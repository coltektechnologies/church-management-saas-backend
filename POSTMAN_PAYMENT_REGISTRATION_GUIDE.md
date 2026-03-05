# Complete Postman Testing Guide - Payment-First Registration Flow
## Church Management System Multi-Step Registration with Paystack

**Last Updated:** February 2026
**Version:** 2.0

---

## 🔧 SETUP: Postman Configuration

### 1. Create New Postman Collection

1. Open Postman
2. Click "New Collection"
3. Name it: **Church Registration - Payment Flow**
4. Save

### 2. Set Collection Variables

Click on your collection → **Variables** tab:

| Variable | Initial Value | Current Value |
|----------|--------------|---------------|
| base_url | http://127.0.0.1:8000/accounts | http://127.0.0.1:8000/accounts |
| session_id | (leave empty) | (leave empty) |
| payment_reference | (leave empty) | (leave empty) |
| authorization_url | (leave empty) | (leave empty) |
| church_id | (leave empty) | (leave empty) |
| admin_user_id | (leave empty) | (leave empty) |
| access_token | (leave empty) | (leave empty) |
| paystack_test_key | sk_test_xxxxx | sk_test_xxxxx |

**How to use:** In requests, use `{{variable_name}}` instead of typing the full URL.

---

## 📝 COMPLETE REGISTRATION FLOW - STEP BY STEP

---

## ✅ STEP 1: Validate and Store Church Information

**Endpoint:** `POST /accounts/registration/step1/`

**Description:** Collect and validate church details. Returns a unique `session_id` for tracking this registration.

**Postman Request:**
```
Method: POST
URL: {{base_url}}/registration/step1/
Headers:
  Content-Type: application/json
Body (raw JSON):
```

```json
{
    "church_name": "Grace Community Church",
    "church_email": "info@gracechurch.com",
    "subdomain": "gracechurch",
    "denomination": "Baptist",
    "country": "Ghana",
    "region": "Greater Accra",
    "city": "Accra",
    "address": "123 Liberation Road, Osu, Accra",
    "phone": "+233201234567",
    "website": "https://gracechurch.com",
    "church_size": "LARGE"
}
```

**Expected Response (200 OK):**
```json
{
    "status": "success",
    "message": "Church information validated",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "data": {
        "church_name": "Grace Community Church",
        "church_email": "info@gracechurch.com",
        "subdomain": "gracechurch",
        "denomination": "Baptist",
        "country": "Ghana",
        "region": "Greater Accra",
        "city": "Accra",
        "address": "123 Liberation Road, Osu, Accra",
        "phone": "+233201234567",
        "website": "https://gracechurch.com",
        "church_size": "LARGE"
    }
}
```

**⚠️ IMPORTANT:** Copy the `session_id` from the response!

**In Postman Variables:**
1. Click on your collection
2. Go to **Variables** tab
3. Set `session_id` = `550e8400-e29b-41d4-a716-446655440000` (from response)
4. **Save**

---

## ✅ STEP 2: Validate and Store Admin Information

**Endpoint:** `POST /accounts/registration/step2/`

**Description:** Collect and validate primary admin (pastor/elder) information. Session must be valid from Step 1.

**Postman Request:**
```
Method: POST
URL: {{base_url}}/registration/step2/
Headers:
  Content-Type: application/json
Body (raw JSON):
```

```json
{
    "session_id": "{{session_id}}",
    "first_name": "John",
    "last_name": "Mensah",
    "admin_email": "pastor@gracechurch.com",
    "phone_number": "+233244123456",
    "position": "SENIOR_PASTOR",
    "password": "SecurePass123!@#",
    "confirm_password": "SecurePass123!@#"
}
```

**Expected Response (200 OK):**
```json
{
    "status": "success",
    "message": "Admin information validated",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "data": {
        "first_name": "John",
        "last_name": "Mensah",
        "email": "pastor@gracechurch.com",
        "position": "SENIOR_PASTOR"
    }
}
```

**✅ Success!** Your session is still active. Move to Step 3.

---

## ✅ STEP 3: Select Subscription Plan

**Endpoint:** `POST /accounts/registration/step3/`

**Description:** Choose subscription plan and billing cycle. Get pricing details for payment.

**Postman Request:**
```
Method: POST
URL: {{base_url}}/registration/step3/
Headers:
  Content-Type: application/json
Body (raw JSON):
```

