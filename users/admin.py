from django.contrib import admin

from users.models import IMAP, Directory, SMTP, Account, Profile
from django.contrib.auth.models import User

class DirAdmin(admin.ModelAdmin):
    list_display = ('name', 'mailbox', 'has_children', 'no_select',
                    'unread', 'total')


class ProfileInline(admin.StackedInline):
    model = Profile
    max_num = 1


class UserWithProfileAdmin(admin.ModelAdmin):
    inlines = [ProfileInline]


admin.site.register(IMAP)
admin.site.register(SMTP)
admin.site.register(Account)
admin.site.register(Directory, DirAdmin)
admin.site.unregister(User)
admin.site.register(User, UserWithProfileAdmin)
