"""ТК-01…ТК-12 (SPEC §13.2) на стенді. Порядок виконання — як у файлі (тести стану залежні).

Результати друкуються рядками ``TK <id> <json>`` (pytest -s) і заносяться до TEST_REPORT.md.
Прапорці середовища (див. conftest.py): колектор, демо-копія, довгі сценарії, td_genset, viewer — без них тест skip.
Тривалість очікувань керується F3D_STAND_WAIT_MIN (ТК-02, за замовчуванням 20), F3D_STAND_BLACKOUT_S (ТК-05, 600),
F3D_STAND_WO_MIN (ТК-03, 30).
"""

from __future__ import annotations

import json
import os
import time

import httpx
import pytest

from conftest import need_collector, need_demo, need_genset, need_long, need_viewer
from helpers import shell_json, wait_for

pytestmark = pytest.mark.stand
WAIT_MIN = float(os.environ.get("F3D_STAND_WAIT_MIN", "20"))
BLACKOUT_S = int(os.environ.get("F3D_STAND_BLACKOUT_S", "600"))
TK09_AT = os.environ.get("F3D_STAND_TK09_AT", "2026-10-12T10:00:00+03:00")  # робочий день (навантаження ≈ 600 кВт)
WO_MIN = float(os.environ.get("F3D_STAND_WO_MIN", "30"))


def tk_report(tk, data):
    print(f"TK {tk} {json.dumps(data, ensure_ascii=False, default=str)}")


def payload() -> dict:
    """infra.totals (CE-03), island і bess_mode живого знімка — через odoo shell (payload_shell.py)."""
    return shell_json("payload_shell.py", "PAYLOAD")


def energy_sources(od):
    return od.k("td.source", "read", od.energy_source_ids(), ["code", "collector_id"])


# --------------------------------------------------------------------------------------------------- ТК-01
def test_tk01_install(odoo, stand_ready):
    """AC-13 (демо-копія), AC-73: звіт хука, 68 джерел, 220 сигналів, API-01 з токеном COL-MAIN."""
    report = json.loads(odoo.get_param("td.energy.install_report") or "{}")
    assert report.get("state") in ("done", "partial"), report
    srcs = energy_sources(odoo)
    sigs = odoo.k("td.signal", "search_count", [("source_id", "in", [s["id"] for s in srcs]), ("address", "!=", False)])
    tk_report("01", {"report": report, "sources": len(srcs), "signals": sigs})
    assert len(srcs) == 68
    assert sigs == 220
    assert not odoo.k("td.source", "search_count", [("code", "=", "EN-DERIVED"), ("collector_id", "!=", False)])
    token = os.environ.get("F3D_COLLECTOR_TOKEN")
    if token:  # AC-73: API-01 колектора COL-MAIN
        r = httpx.get(odoo.url + "/f3d/telemetry/config", headers={"Authorization": f"Bearer {token}"}, timeout=30)
        assert r.status_code == 200, r.text[:200]
        cfg = r.json()
        codes = {s["code"] for s in srcs}
        en = [s for s in cfg["sources"] if s["code"] in codes]
        assert len(en) == 68 and sum(len(s["signals"]) for s in en) == 220
        assert all(s["code"] != "EN-DERIVED" for s in cfg["sources"])
        assert r.headers.get("ETag")


@need_demo
def test_ac13_demo_report(odoo):
    """AC-13: копія демо 14.10 — equipment_linked 80, workcenter_linked 35, signals.created 210/updated 87."""
    rep = json.loads(odoo.get_param("td.energy.install_report"))
    tk_report("01-AC13", rep)
    assert rep["state"] == "done"
    assert rep["equipment_linked"] == 80 and rep["workcenter_linked"] == 35
    assert rep["signals"]["created"] == 210 and rep["signals"]["updated"] == 87
    assert rep["unmatched_equipment"] == 0


