from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("members.urls")),
    path("api/", include("departments.urls")),
    path("api/", include("secretariat.urls")),
    path("api/", include("treasury.urls")),
    path("api/", include("announcements.urls")),
    path("api/", include("notifications.urls")),
    path("api/auth/", include("accounts.urls")),
]
