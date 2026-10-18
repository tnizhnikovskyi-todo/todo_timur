import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .f3d_machine import STATES

_logger = logging.getLogger(__name__)


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    f3d_machine_ids = fields.One2many("f3d.machine", "workcenter_id", string="Верстати")
    f3d_machine_id = fields.Many2one("f3d.machine", compute="_compute_f3d_machine", string="Верстат")
    f3d_machine_state = fields.Selection(STATES, compute="_compute_f3d_machine", string="Стан верстата")
    f3d_oee_today = fields.Float(compute="_compute_f3d_machine", string="OEE зміни")

    @api.depends("f3d_machine_ids", "f3d_machine_ids.state", "f3d_machine_ids.oee_today")
    def _compute_f3d_machine(self):
        for rec in self:
            machine = rec.f3d_machine_ids[:1]
            rec.f3d_machine_id = machine
            rec.f3d_machine_state = machine.state if machine else False
            rec.f3d_oee_today = machine.oee_today if machine else 0.0

    def action_f3d_machine(self):
        """Форма верстата РЦ; створення з `default_workcenter_id`, якщо запису ще немає."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Верстат"),
            "res_model": "f3d.machine",
            "view_mode": "form",
            "target": "current",
        }
        if self.f3d_machine_id:
            action["res_id"] = self.f3d_machine_id.id
        else:
            if not self.env.user.has_group("factory3d_base.group_f3d_manager"):
                raise AccessError(_("Запис підключення верстата створює менеджер «Завод 3D»."))
            action["context"] = {"default_workcenter_id": self.id}
        return action
