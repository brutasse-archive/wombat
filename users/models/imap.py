# -*- coding: utf-8 -*-

import os
import re
import time
import datetime
import imaplib
import email.utils
import email.header
from email.parser import Parser

from django.db import models
from django.db.models.signals import post_save
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
        Shortcut that is used by every method that needs an IMAP connection
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
            # There is no special exception in case of a failed login.
            # Catching the message instead.
            if not 'Invalid credentials' in str(e):  # e.message is deprecated
                # There is maybe another exception...
                raise e
            else:
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
            # Don't even try to update the mailbox tree if the credentials
            # aren't valid
            return

        if connection is None:
            m = self.get_connection()
        else:
            m = connection

        (status, directories) = m.list()

        dirs = []
        if not status == 'OK':
            return

        for d in directories:
            # d should look like:
            # (\HasChildren) "/" "Archives"
            # Or
            # (\HasNoChildren) "/" "Archives/Web"
            # Or even
            # (\Noselect \HasChildren) "/" "[Gmail]"
            # It's a string
            details = d.split('"')
            name = utils.decode(details[-2])

            # Is it a special directory?
            ftype = _guess_folder_type(name.lower())
            if ftype == constants.OTHER:
                name = name.replace('[Gmail]/', '')

            dir_, created = Directory.objects.get_or_create(mailbox=self,
                                                            name=name)
            dir_.has_children = 'HasChildren' in details[0]
            dir_.no_select = 'Noselect' in details[0]
            dir_.folder_type = ftype
            dir_.save()
            dirs.append(dir_)

        # Deleting 'old' directories. If things have changed on the server
        # via another client for instance
        uptodate_dirs = [d.name for d in dirs]
        to_delete = self.directories.exclude(name__in=uptodate_dirs)
        to_delete.delete()

        if update_counts:
            # Update the directory counts
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
    This represents a directory in the IMAP tree. Its attributes are cached for
    performance/latency reasons and should be easy to update on demand or on a
    regular basis.
    """
    mailbox = models.ForeignKey(IMAP, verbose_name=_('Mailbox'),
                                related_name='directories')
    name = models.CharField(_('Name'), max_length=255)

    # A directory can have directories in it, or not.
    has_children = models.BooleanField(_('Has children'), default=False)

    # A directory may be able only to contain directories, not messages.
    # If no_select is true, we can't store messages in it.
    # If false, yes we can.
    no_select = models.BooleanField(_('Can\'t store messages'), default=False)

    # Caching the unread & total counts directly in the DB
    unread = models.PositiveIntegerField(_('Unread messages'), default=0)
    total = models.PositiveIntegerField(_('Number of messages'), default=0)

    # Folders types: Inbox, Trash, Spam...
    folder_type = models.IntegerField(_('Folder type'),
                                      choices=constants.FOLDER_TYPES,
                                      default=constants.NORMAL, db_index=True)

    def __unicode__(self):
        if not self.folder_type == constants.NORMAL:
            if self.folder_type == constants.OTHER:
                return self.name
            return self.get_folder_type_display()
        return self.name

    class Meta:
        ordering = ('name',)
        verbose_name_plural = _('Directories')
        app_label = 'users'

    def message_counts(self, connection=None, update=True):
        """
        Checks the number of messages on the server, depending on their
        statuses. Returns a dictionnary:
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

    def message_list(self, number_of_messages=50, offset=0, connection=None):
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

        # Select the directory to list
        status, response = m.select(utils.encode(self.name))

        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        # Fetch the UIDs of the messages in this directory
        status, ids = m.search(None, 'ALL')

        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        ids_list = ids[0].split()
        if not ids_list:  # No message in this list
            if connection is None:
                m.close()
            return []

        number_of_messages = min(number_of_messages, len(ids_list))
        begin = - (number_of_messages + offset)
        end = - offset - 1
        fetch_range = '%s:%s' % (ids_list[begin], ids_list[end])

        # Those are the headers we're interested in:
        # * From, To, Date, Subject for display
        # * Message-ID and In-Reply-To for grouping messages by threads
        status, response = m.fetch(fetch_range,
                                   ('(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER.'
                                    'FIELDS (Date From To Cc Subject Message-'
                                    'ID References In-Reply-To)]'
                                    ' BODYSTRUCTURE)'))

        # We're done with the IMAP
        m.close()
        if connection is None:
            m.logout()

        if not status == 'OK':
            print 'Fetching headers returned %s (message %s)' % (status,
                                                                 response)
            return

        # The list to fill with message info
        messages = []

        # Getting the flags of each message
        flag_re = r'^(\d+) \(UID \d+ RFC822\.SIZE \d+ FLAGS \(([^\)]*)\)'
        # And the body structure
        body_re = r'\) BODYSTRUCTURE \((.+)\) BODY'

        for msg in response:
            content= msg[0]
            if content == ')':  # That's an imaplib weirdness
                continue
            elements = re.search(flag_re, content)
            bodystructure = re.search(body_re, content)
            message = {
                'uid': int(elements.group(1)),
                'read': 'Seen' in elements.group(2).replace('\\', ''),
                'attachment': 'attachment' in bodystructure.group(1).lower(),
            }

            headers = msg[1].split('\r\n')
            for header in headers:
                if not header or not ':' in header:
                    continue
                (key, value) = header.split(':', 1)
                value = _clean_header(value.strip())
                key = key.lower()
                message[key] = value
                if key == 'date':
                    message[key] = self._imap_to_datetime(value)
                elif key in ('from', 'to'):
                    message[key] = email.utils.parseaddr(value)

            messages.append(message)

        # Sorting the messages by date, most recent first
        messages.sort(key=lambda item: item['date'], reverse=True)
        return messages

    def get_message(self, uid, connection=None):
        """
        Fetches a full message from this diretcory, given its UID.

        Returns (body, headers, raw), where:
        - body is a string containing the plain-text version of the email
        - headers is a dictionnary containing all the available headers in
        this message
        - raw is the unparsed source of this message
        """
        if connection is None:
            m = self.mailbox.get_connection()
        else:
            m = connection

        if m is None:
            return

        status, result = m.select(utils.encode(self.name))
        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        status, response = m.fetch(uid, 'RFC822')
        # We *might* want to fetch the other messages of the conversation. But
        # for now:
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


