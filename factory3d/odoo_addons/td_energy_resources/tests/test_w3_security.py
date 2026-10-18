"""W3-E: ТБ-01…ТБ-04 і AC-60 (ТП-01) — безпека та продуктивність API екрана й експорту."""

import io
import json
import logging
import statistics
import time
from datetime import datetime
from unittest.mock import patch

import openpyxl

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged

from .common import NOW, TAGS, TestW3Common

_logger = logging.getLogger(__name__)
URL = "/td/energy/resources/export"
EXPORT = "odoo.addons.td_energy_resources.controllers.export"
COST_KEYS = {"cost_uah", "price_uah", "save_uah_month", "cost", "plan_sum", "all_sum"}
OPPORTUNITY_PUBLIC = ("get_list", "get_plan_summary")
SIGNALS = (
    ("infra/gas/flow_m3h", 46.0), ("infra/gas/m3_total", 18400.0), ("equipment/BOILER/gas_m3h", 41.0),
    ("infra/chp/gas_m3h", 0.0), ("air/flow_m3min", 9.8), ("air/pressure_bar", 7.1), ("air/m3_total", 1000.0),
    ("energy/consumers/COMPRESSOR/p_now", 52.0), ("infra/water/flow_m3h", 0.4), ("infra/water/m3_total", 500.0),
    ("infra/water/boiler_m3_total", 50.0),
)  # fmt: skip


def walk_keys(data):
    if isinstance(data, dict):
        for key, value in data.items():
            yield key
            yield from walk_keys(value)
    elif isinstance(data, list):
        for item in data:
            yield from walk_keys(item)


