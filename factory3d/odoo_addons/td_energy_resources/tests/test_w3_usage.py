"""W3-A: AC-19 — `td.energy.usage`: потоки, вартість, CO₂, склад view (R-07)."""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import SLOT, T0, TAGS, TestW3Common


@tagged(*TAGS)
class TestW3Usage(TestW3Common):
    def test_usage_flows(self):  # AC-19
        Meter = self.env["td.energy.meter"]
        storage = Meter.search([("role", "=", "storage")], limit=1)
        self.el_interval("PM-Q1", T0, 100.0, kwh_export=20.0, price=8.4)  # import 100, export 20, cost 840
        self.el_interval("PM-QF-1", T0, 90.0)  # load
        self.el_interval("SUN-1", T0, 30.0)  # generation
        self.el_interval("PM-COMPRESSOR", T0, 5.0)  # consumer — у view не входить
        self.el_interval(storage.code, T0, 4.0)  # storage — не входить
        gas_main, gas_boiler = Meter.search([("code", "=", "GM-MAIN")]), Meter.search([("code", "=", "GM-BOILER")])
        self.res_interval(gas_main, T0, 612.0, cost=12117.6)  # supply (точка kind=source)
        self.res_interval(gas_boiler, T0, 41.0, cost=800.0)  # branch
        q1 = Meter.search([("code", "=", "PM-Q1")])
        self.res_interval(q1, T0, 55.0, metric="react")  # у view не входить
        self.env.flush_all()  # view читає таблиці напряму
        usage = self.env["td.energy.usage"].search([("ts_start", "=", T0)])
        self.assertEqual(len(usage), len(set(usage.ids)))  # id унікальні
        by_flow = {u.flow: u for u in usage}
        self.assertEqual(set(by_flow), {"import", "export", "load", "generation", "supply", "branch"})
        self.assertEqual(len(usage), 6)  # consumer, storage, react відсутні
        imp = by_flow["import"]
        self.assertEqual((imp.qty, imp.kwh_eq, imp.cost, imp.resource_id.code), (100.0, 100.0, 840.0, "el"))
        self.assertAlmostEqual(imp.co2_kg, 37.0, places=3)
        self.assertEqual((by_flow["export"].qty, by_flow["export"].cost), (20.0, 0.0))
        self.assertEqual((by_flow["load"].qty, by_flow["load"].cost), (90.0, 756.0))
        self.assertEqual(
            (by_flow["generation"].qty, by_flow["generation"].cost, by_flow["generation"].co2_kg), (30.0, 0.0, 0.0)
        )
        supply = by_flow["supply"]
        self.assertEqual((supply.qty, supply.cost, supply.resource_id.code), (612.0, 12117.6, "gas"))
        self.assertAlmostEqual(supply.co2_kg, 1199.52, places=2)
        self.assertEqual((by_flow["branch"].qty, by_flow["branch"].co2_kg), (41.0, 0.0))
        self.assertEqual(by_flow["supply"].point_id.code, "GAS-MAIN")
        self.assertEqual(by_flow["import"].node_id.code, "Q1")
        # без групи «Вартість» поле cost недоступне
        with self.assertRaises(AccessError):
            self.env["td.energy.usage"].with_user(self.u_view).search([("ts_start", "=", T0)]).mapped("cost")
        self.assertEqual(
            sorted(self.env["td.energy.usage"].with_user(self.u_view).search([("ts_start", "=", T0)]).mapped("flow")),
            sorted(by_flow),
        )

    def test_usage_without_source(self):  # R-07: ресурс без `source`-точки — споживачі рахуються як supply
        self.Point.search([("resource_id.code", "=", "water"), ("kind", "=", "source")]).write({"active": False})
        m = self.env["td.energy.meter"].search([("code", "=", "WM-BOILER")])
        self.res_interval(m, T0 + SLOT, 0.3)
        self.env.flush_all()
        row = self.env["td.energy.usage"].search([("meter_id", "=", m.id)])
        self.assertEqual((row.flow, row.qty), ("supply", 0.3))
