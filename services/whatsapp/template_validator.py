"""Parse a Meta template definition into a variable spec and validate values.

Variable IDs are stable strings used end-to-end (Sheets sidebar mapping,
message records, renderer):

* ``header.1`` / ``header.<name>``  – text header parameter
* ``header.media_link``              – IMAGE / VIDEO / DOCUMENT header (https URL)
* ``body.1`` … ``body.N`` or ``body.<name>`` – body parameters
* ``button.<index>.1``               – dynamic suffix of a URL button
* ``button.<index>.coupon_code``     – COPY_CODE button value
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from shared.exceptions import InvalidTemplateError, ValidationError

POSITIONAL_RE = re.compile(r"\{\{\s*(\d+)\s*\}\}")
NAMED_RE = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")
MEDIA_FORMATS = {"IMAGE", "VIDEO", "DOCUMENT"}
SUPPORTED_BUTTONS = {"QUICK_REPLY", "URL", "PHONE_NUMBER", "COPY_CODE"}
MAX_BODY_PARAM = 1024
MAX_HEADER_TEXT = 60
MAX_COUPON = 15


@dataclass
class ButtonSpec:
    index: int
    type: str
    text: str = ""
    url: str = ""
    variable: str | None = None


@dataclass
class TemplateSpec:
    template_id: str
    name: str
    language: str
    category: str
    status: str
    parameter_format: str
    header_format: str | None
    header_text: str
    body_text: str
    header_variables: list[str] = field(default_factory=list)
    body_variables: list[str] = field(default_factory=list)
    buttons: list[ButtonSpec] = field(default_factory=list)
    unsupported_reason: str | None = None

    @property
    def required_variables(self) -> list[str]:
        out = list(self.header_variables) + list(self.body_variables)
        out += [b.variable for b in self.buttons if b.variable]
        return out

    @property
    def is_sendable(self) -> bool:
        return self.status == "APPROVED" and self.unsupported_reason is None


def _vars(text: str, prefix: str, named: bool) -> list[str]:
    if named:
        names = list(dict.fromkeys(NAMED_RE.findall(text or "")))
        return [f"{prefix}.{n}" for n in names]
    numbers = sorted({int(n) for n in POSITIONAL_RE.findall(text or "")})
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        raise InvalidTemplateError(f"{prefix} placeholders are not sequential: {numbers}")
    return [f"{prefix}.{n}" for n in numbers]


def parse_template(raw: dict[str, Any]) -> TemplateSpec:
    parameter_format = str(raw.get("parameter_format") or "POSITIONAL").upper()
    named = parameter_format == "NAMED"
    spec = TemplateSpec(
        template_id=str(raw.get("id", "")),
        name=str(raw.get("name", "")),
        language=str(raw.get("language", "")),
        category=str(raw.get("category", "")),
        status=str(raw.get("status", "")).upper(),
        parameter_format=parameter_format,
        header_format=None,
        header_text="",
        body_text="",
    )
    for component in raw.get("components") or []:
        ctype = str(component.get("type", "")).upper()
        if ctype == "HEADER":
            fmt = str(component.get("format", "TEXT")).upper()
            spec.header_format = fmt
            if fmt == "TEXT":
                spec.header_text = str(component.get("text", ""))
                spec.header_variables = _vars(spec.header_text, "header", named)
            elif fmt in MEDIA_FORMATS:
                spec.header_variables = ["header.media_link"]
            else:
                spec.unsupported_reason = f"header format {fmt} is not supported"
        elif ctype == "BODY":
            spec.body_text = str(component.get("text", ""))
            spec.body_variables = _vars(spec.body_text, "body", named)
        elif ctype == "BUTTONS":
            for index, button in enumerate(component.get("buttons") or []):
                btype = str(button.get("type", "")).upper()
                b = ButtonSpec(
                    index=index, type=btype, text=str(button.get("text", "")), url=str(button.get("url", ""))
                )
                if btype not in SUPPORTED_BUTTONS:
                    spec.unsupported_reason = f"button type {btype} is not supported"
                elif btype == "URL" and ("{{" in b.url):
                    b.variable = f"button.{index}.1"
                elif btype == "COPY_CODE":
                    b.variable = f"button.{index}.coupon_code"
                spec.buttons.append(b)
    return spec


def _check_text_param(var: str, value: str, limit: int) -> None:
    if "\n" in value or "\t" in value:
        raise ValidationError(
            f"{var}: new-line and tab characters are not allowed in template parameters",
            code="invalid_template_variable",
        )
    if "     " in value:
        raise ValidationError(
            f"{var}: more than 4 consecutive spaces are not allowed", code="invalid_template_variable"
        )
    if len(value) > limit:
        raise ValidationError(f"{var}: longer than {limit} characters", code="invalid_template_variable")


def validate_values(spec: TemplateSpec, values: dict[str, Any]) -> dict[str, str]:
    """Return cleaned values for exactly the required variables, or raise ValidationError."""
    if not spec.is_sendable:
        raise InvalidTemplateError(
            f"template {spec.name}/{spec.language} is not sendable "
            f"(status={spec.status}{', ' + spec.unsupported_reason if spec.unsupported_reason else ''})"
        )
    cleaned: dict[str, str] = {}
    missing = []
    for var in spec.required_variables:
        raw = values.get(var)
        text = "" if raw is None else str(raw).strip()
        if not text:
            missing.append(var)
            continue
        if var == "header.media_link":
            parsed = urlparse(text)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValidationError(f"{var}: must be an https URL", code="invalid_template_variable")
        elif var.startswith("header."):
            _check_text_param(var, text, MAX_HEADER_TEXT)
        elif var.startswith("body."):
            _check_text_param(var, text, MAX_BODY_PARAM)
        elif var.endswith(".coupon_code"):
            if len(text) > MAX_COUPON or " " in text:
                raise ValidationError(
                    f"{var}: coupon code must be <= {MAX_COUPON} chars without spaces", code="invalid_template_variable"
                )
        elif var.startswith("button."):
            if any(ch.isspace() for ch in text) or len(text) > 2000:
                raise ValidationError(f"{var}: URL suffix may not contain spaces", code="invalid_template_variable")
        cleaned[var] = text
    if missing:
        raise ValidationError(
            f"missing template variables: {', '.join(missing)}",
            code="missing_template_variables",
            details={"missing": missing},
        )
    unknown = sorted({k for k, v in values.items() if str(v or "").strip()} - set(spec.required_variables))
    if unknown:
        raise ValidationError(
            f"unexpected variables for this template: {', '.join(unknown)}",
            code="unexpected_template_variables",
            details={"unexpected": unknown},
        )
    return cleaned
