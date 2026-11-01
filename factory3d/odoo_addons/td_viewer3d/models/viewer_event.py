"""M-03: подія шини td.viewer.event, коалесценція повідомлень (R-15), крон сигналів."""

import logging
import time
from datetime import timedelta
from functools import partial

from odoo import api, fields, models, modules
from odoo.tools import SQL

from ..tools import dates

_logger = logging.getLogger(__name__)

PREFIX = "td.viewer."
NOTIFY_KEY = "f3d_viewer.notify"
SNAPSHOT_KEY = "f3d_viewer.event_snapshot"
CODES_CAP = 500
KEEP_HOURS_DEFAULT = 24  # скільки подій потрібно дельті; решта — лише журнал (знімки живуть окремо, snapshot_keep_days)
PURGE_BATCH = 5000
PURGE_SECONDS = 50
PURGE_LOCK = 0x7D3D0E01  # ключ advisory-блокування чистки: щогодинний крон і щодобова ротація не працюють одночасно


def _flag(value, default=True):
    if value in (None, False, ""):
        return default
    return str(value).strip().lower() in ("true", "1")


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class F3dViewerEvent(models.Model):
    _name = "td.viewer.event"
    _description = "3D: подія зміни стану"
    _order = "ts desc, id desc"
    _log_access = False

    ts = fields.Datetime(string="Момент", required=True, index=True, default=fields.Datetime.now)
    model = fields.Char(string="Модель", required=True, size=64)
    codes = fields.Json(string="Коди", required=True)
    kind = fields.Selection(
        [("state", "Стан"), ("stock", "Залишки"), ("doc", "Документ"), ("signal", "Сигнал"), ("maintenance", "ТО")],
        string="Тип",
        required=True,
    )
    user_id = fields.Many2one("res.users", string="Користувач", ondelete="set null")
    n = fields.Integer(string="Кодів", compute="_compute_n", store=True)
    codes_text = fields.Char(string="Коди (текст)", compute="_compute_codes_text")

    def init(self):
        # лише індекс по `ts` (його дають `_since`, знімок і чистка); (ts, model) і індекси model/kind дублювали його
        # й подвоювали вартість кожного INSERT у журналі, що росте на тисячі рядків за годину
        # (Odoo сам не знімає індекс, коли в полі прибрали `index=True`, тож на наявних базах — явний DROP)
        self.env.cr.execute(
            "DROP INDEX IF EXISTS td_viewer_event_ts_model_idx, "
            "td_viewer_event__model_index, td_viewer_event__kind_index"
        )

    @api.depends("codes")
    def _compute_n(self):
        for rec in self:
            rec.n = len(rec.codes or [])

    @api.depends("codes")
    def _compute_codes_text(self):
        for rec in self:
            rec.codes_text = ", ".join(rec.codes or [])[:200]

    # --- публікація -------------------------------------------------------

    @api.model
    def _notify(self, model, codes, kind):
        """C-03: накопичує коди в транзакції; одна подія/повідомлення на (model, kind) при commit (R-15)."""
        if self.env.context.get("f3d_viewer_no_bus"):
            return
        codes = {c for c in (codes or ()) if c}
        if not codes:
            return
        data = self.env.cr.precommit.data.setdefault(NOTIFY_KEY, {})
        first = not data
        data.setdefault((model, kind), set()).update(codes)
        if first:
            self.env.cr.precommit.add(partial(self._flush_notify, self.env))

    @api.model
    def _flush_notify(self, env):
        data = env.cr.precommit.data.pop(NOTIFY_KEY, None)
        if not data:
            return
        try:
            with env.cr.savepoint():
                params = env["ir.config_parameter"].sudo()
                bus_on = _flag(params.get_param(PREFIX + "bus_enabled"))
                now = fields.Datetime.now()
                for (model, kind), codes in sorted(data.items()):
                    codes = sorted(codes)[:CODES_CAP]
                    # `n` у vals: інакше збережене обчислюване поле дає ще один UPDATE на кожен рядок (мертві кортежі)
                    env["td.viewer.event"].sudo().create(
                        {"ts": now, "model": model, "codes": codes, "kind": kind, "user_id": env.uid, "n": len(codes)}
                    )
                    if bus_on:
                        env["bus.bus"]._sendone(
                            "f3d_viewer",
                            "f3d_viewer",
                            {"model": model, "codes": codes, "kind": kind, "ts": dates.iso_utc(now)},
                        )
        except Exception:  # noqa: BLE001
            _logger.exception("не вдалося опублікувати події шини f3d_viewer")

    @api.model
    def _event_snapshot(self, note):
        """AC-49: знімок kind=event після публікації подій (виконується в precommit, один на транзакцію)."""
        if self.env.context.get("f3d_viewer_no_bus"):
            return
        notes = self.env.cr.precommit.data.setdefault(SNAPSHOT_KEY, [])
        first = not notes
        if note not in notes:
            notes.append(note)
        if first:
            self.env.cr.precommit.add(partial(self._flush_event_snapshot, self.env))

    @api.model
    def _flush_event_snapshot(self, env):
        notes = env.cr.precommit.data.pop(SNAPSHOT_KEY, None)
        if not notes:
            return
        try:
            with env.cr.savepoint():
                env["td.viewer.snapshot"].sudo()._take(kind="event", note="; ".join(notes))
        except Exception:  # noqa: BLE001
            _logger.exception("не вдалося зробити знімок за подією")

    # --- читання ----------------------------------------------------------

    @api.model
    def _since(self, since, limit=2000):
        """{model: set(codes)} для подій з `ts >= since` або None («повний»)."""
        params = self.env["ir.config_parameter"].sudo()
        keep = _int(params.get_param(PREFIX + "event_keep_hours"), KEEP_HOURS_DEFAULT)
        if since < fields.Datetime.now() - timedelta(hours=keep):
            return None
        # >= (а не >): ts має точність до секунди, подія тієї ж секунди, що й `since`, не має загубитись.
        # Порядок за `ts` (а не `id`): збігається з індексом, і планувальник не скануватиме всю таблицю по id.
        rows = self.sudo().search_read([("ts", ">=", since)], ["model", "codes"], limit=limit + 1, order="ts, id")
        if len(rows) > limit:
            return None
        res = {}
        for row in rows:
            res.setdefault(row["model"], set()).update(row["codes"] or [])
        return res

    # --- чистка -----------------------------------------------------------

    @api.model
    def _purge_old(self, keep_hours=None, batch=PURGE_BATCH, max_seconds=PURGE_SECONDS):
        """Видаляє події старші за `event_keep_hours` (дельта старішого `since` і так віддає «повний») пакетами по
        `batch` рядків прямим SQL (без ORM-кешу), не довше `max_seconds`; решта — наступним запуском.
        Повертає кількість видалених.

        У кроні (`ir_cron_progress_id`) кожен пакет фіксується (commit): одна довга транзакція тримала б блокування
        рядків і не пускала б автовакуум. Перед кожним пакетом береться `pg_try_advisory_xact_lock`: коли чистку вже
        веде інший запуск (щогодинний крон ↔ щодобова ротація), цей пропускається (блокування знімається разом із
        commit-ом, тож береться знову в кожній транзакції). Поза кроном (тести, RPC) — одна транзакція без commit."""
        started = time.monotonic()
        if keep_hours is None:
            keep_hours = _int(
                self.env["ir.config_parameter"].sudo().get_param(PREFIX + "event_keep_hours"), KEEP_HOURS_DEFAULT
            )
        cutoff = fields.Datetime.now() - timedelta(hours=max(keep_hours, 1))
        in_cron = bool(self.env.context.get("ir_cron_progress_id")) and not modules.module.current_test
        cr = self.env.cr
        self.flush_model()  # прямий SQL нижче не бачить ще не записаних створень
        total = 0
        while True:
            cr.execute("SELECT pg_try_advisory_xact_lock(%s)", (PURGE_LOCK,))
            if not cr.fetchone()[0]:
                _logger.info("td.viewer.event: чистку вже веде інший запуск, пропущено")
                break
            cr.execute(
                SQL(
                    "DELETE FROM td_viewer_event WHERE id IN "
                    "(SELECT id FROM td_viewer_event WHERE ts < %s ORDER BY ts LIMIT %s)",
                    cutoff,
                    batch,
                )
            )
            deleted = cr.rowcount
            total += deleted
            if in_cron:
                self.env["ir.cron"]._commit_progress(deleted)
            if deleted < batch or time.monotonic() - started >= max_seconds:
                break
        if total:
            self.env.invalidate_all()
            _logger.info("td.viewer.event: видалено %d подій старіших за %s", total, cutoff)
        return total

    @api.model
    def _cron_purge(self):
        self._purge_old()

    # --- крон сигналів ----------------------------------------------------

    @api.model
    def _cron_signal_bus(self):
        if "x_f3d_signal" not in self.env:
            return
        params = self.env["ir.config_parameter"].sudo()
        last = params.get_param(PREFIX + "signal_bus_ts")
        domain = [("x_active", "=", True), ("x_code", "!=", False)]
        if last:
            domain.append(("x_updated", ">", last))
        rows = (
            self.env["x_f3d_signal"]
            .sudo()
            .search_read(domain, ["x_code", "x_updated"], order="x_updated asc, id asc", limit=CODES_CAP)
        )
        if not rows:
            return
        self._notify("x_f3d_signal", [r["x_code"] for r in rows], "signal")
        stamps = [r["x_updated"] for r in rows if r["x_updated"]]
        if stamps:
            params.set_param(PREFIX + "signal_bus_ts", fields.Datetime.to_string(max(stamps)))
