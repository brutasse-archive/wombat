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
    uid = IntField()
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
    mailbox = IntField()

    meta = {
        'indexes': ['uid', 'message_id', 'in_reply_to', 'date'],
        'ordering': ['date'],
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
        thread = Thread(date=self.date, mailboxes=[self.mailbox],
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

    def merge_with(self, other_thread):
        """
        Steal the messages stored in ``other_thread`` and delete it
        """
        if self.id == other_thread.id:
            # Nothing to merge with
            return
        for msg in other_thread.messages:
            self.add_message(msg, update=False)
        self.save(safe=True)
        other_thread.delete()

    def add_message(self, message, update=True):
        """
        Appends a message to the thread and updates relevant parameters
        """
        self.date = max(self.date, message.date)
        if not message.mailbox in self.mailboxes:
            self.mailboxes.append(message.mailbox)
        self.messages.append(message)
        if update:
            self.save(safe=True)

    @property
    def messages_count(self):
        return len(self.messages)

    def get_info(self):
        senders = set()
        subject = ''
        read = True
        date = self.date
        for m in self.messages:
            if m.date < date:
                date = m.date
                subject = m.subject

            if not m.read:
                read = False
            if not subject:
                subject = m.subject
            senders.add(m.fro)

        return {
            'read': read,
            'subject': subject,
            'senders': senders,
            'mailboxes': self.mailboxes,
            'date': self.date,
        }
