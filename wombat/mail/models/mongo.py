# -*- coding: utf-8 -*-
import email.header
import email.parser
import imapclient
from mongoengine import (Document, EmbeddedDocument, IntField, StringField,
                         DateTimeField, ListField, EmbeddedDocumentField,
                         BooleanField)

from django.utils.html import strip_tags
from django.utils.text import unescape_entities

from mail.utils import address_struct_to_addresses, clean_header


class Message(EmbeddedDocument):
    uids = ListField(ListField(IntField()))  # ((1, 324), ... (mbox_id, uid))
    message_id = StringField()
    in_reply_to = StringField()
    date = DateTimeField()
    subject = StringField()
    fro = StringField()  # I wish I could call it 'from'
    to = ListField(StringField())
    sender = StringField()
    reply_to = StringField()
    cc = ListField(StringField())
    bcc = ListField(StringField())
    size = IntField()
    read = BooleanField(default=False)

    # Fields fetched for each message individually
    fetched = BooleanField(default=False)
    body = StringField()
    html_body = StringField()

    meta = {
        'indexes': ['uids', 'message_id', 'in_reply_to', 'date'],
        'ordering': ['date'],
    }

    def __unicode__(self):
        return u'%s' % self.subject

    @property
    def mailboxes(self):
        return [m[0] for m in self.uids]

    def get_uid(self, mbox_id):
        for mbid, uid in self.uids:
            if mbox_id == mbid:
                return uid

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

    def parse(self, raw_email):
        """
        Fetches the content of the message and populates the available headers
        """
        body = u''
        html_body = u''
        msg = email.parser.Parser().parsestr(raw_email)

        for part in msg.walk():
            #for key, header in part.items():
            #    self.headers[key.lower()] = clean_header(header)

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
        #self.html_body = html_body

    def assign_new_thread(self):
        thread = Thread(date=self.date, mailboxes=self.mailboxes,
                        messages=[self])
        thread.save(safe=True)


