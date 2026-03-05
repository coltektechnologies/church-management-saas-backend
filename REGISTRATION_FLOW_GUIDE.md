# Multi-Step Registration Flow with Payment Verification

## Overview
The registration flow has been updated to require **payment BEFORE creating the church and admin user**. This ensures churches are verified customers before gaining access.

---

## API Endpoints

### Step 1: Validate Church Information
**POST** `accounts/registration/step1/`

**Request Body:**
```json
{
  "church_name": "Victory Chapel",
  "church_email": "info@victorychapel.com",
  "subdomain": "victorychapel",
  "denomination": "Seventh-day Adventist",
  "country": "Ghana",
  "region": "Greater Accra",
  "city": "Accra",
  "address": "123 Liberation Road",
  "phone": "+233201234567",
  "website": "https://victorychapel.com",
  "church_size": "LARGE"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Church information validated",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": { ... }
}
```

---

### Step 2: Validate Admin Information
**POST** `accounts/registration/step2/`

**Request Body:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "first_name": "John",
  "last_name": "Doe",
  "admin_email": "pastor@victorychapel.com",
  "phone_number": "+233201234567",
  "position": "SENIOR_PASTOR",
  "password": "SecurePass123!",
  "confirm_password": "SecurePass123!"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Admin information validated",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "pastor@victorychapel.com",
    "position": "SENIOR_PASTOR"
  }
}
```

---

### Step 3: Select Subscription Plan
**POST** `accounts/registration/step3/`

**Request Body:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "subscription_plan": "PREMIUM",
  "billing_cycle": "YEARLY"
}
```

**Response (Success):**
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
    "features": ["Advanced Reporting", "Priority Support", "SMS Notifications"],
    "amount_cents": 20000
  }
}
```

---

### Step 4: Initialize Payment
**POST** `accounts/registration/initialize-payment/`

**Request Body:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "authorization_url": "https://checkout.paystack.com/...",
  "access_code": "bxwxvp2x7z",
  "reference": "REG_550e8400-e29b-41d4-a716-446655440000_1707000000",
  "amount": 200,
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Frontend Action:** Redirect user to `authorization_url`

---

### Step 5: Verify Payment & Complete Registration
**POST** `accounts/registration/verify-payment/`

**Request Body:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "reference": "REG_550e8400-e29b-41d4-a716-446655440000_1707000000"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Registration completed successfully",
  "user": { ... },
  "church": { ... },
  "tokens": {
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
  }
}
```

---

### Step 5b: Payment Callback (Optional)
**GET** `accounts/registration/payment-callback/?reference=REG_...`

Handles Paystack redirect after payment. Returns session_id and reference for frontend to complete registration.

---

## Session Management

- **Session Duration:** 1 hour
- **Session Storage:** Django Cache (Redis recommended)
- **Session ID:** UUID format, generated in Step 1
- **Cache Keys:**
  - `registration_step1_{session_id}` - Church info
  - `registration_step2_{session_id}` - Admin info
  - `registration_step3_{session_id}` - Plan selection
  - `registration_payment_{session_id}` - Payment reference

---

## Payment Plans & Pricing

| Plan       | Monthly | Yearly | Users | Features |
|-----------|---------|--------|-------|----------|
| **BASIC** | $14     | $140   | 50    | Basic Reporting, Email Support |
| **PREMIUM** | $20    | $200   | 200   | Advanced Reporting, Priority Support, SMS |
| **ENTERPRISE** | $30 | $300   | 1000  | Custom Reporting, 24/7 Support, API Access |

**Yearly Discount:** 2 months free (10 months billing)

---

## Paystack Integration

### Environment Variables Required
```
PAYSTACK_SECRET_KEY=sk_live_xxxxx
PAYSTACK_PUBLIC_KEY=pk_live_xxxxx
FRONTEND_URL=https://yourdomain.com
```

### Key Methods
- `PaystackAPI.initialize_transaction()` - Start payment
- `PaystackAPI.verify_transaction()` - Verify payment
- `PaystackAPI.create_customer()` - Create customer record

