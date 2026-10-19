from odoo.tests import tagged

from odoo.addons.td_viewer3d.tools.payload import resolve

from .common import F3dViewerBase, F3dViewerCase

CODES = {
    "PLT-04C": "stock.location",
    "SAW-1": "mrp.workcenter",
    "FL-1": "maintenance.equipment",
    "OP-SAW-1": "hr.employee",
    "Z-CUT": "td.zone",
    "TRUCK-IN-1": "stock.picking.batch",
    "DOCK-W1": "stock.location",
    "WO00013": "mrp.workorder",
}
NAMES = {
    "WH/MO/00231": "mrp.production",
    "WH/IN/00128": "stock.picking",
    "S00087": "sale.order",
    "MR/00031": "maintenance.request",
}


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestResolver(F3dViewerBase):
    """Без демо-даних: синтетичні записи."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wc = cls.env["mrp.workcenter"].create({"name": "ZZ центр", "td_code": "ZZ-WC-1"})
        cls.loc = cls.env["stock.location"].create(
            {
                "name": "ZZ",
                "location_id": cls.env.ref("stock.stock_location_stock").id,
                "td_code": "ZZ-LOC-1",
                "td_alias": "ZZ-LOC-ALIAS",
            }
        )
        cls.req = cls.env["maintenance.request"].create({"name": "ZZ-MR-1"})

    def test_codes_synthetic(self):
        res = resolve(self.env, code="ZZ-WC-1")
        self.assertEqual((res["model"], res["res_id"]), ("mrp.workcenter", self.wc.id))
        self.assertEqual(res["display_name"], self.wc.display_name)
        self.assertIn("kind", res)
        self.assertEqual(resolve(self.env, code="ZZ-LOC-ALIAS")["res_id"], self.loc.id)

    def test_names_synthetic(self):
        res = resolve(self.env, name="ZZ-MR-1")
        self.assertEqual((res["model"], res["res_id"], res["kind"]), ("maintenance.request", self.req.id, "document"))

    def test_not_found(self):
        for kw in ({"code": "ZZ-NOPE-9"}, {"name": "NO/SUCH/00001"}, {"code": "OP-W9"}, {"code": "WO99999"}, {}):
            self.assertEqual(resolve(self.env, **kw), {"model": None, "res_id": None, "reason": "not_found"})

    def test_respects_access(self):
        self.assertEqual(resolve(self.env(user=self.user_mrp_only), code="ZZ-WC-1")["model"], "mrp.workcenter")
        self.assertIsNone(resolve(self.env(user=self.user_nobody), code="ZZ-WC-1")["model"])

    def _bins(self):
        stock = self.env.ref("stock.stock_location_stock")
        return self.env["stock.location"].create(
            [{"name": f"ZZ-RK-B{i}", "location_id": stock.id, "td_code": f"ZZ-RK-B{i}"} for i in (1, 2)]
            + [{"name": "ZZ-RK-B3", "location_id": stock.id, "td_code": "ZZ-RK-X3", "td_alias": "ZZ-RK-B3"}]
        )

    def test_group_of_children(self):
        """R-16 п. 5: стелаж без власного запису -> список записів комірок (код і аліас), res_id порожній."""
        bins = self._bins()
        res = resolve(self.env, code="ZZ-RACK-1", codes=["ZZ-RK-B1", "ZZ-RK-B2", "ZZ-RK-B3", "ZZ-NO-BIN"])
        self.assertEqual((res["model"], res["res_id"], res["kind"], res["count"]), ("stock.location", None, "group", 3))
        self.assertEqual(sorted(res["res_ids"]), sorted(bins.ids))

    def test_group_own_record_wins(self):
        """Власний запис важливіший за дочірні коди."""
        self._bins()
        res = resolve(self.env, code="ZZ-WC-1", codes=["ZZ-RK-B1"])
        self.assertEqual((res["model"], res["res_id"]), ("mrp.workcenter", self.wc.id))
        self.assertNotIn("res_ids", res)

    def test_group_nothing_resolves(self):
        self._bins()
        expected = {"model": None, "res_id": None, "reason": "not_found"}
        self.assertEqual(resolve(self.env, code="ZZ-RACK-1", codes=["ZZ-NO-1", "ZZ-NO-2"]), expected)
        self.assertEqual(resolve(self.env, code="ZZ-RACK-1", codes=[]), expected)

    def test_group_cap(self):
        bins = self._bins()
        many = ["ZZ-RK-B1"] + [f"ZZ-PAD-{i}" for i in range(500)]
        res = resolve(self.env, code="ZZ-RACK-1", codes=many)
        self.assertEqual(res["res_ids"], bins[:1].ids)  # лише перші 200 кодів беруть участь у пошуку


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestResolverDemo(F3dViewerCase):
    def test_codes(self):
        """AC-24."""
        for code, model in CODES.items():
            with self.subTest(code=code):
                res = resolve(self.env, code=code)
                self.assertEqual(res["model"], model)
                self.assertTrue(res["res_id"])
        self.assertEqual(resolve(self.env, code="OP-W9")["reason"], "not_found")

    def test_names(self):
        names = dict(NAMES)
        # «MR/00031» — номер заявки з еталонного демо; у CE заявка має лише тему (name), без нумерації
        requests = self.env["maintenance.request"].search([])
        if not requests.filtered(lambda r: r.name == "MR/00031"):
            del names["MR/00031"]
            unique = [r.name for r in requests if requests.mapped("name").count(r.name) == 1]
            self.assertTrue(unique, "у демо-базі немає заявки з унікальною темою")
            names[unique[0]] = "maintenance.request"
        for name, model in names.items():
            with self.subTest(name=name):
                res = resolve(self.env, name=name)
                self.assertEqual(res["model"], model)
                self.assertEqual(self.env[model].browse(res["res_id"]).display_name, res["display_name"])

    def test_no_hr_access(self):
        self.assertEqual(resolve(self.env(user=self.user_mrp_only), code="OP-SAW-1")["reason"], "not_found")
