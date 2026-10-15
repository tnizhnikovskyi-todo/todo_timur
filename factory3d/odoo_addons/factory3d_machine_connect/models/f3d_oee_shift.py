import logging

from odoo import api, fields, models

from .f3d_machine import param

_logger = logging.getLogger(__name__)

D12 = (12, 1)


class F3dOeeShift(models.Model):
    _name = "f3d.oee.shift"
    _description = "Верстати: OEE за зміну"
    _order = "date desc, code"

    machine_id = fields.Many2one("f3d.machine", required=True, index=True, ondelete="cascade")
    workcenter_id = fields.Many2one("mrp.workcenter", related="machine_id.workcenter_id", store=True, index=True)
    code = fields.Char(related="machine_id.code", store=True)
    zone_id = fields.Many2one("f3d.zone", related="machine_id.zone_id", store=True)
    company_id = fields.Many2one("res.company", related="machine_id.company_id", store=True)
    date = fields.Date(string="Дата зміни", required=True, index=True)
    date_start = fields.Datetime(string="Початок зміни")
    date_end = fields.Datetime(string="Кінець зміни")
    state = fields.Selection([("open", "Поточна"), ("closed", "Закрита")], required=True, default="open")
    source = fields.Selection([("machine", "Журнал станів"), ("timelog", "Журнал часу Odoo")], required=True)
    ppt_min = fields.Float(digits=D12, string="Плановий час, хв")
    planned_stop_min = fields.Float(digits=D12)
    nodata_min = fields.Float(digits=D12)
    run_min = fields.Float(digits=D12)
    run_wo_min = fields.Float(digits=D12)
    setup_min = fields.Float(digits=D12)
    fault_min = fields.Float(digits=D12)
    idle_min = fields.Float(digits=D12)
    off_min = fields.Float(digits=D12)
    unexplained_min = fields.Float(digits=D12)
    down_min = fields.Float(digits=D12)
    ideal_min = fields.Float(digits=D12, string="Ідеальний час, хв")
    qty_total = fields.Float(digits=D12)
    qty_bad = fields.Float(digits=D12)
    qty_good = fields.Float(digits=D12)
    availability = fields.Float(digits=(6, 4))
    performance = fields.Float(digits=(6, 4))
    performance_raw = fields.Float(digits=(6, 4))
    quality = fields.Float(digits=(6, 4))
    oee = fields.Float(digits=(6, 4))
    has_data = fields.Boolean(string="Є дані")
    coverage = fields.Float(digits=(6, 4), string="Повнота даних")
    incomplete = fields.Boolean(string="Неповні дані")
    losses = fields.Json(string="Втрати")
    computed_at = fields.Datetime(readonly=True)
    oee_color = fields.Selection(
        [("good", "Добре"), ("warn", "Увага"), ("bad", "Погано")], compute="_compute_oee_color"
    )

    _f3d_oee_uniq = models.Constraint("UNIQUE(machine_id, date)", "OEE за цю зміну вже є.")

    @api.depends("oee")
    def _compute_oee_color(self):
        good = float(param(self.env, "oee_good", "0.75"))
        warn = float(param(self.env, "oee_warn", "0.5"))
        for rec in self:
            rec.oee_color = "good" if rec.oee >= good else "warn" if rec.oee >= warn else "bad"

    @api.model
    def _cron_oee(self):
        """R-14 (W4). Каркас: нічого не робить."""
        return True
