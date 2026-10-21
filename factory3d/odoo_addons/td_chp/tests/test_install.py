"""AC-01 (установка), AC-20 (neutralize.sql)."""

from odoo.tests import tagged
from odoo.tools import file_open

from .. import hooks
from .common import TAGS, ChpCase


@tagged(*TAGS)
class TestInstall(ChpCase):
    def test_install(self):  # AC-01
        self.skip_if_bridge()  # міст переносить сигнали на джерело Енергетики (MB-U72-CHP)
        self.assertEqual(self.unit.code, "CHP")
        self.assertEqual(self.source.code, "CHP-U72")
        self.assertEqual(self.source.module, "chp")
        self.assertEqual(self.source.params["unit"], 72)
        sigs = self.Signal.with_context(active_test=False).search([("module", "=", "chp")])
        self.assertEqual(len(sigs), 230)
        self.assertTrue(all(s.origin == "module" and s.source_id == self.source for s in sigs))
        self.assertEqual(len(self.unit.rule_ids), 5)
        for name in ("user", "operator", "chief"):
            self.assertTrue(self.env.ref(f"td_chp.group_td_chp_{name}"))
        crons = self.env["ir.model.data"].search([("module", "=", "td_chp"), ("model", "=", "ir.cron")])
        self.assertEqual(len(crons), 4)

    def test_post_init_idempotent(self):  # AC-01: повторне встановлення/оновлення не дублює
        hooks.post_init(self.env)
        hooks.post_init(self.env)
        self.assertEqual(self.Signal.with_context(active_test=False).search_count([("module", "=", "chp")]), 230)
        self.assertEqual(self.env["td.chp.unit"].search_count([]), 1)
        self.assertEqual(self.env["td.chp.maintenance.rule"].search_count([]), 5)

    def test_defaults(self):
        icp = self.env["ir.config_parameter"].sudo()
        for key in ("confirm_ttl_s", "second_ttl_s", "verify_timeout_s", "command_ttl_s", "stale_s", "bus_throttle_s"):
            self.assertTrue(icp.get_param("td.chp." + key), key)
        self.assertEqual(icp.get_param("td.chp.event_keep_days"), "365")

    def test_neutralize(self):  # AC-20
        self.enable_write(True)
        with file_open("td_chp/data/neutralize.sql") as f:
            self.env.cr.execute(f.read())
        self.env.invalidate_all()
        for flag in ("write_enabled", "remote_switching_enabled"):
            self.env.cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", ["td.chp." + flag])
            self.assertEqual(self.env.cr.fetchone()[0], "False", flag)
        self.assertFalse(self.source.write_enabled)
        sigs = self.Signal.sudo().search([("module", "=", "chp")])
        self.assertFalse(any(sigs.mapped("write_enabled")))
        data = self.env["ir.model.data"].search([("module", "=", "td_chp"), ("model", "=", "ir.cron")])
        crons = self.env["ir.cron"].with_context(active_test=False).browse(data.mapped("res_id"))
        self.assertEqual(len(crons), 4)
        self.assertFalse(any(crons.mapped("active")))

    def test_uninstall_hook_removes_only_crons_and_params(self):
        hooks.uninstall_hook(self.env)
        data = self.env["ir.model.data"].search([("module", "=", "td_chp"), ("model", "=", "ir.cron")])
        self.assertFalse(self.env["ir.cron"].with_context(active_test=False).browse(data.mapped("res_id")).exists())
        self.assertFalse(self.env["ir.config_parameter"].sudo().search([("key", "=like", "td.chp.%")]))
        self.assertEqual(self.Signal.with_context(active_test=False).search_count([("module", "=", "chp")]), 230)
        self.assertTrue(self.unit.exists())
