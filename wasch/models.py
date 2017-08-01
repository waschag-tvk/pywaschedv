from django.db import models
from django.conf import settings

STATUS_CHOICES = (
    (1, 'enduser'),
    (3, 'exWaschag'),
    (5, 'waschag'),
    (7, 'admin'),
    (9, 'god'),
)


class WashUser(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    isActivated = models.BooleanField()
    status = models.SmallIntegerField(choices=STATUS_CHOICES)

    class Meta:
        db_table = 'washuser'


class WashingMachines(models.Model):
    number = models.SmallIntegerField(unique=True)
    isAvailable = models.BooleanField()
    notes = models.CharField(max_length=500)

    class Meta:
        db_table = 'washingmachines'


class Appointments(models.Model):
    time = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    machine = models.ForeignKey(WashingMachines)
    isBonus = models.BooleanField()
    wasUsed = models.BooleanField()

    class Meta:
        db_table = 'appointments'


class WashParameters(models.Model):
    name = models.CharField(max_length=20)
    value = models.CharField(max_length=20)  # convert this to correct format, depending on parameter

    class Meta:
        db_table = 'washparameters'
