from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Church

from .models import AgentAlert, AgentLog

# Display order + cron strings aligned with churchagents `scheduler/celery_app.py` beat_schedule.
_AGENT_SCHEDULE_ROWS: list[dict[str, str | bool]] = [
    {
        "id": "orch",
        "agent_name": "OrchestratorAgent",
        "is_enabled": True,
        "cron_expr": "0 7 * * *",
    },
    {
        "id": "sub",
        "agent_name": "SubscriptionWatchdogAgent",
        "is_enabled": True,
        "cron_expr": "0 */6 * * *",
    },
    {
        "id": "tre",
        "agent_name": "TreasuryHealthAgent",
        "is_enabled": True,
        "cron_expr": "0 */12 * * *",
    },
    {
        "id": "mem",
        "agent_name": "MemberCareAgent",
        "is_enabled": True,
        "cron_expr": "0 8 * * *",
    },
    {
        "id": "dep",
        "agent_name": "DepartmentProgramAgent",
        "is_enabled": True,
        "cron_expr": "0 */12 * * *",
    },
    {
        "id": "ann",
        "agent_name": "AnnouncementAgent",
        "is_enabled": True,
        "cron_expr": "0 9 * * *",
    },
    {
        "id": "aud",
        "agent_name": "AuditSecurityAgent",
        "is_enabled": True,
        "cron_expr": "0 * * * *",
    },
    {
        "id": "sec",
        "agent_name": "SecretariatAgent",
        "is_enabled": True,
        "cron_expr": "0 7 * * *",
    },
]
from .permissions import IsPlatformStaffOrAgentCaller
from .serializers import (
    AgentAlertCreateSerializer,
    AgentAlertSerializer,
    AgentLogCreateSerializer,
    AgentLogSerializer,
)


class AgentLogListCreateView(generics.ListCreateAPIView):
    """GET list + POST create agent run logs."""

    queryset = AgentLog.objects.select_related("church").all()
    permission_classes = [IsPlatformStaffOrAgentCaller]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AgentLogCreateSerializer
        return AgentLogSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            {"id": str(instance.id), "created": True},
            status=status.HTTP_201_CREATED,
        )


class AgentAlertListCreateView(generics.ListCreateAPIView):
    queryset = AgentAlert.objects.select_related("church").all()
    permission_classes = [IsPlatformStaffOrAgentCaller]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AgentAlertCreateSerializer
        return AgentAlertSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        return Response(
            {"id": str(instance.id), "created": True},
            status=status.HTTP_201_CREATED,
        )


def _answer_security_alerts(request) -> str:
    """Summarize AgentAlert rows (scoped like other platform views)."""
    qs = AgentAlert.objects.select_related("church").order_by("-created_at")
    if not getattr(request.user, "is_platform_admin", False):
        cid = getattr(request.user, "church_id", None)
        if cid:
            qs = qs.filter(church_id=cid)
        else:
            return "Your account has no church scope; only platform admins can see org-wide alerts."
    alerts = list(qs[:25])
    if not alerts:
        return (
            "There are no agent alerts in the database yet (AgentAlert is empty). "
            "Check the dashboard Security tab for audit/activity logs, or run agents that raise alerts."
        )
    lines = []
    for a in alerts:
        cn = a.church.name if a.church else "platform-wide"
        msg = (a.message or "").replace("\n", " ")
        if len(msg) > 240:
            msg = msg[:237] + "..."
        lines.append(
            f"- [{a.severity}] {a.agent_name} · {a.alert_type}: {msg} "
            f"({cn}, {a.created_at.isoformat()})"
        )
    return "Recent agent alerts (up to 25):\n" + "\n".join(lines)


