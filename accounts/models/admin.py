from django.contrib import admin

from .payment import Payment


class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "church",
        "amount",
        "currency",
        "payment_method",
        "status",
        "payment_date",
        "next_billing_date",
    )
    list_filter = ("status", "payment_method", "billing_cycle")
    search_fields = ("church__name", "reference", "payment_details")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "payment_date"

    fieldsets = (
        (
            "Payment Information",
            {"fields": ("church", "amount", "currency", "reference", "status")},
        ),
        (
            "Subscription Details",
            {
                "fields": (
                    "subscription_plan",
                    "billing_cycle",
                    "payment_method",
                    "payment_date",
                    "next_billing_date",
                )
            },
        ),
        (
            "Additional Information",
            {
                "classes": ("collapse",),
                "fields": ("payment_details", "created_at", "updated_at"),
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        # Make all fields read-only if payment is successful
        if obj and obj.status == "SUCCESSFUL":
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields


# Register the model with the admin site
admin.site.register(Payment, PaymentAdmin)
