# -*- coding: utf-8 -*-

from django.contrib.auth.decorators import login_required
from wombat.shortcuts import render
from wombat.mail.models import MailForm


@login_required
def compose(request):
    err = ''
    form = MailForm(request.user)
    return render(request, 'compose.html', {
        'user': request.user, 'form': form, 'err_msg': err,
    })

