"""R-08…R-12, R-25: збирання JSON екрана «Енергоресурси» (API-01; воркер W3-E).

`Screen(env, hooks, code).build()` — один прогін `td.energy.res.dashboard.get_resources`. Дані читаються мінімумом
запитів (AC-60: ≤ 30 SQL на будь-якій вкладці): структура (ресурси, точки, лічильники) і добові агрегати — сирим SQL
по одному запиту на вибірку, живі значення — одним `search_read` сигналів. Електрика береться з тих самих
`td.energy.interval`, що й Пульт W1 (96 локальних слотів, нетто вводів), без `get_pult`: сам Пульт робить 20–28
запитів, і разом з рештою вкладок бюджет був би перевищений (тест звіряє числа з `get_pult`). Неповний слот
(R-08 п. 2) додається до «сьогодні» лічильників неелектричних ресурсів; електрика й генерація — до закритих слотів.
"""

import logging
import math
import re
from collections import defaultdict
from datetime import timedelta
from functools import cached_property

from odoo.exceptions import UserError

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy.tools.dates import param_float

from . import estimate, integrate, shifts
from .build import react_stats, rparam_float

_logger = logging.getLogger(__name__)

COST_GROUP = "td_energy.group_td_energy_cost"
MANAGER_GROUP = "td_energy.group_td_energy_manager"
COST_KEYS = ("cost_uah", "save_uah_month", "price_uah")
SLOTS = 96
FRESH_MIN_S = 120  # R-08 п. 1: свіже, якщо `last_ts ≥ now − max(3·period_s, 120 с)`
NIGHT_COVERAGE = 0.7  # R-09: покриття нічного вікна
RECENT_S = 45 * 60  # останній побудований слот — не старший за 3 слоти
MAX_LIST = 8
NICE = (1, 1.5, 2, 2.5, 3, 4, 5, 6, 7.5, 10)
SIG_RATE = {"gas": "infra/gas/flow_m3h", "air": "air/flow_m3min", "water": "infra/water/flow_m3h"}
SIG_CHP, SIG_PRESSURE = "infra/chp/state", "air/pressure_bar"
SIG_SETPOINT, SIG_COMPRESSOR = "energy_control/air/setpoint_bar", "energy/consumers/COMPRESSOR/p_now"
SIG_GRID, SIG_LOAD = "infra/totals/grid_kw", "energy/totals/p_now"
FIXED_SIGNALS = (SIG_CHP, SIG_PRESSURE, SIG_SETPOINT, SIG_COMPRESSOR, SIG_GRID, SIG_LOAD, *SIG_RATE.values())
RES_FIELDS = (
    "code", "name", "sequence", "uom_label", "rate_label", "rate_hour_factor", "kwh_per_unit", "is_derived",
    "show_tab_cost", "source_note", "price_source", "limit_kind", "rate_limit", "daily_limit", "list_basis", "color",
    "chart_title", "chart_note", "list_title", "foot_template",
)  # fmt: skip

METER_SQL = """
SELECT m.id, m.code, m.point_id, m.resource_id, m.mode, m.qty_signal_id, m.max_rate
  FROM td_energy_meter m JOIN td_energy_resource r ON r.id = m.resource_id
 WHERE m.active AND r.active AND m.company_id IN %s
"""
FLOW_SQL = "SELECT meter_id, signal_id FROM td_energy_meter_flow_signal_rel WHERE meter_id IN %s"
POINT_SQL = """
SELECT p.id, p.resource_id, p.code, p.name, p.kind, p.estimate_method, p.rate_nominal, p.cost_node_id,
       n.code AS node_code, n.p_inst_kw, n.load_factor, n.idle_factor
  FROM td_energy_point p LEFT JOIN td_energy_node n ON n.id = p.node_id
 WHERE p.active AND p.resource_id IN %s AND p.company_id IN %s ORDER BY p.resource_id, p.sequence, p.code
"""
TODAY_SQL = """
SELECT meter_id, SUM(qty), SUM(kwh_eq), SUM(cost) FROM td_energy_res_interval
 WHERE day = %s AND metric = 'main' AND resource_id IN %s GROUP BY meter_id
"""
LAST_SQL = """
SELECT DISTINCT ON (meter_id) meter_id, rate_avg, price FROM td_energy_res_interval
 WHERE metric = 'main' AND day >= %s AND resource_id IN %s AND ts_start >= %s AND ts_start < %s
   AND quality <> 'missing' ORDER BY meter_id, ts_start DESC
"""
READINGS_SQL = """
SELECT signal_id, ts, value FROM td_reading
 WHERE signal_id IN %s AND quality <> 'bad' AND ts >= %s AND ts <= %s ORDER BY signal_id, ts
"""
WINDOW_SQL = """
SELECT ts_start, SUM(rate_avg) FROM td_energy_res_interval
 WHERE metric = 'main' AND day >= %s AND meter_id IN %s AND quality <> 'missing' AND ts_start >= %s AND ts_start < %s
 GROUP BY ts_start ORDER BY ts_start
"""
EL_SQL = """
SELECT i.ts_start, i.role, m.model, SUM(i.kwh), SUM(i.kwh_export), MAX(i.price)
  FROM td_energy_interval i JOIN td_energy_meter m ON m.id = i.meter_id
 WHERE i.ts_start >= %s AND i.ts_start < %s AND i.role IN ('feeder', 'incomer', 'generation')
 GROUP BY i.ts_start, i.role, m.model
"""
NODE_COST_SQL = """
SELECT COALESCE(SUM(kwh), 0), COALESCE(SUM(cost), 0) FROM td_energy_interval
 WHERE day = %s AND role = 'consumer' AND node_id IN %s
"""
REACT_SQL = "SELECT COALESCE(SUM(qty), 0), COUNT(*) FROM td_energy_res_interval WHERE day = %s AND metric = 'react'"
TOP_SQL = """
SELECT n.code, n.name, s.last_value FROM td_energy_node n
  JOIN td_signal s ON s.code = 'energy/consumers/' || n.code || '/p_now'
 WHERE n.kind = 'consumer' AND s.last_ts IS NOT NULL AND s.status NOT IN ('stale', 'unknown')
   AND s.last_quality IS DISTINCT FROM 'bad' AND s.last_value > 0
 ORDER BY s.last_value DESC, n.code LIMIT 6
"""


