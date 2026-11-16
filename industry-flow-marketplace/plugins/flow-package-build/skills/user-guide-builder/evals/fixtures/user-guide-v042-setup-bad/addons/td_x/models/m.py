from odoo import fields, models, _
from odoo.exceptions import UserError, AccessError


class M(models.Model):
    _name = "td.x"

    def action_send_bas(self):
        url = self.env["ir.config_parameter"].sudo().get_param("td_x.bas_url")
        if not url:
            raise UserError(_("Upload the file first."))
        if not self.env.user.has_group("td_x.group_td_finance"):
            raise AccessError(_("Only the finance role runs the exchange."))


class Mixin(models.AbstractModel):
    _name = "td.x.mixin"
    _description = "Mixin"

    td_mix = fields.Char(string="From mixin")
    td_mix_c = fields.Char(compute="_compute_m")


class SaleOrder(models.Model):
    _inherit = ["sale.order", "td.x.mixin"]

    td_width = fields.Integer(string="Width, mm")
    td_depth = fields.Integer(string="Depth, mm")
    td_total_text = fields.Char(compute="_compute_t")
    td_line_ids = fields.One2many("td.x", "id")


class Material(models.Model):
    _name = "td.x.material"
    _description = "Material"

    name = fields.Char()
    td_density = fields.Float()


class Repair(models.Model):
    _name = "td.x.repair"
    _description = "Repair"

    name = fields.Char()
    state = fields.Selection([("a", "A")])
