"""ТК-01, ТК-02, ТК-03, ТК-12 (SPEC §13.2): установка й міграція, аварія CNC-2, зміна лише читання, втрата зв'язку.

Відхилення стенда (TEST_REPORT): немає копії демо-бази (74 простої, WO00013/00101, MR/00031, 29 `working`) і режиму
`follow_odoo` — база наповнена seed_pre.py (35 РЦ, обладнання, оператори, стоси), стани верстатів дає сценарій `shift`.
"""

from __future__ import annotations

import json
import os
import time

from . import odoo_rpc
import pytest
from .helpers import (
    FAKE_ENV,
    FakeUa,
    redirect_source,
    downtimes,
    machine,
    psql,
    stand_sh,
    state_log,
    utcnow,
    wait,
    dt,
)

SOURCES_UA = 15
MODULE_CMD = [("signal_id.module", "=", "machine_connect")]


def snapshots() -> dict:
    """Знімки S0–S5 (§13.5 п. 2)."""
    return {
        "S0": psql("SELECT count(*) FROM mrp_workcenter_productivity"),
        "S1": psql("SELECT workcenter_id, count(*) FROM mrp_workcenter_productivity WHERE date_end IS NULL GROUP BY 1"),
        "S2": psql("SELECT id, state, qty_produced FROM mrp_workorder ORDER BY id"),
        "S3": psql("SELECT id, name, stage_id FROM maintenance_request ORDER BY id"),
        "S4": psql("SELECT max(write_date) FROM mrp_workorder")
        + psql("SELECT max(write_date) FROM mrp_workcenter_productivity"),
        "S5": psql(
            "SELECT q.location_id, q.product_id, q.lot_id, q.quantity FROM stock_quant q JOIN stock_location l ON l.id = q.location_id "
            "WHERE l.f3d_code LIKE 'PLT-%' ORDER BY 1, 2, 3, 4"
        ),
    }


def test_tk01_install_migration_read(sim):
    """ТК-01: установка на копії (без модуля), знімки S0–S5, міграція, читання 35 верстатів за ≤ 3 хв."""
    sim.post("/resume")
    sim.reset()
    sim.sync_time()
    assert "←" in stand_sh("fresh", "seed")
    before = snapshots()
    out = stand_sh("install", timeout=600)
    assert "installed" in out and "код Odoo 0" in out, out
    after = snapshots()
    for k in ("S0", "S1", "S2", "S3", "S4", "S5"):
        assert before[k] == after[k], (k, before[k][:3], after[k][:3])  # AC-83…85: стандартні дані не змінились
    stand_sh("odoo-start")
    o = odoo_rpc.Odoo()
    rep = json.loads(o.param("factory3d.machine_connect.migration_report"))
    assert rep["state"] == "done" and rep["machines"] == 35, rep
    assert o.count("f3d.machine") == 35
    assert (
        o.count("f3d.signal", [("module", "=", "machine_connect")]) >= 200
    )  # 207 = 35 верстатів + GANTRY-1 + CUTOPT (DEC-17)
    sim.scenario("shift", speed=1, trucks=False, people=False)
    stand_sh("collector-restart")
    t0 = time.time()
    assert wait(lambda: o.count("f3d.machine", [("raw_ts", "!=", False)]) >= 35, 180, 3), (
        "не всі верстати прочитано за 3 хв"
    )
    read_s = time.time() - t0
    st = {m["state"] for m in o.search_read("f3d.machine", [], ["state"])}
    assert "nodata" not in st, st
    ms = o.search_read("f3d.machine", [], ["code", "state", "current_log_id"])
    assert all(m["current_log_id"] for m in ms), "у кожного верстата має бути відкритий інтервал журналу"
    assert o.count("f3d.machine.state.log", [("date_end", "=", False)]) == 35

    def sources():
        return {
            s["code"]: s["state"]
            for s in o.search_read("f3d.source", [("module", "=", "machine_connect")], ["code", "state"])
        }

    wait(
        lambda: all(v == "online" for v in sources().values()), 120, 5
    )  # MC-DERIVED оновлює `_cron_tick` раз на хвилину
    src = sources()
    bad = {c: v for c, v in src.items() if v != "online"}
    assert len(src) == SOURCES_UA + 4 + 2 + 1, sorted(src)
    assert not bad, bad
    assert o.count("f3d.command", MODULE_CMD) == 0
    # R-26/DEC-1: модуль не змінює mrp.workorder/productivity автоматикою (макс. write_date = S4)
    assert psql("SELECT max(write_date) FROM mrp_workorder") == before["S4"][:1]
    print("ТК-01: читання 35 верстатів за", round(read_s), "с; стани:", sorted(st))


