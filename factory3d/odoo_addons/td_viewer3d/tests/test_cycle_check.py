from unittest.mock import Mock, patch

from odoo.tests import BaseCase, tagged

from odoo.addons.td_viewer3d.tools.cycle_check import check
from odoo.addons.td_viewer3d.tools.payload import PayloadBuilder

from .common import F3dViewerBase, F3dViewerCase


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

    def setUp(self):
        super().setUp()
        # payload будується з правами користувача: адміністратору «Завод 3D» потрібен ще й доступ до складу/МО
        self.user_admin.group_ids = [(4, self.env.ref("stock.group_stock_user").id),
                                     (4, self.env.ref("mrp.group_mrp_user").id)]

    def test_ok_on_demo(self):
        if "td.viewer.provider.logistics" not in self.env:
            self.skipTest("немає вбудованих провайдерів (W1b)")
        data = PayloadBuilder(self.env(user=self.user_admin), full=True).build()
        self.assertEqual(check(data), [])

    def test_wizard_ok_on_demo(self):
        """AC-36: «Перевірка циклу → Запустити» на демо-базі."""
        if "td.viewer.provider.logistics" not in self.env:
            self.skipTest("немає вбудованих провайдерів (W1b)")
        wiz = self.env["td.viewer.cycle.check"].with_user(self.user_admin).create({})
        wiz.action_run()
        self.assertEqual((wiz.state, wiz.issue_count), ("ok", 0))

    def test_issue_after_cancel_delivery(self):
        """AC-36: після скасування WH/OUT/00412 — «S00087: немає відвантаження» з посиланням."""
        picking = self.env["stock.picking"].search([("name", "=", "WH/OUT/00412")])
        if not picking:
            self.skipTest("немає WH/OUT/00412")
        picking.with_context(tracking_disable=True).action_cancel()
        wiz = self.env["td.viewer.cycle.check"].with_user(self.user_admin).create({})
        wiz.action_run()
        self.assertEqual(wiz.state, "issues")
        self.assertIn("S00087", wiz.result_html)
        self.assertIn("немає відвантаження", wiz.result_html)


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestCycleCheckWizard(F3dViewerBase):

    def _run(self, issues, payload):
        wiz = self.env["td.viewer.cycle.check"].with_user(self.user_admin).create({})
        base = "odoo.addons.td_viewer3d.wizard.cycle_check_wizard"
        with patch(base + ".check", return_value=issues), \
                patch(base + ".PayloadBuilder.build", return_value=payload):
            wiz.action_run()
        return wiz

    def test_html_links(self):
        """AC-36: «{name}: …» зі збігом у payload — data-f3d-open, інакше — data-f3d-code."""
        wiz = self._run(["WH/IN/00134: приймання без західних воріт", "S00087: немає відвантаження"],
                        {"pickings": [{"name": "WH/IN/00134"}], "productions": [], "quality_checks": []})
        self.assertEqual((wiz.state, wiz.issue_count), ("issues", 2))
        self.assertIn('data-f3d-open="WH/IN/00134"', wiz.result_html)
        self.assertIn('data-f3d-code="S00087"', wiz.result_html)
        self.assertEqual(wiz.action_show_first()["params"], {"open": "WH/IN/00134"})

    def test_ok_state(self):
        wiz = self._run([], {"pickings": []})
        self.assertEqual((wiz.state, wiz.issue_count), ("ok", 0))
        self.assertFalse(wiz.result_html)
        self.assertTrue(wiz.ran_at)

    def test_non_admin_uses_own_payload_user(self):
        wiz = self.env["td.viewer.cycle.check"].with_user(self.user_manager).create({})
        wiz.payload_user_id = self.user_kiosk
        seen = []
        base = "odoo.addons.td_viewer3d.wizard.cycle_check_wizard"
        with patch(base + ".check", return_value=[]), patch(
                base + ".PayloadBuilder",
                side_effect=lambda env, **kw: seen.append(env.uid) or Mock(build=lambda: {})):
            wiz.action_run()
        self.assertEqual(seen, [self.user_manager.id])
