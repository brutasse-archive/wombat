# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from django.db import transaction

from shortcuts import render
from users.forms import ProfileForm, IMAPForm, SMTPForm
from users.models import Account, SMTP, IMAP


def login(request, *a, **kw):
    """
    If the user is already logged in, we redirect him to his inbox. If not,
    falling back to contrib.auth's built-in login view..
    """

    if request.user.is_authenticated():
        return redirect(reverse('inbox'))

    return auth_views.login(request, *a, **kw)


def logout(request):
    """
        Return to the index after a logout, we don't care about a
        "Thanks for your visit" page.
    """
    from django.contrib.auth import logout
    logout(request)
    return redirect('/')


@login_required
def settings(request):
    profile = request.user.get_profile()
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            # TODO: Display a javascript "Modification saved"
            # For the moment, redirect to the inbox
            return redirect(reverse('inbox'))
        else:
            # TODO: handle correctly the error and translate the message
            err = "Incorrect config..."
    else:
        err = ''
        form = ProfileForm(instance=profile)
    return render(request, 'settings.html', {
        'user': request.user, 'form': form, 'err_msg': err,
    })

@login_required
def accounts(request):
    accounts = request.user.get_profile().accounts.all()
    return render(request, 'users/accounts.html', {'accounts': accounts})

@login_required
@transaction.commit_on_success
def add_account(request):
    if request.method == 'POST':
        smtp_form = SMTPForm(data=request.POST, prefix='smtp')
        imap_form = IMAPForm(data=request.POST, prefix='imap')
        if all([form.is_valid() for form in (smtp_form, imap_form)]):
            # Create an Account, attach it an IMAP and an SMTP instance.
            account = Account(profile=request.user.get_profile())

            imap = IMAP(**imap_form.cleaned_data)
            smtp = SMTP(**smtp_form.cleaned_data)

            success = imap.check_credentials()
            if success:
                imap.save()
                smtp.save()
                account.imap = imap
                account.smtp = smtp
                account.save()


            context = {'imap': imap_form, 'smtp': smtp_form,
                       'success': success, 'submitted': True}

    else:
        imap_form = IMAPForm(prefix='imap')
        smtp_form = SMTPForm(prefix='smtp')
        context = {'imap': imap_form, 'smtp': smtp_form}

    return render(request, 'users/add_account.html', context)
