# -*- coding: utf-8 -*-

from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from wombat.shortcuts import render
from wombat.users.models import ProfileForm


def login(request):
    """
        Login method from The Django Book:
            http://www.djangobook.com/en/2.0/chapter14/
    """
    if request.method == 'POST':
        username = request.POST.get('email', '')
        password = request.POST.get('password', '')
        user = auth.authenticate(username=username, password=password)
        if user is not None and user.is_active:
            # Correct password, and the user is marked "active"
            auth.login(request, user)
            return redirect('/mail/')
        else:
            # TODO: Add translation string.
            err = "The username or password you entered is incorrect."
    else:
        err = ''
    return render(request, 'login.html', {'err_msg': err})


def logout(request):
    """
        Return to the index after a logout, we don't care about a
        "Thanks for your visit" page.
    """
    auth.logout(request)
    return redirect('/')


@login_required
def inbox(request):
    return render(request, 'mail.html', {'user': request.user})


@login_required
def settings(request):
    profile = request.user.get_profile()
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            # TODO: Display a javascript "Modification saved"
            # For the moment, redirect to the inbox
            return redirect('/mail/')
        else:
            # TODO: handle correctly the error and translate the message
            err = "Incorrect config..."
    else:
        err = ''
        form = ProfileForm(instance=profile)
    return render(request, 'settings.html', {
        'user': request.user, 'form': form, 'err_msg': err,
    })
