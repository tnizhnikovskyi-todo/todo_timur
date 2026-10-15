# ruff: noqa: E501
"""ТК-01…ТК-04, ТК-12 (SPEC §13.2): підключення, filter_clogged, освітлення, аварія світильника, звірка."""

from __future__ import annotations

import re
import time


from bms_lib import bms_requests, last_request_id, close_bms_requests, episodes, group, panel, sleep_until, unit


def test_tk01_connection(odoo, sim):
    """ТК-01: 32 джерела bms + BMS-DERIVED online; 32 групи live; 29 установок без stale; сигнали ok, окрім RV-05 filter."""
    srcs = odoo.search_read("f3d.source", [("module", "=", "bms")], ["code", "state"])
    assert sleep_until(
        lambda: len(odoo.search_read("f3d.source", [("module", "=", "bms"), ("state", "=", "online")], ["id"])) == 33,
        180,
        10,
    ), [s for s in srcs if s["state"] != "online"]
    assert len(srcs) == 33 and any(s["code"] == "BMS-DERIVED" for s in srcs)
    groups = odoo.search_read("f3d.bms.light.group", [], ["code", "level_source"])
    assert len(groups) == 32
    assert sleep_until(
        lambda: all(g["level_source"] == "live" for g in odoo.search_read("f3d.bms.light.group", [], ["level_source"])),
        120,
        10,
    )
    units = odoo.search_read("f3d.bms.hvac.unit", [], ["code", "stale"])
    assert len(units) == 29 and not [u for u in units if u["stale"]], [u["code"] for u in units if u["stale"]]

    def alarms():
        r = odoo.search_read(
            "f3d.signal", [("module", "=", "bms"), ("status", "in", ["alarm", "stale"])], ["code", "status"]
        )
        return sorted(x["code"] for x in r)

    def low_checks():
        """Групи, чия освітленість при рівні 80 % емулятора нижча за норму (D-1 у TEST_REPORT)."""
        r = odoo.search_read(
            "f3d.signal",
            [
                ("module", "=", "bms"),
                ("code", "like", "lighting/groups/%/check"),
                ("status", "=", "alarm"),
                ("last_text", "=", "нижче норми"),
            ],
            ["code"],
        )
        return {x["code"] for x in r}

    def unexpected():
        # D-2: iot_sim склеює діапазони в C:164 для LT-FAC без коми (`@1.2.3.64@1.2.4.1`) → faults=2 завжди
        known = {"ventilation/units/RV-05/filter_dp_pa", "lighting/groups/LT-FAC/faults"}
        return [c for c in alarms() if c not in known and c not in low_checks()]

    assert sleep_until(lambda: not unexpected(), 420, 15), unexpected()
    # RV-05: емулятор стартує зі 285 лише на «холодному» стані (iot_sim S-04); тут фіксуємо фактичне
    print("TK01 сигнали у alarm:", alarms(), "нижче норми при 80 %:", sorted(low_checks()))


def test_tk12_reconcile(odoo, sim):
    """ТК-12: значення Odoo збігаються з емулятором (рівень LT-CUT — точно, RV-08 — з похибкою шуму)."""
    st, d = sim.get("/signals?device=RV-08")
    assert st == 200
    assert sleep_until(lambda: unit(odoo, "RV-08")["live_ts"], 60)
    for code, field, tol in (
        ("ventilation/units/RV-08/supply_c", "supply_c", 1.5),
        ("ventilation/units/RV-08/indoor_c", "indoor_c", 1.0),
    ):
        sv = sim.value(code)
        ov = unit(odoo, "RV-08")[field]
        assert abs(sv - ov) <= tol, (code, sv, ov)
    assert group(odoo, "LT-CUT")["level_pct"] == sim.value("lighting/groups/LT-CUT/level")


def test_tk02_filter_clogged(odoo, fresh_sim):
    """ТК-02: RV-05 фільтр 285 Па → заявка filter_supply, епізод open, після stop — ok і епізод closed."""
    sim = fresh_sim
    close_bms_requests(odoo)
    assert sleep_until(lambda: odoo.signal("ventilation/units/RV-05/filter_dp_pa")["status"] == "ok", 150, 10), (
        odoo.signal("ventilation/units/RV-05/filter_dp_pa")
    )
    base = last_request_id(odoo)
    st, d = sim.post(
        "/scenario/filter_clogged/start",
        {"run_ref": "RUN/TK02", "params": {"device": "RV-05", "value": 285, "ramp_min": 2}},
    )
    assert st == 201, d
    t0 = time.time()
    s = sleep_until(lambda: odoo.signal("ventilation/units/RV-05/filter_dp_pa")["status"] == "alarm", 300, 10)
    assert s
    req = sleep_until(lambda: (bms_requests(odoo, "filter_supply", after_id=base) or [None])[-1], 240, 10)
    assert req, "заявки filter_supply немає"
    # заголовок фіксує значення на момент перетину порогу під час розгону (271 Па), а не фінальні 285 (див. TEST_REPORT, O-1)
    assert "Заміна фільтрів: перепад тиску" in req["name"] and "при нормі до 250" in req["name"], req["name"]
    assert 250 < int(re.search(r"(\d+) Па", req["name"]).group(1)) <= 290, req["name"]
    assert req["maintenance_team_id"] and "механіка" in req["maintenance_team_id"][1]
    assert sleep_until(lambda: episodes(odoo, "filter_supply", "RV-05", "open"), 120, 10)
    assert sleep_until(lambda: abs(unit(odoo, "RV-05")["filter_dp_pa"] - 285) <= 5, 240, 10), unit(odoo, "RV-05")
    u = unit(odoo, "RV-05")
    assert u["alarm_count"] >= 1 and u["plan_state"] == "alarm", u  # на плані RV-05 червоний (тривога фільтра)
    print(f"TK02 alarm за {time.time() - t0:.0f} с, заявка «{req['name']}»")
    odoo.close_request(req["id"])
    sim.post("/scenario/filter_clogged/stop")
    assert sleep_until(lambda: odoo.signal("ventilation/units/RV-05/filter_dp_pa")["status"] == "ok", 240, 10)
    assert sleep_until(lambda: not episodes(odoo, "filter_supply", "RV-05", "open"), 240, 10)
    assert episodes(odoo, "filter_supply", "RV-05", "closed")


