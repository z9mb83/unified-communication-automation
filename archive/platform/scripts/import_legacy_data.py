"""Import legacy data into the new stores. Dry-run by default; nothing is sent.

Sub-commands:

  send-state   Copy the old VM's state/global_send_state.json cross-brand send
               history into the existing Firestore ``successful_sends`` collection
               used by the Cloud Run email job (idempotent document IDs, so
               re-running never duplicates).

  consent      Import explicit opt-ins from a CSV with columns
               brand_id,channel,address,consented_at,evidence
               into the brand/channel consent registry. Rows without a date or
               evidence are rejected; existing opt-outs are never overturned.

Examples:
  python -m scripts.import_legacy_data send-state --file state/global_send_state.json
  python -m scripts.import_legacy_data consent --file consent.csv --apply --actor you@example.com
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def send_state_records(path: Path) -> list[tuple[str, dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for item in data.get("successful_sends", []):
        doc_id = (
            "legacy-"
            + hashlib.sha256(
                f"{item.get('brand')}|{item.get('recipient')}|{item.get('sent_at')}|{item.get('gmail_message_id')}".encode()
            ).hexdigest()[:32]
        )
        out.append(
            (
                doc_id,
                {
                    "recipient": str(item.get("recipient", "")).strip().lower(),
                    "brand": item.get("brand"),
                    "sender": str(item.get("sender", "")).strip().lower(),
                    "sent_at": item.get("sent_at"),
                    "gmail_message_id": item.get("gmail_message_id"),
                    "result": "Sent",
                    "imported_from": "vm_global_send_state",
                },
            )
        )
    return out


def import_send_state(path: Path, apply: bool, client: Any = None) -> dict[str, int]:
    records = send_state_records(path)
    if not apply:
        return {"would_import": len(records)}
    from google.api_core.exceptions import AlreadyExists
    from google.cloud import firestore

    db = client or firestore.Client()
    created = existing = 0
    for doc_id, record in records:
        try:
            db.collection("successful_sends").document(doc_id).create(record)
            created += 1
        except AlreadyExists:
            existing += 1
    return {"created": created, "already_present": existing}


def import_consent(path: Path, apply: bool, actor: str, store: Any = None) -> dict[str, Any]:
    from shared.consent import ConsentRegistry
    from shared.exceptions import AutomationError
    from shared.sheet_registry import normalize_email, normalize_phone

    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    registry = ConsentRegistry(store) if store is not None else None
    if apply and registry is None:
        from shared.store import get_store

        registry = ConsentRegistry(get_store())
    report: dict[str, Any] = {"rows": len(rows), "valid": 0, "recorded": 0, "blocked_by_opt_out": 0, "rejected": []}
    for number, row in enumerate(rows, start=2):
        try:
            channel = row["channel"].strip().lower()
            raw = row["address"]
            address = normalize_email(raw) if channel == "email" else normalize_phone(raw, "91")
            if not row.get("consented_at", "").strip() or not row.get("evidence", "").strip():
                raise ValueError("consented_at and evidence are required")
            report["valid"] += 1
            if apply and registry is not None:
                changed, _ = registry.record_opt_in(
                    row["brand_id"].strip(),
                    channel,
                    address,
                    source="legacy_import",
                    evidence=row["evidence"],
                    recorded_by=actor,
                    consented_at=row["consented_at"],
                )
                report["recorded" if changed else "blocked_by_opt_out"] += 1
        except (AutomationError, ValueError, KeyError) as error:
            report["rejected"].append({"line": number, "reason": str(error)[:120]})
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    s1 = sub.add_parser("send-state")
    s1.add_argument("--file", type=Path, required=True)
    s1.add_argument("--apply", action="store_true")
    s2 = sub.add_parser("consent")
    s2.add_argument("--file", type=Path, required=True)
    s2.add_argument("--apply", action="store_true")
    s2.add_argument("--actor", default="legacy-import")
    args = parser.parse_args()
    if args.command == "send-state":
        print(json.dumps(import_send_state(args.file, args.apply), indent=2))
    else:
        print(json.dumps(import_consent(args.file, args.apply, args.actor), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
