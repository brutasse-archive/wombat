# -*- coding: utf-8 -*-

from django.conf.urls.defaults import *
#from django.views.generic.simple import direct_to_template

from django.contrib import admin
admin.autodiscover()

from wombat.users.views import login, inbox, settings

urlpatterns = patterns('',
    (r'^$', login),
    (r'^logout/', login),
    (r'^mail/', inbox),
    (r'^settings/', settings),
    (r'^admin/(.*)', admin.site.root),
)

from django.conf import settings
if settings.DEBUG:
    urlpatterns += patterns('django.views.static',
            (r'^media/(?P<path>.*)', 'serve',
                {'document_root': settings.MEDIA_ROOT}),
    )
