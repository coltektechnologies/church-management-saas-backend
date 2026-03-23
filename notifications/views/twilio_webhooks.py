import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from twilio.request_validator import RequestValidator

from ..models import EmailLog, SMSLog

logger = logging.getLogger(__name__)


class TwilioWebhookView(APIView):
    """Handle Twilio webhook callbacks for message status updates"""

    authentication_classes = []
    permission_classes = [AllowAny]

    @csrf_exempt
    def post(self, request, *args, **kwargs):
        """Handle incoming Twilio webhook"""
        # Validate the request is from Twilio
        if not self._validate_twilio_request(request):
            return Response("Invalid Twilio request", status=status.HTTP_403_FORBIDDEN)

        # Get the message SID and status
        message_sid = request.data.get("MessageSid")
        message_status = request.data.get("MessageStatus")

        if not message_sid or not message_status:
            logger.warning("Missing MessageSid or MessageStatus in Twilio webhook")
            return Response(
                "Missing required parameters", status=status.HTTP_400_BAD_REQUEST
            )

        # Update the corresponding log entry
        updated = False

        # Check SMS logs
        sms_log = SMSLog.objects.filter(gateway_message_id=message_sid).first()
        if sms_log:
            sms_log.status = message_status.upper()

            if message_status in ["delivered", "sent"]:
                sms_log.delivered_at = timezone.now()
            elif message_status == "failed":
                sms_log.error_message = request.data.get(
                    "ErrorMessage", "Unknown error"
                )

            sms_log.save()
            updated = True

        # If not found in SMS logs, check email logs
        if not updated:
            email_log = EmailLog.objects.filter(gateway_message_id=message_sid).first()
            if email_log:
                email_log.status = message_status.upper()

                if message_status in ["delivered", "sent"]:
                    email_log.delivered_at = timezone.now()
                elif message_status == "failed":
                    email_log.error_message = request.data.get(
                        "ErrorMessage", "Unknown error"
                    )

                email_log.save()
                updated = True

        if not updated:
            logger.warning(f"No matching log found for message SID: {message_sid}")
            return Response(
                "No matching message found", status=status.HTTP_404_NOT_FOUND
            )

        return Response("Status updated", status=status.HTTP_200_OK)

    def _validate_twilio_request(self, request):
        """Validate that the request is from Twilio"""
        if not hasattr(settings, "TWILIO_AUTH_TOKEN") or not settings.TWILIO_AUTH_TOKEN:
            logger.warning("Twilio auth token not configured")
            return False

        # Get the X-Twilio-Signature header
        signature = request.headers.get("X-Twilio-Signature")
        if not signature:
            logger.warning("Missing X-Twilio-Signature header")
            return False

        # Get the full URL
        url = request.build_absolute_uri()

        # Get the POST data
        post_data = request.body.decode("utf-8")

        # Create the validator
        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)

        # Validate the request
        is_valid = validator.validate(url, post_data, signature)

        if not is_valid:
            logger.warning("Invalid Twilio request signature")

        return is_valid


@csrf_exempt
@require_http_methods(["POST"])
def twilio_status_webhook(request):
    """Legacy function-based webhook for Twilio status updates"""
    # This is a simplified version for backward compatibility
    try:
        message_sid = request.POST.get("MessageSid")
        message_status = request.POST.get("MessageStatus")

        if not message_sid or not message_status:
            return JsonResponse({"error": "Missing required parameters"}, status=400)

        # Update SMS log if found
        sms_log = SMSLog.objects.filter(gateway_message_id=message_sid).first()
        if sms_log:
            sms_log.status = message_status.upper()

            if message_status in ["delivered", "sent"]:
                sms_log.delivered_at = timezone.now()
            elif message_status == "failed":
                sms_log.error_message = request.POST.get(
                    "ErrorMessage", "Unknown error"
                )

            sms_log.save()
            return JsonResponse({"status": "updated"})

        return JsonResponse({"error": "Message not found"}, status=404)

    except Exception as e:
        logger.error(f"Error in Twilio status webhook: {str(e)}")
        return JsonResponse({"error": str(e)}, status=500)
