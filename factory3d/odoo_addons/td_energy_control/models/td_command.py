"""M-37 `td.command` — розширення: `energy_action_id`, зворотний хук у дію (R-40 п.6–7)."""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TdCommand(models.Model):
    _inherit = "td.command"

    energy_action_id = fields.Many2one(
        "td.energy.action", string="Дія енергетики", index=True, ondelete="set null", readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("origin") == "energy" and (
                not vals.get("energy_action_id") or not self.env.context.get("td_energy_control_internal")
            ):
                raise UserError(_("Команди енергетики створює лише модуль керування."))
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if "state" in vals:
            for cmd in self.filtered("energy_action_id"):
                cmd.energy_action_id.sudo()._td_on_command(cmd)
        return res
