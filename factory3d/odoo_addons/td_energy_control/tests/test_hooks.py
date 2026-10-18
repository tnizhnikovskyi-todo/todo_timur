"""AC-229, AC-230, AC-232, AC-235: post_init_hook, стенд, деінсталяція без архівних таблиць (D-45)."""

from odoo.tests import tagged

from .. import hooks
from .common import TAGS, TestControlCommon


@tagged(*TAGS)
class TestHooks(TestControlCommon):
    def counts(self):
        env = self.env
        return {
            "sources": env["td.source"].sudo().search_count([("module", "=", "energy_control")]),
            "signals": env["td.signal"].sudo().search_count([("module", "=", "energy_control")]),
            "scenarios": env["td.energy.scenario"].search_count([]),
            "kinds": env["td.energy.command.kind"].search_count([]),
            "interlocks": env["td.energy.interlock"].search_count([]),
            "shed": env["td.energy.shed.item"].search_count([]),
            "state": env["td.energy.control.state"].search_count([]),
        }

    def test_install_counts(self):  # AC-229
        got = self.counts()
        self.assertEqual((got["sources"], got["signals"]), (2, 36))
        self.assertEqual(
            (got["scenarios"], got["kinds"], got["interlocks"], got["shed"], got["state"]), (6, 16, 20, 5, 1)
        )
        self.assertGreaterEqual(self.Slot.search_count([]), 10)
        reg = (
            self.env["td.signal"]
            .sudo()
            .search([("code", "like", "energy_control/%"), ("source_id.code", "=", "MB-U73-SWB-CMD")])
        )
        self.assertEqual(len(reg), 28)
        addrs = sorted(sig.address["addr"] for sig in reg)
        self.assertEqual((addrs[0], addrs[-1]), (200, 291))
        hooks.post_init_hook(self.env)  # ідемпотентність
        self.assertEqual(self.counts(), got)

    def test_enable_stand(self):  # AC-230
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("td.telemetry.write_enabled", "False")
        for flag in hooks.FLAGS:
            icp.set_param(hooks.PARAM + flag, "False")
        self.env["td.source"].sudo().search([("module", "=", "energy_control")]).write({"write_enabled": False})
        self.env["td.signal"].sudo().search([("module", "=", "energy_control")]).write({"write_enabled": False})
        changes = hooks._td_enable_stand(self.env)
        self.assertTrue(changes)
        for key in (
            "td.telemetry.write_enabled",
            "td.energy_control.write_enabled",
            "td.energy_control.automation_enabled",
            "td.energy_control.remote_switching_enabled",
        ):
            self.assertEqual(icp.get_param(key), "True", key)
        sig = self.env["td.signal"].sudo().search([("code", "=", "energy_control/qs/cmd")])
        self.assertTrue(sig.write_enabled)
        self.assertFalse(self.env["td.signal"].sudo().search([("code", "=", "energy_control/qs/ack")]).write_enabled)
        self.assertTrue(self.env["td.signal"].sudo().search([("code", "=", "energy_control/intent")]).write_enabled)
        self.assertFalse(hooks._td_enable_stand(self.env))  # повторний виклик нічого не змінює

    def test_uninstall(self):  # AC-232
        hooks.uninstall_hook(self.env)
        self.assertEqual(
            self.env["td.signal"]
            .sudo()
            .with_context(active_test=False)
            .search_count([("module", "=", "energy_control")]),
            0,
        )
        self.assertEqual(
            self.env["td.source"].sudo().with_context(active_test=False).search_count([("type", "=", "energy_ctl")]), 0
        )
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.search_count([("key", "=like", "td.energy_control.%")]), 0)
        data_ids = (
            self.env["ir.model.data"]
            .search([("module", "=", "td_energy_control"), ("model", "=", "ir.cron")])
            .mapped("res_id")
        )
        self.assertFalse(self.env["ir.cron"].with_context(active_test=False).search([("id", "in", data_ids)]))
        self.env.cr.execute("SELECT to_regclass('td_energy_action_archive'), to_regclass('td_energy_scenario_archive')")
        self.assertEqual(self.env.cr.fetchone(), (None, None))  # архівних таблиць немає (D-45)
        self.assertFalse(hasattr(hooks, "_restore_archive"))

    def test_repeat_load_keeps_counts(self):  # AC-235
        before = self.counts()
        hooks._load_sources_signals(self.env)
        hooks._seed_defaults(self.env)
        self.assertEqual(self.counts(), before)
