"""
This is a mock object that is supposed to simulate the behaviour of an IMAP
server.
"""

class IMAP4_SSL(object):
    """
    IMAP over SSL, all of this in virtual life!

    The tests are supposed to work well for the INBOX folder. For others,
    expect unexpected content!
    """

    logged_in = False

    def __init__(self, server, port):
        self.server = server
        self.port = port

    def login(self, username, password):
        """
        The test user has the following credentials:
        username: test_user
        password: password
        """
        if username == 'test_user' and password == 'password':
            self.logged_in = True
            return ('OK', ['test_user@example.com authenticated (Success)'])
        else:
            raise

    def logout(self):
        """
        Logout should fail if we're not logged in
        """
        if not self.logged_in:
            raise

        self.logged_in = False
        return ('BYE', ['LOGOUT Requested'])

    def close(self):
        """
        Closes the selected directory
        """
        return ('OK', ['Closing currend dir'])

    def list(self):
        """
        Lists the directories of the IMAP account.

        A simple Gmail account with some extra folders.
        """
        if not self.logged_in:
            raise

        return ('OK', [
            '(\\HasChildren) "/" "Archives"',
            '(\\HasNoChildren) "/" "Archives/Web"',
            '(\\HasNoChildren) "/" "INBOX"',
            '(\\HasNoChildren) "/" "OSS"',
            '(\\Noselect \\HasChildren) "/" "[Gmail]"',
            '(\\HasNoChildren) "/" "[Gmail]/All Mail"',
            '(\\HasNoChildren) "/" "[Gmail]/Drafts"',
            '(\\HasNoChildren) "/" "[Gmail]/Sent Mail"',
            '(\\HasNoChildren) "/" "[Gmail]/Starred"',
            '(\\HasNoChildren) "/" "[Gmail]/Trash"',
            ]
        )

    def status(self, name, statuses):
        if not self.logged_in:
            raise

        return ('OK',
                ['"%s" (MESSAGES 10 UIDNEXT 17626 UIDVALIDITY 2 UNSEEN 0)' % \
                        name])

    def select(self, name):
        """
        Select the INBOX folder
        """
        if not self.logged_in:
            raise

        return ('OK', ['10'])

    def search(self, charset, criterion):
        """
        Assuming charset is None and criterion is 'ALL'
        """
        if not self.logged_in:
            raise

        return ('OK', ['1 2 3 4 5 6 7 8 9 10'])

    def fetch(self, fetch_range, things):
        """
        Fetches a single message or a list of messages. Or flags. Or whatever.
        """
        if not self.logged_in:
            raise

        if things == 'FLAGS':
            return ('OK', ['1 (FLAGS ())', '2 (FLAGS ())',
                '3 (FLAGS (\\Seen))', '4 (FLAGS (\\Seen))', '5 (FLAGS ())',
                '6 (FLAGS ())', '7 (FLAGS (\\Seen))', '8 (FLAGS (\\Seen))',
                '9 (FLAGS (\\Seen))', '10 (FLAGS (\\Seen))'])
        elif things == 'RFC822':
            # Fetching message number 9
            return ('OK', [('9 (RFC822 {1510}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48147muo;\r\n        Fri, 13 Nov 2009 14:19:42 -0800 (PST)\r\nReceived: by 10.204.162.143 with SMTP id v15mr1931013bkx.50.1258150781955;\r\n        Fri, 13 Nov 2009 14:19:41 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-fx0-f228.google.com (mail-fx0-f228.google.com [209.85.220.228])\r\n        by mx.google.com with ESMTP id 6si2783036bwz.11.2009.11.13.14.19.41;\r\n        Fri, 13 Nov 2009 14:19:41 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates 209.85.220.228 as permitted sender) client-ip=209.85.220.228;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of bruno@renie.fr designates 209.85.220.228 as permitted sender) smtp.mail=bruno@renie.fr\r\nReceived: by mail-fx0-f228.google.com with SMTP id 28so4160196fxm.25\r\n        for <buburno@gmail.com>; Fri, 13 Nov 2009 14:19:41 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.13.198 with SMTP id d6mr690748bka.188.1258150781473; Fri, \r\n\t13 Nov 2009 14:19:41 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:19:21 +0100\r\nMessage-ID: <b6ffb7d0911131419o6aed14a2w9f973fb756e66320@mail.gmail.com>\r\nSubject: =?UTF-8?B?U2Vjb25kICgvKykqKyIrIiDDqcOow6nDoMOow6nDoA==?=\r\nTo: buburno@gmail.com\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\nTWVhbmluZ2xlc3MgY29udGVudAoKbGJlLMOgYWxkw6hwd2Qgw6DDqGw8ZHcKCjx3ZMOpYXdkw6nD\r\nqCBhdwpkYTx3ZCDDqcOoCgpDaGVlcnMK\r\n'), ')'])
        elif things == '(BODY[HEADER])':
            # Don't look at this -- it's horrible and boring at the same time
            return ('OK', [('1 (BODY[HEADER] {1280}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48313muo; Fri, 13 Nov 2009 14:24:02\r\n -0800 (PST)\r\nReceived: by 10.204.6.65 with SMTP id 1mr688673bky.186.1258151042258; Fri, 13\r\n Nov 2009 14:24:02 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-fx0-f221.google.com (mail-fx0-f221.google.com\r\n [209.85.220.221]) by mx.google.com with ESMTP id\r\n 24si11089355fxm.3.2009.11.13.14.24.02; Fri, 13 Nov 2009 14:24:02 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates\r\n 209.85.220.221 as permitted sender) client-ip=209.85.220.221;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of\r\n bruno@renie.fr designates 209.85.220.221 as permitted sender)\r\n smtp.mail=bruno@renie.fr\r\nReceived: by mail-fx0-f221.google.com with SMTP id 21so988289fxm.21 for\r\n <buburno@gmail.com>; Fri, 13 Nov 2009 14:24:02 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.16.88 with SMTP id n24mr5956533bka.52.1258151042113; Fri,\r\n 13 Nov 2009 14:24:02 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:23:42 +0100\r\nMessage-ID: <b6ffb7d0911131423o13cd0531h9f2b6e3a0b8e1853@mail.gmail.com>\r\nSubject: Last one\r\nTo: buburno@gmail.com\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n'), ')', ('2 (BODY[HEADER] {1284}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48305muo; Fri, 13 Nov 2009 14:23:41\r\n -0800 (PST)\r\nReceived: by 10.213.2.84 with SMTP id 20mr438978ebi.90.1258151021342; Fri, 13\r\n Nov 2009 14:23:41 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-bw0-f222.google.com (mail-bw0-f222.google.com\r\n [209.85.218.222]) by mx.google.com with ESMTP id\r\n 23si2182921eya.12.2009.11.13.14.23.41; Fri, 13 Nov 2009 14:23:41 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates\r\n 209.85.218.222 as permitted sender) client-ip=209.85.218.222;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of\r\n bruno@renie.fr designates 209.85.218.222 as permitted sender)\r\n smtp.mail=bruno@renie.fr\r\nReceived: by mail-bw0-f222.google.com with SMTP id 22so4033900bwz.5 for\r\n <buburno@gmail.com>; Fri, 13 Nov 2009 14:23:41 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.151.210 with SMTP id d18mr5840616bkw.203.1258151021101;\r\n Fri, 13 Nov 2009 14:23:41 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:23:21 +0100\r\nMessage-ID: <b6ffb7d0911131423y272376f9kcb84a1804a5fc7a9@mail.gmail.com>\r\nSubject: two to go\r\nTo: buburno@gmail.com\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n'), ')', ('3 (BODY[HEADER] {1293}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48286muo; Fri, 13 Nov 2009 14:23:10\r\n -0800 (PST)\r\nReceived: by 10.204.36.197 with SMTP id u5mr2524137bkd.81.1258150990097; Fri,\r\n 13 Nov 2009 14:23:10 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-fx0-f213.google.com (mail-fx0-f213.google.com\r\n [209.85.220.213]) by mx.google.com with ESMTP id\r\n 27si11370901fxm.48.2009.11.13.14.23.09; Fri, 13 Nov 2009 14:23:10 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates\r\n 209.85.220.213 as permitted sender) client-ip=209.85.220.213;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of\r\n bruno@renie.fr designates 209.85.220.213 as permitted sender)\r\n smtp.mail=bruno@renie.fr\r\nReceived: by mail-fx0-f213.google.com with SMTP id 5so4362345fxm.8 for\r\n <buburno@gmail.com>; Fri, 13 Nov 2009 14:23:09 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.0.69 with SMTP id 5mr5823429bka.173.1258150989204; Fri, 13\r\n Nov 2009 14:23:09 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:22:49 +0100\r\nMessage-ID: <b6ffb7d0911131422v46184d0cueed0434effac4df4@mail.gmail.com>\r\nSubject: eighth coool message\r\nTo: buburno@gmail.com\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n'), ')', ('4 (BODY[HEADER] {1292}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48245muo; Fri, 13 Nov 2009 14:22:14\r\n -0800 (PST)\r\nReceived: by 10.213.104.75 with SMTP id n11mr3241825ebo.70.1258150934602; Fri,\r\n 13 Nov 2009 14:22:14 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-bw0-f225.google.com (mail-bw0-f225.google.com\r\n [209.85.218.225]) by mx.google.com with ESMTP id\r\n 10si2046610eyz.19.2009.11.13.14.22.14; Fri, 13 Nov 2009 14:22:14 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates\r\n 209.85.218.225 as permitted sender) client-ip=209.85.218.225;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of\r\n bruno@renie.fr designates 209.85.218.225 as permitted sender)\r\n smtp.mail=bruno@renie.fr\r\nReceived: by mail-bw0-f225.google.com with SMTP id 25so3977203bwz.38 for\r\n <buburno@gmail.com>; Fri, 13 Nov 2009 14:22:14 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.155.82 with SMTP id r18mr975618bkw.180.1258150934288; Fri,\r\n 13 Nov 2009 14:22:14 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:21:54 +0100\r\nMessage-ID: <b6ffb7d0911131421o533e055bi3bc69d9c23c764b@mail.gmail.com>\r\nSubject: Seventh WHAT???\r\nTo: buburno@gmail.com\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n'), ')', ('5 (BODY[HEADER] {1374}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48224muo; Fri, 13 Nov 2009 14:21:46\r\n -0800 (PST)\r\nReceived: by 10.204.150.69 with SMTP id x5mr2340264bkv.197.1258150906440; Fri,\r\n 13 Nov 2009 14:21:46 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-fx0-f222.google.com (mail-fx0-f222.google.com\r\n [209.85.220.222]) by mx.google.com with ESMTP id\r\n 28si457399bwz.37.2009.11.13.14.21.46; Fri, 13 Nov 2009 14:21:46 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates\r\n 209.85.220.222 as permitted sender) client-ip=209.85.220.222;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of\r\n bruno@renie.fr designates 209.85.220.222 as permitted sender)\r\n smtp.mail=bruno@renie.fr\r\nReceived: by mail-fx0-f222.google.com with SMTP id 22so4214427fxm.2 for\r\n <buburno@gmail.com>; Fri, 13 Nov 2009 14:21:46 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.141.18 with SMTP id k18mr2021613bku.139.1258150906106;\r\n Fri, 13 Nov 2009 14:21:46 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:21:25 +0100\r\nMessage-ID: <b6ffb7d0911131421s58b71702v57e945d941ba1504@mail.gmail.com>\r\nSubject: =?UTF-8?B?U2l4dGggw6DDqcOpw6jDqcOgw6nDoMOow6nDqMOp?=\r\nTo: buburno@gmail.com\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: quoted-printable\r\n\r\n'), ')', ('6 (BODY[HEADER] {1295}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48216muo; Fri, 13 Nov 2009 14:21:20\r\n -0800 (PST)\r\nReceived: by 10.213.24.15 with SMTP id t15mr3244916ebb.42.1258150880743; Fri,\r\n 13 Nov 2009 14:21:20 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-bw0-f209.google.com (mail-bw0-f209.google.com\r\n [209.85.218.209]) by mx.google.com with ESMTP id\r\n 24si1064842eyx.21.2009.11.13.14.21.20; Fri, 13 Nov 2009 14:21:20 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates\r\n 209.85.218.209 as permitted sender) client-ip=209.85.218.209;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of\r\n bruno@renie.fr designates 209.85.218.209 as permitted sender)\r\n smtp.mail=bruno@renie.fr\r\nReceived: by mail-bw0-f209.google.com with SMTP id 1so4019113bwz.33 for\r\n <buburno@gmail.com>; Fri, 13 Nov 2009 14:21:20 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.155.82 with SMTP id r18mr974525bkw.180.1258150880173; Fri,\r\n 13 Nov 2009 14:21:20 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:21:00 +0100\r\nMessage-ID: <b6ffb7d0911131421r49913550y7a9076282d511ce9@mail.gmail.com>\r\nSubject: What? Fifth already\r\nTo: buburno@gmail.com\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n'), ')', ('7 (BODY[HEADER] {1285}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48196muo; Fri, 13 Nov 2009 14:20:55\r\n -0800 (PST)\r\nReceived: by 10.100.19.31 with SMTP id 31mr5965876ans.74.1258150854251; Fri,\r\n 13 Nov 2009 14:20:54 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-bw0-f225.google.com (mail-bw0-f225.google.com\r\n [209.85.218.225]) by mx.google.com with ESMTP id\r\n 27si11625589yxe.24.2009.11.13.14.20.53; Fri, 13 Nov 2009 14:20:54 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates\r\n 209.85.218.225 as permitted sender) client-ip=209.85.218.225;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of\r\n bruno@renie.fr designates 209.85.218.225 as permitted sender)\r\n smtp.mail=bruno@renie.fr\r\nReceived: by mail-bw0-f225.google.com with SMTP id 25so1175470bwz.18 for\r\n <buburno@gmail.com>; Fri, 13 Nov 2009 14:20:53 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.16.88 with SMTP id n24mr5952668bka.52.1258150853111; Fri,\r\n 13 Nov 2009 14:20:53 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:20:33 +0100\r\nMessage-ID: <b6ffb7d0911131420q5420dab4j8df91374817919db@mail.gmail.com>\r\nSubject: 4th thing\r\nTo: buburno@gmail.com\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n'), ')', ('8 (BODY[HEADER] {1320}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48188muo; Fri, 13 Nov 2009 14:20:37\r\n -0800 (PST)\r\nReceived: by 10.86.13.36 with SMTP id 36mr3614831fgm.25.1258150836848; Fri, 13\r\n Nov 2009 14:20:36 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-fx0-f219.google.com (mail-fx0-f219.google.com\r\n [209.85.220.219]) by mx.google.com with ESMTP id\r\n l12si9867989fgb.7.2009.11.13.14.20.36; Fri, 13 Nov 2009 14:20:36 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates\r\n 209.85.220.219 as permitted sender) client-ip=209.85.220.219;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of\r\n bruno@renie.fr designates 209.85.220.219 as permitted sender)\r\n smtp.mail=bruno@renie.fr\r\nReceived: by mail-fx0-f219.google.com with SMTP id 19so4276209fxm.37 for\r\n <buburno@gmail.com>; Fri, 13 Nov 2009 14:20:36 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.151.210 with SMTP id d18mr5836835bkw.203.1258150836188;\r\n Fri, 13 Nov 2009 14:20:36 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:20:16 +0100\r\nMessage-ID: <b6ffb7d0911131420r333f799dn76393c07c1f97fb1@mail.gmail.com>\r\nSubject: Third what????\r\nTo: buburno@gmail.com\r\nContent-Type: multipart/mixed; boundary=0015175cdcfcaa37c1047848112a\r\n\r\n'), ')', ('9 (BODY[HEADER] {1368}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48147muo; Fri, 13 Nov 2009 14:19:42\r\n -0800 (PST)\r\nReceived: by 10.204.162.143 with SMTP id v15mr1931013bkx.50.1258150781955;\r\n Fri, 13 Nov 2009 14:19:41 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-fx0-f228.google.com (mail-fx0-f228.google.com\r\n [209.85.220.228]) by mx.google.com with ESMTP id\r\n 6si2783036bwz.11.2009.11.13.14.19.41; Fri, 13 Nov 2009 14:19:41 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates\r\n 209.85.220.228 as permitted sender) client-ip=209.85.220.228;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of\r\n bruno@renie.fr designates 209.85.220.228 as permitted sender)\r\n smtp.mail=bruno@renie.fr\r\nReceived: by mail-fx0-f228.google.com with SMTP id 28so4160196fxm.25 for\r\n <buburno@gmail.com>; Fri, 13 Nov 2009 14:19:41 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.13.198 with SMTP id d6mr690748bka.188.1258150781473; Fri,\r\n 13 Nov 2009 14:19:41 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:19:21 +0100\r\nMessage-ID: <b6ffb7d0911131419o6aed14a2w9f973fb756e66320@mail.gmail.com>\r\nSubject: =?UTF-8?B?U2Vjb25kICgvKykqKyIrIiDDqcOow6nDoMOow6nDoA==?=\r\nTo: buburno@gmail.com\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n'), ')', ('10 (BODY[HEADER] {1301}', 'Delivered-To: buburno@gmail.com\r\nReceived: by 10.103.160.2 with SMTP id m2cs48131muo; Fri, 13 Nov 2009 14:19:10\r\n -0800 (PST)\r\nReceived: by 10.150.238.18 with SMTP id l18mr8993703ybh.14.1258150750201; Fri,\r\n 13 Nov 2009 14:19:10 -0800 (PST)\r\nReturn-Path: <bruno@renie.fr>\r\nReceived: from mail-bw0-f218.google.com (mail-bw0-f218.google.com\r\n [209.85.218.218]) by mx.google.com with ESMTP id\r\n 26si11150550gxk.61.2009.11.13.14.19.09; Fri, 13 Nov 2009 14:19:10 -0800 (PST)\r\nReceived-SPF: pass (google.com: domain of bruno@renie.fr designates\r\n 209.85.218.218 as permitted sender) client-ip=209.85.218.218;\r\nAuthentication-Results: mx.google.com; spf=pass (google.com: domain of\r\n bruno@renie.fr designates 209.85.218.218 as permitted sender)\r\n smtp.mail=bruno@renie.fr\r\nReceived: by mail-bw0-f218.google.com with SMTP id 10so4048964bwz.35 for\r\n <buburno@gmail.com>; Fri, 13 Nov 2009 14:19:09 -0800 (PST)\r\nMIME-Version: 1.0\r\nReceived: by 10.204.154.155 with SMTP id o27mr1981470bkw.198.1258150749182;\r\n Fri, 13 Nov 2009 14:19:09 -0800 (PST)\r\nFrom: =?UTF-8?B?QnJ1bm8gUmVuacOp?= <bruno@renie.fr>\r\nDate: Fri, 13 Nov 2009 23:18:48 +0100\r\nMessage-ID: <b6ffb7d0911131418h5c7de120le808a166dd6be4d8@mail.gmail.com>\r\nSubject: First crappy message\r\nTo: buburno@gmail.com\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n'), ')'])
