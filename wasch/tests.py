import datetime
from django.test import TestCase
from django.contrib.auth.models import (
    User,
)
from wasch.models import (
    Appointment,
    WashUser,
    StatusRights,  # not a model
)
from wasch import tvkutils


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
    exampleTooOldTime = datetime.datetime(1991, 12, 25)
    exampleMachine, exampleBrokenMachine, lastMachine = \
        tvkutils.get_or_create_machines()[0]

    def setUp(self):
        tvkutils.setup()
        self.exampleMachine.isAvailable = True  # though this is default
        self.exampleMachine.save()
        self.exampleBrokenMachine.isAvailable = False
        self.exampleMachine.save()
        WashUser.objects.create_enduser(self.exampleUserName, isActivated=True)
        WashUser.objects.create_enduser(
            self.examplePoorUserName, isActivated=False)

    def _createExample(self):
        user = User.objects.get(username=self.exampleUserName)
        return Appointment.objects.create(
            time=self.exampleTime, machine=self.exampleMachine, user=user,
            wasUsed=False)

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
        self.assertEqual(
            Appointment.manager.why_not_bookable(
                self.exampleTime, self.exampleMachine, poorUser),
            31,  # User not active
        )
        self.assertTrue(Appointment.manager.bookable(
            self.exampleTime, self.exampleMachine, user))
        self.assertEqual(
            Appointment.manager.why_not_bookable(
                self.exampleTooOldTime, self.exampleMachine, user),
            11,  # Unsupported time
        )
        self.assertEqual(
            Appointment.manager.why_not_bookable(
                self.exampleTime, self.exampleBrokenMachine, user),
            21,  # Machine out of service
        )
