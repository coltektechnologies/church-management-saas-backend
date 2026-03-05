from functools import wraps

from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .models import ChurchGroupMember, RolePermission, UserRole


def get_effective_role_ids(user, church):
    """
    Get all role IDs for user at church: from direct UserRole + from ChurchGroup membership.
    """
    role_ids = set(
        UserRole.objects.filter(user=user, church=church, is_active=True).values_list(
            "role_id", flat=True
        )
    )
    # Add roles from groups (user in group → group has role)
    group_role_ids = ChurchGroupMember.objects.filter(
        user=user, group__church=church
    ).values_list("group__role_id", flat=True)
    role_ids.update(group_role_ids)
    return role_ids


def has_permission(user, permission_code, church=None):
    """
    Check if user has a specific permission.

    Args:
        user: User instance
        permission_code: Permission code string (e.g., 'MEMBERS.VIEW')
        church: Church instance (optional, defaults to user's church)

    Returns:
        bool: True if user has permission, False otherwise
    """
    # Platform admins have all permissions
    if user.is_platform_admin:
        return True

    # Use user's church if not specified
    if church is None:
        church = user.church

    if not church:
        return False

    role_ids = get_effective_role_ids(user, church)
    if not role_ids:
        return False

    return RolePermission.objects.filter(
        role_id__in=role_ids, permission__code=permission_code
    ).exists()


def has_any_permission(user, permission_codes, church=None):
    """
    Check if user has any of the specified permissions.

    Args:
        user: User instance
        permission_codes: List of permission code strings
        church: Church instance (optional)

    Returns:
        bool: True if user has at least one permission, False otherwise
    """
    for perm_code in permission_codes:
        if has_permission(user, perm_code, church):
            return True
    return False


def has_all_permissions(user, permission_codes, church=None):
    """
    Check if user has all of the specified permissions.

    Args:
        user: User instance
        permission_codes: List of permission code strings
        church: Church instance (optional)

    Returns:
        bool: True if user has all permissions, False otherwise
    """
    for perm_code in permission_codes:
        if not has_permission(user, perm_code, church):
            return False
    return True


def require_permission(permission_code):
    """
    Decorator to require a specific permission for a view function.

    Usage:
        @require_permission('MEMBERS.CREATE')
        def create_member(request):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not has_permission(request.user, permission_code):
                raise PermissionDenied(f"Permission required: {permission_code}")
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


def require_any_permission(*permission_codes):
    """
    Decorator to require any of the specified permissions.

    Usage:
        @require_any_permission('MEMBERS.VIEW', 'MEMBERS.CREATE')
        def member_view(request):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not has_any_permission(request.user, permission_codes):
                raise PermissionDenied(
                    f"One of these permissions required: {', '.join(permission_codes)}"
                )
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


# REST Framework Permission Classes


class HasPermission(BasePermission):
    """
    DRF permission class to check for specific permission.

    Usage:
        class MyView(APIView):
            permission_classes = [HasPermission]
            required_permission = 'MEMBERS.VIEW'
    """

    required_permission = None

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        permission_code = getattr(view, "required_permission", self.required_permission)
        if not permission_code:
            return True  # No permission required

        return has_permission(request.user, permission_code)


class HasAnyPermission(BasePermission):
    """
    DRF permission class to check for any of the specified permissions.

    Usage:
        class MyView(APIView):
            permission_classes = [HasAnyPermission]
            required_permissions = ['MEMBERS.VIEW', 'MEMBERS.CREATE']
    """

    required_permissions = []

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        permission_codes = getattr(
            view, "required_permissions", self.required_permissions
        )
        if not permission_codes:
            return True

        return has_any_permission(request.user, permission_codes)


class IsPlatformAdmin(BasePermission):
    """
    DRF permission class to allow only platform admins.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.is_platform_admin
        )


class IsChurchAdmin(BasePermission):
    """
    DRF permission class to allow church admins (staff users).
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class BelongsToChurch(BasePermission):
    """
    DRF permission class to ensure user belongs to a church.
    """

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.church is not None
        )


class IsActiveSubscription(BasePermission):
    """
    DRF permission class to check if church has active subscription.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Platform admins bypass subscription check
        if request.user.is_platform_admin:
            return True

        church = request.user.church
        if not church:
            return False

        # Check if trial is active or subscription is active
        if church.status == "TRIAL":
            return church.is_trial_active
        elif church.status == "ACTIVE":
            return church.is_subscription_active

        return False


def get_user_permissions(user, church=None):
    """
    Get all permission codes for a user.

    Args:
        user: User instance
        church: Church instance (optional)

    Returns:
        set: Set of permission codes
    """
    # Platform admins have all permissions
    if user.is_platform_admin:
        from .models import Permission

        return set(Permission.objects.values_list("code", flat=True))

    # Use user's church if not specified
    if church is None:
        church = user.church

    if not church:
        return set()

    role_ids = get_effective_role_ids(user, church)
    if not role_ids:
        return set()

    permissions = RolePermission.objects.filter(role_id__in=role_ids).values_list(
        "permission__code", flat=True
    )
    return set(permissions)


def check_role_level(user, required_level, church=None):
    """
    Check if user has a role with level equal to or lower than required_level.
    Lower level numbers = higher privileges (1 = highest, 5 = lowest).

    Args:
        user: User instance
        required_level: Integer (1-5)
        church: Church instance (optional)

    Returns:
        bool: True if user has sufficient role level
    """
    # Platform admins have level 0 (highest)
    if user.is_platform_admin:
        return True

    # Use user's church if not specified
    if church is None:
        church = user.church

    if not church:
        return False

    role_ids = get_effective_role_ids(user, church)
    if not role_ids:
        return False

    from .models import Role

    roles = Role.objects.filter(id__in=role_ids)
    min_level = min(r.level for r in roles)
    return min_level <= required_level
