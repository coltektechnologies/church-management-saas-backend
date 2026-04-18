from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Church
from accounts.seed.tenant_church_groups import ensure_catalog_church_groups


@receiver(post_save, sender=Church)
def seed_catalog_church_groups_for_new_church(
    sender, instance: Church, created: bool, **kwargs
):
    """
    When a church row is first saved, create catalog ChurchGroup rows for that tenant.

    Rows whose Role does not exist yet are skipped (deploy should run setup_initial_data
    so global roles exist before or shortly after the first registrations).
    """
    if not created:
        return
    ensure_catalog_church_groups(instance)
