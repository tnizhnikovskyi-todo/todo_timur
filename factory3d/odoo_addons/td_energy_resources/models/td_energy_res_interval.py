"""M-06 `td.energy.res.interval` (W3-A). Каркас: поля й методи — воркер A."""

from odoo import models


class TdEnergyResInterval(models.Model):
    _name = "td.energy.res.interval"
    _description = "Енергетика: 15-хвилинний інтервал ресурсу"
