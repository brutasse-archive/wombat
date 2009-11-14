from django.conf.urls.defaults import *

urlpatterns = patterns('users.views',
    url(r'^logout/$', 'logout', name='logout'),
    url(r'^settings/$', 'settings', name='settings'),
    url(r'^accounts/$', 'accounts', name='accounts'),
    url(r'^accounts/add/$', 'add_account', name='add_account'),
)
