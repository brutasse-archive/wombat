Wombat
======

Wombat is a django-powered web-based email client.

Status
------

Wombat is under very early development, backwards-incompatible changes can be
made at any time and it won't change anytime soon.

Download
--------

::
    git clone git://gitorious.org/wombat/wombat.git
    cd wombat
    mkvirtualenv wombat
    easy_install pip
    pip install -r requirements.txt

Development
-----------

You need a SQL database and a MongoDB one.

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
