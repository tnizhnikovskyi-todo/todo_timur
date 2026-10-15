import logging
import math
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.factory3d_telemetry.tools.ingest import parse_ts

from ..tools import params as P
from ..tools import tz
from .f3d_yard_visit import GRP_SEC, GRP_STOCK, _f3d_yard_require

_logger = logging.getLogger(__name__)


class F3dYardScale(models.Model):
    _name = "f3d.yard.scale"
    _inherit = ["f3d.scene.mixin", "mail.thread"]
    _description = "Двір: автоваги"
    _order = "f3d_code"
    _rec_name = "name"
    _f3d_kind = "equipment"

    f3d_code = fields.Char(required=True, size=32)
    name = fields.Char(string="Назва", required=True, size=64)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Компанія", required=True, default=lambda s: s.env.company, index=True
    )
    pos_x = fields.Float(string="X, м", digits=(8, 2))
    pos_y = fields.Float(string="Y, м", digits=(8, 2))
    equipment_id = fields.Many2one("maintenance.equipment", string="Обладнання", ondelete="set null")
    zone_id = fields.Many2one("f3d.zone", string="Зона", ondelete="set null")
    source_id = fields.Many2one("f3d.source", string="Джерело", ondelete="set null")
    weight_signal_id = fields.Many2one("f3d.signal", string="Сигнал ваги", ondelete="set null")
    stable_signal_id = fields.Many2one("f3d.signal", string="Сигнал стабільності", ondelete="set null")
    max_kg = fields.Float(string="НПВ, кг", default=60000)
    min_kg = fields.Float(string="НмПВ, кг", default=400)
    division_kg = fields.Float(string="Дискретність, кг", default=20)
    auto_capture = fields.Boolean(string="Автозахоплення", default=True)
    capture_state = fields.Selection(
        [("idle", "Порожньо"), ("settling", "Стабілізація"), ("captured", "Зафіксовано"), ("offline", "Немає даних")],
        string="Стан захоплення",
        required=True,
        default="idle",
        readonly=True,
    )
    last_weight_kg = fields.Float(string="Зараз, кг", digits=(12, 1), readonly=True)
    last_stable = fields.Boolean(string="Стабільно", readonly=True)
    last_ts = fields.Datetime(string="Час показання", readonly=True)
    candidate_kg = fields.Float(readonly=True)
    candidate_ts = fields.Datetime(readonly=True)
    captured_kg = fields.Float(readonly=True)
    last_weighing_id = fields.Many2one("f3d.yard.weighing", string="Останнє зважування", compute="_compute_stats")
    today_count = fields.Integer(string="Зважувань сьогодні", compute="_compute_stats")

    @api.constrains("min_kg", "max_kg", "division_kg")
    def _check_limits(self):
        for scale in self:
            if not (0 < scale.min_kg < scale.max_kg and scale.division_kg > 0):
                raise ValidationError("Межі ваг: 0 < НмПВ < НПВ, дискретність > 0.")

    def _compute_stats(self):
        Weighing = self.env["f3d.yard.weighing"]
        start, end = tz.day_bounds_utc(tz.local_day(fields.Datetime.now()))
        for scale in self:
            base = [("scale_id", "=", scale.id), ("state", "!=", "void")]
            scale.last_weighing_id = Weighing.search(base, limit=1)  # _order = ts desc
            scale.today_count = Weighing.search_count(base + [("ts", ">=", start), ("ts", "<", end)])

    # ------------------------------------------------------------------ показання (M-13)
    @api.model
    def _f3d_yard_dispatch_scales(self, readings):
        """Показання `yard/scale/*` з f3d.signal._f3d_ingest -> scale._f3d_yard_on_readings."""
        scales = self.sudo().search([("active", "=", True)])
        mapping = {}
        for scale in scales:
            if scale.weight_signal_id:
                mapping[scale.weight_signal_id.code] = (scale, "weight")
            if scale.stable_signal_id:
                mapping[scale.stable_signal_id.code] = (scale, "stable")
        groups = {}
        for r in readings:
            target = mapping.get(r.get("code"))
            ts, reason = parse_ts(r.get("ts"))
            if not target or reason:
                continue
            value = r.get("value")
            value = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
            scale, role = target
            groups.setdefault(scale.id, (scale, []))[1].append((role, ts, value, r.get("q") or "good"))
        for scale, items in groups.values():
            items.sort(key=lambda it: it[1])
            scale._f3d_yard_on_readings(items)

    def _f3d_yard_on_readings(self, items):
        """R-10, R-11: items = [(role, ts, value, q)], ts — naive UTC."""
        self.ensure_one()
        self.env.cr.execute("SELECT id FROM f3d_yard_scale WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset()
        by_ts = {}
        for role, ts, value, q in items:
            by_ts.setdefault(ts, {})[role] = (value, q)
        now = fields.Datetime.now()
        for ts in sorted(by_ts):
            self._f3d_yard_on_group(ts, by_ts[ts], now)

    def _f3d_yard_on_group(self, ts, group, now):
        wv, wq = group.get("weight", (None, "bad"))
        if wv is None or wq == "bad" or wv > self.max_kg:
            return  # R-10: ігнорується, стан і last_* не змінюються
        sv, sq = group.get("stable", (None, "bad"))
        stable = (sv >= 0.5) if sv is not None and sq != "bad" else self.last_stable
        newer = not self.last_ts or ts > self.last_ts
        if not newer:
            return  # повтор з буфера колектора
        vals = {"last_weight_kg": wv, "last_stable": stable, "last_ts": ts}
        was_offline = self.capture_state == "offline"
        if was_offline:
            vals["capture_state"] = "idle"
        enabled = P.get_bool(self.env, "read_enabled") and P.get_bool(self.env, "scale_auto_capture")
        capture = None
        if enabled and self.auto_capture:
            capture = self._f3d_yard_step(ts, wv, stable, now, vals, "idle" if was_offline else self.capture_state)
        self.sudo().with_context(tracking_disable=True).write(vals)
        if capture is not None:
            self._f3d_yard_capture(capture, ts)

    def _f3d_yard_step(self, ts, w, stable, now, vals, state):
        """Автомат R-11 п. 2–4; повертає вагу захоплення або None; зміни — у vals."""
        fresh = ts >= now - timedelta(seconds=P.get_int(self.env, "weigh_max_age_s"))
        if w < self.min_kg:
            vals.update(capture_state="idle", candidate_kg=0.0, candidate_ts=False)
            return None
        if not fresh or state == "captured":
            return None
        has_candidate = bool(self.candidate_ts)
        if stable and has_candidate and abs(w - self.candidate_kg) <= 2 * self.division_kg:
            div = self.division_kg
            weight = math.floor((self.candidate_kg + w) / 2 / div + 0.5) * div
            vals.update(capture_state="captured", captured_kg=weight, candidate_kg=0.0, candidate_ts=False)
            return weight
        if stable:
            vals.update(capture_state="settling", candidate_kg=w, candidate_ts=ts)
        else:
            vals.update(capture_state="settling", candidate_kg=0.0, candidate_ts=False)
        return None

    def _f3d_yard_capture(self, weight, ts):
        """R-11 п. 5: призначення зважування рейсу в момент захоплення."""
        self.ensure_one()
        Visit = self.env["f3d.yard.visit"].sudo()
        base = [("weighing_policy", "=", "in_out"), ("company_id", "=", self.company_id.id)]

        def has(visit, kind):
            return visit._f3d_yard_has_weighing(kind)

        def out_pending(visit):
            return has(visit, "in") and not has(visit, "out")

        a_in = Visit.search(base + [("state", "=", "queued"), ("admitted_at", ">=", ts - timedelta(hours=2))])
        a_in = a_in.filtered(lambda v: not has(v, "in"))
        a_ready = Visit.search(base + [("state", "=", "handling"), ("handling_end_at", "!=", False)])
        a_ready = a_ready.filtered(out_pending)
        a_any = Visit.search(base + [("state", "in", ("at_dock", "handling"))]).filtered(out_pending)
        first = a_in | a_ready
        vals = {
            "scale_id": self.id,
            "ts": min(ts, fields.Datetime.now()),
            "weight_kg": weight,
            "stable": True,
            "source": "auto",
            "user_id": False,
        }
        if len(first) == 1:
            vals.update(visit_id=first.id, kind="in" if first in a_in else "out")
        elif not first and len(a_any) == 1:
            vals.update(visit_id=a_any.id, kind="out")
        else:
            vals.update(kind="check", state="unassigned", note="Кандидатів: %s" % len(first | a_any))
        return self.env["f3d.yard.weighing"].sudo().create(vals)

    # ------------------------------------------------------------------ дії
    def action_capture(self, visit=None):
        """Захоплення поточного показання кнопкою «Зважити» (R-10)."""
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC, GRP_STOCK)
        now = fields.Datetime.now()
        age = P.get_int(self.env, "weigh_max_age_s")
        if not (
            self.last_stable
            and self.last_ts
            and now - self.last_ts <= timedelta(seconds=age)
            and self.min_kg <= self.last_weight_kg <= self.max_kg
        ):
            raise UserError("Ваги не дають свіжого стабільного показання — введіть вагу вручну.")
        vals = {
            "scale_id": self.id,
            "ts": self.last_ts,
            "weight_kg": self.last_weight_kg,
            "stable": True,
            "source": "auto",
        }
        if visit:
            kind = "out" if visit._f3d_yard_has_weighing("in") else "in"
            vals.update(visit_id=visit.id, kind=kind)
            return self.env["f3d.yard.weighing"].create(vals)
        weighing = self._f3d_yard_capture(self.last_weight_kg, self.last_ts)
        weighing.write({"user_id": self.env.user.id})
        return weighing

    def _f3d_yard_refresh_offline(self):
        """R-16 п. 6 (викликає крон двору): ваги offline без свіжих даних; свіже показання повертає idle."""
        now = fields.Datetime.now()
        limit = now - timedelta(seconds=3 * P.get_int(self.env, "weigh_max_age_s"))
        for scale in self.search([("active", "=", True)]):
            sig = scale.weight_signal_id
            dead = bool(sig and sig.status in ("stale", "unknown")) or bool(scale.last_ts and scale.last_ts < limit)
            if dead and scale.capture_state != "offline":
                scale.sudo().with_context(tracking_disable=True).write({"capture_state": "offline"})
                scale._f3d_yard_notify()
            elif not dead and scale.capture_state == "offline":
                scale.sudo().with_context(tracking_disable=True).write({"capture_state": "idle"})
                scale._f3d_yard_notify()

    def _f3d_yard_notify(self):
        """R-21: сповіщення шини (реалізує W4)."""
        return True
