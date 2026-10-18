from odoo import fields, models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    td_partner_id = fields.Many2one(
        "res.partner", string="Контрагент-перевізник", domain="[('is_company','=',True)]", ondelete="set null"
    )
