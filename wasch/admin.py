from django.contrib import admin
from wasch.models import WashUser


class WashUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'isActivated', 'status']
    ordering = ['user']


admin.site.register(WashUser, WashUserAdmin)
