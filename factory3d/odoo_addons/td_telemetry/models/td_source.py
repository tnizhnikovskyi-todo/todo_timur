import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import address as address_tools
from ..tools.ingest import parse_ts

MASK_RE = re.compile(r"(?i)(password=|token=|bearer\s+)\S+")
CONFIG_FIELDS = {"params", "params_text", "read_enabled", "write_enabled", "active", "type", "collector_id"}

DEFAULT_ADDRESS = {
    "modbus_tcp": {"fc": 3, "addr": 0, "type": "u16"},
    "mqtt": {"topic": "f3d/<device>/telemetry", "path": "$.value"},
    "http_push": {"route": "lpr", "path": "$.value"},
    "opcua": {"nodeid": "ns=2;s=Node"},
    "bacnet_ip": {"object": "analog-input", "instance": 1, "property": "present-value"},
    "helvarnet": {"group": 1, "query": "level"},
    "sics": {"field": "weight"},
    "rest_vendor": {"method": "GET", "path": "/api/v1/value", "json_path": "$.value"},
}


class F3dSource(models.Model):
    _name = "f3d.source"
    _description = "Телеметрія: джерело даних"
    _inherit = ["mail.thread"]
    _order = "collector_id, code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-\.]{0,31}$")
    TYPES = [
        ("modbus_tcp", "Modbus TCP"),
        ("mqtt", "MQTT"),
        ("http_push", "HTTP push (приймач)"),
        ("opcua", "OPC UA"),
        ("bacnet_ip", "BACnet/IP"),
        ("helvarnet", "HelvarNet"),
        ("sics", "SICS (ваги)"),
        ("rest_vendor", "REST вендора"),
    ]
    MODULES = [
        ("telemetry", "Телеметрія"),
        ("machine_connect", "Верстати"),
        ("energy", "Енергетика"),
        ("genset", "Генератор"),
        ("bms", "Інженерні системи"),
        ("fire_safety", "Пожежна безпека"),
        ("yard", "Двір"),
        ("access", "СКУД"),
        ("other", "Інше"),
    ]

    code = fields.Char(string="Код", required=True, index=True, copy=False, tracking=True)
    name = fields.Char(string="Назва", required=True)
    active = fields.Boolean(default=True)
    type = fields.Selection(TYPES, string="Тип", required=True, tracking=True)
    collector_id = fields.Many2one("f3d.collector", string="Колектор", ondelete="restrict", index=True, tracking=True)
    is_local = fields.Boolean(string="Локальне (без колектора)", compute="_compute_is_local")
    equipment_id = fields.Many2one(
        "maintenance.equipment",
        string="Обладнання",
        ondelete="set null",
        help="Головна одиниця обладнання (для дашборда)",
    )
    module = fields.Selection(MODULES, string="Модуль-власник", default="telemetry")
    params = fields.Json(string="Параметри", default=lambda self: {})
    params_text = fields.Text(string="Параметри (JSON)", compute="_compute_params_text", inverse="_inverse_params_text")
    read_enabled = fields.Boolean(string="Читати", default=True, tracking=True)
    write_enabled = fields.Boolean(string="Дозволити запис", default=False, tracking=True)
    period_s_default = fields.Integer(string="Період опитування за замовчуванням, с", default=10)
    state = fields.Selection(
        [
            ("unknown", "Невідомо"),
            ("online", "Онлайн"),
            ("offline", "Офлайн"),
            ("error", "Помилка"),
            ("disabled", "Вимкнено"),
        ],
        default="unknown",
        index=True,
        readonly=True,
        tracking=True,
    )
    last_ok = fields.Datetime(string="Остання успішна відповідь", readonly=True)
    last_error = fields.Char(string="Остання помилка", readonly=True)
    error_count = fields.Integer(string="Кількість помилок", readonly=True, default=0)
    stats = fields.Json(string="Статистика", readonly=True)
    signal_ids = fields.One2many("f3d.signal", "source_id", string="Сигнали")
    signal_count = fields.Integer(string="Сигналів", compute="_compute_counts")
    alarm_count = fields.Integer(string="Тривог", compute="_compute_counts")
    stale_count = fields.Integer(string="Без даних", compute="_compute_counts")
    note = fields.Text(string="Примітка")

    _f3d_source_code_uniq = models.Constraint("UNIQUE(code)", "Код джерела має бути унікальним.")
    _f3d_source_period = models.Constraint("CHECK(period_s_default >= 1)", "Період опитування має бути ≥ 1 с.")

    # --- обчислювані ---------------------------------------------------------------------------------
    @api.model
    def _f3d_local_types(self):
        """CT-12, R-26: типи локальних джерел (без колектора). Модулі розширюють через `super()`."""
        return []

    @api.depends("type")
    def _compute_is_local(self):
        local = self._f3d_local_types()
        for rec in self:
            rec.is_local = rec.type in local

    @api.depends("params")
    def _compute_params_text(self):
        for rec in self:
            rec.params_text = json.dumps(rec.params or {}, ensure_ascii=False, indent=2)

    def _inverse_params_text(self):
        for rec in self:
            try:
                rec.params = json.loads(rec.params_text) if (rec.params_text or "").strip() else {}
            except ValueError as e:
                raise ValidationError(_("Параметри (JSON): %s", e)) from e

    @api.depends("signal_ids.status", "signal_ids.active")
    def _compute_counts(self):
        counts = {}
        if self.ids:
            for src, status, count in self.env["f3d.signal"]._read_group(
                [("source_id", "in", self.ids)], ["source_id", "status"], ["__count"]
            ):
                counts.setdefault(src.id, {})[status] = count
        for rec in self:
            by = counts.get(rec.id, {})
            rec.signal_count = sum(by.values())
            rec.alarm_count = by.get("alarm", 0)
            rec.stale_count = by.get("stale", 0)

    # --- перевірки -----------------------------------------------------------------------------------
    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not self.CODE_RE.match(rec.code):
                raise ValidationError(_("Код джерела: великі латинські літери, цифри, дефіс, крапка."))

    @api.constrains("type", "params")
    def _check_params(self):
        local = self._f3d_local_types()
        for rec in self:
            errors = address_tools.validate_params(rec.type, rec.params or {}, local)
            if errors:
                raise ValidationError(_("Параметри джерела %s: %s", rec.code, "; ".join(errors)))

    @api.constrains("type", "write_enabled", "params")
    def _check_read_only(self):
        for rec in self:
            if (
                rec.type == "bacnet_ip"
                and isinstance(rec.params, dict)
                and rec.params.get("read_only")
                and rec.write_enabled
            ):
                raise ValidationError(_("Джерело лише для читання (пожежна панель): запис заборонено."))

    @api.constrains("type", "collector_id")
    def _check_f3d_collector_required(self):
        local = self._f3d_local_types()
        for rec in self:
            if not rec.collector_id and rec.type not in local:
                raise ValidationError(_("Джерело %s: вкажіть колектор.", rec.code))

    # --- запис ---------------------------------------------------------------------------------------
    def write(self, vals):
        if "type" in vals:
            for rec in self.with_context(active_test=False):
                if rec.type != vals["type"] and rec.signal_ids:
                    raise ValidationError(_("Тип джерела з сигналами змінити не можна — створіть нове джерело."))
        reset = bool(CONFIG_FIELDS & set(vals))
        collectors = self.collector_id if reset else self.env["f3d.collector"]
        res = super().write(vals)
        if "read_enabled" in vals:
            if vals["read_enabled"]:
                self.filtered(lambda s: s.state == "disabled").write({"state": "unknown"})
            else:
                self.write({"state": "disabled"})
                self.with_context(active_test=False).signal_ids._mark_stale("disabled")
        if reset:
            self._reset_etag(collectors | self.collector_id)
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._reset_etag(records.collector_id)
        return records

    @api.model
    def _reset_etag(self, collectors):
        collectors = collectors.sudo().filtered("config_etag")
        if collectors:
            collectors.with_context(mail_notrack=True).write({"config_etag": False})

    def _apply_status(self, item):
        """R-25: стан джерела зі звіту колектора (API-03)."""
        self.ensure_one()
        vals = {}
        state = item.get("state")
        if state in ("online", "offline", "error") and self.read_enabled:
            vals["state"] = state
        if item.get("last_ok"):
            ts, reason = parse_ts(item["last_ok"])
            if not reason:
                vals["last_ok"] = ts
        error = item.get("error")
        if error:
            vals["last_error"] = MASK_RE.sub(r"\1***", str(error))[:512]
        elif state in ("online", "offline", "error") or "error" in item:
            vals["last_error"] = False  # невідомий/відсутній state без error не стирає попередню помилку (T-5)
        stats = item.get("stats")
        if isinstance(stats, dict):
            vals["stats"] = stats
            if isinstance(stats.get("errors"), int) and not isinstance(stats.get("errors"), bool):
                vals["error_count"] = stats["errors"]
        self.sudo().write(vals)
        if vals.get("state") in ("offline", "error"):
            self.sudo().with_context(active_test=False).signal_ids._mark_stale(vals["state"])

    def action_view_signals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Сигнали"),
            "res_model": "f3d.signal",
            "view_mode": "list,form",
            "domain": [("source_id", "=", self.id)],
            "context": {"default_source_id": self.id},
        }

    def action_test_params(self):
        self.ensure_one()
        errors = address_tools.validate_params(self.type, self.params or {}, self._f3d_local_types())
        if errors:
            message, kind = "; ".join(errors), "danger"
        else:
            message, kind = _("Параметри коректні"), "success"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Перевірка параметрів"), "message": message, "type": kind, "sticky": False},
        }

    def _default_address(self):
        self.ensure_one()
        return dict(DEFAULT_ADDRESS.get(self.type, {}))
