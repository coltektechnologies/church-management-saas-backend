# 🏢 DEPARTMENTS MODULE - POSTMAN TESTING GUIDE

Departments, Programs (5-step flow), Budget Items, and approval chain.

**Base:** `{{base_url}}/api/`

---

## Prerequisites

- Login (00_SETUP_AND_AUTH)
- `church_id`, `access_token`, `member_id`

---

## DEPARTMENT MANAGEMENT

### List Departments

**Endpoint:** `GET {{base_url}}/api/departments/`

**Headers:** `Authorization: Bearer {{access_token}}`

**Query:**
```
?is_active=true
?search=choir
?ordering=name
```

**💾 Save:** `department_id` from list.

---

### Create Department

**Endpoint:** `POST {{base_url}}/api/departments/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "name": "Youth Ministry",
  "code": "YOUTH",
  "description": "Ministry focused on young people",
  "icon": "users",
  "color": "#3498db",
  "is_active": true
}
```

**With Elder and Head:**
```json
{
  "name": "Music Department",
  "code": "MUSIC",
  "description": "Worship and praise ministry",
  "icon": "music",
  "color": "#9b59b6",
  "is_active": true,
  "elder_in_charge": "{{member_id}}",
  "head_member_id": "{{member_id}}"
}
```

**💾 Save:** `department_id` = Response → id

---

### Get Department Detail

**Endpoint:** `GET {{base_url}}/api/departments/{{department_id}}/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Update Department

**Endpoint:** `PUT {{base_url}}/api/departments/{{department_id}}/`
**Endpoint:** `PATCH {{base_url}}/api/departments/{{department_id}}/`

**Body (PATCH):**
```json
{
  "is_active": false
}
```

---

### Delete Department

**Endpoint:** `DELETE {{base_url}}/api/departments/{{department_id}}/`

**Response:** `204 No Content`

---

### Get Department Members

**Endpoint:** `GET {{base_url}}/api/departments/{{department_id}}/members/`

---

### Assign Member to Department

**Endpoint:** `POST {{base_url}}/api/departments/{{department_id}}/assign_member/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "member_id": "{{member_id}}",
  "role_in_department": "Choir Member"
}
```

---

### Remove Member from Department

**Endpoint:** `DELETE {{base_url}}/api/departments/{{department_id}}/members/{{member_id}}/`

---

### Assign Department Head

**Endpoint:** `PUT {{base_url}}/api/departments/{{department_id}}/head/`

**Body:**
```json
{
  "member_id": "{{member_id}}"
}
```

---

### Get Department Statistics

**Endpoint:** `GET {{base_url}}/api/departments/statistics/`

---

### Departments for Program (Step 1 dropdown)

**Endpoint:** `GET {{base_url}}/api/departments/for-program/`

**Headers:** `Authorization: Bearer {{access_token}}`

*Returns departments with head and elder_in_charge info.*

---

## 5-STEP PROGRAM FLOW

Approval order: **Department Elder → Secretariat → Treasury**

### Step 1: Create Program (Basic Info)

**Endpoint:** `POST {{base_url}}/api/programs/step1/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "department_id": "{{department_id}}",
  "fiscal_year": 2025,
  "budget_title": "Youth Conference 2025",
  "budget_overview": "Annual youth conference for spiritual growth",
  "department_head_email": "head@church.com",
  "department_head_phone": "+233244123456"
}
```

**Response (201):**
```json
{
  "program_id": "new-program-uuid",
  "message": "Step 1 completed. Proceed to Step 2.",
  "submitted_by_department_head": true,
  "department_name": "Youth Ministry"
}
```

**💾 Save:** `program_id` = Response → program_id

---

### Step 2: Add Budget Items

**Endpoint:** `PUT {{base_url}}/api/programs/{{program_id}}/step2/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "budget_items": [
    {
      "category": "PERSONNEL_STAFF",
      "description": "Speaker honorarium",
      "quantity": 1,
      "amount": 5000.00
    },
    {
      "category": "PROGRAM_ACTIVITY",
      "description": "Catering for 100 participants",
      "quantity": 100,
      "amount": 30.00
    },
    {
      "category": "EQUIPMENT_SUPPLIES",
      "description": "Materials and handouts",
      "quantity": 1,
      "amount": 1500.00
    }
  ]
}
```

**Budget categories:** `PERSONNEL_STAFF`, `PROGRAM_ACTIVITY`, `EQUIPMENT_SUPPLIES`, `CUSTOM`

---

### Step 3: Justification

**Endpoint:** `PUT {{base_url}}/api/programs/{{program_id}}/step3/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "strategic_objectives": "Develop youth leadership",
  "expected_impact": "100 youth participants",
  "ministry_benefits": "Stronger youth ministry",
  "previous_year_comparison": "Similar to 2024",
  "number_of_beneficiaries": 100,
  "implementation_timeline": "March 2025"
}
```

---

### Step 4: Upload Document

**Endpoint:** `POST {{base_url}}/api/programs/{{program_id}}/step4/documents/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: multipart/form-data
```

**Body (form-data):**
- `file`: (file) PDF or document (max 10MB)

---

### Step 5: Review & Submit

**GET Review:**
**Endpoint:** `GET {{base_url}}/api/programs/{{program_id}}/step5/review/`

**Headers:** `Authorization: Bearer {{access_token}}`

**POST Submit:**
**Endpoint:** `POST {{base_url}}/api/programs/{{program_id}}/step5/submit/`

**Headers:** `Authorization: Bearer {{access_token}}`
**Body:** `{}` (empty) or omit

**Response:**
```json
{
  "program_id": "program-uuid",
  "message": "Budget submitted successfully. Awaiting approval: Department Elder → Secretariat → Treasury.",
  "status": "SUBMITTED"
}
```

---

## PROGRAM APPROVAL (Elder → Secretariat → Treasury)

**Endpoint:** `POST {{base_url}}/api/programs/{{program_id}}/review/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Elder Approval (first):**
```json
{
  "department": "ELDER",
  "action": "APPROVE",
  "notes": "Approved by department elder."
}
```

