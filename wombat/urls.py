# -*- coding: utf-8 -*-

from django.conf import settings
from django.conf.urls.defaults import *
from django.contrib import admin

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^$', 'users.views.login',
        {'template_name': 'login.html'}, name='login'),

    # Enabling the admin
    url(r'^admin/', include(admin.site.urls)),

    # Users: wombat settings and preference, accounts settings
    url(r'^user/', include('users.urls')),

    # Mail: do whatever with emails: send, read, search, sort...
    url(r'^mail/', include('mail.urls')),
)

if settings.DEBUG:
    urlpatterns += patterns('django.views.static',
            (r'^static/(?P<path>.*)', 'serve',
                {'document_root': settings.MEDIA_ROOT}),
    )
