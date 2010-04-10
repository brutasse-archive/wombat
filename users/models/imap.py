# -*- coding: utf-8 -*-

import os
import time
import imaplib
import email.utils
import email.header

from django.db import models
from django.db.models.signals import post_save
from django.utils.html import strip_tags
from django.utils.text import unescape_entities
from django.utils.translation import ugettext_lazy as _

import utils

from mail import constants

imaplib.Debug = 4

# Useful resources regarding the IMAP implementation:
# ===================================================
#
# * Best practices: http://tools.ietf.org/html/rfc3501
# * IMAP4rev1 RFC: http://www.imapwiki.org/ClientImplementation

# Unit testing the imap client
# ============================
#
# If we're running the unit tests -- which we're doing using the test_settings
# module, we monkeypatch the imaplib to ship a mock imap client.
if 'test' in os.environ['DJANGO_SETTINGS_MODULE']:
    from users.tests.mock_imaplib import IMAP4_SSL
    imaplib.IMAP4_SSL = IMAP4_SSL


class IMAP(models.Model):
    """
    A wombat user can have several IMAP configurations. The information about
    those accounts is stored here, including login credentials.
    """
    server = models.CharField(_('Server'), max_length=255)

    # Port: 585 for IMAP4-SSL, 993 for IMAPS (Gmail default)
    port = models.PositiveIntegerField(_('Port'), default=143,
                                       help_text=_("(993 with SSL)"))
    username = models.CharField(_('Username'), max_length=255)

    # TODO: have a look at http://docs.python.org/library/hmac.html
    # We have to find a way to store passwords in an encrypted way, and having
    # the database stolen should not be compromising
    password = models.CharField(_('Password'), max_length=255)

    # A way to tell the user that his account is well configured or
    # something is wrong.
    healthy = models.BooleanField(_('Healthy account'), default=False)

    def __unicode__(self):
        return u'%s imap' % self.account

    class Meta:
        verbose_name = _('IMAP config')
        verbose_name_plural = _('IMAP configs')
        app_label = 'users'

    def get_connection(self):
        """
        Shortcut used by every method that needs an IMAP connection
        instance.

        Returns None or an imaplib.IMAP4_SSL instance (connected).
        """
        if not self.healthy:
            # Spam eggs, bacon and spam
            return

        m = imaplib.IMAP4_SSL(self.server, self.port)
        (status, response) = m.login(self.username, self.password)
        if not status == 'OK':
            return
        return m

    def check_credentials(self):
        """
        Tries to authenticate to the configured IMAP server.

        This method alters the ``healthy`` attribute, settings it to True if
        the authentication is successful.

        The ``healthy`` attribute should therefore be checked before attemting
        to download anything from the IMAP server.
        """
        m = imaplib.IMAP4_SSL(self.server, self.port)
        try:
            response = m.login(self.username, self.password)
            if 'OK' in response:
                self.healthy = True
        except Exception, e:
            # There is no special exception for a failed login, bare except.
            self.healthy = False
        # That was it, closing the connection
        m.logout()
        return self.healthy

    def check_mail(self, connection=None):
        """
        Refresh all directories for this connection.
        """
        if not self.healthy:
            return

        if connection is None:
            m = self.get_connection()
        else:
            m = connection

        for directory in self.directories.all():
            directory.count_messages(connection=m)
        m.logout()

    def update_tree(self, update_counts=True, connection=None):
        """
        Updates directories statuses cached in the database.

        Returns the number of directories or None if failed.
        """
        if not self.healthy:
            return

        if connection is None:
            m = self.get_connection()
        else:
            m = connection

        (status, directories) = m.list()

        if not status == 'OK':
            return

        dirs = []
        for d in directories:
            # d should look like:
            # (\HasChildren) "/" "Archives"
            # Or
            # (\HasNoChildren) "/" "Archives/Web"
            # Or even
            # (\Noselect \HasChildren) "/" "[Gmail]"
            details = d.split('"')
            name = utils.decode(details[-2])

            ftype = _guess_folder_type(name.lower())

            dir_, created = Directory.objects.get_or_create(mailbox=self,
                                                            name=name)
            dir_.has_children = 'HasChildren' in details[0]
            dir_.no_select = 'Noselect' in details[0]
            dir_.no_inferiors = 'NoInferiors' in details[0]
            dir_.folder_type = ftype
            dir_.save()
            dirs.append(dir_)

        # Deleting 'old' directories. If things have changed on the
        # server via another client for instance
        self.directories.exclude(name__in=[d.name for d in dirs]).delete()

        if update_counts:
            for dir_ in dirs:
                dir_.count_messages(update=True, connection=m)

        if connection is None:
            m.logout()

        return len(dirs)


def update_tree_on_save(sender, instance, created, **kwargs):
    """
    When an account is saved, the cached directories are automatically updated.
    """
    if instance.healthy:
        instance.update_tree()
post_save.connect(update_tree_on_save, sender=IMAP)


def _guess_folder_type(name):
    """
    Guesses the type of the folder given its name. Returns a constant to put
    in the ``folder_type`` attribute of the folder.
    """
    if name in ('inbox',):
        return constants.INBOX

    if name in ('drafts', '[gmail]/drafts'):
        return constants.DRAFTS

    if name in ('outbox', 'sent', '[gmail]/sent mail'):
        return constants.OUTBOX

    if name in ('queue'):
        return constants.QUEUE

    if name in ('trash', '[gmail]/trash'):
        return constants.TRASH

    if name.startswith('[gmail]/'):
        return constants.OTHER
    return constants.NORMAL
