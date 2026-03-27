from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# Enhanced Swagger schema view
schema_view = get_schema_view(
    openapi.Info(
        title="Church Management SAAS API",
        default_version="1.0",
        description="""
        # Church Management System API Documentation

        Complete REST API for managing church operations including:

        ## Features
        - **🏛️ Churches**: Multi-tenant church management
        - **👥 Members**: Member registration, profiles, and management
        - **💰 Treasury**: Financial tracking, income/expense recording, budgeting
        - **📢 Secretariat**: Announcements, communications, records
        - **🏢 Departments**: Department management and assignments
        - **🔐 Users & Roles**: Authentication, authorization, permissions

        ## Authentication
        This API uses **JWT (JSON Web Token)** authentication.

        ### How to Authenticate:
        1. **Login**: POST to `/api/auth/login/` with email, password, and church_id
        2. **Get Token**: Receive `access` and `refresh` tokens
        3. **Use Token**: Include in headers: `Authorization: Bearer <access_token>`
        4. **Refresh**: Use refresh token at `/api/token/refresh/` when access expires
        5. **Logout**: POST to `/api/auth/logout/` with `Authorization: Bearer <access_token>` and body `{"refresh": "<refresh_token>"}` to blacklist the refresh token

        ## Multi-Tenancy
        - Each church operates as an independent tenant
        - Regular users can only access their church's data
        - Platform admins can access all churches using `?church_id=<uuid>` parameter

        ## API Conventions
        - All IDs are UUIDs
        - Timestamps in ISO 8601 format
        - Soft deletes (deleted_at field)
        - Pagination on list endpoints (page size: 50)

        ## Support
        For issues or questions, contact: support@churchsaas.com
        """,
        terms_of_service="https://www.churchsaas.com/terms/",
        contact=openapi.Contact(email="support@churchsaas.com"),
        license=openapi.License(name="Proprietary License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    # ==========================================
    # ADMIN PANEL
    # ==========================================
    path("admin/", admin.site.urls),
    path("django-rq/", include("django_rq.urls")),
    # ==========================================
    # API DOCUMENTATION
    # ==========================================
    path("", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("api/docs/", schema_view.with_ui("swagger", cache_timeout=0), name="api-docs"),
    path("api/docs.json", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path(
        "api/redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"
    ),
    # ==========================================
    # API ENDPOINTS
    # ==========================================
    # API Endpoints
    path("api/auth/", include("accounts.urls")),
    path("api/members/", include("members.urls")),
    path("api/announcements/", include("announcements.urls")),
    path("api/treasury/", include("treasury.urls")),
    path("api/notifications/", include("notifications.urls")),
    # Departments mounted at api/ so router's 'departments/' gives api/departments/... (not api/departments/departments/...)
    path("api/", include("departments.urls")),
    path("api/reports/", include("reports.urls")),
    path("api/analytics/", include("analytics.urls")),
    path("api/files/", include("files.urls")),
    path("api/admin/", include("backup.urls")),
    path("api/activity/", include("core.urls_api")),
    path("", include("core.urls")),
    path("api/notifications/", include("notifications.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
