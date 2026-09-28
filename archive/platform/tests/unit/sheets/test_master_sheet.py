"""Pure logic of the master-sheet Apps Script, executed in Node."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def gs(fn, *args):
    out = subprocess.run(
        ["node", str(HERE / "run_master.js"), fn, json.dumps(list(args))], capture_output=True, text=True, check=True
    ).stdout
    return json.loads(out)


def test_brand_codes():
    assert gs("mcBrandByCode_", "sc")["value"][1] == "skyline"
    assert gs("mcBrandByCode_", "99M")["value"][1] == "marketing"
    assert gs("mcBrandByCode_", "99S")["value"][1] == "staffing"
    assert gs("mcBrandByCode_", "PE")["value"][1] == "property"
    assert gs("mcBrandByCode_", "SB")["value"][1] == "shaadi"
    assert gs("mcBrandByCode_", "XX")["value"] is None


def test_phone_normalisation():
    assert gs("mcNormalizePhone_", "98765 43210", "91")["value"] == "919876543210"
    assert gs("mcNormalizePhone_", "+1 415 555 0100", "91")["value"] == "14155550100"
    assert not gs("mcNormalizePhone_", "123", "91")["ok"]


def test_template_parsing_and_components():
    t = {"name": "promo", "components": [{"type": "BODY", "text": "Hi {{1}}, visit {{2}}"}]}
    p = gs("mcParseTemplate_", t)["value"]
    assert p["supported"] and p["count"] == 2
    comps = gs("mcBuildComponents_", p, ["Asha", "Mohali"])["value"]
    assert comps == [
        {"type": "body", "parameters": [{"type": "text", "text": "Asha"}, {"type": "text", "text": "Mohali"}]}
    ]
    assert "Var 2 is required" in gs("mcBuildComponents_", p, ["Asha", ""])["error"]
    assert "line breaks" in gs("mcBuildComponents_", p, ["a\nb", "x"])["error"]
    named = gs(
        "mcParseTemplate_", {"parameter_format": "NAMED", "components": [{"type": "BODY", "text": "Hi {{first_name}}"}]}
    )["value"]
    assert gs("mcBuildComponents_", named, ["Asha"])["value"][0]["parameters"][0]["parameter_name"] == "first_name"
    media = gs(
        "mcParseTemplate_", {"components": [{"type": "HEADER", "format": "IMAGE"}, {"type": "BODY", "text": "x"}]}
    )
    assert media["value"]["supported"] is False


def test_dlt_rendering():
    content = "Dear {#var#}, visit on {#var#}. - SB"
    assert gs("mcRenderDlt_", content, ["Asha", "12 Oct"])["value"] == "Dear Asha, visit on 12 Oct. - SB"
    assert "30 characters" in gs("mcRenderDlt_", content, ["A" * 31, "x"])["error"]
    assert not gs("mcRenderDlt_", content, ["Asha"])["ok"]


def test_meta_error_classification():
    assert gs("mcClassifyMetaError_", 400, {"error": {"code": 130429}})["value"]["status"] == "Retry"
    assert gs("mcClassifyMetaError_", 401, {"error": {"code": 190}})["value"]["status"] == "Failed"
    assert gs("mcClassifyMetaError_", 400, {"error": {"code": 131050}})["value"]["status"] == "Opted out"
    assert gs("mcClassifyMetaError_", 500, {})["value"]["status"] == "Uncertain"


def test_masking():
    assert gs("mcMask_", "919876543210")["value"] == "91******3210"
    assert gs("mcMask_", "asha@example.com")["value"] == "a***@example.com"
