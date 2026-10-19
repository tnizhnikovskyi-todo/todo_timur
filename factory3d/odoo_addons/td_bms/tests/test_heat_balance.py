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
            self.env["td.bms.heat.balance"].sudo().create({"company_id": b.company_id.id})

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
        live = self.balance._td_bms_live()
        self.assertEqual(live["chp_source"], "design")
        self.assertEqual(live["chp_heat_now_kw"], 497)
        self.assertFalse(live["boiler_state"])
        self.assertEqual(live["outdoor_c"], 9.0)
        self.assertEqual(self.balance.sudo().chp_source, "design")
        sig = self.make_signal("equipment/BOILER/state", text="fault", kind="state")
        self.balance.boiler_state_signal_id = sig
        live = self.balance._td_bms_live()
        self.assertEqual((live["boiler_state"], live["boilers_on"]), ("fault", 0))

    def test_get_creates(self):
        self.env["td.bms.heat.balance"].sudo().search([]).unlink()
        b = self.env["td.bms.heat.balance"]._td_bms_get()
        self.assertEqual(b.total_kw, 753)


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestChpHeatSource(F3DBmsHvacMixin, F3DBmsCase):
    """Тепло КГУ в тепловому балансі: сигнали `infra/chp/heat_kw` / `infra/totals/chp_kw` привʼязуються незалежно від
    порядку встановлення `td_bms` і `td_energy` (R-15); зупинена КГУ дає 0."""

    HEAT, EL = "infra/chp/heat_kw", "infra/totals/chp_kw"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_hvac_fixtures()

    def new_signals(self, heat_kw=0.0, el_kw=0.0):
        """Сигнали КГУ створюються після балансу (як `td_energy`, що ставиться після `td_bms`); поля балансу порожні."""
        self.balance.sudo().write({"chp_heat_signal_id": False, "chp_el_signal_id": False})
        return (
            self.make_signal(self.HEAT, heat_kw, unit="кВт"),
            self.make_signal(self.EL, el_kw, unit="кВт"),
        )

    def test_late_signals_are_linked_on_create(self):
        heat_sig, el_sig = self.new_signals()
        b = self.balance.sudo()
        self.assertEqual((b.chp_heat_signal_id, b.chp_el_signal_id), (heat_sig, el_sig))

    def test_manual_link_is_kept(self):
        self.new_signals()
        other = self.make_signal("test/chp_heat_alt", 5.0)
        b = self.balance.sudo()
        b.chp_heat_signal_id = other
        self.make_signal(self.HEAT, 7.0)  # сигнал із кодом з BALANCE_OPTIONAL: привʼязку, змінену вручну, не чіпаємо
        self.assertEqual(b.chp_heat_signal_id, other)

    def test_link_optional_is_idempotent(self):  # міграція 19.0.1.0.1
        heat_sig, el_sig = self.new_signals()
        b = self.balance.sudo()
        b.write({"chp_heat_signal_id": False, "chp_el_signal_id": False})
        written = self.env["td.bms.heat.balance"]._td_bms_link_optional()
        self.assertTrue({"chp_heat_signal_id", "chp_el_signal_id"} <= set(written[b.id]))
        self.assertEqual((b.chp_heat_signal_id, b.chp_el_signal_id), (heat_sig, el_sig))
        self.assertEqual(self.env["td.bms.heat.balance"]._td_bms_link_optional(), {})

    def test_chp_heat_in_live_balance(self):
        heat_sig, el_sig = self.new_signals(heat_kw=0.0, el_kw=0.0)
        b = self.balance
        live = b._td_bms_live()  # КГУ зупинено: сигнал тепла = 0 → у балансі 0, не проєктні 497
        self.assertEqual((live["chp_heat_now_kw"], live["chp_source"]), (0.0, "signal"))
        self.assertEqual(live["boil"], live["need"])  # усе тепло — від котлів
        heat_sig.sudo().write({"last_value": 700.0})
        el_sig.sudo().write({"last_value": 800.0})
        live = b._td_bms_live()  # КГУ працює: тепло КГУ вичитається з потреби
        self.assertEqual((live["chp_heat_now_kw"], live["chp_source"]), (700.0, "signal"))
        self.assertAlmostEqual(live["boil"], max(0.0, live["need"] - 700.0))
        self.assertEqual(b.sudo().chp_heat_now_kw, 700.0)
        heat_sig.sudo().write({"status": "stale"})  # немає сигналу тепла — за електричною потужністю (R-15 п. 2)
        live = b._td_bms_live()
        self.assertEqual((live["chp_heat_now_kw"], live["chp_source"]), (856.0, "calc"))
        el_sig.sudo().write({"last_value": 0.0})  # зупинена КГУ без сигналу тепла: 0, а не проєктні 497
        live = b._td_bms_live()
        self.assertEqual((live["chp_heat_now_kw"], live["chp_source"]), (0, "calc"))
