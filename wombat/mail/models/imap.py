# -*- coding: utf-8 -*-
# Useful resources regarding the IMAP implementation:
# ===================================================
#
# * Best practices: http://www.imapwiki.org/ClientImplementation
# * IMAP4rev1 RFC: http://tools.ietf.org/html/rfc3501

import email.header
import email.parser
import imapclient
import re

from django.conf import settings
from django.db import models
from django.utils.html import strip_tags
from django.utils.text import unescape_entities
from django.utils.translation import ugettext_lazy as _

FLAG_RE = re.compile(r'^(\d+) .* FLAGS \(([^\)]*)\)')
BODY_RE = re.compile(r'BODYSTRUCTURE \((.+)\)')
HEADER_RE = re.compile(r'^([a-zA-Z0-9_-]+):(.*)$')

# Folder types
NORMAL = 100
INBOX = 10
OUTBOX = 20
DRAFTS = 30
QUEUE = 40
TRASH = 50
SPAM = 60
OTHER = 70  # For proprietary stuff like Gmail's Starred/All mail

FOLDER_TYPES = (
    (NORMAL, _('Normal')),
    (INBOX, _('Inbox')),
    (OUTBOX, _('Outbox')),
    (DRAFTS, _('Drafts')),
    (QUEUE, _('Queue')),
    (TRASH, _('Trash')),
    (SPAM, _('Spam')),
    (OTHER, _('Other')),
)

if settings.IMAP_DEBUG:
    import imaplib
    imaplib.Debug = 4


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
        app_label = 'mail'

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
        m = imapclient.IMAPClient(self.server, port=self.port, ssl=ssl)
        try:
            m.login(self.username, self.password)
            return m
        except imapclient.IMAPClient.Error:
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
        m = imapclient.IMAPClient(self.server, port=self.port, ssl=ssl)
        try:
            m.login(self.username, self.password)
            self.healthy = True
        except imapclient.IMAPClient.Error:
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
            if r'\Noselect' in d[0] or r'\NoInferiors' in d[0]:
                dir_.no_select = True
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
models.signals.post_save.connect(update_tree_on_save, sender=IMAP)


def _guess_folder_type(name):
    """
    Guesses the type of the folder given its name. Returns a constant to put
    in the ``folder_type`` attribute of the folder.
    """
    if name in ('inbox',):
        return INBOX

    if name in ('drafts', '[gmail]/drafts'):
        return DRAFTS

    if name in ('outbox', 'sent', '[gmail]/sent mail'):
        return OUTBOX

    if name in ('queue'):
        return QUEUE

    if name in ('trash', '[gmail]/trash'):
        return TRASH

    if name in ('spam', 'junk', '[gmail]/spam'):
        return SPAM

    if name.startswith('[gmail]'):
        return OTHER
    return NORMAL


