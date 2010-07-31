# -*- coding: utf-8 -*-

import os
import time
from imapclient import IMAPClient
import email.utils
import email.header

from django.db import models
from django.db.models.signals import post_save
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from mail import constants

if settings.IMAPLIB_DEBUG:
    import imaplib
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

        Returns None or an IMAPClient instance (connected).
        """
        if not self.healthy:
            # Spam eggs, bacon and spam
            return
        ssl = self.port == 993
        m = IMAPClient(self.server, port=self.port, ssl=ssl)
        try:
            m.login(self.username, self.password)
            return m
        except IMAPClient.Error:
            return

    def check_credentials(self):
        """
        Tries to authenticate to the configured IMAP server.

        This method alters the ``healthy`` attribute, settings it to True if
        the authentication is successful.

        The ``healthy`` attribute should therefore be checked before attemting
        to download anything from the IMAP server.
        """
        ssl = self.port == 993
        m = IMAPClient(self.server, port=self.port, ssl=ssl)
        try:
            m.login(self.username, self.password)
            self.healthy = True
        except IMAPClient.Error:
            self.healthy = False

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

    def update_tree(self, directory="", update_counts=True, connection=None):
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

        pattern = '%'
        if directory:
            pattern = '%s/%%' % directory
        directories = m.list_folders(directory="", pattern=pattern)

        parent = None
        if directory:
            parent = self.directories.get(name=directory)

        dirs = []
        for d in directories:
            name = d[2]

            ftype = _guess_folder_type(name.lower())

            from mail.models import Directory  # XXX
            dir_, created = Directory.objects.get_or_create(mailbox=self,
                                                            name=name)
            dir_.parent = parent
            dir_.has_children = '\\HasChildren' in d[0]
            if dir_.has_children:
                children = self.update_tree(directory=name, connection=m)
                for child in children:
                    dirs.append(child)
            dir_.no_select = '\\Noselect' in d[0]
            dir_.no_inferiors = '\\NoInferiors' in d[0]
            dir_.folder_type = ftype
            dir_.save()
            dirs.append(dir_)

        if not directory:
            # Deleting 'old' directories. If things have changed on
            # the server via another client for instance
            uptodate_dirs = [d.name for d in dirs]
            self.directories.exclude(name__in=uptodate_dirs).delete()

        if update_counts:
            for dir_ in dirs:
                if dir_.no_select:
                    continue
                dir_.count_messages(update=True, connection=m)

        if connection is None:
            m.logout()

        if directory:
            return dirs
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

    if name in ('spam', 'junk', '[gmail]/spam'):
        return constants.SPAM

    if name.startswith('[gmail]'):
        return constants.OTHER
    return constants.NORMAL
