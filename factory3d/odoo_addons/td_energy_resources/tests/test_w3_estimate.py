"""W3-A: AC-12…AC-15 — оцінні методи (R-04): `load_share`, `schedule`, `residual`, `gate_loss`."""

from datetime import datetime, timedelta

from odoo.tests import tagged

from ..tools import estimate
from .common import SLOT, T0, TAGS, TestW3Common

S = timedelta(seconds=1)
SCHEDULE = {"from_h": 8, "to_h": 16, "weekdays": [0, 1, 2, 3, 4], "rate": 1.0}


@tagged(*TAGS)
class TestW3Estimate(TestW3Common):
    def _counter_meter(self, code, resource, kind_point="consumer"):
        point = self.point(code, resource, kind_point)
        return self.meter(
            code, point, "counter", qty=self.signal("energy/t3/%s" % code.lower().replace("-", "_"), "counter", "м³")
        )

    def test_load_share(self):  # AC-12
        self.assertAlmostEqual(estimate.load_share(41.0, 67.5, 3.0, 0.75, 0.05), 2.389, places=3)
        self.assertIsNone(estimate.load_share(None, 67.5, 3.0, 0.75, 0.05))
        self.assertEqual(estimate.load_share(60.0, 67.5, 3.0, 0.75, 0.05), 3.0)  # вище run → active = 1
        self.assertEqual(estimate.load_share(2.0, 67.5, 3.0, 0.75, 0.05), 0.0)  # нижче idle → 0
        self.assertAlmostEqual(estimate.load_share(41.0, 67.5, 3.0), 2.389, places=3)  # коефіцієнти за умовчанням
        node = self.env["td.energy.node"].search([("code", "=", "EDGE-1")], limit=1)
        node.write({"p_inst_kw": 67.5, "load_factor": 0.75, "idle_factor": 0.05})
        self.el_interval("PM-EDGE-1", T0, 10.25)  # 41 кВт
        point = self.point("T-EST-AIR", "air", estimate_method="load_share", node_id=node.id, rate_nominal=3.0)
        meter = self.meter("T-EST-AIR", point, "estimate")
        self.build(meter, now=T0 + SLOT)
        row = self.rows(meter)[-1]
        self.assertEqual((row[0], row[6]), (T0, "estimated"))
        self.assertAlmostEqual(row[2], 2.389, places=3)
        self.assertAlmostEqual(row[1], 2.389 * 60 * 0.25, places=2)
        self.assertEqual(self.rows(meter)[-2][6], "missing")  # немає інтервалу вузла — missing

    def test_schedule(self):  # AC-13
        tue = datetime(2026, 10, 13, 9, 30)
        self.assertEqual(estimate.schedule(tue, SCHEDULE), 1.0)
        self.assertEqual(estimate.schedule(datetime(2026, 10, 17, 9, 30), SCHEDULE), 0.0)  # субота
        self.assertEqual(estimate.schedule(tue.replace(hour=16, minute=0), SCHEDULE), 0.0)  # права межа виключається
        self.assertEqual(estimate.schedule(tue.replace(hour=15, minute=45), SCHEDULE), 1.0)
        self.assertEqual(estimate.schedule(tue.replace(hour=7, minute=45), SCHEDULE), 0.0)
        # через `SlotBuilder`: вівторок 13.10, 06:30 UTC = 09:30 Київ → 1,0; 13:30 Київ теж; 16:00 Київ (13:00 UTC) → 0
        point = self.point("T-SCHED", "gas", estimate_method="schedule", estimate_params=SCHEDULE)
        meter = self.meter("T-SCHED", point, "estimate")
        self.build(meter, now=datetime(2026, 10, 13, 13, 15))
        rows = {r[0]: r for r in self.rows(meter)}
        self.assertEqual(rows[datetime(2026, 10, 13, 6, 30)][2], 1.0)
        self.assertEqual(rows[datetime(2026, 10, 13, 6, 30)][6], "estimated")
        self.assertEqual(rows[datetime(2026, 10, 13, 12, 45)][2], 1.0)  # 15:45 Київ
        self.assertEqual(rows[datetime(2026, 10, 13, 13, 0)][2], 0.0)  # 16:00 Київ

    def test_residual(self):  # AC-14
        self.assertAlmostEqual(estimate.residual([2.1], [0.0125, 0.22, 0.3]), 1.5675, places=4)
        self.assertEqual(estimate.residual([0.5], [0.4, 0.3]), 0.0)  # гілки більші за ввід
        self.assertIsNone(estimate.residual([2.1], [0.0125, None]))  # сусід missing → missing
        self.assertIsNone(estimate.residual([], [0.1]))
        self.Point.search([("resource_id.code", "=", "water")]).write({"active": False})  # демо-точки не заважають
        main = self._counter_meter("T-W-MAIN", "water", "source")
        boiler = self._counter_meter("T-W-BOILER", "water")
        canteen = self._counter_meter("T-W-CANTEEN", "water")
        spray = self._counter_meter("T-W-SPRAY", "water")
        for meter, rate in ((main, 2.1), (boiler, 0.0125), (canteen, 0.22), (spray, 0.3)):
            self.res_interval(meter, T0, rate / 4, rate=rate)
        social_point = self.point(
            "T-W-SOCIAL", "water", estimate_method="residual", estimate_params={"from": ["T-W-MAIN"]}
        )
        social = self.meter("T-W-SOCIAL", social_point, "estimate")
        self.build(social, now=T0 + SLOT)
        row = self.rows(social)[-1]
        self.assertEqual((row[0], row[6]), (T0, "estimated"))
        self.assertAlmostEqual(row[2], 1.5675, places=3)
        self.res_interval(canteen, T0 + SLOT, 0.0, quality="missing")  # сусід missing → слот missing
        self.res_interval(main, T0 + SLOT, 0.5)
        self.build(social, now=T0 + 2 * SLOT)
        self.assertEqual([r for r in self.rows(social) if r[0] == T0 + SLOT][0][6], "missing")

    def test_gate_loss(self):  # AC-15
        self.assertAlmostEqual(estimate.gate_loss(0.5, 18.0, 7.0, 3.5), 19.25, places=2)
        self.assertEqual(estimate.gate_loss(0.5, 18.0, 25.0, 3.5), 0.0)  # зовні тепліше — втрат немає
        self.assertIsNone(estimate.gate_loss(None, 18.0, 7.0, 3.5))
        half = estimate.open_fraction([(T0 - 60 * S, 0.0), (T0 + 450 * S, 1.0)], T0, T0 + SLOT)
        self.assertAlmostEqual(half, 0.5, places=3)
        self.assertIsNone(estimate.open_fraction([], T0, T0 + SLOT))
        state = self.signal("energy/t3/gate_state", "state", False)
        t_out = self.signal("energy/t3/outdoor_c", "gauge", "°C")
        self.feed(state, [(T0 - 60 * S, 0.0), (T0 + 450 * S, 1.0)])
        self.feed(t_out, [(T0 - 300 * S, 7.0), (T0 + 600 * S, 7.0)])
        point = self.point(
            "T-DOCK", "heat", state_signal_id=state.id, estimate_method="gate_loss",
            estimate_params={"loss_kw_per_k": 3.5, "t_out_signal": t_out.code},
        )  # fmt: skip
        meter = self.meter("T-DOCK", point, "estimate")
        self.build(meter, now=T0 + SLOT)
        row = [r for r in self.rows(meter) if r[0] == T0][0]
        self.assertAlmostEqual(row[2], 19.25, places=2)
        self.assertEqual(row[6], "estimated")
        self.assertEqual([r for r in self.rows(meter) if r[0] == T0 - 6 * SLOT][0][6], "missing")  # немає показань
