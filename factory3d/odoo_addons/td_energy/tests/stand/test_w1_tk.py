"""ТК-13…ТК-18 (W1_SPEC 13.2) на стенді: Пульт, історія, тривоги, відключення, PFC, мобільний.

Передумови: емулятор + збирач + Odoo (E-11), `td_energy` 19.0.1.1.0, `_td_backfill(days=90)` після ≥ 5 хв роботи.
Результати друкуються рядками ``TK <id> <json>`` (pytest -s) і заносяться до TEST_REPORT.md. Без F3D_ODOO_URL тести
пропускаються (conftest). Пароль користувачів сценаріїв — F3D_STAND_USER_PASSWORD (за замовчуванням = пароль admin).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta

import pytest

from conftest import need_collector
from helpers import Odoo, OdooFault, env, wait_for

pytestmark = pytest.mark.stand
DASH = "td.energy.dashboard"
USER_PASSWORD = os.environ.get("F3D_STAND_USER_PASSWORD", os.environ.get("F3D_ODOO_PASSWORD", ""))


def tk_report(tk, data):
    print(f"TK {tk} {json.dumps(data, ensure_ascii=False, default=str)}")


def user_odoo(odoo: Odoo, login: str) -> Odoo:
    """Сесія користувача сценарію (логін = пароль користувача стенда з групами енергетики)."""
    return odoo.as_user(login, USER_PASSWORD)


@need_collector
def test_tk13_pult_live(odoo, stand_ready):
    first = odoo.k(DASH, "get_pult", "now", ["kpis", "sld"])
    time.sleep(90)
    second = odoo.k(DASH, "get_pult", "now", ["kpis", "sld"])
    tk_report("13", {"data_state": second["meta"]["data_state"], "nodes": len(second["sld"]["nodes"])})
    assert second["meta"]["data_state"] in ("ok", "partial")
    assert len(second["sld"]["nodes"]) == 21
    assert all(second["kpis"][k] for k in ("grid", "load", "energy", "peak", "generation", "cos_phi"))
    assert second["meta"]["now"] > first["meta"]["now"]
    assert second["kpis"]["load"]["kw"] is not None


@need_collector
def test_tk14_history_join(odoo, stand_ready):
    data = odoo.k(DASH, "get_pult", "day", ["profile", "kpis"])
    profile, foot = (
        data["profile"],
        data["foot"] if "foot" in data else odoo.k(DASH, "get_pult", "now", ["profile"])["foot"],
    )
    now_slot = profile["now_slot"]
    gaps = [s for s in range(now_slot) if profile["cons"][s] is None]
    tk_report(
        "14", {"gaps": gaps, "forecast_days_used": profile["forecast_days_used"], "forecast_kwh": foot["forecast_kwh"]}
    )
    assert not gaps, "дірки профілю на стику історії й живих даних"
    assert profile["forecast_days_used"] >= 3
    assert foot["forecast_kwh"] is not None and foot["forecast_kwh"] > 0


@need_collector
def test_tk15_ack_two_sessions(odoo, sim, stand_ready):
    a, b = (
        user_odoo(odoo, os.environ.get("F3D_STAND_ENERGY_A", "energy_a")),
        user_odoo(odoo, os.environ.get("F3D_STAND_ENERGY_B", "energy_b")),
    )
    meter_dev = os.environ.get("F3D_STAND_METER_DEVICE", "PM-QF-C2")
    sim.post(f"/device/{meter_dev}/fault", {"reason": "generic"})
    try:

        def find():
            items = a.k(DASH, "get_alarms", 8, "active")["items"]
            return next((i for i in items if i["node_code"] == "C2" and i["state"] == "active"), None)

        alarm = wait_for(find, timeout=float(os.environ.get("F3D_STAND_ALARM_WAIT_S", "900")), step=10)
        assert alarm, "подія «лічильник C2 не на зв'язку» не з'явилась"
        a.k("td.energy.event", "action_take", [alarm["id"]])
        seen = wait_for(
            lambda: next(
                (i for i in b.k(DASH, "get_alarms", 8, "all")["items"] if i["id"] == alarm["id"] and i["assigned"]),
                None,
            ),
            timeout=10,
            step=1,
        )
        assert seen, "друга сесія не бачить виконавця ≤ 10 с"
        with pytest.raises(OdooFault, match="Уже в роботі"):
            b.k("td.energy.event", "action_take", [alarm["id"]])
    finally:
        sim.post(f"/device/{meter_dev}/clear")
    resolved = wait_for(
        lambda: odoo.k("td.energy.event", "read", [alarm["id"]], ["state"])[0]["state"] == "resolved",
        timeout=300,
        step=10,
    )
    tk_report("15", {"alarm": alarm["id"], "auto_resolved": bool(resolved)})
    assert resolved


@need_collector
def test_tk16_planned_outage(odoo, stand_ready):
    eng, mrp = (
        user_odoo(odoo, os.environ.get("F3D_STAND_ENERGY_A", "energy_a")),
        user_odoo(odoo, os.environ.get("F3D_STAND_MRP", "mrp_manager")),
    )
    node = odoo.k("td.energy.node", "search", [("code", "=", "BW-2")], limit=1)[0]
    tomorrow = (datetime.utcnow() + timedelta(days=1)).replace(hour=4, minute=0, second=0, microsecond=0)
    vals = {"node_id": node, "reason": "busway", "start": str(tomorrow), "end": str(tomorrow + timedelta(hours=2))}
    plan = eng.k("td.energy.outage.plan", "create", vals)
    eng.k("td.energy.outage.plan", "action_submit", [plan])
    mrp.k("td.energy.outage.plan", "action_approve", [plan])
    card = eng.k(DASH, "get_node_card", "BW-2", "day")
    maint = eng.k(DASH, "get_pult", "now", ["side"])["maint"]
    activities = odoo.k(
        "mail.activity", "search_count", [("res_model", "=", "td.energy.outage.plan"), ("res_id", "=", plan)]
    )
    tk_report("16", {"outage": card["outage"], "maint": [m["title"] for m in maint], "activities": activities})
    assert card["outage"] and card["outage"]["state"] == "approved"
    assert any(m["kind"] == "outage" for m in maint)
    assert activities == 0  # activity створено при поданні й закрито при узгодженні
    eng.k("td.energy.outage.plan", "action_cancel", [plan])


@need_collector
def test_tk17_pfc_fault(odoo, sim, stand_ready):
    sim.scenario("pfc_step_fault", {"section": 2, "step": 3})
    try:

        def event():
            domain = [("kind", "=", "pfc"), ("code", "=", "PFC-2"), ("state", "in", ["active", "acked"])]
            return odoo.k("td.energy.event", "search_read", domain, ["title"], limit=1)

        found = wait_for(event, timeout=300, step=10)
        assert found and found[0]["title"] == "PFC-2: ступінь 3 не вмикається"
        request = odoo.k("maintenance.request", "search_count", [("name", "=", "PFC-2: ступінь 3 не вмикається")])
        sld = odoo.k(DASH, "get_pult", "now", ["sld", "kpis"])
        state = {n["code"]: n["state"] for n in sld["sld"]["nodes"]}
        cos = sld["kpis"]["cos_phi"]
        tk_report(
            "17", {"pfc2": state["PFC-2"], "request": request, "cos": cos["sections"], "low": cos["low_sections"]}
        )
        assert state["PFC-2"] == "warn" and request >= 1
    finally:
        sim.post("/scenario/pfc_step_fault/stop")
    assert wait_for(lambda: not event(), timeout=600, step=15), "після зупинки сценарію подія не вирішилась"


@need_collector
def test_tk18_mobile(odoo, stand_ready):
    eng = user_odoo(odoo, os.environ.get("F3D_STAND_ENERGY_A", "energy_a"))
    mobile = eng.k(DASH, "get_mobile", None)
    tk_report("18", {"tabs": sorted(mobile), "active_count": mobile["alarms"]["active_count"]})
    assert {"state", "alarms", "scheme"} <= set(mobile)
    for item in mobile["alarms"]["active"][:1]:
        eng.k("td.energy.event", "action_take", [item["id"]])
        after = eng.k(DASH, "get_mobile", "alarms")["alarms"]
        mine = [i for i in after["active"] if i["id"] == item["id"]]
        assert mine and mine[0]["taken_by_me"]
        assert after["active_count"] <= mobile["alarms"]["active_count"]
    # «Показати в 3D» (UI) і розміри кнопок (≥ 48 px) перевіряє менеджер у браузері (AC-146, viewport 390×844)
    assert env("F3D_ODOO_URL")
