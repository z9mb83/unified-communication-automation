"""Classification of Meta WhatsApp Cloud API errors into the shared error classes.

Meta returns errors as ``{"error": {"message", "type", "code", "error_subcode",
"error_data": {"details"}, "fbtrace_id"}}``. Codes referenced below are from
Meta's published Cloud API error-code list; anything unknown falls back on the
HTTP status. See docs/ERROR_RESOLUTION.md for operator actions per class.
"""

from __future__ import annotations

from typing import Any

from shared.exceptions import (
    InvalidCredentialsError,
    InvalidTemplateError,
    ProviderError,
    ProviderRejectedError,
    RateLimitedError,
    TransientProviderError,
    UncertainSendError,
)

# Authentication / authorisation: token expired, revoked, missing permission.
AUTH_CODES = {0, 3, 10, 190} | set(range(200, 300))
# Throttling: app/account/business-number rate limits, pair rate limit, spam limit.
RATE_LIMIT_CODES = {4, 80007, 130429, 131048, 131056}
# Template problems: missing/unapproved template, parameter count/format mismatch,
# translation missing, template paused/disabled.
TEMPLATE_CODES = {132000, 132001, 132005, 132007, 132012, 132015, 132016, 132068, 132069}
# Recipient-level rejections that are definitive (do not retry).
RECIPIENT_REJECT_CODES = {131008, 131009, 131021, 131026, 131030, 131045, 131047, 131051, 133010}
# Marketing-message opt-out / Meta chose not to deliver.
OPT_OUT_CODES = {131050}
# Generic "something went wrong" / service unavailable: outcome unknown on send.
AMBIGUOUS_CODES = {1, 2, 131000, 131016}

RATE_LIMIT_BACKOFF_SECONDS = {4: 300, 80007: 900, 130429: 60, 131048: 3600, 131056: 60}


def _error_body(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        return payload["error"]
    return {}


def summarize(payload: Any) -> dict[str, Any]:
    """Provider response fields that are safe to log/store (no tokens, no content)."""
    err = _error_body(payload)
    if not err:
        return {}
    details = (err.get("error_data") or {}).get("details")
    return {
        "code": err.get("code"),
        "subcode": err.get("error_subcode"),
        "type": err.get("type"),
        "message": str(err.get("message", ""))[:300],
        "details": str(details)[:300] if details else None,
        "fbtrace_id": err.get("fbtrace_id"),
    }


def classify(http_status: int, payload: Any, *, is_send: bool) -> ProviderError:
    err = _error_body(payload)
    code = err.get("code")
    try:
        code_int = int(code) if code is not None else None
    except (TypeError, ValueError):
        code_int = None
    summary = summarize(payload)
    message = summary.get("message") or f"Meta API HTTP {http_status}"
    kwargs: dict[str, Any] = {"provider_code": code_int, "provider_response": summary}

    if code_int in RATE_LIMIT_CODES or http_status == 429:
        return RateLimitedError(
            message, retry_after_seconds=RATE_LIMIT_BACKOFF_SECONDS.get(code_int or 0, 120), **kwargs
        )
    oauth_error = err.get("type") == "OAuthException" and code_int in (None, 190)
    if code_int in AUTH_CODES or http_status in (401, 403) or oauth_error:
        return InvalidCredentialsError(message, **kwargs)
    if code_int in TEMPLATE_CODES:
        return InvalidTemplateError(message, **kwargs)
    if code_int in OPT_OUT_CODES:
        return ProviderRejectedError(message, code="recipient_opted_out_marketing", **kwargs)
    if code_int in RECIPIENT_REJECT_CODES:
        return ProviderRejectedError(message, **kwargs)
    if code_int in AMBIGUOUS_CODES or http_status >= 500:
        if is_send:
            return UncertainSendError(message, **kwargs)
        return TransientProviderError(message, **kwargs)
    if 400 <= http_status < 500:
        return ProviderRejectedError(message, **kwargs)
    return ProviderError(message, **kwargs)
