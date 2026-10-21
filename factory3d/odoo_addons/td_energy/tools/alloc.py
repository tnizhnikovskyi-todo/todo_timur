"""R-08, R-09: чисті функції розподілу енергії (без ORM). Час — datetime (UTC naive), енергія — кВт·год."""

from datetime import timedelta

SLOT = timedelta(minutes=15)


def clip(start, end, lo, hi):
    """Перетин `[start, end)` з `[lo, hi)`; порожній — None."""
    s, e = max(start, lo), min(end, hi)
    return (s, e) if s < e else None


def merge(intervals):
    """Об'єднання перетинних інтервалів `[(s, e), …]`."""
    out = []
    for s, e in sorted(intervals):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def intersect(a, b):
    """Перетин двох списків інтервалів `[(s, e), …]` (результат — об'єднаний)."""
    return merge(piece for s, e in a for x, y in b if (piece := clip(s, e, x, y)))


def floor15(dt):
    return dt.replace(minute=dt.minute - dt.minute % 15, second=0, microsecond=0)


def segments(wo_intervals):
    """R-08 п. 3: елементарні сегменти `(x, y, [wo_id, …])` між усіма межами інтервалів завдань одного РЦ та
    межами 15-хв сітки (щоб кожен сегмент лежав в одному слоті R-09). `wo_intervals` — {wo_id: [(s, e), …]}."""
    points = set()
    for ivs in wo_intervals.values():
        for s, e in ivs:
            points.update((s, e))
    if not points:
        return []
    lo, hi = min(points), max(points)
    edge = floor15(lo) + SLOT
    while edge < hi:
        points.add(edge)
        edge += SLOT
    pts = sorted(points)
    result = []
    for x, y in zip(pts, pts[1:], strict=False):
        active = sorted(wo for wo, ivs in wo_intervals.items() if any(s <= x and y <= e for s, e in ivs))
        if active:
            result.append((x, y, active))
    return result


def estimate_kwh(p_inst_kw, load_factor, seconds):
    """R-08 п. 4: `p_inst_kw × load_factor × секунди / 3600`."""
    return (p_inst_kw or 0.0) * (load_factor or 0.0) * seconds / 3600.0


def norm_quality(q):
    """Якість ряду R-03 → якість сегмента розподілу: `reset` — як `interpolated`."""
    return "interpolated" if q in ("reset", "missing") else q


def row_quality(qualities):
    """R-08 п. 6: усі `measured` → `measured`; є `interpolated` → `interpolated`; усі `estimate` → `estimate`;
    суміш оцінки з виміряним/інтерпольованим → `partial`. Порожньо — `estimate`."""
    qs = {norm_quality(q) for q in qualities}
    if not qs or qs == {"estimate"}:
        return "estimate"
    if "estimate" in qs:
        return "partial"
    return "interpolated" if "interpolated" in qs else "measured"


def pool_shares(pool_kwh, drivers):
    """R-09 п. 4: `{ключ: pool_kwh × D / ΣD}`; `ΣD ≤ 0` — порожній словник."""
    total = sum(d for d in drivers.values() if d > 0)
    if total <= 0:
        return {}
    return {k: pool_kwh * d / total for k, d in drivers.items() if d > 0}


def slots(lo, hi):
    """Слоти 15-хв сітки, що перетинають `[lo, hi)`, обрізані `[lo, hi)`: `[(a, b), …]`."""
    out, a = [], floor15(lo)
    while a < hi:
        piece = clip(a, a + SLOT, lo, hi)
        if piece:
            out.append(piece)
        a += SLOT
    return out
