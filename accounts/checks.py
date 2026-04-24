"""Django system checks for configuration that breaks runtime behavior."""

from django.conf import settings
from django.core.checks import Warning, register


@register()
def email_smtp_password_configured(app_configs, **kwargs):
    """
    SMS can work via mNotify while email stays broken if SMTP credentials are missing.
    Warn when using the real SMTP backend without a password.
    """
    warnings = []
    backend = (getattr(settings, "EMAIL_BACKEND", "") or "").lower()
    if "smtp" not in backend:
        return warnings
    if backend.endswith("console.EmailBackend") or "console" in backend:
        return warnings
    pwd = getattr(settings, "EMAIL_HOST_PASSWORD", None)
    if pwd:
        return warnings
    warnings.append(
        Warning(
            "EMAIL_HOST_PASSWORD is empty. Outbound SMTP email will fail until you set it "
            "(e.g. Gmail: Google Account → Security → 2-Step Verification → App passwords). "
            "SMS still works via MNOTIFY_API_KEY.",
            id="accounts.W001",
        )
    )
    return warnings
