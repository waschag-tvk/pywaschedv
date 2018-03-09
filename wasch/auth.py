import crypt
from django.contrib.auth.models import User
from wasch.models import WashUser, GOD_NAME


class GodOnlyBackend:
    def authenticate(self, request, username=None, password=None):
        if username == GOD_NAME \
                and crypt.crypt(password, 'waschpulver') == 'waxudoXH6TLm.':
            washgod, _ = WashUser.objects.get_or_create_god()
            return washgod.user
        else:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
