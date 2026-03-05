from django.contrib.auth.decorators import login_required
from django.urls import path

from core.views.activity import ActivityFeedView

app_name = "core"

urlpatterns = [
    path("activity/", login_required(ActivityFeedView.as_view()), name="activity_feed"),
]
