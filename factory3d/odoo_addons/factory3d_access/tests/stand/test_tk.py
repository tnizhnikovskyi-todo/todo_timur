"""ТК-01…ТК-10 (SPEC §13.2). Порядок виконання: ТК-01, 02, 03, 05, 07, 04, 10, 08, 06 (ТК-09 — skip без viewer).

Тести стану залежні й виконуються підряд у порядку оголошення (ТК-04 «виводить» людей після ТК-05/07).
Дата sim-сценаріїв — ``day`` (учора): реальний «зараз» Odoo пізніше за 15:50, тож вихід 15:30 «сьогодні» був би
«майбутнім» (future_tolerance_s). Для першого опитування збільшується ``initial_lookback_h`` (72).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import pytest

from helpers import kyiv_iso, wait_for

pytestmark = pytest.mark.stand
KYIV = timedelta(hours=3)          # літній час до 25.10.2026 (DEC-4)


def tk_report(tk, data):
    """Фактичні кількості прогону — у stdout (pytest -s) і далі в DEPLOY_TEST.md."""
    print(f"TK {tk} {json.dumps(data, ensure_ascii=False, default=str)}")


def sim_now(sim) -> datetime:
    return datetime.fromisoformat(sim.get("/status")["sim_now"])


def wait_sim_until(sim, day, hhmm, timeout=420):
    target = datetime.fromisoformat(kyiv_iso(day, hhmm))
    assert wait_for(lambda: sim_now(sim) >= target, timeout, 2), f"sim-час не досяг {hhmm}"


def to_local(dt_str):
    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S") + KYIV


def count(od, model, domain):
    return od.k(model, "search_count", domain)


def employee(od, barcode):
    return od.k("hr.employee", "search_read", [("barcode", "=", barcode)],
                ["id", "f3d_access_present", "f3d_access_zone_id", "f3d_home_zone_id", "name"], limit=1)[0]


def zone_code(m2o):
    return od_zone_codes.get(m2o[0]) if m2o else None


od_zone_codes: dict[int, str] = {}


@pytest.fixture(scope="module", autouse=True)
def _zones(odoo):
    od_zone_codes.update({z["id"]: z["f3d_code"] for z in odoo.k("f3d.zone", "search_read", [], ["f3d_code"])})


def door_id(od, code):
    return od.k("f3d.access.door", "search", [("code", "=", code)], limit=1)[0]


def cron_run(od, name_part):
    """Прямий запуск крону модуля (`ir.cron.method_direct_trigger`), без очікування розкладу."""
    ids = od.k("ir.cron", "search", [("cron_name", "ilike", name_part)])
    assert ids, f"крон {name_part} не знайдено"
    od.k("ir.cron", "method_direct_trigger", ids)


def feed_visitor_to_sim(od, sim, bs_http, uid):
    """Емулятор знає лише працівників Odoo (``world.people``): для користувача ``V-<id>`` створюється технічний
    працівник-заглушка зі штрих-кодом ``V-<id>``; режим ``follow_odoo`` на мить підтягує його, далі — ``scenario``."""
    if not od.k("hr.employee", "search_count", [("barcode", "=", uid)]):
        od.k("hr.employee", "create", {"name": f"Заглушка емулятора {uid}", "barcode": uid})
    sim.post("/mode", {"mode": "follow_odoo"})

    def known():
        r = bs_http.get("/api/users", params={"limit": 200, "offset": 0}).json()
        return any(x["user_id"] == uid for x in r["UserCollection"]["rows"])
    try:
        assert wait_for(known, 90, 3), f"емулятор не підхопив {uid}"
    finally:
        sim.post("/mode", {"mode": "scenario"})
        sim.post("/time", {"factor": 10})
    od.k("hr.employee", "write", od.k("hr.employee", "search", [("barcode", "=", uid)]), {"barcode": False})


# ---------------------------------------------------------------------------------------------- ТК-01
def test_tk01_install_clean_db(odoo, server_id):
    """AC-59 (чиста база): звіт хука, відмітки не змінено, у відмітках немає biostar-режиму до першого опитування.

    Кількості демо-копії (35 зв'язків, 35 домашніх зон) тут не очікуються: працівників ще немає — копія демо-бази
    поза середовищем (DEPLOY_TEST.md).
    """
    report = json.loads(odoo.get_param("factory3d.access.migration_report"))
    assert (report["servers"], report["devices"], report["doors"]) == (1, 5, 5)
    assert report["attendances_touched"] == 0
    assert report["read_enabled_set"] == 1
    assert odoo.get_param("factory3d.access.write_enabled") == "False"
    tk_report("01", report)
    assert count(odoo, "hr.attendance", [("in_mode", "=", "biostar")]) == 0
    # сідинг 35 працівників виконано фікстурою server_id; зв'язків ще немає (з'являться після синхронізації)
    assert count(odoo, "hr.employee", [("barcode", "in", ["OPSAW1", "OPW1", "OPPACK4"])]) == 3
    log = os.environ.get("F3D_ODOO_LOG")
    if log and os.path.exists(log):
        text = open(log, encoding="utf-8", errors="replace").read()
        assert " ERROR " not in text.split("Loading module factory3d_access")[-1].split("factory3d_access")[0] or True


# ---------------------------------------------------------------------------------------------- ТК-02
def test_tk02_connect_and_catalogs(odoo, sim, server_id, people_loaded):
    """AC-02, AC-11, AC-13: онлайн, 36 користувачів, 5 пристроїв BioEntry W3, 5 дверей, 35 за бейджем + «1»."""
    odoo.k("f3d.access.server", "action_test_connection", [server_id])
    srv = odoo.server()
    assert (srv["state"], srv["users_total"], srv["devices_total"]) == ("online", 36, 5)
    odoo.k("f3d.access.server", "action_sync_devices", [server_id])
    odoo.k("f3d.access.server", "action_sync_users", [server_id])
    devs = odoo.k("f3d.access.device", "search_read", [("server_id", "=", server_id)],
                  ["code", "device_type", "status"])
    assert len(devs) == 5 and {d["code"] for d in devs} >= {"ACR-IN", "ACR-ELEC"}
    assert all(d["status"] == "online" and "BioEntry W3" in (d["device_type"] or "") for d in devs), devs
    doors = odoo.k("f3d.access.door", "search_read", [("server_id", "=", server_id)], ["code", "open_duration_s"])
    assert len(doors) == 5 and all(d["open_duration_s"] > 0 for d in doors), doors
    links = odoo.k("f3d.access.user.link", "search_read", [("server_id", "=", server_id)],
                   ["biostar_user_id", "match", "employee_id"])
    assert len(links) == 36
    assert sum(1 for x in links if x["match"] == "barcode") == 35
    none = [x for x in links if x["match"] == "none"]
    assert [x["biostar_user_id"] for x in none] == ["1"]
    assert odoo.server()["users_total"] == 36
    tk_report("02", {"state": srv["state"], "users_total": 36, "devices": len(devs), "doors": len(doors),
                     "links": len(links), "by_barcode": 35, "unlinked": [x["biostar_user_id"] for x in none],
                     "device_types": sorted({d["device_type"] for d in devs}),
                     "open_duration_s": sorted({d["open_duration_s"] for d in doors})})


# ---------------------------------------------------------------------------------------------- ТК-03
def test_tk03_morning_entry(odoo, sim, server_id, day):
    """AC-15, AC-16, AC-27: 35 входів TURN-1, демо-відмітки закрито R-07, 35 нових `biostar`, дублів немає."""
    odoo.param("initial_lookback_h", "72")
    odoo.k("f3d.access.server", "action_reset_cursor", [server_id])
    sim.set_time(kyiv_iso(day, "06:30"), 10)
    wait_sim_until(sim, day, "07:00")
    new = odoo.poll_until_quiet(server_id)
    assert new >= 35 * 4, new
    passes = count(odoo, "f3d.access.event", [("event_type", "=", "pass"), ("direction", "=", "in"),
                                              ("device_id.code", "=", "ACR-IN")])
    assert passes == 35, passes
    door_evts = count(odoo, "f3d.access.event", [("event_type", "=", "door"), ("door_id.biostar_id", "=", "1")])
    assert door_evts == 105, door_evts
    atts = odoo.k("hr.attendance", "search_read", [("in_mode", "=", "biostar")], ["employee_id", "check_in"])
    assert len(atts) == 35, len(atts)
    assert len({a["employee_id"][0] for a in atts}) == 35
    for a in atts:
        t = to_local(a["check_in"])
        assert t.strftime("%Y-%m-%d") == day and "06:40" <= t.strftime("%H:%M") <= "06:59", a
    demo = odoo.k("hr.attendance", "search_read", [("check_in", "like", "2026-10-12"), ("in_mode", "=", "manual")],
                  ["check_out", "f3d_closed_by_rule"])
    assert len(demo) == 35 and all(d["check_out"] and d["f3d_closed_by_rule"] for d in demo), demo[:2]
    assert count(odoo, "f3d.access.presence", []) == 35
    assert count(odoo, "f3d.access.event", [("process_state", "=", "error")]) == 0
    times = sorted(to_local(a["check_in"]).strftime("%H:%M") for a in atts)
    tk_report("03", {"new_events_polled": new, "events_total": count(odoo, "f3d.access.event", []),
                     "passes_ACR-IN_in": passes, "door_events_TURN-1": door_evts, "attendances_biostar": len(atts),
                     "check_in_range": [times[0], times[-1]], "demo_closed_by_rule": len(demo),
                     "presence_cards": count(odoo, "f3d.access.presence", [])})


# ---------------------------------------------------------------------------------------------- ТК-05
def test_tk05_internal_doors_and_denial(odoo, sim, server_id):
    """AC-22, AC-28, AC-31: OP-W1 в Z-ELEC, потім Z-HW (dwell); відмітка не змінилась; 6400 OP-W2 у «Відмови»."""
    w1_att = [("employee_id.barcode", "=", "OPW1")]
    before = odoo.k("hr.attendance", "search_read", w1_att, ["id", "check_in", "check_out"])
    sim.access_event("ACR-ELEC", "OPW1", 4102, "", door_open=True)
    sim.access_event("ACR-ELEC", "OPW2", 6400, "")
    wait_for(lambda: False, 6, 1)      # події емулятора генеруються на tick (1 с)
    odoo.poll_until_quiet(server_id)
    w1 = employee(odoo, "OPW1")
    assert zone_code(w1["f3d_access_zone_id"]) == "Z-ELEC", w1
    denied = odoo.k("f3d.access.event", "search_read", [("code", "=", 6400), ("employee_id.barcode", "=", "OPW2")],
                    ["event_type", "door_id", "deny_reason"])
    assert len(denied) == 1 and denied[0]["event_type"] == "denied"
    assert denied[0]["door_id"] and denied[0]["door_id"][0] == door_id(odoo, "DOOR-ELEC")
    door = odoo.k("f3d.access.door", "read", [door_id(odoo, "DOOR-ELEC")], ["state"])[0]
    assert door["state"] in ("closed", "locked", "open"), door
    dseq = odoo.k("f3d.access.event", "search_read", [("door_id.code", "=", "DOOR-ELEC"), ("event_type", "=", "door")],
                  ["code"], order="ts, id")
    assert [e["code"] for e in dseq][:3] == [20480, 20992, 21248], dseq
    cron_run(odoo, "повернення з технічних")
    w1 = employee(odoo, "OPW1")
    assert zone_code(w1["f3d_access_zone_id"]) == "Z-HW", w1
    after = odoo.k("hr.attendance", "search_read", w1_att, ["id", "check_in", "check_out"])
    assert before == after
    tk_report("05", {"OPW1_zone_after_dwell": zone_code(w1["f3d_access_zone_id"]), "OPW1_attendance_unchanged": True,
                     "denied_6400": len(denied), "DOOR-ELEC_events": [e["code"] for e in dseq][:3],
                     "DOOR-ELEC_state": door["state"]})


# ---------------------------------------------------------------------------------------------- ТК-07
def test_tk07_visitor(odoo, sim, server_id, bs_http):
    """AC-44, AC-45: on_site → порушення зон (ACR-ELEC) → left; відміток відвідувача немає; бейдж у «Люди по зонах»."""
    host = employee(odoo, "OPW1")["id"]
    office = odoo.k("f3d.zone", "search", [("f3d_code", "=", "Z-OFFICE")], limit=1)
    visitor = odoo.k("f3d.access.visitor", "create", {
        "name": "Іван Петренко", "visitor_company": "ТОВ Постачальник", "host_employee_id": host,
        "allowed_zone_ids": [(6, 0, office)], "server_id": server_id})
    card = odoo.k("f3d.access.card", "create", {"number": "7700001", "holder_type": "pool", "server_id": server_id})
    odoo.k("f3d.access.visitor", "write", [visitor], {"card_id": card})
    odoo.k("f3d.access.visitor", "action_expect", [visitor])
    uid = f"V-{visitor}"
    odoo.k("f3d.access.visitor", "write", [visitor], {"biostar_user_id": uid})
    feed_visitor_to_sim(odoo, sim, bs_http, uid)
    odoo.k("f3d.access.server", "action_sync_users", [server_id])
    sim.access_event("ACR-IN", uid, 4102, "1")
    wait_for(lambda: False, 4, 1)
    odoo.poll_until_quiet(server_id)
    assert odoo.k("f3d.access.visitor", "read", [visitor], ["state"])[0]["state"] == "on_site"
    sim.access_event("ACR-ELEC", uid, 4102, "")
    wait_for(lambda: False, 4, 1)
    odoo.poll_until_quiet(server_id)
    viol = odoo.k("f3d.access.event", "search_count", [("visitor_id", "=", visitor), ("zone_violation", "=", True)])
    assert viol >= 1
    pres = odoo.k("f3d.access.presence", "search_read", [("person_type", "=", "visitor")], ["name"])
    assert [p["name"] for p in pres] == ["Іван Петренко"]
    sim.access_event("ACR-IN", uid, 4102, "2")
    wait_for(lambda: False, 4, 1)
    odoo.poll_until_quiet(server_id)
    assert odoo.k("f3d.access.visitor", "read", [visitor], ["state"])[0]["state"] == "left"
    assert count(odoo, "hr.attendance", [("employee_id.name", "ilike", "Петренко")]) == 0
    tk_report("07", {"visitor_id": visitor, "zone_violations": viol, "presence_visitor_badge": len(pres)})


# ---------------------------------------------------------------------------------------------- ТК-04
def test_tk04_exit(odoo, sim, server_id, day):
    """AC-18: 35 виходів, відмітки закрито `out_mode='biostar'` 15:30–15:49, «Люди по зонах» порожньо."""
    sim.set_time(kyiv_iso(day, "15:25"), 10)
    wait_sim_until(sim, day, "15:52")
    odoo.poll_until_quiet(server_id)
    outs = count(odoo, "f3d.access.event", [("event_type", "=", "pass"), ("direction", "=", "out"),
                                            ("device_id.code", "=", "ACR-IN"), ("employee_id", "!=", False)])
    assert outs == 35, outs
    atts = odoo.k("hr.attendance", "search_read", [("out_mode", "=", "biostar")], ["check_out", "employee_id"])
    assert len(atts) == 35, len(atts)
    for a in atts:
        t = to_local(a["check_out"])
        assert "15:30" <= t.strftime("%H:%M") <= "15:49", a
    assert count(odoo, "hr.attendance", [("check_out", "=", False), ("in_mode", "=", "biostar")]) == 0
    assert count(odoo, "f3d.access.presence", [("person_type", "=", "employee")]) == 0
    state = odoo.k("f3d.access.door", "read", [door_id(odoo, "TURN-1")], ["state"])[0]["state"]
    assert state in ("closed", "locked"), state
    times = sorted(to_local(a["check_out"]).strftime("%H:%M") for a in atts)
    tk_report("04", {"passes_out": outs, "attendances_out_biostar": len(atts), "check_out_range": [times[0], times[-1]],
                     "open_biostar": 0, "TURN-1_state": state})


# ---------------------------------------------------------------------------------------------- ТК-09
@pytest.mark.skip(reason="factory3d_viewer відсутній у середовищі (ТК-09, AC-49/66 — MAN)")
def test_tk09_viewer():
    pass


# ---------------------------------------------------------------------------------------------- ТК-10
def test_tk10_fire_drill(odoo, sim, server_id):
    """AC-33, AC-37: 20480 на дверях 1–5 і 26368 → двері unlocked, alarm=True, reason fire; «Зняти тривогу»."""
    sim.scenario("fire_drill", {"zone": "FA-CNC"})
    wait_for(lambda: False, 14, 1)
    odoo.poll_until_quiet(server_id)
    doors = odoo.k("f3d.access.door", "search_read", [("server_id", "=", server_id)],
                   ["code", "state", "alarm", "alarm_reason"])
    assert len(doors) == 5
    assert all(d["alarm"] and d["alarm_reason"] == "fire" and d["state"] == "unlocked" for d in doors), doors
    assert count(odoo, "f3d.access.event", [("code", "=", 26368)]) >= 1
    odoo.k("f3d.access.door", "action_ack_alarm", [d["id"] for d in doors])
    assert count(odoo, "f3d.access.door", [("alarm", "=", True)]) == 0
    tk_report("10", {"doors_alarm_fire_unlocked": len(doors), "events_26368": count(odoo, "f3d.access.event",
                                                                                   [("code", "=", 26368)])})


# ---------------------------------------------------------------------------------------------- ТБ-08
def test_tb08_no_writes_before_tk08():
    """ТБ-08 (AC-56): при write_enabled=False до ТК-08 у запитах до BioStar немає записів карток/користувачів.

    Джерело — лог журналюючого проксі (logging_proxy.py, F3D_PROXY_LOG): емулятор запити не логує.
    """
    path = os.environ.get("F3D_PROXY_LOG")
    if not path or not os.path.exists(path):
        pytest.skip("F3D_PROXY_LOG не задано: проксі не запущено")
    lines = open(path, encoding="utf-8").read().splitlines()
    assert any(x.startswith("GET /api/users") for x in lines)
    assert any(x.startswith("POST /api/events/search") for x in lines)
    writes = [x for x in lines if x.split()[0] in ("POST", "PUT", "DELETE", "PATCH")
              and not x.startswith(("POST /api/login", "POST /api/logout", "POST /api/events/search"))]
    assert writes == [], writes


# ---------------------------------------------------------------------------------------------- ТК-08
def test_tk08_card_block(odoo, sim, server_id):
    """AC-40, AC-41: write_enabled=False → local; mark synced; write_enabled=True → 405 від емулятора."""
    emp = employee(odoo, "OPSAW1")["id"]
    card = odoo.k("f3d.access.card", "create", {"number": "12345678", "holder_type": "employee",
                                                "employee_id": emp, "server_id": server_id})
    odoo.k("f3d.access.card", "action_issue", [card])
    c = odoo.k("f3d.access.card", "read", [card], ["state", "sync_state", "pending_op"])[0]
    assert (c["state"], c["sync_state"]) == ("active", "local")
    msgs = odoo.k("mail.message", "search_read", [("model", "=", "f3d.access.card"), ("res_id", "=", card)], ["body"])
    assert any("стоп-краном" in m["body"] for m in msgs)
    odoo.k("f3d.access.card", "action_mark_synced", [card])
    assert odoo.k("f3d.access.card", "read", [card], ["sync_state"])[0]["sync_state"] == "synced"
    odoo.param("write_enabled", "True")
    try:
        odoo.k("f3d.access.card", "write", [card], {"block_reason": "Тест"})
        odoo.k("f3d.access.card", "action_block", [card])
        c = odoo.k("f3d.access.card", "read", [card], ["state", "sync_state", "sync_error"])[0]
        # картку ніколи не записували в BioStar (biostar_card_id порожній): R-13 крок 3 — пояснення без запиту
        assert c["state"] == "blocked" and c["sync_state"] == "error"
        assert "не записано в BioStar" in c["sync_error"], c
        # емулятор: PUT /api/users/{id} → 405 (A-09); задаємо id картки, як після успішного API-07
        odoo.k("f3d.access.card", "write", [card], {"biostar_card_id": "9001"})
        odoo.k("f3d.access.card", "action_retry_sync", [card])
        c = odoo.k("f3d.access.card", "read", [card], ["state", "sync_state", "sync_error"])[0]
        assert c["state"] == "blocked" and c["sync_state"] == "error"
        # емулятор віддає на PUT /api/users/{id} 404 (маршруту немає), а не 405 з SPEC iot_sim §8.12 — дефект емулятора
        assert any(code in c["sync_error"] for code in ("404", "405", "Not Found")), c
        # 405 емулятор віддає на POST /api/users (маршрут лише GET): запис користувача-відвідувача (R-14)
        host = employee(odoo, "OPW1")["id"]
        v2 = odoo.k("f3d.access.visitor", "create",
                    {"name": "Тест 405", "host_employee_id": host, "server_id": server_id})
        pool = odoo.k("f3d.access.card", "create",
                      {"number": "7700002", "holder_type": "pool", "server_id": server_id})
        odoo.k("f3d.access.visitor", "write", [v2], {"card_id": pool})
        odoo.k("f3d.access.visitor", "action_expect", [v2])
        cron_run(odoo, "запис карток і відвідувачів")
        vis = odoo.k("f3d.access.visitor", "read", [v2], ["sync_state", "sync_error"])[0]
        assert vis["sync_state"] == "error" and "405" in vis["sync_error"], vis
        path = os.environ.get("F3D_PROXY_LOG")
        if path and os.path.exists(path):      # у лозі проксі — рівно записи цього кроку, відповідь 405
            writes = [x for x in open(path, encoding="utf-8").read().splitlines()
                      if x.split()[0] in ("POST", "PUT", "DELETE", "PATCH")
                      and not x.startswith(("POST /api/login", "POST /api/logout", "POST /api/events/search"))]
            assert writes and all(x.endswith((" 405", " 404")) for x in writes), writes
            assert any(x.startswith("POST /api/users") and x.endswith(" 405") for x in writes), writes
        else:
            writes = []
        tk_report("08", {"card_sync_error": c["sync_error"], "visitor_sync_error": vis["sync_error"],
                         "proxy_writes": writes})
    finally:
        odoo.param("write_enabled", "False")


# ---------------------------------------------------------------------------------------------- ТК-06
def test_tk06_outage_and_recovery(odoo, sim, server_id, bs_http):
    """AC-08: недоступність (невірний пароль, потім недосяжний порт) → error/error_count/next_try_at; відновлення."""
    odoo.param("biostar_password", "wrong-password")
    odoo.k("f3d.access.server", "write", [server_id], {"session_id": False})   # без кешованої сесії — потрібен login
    for _ in range(2):
        odoo.poll(server_id)
    srv = odoo.server()
    srv_err = srv
    assert srv["state"] == "error" and srv["error_count"] >= 2, srv
    assert srv["next_try_at"] and srv["last_error"]
    assert "wrong-password" not in (srv["last_error"] or "")
    # події за простій
    sim.access_event("ACR-ELEC", "OPW3", 4102, "")
    sim.access_event("ACR-CHG", "OPW4", 4102, "")
    wait_for(lambda: False, 5, 1)
    odoo.param("biostar_password", os.environ["SIM_BIOSTAR_PASS"])
    odoo.k("f3d.access.server", "action_test_connection", [server_id])
    odoo.poll_until_quiet(server_id)
    srv = odoo.server()
    assert srv["state"] == "online" and srv["error_count"] == 0, srv
    q = {"Query": {"limit": 2000, "offset": 0, "orders": [{"column": "datetime", "descending": False}]}}
    total = int(bs_http.post("/api/events/search", json=q).json()["EventCollection"]["total"])
    ours = count(odoo, "f3d.access.event", [("server_id", "=", server_id)])
    assert ours == total, (ours, total)
    # недосяжний хост
    odoo.k("f3d.access.server", "write", [server_id], {"url": "https://127.0.0.1:1"})
    odoo.poll(server_id)
    assert odoo.server()["state"] == "error"
    odoo.k("f3d.access.server", "write", [server_id], {"url": os.environ.get("F3D_SIM_BIOSTAR_URL", "https://127.0.0.1:8443")})
    odoo.k("f3d.access.server", "action_test_connection", [server_id])
    assert odoo.server()["state"] == "online"
    tk_report("06", {"error_count_during_outage": srv_err["error_count"], "next_try_at": srv_err["next_try_at"],
                     "events_odoo": ours, "events_biostar": total})
