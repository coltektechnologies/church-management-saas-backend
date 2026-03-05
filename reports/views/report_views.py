"""
Report API views: all report endpoints with optional export (format=pdf|xlsx|csv).
"""

from django.http import HttpResponse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.filters import get_date_range_from_request, get_report_filters
from reports.models import ScheduledReport
from reports.serializers import (ScheduledReportSerializer,
                                 ScheduleReportCreateSerializer)
from reports.services import ReportGenerationService
from reports.services.exporters import CSVExporter, ExcelExporter, PDFExporter


def _church_from_request(request):
    return getattr(request, "current_church", None) or getattr(
        request.user, "church", None
    )


def _report_response(
    request, report_type: str, use_cache: bool = True
) -> Response | HttpResponse:
    church = _church_from_request(request)
    if not church:
        return Response(
            {"error": "Church context required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    filters = get_report_filters(request)
    date_from, date_to = get_date_range_from_request(request)
    fmt = (request.query_params.get("format") or "").lower().strip()

    service = ReportGenerationService(church)
    result = service.get_report(
        report_type=report_type,
        date_from=date_from,
        date_to=date_to,
        filters=filters,
        use_cache=use_cache,
    )

    if fmt in ("pdf", "xlsx", "csv"):
        if result.get("meta", {}).get("error"):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        if fmt == "pdf":
            exporter = PDFExporter()
        elif fmt == "xlsx":
            exporter = ExcelExporter()
        else:
            exporter = CSVExporter()
        buffer = exporter.export(result, title=f"Report: {report_type}")
        filename = f"report_{report_type}_{result.get('meta', {}).get('date_from', '')}.{exporter.file_extension}"
        response = HttpResponse(buffer.read(), content_type=exporter.content_type)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    return Response(result)


# ---------- Member reports ----------


class ReportMembersView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Members report. Use format=pdf|xlsx|csv for export.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "membership_status", openapi.IN_QUERY, type=openapi.TYPE_STRING
            ),
            openapi.Parameter(
                "format",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["json", "pdf", "xlsx", "csv"],
            ),
        ],
        tags=["Reports"],
    )
    def get(self, request):
        return _report_response(request, "members")


class ReportMembersGrowthView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Members growth (new members by month). Use format=pdf|xlsx|csv for export.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "format",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["json", "pdf", "xlsx", "csv"],
            ),
        ],
        tags=["Reports"],
    )
    def get(self, request):
        return _report_response(request, "members_growth")


class ReportMembersDemographicsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Members demographics (gender, status, marital, baptism). Use format=pdf|xlsx|csv for export.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "format",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["json", "pdf", "xlsx", "csv"],
            ),
        ],
        tags=["Reports"],
    )
    def get(self, request):
        return _report_response(request, "members_demographics")


# ---------- Department report ----------


class ReportDepartmentsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Departments summary. Use format=pdf|xlsx|csv for export.",
        manual_parameters=[
            openapi.Parameter(
                "format",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["json", "pdf", "xlsx", "csv"],
            ),
        ],
        tags=["Reports"],
    )
    def get(self, request):
        return _report_response(request, "departments")


# ---------- Finance reports ----------


class ReportFinanceIncomeView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Income report. Use format=pdf|xlsx|csv for export.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "format",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["json", "pdf", "xlsx", "csv"],
            ),
        ],
        tags=["Reports"],
    )
    def get(self, request):
        return _report_response(request, "finance_income")


class ReportFinanceExpensesView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Expenses report. Use format=pdf|xlsx|csv for export.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "format",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["json", "pdf", "xlsx", "csv"],
            ),
        ],
        tags=["Reports"],
    )
    def get(self, request):
        return _report_response(request, "finance_expenses")


class ReportFinanceBalanceSheetView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Balance sheet (income vs expenses). Use format=pdf|xlsx|csv for export.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "format",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["json", "pdf", "xlsx", "csv"],
            ),
        ],
        tags=["Reports"],
    )
    def get(self, request):
        return _report_response(request, "finance_balance_sheet")


class ReportFinanceCashFlowView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Cash flow summary. Use format=pdf|xlsx|csv for export.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "format",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["json", "pdf", "xlsx", "csv"],
            ),
        ],
        tags=["Reports"],
    )
    def get(self, request):
        return _report_response(request, "finance_cash_flow")


# ---------- Announcements & Audit ----------


class ReportAnnouncementsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Announcements report. Use format=pdf|xlsx|csv for export.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING),
            openapi.Parameter(
                "format",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["json", "pdf", "xlsx", "csv"],
            ),
        ],
        tags=["Reports"],
    )
    def get(self, request):
        return _report_response(request, "announcements")


class ReportAuditTrailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Audit trail report. Use format=pdf|xlsx|csv for export.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "format",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                enum=["json", "pdf", "xlsx", "csv"],
            ),
        ],
        tags=["Reports"],
    )
    def get(self, request):
        return _report_response(request, "audit_trail")


# ---------- Custom report (POST) ----------


class ReportCustomView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Run a custom report by type and filters. Body: report_type, date_from, date_to, filters.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "report_type": openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=[
                        "members",
                        "members_growth",
                        "members_demographics",
                        "departments",
                        "finance_income",
                        "finance_expenses",
                        "finance_balance_sheet",
                        "finance_cash_flow",
                        "announcements",
                        "audit_trail",
                    ],
                ),
                "date_from": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                "date_to": openapi.Schema(type=openapi.TYPE_STRING, format="date"),
                "filters": openapi.Schema(type=openapi.TYPE_OBJECT),
            },
        ),
        tags=["Reports"],
    )
    def post(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        report_type = request.data.get("report_type")
        if not report_type:
            return Response(
                {"error": "report_type is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        date_from = request.data.get("date_from")
        date_to = request.data.get("date_to")
        filters = request.data.get("filters") or {}
        if date_from:
            try:
                from datetime import date

                date_from = (
                    date.fromisoformat(date_from)
                    if isinstance(date_from, str)
                    else date_from
                )
            except (ValueError, TypeError):
                date_from = None
        if date_to:
            try:
                from datetime import date

                date_to = (
                    date.fromisoformat(date_to) if isinstance(date_to, str) else date_to
                )
            except (ValueError, TypeError):
                date_to = None
        service = ReportGenerationService(church)
        result = service.get_report(
            report_type=report_type,
            date_from=date_from,
            date_to=date_to,
            filters=filters,
            use_cache=True,
        )
        return Response(result)


# ---------- Scheduled reports ----------


class ScheduledReportListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="List scheduled reports for the current church.",
        tags=["Reports"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = ScheduledReport.objects.filter(church=church).order_by("next_run_at")
        serializer = ScheduledReportSerializer(qs, many=True)
        return Response(serializer.data)


class ScheduleReportView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a new scheduled report.",
        request_body=ScheduleReportCreateSerializer,
        tags=["Reports"],
    )
    def post(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = ScheduleReportCreateSerializer(data=request.data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        from reports.tasks import compute_next_run

        obj = ScheduledReport.objects.create(
            church=church,
            created_by=request.user,
            name=ser.validated_data["name"],
            report_type=ser.validated_data["report_type"],
            frequency=ser.validated_data["frequency"],
            format=ser.validated_data["format"],
            custom_config=ser.validated_data.get("custom_config") or {},
            recipient_emails=ser.validated_data.get("recipient_emails") or [],
        )
        compute_next_run(obj)
        obj.save()
        return Response(
            ScheduledReportSerializer(obj).data, status=status.HTTP_201_CREATED
        )
