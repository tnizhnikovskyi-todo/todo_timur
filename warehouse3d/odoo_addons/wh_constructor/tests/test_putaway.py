from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged

from .common import G_APPLY, G_DESIGN, G_VIEW, make_user


@tagged("post_install", "-at_install")
class TestWhConstructorPutaway(HttpCase):
    """Правила размещения (W-15): применение плана (создание, правка, удаление, откат), эндпоинт «куди покладе Odoo» против самой Odoo на 10 контрольных товарах
    (правила по товару, категории и её родителю, приоритет, категории хранения с ёмкостью и весом, «искать внутри», упаковки), проверка штрихкодов компании (I-06)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.PKG = "stock.package" if "stock.package" in env else "stock.quant.package"  # 19: stock.package, 18: stock.quant.package
        cls.Loc = env["stock.location"].with_context(active_test=False)
        cls.Rule = env["stock.putaway.rule"]
        cls.wh = env["stock.warehouse"].create({"name": "Put склад", "code": "PA1"})
        cls.stock = cls.wh.lot_stock_id
        cls.wh2 = env["stock.warehouse"].create({"name": "Put склад 2", "code": "PA2"})

        def loc(name, parent, **kw):
            return cls.Loc.create({"name": name, "location_id": parent.id, "usage": "internal", **kw})
        cls.loc = staticmethod(loc)
        vals = {"type": "consu"}
        if "is_storable" in env["product.product"]._fields:
            vals["is_storable"] = True
        cls.pvals = vals
        Prod, Categ = env["product.product"], env["product.category"]
        cls.parent_categ = Categ.create({"name": "PA батьківська"})
        cls.child_categ = Categ.create({"name": "PA дочірня", "parent_id": cls.parent_categ.id})
        cls.child_categ2 = Categ.create({"name": "PA дочірня 2", "parent_id": cls.parent_categ.id})
        cls.categ2 = Categ.create({"name": "PA категорія 2"})
        cls.pt, cls.pt2 = env["stock.package.type"].create({"name": "PA палета"}), env["stock.package.type"].create({"name": "PA піддон 2"})

        def prod(n, **kw):
            return Prod.create({"name": f"Товар PA {n}", "default_code": f"PA-P{n}", **vals, **kw})
        cls.p = {n: prod(n) for n in (1, 2, 3, 4, 5, 6, 9, 10)}
        cls.p[2].categ_id = cls.categ2
        cls.p[3].categ_id = cls.child_categ2
        cls.p[4].categ_id = cls.child_categ
        cls.p[7] = prod(7, weight=2.0)
        cls.p[8] = prod(8, weight=2.0)
        # места назначения
        cls.zA, cls.zA2, cls.zA3, cls.zA4p, cls.zA4c = (loc(n, cls.stock) for n in ("PA-A", "PA-A2", "PA-A3", "PA-A4p", "PA-A4c"))
        cls.sc1 = env["stock.storage.category"].create({"name": "PA SC1", "max_weight": 1000.0, "allow_new_product": "mixed", "capacity_ids": [
            (0, 0, {"product_id": cls.p[5].id, "quantity": 10.0}), (0, 0, {"product_id": cls.p[6].id, "quantity": 10.0})]})
        cls.sc2 = env["stock.storage.category"].create({"name": "PA SC2", "max_weight": 5.0, "allow_new_product": "mixed"})
        cls.sc3 = env["stock.storage.category"].create({"name": "PA SC3", "max_weight": 1000.0, "allow_new_product": "mixed", "capacity_ids": [
            (0, 0, {"package_type_id": cls.pt2.id, "quantity": 1.0})]})
        cls.zB, cls.zB6, cls.zW, cls.zPZ, cls.zPP = (loc(n, cls.stock) for n in ("PA-B", "PA-B6", "PA-W", "PA-PZ", "PA-PP"))
        cls.b1, cls.b2 = loc("B1", cls.zB, storage_category_id=cls.sc1.id, barcode="PA-B1"), loc("B2", cls.zB, storage_category_id=cls.sc1.id, barcode="PA-B2")
        cls.b61 = loc("B6-1", cls.zB6, storage_category_id=cls.sc1.id, barcode="PA-B61")
        cls.w1 = loc("W1", cls.zW, storage_category_id=cls.sc2.id, barcode="PA-W1")
        cls.pp1, cls.pp2 = loc("PP1", cls.zPP, storage_category_id=cls.sc3.id, barcode="PA-PP1"), loc("PP2", cls.zPP, storage_category_id=cls.sc3.id, barcode="PA-PP2")
        env["stock.quant"]._update_available_quantity(cls.p[5], cls.b1, 10.0)  # B1 полна по ёмкости товара
        cls.pkg_in_pp1 = env[cls.PKG].create({"package_type_id": cls.pt2.id})
        env["stock.quant"]._update_available_quantity(cls.p[10], cls.pp1, 1.0, package_id=cls.pkg_in_pp1)  # в PP1 уже стоит упаковка этого типа

        def rule(out, product=None, categ=None, pkgs=(), sub="no", sc=None, seq=0):
            return cls.Rule.create({"location_in_id": cls.stock.id, "location_out_id": out.id, "product_id": product.id if product else False, "category_id": categ.id if categ else False,
                                    "package_type_ids": [(6, 0, [x.id for x in pkgs])], "sublocation": sub, "storage_category_id": sc.id if sc else False, "sequence": seq,
                                    "company_id": cls.wh.company_id.id})
        cls.r1 = rule(cls.zA, product=cls.p[1])
        cls.r2 = rule(cls.zA2, categ=cls.categ2)
        cls.r3 = rule(cls.zA3, categ=cls.parent_categ)
        cls.r4c = rule(cls.zA4c, categ=cls.child_categ)
        cls.r4p = rule(cls.zA4p, product=cls.p[4])
        cls.r5 = rule(cls.zB, product=cls.p[5], sub="closest_location", sc=cls.sc1)
        cls.r6 = rule(cls.zB6, product=cls.p[6], sub="closest_location", sc=cls.sc1)
        cls.r7 = rule(cls.zW, product=cls.p[7], sub="closest_location", sc=cls.sc2)
        cls.r8 = rule(cls.zW, product=cls.p[8], sub="closest_location", sc=cls.sc2)
        cls.r9 = rule(cls.zPZ, pkgs=cls.pt)
        cls.r10 = rule(cls.zPP, pkgs=cls.pt2, sub="closest_location", sc=cls.sc3)
        cls.applier = make_user(env, "wh_pa_applier", G_APPLY)
        cls.designer = make_user(env, "wh_pa_designer", G_DESIGN)
        cls.viewer = make_user(env, "wh_pa_viewer", G_VIEW)
        cls.Log = env["wh.apply.log"]

    # ------------------------------------------------------------ помощники
    def apply(self, ops, user=None):
        return self.Log.with_user(user or self.applier).api_apply(warehouse_id=self.wh.id, ops=ops, project_key="pa-p")

    def rule_op(self, act="create", name="Правило", rid=None, ref="r:new", **rule):
        r = {"location_in": {"id": self.stock.id}, "location_out": {"id": self.zA.id}, "sublocation": "no", **rule}
        o = {"kind": "putaway", "act": act, "name": name, "rule": r}
        if act == "create":
            o["ref"] = ref
        else:
            o["id"] = rid
        return o

    def receipt_dest(self, product, qty):
        """Куда Odoo реально положит поступление: строка движения приёмки из поставщика на «Stock» (putaway при создании строки)."""
        env = self.env
        supplier = env.ref("stock.stock_location_suppliers")
        picking = env["stock.picking"].create({"picking_type_id": self.wh.in_type_id.id, "location_id": supplier.id, "location_dest_id": self.stock.id})
        vals = {"name": "t"} if "name" in env["stock.move"]._fields else {}
        mv = env["stock.move"].create({**vals, "product_id": product.id, "product_uom_qty": qty, "product_uom": product.uom_id.id, "picking_id": picking.id,
                                       "location_id": supplier.id, "location_dest_id": self.stock.id})
        picking.action_confirm()
        picking.action_assign()
        return mv.move_line_ids[:1].location_dest_id

    # ------------------------------------------------------------ «куда положит Odoo»: 10 контрольных товаров
    def test_where_matches_odoo_on_10_products(self):
        reader = self.env["wh.reader"].with_user(self.viewer)
        packages_before = self.env[self.PKG].search_count([])
        cases = [  # (товар, количество, тип упаковки, ожидаемая локация, что проверяет)
            (1, 1.0, None, self.zA, "правило по товару"),
            (2, 1.0, None, self.zA2, "правило по категории"),
            (3, 1.0, None, self.zA3, "правило по родительской категории"),
            (4, 1.0, None, self.zA4p, "товар важнее категории"),
            (5, 4.0, None, self.b2, "«искать внутри»: B1 полна по ёмкости товара — берётся B2"),
            (6, 12.0, None, self.stock, "количество больше ёмкости — правило не подходит, остаётся «Stock»"),
            (7, 2.0, None, self.w1, "вес 4 кг помещается в категорию на 5 кг"),
            (8, 3.0, None, self.stock, "вес 6 кг не помещается в категорию на 5 кг"),
            (9, 1.0, self.pt, self.zPZ, "правило по типу упаковки"),
            (10, 1.0, self.pt2, self.pp2, "упаковка этого типа уже в PP1, ёмкость 1 — берётся PP2"),
        ]
        self.assertEqual(len(cases), 10)
        for n, qty, ptype, want, what in cases:  # у каждого товара — свой порядок вызовов: приёмка резервирует место, и повтор того же товара вёл бы себя иначе (как в Odoo)
            product = self.p[n]
            res = reader.api_putaway_where(self.wh.id, product.id, qty, ptype.id if ptype else None)
            if ptype:  # упаковка — настоящая, как при «Put in pack»: решает сама Odoo
                pkg = self.env[self.PKG].create({"package_type_id": ptype.id})
                expected = self.stock._get_putaway_strategy(product, quantity=qty, package=pkg)
            else:  # поступление — настоящая приёмка
                expected = self.receipt_dest(product, qty)
            self.assertEqual(res["location_id"], expected.id, f"товар {n}: {what} (ответ {res['complete_name']}, Odoo {expected.complete_name})")
            self.assertEqual(res["location_id"], want.id, f"товар {n}: {what} (ожидание сценария)")
        res = reader.api_putaway_where(self.wh.id, self.p[4].id, 1.0)
        self.assertEqual((res["found"], res["rule_id"], res["arrival"]["id"]), (True, self.r4p.id, self.stock.id))
        self.assertEqual(res["rules"][:2], [self.r4p.id, self.r4c.id], "правила подходящие товару — в порядке приоритета Odoo")
        res = reader.api_putaway_where(self.wh.id, self.p[8].id, 3.0)
        self.assertEqual((res["found"], res["location_id"]), (False, self.stock.id))
        self.assertEqual(res["products"][str(self.p[8].id)]["weight"], 2.0)
        self.assertEqual(self.env[self.PKG].search_count([]), packages_before + 2, "эндпоинт не оставляет временных упаковок (две — сами контрольные)")

    def test_where_validation_and_rights(self):
        reader = self.env["wh.reader"].with_user(self.viewer)
        with self.assertRaises(UserError):
            reader.api_putaway_where(self.wh.id, 0, 1.0)
        with self.assertRaises(UserError):
            reader.api_putaway_where(self.wh.id, self.p[1].id, 0)
        with self.assertRaises(UserError):
            reader.api_putaway_where(self.wh.id, self.p[1].id, 1.0, location_id=self.wh2.lot_stock_id.id)
        with self.assertRaises(UserError):
            reader.api_putaway_where(self.wh.id, self.p[1].id, 1.0, package_type_id=999999)
        with self.assertRaises(AccessError):
            self.env["wh.reader"].with_user(make_user(self.env, "wh_pa_nobody")).api_putaway_where(self.wh.id, self.p[1].id, 1.0)
        res = reader.api_putaway_where(self.wh.id, self.p[2].id, 1.0, location_id=self.stock.id)
        self.assertEqual(res["location_id"], self.zA2.id)

    # ------------------------------------------------------------ применение правил
    def test_apply_create_update_delete_and_rollback(self):
        new_zone = {"kind": "create", "ref": "z:new", "name": "PA-NEW", "usage": "internal", "parent": {"id": self.stock.id}, "vals": {}}
        res = self.apply([new_zone, self.rule_op(name="в нову зону", ref="r:one", location_out={"ref": "z:new"}, product="PA-P9", sequence=5),
                          self.rule_op(name="за категорією", ref="r:two", location_out={"id": self.zB.id}, category_id=self.categ2.id, package_type_ids=[self.pt.id],
                                       sublocation="closest_location", storage_category_id={"id": self.sc1.id})])
        self.assertEqual(res["status"], "ok")
        self.assertEqual((res["counts"]["putaway"], res["counts"]["create"]), (2, 1))
        one, two = self.Rule.browse(res["refs"]["r:one"]), self.Rule.browse(res["refs"]["r:two"])
        self.assertEqual((one.location_out_id.name, one.product_id, one.sequence, one.sublocation, one.company_id), ("PA-NEW", self.p[9], 5, "no", self.wh.company_id))
        self.assertEqual((two.category_id, two.package_type_ids, two.sublocation, two.storage_category_id), (self.categ2, self.pt, "closest_location", self.sc1))
        log1 = self.Log.browse(res["log_id"])
        # правка и удаление
        res2 = self.apply([self.rule_op("update", "правка", rid=one.id, location_out={"id": self.zA3.id}, product="PA-P9", sequence=1, sublocation="no"),
                           {"kind": "putaway", "act": "delete", "id": two.id, "name": "видалити"}])
        self.assertEqual(res2["counts"]["putaway"], 2)
        self.assertEqual((one.location_out_id, one.sequence), (self.zA3, 1))
        self.assertFalse(two.active, "«видалити» архивирует правило: Odoo его больше не применяет")
        self.assertNotIn(two, self.stock.putaway_rule_ids)
        # откат: удалённое возвращается (тот же id), изменённое получает прежние значения; позднее применение откатывается первым
        with self.assertRaises(UserError):
            self.Log.with_user(self.applier).api_rollback(log_id=log1.id)
        self.Log.with_user(self.applier).api_rollback(log_id=res2["log_id"])
        self.assertEqual((one.location_out_id.name, one.sequence), ("PA-NEW", 5))
        self.assertTrue(two.active)
        self.assertEqual((two.package_type_ids, two.storage_category_id, two.location_out_id), (self.pt, self.sc1, self.zB))
        self.Log.with_user(self.applier).api_rollback(log_id=log1.id)
        self.assertFalse(one.exists())
        self.assertFalse(two.exists(), "созданные первым применением правила убраны откатом")

    def test_apply_refusals_and_transaction(self):
        before = self.Rule.search_count([])
        foreign = self.wh2.lot_stock_id
        bad = [
            (self.rule_op(location_out={"id": foreign.id}, location_in={"id": foreign.id}), "чужого склада"),
            (self.rule_op(location_in={"id": self.zA.id}, location_out={"id": self.stock.id}), "«куди» вне «звідки»"),
            (self.rule_op(sublocation="closest_location"), "без категории хранения"),
            (self.rule_op(sublocation="closest_location", storage_category_id={"id": 999999}), "нет такой категории хранения"),
            (self.rule_op(product="NOPE-CODE"), "нет такого товара"),
            (self.rule_op(package_type_ids=[999999]), "нет такого типа упаковки"),
            (self.rule_op(category_id=999999), "нет такой категории товаров"),
            (self.rule_op(sublocation="weird"), "неизвестное «искать внутри»"),
            (self.rule_op("update", rid=999999), "нет правила"),
            (self.rule_op("update", rid=self.r1.id, location_out={"id": self.zB.id}, location_in={"id": self.zA.id}), "куди вне звідки при правке"),
            ({"kind": "putaway", "act": "delete", "id": 999999, "name": "x"}, "удаление несуществующего"),
            ({"kind": "putaway", "act": "zzz", "name": "x"}, "неизвестное действие"),
        ]
        for op, what in bad:
            with self.assertRaises(UserError, msg=what):
                self.apply([op])
        # транзакция: хорошее правило пропадает вместе с плохим, созданная локация — тоже
        with self.assertRaises(UserError):
            self.apply([{"kind": "create", "ref": "z:t", "name": "PA-TX", "usage": "internal", "parent": {"id": self.stock.id}, "vals": {}},
                        self.rule_op(ref="r:good", location_out={"ref": "z:t"}), self.rule_op(ref="r:bad", product="NOPE-CODE")])
        self.assertEqual(self.Rule.search_count([]), before)
        self.assertFalse(self.Loc.search([("name", "=", "PA-TX")]))
        with self.assertRaises(AccessError):
            self.apply([self.rule_op()], user=self.designer)

    def test_http_routes(self):
        self.authenticate(self.applier.login, f"{self.applier.login}-pass-1")
        out = self.make_jsonrpc_request("/wh_constructor/api/apply/run", {"warehouse_id": self.wh.id, "key": "pa-http", "ops": [self.rule_op(name="http", ref="r:h", product="PA-P2")]})
        self.assertEqual((out["status"], out["counts"]["putaway"]), ("ok", 1))
        self.authenticate(self.viewer.login, f"{self.viewer.login}-pass-1")
        res = self.make_jsonrpc_request("/wh_constructor/api/read/putaway_where", {"warehouse_id": self.wh.id, "product_id": self.p[1].id, "quantity": 1})
        self.assertEqual((res["status"], res["location_id"]), ("ok", self.zA.id))
        res = self.make_jsonrpc_request("/wh_constructor/api/read/barcodes", {"warehouse_id": self.wh.id, "items": [{"barcode": "PA-B1"}, {"barcode": "PA-NEW-FREE"}]})
        self.assertEqual((res["status"], [c["barcode"] for c in res["conflicts"]]), ("ok", ["PA-B1"]))
        res = self.make_jsonrpc_request("/wh_constructor/api/read/products", {"query": "PA-P1"})
        self.assertEqual(res["status"], "ok")
        self.assertIn(self.p[1].id, res["ids"])
        res = self.make_jsonrpc_request("/wh_constructor/api/read/product_categories", {})
        self.assertIn(self.child_categ.id, [c["id"] for c in res["product_categories"]])
        denied = self.make_jsonrpc_request("/wh_constructor/api/apply/run", {"warehouse_id": self.wh.id, "ops": [self.rule_op(ref="r:x")]})
        self.assertEqual(denied["status"], "denied")

    # ------------------------------------------------------------ чтение для «поместится ли»
    def test_reader_fit_data(self):
        reader = self.env["wh.reader"].with_user(self.viewer)
        self.pt.write({"packaging_length": 120.0, "width": 80.0, "height": 15.0, "base_weight": 20.0, "max_weight": 1000.0})
        rules = {r["id"]: r for r in reader.api_putaway_rules(self.wh.id)["putaway_rules"]}
        self.assertEqual((rules[self.r5.id]["sublocation"], rules[self.r5.id]["storage_category_id"]), ("closest_location", self.sc1.id))
        prods = reader.api_products("PA-P7")["products"]
        p7 = prods[str(self.p[7].id)]
        self.assertEqual(p7["weight"], 2.0)
        p3 = reader.api_products("PA-P3")["products"][str(self.p[3].id)]
        self.assertEqual(p3["categ_ids"][:2], [self.child_categ2.id, self.parent_categ.id], "категория товара и родитель — для правил по родительской категории")
        pk = {x["id"]: x for x in reader.api_package_types()["package_types"]}[self.pt.id]
        k = self.env["wh.reader"]._units(self.env)
        self.assertEqual((pk["length"], pk["max_weight"]), (round(120.0 * k["length"], 6), round(1000.0 * k["weight"], 6)), "размеры упаковки приходят в метрах, вес — в кг")
        self.assertEqual(reader.api_products("x"), {"products": {}, "ids": []})

    # ------------------------------------------------------------ штрихкоды компании (I-06)
    def test_barcodes_company_check(self):
        other_wh_loc = self.loc("PA2-X", self.wh2.lot_stock_id, barcode="PA-OTHER-WH")
        archived = self.loc("PA-ARC", self.stock, barcode="PA-ARCHIVED")
        archived.active = False
        customer = self.env["stock.location"].create({"name": "PA-CUST", "usage": "customer", "barcode": "PA-CUSTOMER-BC", "company_id": self.wh.company_id.id})
        other_co = self.env["res.company"].create({"name": "Чужа компанія PA"})
        self.env["stock.location"].create({"name": "PA-FOREIGN", "usage": "internal", "barcode": "PA-OTHER-CO", "company_id": other_co.id})
        reader = self.env["wh.reader"].with_user(self.viewer)
        items = [{"barcode": "PA-OTHER-WH"}, {"barcode": "PA-ARCHIVED"}, {"barcode": "PA-CUSTOMER-BC"}, {"barcode": "PA-B1"}, {"barcode": "PA-B2", "exclude_id": self.b2.id},
                 {"barcode": "PA-OTHER-CO"}, {"barcode": "PA-FREE"}, {"barcode": ""}]
        res = reader.api_barcodes(self.wh.id, items)
        got = {c["barcode"]: c for c in res["conflicts"]}
        self.assertEqual(set(got), {"PA-OTHER-WH", "PA-ARCHIVED", "PA-CUSTOMER-BC", "PA-B1"})
        self.assertEqual((got["PA-OTHER-WH"]["warehouse"], got["PA-OTHER-WH"]["same_warehouse"], got["PA-OTHER-WH"]["location_id"]), ("PA2", False, other_wh_loc.id))
        self.assertTrue(got["PA-ARCHIVED"]["archived"])
        self.assertTrue(got["PA-B1"]["same_warehouse"])
        self.assertEqual(res["checked"], 7)
        self.assertTrue(customer.exists())
        # то, что сервер называет конфликтом, при применении действительно отказ (и наоборот: свободный штрихкод проходит)
        for code in ("PA-OTHER-WH", "PA-ARCHIVED", "PA-CUSTOMER-BC"):
            with self.assertRaises(UserError, msg=code):
                self.apply([{"kind": "create", "ref": "n", "name": "N", "usage": "internal", "parent": {"id": self.stock.id}, "vals": {"barcode": code}}])
        self.assertEqual(self.apply([{"kind": "create", "ref": "n", "name": "N", "usage": "internal", "parent": {"id": self.stock.id}, "vals": {"barcode": "PA-OTHER-CO"}}])["status"], "ok",
                         "штрихкод другой компании не мешает")
        with self.assertRaises(UserError):
            reader.api_barcodes(self.wh.id, "x")
        with self.assertRaises(AccessError):
            self.env["wh.reader"].with_user(make_user(self.env, "wh_pa_nobody2")).api_barcodes(self.wh.id, [])