class Directory(models.Model):
    """
    Represents a directory in the IMAP tree. Its attributes are cached
    for performance/latency reasons and should be easy to update on
    demand or on a regular basis.
    """
    mailbox = models.ForeignKey(IMAP, verbose_name=_('Mailbox'),
                                related_name='directories')
    name = models.CharField(_('Name'), max_length=255)
    parent = models.ForeignKey('self', related_name='children', null=True)

    # IMAP attributes
    has_children = models.BooleanField(_('Has children'), default=False)
    no_select = models.BooleanField(_('Cannot store messages'), default=False)

    # Caching the unread & total counts directly in the DB
    unread = models.PositiveIntegerField(_('Unread messages'), default=0)
    total = models.PositiveIntegerField(_('Number of messages'), default=0)

    # Folders types: Inbox, Trash, Spam...
    folder_type = models.IntegerField(_('Folder type'),
                                      choices=FOLDER_TYPES,
                                      default=NORMAL, db_index=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = _('Directories')
        app_label = 'mail'

    def __unicode__(self):
        if not self.folder_type == NORMAL:
            if self.folder_type == OTHER:
                return self.name.replace('[Gmail]/', '')  # XXX GMail-only Fix
            return self.get_folder_type_display()

        if self.parent:
            return self.name.replace(self.parent.name + '/', '')
        return self.name

    def get_message(self, uid):
        m = self.mailbox.get_connection()
        msg = Message(uid)
        msg.fetch(m, self.name)
        m.close_folder()
        m.logout()
        return msg

    def get_messages(self, page):
        number_of_messages = min(self.total, 50)
        messages = self.list_messages(number_of_messages=number_of_messages)
        return messages

    def list_messages(self, number_of_messages=50, offset=0, force_uids=None,
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

        ``list_messages(offset=50)`` will retrieve the list to show on the
        second page.

        ``force_uids`` can be used if you're only interested in a few
        messages. ``list_messages(force_uids=[23, 25])`` will return you the
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

        result = m.select_folder(self.name, readonly=True)

        response = m.fetch(fetch_range, ['FLAGS', 'RFC822.SIZE', 'ENVELOPE',
                                         'BODYSTRUCTURE', 'INTERNALDATE'])
        m.close_folder()

        if connection is None:
            m.logout()

        messages = []
        for uid, msg in response.items():
            message = Message(uid=uid, msg_dict=msg)
            messages.append(message)

        messages.sort(key=lambda msg: msg.date, reverse=True)
        return messages

    def count_messages(self, connection=None, update=True):
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

        statuses = m.folder_status(self.name)
        if connection is None:
            m.logout()

        values = {
            'total': statuses['MESSAGES'],
            'uidnext': statuses['UIDNEXT'],
            'uidvalidity': statuses['UIDVALIDITY'],
            'unread': statuses['UNSEEN'],
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
        response = m.select_folder(self.name, readonly=True)

        # Fetch the UIDs of the messages in this directory
        uids = m.search(['NOT DELETED'])
        m.close_folder()

        if connection is None:
            m.logout()
        return uids

    def unread_message(self, uid, connection=None):
        if connection is None:
            m = self.mailbox.get_connection()
        else:
            m = connection

        if m is None:
            return

        response = m.select_folder(self.name)
        response = m.remove_flags([uid], imapclient.SEEN)
        response = m.close_folder()
        if connection is None:
            m.logout()

    def move_message(self, uid, dest, connection=None):
        if connection is None:
            m = self.mailbox.get_connection()
        else:
            m = connection

        if m is None:
            return

        m.select_folder(self.name)
        m.copy([uid], dest)
        m.add_flags([uid], [imapclient.DELETED])
        m.expunge()
        m.close_folder()

        if connection is None:
            m.logout()

    def delete_message(self, uid, connection=None):
        trash = self.mailbox.directories.filter(folder_type=TRASH).get()
        return self.move_message(uid, trash.name, connection=connection)


class Message(models.Model):
    uid = models.PositiveIntegerField()
    dir = models.ForeignKey(Directory)
    read = models.BooleanField()

    class Meta:
        app_label = 'mail'

    # FIXME models.Model already defines __init__ -- should be done differently
    def __init__(self, uid=None, msg_dict=None):
        self.uid = int(uid)
        self.headers = {}
        if msg_dict is not None:
            self.parse_dict(msg_dict)
        self.body = u''
        self.html_body = u''
        self.attachment = None

    def parse_dict(self, msg_dict):
        self.read = imapclient.SEEN in msg_dict['FLAGS']
        self.size = msg_dict['RFC822.SIZE']
        self.date = msg_dict['INTERNALDATE']
        self.headers = {
            'date': msg_dict['INTERNALDATE'],
            'subject': self._clean_header(msg_dict['ENVELOPE'][1]),
            'from': msg_dict['ENVELOPE'][2],
            'sender': msg_dict['ENVELOPE'][3],
            'reply-to': msg_dict['ENVELOPE'][4],
            'cc': msg_dict['ENVELOPE'][5],
            'bcc': msg_dict['ENVELOPE'][6],
            'in-reply-to': msg_dict['ENVELOPE'][7],
            'message-id': msg_dict['ENVELOPE'][8],
        }

        for key in ('from', 'sender', 'reply-to', 'cc', 'bcc'):
            if self.headers[key] is not None:
                self.headers[key] = self.address_struct_to_addresses(self.headers[key])

    def fetch(self, m, dirname):
        """
        Fetches message content from the server. If the message is new, it
        will be implicitly marked as read.
        """
        response = m.select_folder(dirname)
        response = m.fetch([self.uid], ['RFC822', 'FLAGS'])
        self.parse(response[self.uid]['RFC822'])

    def parse(self, raw_email):
        """
        Fetches the content of the message and populates the available headers
        """

        msg = email.parser.Parser().parsestr(raw_email)

        for part in msg.walk():
            for key, header in part.items():
                self.headers[key.lower()] = self._clean_header(header)

            payload = part.get_payload(decode=1)
            charset = part.get_content_charset()
            if charset is not None:
                payload = payload.decode(charset)

            if part.get_content_type() == 'text/plain':
                self.body += payload

            if part.get_content_type() == 'text/html':
                self.html_body += payload

        if not self.body:
            self.body = unescape_entities(strip_tags(self.html_body))

    def address_struct_to_addresses(self, address_struct):
        addresses = []
        for name, at_domain, mailbox_name, host in address_struct:
            if name is None:
                addresses.append('%s@%s' % (mailbox_name, host))
                continue
            name = self._clean_header(name)
            cleaned = '%s <%s@%s>' % (name, mailbox_name, host)
            addresses.append(cleaned)
        return addresses

    @classmethod
    def _clean_header(cls, header):
        """
        The headers returned by the IMAP server are not necessarily
        human-friendly, especially if they contain non-ascii characters. This
        function cleans all of this and return a beautiful, utf-8 encoded
        header.
        """
        if header is None:
            return ''
        if header.startswith('"'):
            header = header.replace('"', '')
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
