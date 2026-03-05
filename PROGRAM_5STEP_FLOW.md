# 5-Step Program/Budget Submission Flow

Department heads create programs (budgets) in 5 steps. Approval flow: **Department Elder → Secretariat → Treasury**.

---

## Step 1: Basic Information

**Endpoint:** `POST /api/programs/step1/`

**Get departments for dropdown:** `GET /api/departments/for-program/`

| Field | Type | Notes |
|-------|------|-------|
| department_id | UUID | Required. Selected from dropdown. |
| fiscal_year | int | Required (2020-2100) |
| budget_title | string | Required |
| budget_overview | text | Required (can be blank) |
| department_head_email | email | Optional. Auto-populated from department head. |
| department_head_phone | string | Optional. Auto-populated from department head. |

**Logic:**
- Department head name is **always auto-populated** (read-only).
- If the submitter selects a department they are **not** the head of → `submitted_by_department_head: false` (flagged).
- Returns `program_id` for next steps.

---

## Step 2: Budget Items

**Endpoint:** `PUT` or `PATCH` `/api/programs/{program_id}/step2/`

**Body:**
```json
{
  "budget_items": [
    {
      "category": "PERSONNEL_STAFF",
      "description": "Staff salaries",
      "quantity": 1,
      "amount": 5000.00
    },
    {
      "category": "PROGRAM_ACTIVITY",
      "description": "Youth outreach event",
      "quantity": 2,
      "amount": 1500.00
    },
    {
      "category": "EQUIPMENT_SUPPLIES",
      "description": "Office supplies",
      "quantity": 10,
      "amount": 200.00
    },
    {
      "category": "CUSTOM",
      "description": "Custom item name",
      "quantity": 1,
      "amount": 500.00
    }
  ]
}
```

**Categories:**
- `PERSONNEL_STAFF` – Personnel & Staff (item description)
- `PROGRAM_ACTIVITY` – Program & Activity (event, outreach, ministry)
- `EQUIPMENT_SUPPLIES` – Equipment & Supplies (materials, equipment)
- `CUSTOM` – Custom (user-defined)

Multiple items per category are allowed. Amounts are in **GHS**. Subtotal per category and grand total are computed automatically.

---

## Step 3: Justification

**Endpoint:** `PUT` or `PATCH` `/api/programs/{program_id}/step3/`

| Field | Type |
|-------|------|
| strategic_objectives | text |
| expected_impact | text |
| ministry_benefits | text |
| previous_year_comparison | text (optional) |
| number_of_beneficiaries | int (optional) |
| implementation_timeline | text (optional) |

---

## Step 4: Documents

**Endpoint:** `POST /api/programs/{program_id}/step4/documents/`

- Upload supporting documents.
- Max **10MB** per file.
- Use `multipart/form-data` with field name `file`.

---

## Step 5: Review & Submit

**Review summary:** `GET /api/programs/{program_id}/step5/review/`

Returns:
- Department, Fiscal Year, Budget Title, Total Amount
- Budget breakdown by category with subtotals
- Grand total

**Submit:** `POST /api/programs/{program_id}/step5/submit/`

Sends the budget into the approval flow.

---

## Department Elder in Charge

When creating or editing a department (Admin → Departments), assign an **Elder in charge**.
This elder approves department programs first. If no elder is assigned, any user in the Elder group or staff can approve.

## Approval Flow

1. **Department Elder** – First approval (the elder assigned to the department, or Elder group / staff)
2. **Secretariat** – Second approval
3. **Treasury** – Final approval

**Review endpoint:** `POST /api/programs/{program_id}/review/`

**Body:**
```json
{
  "department": "ELDER",   // or "SECRETARIAT" or "TREASURY"
  "action": "APPROVE",     // or "REJECT"
  "notes": "Optional notes"
}
```

- Approvers must act in order: Elder → Secretariat → Treasury.
- On **REJECT**, the program goes to `REJECTED`; the department head can edit and resubmit.
- On **APPROVE**, it moves to the next approver or to fully approved.

---

## API Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/departments/for-program/ | List departments with head info for Step 1 |
| POST | /api/programs/step1/ | Step 1: Create program with basic info |
| PUT | /api/programs/{id}/step2/ | Step 2: Add budget items |
| PUT | /api/programs/{id}/step3/ | Step 3: Add justification |
| POST | /api/programs/{id}/step4/documents/ | Step 4: Upload document |
| GET | /api/programs/{id}/step5/review/ | Step 5: Review summary |
| POST | /api/programs/{id}/step5/submit/ | Submit for approval |
| POST | /api/programs/{id}/review/ | Approve/Reject (Elder, Secretariat, Treasury) |

---

## Migration

```bash
python manage.py migrate departments
```
