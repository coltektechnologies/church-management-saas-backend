from rest_framework import serializers

from .models import ChurchFile


class ChurchFileSerializer(serializers.ModelSerializer):
    """Full file metadata for response."""

    uploaded_by_email = serializers.SerializerMethodField()

    class Meta:
        model = ChurchFile
        fields = [
            "id",
            "church",
            "uploaded_by",
            "uploaded_by_email",
            "public_id",
            "secure_url",
            "resource_type",
            "cloudinary_version",
            "folder",
            "subfolder",
            "original_filename",
            "content_type",
            "size_bytes",
            "is_image",
            "description",
            "tags",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_uploaded_by_email(self, obj):
        return obj.uploaded_by.email if obj.uploaded_by else None


class ChurchFileListSerializer(serializers.ModelSerializer):
    """Light list view."""

    uploaded_by_email = serializers.SerializerMethodField()

    class Meta:
        model = ChurchFile
        fields = [
            "id",
            "original_filename",
            "secure_url",
            "content_type",
            "size_bytes",
            "is_image",
            "subfolder",
            "created_at",
            "uploaded_by_email",
        ]

    def get_uploaded_by_email(self, obj):
        return obj.uploaded_by.email if obj.uploaded_by else None


class FileUploadSerializer(serializers.Serializer):
    """Input for single upload (multipart: file + optional fields)."""

    subfolder = serializers.CharField(
        required=False, default="", allow_blank=True, max_length=100
    )
    description = serializers.CharField(
        required=False, default="", allow_blank=True, max_length=500
    )
    tags = serializers.ListField(
        child=serializers.CharField(max_length=50), required=False, default=list
    )
