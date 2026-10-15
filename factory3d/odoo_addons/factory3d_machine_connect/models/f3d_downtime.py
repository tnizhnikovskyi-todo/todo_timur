import logging

from odoo import api, fields, models

from .f3d_machine import local

_logger = logging.getLogger(__name__)


class F3dDowntime(models.Model):
    _name = "f3d.downtime"
    _description = "Верстати: простій"
    _inherit = ["mail.thread"]
    _order = "date_start desc, id desc"

    name = fields.Char(compute="_compute_name", store=True)
    machine_id = fields.Many2one("f3d.machine", string="Верстат", required=True, index=True, ondelete="cascade")
    workcenter_id = fields.Many2one("mrp.workcenter", related="machine_id.workcenter_id", store=True, index=True)
    code = fields.Char(related="machine_id.code", store=True)
    company_id = fields.Many2one("res.company", related="machine_id.company_id", store=True, index=True)
    date_start = fields.Datetime(string="Початок", required=True, index=True, tracking=True)
    date_end = fields.Datetime(string="Кінець", index=True, tracking=True)
    is_open = fields.Boolean(compute="_compute_open", store=True, index=True, string="Триває")
    duration_min = fields.Float(compute="_compute_duration", store=True, digits=(12, 1), string="Тривалість, хв")
    duration_live = fields.Float(compute="_compute_live", string="Тривалість (поточна), хв")
    ppt_min = fields.Float(digits=(12, 1), string="У плановому часі, хв")
    state_kind = fields.Selection(
        [("fault", "Аварія"), ("setup", "Налагодження"), ("idle", "Очікування"), ("off", "Вимкнено")],
        string="Стан верстата",
        required=True,
    )
    loss_id = fields.Many2one(
        "mrp.workcenter.productivity.loss",
        string="Причина",
        required=True,
        ondelete="restrict",
        tracking=True,
        domain="[('loss_type', 'in', ('availability', 'quality'))]",
        default=lambda s: s.env.ref("factory3d_machine_connect.loss_unknown", raise_if_not_found=False),
    )
    loss_type = fields.Selection(related="loss_id.loss_type")
    planned = fields.Boolean(related="loss_id.f3d_planned", string="Плановий")
    reason_source = fields.Selection(
        [
            ("auto", "Автоматично"),
            ("hint", "Підказка верстата"),
            ("operator", "Оператор"),
            ("master", "Майстер"),
            ("demo", "Демо-дані"),
        ],
        string="Хто вказав",
        required=True,
        default="auto",
        tracking=True,
    )
    reason_state = fields.Selection(
        [
            ("to_classify", "Потребує причини"),
            ("to_confirm", "Потребує підтвердження"),
            ("confirmed", "Підтверджено"),
        ],
        string="Класифікація",
        required=True,
        index=True,
        default="to_classify",
        tracking=True,
    )
    hint_loss_id = fields.Many2one("mrp.workcenter.productivity.loss", string="Підказка", ondelete="set null")
    hint_text = fields.Char(string="Звідки підказка", size=256)
    event_id = fields.Many2one("f3d.machine.event", string="Подія верстата", ondelete="set null")
    workorder_id = fields.Many2one("mrp.workorder", string="Завдання", ondelete="set null")
    production_id = fields.Many2one("mrp.production", related="workorder_id.production_id", store=True)
    employee_id = fields.Many2one("hr.employee", string="Працівник (причина)", ondelete="set null")
    reason_user_id = fields.Many2one("res.users", string="Причину вказав", readonly=True)
    reason_at = fields.Datetime(readonly=True)
    confirmed_by = fields.Many2one("res.users", string="Підтвердив", readonly=True)
    confirmed_at = fields.Datetime(readonly=True)
    productivity_ids = fields.One2many("mrp.workcenter.productivity", "f3d_downtime_id", string="Записи журналу часу")
    maintenance_request_id = fields.Many2one("maintenance.request", string="Заявка ТО", ondelete="set null")
    note = fields.Text(string="Примітка")
    has_loss_tool = fields.Boolean(compute="_compute_has_loss_tool")

    _f3d_downtime_dates = models.Constraint(
        "CHECK(date_end IS NULL OR date_end >= date_start)", "Кінець простою раніше за початок."
    )

    def init(self):
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS f3d_downtime_open_uniq ON f3d_downtime (machine_id) "
            "WHERE date_end IS NULL"
        )

    @api.depends("code", "date_start")
    def _compute_name(self):
        for rec in self:
            rec.name = "%s · %s" % (rec.code or "", local(rec.date_start, "%d.%m %H:%M"))

    @api.depends("date_end")
    def _compute_open(self):
        for rec in self:
            rec.is_open = not rec.date_end

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        for rec in self:
            rec.duration_min = (
                (rec.date_end - rec.date_start).total_seconds() / 60 if rec.date_end and rec.date_start else 0.0
            )

    @api.depends("date_start", "date_end", "duration_min")
    def _compute_live(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.date_end or not rec.date_start:
                rec.duration_live = rec.duration_min
            else:
                rec.duration_live = (now - rec.date_start).total_seconds() / 60

    def _compute_has_loss_tool(self):
        has = bool(self.env.ref("factory3d.loss_tool", raise_if_not_found=False))
        for rec in self:
            rec.has_loss_tool = has
