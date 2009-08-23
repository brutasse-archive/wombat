# -*- coding: utf-8 -*-

from django.contrib import auth
from django.shortcuts import render_to_response
from django.http import HttpResponseRedirect
from django.contrib.auth.decorators import login_required


def login(request):
    """
        Login method from The Django Book:
            http://www.djangobook.com/en/2.0/chapter14/
    """
    if request.method == "POST":
        username = request.POST.get('email', '')
        password = request.POST.get('password', '')
        user = auth.authenticate(username=username, password=password)
        if user is not None and user.is_active:
            # Correct password, and the user is marked "active"
            auth.login(request, user)
            return HttpResponseRedirect('/mail/')
        else:
            # TODO: Add translation string.
            err = "The username or password you entered is incorrect."
    else:
        err = ''
    return render_to_response('login.html', {'err_msg': err})


def logout(request):
    """
        Return to the index after a logout, we don't care about a
        "Thanks for your visit" page.
    """
    auth.logout(request)
    return HttpResponseRedirect("/")


@login_required
def inbox(request):
    return render_to_response('mail.html', {'user': request.user})
