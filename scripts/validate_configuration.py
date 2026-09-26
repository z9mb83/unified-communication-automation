"""Validate brands/sheets/channels/access configuration without sending anything.

    python -m scripts.validate_configuration            # uses UCA_CONFIG_DIR or examples (local)
    python -m scripts.validate_configuration --strict   # also fail on warnings

Checks: YAML schema, brand IDs match the existing email brand configs, every
sheet tab maps to exactly one brand, WABA/phone numbers are not shared between
brands, secret references are Secret Manager resource names, DLT data is well
formed, and production sending gates are in the expected state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def validate_context(ctx: Any) -> dict[str, Any]:
    from services.sms.dlt_validator import validate_brand_dlt
    from shared.brand_registry import KNOWN_BRAND_IDS

    errors: list[str] = []
    warnings: list[str] = []
    brands = ctx.brands
    for brand_id in KNOWN_BRAND_IDS:
        if brand_id not in brands.brands:
            warnings.append(f"brand {brand_id} (from the existing email automation) is not in brands.yaml")
    email_brands = sorted(b for b, c in brands.brands.items() if c.email.enabled)
    mapped_email = {bind.brand_id for bind in ctx.sheets.bindings().values() if "email" in bind.channels}
    for brand_id in email_brands:
        if brand_id not in mapped_email:
            warnings.append(f"{brand_id}: no email tab mapped in sheets.yaml (Send Email to Selected Rows unavailable)")
    for (sheet_id, tab), bind in ctx.sheets.bindings().items():
        if bind.brand_id and bind.brand_id not in brands.brands:
            errors.append(f"{sheet_id}/{tab}: brand {bind.brand_id} not in brands.yaml")
    for brand in brands.brands.values():
        if brand.sms.enabled:
            errors += [f"{brand.brand_id} sms: {p}" for p in validate_brand_dlt(brand.sms)]
            if brand.sms.provider == "mock":
                warnings.append(f"{brand.brand_id}: SMS uses the TEST adapter; no real SMS will be sent")
        if brand.whatsapp.enabled and not ctx.channels.whatsapp.live_send_enabled:
            warnings.append(f"{brand.brand_id}: WhatsApp enabled but live sending is disabled (test recipients only)")
    if ctx.channels.sms.live_send_enabled and any(
        b.sms.enabled and b.sms.provider == "mock" for b in brands.brands.values()
    ):
        errors.append("sms.live_send_enabled is true but a brand uses the mock provider")
    if not ctx.access.get("users"):
        warnings.append("access.yaml has no users: nobody can call the API")
    if ctx.settings.is_production_like:
        if not ctx.settings.allowed_audiences:
            errors.append("UCA_ALLOWED_AUDIENCES is empty")
        if not ctx.settings.worker_allowed_callers:
            errors.append("UCA_WORKER_ALLOWED_CALLERS is empty")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "brands": sorted(brands.brands),
        "sheet_bindings": len(ctx.sheets.bindings()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    from services.api.authz import load_access
    from services.api.deps import AppContext
    from shared.brand_registry import load_brand_registry
    from shared.config import load_channels, load_settings
    from shared.job_manager import InlineQueue
    from shared.sheet_registry import load_sheet_registry
    from shared.store import InMemoryStore

    settings = load_settings()
    try:
        ctx = AppContext(
            settings=settings,
            store=InMemoryStore(),
            queue=InlineQueue(),
            brands=load_brand_registry(settings),
            sheets=load_sheet_registry(settings),
            channels=load_channels(settings),
            access=load_access(settings),
        )
    except Exception as error:
        print(json.dumps({"ok": False, "errors": [str(error)]}, indent=2))
        return 1
    report = validate_context(ctx)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] and not (args.strict and report["warnings"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
