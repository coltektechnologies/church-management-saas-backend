"""
Platform-operator pages (superuser / is_platform_admin): church directory & subscription alerts.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib import admin as django_admin
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Church


def _platform_operator(user) -> bool:
    return bool(
        user.is_authenticated
        and user.is_staff
        and (user.is_superuser or getattr(user, "is_platform_admin", False))
    )


def _guard(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return redirect("admin:login")
    if not _platform_operator(request.user):
        return HttpResponseForbidden(
            "Platform operators only (superuser or platform admin)."
        )
    return None


def platform_directory_view(request):
    """All churches with user/member counts, subscription summary, quick links."""
    denied = _guard(request)
    if denied:
        return denied

    from django.db.models import OuterRef, Subquery
    from django.db.models.functions import Coalesce

    from notifications.models import SMSLog

    thirty = timezone.now() - timedelta(days=30)
    seg_sq = (
        SMSLog.objects.filter(
            church_id=OuterRef("pk"),
            created_at__gte=thirty,
        )
        .values("church_id")
        .annotate(s=Sum("sms_count"))
        .values("s")[:1]
    )

    churches = (
        Church.objects.filter(deleted_at__isnull=True)
        .annotate(
            dir_member_count=Count(
                "members",
                filter=Q(members__deleted_at__isnull=True),
                distinct=True,
            ),
            dir_user_count=Count(
                "users",
                filter=Q(users__is_active=True),
                distinct=True,
            ),
            dir_sms30=Coalesce(Subquery(seg_sq), 0),
        )
        .order_by("name")
    )

    context = {
        **django_admin.site.each_context(request),
        "title": "Platform church directory",
        "churches": churches,
        "opts": Church._meta,
    }
    return render(request, "admin/accounts/church/platform_directory.html", context)


@require_POST
def toggle_platform_access_view(request, church_id):
    """Turn tenant API/login access on or off (platform_access_enabled)."""
    denied = _guard(request)
    if denied:
        return denied

    church = get_object_or_404(Church, pk=church_id, deleted_at__isnull=True)
    enabled_raw = (request.POST.get("enabled") or "").strip().lower()
    if enabled_raw not in ("true", "false"):
        messages.error(request, "Invalid access toggle request.")
        return redirect("admin:accounts_church_platform_directory")

    church.platform_access_enabled = enabled_raw == "true"
    church.save(update_fields=["platform_access_enabled", "updated_at"])

    if church.platform_access_enabled:
        messages.success(
            request,
            f"Access enabled for “{church.name}”. Users can log in and use the API again.",
        )
    else:
        messages.warning(
            request,
            f"Access blocked for “{church.name}”. Users cannot log in or call the API until re-enabled.",
        )
    return redirect("admin:accounts_church_platform_directory")


def subscription_reminders_view(request):
    """Churches expiring soon vs already expired + send reminder emails."""
    denied = _guard(request)
    if denied:
        return denied

    now = timezone.now()
    horizon = now + timedelta(days=14)

    base = Church.objects.filter(deleted_at__isnull=True)

    expiring_soon = (
        base.filter(
            Q(
                status="TRIAL",
                trial_ends_at__gte=now,
                trial_ends_at__lte=horizon,
            )
            | Q(
                subscription_ends_at__isnull=False,
                subscription_ends_at__gte=now,
                subscription_ends_at__lte=horizon,
            )
        )
        .distinct()
        .order_by("trial_ends_at", "subscription_ends_at", "name")
    )

    expired_or_blocked = (
        base.filter(
            Q(status="TRIAL", trial_ends_at__lt=now)
            | Q(subscription_ends_at__isnull=False, subscription_ends_at__lt=now)
            | Q(status__in=("SUSPENDED", "INACTIVE"))
        )
        .distinct()
        .order_by("-subscription_ends_at", "-trial_ends_at", "name")
    )

    context = {
        **django_admin.site.each_context(request),
        "title": "Subscription & trial reminders",
        "expiring_soon": expiring_soon,
        "expired_or_blocked": expired_or_blocked,
        "opts": Church._meta,
        "now": now,
        "horizon_days": 14,
    }
    return render(request, "admin/accounts/church/subscription_reminders.html", context)


@require_POST
def send_subscription_reminder_view(request, church_id):
    denied = _guard(request)
    if denied:
        return denied

    church = get_object_or_404(Church, pk=church_id, deleted_at__isnull=True)
    redirect_to = reverse("admin:accounts_church_subscription_reminders")

    if not church.email:
        messages.error(request, f"No contact email on file for “{church.name}”.")
        return redirect(redirect_to)

    lines = [
        "This is a reminder regarding your church account on our platform.",
        "",
        f"Church: {church.name}",
        f"Plan: {church.subscription_plan} ({church.status})",
    ]
    if church.trial_ends_at:
        lines.append(f"Trial ends: {church.trial_ends_at.isoformat()}")
    if church.subscription_ends_at:
        lines.append(f"Subscription ends: {church.subscription_ends_at.isoformat()}")
    lines.extend(
        [
            "",
            "Please renew or upgrade before access is affected.",
            "",
            f"— {getattr(settings, 'PLATFORM_EMAIL_SIGNOFF', 'Platform team')}",
        ]
    )
    body = "\n".join(lines)
    subject = getattr(
        settings,
        "SUBSCRIPTION_REMINDER_EMAIL_SUBJECT",
        "Reminder: subscription or trial ending",
    )

    try:
        from django.core.mail import send_mail

        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [church.email],
            fail_silently=False,
        )
        Church.objects.filter(pk=church.pk).update(
            last_subscription_reminder_at=timezone.now()
        )
        messages.success(
            request,
            f"Reminder sent to {church.email} for “{church.name}”.",
        )
    except Exception as exc:
        messages.error(request, f"Could not send email: {exc}")

    return redirect(redirect_to)
