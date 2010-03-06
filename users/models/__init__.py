# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from users.models.imap import IMAP, Directory

# It's a package so we have to manually add the models that aren't here
__all__ = ['IMAP', 'Directory']


class Profile(models.Model):
    """
    All the information needed to (not so) extensively configure this user's
    wombat account
    """
    user = models.OneToOneField(User, verbose_name=_('User'))
    language = models.CharField(_('Language'), max_length=5,
                                choices=settings.LANGUAGES)
    page_size = models.PositiveIntegerField(_('Page size'), default=50,
                                            choices=((0, 50), (1, 100)))
    signature = models.TextField(_('Signature'), max_length=200, blank=True)

    def __unicode__(self):
        return u'%s\'s profile' % self.user


def user_post_save(sender, instance, **kwargs):
    """
    Makes the ORM create a profile each time an user is createdi
    (or updated, if the user profile lost), including 'admin' user:
        http://www.djangosnippets.org/snippets/500/
    """
    profile, new = Profile.objects.get_or_create(user=instance)

models.signals.post_save.connect(user_post_save, sender=User)


class SMTP(models.Model):
    """
    All the needed information to connect to a SMTP server and send emails.
    """
    server = models.CharField(_('Server'), max_length=255)
    port = models.PositiveIntegerField(_('Port'), default=25,
                                       help_text=_("(465 with SSL)"))
    username = models.CharField(_('Username'), max_length=75)
    password = models.CharField(_('Password'), max_length=75)

    # Are we actually able to connect to this server?
    # There should be some check, try to connect to the server when the
    # configuration is altered.
    healthy = models.BooleanField(_('Healthy'), default=False)

    def __unicode__(self):
        return u'%s' % self.server


class Account(models.Model):
    """
    A wombat user can have several accounts, whose information is gathered here
    """
    # In case we want to give the account a name...
    name = models.CharField(_('Name'), max_length=255, blank=True, default='')

    profile = models.ForeignKey(Profile, verbose_name=_('Profile'),
                                         related_name='accounts')
    smtp = models.OneToOneField(SMTP, verbose_name=_('SMTP'))
    imap = models.OneToOneField(IMAP, verbose_name=_('IMAP'))

    # Make sure there's actually only one default account per user when
    # creating accounts
    default = models.BooleanField(_('Default account'), default=True)

    def __unicode__(self):
        if self.default:
            attr = 'default '
        else:
            attr = ''
        return u'%s\'s %saccount' % (self.profile.user, attr)
