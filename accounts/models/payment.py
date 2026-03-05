import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Payment(models.Model):
    """Model to track payments made by churches"""

    PAYMENT_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SUCCESSFUL", "Successful"),
        ("FAILED", "Failed"),
        ("REFUNDED", "Refunded"),
    ]

    PAYMENT_METHOD_CHOICES = [
        ("PAYSTACK", "Paystack"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("CARD", "Credit/Debit Card"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    church = models.ForeignKey(
        "accounts.Church", on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="GHS")
    reference = models.CharField(max_length=100, unique=True)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="PENDING"
    )
    subscription_plan = models.CharField(max_length=50)
    billing_cycle = models.CharField(max_length=20)
    payment_date = models.DateTimeField(default=timezone.now)
    next_billing_date = models.DateTimeField(null=True, blank=True)
    payment_details = models.JSONField(
        default=dict, blank=True
    )  # Store raw payment processor response
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date"]
        verbose_name = "Payment"
        verbose_name_plural = "Payments"

    def __str__(self):
        return f"{self.church.name} - {self.amount} {self.currency} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Auto-set next billing date for successful payments
        if self.status == "SUCCESSFUL" and not self.next_billing_date:
            if self.billing_cycle == "MONTHLY":
                self.next_billing_date = timezone.now() + timezone.timedelta(days=30)
            elif self.billing_cycle == "YEARLY":
                self.next_billing_date = timezone.now() + timezone.timedelta(days=365)
        super().save(*args, **kwargs)
