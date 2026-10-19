"""R-05: побудова 15-хв слотів ресурсів (крон), ціна й вартість (R-02), параметри `td.energy_resources.*`.

`SlotBuilder(env, now).build_all()` — порядок усередині прогону: `counter`/`flow_integrate` (і `metric='react'` вводів)
→ `load_share`/`schedule`/`gate_loss` → `residual`. Запис — `INSERT … ON CONFLICT (meter_id, metric, ts_start)
DO UPDATE … WHERE NOT is_backfill`: синтетичні рядки живими даними не перезаписуються (стик «історія / живі»).
`CostModel` ділять крон і backfill (`tools/backfill_resources.py`).
"""

import logging
import math
from bisect import bisect_left, bisect_right
from datetime import timedelta

from odoo import fields

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy.tools.dates import SLOT, param_float

from . import estimate, integrate

_logger = logging.getLogger(__name__)

PARAM = "td.energy_resources."
MAX_SLOTS = 192
BATCH = 5000
INSERT_SQL = """
INSERT INTO td_energy_res_interval (meter_id, resource_id, point_id, metric, ts_start, ts_end, day, hour_local, qty,
    rate_avg, kwh_eq, price, cost, quality, built_at, is_backfill)
VALUES %s
ON CONFLICT (meter_id, metric, ts_start) DO UPDATE SET resource_id = EXCLUDED.resource_id,
    point_id = EXCLUDED.point_id, qty = EXCLUDED.qty, rate_avg = EXCLUDED.rate_avg, kwh_eq = EXCLUDED.kwh_eq,
    price = EXCLUDED.price, cost = EXCLUDED.cost, quality = EXCLUDED.quality, built_at = EXCLUDED.built_at
WHERE td_energy_res_interval.is_backfill = false
"""
BACKFILL_INSERT_SQL = INSERT_SQL.split("ON CONFLICT")[0] + "ON CONFLICT (meter_id, metric, ts_start) DO NOTHING"
DEFAULTS = {
    "boiler_eff": 0.91,
    "gap_max_s": 900.0,
    "min_coverage": 0.3,
    "night_from_h": 23.0,
    "night_to_h": 6.5,
    "weeks_per_month": 4.33,
}


def rparam(env, name, default=None):
    """Параметр `td.energy_resources.<name>` (рядок) або `default`."""
    val = env["ir.config_parameter"].sudo().get_param(PARAM + name)
    return default if val in (None, False, "") else val


def rparam_float(env, name, default=None):
    default = DEFAULTS.get(name, 0.0) if default is None else default
    try:
        return float(rparam(env, name, default))
    except (TypeError, ValueError):
        return default


def rparam_bool(env, name, default=False):
    val = rparam(env, name)
    return default if val is None else str(val).strip().lower() in ("1", "true", "yes", "on")


def react_stats(q_kvarh, p_kwh, tg_limit=0.0, rate=0.0):
    """R-06: `tg φ = Q/P`, `cos φ = 1/√(1+tg²)`; «ризик доплати» (D-44) — `tg_limit > 0` і `tg φ` вищий;
    `excess = max(0, Q − tg_limit·P)`, `penalty = excess × rate`. `P ≤ 0` — `tg`/`cos` = `None`."""
    if not p_kwh or p_kwh <= 0:
        return {"tg": None, "cos": None, "risk": False, "excess": 0.0, "penalty": 0.0}
    tg = q_kvarh / p_kwh
    risk = tg_limit > 0 and tg > tg_limit
    excess = max(0.0, q_kvarh - tg_limit * p_kwh) if tg_limit > 0 else 0.0
    return {
        "tg": tg,
        "cos": 1.0 / math.sqrt(1.0 + tg * tg),
        "risk": risk,
        "excess": excess,
        "penalty": round(excess * rate, 2) if risk else 0.0,
    }


def slot_fields(ts):
    """`(ts_end, day, hour_local)` слота, що починається в `ts` (Київ)."""
    local = dates.to_local(ts)
    return ts + SLOT, local.date(), local.hour


def window_points(points, lo, hi):
    """Зріз відсортованого ряду `[(ts, value)]` на `[lo, hi]` (бісекція за часом)."""
    keys = [t for t, _v in points]
    return points[bisect_left(keys, lo) : bisect_right(keys, hi)]