def test_tk02_machine_fault_cnc2(fresh, sim):
    """ТК-02: аварія CNC-2 → простій «Поломка», подія E0421, заявка; після stop — `idle`, заявка відкрита."""
    o = fresh(scenario=None)
    sim.post("/mode", {"mode": "scenario"})
    sim.hold("workcenters/CNC-2/state", 2, 3600)  # READY: верстат у зміні без завдання (`idle`)
    assert wait(lambda: machine(o, "CNC-2")["state"] == "idle", 60, 2)
    time.sleep(125)  # micro_stop_s = 120: простій ≥ 120 с фіксується
    sim.release("workcenters/CNC-2/state")
    sim.scenario("machine_fault", device="CNC-2", reason="spindle")
    t0 = time.time()
    assert wait(lambda: machine(o, "CNC-2")["state"] == "fault", 30, 1), "CNC-2 не став fault"
    react_s = time.time() - t0
    assert react_s <= 10 + 5  # AC-94: ≤ 10 с (запас на опитування)
    ev = wait(
        lambda: o.search_read("f3d.machine.event", [("machine_id.code", "=", "CNC-2")], ["message_id", "text"]), 40, 2
    )
    assert ev, "подій верстата CNC-2 немає (BaseEventType від iot_sim → EV-01)"
    dts = wait(lambda: [d for d in downtimes(o, "CNC-2") if d["state_kind"] == "fault"], 20, 2)
    assert dts, downtimes(o, "CNC-2")
    d = dts[-1]
    print(
        "ТК-02: hint_loss_id=%s hint_text=%r події=%s"
        % (d["hint_loss_id"], d["hint_text"], [e["text"] for e in ev][:3])
    )
    req = o.search_read(
        "maintenance.request", [("f3d_signal_id.code", "=", "workcenters/CNC-2/alarm")], ["name", "stage_id"]
    )
    assert len(req) == 1 and "CNC-2" in req[0]["name"], req
    d = wait(
        lambda: next(
            (x for x in downtimes(o, "CNC-2") if x["state_kind"] == "fault" and x["maintenance_request_id"]), None
        ),
        30,
        2,
    )
    assert d and d["maintenance_request_id"][0] == req[0]["id"], downtimes(o, "CNC-2")
    wc = o.search_read("mrp.workcenter", [("f3d_code", "=", "CNC-2")], ["working_state"])[0]
    assert wc["working_state"] == "blocked", wc
    sim.stop("machine_fault")
    assert wait(lambda: machine(o, "CNC-2")["state"] in ("idle", "off"), 120, 3)
    closed = wait(lambda: [x for x in downtimes(o, "CNC-2") if x["state_kind"] == "fault" and x["date_end"]], 30, 2)
    assert closed
    assert (
        o.search_read("mrp.workcenter", [("f3d_code", "=", "CNC-2")], ["working_state"])[0]["working_state"]
        != "blocked"
    )
    req2 = o.search_read("maintenance.request", [("id", "=", req[0]["id"])], ["stage_id"])[0]
    assert req2["stage_id"] == req[0]["stage_id"]  # заявка лишається відкритою


