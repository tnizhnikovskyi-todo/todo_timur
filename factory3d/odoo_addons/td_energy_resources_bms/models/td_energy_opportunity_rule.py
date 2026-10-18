"""Міст: розширення `td.energy.opportunity.rule` (W3-B, Частина II SPEC). Каркас: тіло — воркер B."""

from odoo import models


class TdEnergyOpportunityRule(models.Model):
    _inherit = "td.energy.opportunity.rule"
