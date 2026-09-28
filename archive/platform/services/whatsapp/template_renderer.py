"""Build the ``template.components`` array for a Cloud API template send."""

from __future__ import annotations

from typing import Any

from services.whatsapp.template_validator import TemplateSpec, validate_values


def _text_param(spec: TemplateSpec, var: str, value: str) -> dict[str, Any]:
    param: dict[str, Any] = {"type": "text", "text": value}
    if spec.parameter_format == "NAMED":
        param["parameter_name"] = var.split(".", 1)[1]
    return param


def render_components(spec: TemplateSpec, values: dict[str, Any]) -> list[dict[str, Any]]:
    cleaned = validate_values(spec, values)
    components: list[dict[str, Any]] = []
    if spec.header_variables:
        if spec.header_format in {"IMAGE", "VIDEO", "DOCUMENT"}:
            media_type = spec.header_format.lower()
            components.append(
                {
                    "type": "header",
                    "parameters": [{"type": media_type, media_type: {"link": cleaned["header.media_link"]}}],
                }
            )
        else:
            components.append(
                {"type": "header", "parameters": [_text_param(spec, v, cleaned[v]) for v in spec.header_variables]}
            )
    if spec.body_variables:
        components.append(
            {"type": "body", "parameters": [_text_param(spec, v, cleaned[v]) for v in spec.body_variables]}
        )
    for button in spec.buttons:
        if not button.variable:
            continue
        if button.type == "URL":
            components.append(
                {
                    "type": "button",
                    "sub_type": "url",
                    "index": str(button.index),
                    "parameters": [{"type": "text", "text": cleaned[button.variable]}],
                }
            )
        elif button.type == "COPY_CODE":
            components.append(
                {
                    "type": "button",
                    "sub_type": "copy_code",
                    "index": str(button.index),
                    "parameters": [{"type": "coupon_code", "coupon_code": cleaned[button.variable]}],
                }
            )
    return components


def preview_text(spec: TemplateSpec, values: dict[str, Any]) -> str:
    """Human preview for the confirmation dialog (not sent anywhere)."""
    text = spec.body_text
    for var in spec.body_variables:
        key = var.split(".", 1)[1]
        text = text.replace("{{" + key + "}}", str(values.get(var, "")))
    return text
