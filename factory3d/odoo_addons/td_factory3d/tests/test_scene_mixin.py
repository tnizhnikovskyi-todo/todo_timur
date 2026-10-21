from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger

from .common import F3DCase


class SceneCase(F3DCase):
    # носії домішки в цьому воркері: mrp.workcenter та hr.employee (інші додають W2+)
    def loc(self, name, **vals):
        return self.env["mrp.workcenter"].create(dict(vals, name=name))

    def emp_(self, name, **vals):
        return self.env["hr.employee"].create(dict(vals, name=name))


@tagged("post_install", "-at_install", "f3d", "f3d_base")
class TestCodeFormat(SceneCase):
    def test_valid_codes(self):
        for code in ("T-1", "A1", "FG-R1-B01-L1"):
            self.assertEqual(self.loc("L " + code, td_code=code).td_code, code)

    def test_invalid_codes(self):
        for code in ("z-test", "Z_TEST", "Z-", "-Z", "Z--1", "A" * 33, "Ворота 1"):
            with self.assertRaises(ValidationError, msg=code), self.cr.savepoint():
                self.loc("Bad " + code, td_code=code)

    def test_zone_code_too_long(self):
        """B-1 (AC-01): 33 символи в td.zone — ValidationError, а не мовчазне обрізання до 32."""
        self.assertEqual(self.make_zone("Z" * 32).td_code, "Z" * 32)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.make_zone("Z" * 33)
        zone = self.make_zone("Z-OK-1")
        with self.assertRaises(ValidationError), self.cr.savepoint():
            zone.td_code = "Z" * 40


@tagged("post_install", "-at_install", "f3d", "f3d_base")
class TestUniqueness(SceneCase):
    def test_unique_in_model(self):
        self.loc("A", td_code="U-1")
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.loc("B", td_code="U-1")

    def test_cross_model_allowed(self):
        wc = self.loc("W", td_code="T-1")
        emp = self.emp_("E", td_code="T-1")
        self.assertEqual(wc.td_code, emp.td_code)

    def test_alias_rules(self):
        a = self.loc("A", td_code="D-1", td_alias="U-1")
        with self.assertRaises(ValidationError):
            self.loc("B", td_code="U-1")
        with self.assertRaises(ValidationError):
            self.loc("C", td_code="C-1", td_alias="D-1")
        with self.assertRaises(ValidationError):
            a.td_alias = "D-1"
        with self.assertRaises(ValidationError):
            self.loc("D", td_alias="ONLY-1")


@tagged("post_install", "-at_install", "f3d", "f3d_base")
class TestSearch(SceneCase):
    def test_search_f3d_code_alias(self):
        loc = self.loc("A", td_code="D-1", td_alias="U-1")
        Loc = self.env["mrp.workcenter"]
        self.assertEqual(Loc.search_f3d("D-1"), loc)
        self.assertEqual(Loc.search_f3d("U-1"), loc)

    def test_search_empty(self):
        self.assertFalse(self.env["mrp.workcenter"].search_f3d(""))
        self.assertFalse(self.env["mrp.workcenter"].search_f3d(None))

    def test_search_archived(self):
        loc = self.loc("A", td_code="ARC-1")
        loc.active = False
        self.assertEqual(self.env["mrp.workcenter"].search_f3d("ARC-1"), loc)

    def test_resolve_order(self):
        wc = self.loc("A", td_code="X-1")
        emp = self.emp_("E", td_code="X-1")
        Mixin = self.env["td.scene.mixin"]
        # зона (td.zone) і локація з'являються в інших воркерах; порядок: ... РЦ -> працівник
        self.assertEqual(Mixin.f3d_resolve("X-1"), wc)
        wc.unlink()
        self.assertEqual(Mixin.f3d_resolve("X-1"), emp)
        self.assertIsNone(Mixin.f3d_resolve("NOPE-0"))

    def test_resolve_all(self):
        wc = self.loc("A", td_code="X-1")
        emp = self.emp_("E", td_code="X-1")
        res = self.env["td.scene.mixin"].f3d_resolve_all("X-1")
        self.assertEqual(res["mrp.workcenter"], wc)
        self.assertEqual(res["hr.employee"], emp)
        self.assertTrue(all(res.values()))
        self.assertNotIn("td.scene.mixin", res)


@tagged("post_install", "-at_install", "f3d", "f3d_base")
class TestShow(SceneCase):
    def test_show_with_viewer(self):
        wc = self.loc("W", td_code="SAW-9")
        with self.viewer_installed(True):
            self.assertTrue(wc.td_viewer_available)
            self.assertEqual(
                wc.action_f3d_show(),
                {
                    "type": "ir.actions.client",
                    "tag": "f3d_viewer.action",
                    "name": "3D Завод",
                    "target": "current",
                    "params": {
                        "code": "SAW-9",
                        "alias": False,
                        "model": "mrp.workcenter",
                        "res_id": wc.id,
                        "kind": "workcenter",
                    },
                },
            )

    def test_show_without_viewer(self):
        wc = self.loc("W", td_code="SAW-9")
        with self.viewer_installed(False):
            self.assertFalse(wc.td_viewer_available)
            act = wc.action_f3d_show()
        self.assertEqual(act["tag"], "display_notification")
        self.assertEqual(act["params"]["title"], "Модуль 3D-переглядача не встановлено")
        self.assertEqual(act["params"]["type"], "warning")
        self.assertIn("SAW-9", act["params"]["message"])

    def test_show_no_code(self):
        wc = self.env["mrp.workcenter"].create({"name": "W"})
        with self.assertRaises(UserError):
            wc.action_f3d_show()

    def test_viewer_detection_real(self):
        mod = self.env["ir.module.module"].sudo().search([("name", "=", "td_viewer3d"), ("state", "=", "installed")])
        self.assertEqual(self.env["td.scene.mixin"]._td_viewer_installed(), bool(mod))


@tagged("post_install", "-at_install", "f3d", "f3d_base")
class TestCodeRights(SceneCase):
    def test_code_write_rights(self):
        wc = self.loc("W")
        mrp_user = new_test_user(self.env, login="f3d_mrp", groups="base.group_user,mrp.group_mrp_manager")
        wc.with_user(mrp_user).write({"name": "W2"})
        with self.assertRaisesRegex(AccessError, "менеджер"):
            wc.with_user(mrp_user).write({"td_code": "W-1"})
        wc.sudo().write({"td_code": "W-2"})
        self.user_manager.group_ids = [(4, self.env.ref("mrp.group_mrp_manager").id)]
        wc.with_user(self.user_manager).write({"td_code": "W-1"})
        self.assertEqual(wc.td_code, "W-1")
        self.assertEqual(wc.td_kind, "workcenter")
