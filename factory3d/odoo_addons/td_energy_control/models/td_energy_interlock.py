"""M-32 td.energy.interlock. Каркас W2-0; реалізація — A."""

from odoo import models


class TdEnergyInterlock(models.Model):
    _name = "td.energy.interlock"
    _description = "Блокування"
