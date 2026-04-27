"""
Treasury signals: auto-create income allocations (Church vs Conference).

- Tithe (TITHE): 100% Conference.
- General + loose offering (GENERAL_OFFERING, LOOSE_OFFERING): 50% Church, 50% Conference.
- Harvest income (HARVEST, ANNUAL_HARVEST, THANKSGIVING_HARVEST): 80% Church, 20% Conference.
- All other categories: 100% Church.
"""

from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from .income_notifications import notify_member_income_recorded
from .models import HARVEST_ALLOCATION_CODES, IncomeAllocation, IncomeTransaction

# Category codes (uppercase) — must match IncomeCategory.code
_OFFERING_5050_CODES = frozenset({"GENERAL_OFFERING", "LOOSE_OFFERING"})


def create_income_allocations(instance):
    """Create or recreate allocations for an IncomeTransaction."""
    IncomeAllocation.objects.filter(transaction=instance).delete()

    try:
        category_code = instance.category.code.upper() if instance.category else ""
    except Exception:
        return

    amount = instance.amount
    if not amount or amount <= 0:
        return

    if category_code == "TITHE":
        IncomeAllocation.objects.create(
            transaction=instance,
            destination=IncomeAllocation.DESTINATION_CONFERENCE,
            amount=amount,
            percentage=Decimal("100.00"),
        )
    elif category_code in _OFFERING_5050_CODES:
        half = (amount / 2).quantize(Decimal("0.01"))
        IncomeAllocation.objects.create(
            transaction=instance,
            destination=IncomeAllocation.DESTINATION_CHURCH,
            amount=half,
            percentage=Decimal("50.00"),
        )
        IncomeAllocation.objects.create(
            transaction=instance,
            destination=IncomeAllocation.DESTINATION_CONFERENCE,
            amount=amount - half,  # avoid rounding drift
            percentage=Decimal("50.00"),
        )
    elif category_code in HARVEST_ALLOCATION_CODES:
        conference = (amount * Decimal("0.20")).quantize(Decimal("0.01"))
        church = amount - conference
        IncomeAllocation.objects.create(
            transaction=instance,
            destination=IncomeAllocation.DESTINATION_CHURCH,
            amount=church,
            percentage=Decimal("80.00"),
        )
        IncomeAllocation.objects.create(
            transaction=instance,
            destination=IncomeAllocation.DESTINATION_CONFERENCE,
            amount=conference,
            percentage=Decimal("20.00"),
        )
    else:
        IncomeAllocation.objects.create(
            transaction=instance,
            destination=IncomeAllocation.DESTINATION_CHURCH,
            amount=amount,
            percentage=Decimal("100.00"),
        )


@receiver(post_save, sender=IncomeTransaction)
def on_income_transaction_saved(sender, instance, created, raw, **kwargs):
    """Create allocations when income transaction is saved."""
    if raw:
        return
    create_income_allocations(instance)
    notify_member_income_recorded(instance, created=created)
