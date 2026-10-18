"""M-04 `td.energy.meter` — розширення (W3-A). Каркас: поля, constraint, `_f3d_update_state` — воркер A."""

from odoo import models


class TdEnergyMeter(models.Model):
    _inherit = "td.energy.meter"
