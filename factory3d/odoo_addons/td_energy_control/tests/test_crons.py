"""AC-233, AC-234: крони завершення прострочених і нагляду за рушієм."""

from datetime import timedelta

from odoo.tests import tagged

from .common import NOW, TAGS, TestControlCommon


@tagged(*TAGS)
class TestCrons(TestControlCommon):
    def at(self, seconds):
        return self.Action.with_context(f3d_now=NOW + timedelta(seconds=seconds))

    def test_expire(self):  # AC-233
        prep = self.ctl(self.u_en1).prepare("bess_charge")
        awaiting = self.run_action("qs_close", user=self.u_en1)
        queued = self.run_action("light_break", user=self.u_en1)
        queued.command_id.write({"expires_at": NOW + timedelta(seconds=30)})
        running = self.run_action("vent_eco", user=self.u_en1)
        self.finish(running, "executing")
        running._me().write({"started_at": NOW})
        self.at(61)._cron_expire()
        self.assertEqual(self.Action.browse(prep["action_id"]).state, "expired")
        self.assertEqual(running.state, "executing")
        self.assertEqual(awaiting.state, "awaiting_second")
        self.at(601)._cron_expire()
        self.assertEqual(awaiting.state, "expired")
        self.assertEqual(queued.state, "expired")
        self.assertEqual(queued.command_id.state, "expired")
        self.assertEqual(running.state, "failed")  # 601 с > exec_timeout_s + 30
        self.assertIn("Немає підтвердження", running.error)
        events = self.env["td.energy.event"].search([("kind", "=", "control")])
        self.assertTrue(any("Немає підтвердження" in e.text or "Керування" in e.text for e in events))

    def test_config_not_applied_event(self):
        act = self.run_action("scenario_toggle", {"scenario": "pfc", "enabled": False}, user=self.u_chief)
        self.at(61)._cron_expire()
        self.at(70)._cron_expire()
        events = self.env["td.energy.event"].search([("code", "=", "CONFIG-NOT-APPLIED")])
        self.assertEqual(len(events), 1)
        self.assertIn("v%d" % act.config_version, events.text)

    def test_watch(self):  # AC-234
        self.env["ir.config_parameter"].sudo().set_param("td.energy.read_enabled", "True")
        state = self.State.get()
        state.write({"heartbeat_at": NOW - timedelta(seconds=600)})
        Event = self.env["td.energy.event"]
        self.State._td_watch()
        hb = Event.search([("code", "=", "CTRL-HEARTBEAT")])
        self.assertEqual(len(hb), 1)
        self.assertEqual(hb.level, "bad")
        self.State._td_watch()
        self.assertEqual(Event.search_count([("code", "=", "CTRL-HEARTBEAT")]), 1)  # dedup 15 хв
        state.write({"heartbeat_at": NOW - timedelta(seconds=5)})
        self.State._td_watch()
        self.assertEqual(Event.search([("code", "=", "CTRL-HEARTBEAT")]).state, "resolved")
        etag, version = state.config_etag, state.config_version
        self.env["td.bms.hvac.unit"].sudo().search([("kind", "=", "roofvent")], limit=1).write(
            {"mode_signal_id": False}
        )
        self.State._td_watch()
        state.invalidate_recordset()
        self.assertNotEqual(state.config_etag, etag)
        self.assertGreater(state.config_version, version)
