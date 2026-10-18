from datetime import timezone

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")
PARAM_KEYS = [
    "read_enabled",
    "write_enabled",
    "keep_days",
    "keep_hours_days",
    "default_store_period_s",
    "stale_periods",
    "stale_min_s",
    "bus_min_interval_s",
    "realarm_cooldown_s",
    "push_max_readings",
    "push_rate_per_min",
    "meter_lead_pct",
    "default_team_id",
    "drop_level0",
    "level0_migrated",
    "stale_notify_min",
]
PARAM_VALUES = {
    "write_enabled": "False",
    "keep_days": "30",
    "keep_hours_days": "400",
    "default_store_period_s": "300",
    "stale_periods": "3",
    "stale_min_s": "60",
    "bus_min_interval_s": "10",
    "realarm_cooldown_s": "3600",
    "push_max_readings": "2000",
    "push_rate_per_min": "60",
    "meter_lead_pct": "5",
    "drop_level0": "False",
    "stale_notify_min": "0",
}
CRONS = {  # xml-id -> (interval_number, interval_type)
    "cron_td_telemetry_stale": (1, "minutes"),
    "cron_td_telemetry_hour": (10, "minutes"),
    "cron_td_telemetry_rotate": (1, "days"),
    "cron_td_telemetry_commands_gc": (10, "minutes"),
}
SOURCES = {  # Додаток C.1: xml-id -> (code, type, ключові params)
    "source_mqtt_mobile": ("MQTT-MOBILE", "mqtt", {"host": "mosquitto", "port": 1883, "client_id": "f3d-collector"}),
    "source_mb_u70_compressor": ("MB-U70-COMPRESSOR", "modbus_tcp", {"unit": 70, "max_block": 100}),
    "source_mb_u84_io5": ("MB-U84-IO5", "modbus_tcp", {"unit": 84}),
    "source_mb_u90_ai1": ("MB-U90-AI1", "modbus_tcp", {"unit": 90}),
    "source_mb_u96_rtd1": ("MB-U96-RTD1", "modbus_tcp", {"unit": 96}),
    "source_bac_140_boiler": ("BAC-140-BOILER", "bacnet_ip", {"device": 140, "port": 47808, "network": 2}),
    "source_http_push": ("HTTP-PUSH", "http_push", {"routes": ["lpr"]}),
}


@tagged(*TAGS)
class TestData(F3DTelemetryCase):
    def test_params(self):
        """AC-66: 16 параметрів §5.1."""
        icp = self.env["ir.config_parameter"].sudo()
        records = icp.search([("key", "=like", "td.telemetry.%")])
        self.assertEqual(sorted(r.key.rsplit(".", 1)[1] for r in records), sorted(PARAM_KEYS))
        for key, value in PARAM_VALUES.items():
            with self.subTest(key=key):
                self.assertEqual(icp.get_param("td.telemetry." + key), value)
        team_id = icp.get_param("td.telemetry.default_team_id")  # фікстури W0 задають команду (§13.0.1)
        self.assertTrue(team_id.isdigit() and self.env["maintenance.team"].browse(int(team_id)).exists())

    def test_crons(self):
        for xmlid, (number, interval_type) in CRONS.items():
            with self.subTest(cron=xmlid):
                cron = self.env.ref("td_telemetry." + xmlid)
                self.assertEqual((cron.interval_number, cron.interval_type, cron.active), (number, interval_type, True))

    def test_rotate_nextcall_kyiv(self):
        cron = self.env.ref("td_telemetry.cron_td_telemetry_rotate")
        local = cron.nextcall.replace(tzinfo=timezone.utc).astimezone(self.KYIV)
        self.assertEqual(local.strftime("%H:%M"), "02:40")

    def test_sources_data(self):
        collector = self.env.ref("td_telemetry.collector_main")
        self.assertEqual(collector.code, "COL-MAIN")
        for xmlid, (code, source_type, params) in SOURCES.items():
            with self.subTest(source=xmlid):
                source = self.env.ref("td_telemetry." + xmlid)
                self.assertEqual(
                    (source.code, source.type, source.collector_id, source.module),
                    (code, source_type, collector, "telemetry"),
                )
                self.assertEqual((source.read_enabled, source.write_enabled), (True, False))
                for key, value in params.items():
                    self.assertEqual(source.params[key], value, key)


@tagged(*TAGS)
class TestRunMigrationAction(F3DTelemetryCase):
    def test_manager_denied(self):
        """AC-67: права на дію «Повторити міграцію»."""
        with self.assertRaises(AccessError):
            self.env["td.signal"].with_user(self.user_manager).f3d_run_migration()

    def test_admin_notification(self):
        Signal = self.env["td.signal"].with_user(self.user_admin)
        action = Signal.f3d_run_migration()
        self.assertEqual(action["tag"], "display_notification")
        self.assertTrue(action["params"]["sticky"])
        self.assertIn('"state"', action["params"]["message"])
        again = Signal.f3d_run_migration()
        self.assertIn('"signals_catalog": {"created": 0', again["params"]["message"])
        self.assertEqual(self.env.ref("td_telemetry.action_td_run_migration").model_id.model, "td.signal")
