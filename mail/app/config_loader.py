"""Configuration loading and validation for all brands."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.utilities import is_valid_email, token_filename_for

BASE_DIR = Path(__file__).resolve().parents[1]
# BRANDS_DIR=brands (old email workbook) or brands_master (Automation Control Center).
BRANDS_DIR = BASE_DIR / os.getenv("BRANDS_DIR", "brands")
STATE_DIR = BASE_DIR / "state"
LOGS_DIR = BASE_DIR / "logs"
SCRIPTS_DIR = BASE_DIR / "scripts"
REPORTS_DIR = BASE_DIR / "reports"

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.metadata",
]
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

LEAD_HEADERS = [
    "Person Name",
    "Email",
    "Details (Optional)",
    "Subject (Auto)",
    "Generated Email (Auto)",
    "Send Status",
    "Sent At",
    "Error",
    "Sent From",
    "Approval",
    "Gmail Message ID",
    "Follow-up Status",
]

LEGACY_LEAD_HEADERS = [
    "Person Name",
    "Email",
    "Details (Optional)",
    "Subject (Auto)",
    "Generated Email (Auto)",
    "Send Status",
    "Sent At",
    "Error",
    "Approval",
]

MAILBOX_HEADERS = [
    "Mailbox",
    "Enabled?",
    "Warm-up Stage",
    "Daily Limit",
    "Hourly Limit",
    "Sent Today",
    "Sent This Hour",
    "Clean Days",
    "Last Sent At",
    "Next Eligible Time",
    "Paused?",
    "Pause Reason",
    "Last Result",
]

SEND_LOG_HEADERS = [
    "Date and Time",
    "Gmail Sender",
    "Lead Email",
    "Subject",
    "Gmail Message ID",
    "Sending Result",
    "Error Reason",
    "Daily Limit",
    "Warm-up Stage",
]

STATUS_VALUES = [
    "Pending",
    "Generated",
    "Approved",
    "Scheduled",
    "Sent",
    "Skipped",
    "Failed",
    "Replied",
    "Unsubscribed",
    "Bounced",
]

FOLLOW_UP_VALUES = ["Pending", "Replied", "Stopped", "Completed"]
BRAND_ORDER = ["shaadi", "marketing", "staffing", "property", "skyline"]
DEFAULT_SHEET_ID = "18hjldwZeoQ8Y99ngc02OVpoT_4Pe1rM0nNhS2KPxfOI"
LEGACY_LEAD_BRANDS: set[str] = set()


@dataclass(frozen=True)
class RuntimeConfig:
    base_dir: Path
    openai_api_key: str
    openai_model: str
    google_oauth_client_file: Path
    google_sheets_token_file: Path
    timezone: str
    cross_brand_duplicate_days: int
    max_drafts_per_brand_per_run: int


@dataclass(frozen=True)
class BrandConfig:
    brand_id: str
    brand_name: str
    enabled: bool
    gmail_accounts: list[str]
    sheet_id: str
    control_tab: str
    lead_tab: str
    send_log_tab: str
    suppression_tab: str
    token_directory: Path
    log_directory: Path
    mandatory_cc: str
    hourly_limit: int
    daily_limit: int
    minimum_gap_minutes: int
    sending_start_time: str
    sending_end_time: str
    brand_facts: str
    website: str
    phone: str
    legacy_lead_tab: str
    initial_emergency_stop: bool

    def token_path_for(self, mailbox: str) -> Path:
        return self.token_directory / token_filename_for(mailbox)


def load_runtime_config() -> RuntimeConfig:
    load_dotenv(BASE_DIR / ".env")
    oauth_file = Path(os.getenv("GOOGLE_OAUTH_CLIENT_FILE", "credentials.json"))
    if not oauth_file.is_absolute():
        oauth_file = BASE_DIR / oauth_file
    sheets_token_file = Path(os.getenv("GOOGLE_SHEETS_TOKEN_FILE", "tokens/google_sheets_token.json"))
    if not sheets_token_file.is_absolute():
        sheets_token_file = BASE_DIR / sheets_token_file
    return RuntimeConfig(
        base_dir=BASE_DIR,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini").strip(),
        google_oauth_client_file=oauth_file,
        google_sheets_token_file=sheets_token_file,
        timezone=os.getenv("TIMEZONE", "Asia/Kolkata").strip(),
        cross_brand_duplicate_days=int(os.getenv("CROSS_BRAND_DUPLICATE_DAYS", "0")),
        max_drafts_per_brand_per_run=int(os.getenv("MAX_DRAFTS_PER_BRAND_PER_RUN", "20")),
    )


def _path_from_config(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def load_brand_config(brand_id: str) -> BrandConfig:
    path = BRANDS_DIR / brand_id / "config.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return BrandConfig(
        brand_id=str(data["brand_id"]),
        brand_name=str(data["brand_name"]),
        enabled=bool(data.get("enabled", True)),
        gmail_accounts=[str(item).strip().lower() for item in data.get("gmail_accounts", [])],
        sheet_id=str(data.get("sheet_id") or DEFAULT_SHEET_ID),
        control_tab=str(data["control_tab"]),
        lead_tab=str(data["lead_tab"]),
        send_log_tab=str(data["send_log_tab"]),
        suppression_tab=str(data["suppression_tab"]),
        token_directory=_path_from_config(str(data["token_directory"])),
        log_directory=_path_from_config(str(data["log_directory"])),
        mandatory_cc=str(data.get("mandatory_cc", "")).strip(),
        hourly_limit=int(data.get("hourly_limit", 1)),
        daily_limit=int(data.get("daily_limit", 3)),
        minimum_gap_minutes=int(data.get("minimum_gap_minutes", 25)),
        sending_start_time=str(data.get("sending_start_time", "10:00")),
        sending_end_time=str(data.get("sending_end_time", "18:00")),
        brand_facts=str(data.get("brand_facts", "")),
        website=str(data.get("website", "")),
        phone=str(data.get("phone", "")),
        legacy_lead_tab=str(data.get("legacy_lead_tab", "")),
        initial_emergency_stop=bool(data.get("initial_emergency_stop", True)),
    )


def load_all_brand_configs(enabled_only: bool = False) -> list[BrandConfig]:
    brands = [load_brand_config(brand_id) for brand_id in BRAND_ORDER]
    return [brand for brand in brands if brand.enabled] if enabled_only else brands


def uses_legacy_lead_format(brand: BrandConfig) -> bool:
    return brand.brand_id in LEGACY_LEAD_BRANDS


def lead_range_end_column(brand: BrandConfig) -> str:
    return "I" if uses_legacy_lead_format(brand) else "L"


def lead_row_width(brand: BrandConfig) -> int:
    return len(LEGACY_LEAD_HEADERS) if uses_legacy_lead_format(brand) else len(LEAD_HEADERS)


def approval_index(brand: BrandConfig) -> int:
    return 8 if uses_legacy_lead_format(brand) else 9


def approval_column(brand: BrandConfig) -> str:
    return "I" if uses_legacy_lead_format(brand) else "J"


def ensure_runtime_directories(brands: list[BrandConfig] | None = None) -> None:
    for path in (STATE_DIR, LOGS_DIR, REPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)
    for brand in brands or []:
        brand.token_directory.mkdir(parents=True, exist_ok=True)
        brand.log_directory.mkdir(parents=True, exist_ok=True)


def validate_brand_config(brand: BrandConfig) -> list[str]:
    errors: list[str] = []
    if brand.brand_id not in BRAND_ORDER:
        errors.append(f"{brand.brand_id}: unknown brand id")
    if not brand.gmail_accounts:
        errors.append(f"{brand.brand_id}: no gmail accounts configured")
    for account in brand.gmail_accounts:
        if account.startswith("replace_with_real_"):
            errors.append(f"{brand.brand_id}: placeholder Gmail account remains: {account}")
        elif not is_valid_email(account):
            errors.append(f"{brand.brand_id}: invalid Gmail account: {account}")
    tabs = [brand.control_tab, brand.lead_tab, brand.send_log_tab, brand.suppression_tab]
    if len(set(tabs)) != len(tabs):
        errors.append(f"{brand.brand_id}: duplicate tab names inside brand config")
    if brand.hourly_limit < 1 or brand.daily_limit < 1:
        errors.append(f"{brand.brand_id}: limits must be positive")
    if brand.minimum_gap_minutes < 0:
        errors.append(f"{brand.brand_id}: minimum gap cannot be negative")
    return errors


def safe_config_summary(brand: BrandConfig) -> dict[str, Any]:
    return {
        "brand_id": brand.brand_id,
        "brand_name": brand.brand_name,
        "enabled": brand.enabled,
        "gmail_accounts": brand.gmail_accounts,
        "tabs": {
            "control": brand.control_tab,
            "lead": brand.lead_tab,
            "send_log": brand.send_log_tab,
            "suppression": brand.suppression_tab,
        },
        "token_directory": str(brand.token_directory.relative_to(BASE_DIR)),
        "mandatory_cc": bool(brand.mandatory_cc),
        "hourly_limit": brand.hourly_limit,
        "daily_limit": brand.daily_limit,
        "minimum_gap_minutes": brand.minimum_gap_minutes,
    }
