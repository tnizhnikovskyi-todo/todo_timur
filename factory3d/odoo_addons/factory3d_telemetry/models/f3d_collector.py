import hashlib
import hmac
import json
import re
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

GROUP_ADMIN = "factory3d_base.group_f3d_admin"


class F3dCollector(models.Model):
    _name = "f3d.collector"
    _description = "Телеметрія: колектор"
    _inherit = ["mail.thread"]
    _order = "code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,31}$")

    code = fields.Char(string="Код", required=True, index=True, copy=False, tracking=True)
    name = fields.Char(string="Назва", required=True)
    active = fields.Boolean(default=True)
    token_hash = fields.Char(string="Хеш токена", groups=GROUP_ADMIN, copy=False, readonly=True)
    token_hint = fields.Char(string="Останні символи токена", groups=GROUP_ADMIN, readonly=True)
    token_set_at = fields.Datetime(string="Токен видано", readonly=True)
    version = fields.Char(string="Версія", readonly=True)
    last_seen = fields.Datetime(string="Останній контакт", readonly=True, index=True)
    last_push_at = fields.Datetime(string="Останній пакет", readonly=True)
    last_ip = fields.Char(string="IP", readonly=True)
    state = fields.Selection(
        [("never", "Ще не підключався"), ("online", "Онлайн"), ("offline", "Офлайн")],
        default="never", index=True, tracking=True, readonly=True)
    status_interval_s = fields.Integer(string="Період звіту стану, с", default=60)
    push_interval_s = fields.Integer(string="Період відправки, с", default=5)
    push_max = fields.Integer(string="Показань у пакеті", default=1000)
    config_poll_s = fields.Integer(string="Період перечитування конфігурації, с", default=60)
    uptime_s = fields.Integer(string="Аптайм, с", readonly=True)
    buffer_rows = fields.Integer(string="У буфері", readonly=True)
    buffer_dropped = fields.Integer(string="Втрачено з буфера", readonly=True)
    plugins = fields.Json(string="Плагіни", readonly=True)
    config_etag = fields.Char(string="ETag конфігурації", readonly=True)
    rate_window_start = fields.Datetime()
    rate_count = fields.Integer()
    source_ids = fields.One2many("f3d.source", "collector_id", string="Джерела")
    source_count = fields.Integer(string="Джерел", compute="_compute_counts")
    signal_count = fields.Integer(string="Сигналів", compute="_compute_counts")
    note = fields.Text(string="Примітка")

    _f3d_collector_code_uniq = models.Constraint("UNIQUE(code)", "Код колектора має бути унікальним.")
    _f3d_collector_intervals = models.Constraint(
        "CHECK(status_interval_s >= 10 AND push_interval_s BETWEEN 1 AND 60 AND push_max BETWEEN 1 AND 2000 "
        "AND config_poll_s >= 10)",
        "Періоди колектора поза межами (статус ≥ 10 с, відправка 1…60 с, пакет 1…2000, конфігурація ≥ 10 с).")

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not self.CODE_RE.match(rec.code):
                raise ValidationError(
                    _("Код колектора: великі латинські літери, цифри, дефіс (напр. COL-MAIN)."))

    def _compute_counts(self):
        sources = {}
        signals = {}
        if self.ids:
            for collector, count in self.env["f3d.source"]._read_group(
                    [("collector_id", "in", self.ids)], ["collector_id"], ["__count"]):
                sources[collector.id] = count
            for collector, count in self.env["f3d.signal"]._read_group(
                    [("source_id.collector_id", "in", self.ids)], ["collector_id"], ["__count"]):
                signals[collector.id] = count
        for rec in self:
            rec.source_count = sources.get(rec.id, 0)
            rec.signal_count = signals.get(rec.id, 0)

    # --- токен ---------------------------------------------------------------------------------------
    def action_generate_token(self):
        self.ensure_one()
        if not self.env.user.has_group(GROUP_ADMIN):
            raise AccessError(_("Токен колектора видає лише адміністратор."))
        token = secrets.token_urlsafe(32)
        self.write({
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "token_hint": token[-4:],
            "token_set_at": fields.Datetime.now(),
        })
        self.message_post(body=_("Видано новий токен (…%s)", token[-4:]))
        return {
            "type": "ir.actions.act_window",
            "name": _("Токен колектора"),
            "res_model": "f3d.collector.token.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_collector_id": self.id, "default_token": token},
        }

    def action_revoke_token(self):
        self.ensure_one()
        self.write({"token_hash": False, "token_hint": False})
        self.message_post(body=_("Токен відкликано"))
        return True

    @api.model
    def _authenticate(self, raw_token):
        """Колектор за токеном (0/1 запис); перебір усіх кандидатів, порівняння сталого часу."""
        if not raw_token or not isinstance(raw_token, str) or len(raw_token) > 256:
            return self.browse()
        digest = hashlib.sha256(raw_token.encode()).hexdigest()
        found = self.browse()
        for cand in self.sudo().search([("active", "=", True), ("token_hash", "!=", False)]):
            if hmac.compare_digest(cand.token_hash, digest) and not found:
                found = cand
        return found

    def _touch(self, ip, version=None):
        vals = {"last_seen": fields.Datetime.now(), "last_ip": ip}
        if version:
            vals["version"] = version
        for rec in self.sudo().with_context(mail_notrack=True):
            v = dict(vals)
            if rec.state != "online":
                v["state"] = "online"
            rec.write(v)

    # --- конфігурація для колектора (API-01, R-16) ---------------------------------------------------
    def _config_body(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()

        def flag(key):
            return icp.get_param("factory3d.telemetry." + key, "False") in ("True", "true", "1")

        read_enabled, write_enabled = flag("read_enabled"), flag("write_enabled")
        local = self.env["f3d.source"]._f3d_local_types()
        sources = []
        for src in self.sudo().source_ids.filtered(lambda s: s.active and s.type not in local).sorted("code"):
            signals = []
            for sig in src.signal_ids.filtered(lambda s: s.active and s.address).sorted("code"):
                signals.append({
                    "code": sig.code, "kind": sig.kind, "unit": sig.unit or "", "period_s": sig.period_s,
                    "scale": sig.scale, "write_enabled": bool(sig.write_enabled), "states": sig.states or None,
                    "decimals": sig.decimals, "address": sig.address,
                })
            sources.append({
                "code": src.code, "type": src.type, "read_enabled": bool(src.read_enabled and read_enabled),
                "write_enabled": bool(src.write_enabled), "params": src.params or {}, "signals": signals,
            })
        return {
            "read_enabled": read_enabled, "write_enabled": write_enabled,
            "collector": {"code": self.code, "push_interval_s": self.push_interval_s, "push_max": self.push_max,
                          "status_interval_s": self.status_interval_s, "config_poll_s": self.config_poll_s},
            "params": {"stale_periods": int(icp.get_param("factory3d.telemetry.stale_periods", "3") or 3),
                       "stale_min_s": int(icp.get_param("factory3d.telemetry.stale_min_s", "60") or 60)},
            "sources": sources,
        }

    @staticmethod
    def _body_etag(body):
        return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def _etag(self):
        self.ensure_one()
        return self._body_etag(self._config_body())

    def _config_payload(self):
        self.ensure_one()
        body = self._config_body()
        etag = self._body_etag(body)
        if self.config_etag != etag:
            self.sudo().with_context(mail_notrack=True).write({"config_etag": etag})
        now = fields.Datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        return {"etag": etag, "generated_at": now, "server_time": now, **body}

    def _rate_check(self):
        """R-17 п. 2: вікно 60 с, не більше `push_rate_per_min` пакетів."""
        self.ensure_one()
        now = fields.Datetime.now()
        limit = int(self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.push_rate_per_min", "60"))
        rec = self.sudo().with_context(mail_notrack=True)
        start = rec.rate_window_start
        if not start or (now - start).total_seconds() >= 60:
            rec.write({"rate_window_start": now, "rate_count": 1})
            return True
        rec.write({"rate_count": rec.rate_count + 1})
        return rec.rate_count <= limit

    # --- навігація, крон -----------------------------------------------------------------------------
    def action_view_sources(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Джерела"), "res_model": "f3d.source",
            "view_mode": "list,form", "domain": [("collector_id", "=", self.id)],
            "context": {"default_collector_id": self.id},
        }

    @api.model
    def _cron_offline(self):
        """R-25: онлайн-колектор без контакту > 3·status_interval_s → offline, його джерела й сигнали."""
        now = fields.Datetime.now()
        for col in self.sudo().search([("state", "=", "online"), ("last_seen", "!=", False)]):
            if col.last_seen < now - timedelta(seconds=3 * col.status_interval_s):
                col.write({"state": "offline"})
                sources = col.source_ids.filtered(lambda s: s.state in ("online", "error"))
                if sources:
                    sources.write({"state": "offline"})
                    sources.signal_ids._mark_stale("колектор офлайн")
