from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged

from .common import G_APPLY, G_DESIGN, G_VIEW, make_user

API = "/wh_constructor/api/apply"


@tagged("post_install", "-at_install")
class TestWhConstructorApply(HttpCase):
    """Применение плана изменений (W-13): создание с иерархией, перенос, переименование, атрибуты, архивация пустого, отказы, транзакционность, журнал и откат."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Loc = env["stock.location"].with_context(active_test=False)
        cls.wh = env["stock.warehouse"].create({"name": "Apply склад", "code": "AP1"})
        cls.view, cls.stock = cls.wh.view_location_id, cls.wh.lot_stock_id
        cls.zone = cls.Loc.create({"name": "Зона", "location_id": cls.stock.id, "usage": "internal"})
        cls.a = cls.Loc.create({"name": "A-1", "location_id": cls.zone.id, "usage": "internal", "barcode": "AP-A-1"})
        cls.b = cls.Loc.create({"name": "B-1", "location_id": cls.zone.id, "usage": "internal"})
        cls.empty = cls.Loc.create({"name": "E-1", "location_id": cls.zone.id, "usage": "internal"})
        cls.full = cls.Loc.create({"name": "F-1", "location_id": cls.zone.id, "usage": "internal"})
        vals = {"type": "consu"}
        if "is_storable" in env["product.product"]._fields:
            vals["is_storable"] = True
        cls.product = env["product.product"].create({"name": "Товар apply", "default_code": "AP-P1", **vals})
        env["stock.quant"]._update_available_quantity(cls.product, cls.full, 4.0)
        cls.pos = "posx" in cls.Loc._fields  # Odoo 18
        cls.applier = make_user(env, "wh_ap_applier", G_APPLY)
        cls.designer = make_user(env, "wh_ap_designer", G_DESIGN)
        cls.viewer = make_user(env, "wh_ap_viewer", G_VIEW)
        cls.Log = env["wh.apply.log"]

    # ------------------------------------------------------------ помощники
    def create_op(self, ref, name, parent, usage="internal", **vals):
        return {"kind": "create", "ref": ref, "name": name, "usage": usage, "parent": parent, "vals": vals}

    def apply(self, ops, user=None, **kw):
        return self.Log.with_user(user or self.applier).api_apply(warehouse_id=self.wh.id, ops=ops, project_key="ap-p", **kw)

    def loc(self, loc_id):
        return self.Loc.browse(loc_id)

    def hierarchy(self):
        return [self.create_op("r", "R7", {"id": self.zone.id}), self.create_op("s", "S01", {"ref": "r"}),
                self.create_op("p", "AP-R7-S01-L1", {"ref": "s"}, barcode="AP-R7-S01-L1")]

    # ------------------------------------------------------------ применение
    def test_create_hierarchy(self):
        ops = self.hierarchy()
        ops.reverse()  # порядок в плане не важен: родители создаются раньше детей
        res = self.apply(ops)
        self.assertEqual(res["status"], "ok")
        r, s, p = (self.loc(res["refs"][k]) for k in "rsp")
        self.assertEqual((r.location_id, s.location_id, p.location_id), (self.zone, r, s))
        self.assertEqual((r.usage, s.usage, p.usage), ("internal", "internal", "internal"))
        self.assertEqual(p.barcode, "AP-R7-S01-L1")
        self.assertEqual(p.complete_name, f"{self.zone.complete_name}/R7/S01/AP-R7-S01-L1")
        self.assertEqual(p.company_id, self.wh.company_id)
        self.assertEqual(res["counts"], {"create": 3, "move": 0, "rename": 0, "attrs": 0, "archive": 0})

    def test_positions_where_supported(self):
        res = self.apply([self.create_op("p", "AP-POS", {"id": self.zone.id}, posx=3, posy=2, posz=1, barcode="AP-POS")])
        p = self.loc(res["refs"]["p"])
        if self.pos:
            self.assertEqual((p.posx, p.posy, p.posz), (3, 2, 1))
        log = self.Log.search([("id", "=", res["log_id"])])
        self.assertEqual(log.ops[0]["skipped"], [] if self.pos else ["posx", "posy", "posz"], "в Odoo 19 позиций нет — поля пропущены, а не ошибка")
        self.assertEqual(p.barcode, "AP-POS")

    def test_move_rename_attrs_archive(self):
        other = self.Loc.create({"name": "Інша зона", "location_id": self.stock.id, "usage": "internal"})
        ops = [{"kind": "move", "id": self.b.id, "to": {"id": other.id}, "name": "B-1"}, {"kind": "rename", "id": self.a.id, "name": "A-2"},
               {"kind": "attrs", "id": self.a.id, "name": "A-2", "vals": {"barcode": "AP-A-2"}}, {"kind": "archive", "id": self.empty.id, "name": "E-1"}]
        res = self.apply(ops)
        self.assertEqual(res["counts"], {"create": 0, "move": 1, "rename": 1, "attrs": 1, "archive": 1})
        self.assertEqual(self.b.location_id, other)
        self.assertEqual((self.a.name, self.a.barcode), ("A-2", "AP-A-2"))
        self.assertFalse(self.empty.active)
        log = self.Log.search([("id", "=", res["log_id"])])
        self.assertEqual((log.user_id, log.state, log.warehouse_id, log.project_key), (self.applier, "applied", self.wh, "ap-p"))
        byop = {j["op"]: j for j in log.ops}
        self.assertEqual(byop["move"]["from"], self.zone.id); self.assertEqual(byop["rename"]["old"], "A-1"); self.assertEqual(byop["attrs"]["old"]["barcode"], "AP-A-1")

    def test_new_place_in_new_zone_under_moved(self):
        """Перенос в только что созданную локацию: родитель — ссылка на создаваемую."""
        res = self.apply([{"kind": "move", "id": self.b.id, "to": {"ref": "z"}, "name": "B-1"}, self.create_op("z", "Нова", {"id": self.stock.id}, "view")])
        self.assertEqual(self.b.location_id.id, res["refs"]["z"])

    # ------------------------------------------------------------ отказы
    def test_archive_refused_with_stock(self):
        with self.assertRaisesRegex(UserError, "не порожня"):
            self.apply([{"kind": "archive", "id": self.full.id, "name": "F-1"}])
        self.assertTrue(self.full.active)

    def test_archive_container_refused_when_child_has_stock(self):
        with self.assertRaisesRegex(UserError, "не порожня"):
            self.apply([{"kind": "archive", "id": self.zone.id, "name": "Зона"}])
        self.assertTrue(self.zone.active)

    def test_archive_refused_with_unfinished_move(self):
        other = self.Loc.create({"name": "M-1", "location_id": self.zone.id, "usage": "internal"})
        vals = {"product_id": self.product.id, "product_uom_qty": 1, "product_uom": self.product.uom_id.id, "location_id": other.id, "location_dest_id": self.a.id}
        if "name" in self.env["stock.move"]._fields:  # в Odoo 19 поля name у перемещения нет
            vals["name"] = "t"
        move = self.env["stock.move"].create(vals)
        self.assertNotIn(move.state, ("done", "cancel"))
        with self.assertRaisesRegex(UserError, "незавершене переміщення"):
            self.apply([{"kind": "archive", "id": other.id, "name": "M-1"}])
        self.assertTrue(other.active)

    def test_archive_warehouse_locations_refused(self):
        with self.assertRaises(UserError):
            self.apply([{"kind": "archive", "id": self.stock.id, "name": "Stock"}])

    def test_denied_without_group(self):
        ops = self.hierarchy()
        for user in (self.designer, self.viewer):
            with self.assertRaises(AccessError):
                self.apply(ops, user=user)
        self.assertFalse(self.Loc.search([("name", "=", "R7"), ("location_id", "=", self.zone.id)]))

    def test_foreign_location_and_bad_input(self):
        other_wh = self.env["stock.warehouse"].create({"name": "Apply склад 2", "code": "AP2"})
        foreign = self.Loc.create({"name": "Чужа", "location_id": other_wh.lot_stock_id.id, "usage": "internal"})
        with self.assertRaisesRegex(UserError, "не належить"):
            self.apply([{"kind": "rename", "id": foreign.id, "name": "X"}])
        with self.assertRaises(UserError):
            self.apply([])
        with self.assertRaises(UserError):
            self.apply([{"kind": "drop", "id": self.a.id}])
        with self.assertRaisesRegex(UserError, "батьківськ"):
            self.apply([self.create_op("p", "ORPHAN", {"ref": "nope"})])
        with self.assertRaisesRegex(UserError, "Штрихкод"):
            self.apply([self.create_op("p", "DUP", {"id": self.zone.id}, barcode="AP-A-1")])

    def test_move_into_itself_refused(self):
        child = self.Loc.create({"name": "Дитина", "location_id": self.zone.id, "usage": "internal"})
        with self.assertRaisesRegex(UserError, "всередину себе"):
            self.apply([{"kind": "move", "id": self.zone.id, "to": {"id": child.id}, "name": "Зона"}])

    def test_transactional(self):
        """Ошибка в середине плана (архив непустого после создания, переноса и переименования) — не применено ничего."""
        before = self.Loc.search_count([])
        ops = self.hierarchy() + [{"kind": "move", "id": self.b.id, "to": {"ref": "r"}, "name": "B-1"}, {"kind": "rename", "id": self.a.id, "name": "A-X"},
                                  {"kind": "archive", "id": self.empty.id, "name": "E-1"}, {"kind": "archive", "id": self.full.id, "name": "F-1"}]
        with self.assertRaises(UserError):
            self.apply(ops)
        self.assertEqual(self.Loc.search_count([]), before, "ничего не создано")
        self.assertEqual((self.b.location_id, self.a.name, self.empty.active), (self.zone, "A-1", True))
        self.assertFalse(self.Log.search([("project_key", "=", "ap-p"), ("state", "=", "applied")]))

    # ------------------------------------------------------------ журнал и откат
    def test_rollback_restores_everything(self):
        other = self.Loc.create({"name": "Інша", "location_id": self.stock.id, "usage": "internal"})
        ops = self.hierarchy() + [{"kind": "move", "id": self.b.id, "to": {"id": other.id}, "name": "B-1"}, {"kind": "rename", "id": self.a.id, "name": "A-2"},
                                  {"kind": "attrs", "id": self.a.id, "name": "A-2", "vals": {"barcode": "AP-A-2"}}, {"kind": "archive", "id": self.empty.id, "name": "E-1"}]
        res = self.apply(ops)
        created = [self.loc(i) for i in res["refs"].values()]
        out = self.Log.with_user(self.applier).api_rollback(log_id=res["log_id"])
        self.assertEqual(out["status"], "ok")
        self.assertTrue(all(not c.active for c in created), "созданное архивировано")
        self.assertEqual((self.b.location_id, self.a.name, self.a.barcode, self.empty.active), (self.zone, "A-1", "AP-A-1", True))
        log = self.Log.browse(res["log_id"])
        self.assertEqual((log.state, log.rolled_back_by), ("rolled_back", self.applier)); self.assertTrue(log.rolled_back_at)
        with self.assertRaisesRegex(UserError, "вже відкочено"):
            self.Log.with_user(self.applier).api_rollback(log_id=res["log_id"])

    def test_rollback_refused_when_created_used(self):
        res = self.apply(self.hierarchy())
        place = self.loc(res["refs"]["p"])
        self.env["stock.quant"]._update_available_quantity(self.product, place, 2.0)
        with self.assertRaisesRegex(UserError, "не порожня"):
            self.Log.with_user(self.applier).api_rollback(log_id=res["log_id"])
        self.assertTrue(place.active); self.assertEqual(self.Log.browse(res["log_id"]).state, "applied")

    def test_rollback_order_and_denied(self):
        first = self.apply([{"kind": "rename", "id": self.a.id, "name": "A-2"}])
        second = self.apply([{"kind": "rename", "id": self.a.id, "name": "A-3"}])
        with self.assertRaisesRegex(UserError, "пізніше"):
            self.Log.with_user(self.applier).api_rollback(log_id=first["log_id"])
        with self.assertRaises(AccessError):
            self.Log.with_user(self.designer).api_rollback(log_id=second["log_id"])
        self.Log.with_user(self.applier).api_rollback(log_id=second["log_id"])
        self.Log.with_user(self.applier).api_rollback(log_id=first["log_id"])
        self.assertEqual(self.a.name, "A-1")

    def test_rollback_keeps_previously_archived_children(self):
        kid = self.Loc.create({"name": "K-1", "location_id": self.empty.id, "usage": "internal"})
        old = self.Loc.create({"name": "K-OLD", "location_id": self.empty.id, "usage": "internal"})
        old.write({"active": False})
        res = self.apply([{"kind": "archive", "id": self.empty.id, "name": "E-1"}])
        self.assertFalse(self.empty.active); self.assertFalse(kid.active)
        self.Log.with_user(self.applier).api_rollback(log_id=res["log_id"])
        self.assertTrue(self.empty.active); self.assertTrue(kid.active); self.assertFalse(old.active, "ранее архивная дочерняя остаётся в архиве")

    def test_list(self):
        res = self.apply(self.hierarchy())
        rows = self.Log.with_user(self.designer).api_list(project_key="ap-p")
        self.assertEqual([r["id"] for r in rows], [res["log_id"]])
        self.assertEqual((rows[0]["user"], rows[0]["state"], rows[0]["counts"]["create"], rows[0]["warehouse"]), (self.applier.name, "applied", 3, "AP1"))
        self.assertEqual(rows[0]["ops"][0]["op"], "create")
        with self.assertRaises(AccessError):
            self.Log.with_user(self.viewer).api_list()

    # ------------------------------------------------------------ HTTP
    def rpc(self, user, route, **params):
        self.authenticate(user.login, f"{user.login}-pass-1")
        return self.make_jsonrpc_request(f"{API}{route}", params)

    def test_http_run_log_rollback(self):
        out = self.rpc(self.applier, "/run", warehouse_id=self.wh.id, ops=self.hierarchy(), key="ap-http")
        self.assertEqual(out["status"], "ok"); self.assertEqual(len(out["refs"]), 3)
        log = self.rpc(self.designer, "/log", key="ap-http")
        self.assertEqual(log["status"], "ok"); self.assertEqual(log["log"][0]["id"], out["log_id"])
        self.assertEqual(self.rpc(self.designer, "/run", warehouse_id=self.wh.id, ops=self.hierarchy())["status"], "denied")
        self.assertEqual(self.rpc(self.designer, "/rollback", log_id=out["log_id"])["status"], "denied")
        self.assertEqual(self.rpc(self.viewer, "/log")["status"], "denied")
        err = self.rpc(self.applier, "/run", warehouse_id=self.wh.id, ops=[{"kind": "archive", "id": self.full.id, "name": "F-1"}])
        self.assertEqual(err["status"], "error"); self.assertIn("не порожня", err["message"])
        self.assertEqual(self.rpc(self.applier, "/rollback", log_id=out["log_id"])["status"], "ok")
        self.assertEqual(self.rpc(self.applier, "/rollback", log_id=out["log_id"])["status"], "error")
