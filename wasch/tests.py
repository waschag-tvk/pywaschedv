import datetime
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth.models import (
    User,
)
from wasch.models import (
    Appointment,
    WashUser,
    WashParameters,
    # not models:
    AppointmentError,
    StatusRights,
)
from wasch import tvkutils, payment, bonuspayment
from accounts import facade


class WashUserTestCase(TestCase):
    def test_god(self):
        god, _ = WashUser.objects.get_or_create_god()
        self.assertTrue(god.isActivated)
        self.assertTrue(god.user.is_staff)
        self.assertTrue(god.user.is_superuser)
        group_names = (group.name for group in god.user.groups.all())
        for expected_group in StatusRights(9).groups:
            self.assertIn(expected_group, group_names)


class AppointmentTestCase(TestCase):
    exampleUserName = 'waschexample'
    examplePoorUserName = 'poor'
    exampleTime = Appointment.manager.scheduled_appointment_times()[-1]
    exampleTooOldTime = timezone.make_aware(datetime.datetime(1991, 12, 25))
    exampleTooOldReference = 4481037
    exampleMachine, exampleBrokenMachine, lastMachine = \
        tvkutils.get_or_create_machines()[0]

    def setUp(self):
        tvkutils.setup()
        self.exampleMachine.isAvailable = True
        self.exampleMachine.save()
        self.exampleBrokenMachine.isAvailable = False  # though this is default
        self.exampleMachine.save()
        self.lastMachine.isAvailable = True
        self.lastMachine.save()
        WashUser.objects.create_enduser(self.exampleUserName, isActivated=True)
        WashUser.objects.create_enduser(
            self.examplePoorUserName, isActivated=False)

    def _createExample(self, machine=None, wasUsed=False):
        user = User.objects.get(username=self.exampleUserName)
        if machine is None:
            machine = self.exampleMachine
        return Appointment.objects.create(
            time=self.exampleTime, machine=machine, user=user, wasUsed=wasUsed)

    def test_create(self):
        result = self._createExample()
        self.assertEqual(result.time, self.exampleTime)
        self.assertEqual(result.machine, self.exampleMachine)
        self.assertEqual(result.user.username, self.exampleUserName)
        self.assertTrue(Appointment.manager.appointment_exists(
            result.time, result.machine))
        self.assertFalse(Appointment.manager.bookable(
            result.time, result.machine, result.user))
        self.assertEqual(
            Appointment.manager.why_not_bookable(
                result.time, result.machine, result.user),
            41,  # Appointment taken
        )
        result.cancel()
        self.assertTrue(Appointment.manager.bookable(
            result.time, result.machine, result.user))

    def test_bookable(self):
        user = User.objects.get(username=self.exampleUserName)
        poorUser = User.objects.get(username=self.examplePoorUserName)
        god, _ = WashUser.objects.get_or_create_god()
        self.assertEqual(
            Appointment.manager.why_not_bookable(
                self.exampleTime, self.exampleMachine, poorUser),
            31,  # User not active
        )
        self.assertTrue(Appointment.manager.bookable(
            self.exampleTime, self.exampleMachine, user))
        self.assertTrue(Appointment.manager.bookable(
            self.exampleTime, self.exampleMachine, god.user))
        self.assertEqual(
            Appointment.manager.why_not_bookable(
                self.exampleTooOldTime, self.exampleMachine, user),
            11,  # Unsupported time
        )
        unsavedTooOldAppointment = Appointment.from_reference(
            self.exampleTooOldReference, user)
        self.assertEqual(self.exampleTooOldReference, Appointment(
            time=self.exampleTooOldTime, machine=self.exampleMachine,
            user=user).reference)
        self.assertEqual(unsavedTooOldAppointment.time, self.exampleTooOldTime)
        self.assertEqual(unsavedTooOldAppointment.machine, self.exampleMachine)
        self.assertEqual(
            unsavedTooOldAppointment.user.username, self.exampleUserName)
        self.assertEqual(
            unsavedTooOldAppointment.reference, self.exampleTooOldReference)
        self.assertEqual(
            Appointment.manager.why_not_bookable(
                self.exampleTime, self.exampleBrokenMachine, user),
            21,  # Machine out of service
        )

    def test_make_appointment(self):
        user = User.objects.get(username=self.exampleUserName)
        god, _ = WashUser.objects.get_or_create_god()
        appointment = Appointment.manager.make_appointment(
            self.exampleTime, self.exampleMachine, user)
        reference = appointment.reference
        self.assertEqual(
            Appointment.manager.why_not_bookable(
                self.exampleTime, self.exampleMachine, god.user),
            41,  # Appointment taken
        )
        with self.assertRaises(AppointmentError) as ae:
            Appointment.manager.make_appointment(
                self.exampleTime, self.exampleMachine, user)
        self.assertEqual(ae.exception.reason, 41)
        appointment.cancel()
        self.assertEqual(
            appointment,
            Appointment.manager.filter_for_reference(reference).get())
        WashParameters.objects.update_value('bonus-method', 'empty')
        self.assertTrue(Appointment.manager.bookable(
            self.exampleTime, self.exampleMachine, user))
        with self.assertRaises(payment.PaymentError):
            Appointment.manager.make_appointment(
                self.exampleTime, self.exampleMachine, user)

    def test_use(self):
        user = User.objects.get(username=self.exampleUserName)
        appointment = Appointment.manager.make_appointment(
            self.exampleTime, self.exampleMachine, user)
        appointment.use()
        with self.assertRaises(AppointmentError) as ae:
            appointment.use()
        self.assertEqual(ae.exception.reason, 61)  # Appointment already used
        with self.assertRaises(AppointmentError) as ae:
            appointment.rebook()
        self.assertEqual(ae.exception.reason, 41)  # Appointment taken
        with self.assertRaises(AppointmentError) as ae:
            appointment.cancel()
        self.assertEqual(ae.exception.reason, 61)  # Appointment already used
        self.assertTrue(appointment.wasUsed)

    def test_bonuspayment(self):
        bpay = bonuspayment.BonusPayment()
        WashParameters.objects.update_value('bonus-method', 'bonus')
        WashParameters.objects.get(name='bonus-method').save()
        user = User.objects.get(username=self.exampleUserName)
        account = facade.Account.objects.create(
                primary_user=user, name='{}-bonus'.format(user.username))
        self.assertEqual(account, bpay.bonus_account_of(user))
        with self.assertRaises(payment.PaymentError):
            appointment = Appointment.manager.make_appointment(
                self.exampleTime, self.exampleMachine, user)
        price = int(WashParameters.objects.get_value('price'))
        self.assertFalse(account == bpay.bonus_source)
        god, _ = WashUser.objects.get_or_create_god()
        bpay.award_bonus(price, user, authorized_by=god.user)
        self.assertEqual(price, bpay.coverage(price, user))
        appointment = Appointment.manager.make_appointment(
            self.exampleTime, self.exampleMachine, user)
        self.assertEqual(0, bpay.coverage(price, user))
        appointment.cancel()
        self.assertEqual(price, bpay.coverage(price, user))

    def test_auto_refund(self):
        user = User.objects.get(username=self.exampleUserName)
        appmt1 = Appointment.manager.make_appointment(
            self.exampleTime, self.exampleMachine, user)
        appmt3 = Appointment.manager.make_appointment(
            self.exampleTime, self.lastMachine, user)
        self.assertIsNotNone(appmt1.refundableTransaction)
        self.assertIsNotNone(appmt3.refundableTransaction)
        appmt1refundableTransaction = appmt1.refundableTransaction
        appmt3.use()
        Appointment.manager.auto_refund_all()
        # self.assertIsNone(appmt1.refundableTransaction)
        self.assertTrue(
                appmt1.transactions.filter(
                    pk=appmt1refundableTransaction.pk
                    ).exists())
        self.assertIsNone(appmt3.refundableTransaction)
