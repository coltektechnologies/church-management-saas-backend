# 💰 TREASURY MODULE - POSTMAN TESTING GUIDE

Income/expense categories, transactions, expense requests, and assets.

**Base:** `{{base_url}}/api/treasury/`

---

## Prerequisites

- Login (00_SETUP_AND_AUTH)
- `church_id`, `access_token`
- `member_id` (optional, for contributor)
- `department_id` (optional, for allocations)
- `income_category_id`, `expense_category_id` (create or list first)

---

## Income Categories

### List Income Categories

**Endpoint:** `GET {{base_url}}/api/treasury/income-categories/`

**Headers:** `Authorization: Bearer {{access_token}}`

**💾 Save:** `income_category_id` from list.

---

### Create Income Category

**Endpoint:** `POST {{base_url}}/api/treasury/income-categories/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON):**
```json
{
  "name": "Tithe",
  "code": "TITHE",
  "description": "Regular tithe contributions",
  "is_active": true
}
```

---

### Get / Update Income Category

**Endpoint:** `GET {{base_url}}/api/treasury/income-categories/{{income_category_id}}/`
**Endpoint:** `PUT {{base_url}}/api/treasury/income-categories/{{income_category_id}}/`

---

## Income Transactions

### List Income Transactions

**Endpoint:** `GET {{base_url}}/api/treasury/income-transactions/`

**Headers:** `Authorization: Bearer {{access_token}}`

**Query:**
```
?start_date=2024-01-01
?end_date=2024-12-31
?category={{income_category_id}}
```

---

### Create Income Transaction

**Endpoint:** `POST {{base_url}}/api/treasury/income-transactions/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body (raw JSON) - Cash:**
```json
{
  "transaction_date": "2024-02-15",
  "category": "{{income_category_id}}",
  "service_type": "SABBATH_SERVICE",
  "amount": 500.00,
  "payment_method": "CASH",
  "member": "{{member_id}}",
  "is_anonymous": false,
  "notes": "Regular tithe"
}
```

**Body - Cheque:**
```json
{
  "transaction_date": "2024-02-15",
  "category": "{{income_category_id}}",
  "amount": 1000.00,
  "payment_method": "CHEQUE",
  "cheque_number": "CHQ-12345",
  "contributor_name": "John Doe",
  "is_anonymous": false
}
```

**Body - Mobile Money / Bank Transfer:**
```json
{
  "transaction_date": "2024-02-15",
  "category": "{{income_category_id}}",
  "amount": 250.00,
  "payment_method": "MOBILE_MONEY",
  "transaction_reference": "MOMO-REF-12345",
  "contributor_name": "Jane Smith",
  "is_anonymous": false
}
```

**Payment methods:** `CASH`, `CHEQUE`, `MOBILE_MONEY`, `BANK_TRANSFER`, `CARD`, `OTHER`
**Service types:** `SABBATH_SERVICE`, `MID_WEEK`, `SPECIAL_EVENT`, `WALK_IN`, `ONLINE`

---

### Get / Update Income Transaction

**Endpoint:** `GET {{base_url}}/api/treasury/income-transactions/{{transaction_id}}/`
**Endpoint:** `PUT {{base_url}}/api/treasury/income-transactions/{{transaction_id}}/`

---

## Expense Categories

### List Expense Categories

**Endpoint:** `GET {{base_url}}/api/treasury/expense-categories/`

**Headers:** `Authorization: Bearer {{access_token}}`

**💾 Save:** `expense_category_id`

---

### Create Expense Category

**Endpoint:** `POST {{base_url}}/api/treasury/expense-categories/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "name": "Utilities",
  "code": "UTIL",
  "description": "Electricity, water, etc.",
  "is_active": true
}
```

---

## Expense Transactions

### List Expense Transactions

