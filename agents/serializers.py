import uuid

from rest_framework import serializers

from accounts.models import Church

from .models import AgentAlert, AgentLog


class AgentLogSerializer(serializers.ModelSerializer):
    church_id = serializers.SerializerMethodField()
    church_name = serializers.SerializerMethodField()

    class Meta:
        model = AgentLog
        fields = (
            "id",
            "agent_name",
            "action",
            "status",
            "input_data",
            "output_data",
            "error",
            "church_id",
            "church_name",
            "triggered_by",
            "duration_ms",
            "created_at",
        )

    def get_church_id(self, obj):
        return str(obj.church_id) if obj.church_id else None

    def get_church_name(self, obj):
        return getattr(obj.church, "name", None) if obj.church_id else None


class AgentAlertSerializer(serializers.ModelSerializer):
    church_id = serializers.SerializerMethodField()
    church_name = serializers.SerializerMethodField()

    class Meta:
        model = AgentAlert
        fields = (
            "id",
            "agent_name",
            "alert_type",
            "message",
            "severity",
            "church_id",
            "church_name",
            "created_at",
        )

    def get_church_id(self, obj):
        return str(obj.church_id) if obj.church_id else None

    def get_church_name(self, obj):
        return getattr(obj.church, "name", None) if obj.church_id else None


def _parse_optional_church_id(value):
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(str(value).strip())
    except (ValueError, AttributeError) as e:
        raise serializers.ValidationError("Invalid church_id UUID.") from e


class AgentLogCreateSerializer(serializers.ModelSerializer):
    church_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
        max_length=40,
    )

    class Meta:
        model = AgentLog
        fields = (
            "agent_name",
            "action",
            "status",
            "input_data",
            "output_data",
            "error",
            "church_id",
            "triggered_by",
            "duration_ms",
        )

    def validate_church_id(self, value):
        return _parse_optional_church_id(value)

    def create(self, validated_data):
        raw_church = validated_data.pop("church_id", None)
        church = None
        if raw_church:
            church = Church.objects.filter(pk=raw_church).first()
        return AgentLog.objects.create(church=church, **validated_data)


class AgentAlertCreateSerializer(serializers.ModelSerializer):
    church_id = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
        max_length=40,
    )

    class Meta:
        model = AgentAlert
        fields = (
            "agent_name",
            "alert_type",
            "message",
            "severity",
            "church_id",
        )

    def validate_church_id(self, value):
        return _parse_optional_church_id(value)

    def create(self, validated_data):
        raw_church = validated_data.pop("church_id", None)
        church = None
        if raw_church:
            church = Church.objects.filter(pk=raw_church).first()
        return AgentAlert.objects.create(church=church, **validated_data)