```json
{
    "session_id": "{{session_id}}",
    "subscription_plan": "PREMIUM",
    "billing_cycle": "YEARLY"
}
```

**Available Plans:**

| Plan | Monthly | Yearly | Users | Features |
|------|---------|--------|-------|----------|
| BASIC | $14 | $140 (save $40) | 50 | Basic Reporting, Email Support |
| PREMIUM | $20 | $200 (save $40) | 200 | Advanced Reporting, Priority Support, SMS |
| ENTERPRISE | $30 | $300 (save $60) | 1000 | Custom Reporting, 24/7 Support, API |

**Expected Response (200 OK):**
```json
{
    "status": "success",
    "message": "Subscription plan selected",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "plan_details": {
        "monthly_price": 20,
        "total_price": 200,
        "discount_amount": 40,
        "billing_cycle": "YEARLY",
        "max_users": 200,
        "features": [
            "Advanced Reporting",
            "Priority Support",
            "SMS Notifications"
        ],
        "amount_cents": 20000
    }
}
```

**Plan Details Breakdown:**
- **monthly_price:** Base monthly price
- **total_price:** Total amount to pay ($200)
- **discount_amount:** Savings with yearly plan ($40)
- **amount_cents:** Amount in cents for payment processor (20000 = $200)

---

## ✅ STEP 4: Initialize Payment with Paystack

**Endpoint:** `POST /accounts/registration/initialize-payment/`

**Description:** Create a payment transaction on Paystack. Returns authorization URL to redirect user to payment page.

**Postman Request:**
```
Method: POST
URL: {{base_url}}/registration/initialize-payment/
Headers:
  Content-Type: application/json
Body (raw JSON):
```

```json
{
    "session_id": "{{session_id}}"
}
```

**Expected Response (200 OK):**
```json
{
    "status": "success",
    "authorization_url": "https://checkout.paystack.com/abc123xyz",
    "access_code": "abc123xyz",
    "reference": "REG_550e8400-e29b-41d4-a716-446655440000_1707000000",
    "amount": 200,
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**⚠️ IMPORTANT:** Copy the `reference` from the response!

**In Postman Variables:**
1. Set `payment_reference` = `REG_550e8400-e29b-41d4-a716-446655440000_1707000000` (from response)
2. Set `authorization_url` = `https://checkout.paystack.com/abc123xyz` (from response)
3. **Save**

### 🔄 Next Step: Complete Payment on Paystack

**Option A: Using Real Paystack Account**
1. Click the `authorization_url` value in Postman response
2. Browser opens Paystack checkout page
3. Use test card: `4111 1111 1111 1111`
4. Expiry: Any future date (e.g., `08/30`)
5. CVV: Any 3 digits (e.g., `123`)
6. Complete payment

**Option B: Skip to Verification (Test Flow)**
If testing without real payment, go directly to **Step 5** with your reference.

---

## ✅ STEP 5: Verify Payment & Complete Registration

**Endpoint:** `POST /accounts/registration/verify-payment/`

**Description:** Verify payment with Paystack. If successful, creates church and admin user automatically.

**Postman Request:**
```
Method: POST
URL: {{base_url}}/registration/verify-payment/
Headers:
  Content-Type: application/json
Body (raw JSON):
```

```json
{
    "session_id": "{{session_id}}",
    "reference": "{{payment_reference}}"
}
```

