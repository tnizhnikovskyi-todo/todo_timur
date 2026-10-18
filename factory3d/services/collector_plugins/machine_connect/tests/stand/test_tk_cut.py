"""ТК-09, ТК-10 (SPEC §13.2): карти розкрою — вручну (CSV → оптимізатор оператором → імпорт плану) і через колектор.

iot_sim: оптимізатор /jobs (:8083, API-30…33). Формат CSV intelliDivide — ПРИПУЩЕННЯ емулятора (Q-03).
"""

from __future__ import annotations

import base64
import json
import math
import time
from pathlib import Path

import pytest

from .helpers import (
    FAKE_ENV,
    FakeUa,
    redirect_source,
    JOBS_KEY,
    JOBS_URL,
    commands,
    cutopt,
    enable_write,
    http,
    make_mo,
    multipart,
    ua_jobs,
    wait,
    wo_of,
)

PARTS = Path(__file__).resolve().parent / "data" / "parts_BR-K4.csv"
QTY = 14


def import_parts(o):
    bom = o.search_read("mrp.bom", [("product_tmpl_id.default_code", "=", "BR-K4")], ["id"])[0]["id"]
    wiz = o.create(
        "td.cut.part.import.wizard",
        {"bom_id": bom, "file": base64.b64encode(PARTS.read_bytes()).decode(), "filename": PARTS.name},
    )
    o.call("td.cut.part.import.wizard", "action_import", [wiz])
    return bom


def create_main_map(o, mo_id):
    o.call("mrp.production", "action_f3d_create_cut_maps", [mo_id])
    cm = o.search_read(
        "td.cut.map", [("production_id", "=", mo_id), ("material_role", "=", "main")], ["id", "state", "mode"]
    )
    assert cm, "карту main не створено"
    return cm[0]["id"]


def map_read(o, mid):
    return o.read(
        "td.cut.map",
        mid,
        [
            "state",
            "ext_job_id",
            "plan_sheets",
            "plan_waste_pct",
            "job_order_id",
            "parts_count",
            "csv_attachment_id",
            "plan_attachment_id",
            "gantry_job_id",
            "error",
            "mode",
        ],
    )[0]


def test_tk09_manual_map(fresh, sim):
    """ТК-09: ручний режим — CSV за R-19 п. 5, оптимізатор оператором, імпорт плану, «Випустити» без команд (AC-60…65)."""
    o = fresh(params={"cutting_mode": "manual"})
    import_parts(o)
    mo = make_mo(o, "BR-K4", QTY)
    mid = create_main_map(o, mo["id"])
    o.call("td.cut.map", "action_build_lines", [mid])
    o.call("td.cut.map", "action_export", [mid])
    m = map_read(o, mid)
    assert m["parts_count"] == 126 and m["csv_attachment_id"], m  # Σ qty × 14 = 9 × 14
    assert o.count("td.cut.map.line", [("map_id", "=", mid)]) == 4
    att = o.read("ir.attachment", m["csv_attachment_id"][0], ["datas", "name"])[0]
    raw = base64.b64decode(att["datas"])
    assert not raw.startswith(b"\xef\xbb\xbf"), "CSV без BOM"
    text = raw.decode("utf-8")
    lines = text.split("\r\n")
    assert (
        lines[0]
        == "PartId;Description;Material;Length;Width;Quantity;Grain;EdgeTop;EdgeBottom;EdgeLeft;EdgeRight;Program"
    ), lines[0]
    rows = [ln for ln in lines[1:] if ln]
    assert len(rows) == 4 and "\n" not in text.replace("\r\n", ""), rows
    exp = sorted(math.ceil(q * QTY) for q in (2, 1, 4, 2))
    assert sorted(int(r.split(";")[5]) for r in rows) == exp, rows
    # крок 4: оператор intelliDivide — оптимізатор
    body, ctype = multipart(
        {"material": "DSP18-ANT", "sheet": "2800x2070x18", "external_ref": mo["name"], "machine": "SAW-1"},
        {"parts": ("parts.csv", raw)},
    )
    st, txt, _ = http("POST", JOBS_URL + "/jobs", raw=body, headers={"X-Api-Key": JOBS_KEY, "Content-Type": ctype})
    assert st == 202, (st, txt)
    job = json.loads(txt)["job_id"]
    plan = None
    for _ in range(30):
        st, plan = cutopt("GET", f"/jobs/{job}/plan")
        if st == 200:
            break
        time.sleep(2)
    assert st == 200 and plan["total_sheets"] > 0, (st, plan)
    pw = o.create(
        "td.cut.plan.import.wizard",
        {"map_id": mid, "file": base64.b64encode(json.dumps(plan).encode()).decode(), "filename": "plan.json"},
    )
    o.call("td.cut.plan.import.wizard", "action_import", [pw])
    m = map_read(o, mid)
    assert m["state"] == "planned" and m["plan_sheets"] == plan["total_sheets"], (m, plan["total_sheets"])
    o.call("td.cut.map", "action_release", [mid])
    m = map_read(o, mid)
    assert m["state"] == "released", m
    assert o.count("td.command", [("td_cut_map_id", "=", mid)]) == 0
    assert m["plan_attachment_id"]
    print("ТК-09: аркушів", m["plan_sheets"], "відхід %", m["plan_waste_pct"])


