from django.urls import include, path
from rest_framework.routers import DefaultRouter

# Import views from the views module
from .views import (BulkNotificationView, EmailViewSet,
                    NotificationBatchViewSet, NotificationPreferenceView,
                    NotificationTemplateViewSet, NotificationViewSet,
                    RecurringNotificationScheduleViewSet, SendEmailView,
                    SendSMSView, SMSViewSet, TestNotificationView,
                    TwilioWebhookView, twilio_status_webhook)

app_name = "notifications"

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"templates", NotificationTemplateViewSet, basename="template")
router.register(r"sms-logs", SMSViewSet, basename="sms-log")
router.register(r"email-logs", EmailViewSet, basename="email-log")
router.register(r"batches", NotificationBatchViewSet, basename="batch")
router.register(
    r"recurring-schedules",
    RecurringNotificationScheduleViewSet,
    basename="recurring-schedule",
)

urlpatterns = [
    # Router endpoints
    path("", include(router.urls)),
    # Preferences
    path("preferences/", NotificationPreferenceView.as_view(), name="preferences"),
    # Send messages
    path("send-sms/", SendSMSView.as_view(), name="send-sms"),
    path("send-email/", SendEmailView.as_view(), name="send-email"),
    path("send-bulk/", BulkNotificationView.as_view(), name="send-bulk"),
    # Test
    path("test/", TestNotificationView.as_view(), name="test"),
    # Twilio Webhooks
    path("twilio/status/", TwilioWebhookView.as_view(), name="twilio-status-webhook"),
    path("twilio/legacy-status/", twilio_status_webhook, name="twilio-legacy-status"),
]
