"""Синхронізація даних модуля з макетом (SPEC §13.1.3). Запуск поза Odoo: `pytest tests/test_data_sync.py`."""

import csv
import importlib.util
import io
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(MODULE, "..", ".."))

pytest.importorskip("plant", reason="потрібен корінь макета factory3d")  # імпорт нижче додає ROOT у sys.path


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
gen_data = _load("f3d_bms_gen_data", os.path.join(MODULE, "tools", "gen_data.py"))
heat = _load("f3d_bms_heat", os.path.join(MODULE, "tools", "heat.py"))

# Додаток A.1: code -> (n, площа округлена до м², e_calc, p_inst)
A1 = {
    "LT-RCV-1": (4, 118, 388, 0.5),
    "LT-RCV-2": (4, 124, 370, 0.5),
    "LT-RCV-3": (4, 124, 370, 0.5),
    "LT-RCV-4": (4, 124, 370, 0.5),
    "LT-RCV-5": (4, 124, 370, 0.5),
    "LT-RCV-6": (4, 124, 370, 0.5),
    "LT-RCV-7": (4, 144, 319, 0.5),
    "LT-SHEETS": (12, 1201, 115, 1.51),
    "LT-HW": (5, 351, 164, 0.63),
    "LT-EDGE": (3, 168, 205, 0.38),
    "LT-PKS": (2, 142, 161, 0.25),
    "LT-CUT": (27, 609, 509, 3.4),
    "LT-EB": (27, 565, 549, 3.4),
    "LT-CNC": (27, 565, 549, 3.4),
    "LT-SORT": (12, 439, 314, 1.51),
    "LT-FAC": (91, 1235, 846, 11.47),
    "LT-ASM": (15, 499, 345, 1.89),
    "LT-PRE": (4, 268, 171, 0.5),
    "LT-MAINT": (4, 125, 366, 0.5),
    "LT-PACK": (12, 383, 360, 1.51),
    "LT-POST": (3, 297, 116, 0.38),
    "LT-CMP": (2, 64, 360, 0.25),
    "LT-CHG": (2, 64, 360, 0.25),
    "LT-FG": (12, 835, 165, 1.51),
    "LT-ELEC": (4, 119, 387, 0.5),
    "LT-OUT-1": (4, 124, 370, 0.5),
    "LT-OUT-2": (4, 130, 353, 0.5),
    "LT-OUT-3": (4, 130, 353, 0.5),
    "LT-OUT-4": (4, 130, 353, 0.5),
    "LT-OUT-5": (4, 130, 353, 0.5),
    "LT-OUT-6": (4, 130, 353, 0.5),
    "LT-OUT-7": (4, 150, 305, 0.5),
}


@pytest.fixture(scope="module")
def generated():
    return gen_data.generate(ROOT)


@pytest.fixture(scope="module")
def plant():
    return gen_data.load_plant(ROOT)


def test_generated_files_match(generated):
    assert sorted(generated) == [
        "data/bms_signals.csv",
        "data/td_bms_hvac_data.xml",
        "data/td_bms_light_data.xml",
        "data/td_bms_light_norm_data.xml",
        "data/td_bms_light_scene_data.xml",
        "data/td_bms_source_data.xml",
        "tests/data/static_bms.json",
    ]
    for rel, text in generated.items():
        with open(os.path.join(MODULE, rel), "rb") as f:
            assert f.read() == text.encode("utf-8"), "%s не збігається з генератором — перегенеруйте gen_data.py" % rel


def test_generator_is_deterministic(generated):
    assert gen_data.generate(ROOT) == generated


def test_groups_vs_macro(plant):
    groups = plant["lighting"].layout(plant["specs"], plant["lux"])
    assert len(groups) == 32
    for code, (n, area, e_calc, p_inst) in A1.items():
        g = groups[code]
        assert (g["n"], g["e_calc"], g["p_inst"]) == (n, e_calc, p_inst), code
        assert abs(g["area"] - area) <= 1, code  # макет округлює 564,5 банківським округленням
    assert sum(g["n"] for g in groups.values()) == 320


def test_balance_vs_macro(plant):
    vent = plant["ventilation"]
    data = vent.ventilation_data(plant["specs"])
    macro = vent.heat_balance(data["units"], 0)
    assert macro["total"] == 753
    assert [i["kw"] for i in macro["items"]] == [189, 109, 247, 208]
    units = [{"kind": u["kind"], "airflow_nom": u["airflow_nom"]} for u in data["units"].values()]
    params = dict(
        t_out_design=-15.0,
        t_in_set=18.0,
        length_m=150.0,
        width_m=72.0,
        height_m=9.0,
        u_wall=0.35,
        u_roof=0.25,
        u_floor=0.15,
        infiltration_ach=0.1,
        winter_oa_share=0.5,
        heat_recovery=0.78,
        air_wh_m3k=0.34,
        ahu_design_share=0.85,
        ahu_supply_c=21.0,
        internal_gains_kw=0.0,
        boilers=2,
        boiler_kw=495.0,
        boiler_stage_share=0.85,
        chp_el_kw=800.0,
        chp_heat_kw=856.0,
        chp_heat_75_kw=676.0,
        chp_heat_50_kw=497.0,
        chp_min_load=0.5,
    )
    res = heat.design_balance(params, units)
    assert res["total_kw"] == 753
    assert [ln["kw_round"] if "kw_round" in ln else round(ln["kw"]) for ln in res["lines"]] == [189, 109, 247, 208]


def test_signal_count(generated):
    rows = list(csv.DictReader(io.StringIO(generated["data/bms_signals.csv"])))
    codes = [r["code"] for r in rows]
    assert len(rows) == 549 and len(set(codes)) == 549
    assert sum(r["writable"] == "1" for r in rows) == 142
    assert sum(r["new"] == "0" for r in rows) == 81
    assert sum(r["origin"] == "catalog" for r in rows) == 176
    assert sum(r["origin"] == "module" for r in rows) == 292
    assert sum(r["source"] == "BMS-DERIVED" for r in rows) == 59
    assert sum(r["source"].startswith("BAC-") for r in rows) == 327
    assert sum(r["source"].startswith("HN-") for r in rows) == 163
    for r in rows:
        for col in ("address", "states", "alarm_states"):
            if r[col]:
                json.loads(r[col])


def test_static_has_sections(generated):
    static = json.loads(generated["tests/data/static_bms.json"])
    assert len(static["lighting"]["groups"]) == 32
    assert len(static["ventilation"]["units"]) == 29
