"""
Centralized audit logging utilities for the application.
"""

import json

from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from accounts.models.base_models import AuditLog, Church


class AuditLogger:
    """Helper class for creating audit log entries"""

    @staticmethod
    def _delete_context_church_id(instance):
        """Tenant id for DELETE audit rows (stored in metadata; never use church FK on delete)."""
        if instance is None:
            return None
        meta = instance._meta
        if meta.app_label == "accounts" and meta.model_name == "church" and instance.pk:
            return str(instance.pk)
        cid = getattr(instance, "church_id", None)
        return str(cid) if cid else None

    @staticmethod
    def _resolve_church_for_audit(instance):
        """Resolve Church FK for CREATE/UPDATE audit rows only."""
        if instance is None:
            return None
        meta = instance._meta
        if meta.app_label == "accounts" and meta.model_name == "church":
            if instance.pk:
                return Church.objects.filter(pk=instance.pk).first()
            return None
        church_id = getattr(instance, "church_id", None)
        if not church_id:
            return None
        return Church.objects.filter(pk=church_id).first()

    @classmethod
    def log_action(cls, user, action, instance, request=None, changes=None, **kwargs):
        """
        Create an audit log entry

        Args:
            user: The user performing the action
            action: Action type (e.g., 'CREATE', 'UPDATE', 'DELETE')
            instance: The model instance being acted upon
            request: Optional request object for additional context
            changes: Dictionary of changed fields (for updates)
            **kwargs: Additional fields to store in the log
        """
        if not user or not instance:
            return None

        kwargs.pop("church", None)

        # DELETE: never set church FK — cascade/commit order can remove the row before
        # INSERT is checked, causing IntegrityError. Keep tenant hint in metadata instead.
        if action == "DELETE":
            church = None
            ctx_id = cls._delete_context_church_id(instance)
            if ctx_id:
                existing = kwargs.get("metadata")
                if isinstance(existing, dict):
                    kwargs["metadata"] = {**existing, "context_church_id": ctx_id}
                else:
                    kwargs["metadata"] = {"context_church_id": ctx_id}
        else:
            church = cls._resolve_church_for_audit(instance)

        # Get request metadata if available
        ip_address = None
        user_agent = None
        if request:
            ip_address = request.META.get("REMOTE_ADDR")
            user_agent = request.META.get("HTTP_USER_AGENT", "")[
                :500
            ]  # Truncate if too long

        # Get model name and ID
        model_name = instance._meta.model.__name__
        object_id = str(instance.pk)

        # Create description based on action (allow override from kwargs)
        if kwargs.get("description"):
            description = kwargs.pop("description")
        elif action == "CREATE":
            description = f"Created {model_name} (ID: {object_id})"
        elif action == "UPDATE" and changes:
            changed_fields = ", ".join(changes.keys())
            description = f"Updated {model_name} (ID: {object_id}): {changed_fields}"
        elif action == "DELETE":
            description = f"Deleted {model_name} (ID: {object_id})"
        else:
            description = f"{action} on {model_name} (ID: {object_id})"

        # Create the audit log entry
        log_entry = AuditLog.objects.create(
            user=user,
            church=church,
            action=action,
            model_name=model_name,
            object_id=object_id,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            changes=json.dumps(changes) if changes else None,
            **kwargs,
        )

        return log_entry


def audit_model_changes(sender, **kwargs):
    """Signal handler to log model changes"""
    instance = kwargs["instance"]
    created = kwargs.get("created", False)

    # Skip for new instances (handled by post_save with created=True)
    if not created and hasattr(instance, "_old_instance"):
        changes = {}
        old_instance = instance._old_instance

        # Compare fields for changes
        for field in instance._meta.fields:
            field_name = field.name
            if field_name in ["updated_at", "last_modified"]:
                continue

            old_value = getattr(old_instance, field_name, None)
            new_value = getattr(instance, field_name, None)

            if old_value != new_value:
                changes[field_name] = {
                    "old": str(old_value) if old_value is not None else None,
                    "new": str(new_value) if new_value is not None else None,
                }

        if changes:
            # Get user from request if available
            from django.contrib.auth import get_user
            from django.db import transaction

            user = None
            if hasattr(instance, "_request_user"):
                user = instance._request_user
            else:
                # Try to get user from thread local
                try:
                    from crum import get_current_user

                    user = get_current_user()
                except:
                    pass

            if user and not user.is_anonymous:
                AuditLogger.log_action(
                    user=user, action="UPDATE", instance=instance, changes=changes
                )


def register_audit_signals(model):
    """Register signals for a model to track changes"""

    def save_handler(sender, instance, **kwargs):
        """Track instance before save to detect changes"""
        if instance.pk:
            try:
                instance._old_instance = sender.objects.get(pk=instance.pk)
            except sender.DoesNotExist:
                instance._old_instance = None

    def post_save_handler(sender, instance, created, **kwargs):
        """Handle post-save logging"""
        if created:
            # Get user from request if available
            user = getattr(instance, "_request_user", None)
            if not user:
                try:
                    from crum import get_current_user

                    user = get_current_user()
                except:
                    user = None

            if user and not user.is_anonymous:
                AuditLogger.log_action(user=user, action="CREATE", instance=instance)

    def post_delete_handler(sender, instance, **kwargs):
        """Handle post-delete logging"""
        user = None
        try:
            from crum import get_current_user

            user = get_current_user()
        except:
            pass

        if user and not user.is_anonymous:
            AuditLogger.log_action(user=user, action="DELETE", instance=instance)

    # Connect signals
    from django.db.models.signals import post_delete, post_save, pre_save

    pre_save.connect(save_handler, sender=model, weak=False)
    post_save.connect(post_save_handler, sender=model, weak=False)
    post_save.connect(audit_model_changes, sender=model, weak=False)
    post_delete.connect(post_delete_handler, sender=model, weak=False)
