from odoo import fields, models

from .td_fire_panel import PRIORITY, STATES
from .td_fire_zone import KINDS


class F3dZone(models.Model):
    _inherit = "td.zone"

    td_fire_zone_ids = fields.One2many("td.fire.zone", "zone_id", string="Зони сигналізації")
    td_fire_zone_count = fields.Integer(compute="_compute_f3d_fire")
    td_fire_kind = fields.Selection(KINDS, compute="_compute_f3d_fire")
    td_fire_state = fields.Selection(STATES, compute="_compute_f3d_fire")
    td_evac_route_id = fields.Many2one("td.fire.route", compute="_compute_f3d_evac")
    td_evac_exit_code = fields.Char(compute="_compute_f3d_evac")
    td_evac_length_m = fields.Float(compute="_compute_f3d_evac", digits=(8, 1))

    def _compute_f3d_fire(self):
        for rec in self:
            zones = rec.td_fire_zone_ids
            rec.td_fire_zone_count = len(zones)
            rec.td_fire_kind = zones.sorted("lsz_instance")[:1].kind or False
            rec.td_fire_state = max(zones.mapped("state"), key=PRIORITY.get) if zones else False

    def _compute_f3d_evac(self):
        Route = self.env["td.fire.route"] if "td.fire.route" in self.env else None
        for rec in self:
            route = Route.search([("zone_id", "=", rec.id)], limit=1) if Route is not None else False
            rec.td_evac_route_id = route or False
            rec.td_evac_exit_code = route.exit_id.code if route else False
            rec.td_evac_length_m = route.length_m if route else 0.0

    def action_view_fire_zones(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Зони сигналізації", "res_model": "td.fire.zone",
                "view_mode": "kanban,list,form", "domain": [("zone_id", "=", self.id)]}
