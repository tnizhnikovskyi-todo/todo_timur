"""M-12 td.push.handler.yard: обробник маршруту lpr (telemetry CT-08)."""

from odoo import models


class F3dPushHandlerYard(models.AbstractModel):
    _name = "td.push.handler.yard"
    _inherit = "td.push.handler"
    _description = "Двір: обробник подій LPR"
    _f3d_push_routes = ("lpr",)

    def _f3d_handle_push(self, route, event):
        if route != "lpr":
            return
        self.env["td.yard.lpr.event"].sudo()._f3d_from_push(event)
