import os

import django
from django.conf import settings
from django.core.mail import send_mail

from notifications.services.mnotify_service import MNotifyService


def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "church_saas.settings")
    django.setup()


def test_email():
    """Test email sending functionality"""
    try:
        subject = "Test Email from Church Management System"
        message = "This is a test email to verify email sending is working."
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = ["kyerematengcollins93@gmail.com"]

        print(f"Sending test email to {recipient_list}...")
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"Failed to send test email: {str(e)}")
        return False


def test_sms():
    """Test SMS sending functionality"""
    try:
        phone_number = "233244960999"  # Replace with your test number
        message = "Test SMS from Church Management System"

        print(f"Sending test SMS to {phone_number}...")
        sms_service = MNotifyService()
        result = sms_service.send_sms(to_phone=phone_number, message=message)

        if result.get("success", False):
            print("SMS sent successfully!")
            return True
        else:
            print(f"Failed to send SMS: {result.get('error', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"Error sending test SMS: {str(e)}")
        return False


if __name__ == "__main__":
    setup_django()

    print("=== Testing Email ===")
    email_success = test_email()

    print("\n=== Testing SMS ===")
    sms_success = test_sms()

    print("\n=== Test Results ===")
    print(f"Email: {'SUCCESS' if email_success else 'FAILED'}")
    print(f"SMS: {'SUCCESS' if sms_success else 'FAILED'}")
