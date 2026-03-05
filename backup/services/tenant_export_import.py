"""
Tenant (church) data export (GDPR-style) and import for migration/restore.
Exports all church-related data as JSON; import creates/updates records.
"""

import json
import logging
from io import BytesIO, StringIO

from django.core import serializers
from django.db import transaction

from accounts.models import Church

logger = logging.getLogger(__name__)

# Models that belong to a church (app_label, model_name, church FK field)
TENANT_MODELS = [
    ("accounts", "User", "church"),
    ("accounts", "ChurchGroup", "church"),
    ("accounts", "ChurchGroupMember", "group__church"),
    ("accounts", "AuditLog", "church"),
    ("members", "Member", "church"),
    ("departments", "Department", "church"),
    ("departments", "MemberDepartment", "church"),
    ("departments", "DepartmentHead", "church"),
    ("departments", "Program", "church"),
    ("departments", "ProgramBudgetItem", "program__church"),
    ("treasury", "IncomeCategory", "church"),
    ("treasury", "IncomeTransaction", "church"),
    ("treasury", "IncomeAllocation", "transaction__church"),
    ("treasury", "ExpenseCategory", "church"),
    ("treasury", "ExpenseTransaction", "church"),
    ("treasury", "ExpenseRequest", "church"),
    ("treasury", "Asset", "church"),
    ("announcements", "AnnouncementCategory", "church"),
    ("announcements", "AnnouncementTemplate", "church"),
    ("announcements", "Announcement", "church"),
    ("files", "ChurchFile", "church"),
    ("reports", "ReportCache", "church"),
    ("reports", "ScheduledReport", "church"),
    ("analytics", "AnalyticsDashboardInfo", None),  # no church FK; skip or export all
]
# Skip analytics dashboard info for tenant export (global config)
TENANT_MODELS = [(a, m, f) for a, m, f in TENANT_MODELS if f]


def get_tenant_querysets(church_id):
    """Yield (model_label, queryset) for all tenant models filtered by church."""
    from django.apps import apps

    for app_label, model_name, church_attr in TENANT_MODELS:
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        if not church_attr:
            continue
        filter_kw = {church_attr: church_id}
        try:
            qs = model.objects.filter(**filter_kw)
            yield f"{app_label}.{model_name}", qs
        except Exception as e:
            logger.warning("Tenant export skip %s.%s: %s", app_label, model_name, e)


class TenantExportImportService:
    """Export one church's data to JSON; import from JSON (with optional target church)."""

    @staticmethod
    def export_tenant_data(church_id, include_church_meta=True):
        """
        Export all tenant data for the given church as JSON string.
        include_church_meta: include the Church record itself (so export is self-contained).
        """
        try:
            church = Church.objects.get(id=church_id)
        except Church.DoesNotExist:
            return None, "Church not found"

        all_objs = []
        for _model_label, qs in get_tenant_querysets(church_id):
            all_objs.extend(list(qs))
        if include_church_meta:
            all_objs.append(church)
        fixture_json = serializers.serialize(
            "json", all_objs, use_natural_foreign_keys=True
        )
        payload = {
            "export_meta": {
                "church_id": str(church_id),
                "church_name": church.name or "",
            },
            "objects": json.loads(fixture_json),
        }
        return json.dumps(payload, indent=2), None

    @staticmethod
    def import_tenant_data(data, target_church_id=None):
        """
        Import from JSON produced by export_tenant_data.
        data: str or bytes. target_church_id: if set, remap all church FKs to this church (for migration).
        Returns (count_loaded, error_message). error_message is None on success.
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as e:
            return 0, f"Invalid JSON: {e}"

        objects = payload.get("objects") or payload.get("object_list") or []
        if not objects:
            return 0, "No objects in export"

        export_meta = payload.get("export_meta") or {}
        source_church_id = export_meta.get("church_id")
        if (
            target_church_id
            and source_church_id
            and str(target_church_id) != str(source_church_id)
        ):
            remap_church = True
            target_church_id = str(target_church_id)
        else:
            remap_church = False
            target_church_id = str(source_church_id) if source_church_id else None

        count = 0
        try:
            with transaction.atomic():
                for item in objects:
                    try:
                        stream = StringIO(json.dumps([item]))
                        for obj in serializers.deserialize("json", stream):
                            if (
                                remap_church
                                and target_church_id
                                and hasattr(obj.object, "church_id")
                            ):
                                obj.object.church_id = target_church_id
                            obj.save()
                            count += 1
                    except Exception as e:
                        logger.warning("Import skip object %s: %s", item.get("pk"), e)
            return count, None
        except Exception as e:
            return count, str(e)
