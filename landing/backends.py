from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    """Permite autenticação com e-mail ou username."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        try:
            if '@' in username:
                user = User.objects.get(email=username)
            else:
                user = User.objects.get(username=username)
        except User.DoesNotExist:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
