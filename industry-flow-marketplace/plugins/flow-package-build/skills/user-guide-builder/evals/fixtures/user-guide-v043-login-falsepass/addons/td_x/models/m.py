from odoo import models, _
from odoo.exceptions import UserError, AccessError


class M(models.Model):
    _name = "td.x"

    def action_send_bas(self):
        url = self.env["ir.config_parameter"].sudo().get_param("td_x.bas_url")
        if not url:
            raise UserError(_("Upload the file first."))
        if not self.env.user.has_group("td_x.group_td_finance"):
            raise AccessError(_("Only the finance role runs the exchange."))
