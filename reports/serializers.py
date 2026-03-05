"""
Report serializers for API responses and scheduled report CRUD.
"""

from rest_framework import serializers

from .models import ScheduledReport


class ScheduledReportSerializer(serializers.ModelSerializer):
    report_type_display = serializers.CharField(
        source="get_report_type_display", read_only=True
    )
    frequency_display = serializers.CharField(
        source="get_frequency_display", read_only=True
    )

    class Meta:
        model = ScheduledReport
        fields = [
            "id",
            "name",
            "report_type",
            "report_type_display",
            "frequency",
            "frequency_display",
            "format",
            "custom_config",
            "recipient_emails",
            "is_active",
            "last_run_at",
            "next_run_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "last_run_at",
            "next_run_at",
            "created_at",
            "updated_at",
        ]


class ScheduleReportCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    report_type = serializers.ChoiceField(choices=ScheduledReport.REPORT_TYPE_CHOICES)
    frequency = serializers.ChoiceField(choices=ScheduledReport.FREQUENCY_CHOICES)
    format = serializers.ChoiceField(
        choices=ScheduledReport.FORMAT_CHOICES, default="pdf"
    )
    custom_config = serializers.JSONField(required=False, default=dict)
    recipient_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        default=list,
    )
