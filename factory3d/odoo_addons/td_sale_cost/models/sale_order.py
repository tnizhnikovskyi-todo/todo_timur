"""Смарт-кнопка «Собівартість» і колонки маржі в замовленні продажу (R-07). Нічого не зберігається.

У роботі головна — «маржа прогноз», виконане — «маржа факт» (див. `_td_cost_label`)."""

from odoo import api, fields, models
from odoo.tools.misc import formatLang

from .td_sale_cost import COST_GROUPS


class SaleOrder(models.Model):
    _inherit = "sale.order"

    td_cost_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_id", string="Валюта собівартості"
    )
    td_cost_plan = fields.Monetary(
        string="Собівартість: план",
        compute="_compute_td_cost",
        currency_field="td_cost_currency_id",
        groups=COST_GROUPS,
    )
    td_cost_fact = fields.Monetary(
        string="Собівартість: факт",
        compute="_compute_td_cost",
        currency_field="td_cost_currency_id",
        groups=COST_GROUPS,
    )
    td_margin_plan_pct = fields.Float(
        string="Маржа план, %", compute="_compute_td_cost", digits=(6, 1), aggregator=None, groups=COST_GROUPS
    )
    td_margin_fact_pct = fields.Float(
        string="Маржа факт (поки що), %",
        compute="_compute_td_cost",
        digits=(6, 1),
        aggregator=None,
        groups=COST_GROUPS,
        help="(ціна − витрати до зараз) / ціна: поки замовлення в роботі, це завищена цифра: див. «Маржа прогноз».",
    )
    td_margin_forecast_pct = fields.Float(
        string="Маржа прогноз, %",
        compute="_compute_td_cost",
        digits=(6, 1),
        aggregator=None,
        groups=COST_GROUPS,
        help="(ціна − прогноз на завершення) / ціна: факт плюс решта плану. Виконане замовлення — як факт.",
    )
    td_cost_level = fields.Selection(
        [("ok", "У нормі"), ("warn", "Увага"), ("alert", "Перевитрата"), ("none", "—")],
        string="Оцінка собівартості",
        compute="_compute_td_cost",
        groups=COST_GROUPS,
    )
    td_cost_label = fields.Char(string="Собівартість", compute="_compute_td_cost", groups=COST_GROUPS)

    def _compute_td_cost(self):
        """Живий розрахунок за пов'язаними МО (R-01); замовлення без МО — порожньо, кнопка схована."""
        results = self.env["td.sale.cost.calc"]._td_calc(self.filtered("id"))  # незбережені (NewId) — без МО
        for order in self:
            res = results.get(order.id)
            if not res:
                order.td_cost_plan = order.td_cost_fact = order.td_margin_plan_pct = 0.0
                order.td_margin_fact_pct = order.td_margin_forecast_pct = 0.0
                order.td_cost_level = "none"
                order.td_cost_label = False
                continue
            order.td_cost_plan = res["plan_cost"]
            order.td_cost_fact = res["fact_cost"]
            order.td_margin_plan_pct = res["margin_plan_pct"] or 0.0
            order.td_margin_fact_pct = res["margin_fact_pct"] or 0.0
            order.td_margin_forecast_pct = res["margin_forecast_pct"] or 0.0
            order.td_cost_level = res["level"]
            order.td_cost_label = self._td_cost_label(res)

    @api.model
    def _td_cost_label(self, res):
        """Виконане: «Собівартість: факт N ₴ · маржа факт M %». У роботі: «Собівартість: факт N ₴ · маржа прогноз M %
        (факт K %)» — маржа за фактом «поки що» не видається за підсумок."""
        symbol = res["currency"].symbol or ""

        def pct(value):
            return "—" if value is None else "%s %%" % formatLang(self.env, value, digits=1)

        head = "Собівартість: факт %s %s" % (formatLang(self.env, res["fact_cost"], digits=0), symbol)
        if res["is_done"]:
            return "%s · маржа факт %s" % (head, pct(res["margin_fact_pct"]))
        return "%s · маржа прогноз %s (факт %s)" % (head, pct(res["margin_forecast_pct"]), pct(res["margin_fact_pct"]))

    def action_td_sale_cost(self):
        """Смарт-кнопка: відкрити форму розбивки (розрахунок заново при кожному відкритті)."""
        self.ensure_one()
        rec = self.env["td.sale.cost"]._td_open(self)
        return {
            "type": "ir.actions.act_window",
            "name": rec.display_name,
            "res_model": "td.sale.cost",
            "res_id": rec.id,
            "view_mode": "form",
            "target": "current",
        }
