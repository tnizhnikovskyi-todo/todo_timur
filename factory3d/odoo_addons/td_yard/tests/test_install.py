from datetime import date, datetime

from odoo.tests import tagged

from ..tools import params as P
from ..tools import plate, tz
from .common import YardCase


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardInstall(YardCase):
    def test_module_installed(self):
        mod = self.env["ir.module.module"].search([("name", "=", "td_yard")])
        self.assertEqual(mod.state, "installed")
        self.assertNotIn("web_gantt", mod.dependencies_id.mapped("name"))

    def test_groups(self):
        sec = self.env.ref("td_yard.group_td_yard_security")
        disp = self.env.ref("td_yard.group_td_yard_dispatcher")
        mgr = self.env.ref("td_yard.group_td_yard_manager")
        admin = self.env.ref("td_factory3d.group_td_admin")
        self.assertIn(self.env.ref("td_factory3d.group_td_user"), sec.implied_ids)
        self.assertIn(sec, disp.implied_ids)
        self.assertIn(self.env.ref("stock.group_stock_user"), disp.implied_ids)
        self.assertIn(disp, mgr.implied_ids)
        self.assertIn(self.env.ref("td_factory3d.group_td_manager"), mgr.implied_ids)
        self.assertIn(mgr, admin.implied_ids)
        self.assertTrue(self.user_guard.has_group("td_factory3d.group_td_user"))
        self.assertTrue(self.user_manager.has_group("td_yard.group_td_yard_security"))

    def test_menus(self):
        root = self.env.ref("td_yard.menu_td_yard")
        self.assertEqual(root.parent_id, self.env.ref("td_factory3d.menu_td_root"))
        self.assertEqual(root.sequence, 60)
        self.assertEqual(len(root.search([("id", "child_of", root.id)])), 17)
        settings = self.env.ref("td_yard.menu_td_yard_config_settings")
        self.assertEqual(settings.parent_id, self.env.ref("td_factory3d.menu_td_config"))

    def test_params(self):
        ICP = self.env["ir.config_parameter"].sudo()
        self.assertEqual(ICP.get_param("td.yard.write_enabled"), "False")
        self.assertEqual(ICP.get_param("td.yard.lpr_min_confidence"), "0.80")
        for name, (_typ, _default) in P.PARAMS.items():
            self.assertIsNotNone(ICP.search([("key", "=", P.PREFIX + name)]).id or None, name)
        self.assertEqual(P.get_int(self.env, "walk_in_limit_per_day"), 5)
        self.assertAlmostEqual(P.get_float(self.env, "lpr_min_confidence"), 0.8)
        self.assertFalse(P.get_bool(self.env, "write_enabled"))
        ICP.set_param("td.yard.early_min", "abc")
        self.assertEqual(P.get_int(self.env, "early_min"), 60)

    def test_sequences(self):
        Seq = self.env["ir.sequence"]
        self.assertRegex(Seq.next_by_code("td.yard.visit"), r"^YV/\d{4}/\d{5}$")
        self.assertRegex(Seq.next_by_code("td.yard.weighing"), r"^WG/\d{4}/\d{5}$")

    def test_normalize_plate(self):
        for src, exp in (
            ("АА 4512 КТ", "AA4512KT"),
            ("aa-4512-kt", "AA4512KT"),
            ("КА 0001 ВХ", "KA0001BX"),
            ("ВІ 7777 ЕН", "BI7777EH"),
            ("ЖЖ1234", "ЖЖ1234"),
            ("", ""),
            (False, ""),
        ):
            self.assertEqual(plate.normalize_plate(src), exp)
        self.assertTrue(plate.is_valid_norm("ЖЖ1234"))
        self.assertFalse(plate.is_valid_norm("A"))

    def test_display_plate(self):
        self.assertEqual(plate.display_plate("АА4512КТ"), "АА 4512 КТ")
        self.assertEqual(plate.display_plate("aa 4512 kt"), "AA 4512 KT")
        self.assertEqual(plate.display_plate("ЖЖ1234"), "ЖЖ1234")

    def test_plate_input(self):
        self.assertTrue(plate.is_valid_plate_input(" аа 4512 кт".strip()))
        self.assertFalse(plate.is_valid_plate_input("A"))
        self.assertFalse(plate.is_valid_plate_input("AA#12"))

    def test_tz(self):
        self.assertEqual(tz.local_hm(datetime(2026, 7, 1, 6, 30)), "09:30")
        self.assertEqual(tz.local_hm(datetime(2026, 12, 1, 6, 30)), "08:30")
        self.assertEqual(tz.local_day(datetime(2026, 10, 14, 22, 30)), date(2026, 10, 15))
        start, end = tz.day_bounds_utc(date(2026, 10, 14))
        self.assertEqual((start, end), (datetime(2026, 10, 13, 21, 0), datetime(2026, 10, 14, 21, 0)))
        start, end = tz.day_bounds_utc(date(2026, 10, 25))
        self.assertEqual((end - start).total_seconds() / 3600, 25)

    def test_parse_axis_ts(self):
        self.assertEqual(tz.parse_axis_ts("1791954905507"), datetime(2026, 10, 14, 5, 15, 5, 507000))
        self.assertEqual(tz.parse_axis_ts(1791954905507), datetime(2026, 10, 14, 5, 15, 5, 507000))
        for bad in (None, "", "abc", "-5", 0, 10**30):
            self.assertIsNone(tz.parse_axis_ts(bad))
