import pytest

from services.whatsapp.template_renderer import render_components
from services.whatsapp.template_validator import parse_template, validate_values
from shared.exceptions import InvalidTemplateError, ValidationError
from tests.conftest import TEMPLATE_SHAADI


def test_parse_positional_template():
    spec = parse_template(TEMPLATE_SHAADI)
    assert spec.required_variables == ["header.1", "body.1", "body.2", "button.0.1"]
    assert spec.is_sendable


def test_render_components_shape():
    spec = parse_template(TEMPLATE_SHAADI)
    comps = render_components(spec, {"header.1": "Asha", "body.1": "Asha", "body.2": "Delhi", "button.0.1": "abc123"})
    assert comps[0] == {"type": "header", "parameters": [{"type": "text", "text": "Asha"}]}
    assert comps[1]["parameters"][1] == {"type": "text", "text": "Delhi"}
    assert comps[2] == {
        "type": "button",
        "sub_type": "url",
        "index": "0",
        "parameters": [{"type": "text", "text": "abc123"}],
    }


def test_missing_and_invalid_variables():
    spec = parse_template(TEMPLATE_SHAADI)
    with pytest.raises(ValidationError) as e:
        validate_values(spec, {"header.1": "A", "body.1": "A"})
    assert e.value.code == "missing_template_variables"
    with pytest.raises(ValidationError):
        validate_values(spec, {"header.1": "A", "body.1": "line\nbreak", "body.2": "x", "button.0.1": "y"})
    with pytest.raises(ValidationError):
        validate_values(spec, {"header.1": "A", "body.1": "a     b", "body.2": "x", "button.0.1": "y"})
    with pytest.raises(ValidationError):
        validate_values(spec, {"header.1": "A", "body.1": "a", "body.2": "x", "button.0.1": "has space"})
    with pytest.raises(ValidationError) as e2:
        validate_values(spec, {"header.1": "A", "body.1": "a", "body.2": "x", "button.0.1": "y", "body.9": "z"})
    assert e2.value.code == "unexpected_template_variables"


def test_named_parameters_and_media_header():
    raw = {
        "id": "1",
        "name": "n",
        "language": "en",
        "status": "APPROVED",
        "parameter_format": "NAMED",
        "components": [
            {"type": "HEADER", "format": "IMAGE"},
            {"type": "BODY", "text": "Hi {{first_name}}, code {{code}}"},
            {"type": "BUTTONS", "buttons": [{"type": "COPY_CODE", "example": "X"}]},
        ],
    }
    spec = parse_template(raw)
    assert spec.required_variables == ["header.media_link", "body.first_name", "body.code", "button.0.coupon_code"]
    comps = render_components(
        spec,
        {
            "header.media_link": "https://cdn.example/a.png",
            "body.first_name": "Asha",
            "body.code": "X1",
            "button.0.coupon_code": "SAVE10",
        },
    )
    assert comps[0]["parameters"][0] == {"type": "image", "image": {"link": "https://cdn.example/a.png"}}
    assert comps[1]["parameters"][0] == {"type": "text", "parameter_name": "first_name", "text": "Asha"}
    assert comps[2]["parameters"][0] == {"type": "coupon_code", "coupon_code": "SAVE10"}
    with pytest.raises(ValidationError):
        validate_values(
            spec,
            {
                "header.media_link": "http://insecure",
                "body.first_name": "a",
                "body.code": "b",
                "button.0.coupon_code": "c",
            },
        )


def test_unapproved_or_unsupported_templates_rejected():
    raw = dict(TEMPLATE_SHAADI, status="PENDING")
    with pytest.raises(InvalidTemplateError):
        validate_values(parse_template(raw), {})
    raw2 = {
        "id": "2",
        "name": "f",
        "language": "en",
        "status": "APPROVED",
        "components": [{"type": "BODY", "text": "x"}, {"type": "BUTTONS", "buttons": [{"type": "FLOW"}]}],
    }
    spec = parse_template(raw2)
    assert not spec.is_sendable
