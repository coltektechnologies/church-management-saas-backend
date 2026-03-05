"""Serializers for core API (activity feed)."""

from rest_framework import serializers

from accounts.models.base_models import AuditLog


class ActivityFeedSerializer(serializers.ModelSerializer):
    """Activity feed item for API."""

    user_email = serializers.SerializerMethodField()
    user_display = serializers.SerializerMethodField()
    action_display = serializers.CharField(source="get_action_display", read_only=True)
    church_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "action",
            "action_display",
            "model_name",
            "object_id",
            "description",
            "changes",
            "user",
            "user_email",
            "user_display",
            "church",
            "church_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_email(self, obj):
        return obj.user.email if obj.user else None

    def get_user_display(self, obj):
        if not obj.user:
            return None
        name = getattr(obj.user, "full_name", None) or (
            getattr(obj.user, "get_full_name", lambda: "")()
        )
        return (name and name.strip()) or obj.user.email

    def get_church_name(self, obj):
        return obj.church.name if obj.church else None
