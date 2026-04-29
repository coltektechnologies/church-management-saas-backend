"""Single Redis lock so only one backup export runs at a time (admin HTTP + Celery workers)."""

from __future__ import annotations

import redis
from django.conf import settings

LOCK_KEY = "church_saas:celery_backup_dumpdata_lock"
LOCK_TTL_S = 7200


def _client():
    url = getattr(settings, "CELERY_BROKER_URL", None) or "redis://localhost:6379/0"
    return redis.Redis.from_url(url)


def acquire_backup_lock(blocking=True, blocking_timeout_s=7100):
    """
    Returns (lock_obj, acquired: bool). Caller must release() if acquired.
    blocking_timeout_s only used when blocking=True.
    """
    try:
        client = _client()
        lock = client.lock(LOCK_KEY, timeout=LOCK_TTL_S)
        kw = {}
        if blocking:
            kw["blocking"] = True
            kw["blocking_timeout"] = blocking_timeout_s
        else:
            kw["blocking"] = False
        acquired = lock.acquire(**kw)
        return lock, bool(acquired)
    except redis.ConnectionError:
        return None, False
