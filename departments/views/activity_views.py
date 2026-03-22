"""
Department Activity (event) API.
List/create/update/delete activities with upcoming/past filter and optional notifications.
"""

from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models.base_models import AuditLog

from ..models import DepartmentActivity
from ..serializers import DepartmentActivitySerializer
from ..services.activity_notifications import (NOTIFY_TO_ALL_CHURCH,
                                               NOTIFY_TO_DEPARTMENT,
                                               NOTIFY_TO_SPECIFIC,
                                               send_activity_notifications)


class DepartmentActivityViewSet(viewsets.ModelViewSet):
    """
    Department activities (events): title, date, time, location, description.
    Filter by ?time_filter=upcoming|past for list.
    Optional: notify department members, all church, or specific members via email/SMS on create.
    """

    permission_classes = []
    serializer_class = DepartmentActivitySerializer

    def get_permissions(self):
        return [IsAuthenticated()]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return DepartmentActivity.objects.none()
        qs = DepartmentActivity.objects.filter(deleted_at__isnull=True).select_related(
            "department", "church", "created_by"
        )
        user = self.request.user
        if not getattr(user, "is_platform_admin", False):
            qs = qs.filter(church=user.church)
        department_pk = self.kwargs.get("department_pk")
        if department_pk:
            qs = qs.filter(department_id=department_pk)
        return qs.order_by("-start_date", "-start_time")

    def filter_queryset_by_time(self, queryset):
        time_filter = self.request.query_params.get("time_filter", "").strip().lower()
        now = timezone.now()
        today = now.date()
        if time_filter == "upcoming":
            return queryset.filter(end_date__gte=today)
        if time_filter == "past":
            return queryset.filter(end_date__lt=today)
        return queryset

    @swagger_auto_schema(
        operation_description="List department activities. Use time_filter=upcoming|past.",
        manual_parameters=[
            openapi.Parameter(
                "time_filter",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["upcoming", "past"],
                description="Filter by upcoming or past (based on end_date/time)",
            ),
        ],
        tags=["Department Activities"],
    )
    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        qs = self.filter_queryset_by_time(qs)
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create activity. Optionally send notifications.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["title", "start_date", "end_date", "status"],
            properties={
                "title": openapi.Schema(type=openapi.TYPE_STRING),
                "description": openapi.Schema(type=openapi.TYPE_STRING),
                "status": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["UPCOMING", "ONGOING", "PAST"],
                ),
                "start_date": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                "end_date": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                "start_time": openapi.Schema(type=openapi.TYPE_STRING, format="time"),
                "end_time": openapi.Schema(type=openapi.TYPE_STRING, format="time"),
                "location": openapi.Schema(type=openapi.TYPE_STRING),
                "notify_to": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["department_members", "all_church", "specific_members"],
                    description="Who to notify (optional)",
                ),
                "member_ids": openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(type=openapi.TYPE_STRING, format="uuid"),
                    description="When notify_to=specific_members",
                ),
                "send_email": openapi.Schema(type=openapi.TYPE_BOOLEAN, default=True),
                "send_sms": openapi.Schema(type=openapi.TYPE_BOOLEAN, default=False),
            },
        ),
        tags=["Department Activities"],
    )
    def create(self, request, *args, **kwargs):
        # Nested: set department from URL if present
        department_pk = kwargs.get("department_pk")
        # Extract notification options from request (don't pass to serializer)
        notify_to = request.data.pop("notify_to", None)
        member_ids = request.data.pop("member_ids", None)
        send_email = request.data.pop("send_email", True)
        send_sms = request.data.pop("send_sms", False)
        if department_pk:
            request.data["department"] = department_pk

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        activity = serializer.save()
        activity._request_user = request.user

        # Audit log for activity feed
        try:
            AuditLog.log(
                user=request.user,
                action="CREATE",
                instance=activity,
                request=request,
                description=f"Activity created: {activity.title} ({activity.department.name})",
            )
        except Exception:
            pass

        # Optional notifications
        notification_result = {}
        if notify_to in (
            NOTIFY_TO_DEPARTMENT,
            NOTIFY_TO_ALL_CHURCH,
            NOTIFY_TO_SPECIFIC,
        ):
            notification_result = send_activity_notifications(
                activity,
                notify_to=notify_to,
                member_ids=member_ids,
                send_email=send_email,
                send_sms=send_sms,
            )

        response_serializer = self.get_serializer(activity)
        data = response_serializer.data
        if notification_result:
            data["notification"] = notification_result
        return Response(data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        activity = serializer.instance
        activity._request_user = self.request.user
        try:
            AuditLog.log(
                user=self.request.user,
                action="UPDATE",
                instance=activity,
                request=self.request,
                description=f"Activity updated: {activity.title} ({activity.department.name})",
            )
        except Exception:
            pass

    def perform_destroy(self, instance):
        instance.deleted_at = timezone.now()
        instance.save()
        try:
            AuditLog.log(
                user=self.request.user,
                action="DELETE",
                instance=instance,
                request=self.request,
                description=f"Activity deleted: {instance.title}",
            )
        except Exception:
            pass
