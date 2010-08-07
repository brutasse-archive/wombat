import imapclient

from django import forms
from django.utils.translation import ugettext as _


from users.models import Account, Profile, IMAP, SMTP


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
            raise forms.ValidationError(_('An error has been encountered whi'
                                          'le checking your credentials. Ple'
                                          'ase double check and try again'))
        m.logout()
        return self.cleaned_data


class SMTPForm(forms.ModelForm):
    class Meta:
        model = SMTP
        exclude = ('healthy',)
