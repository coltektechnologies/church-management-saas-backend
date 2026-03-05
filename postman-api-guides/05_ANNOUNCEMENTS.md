# 📢 ANNOUNCEMENTS MODULE - POSTMAN TESTING GUIDE

Categories, templates, announcements, and attachments.

**Base:** `{{base_url}}/api/announcements/`

---

## Prerequisites

- Login (00_SETUP_AND_AUTH)
- `church_id`, `access_token`

---

## Categories

### List Categories

**Endpoint:** `GET {{base_url}}/api/announcements/categories/`

**Headers:** `Authorization: Bearer {{access_token}}`

**💾 Save:** `category_id` from list.

---

### Create Category

**Endpoint:** `POST {{base_url}}/api/announcements/categories/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "name": "General",
  "description": "General church announcements",
  "is_active": true
}
```

---

### Get / Update / Delete Category

**Endpoint:** `GET {{base_url}}/api/announcements/categories/{{category_id}}/`
**Endpoint:** `PUT {{base_url}}/api/announcements/categories/{{category_id}}/`
**Endpoint:** `DELETE {{base_url}}/api/announcements/categories/{{category_id}}/`

---

## Templates

### List Templates

**Endpoint:** `GET {{base_url}}/api/announcements/templates/`

**Headers:** `Authorization: Bearer {{access_token}}`

**💾 Save:** `template_id` from list.

---

### Create Template

**Endpoint:** `POST {{base_url}}/api/announcements/templates/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "name": "Weekly Bulletin",
  "subject": "Weekly Church Bulletin - {{date}}",
  "content": "Dear members,\n\nThis is the weekly bulletin content...",
  "is_active": true
}
```

---

### Get / Update / Delete Template

**Endpoint:** `GET {{base_url}}/api/announcements/templates/{{template_id}}/`
**Endpoint:** `PUT {{base_url}}/api/announcements/templates/{{template_id}}/`
**Endpoint:** `DELETE {{base_url}}/api/announcements/templates/{{template_id}}/`

---

## Announcements

### List Announcements

**Endpoint:** `GET {{base_url}}/api/announcements/`

**Headers:** `Authorization: Bearer {{access_token}}`

**Query:**
```
?status=DRAFT
?status=PUBLISHED
?category={{category_id}}
?search=sunday
```

**💾 Save:** `announcement_id` from list.

---

### Create Announcement

**Endpoint:** `POST {{base_url}}/api/announcements/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "title": "Sunday Service Announcement",
  "content": "Join us this Sunday for worship. Service starts at 10:00 AM.",
  "status": "DRAFT",
  "priority": "MEDIUM",
  "category_id": "{{category_id}}",
  "template_id": null,
  "is_featured": false,
  "is_pinned": false,
  "allow_comments": true,
  "allow_sharing": true,
  "publish_at": "2024-02-20T09:00:00Z",
  "expires_at": "2024-02-25T23:59:59Z"
}
```

**Status:** `DRAFT`, `PENDING_REVIEW`, `APPROVED`, `REJECTED`, `PUBLISHED`, `ARCHIVED`
**Priority:** `LOW`, `MEDIUM`, `HIGH`, `URGENT`

---

### Get Announcement Detail

**Endpoint:** `GET {{base_url}}/api/announcements/{{announcement_id}}/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Update Announcement

**Endpoint:** `PUT {{base_url}}/api/announcements/{{announcement_id}}/`

**Body:**
```json
{
  "title": "Updated Sunday Service Announcement",
  "content": "Updated content...",
  "priority": "HIGH"
}
```

---

### Delete Announcement

**Endpoint:** `DELETE {{base_url}}/api/announcements/{{announcement_id}}/`

---

### Pending Announcements

**Endpoint:** `GET {{base_url}}/api/announcements/pending/`

---

### Published Announcements

**Endpoint:** `GET {{base_url}}/api/announcements/published/`

---

### Statistics

**Summary:**
**Endpoint:** `GET {{base_url}}/api/announcements/stats/summary/`

**Timeline:**
**Endpoint:** `GET {{base_url}}/api/announcements/stats/timeline/`

---

## Attachments

### Add Attachment to Announcement

**Endpoint:** `POST {{base_url}}/api/announcements/{{announcement_id}}/attachments/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: multipart/form-data
```

**Body (form-data):**
- `file`: (file) PDF, image, etc.
- `display_name`: (optional) "Program Brochure"
- `description`: (optional) "Event brochure"

---

### List Attachments

**Endpoint:** `GET {{base_url}}/api/announcements/{{announcement_id}}/attachments/`

---

### Delete Attachment

**Endpoint:** `DELETE {{base_url}}/api/announcements/{{announcement_id}}/attachments/{{attachment_id}}/`

---

## Variables to Save

| Variable | Source |
|----------|--------|
| category_id | Create / List categories |
| template_id | Create / List templates |
| announcement_id | Create / List announcements |
| attachment_id | Add attachment |
