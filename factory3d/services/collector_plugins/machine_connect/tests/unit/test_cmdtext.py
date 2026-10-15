"""AC-80, AC-57: cmdtext = копія tools/commands.py модуля Odoo, чисті функції R-21."""

from __future__ import annotations

import ast
import filecmp
from pathlib import Path

import pytest
from f3d_collector_mc import cmdtext

PKG = Path(cmdtext.__file__)
ROOT = next(p for p in PKG.parents if (p / "odoo_addons").is_dir())
ODOO_TOOL = ROOT / "odoo_addons" / "factory3d_machine_connect" / "tools" / "commands.py"

FEED = {
    "stack": "PLT-03C",
    "target": "SAW-1",
    "sheets": 4,
    "product": "DSP16-ANT",
    "priority": 5,
    "ref": "WH/MO/00233",
}


def test_identical_to_odoo_tool():
    assert filecmp.cmp(PKG, ODOO_TOOL, shallow=False)


def test_no_odoo_imports():
    tree = ast.parse(PKG.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(a.name.split(".")[0] == "odoo" for a in node.names)
        if isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert (node.module or "").split(".")[0] != "odoo"


def test_examples():
    payload = cmdtext.build_payload("gantry", "feed", **FEED)
    assert payload == {"op": "feed", **FEED}
    assert cmdtext.build_cmd("gantry", "feed", **FEED) == "feed;PLT-03C;SAW-1;4;DSP16-ANT;5;WH/MO/00233"
    assert cmdtext.parse_cmd("gantry", "feed;PLT-03C;SAW-1;4;DSP16-ANT;5;WH/MO/00233") == payload
    with pytest.raises(ValueError, match="^product"):
        cmdtext.build_payload("gantry", "feed", **{**FEED, "product": "DSP16 ANT"})
    with pytest.raises(ValueError, match="stack: відсутнє"):
        cmdtext.check_payload("gantry", {"op": "feed", "sheets": 4})
    with pytest.raises(ValueError, match="fields: очікується 5"):
        cmdtext.parse_cmd("gantry", "stack;PLT-07C;55;DSP16-SON;L1;x")
    assert cmdtext.parse_cmd("job", "Stop;WO00013") == {"method": "Stop", "job": "WO00013"}
    data = {"id": "PLT-07C", "qty": 55}
    stack = {"op": "stack", "stack": "PLT-07C", "qty": 55, "product": "DSP16-SON", "lot": None}
    assert cmdtext.result_text("gantry", stack, data) == "stack PLT-07C=55"
