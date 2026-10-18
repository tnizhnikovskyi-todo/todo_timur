import logging
from math import ceil

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class MrpWorkorder(models.Model):
    _inherit = "mrp.workorder"

    td_qty_counted = fields.Float(digits="Product Unit", readonly=True, copy=False, string="Порахував верстат")
    td_qty_synced_at = fields.Datetime()
    td_auto_started = fields.Boolean(readonly=True, copy=False, string="Стартував верстат")
    td_partial_hold = fields.Boolean(copy=False, string="Неповна партія")
    td_run_min = fields.Float(digits=(12, 1), readonly=True, copy=False, string="Робота верстата, хв")
    td_setup_min = fields.Float(digits=(12, 1), readonly=True, copy=False, string="Налагодження, хв")
    td_machine_state = fields.Selection(related="workcenter_id.td_machine_state", string="Стан верстата")
    td_cut_map_ids = fields.One2many("td.cut.map", "workorder_id", string="Карти розкрою")
    td_can_send = fields.Boolean(compute="_compute_f3d_can_send")
    td_gantry_job_ids = fields.One2many("td.gantry.job", "workorder_id", string="Завдання порталу")
    # DEC-1/ENV-3: у CE 19.0 немає mrp.workorder.employee_ids/start_employee (це mrp_workorder, Enterprise).
    td_employee_id = fields.Many2one("hr.employee", string="Оператор (верстат)")

    @api.depends("workcenter_id.td_machine_ids.protocol", "workcenter_id.td_machine_ids.sig_job_cmd_id")
    def _compute_f3d_can_send(self):
        for rec in self:
            machine = rec.workcenter_id.sudo().td_machine_ids[:1]
            rec.td_can_send = bool(machine and machine.protocol == "opcua" and machine.sig_job_cmd_id)

    def action_f3d_finish_partial(self):
        """R-12 п. 5: майстер завершує завдання неповною партією (`qty_produced = td_qty_counted`)."""
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group("mrp.group_mrp_manager"):
            raise AccessError(_("Завершити неповною партією може лише майстер (керівник виробництва)."))
        vals = {"td_partial_hold": False}
        if self.td_qty_counted > 0:
            vals["qty_produced"] = self.td_qty_counted
        self.write(vals)
        self.button_finish()
        self.production_id.sudo().message_post(
            body=_(
                "Завдання %(wo)s завершено неповною партією: %(c)s з %(q)s",
                wo=self.display_name,
                c=self.td_qty_counted,
                q=self.qty_production,
            ),
            subtype_xmlid="mail.mt_note",
        )
        return True

    def action_f3d_clear_hold(self):
        """Зняти позначку «Неповна партія» (дозапуск)."""
        self.write({"td_partial_hold": False})
        return True

    def action_f3d_send_to_machine(self):
        """FR-27, CMD-01 `Store`: поставити завдання в чергу верстата (OPC UA JobManagement)."""
        self.ensure_one()
        if not self.td_can_send:
            raise UserError(
                _(
                    "Робочий центр %s не приймає завдань з Odoo (немає OPC UA JobManagement).",
                    self.workcenter_id.display_name,
                )
            )
        if self.state not in ("ready", "blocked"):
            raise UserError(_("Завдання %s уже в роботі або завершене.", self.display_name))
        machine = self.workcenter_id.sudo().td_machine_ids[:1]
        cmd = self.env["td.command"]._f3d_mc_create_command(
            machine.sig_job_cmd_id,
            "Store",
            {
                "job": "WO%05d" % self.id,
                "qty": max(1, ceil(self.qty_remaining)),
                "ref": self.production_id.name,
                "priority": 5,
            },
            {"td_machine_id": machine.id},
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
