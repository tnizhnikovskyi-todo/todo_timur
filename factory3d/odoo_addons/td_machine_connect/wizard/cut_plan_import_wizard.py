import base64
import json
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

from ..models.td_cut_map import STATE_LABELS
from ..tools import cutcsv

_logger = logging.getLogger(__name__)


class F3dCutPlanImportWizard(models.TransientModel):
    """M-25: імпорт плану (ручний режим)."""

    _name = "td.cut.plan.import.wizard"
    _description = "Розкрій: імпорт плану"

    map_id = fields.Many2one("td.cut.map", required=True, readonly=True)
    file = fields.Binary(required=True)
    filename = fields.Char()

    def action_import(self):
        self.ensure_one()
        cut_map = self.map_id
        if cut_map.state not in ("exported", "optimizing", "planned"):
            raise UserError(
                _("Карта %s не очікує плану (стан «%s»).", cut_map.name, STATE_LABELS.get(cut_map.state, cut_map.state))
            )
        try:
            data = json.loads(base64.b64decode(self.file).decode("utf-8"))
        except ValueError as e:  # JSONDecodeError і UnicodeDecodeError — підкласи ValueError
            raise UserError(_("Файл плану: невалідний JSON (%s).", e)) from e
        try:
            plan = cutcsv.parse_plan(data)
        except ValueError as e:
            raise UserError(_("Файл плану: %s", e)) from e
        cut_map._f3d_apply_plan(plan)
        return {"type": "ir.actions.act_window_close"}
