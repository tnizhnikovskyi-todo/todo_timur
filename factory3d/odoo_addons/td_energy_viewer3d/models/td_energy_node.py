"""M-42, R-58: `td.energy.node.action_td_open_3d` — «Відкрити в 3D» із підсвіткою вузла."""

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from ..tools import layer as layer_tools


class TdEnergyNode(models.Model):
    _inherit = "td.energy.node"

    @api.model
    def action_td_open_3d(self, code=None):
        """Дія `f3d_viewer.action`: шари GLB, режим `td_energy`, вкладка «Енергія»; з `code` — і об'єкт сцени.

        Вузол без об'єкта в 3D → `params.code = null` (клієнт показує застереження); невідомий `code` → `UserError`."""
        if not self.env.user.has_group(layer_tools.CARD_GROUP):
            raise AccessError(_("Відкрити шар «Енергетика в 3D» можуть користувачі енергетики."))
        scene = node_code = None
        if code:
            node = self.sudo().search([("code", "=", code)], limit=1)
            if not node:
                raise UserError(_("Вузол %s не знайдено.", code))
            node_code, scene = node.code, layer_tools.node_scene(node)
        return {
            "type": "ir.actions.client",
            "tag": "f3d_viewer.action",
            "name": _("Завод 3D"),
            "target": "current",
            "params": {
                "layers": layer_tools.params(self.env)["layers"],
                "mode": "td_energy",
                "tab": "energy",
                "code": scene,
                "td_energy_node": node_code,
            },
        }
