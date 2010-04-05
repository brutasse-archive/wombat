# -*- coding: utf-8 -*-

from django import forms
from django.utils.translation import ugettext_lazy as _

from mail import constants


class MailForm(forms.Form):
    from_addr = forms.ChoiceField(label=u'From', choices=[])
    to_addrs = forms.CharField(label=u'To', max_length=75)
#    cc_addrs = forms.CharField(label=u'Cc', max_length=75)
#    bcc_addrs = forms.CharField(label=u'Bcc', max_length=75)
    subject = forms.CharField(max_length=100)
    content = forms.CharField(widget=forms.widgets.Textarea())

    def __init__(self, user):
        super(MailForm, self).__init__()
        self.fields['from_addr'].choices = self._get_addrs(user)


    def _get_addrs(self, user):
        accounts = user.get_profile().accounts.all()
        for a in accounts:
            yield ('%s' % a.email, '%s <%s>' % (user.get_full_name(), a.email))


class ActionForm(forms.Form):
    action = forms.CharField(widget=forms.widgets.HiddenInput())

    def __init__(self, action, **kwargs):
        super(ActionForm, self).__init__(**kwargs)
        self.fields['action'].initial = action


class MoveForm(ActionForm):
    destination = forms.TypedChoiceField(coerce=lambda x: int(x))

    def __init__(self, account, **kwargs):
        if 'exclude' in kwargs:
            exclude = kwargs['exclude']
            del kwargs['exclude']
        else:
            exclude = None
        super(MoveForm, self).__init__('move', **kwargs)
        self.fields['destination'].choices = self._get_dirs(account, exclude)

    def _get_dirs(self, account, exclude):
        yield ('', _('Move to...'))
        for directory in account.directories.filter(no_select=False,
                folder_type=constants.NORMAL).order_by('name'):
            if exclude is not None and directory == exclude:
                continue
            yield ('%s' % directory.id, u'%s' % directory)
