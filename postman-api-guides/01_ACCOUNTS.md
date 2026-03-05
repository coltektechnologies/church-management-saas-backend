# 👥 ACCOUNTS MODULE - POSTMAN TESTING GUIDE

Churches, users, roles, permissions, and registration flows.

**Base:** `{{base_url}}/api/auth/`

---

## 🔐 Prerequisites

Run **STEP 0** from `00_SETUP_AND_AUTH.md` to obtain `access_token` and `church_id`.

---

## Churches

### List Churches

**Endpoint:** `GET {{base_url}}/api/auth/churches/`

**Headers:** `Authorization: Bearer {{access_token}}`

**Query (optional):**
```
?church_id={{church_id}}   # Platform admin filtering
```

---

### Create Church (Platform Admin Only)

**Endpoint:** `POST {{base_url}}/api/auth/register/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "church_name": "New Church",
  "denomination": "Seventh-day Adventist",
  "country": "Ghana",
  "region": "Greater Accra",
  "city": "Accra",
  "address": "123 Main St",
  "timezone": "Africa/Accra",
  "currency": "GHS",
  "admin_username": "admin_newchurch",
  "admin_email": "admin@newchurch.com",
  "admin_password": "SecurePass123!",
  "admin_first_name": "John",
  "admin_last_name": "Admin",
  "admin_phone": "+233244123456"
}
```

**💾 Save:** `church_id` from response if creating new church for testing.

---

### Get Church Detail

**Endpoint:** `GET {{base_url}}/api/auth/churches/{{church_id}}/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Update Church

**Endpoint:** `PUT {{base_url}}/api/auth/churches/{{church_id}}/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "church_name": "Updated Church Name",
  "church_email": "updated@church.com",
  "address": "456 New Address",
  "church_size": "LARGE"
}
```

---

## Users

### List Users

**Endpoint:** `GET {{base_url}}/api/auth/users/`

**Headers:** `Authorization: Bearer {{access_token}}`

**Query:**
```
?church_id={{church_id}}
```

---

### Create User

**Endpoint:** `POST {{base_url}}/api/auth/users/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "email": "newuser@church.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "church": "{{church_id}}",
  "password": "SecurePass123!",
  "is_active": true
}
```

**💾 Save:** `user_id` from response if needed.

---

### Get User Detail

**Endpoint:** `GET {{base_url}}/api/auth/users/{{user_id}}/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Update User

**Endpoint:** `PUT {{base_url}}/api/auth/users/{{user_id}}/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "first_name": "Jane",
  "last_name": "Doe Updated",
  "is_active": true
}
```

---

## Roles

### List Roles

**Endpoint:** `GET {{base_url}}/api/auth/roles/`

**Headers:** `Authorization: Bearer {{access_token}}`

**Query:** `?church_id={{church_id}}`

**💾 Save:** `role_id` from list if needed for user-role assignment.

---

### Create Role

**Endpoint:** `POST {{base_url}}/api/auth/roles/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "name": "Department Head",
  "church": "{{church_id}}",
  "level": 3,
  "description": "Can manage department programs"
}
```

---

### Get / Update Role

**Endpoint:** `GET {{base_url}}/api/auth/roles/{{role_id}}/`
**Endpoint:** `PUT {{base_url}}/api/auth/roles/{{role_id}}/`

---

## Permissions

### List Permissions

**Endpoint:** `GET {{base_url}}/api/auth/permissions/`

**Headers:** `Authorization: Bearer {{access_token}}`

**Query:** `?church_id={{church_id}}`

---

### Create Permission

**Endpoint:** `POST {{base_url}}/api/auth/permissions/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "name": "approve_program",
  "church": "{{church_id}}",
  "codename": "approve_program",
  "description": "Can approve department programs"
}
```

---

## Role-Permission Mapping

### List Role Permissions

**Endpoint:** `GET {{base_url}}/api/auth/role-permissions/`

**Query:** `?church_id={{church_id}}`

---

### Assign Permission to Role

**Endpoint:** `POST {{base_url}}/api/auth/role-permissions/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "role": "{{role_id}}",
  "permission": "{{permission_id}}",
  "church": "{{church_id}}"
}
```

---

## User-Role Assignment

### List User Roles

**Endpoint:** `GET {{base_url}}/api/auth/user-roles/`

**Query:** `?church_id={{church_id}}&user_id={{user_id}}`

---

### Assign Role to User

**Endpoint:** `POST {{base_url}}/api/auth/user-roles/`

Church is taken from the authenticated user (Bearer token); do not send `church` in the body.

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "user": "{{user_id}}",
  "role": "{{role_id}}"
}
```

---

## Payment-First Registration (Public Flow)

### Step 1: Church Information

**Endpoint:** `POST {{base_url}}/api/auth/registration/step1/`

**Headers:** `Content-Type: application/json`
*No auth required.*

**Body:**
```json
{
  "church_name": "Test Church",
  "church_email": "reg@church.com",
  "subdomain": "testchurch",
  "denomination": "SDA",
  "country": "Ghana",
  "region": "Accra",
  "city": "Accra",
  "address": "123 Street",
  "website": "https://testchurch.com",
  "church_size": "SMALL"
}
```

---

### Step 2: Admin Information

**Endpoint:** `POST {{base_url}}/api/auth/registration/step2/`

**Body:**
```json
{
  "first_name": "Admin",
  "last_name": "User",
  "admin_email": "admin@testchurch.com",
  "phone_number": "+233244123456",
  "position": "PASTOR",
  "password": "SecurePass123!",
  "confirm_password": "SecurePass123!"
}
```

---

### Step 3: Plan Selection

**Endpoint:** `POST {{base_url}}/api/auth/registration/step3/`

**Body:**
```json
{
  "subscription_plan": "BASIC",
  "billing_cycle": "MONTHLY"
}
```

---

### Initialize Payment

**Endpoint:** `POST {{base_url}}/api/auth/registration/initialize-payment/`

**Body:**
```json
{
  "registration_id": "{{registration_id_from_previous_step}}",
  "callback_url": "https://yourdomain.com/registration/callback",
  "return_url": "https://yourdomain.com/success"
}
```

---

### Verify Payment

**Endpoint:** `POST {{base_url}}/api/auth/registration/verify-payment/`

**Body:**
```json
{
  "registration_id": "{{registration_id}}",
  "reference": "{{paystack_reference}}"
}
```

---

## Payment Endpoints

### Test Paystack

**Endpoint:** `GET {{base_url}}/api/auth/paystack/test/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Initialize Payment (for subscription)

**Endpoint:** `POST {{base_url}}/api/auth/payments/initialize/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "church_id": "{{church_id}}",
  "amount": 10000,
  "plan": "BASIC",
  "callback_url": "https://yourdomain.com/callback"
}
```

---

# Variables to Save

| Variable | Source |
|----------|--------|
| church_id | Login response / Create church |
| user_id | Create user / List users |
| role_id | List / Create roles |
| permission_id | List / Create permissions |