**Expected Response (201 Created):**
```json
{
    "status": "success",
    "message": "Registration completed successfully",
    "user": {
        "id": "650e8400-e29b-41d4-a716-446655440001",
        "username": "pastor_john",
        "email": "pastor@gracechurch.com",
        "first_name": "John",
        "last_name": "Mensah",
        "full_name": "John Mensah",
        "phone": "+233244123456",
        "profile_image": null,
        "profile_image_url": null,
        "date_of_birth": null,
        "gender": null,
        "address": null,
        "church": "750e8400-e29b-41d4-a716-446655440002",
        "church_name": "Grace Community Church",
        "church_subdomain": "gracechurch",
        "is_platform_admin": false,
        "is_active": true,
        "is_staff": true,
        "mfa_enabled": false,
        "email_verified": true,
        "roles": [
            {
                "id": "850e8400-e29b-41d4-a716-446655440003",
                "name": "Pastor",
                "level": 1
            }
        ],
        "last_login": null,
        "created_at": "2025-02-01T10:35:00Z",
        "updated_at": "2025-02-01T10:35:00Z"
    },
    "church": {
        "id": "750e8400-e29b-41d4-a716-446655440002",
        "name": "Grace Community Church",
        "email": "info@gracechurch.com",
        "subdomain": "gracechurch",
        "denomination": "Baptist",
        "country": "Ghana",
        "region": "Greater Accra",
        "city": "Accra",
        "address": "123 Liberation Road, Osu, Accra",
        "phone": "+233201234567",
        "church_size": "LARGE",
        "logo": null,
        "logo_url": null,
        "full_domain": "gracechurch.church-management-saas.com",
        "timezone": "Africa/Accra",
        "currency": "USD",
        "status": "TRIAL",
        "subscription_plan": "PREMIUM",
        "billing_cycle": "YEARLY",
        "trial_ends_at": "2025-02-15T10:35:00Z",
        "subscription_starts_at": null,
        "subscription_ends_at": null,
        "next_billing_date": null,
        "is_trial_active": true,
        "is_subscription_active": false,
        "days_until_expiry": 14,
        "plan_price": 200,
        "max_users": 200,
        "user_count": 1,
        "enable_online_giving": false,
        "enable_sms_notifications": false,
        "enable_email_notifications": true,
        "created_at": "2025-02-01T10:35:00Z",
        "updated_at": "2025-02-01T10:35:00Z"
    },
    "tokens": {
        "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoicmVmcmVzaCIsImV4cCI6MTcwNjkwNDAwMCwiaWF0IjoxNzA2ODAwMDAwLCJqdGkiOiI1N2Y0NTc4OTdjMjQ0ZjQyOGI0MjdhYzY4ZTRkZTdkMSIsInVzZXJfaWQiOiI2NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDEifQ.xyz...",
        "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzA2ODAzNjAwLCJpYXQiOjE3MDY4MDAw..."
    }
}
```

**🎉 SUCCESS!** Church and admin user created!

**Save Important IDs:**
1. Set `church_id` = `750e8400-e29b-41d4-a716-446655440002` (from response)
2. Set `admin_user_id` = `650e8400-e29b-41d4-a716-446655440001` (from response)
3. Set `access_token` = (paste access token from response)
4. **Save**

---

## ✅ STEP 6 (OPTIONAL): Payment Callback Handler

**Endpoint:** `GET /accounts/registration/payment-callback/`

**Description:** Paystack redirects here after payment. Returns session_id to complete registration.

**Postman Request:**
```
Method: GET
URL: {{base_url}}/registration/payment-callback/?reference={{payment_reference}}
Headers:
  (No authentication needed)
```

**Expected Response (200 OK):**
```json
{
    "status": "success",
    "message": "Payment received. Please complete registration.",
    "reference": "REG_550e8400-e29b-41d4-a716-446655440000_1707000000",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "next_step": "registration/verify-payment/"
}
```

**ℹ️ Note:** This is typically handled by the frontend automatically after Paystack redirect.

---

## 🧪 VERIFICATION: Test Your New Church

After successful registration, test that everything was created correctly.

### Test 1: Login as New Admin

**Postman Request:**
```
Method: POST
URL: {{base_url}}/login/
Headers:
  Content-Type: application/json
Body (raw JSON):
```

```json
{
    "email": "pastor@gracechurch.com",
    "password": "SecurePass123!@#"
}
```

**Expected Response (200 OK):**
```json
{
    "user": {
        "id": "650e8400-e29b-41d4-a716-446655440001",
        "username": "pastor_john",
        "email": "pastor@gracechurch.com",
        "first_name": "John",
        "last_name": "Mensah",
        "full_name": "John Mensah",
        "church": "750e8400-e29b-41d4-a716-446655440002",
        "church_name": "Grace Community Church",
        "is_active": true,
        "is_staff": true,
        "roles": [
            {
                "id": "850e8400-e29b-41d4-a716-446655440003",
                "name": "Pastor",
                "level": 1
            }
        ]
    },
    "tokens": {
        "refresh": "...",
        "access": "..."
    }
}
```

✅ **Verified!** Admin user created successfully

---

### Test 2: View Church Details

**Postman Request:**
```
Method: GET
URL: {{base_url}}/churches/{{church_id}}/
Headers:
  Authorization: Bearer {{access_token}}
```

