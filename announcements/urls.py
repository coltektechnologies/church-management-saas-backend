from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()

# Category endpoints
router.register(
    r"categories", views.AnnouncementCategoryViewSet, basename="announcement-category"
)

# Template endpoints
router.register(
    r"templates", views.AnnouncementTemplateViewSet, basename="announcement-template"
)

# Announcement endpoints
router.register(r"", views.AnnouncementViewSet, basename="announcement")

# Nested router for attachments
announcement_router = DefaultRouter()
announcement_router.register(
    r"attachments",
    views.AnnouncementAttachmentViewSet,
    basename="announcement-attachment",
)

urlpatterns = [
    # Include all DRF ViewSet URLs
    path("", include(router.urls)),
    # Nested attachment URLs
    path("<uuid:announcement_id>/", include(announcement_router.urls)),
    # Additional custom endpoints
    path(
        "pending/",
        views.AnnouncementViewSet.as_view({"get": "pending"}),
        name="announcement-pending",
    ),
    path(
        "published/",
        views.AnnouncementViewSet.as_view({"get": "published"}),
        name="announcement-published",
    ),
    # Statistics endpoints
    path(
        "stats/summary/",
        views.AnnouncementViewSet.as_view({"get": "stats_summary"}),
        name="announcement-stats-summary",
    ),
    path(
        "stats/timeline/",
        views.AnnouncementViewSet.as_view({"get": "stats_timeline"}),
        name="announcement-stats-timeline",
    ),
]
