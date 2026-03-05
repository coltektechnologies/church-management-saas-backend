# 🔐 Setup and Authentication

**Base URL:** `{{base_url}}` (e.g., `http://localhost:8000`)

---

## 📋 Postman Environment Variables

Create these in Postman Environment or Collection variables:

| Variable | Initial Value | Description |
|----------|---------------|-------------|
| base_url | http://localhost:8000 | API base URL |
| access_token | (empty) | JWT access token – save after login |
| refresh_token | (empty) | JWT refresh token |
| church_id | (empty) | Church UUID – save from login |
| user_id | (empty) | Logged-in user UUID |

---

## 🔑 Authentication Header

**All authenticated requests:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

---

## STEP 0: Login to Get Access Token

**Endpoint:** `POST {{base_url}}/api/auth/login/`

**Headers:**
```
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "email": "admin@church.com",
  "password": "your_password",
  "church_id": "your-church-uuid-here"
}
```

**Response (200):**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "user-uuid",
    "email": "admin@church.com",
    "church": {
      "id": "church-uuid",
      "name": "Grace Church"
    }
  }
}
```

**💾 Save to variables:**
- `access_token` = Response → `access`
- `refresh_token` = Response → `refresh`
- `church_id` = Response → `user.church.id` (or `user.church` if it's a UUID)
- `user_id` = Response → `user.id`

---

## Token Refresh

**Endpoint:** `POST {{base_url}}/api/token/refresh/`

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "refresh": "{{refresh_token}}"
}
```

**Response:**
```json
{
  "access": "new-access-token-here"
}
```

**💾 Save:** `access_token` = Response → `access`

---

## Change Password

**Endpoint:** `POST {{base_url}}/api/auth/change-password/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "old_password": "OldPass123!",
  "new_password": "NewPass123!",
  "new_password_confirm": "NewPass123!"
}
```

---

## Postman Script to Save Variables After Login

Add to **Login** request → **Tests** tab:

```javascript
if (pm.response.code === 200) {
    var json = pm.response.json();
    if (json.access) pm.collectionVariables.set("access_token", json.access);
    if (json.refresh) pm.collectionVariables.set("refresh_token", json.refresh);
    if (json.user) {
        var church = json.user.church;
        if (typeof church === 'object' && church.id)
            pm.collectionVariables.set("church_id", church.id);
        else if (typeof church === 'string')
            pm.collectionVariables.set("church_id", church);
        if (json.user.id) pm.collectionVariables.set("user_id", json.user.id);
    }
}
```
