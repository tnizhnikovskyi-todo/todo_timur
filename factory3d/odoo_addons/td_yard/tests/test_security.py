import csv
import logging
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged
from odoo.tools import file_open

from ..tools import params as P
from .flow import YardFlowCase

MENUS = (
    # xml-id, батько, sequence, група, дія
    ("menu_td_yard_dispatch", "menu_td_yard", 10, "td_factory3d.group_td_user", "action_td_yard_dispatch"),
    ("menu_td_yard_kpp", "menu_td_yard", 20, "group_td_yard_security", "action_td_yard_kpp"),
    ("menu_td_yard_booking", "menu_td_yard", 30, "td_factory3d.group_td_user", "action_td_yard_booking"),
    ("menu_td_yard_visit", "menu_td_yard", 40, "td_factory3d.group_td_user", "action_td_yard_visit"),
    ("menu_td_yard_dispatch_std", "menu_td_yard", 45, "group_td_yard_dispatcher", "action_td_yard_dispatch_std"),
    ("menu_td_yard_journals", "menu_td_yard", 50, "td_factory3d.group_td_user", None),
    ("menu_td_yard_lpr", "menu_td_yard_journals", 10, "group_td_yard_security", "action_td_yard_lpr_event"),
    (
        "menu_td_yard_weighing",
        "menu_td_yard_journals",
        20,
        "td_factory3d.group_td_user",
        "action_td_yard_weighing",
    ),
    ("menu_td_yard_commands", "menu_td_yard_journals", 30, "group_td_yard_security", "action_td_yard_command"),
    ("menu_td_yard_reports", "menu_td_yard", 60, "group_td_yard_dispatcher", None),
    ("menu_td_yard_config", "menu_td_yard", 90, "group_td_yard_manager", None),
    ("menu_td_yard_config_gate", "menu_td_yard_config", 10, "group_td_yard_manager", "action_td_yard_gate"),
    ("menu_td_yard_config_scale", "menu_td_yard_config", 20, "group_td_yard_manager", "action_td_yard_scale"),
    (
        "menu_td_yard_config_migration",
        "menu_td_yard_config",
        90,
        "td_factory3d.group_td_admin",
        "action_td_yard_run_migration",
    ),
)


