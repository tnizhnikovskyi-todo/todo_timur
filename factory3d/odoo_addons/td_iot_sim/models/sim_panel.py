import logging
from datetime import datetime, timedelta, timezone

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

MODES = [("scenario", "Сценарій"), ("follow_odoo", "За Odoo")]
ACTIVE_RUN_STATES = ["queued", "running", "stopping"]


def parse_iso_utc(value):
    """ISO 8601 (із зоною або без) → naive UTC datetime; не вдалося → False."""
    if not value:
        return False
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class F3dSimPanel(models.Model):
    _name = "td.sim.panel"
    _description = "Пульт емулятора обладнання"
    _inherit = ["td.sim.client", "mail.thread"]
    _order = "id"
    _rec_name = "name"

    name = fields.Char(string="Назва", default="Пульт емулятора", required=True)
    state = fields.Selection(
        [
            ("unconfigured", "Не налаштовано"),
            ("offline", "Офлайн"),
            ("online", "Онлайн"),
            ("locked", "Стоп-кран сервісу"),
            ("degraded", "Частково"),
        ],
        string="Стан сервісу",
        default="unconfigured",
        readonly=True,
        tracking=True,
    )
    last_contact = fields.Datetime(string="Останній контакт", readonly=True)
    last_error = fields.Char(string="Остання помилка", readonly=True)
    version = fields.Char(string="Версія сервісу", readonly=True)
    mode = fields.Selection(MODES, string="Режим", readonly=True)
    mode_new = fields.Selection(
        MODES, string="Новий режим", default=lambda self: self._sim_param("mode", "follow_odoo") or "follow_odoo"
    )
    factor = fields.Float(string="Прискорення (факт)", digits=(6, 2), readonly=True)
    factor_new = fields.Float(string="Нове прискорення", default=1.0)
    sim_time = fields.Datetime(string="Час емулятора", readonly=True)
    uptime_s = fields.Integer(string="Аптайм, с", readonly=True)
    seed = fields.Integer(string="Зерно", readonly=True)
    active_run_ids = fields.One2many(
        "td.sim.run", "panel_id", string="Активні запуски", domain=[("state", "in", ACTIVE_RUN_STATES)]
    )
    alarm_count = fields.Integer(string="Сигналів у тривозі", readonly=True)
    device_count = fields.Integer(string="Пристроїв", compute="_compute_counts")
    signal_count = fields.Integer(string="Сигналів", compute="_compute_counts")
    protocol_status = fields.Json(string="Стан протоколів", readonly=True)
    odoo_stale = fields.Boolean(string="Дані Odoo застарілі (follow_odoo)", readonly=True)
    level0_state = fields.Selection(
        [
            ("auto_off", "Авто: вимкнено (сервіс онлайн)"),
            ("auto_on", "Авто: увімкнено (сервіс офлайн)"),
            ("forced_on", "Примусово увімкнено"),
            ("forced_off", "Примусово вимкнено"),
        ],
        string="Рівень 0",
        default="auto_off",
        tracking=True,
    )
    level0_signal_count = fields.Integer(string="Сигналів рівня 0", compute="_compute_counts")
    scenario_ids = fields.Many2many("td.sim.scenario", string="Сценарії", compute="_compute_scenarios")
    read_enabled = fields.Boolean(compute="_compute_flags")
    write_enabled = fields.Boolean(compute="_compute_flags")

    # --- compute / constraints ---
    @api.depends_context("uid")
    def _compute_counts(self):
        devices = self.env["td.sim.device"].search_count([])
        signals = self.env["td.sim.signal"].search_count([])
        level0 = 0
        if "x_f3d_signal" in self.env:
            level0 = self.env["x_f3d_signal"].sudo().search_count([])
        for rec in self:
            rec.device_count = devices
            rec.signal_count = signals
            rec.level0_signal_count = level0

    def _compute_scenarios(self):
        scenarios = self.env["td.sim.scenario"].search([])
        for rec in self:
            rec.scenario_ids = scenarios

    def _compute_flags(self):
        read, write = self._sim_flag("read_enabled"), self._sim_flag("write_enabled")
        for rec in self:
            rec.read_enabled = read
            rec.write_enabled = write

    @api.constrains("factor_new")
    def _check_factor(self):
        for rec in self:
            if not 0.1 <= rec.factor_new <= 60:
                raise ValidationError("Прискорення має бути від 0,1 до 60")

    @api.constrains("name")
    def _check_single(self):
        if self.sudo().search_count([]) > 1:
            raise ValidationError("Пульт емулятора може бути лише один")

    # --- доступ ---
    @api.model
    def get_panel(self):
        panel = self.search([], limit=1)
        if not panel:
            panel = self.browse(self.sudo().create({}).id)
        return panel

    # --- зв'язок ---
    def _notify(self, message, kind="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": "Емулятор", "message": message, "type": kind, "sticky": False},
        }

    def _poll(self):
        """GET /status → _apply_status; помилка → offline, порожній url → unconfigured (§5.3 п.7).
        Повертає текст помилки або ''."""
        self.ensure_one()
        if not (self._sim_param("url") or "").strip():
            self.sudo().write({"state": "unconfigured", "last_error": False})
            return "Адресу сервісу емулятора не налаштовано (Налаштування → Емулятор обладнання)"
        try:
            payload = self._sim_get("/status")
        except UserError as exc:
            self.sudo().write({"state": "offline", "last_error": str(exc.args[0])[:250]})
            return str(exc.args[0])
        self._apply_status(payload)
        return ""

    def action_check(self):
        self.ensure_one()
        error = self._poll()
        self._sync_level0()
        if error:
            return self._notify(error, "danger")
        return self._notify("Сервіс емулятора: %s" % dict(self._fields["state"].selection)[self.state])

    def _apply_status(self, payload):
        self.ensure_one()
        payload = payload or {}
        protocols = payload.get("protocols") or {}
        state = "online"
        if payload.get("enabled") is False:
            state = "locked"
        elif any(v != "ok" for v in protocols.values()):
            state = "degraded"
        odoo_info = payload.get("odoo") or {}
        self.sudo().write(
            {
                "state": state,
                "last_contact": fields.Datetime.now(),
                "last_error": False,
                "version": payload.get("version"),
                "mode": payload.get("mode") or False,
                "factor": payload.get("factor") or 0.0,
                "sim_time": parse_iso_utc(payload.get("sim_now") or payload.get("sim_time")),
                "uptime_s": payload.get("uptime_s") or 0,
                "seed": payload.get("seed") or 0,
                "alarm_count": payload.get("alarms", payload.get("alarm_count")) or 0,
                "protocol_status": protocols,
                "odoo_stale": bool(odoo_info.get("stale", payload.get("odoo_stale"))),
            }
        )
        self._sync_runs(payload.get("runs") or [])
        self._sync_device_faults(payload.get("devices_fault") or [])

    def _sync_runs(self, runs):
        Run = self.env["td.sim.run"].sudo()
        for item in runs:
            run = (
                Run.search(["|", ("sim_run_id", "=", item.get("id")), ("name", "=", item.get("run_ref"))], limit=1)
                if (item.get("id") or item.get("run_ref"))
                else Run
            )
            state = item.get("state")
            if run and state in ("queued", "running", "stopping") and run.state != state:
                run.state = state

    def _sync_device_faults(self, codes):
        Device = self.env["td.sim.device"].sudo()
        now = fields.Datetime.now()
        in_fault = Device.search([("code", "in", codes)]) if codes else Device
        in_fault.filtered(lambda d: d.state != "fault").write({"state": "fault", "last_update": now})
        healed = Device.search([("state", "=", "fault"), ("id", "not in", in_fault.ids)])
        healed.write({"state": "ok", "fault_reason": False, "last_update": now})

    # --- команди ---
    def action_apply_factor(self):
        self.ensure_one()
        self._sim_require_write()
        if self.mode == "follow_odoo" and self.factor_new != 1:
            raise UserError("У режимі «За Odoo» прискорення фіксовано 1 (A-12)")
        self._sim_post("/time", json={"factor": self.factor_new})
        self.sudo().factor = self.factor_new
        self.message_post(body="Прискорення часу: %s" % self.factor_new)
        return self._notify("Прискорення застосовано")

    def action_apply_mode(self):
        self.ensure_one()
        self._sim_require_write()
        self._sim_post("/mode", json={"mode": self.mode_new})
        self.sudo().mode = self.mode_new
        self.message_post(body="Режим емулятора: %s" % dict(MODES)[self.mode_new])
        if self.mode_new == "follow_odoo":
            self.factor_new = 1.0
            self.action_apply_factor()
        return self._notify("Режим застосовано")

    def action_reset(self):
        self.ensure_one()
        self._sim_require_write()
        self._sim_post("/reset", json={"keep_time": True})
        self.env["td.sim.run"].sudo().search([("state", "in", ACTIVE_RUN_STATES)]).write(
            {"state": "stopped", "stop_ts": fields.Datetime.now()}
        )
        self.message_post(body="Стан емулятора скинуто")
        return self._notify("Стан емулятора скинуто")

    def action_stop_all(self):
        self.ensure_one()
        self._sim_require_write()
        self._sim_post("/stop-all")
        self.sudo().state = "locked"
        self.message_post(body="Стоп-кран сервісу: усе зупинено")
        return self._notify("Сервіс зупинено", "warning")

    # --- рівень 0 ---
    def action_level0_force_on(self):
        self.write({"level0_state": "forced_on"})
        self._sync_level0()

    def action_level0_force_off(self):
        self.write({"level0_state": "forced_off"})
        self._sync_level0()

    def action_level0_auto(self):
        self.write({"level0_state": "auto_off" if self.state == "online" else "auto_on"})
        self._sync_level0()

    def _sync_level0(self):
        self.ensure_one()
        cron = self.env.ref("td_iot_sim.cron_iot_sim", raise_if_not_found=False)
        if not cron:
            return
        cron = cron.sudo()
        new_state, active = self.level0_state, cron.active
        if new_state == "forced_on":
            active = True
        elif new_state == "forced_off":
            active = False
        elif self.state == "online":
            active, new_state = False, "auto_off"
        else:
            try:
                after = int(self._sim_param("level0_after_min", "5") or 5)
            except ValueError:
                after = 5
            since = self.last_contact or self.create_date
            offline_long = since and fields.Datetime.now() - since >= timedelta(minutes=after)
            if self._sim_flag("level0_enabled") and offline_long:
                active, new_state = True, "auto_on"
        changed = []
        if cron.active != active:
            cron.active = active
            changed.append("крон рівня 0 %s" % ("увімкнено" if active else "вимкнено"))
        if new_state != self.level0_state:
            self.sudo().level0_state = new_state
            changed.append("стан рівня 0: %s" % dict(self._fields["level0_state"].selection)[new_state])
        if changed:
            self.message_post(body="; ".join(changed))

    @api.model
    def _cron_poll_status(self):
        panel = self.sudo().get_panel()
        if not (self._sim_param("url") or "").strip():
            if panel.state != "unconfigured":
                panel.write({"state": "unconfigured", "last_error": False})
        elif self._sim_flag("read_enabled"):
            panel._poll()
        elif panel.state in ("online", "degraded", "locked"):
            panel.state = "offline"
        panel._sync_level0()

    # --- навігація ---
    def action_open_signals(self):
        return self._open_model("td.sim.signal", "Каталог сигналів")

    def action_open_devices(self):
        return self._open_model("td.sim.device", "Пристрої")

    def _open_model(self, model, name):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": model,
            "view_mode": "list,form",
            "target": "current",
        }

    def action_refresh_signals(self):
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        last = parse_iso_utc(ICP.get_param("td.iot_sim.last_signals_refresh"))
        now = fields.Datetime.now()
        if last and now - last < timedelta(seconds=60):
            raise UserError("Оновлення сигналів — не частіше ніж раз на хвилину")
        ICP.set_param("td.iot_sim.last_signals_refresh", now.isoformat())
        Signal = self.env["td.sim.signal"].sudo()
        offset, limit = 0, 1000
        while True:
            data = self._sim_get("/signals", params={"limit": limit, "offset": offset})
            items = data.get("items", []) if isinstance(data, dict) else (data or [])
            by_code = {s.code: s for s in Signal.search([("code", "in", [i.get("code") for i in items])])}
            for item in items:
                sig = by_code.get(item.get("code"))
                if sig:
                    sig.write(
                        {
                            "last_value": item.get("value") if isinstance(item.get("value"), (int, float)) else 0.0,
                            "last_status": item.get("status")
                            if item.get("status") in ("ok", "warn", "alarm", "stale")
                            else False,
                            "last_ts": parse_iso_utc(item.get("ts")),
                        }
                    )
            if len(items) < limit:
                break
            offset += limit
        return self._notify("Сигнали оновлено")
