import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from accounts.models import Church, User
from notifications.services.notification_manager import NotificationManager
from notifications.services.twilio_service import TwilioService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Test Twilio integration by sending a test message"

    def add_arguments(self, parser):
        parser.add_argument(
            "--phone", type=str, help="Phone number to send test SMS to (E.164 format)"
        )
        parser.add_argument(
            "--email", type=str, help="Email address to send test email to"
        )
        parser.add_argument("--church", type=str, help="Church ID or name")
        parser.add_argument(
            "--whatsapp", action="store_true", help="Send as WhatsApp message"
        )

    def handle(self, *args, **options):
        # Get or create a test church if not specified
        church = None
        if options["church"]:
            try:
                if options["church"].isdigit():
                    church = Church.objects.get(id=int(options["church"]))
                else:
                    church = Church.objects.filter(
                        name__icontains=options["church"]
                    ).first()
            except Church.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(f"Church not found: {options['church']}")
                )
                return

        if not church:
            church = Church.objects.first()
            if not church:
                self.stderr.write(
                    self.style.ERROR("No churches found. Please create a church first.")
                )
                return
            self.stdout.write(
                self.style.WARNING(f"No church specified. Using: {church.name}")
            )

        # Get or create a test user
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.create_superuser(
                username="admin",
                email="admin@example.com",
                password="admin123",
                church=church,
            )
            self.stdout.write(self.style.SUCCESS(f"Created test user: {user.email}"))

        # Initialize services
        twilio = TwilioService()
        notification_manager = NotificationManager()

        # Test SMS
        if options["phone"]:
            phone = options["phone"]
            if not phone.startswith("+"):
                phone = f"+{phone}"

            self.stdout.write(
                self.style.SUCCESS(
                    f"Sending test {'WhatsApp' if options['whatsapp'] else 'SMS'} to {phone}..."
                )
            )

            if options["whatsapp"]:
                result = twilio.send_whatsapp(
                    phone,
                    "🚀 This is a test WhatsApp message from your church management system!",
                )
            else:
                result = twilio.send_sms(
                    phone, "📱 This is a test SMS from your church management system!"
                )

            if result["success"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Message sent successfully! SID: {result['message_sid']}"
                    )
                )
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to send message: {result.get('error_message', 'Unknown error')}"
                    )
                )

        # Test Email
        if options["email"]:
            email = options["email"]
            self.stdout.write(self.style.SUCCESS(f"Sending test email to {email}..."))

            result = notification_manager.send_notification(
                church=church,
                notification_type="EMAIL",
                recipient=email,
                subject="Test Email from Church Management System",
                message_html="""
                <h1>Test Email</h1>
                <p>This is a test email from your church management system.</p>
                <p>If you're seeing this, email notifications are working correctly! 🎉</p>
                <p>Best regards,<br>Your Church Admin Team</p>
                """,
            )

            if result.get("success"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Email sent successfully! Log ID: {result.get('log_id')}"
                    )
                )
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f"Failed to send email: {result.get('error', 'Unknown error')}"
                    )
                )

        if not options["phone"] and not options["email"]:
            self.stdout.write(
                self.style.WARNING(
                    "No phone or email specified. Use --phone or --email to send a test message."
                )
            )
            self.stdout.write("\nExamples:")
            self.stdout.write("  python manage.py test_twilio --phone +1234567890")
            self.stdout.write("  python manage.py test_twilio --email test@example.com")
            self.stdout.write(
                "  python manage.py test_twilio --phone +1234567890 --whatsapp"
            )
            self.stdout.write(
                "  python manage.py test_twilio --church 'Your Church Name' --phone +1234567890"
            )
