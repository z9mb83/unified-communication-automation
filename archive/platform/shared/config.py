"""Runtime settings (environment) and channel configuration (YAML).

Nothing in here holds a secret value. Secrets are referenced by Secret Manager
resource names and resolved lazily by :mod:`shared.secrets`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from shared.exceptions import ConfigurationError

REPO_ROOT = Path(__file__).resolve().parents[1]
GRAPH_VERSION_RE = re.compile(r"^v\d{2,3}\.\d$")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, "").split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    env: str
    service_role: str
    config_dir: Path
    gcp_project: str
    gcp_region: str
    allowed_audiences: list[str]
    allowed_issuers: list[str]
    request_max_age_seconds: int
    tasks_location: str
    tasks_queues: dict[str, str]
    worker_base_url: str
    tasks_invoker_service_account: str
    worker_allowed_callers: list[str]
    email_service_dir: Path
    email_run_job_name: str
    auth_disabled_for_local: bool
    webhook_base_url: str
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def is_production_like(self) -> bool:
        return self.env in {"staging", "production"}


def load_settings() -> Settings:
    env = os.getenv("UCA_ENV", "local").strip().lower()
    if env not in {"local", "test", "staging", "production"}:
        raise ConfigurationError(f"UCA_ENV must be local|test|staging|production, got {env!r}")
    auth_disabled = _env_bool("UCA_AUTH_DISABLED_FOR_LOCAL", False)
    if auth_disabled and env in {"staging", "production"}:
        raise ConfigurationError("UCA_AUTH_DISABLED_FOR_LOCAL cannot be used in staging/production")
    return Settings(
        env=env,
        service_role=os.getenv("UCA_SERVICE_ROLE", "api").strip().lower(),
        config_dir=Path(os.getenv("UCA_CONFIG_DIR", str(REPO_ROOT / "config"))),
        gcp_project=os.getenv("UCA_GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "")).strip(),
        gcp_region=os.getenv("UCA_GCP_REGION", "asia-south1").strip(),
        allowed_audiences=_env_list("UCA_ALLOWED_AUDIENCES"),
        allowed_issuers=_env_list("UCA_ALLOWED_ISSUERS") or ["https://accounts.google.com", "accounts.google.com"],
        request_max_age_seconds=int(os.getenv("UCA_REQUEST_MAX_AGE_SECONDS", "300")),
        tasks_location=os.getenv("UCA_TASKS_LOCATION", os.getenv("UCA_GCP_REGION", "asia-south1")).strip(),
        tasks_queues={
            "email": os.getenv("UCA_QUEUE_EMAIL", "uca-email"),
            "whatsapp": os.getenv("UCA_QUEUE_WHATSAPP", "uca-whatsapp"),
            "sms": os.getenv("UCA_QUEUE_SMS", "uca-sms"),
            "reconciliation": os.getenv("UCA_QUEUE_RECONCILIATION", "uca-reconciliation"),
        },
        worker_base_url=os.getenv("UCA_WORKER_BASE_URL", "").rstrip("/"),
        tasks_invoker_service_account=os.getenv("UCA_TASKS_INVOKER_SA", "").strip(),
        worker_allowed_callers=_env_list("UCA_WORKER_ALLOWED_CALLERS"),
        email_service_dir=Path(os.getenv("UCA_EMAIL_SERVICE_DIR", str(REPO_ROOT / "services" / "email"))),
        email_run_job_name=os.getenv("UCA_EMAIL_RUN_JOB_NAME", "").strip(),
        auth_disabled_for_local=auth_disabled,
        webhook_base_url=os.getenv("UCA_WEBHOOK_BASE_URL", "").rstrip("/"),
    )


def config_file(name: str, settings: Settings | None = None) -> Path:
    """Return ``<config_dir>/<name>.yaml``; fall back to the committed example only
    for local/test runs so production can never silently run on example data."""
    settings = settings or load_settings()
    explicit = os.getenv(f"UCA_{name.upper()}_FILE")
    if explicit:
        return Path(explicit)
    real = settings.config_dir / f"{name}.yaml"
    if real.exists():
        return real
    if settings.env in {"local", "test"}:
        example = REPO_ROOT / "config" / f"{name}.example.yaml"
        if example.exists():
            return example
    raise ConfigurationError(f"Configuration file {real} is missing")


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise ConfigurationError(f"Cannot read {path}: {error}") from error
    if not isinstance(data, dict):
        raise ConfigurationError(f"{path} must contain a mapping at the top level")
    return data


# ---- channels.yaml -----------------------------------------------------------------


class RateLimit(BaseModel):
    per_minute: int = Field(default=20, ge=1)
    per_day: int = Field(default=1000, ge=1)


class WhatsAppChannelConfig(BaseModel):
    graph_api_version: str = "v26.0"
    graph_base_url: str = "https://graph.facebook.com"
    request_timeout_seconds: float = Field(default=20.0, gt=0)
    connect_timeout_seconds: float = Field(default=5.0, gt=0)
    live_send_enabled: bool = False
    test_recipients: list[str] = Field(default_factory=list)
    test_mode_only_allowlist: bool = True
    duplicate_window_hours: int = Field(default=24, ge=0)
    max_recipients_per_job: int = Field(default=500, ge=1)
    uncertain_reconcile_after_minutes: int = Field(default=15, ge=1)
    default_rate_limit: RateLimit = Field(default_factory=RateLimit)
    brand_rate_limits: dict[str, RateLimit] = Field(default_factory=dict)
    opt_out_keywords: list[str] = Field(
        default_factory=lambda: ["STOP", "UNSUBSCRIBE", "STOP ALL", "OPT OUT", "OPTOUT", "CANCEL"]
    )

    @field_validator("graph_api_version")
    @classmethod
    def _version(cls, value: str) -> str:
        if not GRAPH_VERSION_RE.match(value):
            raise ValueError("graph_api_version must look like v26.0")
        return value


class SmsChannelConfig(BaseModel):
    provider: str = "mock"
    live_send_enabled: bool = False
    test_recipients: list[str] = Field(default_factory=list)
    test_mode_only_allowlist: bool = True
    max_variable_length: int = Field(default=30, ge=1)
    duplicate_window_hours: int = Field(default=24, ge=0)
    max_recipients_per_job: int = Field(default=500, ge=1)
    default_rate_limit: RateLimit = Field(default_factory=RateLimit)
    brand_rate_limits: dict[str, RateLimit] = Field(default_factory=dict)
    opt_out_keywords: list[str] = Field(default_factory=lambda: ["STOP", "UNSUBSCRIBE"])


class EmailChannelConfig(BaseModel):
    manual_send_enabled: bool = True
    max_recipients_per_job: int = Field(default=200, ge=1)
    defer_seconds_when_paced: int = Field(default=300, ge=30)
    max_attempts_per_recipient: int = Field(default=200, ge=1)


class ChannelsConfig(BaseModel):
    email: EmailChannelConfig = Field(default_factory=EmailChannelConfig)
    whatsapp: WhatsAppChannelConfig = Field(default_factory=WhatsAppChannelConfig)
    sms: SmsChannelConfig = Field(default_factory=SmsChannelConfig)

    def rate_limit(self, channel: str, brand_id: str) -> RateLimit:
        cfg: WhatsAppChannelConfig | SmsChannelConfig = self.whatsapp if channel == "whatsapp" else self.sms
        return cfg.brand_rate_limits.get(brand_id, cfg.default_rate_limit)


@lru_cache(maxsize=1)
def _channels_cached(path: str) -> ChannelsConfig:
    return ChannelsConfig.model_validate(load_yaml(Path(path)))


def load_channels(settings: Settings | None = None) -> ChannelsConfig:
    return _channels_cached(str(config_file("channels", settings)))


def reset_caches() -> None:
    _channels_cached.cache_clear()