# --- числа й підписи (R-25) -----------------------------------------------------------------------------------
def fmt_int(x):
    """Ціле: пробіл — роздільник тисяч."""
    return "{:,}".format(int(round(x))).replace(",", " ")


def fmt_dec(x, digits=1):
    """Кома — десятковий роздільник, пробіл — тисяч."""
    return "{:,.{d}f}".format(x, d=digits).replace(",", " ").replace(".", ",")


def fmt_auto(x):
    """Норми, тиск, уставка: ≥ 10 — ціле, менше — 1 знак (2, якщо 1 знак губить значення): «6,0», «0,05», «90»."""
    x = float(x)
    if abs(x) >= 10:
        return fmt_int(x)
    return fmt_dec(x, 1 if round(x, 1) == round(x, 6) else 2)


def r_int(x):
    return None if x is None else int(round(x))


def r_rate(x, code=None):
    """м³/год, м³/хв: ≥ 10 — ціле; < 10 — 1 знак; вода < 1 — 2 знаки."""
    if x is None:
        return None
    if abs(x) >= 10:
        return int(round(x))
    return round(x, 2) + 0.0 if code == "water" and abs(x) < 1 else round(x, 1) + 0.0


def r_day(x):
    """м³ за добу: ≥ 100 — ціле, інакше 1 знак."""
    if x is None:
        return None
    return int(round(x)) if abs(x) >= 100 else round(x, 1) + 0.0


def t_rate(v):
    """Текст уже округленої швидкості."""
    if v is None:
        return "—"
    if isinstance(v, int) or abs(v) >= 10:
        return fmt_int(v)
    return fmt_dec(v, 1 if round(v, 1) == v else 2)


def t_day(v):
    if v is None:
        return "—"
    return fmt_int(v) if isinstance(v, int) else fmt_dec(v, 1)


def plural_resources(n):
    if n % 10 == 1 and n % 100 != 11:
        return "ресурс"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "ресурси"
    return "ресурсів"


def nice(x):
    """R-10 п. 3: найменше з `{1; 1,5; 2; 2,5; 3; 4; 5; 6; 7,5; 10}·10^k`, не менше `x`."""
    if x <= 0:
        return 1.0
    k = math.floor(math.log10(x))
    for exp in (k, k + 1):
        for c in NICE:
            v = c * 10.0**exp
            if v >= x * (1 - 1e-9):
                return v
    return 10.0 ** (k + 1)


def num(v):
    v = float(v)
    return int(v) if v.is_integer() else round(v, 6)


def axis(series, limit):
    """`(y_max, ticks)`: три рівні поділки, `y_max = 3·step` (R-10 п. 3, D-42)."""
    peak = max([v for v in series if v is not None] + [limit or 0.0])
    step = nice(1.1 * peak / 3.0)
    return num(3 * step), [num(step), num(2 * step), num(3 * step)]


def strip_cost(data):
    """Ключі вартості — геть (M-08: без групи `group_td_energy_cost` вони видаляються, а не ховаються)."""
    if isinstance(data, dict):
        return {k: strip_cost(v) for k, v in data.items() if k not in COST_KEYS}
    if isinstance(data, list):
        return [strip_cost(v) for v in data]
    return data


def kpi(kid, label, value, unit, note="", tone="neutral", quality="measured"):
    return {"id": kid, "label": label, "value": value, "unit": unit, "note": note, "tone": tone, "quality": quality}


def render_foot(template, values):
    """D-33: підпис під графіком — `foot_template` по реченнях; речення без даних (значення `None`) опускається."""
    out = []
    for part in re.split(r"(?<=\.)(?=\s|\{)", template or ""):
        names = re.findall(r"\{(\w+)\}", part)
        if any(values.get(name) is None for name in names):
            continue
        out.append(part.format(**{n: values[n] for n in names}))
    return "".join(out).strip()


