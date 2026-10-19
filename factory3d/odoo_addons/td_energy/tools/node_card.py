"""W1-A: картка вузла (R-30, API-07): блоки за видом вузла, графік струму, відгалуження, облік, захист, події."""

import math
from datetime import timedelta

from odoo.exceptions import UserError

from . import dates, forecast, live, sld
from .dashboard import rel_time
from .sld import fmt, rnd

FULL_KINDS = ("line",)
PLAN_KINDS = ("line", "cell", "transformer", "section", "switchboard")
MODEL_LABELS = {
    "pm5560": "Schneider PM5560",
    "sun2000": "Huawei SUN2000",
    "luna2000": "Huawei LUNA2000",
    "tedom": "TEDOM ProCon",
    "other": "Інший",
}
LINE_KIND_LABELS = {"busway": "Шинопровід", "cable": "Кабелі"}
SQRT3 = math.sqrt(3)
PLAN_STATES = {"draft": "чернетка", "pending": "на узгодженні", "approved": "узгоджено"}


def _amps(kw, cos, volts=380.0):
    if kw is None or not cos:
        return None
    return kw * 1000.0 / (SQRT3 * volts * cos)


class NodeCard:
    def __init__(self, env, snap, code, hooks=None, cost=False):
        self.env, self.snap, self.hooks, self.cost = env, snap, hooks, cost
        self.sudo = env(su=True)
        row = snap.by_code.get(code)
        if not row:
            raise UserError(env._("Невідомий вузол: %s.", code))
        self.row, self.code = row, code
        self.now = snap.now
        self.today = dates.local_day(self.now)
        self.day0 = dates.local_day_bounds(self.today)[0]
        self.now_slot = forecast.day_start_slot(self.now)
        self.kind = row["kind"]
        self.full = self.kind == "line" or (self.kind == "cell" and row["cell_type"] in ("feeder", "cable"))

    # --- допоміжні вибірки --------------------------------------------------------------------------
    @property
    def subtree(self):
        return self.snap.descendants(self.row)

    @property
    def consumers(self):
        return self.snap.consumers_state(self.row)

    def breaker(self):
        """Шафа-автомат вузла: для лінії — батько-`cell`; для `cell` — він сам."""
        snap, row = self.snap, self.row
        if row["kind"] == "cell":
            return row
        parent = snap.nodes.get(row["parent"])
        return parent if parent and parent["kind"] == "cell" else None

    def card_meter(self):
        """Лічильник блоку: власний, лічильник шафи лінії або лічильник ввідної шафи трансформатора."""
        snap, row = self.snap, self.row
        meter = snap.meter_of(row)
        if meter is None and row["kind"] == "transformer":
            for child in snap.children.get(row["id"], []):
                if child["kind"] == "cell" and child["cell_type"] == "incomer":
                    return snap.meters.get(child["id"])
        return meter

    def signal_prefix(self):
        """`energy/lines/<L>` для лінії (і її шафи), `energy/cells/<Q>` для ввідної шафи, `None` для решти."""
        row = self.row
        if row["kind"] == "line":
            return "energy/lines/%s" % row["code"]
        if row["kind"] == "cell":
            if row["cell_type"] == "incomer":
                return "energy/cells/%s" % row["code"]
            line = next((c for c in self.snap.children.get(row["id"], []) if c["kind"] == "line"), None)
            return "energy/lines/%s" % line["code"] if line else None
        return None

    def rating_a(self):
        row = self.row
        if row["kind"] == "transformer" and row["rating_kva"]:
            return rnd(row["rating_kva"] / (SQRT3 * 0.4))
        if row["kind"] == "cell" and row["cell_type"] != "incomer":
            line = next((c for c in self.snap.children.get(row["id"], []) if c["kind"] == "line"), None)
            return (line or row)["rating_a"] or row["rating_a"]
        return row["rating_a"]

    def power_kw(self):
        v, row = self.snap.v, self.row
        if row["kind"] == "transformer":
            return v("energy/transformers/%s/p_kw" % row["code"])
        if row["kind"] == "consumer":
            return v("energy/consumers/%s/p_now" % row["code"])
        prefix = self.signal_prefix()
        return v(prefix + "/p_now") if prefix else None

    def cos_phi(self):
        v, row = self.snap.v, self.row
        if row["kind"] == "transformer":
            cos = v("energy/transformers/%s/cos_phi" % row["code"])
        else:
            prefix = self.signal_prefix()
            cos = live.pf_to_cos(v(prefix + "/cos_phi")) if prefix else None
        return cos if cos else (self.row.get("cos_phi_nominal") or 0.9)

    def current_a(self):
        v, row = self.snap.v, self.row
        if row["kind"] == "transformer":
            return v("energy/transformers/%s/i_a" % row["code"])
        prefix = self.signal_prefix()
        if not prefix:
            return None
        a = v(prefix + "/i_now")
        if a is None:
            a = _amps(self.power_kw(), self.cos_phi())  # R-16 п. 6 (DEC-15)
        return a

    def p_inst(self):
        if self.row["kind"] == "consumer":
            return self.row["p_inst_kw"] or 0.0
        return sum(n["p_inst_kw"] or 0.0 for n in self.subtree if n["kind"] == "consumer")

    # --- блоки -------------------------------------------------------------------------------------------
    def header(self):
        snap, row = self.snap, self.row
        path = self._path()
        state = snap.state(row)
        chips = []
        if state == "alarm":
            chips.append({"text": "Тривога", "state": "alarm"})
        elif state == "off":
            chips.append({"text": "Знеструмлено або резерв", "state": "off"})
        else:
            chips.append({"text": "Під напругою", "state": "ok"})
        if row["kind"] == "line":
            parent = snap.nodes.get(row["parent"])
            label = LINE_KIND_LABELS.get(row["line_kind"], "Лінія")
            text = "%s %s А · живиться від %s" % (label, fmt(row["rating_a"]), (parent or row)["code"])
            chips.append({"text": text, "state": "ok"})
        meter = self.card_meter()
        if meter:
            ok = meter["data_state"] == "ok"
            chips.append(
                {
                    "text": "Лічильник %s %s" % (meter["code"], "на зв'язку" if ok else "не на зв'язку"),
                    "state": "ok" if ok else "alarm",
                }  # fmt: skip
            )
        kind_label = dict(self.sudo["td.energy.node"]._fields["kind"].selection).get(row["kind"], row["kind"])
        if row["kind"] == "line":
            kind_label = "%s %s А" % (LINE_KIND_LABELS.get(row["line_kind"], "Лінія"), fmt(row["rating_a"]))
        return {
            "code": row["code"],
            "name": row["name"],
            "kind": row["kind"],
            "kind_label": kind_label,
            "path": path,
            "chips": chips,
            "can_3d": bool(row["equipment"]),
        }

    def _path(self):
        snap, row = self.snap, self.row
        chain = [row]
        for anc in snap.ancestors(row):
            chain.append(anc)
            if anc["kind"] in ("section", "switchboard"):
                break
            if row["kind"] == "transformer" and anc["kind"] == "substation":
                break
        chain.reverse()
        if row["kind"] != "transformer" and not any(n["kind"] == "switchboard" for n in chain):
            cabinet = next((snap.nodes.get(n["cabinet"]) for n in chain if n["cabinet"]), None)
            if cabinet and cabinet["kind"] == "switchboard":
                chain.insert(0, cabinet)
        return [{"code": n["code"], "name": n["name"]} for n in chain]

    def kpis(self):
        v, row = self.snap.v, self.row
        out = {}
        if self.kind in ("line", "cell", "transformer"):
            a = self.current_a()
            rating = self.rating_a()
            phases = None
            prefix = self.signal_prefix()
            if prefix and row["kind"] != "transformer":
                ph = [v("%s/i_%s" % (prefix, x)) for x in "abc"]
                phases = [rnd(p) if p is not None else None for p in ph] if any(p is not None for p in ph) else None
            out["current"] = {
                "a": rnd(a) if a is not None else None,
                "pct": rnd(a / rating * 100) if a is not None and rating else None,
                "phases": phases,
                "rating_a": rating,
            }
        if self.kind in ("line", "cell", "transformer", "consumer", "tapoff"):
            kw = self.power_kw()
            out["power"] = {
                "kw": rnd(kw) if kw is not None else None,
                "p_inst_kw": rnd(self.p_inst()),
                "cos_phi": round(self.cos_phi(), 2),
            }
            out["energy"] = self._energy()
        if self.kind in ("line", "cell", "transformer"):
            out["peak"] = self._peak()
        if self.full:
            out["idle"] = self._idle()
        return out

    def _energy(self):
        meter_row = self.card_meter() if self.kind != "tapoff" else None
        if self.kind == "consumer":
            meter_row = self.snap.meters.get(self.row["id"])
        kwh = None
        cost = 0.0
        if meter_row:
            meter = self.sudo["td.energy.meter"].browse(meter_row["id"])
            value, quality = meter._td_kwh(self.day0, self.now) if self.now > self.day0 else (0.0, "missing")
            kwh = value
            if quality == "missing":  # без показань лічильника (демо-історія R-36) — сума інтервалів доби
                self.env.cr.execute(
                    "SELECT SUM(kwh) FROM td_energy_interval WHERE meter_id = %s AND ts_start >= %s AND ts_start < %s"
                    " AND quality <> 'missing'",
                    (meter.id, self.day0, self.now),
                )
                total = self.env.cr.fetchone()[0]
                kwh = float(total) if total is not None else kwh
            self.env.cr.execute(
                "SELECT COALESCE(SUM(cost), 0) FROM td_energy_interval WHERE meter_id = %s AND ts_start >= %s",
                (meter.id, self.day0),
            )
            cost = self.env.cr.fetchone()[0]
        out = {"kwh": rnd(kwh) if kwh is not None else None, "orders": self._orders_count()}
        if self.cost:
            out["cost_uah"] = rnd(cost)
        return out

    def _orders_count(self):
        workcenters = {n["workcenter"] for n in self.subtree + [self.row] if n["workcenter"]}
        if not workcenters:
            return 0
        groups = self.sudo["td.energy.alloc"]._read_group(
            [("day", "=", self.today), ("workcenter_id", "in", list(workcenters)), ("production_id", "!=", False)],
            ["production_id"],
            ["__count"],
        )
        return len(groups)

    def _chart_values(self):
        """R-30 п. 9: `a[s] = kw_avg·1000/(√3·380·cos)` для слотів до `now_slot`; без лічильника — Σ споживачів."""
        cr = self.env.cr
        meter = self.card_meter()
        cos = self.cos_phi()
        volts = 400.0 if self.kind == "transformer" else 380.0
        values = [None] * forecast.SLOTS
        if meter:
            cr.execute(
                "SELECT ts_start, kw_avg FROM td_energy_interval"
                " WHERE meter_id = %s AND ts_start >= %s AND ts_start < %s",
                (meter["id"], self.day0, dates.floor15(self.now)),
            )
            rows = cr.fetchall()
        else:
            ids = [self.snap.meters[n["id"]]["id"] for n in self.subtree if n["id"] in self.snap.meters]
            if not ids:
                return values
            cr.execute(
                "SELECT ts_start, SUM(kw_avg) FROM td_energy_interval WHERE meter_id IN %s AND ts_start >= %s"
                " AND ts_start < %s GROUP BY ts_start",
                (tuple(ids), self.day0, dates.floor15(self.now)),
            )
            rows = cr.fetchall()
        for ts, kw in rows:
            values[forecast.local_slot_index(ts)] = _amps(kw, cos, volts)
        return values

    def chart(self):
        a = self._chart_values()
        rating = self.rating_a()
        peak_a, peak_slot = None, None
        for s, x in enumerate(a):
            if x is not None and (peak_a is None or x > peak_a):
                peak_a, peak_slot = x, s
        return {
            "step_min": 15,
            "now_slot": self.now_slot,
            "a": [None if x is None else round(x, 1) for x in a],
            "warn_a": rnd(0.8 * rating) if rating else None,
            "rating_a": rating,
            "peak": {"a": rnd(peak_a) if peak_a is not None else None, "slot": peak_slot},
        }

    def _peak(self):
        a = self._chart_values()
        peak_a, slot = None, None
        for s, x in enumerate(a):
            if x is not None and (peak_a is None or x > peak_a):
                peak_a, slot = x, s
        live_a = self.current_a()
        if live_a is not None and (peak_a is None or live_a > peak_a):
            peak_a, slot = live_a, self.now_slot
        rating = self.rating_a()
        time = None
        if slot is not None:
            time = "%02d:%02d" % (slot // 4, slot % 4 * 15)
        return {"a": rnd(peak_a) if peak_a is not None else None, "time": time,
                "warn_a": rnd(0.8 * rating) if rating else None}  # fmt: skip

    def _idle(self):
        names, kw = [], 0.0
        for code, (st, p, _n) in sorted(self.consumers.items()):
            if st in ("idle", "mnt"):
                kw += p
                names.append(code)
        return {"kw": round(kw, 1), "names": names[:5]}

    def taps(self):
        snap = self.snap
        consumers = []
        for child in snap.children.get(self.row["id"], []):
            if child["kind"] == "tapoff":
                for c in snap.children.get(child["id"], []):
                    if c["kind"] == "consumer":
                        consumers.append((child["code"], c))
            elif child["kind"] == "consumer":
                consumers.append((child["code"], child))
        wcs = [c["workcenter"] for _t, c in consumers if c["workcenter"]]
        jobs = {}
        if wcs and "mrp.workorder" in self.env:
            for wo in self.sudo["mrp.workorder"].search(
                [("state", "=", "progress"), ("workcenter_id", "in", wcs)], order="id desc"
            ):
                jobs[wo.workcenter_id.id] = "%s · %s" % (wo.production_id.name, wo.name)
        rows, total = [], 0.0
        for tap, c in consumers:
            p = snap.v("energy/consumers/%s/p_now" % c["code"])
            inst = c["p_inst_kw"] or 0.0
            if c["equipment"] and c["equipment"] in snap.corrective_eq:
                state, job = "mnt", "заявка ТО · %s" % snap.corrective_name.get(c["equipment"], "")
            elif p is None or (inst and p < 0.05 * inst):
                state, job = "idle", "немає завдання"
            else:
                state = "run"
                job = jobs.get(c["workcenter"]) or ("—" if not c["workcenter"] else "немає завдання")
            total += p or 0.0
            rows.append(
                {
                    "tap": tap,
                    "code": c["code"],
                    "name": c["name"],
                    "inst_kw": rnd(inst),
                    "now_kw": round(p, 1) if p is not None else None,
                    "state": state,
                    "job": job,
                    "node_code": c["code"],
                }
            )
        power = self.power_kw()
        return {
            "sum_kw": round(total, 1),
            "aux_kw": round((power or 0.0) - total, 1),
            "count": len(rows),
            "rows": rows,
        }

    def meter(self):
        meter_row = self.card_meter()
        if not meter_row:
            return None
        meter = self.sudo["td.energy.meter"].browse(meter_row["id"])
        signal = meter.e_import_signal_id
        balance = self.sudo["td.energy.balance"].search(
            [("node_id", "=", meter.node_id.id), ("state", "in", ("ok", "deviation"))], order="hour desc", limit=1
        )
        pct = None
        if balance:
            denom = max(abs(balance.measured_kwh), abs(balance.expected_kwh))
            pct = round((balance.measured_kwh - balance.expected_kwh) / denom * 100, 1) if denom else 0.0
        return {
            "code": meter.code,
            "model": MODEL_LABELS.get(meter.model, meter.model),
            "ct_ratio": meter.ct_ratio or None,
            "last_ts": dates.to_local(signal.last_ts).strftime("%H:%M:%S") if signal.last_ts else None,
            "last_kwh": rnd(signal.last_value) if signal.last_ts and signal.last_value is not None else None,
            "next_verification": meter.next_verification.isoformat() if meter.next_verification else None,
            "balance_pct": pct,
        }

    def protection(self):
        snap = self.snap
        breaker = self.breaker()
        if not breaker:
            return None
        node = self.sudo["td.energy.node"].browse(breaker["id"])
        rating = breaker["rating_a"] or self.row["rating_a"]
        ratio = breaker["protection_ir_ratio"] or 0.0
        equipment = [e for e in (breaker["equipment"], self.row["equipment"]) if e]
        planned = [snap.planned[e] for e in equipment if e in snap.planned]
        thermo = min(planned, key=lambda r: r["schedule_date"]) if planned else None
        thermography = None
        if thermo:
            date = dates.to_local(thermo["schedule_date"]).strftime("%Y-%m-%d")
            thermography = {"date": date, "state": "Заплановано"}
        return {
            "breaker": breaker["code"],
            "rating_a": rating,
            "trip_unit": breaker["protection_trip_unit"] or None,
            "ir": {"ratio": ratio or None, "a": rnd(ratio * rating) if ratio and rating else None},
            "trips_year": node.trip_count_year,
            "thermography": thermography,
        }

    def events(self, limit=6):
        env = self.sudo
        since = self.now - timedelta(days=7)
        rows = []
        for ev in env["td.energy.event"].search(
            [("node_id", "child_of", self.row["id"]), ("ts", ">=", since)], order="ts desc, id desc", limit=limit
        ):
            rows.append((ev.ts, {"time": rel_time(ev.ts, self.now), "text": ev.text, "kind": ev.kind}))
        equipment = [n["equipment"] for n in self.subtree + [self.row] if n["equipment"]]
        if equipment:
            Request = env["maintenance.request"]
            for r in Request.search(
                [("equipment_id", "in", equipment), ("create_date", ">=", since)], order="create_date desc", limit=limit
            ):
                rows.append(
                    (
                        r.create_date,
                        {
                            "time": rel_time(r.create_date, self.now),
                            "kind": "request",
                            "text": "%s переведено в ТО" % (r.equipment_id.td_code or r.equipment_id.name),
                        },
                    )  # fmt: skip
                )
            for r in Request.search(
                [("equipment_id", "in", equipment), ("stage_id.done", "=", True), ("close_date", "!=", False)],
                order="id desc", limit=limit,
            ):  # fmt: skip
                closed = r.close_date
                if closed and closed >= since.date():
                    ts = fields_to_dt(closed)
                    text = "Заявку закрито: %s" % r.name
                    rows.append((ts, {"time": rel_time(ts, self.now), "kind": "request", "text": text}))
        rows.sort(key=lambda x: x[0], reverse=True)
        return [item for _ts, item in rows[:limit]]

    def maintenance(self, limit=6):
        snap = self.snap
        equipment = [n["equipment"] for n in self.subtree + [self.row] if n["equipment"]]
        if not equipment:
            return []
        out = []
        for r in self.sudo["maintenance.request"].search(
            [("equipment_id", "in", equipment), ("stage_id.done", "=", False)], order="create_date desc", limit=limit
        ):
            planned = r.maintenance_type == "preventive" and r.schedule_date and r.schedule_date >= snap.now
            if planned:
                state, when = "План", dates.to_local(r.schedule_date).strftime("%d.%m %H:%M")
            else:
                state = r.stage_id.name
                when = state.lower()
            out.append({"title": r.name, "when": when, "state": state, "id": r.id})
        return out[:limit]

    def outage(self):
        if self.kind not in PLAN_KINDS:
            return None
        plan = self.sudo["td.energy.outage.plan"].search(
            [("node_id", "=", self.row["id"]), ("state", "in", ("pending", "approved")), ("end", ">=", self.now)],
            order="start", limit=1,
        )  # fmt: skip
        if not plan:
            return None
        return {
            "plan_id": plan.id,
            "when": plan._td_when(),
            "reason": plan._td_reason_label(),
            "orders": plan.production_count,
            "state": plan.state,
            "state_label": PLAN_STATES.get(plan.state, plan.state),
        }

    # --- збирання ----------------------------------------------------------------------------------------
    def build(self):
        out = {"node": self.header()}
        if self.kind in ("line", "transformer", "consumer", "tapoff") or self.full:
            out["kpis"] = self.kpis()
        if self.kind == "transformer" or self.full:
            out["chart"] = self.chart()
        if self.full:
            out["taps"] = self.taps()
        if self.kind == "transformer" or self.full:
            meter = self.meter()
            if meter:
                out["meter"] = meter
        if self.full:
            protection = self.protection()
            if protection:
                out["protection"] = protection
        out["events"] = self.events()
        out["maintenance"] = self.maintenance()
        if self.kind in PLAN_KINDS:
            out["outage"] = self.outage()
        out["extra"] = self.hooks._td_node_card_extra(self.sudo["td.energy.node"].browse(self.row["id"])) or {}
        return out


def fields_to_dt(day):
    """`Date` → `datetime` (початок доби UTC наближено)."""
    from datetime import datetime, time

    return datetime.combine(day, time(12, 0))


def card(env, snap, code, hooks, cost):
    return NodeCard(env, snap, code, hooks, cost).build()


__all__ = ["NodeCard", "card", "sld"]
