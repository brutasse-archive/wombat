from django import forms

from users.models import Account, Profile, IMAP, SMTP


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ('name',)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        exclude = ('user',)


class IMAPForm(forms.ModelForm):
    class Meta:
        model = IMAP
        exclude = ('healthy',)


class SMTPForm(forms.ModelForm):
    class Meta:
        model = SMTP
        exclude = ('healthy',)
