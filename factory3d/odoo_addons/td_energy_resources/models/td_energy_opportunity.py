"""M-10 `td.energy.opportunity` — резерв економії (W3-B). Каркас: `company_id` потрібен record rule (SPEC 4.3);
решту полів і методи пише воркер B."""

from odoo import fields, models


class TdEnergyOpportunity(models.Model):
    _name = "td.energy.opportunity"
    _description = "Енергетика: резерв економії"
    _inherit = ["mail.thread"]

    company_id = fields.Many2one("res.company", string="Компанія", default=lambda self: self.env.company)
