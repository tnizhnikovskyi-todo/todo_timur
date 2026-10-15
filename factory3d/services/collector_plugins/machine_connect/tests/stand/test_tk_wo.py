"""ТК-04, ТК-05, ТК-13 (SPEC §13.2): автостарт/автозавершення за завданням верстата, лічильник ADAM, відмова Odoo.

Відхилення стенда (TEST_REPORT): немає демо-WO (WO00013/WO00101) — МО створюються через XML-RPC за специфікаціями
seed_pre.py; WO «Розкрій» SAW-1 і «Складання шухляди» SLIDE-1.
"""

from __future__ import annotations

import time

import pytest

from .helpers import (
    FAKE_ENV,
    FakeUa,
    redirect_source,
    commands,
    dt,
    enable_write,
    machine,
    make_mo,
    stand_sh,
    state_log,
    ua_jobs,
    utcnow,
    wait,
    wo_of,
)


def wo_read(o, wid, fields=None):
    return o.read(
        "mrp.workorder",
        wid,
        fields or ["state", "qty_produced", "qty_production", "f3d_qty_counted", "f3d_auto_started", "time_ids"],
    )[0]


@pytest.mark.xfail(
    reason="iot_sim: методи JobOrderControl мають BrowseName у просторі екземплярів і вхід (String, String), а плагін викликає "
    "Store(JobOrder: ISA95JobOrderDataType) з простору ISA95-JOBCONTROL за OPC 10031-4 (iot_sim SPEC §8.3.2 для Store також "
    "вимагає структуру) → BadNoMatch; AC-101 покрито CT на фейковому сервері пакета (tests/unit/test_opcua_call.py)",
    strict=False,
)
def test_tk04_store_command(fresh, sim):
    """ТК-04 кроки 1–2: «Надіслати на верстат» → CMD-01 `Store` `done`, завдання в `JobOrderList` (AC-101)."""
    o = fresh(env={"F3D_WRITE_ENABLED": "1"}, params={"auto_start_enabled": "True"})
    enable_write(o, ["UA-SAW-1"], ["workcenters/SAW-1/job_cmd"])
    mo = make_mo(o, "BR-K4", 2)
    wid = wo_of(o, mo, "SAW-1")
    o.call("mrp.workorder", "action_f3d_send_to_machine", [wid])
    cmd = wait(lambda: next((c for c in commands(o, "workcenters/SAW-1/job_cmd") if c["state"] == "done"), None), 60, 2)
    assert cmd, commands(o)
    assert cmd["payload"]["method"] == "Store" and (cmd["result_data"] or {}).get("ReturnStatus") == 0, cmd
    assert "WO%05d" % wid in ua_jobs("SAW-1")


@pytest.mark.timeout(3600)
def test_tk04_autostart_fake(fresh, sim):
    """ТК-04 на фейковому OPC UA-сервері пакета (iot_sim не має структур ISA-95 і не веде машину за Start з пульта):
    Store з Odoo → Start → автостарт таймера ≤ 15 с → лічильник → автозавершення; AC-95, AC-101."""
    o = fresh(env={"F3D_WRITE_ENABLED": "1", **FAKE_ENV}, params={"auto_start_enabled": "True"}, ready=False)
    fake = FakeUa(("SAW-1",))
    try:
        redirect_source(o, "UA-SAW-1", fake.endpoint)
        enable_write(o, ["UA-SAW-1"], ["workcenters/SAW-1/job_cmd"])
        assert wait(
            lambda: o.search_read("f3d.source", [("code", "=", "UA-SAW-1")], ["state"])[0]["state"] == "online", 90, 3
        )
        mo = make_mo(o, "BR-K4", 2)
        wid = wo_of(o, mo, "SAW-1")
        assert wo_read(o, wid)["state"] == "ready", mo
        job = "WO%05d" % wid
        o.call("mrp.workorder", "action_f3d_send_to_machine", [wid])
        cmd = wait(
            lambda: next((c for c in commands(o, "workcenters/SAW-1/job_cmd") if c["state"] == "done"), None), 60, 2
        )
        assert cmd, commands(o)
        p = cmd["payload"]
        assert p["method"] == "Store" and p["job"] == job and p["qty"] == 2 and p["ref"] == mo["name"], cmd
        assert (cmd["result_data"] or {}).get("ReturnStatus") == 0, cmd
        assert [c[0] for c in fake.calls] == ["Store"], fake.calls
        fake.set_jobs([(job, "AllowedToStart")], "SAW-1")  # верстат прийняв завдання
        fake.set_jobs([(job, "Running")], "SAW-1")  # оператор натиснув Start на пульті
        fake.set("CurrentState", 3, "SAW-1")
        t0 = time.time()
        assert wait(lambda: wo_read(o, wid)["state"] == "progress", 40, 1), "WO не стала progress"
        assert time.time() - t0 <= 15 + 3  # AC-95: ≤ 15 с після WORKING
        w = wo_read(o, wid)
        ts = o.read("mrp.workcenter.productivity", w["time_ids"], ["create_uid", "f3d_auto", "date_end"])
        open_t = [t for t in ts if not t["date_end"]]
        assert len(open_t) == 1, ts
        emp = o.read("mrp.workorder", wid, ["f3d_employee_id"])[0]["f3d_employee_id"]
        emp_code = o.read("hr.employee", emp[0], ["f3d_code"])[0]["f3d_code"] if emp else None
        bot = o.search_read("res.users", [("login", "=", "f3d_machine_bot")], ["id"], context={"active_test": False})[
            0
        ]["id"]
        # DEC-1: у CE немає hr-зв'язку в таймері (mrp_workorder) — оператор у `f3d_employee_id` WO
        assert (
            emp_code == "OP-SAW-1"
            and open_t[0]["create_uid"][0] == bot
            and open_t[0]["f3d_auto"]
            and w["f3d_auto_started"]
        ), (emp, open_t)
        for n in (1, 2):
            fake.set("RelativePiecesOut", n, "SAW-1")
            time.sleep(3)
        assert wait(lambda: round(wo_read(o, wid)["f3d_qty_counted"]) == 2, 30, 2), wo_read(o, wid)
        fake.set_jobs([(job, "Completed")], "SAW-1")
        fake.set("CurrentState", 2, "SAW-1")
        assert wait(lambda: wo_read(o, wid)["state"] == "done", 150, 5), wo_read(o, wid)
        w = wo_read(o, wid)
        assert w["qty_produced"] == 2, w
        assert o.count("mrp.workcenter.productivity", [("workorder_id", "=", wid), ("date_end", "=", False)]) == 0
        assert any("SAW-1" in b and "2" in b for b in o.chatter("mrp.production", mo["id"])), o.chatter(
            "mrp.production", mo["id"]
        )
        fake.set_jobs([(job, "Running")], "SAW-1")  # крок 5: повторний Start того ж JobOrderID
        fake.set("CurrentState", 3, "SAW-1")
        time.sleep(20)
        assert o.count("mrp.workcenter.productivity", [("workorder_id", "=", wid), ("date_end", "=", False)]) == 0
        run_min = sum(
            (dt(x["date_end"]) - dt(x["date_start"])).total_seconds() / 60
            for x in state_log(o, "SAW-1")
            if x["state"] == "working" and x["date_end"]
        )
        print(
            "ТК-04: Σ інтервалів working SAW-1, хв:",
            round(run_min, 2),
            o.read("mrp.workorder", wid, ["f3d_run_min"])[0],
        )
    finally:
        fake.stop()


