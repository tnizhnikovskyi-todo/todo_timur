import logging

from odoo import api, fields, models

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
