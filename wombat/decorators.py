from django.shortcuts import redirect
from django.core.urlresolvers import reverse

from users.models import Account

from functools import wraps # Python >= 2.5 needed


def account_required(function=None):
    """
    Checks that the user has a correctly configured account and redirects him
    to the settings page if necessary.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            accounts = request.user.get_profile().accounts.count()
            if accounts > 0:
                return view_func(request, *args, **kwargs)
            return redirect(reverse('add_account'))
        return wraps(view_func)(_wrapped_view)
    return decorator(function)
