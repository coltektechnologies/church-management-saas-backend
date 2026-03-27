"""
JWT authentication with church platform-access enforcement.
"""

from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.constants import CHURCH_PLATFORM_DISABLED_MESSAGE
from accounts.models import Church


class ChurchAwareJWTAuthentication(JWTAuthentication):
    """
    After a valid JWT is accepted, block church users when the tenant is disabled
    by platform admins. Platform admins (no tenant restriction) are not blocked.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, validated_token = result
        if getattr(user, "is_platform_admin", False):
            return user, validated_token
        church_id = getattr(user, "church_id", None)
        if not church_id:
            return user, validated_token
        if not Church.objects.filter(
            pk=church_id, platform_access_enabled=True
        ).exists():
            raise exceptions.AuthenticationFailed(
                CHURCH_PLATFORM_DISABLED_MESSAGE,
                code="church_platform_disabled",
            )
        return user, validated_token
