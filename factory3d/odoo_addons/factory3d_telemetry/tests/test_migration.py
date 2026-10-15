import json
from unittest import mock

from odoo.addons.factory3d_telemetry import hooks
from odoo.tests import tagged

from .common import F3DTelemetryCase

STATE_ROW = {
    "code": "equipment/FL-T/state",
    "name": "FL-T: стан",
    "quantity": "Стан",
    "kind": "state",
    "equipment": "FL-C1-T",
    "source": "MB-T-U70",
    "address": '{"fc": 3, "addr": 3010, "type": "u16"}',
    "period_s": "5",
    "store_period_s": "300",
    "decimals": "0",
    "states": '["idle", "busy", "charging"]',
    "alarm_states": '["fault"]',
    "alarm_title": "",
    "new": "1",
}


class Level0Mixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._level0_models()  # моделі x_f3d_*: один раз на клас (реєстр не відкочується разом із транзакцією тесту)

    def setUp(self):
        super().setUp()
        self.l0 = self.make_level0()
        self.env["f3d.source"].create(
            {
                "code": "MB-T-U70",
                "name": "MB-T-U70",
                "type": "modbus_tcp",
                "collector_id": self.env["f3d.collector"].create({"code": "COL-T", "name": "T"}).id,
                "params": {"host": "iot-sim", "port": 502, "unit": 70},
            }
        )

    def migrate(self):
        with self.with_catalog_rows([STATE_ROW]):
            return hooks.run_migration(self.env)

    def sig(self, code):
        return self.env["f3d.signal"].with_context(active_test=False).search([("code", "=", code)])


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestLevel0(Level0Mixin, F3DTelemetryCase):
    def test_full_migration(self):
        """AC-53."""
        report = self.migrate()
        self.assertEqual(report["signals_migrated"], 7)
        self.assertEqual(report["readings_migrated"], 30)
        self.assertEqual(report["skipped_null_ts"], 1)
        self.assertEqual(report["requests_linked"], 2)
        self.assertEqual(report["mismatches"], [])
        self.assertEqual(report["state"], "done")
        self.assertEqual(report["by_module"], {"bms": 1, "fire_safety": 1, "telemetry": 3, "energy": 2})
        self.assertEqual(
            json.loads(self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.level0_migrated"))[
                "state"
            ],
            "done",
        )
        rv = self.sig("ventilation/units/RV-05-T/filter_dp_pa")
        self.assertEqual(
            (rv.module, rv.kind, rv.alarm_high, rv.alarm_high_on, rv.hysteresis, rv.decimals),
            ("bms", "gauge", 250, True, 5, 0),
        )
        self.assertEqual(rv.alarm_title, "Заміна фільтрів: перепад тиску {value} {unit} при нормі до {threshold}")
        self.assertEqual((rv.status, rv.last_value, rv.origin, rv.sim_mode), ("alarm", 320.594, "sim_data", "drift"))
        self.assertEqual(rv.maintenance_request_id, self.l0["req_a"])
        self.assertEqual(rv.equipment_id, self.eq_rv)
        self.assertEqual(self.sig("fire/groups/FA-T/dust").hysteresis, 1.8)
        hours = self.sig("equipment/FL-T/hours")
        self.assertEqual((hours.kind, hours.decimals, hours.module), ("counter", 1, "telemetry"))
        press = self.sig("equipment/COMPRESSOR-T/pressure_bar")
        self.assertEqual((press.alarm_low, press.alarm_low_on, press.decimals), (6.0, True, 2))
        kwh = self.sig("energy/consumers/SAW-T/kwh_shift")
        self.assertEqual((kwh.module, kwh.kind), ("energy", "counter"))
        self.assertEqual(kwh.derived_from_id, self.sig("energy/consumers/SAW-T/p_now"))
        state = self.sig("equipment/FL-T/state")
        self.assertEqual((state.last_text, state.origin, state.source_id.code), ("charging", "catalog", "MB-T-U70"))
        self.assertEqual(state.equipment_id, self.eq_flc1)
        self.assertEqual(self.env.ref("factory3d_telemetry.sig_ventilation_units_rv_05_t_filter_dp_pa"), rv)
        readings = self.env["f3d.reading"].search(
            [("signal_id", "in", self.sig("equipment/FL-T/battery").ids + rv.ids)]
        )
        for reading in readings:
            self.assertEqual((reading.src, reading.quality), ("sim_data", "good"))
        x_read = self.l0["readings"][0]
        first = self.env["f3d.reading"].search([("signal_id", "=", rv.id), ("ts", "=", self.T0)])
        self.assertEqual(first.received_at, x_read.create_date)
        for req in (self.l0["req_a"], self.l0["req_b"]):
            self.assertEqual((req.f3d_origin, bool(req.f3d_signal_id)), ("threshold", True))
        self.assertFalse(self.env.ref("factory3d_iot_sim.cron_iot_sim").active)
        self.assertFalse(self.env.ref("factory3d_iot_sim.menu_iot_root").active)
        self.assertFalse(self.env.ref("factory3d_iot_sim.view_equipment_form_signals").active)
        self.env.cr.execute("SELECT count(*) FROM x_f3d_signal WHERE x_active")
        self.assertEqual(self.env.cr.fetchone()[0], 0)
        self.assertGreater(self.env["f3d.reading.hour"].search_count([("signal_id", "=", rv.id)]), 0)


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestRerunPartial(Level0Mixin, F3DTelemetryCase):
    def test_rerun_idempotent(self):
        """AC-54."""
        self.migrate()
        signals = self.env["f3d.signal"].search_count([])
        readings = self.env["f3d.reading"].search_count([])
        report = self.migrate()
        self.assertEqual(report["created"], 0)
        self.assertEqual(report["signals_catalog"]["created"], 0)
        self.assertEqual(self.env["f3d.signal"].search_count([]), signals)
        self.assertEqual(self.env["f3d.reading"].search_count([]), readings)
        self.assertEqual((report["mismatches"], report["state"]), ([], "done"))

    def test_partial_keeps_level0(self):
        real = hooks.readings_level0

        def lossy(env):
            res = real(env)
            env.cr.execute("DELETE FROM f3d_reading WHERE id = (SELECT min(id) FROM f3d_reading)")
            env["f3d.reading"].invalidate_model()
            return res

        with mock.patch.object(hooks, "readings_level0", side_effect=lossy):
            report = self.migrate()
        self.assertEqual(report["state"], "partial")
        self.assertTrue(any(m.startswith("readings:") for m in report["mismatches"]), report["mismatches"])
        self.assertTrue(self.env.ref("factory3d_iot_sim.cron_iot_sim").active)
        self.env.cr.execute("SELECT count(*) FROM x_f3d_signal WHERE x_active")
        self.assertEqual(self.env.cr.fetchone()[0], 7)
        self.assertNotIn("requests_linked", report)
        self.assertEqual(
            json.loads(self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.level0_migrated"))[
                "state"
            ],
            "partial",
        )


