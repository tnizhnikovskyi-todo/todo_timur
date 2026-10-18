import json
from datetime import timedelta
from unittest import mock

from odoo.addons.td_telemetry import hooks
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


# Додаток C.2: каталог додає пороги батареї (warn 25 / alarm 15), яких на рівні 0 не було (T-1)
BATTERY_ROW = {"code": "equipment/FL-T/battery", "warn_low": "25", "alarm_low": "15", "new": "0"}


class Level0Mixin:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._level0_models()  # моделі x_f3d_*: один раз на клас (реєстр не відкочується разом із транзакцією тесту)

    def setUp(self):
        super().setUp()
        self.l0 = self.make_level0()
        self.env["td.source"].create(
            {
                "code": "MB-T-U70",
                "name": "MB-T-U70",
                "type": "modbus_tcp",
                "collector_id": self.env["td.collector"].create({"code": "COL-T", "name": "T"}).id,
                "params": {"host": "iot-sim", "port": 502, "unit": 70},
            }
        )

    def migrate(self, rows=None):
        with self.with_catalog_rows(rows or [STATE_ROW]):
            return hooks.run_migration(self.env)

    def sig(self, code):
        return self.env["td.signal"].with_context(active_test=False).search([("code", "=", code)])


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
            json.loads(self.env["ir.config_parameter"].sudo().get_param("td.telemetry.level0_migrated"))[
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
        self.assertEqual(self.env.ref("td_telemetry.sig_ventilation_units_rv_05_t_filter_dp_pa"), rv)
        readings = self.env["td.reading"].search(
            [("signal_id", "in", self.sig("equipment/FL-T/battery").ids + rv.ids)]
        )
        for reading in readings:
            self.assertEqual((reading.src, reading.quality), ("sim_data", "good"))
        x_read = self.l0["readings"][0]
        first = self.env["td.reading"].search([("signal_id", "=", rv.id), ("ts", "=", self.T0)])
        self.assertEqual(first.received_at, x_read.create_date)
        for req in (self.l0["req_a"], self.l0["req_b"]):
            self.assertEqual((req.td_origin, bool(req.td_signal_id)), ("threshold", True))
        self.assertFalse(self.env.ref("td_iot_sim.cron_iot_sim").active)
        self.assertFalse(self.env.ref("td_iot_sim.menu_iot_root").active)
        self.assertFalse(self.env.ref("td_iot_sim.view_equipment_form_signals").active)
        self.env.cr.execute("SELECT count(*) FROM x_f3d_signal WHERE x_active")
        self.assertEqual(self.env.cr.fetchone()[0], 0)
        self.assertGreater(self.env["td.reading.hour"].search_count([("signal_id", "=", rv.id)]), 0)


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestRerunPartial(Level0Mixin, F3DTelemetryCase):
    def test_rerun_idempotent(self):
        """AC-54."""
        self.migrate()
        signals = self.env["td.signal"].search_count([])
        readings = self.env["td.reading"].search_count([])
        report = self.migrate()
        self.assertEqual(report["created"], 0)
        self.assertEqual(report["signals_catalog"]["created"], 0)
        self.assertEqual(self.env["td.signal"].search_count([]), signals)
        self.assertEqual(self.env["td.reading"].search_count([]), readings)
        self.assertEqual((report["mismatches"], report["state"]), ([], "done"))

    def test_partial_keeps_level0(self):
        real = hooks.readings_level0

        def lossy(env):
            res = real(env)
            env.cr.execute("DELETE FROM td_reading WHERE id = (SELECT min(id) FROM td_reading)")
            env["td.reading"].invalidate_model()
            return res

        with mock.patch.object(hooks, "readings_level0", side_effect=lossy):
            report = self.migrate()
        self.assertEqual(report["state"], "partial")
        self.assertTrue(any(m.startswith("readings:") for m in report["mismatches"]), report["mismatches"])
        self.assertTrue(self.env.ref("td_iot_sim.cron_iot_sim").active)
        self.env.cr.execute("SELECT count(*) FROM x_f3d_signal WHERE x_active")
        self.assertEqual(self.env.cr.fetchone()[0], 7)
        self.assertNotIn("requests_linked", report)
        self.assertEqual(
            json.loads(self.env["ir.config_parameter"].sudo().get_param("td.telemetry.level0_migrated"))[
                "state"
            ],
            "partial",
        )


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestCatalogThresholds(Level0Mixin, F3DTelemetryCase):
    """T-1: пороги каталогу дають статус, якого на рівні 0 не було; крок 8 це не розбіжність."""

    def test_status_from_catalog_thresholds_is_not_mismatch(self):
        self.l0["signals"]["bat"].x_value = 22.9  # нижче warn 25, вище alarm 15; рівень 0: «норма», порога немає
        report = self.migrate([STATE_ROW, BATTERY_ROW])
        battery = self.sig("equipment/FL-T/battery")
        self.assertEqual((battery.status, battery.last_value), ("warn", 22.9))
        self.assertEqual(report["mismatches"], [])
        self.assertEqual(report["state"], "done")
        self.assertEqual(report["status_notes_total"], 1)
        self.assertIn("equipment/FL-T/battery", report["status_notes"][0])
        # кроки після звірки виконані
        self.assertEqual(report["requests_linked"], 2)
        self.assertFalse(self.env.ref("td_iot_sim.cron_iot_sim").active)
        self.env.cr.execute("SELECT count(*) FROM x_f3d_signal WHERE x_active")
        self.assertEqual(self.env.cr.fetchone()[0], 0)

    def test_stale_status_is_not_mismatch(self):
        """T-1b: статус stale (немає свіжих даних) залежить від часу, а не від значення — не розбіжність."""
        real = hooks.hours_rebuild

        def go_stale(env):
            res = real(env)
            env["td.signal"].search([("origin", "=", "sim_data")]).with_context(mail_notrack=True).write(
                {"status": "stale"}
            )
            return res

        with mock.patch.object(hooks, "hours_rebuild", side_effect=go_stale):
            report = self.migrate([STATE_ROW, BATTERY_ROW])
        self.assertEqual((report["mismatches"], report["state"]), ([], "done"))
        self.assertGreaterEqual(report["status_notes_total"], 1)
        self.assertTrue(all("stale" in note for note in report["status_notes"]), report["status_notes"])
        self.assertEqual(report["requests_linked"], 2)
        self.assertFalse(self.env.ref("td_iot_sim.cron_iot_sim").active)

    def test_alarm_threshold_from_catalog_is_not_mismatch(self):
        self.l0["signals"]["bat"].x_value = 10.0  # нижче alarm 15: статус «тривога» лише за порогом каталогу
        report = self.migrate([STATE_ROW, BATTERY_ROW])
        self.assertEqual(self.sig("equipment/FL-T/battery").status, "alarm")
        self.assertEqual((report["mismatches"], report["state"]), ([], "done"))

    def test_level0_alarm_missing_in_f3d_is_still_mismatch(self):
        dust = self.l0["signals"]["dust"]
        dust.x_state = "тривога"  # рівень 0 у тривозі (89.3 при порозі 90 — стан від гістерезису)
        report = self.migrate([STATE_ROW, {"code": "fire/groups/FA-T/dust", "alarm_high": "100", "new": "0"}])
        self.assertEqual(report["state"], "partial")
        self.assertTrue(
            any(m.startswith("fire/groups/FA-T/dust: status") for m in report["mismatches"]), report["mismatches"]
        )
        self.assertTrue(self.env.ref("td_iot_sim.cron_iot_sim").active)
        self.assertNotIn("requests_linked", report)


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestRerunLiveLevel0(Level0Mixin, F3DTelemetryCase):
    """T-1: повторний запуск при живому рівні 0 звіряє знімок міграції, а не значення, що змінились потім."""

    def live_tick(self, minutes=60):
        """Рівень 0 «працює»: нові значення й `x_updated`, свіжі показання, а старі показання він чистить."""
        sigs = self.l0["signals"]
        when = self.T0 + timedelta(minutes=minutes)
        for key, value in (("bat", 21.6), ("rv", 330.1), ("press", 7.2), ("pnow", 13.4)):
            sigs[key].write({"x_value": value, "x_updated": when})
        sigs["bat"].x_state = "норма"
        new = self.env["x_f3d_reading"].create(
            {"x_name": "live", "x_signal_id": sigs["bat"].id, "x_value": 21.6, "x_unit": "%", "x_time": when}
        )
        self.l0["readings"][0].unlink()  # ротація iot_sim: рядок є в td.reading, а в x_f3d_reading його вже нема
        return when, new

    def test_rerun_after_live_changes_completes(self):
        report = self.migrate([STATE_ROW, BATTERY_ROW])
        self.assertEqual(report["state"], "done")
        readings = self.env["td.reading"].search_count([("src", "=", "sim_data")])
        when, _new = self.live_tick()
        self.env.cr.execute("UPDATE x_f3d_signal SET x_active = true")  # як на живій базі: рівень 0 ще не вимкнено
        self.env["x_f3d_signal"].invalidate_model()
        report = self.migrate([STATE_ROW, BATTERY_ROW])
        self.assertEqual(report["mismatches"], [])
        self.assertEqual(report["state"], "done")
        self.assertEqual(report["created"], 0)
        battery = self.sig("equipment/FL-T/battery")
        self.assertEqual((battery.last_value, battery.last_ts, battery.status), (21.6, when, "warn"))
        self.assertEqual(self.sig("energy/consumers/SAW-T/p_now").last_value, 13.4)
        self.assertEqual(self.env["td.reading"].search_count([("src", "=", "sim_data")]), readings + 1)
        self.assertFalse(self.env.ref("td_iot_sim.cron_iot_sim").active)

    def test_rerun_does_not_roll_back_newer_telemetry(self):
        self.migrate([STATE_ROW, BATTERY_ROW])
        when, _new = self.live_tick()
        pnow = self.sig("energy/consumers/SAW-T/p_now")
        newer = when + timedelta(minutes=30)
        pnow.write({"last_value": 99.0, "last_ts": newer})  # колектор уже прислав свіжіше значення
        report = self.migrate([STATE_ROW, BATTERY_ROW])
        self.assertEqual((report["mismatches"], report["state"]), ([], "done"))
        self.assertEqual((pnow.last_value, pnow.last_ts), (99.0, newer))

    def test_missing_reading_still_reported_on_rerun(self):
        self.migrate([STATE_ROW, BATTERY_ROW])
        self.env.cr.execute("DELETE FROM td_reading WHERE id = (SELECT min(id) FROM td_reading)")
        self.env["td.reading"].invalidate_model()
        with mock.patch.object(hooks, "readings_level0", return_value={"max_id": 10**9}):
            report = self.migrate([STATE_ROW, BATTERY_ROW])
        self.assertEqual(report["state"], "partial")
        self.assertTrue(any(m.startswith("readings:") for m in report["mismatches"]), report["mismatches"])


class DropMixin(Level0Mixin):
    def setUp(self):
        super().setUp()
        self.env["ir.config_parameter"].sudo().set_param("td.telemetry.drop_level0", "True")


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
            self.assertFalse(self.env.ref("td_iot_sim." + name, raise_if_not_found=False), name)


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestNoDropOnMismatch(DropMixin, F3DTelemetryCase):
    def test_no_drop_on_mismatch(self):
        real = hooks.readings_level0

        def lossy(env):
            res = real(env)
            env.cr.execute("DELETE FROM td_reading WHERE id = (SELECT min(id) FROM td_reading)")
            return res

        with mock.patch.object(hooks, "readings_level0", side_effect=lossy):
            report = self.migrate()
        self.assertEqual(report["state"], "partial")
        self.assertIn("x_f3d_signal", self.env)
        self.assertTrue(self.env.ref("td_iot_sim.view_signal_list", raise_if_not_found=False))


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestCleanDb(F3DTelemetryCase):
    def test_clean_install_state(self):
        """AC-56: результат post_init_hook на чистій базі (без рівня 0 й обладнання макета)."""
        state = json.loads(
            self.env["ir.config_parameter"].sudo().get_param("td.telemetry.level0_migrated") or "{}"
        )
        if state.get("state") != "skipped":
            self.skipTest("база не чиста: міграція рівня 0 виконувалась")
        Signal = self.env["td.signal"].with_context(active_test=False)
        self.assertEqual(Signal.search_count([("origin", "=", "catalog")]), 29)
        self.assertFalse(Signal.search([("origin", "=", "catalog"), ("equipment_id", "!=", False)]))
        collector = self.env.ref("td_telemetry.collector_main")
        self.assertEqual(collector.code, "COL-MAIN")
        self.assertFalse(collector.sudo().token_hash)
        sources = self.env["td.source"].search([("collector_id", "=", collector.id)])
        self.assertEqual(len(sources), 7)
        self.assertEqual(state["signals_catalog"], {"created": 29, "bound": 28, "bind_missing": 27, "no_equipment": 29})
        self.assertEqual(state["meters"], 0)


@tagged("post_install", "-at_install", "f3d", "f3d_telemetry")
class TestUninstall(Level0Mixin, F3DTelemetryCase):
    def test_uninstall_restores_level0(self):
        """AC-57."""
        self.migrate()
        self.env.cr.execute("SELECT to_regclass('td_collector_push')")
        self.assertTrue(self.env.cr.fetchone()[0], "таблиця журналу пакетів колектора є до видалення")
        with self.assertLogs("odoo.addons.td_telemetry.hooks", "WARNING") as logs:
            hooks.uninstall_hook(self.env)
        self.env.cr.execute("SELECT to_regclass('td_collector_push')")
        self.assertFalse(self.env.cr.fetchone()[0], "uninstall_hook видаляє td_collector_push")
        self.assertTrue(any("рівень 0 вимкнено; увімкніть вручну або через пульт" in line for line in logs.output))
        self.env.cr.execute("SELECT count(*) FROM x_f3d_signal WHERE NOT x_active")
        self.assertEqual(self.env.cr.fetchone()[0], 0)
        self.assertTrue(self.env.ref("td_iot_sim.menu_iot_root").active)
        self.assertTrue(self.env.ref("td_iot_sim.view_equipment_form_signals").active)
        self.assertFalse(self.env.ref("td_iot_sim.cron_iot_sim").active)
        self.assertFalse(self.env["ir.config_parameter"].sudo().search([("key", "=like", "td.telemetry.%")]))
