"""Verify WhatsApp configuration and (optionally) live Meta connectivity.

    python -m scripts.verify_whatsapp                               # config only, no network
    python -m scripts.verify_whatsapp --read BRAND                  # read-only: phone numbers + templates
    python -m scripts.verify_whatsapp --send-test BRAND --to 9198XXXXXXXX \
        --template TEMPLATE_ID --language en --var body.1=Test --i-understand-this-sends

A test send is only allowed to numbers listed in channels.yaml
``whatsapp.test_recipients``. It never goes to customer contacts.
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
    parser.add_argument("--read", metavar="BRAND")
    parser.add_argument("--send-test", metavar="BRAND")
    parser.add_argument("--to")
    parser.add_argument("--template")
    parser.add_argument("--language")
    parser.add_argument("--var", action="append", default=[])
    parser.add_argument("--i-understand-this-sends", action="store_true")
    args = parser.parse_args()

    from services.whatsapp.sender import default_client_factory
    from services.whatsapp.template_renderer import render_components
    from services.whatsapp.template_validator import parse_template
    from shared.brand_registry import load_brand_registry
    from shared.config import load_channels, load_settings

    settings = load_settings()
    registry = load_brand_registry(settings)
    channels = load_channels(settings)
    summary = {
        "graph_api_version": channels.whatsapp.graph_api_version,
        "live_send_enabled": channels.whatsapp.live_send_enabled,
        "test_recipients": len(channels.whatsapp.test_recipients),
        "brands": {
            b: {
                "enabled": c.whatsapp.enabled,
                "waba_id": c.whatsapp.waba_id or None,
                "phone_numbers": len(c.whatsapp.phone_numbers),
            }
            for b, c in registry.brands.items()
        },
        "meta_apps": sorted(registry.meta_apps),
    }
    print(json.dumps(summary, indent=2))
    factory = default_client_factory(channels)

    if args.read:
        brand = registry.require_channel(args.read, "whatsapp")
        client = factory(brand)
        numbers = client.list_phone_numbers(brand.whatsapp.waba_id)
        templates = client.list_templates(brand.whatsapp.waba_id)
        print(
            json.dumps(
                {
                    "phone_numbers": [
                        {
                            "id": n.get("id"),
                            "display": n.get("display_phone_number"),
                            "configured": n.get("id") in brand.whatsapp.phone_number_ids(),
                        }
                        for n in numbers
                    ],
                    "templates": [
                        {
                            "id": t.get("id"),
                            "name": t.get("name"),
                            "language": t.get("language"),
                            "status": t.get("status"),
                        }
                        for t in templates
                    ],
                },
                indent=2,
            )
        )

    if args.send_test:
        if not args.i_understand_this_sends:
            print("Refusing: add --i-understand-this-sends to send one test message.")
            return 2
        to = (args.to or "").lstrip("+")
        if to not in {p.lstrip("+") for p in channels.whatsapp.test_recipients}:
            print("Refusing: --to must be listed in whatsapp.test_recipients.")
            return 2
        brand = registry.require_channel(args.send_test, "whatsapp")
        client = factory(brand)
        raw = next(
            (
                t
                for t in client.list_templates(brand.whatsapp.waba_id)
                if t.get("id") == args.template and t.get("language") == args.language
            ),
            None,
        )
        if raw is None:
            print("Template/language not found in this brand's WABA.")
            return 2
        spec = parse_template(raw)
        values = dict(v.split("=", 1) for v in args.var)
        components = render_components(spec, values)
        result = client.send_template(
            phone_number_id=brand.whatsapp.default_phone_number_id(),
            to=to,
            template_name=spec.name,
            language=spec.language,
            components=components,
            callback_data="verify_whatsapp_test",
        )
        print(json.dumps({"sent": True, "wamid": result["wamid"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
