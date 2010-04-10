# -*- coding: utf-8 -*-

import os
import re
import time
import datetime
import imaplib
import email.utils
import email.header

from django.db import models
from django.db.models.signals import post_save
from django.core.cache import cache
from django.utils.html import strip_tags
from django.utils.text import unescape_entities
from django.utils.translation import ugettext_lazy as _

import utils

from mail import constants
from mail.models import Message

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


FLAG_RE = re.compile(r'^(\d+) .* FLAGS \(([^\)]*)\)')
BODY_RE = re.compile(r'BODYSTRUCTURE \((.+)\)')


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
                dir_.message_counts(update=True, connection=m)

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


class Directory(models.Model):
    """
    Represents a directory in the IMAP tree. Its attributes are cached
    for performance/latency reasons and should be easy to update on
    demand or on a regular basis.
    """
    mailbox = models.ForeignKey(IMAP, verbose_name=_('Mailbox'),
                                related_name='directories')
    name = models.CharField(_('Name'), max_length=255)

    # IMAP attributes
    has_children = models.BooleanField(_('Has children'), default=False)
    no_select = models.BooleanField(_('Cannot store messages'), default=False)
    no_inferiors = models.BooleanField(_('Cannot store folders'), default=False)

    # Caching the unread & total counts directly in the DB
    unread = models.PositiveIntegerField(_('Unread messages'), default=0)
    total = models.PositiveIntegerField(_('Number of messages'), default=0)

    # Folders types: Inbox, Trash, Spam...
    folder_type = models.IntegerField(_('Folder type'),
                                      choices=constants.FOLDER_TYPES,
                                      default=constants.NORMAL, db_index=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = _('Directories')
        app_label = 'users'

    def __unicode__(self):
        if not self.folder_type == constants.NORMAL:
            if self.folder_type == constants.OTHER:
                return self.name.replace('[Gmail]/', '')  # XXX GMail-only Fix
            return self.get_folder_type_display()
        return self.name

    def get_message(self, uid):
        # Cache key: message-bob@example.comINBOX1234
        cache_key = utils.safe_cache_key(
                    'message-%s%s%s' % (self.mailbox.username, self.name, uid))
        message = cache.get(cache_key, None)
        if message is None:
            message = self._fetch_message(uid)
            if message is not None:
                cache.set(cache_key, message)
        return message

    def get_messages(self, page):
        number_of_messages = min(self.total, 50)

        # Fetching a message list makes a call to the IMAP server.
        # Trying to fetch
        # from the cache before, it's much faster...
        # Cache key: list-bob@example.comINBOX0
        cache_key = utils.safe_cache_key('list-%s%s%s' % (self.mailbox.username,
                                                    self.name,
                                                    page))
        messages = cache.get(cache_key, None)

        if messages is None:
            messages = self.message_list(number_of_messages=number_of_messages)
            if messages is not None:
                cache.set(cache_key, messages)
        return messages

    def message_counts(self, connection=None, update=True):
        """
        Checks the number of messages on the server, depending on their
        statuses.

        Returns a dictionnary:
        {
            'total': the total amount of messages,
            'unread': the number of unread messages,
            'uidnext': the next available UID that we can assign to a message
            'uidvalidity': this allows us to check if something has changed in
            our back.
        }
        See http://tools.ietf.org/html/rfc3501#section-2.3.1.1 for details
        about UIDs.

        If the remote directory can't store messages, this returns None

        This should probably be cached (here or in memcache) and refreshed
        every <whatever> minutes when the user is online.
        """
        if connection is None:
            m = self.mailbox.get_connection()
        else:
            m = connection

        if m is None:
            return

        statuses = '(MESSAGES UIDNEXT UIDVALIDITY UNSEEN)'
        status, response = m.status('"%s"' % utils.encode(self.name), statuses)
        if connection is None:
            m.logout()  # KTHXBYE

        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        # 'response' looks like:
        # ['"Archives" (MESSAGES 2423 UIDNEXT 2554 UIDVALIDITY 8 UNSEEN 0)']
        # (it's a tuple with one element: a string)
        search = r'MESSAGES (\d+) UIDNEXT (\d+) UIDVALIDITY (\d+) UNSEEN (\d+)'
        numbers = re.search(search, response[0])
        values = {
                'total':       int(numbers.group(1)),
                'uidnext':     int(numbers.group(2)),
                'uidvalidity': int(numbers.group(3)),
                'unread':      int(numbers.group(4)),
        }
        if update:
            self.total = values['total']
            self.unread = values['unread']
            self.save()

        return values

    def get_uids(self, connection=None):
        """Lists the UIDs of the messages stored in this folder.

        Returns a list of the messages' UIDs"""
        if connection is None:
            m = self.mailbox.get_connection()
        else:
            m = connection

        if m is None:
            return

        # Select the directory to list
        status, response = m.select(utils.encode(self.name), readonly=True)

        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        # Fetch the UIDs of the messages in this directory
        status, ids = m.search(None, 'ALL')
        m.close()

        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        if connection is None:
            m.logout()

        uids = ids[0].split()
        if not uids:  # No message in this list
            return []
        return uids

    def message_list(self, number_of_messages=50, offset=0, force_uids=None,
                     connection=None):
        """
        Fetches a list of message headers from the server. This lists some of
        the messages that are stored in this very directory.

        The number_of_messages determines the the number of messages to return.
        If it is greater than the number of messages in the folder, the whole
        list will be returned.

        The ``offset`` can be used for pagination: the messages will be
        displayed as paginated list (with, say, 50 messages per page) and we
        don't need to retrieve the whole list when we display a single page.

        ``message_list(offset=50)`` will retrieve the list to show on the
        second page.

        ``force_uids`` can be used if you're only interested in a few
        messages. ``message_list(force_uids=[23, 25])`` will return you the
        status of those two messages. It is useless to set ``offset`` and
        ``number_of_messages`` if you specify ``force_uids``.

        This method returns a tuple containing dictionnaries, each of them
        representing an email, with the following attributes:
        {
            'uid': the uid of the message in the directory,
            'from': the sender,
            'to': the recipients list,
            'subject': the subject of the message. This may be an empty string,
            'read': whether the message has been flagged as Seen or not,
            'message-id': the header identifying this message,
            (if applicable) 'in-reply-to': the message-id of the message this
            one replies to
        }
        """
        if connection is None:
            m = self.mailbox.get_connection()
        else:
            m = connection

        if m is None:
            return

        if force_uids is None:
            ids_list = self.get_uids(connection=m)
            if not len(ids_list):
                return []

            number_of_messages = min(number_of_messages, len(ids_list))
            begin = - (number_of_messages + offset)
            end = - offset - 1
            fetch_range = '%s:%s' % (ids_list[begin], ids_list[end])
        else:
            fetch_range = ','.join(force_uids)

        status, result = m.select(utils.encode(self.name), readonly=True)
        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        # Those are the headers we're interested in:
        # * From, To, Date, Subject for display
        # * Message-ID and In-Reply-To for grouping messages by threads
        status, response = m.fetch(fetch_range,
                                   ('(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.'
                                    'FIELDS (Date From To Cc Subject Message-'
                                    'ID References In-Reply-To)]'
                                    ' BODYSTRUCTURE)'))

        # We're done with the IMAP
        if connection is None:
            m.logout()

        if not status == 'OK':
            print 'Fetching headers returned %s (message %s)' % (status,
                                                                 response)
            return

        # The list to fill with message info
        messages = []

        # FIXME -- Some servers return 2 responses: one for FLAGS+headers,
        # one for BODYSTRUCTURE. This hack moves a double response into a
        #single one
        if (force_uids and 2*len(force_uids) == len(response)) or \
                (force_uids is None and 2*len(ids_list) == len(response)):
            rsp = []
            for i in range(0, len(response), 2):
                msg = ''.join((response[i][0], response[i+1]))
                rsp.append([msg, response[i][1]])
            response = rsp

        for msg in response:
            content = msg[0]
            if content == ')':  # That's an imaplib weirdness
                continue

            flags = FLAG_RE.search(content)
            bodystructure = BODY_RE.search(content)
            message = {
                'uid': int(flags.group(1)),
                'read': 'Seen' in flags.group(2).replace('\\', ''),
                'attachment': 'attachment' in bodystructure.group(1).lower(),
            }

            headers = msg[1].split('\r\n')
            for header in headers:
                if not header or not ':' in header:
                    continue
                (key, value) = header.split(':', 1)
                value = Message._clean_header(value.strip())
                key = key.lower()
                message[key] = value
                if key == 'date':
                    message[key] = self._imap_to_datetime(value)
                elif key in ('from', 'to'):
                    message[key] = email.utils.parseaddr(value)

            messages.append(message)

        messages.sort(key=lambda item: item['date'], reverse=True)
        return messages

    def unread_message(self, uid, connection=None):
        if connection is None:
            m = self.mailbox.get_connection()
        else:
            m = connection

        if m is None:
            return

        status, response = m.select(utils.encode(self.name))
        status, response = m.store(uid, '-FLAGS.SILENT', '\\Seen')
        status, response = m.close()
        if connection is None:
            m.logout()

    def move_message(self, uid, dest, connection=None):
        if connection is None:
            m = self.mailbox.get_connection()
        else:
            m = connection

        if m is None:
            return

        status, response = m.select(utils.encode(self.name))
        status, response = m.copy(uid, utils.encode(dest))
        status, response = m.store(uid, '+FLAGS.SILENT', '\\Deleted')
        status, response = m.expunge()
        status, response = m.close()

        if connection is None:
            m.logout()

    def delete_message(self, uid, connection=None):
        trash = self.mailbox.directories.filter(folder_type=constants.TRASH).get()
        return self.move_message(uid, trash.name, connection=connection)

    def _fetch_message(self, uid, connection=None):
        """
        Fetches a full message from this diretcory, given its UID.

        Returns a ``Message`` instance.
        """
        if connection is None:
            m = self.mailbox.get_connection()
        else:
            m = connection

        if m is None:
            return

        status, result = m.select(utils.encode(self.name), readonly=True)
        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        status, response = m.fetch(uid, 'RFC822')
        read = self.message_list(force_uids=[uid], connection=m)[0]['read']
        if not read:
            status, response_ = m.store(uid, '+FLAGS.SILENT', '\\Seen')
            if not status == 'OK':
                print 'Unexpected result: "%s"' % status

        m.close()
        if connection is None:
            m.logout()

        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        # Response[0] only is interesting, it is a tuple
        # response[0][0]: '9 (RFC822 {4854}'
        # response[0][1]: the raw email (source)
        raw_email = response[0][1]

        return Message(raw_email)

    def _imap_to_datetime(self, date_string):
        """
        Returns a datetime.datetime instance given an IMAP date string
        """
        time_tuple = email.utils.parsedate_tz(date_string)
        return datetime.datetime(*time_tuple[:6])



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
