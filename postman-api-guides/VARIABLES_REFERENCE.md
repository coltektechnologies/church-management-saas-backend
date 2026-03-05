# 📋 POSTMAN VARIABLES REFERENCE

Variables to configure in Postman Environment or Collection.

---

## Environment / Collection Variables

| Variable | Initial Value | Description |
|----------|---------------|-------------|
| base_url | http://localhost:8000 | API base URL |
| access_token | (empty) | JWT access – set after login |
| refresh_token | (empty) | JWT refresh – set after login |
| church_id | (empty) | Church UUID – from login or create church |
| user_id | (empty) | User UUID – from login or create user |

---

## IDs to Save During Testing

These are typically set via Postman **Tests** scripts or manually after responses.

| Variable | Module | Source |
|----------|--------|--------|
| member_id | Members | Create member / List members |
| visitor_id | Members | Create visitor / List visitors |
| department_id | Departments | Create / List departments |
| program_id | Departments | Step 1 / Create program |
| budget_item_id | Departments | Create budget item |
| income_category_id | Treasury | Create / List income categories |
| expense_category_id | Treasury | Create / List expense categories |
| expense_request_id | Treasury | Create / List expense requests |
| asset_id | Treasury | Create asset |
| role_id | Accounts | List / Create roles |
| permission_id | Accounts | List / Create permissions |
| category_id | Announcements | Create / List categories |
| template_id | Announcements | Create / List templates |
| announcement_id | Announcements | Create / List announcements |
| notification_id | Notifications | Create / List notifications |

---

## Login Script (Tests Tab)

Add to the **Login** request (`POST {{base_url}}/api/auth/login/`) → **Tests** tab:

```javascript
if (pm.response.code === 200) {
    var json = pm.response.json();
    if (json.access) pm.collectionVariables.set("access_token", json.access);
    if (json.refresh) pm.collectionVariables.set("refresh_token", json.refresh);
    if (json.user) {
        var church = json.user.church;
        if (typeof church === 'object' && church && church.id)
            pm.collectionVariables.set("church_id", church.id);
        else if (typeof church === 'string')
            pm.collectionVariables.set("church_id", church);
        if (json.user.id) pm.collectionVariables.set("user_id", json.user.id);
    }
}
```

---

## Save ID from Create Response

Example for **Create Member** (Tests tab):

```javascript
if (pm.response.code === 200 || pm.response.code === 201) {
    var json = pm.response.json();
    if (json.id) pm.collectionVariables.set("member_id", json.id);
}
```

Use the same pattern for other creates (department_id, program_id, etc.), changing the variable name as needed.

---

## Base URL per Environment

| Environment | base_url |
|-------------|----------|
| Local | http://localhost:8000 |
| Staging | https://staging.yourdomain.com |
| Production | https://api.yourdomain.com |