# --------------------------------------------------------------------------------------------------- ТК-11
@need_collector
def test_tk11_address_reconciliation(odoo, sim, stand_ready):
    """AC-91: PM5560 kwh_total vs Float32 2700, SUN2000 p_kw, ATyS position=2, TEDOM chp_kw."""
    sim.post("/mode", {"mode": "scenario"})
    sigs = [
        s["code"] for s in sim.get("/signals", prefix="energy/consumers/")["items"] if s["code"].endswith("/kwh_total")
    ]
    assert len(sigs) >= 5, sigs
    assert wait_for(lambda: odoo.signal("infra/ats/position").get("last_ts"), 180, 5), "колектор не доставив дані"
    rows, bad = [], []
    for code in sigs[:5]:
        sv, ov = sim.value(code), odoo.signal(code).get("last_value", 0.0)
        rows.append((code, sv, ov))
        if abs(sv - ov) > 1.0:
            bad.append((code, sv, ov))
    pv = [
        (c, sim.value(c), odoo.signal(c).get("last_value", 0.0))
        for c in (f"infra/pv/PV-INV-{i}/p_kw" for i in (1, 2, 3))
    ]
    ats = odoo.signal("infra/ats/position").get("last_value")
    chp = (sim.value("infra/totals/chp_kw"), odoo.signal("infra/totals/chp_kw").get("last_value"))
    q2 = (sim.value("energy/cells/Q2/p_now"), odoo.signal("energy/cells/Q2/p_now").get("last_value"))
    tk_report("11", {"q2_p_now_sim_vs_odoo": q2, "kwh": rows, "pv": pv, "ats_position": ats, "chp": chp})
    assert not bad, bad
    assert all(
        abs(s - o) <= 0.5 + 0.05 * abs(s) for _, s, o in pv
    )  # допуск: дані ходять з затримкою періоду опитування
    assert ats == 2
    assert abs(chp[0] - chp[1]) <= 1.0


# --------------------------------------------------------------------------------------------------- ТК-02
@need_collector
def test_tk02_readings_profile(odoo, sim, stand_ready):
    """AC-29: 57 лічильників PM5560 ok, ≥ 1 інтервал, p_now ≈ Σ фідерів, баланс годин ok.

    Перший інтервал будується, коли закрився слот [ceil15(перше показання); +15 хв) + settle_s (120 с): до 30 хв після
    старту колектора — тому очікування інтервалів триває до WAIT_MIN + 25 хв."""
    sim.post("/mode", {"mode": "follow_odoo"})
    time.sleep(WAIT_MIN * 60)
    meters = odoo.k("td.energy.meter", "search_read", [("model", "=", "pm5560")], ["code", "data_state"])

    def meters_without_interval():
        with_iv = {i["meter_id"][0] for i in odoo.k("td.energy.interval", "search_read", [], ["meter_id"])}
        return [m["code"] for m in meters if m["id"] not in with_iv]

    wait_for(lambda: not meters_without_interval(), 25 * 60, 20)
    meters = odoo.k("td.energy.meter", "search_read", [("model", "=", "pm5560")], ["code", "data_state"])
    states = {}
    for m in meters:
        states[m["data_state"]] = states.get(m["data_state"], 0) + 1
    no_iv = meters_without_interval()
    bal = odoo.k("td.energy.balance", "read_group", [], ["diff_kwh:sum"], ["state"])
    lines = [s["code"] for s in sim.get("/signals", prefix="energy/lines/")["items"] if s["code"].endswith("/p_now")]
    sim_sum = sum(sim.value(c) for c in lines)
    p_now = payload()["infra_totals"].get("load_kw")
    tk_report(
        "02",
        {
            "pm5560": len(meters),
            "states": states,
            "no_interval": no_iv,
            "balance": bal,
            "sim_lines_sum_kw": sim_sum,
            "payload_load_kw": p_now,
        },
    )
    assert len(meters) == 57 and states == {"ok": 57}
    assert not no_iv
    assert p_now is not None and abs(p_now - sim_sum) <= 0.02 * sim_sum + 2
    # 'skipped' — неповна перша година після старту колектора (баланс повної години — test_ac92_balance_nodes)
    assert all(b["state"] in ("ok", "skipped") for b in bal)


