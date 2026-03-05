from django.contrib.auth.backends import ModelBackend
from django.db.models import Q

from .models import User


class SafeModelBackend(ModelBackend):
    """
    Wrapper around ModelBackend that catches MultipleObjectsReturned.
    Needed because User allows same email across different churches (unique per church),
    but ModelBackend looks up by email only, which can match multiple users.
    """

    def authenticate(self, request, **kwargs):
        try:
            return super().authenticate(request, **kwargs)
        except User.MultipleObjectsReturned:
            return None


class ChurchAuthBackend(ModelBackend):
    """
    Custom authentication backend for church-based multi-tenant system.
    Allows login with email and optional church_id.
    """

    def authenticate(
        self,
        request,
        email=None,
        password=None,
        church_id=None,
        username=None,
        **kwargs
    ):
        """
        Authenticate user by email and password.
        Accepts both email= and username= (Django admin sends username).
        For regular users, church_id is required.
        For platform admins, church_id is not needed.
        """
        email = (email or username or "").strip().lower()
        if not email or password is None:
            return None

        try:
            if church_id:
                # Regular user - must match church (unique per church)
                user = User.objects.get(Q(email__iexact=email) & Q(church_id=church_id))
            else:
                # Admin/API login without church_id
                # Platform admin first, else staff, else first match (same email in multiple churches)
                qs = User.objects.filter(email__iexact=email)
                user = qs.filter(is_platform_admin=True).first()
                if not user:
                    user = qs.filter(is_staff=True).first()
                if not user:
                    user = qs.first()
                if not user:
                    raise User.DoesNotExist()

            if user.check_password(password):
                return user

        except User.DoesNotExist:
            User().set_password(password)
            return None

        return None

    def get_user(self, user_id):
        """Get user by ID"""
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
