import crypt
from django.contrib.auth.models import User
from django.conf import settings
import requests
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


class KasseBackend:
    def authenticate(self, request, username=None, password=None):
        token_request_data = {}
        if username is not None:
            token_request_data['username'] = username
        if password is not None:
            token_request_data['password'] = password
        try:
            token_json = requests.post(
                settings.KASSE_TOKEN_URL, data=token_request_data
                ).json()
        except requests.ConnectionError:
            # TODO show some error
            return None
        token = token_json.get('token')
        # TODO save the token in database
        print('token ' + token)
        if token is None:
            return None
        washuser = WashUser.objects.create_enduser(
            username, isActivated=False)
        return washuser.user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
