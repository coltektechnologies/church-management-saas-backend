from django.urls import path

from .views import (
    AgentAlertListCreateView,
    AgentAskView,
    AgentLogListCreateView,
    AgentScheduleListView,
)

app_name = "agents"

urlpatterns = [
    path("logs/", AgentLogListCreateView.as_view(), name="agent-logs"),
    path("alerts/", AgentAlertListCreateView.as_view(), name="agent-alerts"),
    path("schedules/", AgentScheduleListView.as_view(), name="agent-schedules"),
    path("ask/", AgentAskView.as_view(), name="agent-ask"),
]
