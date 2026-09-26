"""Combine per-mailbox Gmail token files from the local/VM project into one
JSON bundle, for uploading to Secret Manager as the `gmail-oauth-bundle`
secret that Cloud Run mounts at GMAIL_TOKEN_BUNDLE_FILE.

Usage (run locally, against the ORIGINAL project that still has tokens/):
    python scripts/build_gmail_bundle.py --source "../unified_email_automation" --out gmail_tokens_bundle.json

The output file contains live OAuth refresh tokens. Upload it with:
    gcloud secrets create gmail-oauth-bundle --data-file=gmail_tokens_bundle.json
    (or 'gcloud secrets versions add gmail-oauth-bundle --data-file=...' on updates)
then delete the local file. Never commit it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True, help="Path to the project root that contains brands/<brand>/tokens/*.json")
    parser.add_argument("--out", default="gmail_tokens_bundle.json", help="Output bundle file path")
    args = parser.parse_args()

    source = Path(args.source).resolve()
    brands_dir = source / "brands"
    if not brands_dir.is_dir():
        raise SystemExit(f"No brands/ directory found under {source}")

    bundle: dict[str, dict] = {}
    for token_path in sorted(brands_dir.glob("*/tokens/*.json")):
        mailbox = token_path.stem.replace("__at__", "@")
        info = json.loads(token_path.read_text(encoding="utf-8"))
        if not info.get("refresh_token"):
            print(f"skip (no refresh_token): {mailbox}")
            continue
        bundle[mailbox] = info
        print(f"included: {mailbox}")

    out_path = Path(args.out).resolve()
    out_path.write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nWrote {len(bundle)} mailbox token(s) to {out_path}")
    print("This file contains live secrets. Upload it to Secret Manager, then delete it.")


if __name__ == "__main__":
    main()
