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


class SaleOrder(models.Model):
    _inherit = "sale.order"

    td_width = fields.Integer(string="Width, mm")
    td_depth = fields.Integer(string="Depth, mm")
    td_total_text = fields.Char(compute="_compute_t")
    td_line_ids = fields.One2many("td.x", "id")


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    td_line_cost = fields.Float(compute="_compute_c")  # регрес 0.4.2: поле рядка у xpath order_line/list не вимагається на sale.order


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
