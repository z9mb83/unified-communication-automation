"""Safe daily maintenance for all enabled brands."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

from app import credential_store
from app.config_loader import LOGS_DIR, ensure_runtime_directories, load_all_brand_configs, load_runtime_config
from app.gmail_client import gmail_service
from app.global_state import build_global_state
from app.send_logger import logger_for
from app.utilities import timezone_for


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-tokens", action="store_true", help="Refresh expired Gmail tokens where possible.")
    parser.add_argument("--retention-days", type=int, default=30)
    args = parser.parse_args()

    runtime = load_runtime_config()
    brands = load_all_brand_configs(enabled_only=True)
    ensure_runtime_directories(brands)
    logger = logger_for("unified.maintenance", LOGS_DIR / "unified_maintenance.log")
    now = datetime.now(timezone_for(runtime.timezone))
    logger.info("daily maintenance started refresh_tokens=%s", args.refresh_tokens)

    state = build_global_state()
    if hasattr(state, "path"):
        # Local JSON-file backend only; Firestore has no equivalent file to compact.
        cutoff = now - timedelta(days=max(args.retention_days, 1))
        kept_events = []
        for event in state.data.get("successful_sends", []):
            sent_at = event.get("sent_at")
            try:
                parsed = datetime.fromisoformat(str(sent_at))
            except (TypeError, ValueError):
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone_for(runtime.timezone))
            if parsed >= cutoff:
                kept_events.append(event)
        if len(kept_events) != len(state.data.get("successful_sends", [])):
            state.data["successful_sends"] = kept_events
            from app.utilities import atomic_write_json

            atomic_write_json(state.path, state.data)
            logger.info("pruned old local send-state records")

    for brand in brands:
        present = 0
        missing = []
        for account in brand.gmail_accounts:
            if credential_store.has_credentials(brand, account):
                present += 1
                if args.refresh_tokens:
                    try:
                        gmail_service(brand, account)
                    except Exception as error:
                        logger.warning("token refresh/check failed brand=%s account=%s error=%s", brand.brand_id, account, error)
            else:
                missing.append(account)
        logger.info("brand=%s token_present=%s token_missing=%s", brand.brand_id, present, len(missing))
        print(f"{brand.brand_id}: token_present={present} token_missing={len(missing)}")
    print("Daily maintenance completed. No outreach email was sent and no Sheet rows were cleared.")


if __name__ == "__main__":
    main()
