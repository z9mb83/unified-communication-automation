"""Firestore-backed state for Cloud Run: round-robin index, cross-brand
duplicate log, and a run lock.

Mirrors the interface of the local JSON-file classes in global_state.py and
the file_lock() context manager in utilities.py, so brand_runner.py and
main.py don't need to know which backend is active.
"""

from __future__ import annotations

import os
import socket
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator
from zoneinfo import ZoneInfo

from google.cloud import firestore

from app.config_loader import BRAND_ORDER

_STATE_COLLECTION = os.getenv("FIRESTORE_STATE_COLLECTION", "automation_state")
_SENDS_COLLECTION = os.getenv("FIRESTORE_SENDS_COLLECTION", "successful_sends")


def _client() -> firestore.Client:
    return firestore.Client()


class FirestoreGlobalState:
    def __init__(self) -> None:
        self.db = _client()
        self.sends = self.db.collection(_SENDS_COLLECTION)

    def has_recent_recipient(self, recipient: str, now: datetime, days: int, tz: ZoneInfo) -> bool:
        cutoff = now - timedelta(days=days)
        normalized = recipient.strip().lower()
        for doc in self.sends.where("recipient", "==", normalized).stream():
            item = doc.to_dict() or {}
            sent_at = item.get("sent_at")
            if not sent_at:
                continue
            try:
                parsed = datetime.fromisoformat(str(sent_at))
            except ValueError:
                continue
            parsed = parsed.astimezone(tz) if parsed.tzinfo else parsed.replace(tzinfo=tz)
            if parsed >= cutoff:
                return True
        return False

    def record_success(self, brand_id: str, sender: str, recipient: str, sent_at: datetime, message_id: str) -> None:
        self.sends.add(
            {
                "recipient": recipient.strip().lower(),
                "brand": brand_id,
                "sender": sender.strip().lower(),
                "sent_at": sent_at.isoformat(),
                "gmail_message_id": message_id,
                "result": "Sent",
            }
        )


class FirestoreRoundRobinState:
    def __init__(self) -> None:
        self.db = _client()
        self.doc_ref = self.db.collection(_STATE_COLLECTION).document("round_robin")

    def ordered_brand_ids(self, selected_brand: str | None = None) -> list[str]:
        if selected_brand:
            return [selected_brand]
        snapshot = self.doc_ref.get()
        data = snapshot.to_dict() or {}
        start = int(data.get("next_start_index", 0)) % len(BRAND_ORDER)
        return BRAND_ORDER[start:] + BRAND_ORDER[:start]

    def advance(self) -> None:
        transaction = self.db.transaction()
        doc_ref = self.doc_ref

        @firestore.transactional
        def _advance(txn: firestore.Transaction) -> None:
            snapshot = doc_ref.get(transaction=txn)
            data = snapshot.to_dict() or {}
            current = int(data.get("next_start_index", 0))
            txn.set(doc_ref, {"next_start_index": (current + 1) % len(BRAND_ORDER)})

        _advance(transaction)


@contextmanager
def firestore_lock(name: str = "run_lock", ttl_minutes: int = 30) -> Iterator[bool]:
    """A short-lived Firestore lock that stands in for the VM's flock/msvcrt
    file lock, so overlapping Cloud Run executions don't double-send."""
    db = _client()
    doc_ref = db.collection(_STATE_COLLECTION).document(name)
    owner = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)

    transaction = db.transaction()

    @firestore.transactional
    def _acquire(txn: firestore.Transaction) -> bool:
        snapshot = doc_ref.get(transaction=txn)
        data = snapshot.to_dict() or {}
        locked_until_raw = data.get("locked_until")
        if locked_until_raw:
            try:
                locked_until = datetime.fromisoformat(locked_until_raw)
            except ValueError:
                locked_until = None
            if locked_until and locked_until > now:
                return False
        txn.set(doc_ref, {"owner": owner, "locked_until": (now + timedelta(minutes=ttl_minutes)).isoformat()})
        return True

    acquired = _acquire(transaction)
    try:
        yield acquired
    finally:
        if acquired:
            current = doc_ref.get().to_dict() or {}
            if current.get("owner") == owner:
                doc_ref.delete()
