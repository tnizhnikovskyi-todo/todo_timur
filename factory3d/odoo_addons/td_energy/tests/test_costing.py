"""AC-46…AC-51: енергія в собівартість МО (R-10): extra_cost, фіксація, дозамовлення, аналітика."""

from datetime import timedelta

from odoo.tests import Form, tagged

from .common import TAGS, F3DEnergyCase
from .test_alloc import AllocMixin

SPEC = [("SAW-T", 24, 0.55, 78), ("EDGE-T", 67.5, 0.65, 63), ("CNC-T", 22, 0.5, 74),
        ("SORT-T", 20, 0.45, 29), ("ASMLINE-T", 8, 0.4, 95)]  # fmt: skip


class CostingMixin(AllocMixin):
    def make_231(self, method="average", day_shift=0):
        """МО-231-Т: 26 шт, п'ять РЦ в режимі оцінки (R-08), енергія 724,18 грн. `day_shift` — інша доба."""
        categ = self.env["product.category"].create(
            {"name": "cat-%s-%s" % (method, day_shift), "property_cost_method": method}
        )
        nodes = self.nodes if getattr(self, "nodes", None) else None
        if nodes is None:
            nodes = self.nodes = [self.mk_direct(c, p, lf, meter=False) for c, p, lf, _m in SPEC]
        mo = self.mk_mo(self.env["mrp.workcenter"].concat(*[n.workcenter_id for n in nodes]), categ=categ)
        base = self.at(1) - timedelta(days=day_shift)
        for wo, (_c, _p, _lf, minutes) in zip(mo.workorder_ids.sorted("id"), SPEC, strict=True):
            self.log(wo, base, base + timedelta(minutes=minutes))
        return mo

    def close(self, mo, producing=None):
        mo.qty_producing = producing or mo.product_qty
        res = mo.with_context(skip_backorder=True).button_mark_done()
        return res


@tagged(*TAGS)
class TestCosting(CostingMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alloc_setup(days_back=3)
        cls.nodes = None

    def unit_price(self, mo):
        return mo.move_finished_ids.filtered(lambda m: m.product_id == mo.product_id).price_unit

    def test_avco_extra_cost(self):  # AC-46
        mo = self.make_231("average")
        mo.extra_cost = 0.0
        self.close(mo)
        self.assertEqual(mo.state, "done")
        self.assertAlmostEqual(mo.extra_cost, 27.8531, places=4)
        self.assertAlmostEqual(mo.td_energy_applied_unit, 27.8531, places=4)
        self.assertTrue(mo.td_energy_locked)
        self.assertTrue(all(self.Alloc.sudo().search([("production_id", "=", mo.id)]).mapped("locked")))
        texts = " ".join(mo.message_ids.mapped("body"))
        self.assertIn("До Extra Unit Cost додано енергію: 27,8531 грн/од. (724,18 грн / 26 шт).", texts)
        # той самий МО без внесення енергії (на іншу добу)
        self.env["ir.config_parameter"].sudo().set_param("td.energy.costing_enabled", "False")
        base = self.make_231("average", day_shift=1)
        self.close(base)
        self.assertAlmostEqual(self.unit_price(mo) - self.unit_price(base), 27.8531, places=3)
        self.assertAlmostEqual((self.unit_price(mo) - self.unit_price(base)) * 26, 724.18, delta=0.02)

    def test_standard_no_change(self):  # AC-47
        mo = self.make_231("standard")
        self.close(mo)
        self.assertEqual((mo.extra_cost, mo.td_energy_applied_unit), (0.0, 0.0))
        texts = " ".join(mo.message_ids.mapped("body"))
        self.assertIn("Енергію не внесено у вартість: метод «Стандартна ціна»", texts)
        self.assertTrue(mo.td_energy_locked)
        self.assertTrue(all(self.Alloc.sudo().search([("production_id", "=", mo.id)]).mapped("locked")))

    def test_costing_disabled(self):  # AC-48
        self.env["ir.config_parameter"].sudo().set_param("td.energy.costing_enabled", "False")
        mo = self.make_231("average")
        self.close(mo)
        self.assertEqual((mo.extra_cost, mo.td_energy_applied_unit), (0.0, 0.0))
        self.assertTrue(mo.td_energy_locked)
        self.assertNotIn("Extra Unit Cost", " ".join(mo.message_ids.mapped("body")))

    def test_backorder(self):  # AC-49
        mo = self.make_231("average")
        mo.extra_cost = 3.0
        mo.qty_producing = 10.0
        action = mo.button_mark_done()
        wizard = Form.from_action(self.env, action).save()
        wizard.action_backorder()
        backorder = self.env["mrp.production"].search(
            [("backorder_sequence", ">", 1), ("product_id", "=", mo.product_id.id)]
        )
        self.assertEqual(len(backorder), 1)
        self.assertAlmostEqual(backorder.extra_cost, 3.0, places=4)
        self.assertEqual(mo.state, "done")
        self.assertAlmostEqual(mo.td_energy_kwh, 86.213, places=3)
        self.assertFalse(backorder.td_energy_locked)

    def test_analytic_lines(self):  # AC-50
        plan = self.env["account.analytic.plan"].create({"name": "Plan-T"})
        account = self.env["account.analytic.account"].create({"name": "WC-T", "plan_id": plan.id})
        mo = self.make_231("average")
        saw = self.nodes[0].workcenter_id
        saw.analytic_distribution = {str(account.id): 100}
        self.close(mo)
        lines = self.env["account.analytic.line"].search([("name", "like", "[EN]%")])
        self.assertEqual(len(lines), 1, lines.mapped("name"))
        self.assertAlmostEqual(lines.amount, -144.14, places=2)
        self.assertAlmostEqual(lines.unit_amount, 17.16, places=2)
        self.assertEqual(lines.product_uom_id, self.env.ref("uom.product_uom_kwh"))
        self.assertEqual(lines.category, "manufacturing_order")
        row = self.Alloc.sudo().search(
            [("production_id", "=", mo.id), ("workcenter_id", "=", saw.id), ("kind", "=", "direct")]
        )
        self.assertEqual(row.analytic_line_ids, lines)
        mo._td_energy_analytic(row)  # повторно — без дублів
        self.assertEqual(self.env["account.analytic.line"].search_count([("name", "like", "[EN]%")]), 1)

    def test_cal_price_twice(self):  # AC-51
        mo = self.make_231("average")
        moves = self.env["stock.move"]
        mo._cal_price(moves)
        first = mo.extra_cost
        mo._cal_price(moves)
        self.assertAlmostEqual(first, 27.8531, places=4)
        self.assertEqual(mo.extra_cost, first)
        self.assertEqual(len([m for m in mo.message_ids if "До Extra Unit Cost" in (m.body or "")]), 1)
