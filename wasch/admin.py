from django.contrib import admin
from wasch.models import WashUser, WashingMachine


@admin.register(WashUser)
class WashUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'isActivated', 'status']
    ordering = ['user']


@admin.register(WashingMachine)
class WashingMachineAdmin(admin.ModelAdmin):
    pass
