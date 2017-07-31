from django.db import models


class Users(models.Model):
    username = models.TextField()
    isActivated = models.BooleanField()
    status = models.SmallIntegerField()

    class Meta:
        db_table = 'users'


class WashingMachines(models.Model):
    number = models.SmallIntegerField(unique=True)
    isAvailable = models.BooleanField()
    notes = models.CharField(max_length=500)

    class Meta:
        db_table = 'washingmachines'


class Appointments(models.Model):
    time = models.DateTimeField()
    user = models.ForeignKey(Users)
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