---

## Platform Admin Registration

The old `/accounts/register/` endpoint is **now restricted to platform admins only**.

**Usage:** Platform admins can still create churches without payment using:

```python
class RegisterAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Require authentication

    def post(self, request):
        # Only platform admins can use this endpoint
        if not request.user.is_platform_admin:
            return Response(
                {'error': 'Only platform admins can use this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        # ... create church without payment
```

---

## Frontend Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         START REGISTRATION                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                    ┌─────────────────┐
                    │   STEP 1        │
                    │ Church Info     │
                    │ POST /step1/    │
                    └─────────────────┘
                              ↓
                    ┌─────────────────┐
                    │   STEP 2        │
                    │ Admin Info      │
                    │ POST /step2/    │
                    └─────────────────┘
                              ↓
                    ┌─────────────────┐
                    │   STEP 3        │
                    │ Select Plan     │
                    │ POST /step3/    │
                    └─────────────────┘
                              ↓
              ┌───────────────────────────────┐
              │  INITIALIZE PAYMENT           │
              │ POST /initialize-payment/     │
              └───────────────────────────────┘
                              ↓
              ┌───────────────────────────────┐
              │  REDIRECT TO PAYSTACK         │
              │ (User pays on Paystack page)  │
              └───────────────────────────────┘
                              ↓
              ┌───────────────────────────────┐
              │  VERIFY PAYMENT               │
              │ POST /verify-payment/         │
              └───────────────────────────────┘
                              ↓
        ┌─────────────────────────────────────────┐
        │     CHURCH & ADMIN CREATED              │
        │     JWT TOKENS GENERATED                │
        │     READY TO USE DASHBOARD              │
        └─────────────────────────────────────────┘
```

---

## Error Handling

### Session Expired
**Status:** 400
```json
{
  "status": "error",
  "message": "Session expired or invalid. Please start over."
}
```

### Payment Verification Failed
**Status:** 400
```json
{
  "status": "error",
  "message": "Payment verification failed"
}
```

### Invalid Credentials
**Status:** 403
```json
{
  "status": "error",
  "message": "Only platform admins can use this endpoint"
}
```

---

## Testing

### Test with Paystack Test Keys
1. Use test credentials in environment
2. Test card: `4111 1111 1111 1111` (Visa)
3. Expiry: Any future date
4. CVV: Any 3 digits

### Manual Testing Flow
```bash
# Step 1
curl -X POST http://localhost:8000/accounts/registration/step1/ \
  -H "Content-Type: application/json" \
  -d '{"church_name": "Test Church", ...}'

# Copy session_id from response

# Step 2
curl -X POST http://localhost:8000/accounts/registration/step2/ \
  -H "Content-Type: application/json" \
  -d '{"session_id": "...", "first_name": "John", ...}'

# ... continue through steps
```

---

## Database Changes

No migrations needed. Uses existing Church, User, and related models.

---

## Cache Configuration

Ensure Redis or memcached is configured in `settings.py`:

```python
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

---

## Summary of Changes

✅ **New Views Added:**
- `registration_step1` - Validate church info
- `registration_step2` - Validate admin info
- `registration_step3` - Select plan & get pricing
- `registration_initialize_payment` - Start payment
- `registration_verify_payment` - Complete registration after payment
- `registration_payment_callback` - Handle Paystack redirect

✅ **RegisterAPIView Updated:**
- Now requires `IsAuthenticated` permission
- Restricted to platform admins only
- Used for admin-only church creation without payment

✅ **URLs Updated:**
- Added 6 new registration endpoints
- All use `/accounts/registration/` prefix

✅ **Paystack Integration:**
- `verify_transaction()` method already exists
- Ready for payment verification

✅ **Features:**
- Session-based data storage (1 hour timeout)
- Multi-step validation
- Payment required before creation
- Automatic user & church creation after payment
- JWT token generation on completion
