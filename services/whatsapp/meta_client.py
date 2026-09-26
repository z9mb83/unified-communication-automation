"""Thin, strict client for the Meta WhatsApp Cloud API (Graph API).

* Graph API version comes from ``channels.yaml`` (``graph_api_version``) and is
  validated; it defaults to the current version at build time (v26.0, released
  2026-07-29 per Meta's version table) and should be reviewed at each Meta
  release. Nothing else hard-codes a version.
* The access token is fetched from Secret Manager per call via ``token_provider``
  and is sent only in the Authorization header — never in a URL or a log line.
* Send requests are never retried inside this client. The caller decides based
  on the error class; ambiguous outcomes raise ``UncertainSendError``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import requests

from services.whatsapp.errors import classify
from shared.exceptions import TransientProviderError, UncertainSendError
from shared.secrets import SecretValue

TEMPLATE_FIELDS = "id,name,status,category,language,components,parameter_format,rejected_reason,quality_score"


class MetaClient:
    def __init__(
        self,
        token_provider: Callable[[], SecretValue],
        *,
        api_version: str,
        base_url: str = "https://graph.facebook.com",
        connect_timeout: float = 5.0,
        read_timeout: float = 20.0,
        session: requests.Session | None = None,
    ) -> None:
        self._token_provider = token_provider
        self.api_version = api_version
        self.base_url = base_url.rstrip("/")
        self.timeout = (connect_timeout, read_timeout)
        self.session = session or requests.Session()

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{self.api_version}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token_provider().reveal()}", "Content-Type": "application/json"}

    # ---- reads (safe to retry) ------------------------------------------------------------

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = self.session.get(url, params=params, headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as error:
            raise TransientProviderError(f"Meta API unreachable: {type(error).__name__}") from error
        payload = _json(response)
        if response.status_code >= 400:
            raise classify(response.status_code, payload, is_send=False)
        return payload

    def _paged(self, path: str, params: dict[str, Any]) -> Iterator[dict[str, Any]]:
        url: str | None = self._url(path)
        query: dict[str, Any] | None = params
        pages = 0
        while url and pages < 50:
            payload = self._get(url, query)
            yield from payload.get("data", [])
            url = (payload.get("paging") or {}).get("next")
            query = None  # the 'next' URL already carries the cursor and fields
            pages += 1

    def list_templates(self, waba_id: str) -> list[dict[str, Any]]:
        return list(self._paged(f"{waba_id}/message_templates", {"fields": TEMPLATE_FIELDS, "limit": 100}))

    def list_phone_numbers(self, waba_id: str) -> list[dict[str, Any]]:
        return list(
            self._paged(
                f"{waba_id}/phone_numbers",
                {"fields": "id,display_phone_number,verified_name,quality_rating,code_verification_status"},
            )
        )

    # ---- send (never retried here) -----------------------------------------------------------

    def send_template(
        self,
        *,
        phone_number_id: str,
        to: str,
        template_name: str,
        language: str,
        components: list[dict[str, Any]],
        callback_data: str,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "template",
            "template": {"name": template_name, "language": {"code": language}},
            # Echoed back in status webhooks: lets reconciliation match an
            # uncertain send to its record without resending.
            "biz_opaque_callback_data": callback_data[:512],
        }
        if components:
            body["template"]["components"] = components
        try:
            response = self.session.post(
                self._url(f"{phone_number_id}/messages"), json=body, headers=self._headers(), timeout=self.timeout
            )
        except requests.ConnectTimeout as error:
            # The TCP connection was never established: Meta cannot have received it.
            raise TransientProviderError("Meta API connect timeout (request not sent)") from error
        except (requests.ReadTimeout, requests.ConnectionError, requests.exceptions.ChunkedEncodingError) as error:
            raise UncertainSendError(
                f"No definitive response from Meta ({type(error).__name__}); message may have been accepted"
            ) from error
        except requests.RequestException as error:
            raise UncertainSendError(f"Meta API request failed ambiguously: {type(error).__name__}") from error
        payload = _json(response)
        if response.status_code >= 400:
            raise classify(response.status_code, payload, is_send=True)
        messages = payload.get("messages") or []
        if not messages or not messages[0].get("id"):
            raise UncertainSendError(
                "Meta returned success without a message id", provider_response={"keys": list(payload)}
            )
        contacts = payload.get("contacts") or [{}]
        return {
            "wamid": messages[0]["id"],
            "message_status": messages[0].get("message_status"),
            "wa_id": contacts[0].get("wa_id"),
        }


def _json(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        # Non-JSON: callers treat a missing message id on a send as uncertain.
        return {}
    return data if isinstance(data, dict) else {"data": data}
