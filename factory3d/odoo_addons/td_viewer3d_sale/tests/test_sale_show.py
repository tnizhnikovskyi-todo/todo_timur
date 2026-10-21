from lxml import etree
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestSaleShow(TransactionCase):
    """A-17, V-09, AC-55: міст-модуль td_viewer3d_sale."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.partner = env["res.partner"].create({"name": "TST клієнт"})
        cls.product = env["product.product"].create({"name": "TST SO prod", "is_storable": True})
        cls.so = env["sale.order"].create(
            {"partner_id": cls.partner.id, "order_line": [(0, 0, {"product_id": cls.product.id, "product_uom_qty": 1})]}
        )

    def test_auto_installed(self):
        mod = self.env["ir.module.module"].search([("name", "=", "td_viewer3d_sale")])
        self.assertEqual(mod.state, "installed")
        self.assertTrue(mod.auto_install)

    def test_no_documents_raises(self):
        self.assertFalse(self.so.td_has_3d)
        with self.assertRaises(UserError):
            self.so.action_f3d_show()

    def test_mo_has_priority(self):
        later = self.env["mrp.production"].create(
            {
                "product_id": self.product.id,
                "product_qty": 1,
                "origin": self.so.name,
                "date_start": "2026-10-14 10:00:00",
            }
        )
        earlier = self.env["mrp.production"].create(
            {
                "product_id": self.product.id,
                "product_qty": 1,
                "origin": self.so.name,
                "date_start": "2026-10-12 10:00:00",
            }
        )
        self.assertNotEqual(later, earlier)
        self.so.invalidate_recordset()
        self.assertTrue(self.so.td_has_3d)
        act = self.so.action_f3d_show()
        self.assertEqual(act["tag"], "f3d_viewer.action")
        self.assertEqual(act["params"], {"mo": earlier.name, "so": self.so.name})

    def _mo(self, **vals):
        vals.setdefault("date_start", "2026-10-12 10:00:00")
        mo = self.env["mrp.production"].create(
            {"product_id": self.product.id, "product_qty": 1, "origin": self.so.name, **vals}
        )
        self.so.invalidate_recordset()
        return mo

    def test_first_live_mo_wins_over_done(self):
        """Кілька МО: перше «живе» (за date_start), навіть якщо виконане новіше чи старіше."""
        done = self._mo(date_start="2026-10-01 10:00:00")
        done.write({"state": "done", "date_finished": "2026-10-06 12:00:00"})
        live_late = self._mo(date_start="2026-10-14 10:00:00")
        live_early = self._mo(date_start="2026-10-12 10:00:00")
        self.assertEqual(live_early.state, "draft")
        self.assertEqual(self.so.action_f3d_show()["params"], {"mo": live_early.name, "so": self.so.name})
        self.assertNotEqual(live_late, live_early)

    def test_latest_mo_when_none_live(self):
        """Усі МО виконані чи скасовані: найновіше непроскасоване, а коли всі скасовані — найновіше скасоване."""
        old = self._mo(date_start="2026-10-01 10:00:00")
        old.write({"state": "done", "date_finished": "2026-10-03 12:00:00"})
        recent = self._mo(date_start="2026-10-02 10:00:00")
        recent.write({"state": "done", "date_finished": "2026-10-06 12:00:00"})
        cancelled = self._mo(date_start="2026-10-09 10:00:00")
        cancelled.write({"state": "cancel"})
        self.assertEqual(self.so.action_f3d_show()["params"]["mo"], recent.name)
        recent.write({"state": "cancel", "date_finished": "2026-10-06 12:00:00"})
        old.write({"state": "cancel", "date_finished": "2026-10-03 12:00:00"})
        self.assertEqual(self.so.action_f3d_show()["params"]["mo"], cancelled.name)

    def test_picking_fallback(self):
        ptype = (
            self.env["stock.picking.type"].with_context(active_test=False).search([("code", "=", "outgoing")], limit=1)
        )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": ptype.id,
                "location_id": ptype.default_location_src_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
                "origin": self.so.name,
            }
        )
        cancelled = picking.copy({"origin": self.so.name})
        cancelled.action_cancel()
        self.so.invalidate_recordset()
        self.assertTrue(self.so.td_has_3d)
        self.assertEqual(self.so.action_f3d_show()["params"], {"picking": picking.name, "so": self.so.name})
        picking.action_cancel()  # лишились самі скасовані: показуємо найновіше, а не помилку
        self.so.invalidate_recordset()
        self.assertTrue(self.so.td_has_3d)
        self.assertEqual(self.so.action_f3d_show()["params"], {"picking": cancelled.name, "so": self.so.name})

    def test_button_in_view(self):
        """V-09: кнопка в шапці з групою group_td_user; без групи — вилучена з arch."""
        user = new_test_user(
            self.env,
            login="f3d_sale_u",
            groups="base.group_user,sales_team.group_sale_salesman,td_factory3d.group_td_user",
        )
        plain = new_test_user(self.env, login="f3d_sale_p", groups="base.group_user,sales_team.group_sale_salesman")
        xp = "//header//button[@name='action_f3d_show']"
        arch = lambda u: etree.fromstring(  # noqa: E731
            self.env["sale.order"].with_user(u).get_view(view_type="form")["arch"]
        )
        self.assertEqual(len(arch(user).xpath(xp)), 1)
        self.assertEqual(arch(user).xpath(xp)[0].get("invisible"), "not td_has_3d")
        self.assertFalse(arch(plain).xpath(xp))
