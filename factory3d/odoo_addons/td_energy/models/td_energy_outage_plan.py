"""W1-A: M-25 `td.energy.outage.plan` — планове відключення (W1_SPEC M-25, R-31, API-09/10). Каркас: наповнює W1-A."""

from odoo import models


class TdEnergyOutagePlan(models.Model):
    _name = "td.energy.outage.plan"
    _description = "Енергетика: планове відключення"
