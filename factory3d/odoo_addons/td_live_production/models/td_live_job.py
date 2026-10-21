"""Фонові задачі «Живого виробництва»: важкі кнопки лише ставлять роботу в чергу й одразу повертають «запущено у фоні».

Роботу забирає крон-виконавець `_cron_td_live_jobs`: порціями (кожна — окрема транзакція з commit, до `job_budget_s` с
за запуск), після порції сам себе перезапускає (`ir.cron._trigger`). Прогрес і підсумок лежать у `td.live.job` (видно в
налаштуваннях і в добі). Повторне натискання під час роботи не дублює задачу: унікальний індекс на активні задачі.
"""

import json
import logging
import time
from collections import Counter
from datetime import timedelta

from psycopg2 import errors as pg_errors

from odoo import _, api, fields, models, modules

from ..tools import clock

_logger = logging.getLogger(__name__)

PREFIX = "td.live_production."
CRON_JOBS = "td_live_production.cron_td_live_jobs"
CONCURRENCY = (pg_errors.SerializationFailure, pg_errors.LockNotAvailable, pg_errors.DeadlockDetected)
BUDGET_S = 30.0  # скільки секунд за запуск крон бере нові порції (ліміт крона на сервері ~120 с; порція — до ~20 с)
UNIT_BUDGET_S = 15.0  # порція диспетчера в задачі
UNIT_TRIES = 3  # спроб порції при конкурентному оновленні
ITEM_TRIES = 3  # скільки разів МО «Догнати минуле» відкладається в кінець черги при конфліктах
PHASES = {
    "dispatch": "диспетчер",
    "mos": "МО",
    "orders": "замовлення",
    "schedule": "розклад",
    "apply": "наряди",
    "finalize": "завершення",
}
CONFLICT_TEXT = "конкурентне оновлення даних"


