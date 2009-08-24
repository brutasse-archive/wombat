# -*- coding: utf-8 -*-

from django.db import models
from django.forms import ModelForm
from django.contrib.auth.models import User

from django.conf import settings

class Profile(models.Model):
    user = models.ForeignKey(User, unique=True)
    language = models.CharField(max_length=5, choices=settings.LANGUAGES)
    page_size = models.PositiveIntegerField(default=50,
                                            choices=((0, 50), (1, 100)))
    signature = models.TextField(max_length=200, blank=True)

    def __unicode__(self):
        return u'%s\'s profile' % self.user


class ProfileForm(ModelForm):
    class Meta:
        model = Profile
        exclude = ['user']


def user_post_save(sender, instance, **kwargs):
    """
        Makes the ORM create a profile each time an user is createdi
        (or updated, if the user profile lost), including 'admin' user:
            http://www.djangosnippets.org/snippets/500/
    """
    profile, new = Profile.objects.get_or_create(user=instance)

models.signals.post_save.connect(user_post_save, sender=User)


class SMTP(models.Model):
    server = models.URLField()
    username = models.CharField(max_length=75)
    password = models.CharField(max_length=75)

    def __unicode__(self):
        return u'%s' % self.server


class IMAP(models.Model):
    server = models.URLField()
    username = models.CharField(max_length=75)
    password = models.CharField(max_length=75)

    def __unicode__(self):
        return u'%s' % self.server


class Account(models.Model):
    profile = models.ForeignKey(Profile, unique=True)
    smtp = models.ForeignKey(SMTP, unique=True)
    imap = models.ForeignKey(IMAP, unique=True)

    def __unicode__(self):
        return u'%s\'s default account' % self.profile.user
