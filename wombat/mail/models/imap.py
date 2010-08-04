# -*- coding: utf-8 -*-
# Useful resources regarding the IMAP implementation:
# ===================================================
#
# * Best practices: http://www.imapwiki.org/ClientImplementation
# * IMAP4rev1 RFC: http://tools.ietf.org/html/rfc3501

import email.header
import email.parser
import imapclient
import mongoengine

from django.conf import settings
from django.db import models
from django.utils.encoding import smart_unicode
from django.utils.html import strip_tags
from django.utils.text import unescape_entities
from django.utils.translation import ugettext_lazy as _

from mail.fields import UUIDField, SeparatedValuesField

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

            dir_, created = Mailbox.objects.get_or_create(imap=self,
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


class Mailbox(models.Model):
    """
    Represents a directory in the IMAP tree. Its attributes are cached
    for performance/latency reasons and should be easy to update on
    demand or on a regular basis.
    """
    imap = models.ForeignKey(IMAP, verbose_name=_('Mailbox'),
                             related_name='directories')  # XXX rename
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
        ordering = ('imap', 'name')
        verbose_name_plural = _('Mailboxes')
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
        m = self.imap.get_connection()
        msg = Message(uid=uid)
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

        This method returns a list of ``Message`` instances.
        """
        if connection is None:
            m = self.imap.get_connection()
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

        m.select_folder(self.name, readonly=True)
        response = m.fetch(fetch_range, ['FLAGS', 'RFC822.SIZE', 'ENVELOPE',
                                         'BODYSTRUCTURE', 'INTERNALDATE'])
        m.close_folder()

        if connection is None:
            m.logout()

        messages = []
        for uid, msg in response.items():
            message = Message(uid=uid, mailbox=self.id,
                              msg_dict=msg, update=False)
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
            m = self.imap.get_connection()
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
            m = self.imap.get_connection()
        else:
            m = connection

        if m is None:
            return

        m.select_folder(self.name, readonly=True)

        # Fetch the UIDs of the messages in this directory
        uids = m.search(['NOT DELETED'])
        m.close_folder()

        if connection is None:
            m.logout()
        return uids

    def unread_message(self, uid, connection=None):
        if connection is None:
            m = self.imap.get_connection()
        else:
            m = connection

        if m is None:
            return

        m.select_folder(self.name)
        m.remove_flags([uid], imapclient.SEEN)
        m.close_folder()
        if connection is None:
            m.logout()

    def move_message(self, uid, dest, connection=None):
        if connection is None:
            m = self.imap.get_connection()
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
        trash = self.imap.directories.filter(folder_type=TRASH).get()
        return self.move_message(uid, trash.name, connection=connection)

    def get_messages(self):
        return Message.objects(mailbox=self.id)

    def update_messages(self, connection=None):
        if connection is None:
            m = self.imap.get_connection()
        else:
            m = connection

        db_uids = set([msg.uid for msg in self.get_messages().only('uid')])
        imap_uids = set(self.get_uids(connection=m))

        remove_from_db = list(db_uids - imap_uids)
        self.get_messages().filter(uid__in=remove_from_db).delete()

        fetch_from_imap = list(imap_uids - db_uids)
        fetch_from_imap = map(str, fetch_from_imap)

        if fetch_from_imap:
            print "Updating %s messages" % len(fetch_from_imap)
            messages = self.list_messages(force_uids=fetch_from_imap,
                                          connection=m)
        else:
            messages = ()

        if connection is None:
            m.logout()

        account_mailboxes = self.imap.directories.values_list('id', flat=True)
        for message in messages:
            account_messages = Message.objects(mailbox__in=account_mailboxes)
            if message.message_id is None and message.in_reply_to is None:
                message.assign_new_thread()
                continue

            qs = []
            if message.message_id is not None:
                qs.append({'in_reply_to': message.message_id})
            if message.in_reply_to is not None:
                qs.append({'message_id': message.in_reply_to})
                qs.append({'in_reply_to': message.in_reply_to})

            thread_messages = []
            for query in qs:
                thread_messages += account_messages.filter(**query)

            threads = set()
            for msg in thread_messages:
                threads.add(msg.thread)

            if not threads:
                message.assign_new_thread()
                continue

            current_thread = threads.pop()
            if len(threads) > 0:  # Merge threads
                for msg in thread_messages:
                    msg.thread = current_thread
                    msg.save(safe=True)

                for empty_thread in threads:
                    now_count = empty_thread.get_message_count()
                    if now_count == 0:
                        empty_thread.delete()
                    else:
                        print "%s is not empty (%s messages)" % (empty_thread,
                                                                 now_count)
            message.thread = current_thread
            message.save()


class Thread(mongoengine.Document):
    """
    Every message is tied to a thread. Putting it in the DB have several
    advantages:
        * Having reliable, persistent URLs for threads is trivial
        * It makes it easy to regroup messages in the same thread even if
          they're not in the same mailbox.
    Threads are "flat", there is no tree structure. Sort of like gmail.
    """
    pass

    def __unicode__(self):
        return u'%s' % self.id

    def get_message_count(self):
        return len(Message.objects(thread=self))


class Message(mongoengine.Document):
    uid = mongoengine.IntField()
    message_id = mongoengine.StringField()
    in_reply_to = mongoengine.StringField()
    date = mongoengine.DateTimeField()
    subject = mongoengine.StringField()
    fro = mongoengine.StringField()  # I wish I could call it 'from'
    to = mongoengine.ListField(mongoengine.StringField())
    sender = mongoengine.StringField()
    reply_to = mongoengine.StringField()
    cc = mongoengine.ListField(mongoengine.StringField())
    bcc = mongoengine.ListField(mongoengine.StringField())
    size = mongoengine.IntField()
    read = mongoengine.BooleanField(default=False)

    # Fields fetched for each message individually
    fetched = mongoengine.BooleanField(default=False)
    body = mongoengine.StringField()
    html_body = mongoengine.StringField()
    mailbox = mongoengine.IntField()
    thread = mongoengine.ReferenceField(Thread)

    meta = {
        'indexes': ['uid', 'message_id', 'in_reply_to', 'date'],
        'ordering': ['-date'],
    }

    def __unicode__(self):
        return u'%s' % self.subject

    def __init__(self, *args, **kwargs):
        """
        Creates a ``Message`` instance.

        ``msg_dict`` can be passed to populate lots of attributes.
        Set ``update`` to False if you don't want the model
        to be saved.
        """
        msg_dict = kwargs.pop('msg_dict', None)
        update = kwargs.pop('update', True)
        super(Message, self).__init__(*args, **kwargs)

        if msg_dict is not None:
            self.parse_dict(msg_dict, update=update)
        self.attachment = None # XXX see BODYSTRUCTURE

    def parse_dict(self, msg_dict, update=True):
        """
        Parsed the response from a FETCH command and populates as
        much headers as possible

        if ``update`` is set to False, the model won't be saved
        once parse.
        """
        self.read = imapclient.SEEN in msg_dict['FLAGS']
        self.size = msg_dict['RFC822.SIZE']
        self.date = msg_dict['INTERNALDATE']
        self.subject = clean_header(msg_dict['ENVELOPE'][1])
        self.in_reply_to = msg_dict['ENVELOPE'][8]
        self.message_id = msg_dict['ENVELOPE'][9]

        addresses = {
            'from': msg_dict['ENVELOPE'][2],
            'sender': msg_dict['ENVELOPE'][3],
            'reply-to': msg_dict['ENVELOPE'][4],
            'to': msg_dict['ENVELOPE'][5],
            'cc': msg_dict['ENVELOPE'][6],
            'bcc': msg_dict['ENVELOPE'][7],
        }

        for key, value in addresses.items():
            if value is not None:
                addresses[key] = address_struct_to_addresses(value)

        self.to = addresses['to']
        self.fro = addresses['from'][0]
        self.sender = addresses['sender'][0]
        self.reply_to = addresses['reply-to'][0]
        self.cc = addresses['cc']
        self.bcc = addresses['bcc']
        if update:
            self.save()

    def fetch(self, m):
        """
        Fetches message content from the server.
        ``m`` is an imapclient.IMAPClient instance, logged in.
        """
        m.select_folder(self.mailbox.name, readonly=True)
        response = m.fetch([self.uid], ['RFC822', 'FLAGS'])
        m.close_folder()
        self.read = imapclient.SEEN in response[self.uid]['FLAGS']
        self.parse(response[self.uid]['RFC822'])

    def parse(self, raw_email, update=True):
        """
        Fetches the content of the message and populates the available headers
        """
        body = u''
        html_body = u''
        msg = email.parser.Parser().parsestr(raw_email)

        for part in msg.walk():
            for key, header in part.items():
                self.headers[key.lower()] = clean_header(header)

            payload = part.get_payload(decode=1)
            charset = part.get_content_charset()
            if charset is not None:
                payload = payload.decode(charset)

            if part.get_content_type() == 'text/plain':
                body += payload

            if part.get_content_type() == 'text/html':
                html_body += payload

        if not body:
            body = unescape_entities(strip_tags(html_body))
        self.body = body
        self.html_body = html_body
        if update:
            self.save()

    def assign_new_thread(self):
        thread = Thread()
        thread.save()
        self.thread = thread
        self.save()


def address_struct_to_addresses(address_struct):
    """
    Converts an IMAP "address structure" to a proper list of email
    addresses with a format looking like:
        ('First Last <username@example.com>',
         'Other Dude <foo.bar@baz.org>')
    """
    addresses = []
    for name, at_domain, mailbox_name, host in address_struct:
        if name is None:
            addresses.append('%s@%s' % (mailbox_name, host))
            continue
        name = clean_header(name)
        cleaned = '%s <%s@%s>' % (name, mailbox_name, host)
        addresses.append(cleaned)
    return addresses


def clean_header(header):
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
