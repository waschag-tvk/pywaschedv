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
    exampleTime = datetime.datetime(2015, 12, 12)
    exampleMachine = tvkutils.get_or_create_machines()[0][0]

    def setUp(self):
        tvkutils.setup()
        WashUser.objects.create_enduser(self.exampleUserName, isActivated=True)

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
