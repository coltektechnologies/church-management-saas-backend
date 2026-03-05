from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import requests
from django.conf import settings


class MNotifySMS:
    """
    A service class for sending SMS messages using the mNotify API.
    """

    BASE_URL = "https://api.mnotify.com/api"

    def __init__(self, api_key: str = None, sender_id: str = None):
        """
        Initialize the mNotify SMS service.

        Args:
            api_key: Your mNotify API key. If not provided, will try to get from settings.MNOTIFY_API_KEY
            sender_id: The sender ID to use for messages. If not provided, will try to get from settings.MNOTIFY_SENDER_ID
        """
        self.api_key = api_key or getattr(settings, "MNOTIFY_API_KEY", None)
        self.sender_id = sender_id or getattr(
            settings, "MNOTIFY_SENDER_ID", "Open door"
        )

        if not self.api_key:
            raise ValueError(
                "mNotify API key is required. Please provide it or set MNOTIFY_API_KEY in settings."
            )

        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _make_request(
        self, endpoint: str, data: Dict[str, Any], method: str = "post"
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the mNotify API.

        Args:
            endpoint: The API endpoint to call (e.g., 'sms/quick')
            data: The payload to send with the request
            method: HTTP method to use ('post' or 'get')

        Returns:
            Dict containing the API response
        """
        import json
        import sys

        url = f"{self.BASE_URL}/{endpoint}?key={self.api_key}"

        try:
            # Print request info to console
            print("\n" + "=" * 70)
            print("mNotify API Request:")
            print(f"URL: {url}")
            print(f"Method: {method.upper()}")
            print("Payload:")
            print(json.dumps(data, indent=2))

            if method.lower() == "post":
                response = self.session.post(url, json=data)
            else:
                response = self.session.get(url)

            response.raise_for_status()
            result = response.json()

            # Print formatted response to console
            print("\nmNotify API Response:")
            print(json.dumps(result, indent=2))
            print("=" * 70 + "\n")

            # Ensure output is immediately visible
            sys.stdout.flush()

            return result

        except requests.exceptions.RequestException as e:
            error_response = {
                "status": "error",
                "message": str(e),
                "code": "request_error",
            }
            print("\n!!! mNotify API Error:")
            print(json.dumps(error_response, indent=2))
            print("=" * 70 + "\n")
            sys.stdout.flush()
            return error_response

    def send_quick_sms(
        self,
        recipients: List[str],
        message: str,
        is_schedule: bool = False,
        schedule_date: Optional[datetime] = None,
        is_otp: bool = False,
    ) -> Dict[str, Any]:
        """
        Send a quick SMS to one or more recipients.

        Args:
            recipients: List of phone numbers (as strings)
            message: The message content
            is_schedule: Whether to schedule the message
            schedule_date: When to send the message (required if is_schedule is True)
            is_otp: Whether this is an OTP message (affects pricing)

        Returns:
            Dict containing the API response
        """
        if not recipients:
            return {"status": "error", "message": "At least one recipient is required"}

        if is_schedule and not schedule_date:
            return {
                "status": "error",
                "message": "Schedule date is required when is_schedule is True",
            }

        payload = {
            "recipient": recipients,
            "sender": self.sender_id,
            "message": message,
            "is_schedule": is_schedule,
            "schedule_date": (
                schedule_date.strftime("%Y-%m-%d %H:%M") if schedule_date else ""
            ),
        }

        if is_otp:
            payload["sms_type"] = "otp"

        return self._make_request("sms/quick", payload)

    def send_group_sms(
        self,
        group_ids: List[Union[str, int]],
        message_id: str,
        message: str = "",
        is_schedule: bool = False,
        schedule_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Send an SMS to one or more groups.

        Args:
            group_ids: List of group IDs
            message_id: The template message ID from mNotify
            message: The message content (if not using a template)
            is_schedule: Whether to schedule the message
            schedule_date: When to send the message (required if is_schedule is True)

        Returns:
            Dict containing the API response
        """
        if not group_ids:
            return {"status": "error", "message": "At least one group ID is required"}

        if not message_id and not message:
            return {
                "status": "error",
                "message": "Either message_id or message is required",
            }

        if is_schedule and not schedule_date:
            return {
                "status": "error",
                "message": "Schedule date is required when is_schedule is True",
            }

        payload = {
            "group_id[]": [str(gid) for gid in group_ids],
            "sender": self.sender_id,
            "message": message,
            "is_schedule": is_schedule,
            "schedule_date": (
                schedule_date.strftime("%Y-%m-%d %H:%M") if schedule_date else ""
            ),
        }

        if message_id:
            payload["message_id"] = str(message_id)

        return self._make_request("sms/group", payload)

    def get_scheduled_messages(self) -> Dict[str, Any]:
        """
        Get all scheduled messages.

        Returns:
            Dict containing the list of scheduled messages
        """
        return self._make_request("scheduled", {}, method="get")

    def update_scheduled_message(
        self,
        message_id: str,
        message: str,
        schedule_date: datetime,
        sender_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update a scheduled message.

        Args:
            message_id: The ID of the scheduled message to update
            message: New message content
            schedule_date: New schedule date and time
            sender_id: Optional sender ID (uses default if not provided)

        Returns:
            Dict containing the API response
        """
        payload = {
            "sender": sender_id or self.sender_id,
            "message": message,
            "schedule_date": schedule_date.strftime("%Y-%m-%d %H:%M"),
        }

        return self._make_request(f"scheduled/{message_id}", payload)


# Example usage:
# sms_service = MNotifySMS(api_key='your_api_key_here')
#
# # Send quick SMS
# result = sms_service.send_quick_sms(
#     recipients=['0241234567', '0201234567'],
#     message='Hello from our church management system!'
# )
#
# # Schedule a group SMS
# from datetime import datetime, timedelta
# schedule_time = datetime.now() + timedelta(hours=1)
# result = sms_service.send_group_sms(
#     group_ids=['1', '2'],
#     message='Reminder: Service starts in 1 hour!',
#     is_schedule=True,
#     schedule_date=schedule_time
# )
