import os

import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "church_saas.settings")
django.setup()

from django.conf import settings
from django.core.mail import send_mail

from members.models import Member


def test_email():
    try:
        # Test sending a simple email
        send_mail(
            "Test Email from Church Management System",
            "This is a test email to verify email sending functionality.",
            settings.DEFAULT_FROM_EMAIL,
            ["kyerematengcollins93@gmail.com"],  # Replace with your test email
            fail_silently=False,
        )
        print("Test email sent successfully!")
        return True
    except Exception as e:
        print(f"Failed to send test email: {str(e)}")
        return False


if __name__ == "__main__":
    print("Testing email configuration...")
    success = test_email()
    if success:
        print("Email test successful! Check your inbox (and spam folder).")
    else:
        print("Email test failed. Check the error message above.")
