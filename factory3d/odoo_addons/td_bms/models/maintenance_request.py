from odoo import api, fields, models

from ..tools import rules
from .td_bms_deviation import RULES


class MaintenanceRequest(models.Model):
    """M-14: правило «Будівля» і журнал відхилень у заявці ТО."""

    _inherit = "maintenance.request"

    td_bms_rule = fields.Selection(RULES, string="Правило «Будівля»", compute="_compute_f3d_bms_rule", store=True)
    td_bms_deviation_ids = fields.One2many("td.bms.deviation", "request_id", string="Відхилення")
    td_bms_enriched = fields.Boolean(string="Доповнено (Будівля)", default=False, copy=False, readonly=True)

    @api.depends("td_signal_id")
    def _compute_f3d_bms_rule(self):
        for rec in self:
            sig = rec.td_signal_id
            rec.td_bms_rule = rules.rule_of(sig.code, sig.last_text) if sig and sig.module == "bms" else False
