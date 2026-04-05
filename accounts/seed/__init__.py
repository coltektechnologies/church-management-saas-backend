"""Seed catalogs for roles and permissions (used by setup_initial_data and similar commands)."""

from .church_groups_catalog import CHURCH_GROUPS_SEED_DATA
from .permissions_catalog import PERMISSIONS_SEED_DATA
from .role_permissions_catalog import (
    LEADERSHIP_ROLE_PERMISSION_LINKS,
    ROLE_PERMISSION_ASSIGNMENTS,
)
from .roles_catalog import ROLES_SEED_DATA

__all__ = [
    "CHURCH_GROUPS_SEED_DATA",
    "PERMISSIONS_SEED_DATA",
    "ROLES_SEED_DATA",
    "ROLE_PERMISSION_ASSIGNMENTS",
    "LEADERSHIP_ROLE_PERMISSION_LINKS",
]
