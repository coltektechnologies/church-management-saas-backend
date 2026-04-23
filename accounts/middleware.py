from django.utils.deprecation import MiddlewareMixin


def _get_jwt_user(request):
    """
    Extract and validate the Bearer JWT token from the request before DRF runs.
    Returns the authenticated User or None.
    DRF authentication only fires inside view dispatch, so middleware sees
    request.user as AnonymousUser for JWT-authenticated API clients.
    """
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:].strip()
    if not token:
        return None
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication

        jwt_auth = JWTAuthentication()
        validated_token = jwt_auth.get_validated_token(token)
        return jwt_auth.get_user(validated_token)
    except Exception:
        return None


class ChurchContextMiddleware(MiddlewareMixin):
    """
    Attach current church to request based on:
    1. Platform admin can access all churches (pass church_id query param or X-Church-ID header)
    2. Regular users are limited to their own church

    Because DRF JWT authentication runs inside view dispatch — AFTER all middleware —
    we resolve the JWT Bearer token ourselves here so platform-admin agents can
    pass church_id correctly.
    """

    def process_request(self, request):
        request.current_church = None

        # Resolve the authenticated user: prefer Django session auth (already set),
        # fall back to parsing the JWT Bearer token.
        user = None
        if hasattr(request, "user") and request.user.is_authenticated:
            user = request.user
        else:
            user = _get_jwt_user(request)

        if user and user.is_authenticated:
            if user.is_platform_admin:
                # Platform admins can scope to any church via query param or header
                church_id = request.GET.get("church_id") or request.headers.get(
                    "X-Church-ID"
                )
                if church_id:
                    from accounts.models import Church

                    try:
                        request.current_church = Church.objects.get(id=church_id)
                    except (Church.DoesNotExist, Exception):
                        pass
            else:
                # Regular users are always scoped to their own church
                request.current_church = user.church
