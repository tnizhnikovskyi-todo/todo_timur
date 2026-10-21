from datetime import datetime, timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.misc import formatLang

RATE = 600.0  # ₴/год РЦ
STD = 10.0  # ₴ за одиницю компонента
QTY = 2  # виробів у замовленні
PER = 4  # компонентів на виріб
PRICE = 5000.0  # ₴ за виріб


@tagged("post_install", "-at_install", "f3d", "f3d_sale_cost")
class TestSaleCost(TransactionCase):
    """AC-01…AC-12: собівартість замовлення за МО (план/факт, статті, МО, форма, права, живе оновлення)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        route_mto = env.ref("stock.route_warehouse0_mto")
        route_mto.active = True
        route_mfg = env.ref("mrp.route_warehouse0_manufacture")
        cls.wc = env["mrp.workcenter"].create({"name": "TSC РЦ", "costs_hour": RATE})
        cls.comp = env["product.product"].create({"name": "TSC компонент", "is_storable": True, "standard_price": STD})
        cls.prod = env["product.product"].create(
            {
                "name": "TSC виріб",
                "is_storable": True,
                "list_price": PRICE,
                "route_ids": [Command.set([route_mto.id, route_mfg.id])],
            }
        )
        env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.prod.product_tmpl_id.id,
                "product_qty": 1,
                "bom_line_ids": [Command.create({"product_id": cls.comp.id, "product_qty": PER})],
                "operation_ids": [
                    Command.create({"name": "TSC операція", "workcenter_id": cls.wc.id, "time_cycle_manual": 60})
                ],
            }
        )
        cls.partner = env["res.partner"].create({"name": "TSC клієнт"})
        cls.manager = new_test_user(env, "tsc_mgr", groups="sales_team.group_sale_manager,base.group_user")
        cls.so = cls._make_order()
        cls.mo = cls.so.mrp_production_ids
        cls.wo = cls.mo.workorder_ids

    @classmethod
    def _make_order(cls):
        so = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "order_line": [
                    Command.create({"product_id": cls.prod.id, "product_uom_qty": QTY, "price_unit": PRICE})
                ],
            }
        )
        so.action_confirm()
        return so

    def calc(self, order=None):
        order = order or self.so
        self.env.invalidate_all()
        return self.env["td.sale.cost.calc"]._td_calc(order)[order.id]

    def _log(self, minutes, wo=None, ended=True):
        wo = wo or self.wo
        start = fields.Datetime.now() - timedelta(minutes=minutes)
        return self.env["mrp.workcenter.productivity"].create(
            {
                "workorder_id": wo.id,
                "workcenter_id": wo.workcenter_id.id,
                "loss_id": self.env.ref("mrp.block_reason7").id,
                "date_start": start,
                "date_end": fields.Datetime.now() if ended else False,
            }
        )

    # --- зв'язок із МО ---------------------------------------------------------------------------------
    def test_fixture_links_mo(self):
        self.assertEqual(len(self.mo), 1, "sale_mrp створив одне МО")
        self.assertEqual(len(self.wo), 1)

    def test_no_mo_no_cost(self):
        so = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "order_line": [Command.create({"product_id": self.comp.id})]}
        )
        self.assertNotIn(so.id, self.env["td.sale.cost.calc"]._td_calc(so))
        self.assertFalse(so.td_cost_label)

    # --- план (R-01, R-02, R-04) -----------------------------------------------------------------------
    def test_plan_from_bom_and_route(self):
        res = self.calc()
        expected_min = self.wo.duration_expected
        self.assertGreater(expected_min, 0)
        arts = res["articles"]
        self.assertAlmostEqual(arts["machine"]["plan"], expected_min / 60 * RATE)
        self.assertAlmostEqual(arts["material"]["plan"], QTY * PER * STD)
        self.assertEqual(res["price"], QTY * PRICE)
        self.assertAlmostEqual(res["margin_plan"], res["price"] - res["plan_cost"])
        self.assertAlmostEqual(res["margin_plan_pct"], res["margin_plan"] / res["price"] * 100)

    # --- факт: станки (R-02) ---------------------------------------------------------------------------
    def test_fact_machine_from_time_log(self):
        self.assertEqual(self.calc()["articles"]["machine"]["fact"], 0.0)
        self._log(90)
        res = self.calc()
        self.assertAlmostEqual(res["articles"]["machine"]["fact"], 1.5 * RATE, places=1)
        self.assertIn("журнал часу", " ".join(res["articles"]["machine"]["notes"]))

    def test_open_time_log_counts_live(self):
        self._log(30, ended=False)
        self.assertAlmostEqual(self.calc()["articles"]["machine"]["fact"], 0.5 * RATE, delta=5)

    def test_zero_rate_is_flagged(self):
        self.wc.costs_hour = 0
        self._log(60)
        res = self.calc()
        self.assertEqual(res["articles"]["machine"]["fact"], 0.0)
        self.assertIn("ставка РЦ 0", " ".join(res["articles"]["machine"]["notes"]))

    def test_demo_clock_is_now_for_open_logs(self):
        """Демо-годинник (час за Києвом) — «зараз» для відкритого запису журналу, як у R-30 td_machine_connect."""
        self.env["ir.config_parameter"].set_param("td.viewer.demo_clock", "2026-10-12 10:30")
        self.env["mrp.workcenter.productivity"].create(
            {
                "workorder_id": self.wo.id,
                "workcenter_id": self.wc.id,
                "loss_id": self.env.ref("mrp.block_reason7").id,
                "date_start": datetime(2026, 10, 12, 7, 0),  # 10:00 за Києвом (UTC+3)
            }
        )
        self.assertAlmostEqual(self.calc()["articles"]["machine"]["fact"], 0.5 * RATE, places=1)

    # --- МО за origin і напівфабрикати (R-01) ----------------------------------------------------------
    def test_origin_linked_mo_and_semi_finished_rollup(self):
        env = self.env
        semi = env["product.product"].create({"name": "TSC напівфабрикат", "is_storable": True, "standard_price": 99.0})
        env["mrp.bom"].create(
            {
                "product_tmpl_id": semi.product_tmpl_id.id,
                "product_qty": 1,
                "bom_line_ids": [Command.create({"product_id": self.comp.id, "product_qty": 1})],
                "operation_ids": [
                    Command.create({"name": "TSC під-операція", "workcenter_id": self.wc.id, "time_cycle_manual": 30})
                ],
            }
        )
        top = env["product.product"].create({"name": "TSC складальний виріб", "is_storable": True})
        env["mrp.bom"].create(
            {
                "product_tmpl_id": top.product_tmpl_id.id,
                "product_qty": 1,
                "bom_line_ids": [
                    Command.create({"product_id": semi.id, "product_qty": 1}),
                    Command.create({"product_id": self.comp.id, "product_qty": 2}),
                ],
                "operation_ids": [
                    Command.create({"name": "TSC складання", "workcenter_id": self.wc.id, "time_cycle_manual": 60})
                ],
            }
        )
        so = env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [Command.create({"product_id": top.id, "product_uom_qty": 1, "price_unit": 1000.0})],
            }
        )
        parent = env["mrp.production"].create({"product_id": top.id, "product_qty": 1, "origin": so.name})
        parent.action_confirm()
        child = env["mrp.production"].create({"product_id": semi.id, "product_qty": 1, "origin": parent.name})
        child.action_confirm()
        res = self.calc(so)
        self.assertEqual(
            [d["mo"] for d in res["mos"]], [parent, child], "корінь за origin = номер замовлення, далі підМО"
        )
        self.assertEqual(res["mos"][1]["parent"], parent)
        mat = res["articles"]["material"]
        # план матеріалів: компонент батька (2 × STD) + компонент підМО (1 × STD); напівфабрикат (99) не двічі
        self.assertAlmostEqual(mat["plan"], 3 * STD)
        self.assertIn("напівфабрикати", " ".join(mat["notes"]))
        expected_min = sum((parent | child).workorder_ids.mapped("duration_expected"))
        self.assertAlmostEqual(res["articles"]["machine"]["plan"], expected_min / 60 * RATE)
        rec = env["td.sale.cost"]._td_open(so)
        self.assertEqual(rec.mo_line_ids.mapped("production_id"), parent | child)
        self.assertIn(parent.name, rec.mo_line_ids.filtered(lambda line: line.production_id == child).note)

    # --- факт: матеріали (R-04) ------------------------------------------------------------------------
    def test_materials_picked_is_estimate_not_reserved(self):
        move = self.mo.move_raw_ids
        move.write({"quantity": 3, "picked": False})
        self.assertEqual(self.calc()["articles"]["material"]["fact"], 0.0, "зарезервоване — не списання")
        move.write({"quantity": 3, "picked": True})
        res = self.calc()
        self.assertAlmostEqual(res["articles"]["material"]["fact"], 3 * STD)
        self.assertIn("standard_price", " ".join(res["articles"]["material"]["notes"]))

    def test_materials_done_uses_move_value(self):
        self.mo.move_raw_ids.write({"quantity": QTY * PER + 2, "picked": True})  # перевитрата на 2 од.
        self.mo.qty_producing = self.mo.product_qty
        self.mo.with_context(skip_consumption=True, skip_immediate=True, skip_backorder=True).button_mark_done()
        self.assertEqual(self.mo.state, "done")
        res = self.calc()
        raw = self.mo.move_raw_ids
        self.assertEqual(raw.state, "done")
        value = sum(abs(v) for v in raw.mapped("value"))
        self.assertGreater(value, 0)
        self.assertAlmostEqual(res["articles"]["material"]["fact"], value)
        self.assertAlmostEqual(res["articles"]["material"]["fact"], (QTY * PER + 2) * STD)
        self.assertGreater(res["articles"]["material"]["fact"], res["articles"]["material"]["plan"])
        self.assertEqual(res["progress"], 1.0)
        self.assertEqual(res["articles"]["material"]["plan_now"], res["articles"]["material"]["plan"])

    # --- відходи (R-05) --------------------------------------------------------------------------------
    def test_waste_no_data_then_scrap(self):
        art = self.calc()["articles"]["waste"]
        self.assertIsNone(art["fact"])
        self.assertIn("немає даних", " ".join(art["notes"]))
        scrap = self.env["stock.scrap"].create(
            {
                "product_id": self.comp.id,
                "scrap_qty": 3,
                "production_id": self.mo.id,
                "product_uom_id": self.comp.uom_id.id,
            }
        )
        self.env["stock.quant"]._update_available_quantity(self.comp, scrap.location_id, 10)
        scrap.action_validate()
        self.assertEqual(scrap.state, "done")
        art = self.calc()["articles"]["waste"]
        self.assertAlmostEqual(art["fact"], 3 * STD)

    # --- енергія і журнал станів: необов'язкові частини ------------------------------------------------
    def test_energy_optional(self):
        art = self.calc()["articles"]["energy"]
        self.assertIsNone(art["fact"])
        if "td.energy.alloc" not in self.env:
            self.assertIn("не встановлено", " ".join(art["notes"]))
            return
        self.assertIn("немає даних", " ".join(art["notes"]))
        self.env["td.energy.alloc"].create(
            [
                {
                    "day": fields.Date.today(),
                    "kind": kind,
                    "workorder_id": self.wo.id,
                    "workcenter_id": self.wc.id,
                    "kwh": kwh,
                    "minutes": 30,
                    "cost": amount,
                }
                for kind, kwh, amount in (("direct", 10.0, 45.0), ("shared", 40.0, 360.0), ("idle", 2.0, 9.0))
            ]
        )
        res = self.calc()
        # прямі рядки входять, спільні (цеховий пул) — накладні, idle — не завдання; спільні — лише в нотатці
        self.assertAlmostEqual(res["articles"]["energy"]["fact"], 45.0)
        self.assertIn("не входить", " ".join(res["articles"]["energy"]["notes"]))
        # план енергії: плановий час × історичні ₴/год роботи РЦ (45 ₴ за 30 хв прямого часу = 90 ₴/год)
        self.assertAlmostEqual(res["articles"]["energy"]["plan"], self.wo.duration_expected / 60 * 90.0)
        self.assertGreater(res["fact_cost"], res["articles"]["machine"]["fact"])
        # параметр td.sale_cost.energy_shared = 1: спільні входять у факт, а хвилини плану лишаються прямими (не ×2)
        self.env["ir.config_parameter"].set_param("td.sale_cost.energy_shared", "1")
        res = self.calc()
        self.assertAlmostEqual(res["articles"]["energy"]["fact"], 405.0)
        self.assertAlmostEqual(res["articles"]["energy"]["plan"], self.wo.duration_expected / 60 * 810.0)

    def test_state_log_preferred_over_time_log(self):
        if "td.machine.state.log" not in self.env:
            self.skipTest("td_machine_connect не встановлено")
        machine = self.env["td.machine"].create(
            {"name": "TSC верстат", "code": "TSC-1", "workcenter_id": self.wc.id, "protocol": "manual"}
        )
        now = fields.Datetime.now()
        self.env["td.machine.state.log"].create(
            {
                "machine_id": machine.id,
                "state": "working",
                "date_start": now - timedelta(minutes=120),
                "date_end": now - timedelta(minutes=60),
                "workorder_id": self.wo.id,
            }
        )
        self._log(10)  # у журналі часу лише 10 хв, у журналі станів — 60 хв
        art = self.calc()["articles"]["machine"]
        self.assertAlmostEqual(art["fact"], 1.0 * RATE, places=1)
        self.assertIn("журнал станів верстата 60", " ".join(art["notes"]))

    # --- відхилення, колір, прогноз (R-06) -------------------------------------------------------------
    def test_deviation_level_and_forecast(self):
        self._log(30)
        res = self.calc()
        self.assertEqual(res["progress"], 30 / self.wo.duration_expected)
        self.assertAlmostEqual(res["plan_now_cost"], res["articles"]["machine"]["plan"] * res["progress"], places=4)
        self.assertEqual(res["level"], "ok")
        self.assertAlmostEqual(res["forecast_cost"], res["fact_cost"] + res["plan_cost"] - res["plan_now_cost"])
        self._log(60)  # час більший за план для 50 % прогресу
        res = self.calc()
        self.assertEqual(res["level"], "ok" if res["dev_pct"] <= 5 else res["level"])
        self.assertIn(res["level"], ("ok", "warn", "alert"))

    def test_thresholds_from_parameters(self):
        self.wo.duration_expected = 100.0
        self._log(100)
        self.mo.move_raw_ids.write({"quantity": QTY * PER, "picked": True})
        self.env["ir.config_parameter"].set_param("td.sale_cost.warn_pct", "-100")
        self.env["ir.config_parameter"].set_param("td.sale_cost.alert_pct", "-50")
        self.assertEqual(self.calc()["level"], "alert", "пороги беруться з параметрів")

    # --- форма, кнопка, список, права ------------------------------------------------------------------
    def test_smart_button_label_and_fields(self):
        self._log(60)
        so = self.so.with_user(self.manager)
        so.invalidate_recordset()
        label = so.td_cost_label
        self.assertTrue(label.startswith("Собівартість: факт"), label)
        self.assertIn("маржа", label)
        self.assertAlmostEqual(so.td_cost_fact, self.calc()["fact_cost"])
        self.assertAlmostEqual(so.td_margin_plan_pct, self.calc()["margin_plan_pct"])
        arch = self.env["sale.order"].get_view(self.env.ref("sale.view_order_form").id)["arch"]
        self.assertIn("action_td_sale_cost", arch)

    def test_forecast_margin_is_headline_while_in_progress(self):
        """Замовлення в роботі: головна — «маржа прогноз» = (ціна − факт − решта плану) / ціна; «факт» лишається."""
        self._log(30)  # 30 хв із плану: факт ≈ 300 ₴, решта плану ≈ матеріали й решта часу
        res = self.calc()
        self.assertFalse(res["is_done"])
        self.assertEqual(res["margin_main"], "forecast")
        self.assertAlmostEqual(
            res["margin_forecast_pct"], (res["price"] - res["forecast_cost"]) / res["price"] * 100.0, places=6
        )
        self.assertLess(res["margin_forecast_pct"], res["margin_fact_pct"], "факт «поки що» завищує маржу")
        so = self.so.with_user(self.manager)
        so.invalidate_recordset()
        label = so.td_cost_label
        fmt = lambda v: formatLang(self.env, v, digits=1)  # noqa: E731
        self.assertIn("маржа прогноз %s %%" % fmt(res["margin_forecast_pct"]), label)
        self.assertIn("(факт %s %%)" % fmt(res["margin_fact_pct"]), label)
        self.assertAlmostEqual(so.td_margin_forecast_pct, res["margin_forecast_pct"])
        rec = self.env["td.sale.cost"]._td_open(self.so)
        self.assertFalse(rec.is_done)
        self.assertAlmostEqual(rec.margin_forecast_pct, res["margin_forecast_pct"])
        self.assertIn("маржа прогноз", rec.warnings)

    def test_done_order_keeps_fact_margin(self):
        """Виконане замовлення: у кнопці «маржа факт», без прогнозу в дужках."""
        self._log(60)
        self.mo.write({"state": "done"})
        res = self.calc()
        self.assertTrue(res["is_done"])
        self.assertEqual(res["margin_main"], "fact")
        so = self.so.with_user(self.manager)
        so.invalidate_recordset()
        self.assertIn("маржа факт", so.td_cost_label)
        self.assertNotIn("прогноз", so.td_cost_label)

    def test_list_columns_are_optional_and_hidden(self):
        arch = self.env["sale.order"].get_view(self.env.ref("sale.view_order_tree").id)["arch"]
        self.assertRegex(arch, r'name="td_margin_fact_pct"[^>]*optional="hide"')
        self.assertRegex(arch, r'name="td_margin_forecast_pct"[^>]*optional="hide"')
        self.assertRegex(arch, r'name="td_margin_plan_pct"[^>]*optional="hide"')

    def test_unsaved_order_has_no_cost(self):
        new = self.env["sale.order"].with_user(self.manager).new({"partner_id": self.partner.id})
        self.assertFalse(new.td_cost_label)

    def test_form_has_articles_and_mos_and_refreshes(self):
        action = self.so.with_user(self.manager).action_td_sale_cost()
        rec = self.env["td.sale.cost"].browse(action["res_id"]).with_user(self.manager)
        self.assertEqual(action["res_model"], "td.sale.cost")
        self.assertEqual(rec.mo_count, 1)
        self.assertEqual(len(rec.article_line_ids), 4)
        self.assertEqual(rec.mo_line_ids.production_id, self.mo)
        self.assertEqual(rec.article_line_ids.mapped("name")[0][:7], "Верстат")
        waste = rec.article_line_ids.filtered(lambda line: line.name.startswith("Відходи"))
        self.assertFalse(waste.has_fact)
        self.assertIn("немає даних", waste.note)
        self.assertIn("немає даних", rec.warnings)
        before = rec.fact_cost
        self._log(120)
        rec.action_refresh()
        self.assertAlmostEqual(rec.fact_cost - before, 2 * RATE, places=1)
        self.assertEqual(len(rec.article_line_ids), 4, "рядки перестворені, не дублюються")
        self.assertEqual(len(rec.mo_line_ids), 1)
        self.assertAlmostEqual(rec.mo_line_ids.fact_machine, 2 * RATE, places=1)

    def test_form_for_order_without_mo(self):
        so = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "order_line": [Command.create({"product_id": self.comp.id})]}
        )
        rec = self.env["td.sale.cost"]._td_open(so)
        self.assertEqual(rec.mo_count, 0)
        self.assertIn("немає виробничих", rec.warnings)

    def test_list_columns_batch_equal_single(self):
        so2 = self._make_order()
        self._log(60)
        orders = (self.so | so2).with_user(self.manager)
        orders.invalidate_recordset()
        pairs = [(o.td_margin_plan_pct, o.td_margin_fact_pct) for o in orders]
        for o, (plan, fact) in zip(orders, pairs, strict=True):
            res = self.calc(o.sudo())
            self.assertAlmostEqual(plan, res["margin_plan_pct"])
            self.assertAlmostEqual(fact, res["margin_fact_pct"])
        self.assertNotAlmostEqual(pairs[0][1], pairs[1][1], msg="у першого замовлення є час, у другого немає")

    def test_access_only_sale_manager_or_td_manager(self):
        salesman = new_test_user(self.env, "tsc_sales", groups="sales_team.group_sale_salesman,base.group_user")
        with self.assertRaises(AccessError):
            self.so.with_user(salesman).action_td_sale_cost()
        with self.assertRaises(AccessError):
            self.so.with_user(salesman).td_cost_label  # noqa: B018
        td_manager = new_test_user(
            self.env, "tsc_td", groups="td_factory3d.group_td_manager,sales_team.group_sale_salesman,base.group_user"
        )
        self.assertTrue(self.so.with_user(td_manager).td_cost_label)

    def test_auto_installed_bridge(self):
        mod = self.env["ir.module.module"].search([("name", "=", "td_sale_cost")])
        self.assertEqual(mod.state, "installed")
        self.assertTrue(mod.auto_install)
