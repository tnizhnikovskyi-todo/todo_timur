"""M-01 `td.energy.area` (ділянка) і M-11 `td.energy.node.area_id` (W4-A). Каркас: поля — за SPEC; обмеження,
`node_count`, `unlink` — воркер A (замінює файл цілком)."""

from odoo import fields, models


class TdEnergyArea(models.Model):
    _name = "td.energy.area"
    _description = "Енергетика: ділянка"
    _order = "sequence, id"

    code = fields.Char(string="Код", size=16, required=True, index=True)
    name = fields.Char(string="Назва", size=64, required=True)
    sequence = fields.Integer(default=10)
    color = fields.Char(string="Колір", size=7, required=True)
    active = fields.Boolean(default=True)
    spec_driver_id = fields.Many2one("td.energy.driver", string="Драйвер питомого показника")
    node_ids = fields.One2many("td.energy.node", "area_id", string="Вузли", readonly=True)
    node_count = fields.Integer(string="Вузлів")


class TdEnergyNode(models.Model):
    _inherit = "td.energy.node"

    area_id = fields.Many2one("td.energy.area", string="Ділянка", index=True, ondelete="set null")
