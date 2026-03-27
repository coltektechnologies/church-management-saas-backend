"""Safe logging for registration flows — never log passwords or tokens."""

from __future__ import annotations

from typing import Any

_REDACT_EXACT = frozenset(
    {
        "password",
        "confirm_password",
        "old_password",
        "new_password",
        "token",
        "access_token",
        "refresh_token",
        "secret",
        "mfa_secret",
        "api_key",
        "authorization",
    }
)


def redact_registration_snapshot(data: Any) -> Any:
    """
    Return a structure suitable for logs: password-like keys become ***REDACTED***.
    """
    if data is None:
        return None
    if isinstance(data, dict):
        out: dict[str, Any] = {}
        for key, value in data.items():
            lk = str(key).lower()
            if lk in _REDACT_EXACT or "password" in lk:
                out[key] = "***REDACTED***"
            else:
                out[key] = redact_registration_snapshot(value)
        return out
    if isinstance(data, list):
        return [redact_registration_snapshot(item) for item in data]
    if isinstance(data, tuple):
        return tuple(redact_registration_snapshot(item) for item in data)
    return data
