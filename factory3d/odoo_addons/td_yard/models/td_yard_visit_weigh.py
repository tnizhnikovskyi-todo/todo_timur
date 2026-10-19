"""Розширення моделей W1 модулем ваг (W3): зважування рейсу, документа, хук «Зважити»."""

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.td_telemetry.tools.ingest import parse_ts


class F3dYardVisit(models.Model):
    _inherit = "td.yard.visit"

    weighing_ids = fields.One2many("td.yard.weighing", "visit_id", string="Зважування")

    @api.depends("weighing_ids.kind", "weighing_ids.ts", "weighing_ids.weight_kg", "weighing_ids.state")
    def _compute_weights(self):
        return super()._compute_weights()

    @api.model
    def _cron_queue(self):
        res = super()._cron_queue()
        self.env["td.yard.scale"].sudo().search([("active", "=", True)])._td_yard_refresh_offline()  # R-16 п. 6
        return res

    def _td_yard_write_pickings(self, net=None):
        """Без чинних зважувань документи не звіряються: скидання, без відхилення й активності."""
        self.ensure_one()
        if net is None and self.weight_check == "none":
            for picking in self.batch_id.picking_ids.filtered(lambda p: p.state != "cancel").sudo():
                picking.write({"td_net_weight_kg": 0.0, "td_weight_check": "none", "td_weight_deviation_pct": 0.0})
            return
        return super()._td_yard_write_pickings(net=net)

    def _td_yard_do_weigh(self):
        """«Зважити»: захоплення свіжого показання ваг або форма ручного вводу (FR-28)."""
        self.ensure_one()
        scale = self.env["td.yard.scale"].search([("company_id", "=", self.company_id.id)], limit=1)
        kind = "out" if self._td_yard_has_weighing("in") else "in"
        if scale and scale.capture_state != "offline":
            try:
                weighing = scale.action_capture(visit=self)
            except UserError:
                weighing = None
            if weighing:
                return {
                    "type": "ir.actions.act_window",
                    "res_model": "td.yard.weighing",
                    "res_id": weighing.id,
                    "view_mode": "form",
                    "target": "current",
                }
        return {
            "type": "ir.actions.act_window",
            "name": "Зважування вручну",
            "res_model": "td.yard.weighing",
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

    td_weighing_ids = fields.One2many("td.yard.weighing", "picking_id", string="Зважування двору")


class F3dYardGate(models.Model):
    _inherit = "td.yard.gate"

    ROLES = ("state", "loop", "photocell", "passes", "cmd_open", "cmd_close", "cmd_hold")

    scale_id = fields.Many2one("td.yard.scale", string="Автоваги", ondelete="set null")

    @api.model
    def _td_yard_dispatch(self, readings):
        """Показання `yard/gates/*` (M-13) -> gate._td_yard_on_readings."""
        by_code = {}
        for gate in self.sudo().search([("active", "=", True)]):
            for role in self.ROLES:
                sig = gate[role + "_signal_id"]
                if sig:
                    by_code[sig.code] = (gate, role)
        groups = {}
        for r in readings:
            target = by_code.get(r.get("code"))
            ts, reason = parse_ts(r.get("ts"))
            if not target or reason:
                continue
            value = r.get("value")
            value = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
            gate, role = target
            groups.setdefault(gate.id, (gate, []))[1].append((role, ts, value, r.get("q") or "good"))
        for gate, items in groups.values():
            gate._td_yard_on_readings(items)
