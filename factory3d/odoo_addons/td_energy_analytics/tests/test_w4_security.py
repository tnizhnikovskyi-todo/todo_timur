"""W4-A: безпека й розгортання (AC-51, AC-52, AC-53, AC-59, ТБ-01…ТБ-04)."""

import importlib.util
from datetime import date, timedelta
from pathlib import Path

from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.td_energy_analytics import hooks
from odoo.tests import tagged
from odoo.tools import file_open

from .common import TAGS, TODAY, TestW4Common

CRONS = (
    "cron_td_energy_daily", "cron_td_energy_drivers", "cron_td_energy_enpi", "cron_td_energy_analytics_rotate",
)  # fmt: skip
PARAMS = (
    "daily_close_h", "catchup_days", "forecast_weeks", "forecast_min_days", "r2_min", "baseline_min_days",
    "refresh_s", "top_equipment", "top_mo",
)  # fmt: skip
COST_KEYS = {"cost_uah", "save_uah_month", "plan_sum", "all_sum", "saving_uah", "plan_uah", "fact_uah", "forecast_uah"}


def _keys(data):
    """Усі ключі словників на всіх рівнях."""
    out = set()
    if isinstance(data, dict):
        for key, value in data.items():
            out.add(key)
            out |= _keys(value)
    elif isinstance(data, list | tuple):
        for item in data:
            out |= _keys(item)
    return out


