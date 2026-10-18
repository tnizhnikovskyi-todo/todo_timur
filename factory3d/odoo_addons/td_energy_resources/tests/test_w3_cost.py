"""W3-A: AC-16, AC-17, AC-18, AC-20, AC-51, AC-60 (ТП-02, ТП-03) — ціна й вартість, крон, ротація, реактивна енергія,
налаштування, продуктивність."""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..tools import build
from .common import SLOT, T0, TAGS, TestW3Common

S = timedelta(seconds=1)
LOGGER = "odoo.addons.td_energy_resources.tools.build"


def pts(t0, values, step=300):
    return [(t0 + i * step * S, v) for i, v in enumerate(values)]


@tagged(*TAGS)
class TestW3Cost(TestW3Common):
    def _counter(self, code, resource, readings, step=900, **point_vals):
        sig = self.signal("energy/t3/%s" % code.lower().replace("-", "_"), "counter", "м³")
        self.feed(sig, pts(T0, readings, step))
        return self.meter(code, self.point(code, resource, **point_vals), "counter", qty=sig)

    def test_cost_by_resource(self):  # AC-16
        now = T0 + SLOT
        gas = self._counter("T-C-GAS", "gas", [0.0, 612.0])
        water = self._counter("T-C-WATER", "water", [10.0, 14.2])
        flow = self.signal("energy/t3/heat_kw", "gauge", "кВт")
        self.feed(flow, pts(T0, [100.0] * 4))
        heat = self.meter("T-C-HEAT", self.point("T-C-HEAT", "heat", "source"), "flow_integrate", flow=[flow])
        self.build(gas | water | heat, now=now)
        g = self.rows(gas)[-1]  # ts, qty, rate_avg, kwh_eq, price, cost, quality
        self.assertEqual((g[0], g[1], g[4], g[5]), (T0, 612.0, 19.8, 12117.6))
        self.assertAlmostEqual(g[3], 612 * 10.5, places=3)
        w = self.rows(water)[-1]
        self.assertEqual((w[1], w[4], w[5]), (4.2, 60.0, 252.0))
        h = self.rows(heat)[-1]
        price_heat = 19.8 / (10.5 * 0.91)
        self.assertAlmostEqual(h[1], 25.0, places=3)
        self.assertAlmostEqual(h[4], round(price_heat, 4), places=4)
        self.assertEqual(h[5], round(25.0 * price_heat, 2))
        self.assertEqual(h[3], 25.0)  # kwh_eq тепла = qty
        self.Price.search([]).unlink()  # немає ціни: price = cost = 0
        self.build(gas, now=now, force_from=T0, force_to=T0 + SLOT)
        g2 = self.rows(gas)[-1]
        self.assertEqual((g2[4], g2[5]), (0.0, 0.0))

    def test_cost_air_from_electricity(self):  # AC-16, R-02 п. 4: 4 слоти × 160,5 кВт·год × 8,40 = 5 392,80
        compressor = self.env["td.energy.node"].search([("code", "=", "COMPRESSOR")], limit=1)
        for k in range(4):
            self.el_interval("PM-COMPRESSOR", T0 + k * SLOT, 160.5, price=8.4)
        flow = self.signal("energy/t3/air_flow", "gauge", "м³/хв")
        self.feed(flow, pts(T0, [9.8] * 13))
        point = self.point("T-AIR-MAIN", "air", "source", cost_node_id=compressor.id)
        meter = self.meter("T-AIR-MAIN", point, "flow_integrate", flow=[flow])
        self.build(meter, now=T0 + 4 * SLOT)
        rows = [r for r in self.rows(meter) if T0 <= r[0] < T0 + 4 * SLOT]
        self.assertEqual(len(rows), 4)
        self.assertAlmostEqual(sum(r[5] for r in rows), 5392.8, places=2)
        self.assertAlmostEqual(rows[0][2], 9.8, places=3)  # м³/хв
        self.assertAlmostEqual(rows[0][1], 9.8 * 15, places=2)  # норм. м³ за слот
        self.assertEqual(rows[0][3], 0.0)  # kwh_eq повітря = 0
        self.assertAlmostEqual(rows[0][4], rows[0][5] / rows[0][1], places=3)

    def test_cron_build(self):  # AC-17
        cron = self.ResInterval.with_context(f3d_now=T0 + 2 * SLOT)  # слоти до 06:15 включно
        sig = self.signal("energy/t3/cron_total", "counter", "м³")
        self.feed(sig, pts(T0 - 900 * S, [0.0, 10.0, 20.0], 900))
        meter = self.meter("T-CRON", self.point("T-CRON", "gas"), "counter", qty=sig)
        backfill = self.res_interval(meter, T0 - SLOT, 99.0, is_backfill=True)
        cron._cron_build()
        count = len(self.rows(meter))
        self.assertEqual(count, 96)  # перший прогін — 24 год (один слот — синтетичний)
        last = self.rows(meter)[-1]
        self.assertEqual((last[0], last[6]), (T0 + SLOT, "missing"))  # немає показання на правій межі слота
        cron._cron_build()  # другий прогін: нових рядків немає, два останні слоти перераховані
        self.assertEqual(len(self.rows(meter)), count)
        self.env.cr.execute("SELECT qty, is_backfill FROM td_energy_res_interval WHERE id = %s", (backfill.id,))
        self.assertEqual(self.env.cr.fetchone(), (99.0, True))  # синтетичний рядок не перезаписаний
        self.feed(sig, [(T0 + 1800 * S, 30.0)])  # пізнє показання уточнює останній слот
        cron._cron_build()
        self.assertEqual(len(self.rows(meter)), count)
        last = self.rows(meter)[-1]
        self.assertEqual((last[0], last[1], last[6]), (T0 + SLOT, 10.0, "measured"))
        self.assertEqual(meter.res_last_interval_start, T0 + SLOT)

    def test_cron_stop_and_isolation(self):  # AC-17
        cron = self.ResInterval.with_context(f3d_now=T0 + 2 * SLOT)
        sig = self.signal("energy/t3/cron2_total", "counter", "м³")
        self.feed(sig, pts(T0, [0.0, 10.0], 900))
        a = self.meter("T-CRON-A", self.point("T-CRON-A", "gas"), "counter", qty=sig)
        sig_b = self.signal("energy/t3/cron2b_total", "counter", "м³")
        self.feed(sig_b, pts(T0, [0.0, 10.0], 900))
        b = self.meter("T-CRON-B", self.point("T-CRON-B", "gas"), "counter", qty=sig_b)
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("td.energy.read_enabled", "False")
        self.assertEqual(cron._cron_build(), 0)
        self.assertEqual((len(self.rows(a)), len(self.rows(b))), (0, 0))
        icp.set_param("td.energy.read_enabled", "True")
        original = build.SlotBuilder.build_meter

        def broken(builder, meter, *args, **kw):
            if meter.code == "T-CRON-A":
                raise RuntimeError("збій лічильника")
            return original(builder, meter, *args, **kw)

        with patch.object(build.SlotBuilder, "build_meter", autospec=True, side_effect=broken), mute_logger(LOGGER):
            cron._cron_build()
        self.assertEqual(len(self.rows(a)), 0)  # збій ізольовано savepoint
        self.assertEqual(len(self.rows(b)), 96)

    def test_rotate(self):  # AC-18
        meter = self._counter("T-ROT", "gas", [0.0, 1.0])
        old = self.now - timedelta(days=401)
        for k in range(3):
            self.res_interval(meter, old + k * SLOT, 1.0, is_backfill=bool(k % 2))
        fresh = self.res_interval(meter, self.now - SLOT, 2.0)
        self.assertEqual(self.ResInterval._cron_rotate(), 3)
        self.assertEqual([r[0] for r in self.rows(meter)], [fresh.ts_start])

    def test_react_stats(self):  # AC-20, R-06
        stats = build.react_stats(2514.0, 6284.0, 0.30, 0.24)
        self.assertAlmostEqual(stats["tg"], 0.40, places=2)
        self.assertAlmostEqual(stats["cos"], 0.928, places=3)
        self.assertTrue(stats["risk"])
        self.assertAlmostEqual(stats["excess"], 628.8, places=1)
        self.assertAlmostEqual(stats["penalty"], 150.9, places=1)
        self.assertEqual(build.react_stats(2514.0, 6284.0, 0.0, 0.0)["penalty"], 0.0)  # ліміт не заданий
        self.assertFalse(build.react_stats(2514.0, 6284.0, 0.0, 0.0)["risk"])
        self.assertIsNone(build.react_stats(10.0, 0.0)["tg"])
        tariff = self.env["td.energy.tariff"].search([], limit=1)
        tariff.write({"tg_phi_limit": 0.30, "react_rate": 0.24})
        self.assertAlmostEqual(tariff._td_react_penalty(stats["excess"]), 150.9, places=1)

    def test_settings(self):  # AC-51
        Settings = self.env["res.config.settings"]
        settings = Settings.create({"td_energy_resources_night_to_h": 7.0, "td_energy_resources_gap_max_s": 600})
        settings.set_values()
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(float(icp.get_param("td.energy_resources.night_to_h")), 7.0)
        self.assertEqual(settings.td_energy_resources_no_price_count, 0)
        for field, value in (
            ("td_energy_resources_night_from_h", 24.0),
            ("td_energy_resources_gap_max_s", 100),
            ("td_energy_resources_min_coverage", 0.0),
            ("td_energy_resources_min_coverage", 1.5),
        ):
            with self.assertRaises(ValidationError, msg=field):
                Settings.create({field: value}).set_values()
        self.Price.search([]).unlink()
        self.assertEqual(Settings.create({}).td_energy_resources_no_price_count, 2)

    def test_performance(self):  # AC-60: ТП-02, ТП-03
        meters = self.env["td.energy.meter"]
        for k in range(24):
            sig = self.signal("energy/t3/perf_%02d" % k, "counter", "м³")
            self.feed(sig, pts(T0 - 3600 * S, [float(i) for i in range(0, 30)], 900))
            meters |= self.meter("T-PERF-%02d" % k, self.point("T-PERF-%02d" % k, "gas"), "counter", qty=sig)
        started = time.monotonic()
        rows = self.build(meters, now=T0 + 2 * SLOT)
        self.assertEqual(rows, 24 * 96)
        self.assertLess(time.monotonic() - started, 5.0)
        started = time.monotonic()
        day = datetime(2026, 10, 17).date()
        self.assertEqual(self.env["td.energy.usage"].search_count([("day", "=", day)]) > 0, True)
        self.assertLess(time.monotonic() - started, 0.2)
