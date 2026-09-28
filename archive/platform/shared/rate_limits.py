"""Atomic fixed-window rate limits per (brand, channel).

Each brand/channel has its own counters, so one brand exhausting its quota (or
a provider throttling one WhatsApp number) never slows another.

Email pacing is NOT handled here: the existing email automation keeps its own
mailbox daily/hourly limits, minimum gap and sending hours.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from shared.exceptions import RateLimitedError
from shared.store import Store

COLLECTION = "rate_limits"


class RateLimiter:
    def __init__(self, store: Store) -> None:
        self.store = store

    def _consume(self, doc_id: str, limit: int) -> tuple[bool, int]:
        def allowed(current: dict[str, Any] | None) -> bool:
            return int((current or {}).get("count", 0)) < limit

        def mutate(current: dict[str, Any] | None) -> dict[str, Any]:
            return {"count": int((current or {}).get("count", 0)) + 1}

        ok, current = self.store.update_if(COLLECTION, doc_id, allowed, mutate)
        return ok, int((current or {}).get("count", 0))

    def _refund(self, doc_id: str) -> None:
        self.store.update_if(
            COLLECTION,
            doc_id,
            lambda c: bool(c and int(c.get("count", 0)) > 0),
            lambda c: {"count": int((c or {}).get("count", 1)) - 1},
        )

    def acquire(self, brand_id: str, channel: str, per_minute: int, per_day: int, now: datetime | None = None) -> None:
        """Consume one unit from both windows or raise RateLimitedError (nothing consumed)."""
        now = now or datetime.now(UTC)
        minute_id = f"{brand_id}:{channel}:m:{now:%Y%m%d%H%M}"
        day_id = f"{brand_id}:{channel}:d:{now:%Y%m%d}"
        ok_day, _ = self._consume(day_id, per_day)
        if not ok_day:
            seconds_to_midnight = 86400 - (now.hour * 3600 + now.minute * 60 + now.second)
            raise RateLimitedError(
                f"daily {channel} limit {per_day} reached for {brand_id}",
                code="local_daily_limit",
                retry_after_seconds=max(seconds_to_midnight, 60),
            )
        ok_min, _ = self._consume(minute_id, per_minute)
        if not ok_min:
            self._refund(day_id)
            raise RateLimitedError(
                f"per-minute {channel} limit {per_minute} reached for {brand_id}",
                code="local_minute_limit",
                retry_after_seconds=max(60 - now.second, 5),
            )
