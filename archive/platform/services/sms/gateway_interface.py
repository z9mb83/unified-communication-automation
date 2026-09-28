"""Provider-neutral SMS gateway interface.

No live SMS gateway was identified in the existing project, so only the
interface and a test adapter (``providers/mock.py``) ship today. Adding a real
Indian DLT-compliant provider means implementing :class:`SmsGateway` in
``providers/<name>.py`` and registering it in :data:`PROVIDERS` — nothing else
in the pipeline changes. See docs/SMS_DLT_SETUP.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from shared.exceptions import ConfigurationError
from shared.secrets import SecretValue


@dataclass(frozen=True)
class SmsSendRequest:
    to: str  # E.164 digits, no '+'
    sender_header: str  # DLT-registered header (sender ID)
    dlt_entity_id: str  # Principal Entity ID
    dlt_template_id: str  # DLT content template ID
    text: str  # exact rendered text of the registered template
    content_type: str  # promotional | transactional | service_implicit | service_explicit
    callback_ref: str  # our idempotency key, echoed back in delivery reports


@dataclass(frozen=True)
class SmsSendResult:
    provider_message_id: str
    status: str = "accepted"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DeliveryReport:
    provider_message_id: str
    status: str  # delivered | failed | expired | rejected | sent
    callback_ref: str | None = None
    error_code: str | None = None
    timestamp: str | None = None


class SmsGateway(ABC):
    name: str = "abstract"
    is_test_adapter: bool = False

    def __init__(self, credential: SecretValue | None) -> None:
        self.credential = credential

    @abstractmethod
    def send(self, request: SmsSendRequest) -> SmsSendResult:
        """Submit one SMS. Must raise the shared error classes:
        RateLimitedError / TransientProviderError (not accepted, retryable),
        UncertainSendError (maybe accepted), ProviderRejectedError,
        InvalidCredentialsError, InvalidTemplateError (DLT scrubbing failure)."""

    @abstractmethod
    def verify_callback(self, headers: dict[str, str], raw_body: bytes, secret: SecretValue) -> None:
        """Raise AuthenticationError unless the delivery callback is authentic."""

    @abstractmethod
    def parse_callback(self, raw_body: bytes) -> list[DeliveryReport]:
        """Translate a provider callback into DeliveryReports."""


PROVIDERS: dict[str, Callable[[SecretValue | None], SmsGateway]] = {}


def register(name: str) -> Callable[[type[SmsGateway]], type[SmsGateway]]:
    def wrap(cls: type[SmsGateway]) -> type[SmsGateway]:
        PROVIDERS[name] = cls
        return cls

    return wrap


def get_gateway(name: str, credential: SecretValue | None) -> SmsGateway:
    # Import providers so they self-register.
    from services.sms.providers import mock  # noqa: F401

    factory = PROVIDERS.get(name)
    if factory is None:
        raise ConfigurationError(f"SMS provider {name!r} is not implemented", code="sms_provider_not_implemented")
    return factory(credential)
