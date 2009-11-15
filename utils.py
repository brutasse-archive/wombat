import hashlib
from django.conf import settings

def safe_cache_key(value):
    """
    Returns an md5 hexdigest of value if len(value) > 250. Replaces invalid
    memcache control characters with an underscore. Also adds the
    CACHE_MIDDLEWARE_KEY_PREFIX to your keys automatically.

    From http://www.djangosnippets.org/snippets/1212/ -- Thanks!
    """
    for char in value:
        if ord(char) < 33:
            value = value.replace(char, '_')

    value = "%s_%s" % (settings.CACHE_MIDDLEWARE_KEY_PREFIX, value)

    if len(value) <= 250:
        return value
    md5 = hashlib.md5()
    md5.update(value)
    return md5.hexdigest()
