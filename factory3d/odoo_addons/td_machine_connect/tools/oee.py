"""R-13: OEE за фактом. Чисті функції без `env` (інтервали — пари naive UTC `(start, end)`)."""

from . import ppt

DOWN_KEYS = ("setup", "fault", "idle", "off")


def _isect(a, b):
    """Перетин двох списків інтервалів."""
    return ppt.minus(a, ppt.minus(a, b))


def compute_oee(inp, coverage_min=0.95):
    """Показники OEE за вікно (R-13 п. 1–8, 10).

    `inp`: `ppt`, `planned`, `nodata`, `run`, `run_wo`, `setup`, `fault`, `idle`, `off` — списки інтервалів;
    `pieces` `{wo_id: к-сть}`, `cycles` `{wo_id: хв/шт}`, `bad` (брак, шт), `losses` `[(loss_id, назва, інтервали)]`.
    Повертає словник з іменами полів `td.oee.shift` (без `source`, дат і `computed_at`)."""
    ppt_iv = ppt.union(inp.get("ppt", []))
    planned_iv = _isect(inp.get("planned", []), ppt_iv)
    nodata_iv = ppt.minus(_isect(inp.get("nodata", []), ppt_iv), planned_iv)
    eff = ppt.minus(ppt.minus(ppt_iv, planned_iv), nodata_iv)
    planned_stop = ppt.total_min(planned_iv)
    nodata = ppt.total_min(nodata_iv)
    ppt_min = max(0.0, ppt.total_min(eff))

    def part(key):
        return ppt.total_min(_isect(inp.get(key, []), eff))

    run = part("run")
    run_wo = part("run_wo")
    down = {k: part(k) for k in DOWN_KEYS}
    down_min = sum(down.values())
    pieces = inp.get("pieces", {})
    cycles = inp.get("cycles", {})
    ideal = sum(q * cycles.get(wo, 0.0) for wo, q in pieces.items())
    total = float(sum(pieces.values()))
    bad = min(float(inp.get("bad", 0.0)), total)
    losses = []
    for loss_id, name, ivs in inp.get("losses", []):
        minutes = ppt.total_min(_isect(ivs, eff))
        if minutes > 0:
            losses.append({"loss_id": loss_id, "name": name, "minutes": round(minutes, 1)})
    losses.sort(key=lambda x: -x["minutes"])
    has_data = ppt_min > 0
    den = ppt_min + nodata
    coverage = 1.0 - nodata / den if den > 0 else 1.0
    res = {
        "ppt_min": ppt_min,
        "planned_stop_min": planned_stop,
        "nodata_min": nodata,
        "run_min": run,
        "run_wo_min": run_wo,
        "setup_min": down["setup"],
        "fault_min": down["fault"],
        "idle_min": down["idle"],
        "off_min": down["off"],
        "down_min": down_min,
        "unexplained_min": max(0.0, ppt_min - run - down_min),
        "ideal_min": ideal,
        "qty_total": total,
        "qty_bad": bad,
        "qty_good": total - bad,
        "has_data": has_data,
        "coverage": coverage,
        "incomplete": coverage < coverage_min,
        "losses": losses,
    }
    res.update(ratios(ppt_min, run, run_wo, ideal, total, bad))
    if not has_data:
        res.update(availability=0.0, performance=0.0, performance_raw=0.0, quality=0.0, oee=0.0)
    return res


def ratios(ppt_min, run, run_wo, ideal, total, bad):
    """A, P, Q, OEE із сум (R-13 п. 4, 6–8)."""
    a = run / ppt_min if ppt_min > 0 else 0.0
    p_raw = ideal / run_wo if run_wo > 0 else 0.0
    p = min(1.0, p_raw) if run_wo > 0 else 1.0
    q = (total - bad) / total if total > 0 else 1.0
    return {"availability": a, "performance": p, "performance_raw": p_raw, "quality": q, "oee": a * p * q}


def aggregate(rows):
    """OEE за період із сум хвилин, ідеального часу й кількостей змін (не середнє відношень)."""

    def s(key):
        return sum(r.get(key, 0.0) or 0.0 for r in rows)

    res = ratios(s("ppt_min"), s("run_min"), s("run_wo_min"), s("ideal_min"), s("qty_total"), s("qty_bad"))
    if s("ppt_min") <= 0:
        res = dict.fromkeys(res, 0.0)
    return res
