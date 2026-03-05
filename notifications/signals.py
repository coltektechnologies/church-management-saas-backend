from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import SMSDeliveryReport, SMSLog


@receiver(post_save, sender=SMSLog)
def create_delivery_report(sender, instance, created, **kwargs):
    """
    Create a delivery report when a new SMS log is created for outbound messages
    """
    if (
        created
        and instance.direction == "OUTBOUND"
        and not hasattr(instance, "delivery_report")
    ):
        SMSDeliveryReport.objects.create(sms_log=instance)
