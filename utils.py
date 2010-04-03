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


def encode(s):
    r = []
    _in = []
    for c in s:
        if ord(c) in (range(0x20, 0x26) + range(0x27, 0x7f)):
            if _in:
                r.extend(['&', modified_base64(''.join(_in)), '-'])
                del _in[:]
            r.append(str(c))
        elif c == '&':
            if _in:
                r.extend(['&', modified_base64(''.join(_in)), '-'])
                del _in[:]
            r.append('&-')
        else:
            _in.append(c)
    if _in:
        r.extend(['&', modified_base64(''.join(_in)), '-'])
    return ''.join(r)


def decode(s):
    r = []
    decode = []
    for c in s:
        if c == '&' and not decode:
            decode.append('&')
        elif c == '-' and decode:
            if len(decode) == 1:
                r.append('&')
            else:
                r.append(modified_unbase64(''.join(decode[1:])))
            decode = []
        elif decode:
            decode.append(c)
        else:
            r.append(c)
    if decode:
        r.append(modified_unbase64(''.join(decode[1:])))
    return ''.join(r)


def modified_base64(s):
    s_utf7 = s.encode('utf-7')
    return s_utf7[1:-1].replace('/', ',')


def modified_unbase64(s):
    s_utf7 = '+' + s.replace(',', '/') + '-'
    return s_utf7.decode('utf-7')
