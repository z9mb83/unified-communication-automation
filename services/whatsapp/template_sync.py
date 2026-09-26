"""Synchronise message templates and phone numbers from each brand's own WABA.

Templates are stored per brand and tagged with the WABA they were read from.
Only templates that are APPROVED, supported, enabled and belong to the brand's
configured WABA are ever offered or sent.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from services.whatsapp.template_validator import TemplateSpec, parse_template
from shared.audit import audit
from shared.brand_registry import BrandConfig
from shared.exceptions import InvalidTemplateError, ValidationError
from shared.store import Store

if TYPE_CHECKING:
    from services.whatsapp.meta_client import MetaClient

TEMPLATES = "wa_templates"
BRAND_STATE = "wa_brand_state"

SHEET_COLUMNS = [
    "Brand ID",
    "WABA ID",
    "Phone Number ID",
    "Meta Template ID",
    "Template Name",
    "Language",
    "Category",
    "Approval Status",
    "Header Format",
    "Body Text",
    "Required Variables",
    "Button Definitions",
    "Last Synchronized",
    "Enabled",
]


def template_doc_id(brand_id: str, template_id: str) -> str:
    return f"{brand_id}:{template_id}"


class TemplateRepository:
    def __init__(self, store: Store) -> None:
        self.store = store

    def sync_brand(self, brand: BrandConfig, client: MetaClient, actor: str) -> dict[str, Any]:
        wa = brand.whatsapp
        if not wa.enabled:
            raise ValidationError(f"WhatsApp is not enabled for {brand.brand_id}", code="channel_disabled")
        now = datetime.now(UTC).isoformat()

        numbers = client.list_phone_numbers(wa.waba_id)
        waba_number_ids = {str(n.get("id")) for n in numbers}
        configured = wa.phone_number_ids()
        verified = sorted(configured & waba_number_ids)
        not_in_waba = sorted(configured - waba_number_ids)

        raw_templates = client.list_templates(wa.waba_id)
        seen: set[str] = set()
        counts = {"approved": 0, "other": 0, "unsupported": 0}
        for raw in raw_templates:
            spec = parse_template(raw)
            if not spec.template_id:
                continue
            doc_id = template_doc_id(brand.brand_id, spec.template_id)
            seen.add(doc_id)
            existing = self.store.get(TEMPLATES, doc_id) or {}
            enabled = existing.get("enabled", True)
            self.store.set(
                TEMPLATES,
                doc_id,
                {
                    "brand_id": brand.brand_id,
                    "waba_id": wa.waba_id,
                    "template_id": spec.template_id,
                    "name": spec.name,
                    "language": spec.language,
                    "category": spec.category,
                    "status": spec.status,
                    "parameter_format": spec.parameter_format,
                    "header_format": spec.header_format or "NONE",
                    "body_text": spec.body_text,
                    "required_variables": spec.required_variables,
                    "buttons": [b.__dict__ for b in spec.buttons],
                    "unsupported_reason": spec.unsupported_reason,
                    "raw": raw,
                    "enabled": bool(enabled),
                    "last_synchronized": now,
                    "present_in_waba": True,
                },
            )
            if spec.unsupported_reason:
                counts["unsupported"] += 1
            elif spec.status == "APPROVED":
                counts["approved"] += 1
            else:
                counts["other"] += 1
        # Templates deleted in Meta must stop being offered.
        for doc_id, doc in self.store.query(TEMPLATES, [("brand_id", "==", brand.brand_id)], limit=5000):
            if doc_id not in seen and doc.get("present_in_waba", True):
                self.store.set(
                    TEMPLATES,
                    doc_id,
                    {"present_in_waba": False, "status": "NOT_FOUND_IN_WABA", "last_synchronized": now},
                    merge=True,
                )
        self.store.set(
            BRAND_STATE,
            brand.brand_id,
            {
                "waba_id": wa.waba_id,
                "verified_phone_number_ids": verified,
                "last_sync": now,
                "synced_by": actor,
            },
        )
        result = {
            "brand_id": brand.brand_id,
            "waba_id": wa.waba_id,
            "templates": counts,
            "verified_phone_number_ids": verified,
            "phone_numbers_not_in_waba": not_in_waba,
        }
        audit(
            "wa_templates_synced",
            brand_id=brand.brand_id,
            channel="whatsapp",
            actor=actor,
            details=result,
            store=self.store,
        )
        return result

    def verified_phone_numbers(self, brand_id: str) -> set[str]:
        state = self.store.get(BRAND_STATE, brand_id) or {}
        return set(state.get("verified_phone_number_ids") or [])

    def approved_for_brand(self, brand: BrandConfig) -> list[dict[str, Any]]:
        docs = self.store.query(
            TEMPLATES, [("brand_id", "==", brand.brand_id), ("status", "==", "APPROVED")], limit=2000
        )
        return [
            d
            for _, d in docs
            if d.get("enabled")
            and d.get("present_in_waba", True)
            and not d.get("unsupported_reason")
            and d.get("waba_id") == brand.whatsapp.waba_id
        ]

    def get_sendable(self, brand: BrandConfig, template_id: str, language: str | None = None) -> TemplateSpec:
        doc = self.store.get(TEMPLATES, template_doc_id(brand.brand_id, template_id))
        if not doc:
            raise InvalidTemplateError(
                f"template {template_id} is not registered for brand {brand.brand_id}", code="template_not_for_brand"
            )
        if doc.get("brand_id") != brand.brand_id or doc.get("waba_id") != brand.whatsapp.waba_id:
            raise InvalidTemplateError("template belongs to another brand/WABA", code="template_not_for_brand")
        if not doc.get("enabled") or not doc.get("present_in_waba", True):
            raise InvalidTemplateError(
                "template is disabled or no longer present in the WABA", code="template_disabled"
            )
        if language and doc.get("language") != language:
            raise InvalidTemplateError(
                f"template language is {doc.get('language')}, not {language}", code="template_language_mismatch"
            )
        if str(doc.get("status", "")).upper() != "APPROVED":
            # Status may have been changed by a template-status webhook after sync.
            raise InvalidTemplateError(f"template status is {doc.get('status')}", code="template_not_approved")
        spec = parse_template(doc["raw"])
        if not spec.is_sendable:
            raise InvalidTemplateError(f"template status is {spec.status}", code="template_not_approved")
        return spec

    def set_enabled(self, brand_id: str, template_id: str, enabled: bool, actor: str) -> None:
        self.store.set(
            TEMPLATES,
            template_doc_id(brand_id, template_id),
            {"enabled": enabled, "enabled_changed_by": actor},
            merge=True,
        )

    @staticmethod
    def to_sheet_row(doc: dict[str, Any], phone_number_id: str) -> list[Any]:
        return [
            doc.get("brand_id"),
            doc.get("waba_id"),
            phone_number_id,
            doc.get("template_id"),
            doc.get("name"),
            doc.get("language"),
            doc.get("category"),
            doc.get("status"),
            doc.get("header_format"),
            doc.get("body_text"),
            ", ".join(doc.get("required_variables") or []),
            json.dumps(
                [{k: b.get(k) for k in ("index", "type", "text", "url", "variable")} for b in doc.get("buttons") or []]
            ),
            doc.get("last_synchronized"),
            "Yes" if doc.get("enabled") else "No",
        ]
