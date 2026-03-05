from rest_framework import serializers

from .models import (EmailLog, Notification, NotificationBatch,
                     NotificationPreference, NotificationTemplate, SMSLog)

# =====================================================
# NOTIFICATION SERIALIZERS
# =====================================================


class NotificationSerializer(serializers.ModelSerializer):
    """In-app notification"""

    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "priority",
            "priority_display",
            "category",
            "link",
            "icon",
            "status",
            "status_display",
            "is_read",
            "read_at",
            "time_ago",
            "created_at",
        ]
        read_only_fields = ["id", "status", "is_read", "read_at", "created_at"]

    def get_time_ago(self, obj):
        """Human-readable time"""
        from django.utils.timesince import timesince

        return timesince(obj.created_at)


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Create notification"""

    user_id = serializers.UUIDField(required=False)
    member_id = serializers.UUIDField(required=False)

    class Meta:
        model = Notification
        fields = [
            "user_id",
            "member_id",
            "title",
            "message",
            "priority",
            "category",
            "link",
            "icon",
            "scheduled_for",
        ]

    def create(self, validated_data):
        from accounts.models import User
        from members.models import Member

        from .services import NotificationService

        request = self.context.get("request")
        church = request.current_church or request.user.church

        user_id = validated_data.pop("user_id", None)
        member_id = validated_data.pop("member_id", None)

        user = User.objects.get(id=user_id) if user_id else None
        member = Member.objects.get(id=member_id) if member_id else None

        return NotificationService.create_notification(
            church=church, user=user, member=member, **validated_data
        )


# =====================================================
# TEMPLATE SERIALIZERS
# =====================================================


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Notification template"""

    template_type_display = serializers.CharField(
        source="get_template_type_display", read_only=True
    )
    category_display = serializers.CharField(
        source="get_category_display", read_only=True
    )

    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "name",
            "template_type",
            "template_type_display",
            "category",
            "category_display",
            "subject",
            "message",
            "is_system_template",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "is_system_template", "created_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        church = request.current_church or request.user.church

        return NotificationTemplate.objects.create(church=church, **validated_data)


# =====================================================
# PREFERENCE SERIALIZERS
# =====================================================


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """User notification preferences"""

    class Meta:
        model = NotificationPreference
        fields = [
            "enable_in_app",
            "enable_email",
            "enable_sms",
            "announcements",
            "reminders",
            "birthdays",
            "events",
            "finance",
            "digest_mode",
            "digest_frequency",
            "quiet_hours_enabled",
            "quiet_hours_start",
            "quiet_hours_end",
        ]


# =====================================================
# LOG SERIALIZERS
# =====================================================


class SMSLogSerializer(serializers.ModelSerializer):
    """SMS log"""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = SMSLog
        fields = [
            "id",
            "phone_number",
            "member_name",
            "message",
            "message_length",
            "sms_count",
            "gateway",
            "status",
            "status_display",
            "delivery_status",
            "error_message",
            "sent_at",
            "delivered_at",
            "created_at",
        ]

    def get_member_name(self, obj):
        return obj.member.full_name if obj.member else None


class EmailLogSerializer(serializers.ModelSerializer):
    """Email log"""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    member_name = serializers.SerializerMethodField()

    class Meta:
        model = EmailLog
        fields = [
            "id",
            "email_address",
            "member_name",
            "subject",
            "gateway",
            "status",
            "status_display",
            "opened_count",
            "clicked_count",
            "error_message",
            "sent_at",
            "delivered_at",
            "first_opened_at",
            "created_at",
        ]

    def get_member_name(self, obj):
        return obj.member.full_name if obj.member else None


# =====================================================
# BATCH SERIALIZERS
# =====================================================


class NotificationBatchSerializer(serializers.ModelSerializer):
    """Notification batch"""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    progress_percentage = serializers.SerializerMethodField()

    class Meta:
        model = NotificationBatch
        fields = [
            "id",
            "name",
            "description",
            "target_all_members",
            "target_departments",
            "target_members",
            "message",
            "send_sms",
            "send_email",
            "send_in_app",
            "status",
            "status_display",
            "total_recipients",
            "successful_count",
            "failed_count",
            "progress_percentage",
            "scheduled_for",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "total_recipients",
            "successful_count",
            "failed_count",
            "started_at",
            "completed_at",
            "created_at",
        ]

    def get_progress_percentage(self, obj):
        if obj.total_recipients == 0:
            return 0
        completed = obj.successful_count + obj.failed_count
        return (completed / obj.total_recipients) * 100

    def create(self, validated_data):
        request = self.context.get("request")
        church = request.current_church or request.user.church

        return NotificationBatch.objects.create(
            church=church, created_by=request.user, **validated_data
        )


# =====================================================
# ACTION SERIALIZERS
# =====================================================


class SendSMSSerializer(serializers.Serializer):
    """Send SMS"""

    phone_number = serializers.CharField(max_length=50)
    message = serializers.CharField()
    member_id = serializers.UUIDField(required=False)
    scheduled_for = serializers.DateTimeField(required=False)


class SendEmailSerializer(serializers.Serializer):
    """Send email"""

    email_address = serializers.EmailField()
    subject = serializers.CharField(max_length=200)
    message_html = serializers.CharField()
    member_id = serializers.UUIDField(required=False)
    scheduled_for = serializers.DateTimeField(required=False)


class SendBulkNotificationSerializer(serializers.Serializer):
    """Send bulk notification"""

    title = serializers.CharField(max_length=200)
    message = serializers.CharField()
    target = serializers.ChoiceField(choices=["all_members", "departments", "specific"])
    department_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False
    )
    member_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    send_sms = serializers.BooleanField(default=False)
    send_email = serializers.BooleanField(default=False)
    send_in_app = serializers.BooleanField(default=True)
