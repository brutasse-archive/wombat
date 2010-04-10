# -*- coding: utf-8 -*-

import email.parser

from django.db import models


class Message(object):
    raw = ''
    headers = {}
    body = u''
    html_body = u''

    def __init__(self, content):
        self.raw = content
        self.parse()

    def parse(self):
        """Fetches the content of the message and populates the available
        headers"""
        p = email.parser.Parser()
        message = p.parsestr(self.raw)
        for part in message.walk():
            charset = part.get_content_charset()
            for header, to_clean in part.items():
                self.headers[header.lower()] = self._clean_header(to_clean)

            payload = part.get_payload(decode=1)
            if charset is not None:
                payload = payload.decode(charset)

            if part.get_content_type() == 'text/plain':
                self.body += payload

            if part.get_content_type() == 'text/html':
                self.html_body += payload
        if not self.body:
            self.body = unescape_entities(strip_tags(self.html_body))

    @classmethod
    def _clean_header(cls, header):
        """
        The headers returned by the IMAP server are not necessarily
        human-friendly, especially if they contain non-ascii characters. This
        function cleans all of this and return a beautiful, utf-8 encoded
        header.
        """
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
