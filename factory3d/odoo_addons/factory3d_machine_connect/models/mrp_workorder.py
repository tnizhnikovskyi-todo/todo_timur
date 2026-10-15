import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    f3d_qty_counted = fields.Float(digits="Product Unit", readonly=True, copy=False, string="Порахував верстат")
    f3d_qty_synced_at = fields.Datetime()
    f3d_auto_started = fields.Boolean(readonly=True, copy=False, string="Стартував верстат")
    f3d_partial_hold = fields.Boolean(copy=False, string="Неповна партія")
    f3d_run_min = fields.Float(digits=(12, 1), readonly=True, copy=False, string="Робота верстата, хв")
    f3d_setup_min = fields.Float(digits=(12, 1), readonly=True, copy=False, string="Налагодження, хв")
    f3d_machine_state = fields.Selection(related="workcenter_id.f3d_machine_state", string="Стан верстата")
    f3d_cut_map_ids = fields.One2many("f3d.cut.map", "workorder_id", string="Карти розкрою")
    f3d_can_send = fields.Boolean(compute="_compute_f3d_can_send")
    f3d_gantry_job_ids = fields.One2many("f3d.gantry.job", "workorder_id", string="Завдання порталу")
    # DEC-1/ENV-3: у CE 19.0 немає mrp.workorder.employee_ids/start_employee (це mrp_workorder, Enterprise).
    f3d_employee_id = fields.Many2one("hr.employee", string="Оператор (верстат)")

    @api.depends("workcenter_id.f3d_machine_ids.protocol", "workcenter_id.f3d_machine_ids.sig_job_cmd_id")
    def _compute_f3d_can_send(self):
        for rec in self:
            machine = rec.workcenter_id.f3d_machine_ids[:1]
            rec.f3d_can_send = bool(machine and machine.protocol == "opcua" and machine.sig_job_cmd_id)
