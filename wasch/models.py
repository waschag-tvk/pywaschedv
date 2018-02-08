import struct
import operator
import datetime
import math
from functools import reduce
from django.db import models
from django.conf import settings
from django.core import exceptions
from django.contrib import admin


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

    number = models.SmallIntegerField(primary_key=True)
    isAvailable = models.BooleanField(verbose_name='available')
    notes = models.CharField(max_length=500)

    def __str__(self):
        return 'Washing Machine {:d}'.format(self.number)

    class Meta:
        db_table = 'washingmachines'


@admin.register(WashingMachine)
class WashingMachineAdmin(admin.ModelAdmin):
    pass


APPOINTMENT_ERROR_REASONS = {
    11: 'Unsupported time',
    21: 'Machine out of service',
    31: 'User not active',
    41: 'Appointment taken',
}


class AppointmentError(RuntimeError):
    def __init__(self, reason, time=None, machine=None, user=None):
        if isinstance(reason, int):
            # will raise KeyError if wrong reason
            RuntimeError.__init__(self, APPOINTMENT_ERROR_REASONS[reason])
        else:
            raise NotImplementedError(
                'reason has to be int from APPOINTMENT_ERROR_REASONS')
        self.reason = reason
        self.time = time
        self.machine = machine
        self.user = user

    def long_reason(self):
        if self.reason == 41:
            return (
                "Can't book an appointment for machine {} at {} that is "
                'already booked'.format(self.machine, self.time)
            )
        # TODO good description for the rest of the reasons
        else:
            try:
                return APPOINTMENT_ERROR_REASONS[self.reason]
            except KeyError:
                return 'Appointment error {}'.format(self.reason)


class AppointmentManager(models.Manager):
    """Manages table-wide operations."""
    appointments_per_day = 16
    """number of appointments each day is divided into"""
    appointments_number = 16 * 7  # week
    """number of appointments offered into the future"""
    interval_minutes = 24 * 60 // appointments_per_day
    """length of an appointment in minutes"""

    def appointment_exists(self, time, machine):
        """Returns True if an appointment has been booked at this time, and False if the appointment time is free."""

        # search for appointments at this time for this machine
        appointment_qs = self.filter(time=time).filter(machine=machine)

        return len(appointment_qs) != 0

        # TODO: add logic to determine missing washing machine entries, input checks etc.
        # raise NotImplementedError

    @classmethod
    def next_appointment_number(cls, start_time=None):
        if start_time is None:
            start_time = datetime.datetime.now()
        return math.ceil(
            float(60 * start_time.hour + start_time.minute)
            / cls.interval_minutes)

    @classmethod
    def next_appointment_time(cls, start_time=None):
        if start_time is None:
            start_time = datetime.datetime.now()
        day_begin = datetime.datetime(
            start_time.year, start_time.month, start_time.day)
        return day_begin + datetime.timedelta(minutes=(
            cls.next_appointment_number(start_time) * cls.interval_minutes))

    @classmethod
    def scheduled_appointment_times(cls, start_time=None):
        begin = cls.next_appointment_time(start_time)
        return [
            begin + datetime.timedelta(minutes=i*cls.interval_minutes)
            for i in range(cls.appointments_number)]

    def why_not_bookable(self, time, machine, user):
        """Reason of why an appointment for the machine at this time can
        not be booked by the user. Return None if bookable."""
        # check whether time is generally bookable
        if not machine.isAvailable:
            return 21
        if not user.groups.filter(name='enduser').exists():
            return 31
        try:
            if not WashUser.objects.get(pk=user).isActivated:
                return 31
        except WashUser.DoesNotExist:
            return 31
        if self.appointment_exists(time, machine):
            return 41
        if time not in self.scheduled_appointment_times():
            return 11

    def bookable(self, time, machine, user):
        """Return whether an appointment for the machine at this time
        can be booked by the user. (this makes no reservation)"""
        return self.why_not_bookable(time, machine, user) is None

    def make_appointment(self, time, machine, user):
        """Creates an appointment for the user at the specified time."""

        if self.appointment_exists(time, machine):
            raise AppointmentError(41, time, machine, user)
        # TODO: finish writing


class Transaction(models.Model):
    '''to be considered atomic, so use only for one appointment
    (partial refunds wouldn't be needed!)
    '''
    fromUser = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            related_name='outgoing_transaction',
            )
    toUser = models.ForeignKey(
            settings.AUTH_USER_MODEL,
            related_name='incoming_transaction',
            )
    value = models.PositiveIntegerField()
    isBonus = models.BooleanField(default=False)
    notes = models.CharField(max_length=159)

    class Meta:
        db_table = 'transaction'


class Appointment(models.Model):

    time = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    machine = models.ForeignKey(WashingMachine)
    # multiple transactions if bonus portion, refunds etc. exist
    transactions = models.ManyToManyField(Transaction)
    wasUsed = models.BooleanField()
    objects = models.Manager()
    manager = AppointmentManager()
    reference = models.PositiveIntegerField()  # 0 to 2**31-1

    class Meta:
        db_table = 'appointments'


def ref_checksum(ref_partial, sup=8):
    return reduce(operator.xor, struct.pack('I', ref_partial)) % sup


def new_appointment(time, user, machine):
    timestamp = time.timestamp()
    reference = (timestamp << 2) + machine.number
    reference = (reference << 3) + ref_checksum(reference)
    return Appointment(
            time=time, user=user, machine=machine, reference=reference)


class WashParameters(models.Model):

    name = models.CharField(max_length=20)
    value = models.CharField(max_length=20)  # convert this to correct format, depending on parameter

    class Meta:
        db_table = 'washparameters'
