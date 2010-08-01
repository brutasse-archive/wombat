from django.conf.urls.defaults import *

urlpatterns = patterns('users.views',
    url(r'^logout/$', 'logout', name='logout'),
    url(r'^settings/$', 'settings', name='settings'),
    url(r'^accounts/$', 'accounts', name='accounts'),
    url(r'^accounts/add/$', 'add_account', name='add_account'),
    url(r'^accounts/edit/(?P<id>\d+)/$', 'edit_account', name='edit_account'),
    url(r'^accounts/del/(?P<id>\d+)/$', 'del_account', name='del_account'),
)
