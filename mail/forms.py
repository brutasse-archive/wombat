# -*- coding: utf-8 -*-

from django import forms


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
