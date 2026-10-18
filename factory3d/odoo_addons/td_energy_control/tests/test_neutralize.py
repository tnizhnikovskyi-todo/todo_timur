"""AC-231: neutralize.sql."""

from odoo.tests import tagged
from odoo.tools import file_open

from .common import TAGS, TestControlCommon


@tagged(*TAGS)
class TestNeutralize(TestControlCommon):
    def test_neutralize(self):
        act = self.run_action("bess_charge", user=self.u_en1)
        self.assertEqual(act.state, "queued")
        with file_open("td_energy_control/data/neutralize.sql") as f:
            sql = f.read()
        self.env.cr.execute(sql)
        self.env.invalidate_all()
        for flag in ("write_enabled", "automation_enabled", "remote_switching_enabled"):
            self.env.cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", ["td.energy_control." + flag])
            self.assertEqual(self.env.cr.fetchone()[0], "False", flag)
        sources = (
            self.env["td.source"].sudo().with_context(active_test=False).search([("module", "=", "energy_control")])
        )
        self.assertTrue(sources)
        self.assertFalse(any(sources.mapped("write_enabled")) or any(sources.mapped("read_enabled")))
        self.assertFalse(
            any(self.env["td.signal"].sudo().search([("module", "=", "energy_control")]).mapped("write_enabled"))
        )
        data = self.env["ir.model.data"].search([("module", "=", "td_energy_control"), ("model", "=", "ir.cron")])
        crons = self.env["ir.cron"].with_context(active_test=False).browse(data.mapped("res_id"))
        self.assertEqual(len(crons), 3)
        self.assertFalse(any(crons.mapped("active")))
        self.assertEqual(act.command_id.state, "cancelled")
