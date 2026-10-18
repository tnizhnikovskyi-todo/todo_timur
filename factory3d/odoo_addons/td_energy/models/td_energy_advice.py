"""W1-A: M-26 `td.energy.advice` — слот рекомендацій (W1_SPEC M-26, R-32, API-11). Каркас: наповнює W1-A."""

from odoo import models


class TdEnergyAdvice(models.Model):
    _name = "td.energy.advice"
    _description = "Енергетика: рекомендація"
