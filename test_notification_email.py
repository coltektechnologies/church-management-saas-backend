import os

import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "church_saas.settings")
django.setup()

from accounts.models import User
from members.models import Member
from notifications.models import Church, EmailLog, NotificationTemplate


def test_notification_email():
    try:
        # Get or create test church
        church = Church.objects.first()
        if not church:
            print("No church found. Please create a church first.")
            return

        # Get or create a test member with email
        member = Member.objects.filter(location__isnull=False).first()
        if not member:
            print(
                "No member with location found. Please create a member with email first."
            )
            return

        email = (
            member.location.email
            if hasattr(member, "location") and member.location
            else None
        )
        if not email:
            print("Member has no email address. Please update member's email first.")
            return

        # Create a test email log with both plain and HTML content
        subject = "Test Notification Email"
        message_plain = "This is a test email from the notification system."
        message_html = f"""
        <html>
            <body>
                <h1>Test Notification Email</h1>
                <p>This is a test email from the notification system.</p>
                <p>Sent to: {email}</p>
            </body>
        </html>
        """

        email_log = EmailLog.objects.create(
            church=church,
            email_address=email,
            member=member,
            subject=subject,
            message_plain=message_plain,
            message_html=message_html,
            status="PENDING",
            gateway="smtp",  # Using SMTP as per your settings
            has_attachments=False,
            attachment_urls=[],
        )

        print(f"Created EmailLog with ID: {email_log.id}")

        # Try to send the email
        from notifications.services.email_service import EmailService

        email_service = EmailService()
        result = email_service.send_email(
            to_email=email,
            subject=email_log.subject,
            plain_message=email_log.message_plain,
            html_message=email_log.message_html,
        )

        # Update the email log
        if result.get("success"):
            email_log.status = "SENT"
            email_log.sent_at = django.utils.timezone.now()
            email_log.gateway_message_id = result.get("message_id")
            print("Email sent successfully!")
        else:
            email_log.status = "FAILED"
            email_log.error_message = result.get("error", "Unknown error")
            print(f"Failed to send email: {email_log.error_message}")

        email_log.save()

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_notification_email()
