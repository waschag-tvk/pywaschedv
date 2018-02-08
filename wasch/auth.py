import crypt
from django.contrib.auth.models import User
from wasch.models import WashUser


class GodOnlyBackend:
    god_username = 'WaschRoss'

    @classmethod
    def get_or_create_god(cls, create_washgod=True):
        try:
            god = User.objects.get(username=cls.god_username)
            was_created = False
        except User.DoesNotExist:
            god = User.create(
                username=cls.god_username,
                is_staff=True,
                is_superuser=True,
            )
            was_created = True
        if create_washgod and not WashUser.objects.filter(user=god).exists():
            washgod = WashUser(
                user=GodOnlyBackend.god, isActivated=True, status=9)
            washgod.save()
        return god, was_created

    def authenticate(self, request, username=None, password=None):
        if username == self.god_username \
                and crypt.crypt(password, 'waschpulver') == 'waxudoXH6TLm.':
            god, _ = self.get_or_create_god()
            return god
        else:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
