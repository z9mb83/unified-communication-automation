import threading
from datetime import UTC, datetime, timedelta

import pytest

from shared.exceptions import DuplicateJobError, ReplayError
from shared.idempotency import (
    claim_recipient_window,
    guard_selection,
    message_idempotency_key,
    release_recipient_window,
    reserve_request,
)
from shared.store import InMemoryStore


def test_create_is_atomic_under_concurrency():
    store = InMemoryStore()
    wins = []

    def worker():
        if store.create("c", "doc", {"x": 1}):
            wins.append(1)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(wins) == 1


def test_update_if_compare_and_set():
    store = InMemoryStore()
    store.set("c", "d", {"status": "queued"})
    ok, _ = store.update_if("c", "d", lambda c: c["status"] == "queued", lambda c: {**c, "status": "sending"})
    assert ok
    ok2, current = store.update_if("c", "d", lambda c: c["status"] == "queued", lambda c: {**c, "status": "sending"})
    assert not ok2 and current["status"] == "sending"


def test_message_key_is_stable_and_scoped():
    a = message_idempotency_key("shaadi", "whatsapp", "job1", "c1")
    assert a == message_idempotency_key("shaadi", "whatsapp", "job1", "c1")
    assert a != message_idempotency_key("marketing", "whatsapp", "job1", "c1")
    assert a != message_idempotency_key("shaadi", "sms", "job1", "c1")


def test_request_replay_and_staleness():
    store = InMemoryStore()
    now = datetime.now(UTC).isoformat()
    reserve_request(store, "a" * 32, now, "u@x.com", 300)
    with pytest.raises(ReplayError) as e:
        reserve_request(store, "a" * 32, now, "u@x.com", 300)
    assert e.value.code == "replayed_request"
    old = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
    with pytest.raises(ReplayError) as e2:
        reserve_request(store, "b" * 32, old, "u@x.com", 300)
    assert e2.value.code == "stale_request"
    with pytest.raises(ReplayError):
        reserve_request(store, "short", now, "u@x.com", 300)


def test_selection_guard_blocks_second_submission_of_same_rows():
    store = InMemoryStore()
    guard_selection(store, "fp1", "job_a")
    guard_selection(store, "fp1", "job_a")  # same job (retry) is fine
    with pytest.raises(DuplicateJobError):
        guard_selection(store, "fp1", "job_b")


def test_recipient_window_claim_and_release():
    store = InMemoryStore()
    ok, _ = claim_recipient_window(store, "shaadi", "whatsapp", "t1", "919", "m_1", 24)
    assert ok
    ok2, existing = claim_recipient_window(store, "shaadi", "whatsapp", "t1", "919", "m_2", 24)
    assert not ok2 and existing == "m_1"
    # other brand / channel are independent
    assert claim_recipient_window(store, "marketing", "whatsapp", "t1", "919", "m_3", 24)[0]
    assert claim_recipient_window(store, "shaadi", "sms", "t1", "919", "m_4", 24)[0]
    release_recipient_window(store, "shaadi", "whatsapp", "t1", "919", "m_1")
    assert claim_recipient_window(store, "shaadi", "whatsapp", "t1", "919", "m_2", 24)[0]
