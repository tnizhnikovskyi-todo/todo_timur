"""AC-92: `uninstall_hook` і `data/neutralize.sql`."""

from odoo.addons.factory3d_machine_connect import hooks
from odoo.tests import tagged
from odoo.tools import file_open

from .common import F3DMachineCase

P = "factory3d.machine_connect."
STOPS = ("read_enabled", "auto_start_enabled", "write_enabled", "gantry_auto_replenish", "gantry_auto_feed")


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestHooks(F3DMachineCase):
    def _module_crons(self):
        ids = (
            self.env["ir.model.data"]
            .search([("module", "=", hooks.MODULE), ("model", "=", "ir.cron")])
            .mapped("res_id")
        )
        return self.env["ir.cron"].with_context(active_test=False).browse(ids).exists()

    def test_uninstall_hook_params_crons(self):
        crons = self._module_crons()
        self.assertEqual(len(crons), 5)
        signals = (
            self.env["f3d.signal"].with_context(active_test=False).search_count([("module", "=", "machine_connect")])
        )
        sources = (
            self.env["f3d.source"].with_context(active_test=False).search_count([("module", "=", "machine_connect")])
        )
        self.assertTrue(self.env["ir.config_parameter"].search([("key", "=like", P + "%")]))
        other = self.env["ir.config_parameter"].sudo().create({"key": "factory3d.machine_connectX", "value": "keep"})
        hooks.uninstall_hook(self.env)
        self.assertFalse(self.env["ir.config_parameter"].search([("key", "=like", P + "%")]))
        self.assertTrue(other.exists())
        self.assertFalse(any(crons.mapped("active")))
        self.assertEqual(
            self.env["f3d.signal"].with_context(active_test=False).search_count([("module", "=", "machine_connect")]),
            signals,
        )
        self.assertEqual(
            self.env["f3d.source"].with_context(active_test=False).search_count([("module", "=", "machine_connect")]),
            sources,
        )

    def test_neutralize_sql(self):
        icp = self._icp()
        for key in STOPS:
            icp.set_param(P + key, "True")
        icp.set_param(P + "cutting_mode", "collector")
        self.env["f3d.machine"].search([]).write({"read_enabled": True, "auto_start_mode": "job_or_single"})
        self.env["f3d.cut.map"].search([]).write({"export_token_hash": "x" * 64})
        self.env.flush_all()
        with file_open("%s/data/neutralize.sql" % hooks.MODULE, "r") as fh:
            sql = fh.read()
        self.env.cr.execute(sql)
        self.env.invalidate_all()
        icp.invalidate_recordset()
        for key in STOPS:
            self.assertEqual(self._param_sql(key), "False", key)
        self.assertEqual(self._param_sql("cutting_mode"), "manual")
        machines = self.env["f3d.machine"].with_context(active_test=False).search([])
        self.assertTrue(machines)
        self.assertFalse(any(machines.mapped("read_enabled")))
        self.assertEqual(set(machines.mapped("auto_start_mode")), {"off"})
        self.assertFalse(any(self.env["f3d.cut.map"].search([]).mapped("export_token_hash")))
        self.assertFalse(any(self._module_crons().mapped("active")))

    def _param_sql(self, key):
        self.env.cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (P + key,))
        return self.env.cr.fetchone()[0]
