"""
Analytics & Dashboard API views. All endpoints are church-scoped and cached.
"""

from datetime import date

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.services import DashboardService


def _church_from_request(request):
    return getattr(request, "current_church", None) or getattr(
        request.user, "church", None
    )


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, TypeError):
        return None


# ---------- Dashboard endpoints ----------


class DashboardSecretariatView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Secretariat dashboard: announcements and programs pending secretariat approval.",
        tags=["Analytics - Dashboard"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        data = DashboardService(church).dashboard_secretariat()
        return Response(data)


class DashboardTreasuryView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Treasury dashboard: income, expenses, pending requests, assets.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
        ],
        tags=["Analytics - Dashboard"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        date_from = _parse_date(request.query_params.get("date_from") or "")
        date_to = _parse_date(request.query_params.get("date_to") or "")
        data = DashboardService(church).dashboard_treasury(
            date_from=date_from, date_to=date_to
        )
        return Response(data)


class DashboardDepartmentView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Dashboard for a single department by ID.",
        tags=["Analytics - Dashboard"],
    )
    def get(self, request, id):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        data = DashboardService(church).dashboard_department(str(id))
        if data.get("error"):
            return Response(data, status=status.HTTP_404_NOT_FOUND)
        return Response(data)


class DashboardAdminView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Admin overview dashboard: high-level KPIs across members, departments, announcements, finance.",
        tags=["Analytics - Dashboard"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        data = DashboardService(church).dashboard_admin()
        return Response(data)


# ---------- Analytics endpoints ----------


class AnalyticsMembersStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Member statistics: total, by membership status, by gender.",
        tags=["Analytics"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        data = DashboardService(church).members_stats()
        return Response(data)


class AnalyticsFinanceTrendsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Finance trends: income and expenses by month over a period.",
        manual_parameters=[
            openapi.Parameter(
                "period_days", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, default=90
            ),
        ],
        tags=["Analytics"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            period_days = int(request.query_params.get("period_days") or 90)
        except (ValueError, TypeError):
            period_days = 90
        data = DashboardService(church).finance_trends(period_days=period_days)
        return Response(data)


class AnalyticsFinanceKPIsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Finance KPIs: total income, expenses, net, transaction counts for a period.",
        manual_parameters=[
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
        ],
        tags=["Analytics"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        date_from = _parse_date(request.query_params.get("date_from") or "")
        date_to = _parse_date(request.query_params.get("date_to") or "")
        data = DashboardService(church).finance_kpis(
            date_from=date_from, date_to=date_to
        )
        return Response(data)


class AnalyticsAnnouncementsStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Announcements statistics: total, by status, by priority.",
        tags=["Analytics"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        data = DashboardService(church).announcements_stats()
        return Response(data)


class AnalyticsTitheOfferingStatsView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Tithe and offerings: monthly trend, this month totals and weekly breakdown.",
        manual_parameters=[
            openapi.Parameter(
                "period_months",
                openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                default=9,
                description="Number of months for trend (default 9)",
            ),
        ],
        tags=["Analytics"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            period_months = int(request.query_params.get("period_months") or 9)
        except (ValueError, TypeError):
            period_months = 9
        data = DashboardService(church).tithe_offering_stats(
            period_months=period_months
        )
        return Response(data)


class AnalyticsDepartmentsPerformanceView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Departments performance: member count, programs (total, completed, in progress, approved) per department.",
        tags=["Analytics"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        data = DashboardService(church).departments_performance()
        return Response(data)


class AnalyticsMemberContributionsView(APIView):
    """Member contributions aggregated from income transactions for treasury dashboard."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Members who have contributed (income transactions with member FK), with totals and recent contributions.",
        manual_parameters=[
            openapi.Parameter(
                "limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, default=20
            ),
            openapi.Parameter(
                "date_from", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
            openapi.Parameter(
                "date_to", openapi.IN_QUERY, type=openapi.TYPE_STRING, format="date"
            ),
        ],
        tags=["Analytics"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            limit = int(request.query_params.get("limit") or 20)
            limit = min(max(limit, 1), 100)
        except (ValueError, TypeError):
            limit = 20
        date_from = _parse_date(request.query_params.get("date_from") or "")
        date_to = _parse_date(request.query_params.get("date_to") or "")
        data = DashboardService(church).member_contributions(
            limit=limit, date_from=date_from, date_to=date_to
        )
        return Response(data)


class AnalyticsDepartmentBudgetsView(APIView):
    """Per-department budget allocated vs utilized for treasury dashboard."""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Department budgets: allocated (program expense budgets) vs utilized (expense transactions) per department.",
        tags=["Analytics"],
    )
    def get(self, request):
        church = _church_from_request(request)
        if not church:
            return Response(
                {"error": "Church context required"}, status=status.HTTP_400_BAD_REQUEST
            )
        data = DashboardService(church).department_budgets()
        return Response(data)
