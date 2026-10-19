from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import TAG_ARGS, SimCase

TOKEN_FIELDS = ("td_sim_token", "td_sim_export_token", "td_sim_url")


@tagged(*TAG_ARGS)
class TestSecurity(SimCase):
    def test_user_readonly(self):
        device = self.make_device("SEC-T1")
        as_user = self.env["td.sim.device"].with_user(self.user_reader)
        self.assertTrue(as_user.search([("code", "=", "SEC-T1")]))
        self.env["td.sim.panel"].with_user(self.user_reader).get_panel().read(["state"])
        with self.assertRaises(AccessError):
            device.with_user(self.user_reader).write({"name": "x"})
        with self.assertRaises(AccessError):
            as_user.create({"code": "SEC-T2", "name": "x"})
        with self.assertRaises(AccessError):
            self.env["td.sim.scenario"].with_user(self.user_reader).create({"code": "x", "name": "x", "group": "bms"})
        with self.assertRaises(AccessError):
            self.env["td.sim.run.wizard"].with_user(self.user_reader).create({})

    def test_manager_no_settings(self):
        device = self.make_device("SEC-T3")
        device.with_user(self.user_manager).write({"name": "ok"})
        with self.assertRaises(AccessError):
            self.env["td.sim.device"].with_user(self.user_manager).create({"code": "SEC-T4", "name": "x"})
        with self.assertRaises(AccessError):
            self.env["td.sim.event"].with_user(self.user_manager).create({"kind": "info", "message": "x"})

    def test_token_fields_admin_only(self):
        manager_fields = self.env["res.config.settings"].with_user(self.user_manager).fields_get()
        admin_fields = self.env["res.config.settings"].with_user(self.user_admin).fields_get()
        for name in TOKEN_FIELDS:
            self.assertNotIn(name, manager_fields)
            self.assertIn(name, admin_fields)
