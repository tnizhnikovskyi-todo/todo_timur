"""ТК-01…ТК-05 (W4_SPEC 13.2) — pytest проти стенда E-11 (Odoo + емулятор + збирач).

Самодостатній файл (не імпортується Odoo): без `F3D_ODOO_URL` усі тести пропускаються. Змінні: `F3D_ODOO_URL`,
`F3D_ODOO_DB`, `F3D_ODOO_USER`, `F3D_ODOO_PASSWORD` (адміністратор); для ролей — логіни `F3D_STAND_MANAGER`,
`F3D_STAND_CHIEF` з паролем `F3D_STAND_USER_PASSWORD` (за замовчуванням — пароль адміністратора).
Передумови: встановлені `td_energy`, `td_energy_resources`, `td_energy_analytics`; виконано електричний
`_td_backfill(days=400)`, ресурсний `_td_backfill(days=400)` (W3) і `td.energy.analytics._td_seed_demo(days=400)`.
Результати друкуються рядками ``TK <id> <json>`` (pytest -s) і заносяться до TEST_REPORT.md.
Запуск: ``pytest -s factory3d/odoo_addons/td_energy_analytics/tests/stand/test_w4_tk.py``.
"""

from __future__ import annotations

import json
import os
import time
import xmlrpc.client
from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("F3D_ODOO_URL"), reason="F3D_ODOO_URL не задано: стенд не піднято")
API = "td.energy.analytics"
PERIODS = ("w", "m", "q", "y")
DIMS = ("area", "eq", "mo", "prod", "shift")
KPI_IDS = ["el", "gas", "cost", "spec", "cogs", "selfgen", "co2"]
SWITCH_LIMIT_S = 1.5


class OdooFault(Exception):
    pass


class Odoo:
    """Тонка обгортка над ``xmlrpc/2``."""

    def __init__(self, url: str, db: str, user: str, password: str):
        self.url, self.db, self.user, self.password = url.rstrip("/"), db, user, password
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(db, user, password, {})
        if not self.uid:
            raise RuntimeError(f"Odoo: автентифікація {user} не вдалась")
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)

    def k(self, model: str, method: str, *args, **kw):
        try:
            return self.models.execute_kw(self.db, self.uid, self.password, model, method, list(args), kw)
        except xmlrpc.client.Fault as fault:
            lines = [ln for ln in str(fault.faultString).strip().splitlines() if ln.strip()]
            raise OdooFault(f"{model}.{method}: {lines[-1] if lines else fault.faultCode}") from None

    def as_user(self, login: str) -> Odoo:
        return Odoo(self.url, self.db, login, os.environ.get("F3D_STAND_USER_PASSWORD", self.password))


def tk_report(tk: str, data: dict) -> None:
    print(f"TK {tk} {json.dumps(data, ensure_ascii=False, default=str)}")


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"змінна середовища {name} не задана")
    return value


@pytest.fixture(scope="module")
def odoo() -> Odoo:
    return Odoo(env("F3D_ODOO_URL"), env("F3D_ODOO_DB"), env("F3D_ODOO_USER", "admin"), env("F3D_ODOO_PASSWORD"))


def role(odoo: Odoo, var: str, default: str) -> Odoo:
    return odoo.as_user(os.environ.get(var, default))


def dashboard(odoo: Odoo, period: str = "m", dim: str = "area", parts=None) -> dict:
    return odoo.k(API, "get_dashboard", period, dim, parts)


def timed(func):
    started = time.monotonic()
    result = func()
    return result, time.monotonic() - started


def xmlid(odoo: Odoo, module: str, name: str) -> int:
    return odoo.k("ir.model.data", "check_object_reference", module, name)[1]


# --- ТК-01: екран «Аналітика» -------------------------------------------------------------------------------
def test_tk01_screen_blocks_and_switching(odoo):
    """AC-50 (дані): блоки заповнені, 7 KPI зі значеннями, EnPI 12 точок, теплокарта 7×24, таблиця не порожня."""
    slowest = 0.0
    for period in PERIODS:
        data, took = timed(lambda p=period: dashboard(odoo, p, "area"))
        slowest = max(slowest, took)
        assert [k["id"] for k in data["kpis"]] == KPI_IDS, period
        assert all(k["value"] is not None for k in data["kpis"] if k["id"] != "cogs"), period
        assert len(data["stack"]["bars"]) == {"w": 7, "m": 30, "q": 13, "y": 12}[period]
        assert len(data["heatmap"]["cells"]) == 7 and all(len(row) == 24 for row in data["heatmap"]["cells"])
        assert len(data["enpi"]["weeks"]) == 12
        assert data["cut"]["rows"], period
        assert all("error" not in data[part] for part in ("kpis", "stack", "heatmap", "enpi", "cut", "opps"))
        for dim in DIMS:
            cut, took = timed(lambda p=period, d=dim: odoo.k(API, "get_cut", d, p))
            slowest = max(slowest, took)
            assert cut["dim"] == dim and cut["rows"], (period, dim)
    tk_report("01", {"slowest_s": round(slowest, 3)})
    assert slowest <= SWITCH_LIMIT_S


