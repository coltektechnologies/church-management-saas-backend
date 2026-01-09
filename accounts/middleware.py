from django.utils.deprecation import MiddlewareMixin


class ChurchContextMiddleware(MiddlewareMixin):
    """
    Attach current church to request based on:
    1. Platform admin can access all churches
    2. Regular users limited to their church
    """

    def process_request(self, request):
        request.current_church = None

        if hasattr(request, "user") and request.user.is_authenticated:
            if request.user.is_platform_admin:
                # Platform admins can access all churches
                # Church can be set via query param or header
                church_id = request.GET.get("church_id") or request.headers.get(
                    "X-Church-ID"
                )
                if church_id:
                    from accounts.models import Church

                    try:
                        request.current_church = Church.objects.get(id=church_id)
                    except Church.DoesNotExist:
                        pass
            else:
                # Regular users limited to their church
                request.current_church = request.user.church
