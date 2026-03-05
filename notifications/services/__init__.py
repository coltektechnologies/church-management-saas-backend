# Import services to make them available when importing from notifications.services
from .email_service import EmailService
from .notification_service import NotificationService
from .sms_service import MNotifySMS
from .twilio_service import TwilioService

# For backward compatibility
NotificationService = NotificationService  # Alias for backward compatibility

# Set MNotifySMS as the default SMS service
SMSService = MNotifySMS


# Create a simple TemplateService class as a placeholder
class TemplateService:
    """Placeholder for template service functionality"""

    pass


__all__ = [
    "TwilioService",
    "NotificationService",
    "SMSService",
    "EmailService",
    "TemplateService",
]
