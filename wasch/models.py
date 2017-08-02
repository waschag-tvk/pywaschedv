from django.db import models
from django.conf import settings
from django.core import exceptions


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


class WashingMachine(models.Model):

    number = models.SmallIntegerField(unique=True)
    isAvailable = models.BooleanField()
    notes = models.CharField(max_length=500)

    class Meta:
        db_table = 'washingmachines'


class AppointmentManager(models.Manager):
    """Manages table-wide operations."""

    def appointment_exists(self, time, machine_number):
        """Returns True if an appointment has been booked at this time, and False if the appointment time is free."""

        # search for appointments at this time for this machine number
        machine = WashingMachine.objects.get(number=machine_number)
        appointment_qs = self.filter(time=time).filter(machine=machine.id)

        if len(appointment_qs) != 0:
            return False
        else:
            return True

        # TODO: add logic to determine missing washing machine entries, input checks etc.
        # raise NotImplementedError

    def make_appointment(self, user, machine, time, is_bonus=False):
        """Creates an appointment for the user at the specified time."""

        if self.appointment_exists(time, machine):
            raise Exception("Can't book an appointment that is already booked")

        # TODO: finish writing


class Appointment(models.Model):

    time = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    machine = models.ForeignKey(WashingMachine)
    isBonus = models.BooleanField()
    wasUsed = models.BooleanField()
    manager = AppointmentManager()

    class Meta:
        db_table = 'appointments'


class WashParameters(models.Model):

    name = models.CharField(max_length=20)
    value = models.CharField(max_length=20)  # convert this to correct format, depending on parameter

    class Meta:
        db_table = 'washparameters'
