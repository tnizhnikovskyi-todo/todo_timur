"""M-39 td.energy.control.state. Каркас W2-0; реалізація — A."""

from odoo import models


class TdEnergyControlState(models.Model):
    _name = "td.energy.control.state"
    _description = "Стан керування"
