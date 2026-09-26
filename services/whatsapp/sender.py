"""WhatsApp dispatch for one queued message (called by the WhatsApp worker).

Order of checks before any provider call:
controls -> atomic claim -> controls again -> approval -> job not cancelled ->
live-send gate -> consent -> suppression -> template (brand, WABA, APPROVED,
language) -> phone-number association -> variables -> per-recipient duplicate
window -> rate limit -> send.
"""

from __future__ import annotations

import socket
from collections.abc import Callable
from typing import Any

from services.whatsapp.meta_client import MetaClient
from services.whatsapp.template_renderer import render_components
from services.whatsapp.template_sync import TemplateRepository
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

CHANNEL = "whatsapp"
MAX_TRANSIENT_ATTEMPTS = 5
WAMID_INDEX = "wa_wamid"


def default_client_factory(channels: ChannelsConfig) -> Callable[[BrandConfig], MetaClient]:
    cfg = channels.whatsapp

    def factory(brand: BrandConfig) -> MetaClient:
        ref = brand.whatsapp.access_token_secret
        return MetaClient(
            lambda: get_resolver().get(ref),
            api_version=cfg.graph_api_version,
            base_url=cfg.graph_base_url,
            connect_timeout=cfg.connect_timeout_seconds,
            read_timeout=cfg.request_timeout_seconds,
        )

    return factory


def live_send_permitted(channels: ChannelsConfig, phone: str) -> tuple[bool, str]:
    cfg = channels.whatsapp
    if cfg.live_send_enabled:
        return True, "live"
    if phone in {p.lstrip("+") for p in cfg.test_recipients}:
        return True, "test_recipient"
    return False, "live_send_disabled"


