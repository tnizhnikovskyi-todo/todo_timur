import logging
from zoneinfo import ZoneInfo

from odoo import api, fields, models

from ..models.f3d_machine import KYIV

_logger = logging.getLogger(__name__)


class F3dDowntimeReasonWizard(models.TransientModel):
    """M-24: причина простою."""

    _name = "f3d.downtime.reason.wizard"
    _description = "Верстати: причина простою"

    downtime_id = fields.Many2one("f3d.downtime", required=True, readonly=True)
    hint_text = fields.Char(related="downtime_id.hint_text")
    loss_id = fields.Many2one(
        "mrp.workcenter.productivity.loss",
        required=True,
        domain="[('manual', '=', True), ('loss_type', 'in', ('availability', 'quality'))]",
    )
    employee_id = fields.Many2one("hr.employee", default=lambda s: s.env.user.employee_id)
    note = fields.Char(size=256)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        dt = self.env["f3d.downtime"].browse(res.get("downtime_id") or self.env.context.get("default_downtime_id"))
        if dt.exists() and "loss_id" in fields_list and not res.get("loss_id"):
            unknown = self.env.ref("factory3d_machine_connect.loss_unknown")
            loss = dt.hint_loss_id or (dt.loss_id if dt.loss_id != unknown else False)
            if loss:
                res["loss_id"] = loss.id
        return res

    def action_apply(self):
        self.ensure_one()
        dt = self.downtime_id
        dt.action_set_reason(self.loss_id.id, self.employee_id.id or None)
        if self.note:
            now = fields.Datetime.now().replace(tzinfo=ZoneInfo("UTC")).astimezone(KYIV)
            line = "%s %s: %s" % (now.strftime("%d.%m %H:%M"), self.env.user.name, self.note)
            dt.sudo().write({"note": ((dt.note + "\n") if dt.note else "") + line})
        return {"type": "ir.actions.act_window_close"}
