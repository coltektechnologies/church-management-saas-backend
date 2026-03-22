# 👤 MEMBERS MODULE - POSTMAN TESTING GUIDE

Member management, visitors, and convert-to-member.

**Base:** `{{base_url}}/api/members/`

---

## Prerequisites

- Login (00_SETUP_AND_AUTH)
- `church_id`, `access_token`

---

## Members

### List Members

**Endpoint:** `GET {{base_url}}/api/members/members/`

**Headers:** `Authorization: Bearer {{access_token}}`

**Query:**
```
?search=john
?membership_status=ACTIVE
?ordering=last_name
```

**💾 Save:** `member_id` from any result for later requests.

---

### Create Member

**Endpoint:** `POST {{base_url}}/api/members/create/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "title": "Mr",
  "first_name": "John",
  "middle_name": "Kwame",
  "last_name": "Doe",
  "gender": "MALE",
  "date_of_birth": "1990-05-15",
  "marital_status": "MARRIED",
  "national_id": "GHA-123456",
  "membership_status": "ACTIVE",
  "member_since": "2020-01-01",
  "baptism_status": "BAPTISED",
  "education_level": "TERTIARY",
  "occupation": "Software Engineer",
  "employer": "Tech Corp",
  "emergency_contact_name": "Jane Doe",
  "emergency_contact_phone": "+233244111222",
  "emergency_contact_relationship": "Spouse",
  "notes": "New member",
  "location": {
    "phone_primary": "+233244123456",
    "phone_secondary": "+233244654321",
    "email": "john.doe@example.com",
    "address": "123 Main Street, Accra",
    "city": "Accra",
    "region": "Greater Accra",
    "country": "Ghana"
  }
}
```

**Minimal body:**
```json
{
  "first_name": "John",
  "last_name": "Doe",
  "gender": "MALE",
  "member_since": "2024-01-01",
  "location": {
    "phone_primary": "+233244123456",
    "address": "123 Main St"
  }
}
```

**💾 Save:** `member_id` = Response → id

---

### Get Member Detail

**Endpoint:** `GET {{base_url}}/api/members/members/{{member_id}}/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Update Member

**Endpoint:** `PUT {{base_url}}/api/members/members/{{member_id}}/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "first_name": "John",
  "last_name": "Doe Updated",
  "occupation": "Senior Engineer",
  "location": {
    "phone_primary": "+233244123456",
    "email": "john.updated@example.com",
    "address": "456 New Address"
  }
}
```

---

### Partial Update (PATCH)

**Endpoint:** `PATCH {{base_url}}/api/members/members/{{member_id}}/`

**Body:**
```json
{
  "membership_status": "INACTIVE"
}
```

---

## Visitors

### List Visitors

**Endpoint:** `GET {{base_url}}/api/members/visitors/`

**Headers:** `Authorization: Bearer {{access_token}}`

**💾 Save:** `visitor_id` for convert-to-member.

---

### Create Visitor

**Endpoint:** `POST {{base_url}}/api/members/visitors/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "full_name": "Jane Visitor",
  "gender": "FEMALE",
  "phone": "+233244777888",
  "email": "jane.visitor@example.com",
  "address": "789 Visitor St",
  "city": "Accra",
  "region": "Greater Accra",
  "country": "Ghana",
  "notes": "First-time visitor"
}
```

**💾 Save:** `visitor_id` = Response → id

---

### Get Visitor Detail

**Endpoint:** `GET {{base_url}}/api/members/visitors/{{visitor_id}}/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Update Visitor

**Endpoint:** `PUT {{base_url}}/api/members/visitors/{{visitor_id}}/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "full_name": "Jane Visitor Updated",
  "phone": "+233244999000",
  "notes": "Returning visitor"
}
```

---

## Convert Visitor to Member

**Endpoint:** `POST {{base_url}}/api/members/visitors/convert-to-member/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "visitor_id": "{{visitor_id}}",
  "member_since": "2024-02-01",
  "occupation": "Teacher",
  "notes": "Converted from visitor register"
}
```

**Response:** Created Member object with nested location.

---

## Members by Church (API Helper)

**Endpoint:** `GET {{base_url}}/api/members/members/by-church/?church_id={{church_id}}`

**Headers:** `Authorization: Bearer {{access_token}}`

*Returns members for the given church (used by forms/dropdowns).*

---

# Variables to Save

| Variable | Source |
|----------|--------|
| member_id | Create member / List members |
| visitor_id | Create visitor / List visitors |
