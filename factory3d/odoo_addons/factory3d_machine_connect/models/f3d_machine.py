import logging
from datetime import timezone
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")

STATES = [
    ("working", "В роботі"),
    ("setup", "Налагодження"),
    ("idle", "Очікування"),
    ("fault", "Аварія"),
    ("off", "Вимкнено"),
    ("nodata", "Немає даних"),
]
DOWN_STATES = ("setup", "idle", "fault", "off")  # стани, що дають простій
PROTOCOLS = [
    ("opcua", "OPC UA (OPC 40550-1)"),
    ("io", "Модуль вводу (ADAM, Modbus TCP)"),
    ("manual", "Без підключення"),
]
AUTO_MODES = [
    ("off", "Вимкнено"),
    ("job", "Лише за завданням верстата"),
    ("job_or_single", "За завданням або єдиним у черзі"),
]
SIG_ROLES = ("state", "mode", "alarm", "pieces", "job", "event")
P = "factory3d.machine_connect."  # префікс параметрів
SIG_FIELDS = (
    "sig_state_id",
    "sig_mode_id",
    "sig_alarm_id",
    "sig_pieces_id",
    "sig_job_id",
    "sig_event_id",
    "sig_machine_state_id",
    "sig_job_cmd_id",
)
STATE_COLORS = {"working": 10, "setup": 4, "idle": 3, "fault": 1, "off": 0, "nodata": 0}


def param(env, key, default):
    return env["ir.config_parameter"].sudo().get_param(P + key, default)


def param_bool(env, key, default="False"):
    return param(env, key, default) in ("True", "true", "1")


def env_default(env):
    """Умовчання `read_enabled` при відсутньому параметрі (CB-10): `True` лише в тестовому середовищі."""
    return (
        "True" if env["ir.config_parameter"].sudo().get_param("factory3d.base.environment", "") == "test" else "False"
    )


def local(dt, fmt="%d.%m %H:%M"):
    """Naive-UTC datetime → рядок за київським часом (порожньо для `False`)."""
    if not dt:
        return ""
    return dt.replace(tzinfo=timezone.utc).astimezone(KYIV).strftime(fmt)


