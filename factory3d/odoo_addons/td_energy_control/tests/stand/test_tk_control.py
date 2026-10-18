"""ТК-19…ТК-28 (W2_SPEC 13.2), частина «Odoo + емулятор»: екран, команди, журнал, відмови.

Передумови — `conftest.py`. Результати друкуються рядками ``TK <id> <json>`` (pytest -s). UI-перевірки (консоль, 3D) —
Playwright менеджера (ТК-19 UI, ТК-28). Без F3D_ODOO_URL тести пропускаються.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from conftest import need_collector
from helpers import Odoo, OdooFault, wait_for

pytestmark = pytest.mark.stand
CTL = "td.energy.control"
PASSWORD = os.environ.get("F3D_STAND_USER_PASSWORD", os.environ.get("F3D_ODOO_PASSWORD", ""))


def tk_report(tk, data):
    print(f"TK {tk} {json.dumps(data, ensure_ascii=False, default=str)}")


def user(odoo: Odoo, login: str) -> Odoo:
    return odoo.as_user(login, PASSWORD)


def run(who: Odoo, kind: str, params: dict | None = None, second: Odoo | None = None) -> dict:
    """prepare → confirm (→ confirm_second); повертає `get_action` після завершення (до 60 с)."""
    prep = who.k(CTL, "prepare", kind, params or {})
    res = who.k(CTL, "confirm", prep["token"])
    if res["state"] == "awaiting_second" and second:
        res = second.k(CTL, "confirm_second", prep["action_id"])
    final = wait_for(
        lambda: (
            (a := who.k(CTL, "get_action", prep["action_id"]))["state"] in ("done", "failed", "blocked", "expired")
            and a
        ),
        timeout=60,
    )
    return final or who.k(CTL, "get_action", prep["action_id"])


@need_collector
def test_tk19_screen_alive(odoo, control_ready):
    en1 = user(odoo, "en1")
    time.sleep(30)
    data = en1.k(CTL, "get_control")
    tk_report("19", {"engine": data["engine"]["label"], "scenarios": data["scenarios"]["on_count"]})
    assert data["engine"]["level"] == "ok", data["engine"]["label"]
    assert data["scenarios"]["total"] == 6 and data["scenarios"]["on_count"] == 4
    assert data["shed"]["sum_kw"] == 174 and len(data["shed"]["items"]) == 5
    assert len(data["commands"]) == 8
    assert len(data["schedule"]["rows"]) == 6
    assert data["journal"] is not None


@need_collector
def test_tk20_export_charge_undo(odoo, sim, control_ready):
    en1 = user(odoo, "en1")
    sim.scenario("export_demo", {"export_kw": 26})
    act = run(en1, "bess_charge", {"power_kw": 50, "until": "23:00"})
    tk_report("20", {"state": act["state"], "result": act["result_text"]})
    assert act["state"] == "done", act
    assert sim.value("energy_control/bess/mode") == 1
    back = en1.k(CTL, "undo", act["id"])
    en1.k(CTL, "confirm", back["token"])
    assert wait_for(lambda: sim.value("energy_control/bess/mode") == 0, timeout=30)


@need_collector
def test_tk21_qs_two_persons_and_blocking(odoo, sim, control_ready):
    en1, en2 = user(odoo, "en1"), user(odoo, "en2")
    act = run(en1, "qs_close", second=en2)
    tk_report("21", {"state": act["state"], "checks": [c["state"] for c in act["checks"]]})
    assert act["state"] == "done", act
    assert en1.k(CTL, "get_node_actions", "QS")[0]["code"] == "qs_open"
    run(user(odoo, "chief"), "qs_open")
    sim.post("/flags", {"ctl_remote": 0})
    try:
        blocked = en1.k(CTL, "prepare", "qs_close")
        assert blocked["blocked"], blocked
    finally:
        sim.post("/flags", {"ctl_remote": 1})


@need_collector
def test_tk22_other_commands(odoo, control_ready):
    chief, en1 = user(odoo, "chief"), user(odoo, "en1")
    for kind, params in (
        ("bess_discharge", {"power_kw": 100, "duration_min": 60}),
        ("air_setpoint", {"setpoint_bar": 6.5}),
    ):
        act = run(chief, kind, params)
        tk_report("22", {kind: act["state"]})
        assert act["state"] in ("done", "blocked"), act
    assert run(en1, "light_break")["state"] in ("done", "blocked")
    prep = en1.k(CTL, "prepare", "chp_start")
    assert prep["needs_second"] is True
    en1.k(CTL, "cancel", prep["token"])


@need_collector
def test_tk24_scenarios_toggle(odoo, control_ready):
    chief = user(odoo, "chief")
    act = run(chief, "scenario_toggle", {"scenario": "self", "enabled": True})
    assert act["state"] == "done"
    assert wait_for(lambda: chief.k(CTL, "get_control")["scenarios"]["items"][1]["applied"], timeout=40)
    run(chief, "scenario_toggle", {"scenario": "self", "enabled": False})


@need_collector
def test_tk27_failures_flags(odoo, control_ready):
    en1 = user(odoo, "en1")
    odoo.param("write_enabled", "False", prefix="td.energy_control.")
    try:
        with pytest.raises(OdooFault):
            en1.k(CTL, "prepare", "bess_charge")
    finally:
        odoo.param("write_enabled", "True", prefix="td.energy_control.")
