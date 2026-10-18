"""Освітлення: чисті функції (R-02…R-06). Без ORM — тестуються окремо."""

import math
import re

DEFAULT_FIX = {"highbay": (24000, 160), "highbay_rack": (19000, 130)}  # plant/lighting.py:DEFAULT_FIX
LINE_CAPACITY = 64
LIVE_STATUSES = ("ok", "warn", "alarm")

_DEV_RE = re.compile(r"^@(\d{1,3})\.(\d{1,3})\.(\d{1,2})\.(\d{1,2})(?:-(\d{1,2}))?$")


def round_half_up(x):
    return int(math.floor(x + 0.5))


def n_required(lux, area, lumen, uf, mf):
    """R-03: max(1, ⌈E·A / (Φ·UF·MF)⌉)."""
    den = lumen * uf * mf
    if area <= 0 or den <= 0:
        return 1
    return max(1, int(math.ceil(round(lux * area / den, 9))))


def e_calc_raw(n, lumen, uf, mf, area):
    """R-04: E = N·Φ·UF·MF / A."""
    if area <= 0:
        return 0.0
    return n * lumen * uf * mf / area


def design(lux, area, lumen, watt, n, uf, mf):
    """R-03/R-04: (n_required, e_calc_raw, e_calc, design_ok, p_inst_kw)."""
    n_req = n_required(lux, area, lumen, uf, mf)
    raw = e_calc_raw(n, lumen, uf, mf, area)
    ok = n >= n_req and raw >= lux
    return n_req, raw, round_half_up(raw), ok, round(n * watt / 1000.0, 2)


def parse_devices(text):
    """R-06: `@c.r.s.d1-d2[;…]` → [(c, r, s, d1, d2)]; невалідне → ValueError."""
    items = []
    for part in (text or "").split(";"):
        part = part.strip()
        m = _DEV_RE.match(part)
        if not m:
            raise ValueError("некоректний елемент «%s» (очікується @кластер.роутер.лінія.пристрій[-пристрій])" % part)
        c, r, s, d1, d2 = int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5] or m[4])
        if not (1 <= c <= 253 and 1 <= r <= 254):
            raise ValueError("кластер 1…253, роутер 1…254 («%s»)" % part)
        if not 1 <= s <= 4:
            raise ValueError("лінія 1…4 («%s»)" % part)
        if not (1 <= d1 <= d2 <= LINE_CAPACITY):
            raise ValueError("пристрої 1…64 за зростанням («%s»)" % part)
        items.append((c, r, s, d1, d2))
    return items


def count_devices(items):
    return sum(d2 - d1 + 1 for _c, _r, _s, d1, d2 in items)


def pack_dali(groups, cluster=1, router=1):
    """R-06: розклад груп щита по лініях. groups = [(code, n)] у порядку каталогу → {code: 'dali_devices'}."""
    res, line, used = {}, 1, 0
    for code, n in groups:
        if used > 0 and n > LINE_CAPACITY - used:
            line, used = line + 1, 0
        segs, left = [], n
        while left > 0:
            take = min(left, LINE_CAPACITY - used)
            a, b = used + 1, used + take
            segs.append("@%d.%d.%d.%d%s" % (cluster, router, line, a, "" if a == b else "-%d" % b))
            used += take
            left -= take
            if used == LINE_CAPACITY and left > 0:
                line, used = line + 1, 0
        res[code] = ";".join(segs)
    return res


def is_live(status):
    return status in LIVE_STATUSES


def plan_state(faults, deviation, stale, level_pct, check_norm, e_now_raw, e_norm, tol):
    """R-05 п. 7."""
    if faults > 0:
        return "fault"
    if deviation in ("off_in_work", "below_norm"):
        return "alarm"
    if stale:
        return "nodata"
    if level_pct < 1:
        return "off"
    if check_norm and e_now_raw < e_norm * (1 - tol):
        return "low"
    return "ok"


DEVIATION_BY_TEXT = {
    "норма": "none",
    "поза робочим часом": "off_hours",
    "вимкнено в робочий час": "off_in_work",
    "нижче норми": "below_norm",
    "немає даних": "no_data",
    "немає мережі (живлення від резерву)": "no_mains",
}
