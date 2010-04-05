# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, redirect

from shortcuts import render
from decorators import account_required
from utils import safe_cache_key

from mail import constants
from mail.forms import MailForm
from users.models import Account, Directory, IMAP


@login_required
@account_required
def inbox(request, account_slug=None):
    accounts = request.user.get_profile().accounts.all()
    if account_slug is None:
        account = accounts[0]
    else:
        account = accounts.get(slug=account_slug)
    inbox = account.imap.directories.get(folder_type=constants.INBOX)
    return directory(request, account.slug, inbox.id)


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
def directory(request, account_slug, mbox_id, page=1):
    # Filter with user profile to be sure you are looking at your mails !
    directory = request.user.get_profile().get_directory(mbox_id)
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
def message(request, account_slug, mbox_id, uid):
    directory = request.user.get_profile().get_directory(mbox_id)

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


@login_required
@account_required
def check_mail(request, account_slug):
    imap = get_object_or_404(IMAP, account__slug=account_slug,
                             account__profile=request.user.get_profile())
    m = imap.get_connection()
    for directory in imap.directories.all():
        directory.message_counts(connection=m)
    m.logout()

    # TODO make sure the 'from' field is safe
    return redirect(request.GET.get('from', reverse('default_inbox')))
