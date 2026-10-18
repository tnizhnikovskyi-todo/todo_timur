"""M-H4 `td.energy.round` (обхід), M-H5 `td.energy.round.item` (пункт); API-H1…API-H6, крони R-H1, R-H2 (W4-C).
Відповідь `get_mobile` — `contracts/api_h1_get_mobile.json`. Запис пунктів виконують лише методи (`sudo()` після
перевірки групи й виконавця, R-H3); ключів вартості в відповідях немає."""

import logging
import time
from datetime import timedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.td_energy.tools import bus, dates
from odoo.addons.td_energy.tools.dates import param_bool

from ..tools import schedule, value

_logger = logging.getLogger(__name__)

G_USER = "td_energy.group_td_energy_user"
G_MANAGER = "td_energy.group_td_energy_manager"
G_CHIEF = "td_energy.group_td_energy_chief"
G_ADMIN = "td_factory3d.group_td_admin"

OPEN = ("open", "in_progress")
CLOSED = ("done", "missed")
REFRESH_S = 30
OFF_SCHEDULE = "поза розкладом"
OFF_SCHEDULE_H = 2  # «поза розкладом»: due_at = now + 2 год (AC-H26)
ROTATE_BUDGET_S = 10
ROTATE_BATCH = 500
SNAPSHOT_FIELDS = (
    "sequence", "code", "title", "hint", "source", "norm_kind", "norm_min", "norm_max", "unit", "precision",
    "required",
)  # fmt: skip


def _param(env, key, default):
    """`td.energy_mobile.<key>`; Boolean-налаштування, збережене як `False`, прибирає параметр (див. res.config)."""
    val = env["ir.config_parameter"].sudo().get_param("td.energy_mobile." + key)
    return default if val in (None, False, "") else val


def _param_flag(env, key):
    """Булевий параметр: відсутній (у т. ч. після зняття прапорця в налаштуваннях) — `False`."""
    return str(_param(env, key, "")).strip().lower() in ("1", "true", "yes", "on")


def _param_int(env, key, default):
    try:
        return int(float(_param(env, key, default)))
    except (TypeError, ValueError):
        return default


