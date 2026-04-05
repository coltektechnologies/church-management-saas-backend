"""
Create catalog church groups for one tenant church (idempotent).

Used by setup_initial_data and by the Church post_save signal so new registrations
get the same group rows as older churches.
"""

from __future__ import annotations

from accounts.models import Church, ChurchGroup, Role

from .church_groups_catalog import CHURCH_GROUPS_SEED_DATA


def ensure_catalog_church_groups(church: Church) -> list[tuple[str, str]]:
    """
    For each row in CHURCH_GROUPS_SEED_DATA, get_or_create a ChurchGroup for `church`.

    Skips rows whose role_name is missing in the DB (run setup_initial_data / roles first).

    Returns a list of (group_name, role_name) for each **newly** created group.
    """
    created: list[tuple[str, str]] = []
    for row in CHURCH_GROUPS_SEED_DATA:
        role = Role.objects.filter(name=row["role_name"]).first()
        if not role:
            continue
        _, was_created = ChurchGroup.objects.get_or_create(
            church=church,
            name=row["name"],
            defaults={
                "role": role,
                "description": (row.get("description") or "").strip() or None,
            },
        )
        if was_created:
            created.append((row["name"], role.name))
    return created
