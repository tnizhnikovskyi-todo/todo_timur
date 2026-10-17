from odoo import fields, models


class F3dTerm(models.Model):
    _name = 'f3d.term'
    _description = "Довідник конструктора"
    _order = 'term_type, sequence, id'
    _rec_name = 'name'

    term_type = fields.Selection(
        [('layer_kind', "Вид шару"), ('slot_type', "Тип місця")], string="Довідник", required=True, index=True)
    key = fields.Char(
        string="Ключ", size=32, required=True,
        help="Збігається зі значенням f3d.layer.kind / f3d.slot.template")
    name = fields.Char(string="Назва", required=True, translate=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _f3d_term_key_uniq = models.Constraint(
        'UNIQUE(term_type, key)', "Ключ довідника має бути унікальним у межах типу.")
