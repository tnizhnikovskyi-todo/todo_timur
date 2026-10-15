import logging

from odoo import models

_logger = logging.getLogger(__name__)


class MaintenanceRequest(models.Model):
    """M-28: заявка з тривоги верстата (R-08). Власник — W2."""

    _inherit = "maintenance.request"