def _xmlid(name):
    return name if "." in name else "td_yard." + name


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardSecurity(YardFlowCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_stock = new_test_user(cls.env, "yard_stock", groups="stock.group_stock_user")
        cls.users = {
            "reader": cls.user_reader,
            "stock": cls.user_stock,
            "guard": cls.user_guard,
            "dispatcher": cls.user_dispatcher,
            "manager": cls.user_manager,
        }

    # ------------------------------------------------------------------ AC-66
    def test_menus_and_groups(self):  # AC-66
        root = self.env.ref("td_yard.menu_td_yard")
        self.assertEqual((root.parent_id, root.sequence), (self.env.ref("td_factory3d.menu_td_root"), 60))
        for xmlid, parent, seq, group, action in MENUS:
            menu = self.env.ref("td_yard." + xmlid)
            self.assertEqual(menu.parent_id, self.env.ref("td_yard." + parent), xmlid)
            self.assertEqual(menu.sequence, seq, xmlid)
            self.assertEqual(menu.group_ids, self.env.ref(_xmlid(group)), xmlid)
            if action:
                self.assertEqual(menu.action, self.env.ref("td_yard." + action), xmlid)
        settings = self.env.ref("td_yard.menu_td_yard_config_settings")
        self.assertEqual((settings.parent_id, settings.sequence), (self.env.ref("td_factory3d.menu_td_config"), 60))
        self.assertEqual(settings.action, self.env.ref("td_yard.action_td_yard_settings"))
        sec = self.env.ref("td_yard.group_td_yard_security")
        disp = self.env.ref("td_yard.group_td_yard_dispatcher")
        mgr = self.env.ref("td_yard.group_td_yard_manager")
        admin = self.env.ref("td_factory3d.group_td_admin")
        self.assertIn(sec, disp.implied_ids)
        self.assertIn(disp, mgr.implied_ids)
        self.assertIn(mgr, admin.implied_ids)
        self.assertIn(self.env.ref("stock.group_stock_user"), disp.implied_ids)

    # ------------------------------------------------------------------ AC-67
    def test_access_matrix(self):  # AC-67
        with file_open("td_yard/security/ir.model.access.csv", "rb") as fh:
            rows = list(csv.DictReader(fh.read().decode("utf-8").splitlines()))
        by_model = {}
        for row in rows:
            by_model.setdefault(row["model_id:id"], []).append(row)
        ops = ("read", "write", "create", "unlink")
        for model_xmlid, model_rows in by_model.items():
            model = self.env.ref("td_yard." + model_xmlid).model
            for role, user in self.users.items():
                expected = dict.fromkeys(ops, False)
                for row in model_rows:
                    group = row["group_id:id"]
                    if user.has_group(_xmlid(group)):
                        for op in ops:
                            expected[op] = expected[op] or row["perm_" + op] == "1"
                for op in ops:
                    got = self.env[model].with_user(user).has_access(op)
                    self.assertEqual(got, expected[op], "%s %s %s" % (model, role, op))

    # ------------------------------------------------------------------ AC-68
    def test_pii_fields(self):  # AC-68
        visit = self._visit(plate="АА1234КТ", driver_phone="+380501112233", driver_doc="ВВ123456")
        reader = self.env["td.yard.visit"].with_user(self.user_reader).browse(visit.id)
        with self.assertRaises(AccessError):
            reader.read(["driver_phone"])
        with self.assertRaises(AccessError):
            reader.driver_doc  # noqa: B018
        rows = (
            self.env["td.yard.visit"]
            .with_user(self.user_reader)
            .search_read([("id", "=", visit.id)], ["name", "plate"])
        )
        self.assertEqual(rows[0]["plate"], "АА1234КТ")
        gate = self.env.ref("td_yard.gate_w").with_user(self.user_reader)
        with self.assertRaises(AccessError):
            gate.read(["last_plate"])
        guard = visit.with_user(self.user_guard)
        self.assertEqual(guard.driver_doc, "ВВ123456")

    # ------------------------------------------------------------------ AC-69
    def test_company_rule(self):  # AC-69
        company_b = self.env["res.company"].create({"name": "Компанія B (двір)"})
        visit_b = self._visit(plate="ВВ0001ТТ", company_id=company_b.id)
        user_a = new_test_user(self.env, "yard_only_a", groups="td_yard.group_td_yard_dispatcher")
        user_a.company_ids = [Command.set([self.env.company.id])]
        user_a.company_id = self.env.company
        self.assertEqual(self.env["td.yard.visit"].with_user(user_a).search_count([("id", "=", visit_b.id)]), 0)
        self.assertEqual(self.env["td.yard.visit"].search_count([("id", "=", visit_b.id)]), 1)

    # ------------------------------------------------------------------ AC-59
    def test_journal_actions(self):  # AC-59
        guard, reader = self.user_guard, self.user_reader
        lpr = self.env.ref("td_yard.action_td_yard_lpr_event")
        weighing = self.env.ref("td_yard.action_td_yard_weighing")
        command = self.env.ref("td_yard.action_td_yard_command")
        for action in (lpr, weighing, command):
            self.env[action.res_model].with_user(guard).search_count([])
        self.env["td.yard.weighing"].with_user(reader).search_count([])
        with self.assertRaises(AccessError):
            self.env["td.yard.lpr.event"].with_user(reader).search_count([])
        self.assertIn("td_yard_gate_id", command.domain)
        gate = self.env.ref("td_yard.gate_w")
        sig = self.env["td.signal"].create(
            {"code": "other/cmd/z", "name": "T", "kind": "gauge", "write_enabled": True}
        )
        self.env["ir.config_parameter"].sudo().set_param("td.telemetry.write_enabled", "True")
        Cmd = self.env["td.command"].sudo()
        mine = Cmd.create({"signal_id": sig.id, "value": 1, "td_yard_gate_id": gate.id})
        foreign = Cmd.create({"signal_id": sig.id, "value": 1})
        shown = Cmd.with_user(guard).search(self._domain(command))
        self.assertIn(mine, shown)
        self.assertNotIn(foreign, shown)

    def _domain(self, action):
        from odoo.tools.safe_eval import safe_eval

        return safe_eval(action.domain or "[]")

    # ------------------------------------------------------------------ AC-73
    def test_neutralize_sql(self):  # AC-73
        icp = self.env["ir.config_parameter"].sudo()
        for name in ("write_enabled", "read_enabled"):
            P.set_param(self.env, name, "True")
        gate = self.env.ref("td_yard.gate_w")
        gate.sudo().write({"mode": "auto"})
        source = self.env["td.source"].search([("code", "=", "MB-U86-IO7")])
        source.sudo().write({"read_enabled": True})
        self.env["ir.cron"].browse(self.env.ref("td_yard.cron_td_yard_queue").id).active = True
        self.env.flush_all()
        self.cr.execute(file_open("td_yard/data/neutralize.sql").read())
        self.env.invalidate_all()
        self.env.registry.clear_cache("stable")
        self.assertEqual(icp.get_param("td.yard.write_enabled"), "False")
        self.assertEqual(icp.get_param("td.yard.read_enabled"), "False")
        self.cr.execute(
            "SELECT count(*) FROM ir_cron c JOIN ir_model_data d ON d.model = 'ir.cron' "
            "AND d.res_id = c.id AND d.module = 'td_yard' WHERE c.active"
        )
        self.assertEqual(self.cr.fetchone()[0], 0)
        self.assertEqual(gate.mode, "manual")
        self.assertEqual((source.read_enabled, source.write_enabled), (False, False))

    # ------------------------------------------------------------------ AC-74
    def test_no_secrets_in_params(self):  # AC-74
        keys = self.env["ir.config_parameter"].sudo().search([("key", "=like", "td.yard.%")]).mapped("key")
        self.assertTrue(keys)
        for key in keys:
            for word in ("token", "secret", "password"):
                self.assertNotIn(word, key)

    def test_logs_without_pii(self):  # AC-74
        from .gate_case import lpr_event

        logger = "odoo.addons.td_yard"
        visit = self._visit(plate="АА4512КТ", driver_phone="+380501112233", driver_doc="ВВ123456")
        marker = "QQmarkerQQ"
        image = "/9j/" + "A" * 300
        with self.assertLogs(logger, level="INFO") as cm:
            logging.getLogger(logger).info(marker)
            event = lpr_event(1, imageArray=[image])
            self.env["td.yard.lpr.event"].sudo()._f3d_from_push(event)
            visit.sudo().message_post(body="тест")
            self.env["td.yard.visit"]._cron_gc()
        text = "\n".join(cm.output)
        for secret in ("+380501112233", "ВВ123456", image[:40]):
            self.assertNotIn(secret, text)

    # ------------------------------------------------------------------ AC-55
    def test_dispatch_std_action(self):  # AC-55
        from odoo.api import Environment

        action = self.env.ref("td_yard.action_td_yard_dispatch_std")
        res = action.with_context(active_model="stock.picking.batch").run()
        self.assertEqual(res["domain"], [("dock_id", "!=", False)])
        self.assertNotIn("gantt", res["view_mode"])
        view = self.env["ir.ui.view"].search([("type", "=", "list")], limit=1)
        original = Environment.ref

        def fake_ref(env, xmlid, raise_if_not_found=True):
            if xmlid.endswith("view_stock_picking_batch_gantt"):
                return view
            return original(env, xmlid, raise_if_not_found)

        with patch.object(Environment, "ref", fake_ref):
            res = action.with_context(active_model="stock.picking.batch").run()
        self.assertEqual(res["views"][0], (view.id, "gantt"))
        self.assertEqual(res["domain"], [("dock_id", "!=", False)])
