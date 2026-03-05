import logging

from django.conf import settings
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

logger = logging.getLogger(__name__)


class TwilioService:
    """Service for handling Twilio SMS and WhatsApp messaging"""

    def __init__(self):
        # Use test credentials in development
        if settings.DEBUG:
            # These are Twilio test credentials that work with test numbers
            self.account_sid = "AC00000000000000000000000000000001"  # Test Account SID
            self.auth_token = "00000000000000000000000000000001"  # Test Auth Token
            self.phone_number = "+15005550006"  # Test phone number that always works
            self.test_mode = True
        else:
            self.account_sid = settings.TWILIO_ACCOUNT_SID
            self.auth_token = settings.TWILIO_AUTH_TOKEN
            self.phone_number = settings.TWILIO_PHONE_NUMBER
            self.test_mode = False

        self.messaging_service_sid = getattr(
            settings, "TWILIO_MESSAGING_SERVICE_SID", None
        )
        self.client = Client(self.account_sid, self.auth_token)

    def send_sms(self, to_phone, message_body):
        """
        Send an SMS message using Twilio

        Args:
            to_phone (str): Recipient phone number in E.164 format (e.g., +1234567890)
            message_body (str): The message content to send

        Returns:
            dict: Dictionary containing success status and message details or error information
        """
        try:
            # Prepare message parameters
            message_params = {
                "body": message_body,
                "from_": self.phone_number,
                "to": to_phone,
            }

            # Only add status_callback if BASE_URL is set and not localhost
            if hasattr(settings, "BASE_URL") and "localhost" not in settings.BASE_URL:
                message_params["status_callback"] = (
                    f"{settings.BASE_URL}/api/notifications/twilio/status"
                )

            message = self.client.messages.create(**message_params)

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
            logger.error(f"Twilio SMS sending failed: {str(e)}")
            return {
                "success": False,
                "message_sid": None,
                "status": "failed",
                "to": to_phone,
                "from": self.phone_number,
                "body": message_body,
                "error_code": e.code,
                "error_message": str(e),
            }

    def send_whatsapp(self, to_phone, message_body, media_urls=None):
        """
        Send a WhatsApp message using Twilio

        Args:
            to_phone (str): Recipient phone number in E.164 format with 'whatsapp:' prefix
            message_body (str): The message content to send
            media_urls (list, optional): List of media URLs to include in the message

        Returns:
            dict: Dictionary containing success status and message details or error information
        """
        try:
            # Ensure the phone number has the whatsapp: prefix
            to_whatsapp = (
                f"whatsapp:{to_phone}"
                if not to_phone.startswith("whatsapp:")
                else to_phone
            )

            message_kwargs = {
                "body": message_body,
                "from_": f"whatsapp:{self.phone_number.lstrip('+')}",
                "to": to_whatsapp,
                "status_callback": f"{settings.BASE_URL}/api/notifications/twilio/status",
            }

            if media_urls:
                message_kwargs["media_url"] = media_urls

            message = self.client.messages.create(**message_kwargs)

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
            logger.error(f"Twilio WhatsApp sending failed: {str(e)}")
            return {
                "success": False,
                "message_sid": None,
                "status": "failed",
                "to": to_phone,
                "from": f"whatsapp:{self.phone_number}",
                "body": message_body,
                "error_code": e.code,
                "error_message": str(e),
            }

    def send_verification_email(self, to_email, template_sid, template_data):
        """
        Send a verification email using Twilio SendGrid

        Args:
            to_email (str): Recipient email address
            template_sid (str): Twilio SendGrid template ID
            template_data (dict): Dynamic data for the email template

        Returns:
            dict: Dictionary containing success status and message details or error information
        """
        try:
            message = self.client.verify.v2.services(
                settings.TWILIO_VERIFY_SERVICE_SID
            ).verifications.create(
                to=to_email,
                channel="email",
                custom_fid=template_sid,
                custom_fields=template_data,
            )

            return {
                "success": True,
                "sid": message.sid,
                "status": message.status,
                "to": to_email,
                "channel": message.channel,
                "error_code": None,
                "error_message": None,
            }

        except TwilioRestException as e:
            logger.error(f"Twilio email verification failed: {str(e)}")
            return {
                "success": False,
                "sid": None,
                "status": "failed",
                "to": to_email,
                "channel": "email",
                "error_code": e.code,
                "error_message": str(e),
            }

    def check_verification(self, to_email, code):
        """
        Verify an email verification code

        Args:
            to_email (str): The email address that received the verification code
            code (str): The verification code to check

        Returns:
            dict: Dictionary containing verification status
        """
        try:
            verification_check = self.client.verify.v2.services(
                settings.TWILIO_VERIFY_SERVICE_SID
            ).verification_checks.create(to=to_email, code=code)

            return {
                "success": verification_check.status == "approved",
                "status": verification_check.status,
                "valid": verification_check.valid,
                "error_code": None,
                "error_message": None,
            }

        except TwilioRestException as e:
            logger.error(f"Twilio verification check failed: {str(e)}")
            return {
                "success": False,
                "status": "failed",
                "valid": False,
                "error_code": e.code,
                "error_message": str(e),
            }
