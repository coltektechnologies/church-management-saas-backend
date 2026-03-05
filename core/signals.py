"""
Signal handlers for automatic audit logging
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from accounts.models.base_models import AuditLog
from core.audit import register_audit_signals

User = get_user_model()


def register_audit_handlers():
    """Register audit handlers for all models that need tracking"""
    from django.apps import apps

    # Models to exclude from automatic auditing
    EXCLUDED_MODELS = [
        "sessions.Session",
        "admin.LogEntry",
        "contenttypes.ContentType",
        "authtoken.Token",
        "authtoken.TokenProxy",
    ]

    # Register handlers for each model
    for model in apps.get_models():
        model_label = f"{model._meta.app_label}.{model._meta.model_name}"

        # Skip excluded models
        if model_label in EXCLUDED_MODELS or model is AuditLog:
            continue

        # Register the model for audit logging
        register_audit_signals(model)


@receiver(post_save, sender=User)
def log_user_activity(sender, instance, created, **kwargs):
    """Log user-related activities"""
    from crum import get_current_request
    from django.contrib.auth import get_user_model

    User = get_user_model()
    request = get_current_request()

    if created:
        action = "CREATE"
        description = f"User account created: {instance.email}"
    else:
        action = "UPDATE"
        description = f"User account updated: {instance.email}"

    # Get the requesting user if available
    user = request.user if request and hasattr(request, "user") else None
    if not user or not user.is_authenticated:
        user = instance  # Fall back to the user themselves

    # Log the action
    AuditLog.log(
        user=user,
        action=action,
        instance=instance,
        request=request,
        description=description,
    )


@receiver(post_delete, sender=User)
def log_user_deletion(sender, instance, **kwargs):
    """Log user deletion. Never use the deleted user as actor - they no longer exist in DB."""
    from crum import get_current_request

    request = get_current_request()
    user = (
        request.user
        if request and hasattr(request, "user") and request.user.is_authenticated
        else None
    )
    # Must NOT use instance (deleted user) - would cause IntegrityError on insert
    AuditLog.log(
        user=user,
        action="DELETE",
        instance=instance,
        request=request,
        description=f"User account deleted: {instance.email}",
    )


# Connect the audit handlers when the app is ready
def ready():
    from django.apps import AppConfig

    class CoreConfig(AppConfig):
        name = "core"

        def ready(self):
            register_audit_handlers()

    return CoreConfig