class TdLiveJob(models.Model):
    _name = "td.live.job"
    _description = "Живе виробництво: фонова задача"
    _order = "id desc"

    name = fields.Char(compute="_compute_name", store=True)
    kind = fields.Selection(
        [("catch_up", "Догнати минуле"), ("generate_day", "Згенерувати добу")],
        string="Задача",
        required=True,
        index=True,
    )
    day_date = fields.Date(string="Доба")
    day_id = fields.Many2one("td.live.day", string="Доба (запис)", ondelete="set null", index=True)
    company_id = fields.Many2one(
        "res.company", string="Компанія", required=True, default=lambda s: s.env.company, index=True
    )
    state = fields.Selection(
        [("queued", "У черзі"), ("running", "Виконується"), ("done", "Завершено"), ("failed", "Помилка")],
        string="Стан",
        default="queued",
        required=True,
        index=True,
    )
    phase = fields.Char(string="Фаза")
    total = fields.Integer(string="Усього")
    done_count = fields.Integer(string="Зроблено")
    failed_count = fields.Integer(string="Не вдалось")
    skipped_count = fields.Integer(string="Пропущено")
    reasons = fields.Text(string="Причини невдач (JSON)")
    stats = fields.Text(string="Лічильники диспетчера (JSON)")
    queue = fields.Text(string="Черга (JSON)")
    then_start = fields.Boolean(
        string="Потім запустити живе виробництво",
        help="Після завершення задачі вмикається диспетчер: крони й вимкнений демо-годинник (кнопка «Запустити»).",
    )
    message = fields.Text(string="Підсумок")
    error = fields.Text(string="Помилка")
    date_start = fields.Datetime(string="Початок")
    date_end = fields.Datetime(string="Кінець")
    heartbeat = fields.Datetime(string="Остання порція")
    progress_text = fields.Char(compute="_compute_progress", string="Прогрес")

    def init(self):
        # одна активна задача на (вид, доба, компанія): повторне натискання не дублює роботу
        self.env.cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS td_live_job_active_uniq ON td_live_job "
            "(kind, company_id, COALESCE(day_date, DATE '1970-01-01')) WHERE state IN ('queued', 'running')"
        )

    # --- відображення -----------------------------------------------------------------------------------
    @api.depends("kind", "day_date", "create_date")
    def _compute_name(self):
        labels = dict(self._fields["kind"]._description_selection(self.env))
        for rec in self:
            tail = rec.day_date or (rec.create_date and rec.create_date.date()) or ""
            rec.name = "%s %s" % (labels.get(rec.kind, rec.kind), tail)

    def _json(self, field, default):
        try:
            return json.loads(self[field]) if self[field] else default
        except ValueError:
            return default

    def top_reasons(self, n=3):
        counts = Counter(self._json("reasons", {}))
        return "; ".join("%s — %s" % (text, k) for text, k in counts.most_common(n))

    @api.depends(
        "state", "phase", "total", "done_count", "failed_count", "skipped_count", "reasons", "message", "error"
    )
    def _compute_progress(self):
        for rec in self:
            rec.progress_text = rec._td_progress()

    def _td_progress(self):
        self.ensure_one()
        if self.state == "queued":
            return _("у черзі")
        if self.state == "failed":
            return _("помилка: %s", (self.error or "")[:200])
        if self.state == "done" and self.message:
            return self.message
        label = PHASES.get(self.phase or "", self.phase or "")
        if self.kind == "catch_up" and self.phase == "mos":
            text = _("закрито %(done)s з %(total)s", done=self.done_count, total=self.total)
            if self.failed_count:
                text += _(", не вдалось %s", self.failed_count)
            if self.skipped_count:
                text += _(", пропущено %s", self.skipped_count)
            top = self.top_reasons()
            return text + (_(". Причини: %s", top) if top else "")
        if self.total:
            return _("%(label)s: %(done)s з %(total)s", label=label, done=self.done_count, total=self.total)
        return label or _("виконується")

    # --- постановка в чергу ---------------------------------------------------------------------------------
    @api.model
    def td_enqueue(self, kind, day=None, then_start=False):
        """Поставити задачу. Повертає `(задача, статус)`: `created`, `active` (вже виконується — не дублюється),
        `exists` (доба вже згенерована). Крон-виконавець будиться одразу."""
        self = self.sudo()
        env = self.env
        company = env.company
        if kind == "generate_day":
            if env["td.live.day"].search_count(
                [("date", "=", day), ("company_id", "=", company.id), ("generated", "=", True)]
            ):
                return self.browse(), "exists"
        domain = [("kind", "=", kind), ("company_id", "=", company.id), ("state", "in", ("queued", "running"))]
        if kind == "generate_day":
            domain.append(("day_date", "=", day))
        active = self.search(domain, limit=1)
        if active:
            if then_start and not active.then_start:
                active.then_start = True
            return active, "active"
        try:
            with env.cr.savepoint():
                job = self.create(
                    {
                        "kind": kind,
                        "day_date": day if kind == "generate_day" else False,
                        "company_id": company.id,
                        "then_start": then_start,
                    }
                )
        except pg_errors.UniqueViolation:
            return self.search(domain, limit=1), "active"
        self._td_wake()
        return job, "created"

    @api.model
    def _td_wake(self, delay_s=0):
        """Розбудити крон-виконавець (і одразу після порції, і через `delay_s` при конфліктах)."""
        cron = self.env.ref(CRON_JOBS, raise_if_not_found=False)
        if cron:
            at = fields.Datetime.now() + timedelta(seconds=delay_s) if delay_s else None
            cron.sudo()._trigger(at=at)

    @api.model
    def td_status_text(self, limit=4):
        """Останні задачі для екрана налаштувань: прогрес і підсумок."""
        jobs = self.sudo().search([("company_id", "=", self.env.company.id)], limit=limit)
        if not jobs:
            return _("Фонових задач ще не було.")
        lines = []
        for job in jobs:
            stamp = fields.Datetime.to_string(job.heartbeat or job.create_date)[:16]
            lines.append(
                "%s · %s · %s · %s"
                % (job.name, dict(job._fields["state"].selection)[job.state], stamp, job.progress_text)
            )
        return "\n".join(lines)

    # --- виконавець -----------------------------------------------------------------------------------------
    @api.model
    def _td_budget(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(PREFIX + "job_budget_s")
        try:
            return float(raw) if raw else BUDGET_S
        except ValueError:
            return BUDGET_S

    @api.model
    def _td_in_test(self):
        return bool(modules.module.current_test)

    @api.model
    def _td_claim(self):
        """Найстарша активна задача, заблокована для себе (одночасний запуск другим процесом її пропускає)."""
        self.env.cr.execute(
            "SELECT id FROM td_live_job WHERE state IN ('queued', 'running') ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED"
        )
        row = self.env.cr.fetchone()
        return self.browse(row[0]) if row else self.browse()

    @api.model
    def _cron_td_live_jobs(self):
        """Крон-виконавець: порції задач у межах бюджету часу, далі сам себе будить, якщо роботи ще лишилось."""
        started = time.monotonic()
        budget = self._td_budget()
        while True:
            job = self._td_claim()
            if not job:
                return
            job._td_run()
            if time.monotonic() - started >= budget:  # хоча б одна порція за запуск, далі — за бюджетом часу
                break
        if self.search_count([("state", "in", ("queued", "running"))]):
            self._td_wake()

    def _td_run(self):
        """Одна порція задачі в транзакції з commit і повтором при конкурентному оновленні."""
        self.ensure_one()
        env = self.env
        in_test = self._td_in_test()
        for attempt in range(UNIT_TRIES):
            try:
                with env.cr.savepoint():
                    if self.state == "queued":
                        self.write({"state": "running", "date_start": fields.Datetime.now()})
                    self._td_work()
                self.heartbeat = fields.Datetime.now()
                if not in_test:
                    env.cr.commit()
                return
            except CONCURRENCY:
                if in_test:
                    raise
                env.cr.rollback()
                time.sleep(attempt + 1)  # крон верстатів тримає ті самі рядки: коротка пауза й свіжий знімок
            except Exception as exc:  # noqa: BLE001 — задача падає зрозуміло, а не ламає крон
                _logger.warning("td_live_production: задача %s #%s: %s", self.kind, self.id, exc, exc_info=True)
                if not in_test:
                    env.cr.rollback()
                self.write(
                    {
                        "state": "failed",
                        "error": str(exc.args[0] if exc.args else exc)[:500],
                        "date_end": fields.Datetime.now(),
                        "heartbeat": fields.Datetime.now(),
                    }
                )
                if not in_test:
                    env.cr.commit()
                return
        self._td_on_conflict()
        if not in_test:
            env.cr.commit()

    def _td_on_conflict(self):
        """Порція кілька разів поспіль уперлась у конкурентне оновлення: відкласти елемент у кінець черги."""
        if self.kind != "catch_up" or self.phase != "mos":
            return
        queue = self._json("queue", [])
        if not queue:
            return
        mo_id, tries = queue.pop(0)
        if tries + 1 >= ITEM_TRIES:
            self._td_add_reason(_(CONFLICT_TEXT))
            self.failed_count += 1
        else:
            queue.append([mo_id, tries + 1])
        self.queue = json.dumps(queue)
        self.heartbeat = fields.Datetime.now()
        if not queue:
            self._td_finish()

    # --- роботи --------------------------------------------------------------------------------------------
    def _td_work(self):
        """Одна порція роботи задачі; завершення — `_td_finish()`."""
        self.ensure_one()
        return getattr(self, "_td_work_%s" % self.kind)()

    def _td_add_reason(self, text):
        counts = Counter(self._json("reasons", {}))
        counts[text] += 1
        self.reasons = json.dumps(dict(counts), ensure_ascii=False)

    def _td_add_stats(self, res):
        stats = Counter(self._json("stats", {}))
        for key in ("started", "finished", "closed", "shipped", "downtimes"):
            stats[key] += res.get(key, 0)
        self.stats = json.dumps(dict(stats))

    def _td_dispatch_unit(self, eng, now):
        """Порція диспетчера в межах бюджету; `True`, якщо ще є події, які вдається виконати."""
        res = eng.td_dispatch(now=now, force=True, budget_s=UNIT_BUDGET_S)
        self._td_add_stats(res)
        self.phase = "dispatch"
        self.total = self.done_count = 0
        return bool(res["pending"] and res["applied"])

    def _td_work_catch_up(self):
        eng = self.env["td.live.engine"]
        now = eng._td_now()
        today_start = clock.shift_window(clock.local_date(now), (0.0, 24.0))[0]
        if self.phase in (False, "", "dispatch"):
            if self._td_dispatch_unit(eng, now):
                return True
            past, skipped = eng._td_catch_up_candidates(today_start)
            self.write(
                {
                    "phase": "mos",
                    "queue": json.dumps([[mo_id, 0] for mo_id in past]),
                    "total": len(past) + skipped,
                    "skipped_count": skipped,
                }
            )
            return bool(past) or self._td_finish()
        queue = self._json("queue", [])
        if not queue:
            return self._td_finish()
        mo_id, _tries = queue[0]
        verdict, reason = eng._td_catch_up_unit(mo_id, today_start)  # конкурентне оновлення піднімається до виконавця
        queue.pop(0)
        vals = {"queue": json.dumps(queue)}
        if verdict == "done":
            vals["done_count"] = self.done_count + 1
        elif verdict == "skipped":
            vals["skipped_count"] = self.skipped_count + 1
        else:
            self._td_add_reason(reason)
            vals["failed_count"] = self.failed_count + 1
        self.write(vals)
        return bool(queue) or self._td_finish()

    def _td_work_generate_day(self):
        eng = self.env["td.live.engine"]
        now = eng._td_now()
        Day = self.env["td.live.day"]
        rec = Day.search([("date", "=", self.day_date), ("company_id", "=", self.company_id.id)], limit=1)
        if not rec:
            rec = eng._td_gen_plan(self.day_date)
            self.write({"day_id": rec.id, "phase": rec.gen_phase, "done_count": 0, "total": eng._td_gen_total(rec)})
            return True
        if self.day_id != rec:
            self.day_id = rec
        if not rec.generated:
            phase, done, total = eng._td_gen_step(rec)
            self.write({"phase": phase, "done_count": done, "total": total})
            return True
        if self.day_date <= eng._td_today(now) and self._td_dispatch_unit(eng, now):
            return True
        return self._td_finish()

    def _td_finish(self):
        """Підсумок, «готово», за потреби запуск живого виробництва. Повертає `False`: більше роботи немає."""
        self.ensure_one()
        eng = self.env["td.live.engine"]
        stats = self._json("stats", {})
        tail = _(
            " Диспетчер: стартувало нарядів %(started)s, завершено %(finished)s, закрито МО %(closed)s, "
            "відвантажено %(shipped)s.",
            started=stats.get("started", 0),
            finished=stats.get("finished", 0),
            closed=stats.get("closed", 0),
            shipped=stats.get("shipped", 0),
        )
        if self.kind == "catch_up":
            top = self.top_reasons()
            message = _(
                "Догнати минуле: закрито %(done)s з %(total)s МО (не вдалось %(failed)s, пропущено %(skipped)s)."
                "%(why)s",
                done=self.done_count,
                total=self.total,
                failed=self.failed_count,
                skipped=self.skipped_count,
                why=_(" Причини невдач: %s. Деталі — в чаттері МО.", top) if top else "",
            )
            today = eng._td_today()
            day = self.env["td.live.day"].search(
                [("date", "=", today), ("company_id", "=", self.company_id.id)], limit=1
            )
            if day:
                self.day_id = day
        else:
            day = self.day_id
            message = _(
                "Доба %(day)s: замовлень %(so)s, МО %(mo)s. %(note)s",
                day=self.day_date,
                so=day.order_count,
                mo=day.production_count,
                note=day.note or "",
            )
        self.write(
            {
                "state": "done",
                "phase": "done",
                "message": (message + (tail if stats else "")).strip(),
                "date_end": fields.Datetime.now(),
            }
        )
        if self.then_start:
            eng.td_activate()
        return False

    def action_cancel_queue(self):
        """Прибрати задачу з черги (лише ще не завершену): користувач вирішив не чекати."""
        for rec in self.filtered(lambda r: r.state in ("queued", "running")):
            rec.write({"state": "failed", "error": _("Скасовано користувачем"), "date_end": fields.Datetime.now()})
        return True
