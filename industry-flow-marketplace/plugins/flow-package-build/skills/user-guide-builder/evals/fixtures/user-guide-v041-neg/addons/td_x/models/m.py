from odoo import models, _
from odoo.exceptions import UserError, AccessError, ValidationError


class M(models.Model):
    _name = "td.x"

    def action_send_bas(self):
        url = self.env["ir.config_parameter"].sudo().get_param("td_x.bas_url")
        if not url:
            raise UserError(_("Upload the file first."))
        if not self.env.user.has_group("td_x.group_td_finance"):
            raise AccessError(_("Only the finance role runs the exchange."))

    def more(self):
        raise UserError(_("Order {} is locked.").format(self.id))
        raise UserError(f"Stock {self.id} is negative.")
        raise ValidationError(_("Name is required.") if self.id else _("Other."))
        msg = _("No rights for %s") % self.id
        raise UserError(msg)
        raise UserError(self.dyn())
