"""M-H7 `res.config.settings` — параметри `td.energy_mobile.*` (W4-C). Каркас: поля `td_energy_mobile_*` — воркер C."""

from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"
