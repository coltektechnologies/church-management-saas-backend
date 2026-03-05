"""Utilities for notification access control based on church subscription plan."""


def church_can_use_sms_email(church, allow_initial_admin=False):
    """
    Check if a church can use SMS and email notifications.

    FREE plan: Only allowed when creating the first admin user (initial church setup).
    TRIAL, BASIC, PREMIUM, ENTERPRISE: Full access.

    Args:
        church: Church instance (can be None for platform)
        allow_initial_admin: If True, allow SMS/email for FREE when sending
            credentials to the first admin during church creation.

    Returns:
        bool: True if SMS/email notifications are allowed.
    """
    if church is None:
        return True
    if getattr(church, "subscription_plan", None) != "FREE":
        return True
    return bool(allow_initial_admin)
