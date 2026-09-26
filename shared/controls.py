"""Persistent Start / Stop / Emergency Stop flags.

Workers call :meth:`Controls.check_dispatch` immediately before every provider
call, so a Stop takes effect for the very next dispatch even if messages are
already queued in Cloud Tasks.

Defaults are fail-safe: a brand/channel that has never been started is stopped.
Starting a channel only allows *already approved* messages to dispatch; it
never creates or approves messages by itself.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from shared.exceptions import AuthorizationError, ControlBlockedError
from shared.store import Store

COLLECTION = "controls"
GLOBAL_DOC = "global"


def scope_id(brand_id: str, channel: str) -> str:
    return f"{brand_id}:{channel}"


class Controls:
    def __init__(self, store: Store) -> None:
        self.store = store

    # ---- reads -----------------------------------------------------------------------

    def global_state(self) -> dict[str, Any]:
        return self.store.get(COLLECTION, GLOBAL_DOC) or {"emergency_stop": False}

    def scope_state(self, brand_id: str, channel: str) -> dict[str, Any]:
        return self.store.get(COLLECTION, scope_id(brand_id, channel)) or {"running": False}

    def dispatch_allowed(self, brand_id: str, channel: str) -> tuple[bool, str]:
        glob = self.global_state()
        if glob.get("emergency_stop"):
            return False, "emergency_stop_active"
        scope = self.scope_state(brand_id, channel)
        if not scope.get("running"):
            return False, f"{channel}_stopped_for_{brand_id}"
        return True, "ok"

    def check_dispatch(self, brand_id: str, channel: str) -> None:
        allowed, reason = self.dispatch_allowed(brand_id, channel)
        if not allowed:
            raise ControlBlockedError(f"dispatch blocked: {reason}", code=reason)

    # ---- writes ----------------------------------------------------------------------

    def _write_scope(self, brand_id: str, channel: str, running: bool, actor: str, reason: str) -> dict[str, Any]:
        record = {
            "brand_id": brand_id,
            "channel": channel,
            "running": running,
            "updated_by": actor,
            "updated_at": datetime.now(UTC).isoformat(),
            "reason": reason[:300],
        }
        self.store.set(COLLECTION, scope_id(brand_id, channel), record)
        return record

    def start(self, brand_id: str, channel: str, actor: str, reason: str = "") -> dict[str, Any]:
        if self.global_state().get("emergency_stop"):
            raise ControlBlockedError(
                "Emergency stop is active; an admin must release it before starting", code="emergency_stop_active"
            )
        return self._write_scope(brand_id, channel, True, actor, reason or "started")

    def stop(self, brand_id: str, channel: str, actor: str, reason: str = "") -> dict[str, Any]:
        return self._write_scope(brand_id, channel, False, actor, reason or "stopped")

    def emergency_stop(
        self, actor: str, reason: str, brand_ids: list[str] | None = None, channels: list[str] | None = None
    ) -> dict[str, Any]:
        record = {
            "emergency_stop": True,
            "engaged_by": actor,
            "engaged_at": datetime.now(UTC).isoformat(),
            "reason": reason[:300],
        }
        # Global flag first: it blocks every dispatch immediately.
        self.store.set(COLLECTION, GLOBAL_DOC, record)
        for brand_id in brand_ids or []:
            for channel in channels or []:
                self._write_scope(brand_id, channel, False, actor, "emergency stop")
        return record

    def release_emergency_stop(self, actor: str, is_admin: bool, reason: str) -> dict[str, Any]:
        if not is_admin:
            raise AuthorizationError("Only an admin can release the emergency stop")
        record = {
            "emergency_stop": False,
            "released_by": actor,
            "released_at": datetime.now(UTC).isoformat(),
            "reason": reason[:300],
        }
        # Releasing does NOT restart channels: each brand/channel stays stopped
        # until someone explicitly starts it again.
        self.store.set(COLLECTION, GLOBAL_DOC, record)
        return record

    def snapshot(self, brand_ids: list[str], channels: list[str]) -> dict[str, Any]:
        return {
            "global": self.global_state(),
            "scopes": {scope_id(b, c): self.scope_state(b, c) for b in brand_ids for c in channels},
        }
