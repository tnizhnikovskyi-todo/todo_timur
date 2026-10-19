"""W1-A: AC-142, AC-144 (UT-частина), AC-154, AC-155, AC-156 + форма JSON (контракти C-30…C-34)."""

import json
import os
import statistics
import time
from datetime import timedelta

from odoo.tests import tagged
from odoo.tools import file_open

from .. import hooks
from .common import TAGS, TestW1Common

OPTIONAL_EMPTY = (None, [], {})


def check_keys(test, expected, actual, path="$"):
    """Збіг наборів ключів приклада контракту й відповіді API (порожні значення пропускаються)."""
    if expected in OPTIONAL_EMPTY or actual in OPTIONAL_EMPTY:
        return
    if isinstance(expected, dict):
        test.assertIsInstance(actual, dict, path)
        test.assertEqual(sorted(expected), sorted(actual), path)
        for key, value in expected.items():
            check_keys(test, value, actual[key], "%s.%s" % (path, key))
    elif isinstance(expected, list):
        test.assertIsInstance(actual, list, path)
        check_keys(test, expected[0], actual[0], path + "[0]")


@tagged(*TAGS)
class TestW1Security(TestW1Common):
    def test_groups_and_acl(self):  # AC-142
        chief = self.env.ref("td_energy.group_td_energy_chief")
        self.assertIn(self.env.ref("td_energy.group_td_energy_manager"), chief.implied_ids)
        self.assertIn(chief, self.env.ref("td_factory3d.group_td_admin").implied_ids)
        self.assertTrue(self.u_chief.has_group("td_energy.group_td_energy_manager"))
        for model in ("td.energy.outage.plan", "td.energy.advice"):
            view = self.env[model].with_user(self.u_view)
            self.assertTrue(view.has_access("read"), model)
            self.assertFalse(view.has_access("write") or view.has_access("create"), model)
        plan = self.env["td.energy.outage.plan"].with_user(self.u_mrp)
        self.assertTrue(plan.has_access("read"))
        self.assertFalse(plan.has_access("write") or plan.has_access("create"))
        self.assertTrue(self.env["td.energy.outage.plan"].with_user(self.u_eng).has_access("create"))

    def test_menus(self):  # AC-144 (UT-частина; меню створює W1-B)
        generation = self.env.ref("td_energy.menu_td_energy_generation", raise_if_not_found=False)
        if not generation:
            self.skipTest("меню «Генерація й резерв» додає W1-B (views/menus.xml)")
        overview = self.env.ref("td_energy.menu_td_energy_generation_overview")
        self.assertEqual((generation.parent_id, generation.sequence), (self.env.ref("td_energy.menu_td_energy"), 35))
        group = self.env.ref("td_energy.group_td_energy_user")
        for menu in (generation, overview):
            self.assertIn(group, menu.group_ids | group)
        self.assertFalse(self.env["ir.ui.menu"].search([("name", "=", "Генератор"), ("parent_id", "=", False)]))

    def test_performance(self):  # AC-154, ТП-08
        self.fixture_grid()
        self.env["td.energy.interval"]._td_backfill(days=3, until=self.now.replace(minute=15), with_balance=False)
        dash = self.env["td.energy.dashboard"].with_user(self.u_cost)
        for name, call, limit in (
            ("get_pult", lambda: dash.get_pult(), 0.5),
            ("get_node_card", lambda: dash.get_node_card("BW-2"), 0.3),
            ("get_mobile", lambda: dash.get_mobile(None), 0.25),
        ):
            call()  # прогрів кешів
            times, queries = [], 0
            for _k in range(10):
                before = self.cr.sql_log_count
                start = time.perf_counter()
                call()
                times.append(time.perf_counter() - start)
                queries = self.cr.sql_log_count - before
            self.assertLessEqual(statistics.median(times), limit, name)
            if name == "get_pult":
                self.assertLessEqual(queries, 40, "SQL-запитів: %d" % queries)

    def test_neutralize_and_uninstall(self):  # AC-155
        with file_open("td_energy/data/neutralize.sql") as f:
            self.env.cr.execute(f.read())
        self.env.invalidate_all()
        for xmlid in ("cron_td_energy_advice", "cron_td_energy_outage_plan", "cron_td_energy_verification"):
            self.assertFalse(self.env.ref("td_energy." + xmlid).active, xmlid)
        source = self.env["td.source"].search([("code", "=", "MB-U73-SWB-CTRL")])
        self.assertEqual((source.read_enabled, source.state), (False, "disabled"))
        self.assertEqual(self.env["ir.config_parameter"].sudo().get_param("td.energy.write_enabled"), "False")
        event = self.Event._td_log("warn", "meter", "PM-QF-C2", "Лічильник. Немає даних.", ts=self.now)
        plan = self.env["td.energy.outage.plan"].create(
            {
                "node_id": self.Node.search([("code", "=", "BW-2")]).id,
                "start": self.now + timedelta(days=2),
                "end": self.now + timedelta(days=2, hours=1),
            }  # fmt: skip
        )
        advice = self.env["td.energy.advice"]._td_demo_seed()
        hooks.uninstall_hook(self.env)
        self.assertTrue(event.exists() and plan.exists() and advice.exists())

    def test_refresh_param(self):  # AC-156
        settings = self.env["res.config.settings"].create({})
        settings.write({"td_energy_pult_refresh_s": 45, "td_energy_alarm_list_limit": 3})
        settings.set_values()
        self.assertEqual(
            self.env["td.energy.dashboard"].with_user(self.u_view).get_pult(parts=[])["meta"]["refresh_s"], 45
        )
        for k in range(5):
            self.Event._td_log(
                "warn", "meter", "PM-%d" % k, "Подія %d. Текст." % k, ts=self.now - timedelta(minutes=k)
            )
        items = self.env["td.energy.dashboard"].with_user(self.u_view).get_alarms()["items"]
        self.assertEqual(len(items), 3)
        values = self.env["res.config.settings"].default_get(["td_energy_cos_phi_warn", "td_energy_load_warn_pct"])
        self.assertEqual((values["td_energy_cos_phi_warn"], values["td_energy_load_warn_pct"]), (0.92, 80))

    def test_contract_shape(self):  # C-30…C-34: форма відповідей = заморожений приклад
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "tests", "fixtures",
                            "contracts.json")  # fmt: skip
        with open(path, encoding="utf-8") as f:
            contract = json.load(f)["C-30"]
        self.fixture_grid()
        self.env["td.energy.advice"]._td_demo_seed()
        event = self.Event._td_log("warn", "meter", "PM-QF-C2", "Лічильник PM-QF-C2. Немає даних.", ts=self.now,
                                    node=self.Node.search([("code", "=", "C2")]))  # fmt: skip
        event.with_user(self.u_eng).action_ack()
        self.Event._td_log("info", "peak", "SWB-1", "Пік. Деталі.", ts=self.now)
        self.interval("PM-Q1", self.now - timedelta(hours=5), 50.0)
        dash = self.env["td.energy.dashboard"].with_user(self.u_cost)
        check_keys(self, contract["API-05"]["response"], dash.get_pult())
        check_keys(self, contract["API-06"]["response"], dash.get_alarms())
        check_keys(self, contract["API-07"]["response"], dash.get_node_card("BW-2"))
        check_keys(self, contract["API-12"]["response"], dash.get_mobile(None))
        check_keys(self, contract["API-13"]["response"], dash.get_generation())
        pult = dash.get_pult(period="month", parts=["kpis"])
        self.assertEqual(sorted(pult), ["kpis", "meta"])
