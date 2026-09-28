"""Test SMS adapter. Never touches the network; refuses to be used for live sends.

Behaviour can be scripted per recipient for tests:
``MockSmsGateway.script[to] = "rate_limit" | "timeout" | "reject" | "auth" | "dlt"``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any, ClassVar

from services.sms.gateway_interface import (
    DeliveryReport,
    SmsGateway,
    SmsSendRequest,
    SmsSendResult,
    register,
)
from shared.exceptions import (
    AuthenticationError,
    InvalidCredentialsError,
    InvalidTemplateError,
    ProviderRejectedError,
    RateLimitedError,
    UncertainSendError,
)
from shared.secrets import SecretValue


@register("mock")
class MockSmsGateway(SmsGateway):
    name = "mock"
    is_test_adapter = True
    sent: ClassVar[list[SmsSendRequest]] = []
    script: ClassVar[dict[str, str]] = {}

    def send(self, request: SmsSendRequest) -> SmsSendResult:
        behaviour = self.script.get(request.to)
        if behaviour == "rate_limit":
            raise RateLimitedError("mock throttled", retry_after_seconds=30)
        if behaviour == "timeout":
            raise UncertainSendError("mock read timeout")
        if behaviour == "reject":
            raise ProviderRejectedError("mock rejected recipient")
        if behaviour == "auth":
            raise InvalidCredentialsError("mock invalid api key")
        if behaviour == "dlt":
            raise InvalidTemplateError("mock DLT scrubbing failure")
        self.sent.append(request)
        return SmsSendResult(provider_message_id=f"mock-{uuid.uuid4().hex[:16]}")

    def verify_callback(self, headers: dict[str, str], raw_body: bytes, secret: SecretValue) -> None:
        signature = {k.lower(): v for k, v in headers.items()}.get("x-mock-signature", "")
        expected = hmac.new(secret.reveal().encode(), raw_body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            raise AuthenticationError("invalid SMS callback signature", code="sms_callback_signature_invalid")

    def parse_callback(self, raw_body: bytes) -> list[DeliveryReport]:
        data: Any = json.loads(raw_body)
        items = data if isinstance(data, list) else [data]
        return [
            DeliveryReport(
                provider_message_id=str(i["message_id"]),
                status=str(i["status"]).lower(),
                callback_ref=i.get("ref"),
                error_code=i.get("error_code"),
                timestamp=i.get("timestamp"),
            )
            for i in items
        ]

    @classmethod
    def reset(cls) -> None:
        cls.sent.clear()
        cls.script.clear()
