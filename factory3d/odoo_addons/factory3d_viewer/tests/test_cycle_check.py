from odoo.tests import BaseCase, tagged

from odoo.addons.factory3d_viewer.tools.cycle_check import check
from odoo.addons.factory3d_viewer.tools.payload import PayloadBuilder

from .common import F3dViewerCase


def _empty():
    return {"pickings": [], "locations": {}, "sale_orders": [], "quality_checks": [], "productions": [],
            "workorders": {}}


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestCycleCheckPure(BaseCase):

    def test_empty_returns_list(self):
        issues = check(_empty())
        self.assertIsInstance(issues, list)
        self.assertFalse([i for i in issues if "приймання" in i])

    def test_issue_incoming_without_gate(self):
        d = _empty()
        d["pickings"] = [{"name": "WH/IN/00134", "type": "incoming", "dock": None, "lines": []}]
        self.assertIn("WH/IN/00134: приймання без західних воріт", check(d))


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestCycleCheck(F3dViewerCase):

    def test_ok_on_demo(self):
        if "f3d.viewer.provider.logistics" not in self.env:
            self.skipTest("немає вбудованих провайдерів (W1b)")
        # payload будується з правами користувача: адміністратору «Завод 3D» потрібен ще й доступ до складу/МО
        self.user_admin.group_ids = [(4, self.env.ref("stock.group_stock_user").id),
                                     (4, self.env.ref("mrp.group_mrp_user").id)]
        data = PayloadBuilder(self.env(user=self.user_admin), full=True).build()
        self.assertEqual(check(data), [])