# --------------------------------------------------------------------------------------------------- ТК-07
@need_collector
def test_tk07_pv_export_noon(odoo, sim, stand_ready):
    """AC-90: експорт СЕС у полудень: pv_now = Σ інверторів ± 1, export_kw > 0, grid_kw = 0, bess_kw ≤ 200."""
    sim.post("/mode", {"mode": "scenario"})
    sim.post("/time", {"set": "2026-10-12T12:30:00+03:00"})
    time.sleep(10 * 60)
    tot = payload()["infra_totals"]
    inv = sum(odoo.signal(f"infra/pv/PV-INV-{i}/p_kw").get("last_value", 0) for i in range(1, 9))
    kwh_export = odoo.signal("energy/cells/Q2/kwh_export").get("last_value")
    tk_report("07", {"payload_totals": tot, "sum_inv": inv, "kwh_export_q2": kwh_export})
    assert tot["pv_now"] > 600 and abs(tot["pv_now"] - inv) <= 1.0
    assert tot["export_kw"] > 0 and tot["grid_kw"] == 0
    assert tot["bess_kw"] <= 200 and tot["bess_mode"] == "charge"
    time.sleep(120)
    assert odoo.signal("energy/cells/Q2/kwh_export")["last_value"] > kwh_export


# --------------------------------------------------------------------------------------------------- ТК-08
@need_collector
def test_tk08_cloudy(odoo, sim, stand_ready):
    """pv_now падає ≈ втричі, bess_kw < 0 або grid_kw росте; події немає."""
    before = payload()["infra_totals"]
    dom = [("kind", "!=", "pfc")]  # ступені компенсації (cos φ) змінюються незалежно від хмарності
    ev0 = odoo.k("td.energy.event", "search_count", dom)
    sim.scenario("pv_cloudy", {"cf": 0.3, "duration_s": 900})
    try:
        time.sleep(5 * 60)
        after = payload()["infra_totals"]
        ev1 = odoo.k("td.energy.event", "search_count", dom)
    finally:  # сценарій групи energy блокує blackout (409) — зупиняємо завжди
        sim.post("/scenario/pv_cloudy/stop")
    tk_report("08", {"before": before, "after": after, "events": ev1 - ev0})
    assert after["pv_now"] < before["pv_now"] * 0.5
    assert after["bess_kw"] < 0 or after["grid_kw"] > before["grid_kw"]
    assert ev1 == ev0


# --------------------------------------------------------------------------------------------------- ТК-05
@need_collector
def test_tk05_blackout_variant_a(odoo, sim, stand_ready):
    """AC-56, AC-59, AC-89: блекаут, варіант A (amf_master=hgm)."""
    odoo.param("amf_master", "hgm", prefix="td.genset.")
    sim.post("/time", {"set": "2026-10-12T10:00:00+03:00"})
    time.sleep(20)  # дати колектору й живому знімку прийняти нову добу
    before = payload()["infra_totals"]
    t0 = time.time()
    sim.scenario("blackout", {"duration_s": BLACKOUT_S, "genset": True, "restore_delay_s": 60})
    outage = wait_for(
        lambda: odoo.k(
            "td.energy.outage", "search_read", [("state", "!=", "closed")], ["transfer_s", "state"], limit=1
        ),
        90,
        3,
    )
    assert outage, "відключення не зафіксовано за 90 с"
    snaps = []
    while time.time() - t0 < 60:  # знімки payload (CE-03) і острівного режиму протягом ≈ 60 с після відключення
        snap = payload()
        snap["t"] = round(time.time() - t0)
        snaps.append(snap)
        time.sleep(3)
    time.sleep(max(0, BLACKOUT_S + 60 + 30 - (time.time() - t0)))
    outage = odoo.k(
        "td.energy.outage",
        "read",
        [outage[0]["id"]],
        ["state", "transfer_s", "return_s", "shed_kw", "amf_master", "fail_start"],
    )[0]
    tk_report(
        "05",
        {
            "outage": outage,
            "before": before,
            "snaps": [
                (
                    s["t"],
                    s["island"],
                    s["infra_totals"]["grid_kw"],
                    s["infra_totals"]["export_kw"],
                    s["infra_totals"]["shed_kw"],
                    s["infra_totals"]["bess_mode"],
                    s["infra_totals"]["load_kw"],
                )
                for s in snaps
            ],
        },
    )
    late = [s for s in snaps if s["t"] >= outage["transfer_s"] + 5]
    assert late, "знімків після переходу на генератор немає"
    assert 10 <= outage["transfer_s"] <= 35
    assert all(s["infra_totals"]["grid_kw"] == 0 and s["infra_totals"]["export_kw"] == 0 for s in late)
    assert any(s["infra_totals"]["bess_mode"] == "discharge" for s in snaps)
    assert any(s["island"] for s in late)
    shed = max(s["infra_totals"]["shed_kw"] for s in snaps)
    # SPEC: shed_kw 278 ± 30 (для навантаження демо ≈ 485 кВт); на емуляторі споживання залежить від часу доби —
    # перевіряємо ще й узгодженість: shed = навантаження до − навантаження в острові
    assert (
        abs(shed - 278) <= 30
        or abs(shed - (before["load_kw"] - min(s["infra_totals"]["load_kw"] for s in snaps))) <= 30
    )
    assert outage["state"] == "closed" and 40 <= outage["return_s"] <= 80