**Expected Response (200 OK):**
```json
{
    "id": "750e8400-e29b-41d4-a716-446655440002",
    "name": "Grace Community Church",
    "email": "info@gracechurch.com",
    "subdomain": "gracechurch",
    "denomination": "Baptist",
    "country": "Ghana",
    "region": "Greater Accra",
    "city": "Accra",
    "address": "123 Liberation Road, Osu, Accra",
    "phone": "+233201234567",
    "church_size": "LARGE",
    "status": "TRIAL",
    "subscription_plan": "PREMIUM",
    "billing_cycle": "YEARLY",
    "trial_ends_at": "2025-02-15T10:35:00Z",
    "max_users": 200,
    "user_count": 1,
    "enable_online_giving": false,
    "enable_sms_notifications": false,
    "enable_email_notifications": true,
    "created_at": "2025-02-01T10:35:00Z",
    "updated_at": "2025-02-01T10:35:00Z"
}
```

✅ **Verified!** Church created with correct subscription plan

---

### Test 3: List Users in Church

**Postman Request:**
```
Method: GET
URL: {{base_url}}/users/
Headers:
  Authorization: Bearer {{access_token}}
```

**Expected Response (200 OK):**
```json
[
    {
        "id": "650e8400-e29b-41d4-a716-446655440001",
        "username": "pastor_john",
        "email": "pastor@gracechurch.com",
        "full_name": "John Mensah",
        "phone": "+233244123456",
        "church_name": "Grace Community Church",
        "is_active": true,
        "is_staff": true,
        "last_login": "2025-02-01T11:00:00Z",
        "created_at": "2025-02-01T10:35:00Z"
    }
]
```

✅ **Verified!** Admin user is member of the church

---

## 🚨 ERROR SCENARIOS & SOLUTIONS

---

### Error 1: Session Expired or Invalid

**Status:** 400
**Response:**
```json
{
    "status": "error",
    "message": "Session expired or invalid. Please start over."
}
```

**Cause:** More than 1 hour passed since Step 1, or session_id is wrong

**Solution:**
- Go back to **Step 1** to start a new registration
- Copy the new session_id
- Complete all steps within 1 hour

---

### Error 2: Invalid Email Format

**Status:** 400
**Response:**
```json
{
    "status": "error",
    "errors": {
        "church_email": ["Enter a valid email address."]
    }
}
```

**Cause:** Email doesn't follow format: `user@domain.com`

**Solution:** Use valid email like `info@gracechurch.com`

---

### Error 3: Subdomain Already Taken

**Status:** 400
**Response:**
```json
{
    "status": "error",
    "errors": {
        "subdomain": ["This subdomain is already taken"]
    }
}
```

**Cause:** Someone already registered this subdomain

**Solution:** Choose a different subdomain (e.g., `gracechurch2`)

---

### Error 4: Password Too Weak

**Status:** 400
**Response:**
```json
{
    "status": "error",
    "errors": {
        "password": ["Password must contain at least one uppercase letter"]
    }
}
```

**Cause:** Password doesn't meet strength requirements

**Solution:** Password must have:
- At least 8 characters
- One uppercase letter (A-Z)
- One lowercase letter (a-z)
- One digit (0-9)

Example: `SecurePass123!`

---

### Error 5: Passwords Don't Match

**Status:** 400
**Response:**
```json
{
    "status": "error",
    "errors": {
        "confirm_password": "Passwords do not match"
    }
}
```

**Cause:** Password and confirm_password fields don't match

**Solution:** Make sure both password fields are identical

---

### Error 6: Payment Verification Failed

**Status:** 400
**Response:**
```json
{
    "status": "error",
    "message": "Payment verification failed"
}
```

**Cause:**
- Payment wasn't completed on Paystack
- Payment reference is invalid
- Paystack server error

**Solution:**
1. Check payment status on Paystack dashboard
2. Verify payment reference is correct
3. Try again with a different payment

---

### Error 7: Session ID Required

**Status:** 400
**Response:**
```json
{
    "status": "error",
    "message": "Session ID is required"
}
```

**Cause:** Forgot to include `session_id` in request body

**Solution:** Always include session_id from Step 1:
```json
{
    "session_id": "{{session_id}}",
    ...
}
```

---

### Error 8: Invalid Payment Reference

**Status:** 400
**Response:**
```json
{
    "status": "error",
    "message": "Invalid payment reference"
}
```

