"""M-11 `res.config.settings` — розширення (W3-A). Каркас: поля `td_energy_resources_*` — воркер A."""

from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"
