"""Gmail OAuth credential loading.

Two backends, chosen automatically:
- Local/VM: one token file per mailbox under brands/<brand>/tokens/.
- Cloud Run: a single JSON bundle (mailbox -> authorized-user info) mounted
  from Secret Manager at the path in GMAIL_TOKEN_BUNDLE_FILE.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials

from app.config_loader import BrandConfig, GMAIL_SCOPES

_bundle_cache: dict[str, dict] | None = None


def _bundle_path() -> Path | None:
    raw = os.getenv("GMAIL_TOKEN_BUNDLE_FILE", "").strip()
    return Path(raw) if raw else None


def _bundle() -> dict[str, dict] | None:
    global _bundle_cache
    path = _bundle_path()
    if not path:
        return None
    if _bundle_cache is None:
        _bundle_cache = json.loads(path.read_text(encoding="utf-8"))
    return _bundle_cache


def has_credentials(brand: BrandConfig, mailbox: str) -> bool:
    bundle = _bundle()
    if bundle is not None:
        return mailbox.strip().lower() in bundle
    return brand.token_path_for(mailbox).exists()


def load_credentials(brand: BrandConfig, mailbox: str) -> Credentials:
    bundle = _bundle()
    if bundle is not None:
        info = bundle.get(mailbox.strip().lower())
        if info is None:
            raise FileNotFoundError(f"OAuth token missing from bundle for {mailbox}")
        return Credentials.from_authorized_user_info(info, GMAIL_SCOPES)
    token_path = brand.token_path_for(mailbox)
    if not token_path.exists():
        raise FileNotFoundError(f"OAuth token missing for {mailbox}: {token_path}")
    return Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)


def persist_refresh(brand: BrandConfig, mailbox: str, credentials: Credentials) -> None:
    """Save a refreshed access token. No-op on the read-only Secret Manager
    mount; the refresh token is reused to refresh again next execution."""
    if _bundle() is not None:
        return
    brand.token_path_for(mailbox).write_text(credentials.to_json(), encoding="utf-8")
