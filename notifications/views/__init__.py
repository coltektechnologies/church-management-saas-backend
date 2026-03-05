# Import all views to make them available when importing from notifications.views
# Import Twilio webhook views
from .twilio_webhooks import TwilioWebhookView, twilio_status_webhook
from .views import (BulkNotificationView, EmailViewSet,
                    NotificationBatchViewSet, NotificationPreferenceView,
                    NotificationTemplateViewSet, NotificationViewSet,
                    SendEmailView, SendSMSView, SMSViewSet,
                    TestNotificationView)

__all__ = [
    "NotificationViewSet",
    "NotificationPreferenceView",
    "NotificationTemplateViewSet",
    "SMSViewSet",
    "SendSMSView",
    "EmailViewSet",
    "SendEmailView",
    "BulkNotificationView",
    "NotificationBatchViewSet",
    "TestNotificationView",
    "TwilioWebhookView",
    "twilio_status_webhook",
]
