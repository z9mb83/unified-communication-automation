import copy
import os

import pytest

from shared.audit import mask_address, sanitize, scrub_text
from shared.brand_registry import BrandRegistry
from shared.exceptions import BrandResolutionError, ConfigurationError, ValidationError
from shared.secrets import SecretResolver, SecretValue
from shared.sheet_registry import SheetRegistry, derived_contact_id, normalize_phone
from tests.conftest import BRANDS, SHEET, SHEETS


def test_brand_registry_rejects_shared_waba():
    data = copy.deepcopy(BRANDS)
    data["brands"]["marketing"]["whatsapp"]["waba_id"] = "111"
    with pytest.raises(ConfigurationError, match="WABA"):
        BrandRegistry.from_dict(data)


def test_brand_registry_rejects_unknown_brand_and_raw_secret():
    data = copy.deepcopy(BRANDS)
    data["brands"]["other"] = {"name": "x"}
    with pytest.raises(ConfigurationError):
        BrandRegistry.from_dict(data)
    data = copy.deepcopy(BRANDS)
    data["brands"]["shaadi"]["whatsapp"]["access_token_secret"] = "EAAraw-token-pasted-here"
    with pytest.raises(ConfigurationError):
        BrandRegistry.from_dict(data)


def test_enabled_whatsapp_requires_ids():
    data = copy.deepcopy(BRANDS)
    data["brands"]["shaadi"]["whatsapp"]["waba_id"] = ""
    with pytest.raises(ConfigurationError):
        BrandRegistry.from_dict(data)


def test_sheet_registry_exact_mapping_only():
    reg = SheetRegistry.from_dict(SHEETS)
    assert reg.resolve_brand(SHEET, "Shaadi WA", "shaadi", "whatsapp").brand_id == "shaadi"
    with pytest.raises(BrandResolutionError):
        reg.resolve(SHEET, "shaadi wa")  # case-sensitive exact match; no guessing
    with pytest.raises(BrandResolutionError) as e:
        reg.resolve_brand(SHEET, "Shaadi WA", "marketing", "whatsapp")
    assert e.value.code == "brand_mismatch"
    with pytest.raises(BrandResolutionError):
        reg.resolve_brand(SHEET, "Shaaadibells", "shaadi", "whatsapp")  # tab not enabled for channel
    generic = reg.resolve_brand(SHEET, "WA Contacts", "marketing", "whatsapp")
    assert generic.is_generic


def test_phone_normalization():
    assert normalize_phone("+91 98765 43210", "91") == "919876543210"
    assert normalize_phone("098765 43210", "91") == "919876543210"
    assert normalize_phone("9876543210", "91") == "919876543210"
    with pytest.raises(ValidationError):
        normalize_phone("12", "91")


def test_contact_id_independent_of_row_position():
    assert derived_contact_id("shaadi", "phone", "919") == derived_contact_id("shaadi", "phone", "919")
    assert derived_contact_id("shaadi", "phone", "919") != derived_contact_id("marketing", "phone", "919")


def test_secrets_never_printed_and_env_refs_blocked_in_prod(monkeypatch):
    value = SecretValue("super-secret")
    assert "super-secret" not in repr(value) and "super-secret" not in str(value)
    monkeypatch.setenv("X_TOKEN", "abc")
    assert SecretResolver(env="local").get("env://X_TOKEN").reveal() == "abc"
    with pytest.raises(ConfigurationError):
        SecretResolver(env="production").get("env://X_TOKEN")
    calls = []
    resolver = SecretResolver(env="production", fetcher=lambda ref: calls.append(ref) or "v")
    resolver.get("projects/p/secrets/s/versions/latest")
    resolver.get("projects/p/secrets/s/versions/latest")
    assert len(calls) == 1  # cached


def test_audit_redacts_tokens_and_content():
    out = sanitize(
        {
            "access_token": "EAAxyz",
            "body": "hello",
            "nested": {"Authorization": "Bearer abc"},
            "note": "token " + "EAA" + "ABBBBCCCCDDDDEEEEFFFFGGGG" + " in text",
        }
    )
    assert out["access_token"] == "[REDACTED]"
    assert out["body"] == "[CONTENT OMITTED]"
    assert out["nested"]["Authorization"] == "[REDACTED]"
    assert "EAAABBBB" not in out["note"]
    assert "abc123" not in scrub_text("Bearer abc123")
    assert mask_address("919876543210").endswith("3210") and "98765" not in mask_address("919876543210")


def test_production_requires_firestore_backend(monkeypatch):
    from shared import store as store_module

    store_module.set_store(None)
    monkeypatch.setenv("UCA_ENV", "production")
    monkeypatch.setenv("UCA_STORE_BACKEND", "memory")
    with pytest.raises(RuntimeError):
        store_module.get_store()
    store_module.set_store(None)
    os.environ["UCA_ENV"] = "test"
