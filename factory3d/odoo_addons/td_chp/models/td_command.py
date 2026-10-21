"""M-05: зворотний хук `td.command` → `td.chp.command` (R-08 п.5) і заборона сторонніх команд `origin='chp'`."""

from odoo import _, api, models
from odoo.exceptions import UserError


class TdCommand(models.Model):
    _inherit = "td.command"

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("td_chp_internal"):
            for vals in vals_list:
                if vals.get("origin") == "chp":
                    raise UserError(_("Команди КГУ створює лише модуль «Когенерація»."))
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if "state" in vals:
            chp = self.filtered(lambda c: c.origin == "chp")
            if chp:
                self.env["td.chp.command"].sudo()._td_on_command(chp)
        return res
