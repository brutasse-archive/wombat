# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required

from shortcuts import render
from decorators import account_required

from mail.forms import MailForm
from users.models import Account, Directory


@login_required
@account_required
def inbox(request, id=None):
    if id is None:
        id = request.user.get_profile().accounts.all()[0].id
    return directory(request, id, 'INBOX')


@login_required
@account_required
def compose(request):
    err = ''
    form = MailForm(request.user)
    return render(request, 'compose.html', {'form': form, 'err_msg': err})


@login_required
@account_required
def directory(request, id, page=1):
    # Filter with user profile to be sure you are looking at your mails !
    # TODO Replace account's id with something more fashion
    dir = request.user.get_profile().get_directory(id)
    context = {'directory': dir, 'messages': dir.get_messages(page)}
    return render(request, 'mail.html', context)


@login_required
@account_required
def message(request, id, uid):
    dir = request.user.get_profile().get_directory(id)
    context = {'directory': dir, 'message': dir.get_message(uid)}
    return render(request, 'message.html', context)
