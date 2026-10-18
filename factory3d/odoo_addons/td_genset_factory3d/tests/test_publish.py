from datetime import timedelta
from unittest import mock

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..adapters import telemetry
from .test_rules import TD, GensetCase

LINK_LOGGER = "odoo.addons.td_genset_factory3d.models.genset_link"
PFX = "infra/genset/GENSET/"


@tagged("post_install", "-at_install")
class TestPublish(GensetCase):
    def readings(self, link=None):
        link = link or self.link
        return self.env["td.reading"].search([("signal_id.code", "=like", telemetry.prefix(link.td_code) + "%")])

    def values(self):
        signals = self.env["td.signal"].search([("code", "=like", PFX + "%")])
        return {s.code[len(PFX) :]: s for s in signals}

    def test_publish_values(self):  # AC-07
        snap = self.snap()
        self.link._cron_publish()
        readings = self.readings()
        self.assertEqual(len(readings), 26)
        self.assertEqual(set(readings.mapped("ts")), {snap["ts"]})
        sig = self.values()
        expected = {
            "state": 7,
            "p_kw": 348.0,
            "load_pct": 68.6,
            "fuel_l": 500.2,
            "fuel_lph": 95.5,
            "autonomy_h": 5.2,
            "hours": 1213.0,
            "online": 1,
            "service_h_left": 37.0,
            "oil_bar": 4.4,
        }
        for leaf, value in expected.items():
            self.assertEqual(sig[leaf].last_value, value, leaf)
        self.assertTrue(self.link.last_publish_ts)
        self.assertFalse(self.link.last_publish_error)

    def test_stop_crane(self):  # AC-08
        self.set_param("read_enabled", "False")
        self.link._cron_publish()
        self.assertFalse(self.readings())
        with self.assertRaisesRegex(UserError, "td.genset.read_enabled"):
            self.link.with_user(self.user_manager).action_check()

    def test_idempotent_same_ts(self):  # AC-10
        self.link._publish_one()
        res = self.link._publish_one()
        self.assertEqual(len(self.readings()), 26)
        self.assertEqual(res["result"]["skipped"], 26)

    def test_signals_appendix_a(self):  # AC-11, T-4, T-6
        sig = self.values()
        self.assertEqual(len(sig), 26)
        self.assertEqual(self.link.source_id.code, "GENSET-RELAY")
        self.assertEqual(self.link.source_id.type, "td_genset")
        self.assertFalse(self.link.source_id.collector_id)
        for leaf, s in sig.items():
            self.assertEqual((s.period_s, s.store_period_s, s.scale, s.create_request), (100, 0, 1.0, False), leaf)
            self.assertEqual(s.alarm_high_on, leaf == "alarm_level", leaf)
            self.assertFalse(s.warn_low_on or s.warn_high_on or s.alarm_low_on, leaf)
            self.assertEqual(s.address, {"leaf": leaf})
            self.assertEqual(s.source_id, self.link.source_id)
        for leaf in ("kwh", "hours", "starts"):
            self.assertEqual(sig[leaf].kind, "counter")
        self.assertEqual(sig["state"].kind, "gauge")
        self.assertEqual(sig["alarm_level"].alarm_high, 0.5)

    def test_alarm_level_status(self):
        self.snap(alarms=[{"code": "oil_low_shutdown", "severity": "shutdown", "name": "x", "since": None}])
        self.link._publish_one()
        sig = self.values()["alarm_level"]
        self.assertEqual(sig.last_value, 2.0)
        self.assertEqual(sig.status, "alarm")
        if "maintenance_request_id" in sig._fields:
            self.assertFalse(sig.maintenance_request_id)

    def test_offline_min_changes_period(self):  # AC-62
        self.env["res.config.settings"].create({"td_genset_offline_min": 10}).set_values()
        for s in self.values().values():
            self.assertEqual(s.period_s, 200)

    def test_state_change_chatter(self):  # AC-27, AC-28
        def state_messages():
            return self.link.message_ids.filtered(lambda m: "Стан:" in (m.body or ""))

        self.link.last_state_json = {"state": 1, "online": 1}
        self.link._publish_one()
        self.assertEqual(len(state_messages()), 1)
        self.link._publish_one()
        self.assertEqual(len(state_messages()), 1)
        self.snap(online=False)
        self.link._publish_one()
        self.assertEqual(len(state_messages()), 1)
        self.assertFalse(self.link.online)

    def test_offline_stale(self):  # AC-40, R-12
        self.snap(ts=fields.Datetime.now() - timedelta(minutes=2))
        self.link._publish_one()
        self.snap(ts=fields.Datetime.now() - timedelta(minutes=7))
        self.link._publish_one()
        sig = self.values()
        self.assertEqual(sig["online"].last_value, 0.0)
        self.assertEqual(sig["state"].last_value, 0.0)
        self.assertEqual(sig["state"].status, "ok")
        stale = [leaf for leaf, s in sig.items() if s.status == "stale"]
        self.assertEqual(sorted(stale), sorted(telemetry.STALE_LEAFS))
        self.assertEqual(len(stale), 22)
        self.assertTrue(self.link.last_state_json["comm_lost"])
        # свіжий знімок повертає статус
        self.snap()
        self.link._publish_one()
        self.assertEqual(self.values()["p_kw"].status, "ok")
        self.assertEqual(self.link.last_state_json["online"], 1)

    def test_clock_ahead(self):  # AC-46
        before = fields.Datetime.now()
        self.snap(ts=before + timedelta(seconds=300))
        self.link._publish_one()
        ts = self.readings().mapped("ts")
        self.assertTrue(all(t <= fields.Datetime.now() for t in ts))
        self.assertIn("годинник ретранслятора попереду", self.link.last_publish_error)

    def test_adapter_not_verified_and_isolation(self):  # MG-11
        eq2 = self.env["maintenance.equipment"].create(
            {"name": "Генератор 2", "td_code": "GENSET-2", "td_passport_id": self.passport.id}
        )
        gen2 = self.env["res.partner"].create({"name": "Генератор td_genset 2"})
        link2 = self.env["td.genset3d.link"].create(
            {"equipment_id": eq2.id, "td_genset_ref": "res.partner,%d" % gen2.id, "profile_id": self.profile.id}
        )
        good = self.snap()

        def snapshot(gen):
            if gen == self.td_gen:
                raise NotImplementedError("ADP-03: звірити з td_genset")
            return good

        with mock.patch(TD + ".snapshot", side_effect=snapshot), mute_logger(LINK_LOGGER):
            self.env["td.genset3d.link"]._cron_publish()
        self.assertEqual(self.link.last_publish_error, "NotImplementedError: ADP-03: звірити з td_genset")
        self.assertTrue(link2.last_publish_ts)
        self.assertFalse(link2.last_publish_error)
        self.assertEqual(len(self.readings(link2)), 26)
