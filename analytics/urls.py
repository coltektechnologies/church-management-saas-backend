from django.urls import path

from .views import (AnalyticsAnnouncementsStatsView,
                    AnalyticsDepartmentsPerformanceView,
                    AnalyticsFinanceKPIsView, AnalyticsFinanceTrendsView,
                    AnalyticsMembersStatsView, DashboardAdminView,
                    DashboardDepartmentView, DashboardSecretariatView,
                    DashboardTreasuryView)

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
        "announcements/stats/",
        AnalyticsAnnouncementsStatsView.as_view(),
        name="announcements-stats",
    ),
    path(
        "departments/performance/",
        AnalyticsDepartmentsPerformanceView.as_view(),
        name="departments-performance",
    ),
]
