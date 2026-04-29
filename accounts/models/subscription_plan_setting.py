"""Central defaults for subscription tiers (staff edit in Django admin)."""

from django.db import models
from django.utils.translation import gettext_lazy as _

# Mirrors Church.subscription_plan codes
PLAN_CODES = ("FREE", "TRIAL", "BASIC", "PREMIUM", "ENTERPRISE")


class SubscriptionPlanSetting(models.Model):
    """
    Platform-wide defaults per plan: max users, optional SMS monthly quota.
    Individual churches still store their own Church.max_users; these rows
    document policy and can be applied manually or via management commands.
    """

    plan_code = models.CharField(
        _("Plan code"),
        max_length=20,
        unique=True,
        db_index=True,
        help_text=_(
            "Unique ID stored on churches (e.g. FREE, BASIC, TECH). "
            "Must match Church.subscription_plan when assigning tenants."
        ),
    )
    label = models.CharField(
        _("Display label"),
        max_length=120,
        blank=True,
        help_text=_("Name shown on pricing pages and admin."),
    )
    is_active = models.BooleanField(
        _("Visible on site"),
        default=True,
        help_text=_(
            "If checked, this plan is returned by the public registration/plans API "
            "and can be chosen at signup (when validation allows it)."
        ),
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    max_users_default = models.PositiveIntegerField(
        default=50,
        help_text=_("Default seat limit for new or upgraded churches on this plan."),
    )
    sms_monthly_quota = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_(
            "Optional monthly SMS segments cap per church (blank = no platform cap)."
        ),
    )
    enforce_sms_quota = models.BooleanField(
        default=False,
        help_text=_(
            "When True, operational code may enforce sms_monthly_quota (if implemented)."
        ),
    )
    email_monthly_quota = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_(
            "Optional monthly outbound email cap per church (blank = no platform cap)."
        ),
    )
    enforce_email_quota = models.BooleanField(
        default=False,
        help_text=_(
            "When True, operational code may enforce email_monthly_quota (if implemented)."
        ),
    )
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "subscription_plan_settings"
        verbose_name = _("Subscription plan default")
        verbose_name_plural = _("Subscription plan defaults")
        ordering = ["sort_order", "plan_code"]

    def __str__(self):
        return self.label or self.plan_code
