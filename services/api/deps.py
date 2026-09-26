"""Dependency container shared by the API, webhook and worker roles.

Tests build an ``AppContext`` with an in-memory store, inline queue and fake
provider factories; production builds it from environment + Secret Manager.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from shared.brand_registry import BrandConfig, BrandRegistry, load_brand_registry
from shared.config import ChannelsConfig, Settings, load_channels, load_settings
from shared.job_manager import JobManager, TaskQueue, get_queue
from shared.sheet_registry import SheetRegistry, load_sheet_registry
from shared.store import Store, get_store


@dataclass
class AppContext:
    settings: Settings
    store: Store
    queue: TaskQueue
    brands: BrandRegistry
    sheets: SheetRegistry
    channels: ChannelsConfig
    access: dict[str, Any]
    meta_client_factory: Callable[[BrandConfig], Any] | None = None
    sms_gateway_factory: Callable[[BrandConfig], Any] | None = None
    email_adapter_factory: Callable[[], Any] | None = None
    secret_getter: Callable[[str], str] | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def jobs(self) -> JobManager:
        return JobManager(self.store, self.queue)

    def secret(self, ref: str) -> str:
        if self.secret_getter is not None:
            return self.secret_getter(ref)
        from shared.secrets import get_resolver

        return get_resolver().get(ref).reveal()

    def email_adapter(self) -> Any:
        if self.email_adapter_factory is not None:
            return self.email_adapter_factory()
        cached = self.extras.get("email_adapter")
        if cached is None:
            from services.email.compat.adapter import LegacyEmailApp

            cached = LegacyEmailApp(self.settings.email_service_dir)
            self.extras["email_adapter"] = cached
        return cached


_context: AppContext | None = None


def build_context() -> AppContext:
    from services.api.authz import load_access

    settings = load_settings()
    return AppContext(
        settings=settings,
        store=get_store(),
        queue=get_queue(),
        brands=load_brand_registry(settings),
        sheets=load_sheet_registry(settings),
        channels=load_channels(settings),
        access=load_access(settings),
    )


def get_context() -> AppContext:
    global _context
    if _context is None:
        _context = build_context()
    return _context


def set_context(context: AppContext | None) -> None:
    global _context
    _context = context
