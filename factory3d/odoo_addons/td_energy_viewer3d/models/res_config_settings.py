"""M-42, V-46: налаштування моста «Енергетика в 3D» (`td.energy_viewer3d.*`)."""

import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import layer as layer_tools

P = layer_tools.P


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_energy_viewer3d_layers = fields.Char(  # Text не допускається для `config_parameter` (res.config.settings)
        string="Шари GLB для «Відкрити в 3D»",
        config_parameter=P + "layers",
        default=lambda self: json.dumps(layer_tools.DEFAULT_LAYERS),
    )
    td_energy_viewer3d_marker_limit = fields.Integer(
        string="Маркерів тривог, не більше",
        config_parameter=P + "marker_limit",
        default=layer_tools.DEFAULT_MARKER_LIMIT,
    )
    # Boolean із типовим «увімкнено» не зберігається через `config_parameter` (False видаляє параметр і форма знову
    # показує типове) — читаємо й пишемо рядком вручну.
    td_energy_viewer3d_show_markers = fields.Boolean(string="Маркери тривог на моделі", default=True)

    @api.constrains("td_energy_viewer3d_layers", "td_energy_viewer3d_marker_limit")
    def _check_td_energy_viewer3d(self):
        for rec in self:
            raw = (rec.td_energy_viewer3d_layers or "").strip()
            if raw:
                try:
                    value = json.loads(raw)
                except ValueError:
                    value = None
                if not (isinstance(value, list) and value and all(isinstance(k, str) and k for k in value)):
                    raise ValidationError(_('Шари GLB: JSON-список ключів, напр. ["building", "energy"].'))
            if not 1 <= rec.td_energy_viewer3d_marker_limit <= layer_tools.MAX_MARKER_LIMIT:
                raise ValidationError(_("Маркерів тривог: від 1 до %s.", layer_tools.MAX_MARKER_LIMIT))

    @api.model
    def get_values(self):
        res = super().get_values()
        raw = self.env["ir.config_parameter"].sudo().get_param(P + "show_markers", "True")
        res["td_energy_viewer3d_show_markers"] = raw not in ("False", "false", "0")
        return res

    def set_values(self):
        super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        for rec in self:
            icp.set_param(P + "show_markers", str(bool(rec.td_energy_viewer3d_show_markers)))
