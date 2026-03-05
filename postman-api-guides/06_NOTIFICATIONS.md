# 🔔 NOTIFICATIONS MODULE - POSTMAN TESTING GUIDE

In-app notifications, templates, SMS, email, preferences, and bulk send.

**Base:** `{{base_url}}/api/notifications/`

---

## Prerequisites

- Login (00_SETUP_AND_AUTH)
- `church_id`, `access_token`, `user_id`, `member_id`

---

## In-App Notifications

### List My Notifications

**Endpoint:** `GET {{base_url}}/api/notifications/notifications/`

**Headers:** `Authorization: Bearer {{access_token}}`

**Query:**
```
?status=unread
?priority=HIGH
?category=ANNOUNCEMENT
```

---

### Create Notification (for user or member)

**Endpoint:** `POST {{base_url}}/api/notifications/notifications/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (to user):**
```json
{
  "user_id": "{{user_id}}",
  "title": "Reminder: Sunday Service",
  "message": "Join us this Sunday at 10:00 AM.",
  "priority": "MEDIUM",
  "category": "REMINDER",
  "link": "/announcements/123",
  "icon": "calendar"
}
```

**Body (to member):**
```json
{
  "member_id": "{{member_id}}",
  "title": "Birthday Greetings",
  "message": "Happy Birthday! May God bless you.",
  "priority": "LOW",
  "category": "BIRTHDAY"
}
```

**Priority:** `LOW`, `MEDIUM`, `HIGH`
**Category:** `ANNOUNCEMENT`, `REMINDER`, `EVENT`, `BIRTHDAY`, `PROGRAM`, etc.

---

### Mark as Read

**Endpoint:** `PATCH {{base_url}}/api/notifications/notifications/{{notification_id}}/`

**Body:**
```json
{
  "is_read": true
}
```

---

### Delete Notification

**Endpoint:** `DELETE {{base_url}}/api/notifications/notifications/{{notification_id}}/`

---

## Preferences

### Get My Preferences

**Endpoint:** `GET {{base_url}}/api/notifications/preferences/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Update Preferences

**Endpoint:** `PUT {{base_url}}/api/notifications/preferences/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "enable_in_app": true,
  "enable_email": true,
  "enable_sms": false,
  "announcements": true,
  "reminders": true,
  "birthdays": true,
  "events": true,
  "finance": false,
  "digest_mode": false,
  "digest_frequency": "DAILY",
  "quiet_hours_enabled": false,
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "07:00"
}
```

---

## Templates

### List Templates

**Endpoint:** `GET {{base_url}}/api/notifications/templates/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Create Template

**Endpoint:** `POST {{base_url}}/api/notifications/templates/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "name": "Event Reminder",
  "template_type": "SMS",
  "category": "EVENT",
  "subject": "Event Reminder",
  "message": "Hi {{name}}, reminder: {{event_title}} on {{date}}. Location: {{location}}.",
  "is_active": true
}
```

---

## Send SMS (Single Recipient)

**Endpoint:** `POST {{base_url}}/api/notifications/send-sms/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "phone_number": "+233244123456",
  "message": "Church service starts at 10 AM. See you there!",
  "member_id": null
}
```

*Use `member_id` to associate the SMS with a member record.*

---

## Send Email (Single Recipient)

**Endpoint:** `POST {{base_url}}/api/notifications/send-email/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "email_address": "user@example.com",
  "subject": "Weekly Church Bulletin",
  "message_html": "<p>Dear member,</p><p>Here is your weekly bulletin...</p>",
  "member_id": null
}
```

---

## Bulk Notification

**Endpoint:** `POST {{base_url}}/api/notifications/send-bulk/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "title": "Important Announcement",
  "message": "All members are invited to the special meeting.",
  "target": "all_members",
  "department_ids": [],
  "member_ids": [],
  "send_in_app": true,
  "send_sms": false,
  "send_email": false
}
```

*`target`: `all_members`, `departments`, or `specific`.*
*For `departments`, provide `department_ids`. For `specific`, provide `member_ids`.*

---

## Logs

### SMS Logs

**Endpoint:** `GET {{base_url}}/api/notifications/sms-logs/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Email Logs

**Endpoint:** `GET {{base_url}}/api/notifications/email-logs/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Batches

**Endpoint:** `GET {{base_url}}/api/notifications/batches/`

*List bulk notification batches.*

---

## Test Notification

**Endpoint:** `POST {{base_url}}/api/notifications/test/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "channel": "email",
  "recipient": "test@example.com"
}
```

*`channel`: `email` or `sms`.*

---

## Variables to Save

| Variable | Source |
|----------|--------|
| notification_id | Create / List notifications |
| user_id | Login / Accounts |
| member_id | Members list |
