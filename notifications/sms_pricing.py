"""Helpers for SMS segment cost (stored on SMSLog when configured)."""

from decimal import Decimal, InvalidOperation

from django.conf import settings


def segment_unit_price() -> Decimal | None:
    raw = getattr(settings, "SMS_SEGMENT_UNIT_PRICE", None)
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        return None


def apply_sms_log_segment_cost(sms_log, *, force: bool = False) -> None:
    """
    Set SMSLog.cost from SMS_SEGMENT_UNIT_PRICE * sms_count (when cost not set).
    Uses SMS_PRICE_CURRENCY on price_unit when set.
    """
    if not force and sms_log.cost is not None:
        return
    unit = segment_unit_price()
    if unit is None:
        return
    segs = int(sms_log.sms_count or 0)
    if segs < 1:
        segs = 1
    sms_log.cost = (unit * segs).quantize(Decimal("0.0001"))
    cur = getattr(settings, "SMS_PRICE_CURRENCY", "") or ""
    if cur:
        sms_log.price_unit = str(cur).strip().upper()[:3]


def estimated_cost_display(sms_log) -> tuple[str, bool]:
    """
    Returns (formatted string, is_estimate).
    Uses stored cost if present; otherwise estimates from settings + sms_count.
    """
    unit = segment_unit_price()
    currency = (
        (sms_log.price_unit or "").strip()
        or getattr(settings, "SMS_PRICE_CURRENCY", "GHS")
        or "GHS"
    )
    if sms_log.cost is not None:
        return (f"{sms_log.cost:.4f} {currency}", False)
    segs = max(int(sms_log.sms_count or 0), 1)
    if unit is not None:
        try:
            est = (unit * segs).quantize(Decimal("0.0001"))
            return (f"{est:.4f} {currency} (est.)", True)
        except Exception:
            pass
    return ("—", False)
