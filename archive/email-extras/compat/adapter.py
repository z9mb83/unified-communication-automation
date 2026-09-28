"""Compatibility adapter around the existing (unchanged) email automation.

The existing Cloud Run email application in ``services/email`` is the source of
truth. This adapter never re-implements sending. It:

* loads the existing modules (``app.*`` and ``main.py``) from their directory;
* runs the existing :class:`BrandRunner` with two narrowly-overridden lookups so
  that a run only *drafts* and *sends* rows whose contact ID the operator
  selected in Sheets. Everything else — Approval = Yes, sendable status,
  suppression tab, brand/cross-brand duplicates, sending hours, mailbox
  rotation, warm-up/daily/hourly limits, minimum gap, CC, OpenAI prompt,
  signature, Sheet/Send Log updates, Firestore run lock — is the existing code;
* triggers the existing scheduled Cloud Run job for "Run Existing Email
  Automation" instead of running a duplicate implementation.

Rows are matched by a contact ID derived from the recipient email, not by row
number, so re-sorting the sheet between selection and dispatch cannot redirect
a send to a different person.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from shared.exceptions import ConfigurationError
from shared.sheet_registry import derived_contact_id, normalize_email

_LOAD_LOCK = threading.Lock()

# BrandRunResult.skipped_reason prefixes from services/email/app/brand_runner.py
DEFER_REASONS = ("Brand send gap active", "Outside sending hours", "No eligible mailbox")
HOLD_REASONS = ("Emergency stop active", "brand disabled")
TERMINAL_SKIP_REASONS = {
    "Recipient suppressed": "recipient_suppressed",
    "Brand duplicate recipient": "duplicate_recipient",
    "Cross-brand duplicate recipient": "cross_brand_duplicate",
    "Invalid email address": "invalid_email",
    "Approved row has blank subject or body": "blank_subject_or_body",
}


@dataclass
class TargetedOutcome:
    outcome: str  # sent | deferred | held | skipped | failed | not_found | lock_busy
    reason: str = ""
    code: str = ""
    row_number: int | None = None
    errors: list[str] = field(default_factory=list)
    dry_run_notes: list[str] = field(default_factory=list)


class LegacyEmailApp:
    """Loads the existing email modules exactly as they ship in services/email."""

    def __init__(self, email_dir: Path) -> None:
        self.email_dir = email_dir.resolve()
        if not (self.email_dir / "app" / "brand_runner.py").exists():
            raise ConfigurationError(f"existing email application not found at {self.email_dir}")
        with _LOAD_LOCK:
            path = str(self.email_dir)
            if path not in sys.path:
                sys.path.insert(0, path)
            self.brand_runner: Any = importlib.import_module("app.brand_runner")
            self.config_loader: Any = importlib.import_module("app.config_loader")
            self.global_state: Any = importlib.import_module("app.global_state")
            self.utilities: Any = importlib.import_module("app.utilities")
            loaded = sys.modules.get("legacy_email_main")
            if loaded is None:
                spec = importlib.util.spec_from_file_location("legacy_email_main", self.email_dir / "main.py")
                if spec is None or spec.loader is None:
                    raise ConfigurationError("cannot load existing email main.py")
                loaded = importlib.util.module_from_spec(spec)
                sys.modules["legacy_email_main"] = loaded
                spec.loader.exec_module(loaded)
            self.main: ModuleType = loaded
        self.TargetedBrandRunner = _make_targeted_runner(self.brand_runner.BrandRunner, self.utilities)

    def contact_id_for_row(self, brand_id: str, row: list[Any]) -> str | None:
        email = normalize_email(row[1] if len(row) > 1 else "")
        return derived_contact_id(brand_id, "email", email) if email else None

    def send_selected_contact(self, brand_id: str, contact_id: str, *, dry_run: bool = False) -> TargetedOutcome:
        """Run one existing-pipeline pass restricted to ``contact_id``."""
        with self.main._run_lock() as acquired:
            if not acquired:
                return TargetedOutcome("lock_busy", "another email run is active", code="email_run_lock_busy")
            runtime = self.config_loader.load_runtime_config()
            brand = self.config_loader.load_brand_config(brand_id)
            self.config_loader.ensure_runtime_directories([brand])
            state = self.global_state.build_global_state()
            runner = self.TargetedBrandRunner(
                runtime,
                brand,
                state,
                targets={contact_id},
                contact_id_fn=lambda row: self.contact_id_for_row(brand_id, row),
            )
            result = runner.process(dry_run=dry_run, read_sheets=True)
        return interpret(result, runner)

    # -- existing scheduled job ---------------------------------------------------------

    @staticmethod
    def trigger_existing_job(project: str, region: str, job_name: str, session: Any | None = None) -> dict[str, Any]:
        """Execute the existing Cloud Run job (e.g. ``email-sender``) exactly as Cloud
        Scheduler does. No arguments are overridden."""
        if not (project and region and job_name):
            raise ConfigurationError(
                "UCA_GCP_PROJECT, UCA_GCP_REGION and UCA_EMAIL_RUN_JOB_NAME must be set",
                code="email_job_not_configured",
            )
        session = session or _authorized_session()
        url = f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job_name}:run"
        response = session.post(url, json={}, timeout=30)
        if response.status_code >= 400:
            raise ConfigurationError(
                f"Cloud Run job run failed: HTTP {response.status_code}", code="email_job_trigger_failed"
            )
        operation = response.json()
        return {"operation": operation.get("name"), "job": job_name}

    @staticmethod
    def recent_executions(
        project: str, region: str, job_name: str, session: Any | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        if not (project and region and job_name):
            return []
        session = session or _authorized_session()
        url = f"https://run.googleapis.com/v2/projects/{project}/locations/{region}/jobs/{job_name}/executions"
        response = session.get(url, params={"pageSize": limit}, timeout=30)
        if response.status_code >= 400:
            return [{"error": f"HTTP {response.status_code}"}]
        out = []
        for item in response.json().get("executions", [])[:limit]:
            out.append(
                {
                    "name": str(item.get("name", "")).rsplit("/", 1)[-1],
                    "created": item.get("createTime"),
                    "completed": item.get("completionTime"),
                    "succeeded": item.get("succeededCount", 0),
                    "failed": item.get("failedCount", 0),
                    "running": item.get("runningCount", 0),
                }
            )
        return out


def _authorized_session() -> Any:
    import google.auth
    from google.auth.transport.requests import AuthorizedSession

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    return AuthorizedSession(credentials)


def _make_targeted_runner(base: type, utilities: Any) -> type:
    class TargetedBrandRunner(base):  # type: ignore[misc, valid-type]
        """Existing BrandRunner; only the two row lookups are restricted to targets."""

        def __init__(self, runtime: Any, brand: Any, state: Any, *, targets: set[str], contact_id_fn: Any) -> None:
            super().__init__(runtime, brand, state)
            self.targets = targets
            self.contact_id_fn = contact_id_fn
            self.found_rows: dict[str, tuple[int, str]] = {}
            self.selected_row: int | None = None

        def _mask(self, leads: list[list[Any]]) -> list[list[Any]]:
            masked: list[list[Any]] = []
            for offset, raw in enumerate(leads, start=3):
                cid = self.contact_id_fn(raw)
                if cid in self.targets:
                    status = str(utilities.pad(list(raw), 12)[5] or "").strip()
                    self.found_rows[cid] = (offset, status)
                    masked.append(raw)
                else:
                    masked.append([])  # keeps row numbering identical
            return masked

        def _generate_drafts(self, sheets: Any, leads: list[list[Any]], dry_run: bool, result: Any) -> int:
            return int(super()._generate_drafts(sheets, self._mask(leads), dry_run, result))

        def _first_approved_row(self, leads: list[list[Any]]) -> Any:
            found = super()._first_approved_row(self._mask(leads))
            if found is not None:
                self.selected_row = found[0]
            return found

    return TargetedBrandRunner


def interpret(result: Any, runner: Any) -> TargetedOutcome:
    row = runner.selected_row
    if result.sent:
        return TargetedOutcome("sent", "sent by existing pipeline", code="sent", row_number=row)
    reason = str(result.skipped_reason or "")
    notes = list(getattr(result, "dry_run_notes", []))
    if result.errors:
        return TargetedOutcome(
            "failed",
            "; ".join(result.errors)[:300],
            code="email_send_failed",
            row_number=row,
            errors=list(result.errors),
            dry_run_notes=notes,
        )
    if any(reason.startswith(r) for r in HOLD_REASONS):
        return TargetedOutcome(
            "held", reason, code="email_emergency_stop" if "Emergency" in reason else "brand_disabled"
        )
    if any(reason.startswith(r) for r in DEFER_REASONS):
        return TargetedOutcome("deferred", reason, code="email_paced", row_number=row, dry_run_notes=notes)
    if reason.startswith("Missing required Sheet tab"):
        return TargetedOutcome("failed", reason, code="email_sheet_misconfigured")
    for prefix, code in TERMINAL_SKIP_REASONS.items():
        if reason.startswith(prefix):
            return TargetedOutcome("skipped", reason, code=code, row_number=row)
    if reason.startswith("No approved lead is ready"):
        if not runner.found_rows:
            return TargetedOutcome(
                "not_found", "contact is no longer present in the lead tab", code="contact_not_found"
            )
        _, status = next(iter(runner.found_rows.values()))
        if status == "Sent":
            return TargetedOutcome("skipped", "row is already marked Sent", code="already_sent")
        return TargetedOutcome(
            "skipped", "row is not approved (Approval must be Yes with a sendable status)", code="not_approved"
        )
    if runner.selected_row is not None and notes:
        return TargetedOutcome("deferred", "dry run", code="dry_run", row_number=row, dry_run_notes=notes)
    return TargetedOutcome("skipped", reason or "no action", code="no_action", dry_run_notes=notes)
