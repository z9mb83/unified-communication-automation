"""Exact (spreadsheet ID, tab name) -> brand mapping.

Rules (enforced server-side; the Apps Script UI only mirrors them):

* A tab resolves to a brand only through an exact entry in ``sheets.yaml``.
  Nothing is inferred from tab names or cell contents.
* A brand-specific tab has ``brand_id``. A shared/generic tab (e.g. a single
  "WhatsApp Contacts" tab) instead has ``brand_column`` and every submitted row
  must carry a Brand ID that exactly matches the requested brand.
* Existing email tabs keep their existing column layout (A:L, data from row 3).
"""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.brand_registry import CHANNELS, KNOWN_BRAND_IDS
from shared.config import Settings, config_file, load_settings, load_yaml
from shared.exceptions import BrandResolutionError, ConfigurationError, ValidationError

COLUMN_RE = re.compile(r"^[A-Z]{1,3}$")
EMAIL_RE = re.compile(r"^[^\s@,]+@[^\s@,]+\.[^\s@,]+$")


def column_index(letter: str) -> int:
    """'A' -> 0, 'L' -> 11, 'AA' -> 26."""
    value = 0
    for char in letter:
        value = value * 26 + (ord(char) - 64)
    return value - 1


class TabBinding(BaseModel):
    tab: str
    brand_id: str | None = None
    brand_column: str | None = None
    channels: list[str]
    header_row: int = Field(default=1, ge=1)
    first_data_row: int = Field(default=2, ge=2)
    columns: dict[str, str] = Field(default_factory=dict)
    contact_id_column: str | None = None
    notes: str = ""

    @field_validator("channels")
    @classmethod
    def _channels(cls, value: list[str]) -> list[str]:
        bad = [c for c in value if c not in CHANNELS]
        if bad or not value:
            raise ValueError(f"channels must be a non-empty subset of {CHANNELS}")
        return value

    @field_validator("columns")
    @classmethod
    def _columns(cls, value: dict[str, str]) -> dict[str, str]:
        for key, letter in value.items():
            if not COLUMN_RE.match(letter):
                raise ValueError(f"column {key} must be a column letter, got {letter!r}")
        return value

    @model_validator(mode="after")
    def _brand_xor(self) -> TabBinding:
        if bool(self.brand_id) == bool(self.brand_column):
            raise ValueError(f"tab {self.tab!r}: set exactly one of brand_id or brand_column")
        if self.brand_id and self.brand_id not in KNOWN_BRAND_IDS:
            raise ValueError(f"tab {self.tab!r}: unknown brand {self.brand_id!r}")
        if self.first_data_row <= self.header_row:
            raise ValueError(f"tab {self.tab!r}: first_data_row must be after header_row")
        if "email" in self.channels and "email" not in self.columns:
            raise ValueError(f"tab {self.tab!r}: email channel needs an 'email' column")
        if ({"whatsapp", "sms"} & set(self.channels)) and "phone" not in self.columns:
            raise ValueError(f"tab {self.tab!r}: whatsapp/sms channels need a 'phone' column")
        return self

    @property
    def is_generic(self) -> bool:
        return self.brand_column is not None


class SpreadsheetBinding(BaseModel):
    spreadsheet_id: str
    tabs: list[TabBinding]


class SheetRegistry:
    def __init__(self, spreadsheets: list[SpreadsheetBinding]) -> None:
        self._index: dict[tuple[str, str], TabBinding] = {}
        for sheet in spreadsheets:
            for tab in sheet.tabs:
                key = (sheet.spreadsheet_id, tab.tab)
                if key in self._index:
                    raise ConfigurationError(f"Duplicate sheet mapping for {key}")
                self._index[key] = tab

    @classmethod
    def from_dict(cls, data: dict) -> SheetRegistry:
        try:
            sheets = [SpreadsheetBinding.model_validate(item) for item in data.get("spreadsheets") or []]
        except Exception as error:
            raise ConfigurationError(f"sheets.yaml: {error}") from error
        return cls(sheets)

    def bindings(self) -> dict[tuple[str, str], TabBinding]:
        return dict(self._index)

    def resolve(self, spreadsheet_id: str, tab: str) -> TabBinding:
        binding = self._index.get((spreadsheet_id, tab))
        if binding is None:
            raise BrandResolutionError(
                f"Tab {tab!r} in spreadsheet {spreadsheet_id} is not mapped to a brand. "
                "Add an exact entry to sheets.yaml; brands are never guessed."
            )
        return binding

    def resolve_brand(self, spreadsheet_id: str, tab: str, requested_brand: str, channel: str) -> TabBinding:
        """Validate that ``requested_brand`` may use ``channel`` from this tab."""
        binding = self.resolve(spreadsheet_id, tab)
        if channel not in binding.channels:
            raise BrandResolutionError(f"Tab {tab!r} is not enabled for channel {channel}")
        if binding.brand_id is not None and binding.brand_id != requested_brand:
            raise BrandResolutionError(
                f"Tab {tab!r} belongs to brand {binding.brand_id!r}, not {requested_brand!r}",
                code="brand_mismatch",
            )
        if binding.brand_id is None and requested_brand not in KNOWN_BRAND_IDS:
            raise BrandResolutionError(f"Unknown brand {requested_brand!r}")
        return binding


def normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def normalize_phone(value: str, default_country_code: str) -> str:
    """Return E.164 digits without '+', or raise ValidationError.

    Accepts '+91 98765 43210', '098765 43210', '9876543210' (default country)."""
    raw = str(value or "").strip()
    if not raw:
        raise ValidationError("phone number is blank", code="invalid_phone")
    has_plus = raw.startswith("+") or raw.startswith("00")
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("00"):
        digits = digits[2:]
    if not has_plus:
        digits = digits.lstrip("0")
        if len(digits) <= 10:
            digits = default_country_code + digits
    if not 8 <= len(digits) <= 15:
        raise ValidationError(f"phone number {value!r} is not a valid international number", code="invalid_phone")
    return digits


def derived_contact_id(brand_id: str, kind: str, normalized_address: str) -> str:
    """Stable contact ID that does not depend on row position (safe across sorting)."""
    digest = hashlib.sha256(f"{brand_id}|{kind}|{normalized_address}".encode()).hexdigest()
    return f"c_{digest[:24]}"


@lru_cache(maxsize=1)
def _load(path: str) -> SheetRegistry:
    return SheetRegistry.from_dict(load_yaml(Path(path)))


def load_sheet_registry(settings: Settings | None = None) -> SheetRegistry:
    return _load(str(config_file("sheets", settings or load_settings())))


def reset_cache() -> None:
    _load.cache_clear()
