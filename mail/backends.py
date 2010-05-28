# From http://www.djangosnippets.org/snippets/74/#c195
from django.contrib.auth.backends import ModelBackend
from django.forms.fields import email_re
from django.contrib.auth.models import User

class EmailAuthBackend(ModelBackend):
    def authenticate(self, username=None, password=None):
        if email_re.search(username):
            try:
                user = User.objects.get(email=username)
                if user.check_password(password):
                    return user
            except User.DoesNotExist:
                return None
        return None
