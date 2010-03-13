from django.conf.urls.defaults import *

urlpatterns = patterns('mail.views',
    url(r'^$', 'inbox', name='default_inbox'),
    url(r'^(?P<id>\d+)/$', 'inbox', name='inbox'),
    url(r'^compose/$', 'compose', name='compose'),

    # The order matters here
    url(r'^(?P<id>\d+)/(?P<uid>\d+)/$', 'message', name='message'),
    url(r'^(?P<id>\d+)/$', 'directory', name='directory'),
)
