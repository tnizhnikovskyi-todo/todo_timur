"""M-02: знімок стану заводу (gzip JSON), плановий/подієвий/ручний; ротація."""

import base64
import gzip
import json
import logging
import re
import time
from datetime import date, timedelta

from odoo import api, fields, models

from ..tools import dates

_logger = logging.getLogger(__name__)

PREFIX = "td.viewer."
WINDOW_RE = re.compile(r"^(\d\d):(\d\d)-(\d\d):(\d\d)$")
EVENTS_CAP = 500
ROTATE_BATCH = 1000
ROTATE_SECONDS = 60


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class F3dViewerSnapshot(models.Model):
    _name = "td.viewer.snapshot"
    _description = "3D: знімок стану заводу"
    _order = "ts desc"
    _rec_name = "display_name"

    ts = fields.Datetime(string="Момент", required=True, index=True, default=fields.Datetime.now)
    shift_date = fields.Date(
        string="Дата зміни", required=True, index=True, compute="_compute_shift_date", store=True, precompute=True
    )
    is_today = fields.Boolean(string="Сьогодні", compute="_compute_day_flags", search="_search_is_today")
    is_this_week = fields.Boolean(string="Цей тиждень", compute="_compute_day_flags", search="_search_is_this_week")
    kind = fields.Selection(
        [("periodic", "Плановий"), ("event", "Подія"), ("install", "Установка"), ("manual", "Вручну")],
        string="Тип",
        required=True,
        default="periodic",
        index=True,
    )
    payload_file = fields.Binary(string="Дані (gzip JSON)", attachment=True, required=True)
    payload_name = fields.Char(string="Файл", default="snapshot.json.gz")
    size_kb = fields.Integer(
        string="Розмір, КБ", readonly=True, compute="_compute_size_kb", store=True, precompute=True
    )
    schema = fields.Char(string="Версія схеми", default="1.1", required=True)
    note = fields.Char(string="Примітка")
    event_count = fields.Integer(string="Подій з попереднього", readonly=True)
    user_id = fields.Many2one("res.users", string="Від імені")
    company_id = fields.Many2one(
        "res.company", string="Компанія", required=True, default=lambda s: s.env.company, index=True
    )
    display_name = fields.Char(compute="_compute_display_name")

    _f3d_size_nonneg = models.Constraint("CHECK (size_kb >= 0)", "Розмір знімка не може бути від'ємним.")

    @api.depends("ts")
    def _compute_shift_date(self):
        for rec in self:
            rec.shift_date = dates.local(rec.ts)[:10] if rec.ts else False

    @api.model
    def _today(self):
        """Поточна доба за Києвом у шкалі `demo_clock` (R-21) — та сама, що «сьогодні» API-05 і `shift_date`."""
        return date.fromisoformat(dates.today(self.env))

    @api.depends("shift_date")
    def _compute_day_flags(self):
        today = self._today()
        week = today - timedelta(days=today.weekday())
        for rec in self:
            rec.is_today = rec.shift_date == today
            rec.is_this_week = bool(rec.shift_date) and rec.shift_date >= week

    @staticmethod
    def _day_domain(operator, value, first, last=None):
        """`shift_date ∈ [first, last]` (`last=None` — без верхньої межі) для `= True` / `!= False`; інакше —
        доповнення."""
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError("Пошук за добою підтримує лише = / != True/False")
        if (operator == "=") == value:
            return [("shift_date", ">=", first)] + ([("shift_date", "<=", last)] if last else [])
        return ["|", ("shift_date", "<", first), ("shift_date", ">", last)] if last else [("shift_date", "<", first)]

    def _search_is_today(self, operator, value):
        """Фільтр «Сьогодні»: київська доба сервера, а не `context_today()` браузера (UTC на стенді)."""
        today = self._today()
        return self._day_domain(operator, value, today, today)

    def _search_is_this_week(self, operator, value):
        today = self._today()
        return self._day_domain(operator, value, today - timedelta(days=today.weekday()))

    @api.depends("payload_file")
    def _compute_size_kb(self):
        for rec in self:
            size = len(rec.payload_file or b"") * 3 // 4
            rec.size_kb = (size + 1023) // 1024

    @api.depends("ts", "kind")
    def _compute_display_name(self):
        labels = dict(self._fields["kind"]._description_selection(self.env))
        for rec in self:
            rec.display_name = "%s · %s" % (dates.local(rec.ts) if rec.ts else "", labels.get(rec.kind, ""))

    # --- створення --------------------------------------------------------

    @staticmethod
    def _pack(payload):
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        return base64.b64encode(gzip.compress(raw, 6))

    @api.model
    def _take(self, kind="periodic", note=None, user=None):
        from ..tools.payload import PayloadBuilder

        env = self.env
        now = dates.now(env)  # шкала демо-годинника (R-21): shift_date знімка збігається з «сьогодні» API-05
        prev = self.search([], limit=1)
        if kind == "periodic" and prev and prev.ts > now - timedelta(seconds=60):
            return prev
        user = user or env.ref("td_viewer3d.user_kiosk", raise_if_not_found=False) or env.user
        if isinstance(user, int):
            user = env["res.users"].browse(user)
        payload = PayloadBuilder(env(user=user.id, su=False), full=True).build()
        events = []
        if prev:
            rows = (
                env["td.viewer.event"]
                .sudo()
                .search_read(
                    [("ts", ">", prev.ts)], ["ts", "model", "codes", "kind"], limit=EVENTS_CAP, order="ts desc, id desc"
                )
            )
            events = [
                {"ts": dates.iso_utc(r["ts"]), "model": r["model"], "codes": r["codes"], "kind": r["kind"]}
                for r in rows
            ]
        meta = payload.setdefault("meta", {})
        meta["events"] = events
        meta["snapshot"] = {"id": None, "ts": dates.local(now), "kind": kind}
        rec = self.create(
            {
                "ts": now,
                "kind": kind,
                "note": note,
                "payload_file": self._pack(payload),
                "schema": meta.get("schema") or "1.1",
                "event_count": len(events),
                "user_id": user.id,
                "company_id": env.company.id,
            }
        )
        # id відомий лише після create: дописуємо його в meta.snapshot (API-06 віддає вкладення як є)
        meta["snapshot"]["id"] = rec.id
        rec.payload_file = self._pack(payload)
        return rec

    @api.model
    def _in_window(self, hours, now_utc):
        if not hours:
            return True
        m = WINDOW_RE.match(hours.strip())
        if not m:
            _logger.warning("snapshot_hours невалідний (%r): знімок без обмеження вікна", hours)
            return True
        h1, m1, h2, m2 = (int(x) for x in m.groups())
        start, end = h1 * 60 + m1, h2 * 60 + m2
        loc = dates.local(now_utc)
        cur = int(loc[11:13]) * 60 + int(loc[14:16])
        return start <= cur <= end if start <= end else (cur >= start or cur <= end)

    @api.model
    def _cron_snapshot(self):
        hours = self.env["ir.config_parameter"].sudo().get_param(PREFIX + "snapshot_hours")
        if not self._in_window(hours, dates.now(self.env)):
            return
        self._take("periodic")

    @api.model
    def _cron_rotate(self):
        started = time.monotonic()
        params = self.env["ir.config_parameter"].sudo()
        days = _int(params.get_param(PREFIX + "snapshot_keep_days"), 14)
        cutoff = fields.Datetime.now() - timedelta(days=days)
        snaps = self.sudo().search([("ts", "<", cutoff), ("kind", "!=", "install")])
        n_snaps = len(snaps)
        snaps.unlink()
        events = self.env["td.viewer.event"].sudo()
        n_events = 0
        while time.monotonic() - started < ROTATE_SECONDS:
            batch = events.search([("ts", "<", cutoff)], limit=ROTATE_BATCH)
            if not batch:
                break
            n_events += len(batch)
            batch.unlink()
        _logger.info("ротація: знімків %d, подій %d", n_snaps, n_events)

    # --- дії --------------------------------------------------------------

    def action_open_viewer(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("td_viewer3d.action_td_viewer")
        action["params"] = {"snapshot": self.id}
        return action

    def read_payload(self):
        self.ensure_one()
        return json.loads(gzip.decompress(base64.b64decode(self.payload_file)).decode("utf-8"))
