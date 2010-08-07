import imapclient
import smtplib

from django import forms
from django.utils.translation import ugettext as _

from users.models import Account, Profile, IMAP, SMTP

CREDENTIALS_ERROR = ('An error has been encountered while checking your '
                     'credentials. Please double check and try again.')

class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ('name', 'email')


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        exclude = ('user',)


class IMAPForm(forms.ModelForm):
    class Meta:
        model = IMAP
        exclude = ('healthy',)

    def clean(self):
        data = self.cleaned_data
        ssl = data['port'] == 993
        m = imapclient.IMAPClient(data['server'], port=data['port'], ssl=ssl)
        try:
            m.login(data['username'], data['password'])
        except imapclient.IMAPClient.Error:
            raise forms.ValidationError(_(CREDENTIALS_ERROR))
        m.logout()
        return self.cleaned_data


class SMTPForm(forms.ModelForm):
    class Meta:
        model = SMTP
        exclude = ('healthy',)

    def clean(self):
        data = self.cleaned_data
        ssl = data['port'] == 465
        smtp_class = smtplib.SMTP
        if ssl:
            smtp_class = smtplib.SMTP_SSL
        server = smtp_class(data['server'], data['port'])
        try:
            server.login(data['username'], data['password'])
        except smtplib.SMTPException:
            raise forms.ValidationError(_(CREDENTIALS_ERROR))
        server.quit()
        return self.cleaned_data
