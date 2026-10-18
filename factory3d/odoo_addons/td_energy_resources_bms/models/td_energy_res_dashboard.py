"""Міст: розширення `td.energy.res.dashboard` (W3-B, M-B2). Каркас: хуки `_td_heat_*` — воркер B."""

from odoo import models


class TdEnergyResDashboard(models.AbstractModel):
    _inherit = "td.energy.res.dashboard"
