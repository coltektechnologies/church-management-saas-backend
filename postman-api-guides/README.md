# 📚 Postman API Testing Guides

Complete API testing guides for the Church Management SAAS backend.

---

## Quick Start

1. **Login** – `00_SETUP_AND_AUTH.md` → Save `access_token` and `church_id`
2. **Create Environment** – Use variables from `VARIABLES_REFERENCE.md`
3. **Test Module** – Follow the guide for the module you want to test

---

## Guide Index

| File | Module | Description |
|------|--------|-------------|
| [00_SETUP_AND_AUTH.md](00_SETUP_AND_AUTH.md) | Auth | Login, token refresh, change password |
| [01_ACCOUNTS.md](01_ACCOUNTS.md) | Accounts | Churches, users, roles, permissions, registration |
| [02_MEMBERS.md](02_MEMBERS.md) | Members | Members, visitors, convert-to-member |
| [03_TREASURY.md](03_TREASURY.md) | Treasury | Income/expense categories, transactions, expense requests, assets |
| [04_DEPARTMENTS.md](04_DEPARTMENTS.md) | Departments | Departments, programs (5-step flow), budget items, approval |
| [05_ANNOUNCEMENTS.md](05_ANNOUNCEMENTS.md) | Announcements | Categories, templates, announcements, attachments |
| [06_NOTIFICATIONS.md](06_NOTIFICATIONS.md) | Notifications | In-app, SMS, email, preferences, bulk send |
| [VARIABLES_REFERENCE.md](VARIABLES_REFERENCE.md) | Reference | Postman variables and scripts |

---

## API Base Paths

| Module | Base Path |
|--------|-----------|
| Auth / Accounts | `/api/auth/` |
| Members | `/api/members/` |
| Treasury | `/api/treasury/` |
| Departments | `/api/` (departments, programs) |
| Announcements | `/api/announcements/` |
| Notifications | `/api/notifications/` |

---

## Common Variables

After login, save: `access_token`, `refresh_token`, `church_id`, `user_id`.

During testing, save IDs from create responses: `member_id`, `department_id`, `program_id`, etc.