class TdEnergyRound(models.Model):
    _name = "td.energy.round"
    _description = "Енергетика: обхід"
    _inherit = ["mail.thread"]
    _order = "date desc, starts_at desc, id desc"

    name = fields.Char(string="Назва", compute="_compute_name", store=True)
    template_id = fields.Many2one(
        "td.energy.round.template", string="Шаблон", required=True, index=True, ondelete="restrict"
    )
    slot_id = fields.Many2one("td.energy.round.slot", string="Слот", ondelete="set null")
    slot_name = fields.Char(string="Назва слота")
    date = fields.Date(string="Дата (Київ)", required=True, index=True)
    starts_at = fields.Datetime(string="Початок слота", required=True)
    due_at = fields.Datetime(string="Кінець слота", required=True)
    state = fields.Selection(
        [
            ("open", "Відкритий"),
            ("in_progress", "У роботі"),
            ("done", "Завершено"),
            ("missed", "Не виконано"),
            ("cancelled", "Скасовано"),
        ],
        string="Стан",
        default="open",
        index=True,
        tracking=True,
    )
    performer_id = fields.Many2one("res.users", string="Виконавець", readonly=True)
    started_at = fields.Datetime(string="Розпочато", readonly=True)
    finished_at = fields.Datetime(string="Завершено", readonly=True)
    item_ids = fields.One2many("td.energy.round.item", "round_id", string="Пункти")
    total_count = fields.Integer(string="Пунктів", compute="_compute_counts", store=True)
    done_count = fields.Integer(string="Виконано", compute="_compute_counts", store=True)
    progress_pct = fields.Integer(string="Прогрес, %", compute="_compute_counts", store=True)
    deviation_count = fields.Integer(string="Відхилень", compute="_compute_counts", store=True)
    note = fields.Char(string="Примітка", size=256)
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)

    _td_energy_round_slot_date_uniq = models.Constraint(
        "UNIQUE(template_id, slot_id, date)", "Обхід цього слота на цю дату вже є."
    )

    @api.depends("template_id.name", "slot_name", "date")
    def _compute_name(self):
        for rec in self:
            day = rec.date.strftime("%d.%m") if rec.date else ""
            rec.name = " · ".join(p for p in (rec.template_id.name, rec.slot_name, day) if p)

    @api.depends("item_ids.done", "item_ids.result")
    def _compute_counts(self):
        for rec in self:
            total = len(rec.item_ids)
            done = len(rec.item_ids.filtered("done"))
            rec.total_count = total
            rec.done_count = done
            rec.progress_pct = round(done * 100 / total) if total else 0
            rec.deviation_count = len(rec.item_ids.filtered(lambda i: i.result == "deviation"))

    # --- доступ ----------------------------------------------------------------------------------------
    @api.model
    def _td_require(self, group=G_USER):
        if self.env.is_superuser() or self.env.user.has_group(group):
            return
        raise AccessError(_("Немає доступу до Енергетики."))

    def _td_is_chief(self):
        return self.env.is_superuser() or self.env.user.has_group(G_CHIEF)

    # --- створення (R-H1, API-H4) ----------------------------------------------------------------------
    @api.model
    def _td_create_round(self, template, slot, day, starts_at, due_at, slot_name=None):
        """Обхід зі знімком пунктів шаблону (наступні правки шаблона його не змінюють)."""
        items = []
        for tpl in template.item_ids:
            vals = {field: tpl[field] for field in SNAPSHOT_FIELDS}
            vals["node_id"] = tpl.node_id.id
            items.append(Command.create(vals))
        return (
            self.sudo()
            .with_context(mail_create_nolog=True)
            .create(
                {
                    "template_id": template.id,
                    "slot_id": slot.id or False,
                    "slot_name": slot_name or slot.name,
                    "date": day,
                    "starts_at": starts_at,
                    "due_at": due_at,
                    "state": "open",
                    "company_id": template.company_id.id,
                    "item_ids": items,
                }
            )
        )

    # --- значення пунктів (R-H4) -----------------------------------------------------------------------
    def _td_item_values(self, items, now):
        """{item.id: float | None} одним проходом: один `search_read` сигналів і один `get_pult(kpis)` на всі пункти."""
        fresh_s = _param_int(self.env, "value_fresh_s", 120)
        parsed = {item.id: value.parse_source(item.source) for item in items}
        codes = {ref for kind, ref in filter(None, parsed.values()) if kind == "signal"}
        values = {}
        signals = {}
        if codes:
            rows = self.env["td.signal"].sudo().search_read(
                [("code", "in", sorted(codes))], ["code", "last_value", "last_ts", "period_s"]
            )  # fmt: skip
            signals = {r["code"]: r for r in rows}
        pult = None
        if any(src and src[0] == "pult" for src in parsed.values()):
            try:
                pult = self.env["td.energy.dashboard"].get_pult(period="now", parts=["kpis"])
            except Exception:
                _logger.warning("td_energy_mobile: get_pult для значень обходу недоступний", exc_info=True)
        for item in items:
            src = parsed[item.id]
            val = None
            if src and src[0] == "signal":
                row = signals.get(src[1])
                if row and value.is_fresh(row["last_ts"], now, row["period_s"], fresh_s):
                    val = row["last_value"]
            elif src and src[0] == "pult" and pult is not None:
                val = value.walk_path(pult, src[1])
            values[item.id] = val
        return values

    # --- відповіді (API-H1, API-H2) ------------------------------------------------------------------
    def _td_title(self):
        """«Обхід ТП і ГРЩ · зміна 2» (назва слота — з малої літери, як у макеті)."""
        self.ensure_one()
        slot = (self.slot_name or "")[:1].lower() + (self.slot_name or "")[1:]
        return " · ".join(p for p in (self.template_id.name, slot) if p)

    def _td_round_payload(self, now, values):
        """JSON обходу (`get_mobile.round`); `self` — один запис, `sudo`; користувач — `self.env.user`."""
        self.ensure_one()
        user = self.env.user
        manager = user.has_group(G_MANAGER)
        chief = user.has_group(G_CHIEF)
        performer = self.performer_id
        can_edit = (
            self.state in OPEN and manager and (not performer or performer == user or chief)
        )  # fmt: skip
        left = len(self.item_ids.filtered(lambda i: i.required and not i.done))
        finish_blocked = _("залишилось %s", left) if left else None
        items = []
        for item in self.item_ids:
            node_code = item.node_id.code or ""
            items.append(
                {
                    "id": item.id,
                    "code": item.code,
                    "title": item.title,
                    "hint": value.hint(
                        item.hint, bool(value.parse_source(item.source)), item.norm_kind, item.norm_min,
                        item.norm_max, item.unit, item.precision, values.get(item.id),
                    ),  # fmt: skip
                    "done": item.done,
                    "result": item.result,
                    "value_text": item.value_text or "",
                    "comment": item.comment or "",
                    "node_code": node_code,
                    "can_3d": bool(node_code),
                }
            )
        return {
            "id": self.id,
            "title": self._td_title(),
            "state": self.state,
            "slot": self.slot_name or "",
            "due_local": schedule.local_hhmm(self.due_at),
            "performer": {"id": performer.id, "name": performer.name, "is_me": performer == user}
            if performer
            else None,
            "done_count": self.done_count,
            "total_count": self.total_count,
            "progress_pct": self.progress_pct,
            "can_edit": can_edit,
            "can_finish": finish_blocked is None,
            "finish_blocked": finish_blocked,
            "items": items,
        }

    def _td_history_row(self, today):
        self.ensure_one()
        title = self._td_title()
        if self.date and self.date != today:
            title += " · " + self.date.strftime("%d.%m")
        return {
            "id": self.id,
            "title": title,
            "state": self.state,
            "finished_at_local": schedule.local_hhmm(self.finished_at) if self.finished_at else "",
            "done_count": self.done_count,
            "total_count": self.total_count,
            "deviation_count": self.deviation_count,
            "performer": self.performer_id.name or "",
        }

    @api.model
    def _td_pick_round(self, now, round_id=None):
        """R-H6 п. 1: вказаний обхід або `open`/`in_progress` за сьогодні: слот, що містить `now`, першим, далі за `starts_at`."""
        if round_id:
            rnd = self.browse(int(round_id)).exists()
            if rnd:
                rnd.check_access("read")
            return rnd
        today = dates.local_day(now)
        rounds = self.search([("state", "in", OPEN), "|", ("date", "=", today), ("due_at", ">", now)])
        return rounds.sorted(lambda r: (not (r.starts_at <= now < r.due_at), r.starts_at, r.id))[:1]

    @api.model
    def get_mobile(self, round_id=None):
        """API-H1: JSON вкладки «Обхід»: `{meta, round, next, history}` (R-H6)."""
        self._td_require(G_USER)
        now = dates.now_utc(self.env)
        today = dates.local_day(now)
        rnd = self._td_pick_round(now, round_id).sudo()
        payload_round = None
        nxt = None
        if rnd:
            payload_round = rnd._td_round_payload(now, rnd._td_item_values(rnd.item_ids, now))
        else:
            slots = self.env["td.energy.round.slot"].search([("template_id.active", "=", True)])
            found = schedule.next_slot_today(now, [(s.name, s.time_from, s.weekdays) for s in slots])
            nxt = {"slot": found[0], "starts_local": found[1]} if found else None
        limit = max(_param_int(self.env, "history_limit", 3), 0)
        history = self.search([("state", "in", CLOSED)], limit=limit).sudo()
        return {
            "meta": {
                "now_local": schedule.local_hhmm(now),
                "refresh_s": REFRESH_S,
                "can_edit": self.env.is_superuser() or self.env.user.has_group(G_MANAGER),
            },
            "round": payload_round,
            "next": nxt,
            "history": [r._td_history_row(today) for r in history],
        }

    # --- дії (API-H2…API-H6) -----------------------------------------------------------------------------
    def _td_lock(self):
        """R-H3 п. 2: `SELECT … FOR UPDATE` рядка обходу; потім перечитати стан і виконавця."""
        self.env.cr.execute("SELECT id FROM td_energy_round WHERE id = %s FOR UPDATE", (self.id,))
        self.invalidate_recordset(["state", "performer_id", "started_at"])

    def _td_claim(self, user, now, chief):
        """Виконавець блокується за першим, хто відмітив; чужий (не chief) — `UserError` (D-76).
        `chief` обчислює метод API в середовищі користувача (запис обходу тут — під `sudo`)."""
        self.ensure_one()
        if self.state not in OPEN:
            raise UserError(_("Обхід уже закрито."))
        performer = self.performer_id
        if not performer:
            self.write({"performer_id": user.id, "state": "in_progress", "started_at": now})
        elif performer != user and not chief:
            raise UserError(_("Обхід виконує %s.", performer.name))

    @api.model
    def action_toggle_item(self, item_id, done, comment=None):
        """API-H2 (R-H3): відмітка пункту; → `{"round": <як get_mobile.round>}`."""
        self._td_require(G_MANAGER)
        item = self.env["td.energy.round.item"].sudo().browse(int(item_id)).exists()
        if not item:
            raise UserError(_("Пункт обходу не знайдено."))
        rnd = item.round_id
        self.browse(rnd.id).check_access("read")  # правила компанії для користувача (sudo їх обходить)
        rnd._td_lock()
        user, now = self.env.user, dates.now_utc(self.env)
        rnd._td_claim(user, now, self._td_is_chief())
        values = rnd._td_item_values(rnd.item_ids, now)
        vals = {}
        if comment is not None:
            vals["comment"] = (comment or "")[:256]
        if done:
            val = values.get(item.id)
            vals.update(
                done=True,
                done_at=now,
                done_by=user.id,
                value=val if val is not None else 0.0,
                value_text=value.fmt_value(val, item.unit, item.precision) if item.source else "",
                result=value.evaluate(item.norm_kind, item.norm_min, item.norm_max, val),
            )
        else:
            vals.update(done=False, done_at=False, done_by=False, value=0.0, value_text="", result="pending")
        item.write(vals)
        bus.tick(self.env, "state")
        return {"round": rnd._td_round_payload(now, values)}

    @api.model
    def action_finish(self, round_id, note=None):
        """API-H3 (R-H5): завершення; → `{"finished_at_local": "HH:MM", "deviation_count": n}`."""
        self._td_require(G_MANAGER)
        if isinstance(round_id, models.BaseModel):
            round_id = round_id.id
        elif isinstance(round_id, (list, tuple)):  # кнопка форми викликає метод із `ids`
            round_id = round_id[0] if round_id else None
        rnd = self.sudo().browse(int(round_id or 0)).exists()
        if not rnd:
            raise UserError(_("Обхід не знайдено."))
        self.browse(rnd.id).check_access("read")
        rnd._td_lock()
        user, now = self.env.user, dates.now_utc(self.env)
        rnd._td_claim(user, now, self._td_is_chief())
        left = len(rnd.item_ids.filtered(lambda i: i.required and not i.done))
        if left:
            raise UserError(_("Позначте всі пункти обходу: залишилось %s.", left))
        vals = {"state": "done", "finished_at": now}
        if note:
            vals["note"] = note[:256]
        rnd.write(vals)
        for item in rnd.item_ids.filtered(lambda i: i.result == "deviation"):
            event = self.env["td.energy.event"]._td_log(
                "warn", "round", "ROUND-%s-%s" % (rnd.id, item.code),
                _("Обхід: %(title)s — поза нормою (%(value)s)", title=item.title, value=item.value_text),
                node=item.node_id, dedup_min=1440,
            )  # fmt: skip
            if event:
                item.event_id = event.id
        rnd.message_post(
            body=_(
                "Обхід завершено: %(done)s/%(total)s, відхилень %(dev)s",
                done=rnd.done_count, total=rnd.total_count, dev=rnd.deviation_count,
            )  # fmt: skip
        )
        bus.tick(self.env, "state")
        return {"finished_at_local": schedule.local_hhmm(now), "deviation_count": rnd.deviation_count}

    @api.model
    def action_start(self, template_id, slot_id=None):
        """API-H4 (FR-H2): ручний запуск, якщо немає відкритого обходу шаблону → `round_id`."""
        self._td_require(G_MANAGER)
        template = self.env["td.energy.round.template"].browse(int(template_id or 0)).exists()
        if not template:
            raise UserError(_("Шаблон обходу не знайдено."))
        now = dates.now_utc(self.env)
        today = dates.local_day(now)
        if self.sudo().search_count([("template_id", "=", template.id), ("state", "in", OPEN)]):
            raise UserError(_("Обхід уже відкритий."))
        slot = self.env["td.energy.round.slot"]
        if slot_id:
            slot = template.slot_ids.filtered(lambda s: s.id == int(slot_id))
            if not slot:
                raise UserError(_("Слот не належить шаблону."))
            if self.sudo().search_count([("template_id", "=", template.id), ("slot_id", "=", slot.id), ("date", "=", today)]):
                raise UserError(_("Обхід уже відкритий."))
        starts_at, due_at = now, now + timedelta(hours=OFF_SCHEDULE_H)
        if slot:
            starts_at, due_at = schedule.slot_bounds(today, slot.time_from, slot.time_to)
            if due_at <= now:
                starts_at, due_at = now, now + timedelta(hours=OFF_SCHEDULE_H)
        rnd = self._td_create_round(template, slot, today, starts_at, due_at, slot_name=None if slot else OFF_SCHEDULE)
        bus.tick(self.env, "state")
        return rnd.id

    @api.model
    def action_start_now(self):
        """V-H4: «Запустити обхід зараз» — перший активний шаблон без відкритого обходу; відкриває форму обходу."""
        self._td_require(G_MANAGER)
        busy = self.sudo().search([("state", "in", OPEN)]).template_id
        template = self.env["td.energy.round.template"].search([("id", "not in", busy.ids)], limit=1)
        if not template:
            raise UserError(_("Обхід уже відкритий."))
        rnd_id = self.action_start(template.id)
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": rnd_id,
            "views": [[False, "form"]],
            "target": "current",
        }

    def action_finish_form(self):
        """Кнопка «Завершити» форми журналу (chief): `action_finish` для запису → `True`."""
        self.ensure_one()
        self.action_finish(self.id)
        return True

    def action_cancel(self):
        """API-H6: скасування відкритого обходу (chief) → `True`."""
        if not self._td_is_chief():
            raise AccessError(_("Немає доступу до Енергетики."))
        now = dates.now_utc(self.env)
        for rnd in self.sudo():
            if rnd.state not in OPEN:
                raise UserError(_("Обхід уже закрито."))
            rnd.write({"state": "cancelled", "finished_at": now})
        bus.tick(self.env, "state")
        return True

    @api.model
    def get_journal(self, limit=20, offset=0):
        """API-H5 (R-H7): `{"items": [...], "total": n}` — серверне представлення журналу для «Усі обходи»."""
        self._td_require(G_USER)
        rows = self.search([], limit=max(int(limit or 0), 0), offset=max(int(offset or 0), 0))
        return {
            "items": [
                {
                    "id": r.id,
                    "name": r.name,
                    "date": fields.Date.to_string(r.date),
                    "state": r.state,
                    "performer": r.performer_id.name or "",
                    "finished_at_local": schedule.local_hhmm(r.finished_at) if r.finished_at else "",
                    "done_count": r.done_count,
                    "total_count": r.total_count,
                    "deviation_count": r.deviation_count,
                }
                for r in rows
            ],
            "total": self.search_count([]),
        }

    # --- крони (H.6) ---------------------------------------------------------------------------------------
    @api.model
    def _cron_open(self):
        """R-H1: для кожного слота активних шаблонів, чиє вікно містить `now` у відповідний день тижня, — обхід."""
        if not param_bool(self.env, "read_enabled"):
            return 0
        now = dates.now_utc(self.env)
        today = dates.local_day(now)
        created = 0
        try:
            existing = {(r.template_id.id, r.slot_id.id) for r in self.sudo().search([("date", "=", today)])}
            slots = self.env["td.energy.round.slot"].sudo().search([("template_id.active", "=", True)])
            for slot in slots:
                if (slot.template_id.id, slot.id) in existing:
                    continue
                if not schedule.slot_runs(today, slot.weekdays, slot.time_from, slot.time_to, now):
                    continue
                starts_at, due_at = schedule.slot_bounds(today, slot.time_from, slot.time_to)
                try:
                    with self.env.cr.savepoint():
                        self._td_create_round(slot.template_id, slot, today, starts_at, due_at)
                    created += 1
                except Exception:
                    _logger.exception("td_energy_mobile: відкриття обходу слота %s", slot.id)
        except Exception:
            _logger.exception("td_energy_mobile: крон відкриття обходів")
        if created:
            bus.tick(self.env, "state")
        return created

    @api.model
    def _cron_close(self):
        """R-H2: `open`/`in_progress` з `due_at < now` → `missed` (`finished_at = due_at`) і попередження в «Подіях»."""
        if not param_bool(self.env, "read_enabled"):
            return 0
        now = dates.now_utc(self.env)
        events = _param_flag(self.env, "missed_event")
        closed = 0
        try:
            for rnd in self.sudo().search([("state", "in", OPEN), ("due_at", "<", now)]):
                with self.env.cr.savepoint():
                    rnd.write({"state": "missed", "finished_at": rnd.due_at})
                    if events:
                        text = _("Обхід не завершено: %s", rnd.name)
                        self.env["td.energy.event"]._td_log(
                            "warn", "round", "ROUND-%s" % rnd.id, text, title=text,
                            detail=_("Виконано %(done)s/%(total)s.", done=rnd.done_count, total=rnd.total_count),
                            dedup_min=1440,
                        )  # fmt: skip
                closed += 1
        except Exception:
            _logger.exception("td_energy_mobile: крон закриття обходів")
        if closed:
            bus.tick(self.env, "state")
        return closed

    @api.model
    def _cron_rotate(self):
        """Ротація: видалити обходи старші за `keep_days` (пакетами, ≤ 10 с)."""
        if not param_bool(self.env, "read_enabled"):
            return 0
        cutoff = dates.now_utc(self.env) - timedelta(days=_param_int(self.env, "keep_days", 730))
        deadline = time.monotonic() + ROTATE_BUDGET_S
        deleted = 0
        try:
            while time.monotonic() < deadline:
                batch = self.sudo().search([("due_at", "<", cutoff)], limit=ROTATE_BATCH)
                if not batch:
                    break
                deleted += len(batch)
                batch.unlink()
        except Exception:
            _logger.exception("td_energy_mobile: ротація обходів")
        return deleted


