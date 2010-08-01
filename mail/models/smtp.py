from django.db import models
from django.utils.translation import ugettext_lazy as _


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
        app_label = 'mail'
