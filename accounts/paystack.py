import logging
import os
from decimal import Decimal

import requests
from django.conf import settings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class PaystackAPI:
    """Paystack payment integration"""

    BASE_URL = "https://api.paystack.co"

    @classmethod
    def get_secret_key(cls):
        key = os.getenv("PAYSTACK_SECRET_KEY")
        if not key:
            # Fallback to test key if no environment variable is set
            return "sk_test_your_test_key_here"
        return key

    @classmethod
    def get_public_key(cls):
        key = os.getenv("PAYSTACK_PUBLIC_KEY")
        if not key:
            # Fallback to test key if no environment variable is set
            return "pk_test_your_test_key_here"
        return key

    @property
    def SECRET_KEY(self):
        return self.get_secret_key()

    @property
    def PUBLIC_KEY(self):
        return self.get_public_key()

    @classmethod
    def initialize_transaction(cls, email, amount, reference, metadata=None):
        """
        Initialize payment transaction

        Args:
            email: Customer email
            amount: Amount in cents/kobo (e.g., 1400 for $14)
            reference: Unique payment reference
            metadata: Additional data (optional)

        Returns:
            dict: Response from Paystack
        """
        url = f"{cls.BASE_URL}/transaction/initialize"

        headers = {
            "Authorization": f"Bearer {cls.get_secret_key()}",
            "Content-Type": "application/json",
        }

        # Get frontend URL from settings or use default (Paystack redirects user here after payment)
        frontend_url = getattr(
            settings,
            "FRONTEND_URL",
            "https://opendoor-xi.vercel.app",
        ).rstrip("/")

        payload = {
            "email": email,
            "amount": int(amount * 100),  # Convert to pesewas (cents)
            "reference": reference,
            "currency": "GHS",  # Ghana Cedis
            "callback_url": f"{frontend_url}/signup/success?reference={reference}",
        }

        if metadata:
            payload["metadata"] = metadata

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            try:
                body = response.json()
            except ValueError:
                logger.error("Paystack non-JSON response: %s", response.text[:500])
                return {
                    "status": False,
                    "message": response.text or "Invalid response from Paystack",
                }

            if response.status_code >= 400:
                msg = (
                    body.get("message")
                    or response.text
                    or f"HTTP {response.status_code}"
                )
                logger.error("Paystack HTTP %s: %s", response.status_code, msg)
                return {"status": False, "message": msg}

            if not body.get("status"):
                msg = (
                    body.get("message")
                    or "Paystack declined the transaction initialize request"
                )
                logger.warning("Paystack status=false: %s", msg)
                return {"status": False, "message": msg}

            return body
        except requests.exceptions.RequestException as e:
            logger.error("Paystack request error: %s", e, exc_info=True)
            logger.error("Secret Key prefix: %s...", cls.get_secret_key()[:10])
            return {"status": False, "message": str(e)}

    @classmethod
    def verify_transaction(cls, reference):
        """
        Verify a transaction using the reference
        """
        url = f"{cls.BASE_URL}/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {cls.get_secret_key()}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            try:
                return response.json()
            except ValueError:
                logger.error(
                    "Paystack verify non-JSON (status=%s): %s",
                    response.status_code,
                    (response.text or "")[:500],
                )
                return {
                    "status": False,
                    "message": "Invalid response from Paystack",
                }
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            try:
                error_detail = response.text
            except:
                pass
            logger.error(f"Error verifying transaction: {error_detail}")
            logger.error(
                f"Response Status: {response.status_code if 'response' in locals() else 'No response'}"
            )
            return {"status": False, "message": error_detail}

    @classmethod
    def create_customer(cls, email, first_name, last_name, phone=None):
        """Create customer on Paystack"""
        url = f"{cls.BASE_URL}/customer"

        headers = {
            "Authorization": f"Bearer {cls.get_secret_key()}",
            "Content-Type": "application/json",
        }

        payload = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        }

        if phone:
            payload["phone"] = phone

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating customer: {str(e)}")
            return {"status": False, "message": str(e)}
