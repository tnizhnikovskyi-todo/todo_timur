"""M-01 `td.energy.area` (ділянка) і M-11 `td.energy.node.area_id` (W4-A)."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TdEnergyArea(models.Model):
    _name = "td.energy.area"
    _description = "Енергетика: ділянка"
    _order = "sequence, id"

    code = fields.Char(string="Код", size=16, required=True, index=True)
    name = fields.Char(string="Назва", size=64, required=True)
    sequence = fields.Integer(default=10)
    color = fields.Char(string="Колір", size=7, required=True)
    active = fields.Boolean(default=True)
    spec_driver_id = fields.Many2one(
        "td.energy.driver", string="Драйвер питомого показника", ondelete="set null",
        help="Порожньо — питомий показник «—» (освітлення й офіс).",
    )  # fmt: skip
    node_ids = fields.One2many("td.energy.node", "area_id", string="Вузли", readonly=True)
    node_count = fields.Integer(string="Вузлів", compute="_compute_node_count")

    _code_uniq = models.Constraint("UNIQUE(code)", "Код ділянки має бути унікальним.")

    @api.depends("node_ids")
    def _compute_node_count(self):
        groups = self.env["td.energy.node"].with_context(active_test=False)._read_group(
            [("area_id", "in", self.ids)], ["area_id"], ["__count"]
        )  # fmt: skip
        counts = {area.id: count for area, count in groups}
        for area in self:
            area.node_count = counts.get(area.id, 0)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used(self):
        used = self.env["td.energy.node"].with_context(active_test=False).sudo().search_count(
            [("area_id", "in", self.ids)]
        )  # fmt: skip
        if used:
            raise UserError(_("Ділянка використовується вузлами."))


class TdEnergyNode(models.Model):
    _inherit = "td.energy.node"

    area_id = fields.Many2one("td.energy.area", string="Ділянка", index=True, ondelete="set null")
