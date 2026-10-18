"""M-35 td.energy.control (AbstractModel, API екрана). Каркас W2-0; реалізація — A."""

from odoo import models


class TdEnergyControl(models.AbstractModel):
    _name = "td.energy.control"
    _description = "API екрана «Керування»"
