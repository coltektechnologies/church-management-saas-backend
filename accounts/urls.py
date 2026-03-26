from django.urls import path

from .payments import initialize_payment, paystack_webhook, test_paystack
from .views import (
    ChangePasswordAPIView,
    ChurchDetailAPIView,
    ChurchGroupDetailAPIView,
    ChurchGroupMemberDetailAPIView,
    ChurchGroupMemberView,
    ChurchGroupView,
    ChurchPlatformAccessAPIView,
    ChurchView,
    LoginAPIView,
    PermissionDetailAPIView,
    PermissionView,
    RegisterAPIView,
    RoleDetailAPIView,
    RolePermissionDetailAPIView,
    RolePermissionView,
    RoleView,
    UserDetailAPIView,
    UserRoleDetailAPIView,
    UserRoleView,
    UserView,
    registration_initialize_payment,
    registration_payment_callback,
    registration_plans,
    registration_step1,
    registration_step2,
    registration_step3,
    registration_verify_payment,
)

app_name = "accounts"

urlpatterns = [
    # ==========================================
    # AUTHENTICATION ENDPOINTS
    # ==========================================
    path("login/", LoginAPIView.as_view(), name="login"),
    path("change-password/", ChangePasswordAPIView.as_view(), name="change-password"),
    path("register/", RegisterAPIView.as_view(), name="register"),
    # ==========================================
    # PAYMENT-FIRST REGISTRATION FLOW
    # ==========================================
    path(
        "registration/plans/",
        registration_plans,
        name="registration-plans",
    ),
    path(
        "registration/step1/",
        registration_step1,
        name="registration-step1",
    ),
    path(
        "registration/step2/",
        registration_step2,
        name="registration-step2",
    ),
    path(
        "registration/step3/",
        registration_step3,
        name="registration-step3",
    ),
    path(
        "registration/initialize-payment/",
        registration_initialize_payment,
        name="registration-initialize-payment",
    ),
    path(
        "registration/verify-payment/",
        registration_verify_payment,
        name="registration-verify-payment",
    ),
    path(
        "registration/payment-callback/",
        registration_payment_callback,
        name="registration-payment-callback",
    ),
    # ==========================================
    # CHURCH ENDPOINTS
    # ==========================================
    path("churches/", ChurchView.as_view(), name="church-list-create"),
    path(
        "churches/<uuid:pk>/platform-access/",
        ChurchPlatformAccessAPIView.as_view(),
        name="church-platform-access",
    ),
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
    # CHURCH GROUP ENDPOINTS
    # ==========================================
    path("church-groups/", ChurchGroupView.as_view(), name="church-group-list-create"),
    path(
        "church-groups/<uuid:pk>/",
        ChurchGroupDetailAPIView.as_view(),
        name="church-group-detail",
    ),
    path(
        "church-groups/<uuid:pk>/members/",
        ChurchGroupMemberView.as_view(),
        name="church-group-member-list-add",
    ),
    path(
        "church-groups/<uuid:pk>/members/<uuid:member_pk>/",
        ChurchGroupMemberDetailAPIView.as_view(),
        name="church-group-member-remove",
    ),
    # ==========================================
    # USER-ROLE MAPPING ENDPOINTS
    # ==========================================
    path("user-roles/", UserRoleView.as_view(), name="user-role-list-create"),
    path(
        "user-roles/<uuid:pk>/",
        UserRoleDetailAPIView.as_view(),
        name="user-role-detail",
    ),
    # ==========================================
    # PAYMENT ENDPOINTS
    # ==========================================
    path(
        "paystack/test/",
        test_paystack,
        name="test-paystack",
    ),
    path(
        "payments/initialize/",
        initialize_payment,
        name="initialize-payment",
    ),
    path(
        "webhooks/paystack/",
        paystack_webhook,
        name="paystack-webhook",
    ),
]
