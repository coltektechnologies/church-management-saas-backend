"""
Role → permission assignments for `setup_initial_data`.

Rules (high level):
- Permissions are grouped by `module` in `permissions_catalog.py`; steward roles receive
  every permission in the modules they own.
- **Pastor** / **First Elder**: all permissions (church-level super access).
- **Treasurer**: full **TREASURY** + full **REPORTS** + member directory/financial read +
  **departments.view** + **settings.view** (and billing-related settings).
- **Secretary**: full **SECRETARIAT**, **ANNOUNCEMENTS**, **COMMUNICATIONS**, **MEMBERS**,
  **EVENTS**, **ATTENDANCE**, **REPORTS** except `reports.sensitive`, plus **departments.view**
  and limited **settings** (profile + view).
- **Department Head** & **Elder in charge**: full **DEPARTMENTS** (includes
  `departments.manage_members` for assigning members to departments) + **members.view_all** /
  **members.edit** for roster work + full **EVENTS** + **ATTENDANCE** + read **announcements**
  + full **COMMUNICATIONS** for departmental outreach.
- **Member** / **Visitor**: read-mostly defaults for portal use.

`LEADERSHIP_ROLE_PERMISSION_LINKS` documents the narrower leadership matrix; the assignments
above are supersets (e.g. Pastor already has all `departments.*` including assign_head).
"""

from __future__ import annotations

from .permissions_catalog import PERMISSIONS_SEED_DATA


def _all_permission_codes() -> list[str]:
    return [p["code"] for p in PERMISSIONS_SEED_DATA]


def _codes_for_modules(*module_names: str) -> list[str]:
    wanted = set(module_names)
    return [p["code"] for p in PERMISSIONS_SEED_DATA if p["module"] in wanted]


def _uniq_sorted(*iterables: list[str]) -> list[str]:
    s: set[str] = set()
    for it in iterables:
        s.update(it)
    return sorted(s)


# Narrow leadership matrix (subset of `departments.*`). Kept for documentation and parity
# with the original seed; full role rows use ROLE_PERMISSION_ASSIGNMENTS below.
LEADERSHIP_ROLE_PERMISSION_LINKS: list[tuple[str, list[str]]] = [
    ("Pastor", ["departments.assign_head", "departments.assign_elder_in_charge"]),
    ("First Elder", ["departments.assign_head", "departments.assign_elder_in_charge"]),
    ("Secretary", ["departments.assign_head", "departments.assign_elder_in_charge"]),
    ("Department Head", ["departments.assign_head"]),
    ("Elder in charge", ["departments.assign_elder_in_charge"]),
]


# --- Composed permission packs ---

_ALL = _all_permission_codes()

_TREASURY = _codes_for_modules("TREASURY")
_REPORTS = _codes_for_modules("REPORTS")
_REPORTS_NON_SENSITIVE = [c for c in _REPORTS if c != "reports.sensitive"]
_MEMBERS = _codes_for_modules("MEMBERS")
_DEPARTMENTS = _codes_for_modules("DEPARTMENTS")
_SECRETARIAT = _codes_for_modules("SECRETARIAT")
_ANNOUNCEMENTS = _codes_for_modules("ANNOUNCEMENTS")
_COMMUNICATIONS = _codes_for_modules("COMMUNICATIONS")
_EVENTS = _codes_for_modules("EVENTS")
_ATTENDANCE = _codes_for_modules("ATTENDANCE")

# Treasurer: finance + reporting + read members/financial context
_TREASURER_EXTRA_MEMBERS = [
    "members.view_all",
    "members.view_financial",
    "members.export",
]
_TREASURER_SETTINGS = [
    "settings.view",
    "settings.edit_billing",
    "settings.integrations",
]

# Secretary: comms / records / life of church ops (not sensitive leadership-only reports)
_SECRETARY_SETTINGS = [
    "settings.view",
    "settings.edit_church_profile",
    "settings.integrations",
]

# Department stewards: all department perms + directory + events + attendance + comms
_DEPT_STEWARD_MEMBERS = [
    "members.view_all",
    "members.edit",
]
_DEPT_STEWARD_ANNOUNCEMENTS = ["announcements.view"]

# Member / visitor portal
_MEMBER_PORTAL = [
    "members.view_own",
    "announcements.view",
    "events.view",
    "attendance.view",
    "communications.view",
]
_VISITOR_PORTAL = [
    "announcements.view",
    "events.view",
]


ROLE_PERMISSION_ASSIGNMENTS: dict[str, list[str]] = {
    "Pastor": list(_ALL),
    "First Elder": list(_ALL),
    "Treasurer": _uniq_sorted(
        _TREASURY,
        _REPORTS,
        _TREASURER_EXTRA_MEMBERS,
        ["departments.view"],
        _TREASURER_SETTINGS,
    ),
    "Secretary": _uniq_sorted(
        _SECRETARIAT,
        _ANNOUNCEMENTS,
        _COMMUNICATIONS,
        _MEMBERS,
        _EVENTS,
        _ATTENDANCE,
        _REPORTS_NON_SENSITIVE,
        ["departments.view"],
        _SECRETARY_SETTINGS,
    ),
    "Department Head": _uniq_sorted(
        _DEPARTMENTS,
        _DEPT_STEWARD_MEMBERS,
        _EVENTS,
        _ATTENDANCE,
        _DEPT_STEWARD_ANNOUNCEMENTS,
        _COMMUNICATIONS,
    ),
    "Elder in charge": _uniq_sorted(
        _DEPARTMENTS,
        _DEPT_STEWARD_MEMBERS,
        _EVENTS,
        _ATTENDANCE,
        _DEPT_STEWARD_ANNOUNCEMENTS,
        _COMMUNICATIONS,
    ),
    "Member": _uniq_sorted(_MEMBER_PORTAL),
    "Visitor": _uniq_sorted(_VISITOR_PORTAL),
}
