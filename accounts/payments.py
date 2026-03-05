import hashlib
import hmac
import json
import logging
import time
from decimal import Decimal

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.decorators import (api_view, authentication_classes,
                                       permission_classes)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Church, Payment, User
from .paystack import PaystackAPI

logger = logging.getLogger(__name__)


def verify_paystack_webhook(request):
    """Verify the signature of a Paystack webhook request"""
    paystack_secret = PaystackAPI.get_secret_key()
    signature = request.headers.get("x-paystack-signature")

    if not signature:
        return False

    # Calculate signature
    body = request.body.decode("utf-8")
    computed_signature = hmac.new(
        paystack_secret.encode("utf-8"),
        msg=body.encode("utf-8"),
        digestmod=hashlib.sha512,
    ).hexdigest()

    return hmac.compare_digest(computed_signature, signature)


@api_view(["GET"])
@permission_classes([AllowAny])
def test_paystack(request):
    """Test Paystack integration"""
    try:
        from .paystack import PaystackAPI

        # Create an instance of PaystackAPI
        paystack = PaystackAPI()

        # Test API key retrieval
        secret_key = paystack.SECRET_KEY
        public_key = paystack.PUBLIC_KEY

        # Check if test keys are being used
        is_test_key = "test" in secret_key.lower() or "test" in public_key.lower()

        return Response(
            {
                "status": "success",
                "keys_loaded": bool(secret_key and public_key),
                "using_test_keys": is_test_key,
                "public_key": (
                    public_key[:8] + "..." + public_key[-4:] if public_key else None
                ),
                "note": "Check the server console for API test results",
            }
        )
    except Exception as e:
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def initialize_payment(request):
    """Initialize a payment transaction and create PENDING Payment record"""
    try:
        user = request.user
        amount = request.data.get(
            "amount"
        )  # Amount in main currency (e.g. dollars/cedis)
        email = request.data.get("email", user.email)
        metadata = request.data.get("metadata", {})

        if not amount or not email:
            return Response(
                {"status": "error", "message": "Amount and email are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.church:
            return Response(
                {"status": "error", "message": "Church is required for payment"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        church = user.church
        subscription_plan = metadata.get(
            "subscription_plan", church.subscription_plan or "BASIC"
        )
        billing_cycle = metadata.get("billing_cycle", church.billing_cycle or "MONTHLY")

        metadata.update(
            {
                "user_id": str(user.id),
                "church_id": str(church.id),
                "purpose": "subscription_payment",
                "subscription_plan": subscription_plan,
                "billing_cycle": billing_cycle,
            }
        )

        reference = f"CHURCH_{church.id}_{int(time.time())}"

        # Create PENDING Payment record for tracking
        payment = Payment.objects.create(
            church=church,
            amount=Decimal(str(amount)),
            currency=church.currency or "GHS",
            reference=reference,
            payment_method="PAYSTACK",
            status="PENDING",
            subscription_plan=subscription_plan,
            billing_cycle=billing_cycle,
            payment_date=timezone.now(),
            payment_details={
                "initiated_by": str(user.id),
                "purpose": "subscription_payment",
                "paystack_init": True,
            },
        )

        response = PaystackAPI().initialize_transaction(
            email=email, amount=float(amount), reference=reference, metadata=metadata
        )

        if response.get("status"):
            return Response(
                {
                    "status": "success",
                    "authorization_url": response["data"]["authorization_url"],
                    "access_code": response["data"]["access_code"],
                    "reference": reference,
                }
            )
        else:
            payment.status = "FAILED"
            payment.payment_details["paystack_error"] = response.get(
                "message", "Failed to initialize"
            )
            payment.save()
            return Response(
                {
                    "status": "error",
                    "message": response.get("message", "Failed to initialize payment"),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    except Exception as e:
        logger.error(f"Error initializing payment: {str(e)}", exc_info=True)
        return Response(
            {
                "status": "error",
                "message": "An error occurred while processing your payment",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@csrf_exempt
@require_http_methods(["POST"])
def paystack_webhook(request):
    """Handle Paystack webhook events"""
    try:
        # Verify the webhook signature
        if not verify_paystack_webhook(request):
            logger.warning("Invalid webhook signature")
            return HttpResponse(status=400)

        # Parse the webhook payload
        payload = json.loads(request.body)
        event = payload.get("event")
        data = payload.get("data")

        if not event or not data:
            logger.warning("Invalid webhook payload")
            return HttpResponse(status=400)

        logger.info(f"Received Paystack webhook event: {event}")

        # Handle different webhook events
        if event == "charge.success":
            return handle_successful_charge(data)
        elif event == "charge.failed":
            return handle_failed_charge(data)
        elif event == "subscription.create":
            return handle_subscription_created(data)
        elif event == "subscription.disable":
            return handle_subscription_disabled(data)
        else:
            logger.info(f"Unhandled webhook event: {event}")
            return JsonResponse(
                {"status": "success", "message": "Event received but not handled"}
            )

    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook payload")
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return HttpResponse(status=500)


def handle_successful_charge(data):
    """Handle successful payment charge - verify with Paystack and update Payment record"""
    try:
        reference = data.get("reference")
        if not reference:
            logger.warning("charge.success webhook missing reference")
            return JsonResponse(
                {"status": "success", "message": "Reference missing, skipping"}
            )

        # 1. Verify transaction with Paystack (best practice - don't trust webhook data alone)
        verification = PaystackAPI.verify_transaction(reference)
        if (
            not verification.get("status")
            or verification.get("data", {}).get("status") != "success"
        ):
            logger.warning(
                f"Paystack verification failed for reference {reference}: {verification.get('message', 'Unknown')}"
            )
            return JsonResponse(
                {"status": "error", "message": "Verification failed"}, status=400
            )

        verified_data = verification["data"]
        amount = Decimal(verified_data["amount"]) / 100  # Convert from kobo
        metadata = verified_data.get("metadata", {}) or data.get("metadata", {})

        logger.info(
            f"Processing verified charge. Reference: {reference}, Amount: {amount}"
        )

        # 2. Find or create Payment record
        payment = Payment.objects.filter(reference=reference).first()

        if payment:
            payment.status = "SUCCESSFUL"
            payment.amount = amount
            payment.payment_date = timezone.now()
            payment.payment_details.update(
                {
                    "webhook": "charge.success",
                    "verified_at": timezone.now().isoformat(),
                    "paystack_reference": verified_data.get("reference"),
                    "paystack_message": verification.get("message", ""),
                    "channel": verified_data.get("channel", ""),
                    "authorization": verified_data.get("authorization", {}),
                }
            )
            payment.save()
            logger.info(f"Updated Payment {payment.id} for reference {reference}")
        else:
            # Payment not found - may be registration (church created later) or subscription with missing init
            church_id = metadata.get("church_id")
            if church_id:
                try:
                    church = Church.objects.get(id=church_id)
                    payment = Payment.objects.create(
                        church=church,
                        amount=amount,
                        currency=verified_data.get("currency", "GHS"),
                        reference=reference,
                        payment_method="PAYSTACK",
                        status="SUCCESSFUL",
                        subscription_plan=metadata.get(
                            "subscription_plan", church.subscription_plan or "BASIC"
                        ),
                        billing_cycle=metadata.get(
                            "billing_cycle", church.billing_cycle or "MONTHLY"
                        ),
                        payment_date=timezone.now(),
                        payment_details={
                            "webhook": "charge.success",
                            "created_from_webhook": True,
                            "paystack_reference": verified_data.get("reference"),
                            "metadata": metadata,
                        },
                    )
                    logger.info(
                        f"Created Payment {payment.id} from webhook for reference {reference}"
                    )
                except Church.DoesNotExist:
                    logger.warning(
                        f"Church {church_id} not found for webhook reference {reference}"
                    )
            else:
                logger.info(
                    f"No Payment or Church for reference {reference} (likely registration - will be created on verify)"
                )

        return JsonResponse({"status": "success"})

    except Exception as e:
        logger.error(f"Error handling successful charge: {str(e)}", exc_info=True)
        return JsonResponse({"status": "error"}, status=500)


def handle_failed_charge(data):
    """Handle failed payment charge - update Payment record to FAILED"""
    try:
        reference = data.get("reference")
        if not reference:
            return JsonResponse(
                {"status": "success", "message": "Reference missing, skipping"}
            )

        payment = Payment.objects.filter(reference=reference).first()
        if payment:
            payment.status = "FAILED"
            payment.payment_details.update(
                {
                    "webhook": "charge.failed",
                    "failed_at": timezone.now().isoformat(),
                    "gateway_response": data.get("gateway_response", ""),
                    "message": data.get("message", "Payment failed"),
                }
            )
            payment.save()
            logger.info(
                f"Updated Payment {payment.id} to FAILED for reference {reference}"
            )

        return JsonResponse({"status": "success"})
    except Exception as e:
        logger.error(f"Error handling failed charge: {str(e)}", exc_info=True)
        return JsonResponse({"status": "error"}, status=500)


def handle_subscription_created(data):
    """Handle new subscription creation"""
    try:
        subscription_code = data.get("subscription_code")
        customer_email = data.get("customer", {}).get("email")

        logger.info(
            f"New subscription created. Code: {subscription_code}, Email: {customer_email}"
        )

        # Update user's subscription in your database

        return JsonResponse({"status": "success"})

    except Exception as e:
        logger.error(f"Error handling subscription creation: {str(e)}", exc_info=True)
        return JsonResponse({"status": "error"}, status=500)


def handle_subscription_disabled(data):
    """Handle subscription deactivation"""
    try:
        subscription_code = data.get("subscription_code")

        logger.info(f"Subscription disabled. Code: {subscription_code}")

        # Update subscription status in your database

        return JsonResponse({"status": "success"})

    except Exception as e:
        logger.error(
            f"Error handling subscription deactivation: {str(e)}", exc_info=True
        )
        return JsonResponse({"status": "error"}, status=500)
