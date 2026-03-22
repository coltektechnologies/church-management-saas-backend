from django.urls import path

from .views import (
    AnalyticsAnnouncementsStatsView,
    AnalyticsDepartmentBudgetsView,
    AnalyticsDepartmentsPerformanceView,
    AnalyticsFinanceKPIsView,
    AnalyticsFinanceTrendsView,
    AnalyticsMemberContributionsView,
    AnalyticsMembersStatsView,
    AnalyticsTitheOfferingStatsView,
    DashboardAdminView,
    DashboardDepartmentView,
    DashboardSecretariatView,
    DashboardTreasuryView,
)

app_name = "analytics"

urlpatterns = [
    # Dashboard
    path(
        "dashboard/secretariat/",
        DashboardSecretariatView.as_view(),
        name="dashboard-secretariat",
    ),
    path(
        "dashboard/treasury/",
        DashboardTreasuryView.as_view(),
        name="dashboard-treasury",
    ),
    path(
        "dashboard/department/<uuid:id>/",
        DashboardDepartmentView.as_view(),
        name="dashboard-department",
    ),
    path("dashboard/admin/", DashboardAdminView.as_view(), name="dashboard-admin"),
    # Analytics
    path("members/stats/", AnalyticsMembersStatsView.as_view(), name="members-stats"),
    path(
        "finance/trends/", AnalyticsFinanceTrendsView.as_view(), name="finance-trends"
    ),
    path("finance/kpis/", AnalyticsFinanceKPIsView.as_view(), name="finance-kpis"),
    path(
        "finance/tithe-offerings/",
        AnalyticsTitheOfferingStatsView.as_view(),
        name="tithe-offerings-stats",
    ),
    path(
        "announcements/stats/",
        AnalyticsAnnouncementsStatsView.as_view(),
        name="announcements-stats",
    ),
    path(
        "departments/performance/",
        AnalyticsDepartmentsPerformanceView.as_view(),
        name="departments-performance",
    ),
    path(
        "finance/member-contributions/",
        AnalyticsMemberContributionsView.as_view(),
        name="member-contributions",
    ),
    path(
        "finance/department-budgets/",
        AnalyticsDepartmentBudgetsView.as_view(),
        name="department-budgets",
    ),
]
