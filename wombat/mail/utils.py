import email.header
import re

SUBJECT_RE = re.compile(r'^(\[[^\]]+\])?\s*re\s*:\s+(.*)$', re.IGNORECASE)


def address_struct_to_addresses(address_struct):
    """
    Converts an IMAP "address structure" to a proper list of email
    addresses with a format looking like:
        ('First Last <username@example.com>',
         'Other Dude <foo.bar@baz.org>')
    """
    addresses = []
    for name, at_domain, mailbox_name, host in address_struct:
        if name is None:
            addresses.append('%s@%s' % (mailbox_name, host))
            continue
        name = clean_header(name)
        cleaned = '%s <%s@%s>' % (name, mailbox_name, host)
        addresses.append(cleaned)
    return addresses


def clean_header(header):
    """
    The headers returned by the IMAP server are not necessarily
    human-friendly, especially if they contain non-ascii characters. This
    function cleans all of this and return a beautiful, utf-8 encoded
    header.
    """
    if header is None:
        return ''
    if header.startswith('"'):
        header = header.replace('"', '')
    cleaned = email.header.decode_header(header)
    assembled = ''
    for element in cleaned:
        if assembled == '':
            separator = ''
        else:
            separator = ' '
        if element[1] is not None:
            decoded = element[0].decode(element[1])
        else:
            decoded = element[0]
        assembled += '%s%s' % (separator, decoded)
    return assembled


def clean_subject(subject):
    """
    Removes the Re: RE : RE: crap from a subject.
    """
    match = SUBJECT_RE.match(subject)
    while match:
        subject = ' '.join([m for m in match.groups() if m is not None])
        match = SUBJECT_RE.match(subject)
    return subject
