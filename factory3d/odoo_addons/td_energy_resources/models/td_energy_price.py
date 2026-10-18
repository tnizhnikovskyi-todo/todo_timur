"""M-02 `td.energy.price` (W3-A). Каркас: поля й методи — воркер A."""

from odoo import models


class TdEnergyPrice(models.Model):
    _name = "td.energy.price"
    _description = "Енергетика: ціна ресурсу"
