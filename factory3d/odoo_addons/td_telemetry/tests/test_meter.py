from datetime import timedelta

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d_telemetry")
NOW = "2026-10-14 06:00:00"


class MeterCase(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()
        cls.eq_comp.write(
            {
                "f3d_meter_signal_id": cls.sig_hours.id,
                "f3d_meter_interval": 2000.0,
                "f3d_meter_last_value": 16000.0,
                "f3d_meter_lead_pct": 5.0,
            }
        )
        cls.eq_fl2.write(
            {"f3d_meter_signal_id": cls.sig_fl2_hours.id, "f3d_meter_interval": 1000.0, "f3d_meter_last_value": 3000.0}
        )

    def setUp(self):
        super().setUp()
        frozen = freeze_time(NOW)
        frozen.start()
        self.addCleanup(frozen.stop)

    def requests(self, eq):
        return self.env["maintenance.request"].search([("equipment_id", "=", eq.id), ("f3d_origin", "=", "meter")])


@tagged(*TAGS)
class TestMeterCreate(MeterCase):
    def test_no_request_before_lead(self):
        self.push([self.rd(self.sig_hours, 17846.6)])
        self.assertEqual(self.eq_comp.f3d_meter_next_value, 18000)
        self.assertAlmostEqual(self.eq_comp.f3d_meter_remaining, 153.4, places=1)
        self.assertFalse(self.requests(self.eq_comp))

    def test_request_at_lead(self):
        self.push([self.rd(self.sig_hours, 17900.2)])
        req = self.requests(self.eq_comp)
        self.assertEqual(len(req), 1)
        self.assertEqual(req.name, "ТО за лічильником: COMPRESSOR-T — 18 000 год (зараз 17 900)")
        self.assertEqual(req.maintenance_type, "preventive")
        self.assertEqual(req.priority, "1")
        self.assertEqual(req.f3d_origin, "meter")
        self.assertEqual(req.f3d_signal_id, self.sig_hours)
        self.assertAlmostEqual(req.f3d_value, 17900.2)
        self.assertEqual(req.f3d_threshold, 18000)
        self.assertEqual(req.maintenance_team_id, self.team_mech)
        self.assertEqual(self.eq_comp.f3d_meter_request_id, req)

    def test_no_duplicate(self):
        self.push([self.rd(self.sig_hours, 17900.2)])
        self.push([self.rd(self.sig_hours, 17901.0, at=60)])
        self.assertEqual(len(self.requests(self.eq_comp)), 1)

    def test_overdue_priority(self):
        self.push([self.rd(self.sig_fl2_hours, 4000.5)])
        self.assertEqual(self.requests(self.eq_fl2).priority, "3")


@tagged(*TAGS)
class TestMeterClose(MeterCase):
    def test_close_updates_last_value(self):
        self.push([self.rd(self.sig_hours, 17900.2)])
        req = self.requests(self.eq_comp)
        self.set_sql(self.sig_hours, last_value=17905.0)
        self.close(req)
        eq = self.eq_comp
        self.assertEqual(eq.f3d_meter_last_value, 17905.0)
        self.assertEqual(eq.f3d_meter_last_date, fields.Date.today())
        self.assertFalse(eq.f3d_meter_request_id)
        self.assertEqual(eq.f3d_meter_next_value, 19905.0)
        self.assertIn("ТО за лічильником виконано при 17 905", " ".join(eq.message_ids.mapped("body")))


@tagged(*TAGS)
class TestMeterRules(MeterCase):
    def test_constraints(self):
        with self.assertRaisesRegex(ValidationError, "Задайте інтервал"):
            self.eq_flc1.write({"f3d_meter_signal_id": self.sig_hours.id})
        with self.assertRaisesRegex(ValidationError, "Задайте інтервал"):
            self.eq_comp.write({"f3d_meter_interval": 0})
        with self.assertRaisesRegex(ValidationError, "Лічильник належить іншому обладнанню"):
            self.eq_other.write({"f3d_meter_signal_id": self.sig_fl2_hours.id, "f3d_meter_interval": 10})

    def _hours(self, delta_total):
        now = fields.Datetime.now()
        Hour = self.env["f3d.reading.hour"]
        for i in range(7):
            Hour.create(
                {"signal_id": self.sig_hours.id, "hour": now - timedelta(days=i + 1), "delta": delta_total / 7.0}
            )

    def test_schedule_with_rate(self):
        self._hours(59.5)
        self.push([self.rd(self.sig_hours, 17900.2)])
        req = self.requests(self.eq_comp)
        days = (req.schedule_date - fields.Datetime.now()).total_seconds() / 86400
        self.assertAlmostEqual(days, 11.74, delta=0.05)

    def test_schedule_without_rate(self):
        self.push([self.rd(self.sig_hours, 17900.2)])
        req = self.requests(self.eq_comp)
        self.assertLessEqual(abs((req.schedule_date - fields.Datetime.now()).total_seconds()), 60)

    def test_remaining(self):
        self.push([self.rd(self.sig_fl2_hours, 3216.5)])
        self.assertAlmostEqual(self.eq_fl2.f3d_meter_remaining, 783.5, places=1)
