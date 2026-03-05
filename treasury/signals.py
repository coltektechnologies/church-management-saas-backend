"""
Treasury signals: auto-create income allocations (Church vs Conference).
Tithe: 100% Conference. General/Loose Offering: 50% Church, 50% Conference.
All other income: 100% Church.
"""

from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import IncomeAllocation, IncomeTransaction


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
    elif category_code in ("GENERAL_OFFERING", "LOOSE_OFFERING"):
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
