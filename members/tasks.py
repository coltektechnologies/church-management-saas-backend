"""Celery tasks for member-related background work."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def run_member_credentials_delivery(
    member_id: str,
    password: str,
    send_email: bool,
    send_sms: bool,
    member_email: str | None,
    member_phone: str | None,
    login_username: str | None = None,
):
    """Send new-member login credentials via email and/or SMS (thread, worker, or eager Celery)."""
    from members.models import Member
    from members.services.credential_service import (
        send_credentials_email,
        send_credentials_sms,
    )

    try:
        m = Member.objects.select_related("church").get(pk=member_id)
        if send_email and member_email:
            try:
                send_credentials_email(
                    m,
                    member_email,
                    password,
                    allow_initial_admin=False,
                )
            except Exception:
                logger.exception(
                    "Member credential email failed (member_id=%s)", member_id
                )
        if send_sms and member_phone:
            sms_result = send_credentials_sms(
                m,
                member_phone,
                password,
                member_email,
                allow_initial_admin=False,
                login_username=login_username,
            )
            if not sms_result.get("success"):
                logger.error(
                    "Member credential SMS failed (member_id=%s): %s",
                    member_id,
                    sms_result.get("error", sms_result),
                )
    except Member.DoesNotExist:
        logger.error("run_member_credentials_delivery: Member %s not found", member_id)
    except Exception:
        logger.exception("Member credentials delivery failed (member_id=%s)", member_id)


@shared_task
def deliver_member_credentials_task(
    member_id: str,
    password: str,
    send_email: bool,
    send_sms: bool,
    member_email: str | None,
    member_phone: str | None,
    login_username: str | None = None,
):
    """Celery entrypoint — same behavior as run_member_credentials_delivery."""
    run_member_credentials_delivery(
        member_id,
        password,
        send_email,
        send_sms,
        member_email,
        member_phone,
        login_username=login_username,
    )
