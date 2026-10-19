from lxml import etree

from odoo.tests import tagged

from .common import F3dViewerBase

CARRIER_MODELS = (
    "stock.location",
    "mrp.workcenter",
    "maintenance.equipment",
    "hr.employee",
    "td.zone",
    "stock.picking.batch",
)


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestShowIn3D(F3dViewerBase):
    """FR-22, M-08, M-09: «Показати в 3D» на документах (viewer) і дія base CB-02 при встановленому viewer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._extra_users()
        env = cls.env
        cls.wc = env["mrp.workcenter"].create({"name": "TST WC", "code": "TSTWC", "td_code": "TST-SHOW-WC"})
        cls.finished = env["product.product"].create({"name": "TST fin", "default_code": "TST-F", "is_storable": True})
        cls.comp = env["product.product"].create({"name": "TST cmp", "default_code": "TST-C", "is_storable": True})
        cls.bom = env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.finished.product_tmpl_id.id,
                "product_id": cls.finished.id,
                "product_qty": 1,
                "bom_line_ids": [(0, 0, {"product_id": cls.comp.id, "product_qty": 1})],
                "operation_ids": [(0, 0, {"name": "Op", "workcenter_id": cls.wc.id, "time_cycle_manual": 10})],
            }
        )
        cls.mo = env["mrp.production"].create({"product_id": cls.finished.id, "bom_id": cls.bom.id, "product_qty": 1})
        cls.mo.action_confirm()
        cls.loc = env["stock.location"].create(
            {
                "name": "TST-LOC",
                "usage": "internal",
                "td_code": "TST-SHOW-LOC",
                "location_id": env["stock.warehouse"].search([], limit=1).view_location_id.id,
            }
        )
        cls.plain_loc = env["stock.location"].create(
            {
                "name": "TST-PLAIN",
                "usage": "internal",
                "location_id": env["stock.warehouse"].search([], limit=1).view_location_id.id,
            }
        )

    @classmethod
    def _extra_users(cls):
        cls.user_nogroup = cls._make_user(
            "f3d_nogroup", ["base.group_user", "sales_team.group_sale_salesman"]
        )  # читає документи, але без group_td_user

    def _picking(self, src):
        ptype = (
            self.env["stock.picking.type"].with_context(active_test=False).search([("code", "=", "internal")], limit=1)
        )
        picking = self.env["stock.picking"].create(
            {"picking_type_id": ptype.id, "location_id": src.id, "location_dest_id": self.plain_loc.id}
        )
        self.env["stock.move.line"].create(
            {
                "picking_id": picking.id,
                "product_id": self.comp.id,
                "location_id": src.id,
                "location_dest_id": self.plain_loc.id,
                "quantity": 1,
            }
        )
        return picking

    def test_mo_action(self):
        """M-08: params.mo + tab=production; для кількох записів — перший."""
        act = self.mo.action_f3d_show()
        self.assertEqual(act["type"], "ir.actions.client")
        self.assertEqual(act["tag"], "f3d_viewer.action")
        self.assertEqual(act["name"], "3D: " + self.mo.name)
        self.assertEqual(act["params"], {"mo": self.mo.name, "tab": "production"})
        other = self.mo.copy()
        self.assertEqual((other | self.mo).action_f3d_show()["params"]["mo"], other.name)

    def test_picking_action(self):
        picking = self._picking(self.loc)
        act = picking.action_f3d_show()
        self.assertEqual(act["tag"], "f3d_viewer.action")
        self.assertEqual(act["params"], {"picking": picking.name, "tab": "logistics"})

    def test_has_3d_compute(self):
        self.assertTrue(self.mo.td_has_3d)
        empty_mo = self.env["mrp.production"].create(
            {"product_id": self.finished.id, "product_qty": 1, "bom_id": False}
        )
        self.assertFalse(empty_mo.workorder_ids)
        self.assertFalse(empty_mo.td_has_3d)
        self.assertTrue(self._picking(self.loc).td_has_3d)
        self.assertFalse(self._picking(self.plain_loc).td_has_3d)

    def test_base_action_opens_viewer(self):
        """X-08: дія base CB-02 для 6 моделей носіїв при встановленому viewer; viewer метод не перевизначає."""
        env = self.env
        wh = env["stock.warehouse"].search([], limit=1)
        ptype = env["stock.picking.type"].with_context(active_test=False).search([("code", "=", "internal")], limit=1)
        picking = env["stock.picking"].create(
            {
                "picking_type_id": ptype.id,
                "location_id": self.loc.id,
                "location_dest_id": self.plain_loc.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.comp.id,
                            "product_uom_qty": 1,
                            "product_uom": self.comp.uom_id.id,
                            "location_id": self.loc.id,
                            "location_dest_id": self.plain_loc.id,
                        },
                    )
                ],
            }
        )
        records = {
            "stock.location": self.loc,
            "mrp.workcenter": self.wc,
            "maintenance.equipment": env["maintenance.equipment"].create({"name": "TST eq", "td_code": "TST-SHOW-EQ"}),
            "hr.employee": env["hr.employee"].create({"name": "TST emp", "td_code": "TST-SHOW-EMP"}),
            "td.zone": env["td.zone"].create({"name": "TST zone", "zone_type": "storage", "td_code": "TST-SHOW-ZONE"}),
            "stock.picking.batch": env["stock.picking.batch"].create(
                {"picking_ids": [(6, 0, picking.ids)], "td_code": "TST-SHOW-BATCH"}
            ),
        }
        self.assertEqual(set(records), set(CARRIER_MODELS))
        for model, rec in records.items():
            act = rec.action_f3d_show()
            self.assertEqual(act["tag"], "f3d_viewer.action", model)
            self.assertEqual(act["params"]["code"], rec.td_code, model)
            self.assertEqual(act["params"]["model"], model)
            self.assertEqual(act["params"]["res_id"], rec.id)
            self.assertNotIn("td_viewer3d", type(rec).action_f3d_show.__module__, model)
        self.assertEqual(wh.company_id, env.company)

    def _buttons(self, model, user):
        view = self.env[model].with_user(user).get_view(view_type="form")
        root = etree.fromstring(view["arch"])
        return root.xpath("//header//button[@name='action_f3d_show']"), root.xpath("//field[@name='td_has_3d']")

    def test_button_in_views(self):
        """AC-22: кнопка viewer у формах документів (з групою); у модулі немає представлень носіїв домішки."""
        for model in ("mrp.production", "stock.picking"):
            buttons, fields_ = self._buttons(model, self.user_f3d)
            self.assertEqual(len(buttons), 1, model)
            self.assertEqual(buttons[0].get("invisible"), "not td_has_3d", model)
            self.assertTrue(fields_, model)
            none, _ = self._buttons(model, self.user_nogroup)
            self.assertFalse(none, "без групи group_td_user кнопки немає: " + model)
        views = self.env["ir.model.data"].search([("module", "=", "td_viewer3d"), ("model", "=", "ir.ui.view")])
        models_ = set(self.env["ir.ui.view"].browse(views.mapped("res_id")).mapped("model"))
        self.assertFalse(models_ & set(CARRIER_MODELS))
