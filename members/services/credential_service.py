from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from accounts.notification_utils import church_can_use_sms_email
from notifications.services import SMSService


def send_credentials_email(recipient, email, password, allow_initial_admin=False):
    """Send login credentials via email.

    allow_initial_admin: If True, allow for FREE plan when sending to first admin during church setup.
    """
    church = getattr(recipient, "church", None)
    if not church_can_use_sms_email(church, allow_initial_admin=allow_initial_admin):
        return
    subject = f"Your {church.name} Login Credentials"
    context = {
        "member": recipient,
        "church": church,
        "email": email,
        "password": password,
        "login_url": settings.FRONTEND_LOGIN_URL,
        "has_password": bool(password),  # Add flag for password existence
    }

    message = render_to_string("emails/credentials_email.txt", context)
    html_message = render_to_string("emails/credentials_email.html", context)

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_message,
        fail_silently=False,
    )


def send_credentials_sms(
    recipient, phone_number, password=None, email=None, allow_initial_admin=False
):
    """Send login credentials via SMS using mNotify.

    allow_initial_admin: If True, allow for FREE plan when sending to first admin during church setup.
    """
    church = getattr(recipient, "church", None)
    if not church_can_use_sms_email(church, allow_initial_admin=allow_initial_admin):
        return {"success": False, "error": "SMS/email not available for FREE plan"}
    member = recipient
    try:
        from notifications.services.mnotify_service import MNotifyService

        # Initialize the mNotify service
        sms_service = MNotifyService()

        # Format the message (include church details)
        church_name = (
            getattr(member.church, "name", "Your Church")
            if getattr(member, "church", None)
            else "Your Church"
        )
        church_sub = (
            getattr(member.church, "subdomain", "")
            if getattr(member, "church", None)
            else ""
        )
        message = (
            f"Hello {member.first_name},\n"
            f"Your login for {church_name}"
            + (f" (subdomain: {church_sub})" if church_sub else "")
            + ":\n"
            f"Email: {email or 'Use your registered email'}\n"
            f"Username: {member.username}\n"
        )

        if password:
            message += f"Password: {password}\n"

        message += f"Login: {settings.FRONTEND_LOGIN_URL}"

        # Send the SMS
        result = sms_service.send_sms(to_phone=phone_number, message=message)

        # Log the result
        import logging

        logger = logging.getLogger(__name__)

        if result.get("success"):
            logger.info(f"SMS sent successfully to {phone_number}")
        else:
            logger.error(
                f"Failed to send SMS to {phone_number}: {result.get('error', 'Unknown error')}"
            )

        return result

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Error sending SMS to {phone_number}: {str(e)}")
        return {"success": False, "error": str(e)}


def send_credentials(
    user,
    password,
    notification_preference="email",
    request=None,
    allow_initial_admin=None,
):
    """Send login credentials to the user based on their notification preference.

    allow_initial_admin: If True, allow for FREE plan (first admin during church setup).
        If None, auto-detect: True when church has exactly 1 active user (the one we're sending to).
    """
    if allow_initial_admin is None and user.church:
        allow_initial_admin = user.church.users.filter(is_active=True).count() == 1
    elif allow_initial_admin is None:
        allow_initial_admin = False

    import logging

    logger = logging.getLogger(__name__)
    results = {}

    try:
        # Send email if requested
        if notification_preference in ["email", "both"] and user.email:
            try:
                send_credentials_email(
                    user, user.email, password, allow_initial_admin=allow_initial_admin
                )
                results["email_sent"] = True
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send email to {user.email}: {str(e)}")
                results["email_sent"] = False
                results["email_error"] = str(e)

        # Send SMS if requested and phone number exists
        if notification_preference in ["sms", "both"] and user.phone:
            try:
                send_credentials_sms(
                    user,
                    user.phone,
                    password,
                    user.email,
                    allow_initial_admin=allow_initial_admin,
                )
                results["sms_sent"] = True
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send SMS to {user.phone}: {str(e)}")
                results["sms_sent"] = False
                results["sms_error"] = str(e)

        # Check if at least one method was successful
        if (
            (notification_preference == "email" and results.get("email_sent", False))
            or (notification_preference == "sms" and results.get("sms_sent", False))
            or (
                notification_preference == "both"
                and (results.get("email_sent", False) or results.get("sms_sent", False))
            )
        ):
            return {"success": True}
        else:
            error_msg = "Failed to send credentials: "
            if notification_preference in ["email", "both"] and not results.get(
                "email_sent", True
            ):
                error_msg += (
                    f"Email failed: {results.get('email_error', 'Unknown error')}. "
                )
            if notification_preference in ["sms", "both"] and not results.get(
                "sms_sent", True
            ):
                error_msg += f"SMS failed: {results.get('sms_error', 'Unknown error')}"
            return {"success": False, "error": error_msg.strip()}

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error in send_credentials: {str(e)}")
        return {"success": False, "error": str(e)}
