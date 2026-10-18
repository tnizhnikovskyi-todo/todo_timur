"""R-22: генератор історії ресурсів `td.energy.res.interval._td_backfill` (FR-18, API-08).

Стик з електричним backfill W1 (`td_energy/tools/backfill.py`: `rnd`, `target_p`): навантаження оцінюваних
точок беруться з `td.energy.interval`. Детермінізм — за `seed` (SHA-1 від ключа). Запис по пакетах ≤ 5 000 рядків
`INSERT … ON CONFLICT (meter_id, metric, ts_start) DO NOTHING`: живі слоти не чіпаються, повтор безпечний.

Для моста (R-B5): `plan.slot_states(seed, since, until)` — стани слотів (зміна, `heat_need`, КГУ),
`plan.row(meter, ts, qty, quality)` — кортеж рядка (ціна й вартість рахуються), `plan.write(rows)` — запис із
підрахунком статистики.
"""

import logging
import math
import time
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy.tools.backfill import rnd, target_p
from odoo.addons.td_energy.tools.dates import SLOT

from . import build, estimate

_logger = logging.getLogger(__name__)

GAS_KWH_M3 = 10.5
BOILER_ETA = 0.914
HEAT_PEAK_KW = 390.0
CHP_HEAT_KW = 497.0
CHP_GAS_M3H = 109.0
AIR_LEAK = 1.6
AIR_REF = 9.8
WATER_SHIFT, WATER_NIGHT, WATER_PAINT, WATER_BOILER = 2.1, 0.3, 1.5, 0.0125
REACT_COS = {1: 0.95, 2: 0.88}


class SlotState:
    """Стан слота, спільний для генераторів газу, повітря, води й тепла (R-22 п. 2)."""

    __slots__ = ("i", "ts", "local", "hs", "weekday", "shift", "act", "heat_need", "chp_on", "heat_chp")

    def __init__(self, i, ts, local, seed, chp_days):
        self.i, self.ts, self.local = i, ts, local
        self.hs = local.hour + local.minute / 60.0
        self.weekday = local.weekday()
        hs, wd = self.hs, self.weekday
        self.shift = (wd < 5 and 7 <= hs < 23) or (wd == 5 and 7 <= hs < 14)
        self.act = estimate.clamp((target_p(hs, wd) - 210.0) / (667.0 - 210.0), 0.0, 1.3)
        doy = local.timetuple().tm_yday
        season = estimate.clamp(0.5 + 0.5 * math.cos(2 * math.pi * (doy - 15) / 365.0), 0.1, 1.0)
        need = season * (0.35 + 0.65 * (1.0 if self.shift else 0.0)) * HEAT_PEAK_KW
        if wd < 6 and 5.5 <= hs < 7:
            need *= 1.3  # розігрів перед зміною
        self.heat_need = need
        day_key = local.date().isoformat()
        if day_key not in chp_days:
            chp_days[day_key] = rnd(seed, day_key, "chp") < 0.1
        self.chp_on = wd < 5 and 16 <= hs < 19 and chp_days[day_key]
        self.heat_chp = CHP_HEAT_KW if self.chp_on else 0.0


