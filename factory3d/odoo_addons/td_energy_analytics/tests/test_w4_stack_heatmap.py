"""W4-A: стовпці по ділянках й теплокарта (AC-33, AC-34)."""

from datetime import timedelta

from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common


@tagged(*TAGS)
class TestW4StackHeatmap(TestW4Common):
    def _nodes_fixture(self):
        """30 діб: CUT 3000/добу у піковий день, EDGE 2500, HVAC 2000 (разом 7 500); решта діб — менше."""
        self._node("LP-1").area_id = False
        window = self._days(TODAY - timedelta(days=29), 30)
        for i, day in enumerate(window):
            k = 1.0 if i == 4 else 0.5
            self._daily(day, qty=7600.0 * k)
            self._daily(day, scope="node", node="SAW-1", qty=3000.0 * k)
            self._daily(day, scope="node", node="EDGE-1", qty=2500.0 * k)
            self._daily(day, scope="node", node="RV-ALL", qty=2000.0 * k)
            if i % 2 == 0:
                self._daily(day, scope="node", node="LP-1", qty=10.0)
        return window

    def test_ac33_stack_month(self):
        window = self._nodes_fixture()
        stack = self.Api.with_user(self.u_view).get_stack("m")
        self.assertEqual(stack["bar_unit"], "day")
        self.assertEqual(stack["unit"], "кВт·год за день")
        codes = [a["code"] for a in stack["areas"]]
        self.assertEqual(codes[:8], ["CUT", "EDGE", "DRILL", "FACADE", "ASSY", "AIR_DUST", "HVAC", "LIGHT_OFFICE"])
        self.assertEqual(codes[8], "NONE", "сірий сегмент «Без ділянки» при залишку")
        self.assertEqual(stack["areas"][8]["name"], "Без ділянки")
        self.assertEqual(len(stack["bars"]), 30)
        peak = stack["bars"][4]
        self.assertEqual(peak["key"], window[4].isoformat())
        self.assertEqual((peak["values"]["CUT"], peak["values"]["EDGE"], peak["values"]["HVAC"]), (3000, 2500, 2000))
        self.assertEqual(peak["values"]["DRILL"], 0)
        self.assertEqual(peak["total"], 7500 + peak["values"]["NONE"])
        self.assertEqual(sum(peak["values"].values()), peak["total"])
        # шкала: 7 510 → y_max = round(1,08 · 7510) = 8 111; ticks — треті
        self.assertEqual(stack["y_max"], round(1.08 * 7510))
        self.assertEqual(stack["ticks"], [round(stack["y_max"] / 3), round(2 * stack["y_max"] / 3), stack["y_max"]])
        # зі стовпцем 7 500 рівно: y_max = 8 100, ticks 2 700 / 5 400 / 8 100
        self.env.cr.execute("DELETE FROM td_energy_daily WHERE node_id = %s", (self._node("LP-1").id,))
        self.Daily.invalidate_model()
        stack = self.Api.get_stack("m")
        self.assertNotIn("NONE", [a["code"] for a in stack["areas"]])
        self.assertEqual((stack["y_max"], stack["ticks"]), (8100, [2700, 5400, 8100]))
        self.assertEqual([b["label"] for b in stack["bars"][:6]], ["18", "", "", "", "", "23"])

    def test_ac33_units_and_gap(self):
        self._nodes_fixture()
        self.assertEqual(self.Api.get_stack("w")["bar_unit"], "day")
        q, y = self.Api.get_stack("q"), self.Api.get_stack("y")
        self.assertEqual((q["bar_unit"], len(q["bars"]), q["unit"]), ("week", 13, "кВт·год за тиждень"))
        self.assertEqual((y["bar_unit"], len(y["bars"]), y["unit"]), ("month", 12, "кВт·год за місяць"))
        self.assertEqual(
            sum(b["total"] for b in y["bars"][-2:]), sum(b["total"] for b in self.Api.get_stack("m")["bars"])
        )
        gap = self.Api._td_stack_gap_pct("m")
        self.assertLessEqual(gap, 3.0)
        self.assertGreaterEqual(gap, 0.0)

    def test_ac33_empty(self):
        stack = self.Api.get_stack("m")
        self.assertEqual((len(stack["bars"]), stack["y_max"]), (30, 3))
        self.assertTrue(all(b["total"] == 0 for b in stack["bars"]))

    def test_ac34_heatmap(self):
        mondays = [TODAY - timedelta(days=k) for k in (26, 19, 12, 5)]  # 21.09, 28.09, 05.10, 12.10
        self.assertTrue(all(d.weekday() == 0 for d in mondays))
        for day, total in zip(mondays, (400.0, 410.0, 390.0, 400.0), strict=True):
            self._fill("PM-QF-1", day, total / 4, slots=range(48, 52))  # 12:00–12:59
        tuesday = TODAY - timedelta(days=25)
        self._fill("PM-QF-1", tuesday, 53.0, slots=range(12, 16))  # 03:00: 212 кВт
        self._fill("PM-QF-2", mondays[0], 5.0, slots=range(48, 52), quality="missing")  # не враховується
        heat = self.Api.with_user(self.u_view).get_heatmap("m")
        self.assertEqual(heat["days"], ["пн", "вт", "ср", "чт", "пт", "сб", "нд"])
        self.assertEqual((len(heat["cells"]), {len(r) for r in heat["cells"]}), (7, {24}))
        self.assertAlmostEqual(heat["cells"][0][12], 400.0)
        self.assertAlmostEqual(heat["cells"][1][3], 212.0)
        self.assertIsNone(heat["cells"][2][12], "порожня клітинка")
        self.assertEqual((heat["max_ref"], heat["levels"], heat["base_load_kw"]), (400, 5, 210))

    def test_ac34_empty_and_period_window(self):
        heat = self.Api.get_heatmap("w")
        self.assertTrue(all(v is None for row in heat["cells"] for v in row))
        self.assertEqual((heat["max_ref"], heat["base_load_kw"]), (50, None))
        old = TODAY - timedelta(days=40)  # поза вікном m
        self._fill("PM-QF-1", old, 25.0, slots=[10])
        self.assertTrue(all(v is None for row in self.Api.get_heatmap("m")["cells"] for v in row))
        self.assertTrue(any(v is not None for row in self.Api.get_heatmap("y")["cells"] for v in row))
