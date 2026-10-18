"""R-03: інтеграл витрати (`flow_integrate`) і лічильник-накопичувач (`counter`) на слот. Чисті функції без ORM.

Час — `datetime` (UTC naive); значення — у одиницях ресурсу (`rate_label`). Приклади: SPEC R-03 (газ 11,083 м³,
повітря 147,5 норм. м³), AC-08…AC-11.
"""

from odoo.addons.td_energy.tools.counter import Series

MEASURED_COVERAGE = 0.9
COUNTER_QUALITY = {"measured": "measured", "interpolated": "interpolated", "reset": "interpolated"}


def _segments(points, t0, t1, gap_max_s):
    """Відрізки лінійної інтерполяції одного сигналу всередині `[t0, t1]` (секунди від `t0`):
    `(lo, hi, v_lo, v_hi)`; розрив між сусідніми показаннями понад `gap_max_s` — «діра» (відрізка немає)."""
    pts = sorted(((t - t0).total_seconds(), v) for t, v in points if v is not None)
    span = (t1 - t0).total_seconds()
    segs = []
    for (a, va), (b, vb) in zip(pts, pts[1:], strict=False):
        if b <= a or b - a > gap_max_s:
            continue
        lo, hi = max(a, 0.0), min(b, span)
        if hi <= lo:
            continue
        slope = (vb - va) / (b - a)
        segs.append((lo, hi, va + slope * (lo - a), va + slope * (hi - a)))
    return segs


def _segment_at(segs, t):
    for seg in segs:
        if seg[0] <= t <= seg[1]:
            return seg
    return None


def flow_slot(signals_points, t0, t1, rate_hour_factor=1.0, gap_max_s=900.0, min_coverage=0.3):
    """R-03 `flow_integrate`: `signals_points` — список рядів `[(ts, value)]` (по одному на сигнал `flow_signal_ids`;
    показання `[t0 − gap_max, t1 + gap_max]`). Сума `F(t) = Σ_k f_k(t)` визначена лише там, де визначені всі `f_k`.

    Повертає `{"qty", "rate_avg", "coverage", "quality"}`; `coverage < min_coverage` — `qty = 0`, `missing`.
    """
    span = (t1 - t0).total_seconds()
    seg_lists = [_segments(points, t0, t1, gap_max_s) for points in signals_points]
    if not seg_lists:
        return {"qty": 0.0, "rate_avg": 0.0, "coverage": 0.0, "quality": "missing"}
    nodes = {0.0, span}
    for segs in seg_lists:
        for lo, hi, _a, _b in segs:
            nodes.update((lo, hi))
    nodes = sorted(nodes)
    covered = area = 0.0
    for u, v in zip(nodes, nodes[1:], strict=False):
        mid = (u + v) / 2.0
        found = [_segment_at(segs, mid) for segs in seg_lists]
        if any(seg is None for seg in found):
            continue
        f_u = f_v = 0.0
        for lo, hi, v_lo, v_hi in found:
            slope = (v_hi - v_lo) / (hi - lo)
            f_u += v_lo + slope * (u - lo)
            f_v += v_lo + slope * (v - lo)
        covered += v - u
        area += (f_u + f_v) / 2.0 * (v - u)
    coverage = covered / span if span else 0.0
    if coverage < min_coverage or coverage <= 0.0:
        return {"qty": 0.0, "rate_avg": 0.0, "coverage": round(coverage, 4), "quality": "missing"}
    qty = area * rate_hour_factor / 3600.0 / coverage
    return {
        "qty": qty,
        "rate_avg": qty * 4.0 / rate_hour_factor,
        "coverage": coverage,
        "quality": "measured" if coverage >= MEASURED_COVERAGE else "interpolated",
    }


def counter_slot(points, t0, t1, reset_tol=1.0, max_rate=1000.0, gap_max_s=900.0, rate_hour_factor=1.0):
    """R-03 `counter`: `points` — `[(ts, показання)]` у `[t0 − gap_max, t1 + gap_max]` (+ якір до вікна).

    Різниця накопичувача на слот (`Series` з `td_energy/tools/counter.py`): скидання й розрив — `interpolated`,
    немає даних на межах слота — `missing` (`qty = 0`). Повертає `{"qty", "rate_avg", "quality"}`.
    """
    series = Series.build(sorted(points), base=0.0, reset_tol=reset_tol, max_kw=max_rate, gap_max_s=gap_max_s)
    delta, quality = series.delta(t0, t1)
    if delta is None:
        return {"qty": 0.0, "rate_avg": 0.0, "quality": "missing"}
    qty = max(delta, 0.0)
    return {
        "qty": qty,
        "rate_avg": qty * 4.0 / rate_hour_factor,
        "quality": COUNTER_QUALITY.get(quality, "interpolated"),
    }
