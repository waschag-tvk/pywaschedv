import struct
import operator
import datetime
import math
from functools import reduce
from django.db import models, transaction
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth.models import User, Group

WASCH_EPOCH = datetime.date(1980, 1, 1)

STATUS_CHOICES = (
    (1, 'enduser'),
    (3, 'exWaschag'),
    (5, 'waschag'),
    (7, 'admin'),
    (9, 'god'),
)

GOD_NAME = 'WaschRoss'

WASCH_GROUP_NAMES = ['enduser', 'waschag']

# groups, is_staff, is_superuser
STATUS_RIGHTS = {
    1: (['enduser'], False, False),
    3: (['enduser'], False, False),
    5: (WASCH_GROUP_NAMES, True, False),
    7: (WASCH_GROUP_NAMES, True, False),
    9: (WASCH_GROUP_NAMES, True, True),
}


def get_or_create_wash_groups():
    return [
        Group.objects.get_or_create(name=name)
        for name in WASCH_GROUP_NAMES
    ]


class StatusRights:
    """Friendly access to status rights"""

    def __init__(self, status):
        self.status = status

    @property
    def groups(self):
        """Names of groups"""
        return STATUS_RIGHTS[self.status][0]

    @property
    def is_staff(self):
        return STATUS_RIGHTS[self.status][1]

    @property
    def is_superuser(self):
        return STATUS_RIGHTS[self.status][2]


class WashUserManager(models.Manager):
    def _create_with_user(
            self, user_or_username, isActivated, status, **kwargs):
        if isinstance(user_or_username, User):
            user = user_or_username
        else:
            user = User.objects.create(username=user_or_username, **kwargs)
        try:
            washuser = self.get(user=user)
        except WashUser.DoesNotExist:  # normally expected
            washuser = self.create(
                user=user, isActivated=isActivated, status=status)
        if isActivated:
            washuser.activate()
        return washuser

    def create_enduser(self, user_or_username, isActivated=True, **kwargs):
        """This is what you normally use"""
        return self._create_with_user(
            user_or_username, status=1, isActivated=isActivated, **kwargs)

    def get_or_create_god(self):
        was_created = True
        try:
            god_user = User.objects.get(username=GOD_NAME)
            god = self.get(user=god_user)
            was_created = False
        except User.DoesNotExist:
            god = self._create_with_user(GOD_NAME, status=9, isActivated=True)
        except WashUser.DoesNotExist:
            god = self._create_with_user(
                god_user, status=9, isActivated=True)
        return god, was_created


