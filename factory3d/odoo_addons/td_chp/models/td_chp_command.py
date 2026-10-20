"""M-03 `td.chp.command` — команда КГУ (D-05): потік prepare → confirm → [confirm_second] → виконання (R-08, R-09).

Мінімальний полесумісний еквівалент `td.energy.action` (імена полів, ключі `state`, TTL, правила токена й 2/2).
Запис — лише `sudo()` у методах моделі; права на дії перевіряє `td.chp.pult` (operator), а `confirm_second` — тут.
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from odoo import _, api, fields, models, tools as odoo_tools
from odoo.exceptions import AccessError, UserError

from odoo.addons.td_telemetry.tools.ingest import parse_ts

from ..tools import alarms, bus, interlocks
from ..tools import command_flow as flow
from ..tools.signals import Snapshot, cparam_bool, cparam_int, iso, now, write_off_reason

G_OPERATOR = "td_chp.group_td_chp_operator"
G_CHIEF = "td_chp.group_td_chp_chief"
TOKEN_NOT_FOUND = "Підтвердження не знайдено. Відкрийте діалог знову."
WRITE_OFF = "Керування вимкнено: td.chp.write_enabled. Зверніться до адміністратора."
RSW_OFF = "Керування вимкнено: td.chp.remote_switching_enabled. Зверніться до адміністратора."


def _hash(token):
    return hashlib.sha256((token or "").encode()).hexdigest()


class TdChpCommand(models.Model):
    _name = "td.chp.command"
    _description = "КГУ: команда"
    _order = "create_date desc, id desc"

    _td_second_distinct = models.Constraint(
        "CHECK(second_by IS NULL OR (second_by IS DISTINCT FROM prepared_by "
        "AND second_by IS DISTINCT FROM confirmed_by))",
        "Друге підтвердження має дати інший користувач.",
    )

    name = fields.Char(string="Номер", readonly=True, copy=False)
    unit_id = fields.Many2one("td.chp.unit", string="Агрегат", required=True, index=True, ondelete="cascade")
    kind_code = fields.Selection(
        [(k, v["label"]) for k, v in flow.KINDS.items()], string="Вид команди", required=True, index=True
    )
    origin = fields.Selection([("manual", "Вручну")], string="Джерело", default="manual")
    cls = fields.Selection([("A", "A"), ("B", "B")], string="Клас")
    state = fields.Selection(flow.STATES, string="Стан", default="prepared", index=True)
    params = fields.Json(string="Параметри")
    checks = fields.Json(string="Перевірки")
    token_hash = fields.Char(size=64, index=True, copy=False)
    token_expires_at = fields.Datetime(string="Токен діє до")
    needs_second = fields.Boolean(string="Потрібне друге підтвердження")
    prepared_by = fields.Many2one("res.users", string="Підготував", readonly=True, ondelete="set null")
    confirmed_by = fields.Many2one("res.users", string="Підтвердив (1/2)", readonly=True, ondelete="set null")
    second_by = fields.Many2one("res.users", string="Підтвердив (2/2)", readonly=True, ondelete="set null")
    prepared_at = fields.Datetime(string="Підготовлено", readonly=True)
    confirmed_at = fields.Datetime(string="Підтверджено", readonly=True)
    second_at = fields.Datetime(string="Друге підтвердження о", readonly=True)
    second_expires_at = fields.Datetime(string="Друге підтвердження до", readonly=True)
    started_at = fields.Datetime(string="Розпочато", readonly=True)
    finished_at = fields.Datetime(string="Завершено", readonly=True)
    command_id = fields.Many2one("td.command", string="Команда телеметрії", ondelete="set null", readonly=True)
    expect = fields.Json(string="Очікування верифікації")
    idem = fields.Char(size=40)
    params_text = fields.Char(string="Параметри (текст)", compute="_compute_texts")
    checks_text = fields.Text(string="Перевірки (текст)", compute="_compute_texts")
    summary = fields.Char(string="Дія", size=128)
    detail = fields.Char(string="Деталі", size=256)
    result_text = fields.Char(string="Результат", size=96)
    error = fields.Char(string="Помилка", size=256)

    @api.depends("params", "checks")
    def _compute_texts(self):
        marks = {"ok": "✓", "fail": "✗", "unknown": "?"}
        for rec in self:
            rec.params_text = ", ".join(f"{k}={v}" for k, v in (rec.params or {}).items())
            rec.checks_text = "\n".join(
                f"{marks.get(c.get('state'), '?')} {c.get('label')}" + (f" — {c['detail']}" if c.get("detail") else "")
                for c in (rec.checks or [])
            )

    def init(self):
        cr = self.env.cr
        cr.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS td_chp_command_idem_uniq ON td_chp_command (idem) WHERE idem IS NOT NULL"
        )
        odoo_tools.sql.create_index(cr, "td_chp_command_state_created_idx", self._table, ["state", "create_date"])

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            vals.setdefault("name", seq.next_by_code("td.chp.command") or "CHP")
        return super().create(vals_list)

    def unlink(self):
        if not self.env.su and not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError(_("Журнал команд КГУ не видаляється."))
        return super().unlink()

    # --- допоміжні ----------------------------------------------------------------------------------------------
    @property
    def _td_ref(self):
        return f"chp:{self.id}"

    def _td_state_label(self):
        return flow.STATE_LABELS.get(self.state, self.state)

    def _td_lock(self):
        self.env.cr.execute("SELECT id FROM td_chp_command WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset()

    def _td_response(self, message=None, reason=None):
        self.ensure_one()
        return {
            "ref": self._td_ref,
            "state": self.state,
            "state_label": self._td_state_label(),
            "needs_second": bool(self.needs_second and self.state == "awaiting_second"),
            "message": message,
            "blocked_reason": reason or (self.error if self.state == "blocked" else None),
        }

    def _td_get_dict(self):
        """API-05 `get`."""
        self.ensure_one()
        return {
            "ref": self._td_ref,
            "state": self.state,
            "state_label": self._td_state_label(),
            "summary": self.summary,
            "result_text": self.result_text,
            "error": self.error,
            "finished_at": iso(self.finished_at),
            "needs_second": bool(self.needs_second and self.state == "awaiting_second"),
            "checks": self.checks or [],
        }

    @api.model
    def _td_by_token(self, token):
        h = _hash(token)
        rec = self.sudo().search([("token_hash", "=", h)], limit=1)
        if not rec or not hmac.compare_digest(rec.token_hash or "", h):
            raise UserError(_(TOKEN_NOT_FOUND))
        if rec.prepared_by != self.env.user:
            raise AccessError(_("Токен належить іншому користувачу."))
        return rec

    # --- prepare ------------------------------------------------------------------------------------------------
    @api.model
    def _td_prepare(self, unit, kind, params):
        """Створити `prepared` + токен (або одразу `blocked`). → `(запис, токен|None, тексти, blocked, reason)`."""
        env, user = self.env, self.env.user
        info = flow.kind_info(kind)
        if not cparam_bool(env, "write_enabled"):
            raise UserError(_(WRITE_OFF))
        if kind == "start" and not unit._td_remote_switching():
            raise UserError(_(RSW_OFF))
        params = flow.normalize(kind, params)
        t = now(env)
        rendered = flow.render(kind, params, unit)
        checks = interlocks.build_checks(unit, kind, Snapshot(env, t))
        blocked, reason = self._td_gate(interlocks.verdict(checks, kind), kind)
        Command = self.sudo().with_context(td_chp_internal=True)
        base = {
            "unit_id": unit.id,
            "kind_code": kind,
            "origin": "manual",
            "cls": info["cls"],
            "params": params,
            "checks": checks,
            "prepared_by": user.id,
            "prepared_at": t,
            "summary": rendered["label"][:128],
            "detail": (rendered["text"] or "")[:256],
        }
        if blocked:
            rec = Command.create({**base, "state": "blocked", "finished_at": t, "error": reason[:256]})
            bus.tick(env, "command")
            bus.tick(env, "journal")
            return rec, None, rendered, True, reason
        token = secrets.token_urlsafe(24)
        needs_second = info["cls"] == "B" and not user.has_group(G_CHIEF)
        vals = {
            "token_hash": _hash(token),
            "token_expires_at": t + timedelta(seconds=cparam_int(env, "confirm_ttl_s")),
            "checks": checks,
            "needs_second": needs_second,
        }
        same = self.sudo().search(
            [
                ("unit_id", "=", unit.id),
                ("prepared_by", "=", user.id),
                ("kind_code", "=", kind),
                ("state", "=", "prepared"),
                ("prepared_at", ">=", t - timedelta(seconds=5)),
            ]
        )
        same = same.filtered(lambda r: (r.params or {}) == params)[:1]
        if same:
            same.write(vals)
            rec = same
        else:
            rec = Command.create({**base, **vals, "state": "prepared"})
        return rec, token, rendered, False, None

    # --- confirm ------------------------------------------------------------------------------------------------
    @api.model
    def _td_gate(self, verdict, kind):
        """Додає до вердикту переліку засув запису: `td.telemetry.write_enabled`, джерело, сигнал цілі (R-07)."""
        blocked, reason = verdict
        why = write_off_reason(self.env, flow.KINDS[kind]["signal"])
        if why:
            blocked, reason = True, "; ".join(filter(None, [reason, f"Запис вимкнено: {why}"]))
        return blocked, reason

    def _td_recheck(self):
        """Повторні перевірки перед виконанням (R-08 п. 3): → `(blocked, reason)`; побічно оновлює `checks`."""
        self.ensure_one()
        env, kind = self.env, self.kind_code
        checks = interlocks.build_checks(self.unit_id, kind, Snapshot(env))
        if not cparam_bool(env, "write_enabled"):
            verdict = (True, "Запис вимкнено: td.chp.write_enabled")
        else:
            verdict = interlocks.verdict(checks, kind)
        blocked, reason = self._td_gate(verdict, kind)
        self.sudo().write({"checks": checks})
        return blocked, reason

    def _td_confirm(self, token):
        """API-05 `confirm`: токен → `awaiting_second` / `queued` / `blocked`; повтор — поточний стан."""
        rec = self._td_by_token(token)
        rec._td_lock()
        t = now(self.env)
        if rec.state in ("cancelled", "expired"):
            raise UserError(_(TOKEN_NOT_FOUND))
        if rec.state != "prepared":
            return rec._td_response(_("Уже надіслано"))
        if rec.token_expires_at and rec.token_expires_at < t:
            raise UserError(_("Час підтвердження минув. Відкрийте діалог знову."))
        blocked, reason = rec._td_recheck()
        if blocked:
            rec._td_close("blocked", "заблоковано", reason)
            return rec._td_response(reason=reason)
        rec = rec.sudo()
        rec.write({"confirmed_by": self.env.uid, "confirmed_at": t})
        if rec.needs_second and not self.env.user.has_group(G_CHIEF):
            rec.write(
                {
                    "state": "awaiting_second",
                    "second_expires_at": t + timedelta(seconds=cparam_int(self.env, "second_ttl_s")),
                }
            )
            bus.tick(self.env, "command")
            bus.tick(self.env, "journal")
            return rec._td_response(_("Очікуємо друге підтвердження іншим користувачем."))
        rec.write({"needs_second": False})
        rec._td_enqueue()
        return rec._td_response()

    def _td_confirm_second(self):
        """API-05 `confirm_second`: друге підтвердження іншою особою (operator/chief)."""
        self.ensure_one()
        user = self.env.user
        if not user.has_group(G_OPERATOR):
            raise AccessError(_("Підтверджувати команди КГУ може лише енергетик."))
        self._td_lock()
        rec = self.sudo()
        t = now(self.env)
        if rec.state == "expired":
            raise UserError(_("Час другого підтвердження минув."))
        if rec.state != "awaiting_second":
            if rec.state in flow.FINAL or flow.RANK.get(rec.state, 0) > flow.RANK["awaiting_second"]:
                raise UserError(_("Команда вже підтверджена."))
            raise UserError(_("Команда не очікує другого підтвердження."))
        if user.id in (rec.prepared_by.id, rec.confirmed_by.id):
            raise UserError(_("Друге підтвердження має дати інший користувач."))
        if rec.second_expires_at and rec.second_expires_at < t:
            raise UserError(_("Час другого підтвердження минув."))
        blocked, reason = rec._td_recheck()
        if blocked:
            rec._td_close("blocked", "заблоковано", reason)
            return rec._td_response(reason=reason)
        rec.write({"second_by": user.id, "second_at": t})
        rec._td_enqueue()
        return rec._td_response()

    def _td_cancel(self, token):
        """API-05 `cancel`: `prepared/awaiting_second` → `cancelled`; повтор ідемпотентний."""
        rec = self._td_by_token(token)
        rec._td_lock()
        rec._td_cancel_record()
        return {"ref": rec._td_ref, "state": "cancelled", "state_label": flow.STATE_LABELS["cancelled"]}

    def _td_cancel_record(self):
        self.ensure_one()
        rec = self.sudo()
        if rec.state == "cancelled":
            return True
        if rec.state in ("prepared", "awaiting_second"):
            rec._td_close("cancelled", "скасовано")
        elif rec.state == "queued" and rec.command_id:
            rec.command_id.sudo().action_cancel()  # хук td.command закриває команду як `cancelled`
            if rec.state != "cancelled":
                rec._td_close("cancelled", "скасовано")
        else:
            raise UserError(_("Скасувати можна лише підготовлену команду або таку, що очікує підтвердження."))
        return True

    # --- виконання ----------------------------------------------------------------------------------------------
    def _td_enqueue(self):
        """R-08 п. 4: одна активна команда на агрегат → `td.command` (`origin='chp'`) і стан `queued`."""
        self.ensure_one()
        env, rec = self.env, self.sudo()
        info = flow.KINDS[rec.kind_code]
        t = now(env)
        sig_code = "chp/" + info["signal"]
        if rec.kind_code == "estop":  # аварійний стоп завжди дозволено: скасовує інші `queued`
            for other in self.sudo().search(
                [("unit_id", "=", rec.unit_id.id), ("id", "!=", rec.id), ("state", "=", "queued")]
            ):
                other._td_cancel_record()
            busy = self.browse()
        else:
            busy = self.sudo().search(
                [("unit_id", "=", rec.unit_id.id), ("id", "!=", rec.id), ("state", "in", flow.ACTIVE)], limit=1
            )
        if busy:
            return rec._td_close("blocked", "заблоковано", _("Уже виконується команда %s", busy.name))
        why = write_off_reason(env, info["signal"])
        if why:
            return rec._td_close("blocked", "заблоковано", _("Запис вимкнено: %s", why))
        sig = env["td.signal"].sudo().search([("code", "=", sig_code)], limit=1)
        params = rec.params or {}
        value = flow.target_value(rec.kind_code, params)
        ttl = cparam_int(env, "command_ttl_s")
        cmd = (
            env["td.command"]
            .sudo()
            .with_context(td_chp_internal=True, mail_create_nolog=True)
            .create(
                {
                    "signal_id": sig.id,
                    "value": value,
                    "origin": "chp",
                    "requested_by": (rec.confirmed_by or env.user).id,
                    "expires_at": t + timedelta(seconds=ttl),
                    "note": (rec.summary or "")[:128],
                }
            )
        )
        if rec.kind_code in ("start", "stop", "estop", "reset"):
            expect = {"signal": "chp/ctl/ack", "kind": "ack"}
        else:
            scale = (sig.address or {}).get("scale") or 1.0
            expect = {"signal": sig_code, "kind": "value", "value": value, "tol": 0.5 * abs(scale)}
        rec.write(
            {
                "state": "queued",
                "started_at": t,
                "command_id": cmd.id,
                "expect": expect,
                "idem": hashlib.sha1(f"{rec.id}:{rec.kind_code}".encode()).hexdigest(),
            }
        )
        bus.tick(env, "command")
        bus.tick(env, "journal")
        return True

    def _td_close(self, state, result_text=None, error=None):
        """Єдина точка завершення: стан, `finished_at`, шина."""
        for rec in self.sudo():
            rec.write(
                {
                    "state": state,
                    "finished_at": now(self.env),
                    "result_text": (result_text or "")[:96] or False,
                    "error": (error or "")[:256] or False,
                }
            )
            bus.tick(self.env, "command")
            bus.tick(self.env, "journal")
        return True

    # --- хуки td.command (R-08 п. 5) і показання (R-09) -----------------------------------------------------------
    @api.model
    def _td_on_command(self, cmds):
        """Стан транспорту `td.command` → стан команди (лише «вперед»)."""
        if self.env.context.get("td_chp_skip_hook"):
            return
        for rec in self.sudo().search([("command_id", "in", cmds.ids), ("state", "in", flow.ACTIVE)]):
            cmd = rec.command_id
            if cmd.state == "sent" and rec.state == "queued":
                rec.write({"state": "sent"})
                bus.tick(self.env, "command")
            elif cmd.state == "done" and flow.RANK[rec.state] < flow.RANK["executing"]:
                rec.write({"state": "executing"})
                bus.tick(self.env, "command")
            elif cmd.state in ("failed", "expired", "cancelled"):
                rec._td_close(cmd.state, flow.STATE_LABELS[cmd.state].lower(), cmd.error or cmd.result)

    @api.model
    def _td_on_ingest(self, before, readings):
        """R-09: `start/stop/estop/reset` — `chp/ctl/ack` (1 → done, 2 → failed); `set_*` — цільовий сигнал."""
        by_code = {}
        for r in readings or ():
            if not isinstance(r, dict) or not str(r.get("code", "")).startswith("chp/") or r.get("value") is None:
                continue
            ts, reason = parse_ts(r.get("ts"))
            if not reason:
                by_code.setdefault(r["code"], []).append((ts, float(r["value"])))
        if not by_code:
            return
        for rec in self.sudo().search([("state", "=", "executing")]):
            expect, done_at = rec.expect or {}, rec.command_id.done_at
            if not expect or not done_at:
                continue
            for ts, value in sorted(by_code.get(expect.get("signal"), [])):
                if ts < done_at:
                    continue
                if expect["kind"] == "ack":
                    if int(round(value)) == 1:
                        rec._td_close("done", "Контролер прийняв команду")
                    elif int(round(value)) == 2:
                        reason_code = rec.unit_id._td_value("ctl/ack_reason")
                        why = alarms.ACK_REASONS.get(int(reason_code or 0), "причина не вказана")
                        rec._td_close("failed", "Контролер відхилив команду", f"Контролер відхилив команду: {why}")
                elif abs(value - expect["value"]) <= expect["tol"] + 1e-9:
                    rec._td_close("done", "Значення прийнято контролером")
                if rec.state not in flow.ACTIVE:
                    break

    @api.model
    def _cron_expire(self):
        """`prepared`/`awaiting_second` після строку → `expired`; активні без підтвердження за N с → `failed`."""
        if not cparam_bool(self.env, "read_enabled"):
            return 0
        t = now(self.env)
        n = 0
        for rec in self.sudo().search([("state", "=", "prepared"), ("token_expires_at", "<", t)]):
            rec._td_close("expired", "прострочено")
            n += 1
        for rec in self.sudo().search([("state", "=", "awaiting_second"), ("second_expires_at", "<", t)]):
            rec._td_close("expired", "прострочено")
            n += 1
        timeout = cparam_int(self.env, "verify_timeout_s")
        for rec in self.sudo().search([("state", "in", flow.ACTIVE), ("started_at", "!=", False)]):
            if rec.started_at + timedelta(seconds=timeout) < t:
                cmd = rec.command_id
                if cmd and cmd.state == "queued":
                    cmd.sudo().with_context(td_chp_skip_hook=True).action_cancel()
                rec._td_close("failed", "не підтверджено", _("Контролер не підтвердив команду за %s с", timeout))
                n += 1
        return n

    # --- журнал і картка «Очікує другого підтвердження» ------------------------------------------------------------
    def _td_journal_row(self):
        """Рядок API-03 для команди (R-12)."""
        self.ensure_one()
        label = flow.KINDS[self.kind_code]["label"]
        return {
            "type": "command",
            "id": self.id,
            "ref": self._td_ref,
            "ts": iso(self.finished_at or self.prepared_at),
            "level": "warn" if self.state in ("failed", "blocked", "expired") else "info",
            "text": flow.journal_text(label, self.state, self.prepared_by.name, self.second_by.name),
            "ack_state": None,
            "state": self.state,
        }

    @api.model
    def _td_journal_rows(self, unit, limit, before):
        """Рядки-команди для API-03: без `prepared/cancelled`, `ts desc, id desc`, лише з `ts < before`."""
        rows = self.sudo().search(
            [("unit_id", "=", unit.id), ("state", "in", flow.JOURNAL_STATES)], order="id desc", limit=limit * 3 + 50
        )
        out = [r._td_journal_row() for r in rows]
        if before:
            cut = iso(before)
            out = [r for r in out if r["ts"] < cut]
        out.sort(key=lambda r: (r["ts"], r["id"]), reverse=True)
        return out[:limit]

    @api.model
    def _td_pending_rows(self, unit):
        """Команди в `awaiting_second` для `pending` у `get_state`."""
        user = self.env.user
        can_role = user.has_group(G_OPERATOR)
        rows = []
        for rec in self.sudo().search([("unit_id", "=", unit.id), ("state", "=", "awaiting_second")]):
            info = flow.KINDS[rec.kind_code]
            rows.append(
                {
                    "ref": rec._td_ref,
                    "kind": rec.kind_code,
                    "title": f"{info['label']} {flow.short_name(unit)}",
                    "prepared_by": rec.prepared_by.name,
                    "can_second": bool(can_role and user.id not in (rec.prepared_by.id, rec.confirmed_by.id)),
                    "second_expires_at": iso(rec.second_expires_at),
                }
            )
        return rows
