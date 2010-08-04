from django.contrib import admin

from mail.models import SMTP, IMAP, Mailbox


class MailboxAdmin(admin.ModelAdmin):
    list_display = ('name', 'imap', 'has_children', 'no_select',
                    'unread', 'total', 'parent')


admin.site.register(IMAP)
admin.site.register(SMTP)
admin.site.register(Mailbox, MailboxAdmin)
