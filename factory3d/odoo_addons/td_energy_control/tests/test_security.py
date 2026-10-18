"""AC-226, AC-227: матриця прав, токени, ін'єкції; ТБ-11…ТБ-15 (безпека керування)."""

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import TAGS, TestControlCommon


@tagged(*TAGS)
class TestSecurity(TestControlCommon):
    def test_matrix(self):  # AC-226
        with self.assertRaises(AccessError):
            self.ctl(self.u_view).prepare("bess_charge")
        with self.assertRaises(AccessError):
            self.ctl(self.u_plain).get_control()
        self.assertEqual(self.run_action("qs_close", user=self.u_en1).state, "awaiting_second")
        self.assertEqual(self.run_action("qs_open", user=self.u_chief).state, "queued")
        kind = self.Kind.search([("code", "=", "qs_close")])
        with self.assertRaises(AccessError):
            kind.with_user(self.u_chief).write({"cls": "A"})
        kind.with_user(self.u_admin).write({"sub_template": "секції 1 і 2 разом"})
        act = self.Action.search([], limit=1)
        for user in (self.u_en1, self.u_chief, self.u_admin):
            with self.assertRaises(AccessError):
                act.with_user(user).write({"state": "done"})
        sc = self.Scenario.search([("code", "=", "peak")])
        for user in (self.u_en1, self.u_chief):
            with self.assertRaises(AccessError):
                sc.with_user(user).write({"enabled": False})
        state_id = self.State.get().id
        for user in (self.u_en1, self.u_admin):
            with self.assertRaises(AccessError):
                self.State.with_user(user).browse(state_id).write({"engine_mode": "auto"})

    def test_token_abuse(self):  # AC-227
        prep = self.ctl(self.u_en1).prepare("bess_charge")
        with self.assertRaises(AccessError):
            self.ctl(self.u_chief).confirm(prep["token"])
        self.ctl(self.u_en1).cancel(prep["token"])
        with self.assertRaises(UserError):
            self.ctl(self.u_en1).confirm(prep["token"])
        for bad in ("x'; DROP TABLE td_energy_action;--", "bess_charge'--", "", None):
            with self.assertRaises(UserError), self.cr.savepoint():
                self.ctl(self.u_en1).prepare(bad)
        for params in ("строка", [1, 2], {"power_kw": "1; DROP"}, {"power_kw": True}, {"x": 1}):
            with self.assertRaises(UserError), self.cr.savepoint():
                self.ctl(self.u_en1).prepare("bess_charge", params)
        self.assertTrue(self.Action.search_count([]) > 0)

    def test_not_controlled_systems(self):  # ТБ-12, R-60
        from ..tools import kinds

        controlled = set(kinds.SIGNALS.values()) | {
            s["signal"]
            for s in __import__("odoo").addons.td_energy_control.tools.config_builder.build(self.env)["shed"]
        }
        for code in controlled:
            self.assertFalse(
                code.startswith(
                    (
                        "fire/",
                        "evacuation/",
                        "sprinklers/",
                        "smoke/",
                        "lightning/",
                        "access/",
                        "workcenters/",
                        "security/",
                        "yard/",
                    )
                ),
                code,
            )
        sources = self.env["td.source"].sudo().search([("module", "=", "energy_control")])
        self.assertTrue(all(not s.write_enabled or s.code in ("MB-U73-SWB-CMD", "ENERGY-CTL") for s in sources))

    def test_safeguards_default_off(self):  # ТБ-11
        icp = self.env["ir.config_parameter"].sudo()
        for flag in ("write_enabled", "automation_enabled", "remote_switching_enabled"):
            icp.set_param("td.energy_control." + flag, "False")
        for code in ("bess_charge", "qs_close", "genset_test"):
            with self.assertRaises(UserError), self.cr.savepoint():
                self.ctl(self.u_chief).prepare(code)
        tiles = self.ctl(self.u_chief).get_control()["commands"]
        self.assertFalse(any(t["enabled"] for t in tiles if t["code"] in ("qs_close", "bess_charge", "chp_start")))
