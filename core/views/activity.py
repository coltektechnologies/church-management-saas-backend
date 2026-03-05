"""
Views for the activity feed
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.views.generic import ListView

from accounts.models.base_models import AuditLog


class ActivityFeedView(LoginRequiredMixin, ListView):
    """View for displaying user activity feed"""

    model = AuditLog
    template_name = "core/activity_feed.html"
    context_object_name = "activities"
    paginate_by = 20

    def get_queryset(self):
        """Filter activities for the current user's church"""
        queryset = AuditLog.objects.filter(
            Q(church=self.request.user.church) | Q(user=self.request.user)
        ).select_related("user", "church", "content_type")

        # Filter by action type if provided
        action = self.request.GET.get("action")
        if action:
            queryset = queryset.filter(action=action)

        # Filter by model if provided
        model_name = self.request.GET.get("model")
        if model_name:
            queryset = queryset.filter(model_name__iexact=model_name)

        return queryset.order_by("-created_at")

    def get_context_data(self, **kwargs):
        """Add additional context to the template"""
        context = super().get_context_data(**kwargs)

        # Get available filters
        context["available_actions"] = dict(AuditLog.ACTION_CHOICES)
        context["available_models"] = (
            AuditLog.objects.filter(church=self.request.user.church)
            .values_list("model_name", flat=True)
            .distinct()
        )

        # Current filters
        context["current_action"] = self.request.GET.get("action", "")
        context["current_model"] = self.request.GET.get("model", "")

        return context