class Screen:
    def __init__(self, env, hooks, code=None, isolate=False):
        self.env, self.sudo, self.cr, self.hooks = env, env(su=True), env.cr, hooks
        self.code, self.isolate, self.focus = code, isolate, None
        self.now = dates.now_utc(env)
        self.today = dates.local_day(self.now)
        self.day0, self.day1 = dates.local_day_bounds(self.today)
        self.cur = dates.floor15(self.now)
        self.now_slot = dates.local_slot_index(self.cur)
        self.cost = env.user.has_group(COST_GROUP)
        self.manager = env.user.has_group(MANAGER_GROUP)
        self.companies = tuple(env.companies.ids) or (env.company.id,)
        self.gap_max_s = rparam_float(env, "gap_max_s")
        self.min_coverage = rparam_float(env, "min_coverage")
        self._cache = {}
        env.flush_all()  # сирі SQL нижче бачать лише записане

    # --- структура: ресурси, лічильники, точки ------------------------------------------------------------
    @cached_property
    def _meter_rows(self):
        self.cr.execute(METER_SQL, (self.companies,))
        return self.cr.dictfetchall()

    @cached_property
    def resources(self):
        """R-12, D-48: активні ресурси з хоча б одним активним лічильником, за `sequence`."""
        has = {m["resource_id"] for m in self._meter_rows}
        rows = self.sudo["td.energy.resource"].search_read([], RES_FIELDS, order="sequence, id")
        return [r for r in rows if r["id"] in has]

    @cached_property
    def by_code(self):
        return {r["code"]: r for r in self.resources}

    @cached_property
    def ne_ids(self):
        return tuple(r["id"] for r in self.resources if r["code"] != "el")

    @cached_property
    def meters(self):
        """Лічильники неелектричних вкладок:
        `{id, code, point_id, resource_id, mode, qty_signal_id, max_rate, flows}`."""
        ids = set(self.ne_ids)
        meters = [dict(m, flows=[]) for m in self._meter_rows if m["resource_id"] in ids]
        if meters:
            by_id = {m["id"]: m for m in meters}
            self.cr.execute(FLOW_SQL, (tuple(by_id),))
            for meter_id, signal_id in self.cr.fetchall():
                by_id[meter_id]["flows"].append(signal_id)
        return meters

    @cached_property
    def points(self):
        """`{resource_id: [точка…]}` активних точок неелектричних вкладок (одним запитом, разом із вузлом)."""
        out = defaultdict(list)
        if self.ne_ids:
            self.cr.execute(POINT_SQL, (self.ne_ids, self.companies))
            for row in self.cr.dictfetchall():
                out[row["resource_id"]].append(row)
        return out

    @cached_property
    def point_meters(self):
        out = defaultdict(list)
        for m in self.meters:
            out[m["point_id"]].append(m)
        return out

    def sources(self, res):
        return [p for p in self.points[res["id"]] if p["kind"] == "source"]

    def supply_points(self, res):
        """R-07: точки `source`; немає — `consumer` (ресурс без вводу)."""
        return self.sources(res) or [p for p in self.points[res["id"]] if p["kind"] == "consumer"]

    def supply_meters(self, res):
        return [m for p in self.supply_points(res) for m in self.point_meters[p["id"]]]

    @staticmethod
    def meter_signal_ids(m):
        return ([m["qty_signal_id"]] if m["qty_signal_id"] else []) + m["flows"]

    # --- сигнали й живі значення (R-08 п. 1) --------------------------------------------------------------
    @cached_property
    def signals(self):
        ids = {sid for m in self.meters for sid in self.meter_signal_ids(m)}
        codes = set(FIXED_SIGNALS)
        for p in self.points[self.focus["id"]] if self.focus else []:
            if p["node_code"]:
                codes.add("energy/consumers/%s/p_now" % p["node_code"])
        rows = self.sudo["td.signal"].search_read(
            ["|", ("code", "in", sorted(codes)), ("id", "in", sorted(ids))],
            ["code", "last_value", "last_text", "last_ts", "last_quality", "period_s"],
        )
        return {"code": {r["code"]: r for r in rows}, "id": {r["id"]: r for r in rows}}

    def is_fresh(self, sig):
        if not sig or not sig["last_ts"] or sig["last_quality"] == "bad":
            return False
        return (self.now - sig["last_ts"]).total_seconds() <= max(3 * (sig["period_s"] or 60), FRESH_MIN_S)

    def sig_value(self, code):
        sig = self.signals["code"].get(code)
        return sig["last_value"] if self.is_fresh(sig) else None

    def sig_text(self, code):
        sig = self.signals["code"].get(code)
        return (sig["last_text"] or None) if self.is_fresh(sig) else None

    # --- ряди й добові агрегати ресурсів -------------------------------------------------------------------
    @cached_property
    def today_rows(self):
        """`{meter_id: (qty, kwh_eq, cost)}` за добу (Київ), `metric='main'`."""
        if not self.ne_ids:
            return {}
        self.cr.execute(TODAY_SQL, (self.today, self.ne_ids))
        return {mid: (qty or 0.0, kwh or 0.0, cost or 0.0) for mid, qty, kwh, cost in self.cr.fetchall()}

    @cached_property
    def last_slots(self):
        """Останній побудований слот лічильника (не старший за `RECENT_S`): `{meter_id: {rate_avg, price}}`."""
        if not self.ne_ids:
            return {}
        since = self.cur - timedelta(seconds=RECENT_S)
        self.cr.execute(LAST_SQL, (self.today - timedelta(days=1), self.ne_ids, since, self.now))
        return {mid: {"rate_avg": rate or 0.0, "price": price or 0.0} for mid, rate, price in self.cr.fetchall()}

    @cached_property
    def partial(self):
        """R-08 п. 2: неповний слот `[floor15(now), now)` лічильників-джерел за правилами R-03: `{meter_id: qty}`.
        Минуло < 60 с — порожньо; `coverage` рахується відносно минулого часу."""
        if (self.now - self.cur).total_seconds() < 60:
            return {}
        meters = [
            m
            for r in self.resources
            if r["code"] != "el"
            for m in self.supply_meters(r)
            if m["mode"] in ("counter", "flow_integrate")
        ]
        sig_ids = sorted({sid for m in meters for sid in self.meter_signal_ids(m)})
        if not sig_ids:
            return {}
        lo = self.cur - timedelta(seconds=self.gap_max_s)
        series = defaultdict(dict)
        self.cr.execute(READINGS_SQL, (tuple(sig_ids), lo, self.now))
        for sid, ts, value in self.cr.fetchall():
            if value is not None:
                series[sid][ts] = value
        for sid in sig_ids:
            sig = self.signals["id"].get(sid)
            if sig and sig["last_ts"] and lo <= sig["last_ts"] <= self.now and sig["last_quality"] != "bad":
                if sig["last_value"] is not None:
                    series[sid].setdefault(sig["last_ts"], sig["last_value"])
        res_by_id = {r["id"]: r for r in self.resources}
        points = {p["id"]: p for plist in self.points.values() for p in plist}
        reset_tol = param_float(self.env, "reset_tol_kwh", 1.0)
        out = {}
        for m in meters:
            factor = res_by_id[m["resource_id"]]["rate_hour_factor"] or 1.0
            if m["mode"] == "flow_integrate":
                result = integrate.flow_slot(
                    [sorted(series[sid].items()) for sid in m["flows"]],
                    self.cur,
                    self.now,
                    rate_hour_factor=factor,
                    gap_max_s=self.gap_max_s,
                    min_coverage=self.min_coverage,
                )
            else:
                max_rate = m["max_rate"] or points.get(m["point_id"], {}).get("rate_nominal") or 1000.0
                result = integrate.counter_slot(
                    sorted(series[m["qty_signal_id"]].items()),
                    self.cur,
                    self.now,
                    reset_tol=reset_tol,
                    max_rate=max_rate,
                    gap_max_s=self.gap_max_s,
                    rate_hour_factor=factor,
                )
            if result["quality"] != "missing":
                out[m["id"]] = result["qty"]
        return out

    def qty_today(self, res, meters=None):
        """`Σ qty` лічильників (за умовчанням — джерел ресурсу) за добу + неповний слот."""
        meters = self.supply_meters(res) if meters is None else meters
        return sum(self.today_rows.get(m["id"], (0.0,))[0] + self.partial.get(m["id"], 0.0) for m in meters)

    def node_cost(self, res):
        """`(кВт·год, ₴)` вузлів `cost_node_id` точок ресурсу за добу (R-02 п. 4)."""
        key = ("node_cost", res["code"])
        if key not in self._cache:
            nodes = tuple({p["cost_node_id"] for p in self.points[res["id"]] if p["cost_node_id"]})
            kwh = cost = 0.0
            if nodes:
                self.cr.execute(NODE_COST_SQL, (self.today, nodes))
                kwh, cost = (float(v) for v in self.cr.fetchone())
            self._cache[key] = (kwh, cost)
        return self._cache[key]

    def cost_today(self, res):
        """R-12: вартість вкладки за сьогодні: `tariff` — електрика; `price`/`derived_gas` — Σ cost джерел (+ неповний
        слот за ціною останнього слота); `derived_el` — Σ cost вузла `cost_node_id`; `none` — `None`."""
        key = ("cost", res["code"])
        if key not in self._cache:
            source, value = res["price_source"], None
            if source == "tariff":
                value = self.el["cost"]
            elif source in ("price", "derived_gas"):
                value = 0.0
                for m in self.supply_meters(res):
                    value += self.today_rows.get(m["id"], (0.0, 0.0, 0.0))[2]
                    value += self.partial.get(m["id"], 0.0) * self.last_slots.get(m["id"], {}).get("price", 0.0)
            elif source == "derived_el":
                value = self.node_cost(res)[1]
            self._cache[key] = value
        return self._cache[key]

    # --- швидкості «зараз» ----------------------------------------------------------------------------------
    def meter_rate(self, m):
        if m["mode"] == "flow_integrate" and m["flows"]:
            sigs = [self.signals["id"].get(sid) for sid in m["flows"]]
            if all(self.is_fresh(s) for s in sigs):
                return sum(s["last_value"] for s in sigs)
        slot = self.last_slots.get(m["id"])
        return slot["rate_avg"] if slot else None

    def point_rate(self, p):
        """R-11 п. 1: живе значення виміряних, `load_share` — за живою `p_now` вузла, інакше останній слот."""
        if p["estimate_method"] == "load_share" and p["node_code"]:
            kw = self.sig_value("energy/consumers/%s/p_now" % p["node_code"])
            if kw is not None:
                return estimate.load_share(kw, p["p_inst_kw"], p["rate_nominal"], p["load_factor"], p["idle_factor"])
        rates = [r for r in (self.meter_rate(m) for m in self.point_meters[p["id"]]) if r is not None]
        return sum(rates) if rates else None

    def rate_now(self, res):
        """R-09: швидкість зараз (одиниці `rate_label`); `None` — немає свіжих даних."""
        key = ("rate", res["code"])
        if key not in self._cache:
            if res["code"] == "el":
                value = self.sig_value(SIG_GRID)
            else:
                value = self.sig_value(SIG_RATE[res["code"]]) if res["code"] in SIG_RATE else None
                if value is None:
                    rates = [r for r in (self.point_rate(p) for p in self.supply_points(res)) if r is not None]
                    value = sum(rates) if rates else None
            self._cache[key] = value
        return self._cache[key]

    # --- електрика (R-09 п. 3) ------------------------------------------------------------------------------
    @cached_property
    def el(self):
        """Електрика за добу: слоти `td.energy.interval` до поточного (нетто вводів, як у Пульті W1)."""
        self.cr.execute(EL_SQL, (self.day0, self.cur))
        slots = {}
        d = {"import": 0.0, "export": 0.0, "cost": 0.0, "p_in": 0.0, "gen": 0.0, "pv": 0.0, "chp": 0.0, "load": 0.0}
        for ts, role, model, kwh, kwh_exp, price in self.cr.fetchall():
            kwh, kwh_exp = kwh or 0.0, kwh_exp or 0.0
            slot = slots.setdefault(ts, {"net": None, "price": 0.0})
            if role == "incomer":
                slot["net"] = (slot["net"] or 0.0) + kwh - kwh_exp
                slot["price"] = max(slot["price"], price or 0.0)
                d["p_in"] += kwh
            elif role == "generation":
                d["gen"] += kwh
                d["pv"] += kwh if model == "sun2000" else 0.0
                d["chp"] += kwh if model == "tedom" else 0.0
            else:
                d["load"] += kwh
        grid, first_export = [None] * SLOTS, None
        for ts in sorted(slots):
            net = slots[ts]["net"]
            if net is None:
                continue
            d["import"] += max(0.0, net)
            d["export"] += max(0.0, -net)
            d["cost"] += max(0.0, net) * slots[ts]["price"]
            grid[dates.local_slot_index(ts)] = max(0.0, net) * 4
            if net < 0 and first_export is None:
                first_export = ts
        d.update(grid=grid, first_export=first_export, grid_kw=self.sig_value(SIG_GRID))
        return d

    @cached_property
    def tariff(self):
        return self.sudo["td.energy.tariff"]._td_tariff_at(self.now)

    @cached_property
    def contract_kw(self):
        return self.tariff.contract_kw if self.tariff else 0.0

    # --- стан даних (R-08 п. 4) -----------------------------------------------------------------------------
    def state_of(self, res):
        """`(data_state, age_s)`: `stale` — немає свіжих сигналів лічильників ресурсу, `partial` — частина без даних."""
        if res["code"] == "el":
            groups = [[self.signals["code"].get(SIG_LOAD)], [self.signals["code"].get(SIG_GRID)]]
        else:
            meters = [m for m in self.meters if m["resource_id"] == res["id"]]
            measured = [m for m in meters if m["mode"] != "estimate"]
            if measured:
                groups = [[self.signals["id"].get(sid) for sid in self.meter_signal_ids(m)] for m in measured]
            else:  # лише оцінні лічильники: свіжий — якщо є недавній побудований слот
                stub = {"last_ts": self.now, "last_quality": None, "period_s": 3600}
                groups = [[stub if m["id"] in self.last_slots else None] for m in meters]
        fresh = [bool(g) and all(self.is_fresh(s) for s in g) for g in groups]
        stamps = [s["last_ts"] for g in groups for s in g if s and s["last_ts"]]
        age = int((self.now - max(stamps)).total_seconds()) if stamps else None
        if not any(fresh):
            return "stale", age
        return ("ok" if all(fresh) else "partial"), age

    # --- вкладки, підписи, підсумок (R-12) ------------------------------------------------------------------
    def tabs_and_total(self):
        tabs, total, names, derived = [], 0, [], []
        for res in self.resources:
            rate = self.rate_now(res)
            value = r_int(rate) if res["code"] == "el" else r_rate(rate, res["code"])
            cost = self.cost_today(res)
            sub = ("%s %s" % (t_rate(value), res["rate_label"])) if value is not None else "—"
            tab = {"code": res["code"], "name": res["name"], "rate": value, "rate_unit": res["rate_label"]}
            if res["show_tab_cost"] and self.cost and res["price_source"] not in ("derived_gas", "none"):
                tab["cost_uah"] = r_int(cost)
                sub += " · %s ₴" % (fmt_int(cost) if cost is not None else "—")
            elif res["source_note"]:
                sub += " · " + res["source_note"]
            tab["sub"] = sub
            tabs.append(tab)
            if res["is_derived"]:
                derived.append(res["name"])
            else:
                names.append(res["name"])
                total += r_int(cost) or 0  # сума округлених вартостей вкладок (65 156 = 52 786 + 12 118 + 252)
        if self.cost:
            text = "Сьогодні разом: %s ₴ · %s." % (fmt_int(total), ", ".join(names))
            if derived:
                text += " Похідні не додаються: %s." % ", ".join(derived)
            return tabs, {"cost_uah": total, "text": text}
        return tabs, {"text": "Сьогодні: %d %s" % (len(tabs), plural_resources(len(tabs)))}

    # --- нічна й денна витрата (R-09) -----------------------------------------------------------------------
    @cached_property
    def shift_windows(self):
        return shifts.load_windows(self.sudo)

    def day_windows(self):
        """Вікна змін `[(from_utc, to_utc)]` для `day_mean`: сьогодні (до `now`), якщо зміна вже почалась, інакше
        останній робочий день (≤ 7 діб)."""
        for back in range(8):
            wins = self.shift_windows.windows_for(self.today - timedelta(days=back))
            if not wins or (back == 0 and self.now <= wins[0][1]):
                continue
            return [(a, min(b, self.now)) for _name, a, b in wins if a < self.now]
        return []

    def window(self, res):
        """Єдиний запит слотів джерел: `(by_ts, night, day_mean)`; `by_ts` — `{ts_start: Σ rate_avg}` від початку
        нічного вікна й вікон змін до `now`; `night` — мінімум нічного вікна (покриття < 70 % — `None`)."""
        key = ("window", res["code"])
        if key not in self._cache:
            meters = tuple(m["id"] for m in self.supply_meters(res))
            n_lo, n_hi = self.shift_windows.night_window(self.today)
            n_hi = min(n_hi, self.now)
            day_wins = self.day_windows()
            lo = min([self.day0, n_lo] + [a for a, _b in day_wins])
            by_ts = {}
            if meters:
                self.cr.execute(WINDOW_SQL, (lo.date() - timedelta(days=1), meters, lo, self.now))
                by_ts = {ts: rate or 0.0 for ts, rate in self.cr.fetchall()}
            expected = math.ceil((n_hi - n_lo).total_seconds() / 900) if n_hi > n_lo else 0
            night_vals = [v for ts, v in by_ts.items() if n_lo <= ts < n_hi]
            night = min(night_vals) if expected and len(night_vals) / expected >= NIGHT_COVERAGE else None
            day_vals = [v for ts, v in by_ts.items() if any(a <= ts < b for a, b in day_wins)]
            self._cache[key] = (by_ts, night, sum(day_vals) / len(day_vals) if day_vals else None)
        return self._cache[key]

    # --- ctx для хуків моста (C-04) -------------------------------------------------------------------------
    def make_ctx(self, res):
        """Контекст хуків: `rate` — швидкість ресурсу зараз, `rates` — `{код точки: швидкість}`, `qty_today`,
        `points` — активні точки ресурсу, `screen` — цей об'єкт (сирі агрегати)."""
        points = self.points[res["id"]] if res["code"] != "el" else []
        return {
            "env": self.env,
            "now": self.now,
            "today": self.today,
            "cost": self.cost,
            "resource": res,
            "rate": self.rate_now(res),
            "rates": {p["code"]: self.point_rate(p) for p in points},
            "qty_today": self.qty_today(res) if res["code"] != "el" else self.el["import"],
            "points": points,
            "screen": self,
        }

    # --- відповідь -------------------------------------------------------------------------------------------
    def build(self):
        if self.code and self.code not in self.by_code:
            raise UserError(self.env._("Невідомий ресурс: %s.", self.code))
        res = self.by_code[self.code] if self.code else (self.resources[0] if self.resources else None)
        self.focus = res
        tabs, total = self.tabs_and_total() if res else ([], {})
        state, age = self.state_of(res) if res else ("stale", None)
        meta = {
            "now": self.now.replace(microsecond=0).isoformat(),
            "now_local": dates.to_local(self.now).strftime("%H:%M"),
            "data_state": state,
            "age_s": age,
            "refresh_s": int(param_float(self.env, "pult_refresh_s", 30)),
            "control_available": self.sudo["td.energy.advice"]._td_control_available(),
            "capabilities": {"export": True, "manage": self.manager},
            "total": total,
        }
        if self.cost:
            meta["capabilities"]["cost"] = True
        out = {"meta": meta, "tabs": tabs, "resource": self.resource_block(res) if res else None}
        return out if self.cost else strip_cost(out)

    def part(self, name, fn, *args):
        """Частина відповіді: збій не ламає решту (розд. 11) — у режимі повтору (`isolate`, під savepoint)."""
        if not self.isolate:
            return fn(*args)
        try:
            with self.cr.savepoint():
                return fn(*args)
        except Exception as exc:
            _logger.exception("td_energy_resources: частина екрана %s", name)
            return {"error": str(exc) or exc.__class__.__name__}

    def resource_block(self, res):
        ctx = self.make_ctx(res)
        kpis = self.part("kpis", self.kpis, res, ctx)
        lst = self.part("list", self.list_block, res, ctx)  # перед графіком: підпис «Куди йде тепло»
        block = {"code": res["code"], "name": res["name"], "color": res["color"], "kpis": kpis}
        block["chart"] = self.part("chart", self.chart, res, ctx)
        block["list"] = lst
        block["notes"] = self.part("notes", self.notes, res)
        extra = self.part("extra", self.hooks._td_resource_extra, res["code"], ctx)
        for key, value in (extra if isinstance(extra, dict) else {}).items():
            block.setdefault(key, value)
        return block

    # --- KPI (R-09) ------------------------------------------------------------------------------------------
    def kpis(self, res, ctx):
        builder = getattr(self, "kpis_" + res["code"], None) or self.kpis_generic
        items = builder(res, ctx)
        if res["code"] == "heat":
            by_id = {k["id"]: k for k in items}
            for extra in self.hooks._td_heat_kpis(ctx) or []:
                if extra.get("id") in by_id:
                    by_id[extra["id"]].update({k: v for k, v in extra.items() if k != "id"})
                else:
                    items.append(extra)
        return items

    def cost_note(self, cost, price=None, unit=""):
        """«{cost} ₴ · {price} ₴/{unit}» — лише з групою вартості."""
        if not self.cost:
            return ""
        text = "%s ₴" % (fmt_int(cost) if cost is not None else "—")
        if price is not None:
            text += " · %s ₴/%s" % (fmt_dec(price, 2), unit)
        return text

    def kpis_generic(self, res, ctx):
        code, rate = res["code"], ctx["rate"]
        return [
            kpi("rate", "Витрата зараз", r_rate(rate, code), res["rate_label"]),
            kpi(
                "today", "Сьогодні", r_day(self.qty_today(res)), res["uom_label"], self.cost_note(self.cost_today(res))
            ),
        ]

    def kpis_el(self, res, ctx):
        el, tariff = self.el, self.tariff
        contract, warn = self.contract_kw, (tariff.peak_warn_pct if tariff else 90.0)
        kw = el["grid_kw"]
        pct = kw / contract * 100 if kw is not None and contract else None
        price = self.sudo["td.energy.tariff"]._td_price_at(self.now, tariff=tariff)[1] if self.cost else None
        gen, load = el["gen"], el["load"]

        def share(part):
            return fmt_int(part / gen * 100) if gen else "0"

        self.cr.execute(REACT_SQL, (self.today,))
        q_sum, q_rows = self.cr.fetchone()
        react = react_stats(
            q_sum, el["p_in"], tariff.tg_phi_limit if tariff else 0.0, tariff.react_rate if tariff else 0.0
        )
        if not q_rows or react["tg"] is None:
            react_note = "—"
        else:
            react_note = "tg φ %s%s" % (fmt_dec(react["tg"], 2), " · ризик доплати" if react["risk"] else "")
        grid_note = "%s %% договірної %s кВт" % (fmt_int(pct), fmt_int(contract)) if pct is not None else "—"
        gen_note = "СЕС %s %% · КГУ %s %% · частка %s %%" % (
            share(el["pv"]),
            share(el["chp"]),
            fmt_int(gen / load * 100) if load else "0",
        )
        return [
            kpi(
                "grid_now",
                "З мережі зараз",
                r_int(kw),
                res["rate_label"],
                grid_note,
                "neutral" if pct is None else ("bad" if pct >= warn else "good"),
            ),
            kpi(
                "today",
                "Сьогодні з мережі",
                r_int(el["import"]),
                res["uom_label"],
                self.cost_note(el["cost"], price, res["uom_label"]),
            ),
            kpi("generation", "Власна генерація", r_int(gen), res["uom_label"], gen_note, "good"),
            kpi(
                "reactive",
                "Реактивна енергія",
                r_int(q_sum) if q_rows else None,
                "квар·год",
                react_note,
                "bad" if react["risk"] else "neutral",
            ),
        ]

    def kpis_gas(self, res, ctx):
        rate, today = ctx["rate"], self.qty_today(res)
        rates = {p["code"]: ctx["rates"].get(p["code"]) for p in ctx["points"] if p["kind"] == "consumer"}
        top = max((c for c, v in rates.items() if v is not None), key=lambda c: rates[c], default=None)
        note = []
        if top is not None and rates[top] > 0:
            note.append("котельня %s" % top)
        chp = self.sig_text(SIG_CHP)
        if chp:
            note.append("КГУ працює" if chp == "running" else "КГУ стоїть")
        price = self.sudo["td.energy.price"]._td_price_at(res["code"], self.today) if self.cost else None
        out = [
            kpi("rate", "Витрата зараз", r_rate(rate), res["rate_label"], " · ".join(note)),
            kpi(
                "today",
                "Сьогодні",
                r_day(today),
                res["uom_label"],
                self.cost_note(self.cost_today(res), price, res["uom_label"]),
            ),
        ]
        if res["daily_limit"] > 0:
            used = today / res["daily_limit"] * 100
            out.append(
                kpi(
                    "limit",
                    "Ліміт доби за договором",
                    r_day(res["daily_limit"]),
                    res["uom_label"],
                    "використано %s %%" % fmt_int(used),
                    "bad" if used >= 90 else "good",
                )
            )
        norm = rparam_float(self.env, "boiler_eff_norm", 90.0)
        eff = None
        boiler = [m for m in self.meters if m["code"] == "GM-BOILER"]
        heat = [m for m in self.meters if m["code"] == "HM-BOILER"] or self._heat_boiler()
        gas_qty = self.qty_today(res, boiler) if boiler else 0.0
        if boiler and heat and gas_qty > 0 and res["kwh_per_unit"]:
            eff = 100.0 * sum(self.today_rows.get(m["id"], (0.0,))[0] for m in heat) / (gas_qty * res["kwh_per_unit"])
        out.append(
            kpi(
                "eff",
                "ККД котельні",
                None if eff is None else round(eff, 1),
                "%",
                "норма ≥ %s %%" % fmt_auto(norm),
                "neutral" if eff is None else ("good" if eff >= norm else "bad"),
                "estimated",
            )
        )
        return out

    def _heat_boiler(self):
        """Теплосчётчик котельні `HM-BOILER` (створює міст): лічильники ресурсу `heat` за кодом."""
        heat = self.by_code.get("heat")
        return [m for m in self.meters if heat and m["resource_id"] == heat["id"] and m["code"] == "HM-BOILER"]

    def kpis_heat(self, res, ctx):
        return [
            kpi("power", "Теплова потужність", r_rate(ctx["rate"], "heat"), res["rate_label"], "—"),
            kpi("today", "Сьогодні", r_int(self.qty_today(res)), res["uom_label"], "теплобаланс BMS"),
        ]

    def kpis_air(self, res, ctx):
        flow, pressure = ctx["rate"], self.sig_value(SIG_PRESSURE)
        setpoint, from_params = self.sig_value(SIG_SETPOINT), False
        if setpoint is None:
            setpoint, from_params = rparam_float(self.env, "air_setpoint_bar", 0.0) or None, True
        parts = []
        if pressure is not None:
            parts.append("тиск %s бар" % fmt_auto(pressure))
        if setpoint is not None:
            parts.append("уставка %s%s" % (fmt_auto(setpoint), " (задана в налаштуваннях)" if from_params else ""))
        p_now = self.sig_value(SIG_COMPRESSOR)
        spec = p_now / flow if p_now is not None and flow is not None and flow >= 1 else None
        spec_norm = rparam_float(self.env, "air_spec_norm", 6.0)
        kwh, cost = self.node_cost(res)
        _by_ts, night, day = self.window(res)
        share = night / day * 100 if night is not None and day else None
        return [
            kpi("rate", "Витрата зараз", r_rate(flow), res["rate_label"], " · ".join(parts) or "—"),
            kpi(
                "spec",
                "Питома потужність",
                None if spec is None else round(spec, 1),
                "кВт/(%s)" % res["rate_label"],
                "норма ≤ %s" % fmt_auto(spec_norm),
                "neutral" if spec is None else ("good" if spec <= spec_norm else "bad"),
            ),
            kpi("today_el", "Сьогодні електрики", r_int(kwh), "кВт·год", self.cost_note(cost)),
            kpi(
                "night_leak",
                "Витоки вночі",
                r_rate(night),
                res["rate_label"],
                "—" if share is None else "%s %% від денної витрати" % fmt_int(share),
                "neutral" if share is None else ("bad" if share > 10 else "good"),
            ),
        ]

    def kpis_water(self, res, ctx):
        _by_ts, night, _day = self.window(res)
        night_norm = rparam_float(self.env, "water_night_norm", 0.05)
        makeup_norm = rparam_float(self.env, "boiler_makeup_norm", 0.5)
        out = [
            kpi("rate", "Витрата зараз", r_rate(ctx["rate"], "water"), res["rate_label"], "основний ввід"),
            kpi(
                "today", "Сьогодні", r_day(self.qty_today(res)), res["uom_label"], self.cost_note(self.cost_today(res))
            ),
            kpi(
                "night",
                "Нічна витрата",
                r_rate(night, "water"),
                res["rate_label"],
                "норма ≤ %s" % fmt_auto(night_norm),
                "neutral" if night is None else ("good" if night <= night_norm else "bad"),
            ),
        ]
        boiler = [m for m in self.meters if m["code"] == "WM-BOILER"]
        if boiler:
            qty = self.qty_today(res, boiler)
            out.append(
                kpi(
                    "boiler",
                    "Підживлення котельні",
                    r_day(qty),
                    res["uom_label"],
                    "норма ≤ %s м³/добу" % fmt_auto(makeup_norm),
                    "good" if qty <= makeup_norm else "bad",
                )
            )
        return out

    # --- графік доби (R-10) ----------------------------------------------------------------------------------
    def chart(self, res, ctx):
        code, series = res["code"], [None] * SLOTS
        live, night, day = ctx["rate"], None, None
        if code == "el":
            series = [None if v is None else round(v, 1) for v in self.el["grid"]]
        else:
            by_ts, night, day = self.window(res)
            for ts, value in sorted(by_ts.items()):
                if self.day0 <= ts < self.day1:
                    series[dates.local_slot_index(ts)] = round(value, 2 if abs(value) < 1 else 1)
        for i in range(self.now_slot, SLOTS):
            series[i] = None  # слоти після `now_slot` — `null`; сам `now_slot` — живе значення
        series[self.now_slot] = (
            None if live is None else (round(live, 1) if code == "el" else round(live, 2 if abs(live) < 1 else 1))
        )
        limit = None
        if res["limit_kind"] == "tariff_contract":
            limit = self.contract_kw or None
        elif res["limit_kind"] == "fixed":
            limit = res["rate_limit"] or None
        y_max, ticks = axis(series, limit)
        peak_idx = max((i for i, v in enumerate(series) if v is not None), key=lambda i: series[i], default=None)
        peak = (
            None if peak_idx is None else (r_int(series[peak_idx]) if code == "el" else r_rate(series[peak_idx], code))
        )
        foot_vars = {
            "peak": None if peak is None else t_rate(peak),
            "peak_kw": None if peak is None else t_rate(peak),
            "peak_time": None if peak_idx is None else "%02d:%02d" % (peak_idx // 4, peak_idx % 4 * 15),
        }
        foot_vars.update(self.foot_extra(res, ctx, night, day))
        return {
            "title": res["chart_title"],
            "note": self.chart_note(res, ctx, limit),
            "unit": res["rate_label"],
            "y_max": y_max,
            "ticks": ticks,
            "step_min": 15,
            "now_slot": self.now_slot,
            "series": series,
            "limit": None if limit is None else num(limit),
            "foot": render_foot(res["foot_template"], foot_vars),
        }

    def chart_note(self, res, ctx, limit):
        note = res["chart_note"] or ""
        if "{capacity}" in note:
            capacity = self.hooks._td_heat_chart_note(ctx) if res["code"] == "heat" else None
            if capacity in (None, ""):
                note = re.sub(r"\s*·\s*[^·{}]*\{capacity\}[^·{}]*", "", note)
            else:
                note = note.replace("{capacity}", str(capacity))
        note = note.replace("{limit}", t_rate(r_rate(limit, res["code"])) if limit else "—")
        return note.replace("{contract}", fmt_int(self.contract_kw) if res["code"] == "el" else "—")

    def foot_extra(self, res, ctx, night, day):
        """Змінні `foot_template` (R-10 п. 5), що залежать від ресурсу; `None` — немає даних (речення опускається)."""
        code, extra = res["code"], {}
        if code == "el":
            first, export = self.el["first_export"], self.el["export"]
            local = dates.to_local(first).strftime("%H:%M") if first else None
            extra["export_sentence"] = (
                " З %s частина енергії СЕС віддавалась у мережу (%s кВт·год)." % (local, fmt_int(export))
                if export > 0 and local
                else ""
            )
            return extra
        extra["night"] = None if night is None else t_rate(r_rate(night, code))
        extra["day"] = None if day is None else t_rate(r_rate(day, code))
        items = self._cache.get("list_items")
        if code == "heat" and items:
            top, total = items[0], sum(i["value"] or 0.0 for i in items)
            extra["top_name"] = top["name"]
            extra["top_share"] = fmt_int((top["value"] or 0.0) / total * 100) if total else None
        elif code == "heat":
            extra["top_name"] = extra["top_share"] = None
        share = night / day * 100 if night is not None and day else None
        if code == "air":
            if share is None:
                extra["leak_sentence"] = None
            elif share > 10:
                extra["leak_sentence"] = "Вночі витрата %s м³/хв — це витоки в мережі." % extra["night"]
            else:
                extra["leak_sentence"] = "Нічна витрата %s м³/хв в межах норми." % extra["night"]
        if code == "water":
            norm = rparam_float(self.env, "water_night_norm", 0.05)
            if night is None:
                extra["norm_sentence"] = None
            else:
                extra["norm_sentence"] = "в нормі" if night <= norm else "вища за норму %s" % fmt_auto(norm)
        return extra

    # --- список «Споживачі» й баланс (R-11) -------------------------------------------------------------------
    def list_block(self, res, ctx):
        code = res["code"]
        basis = "rate" if code == "el" else (res["list_basis"] or "rate")
        unit = res["rate_label"] if basis == "rate" else res["uom_label"]
        block = {"title": res["list_title"], "basis": basis, "unit": unit, "items": [], "unaccounted": None}
        if code == "el":
            self.cr.execute(TOP_SQL)
            entries = [(c, n, kw, "measured") for c, n, kw in self.cr.fetchall()]
        else:
            entries = self.list_entries(res, ctx, basis)
        entries.sort(key=lambda e: (e[2] is None, -(e[2] or 0.0), e[0]))
        top = max((e[2] or 0.0 for e in entries), default=0.0)
        items = [
            {
                "code": c,
                "name": n,
                "value": self.round_value(code, basis, v),
                "share": round((v or 0.0) / top, 3) if top else 0.0,
                "quality": q,
            }
            for c, n, v, q in entries
        ]
        self._cache["list_items"] = items
        block["items"] = items[:MAX_LIST]
        if code != "el":
            block["unaccounted"] = self.balance(res, ctx, basis, sum(e[2] or 0.0 for e in entries))
        return block

    @staticmethod
    def round_value(code, basis, v):
        if code == "el":
            return r_int(v)
        return r_rate(v, code) if basis == "rate" else r_day(v)

    def list_entries(self, res, ctx, basis):
        """`[(code, name, value, quality)]` споживачів: хук моста (тепло) або активні точки `consumer`."""
        hooked = self.hooks._td_heat_list(ctx) if res["code"] == "heat" else None
        if hooked is not None:
            return [
                (i["code"], i.get("name") or i["code"], i.get("value"), i.get("quality", "measured")) for i in hooked
            ]
        entries = []
        for p in self.points[res["id"]]:
            if p["kind"] != "consumer":
                continue
            if basis == "rate":
                value = ctx["rates"].get(p["code"])
            else:
                value = sum(self.today_rows.get(m["id"], (0.0,))[0] for m in self.point_meters[p["id"]])
            entries.append((p["code"], p["name"], value, "measured" if p["estimate_method"] == "none" else "estimated"))
        return entries

    def balance(self, res, ctx, basis, consumers):
        """R-11 п. 3: `unaccounted = Σ source − Σ consumer`; нема `source`-точки або даних вводу — `None`."""
        sources = self.sources(res)
        if not sources:
            return None
        src = (
            ctx["rate"]
            if basis == "rate"
            else self.qty_today(res, [m for p in sources for m in self.point_meters[p["id"]]])
        )
        if src is None:
            return None
        value = src - consumers
        pct = value / src * 100 if src else 0.0
        out = {"value": self.round_value(res["code"], basis, value), "pct": round(pct, 1) + 0.0}
        if pct < -5:
            out["inconsistent"] = True
        return out

    # --- заметки з резервів (API-02) ---------------------------------------------------------------------------
    def notes(self, res):
        """Відкриті резерви ресурсу (W3-B `td.energy.opportunity.get_list`); моделі/методу немає — порожньо."""
        if "td.energy.opportunity" not in self.env:
            return []
        model = self.env["td.energy.opportunity"]
        if not hasattr(model, "get_list"):
            return []
        out = []
        for item in model.get_list(resource_code=res["code"], states=("open",)).get("items", []):
            note = {"id": item["id"], "title": item["title"], "text": item["text"]}
            if "save_uah_month" in item:
                note["save_uah_month"] = item["save_uah_month"]
            note["actions"] = item.get("actions", [])
            out.append(note)
        return out
