from django.urls import path

from .api_views import MembersByChurchListView

# Import views from their respective modules
from .views.member_views import (
    CurrentMemberProfileAPIView,
    MemberCreateView,
    MemberDetailAPIView,
    MemberMyGivingSummaryAPIView,
    MemberMyPledgeDetailAPIView,
    MemberMyPledgesAPIView,
    MemberView,
)
from .views.visitor_views import VisitorDetailAPIView, VisitorToMemberView, VisitorView

app_name = "members"

urlpatterns = [
    # ==========================================
    # MEMBER ENDPOINTS
    # ==========================================
    path("create/", MemberCreateView.as_view(), name="member-create"),
    path("members/", MemberView.as_view(), name="member-list"),
    path("members/me/", CurrentMemberProfileAPIView.as_view(), name="member-me"),
    path(
        "members/me/giving-summary/",
        MemberMyGivingSummaryAPIView.as_view(),
        name="member-me-giving-summary",
    ),
    path(
        "members/me/pledges/",
        MemberMyPledgesAPIView.as_view(),
        name="member-me-pledges",
    ),
    path(
        "members/me/pledges/<uuid:pk>/",
        MemberMyPledgeDetailAPIView.as_view(),
        name="member-me-pledge-detail",
    ),
    path("members/<uuid:pk>/", MemberDetailAPIView.as_view(), name="member-detail"),
    # ==========================================
    # VISITOR ENDPOINTS
    # ==========================================
    path("visitors/", VisitorView.as_view(), name="visitor-list-create"),
    path("visitors/<uuid:pk>/", VisitorDetailAPIView.as_view(), name="visitor-detail"),
    # ==========================================
    # VISITOR TO MEMBER CONVERSION
    # ==========================================
    path(
        "visitors/convert-to-member/",
        VisitorToMemberView.as_view(),
        name="visitor-to-member",
    ),
    # ==========================================
    # API ENDPOINTS
    # ==========================================
    path(
        "members/by-church/",
        MembersByChurchListView.as_view(),
        name="api-members-by-church",
    ),
]