**Endpoint:** `GET {{base_url}}/api/treasury/expense-transactions/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Create Expense Transaction

**Endpoint:** `POST {{base_url}}/api/treasury/expense-transactions/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "transaction_date": "2024-02-15",
  "category": "{{expense_category_id}}",
  "amount": 300.00,
  "payment_method": "CASH",
  "description": "Office supplies",
  "vendor": "Office Depot",
  "receipt_number": "RCP-001"
}
```

---

## Expense Requests

### List Expense Requests

**Endpoint:** `GET {{base_url}}/api/treasury/expense-requests/`

**Headers:** `Authorization: Bearer {{access_token}}`

**💾 Save:** `expense_request_id` from list.

---

### Create Expense Request

**Endpoint:** `POST {{base_url}}/api/treasury/expense-requests/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "amount_requested": 1500.00,
  "category_id": "{{expense_category_id}}",
  "department_id": "{{department_id}}",
  "purpose": "Youth conference materials",
  "justification": "Printing and supplies for event",
  "required_by_date": "2024-03-01",
  "priority": "MEDIUM"
}
```

*`requested_by` is set from the logged-in user.*

**💾 Save:** `expense_request_id` from response.

---

### Submit Expense Request

**Endpoint:** `POST {{base_url}}/api/treasury/expense-requests/{{expense_request_id}}/submit/`

**Headers:** `Authorization: Bearer {{access_token}}`
**Body:** `{}` (empty) or `{"notes": "Ready for review"}`

---

### Approve (Department Head)

**Endpoint:** `POST {{base_url}}/api/treasury/expense-requests/{{expense_request_id}}/approve-dept-head/`

**Body:**
```json
{
  "comments": "Approved by department head",
  "amount_approved": 1500.00
}
```

---

### Approve (First Elder)

**Endpoint:** `POST {{base_url}}/api/treasury/expense-requests/{{expense_request_id}}/approve-first-elder/`

**Body:**
```json
{
  "comments": "Approved by first elder",
  "amount_approved": 1500.00
}
```

---

### Approve (Treasurer)

**Endpoint:** `POST {{base_url}}/api/treasury/expense-requests/{{expense_request_id}}/approve-treasurer/`

**Body:**
```json
{
  "comments": "Approved. Ready for disbursement.",
  "amount_approved": 1500.00
}
```

---

### Reject Expense Request

**Endpoint:** `POST {{base_url}}/api/treasury/expense-requests/{{expense_request_id}}/reject/`

**Body:**
```json
{
  "rejection_reason": "Budget exceeded for this category"
}
```

---

### Disburse Expense Request

**Endpoint:** `POST {{base_url}}/api/treasury/expense-requests/{{expense_request_id}}/disburse/`

**Body:**
```json
{
  "disbursed_amount": 1500.00,
  "transaction_reference": "DISB-001",
  "notes": "Cash disbursed"
}
```

---

## Assets

### List Assets

**Endpoint:** `GET {{base_url}}/api/treasury/assets/`

**Headers:** `Authorization: Bearer {{access_token}}`

---

### Create Asset

**Endpoint:** `POST {{base_url}}/api/treasury/assets/`

**Headers:**
```
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

**Body:**
```json
{
  "name": "Church Van",
  "description": "15-seater bus for transport",
  "asset_type": "VEHICLE",
  "purchase_date": "2020-05-10",
  "purchase_value": 50000.00,
  "current_value": 35000.00,
  "serial_number": "VAN-001",
  "location": "Church garage"
}
```

---

### Get / Update Asset

**Endpoint:** `GET {{base_url}}/api/treasury/assets/{{asset_id}}/`
**Endpoint:** `PUT {{base_url}}/api/treasury/assets/{{asset_id}}/`

---

## Statistics

**Endpoint:** `GET {{base_url}}/api/treasury/statistics/`

**Headers:** `Authorization: Bearer {{access_token}}`

**Response:** Summary of income, expenses, balance, etc.

---

# Variables to Save

| Variable | Source |
|----------|--------|
| income_category_id | Create / List income categories |
| expense_category_id | Create / List expense categories |
| expense_request_id | Create / List expense requests |
| asset_id | Create / List assets |
