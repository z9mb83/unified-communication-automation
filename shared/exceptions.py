"""Structured error hierarchy shared by every channel.

Every error carries a stable machine-readable ``code`` so that logs, audit
records, the Sheets UI and alerting can reason about failures without parsing
free text.  ``retryable`` tells workers whether an automatic retry is safe.
``uncertain`` marks the dangerous case where a provider may already have
accepted a message: such messages must never be retried automatically.
"""

from __future__ import annotations

from typing import Any


class AutomationError(Exception):
    code = "automation_error"
    retryable = False
    uncertain = False
    http_status = 500

    def __init__(self, message: str, *, code: str | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.code,
            "message": str(self),
            "retryable": self.retryable,
            "uncertain": self.uncertain,
            "details": self.details,
        }


# ---- Configuration / authorization -------------------------------------------------


class ConfigurationError(AutomationError):
    code = "configuration_error"
    http_status = 500


class BrandResolutionError(AutomationError):
    """The spreadsheet/tab is not mapped to exactly one brand, or a row's Brand ID is invalid."""

    code = "brand_resolution_failed"
    http_status = 422


class AuthenticationError(AutomationError):
    code = "unauthenticated"
    http_status = 401


class AuthorizationError(AutomationError):
    code = "forbidden"
    http_status = 403


class ReplayError(AutomationError):
    code = "replayed_request"
    http_status = 409


class ValidationError(AutomationError):
    code = "validation_failed"
    http_status = 422


class ControlBlockedError(AutomationError):
    """Dispatch refused because a Stop / Emergency Stop flag is active."""

    code = "dispatch_blocked_by_control"
    http_status = 409


class DuplicateJobError(AutomationError):
    code = "duplicate_job"
    http_status = 409


# ---- Consent / suppression ------------------------------------------------------------


class ConsentError(AutomationError):
    code = "consent_missing"
    http_status = 422


class SuppressedError(AutomationError):
    code = "recipient_suppressed"
    http_status = 422


# ---- Provider errors (used by WhatsApp and SMS) ----------------------------------------


class ProviderError(AutomationError):
    code = "provider_error"
    http_status = 502

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        provider_code: str | int | None = None,
        provider_response: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)
        self.provider_code = provider_code
        self.provider_response = provider_response or {}

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["provider_code"] = self.provider_code
        return data


class ProviderRejectedError(ProviderError):
    """The provider synchronously refused the submission (bad recipient, policy, params)."""

    code = "provider_rejected"


class DeliveryFailedError(ProviderError):
    """The provider accepted the message but later reported that delivery failed."""

    code = "delivery_failed"


class RateLimitedError(ProviderError):
    """Temporary throttling; the message was NOT accepted and may be retried later."""

    code = "rate_limited"
    retryable = True
    http_status = 429

    def __init__(self, message: str, *, retry_after_seconds: int = 60, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after_seconds = retry_after_seconds


class InvalidCredentialsError(ProviderError):
    """Access token invalid/expired/revoked or lacks permission. Needs human action."""

    code = "invalid_credentials"
    http_status = 502


class InvalidTemplateError(ProviderError):
    """Template missing, not approved, paused, or parameters do not match it."""

    code = "invalid_template"
    http_status = 422


class TransientProviderError(ProviderError):
    """Provider unavailable before the request was accepted (e.g. connect timeout, 5xx
    that the provider documents as not-processed). Safe to retry."""

    code = "provider_unavailable"
    retryable = True


class UncertainSendError(ProviderError):
    """The request may have reached the provider but no definitive answer came back
    (read timeout, dropped connection). NEVER retry automatically: reconcile first."""

    code = "send_outcome_uncertain"
    uncertain = True
