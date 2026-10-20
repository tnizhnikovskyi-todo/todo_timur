"""Форма «Собівартість замовлення» (R-07): тимчасовий запис, що створюється при відкритті й рахується заново."""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from ..tools import cost

LEVELS = [("ok", "У нормі"), ("warn", "Увага"), ("alert", "Перевитрата"), ("none", "—")]
ARTICLE_NAMES = {
    "machine": "Верстати",
    "energy": "Енергія",
    "material": "Матеріали",
    "waste": "Відходи",
}
COST_GROUPS = "sales_team.group_sale_manager,td_factory3d.group_td_manager"


class TdSaleCost(models.TransientModel):
    _name = "td.sale.cost"
    _description = "Собівартість замовлення"

    order_id = fields.Many2one("sale.order", string="Замовлення", required=True, readonly=True, ondelete="cascade")
    currency_id = fields.Many2one("res.currency", string="Валюта", readonly=True)
    calc_at = fields.Datetime(string="Розраховано", readonly=True)
    mo_count = fields.Integer(string="МО", readonly=True)
    progress_pct = fields.Float(string="Виконання, %", digits=(5, 1), readonly=True)
    price = fields.Monetary(string="Ціна замовлення (без ПДВ)", readonly=True)
    plan_cost = fields.Monetary(string="Собівартість: план", readonly=True)
    plan_now_cost = fields.Monetary(string="План на поточний стан", readonly=True)
    fact_cost = fields.Monetary(string="Собівартість: факт", readonly=True)
    forecast_cost = fields.Monetary(string="Прогноз на завершення", readonly=True)
    dev_pct = fields.Float(string="Відхилення факту від плану, %", digits=(6, 1), readonly=True)
    has_dev = fields.Boolean(readonly=True)
    level = fields.Selection(LEVELS, string="Оцінка", readonly=True)
    margin_plan = fields.Monetary(string="Маржа: план", readonly=True)
    margin_fact = fields.Monetary(string="Маржа: факт", readonly=True)
    margin_forecast = fields.Monetary(string="Маржа: прогноз", readonly=True)
    margin_plan_pct = fields.Float(string="Маржа план, %", digits=(6, 1), readonly=True)
    margin_fact_pct = fields.Float(string="Маржа факт, %", digits=(6, 1), readonly=True)
    margin_forecast_pct = fields.Float(string="Маржа прогноз, %", digits=(6, 1), readonly=True)
    warnings = fields.Text(string="Дані й припущення", readonly=True)
    article_line_ids = fields.One2many(
        "td.sale.cost.line", "cost_id", string="За статтями", domain=[("kind", "=", "article")], readonly=True
    )
    mo_line_ids = fields.One2many(
        "td.sale.cost.line", "cost_id", string="За МО", domain=[("kind", "=", "mo")], readonly=True
    )

    @api.depends("order_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "Собівартість %s" % (rec.order_id.name or "")

    @api.model
    def _td_check_access(self):
        if not self.env.su and not self.env.user.has_group("td_factory3d.group_td_manager"):
            if not self.env.user.has_group("sales_team.group_sale_manager"):
                raise AccessError(_("Собівартість замовлень бачать керівник продажів і менеджер «Завод 3D»."))

    @api.model
    def _td_open(self, order):
        """Створити форму для замовлення: розрахунок «наживо» на момент виклику."""
        self._td_check_access()
        rec = self.sudo().create({"order_id": order.id})
        rec._td_fill()
        return rec.sudo(False)

    def _td_fill(self):
        """Порахувати заново й записати підсумки та рядки (також для кнопки «Оновити»)."""
        self.ensure_one()
        order = self.order_id
        res = self.env["td.sale.cost.calc"]._td_calc(order).get(order.id)
        self._td_lines().unlink()
        if not res:
            self.write(
                {
                    "mo_count": 0,
                    "calc_at": fields.Datetime.now(),
                    "warnings": _("У замовлення немає виробничих замовлень (МО) — собівартість не розраховується."),
                }
            )
            return
        vals = {
            "currency_id": res["currency"].id,
            "calc_at": fields.Datetime.now(),
            "mo_count": len(res["mos"]),
            "progress_pct": res["progress"] * 100.0,
            "price": res["price"],
            "plan_cost": res["plan_cost"],
            "plan_now_cost": res["plan_now_cost"],
            "fact_cost": res["fact_cost"],
            "forecast_cost": res["forecast_cost"],
            "has_dev": res["dev_pct"] is not None,
            "dev_pct": res["dev_pct"] or 0.0,
            "level": res["level"],
            "warnings": self._td_warnings(res),
        }
        for key in ("plan", "fact", "forecast"):
            vals["margin_" + key] = res["margin_" + key]
            vals["margin_%s_pct" % key] = res["margin_%s_pct" % key] or 0.0
        self.write(vals)
        lines = [self._td_article_vals(a, res["articles"][a], res, i) for i, a in enumerate(cost.ARTICLES)]
        lines += [self._td_mo_vals(d, i) for i, d in enumerate(res["mos"])]
        self.env["td.sale.cost.line"].sudo().create([{"cost_id": self.id, **v} for v in lines])

    def _td_lines(self):
        return self.env["td.sale.cost.line"].sudo().search([("cost_id", "in", self.ids)])

    @api.model
    def _td_warnings(self, res):
        out = []
        for a in cost.ARTICLES:
            if res["articles"][a]["notes"]:
                out.append("%s: %s" % (ARTICLE_NAMES[a], "; ".join(res["articles"][a]["notes"])))
        if res["progress"] < 1.0:
            out.append(
                _(
                    "Замовлення виконано на %.0f %%: факт неповний, тож його порівнюють із планом на поточний стан "
                    "(план × виконання операцій; матеріали — за взятими позиціями), а не з повним планом.",
                    res["progress"] * 100.0,
                )
            )
        return "\n".join(out)

    @api.model
    def _td_article_vals(self, article, art, res, seq):
        has_fact = art["fact"] is not None
        return {
            "kind": "article",
            "sequence": seq,
            "name": ARTICLE_NAMES[article],
            "plan": cost.num(art["plan"]),
            "plan_now": cost.num(art["plan_now"]),
            "fact": cost.num(art["fact"]),
            "has_plan": art["plan"] is not None,
            "has_fact": has_fact,
            "note": "; ".join(art["notes"]),
            **self._td_dev_vals(art["fact"], art["plan_now"]),
        }

    @api.model
    def _td_mo_vals(self, d, seq):
        mo = d["mo"]
        return {
            "kind": "mo",
            "sequence": seq,
            "name": mo.name,
            "production_id": mo.id,
            "mo_state": mo.state,
            "progress_pct": d["progress"] * 100.0,
            "plan": d["plan_cost"],
            "plan_now": d["plan_now_cost"],
            "fact": d["fact_cost"],
            "has_plan": True,
            "has_fact": True,
            "fact_machine": cost.num(d["fact"]["machine"]),
            "fact_energy": cost.num(d["fact"]["energy"]),
            "fact_material": cost.num(d["fact"]["material"]),
            "fact_waste": cost.num(d["fact"]["waste"]),
            "dev_pct": d["dev_pct"] or 0.0,
            "has_dev": d["dev_pct"] is not None,
            "deviation": d["fact_cost"] - d["plan_now_cost"],
            "level": d["level"],
            "note": _("підпорядковане: %s", d["parent"].name) if d["parent"] else "",
        }

    @api.model
    def _td_dev_vals(self, fact, plan_now):
        warn, alert = self.env["td.sale.cost.calc"]._td_thresholds()
        dev = cost.deviation_pct(fact, plan_now)
        return {
            "deviation": cost.num(fact) - cost.num(plan_now),
            "dev_pct": dev or 0.0,
            "has_dev": dev is not None,
            "level": cost.level(fact, plan_now, warn, alert) if fact is not None else "none",
        }

    def action_refresh(self):
        """Кнопка «Оновити»: розрахунок заново, форма перечитується."""
        self._td_check_access()
        for rec in self:
            rec.sudo()._td_fill()
        return True

    def action_open_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "res_id": self.order_id.id,
            "view_mode": "form",
        }


