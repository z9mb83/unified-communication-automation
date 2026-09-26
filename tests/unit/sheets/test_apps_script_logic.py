"""Executes the real Apps Script source (pure functions) in Node."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def gs(fn, *args):
    out = subprocess.run(
        ["node", str(HERE / "run_gs.js"), fn, json.dumps(list(args))], capture_output=True, text=True, check=True
    ).stdout
    return json.loads(out)


def test_non_contiguous_selection_dedupes_and_skips_headers():
    ranges = [{"start": 1, "count": 3}, {"start": 7, "count": 2}, {"start": 2, "count": 2}, {"start": 8, "count": 1}]
    assert gs("collectRowNumbers_", ranges, 3)["value"] == [3, 7, 8]


def test_selection_cap():
    res = gs("collectRowNumbers_", [{"start": 2, "count": 2500}], 2)
    assert not res["ok"] and "at most" in res["error"]


def test_group_runs_minimises_reads():
    assert gs("groupRuns_", [3, 4, 5, 9, 10, 12])["value"] == [
        {"start": 3, "count": 3},
        {"start": 9, "count": 2},
        {"start": 12, "count": 1},
    ]


def test_column_index():
    assert [gs("columnIndex_", c)["value"] for c in ("A", "L", "Z", "AA")] == [0, 11, 25, 26]


def test_snapshot_record_maps_columns():
    binding = {"columns": {"name": "A", "phone": "C"}, "brand_column": None, "contact_id_column": None}
    rec = gs("snapshotRecord_", 5, ["Asha", "x", " +91 98 ", "Delhi"], binding)["value"]
    assert rec["row_number"] == 5 and rec["name"] == "Asha" and rec["phone"] == "+91 98"
    assert rec["cells"]["D"] == "Delhi"


def test_brand_detection_never_guesses():
    assert gs("resolveBrandFromRows_", {"brand_id": "shaadi"}, [], None)["value"] == "shaadi"
    generic = {"brand_id": None, "brand_column": "A"}
    assert gs("resolveBrandFromRows_", generic, ["marketing", "marketing"], ["marketing"])["value"] == "marketing"
    assert "several brands" in gs("resolveBrandFromRows_", generic, ["marketing", "shaadi"], None)["error"]
    assert "blank Brand ID" in gs("resolveBrandFromRows_", generic, ["marketing", ""], None)["error"]
    assert "not a brand you are allowed" in gs("resolveBrandFromRows_", generic, ["skyline"], ["marketing"])["error"]
    assert "not mapped" in gs("resolveBrandFromRows_", {"brand_id": None, "brand_column": None}, ["x"], None)["error"]


def test_build_recipients_whatsapp_and_sms():
    snap = [
        {
            "row_number": 2,
            "contact_id": "",
            "row_brand_id": "",
            "name": "Asha",
            "email": "",
            "phone": "98",
            "cells": {"A": "Asha", "C": "Delhi"},
        }
    ]
    mapping = {"body.1": {"source": "column", "value": "a"}, "body.2": {"source": "fixed", "value": "Mon"}}
    wa = gs("buildRecipients_", snap, mapping, "whatsapp")["value"]
    assert wa[0]["variables"] == {"body.1": "Asha", "body.2": "Mon"}
    sms_map = {"var.2": {"source": "column", "value": "C"}, "var.1": {"source": "column", "value": "A"}}
    sms = gs("buildRecipients_", snap, sms_map, "sms")["value"]
    assert sms[0]["variables"] == ["Asha", "Delhi"]


def test_menu_structure_matches_specification():
    src = (HERE / "../../../apps/google-sheets/Menu.gs").resolve().read_text()
    required = [
        "UCA.MENU_NAME",
        "Send Email to Selected Rows",
        "Run Existing Email Automation",
        "Start Email Automation",
        "Stop Email Automation",
        "Check Email Status",
        "Send WhatsApp to Selected Rows",
        "Select Approved Template",
        "Sync Approved Templates",
        "Start WhatsApp Automation",
        "Stop WhatsApp Automation",
        "Check WhatsApp Status",
        "Send SMS to Selected Rows",
        "Select Approved SMS Template",
        "Start SMS Automation",
        "Stop SMS Automation",
        "Start All Enabled Automations",
        "Stop All Automations",
        "Emergency Stop",
        "View Job Status",
        "Validate Configuration",
    ]
    for label in required:
        assert label in src, label
    code = (HERE / "../../../apps/google-sheets/Code.gs").resolve().read_text()
    assert "MENU_NAME: 'AUTOMATION MANAGER'" in code
