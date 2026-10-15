import logging

from odoo import models

_logger = logging.getLogger(__name__)


class F3dMachineWo(models.Model):
    """M-01 (`_inherit = "f3d.machine"`): автостарт, пауза, лічильник, завершення (R-09…R-12). Власник — W3.

    Перевизначення гачків `_f3d_on_count`, `_f3d_on_job`, `_f3d_after_commit`, `_f3d_tick_extra`,
    `_f3d_apply_event` — через `super()` першим.
    """

    _inherit = "f3d.machine"
