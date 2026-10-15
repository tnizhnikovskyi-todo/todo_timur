import logging

from odoo import models

_logger = logging.getLogger(__name__)


class F3dSignal(models.Model):
    """M-18: вхід показань (`_f3d_ingest`, `_mark_stale` з `super()` першим). Власник — W1."""

    _inherit = "f3d.signal"