class DropMixin(Level0Mixin):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("factory3d.telemetry.drop_level0", "True")


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestDrop(DropMixin, F3DTelemetryCase):
    def test_drop_level0(self):
        """AC-55."""
        self.migrate()
        self.assertNotIn("x_f3d_signal", self.env)
        self.assertNotIn("x_f3d_reading", self.env)
        self.assertFalse(
            self.env["ir.model.fields"].search_count(
                [("model", "=", "maintenance.equipment"), ("name", "=", "x_f3d_signal_ids")]
            )
        )
        for name in hooks.LEVEL0_VIEWS:
            self.assertFalse(self.env.ref("factory3d_iot_sim." + name, raise_if_not_found=False), name)


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestNoDropOnMismatch(DropMixin, F3DTelemetryCase):
    def test_no_drop_on_mismatch(self):
        real = hooks.readings_level0

        def lossy(env):
            res = real(env)
            env.cr.execute("DELETE FROM f3d_reading WHERE id = (SELECT min(id) FROM f3d_reading)")
            return res

        with mock.patch.object(hooks, "readings_level0", side_effect=lossy):
            report = self.migrate()
        self.assertEqual(report["state"], "partial")
        self.assertIn("x_f3d_signal", self.env)
        self.assertTrue(self.env.ref("factory3d_iot_sim.view_signal_list", raise_if_not_found=False))


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestCleanDb(F3DTelemetryCase):
    def test_clean_install_state(self):
        """AC-56: результат post_init_hook на чистій базі (без рівня 0 й обладнання макета)."""
        state = json.loads(
            self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.level0_migrated") or "{}"
        )
        if state.get("state") != "skipped":
            self.skipTest("база не чиста: міграція рівня 0 виконувалась")
        Signal = self.env["f3d.signal"].with_context(active_test=False)
        self.assertEqual(Signal.search_count([("origin", "=", "catalog")]), 29)
        self.assertFalse(Signal.search([("origin", "=", "catalog"), ("equipment_id", "!=", False)]))
        collector = self.env.ref("factory3d_telemetry.collector_main")
        self.assertEqual(collector.code, "COL-MAIN")
        self.assertFalse(collector.sudo().token_hash)
        sources = self.env["f3d.source"].search([("collector_id", "=", collector.id)])
        self.assertEqual(len(sources), 7)
        self.assertEqual(state["signals_catalog"], {"created": 29, "bound": 28, "bind_missing": 27, "no_equipment": 29})
        self.assertEqual(state["meters"], 0)


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestUninstall(Level0Mixin, F3DTelemetryCase):
    def test_uninstall_restores_level0(self):
        """AC-57."""
        self.migrate()
        with self.assertLogs("odoo.addons.factory3d_telemetry.hooks", "WARNING") as logs:
            hooks.uninstall_hook(self.env)
        self.assertTrue(any("рівень 0 вимкнено; увімкніть вручну або через пульт" in line for line in logs.output))
        self.env.cr.execute("SELECT count(*) FROM x_f3d_signal WHERE NOT x_active")
        self.assertEqual(self.env.cr.fetchone()[0], 0)
        self.assertTrue(self.env.ref("factory3d_iot_sim.menu_iot_root").active)
        self.assertTrue(self.env.ref("factory3d_iot_sim.view_equipment_form_signals").active)
        self.assertFalse(self.env.ref("factory3d_iot_sim.cron_iot_sim").active)
        self.assertFalse(self.env["ir.config_parameter"].sudo().search([("key", "=like", "factory3d.telemetry.%")]))
