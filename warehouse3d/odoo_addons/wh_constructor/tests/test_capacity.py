from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged

from .common import G_APPLY, G_DESIGN, G_VIEW, make_user


@tagged("post_install", "-at_install")
class TestWhConstructorCapacity(HttpCase):
    """Ёмкость и атрибуты мест (W-14): новая категория хранения и её назначение, правка категории, флаги и стратегия списания, min/max (создание и изменение
    orderpoint), порядок «категории → локации → правила», отказы, откат, справочники читателя; отказ без группы."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Loc = env["stock.location"].with_context(active_test=False)
        cls.wh = env["stock.warehouse"].create({"name": "Cap склад", "code": "CP1"})
        cls.stock = cls.wh.lot_stock_id
        cls.zone = cls.Loc.create({"name": "Зона", "location_id": cls.stock.id, "usage": "internal"})
        cls.a = cls.Loc.create({"name": "A-1", "location_id": cls.zone.id, "usage": "internal", "barcode": "CP-A-1"})
        cls.b = cls.Loc.create({"name": "B-1", "location_id": cls.zone.id, "usage": "internal", "barcode": "CP-B-1"})
        cls.full = cls.Loc.create({"name": "F-1", "location_id": cls.zone.id, "usage": "internal", "barcode": "CP-F-1"})
        # «Stock» склада уже место пополнения, поэтому вложенным в него локациям флаг не поставить (правило Odoo); проверки флага — в отдельной зоне под корнем склада
        cls.rzone = cls.Loc.create({"name": "Окрема зона", "location_id": cls.wh.view_location_id.id, "usage": "internal"})
        cls.rplace = cls.Loc.create({"name": "R-1", "location_id": cls.rzone.id, "usage": "internal", "barcode": "CP-R-1"})
        vals = {"type": "consu"}
        if "is_storable" in env["product.product"]._fields:
            vals["is_storable"] = True
        cls.product = env["product.product"].create({"name": "Товар cap", "default_code": "CP-P1", **vals})
        cls.product2 = env["product.product"].create({"name": "Товар cap 2", "default_code": "CP-P2", **vals})
        env["stock.quant"]._update_available_quantity(cls.product, cls.full, 4.0)
        cls.pkg = env["stock.package.type"].create({"name": "Палета cap"})
        cls.strategy = env["product.removal"].search([], limit=1)
        cls.cat = env["stock.storage.category"].create({"name": "Cap категорія", "max_weight": 100.0, "allow_new_product": "mixed",
                                                        "capacity_ids": [(0, 0, {"product_id": cls.product.id, "quantity": 10.0})]})
        cls.free_cat = env["stock.storage.category"].create({"name": "Cap вільна", "max_weight": 5.0})
        cls.applier = make_user(env, "wh_cp_applier", G_APPLY)
        cls.designer = make_user(env, "wh_cp_designer", G_DESIGN)
        cls.viewer = make_user(env, "wh_cp_viewer", G_VIEW)
        cls.Log = env["wh.apply.log"]

    # ------------------------------------------------------------ помощники
    def apply(self, ops, user=None):
        return self.Log.with_user(user or self.applier).api_apply(warehouse_id=self.wh.id, ops=ops, project_key="cp-p")

    def new_cat(self, ref="c:new", name="Нова категорія", **vals):
        v = {"max_weight": 50, "allow_new_product": "same", "capacities": [{"product": "CP-P1", "quantity": 5}, {"package_type_id": self.pkg.id, "quantity": 2}]}
        v.update(vals)
        return {"kind": "category", "ref": ref, "name": name, "vals": v}

    # ------------------------------------------------------------ категории
    def test_new_category_assigned_to_new_and_existing_places(self):
        """Порядок «категории → локации»: категория создаётся первой, на неё ссылаются создаваемая и существующая локации (даже если в запросе они раньше)."""
        ops = [{"kind": "create", "ref": "p", "name": "CP-NEW", "usage": "internal", "parent": {"id": self.zone.id}, "vals": {"barcode": "CP-NEW", "storage_category_id": {"ref": "c:new"}}},
               {"kind": "attrs", "id": self.a.id, "name": "A-1", "vals": {"storage_category_id": {"ref": "c:new"}}}, self.new_cat()]
        res = self.apply(ops)
        self.assertEqual(res["status"], "ok")
        cat = self.env["stock.storage.category"].browse(res["refs"]["c:new"])
        self.assertEqual((cat.name, cat.max_weight, cat.allow_new_product, cat.company_id), ("Нова категорія", 50.0, "same", self.wh.company_id))
        self.assertEqual({(k.product_id.default_code or "", k.package_type_id.id or 0, k.quantity) for k in cat.capacity_ids}, {("CP-P1", 0, 5.0), ("", self.pkg.id, 2.0)})
        self.assertEqual(self.a.storage_category_id, cat)
        self.assertEqual(self.loc(res["refs"]["p"]).storage_category_id, cat)
        self.assertEqual(res["counts"], {"category": 1, "create": 1, "move": 0, "rename": 0, "attrs": 1, "orderpoint": 0, "archive": 0})
        log = self.Log.browse(res["log_id"])
        self.assertEqual((log.n_categories, log.n_orderpoints, log.n_attrs), (1, 0, 1))
        # откат: категория удалена, назначение снято, созданная локация в архиве
        self.Log.with_user(self.applier).api_rollback(log_id=res["log_id"])
        self.assertFalse(cat.exists())
        self.assertFalse(self.a.storage_category_id)
        self.assertFalse(self.loc(res["refs"]["p"]).active)

    def loc(self, loc_id):
        return self.Loc.browse(loc_id)

    def test_update_category_and_rollback(self):
        ops = [{"kind": "category", "id": self.cat.id, "name": "Cap категорія 2", "vals": {"max_weight": 250, "allow_new_product": "empty",
                                                                                            "capacities": [{"product": "CP-P2", "quantity": 7}]}}]
        res = self.apply(ops)
        self.assertEqual(res["counts"]["category"], 1)
        self.assertEqual((self.cat.name, self.cat.max_weight, self.cat.allow_new_product), ("Cap категорія 2", 250.0, "empty"))
        self.assertEqual([(k.product_id.default_code, k.quantity) for k in self.cat.capacity_ids], [("CP-P2", 7.0)])
        self.Log.with_user(self.applier).api_rollback(log_id=res["log_id"])
        self.assertEqual((self.cat.name, self.cat.max_weight, self.cat.allow_new_product), ("Cap категорія", 100.0, "mixed"))
        self.assertEqual([(k.product_id.default_code, k.quantity) for k in self.cat.capacity_ids], [("CP-P1", 10.0)])

    def test_assign_existing_category_and_clear(self):
        res = self.apply([{"kind": "attrs", "id": self.a.id, "name": "A-1", "vals": {"storage_category_id": self.cat.id}}])
        self.assertEqual(self.a.storage_category_id, self.cat)
        self.apply([{"kind": "attrs", "id": self.a.id, "name": "A-1", "vals": {"storage_category_id": None}}])
        self.assertFalse(self.a.storage_category_id)
        self.assertEqual(res["counts"]["attrs"], 1)

    # ------------------------------------------------------------ флаги и стратегия
    def test_flags_and_removal_strategy(self):
        vals = {"replenish_location": True, "removal_strategy_id": self.strategy.id}
        if "scrap_location" in self.Loc._fields:  # Odoo 18
            vals["scrap_location"] = True
        res = self.apply([{"kind": "attrs", "id": self.rplace.id, "name": "R-1", "vals": vals}])
        self.assertTrue(self.rplace.replenish_location)
        self.assertEqual(self.rplace.removal_strategy_id, self.strategy)
        if "scrap_location" in vals:
            self.assertTrue(self.rplace.scrap_location)
        log = self.Log.browse(res["log_id"])
        self.assertEqual(log.ops[0]["old"]["replenish_location"], False)
        self.Log.with_user(self.applier).api_rollback(log_id=res["log_id"])
        self.assertFalse(self.rplace.replenish_location)
        self.assertFalse(self.rplace.removal_strategy_id)

    def test_flags_on_created_zone_and_usage(self):
        res = self.apply([{"kind": "create", "ref": "z", "name": "Нова зона", "usage": "internal", "parent": {"id": self.wh.view_location_id.id},
                           "vals": {"replenish_location": True, "removal_strategy_id": self.strategy.id}}])
        z = self.loc(res["refs"]["z"])
        self.assertTrue(z.replenish_location)
        self.assertEqual(z.removal_strategy_id, self.strategy)
        self.apply([{"kind": "attrs", "id": self.a.id, "name": "A-1", "vals": {"usage": "view"}}])
        self.assertEqual(self.a.usage, "view")

    def test_flag_refusals(self):
        with self.assertRaisesRegex(UserError, "не порожня"):
            self.apply([{"kind": "attrs", "id": self.full.id, "name": "F-1", "vals": {"usage": "view"}}])
        with self.assertRaises(UserError):
            self.apply([{"kind": "attrs", "id": self.a.id, "name": "A-1", "vals": {"usage": "customer"}}])
        with self.assertRaises(UserError):
            self.apply([{"kind": "attrs", "id": self.a.id, "name": "A-1", "vals": {"removal_strategy_id": 987654}}])
        # «место пополнения» на вложенной локации, если оно уже стоит выше (правило Odoo)
        self.apply([{"kind": "attrs", "id": self.rzone.id, "name": "Окрема зона", "vals": {"replenish_location": True}}])
        with self.assertRaises(UserError):
            self.apply([{"kind": "attrs", "id": self.rplace.id, "name": "R-1", "vals": {"replenish_location": True}}])
        self.assertFalse(self.rplace.replenish_location)
        with self.assertRaises(UserError):  # и вложенной в «Stock» тоже: он сам место пополнения
            self.apply([{"kind": "attrs", "id": self.a.id, "name": "A-1", "vals": {"replenish_location": True}}])

    # ------------------------------------------------------------ min / max
    def rule(self, loc, product):
        return self.env["stock.warehouse.orderpoint"].with_context(active_test=False).search([("location_id", "=", loc.id), ("product_id", "=", product.id)])

    def test_orderpoint_create_update_rollback(self):
        res = self.apply([{"kind": "orderpoint", "name": "F-1", "location_id": self.full.id, "product": "CP-P1", "min": 2, "max": 8}])
        rule = self.rule(self.full, self.product)
        self.assertEqual((len(rule), rule.product_min_qty, rule.product_max_qty, rule.warehouse_id), (1, 2.0, 8.0, self.wh))
        self.assertEqual(res["counts"]["orderpoint"], 1)
        # изменение существующего правила (по id)
        res2 = self.apply([{"kind": "orderpoint", "name": "F-1", "id": rule.id, "location_id": self.full.id, "product": "CP-P1", "min": 3, "max": 12}])
        self.assertEqual((rule.product_min_qty, rule.product_max_qty), (3.0, 12.0))
        self.assertEqual(self.Log.browse(res2["log_id"]).ops[0]["old"], {"product_min_qty": 2.0, "product_max_qty": 8.0})
        # правило читается читателем: min / max видны приложению
        rows = self.env["wh.reader"].with_user(self.viewer).api_orderpoints(self.wh.id)["orderpoints"]
        self.assertEqual([(r["id"], r["min"], r["max"]) for r in rows], [(rule.id, 3.0, 12.0)])
        self.Log.with_user(self.applier).api_rollback(log_id=res2["log_id"])
        self.assertEqual((rule.product_min_qty, rule.product_max_qty), (2.0, 8.0))
        self.Log.with_user(self.applier).api_rollback(log_id=res["log_id"])
        self.assertFalse(self.rule(self.full, self.product).active, "созданное правило в архиве")

    def test_orderpoint_refusals(self):
        with self.assertRaisesRegex(UserError, "max"):
            self.apply([{"kind": "orderpoint", "name": "F-1", "location_id": self.full.id, "product": "CP-P1", "min": 9, "max": 3}])
        with self.assertRaisesRegex(UserError, "не знайдено"):
            self.apply([{"kind": "orderpoint", "name": "F-1", "location_id": self.full.id, "product": "НЕМАЄ", "min": 1, "max": 3}])
        with self.assertRaisesRegex(UserError, "товар"):
            self.apply([{"kind": "orderpoint", "name": "F-1", "location_id": self.full.id, "min": 1, "max": 3}])
        other_wh = self.env["stock.warehouse"].create({"name": "Cap склад 2", "code": "CP2"})
        foreign = self.Loc.create({"name": "Чужа", "location_id": other_wh.lot_stock_id.id, "usage": "internal"})
        with self.assertRaisesRegex(UserError, "не належить"):
            self.apply([{"kind": "orderpoint", "name": "x", "location_id": foreign.id, "product": "CP-P1", "min": 1, "max": 3}])
        self.apply([{"kind": "orderpoint", "name": "F-1", "location_id": self.full.id, "product": "CP-P1", "min": 1, "max": 3}])
        with self.assertRaisesRegex(UserError, "вже є"):
            self.apply([{"kind": "orderpoint", "name": "F-1", "location_id": self.full.id, "product": "CP-P1", "min": 2, "max": 4}])

    # ------------------------------------------------------------ отказы, транзакция
    def test_category_validation_and_transaction(self):
        before = self.env["stock.storage.category"].search_count([])
        bad_caps = [[{"product": "CP-P1", "package_type_id": self.pkg.id, "quantity": 1}], [{"quantity": 1}], [{"product": "CP-P1", "quantity": 0}],
                    [{"product": "CP-P1", "quantity": 1}, {"product": "CP-P1", "quantity": 2}], [{"product": "НЕМАЄ", "quantity": 1}], [{"package_type_id": 987654, "quantity": 1}]]
        for caps in bad_caps:
            with self.assertRaises(UserError, msg=str(caps)):
                self.apply([self.new_cat(capacities=caps)])
        with self.assertRaises(UserError):
            self.apply([self.new_cat(max_weight=-1)])
        with self.assertRaises(UserError):
            self.apply([self.new_cat(name=" ")])
        # категория создана, а следующая операция не проходит — в базе нет ни категории, ни локации
        with self.assertRaisesRegex(UserError, "Штрихкод"):
            self.apply([self.new_cat(), {"kind": "create", "ref": "p", "name": "DUP", "usage": "internal", "parent": {"id": self.zone.id}, "vals": {"barcode": "CP-A-1", "storage_category_id": {"ref": "c:new"}}}])
        self.assertEqual(self.env["stock.storage.category"].search_count([]), before)
        self.assertFalse(self.Log.search([("project_key", "=", "cp-p")]))

    def test_denied_without_group(self):
        ops = [self.new_cat(), {"kind": "orderpoint", "name": "F-1", "location_id": self.full.id, "product": "CP-P1", "min": 1, "max": 3}]
        for user in (self.designer, self.viewer):
            with self.assertRaises(AccessError):
                self.apply(ops, user=user)
        self.assertFalse(self.env["stock.storage.category"].search([("name", "=", "Нова категорія")]))
        self.assertFalse(self.rule(self.full, self.product))

    def test_http_apply_new_kinds(self):
        self.authenticate(self.applier.login, f"{self.applier.login}-pass-1")
        out = self.make_jsonrpc_request("/wh_constructor/api/apply/run", {"warehouse_id": self.wh.id, "key": "cp-http", "ops": [self.new_cat(),
              {"kind": "attrs", "id": self.b.id, "name": "B-1", "vals": {"storage_category_id": {"ref": "c:new"}}}]})
        self.assertEqual(out["status"], "ok")
        self.assertEqual((out["counts"]["category"], out["counts"]["attrs"]), (1, 1))
        self.authenticate(self.designer.login, f"{self.designer.login}-pass-1")
        denied = self.make_jsonrpc_request("/wh_constructor/api/apply/run", {"warehouse_id": self.wh.id, "ops": [self.new_cat(ref="c:other", name="Інша")]})
        self.assertEqual(denied["status"], "denied")

    # ------------------------------------------------------------ чтение справочников
    def test_reader_lists(self):
        reader = self.env["wh.reader"].with_user(self.viewer)
        names = {c["name"]: c for c in reader.api_storage_categories(self.wh.id)["storage_categories"]}
        self.assertIn("Cap вільна", names, "категория, ещё не назначенная локации, тоже читается: иначе конструктор создал бы её повторно")
        other_co = self.env["res.company"].create({"name": "Чужа компанія cap"})
        foreign = self.env["stock.storage.category"].create({"name": "Cap чужа", "company_id": other_co.id})
        self.assertNotIn("Cap чужа", {c["name"] for c in reader.api_storage_categories(self.wh.id)["storage_categories"]}, foreign.name)
        self.assertEqual(names["Cap категорія"]["capacities"][0]["quantity"], 10.0)
        strategies = reader.api_removal_strategies()["removal_strategies"]
        self.assertIn(self.strategy.id, [r["id"] for r in strategies])
        self.assertTrue(all(set(r) == {"id", "name", "method"} for r in strategies))
        self.assertIn(self.pkg.id, [r["id"] for r in reader.api_package_types()["package_types"]])
        locs = {r["id"]: r for r in reader.api_locations(self.wh.id)["locations"]}
        self.assertIn("removal_strategy_id", locs[self.a.id])
        self.authenticate(self.viewer.login, f"{self.viewer.login}-pass-1")
        for route in ("/removal_strategies", "/package_types"):
            self.assertEqual(self.make_jsonrpc_request(f"/wh_constructor/api/read{route}", {})["status"], "ok")
        self.authenticate(self.applier.login, f"{self.applier.login}-pass-1")
        self.assertEqual(self.make_jsonrpc_request("/wh_constructor/api/read/removal_strategies", {})["status"], "ok")
        with self.assertRaises(AccessError):
            self.env["wh.reader"].with_user(make_user(self.env, "wh_cp_nobody")).api_removal_strategies()
