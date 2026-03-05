from datetime import timedelta

from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class StatusFilter(admin.SimpleListFilter):
    title = _("Status")
    parameter_name = "status"

    def lookups(self, request, model_admin):
        from .models import Announcement

        return Announcement.Status.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


class PriorityFilter(admin.SimpleListFilter):
    title = _("Priority")
    parameter_name = "priority"

    def lookups(self, request, model_admin):
        from .models import Announcement

        return Announcement.Priority.choices

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(priority=self.value())
        return queryset


class DateRangeFilter(admin.SimpleListFilter):
    title = "date range"
    parameter_name = "date_range"

    def lookups(self, request, model_admin):
        return (
            ("today", _("Today")),
            ("yesterday", _("Yesterday")),
            ("this_week", _("This week")),
            ("this_month", _("This month")),
            ("this_year", _("This year")),
            ("last_week", _("Last week")),
            ("last_month", _("Last month")),
            ("last_year", _("Last year")),
        )

    def queryset(self, request, queryset):
        now = timezone.now()
        today = now.date()

        if self.value() == "today":
            return queryset.filter(**{f"{self.parameter_name}__date": today})
        if self.value() == "yesterday":
            yesterday = today - timedelta(days=1)
            return queryset.filter(**{f"{self.parameter_name}__date": yesterday})
        if self.value() == "this_week":
            return queryset.filter(
                **{
                    f"{self.parameter_name}__date__gte": today
                    - timedelta(days=today.weekday()),
                    f"{self.parameter_name}__date__lte": today,
                }
            )
        if self.value() == "last_week":
            start = today - timedelta(days=today.weekday() + 7)
            end = start + timedelta(days=6)
            return queryset.filter(
                **{f"{self.parameter_name}__date__range": [start, end]}
            )
        if self.value() == "this_month":
            return queryset.filter(
                **{
                    f"{self.parameter_name}__year": today.year,
                    f"{self.parameter_name}__month": today.month,
                }
            )
        if self.value() == "last_month":
            first_day = today.replace(day=1)
            prev_month = first_day - timedelta(days=1)
            return queryset.filter(
                **{
                    f"{self.parameter_name}__year": prev_month.year,
                    f"{self.parameter_name}__month": prev_month.month,
                }
            )
        if self.value() == "this_year":
            return queryset.filter(**{f"{self.parameter_name}__year": today.year})
        if self.value() == "last_year":
            return queryset.filter(**{f"{self.parameter_name}__year": today.year - 1})
        return queryset


class IsActiveFilter(admin.SimpleListFilter):
    title = _("is active")
    parameter_name = "is_active"

    def lookups(self, request, model_admin):
        return (
            ("1", _("Yes")),
            ("0", _("No")),
        )

    def queryset(self, request, queryset):
        if self.value() == "1":
            return queryset.filter(is_active=True)
        if self.value() == "0":
            return queryset.filter(is_active=False)
        return queryset
