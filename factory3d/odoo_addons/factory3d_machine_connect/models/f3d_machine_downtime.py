import logging

from odoo import models

_logger = logging.getLogger(__name__)


class F3dMachineDowntime(models.Model):
    """M-01 (`_inherit = "f3d.machine"`): простої, підказки, заявки ТО (R-05…R-08). Власник — W2.

    Перевизначення гачків `_f3d_after_commit`, `_f3d_tick_extra`, `_f3d_apply_event` — через `super()` першим.
    """

    _inherit = "f3d.machine"
