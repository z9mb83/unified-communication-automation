"""Request/response models for the Sheets-facing API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class RecipientIn(BaseModel):
    row_number: int = Field(ge=1)
    contact_id: str = ""
    row_brand_id: str = ""
    name: str = ""
    email: str = ""
    phone: str = ""
    variables: dict[str, str] | list[str] = Field(default_factory=dict)


class SelectionBase(BaseModel):
    spreadsheet_id: str = Field(min_length=10, max_length=128)
    tab: str = Field(min_length=1, max_length=200)
    brand_id: str = Field(min_length=2, max_length=40)
    recipients: list[RecipientIn] = Field(min_length=1, max_length=2000)

    @field_validator("recipients")
    @classmethod
    def _rows_unique(cls, value: list[RecipientIn]) -> list[RecipientIn]:
        # Rows are deduplicated client-side too; the server re-checks.
        seen: set[int] = set()
        out: list[RecipientIn] = []
        for recipient in value:
            if recipient.row_number not in seen:
                seen.add(recipient.row_number)
                out.append(recipient)
        return out


class WhatsAppPreviewRequest(SelectionBase):
    template_id: str = Field(min_length=1, max_length=64)
    language: str = Field(min_length=2, max_length=16)
    phone_number_id: str = ""


class WhatsAppSendRequest(WhatsAppPreviewRequest):
    submission_id: str = Field(min_length=16, max_length=128)
    confirmation_hash: str = Field(min_length=64, max_length=64)


class SmsPreviewRequest(SelectionBase):
    template_id: str = Field(min_length=1, max_length=64)


class SmsSendRequest(SmsPreviewRequest):
    submission_id: str = Field(min_length=16, max_length=128)
    confirmation_hash: str = Field(min_length=64, max_length=64)


class EmailPreviewRequest(SelectionBase):
    pass


class EmailSendRequest(SelectionBase):
    submission_id: str = Field(min_length=16, max_length=128)
    confirmation_hash: str = Field(min_length=64, max_length=64)


class ControlRequest(BaseModel):
    brand_id: str
    reason: str = Field(default="", max_length=300)


class GlobalControlRequest(BaseModel):
    reason: str = Field(default="", max_length=300)


class ConsentImportItem(BaseModel):
    row_number: int
    phone: str = ""
    email: str = ""
    consent: str
    consented_at: str
    evidence: str = Field(min_length=3, max_length=500)


class ConsentImportRequest(BaseModel):
    spreadsheet_id: str
    tab: str
    brand_id: str
    channel: str
    items: list[ConsentImportItem] = Field(min_length=1, max_length=2000)


class TemplateToggleRequest(BaseModel):
    brand_id: str
    template_id: str
    enabled: bool


class PreviewResponse(BaseModel):
    brand_id: str
    channel: str
    template: dict[str, Any] | None = None
    eligible_count: int
    ineligible: list[dict[str, Any]]
    eligible: list[dict[str, Any]]
    confirmation_hash: str
    warnings: list[str] = Field(default_factory=list)
