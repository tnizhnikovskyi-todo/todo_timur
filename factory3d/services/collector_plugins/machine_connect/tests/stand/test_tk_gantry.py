"""ТК-06, ТК-07, ТК-08, ТК-15 (SPEC §13.2): портал woodStore — подача, звірка стосів, події з пульта, стоп-крани.

iot_sim: woodStore API v1 (:8082) і сценарій `machine_fault` GANTRY-1. Відхилення — див. TEST_REPORT.
"""

from __future__ import annotations

import time

import pytest

from . import odoo_rpc
from .helpers import (
    commands,
    enable_write,
    machine,
    make_mo,
    stand_sh,
    wait,
    wo_of,
    ws,
)

GCMD = "equipment/GANTRY-1/cmd"


def job_read(o, jid):
    return o.read(
        "td.gantry.job",
        jid,
        [
            "state",
            "ws_id",
            "done",
            "sheets",
            "sheet_log",
            "consumed_qty",
            "stack_id",
            "origin",
            "production_id",
            "command_id",
            "error",
        ],
    )[0]


def stack_read(o, code):
    return o.search_read(
        "td.gantry.stack",
        [("code", "=", code)],
        [
            "ws_qty",
            "fed_unconsumed",
            "expected_qty",
            "diff",
            "state",
            "odoo_qty",
            "ws_product",
            "ws_lot",
            "odoo_lot_id",
        ],
    )[0]


def as_user(login: str):
    return odoo_rpc.Odoo(login=login, password=login)


@pytest.mark.timeout(3600)
def test_tk06_feed_by_mo(fresh, sim):
    """ТК-06: подача плити за МО (CMD-02 `feed`) і списання; AC-96."""
    o = fresh(env={"F3D_WRITE_ENABLED": "1"})
    enable_write(o, ["REST-WOODSTORE"], [GCMD])
    mo = make_mo(o, "BR-K4", 14)
    act = o.call("mrp.production", "action_f3d_feed_gantry", [mo["id"]])
    jid = act["res_id"]
    job = job_read(o, jid)
    assert job["sheets"] == 4 and job["state"] in ("draft", "to_send"), job
    code = o.read("td.gantry.stack", job["stack_id"][0], ["code"])[0]["code"]
    before = stack_read(o, code)
    o.call("td.gantry.job", "action_send", [jid])
    cmd = wait(lambda: next((c for c in commands(o, GCMD) if c["state"] == "done"), None), 90, 2)
    assert cmd, commands(o, GCMD)
    assert (cmd["text"] or "").startswith("feed;%s;SAW-1;4;" % code) or cmd["payload"].get("op") == "feed", cmd
    assert wait(lambda: job_read(o, jid)["ws_id"], 60, 2)
    job = job_read(o, jid)
    assert str(job["ws_id"]).startswith("wj-") and cmd["result_data"]["id"] == job["ws_id"], (job, cmd)
    assert wait(lambda: job_read(o, jid)["state"] == "done", 8 * 60, 10), job_read(o, jid)
    job = job_read(o, jid)
    assert job["done"] == 4 and len(job["sheet_log"]) == 4, job
    after = wait(lambda: (s := stack_read(o, code)) and s["ws_qty"] == before["ws_qty"] - 4 and s, 90, 5)
    assert after, (before, stack_read(o, code))
    assert after["fed_unconsumed"] == 4 and after["state"] == "ok", after
    moves = o.search_read(
        "stock.move",
        [("raw_material_production_id", "=", mo["id"]), ("location_id.td_code", "=", code)],
        ["state", "quantity"],
    )
    print("ТК-06: стос", code, "до", before["ws_qty"], "після", after["ws_qty"], "рухи МО:", moves)
    o.call("mrp.production", "action_f3d_view_gantry_jobs", [mo["id"]])


