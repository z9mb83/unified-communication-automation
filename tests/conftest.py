"""Shared fixtures. Everything external (Meta, SMS gateway, Gmail, Sheets, OpenAI,
Firestore, Cloud Tasks, Secret Manager) is replaced by in-memory fakes."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
os.environ.setdefault("UCA_ENV", "test")
os.environ.setdefault("UCA_AUTH_DISABLED_FOR_LOCAL", "true")
os.environ.setdefault("RUNTIME_ENV", "cloud_run")  # legacy email logger -> stdout, no log files
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
# The unchanged email application imports itself as top-level ``app`` / ``main``.
if str(REPO / "services" / "email") not in sys.path:
    sys.path.append(str(REPO / "services" / "email"))

# Project modules are imported inside fixtures so that each component's tests
# can run as soon as that component exists (feature branches merge incrementally).

SHEET = "sheet_test_0000000001"
APP_ID = "999000999"
SECRETS = {
    "env://META_TOKEN_SHAADI": "EAAtesttokenshaadi000000000000",
    "env://META_TOKEN_MARKETING": "EAAtesttokenmarketing00000000",
    "env://META_APP_SECRET": "app-secret-for-tests",
    "env://META_VERIFY": "verify-token-for-tests",
    "env://SMS_KEY": "sms-callback-secret",
}

BRANDS: dict[str, Any] = {
    "meta_apps": {APP_ID: {"app_secret_secret": "env://META_APP_SECRET", "verify_token_secret": "env://META_VERIFY"}},
    "brands": {
        "shaadi": {
            "name": "Shaadi Bells",
            "whatsapp": {
                "enabled": True,
                "waba_id": "111",
                "app_id": APP_ID,
                "phone_numbers": [{"phone_number_id": "2001", "default": True}],
                "access_token_secret": "env://META_TOKEN_SHAADI",
            },
            "sms": {
                "enabled": True,
                "provider": "mock",
                "dlt_principal_entity_id": "1201159100000000001",
                "sender_headers": ["SHDBEL"],
                "api_secret": "env://SMS_KEY",
                "templates": [
                    {
                        "template_id": "1207160000000000001",
                        "name": "reminder",
                        "sender_header": "SHDBEL",
                        "content_type": "service_implicit",
                        "content": "Dear {#var#}, your consultation is on {#var#}. - Shaadi Bells",
                    }
                ],
            },
        },
        "marketing": {
            "name": "99 Marketing Services",
            "whatsapp": {
                "enabled": True,
                "waba_id": "222",
                "app_id": APP_ID,
                "phone_numbers": [{"phone_number_id": "2002", "default": True}],
                "access_token_secret": "env://META_TOKEN_MARKETING",
            },
            "sms": {
                "enabled": True,
                "provider": "mock",
                "dlt_principal_entity_id": "1201159100000000002",
                "sender_headers": ["NNMKTG"],
                "templates": [
                    {
                        "template_id": "1207160000000000002",
                        "name": "offer",
                        "sender_header": "NNMKTG",
                        "content_type": "service_explicit",
                        "content": "Hi {#var#}, reply YES for details. 99MS",
                    }
                ],
            },
        },
        "staffing": {"name": "99 Staffing Services"},
        "property": {"name": "Property Experts Group"},
        "skyline": {"name": "Skyline Capital"},
    },
}

SHEETS: dict[str, Any] = {
    "spreadsheets": [
        {
            "spreadsheet_id": SHEET,
            "tabs": [
                {
                    "tab": "Shaadi WA",
                    "brand_id": "shaadi",
                    "channels": ["whatsapp", "sms"],
                    "header_row": 1,
                    "first_data_row": 2,
                    "columns": {"name": "A", "phone": "B", "city": "C"},
                },
                {
                    "tab": "Marketing WA",
                    "brand_id": "marketing",
                    "channels": ["whatsapp", "sms"],
                    "header_row": 1,
                    "first_data_row": 2,
                    "columns": {"name": "A", "phone": "B"},
                },
                {
                    "tab": "WA Contacts",
                    "brand_column": "A",
                    "channels": ["whatsapp"],
                    "header_row": 1,
                    "first_data_row": 2,
                    "columns": {"brand": "A", "name": "B", "phone": "C"},
                },
                {
                    "tab": "Shaaadibells",
                    "brand_id": "shaadi",
                    "channels": ["email"],
                    "header_row": 2,
                    "first_data_row": 3,
                    "columns": {"name": "A", "email": "B"},
                },
            ],
        }
    ]
}

ACCESS = {
    "users": {
        "admin@example.com": {"admin": True},
        "op@example.com": {"brands": {"shaadi": "operator", "marketing": "viewer"}},
        "viewer@example.com": {"brands": {"shaadi": "viewer"}},
    }
}

TEMPLATE_SHAADI = {
    "id": "7001",
    "name": "welcome_offer",
    "language": "en",
    "category": "MARKETING",
    "status": "APPROVED",
    "components": [
        {"type": "HEADER", "format": "TEXT", "text": "Hello {{1}}"},
        {"type": "BODY", "text": "Hi {{1}}, meet our advisor in {{2}}."},
        {
            "type": "BUTTONS",
            "buttons": [
                {"type": "URL", "text": "Book", "url": "https://x.example/b/{{1}}"},
                {"type": "QUICK_REPLY", "text": "STOP"},
            ],
        },
    ],
}
TEMPLATE_MARKETING = {
    "id": "8001",
    "name": "promo",
    "language": "en_US",
    "category": "MARKETING",
    "status": "APPROVED",
    "components": [{"type": "BODY", "text": "Offer for {{1}}"}],
}


class FakeMetaClient:
    """Stands in for MetaClient; scripted per recipient phone."""

    lock = threading.Lock()

    def __init__(self, waba_templates: dict[str, list[dict[str, Any]]], numbers: dict[str, list[str]]) -> None:
        self.waba_templates = waba_templates
        self.numbers = numbers
        self.sent: list[dict[str, Any]] = []
        self.script: dict[str, Exception] = {}
        self.delay: float = 0.0

    def list_templates(self, waba_id: str) -> list[dict[str, Any]]:
        return list(self.waba_templates.get(waba_id, []))

    def list_phone_numbers(self, waba_id: str) -> list[dict[str, Any]]:
        return [{"id": n, "display_phone_number": "+91 0000"} for n in self.numbers.get(waba_id, [])]

    def send_template(self, **kwargs: Any) -> dict[str, Any]:
        if self.delay:
            import time

            time.sleep(self.delay)
        error = self.script.get(kwargs["to"])
        if error is not None:
            raise error
        with self.lock:
            self.sent.append(kwargs)
            return {"wamid": f"wamid.{len(self.sent)}", "message_status": "accepted", "wa_id": kwargs["to"]}


@pytest.fixture()
def fake_meta() -> FakeMetaClient:
    return FakeMetaClient({"111": [TEMPLATE_SHAADI], "222": [TEMPLATE_MARKETING]}, {"111": ["2001"], "222": ["2002"]})


@pytest.fixture()
def channels_cfg() -> Any:
    from shared.config import ChannelsConfig

    return ChannelsConfig.model_validate(
        {
            "whatsapp": {
                "live_send_enabled": True,
                "duplicate_window_hours": 24,
                "default_rate_limit": {"per_minute": 100, "per_day": 1000},
            },
            "sms": {"live_send_enabled": False, "default_rate_limit": {"per_minute": 100, "per_day": 1000}},
        }
    )


@pytest.fixture()
def ctx(fake_meta: FakeMetaClient, channels_cfg: Any) -> Any:
    from services.api.deps import AppContext, set_context
    from services.sms.gateway_interface import get_gateway
    from services.sms.providers.mock import MockSmsGateway
    from shared.brand_registry import BrandRegistry
    from shared.config import load_settings
    from shared.job_manager import InlineQueue, set_queue
    from shared.sheet_registry import SheetRegistry
    from shared.store import InMemoryStore, set_store

    MockSmsGateway.reset()
    store = InMemoryStore()
    queue = InlineQueue()
    set_store(store)
    set_queue(queue)
    context = AppContext(
        settings=load_settings(),
        store=store,
        queue=queue,
        brands=BrandRegistry.from_dict(BRANDS, REPO / "services" / "email" / "brands"),
        sheets=SheetRegistry.from_dict(SHEETS),
        channels=channels_cfg,
        access=ACCESS,
        meta_client_factory=lambda brand: fake_meta,
        sms_gateway_factory=lambda brand: get_gateway("mock", None),
        secret_getter=lambda ref: SECRETS[ref],
    )
    set_context(context)
    yield context
    set_context(None)
    set_store(None)
    set_queue(None)


@pytest.fixture()
def client(ctx: Any) -> Any:
    from fastapi.testclient import TestClient

    from services.api.main import create_app

    return TestClient(create_app("all"), raise_server_exceptions=True)


def headers(user: str = "admin@example.com", mutating: bool = True) -> dict[str, str]:
    import uuid
    from datetime import UTC, datetime

    h = {"X-UCA-Test-User": user}
    if mutating:
        h["X-UCA-Request-Id"] = uuid.uuid4().hex + uuid.uuid4().hex[:8]
        h["X-UCA-Timestamp"] = datetime.now(UTC).isoformat()
    return h


def drain(ctx: Any, client: Any, channel: str | None = None, rounds: int = 10) -> list[dict[str, Any]]:
    """Run queued tasks through the worker endpoint (as Cloud Tasks would)."""
    results = []
    for _ in range(rounds):
        tasks = ctx.queue.drain(channel)
        if not tasks:
            break
        for task in tasks:
            resp = client.post(f"/workers/{task['channel']}/dispatch", json=task["payload"])
            assert resp.status_code == 200, resp.text
            results.append(resp.json())
    return results
