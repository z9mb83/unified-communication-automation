"""Validate SMS DLT configuration and render every registered template.

    python -m scripts.verify_sms
    python -m scripts.verify_sms --sample BRAND TEMPLATE_ID "Asha" "12 Oct 11:00"

No network calls are made. A real provider adapter must be added (see
docs/SMS_DLT_SETUP.md) before any live SMS can be sent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", nargs="+", metavar="ARG")
    args = parser.parse_args()
    from services.sms.dlt_validator import find_template, render, validate_brand_dlt, variable_count
    from services.sms.gateway_interface import PROVIDERS, get_gateway
    from shared.brand_registry import load_brand_registry
    from shared.config import load_channels, load_settings

    settings = load_settings()
    registry = load_brand_registry(settings)
    channels = load_channels(settings)
    get_gateway("mock", None)  # registers built-in providers
    report: dict[str, object] = {
        "providers_available": sorted(PROVIDERS),
        "live_send_enabled": channels.sms.live_send_enabled,
        "brands": {},
    }
    ok = True
    for brand_id, brand in registry.brands.items():
        if not brand.sms.enabled:
            report["brands"][brand_id] = "disabled"  # type: ignore[index]
            continue
        problems = validate_brand_dlt(brand.sms)
        ok = ok and not problems
        report["brands"][brand_id] = {  # type: ignore[index]
            "provider": brand.sms.provider,
            "problems": problems,
            "templates": [{"id": t.template_id, "vars": variable_count(t)} for t in brand.sms.templates],
        }
    if args.sample:
        brand_id, template_id, *values = args.sample
        template = find_template(registry.get(brand_id).sms, template_id)
        rendered = render(template, values, channels.sms.max_variable_length)
        report["sample"] = {"text": rendered.text, "encoding": rendered.encoding, "segments": rendered.segments}
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
