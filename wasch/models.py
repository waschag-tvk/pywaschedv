import struct
import operator
import datetime
import math
from functools import reduce
from django.db import models, transaction
from django.dispatch import receiver
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User, Group
from wasch import payment

WASCH_EPOCH = datetime.date(1980, 1, 1)

STATUS_CHOICES = (
    (1, 'enduser'),
    (3, 'exWaschag'),
    (5, 'waschag'),
    (7, 'admin'),
    (9, 'god'),
)

GOD_NAME = 'WaschRoss'
SERVICE_USER_NAME = 'WaschService'

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
    def _get_or_create_with_user(
            self, user_or_username, isActivated, status, **kwargs):
        if isinstance(user_or_username, User):
            user = user_or_username
            user_was_created = False
        else:
            user, user_was_created = User.objects.get_or_create(
                username=user_or_username, defaults=kwargs)
        washuser, was_created = self.get_or_create(
            user=user, defaults={'isActivated': isActivated, 'status': status})
        if isActivated:
            washuser.activate()
        return washuser, was_created, user_was_created

    def create_enduser(self, user_or_username, isActivated=True, **kwargs):
        """This is what you normally use"""
        washuser, _, _ = self._get_or_create_with_user(
            user_or_username, status=1, isActivated=isActivated, **kwargs)
        return washuser

    def get_or_create_god(self):
        try:
            self.cached_god.activate()
            return self.cached_god, False
        except AttributeError:
            pass  # expected
        god, was_created, user_was_created = self._get_or_create_with_user(
            GOD_NAME, status=9, isActivated=True)
        self.cached_god = god
        return god, was_created or user_was_created

    def get_or_create_service_user(self):
        try:
            return self.cached_service_washuser, False
        except AttributeError:
            pass  # expected
        service, was_created, user_was_created = self._get_or_create_with_user(
            SERVICE_USER_NAME, status=5, isActivated=False)
        self.cached_service_washuser = service
        return service, was_created or user_was_created


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

    @property
    def remaining_ration(self):
        """number of allowed use this month"""
        if self.status == 9:
            return GOD_RATION
        ration = int(WashParameters.objects.get_value('ration'))
        use = Appointment.objects.filter(
            user=self.user, canceled=False,
        ).count()
        return ration - use

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
    32: 'Monthly ration of user is used up',
    41: 'Appointment taken',
    51: 'Appointment canceled',  # for use
    61: 'Appointment already used',  # for use or cancellation
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
        # datetime.time can't add datetime.timedelta
        minute = appointment_number * cls.interval_minutes
        hour = (minute // 60) % 24
        minute %= 60
        return datetime.time(hour=hour, minute=minute)

    @classmethod
    def next_appointment_time(cls, start_time=None):
        if start_time is None:
            start_time = datetime.datetime.now()
        day_begin = datetime.datetime(
            start_time.year, start_time.month, start_time.day)
        return timezone.make_aware(day_begin + datetime.timedelta(minutes=(
            cls.next_appointment_number(start_time.time())
            * cls.interval_minutes)))

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
        if hasattr(self, 'bookable_cache'):
            why = self.bookable_cache[machine.number]
            if isinstance(why, int):
                return why
            try:
                why = why[user.username]
                if isinstance(why, int):
                    return why
                return why[time]
            except KeyError:
                pass  # just not using cache
        if not machine.isAvailable:
            return 21
        if not user.groups.filter(name='enduser').exists():
            return 31
        try:
            washuser = WashUser.objects.get(pk=user)
            if not washuser.isActivated:
                return 31
            if washuser.remaining_ration < 1:
                return 32
        except WashUser.DoesNotExist:
            return 31
        if self.appointment_exists(time, machine):
            return 41
        if time not in self.scheduled_appointment_times():
            return 11

    def prefetch_bookable(self, users, times=None, machines=None):
        scheduledTimes = self.scheduled_appointment_times()
        if times is None:
            times = scheduledTimes
        if machines is None:
            machines = WashingMachine.objects.all()
        # bookable_cache is nested dict over machine, user, time
        # when a machine is not available, it's not a dict, but just
        # this value; same for user not active etc.
        if not hasattr(self, 'bookable_cache'):
            self.bookable_cache = {}
        availableMachines = []
        for machine in machines:
            if not machine.isAvailable:
                self.bookable_cache[machine.number] = 21
            else:
                self.bookable_cache[machine.number] = {}
				# TODO: should setdefault be use then have to first check if entrie in bookable_cache is alrd a dict
                availableMachines.append(machine)
        if not availableMachines:
            return
        usersWhoCanBook = []
        for user in users:
            why = None
            if not user.groups.filter(name='enduser').exists():
                why = 31
            try:
                washuser = WashUser.objects.get(pk=user)
                if not washuser.isActivated:
                    why = 31
                elif washuser.remaining_ration < 1:
                    why = 32
            except WashUser.DoesNotExist:
                why = 31
            if why is not None:
                for machine in availableMachines:
                    self.bookable_cache[machine.number][user.username] = why
            else:
                usersWhoCanBook.append(user)
        if not usersWhoCanBook:
            return
        for machine in availableMachines:
            for user in usersWhoCanBook:
                self.bookable_cache[machine.number].setdefault(
                    user.username, {})
                for time in times:
                    if time not in scheduledTimes:
                        continue  # not worthy of caching
                    (
                        self.bookable_cache[machine.number][user.username]
                    )[time] = (
                        41 if self.appointment_exists(time, machine) else None)

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
            try:
                appointment.pay()
            except payment.PaymentError:
                appointment.delete()
                raise
            return appointment


GOD_RATION = 31 * AppointmentManager.appointments_per_day


class TransactionManager(models.Manager):
    def pay(self, value, fromUser, toUser, bonusAllowed=True, notes=''):
        '''
        :raises PaymentError: when full payment wasn't achieved
        '''
        paid = 0
        reference = ''
        if bonusAllowed:
            method = WashParameters.objects.get_value('bonus-method')
            bonusCoverage = payment.coverage(value, fromUser, method)
            if bonusCoverage == value:  # only "all or nothing" implemented
                paid, reference = payment.pay(
                    value, fromUser, toUser, method, notes=notes)
        if paid > 0:
            isBonus = True
        else:
            isBonus = False
            method = WashParameters.objects.get_value('payment-method')
            _, reference = payment.pay(
                value, fromUser, toUser, method, notes=notes)
        return self.create(
            fromUser=fromUser,
            toUser=toUser,
            value=value,
            isBonus=isBonus,
            notes=notes,
            method=method,
            methodReference=reference,
        )

    def refund(self, transaction):
        # only full refund implemented
        _, reference = payment.refund(
            transaction.method, transaction.methodReference)
        return self.create(
            fromUser=transaction.toUser,
            toUser=transaction.fromUser,
            value=transaction.value,
            isBonus=transaction.isBonus,
            notes='refund {}\n{}'.format(transaction.pk, transaction.notes),
            method=transaction.method,
            methodReference=reference,
        )


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
    objects = TransactionManager()

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


class AnonymousAppointment:
    """Helper class for Appointment parameters without user;
    mainly for AppointmentManager.from_reference"""

    def __init__(self, time, machine):
        self.time = time
        self.machine = machine

    def get(self, user):
        return Appointment(time=self.time, machine=self.machine, user=user)


class Appointment(models.Model):

    time = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    machine = models.ForeignKey(WashingMachine)
    # multiple transactions if refunds etc. exist
    transactions = models.ManyToManyField(Transaction)
    refundableTransaction = models.OneToOneField(
        Transaction, null=True, related_name='refundable_appointment')
    wasUsed = models.BooleanField()
    canceled = models.BooleanField(default=False)
    objects = models.Manager()
    manager = AppointmentManager()

    class Meta:
        db_table = 'appointments'

    def pay(self, bonusAllowed=True):
        price = int(WashParameters.objects.get_value('price'))
        notes = 'make appointment {}'.format(self.reference)
        service_washuser, _ = WashUser.objects.get_or_create_service_user()
        transaction = Transaction.objects.pay(
            price, self.user, service_washuser.user, bonusAllowed, notes)
        self.transactions.add(transaction)
        self.refundableTransaction = transaction
        self.save()

    @transaction.atomic
    def cancel(self):
        if self.wasUsed:
            raise AppointmentError(61, self.time, self.machine, self.user)
        try:
            refundableTransaction = Transaction.objects.get(
                refundable_appointment=self)
            # may raise payment.PaymentError
            transaction = Transaction.objects.refund(refundableTransaction)
            self.transactions.add(transaction)
            self.refundableTransaction = None
        except Transaction.DoesNotExist:
            pass  # nothing to refund
        self.canceled = True
        self.save()

    @transaction.atomic
    def rebook(self):
        error_reason = Appointment.manager.why_not_bookable(
            self.time, self.machine, self.user)
        if error_reason is not None:
            raise AppointmentError(
                error_reason, self.time, self.machine, self.user)
        self.pay()  # may raise payment.PaymentError
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
        if self.wasUsed:
            return 61

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
        return Appointment.manager.appointment_number_at(self.time)

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
        short_days = (timezone.make_naive(self.time).date() - WASCH_EPOCH).days
        if short_days < 0 or short_days >= 2**18:
            raise ValueError('only years between 1980 and 2696 supported!')
        reference = short_days << 5
        reference += self.appointment_number
        reference <<= 2
        reference += self.machine.number % 4
        checksum = ref_checksum(reference)
        reference <<= 3
        return reference + checksum

    @classmethod
    def from_reference(cls, reference, user, allow_unsaved_machine=False):
        checksum = reference % 8
        reference >>= 3
        if ref_checksum(reference) != checksum:
            raise ValueError('checksum does not match!')
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
        time = timezone.make_aware(datetime.datetime.combine(
            WASCH_EPOCH + datetime.timedelta(days=reference),
            time_of_day))
        if user is None:
            return AnonymousAppointment(time=time, machine=machine)
        return cls(time=time, machine=machine, user=user)


@receiver(models.signals.post_init, sender=Appointment)
def post_init_appointment(sender, **kwargs):
    if not user_is_washuser(kwargs['instance'].user):
        raise ValueError('Given user is not a WashUser!')


class WashParametersManager(models.Manager):
    def get_value(self, name):
        value = self.get(name=name).value
        if value == 'bonus' and name in ('payment-method', 'bonus-method'):
            from wasch.bonuspayment import BonusPayment
            payment.register_method('bonus', BonusPayment, no_clobber=True)
        return value

    def update_value(self, name, value):
        return self.filter(name=name).update(value=value)


class WashParameters(models.Model):
    WASH_PARAM_NAMES = (
        ('payment-method', 'payment method name'),
        ('bonus-method', 'bonus payment method name'),
        ('price', 'price in EUR Cent to be paid by user per wash'),
        ('ration', 'allowed use per month per user'),
        ('bonus-waschag', 'bonus for waschag members in EUR Cent per month'),
        ('retention-time', 'days to keep user data'),
        ('retention-time-waschag', 'days to keep waschag user data'),
        (
            'cancel-period',
            'minimum minutes prior to appointment to allow cancellation'
        ),
    )
    name = models.CharField(
        max_length=20, choices=WASH_PARAM_NAMES, unique=True)
    value = models.CharField(max_length=20)  # convert this to correct format, depending on parameter
    objects = WashParametersManager()

    class Meta:
        db_table = 'washparameters'


@receiver(models.signals.pre_save, sender=WashParameters)
def pre_save_wash_parameters(sender, **kwargs):
    instance = kwargs['instance']
    if instance.value == 'bonus' and instance.name in (
            'payment-method', 'bonus-method'):
        from wasch.bonuspayment import BonusPayment
        payment.register_method('bonus', BonusPayment, no_clobber=True)
