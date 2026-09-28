"""Structured logging and durable audit records.

Every record carries: event, brand_id, channel, campaign/job ID, message ID,
error_code, provider response (sanitised), retry count and correlation ID.
Secrets and message content are stripped before anything is written.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from shared.store import Store, get_store

correlation_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default="")

SENSITIVE_KEY_RE = re.compile(
    r"(token|secret|password|authorization|api[_-]?key|access[_-]?key|refresh|cookie|signature|credential)",
    re.IGNORECASE,
)
CONTENT_KEYS = {"body", "text", "content", "message_body", "rendered_text", "parameters", "variables", "params"}
BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
LONG_TOKEN_RE = re.compile(
    r"\b(EAA[A-Za-z0-9]{20,}|ya29\.[A-Za-z0-9._-]{20,}|sk-[A-Za-z0-9_-]{20,}|1//[A-Za-z0-9_-]{20,})"
)


def new_correlation_id() -> str:
    return uuid.uuid4().hex


def mask_address(value: str) -> str:
    """'9198765 43210' -> '91******3210', 'a.b@x.com' -> 'a***@x.com'."""
    text = str(value or "")
    if "@" in text:
        local, _, domain = text.partition("@")
        return f"{local[:1]}***@{domain}"
    digits = re.sub(r"\D", "", text)
    if len(digits) <= 4:
        return "****"
    return digits[:2] + "*" * (len(digits) - 6) + digits[-4:] if len(digits) > 6 else "**" + digits[-4:]


def scrub_text(text: str) -> str:
    return LONG_TOKEN_RE.sub("[REDACTED]", BEARER_RE.sub(r"\1[REDACTED]", text))


def sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return "[TRUNCATED]"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if SENSITIVE_KEY_RE.search(key_text):
                out[key_text] = "[REDACTED]"
            elif key_text.lower() in CONTENT_KEYS:
                out[key_text] = "[CONTENT OMITTED]"
            else:
                out[key_text] = sanitize(item, depth + 1)
        return out
    if isinstance(value, list | tuple):
        return [sanitize(item, depth + 1) for item in list(value)[:50]]
    if isinstance(value, str):
        return scrub_text(value)[:2000]
    return value


class JsonFormatter(logging.Formatter):
    """Cloud Logging understands JSON lines with 'severity' and 'message'."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "severity": record.levelname,
            "message": scrub_text(record.getMessage()),
            "logger": record.name,
            "time": datetime.now(UTC).isoformat(),
        }
        correlation = correlation_id_var.get()
        if correlation:
            payload["correlation_id"] = correlation
        extra = getattr(record, "uca", None)
        if isinstance(extra, dict):
            payload.update(sanitize(extra))
        if record.exc_info:
            payload["exception"] = scrub_text(self.formatException(record.exc_info))[:4000]
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


_log = get_logger("uca.audit")


def audit(
    event: str,
    *,
    brand_id: str | None = None,
    channel: str | None = None,
    job_id: str | None = None,
    message_id: str | None = None,
    actor: str | None = None,
    error_code: str | None = None,
    provider_response: Any = None,
    retry_count: int | None = None,
    details: dict[str, Any] | None = None,
    level: int = logging.INFO,
    store: Store | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "event": event,
        "brand_id": brand_id,
        "channel": channel,
        "job_id": job_id,
        "message_id": message_id,
        "actor": actor,
        "error_code": error_code,
        "provider_response": sanitize(provider_response) if provider_response is not None else None,
        "retry_count": retry_count,
        "correlation_id": correlation_id_var.get() or None,
        "details": sanitize(details or {}),
        "at": datetime.now(UTC).isoformat(),
    }
    record = {k: v for k, v in record.items() if v is not None}
    _log.log(level, event, extra={"uca": record})
    if persist:
        try:
            (store or get_store()).add("audit", record)
        except Exception:  # audit persistence must never break a send path
            _log.exception("audit_persist_failed", extra={"uca": {"event": event}})
    return record
