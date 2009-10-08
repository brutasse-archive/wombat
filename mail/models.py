# -*- coding: utf-8 -*-

from django.db import models
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
        self.fields['from_addr'].choices = [('', '%s <%s>' % (user, user.email))]

