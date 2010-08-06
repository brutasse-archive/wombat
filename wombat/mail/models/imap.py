# -*- coding: utf-8 -*-
# Useful resources regarding the IMAP implementation:
# ===================================================
#
# * Best practices: http://www.imapwiki.org/ClientImplementation
# * IMAP4rev1 RFC: http://tools.ietf.org/html/rfc3501

import imapclient

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _

from mail.models.mongo import Message, Thread
from mail.utils import clean_subject

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

        for directory in self.directories.exclude(no_select=True):
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
        return reversed(messages)

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

    def get_uids_in_db(self):
        """
        Returns the UIDs of messages in this mailbox & stored in the DB
        """
        uids = set()
        threads = Thread.objects(mailboxes=self.id)
        for t in threads:
            for m in t.messages:
                if m.mailbox == self.id:
                    uids.add(m.uid)
        return uids

    def update_messages(self, connection=None):
        if connection is None:
            m = self.imap.get_connection()
        else:
            m = connection

        db_uids = self.get_uids_in_db()
        imap_uids = set(self.get_uids(connection=m))

        remove_from_db = list(db_uids - imap_uids)
        threads_remove = Thread.objects(mailboxes=self.id,
                                        messages__uid__in=remove_from_db)
        for t in threads_remove:
            t.remove_message(self.id, remove_from_db)

        fetch_from_imap = map(str, list(imap_uids - db_uids))

        messages = ()
        if fetch_from_imap:
            print "Updating %s messages" % len(fetch_from_imap)
            messages = self.list_messages(force_uids=fetch_from_imap,
                                          connection=m)

        m.select_folder(self.name)
        unseen = m.search(['NOT SEEN'])
        m.close_folder()

        if connection is None:
            m.logout()

        account_mailboxes = self.imap.directories.values_list('id', flat=True)
        for message in messages:
            if message.message_id is None and message.in_reply_to is None:
                message.assign_new_thread()
                continue

            qs = []
            if message.message_id is not None:
                qs.append({'messages__in_reply_to': message.message_id})
            if message.in_reply_to is not None:
                qs.append({'messages__message_id': message.in_reply_to})
                qs.append({'messages__in_reply_to': message.in_reply_to})

            threads = set()
            for query in qs:
                for t in Thread.objects(mailboxes__in=account_mailboxes).filter(**query):
                    threads.add(t)

            if not threads:
                subject = clean_subject(message.subject)
                if subject != message.subject:
                    # This is a Re: RE or whatever without any In-Reply-To.
                    # Trying to guess which thread it's in.
                    thrds = Thread.objects(mailboxes__in=account_mailboxes)
                    thrds = thrds.filter(messages__subject=subject)
                    for t in thrds.order_by('-date'):
                        threads.add(t)
                        break

            if not threads:
                message.assign_new_thread()
                continue

            current_thread = threads.pop()
            if len(threads) > 0:  # Merge threads
                for thread in threads:
                    current_thread.merge_with(thread)
            current_thread.add_message(message)

        threads = Thread.objects(mailboxes=self.id)
        for t in threads:
            t.ensure_unread(self.id, unseen)

    def fetch_messages(self, uids, m):
        """
        Fetch the content of a few messages, given the UID.
        """
        m.select_folder(self.name, readonly=True)
        response = m.fetch(uids, ['RFC822', 'FLAGS'])
        m.close_folder()
        return response
