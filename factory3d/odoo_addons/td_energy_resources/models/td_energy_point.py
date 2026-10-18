"""M-03 `td.energy.point` (W3-A). Каркас: поля й методи — воркер A."""

from odoo import models


class TdEnergyPoint(models.Model):
    _name = "td.energy.point"
    _description = "Енергетика: точка обліку ресурсу"
