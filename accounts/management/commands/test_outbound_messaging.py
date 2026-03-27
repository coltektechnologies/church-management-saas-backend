"""
Verify SMTP and mNotify from the same environment as the running app.

Examples:
  python manage.py test_outbound_messaging --email=you@gmail.com --phone=233549361771
  python manage.py test_outbound_messaging --email=test@example.com --skip-sms
  python manage.py test_outbound_messaging --phone=0549361771 --skip-email
"""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Send a test email (SMTP) and/or SMS (mNotify) to validate configuration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            help="Address to receive the test email (required unless --skip-email)",
        )
        parser.add_argument(
            "--phone",
            type=str,
            help="Phone for test SMS (Ghana/local or E.164; required unless --skip-sms)",
        )
        parser.add_argument(
            "--skip-email",
            action="store_true",
            help="Do not send email",
        )
        parser.add_argument(
            "--skip-sms",
            action="store_true",
            help="Do not send SMS",
        )

    def handle(self, *args, **options):
        email = (options.get("email") or "").strip()
        phone = (options.get("phone") or "").strip()
        skip_email = options["skip_email"]
        skip_sms = options["skip_sms"]

        if not skip_email and not email:
            self.stderr.write(self.style.ERROR("Provide --email or use --skip-email"))
            return
        if not skip_sms and not phone:
            self.stderr.write(self.style.ERROR("Provide --phone or use --skip-sms"))
            return

        if not skip_email:
            self.stdout.write(
                f"SMTP backend={settings.EMAIL_BACKEND} host={getattr(settings, 'EMAIL_HOST', '')}"
            )
            try:
                send_mail(
                    subject="[Church SaaS] Test email — outbound SMTP OK",
                    message=(
                        "If you received this, Django SMTP settings work from this host.\n"
                        "Fix Errno 101 (network unreachable) by allowing outbound port 587 "
                        "or use an HTTPS email API provider."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(f"Email: sent to {email}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Email: FAILED — {e}"))

        if not skip_sms:
            if not getattr(settings, "MNOTIFY_API_KEY", ""):
                self.stdout.write(
                    self.style.WARNING(
                        "SMS: skipped — MNOTIFY_API_KEY is empty in environment"
                    )
                )
            else:
                from notifications.services.mnotify_service import MNotifyService

                svc = MNotifyService()
                msg = (
                    "Church SaaS test SMS: mNotify is configured. "
                    "Reply not required."
                )
                try:
                    result = svc.send_sms(to_phone=phone, message=msg)
                    if result.get("success"):
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"SMS: queued/sent to {phone} (id={result.get('message_id')})"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.ERROR(
                                f"SMS: FAILED — {result.get('error', result)}"
                            )
                        )
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"SMS: FAILED — {e}"))

        self.stdout.write("Done.")
