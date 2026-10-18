"""M-33 `td.energy.action` — дія оператора, автоматики й конфігурації: журнал і потік prepare → confirm → виконання."""

import hashlib
import hmac
import json
import logging
import secrets
from datetime import timedelta

from odoo import _, api, fields, models, tools as odoo_tools
from odoo.exceptions import AccessError, UserError

from odoo.addons.td_energy.tools import bus as energy_bus
from odoo.addons.td_energy.tools import dates

from .. import tools
from ..tools import bus, genset_link, kinds

_logger = logging.getLogger(__name__)

STATES = [
    ("prepared", "Підготовлено"),
    ("awaiting_second", "Очікує другого підтвердження"),
    ("queued", "У черзі"),
    ("sent", "Передано збирачу"),
    ("executing", "Виконується"),
    ("done", "Виконано"),
    ("failed", "Не виконано"),
    ("blocked", "Заблоковано"),
    ("expired", "Прострочено"),
    ("cancelled", "Скасовано"),
]
ORIGINS = [
    ("manual", "Вручну"),
    ("advice", "Рекомендація"),
    ("schedule", "Розклад"),
    ("auto", "Автоматика"),
    ("undo", "Скасування"),
    ("config", "Конфігурація"),
]
RANK = {"prepared": 0, "awaiting_second": 1, "queued": 2, "sent": 3, "executing": 4}
FINAL = ("done", "failed", "blocked", "expired", "cancelled")
ACTIVE_RESOURCE = ("queued", "sent", "executing")
JOURNAL_STATES = ("awaiting_second", "queued", "sent", "executing", "done", "failed", "blocked", "expired")
CHIPS = {
    "done": ("виконано", "ok"),
    "queued": ("виконується", "info"),
    "sent": ("виконується", "info"),
    "executing": ("виконується", "info"),
    "awaiting_second": ("очікує 2-го підтвердження", "info"),
    "failed": ("не виконано", "bad"),
    "blocked": ("заблоковано", "bad"),
    "expired": ("прострочено", "muted"),
    "cancelled": ("скасовано", "muted"),
    "prepared": ("підготовлено", "muted"),
}
TOKEN_NOT_FOUND = "Підтвердження не знайдено. Відкрийте діалог знову."
WRITE_OFF = "Керування вимкнено: td.energy_control.write_enabled. Зверніться до адміністратора."


def _hash(token):
    return hashlib.sha256((token or "").encode()).hexdigest()


