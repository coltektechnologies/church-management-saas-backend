from rest_framework import permissions


class IsPlatformAdminOrChurchUser(permissions.BasePermission):
    """
    Platform admins can access everything
    Church users can only access their church data
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Platform admins have full access
        if request.user.is_platform_admin:
            return True

        # Regular users must belong to a church
        return request.user.church is not None


class IsPlatformAdmin(permissions.BasePermission):
    """Only platform administrators"""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_platform_admin
        )
