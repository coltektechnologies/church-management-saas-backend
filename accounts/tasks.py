"""Celery tasks for accounts / registration background work."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def run_registration_credentials_delivery(
    user_id: str,
    password: str,
    notification_preference: str,
) -> None:
    """Send church-registration admin credentials (email/SMS). Safe to call from a thread or Celery worker."""
    from members.services.credential_service import send_credentials

    from .models import User

    try:
        admin_user = User.objects.select_related("church").get(pk=user_id)
        church = admin_user.church
        church_name = church.name if church else "unknown"

        outcome = send_credentials(
            admin_user,
            password,
            notification_preference=notification_preference,
            allow_initial_admin=True,
        )
        if outcome.get("success"):
            logger.info(
                "Registration credential delivery church=%s email_sent=%s sms_sent=%s",
                church_name,
                outcome.get("email_sent"),
                outcome.get("sms_sent"),
            )
            if outcome.get("email_sent") is False and outcome.get("sms_sent"):
                logger.warning(
                    "Registration email failed but SMS succeeded for church=%s; "
                    "check SMTP/network (e.g. Errno 101 unreachable from host).",
                    church_name,
                )
            if outcome.get("sms_sent") is False and outcome.get("email_sent"):
                logger.warning(
                    "Registration SMS failed but email succeeded for church=%s.",
                    church_name,
                )
        else:
            logger.warning(
                "Registration credentials not delivered for %s (church %s): %s",
                admin_user.email or admin_user.phone,
                church_name,
                outcome.get("error", "unknown"),
            )
    except User.DoesNotExist:
        logger.error(
            "run_registration_credentials_delivery: User %s not found",
            user_id,
        )
    except Exception as e:
        logger.error(
            "Failed to send registration credentials: %s",
            e,
            exc_info=True,
        )


@shared_task
def deliver_registration_credentials_task(
    user_id: str,
    password: str,
    notification_preference: str,
):
    """Optional Celery entrypoint (e.g. if you enqueue from elsewhere)."""
    run_registration_credentials_delivery(user_id, password, notification_preference)


@shared_task
def send_password_reset_email_task(user_id: str, token: str):
    """Send password reset email asynchronously via Celery to avoid blocking requests."""
    from django.conf import settings
    from django.core.mail import send_mail
    from django.utils import timezone

    from .models import User

    try:
        user = User.objects.select_related("church").get(pk=user_id)
        church = user.church or None

        # Reconstruct the password reset link
        base = getattr(settings, "FRONTEND_BASE_URL", "http://localhost:3000").rstrip(
            "/"
        )
        link = f"{base}/login/resetpassword?token={token}"

        church_name = getattr(church, "name", None) or "The Open Door"
        subject = f"Reset your {church_name} password"
        message = (
            f"Hello,\n\n"
            f"We received a request to reset your password. Use the link below to set a new password:\n\n"
            f"{link}\n\n"
            f"If you didn't request this, you can ignore this email.\n"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info(f"Password reset email sent to {user.email}")
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for password reset email")
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}", exc_info=True)
