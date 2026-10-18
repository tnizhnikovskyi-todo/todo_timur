"""M-14 f3d.viewer.provider.yard: розділ `yard` переглядача (R-20, Додатки B, C)."""

from datetime import timedelta

from odoo import fields, models

from ..tools import params as P
from ..tools import plate as plate_tools
from ..tools import tz
from .f3d_yard_visit import GRP_SEC
from .f3d_yard_visit_kpp import SINCE_FIELD

ACTIVE_STATES = ("arrived", "queued", "at_dock", "handling", "weighed")
ARRIVED_DX = (0.0, -3.5, 3.5)
CARD_CODES = ("GATE-W", "GATE-E", "TRUCK-SCALE")
WEST_QUEUE_X, EAST_QUEUE_X = -26.0, 176.0
DOCK_DX = 7.3


def _fmt_kg(value):
    return "{:,}".format(int(round(value or 0.0))).replace(",", " ")


def _ymdhm(dt):
    return tz.to_local(dt).strftime("%Y-%m-%d %H:%M") if dt else None


def _deep_merge(target, source):
    """Запасний deep_merge (рекурсивне злиття словників, списки — заміна), якщо viewer не встановлено."""
    for key, value in source.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
    return target


class F3dViewerProviderYard(models.AbstractModel):
    _name = "f3d.viewer.provider.yard"  # без _inherit: viewer R-01 п. 3 шукає за префіксом імені
    _description = "3D: двір (фури, КПП, ваги)"
    _f3d_sequence = 160
    _f3d_sections = ("yard",)
    _f3d_group = "factory3d_base.group_f3d_user"

    # ------------------------------------------------------------------ контекст
    def _f3d_ctx(self, ctx):
        user = ctx.get("user")
        if isinstance(user, int):
            user = self.env["res.users"].browse(user)
        user = user or self.env.user
        kiosk = bool(ctx.get("kiosk"))
        sec = bool(user.sudo().has_group(GRP_SEC))
        now = fields.Datetime.now()
        return {
            "user": user,
            "kiosk": kiosk,
            "sec": sec,
            "private": sec and not kiosk,
            "now": now,
            "now_local": ctx.get("now_local") or _ymdhm(now),
            "companies": user.sudo().company_ids,
        }

    # ------------------------------------------------------------------ збирання
    def _f3d_viewer_collect(self, payload, ctx):
        c = self._f3d_ctx(ctx)
        env = self.env
        Gate, Scale = env["f3d.yard.gate"].sudo(), env["f3d.yard.scale"].sudo()
        gates = Gate.search([("active", "=", True), ("company_id", "in", c["companies"].ids)])
        scales = Scale.search([("active", "=", True), ("company_id", "in", c["companies"].ids)])
        scale = scales[:1]
        payload["yard"] = {
            "updated": c["now_local"],
            "gates": {g.f3d_code: self._f3d_gate_node(g, c) for g in gates},
            "scale": {s.f3d_code: self._f3d_scale_node(s, c) for s in scales},
            "trucks": [],
            "queue": {"west": [], "east": []},
            "kpp": {"west": [], "east": []},
            "stats": {},
        }
        yard = payload["yard"]
        yard["trucks"], yard["queue"], yard["kpp"] = self._f3d_trucks(c, gates, scale)
        yard["stats"] = self._f3d_stats(c)
        cards = (payload.get("infra") or {}).get("cards") if isinstance(payload.get("infra"), dict) else None
        if isinstance(cards, dict):
            for code, rows in self._f3d_card_rows(c, gates, scales).items():
                if isinstance(cards.get(code), dict):
                    cards[code]["rows"] = rows

    def _f3d_gate_node(self, gate, c):
        return {
            "name": gate.name,
            "state": gate.state,
            "mode": gate.mode,
            "error": gate.last_error or None,
            "passes_today": gate.passes_today,
            "admitted_today": gate.admitted_today,
            "tailgate_today": gate.tailgate_today,
            "last_plate": (gate.last_plate or None) if c["private"] else None,
            "last_plate_at": _ymdhm(gate.last_plate_at) if c["private"] else None,
            "x": gate.pos_x,
            "y": gate.pos_y,
        }

    def _f3d_scale_node(self, scale, c):
        last = scale.last_weighing_id
        return {
            "weight_kg": scale.last_weight_kg if scale.capture_state != "offline" else None,
            "stable": bool(scale.last_stable),
            "state": scale.capture_state,
            "today": scale.today_count,
            "last": {
                "plate": plate_tools.display_plate(last.plate) if last.plate else None,
                "weight_kg": last.weight_kg,
                "kind": last.kind,
                "picking": last.picking_id.name or None,
                "ts": _ymdhm(last.ts),
            }
            if last
            else None,
            "x": scale.pos_x,
            "y": scale.pos_y,
        }

    # ------------------------------------------------------------------ фури (Додаток B)
    def _f3d_trucks(self, c, gates, scale):
        Visit = self.env["f3d.yard.visit"].sudo()
        now = c["now"]
        dwell = timedelta(seconds=P.get_int(self.env, "scale_dwell_s"))
        visits = Visit.search([("state", "in", ACTIVE_STATES), ("company_id", "in", c["companies"].ids)])
        arrived = visits.filtered(lambda v: v.state == "arrived").sorted(key=lambda v: (v.arrived_at or now, v.id))
        kpp = {"west": [], "east": []}
        arrived_pos = {}
        slots = {}
        for v in arrived:
            gate = v.gate_in_id or v._f3d_yard_default_gate()
            k = slots.get(gate.id, 0)
            slots[gate.id] = k + 1
            kpp[v.side if v.side in kpp else "west"].append(v.name)
            if gate and k < len(ARRIVED_DX):
                arrived_pos[v.id] = (gate.pos_x + ARRIVED_DX[k], gate.pos_y + 8.0, 90)
        queue, queue_pos = {"west": [], "east": []}, {}
        for side in ("west", "east"):
            for k, v in enumerate(Visit._f3d_yard_queue(side).filtered(lambda v: v.id in visits.ids)):
                queue[side].append(v.name)
                if k <= 3:
                    queue_pos[v.id] = ((WEST_QUEUE_X if side == "west" else EAST_QUEUE_X), 9.0 + 16.0 * k, 90)
        scale_pos = (scale.pos_x, scale.pos_y, 90) if scale else None
        out_gates = self.env["f3d.yard.gate"].sudo().search([("direction", "in", ("out", "both"))])
        trucks = []
        for v in visits.sorted(key=lambda v: (v.arrived_at or now, v.id)):
            pos = self._f3d_truck_pos(v, now, dwell, arrived_pos, queue_pos, scale_pos, out_gates)
            x, y, rz = pos if pos else (None, None, None)
            zone = self.env["f3d.zone"].sudo().zone_at(x, y) if x is not None else None
            trucks.append(
                {
                    "visit": v.name,
                    "code": v.scene_code or None,
                    "plate": None if c["kiosk"] else (v.plate_display or None),
                    "state": v.state,
                    "type": v.visit_type,
                    "dock": v.dock_code or None,
                    "picking": v.picking_ids.sorted("name")[:1].name or None,
                    "partner": v.partner_id.name or None,
                    "carrier": v.carrier_id.name or None,
                    "walk_in": bool(v.is_walk_in),
                    "progress": v.progress if v.state in ("at_dock", "handling") else 0.0,
                    "since": _ymdhm(v[SINCE_FIELD[v.state]] or v.arrived_at),
                    "weight_check": v.weight_check,
                    "x": x,
                    "y": y,
                    "rz": rz,
                    "zone": (zone.f3d_code or None) if zone else None,
                }
            )
        return trucks, queue, kpp

    def _f3d_truck_pos(self, v, now, dwell, arrived_pos, queue_pos, scale_pos, out_gates):
        if v.state in ("at_dock", "handling"):
            dock = v.dock_id
            if not dock:
                return None
            if dock.f3d_side == "east":
                return (dock.f3d_x + DOCK_DX, dock.f3d_y, 180)
            return (dock.f3d_x - DOCK_DX, dock.f3d_y, 0)
        if v.state == "arrived":
            return arrived_pos.get(v.id)
        if v.state == "queued":
            last_in = v._f3d_yard_weighings().filtered(lambda w: w.kind == "in")
            if scale_pos and last_in and max(last_in.mapped("ts")) + dwell >= now:
                return scale_pos
            return queue_pos.get(v.id)
        if v.state == "weighed":
            stamp = v.weighed_out_at or v.weighed_in_at
            if scale_pos and stamp and stamp + dwell >= now:
                return scale_pos
            gate = v.gate_out_id or out_gates.filtered(lambda g: g.side == v.side)[:1] or out_gates[:1]
            return (gate.pos_x, gate.pos_y + 8.0, 270) if gate else None
        return None

    # ------------------------------------------------------------------ статистика
    def _f3d_stats(self, c):
        env = self.env
        Visit = env["f3d.yard.visit"].sudo()
        start, end = tz.day_bounds_utc(tz.local_day(c["now"]))
        base = [("company_id", "in", c["companies"].ids)]
        today = lambda f: [(f, ">=", start), (f, "<", end)]  # noqa: E731
        waited = Visit.search(base + today("at_dock_at") + [("wait_min", "!=", False)])
        return {
            "planned_today": Visit.search_count(
                base
                + [("day", "=", tz.local_day(c["now"]))]
                + [("state", "not in", ("draft", "cancelled", "rejected"))]
            ),
            "arrived_today": Visit.search_count(base + today("arrived_at")),
            "on_site": Visit.search_count(base + [("state", "in", ACTIVE_STATES)]),
            "at_dock": Visit.search_count(base + [("state", "in", ("at_dock", "handling"))]),
            "left_today": Visit.search_count(base + today("left_at") + [("state", "=", "left")]),
            "walk_in_today": Visit.search_count(
                base + today("arrived_at") + [("is_walk_in", "=", True), ("state", "!=", "rejected")]
            ),
            "unmatched": env["f3d.yard.lpr.event"].sudo().search_count([("kpp_alert", "=", True)])
            if c["sec"]
            else None,
            "avg_wait_min": round(sum(waited.mapped("wait_min")) / len(waited), 1) if waited else None,
            "weighings_today": env["f3d.yard.weighing"].sudo().search_count(today("ts") + [("state", "!=", "void")]),
        }

    # ------------------------------------------------------------------ infra.cards (R-20 п. 6)
    def _f3d_card_rows(self, c, gates, scales):
        rows = {}
        for gate in gates:
            state_label = dict(gate._fields["state"].selection).get(gate.state, "").lower()
            items = [
                ["Стан", state_label],
                ["Сьогодні проїздів", str(gate.passes_today)],
                ["Режим", "авто" if gate.mode == "auto" else "ручний"],
            ]
            if c["private"] and gate.last_plate:
                items.append(
                    [
                        "Останній номер",
                        "%s · %s" % (plate_tools.display_plate(gate.last_plate), tz.local_hm(gate.last_plate_at))
                        if gate.last_plate_at
                        else plate_tools.display_plate(gate.last_plate),
                    ]
                )
            rows[gate.f3d_code] = items
        for scale in scales:
            last = scale.last_weighing_id
            if scale.capture_state == "offline":
                now_text = "немає даних"
            else:
                now_text = "%s кг · %s" % (
                    _fmt_kg(scale.last_weight_kg),
                    "стабільно" if scale.last_stable else "динамічно",
                )
            rows[scale.f3d_code] = [
                [
                    "Остання машина",
                    "%s · брутто %s кг · %s"
                    % (
                        plate_tools.display_plate(last.plate) if last and last.plate else "—",
                        _fmt_kg(last.weight_kg),
                        (last.picking_id.name if last and last.picking_id else "—"),
                    )
                    if last
                    else "—",
                ],
                ["Сьогодні зважувань", str(scale.today_count)],
                ["Зараз", now_text],
            ]
        return rows

    # ------------------------------------------------------------------ дельта (R-20 п. 7)
    def _f3d_viewer_delta(self, patch, ctx):
        changes = ctx.get("changes") or {}
        if not any(m in changes for m in ("f3d.yard.visit", "f3d.yard.gate", "f3d.yard.scale")):
            return
        full = {}
        self._f3d_viewer_collect(full, ctx)
        patch["yard"] = full["yard"]
        try:
            from odoo.addons.factory3d_viewer.tools.payload import deep_merge
        except ImportError:  # viewer не встановлено: провайдера ніхто не викликає, лише тести
            deep_merge = _deep_merge
        c = self._f3d_ctx(ctx)
        gates = (
            self.env["f3d.yard.gate"].sudo().search([("active", "=", True), ("company_id", "in", c["companies"].ids)])
        )
        scales = (
            self.env["f3d.yard.scale"].sudo().search([("active", "=", True), ("company_id", "in", c["companies"].ids)])
        )
        rows = self._f3d_card_rows(c, gates, scales)
        cards = {code: {"rows": rows[code]} for code in CARD_CODES if code in rows}
        if cards:
            deep_merge(patch.setdefault("infra", {}), {"cards": cards})

    def _f3d_viewer_bus_models(self):
        return ["f3d.yard.visit", "f3d.yard.gate", "f3d.yard.scale"]
