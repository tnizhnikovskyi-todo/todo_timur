"""M-H1 `td.energy.round.template`, M-H2 `.slot`, M-H3 `.template.item` (W4-C). Каркас: ключові поля — для ACL
і record rules; решта полів, обмеження, `UNIQUE` — воркер C (замінює файл цілком)."""

from odoo import fields, models


class TdEnergyRoundTemplate(models.Model):
    _name = "td.energy.round.template"
    _description = "Енергетика: шаблон обходу"
    _order = "sequence, id"

    name = fields.Char(string="Назва", size=64, required=True)
    code = fields.Char(string="Код", size=32, required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    slot_ids = fields.One2many("td.energy.round.slot", "template_id", string="Розклад")
    item_ids = fields.One2many("td.energy.round.template.item", "template_id", string="Пункти")
    note = fields.Text(string="Примітка")
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)


class TdEnergyRoundSlot(models.Model):
    _name = "td.energy.round.slot"
    _description = "Енергетика: слот обходу"
    _order = "sequence, id"

    template_id = fields.Many2one("td.energy.round.template", string="Шаблон", required=True, ondelete="cascade")
    name = fields.Char(string="Назва", size=32, required=True)
    time_from = fields.Float(string="З (год)", required=True)
    time_to = fields.Float(string="До (год)", required=True)
    weekdays = fields.Char(string="Дні тижня", size=13, default="0,1,2,3,4")
    sequence = fields.Integer(default=10)


class TdEnergyRoundTemplateItem(models.Model):
    _name = "td.energy.round.template.item"
    _description = "Енергетика: пункт шаблону обходу"
    _order = "sequence, id"

    template_id = fields.Many2one("td.energy.round.template", string="Шаблон", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    code = fields.Char(string="Код", size=16, required=True)
    title = fields.Char(string="Назва", size=128, required=True)
