"""
Role catalog aligned with Role.ROLE_LEVELS (1 = highest).

Role → permission links: `accounts.seed.role_permissions_catalog`.
"""

from __future__ import annotations

RoleSeedDict = dict[str, str | int | bool]

ROLES_SEED_DATA: list[RoleSeedDict] = [
    {
        "name": "Pastor",
        "level": 1,
        "description": "Church Pastor - Full Access",
        "is_system_role": True,
    },
    {
        "name": "First Elder",
        "level": 1,
        "description": "First Elder - Full Access",
        "is_system_role": True,
    },
    {
        "name": "Secretary",
        "level": 2,
        "description": "Church Secretary",
        "is_system_role": True,
    },
    {
        "name": "Treasurer",
        "level": 2,
        "description": "Church Treasurer",
        "is_system_role": True,
    },
    {
        "name": "Department Head",
        "level": 3,
        "description": "Department Head/Staff",
        "is_system_role": True,
    },
    {
        "name": "Elder in charge",
        "level": 3,
        "description": "Oversight elder for a department (e.g. program approval)",
        "is_system_role": True,
    },
    {
        "name": "Member",
        "level": 4,
        "description": "Regular Church Member",
        "is_system_role": True,
    },
    {
        "name": "Visitor",
        "level": 5,
        "description": "Visitor or guest portal access",
        "is_system_role": True,
    },
]
