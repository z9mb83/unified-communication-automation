"""Brand registry: which brands exist and what each is authorised to use per channel.

The five brand IDs are the ones discovered in the existing email automation
(``services/email/brands/<id>/config.json``). The email channel keeps reading
those JSON files unchanged; ``brands.yaml`` only *adds* WhatsApp/SMS settings and
references to secrets.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from shared.config import REPO_ROOT, Settings, config_file, load_settings, load_yaml
from shared.exceptions import BrandResolutionError, ConfigurationError

Channel = Literal["email", "whatsapp", "sms"]
CHANNELS: tuple[Channel, ...] = ("email", "whatsapp", "sms")
KNOWN_BRAND_IDS = ("shaadi", "marketing", "staffing", "property", "skyline")
SECRET_REF_RE = re.compile(r"^projects/[^/]+/secrets/[A-Za-z0-9_-]+/versions/[A-Za-z0-9_-]+$")
DIGITS_RE = re.compile(r"^\d+$")


def _check_secret_ref(value: str) -> str:
    if value and not (SECRET_REF_RE.match(value) or value.startswith("env://")):
        raise ValueError(
            "secret references must be 'projects/<p>/secrets/<name>/versions/<v>' (or env://VAR for local dev)"
        )
    return value


class PhoneNumber(BaseModel):
    phone_number_id: str
    display_number: str = ""
    default: bool = False


class WhatsAppBrandConfig(BaseModel):
    enabled: bool = False
    waba_id: str = ""
    app_id: str = ""
    phone_numbers: list[PhoneNumber] = Field(default_factory=list)
    access_token_secret: str = ""
    default_country_code: str = "91"

    @field_validator("access_token_secret")
    @classmethod
    def _v_secret(cls, value: str) -> str:
        return _check_secret_ref(value)

    @model_validator(mode="after")
    def _enabled_requires_ids(self) -> WhatsAppBrandConfig:
        if self.enabled:
            missing = [
                name
                for name, value in (
                    ("waba_id", self.waba_id),
                    ("app_id", self.app_id),
                    ("access_token_secret", self.access_token_secret),
                )
                if not value
            ]
            if not self.phone_numbers:
                missing.append("phone_numbers")
            if missing:
                raise ValueError(f"whatsapp enabled but missing: {', '.join(missing)}")
            for pid in [p.phone_number_id for p in self.phone_numbers] + [self.waba_id, self.app_id]:
                if not DIGITS_RE.match(pid):
                    raise ValueError(f"Meta IDs must be numeric, got {pid!r}")
        return self

    def phone_number_ids(self) -> set[str]:
        return {p.phone_number_id for p in self.phone_numbers}

    def default_phone_number_id(self) -> str:
        for number in self.phone_numbers:
            if number.default:
                return number.phone_number_id
        return self.phone_numbers[0].phone_number_id if self.phone_numbers else ""


class SmsTemplate(BaseModel):
    template_id: str
    name: str
    sender_header: str
    content_type: Literal["promotional", "transactional", "service_implicit", "service_explicit"]
    content: str
    enabled: bool = True


class SmsBrandConfig(BaseModel):
    enabled: bool = False
    provider: str = "mock"
    dlt_principal_entity_id: str = ""
    sender_headers: list[str] = Field(default_factory=list)
    api_secret: str = ""
    default_country_code: str = "91"
    require_consent: bool = True
    templates: list[SmsTemplate] = Field(default_factory=list)

    @field_validator("api_secret")
    @classmethod
    def _v_secret(cls, value: str) -> str:
        return _check_secret_ref(value)


class EmailBrandConfig(BaseModel):
    enabled: bool = True
    legacy_config: str = ""


class MetaAppConfig(BaseModel):
    app_secret_secret: str
    verify_token_secret: str

    @field_validator("app_secret_secret", "verify_token_secret")
    @classmethod
    def _v_secret(cls, value: str) -> str:
        return _check_secret_ref(value)


class BrandConfig(BaseModel):
    brand_id: str
    name: str
    email: EmailBrandConfig = Field(default_factory=EmailBrandConfig)
    whatsapp: WhatsAppBrandConfig = Field(default_factory=WhatsAppBrandConfig)
    sms: SmsBrandConfig = Field(default_factory=SmsBrandConfig)

    def channel_enabled(self, channel: str) -> bool:
        flags = {"email": self.email.enabled, "whatsapp": self.whatsapp.enabled, "sms": self.sms.enabled}
        return bool(flags.get(channel, False))


class BrandRegistry:
    def __init__(self, brands: dict[str, BrandConfig], meta_apps: dict[str, MetaAppConfig]) -> None:
        self.brands = brands
        self.meta_apps = meta_apps

    @classmethod
    def from_dict(cls, data: dict, email_brands_dir: Path | None = None) -> BrandRegistry:
        raw_brands = data.get("brands") or {}
        if not isinstance(raw_brands, dict):
            raise ConfigurationError("brands.yaml: 'brands' must be a mapping")
        brands: dict[str, BrandConfig] = {}
        for brand_id, body in raw_brands.items():
            if brand_id not in KNOWN_BRAND_IDS:
                raise ConfigurationError(f"brands.yaml: unknown brand id {brand_id!r}; allowed {KNOWN_BRAND_IDS}")
            try:
                brands[brand_id] = BrandConfig.model_validate({"brand_id": brand_id, **(body or {})})
            except Exception as error:
                raise ConfigurationError(f"brands.yaml: brand {brand_id}: {error}") from error
        meta_apps: dict[str, MetaAppConfig] = {}
        for app_id, body in (data.get("meta_apps") or {}).items():
            meta_apps[str(app_id)] = MetaAppConfig.model_validate(body)
        registry = cls(brands, meta_apps)
        registry._cross_validate(email_brands_dir)
        return registry

    def _cross_validate(self, email_brands_dir: Path | None) -> None:
        waba_owner: dict[str, str] = {}
        phone_owner: dict[str, str] = {}
        for brand in self.brands.values():
            wa = brand.whatsapp
            if wa.enabled:
                if wa.app_id not in self.meta_apps:
                    raise ConfigurationError(f"{brand.brand_id}: whatsapp.app_id {wa.app_id} has no meta_apps entry")
                # A WABA/phone number may only be authorised for one brand, so a
                # template or opt-in on one brand can never be used by another.
                if wa.waba_id in waba_owner:
                    raise ConfigurationError(
                        f"WABA {wa.waba_id} assigned to both {waba_owner[wa.waba_id]} and {brand.brand_id}"
                    )
                waba_owner[wa.waba_id] = brand.brand_id
                for pid in wa.phone_number_ids():
                    if pid in phone_owner:
                        raise ConfigurationError(f"Phone number id {pid} assigned to two brands")
                    phone_owner[pid] = brand.brand_id
            if email_brands_dir is not None and brand.email.enabled:
                legacy = email_brands_dir / brand.brand_id / "config.json"
                if not legacy.exists():
                    raise ConfigurationError(f"{brand.brand_id}: existing email config {legacy} not found")
                data = json.loads(legacy.read_text(encoding="utf-8"))
                if data.get("brand_id") != brand.brand_id:
                    raise ConfigurationError(f"{legacy}: brand_id mismatch")

    def get(self, brand_id: str) -> BrandConfig:
        brand = self.brands.get(brand_id)
        if brand is None:
            raise BrandResolutionError(f"Unknown brand {brand_id!r}")
        return brand

    def require_channel(self, brand_id: str, channel: str) -> BrandConfig:
        brand = self.get(brand_id)
        if not brand.channel_enabled(channel):
            raise BrandResolutionError(
                f"Channel {channel} is not enabled for brand {brand_id}", code="channel_disabled"
            )
        return brand

    def brand_for_phone_number_id(self, phone_number_id: str) -> BrandConfig | None:
        for brand in self.brands.values():
            if phone_number_id in brand.whatsapp.phone_number_ids():
                return brand
        return None

    def brand_for_waba(self, waba_id: str) -> BrandConfig | None:
        for brand in self.brands.values():
            if brand.whatsapp.waba_id and brand.whatsapp.waba_id == waba_id:
                return brand
        return None


@lru_cache(maxsize=1)
def _load(path: str, email_dir: str) -> BrandRegistry:
    return BrandRegistry.from_dict(load_yaml(Path(path)), Path(email_dir) / "brands")


def load_brand_registry(settings: Settings | None = None) -> BrandRegistry:
    settings = settings or load_settings()
    return _load(str(config_file("brands", settings)), str(settings.email_service_dir))


def reset_cache() -> None:
    _load.cache_clear()


__all__ = [
    "CHANNELS",
    "KNOWN_BRAND_IDS",
    "REPO_ROOT",
    "BrandConfig",
    "BrandRegistry",
    "Channel",
    "load_brand_registry",
]
