import logging

from django.conf import settings
from django.utils import timezone
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling various types of notifications"""

    def __init__(self):
        self.twilio_client = Client(
            settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN
        )

    def send_sms(self, to_phone, message_body, **kwargs):
        """
        Send an SMS message

        Args:
            to_phone (str): Recipient phone number in E.164 format
            message_body (str): The message content
            **kwargs: Additional arguments for future use

        Returns:
            dict: Result of the operation
        """
        try:
            message = self.twilio_client.messages.create(
                body=message_body,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to_phone,
                status_callback=f"{settings.BASE_URL}/api/notifications/twilio/status",
            )

            return {
                "success": True,
                "message_sid": message.sid,
                "status": message.status,
                "to": message.to,
                "from": message.from_,
                "body": message.body,
                "error_code": None,
                "error_message": None,
            }

        except TwilioRestException as e:
            logger.error(f"Failed to send SMS to {to_phone}: {str(e)}")
            return {
                "success": False,
                "message_sid": None,
                "status": "failed",
                "to": to_phone,
                "from": settings.TWILIO_PHONE_NUMBER,
                "body": message_body,
                "error_code": e.code,
                "error_message": str(e),
            }
