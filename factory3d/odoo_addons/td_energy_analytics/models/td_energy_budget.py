"""M-07 `td.energy.budget` — бюджет енергії (W4-A). Каркас: поля — за SPEC; обмеження, індекс `init()`, `action_approve`
(заглушка для кнопки V-07), `get_status` — воркер A (замінює файл цілком)."""

from odoo import fields, models

COST = "td_energy.group_td_energy_cost"


class TdEnergyBudget(models.Model):
    _name = "td.energy.budget"
    _description = "Енергетика: бюджет"
    _inherit = ["mail.thread"]
    _order = "month desc, resource_id"

    month = fields.Date(string="Місяць", required=True, index=True)
    resource_id = fields.Many2one("td.energy.resource", string="Ресурс")
    amount_uah = fields.Float(string="Бюджет, ₴", digits=(14, 2), required=True, groups=COST)
    amount_qty = fields.Float(string="Бюджет, од. ресурсу", digits=(14, 2))
    state = fields.Selection(
        [("draft", "Чернетка"), ("approved", "Затверджено")], string="Стан", default="draft", tracking=True
    )
    approved_by = fields.Many2one("res.users", string="Затвердив", readonly=True)
    approved_at = fields.Datetime(string="Затверджено", readonly=True)
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)
    note = fields.Char(string="Примітка", size=256)

    def action_approve(self):
        raise NotImplementedError("W4-A: R-06")
