"""API-13: маршрут МО/переміщення, якого немає в живому payload («Показати в 3D» з виконаного чи скасованого документа)."""

from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged

from odoo.addons.td_viewer3d.tools import doc_route

from .common import F3dViewerBase

URL = "/f3d/viewer/doc_route"


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestDocRoute(HttpCase, F3dViewerBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        for user in (cls.user_f3d, cls.user_nobody):
            user.password = user.login
        cls.wc1 = env["mrp.workcenter"].create({"name": "TST DR WC1", "code": "TDR1", "td_code": "TST-DR-WC1"})
        cls.wc2 = env["mrp.workcenter"].create({"name": "TST DR WC2", "code": "TDR2", "td_code": "TST-DR-WC2"})
        cls.wc_plain = env["mrp.workcenter"].create({"name": "TST DR plain", "code": "TDRP"})
        cls.finished = env["product.product"].create({"name": "TST DR fin", "default_code": "TST-DR-F"})
        cls.comp = env["product.product"].create({"name": "TST DR cmp", "default_code": "TST-DR-C"})
        cls.bom = cls._bom(cls.finished, [cls.wc1, cls.wc2])
        cls.old = fields.Datetime.now() - timedelta(days=15)

    @classmethod
    def _bom(cls, product, centers):
        return cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_id": product.id,
                "product_qty": 1,
                "bom_line_ids": [(0, 0, {"product_id": cls.comp.id, "product_qty": 1})],
                "operation_ids": [
                    (0, 0, {"name": "Op %d" % i, "workcenter_id": wc.id, "time_cycle_manual": 10, "sequence": i})
                    for i, wc in enumerate(centers, 1)
                ],
            }
        )

    def _mo(self, bom=None):
        mo = self.env["mrp.production"].create(
            {"product_id": self.finished.id, "bom_id": (bom or self.bom).id, "product_qty": 1}
        )
        mo.action_confirm()
        return mo

    def _done_mo(self):
        """Виконане давно: поза payload (він бере лише відкриті й завершені сьогодні)."""
        mo = self._mo()
        mo.workorder_ids.write({"state": "done", "date_start": self.old, "date_finished": self.old})
        mo.with_context(force_date=True).write({"state": "done", "date_start": self.old, "date_finished": self.old})
        return mo

    def _picking(self, src, dest, state=None):
        ptype = (
            self.env["stock.picking.type"].with_context(active_test=False).search([("code", "=", "internal")], limit=1)
        )
        picking = self.env["stock.picking"].create(
            {"picking_type_id": ptype.id, "location_id": src.id, "location_dest_id": dest.id, "origin": "TST-ORIGIN"}
        )
        self.env["stock.move.line"].create(
            {
                "picking_id": picking.id,
                "product_id": self.comp.id,
                "location_id": src.id,
                "location_dest_id": dest.id,
                "quantity": 1,
            }
        )
        if state:
            picking.write({"state": state})
        return picking

    def _loc(self, name, code=None):
        parent = self.env["stock.warehouse"].search([], limit=1).view_location_id
        vals = {"name": name, "usage": "internal", "location_id": parent.id}
        if code:
            vals["td_code"] = code
        return self.env["stock.location"].create(vals)

    # --- МО ---------------------------------------------------------------
    def test_done_mo_route(self):
        """Виконане МО поза payload: коди центрів за порядком операцій, стани, дати, картка."""
        mo = self._done_mo()
        self.assertNotIn(mo.name, [m["name"] for m in self.payload(self.user_f3d)["productions"]])
        res = doc_route.build(self.env(user=self.user_f3d), "mo", mo.name)
        self.assertIsNone(res["reason"])
        self.assertEqual((res["kind"], res["name"], res["state"]), ("mo", mo.name, "done"))
        self.assertEqual([s["code"] for s in res["steps"]], ["TST-DR-WC1", "TST-DR-WC2"])
        self.assertEqual([s["sequence"] for s in res["steps"]], [1, 2])
        self.assertEqual({s["state"] for s in res["steps"]}, {"done"})
        self.assertEqual(res["steps"][0]["workcenter"], "TST DR WC1")
        self.assertEqual(res["date_finished"], res["date"])
        self.assertRegex(res["date"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
        self.assertEqual((res["product"], res["product_name"], res["qty"]), ("TST-DR-F", "TST DR fin", 1.0))

    def test_cancelled_mo_route(self):
        """Скасоване МО: маршрут усе одно віддається (стани операцій — cancel), без reason."""
        mo = self._mo()
        mo.action_cancel()
        res = doc_route.build(self.env(user=self.user_f3d), "mo", mo.name)
        self.assertEqual(res["state"], "cancel")
        self.assertIsNone(res["reason"])
        self.assertEqual([s["code"] for s in res["steps"]], ["TST-DR-WC1", "TST-DR-WC2"])
        self.assertEqual({s["state"] for s in res["steps"]}, {"cancel"})

    def test_mo_without_workorders(self):
        """МО без операцій: порожній маршрут із причиною, але з карткою (стан, виріб)."""
        mo = self.env["mrp.production"].create({"product_id": self.finished.id, "product_qty": 2, "bom_id": False})
        res = doc_route.build(self.env(user=self.user_f3d), "mo", mo.name)
        self.assertEqual(res["reason"], "no_workorders")
        self.assertEqual(res["steps"], [])
        self.assertEqual((res["name"], res["state"], res["qty"]), (mo.name, "draft", 2.0))

    def test_mo_without_scene_codes(self):
        """Операції є, але жоден центр не має td_code: причина no_codes, кроки лишаються для картки."""
        product = self.env["product.product"].create({"name": "TST DR fin2", "default_code": "TST-DR-F2"})
        mo = self._mo(self._bom(product, [self.wc_plain]))
        res = doc_route.build(self.env(user=self.user_f3d), "mo", mo.name)
        self.assertEqual(res["reason"], "no_codes")
        self.assertEqual([s["code"] for s in res["steps"]], [""])

    def test_mo_not_found_and_access(self):
        mo = self._mo()
        self.assertEqual(doc_route.build(self.env(user=self.user_f3d), "mo", "WH/MO/NOPE")["reason"], "not_found")
        # без прав на виробництво — відмова, дані не віддаються
        res = doc_route.build(self.env(user=self.user_stock_only), "mo", mo.name)
        self.assertEqual(res["reason"], "forbidden")
        self.assertNotIn("steps", res)

    # --- переміщення ------------------------------------------------------
    def test_picking_route(self):
        src, dest = self._loc("TST-DR-SRC", "TST-DR-SRC"), self._loc("TST-DR-DST", "TST-DR-DST")
        picking = self._picking(src, dest, state="done")
        res = doc_route.build(self.env(user=self.user_f3d), "picking", picking.name)
        self.assertIsNone(res["reason"])
        self.assertEqual((res["kind"], res["name"], res["state"], res["origin"]), ("picking", picking.name, "done", "TST-ORIGIN"))
        self.assertEqual([(x["code"], x["role"]) for x in res["locations"]], [("TST-DR-SRC", "from"), ("TST-DR-DST", "to")])

    def test_picking_without_scene_locations(self):
        picking = self._picking(self._loc("TST-DR-P1"), self._loc("TST-DR-P2"))
        res = doc_route.build(self.env(user=self.user_f3d), "picking", picking.name)
        self.assertEqual(res["reason"], "no_locations")
        self.assertEqual(res["locations"], [])
        self.assertEqual(doc_route.build(self.env(user=self.user_f3d), "picking", "WH/NOPE/1")["reason"], "not_found")

    # --- маршрут (jsonrpc) ------------------------------------------------
    def _rpc(self, params, login="f3d_user"):
        self.authenticate(login, login)
        return self.make_jsonrpc_request(URL, params)

    def test_route_jsonrpc(self):
        mo = self._done_mo()
        res = self._rpc({"mo": mo.name})
        self.assertEqual([s["code"] for s in res["steps"]], ["TST-DR-WC1", "TST-DR-WC2"])
        self.assertIsNone(res["reason"])
        dest = self._loc("TST-DR-J1", "TST-DR-J1")
        picking = self._picking(self._loc("TST-DR-J0", "TST-DR-J0"), dest)
        self.assertEqual(self._rpc({"picking": picking.name})["locations"][-1]["code"], "TST-DR-J1")

    def test_route_jsonrpc_validation_and_access(self):
        mo = self._mo()
        for params in ({}, {"mo": "A", "picking": "B"}, {"mo": "../x"}, {"mo": 5}, {"picking": "x" * 65}):
            with self.subTest(params=params):
                self.assertEqual(self._rpc(params)["reason"], "bad_request")
        self.assertEqual(self._rpc({"mo": mo.name}, login="f3d_nobody")["reason"], "forbidden")
        self.assertEqual(self._rpc({"mo": "WH/MO/NOPE"})["reason"], "not_found")
