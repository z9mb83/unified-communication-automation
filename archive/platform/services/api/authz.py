"""Authentication (Google-signed ID tokens) and per-action, per-brand authorisation.

Callers:
* Google Sheets (Apps Script) sends ``ScriptApp.getIdentityToken()`` — an ID
  token for the signed-in user whose audience is the Apps Script project's
  OAuth client ID. That client ID is listed in ``UCA_ALLOWED_AUDIENCES`` and
  added to the Cloud Run service as a custom audience.
* Cloud Tasks calls workers with an OIDC token for the dedicated invoker
  service account (audience = worker base URL).

Knowing the spreadsheet is not enough: every user must be listed in
``access.yaml`` with a role per brand; admin-only actions require ``admin``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.config import Settings, config_file, load_yaml
from shared.exceptions import AuthenticationError, AuthorizationError, ConfigurationError

ROLE_RANK = {"viewer": 1, "operator": 2, "admin": 3}

ACTION_ROLES: dict[str, str] = {
    "view": "viewer",
    "validate_config": "viewer",
    "preview": "operator",
    "send_selected": "operator",
    "start": "operator",
    "stop": "operator",
    "run_existing_email": "admin",  # runs the scheduled job for ALL brands
    "cancel_job": "operator",
    "emergency_stop": "operator",
    "stop_all": "operator",
    "start_all": "admin",
    "release_emergency": "admin",
    "sync_templates": "admin",
    "import_consent": "admin",
    "set_template_enabled": "admin",
}


@dataclass(frozen=True)
class Principal:
    email: str
    is_admin: bool
    brand_roles: dict[str, str]
    kind: str = "user"

    def role_for(self, brand_id: str) -> str | None:
        if self.is_admin:
            return "admin"
        return self.brand_roles.get(brand_id)

    def can(self, action: str, brand_id: str | None) -> bool:
        needed = ACTION_ROLES.get(action)
        if needed is None:
            return False
        if brand_id is None:
            # Global actions: admin always; operator-level global actions need
            # operator on at least one brand.
            if self.is_admin:
                return True
            best = max((ROLE_RANK.get(r, 0) for r in self.brand_roles.values()), default=0)
            return best >= ROLE_RANK[needed] and needed != "admin"
        role = self.role_for(brand_id)
        return role is not None and ROLE_RANK.get(role, 0) >= ROLE_RANK[needed]

    def require(self, action: str, brand_id: str | None = None) -> None:
        if not self.can(action, brand_id):
            scope = f" for brand {brand_id}" if brand_id else ""
            raise AuthorizationError(f"{self.email} is not allowed to {action}{scope}")

    def brands(self, all_brand_ids: list[str]) -> list[str]:
        return list(all_brand_ids) if self.is_admin else [b for b in all_brand_ids if b in self.brand_roles]


def load_access(settings: Settings) -> dict[str, Any]:
    try:
        path = config_file("access", settings)
    except ConfigurationError:
        if settings.env in {"local", "test"}:
            return {"users": {}}
        raise
    data = load_yaml(Path(path))
    users = data.get("users") or {}
    for email, body in users.items():
        for brand, role in ((body or {}).get("brands") or {}).items():
            if role not in ROLE_RANK:
                raise ConfigurationError(f"access.yaml: {email}/{brand}: unknown role {role}")
    return {"users": {str(k).lower(): v or {} for k, v in users.items()}}


def principal_for(email: str, access: dict[str, Any]) -> Principal:
    body = access.get("users", {}).get(email.lower())
    if body is None:
        raise AuthorizationError(f"{email} is not an authorised user of this automation", code="user_not_allowed")
    return Principal(
        email=email.lower(),
        is_admin=bool(body.get("admin")),
        brand_roles={str(k): str(v) for k, v in (body.get("brands") or {}).items()},
    )


IdTokenVerifier = Callable[[str], dict[str, Any]]


def google_id_token_verifier(settings: Settings) -> IdTokenVerifier:
    def verify(token: str) -> dict[str, Any]:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        try:
            claims = dict(id_token.verify_token(token, google_requests.Request(), audience=None))
        except Exception as error:
            raise AuthenticationError(f"invalid identity token: {type(error).__name__}") from error
        return claims

    return verify


def authenticate_user(
    authorization: str | None,
    settings: Settings,
    access: dict[str, Any],
    verifier: IdTokenVerifier | None,
    test_user: str | None = None,
) -> Principal:
    if settings.auth_disabled_for_local and settings.env in {"local", "test"} and test_user:
        return principal_for(test_user, access)
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("missing bearer identity token")
    claims = (verifier or google_id_token_verifier(settings))(authorization[len("Bearer ") :].strip())
    audiences = claims.get("aud")
    aud_list = audiences if isinstance(audiences, list) else [audiences]
    if not settings.allowed_audiences or not any(a in settings.allowed_audiences for a in aud_list):
        raise AuthenticationError("identity token audience is not allowed", code="bad_audience")
    if claims.get("iss") not in settings.allowed_issuers:
        raise AuthenticationError("identity token issuer is not allowed", code="bad_issuer")
    if not claims.get("email") or not claims.get("email_verified", False):
        raise AuthenticationError("identity token has no verified email", code="unverified_email")
    return principal_for(str(claims["email"]), access)


def authenticate_worker(authorization: str | None, settings: Settings, verifier: IdTokenVerifier | None) -> str:
    if settings.auth_disabled_for_local and settings.env in {"local", "test"}:
        return "local-worker"
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("missing worker OIDC token")
    claims = (verifier or google_id_token_verifier(settings))(authorization[len("Bearer ") :].strip())
    if claims.get("aud") != settings.worker_base_url:
        raise AuthenticationError("worker token audience mismatch", code="bad_audience")
    email = str(claims.get("email", "")).lower()
    if not email or email not in {c.lower() for c in settings.worker_allowed_callers}:
        raise AuthorizationError("caller is not an allowed task invoker", code="worker_caller_not_allowed")
    return email