def _fallback_ask_answer(request, question: str) -> str:
    """Lightweight answers when no external orchestrator URL is configured."""
    q = question.lower()

    security_keywords = (
        "security",
        "alert",
        "audit",
        "breach",
        "anomaly",
        "suspicious",
        "intrusion",
    )
    if any(k in q for k in security_keywords):
        return _answer_security_alerts(request)

    subscription_keywords = (
        "expir",
        "subscription",
        "renew",
        "trial",
        "billing",
        "church",
    )
    if not any(k in q for k in subscription_keywords):
        return (
            "No AI orchestrator is linked to this API (CHURCHAGENTS_ORCHESTRATOR_URL is unset). "
            "Try questions about subscriptions (expiring churches), security alerts, or use the dashboard tabs. "
            "For open-ended AI answers, deploy `orchestrator_server` and set CHURCHAGENTS_ORCHESTRATOR_URL."
        )

    now = timezone.now()
    week_end = now + timedelta(days=7)
    qs = Church.objects.filter(deleted_at__isnull=True).exclude(
        subscription_ends_at__isnull=True
    )
    if not getattr(request.user, "is_platform_admin", False):
        cid = getattr(request.user, "church_id", None)
        if cid:
            qs = qs.filter(pk=cid)
        else:
            return "Your account has no church scope; only platform admins can list all churches."

    qs = qs.filter(
        subscription_ends_at__gte=now,
        subscription_ends_at__lte=week_end,
    ).order_by("subscription_ends_at")
    if not qs.exists():
        return (
            "No churches have a subscription end date falling in the next 7 days "
            "(based on subscription_ends_at)."
        )
    lines = []
    for c in qs[:100]:
        lines.append(
            f"- {c.name}: subscription_ends_at={c.subscription_ends_at.isoformat()} "
            f"(plan={c.subscription_plan}, status={c.status})"
        )
    return "Churches with subscription_ends_at in the next 7 days:\n" + "\n".join(lines)


class AgentScheduleListView(APIView):
    """
    GET — one row per known agent with cron hint + latest AgentLog (last run / status).

    Populated from DB logs; schedules are not stored separately — Celery drives real execution.
    """

    permission_classes = [IsPlatformStaffOrAgentCaller]

    def get(self, request):
        results = []
        for row in _AGENT_SCHEDULE_ROWS:
            agent_name = str(row["agent_name"])
            log = (
                AgentLog.objects.filter(agent_name=agent_name)
                .order_by("-created_at")
                .only("status", "created_at")
                .first()
            )
            last_run = log.created_at if log else None
            if log:
                last_status = log.status
            elif agent_name == "OrchestratorAgent":
                last_status = "Configure Celery beat"
            else:
                last_status = ""
            results.append(
                {
                    "id": row["id"],
                    "agent_name": agent_name,
                    "is_enabled": row["is_enabled"],
                    "cron_expr": row["cron_expr"],
                    "last_run": last_run.isoformat() if last_run else None,
                    "next_run": None,
                    "last_status": last_status,
                }
            )
        return Response({"results": results})


class AgentAskView(APIView):
    """
    POST JSON: question, session_id — answered via optional external orchestrator or DB fallback.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = (request.data.get("question") or "").strip()
        session_id = (request.data.get("session_id") or "default").strip() or "default"
        if not question:
            return Response(
                {"answer": "Ask a non-empty question."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        upstream = getattr(settings, "CHURCHAGENTS_ORCHESTRATOR_URL", "") or ""
        if upstream:
            try:
                r = requests.post(
                    f"{upstream}/ask",
                    json={"question": question, "session_id": session_id},
                    timeout=120,
                    headers={"Content-Type": "application/json"},
                )
                try:
                    data = r.json()
                except ValueError:
                    data = {"answer": r.text[:2000]}
                return Response(data, status=r.status_code)
            except requests.RequestException as exc:
                return Response(
                    {
                        "answer": (
                            f"Could not reach orchestrator at {upstream} ({exc!s}). "
                            "Check CHURCHAGENTS_ORCHESTRATOR_URL or rely on fallback by clearing it."
                        )
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        answer = _fallback_ask_answer(request, question)
        return Response({"answer": answer})