class WhatsAppSender:
    def __init__(
        self,
        *,
        store: Store,
        registry: BrandRegistry,
        channels: ChannelsConfig,
        jobs: JobManager,
        client_factory: Callable[[BrandConfig], MetaClient] | None = None,
    ) -> None:
        self.store = store
        self.registry = registry
        self.channels = channels
        self.jobs = jobs
        self.controls = Controls(store)
        self.approvals = Approvals(store)
        self.consent = ConsentRegistry(store)
        self.suppression = SuppressionList(store)
        self.templates = TemplateRepository(store)
        self.rate_limiter = RateLimiter(store)
        self.client_factory = client_factory or default_client_factory(channels)
        self.worker_id = f"{socket.gethostname()}"

    def _finish(
        self, key: str, status: str, msg: dict[str, Any], error: AutomationError | None = None, **fields: Any
    ) -> dict[str, Any]:
        if error is not None:
            fields.setdefault("error_code", error.code)
            fields.setdefault("error_message", str(error)[:300])
            if isinstance(error, ProviderError):
                fields.setdefault("provider_code", error.provider_code)
                fields.setdefault("provider_response", error.provider_response)
        self.jobs.transition(key, ("sending",), status, **fields)
        audit(
            f"wa_message_{status}",
            brand_id=msg["brand_id"],
            channel=CHANNEL,
            job_id=msg["job_id"],
            message_id=key,
            error_code=fields.get("error_code"),
            provider_response=fields.get("provider_response"),
            retry_count=msg.get("attempts"),
            details={"to": mask_address(msg.get("phone", ""))},
            store=self.store,
        )
        return {
            "message_key": key,
            "status": status,
            **({"error_code": fields["error_code"]} if "error_code" in fields else {}),
        }

    def dispatch(self, message_key: str) -> dict[str, Any]:
        msg = self.jobs.get_message(message_key)
        if not msg:
            return {"message_key": message_key, "status": "not_found"}
        brand_id = msg["brand_id"]
        allowed, reason = self.controls.dispatch_allowed(brand_id, CHANNEL)
        if not allowed:
            self.jobs.transition(message_key, ("queued", "retry_scheduled"), "held", held_reason=reason)
            return {"message_key": message_key, "status": "held", "reason": reason}

        claimed = self.jobs.claim(message_key, self.worker_id)
        if claimed is None:
            current = self.jobs.get_message(message_key) or {}
            return {"message_key": message_key, "status": "not_claimed", "current_status": current.get("status")}
        msg = claimed

        try:
            self.controls.check_dispatch(brand_id, CHANNEL)
        except ControlBlockedError as error:
            self.jobs.transition(message_key, ("sending",), "held", held_reason=error.code)
            return {"message_key": message_key, "status": "held", "reason": error.code}

        job = self.store.get(JOBS, msg["job_id"]) or {}
        if job.get("status") == "cancelled":
            return self._finish(message_key, "cancelled", msg)

        try:
            self.approvals.verify(
                job_id=msg["job_id"],
                brand_id=brand_id,
                channel=CHANNEL,
                template_key=job.get("template_key", ""),
                snapshot_hash=job.get("snapshot_hash", ""),
            )
            brand = self.registry.require_channel(brand_id, CHANNEL)
            phone = msg["phone"]
            permitted, gate = live_send_permitted(self.channels, phone)
            if not permitted:
                raise ValidationError(
                    "live WhatsApp sending is disabled and recipient is not a test recipient", code=gate
                )
            self.consent.require_opt_in(brand_id, CHANNEL, phone)
            self.suppression.require_not_suppressed(brand_id, CHANNEL, phone)
            spec = self.templates.get_sendable(brand, msg["template_id"], msg.get("language"))
            phone_number_id = msg.get("phone_number_id") or brand.whatsapp.default_phone_number_id()
            if phone_number_id not in brand.whatsapp.phone_number_ids():
                raise ValidationError(
                    "phone number id is not configured for this brand", code="phone_number_not_for_brand"
                )
            if phone_number_id not in self.templates.verified_phone_numbers(brand_id):
                raise ValidationError(
                    "phone number is not verified as belonging to the brand's WABA; run template sync",
                    code="phone_number_not_verified",
                )
            components = render_components(spec, msg.get("variables") or {})
        except (ConsentError, SuppressedError) as error:
            return self._finish(message_key, "skipped", msg, error)
        except ValidationError as error:
            status = "skipped" if error.code == "live_send_disabled" else "failed"
            return self._finish(message_key, status, msg, error)
        except InvalidTemplateError as error:
            return self._finish(message_key, "failed", msg, error)
        except AutomationError as error:  # approval / brand problems
            return self._finish(message_key, "failed", msg, error)

        template_key = f"{spec.template_id}:{spec.language}"
        claimed_window, existing = claim_recipient_window(
            self.store,
            brand_id,
            CHANNEL,
            template_key,
            phone,
            message_key,
            self.channels.whatsapp.duplicate_window_hours,
        )
        if not claimed_window:
            return self._finish(
                message_key,
                "skipped",
                msg,
                ValidationError("same template already sent to this recipient recently", code="duplicate_recipient"),
                duplicate_of=existing,
            )

        limit = self.channels.rate_limit(CHANNEL, brand_id)
        try:
            self.rate_limiter.acquire(brand_id, CHANNEL, limit.per_minute, limit.per_day)
        except RateLimitedError as error:
            release_recipient_window(self.store, brand_id, CHANNEL, template_key, phone, message_key)
            self.jobs.schedule_retry(message_key, error.retry_after_seconds, error.code)
            return {"message_key": message_key, "status": "retry_scheduled", "error_code": error.code}

        client = self.client_factory(brand)
        try:
            result = client.send_template(
                phone_number_id=phone_number_id,
                to=phone,
                template_name=spec.name,
                language=spec.language,
                components=components,
                callback_data=message_key,
            )
        except RateLimitedError as error:
            release_recipient_window(self.store, brand_id, CHANNEL, template_key, phone, message_key)
            self.jobs.schedule_retry(message_key, error.retry_after_seconds, error.code)
            audit(
                "wa_rate_limited",
                brand_id=brand_id,
                channel=CHANNEL,
                message_id=message_key,
                error_code=error.code,
                provider_response=error.provider_response,
                store=self.store,
            )
            return {"message_key": message_key, "status": "retry_scheduled", "error_code": error.code}
        except TransientProviderError as error:
            release_recipient_window(self.store, brand_id, CHANNEL, template_key, phone, message_key)
            if int(msg.get("attempts", 1)) >= MAX_TRANSIENT_ATTEMPTS:
                return self._finish(message_key, "failed", msg, error)
            self.jobs.schedule_retry(message_key, 60 * int(msg.get("attempts", 1)), error.code)
            return {"message_key": message_key, "status": "retry_scheduled", "error_code": error.code}
        except InvalidCredentialsError as error:
            # Not sent. Stop this brand's WhatsApp channel so every queued message
            # is held until a human fixes the token, then put this one on hold too.
            release_recipient_window(self.store, brand_id, CHANNEL, template_key, phone, message_key)
            self.controls.stop(brand_id, CHANNEL, actor="system", reason=f"auto-stop: {error.code}")
            audit(
                "wa_channel_auto_stopped",
                brand_id=brand_id,
                channel=CHANNEL,
                error_code=error.code,
                provider_response=error.provider_response,
                store=self.store,
            )
            self.jobs.transition(message_key, ("sending",), "held", held_reason=error.code, error_code=error.code)
            return {"message_key": message_key, "status": "held", "error_code": error.code}
        except InvalidTemplateError as error:
            release_recipient_window(self.store, brand_id, CHANNEL, template_key, phone, message_key)
            return self._finish(message_key, "failed", msg, error)
        except ProviderRejectedError as error:
            release_recipient_window(self.store, brand_id, CHANNEL, template_key, phone, message_key)
            if error.code == "recipient_opted_out_marketing":
                self.suppression.add(brand_id, CHANNEL, phone, reason="opt_out", source="meta_131050", actor="system")
            return self._finish(message_key, "failed", msg, error)
        except UncertainSendError as error:
            # Keep the recipient-window claim: a resend could duplicate.
            out = self._finish(message_key, "uncertain", msg, error, needs_reconciliation=True)
            return out
        except ProviderError as error:
            return self._finish(message_key, "uncertain", msg, error, needs_reconciliation=True)

        self.store.set(WAMID_INDEX, result["wamid"], {"message_key": message_key, "brand_id": brand_id})
        return self._finish(
            message_key,
            "accepted",
            msg,
            wamid=result["wamid"],
            wa_id=result.get("wa_id"),
            delivery_status=result.get("message_status") or "accepted",
        )
