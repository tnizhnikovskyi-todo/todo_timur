"""AC-89…AC-91: меню, матриця прав (§13.3 ТБ-01), стоп-крани в налаштуваннях, технічний користувач."""

from odoo.exceptions import AccessDenied, AccessError, ValidationError
from odoo.tests import tagged

from .common import F3DMachineCase

R, W, C, D = "read", "write", "create", "unlink"
# (модель, {користувач: операції}) за матрицею §13.3; відсутня позначка = AccessError.
# Колонки: user_f3d, user_mrp, user_stock_manager, user_f3d_manager, user_f3d_admin (`user_plain` — завжди «—»).
USERS = ("user_f3d", "user_mrp", "user_stock_manager", "user_f3d_manager", "user_f3d_admin")
MATRIX = {
    "f3d.machine": "R R R RWCD RWCD",
    "f3d.machine.state.log": "R R R R RWCD",
    "f3d.downtime": "R RW R R RWCD",
    "f3d.machine.event": "R R R R RWCD",
    "f3d.oee.shift": "R R R R RWCD",
    "f3d.machine.message": "R R R RWCD RWCD",
    "f3d.gantry.stack": "R R RW RWCD RWCD",
    "f3d.gantry.job": "R RWC R RWCD RWCD",
    "f3d.cut.part": "R R R RWCD RWCD",
    "f3d.cut.map": "R R R RWCD RWCD",
    "f3d.cut.map.line": "R R R RWCD RWCD",
    "f3d.downtime.reason.wizard": "- RWC - - -",
    "f3d.cut.plan.import.wizard": "- - - RWC RWC",
    "f3d.cut.part.import.wizard": "- - - RWC RWC",
}
OPS = {"R": R, "W": W, "C": C, "D": D}
P = "factory3d.machine_connect."


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestSecurity(F3DMachineCase):
    def _visible(self, user):
        return self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()

    def test_menu_and_access_matrix(self):
        root = self.env.ref("factory3d_machine_connect.menu_f3d_mc_root")
        settings = self.env.ref("factory3d_machine_connect.menu_f3d_mc_settings")
        self.assertEqual(root.parent_id, self.env.ref("factory3d_base.menu_f3d_root"))
        self.assertEqual(root.sequence, 40)
        self.assertEqual(settings.parent_id, self.env.ref("factory3d_base.menu_f3d_config"))
        self.assertEqual(settings.sequence, 40)
        self.assertEqual(settings.action.res_model, "res.config.settings")
        self.assertEqual(settings.action.context, "{'module': 'factory3d_machine_connect'}")
        self.assertIn(root.id, self._visible(self.user_f3d))
        self.assertNotIn(root.id, self._visible(self.user_plain))
        self.assertIn(settings.id, self._visible(self.user_f3d_manager))
        self.assertNotIn(settings.id, self._visible(self.user_f3d))
        for model, row in MATRIX.items():
            grants = dict(zip(USERS, row.split(), strict=True))
            for login in ("user_plain", *USERS):
                user = getattr(self, login)
                Model = self.env[model].with_user(user)
                allowed = grants.get(login, "").replace("-", "")
                for letter, op in OPS.items():
                    with self.subTest(model=model, user=login, op=op):
                        self.assertEqual(Model.has_access(op), letter in allowed)
        wc = self.env["mrp.workcenter"].create({"name": "Новий", "f3d_code": "NEW-T"})
        machine = (
            self.env["f3d.machine"]
            .with_user(self.user_f3d_manager)
            .create({"workcenter_id": wc.id, "protocol": "manual"})
        )
        self.assertEqual(machine.protocol, "manual")

    def test_company_rule(self):
        company2 = self.env["res.company"].create({"name": "C2 (тест)"})
        wc2 = (
            self.env["mrp.workcenter"]
            .with_company(company2)
            .create({"name": "РЦ C2", "f3d_code": "C2-1", "company_id": company2.id})
        )
        machine2 = (
            self.env["f3d.machine"].with_company(company2).create({"workcenter_id": wc2.id, "protocol": "manual"})
        )
        self.assertFalse(self.env["f3d.machine"].with_user(self.user_f3d).search([("id", "=", machine2.id)]))
        self.assertTrue(self.env["f3d.machine"].with_user(self.user_f3d).search([("id", "=", self.m_saw.id)]))

    def test_stock_actions(self):
        """Дії розбіжності стосу — лише `stock.group_stock_manager`."""
        with self.assertRaises(AccessError):
            self.stack_t1.with_user(self.user_stock).action_accept_portal()
        with self.assertRaises(AccessError):
            self.stack_t1.with_user(self.user_f3d_manager).action_fix_portal()

    def _settings(self, user, **vals):
        # Створення форми налаштувань іншими модулями (company-поля) — лише system: створюємо від su, зберігає `user`.
        return self.env["res.config.settings"].create(vals).with_user(user)

    def _save(self, **vals):
        """Збереження «успішного» шляху від su: `set_values` інших модулів (поля з groups) недоступні не-system."""
        self.env["res.config.settings"].create(vals).set_values()

    def test_settings_admin_only(self):
        icp = self._icp()
        with self.assertRaises(AccessError):
            self._settings(self.user_f3d_manager, f3d_mc_write_enabled=True).set_values()
        self.assertEqual(icp.get_param(P + "write_enabled"), "False")
        for vals in ({"f3d_mc_read_enabled": False}, {"f3d_mc_cutting_mode": "manual"}, {"f3d_mc_keep_log_days": 100}):
            with self.assertRaises(AccessError):
                self._settings(self.user_f3d_manager, **vals).set_values()
        # поле групи manager — дозволено
        self._save(f3d_mc_micro_stop_s=90)
        self.assertEqual(icp.get_param(P + "micro_stop_s"), "90")
        # admin вмикає стоп-кран
        self._save(f3d_mc_write_enabled=True)
        self.assertEqual(icp.get_param(P + "write_enabled"), "True")
        with self.assertRaises(AccessError):
            self._settings(self.user_f3d_manager).action_f3d_mc_run_migration()

    def test_settings_bounds(self):
        bad = (
            {"f3d_mc_micro_stop_s": 4000},
            {"f3d_mc_pause_after_min": 0},
            {"f3d_mc_finish_idle_s": -1},
            {"f3d_mc_qty_sync_s": 10},
            {"f3d_mc_coverage_min": 1.5},
            {"f3d_mc_stack_diff_tolerance": 61},
            {"f3d_mc_stack_diff_confirm_min": 0},
            {"f3d_mc_export_token_ttl_s": 30},
            {"f3d_mc_keep_log_days": 10},
            {"f3d_mc_keep_event_days": 3},
            {"f3d_mc_oee_warn": 0.8},  # warn ≥ good (0.75)
            {"f3d_mc_oee_good": 0.4},  # good ≤ warn (0.5)
        )
        for vals in bad:
            with self.subTest(vals=vals), self.assertRaises(ValidationError):
                self._settings(self.user_f3d_admin, **vals).set_values()
        with self.assertRaises(ValidationError) as ctx:
            self._settings(self.user_f3d_admin, f3d_mc_keep_log_days=10).set_values()
        self.assertIn("поза межами 30", str(ctx.exception))
        self._save(f3d_mc_oee_good=0.9, f3d_mc_oee_warn=0.6, f3d_mc_keep_event_days=7)
        self.assertEqual(self._icp().get_param(P + "oee_good"), "0.9")
        self.assertEqual(self._settings(self.user_f3d_admin).f3d_mc_migration_state, "done")

    def test_tech_user(self):
        user = self.env.ref("factory3d_machine_connect.user_f3d_machine").with_context(active_test=False)
        self.assertEqual(user.login, "f3d_machine_bot")
        self.assertFalse(user.active)
        self.assertFalse(user.share)
        self.env.cr.execute("SELECT password FROM res_users WHERE id = %s", (user.id,))
        self.assertFalse(self.env.cr.fetchone()[0])
        for xmlid in (
            "base.group_user",
            "mrp.group_mrp_user",
            "stock.group_stock_user",
            "maintenance.group_equipment_manager",
            "factory3d_base.group_f3d_user",
        ):
            self.assertTrue(user.has_group(xmlid), xmlid)
        for xmlid in ("base.group_system", "factory3d_base.group_f3d_manager"):
            self.assertFalse(user.has_group(xmlid), xmlid)
        for secret in ("", "x", "f3d_machine_bot"):
            with self.assertRaises(AccessDenied):
                self.env["res.users"].authenticate(
                    {"type": "password", "login": "f3d_machine_bot", "password": secret}, {"interactive": False}
                )
