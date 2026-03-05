"""
REST API for activity feed. Church-scoped; platform admins can filter by church_id.
"""

from django.db.models import Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models.base_models import AuditLog
from core.serializers import ActivityFeedSerializer


def _church_for_request(request):
    """Church for filtering: church_id query (platform admin) or request.user.church."""
    if getattr(request.user, "is_platform_admin", False) and request.query_params.get(
        "church_id"
    ):
        return request.query_params.get("church_id")
    return getattr(request.user, "church_id", None)


class ActivityFeedPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class ActivityFeedAPIView(APIView):
    """
    GET /api/activity/
    List recent activity (audit log) for the current church.
    Query params: action, model_name, app_label, church_id (platform admin), page, page_size.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = ActivityFeedPagination

    @swagger_auto_schema(
        operation_description="List activity feed (audit log) for the current church. Filter by action, model_name, or app_label.",
        manual_parameters=[
            openapi.Parameter(
                "action",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Filter by action (e.g. CREATE, UPDATE, DELETE)",
            ),
            openapi.Parameter(
                "model_name",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Filter by model name (e.g. Member, IncomeTransaction)",
            ),
            openapi.Parameter(
                "app_label",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                description="Filter by app (e.g. members, treasury, departments)",
            ),
            openapi.Parameter(
                "church_id",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                format="uuid",
                description="Platform admin: filter by church",
            ),
            openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
            openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER),
        ],
        tags=["Activity Feed"],
    )
    def get(self, request):
        church_id = _church_for_request(request)
        if not church_id and not getattr(request.user, "is_platform_admin", False):
            return Response(
                {"error": "Church context required or use church_id as platform admin"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            AuditLog.objects.all()
            .select_related("user", "church")
            .order_by("-created_at")
        )

        if church_id:
            qs = qs.filter(church_id=church_id)
        else:
            # Platform admin without church_id: show all (or could restrict)
            pass

        action = request.query_params.get("action", "").strip()
        if action:
            qs = qs.filter(action=action)
        model_name = request.query_params.get("model_name", "").strip()
        if model_name:
            qs = qs.filter(model_name__iexact=model_name)
        app_label = request.query_params.get("app_label", "").strip().lower()
        if app_label:
            # Map app_label to model names we care about (optional: use ContentType)
            from django.apps import apps

            try:
                app_config = apps.get_app_config(app_label)
                model_names = [m.__name__ for m in app_config.get_models()]
                qs = qs.filter(model_name__in=model_names)
            except LookupError:
                qs = qs.none()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ActivityFeedSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class ActivityFeedByAppView(APIView):
    """
    GET /api/activity/<app_label>/
    Convenience endpoint: activity for one app (e.g. members, treasury, departments).
    """

    permission_classes = [IsAuthenticated]
    pagination_class = ActivityFeedPagination

    @swagger_auto_schema(
        operation_description="Activity feed for a specific app (e.g. members, treasury, departments, announcements, files).",
        manual_parameters=[
            openapi.Parameter("action", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "church_id", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="uuid"
            ),
        ],
        tags=["Activity Feed"],
    )
    def get(self, request, app_label):
        church_id = _church_for_request(request)
        if not church_id and not getattr(request.user, "is_platform_admin", False):
            return Response(
                {"error": "Church context required or use church_id as platform admin"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.apps import apps

        try:
            app_config = apps.get_app_config(app_label)
            model_names = [m.__name__ for m in app_config.get_models()]
        except LookupError:
            return Response(
                {"error": f"Unknown app: {app_label}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = (
            AuditLog.objects.filter(model_name__in=model_names)
            .select_related("user", "church")
            .order_by("-created_at")
        )
        if church_id:
            qs = qs.filter(church_id=church_id)
        action = request.query_params.get("action", "").strip()
        if action:
            qs = qs.filter(action=action)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        serializer = ActivityFeedSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
