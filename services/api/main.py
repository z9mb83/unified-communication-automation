"""FastAPI application factory.

One image, three Cloud Run services selected by ``UCA_SERVICE_ROLE``:

* ``api``      – private; called by Google Sheets with user identity tokens.
* ``webhooks`` – public; only provider webhooks (signature-verified).
* ``workers``  – private; only Cloud Tasks with an OIDC token.

A role never mounts another role's routes, so e.g. the public webhook service
has no send endpoint at all.
"""

from __future__ import annotations

import os
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from services.api.routes import controls, email, sms, webhooks, whatsapp, workers
from shared.audit import correlation_id_var, get_logger
from shared.exceptions import AutomationError

log = get_logger("uca.api")


def create_app(role: str | None = None) -> FastAPI:
    role = (role or os.getenv("UCA_SERVICE_ROLE") or "api").lower()
    app = FastAPI(
        title=f"Unified Communication Automation ({role})",
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if role == "api" else None,
    )

    if role == "api":
        for module in (email, whatsapp, sms, controls):
            app.include_router(module.router)
    elif role == "webhooks":
        app.include_router(webhooks.router)
    elif role == "workers":
        app.include_router(workers.router)
    elif role == "all" and os.getenv("UCA_ENV", "local") in {"local", "test"}:
        for module in (email, whatsapp, sms, controls, webhooks, workers):
            app.include_router(module.router)
    else:
        raise RuntimeError(f"unknown or disallowed UCA_SERVICE_ROLE {role!r}")

    @app.middleware("http")
    async def correlation(request: Request, call_next):  # type: ignore[no-untyped-def]
        cid = request.headers.get("x-cloud-trace-context", "").split("/")[0] or uuid.uuid4().hex
        token = correlation_id_var.set(cid[:64])
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers["X-Correlation-Id"] = cid[:64]
        return response

    @app.exception_handler(AutomationError)
    async def automation_error(_request: Request, error: AutomationError) -> JSONResponse:
        log.warning("request_failed", extra={"uca": {"error_code": error.code}})
        return JSONResponse(status_code=error.http_status, content=error.to_dict())

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "role": role}

    return app


app = create_app() if os.getenv("UCA_CREATE_APP_ON_IMPORT", "1") == "1" else None
