import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class F3dCutPlanImportWizard(models.TransientModel):
    """M-25: імпорт плану (ручний режим). Методи (`action_import`) — W6."""

    _name = "f3d.cut.plan.import.wizard"
    _description = "Розкрій: імпорт плану"

    map_id = fields.Many2one("f3d.cut.map", required=True, readonly=True)
    file = fields.Binary(required=True)
    filename = fields.Char()
