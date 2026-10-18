from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..tools import heat
from .common import F3DBmsCase, F3DBmsHvacMixin

P = {
    "chp_el_kw": 800.0,
    "chp_heat_kw": 856.0,
    "chp_heat_75_kw": 676.0,
    "chp_heat_50_kw": 497.0,
    "chp_min_load": 0.5,
    "boilers": 2,
    "boiler_kw": 495.0,
    "boiler_stage_share": 0.85,
}


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestDesign(F3DBmsHvacMixin, F3DBmsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_hvac_fixtures()

    def test_macro_753(self):
        b = self.balance
        self.assertEqual(b.line_ids.mapped("kw_round"), [189, 109, 247, 208])
        self.assertEqual(
            b.line_ids.mapped("name")[1:3],
            [
                "Інфільтрація крізь ворота (0,1 обміну/год)",
                "Дахові установки: 50 % зовнішнього повітря, рекуперація 78 %",
            ],
        )
        self.assertEqual(b.total_kw, 753)
        self.assertAlmostEqual(b.total_raw, 752.69, delta=0.01)
        self.assertEqual(b.capacity_kw, 990)
        self.assertEqual(b.chp_heat_kw, 856)
        self.assertEqual(b.reserve, 1.45)
        self.assertEqual(b.reserve_boilers, 0.32)
        self.assertEqual(
            b.note,
            "Оцінка, не проєкт: U стін 0,35, покрівлі 0,25, підлоги 0,15 Вт/(м²·К); внутрішні теплонадходження від "
            "верстатів (сотні кВт у зміну) не враховано — це запас.",
        )
        self.assertEqual(b.line_ids[0].formula, "(3 996·0,35 + 10 800·0,25 + 10 800·0,15)·33/1000")

    def test_param_change_recompute(self):
        b = self.balance.with_user(self.user_manager)
        b.write({"u_wall": 0.5})
        self.assertEqual(b.line_ids[0].kw_round, 208)
        self.assertEqual(b.total_kw, 772)

    def test_internal_gains(self):
        b = self.balance.with_user(self.user_manager)
        b.write({"u_wall": 0.5, "internal_gains_kw": 100.0})
        self.assertEqual(len(b.line_ids), 5)
        self.assertEqual(b.line_ids[4].kw_round, -100)
        self.assertEqual(b.total_kw, 672)

    def test_reset_macro(self):
        b = self.balance.with_user(self.user_manager)
        b.write({"u_wall": 0.5, "internal_gains_kw": 100.0})
        b.action_reset_macro()
        self.assertEqual(b.total_kw, 753)
        self.assertEqual(len(b.line_ids), 4)

    def test_constraints(self):
        b = self.balance
        for vals in (
            {"heat_recovery": 1.0},
            {"t_in_set": -20.0},
            {"boiler_stage_share": 0.0},
            {"chp_heat_50_kw": 900.0},
            {"u_wall": 0.0},
        ):
            with self.subTest(vals=vals), self.assertRaises(ValidationError), self.cr.savepoint():
                b.write(vals)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.env["f3d.bms.heat.balance"].sudo().create({"company_id": b.company_id.id})

    def test_rights(self):
        with self.assertRaises(AccessError):
            self.balance.with_user(self.user_reader).write({"u_wall": 0.4})
        self.balance.with_user(self.user_reader).read(["total_kw"])


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestLive(F3DBmsHvacMixin, F3DBmsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_hvac_fixtures()

    def test_chp_heat_table(self):
        cases = {
            None: (497, "design"),
            0: (0, "calc"),
            397.3: (497, "calc"),
            500: (586.5, "calc"),
            700: (766, "calc"),
            800: (856, "calc"),
            900: (856, "calc"),
        }
        for el, (kw, src) in cases.items():
            res = heat.chp_heat(el, P)
            self.assertAlmostEqual(res[0], kw, delta=0.6, msg=str(el))
            self.assertEqual(res[1], src, str(el))
        self.assertEqual(heat.chp_heat(None, P, 512), (512, "signal"))

    def test_live_balance_table(self):
        r = heat.live_balance(322, 497, P)
        self.assertEqual((r["boil"], r["calc"], r["boilers_on"], r["load"], r["deficit"]), (0, 0, 0, 0.0, 0))
        r = heat.live_balance(600, 497, P, "K1")
        self.assertEqual((r["calc"], r["boilers_on"], r["load"], r["deficit"]), (1, 1, 0.21, 0))
        r = heat.live_balance(600, 497, P, "fault")
        self.assertEqual((r["boilers_on"], r["deficit"]), (0, 103.0))
        r = heat.live_balance(2000, 856, P, "K1+K2")
        self.assertEqual(r["deficit"], 154.0)
        r = heat.live_balance(917.75, 497, P)
        self.assertEqual((round(r["boil"], 2), r["calc"]), (420.75, 1))
        self.assertEqual(heat.live_balance(918, 497, P)["calc"], 2)

    def test_live_model(self):
        live = self.balance._f3d_bms_live()
        self.assertEqual(live["chp_source"], "design")
        self.assertEqual(live["chp_heat_now_kw"], 497)
        self.assertFalse(live["boiler_state"])
        self.assertEqual(live["outdoor_c"], 9.0)
        self.assertEqual(self.balance.sudo().chp_source, "design")
        sig = self.make_signal("equipment/BOILER/state", text="fault", kind="state")
        self.balance.boiler_state_signal_id = sig
        live = self.balance._f3d_bms_live()
        self.assertEqual((live["boiler_state"], live["boilers_on"]), ("fault", 0))

    def test_get_creates(self):
        self.env["f3d.bms.heat.balance"].sudo().search([]).unlink()
        b = self.env["f3d.bms.heat.balance"]._f3d_bms_get()
        self.assertEqual(b.total_kw, 753)
