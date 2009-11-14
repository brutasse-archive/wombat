from django.conf.urls.defaults import *

urlpatterns = patterns('mail.views',
    url(r'^$', 'inbox', name='inbox'),
    url(r'^compose/$', 'compose', name='compose'),
)
