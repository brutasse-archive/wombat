from django.contrib import admin

from users.models import IMAP, Directory, SMTP, Account

class DirAdmin(admin.ModelAdmin):
    list_display = ('name', 'mailbox', 'has_children', 'no_select')

admin.site.register(IMAP)
admin.site.register(SMTP)
admin.site.register(Account)
admin.site.register(Directory, DirAdmin)