class ResPlan:
    """Знімок: лічильники ресурсів, електричні дані для оцінок, вартість."""

    def __init__(self, env, resources=None):
        self.env = env
        Meter = env["td.energy.meter"].sudo()
        wanted = set(resources) if resources else None
        self.wanted = wanted  # коди ресурсів, запитані викликом (`None` — усі); хук моста застосовує той самий фільтр
        meters = Meter.search([("active", "=", True), ("resource_id.active", "=", True)], order="code")
        self.items = []  # [(meter, metric)]
        for meter in meters:
            code = meter.resource_id.code
            if code == "heat" or (wanted and code not in wanted):
                continue  # тепло генерує хук `_td_backfill_extra` моста (R-B5)
            if code == "el":
                if meter.role == "incomer" and meter.e_react_signal_id:
                    self.items.append((meter, "react"))
            else:
                self.items.append((meter, "main"))
        self.by_code = {m.code: m for m, metric in self.items if metric == "main"}
        self.cost = build.CostModel(env)
        self.stats = {"meters": 0, "slots": 0, "rows": 0, "skipped": 0}
        self.attempted = 0
        self._chp_days = {}
        self.node_kw = {}
        self.incomer_kwh = {}
        self.built_at = fields.Datetime.now()

    # --- електричні дані -------------------------------------------------------------------------------
    def load_electric(self, since, until):
        cr = self.env.cr
        nodes = {m.point_id.node_id.id for m, metric in self.items if metric == "main" and m.point_id.node_id}
        nodes |= {
            m.point_id.cost_node_id.id for m, metric in self.items if metric == "main" and m.point_id.cost_node_id
        }
        nodes.discard(False)
        if nodes:
            cr.execute(
                """SELECT node_id, ts_start, SUM(kw_avg) FROM td_energy_interval
                    WHERE role = 'consumer' AND node_id IN %s AND quality != 'missing'
                      AND ts_start >= %s AND ts_start < %s GROUP BY node_id, ts_start""",
                (tuple(nodes), since, until),
            )
            self.node_kw = {(n, t): kw for n, t, kw in cr.fetchall()}
            self.cost.load_el_costs(
                [
                    m.point_id.cost_node_id.id
                    for m, metric in self.items
                    if metric == "main" and m.point_id.cost_node_id
                ],
                since,
                until,
            )
        incomers = [m.id for m, metric in self.items if metric == "react"]
        if incomers:
            cr.execute(
                """SELECT meter_id, ts_start, kwh FROM td_energy_interval
                    WHERE meter_id IN %s AND quality != 'missing' AND ts_start >= %s AND ts_start < %s""",
                (tuple(incomers), since, until),
            )
            self.incomer_kwh = {(mid, t): kwh for mid, t, kwh in cr.fetchall()}
        if (nodes or incomers) and not self.node_kw and not self.incomer_kwh:
            _logger.warning("td_energy_resources: backfill: немає td.energy.interval — оцінні слоти будуть missing")

    # --- слоти -------------------------------------------------------------------------------------------
    def slot_states(self, seed, since, until):
        for i in range(int((until - since) / SLOT)):
            ts = since + SLOT * i
            yield SlotState(i, ts, dates.to_local(ts), seed, self._chp_days)

    def row(self, meter, ts, qty, quality, metric="main"):
        """Кортеж рядка `td_energy_res_interval` (ціна, вартість, `kwh_eq` — R-01, R-02)."""
        resource, point = meter.resource_id, meter.point_id
        factor = resource.rate_hour_factor or 1.0
        ts_end, day, hour = build.slot_fields(ts)
        if quality == "missing":
            qty = 0.0
        if metric == "react":
            kwh_eq = price = cost = 0.0
        else:
            kwh_eq, price, cost = self.cost.finish(resource, point, ts, qty)
        return (
            meter.id, resource.id, point.id or None, metric, ts, ts_end, day, hour, round(qty, 3),
            round(qty * 4.0 / factor, 3), round(kwh_eq, 3), round(price, 4), cost, quality, self.built_at, True,
        )  # fmt: skip

    def write(self, rows):
        attempted, affected = build.write_rows(self.env, rows, build.BACKFILL_INSERT_SQL)
        self.stats["rows"] += affected
        self.attempted += attempted

    # --- оцінки -------------------------------------------------------------------------------------------
    def estimate_rate(self, meter, st):
        point = meter.point_id
        method = point.estimate_method
        if method == "load_share":
            node = point.node_id
            return estimate.load_share(
                self.node_kw.get((node.id, st.ts)), node.p_inst_kw, point.rate_nominal, node.load_factor,
                node.idle_factor,
            )  # fmt: skip
        if method == "schedule":
            return estimate.schedule(st.local, point.estimate_params or {})
        return None

    def spray_active(self, st):
        """`active(SPRAY-1)` — частка роботи фарбувальної камери за навантаженням вузла (R-22, вода)."""
        meter = self.by_code.get("WM-SPRAY")
        node = meter.point_id.node_id if meter else None
        if not node:
            return 0.0
        kw = self.node_kw.get((node.id, st.ts))
        value = estimate.load_share(kw, node.p_inst_kw, 1.0, node.load_factor, node.idle_factor)
        return value or 0.0


