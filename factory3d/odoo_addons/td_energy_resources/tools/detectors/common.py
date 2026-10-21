"""Детектори резервів: R-14 — вікна, ціни, `K_month`, схема параметрів, спільні вибірки (W3-B).

Вікно `L = rule.lookback_days` **повних** київських діб, що закінчується вчора. Мало даних (менше 70 % слотів
потрібних рядів або менше 3 діб) — детектор повертає `[]`. Ціна енергії — зважена `Σ(kwh·price)/Σ kwh`; місяць —
`K_month(L) = weeks_per_month × 7 / L`. Усі читання — сирим SQL: ціни й вартість лежать у полях групи вартості, а
детектор працює від імені крона (або енергетика через `sudo`).
"""

from datetime import timedelta

from odoo.addons.td_energy.tools import dates, tariff as tariff_tools

from .. import shifts
from ..build import rparam_float
from ..resource_data import fmt_auto, fmt_dec, fmt_int  # noqa: F401  (R-25: числа в текстах знахідок)

SLOT = dates.SLOT
MIN_COVERAGE = 0.7  # R-14: частка слотів потрібних рядів
MIN_DAYS = 3  # R-14: мінімум діб з даними
MAX_TEXT = 400

READINGS_SQL = """
SELECT signal_id, ts, value FROM td_reading
 WHERE signal_id IN %s AND quality <> 'bad' AND ts >= %s AND ts <= %s ORDER BY signal_id, ts
"""
NODE_SLOTS_SQL = """
SELECT ts_start, SUM(kwh), SUM(kwh * COALESCE(price, 0))
  FROM td_energy_interval
 WHERE role = %s AND node_id IN %s AND quality <> 'missing' AND ts_start >= %s AND ts_start < %s
 GROUP BY ts_start ORDER BY ts_start
"""
RES_SLOTS_SQL = """
SELECT ts_start, SUM(rate_avg), SUM(qty) FROM td_energy_res_interval
 WHERE metric = 'main' AND meter_id IN %s AND quality <> 'missing' AND day >= %s AND day <= %s
   AND ts_start >= %s AND ts_start < %s
 GROUP BY ts_start ORDER BY ts_start
"""


class DetectorNote(Exception):
    """Інформаційна відмова детектора (не збій): знахідок немає, текст іде в `rule.last_error` (R-19)."""


def rule_params(rule):
    """Параметри правила: `default` зі `params_schema`, перекриті `rule.params`."""
    out = {item["key"]: item.get("default") for item in rule.params_schema or [] if item.get("key")}
    out.update(rule.params or {})
    return out


def check_params(schema, params):
    """M-09 `_check_params`: `[(key, type, min, max)]` порушених ключів схеми (немає, не той тип, поза діапазоном)."""
    effective = {item["key"]: item.get("default") for item in schema or [] if item.get("key")}
    effective.update(params or {})
    bad = []
    for item in schema or []:
        key, kind = item.get("key"), item.get("type")
        value = effective.get(key)
        lo, hi = item.get("min"), item.get("max")
        if kind == "bool":
            ok = isinstance(value, bool)
        elif kind == "int":
            ok = isinstance(value, int) and not isinstance(value, bool)
        elif kind == "float":
            ok = isinstance(value, (int, float)) and not isinstance(value, bool)
        else:
            ok = False
        if ok and kind != "bool":
            ok = (lo is None or value >= lo) and (hi is None or value <= hi)
        if not ok:
            bad.append((key, kind, lo, hi))
    return bad


def k_month(env, days):
    """R-14: переведення суми за вікно `days` діб у місяць."""
    return rparam_float(env, "weeks_per_month") * 7.0 / max(int(days), 1)


class Window:
    """Вікно детектора: київські доби `days`, межі `[lo, hi)` в UTC, зміни R-21, `K_month`."""

    def __init__(self, env, rule, now):
        self.env = env
        self.length = max(1, int(rule.lookback_days or 7))
        today = dates.local_day(now)
        self.days = [today - timedelta(days=n) for n in range(self.length, 0, -1)]
        self.lo = dates.local_day_bounds(self.days[0])[0]
        self.hi = dates.local_day_bounds(self.days[-1])[1]
        self.shifts = shifts.load_windows(env)
        self.k_month = k_month(env, self.length)
        self.expected_slots = max(1, round((self.hi - self.lo) / SLOT))

    def is_shift(self, ts):
        return self.shifts.is_shift(dates.to_local(ts))

    def sparse(self, stamps):
        """R-14: менше 70 % слотів або менше 3 діб з даними."""
        stamps = list(stamps)
        if len(stamps) / self.expected_slots < MIN_COVERAGE:
            return True
        return len({dates.local_day(ts) for ts in stamps}) < MIN_DAYS

    def shift_hours(self):
        """Робочі години вікна за календарем змін (R-21): `Σ (to − from)` усіх змін усіх діб."""
        total = 0.0
        for day in self.days:
            for _name, a, b in self.shifts.windows_for(day):
                total += (b - a).total_seconds() / 3600.0
        return total

    def work_days(self):
        """Доби вікна, у які є хоча б одна зміна."""
        return [day for day in self.days if self.shifts.windows_for(day)]


