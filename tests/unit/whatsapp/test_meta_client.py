from typing import Any

import pytest
import requests

from services.whatsapp.meta_client import MetaClient
from shared.exceptions import (
    InvalidCredentialsError,
    InvalidTemplateError,
    ProviderRejectedError,
    RateLimitedError,
    TransientProviderError,
    UncertainSendError,
)
from shared.secrets import SecretValue


class FakeResponse:
    def __init__(self, status: int, payload: Any) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def _next(self, **kw: Any) -> Any:
        self.calls.append(kw)
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def post(self, url: str, **kw: Any) -> Any:
        return self._next(url=url, **kw)

    def get(self, url: str, **kw: Any) -> Any:
        return self._next(url=url, **kw)


def client(responses: list[Any]) -> tuple[MetaClient, FakeSession]:
    session = FakeSession(responses)
    return MetaClient(lambda: SecretValue("EAAsecret"), api_version="v26.0", session=session), session  # type: ignore[arg-type]


def send(c: MetaClient) -> dict[str, Any]:
    return c.send_template(
        phone_number_id="2001", to="919", template_name="t", language="en", components=[], callback_data="m_abc"
    )


def test_success_payload_and_headers():
    c, s = client(
        [
            FakeResponse(
                200,
                {
                    "messaging_product": "whatsapp",
                    "contacts": [{"wa_id": "919"}],
                    "messages": [{"id": "wamid.X", "message_status": "accepted"}],
                },
            )
        ]
    )
    assert send(c)["wamid"] == "wamid.X"
    call = s.calls[0]
    assert call["url"] == "https://graph.facebook.com/v26.0/2001/messages"
    assert call["headers"]["Authorization"] == "Bearer EAAsecret"
    assert call["json"]["biz_opaque_callback_data"] == "m_abc"
    assert "EAAsecret" not in call["url"]


@pytest.mark.parametrize(
    ("status", "code", "exc"),
    [
        (401, 190, InvalidCredentialsError),
        (400, 130429, RateLimitedError),
        (400, 80007, RateLimitedError),
        (400, 131056, RateLimitedError),
        (404, 132001, InvalidTemplateError),
        (400, 132000, InvalidTemplateError),
        (400, 131026, ProviderRejectedError),
        (400, 100, ProviderRejectedError),
        (500, 131000, UncertainSendError),
        (503, None, UncertainSendError),
    ],
)
def test_error_classification(status, code, exc):
    payload = {"error": {"message": "m", "type": "OAuthException", "code": code, "fbtrace_id": "T"}} if code else {}
    c, _ = client([FakeResponse(status, payload)])
    with pytest.raises(exc):
        send(c)


def test_timeouts_are_classified_by_whether_request_was_sent():
    c, _ = client([requests.ConnectTimeout("x")])
    with pytest.raises(TransientProviderError):
        send(c)
    c, _ = client([requests.ReadTimeout("x")])
    with pytest.raises(UncertainSendError):
        send(c)
    c, _ = client([requests.ConnectionError("reset")])
    with pytest.raises(UncertainSendError):
        send(c)


def test_success_without_message_id_is_uncertain():
    c, _ = client([FakeResponse(200, ValueError("not json"))])
    with pytest.raises(UncertainSendError):
        send(c)


def test_template_paging():
    c, s = client(
        [
            FakeResponse(
                200, {"data": [{"id": "1"}], "paging": {"next": "https://graph.facebook.com/v26.0/next?after=x"}}
            ),
            FakeResponse(200, {"data": [{"id": "2"}]}),
        ]
    )
    assert [t["id"] for t in c.list_templates("111")] == ["1", "2"]
    assert s.calls[0]["url"].endswith("/v26.0/111/message_templates")
    assert s.calls[1]["params"] is None


def test_read_errors_are_transient_not_uncertain():
    c, _ = client([FakeResponse(500, {"error": {"code": 2}})])
    with pytest.raises(TransientProviderError):
        c.list_phone_numbers("111")
