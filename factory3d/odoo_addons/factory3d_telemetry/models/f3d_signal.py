import json
import re
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import address as address_tools
from ..tools import sim_catalog
from ..tools import thresholds
from ..tools.ingest import STATUS_LABELS, Ingester
from ..tools.titles import fmt_num, render_title
from .f3d_source import F3dSource

KYIV = ZoneInfo("Europe/Kyiv")
ETAG_FIELDS = {
    "address",
    "address_text",
    "period_s",
    "scale",
    "source_id",
    "active",
    "write_enabled",
    "states",
    "kind",
    "unit",
    "decimals",
    "code",
}
THRESHOLD_FIELDS = {
    "warn_low",
    "warn_high",
    "alarm_low",
    "alarm_high",
    "warn_low_on",
    "warn_high_on",
    "alarm_low_on",
    "alarm_high_on",
    "hysteresis",
    "alarm_states",
    "kind",
}
COV_DEFAULT_OBJECTS = {
    "analog-input",
    "binary-input",
    "multi-state-input",
    "multi-state-value",
    "life-safety-zone",
    "life-safety-point",
    "AI",
    "BI",
    "MSI",
    "MSV",
    "LSZ",
    "LSP",
}


def _split_csv(text):
    return [p.strip() for p in (text or "").split(",") if p.strip()]


