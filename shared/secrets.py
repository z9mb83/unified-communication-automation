"""Secret resolution via Google Secret Manager.

Secrets are referenced as ``projects/<project>/secrets/<name>/versions/<version>``.
For local development only, ``env://VAR_NAME`` reads an environment variable;
this form is rejected in staging/production.

Values are cached in memory for a short TTL, are never logged and never
returned by any API endpoint. ``SecretValue`` hides itself from repr/str so an
accidental ``logger.info(secret)`` prints ``SecretValue(***)``.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from typing import Any

from shared.exceptions import ConfigurationError, InvalidCredentialsError


class SecretValue:
    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return "SecretValue(***)"

    __str__ = __repr__

    def __bool__(self) -> bool:
        return bool(self._value)


class SecretResolver:
    def __init__(
        self,
        env: str | None = None,
        ttl_seconds: int = 300,
        fetcher: Callable[[str], str] | None = None,
    ) -> None:
        self.env = (env or os.getenv("UCA_ENV") or "local").lower()
        self.ttl_seconds = ttl_seconds
        self._fetcher = fetcher
        self._cache: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()
        self._client: Any | None = None

    def _fetch_from_secret_manager(self, ref: str) -> str:
        if self._client is None:
            from google.cloud import secretmanager

            self._client = secretmanager.SecretManagerServiceClient()
        try:
            response = self._client.access_secret_version(request={"name": ref})
        except Exception as error:  # permission denied, not found ...
            # Error text from the API never contains the secret payload, but may
            # contain the resource name, which is not sensitive.
            raise InvalidCredentialsError(
                f"Cannot access secret {ref}: {type(error).__name__}", code="secret_unavailable"
            ) from error
        return str(response.payload.data.decode("utf-8")).strip()

    def get(self, ref: str) -> SecretValue:
        if not ref:
            raise ConfigurationError("secret reference is empty", code="secret_not_configured")
        if ref.startswith("env://"):
            if self.env in {"staging", "production"}:
                raise ConfigurationError("env:// secret references are not allowed in staging/production")
            value = os.getenv(ref[len("env://") :], "")
            if not value:
                raise ConfigurationError(f"environment variable for {ref} is not set", code="secret_not_configured")
            return SecretValue(value)
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(ref)
            if cached and now - cached[0] < self.ttl_seconds:
                return SecretValue(cached[1])
        fetch = self._fetcher or self._fetch_from_secret_manager
        value = fetch(ref)
        if not value:
            raise ConfigurationError(f"secret {ref} is empty", code="secret_not_configured")
        with self._lock:
            self._cache[ref] = (now, value)
        return SecretValue(value)

    def invalidate(self, ref: str) -> None:
        with self._lock:
            self._cache.pop(ref, None)


_resolver: SecretResolver | None = None


def get_resolver() -> SecretResolver:
    global _resolver
    if _resolver is None:
        _resolver = SecretResolver()
    return _resolver


def set_resolver(resolver: SecretResolver | None) -> None:
    global _resolver
    _resolver = resolver
