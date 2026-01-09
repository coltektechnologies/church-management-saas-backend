from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

User = get_user_model()


class ChurchEmailBackend(BaseBackend):
    """
    Authenticate using email + password + church (for regular users)
    OR just email + password (for platform admins)
    """

    def authenticate(
        self, request, email=None, password=None, church_id=None, **kwargs
    ):
        if email is None or password is None:
            return None

        try:
            # Try platform admin first (no church required)
            user = User.objects.filter(
                email=email, is_active=True, is_platform_admin=True
            ).first()

            if user and user.check_password(password):
                return user

            # If not platform admin, church_id is required
            if church_id is None:
                return None

            # Regular church user
            user = User.objects.get(
                email=email,
                church_id=church_id,
                is_active=True,
                is_platform_admin=False,
            )

            if user.check_password(password):
                return user

        except User.DoesNotExist:
            return None

        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
