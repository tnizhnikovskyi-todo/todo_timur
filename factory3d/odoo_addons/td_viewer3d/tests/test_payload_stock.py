from odoo.tests import tagged

from .common import F3dViewerBase, F3dViewerCase


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestStockSynthetic(F3dViewerBase):
    """Провайдер stock на власних записах (без демо): R-03, R-04, AC-65."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_plain = cls._make_user("f3d_plain", ["base.group_user", "td_factory3d.group_td_user"])
        wh = cls.env["stock.warehouse"].search([], limit=1)
        cls.loc = cls.env["stock.location"].create({
            "name": "TST stack", "location_id": wh.lot_stock_id.id, "usage": "internal",
            "td_code": "TST-STK-1", "td_loc_kind": "stack", "td_capacity": 60})
        cls.kit = cls.env["stock.location"].create({
            "name": "TST kit", "location_id": wh.lot_stock_id.id, "usage": "internal", "td_code": "TST-KIT-1"})
        cls.product = cls.env["product.product"].create({
            "name": "TST sheet", "default_code": "TST-DSP", "is_storable": True})
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.loc, 15)

    def _data(self):
        return self.payload(self.user_stock_only, sections=["products", "locations"])

    def test_loc_kind_capacity_from_base(self):
        """AC-65: kind/capacity з base, fill перераховується."""
        rec = self._data()["locations"]["TST-STK-1"]
        self.assertEqual((rec["kind"], rec["capacity"]), ("stack", 60))
        self.assertAlmostEqual(rec["fill"], 0.25, places=3)
        self.loc.td_capacity = 80
        rec = self._data()["locations"]["TST-STK-1"]
        self.assertEqual(rec["capacity"], 80)
        self.assertAlmostEqual(rec["fill"], 15 / 80, places=3)

    def test_quants_and_products(self):
        data = self._data()
        rec = data["locations"]["TST-STK-1"]
        self.assertEqual(rec["quants"], [{"product": "TST-DSP", "qty": 15.0}])
        self.assertEqual(rec["complete_name"], self.loc.complete_name)
        self.assertEqual(data["products"]["TST-DSP"]["uom"], self.product.uom_id.name)
        self.assertEqual(data["meta"]["sections"]["locations"], "live")

    def test_empty_location_and_static_fallback(self):
        rec = self._data()["locations"]["TST-KIT-1"]
        self.assertEqual(rec["quants"], [])
        self.assertIsNone(rec["capacity"])
        self.assertIsNone(rec["fill"])

    def test_orderpoint_state(self):
        bin_loc = self.env["stock.location"].create({
            "name": "TST bin", "location_id": self.loc.location_id.id, "usage": "internal",
            "td_code": "TST-BIN-1", "td_loc_kind": "bin"})
        self.env["stock.warehouse.orderpoint"].create({
            "product_id": self.product.id, "location_id": bin_loc.id, "product_min_qty": 10,
            "product_max_qty": 40})
        rec = self._data()["locations"]["TST-BIN-1"]
        self.assertEqual(rec["orderpoint"], {"product": "TST-DSP", "min": 10, "max": 40})
        self.assertEqual((rec["state"], rec["capacity"], rec["fill"]), ("out", 40, 0.0))
        self.env["stock.quant"]._update_available_quantity(self.product, bin_loc, 5)
        self.assertEqual(self._data()["locations"]["TST-BIN-1"]["state"], "low")
        self.env["stock.quant"]._update_available_quantity(self.product, bin_loc, 20)
        self.assertEqual(self._data()["locations"]["TST-BIN-1"]["state"], "ok")

    def test_denied_without_stock_group(self):
        data = self.payload(self.user_plain)
        self.assertEqual(data["meta"]["sections"]["locations"], "denied")
        self.assertFalse(data.get("locations"))

    def test_delta_only_changed_locations(self):
        from odoo.addons.td_viewer3d.tools.payload import DeltaBuilder
        res = DeltaBuilder(self.env(user=self.user_stock_only), since=None,
                           changes={"stock.quant": {"TST-STK-1"}}).build()
        self.assertEqual(set(res["patch"]["locations"]), {"TST-STK-1"})


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestStock(F3dViewerCase):
    """Демо-база: значення як у dist/odoo_demo.json."""

    def _locs(self):
        return self.payload(self.user_f3d)["locations"]

    def test_locations_count_689(self):
        """R-03: усі `internal|transit` локації з `td_code`. Еталонна демо — 689; шаблон на CE кодує ворота
        як `DOCK-*` (аліас `UNLOAD-*`), тож рахуємо очікування з бази, не слабше за еталон."""
        locs = self._locs()
        expected = self.env["stock.location"].search_count([
            ("td_code", "!=", False), ("usage", "in", ("internal", "transit"))])
        self.assertEqual(len(locs), expected)
        self.assertGreaterEqual(len(locs), 689)

    def test_quants_plt_04c(self):
        loc = self._locs()["PLT-04C"]
        self.assertEqual(loc["kind"], "stack")
        self.assertEqual(loc["capacity"], 60)
        self.assertTrue(loc["quants"])
        self.assertTrue(all("lot" in q for q in loc["quants"]))

    def test_fill_state_orderpoint(self):
        loc = self._locs()["FUR-R1-S02-L3"]
        self.assertEqual(loc["state"], "ok")
        self.assertAlmostEqual(loc["fill"], 705 / 833, delta=0.01)
        self.assertEqual(loc["orderpoint"]["min"], 250)

    def test_reserved_for_outgoing(self):
        self.assertTrue(any(q.get("reserved_for") for loc in self._locs().values() for q in loc["quants"]))

    def test_quality_quarantine_qc1(self):
        if "quality.check" not in self.env:
            self.skipTest("quality.check відсутній (Enterprise)")
        self.assertTrue(any(q.get("quality") for loc in self._locs().values() for q in loc["quants"]))

    def test_products_subset(self):
        data = self.payload(self.user_f3d)
        used = {q["product"] for loc in data["locations"].values() for q in loc["quants"]}
        self.assertTrue(used <= set(data["products"]))

    def test_loc_kind_capacity_from_base(self):
        """AC-65 на демо: PLT-04C base 60 -> 80; KIT-01 — зі статики."""
        loc = self.env["stock.location"].search([("td_code", "=", "PLT-04C")])
        loc.td_capacity = 80
        self.assertEqual(self._locs()["PLT-04C"]["capacity"], 80)
        kit = self._locs()["KIT-01"]
        self.assertEqual((kit["kind"], kit["capacity"]), ("kit", None))
