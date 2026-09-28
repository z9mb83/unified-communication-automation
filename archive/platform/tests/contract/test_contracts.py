"""Contract tests: Apps Script <-> API routes, Meta request/notification shapes."""

import json
import re
from pathlib import Path

from services.api.main import create_app
from services.whatsapp.template_renderer import render_components
from services.whatsapp.template_validator import parse_template
from tests.conftest import TEMPLATE_SHAADI

REPO = Path(__file__).resolve().parents[2]
GS = REPO / "apps" / "google-sheets"
FIXTURES = REPO / "tests" / "fixtures"


def routes_of(role: str) -> set[tuple[str, str]]:
    paths = create_app(role).openapi()["paths"]
    return {(method.upper(), path) for path, ops in paths.items() for method in ops}


def api_routes() -> set[tuple[str, str]]:
    return routes_of("api")


def test_every_apps_script_call_has_an_api_route():
    routes = api_routes()
    source = "\n".join(p.read_text() for p in GS.glob("*.gs"))
    calls = re.findall(r"api(Get|Post)_\('([^']+)'", source)
    dynamic = re.findall(r"api(Get|Post)_\('/v1/' \+ (\w+) \+ '([^']+)'", source)
    assert calls, "no API calls found in Apps Script"
    for kind, path in calls:
        method = "GET" if kind == "Get" else "POST"
        if path.endswith("/"):
            continue
        assert (method, path) in routes or any(
            m == method and re.fullmatch(re.sub(r"\{[^}]+\}", "[^/]+", p), path) for m, p in routes
        ), (method, path)
    for kind, _var, suffix in dynamic:
        method = "GET" if kind == "Get" else "POST"
        for channel in ("email", "whatsapp", "sms"):
            candidate = f"/v1/{channel}{suffix}" if suffix.startswith("/") else f"/v1/{channel}/{suffix}"
            if suffix.startswith("/start") or suffix.startswith("/stop"):
                candidate = f"/v1/controls/{channel}{suffix}"
            if (method, candidate) in routes:
                break
        else:
            raise AssertionError(f"no route for dynamic call {method} /v1/<channel>{suffix}")


def test_menu_handlers_exist():
    source = "\n".join(p.read_text() for p in GS.glob("*.gs"))
    handlers = re.findall(r"\.addItem\('[^']+', '(\w+)'\)", (GS / "Menu.gs").read_text())
    for handler in handlers:
        assert re.search(rf"function {handler}\s*\(", source), handler


def test_public_webhook_service_exposes_no_send_routes():
    paths = {p for _, p in routes_of("webhooks")}
    assert any(p.startswith("/webhooks/") for p in paths)
    assert not any(p.startswith("/v1/") or p.startswith("/workers") for p in paths)
    worker = {p for _, p in routes_of("workers")}
    assert any(p.startswith("/workers/") for p in worker)
    assert not any(p.startswith("/v1/") or p.startswith("/webhooks") for p in worker)


def test_send_payload_matches_cloud_api_shape():
    spec = parse_template(TEMPLATE_SHAADI)
    comps = render_components(spec, {"header.1": "A", "body.1": "A", "body.2": "B", "button.0.1": "x"})
    for comp in comps:
        assert comp["type"] in {"header", "body", "button"}
        for param in comp["parameters"]:
            assert param["type"] in {"text", "image", "video", "document", "coupon_code"}
    assert all("sub_type" in c and "index" in c for c in comps if c["type"] == "button")


def test_documented_notification_samples_parse(ctx):
    """Samples follow the structure of Meta's published webhook examples."""
    from services.whatsapp.webhook import process_inbox

    for name in ("wa_status_notification.json", "wa_inbound_stop.json"):
        payload = json.loads((FIXTURES / name).read_text())
        assert payload["object"] == "whatsapp_business_account"
        ctx.store.create("webhook_inbox", name, {"payload": payload, "status": "pending"})
        counts = process_inbox(ctx.store, ctx.brands, ctx.jobs, name, ["STOP"])
        assert counts and "unknown_number" not in counts
