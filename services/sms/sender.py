"""SMS dispatch for one queued message (called by the SMS worker)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from services.sms.dlt_validator import find_template, render
from services.sms.gateway_interface import SmsGateway, SmsSendRequest, get_gateway
from shared.approvals import Approvals
from shared.audit import audit, mask_address
from shared.brand_registry import BrandConfig, BrandRegistry
from shared.config import ChannelsConfig
from shared.consent import ConsentRegistry
from shared.controls import Controls
from shared.exceptions import (
    AutomationError,
    ConsentError,
    ControlBlockedError,
    InvalidCredentialsError,
    InvalidTemplateError,
    ProviderError,
    ProviderRejectedError,
    RateLimitedError,
    SuppressedError,
    TransientProviderError,
    UncertainSendError,
    ValidationError,
)
from shared.idempotency import claim_recipient_window, release_recipient_window
from shared.job_manager import JOBS, JobManager
from shared.rate_limits import RateLimiter
from shared.secrets import get_resolver
from shared.store import Store
from shared.suppression import SuppressionList

CHANNEL = "sms"
SMS_INDEX = "sms_provider_ids"
MAX_TRANSIENT_ATTEMPTS = 5


def default_gateway_factory(brand: BrandConfig) -> SmsGateway:
    cfg = brand.sms
    credential = get_resolver().get(cfg.api_secret) if cfg.api_secret else None
    return get_gateway(cfg.provider, credential)


def live_send_permitted(channels: ChannelsConfig, phone: str, gateway: SmsGateway) -> tuple[bool, str]:
    cfg = channels.sms
    if cfg.live_send_enabled and not gateway.is_test_adapter:
        return True, "live"
    if phone in {p.lstrip("+") for p in cfg.test_recipients}:
        return True, "test_recipient"
    if gateway.is_test_adapter and not cfg.live_send_enabled:
        # The mock adapter never reaches a real handset, so it is safe for staging.
        return True, "test_adapter"
    return False, "live_send_disabled"


class SmsSender:
    def __init__(
        self,
        *,
        store: Store,
        registry: BrandRegistry,
        channels: ChannelsConfig,
        jobs: JobManager,
        gateway_factory: Callable[[BrandConfig], SmsGateway] | None = None,
    ) -> None:
        self.store = store
        self.registry = registry
        self.channels = channels
        self.jobs = jobs
        self.controls = Controls(store)
        self.approvals = Approvals(store)
        self.consent = ConsentRegistry(store)
        self.suppression = SuppressionList(store)
        self.rate_limiter = RateLimiter(store)
        self.gateway_factory = gateway_factory or default_gateway_factory

    def _finish(
        self, key: str, status: str, msg: dict[str, Any], error: AutomationError | None = None, **fields: Any
    ) -> dict[str, Any]:
        if error is not None:
            fields.setdefault("error_code", error.code)
            fields.setdefault("error_message", str(error)[:300])
            if isinstance(error, ProviderError):
                fields.setdefault("provider_code", error.provider_code)
        self.jobs.transition(key, ("sending",), status, **fields)
        audit(
            f"sms_message_{status}",
            brand_id=msg["brand_id"],
            channel=CHANNEL,
            job_id=msg["job_id"],
            message_id=key,
            error_code=fields.get("error_code"),
            retry_count=msg.get("attempts"),
            details={"to": mask_address(msg.get("phone", ""))},
            store=self.store,
        )
        out = {"message_key": key, "status": status}
        if "error_code" in fields:
            out["error_code"] = fields["error_code"]
        return out

    def dispatch(self, message_key: str) -> dict[str, Any]:
        msg = self.jobs.get_message(message_key)
        if not msg:
            return {"message_key": message_key, "status": "not_found"}
        brand_id = msg["brand_id"]
        allowed, reason = self.controls.dispatch_allowed(brand_id, CHANNEL)
        if not allowed:
            self.jobs.transition(message_key, ("queued", "retry_scheduled"), "held", held_reason=reason)
            return {"message_key": message_key, "status": "held", "reason": reason}
        claimed = self.jobs.claim(message_key, "sms-worker")
        if claimed is None:
            return {"message_key": message_key, "status": "not_claimed"}
        msg = claimed
        try:
            self.controls.check_dispatch(brand_id, CHANNEL)
        except ControlBlockedError as error:
            self.jobs.transition(message_key, ("sending",), "held", held_reason=error.code)
            return {"message_key": message_key, "status": "held", "reason": error.code}
        job = self.store.get(JOBS, msg["job_id"]) or {}
        if job.get("status") == "cancelled":
            return self._finish(message_key, "cancelled", msg)
        phone = msg["phone"]
        try:
            self.approvals.verify(
                job_id=msg["job_id"],
                brand_id=brand_id,
                channel=CHANNEL,
                template_key=job.get("template_key", ""),
                snapshot_hash=job.get("snapshot_hash", ""),
            )
            brand = self.registry.require_channel(brand_id, CHANNEL)
            gateway = self.gateway_factory(brand)
            permitted, gate = live_send_permitted(self.channels, phone, gateway)
            if not permitted:
                raise ValidationError("live SMS sending is disabled for this recipient", code=gate)
            if brand.sms.require_consent:
                self.consent.require_opt_in(brand_id, CHANNEL, phone)
            self.suppression.require_not_suppressed(brand_id, CHANNEL, phone)
            template = find_template(brand.sms, msg["template_id"])
            rendered = render(template, list(msg.get("variables") or []), self.channels.sms.max_variable_length)
        except (ConsentError, SuppressedError) as error:
            return self._finish(message_key, "skipped", msg, error)
        except ValidationError as error:
            return self._finish(message_key, "skipped" if error.code == "live_send_disabled" else "failed", msg, error)
        except AutomationError as error:
            return self._finish(message_key, "failed", msg, error)

        claimed_window, existing = claim_recipient_window(
            self.store,
            brand_id,
            CHANNEL,
            template.template_id,
            phone,
            message_key,
            self.channels.sms.duplicate_window_hours,
        )
        if not claimed_window:
            return self._finish(
                message_key,
                "skipped",
                msg,
                ValidationError("duplicate within window", code="duplicate_recipient"),
                duplicate_of=existing,
            )
        limit = self.channels.rate_limit(CHANNEL, brand_id)
        try:
            self.rate_limiter.acquire(brand_id, CHANNEL, limit.per_minute, limit.per_day)
        except RateLimitedError as error:
            release_recipient_window(self.store, brand_id, CHANNEL, template.template_id, phone, message_key)
            self.jobs.schedule_retry(message_key, error.retry_after_seconds, error.code)
            return {"message_key": message_key, "status": "retry_scheduled", "error_code": error.code}

        request = SmsSendRequest(
            to=phone,
            sender_header=template.sender_header,
            dlt_entity_id=brand.sms.dlt_principal_entity_id,
            dlt_template_id=template.template_id,
            text=rendered.text,
            content_type=template.content_type,
            callback_ref=message_key,
        )
        try:
            result = gateway.send(request)
        except (RateLimitedError, TransientProviderError) as error:
            release_recipient_window(self.store, brand_id, CHANNEL, template.template_id, phone, message_key)
            if isinstance(error, TransientProviderError) and int(msg.get("attempts", 1)) >= MAX_TRANSIENT_ATTEMPTS:
                return self._finish(message_key, "failed", msg, error)
            delay = error.retry_after_seconds if isinstance(error, RateLimitedError) else 60
            self.jobs.schedule_retry(message_key, delay, error.code)
            return {"message_key": message_key, "status": "retry_scheduled", "error_code": error.code}
        except InvalidCredentialsError as error:
            release_recipient_window(self.store, brand_id, CHANNEL, template.template_id, phone, message_key)
            self.controls.stop(brand_id, CHANNEL, actor="system", reason=f"auto-stop: {error.code}")
            self.jobs.transition(message_key, ("sending",), "held", held_reason=error.code, error_code=error.code)
            return {"message_key": message_key, "status": "held", "error_code": error.code}
        except (InvalidTemplateError, ProviderRejectedError) as error:
            release_recipient_window(self.store, brand_id, CHANNEL, template.template_id, phone, message_key)
            return self._finish(message_key, "failed", msg, error)
        except (UncertainSendError, ProviderError) as error:
            return self._finish(message_key, "uncertain", msg, error, needs_reconciliation=True)
        self.store.set(
            SMS_INDEX,
            f"{brand.sms.provider}:{result.provider_message_id}",
            {"message_key": message_key, "brand_id": brand_id},
        )
        return self._finish(
            message_key,
            "accepted",
            msg,
            provider_message_id=result.provider_message_id,
            delivery_status="accepted",
            segments=rendered.segments,
            encoding=rendered.encoding,
            test_adapter=gateway.is_test_adapter,
        )