def load_points(env, signal, lo, hi):
    """Показання `td.reading` сигналу (`quality != bad`) у `[lo, hi]`, плюс `last_value`, якщо він у вікні."""
    signal = signal.sudo()
    rows = (
        env["td.reading"]
        .sudo()
        .search_read(
            [("signal_id", "=", signal.id), ("quality", "!=", "bad"), ("ts", ">=", lo), ("ts", "<=", hi)],
            ["ts", "value"],
            order="ts",
        )
    )
    points = {r["ts"]: r["value"] for r in rows if r["value"] is not None}
    if signal.last_ts and lo <= signal.last_ts <= hi and signal.last_quality != "bad" and signal.last_value is not None:
        points.setdefault(signal.last_ts, signal.last_value)
    return sorted(points.items())


class CostModel:
    """R-01, R-02: `kwh_eq`, ціна й вартість слота ресурсу. Кеші на прогін (ціна — на місцеву дату)."""

    def __init__(self, env):
        self.env = env
        self.price_model = env["td.energy.price"].sudo()
        self._price = {}
        self._el_cost = {}  # (node_id, ts) → Σ cost `td.energy.interval` role=consumer

    def price(self, resource, local_date, company=None):
        key = (resource.id, local_date, company.id if company else 0)
        if key not in self._price:
            self._price[key] = self.price_model._td_price_at(resource, local_date, company=company)
        return self._price[key]

    def load_el_costs(self, node_ids, since, until):
        """Вартість електрики вузлів `cost_node_id` (R-02 п. 4) за `[since, until)` — одним запитом."""
        node_ids = [n for n in set(node_ids) if n]
        if not node_ids:
            return
        self.env.cr.execute(
            """SELECT node_id, ts_start, SUM(cost) FROM td_energy_interval
                WHERE role = 'consumer' AND node_id IN %s AND ts_start >= %s AND ts_start < %s
                GROUP BY node_id, ts_start""",
            (tuple(node_ids), since, until),
        )
        for node_id, ts, cost in self.env.cr.fetchall():
            self._el_cost[(node_id, ts)] = cost or 0.0

    def finish(self, resource, point, ts, qty):
        """`(kwh_eq, price, cost)` слота: `price`/`derived_gas` — ціна × кількість; `derived_el` — вартість
        електрики вузла `cost_node_id` (R-02 п. 4); `tariff`/`none` — 0."""
        kwh_eq = resource._td_kwh_eq(qty)
        source = resource.price_source
        if source in ("price", "derived_gas"):
            price = self.price(resource, dates.local_day(ts), point.company_id if point else None)
            return kwh_eq, price, round(qty * price, 2)
        if source == "derived_el" and point and point.cost_node_id:
            cost = round(self._el_cost.get((point.cost_node_id.id, ts), 0.0), 2)
            return kwh_eq, (cost / qty if qty > 0 else 0.0), cost
        return kwh_eq, 0.0, 0.0


def write_rows(env, rows, sql=INSERT_SQL):
    """Пакетний запис кортежів у `td_energy_res_interval`; повертає `(attempted, affected)`."""
    attempted = affected = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        env.cr.execute_values(sql, chunk, page_size=len(chunk))
        attempted += len(chunk)
        affected += env.cr.rowcount
    return attempted, affected


