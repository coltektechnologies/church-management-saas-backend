import os

import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "church_saas.settings")
django.setup()

from django.conf import settings
from django.core.mail import send_mail


def test_email_sending():
    try:
        # Test email
        subject = "Test Email from Church Management System"
        message = "This is a test email to verify SMTP settings."
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = ["kyerematengcollins93@gmail.com"]

        # Send the email
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {str(e)}")


if __name__ == "__main__":
    test_email_sending()