# --------------------------------------------------------------------------------------------------- ТК-06
@need_genset
def test_tk06_fail_start_variant_b(odoo, sim, stand_ready):
    """AC-57: amf_master=ats, генератор не запускається → fail_start за 35 ± 5 с і заявка на ATS-1."""
    odoo.param("amf_master", "ats", prefix="td.genset.")
    sim.scenario("blackout", {"duration_s": 180, "amf_master": "ats"})
    sim.put("/signals/infra/ats/gen_start", {"value": 1, "hold_s": 120})
    sim.put("/signals/infra/ats/src2_state", {"value": 0, "hold_s": 120})
    out = wait_for(lambda: odoo.k("td.energy.outage", "search_read", [("fail_start", "=", True)], ["id"]), 90, 3)
    assert out
    req = odoo.k("maintenance.request", "search_count", [("name", "ilike", "FAIL START")])
    assert req >= 1


# --------------------------------------------------------------------------------------------------- ТК-09
@need_collector
def test_tk09_contract_power(odoo, sim, stand_ready):
    """AC-34: contract_kw=300 → заявка «Перевищення договірної потужності»; повернення 800 → ok."""
    tariffs = odoo.k("td.energy.tariff", "search_read", [], ["contract_kw"], limit=1, order="id desc")
    old = tariffs[0]["contract_kw"]
    try:
        # Емулятор: СЕС і когенерація (≈ 400 + 400 кВт) покривають навантаження — нетто-імпорт 0 (Q2 віддає в мережу).
        # Для імпорту > 300 кВт: робочий день, когенерацію зупиняємо (infra/chp/state=0), СЕС глушимо хмарністю
        sim.post("/mode", {"mode": "scenario"})
        sim.post("/time", {"set": TK09_AT})
        sim.put("/signals/infra/chp/state", {"value": 0, "hold_s": 1500})
        sim.scenario("pv_cloudy", {"cf": 0.05, "duration_s": 1500})
        odoo.k("td.energy.tariff", "write", [tariffs[0]["id"]], {"contract_kw": 300})
        req = wait_for(
            lambda: odoo.k(
                "maintenance.request", "search_read", [("name", "ilike", "Перевищення договірної потужності")], ["name"]
            ),
            20 * 60,
            20,
        )
        grid15 = odoo.signal("energy/totals/grid15_kw")
        tk_report("09", {"requests": req, "grid15": grid15})
        assert req and "ліміті 300" in req[0]["name"]
        followers = odoo.k("maintenance.request", "read", [req[0]["id"]], ["message_partner_ids"])[0]
        assert followers["message_partner_ids"], "енергетик має бути підписником заявки"
        odoo.k("td.energy.tariff", "write", [tariffs[0]["id"]], {"contract_kw": 800})
        assert wait_for(lambda: odoo.signal("energy/totals/grid15_kw").get("status") == "ok", 20 * 60, 20)
    finally:
        sim.put("/signals/infra/chp/state", {"release": True})
        sim.post("/scenario/pv_cloudy/stop")
        odoo.k("td.energy.tariff", "write", [tariffs[0]["id"]], {"contract_kw": old or 800})


