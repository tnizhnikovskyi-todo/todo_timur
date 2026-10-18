"""W1-C: M-10 розширення `td.energy.dashboard` (хуки генерації й фактів ДГУ; W1_SPEC B.2). Каркас."""

from odoo import models


class TdEnergyDashboard(models.AbstractModel):
    _inherit = "td.energy.dashboard"