class F3dMachine(models.Model):
    _name = "f3d.machine"
    _description = "Верстати: підключення верстата"
    _inherit = ["mail.thread"]
    _order = "code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]

    workcenter_id = fields.Many2one(
        "mrp.workcenter", string="Робочий центр", required=True, index=True, ondelete="cascade", tracking=True
    )
    name = fields.Char(related="workcenter_id.name", store=True, string="Назва")
    code = fields.Char(related="workcenter_id.f3d_code", store=True, index=True, string="Код")
    zone_id = fields.Many2one("f3d.zone", related="workcenter_id.f3d_zone_id", store=True, string="Зона")
    company_id = fields.Many2one("res.company", related="workcenter_id.company_id", store=True, index=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Обладнання",
        ondelete="set null",
        help="За f3d_code = code: заявки ТО, паспорт",
    )
    active = fields.Boolean(default=True)
    protocol = fields.Selection(PROTOCOLS, string="Підключення", required=True, default="opcua", tracking=True)
    source_id = fields.Many2one("f3d.source", string="Джерело", ondelete="set null", help="UA-<код> або MB-U8x-IOy")
    io_slot = fields.Integer(
        string="Позиція в модулі I/O",
        help="m = 0…4: DI(2m) — в роботі, DI(2m+1) — аварія, лічильник DI(2m)",
    )
    sig_state_id = fields.Many2one("f3d.signal", string="Сигнал стану", ondelete="set null")
    sig_mode_id = fields.Many2one("f3d.signal", string="Сигнал режиму", ondelete="set null")
    sig_alarm_id = fields.Many2one("f3d.signal", string="Сигнал тривоги", ondelete="set null")
    sig_pieces_id = fields.Many2one("f3d.signal", string="Лічильник деталей", ondelete="set null")
    sig_job_id = fields.Many2one("f3d.signal", string="Сигнал завдання", ondelete="set null")
    sig_event_id = fields.Many2one("f3d.signal", string="Сигнал подій", ondelete="set null")
    sig_machine_state_id = fields.Many2one("f3d.signal", string="Обчислений стан", ondelete="set null")
    sig_job_cmd_id = fields.Many2one("f3d.signal", string="Команди завдань", ondelete="set null")
    read_enabled = fields.Boolean(string="Читати", default=True, tracking=True)
    auto_start_mode = fields.Selection(
        AUTO_MODES, string="Автостарт", required=True, default="job_or_single", tracking=True
    )
    auto_finish = fields.Boolean(string="Автозавершення", default=True, tracking=True)
    auto_pause = fields.Boolean(string="Автопауза", default=True, tracking=True)
    micro_stop_s = fields.Integer(
        string="Мікрозупинка до, с", default=lambda s: int(param(s.env, "micro_stop_s", "120"))
    )
    pause_after_min = fields.Integer(
        string="Пауза завдання після, хв", default=lambda s: int(param(s.env, "pause_after_min", "10"))
    )
    finish_idle_s = fields.Integer(
        string="Завершення після зупинки, с", default=lambda s: int(param(s.env, "finish_idle_s", "60"))
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Працівник для автостарту",
        ondelete="set null",
        help="Якщо немає поточного й оператора OP-<код>",
    )
    state = fields.Selection(STATES, string="Стан", default="nodata", required=True, index=True, readonly=True)
    state_since = fields.Datetime(string="Стан з", readonly=True)
    raw_state = fields.Char(string="Стан верстата (сирий)", size=16, readonly=True)
    raw_mode = fields.Char(string="Режим (сирий)", size=16, readonly=True)
    raw_alarm = fields.Boolean(string="Тривога", readonly=True)
    raw_job = fields.Char(string="Завдання на верстаті", size=64, readonly=True)
    raw_ts = fields.Datetime(string="Останнє показання", readonly=True)
    pending_state = fields.Selection(STATES)
    pending_since = fields.Datetime()
    pieces_last = fields.Float(string="Лічильник (останнє)", readonly=True)
    pieces_ts = fields.Datetime(readonly=True)
    current_log_id = fields.Many2one("f3d.machine.state.log", readonly=True, ondelete="set null")
    current_downtime_id = fields.Many2one("f3d.downtime", string="Поточний простій", readonly=True, ondelete="set null")
    active_workorder_id = fields.Many2one(
        "mrp.workorder", string="Активне завдання", readonly=True, ondelete="set null"
    )
    wo_paused = fields.Boolean(help="Таймер активного завдання закрив верстат (R-10)")
    last_autostart_key = fields.Char(size=64)
    no_job_since = fields.Datetime(help="Верстат працює без завдання з (R-09 п. 9)")
    no_job_notified = fields.Boolean()
    oee_shift_id = fields.Many2one("f3d.oee.shift", string="OEE поточної зміни", readonly=True, ondelete="set null")
    oee_today = fields.Float(related="oee_shift_id.oee", string="OEE зміни")
    availability_today = fields.Float(related="oee_shift_id.availability", string="Доступність")
    performance_today = fields.Float(related="oee_shift_id.performance", string="Продуктивність")
    quality_today = fields.Float(related="oee_shift_id.quality", string="Якість")
    downtime_open_min = fields.Float(compute="_compute_live", string="Простій триває, хв")
    queue_ready_count = fields.Integer(compute="_compute_live", string="Завдань у черзі")
    color = fields.Integer(compute="_compute_live")
    note = fields.Text(string="Примітка")

    _f3d_machine_wc_uniq = models.Constraint("UNIQUE(workcenter_id)", "Для робочого центру вже є запис підключення.")
    _f3d_machine_thresholds = models.Constraint(
        "CHECK(micro_stop_s >= 0 AND pause_after_min >= 1 AND finish_idle_s >= 0)",
        "Пороги верстата: мікрозупинка ≥ 0 с, пауза ≥ 1 хв, завершення ≥ 0 с.",
    )

    # --- обчислювані ---------------------------------------------------------------------------------
    @api.depends("state", "current_downtime_id.date_start")
    def _compute_live(self):
        now = fields.Datetime.now()
        for rec in self:
            dt = rec.current_downtime_id
            rec.downtime_open_min = (now - dt.date_start).total_seconds() / 60 if dt and dt.date_start else 0.0
            rec.queue_ready_count = self.env["mrp.workorder"].search_count(
                [("workcenter_id", "=", rec.workcenter_id.id), ("state", "=", "ready")]
            )
            rec.color = STATE_COLORS.get(rec.state, 0)

    # --- перевірки -----------------------------------------------------------------------------------
    @api.constrains(
        "protocol",
        "sig_state_id",
        "sig_job_id",
        "auto_start_mode",
        "sig_mode_id",
        "sig_alarm_id",
        "sig_pieces_id",
        "sig_event_id",
        "sig_machine_state_id",
        "sig_job_cmd_id",
        "io_slot",
    )
    def _check_f3d_signals(self):
        for rec in self:
            if rec.protocol != "manual" and not rec.sig_state_id:
                raise ValidationError(_("Для підключеного верстата задайте сигнал стану."))
            prefix = "workcenters/%s/" % rec.code
            for fname in SIG_FIELDS:
                sig = rec[fname]
                if fname == "sig_machine_state_id" or not sig:
                    continue
                if not sig.code.startswith(prefix):
                    raise ValidationError(_("Сигнал %s не належить верстату %s.", sig.code, rec.code))
            if rec.sig_machine_state_id and rec.sig_machine_state_id.source_id.type != "f3d_machine":
                raise ValidationError(_("Обчислений стан має бути на джерелі MC-DERIVED."))
            if rec.auto_start_mode == "job" and (rec.protocol != "opcua" or not rec.sig_job_id):
                raise ValidationError(_("Режим «Лише за завданням» потребує сигналу завдання (OPC UA)."))
            if rec.protocol == "io" and not 0 <= rec.io_slot <= 4:
                raise ValidationError(_("Позиція в модулі I/O: 0…4."))

    # --- запис ---------------------------------------------------------------------------------------
    def _f3d_clear_map_cache(self, vals):
        if any(k in vals for k in SIG_FIELDS) or "active" in vals or "read_enabled" in vals:
            self.env.registry.clear_cache()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for vals in vals_list:
            records._f3d_clear_map_cache(vals)
        return records

    def write(self, vals):
        res = super().write(vals)
        self._f3d_clear_map_cache(vals)
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

    # --- довідник сигналів ---------------------------------------------------------------------------
    @api.model
    @tools.ormcache()
    def _f3d_code_map(self):
        """`{signal_code: (machine_id, role)}` для активних верстатів (ролі SIG_ROLES)."""
        res = {}
        fnames = ["sig_%s_id" % r for r in SIG_ROLES]
        recs = self.sudo().search_read([("active", "=", True)], ["id", *fnames])
        sig_ids = {rec[f][0] for rec in recs for f in fnames if rec[f]}
        codes = {s["id"]: s["code"] for s in self.env["f3d.signal"].sudo().browse(sig_ids).read(["code"])}
        for rec in recs:
            for role in SIG_ROLES:
                sig = rec["sig_%s_id" % role]
                if sig:
                    res[codes[sig[0]]] = (rec["id"], role)
        return res

    # --- гачки між файлами (W1 викликає, W2/W3 перевизначають через super()) -------------------------
    def _f3d_after_commit(self, old, new, ts):
        """Після фіксації переходу стану (R-04 п. 4). Тут порожній."""

    def _f3d_tick_extra(self, now):
        """Частина `_cron_tick` для кожного верстата з `read_enabled`. Тут порожній."""

    def _f3d_on_count(self, delta, ts):
        """Після R-11 п. 1–3 (приріст лічильника). Тут порожній."""

    def _f3d_on_job(self, text, ts):
        """Зміна `raw_job`. Базова реалізація пише `raw_job`."""
        for rec in self:
            if rec.raw_job != text:
                rec.raw_job = text

    @api.model
    def _f3d_apply_event(self, payload):
        """EV-01 (M-21). Базова частина: знайти верстат за `machine`; решта — у файлах W2/W3."""
        machine = self.sudo().search([("code", "=", payload.get("machine"))], limit=1)
        if not machine:
            raise ValueError("mc_opcua: machine %s" % payload.get("machine"))
        return machine

    def _f3d_tech_env(self):
        """Середовище технічного користувача (R-00: автоматичні зміни стандартних моделей)."""
        user = self.env.ref("factory3d_machine_connect.user_f3d_machine")
        return self.env(user=user.id, su=False, context=dict(self.env.context, tz="Europe/Kyiv", f3d_mc_auto=True))

    # --- крон-заглушки (реалізує власник файлу) ------------------------------------------------------
    @api.model
    def _cron_tick(self):
        """R-02 п. 4, R-03 п. 3 і `_f3d_tick_extra` (W1). Каркас: нічого не робить."""
        return True

    @api.model
    def _f3d_run_migration(self):
        """Серверна дія «Повторити міграцію» (W8). Каркас: звіт `skipped`."""
        from .. import hooks

        report = hooks.run_migration(self.env)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Міграція верстатів"),
                "message": _("Стан: %s", report.get("state", "—")),
                "type": "info",
                "sticky": False,
            },
        }