def _simulate(plan, seed, since, until):
    """`(state, {meter_code: rate | None})` по слотах; швидкості — у одиницях `rate_label` ресурсу."""
    estimates = [
        m
        for m, metric in plan.items
        if metric == "main"
        and m.mode == "estimate"
        and m.point_id.estimate_method in ("load_share", "schedule", "residual")
    ]
    simple = [m for m in estimates if m.point_id.estimate_method != "residual"]
    residuals = [m for m in estimates if m.point_id.estimate_method == "residual"]
    measured = {m.code for m, metric in plan.items if metric == "main" and m.mode != "estimate"}
    for st in plan.slot_states(seed, since, until):
        rates = {m.code: plan.estimate_rate(m, st) for m in simple}
        by_point = {}
        for m in simple:
            by_point[(m.resource_id.code, m.point_id.code)] = rates[m.code]
        # газ
        boiler = chp = 0.0
        if "GM-BOILER" in measured or "GM-MAIN" in measured:
            boiler = max(0.0, st.heat_need - st.heat_chp) / (GAS_KWH_M3 * BOILER_ETA)
            chp = CHP_GAS_M3H if st.chp_on else 0.0
        if "GM-BOILER" in measured:
            rates["GM-BOILER"] = boiler
        if "GM-CHP" in measured:
            rates["GM-CHP"] = chp
        if "GM-MAIN" in measured:
            branches = (
                boiler
                + chp
                + sum(r or 0.0 for m in simple if m.resource_id.code == "gas" and (r := rates.get(m.code)) is not None)
            )
            eps = 0.01 + 0.004 * (2 * rnd(seed, "gas", st.i) - 1)
            rates["GM-MAIN"] = branches * (1.0 + eps)
        # повітря
        if "AM-MAIN" in measured:
            rates["AM-MAIN"] = AIR_LEAK * (1.0 + 0.05 * rnd(seed, "air", st.i)) + (AIR_REF - AIR_LEAK) * st.act
        # вода
        paint = 1.0 if plan.spray_active(st) >= 0.5 else 0.0
        if "WM-MAIN" in measured:
            rates["WM-MAIN"] = (WATER_SHIFT if st.shift else WATER_NIGHT) + WATER_PAINT * paint + WATER_BOILER
        if "WM-BOILER" in measured:
            rates["WM-BOILER"] = WATER_BOILER
        for m in measured:
            if m in rates:
                meter = plan.by_code[m]
                by_point[(meter.resource_id.code, meter.point_id.code)] = rates[m]
        # залишок
        for m in residuals:
            params = m.point_id.estimate_params or {}
            res = m.resource_id.code
            sources = [by_point.get((res, c)) for c in params.get("from", [])]
            siblings = [
                by_point.get((res, o.point_id.code))
                for o in plan.by_code.values()
                if o.resource_id == m.resource_id and o.point_id.kind == "consumer" and o != m
                and o.point_id.parent_id == m.point_id.parent_id
            ]  # fmt: skip
            rates[m.code] = estimate.residual(sources, siblings)
        yield st, rates


def _range(env, days, until):
    now = dates.now_utc(env)
    if until:
        until = dates.floor15(fields.Datetime.to_datetime(until))
    else:
        env.cr.execute(
            """SELECT MIN(r.ts) FROM td_reading r WHERE r.signal_id IN (
                   SELECT qty_signal_id FROM td_energy_meter WHERE qty_signal_id IS NOT NULL AND active
                   UNION SELECT e_react_signal_id FROM td_energy_meter WHERE e_react_signal_id IS NOT NULL AND active
                   UNION SELECT f.signal_id FROM td_energy_meter_flow_signal_rel f
                           JOIN td_energy_meter m ON m.id = f.meter_id WHERE m.active)"""
        )
        first = env.cr.fetchone()[0]
        until = dates.ceil15(first) if first else dates.floor15(now)
        if until > now:
            until = dates.floor15(now)
    return until - timedelta(days=days), until


