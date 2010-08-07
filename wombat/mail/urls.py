from django.conf.urls.defaults import *

account = '(?P<account_slug>[\w-]+)'
mbox = '(?P<mbox_id>\d+)'
msg = '(?P<uid>[a-f0-9]{24})'

urlpatterns = patterns('mail.views',
    url(r'^$', 'inbox', name='inbox'),
    url(r'^(?P<page>\d+)/$', 'inbox', name='inbox'),
    url(r'^check/$', 'check_mail', name='check_mail'),
    url(r'^check/inboxes/$', 'check_directory', name='check_directory'),
    url(r'^compose/$', 'compose', name='compose'),
    url(r'^%(account)s/$' % locals(), 'inbox', name='account_inbox'),

    url(r'^%(account)s/%(mbox)s/$' % locals(), 'directory', name='directory'),
    url(r'^%(account)s/%(mbox)s/(?P<page>\d+)/$' % locals(),
        'directory', name='directory'),

    url(r'^%(account)s/%(mbox)s/check/$' % locals(),
        'check_directory', name='check_directory'),

    url(r'^%(account)s/%(mbox)s/%(msg)s/$' % locals(),
        'message', name='message'),
)