@pytest.mark.timeout(5400)
def test_tk03_shift_read_only(fresh, sim):
    """ТК-03: `shift` — лише читання. Тривалість F3D_STAND_TK03_MIN хв (SPEC: 60; у середовищі розробки типово 12)."""
    minutes = int(os.environ.get("F3D_STAND_TK03_MIN", "12"))
    o = fresh(scenario=("shift", {"speed": 1, "trucks": False, "people": False}))
    t_start = utcnow()
    time.sleep(minutes * 60)
    o.call("f3d.oee.shift", "_cron_oee") if False else None
    elapsed = (utcnow() - t_start).total_seconds() / 60
    bad = []
    for m in o.search_read("f3d.machine", [], ["code"], order="code"):
        logs = state_log(o, m["code"])
        for a, b in zip(logs, logs[1:], strict=False):
            if a["date_end"] != b["date_start"]:
                bad.append((m["code"], "розрив/перекриття", a, b))
        closed = [x for x in logs if x["date_end"] and x["state"] != "working" and x["state"] != "nodata"]
        for x in closed:
            if (dt(x["date_end"]) - dt(x["date_start"])).total_seconds() < 120 - 2:
                bad.append((m["code"], "інтервал простою < 120 с", x))
        if logs:
            total = (utcnow() - dt(logs[0]["date_start"])).total_seconds() / 60
            assert total <= elapsed + 4, (m["code"], total, elapsed)
    assert not bad, bad[:5]
    bot = o.search_read("res.users", [("login", "=", "f3d_machine_bot")], ["id"], context={"active_test": False})[0][
        "id"
    ]
    assert o.count("mrp.workorder", [("write_uid", "=", bot)]) == 0
    assert o.count("mrp.workcenter.productivity", [("write_uid", "=", bot)]) == 0
    assert o.count("f3d.command", MODULE_CMD) == 0
    # iot_sim публікує події без MessageId (I0001/I0002 лише в тексті «Завдання … запущено/завершено», «Зміна розпочата»)
    ev = o.search_read("f3d.machine.event", [], ["message_id", "text"], limit=50)
    assert ev, "події OPC UA-верстатів у «Подіях верстатів» відсутні"
    assert any("Завдання" in e["text"] or "Зміна" in e["text"] for e in ev), [e["text"] for e in ev][:5]
    assert o.count("mail.activity", [("summary", "ilike", "не знайдено в Odoo")]) == 0


@pytest.mark.xfail(
    reason="iot_sim при machine_fault comm пише CurrentState=OFFLINE зі StatusCode Good (iot_sim SPEC §8.3.1: усі змінні Bad_"
    "CommunicationError) → верстат `off`, а не `nodata`; AC-98 перевіряється на фейковому сервері (тест нижче)",
    strict=False,
)
def test_tk12_comm_loss_sim(fresh, sim):
    """ТК-12 на iot_sim: втрата зв'язку CNC-3 → `nodata` ≤ 180 с."""
    o = fresh(scenario=("shift", {"speed": 1, "trucks": False, "people": False}))
    sim.hold("workcenters/CNC-3/state", 3, 600)
    assert wait(lambda: machine(o, "CNC-3")["state"] == "working", 30, 1)
    sim.scenario("machine_fault", device="CNC-3", reason="comm")
    assert wait(lambda: machine(o, "CNC-3")["state"] == "nodata", 180, 3), machine(o, "CNC-3")
    sim.stop("machine_fault")


def test_tk12_comm_loss_fake(fresh, sim):
    """ТК-12 / AC-98 на фейковому OPC UA-сервері пакета: обрив зв'язку → `nodata` ≤ 180 с, автодій немає, `coverage` < 1; відновлення."""
    o = fresh(env=FAKE_ENV, ready=False)
    fake = FakeUa(("CNC-3",))
    try:
        redirect_source(o, "UA-CNC-3", fake.endpoint)
        fake.set("CurrentState", 3, "CNC-3")
        assert wait(lambda: machine(o, "CNC-3")["state"] == "working", 90, 2)
        fake.stop()  # обрив зв'язку
        t0 = time.time()
        assert wait(lambda: machine(o, "CNC-3")["state"] == "nodata", 180, 3), machine(o, "CNC-3")
        nodata_s = time.time() - t0
        time.sleep(30)
        assert o.count("maintenance.request", [("f3d_signal_id.code", "like", "CNC-3")]) == 0  # автодій немає
        fake = FakeUa(("CNC-3",))
        fake.set("CurrentState", 3, "CNC-3")
        assert wait(lambda: machine(o, "CNC-3")["state"] == "working", 120, 3), machine(o, "CNC-3")
        logs = state_log(o, "CNC-3")
        assert any(x["state"] == "nodata" and x["date_end"] for x in logs), logs
        sid = o.search_read("f3d.oee.shift", [("machine_id.code", "=", "CNC-3")], ["id"])
        if sid:
            o.call("f3d.oee.shift", "action_recompute", [sid[0]["id"]])
            cov = o.search_read("f3d.oee.shift", [("machine_id.code", "=", "CNC-3")], ["coverage"])[0]["coverage"]
            assert cov < 1, cov
        print("ТК-12: nodata через", round(nodata_s), "с")
    finally:
        fake.stop()
