# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.core.cache import cache

from shortcuts import render
from decorators import account_required
from utils import safe_cache_key

from mail.models import MailForm
from users.models import Account, Directory


@login_required
@account_required
def inbox(request):
    return directory(request, 'INBOX')

@login_required
def compose(request):
    err = ''
    form = MailForm(request.user)
    return render(request, 'compose.html', {
        'user': request.user, 'form': form, 'err_msg': err,
    })

@login_required
@account_required
def directory(request, directory, page=1):
    dir_list = request.user.get_profile().accounts.get(
            default=True).imap.directories.all()

    directory = get_object_or_404(dir_list, name=directory)
    number_of_messages = min(directory.total, 50)

    # Fetching a message list makes a call to the IMAP server. Trying to fetch
    # from the cache before, it's much faster...
    # Cache key: list-bob@example.comINBOX0
    cache_key = safe_cache_key('list-%s%s%s' % (directory.mailbox.username,
                                           directory.name,
                                           page))
    messages = cache.get(cache_key, None)

    if messages is None:
        messages = directory.message_list(number_of_messages=number_of_messages)
        if messages is not None:
            cache.set(cache_key, messages)

    context = {
            'user': request.user,
            'directory': directory,
            'directories': dir_list,
            'messages': messages,
    }
    return render(request, 'mail.html', context)

@login_required
def message(request, directory, uid):
    uid = int(uid)
    dir_list = request.user.get_profile().accounts.get(
            default=True).imap.directories.all()

    directory = get_object_or_404(dir_list, name=directory)

    # Cache key: message-bob@example.comINBOX1234
    cache_key = safe_cache_key('message-%s%s%s' % (directory.mailbox.username,
                                                   directory.name,
                                                   uid))
    message = cache.get(cache_key, None)
    if message is None:
        message = directory.get_message(uid)
        if message is not None:
            cache.set(cache_key, message)

    context = {
            'user': request.user,
            'directory': directory,
            'directories': dir_list,
            'message': message,
    }
    return render(request, 'message.html', context)
