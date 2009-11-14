from django import forms

from users.models import Profile, IMAP, SMTP

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        exclude = ['user',]

class IMAPForm(forms.ModelForm):
    class Meta:
        model = IMAP
        exclude = ['healthy',]

class SMTPForm(forms.ModelForm):
    class Meta:
        model = SMTP
        exclude = ['healthy',]
