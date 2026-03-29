import logging

from django.conf import settings
from django.utils import timezone

from accounts.notification_utils import church_can_use_sms_email

from .models import EmailLog, Notification, NotificationTemplate, SMSLog

logger = logging.getLogger(__name__)


class NotificationService:
    """Main notification service"""

    @staticmethod
    def create_notification(
        church, user=None, member=None, title="", message="", **kwargs
    ):
        """Create in-app notification"""
        notification = Notification.objects.create(
            church=church,
            user=user,
            member=member,
            title=title,
            message=message,
            priority=kwargs.get("priority", "MEDIUM"),
            category=kwargs.get("category"),
            link=kwargs.get("link"),
            icon=kwargs.get("icon"),
            scheduled_for=kwargs.get("scheduled_for"),
        )

        # If not scheduled, mark as sent
        if not notification.scheduled_for:
            notification.status = "SENT"
            notification.sent_at = timezone.now()
            notification.save()

        return notification

    @staticmethod
    def mark_as_read(notification_id, user):
        """Mark notification as read"""
        try:
            notification = Notification.objects.get(id=notification_id, user=user)
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.status = "READ"
            notification.save()
            return notification
        except Notification.DoesNotExist:
            return None

    @staticmethod
    def mark_all_read(user):
        """Mark all notifications as read for a user"""
        count = Notification.objects.filter(user=user, is_read=False).update(
            is_read=True, read_at=timezone.now(), status="READ"
        )
        return count

    @staticmethod
    def get_unread_count(user):
        """Get unread notification count"""
        return Notification.objects.filter(
            user=user, is_read=False, status="SENT"
        ).count()


