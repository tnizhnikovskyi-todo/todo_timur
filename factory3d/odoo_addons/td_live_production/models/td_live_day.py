from odoo import api, fields, models


class TdLiveDay(models.Model):
    """Доба живого виробництва: замовлення, МО й плановані простої, згенеровані планувальником."""

    _name = "td.live.day"
    _description = "Живе виробництво: доба"
    _order = "date desc, id desc"
    _rec_name = "date"

    date = fields.Date(string="Доба", required=True, index=True, readonly=True)
    company_id = fields.Many2one(
        "res.company", string="Компанія", required=True, default=lambda s: s.env.company, index=True, readonly=True
    )
    currency_id = fields.Many2one("res.currency", related="company_id.currency_id")
    order_ids = fields.One2many("sale.order", "td_live_day_id", string="Замовлення", readonly=True)
    production_ids = fields.One2many("mrp.production", "td_live_day_id", string="Виробничі замовлення", readonly=True)
    downtime_ids = fields.One2many("td.live.downtime", "day_id", string="Плановані простої", readonly=True)
    order_count = fields.Integer(compute="_compute_counts")
    production_count = fields.Integer(compute="_compute_counts")
    state = fields.Selection(
        [("planned", "Заплановано"), ("running", "Виконується"), ("done", "Завершено")],
        compute="_compute_state",
        store=True,
        string="Стан",
    )
    revenue = fields.Monetary(string="Виручка (план)", currency_field="currency_id", readonly=True)
    cost_plan = fields.Monetary(string="Собівартість (план)", currency_field="currency_id", readonly=True)
    margin_plan_pct = fields.Float(string="Маржа план, %", digits=(5, 1), readonly=True)
    hot_section = fields.Char(string="Перевантажена ділянка", readonly=True)
    hot_load_pct = fields.Float(
        string="Завантаження ділянки (план), %",
        digits=(7, 0),
        readonly=True,
        help="Заплановані хвилини ділянки / (верстатів × зміна). Понад 100 % — черга.",
    )
    spill_min = fields.Float(string="Переноситься на наступну зміну, хв", digits=(9, 0), readonly=True)
    note = fields.Text(string="Підсумок генерації", readonly=True)

    _td_live_day_uniq = models.Constraint("UNIQUE(date, company_id)", "Для цієї доби вже є план живого виробництва.")

    @api.depends("production_ids.state")
    def _compute_state(self):
        for rec in self:
            states = rec.production_ids.mapped("state")
            if not states or all(s == "cancel" for s in states):
                rec.state = "planned"
            elif all(s in ("done", "cancel") for s in states):
                rec.state = "done"
            elif any(s in ("progress", "to_close", "done") for s in states):
                rec.state = "running"
            else:
                rec.state = "planned"

    @api.depends("order_ids", "production_ids")
    def _compute_counts(self):
        for rec in self:
            rec.order_count = len(rec.order_ids)
            rec.production_count = len(rec.production_ids)

    def action_open_orders(self):
        self.ensure_one()
        return self._td_act("sale.order", "Замовлення доби", [("td_live_day_id", "=", self.id)])

    def action_open_productions(self):
        self.ensure_one()
        return self._td_act("mrp.production", "Виробничі замовлення доби", [("td_live_day_id", "=", self.id)])

    def _td_act(self, model, name, domain):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "domain": domain,
        }


class TdLiveDowntime(models.Model):
    """Запланований простій верстата: диспетчер відкриває його в свій час і закриває за тривалістю."""

    _name = "td.live.downtime"
    _description = "Живе виробництво: запланований простій"
    _order = "plan_start, id"

    day_id = fields.Many2one("td.live.day", string="Доба", required=True, ondelete="cascade", index=True)
    workcenter_id = fields.Many2one("mrp.workcenter", string="Робочий центр", required=True, index=True)
    kind = fields.Selection(
        [("setup", "Налагодження"), ("idle", "Очікування"), ("fault", "Аварія")], string="Стан верстата", required=True
    )
    reason = fields.Char(string="Ключ причини", required=True)
    loss_id = fields.Many2one("mrp.workcenter.productivity.loss", string="Причина", ondelete="set null")
    plan_start = fields.Datetime(string="Плановий початок", required=True, index=True)
    minutes = fields.Float(string="Тривалість, хв", required=True)
    state = fields.Selection(
        [("planned", "Заплановано"), ("active", "Триває"), ("done", "Завершено"), ("skipped", "Пропущено")],
        string="Стан",
        default="planned",
        required=True,
        index=True,
    )
    date_start = fields.Datetime(string="Початок (факт)")
    date_end = fields.Datetime(string="Кінець (факт)")
    downtime_id = fields.Many2one("td.downtime", string="Простій верстата", ondelete="set null")
    owned = fields.Boolean(
        string="Простій створив диспетчер",
        help="Лише такий простій диспетчер закриває сам; простій, відкритий станом верстата, закриває верстат.",
    )


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    td_live_day_id = fields.Many2one(
        "td.live.day", string="Доба живого виробництва", copy=False, index=True, ondelete="set null"
    )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    td_live_day_id = fields.Many2one(
        "td.live.day", string="Доба живого виробництва", copy=False, index=True, ondelete="set null"
    )
