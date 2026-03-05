"""API URL patterns for core (activity feed)."""

from django.urls import path

from .views.activity_api import ActivityFeedAPIView, ActivityFeedByAppView

app_name = "core_api"

urlpatterns = [
    path("", ActivityFeedAPIView.as_view(), name="activity-feed"),
    path(
        "<str:app_label>/", ActivityFeedByAppView.as_view(), name="activity-feed-by-app"
    ),
]