class TdSaleCostLine(models.TransientModel):
    _name = "td.sale.cost.line"
    _description = "Собівартість замовлення: рядок"
    _order = "kind, sequence, id"

    cost_id = fields.Many2one("td.sale.cost", required=True, ondelete="cascade", index=True)
    currency_id = fields.Many2one("res.currency", related="cost_id.currency_id")
    kind = fields.Selection([("article", "Стаття"), ("mo", "МО")], required=True)
    sequence = fields.Integer()
    name = fields.Char(string="Назва")
    production_id = fields.Many2one("mrp.production", string="МО", ondelete="set null")
    mo_state = fields.Selection(
        [
            ("draft", "Чернетка"),
            ("confirmed", "Підтверджено"),
            ("progress", "У роботі"),
            ("to_close", "До закриття"),
            ("done", "Виконано"),
            ("cancel", "Скасовано"),
        ],
        string="Стан",
    )
    progress_pct = fields.Float(string="Викон., %", digits=(5, 1))
    plan = fields.Monetary(string="План")
    plan_now = fields.Monetary(string="План на зараз")
    fact = fields.Monetary(string="Факт")
    deviation = fields.Monetary(string="Відх.")
    dev_pct = fields.Float(string="Відх., %", digits=(6, 1))
    has_plan = fields.Boolean()
    has_fact = fields.Boolean()
    has_dev = fields.Boolean()
    level = fields.Selection(LEVELS, string="Оцінка")
    fact_machine = fields.Monetary(string="Верстати")
    fact_energy = fields.Monetary(string="Енергія")
    fact_material = fields.Monetary(string="Матеріали")
    fact_waste = fields.Monetary(string="Відходи")
    note = fields.Char(string="Джерело й примітка")
