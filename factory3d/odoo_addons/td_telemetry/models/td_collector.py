import hashlib
import hmac
import json
import logging
import re
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..tools.locking import CONTENTION_ERRORS, lock_skip_locked

_logger = logging.getLogger(__name__)

GROUP_ADMIN = "td_factory3d.group_td_admin"
TOUCH_INTERVAL_PARAM = "td.telemetry.touch_interval_s"
TOUCH_INTERVAL_S = 30  # DEC-19: мінімальний інтервал запису last_seen/last_push_at
RATE_WINDOW_S = 60  # R-17 п. 2: вікно ліміту частоти push
RATE_KEEP_S = 600  # скільки секунд `_cron_offline` тримає журнал пакетів `td_collector_push`


class F3dCollector(models.Model):
    _name = "td.collector"
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
        default="never",
        index=True,
        tracking=True,
        readonly=True,
    )
    status_interval_s = fields.Integer(string="Період звіту стану, с", default=60)
    push_interval_s = fields.Integer(string="Період відправки, с", default=5)
    push_max = fields.Integer(string="Показань у пакеті", default=1000)
    config_poll_s = fields.Integer(string="Період перечитування конфігурації, с", default=60)
    uptime_s = fields.Integer(string="Аптайм, с", readonly=True)
    buffer_rows = fields.Integer(string="У буфері", readonly=True)
    buffer_dropped = fields.Integer(string="Втрачено з буфера", readonly=True)
    plugins = fields.Json(string="Плагіни", readonly=True)
    config_etag = fields.Char(string="ETag конфігурації", readonly=True)
    source_ids = fields.One2many("td.source", "collector_id", string="Джерела")
    source_count = fields.Integer(string="Джерел", compute="_compute_counts")
    signal_count = fields.Integer(string="Сигналів", compute="_compute_counts")
    note = fields.Text(string="Примітка")

    _f3d_collector_code_uniq = models.Constraint("UNIQUE(code)", "Код колектора має бути унікальним.")
    _f3d_collector_intervals = models.Constraint(
        "CHECK(status_interval_s >= 10 AND push_interval_s BETWEEN 1 AND 60 AND push_max BETWEEN 1 AND 2000 "
        "AND config_poll_s >= 10)",
        "Періоди колектора поза межами (статус ≥ 10 с, відправка 1…60 с, пакет 1…2000, конфігурація ≥ 10 с).",
    )

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not self.CODE_RE.match(rec.code):
                raise ValidationError(_("Код колектора: великі латинські літери, цифри, дефіс (напр. COL-MAIN)."))

    def init(self):
        """DEC-19: журнал пакетів для ліміту частоти (лише вставки, без FK) — окремо від рядка колектора."""
        super().init()
        self.env.cr.execute(
            "CREATE TABLE IF NOT EXISTS td_collector_push (collector_id integer NOT NULL, ts timestamp NOT NULL)"
        )
        self.env.cr.execute(
            "CREATE INDEX IF NOT EXISTS td_collector_push_collector_ts_idx ON td_collector_push (collector_id, ts)"
        )

    def _compute_counts(self):
        sources = {}
        signals = {}
        if self.ids:
            for collector, count in self.env["td.source"]._read_group(
                [("collector_id", "in", self.ids)], ["collector_id"], ["__count"]
            ):
                sources[collector.id] = count
            for collector, count in self.env["td.signal"]._read_group(
                [("source_id.collector_id", "in", self.ids)], ["collector_id"], ["__count"]
            ):
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
        self.write(
            {
                "token_hash": hashlib.sha256(token.encode()).hexdigest(),
                "token_hint": token[-4:],
                "token_set_at": fields.Datetime.now(),
            }
        )
        self.message_post(body=_("Видано новий токен (…%s)", token[-4:]))
        return {
            "type": "ir.actions.act_window",
            "name": _("Токен колектора"),
            "res_model": "td.collector.token.wizard",
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

    def _touch(self, ip, version=None, pushed=False):
        """Контакт колектора: `last_seen`, `last_ip`, `version`, `state` → `online` (+ `last_push_at` при `pushed`).

        DEC-19: рядок колектора спільний для всіх запитів, тому запис — не частіше ніж раз на
        `min(touch_interval_s, status_interval_s)` с (параметр `td.telemetry.touch_interval_s`, 30 за
        замовчуванням; не більше `status_interval_s`, щоб `_cron_offline` — 3·status_interval_s — не спрацював хибно).
        Негайно пишеться зміна стану (не `online`) чи версії. IP не є причиною запису: за CDN/проксі (Cloudflare)
        він інший у кожного запиту й звів би тротлінг нанівець; `last_ip` оновлюється разом із тротлінговим
        записом або зміною стану. Один `write` на колектор.
        """
        now = fields.Datetime.now()
        try:
            interval = int(self.env["ir.config_parameter"].sudo().get_param(TOUCH_INTERVAL_PARAM, TOUCH_INTERVAL_S))
        except ValueError:
            interval = TOUCH_INTERVAL_S
        for rec in self.sudo().with_context(mail_notrack=True):
            if (
                rec.state == "online"
                and rec.last_seen
                and (not version or rec.version == version)
                and 0 <= (now - rec.last_seen).total_seconds() < min(interval, rec.status_interval_s)
            ):
                continue
            vals = {"last_seen": now, "last_ip": ip}
            if version:
                vals["version"] = version
            if pushed:
                vals["last_push_at"] = now
            if rec.state != "online":
                vals["state"] = "online"
            rec.write(vals)

    # --- конфігурація для колектора (API-01, R-16) ---------------------------------------------------
    def _config_body(self):
        self.ensure_one()
        icp = self.env["ir.config_parameter"].sudo()

        def flag(key):
            return icp.get_param("td.telemetry." + key, "False") in ("True", "true", "1")

        read_enabled, write_enabled = flag("read_enabled"), flag("write_enabled")
        local = self.env["td.source"]._td_local_types()
        sources = []
        for src in self.sudo().source_ids.filtered(lambda s: s.active and s.type not in local).sorted("code"):
            signals = []
            for sig in src.signal_ids.filtered(lambda s: s.active and s.address).sorted("code"):
                signals.append(
                    {
                        "code": sig.code,
                        "kind": sig.kind,
                        "unit": sig.unit or "",
                        "period_s": sig.period_s,
                        "scale": sig.scale,
                        "write_enabled": bool(sig.write_enabled),
                        "states": sig.states or None,
                        "decimals": sig.decimals,
                        "address": sig.address,
                    }
                )
            sources.append(
                {
                    "code": src.code,
                    "type": src.type,
                    "read_enabled": bool(src.read_enabled and read_enabled),
                    "write_enabled": bool(src.write_enabled),
                    "params": src.params or {},
                    "signals": signals,
                }
            )
        return {
            "read_enabled": read_enabled,
            "write_enabled": write_enabled,
            "collector": {
                "code": self.code,
                "push_interval_s": self.push_interval_s,
                "push_max": self.push_max,
                "status_interval_s": self.status_interval_s,
                "config_poll_s": self.config_poll_s,
            },
            "params": {
                "stale_periods": int(icp.get_param("td.telemetry.stale_periods", "3") or 3),
                "stale_min_s": int(icp.get_param("td.telemetry.stale_min_s", "60") or 60),
            },
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
        """R-17 п. 2: вікно 60 с, не більше `push_rate_per_min` пакетів (інакше `429`).

        DEC-19: лічильник не лежить у рядку колектора. Кожен пакет — один `INSERT` у `td_collector_push`, далі
        `COUNT` за останні 60 с. Рядки лише додаються, тож паралельні push одного колектора не блокують один
        одного й не дають serialization failure (на відміну від `UPDATE` спільного рядка). Старі рядки
        прибирає `_cron_offline`. Відхилені пакети теж рахуються, як і раніше.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        limit = int(self.env["ir.config_parameter"].sudo().get_param("td.telemetry.push_rate_per_min", "60"))
        cr = self.env.cr
        cr.execute("INSERT INTO td_collector_push (collector_id, ts) VALUES (%s, %s)", (self.id, now))
        cr.execute(
            "SELECT COUNT(*) FROM td_collector_push WHERE collector_id = %s AND ts > %s",
            (self.id, now - timedelta(seconds=RATE_WINDOW_S)),
        )
        return cr.fetchone()[0] <= limit

    # --- навігація, крон -----------------------------------------------------------------------------
    def action_view_sources(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Джерела"),
            "res_model": "td.source",
            "view_mode": "list,form",
            "domain": [("collector_id", "=", self.id)],
            "context": {"default_collector_id": self.id},
        }

    @api.model
    def _cron_offline(self):
        """R-25: онлайн-колектор без контакту > 3·status_interval_s → offline, його джерела й сигнали.

        DEC-20: колектор із його джерелами обробляється в одному savepoint, без очікування (`SKIP LOCKED`). Колектор
        чи джерело, зайняті паралельною транзакцією (push) або змінені нею після знімка, — не помилка: колектор
        лишається `online` і потрапить до наступного запуску (хвилина), стан джерел не розходиться зі станом
        колектора. Сигнали, зайняті іншою транзакцією, пропускаються (їх візьме `_cron_stale` за таймаутом).
        """
        now = fields.Datetime.now()
        cr = self.env.cr
        cr.execute("DELETE FROM td_collector_push WHERE ts < %s", (now - timedelta(seconds=RATE_KEEP_S),))
        cols = self.sudo().search([("state", "=", "online"), ("last_seen", "!=", False)])
        for col in cols.filtered(lambda c: c.last_seen < now - timedelta(seconds=3 * c.status_interval_s)).sorted("id"):
            try:
                with cr.savepoint():
                    locked = lock_skip_locked(col)
                    if not locked or locked.state != "online":
                        continue
                    sources = col.source_ids.filtered(lambda s: s.state in ("online", "error"))
                    if sources and len(lock_skip_locked(sources)) < len(sources):
                        _logger.info("td.collector %s: джерело зайняте, офлайн повторить крон", col.code)
                        continue
                    col.write({"state": "offline"})
                    if sources:
                        sources.write({"state": "offline"})
                        signals = sources.signal_ids
                        signals.with_context(td_skip_locked=True)._mark_stale("колектор офлайн")
                        if pending := signals.filtered(lambda s: s.status not in ("unknown", "stale")):
                            _logger.info(
                                "td.collector %s: сигналів зайнято %d, stale за таймаутом", col.code, len(pending)
                            )
            except CONTENTION_ERRORS as exc:
                _logger.info(
                    "td.collector %s: паралельне оновлення (%s), офлайн повторить крон", col.code, type(exc).__name__
                )
