from django.urls import path

from .views import (  # Church views; User views; Authentication views; Role views; Permission views; Role-Permission views; User-Role views
    ChangePasswordAPIView, ChurchDetailAPIView, ChurchView, LoginAPIView,
    PermissionDetailAPIView, PermissionView, RegisterAPIView,
    RoleDetailAPIView, RolePermissionDetailAPIView, RolePermissionView,
    RoleView, UserDetailAPIView, UserRoleDetailAPIView, UserRoleView, UserView)

app_name = "accounts"

urlpatterns = [
    # ==========================================
    # AUTHENTICATION ENDPOINTS
    # ==========================================
    path("login/", LoginAPIView.as_view(), name="login"),
    path("change-password/", ChangePasswordAPIView.as_view(), name="change-password"),
    path("register/", RegisterAPIView.as_view(), name="register"),
    # ==========================================
    # CHURCH ENDPOINTS
    # ==========================================
    path("churches/", ChurchView.as_view(), name="church-list-create"),
    path("churches/<uuid:pk>/", ChurchDetailAPIView.as_view(), name="church-detail"),
    # ==========================================
    # USER ENDPOINTS
    # ==========================================
    path("users/", UserView.as_view(), name="user-list-create"),
    path("users/<uuid:pk>/", UserDetailAPIView.as_view(), name="user-detail"),
    # ==========================================
    # ROLE ENDPOINTS
    # ==========================================
    path("roles/", RoleView.as_view(), name="role-list-create"),
    path("roles/<uuid:pk>/", RoleDetailAPIView.as_view(), name="role-detail"),
    # ==========================================
    # PERMISSION ENDPOINTS
    # ==========================================
    path("permissions/", PermissionView.as_view(), name="permission-list-create"),
    path(
        "permissions/<uuid:pk>/",
        PermissionDetailAPIView.as_view(),
        name="permission-detail",
    ),
    # ==========================================
    # ROLE-PERMISSION MAPPING ENDPOINTS
    # ==========================================
    path(
        "role-permissions/",
        RolePermissionView.as_view(),
        name="role-permission-list-create",
    ),
    path(
        "role-permissions/<int:pk>/",
        RolePermissionDetailAPIView.as_view(),
        name="role-permission-detail",
    ),
    # ==========================================
    # USER-ROLE MAPPING ENDPOINTS
    # ==========================================
    path("user-roles/", UserRoleView.as_view(), name="user-role-list-create"),
    path(
        "user-roles/<int:pk>/", UserRoleDetailAPIView.as_view(), name="user-role-detail"
    ),
]
