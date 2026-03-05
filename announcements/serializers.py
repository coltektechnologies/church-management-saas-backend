from rest_framework import serializers

from .models import (Announcement, AnnouncementAttachment,
                     AnnouncementCategory, AnnouncementTemplate)


class AnnouncementCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementCategory
        fields = ["id", "name", "description", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class AnnouncementTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementTemplate
        fields = [
            "id",
            "name",
            "subject",
            "content",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AnnouncementAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()

    class Meta:
        model = AnnouncementAttachment
        fields = [
            "id",
            "file",
            "file_type",
            "display_name",
            "description",
            "uploaded_at",
            "file_url",
            "file_name",
            "file_size",
        ]
        read_only_fields = ["id", "uploaded_at", "file_type"]

    def get_file_url(self, obj):
        if obj.file:
            return obj.file.url
        return None

    def get_file_name(self, obj):
        if obj.file:
            return obj.file.name.split("/")[-1]
        return None

    def get_file_size(self, obj):
        if obj.file:
            return obj.file.size
        return None


class AnnouncementListSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    created_by = serializers.StringRelatedField()
    status_display = serializers.CharField(source="get_status_display")
    priority_display = serializers.CharField(source="get_priority_display")
    attachment_count = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "is_featured",
            "is_pinned",
            "publish_at",
            "expires_at",
            "created_at",
            "category",
            "created_by",
            "attachment_count",
        ]

    def get_attachment_count(self, obj):
        return obj.attachments.count()


class AnnouncementDetailSerializer(serializers.ModelSerializer):
    category = AnnouncementCategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=AnnouncementCategory.objects.all(),
        source="category",
        write_only=True,
        required=False,
        allow_null=True,
    )
    template = AnnouncementTemplateSerializer(read_only=True)
    template_id = serializers.PrimaryKeyRelatedField(
        queryset=AnnouncementTemplate.objects.all(),
        source="template",
        write_only=True,
        required=False,
        allow_null=True,
    )
    created_by = serializers.StringRelatedField(read_only=True)
    approved_by = serializers.StringRelatedField(read_only=True)
    attachments = AnnouncementAttachmentSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )
    is_published = serializers.BooleanField(read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "content",
            "status",
            "status_display",
            "priority",
            "priority_display",
            "is_featured",
            "is_pinned",
            "is_published",
            "allow_comments",
            "allow_sharing",
            "publish_at",
            "expires_at",
            "rejection_reason",
            "created_at",
            "updated_at",
            "category",
            "category_id",
            "template",
            "template_id",
            "created_by",
            "approved_by",
            "approved_at",
            "attachments",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "approved_at",
            "is_published",
        ]

    def validate(self, data):
        """
        Validate that publish_at is before expires_at if both are provided
        """
        publish_at = data.get("publish_at")
        expires_at = data.get("expires_at")

        if publish_at and expires_at and publish_at >= expires_at:
            raise serializers.ValidationError(
                {"expires_at": "Expiration date must be after publish date"}
            )

        return data


class AnnouncementCreateSerializer(AnnouncementDetailSerializer):
    class Meta(AnnouncementDetailSerializer.Meta):
        read_only_fields = AnnouncementDetailSerializer.Meta.read_only_fields + [
            "status"
        ]


class AnnouncementUpdateStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["status", "rejection_reason"]
        extra_kwargs = {"rejection_reason": {"required": False}}

    def validate(self, data):
        status = data.get("status")
        rejection_reason = data.get("rejection_reason")

        if status == "REJECTED" and not rejection_reason:
            raise serializers.ValidationError(
                {
                    "rejection_reason": "Rejection reason is required when rejecting an announcement"
                }
            )
        return data
