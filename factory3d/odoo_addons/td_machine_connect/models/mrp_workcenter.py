import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .td_machine import STATES

_logger = logging.getLogger(__name__)


class MrpWorkcenter(models.Model):
    _inherit = "mrp.workcenter"

    td_machine_ids = fields.One2many("td.machine", "workcenter_id", string="Верстати")
    td_machine_id = fields.Many2one("td.machine", compute="_compute_f3d_machine", string="Верстат")
    td_machine_state = fields.Selection(STATES, compute="_compute_f3d_machine", string="Стан верстата")
    td_oee_today = fields.Float(compute="_compute_f3d_machine", string="OEE зміни")

    @api.depends("td_machine_ids", "td_machine_ids.state", "td_machine_ids.oee_today")
    def _compute_f3d_machine(self):
        for rec in self:
            machine = rec.td_machine_ids[:1]
            rec.td_machine_id = machine
            rec.td_machine_state = machine.state if machine else False
            rec.td_oee_today = machine.oee_today if machine else 0.0

    def action_f3d_machine(self):
        """Форма верстата РЦ; створення з `default_workcenter_id`, якщо запису ще немає."""
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": _("Верстат"),
            "res_model": "td.machine",
            "view_mode": "form",
            "target": "current",
        }
        if self.td_machine_id:
            action["res_id"] = self.td_machine_id.id
        else:
            if not self.env.user.has_group("td_factory3d.group_td_manager"):
                raise AccessError(_("Запис підключення верстата створює менеджер «Завод 3D»."))
            action["context"] = {"default_workcenter_id": self.id}
        return action
