# -*- coding: utf-8 -*-

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext as _

from shortcuts import render
from decorators import account_required

from mail.models import IMAP, Mailbox, Thread, INBOX
from mail.forms import MailForm, ActionForm, MoveForm


@login_required
def inbox(request, account_slug=None, page=1):
    profile = request.user.get_profile()
    accounts = profile.accounts.all()
    if account_slug is not None:
        accounts = [accounts.get(slug=account_slug)]

    if not accounts:
        messages.info(request, _('You don\'t have any account yet, please '
                                 'fill in the form below'))
        return redirect(reverse('add_account'))

    begin = (page - 1) * 50
    end = begin + 50

    inboxes = Mailbox.objects.filter(imap__account__in=accounts,
                                     folder_type=INBOX).values_list('id',
                                                                    flat=True)
    threads = Thread.objects(mailboxes__in=inboxes)[begin:end]
    directory = profile.get_directory(inboxes[0])
    context = {
        'unified': True,
        'directory': directory,
        'threads': threads,
    }
    return render(request, 'mail.html', context)


@login_required
@account_required
def compose(request):
    err = ''
    form = MailForm(request.user)
    return render(request, 'compose.html', {'form': form, 'err_msg': err})


@login_required
@account_required
def directory(request, account_slug, mbox_id, page=1):
    mbox_id = int(mbox_id)
    begin = (page - 1) * 50
    end = begin + 50

    threads = Thread.objects(mailboxes=mbox_id)[begin:end]
    # Filter with user profile to be sure you are looking at your mails !
    # TODO Replace account's id with something more fashion
    directory = request.user.get_profile().get_directory(mbox_id)
    context = {
        'directory': directory,
        'threads': threads,
    }
    return render(request, 'mail.html', context)


@login_required
@account_required
def message(request, account_slug, mbox_id, uid):
    directory = request.user.get_profile().get_directory(mbox_id)

    if request.method == 'POST':
        action = request.POST.get('action', None)
        if action == 'unread':
            directory.unread_message(uid)

        if action == 'delete':
            directory.delete_message(uid)
            messages.succes(request,
                            'The conversation has been successfully deleted')

        if action == 'move':
            form = MoveForm(directory.imap, data=request.POST)
            if form.is_valid():
                dest = directory.imap.directories.get(pk=form.cleaned_data['destination'])
                directory.move_message(uid, dest.name)
                messages.success(request, 'The conversation has been successfully moved to "%s"' % dest.name)
            else:
                messages.error(request, 'Unable to move the conversation')
                pass

        return redirect(reverse('directory', args=[account_slug, mbox_id]))

    thread = Thread.objects(id=uid)[0]
    thread.fetch_missing()

    context = {
        'directory': directory,
        'thread': thread,
        'move_form': MoveForm(directory.imap, exclude=directory),
        'unread_form': ActionForm('unread'),
        'delete_form': ActionForm('delete'),
    }
    return render(request, 'message.html', context)


@login_required
@account_required
def check_mail(request, account_slug):
    imap = get_object_or_404(IMAP, account__slug=account_slug,
                             account__profile=request.user.get_profile())
    imap.check_mail()

    # TODO make sure the 'from' field is safe
    return redirect(request.GET.get('from', reverse('default_inbox')))


def check_directory(request, account_slug, mbox_id):
    mbox_id = int(mbox_id)
    imap = get_object_or_404(IMAP, account__slug=account_slug,
                             account__profile=request.user.get_profile())
    directory = imap.directories.get(pk=mbox_id)
    directory.update_messages()
    return redirect(reverse('directory', args=[account_slug, mbox_id]))
