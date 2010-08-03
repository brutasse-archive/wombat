from django.contrib import admin

from mail.models import SMTP, IMAP, Thread, Mailbox, Message


class MailboxAdmin(admin.ModelAdmin):
    list_display = ('name', 'imap', 'has_children', 'no_select',
                    'unread', 'total', 'parent')


class MessageInline(admin.TabularInline):
    model = Message

class ThreadAdmin(admin.ModelAdmin):
    list_display = ('__unicode__', 'get_message_count')
    inlines = [MessageInline]

admin.site.register(IMAP)
admin.site.register(SMTP)
admin.site.register(Thread, ThreadAdmin)
admin.site.register(Mailbox, MailboxAdmin)
