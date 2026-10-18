"""AC-30…AC-32: погодинний баланс обліку на реальній схемі (дані post_init_hook), інтервали — синтетичні."""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import TAGS, F3DEnergyCase
from .test_counter import EnergyMixin


@tagged(*TAGS)
class TestBalance(EnergyMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Balance = cls.env["td.energy.balance"]
        cls.Event = cls.env["td.energy.event"]
        cls.Node = cls.env["td.energy.node"]
        cls.meters = cls.env["td.energy.meter"].search([("active", "=", True), ("e_import_signal_id", "!=", False)])
        cls.hour = (fields.Datetime.now() - timedelta(days=3)).replace(hour=8, minute=0, second=0, microsecond=0)

    def fill(self, hour, kwh=None, export=None, missing=()):
        """Усі лічильники години: 4 слоти, уся енергія — у першому; решта лічильників — нулі."""
        kwh, export = kwh or {}, export or {}
        vals = []
        for meter in self.meters:
            for k in range(4):
                first = k == 0
                vals.append(
                    {
                        "meter_id": meter.id,
                        "ts_start": hour + timedelta(minutes=15 * k),
                        "ts_end": hour + timedelta(minutes=15 * (k + 1)),
                        "day": hour.date(),
                        "hour_local": (hour.hour + 3) % 24,
                        "kwh": kwh.get(meter.code, 0.0) if first else 0.0,
                        "kwh_export": export.get(meter.code, 0.0) if first else 0.0,
                        "quality": "missing" if (meter.code in missing and k < 2) else "measured",
                        "built_at": fields.Datetime.now(),
                    }
                )
        self.env["td.energy.interval"].create(vals)

    def consumer(self, node_code):
        found = (
            self.Node.search([("code", "=", node_code)])
            ._f3d_descendant_meters()
            .filtered(lambda m: m.role == "consumer")
        )
        self.assertTrue(found, node_code)
        return found.sorted("code")[0]

    def check(self, hour, node_code):
        return self.Balance._f3d_balance_hour(hour, hour + timedelta(hours=2)).filtered(
            lambda r: r.node_id.code == node_code
        )

    def test_balance_states(self):  # AC-30
        saw, comp = self.consumer("QF-1"), self.consumer("QF-C1")
        self.fill(
            self.hour,
            {
                "PM-Q1": 334.7, "PM-QF-3": 70.1, "PM-QF-2": 80.5, "PM-QF-C1": 1.5, "PM-QF-1": 110.5,
                "PM-QF-4": 26.4, "PM-QF-C2": 158.0, "SUN-1": 468.0, "TEDOM-1": 400.0, "LUNA-1": 200.0,
                saw.code: 106.9, comp.code: 0.2,
            },
            {"PM-Q2": 376.7},
        )  # fmt: skip
        # Q1: фідери секції 1 = 70,1 + 80,5 + 1,5 — для чистоти перевіряємо Q2 і лінії
        q2 = self.check(self.hour, "Q2")
        self.assertAlmostEqual(q2.measured_kwh, -376.7, places=3)
        self.assertAlmostEqual(q2.expected_kwh, (110.5 + 26.4 + 158.0) - 468.0 - 400.0 + 200.0, places=3)
        qf1 = self.check(self.hour, "QF-1")
        self.assertEqual(qf1.state, "deviation")
        self.assertAlmostEqual(qf1.diff_kwh, 3.6, places=3)
        self.assertAlmostEqual(qf1.diff_pct, 3.26, places=2)
        event = self.Event.search([("kind", "=", "balance"), ("code", "=", "QF-1")])
        self.assertEqual(len(event), 1)
        self.assertTrue(
            event.text.startswith("Небаланс обліку BW-1: 3,26 % (110,5 проти 106,9 кВт·год за "), event.text
        )
        self.assertEqual(event.level, "warn")
        qfc1 = self.check(self.hour, "QF-C1")
        self.assertEqual(qfc1.state, "ok")
        self.assertAlmostEqual(qfc1.diff_kwh, 1.3, places=3)
        # сигнал небалансу лінії записано (годиною-кінцем)
        sig = self.env["td.signal"].search([("code", "=", "energy/lines/BW-1/imbalance_pct")])
        self.assertAlmostEqual(sig.last_value, 3.26, places=2)
        self.assertEqual(sig.last_ts, self.hour + timedelta(hours=1))

    def test_balance_sections_and_tolerance(self):  # AC-30 (Q1, Q2, 109,0 / 106,9)
        saw = self.consumer("QF-1")
        h2 = self.hour + timedelta(hours=1)
        self.fill(self.hour, {"PM-Q1": 334.7, "PM-QF-3": 70.1, "PM-QF-2": 80.5, "PM-QF-C1": 184.1})
        q1 = self.check(self.hour, "Q1")
        self.assertEqual(q1.state, "ok")
        self.assertAlmostEqual(q1.diff_kwh, 0.0, places=6)
        self.fill(
            h2,
            {"PM-QF-1": 106.9, "PM-QF-4": 26.4, "PM-QF-C2": 158.0, "SUN-1": 468.0, "TEDOM-1": 400.0,
             "LUNA-1": 200.0, saw.code: 106.9},
            {"PM-Q2": 376.7},
        )  # fmt: skip
        q2 = self.check(h2, "Q2")
        self.assertEqual(q2.state, "ok")
        self.assertAlmostEqual(q2.expected_kwh, -376.7, places=3)
        self.assertAlmostEqual(q2.diff_kwh, 0.0, places=6)
        h3 = self.hour + timedelta(hours=2)
        self.fill(h3, {"PM-QF-1": 109.0, saw.code: 106.9})
        qf1 = self.check(h3, "QF-1")
        self.assertEqual(qf1.state, "ok")
        self.assertAlmostEqual(qf1.diff_pct, 1.93, places=2)

    def test_balance_skipped(self):  # AC-31
        saw = self.consumer("QF-1")
        self.fill(self.hour, {"PM-QF-1": 110.5, saw.code: 106.9}, missing=(saw.code,))
        qf1 = self.check(self.hour, "QF-1")
        self.assertEqual(qf1.state, "skipped")
        self.assertIn(saw.code, qf1.reason)
        self.assertTrue(qf1.reason.startswith("немає даних"))
        sig = self.env["td.signal"].search([("code", "=", "energy/lines/BW-1/imbalance_pct")])
        self.assertFalse(sig.last_ts)
        self.assertFalse(self.Event.search([("kind", "=", "balance"), ("code", "=", "QF-1")]))

    def test_imbalance_alarm_two_hours(self):  # AC-32
        saw = self.consumer("QF-1")
        self.bind_equipment("energy/lines/BW-1/imbalance_pct", "QF-1")
        h2 = self.hour + timedelta(hours=1)
        self.fill(self.hour, {"PM-QF-1": 110.5, saw.code: 106.9})
        self.fill(h2, {"PM-QF-1": 105.71, saw.code: 100.0})
        self.check(self.hour, "QF-1")
        sig = self.env["td.signal"].search([("code", "=", "energy/lines/BW-1/imbalance_pct")])
        self.assertEqual(sig.status, "ok")  # min_duration_s = 3600: утримання від першого показання
        self.assertFalse(self.env["maintenance.request"].search([("name", "=like", "Небаланс обліку QF-1:%")]))
        self.check(h2, "QF-1")
        self.assertAlmostEqual(sig.last_value, 5.4, places=2)
        self.assertEqual(sig.status, "alarm")
        requests = self.env["maintenance.request"].search([("name", "=like", "Небаланс обліку QF-1: 5,4%")])
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests.equipment_id.td_code, "QF-1")
