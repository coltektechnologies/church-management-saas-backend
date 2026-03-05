from django.urls import path

from .views import (BackupCreateView, BackupListView, BackupRestoreView,
                    ExportTenantDataView, ImportTenantDataView)

app_name = "backup"

urlpatterns = [
    path("backup/create/", BackupCreateView.as_view(), name="backup-create"),
    path("backup/list/", BackupListView.as_view(), name="backup-list"),
    path("backup/restore/", BackupRestoreView.as_view(), name="backup-restore"),
    path(
        "export/tenant-data/", ExportTenantDataView.as_view(), name="export-tenant-data"
    ),
    path(
        "import/tenant-data/", ImportTenantDataView.as_view(), name="import-tenant-data"
    ),
]