class F3dSignal(models.Model):
    _name = "f3d.signal"
    _description = "Телеметрія: сигнал"
    _inherit = ["mail.thread"]
    _order = "sequence, code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^[a-z_]+(/[A-Za-z0-9_\-\.]+)+$")
    KINDS = [("gauge", "Величина"), ("counter", "Лічильник"), ("state", "Стан"), ("event", "Подія")]
    STATUSES = [
        ("unknown", "Невідомо"),
        ("ok", "Норма"),
        ("warn", "Увага"),
        ("alarm", "Тривога"),
        ("stale", "Немає даних"),
    ]

    code = fields.Char(string="Код (шлях)", required=True, index=True, copy=False, tracking=True)
    name = fields.Char(string="Назва", required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    quantity = fields.Char(string="Величина")
    kind = fields.Selection(KINDS, string="Вид", required=True, default="gauge", tracking=True)
    unit = fields.Char(string="Одиниця")
    states = fields.Json(string="Допустимі стани")
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Обладнання", ondelete="set null", index=True, tracking=True
    )
    equipment_code = fields.Char(string="Код обладнання", related="equipment_id.f3d_code")
    workcenter_id = fields.Many2one("mrp.workcenter", string="Робочий центр", ondelete="set null")
    source_id = fields.Many2one("f3d.source", string="Джерело", ondelete="set null", index=True, tracking=True)
    source_type = fields.Selection(related="source_id.type")
    collector_id = fields.Many2one("f3d.collector", related="source_id.collector_id", store=True, index=True)
    address = fields.Json(string="Адреса в джерелі", default=lambda self: {})
    address_text = fields.Text(string="Адреса (JSON)", compute="_compute_address_text", inverse="_inverse_address_text")
    period_s = fields.Integer(string="Період, с", default=10)
    store_period_s = fields.Integer(
        string="Зберігати не частіше, с",
        default=lambda self: int(
            self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.default_store_period_s", "300")
        ),
    )
    scale = fields.Float(
        string="Множник",
        digits=(16, 6),
        default=1.0,
        help="Множник сигналу: ядро колектора один раз множить на нього інженерне значення, яке повернув "
        "плагін (масштаб і зсув адреси плагін уже застосував). R-02.",
    )
    decimals = fields.Integer(string="Знаків після коми", default=2)
    nominal = fields.Float(string="Номінал")
    warn_low = fields.Float(string="Увага, нижче", tracking=True)
    warn_high = fields.Float(string="Увага, вище", tracking=True)
    alarm_low = fields.Float(string="Тривога, нижче", tracking=True)
    alarm_high = fields.Float(string="Тривога, вище", tracking=True)
    warn_low_on = fields.Boolean(default=False)
    warn_high_on = fields.Boolean(default=False)
    alarm_low_on = fields.Boolean(default=False)
    alarm_high_on = fields.Boolean(default=False)
    hysteresis = fields.Float(string="Гістерезис", default=0.0)
    min_duration_s = fields.Integer(string="Мінімальна тривалість, с", default=0)
    alarm_states = fields.Json(string="Стани-тривоги")
    alarm_title = fields.Char(string="Заголовок заявки")
    alarm_priority = fields.Selection(
        [("0", "Дуже низький"), ("1", "Низький"), ("2", "Звичайний"), ("3", "Високий")],
        default="2",
        string="Пріоритет заявки",
    )
    create_request = fields.Boolean(string="Створювати заявку ТО", default=True)
    write_enabled = fields.Boolean(string="Дозволити запис", default=False, tracking=True)
    viewer_visible = fields.Boolean(string="Показувати в 3D", default=True)
    last_value = fields.Float(string="Останнє значення", readonly=True)
    last_text = fields.Char(string="Останній стан", readonly=True)
    last_ts = fields.Datetime(string="Час останнього", readonly=True, index=True)
    last_quality = fields.Selection(
        [("good", "Добра"), ("uncertain", "Непевна"), ("bad", "Погана")], string="Якість", readonly=True
    )
    last_stored_ts = fields.Datetime()
    status = fields.Selection(STATUSES, string="Статус", default="unknown", index=True, readonly=True, tracking=True)
    status_since = fields.Datetime(string="Статус з", readonly=True)
    breach_since = fields.Datetime()
    maintenance_request_id = fields.Many2one(
        "maintenance.request", string="Відкрита заявка", ondelete="set null", readonly=True, copy=False
    )
    request_closed_at = fields.Datetime()
    last_notified_ts = fields.Datetime()
    origin = fields.Selection(
        [
            ("sim_data", "Рівень 0 (макет)"),
            ("catalog", "Каталог емулятора"),
            ("manual", "Вручну"),
            ("module", "Дані модуля"),
        ],
        default="manual",
        string="Походження",
    )
    module = fields.Selection(F3dSource.MODULES, string="Модуль-власник", default="telemetry", index=True)
    derived_from_id = fields.Many2one("f3d.signal", string="Похідний від", ondelete="set null")
    derive_rule = fields.Selection(
        [("none", "—"), ("rate_h", "Швидкість за годину (Δ/Δt)")], default="none", string="Правило похідної"
    )
    sim_mode = fields.Char(string="Режим макета")
    sim_params = fields.Json(string="Параметри макета")
    note = fields.Text(string="Примітка")
    reading_count = fields.Integer(string="Показань за 2 доби", compute="_compute_reading_count")
    meter_equipment_ids = fields.One2many("maintenance.equipment", "f3d_meter_signal_id", string="ТО за лічильником")
    is_f3d_manager = fields.Boolean(compute="_compute_is_f3d_manager")
    states_text = fields.Char(
        string="Допустимі стани (через кому)", compute="_compute_states_text", inverse="_inverse_states_text"
    )
    alarm_states_text = fields.Char(
        string="Стани-тривоги (через кому)", compute="_compute_states_text", inverse="_inverse_alarm_states_text"
    )
    sim_params_text = fields.Text(compute="_compute_sim_params_text")

    _f3d_signal_code_uniq = models.Constraint("UNIQUE(code)", "Код сигналу має бути унікальним.")
    _f3d_signal_periods = models.Constraint(
        "CHECK(period_s >= 1 AND store_period_s >= 0 AND min_duration_s >= 0 AND hysteresis >= 0)",
        "Період ≥ 1 с, інтервал зберігання ≥ 0, тривалість і гістерезис ≥ 0.",
    )

    # --- обчислювані ---------------------------------------------------------------------------------
    @api.depends("name", "code")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s (%s)" % (rec.name, rec.code) if rec.code else (rec.name or "")

    @api.depends("address")
    def _compute_address_text(self):
        for rec in self:
            rec.address_text = json.dumps(rec.address, ensure_ascii=False, indent=2) if rec.address else "{}"

    def _inverse_address_text(self):
        for rec in self:
            try:
                rec.address = json.loads(rec.address_text) if (rec.address_text or "").strip() else {}
            except ValueError as e:
                raise ValidationError(_("Адреса (JSON): %s", e)) from e

    @api.depends("states", "alarm_states")
    def _compute_states_text(self):
        for rec in self:
            rec.states_text = ", ".join(rec.states or [])
            rec.alarm_states_text = ", ".join(rec.alarm_states or [])

    def _inverse_states_text(self):
        for rec in self:
            rec.states = _split_csv(rec.states_text) or False

    def _inverse_alarm_states_text(self):
        for rec in self:
            rec.alarm_states = _split_csv(rec.alarm_states_text) or False

    @api.depends("sim_params")
    def _compute_sim_params_text(self):
        for rec in self:
            rec.sim_params_text = json.dumps(rec.sim_params or {}, ensure_ascii=False, indent=2)

    def _compute_is_f3d_manager(self):
        is_manager = self.env.user.has_group("factory3d_base.group_f3d_manager")
        for rec in self:
            rec.is_f3d_manager = is_manager

    def _compute_reading_count(self):
        counts = {}
        if self.ids:
            since = fields.Datetime.now() - timedelta(hours=48)
            for sig, count in (
                self.env["f3d.reading"]
                .sudo()
                ._read_group([("signal_id", "in", self.ids), ("ts", ">=", since)], ["signal_id"], ["__count"])
            ):
                counts[sig.id] = count
        for rec in self:
            rec.reading_count = counts.get(rec.id, 0)

    # --- перевірки -----------------------------------------------------------------------------------
    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or len(rec.code) > 128 or not self.CODE_RE.match(rec.code):
                raise ValidationError(
                    _(
                        "Код сигналу %s: шлях виду energy/consumers/SAW-1/p_now (малі літери групи, далі сегменти "
                        "через /).",
                        rec.code,
                    )
                )

    @api.constrains("source_id", "address")
    def _check_address(self):
        local = self.env["f3d.source"]._f3d_local_types()
        for rec in self:
            if rec.source_id and rec.address:
                errors = address_tools.validate_address(rec.source_id.type, rec.address, local)
                if errors:
                    raise ValidationError(_("Адреса сигналу %s: %s", rec.code, "; ".join(errors)))

    @api.constrains(
        "warn_low_on",
        "warn_low",
        "alarm_low_on",
        "alarm_low",
        "warn_high_on",
        "warn_high",
        "alarm_high_on",
        "alarm_high",
    )
    def _check_thresholds(self):
        for rec in self:
            if rec.alarm_low_on and rec.warn_low_on and rec.alarm_low > rec.warn_low:
                raise ValidationError(_("«Тривога, нижче» має бути ≤ «Увага, нижче»."))
            if rec.alarm_high_on and rec.warn_high_on and rec.alarm_high < rec.warn_high:
                raise ValidationError(_("«Тривога, вище» має бути ≥ «Увага, вище»."))
            if rec.alarm_low_on and rec.alarm_high_on and rec.alarm_low >= rec.alarm_high:
                raise ValidationError(_("«Тривога, нижче» має бути < «Тривога, вище»."))

    @api.constrains(
        "kind", "warn_low_on", "warn_high_on", "alarm_low_on", "alarm_high_on", "derive_rule", "derived_from_id"
    )
    def _check_kind(self):
        for rec in self:
            if rec.kind == "state" and (rec.warn_low_on or rec.warn_high_on or rec.alarm_low_on or rec.alarm_high_on):
                raise ValidationError(_("Для стану задайте «Стани-тривоги», а не числові пороги."))
            if rec.derive_rule == "rate_h" and (not rec.derived_from_id or rec.derived_from_id.kind != "counter"):
                raise ValidationError(_("Похідна «за годину» потребує лічильника-джерела."))

    @api.constrains("write_enabled", "source_id")
    def _check_write_enabled(self):
        for rec in self:
            src = rec.source_id
            if (
                rec.write_enabled
                and src
                and src.type == "bacnet_ip"
                and isinstance(src.params, dict)
                and src.params.get("read_only")
            ):
                raise ValidationError(_("Запис у пожежну панель заборонено (D-07)."))

    # --- запис ---------------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env["f3d.source"]._reset_etag(records.collector_id)
        return records

    def write(self, vals):
        reset = bool(ETAG_FIELDS & set(vals))
        collectors = self.collector_id if reset else self.env["f3d.collector"]
        res = super().write(vals)
        if reset:
            self.env["f3d.source"]._reset_etag(collectors | self.collector_id)
        if THRESHOLD_FIELDS & set(vals):
            self._recompute_status()
        return res

    def unlink(self):
        used = self.meter_equipment_ids
        if used:
            raise UserError(_("Сигнал використовується для ТО за лічильником на %s.", ", ".join(used.mapped("name"))))
        return super().unlink()

    def _f3d_cfg(self):
        self.ensure_one()
        cfg = {f: self[f] for f in thresholds.CFG_FIELDS}
        cfg["alarm_states"] = self.alarm_states or []
        return cfg

    def _recompute_status(self):
        """R-04 при зміні порогів: статус з `last_value` без мін. тривалості, без нової заявки."""
        now = fields.Datetime.now()
        for rec in self.filtered(lambda r: r.last_ts and r.status in ("ok", "warn", "alarm")):
            new, _since = thresholds.eval_status(
                {"status": rec.status, "breach_since": False},
                rec.last_value,
                rec.last_text,
                now,
                rec._f3d_cfg(),
                ignore_min_duration=True,
            )
            if new != rec.status:
                old = rec.status
                rec.with_context(mail_notrack=True).write({"status": new, "status_since": now, "breach_since": False})
                rec.message_post(body=rec._status_message(old, new), subtype_xmlid="mail.mt_note")

    def _status_message(self, old, new):
        self.ensure_one()
        if self.kind == "state":
            detail = self.last_text or ""
        else:
            detail = ("%s %s" % (fmt_num(self.last_value, self.decimals), self.unit or "")).strip()
        return "Стан: %s → %s%s" % (
            STATUS_LABELS.get(old, old),
            STATUS_LABELS.get(new, new),
            " (%s)" % detail if detail else "",
        )

    # --- інгест (CT-10) ------------------------------------------------------------------------------
    @api.model
    def _f3d_ingest(self, readings, src="module", collector=None):
        """Єдиний вхід показань (API-02/API-05 з src='collector', модулі — src='module'). R-17."""
        return Ingester(self.env, src=src, collector=collector).run(readings)

    # --- каталог емулятора (CT-11, R-24) -------------------------------------------------------------
    SIM_ROW_FIELDS = ("code", "name", "protocol", "address", "dtype", "unit", "scale", "nominal", "thresholds", "kind")

    @api.model
    def _f3d_import_sim_catalog(self, codes=None, module=None, source_map=None, defaults=None):
        """CT-11: імпорт `f3d.sim.signal` (iot_sim ≥ 2.0.0); без моделі — нулі й `state='skipped'`."""
        if "f3d.sim.signal" not in self.env:
            return {"created": 0, "updated": 0, "unparsed": [], "skipped": [], "state": "skipped"}
        sims = self.env["f3d.sim.signal"].sudo().search([("code", "in", list(codes))] if codes is not None else [])
        if module:
            sims = sims.filtered(lambda s: sim_catalog.module_for_code(s.code) == module)
        rows = [{f: s[f] or "" for f in self.SIM_ROW_FIELDS} for s in sims]
        return self._f3d_import_sim_rows(rows, source_map or {}, defaults or {})

    @api.model
    def _f3d_import_sim_rows(self, rows, source_map, defaults):
        """Ядро CT-11: рядки каталогу → створення/оновлення сигналів (адреса, `sim_params`, `nominal`).

        Існуючий сигнал: `address` лише якщо порожня, `source_id` лише якщо порожній, `sim_params` — додаються
        відсутні ключі; `last_*` не чіпаються. Новий — `origin` з `defaults` (умовчання `catalog`)."""
        Signal = self.sudo().with_context(active_test=False, tracking_disable=True, mail_create_nolog=True)
        Source = self.env["f3d.source"].sudo().with_context(active_test=False)
        local = self.env["f3d.source"]._f3d_local_types()
        result = {"created": 0, "updated": 0, "unparsed": [], "skipped": []}
        origin = defaults.get("origin")
        origin = origin if origin in ("sim_data", "catalog", "manual", "module") else "catalog"
        for row in rows:
            code = row.get("code")
            if not code or len(code) > 128 or not self.CODE_RE.match(code):
                result["skipped"].append(code)
                continue
            text = row.get("address") or ""
            address = sim_catalog.parse_sim_address(
                row.get("protocol"), text, row.get("dtype"), row.get("scale"), row.get("unit")
            )
            if address is None:
                result["unparsed"].append(code)
                continue
            sig = Signal.search([("code", "=", code)], limit=1)
            src_code = source_map.get(sim_catalog.source_key(text))
            source = sig.source_id or (Source.search([("code", "=", src_code)], limit=1) if src_code else Source)
            if source and address_tools.validate_address(source.type, address, local):
                result["unparsed"].append(code)
                continue
            nominal = sim_catalog.parse_nominal(row.get("nominal"))
            params = {
                k: v
                for k, v in (
                    ("nominal", nominal),
                    ("thresholds", row.get("thresholds") or None),
                    ("catalog_address", text),
                )
                if v is not None
            }
            if sig:
                vals = {}
                if not sig.address:
                    vals["address"] = address
                if not sig.source_id and source:
                    vals["source_id"] = source.id
                if nominal is not None and not sig.nominal:
                    vals["nominal"] = nominal
                merged = {**params, **(sig.sim_params or {})}
                if merged != (sig.sim_params or {}):
                    vals["sim_params"] = merged
                if vals:
                    sig.write(vals)
                result["updated"] += 1
                continue
            vals = {
                "code": code,
                "name": row.get("name") or code,
                "origin": origin,
                "address": address,
                "module": defaults.get("module") or sim_catalog.module_for_code(code),
                "sim_params": params,
                "source_id": source.id if source else False,
                "nominal": nominal or 0.0,
            }
            if row.get("kind") in ("gauge", "counter", "state", "event"):
                vals["kind"] = row["kind"]
            if row.get("unit") and not sim_catalog.parse_enum_map(row["unit"]):
                vals["unit"] = row["unit"]
            if vals.get("kind") == "state" and isinstance(address.get("map"), dict):
                vals["states"] = list(dict.fromkeys(address["map"].values()))
            eq_code = sim_catalog.equipment_code(code)
            equipment = self.env["maintenance.equipment"].sudo().search_f3d(eq_code) if eq_code else False
            if equipment:
                vals["equipment_id"] = equipment.id
            Signal.create(vals)
            result["created"] += 1
        return result

    @api.model
    def f3d_run_migration(self):
        """Дія «Повторити міграцію рівня 0» (§5.3): лише `group_f3d_admin`."""
        if not self.env.user.has_group("factory3d_base.group_f3d_admin"):
            raise AccessError(_("Запускати міграцію може лише адміністратор «Завод 3D»."))
        from .. import hooks  # noqa: PLC0415

        data = hooks.run_migration(self.sudo().env)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Міграція рівня 0"),
                "message": _("Міграцію виконано: %s", json.dumps(data, ensure_ascii=False)),
                "type": "success",
                "sticky": True,
            },
        }

    def _apply_reading(self, ts, value, text, quality):
        """Нові значення last_*/status* для показання (у пам'яті, без запису)."""
        self.ensure_one()
        vals = {}
        if quality != "bad" and (not self.last_ts or ts > self.last_ts):
            vals.update(
                last_value=value if value is not None else self.last_value,
                last_text=text or self.last_text,
                last_ts=ts,
                last_quality=quality,
            )
            status, since = thresholds.eval_status(
                {"status": self.status, "breach_since": self.breach_since},
                value,
                text,
                ts,
                self._f3d_cfg(),
                quality=quality,
            )
            vals.update(breach_since=since)
            if status != self.status:
                vals.update(status=status, status_since=ts)
        return vals

    # --- заявки ТО (R-05, R-06) ----------------------------------------------------------------------
    def _open_request(self, value, text, ts):
        """R-05: заявка ТО за тривогою. Поля `f3d_*` заявки пише лише якщо вони є (їх додає M-08)."""
        self.ensure_one()
        eq = self.equipment_id
        icp = self.env["ir.config_parameter"].sudo()
        threshold, rel = thresholds.breach_info(self._f3d_cfg(), value)
        team = eq.maintenance_team_id
        if not team and (icp.get_param("factory3d.telemetry.default_team_id") or "").isdigit():
            team = self.env["maintenance.team"].browse(int(icp.get_param("factory3d.telemetry.default_team_id")))
        local_ts = ts.replace(tzinfo=timezone.utc).astimezone(KYIV).strftime("%d.%m.%Y %H:%M")
        source = self.source_id.code or ""
        if self.kind == "state":
            what = "стан «%s»" % (text or "")
        else:
            what = "показник %s %s %s порогу %s %s" % (
                fmt_num(value, self.decimals),
                self.unit or "",
                rel,
                fmt_num(threshold, self.decimals),
                self.unit or "",
            )
        vals = {
            "name": render_title(self, value, rel, threshold, text),
            "equipment_id": eq.id,
            "maintenance_type": "corrective",
            "maintenance_team_id": team.id if team else False,
            "priority": self.alarm_priority or "2",
            "description": "Автоматично з телеметрії: сигнал %s, %s, джерело %s, час %s."
            % (self.code, re.sub(r"\s+", " ", what).strip(), source, local_ts),
            "request_date": fields.Date.today(),
            "schedule_date": fields.Datetime.now(),
        }
        Request = self.env["maintenance.request"].sudo()
        extra = {"f3d_signal_id": self.id, "f3d_origin": "threshold", "f3d_value": value, "f3d_threshold": threshold}
        vals.update({k: v for k, v in extra.items() if k in Request._fields and v is not None})
        request = Request.create(vals)
        self.sudo().with_context(mail_notrack=True).write({"maintenance_request_id": request.id})
        self.message_post(body=_("Створено заявку %s", request.name), subtype_xmlid="mail.mt_note")
        return request

    def _on_request_closed(self, request):
        """R-06: заявку закрито — звільнити сигнал, перерахувати статус без мін. тривалості."""
        now = fields.Datetime.now()
        cooldown = int(
            self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.realarm_cooldown_s", "3600") or 3600
        )
        for rec in self:
            vals = {}
            if rec.maintenance_request_id == request:
                vals.update(maintenance_request_id=False, request_closed_at=now)
            status = rec.status
            if rec.last_ts and status in ("ok", "warn", "alarm"):
                new, _since = thresholds.eval_status(
                    {"status": status, "breach_since": False},
                    rec.last_value,
                    rec.last_text,
                    now,
                    rec._f3d_cfg(),
                    ignore_min_duration=True,
                )
                if new != status:
                    vals.update(status=new, status_since=now, breach_since=False)
                    status = new
            if vals:
                rec.sudo().with_context(mail_notrack=True).write(vals)
            label = dict(self.STATUSES).get(status, status)
            body = _("Заявку %s закрито; стан: %s", request.name, label)
            if status == "alarm":
                until = (now + timedelta(seconds=cooldown)).replace(tzinfo=timezone.utc).astimezone(KYIV)
                body += _(". Тривога триває, нова заявка не раніше %s", until.strftime("%d.%m.%Y %H:%M"))
            rec.message_post(body=body, subtype_xmlid="mail.mt_note")

    # --- stale (R-07) --------------------------------------------------------------------------------
    def _f3d_stale_after(self):
        """Вікно stale сигналу в секундах; для COV-сигналів BACnet — від `cov_check_s` (X-06)."""
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()
        periods = int(icp.get_param("factory3d.telemetry.stale_periods", "3") or 3)
        min_s = int(icp.get_param("factory3d.telemetry.stale_min_s", "60") or 60)
        p = self.period_s
        src = self.source_id
        if src and src.type == "bacnet_ip" and not (src.params or {}).get("read_only"):
            addr = self.address or {}
            mode = addr.get("mode")
            if mode == "cov" or (mode is None and addr.get("object") in COV_DEFAULT_OBJECTS):
                p = thresholds.cov_check_s(self.period_s)
        return max(periods * p, min_s)

    def _mark_stale(self, reason):
        now = fields.Datetime.now()
        for rec in self:
            if rec.status in ("unknown", "stale"):
                continue
            rec.sudo().with_context(mail_notrack=True).write({"status": "stale", "status_since": now})
            rec.message_post(body=_("Немає даних: %s", reason), subtype_xmlid="mail.mt_note")

    @api.model
    def _cron_stale(self):
        """R-07: сигнали без свіжих показань → stale; далі колектори офлайн (R-25)."""
        now = fields.Datetime.now()
        min_s = int(self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.stale_min_s", "60") or 60)
        local = self.env["f3d.source"]._f3d_local_types()
        cands = self.sudo().search(
            [
                ("status", "in", ("ok", "warn", "alarm")),
                ("source_id", "!=", False),
                ("source_id.type", "not in", local),
                ("last_ts", "<", now - timedelta(seconds=min_s)),
            ],
            limit=2000,
        )
        stale = cands.filtered(lambda s: s.last_ts < now - timedelta(seconds=s._f3d_stale_after()))
        stale._mark_stale("timeout")
        self.env["f3d.collector"]._cron_offline()

    # --- шина, дії -----------------------------------------------------------------------------------
    def _notify_viewer(self, codes):
        if "f3d.viewer.event" in self.env:
            self.env["f3d.viewer.event"]._notify("f3d.signal", codes, "signal")

    def action_test_address(self):
        self.ensure_one()
        errors = []
        if self.source_id:
            errors = address_tools.validate_address(
                self.source_id.type, self.address or {}, self.env["f3d.source"]._f3d_local_types()
            )
        message, kind = ("; ".join(errors), "danger") if errors else (_("Адреса коректна"), "success")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Перевірка адреси"), "message": message, "type": kind, "sticky": False},
        }

    def action_view_readings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Показання"),
            "res_model": "f3d.reading",
            "view_mode": "graph,list",
            "domain": [("signal_id", "=", self.id)],
            "context": {"search_default_last_48h": 1},
        }

    def action_open_request(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "maintenance.request",
            "view_mode": "form",
            "res_id": self.maintenance_request_id.id,
        }

    def action_request_write(self):
        self.ensure_one()
        if not self.write_enabled:
            raise UserError(_("Запис у сигнал не дозволено."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Команда на пристрій"),
            "res_model": "f3d.command",
            "view_mode": "form",
            "target": "new",
            "context": {"default_signal_id": self.id},
        }