class Message(object):
    raw = ''
    headers = {}
    body = ''

    def __init__(self, content):
        self.raw = content
        self.parse()

    def parse(self):
        """Fetches the content of the message and populates the available
        headers"""
        p = Parser()
        message = p.parsestr(self.raw)
        is_utf8 = False
        for part in message.walk():
            # VERY important to handle different encodings correctly
            charset = part.get_content_charset()
            if part.get_content_type() == 'text/plain':
                for header, to_clean in part.items():
                    self.headers[header.lower()] = _clean_header(to_clean)
                self.body += part.get_payload(decode=1)

        if charset is not None:
            self.body = self.body.decode(charset)


def _clean_header(header):
    """
    The headers returned by the IMAP server are not necessarily
    human-friendly, especially if they contain non-ascii characters. This
    function cleans all of this and return a beautiful, utf-8 encoded
    header.
    """
    cleaned = email.header.decode_header(header)
    assembled = ''
    for element in cleaned:
        if assembled == '':
            separator = ''
        else:
            separator = ' '
        if element[1] is not None:
            decoded = element[0].decode(element[1])
        else:
            decoded = element[0]
        assembled += '%s%s' % (separator, decoded)
    return assembled

def _guess_folder_type(name):
    """
    Guesses the type of the folder given its name. Returns a constant to put
    in the ``folder_type`` attribute of the folder.
    """
    if name in ('inbox',):
        return constants.INBOX

    if name in ('drafts', '[gmail]/drafts'):
        return constants.DRAFTS

    if name in ('outbox', '[gmail]/sent mail'):
        return constants.OUTBOX

    if name in ('queue'):
        return constants.QUEUE

    if name in ('trash', '[gmail]/trash'):
        return constants.TRASH

    if name.startswith('[gmail]/'):
        return constants.OTHER
    # Finally...
    return constants.NORMAL
