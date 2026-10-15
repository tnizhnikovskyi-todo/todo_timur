import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class F3dDowntimeReasonWizard(models.TransientModel):
    """M-24: причина простою. Методи (`action_apply`) — W2."""

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
