import logging
from math import ceil

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

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
            machine = rec.workcenter_id.sudo().f3d_machine_ids[:1]
            rec.f3d_can_send = bool(machine and machine.protocol == "opcua" and machine.sig_job_cmd_id)

    def action_f3d_finish_partial(self):
        """R-12 п. 5: майстер завершує завдання неповною партією (`qty_produced = f3d_qty_counted`)."""
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("mrp.group_mrp_manager"):
            raise AccessError(_("Завершити неповною партією може лише майстер (керівник виробництва)."))
        vals = {"f3d_partial_hold": False}
        if self.f3d_qty_counted > 0:
            vals["qty_produced"] = self.f3d_qty_counted
        self.write(vals)
        self.button_finish()
        self.production_id.sudo().message_post(
            body=_(
                "Завдання %(wo)s завершено неповною партією: %(c)s з %(q)s",
                wo=self.display_name,
                c=self.f3d_qty_counted,
                q=self.qty_production,
            ),
            subtype_xmlid="mail.mt_note",
        )
        return True

    def action_f3d_clear_hold(self):
        """Зняти позначку «Неповна партія» (дозапуск)."""
        self.write({"f3d_partial_hold": False})
        return True

    def action_f3d_send_to_machine(self):
        """FR-27, CMD-01 `Store`: поставити завдання в чергу верстата (OPC UA JobManagement)."""
        self.ensure_one()
        if not self.f3d_can_send:
            raise UserError(
                _(
                    "Робочий центр %s не приймає завдань з Odoo (немає OPC UA JobManagement).",
                    self.workcenter_id.display_name,
                )
            )
        if self.state not in ("ready", "blocked"):
            raise UserError(_("Завдання %s уже в роботі або завершене.", self.display_name))
        machine = self.workcenter_id.sudo().f3d_machine_ids[:1]
        cmd = self.env["f3d.command"]._f3d_mc_create_command(
            machine.sig_job_cmd_id,
            "Store",
            {
                "job": "WO%05d" % self.id,
                "qty": max(1, ceil(self.qty_remaining)),
                "ref": self.production_id.name,
                "priority": 5,
            },
            {"f3d_machine_id": machine.id},
        )
        self.production_id.sudo().message_post(
            body=_(
                "Завдання %(wo)s поставлено в чергу верстата %(code)s: %(text)s",
                wo=self.display_name,
                code=machine.code,
                text=cmd.text or "",
            ),
            subtype_xmlid="mail.mt_note",
        )
        return True