def zone_price_at(env, now):
    """`ts (UTC naive) → ₴/кВт·год` за зонами тарифу, чинного на `now`; `None`, якщо тарифу чи зон немає або слот поза
    зонами. Прогноз на місяць рахується за поточним зонним тарифом, а не за плоскою ціною історичних слотів."""
    tariff = env["td.energy.tariff"].sudo()._td_tariff_at(now)
    zones = tariff.zone_ids.sorted("sequence") if tariff else None
    if not zones:
        return None
    cache = {}

    def price_at(ts):
        if ts not in cache:
            zone = tariff_tools.zone_for(tariff_tools.to_local(ts), zones)
            cache[ts] = zone.price if zone else None
        return cache[ts]

    return price_at


def node_slots(env, node_ids, role, lo, hi):
    """`[(ts, kwh, kwh·price)]`: сума по вузлах за слот (`td.energy.interval`)."""
    if not node_ids:
        return []
    env.cr.execute(NODE_SLOTS_SQL, (role, tuple(node_ids), lo, hi))
    return [(ts, kwh or 0.0, kp or 0.0) for ts, kwh, kp in env.cr.fetchall()]


def res_slots(env, meter_ids, win):
    """`[(ts, rate_avg, qty)]`: сума по лічильниках за слот (`td.energy.res.interval`, `metric='main'`)."""
    if not meter_ids:
        return []
    env.cr.execute(RES_SLOTS_SQL, (tuple(meter_ids), win.days[0], win.days[-1], win.lo, win.hi))
    return [(ts, rate or 0.0, qty or 0.0) for ts, rate, qty in env.cr.fetchall()]


def readings(env, signal_ids, lo, hi):
    """`{signal_id: [(ts, value)]}` сирих показань (без `bad`) у `[lo, hi]`; порожні сигнали — порожні списки."""
    out = {sid: [] for sid in signal_ids}
    ids = tuple(sid for sid in signal_ids if sid)
    if ids:
        env.cr.execute(READINGS_SQL, (ids, lo, hi))
        for sid, ts, value in env.cr.fetchall():
            out[sid].append((ts, value))
    return out


def signal_ids(env, codes):
    """`{code: id}` наявних сигналів (також неактивних)."""
    if not codes:
        return {}
    rows = env["td.signal"].sudo().with_context(active_test=False).search_read([("code", "in", list(codes))], ["code"])
    return {r["code"]: r["id"] for r in rows}


def fresh_value(env, code, now):
    """Свіже `last_value` сигналу за кодом (`last_ts ≥ now − max(3·period_s, 120 с)`, не `bad`) або `None`."""
    sig = env["td.signal"].sudo().with_context(active_test=False).search([("code", "=", code)], limit=1)
    if not sig or not sig.last_ts or sig.last_quality == "bad":
        return None
    if (now - sig.last_ts).total_seconds() > max(3 * (sig.period_s or 60), 120):
        return None
    return sig.last_value


def step_value(points, ts, hold_s):
    """Ступінчасте утримання: останнє значення `≤ ts`, не старше `hold_s` с; інакше `None`. `points` відсортовано."""
    value, found = None, None
    for t, v in points:
        if t > ts:
            break
        value, found = v, t
    if found is None or (ts - found).total_seconds() > hold_s:
        return None
    return value


def step_below(points, t0, t1, threshold, hold_s):
    """Години `[t0, t1)`, коли ступінчасте значення `< threshold`, і покриті години: `(hours_below, hours_covered)`.
    Утримання значення обмежене `hold_s` (розрив понад нього — «немає даних»)."""
    pts = [(t, v) for t, v in points if v is not None]
    below = covered = 0.0
    for i, (t, v) in enumerate(pts):
        nxt = pts[i + 1][0] if i + 1 < len(pts) else t1
        a, b = max(t, t0), min(nxt, t1, t + timedelta(seconds=hold_s))
        if b <= a:
            continue
        seconds = (b - a).total_seconds()
        covered += seconds
        if v < threshold:
            below += seconds
    return below / 3600.0, covered / 3600.0


def weighted(sum_weighted, sum_weights):
    """Зважена ціна `Σ(kwh·price)/Σ kwh`; ваги нульові — `0.0` (знахідка відкидається)."""
    return sum_weighted / sum_weights if sum_weights > 0 else 0.0


def median(values):
    values = sorted(values)
    n = len(values)
    if not n:
        return None
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) / 2.0


def mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def finding(dedup_key, title, text, saving, qty, evidence, node_code=None, point_code=None, actions=None):
    """Знахідка за контрактом R-14; `saving` округлюється до гривні, `text` — до 400 символів. `actions` (необов'язково)
    підміняє `rule.actions` для цієї знахідки (react_section, dock_gates)."""
    item = {
        "dedup_key": dedup_key,
        "title": title,
        "text": text[:MAX_TEXT],
        "est_saving_month": float(round(saving, 0)),
        "est_qty_month": round(qty, 2),
        "evidence": evidence,
        "node_code": node_code,
        "point_code": point_code,
    }
    if actions is not None:
        item["actions"] = actions
    return item