@pytest.mark.timeout(5400)
def test_tk10_collector_map(fresh, sim):
    """ТК-10: режим collector — upload → plan → release на верстат → портал; AC-97."""
    o = fresh(
        env={"F3D_WRITE_ENABLED": "1", **FAKE_ENV},
        params={"cutting_mode": "collector", "auto_start_enabled": "True"},
        ready=False,
    )
    enable_write(o, ["REST-CUTOPT", "REST-WOODSTORE"], ["equipment/CUTOPT/cmd", "equipment/GANTRY-1/cmd"])
    sim.post("/mode", {"mode": "scenario"})
    assert wait(
        lambda: all(
            o.search_read("td.source", [("code", "=", code)], ["state"])[0]["state"] == "online"
            for code in ("REST-CUTOPT", "REST-WOODSTORE")
        ),
        120,
        3,
    ), "REST-джерела не online"
    import_parts(o)
    mo = make_mo(o, "BR-K4", QTY)
    mid = create_main_map(o, mo["id"])
    o.call("td.cut.map", "action_build_lines", [mid])
    o.call("td.cut.map", "action_export", [mid])
    cmd = wait(lambda: next((c for c in commands(o, "equipment/CUTOPT/cmd") if c["state"] == "done"), None), 120, 3)
    assert (
        cmd and cmd["payload"]["op"] == "upload" and cmd["payload"]["map"] == mid and len(cmd["payload"]["token"]) == 16
    ), commands(o)
    m = wait(lambda: (x := map_read(o, mid)) and x["state"] == "planned" and x, 120, 3)
    assert m and m["plan_sheets"] > 0 and str(m["ext_job_id"]).startswith("cj-"), map_read(o, mid)
    assert cmd["result_data"]["job_id"] == m["ext_job_id"]
    wid = wo_of(o, mo, "SAW-1")
    o.call("td.cut.map", "action_release", [mid])
    m = map_read(o, mid)
    assert wait(lambda: map_read(o, mid)["job_order_id"], 60, 3), map_read(o, mid)
    jo = map_read(o, mid)["job_order_id"]
    assert jo in ua_jobs("SAW-1"), ua_jobs("SAW-1")
    # iot_sim віддає JobOrderList як String[] (без структур ISA-95) → плагін бачить job='-'; машинну частину (Running за cj-…) веде
    # фейковий OPC UA-сервер пакета
    fake = FakeUa(("SAW-1",))
    try:
        redirect_source(o, "UA-SAW-1", fake.endpoint)
        assert wait(
            lambda: o.search_read("td.source", [("code", "=", "UA-SAW-1")], ["state"])[0]["state"] == "online", 90, 3
        )
        fake.set_jobs([(jo, "Running")], "SAW-1")
        fake.set("CurrentState", 3, "SAW-1")
        assert wait(lambda: o.read("mrp.workorder", wid, ["state"])[0]["state"] == "progress", 90, 3), o.read(
            "mrp.workorder", wid, ["state"]
        )
        gj = wait(
            lambda: o.search_read(
                "td.gantry.job", [("origin", "=", "machine"), ("external_ref", "=", mo["name"])], ["sheets", "state"]
            ),
            120,
            5,
        )
        assert gj and gj[0]["sheets"] == map_read(o, mid)["plan_sheets"], gj
        assert wait(lambda: map_read(o, mid)["state"] in ("running", "done"), 120, 5), map_read(o, mid)
        # `done` карти приходить із завершенням завдання в оптимізаторі (iot_sim веде його лише власним верстатом) — не перевіряється
        print("ТК-10: карта", map_read(o, mid)["state"], "портал", gj)
    finally:
        fake.stop()
