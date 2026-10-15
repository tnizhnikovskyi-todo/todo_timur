import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class F3dCutPartImportWizard(models.TransientModel):
    """M-26: імпорт деталей (CSV, Додаток E). Методи (`action_import`) — W6."""

    _name = "f3d.cut.part.import.wizard"
    _description = "Розкрій: імпорт деталей"

    bom_id = fields.Many2one("mrp.bom", required=True)
    file = fields.Binary(required=True)
    filename = fields.Char()
    replace = fields.Boolean(default=False, string="Замінити наявні")
