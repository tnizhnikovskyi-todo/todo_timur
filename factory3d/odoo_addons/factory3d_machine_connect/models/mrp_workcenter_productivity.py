import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MrpWorkcenterProductivity(models.Model):
    """M-15: відмітки журналу часу. `create` (R-06 злиття) — W2."""

    _inherit = "mrp.workcenter.productivity"

    f3d_downtime_id = fields.Many2one("f3d.downtime", string="Простій верстата", ondelete="set null", index=True)
    f3d_source = fields.Selection(
        [("operator", "Оператор"), ("machine", "Верстат"), ("master", "Майстер"), ("demo", "Демо-дані")],
        default="operator",
        string="Звідки запис",
    )
    f3d_auto = fields.Boolean(default=False, string="Створено верстатом")


class MrpWorkcenterProductivityLoss(models.Model):
    """M-16."""

    _inherit = "mrp.workcenter.productivity.loss"

    f3d_planned = fields.Boolean(
        default=False,
        string="Плановий простій",
        help="Не входить у плановий час виробництва при розрахунку OEE (обід, регламентна перерва)",
    )
