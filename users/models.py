from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.ForeignKey(User, unique=True)

    def __unicode__(self):
        return u'%s\'s profile' % self.user
