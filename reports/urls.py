from django.urls import path

from .views import (ReportAnnouncementsView, ReportAuditTrailView,
                    ReportCustomView, ReportDepartmentsView,
                    ReportFinanceBalanceSheetView, ReportFinanceCashFlowView,
                    ReportFinanceExpensesView, ReportFinanceIncomeView,
                    ReportMembersDemographicsView, ReportMembersGrowthView,
                    ReportMembersView, ScheduledReportListView,
                    ScheduleReportView)

app_name = "reports"

urlpatterns = [
    # Members
    path("members/", ReportMembersView.as_view(), name="report-members"),
    path(
        "members/growth/",
        ReportMembersGrowthView.as_view(),
        name="report-members-growth",
    ),
    path(
        "members/demographics/",
        ReportMembersDemographicsView.as_view(),
        name="report-members-demographics",
    ),
    # Departments
    path("departments/", ReportDepartmentsView.as_view(), name="report-departments"),
    # Finance
    path(
        "finance/income/",
        ReportFinanceIncomeView.as_view(),
        name="report-finance-income",
    ),
    path(
        "finance/expenses/",
        ReportFinanceExpensesView.as_view(),
        name="report-finance-expenses",
    ),
    path(
        "finance/balance-sheet/",
        ReportFinanceBalanceSheetView.as_view(),
        name="report-finance-balance-sheet",
    ),
    path(
        "finance/cash-flow/",
        ReportFinanceCashFlowView.as_view(),
        name="report-finance-cash-flow",
    ),
    # Announcements & Audit
    path(
        "announcements/", ReportAnnouncementsView.as_view(), name="report-announcements"
    ),
    path("audit-trail/", ReportAuditTrailView.as_view(), name="report-audit-trail"),
    # Custom (POST)
    path("custom/", ReportCustomView.as_view(), name="report-custom"),
    # Scheduled
    path("scheduled/", ScheduledReportListView.as_view(), name="report-scheduled-list"),
    path("schedule/", ScheduleReportView.as_view(), name="report-schedule"),
]
