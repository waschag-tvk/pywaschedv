from django.contrib import admin
from wasch.models import WashUser, WashingMachine, WashParameters


@admin.register(WashUser)
class WashUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'isActivated', 'status']
    ordering = ['user']


@admin.register(WashingMachine)
class WashingMachineAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'isAvailable', 'notes']
    ordering = ['number']


@admin.register(WashParameters)
class WashParametersAdmin(admin.ModelAdmin):
    list_display = ['name', 'value']