@pytest.mark.timeout(5400)
def test_tk07_stack_diff_fix(fresh, sim):
    """ТК-07: розбіжність стосу PLT-01B → `pending` → `diff` + діяльність → «Прийняти з порталу»; виправлення порталу (CMD-02 `stack`)."""
    # SPEC: розбіжність підтверджується через 10 хв (`stack_diff_confirm_min`); на стенді — 2 хв (скорочення прогону)
    o = fresh(env={"F3D_WRITE_ENABLED": "1"}, params={"stack_diff_confirm_min": "2"})
    enable_write(o, ["REST-WOODSTORE"], [GCMD])
    st, stacks = ws("GET", "/api/v1/stacks")
    q = next(s["qty"] for s in stacks if s["id"] == "PLT-01B")
    assert wait(lambda: stack_read(o, "PLT-01B")["ws_qty"] == q, 90, 3)
    assert stack_read(o, "PLT-01B")["state"] == "ok"
    st, d = ws("PATCH", "/api/v1/stacks/PLT-01B", {"qty": q - 2, "reason": "test"})
    assert st == 200, (st, d)
    s1 = wait(lambda: (s := stack_read(o, "PLT-01B")) and s["ws_qty"] == q - 2 and s, 90, 3)
    assert s1 and s1["state"] == "pending", s1
    s2 = wait(lambda: (s := stack_read(o, "PLT-01B")) and s["state"] == "diff" and s, 11 * 60, 15)
    assert s2, stack_read(o, "PLT-01B")
    sid = o.search_read("td.gantry.stack", [("code", "=", "PLT-01B")], ["id"])[0]["id"]
    acts = o.search_read("mail.activity", [("res_model", "=", "td.gantry.stack"), ("res_id", "=", sid)], ["summary"])
    assert len(acts) == 1 and "PLT-01B" in (acts[0]["summary"] or ""), acts
    stock = as_user("stand_stock")
    stock.call("td.gantry.stack", "action_accept_portal", [sid])
    s3 = stack_read(o, "PLT-01B")
    assert s3["state"] == "ok" and abs(s3["odoo_qty"] - (s3["ws_qty"] + s3["fed_unconsumed"])) < 0.01, s3
    # крок 5: портал розійшовся в інший бік → «Виправити портал» (команда `stack`)
    st, d = ws("PATCH", "/api/v1/stacks/PLT-01B", {"qty": q - 2 + 3, "reason": "test"})
    assert st == 200
    assert wait(lambda: (s := stack_read(o, "PLT-01B")) and s["state"] == "diff" and s, 11 * 60, 15), stack_read(
        o, "PLT-01B"
    )
    exp = stack_read(o, "PLT-01B")["expected_qty"]
    stock.call("td.gantry.stack", "action_fix_portal", [sid])
    cmd = wait(
        lambda: next(
            (c for c in commands(o, GCMD) if c["state"] == "done" and (c["payload"] or {}).get("op") == "stack"), None
        ),
        90,
        3,
    )
    assert cmd, commands(o, GCMD)
    assert wait(
        lambda: stack_read(o, "PLT-01B")["ws_qty"] == exp and stack_read(o, "PLT-01B")["state"] == "ok", 120, 5
    ), stack_read(o, "PLT-01B")
    st, stacks = ws("GET", "/api/v1/stacks")
    assert next(s["qty"] for s in stacks if s["id"] == "PLT-01B") == exp


@pytest.mark.timeout(3600)
def test_tk08_portal_events(fresh, sim):
    """ТК-08: завдання з пульта woodStore → дзеркало `origin='machine'` (AC-55); тривога порталу → заявка (AC-49)."""
    o = fresh()
    mo = make_mo(o, "BR-K4", 14)
    st, stacks = ws("GET", "/api/v1/stacks")
    s04c = next(s for s in stacks if s["id"] == "PLT-04C")
    assert wait(lambda: stack_read(o, "PLT-04C")["ws_qty"] == s04c["qty"], 90, 3)
    st, d = ws(
        "POST",
        "/api/v1/jobs",
        {
            "type": "feed",
            "source": "PLT-04C",
            "target": "SAW-2",
            "sheets": 2,
            "product": s04c["product"],
            "external_ref": mo["name"],
        },
    )
    assert st in (200, 201, 202), (st, d)
    jobs = wait(
        lambda: o.search_read(
            "td.gantry.job", [("origin", "=", "machine")], ["id", "state", "done", "sheet_log", "production_id"]
        ),
        120,
        5,
    )
    assert jobs, "завдання з пульта не потрапило в Odoo"
    j = wait(
        lambda: (
            (
                x := o.search_read(
                    "td.gantry.job", [("origin", "=", "machine")], ["state", "done", "sheet_log", "production_id"]
                )[0]
            )
            and x["state"] == "done"
            and x
        ),
        8 * 60,
        10,
    )
    assert j and j["done"] == 2 and len(j["sheet_log"]) == 2 and j["production_id"][0] == mo["id"], j
    s = wait(lambda: (x := stack_read(o, "PLT-04C")) and x["ws_qty"] == s04c["qty"] - 2 and x, 90, 5)
    assert s and s["fed_unconsumed"] == 2 and s["state"] == "ok", s
    sim.scenario("machine_fault", device="GANTRY-1")
    sig = wait(lambda: o.signal("equipment/GANTRY-1/state").get("last_text") == "error" and 1, 60, 2)
    assert sig, o.signal("equipment/GANTRY-1/state")
    req = wait(lambda: o.search_read("maintenance.request", [("name", "ilike", "GANTRY-1")], ["name"]), 60, 2)
    assert len(req) == 1, req
    sim.stop("machine_fault")
    assert commands(o) == []  # запис вимкнено: команд модуля 0


