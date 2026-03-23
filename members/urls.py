from django.urls import path

from .api_views import MembersByChurchListView

# Import views from their respective modules
from .views.member_views import MemberCreateView, MemberDetailAPIView, MemberView
from .views.visitor_views import VisitorDetailAPIView, VisitorToMemberView, VisitorView

app_name = "members"

urlpatterns = [
    # ==========================================
    # MEMBER ENDPOINTS
    # ==========================================
    path("create/", MemberCreateView.as_view(), name="member-create"),
    path("members/", MemberView.as_view(), name="member-list"),
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
