"""Розширення моделей W1 модулем ваг (W3): зважування рейсу, документа, хук «Зважити»."""

from odoo import api, fields, models
from odoo.exceptions import UserError


class F3dYardVisit(models.Model):
    _inherit = "f3d.yard.visit"

    weighing_ids = fields.One2many("f3d.yard.weighing", "visit_id", string="Зважування")

    @api.depends("weighing_ids.kind", "weighing_ids.ts", "weighing_ids.weight_kg", "weighing_ids.state")
    def _compute_weights(self):
        return super()._compute_weights()

    def _f3d_yard_write_pickings(self, net=None):
        """Без чинних зважувань документи не звіряються: скидання, без відхилення й активності."""
        self.ensure_one()
        if net is None and self.weight_check == "none":
            for picking in self.batch_id.picking_ids.filtered(lambda p: p.state != "cancel").sudo():
                picking.write({"f3d_net_weight_kg": 0.0, "f3d_weight_check": "none", "f3d_weight_deviation_pct": 0.0})
            return
        return super()._f3d_yard_write_pickings(net=net)

    def _f3d_yard_do_weigh(self):
        """«Зважити»: захоплення свіжого показання ваг або форма ручного вводу (FR-28)."""
        self.ensure_one()
        scale = self.env["f3d.yard.scale"].search([("company_id", "=", self.company_id.id)], limit=1)
        kind = "out" if self._f3d_yard_has_weighing("in") else "in"
        if scale and scale.capture_state != "offline":
            try:
                weighing = scale.action_capture(visit=self)
            except UserError:
                weighing = None
            if weighing:
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "f3d.yard.weighing",
                    "res_id": weighing.id,
                    "view_mode": "form",
                    "target": "current",
                }
        return {
            "type": "ir.actions.act_window",
            "name": "Зважування вручну",
            "res_model": "f3d.yard.weighing",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_visit_id": self.id,
                "default_kind": kind,
                "default_source": "manual",
                "default_scale_id": scale.id,
            },
        }


class StockPicking(models.Model):
    _inherit = "stock.picking"

    f3d_weighing_ids = fields.One2many("f3d.yard.weighing", "picking_id", string="Зважування двору")
