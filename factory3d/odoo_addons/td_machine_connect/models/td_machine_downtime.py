import hashlib
import json
import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import api, models

from ..tools import ppt
from .td_machine import DOWN_STATES, KYIV

_logger = logging.getLogger(__name__)

EVENT_WINDOW_S = 120  # R-07: подія не раніше за `початок простою − 120 с`
REQUEST_WINDOW_MIN = 10  # R-08 п. 2
MIN_RECORD_MIN = 1.0  # R-05 п. 4: машинні записи ≥ 1 хв
BOUNDARY_ROUNDS = 8


def _parse_event_time(value):
    """ISO-час події (`…Z`) → naive UTC."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class F3dMachineDowntime(models.Model):
    """M-01 (`_inherit = "td.machine"`): простої, підказки, заявки ТО (R-05…R-08).

    Гачки `_f3d_after_commit`, `_f3d_tick_extra`, `_f3d_apply_event` перевизначені через `super()` першим.
    """

    _inherit = "td.machine"

    # --- гачки --------------------------------------------------------------------------------------
    def _f3d_after_commit(self, old, new, ts):
        """R-05 п. 1–4, R-08 п. 2: закрити поточний простій, відкрити новий для `new in DOWN_STATES`."""
        super()._f3d_after_commit(old, new, ts)
        for rec in self:
            rec._f3d_close_downtime(ts)
            if new in DOWN_STATES:
                rec._f3d_open_downtime(new, ts)

    def _f3d_tick_extra(self, now):
        """R-05 п. 6 (межа робочого дня), R-06 п. 3 і 5."""
        super()._f3d_tick_extra(now)
        for rec in self:
            rec._f3d_day_boundary(now)
            rec._f3d_reopen_after_boundary(now)
            rec._f3d_close_operator_records(now)
            rec._f3d_reopen_fault_record(now)

    @api.model
    def _f3d_apply_event(self, payload):
        """EV-01: журнал подій, показання `event`, підказка причини (R-07 п. 1), заявка ТО (R-08 п. 3)."""
        machine = super()._f3d_apply_event(payload)
        machine = machine.sudo()
        Event = self.env["td.machine.event"].sudo()
        source = str(payload.get("source") or "")
        ext_id = (
            self.env.context.get("f3d_push_event_id")
            or hashlib.sha256(
                (
                    "mc_opcua\n%s\n%s"
                    % (source, json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
                ).encode()
            ).hexdigest()
        )
        if Event.with_context(active_test=False).search_count([("ext_event_id", "=", ext_id)]):
            return machine
        ts = _parse_event_time(payload["time"])
        message_id = payload.get("message_id") or False
        texts = payload.get("texts") or {}
        text = (texts.get("uk") or (next(iter(texts.values()), None) if texts else None) or payload.get("text") or "")[
            :256
        ]
        path = payload.get("path")
        active = payload.get("active")
        event = Event.create(
            {
                "machine_id": machine.id,
                "ts": ts,
                "kind": payload["kind"],
                "message_id": message_id,
                "message_name": (payload.get("message_name") or "")[:64] or False,
                "category": str(int(payload["category"])),
                "severity": int(payload.get("severity") or 0),
                "text": text,
                "path": (" / ".join(path) if isinstance(path, list) else (path or ""))[:256] or False,
                "active": True if (payload["kind"] != "alarm" or active is None) else bool(active),
                "acked": bool(payload.get("acked")),
                "ext_event_id": ext_id,
                "payload": payload,
            }
        )
        if machine.sig_event_id:
            res = (
                self.env["td.signal"]
                .sudo()
                .with_context(f3d_mc_internal=True)
                ._f3d_ingest(
                    [
                        {
                            "code": machine.sig_event_id.code,
                            "ts": ts,
                            "text": ("%s %s" % (message_id or "", text)).strip()[:64],
                            "value": 1,
                            "q": "good",
                        }
                    ],
                    src="module",
                )
            )
            if res and res.get("rejected"):
                _logger.warning("td.machine %s: показання події відхилено: %s", machine.code, res["rejected"])
        if payload["kind"] == "alarm" and active is False:
            previous = Event.search(
                [("machine_id", "=", machine.id), ("message_id", "=", message_id), ("id", "!=", event.id)]
            ).filtered(lambda e: e.kind == "alarm")
            previous.write({"active": False})
            return machine
        machine._f3d_event_hint(event)
        return machine

    # --- R-07: підказки -----------------------------------------------------------------------------
    def _f3d_event_hint(self, event):
        """R-07 п. 1: подія після початку простою → підказка (і причина, якщо `auto_apply`)."""
        self.ensure_one()
        dt = self.current_downtime_id.sudo()
        if not dt or dt.date_end:
            return
        if int(event.category) < 3 or dt.reason_source not in ("auto", "hint"):
            return
        if dt.date_start < event.ts - timedelta(seconds=EVENT_WINDOW_S):
            return
        loss, text, ev = self._f3d_event_loss(event)
        if not loss:
            return
        dt._f3d_set_hint(loss, text, ev, self._f3d_hint_applies("fault", ev))
        self._f3d_post_request_event(dt)

    def _f3d_event_loss(self, event):
        """`(loss, hint_text, event)` події за довідником (категорія ≥ 4 без повідомлення → «Поломка»)."""
        message = event.message_rec_id
        loss = message.loss_id
        if not loss and int(event.category) >= 4:
            loss = self.env.ref("mrp.block_reason1")
        text = ("%s %s" % (event.message_id or "", event.text or "")).strip()
        return loss, text, event

    def _f3d_hint_applies(self, kind, event):
        """Чи ставиться підказка причиною автоматично (R-07 п. 1, 3, 4; п. 5 — ні)."""
        if event:
            message = event.message_rec_id
            return message.auto_apply if message else int(event.category) >= 4
        return kind in ("setup", "fault")

    def _f3d_hint(self, kind, ts):
        """R-07 п. 2–6: `(loss, hint_text, event)` для простою, що відкривається о `ts`."""
        self.ensure_one()
        Loss = self.env["mrp.workcenter.productivity.loss"]
        events = (
            self.env["td.machine.event"]
            .sudo()
            .search(
                [
                    ("machine_id", "=", self.id),
                    ("ts", ">=", ts - timedelta(seconds=EVENT_WINDOW_S)),
                    ("category", ">=", "3"),
                    ("downtime_id", "=", False),
                ]
            )
        )
        if events:
            best = max(events, key=lambda e: (int(e.category), e.ts))
            loss, text, ev = self._f3d_event_loss(best)
            if loss:
                return loss, text, ev
        if kind == "setup":
            return self.env.ref("mrp.block_reason2"), "Режим верстата SETUP", self.env["td.machine.event"]
        if kind == "fault":
            text = "Вхід аварії" if self.protocol == "io" else "Стан верстата ERROR"
            return self.env.ref("mrp.block_reason1"), text, self.env["td.machine.event"]
        if kind == "idle":
            wos = self.env["mrp.workorder"].sudo().search([("workcenter_id", "=", self.workcenter_id.id)])
            ready = wos.filtered(lambda w: w.state == "ready")
            blocked = wos.filtered(lambda w: w.state == "blocked")
            starved = ready.filtered(lambda w: w.production_id.reservation_state != "assigned")
            target = (blocked[:1] if not ready else wos.browse()) or starved[:1]
            if target:
                text = "%s: чекає компонентів/попередньої операції" % target.production_id.name
                return self.env.ref("mrp.block_reason0"), text, self.env["td.machine.event"]
        return Loss.browse(), "", self.env["td.machine.event"]

    # --- R-05: простій і записи журналу часу --------------------------------------------------------
    def _f3d_open_downtime(self, kind, ts):
        """R-05 п. 1–2, R-07, R-08 п. 2: відкрити простій (`kind` ∈ DOWN_STATES)."""
        self.ensure_one()
        Downtime = self.env["td.downtime"].sudo()
        if Downtime.search_count([("machine_id", "=", self.id), ("date_end", "=", False)]):
            self._f3d_close_downtime(ts)
        wo = self.active_workorder_id
        dt = Downtime.create(
            {
                "machine_id": self.id,
                "date_start": ts,
                "state_kind": kind,
                "workorder_id": wo.id if wo else False,
                "loss_id": self.env.ref("td_machine_connect.loss_unknown").id,
                "reason_source": "auto",
                "reason_state": "to_classify",
            }
        )
        self.with_context(tracking_disable=True).write({"current_downtime_id": dt.id})
        loss, text, event = self._f3d_hint(kind, ts)
        operator_rec = self._f3d_bind_operator_record(dt)
        if loss:
            dt._f3d_set_hint(loss, text, event, self._f3d_hint_applies(kind, event))
        if kind == "fault":
            close_timers = getattr(self, "_f3d_close_timers", None)
            if close_timers:
                close_timers(ts)
            if not operator_rec:
                self._f3d_create_machine_record(dt, ts, dt.hint_text or "Аварія верстата")
        self._f3d_link_request(dt, ts)
        return dt

    def _f3d_bind_operator_record(self, dt):
        """R-05 п. 1: відкритий запис втрати оператора без завдання → прив'язати, причина стає причиною простою."""
        rec = (
            self.env["mrp.workcenter.productivity"]
            .sudo()
            .search(
                [
                    ("workcenter_id", "=", self.workcenter_id.id),
                    ("date_end", "=", False),
                    ("td_auto", "=", False),
                    ("td_downtime_id", "=", False),
                    ("workorder_id", "=", False),
                    ("loss_id.loss_type", "in", ("availability", "quality")),
                ],
                limit=1,
            )
        )
        if not rec:
            return rec
        rec.write({"td_downtime_id": dt.id})
        master = rec.td_source == "master"
        dt._f3d_apply_reason(rec.loss_id, "master" if master else "operator", dt.employee_id)
        dt.sudo().with_context(f3d_mc_internal=True).write({"reason_state": "confirmed" if master else "to_confirm"})
        return rec

    def _f3d_create_machine_record(self, dt, ts, description, date_end=None, workorder=None, loss=None):
        """Запис журналу часу верстата (R-05) у технічному середовищі."""
        vals = {
            "workcenter_id": self.workcenter_id.id,
            "loss_id": (loss or dt.loss_id).id,
            "date_start": ts,
            "description": description,
            "td_downtime_id": dt.id,
            "td_source": "machine",
            "td_auto": True,
        }
        if date_end:
            vals["date_end"] = date_end
        if workorder:
            vals["workorder_id"] = workorder.id
        if dt.employee_id and "employee_id" in self.env["mrp.workcenter.productivity"]._fields:
            vals["employee_id"] = dt.employee_id.id
        return self._f3d_tech_env()["mrp.workcenter.productivity"].create(vals)

    def _f3d_close_downtime(self, ts):
        """R-05 п. 4: закрити відкриті простої верстата переходом о `ts`."""
        self.ensure_one()
        downtimes = self.env["td.downtime"].sudo().search([("machine_id", "=", self.id), ("date_end", "=", False)])
        for dt in downtimes:
            dt._f3d_close(ts)
        if self.current_downtime_id:
            self.with_context(tracking_disable=True).write({"current_downtime_id": False})
        return True

    def _f3d_link_request(self, dt, ts):
        """R-08 п. 2: відкрита заявка ТО з тривоги верстата → простій `fault`."""
        if dt.state_kind != "fault" or not self.sig_alarm_id or dt.maintenance_request_id:
            return
        Request = self.env["maintenance.request"].sudo()
        cands = Request.search(
            [
                ("td_signal_id", "=", self.sig_alarm_id.id),
                ("stage_id.done", "=", False),
                ("create_date", ">=", ts - timedelta(minutes=REQUEST_WINDOW_MIN)),
            ],
            order="create_date desc",
        )
        taken = (
            self.env["td.downtime"]
            .sudo()
            .search([("maintenance_request_id", "in", cands.ids)])
            .mapped("maintenance_request_id")
        )
        free = cands - taken
        if free:
            dt.write({"maintenance_request_id": free[0].id})
            self._f3d_post_request_event(dt)

    def _f3d_post_request_event(self, dt):
        """R-08 п. 1, 3: «Подія верстата: <hint_text> (<час Київ>)» у заявку."""
        req = dt.maintenance_request_id.sudo()
        if not req or not dt.hint_text:
            return
        when = dt.event_id.ts or dt.date_start
        local_t = when.replace(tzinfo=ZoneInfo("UTC")).astimezone(KYIV).strftime("%d.%m %H:%M")
        req.message_post(body="Подія верстата: %s (%s)" % (dt.hint_text, local_t))

    # --- R-05 п. 6: межа робочого дня ---------------------------------------------------------------
    def _f3d_tz(self, wc):
        cal = wc.resource_calendar_id or wc.company_id.resource_calendar_id
        return ZoneInfo(cal.tz) if cal and cal.tz else KYIV

    def _f3d_is_day_end(self, wc, end, tz):
        """Чи є `end` кінцем останнього інтервалу планового часу локального дня."""
        local_day = (end - timedelta(seconds=1)).replace(tzinfo=ZoneInfo("UTC")).astimezone(tz).date()
        midnight = datetime.combine(local_day + timedelta(days=1), time.min, tz)
        limit = midnight.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        return not ppt.ppt_intervals(self.env, wc, end, limit)

    def _f3d_next_ppt_start(self, wc, after):
        ivs = ppt.ppt_intervals(self.env, wc, after, after + timedelta(days=10))
        return ivs[0][0] if ivs else None

    def _f3d_day_boundary(self, now):
        """Межа дня: закрити простій `idle/setup/off` о кінці планового часу, відкрити новий наступного дня."""
        self.ensure_one()
        wc = self.workcenter_id.sudo()
        tz = self._f3d_tz(wc)
        for _i in range(BOUNDARY_ROUNDS):
            dt = self.current_downtime_id.sudo()
            if not dt or dt.date_end or dt.state_kind == "fault":
                return
            end = None
            for _s, e in ppt.ppt_intervals(self.env, wc, dt.date_start, now):
                if e <= now and self._f3d_is_day_end(wc, e, tz):
                    end = e
                    break
            if not end:
                return
            kind = dt.state_kind
            self._f3d_close_downtime(end)
            if self.state != kind:
                return
            nxt = self._f3d_next_ppt_start(wc, end)
            if not nxt or nxt > now:
                return
            self._f3d_open_downtime(kind, nxt)

    def _f3d_reopen_after_boundary(self, now):
        """Стан не змінився після закриття на межі дня → новий простій з початку наступного інтервалу."""
        self.ensure_one()
        if self.state not in ("idle", "setup", "off") or self.current_downtime_id:
            return
        last = self.env["td.downtime"].sudo().search([("machine_id", "=", self.id)], order="date_end desc", limit=1)
        if not last or not last.date_end or last.state_kind != self.state or last.date_end < self.state_since:
            return
        wc = self.workcenter_id.sudo()
        nxt = self._f3d_next_ppt_start(wc, last.date_end)
        if nxt and nxt <= now:
            self._f3d_open_downtime(self.state, nxt)
            self._f3d_day_boundary(now)

    # --- R-06 п. 3 і 5 -------------------------------------------------------------------------------
    def _f3d_close_operator_records(self, now):
        """Верстат працює ≥ `micro_stop_s` після створення запису оператора → закрити запис (п. 3)."""
        self.ensure_one()
        if self.state != "working" or self.pending_state or not self.state_since:
            return
        recs = (
            self.env["mrp.workcenter.productivity"]
            .sudo()
            .search(
                [
                    ("workcenter_id", "=", self.workcenter_id.id),
                    ("date_end", "=", False),
                    ("td_auto", "=", False),
                    ("td_downtime_id", "=", False),
                    ("workorder_id", "=", False),
                    ("loss_id.loss_type", "in", ("availability", "quality")),
                ]
            )
        )
        for rec in recs:
            if now >= max(rec.date_start, self.state_since) + timedelta(seconds=self.micro_stop_s):
                desc = (rec.description or "") + " (закрито: верстат працює)"
                rec.with_env(self._f3d_tech_env()).write({"date_end": now, "description": desc.strip()})

    def _f3d_reopen_fault_record(self, now):
        """Оператор «Розблокував» під час аварії: відкрити новий машинний запис «Аварія триває» (п. 5)."""
        self.ensure_one()
        dt = self.current_downtime_id.sudo()
        if self.state != "fault" or not dt or dt.date_end:
            return
        if dt.productivity_ids.filtered(lambda r: not r.date_end):
            return
        loss = dt.loss_id
        self._f3d_create_machine_record(dt, now, "Аварія триває", loss=loss)
