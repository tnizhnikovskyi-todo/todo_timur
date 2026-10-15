import logging

from odoo import models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    """M-27: поповнення під портал (`_action_done`, R-18). Власник — W5."""

    _inherit = "stock.picking"
