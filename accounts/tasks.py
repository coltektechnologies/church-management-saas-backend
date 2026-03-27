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
            "run_registration_credentials_delivery: User %s not found", user_id
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