class SMSService:
    """SMS sending service"""

    @staticmethod
    def send_sms(church, phone_number, message, member=None, scheduled_for=None):
        """Send SMS message. FREE plan churches are blocked (except initial admin via credential_service)."""
        if not church_can_use_sms_email(church, allow_initial_admin=False):
            raise PermissionError("SMS notifications are not available for FREE plan")
        # Calculate SMS count (160 chars per SMS)
        message_length = len(message)
        sms_count = (message_length // 160) + 1

        # Create SMS log
        sms_log = SMSLog.objects.create(
            church=church,
            phone_number=phone_number,
            member=member,
            message=message,
            message_length=message_length,
            sms_count=sms_count,
            scheduled_for=scheduled_for,
        )

        # If not scheduled, send immediately
        if not scheduled_for:
            result = SMSService._send_via_gateway(sms_log)
            return result

        return sms_log

    @staticmethod
    def _resolve_sms_gateway():
        """Prefer explicit SMS_GATEWAY; otherwise use mNotify when an API key is set."""
        gateway = (getattr(settings, "SMS_GATEWAY", None) or "").strip().lower()
        if gateway:
            return gateway
        if getattr(settings, "MNOTIFY_API_KEY", None):
            return "mnotify"
        return "africastalking"

    @staticmethod
    def _send_via_gateway(sms_log):
        """Send SMS via configured gateway"""
        try:
            gateway = SMSService._resolve_sms_gateway()

            if gateway == "africastalking":
                return SMSService._send_via_africastalking(sms_log)
            elif gateway == "twilio":
                return SMSService._send_via_twilio(sms_log)
            elif gateway == "mnotify":
                return SMSService._send_via_mnotify(sms_log)
            else:
                # Fallback: mark as sent for testing
                sms_log.status = "SENT"
                sms_log.sent_at = timezone.now()
                sms_log.save()
                logger.info(
                    f"SMS (Test Mode): {sms_log.phone_number} - {sms_log.message}"
                )
                return sms_log

        except Exception as e:
            sms_log.status = "FAILED"
            sms_log.error_message = str(e)
            sms_log.save()
            logger.error(f"SMS Failed: {e}")
            return sms_log

    @staticmethod
    def _send_via_mnotify(sms_log):
        """Send via mNotify (Ghana / regional SMS)."""
        try:
            from notifications.services.sms_service import MNotifySMS

            client = MNotifySMS()
            result = client.send_quick_sms(
                recipients=[sms_log.phone_number], message=sms_log.message
            )
            err = (
                result.get("status") == "error" or result.get("code") == "request_error"
            )
            if err:
                sms_log.status = "FAILED"
                sms_log.error_message = str(
                    result.get("message") or result.get("error") or result
                )[:500]
            else:
                sms_log.status = "SENT"
                sms_log.sent_at = timezone.now()
                mid = result.get("id") or result.get("message_id")
                if mid:
                    sms_log.gateway_message_id = str(mid)[:100]
            sms_log.save()
            return sms_log
        except Exception as e:
            sms_log.status = "FAILED"
            sms_log.error_message = str(e)[:500]
            sms_log.save()
            logger.error("mNotify SMS error: %s", e)
            return sms_log

    @staticmethod
    def _send_via_africastalking(sms_log):
        """Send via Africa's Talking"""
        try:
            import africastalking

            username = getattr(settings, "AFRICASTALKING_USERNAME", "")
            api_key = getattr(settings, "AFRICASTALKING_API_KEY", "")

            if not username or not api_key:
                raise Exception("Africa's Talking credentials not configured")

            africastalking.initialize(username, api_key)
            sms = africastalking.SMS

            response = sms.send(sms_log.message, [sms_log.phone_number])

            if response["SMSMessageData"]["Recipients"]:
                recipient = response["SMSMessageData"]["Recipients"][0]
                sms_log.gateway_message_id = recipient.get("messageId")
                sms_log.status = "SENT"
                sms_log.delivery_status = recipient.get("status")
                sms_log.sent_at = timezone.now()
            else:
                sms_log.status = "FAILED"
                sms_log.error_message = "No recipients in response"

            sms_log.save()
            return sms_log

        except Exception as e:
            sms_log.status = "FAILED"
            sms_log.error_message = str(e)
            sms_log.save()
            logger.error(f"Africa's Talking Error: {e}")
            return sms_log

    @staticmethod
    def _send_via_twilio(sms_log):
        """Send via Twilio"""
        try:
            from twilio.rest import Client

            account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", "")
            auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", "")
            from_number = getattr(settings, "TWILIO_PHONE_NUMBER", "")

            if not account_sid or not auth_token or not from_number:
                raise Exception("Twilio credentials not configured")

            client = Client(account_sid, auth_token)

            message = client.messages.create(
                body=sms_log.message, from_=from_number, to=sms_log.phone_number
            )

            sms_log.gateway_message_id = message.sid
            sms_log.status = "SENT"
            sms_log.delivery_status = message.status
            sms_log.sent_at = timezone.now()
            sms_log.save()

            return sms_log

        except Exception as e:
            sms_log.status = "FAILED"
            sms_log.error_message = str(e)
            sms_log.save()
            logger.error(f"Twilio Error: {e}")
            return sms_log


class EmailService:
    """Email sending service"""

    @staticmethod
    def send_email(
        church,
        email_address,
        subject,
        message_html,
        member=None,
        message_plain=None,
        scheduled_for=None,
    ):
        """Send email message. FREE plan churches are blocked (except initial admin via credential_service)."""
        if not church_can_use_sms_email(church, allow_initial_admin=False):
            raise PermissionError("Email notifications are not available for FREE plan")
        # Create email log
        email_log = EmailLog.objects.create(
            church=church,
            email_address=email_address,
            member=member,
            subject=subject,
            message_html=message_html,
            message_plain=message_plain or message_html,
            scheduled_for=scheduled_for,
        )

        # If not scheduled, send immediately
        if not scheduled_for:
            result = EmailService._send_via_gateway(email_log)
            return result

        return email_log

    @staticmethod
    def _send_via_gateway(email_log):
        """Send email via configured gateway"""
        try:
            gateway = getattr(settings, "EMAIL_GATEWAY", "smtp")

            if gateway == "sendgrid":
                return EmailService._send_via_sendgrid(email_log)
            else:
                return EmailService._send_via_smtp(email_log)

        except Exception as e:
            email_log.status = "FAILED"
            email_log.error_message = str(e)
            email_log.save()
            logger.error(f"Email Failed: {e}")
            return email_log

    @staticmethod
    def _send_via_smtp(email_log):
        """Send via Django SMTP"""
        try:
            from django.core.mail import send_mail

            send_mail(
                subject=email_log.subject,
                message=email_log.message_plain,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email_log.email_address],
                html_message=email_log.message_html,
                fail_silently=False,
            )

            email_log.status = "SENT"
            email_log.sent_at = timezone.now()
            email_log.save()

            return email_log

        except Exception as e:
            email_log.status = "FAILED"
            email_log.error_message = str(e)
            email_log.save()
            logger.error(f"SMTP Error: {e}")
            return email_log

    @staticmethod
    def _send_via_sendgrid(email_log):
        """Send via SendGrid"""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail

            sg_api_key = getattr(settings, "SENDGRID_API_KEY", "")

            if not sg_api_key:
                raise Exception("SendGrid API key not configured")

            message = Mail(
                from_email=settings.DEFAULT_FROM_EMAIL,
                to_emails=email_log.email_address,
                subject=email_log.subject,
                html_content=email_log.message_html,
            )

            sg = SendGridAPIClient(sg_api_key)
            response = sg.send(message)

            email_log.gateway_message_id = response.headers.get("X-Message-Id")
            email_log.status = "SENT"
            email_log.sent_at = timezone.now()
            email_log.save()

            return email_log

        except Exception as e:
            email_log.status = "FAILED"
            email_log.error_message = str(e)
            email_log.save()
            logger.error(f"SendGrid Error: {e}")
            return email_log


class TemplateService:
    """Template rendering service"""

    @staticmethod
    def render_template(template, context):
        """Render template with context variables"""
        message = template.message

        for key, value in context.items():
            placeholder = "{" + key + "}"
            message = message.replace(placeholder, str(value))

        return message

    @staticmethod
    def get_default_templates():
        """Get system default templates"""
        return [
            {
                "name": "Service Reminder",
                "category": "REMINDER",
                "template_type": "SMS",
                "message": "Hello {name}, worship with us tomorrow at {time}. Theme: {theme}. See you there!",
            },
            {
                "name": "Birthday Greeting",
                "category": "BIRTHDAY",
                "template_type": "SMS",
                "message": "Happy Birthday {name}! May God bless you abundantly. - {church_name} Family",
            },
            {
                "name": "Event Reminder",
                "category": "EVENT",
                "template_type": "SMS",
                "message": "Reminder: {event_name} on {date} at {time}. Location: {venue}",
            },
        ]