class SlotBuilder:
    """R-05 п. 1–7. `build_all()` → кількість записаних слотів; збій лічильника ізольується `savepoint`."""

    def __init__(self, env, now=None):
        self.env = env(su=True)
        self.env.flush_all()  # сирі SQL-читання нижче бачать лише записане
        self.now = now or dates.now_utc(env)
        self.end = dates.floor15(self.now)
        self.gap_max_s = rparam_float(env, "gap_max_s")
        self.min_coverage = rparam_float(env, "min_coverage")
        self.reset_tol = param_float(env, "reset_tol_kwh", 1.0)
        self.cost = CostModel(self.env)
        self.built_at = fields.Datetime.now()

    # --- вибір лічильників і порядок фаз ------------------------------------------------------------
    def work_items(self, meters=None):
        """`[(meter, metric)]`: неелектричні (`main`) і вводи електрики з `e_react_signal_id` (`react`)."""
        meters = meters if meters is not None else self.env["td.energy.meter"].search([("active", "=", True)])
        items = []
        for meter in meters.filtered(lambda m: m.active and m.resource_id.active):
            if meter.resource_id.code == "el":
                if meter.role == "incomer" and meter.e_react_signal_id:
                    items.append((meter, "react"))
            else:
                items.append((meter, "main"))
        return items

    @staticmethod
    def phase(item):
        meter, metric = item
        if metric == "react" or meter.mode in ("counter", "flow_integrate"):
            return 0
        return 2 if meter.point_id.estimate_method == "residual" else 1

    def build_all(self, meters=None, force_from=None, force_to=None):
        items = sorted(self.work_items(meters), key=lambda it: (self.phase(it), it[0].code))
        total = 0
        el_nodes = [m.point_id.cost_node_id.id for m, _metric in items if m.point_id.cost_node_id]
        if el_nodes:
            self.cost.load_el_costs(el_nodes, self.end - timedelta(days=45), self.end + SLOT)
        for item in items:
            meter, metric = item
            try:
                with self.env.cr.savepoint():
                    total += self.build_meter(meter, metric, force_from=force_from, force_to=force_to)
            except Exception:
                _logger.exception("td_energy_resources: інтервали лічильника %s", meter.code)
        self.env["td.energy.res.interval"].invalidate_model()
        self.env["td.energy.meter"].invalidate_model(["res_last_interval_start"])
        return total

    # --- один лічильник -------------------------------------------------------------------------------
    def slot_range(self, meter, force_from=None, force_to=None):
        """R-05 п. 1: від `res_last_interval_start − 15 хв` (два останні слоти перераховуються), перший прогін —
        `now − 24 год`; не більше 192 слотів. `(s0, n)`."""
        if force_from:
            s0 = dates.floor15(force_from)
            end = min(self.end, dates.ceil15(force_to)) if force_to else self.end
            return s0, int((end - s0) / SLOT)
        last = meter.res_last_interval_start
        s0 = last - SLOT if last else self.end - timedelta(hours=24)
        return s0, min(int((self.end - s0) / SLOT), MAX_SLOTS)

    def build_meter(self, meter, metric="main", force_from=None, force_to=None):
        s0, n = self.slot_range(meter, force_from, force_to)
        if n <= 0:
            return 0
        resource = meter.resource_id
        point = meter.point_id
        factor = resource.rate_hour_factor or 1.0
        if metric == "react" or meter.mode == "counter":
            results = self._counter_slots(meter, metric, s0, n, factor)
        elif meter.mode == "flow_integrate":
            results = self._flow_slots(meter, s0, n, factor)
        else:
            results = self._estimate_slots(meter, s0, n, factor)
        rows = []
        for k, res in enumerate(results):
            ts = s0 + k * SLOT
            ts_end, day, hour = slot_fields(ts)
            qty = res["qty"] if res["quality"] != "missing" else 0.0
            if metric == "react":
                kwh_eq = price = cost = 0.0
            else:
                kwh_eq, price, cost = self.cost.finish(resource, point, ts, qty)
            rows.append(
                (
                    meter.id, resource.id, point.id or None, metric, ts, ts_end, day, hour, round(qty, 3),
                    round(res["rate_avg"], 3), round(kwh_eq, 3), round(price, 4), cost, res["quality"], self.built_at,
                    False,
                )
            )  # fmt: skip
        write_rows(self.env, rows)
        last = s0 + (n - 1) * SLOT
        if not force_from and (not meter.res_last_interval_start or last > meter.res_last_interval_start):
            self.env.cr.execute(
                "UPDATE td_energy_meter SET res_last_interval_start = %s WHERE id = %s", (last, meter.id)
            )
        return len(rows)

    # --- джерела слотів ---------------------------------------------------------------------------------
    def _counter_slots(self, meter, metric, s0, n, factor):
        signal = meter.e_react_signal_id if metric == "react" else meter.qty_signal_id
        gap = timedelta(seconds=self.gap_max_s)
        points = load_points(self.env, signal, s0 - gap, s0 + n * SLOT + gap) if signal else []
        max_rate = meter.max_rate or meter.point_id.rate_nominal or 1000.0
        if metric == "react":
            max_rate = meter.max_kw or 1000.0
        out = []
        for k in range(n):
            t0 = s0 + k * SLOT
            window = window_points(points, t0 - gap, t0 + SLOT + gap)
            out.append(
                integrate.counter_slot(
                    window, t0, t0 + SLOT, reset_tol=self.reset_tol, max_rate=max_rate,
                    gap_max_s=self.gap_max_s, rate_hour_factor=factor,
                )
            )  # fmt: skip
        return out

    def _flow_slots(self, meter, s0, n, factor):
        gap = timedelta(seconds=self.gap_max_s)
        lo, hi = s0 - gap, s0 + n * SLOT + gap
        series = [load_points(self.env, sig, lo, hi) for sig in meter.flow_signal_ids]
        out = []
        for k in range(n):
            t0 = s0 + k * SLOT
            windows = [window_points(pts, t0 - gap, t0 + SLOT + gap) for pts in series]
            out.append(
                integrate.flow_slot(
                    windows, t0, t0 + SLOT, rate_hour_factor=factor, gap_max_s=self.gap_max_s,
                    min_coverage=self.min_coverage,
                )
            )  # fmt: skip
        return out

    def _estimate_slots(self, meter, s0, n, factor):
        point = meter.point_id
        method = point.estimate_method
        params = point.estimate_params or {}
        slots = [s0 + k * SLOT for k in range(n)]
        rates = [None] * n
        if method == "load_share":
            kw = self.node_kw(point.node_id.id, s0, s0 + n * SLOT)
            node = point.node_id
            rates = [
                estimate.load_share(kw.get(t), node.p_inst_kw, point.rate_nominal, node.load_factor, node.idle_factor)
                for t in slots
            ]
        elif method == "schedule":
            rates = [estimate.schedule(dates.to_local(t), params) for t in slots]
        elif method == "residual":
            rates = self._residual_rates(point, params, slots)
        elif method == "gate_loss":
            rates = self._gate_loss_rates(point, params, slots)
        out = []
        for rate in rates:
            if rate is None:
                out.append({"qty": 0.0, "rate_avg": 0.0, "quality": "missing"})
            else:
                out.append({"qty": rate * factor * 0.25, "rate_avg": rate, "quality": "estimated"})
        return out

    def node_kw(self, node_id, since, until):
        """`kw_avg` вузла споживача по слотах (`td.energy.interval`, `role='consumer'`, без `missing`)."""
        if not node_id:
            return {}
        self.env.cr.execute(
            """SELECT ts_start, SUM(kw_avg) FROM td_energy_interval
                WHERE role = 'consumer' AND node_id = %s AND quality != 'missing'
                  AND ts_start >= %s AND ts_start < %s GROUP BY ts_start""",
            (node_id, since, until),
        )
        return dict(self.env.cr.fetchall())

    def point_rates(self, points, since, until):
        """Швидкість точок по слотах із вже побудованих рядів `main`: `{(point_id, ts): rate | None}` (`None` —
        слот `missing`). Точка з кількома лічильниками — сума."""
        if not points:
            return {}
        self.env.cr.execute(
            """SELECT point_id, ts_start, SUM(rate_avg), bool_or(quality = 'missing')
                 FROM td_energy_res_interval
                WHERE metric = 'main' AND point_id IN %s AND ts_start >= %s AND ts_start < %s
                GROUP BY point_id, ts_start""",
            (tuple(points.ids), since, until),
        )
        return {(pid, ts): (None if miss else rate) for pid, ts, rate, miss in self.env.cr.fetchall()}

    def _residual_rates(self, point, params, slots):
        Point = self.env["td.energy.point"]
        sources = Point.search(
            [("resource_id", "=", point.resource_id.id), ("code", "in", list(params.get("from") or [])),
             ("company_id", "=", point.company_id.id)]
        )  # fmt: skip
        siblings = Point.search(
            [("resource_id", "=", point.resource_id.id), ("kind", "=", "consumer"), ("id", "!=", point.id),
             ("parent_id", "=", point.parent_id.id or False), ("company_id", "=", point.company_id.id)]
        )  # fmt: skip
        rates = self.point_rates(sources | siblings, slots[0], slots[-1] + SLOT)
        out = []
        for t in slots:
            src = [rates.get((p.id, t)) for p in sources]
            sib = [rates.get((p.id, t)) for p in siblings]
            out.append(estimate.residual(src, sib))
        return out

    def _gate_loss_rates(self, point, params, slots):
        gap = timedelta(seconds=self.gap_max_s)
        state = load_points(self.env, point.state_signal_id, slots[0] - 6 * gap, slots[-1] + SLOT)
        t_out_code = params.get("t_out_signal") or "ventilation/totals/outdoor_c"
        t_out_sig = self.env["td.signal"].with_context(active_test=False).search([("code", "=", t_out_code)], limit=1)
        t_out = load_points(self.env, t_out_sig, slots[0] - gap, slots[-1] + SLOT + gap) if t_out_sig else []
        t_in = float(params.get("t_in", estimate.DEFAULT_T_IN))
        loss = float(params.get("loss_kw_per_k", 0.0))
        invert = bool(params.get("state_invert"))  # NC-контакт воріт (`td.yard.gate.invert_di`): 0 = відкрито
        out = []
        for t0 in slots:
            t1 = t0 + SLOT
            frac = estimate.open_fraction(window_points(state, t0 - 6 * gap, t1), t0, t1, invert=invert)
            near = window_points(t_out, t0 - gap, t1 + gap)
            temp = sum(v for _t, v in near) / len(near) if near else None
            if not window_points(state, t0, t1) and not window_points(state, t0 - 6 * gap, t0):
                frac = None  # немає сирих показань за слот (R-04 п. 4)
            out.append(estimate.gate_loss(frac, t_in, temp, loss))
        return out
