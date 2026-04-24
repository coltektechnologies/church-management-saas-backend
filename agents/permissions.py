from rest_framework import permissions


class IsPlatformStaffOrAgentCaller(permissions.BasePermission):
    """
    Allow platform admins, Django staff, or superusers to ingest agent telemetry.
    Matches typical churchagents JWT (platform admin service account).
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        u = request.user
        return bool(
            getattr(u, "is_platform_admin", False) or u.is_staff or u.is_superuser
        )
