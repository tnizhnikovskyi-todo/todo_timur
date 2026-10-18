"""M-34 td.energy.schedule.slot. Каркас W2-0; реалізація — A."""

from odoo import models


class TdEnergyScheduleSlot(models.Model):
    _name = "td.energy.schedule.slot"
    _description = "Слот розкладу"
