"""M-03 td.yard.gate: КПП / шлагбаум (SPEC R-15…R-17)."""

import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import params as P
from ..tools import tz
from .td_yard_visit import GRP_SEC, _f3d_yard_require

_logger = logging.getLogger(__name__)

KINDS = ("open", "close", "hold", "release")
KIND_LABELS = {"open": "Відкрити", "close": "Закрити", "hold": "Тримати відкритим", "release": "Зняти утримання"}
KIND_SIGNAL = {
    "open": "cmd_open_signal_id",
    "close": "cmd_close_signal_id",
    "hold": "cmd_hold_signal_id",
    "release": "cmd_hold_signal_id",
}
AUTO_REASONS = ("auto_booking", "auto_exit", "auto_hold_max")
CMD_STATE_LABELS = {
    "queued": "у черзі",
    "sent": "передано колектору",
    "done": "виконано",
    "failed": "помилка",
    "expired": "прострочено",
    "cancelled": "скасовано",
}


def _fresh(sig, now, max_age_s):
    """Сигнал є, має статус не stale/unknown й оновлений не раніше now − max_age_s."""
    return bool(
        sig
        and sig.status not in ("stale", "unknown")
        and sig.last_ts
        and sig.last_ts >= now - timedelta(seconds=max_age_s)
    )


