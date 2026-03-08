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
            settings, "FRONTEND_URL", "http://localhost:3000"
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
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            error_detail = str(e)
            try:
                error_detail = response.text
            except:
                pass
            logger.error(f"Paystack API Error: {error_detail}")
            logger.error(
                f"Response Status: {response.status_code if 'response' in locals() else 'No response'}"
            )
            logger.error(f"Secret Key being used: {cls.get_secret_key()[:10]}...")
            return {"status": False, "message": error_detail}

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
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
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
