import pytest

from shared.consent import ConsentRegistry
from shared.controls import Controls
from shared.exceptions import AuthorizationError, ConsentError, ControlBlockedError
from shared.rate_limits import RateLimiter
from shared.store import InMemoryStore
from shared.suppression import SuppressionList


def test_default_is_stopped_and_start_stop_are_scoped():
    c = Controls(InMemoryStore())
    assert c.dispatch_allowed("shaadi", "whatsapp")[0] is False
    c.start("shaadi", "whatsapp", "a")
    assert c.dispatch_allowed("shaadi", "whatsapp")[0]
    assert not c.dispatch_allowed("shaadi", "sms")[0]
    assert not c.dispatch_allowed("marketing", "whatsapp")[0]
    c.stop("shaadi", "whatsapp", "a")
    with pytest.raises(ControlBlockedError):
        c.check_dispatch("shaadi", "whatsapp")


def test_emergency_stop_blocks_everything_and_release_needs_admin():
    c = Controls(InMemoryStore())
    c.start("shaadi", "whatsapp", "a")
    c.emergency_stop("a", "test", ["shaadi"], ["whatsapp"])
    assert c.dispatch_allowed("shaadi", "whatsapp") == (False, "emergency_stop_active")
    with pytest.raises(ControlBlockedError):
        c.start("shaadi", "whatsapp", "a")
    with pytest.raises(AuthorizationError):
        c.release_emergency_stop("a", is_admin=False, reason="")
    c.release_emergency_stop("admin", is_admin=True, reason="done")
    # channels stay stopped after release
    assert c.dispatch_allowed("shaadi", "whatsapp") == (False, "whatsapp_stopped_for_shaadi")


def test_consent_is_per_brand_and_per_channel():
    reg = ConsentRegistry(InMemoryStore())
    reg.record_opt_in("shaadi", "whatsapp", "919", source="sheet_import", evidence="form", recorded_by="a")
    reg.require_opt_in("shaadi", "whatsapp", "919")
    with pytest.raises(ConsentError):
        reg.require_opt_in("marketing", "whatsapp", "919")
    with pytest.raises(ConsentError):
        reg.require_opt_in("shaadi", "sms", "919")


def test_opt_out_wins_and_import_cannot_override():
    reg = ConsentRegistry(InMemoryStore())
    reg.record_opt_in("shaadi", "whatsapp", "919", source="sheet_import", evidence="form", recorded_by="a")
    reg.record_opt_out("shaadi", "whatsapp", "919", source="recipient_keyword", evidence="STOP", recorded_by="w")
    with pytest.raises(ConsentError) as e:
        reg.require_opt_in("shaadi", "whatsapp", "919")
    assert e.value.code == "consent_opted_out"
    changed, reason = reg.record_opt_in(
        "shaadi", "whatsapp", "919", source="sheet_import", evidence="x", recorded_by="a"
    )
    assert not changed and reason == "blocked_by_existing_opt_out"
    changed, _ = reg.record_opt_in(
        "shaadi", "whatsapp", "919", source="double_opt_in", evidence="START", recorded_by="w"
    )
    assert changed


def test_suppression_scoped():
    s = SuppressionList(InMemoryStore())
    s.add("shaadi", "sms", "919", reason="opt_out", source="t", actor="a")
    assert s.is_suppressed("shaadi", "sms", "919")
    assert not s.is_suppressed("shaadi", "whatsapp", "919")
    assert not s.is_suppressed("marketing", "sms", "919")
    s.remove("shaadi", "sms", "919", actor="a")
    assert not s.is_suppressed("shaadi", "sms", "919")


def test_rate_limiter_per_brand_channel():
    limiter = RateLimiter(InMemoryStore())
    limiter.acquire("shaadi", "whatsapp", per_minute=2, per_day=10)
    limiter.acquire("shaadi", "whatsapp", per_minute=2, per_day=10)
    from shared.exceptions import RateLimitedError

    with pytest.raises(RateLimitedError):
        limiter.acquire("shaadi", "whatsapp", per_minute=2, per_day=10)
    limiter.acquire("marketing", "whatsapp", per_minute=2, per_day=10)  # isolated
    limiter.acquire("shaadi", "sms", per_minute=2, per_day=10)
