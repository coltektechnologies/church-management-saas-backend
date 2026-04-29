"""
Inject platform-wide KPIs into the Django admin index for staff.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone


def platform_dashboard_extra_context(request) -> dict[str, object]:
    """Numbers for the operations dashboard cards."""
    if not request.user.is_authenticated or not request.user.is_staff:
        return {}

    from accounts.models import Church, SubscriptionPlanSetting, User
    from notifications.models import SMSLog

    now = timezone.now()
    thirty_start = now - timedelta(days=30)

    churches_active = Church.objects.filter(deleted_at__isnull=True)

    totals = churches_active.aggregate(
        total=Count("id"),
        trial=Count("id", filter=Q(status="TRIAL")),
        suspended=Count("id", filter=Q(status="SUSPENDED")),
    )

    plan_breakdown = {
        row["subscription_plan"]: row["c"]
        for row in churches_active.values("subscription_plan").annotate(c=Count("id"))
    }

    sms_30 = SMSLog.objects.filter(created_at__gte=thirty_start).aggregate(
        segments=Sum("sms_count"),
        sends=Count("id"),
    )

    platform_staff = User.objects.filter(
        is_platform_admin=True,
        is_active=True,
        deleted_at__isnull=True,
    ).count()

    top_sms = (
        SMSLog.objects.filter(created_at__gte=thirty_start)
        .values("church_id", "church__name")
        .annotate(seg=Sum("sms_count"))
        .order_by("-seg")[:10]
    )

    try:
        plan_catalog = list(
            SubscriptionPlanSetting.objects.order_by("sort_order", "plan_code").values(
                "plan_code",
                "label",
                "is_active",
                "max_users_default",
                "sms_monthly_quota",
                "enforce_sms_quota",
            )
        )
    except Exception:
        plan_catalog = []

    return {
        "dashboard_show": True,
        "dashboard_churches_total": totals.get("total") or 0,
        "dashboard_churches_trial": totals.get("trial") or 0,
        "dashboard_churches_suspended": totals.get("suspended") or 0,
        "dashboard_plan_breakdown": plan_breakdown,
        "dashboard_sms_segments_30d": int(sms_30.get("segments") or 0),
        "dashboard_sms_count_30d": int(sms_30.get("sends") or 0),
        "dashboard_platform_admins": platform_staff,
        "dashboard_top_sms_churches": list(top_sms),
        "dashboard_plan_catalog": plan_catalog,
    }


def patch_admin_index():
    """Attach dashboard context + custom index template to the default admin site."""
    import types

    from django.contrib import admin
    from django.contrib.admin.sites import AdminSite

    site = admin.site
    if getattr(site, "_opendoor_dashboard_patched", False):
        return

    orig = AdminSite.index

    def index_with_dashboard(self, request, extra_context=None):
        extra_context = extra_context or {}
        if request.user.is_staff:
            extra_context.update(platform_dashboard_extra_context(request))
        return orig(self, request, extra_context)

    site.index = types.MethodType(index_with_dashboard, site)
    site._opendoor_dashboard_patched = True  # type: ignore[attr-defined]
    site.index_template = "admin/opendoor_index.html"