class TdEnergyAction(models.Model):
    _name = "td.energy.action"
    _description = "Енергетика: дія керування"
    _order = "create_date desc, id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Номер", readonly=True, copy=False)
    kind_id = fields.Many2one("td.energy.command.kind", string="Вид команди", index=True, ondelete="restrict")
    kind_code = fields.Char(string="Код виду", size=48, index=True)
    origin = fields.Selection(ORIGINS, string="Джерело", default="manual", index=True)
    cls = fields.Selection([("A", "A"), ("B", "B")], string="Клас")
    state = fields.Selection(STATES, string="Стан", default="prepared", index=True, tracking=True)
    params = fields.Json(string="Параметри")
    checks = fields.Json(string="Перевірки Odoo")
    collector_checks = fields.Json(string="Перевірки збирача")
    token_hash = fields.Char(size=64, index=True, copy=False)
    token_expires_at = fields.Datetime(string="Токен діє до")
    needs_second = fields.Boolean(string="Потрібне друге підтвердження")
    prepared_by = fields.Many2one("res.users", string="Підготував", readonly=True, ondelete="set null")
    confirmed_by = fields.Many2one("res.users", string="Підтвердив", readonly=True, ondelete="set null")
    second_by = fields.Many2one("res.users", string="Друге підтвердження", readonly=True, ondelete="set null")
    prepared_at = fields.Datetime(string="Підготовлено", readonly=True)
    confirmed_at = fields.Datetime(string="Підтверджено", readonly=True)
    second_at = fields.Datetime(string="Друге підтвердження о", readonly=True)
    second_expires_at = fields.Datetime(string="Друге підтвердження до", readonly=True)
    started_at = fields.Datetime(string="Розпочато", readonly=True)
    finished_at = fields.Datetime(string="Завершено", readonly=True)
    command_id = fields.Many2one("td.command", string="Команда", ondelete="set null", readonly=True)
    scenario_id = fields.Many2one("td.energy.scenario", string="Сценарій", ondelete="set null")
    node_id = fields.Many2one("td.energy.node", string="Вузол", ondelete="set null")
    advice_id = fields.Many2one("td.energy.advice", string="Рекомендація", ondelete="set null")
    undo_of_id = fields.Many2one("td.energy.action", string="Скасовує дію", ondelete="set null")
    undone_by_id = fields.Many2one("td.energy.action", string="Скасована дією", ondelete="set null", readonly=True)
    undo_params = fields.Json(string="Параметри скасування")
    undo_available = fields.Boolean(string="Можна скасувати", compute="_compute_undo")
    config_version = fields.Integer(string="Версія конфігурації")
    applied = fields.Boolean(string="Застосовано", compute="_compute_applied")
    idem = fields.Char(size=40)
    step = fields.Integer(string="Крок")
    steps_total = fields.Integer(string="Кроків")
    summary = fields.Char(size=128, string="Дія")
    detail = fields.Char(size=256, string="Деталі")
    actor_text = fields.Char(size=96, string="Виконавець")
    result_text = fields.Char(size=96, string="Результат")
    error = fields.Char(size=256, string="Помилка")
    ref_model = fields.Char(string="Об'єкт (модель)")
    ref_id = fields.Integer(string="Об'єкт (id)")

    _td_second_distinct = models.Constraint(
        "CHECK(second_by IS NULL OR (second_by IS DISTINCT FROM prepared_by "
        "AND second_by IS DISTINCT FROM confirmed_by))",
        "Друге підтвердження має дати інший енергетик.",
    )

    def init(self):
        cr = self.env.cr
        cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS td_energy_action_idem_uniq ON td_energy_action (idem) "
            "WHERE idem IS NOT NULL"
        )
        odoo_tools.sql.create_index(cr, "td_energy_action_state_created_idx", self._table, ["state", "create_date"])
        odoo_tools.sql.create_index(cr, "td_energy_action_kind_state_idx", self._table, ["kind_code", "state"])
        odoo_tools.sql.create_index(cr, "td_energy_action_node_created_idx", self._table, ["node_id", "create_date"])

    # --- права ------------------------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            vals.setdefault("name", seq.next_by_code("td.energy.action") or "ACT")
        return super().create(vals_list)

    def write(self, vals):
        if not tools.is_internal(self.env):
            raise AccessError(_("Дії керування змінюються лише методами модуля."))
        return super().write(vals)

    def unlink(self):
        if not self.env.user.has_group("td_factory3d.group_td_admin") and not tools.is_internal(self.env):
            raise AccessError(_("Журнал керування не видаляється."))
        return super().unlink()

    def _me(self):
        """Запис під sudo з внутрішнім контекстом (єдина форма зміни стану)."""
        return self.sudo().with_context(td_energy_control_internal=True)

    # --- обчислювані ------------------------------------------------------------------------------------------
    @api.depends("state", "finished_at", "undone_by_id", "kind_id", "undo_params")
    def _compute_undo(self):
        for rec in self:
            rec.undo_available = not rec._td_undo_reason()

    def _td_undo_reason(self):
        """R-56 п.5: '' якщо скасування доступне, інакше причина."""
        self.ensure_one()
        now = dates.now_utc(self.env)
        window = tools.cparam_int(self.env, "undo_window_min", 15)
        if self.state != "done":
            return "дія не виконана"
        if self.undone_by_id:
            return "дію вже скасовано"
        undo_kind = self.kind_id.undo_kind_id
        if not undo_kind:
            return "немає зворотної дії"
        if self.kind_code == "air_setpoint" and not (self.undo_params or {}).get("setpoint_bar"):
            return "невідома попередня уставка"
        if not self.finished_at or self.finished_at < now - timedelta(minutes=window):
            return "минуло понад %d хв" % window
        later = (
            self.sudo().search_count(
                [
                    ("id", ">", self.id),
                    ("kind_id.resource", "=", self.kind_id.resource),
                    ("state", "in", ("queued", "sent", "executing", "done")),
                    ("origin", "!=", "auto"),
                    ("confirmed_at", "!=", False),
                ]
            )
            if self.kind_id.resource != "config"
            else 0
        )
        if later:
            return "є пізніша дія над цим ресурсом"
        return ""

    @api.depends("config_version", "state")
    def _compute_applied(self):
        applied = self.env["td.energy.control.state"].get().applied_version
        for rec in self:
            if rec.kind_id.executor == "config":
                rec.applied = applied >= rec.config_version
            else:
                rec.applied = rec.state == "done"

    def _td_state_label(self):
        return dict(STATES).get(self.state, self.state)

    def _td_result_chip(self):
        """R-56 п.4: (текст, вид) чипа результату журналу."""
        self.ensure_one()
        if self.state == "done" and self.kind_id.executor == "config" and not self.applied:
            return "збережено, очікує збирач", "info"
        return CHIPS.get(self.state, (self.state, "muted"))

    # --- prepare ----------------------------------------------------------------------------------------------
    @api.model
    def _td_prepare(self, kind, params, origin="manual", advice=None, undo_of=None):
        """Створити `prepared` + токен. Повертає (запис, токен). Права перевіряє виклик (M-35)."""
        env, user = self.env, self.env.user
        kind._td_check_remote()
        if not kind.available:
            raise UserError(_("Команда «%(name)s» недоступна: %(why)s.", name=kind.name, why=kind.unavailable_reason))
        if kind.executor in ("intent", "genset") and not tools.cparam_bool(env, "write_enabled"):
            raise UserError(WRITE_OFF)
        params = kind.normalize(params)
        now = dates.now_utc(env)
        same = (
            self.sudo()
            .search(
                [
                    ("prepared_by", "=", user.id),
                    ("kind_id", "=", kind.id),
                    ("state", "=", "prepared"),
                    ("origin", "=", origin),
                    ("prepared_at", ">=", now - timedelta(seconds=5)),
                ]
            )
            .filtered(lambda r: json.dumps(r.params, sort_keys=True) == json.dumps(params, sort_keys=True))[:1]
        )
        token = secrets.token_urlsafe(24)
        rendered = kind.render(params)
        checks, blocked, reason = kind.build_checks(params)
        needs_second = kind.cls == "B" and not user.has_group("td_energy.group_td_energy_chief")
        vals = {
            "token_hash": _hash(token),
            "token_expires_at": now + timedelta(seconds=tools.cparam_int(env, "confirm_ttl_s", 60)),
            "checks": checks,
            "needs_second": needs_second,
        }
        if same:
            rec = same._me()
            rec.write(vals)
        else:
            prefix = "Скасування: " if origin == "undo" else ""
            rec = (
                self.sudo()
                .with_context(td_energy_control_internal=True, mail_create_nolog=True)
                .create(
                    dict(
                        vals,
                        kind_id=kind.id,
                        kind_code=kind.code,
                        origin=origin,
                        cls=kind.cls,
                        state="prepared",
                        params=params,
                        prepared_by=user.id,
                        prepared_at=now,
                        summary=(prefix + rendered["label"])[:128],
                        detail=(rendered["sub"] or "")[:256],
                        actor_text=user.name[:96],
                        advice_id=advice.id if advice else False,
                        undo_of_id=undo_of.id if undo_of else False,
                        node_id=self._td_node_for(kind).id,
                    )
                )
            )
            rec.message_post(body=_("Підготовлено: %s", rec.summary), subtype_xmlid="mail.mt_note")
        return rec, token, rendered, blocked, reason

    @api.model
    def _td_node_for(self, kind):
        code = {"qs": "QS", "bess": "BESS", "chp": "CHP", "genset": "GENSET"}.get(kind.resource)
        return (
            self.env["td.energy.node"].sudo().search([("code", "=", code)], limit=1)
            if code
            else self.env["td.energy.node"]
        )

    # --- confirm ----------------------------------------------------------------------------------------------
    def _td_lock(self):
        self.env.cr.execute("SELECT id FROM td_energy_action WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset()

    @api.model
    def _td_by_token(self, token):
        h = _hash(token)
        rec = self.sudo().search([("token_hash", "=", h)], limit=1)
        if not rec or not hmac.compare_digest(rec.token_hash or "", h):
            raise UserError(_(TOKEN_NOT_FOUND))
        if rec.prepared_by != self.env.user:
            raise AccessError(_("Токен належить іншому користувачу."))
        return rec

    def _td_response(self, message=None, reason=None):
        self.ensure_one()
        return {
            "action_id": self.id,
            "state": self.state,
            "state_label": self._td_state_label(),
            "needs_second": bool(self.needs_second and self.state == "awaiting_second"),
            "message": message,
            "blocked_reason": reason or (self.error if self.state == "blocked" else None),
        }

    def _td_confirm(self, token):
        """API-18 (R-40 п.3): токен → `awaiting_second` / `queued` / `blocked` / `done` (config)."""
        rec = self._td_by_token(token)
        rec._td_lock()
        now = dates.now_utc(self.env)
        if rec.state in ("cancelled", "expired"):
            raise UserError(_(TOKEN_NOT_FOUND))
        if rec.state != "prepared":
            return rec._td_response(_("Уже надіслано"))
        if rec.token_expires_at and rec.token_expires_at < now:
            rec._me()._td_close("expired", "прострочено")
            raise UserError(_("Час підтвердження минув. Відкрийте діалог знову."))
        kind = rec.kind_id
        kind._td_check_remote()
        me = rec._me()
        why = rec._td_write_blocked_reason()
        if why:
            text = "Запис вимкнено: %s" % why
            me._td_close("blocked", "заблоковано", text)
            return rec._td_response(reason=text)
        checks, blocked, reason = kind.build_checks(rec.params or {})
        me.write({"checks": checks})
        if blocked:
            me._td_close("blocked", "заблоковано", reason)
            return rec._td_response(reason=reason)
        busy = rec._td_resource_conflict()
        if busy:
            text = _("Для ресурсу «%(res)s» уже виконується дія %(name)s", res=kind.resource, name=busy.name)
            me._td_close("blocked", "заблоковано", text)
            return rec._td_response(reason=text)
        me.write(
            {
                "confirmed_by": self.env.uid,
                "confirmed_at": now,
                "undo_params": rec._td_capture_undo(),
            }
        )
        me.message_post(body=_("Підтверджено: %s", self.env.user.name), subtype_xmlid="mail.mt_note")
        if rec.needs_second and not self.env.user.has_group("td_energy.group_td_energy_chief"):
            me.write(
                {
                    "state": "awaiting_second",
                    "second_expires_at": now + timedelta(seconds=tools.cparam_int(self.env, "second_ttl_s", 600)),
                }
            )
            me._td_notify_second()
            bus.tick(self.env, "action")
            return rec._td_response(_("Очікуємо друге підтвердження іншим енергетиком."))
        me.write({"needs_second": False})
        me._td_enqueue()
        return rec._td_response()

    def _td_confirm_second(self):
        """API-19 (R-40 п.5): друге підтвердження іншою особою."""
        self.ensure_one()
        user = self.env.user
        if not user.has_group("td_energy.group_td_energy_manager"):
            raise AccessError(_("Керувати енергетикою може лише енергетик."))
        self._td_lock()
        rec = self.sudo()
        now = dates.now_utc(self.env)
        if rec.state == "expired":
            raise UserError(_("Час другого підтвердження минув."))
        if rec.state != "awaiting_second":
            if rec.state in FINAL or RANK.get(rec.state, 0) > RANK["awaiting_second"]:
                raise UserError(_("Дія вже підтверджена."))
            raise UserError(_("Дія не очікує другого підтвердження."))
        if user.id in (rec.prepared_by.id, rec.confirmed_by.id):
            raise UserError(_("Друге підтвердження має дати інший енергетик."))
        if rec.second_expires_at and rec.second_expires_at < now:
            rec._me()._td_close("expired", "прострочено")
            raise UserError(_("Час другого підтвердження минув."))
        rec.kind_id._td_check_remote()
        me = rec._me()
        why = rec._td_write_blocked_reason()
        checks, blocked, reason = rec.kind_id.build_checks(rec.params or {})
        reason = ("Запис вимкнено: %s" % why) if why else reason
        me.write({"checks": checks})
        if why or blocked:
            me._td_close("blocked", "заблоковано", reason)
            return rec._td_response(reason=reason)
        me.write({"second_by": user.id, "second_at": now})
        me.message_post(body=_("Друге підтвердження: %s", user.name), subtype_xmlid="mail.mt_note")
        me._td_enqueue()
        return rec._td_response()

    def _td_cancel(self, token):
        """API-20 (R-40 п.11): `prepared`/`awaiting_second` → `cancelled`; повтор ідемпотентний."""
        rec = self._td_by_token(token)
        rec._td_lock()
        if rec.state == "cancelled":
            return {"action_id": rec.id, "state": "cancelled"}
        if rec.state in ("prepared", "awaiting_second"):
            rec._me()._td_close("cancelled", "скасовано")
        elif rec.state == "queued" and rec.command_id:
            rec.command_id.sudo().action_cancel()
            rec._me()._td_close("cancelled", "скасовано")
        else:
            raise UserError(_("Скасувати можна лише підготовлену або таку, що очікує, дію."))
        return {"action_id": rec.id, "state": "cancelled"}

    # --- перевірки перед виконанням --------------------------------------------------------------------------
    def _td_write_blocked_reason(self):
        """Прапори запису для `intent`/`genset`: '' або що саме вимкнено (R-40 п.6)."""
        self.ensure_one()
        env, kind = self.env, self.kind_id
        if kind.executor not in ("intent", "genset"):
            return ""
        if not tools.cparam_bool(env, "write_enabled"):
            return "td.energy_control.write_enabled"
        if kind.executor == "genset":
            return ""
        icp = env["ir.config_parameter"].sudo()
        if str(icp.get_param("td.telemetry.write_enabled", "False")).lower() not in ("true", "1"):
            return "td.telemetry.write_enabled"
        sig = env["td.signal"].sudo().search([("code", "=", "energy_control/intent")], limit=1)
        if not sig:
            return "сигнал energy_control/intent"
        if not sig.source_id.write_enabled:
            return "джерело %s" % sig.source_id.code
        if not sig.write_enabled:
            return "сигнал %s" % sig.code
        return ""

    def _td_resource_conflict(self):
        """R-40 п.9: одна дія в `queued/sent/executing` на ресурс (лише виконавець `intent`)."""
        self.ensure_one()
        if self.kind_id.executor != "intent":
            return self.browse()
        return self.sudo().search(
            [
                ("id", "!=", self.id),
                ("kind_id.executor", "=", "intent"),
                ("kind_id.resource", "=", self.kind_id.resource),
                ("state", "in", ACTIVE_RESOURCE),
            ],
            limit=1,
        )

    def _td_capture_undo(self):
        """Параметри зворотної дії (фіксуються на `confirm`)."""
        self.ensure_one()
        env, p = self.env, self.params or {}
        if self.kind_code == "air_setpoint":
            sig = env["td.signal"].sudo().search([("code", "=", kinds.SIGNALS["air_sp"])], limit=1)
            return {"setpoint_bar": round(sig.last_value, 2)} if sig and sig.last_ts else {}
        if self.kind_code == "scenario_toggle":
            sc = env["td.energy.scenario"].sudo().search([("code", "=", p.get("scenario"))], limit=1)
            return {"scenario": p.get("scenario"), "enabled": bool(sc.enabled)}
        if self.kind_code == "scenario_params":
            sc = env["td.energy.scenario"].sudo().search([("code", "=", p.get("scenario"))], limit=1)
            return {"scenario": p.get("scenario"), "params": dict(sc.params or {})}
        if self.kind_code == "shed_reorder":
            return {"order": env["td.energy.shed.item"].sudo().search([("active", "=", True)]).ids}
        return {}

    # --- сповіщення про друге підтвердження -------------------------------------------------------------------
    def _td_notify_second(self):
        self.ensure_one()
        group = self.env.ref("td_energy.group_td_energy_manager")
        users = group.sudo().all_user_ids.filtered(lambda u: u.id != self.prepared_by.id and u.active)[:10]
        deadline = (self.second_expires_at or dates.now_utc(self.env)).date()
        for user in users:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=deadline,
                summary=_("Друге підтвердження: %s", self.summary),
                user_id=user.id,
            )

    def _td_close_activities(self):
        self.sudo().activity_ids.unlink()

    # --- виконання --------------------------------------------------------------------------------------------
    def _td_payload(self):
        self.ensure_one()
        now = dates.now_utc(self.env)
        ttl = self.kind_id.valid_s or tools.cparam_int(self.env, "command_ttl_s", 120)
        user = self.second_by or self.confirmed_by or self.env.user
        return {
            "v": 1,
            "action_id": self.id,
            "idem": self.idem,
            "kind": self.kind_code,
            "cls": self.cls,
            "params": self.params or {},
            "requested_by": user.login,
            "requested_at": tools.iso(now),
            "expires_at": tools.iso(now + timedelta(seconds=ttl)),
            "tz": "Europe/Kyiv",
            "limits": {"bess_kw_max": 200},
        }

    def _td_enqueue(self):
        """R-40 п.6: за виконавцем — команда збирачу / ДГУ / конфігурація Odoo."""
        self.ensure_one()
        me = self._me()
        now = dates.now_utc(self.env)
        kind = self.kind_id
        idem = hashlib.sha1(("%d:%s" % (self.id, self.kind_code)).encode()).hexdigest()
        if kind.executor == "intent":
            why = self._td_write_blocked_reason()
            if why:
                return me._td_close("blocked", "заблоковано", "Запис вимкнено: %s" % why)
            me.write({"idem": idem})
            sig = self.env["td.signal"].sudo().search([("code", "=", "energy_control/intent")], limit=1)
            payload = me._td_payload()
            ttl = kind.valid_s or tools.cparam_int(self.env, "command_ttl_s", 120)
            cmd = (
                self.env["td.command"]
                .sudo()
                .with_context(td_energy_control_internal=True, mail_create_nolog=True)
                .create(
                    {
                        "signal_id": sig.id,
                        "value": 0,
                        "payload": payload,
                        "origin": "energy",
                        "expires_at": now + timedelta(seconds=ttl),
                        "requested_by": (self.second_by or self.confirmed_by or self.env.user).id,
                        "note": (self.summary or "")[:128],
                        "energy_action_id": self.id,
                    }
                )
            )
            me.write({"state": "queued", "started_at": now, "command_id": cmd.id})
            me._td_close_activities()
            bus.tick(self.env, "action")
        elif kind.executor == "genset":
            me.write({"idem": idem, "started_at": now})
            try:
                res = genset_link.start_test(self.env, self.confirmed_by or self.env.user)
            except UserError as e:
                return me._td_close("blocked", "заблоковано", str(e))
            ref = (res or {}).get("ref") or {}
            me.write({"ref_model": ref.get("model"), "ref_id": ref.get("id")})
            me._td_close("done", "Тест ДГУ прийнято td_genset: %s хв" % kinds.fmt((res or {}).get("minutes")))
        else:
            me.write({"started_at": now})
            me._td_apply_config()
        return True

    def _td_apply_config(self):
        """`executor='config'`: застосувати зміну в Odoo одразу; «виконано» стане, коли збирач підтвердить версію."""
        self.ensure_one()
        env, p = self.env, self.params or {}
        me = self._me()
        if self.kind_code == "scenario_toggle":
            sc = env["td.energy.scenario"].sudo().search([("code", "=", p["scenario"])], limit=1)
            version = sc._td_apply_change({"enabled": bool(p["enabled"])}, self)
            me.write({"scenario_id": sc.id})
        elif self.kind_code == "scenario_params":
            sc = env["td.energy.scenario"].sudo().search([("code", "=", p["scenario"])], limit=1)
            version = sc._td_apply_change({"params": p["params"]}, self)
            me.write({"scenario_id": sc.id})
        elif self.kind_code == "shed_reorder":
            Item = env["td.energy.shed.item"].sudo().with_context(td_energy_control_internal=True)
            for seq, item in enumerate(Item.browse(p["order"]), 1):
                item.write({"sequence": seq * 10})
            version = env["td.energy.control.state"].bump()
            bus.tick(env, "shed")
        else:  # pragma: no cover
            raise UserError(_("Невідомий вид конфігурації %s.", self.kind_code))
        me.write({"config_version": version})
        me._td_close("done", "збережено, очікує збирач")

    # --- завершення ---------------------------------------------------------------------------------------------
    def _td_close(self, state, result_text=None, error=None):
        """Єдина точка завершення: `finished_at`, чат, шина, `advice.action_done`, закриття activity, події."""
        for rec in self:
            now = dates.now_utc(self.env)
            rec.write(
                {
                    "state": state,
                    "finished_at": now,
                    "result_text": (result_text or "")[:96] or False,
                    "error": (error or "")[:256] or False,
                }
            )
            rec._td_close_activities()
            rec.message_post(
                body=_("Результат: %(state)s — %(text)s", state=rec._td_state_label(), text=error or result_text or ""),
                subtype_xmlid="mail.mt_note",
            )
            bus.tick(self.env, "action")
            if rec.kind_id.resource in ("qs", "bess", "chp"):
                energy_bus.tick(self.env, "state")
            if state == "done":
                if rec.undo_of_id:
                    rec.undo_of_id.write({"undone_by_id": rec.id})
                if rec.advice_id:
                    rec.advice_id._td_on_action_done(rec)
            if (
                (state == "failed")
                or (state == "expired" and rec.started_at)
                or (state == "blocked" and rec.origin == "auto")
            ):
                self.env["td.energy.event"]._td_log(
                    "warn",
                    "control",
                    ("ACT-%s" % rec.name)[:32],
                    "Керування: %s — %s" % (rec.summary, error or result_text or rec._td_state_label()),
                    dedup_min=1,
                )
        return True

    # --- хуки від td.command (M-37) і сборщика (API-25) ----------------------------------------------------------
    def _td_on_command(self, cmd):
        """R-40 п.7: стан транспорту команди → стан дії (лише «вперед»; `expired` не відновлюється тут)."""
        for rec in self.sudo():
            if rec.state not in ACTIVE_RESOURCE:
                continue
            me = rec._me()
            data = cmd.result_data if isinstance(cmd.result_data, dict) else {}
            if cmd.state == "sent" and rec.state == "queued":
                me.write({"state": "sent"})
                bus.tick(self.env, "action")
            elif cmd.state == "done":
                if data.get("accepted") is False:
                    reason = data.get("reason") or "відмовлено збирачем"
                    if data.get("state") == "rejected":
                        me._td_close("failed", "не виконано", reason)
                    else:
                        me._td_close("blocked", "заблоковано", reason)
                else:
                    if data.get("checks"):
                        me.write({"collector_checks": data["checks"]})
                    me.write({"state": "executing"})
                    bus.tick(self.env, "action")
            elif cmd.state == "failed":
                me._td_close("failed", "не виконано", cmd.error or "помилка транспорту")
            elif cmd.state == "expired":
                me._td_close("expired", "прострочено")
            elif cmd.state == "cancelled":
                me._td_close("cancelled", "скасовано")

    @api.model
    def _td_on_engine(self, item):
        """API-25 `actions[]`: True — застосовано; None — повтор без ефекту; рядок — причина відмови."""
        if not isinstance(item, dict):
            return "bad_state"
        rec = self.sudo().browse(int(item["id"])).exists() if str(item.get("id", "")).isdigit() else self.browse()
        if not rec or (item.get("idem") and rec.idem and rec.idem != item["idem"]):
            return "unknown_action"
        new = item.get("state")
        if new not in ("executing", "done", "failed", "blocked"):
            return "bad_state"
        me = rec._me()
        cur = rec.state
        if cur == new and new in FINAL:
            return None
        if cur in ("done", "failed", "blocked", "cancelled"):
            return "already_final"
        if cur == "expired" and not (item.get("idem") and item["idem"] == rec.idem):
            return "already_final"
        if cur in ("prepared", "awaiting_second"):
            return "bad_state"
        vals = {"step": int(item.get("step") or 0), "steps_total": int(item.get("steps_total") or 0)}
        if item.get("checks"):
            vals["collector_checks"] = item["checks"]
        if new == "executing":
            if cur == "executing":
                me.write(vals)
                return None
            me.write(dict(vals, state="executing"))
            bus.tick(self.env, "action")
            return True
        me.write(vals)
        if new == "done":
            me._td_close("done", item.get("result") or "виконано")
        elif new == "failed":
            me._td_close("failed", "не виконано", item.get("error") or item.get("result") or "помилка виконання")
        else:
            me._td_close("blocked", "заблоковано", item.get("error") or item.get("result") or "заблоковано збирачем")
        return True

    @api.model
    def _td_log_auto(self, ev):
        """API-25 `events[]` → запис журналу `origin='auto'` (+ подія `control` для інтерлоків/збоїв)."""
        if not isinstance(ev, dict) or not ev.get("event_id") or not ev.get("text"):
            return "bad_state"
        event_id = str(ev["event_id"])[:40]
        if self.sudo().search_count([("idem", "=", event_id)]):
            return "duplicate"
        scenario = ev.get("scenario") or "peak"
        kind = str(ev.get("kind") or "auto_step")
        code = ("auto_%s_%s" % (scenario, kind))[:48]
        text = str(ev["text"])[:256]
        now = dates.now_utc(self.env)
        if self.sudo().search_count(
            [
                ("origin", "=", "auto"),
                ("kind_code", "=", code),
                ("detail", "=", text),
                ("create_date", ">=", fields.Datetime.now() - timedelta(seconds=60)),
            ]
        ):
            return None
        sc = self.env["td.energy.scenario"].sudo().search([("code", "=", scenario)], limit=1)
        actor = "сценарій «%s»" % kinds.SCENARIO_SHORT.get(scenario, scenario)
        rec = (
            self.sudo()
            .with_context(td_energy_control_internal=True, tracking_disable=True, mail_create_nolog=True)
            .create(
                {
                    "kind_code": code,
                    "origin": "auto",
                    "state": "done",
                    "idem": event_id,
                    "summary": self._td_auto_summary(ev)[:128],
                    "detail": text,
                    "actor_text": actor[:96],
                    "result_text": str(ev.get("result") or "виконано")[:96],
                    "scenario_id": sc.id,
                    "started_at": now,
                    "finished_at": now,
                }
            )
        )
        if kind in ("interlock", "failsafe", "mode", "config", "hold", "override"):
            self.env["td.energy.event"]._td_log(
                "warn", "control", ("%s-%s" % (scenario, kind))[:32], text, dedup_min=60
            )
        bus.tick(self.env, "action")
        return True if rec else None

    @api.model
    def _td_auto_summary(self, ev):
        sig, val, kind = ev.get("signal") or "", ev.get("value"), ev.get("kind") or ""
        if sig.endswith("bess/mode"):
            return "BESS · %s" % {1: "заряд", 2: "розряд"}.get(int(val or 0), "зупинка")
        if sig.endswith("chp/cmd"):
            return "КГУ · %s" % ("пуск" if int(val or 0) == 1 else "зупинка")
        if "/shed/" in sig:
            node = sig.split("/shed/")[1].split("/")[0]
            return "Скидання · %s" % node
        if ev.get("scenario") == "night":
            return "Вентиляція · %s режим" % ("нічний" if kind != "auto_release" else "денний")
        return "Автоматика · %s" % kind

    # --- журнал конфігурації (shed_edit, schedule_edit, interlock_param, switch_flag) ----------------------------
    @api.model
    def _td_log_config(self, kind_code, summary, detail=None, user=None):
        """Запис `origin='config'` класу B (змінює chief/адміністратор), `state='done'`; публікує `bump()`."""
        user = user or self.env.user
        now = dates.now_utc(self.env)
        rec = (
            self.sudo()
            .with_context(td_energy_control_internal=True, tracking_disable=True, mail_create_nolog=True)
            .create(
                {
                    "kind_code": kind_code,
                    "origin": "config",
                    "cls": "B",
                    "state": "done",
                    "summary": summary[:128],
                    "detail": (detail or "")[:256],
                    "actor_text": user.name[:96],
                    "result_text": "збережено, очікує збирач",
                    "prepared_by": user.id,
                    "confirmed_by": user.id,
                    "prepared_at": now,
                    "confirmed_at": now,
                    "started_at": now,
                    "finished_at": now,
                    "config_version": self.env["td.energy.control.state"].bump(),
                }
            )
        )
        bus.tick(self.env, "action")
        return rec

    # --- крон завершення прострочених (разд. 6) -----------------------------------------------------------------
    @api.model
    def _cron_expire(self):
        try:
            with self.env.cr.savepoint():
                return self._td_expire()
        except Exception:
            _logger.exception("td_energy_control: крон завершення прострочених")
        return 0

    @api.model
    def _td_expire(self):
        env = self.env
        now = dates.now_utc(env)
        Action = self.sudo().with_context(td_energy_control_internal=True)
        n = 0
        for rec in Action.search([("state", "=", "prepared"), ("token_expires_at", "<", now)]):
            rec._td_close("expired", "прострочено")
            n += 1
        for rec in Action.search([("state", "=", "awaiting_second"), ("second_expires_at", "<", now)]):
            rec._td_close("expired", "прострочено")
            n += 1
        for rec in Action.search([("state", "in", ("queued", "sent")), ("command_id.expires_at", "<", now)]):
            if rec.command_id.state in ("queued", "sent"):
                rec.command_id.sudo().write({"state": "expired"})
            if rec.state in ("queued", "sent"):
                rec._td_close("expired", "прострочено")
            n += 1
        limit = tools.cparam_int(env, "exec_timeout_s", 60) + 30
        for rec in Action.search([("state", "=", "executing"), ("started_at", "<", now - timedelta(seconds=limit))]):
            rec._td_close(
                "failed", "не виконано", "Немає підтвердження виконання від збирача: перевірте пристрій вручну"
            )
            n += 1
        apply_s = tools.cparam_int(env, "apply_timeout_s", 60)
        state = env["td.energy.control.state"].get()
        for rec in Action.search(
            [
                ("kind_id.executor", "=", "config"),
                ("state", "=", "done"),
                ("finished_at", "<", now - timedelta(seconds=apply_s)),
                ("origin", "!=", "auto"),
            ]
        ).filtered(lambda r: r.config_version and r.config_version > state.applied_version):
            env["td.energy.event"]._td_log(
                "warn",
                "control",
                "CONFIG-NOT-APPLIED",
                "Збирач не застосував конфігурацію v%d" % rec.config_version,
                dedup_min=24 * 60,
            )
        return n

    # --- публічний рядок журналу (API-28, 7.6) --------------------------------------------------------------------
    def _td_journal_row(self, now=None):
        self.ensure_one()
        chip, kind = self._td_result_chip()
        when = self.finished_at or self.started_at or self.confirmed_at or self.prepared_at or self.create_date
        ref = {"model": self.ref_model, "id": self.ref_id} if self.ref_model and self.ref_id else None
        return {
            "id": self.id,
            "time": tools.local_hhmm(when, now),
            "what": self.summary or self.kind_code or "",
            "detail": self.detail or "",
            "who": self.actor_text or "",
            "result": chip,
            "result_kind": kind,
            "state": self.state,
            "undo_available": bool(self.undo_available),
            "awaiting_second": self.state == "awaiting_second",
            "ref": ref,
        }

    def _td_get_dict(self):
        """API-22."""
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "state": self.state,
            "state_label": self._td_state_label(),
            "summary": self.summary or "",
            "detail": self.detail or "",
            "result_text": self.result_text or None,
            "error": self.error or None,
            "finished_at": tools.iso(self.finished_at),
            "needs_second": bool(self.state == "awaiting_second"),
            "checks": self.checks or [],
            "collector_checks": self.collector_checks or [],
            "undo_available": bool(self.undo_available),
        }
