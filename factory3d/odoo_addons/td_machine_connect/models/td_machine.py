import logging
import time
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models, modules, tools
from odoo.exceptions import AccessError, ValidationError

from ..tools.states import normalize, parse_ts

_logger = logging.getLogger(__name__)

KYIV = ZoneInfo("Europe/Kyiv")
ROLE_ORDER = {"state": 0, "mode": 1, "alarm": 2, "job": 3, "pieces": 4}
TICK_BUDGET_S = 10
HEARTBEAT_S = 30  # DEC-19: `raw_ts`/`pieces_ts` без інших змін пишуться не частіше за раз на стільки секунд
TICK_BATCH = 10  # DEC-19: верстатів на транзакцію такту (після пачки — commit, нова знімка, блокування знято)
PENDING_SLACK_S = 30

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
P = "td.machine_connect."  # префікс параметрів
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
    return "True" if env["ir.config_parameter"].sudo().get_param("td.base.environment", "") == "test" else "False"


def local(dt, fmt="%d.%m %H:%M"):
    """Naive-UTC datetime → рядок за київським часом (порожньо для `False`)."""
    if not dt:
        return ""
    return dt.replace(tzinfo=timezone.utc).astimezone(KYIV).strftime(fmt)


class F3dMachine(models.Model):
    _name = "td.machine"
    _description = "Верстати: підключення верстата"
    _inherit = ["mail.thread"]
    _order = "code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]

    workcenter_id = fields.Many2one(
        "mrp.workcenter", string="Робочий центр", required=True, index=True, ondelete="cascade", tracking=True
    )
    name = fields.Char(related="workcenter_id.name", store=True, string="Назва")
    code = fields.Char(related="workcenter_id.td_code", store=True, index=True, string="Код")
    zone_id = fields.Many2one("td.zone", related="workcenter_id.td_zone_id", store=True, string="Зона")
    company_id = fields.Many2one("res.company", related="workcenter_id.company_id", store=True, index=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Обладнання",
        ondelete="set null",
        help="За td_code = code: заявки ТО, паспорт",
    )
    active = fields.Boolean(default=True)
    protocol = fields.Selection(PROTOCOLS, string="Підключення", required=True, default="opcua", tracking=True)
    source_id = fields.Many2one("td.source", string="Джерело", ondelete="set null", help="UA-<код> або MB-U8x-IOy")
    io_slot = fields.Integer(
        string="Позиція в модулі I/O",
        help="m = 0…4: DI(2m) — в роботі, DI(2m+1) — аварія, лічильник DI(2m)",
    )
    sig_state_id = fields.Many2one("td.signal", string="Сигнал стану", ondelete="set null")
    sig_mode_id = fields.Many2one("td.signal", string="Сигнал режиму", ondelete="set null")
    sig_alarm_id = fields.Many2one("td.signal", string="Сигнал тривоги", ondelete="set null")
    sig_pieces_id = fields.Many2one("td.signal", string="Лічильник деталей", ondelete="set null")
    sig_job_id = fields.Many2one("td.signal", string="Сигнал завдання", ondelete="set null")
    sig_event_id = fields.Many2one("td.signal", string="Сигнал подій", ondelete="set null")
    sig_machine_state_id = fields.Many2one("td.signal", string="Обчислений стан", ondelete="set null")
    sig_job_cmd_id = fields.Many2one("td.signal", string="Команди завдань", ondelete="set null")
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
    current_log_id = fields.Many2one("td.machine.state.log", readonly=True, ondelete="set null")
    current_downtime_id = fields.Many2one("td.downtime", string="Поточний простій", readonly=True, ondelete="set null")
    active_workorder_id = fields.Many2one(
        "mrp.workorder", string="Активне завдання", readonly=True, ondelete="set null"
    )
    wo_paused = fields.Boolean(help="Таймер активного завдання закрив верстат (R-10)")
    last_autostart_key = fields.Char(size=64)
    no_job_since = fields.Datetime(help="Верстат працює без завдання з (R-09 п. 9)")
    no_job_notified = fields.Boolean()
    oee_shift_id = fields.Many2one("td.oee.shift", string="OEE поточної зміни", readonly=True, ondelete="set null")
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
    def _td_clear_map_cache(self, vals):
        if any(k in vals for k in SIG_FIELDS) or "active" in vals or "read_enabled" in vals:
            self.env.registry.clear_cache()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for vals in vals_list:
            records._td_clear_map_cache(vals)
        return records

    def write(self, vals):
        res = super().write(vals)
        self._td_clear_map_cache(vals)
        return res

    def unlink(self):
        res = super().unlink()
        self.env.registry.clear_cache()
        return res

    # --- довідник сигналів ---------------------------------------------------------------------------
    @api.model
    @tools.ormcache()
    def _td_code_map(self):
        """`{signal_code: (machine_id, role)}` для активних верстатів (ролі SIG_ROLES)."""
        res = {}
        fnames = ["sig_%s_id" % r for r in SIG_ROLES]
        recs = self.sudo().search_read([("active", "=", True)], ["id", *fnames])
        sig_ids = {rec[f][0] for rec in recs for f in fnames if rec[f]}
        codes = {s["id"]: s["code"] for s in self.env["td.signal"].sudo().browse(sig_ids).read(["code"])}
        for rec in recs:
            for role in SIG_ROLES:
                sig = rec["sig_%s_id" % role]
                if sig:
                    res[codes[sig[0]]] = (rec["id"], role)
        return res

    # --- гачки між файлами (W1 викликає, W2/W3 перевизначають через super()) -------------------------
    def _td_after_commit(self, old, new, ts):
        """Після фіксації переходу стану (R-04 п. 4). Тут порожній."""

    def _td_tick_extra(self, now):
        """Частина `_cron_tick` для кожного верстата з `read_enabled`. Тут порожній."""

    def _td_on_count(self, delta, ts):
        """Після R-11 п. 1–3 (приріст лічильника). Тут порожній."""

    def _td_on_job(self, text, ts):
        """Зміна `raw_job`. Базова реалізація пише `raw_job`."""
        for rec in self:
            if rec.raw_job != text:
                rec.raw_job = text

    @api.model
    def _td_apply_event(self, payload):
        """EV-01 (M-21). Базова частина: знайти верстат за `machine`; решта — у файлах W2/W3."""
        machine = self.sudo().search([("code", "=", payload.get("machine"))], limit=1)
        if not machine:
            raise ValueError("mc_opcua: machine %s" % payload.get("machine"))
        return machine

    def _td_tech_env(self):
        """Середовище технічного користувача (R-00: автоматичні зміни стандартних моделей)."""
        user = self.env.ref("td_machine_connect.user_td_machine")
        return self.env(user=user.id, su=False, context=dict(self.env.context, tz="Europe/Kyiv", f3d_mc_auto=True))

    # --- диспетчер показань (R-04 п. 0) --------------------------------------------------------------
    @api.model
    def _td_dispatch(self, readings, src):
        """Вхід із M-18: показання → верстати → `_td_apply`. Синхронний; помилка верстата не поширюється."""
        stats = {"machines": 0, "transitions": 0, "autostarts": 0, "finished": 0, "errors": []}
        code_map = self._td_code_map()
        groups = {}
        for r in readings:
            entry = code_map.get(r.get("code"))
            ts = parse_ts(r.get("ts"))
            if not entry or ts is None:
                continue
            machine_id, role = entry
            groups.setdefault(machine_id, []).append(
                {
                    "role": role,
                    "ts": ts,
                    "text": r.get("text"),
                    "value": r.get("value"),
                    "q": r.get("q") or "good",
                }
            )
        # DEC-19: єдиний порядок блокування рядків — за id (push, такт і `_td_mark_nodata` не блокують навхрест)
        machines = self.sudo().browse(sorted(groups)).exists().filtered(lambda m: m.active and m.read_enabled)
        machines = machines.with_context(f3d_mc_stats=stats)
        for machine in machines:
            try:
                with self.env.cr.savepoint():
                    machine._td_lock()
                    machine._td_apply(groups[machine.id])
                stats["machines"] += 1
            except Exception:
                _logger.exception("td.machine %s: помилка обробки показань", machine.code)
                stats["errors"].append(machine.code)
        return stats

    def _td_lock(self):
        """Блокування рядків верстатів до зміни стану (R-04 п. 0, R-09 п. 7) і свіжий стан після блокування."""
        if self.ids:
            self.env.cr.execute("SELECT id FROM td_machine WHERE id IN %s ORDER BY id FOR UPDATE", (tuple(self.ids),))
            self.invalidate_recordset()

    def _td_lock_skip_locked(self):
        """DEC-19: як `_td_lock`, але без очікування: рядки, зайняті іншою транзакцією (push), пропускаються.

        Повертає підмножину `self`, яку вдалося заблокувати (за зростанням id), зі свіжим станом із бази.
        """
        if not self.ids:
            return self
        cr = self.env.cr
        cr.execute("SELECT id FROM td_machine WHERE id IN %s ORDER BY id FOR UPDATE SKIP LOCKED", (tuple(self.ids),))
        locked = [row[0] for row in cr.fetchall()]
        self.invalidate_recordset()
        return self.browse(locked)

    def _td_stat(self, key, n=1):
        """Лічильник для результату `_td_dispatch` (W3 рахує `autostarts`, `finished`)."""
        stats = self.env.context.get("f3d_mc_stats")
        if stats is not None:
            stats[key] = stats.get(key, 0) + n

    def _td_apply(self, items):
        """R-04 п. 1: показання одного верстата (`role`, `ts`, `text`, `value`, `q`) → raw_*, стан, лічильник."""
        self.ensure_one()
        items = sorted(items, key=lambda it: (it["ts"], ROLE_ORDER.get(it["role"], 9)))
        raw = {
            "state": self.raw_state or None,
            "mode": self.raw_mode or None,
            "alarm": self.raw_alarm,
            "bad": not self.raw_state,
        }
        job = self.raw_job
        raw_ts = self.raw_ts
        before = (self.state, self.pending_state)
        dirty = False  # у цьому push рядок верстата й так змінюється → `raw_ts` їде в тому самому UPDATE (DEC-19)
        i = 0
        while i < len(items):
            ts = items[i]["ts"]
            group = []
            while i < len(items) and items[i]["ts"] == ts:
                group.append(items[i])
                i += 1
            late = bool(self.state_since and ts < self.state_since)
            changed = False
            for it in group:
                role = it["role"]
                if late and role in ("state", "mode", "alarm", "job"):
                    _logger.debug("td.machine %s: пізнє показання %s @%s", self.code, role, ts)
                    continue
                if role == "state":
                    raw["state"] = None if it["q"] == "bad" else it["text"]
                    changed = True
                elif role == "mode" and it["q"] != "bad":
                    raw["mode"] = it["text"]
                    changed = True
                elif role == "alarm" and it["q"] != "bad":
                    raw["alarm"] = it["text"] == "on" or it["value"] == 1
                    changed = True
            if changed:
                vals = {"raw_state": raw["state"] or False, "raw_mode": raw["mode"] or False, "raw_alarm": raw["alarm"]}
                dirty = dirty or any(self[key] != val for key, val in vals.items())
                self.write(vals)
                raw["bad"] = raw["state"] is None
                new = normalize(self.protocol, raw, key=self.code, now=ts)
                self._td_on_raw_state(new, ts)
                raw_ts = max(raw_ts, ts) if raw_ts else ts
            for it in group:
                if it["role"] == "job" and not late and it["q"] != "bad" and it["text"] is not None:
                    if it["text"] != job:
                        job = it["text"]
                        dirty = True
                        self._td_on_job(job, ts)
                    raw_ts = max(raw_ts, ts) if raw_ts else ts
                elif it["role"] == "pieces" and it["value"] is not None and it["q"] != "bad":
                    dirty = dirty or it["value"] != self.pieces_last
                    self._td_count(it["value"], ts)
                    raw_ts = max(raw_ts, ts) if raw_ts else ts
        if raw_ts != self.raw_ts and (
            dirty or before != (self.state, self.pending_state) or self._td_heartbeat_due(self.raw_ts, raw_ts)
        ):
            self.write({"raw_ts": raw_ts})

    @staticmethod
    def _td_heartbeat_due(stored, new):
        """DEC-19: чи минуло `HEARTBEAT_S` від збереженої мітки (порожня мітка — пишемо одразу)."""
        return not stored or abs((new - stored).total_seconds()) >= HEARTBEAT_S

    def _td_on_raw_state(self, new, ts):
        """R-02: мікрозупинки й момент фіксації стану."""
        self.ensure_one()
        if self.state_since and ts < self.state_since:
            _logger.debug("td.machine %s: late %s @%s", self.code, new, ts)
            return
        if new == self.state:
            if self.pending_state:
                self.write({"pending_state": False, "pending_since": False})
            return
        if new in ("working", "fault", "off", "nodata"):
            self._td_commit_state(new, ts)
            return
        # new in (idle, setup)
        if self.state == "working" and self.micro_stop_s > 0:
            since = self.pending_since if self.pending_state else ts
            if not self.pending_state:
                self.write({"pending_state": new, "pending_since": ts})
            elif self.pending_state != new:
                self.write({"pending_state": new})
            if ts >= since + timedelta(seconds=self.micro_stop_s):
                self._td_commit_state(new, since)
        else:
            self._td_commit_state(new, ts)

    def _td_commit_state(self, new, ts, cause="machine"):
        """R-04 п. 2–6: закрити інтервал, відкрити новий, гачки (простій, автостарт…), сигнал, шина."""
        self.ensure_one()
        if new == self.state:
            if self.pending_state:
                self.write({"pending_state": False, "pending_since": False})
            return False
        old = self.state
        Log = self.env["td.machine.state.log"].sudo()
        if self.current_log_id:
            self.current_log_id._td_close(ts)
            self.current_log_id.flush_recordset()
        wo = self.active_workorder_id
        mode = self.raw_mode or "alarm=%d" % bool(self.raw_alarm)
        log = Log.create(
            {
                "machine_id": self.id,
                "state": new,
                "date_start": ts,
                "workorder_id": wo.id if wo else False,
                "employee_id": wo.td_employee_id.id if wo and wo.td_employee_id else False,
                "source": cause,
                "raw": ("%s/%s" % (self.raw_state or "", mode))[:64],
                "pieces_start": self.pieces_last,
            }
        )
        self.with_context(tracking_disable=True).write(
            {
                "state": new,
                "state_since": ts,
                "current_log_id": log.id,
                "pending_state": False,
                "pending_since": False,
            }
        )
        self._td_stat("transitions")
        self._td_after_commit(old, new, ts)
        self._td_emit_state(ts)
        self._td_notify()
        return True

    def _td_mark_nodata(self, ts, reason):
        """R-03: сигнал стану `stale` → `nodata` (причина — у лог)."""
        for rec in self.sudo().exists().filtered(lambda m: m.active and m.read_enabled).sorted("id"):
            if not param_bool(rec.env, "read_enabled", env_default(rec.env)):
                continue
            with rec.env.cr.savepoint():
                rec._td_lock()
                _logger.info("td.machine %s: nodata (%s)", rec.code, reason)
                rec._td_commit_state("nodata", ts, cause="system")

    def _td_emit_state(self, ts):
        """Обчислений стан → сигнал `machine_state` (CT-10)."""
        self.ensure_one()
        sig = self.sig_machine_state_id
        if not sig:
            return
        self.env["td.signal"].sudo().with_context(f3d_mc_internal=True)._td_ingest(
            [{"code": sig.code, "ts": ts, "text": self.state, "q": "good"}], src="module"
        )

    def _td_notify(self, kinds=("state",)):
        if "td.viewer.event" in self.env:
            self.env["td.viewer.event"]._notify("mrp.workcenter", self.mapped("code"), "state")

    def _td_count(self, value, ts):
        """R-11 п. 1–3: приріст лічильника; далі гачок `_td_on_count`."""
        self.ensure_one()
        delta = 0.0
        if self.pieces_ts or self.pieces_last:
            delta = value - self.pieces_last
            if delta < 0:
                if value <= 1000:
                    delta = value
                else:
                    _logger.warning("td.machine %s: скидання лічильника на %s", self.code, value)
                    delta = 0.0
            elif delta > 1000:
                _logger.warning("td.machine %s: стрибок лічильника %s → %s", self.code, self.pieces_last, value)
                delta = 0.0
        vals = {"pieces_last": value}
        if value != self.pieces_last or self._td_heartbeat_due(self.pieces_ts, ts):
            vals["pieces_ts"] = ts  # мітка без зміни лічильника — не частіше за HEARTBEAT_S (DEC-19)
        self.write(vals)
        if delta and self.current_log_id:
            self.current_log_id.pieces += delta
        self._td_on_count(delta, ts)

    # --- дії (кнопки) --------------------------------------------------------------------------------
    def action_test_connection(self):
        self.ensure_one()
        message = _(
            "Джерело %(src)s: %(src_state)s; стан %(raw_state)s/%(raw_mode)s, тривога %(alarm)s, лічильник %(pieces)s, "
            "завдання %(job)s; останнє показання %(ts)s",
            src=self.source_id.code or "—",
            src_state=self.source_id.state or "—",
            raw_state=self.raw_state or "—",
            raw_mode=self.raw_mode or "—",
            alarm=_("так") if self.raw_alarm else _("ні"),
            pieces=self.pieces_last,
            job=self.raw_job or "—",
            ts=local(self.raw_ts) or "—",
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": self.display_name, "message": message, "type": "info", "sticky": False},
        }

    def _td_act_window(self, model, name, view_mode="list,form"):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": view_mode,
            "domain": [("machine_id", "=", self.id)],
            "context": {"default_machine_id": self.id},
        }

    def action_view_logs(self):
        return self._td_act_window("td.machine.state.log", _("Журнал станів"), "list,graph,pivot")

    def action_view_downtimes(self):
        return self._td_act_window("td.downtime", _("Простої"), "list,kanban,form,graph,pivot")

    def action_view_oee(self):
        return self._td_act_window("td.oee.shift", _("OEE"), "list,pivot,graph,form")

    def action_open_workcenter(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "mrp.workcenter",
            "res_id": self.workcenter_id.id,
            "view_mode": "form",
        }

    def action_f3d_show(self):
        self.ensure_one()
        return self.workcenter_id.action_f3d_show()

    def action_open_reason_wizard(self):
        """Кнопка «Причина» картки: майстер причини поточного простою (M-24, W2)."""
        self.ensure_one()
        return self.current_downtime_id.action_open_reason_wizard()

    def action_reset_state(self):
        if not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError(_("Скинути стан верстата може лише адміністратор «3D Завод»."))
        now = fields.Datetime.now()
        for rec in self:
            rec = rec.sudo()
            rec._td_lock()
            rec._td_commit_state("nodata", now, cause="system")
            rec.message_post(body=_("Стан скинуто адміністратором"))
        return True

    # --- крон ----------------------------------------------------------------------------------------
    @api.model
    def _cron_tick(self):
        """Щохвилини: стан MC-DERIVED, відкладені переходи (R-02 п. 4), `_td_tick_extra` для кожного верстата."""
        enabled = param_bool(self.env, "read_enabled", env_default(self.env))
        source = self.env.ref("td_machine_connect.source_mc_derived", raise_if_not_found=False)
        if source:
            wanted = "online" if enabled else "disabled"
            if source.state != wanted:
                source.sudo().write({"state": wanted})
        if not enabled:
            return True
        now = fields.Datetime.now()
        started = time.monotonic()
        # DEC-19: стабільний порядок (id), пачки з commit між ними, рядки, зайняті push, — SKIP LOCKED (без очікування).
        ids = self.sudo().search([("active", "=", True), ("read_enabled", "=", True)], order="id").ids
        Machine = self.sudo().with_context(f3d_mc_stats={})
        skipped = 0
        for pos in range(0, len(ids), TICK_BATCH):
            if time.monotonic() - started > TICK_BUDGET_S:
                _logger.warning("td.machine: такт перевищив %s с, решту верстатів пропущено", TICK_BUDGET_S)
                break
            batch = Machine.browse(ids[pos : pos + TICK_BATCH])
            locked = batch._td_lock_skip_locked()
            skipped += len(batch) - len(locked)
            for machine in locked:
                try:
                    with self.env.cr.savepoint():
                        if machine.pending_state and machine.pending_since:
                            limit = machine.pending_since + timedelta(seconds=machine.micro_stop_s + PENDING_SLACK_S)
                            if now >= limit:
                                machine._td_commit_state(machine.pending_state, machine.pending_since)
                        machine._td_tick_extra(now)
                except Exception:
                    _logger.exception("td.machine %s: помилка такту", machine.code)
            if not modules.module.current_test:  # у тестах commit курсора заборонено
                self.env["ir.cron"]._commit_progress(len(batch), remaining=len(ids) - pos - len(batch))
        if skipped:
            _logger.info(
                "td.machine: такт пропустив %s верстатів, зайнятих push (опрацюються наступним тактом)", skipped
            )
        return True

    @api.model
    def _td_run_migration(self):
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
