from django.urls import path

from .views import MemberDetailAPIView  # Member views; Visitor views
from .views import (MemberView, VisitorDetailAPIView, VisitorToMemberView,
                    VisitorView)

app_name = "members"

urlpatterns = [
    # ==========================================
    # MEMBER ENDPOINTS
    # ==========================================
    path("members/", MemberView.as_view(), name="member-list-create"),
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
]
