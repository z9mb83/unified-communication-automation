"""FastAPI dependencies: context, authenticated principal, replay protection."""

from __future__ import annotations

from fastapi import Depends, Header

from services.api.authz import Principal, authenticate_user, authenticate_worker
from services.api.deps import AppContext, get_context
from shared.idempotency import reserve_request


def context_dep() -> AppContext:
    return get_context()


def principal_dep(
    ctx: AppContext = Depends(context_dep),
    authorization: str | None = Header(default=None),
    x_uca_test_user: str | None = Header(default=None),
) -> Principal:
    verifier = ctx.extras.get("id_token_verifier")
    return authenticate_user(authorization, ctx.settings, ctx.access, verifier, test_user=x_uca_test_user)


def mutating_principal_dep(
    ctx: AppContext = Depends(context_dep),
    principal: Principal = Depends(principal_dep),
    x_uca_request_id: str | None = Header(default=None),
    x_uca_timestamp: str | None = Header(default=None),
) -> Principal:
    """Authenticated caller + single-use request ID within the allowed clock window."""
    reserve_request(
        ctx.store, x_uca_request_id or "", x_uca_timestamp or "", principal.email, ctx.settings.request_max_age_seconds
    )
    return principal


def worker_dep(
    ctx: AppContext = Depends(context_dep),
    authorization: str | None = Header(default=None),
) -> str:
    return authenticate_worker(authorization, ctx.settings, ctx.extras.get("id_token_verifier"))
