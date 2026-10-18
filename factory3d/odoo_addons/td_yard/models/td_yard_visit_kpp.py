"""f3d.yard.visit: екран КПП (API-01/02, R-18), сповіщення R-21, крон no_show і auto_call_next (W4)."""

import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.tools import SQL

from ..tools import params as P
from ..tools import tz
from .f3d_yard_notify import f3d_yard_bus_add
from .f3d_yard_visit import GRP_DISP, GRP_SEC, _f3d_yard_require

_logger = logging.getLogger(__name__)

IN_YARD_STATES = ("queued", "at_dock", "handling", "weighed")
STATE_ORDER = {s: i for i, s in enumerate(IN_YARD_STATES)}
VISIT_ACTIONS = {
    "arrived": ["admit", "reject"],
    "queued": ["call", "weigh", "leave"],
    "at_dock": ["weigh", "leave"],
    "handling": ["weigh", "leave"],
    "weighed": ["leave"],
}
OPEN_MATCH = ("unmatched", "low_confidence")
LIST_LIMIT = 50
EVENT_RECENT = 20
SINCE_FIELD = {
    "arrived": "arrived_at",
    "queued": "admitted_at",
    "at_dock": "at_dock_at",
    "handling": "handling_start_at",
    "weighed": "weighed_out_at",
}
DURATION_MARKS = {  # поле -> групи міток (у кожній групі потрібна хоча б одна)
    "wait_min": (("arrived_at",), ("at_dock_at",)),
    "dock_min": (("at_dock_at",), ("handling_end_at", "weighed_out_at", "left_at")),
    "total_min": (("arrived_at",), ("left_at",)),
    "late_min": (("arrived_at",), ("planned_start",)),
}
GATE_ACTIONS = ("open", "close", "hold", "release")


def _hm(dt):
    return tz.local_hm(dt) if dt else None


def _ymdhm(dt):
    return tz.to_local(dt).strftime("%Y-%m-%d %H:%M") if dt else None


