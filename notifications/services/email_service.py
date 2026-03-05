import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailService:
    """Service for handling email notifications"""

    def __init__(self):
        self.default_from_email = settings.DEFAULT_FROM_EMAIL

    def send_email(
        self,
        to_email,
        subject,
        template_name=None,
        context=None,
        html_message=None,
        plain_message=None,
    ):
        """
        Send an email using Django's send_mail

        Args:
            to_email (str|list): Email address(es) to send to
            subject (str): Email subject
            template_name (str, optional): Path to email template
            context (dict, optional): Context for template rendering
            html_message (str, optional): HTML content of the email
            plain_message (str, optional): Plain text content of the email

        Returns:
            dict: Result of the operation
        """
        try:
            if template_name and context is not None:
                html_message = render_to_string(template_name, context)
                plain_message = strip_tags(html_message)

            if not (html_message or plain_message):
                raise ValueError(
                    "Either template_name or message content must be provided"
                )

            send_mail(
                subject=subject,
                message=plain_message,
                html_message=html_message,
                from_email=self.default_from_email,
                recipient_list=[to_email] if isinstance(to_email, str) else to_email,
                fail_silently=False,
            )

            return {
                "success": True,
                "to": to_email,
                "subject": subject,
                "error_message": None,
            }

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return {
                "success": False,
                "to": to_email,
                "subject": subject,
                "error_message": str(e),
            }