**Cause:** Payment reference format is incorrect or corrupted

**Solution:** Copy the exact reference from Step 4 response

---

## 📋 COMPLETE POSTMAN COLLECTION STRUCTURE

```
Church Registration - Payment Flow/
├── 1. Registration Flow/
│   ├── Step 1 - Validate Church Info
│   ├── Step 2 - Validate Admin Info
│   ├── Step 3 - Select Plan
│   ├── Step 4 - Initialize Payment
│   ├── Step 5 - Verify Payment & Create
│   └── Step 6 - Payment Callback (Optional)
│
└── 2. Verification/
    ├── Login as New Admin
    ├── Get Church Details
    ├── List Church Users
    └── Get Admin User Details
```

---

## 📊 TESTING CHECKLIST

### Registration Flow
- [ ] Step 1: Church info validated, session_id received
- [ ] Step 2: Admin info validated, session still active
- [ ] Step 3: Plan selected, pricing calculated
- [ ] Step 4: Payment initialized, authorization_url received
- [ ] Complete payment on Paystack (or use test reference)
- [ ] Step 5: Payment verified, church & user created
- [ ] Received JWT tokens

### Verification
- [ ] Login as new admin successful
- [ ] View church details shows PREMIUM plan
- [ ] User list shows 1 admin user
- [ ] Church status is TRIAL (14-day free trial)
- [ ] Subdomain correctly set

---

## 💡 PRO TIPS

### 1. Variable Management
Always copy IDs and tokens from responses into Postman variables:
```
session_id → from Step 1
payment_reference → from Step 4
church_id → from Step 5
access_token → from Step 5
```

### 2. Testing Multiple Churches
Run this flow multiple times with different church names:
- Church 1: `gracechurch` subdomain
- Church 2: `victorychapel` subdomain
- Church 3: `livingfaith` subdomain

### 3. Paystack Test Cards
Use these test cards with Paystack sandbox:
- **Visa:** `4111 1111 1111 1111`
- **Mastercard:** `5555 5555 5555 4444`
- **Expiry:** Any future date (e.g., 08/30)
- **CVV:** Any 3 digits (e.g., 123)
- **OTP (if prompted):** 123456

### 4. Save Requests
After testing, save all requests:
- Right-click request → Save as → Give it a name
- Use descriptive names like "Step 1 - Grace Church"

### 5. Check Response Status
Always verify HTTP status code:
- **200 OK** = Success (validation)
- **201 Created** = Success (creation)
- **400 Bad Request** = Validation error
- **500 Internal Server Error** = Server error

---

## 🔄 TROUBLESHOOTING FLOW

```
❓ Is session_id in the request?
├─ NO → Add it from Step 1 response
└─ YES ↓

❓ Is it the same session_id from Step 1?
├─ NO → Use correct session_id
└─ YES ↓

❓ Is it within 1 hour?
├─ NO → Start fresh from Step 1
└─ YES ↓

❓ Did you complete all previous steps?
├─ NO → Go back and complete missing steps
└─ YES ↓

❓ Is your payment reference correct?
├─ NO → Copy exact reference from Step 4
└─ YES ↓

✅ Everything should work!
```

---

## 📚 REFERENCE: Payment Session Timeline

```
Step 1 (Church Info)          ← Session created, 1 hour timeout starts
  ↓ (saves in cache)
Step 2 (Admin Info)            ← Session still valid
  ↓ (saves in cache)
Step 3 (Plan Selection)        ← Session still valid, pricing calculated
  ↓ (saves in cache)
Step 4 (Initialize Payment)    ← Session still valid, payment reference created
  ↓ (saves reference in cache)
[USER PAYS ON PAYSTACK]        ← 5 minutes to 2 hours (typical)
  ↓
Step 5 (Verify Payment)        ← Session must still be valid
  ↓
✅ CHURCH CREATED              ← All cache data cleared, session ended
```

**⚠️ Important:** If more than 1 hour passes between Step 1 and Step 5, you must start over.

---

## 🎯 SUCCESS CRITERIA

Your registration is successful when:

✅ Step 5 returns 201 Created status
✅ Church ID is in the response
✅ User ID is in the response
✅ JWT tokens are in the response
✅ Church status is "TRIAL"
✅ Subscription plan matches your selection
✅ Admin user can login successfully
✅ Church appears in user's church list

---

**Ready to test? Start with Step 1! 🚀**
