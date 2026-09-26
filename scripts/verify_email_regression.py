"""Prove the migrated email application is byte-identical to the original and
that its behaviour is unchanged (mocked Gmail/Sheets/OpenAI; nothing is sent).

    python -m scripts.verify_email_regression
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EMAIL_DIR = REPO / "services" / "email"
MANIFEST = REPO / "tests" / "fixtures" / "email_baseline_manifest.json"


def check_manifest() -> list[str]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = []
    for rel, digest in manifest["files"].items():
        path = EMAIL_DIR / rel
        if not path.exists():
            problems.append(f"missing: {rel}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append(f"modified: {rel}")
    return problems


def main() -> int:
    problems = check_manifest()
    if problems:
        print("Existing email application differs from the original archive:")
        print("\n".join(f"  - {p}" for p in problems))
        return 1
    print(f"OK: {len(json.loads(MANIFEST.read_text())['files'])} original email files are byte-identical.")
    targets = [
        t for t in ("tests/unit/email", "tests/integration/test_email_adapter_integration.py") if (REPO / t).exists()
    ]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *targets], cwd=REPO)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
