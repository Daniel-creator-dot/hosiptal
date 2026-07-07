"""
Cross-process payment idempotency for cashier POSTs.

Uses Django cache (Redis in production) so duplicate submits from the same
browser form token coalesce even when select_for_update races or multiple
Gunicorn workers handle the same double-click.
"""
from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

from django.core.cache import cache

logger = logging.getLogger(__name__)


class PaymentIdempotency:
    PREFIX = "hms:payidemp:v2"

    @classmethod
    def _keys(cls, user_id: int, token: str) -> tuple[str, str]:
        t = (token or "").strip()[:96]
        base = f"{cls.PREFIX}:{int(user_id)}:{t}"
        return f"{base}:rid", f"{base}:lck"

    @classmethod
    def begin(cls, user_id: int, token: str) -> Tuple[str, Optional[str]]:
        """
        Returns:
            ('CACHED', receipt_pk_str) — reuse this receipt, do not charge again
            ('LOCKED', None) — this request owns the lock; caller must complete() or abort()
            ('BUSY', None) — another request held the lock and no receipt appeared in time
            ('INVALID', None) — missing/invalid token (caller may fall back to non-token flow)
        """
        tok = (token or "").strip()
        if not tok or not user_id:
            return "INVALID", None
        receipt_key, lock_key = cls._keys(user_id, tok)
        cached = cache.get(receipt_key)
        if cached:
            return "CACHED", str(cached)

        if cache.add(lock_key, "1", timeout=120):
            return "LOCKED", None

        for _ in range(30):
            time.sleep(0.05)
            cached = cache.get(receipt_key)
            if cached:
                return "CACHED", str(cached)
        logger.warning("payment_idempotency: busy timeout user=%s token_prefix=%s", user_id, tok[:12])
        return "BUSY", None

    @classmethod
    def complete(cls, user_id: int, token: str, receipt_pk) -> None:
        receipt_key, lock_key = cls._keys(user_id, token)
        cache.set(receipt_key, str(receipt_pk), timeout=86400)
        cache.delete(lock_key)

    @classmethod
    def abort(cls, user_id: int, token: str) -> None:
        _, lock_key = cls._keys(user_id, token)
        cache.delete(lock_key)
