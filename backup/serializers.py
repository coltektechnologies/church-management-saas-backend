from rest_framework import serializers

from .models import BackupRecord


class BackupRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupRecord
        fields = [
            "id",
            "backup_type",
            "file_path",
            "file_size_bytes",
            "created_by_id",
            "created_at",
            "notes",
        ]
        read_only_fields = fields