class F3dYardVisitKpp(models.Model):
    _inherit = "f3d.yard.visit"

    # ------------------------------------------------------------------ R-21
    def _f3d_yard_notify(self):
        res = super()._f3d_yard_notify()
        visits = self.sudo()
        f3d_yard_bus_add(self.env, "f3d.yard.visit", visits.ids)
        ev = self._f3d_yard_viewer_event()
        if ev:
            for visit in visits:
                ev._notify("f3d.yard.visit", [visit.name, visit.scene_code, visit.dock_code], "doc")
        return res

    # ------------------------------------------------------------------ R-19 п. 1, 3: середні без відсутніх міток
    @api.model
    def _read_group_select(self, aggregate_spec, query):
        fname, _sep, func = aggregate_spec.partition(":")
        if func == "avg" and fname in DURATION_MARKS:
            conds = []
            for marks in DURATION_MARKS[fname]:
                cols = [self._field_to_sql(self._table, m, query) for m in marks]
                conds.append(SQL("COALESCE(%s) IS NOT NULL", SQL(", ").join(cols)))
            return SQL(
                "AVG(CASE WHEN %s THEN %s END)",
                SQL(" AND ").join(conds),
                self._field_to_sql(self._table, fname, query),
            )
        return super()._read_group_select(aggregate_spec, query)

    # ------------------------------------------------------------------ API-01
    def _f3d_yard_card_color(self, now):
        """R-18 п. 1: колір картки рейсу."""
        self.ensure_one()
        gate_err = any(g.state == "error" and g.last_error for g in (self.gate_in_id | self.gate_out_id))
        if self.weight_check == "deviation" or gate_err:
            return "red"
        if self.state in ("at_dock", "handling"):
            return "blue"
        if self.is_walk_in:
            return "yellow"
        if self.state == "arrived":
            booking = self.booking_id
            if not booking or booking.state != "confirmed" or not booking.slot_start:
                return "yellow"
            early = timedelta(minutes=P.get_int(self.env, "early_min"))
            late = timedelta(minutes=P.get_int(self.env, "late_min"))
            ref = self.arrived_at or now
            if not (booking.slot_start - early <= ref <= booking.slot_start + late):
                return "yellow"
        return "green"

    def _f3d_yard_card(self, now, with_actions=True):
        self.ensure_one()
        state_labels = dict(self._fields["state"].selection)
        card = {
            "visit_id": self.id,
            "name": self.name,
            "plate": self.plate_display or "",
            "partner": self.partner_id.name or "",
            "carrier": self.carrier_id.name or "",
            "type": self.visit_type,
            "state": self.state,
            "state_label": state_labels[self.state],
            "dock": self.dock_code or "",
            "slot": ("%s–%s" % (_hm(self.planned_start), _hm(self.planned_end))) if self.planned_start else "",
            "since": _hm(self[SINCE_FIELD[self.state]] or self.arrived_at),
            "walk_in": bool(self.is_walk_in),
            "color": self._f3d_yard_card_color(now),
            "weights": {"gross": self.gross_kg, "tare": self.tare_kg, "net": self.net_kg},
            "progress": self.progress if self.state in ("at_dock", "handling") else 0.0,
            "actions": list(VISIT_ACTIONS.get(self.state, [])),
        }
        return card

    @api.model
    def _f3d_yard_event_card(self, event):
        labels = dict(event._fields["match_state"].selection)
        if event.match_state == "unknown_camera":
            color = "red"
        elif event.kpp_alert:
            color = "yellow"
        elif event.match_state == "matched":
            color = "green"
        else:
            color = "grey"
        if event.match_state in OPEN_MATCH:
            actions = ["link", "dismiss"] if event.direction == "out" else ["walk_in", "reject", "link", "dismiss"]
        else:
            actions = ["dismiss"] if event.kpp_alert else []
        image_url = False
        if event.image_attachment_id:
            image_url = "/web/content/%s" % event.image_attachment_id.id
        return {
            "id": event.id,
            "ts": _hm(event.ts),
            "camera": event.camera_code or "",
            "gate": event.gate_id.f3d_code or "",
            "direction": event.direction or "",
            "plate": event.plate_norm or "",
            "confidence": event.confidence,
            "match_state": event.match_state,
            "match_label": labels.get(event.match_state, ""),
            "visit": event.visit_id.name or None,
            "kpp_alert": bool(event.kpp_alert),
            "color": color,
            "image_url": image_url or event.image_url or None,
            "actions": actions,
        }

    def _f3d_yard_gate_card(self, gate, now):
        labels = dict(gate._fields["state"].selection)
        block = gate._f3d_yard_check("open", "manual", now)
        return {
            "id": gate.id,
            "code": gate.f3d_code,
            "name": gate.name,
            "direction": gate.direction,
            "mode": gate.mode,
            "state": gate.state,
            "state_label": labels.get(gate.state, ""),
            "error": gate.last_error or None,
            "loop": bool(gate.loop_occupied),
            "photocell": bool(gate.photocell_blocked),
            "last_plate": gate.last_plate or "",
            "last_plate_at": _hm(gate.last_plate_at),
            "passes_today": gate.passes_today,
            "admitted_today": gate.admitted_today,
            "tailgate_today": gate.tailgate_today,
            "hold_until": _hm(gate.hold_until),
            "command_block": block or None,
        }

    def _f3d_yard_scale_card(self, now):
        scale = self.env["f3d.yard.scale"].search([("company_id", "=", self.env.company.id)], limit=1)
        if not scale:
            return None
        last = scale.last_weighing_id
        return {
            "id": scale.id,
            "code": scale.f3d_code,
            "weight_kg": scale.last_weight_kg,
            "stable": bool(scale.last_stable),
            "state": scale.capture_state,
            "age_s": int((now - scale.last_ts).total_seconds()) if scale.last_ts else None,
            "offline": scale.capture_state == "offline",
            "today_count": scale.today_count,
            "last": {
                "plate": last.plate or "",
                "weight_kg": last.weight_kg,
                "kind": last.kind,
                "picking": last.picking_id.name or "",
                "ts": _hm(last.ts),
            }
            if last
            else None,
        }

    @api.model
    def kpp_data(self, gate_ids=None):
        _f3d_yard_require(self.env, GRP_SEC)
        env = self.sudo().env
        Visit, Gate, Event = env["f3d.yard.visit"], env["f3d.yard.gate"], env["f3d.yard.lpr.event"]
        now = fields.Datetime.now()
        is_disp = self.env.user.has_group(GRP_DISP)
        walk_in_left = max(P.get_int(env, "walk_in_limit_per_day") - env["f3d.yard.walkin.wizard"]._walk_in_today(), 0)
        write_enabled = P.get_bool(env, "write_enabled")
        gate_domain = [("company_id", "in", (self.env.company.id, False))]
        if gate_ids:
            gate_domain.append(("id", "in", list(gate_ids)))
        gates = Gate.search(gate_domain)
        gate_cards = [self._f3d_yard_gate_card(g, now) for g in gates]
        command_reason = next((g["command_block"] for g in gate_cards if g["command_block"]), None)
        at_gate = Visit.search([("state", "=", "arrived")], order="arrived_at, id", limit=LIST_LIMIT)
        in_yard = Visit.search([("state", "in", IN_YARD_STATES)], limit=LIST_LIMIT * 4).sorted(
            key=lambda v: (STATE_ORDER[v.state], v.admitted_at or v.arrived_at or now, v.id)
        )[:LIST_LIMIT]
        day_start, _end = tz.day_bounds_utc(tz.local_day(now))
        events = Event.search(
            ["|", ("received_at", ">=", day_start), ("kpp_alert", "=", True)],
            order="ts desc, id desc",
            limit=EVENT_RECENT,
        )
        events |= Event.search([("kpp_alert", "=", True)], order="ts desc, id desc", limit=LIST_LIMIT)
        events = events.sorted(key=lambda e: (e.ts, e.id), reverse=True)
        unassigned = env["f3d.yard.weighing"].search([("state", "=", "unassigned")], order="ts desc, id desc", limit=20)
        scale_label = {"in": "В'їзд", "out": "Виїзд", "check": "Контрольне"}
        return {
            "now": _ymdhm(now),
            "refresh_s": P.get_int(env, "kpp_refresh_s"),
            "read_enabled": P.get_bool(env, "read_enabled"),
            "write_enabled": write_enabled,
            "can": {
                "walk_in": (P.get_bool(env, "walk_in_allowed") and walk_in_left > 0) or is_disp,
                "walk_in_left": walk_in_left,
                "dispatcher": is_disp,
                "command": write_enabled,
                "command_reason": command_reason or "",
            },
            "gates": gate_cards,
            "scale": self._f3d_yard_scale_card(now),
            "at_gate": [v._f3d_yard_card(now) for v in at_gate],
            "in_yard": [v._f3d_yard_card(now) for v in in_yard],
            "events": [self._f3d_yard_event_card(e) for e in events],
            "unassigned_weighings": [
                {
                    "id": w.id,
                    "name": w.name,
                    "ts": _hm(w.ts),
                    "weight_kg": w.weight_kg,
                    "kind": scale_label.get(w.kind, w.kind),
                    "color": "red",
                    "actions": ["assign_weighing"],
                }
                for w in unassigned
            ],
        }

    # ------------------------------------------------------------------ API-02
    @api.model
    def _f3d_yard_kpp_wizard(self, act, **ctx):
        act = dict(act)
        act["context"] = dict(act.get("context") or {}, kpp=1, **ctx)
        return act

    @api.model
    def kpp_action(self, action, visit_id=None, event_id=None, gate_id=None, values=None):
        _f3d_yard_require(self.env, GRP_SEC)
        values = values or {}
        Event = self.env["f3d.yard.lpr.event"]
        visit = self.browse(visit_id).exists() if visit_id else self.browse()
        event = Event.browse(event_id).exists() if event_id else Event
        gate = self.env["f3d.yard.gate"].browse(gate_id).exists() if gate_id else self.env["f3d.yard.gate"]
        message, result_action = "Готово", None
        if action in ("admit", "call", "leave", "weigh", "reject") and not visit and not (action == "reject" and event):
            raise UserError("Оберіть рейс.")
        if action == "admit":
            message = self._f3d_yard_message(visit.action_admit(), "Фуру пропущено")
        elif action == "call":
            visit.action_call_to_dock()
            message = "Фуру викликано на ворота"
        elif action == "leave":
            visit.action_leave()
            message = "Виїзд зафіксовано"
        elif action == "reject":
            result_action = visit.action_reject_wizard() if visit else event.action_reject()
            result_action = self._f3d_yard_kpp_wizard(result_action)
        elif action == "walk_in":
            if event:
                result_action = event.action_walk_in()
            else:
                plate = (values.get("plate") or "").strip()
                if not plate or not gate:
                    raise UserError("Вкажіть номер і ворота.")
                result_action = {
                    "type": "ir.actions.act_window",
                    "name": "Рейс без броні",
                    "res_model": "f3d.yard.walkin.wizard",
                    "view_mode": "form",
                    "target": "new",
                    "context": {"default_plate": plate, "default_gate_id": gate.id},
                }
            result_action = self._f3d_yard_kpp_wizard(result_action)
        elif action == "weigh":
            result_action, message = self._f3d_yard_kpp_weigh(visit, values)
        elif action in GATE_ACTIONS:
            if not gate:
                raise UserError("Оберіть ворота.")
            gate.action_command(action)
            message = "Команду надіслано"
        elif action == "opened_manually":
            if not gate:
                raise UserError("Оберіть ворота.")
            gate.action_opened_manually()
            message = "Відкриття вручну враховано"
        elif action == "link":
            if not event or not visit_id:
                raise UserError("Оберіть подію й рейс.")
            event.action_link_visit(visit_id)
            message = "Подію прив'язано до рейсу"
        elif action == "dismiss":
            if not event:
                raise UserError("Оберіть подію.")
            event.action_dismiss()
            message = "Вирішено"
        elif action == "assign_weighing":
            weighing = self.env["f3d.yard.weighing"].browse(values.get("weighing_id") or 0).exists()
            if not weighing or not visit:
                raise UserError("Оберіть зважування й рейс.")
            weighing.action_assign(visit.id)
            message = "Зважування призначено рейсу"
        else:
            raise UserError("Невідома дія КПП: %s" % action)
        f3d_yard_bus_add(self.env, "f3d.yard.visit", visit.ids)
        f3d_yard_bus_add(self.env, "f3d.yard.gate", gate.ids)
        f3d_yard_bus_add(self.env, "f3d.yard.lpr.event", event.ids)
        return {"ok": True, "message": message, "action": result_action}

    @staticmethod
    def _f3d_yard_message(result, default):
        if isinstance(result, dict):
            return (result.get("params") or {}).get("message") or default
        return default

    def _f3d_yard_kpp_weigh(self, visit, values):
        weight = values.get("weight_kg")
        if weight:
            try:
                weight = float(weight)
            except (TypeError, ValueError) as exc:
                raise UserError("Вага має бути числом.") from exc
            if visit.state not in ("queued", "at_dock", "handling"):
                raise UserError("Зважити можна фуру в черзі, біля воріт або в операції.")
            vals = {
                "visit_id": visit.id,
                "kind": "in" if not visit.weighed_in_at else "out",
                "weight_kg": weight,
                "source": "manual",
                "ts": fields.Datetime.now(),
            }
            scale = self.env["f3d.yard.scale"].search([("company_id", "=", visit.company_id.id)], limit=1)
            if scale:
                vals["scale_id"] = scale.id
            self.env["f3d.yard.weighing"].create(vals)
            return None, "Зважування записано: %s кг" % ("%.0f" % weight)
        act = visit.action_weigh()
        if isinstance(act, dict) and act.get("target") == "new":
            return act, "Введіть вагу вручну"
        return None, "Зважування записано"

    # ------------------------------------------------------------------ крон (R-19 п. 2, R-05 п. 4)
    @api.model
    def _cron_queue(self):
        res = super()._cron_queue()
        self._f3d_yard_mark_no_show()
        if P.get_bool(self.env, "auto_call_next"):
            self._f3d_yard_auto_call_next()
        return res

    @api.model
    def _f3d_yard_mark_no_show(self):
        limit = fields.Datetime.now() - timedelta(minutes=P.get_int(self.env, "no_show_min"))
        visits = self.sudo().search(
            [("state", "=", "planned"), ("is_no_show", "=", False), ("planned_start", "<", limit)]
        )
        for visit in visits:
            visit.write({"is_no_show": True})
            visit.message_post(body="Фура не приїхала: слот %s минув." % tz.local_hm(visit.planned_start))
        return len(visits)

    @api.model
    def _f3d_yard_auto_call_next(self):
        """Вільні ворота з чергою: «наступний на ворота» (P.auto_call_next)."""
        docks = self.env["stock.location"].sudo().search([("f3d_kind", "=", "dock")], order="f3d_dock_no, id")
        called = 0
        for dock in docks:
            if not self.sudo().search_count([("state", "=", "queued"), ("side", "=", dock.f3d_side)]):
                continue
            try:
                with self.env.cr.savepoint():
                    if self.sudo()._f3d_yard_call_next(dock):
                        called += 1
            except (UserError, ValidationError) as exc:
                _logger.info("auto_call_next %s: %s", dock.f3d_code, exc)
        return called
