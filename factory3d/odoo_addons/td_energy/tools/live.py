"""R-06, R-12, R-15: живі показники, асиметрія, профіль доби. Чисті функції без ORM."""

import math

PFC_STEP = 50
PFC_MAX = 350
TARGET_COS = 0.97


def pf_to_cos(value):
    """R-02 п. 2: чотириквадрантний cos φ PM5560 → [0, 1]."""
    if value is None:
        return None
    v = abs(value)
    cos = v if v <= 1 else 2 - v
    return min(max(cos, 0.0), 1.0)


def _q(p, cos):
    cos = min(max(cos, 1e-6), 1.0)
    return p * math.tan(math.acos(cos))


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _round_half_up(x):
    return math.floor(x + 0.5)


def line_values(p, cos, i, rating_a, cos_nominal=0.9):
    """П. 1: `cos` None (несвіжий) — номінал вузла. Повертає dict `p, q, cos, i, load`."""
    cos_l = cos if cos is not None else cos_nominal
    load = (i / rating_a) if (i is not None and rating_a) else None
    return {"p": p, "q": _q(p, cos_l), "cos": cos_l, "i": i, "load": load}


def site_totals(lines, q_kvar=None, rating_kvar=None, pfc_meas=None, pfc_step=None):
    """П. 2–3. `lines` — {код: {"section": 1|2, "p": кВт, "cos": float|None, "i": А|None, "rating_a": А,
    "cos_nominal": 0.9}}; `q_kvar` — {секція: виміряна квар на вводі або None}; `rating_kvar` — {секція: 350}.
    W1 (R-35, D-09): `pfc_meas` — {секція: `energy/cells/PFC-s/q_kvar` або None} (замість різниці з вводом);
    `pfc_step` — {секція: крок ступеня, квар} (за замовчуванням 50).
    Повертає {"lines", "sections": {s: {...}}, "p_now", "s_now", "cos_before", "cos_after"}."""
    q_kvar = q_kvar or {}
    rating_kvar = rating_kvar or {}
    pfc_meas = pfc_meas or {}
    pfc_step = pfc_step or {}
    out_lines = {}
    sections = {}
    for code, ln in lines.items():
        vals = line_values(ln["p"], ln.get("cos"), ln.get("i"), ln.get("rating_a"), ln.get("cos_nominal") or 0.9)
        out_lines[code] = vals
        sec = sections.setdefault(ln["section"], {"p": 0.0, "q": 0.0})
        sec["p"] += vals["p"]
        sec["q"] += vals["q"]
    sum_p = sum_q = sum_q_after = 0.0
    for s, sec in sorted(sections.items()):
        p, q = sec["p"], sec["q"]
        sec["cos_before"] = p / math.hypot(p, q) if p or q else 1.0
        rating = rating_kvar.get(s, PFC_MAX) or PFC_MAX
        measured = q_kvar.get(s)
        step = pfc_step.get(s) or PFC_STEP
        if pfc_meas.get(s) is not None:
            q_pfc = _clamp(pfc_meas[s], 0.0, rating)
        elif measured is not None:
            q_pfc = _clamp(q - measured, 0.0, rating)
        else:
            q_pfc = _clamp(q - p * math.tan(math.acos(TARGET_COS)), 0.0, PFC_MAX)
        sec["q_pfc"] = q_pfc
        sec["pfc_q_now"] = int(min(rating, _round_half_up(q_pfc / step) * step))
        sec["s"] = math.hypot(p, q - q_pfc)
        sec["cos_after"] = p / sec["s"] if sec["s"] else 1.0
        sum_p += p
        sum_q += q
        sum_q_after += q - q_pfc
    s_now = math.hypot(sum_p, sum_q_after)
    return {
        "lines": out_lines,
        "sections": sections,
        "p_now": sum_p,
        "s_now": s_now,
        "cos_before": sum_p / math.hypot(sum_p, sum_q) if sum_p or sum_q else 1.0,
        "cos_after": sum_p / s_now if s_now else 1.0,
    }


def grid_split(p_q1, p_q2, island=False):
    """П. 6: `(grid_kw, export_kw)`; в острові — `(0, 0)`."""
    if island:
        return 0.0, 0.0
    net = (p_q1 or 0.0) + (p_q2 or 0.0)
    return max(0.0, net), max(0.0, -net)


def bess_mode(bess_kw):
    """П. 5: `charge` (> 1 кВт) / `discharge` (< −1) / `idle`."""
    if bess_kw is None:
        return "idle"
    if bess_kw > 1:
        return "charge"
    if bess_kw < -1:
        return "discharge"
    return "idle"


def critical_kw(values):
    """П. 7: Σ `p_now` критичних вузлів (None — пропуск)."""
    return sum(v for v in values if v is not None)


def unbalance_pct(i_a, i_b, i_c, rating_a):
    """R-12 п. 3: асиметрія фазних струмів, %; `I_avg < max(5 А, 0,02·rating)` — `None` (не рахувати)."""
    if None in (i_a, i_b, i_c):
        return None
    avg = (i_a + i_b + i_c) / 3.0
    if avg < max(5.0, 0.02 * (rating_a or 0)):
        return None
    return max(abs(i - avg) for i in (i_a, i_b, i_c)) / avg * 100.0


def day_profile(slots, now_local_hour, partial_kwh=0.0):
    """R-15 п. 1: `slots` — [(hour_local, kwh)] закритих інтервалів фідерів за сьогодні; `now_local_hour` — поточна
    година; `partial_kwh` — частковий поточний слот. Години після поточної — `None`; значення цілі."""
    acc = [0.0] * 24
    for hour, kwh in slots:
        acc[hour] += kwh
    acc[now_local_hour] += partial_kwh
    return [int(round(v)) if h <= now_local_hour else None for h, v in enumerate(acc)]


def peak(load15):
    """R-15 п. 3: `load15` — [(початок слота, кВт)]; повертає `(peak_kw int, початок слота)` або `(0, None)`."""
    if not load15:
        return 0, None
    start, kw = max(load15, key=lambda x: x[1])
    return int(round(kw)), start


def typical(profiles):
    """R-15 п. 5: середнє по годинах профілів повних робочих днів; менше 3 днів — `None` (статика без змін)."""
    if len(profiles) < 3:
        return None
    return [int(round(sum(p[h] or 0 for p in profiles) / len(profiles))) for h in range(24)]