class WashUser(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    isActivated = models.BooleanField()
    status = models.SmallIntegerField(choices=STATUS_CHOICES)
    objects = WashUserManager()

    def activate(self):
        status_rights = StatusRights(self.status)
        groups = [
            group for group, _ in (
                Group.objects.get_or_create(name=group_name)
                for group_name in status_rights.groups
            )]
        self.user.groups.add(*groups)
        # only adding rights
        if status_rights.is_staff:
            self.user.is_staff = True
        if status_rights.is_superuser:
            self.user.is_superuser = True
        self.user.save()
        self.isActivated = True
        self.save()

    def deactivate(self):
        if self.status == 9:
            raise ValueError('God should not be deactivated!')
        self.user.groups.clear()
        self.user.is_staff = False
        self.user.is_superuser = False
        self.user.save()
        self.isActivated = False
        self.save()

    class Meta:
        db_table = 'washuser'


def user_is_washuser(user):
    # default related_name according to
    # https://docs.djangoproject.com/en/2.0/ref/models/fields/#onetoonefield
    try:
        return user.washuser is not None
    except User.DoesNotExist:
        return False


class WashingMachine(models.Model):

    number = models.SmallIntegerField(primary_key=True)
    isAvailable = models.BooleanField(verbose_name='available')
    notes = models.CharField(max_length=500)

    def __str__(self):
        return 'Washing Machine {:d}'.format(self.number)

    class Meta:
        db_table = 'washingmachines'


APPOINTMENT_ERROR_REASONS = {
    11: 'Unsupported time',
    21: 'Machine out of service',
    31: 'User not active',
    41: 'Appointment taken',
    51: 'Appointment cancelled',  # for use
    61: 'Appointment already used',  # for cancellation
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
        """Returns True if an appointment has been booked at this time
        (and not canceled), and False if the appointment time is free.
        """

        # search for appointments at this time for this machine
        appointment_qs = self.filter(
            time=time, machine=machine, canceled=False)
        return appointment_qs.exists()

        # TODO: add logic to determine missing washing machine entries, input checks etc.
        # raise NotImplementedError

    @classmethod
    def next_appointment_number(cls, start_time):
        """Get next appointment beginning at or after given
        start_time"""
        minute = start_time.minute + (1 if start_time.second > 0 else 0)
        return math.ceil(
            float(60 * start_time.hour + minute) / cls.interval_minutes)

    @classmethod
    def appointment_number_at(cls, time):
        """Get appointment number of the appointment taking place at
        given time.
        Same as next_appointment_number if time is exactly the start of
        an appointment. Otherwise next_appointment_number - 1."""
        return (60 * time.hour + time.minute) // cls.interval_minutes

    @classmethod
    def time_of_appointment_number(cls, appointment_number):
        return datetime.time() + datetime.timedelta(
            minutes=appointment_number * cls.interval_minutes)

    @classmethod
    def next_appointment_time(cls, start_time=None):
        if start_time is None:
            start_time = datetime.datetime.now()
        day_begin = datetime.datetime(
            start_time.year, start_time.month, start_time.day)
        return day_begin + datetime.timedelta(minutes=(
            cls.next_appointment_number(start_time.time())
            * cls.interval_minutes))

    @classmethod
    def scheduled_appointment_times(cls, start_time=None):
        begin = cls.next_appointment_time(start_time)
        return [
            begin + datetime.timedelta(minutes=i*cls.interval_minutes)
            for i in range(cls.appointments_number)]

    def filter_for_reference(self, reference):
        tmp_appointment = Appointment.from_reference(reference, None)
        return self.filter(
            time=tmp_appointment.time, machine=tmp_appointment.machine)

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

    @transaction.atomic
    def make_appointment(self, time, machine, user):
        """Creates an appointment for the user at the specified time."""
        error_reason = self.why_not_bookable(time, machine, user)
        if error_reason is not None:
            raise AppointmentError(error_reason, time, machine, user)
        try:
            my_canceled_appointment = self.get(
                time=time, machine=machine, user=user)
            my_canceled_appointment.rebook()
            return my_canceled_appointment
        except Appointment.DoesNotExist:  # normal case
            appointment = self.create(
                time=time, machine=machine, user=user, wasUsed=False)
            # TODO: finish writing
            return appointment


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
    notes = models.CharField(max_length=159, default='')
    method = models.CharField(max_length=39, default='')
    methodReference = models.CharField(max_length=159, default='')

    class Meta:
        db_table = 'transaction'


@receiver(models.signals.post_init, sender=Transaction)
def post_init_transaction(sender, **kwargs):
    if not user_is_washuser(kwargs['instance'].fromUser):
        raise ValueError('Given fromUser is not a WashUser!')
    if not user_is_washuser(kwargs['instance'].toUser):
        raise ValueError('Given toUser is not a WashUser!')


def ref_checksum(ref_partial, sup=8):
    return reduce(operator.xor, struct.pack('I', ref_partial)) % sup


class Appointment(models.Model):

    time = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    machine = models.ForeignKey(WashingMachine)
    # multiple transactions if bonus portion, refunds etc. exist
    transactions = models.ManyToManyField(Transaction)
    wasUsed = models.BooleanField()
    canceled = models.BooleanField(default=False)
    objects = models.Manager()
    manager = AppointmentManager()

    class Meta:
        db_table = 'appointments'

    @transaction.atomic
    def cancel(self):
        # TODO refund
        if self.wasUsed:
            raise AppointmentError(61, self.time, self.machine, self.user)
        self.canceled = True
        self.save()

    @transaction.atomic
    def rebook(self):
        # TODO payment
        error_reason = Appointment.manager.why_not_bookable(
            self.time, self.machine, self.user)
        if error_reason is not None:
            raise AppointmentError(
                error_reason, self.time, self.machine, self.user)
        self.canceled = False
        self.save()

    def why_not_usable(self):
        if not self.machine.isAvailable:
            return 21
        if not self.user.groups.filter(name='enduser').exists():
            return 31
        try:
            if not WashUser.objects.get(pk=self.user).isActivated:
                return 31
        except WashUser.DoesNotExist:
            return 31
        if self.canceled:
            return 51

    @transaction.atomic
    def use(self):
        error_reason = self.why_not_usable()
        if error_reason is not None:
            raise AppointmentError(
                error_reason, self.time, self.machine, self.user)
        self.wasUsed = True
        self.save()

    @property
    def appointment_number(self):
        return self.manager.appointment_number_at(self.time)

    @property
    def reference(self):
        """reference is 0 to 2**31 - 1, consisting of binary fields
        18 for days since epoch (enough till year 2696!),
        5 for appointment number,
        2 for machine number (only 4 machines supported!),
        3 for checksum

        note: using datetime.timestamp, even without seconds, requires
        far more space!
        """
        short_days = (self.time.date() - WASCH_EPOCH).days
        if short_days < 0 or short_days >= 2**18:
            raise ValueError('only years between 1980 and 2696 supported!')
        reference = short_days << 5
        reference += self.appointment_number
        reference <<= 2
        reference += self.machine.number % 4
        reference <<= 3
        return reference + ref_checksum(reference)

    @classmethod
    def from_reference(cls, reference, user, allow_unsaved_machine=False):
        checksum = reference % 8
        reference >>= 3
        if ref_checksum(reference) != checksum:
            return ValueError('checksum does not match!')
        try:
            machine = WashingMachine.objects.get(number=reference % 4)
        except WashingMachine.DoesNotExist:
            if not allow_unsaved_machine:
                raise
            machine = WashingMachine(number=reference % 4)
        reference >>= 2
        time_of_day = AppointmentManager.time_of_appointment_number(
            reference % 32)
        reference >>= 5
        # assumes time is the start time of appointment
        time = datetime.combine(
            WASCH_EPOCH + datetime.timedelta(days=reference),
            time_of_day)
        return cls(time=time, machine=machine, user=user)


@receiver(models.signals.post_init, sender=Appointment)
def post_init_appointment(sender, **kwargs):
    if not user_is_washuser(kwargs['instance'].user):
        raise ValueError('Given user is not a WashUser!')


class WashParameters(models.Model):

    name = models.CharField(max_length=20)
    value = models.CharField(max_length=20)  # convert this to correct format, depending on parameter

    class Meta:
        db_table = 'washparameters'
