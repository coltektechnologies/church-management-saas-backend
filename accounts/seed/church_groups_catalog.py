"""
Default church groups for seeded development church.

Each row maps a **group name** (per church) to a **role** by `role_name`. Adding a user to the
group grants that role via `get_effective_role_ids` (see `accounts.permissions`).
"""

from __future__ import annotations

ChurchGroupSeedDict = dict[str, str]

# Applied with get_or_create(church=..., name=...) — unique (church, name).
CHURCH_GROUPS_SEED_DATA: list[ChurchGroupSeedDict] = [
    {
        "name": "Pastoral Leadership",
        "role_name": "Pastor",
        "description": "Senior pastoral access; add senior pastors here for full church permissions.",
    },
    {
        "name": "Eldership",
        "role_name": "First Elder",
        "description": "First elder / governing elder access aligned with the First Elder role.",
    },
    {
        "name": "Secretariat",
        "role_name": "Secretary",
        "description": "Church secretary staff — members, announcements, communications, events.",
    },
    {
        "name": "Treasury",
        "role_name": "Treasurer",
        "description": "Finance team — treasury, reports, and related member financial views.",
    },
    {
        "name": "Department Heads",
        "role_name": "Department Head",
        "description": "Heads of departments; includes assigning members to departments and programs.",
    },
    {
        "name": "Elders in Charge",
        "role_name": "Elder in charge",
        "description": "Elders overseeing departments; same department permission bundle as heads where applicable.",
    },
    {
        "name": "Members",
        "role_name": "Member",
        "description": "Regular members — portal read access (announcements, events, own profile).",
    },
    {
        "name": "Visitors",
        "role_name": "Visitor",
        "description": "Guests and new visitors — minimal read access.",
    },
]
