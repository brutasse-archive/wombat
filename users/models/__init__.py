# -*- coding: utf-8 -*-

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _

from users.models.imap import IMAP, Directory
from mail import constants

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

    def _get_emails(self):
        return [a.email for a in self.accounts.all()]

    emails = property(_get_emails)

    def get_directory(self, id):
        """ Return user's IMAP directory matching the id """
        dir = get_object_or_404(Directory, id=id)
        if dir.mailbox.account in self.accounts.all():
            return dir
        else:
            raise Http404(_("Directory not found"))


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
        return u'%s smtp' % self.account

    class Meta:
        verbose_name = _('SMTP config')
        verbose_name_plural = _('SMTP configs')
        app_label = 'users'


class Account(models.Model):
    """
    A wombat user can have several accounts, whose information is gathered here
    """
    name = models.CharField(_('Name'), max_length=255, default=_('Default'))
    slug = models.SlugField(_('Slug'))
    email = models.EmailField(_('Mail addresse'), default='john.bob@wmail.org')

    profile = models.ForeignKey(Profile, verbose_name=_('Profile'),
                                         related_name='accounts')
    smtp = models.OneToOneField(SMTP, verbose_name=_('SMTP'))
    imap = models.OneToOneField(IMAP, verbose_name=_('IMAP'))

    def __unicode__(self):
        return u'%s\'s %s' % (self.profile.user, self.name)

    class Meta:
        unique_together = ('profile', 'slug')

    def delete(self):
        self.smtp.delete()
        self.imap.delete()
        super(Account, self).delete()

    def common_directories(self):
        """Returns all the common directories: inbox, outbox, etc."""
        if self.imap:
            dirs = self.imap.directories.exclude(folder_type=constants.NORMAL).exclude(name__iexact='[gmail]')
            return dirs.order_by('folder_type')
        return []

    def custom_directories(self):
        """ Return the list of Directories. """
        if self.imap:
            return self.imap.directories.filter(folder_type=constants.NORMAL, parent__isnull=True)
        return []


def account_pre_save(sender, instance, **kwargs):
    # TODO make sure the slug is unique and doesn't conflict with URLs
    instance.slug = slugify(instance.name)

models.signals.pre_save.connect(account_pre_save, sender=Account)
