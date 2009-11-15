from django.conf.urls.defaults import *

urlpatterns = patterns('mail.views',
    url(r'^$', 'inbox', name='inbox'),
    url(r'^compose/$', 'compose', name='compose'),

    # The order matters here
    url(r'^(?P<directory>.*)/(?P<uid>\d+)/$', 'message', name='message'),
    url(r'^(?P<directory>.*)/$', 'directory', name='directory'),
)