def _purge(env, since, until):
    env.cr.execute(
        "DELETE FROM td_energy_res_interval WHERE is_backfill AND ts_start >= %s AND ts_start < %s", (since, until)
    )
    rows = env.cr.rowcount
    env["td.energy.res.interval"].invalidate_model()
    return {"purged_rows": rows}


def _touch_meters(env, meter_ids, last_slot, until):
    """`res_last_interval_start = max(існуюче, останній слот)` — лише коли немає живих слотів пізніше (R-22 п. 3)."""
    env.cr.execute(
        """UPDATE td_energy_meter m SET res_last_interval_start = GREATEST(COALESCE(m.res_last_interval_start, %s), %s)
            WHERE m.id IN %s AND NOT EXISTS (SELECT 1 FROM td_energy_res_interval r
                  WHERE r.meter_id = m.id AND NOT r.is_backfill AND r.ts_start >= %s)""",
        (last_slot, last_slot, tuple(meter_ids), until),
    )
    env["td.energy.meter"].invalidate_model(["res_last_interval_start"])


def run(env, days=90, until=None, seed=20261018, purge=False, resources=None):
    """API-08 / R-22: історія ресурсів; повертає `{"meters","slots","rows","skipped","since","until","seconds"}`."""
    started = time.monotonic()
    env.flush_all()  # сирі SQL-читання (показання, інтервали) бачать лише записане
    days = int(days)
    if not 1 <= days <= 400:
        raise UserError(env._("Кількість діб має бути від 1 до 400."))
    since, until = _range(env, days, until)
    stats = {"meters": 0, "slots": 0, "rows": 0, "skipped": 0, "since": fields.Datetime.to_string(since),
             "until": fields.Datetime.to_string(until), "seconds": 0.0}  # fmt: skip
    if purge:
        stats.update(_purge(env, since, until))
        stats["seconds"] = round(time.monotonic() - started, 2)
        return stats
    plan = ResPlan(env, resources)
    plan.load_electric(since, until)
    plan.stats = stats
    state = {}  # накопичувачі лічильників: (meter_id) → (кумулятив, округлений)
    batch, last_slot, written = [], None, set()
    for st, rates in _simulate(plan, seed, since, until):
        stats["slots"] += 1
        last_slot = st.ts
        for meter, metric in plan.items:
            if metric == "react":
                kwh = plan.incomer_kwh.get((meter.id, st.ts))
                cos_phi = REACT_COS.get(meter.node_id.section or 1, REACT_COS[1])
                if kwh is None:
                    qty, quality = 0.0, "missing"
                else:
                    qty, quality = kwh * math.tan(math.acos(cos_phi)), "measured"
                batch.append(plan.row(meter, st.ts, qty, quality, "react"))
                written.add(meter.id)
                continue
            if meter.code not in rates:
                continue  # немає генератора (не демо-лічильник)
            rate = rates[meter.code]
            written.add(meter.id)
            factor = meter.resource_id.rate_hour_factor or 1.0
            if rate is None:
                batch.append(plan.row(meter, st.ts, 0.0, "missing"))
                continue
            qty = rate * factor * 0.25
            if meter.mode == "estimate":
                batch.append(plan.row(meter, st.ts, qty, "estimated"))
                continue
            if meter.mode == "counter":  # накопичувач із квантом 0,01 (R-22 п. 2)
                cum, rounded = state.get(meter.id, (0.0, 0.0))
                cum += qty
                new_rounded = round(cum, 2)
                state[meter.id] = (cum, new_rounded)
                qty = new_rounded - rounded
            batch.append(plan.row(meter, st.ts, qty, "measured"))
        if len(batch) >= build.BATCH:
            plan.write(batch)
            batch = []
    if batch:
        plan.write(batch)
    extra = env["td.energy.res.interval"]._td_backfill_extra(plan, seed, since, until) or {}
    written |= set(extra.get("meter_ids", ()))
    stats["meters"] = len(written)
    stats["skipped"] = plan.attempted - stats["rows"]
    env["td.energy.res.interval"].invalidate_model()
    if last_slot is not None and written:
        _touch_meters(env, written, last_slot, until)
    stats["seconds"] = round(time.monotonic() - started, 2)
    _logger.info("td_energy_resources: backfill: %s", stats)
    return stats
