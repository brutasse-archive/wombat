# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required

from shortcuts import render
from mail.models import MailForm
from users.models import Account


@login_required
def inbox(request):
    try:
        imap = request.user.get_profile().accounts.get(default=True).imap
        inbox = imap.directories.get(name='INBOX')
        dir_list = imap.directories.all()

        inbox_counts = inbox.message_counts()
        messages = inbox.message_list(number_of_messages=inbox_counts['total'])

        context = {
                'user': request.user,
                'directories': dir_list,
                'counts': inbox_counts,
                'messages': messages,
        }
    except Account.DoesNotExist:
        context = {'user': request.user}
    return render(request, 'mail.html', context)

@login_required
def compose(request):
    err = ''
    form = MailForm(request.user)
    return render(request, 'compose.html', {
        'user': request.user, 'form': form, 'err_msg': err,
    })