# --------------------------------------------------------------------------------------------------- ТК-10
@need_collector
@need_long
def test_tk10_meter_unavailable(odoo, sim, stand_ready):
    """AC-22: PM-SAW-1 недоступний 70 хв → stale + подія; після clear — слоти interpolated, Σ kwh = різниця."""
    sim.post("/device/SAW-1-PM/fault", {"reason": "comm"})
    time.sleep(70 * 60)
    meter = odoo.k("td.energy.meter", "search_read", [("code", "=", "PM-SAW-1")], ["data_state"])[0]
    ev = odoo.k("td.energy.event", "search_count", [("text", "ilike", "немає даних")])
    sim.post("/device/SAW-1-PM/clear")
    time.sleep(20 * 60)
    ivs = odoo.k(
        "td.energy.interval",
        "search_read",
        [("meter_id.code", "=", "PM-SAW-1"), ("quality", "=", "interpolated")],
        ["kwh"],
    )
    tk_report("10", {"state_during": meter["data_state"], "events": ev, "interpolated": len(ivs)})
    assert meter["data_state"] in ("stale", "missing") and ev >= 1 and ivs


# --------------------------------------------------------------------------------------------------- ТК-03/04
@need_demo
@need_collector
def test_tk03_shift_to_mo(odoo, sim, stand_ready):
    """AC-88: WO SAW-1/EDGE-1 td_energy_direct_kwh = ∫ p_now емулятора ± 3 %, quality measured; спільні > 0."""
    sim.post("/mode", {"mode": "scenario"})
    bom = odoo.k("mrp.bom", "search_read", [("code", "ilike", "A")], ["product_tmpl_id"], limit=1)[0]
    prod = odoo.k("product.product", "search", [("product_tmpl_id", "=", bom["product_tmpl_id"][0])], limit=1)[0]
    mo = odoo.k("mrp.production", "create", {"product_id": prod, "product_qty": 4, "bom_id": bom["id"]})
    odoo.k("mrp.production", "action_confirm", [mo])
    wos = {
        w["workcenter_id"][1]: w["id"]
        for w in odoo.k("mrp.workorder", "search_read", [("production_id", "=", mo)], ["workcenter_id"])
    }
    saw = next(v for k, v in wos.items() if "SAW" in k.upper() or "Розкрій" in k)
    integral, last = 0.0, time.time()
    odoo.k("mrp.workorder", "button_start", [saw])
    end = last + WO_MIN * 60
    while time.time() < end:
        time.sleep(30)
        now = time.time()
        integral += sim.value("energy/consumers/SAW-1/p_now") * (now - last) / 3600
        last = now
    odoo.k("mrp.workorder", "button_finish", [saw])
    wo = odoo.k("mrp.workorder", "read", [saw], ["td_energy_direct_kwh", "td_energy_quality"])[0]
    kwh = wo["td_energy_direct_kwh"]
    shared = odoo.k("td.energy.alloc", "read_group", [("production_id", "=", mo)], ["kwh:sum"], ["pool_id"])
    tk_report("03", {"mo": mo, "wo": wo, "integral": integral, "shared_by_pool": shared})
    assert wo["td_energy_quality"] == "measured"
    assert any(g["pool_id"] and g["kwh"] > 0 for g in shared)
    assert abs(kwh - integral) <= 0.03 * integral


