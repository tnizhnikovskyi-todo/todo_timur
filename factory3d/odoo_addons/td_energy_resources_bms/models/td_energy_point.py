"""Міст: розширення `td.energy.point` (W3-B, Частина II SPEC). Каркас: тіло — воркер B."""

from odoo import models


class TdEnergyPoint(models.Model):
    _inherit = "td.energy.point"
