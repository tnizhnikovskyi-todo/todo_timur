"""ТК-01…ТК-06 (W3_SPEC 13.2) на стенді: екран «Енергоресурси», нові сигнали, стик історії й живих даних, витік повітря,
перевитрата газу, експорт xlsx (AC-45, AC-59, AC-62).

Передумови E-11: емулятор `iot_sim` (з газом, повітрям, водою, котлом, kvarh) + збирач + Odoo із `td_energy`,
`td_energy_resources`, `td_bms`, `td_energy_resources_bms`; електричний `_td_backfill(days=90)` виконано ≥ 5 хв після
старту збирача, потім `td.energy.res.interval._td_backfill(days=90)`. Без `F3D_ODOO_URL` усі тести пропускаються.

Запуск (клієнти XML-RPC і /sim/v1 — із стенда `td_energy`; з каталогу файлу, бо `tests/` — пакет Odoo-модуля):

    cd odoo_addons/td_energy_resources/tests/stand
    pytest -p no:cacheprovider -o "markers=stand: стенд" -s test_w3_tk.py

Змінні: F3D_ODOO_URL/DB/USER/PASSWORD, SIM_API_URL, SIM_API_TOKEN (як у `td_energy`); F3D_STAND_COLLECTOR=1 (збирач шле
дані: ТК-01…ТК-03, ТК-05, ТК-06), F3D_STAND_LONG=1 (сценарії > 30 хв: ТК-01 на 10 хв, ТК-04, лінія ліміту в ТК-05);
F3D_W3_TK04_PHASE=start|check|expire (ТК-04, за замовчуванням `check`): `start` увечері запускає `air_leak` і виходить;
`check` після ≥ 1 ночі перевіряє KPI й резерв, потім зупиняє сценарій; `expire` наступного ранку (після ночі без витоку)
запускає правило й перевіряє, що резерв став `expired`. Результати друкуються рядками ``TK <id> <json>`` (pytest -s).
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

HELPERS = Path(__file__).resolve().parents[3] / "td_energy" / "tests" / "stand" / "helpers.py"
RES = "td.energy.res.dashboard"
RULE = "td.energy.opportunity.rule"
OPP = "td.energy.opportunity"
INTERVAL = "td.energy.res.interval"
TABS = ["el", "gas", "heat", "air", "water"]
# 10 сигналів SPEC 5.4: (код, лічильник?)
SIGNALS = [
    ("infra/gas/m3_total", True),
    ("infra/gas/flow_m3h", False),
    ("equipment/BOILER/gas_m3h", False),
    ("air/flow_m3min", False),
    ("air/m3_total", True),
    ("air/pressure_bar", False),
    ("infra/water/boiler_m3_total", True),
    ("infra/water/boiler_flow_m3h", False),
    ("energy/cells/Q1/kvarh_total", True),
    ("energy/cells/Q2/kvarh_total", True),
]
# підживлення котельні 0,0125 м³/год при кванті 0,01 м³ дає імпульс раз на ~48 хв: за хвилини лічильник лише не спадає
SLOW_COUNTERS = {"infra/water/boiler_m3_total"}
LIMIT_H = 80.0  # ліміт години газу, м³/год (SPEC 8.1, ТК-05)
DRY_M3H, CANTEEN_M3H = 6.0, 1.0  # необліковані гілки корректора GAS-MAIN (SPEC 8.1)


def _flag(name: str) -> bool:
    return os.environ.get(name) == "1"


pytestmark = [
    pytest.mark.stand,
    pytest.mark.skipif(not os.environ.get("F3D_ODOO_URL"), reason="F3D_ODOO_URL не задано: стенд не піднято"),
]
need_collector = pytest.mark.skipif(
    not _flag("F3D_STAND_COLLECTOR"), reason="збирач не запущено (F3D_STAND_COLLECTOR=1)"
)
need_long = pytest.mark.skipif(not _flag("F3D_STAND_LONG"), reason="сценарій > 30 хв: F3D_STAND_LONG=1")


def tk_report(tk: str, data: dict) -> None:
    print(f"TK {tk} {json.dumps(data, ensure_ascii=False, default=str)}")


@pytest.fixture(scope="session")
def h():
    """Модуль клієнтів стенда `td_energy` (Odoo XML-RPC, /sim/v1) — підключається за шляхом, без sys.path."""
    spec = importlib.util.spec_from_file_location("td_energy_stand_helpers", HELPERS)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def odoo(h):
    return h.Odoo(
        h.env("F3D_ODOO_URL"), h.env("F3D_ODOO_DB"), h.env("F3D_ODOO_USER", "admin"), h.env("F3D_ODOO_PASSWORD")
    )


@pytest.fixture(scope="session")
def sim(h):
    return h.Sim(h.env("SIM_API_URL", "http://127.0.0.1:8090"), h.env("SIM_API_TOKEN"))


@pytest.fixture(scope="session")
def stand_ready(odoo):
    """Середовище test, читання з емулятора дозволено, запис — ні; модуль ресурсів встановлено."""
    assert odoo.get_param("td.base.environment") == "test"
    odoo.param("read_enabled", "True")
    odoo.param("write_enabled", "False")
    assert odoo.k(
        "ir.module.module", "search_count", [("name", "=", "td_energy_resources"), ("state", "=", "installed")]
    )
    return True


# --- допоміжні -------------------------------------------------------------------------------------------
def parse_utc(text: str) -> datetime:
    return datetime.strptime(text[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")


def utc_now() -> datetime:
    """Поточний час UTC без зони: так Odoo віддає Datetime через XML-RPC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fmt_utc(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def kpi(data: dict, kpi_id: str) -> dict:
    found = [k for k in data["resource"]["kpis"] if k["id"] == kpi_id]
    assert found, f"KPI {kpi_id} немає у вкладці {data['resource']['code']}"
    return found[0]


def screen(odoo, code: str) -> dict:
    return odoo.k(RES, "get_resources", code)


def sig_row(odoo, code: str) -> dict:
    row = odoo.signal(code)
    assert row, f"td.signal {code} не створено (hooks._ensure_resource_signals)"
    return row


def last_value(odoo, code: str) -> float:
    value = sig_row(odoo, code).get("last_value")
    assert value is not None, f"{code}: немає значення"
    return float(value)


def stop_scenario(sim, name: str) -> None:
    try:
        sim.post(f"/scenario/{name}/stop")
    except Exception as exc:  # сценарій уже зупинено або не запущено — не заважає наступним тестам
        print(f"TK stop {name}: {exc}")


def active_runs(sim, name: str) -> list[dict]:
    return [r for r in sim.get("/runs") if r.get("name") == name and r.get("state") in ("running", "stopping")]


def pct_of(note: str) -> float:
    found = re.search(r"(\d+(?:[.,]\d+)?)\s*%", note or "")
    assert found, f"у підписі «{note}» немає відсотка"
    return float(found.group(1).replace(",", "."))


def wait_until(cond, minutes: float, step: float = 20.0) -> bool:
    end = time.monotonic() + minutes * 60
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(step)
    return bool(cond())


# --- ТК-01 -----------------------------------------------------------------------------------------------
@need_collector
def test_tk01_screen_live(odoo, sim, stand_ready):
    """ТК-01 (AC-59): 5 вкладок, KPI заповнені, `data_state='ok'`, графік за годину цілий, значення змінюються."""
    minutes = 10 if _flag("F3D_STAND_LONG") else 2
    first = {code: screen(odoo, code) for code in TABS}
    assert [t["code"] for t in first["gas"]["tabs"]] == TABS
    for code in TABS:
        assert first[code]["meta"]["data_state"] == "ok", f"{code}: {first[code]['meta']}"
    for code in ("el", "gas", "air", "water"):  # тепло в ядрі — «—» без моста BMS
        empty = [k["id"] for k in first[code]["resource"]["kpis"] if k["value"] is None]
        assert not empty, f"{code}: порожні KPI {empty}"
    time.sleep(minutes * 60)
    last = {code: screen(odoo, code) for code in TABS}
    for code in ("gas", "air", "water"):
        chart = last[code]["resource"]["chart"]
        assert len(chart["series"]) == 96
        hour = chart["series"][max(0, chart["now_slot"] - 4) : chart["now_slot"]]
        assert hour and None not in hour, f"{code}: розрив графіка за останню годину {hour}"
    assert last["gas"]["meta"]["now"] > first["gas"]["meta"]["now"]
    changed = [
        code
        for code, kid in (("gas", "rate"), ("air", "rate"), ("water", "rate"), ("el", "grid_now"))
        if kpi(first[code], kid)["value"] != kpi(last[code], kid)["value"]
    ]
    air_sim = sim.value("air/flow_m3min")
    air_kpi = kpi(last["air"], "rate")["value"]
    tk_report("01", {"minutes": minutes, "changed_kpis": changed, "air_kpi": air_kpi, "air_sim": air_sim})
    assert changed, "значення KPI не змінилися за час спостереження"
    assert abs(air_kpi - air_sim) <= 0.15 * max(air_sim, 1.0), "KPI повітря не відповідає емулятору"


# --- ТК-02 -----------------------------------------------------------------------------------------------
@need_collector
def test_tk02_new_signals(odoo, sim, stand_ready):
    """ТК-02: 10 нових сигналів `status='ok'`, `last_ts` ≤ 2 хв, лічильники ростуть, газ ≈ сума гілок ±5 %."""
    before = {code: sig_row(odoo, code) for code, _ in SIGNALS}
    now = utc_now()
    report: dict[str, dict] = {}
    for code, _counter in SIGNALS:
        row = before[code]
        age = (now - parse_utc(row["last_ts"])).total_seconds() if row.get("last_ts") else None
        report[code] = {"status": row.get("status"), "age_s": age}
        assert row.get("status") == "ok", f"{code}: status={row.get('status')}"
        assert age is not None and age <= 120, f"{code}: last_ts застарілий ({age} с)"
    time.sleep(120)
    for code, counter in SIGNALS:
        if not counter:
            continue
        old, new = float(before[code]["last_value"]), last_value(odoo, code)
        report[code]["delta"] = round(new - old, 4)
        assert new >= old, f"{code}: лічильник спадає ({old} → {new})"
        if code not in SLOW_COUNTERS:
            assert new > old, f"{code}: лічильник не росте"
    flow = last_value(odoo, "infra/gas/flow_m3h")
    boiler = last_value(odoo, "equipment/BOILER/gas_m3h")
    chp = float(odoo.signal("infra/chp/gas_m3h").get("last_value") or 0.0)
    sim_flow = sim.value("infra/gas/flow_m3h")
    low, high = boiler + chp, boiler + chp + DRY_M3H + CANTEEN_M3H
    tk_report("02", {"flow": flow, "boiler": boiler, "chp": chp, "sim_flow": sim_flow, "signals": report})
    assert low * 0.95 <= flow <= high * 1.05, f"витрата газу {flow} поза сумою гілок {low}…{high} ±5 %"
    assert abs(flow - sim_flow) <= 0.05 * max(sim_flow, 1.0) + 1.0, "похідна витрата розходиться з емулятором"


# --- ТК-03 -----------------------------------------------------------------------------------------------
@need_collector
def test_tk03_history_join(odoo, stand_ready):
    """ТК-03: на стику `until` немає `missing` і дірок, `is_backfill` стає `False` одним переходом, графіки цілі."""
    meters = odoo.k("td.energy.meter", "search_read", [("resource_id.code", "in", ["gas", "air", "water"])], ["code"])
    assert meters, "лічильників ресурсів немає (hooks._seed_points_meters)"
    report: dict[str, dict] = {}
    for meter in meters:
        scope = [("meter_id", "=", meter["id"]), ("metric", "=", "main")]
        live = odoo.k(
            INTERVAL, "search_read", [*scope, ("is_backfill", "=", False)], ["ts_start"], order="ts_start asc", limit=1
        )
        hist = odoo.k(
            INTERVAL, "search_read", [*scope, ("is_backfill", "=", True)], ["ts_start"], order="ts_start desc", limit=1
        )
        assert live and hist, f"{meter['code']}: немає живих або історичних слотів (backfill + крон)"
        t_live, t_hist = parse_utc(live[0]["ts_start"]), parse_utc(hist[0]["ts_start"])
        window = [
            ("ts_start", ">=", fmt_utc(t_hist - timedelta(hours=2))),
            ("ts_start", "<=", fmt_utc(t_live + timedelta(hours=2))),
        ]
        rows = odoo.k(
            INTERVAL, "search_read", [*scope, *window], ["ts_start", "quality", "is_backfill"], order="ts_start asc"
        )
        starts = [parse_utc(r["ts_start"]) for r in rows]
        gaps = [(a, b) for a, b in zip(starts, starts[1:], strict=False) if b - a != timedelta(minutes=15)]
        missing = [r["ts_start"] for r in rows if r["quality"] == "missing"]
        flags = [bool(r["is_backfill"]) for r in rows]
        changes = sum(1 for a, b in zip(flags, flags[1:], strict=False) if a != b)
        later_hist = odoo.k(
            INTERVAL, "search_count", [*scope, ("is_backfill", "=", True), ("ts_start", ">", live[0]["ts_start"])]
        )
        report[meter["code"]] = {
            "until": str(t_hist),
            "first_live": str(t_live),
            "gaps": len(gaps),
            "missing": len(missing),
            "changes": changes,
        }
        assert not missing, f"{meter['code']}: слоти missing на стику {missing[:3]}"
        assert not gaps, f"{meter['code']}: дірки на стику {gaps[:3]}"
        assert changes == 1 and flags[0] and not flags[-1], f"{meter['code']}: is_backfill змінюється {changes} разів"
        assert later_hist == 0, f"{meter['code']}: історичні слоти після першого живого"
    for code in ("gas", "air", "water"):
        chart = screen(odoo, code)["resource"]["chart"]
        gaps_chart = [i for i, v in enumerate(chart["series"][: chart["now_slot"]]) if v is None]
        report[f"chart_{code}"] = {"null_slots": len(gaps_chart)}
        assert not gaps_chart, f"графік {code}: порожні слоти {gaps_chart[:5]}"
    tk_report("03", report)


# --- ТК-04 -----------------------------------------------------------------------------------------------
@need_long
def test_tk04_air_leak(odoo, sim, stand_ready):
    """ТК-04 (AC-62): `air_leak` ≥ 1 ніч → KPI «Витоки вночі» > 10 % денної, резерв `air_leaks`; зупинка → `expired`.

    Три фази (`F3D_W3_TK04_PHASE`): `start` — увечері запускає сценарій; `check` — наступного ранку (≥ 1 ніч з витоком;
    потрібна історія ≥ 3 ночей) перевіряє KPI й резерв і зупиняє сценарій; `expire` — ще через ніч без витоку."""
    phase = os.environ.get("F3D_W3_TK04_PHASE", "check")
    rule_ids = odoo.k(RULE, "search", [("code", "=", "air_leaks")], limit=1)
    assert rule_ids, "правила air_leaks немає (opportunity_rules.xml)"
    if phase == "start":
        if not active_runs(sim, "air_leak"):
            sim.scenario("air_leak", {})
        runs = active_runs(sim, "air_leak")
        tk_report("04", {"phase": "start", "run": runs[0]["id"] if runs else None, "at": datetime.now().isoformat()})
        assert runs, "сценарій air_leak не запустився"
    elif phase == "check":
        assert active_runs(sim, "air_leak"), (
            "air_leak не запущено: спершу F3D_W3_TK04_PHASE=start (≥ 1 ніч до перевірки)"
        )
        try:
            night = kpi(screen(odoo, "air"), "night_leak")
            share = pct_of(night["note"])
            stats = odoo.k(RULE, "action_run", rule_ids)
            open_ids = odoo.k(OPP, "search", [("rule_id", "=", rule_ids[0]), ("state", "=", "open")])
            tk_report(
                "04",
                {
                    "phase": "check",
                    "night_leak": night["value"],
                    "share_pct": share,
                    "tone": night["tone"],
                    "run": stats,
                    "open": open_ids,
                },
            )
            assert share > 10 and night["tone"] == "bad", f"витоки вночі {share} % ≤ 10 % денної"
            assert open_ids, "резерв air_leaks не створено"
        finally:
            stop_scenario(sim, "air_leak")
        assert not active_runs(sim, "air_leak")
    else:
        assert not active_runs(sim, "air_leak"), "air_leak ще працює: спершу фаза check"
        before = odoo.k(OPP, "search", [("rule_id", "=", rule_ids[0]), ("state", "=", "open")])
        stats = odoo.k(RULE, "action_run", rule_ids)
        after = odoo.k(OPP, "search", [("rule_id", "=", rule_ids[0]), ("state", "=", "open")])
        tk_report("04", {"phase": "expire", "open_before": before, "open_after": after, "run": stats})
        assert before, "немає відкритого резерву air_leaks: фаза check не виконана"
        assert not after, f"після зупинки сценарію резерв лишився відкритим: {after}"
        states = [r["state"] for r in odoo.k(OPP, "read", before, ["state"])]
        assert all(s == "expired" for s in states), f"стани резервів: {states}"


# --- ТК-05 -----------------------------------------------------------------------------------------------
@need_collector
def test_tk05_gas_overuse(odoo, sim, stand_ready):
    """ТК-05: `gas_overuse` → витрата джерела > 80 м³/год, лінія ліміту перетнута, «Сьогодні»/«Ліміт доби» ростуть."""
    before = screen(odoo, "gas")
    today_before = kpi(before, "today")["value"]
    pct_before = pct_of(kpi(before, "limit")["note"])
    sim.scenario("gas_overuse", {})
    try:
        exceeded = wait_until(lambda: last_value(odoo, "infra/gas/flow_m3h") > LIMIT_H, minutes=8)
        assert exceeded, f"витрата газу не перевищила {LIMIT_H} м³/год (емулятор: {sim.value('infra/gas/flow_m3h')})"
        if _flag("F3D_STAND_LONG"):
            time.sleep(15 * 60)  # 15-хвилинний слот графіка має накопичити перевитрату
        after = screen(odoo, "gas")
        chart = after["resource"]["chart"]
        series = [v for v in chart["series"][max(0, chart["now_slot"] - 3) : chart["now_slot"] + 1] if v is not None]
        today_after = kpi(after, "today")["value"]
        pct_after = pct_of(kpi(after, "limit")["note"])
        tk_report(
            "05",
            {
                "flow": last_value(odoo, "infra/gas/flow_m3h"),
                "limit_line": chart["limit"],
                "series_tail": series,
                "today": [today_before, today_after],
                "limit_pct": [pct_before, pct_after],
            },
        )
        assert chart["limit"] == LIMIT_H
        assert today_after > today_before + 2.0, "«Сьогодні» не росте"
        assert pct_after >= pct_before, "«Ліміт доби» не росте"
        if _flag("F3D_STAND_LONG"):
            assert max(series) > LIMIT_H, f"лінія ліміту не перетнута: {series}"
    finally:
        stop_scenario(sim, "gas_overuse")


# --- ТК-06 -----------------------------------------------------------------------------------------------
@need_collector
def test_tk06_export_xlsx(h, odoo, stand_ready):
    """ТК-06 (AC-45): xlsx за вчора відкривається `openpyxl`, рядків = рядків `td.energy.usage`, суми збігаються."""
    openpyxl = pytest.importorskip("openpyxl")
    yesterday = date.today() - timedelta(days=1)
    client = h.httpx.Client(base_url=h.env("F3D_ODOO_URL").rstrip("/"), timeout=120)
    login = {
        "db": h.env("F3D_ODOO_DB"),
        "login": h.env("F3D_ODOO_USER", "admin"),
        "password": h.env("F3D_ODOO_PASSWORD"),
    }
    auth = client.post("/web/session/authenticate", json={"jsonrpc": "2.0", "method": "call", "params": login})
    assert auth.json().get("result", {}).get("uid"), "сесія Odoo не відкрилась"
    resp = client.get("/td/energy/resources/export", params={"day": yesterday.isoformat()})
    assert resp.status_code == 200, resp.text[:200]
    assert f"energoresursy_{yesterday.isoformat()}.xlsx" in resp.headers.get("content-disposition", "")
    book = openpyxl.load_workbook(io.BytesIO(resp.content), read_only=True, data_only=True)
    assert "Ресурси" in book.sheetnames and "Підсумок" in book.sheetnames
    rows = list(book["Ресурси"].iter_rows(values_only=True))
    header, body = rows[0], [r for r in rows[1:] if any(c is not None for c in r)]
    assert tuple(header[:6]) == ("Ресурс", "Потік", "Об'єкт", "Початок (Київ)", "Кількість", "Одиниця")
    usage_domain = [("day", "=", yesterday.isoformat())]
    usage_rows = odoo.k("td.energy.usage", "search_count", usage_domain)
    sums_x: dict[str, float] = {}
    for row in body:
        sums_x[str(row[0])] = sums_x.get(str(row[0]), 0.0) + float(row[4] or 0.0)
    grouped = odoo.k("td.energy.usage", "read_group", usage_domain, ["qty:sum"], ["resource_id"], lazy=False)
    sums_u = {g["resource_id"][1]: float(g["qty"] or 0.0) for g in grouped if g.get("resource_id")}
    tk_report("06", {"day": yesterday, "rows": len(body), "usage_rows": usage_rows, "resources": sorted(sums_x)})
    assert body, "файл порожній: немає даних за вчора"
    assert len(body) == usage_rows, f"рядків {len(body)} ≠ td.energy.usage {usage_rows}"
    assert set(sums_x) == set(sums_u)
    for name, qty in sums_u.items():
        assert sums_x[name] == pytest.approx(qty, rel=1e-3, abs=0.5), f"{name}: xlsx {sums_x[name]} ≠ usage {qty}"
