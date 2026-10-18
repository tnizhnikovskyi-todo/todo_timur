"""M-05 `td.energy.tariff` — розширення (W3-A). Каркас: `tg_phi_limit`, `react_rate`, `_td_react_penalty` — воркер A."""

from odoo import models


class TdEnergyTariff(models.Model):
    _inherit = "td.energy.tariff"
