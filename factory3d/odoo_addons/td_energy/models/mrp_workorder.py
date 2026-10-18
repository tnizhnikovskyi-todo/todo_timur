from odoo import api, fields, models

COST_GROUP = "factory3d_energy.group_f3d_energy_cost"


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    f3d_energy_alloc_ids = fields.One2many("f3d.energy.alloc", "workorder_id", string="Розподіл енергії")
    f3d_energy_direct_kwh = fields.Float(
        string="Енергія пряма, кВт·год", compute="_compute_f3d_energy", store=True, digits=(12, 3)
    )
    f3d_energy_shared_kwh = fields.Float(
        string="Енергія спільна, кВт·год", compute="_compute_f3d_energy", store=True, digits=(12, 3)
    )
    f3d_energy_kwh = fields.Float(string="Енергія, кВт·год", compute="_compute_f3d_energy", store=True, digits=(12, 3))
    f3d_energy_cost = fields.Float(
        string="Вартість енергії, грн", compute="_compute_f3d_energy", store=True, digits=(12, 2), groups=COST_GROUP
    )
    f3d_energy_minutes = fields.Float(
        string="Хвилин з енергією", compute="_compute_f3d_energy", store=True, digits=(10, 1)
    )
    f3d_energy_quality = fields.Selection(
        [("none", "Немає даних"), ("measured", "Виміряно"), ("estimate", "Оцінка"), ("partial", "Частково")],
        string="Якість енергії",
        compute="_compute_f3d_energy",
        store=True,
    )

    @api.depends(
        "f3d_energy_alloc_ids.kwh",
        "f3d_energy_alloc_ids.cost",
        "f3d_energy_alloc_ids.kind",
        "f3d_energy_alloc_ids.quality",
        "f3d_energy_alloc_ids.minutes",
    )
    def _compute_f3d_energy(self):
        for wo in self:
            rows = wo.sudo().f3d_energy_alloc_ids
            direct = rows.filtered(lambda r: r.kind == "direct")
            shared = rows.filtered(lambda r: r.kind == "shared")
            wo.f3d_energy_direct_kwh = round(sum(direct.mapped("kwh")), 3)
            wo.f3d_energy_shared_kwh = round(sum(shared.mapped("kwh")), 3)
            wo.f3d_energy_kwh = round(wo.f3d_energy_direct_kwh + wo.f3d_energy_shared_kwh, 3)
            wo.f3d_energy_cost = round(sum((direct | shared).mapped("cost")), 2)
            wo.f3d_energy_minutes = round(sum(direct.mapped("minutes")), 1)
            quals = set(direct.mapped("quality"))
            if not rows:
                wo.f3d_energy_quality = "none"
            elif quals and quals <= {"measured", "interpolated"}:
                wo.f3d_energy_quality = "measured"
            elif quals == {"estimate"}:
                wo.f3d_energy_quality = "estimate"
            elif quals:
                wo.f3d_energy_quality = "partial"
            else:
                wo.f3d_energy_quality = "none"
