from odoo import fields, models

from .f3d_fire_panel import PRIORITY, STATES
from .f3d_fire_zone import KINDS


class F3dZone(models.Model):
    _inherit = "f3d.zone"

    f3d_fire_zone_ids = fields.One2many("f3d.fire.zone", "zone_id", string="Зони сигналізації")
    f3d_fire_zone_count = fields.Integer(compute="_compute_f3d_fire")
    f3d_fire_kind = fields.Selection(KINDS, compute="_compute_f3d_fire")
    f3d_fire_state = fields.Selection(STATES, compute="_compute_f3d_fire")
    f3d_evac_route_id = fields.Many2one("f3d.fire.route", compute="_compute_f3d_evac")
    f3d_evac_exit_code = fields.Char(compute="_compute_f3d_evac")
    f3d_evac_length_m = fields.Float(compute="_compute_f3d_evac", digits=(8, 1))

    def _compute_f3d_fire(self):
        for rec in self:
            zones = rec.f3d_fire_zone_ids
            rec.f3d_fire_zone_count = len(zones)
            rec.f3d_fire_kind = zones.sorted("lsz_instance")[:1].kind or False
            rec.f3d_fire_state = max(zones.mapped("state"), key=PRIORITY.get) if zones else False

    def _compute_f3d_evac(self):
        Route = self.env["f3d.fire.route"] if "f3d.fire.route" in self.env else None
        for rec in self:
            route = Route.search([("zone_id", "=", rec.id)], limit=1) if Route is not None else False
            rec.f3d_evac_route_id = route or False
            rec.f3d_evac_exit_code = route.exit_id.code if route else False
            rec.f3d_evac_length_m = route.length_m if route else 0.0

    def action_view_fire_zones(self):
        self.ensure_one()
        return {"type": "ir.actions.act_window", "name": "Зони сигналізації", "res_model": "f3d.fire.zone",
                "view_mode": "kanban,list,form", "domain": [("zone_id", "=", self.id)]}
