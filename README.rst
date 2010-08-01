Wombat
======

Wombat is a django-powered web-based email client.

Download
--------

::
    git clone git://gitorious.org/wombat/wombat.git

Development
-----------

Under the ``wombat/wombat`` directory, create a minmal ``settings.py`` file::

    from default_settings import *

``default_settings`` are sane defaults for development. You can override
whatever you want. For example, to add the debug toolbar::

    INSTALLED_APPS = INSTALLED_APPS + (
    'debug_toolbar',
    )   

    MIDDLEWARE_CLASSES = MIDDLEWARE_CLASSES + (
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )

    DEBUG_TOOLBAR_CONFIG = {
        'INTERCEPT_REDIRECTS': False,
    }

    INTERNAL_IPS = ('127.0.0.1',)