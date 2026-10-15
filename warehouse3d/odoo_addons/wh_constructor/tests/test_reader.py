from odoo import Command, release
from odoo.tests import HttpCase, tagged

from .common import G_VIEW, make_user

API = "/wh_constructor/api/read"


@tagged("post_install", "-at_install")
class TestWhConstructorReader(HttpCase):
    """Чтение данных склада (W-11): демо-данные — 2 склада, по 10 локаций, остатки, категория хранения, правило размещения, min/max."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Location, Quant = env["stock.location"], env["stock.quant"]
        cls.wh1 = env["stock.warehouse"].create({"name": "Reader склад 1", "code": "RD1"})
        cls.wh2 = env["stock.warehouse"].create({"name": "Reader склад 2", "code": "RD2"})
        vals = {"type": "consu"}
        if "is_storable" in env["product.product"]._fields:
            vals["is_storable"] = True
        cls.p1 = env["product.product"].create({"name": "Плита тест", "default_code": "RD-P1", **vals})
        cls.p2 = env["product.product"].create({"name": "Фурнітура тест", "default_code": "RD-P2", **vals})
        cls.p3 = env["product.product"].create({"name": "Без коду", **vals})

        def shelves(wh, n, parent=None, prefix="S"):
            parent = parent or wh.lot_stock_id
            return [Location.create({"name": f"{prefix}{i:02d}", "location_id": parent.id, "usage": "internal",
                                     "barcode": f"{wh.code}-{prefix}{i:02d}"}) for i in range(1, n + 1)]

        zone = Location.create({"name": "Зона A", "location_id": cls.wh1.lot_stock_id.id, "usage": "internal"})
        cls.l1 = shelves(cls.wh1, 4, zone, "A") + shelves(cls.wh1, 5, None, "B") + [zone]  # 10 локаций склада 1
        cls.l2 = shelves(cls.wh2, 10)
        cls.zone = zone
        if "posx" in Location._fields:  # только Odoo 18
            cls.l1[0].write({"posx": 3, "posy": 2, "posz": 1})
        lot = env["stock.lot"].create({"name": "RD-LOT-1", "product_id": cls.p1.id, "company_id": env.company.id})
        Quant._update_available_quantity(cls.p1, cls.l1[0], 12.0, lot_id=lot)
        Quant._update_available_quantity(cls.p2, cls.l1[0], 5.0)
        Quant._update_available_quantity(cls.p2, cls.l1[4], 7.0)
        Quant._update_available_quantity(cls.p3, cls.l2[0], 3.0)
        cls.l1[0].quant_ids.filtered(lambda q: q.product_id == cls.p2).reserved_quantity = 2.0
        pt = env["stock.package.type"].create({"name": "Піддон тест"})
        cls.cat = env["stock.storage.category"].create({"name": "Категорія тест", "max_weight": 100.0, "capacity_ids": [
            Command.create({"product_id": cls.p1.id, "quantity": 50.0}), Command.create({"package_type_id": pt.id, "quantity": 4.0})]})
        cls.l1[0].storage_category_id = cls.cat
        cls.rule = env["stock.putaway.rule"].create({"product_id": cls.p1.id, "location_in_id": cls.wh1.lot_stock_id.id,
                                                    "location_out_id": cls.l1[0].id, "storage_category_id": cls.cat.id})
        cls.op = env["stock.warehouse.orderpoint"].create({"product_id": cls.p2.id, "location_id": cls.l1[0].id, "warehouse_id": cls.wh1.id,
                                                          "product_min_qty": 2.0, "product_max_qty": 10.0})
        # чужая компания: свой склад и остаток
        cls.other = env["res.company"].create({"name": "Чужа компанія тест"})
        cls.wh_other = env["stock.warehouse"].search([("company_id", "=", cls.other.id)], limit=1)
        cls.foreign_loc = Location.create({"name": "F01", "location_id": cls.wh_other.lot_stock_id.id, "usage": "internal", "company_id": cls.other.id})
        Quant._update_available_quantity(cls.p1.with_company(cls.other), cls.foreign_loc, 9.0)
        cls.viewer = make_user(env, "wh_rd_viewer", G_VIEW)
        cls.plain = make_user(env, "wh_rd_plain")
        cls.multi = make_user(env, "wh_rd_multi", G_VIEW)
        cls.multi.write({"company_ids": [Command.link(cls.other.id)]})

    def rpc(self, user, route, **params):
        self.authenticate(user.login, f"{user.login}-pass-1")
        return self.make_jsonrpc_request(f"{API}{route}", params)

    def locations(self, wh, **kw):
        return self.rpc(self.viewer, "/locations", warehouse_id=wh.id, **kw)

    # ------------------------------------------------------------ склады
    def test_warehouses(self):
        res = self.rpc(self.viewer, "/warehouses")
        self.assertEqual(res["status"], "ok")
        by_id = {w["id"]: w for w in res["warehouses"]}
        self.assertIn(self.wh1.id, by_id)
        self.assertIn(self.wh2.id, by_id)
        w1 = by_id[self.wh1.id]
        self.assertEqual((w1["code"], w1["name"], w1["company_id"], w1["view_location_id"]),
                         ("RD1", "Reader склад 1", self.env.company.id, self.wh1.view_location_id.id))
        self.assertEqual(w1["places"], 11)  # Stock + зона + 4 + 5 полок
        self.assertEqual(by_id[self.wh2.id]["places"], 11)  # Stock + 10 полок
        self.assertNotIn(self.wh_other.id, by_id)
        self.assertEqual(res["version"]["major"], release.version_info[0])
        self.assertTrue(res["now"])

    def test_foreign_company_hidden(self):
        self.assertEqual(self.locations(self.wh_other)["status"], "error")
        for route in ("/quants", "/storage_categories", "/putaway_rules", "/orderpoints"):
            self.assertEqual(self.rpc(self.viewer, route, warehouse_id=self.wh_other.id)["status"], "error", route)

    def test_multi_company_user_sees_all_own_companies(self):
        ids = {w["id"] for w in self.rpc(self.multi, "/warehouses")["warehouses"]}
        self.assertTrue({self.wh1.id, self.wh_other.id} <= ids)
        res = self.rpc(self.multi, "/quants", warehouse_id=self.wh_other.id)
        self.assertEqual([(q["product_id"], q["quantity"]) for q in res["quants"]], [(self.p1.id, 9.0)])

    # ------------------------------------------------------------ локации
    def test_locations(self):
        res = self.locations(self.wh1)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["total"], 12)  # view-корень, Stock, зона, 4 + 5 полок
        self.assertEqual(len(res["locations"]), 12)
        rows = {r["id"]: r for r in res["locations"]}
        view = rows[self.wh1.view_location_id.id]
        self.assertEqual((view["usage"], view["complete_name"], view["location_id"]), ("view", "RD1", self.wh1.view_location_id.location_id.id or None))
        a1 = rows[self.l1[0].id]
        self.assertEqual((a1["name"], a1["complete_name"], a1["usage"], a1["barcode"], a1["location_id"], a1["storage_category_id"]),
                         ("A01", "RD1/Stock/Зона A/A01", "internal", "RD1-A01", self.zone.id, self.cat.id))
        self.assertTrue(rows[self.wh1.lot_stock_id.id]["replenish_location"])  # место пополнения — склад Stock, не его подчинённые
        self.assertFalse(a1["replenish_location"])
        self.assertIsNone(rows[self.l1[2].id]["storage_category_id"])
        self.assertIn("removal_strategy_id", a1)
        # поля, существующих только в одной версии: отдаются лишь там, где они есть
        fields_ = self.env["stock.location"]._fields
        for f in ("posx", "posy", "posz", "scrap_location"):
            self.assertEqual(f in a1, f in fields_, f)
        if "posx" in fields_:
            self.assertEqual((a1["posx"], a1["posy"], a1["posz"]), (3, 2, 1))
        self.assertFalse({r["id"] for r in res["locations"]} & {r.id for r in self.l2})  # чужие локации склада 2 не попадают
        self.assertEqual(self.locations(self.wh2)["total"], 12)  # view-корень, Stock, 10 полок

    def test_locations_paging(self):
        got, offset, pages = [], 0, 0
        while offset is not None:
            res = self.locations(self.wh1, offset=offset, limit=5)
            self.assertEqual(res["total"], 12)
            self.assertLessEqual(len(res["locations"]), 5)
            got += [r["id"] for r in res["locations"]]
            offset, pages = res["next"], pages + 1
        self.assertEqual(pages, 3)
        self.assertEqual(len(got), 12)
        self.assertEqual(len(set(got)), 12)
        self.assertEqual(sorted(got), sorted(r["id"] for r in self.locations(self.wh1)["locations"]))
        self.assertEqual(self.locations(self.wh1, offset=100, limit=5)["locations"], [])

    # ------------------------------------------------------------ остатки
    def test_quants(self):
        res = self.rpc(self.viewer, "/quants", warehouse_id=self.wh1.id)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["total"], 3)
        rows = {(q["location_id"], q["product_id"]): q for q in res["quants"]}
        q = rows[(self.l1[0].id, self.p1.id)]
        self.assertEqual((q["quantity"], q["reserved_quantity"], q["lot"]), (12.0, 0.0, "RD-LOT-1"))
        q = rows[(self.l1[0].id, self.p2.id)]
        self.assertEqual((q["quantity"], q["reserved_quantity"], q["lot"]), (5.0, 2.0, None))
        self.assertEqual(rows[(self.l1[4].id, self.p2.id)]["quantity"], 7.0)
        prod = res["products"][str(self.p1.id)]
        self.assertEqual((prod["default_code"], prod["name"]), ("RD-P1", "Плита тест"))
        self.assertTrue(prod["uom"])
        # склад 2: остаток другого товара без кода
        res2 = self.rpc(self.viewer, "/quants", warehouse_id=self.wh2.id)
        self.assertEqual([(q["location_id"], q["quantity"]) for q in res2["quants"]], [(self.l2[0].id, 3.0)])
        self.assertIsNone(res2["products"][str(self.p3.id)]["default_code"])

    def test_quants_paging(self):
        a = self.rpc(self.viewer, "/quants", warehouse_id=self.wh1.id, offset=0, limit=2)
        b = self.rpc(self.viewer, "/quants", warehouse_id=self.wh1.id, offset=a["next"], limit=2)
        self.assertEqual((len(a["quants"]), a["total"], len(b["quants"]), b["next"]), (2, 3, 1, None))
        self.assertFalse({q["id"] for q in a["quants"]} & {q["id"] for q in b["quants"]})

    # ------------------------------------------------------------ категории хранения, правила размещения, min / max
    def test_storage_categories(self):
        res = self.rpc(self.viewer, "/storage_categories", warehouse_id=self.wh1.id)
        self.assertEqual(res["status"], "ok")
        self.assertEqual([c["id"] for c in res["storage_categories"]], [self.cat.id])
        c = res["storage_categories"][0]
        self.assertEqual((c["name"], c["max_weight"], c["allow_new_product"]), ("Категорія тест", 100.0, self.cat.allow_new_product))
        caps = {(k["product_id"], k["package_type"]): k["quantity"] for k in c["capacities"]}
        self.assertEqual(caps, {(self.p1.id, None): 50.0, (None, "Піддон тест"): 4.0})
        self.assertIn(str(self.p1.id), res["products"])
        self.assertEqual(self.rpc(self.viewer, "/storage_categories", warehouse_id=self.wh2.id)["storage_categories"], [])

    def test_putaway_rules(self):
        res = self.rpc(self.viewer, "/putaway_rules", warehouse_id=self.wh1.id)
        rules = [r for r in res["putaway_rules"] if r["id"] == self.rule.id]
        self.assertEqual(len(rules), 1)
        r = rules[0]
        self.assertEqual((r["product_id"], r["location_in_id"], r["location_out_id"], r["storage_category_id"], r["package_types"]),
                         (self.p1.id, self.wh1.lot_stock_id.id, self.l1[0].id, self.cat.id, []))
        self.assertIn("sublocation", r)
        self.assertFalse([x for x in self.rpc(self.viewer, "/putaway_rules", warehouse_id=self.wh2.id)["putaway_rules"] if x["id"] == self.rule.id])

    def test_orderpoints(self):
        res = self.rpc(self.viewer, "/orderpoints", warehouse_id=self.wh1.id)
        self.assertEqual(res["total"], 1)
        o = res["orderpoints"][0]
        self.assertEqual((o["location_id"], o["product_id"], o["min"], o["max"], o["warehouse_id"]), (self.l1[0].id, self.p2.id, 2.0, 10.0, self.wh1.id))
        self.assertEqual(self.rpc(self.viewer, "/orderpoints", warehouse_id=self.wh2.id)["orderpoints"], [])

    # ------------------------------------------------------------ права
    def test_denied_without_group(self):
        for route in ("/warehouses", "/locations", "/quants", "/storage_categories", "/putaway_rules", "/orderpoints"):
            res = self.rpc(self.plain, route, warehouse_id=self.wh1.id)
            self.assertEqual(res["status"], "denied", route)
            self.assertNotIn("locations", res)