@tagged(*TAGS)
class TestW3Security(HttpCase, TestW3Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dash = cls.env["td.energy.res.dashboard"]
        for user in (cls.u_view, cls.u_cost, cls.u_eng, cls.u_plain):
            user.password = user.login

    def setUp(self):
        super().setUp()
        patcher = patch("odoo.addons.td_energy.tools.dates.now_utc", return_value=NOW)
        patcher.start()
        self.addCleanup(patcher.stop)

    def opportunity_methods(self, user):
        """Публічні методи моделі резервів (воркер B) — лише ті, що вже є."""
        model = self.env["td.energy.opportunity"].with_user(user) if "td.energy.opportunity" in self.env else None
        return [getattr(model, name) for name in OPPORTUNITY_PUBLIC if model is not None and hasattr(model, name)]

    def export(self, query, user):
        if user:
            self.authenticate(user, user)
        return self.url_open(URL + query, allow_redirects=False)

    # --- ТБ-01 ------------------------------------------------------------------------------------------------
    def test_tb01_no_group_denied(self):  # AC-21, AC-44
        dash = self.Dash.with_user(self.u_plain)
        for call in (
            lambda: dash.get_resources(),
            lambda: dash.get_resources("gas"),
            lambda: dash._td_totals("2026-10-17", "2026-10-17"),
        ):
            with self.assertRaises(AccessError):
                call()
        for method in self.opportunity_methods(self.u_plain):
            with self.assertRaises(AccessError):
                method()
        self.assertEqual(self.export("?day=2026-10-17", "w1_plain").status_code, 403)

    # --- ТБ-02 ------------------------------------------------------------------------------------------------
    def test_tb02_cost_keys_absent(self):  # AC-21, AC-43, AC-44
        self.fixture_grid()
        self.el_interval("PM-Q1", datetime(2026, 10, 17, 6, 0), 100.0)
        gas = self.env["td.energy.meter"].search([("code", "=", "GM-MAIN")])
        self.res_interval(gas, datetime(2026, 10, 17, 6, 0), 25.5, cost=504.9)
        view = self.Dash.with_user(self.u_view)
        for code in ("el", "gas", "air", "water"):
            self.assertFalse(COST_KEYS & set(walk_keys(view.get_resources(code))), code)
            self.assertNotIn("₴", json.dumps(view.get_resources(code), ensure_ascii=False))
        totals = view._td_totals("2026-10-17", "2026-10-17")
        self.assertTrue(totals and all("cost" not in row for row in totals))
        for method in self.opportunity_methods(self.u_view):
            self.assertFalse(COST_KEYS & set(walk_keys(method())), method.__name__)
        with_cost = self.Dash.with_user(self.u_cost)
        self.assertTrue(all("cost" in row for row in with_cost._td_totals("2026-10-17", "2026-10-17")))
        res = self.export("?day=2026-10-17", "w1_view")
        self.assertEqual(res.status_code, 200)
        book = openpyxl.load_workbook(io.BytesIO(res.content))
        headers = [cell.value for ws in book.worksheets for cell in ws[1]]
        self.assertTrue(headers and not [h for h in headers if "₴" in h])  # колонок ціни й вартості немає

    # --- ТБ-03 ------------------------------------------------------------------------------------------------
    def test_tb03_acl(self):  # AC-42, AC-49
        point = self.env["td.energy.point"].search([("code", "=", "GAS-MAIN")])
        gas = self.resource("gas")
        price_vals = {"resource_id": self.resource("heat").id, "date_from": "2030-01-01", "price": 21.0}
        view = self.env["td.energy.price"].with_user(self.u_view)
        with self.assertRaises(AccessError):
            view.create(price_vals)
        with self.assertRaises(AccessError):
            point.with_user(self.u_view).write({"name": "X"})
        with self.assertRaises(AccessError):
            gas.with_user(self.u_view).write({"daily_limit": 1.0})
        with self.assertRaises(AccessError):
            self.env["td.energy.res.interval"].with_user(self.u_view).create({})
        manager = self.env["td.energy.price"].with_user(self.u_eng)
        price = manager.create(price_vals)  # енергетик ціни веде
        with self.assertRaises(AccessError):
            price.unlink()
        with self.assertRaises(AccessError):
            self.env["td.energy.res.interval"].with_user(self.u_eng).create({})  # лише крон/backfill
        if self.env["ir.model.access"].search_count([("model_id.model", "=", "td.energy.opportunity.rule")]):
            rule = self.env["td.energy.opportunity.rule"].with_user(self.u_view)
            with self.assertRaises(AccessError):
                rule.create({})

    # --- ТБ-04 ------------------------------------------------------------------------------------------------
    def test_tb04_export_params(self):  # AC-63
        with patch(EXPORT + ".COUNT_SQL", "SELECT 1/0"), patch(EXPORT + ".ROWS_SQL", "SELECT 1/0"):
            for query in (
                "?day=2026-10-17;DROP%20TABLE%20td_energy_resource",
                "?day=2026-10-17&resources=../../etc/passwd",
                "?day=2026-10-17&resources=%27%20OR%201=1--",
                "?day=..%2F..%2Fetc",
            ):
                res = self.export(query, "w1_cost")
                self.assertEqual(res.status_code, 400, query)  # перевірка — до SQL (інакше було б 500)
                self.assertNotIn("passwd", res.text)
        self.assertEqual(self.env["td.energy.resource"].search_count([]), 5)

    # --- AC-60 (ТП-01) ----------------------------------------------------------------------------------------
    def test_perf_get_resources(self):  # AC-60: ≤ 400 мс (медіана 10 викликів), ≤ 30 SQL, без N+1 по точках
        until = datetime(2026, 10, 17, 11, 15)
        t0 = time.perf_counter()
        self.env["td.energy.interval"]._td_backfill(days=90, until=until, seed=1, with_balance=False, with_events=False)
        stats = self.env["td.energy.res.interval"]._td_backfill(days=90, until=until, seed=1)
        _logger.info("W3E perf: backfill 90 діб за %.1f с, рядків ресурсів %s", time.perf_counter() - t0, stats["rows"])
        flow = self.signal("test/hm_boiler_kw", unit="кВт")
        self.meter("HM-BOILER", self.point("HEAT-BOILER", "heat", "source"), "flow_integrate", flow=[flow])
        self.fixture_grid()
        for code, value in (*SIGNALS, (flow.code, 390.0)):
            self.fresh(code, value)
        self.fresh("infra/chp/state", 0.0, "stop")
        cr = self.env.cr
        for code in ("el", "gas", "heat", "air", "water"):
            dash = self.Dash.with_user(self.u_cost)
            dash.get_resources(code)  # прогрів реєстру й кешів параметрів
            times, queries = [], []
            for _ in range(10):
                self.env.flush_all()
                self.env.invalidate_all()  # «холодний» запит: кеш ORM порожній
                count0, start = cr.sql_log_count, time.perf_counter()
                data = dash.get_resources(code)
                times.append(time.perf_counter() - start)
                queries.append(cr.sql_log_count - count0)
            size = len(json.dumps(data, ensure_ascii=False).encode())
            _logger.info(
                "W3E perf: %s медіана %.0f мс, макс. %.0f мс, SQL %s, JSON %d Б",
                code, statistics.median(times) * 1000, max(times) * 1000, max(queries), size,
            )  # fmt: skip
            self.assertLessEqual(max(queries), 30, "%s: %s SQL" % (code, queries))
            self.assertLessEqual(statistics.median(times), 0.4, "%s: %.0f мс" % (code, statistics.median(times) * 1000))
            self.assertLess(size, 25 * 1024, code)
            self.assertIsNotNone(data["resource"]["kpis"][0]["value"], code)  # дані 90 діб читаються, а не порожньо
        with self.assertRaises(UserError):
            self.Dash.with_user(self.u_cost).get_resources("xx")
