import logging
from typing import Any, Dict, Optional

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class MNotifyService:
    """Service for handling SMS via mNotify API"""

    def __init__(self):
        self.api_key = settings.MNOTIFY_API_KEY
        self.sender_id = getattr(settings, "MNOTIFY_SENDER_ID", "ChurchApp")
        self.base_url = "https://api.mnotify.com/api"

    def send_sms(
        self, to_phone: str, message: str, group_ids: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Send an SMS message using mNotify

        Args:
            to_phone: Recipient phone number in E.164 format (e.g., 233XXXXXXXXX)
            message: The message content to send
            group_ids: Optional list of group IDs to send to

        Returns:
            Dictionary containing success status and message details or error information
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "mNotify API key not configured",
                "code": "CONFIG_ERROR",
            }

        # Clean phone number (remove + and any non-digit characters)
        phone = "".join(filter(str.isdigit, str(to_phone)))

        # Normalize Ghana numbers: 0XXXXXXXXX -> 233XXXXXXXXX; 9 digits (no 0/233) -> 233XXXXXXXXX
        if phone.startswith("0"):
            phone = "233" + phone[1:]
        elif len(phone) == 9 and phone[0] in "23456789":
            phone = "233" + phone

        if not phone or len(phone) < 9:
            return {
                "success": False,
                "error": "Invalid or missing phone number",
                "code": "INVALID_PHONE",
            }

        try:
            if group_ids:
                # Send to group
                endpoint = f"{self.base_url}/sms/group"
                data = {
                    "group_id[]": group_ids,
                    "sender": self.sender_id[:11],  # Max 11 chars
                    "message": message,
                    "is_schedule": False,
                }
            else:
                # Send to single number
                endpoint = f"{self.base_url}/sms/quick"
                data = {
                    "recipient[]": [phone],
                    "sender": self.sender_id[:11],  # Max 11 chars
                    "message": message,
                    "is_schedule": False,
                }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
            }

            url = f"{endpoint}?key={self.api_key}"
            response = requests.post(url, data=data, headers=headers)
            try:
                response_data = response.json()
            except ValueError:
                logger.warning(
                    "mNotify returned non-JSON response (status=%s): %s",
                    response.status_code,
                    response.text[:500],
                )
                return {
                    "success": False,
                    "error": f"Invalid response from mNotify (status {response.status_code})",
                    "code": "INVALID_RESPONSE",
                    "status_code": response.status_code,
                    "raw_response": {"text": response.text[:500]},
                }

            if response.status_code == 200 and response_data.get("status") == "success":
                return {
                    "success": True,
                    "message_id": response_data.get("data", {}).get("id"),
                    "recipient_count": response_data.get("data", {}).get(
                        "recipient_count", 1
                    ),
                    "status": "queued",
                    "raw_response": response_data,
                }
            else:
                # mNotify can return message, msg, or error; log full response for debugging
                err_msg = (
                    response_data.get("message")
                    or response_data.get("msg")
                    or response_data.get("error")
                    or f"Unknown error from mNotify (status={response_data.get('status')}, code={response_data.get('code')})"
                )
                logger.warning(
                    "mNotify SMS failed: %s | raw_response=%s",
                    err_msg,
                    response_data,
                )
                return {
                    "success": False,
                    "error": err_msg,
                    "code": response_data.get("code"),
                    "status_code": response.status_code,
                    "raw_response": response_data,
                }

        except Exception as e:
            logger.error(f"mNotify SMS sending failed: {str(e)}")
            return {"success": False, "error": str(e), "code": "SEND_ERROR"}

    def check_delivery_status(self, message_id: str) -> Dict[str, Any]:
        """
        Check the delivery status of an SMS message

        Args:
            message_id: The message ID returned when the SMS was sent

        Returns:
            Dictionary containing delivery status and details:
            - success: boolean indicating if the request was successful
            - status: delivery status (pending, delivered, failed)
            - status_code: status code from the API
            - status_message: human-readable status message
            - message_id: the message ID being checked
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "mNotify API key not configured",
                "code": "CONFIG_ERROR",
            }

        if not message_id:
            return {
                "success": False,
                "error": "Message ID is required",
                "code": "INVALID_INPUT",
            }

        try:
            url = f"{self.base_url}/message/{message_id}/status?key={self.api_key}"
            response = requests.get(url)
            response_data = response.json()

            if response.status_code == 200 and response_data.get("status") == "success":
                # Map mNotify status to our internal status
                status_map = {
                    "sent": "pending",
                    "delivered": "delivered",
                    "failed": "failed",
                    "rejected": "failed",
                    "undelivered": "failed",
                    "pending": "pending",
                }

                mnotify_status = response_data.get("data", {}).get("status", "").lower()
                status = status_map.get(mnotify_status, "pending")

                return {
                    "success": True,
                    "status": status,
                    "status_code": response_data.get("code"),
                    "status_message": response_data.get("message") or mnotify_status,
                    "message_id": message_id,
                    "raw_response": response_data,
                }
            else:
                error_msg = response_data.get(
                    "message", "Failed to check delivery status"
                )
                logger.error(
                    f"Failed to check delivery status for message {message_id}: {error_msg}"
                )
                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": response.status_code,
                    "message_id": message_id,
                    "raw_response": response_data,
                }

        except Exception as e:
            error_msg = (
                f"Error checking delivery status for message {message_id}: {str(e)}"
            )
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg,
                "message_id": message_id,
                "code": "STATUS_CHECK_ERROR",
            }

    def check_balance(self) -> Dict[str, Any]:
        """
        Check the current SMS balance from mNotify

        Returns:
            Dictionary containing:
            - success: boolean indicating if the request was successful
            - balance: remaining SMS balance (if successful)
            - error: error message if request failed
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "mNotify API key not configured",
                "code": "CONFIG_ERROR",
            }

        try:
            url = f"{self.base_url}/balance/sms?key={self.api_key}"
            response = requests.get(url)
            response_data = response.json()

            if response.status_code == 200 and response_data.get("status") == "success":
                return {
                    "success": True,
                    "balance": response_data.get("balance", 0),
                    "currency": response_data.get("currency", "GHS"),
                    "raw_response": response_data,
                }
            else:
                return {
                    "success": False,
                    "error": response_data.get("message", "Failed to check balance"),
                    "code": response_data.get("code", "BALANCE_CHECK_FAILED"),
                }

        except Exception as e:
            logger.error(f"Failed to check mNotify balance: {str(e)}")
            return {"success": False, "error": str(e), "code": "BALANCE_CHECK_ERROR"}
