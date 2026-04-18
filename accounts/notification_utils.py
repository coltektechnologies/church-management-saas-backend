"""Utilities for notification access control based on church subscription plan."""


def church_can_use_sms_email(
    church, allow_initial_admin=False, allow_staff_invite=False
):
    """
    Check if a church can use SMS and email notifications.

    FREE plan: Allowed for the first admin during setup, or when an authenticated
    church/platform admin invites another user (staff invite).
    TRIAL, BASIC, PREMIUM, ENTERPRISE: Full access.

    Args:
        church: Church instance (can be None for platform)
        allow_initial_admin: If True, allow SMS/email for FREE when sending
            credentials to the first admin during church creation.
        allow_staff_invite: If True, allow FREE-plan outbound send for admin-created users.

    Returns:
        bool: True if SMS/email notifications are allowed.
    """
    if church is None:
        return True
    if getattr(church, "subscription_plan", None) != "FREE":
        return True
    return bool(allow_initial_admin or allow_staff_invite)
