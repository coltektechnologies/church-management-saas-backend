import logging
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.utils import timezone

from accounts.models import Church, User
from members.models import Member

from ..models import (EmailLog, Notification, NotificationBatch,
                      NotificationTemplate, SMSLog)
from .mnotify_service import MNotifyService
from .twilio_service import TwilioService

logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Centralized notification manager that handles all types of notifications
    using Twilio for SMS and email delivery.
    """

    def __init__(self):
        self.twilio = TwilioService()
        self.mnotify = MNotifyService()

    def send_notification(
        self,
        church: Church,
        notification_type: str,
        recipient: Union[User, Member, str],
        template_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Send a notification to a recipient using the specified template or direct content.

        Args:
            church: The church sending the notification
            notification_type: Type of notification (SMS, EMAIL, WHATSAPP, IN_APP)
            recipient: Can be a User, Member, or direct contact (email/phone)
            template_name: Optional template name to use
            context: Context variables for template rendering
            **kwargs: Additional parameters for the notification

        Returns:
            Dictionary with notification results
        """
        # Get or create template if provided
        template = None
        if template_name:
            template = self._get_template(church, template_name, notification_type)
            if not template:
                return {
                    "success": False,
                    "error": f"Template {template_name} not found",
                    "notification_type": notification_type,
                }

        # Prepare recipient details
        recipient_info = self._get_recipient_info(recipient)

        # Process based on notification type
        if notification_type.upper() in ["SMS", "WHATSAPP"]:
            return self._send_sms_notification(
                church=church,
                recipient=recipient_info,
                template=template,
                context=context,
                is_whatsapp=(notification_type.upper() == "WHATSAPP"),
                **kwargs,
            )

        elif notification_type.upper() == "EMAIL":
            return self._send_email_notification(
                church=church,
                recipient=recipient_info,
                template=template,
                context=context,
                **kwargs,
            )

        elif notification_type.upper() == "IN_APP":
            return self._send_in_app_notification(
                church=church,
                recipient=recipient_info,
                template=template,
                context=context,
                **kwargs,
            )

        return {
            "success": False,
            "error": f"Unsupported notification type: {notification_type}",
            "notification_type": notification_type,
        }

    def _get_template(
        self, church: Church, template_name: str, template_type: str
    ) -> Optional[NotificationTemplate]:
        """Get a notification template by name and type"""
        try:
            return NotificationTemplate.objects.get(
                name=template_name,
                template_type=template_type.upper(),
                church=church,
                is_active=True,
            )
        except NotificationTemplate.DoesNotExist:
            # Try to find a system template if no church-specific one exists
            try:
                return NotificationTemplate.objects.get(
                    name=template_name,
                    template_type=template_type.upper(),
                    is_system_template=True,
                    is_active=True,
                )
            except NotificationTemplate.DoesNotExist:
                return None

    def _get_recipient_info(
        self, recipient: Union[User, Member, str, Dict]
    ) -> Dict[str, Any]:
        """Extract recipient information from various input types"""
        if isinstance(recipient, dict):
            return recipient

        if hasattr(recipient, "email") and hasattr(recipient, "phone_number"):
            # Handle User or Member objects
            return {
                "id": recipient.id,
                "name": getattr(recipient, "get_full_name", lambda: "")()
                or str(recipient),
                "email": recipient.email,
                "phone": getattr(recipient, "phone_number", None),
                "user": recipient if isinstance(recipient, User) else None,
                "member": recipient if isinstance(recipient, Member) else None,
            }

        # Handle direct email or phone
        if "@" in str(recipient):
            return {"email": str(recipient)}

        return {"phone": str(recipient)}

    def _send_sms_notification(
        self,
        church: Church,
        recipient: Dict[str, Any],
        template: Optional[NotificationTemplate] = None,
        context: Optional[Dict[str, Any]] = None,
        is_whatsapp: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Send an SMS or WhatsApp notification

        For SMS, uses mNotify service
        For WhatsApp, falls back to Twilio
        """
        phone = recipient.get("phone")
        if not phone:
            return {
                "success": False,
                "error": "No phone number provided for recipient",
                "notification_type": "WHATSAPP" if is_whatsapp else "SMS",
            }

        # Ensure phone is a string and clean it up
        phone = str(phone).strip()
        if not phone:
            return {
                "success": False,
                "error": "Invalid phone number format",
                "notification_type": "WHATSAPP" if is_whatsapp else "SMS",
            }

        # Get message content from template or kwargs
        message = kwargs.get("message")
        if template:
            message = self._render_template(template, context or {})

        if not message:
            return {
                "success": False,
                "error": "No message content provided",
                "notification_type": "WHATSAPP" if is_whatsapp else "SMS",
            }

        # For WhatsApp, use Twilio
        if is_whatsapp:
            result = self.twilio.send_whatsapp(phone, message, kwargs.get("media_urls"))
            gateway = "TWILIO_WHATSAPP"
        else:
            # For SMS, use mNotify
            group_ids = kwargs.get("group_ids")  # Optional group IDs for mNotify
            result = self.mnotify.send_sms(phone, message, group_ids)
            gateway = "MNOTIFY"

        # Log the SMS
        sms_log = SMSLog.objects.create(
            church=church,
            phone_number=phone,
            member=recipient.get("member"),
            message=message,
            message_length=len(message),
            sms_count=(len(message) // 160) + 1,
            gateway=gateway,
            gateway_message_id=result.get("message_id") or result.get("message_sid"),
            status="SENT" if result.get("success") else "FAILED",
            error_message=result.get("error_message") or result.get("error"),
            scheduled_for=kwargs.get("scheduled_for"),
            direction="OUTBOUND",
        )

        if result.get("success") and not kwargs.get("scheduled_for"):
            sms_log.sent_at = timezone.now()
            sms_log.status = "SENT"
            sms_log.save()

        return {
            "success": result.get("success", False),
            "notification_type": "WHATSAPP" if is_whatsapp else "SMS",
            "log_id": str(sms_log.id),
            "message_id": result.get("message_id") or result.get("message_sid"),
            "error_message": result.get("error_message") or result.get("error"),
        }

    def _send_email_notification(
        self,
        church: Church,
        recipient: Dict[str, Any],
        template: Optional[NotificationTemplate] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send an email notification"""
        email = recipient.get("email")
        if not email:
            return {
                "success": False,
                "error": "No email address provided for recipient",
                "notification_type": "EMAIL",
            }

        # Get subject and message from template or kwargs
        subject = kwargs.get("subject", "")
        message_html = kwargs.get("message_html")
        message_plain = kwargs.get("message_plain")

        if template:
            subject = template.subject or subject
            message_html = self._render_template(template, context or {})
            message_plain = self._html_to_plain(message_html) if message_html else None

        if not message_html and not message_plain:
            return {
                "success": False,
                "error": "No message content provided",
                "notification_type": "EMAIL",
            }

        # Log the email
        email_log = EmailLog.objects.create(
            church=church,
            email_address=email,
            member=recipient.get("member"),
            user=recipient.get("user"),
            subject=subject,
            message_html=message_html,
            message_plain=message_plain,
            has_attachments=bool(kwargs.get("attachments")),
            attachment_urls=kwargs.get("attachments"),
            gateway="twilio_sendgrid",
            status="PENDING",
            scheduled_for=kwargs.get("scheduled_for"),
        )

        try:
            # For Twilio SendGrid, we'd typically use their Python library
            # This is a simplified example - in production, you'd use the actual SendGrid API
            if settings.EMAIL_BACKEND == "sendgrid_backend.SendgridBackend":
                from django.core.mail import EmailMultiAlternatives

                email_message = EmailMultiAlternatives(
                    subject=subject,
                    body=message_plain or "",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[email],
                    headers={
                        "X-SMTPAPI": json.dumps(
                            {
                                "unique_args": {
                                    "notification_id": str(email_log.id),
                                    "church_id": str(church.id),
                                }
                            }
                        )
                    },
                )

                if message_html:
                    email_message.attach_alternative(message_html, "text/html")

                # Attach files if any
                if kwargs.get("attachments"):
                    for attachment in kwargs["attachments"]:
                        # This is a placeholder - actual implementation would need to handle file attachments
                        pass

                # Send the email
                email_message.send()

                email_log.status = "SENT"
                email_log.sent_at = timezone.now()
                email_log.save()

                return {
                    "success": True,
                    "notification_type": "EMAIL",
                    "log_id": str(email_log.id),
                }
            else:
                # Fallback to Django's default email backend
                from django.core.mail import send_mail

                send_mail(
                    subject=subject,
                    message=message_plain or message_html,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    html_message=message_html,
                    fail_silently=False,
                )

                email_log.status = "SENT"
                email_log.sent_at = timezone.now()
                email_log.save()

                return {
                    "success": True,
                    "notification_type": "EMAIL",
                    "log_id": str(email_log.id),
                }

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            email_log.status = "FAILED"
            email_log.error_message = str(e)
            email_log.save()

            return {
                "success": False,
                "notification_type": "EMAIL",
                "error": str(e),
                "log_id": str(email_log.id),
            }

    def _send_in_app_notification(
        self,
        church: Church,
        recipient: Dict[str, Any],
        template: Optional[NotificationTemplate] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Send an in-app notification"""
        user = recipient.get("user")
        if not user:
            return {
                "success": False,
                "error": "No user provided for in-app notification",
                "notification_type": "IN_APP",
            }

        # Get notification details from template or kwargs
        title = kwargs.get("title", "")
        message = kwargs.get("message")

        if template:
            title = template.subject or title
            message = self._render_template(template, context or {})

        if not message:
            return {
                "success": False,
                "error": "No message content provided",
                "notification_type": "IN_APP",
            }

        # Create the in-app notification
        notification = Notification.objects.create(
            church=church,
            user=user,
            member=recipient.get("member"),
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

        return {
            "success": True,
            "notification_type": "IN_APP",
            "notification_id": str(notification.id),
        }

    def _render_template(
        self, template: NotificationTemplate, context: Dict[str, Any]
    ) -> str:
        """Render a template with the given context"""
        from django.template import Context, Template

        try:
            template_obj = Template(template.message)
            return template_obj.render(Context(context))
        except Exception as e:
            logger.error(f"Failed to render template {template.name}: {str(e)}")
            return template.message  # Fallback to raw template

    @staticmethod
    def _html_to_plain(html: str) -> str:
        """Convert HTML to plain text"""
        import re
        from html.parser import HTMLParser

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html)

        # Convert HTML entities
        text = HTMLParser().unescape(text)

        # Normalize whitespace
        text = " ".join(text.split())

        return text

    def process_batch(self, batch_id: str) -> Dict[str, Any]:
        """Process a batch of notifications"""
        try:
            batch = NotificationBatch.objects.get(id=batch_id, status="PENDING")
        except NotificationBatch.DoesNotExist:
            return {
                "success": False,
                "error": f"Batch {batch_id} not found or not pending",
                "batch_id": batch_id,
            }

        # Update batch status
        batch.status = "PROCESSING"
        batch.started_at = timezone.now()
        batch.save()

        # Get recipients
        recipients = self._get_batch_recipients(batch)

        # Process each recipient
        success_count = 0
        failed_count = 0

        for recipient in recipients:
            try:
                # Determine notification type based on recipient and batch settings
                notification_type = self._determine_notification_type(batch, recipient)

                # Prepare context
                context = {
                    "recipient": recipient,
                    "church": batch.church,
                    "batch": batch,
                    "date": timezone.now().strftime("%Y-%m-%d"),
                }

                # Send notification
                result = self.send_notification(
                    church=batch.church,
                    notification_type=notification_type,
                    recipient=recipient,
                    template=batch.template,
                    context=context,
                    scheduled_for=batch.scheduled_for,
                    **{
                        "subject": batch.template.subject if batch.template else None,
                        "message": batch.message,
                        "priority": (
                            "HIGH" if batch.send_sms or batch.send_email else "MEDIUM"
                        ),
                    },
                )

                if result.get("success"):
                    success_count += 1
                else:
                    failed_count += 1
                    logger.error(
                        f'Failed to send notification to {recipient}: {result.get("error")}'
                    )

            except Exception as e:
                failed_count += 1
                logger.error(f"Error processing recipient {recipient}: {str(e)}")

        # Update batch status
        batch.status = "COMPLETED" if failed_count == 0 else "PARTIALLY_COMPLETED"
        batch.completed_at = timezone.now()
        batch.successful_count = success_count
        batch.failed_count = failed_count
        batch.save()

        return {
            "success": True,
            "batch_id": str(batch.id),
            "total_recipients": len(recipients),
            "success_count": success_count,
            "failed_count": failed_count,
        }

    def _get_batch_recipients(self, batch: NotificationBatch) -> List[Dict[str, Any]]:
        """Get recipients for a notification batch"""
        from members.models import Member

        recipients = []

        # Get members based on batch criteria
        if batch.target_all_members:
            members = Member.objects.filter(church=batch.church, is_active=True)
            for member in members:
                recipients.append(
                    {
                        "member": member,
                        "user": member.user,
                        "name": member.get_full_name(),
                        "email": member.email,
                        "phone": member.phone_number,
                    }
                )

        # Add specific members if specified
        if batch.target_members:
            member_ids = [m["id"] for m in batch.target_members if "id" in m]
            members = Member.objects.filter(
                id__in=member_ids, church=batch.church, is_active=True
            )
            for member in members:
                recipients.append(
                    {
                        "member": member,
                        "user": member.user,
                        "name": member.get_full_name(),
                        "email": member.email,
                        "phone": member.phone_number,
                    }
                )

        # Add department members if specified
        if batch.target_departments:
            from departments.models import DepartmentMember

            dept_members = DepartmentMember.objects.filter(
                department_id__in=batch.target_departments,
                member__church=batch.church,
                member__is_active=True,
            ).select_related("member")

            for dept_member in dept_members:
                member = dept_member.member
                recipients.append(
                    {
                        "member": member,
                        "user": member.user,
                        "name": member.get_full_name(),
                        "email": member.email,
                        "phone": member.phone_number,
                        "department": dept_member.department.name,
                    }
                )

        # Remove duplicates (in case a member is in multiple target groups)
        seen = set()
        unique_recipients = []

        for r in recipients:
            key = r.get("member") or r.get("user") or r.get("email") or r.get("phone")
            if key and key not in seen:
                seen.add(key)
                unique_recipients.append(r)

        return unique_recipients

    def _determine_notification_type(
        self, batch: NotificationBatch, recipient: Dict[str, Any]
    ) -> str:
        """Determine the best notification type for a recipient"""
        # Check recipient preferences if available
        if "user" in recipient and hasattr(
            recipient["user"], "notification_preferences"
        ):
            prefs = recipient["user"].notification_preferences

            if batch.send_email and prefs.enable_email:
                return "EMAIL"
            elif batch.send_sms and prefs.enable_sms:
                return "SMS"

        # Fall back to batch settings
        if batch.send_email and "email" in recipient and recipient["email"]:
            return "EMAIL"
        elif batch.send_sms and "phone" in recipient and recipient["phone"]:
            return "SMS"

        # Default to in-app if nothing else is available
        return "IN_APP"
