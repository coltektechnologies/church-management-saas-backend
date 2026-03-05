"""
Backup & data export/import API. Platform admin only.
"""

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsPlatformAdmin
from backup.serializers import BackupRecordSerializer
from backup.services import BackupService, TenantExportImportService


def _platform_admin_required(request):
    if not request.user or not request.user.is_authenticated:
        return False
    return getattr(request.user, "is_platform_admin", False)


# ---------- Backup ----------


class BackupCreateView(APIView):
    permission_classes = [IsPlatformAdmin]

    @swagger_auto_schema(
        operation_description="Create a full database backup (dumpdata). Platform admin only.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={"notes": openapi.Schema(type=openapi.TYPE_STRING)},
        ),
        tags=["Admin - Backup"],
    )
    def post(self, request):
        notes = (request.data.get("notes") or "").strip()[:255]
        created_by_id = str(request.user.id) if request.user else None
        record, err = BackupService.create(created_by_id=created_by_id, notes=notes)
        if err:
            return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            BackupRecordSerializer(record).data, status=status.HTTP_201_CREATED
        )


class BackupListView(APIView):
    permission_classes = [IsPlatformAdmin]

    @swagger_auto_schema(
        operation_description="List full database backups. Platform admin only.",
        tags=["Admin - Backup"],
    )
    def get(self, request):
        records = BackupService.list_backups()
        return Response(BackupRecordSerializer(records, many=True).data)


class BackupRestoreView(APIView):
    permission_classes = [IsPlatformAdmin]

    @swagger_auto_schema(
        operation_description="Restore database from a backup by id. Destructive. Platform admin only.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=["backup_id"],
            properties={
                "backup_id": openapi.Schema(type=openapi.TYPE_STRING, format="uuid")
            },
        ),
        tags=["Admin - Backup"],
    )
    def post(self, request):
        backup_id = request.data.get("backup_id")
        if not backup_id:
            return Response(
                {"error": "backup_id required"}, status=status.HTTP_400_BAD_REQUEST
            )
        ok, err = BackupService.restore(backup_id)
        if not ok:
            return Response(
                {"error": err or "Restore failed"}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response({"status": "restored", "backup_id": backup_id})


# ---------- Tenant export (GDPR) ----------


class ExportTenantDataView(APIView):
    permission_classes = [IsPlatformAdmin]

    @swagger_auto_schema(
        operation_description="Export one church's data as JSON (GDPR-style). Platform admin only.",
        manual_parameters=[
            openapi.Parameter(
                "church_id",
                openapi.IN_QUERY,
                type=openapi.TYPE_STRING,
                format="uuid",
                required=True,
            )
        ],
        tags=["Admin - Export/Import"],
    )
    def get(self, request):
        church_id = request.query_params.get("church_id")
        if not church_id:
            return Response(
                {"error": "church_id required"}, status=status.HTTP_400_BAD_REQUEST
            )
        data, err = TenantExportImportService.export_tenant_data(church_id)
        if err:
            return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)
        from django.http import HttpResponse

        response = HttpResponse(data, content_type="application/json")
        response["Content-Disposition"] = (
            'attachment; filename="tenant_export_{}.json"'.format(church_id[:8])
        )
        return response


# ---------- Tenant import ----------


class ImportTenantDataView(APIView):
    permission_classes = [IsPlatformAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @swagger_auto_schema(
        operation_description="Import tenant data from JSON (export format). Optional target_church_id to migrate to another church. Platform admin only.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                "target_church_id": openapi.Schema(
                    type=openapi.TYPE_STRING, format="uuid"
                ),
                "data": openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    description="JSON export body (or send as file)",
                ),
            },
        ),
        tags=["Admin - Export/Import"],
    )
    def post(self, request):
        target_church_id = request.data.get(
            "target_church_id"
        ) or request.query_params.get("target_church_id")
        # Accept: JSON body (full export or {"data": ...}), or file upload
        data = None
        if request.FILES:
            file_obj = request.FILES.get("file") or request.FILES.get("data")
            if file_obj:
                data = file_obj.read()
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
        if data is None and request.data:
            import json as _json

            raw = request.data
            if isinstance(raw, dict):
                if "objects" in raw or "export_meta" in raw:
                    data = _json.dumps(raw)
                else:
                    data = raw.get("data")
                    if isinstance(data, dict):
                        data = _json.dumps(data)
                    elif data is not None:
                        data = str(data)
            else:
                data = _json.dumps(raw) if not isinstance(raw, str) else raw
        if data is None and request.body:
            data = (
                request.body.decode("utf-8")
                if isinstance(request.body, bytes)
                else request.body
            )
        if not data:
            return Response(
                {
                    "error": "No data provided (send JSON body, or 'data' key, or 'file' upload)"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        count, err = TenantExportImportService.import_tenant_data(
            data, target_church_id=target_church_id
        )
        if err:
            return Response(
                {"error": err, "loaded": count}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response({"status": "imported", "objects_loaded": count})
