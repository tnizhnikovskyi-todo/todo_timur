from odoo.tests import tagged

from odoo.addons.factory3d_viewer.tools.payload import resolve

from .common import F3dViewerBase, F3dViewerCase

CODES = {
    "PLT-04C": "stock.location", "SAW-1": "mrp.workcenter", "FL-1": "maintenance.equipment",
    "OP-SAW-1": "hr.employee", "Z-CUT": "f3d.zone", "TRUCK-IN-1": "stock.picking.batch",
    "DOCK-W1": "stock.location", "WO00013": "mrp.workorder",
}
NAMES = {
    "WH/MO/00231": "mrp.production", "WH/IN/00128": "stock.picking", "S00087": "sale.order",
    "MR/00031": "maintenance.request",
}


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestResolver(F3dViewerBase):
    """Без демо-даних: синтетичні записи."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wc = cls.env["mrp.workcenter"].create({"name": "ZZ центр", "f3d_code": "ZZ-WC-1"})
        cls.loc = cls.env["stock.location"].create({
            "name": "ZZ", "location_id": cls.env.ref("stock.stock_location_stock").id, "f3d_code": "ZZ-LOC-1",
            "f3d_alias": "ZZ-LOC-ALIAS"})
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
        for name, model in NAMES.items():
            with self.subTest(name=name):
                res = resolve(self.env, name=name)
                self.assertEqual(res["model"], model)
                self.assertEqual(self.env[model].browse(res["res_id"]).display_name, res["display_name"])

    def test_no_hr_access(self):
        self.assertEqual(resolve(self.env(user=self.user_mrp_only), code="OP-SAW-1")["reason"], "not_found")