class F3dYardGate(models.Model):
    _name = "td.yard.gate"
    _inherit = ["td.scene.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Двір: КПП і шлагбаум"
    _order = "sequence, td_code"
    _rec_name = "name"
    _rec_names_search = ["name", "td_code", "camera_code"]
    _f3d_kind = "other"
    STATES = [
        ("closed", "Закритий"),
        ("open", "Відкритий"),
        ("held", "Утримується відкритим"),
        ("error", "Помилка"),
        ("unknown", "Невідомо"),
    ]

    td_code = fields.Char(required=True)
    name = fields.Char(string="Назва", size=64, required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    direction = fields.Selection(
        [("in", "В'їзд"), ("out", "Виїзд"), ("both", "В'їзд і виїзд")], string="Напрямок", required=True
    )
    side = fields.Selection([("west", "Захід"), ("east", "Схід")], string="Сторона", required=True)
    pos_x = fields.Float(string="X, м", digits=(8, 2))
    pos_y = fields.Float(string="Y, м", digits=(8, 2))
    equipment_id = fields.Many2one("maintenance.equipment", string="Обладнання", ondelete="set null")
    zone_id = fields.Many2one("td.zone", string="Зона", ondelete="set null")
    camera_code = fields.Char(string="Камера LPR", size=32, index=True, help="sensorProviderID камери Axis (CAM-05)")
    camera_equipment_id = fields.Many2one("maintenance.equipment", string="Обладнання камери", ondelete="set null")
    source_id = fields.Many2one("td.source", string="Модуль I/O", ondelete="set null")
    state_signal_id = fields.Many2one("td.signal", string="Сигнал: стріла відкрита", ondelete="set null")
    loop_signal_id = fields.Many2one("td.signal", string="Сигнал: петля", ondelete="set null")
    photocell_signal_id = fields.Many2one("td.signal", string="Сигнал: фотоелемент", ondelete="set null")
    passes_signal_id = fields.Many2one("td.signal", string="Сигнал: лічильник проїздів", ondelete="set null")
    cmd_open_signal_id = fields.Many2one("td.signal", string="Команда: відкрити", ondelete="set null")
    cmd_close_signal_id = fields.Many2one("td.signal", string="Команда: закрити", ondelete="set null")
    cmd_hold_signal_id = fields.Many2one("td.signal", string="Команда: тримати", ondelete="set null")
    invert_di = fields.Boolean(
        string="Інверсія входів", default=False, help="Контакти NC: 0 = активний стан (ризик монтажу ARCH §5.3)"
    )
    mode = fields.Selection(
        [("auto", "Авто"), ("manual", "Ручний")], string="Режим", required=True, default="manual", tracking=True
    )
    state = fields.Selection(STATES, string="Стан", required=True, default="unknown", readonly=True, index=True)
    state_since = fields.Datetime(readonly=True)
    last_error = fields.Char(string="Помилка", size=256, readonly=True)
    responsible_id = fields.Many2one(
        "res.users", string="Відповідальний (охорона)", help="Кому ставиться активність при помилці воріт"
    )
    loop_occupied = fields.Boolean(readonly=True)
    photocell_blocked = fields.Boolean(readonly=True)
    counter_value = fields.Integer(readonly=True)
    passes_day_start = fields.Integer(readonly=True)
    passes_today = fields.Integer(string="Проїздів сьогодні", readonly=True)
    admitted_today = fields.Integer(string="Дозволів сьогодні", readonly=True)
    tailgate_today = fields.Integer(string="Проїздів без дозволу", readonly=True)
    last_tailgate_at = fields.Datetime(readonly=True)
    last_plate = fields.Char(string="Останній номер", size=16, readonly=True, groups=GRP_SEC)
    last_plate_at = fields.Datetime(readonly=True)
    pending_visit_id = fields.Many2one("td.yard.visit", string="Очікує проїзду", readonly=True, ondelete="set null")
    open_cmd_id = fields.Many2one("td.command", readonly=True, ondelete="set null")
    opened_at = fields.Datetime(readonly=True)
    hold_until = fields.Datetime(string="Утримання до", readonly=True)
    last_command_id = fields.Many2one("td.command", readonly=True, ondelete="set null")
    command_ids = fields.One2many("td.command", "td_yard_gate_id", string="Команди")
    can_command = fields.Boolean(compute="_compute_can_command")
    command_block_reason = fields.Char(compute="_compute_can_command")
    note = fields.Text()

    # ------------------------------------------------------------------ constraints, compute
    @api.constrains("camera_code", "active")
    def _check_camera(self):
        for gate in self.filtered(lambda g: g.camera_code and g.active):
            other = self.with_context(active_test=False).search(
                [("camera_code", "=", gate.camera_code), ("active", "=", True), ("id", "!=", gate.id)], limit=1
            )
            if other:
                raise ValidationError("Камера %s уже призначена воротам %s." % (gate.camera_code, other.name))

    def _compute_can_command(self):
        for gate in self:
            reason = gate.sudo()._f3d_yard_check("open", "manual", fields.Datetime.now())
            gate.command_block_reason = reason or False
            gate.can_command = not reason and (self.env.su or self.env.user.has_group(GRP_SEC))

    # ------------------------------------------------------------------ R-15
    def _f3d_yard_check(self, kind, reason, now):
        """R-15 п. 3–7: текст першої невдалої перевірки або None."""
        self.ensure_one()
        gate = self.sudo()
        if not P.get_bool(self.env, "write_enabled"):
            return (
                "Команди на шлагбаум вимкнено (td.yard.write_enabled). "
                "Відкрийте шлагбаум з пульта CAME і натисніть «Відкрито вручну»."
            )
        sig = gate[KIND_SIGNAL[kind]]
        if not (sig and sig.active and sig.write_enabled and sig.source_id.write_enabled):
            return "Сигнал команди «%s» для %s не налаштований або запис на сигналі/джерелі вимкнено." % (
                KIND_LABELS[kind],
                gate.td_code,
            )
        if kind in ("open", "close"):
            ph = gate.photocell_signal_id
            if not _fresh(ph, now, P.get_int(self.env, "signal_max_age_s")):
                return "Немає свіжих даних фотоелемента %s (останні: %s)." % (
                    ph.code if ph else gate.td_code,
                    tz.local_hm(ph.last_ts) if ph and ph.last_ts else "—",
                )
            if (ph.last_value >= 0.5) != gate.invert_di:
                return "Під стрілою перешкода (фотоелемент %s) — команда заборонена." % ph.code
        busy = (
            self.env["td.command"]
            .sudo()
            .search(
                [
                    ("td_yard_gate_id", "=", gate.id),
                    ("state", "in", ("queued", "sent")),
                    ("requested_at", ">", now - timedelta(seconds=P.get_int(self.env, "cmd_cooldown_s"))),
                ],
                limit=1,
                order="requested_at desc",
            )
        )
        if busy:
            return "Попередня команда «%s» ще виконується (з %s)." % (
                KIND_LABELS.get(busy.td_yard_kind, busy.td_yard_kind or "?"),
                tz.local_hm(busy.requested_at),
            )
        if reason in AUTO_REASONS and gate.state == "error":
            return "Ворота %s у стані помилки — авто-відкриття вимкнено." % gate.td_code
        return None

    def action_command(self, kind, visit=None, reason="manual"):
        self.ensure_one()
        if kind not in KINDS:
            raise ValueError("Невідома команда шлагбаума: %r" % kind)
        if reason == "manual":
            _f3d_yard_require(self.env, GRP_SEC)
        elif reason in AUTO_REASONS:
            if not self.env.su:
                raise AccessError("Автоматичні команди створює лише система.")
        else:
            raise ValueError("Невідома причина команди: %r" % reason)
        gate = self.sudo()
        self.env.cr.execute("SELECT id FROM td_yard_gate WHERE id = %s FOR UPDATE", [gate.id])
        now = fields.Datetime.now()
        error = gate._f3d_yard_check(kind, reason, now)
        if error:
            raise UserError(error)
        visit = visit.sudo() if visit else None
        requested_by = self.env.uid if reason == "manual" else self.env.ref("base.user_root").id
        cmd = (
            self.env["td.command"]
            .sudo()
            .create(
                {
                    "signal_id": gate[KIND_SIGNAL[kind]].id,
                    "value": 0.0 if kind == "release" else 1.0,
                    "origin": "yard",
                    "requested_at": now,
                    "expires_at": now + timedelta(seconds=P.get_int(self.env, "cmd_expire_s")),
                    "requested_by": requested_by,
                    "note": "%s %s · %s" % (kind, gate.td_code, (visit.name if visit else "") or ""),
                    "td_yard_gate_id": gate.id,
                    "td_yard_visit_id": visit.id if visit else False,
                    "td_yard_kind": kind,
                    "td_yard_reason": reason,
                }
            )
        )
        vals = {"last_command_id": cmd.id}
        if kind == "open":
            vals["open_cmd_id"] = cmd.id
        elif kind == "hold":
            vals["hold_until"] = now + timedelta(minutes=P.get_int(self.env, "hold_max_min"))
        elif kind == "release":
            vals["hold_until"] = False
        gate.write(vals)
        if kind == "open":
            gate._f3d_yard_count_permit(visit)
        text = "Команда «%s» %s (#%s) · %s" % (KIND_LABELS[kind], gate.td_code, cmd.id, CMD_STATE_LABELS[cmd.state])
        gate.message_post(body=text)
        if visit:
            visit.message_post(body=text)
        gate._f3d_yard_notify()
        return cmd

    def _notify_sent(self):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "message": "Команду надіслано",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def action_open(self):
        self.action_command("open")
        return self._notify_sent()

    def action_close(self):
        self.action_command("close")
        return self._notify_sent()

    def action_hold(self):
        self.action_command("hold")
        return self._notify_sent()

    def action_release(self):
        self.action_command("release")
        return self._notify_sent()

    def action_opened_manually(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        gate = self.sudo()
        gate._f3d_yard_count_permit(gate.pending_visit_id or None)
        gate.last_error = False
        gate.message_post(body="Відкрито з пульта CAME (%s)" % self.env.user.name)
        gate._f3d_yard_refresh_state()
        return True

    def action_reset_error(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        gate = self.sudo()
        gate.write({"last_error": False, "open_cmd_id": False})
        gate.activity_unlink(["mail.mail_activity_data_warning"])
        gate._f3d_yard_refresh_state()
        return True

    def action_view_commands(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Команди",
            "res_model": "td.command",
            "view_mode": "list,form",
            "domain": [("td_yard_gate_id", "=", self.id)],
        }

    def _f3d_yard_count_permit(self, visit=None):
        for gate in self.sudo():
            vals = {"admitted_today": gate.admitted_today + 1}
            if visit:
                vals["pending_visit_id"] = visit.id
            gate.write(vals)

    def _f3d_yard_notify(self):
        """R-21: сповіщення шини (реалізує W4); у W2 — нічого."""
        return True

    # ------------------------------------------------------------------ авто-відкриття (R-15 п. 10–11)
    @api.model
    def _f3d_yard_event_note(self, event, text, alert=None):
        if not event:
            return
        vals = {"note": ("%s; %s" % (event.note, text) if event.note else text)[:256]}
        if alert is not None:
            vals["kpp_alert"] = alert
        event.sudo().write(vals)

    def _f3d_yard_auto_open(self, visit, event=None):
        self.ensure_one()
        gate = self.sudo()
        visit = visit.sudo()
        now = fields.Datetime.now()
        outbound = bool(event and event.direction == "out")
        note = self._f3d_yard_event_note
        if gate.mode != "auto":
            return note(event, "Ворота в ручному режимі", None)
        if not P.get_bool(self.env, "write_enabled"):
            return note(event, "Команди вимкнено", None)
        if event and (now - event.ts).total_seconds() > 60:
            return note(
                event,
                "Подія запізнилась на %d с — авто-пропуск вимкнено" % (now - event.ts).total_seconds(),
                True,
            )
        if outbound:
            done_docs = all(p.state in ("done", "cancel") for p in visit.picking_ids)
            if visit.state == "weighed" or (
                visit.weighing_policy == "none" and visit.state in ("at_dock", "handling") and done_docs
            ):
                reason = "auto_exit"
            else:
                return None
        else:
            if gate.direction == "out" or visit.state != "arrived":
                return None
            booking = visit.booking_id
            if visit.is_walk_in or not booking or booking.state != "confirmed":
                return note(event, "Без броні", True)
            ts = event.ts if event else now
            start = visit.planned_start or booking.slot_start
            lo, hi = (
                start - timedelta(minutes=P.get_int(self.env, "early_min")),
                start + timedelta(minutes=P.get_int(self.env, "late_min")),
            )
            if not lo <= ts <= hi:
                return note(event, "Поза вікном слоту %s–%s" % (tz.local_hm(lo), tz.local_hm(hi)), True)
            reason = "auto_booking"
        try:
            gate.sudo().action_command("open", visit, reason)
        except UserError as e:
            return note(event, str(e.args[0]), True)
        if reason == "auto_booking":
            visit._set_state("queued", note="пропущено автоматично")
        return True

    # ------------------------------------------------------------------ R-17
    def _f3d_yard_on_readings(self, items):
        """items = [(role, ts, value, q)]; обробка за зростанням ts."""
        self.ensure_one()
        gate = self.sudo()
        opened_ts = None
        for role, ts, value, _q in sorted(items, key=lambda it: it[1]):
            v = float(value or 0.0)
            if role == "loop":
                occ = (v >= 0.5) != gate.invert_di
                visit = gate.pending_visit_id
                if gate.loop_occupied and not occ and visit:
                    if gate.direction in ("out", "both") and visit.state in (
                        "queued",
                        "at_dock",
                        "handling",
                        "weighed",
                    ):
                        visit.sudo().action_leave(ts, note="виїзд за петлею %s" % gate.td_code)
                    gate.pending_visit_id = False
                gate.loop_occupied = occ
            elif role == "photocell":
                gate.photocell_blocked = (v >= 0.5) != gate.invert_di
            elif role == "passes":
                gate._f3d_yard_on_passes(int(v), ts)
            elif role == "state":
                if (v >= 0.5) != gate.invert_di and gate.state not in ("open", "held"):
                    opened_ts = ts
        gate._f3d_yard_refresh_state(opened_ts=opened_ts)
        return True

    def _f3d_yard_on_passes(self, v, ts):
        if v < self.passes_day_start:
            self.passes_day_start = 0
        prev = self.passes_today
        vals = {"passes_today": v - self.passes_day_start, "counter_value": v}
        today = vals["passes_today"]
        if P.get_bool(self.env, "antipassback") and today > self.admitted_today and today > prev:
            vals["tailgate_today"] = self.tailgate_today + today - max(prev, self.admitted_today)
            vals["last_tailgate_at"] = ts
            self.message_post(body="Проїзд без дозволу: проїздів %s, дозволів %s" % (today, self.admitted_today))
            self._f3d_yard_notify()
        self.write(vals)

    # ------------------------------------------------------------------ R-16
    def _f3d_yard_is_open(self, now):
        """Стріла відкрита за свіжим сигналом стану (з урахуванням invert_di) або None, якщо стан невідомий."""
        self.ensure_one()
        sig = self.state_signal_id
        max_age = max(P.get_int(self.env, "signal_max_age_s"), 3 * (sig.period_s or 0))
        if not P.get_bool(self.env, "read_enabled") or not _fresh(sig, now, max_age):
            return None
        return (sig.last_value >= 0.5) != self.invert_di

    def _f3d_yard_refresh_state(self, now=None, opened_ts=None):
        now = now or fields.Datetime.now()
        for gate in self.sudo():
            gate._f3d_yard_refresh_one(now, opened_ts)
        return True

    def _f3d_yard_refresh_one(self, now, opened_ts):
        self.ensure_one()
        # 1. контроль команди «відкрити»
        cmd = self.open_cmd_id
        if cmd:
            if cmd.state in ("failed", "expired"):
                self.write(
                    {
                        "last_error": "Команду «Відкрити» не виконано: %s" % (cmd.error or CMD_STATE_LABELS[cmd.state]),
                        "open_cmd_id": False,
                    }
                )
            elif cmd.state == "cancelled":
                self.open_cmd_id = False
            elif cmd.state == "done":
                done_at = cmd.done_at or now
                if (self.opened_at and self.opened_at >= done_at - timedelta(seconds=1)) or self._f3d_yard_is_open(now):
                    self.open_cmd_id = False
                elif (now - done_at).total_seconds() > P.get_int(self.env, "open_timeout_s"):
                    self.write(
                        {
                            "last_error": "Немає підтвердження відкриття за %s с"
                            % P.get_int(self.env, "open_timeout_s"),
                            "open_cmd_id": False,
                        }
                    )
        # 2. утримання
        if self.hold_until and now > self.hold_until:
            if P.get_bool(self.env, "write_enabled"):
                try:
                    self.action_command("release", reason="auto_hold_max")
                except UserError as e:
                    self.message_post(body=str(e.args[0]))
            self.hold_until = False
            self.message_post(body="Утримання знято за часом (%s хв)" % P.get_int(self.env, "hold_max_min"))
        # 3. стан
        is_open = self._f3d_yard_is_open(now)
        if self.last_error:
            new = "error"
        elif is_open is None:
            new = "unknown"
        elif is_open:
            hold = self.cmd_hold_signal_id
            held = (self.hold_until and self.hold_until > now) or (
                _fresh(hold, now, P.get_int(self.env, "signal_max_age_s")) and hold.last_value >= 0.5
            )
            new = "held" if held else "open"
        else:
            new = "closed"
        old = self.state
        if new != old:
            vals = {"state": new, "state_since": now}
            if new in ("open", "held") and old not in ("open", "held"):
                vals["opened_at"] = opened_ts or now
            self.write(vals)
            if new == "error":
                self._f3d_yard_on_error()
            self._f3d_yard_notify()
        return True

    def _f3d_yard_on_error(self):
        self.message_post(body="Помилка воріт: %s" % self.last_error)
        if not self.responsible_id:
            return
        act_type = self.env.ref("mail.mail_activity_data_warning", raise_if_not_found=False)
        if act_type and not self.activity_ids.filtered(lambda a: a.activity_type_id == act_type):
            self.activity_schedule(
                "mail.mail_activity_data_warning",
                user_id=self.responsible_id.id,
                summary="Помилка воріт %s" % self.td_code,
                note=self.last_error,
            )

    @api.model
    def _cron_gates(self):
        """Крон: R-16 для всіх активних воріт."""
        for gate in self.sudo().search([]):
            try:
                with self.env.cr.savepoint():
                    gate._f3d_yard_refresh_state()
            except Exception:
                _logger.exception("f3d_yard: оновлення стану воріт %s", gate.td_code)
        return True