class Thread(Document):
    """
    Every message is tied to a thread. Putting it in the DB have several
    advantages:
        * Having reliable, persistent URLs for threads is trivial
        * It makes it easy to regroup messages in the same thread even if
          they're not in the same mailbox.
    Threads are "flat", there is no tree structure. Sort of like gmail.
    """
    mailboxes = ListField(IntField())
    date = DateTimeField()
    messages = ListField(EmbeddedDocumentField(Message))

    meta = {
        'indexes': ['mailboxes', 'date'],
        'ordering': ['-date'],
    }

    def __unicode__(self):
        return u'%s' % self.id

    @property
    def subject(self):
        return self.messages[0].subject

    @property
    def read(self):
        return all([m.read for m in self.messages])

    @property
    def last_date(self):
        return self.messages[-1].date

    @property
    def messages_count(self):
        return len(self.messages)

    @property
    def senders(self):
        senders = []
        for msg in self.messages:
            if msg.fro not in senders:
                senders.append(msg.fro)
        return senders

    def merge_with(self, other_thread, mbox_id):
        """
        Steal the messages stored in ``other_thread`` and delete it
        """
        if self.id == other_thread.id:
            # Nothing to merge with
            return
        for msg in other_thread.messages:
            self.add_message(msg, mbox_id, update=False)
        # Sanity check / rebuild if something bad happens to the uids
        for msg in self.messages:
            msg.uids = [uid for uid in msg.uids if uid[1] is not None]
        self.save(safe=True)
        other_thread.delete()

    def add_message(self, message, mbox_id, update=True):
        """
        Appends a message to the thread and updates relevant parameters
        """
        existing = False
        for msg in self.messages:
            if all([msg.date == message.date,
                    msg.fro == message.fro,
                    msg.subject == message.subject]):
                existing = True
                msg.uids.append([mbox_id, message.get_uid(mbox_id)])

        if not existing:
            self.date = max(self.date, message.date)
            self.messages.append(message)

        self.update_mailboxes()
        self.messages.sort(key=lambda m: m.date)
        if update:
            self.save(safe=True)

    def remove_message(self, mailbox_id, message_ids, update=True):
        # message_ids is already a list of (mbox_id, uid) pairs!
        to_remove = []
        for msg in self.messages:
            for uid in msg.uids:
                if mailbox_id in msg.mailboxes and uid in message_ids:
                    if len(msg.mailboxes) == 1:
                        to_remove.append(msg)
                    else:
                        msg.uids = [uid for uid in msg.uids if \
                                    uid[0] != mailbox_id]
        for msg in to_remove:
            self.messages.remove(msg)

        if len(self.messages) == 0:
            self.delete()
            return

        self.update_mailboxes()
        if update:
            self.save(safe=True)

    def ensure_unread(self, mailbox_id, message_ids, update=True):
        message_ids = [[mailbox_id, msg_id] for msg_id in message_ids]
        for msg in self.messages:
            read = True
            for uid in msg.uids:
                if mailbox_id in msg.mailboxes and uid in message_ids:
                    read = False
            msg.read = read
        if update:
            self.save(safe=True)

    def update_mailboxes(self):
        mailboxes = set()
        for m in self.messages:
            for mbox in m.mailboxes:
                mailboxes.add(mbox)
        self.mailboxes = list(mailboxes)

    def get_mailboxes(self):
        from mail.models import Mailbox, OUTBOX
        mboxes = Mailbox.objects.filter(id__in=self.mailboxes)
        return mboxes.exclude(folder_type=OUTBOX)

    def find_missing(self):
        """
        Retuns a dict of {mailboxes: uids} that have not been fetched yet.
        """
        missing = {}
        for message in self.messages:
            if not message.body:
                mbox, uid = message.uids[0]
                if mbox in missing:
                    missing[mbox].append(uid)
                else:
                    missing[mbox] = [uid]
        return missing

    def fetch_missing(self):
        """
        Fetches the content of the messages that haven't been fetched yet.
        """
        from mail.models import Mailbox
        missing = self.find_missing()
        if not missing:
            return

        mailboxes = Mailbox.objects.filter(id__in=missing.keys())
        connection = mailboxes[0].imap.get_connection()
        for mailbox in mailboxes:
            response = mailbox.fetch_messages(missing[mailbox.id], connection)
            for msg in self.messages:
                if mailbox.id in msg.mailboxes:
                    uid = msg.get_uid(mailbox.id)
                    if uid in response:
                        msg.parse(response[uid]['RFC822'])
        self.save(safe=True)

    def mark_as_read(self):
        from mail.models import Mailbox
        to_mark = {}
        for msg in self.messages:
            if msg.read:
                continue
            msg.read = True
            for mbox_id, uid in msg.uids:
                if mbox_id in to_mark:
                    to_mark[mbox_id].append(uid)
                else:
                    to_mark[mbox_id] = [uid]
        if not to_mark:
            return

        mailboxes = Mailbox.objects.filter(id__in=to_mark.keys())
        connection = mailboxes[0].imap.get_connection()
        for mailbox in mailboxes:
            uids = ','.join(map(str, to_mark[mailbox.id]))
            connection.select_folder(mailbox.name)
            connection.add_flags(uids, imapclient.SEEN)
            connection.close_folder()
        connection.logout()
        self.save(safe=True)

    def mark_as_unread(self):
        from mail.models import Mailbox
        to_mark = {}
        for msg in self.messages:
            for mbox_id, uid in msg.uids:
                if mbox_id in to_mark:
                    to_mark[mbox_id].append(uid)
                else:
                    to_mark[mbox_id] = [uid]

        mailboxes = Mailbox.objects.filter(id__in=to_mark.keys())
        connection = mailboxes[0].imap.get_connection()
        for mailbox in mailboxes:
            uids = ','.join(map(str, to_mark[mailbox.id]))
            connection.select_folder(mailbox.name)
            connection.remove_flags(uids, imapclient.SEEN)
            connection.close_folder()

        for mailbox in mailboxes:
            mailbox.update_messages(connection)
        connection.logout()

    def move_to(self, destination):
        from mail.models import Mailbox, NORMAL, INBOX, SPAM, TRASH
        to_move = {}
        to_delete = {}
        for msg in self.messages:
            mbox_id, uid = msg.uids[0]
            if mbox_id in to_move:
                to_move[mbox_id].append(uid)
            else:
                to_move[mbox_id] = [uid]

            for mbox_id, uid in msg.uids[1:]:
                if mbox_id in to_delete:
                    to_delete[mbox_id].append(uid)
                else:
                    to_delete[mbox_id] = [uid]
        mailboxes = Mailbox.objects.filter(id__in=to_move.keys())
        # Don't delete messages in OUTBOX, DRAFTS, QUEUE, OTHER...
        mailboxes = mailboxes.filter(folder_type__in=[NORMAL, INBOX,
                                                      SPAM, TRASH])
        connection = mailboxes[0].imap.get_connection()
        for mailbox in mailboxes:
            uids = ','.join(map(str, to_move[mailbox.id]))
            connection.select_folder(mailbox.name)
            connection.copy(uids, destination)
            connection.add_flags(uids, imapclient.DELETED)
            connection.expunge()
            connection.close_folder()

        mailboxes = Mailbox.objects.filter(id__in=to_delete.keys())
        for mailbox in mailboxes:
            uids = ','.join(map(str, to_delete[mailbox.id]))
            connection.select_folder(mailbox.name)
            connection.add_flags(uids, imapclient.DELETED)
            connection.expunge()
            connection.close_folder()

        mailboxes = Mailbox.objects.filter(id__in=to_delete.keys()+to_move.keys())
        for mailbox in mailboxes:
            mailbox.update_messages(connection)
        connection.logout()

    def delete_from_imap(self):
        from mail.models import Mailbox
        to_delete = {}
        for msg in self.messages:
            for mbox_id, uid in msg.uids:
                if mbox_id in to_delete:
                    to_delete[mbox_id].append(uid)
                else:
                    to_delete[mbox_id] = [uid]

        mailboxes = Mailbox.objects.filter(id__in=to_delete.keys())
        connection = mailboxes[0].imap.get_connection()
        for mailbox in mailboxes:
            uids = ','.join(map(str, to_delete[mailbox.id]))
            connection.select_folder(mailbox.name)
            connection.add_flags(uids, imapclient.DELETED)
            connection.expunge()
            connection.close_folder()

        for mailbox in mailboxes:
            mailbox.update_messages(connection)
        connection.logout()