class TdEnergyRoundItem(models.Model):
    _name = "td.energy.round.item"
    _description = "Енергетика: пункт обходу"
    _order = "sequence, id"

    round_id = fields.Many2one("td.energy.round", string="Обхід", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    code = fields.Char(string="Код", size=16)
    title = fields.Char(string="Назва", size=128)
    hint = fields.Char(string="Підказка", size=128)
    source = fields.Char(string="Джерело значення", size=96)
    norm_kind = fields.Selection(
        [("none", "Без норми"), ("max", "до"), ("min", "від"), ("range", "діапазон")], string="Норма", default="none"
    )
    norm_min = fields.Float(string="Норма від")
    norm_max = fields.Float(string="Норма до")
    unit = fields.Char(string="Одиниця", size=16)
    precision = fields.Integer(string="Знаків після коми", default=0)
    required = fields.Boolean(string="Обов'язковий", default=True)
    node_id = fields.Many2one("td.energy.node", string="Вузол (3D)", ondelete="set null")
    done = fields.Boolean(string="Виконано", default=False)
    done_at = fields.Datetime(string="Відмічено", readonly=True)
    done_by = fields.Many2one("res.users", string="Відмітив", readonly=True)
    value = fields.Float(string="Значення")
    value_text = fields.Char(string="Значення (текст)", size=32)
    result = fields.Selection(
        [("pending", "Очікує"), ("ok", "У нормі"), ("deviation", "Поза нормою")],
        string="Результат",
        default="pending",
    )
    comment = fields.Char(string="Коментар", size=256)
    event_id = fields.Many2one("td.energy.event", string="Подія", ondelete="set null", readonly=True)
    request_id = fields.Many2one("maintenance.request", string="Заявка ТО", ondelete="set null")

    def write(self, vals):
        """Пункти змінюють методи обходу (`sudo`, R-H3); прямий запис клієнта — лише `group_td_admin`."""
        if not (self.env.su or self.env.user.has_group(G_ADMIN)):
            raise AccessError(_("Пункти обходу змінюються лише через методи обходу."))
        return super().write(vals)