def test_tk05_slide1_counter(fresh, sim):
    """ТК-05: автостарт «одне в черзі» й лічильник ADAM через межу слова (SLIDE-1, I/O)."""
    o = fresh(params={"auto_start_enabled": "True"})
    sim.post("/mode", {"mode": "scenario"})
    qty = 5
    mo = make_mo(o, "SLIDE-FG", qty)
    wid = wo_of(o, mo, "SLIDE-1")
    o.call("mrp.workorder", "button_start", [wid])  # WO progress: «таймер оператора»
    assert wo_read(o, wid)["state"] == "progress"
    sim.hold("workcenters/SLIDE-1/state", 1, 1800)
    assert wait(lambda: machine(o, "SLIDE-1")["state"] == "working", 30, 1)
    m = machine(o, "SLIDE-1")
    assert m["active_workorder_id"] and m["active_workorder_id"][0] == wid, m
    for v in (65534, 65535, 65537):
        sim.hold("workcenters/SLIDE-1/pieces_out", v, 1800)
        time.sleep(8)  # лічильник читається раз на 5 с
    for v in range(65538, 65537 + qty - 3 + 1):
        sim.hold("workcenters/SLIDE-1/pieces_out", v, 1800)
        time.sleep(8)
    assert wait(lambda: round(wo_read(o, wid)["f3d_qty_counted"]) == qty, 40, 2), wo_read(o, wid)
    sim.hold("workcenters/SLIDE-1/state", 0, 600)
    assert wait(lambda: wo_read(o, wid)["state"] == "done", 120, 3), wo_read(o, wid)
    assert wo_read(o, wid)["qty_produced"] == qty
    sim.hold("workcenters/SLIDE-1/alarm", 1, 120)
    assert wait(lambda: machine(o, "SLIDE-1")["state"] == "fault", 30, 1)
    req = o.search_read("maintenance.request", [("f3d_signal_id.code", "=", "workcenters/SLIDE-1/alarm")], ["name"])
    assert len(req) == 1, req


@pytest.mark.timeout(3600)
def test_tk13_odoo_outage_buffer(fresh, sim):
    """ТК-13: Odoo недоступна 3 хв — колектор буферизує показання; після відновлення журнал має інтервал за часом показань."""
    o = fresh()
    sim.post("/mode", {"mode": "scenario"})
    sim.hold("workcenters/SAW-1/state", 3, 1800)
    assert wait(lambda: machine(o, "SAW-1")["state"] == "working", 30, 1)
    stand_sh("odoo-stop")
    time.sleep(120)
    t1 = utcnow()
    sim.hold("workcenters/SAW-1/state", 2, 1800)  # READY → idle
    time.sleep(300)
    t2 = utcnow()
    sim.hold("workcenters/SAW-1/state", 3, 1800)
    time.sleep(40)
    stand_sh("odoo-start")
    from . import odoo_rpc

    o = odoo_rpc.Odoo()
    assert wait(lambda: [x for x in state_log(o, "SAW-1") if x["state"] == "idle" and x["date_end"]], 300, 10)
    logs = [x for x in state_log(o, "SAW-1") if x["state"] == "idle" and x["date_end"]]
    assert logs, state_log(o, "SAW-1")
    x = logs[-1]
    assert abs((dt(x["date_start"]) - t1).total_seconds()) <= 6, (x, t1)
    assert abs((dt(x["date_end"]) - t2).total_seconds()) <= 6, (x, t2)
    all_logs = state_log(o, "SAW-1")
    assert len({(a["state"], a["date_start"]) for a in all_logs}) == len(all_logs), "дублікати інтервалів"
    from .helpers import Metrics, METRICS_URL

    assert wait(lambda: (Metrics(METRICS_URL).health()["buffer_rows"] or 0) <= 30, 150, 5), "буфер не спорожнів"
