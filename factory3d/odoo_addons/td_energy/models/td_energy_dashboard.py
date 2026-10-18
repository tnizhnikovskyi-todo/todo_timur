"""W1-A: M-27 `td.energy.dashboard` — API Пульту, картки, мобільного, генерації (W1_SPEC M-27). Каркас."""

from odoo import models


class TdEnergyDashboard(models.AbstractModel):
    _name = "td.energy.dashboard"
    _description = "Енергетика: дані Пульту"
