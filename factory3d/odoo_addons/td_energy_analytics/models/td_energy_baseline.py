"""M-04 `td.energy.baseline` — модель бази ISO 50001, M-05 `.line` (W4-A). Каркас: поля — за SPEC; `name` (compute),
обмеження, `action_fit/approve/archive/to_draft` (заглушки для кнопок V-05), `expected` — воркер A
(замінює файл цілком)."""

from odoo import fields, models


class TdEnergyBaseline(models.Model):
    _name = "td.energy.baseline"
    _description = "Енергетика: модель бази (EnPB)"
    _inherit = ["mail.thread"]
    _order = "state, period_to desc, id desc"

    name = fields.Char(string="Назва")
    resource_id = fields.Many2one("td.energy.resource", string="Ресурс", required=True)
    scope = fields.Selection([("plant", "Завод"), ("area", "Ділянка")], string="Рівень", default="plant")
    area_id = fields.Many2one("td.energy.area", string="Ділянка")
    period_from = fields.Date(string="Період з", required=True)
    period_to = fields.Date(string="Період по", required=True)
    const_per_day = fields.Float(string="Постійна складова, од./добу", digits=(14, 3))
    line_ids = fields.One2many("td.energy.baseline.line", "baseline_id", string="Драйвери")
    n_days = fields.Integer(string="Діб у підгонці", readonly=True)
    r2 = fields.Float(string="R²", readonly=True)
    rmse = fields.Float(string="RMSE", readonly=True)
    method = fields.Selection([("ols", "Регресія"), ("manual", "Вручну")], string="Метод", default="ols")
    state = fields.Selection(
        [("draft", "Чернетка"), ("approved", "Затверджено"), ("archived", "В архіві")],
        string="Стан",
        default="draft",
        tracking=True,
    )
    fitted_at = fields.Datetime(string="Розраховано", readonly=True)
    approved_at = fields.Datetime(string="Затверджено", readonly=True)
    approved_by = fields.Many2one("res.users", string="Затвердив", readonly=True)
    warning = fields.Char(string="Попередження", readonly=True)
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)
    note = fields.Text(string="Примітка")

    def action_fit(self):
        raise NotImplementedError("W4-A: R-04")

    def action_approve(self):
        raise NotImplementedError("W4-A: R-04")

    def action_archive(self):
        raise NotImplementedError("W4-A: R-04")

    def action_to_draft(self):
        raise NotImplementedError("W4-A: R-04")


class TdEnergyBaselineLine(models.Model):
    _name = "td.energy.baseline.line"
    _description = "Енергетика: рядок моделі бази"
    _order = "sequence, id"

    baseline_id = fields.Many2one("td.energy.baseline", string="Модель", required=True, ondelete="cascade")
    driver_id = fields.Many2one("td.energy.driver", string="Драйвер", required=True, ondelete="restrict")
    coef = fields.Float(string="Коефіцієнт, од. на одиницю драйвера", digits=(14, 6))
    sequence = fields.Integer(default=10)
