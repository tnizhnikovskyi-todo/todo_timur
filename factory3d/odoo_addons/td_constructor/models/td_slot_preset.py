from odoo import fields, models

SLOT_PRESET_KIND_SELECTION = [('row', "Ряд"), ('section', "Секція"), ('group', "Виділене")]


class TdSlotPreset(models.Model):
    """Пресет (F09-06/07): збережена настройка ряду, секції чи виділеного; бібліотека на компанію."""

    _name = 'td.slot.preset'
    _description = "Пресет місця"
    _order = 'name, id'

    name = fields.Char(string="Назва", required=True)
    type_id = fields.Many2one('td.slot.type', string="Тип місця", ondelete='set null', index=True)
    kind = fields.Selection(SLOT_PRESET_KIND_SELECTION, string="Вид", required=True, default='row')
    data = fields.Json(string="Дані пресету", default=dict)
    company_id = fields.Many2one(
        'res.company', string="Компанія", required=True, index=True, default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)
