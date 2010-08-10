# -*- coding: utf-8 -*-

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import Http404
from django.shortcuts import get_object_or_404, get_list_or_404, redirect
from django.utils.translation import ugettext as _

from shortcuts import render

from mail.models import IMAP, Mailbox, Thread, INBOX
from mail.forms import MailForm, ActionForm, MoveForm


@login_required
def inbox(request, account_slug=None, page=1):
    page = int(page)
    profile = request.user.get_profile()
    accounts = profile.accounts.all()
    if account_slug is not None:
        accounts = [accounts.get(slug=account_slug)]

    if not accounts:
        messages.info(request, _('You don\'t have any account yet, please '
                                 'fill in the form below'))
        return redirect(reverse('add_account'))

    inboxes = Mailbox.objects.filter(imap__account__in=accounts,
                                     folder_type=INBOX).values_list('id',
                                                                    flat=True)
    total = Thread.objects(mailboxes__in=inboxes).count()
    begin = (page - 1) * 50
    end = min(total, begin + 50)

    threads = Thread.objects(mailboxes__in=inboxes)[begin:end]
    directory = profile.get_directory(inboxes[0])
    context = {
        'unified': True,
        'directory': directory,
        'threads': threads,
        'begin': begin + 1,
        'end': end,
        'total': total,
    }
    if total > end:
        context['next_url'] = reverse('inbox', args=[page+1])
    if page > 1:
        context['previous_url'] = reverse('inbox', args=[page-1])
    return render(request, 'mail.html', context)


@login_required
def compose(request):
    form = MailForm(request.user)
    return render(request, 'compose.html', {'form': form})


@login_required
def directory(request, mbox_id, page=1):
    mbox_id = int(mbox_id)
    page = int(page)

    total = Thread.objects(mailboxes=mbox_id).count()
    begin = (page - 1) * 50
    end = min(total, begin + 50)

    threads = Thread.objects(mailboxes=mbox_id)[begin:end]
    # Filter with user profile to be sure you are looking at your mails !
    # TODO Replace account's id with something more fashion
    directory = request.user.get_profile().get_directory(mbox_id)
    context = {
        'directory': directory,
        'threads': threads,
        'begin': begin + 1,
        'end': end,
        'total': total,
    }
    if total > end:
        context['next_url'] = reverse('directory',
                                      args=[mbox_id, page+1])
    if page > 1:
        context['previous_url'] = reverse('directory',
                                          args=[mbox_id, page-1])
    return render(request, 'mail.html', context)


@login_required
def message(request, mbox_id, uid):
    profile = request.user.get_profile()
    mailbox = profile.get_directory(mbox_id)
    mbox_id = mailbox.id
    thread = Thread.objects.get(id=uid)
    if mbox_id not in thread.mailboxes:
        raise Http404

    if request.method == 'POST':
        mailboxes = Mailbox.objects.filter(imap=mailbox.imap)
        action = request.POST.get('action', None)
        if action == 'unread':
            thread.mark_as_unread()
            messages.success(request, _('The conversation has been marked as'
                                        ' new'))

        if action == 'delete':
            thread.delete_from_imap()
            messages.success(request, _('The conversation has been '
                                        'successfully deleted'))

        if action == 'move':
            form = MoveForm(mailbox.imap, data=request.POST)
            if form.is_valid():
                dest = mailboxes.get(pk=form.cleaned_data['destination'])
                thread.move_to(dest.name)
                messages.success(request, _('The conversation has been '
                                            'successfully moved to '
                                            '"%s"' % dest.name))
            else:
                messages.error(request, _('Unable to move the conversation'))
        return redirect(reverse('directory', args=[mbox_id]))

    thread.fetch_missing()
    context = {
        'directory': mailbox,
        'thread': thread,
        'move_form': MoveForm(mailbox.imap, exclude=directory),
        'unread_form': ActionForm('unread'),
        'delete_form': ActionForm('delete'),
    }
    response = render(request, 'message.html', context)
    if not thread.read:
        thread.mark_as_read()
    return response


@login_required
def check_mail(request):
    profile = request.user.get_profile()
    accounts = get_list_or_404(IMAP, account__profile=profile)

    for account in accounts:
        account.check_mail()
    # TODO make sure the 'from' field is safe
    return redirect(request.GET.get('from', reverse('inbox')))


@login_required
def check_directory(request, mbox_id=None):
    profile = request.user.get_profile()
    accounts = get_list_or_404(IMAP, account__profile=profile)

    if mbox_id is None:
        directories = Mailbox.objects.filter(imap__in=accounts,
                                             folder_type=INBOX)
        url = reverse('inbox')
    else:
        mbox_id = int(mbox_id)
        directories = Mailbox.objects.filter(imap__in=accounts, pk=mbox_id)
        url = reverse('directory', args=[mbox_id])

    for directory in directories:
        directory.update_messages()
    return redirect(url)
