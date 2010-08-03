from django.contrib import admin

from users.models import Account, Profile
from django.contrib.auth.models import User


class ProfileInline(admin.StackedInline):
    model = Profile
    max_num = 1


class UserWithProfileAdmin(admin.ModelAdmin):
    inlines = [ProfileInline]


admin.site.register(Account)
admin.site.unregister(User)
admin.site.register(User, UserWithProfileAdmin)
