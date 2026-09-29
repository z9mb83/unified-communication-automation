"""Unified entry point for all brands."""

from __future__ import annotations

import argparse
import os
from contextlib import contextmanager
from typing import Iterator

from app.brand_runner import BrandRunner, BrandRunResult
from app.config_loader import BRAND_ORDER, LOGS_DIR, ensure_runtime_directories, load_all_brand_configs, load_runtime_config
from app.global_state import build_global_state, build_round_robin_state
from app.send_logger import logger_for
from app.utilities import file_lock


@contextmanager
def _run_lock() -> Iterator[bool]:
    if os.getenv("STATE_BACKEND", "local") == "firestore":
        from app.firestore_state import firestore_lock

        with firestore_lock("run_lock") as acquired:
            yield acquired
        return
    with file_lock(LOGS_DIR / "unified_main.lock") as acquired:
        yield acquired


def run_unified(
    selected_brand: str | None = None,
    dry_run: bool = False,
    read_sheets: bool = False,
    generate_only: bool = False,
) -> list[BrandRunResult]:
    runtime = load_runtime_config()
    all_brands = {brand.brand_id: brand for brand in load_all_brand_configs(enabled_only=True)}
    ensure_runtime_directories(list(all_brands.values()))
    logger = logger_for("unified.main", LOGS_DIR / "unified_main.log")
    round_robin = build_round_robin_state()
    state = build_global_state()

    if not dry_run and not generate_only and selected_brand is None:
        # Rows selected in the sheet with "Send mail to selected rows" go first.
        try:
            from datetime import datetime

            from app.send_now import process_queue
            from app.sheet_client import SheetClient
            from app.utilities import timezone_for

            tz = timezone_for(runtime.timezone)
            for line in process_queue(lambda b: BrandRunner(runtime, b, state), list(all_brands.values()),
                                      lambda sid: SheetClient(sid), lambda: datetime.now(tz)):
                print(line)
                logger.info(line)
        except Exception as error:
            logger.exception("send-now queue failed")
            print(f"send-now queue failed: {error}")

    ordered_ids = round_robin.ordered_brand_ids(selected_brand)
    results: list[BrandRunResult] = []
    for brand_id in ordered_ids:
        brand = all_brands.get(brand_id)
        if not brand:
            continue
        try:
            runner = BrandRunner(runtime, brand, state)
            result = runner.process(dry_run=dry_run, read_sheets=read_sheets, generate_only=generate_only)
            results.append(result)
            logger.info("brand_result brand=%s sent=%s generated=%s skipped=%s errors=%s", brand_id, result.sent, result.generated_count, result.skipped_reason, len(result.errors))
        except Exception as error:
            message = f"{brand_id} failed: {error}"
            logger.exception(message)
            results.append(BrandRunResult(brand_id=brand_id, processed=False, errors=[message]))

    if not dry_run and selected_brand is None:
        round_robin.advance()
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brand", choices=BRAND_ORDER)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--read-sheets", action="store_true", help="In dry-run mode, read live Sheets data read-only.")
    parser.add_argument("--generate-only", action="store_true", help="Generate drafts for one brand without any Gmail send request.")
    parser.add_argument("--regenerate-drafts", action="store_true",
                        help="Rewrite queued (unsent) drafts that are still in the old format; sends nothing (app/regenerate.py).")
    parser.add_argument("--limit", type=int, default=250, help="With --regenerate-drafts: max drafts per run.")
    args = parser.parse_args()
    if args.regenerate_drafts:
        _regenerate(args)
        return
    if args.generate_only and args.dry_run:
        parser.error("--generate-only writes drafts, so it cannot be combined with --dry-run")
    if args.generate_only and not args.brand:
        parser.error("--generate-only requires --brand to limit its Sheet updates")

    with _run_lock() as acquired:
        if not acquired:
            print("Another unified main.py run is already active. Exiting.")
            return
        results = run_unified(
            selected_brand=args.brand,
            dry_run=args.dry_run,
            read_sheets=args.read_sheets,
            generate_only=args.generate_only,
        )

    for result in results:
        print(
            f"{result.brand_id}: processed={result.processed} generated={result.generated_count} "
            f"sent={result.sent} skipped={result.skipped_reason or '-'} errors={len(result.errors)}"
        )
        for note in result.dry_run_notes:
            print(f"  dry-run: {note}")
        for error in result.errors:
            print(f"  error: {error}")


def _regenerate(args) -> None:
    from app.regenerate import regenerate
    from app.sheet_client import SheetClient
    from app.utilities import timezone_for

    runtime = load_runtime_config()
    brands = [b for b in load_all_brand_configs(enabled_only=True) if not args.brand or b.brand_id == args.brand]
    tz = timezone_for(runtime.timezone)
    # Hold the sender's run lock so no email is sent with a half-rewritten draft meanwhile.
    with _run_lock() as acquired:
        if not acquired:
            print("The sender is running right now - try again in a minute.")
            return
        print("== Regenerate drafts" + (" (PREVIEW: nothing is changed or sent)" if args.dry_run else " (sends nothing)"))
        for line in regenerate(runtime, brands, lambda sid: SheetClient(sid), args.dry_run, args.limit, tz):
            print(line)


if __name__ == "__main__":
    main()
