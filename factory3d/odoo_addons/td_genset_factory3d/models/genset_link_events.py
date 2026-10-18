"""R-07, R-08, R-09: події контролера td_genset → заявки ТО; ТО за мотогодинами (SPEC §6, §13.1)."""

import logging
import re
from datetime import datetime, timedelta, timezone

from odoo import _, api, fields, models

from ..adapters import td_genset as td
from ..adapters import telemetry
from .genset_link import KYIV, _to_utc_naive

_logger = logging.getLogger(__name__)
EVENT_BATCH = 200
CODE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
NAME_LIMIT = 255
# рядки мапи, після дії яких виконується R-09 (крок 7)
SERVICE_ROW_KEYS = ("MAINTENANCE_DUE_W", "MAINTENANCE_DUE_SD", "DEFAULT_SERVICE")


def _fmt_int(value):
    """1250 → «1 250»."""
    return format(int(round(value or 0)), ",").replace(",", " ")


class F3dGensetLinkEvents(models.Model):
    _inherit = "td.genset.link"

    # --- крони -----------------------------------------------------------------------------------------------
    @api.model
    def _cron_events(self):
        if not self._flag("requests_enabled", "True"):
            return
        retry = False
        for link in self.search([]):
            try:
                with self.env.cr.savepoint():
                    retry = link._process_events_one() or retry
            except Exception:  # MG-11: збій однієї зв'язки не валить крон
                _logger.exception("td_genset_factory3d: події зв'язки %s не оброблено", link.id)
        if retry:  # повтор наступного прогону при 200
            cron = self.env.ref("td_genset_factory3d.cron_td_genset_events", raise_if_not_found=False)
            if cron:
                cron.sudo()._trigger()

    @api.model
    def _cron_service(self):
        if not self._flag("requests_enabled", "True"):
            return
        for link in self.search([]):
            try:
                with self.env.cr.savepoint():
                    link._service_one()
            except Exception:
                _logger.exception("td_genset_factory3d: ТО за мотогодинами для зв'язки %s не оброблено", link.id)

    # --- події -----------------------------------------------------------------------------------------------
    def _process_events_one(self):
        """ADP-04 → R-07/R-08; повертає True, якщо прочитано повний пакет (потрібен повтор)."""
        self.ensure_one()
        kwargs = {"limit": EVENT_BATCH}
        if self.last_event_ts:
            kwargs["since"] = self.last_event_ts
        events = td.events_since(self.td_genset_ref, **kwargs)
        last = None
        for ev in events:
            ev = dict(ev)
            code = ev.get("code") or ""
            ev["code"] = code if CODE_RE.match(code) else ""
            ev["name"] = (ev.get("name") or "")[:NAME_LIMIT]
            ev["text"] = (ev.get("text") or "")[:2000]
            try:
                with self.env.cr.savepoint():
                    self._apply_event(ev, self.env["td.genset.event.map"]._match(ev))
            except Exception:  # одна «отруйна» подія не блокує потік
                _logger.exception("td_genset_factory3d: подію %s зв'язки %s не оброблено", ev.get("id"), self.id)
            last = ev
        if last:
            vals = {"last_event_id": last.get("id") or 0}
            ts = _to_utc_naive(last.get("ts"))
            if ts:
                vals["last_event_ts"] = ts
            self.write(vals)
        return len(events) >= EVENT_BATCH

    def _apply_event(self, ev, row):
        """R-07 кроки 2–3, R-08, R-09 крок 7. Немає рядка / ignore → нічого."""
        self.ensure_one()
        if not row or row.action == "ignore":
            return False
        if ev.get("code") == "COMM_LOST" and ev.get("value") is None:
            ev = dict(ev, value=self._offline_minutes())
        request = False
        if row.action == "bus_only":
            self._notify_bus_state()
        else:
            request = self._open_request(row, ev, "GENSET:%s" % row.key, self._signal_leaf(row))
        if row.key in SERVICE_ROW_KEYS or ev.get("severity") == "service":
            self._service_one()
        return request

    def _offline_minutes(self):
        since = (self.last_state_json or {}).get("offline_since")
        if not since:
            return None
        return max(0.0, (fields.Datetime.now() - fields.Datetime.from_string(since)).total_seconds() / 60.0)

    @staticmethod
    def _signal_leaf(row):
        if row.severity == "comm":
            return "online"
        if row.severity == "service" or row.action == "request_preventive":
            return "hours"
        return "alarm_level"

    def _notify_bus_state(self):
        if "td.viewer.event" in self.env:
            self.env["td.viewer.event"]._notify("maintenance.equipment", [self.td_code], "state")

    def _open_request(self, row, ev, key, leaf, priority=None, schedule_date=None, notify_repeat=True):
        """R-07 крок 3 + R-08: одна відкрита заявка на ключ; повтор — коментар. Повертає заявку або False."""
        self.ensure_one()
        if row.action == "request_preventive" and td.SERVICE_REQUESTS_BY_TD:
            return False  # планові заявки створює td_genset (Q-17); консервативно не дублюємо
        eq = self.equipment_id
        Request = self.env["maintenance.request"].sudo()  # R-07: заявка від імені OdooBot
        name, description = row._render(ev, self)
        open_req = Request.search(
            [("equipment_id", "=", eq.id), ("td_genset_event_key", "=", key), ("stage_id.done", "=", False)], limit=1
        )
        if open_req:
            if notify_repeat:
                ts = _to_utc_naive(ev.get("ts")) or fields.Datetime.now()
                local = ts.replace(tzinfo=timezone.utc).astimezone(KYIV)
                open_req.message_post(
                    body=_("Повтор: %(name)s о %(time)s", name=name, time=local.strftime("%H:%M %d.%m"))
                )
            return open_req
        priority = priority or row.priority or "2"
        now = fields.Datetime.now()
        team = eq.maintenance_team_id or self.env["maintenance.team"].sudo().search(
            [("company_id", "in", (eq.company_id.id, False))], limit=1
        )
        signal = self.env["td.signal"].sudo().search([("code", "=", telemetry.prefix(eq.td_code) + leaf)], limit=1)
        vals = {
            "name": name,
            "description": description,
            "equipment_id": eq.id,
            "maintenance_team_id": team.id,
            "priority": priority,
            "maintenance_type": "preventive" if row.action == "request_preventive" else "corrective",
            "request_date": datetime.now(KYIV).date(),
            "schedule_date": schedule_date or (now if priority == "3" else now + timedelta(days=1)),
            "user_id": eq.technician_user_id.id or False,
            "td_signal_id": signal.id or False,
            "td_genset_event_key": key,
            "company_id": eq.company_id.id or self.env.company.id,
        }
        if "maintenance_for" in Request._fields:  # Odoo 19 CE поля немає
            vals["maintenance_for"] = "equipment"
        if ev.get("value") is not None and row.severity not in ("comm", "service"):
            vals["td_value"] = ev["value"]
        if ev.get("threshold") is not None:
            vals["td_threshold"] = ev["threshold"]
        return Request.create(vals)

    # --- R-09: ТО за мотогодинами ------------------------------------------------------------------------------
    def _service_one(self):
        self.ensure_one()
        eq = self.equipment_id
        Request = self.env["maintenance.request"].sudo()
        hours_signal = (
            self.env["td.signal"].sudo().search([("code", "=", telemetry.prefix(eq.td_code) + "hours")], limit=1)
        )
        if td.SERVICE_REQUESTS_BY_TD:
            # крок 1: заявки створює td_genset — міст лише дописує сигнал `hours`
            if hours_signal:
                Request.search(
                    [
                        ("equipment_id", "=", eq.id),
                        ("maintenance_type", "=", "preventive"),
                        ("stage_id.done", "=", False),
                        ("td_signal_id", "=", False),
                        ("td_genset_event_key", "=", False),
                    ]
                ).write({"td_signal_id": hours_signal.id})
            return False
        info = td.service_info(self.td_genset_ref)
        left, hours_now, next_h = info.get("hours_left"), info.get("hours_now"), info.get("next_service_hours")
        try:
            warn_h = float(self._param("service_warn_h", "50"))
        except (TypeError, ValueError):
            warn_h = 50.0
        if left is None or next_h is None or not (info.get("due") or left <= warn_h):
            return False
        row = self.env["td.genset.event.map"].search([("key", "=", "SERVICE_DUE")], limit=1)
        if not row:
            return False
        avg = self._avg_hours_per_day(hours_signal, hours_now)
        days = min(365.0, max(0.0, left / avg))
        now = fields.Datetime.now()
        priority = "3" if left < 0 else "2" if left <= 10 else "1"
        if left >= 0:
            text = _(
                "через %(h)s мотогодин (наступне на %(next)s, зараз %(now)s)",
                h=_fmt_int(left),
                next=_fmt_int(next_h),
                now=_fmt_int(hours_now),
            )
        else:
            text = _(
                "прострочено на %(h)s мотогодин (наступне на %(next)s, зараз %(now)s)",
                h=_fmt_int(-left),
                next=_fmt_int(next_h),
                now=_fmt_int(hours_now),
            )
        ev = {
            "id": 0,
            "ts": now,
            "code": "SERVICE_DUE",
            "severity": "service",
            "name": _("Планове ТО"),
            "value": None,
            "unit": None,
            "threshold": None,
            "text": text,
        }
        return self._open_request(
            row,
            ev,
            "GENSET:SERVICE:%d" % int(next_h),
            "hours",
            priority=priority,
            schedule_date=now + timedelta(days=days),
            notify_repeat=False,
        )

    def _avg_hours_per_day(self, hours_signal, hours_now):
        """R-09 крок 3: (hours_now − перше показання за 30 діб)/30, не менше 0,1; немає показань — 1,0."""
        if not hours_signal or hours_now is None:
            return 1.0
        since = fields.Datetime.now() - timedelta(days=30)
        first = (
            self.env["td.reading"]
            .sudo()
            .search([("signal_id", "=", hours_signal.id), ("ts", ">=", since)], order="ts, id", limit=1)
        )
        if not first:
            return 1.0
        return max(0.1, (hours_now - first.value) / 30.0)