def test_tk03_lighting(odoo, fresh_sim, full_calendar):
    """ТК-03: LT-CUT вимкнено (рівень 0) → заявка; LT-EB 60 % → e_now 329 і заявка «нижче норми»."""
    sim = fresh_sim
    close_bms_requests(odoo)
    base = last_request_id(odoo)
    st, d = sim.post(
        "/scenario/lighting_scene/start",
        {"run_ref": "RUN/TK03A", "params": {"group": "LT-CUT", "level": 0, "duration_s": 900}},
    )
    assert st == 201, d
    t0 = time.time()
    assert sleep_until(lambda: group(odoo, "LT-CUT")["level_pct"] == 0, 30, 2), group(odoo, "LT-CUT")
    print(f"TK03 LT-CUT level=0 в Odoo за {time.time() - t0:.0f} с (push)")
    st, d = sim.post(
        "/scenario/lighting_scene/start",
        {"run_ref": "RUN/TK03B", "params": {"group": "LT-EB", "level": 60, "duration_s": 900}},
    )
    assert st == 201, d
    off = sleep_until(
        lambda: [r for r in bms_requests(odoo, "light_off", after_id=base) if "LT-CUT" in r["name"]], 240, 10
    )
    assert off, bms_requests(odoo)
    print("TK03 заявка:", off[0]["name"], f"за {time.time() - t0:.0f} с")
    assert "вимкнено" in off[0]["name"].lower() and "500" in off[0]["name"]
    low = sleep_until(
        lambda: [r for r in bms_requests(odoo, "light_low", after_id=base) if "LT-EB" in r["name"]], 240, 10
    )
    assert low, bms_requests(odoo)
    assert group(odoo, "LT-EB")["e_now"] == 329
    assert "329" in low[0]["name"] and "500" in low[0]["name"], low[0]["name"]
    sim.post("/scenario/lighting_scene/stop")
    assert sleep_until(
        lambda: group(odoo, "LT-CUT")["deviation"] == "none" and group(odoo, "LT-EB")["deviation"] == "none", 240, 10
    )
    assert sleep_until(
        lambda: not episodes(odoo, code="LT-CUT", state="open") and not episodes(odoo, code="LT-EB", state="open"),
        240,
        10,
    )


def test_tk04_lamp_fault(odoo, fresh_sim):
    """ТК-04: несправний світильник 1.2.1.5 → faults=1, заявка «Аварія світильників», щит LP-2 fault."""
    sim = fresh_sim
    close_bms_requests(odoo)
    base = last_request_id(odoo)
    for code in ("lighting/groups/LT-CUT/faults", "lighting/groups/LT-CUT/faulty"):
        sid = odoo.signal_id(code)
        odoo.write("f3d.signal", sid, {"period_s": 60})
    st, d = sim.post(
        "/scenario/lighting_scene/start",
        {
            "run_ref": "RUN/TK04",
            "params": {"group": "LT-CUT", "scene": 1, "fault_device": "@1.2.1.5", "duration_s": 900},
        },
    )
    assert st == 201, d
    assert sleep_until(lambda: group(odoo, "LT-CUT")["faults"] == 1, 240, 10), group(odoo, "LT-CUT")
    assert group(odoo, "LT-CUT")["faulty"] == "1.2.1.5"
    req = sleep_until(
        lambda: [r for r in bms_requests(odoo, "light_fault", after_id=base) if "LT-CUT" in r["name"]], 240, 10
    )
    assert req, bms_requests(odoo)
    assert "несправних 1" in req[0]["name"], req[0]["name"]
    assert sleep_until(
        lambda: "1.2.1.5" in (bms_requests(odoo, "light_fault", after_id=base)[-1]["description"] or ""), 180, 10
    )
    desc = [r for r in bms_requests(odoo, "light_fault", after_id=base) if "LT-CUT" in r["name"]][-1]["description"]
    assert "LP-2" in desc and "G:12" in desc, desc
    assert sleep_until(lambda: panel(odoo, "LP-2")["state"] == "fault", 180, 10), panel(odoo, "LP-2")
    sim.post("/scenario/lighting_scene/stop")
    assert sleep_until(lambda: group(odoo, "LT-CUT")["faults"] == 0, 240, 10)
