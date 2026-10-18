"""ТК-11, ТК-14, ТК-16 (SPEC §13.2): причини простоїв, 3D-переглядач, кінець зміни.

Відхилення (TEST_REPORT): ТК-11 крок 4 (злиття із записом оператора в «Цеху») — MAN/Shop Floor (Enterprise `mrp_workorder`
відсутній, DEC-1), покрито Odoo-тестом test_merge_operator; ТК-14 — `td_viewer3d` не встановлено; ТК-16 — календар РЦ EDGE-3
підмінено на «зміна до now+9 хв» (SPEC: 15:00–15:40 за реальним календарем).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from . import odoo_rpc
from .helpers import KYIV, cron_run, dt, downtimes, machine, wait


def test_tk11_reasons(fresh, sim):
    """ТК-11 (кроки 1–3, 5, 6): простій `idle` із затримкою 120 с → причина оператора → підтвердження майстром → закриття."""
    o = fresh()
    sim.post("/mode", {"mode": "scenario"})
    t_put = datetime.now(UTC).replace(tzinfo=None)
    sim.hold("workcenters/SAW-2/state", 2, 1800)  # READY
    assert wait(lambda: machine(o, "SAW-2")["state"] == "idle", 40, 1)
    d = wait(lambda: next(iter(downtimes(o, "SAW-2", open_only=True)), None), 200, 5)
    assert d, "простій idle не з'явився за 120 с + запас"
    assert abs((dt(d["date_start"]) - t_put).total_seconds()) <= 8, (d, t_put)  # час переходу, а не час запису
    loss = o.call("ir.model.data", "check_object_reference", "mrp", "block_reason0")[1]
    op = odoo_rpc.Odoo(login="stand_op", password="stand_op")
    op.call("td.downtime", "action_set_reason", [d["id"]], loss)
    r = o.read("td.downtime", d["id"], ["reason_source", "reason_state", "loss_id"])[0]
    assert (r["reason_source"], r["reason_state"]) == ("operator", "to_confirm") and r["loss_id"][0] == loss, r
    master = odoo_rpc.Odoo(login="stand_master", password="stand_master")
    master.call("td.downtime", "action_confirm", [d["id"]])
    assert o.read("td.downtime", d["id"], ["reason_state"])[0]["reason_state"] == "confirmed"
    # простій коротший за micro_stop_s (120 с) при закритті видаляється (R-05 п. 4) — тримаємо стан ≥ 3 хв, як у SPEC
    time.sleep(max(0.0, 180 - (datetime.now(UTC).replace(tzinfo=None) - t_put).total_seconds()))
    sim.release("workcenters/SAW-2/state")  # повернення до моделі емулятора
    assert wait(lambda: machine(o, "SAW-2")["state"] != "idle", 60, 2)
    closed = o.read("td.downtime", d["id"], ["date_end"])[0]["date_end"]
    assert closed, "простій не закрито"
    assert (
        o.search_read("mrp.workcenter", [("td_code", "=", "SAW-2")], ["working_state"])[0]["working_state"]
        != "blocked"
    )


def test_tk14_viewer():
    """ТК-14: 3D-переглядач (AC-86…88 на стенді) — `td_viewer3d` у стенді не встановлено."""
    pytest.skip("td_viewer3d не встановлено в стенді (AC-70 skip до viewer); перевірка в UI — MAN")


@pytest.mark.timeout(3000)
def test_tk16_end_of_shift(fresh, sim):
    """ТК-16: простій через межу зміни закривається о кінці планового часу, нового немає; після +5 хв запис OEE `closed`."""
    o = fresh(scenario=("shift", {"speed": 1, "trucks": False, "people": False}))
    now_k = datetime.now(KYIV)
    end_min = now_k.hour * 60 + now_k.minute + 9
    assert end_min < 24 * 60 - 20, "тест не запускати біля півночі"
    e_local = now_k.replace(hour=end_min // 60, minute=end_min % 60, second=0, microsecond=0)
    e_utc = (e_local - timedelta(hours=3)).replace(tzinfo=None)
    cal = o.create(
        "resource.calendar",
        {
            "name": "Стенд ТК-16",
            "tz": "Europe/Kyiv",
            "hours_per_day": 8,
            "attendance_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Зміна",
                        "dayofweek": str(now_k.weekday()),
                        "hour_from": 0.0,
                        "hour_to": end_min / 60.0,
                        "day_period": "morning",
                    },
                )
            ],
        },
    )
    o.write(
        "mrp.workcenter",
        o.search_read("mrp.workcenter", [("td_code", "=", "EDGE-3")], ["id"])[0]["id"],
        {"resource_calendar_id": cal},
    )
    sim.hold("workcenters/EDGE-3/state", 2, 3600)  # простій через межу зміни
    assert wait(lambda: machine(o, "EDGE-3")["state"] == "idle", 60, 2)
    time.sleep(max(0, (e_utc - datetime.now(UTC).replace(tzinfo=None)).total_seconds()) + 75)
    dts = [x for x in downtimes(o, "EDGE-3") if x["state_kind"] == "idle"]
    assert dts, downtimes(o, "EDGE-3")
    last = dts[-1]
    assert last["date_end"], last
    assert abs((dt(last["date_end"]) - e_utc).total_seconds()) <= 2, (last, e_utc)  # R-05 п. 6: закрито в кінці плану
    assert not downtimes(o, "EDGE-3", open_only=True), "після кінця зміни новий простій не відкривається"
    time.sleep(
        max(0, (e_utc + timedelta(minutes=5, seconds=70) - datetime.now(UTC).replace(tzinfo=None)).total_seconds())
    )
    cron_run(o, "OEE змін")
    rows = o.search_read(
        "td.oee.shift",
        [("code", "=", "EDGE-3"), ("date", "=", e_local.strftime("%Y-%m-%d"))],
        ["state", "oee", "availability", "performance", "quality", "run_min", "down_min", "unexplained_min", "ppt_min"],
    )
    assert rows and rows[0]["state"] == "closed", rows
    state_after = o.read("td.oee.shift", rows[0]["id"], ["write_date"])[0]["write_date"]
    cron_run(o, "OEE змін")
    assert o.read("td.oee.shift", rows[0]["id"], ["write_date"])[0]["write_date"] == state_after, (
        "повторний крон змінив закриту зміну"
    )
    for r in o.search_read(
        "td.oee.shift",
        [],
        ["oee", "availability", "performance", "quality", "run_min", "down_min", "unexplained_min", "ppt_min"],
    ):
        assert abs(r["oee"] - r["availability"] * r["performance"] * r["quality"]) <= 1e-4, r
        assert abs(r["run_min"] + r["down_min"] + r["unexplained_min"] - r["ppt_min"]) <= 0.5, r
