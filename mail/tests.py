from django.test import TestCase
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User

from users.models import Account, IMAP, SMTP

class MailTest(TestCase):
    def setUp(self):
        # Creating a user
        u = User.objects.create_user('testuser', 'test@example.com', 'pass')
        self.user = u
        # Logging him in
        self.client.login(username='testuser', password='pass')
        # Creating an account
        imap = IMAP(server='imap.gmail.com', username='test_user',
                    password='password', healthy=True)
        imap.save() # should update tree
        smtp = SMTP(server='smtp.gmail.com', username='test_user',
                    password='password', port=25, healthy=True)
        smtp.save()
        account = Account(name='Test', profile=u.get_profile(),
                          smtp=smtp, imap=imap)
        account.save()

    def test_inbox(self):
        """
        The inbox shows a list of 10 messages, 4 are unread.
        """
        url = reverse('inbox')
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)
        self.assertTrue('First crappy message' in response.content)

    def test_compose(self):
        """
        Sending a message
        """
        # FIXME: This doesn't do anything so we're just checking that the
        # view works.
        url = reverse('compose')
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)

    def test_message(self):
        """
        Reading a single message
        """
        url = reverse('message', args=['INBOX', 10])
        response = self.client.get(url)
        self.assertEquals(response.status_code, 200)
        self.assertTrue('Meaningless content' in response.content)
        self.assertTrue('back to <b>INBOX</b>' in response.content)
