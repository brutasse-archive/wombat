from django.conf.urls.defaults import *

account = '(?P<account_slug>[\w-]+)'
mbox = '(?P<mbox_id>\d+)'
msg = '(?P<uid>\d+)'

urlpatterns = patterns('mail.views',
    url(r'^$', 'inbox', name='default_inbox'),
    url(r'^compose/$', 'compose', name='compose'),
    url(r'^%(account)s/$' % locals(), 'inbox', name='account_inbox'),
    url(r'^%(account)s/check/$' % locals(), 'check_mail', name='check_mail'),
    url(r'^%(account)s/%(mbox)s/$' % locals(), 'directory', name='directory'),
    url(r'^%(account)s/%(mbox)s/%(msg)s/$' % locals(),
        'message', name='message'),
)
