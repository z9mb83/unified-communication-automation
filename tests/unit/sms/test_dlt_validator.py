import pytest

from services.sms.dlt_validator import render, validate_brand_dlt
from services.sms.gateway_interface import get_gateway
from shared.brand_registry import SmsBrandConfig, SmsTemplate
from shared.exceptions import ConfigurationError, InvalidTemplateError, ValidationError

TPL = SmsTemplate(
    template_id="1207160000000000001",
    name="reminder",
    sender_header="SHDBEL",
    content_type="service_implicit",
    content="Dear {#var#}, your consultation is on {#var#}. - Shaadi Bells",
)
P1 = "919800000001"


def test_render_preserves_exact_wording():
    out = render(TPL, ["Asha", "12 Oct 11:00"])
    assert out.text == "Dear Asha, your consultation is on 12 Oct 11:00. - Shaadi Bells"
    assert out.encoding == "GSM-7" and out.segments == 1


@pytest.mark.parametrize(
    ("values", "code"),
    [
        (["Asha"], "sms_variable_count_mismatch"),
        (["Asha", ""], "sms_variable_blank"),
        (["A" * 31, "x"], "sms_variable_too_long"),
        (["Asha {#var#}", "x"], "sms_variable_invalid"),
        (["Asha\nX", "x"], "sms_variable_invalid"),
    ],
)
def test_invalid_variables(values, code):
    with pytest.raises(ValidationError) as e:
        render(TPL, values)
    assert e.value.code == code


def test_unicode_segments():
    t = SmsTemplate(
        template_id="1", name="u", sender_header="SHDBEL", content_type="transactional", content="नमस्ते {#var#}"
    )
    out = render(t, ["आशा"])
    assert out.encoding == "UCS-2"


def test_disabled_template_rejected():
    with pytest.raises(InvalidTemplateError):
        render(TPL.model_copy(update={"enabled": False}), ["a", "b"])


def test_brand_dlt_static_validation():
    good = SmsBrandConfig(
        enabled=True, dlt_principal_entity_id="1201159100000000001", sender_headers=["SHDBEL"], templates=[TPL]
    )
    assert validate_brand_dlt(good) == []
    bad = SmsBrandConfig(
        enabled=True,
        dlt_principal_entity_id="abc",
        sender_headers=["SHDBEL"],
        templates=[TPL.model_copy(update={"sender_header": "OTHER1", "content_type": "promotional"})],
    )
    problems = validate_brand_dlt(bad)
    assert any("Principal Entity" in p for p in problems)
    assert any("not registered" in p for p in problems)
    assert any("invalid for promotional" in p for p in problems)


def test_unknown_provider_is_not_silently_live():
    with pytest.raises(ConfigurationError):
        get_gateway("some-real-provider", None)
