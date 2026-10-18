"""M-09 `td.energy.opportunity.rule` — правило резерву (W3-B). Каркас: `company_id` потрібен record rule (SPEC 4.3);
решту полів і методи пише воркер B."""

from odoo import fields, models


class TdEnergyOpportunityRule(models.Model):
    _name = "td.energy.opportunity.rule"
    _description = "Енергетика: правило резерву економії"

    company_id = fields.Many2one("res.company", string="Компанія", default=lambda self: self.env.company)
