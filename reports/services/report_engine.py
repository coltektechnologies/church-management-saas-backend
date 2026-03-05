"""
Generic report generation service with filtering, date ranges, and caching.
"""

import hashlib
import json
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

from django.core.cache import cache
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.models import Church
from accounts.models.base_models import AuditLog
from announcements.models import Announcement
from departments.models import Department, MemberDepartment
from members.models import Member
from reports.models import ReportCache
from treasury.models import (ExpenseCategory, ExpenseTransaction,
                             IncomeCategory, IncomeTransaction)

logger = logging.getLogger(__name__)

# Default cache TTL in seconds (1 hour for reports)
REPORT_CACHE_TTL = 3600
# DB cache expiry: keep cached rows for 24h
REPORT_CACHE_EXPIRY_HOURS = 24


def _date_range_defaults(date_from: Optional[date], date_to: Optional[date]):
    """Return (date_from, date_to) with sensible defaults (e.g. start/end of current month)."""
    today = timezone.localdate()
    if date_from is None:
        date_from = today.replace(day=1)
    if date_to is None:
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return date_from, date_to


def _filter_hash(filters: dict) -> str:
    """Stable hash of filter dict for cache key."""
    canonical = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _cache_key(
    church_id: str, report_type: str, date_from: date, date_to: date, filters: dict
) -> str:
    fh = _filter_hash(filters)
    return f"report:{church_id}:{report_type}:{date_from}:{date_to}:{fh}"


class ReportGenerationService:
    """
    Central service for generating report data. Supports:
    - Date range filtering
    - Optional extra filters (dict)
    - In-memory (Django cache) and DB (ReportCache) caching
    """

    def __init__(self, church: Church):
        self.church = church
        self.church_id_str = str(church.id)

    def get_cached(
        self, report_type: str, date_from: date, date_to: date, filters: dict
    ) -> Optional[dict]:
        """Return cached result from Django cache or ReportCache if valid."""
        key = _cache_key(self.church_id_str, report_type, date_from, date_to, filters)
        # 1) In-memory cache
        data = cache.get(key)
        if data is not None:
            return data
        # 2) DB cache (non-expired)
        try:
            rc = ReportCache.objects.get(cache_key=key)
            if not rc.is_expired:
                cache.set(key, rc.result_data, REPORT_CACHE_TTL)
                return rc.result_data
        except ReportCache.DoesNotExist:
            pass
        return None

    def set_cached(
        self,
        report_type: str,
        date_from: date,
        date_to: date,
        filters: dict,
        result_data: dict,
    ) -> None:
        """Store result in Django cache and ReportCache."""
        key = _cache_key(self.church_id_str, report_type, date_from, date_to, filters)
        expires_at = timezone.now() + timedelta(hours=REPORT_CACHE_EXPIRY_HOURS)
        cache.set(key, result_data, REPORT_CACHE_TTL)
        ReportCache.objects.update_or_create(
            church=self.church,
            cache_key=key,
            defaults={
                "report_type": report_type,
                "result_data": result_data,
                "date_from": date_from,
                "date_to": date_to,
                "expires_at": expires_at,
            },
        )

    def get_report(
        self,
        report_type: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        filters: Optional[dict] = None,
        use_cache: bool = True,
    ) -> dict:
        """
        Generate or return cached report. filters is passed to report builders
        (e.g. status, department_id). Returns dict with 'data', 'meta' (date range, generated_at).
        """
        filters = filters or {}
        date_from, date_to = _date_range_defaults(date_from, date_to)

        if use_cache:
            cached = self.get_cached(report_type, date_from, date_to, filters)
            if cached is not None:
                return cached

        builder = _REPORT_BUILDERS.get(report_type)
        if not builder:
            return {
                "data": None,
                "meta": {
                    "report_type": report_type,
                    "date_from": str(date_from),
                    "date_to": str(date_to),
                    "error": f"Unknown report type: {report_type}",
                },
            }

        try:
            result = builder(self.church, date_from, date_to, filters)
        except Exception as e:
            logger.exception("Report generation failed: %s", e)
            result = {
                "data": None,
                "meta": {
                    "report_type": report_type,
                    "date_from": str(date_from),
                    "date_to": str(date_to),
                    "error": str(e),
                },
            }

        result.setdefault("meta", {})
        result["meta"].update(
            {
                "report_type": report_type,
                "date_from": str(date_from),
                "date_to": str(date_to),
                "generated_at": timezone.now().isoformat(),
            }
        )

        if use_cache and result.get("data") is not None:
            self.set_cached(report_type, date_from, date_to, filters, result)

        return result


