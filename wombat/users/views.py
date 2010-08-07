# -*- coding: utf-8 -*-

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.core.urlresolvers import reverse
from django.db import transaction
from django.shortcuts import redirect, get_object_or_404
from django.utils.translation import ugettext as _

from shortcuts import render
from users.forms import AccountForm, ProfileForm, IMAPForm, SMTPForm
from users.models import Account


def login(request, *a, **kw):
    """
    If the user is already logged in, we redirect him to his inbox. If not,
    falling back to contrib.auth's built-in login view..
    """

    if request.user.is_authenticated():
        return redirect(reverse('default_inbox'))

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
            messages.success(request, _('Your settings have been updated'))
            return redirect(reverse('default_inbox'))
        else:
            # TODO: handle correctly the error and translate the message
            err = "Incorrect config..."
    else:
        err = ''
        form = ProfileForm(instance=profile)

    context = {'user': request.user, 'form': form,}
    return render(request, 'settings.html', context)


@login_required
def accounts(request):
    accounts = request.user.get_profile().accounts.all()
    return render(request, 'users/accounts.html', {'accounts': accounts})


@login_required
@transaction.commit_on_success
def del_account(request, id):
    a = get_object_or_404(Account, id=id)
    a.delete()
    return redirect(reverse('accounts'))


@login_required
@transaction.commit_on_success
def add_account(request):
    if request.method == 'POST':
        account_form = AccountForm(data=request.POST)
        smtp_form = SMTPForm(data=request.POST, prefix='smtp')
        imap_form = IMAPForm(data=request.POST, prefix='imap')
        if all([form.is_valid() for form in (account_form,
                                             smtp_form,
                                             imap_form)]):
            # Create an Account, attach it an IMAP and an SMTP instance.
            account = account_form.save(commit=False)
            account.profile = request.user.get_profile()
            account.imap = imap_form.save()
            account.smtp = smtp_form.save()
            account.save()
            messages.success(request, _('Your account has been successfully '
                                       'created'))
            return redirect(reverse('edit_account', args=[account.id]))
    else:
        account_form = AccountForm()
        smtp_form = SMTPForm(prefix='smtp')
        imap_form = IMAPForm(prefix='imap')
    context = {
        'account': account_form,
        'imap': imap_form,
        'smtp': smtp_form
    }
    return render(request, 'users/add_account.html', context)


@login_required
@transaction.commit_on_success
def edit_account(request, id):
    account = get_object_or_404(Account, id=id)

    if request.method == 'POST':
        account_form = AccountForm(data=request.POST, instance=account)
        smtp_form = SMTPForm(data=request.POST, prefix='smtp',
                             instance=account.smtp)
        imap_form = IMAPForm(data=request.POST, prefix='imap',
                             instance=account.imap)
        if all([form.is_valid() for form in (account_form, smtp_form,
                                             imap_form)]):
            account_form.save()
            imap_form.save()
            smtp_form.save()
            messages.success(request, _('Your account have been successfully'
                                        'updated.'))
            return redirect(reverse('accounts'))
    else:
        account_form = AccountForm(instance=account)
        smtp_form = SMTPForm(prefix='smtp', instance=account.smtp)
        imap_form = IMAPForm(prefix='imap', instance=account.imap)

    context = {
        'account': account,
        'account_form': account_form,
        'imap': imap_form,
        'smtp': smtp_form
    }
    return render(request, 'users/edit_account.html', context)
