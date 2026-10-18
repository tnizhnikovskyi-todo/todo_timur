"""M-04 f3d.yard.lpr.event: подія розпізнавання номера (SPEC R-07, R-08)."""

import base64
import binascii
import logging
import re
from datetime import timedelta

from odoo import api, fields, models, tools
from odoo.exceptions import UserError

from ..tools import params as P
from ..tools import plate as plate_tools
from ..tools import tz
from .f3d_yard_visit import GRP_SEC, _f3d_yard_require

_logger = logging.getLogger(__name__)

CAMERA_RE = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")
DOC_RE = re.compile(r"[A-Z]{2,}/[A-Z]{2,}/\d{3,}")
DATA_URI_RE = re.compile(r"^data:image/[a-z0-9.+-]+;base64,", re.I)
IMAGE_SIGNATURES = (("image/jpeg", "jpg", b"\xff\xd8\xff"), ("image/png", "png", b"\x89PNG"))
OPEN_MATCH = ("unmatched", "low_confidence")


def _str(value, size):
    return str(value).strip()[:size] if value not in (None, False) else ""


class F3dYardLprEvent(models.Model):
    _name = "f3d.yard.lpr.event"
    _description = "Двір: розпізнавання номера"
    _order = "ts desc, id desc"
    _log_access = False
    _rec_name = "plate_norm"
    MATCH = [
        ("matched", "Зіставлено"),
        ("unmatched", "Без бронювання"),
        ("low_confidence", "Низька довіра"),
        ("unknown_camera", "Невідома камера"),
        ("ignored", "Ігноровано (читання вимкнено)"),
        ("handled", "Вирішено охороною"),
        ("expired", "Минув час"),
    ]

    ts = fields.Datetime(string="Час камери", required=True, index=True)
    received_at = fields.Datetime(string="Отримано", required=True, default=fields.Datetime.now)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    push_event_id = fields.Char(string="Подія телеметрії", size=64, index=True)
    dedup_key = fields.Char(string="Ключ дубліката", size=160, required=True)
    camera_code = fields.Char(string="Камера", size=32, required=True, index=True)
    gate_id = fields.Many2one("f3d.yard.gate", string="КПП", index=True, ondelete="set null")
    direction = fields.Selection(
        [("in", "В'їзд"), ("out", "Виїзд"), ("unknown", "Невідомо")], required=True, default="unknown"
    )
    car_state = fields.Selection(
        [("new", "Нова"), ("update", "Оновлення"), ("lost", "Зникла")], required=True, default="new"
    )
    car_id = fields.Char(string="carID", size=32)
    packet_counter = fields.Char(size=32)
    plate_raw = fields.Char(string="Номер (plateText)", size=32)
    plate_unicode = fields.Char(string="Номер (Unicode)", size=32)
    plate_norm = fields.Char(string="Номер", size=16, index=True)
    plate_country = fields.Char(size=8)
    confidence = fields.Float(string="Довіра", digits=(4, 3))
    plate_list = fields.Char(
        string="Список камери",
        size=32,
        help="Назва списку Axis LPV, у який потрапив номер (plateList), напр. f3d_bookings",
    )
    plate_list_mode = fields.Char(string="Режим списку", size=16, help="plateListMode камери: allow / block / none")
    plate_list_description = fields.Char(string="Опис у списку камери", size=256)
    image_attachment_id = fields.Many2one("ir.attachment", string="Знімок", ondelete="set null")
    image_url = fields.Char(string="Посилання на знімок", size=512)
    image = fields.Binary(string="Знімок", related="image_attachment_id.datas")
    match_state = fields.Selection(MATCH, string="Результат", required=True, default="unmatched", index=True)
    visit_id = fields.Many2one("f3d.yard.visit", string="Рейс", index=True, ondelete="set null")
    kpp_alert = fields.Boolean(string="Потрібне рішення охорони", default=False, index=True)
    lost_at = fields.Datetime(string="Зникла з кадру")
    handled_by = fields.Many2one("res.users", ondelete="set null")
    handled_at = fields.Datetime()
    note = fields.Char(string="Пояснення", size=256)

    _f3d_yard_lpr_dedup_uniq = models.Constraint("UNIQUE(dedup_key)", "Подія LPR з таким ключем уже є.")

    def init(self):
        super().init()
        tools.sql.create_index(self.env.cr, "f3d_yard_lpr_event_plate_ts_idx", self._table, ["plate_norm", "ts"])

    # ------------------------------------------------------------------ R-07
    @api.model
    def _f3d_from_push(self, event):
        payload = event.get("payload")
        if not isinstance(payload, dict):
            _logger.warning("f3d_yard: подія LPR %s без тіла-словника", event.get("event_id"))
            return False
        now = fields.Datetime.now()
        camera = _str(payload.get("sensorProviderID"), 64)
        camera_ok = bool(CAMERA_RE.match(camera))
        camera_code = camera if camera_ok else "?"
        gate = (
            self.env["f3d.yard.gate"].sudo().search([("camera_code", "=", camera), ("active", "=", True)], limit=1)
            if camera_ok
            else self.env["f3d.yard.gate"]
        )
        car_id = _str(payload.get("carID"), 32)
        packet = _str(payload.get("packetCounter"), 32)
        key = "%s|%s|%s" % (camera_code, car_id, packet) if car_id and packet else "evt|%s" % event.get("event_id")
        existing = self.search([("dedup_key", "=", key)], limit=1)
        if existing:
            return existing
        notes = []
        ts, reason = self._f3d_lpr_ts(payload, now)
        if reason:
            notes.append("Час камери відкинуто (%s) — узято час прийому" % reason)
            ts = now
        state = payload.get("carState") if payload.get("carState") in ("new", "update", "lost") else "new"
        plate_raw = _str(payload.get("plateText"), 32)
        plate_unicode = _str(payload.get("plateUnicode") or payload.get("plateUTF8"), 32)
        try:
            confidence = min(max(float(payload.get("plateConfidence")), 0.0), 1.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if gate and payload.get("GEOtarget") and _str(payload["GEOtarget"], 64) != gate.f3d_code:
            notes.append("GEOtarget %s ≠ %s" % (_str(payload["GEOtarget"], 64), gate.f3d_code))
        move = payload.get("carMoveDirection")
        direction = (
            move if move in ("in", "out") else ("unknown" if not gate else "out" if gate.direction == "out" else "in")
        )
        vals = {
            "ts": ts,
            "received_at": now,
            "push_event_id": _str(event.get("event_id"), 64),
            "dedup_key": key,
            "camera_code": camera_code,
            "gate_id": gate.id,
            "direction": direction,
            "car_state": state,
            "car_id": car_id,
            "packet_counter": packet,
            "plate_raw": plate_raw,
            "plate_unicode": plate_unicode,
            "plate_norm": plate_tools.normalize_plate(plate_unicode or plate_raw)[:16],
            "plate_country": _str(payload.get("plateCountry"), 8),
            "confidence": confidence,
            "plate_list": _str(payload.get("plateList"), 32),
            "plate_list_mode": _str(payload.get("plateListMode"), 16),
            "plate_list_description": _str(payload.get("plateListDescription"), 256),
            "note": "; ".join(notes)[:256] or False,
        }
        if not camera_ok or not gate:
            vals.update(match_state="unknown_camera", kpp_alert=False)
            return self.create(vals)
        if not P.get_bool(self.env, "read_enabled"):
            vals.update(match_state="ignored", kpp_alert=False)
            return self.create(vals)
        prev = None
        if state == "lost":
            prev = self._f3d_lpr_previous(camera_code, car_id, ts, timedelta(hours=2), lost=True)
            if prev:
                prev._f3d_lpr_on_lost(ts)
                return prev
            vals.update(match_state="ignored", kpp_alert=False)
            return self.create(vals)
        if state == "update":
            prev = self._f3d_lpr_previous(camera_code, car_id, ts, timedelta(minutes=30))
            if prev:
                if confidence > prev.confidence and (plate_unicode or plate_raw):
                    prev.write(
                        {
                            k: vals[k]
                            for k in ("plate_raw", "plate_unicode", "plate_norm", "plate_country", "confidence")
                        }
                    )
                    if prev.match_state in OPEN_MATCH:
                        prev._f3d_match()
                return prev
        rec = self.create(vals)
        if P.get_bool(self.env, "lpr_store_images"):
            rec._f3d_lpr_store_image(payload)
        uri = payload.get("imagesURI")
        uri = uri[0] if isinstance(uri, list) and uri else None
        if isinstance(uri, str) and re.match(r"^https?://", uri) and len(uri) <= 512:
            rec.image_url = uri
        if rec.plate_norm and plate_tools.is_valid_norm(rec.plate_norm):
            gate.sudo().write({"last_plate": plate_unicode or plate_raw, "last_plate_at": ts})
        rec._f3d_match()
        rec._f3d_yard_notify()
        return rec

    @api.model
    def _f3d_lpr_ts(self, payload, now):
        """(ts, причина відкидання) за правилом telemetry R-22."""
        ts = tz.parse_axis_ts(payload.get("capture_timestamp"))
        if ts is None:
            return None, "ts_invalid"
        if ts > now + timedelta(seconds=60):
            return None, "ts_future"
        keep_days = int(self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.keep_days", "30") or 30)
        if ts < now - timedelta(days=keep_days):
            return None, "ts_too_old"
        return ts, None

    @api.model
    def _f3d_lpr_previous(self, camera_code, car_id, ts, delta, lost=False):
        if not car_id:
            return self.browse()
        domain = [
            ("camera_code", "=", camera_code),
            ("car_id", "=", car_id),
            ("car_state", "!=", "lost"),
            ("ts", ">=", ts - delta),
        ]
        return self.search(domain, order="ts desc, id desc", limit=1)

    def _f3d_lpr_on_lost(self, ts):
        self.ensure_one()
        self.lost_at = ts
        if self.kpp_alert and self.match_state in OPEN_MATCH:
            self.write({"match_state": "expired", "kpp_alert": False, "note": "Фура поїхала без рішення"})
        visit = self.visit_id
        if (
            visit
            and self.direction == "out"
            and visit.state != "left"
            and self.gate_id.pending_visit_id == visit
            and visit.state in ("queued", "at_dock", "handling", "weighed")
        ):
            visit.sudo().action_leave(ts, note="виїзд за камерою %s" % self.camera_code)

    def _f3d_lpr_store_image(self, payload):
        self.ensure_one()
        data = payload.get("imageArray")
        while isinstance(data, (list, dict)):
            if isinstance(data, list):
                data = data[0] if data else None
            else:
                data = (
                    data.get("image")
                    or data.get("data")
                    or next((x for x in data.values() if isinstance(x, str)), None)
                )
        if not isinstance(data, str) or not data:
            return
        try:
            raw = base64.b64decode(DATA_URI_RE.sub("", data), validate=True)
        except (binascii.Error, ValueError):
            return self._f3d_yard_event_add_note("Знімок відхилено: формат")
        if len(raw) > P.get_int(self.env, "lpr_image_max_kb") * 1024:
            return self._f3d_yard_event_add_note("Знімок відхилено: розмір")
        found = next(((m, e) for m, e, sig in IMAGE_SIGNATURES if raw.startswith(sig)), None)
        if not found:
            return self._f3d_yard_event_add_note("Знімок відхилено: формат")
        mimetype, ext = found
        att = (
            self.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": "lpr-%s-%s.%s" % (self.camera_code, self.ts.strftime("%Y%m%d-%H%M%S"), ext),
                    "res_model": self._name,
                    "res_id": self.id,
                    "raw": raw,
                    "mimetype": mimetype,
                    "public": False,
                }
            )
        )
        self.image_attachment_id = att.id

    def _f3d_join_note(self, text):
        """Додає пояснення до наявного (без дублювання)."""
        if not self.note or text in self.note:
            return text if not self.note else self.note
        return ("%s; %s" % (self.note, text))[:256]

    def _f3d_yard_event_add_note(self, text):
        self.note = self._f3d_join_note(text)

    def _f3d_yard_notify(self):
        """R-21: сповіщення шини (реалізує W4); у W2 — нічого."""
        return True

    # ------------------------------------------------------------------ R-08
    def _f3d_match(self):
        for event in self:
            event._f3d_match_one()
        return True

    def _f3d_match_one(self):
        self.ensure_one()
        if not plate_tools.is_valid_norm(self.plate_norm):
            return self.write(
                {"match_state": "low_confidence", "note": self._f3d_join_note("Номер не розпізнано"), "kpp_alert": True}
            )
        min_conf = P.get_float(self.env, "lpr_min_confidence")
        if self.confidence < min_conf:
            return self.write(
                {
                    "match_state": "low_confidence",
                    "note": self._f3d_join_note("Довіра %.2f < %.2f" % (self.confidence, min_conf)),
                    "kpp_alert": True,
                }
            )
        Visit = self.env["f3d.yard.visit"].sudo()
        direction = self.direction if self.direction in ("in", "out") else "in"
        found = Visit._f3d_yard_find_by_plate(self.plate_norm, direction, self.ts)
        tokens = DOC_RE.findall(self.plate_list_description or "")
        doc_visits = Visit._f3d_yard_find_by_docs(tokens, direction, self.ts) if tokens else Visit
        visit, note, alert = Visit, False, False
        if len(found) == 1:
            visit = found
        elif len(found) > 1:
            both = found & doc_visits
            if len(both) == 1:
                visit = both
            else:
                visit = found[:1]
                note, alert = "Кілька рейсів з номером %s — обрано %s" % (self.plate_norm, visit.name), True
        elif len(doc_visits) == 1:
            visit = doc_visits
            camera_plate = self.plate_unicode or self.plate_raw
            if not visit.plate:
                visit.write({"plate": camera_plate})
                visit.message_post(body="Номер заповнено з камери %s" % self.camera_code)
            elif visit.plate_norm != self.plate_norm:
                note, alert = "Номер камери %s ≠ номер рейсу %s" % (camera_plate, visit.plate), True
        if not visit:
            return self.write(
                {
                    "match_state": "unmatched",
                    "kpp_alert": True,
                    "note": self._f3d_join_note(
                        "Фура виїжджає без рейсу" if direction == "out" else "Номер не знайдено серед рейсів"
                    ),
                }
            )
        vals = {"visit_id": visit.id, "match_state": "matched", "kpp_alert": alert}
        if note:
            vals["note"] = self._f3d_join_note(note)
        self.write(vals)
        gate = self.gate_id
        if direction == "in":
            if visit.state in ("draft", "planned"):
                visit.action_arrive(self.ts, gate, self)
            else:
                self._f3d_yard_event_add_note("Повторне розпізнавання")
            if not self.kpp_alert and gate:
                gate._f3d_yard_auto_open(visit, self)
        else:
            visit.write({"gate_out_id": gate.id})
            if not self.kpp_alert and gate:
                gate._f3d_yard_auto_open(visit, self)
        return True

    # ------------------------------------------------------------------ дії охорони
    def action_walk_in(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        if self.match_state not in OPEN_MATCH or self.direction == "out":
            raise UserError("Рейс без броні можна створити лише для нерозпізнаного в'їзду.")
        return {
            "type": "ir.actions.act_window",
            "name": "Рейс без броні",
            "res_model": "f3d.yard.walkin.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_event_id": self.id},
        }

    def action_link_visit(self, visit_id):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        Visit = self.env["f3d.yard.visit"]
        visit = visit_id if isinstance(visit_id, models.BaseModel) else Visit.browse(visit_id)
        outbound = self.direction == "out"
        allowed = (
            ("queued", "at_dock", "handling", "weighed") if outbound else ("draft", "planned", "arrived", "queued")
        )
        if visit.state not in allowed:
            raise UserError("Рейс у цьому стані не можна прив'язати до події.")
        self.write(
            {
                "visit_id": visit.id,
                "match_state": "handled",
                "kpp_alert": False,
                "handled_by": self.env.uid,
                "handled_at": fields.Datetime.now(),
            }
        )
        if not visit.plate:
            visit.sudo().write({"plate": self.plate_unicode or self.plate_raw})
        if outbound:
            visit.sudo().write({"gate_out_id": self.gate_id.id})
        elif visit.state in ("planned", "draft"):
            visit.action_arrive(self.ts, self.gate_id or None, self)
            self.sudo().write({"match_state": "handled"})
        return True

    def action_dismiss(self):
        _f3d_yard_require(self.env, GRP_SEC)
        for event in self:
            vals = {"kpp_alert": False, "handled_by": self.env.uid, "handled_at": fields.Datetime.now()}
            if event.match_state in OPEN_MATCH:
                vals["match_state"] = "handled"
            event.write(vals)
        return True

    def action_reject(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        return {
            "type": "ir.actions.act_window",
            "name": "Відхилити",
            "res_model": "f3d.yard.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_event_id": self.id},
        }

    # ------------------------------------------------------------------ крон (R-07 п. 10)
    @api.model
    def _cron_expire(self):
        limit = fields.Datetime.now() - timedelta(minutes=P.get_int(self.env, "arrival_timeout_min"))
        stale = self.sudo().search(
            [("kpp_alert", "=", True), ("match_state", "in", OPEN_MATCH), ("received_at", "<", limit)]
        )
        stale.write({"match_state": "expired", "kpp_alert": False})
        return len(stale)