# ---------- Report builders (church, date_from, date_to, filters) -> dict ----------


def _report_members(
    church: Church, date_from: date, date_to: date, filters: dict
) -> dict:
    qs = Member.objects.filter(church=church).filter(deleted_at__isnull=True)
    status = filters.get("membership_status")
    if status:
        qs = qs.filter(membership_status=status)
    total = qs.count()
    # Optional: filter by member_since in range
    in_range = qs.filter(
        member_since__gte=date_from,
        member_since__lte=date_to,
    ).count()
    members_list = []
    for m in qs[:500]:
        members_list.append(
            {
                "id": str(m.id),
                "first_name": m.first_name,
                "last_name": m.last_name,
                "gender": m.gender,
                "membership_status": m.membership_status,
                "member_since": m.member_since.isoformat() if m.member_since else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )
    return {
        "data": {
            "total": total,
            "joined_in_period": in_range,
            "members": members_list,
        },
    }


def _report_members_growth(
    church: Church, date_from: date, date_to: date, filters: dict
) -> dict:
    qs = Member.objects.filter(church=church, deleted_at__isnull=True)
    # Count by month in range
    by_month = (
        qs.filter(member_since__gte=date_from, member_since__lte=date_to)
        .annotate(month=TruncMonth("member_since"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    cumulative = 0
    series = []
    for row in by_month:
        cumulative += row["count"]
        m = row.get("month")
        series.append(
            {
                "month": m.strftime("%Y-%m") if m else None,
                "new_members": row["count"],
                "cumulative": cumulative,
            }
        )
    total_in_period = sum(r["new_members"] for r in series)
    return {
        "data": {
            "date_from": str(date_from),
            "date_to": str(date_to),
            "total_new_members": total_in_period,
            "by_month": series,
        },
    }


def _report_members_demographics(
    church: Church, date_from: date, date_to: date, filters: dict
) -> dict:
    qs = Member.objects.filter(church=church, deleted_at__isnull=True)
    by_gender = list(qs.values("gender").annotate(count=Count("id")))
    by_status = list(qs.values("membership_status").annotate(count=Count("id")))
    by_marital = list(
        qs.values("marital_status")
        .annotate(count=Count("id"))
        .exclude(marital_status__isnull=True)
        .exclude(marital_status="")
    )
    by_baptism = list(
        qs.values("baptism_status")
        .annotate(count=Count("id"))
        .exclude(baptism_status__isnull=True)
        .exclude(baptism_status="")
    )
    return {
        "data": {
            "by_gender": by_gender,
            "by_membership_status": by_status,
            "by_marital_status": by_marital,
            "by_baptism_status": by_baptism,
            "total": qs.count(),
        },
    }


def _report_departments(
    church: Church, date_from: date, date_to: date, filters: dict
) -> dict:
    depts = Department.objects.filter(church=church, deleted_at__isnull=True)
    list_data = []
    for d in depts:
        member_count = MemberDepartment.objects.filter(
            department=d, deleted_at__isnull=True
        ).count()
        list_data.append(
            {
                "id": str(d.id),
                "name": d.name,
                "code": d.code,
                "member_count": member_count,
                "is_active": d.is_active,
            }
        )
    return {
        "data": {
            "departments": list_data,
            "total_departments": len(list_data),
        },
    }


def _report_finance_income(
    church: Church, date_from: date, date_to: date, filters: dict
) -> dict:
    qs = IncomeTransaction.objects.filter(
        church=church,
        transaction_date__gte=date_from,
        transaction_date__lte=date_to,
        deleted_at__isnull=True,
    )
    total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    by_category = list(
        qs.values("category__name", "category__code")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    return {
        "data": {
            "total_income": str(total),
            "date_from": str(date_from),
            "date_to": str(date_to),
            "by_category": [
                {
                    "name": x["category__name"],
                    "code": x["category__code"],
                    "total": str(x["total"]),
                    "count": x["count"],
                }
                for x in by_category
            ],
            "transaction_count": qs.count(),
        },
    }


def _report_finance_expenses(
    church: Church, date_from: date, date_to: date, filters: dict
) -> dict:
    qs = ExpenseTransaction.objects.filter(
        church=church,
        transaction_date__gte=date_from,
        transaction_date__lte=date_to,
        deleted_at__isnull=True,
    )
    total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    by_category = list(
        qs.values("category__name", "category__code")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    return {
        "data": {
            "total_expenses": str(total),
            "date_from": str(date_from),
            "date_to": str(date_to),
            "by_category": [
                {
                    "name": x["category__name"],
                    "code": x["category__code"],
                    "total": str(x["total"]),
                    "count": x["count"],
                }
                for x in by_category
            ],
            "transaction_count": qs.count(),
        },
    }


def _report_finance_balance_sheet(
    church: Church, date_from: date, date_to: date, filters: dict
) -> dict:
    income_qs = IncomeTransaction.objects.filter(
        church=church,
        transaction_date__gte=date_from,
        transaction_date__lte=date_to,
        deleted_at__isnull=True,
    )
    expense_qs = ExpenseTransaction.objects.filter(
        church=church,
        transaction_date__gte=date_from,
        transaction_date__lte=date_to,
        deleted_at__isnull=True,
    )
    total_income = income_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    total_expense = expense_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    net = total_income - total_expense
    return {
        "data": {
            "date_from": str(date_from),
            "date_to": str(date_to),
            "total_income": str(total_income),
            "total_expenses": str(total_expense),
            "net_position": str(net),
        },
    }


def _report_finance_cash_flow(
    church: Church, date_from: date, date_to: date, filters: dict
) -> dict:
    income_qs = IncomeTransaction.objects.filter(
        church=church,
        transaction_date__gte=date_from,
        transaction_date__lte=date_to,
        deleted_at__isnull=True,
    )
    expense_qs = ExpenseTransaction.objects.filter(
        church=church,
        transaction_date__gte=date_from,
        transaction_date__lte=date_to,
        deleted_at__isnull=True,
    )
    total_in = income_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    total_out = expense_qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
    net_cash_flow = total_in - total_out
    return {
        "data": {
            "date_from": str(date_from),
            "date_to": str(date_to),
            "cash_inflow": str(total_in),
            "cash_outflow": str(total_out),
            "net_cash_flow": str(net_cash_flow),
        },
    }


def _report_announcements(
    church: Church, date_from: date, date_to: date, filters: dict
) -> dict:
    dt_from = timezone.make_aware(
        timezone.datetime.combine(date_from, timezone.datetime.min.time())
    )
    dt_to = timezone.make_aware(
        timezone.datetime.combine(date_to, timezone.datetime.max.time())
    )
    qs = Announcement.objects.filter(
        church=church,
        created_at__gte=dt_from,
        created_at__lte=dt_to,
    )
    status = filters.get("status")
    if status:
        qs = qs.filter(status=status)
    by_status = list(qs.values("status").annotate(count=Count("id")))
    list_data = list(qs.values("id", "title", "status", "priority", "created_at")[:200])
    for r in list_data:
        r["id"] = str(r["id"])
        if r.get("created_at"):
            r["created_at"] = r["created_at"].isoformat()
    return {
        "data": {
            "total": qs.count(),
            "by_status": by_status,
            "announcements": list_data,
        },
    }


def _report_audit_trail(
    church: Church, date_from: date, date_to: date, filters: dict
) -> dict:
    dt_from = timezone.make_aware(
        timezone.datetime.combine(date_from, timezone.datetime.min.time())
    )
    dt_to = timezone.make_aware(
        timezone.datetime.combine(date_to, timezone.datetime.max.time())
    )
    qs = (
        AuditLog.objects.filter(
            church=church,
            created_at__gte=dt_from,
            created_at__lte=dt_to,
        )
        .select_related("user")
        .order_by("-created_at")[:500]
    )
    list_data = []
    for log in qs:
        list_data.append(
            {
                "id": str(log.id),
                "action": log.action,
                "model_name": log.model_name,
                "object_id": log.object_id,
                "description": log.description,
                "user_id": str(log.user_id) if log.user_id else None,
                "user_email": log.user.email if log.user else None,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
        )
    return {
        "data": {
            "total": len(list_data),
            "entries": list_data,
        },
    }


_REPORT_BUILDERS = {
    "members": _report_members,
    "members_growth": _report_members_growth,
    "members_demographics": _report_members_demographics,
    "departments": _report_departments,
    "finance_income": _report_finance_income,
    "finance_expenses": _report_finance_expenses,
    "finance_balance_sheet": _report_finance_balance_sheet,
    "finance_cash_flow": _report_finance_cash_flow,
    "announcements": _report_announcements,
    "audit_trail": _report_audit_trail,
}
