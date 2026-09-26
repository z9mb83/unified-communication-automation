"""The existing email application must be byte-identical to the archive's
Cloud Run implementation (the working production baseline)."""

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
MANIFEST = json.loads((REPO / "tests/fixtures/email_baseline_manifest.json").read_text())


def test_all_original_email_files_unchanged():
    changed = []
    for rel, digest in MANIFEST["files"].items():
        path = REPO / "services/email" / rel
        assert path.exists(), f"missing preserved file {rel}"
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            changed.append(rel)
    assert changed == [], f"existing email files were modified: {changed}"


def test_no_secret_bundle_in_repo():
    assert not (REPO / "services/email/gmail_tokens_bundle.json").exists()
    assert not list((REPO / "services/email/brands").rglob("tokens/*.json"))