# --- ТК-02: EnPI і бюджет -----------------------------------------------------------------------------------
def test_tk02_enpi_and_budget(odoo):
    """EnPI 0,92…0,96; бюджет: зміна й затвердження — лише головним енергетиком."""
    data = dashboard(odoo, "m", "area", ["enpi", "budget"])
    enpi = data["enpi"]["enpi"]
    assert enpi is not None and 0.92 <= enpi <= 0.96, enpi
    assert data["budget"] is not None, "немає затвердженого бюджету поточного місяця (сид)"
    month = date.today().replace(day=1).isoformat()
    manager = role(odoo, "F3D_STAND_MANAGER", "td_energy_manager")
    chief = role(odoo, "F3D_STAND_CHIEF", "td_energy_chief")
    ids = odoo.k("td.energy.budget", "search", [("month", "=", month), ("resource_id", "=", False)])
    assert ids
    plan = data["budget"]["plan_uah"]
    chief.k("td.energy.budget", "write", ids, {"amount_uah": plan + 10000.0})
    assert odoo.k("td.energy.budget", "read", ids, ["state"])[0]["state"] == "draft"
    assert dashboard(odoo, "m", "area", ["budget"])["budget"] is None, "чернетка не враховується"
    with pytest.raises(OdooFault):
        manager.k("td.energy.budget", "action_approve", ids)
    chief.k("td.energy.budget", "action_approve", ids)
    updated = dashboard(odoo, "m", "area", ["budget"])["budget"]
    tk_report("02", {"enpi": enpi, "plan": updated["plan_uah"], "forecast": updated["forecast_uah"]})
    assert updated["plan_uah"] == plan + 10000.0
    chief.k("td.energy.budget", "write", ids, {"amount_uah": plan})
    chief.k("td.energy.budget", "action_approve", ids)


# --- ТК-03: резерви й «у плані» -----------------------------------------------------------------------------
def test_tk03_opportunities_plan_and_ticket(odoo):
    """Позначити резерв «у плані» (plan_sum), створити заявку з тегом [OPP-id], закрити → резерв `done`."""
    manager = role(odoo, "F3D_STAND_MANAGER", "td_energy_manager")
    opps = odoo.k(API, "get_opportunities")
    open_items = [i for i in opps["items"] if not i["in_plan"]]
    assert open_items, "немає відкритих резервів поза планом"
    target = open_items[0]
    before = opps["plan_sum"]
    manager.k("td.energy.opportunity", "action_plan_toggle", [target["id"]])
    after = odoo.k(API, "get_opportunities")["plan_sum"]
    assert after == before + target["save_uah_month"]
    request = odoo.k(
        "maintenance.request", "create",
        {"name": f"Резерв {target['title']}", "description": f"[OPP-{target['id']}] {target['text']}"},
    )  # fmt: skip
    cron = xmlid(odoo, "td_energy_resources", "cron_td_energy_opportunity")
    odoo.k("ir.cron", "method_direct_trigger", [cron])
    linked = odoo.k("td.energy.opportunity", "read", [target["id"]], ["request_id", "state"])[0]
    assert linked["request_id"] and linked["request_id"][0] == request
    done_stage = odoo.k("maintenance.stage", "search", [("done", "=", True)], limit=1)
    odoo.k("maintenance.request", "write", [request], {"stage_id": done_stage[0]})
    odoo.k("ir.cron", "method_direct_trigger", [cron])
    closed = odoo.k("td.energy.opportunity", "read", [target["id"]], ["state"])[0]
    tk_report("03", {"plan_sum_before": before, "plan_sum_after": after, "state": closed["state"]})
    assert closed["state"] == "done"


# --- ТК-04: PDF ---------------------------------------------------------------------------------------------
def test_tk04_pdf_reports(odoo):
    """AC-45/46: «Звіт для керівництва» і «Звіт за зміну» (модуль W4-B): PDF ≤ 15 с, < 3 МБ."""
    if not odoo.k("ir.model", "search", [("model", "=", "td.energy.report.wizard")]):
        pytest.skip("Майстер звітів (W4-B) не встановлено")
    action, took = timed(lambda: odoo.k("td.energy.report.wizard", "create_and_print", "management", "m"))
    tk_report("04", {"report": action.get("report_name"), "create_s": round(took, 3)})
    assert action["type"] == "ir.actions.report" and took <= 15
    report = xmlrpc.client.ServerProxy(f"{odoo.url}/xmlrpc/2/report", allow_none=True)
    pdf, took = timed(
        lambda: report.render_report(
            odoo.db,
            odoo.uid,
            odoo.password,
            action["report_name"],
            action.get("context", {}).get("active_ids") or [],
            {},
        )
    )
    assert took <= 15
    assert len(pdf["result"]) * 3 // 4 < 3 * 1024 * 1024
    assert odoo.k("td.energy.report.wizard", "create_and_print", "shift")["type"] == "ir.actions.report"


# --- ТК-05: живе добудовування фактів -----------------------------------------------------------------------
def test_tk05_cron_builds_and_catches_up(odoo):
    """AC-61: рядок `plant` вчорашньої доби й 49 рядків `node`; після видалення крон добудовує."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    cron = xmlid(odoo, "td_energy_analytics", "cron_td_energy_daily")

    def rows():
        plant = odoo.k("td.energy.daily", "search_read", [("day", "=", yesterday), ("scope", "=", "plant")], ["qty"])
        nodes = odoo.k("td.energy.daily", "search_count", [("day", "=", yesterday), ("scope", "=", "node")])
        return plant, nodes

    plant, nodes = rows()
    assert len(plant) == 1 and nodes == 49, (len(plant), nodes)
    feeders = odoo.k(
        "td.energy.interval", "read_group", [("day", "=", yesterday), ("role", "=", "feeder")], ["kwh:sum"], []
    )
    assert abs(plant[0]["qty"] - feeders[0]["kwh"]) <= 0.001 * max(1.0, plant[0]["qty"])
    odoo.k("td.energy.daily", "unlink", odoo.k("td.energy.daily", "search", [("day", "=", yesterday)]))
    assert rows()[0] == []
    odoo.k("ir.cron", "method_direct_trigger", [cron])
    plant, nodes = rows()
    tk_report("05", {"plant_rows": len(plant), "node_rows": nodes})
    assert len(plant) == 1 and nodes == 49
