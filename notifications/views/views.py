from django.db.models import Count, Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from members.models import Member
from notifications.models import (EmailLog, Notification, NotificationBatch,
                                  NotificationPreference, NotificationTemplate,
                                  RecurringNotificationSchedule, SMSLog)
from notifications.serializers import (EmailLogSerializer,
                                       NotificationBatchSerializer,
                                       NotificationCreateSerializer,
                                       NotificationPreferenceSerializer,
                                       NotificationSerializer,
                                       NotificationTemplateSerializer,
                                       RecurringNotificationScheduleSerializer,
                                       SendBulkNotificationSerializer,
                                       SendEmailSerializer, SendSMSSerializer,
                                       SMSLogSerializer)
from notifications.services import (EmailService, NotificationService,
                                    SMSService, TemplateService)

# ==========================================
# NOTIFICATION VIEWSET
# ==========================================


class NotificationViewSet(viewsets.ModelViewSet):
    """
    In-app notification management

    list: GET /api/notifications/
    create: POST /api/notifications/
    retrieve: GET /api/notifications/{id}/
    """

    permission_classes = [IsAuthenticated]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["is_read", "priority", "category", "status"]
    search_fields = ["title", "message"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Get notifications for current user"""
        # Handle schema generation case
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()

        user = self.request.user
        return Notification.objects.filter(user=user).select_related("church")

    def get_serializer_class(self):
        if self.action == "create":
            return NotificationCreateSerializer
        return NotificationSerializer

    @swagger_auto_schema(
        operation_description="Get list of notifications for current user",
        manual_parameters=[
            openapi.Parameter("is_read", openapi.IN_QUERY, type=openapi.TYPE_BOOLEAN),
            openapi.Parameter("priority", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter("category", openapi.IN_QUERY, type=openapi.TYPE_STRING),
        ],
        responses={200: NotificationSerializer(many=True)},
        tags=["Notifications"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Create a new notification",
        request_body=NotificationCreateSerializer,
        responses={201: NotificationSerializer()},
        tags=["Notifications"],
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        notification = serializer.save()

        output_serializer = NotificationSerializer(
            notification, context={"request": request}
        )
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["put"])
    @swagger_auto_schema(
        operation_description="Mark notification as read",
        responses={200: NotificationSerializer()},
        tags=["Notifications"],
    )
    def read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()

        notification = NotificationService.mark_as_read(notification.id, request.user)

        if notification:
            serializer = NotificationSerializer(
                notification, context={"request": request}
            )
            return Response(serializer.data)

        return Response(
            {"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND
        )

    @action(detail=False, methods=["put"])
    @swagger_auto_schema(
        operation_description="Mark all notifications as read",
        responses={
            200: openapi.Response(
                description="Success",
                examples={
                    "application/json": {"message": "5 notifications marked as read"}
                },
            )
        },
        tags=["Notifications"],
    )
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        count = NotificationService.mark_all_read(request.user)

        return Response(
            {
                "message": f"{count} notification{'s' if count != 1 else ''} marked as read"
            }
        )

    @action(detail=False, methods=["get"])
    @swagger_auto_schema(
        operation_description="Get unread notification count",
        responses={
            200: openapi.Response(
                description="Unread count",
                examples={"application/json": {"unread_count": 5}},
            )
        },
        tags=["Notifications"],
    )
    def unread_count(self, request):
        """Get unread notification count"""
        count = NotificationService.get_unread_count(request.user)

        return Response({"unread_count": count})

    @action(detail=False, methods=["delete"])
    @swagger_auto_schema(
        operation_description="Delete all read notifications",
        responses={204: "Deleted"},
        tags=["Notifications"],
    )
    def clear_read(self, request):
        """Delete all read notifications"""
        count = Notification.objects.filter(user=request.user, is_read=True).delete()[0]

        return Response(
            {"message": f"{count} read notifications deleted"},
            status=status.HTTP_204_NO_CONTENT,
        )


# ==========================================
# NOTIFICATION PREFERENCES
# ==========================================


class NotificationPreferenceView(APIView):
    """Manage user notification preferences"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get user notification preferences",
        responses={200: NotificationPreferenceSerializer()},
        tags=["Notifications"],
    )
    def get(self, request):
        """Get or create preferences"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=request.user
        )

        serializer = NotificationPreferenceSerializer(preferences)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Update notification preferences",
        request_body=NotificationPreferenceSerializer,
        responses={200: NotificationPreferenceSerializer()},
        tags=["Notifications"],
    )
    def put(self, request):
        """Update preferences"""
        preferences, created = NotificationPreference.objects.get_or_create(
            user=request.user
        )

        serializer = NotificationPreferenceSerializer(
            preferences, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# NOTIFICATION TEMPLATES
# ==========================================


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """Notification template management"""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationTemplateSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["template_type", "category", "is_active"]
    search_fields = ["name", "message"]

    def get_queryset(self):
        """Get notification templates for current user's church"""
        # Handle schema generation case
        if getattr(self, "swagger_fake_view", False):
            return NotificationTemplate.objects.none()

        user = self.request.user
        church = user.church
        return NotificationTemplate.objects.filter(
            Q(church=church) | Q(is_system_template=True)
        )

    @swagger_auto_schema(
        operation_description="Get list of notification templates",
        responses={200: NotificationTemplateSerializer(many=True)},
        tags=["Notifications"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(
        operation_description="Create notification template",
        request_body=NotificationTemplateSerializer,
        responses={201: NotificationTemplateSerializer()},
        tags=["Notifications"],
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)


# ==========================================
# SMS MANAGEMENT
# ==========================================


class SMSViewSet(viewsets.ReadOnlyModelViewSet):
    """SMS log viewing"""

    permission_classes = [IsAuthenticated]
    serializer_class = SMSLogSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "gateway"]
    search_fields = ["phone_number", "message"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Handle schema generation case
        if getattr(self, "swagger_fake_view", False):
            return SMSLog.objects.none()

        user = self.request.user
        church = user.church

        if user.is_platform_admin:
            church_id = self.request.query_params.get("church_id")
            if church_id:
                return SMSLog.objects.filter(church_id=church_id)
            return SMSLog.objects.all()

        return SMSLog.objects.filter(church=church)

    @swagger_auto_schema(
        operation_description="Get SMS logs",
        responses={200: SMSLogSerializer(many=True)},
        tags=["Notifications"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class SendSMSView(APIView):
    """Send individual SMS"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Send SMS message",
        request_body=SendSMSSerializer,
        responses={201: SMSLogSerializer()},
        tags=["Notifications"],
    )
    def post(self, request):
        serializer = SendSMSSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        church = request.current_church or request.user.church
        from accounts.notification_utils import church_can_use_sms_email

        if not church_can_use_sms_email(church, allow_initial_admin=False):
            return Response(
                {
                    "detail": "SMS notifications are not available on the FREE plan. Upgrade to send SMS."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        member = None
        if serializer.validated_data.get("member_id"):
            try:
                member = Member.objects.get(
                    id=serializer.validated_data["member_id"], church=church
                )
            except Member.DoesNotExist:
                pass

        sms_log = SMSService.send_sms(
            church=church,
            phone_number=serializer.validated_data["phone_number"],
            message=serializer.validated_data["message"],
            member=member,
            scheduled_for=serializer.validated_data.get("scheduled_for"),
        )

        output_serializer = SMSLogSerializer(sms_log)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


# ==========================================
# EMAIL MANAGEMENT
# ==========================================


class EmailViewSet(viewsets.ReadOnlyModelViewSet):
    """Email log viewing"""

    permission_classes = [IsAuthenticated]
    serializer_class = EmailLogSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "gateway"]
    search_fields = ["email_address", "subject"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Handle schema generation case
        if getattr(self, "swagger_fake_view", False):
            return EmailLog.objects.none()

        user = self.request.user
        church = user.church

        if user.is_platform_admin:
            church_id = self.request.query_params.get("church_id")
            if church_id:
                return EmailLog.objects.filter(church_id=church_id)
            return EmailLog.objects.all()

        return EmailLog.objects.filter(church=church)

    @swagger_auto_schema(
        operation_description="Get email logs",
        responses={200: EmailLogSerializer(many=True)},
        tags=["Notifications"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class SendEmailView(APIView):
    """Send individual email"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Send email message",
        request_body=SendEmailSerializer,
        responses={201: EmailLogSerializer()},
        tags=["Notifications"],
    )
    def post(self, request):
        serializer = SendEmailSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        church = request.current_church or request.user.church
        from accounts.notification_utils import church_can_use_sms_email

        if not church_can_use_sms_email(church, allow_initial_admin=False):
            return Response(
                {
                    "detail": "Email notifications are not available on the FREE plan. Upgrade to send emails."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        member = None
        if serializer.validated_data.get("member_id"):
            try:
                member = Member.objects.get(
                    id=serializer.validated_data["member_id"], church=church
                )
            except Member.DoesNotExist:
                pass

        email_log = EmailService.send_email(
            church=church,
            email_address=serializer.validated_data["email_address"],
            subject=serializer.validated_data["subject"],
            message_html=serializer.validated_data["message_html"],
            member=member,
            scheduled_for=serializer.validated_data.get("scheduled_for"),
        )

        output_serializer = EmailLogSerializer(email_log)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


# ==========================================
# BULK NOTIFICATIONS
# ==========================================


class BulkNotificationView(APIView):
    """Send bulk notifications"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Send bulk notification to multiple recipients",
        request_body=SendBulkNotificationSerializer,
        responses={
            201: openapi.Response(
                description="Batch created",
                examples={
                    "application/json": {
                        "message": "Notification batch created successfully",
                        "batch_id": "uuid-here",
                        "total_recipients": 150,
                    }
                },
            )
        },
        tags=["Notifications"],
    )
    def post(self, request):
        serializer = SendBulkNotificationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        church = request.current_church or request.user.church
        from accounts.notification_utils import church_can_use_sms_email

        wants_sms = serializer.validated_data.get("send_sms", False)
        wants_email = serializer.validated_data.get("send_email", False)
        if (wants_sms or wants_email) and not church_can_use_sms_email(
            church, allow_initial_admin=False
        ):
            return Response(
                {
                    "detail": "SMS and email notifications are not available on the FREE plan. Upgrade to send notifications."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Create notification batch
        batch = NotificationBatch.objects.create(
            church=church,
            name=f"Bulk notification - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
            message=serializer.validated_data["message"],
            target_all_members=serializer.validated_data["target"] == "all_members",
            target_departments=serializer.validated_data.get("department_ids"),
            target_members=serializer.validated_data.get("member_ids"),
            send_sms=serializer.validated_data.get("send_sms", False),
            send_email=serializer.validated_data.get("send_email", False),
            send_in_app=serializer.validated_data.get("send_in_app", True),
            created_by=request.user,
        )

        # Queue batch for processing (using Celery)
        from .tasks import process_notification_batch

        process_notification_batch.delay(str(batch.id))

        return Response(
            {
                "message": "Notification batch created successfully",
                "batch_id": str(batch.id),
                "status": "queued",
            },
            status=status.HTTP_201_CREATED,
        )


class NotificationBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """View notification batches"""

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationBatchSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Handle schema generation case
        if getattr(self, "swagger_fake_view", False):
            return NotificationBatch.objects.none()

        user = self.request.user
        church = user.church

        if user.is_platform_admin:
            church_id = self.request.query_params.get("church_id")
            if church_id:
                return NotificationBatch.objects.filter(church_id=church_id)
            return NotificationBatch.objects.all()

        return NotificationBatch.objects.filter(church=church)

    @swagger_auto_schema(
        operation_description="Get notification batches",
        responses={200: NotificationBatchSerializer(many=True)},
        tags=["Notifications"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


# ==========================================
# RECURRING NOTIFICATION SCHEDULES (GOOGLE MEET–STYLE)
# ==========================================


class RecurringNotificationScheduleViewSet(viewsets.ModelViewSet):
    """
    CRUD for recurring notification schedules.
    Frequency: daily, weekly (specific weekdays), monthly (day of month), yearly (date).
    A Celery beat task runs every 5 minutes and sends when next_run_at <= now.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RecurringNotificationScheduleSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["is_active", "frequency"]
    ordering = ["next_run_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RecurringNotificationSchedule.objects.none()
        user = self.request.user
        church = getattr(user, "church", None)
        if not church:
            return RecurringNotificationSchedule.objects.none()
        if getattr(user, "is_platform_admin", False):
            church_id = self.request.query_params.get("church_id")
            if church_id:
                return RecurringNotificationSchedule.objects.filter(church_id=church_id)
            return RecurringNotificationSchedule.objects.all()
        return RecurringNotificationSchedule.objects.filter(church=church)

    def perform_create(self, serializer):
        church = getattr(self.request.user, "church", None)
        if not church:
            raise ValidationError("User has no church.")
        serializer.save(church=church, created_by=self.request.user)

    @swagger_auto_schema(
        operation_description="List recurring notification schedules",
        responses={200: RecurringNotificationScheduleSerializer(many=True)},
        tags=["Notifications"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


# ==========================================
# TEST NOTIFICATION
# ==========================================


class TestNotificationView(APIView):
    """Send test notification"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Send test notification to yourself",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "channel": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=["in_app", "sms", "email"],
                    example="in_app",
                ),
                "message": openapi.Schema(
                    type=openapi.TYPE_STRING, example="This is a test notification"
                ),
            },
        ),
        responses={200: "Test notification sent"},
        tags=["Notifications"],
    )
    def post(self, request):
        channel = request.data.get("channel", "in_app")
        message = request.data.get("message", "This is a test notification")

        church = request.current_church or request.user.church
        from accounts.notification_utils import church_can_use_sms_email

        if channel in ("sms", "email") and not church_can_use_sms_email(
            church, allow_initial_admin=False
        ):
            return Response(
                {
                    "detail": "SMS and email notifications are not available on the FREE plan. Upgrade to send notifications."
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if channel == "in_app":
            NotificationService.create_notification(
                church=church,
                user=request.user,
                title="Test Notification",
                message=message,
                priority="MEDIUM",
                category="GENERAL",
            )
            return Response({"message": "Test in-app notification sent"})

        elif channel == "sms" and request.user.phone:
            SMSService.send_sms(
                church=church, phone_number=request.user.phone, message=message
            )
            return Response({"message": f"Test SMS sent to {request.user.phone}"})

        elif channel == "email" and request.user.email:
            EmailService.send_email(
                church=church,
                email_address=request.user.email,
                subject="Test Email from Church Management System",
                message_html=f"<p>{message}</p>",
            )
            return Response({"message": f"Test email sent to {request.user.email}"})

        return Response(
            {"error": "Invalid channel or missing contact information"},
            status=status.HTTP_400_BAD_REQUEST,
        )
