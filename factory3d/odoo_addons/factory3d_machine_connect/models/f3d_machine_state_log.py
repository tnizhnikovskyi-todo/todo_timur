import logging

from odoo import api, fields, models

from .f3d_machine import STATES, local

_logger = logging.getLogger(__name__)


class F3dMachineStateLog(models.Model):
    _name = "f3d.machine.state.log"
    _description = "Верстати: інтервал стану"
    _order = "date_start desc, id desc"

    machine_id = fields.Many2one("f3d.machine", string="Верстат", required=True, index=True, ondelete="cascade")
    workcenter_id = fields.Many2one("mrp.workcenter", related="machine_id.workcenter_id", store=True, index=True)
    code = fields.Char(related="machine_id.code", store=True)
    state = fields.Selection(STATES, string="Стан", required=True, index=True)
    date_start = fields.Datetime(string="Початок", required=True, index=True)
    date_end = fields.Datetime(string="Кінець", index=True, help="Порожньо — триває")
    duration_min = fields.Float(compute="_compute_duration", store=True, digits=(12, 2), string="Хв")
    workorder_id = fields.Many2one("mrp.workorder", string="Завдання", ondelete="set null", index=True)
    production_id = fields.Many2one("mrp.production", related="workorder_id.production_id", store=True)
    employee_id = fields.Many2one("hr.employee", string="Працівник", ondelete="set null")
    downtime_id = fields.Many2one("f3d.downtime", string="Простій", ondelete="set null")
    source = fields.Selection(
        [("machine", "Верстат"), ("operator", "Оператор"), ("system", "Система")], default="machine", required=True
    )
    raw = fields.Char(string="Сирий стан", size=64)
    pieces_start = fields.Float(string="Лічильник на початку")
    pieces = fields.Float(string="Деталей", default=0, help="Приріст лічильника за інтервал (R-11)")
    in_ppt_min = fields.Float(string="У плановому часі, хв", digits=(12, 2))

    _f3d_log_dates = models.Constraint(
        "CHECK(date_end IS NULL OR date_end >= date_start)", "Кінець інтервалу раніше за початок."
    )
    _f3d_log_machine_start_idx = models.Index("(machine_id, date_start)")

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS f3d_machine_state_log_open_uniq "
            "ON f3d_machine_state_log (machine_id) WHERE date_end IS NULL"
        )

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        for rec in self:
            rec.duration_min = (
                (rec.date_end - rec.date_start).total_seconds() / 60 if rec.date_end and rec.date_start else 0.0
            )

    @api.depends("code", "state", "date_start", "date_end")
    def _compute_display_name(self):
        labels = dict(self._fields["state"].selection)
        for rec in self:
            rec.display_name = "%s · %s · %s–%s" % (
                rec.code or "",
                labels.get(rec.state, ""),
                local(rec.date_start, "%H:%M"),
                local(rec.date_end, "%H:%M") or "…",
            )

    @api.model
    def _cron_rotate(self):
        """R-14 п. 6 (ротація журналів). Каркас: нічого не робить; реалізує W1."""
        return True
