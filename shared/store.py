"""Document store abstraction with atomic primitives.

Production uses Firestore (the same database the existing email automation
already uses for its run lock, round-robin index and successful-send log).
Tests and local development use ``InMemoryStore`` which implements identical
semantics with a process-wide lock, so concurrency tests exercise real
compare-and-set behaviour.

Only three atomic primitives are needed by the rest of the system:

* ``create``      – insert only if the document does not exist (reservation).
* ``update_if``   – read-check-write inside a transaction (compare-and-set).
* ``increment_window`` – bounded counter for rate limits (built on update_if).
"""

from __future__ import annotations

import copy
import os
import threading
import uuid
from collections.abc import Callable
from typing import Any, Protocol

Doc = dict[str, Any]
Predicate = Callable[[Doc | None], bool]
Mutator = Callable[[Doc | None], Doc]


class Store(Protocol):
    def get(self, collection: str, doc_id: str) -> Doc | None: ...

    def create(self, collection: str, doc_id: str, data: Doc) -> bool: ...

    def set(self, collection: str, doc_id: str, data: Doc, merge: bool = False) -> None: ...

    def update_if(
        self, collection: str, doc_id: str, predicate: Predicate, mutate: Mutator
    ) -> tuple[bool, Doc | None]: ...

    def query(
        self, collection: str, filters: list[tuple[str, str, Any]], limit: int = 500
    ) -> list[tuple[str, Doc]]: ...

    def add(self, collection: str, data: Doc) -> str: ...

    def delete(self, collection: str, doc_id: str) -> None: ...


_OPS: dict[str, Callable[[Any, Any], bool]] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "in": lambda a, b: a in b,
    "<": lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
    ">": lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
}


class InMemoryStore:
    """Thread-safe store with the same atomic guarantees as the Firestore adapter."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Doc]] = {}
        self._lock = threading.RLock()

    def _coll(self, collection: str) -> dict[str, Doc]:
        return self._data.setdefault(collection, {})

    def get(self, collection: str, doc_id: str) -> Doc | None:
        with self._lock:
            doc = self._coll(collection).get(doc_id)
            return copy.deepcopy(doc) if doc is not None else None

    def create(self, collection: str, doc_id: str, data: Doc) -> bool:
        with self._lock:
            coll = self._coll(collection)
            if doc_id in coll:
                return False
            coll[doc_id] = copy.deepcopy(data)
            return True

    def set(self, collection: str, doc_id: str, data: Doc, merge: bool = False) -> None:
        with self._lock:
            coll = self._coll(collection)
            if merge and doc_id in coll:
                coll[doc_id].update(copy.deepcopy(data))
            else:
                coll[doc_id] = copy.deepcopy(data)

    def update_if(self, collection: str, doc_id: str, predicate: Predicate, mutate: Mutator) -> tuple[bool, Doc | None]:
        with self._lock:
            coll = self._coll(collection)
            current = copy.deepcopy(coll.get(doc_id))
            if not predicate(current):
                return False, current
            new = mutate(copy.deepcopy(current))
            coll[doc_id] = copy.deepcopy(new)
            return True, copy.deepcopy(new)

    def query(self, collection: str, filters: list[tuple[str, str, Any]], limit: int = 500) -> list[tuple[str, Doc]]:
        with self._lock:
            out: list[tuple[str, Doc]] = []
            for doc_id, doc in self._coll(collection).items():
                if all(_OPS[op](doc.get(field), value) for field, op, value in filters):
                    out.append((doc_id, copy.deepcopy(doc)))
                    if len(out) >= limit:
                        break
            return out

    def add(self, collection: str, data: Doc) -> str:
        doc_id = uuid.uuid4().hex
        self.create(collection, doc_id, data)
        return doc_id

    def delete(self, collection: str, doc_id: str) -> None:
        with self._lock:
            self._coll(collection).pop(doc_id, None)


class FirestoreStore:
    """Firestore implementation. Collections are prefixed so the new platform can
    share the existing project/database without touching the email automation's
    ``automation_state`` / ``successful_sends`` / ``automation_report_receipts``."""

    def __init__(self, prefix: str | None = None, client: Any | None = None) -> None:
        from google.cloud import firestore

        self._firestore = firestore
        self.db = client or firestore.Client()
        self.prefix = prefix if prefix is not None else os.getenv("UCA_FIRESTORE_PREFIX", "uca_")

    def _ref(self, collection: str, doc_id: str) -> Any:
        return self.db.collection(self.prefix + collection).document(doc_id)

    def get(self, collection: str, doc_id: str) -> Doc | None:
        snap = self._ref(collection, doc_id).get()
        return snap.to_dict() if snap.exists else None

    def create(self, collection: str, doc_id: str, data: Doc) -> bool:
        from google.api_core.exceptions import AlreadyExists

        try:
            self._ref(collection, doc_id).create(data)
            return True
        except AlreadyExists:
            return False

    def set(self, collection: str, doc_id: str, data: Doc, merge: bool = False) -> None:
        self._ref(collection, doc_id).set(data, merge=merge)

    def update_if(self, collection: str, doc_id: str, predicate: Predicate, mutate: Mutator) -> tuple[bool, Doc | None]:
        ref = self._ref(collection, doc_id)
        transaction = self.db.transaction()
        firestore = self._firestore

        @firestore.transactional  # type: ignore[misc]
        def _run(txn: Any) -> tuple[bool, Doc | None]:
            snap = ref.get(transaction=txn)
            current = snap.to_dict() if snap.exists else None
            if not predicate(current):
                return False, current
            new = mutate(copy.deepcopy(current))
            txn.set(ref, new)
            return True, new

        result: tuple[bool, Doc | None] = _run(transaction)
        return result

    def query(self, collection: str, filters: list[tuple[str, str, Any]], limit: int = 500) -> list[tuple[str, Doc]]:
        from google.cloud.firestore_v1.base_query import FieldFilter

        q: Any = self.db.collection(self.prefix + collection)
        for field, op, value in filters:
            q = q.where(filter=FieldFilter(field, op, value))
        return [(snap.id, snap.to_dict() or {}) for snap in q.limit(limit).stream()]

    def add(self, collection: str, data: Doc) -> str:
        _, ref = self.db.collection(self.prefix + collection).add(data)
        return str(ref.id)

    def delete(self, collection: str, doc_id: str) -> None:
        self._ref(collection, doc_id).delete()


_default_store: Store | None = None


def get_store() -> Store:
    """Process-wide store chosen by ``UCA_STORE_BACKEND`` (``firestore`` | ``memory``)."""
    global _default_store
    if _default_store is None:
        backend = os.getenv("UCA_STORE_BACKEND", "memory").strip().lower()
        env = os.getenv("UCA_ENV", "local").strip().lower()
        if env in {"staging", "production"} and backend != "firestore":
            raise RuntimeError("UCA_STORE_BACKEND must be 'firestore' in staging/production")
        _default_store = FirestoreStore() if backend == "firestore" else InMemoryStore()
    return _default_store


def set_store(store: Store | None) -> None:
    global _default_store
    _default_store = store
