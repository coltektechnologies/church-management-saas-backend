"""
Notification service facades.

`notifications.services` is this package. The church-scoped orchestration (SMSLog / EmailLog,
in-app Notification helpers) lives in ``notifications.dispatch`` and is re-exported here so
``from notifications.services import SMSService, EmailService`` matches the API used by views
and tasks.

Low-level helpers remain importable as submodules, e.g. ``notifications.services.sms_service``.
"""

from notifications.dispatch import (
    EmailService,
    NotificationService,
    SMSService,
    TemplateService,
)

from .email_service import EmailService as SimpleEmailService
from .notification_service import NotificationService as TwilioNotificationService
from .sms_service import MNotifySMS
from .twilio_service import TwilioService

__all__ = [
    "EmailService",
    "MNotifySMS",
    "NotificationService",
    "SimpleEmailService",
    "SMSService",
    "TemplateService",
    "TwilioNotificationService",
    "TwilioService",
]
