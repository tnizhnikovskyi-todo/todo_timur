"""W3-A: AC-08…AC-11 — інтеграл витрати й лічильник на слот (R-03): формули `tools/integrate` і побудова слотів."""

from datetime import timedelta

from odoo.tests import tagged

from ..tools import integrate
from .common import SLOT, T0, TAGS, TestW3Common

S = timedelta(seconds=1)


def pts(t0, values, step=300):
    return [(t0 + i * step * S, v) for i, v in enumerate(values)]


@tagged(*TAGS)
class TestW3Integrate(TestW3Common):
    def test_flow_trapezoid(self):  # AC-08: газ 40/44/46/46 м³/год → 11,083 м³
        res = integrate.flow_slot([pts(T0, [40, 44, 46, 46])], T0, T0 + SLOT)
        self.assertAlmostEqual(res["qty"], 11.083, places=3)
        self.assertAlmostEqual(res["rate_avg"], 44.333, places=3)
        self.assertEqual((res["coverage"], res["quality"]), (1.0, "measured"))

    def test_flow_coverage(self):  # AC-09
        res = integrate.flow_slot([[(T0, 40.0), (T0 + 300 * S, 44.0), (T0 + 1300 * S, 50.0)]], T0, T0 + SLOT)
        self.assertAlmostEqual(res["coverage"], 1 / 3, places=3)
        self.assertEqual(res["quality"], "interpolated")
        self.assertAlmostEqual(res["qty"], 12600 / 3600 / (1 / 3), places=3)  # інтеграл [0, 300] / покриття
        alone = integrate.flow_slot([[(T0 + 450 * S, 40.0), (T0 + 1500 * S, 40.0)]], T0, T0 + SLOT)
        self.assertEqual((alone["qty"], alone["quality"]), (0.0, "missing"))
        none = integrate.flow_slot([[]], T0, T0 + SLOT)
        self.assertEqual((none["qty"], none["quality"]), (0.0, "missing"))
        low = integrate.flow_slot([[(T0, 40.0), (T0 + 100 * S, 40.0)]], T0, T0 + SLOT, min_coverage=0.3)
        self.assertEqual(low["quality"], "missing")  # покриття 0,11 < 0,3

    def test_flow_air(self):  # AC-09: повітря 9,6/9,8/10,0/9,8 м³/хв → 147,5 норм. м³
        res = integrate.flow_slot([pts(T0, [9.6, 9.8, 10.0, 9.8])], T0, T0 + SLOT, rate_hour_factor=60)
        self.assertAlmostEqual(res["qty"], 147.5, places=3)
        self.assertAlmostEqual(res["rate_avg"], 9.833, places=3)

    def test_counter_reset(self):  # AC-10
        slot = integrate.counter_slot(pts(T0, [100.00, 100.35, 100.70], 900), T0, T0 + SLOT)
        self.assertAlmostEqual(slot["qty"], 0.35, places=3)
        self.assertEqual(slot["quality"], "measured")
        reset = integrate.counter_slot(pts(T0, [100.0, 100.7, 0.10], 450), T0, T0 + SLOT)
        self.assertGreaterEqual(reset["qty"], 0.0)
        self.assertEqual(reset["quality"], "interpolated")
        gap = integrate.counter_slot([(T0, 100.0), (T0 + 1000 * S, 101.0)], T0, T0 + SLOT, gap_max_s=900)
        self.assertEqual(gap["quality"], "interpolated")
        self.assertEqual(integrate.counter_slot([(T0 + 100 * S, 1.0)], T0, T0 + SLOT)["quality"], "missing")

    def test_multisignal(self):  # AC-11: 25 сигналів × 9,1 кВт = 227,5 кВт
        series = [pts(T0, [9.1, 9.1, 9.1, 9.1]) for _ in range(25)]
        res = integrate.flow_slot(series, T0, T0 + SLOT)
        self.assertAlmostEqual(res["rate_avg"], 227.5, places=3)
        self.assertEqual(res["quality"], "measured")
        series[7] = [(T0, 9.1), (T0 + 300 * S, 9.1)]  # один сигнал замовк на 2/3 слота (діра)
        half = integrate.flow_slot(series + [], T0, T0 + SLOT)
        self.assertEqual(half["quality"], "interpolated")
        self.assertAlmostEqual(half["coverage"], 1 / 3, places=3)
        series[7] = []
        self.assertEqual(integrate.flow_slot(series, T0, T0 + SLOT)["quality"], "missing")

    def test_builder_slots(self):  # R-03 через `SlotBuilder`: показання `td.reading` → рядки
        now = T0 + SLOT  # слот T0 — останній з побудованих
        flow = self.signal("energy/t3/int_flow")
        self.feed(flow, pts(T0, [40, 44, 46, 46]))
        total = self.signal("energy/t3/int_total", "counter", "м³")
        self.feed(total, pts(T0, [100.0, 100.35, 100.70], 900))
        m_flow = self.meter("T-INT-F", self.point("T-INT-F", "gas"), "flow_integrate", flow=[flow])
        m_cnt = self.meter("T-INT-C", self.point("T-INT-C", "gas"), "counter", qty=total)
        written = self.build(m_flow | m_cnt, now=now)
        self.assertEqual(written, 2 * 96)  # перший прогін: 24 год
        flow_row = self.rows(m_flow)[-1]
        self.assertEqual(flow_row[0], T0)
        self.assertAlmostEqual(flow_row[1], 11.083, places=3)
        self.assertAlmostEqual(flow_row[2], 44.333, places=3)
        self.assertEqual(flow_row[6], "measured")
        cnt_row = self.rows(m_cnt)[-1]
        self.assertAlmostEqual(cnt_row[1], 0.35, places=3)
        self.assertEqual(self.rows(m_flow)[0][6], "missing")  # доба до першого показання — немає даних
        self.assertEqual(m_flow.res_last_interval_start, T0)

    def test_builder_react(self):  # R-05 п. 4: вводи з `e_react_signal_id` → `metric='react'`
        now = T0 + SLOT
        sig = self.signal("energy/t3/react_total", "counter", "квар·год")
        self.feed(sig, pts(T0, [1000.0, 1100.0, 1200.0], 900))
        incomer = self.env["td.energy.meter"].search([("code", "=", "PM-Q1")])
        incomer.e_react_signal_id = sig
        self.build(incomer, now=now)
        row = self.rows(incomer, "react")[-1]
        self.assertEqual((row[0], round(row[1], 3), row[6]), (T0, 100.0, "measured"))
        self.assertEqual((row[4], row[5]), (0.0, 0.0))  # price = cost = 0
        self.assertEqual(self.rows(incomer, "main"), [])
