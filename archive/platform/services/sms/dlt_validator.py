"""Indian TRAI DLT validation for registered SMS templates.

The registered template text is the only allowed wording. Rendering replaces
each ``{#var#}`` placeholder in order with a validated value and nothing else;
the result is then re-checked against a regex built from the registered text,
so any drift (extra words, changed punctuation, AI rewriting) is rejected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from shared.brand_registry import SmsBrandConfig, SmsTemplate
from shared.exceptions import InvalidTemplateError, ValidationError

PLACEHOLDER = "{#var#}"
DLT_ID_RE = re.compile(r"^\d{12,25}$")
HEADER_ALPHA_RE = re.compile(r"^[A-Z]{6}$")
HEADER_NUMERIC_RE = re.compile(r"^\d{6}$")
GSM7 = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§"
    "¿abcdefghijklmnopqrstuvwxyzäöñüà^{}\\[~]|€"
)


@dataclass(frozen=True)
class RenderedSms:
    text: str
    encoding: str
    segments: int


def variable_count(template: SmsTemplate) -> int:
    return template.content.count(PLACEHOLDER)


def template_regex(content: str, max_len: int) -> re.Pattern[str]:
    parts = [re.escape(p) for p in content.split(PLACEHOLDER)]
    return re.compile("^" + f"(.{{1,{max_len}}})".join(parts) + "$", re.DOTALL)


def validate_brand_dlt(config: SmsBrandConfig) -> list[str]:
    """Static checks on a brand's DLT registration data. Returns a list of problems."""
    problems: list[str] = []
    if not DLT_ID_RE.match(config.dlt_principal_entity_id or ""):
        problems.append("dlt_principal_entity_id must be the numeric DLT Principal Entity ID")
    if not config.sender_headers:
        problems.append("at least one registered sender header is required")
    seen: set[str] = set()
    for t in config.templates:
        if t.template_id in seen:
            problems.append(f"duplicate DLT template id {t.template_id}")
        seen.add(t.template_id)
        if not DLT_ID_RE.match(t.template_id):
            problems.append(f"{t.name}: DLT template id must be numeric")
        if t.sender_header not in config.sender_headers:
            problems.append(f"{t.name}: header {t.sender_header} is not registered for this brand")
        header_ok = HEADER_NUMERIC_RE if t.content_type == "promotional" else HEADER_ALPHA_RE
        if not header_ok.match(t.sender_header):
            problems.append(f"{t.name}: header {t.sender_header!r} invalid for {t.content_type} messages")
        if "{#" in t.content.replace(PLACEHOLDER, ""):
            problems.append(f"{t.name}: malformed placeholder; DLT uses {PLACEHOLDER}")
        if not t.content.strip():
            problems.append(f"{t.name}: empty content")
    return problems


def render(template: SmsTemplate, values: list[str], max_variable_length: int = 30) -> RenderedSms:
    if not template.enabled:
        raise InvalidTemplateError(f"SMS template {template.name} is disabled", code="template_disabled")
    expected = variable_count(template)
    if len(values) != expected:
        raise ValidationError(
            f"template {template.name} needs {expected} variable(s), got {len(values)}",
            code="sms_variable_count_mismatch",
        )
    cleaned: list[str] = []
    for index, raw in enumerate(values, start=1):
        value = str(raw or "").strip()
        if not value:
            raise ValidationError(f"variable {index} is blank", code="sms_variable_blank")
        if len(value) > max_variable_length:
            raise ValidationError(
                f"variable {index} exceeds {max_variable_length} characters", code="sms_variable_too_long"
            )
        if "{#" in value or "#}" in value or "\n" in value or "\r" in value:
            raise ValidationError(f"variable {index} contains forbidden characters", code="sms_variable_invalid")
        cleaned.append(value)
    parts = template.content.split(PLACEHOLDER)
    text = parts[0] + "".join(v + p for v, p in zip(cleaned, parts[1:], strict=True))
    if not template_regex(template.content, max_variable_length).match(text):
        raise InvalidTemplateError("rendered text does not match the registered DLT template", code="dlt_mismatch")
    unicode = any(ch not in GSM7 for ch in text)
    single, multi = (70, 67) if unicode else (160, 153)
    segments = 1 if len(text) <= single else -(-len(text) // multi)
    return RenderedSms(text=text, encoding="UCS-2" if unicode else "GSM-7", segments=segments)


def find_template(config: SmsBrandConfig, template_id: str) -> SmsTemplate:
    for t in config.templates:
        if t.template_id == template_id:
            return t
    raise InvalidTemplateError(
        f"DLT template {template_id} is not registered for this brand", code="template_not_for_brand"
    )
