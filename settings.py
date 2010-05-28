# -*- coding: utf-8 -*-
#
# Wombat default settings.py for Django 1.2
#
# DON'T EDIT THIS FILE! Please use local_setting.py instead.
# Look at the generated settings.py for an example. We keep
# this one as simple as possible.
#

import os.path

HERE = os.path.dirname(__file__)


DEBUG = True
TEMPLATE_DEBUG = DEBUG
IMAPLIB_DEBUG = DEBUG

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)
MANAGERS = ADMINS


DATABASES = {
    'default': { # Development SQLite
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(HERE, 'dev.db'),
    }
}


TIME_ZONE = 'Europe/Paris'
LANGUAGE_CODE = 'en-us'

USE_I18N = True
USE_L10N = True

MEDIA_ROOT = os.path.join(HERE, 'media')
MEDIA_URL = '/media/'
ADMIN_MEDIA_PREFIX = '/admin_media/'

SECRET_KEY = '2q(ac(%ae6ni8(v0+_&@9zkl5^a_76ozmg59kw%xst9c(c%o61'

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'urls'

TEMPLATE_DIRS = (
    os.path.join(HERE, 'templates'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.admin',
    'users',
    'mail',
)


LOGIN_URL = '/'
LOGIN_REDIRECT_URL = '/mail/'
AUTH_PROFILE_MODULE = 'users.Profile'


AUTHENTICATION_BACKENDS = (
    'mail.backends.EmailAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
)

# Dummy translation 'ugettext()' function
_ = lambda s: s

# Language available
LANGUAGES = (
  ('en', _('English')),
)

try:
    from local_settings import *
except ImportError:
    pass
