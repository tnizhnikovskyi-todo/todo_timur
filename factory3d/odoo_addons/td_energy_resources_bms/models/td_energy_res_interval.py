"""Міст: розширення `td.energy.res.interval` (W3-B, Частина II SPEC). Каркас: тіло — воркер B."""

from odoo import models


class TdEnergyResInterval(models.Model):
    _inherit = "td.energy.res.interval"