@pytest.mark.timeout(5400)
def test_tk15_stop_cranes(fresh, sim):
    """ТК-15 (скорочено): автостарт вимк./увімк., `read_enabled=False`, п'ять запобіжників запису порталу (AC-58, ТБ-02)."""
    o = fresh(env={"F3D_WRITE_ENABLED": "1"}, scenario=("shift", {"speed": 1, "trucks": False, "people": False}))
    mo = make_mo(o, "SLIDE-FG", 5)
    wid = wo_of(o, mo, "SLIDE-1")
    sim.hold("workcenters/SLIDE-1/state", 1, 1800)
    assert wait(lambda: machine(o, "SLIDE-1")["state"] == "working", 40, 1)
    time.sleep(180)  # крок 1 (SPEC: 10 хв): автостарт вимкнено
    assert o.read("mrp.workorder", wid, ["state"])[0]["state"] == "ready"
    o.param("td.machine_connect.auto_start_enabled", "True")  # крок 2
    sim.hold("workcenters/SLIDE-1/state", 0, 1800)
    time.sleep(10)
    sim.hold("workcenters/SLIDE-1/state", 1, 1800)
    assert wait(lambda: o.read("mrp.workorder", wid, ["state"])[0]["state"] == "progress", 120, 3), (
        "автостарт I/O не спрацював"
    )
    # крок 4–6: read_enabled=False
    o.param("td.machine_connect.read_enabled", "False")
    sim.hold("workcenters/SAW-1/state", 3, 600)
    time.sleep(60)
    assert machine(o, "SAW-1")["state"] != "working"
    src = o.search_read("td.source", [("code", "=", "MC-DERIVED")], ["state"])[0]["state"]
    o.param("td.machine_connect.read_enabled", "True")
    print("ТК-15: MC-DERIVED при read_enabled=False:", src)
    # крок 7: п'ять запобіжників
    enable_write(o, ["REST-WOODSTORE"], [GCMD])
    mo2 = make_mo(o, "BR-K4", 14)
    sigid = o.search_read("td.signal", [("code", "=", GCMD)], ["id"])[0]["id"]
    srcid = o.search_read("td.source", [("code", "=", "REST-WOODSTORE")], ["id"])[0]["id"]
    guards = [
        ("module", lambda v: o.param("td.machine_connect.write_enabled", "True" if v else "False")),
        ("telemetry", lambda v: o.param("td.telemetry.write_enabled", "True" if v else "False")),
        ("source", lambda v: o.write("td.source", srcid, {"write_enabled": v})),
        ("signal", lambda v: o.write("td.signal", sigid, {"write_enabled": v})),
    ]
    for name, setter in guards:
        setter(False)
        act = o.call("mrp.production", "action_f3d_feed_gantry", [mo2["id"]])
        err = None
        try:
            o.call("td.gantry.job", "action_send", [act["res_id"]])
        except RuntimeError as e:
            err = str(e)
        n = len([c for c in commands(o, GCMD) if c["state"] != "failed"])
        assert err or n == 0, (name, err, commands(o, GCMD))
        assert n == 0, (name, "команду створено при вимкненому запобіжнику", commands(o, GCMD))
        setter(True)
        jid = act["res_id"]
        o.call("td.gantry.job", "action_cancel", [jid]) if o.read("td.gantry.job", jid, ["state"])[0][
            "state"
        ] != "cancelled" else None
    # п'ятий: F3D_WRITE_ENABLED=0 в колекторі → команда `queued` → `expired`
    stand_sh("collector-restart", env={"F3D_WRITE_ENABLED": "0"})
    act = o.call("mrp.production", "action_f3d_feed_gantry", [mo2["id"]])
    o.call("td.gantry.job", "action_send", [act["res_id"]])
    c = wait(lambda: next((x for x in commands(o, GCMD) if x["state"] in ("expired", "failed")), None), 20 * 60, 20)
    assert c and c["state"] == "expired", commands(o, GCMD)
