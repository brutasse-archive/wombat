from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import ugettext_lazy as _

import imaplib
import re
import os
import email.utils
import email.header
from email.parser import Parser

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
    server = models.CharField(_('IMAP Server'), max_length=255)

    # Port: 585 for IMAP4-SSL, 993 for IMAPS (Gmail default)
    port = models.PositiveIntegerField(_('IMAP Port'), default=993)
    username = models.CharField(_('Username or email'), max_length=255)

    # TODO: have a look at http://docs.python.org/library/hmac.html
    # We have to find a way to store passwords in an encrypted way, and having
    # the database stolen should not be compromising
    password = models.CharField(_('Password'), max_length=255)

    # A way to tell the user that his account is well configured or
    # something is wrong.
    healthy = models.BooleanField(_('Healthy account'), default=False)

    def __unicode__(self):
        return u'IMAP configuration for %s' % self.username

    class Meta:
        verbose_name = _('IMAP configuration')
        verbose_name_plural = _('IMAP configurations')
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
        except Exception as e:
            # There is no special exception in case of a failed login.
            # Catching the message instead.
            if not 'Invalid credentials' in str(e): # e.message is deprecated
                # There is maybe another exception...
                raise e
            else:
                self.healthy = False
        # That was it, closing the connection
        m.logout()
        return self.healthy


    def update_tree(self, update_counts=True, connection=None):
        """
        Updates the statuses of the directories, which are cached in the
        database.

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
        if status == 'OK':
            for d in directories:
                # d should look like:
                # (\HasChildren) "/" "Archives"
                # Or
                # (\HasNoChildren) "/" "Archives/Web"
                # Or even
                # (\Noselect \HasChildren) "/" "[Gmail]"
                # It's a string
                details = d.split('"')
                name = details[-2].decode('UTF-8')
                directory, created = Directory.objects.get_or_create(mailbox=self,
                                                            name=name)
                directory.has_children = 'HasChildren' in details[0]
                directory.no_select = 'Noselect' in details[0]
                directory.save()
                dirs.append(directory)

            # Deleting 'old' directories. If things have changed on the server
            # via another client for instance
            uptodate_dirs = [d.name for d in dirs]
            to_delete = self.directories.exclude(name__in=uptodate_dirs)
            to_delete.delete()

            if update_counts:
                # Update the directory counts
                for directory in dirs:
                    directory.message_counts(update=True, connection=m)

            # Returning the number of directories or None
            value = len(dirs)
        else:
            value = None

        if connection is None:
            m.logout()
        return value

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

    def __unicode__(self):
        return u'%s' % self.name

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
        status, response = m.status('"%s"' % self.name, statuses)
        if connection is None:
            m.logout() # KTHXBYE

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
        status, response = m.select(self.name)

        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        # Fetch the UIDs of the messages in this directory
        status, ids = m.search(None, 'ALL')

        if not status == 'OK':
            print 'Unexpected result: "%s"' % status
            return

        ids_list = ids[0].split()
        if not ids_list: # No message in this list
            if connection is None:
                m.close()
            return []

        number_of_messages = min(number_of_messages, len(ids_list))
        begin = - (number_of_messages + offset)
        end = - offset - 1
        fetch_range = '%s:%s' % (ids_list[begin], ids_list[end])

        # Fetching only the header since we're just displaying a list
        status, response = m.fetch(fetch_range, '(BODY[HEADER])')

        # We need the IMAP flags since we don't know which message has been
        # read from the SMTP headers.
        flag_status, flags = m.fetch(fetch_range, 'FLAGS')

        # We're done with the IMAP
        m.close()
        if connection is None:
            m.logout()

        if not status == 'OK' and flag_status == 'OK':
            print 'Fetching headers returned %s (message %s)' % (status,
                                                                 response)
            print 'Fetching flags returned %s (message %s)' % (flag_status,
                                                               flags)
            return

        # Build a dictionnary with message UIDs as keys and its flags as
        # values. Empty flag means unread. Otherwise it's 'Seen' or
        # whatever else.
        flag_re = r'^(\d+) \(FLAGS \(([^\)]*)\)\)$'
        flag_dict = {}
        for flag in flags:
            elements = re.search(flag_re, flag)
            flag_dict[elements.group(1)] = elements.group(2).replace('\\', '')

        # The list to fill with message info
        messages = []

        num_elements = len(response)
        body_re = r'^(\d+) \(BODY' # After that we don't care
        parser = Parser() # We have to parse the headers
        msgs = (2*i for i in range(num_elements/2)) # one message for 2 elements
        for index in msgs:
            header_data = response[index][1]
            message_id = re.search(body_re, response[index][0]).group(1)
            parsed_header = parser.parsestr(header_data)

            # To be extended just after
            message = {
                    'read': 'Seen' in flag_dict[message_id],
                    'uid': message_id,
            }

            # Here are the headers we're interested in:
            # * From, To, Date, Subject for displaying
            # * Message-ID and In-Reply-To for grouping messages by threads
            interesting_headers = ('From', 'To', 'Date', 'Subject',
                    'Message-ID', 'In-Reply-To')
            for part in parsed_header.walk():
                for key in interesting_headers:
                    if part.has_key(key):
                        message[key.lower()] = self._clean_header(part[key])
            messages.append(message)

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

        status, result = m.select(self.name)
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

        p = Parser()
        message = p.parsestr(raw_email)
        plain_text_content = ''
        header_dict = {}
        for part in message.walk():
            if part.get_content_type() == 'text/plain':
                for header in part.keys():
                    to_clean = part[header]
                    header_dict[header.lower()] = self._clean_header(to_clean)
                plain_text_content += part.get_payload(decode=1)

        return (plain_text_content, header_dict, raw_email)

    def _clean_header(self, header):
        """
        The headers returned by the IMAP erver are not necessarily
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
            assembled = '%s%s%s' % (assembled, separator, element[0])
        return assembled
