"""M-12 f3d.push.handler.yard: обробник маршруту lpr (telemetry CT-08)."""

from odoo import models


class F3dPushHandlerYard(models.AbstractModel):
    _name = "f3d.push.handler.yard"
    _inherit = "f3d.push.handler"
    _description = "Двір: обробник подій LPR"
    _f3d_push_routes = ("lpr",)

    def _f3d_handle_push(self, route, event):
        if route != "lpr":
            return
        self.env["f3d.yard.lpr.event"].sudo()._f3d_from_push(event)
