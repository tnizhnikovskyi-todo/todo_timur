import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    f3d_cut_map_ids = fields.One2many("f3d.cut.map", "production_id", string="Карти розкрою")
    f3d_cut_map_count = fields.Integer(compute="_compute_f3d_counts")
    f3d_gantry_job_ids = fields.One2many("f3d.gantry.job", "production_id", string="Завдання порталу")
    f3d_gantry_job_count = fields.Integer(compute="_compute_f3d_counts")

    @api.depends("f3d_cut_map_ids", "f3d_gantry_job_ids")
    def _compute_f3d_counts(self):
        for rec in self:
            rec.f3d_cut_map_count = len(rec.f3d_cut_map_ids)
            rec.f3d_gantry_job_count = len(rec.f3d_gantry_job_ids)

    def action_f3d_create_cut_maps(self):
        """M-14: карти розкрою для ролей `main` і `back` (якщо в МО є плита відповідної товщини)."""
        if not self.env.su and not self.env.user.has_group("factory3d_base.group_f3d_manager"):
            raise AccessError(_("Створення карт розкрою доступне менеджерам заводу."))
        self.ensure_one()
        if self.state in ("done", "cancel"):
            raise UserError(_("МО %s завершено або скасовано.", self.name))
        CutMap = self.env["f3d.cut.map"]
        maps = CutMap
        for role in ("main", "back"):
            if role == "back" and not CutMap._f3d_plate_move(self.sudo(), role):
                continue
            maps |= CutMap._f3d_create_for(self, role)
        action = {"type": "ir.actions.act_window", "name": _("Карти розкрою"), "res_model": "f3d.cut.map"}
        if len(maps) == 1:
            return {**action, "view_mode": "form", "res_id": maps.id}
        return {**action, "view_mode": "list,form", "domain": [("id", "in", maps.ids)]}

    def action_f3d_view_cut_maps(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Карти розкрою"),
            "res_model": "f3d.cut.map",
            "view_mode": "list,form",
            "domain": [("production_id", "=", self.id)],
            "context": {"default_production_id": self.id},
        }

    def action_f3d_feed_gantry(self):
        """R-16 п. 1: завдання порталу з МО; відкриває його форму."""
        self.ensure_one()
        job = self.env["f3d.gantry.job"]._f3d_from_production(self)
        return {
            "type": "ir.actions.act_window",
            "name": _("Завдання порталу"),
            "res_model": "f3d.gantry.job",
            "view_mode": "form",
            "res_id": job.id,
        }

    def action_f3d_view_gantry_jobs(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Завдання порталу"),
            "res_model": "f3d.gantry.job",
            "view_mode": "list,kanban,form",
            "domain": [("production_id", "=", self.id)],
        }