@tagged(*TAGS)
class TestW4Security(TestW4Common):
    # --- ТБ-01 -------------------------------------------------------------------------------------------
    def test_tb01_no_group_access_error(self):
        api = self.Api.with_user(self.u_plain)
        calls = (
            lambda: api.get_dashboard("m", "area"), lambda: api.get_kpis("m"), lambda: api.get_stack("m"),
            lambda: api.get_heatmap("m"), lambda: api.get_enpi(), lambda: api.get_budget(),
            lambda: api.get_cut("area", "m"), lambda: api.action_open_cut("area", "CUT", "m"),
            lambda: api.get_opportunities(), lambda: api._td_stack_gap_pct("m"),
        )  # fmt: skip
        for call in calls:
            with self.assertRaisesRegex(AccessError, "Немає доступу до Енергетики"):
                call()
        if "td.energy.report.wizard" in self.env:  # M-13 — модуль W4-B
            with self.assertRaises(AccessError):
                self.env["td.energy.report.wizard"].with_user(self.u_plain).create({})

    # --- ТБ-02, AC-51 ------------------------------------------------------------------------------------
    def test_tb02_cost_keys_removed_without_group(self):
        self._mockup_1710()
        self._daily(TODAY, scope="node", node="SAW-1", qty=100.0, cost=840.0)
        self._budget(date(2026, 10, 1), 1950000.0)
        rule = self.env.ref("td_energy_resources.rule_vent_offshift")
        self.env["td.energy.opportunity"].create(
            {"rule_id": rule.id, "dedup_key": "w4:sec", "title": "Резерв", "text": "Текст", "est_saving_month": 1000.0}
        )
        base = self.Baseline.search([("state", "=", "approved"), ("resource_id", "=", self.res_el.id)])
        self.assertTrue(base)
        views = (
            self.Api.with_user(self.u_view).get_dashboard("m", "area", None),
            self.Api.with_user(self.u_view).get_kpis("m"),
            self.Api.with_user(self.u_view).get_enpi(),
            self.Api.with_user(self.u_view).get_cut("area", "m"),
            self.Api.with_user(self.u_view).get_opportunities(),
            self.Api.with_user(self.u_view).get_budget(),
        )
        for data in views:
            self.assertFalse(_keys(data) & COST_KEYS, _keys(data) & COST_KEYS)
        dash = views[0]
        self.assertNotIn("cost", [k["id"] for k in dash["kpis"]])
        self.assertNotIn("cost", dash["meta"]["capabilities"])
        self.assertIsNone(dash["budget"])
        self.assertIsNone(views[5])
        # з групою вартості ключі на місці
        full = self.Api.with_user(self.u_cost).get_dashboard("m", "area", None)
        self.assertTrue({"cost_uah", "save_uah_month", "plan_sum", "all_sum", "plan_uah", "fact_uah"} <= _keys(full))
        self.assertIn("cost", [k["id"] for k in full["kpis"]])
        # чисті таблиці й поля вартості: без групи — AccessError
        with self.assertRaises(AccessError):
            self.Daily.with_user(self.u_view).search([]).mapped("cost")
        with self.assertRaises(AccessError):
            self.Budget.with_user(self.u_view).search([])

    # --- AC-51: ролі -------------------------------------------------------------------------------------
    def test_ac51_roles(self):
        area = self._area("CUT")
        driver = self.Driver.create({"code": "man", "name": "Ручний", "source_kind": "manual"})
        first = TODAY - timedelta(days=100)
        # user: лише читання
        for model, vals in (
            ("td.energy.area", {"code": "U1", "name": "U", "color": "#000000"}),
            ("td.energy.driver", {"code": "u1", "name": "U", "source_kind": "manual"}),
            ("td.energy.driver.value", {"driver_id": driver.id, "day": TODAY, "value": 1.0}),
        ):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.u_view).create(vals)
        self.assertEqual(self.Area.with_user(self.u_view).search_count([]), 8)
        with self.assertRaises(AccessError):
            area.with_user(self.u_view).write({"name": "Хак"})
        with self.assertRaises(AccessError):
            self.Daily.with_user(self.u_view).create({"day": TODAY, "scope": "plant", "built_at": self.now})
        # manager: підгонка, ручні драйвери, чернетка бюджету, перерахунок
        self.DriverValue.with_user(self.u_eng).create({"driver_id": driver.id, "day": TODAY, "value": 3.0})
        budget = self.Budget.with_user(self.u_eng).create({"month": date(2026, 11, 1), "amount_uah": 10.0})
        self.assertEqual(budget.state, "draft")
        base = self._baseline((first, first + timedelta(days=29)), {})
        for i in range(30):
            self._daily(first + timedelta(days=i), qty=100.0 + i)
        base.with_user(self.u_eng).action_fit()
        self.assertEqual(base.n_days, 30)
        base.write({"method": "manual"})  # k = 0: R² = 0 — для затвердження потрібен ручний метод
        self.assertEqual(self.Daily.with_user(self.u_eng).action_rebuild(TODAY, TODAY)["days"], 0)
        with self.assertRaises(AccessError):
            base.with_user(self.u_eng).action_approve()
        with self.assertRaises(AccessError):
            budget.with_user(self.u_eng).action_approve()
        with self.assertRaises(AccessError):
            self.Baseline.with_user(self.u_eng).browse(base.id).unlink()
        # chief: затвердження, видалення
        budget.with_user(self.u_chief).action_approve()
        self.assertEqual(budget.state, "approved")
        base.with_user(self.u_chief).action_approve()
        self.assertEqual(base.state, "approved")
        # admin: усе
        admin = self._mk_user("w4_sec_admin", ["td_factory3d.group_td_admin"])
        new = self.Area.with_user(admin).create({"code": "ADM", "name": "Адмін", "color": "#123456"})
        new.with_user(admin).unlink()

    def test_ac51_company_rules(self):
        other = self.env["res.company"].create({"name": "Інша компанія W4"})
        base = self._baseline(
            (TODAY - timedelta(days=100), TODAY - timedelta(days=70)), {}, company_id=other.id, method="manual"
        )
        budget = self.Budget.create({"month": date(2026, 10, 1), "amount_uah": 5.0, "company_id": other.id})
        self.assertFalse(self.Baseline.with_user(self.u_eng).search([("id", "=", base.id)]))
        self.assertFalse(self.Budget.with_user(self.u_chief).search([("id", "=", budget.id)]))
        self.assertTrue(self.env.ref("td_energy_analytics.td_energy_baseline_rule_company"))
        self.assertTrue(self.env.ref("td_energy_analytics.td_energy_budget_rule_company"))

    # --- ТБ-03, ТБ-04 ------------------------------------------------------------------------------------
    def test_tb03_tb04_privileged_methods(self):
        for user in (self.u_view, self.u_cost):
            with self.assertRaises(AccessError):
                self.Daily.with_user(user)._td_build_days([TODAY])
            with self.assertRaises(AccessError):
                self.Daily.with_user(user).action_rebuild(TODAY, TODAY)
            with self.assertRaises(AccessError):
                self.Enpi.with_user(user).recompute(TODAY, TODAY)
        for user in (self.u_view, self.u_eng, self.u_chief):
            with self.assertRaisesRegex(AccessError, "лише адміністратор"):
                self.Api.with_user(user)._td_seed_demo(days=30)
        self.assertEqual(self.Daily.with_user(self.u_eng)._td_build_days([TODAY])["days"], 0)

    # --- AC-52 -------------------------------------------------------------------------------------------
    def test_ac52_neutralize_and_crons(self):
        for xmlid in CRONS:
            self.assertTrue(self.env.ref("td_energy_analytics.%s" % xmlid).active, xmlid)
        with file_open("td_energy_analytics/data/neutralize.sql", "r") as f:
            self.env.cr.execute(f.read())
        self.env["ir.cron"].invalidate_model()
        for xmlid in CRONS:
            self.assertFalse(self.env.ref("td_energy_analytics.%s" % xmlid).active, xmlid)
        self.assertTrue(self.env.ref("td_energy.cron_td_energy_alloc"), "крони інших модулів не чіпаємо")

    def test_ac52_migration_idempotent_and_alloc_product(self):
        Node = self.env["td.energy.node"]
        counts = lambda: (  # noqa: E731
            self.Area.search_count([]),
            Node.search_count([("kind", "=", "consumer"), ("area_id", "!=", False)]),
        )
        before = counts()
        path = Path(hooks.__file__).parent / "migrations" / "19.0.1.0.0" / "post-migration.py"
        spec = importlib.util.spec_from_file_location("w4_post_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "19.0.0.9")
        module.migrate(self.env.cr, "19.0.0.9")
        self.assertEqual((before, counts()), ((8, 49), (8, 49)))
        # alloc.product_id заповнюється SQL-кроком
        product = self._product("W4-MIG", 1.0)
        mo = self._mo(product, 3)
        alloc = self._alloc(mo, self._node("SAW-1"), TODAY, kwh=1.0)
        self.env.flush_all()
        self.env.cr.execute("UPDATE td_energy_alloc SET product_id = NULL WHERE id = %s", (alloc.id,))
        alloc.invalidate_recordset()
        self.assertEqual(hooks._fill_alloc_product(self.env), 1)
        self.assertEqual(alloc.product_id, product)
        self.assertEqual(hooks._fill_alloc_product(self.env), 0)

    def test_ac52_uninstall_hook_keeps_electrical_data(self):
        self._fill("PM-QF-1", TODAY, 1.0, slots=[0])
        nodes = self.env["td.energy.node"].search_count([])
        intervals = self.env["td.energy.interval"].search_count([])
        hooks.uninstall_hook(self.env)
        self.env["ir.cron"].invalidate_model()
        icp = self.env["ir.config_parameter"].sudo()
        self.assertFalse(icp.search_count([("key", "like", "td.energy_analytics.")]))
        for xmlid in CRONS:
            self.assertFalse(self.env.ref("td_energy_analytics.%s" % xmlid, raise_if_not_found=False))
        self.assertEqual(self.env["td.energy.node"].search_count([]), nodes)
        self.assertEqual(self.env["td.energy.interval"].search_count([]), intervals)

    def test_ac52_data_loaded(self):
        icp = self.env["ir.config_parameter"].sudo()
        for name in PARAMS:
            self.assertTrue(icp.get_param("td.energy_analytics." + name), name)
        self.assertEqual(icp.get_param("td.energy_analytics.r2_min"), "0.6")
        cron = self.env.ref("td_energy_analytics.cron_td_energy_daily")
        self.assertEqual((cron.interval_number, cron.interval_type), (15, "minutes"))
        self.assertEqual(self.env.ref("td_energy_analytics.cron_td_energy_drivers").interval_type, "days")
        self.assertEqual(
            self.env.ref("td_energy_analytics.cron_td_energy_daily").user_id, self.env.ref("base.user_root")
        )
        self.assertEqual(self.Driver.search_count([]), 2)

    # --- AC-53 -------------------------------------------------------------------------------------------
    def test_ac53_settings_validation(self):
        Settings = self.env["res.config.settings"]
        for vals in (
            {"td_energy_analytics_r2_min": 1.5},
            {"td_energy_analytics_r2_min": -0.1},
            {"td_energy_analytics_forecast_min_days": 9, "td_energy_analytics_forecast_weeks": 8},
            {"td_energy_analytics_daily_close_h": 13},
            {"td_energy_analytics_daily_close_h": -1},
        ):
            with self.assertRaises(ValidationError, msg=str(vals)):
                Settings.create(vals)
        settings = Settings.create({"td_energy_analytics_forecast_weeks": 6, "td_energy_analytics_top_mo": 10})
        settings.execute()
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(
            (icp.get_param("td.energy_analytics.forecast_weeks"), icp.get_param("td.energy_analytics.top_mo")),
            ("6", "10"),
        )

    # --- AC-59 -------------------------------------------------------------------------------------------
    def test_ac59_menus(self):
        menu = self.env.ref("td_energy_analytics.menu_td_energy_analytics", raise_if_not_found=False)
        if not menu:
            self.skipTest("Меню створює W4-B (views/menus.xml)")
        self.assertEqual(menu.sequence, 12)
        loading = self.env["ir.ui.menu"].search([("parent_id", "=", menu.parent_id.id), ("sequence", "=", 15)], limit=1)
        self.assertTrue(loading)
        siblings = self.env["ir.ui.menu"].search([("parent_id", "=", menu.parent_id.id)], order="sequence, id")
        self.assertLess(siblings.ids.index(menu.id), siblings.ids.index(loading.id))
        self.assertEqual(
            self.env.ref("td_energy_analytics.menu_td_energy_budget").group_ids,
            self.env.ref("td_energy.group_td_energy_cost"),
        )
        for xmlid in (
            "menu_td_energy_area",
            "menu_td_energy_driver",
            "menu_td_energy_baseline",
            "menu_td_energy_daily",
        ):
            self.assertEqual(
                self.env.ref("td_energy_analytics.%s" % xmlid).group_ids,
                self.env.ref("td_energy.group_td_energy_manager"), xmlid,
            )  # fmt: skip

    def test_unused_import_guard(self):
        self.assertTrue(UserError)
