from django.conf.urls.defaults import *

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    # (r'^wombat/', include('wombat.foo.urls')),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs'
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^admin/(.*)', admin.site.root),
)

from django.conf import settings
if settings.DEBUG:
    urlpatterns += patterns('django.views.static',
            (r'^media/(?P<path>.*)', 'serve',
                {'document_root': settings.MEDIA_ROOT}),
    )