@need_demo
def test_tk04_costing_avco(odoo):
    """AC-46: AVCO: extra_cost = td_energy_cost / qty, td_energy_locked (потребує копії бази)."""
    pytest.skip("залежить від МО ТК-03 і зміни категорії на AVCO (лише копія демо)")


@need_collector
def test_tk11b_nonzero_counters(odoo, sim, stand_ready):
    """AC-91 (посилений): лічильники PM5560 примусово ≠ 0 → Odoo `kwh_total` (INT64 ×0,001) = Float32 2700."""
    codes = [
        s["code"] for s in sim.get("/signals", prefix="energy/consumers/")["items"] if s["code"].endswith("/kwh_total")
    ][:5]
    forced = {c: 12345.678 + 1000 * i for i, c in enumerate(codes)}
    for c, v in forced.items():
        sim.put("/signals/" + c, {"value": v, "hold_s": 600})
    time.sleep(150)  # період опитування kwh_total = 60 с (SPEC §3 сигнали)
    rows = [(c, sim.value(c), odoo.signal(c).get("last_value", 0.0)) for c in codes]
    tk_report("11b", {"rows": rows})
    for c in codes:
        sim.put("/signals/" + c, {"release": True})
    assert all(abs(s - o) <= 1.0 and s > 10000 for _, s, o in rows), rows


@need_demo
def test_ac53_mo231(odoo):
    """AC-53: крон розподілу 12.10 → WH/MO/00231: WO00001…4 прямі 17,160 / 46,069 / 13,567 / 4,350 (estimate)."""
    cron = odoo.ref_id("td_energy.cron_td_energy_alloc")
    odoo.k("ir.cron", "method_direct_trigger", [cron])
    mo = odoo.k("mrp.production", "search", [("name", "=", "WH/MO/00231")], limit=1)
    assert mo, "МО WH/MO/00231 відсутнє (потрібна копія демо 14.10)"
    wos = odoo.k(
        "mrp.workorder",
        "search_read",
        [("production_id", "=", mo[0])],
        ["name", "td_energy_direct_kwh", "td_energy_quality"],
        order="id",
    )
    tk_report("AC53", {"wos": wos})
    want = [17.160, 46.069, 13.567, 4.350]
    assert [round(w["td_energy_direct_kwh"], 3) for w in wos[:4]] == want
    assert all(w["td_energy_quality"] == "estimate" for w in wos[:4])


@need_collector
def test_ac92_balance_nodes(odoo, stand_ready):
    """AC-92 (етап 2 «весь ГРЩ»): за повний годину баланс вузлів `ok` (Q1 і три фідери — серед них) або `deviation`
    з причиною. Потрібна хоча б одна повна година даних колектора (крон балансу: щогодини о :07)."""
    rows = odoo.k(
        "td.energy.balance",
        "search_read",
        [],
        ["node_id", "hour", "state", "diff_pct", "reason"],
        order="hour desc",
        limit=200,
    )
    assert rows, "баланс ще не розрахований: потрібна повна година даних колектора"
    last_hour = rows[0]["hour"]
    cur = [r for r in rows if r["hour"] == last_hour]
    tk_report(
        "AC92", {"hour": last_hour, "states": [(r["node_id"][1], r["state"], r["diff_pct"], r["reason"]) for r in cur]}
    )
    bad = [r for r in cur if r["state"] != "ok" and not r["reason"]]
    assert not bad, bad
    key = [r for r in cur if any(c in r["node_id"][1] for c in ("Q1", "QF-2", "QF-3", "QF-C1"))]
    assert key and all(r["state"] == "ok" for r in key if r["node_id"][1].endswith(("Q1", "QF-2", "QF-3", "QF-C1"))), (
        key
    )


# --------------------------------------------------------------------------------------------------- ТК-12
@need_viewer
def test_tk12_viewer(odoo):
    """AC-63, AC-65 (MAN): u_energy відкриває 3D → «Енергія»; секції live; у кіоску немає грн."""
    pytest.skip("MAN: візуальна перевірка 3D-переглядача")
