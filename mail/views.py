# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from django.core.cache import cache

from shortcuts import render
from decorators import account_required
from utils import safe_cache_key

from mail.models import MailForm
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
    return render(request, 'compose.html', {
        'user': request.user, 'form': form, 'err_msg': err,
    })


@login_required
@account_required
def directory(request, id, page=1):
    # Filter with user profile to be sure you are looking at your mails !
    # TODO Replace account's id with something more fashion
    directory = request.user.get_profile().get_directory(id)
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
            'messages': messages,
    }
    return render(request, 'mail.html', context)


@login_required
@account_required
def message(request, id, uid):
    directory = request.user.get_profile().get_directory(id)

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
            'message': message,
    }
    return render(request, 'message.html', context)