**Secretariat Approval (after Elder):**
```json
{
  "department": "SECRETARIAT",
  "action": "APPROVE",
  "notes": "Approved by secretariat."
}
```

**Treasury Approval (final):**
```json
{
  "department": "TREASURY",
  "action": "APPROVE",
  "notes": "Budget approved."
}
```

**Reject (any approver):**
```json
{
  "department": "ELDER",
  "action": "REJECT",
  "notes": "Please revise the budget dates."
}
```

---

## LEGACY PROGRAM ENDPOINTS (Direct CRUD)

### List Programs

**Endpoint:** `GET {{base_url}}/api/programs/`

**Query:** `?status=DRAFT&department={{department_id}}`

---

### Create Program (Direct)

**Endpoint:** `POST {{base_url}}/api/programs/`

**Body:**
```json
{
  "department": "{{department_id}}",
  "title": "Youth Conference 2025",
  "description": "Annual youth conference",
  "start_date": "2025-03-15",
  "end_date": "2025-03-17",
  "location": "Conference Center"
}
```

---

### Get / Update / Delete Program

**Endpoint:** `GET {{base_url}}/api/programs/{{program_id}}/`
**Endpoint:** `PUT {{base_url}}/api/programs/{{program_id}}/`
**Endpoint:** `DELETE {{base_url}}/api/programs/{{program_id}}/`

---

## BUDGET ITEMS (Nested under Program)

*Use nested route when program was created via legacy `POST /api/programs/` or `POST /api/departments/{{department_id}}/programs/`.*

### List Budget Items

**Endpoint:** `GET {{base_url}}/api/departments/{{department_id}}/programs/{{program_id}}/budget-items/`

---

### Create Income Budget Item

**Endpoint:** `POST {{base_url}}/api/departments/{{department_id}}/programs/{{program_id}}/budget-items/`

**Body:**
```json
{
  "item_type": "INCOME",
  "income_source": "CHURCH_COFFERS",
  "description": "Budget allocation from church",
  "amount": 5000.00,
  "notes": "Approved by board"
}
```

**Income sources:** `CHURCH_COFFERS`, `SILVER_COLLECTION`, `HARVEST`, `DONATION`, `OUTSOURCE`, `OTHER`

---

### Create Expense Budget Item

**Body:**
```json
{
  "item_type": "EXPENSE",
  "description": "Venue rental",
  "amount": 4500.00,
  "notes": "3-day rental"
}
```

---

### Get / Update / Delete Budget Item

**Endpoint:** `GET {{base_url}}/api/departments/{{department_id}}/programs/{{program_id}}/budget-items/{{budget_item_id}}/`
**Endpoint:** `PUT` (same URL)
**Endpoint:** `DELETE` (same URL)

---

## STATUS FLOW

```
DRAFT
  ↓ (step5/submit)
SUBMITTED
  ↓ (ELDER approves)
ELDER_APPROVED
  ↓ (SECRETARIAT approves)
SECRETARIAT_APPROVED
  ↓ (TREASURY approves)
APPROVED
```

Any approver can **REJECT** → status = `REJECTED` (can resubmit from DRAFT).

---

## Variables to Save

| Variable | Source |
|----------|--------|
| department_id | Create / List departments |
| program_id | Step 1 / Create program |
| budget_item_id | Create budget item |
| member_id | Members list (for assign head/elder) |
