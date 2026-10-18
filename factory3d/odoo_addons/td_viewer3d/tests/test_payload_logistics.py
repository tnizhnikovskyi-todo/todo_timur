from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from odoo.addons.td_viewer3d.tools import payload as payload_tools

from .common import F3dViewerBase, F3dViewerCase


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestLogisticsSynthetic(F3dViewerBase):
    """Провайдер logistics на власних записах: R-05, R-09; AC-41."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_plain = cls._make_user("f3d_plain", ["base.group_user", "td_factory3d.group_td_user"])
        env = cls.env
        wh = env["stock.warehouse"].search([], limit=1)
        cls.wh = wh
        cls.dock9 = env["stock.location"].create({
            "name": "TST dock 9", "location_id": wh.lot_stock_id.id, "usage": "internal", "td_code": "DOCK-W9",
            "td_kind": "dock", "td_x": 0, "td_y": 5,
            "td_alias": "UNLOAD-9", "td_side": "west", "td_dock_no": 9})
        cls.dock8 = env["stock.location"].create({
            "name": "TST dock 8", "location_id": wh.lot_stock_id.id, "usage": "internal", "td_code": "DOCK-W8",
            "td_kind": "dock", "td_x": 0, "td_y": 15,
            "td_side": "west", "td_dock_no": 8})
        cls.product = env["product.product"].create({"name": "TST item", "default_code": "TST-ITM",
                                                     "is_storable": True})
        cls.supplier = env["res.partner"].create({"name": "TST supplier"})

    def _picking(self, dest, **kw):
        vals = {"picking_type_id": self.wh.in_type_id.id, "partner_id": self.supplier.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id, "location_dest_id": dest.id,
                "scheduled_date": fields.Datetime.now(), "origin": "P-TST",
                "move_ids": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 10,
                                     "location_id": self.env.ref("stock.stock_location_suppliers").id,
                                     "location_dest_id": dest.id})]}
        vals.update(kw)
        p = self.env["stock.picking"].create(vals)
        p.action_confirm()
        return p

    def _data(self, **kw):
        return self.payload(self.user_stock_only, **kw)

    def _find(self, data, name):
        return next(p for p in data["pickings"] if p["name"] == name)

    def test_dock_from_location(self):
        """AC-41: без батча dock — з локації призначення (аліас UNLOAD-k -> DOCK-Wk), truck null."""
        p = self._picking(self.dock9)
        rec = self._find(self._data(), p.name)
        self.assertEqual(rec["dock"], "DOCK-W9")
        self.assertIsNone(rec["truck"])
        self.assertEqual(rec["type"], "incoming")
        self.assertEqual(rec["state"], "assigned")

    def test_dock_from_batch(self):
        """AC-41: dock з батча, truck з td_code (не з td_truck)."""
        p = self._picking(self.wh.lot_stock_id)
        batch = self.env["stock.picking.batch"].create({
            "picking_type_id": self.wh.in_type_id.id, "dock_id": self.dock8.id, "td_code": "TRUCK-IN-9",
            "td_truck": "Фура постачальника плит", "picking_ids": [(4, p.id)]})
        data = self._data()
        rec = self._find(data, p.name)
        self.assertEqual(rec["dock"], "DOCK-W8")
        self.assertEqual(rec["truck"], "TRUCK-IN-9")
        self.assertEqual(data["docks"]["DOCK-W8"], p.name)
        self.assertNotIn("vehicle", rec)
        self.assertTrue(batch)

    def test_progress_lines(self):
        p = self._picking(self.dock9)
        p.move_ids.quantity = 4
        p.move_ids.picked = True
        rec = self._find(self._data(), p.name)
        self.assertEqual(rec["lines"], [{"product": "TST-ITM", "qty": 10.0, "qty_done": 4.0}])
        self.assertEqual(rec["progress"], 0.4)
        self.assertEqual(rec["partner"], "TST supplier")
        self.assertEqual(rec["origin"], "P-TST")

    def test_other_internal_types_skipped(self):
        p = self._picking(self.dock9, picking_type_id=self.wh.int_type_id.id,
                          location_id=self.wh.lot_stock_id.id)
        self.assertFalse([x for x in self._data()["pickings"] if x["name"] == p.name])

    def test_sale_purchase_optional(self):
        """Моделі немає або доступу немає -> [] і sections missing/denied."""
        orig = payload_tools.access_ok

        def fake(env, model):
            return False if model in ("sale.order", "purchase.order") else orig(env, model)
        with patch.object(payload_tools, "access_ok", side_effect=fake):
            data = self._data()
        self.assertEqual(data["sale_orders"], [])
        self.assertEqual(data["purchase_orders"], [])
        self.assertIn(data["meta"]["sections"]["sale_orders"], ("missing", "denied"))

    def test_denied_without_stock_group(self):
        data = self.payload(self.user_plain)
        self.assertEqual(data["meta"]["sections"]["pickings"], "denied")


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestLogistics(F3dViewerCase):
    """Демо-база."""

    def _data(self):
        return self.payload(self.user_f3d)

    def test_dock_from_batch(self):
        """AC-41 (WH/IN/00128)."""
        rec = next(p for p in self._data()["pickings"] if p["name"] == "WH/IN/00128")
        self.assertEqual((rec["dock"], rec["truck"]), ("DOCK-W1", "TRUCK-IN-1"))

    def test_dock_from_location(self):
        """AC-41 (WH/IN/00131)."""
        rec = next(p for p in self._data()["pickings"] if p["name"] == "WH/IN/00131")
        self.assertEqual(rec["dock"], "DOCK-W2")
        self.assertIsNone(rec["truck"])

    def test_types_mapping(self):
        types = {}
        for p in self._data()["pickings"]:
            types[p["type"]] = types.get(p["type"], 0) + 1
        self.assertEqual(set(types), {"incoming", "outgoing", "putaway", "replenish", "pick_components",
                                      "store_finished"})
        self.assertEqual(types["incoming"], 13)
        self.assertEqual(types["pick_components"], 12)

    def test_progress_lines(self):
        for p in self._data()["pickings"]:
            self.assertTrue(0 <= p["progress"] <= 1)

    def test_docks_dict_14(self):
        docks = self._data()["docks"]
        self.assertEqual(len(docks), 14)
        self.assertEqual(docks["DOCK-W1"], "WH/IN/00128")

    def test_note_waiting(self):
        notes = [p.get("note") for p in self._data()["pickings"] if p["type"] == "outgoing" and p["state"] == "waiting"]
        self.assertTrue(all(n == "Чекає завершення МО" for n in notes))
