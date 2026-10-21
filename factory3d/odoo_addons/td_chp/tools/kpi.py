"""R-02: KPI когенерації з показань (`v` — код без `chp/` → число|None)."""


def _r(x, nd=1):
    return None if x is None else round(x, nd)


def compute(v, lhv_kwh_m3, co2_kg_m3):
    """`{fuel_kw, eta_e, eta_h, eta_t, co2_kgh, co2_day_t, dT}`; відсутній вхід → None, `eta_*` = 0 при `ok=False`."""
    gas, p_el, q_th = v.get("gas/flow"), v.get("gen/p_kw"), v.get("ht/q_total")
    fuel = None if gas is None else gas * lhv_kwh_m3
    rpm = v.get("eng/rpm")
    ok = fuel is not None and fuel > 20 and rpm is not None and rpm > 1200
    eta_e = eta_h = eta_t = 0.0
    if fuel is None or rpm is None:
        eta_e = eta_h = eta_t = None
    elif ok:
        eta_e = None if p_el is None else p_el / fuel * 100
        eta_h = None if q_th is None else q_th / fuel * 100
        eta_t = None if eta_e is None or eta_h is None else eta_e + eta_h
    gas_day = v.get("gas/day")
    t_sup, t_ret = v.get("ht/t_sup"), v.get("ht/t_ret")
    return {
        "fuel_kw": _r(fuel),
        "eta_e": _r(eta_e),
        "eta_h": _r(eta_h),
        "eta_t": _r(eta_t),
        "co2_kgh": _r(None if gas is None else gas * co2_kg_m3),
        "co2_day_t": _r(None if gas_day is None else gas_day * co2_kg_m3 / 1000, 2),
        "dT": _r(None if t_sup is None or t_ret is None else t_sup - t_ret),
    }


def cylinders(ids, v, th):
    """R-03: `[{id, t, dev, knock, kv, ms, plug_h}]`; `dev = t − mean` лише при `eng/rpm > 1200`, інакше None."""
    temps = [v.get(f"cyl/{cid}/t") for cid in ids]
    known = [t for t in temps if t is not None]
    mean = sum(known) / len(known) if known else None
    run = (v.get("eng/rpm") or 0) > 1200
    rows = []
    for cid, t in zip(ids, temps, strict=True):
        dev = None if (not run or t is None or mean is None) else round(t - mean, 1)
        rows.append(
            {
                "id": cid,
                "t": t,
                "dev": dev,
                "knock": v.get(f"cyl/{cid}/knock"),
                "kv": v.get(f"cyl/{cid}/kv"),
                "ms": v.get(f"cyl/{cid}/ms"),
                "plug_h": v.get(f"cyl/{cid}/plug_h"),
            }
        )
    return rows


def cylinder_level(dev, th):
    """R-03: `|dev| > alarm` → alarm, `> warn` → warn, інакше ok; `dev=None` → None."""
    if dev is None:
        return None
    if abs(dev) > th["cyl_dev_alarm_k"]:
        return "alarm"
    if abs(dev) > th["cyl_dev_warn_k"]:
        return "warn"
    return "ok"


def plug_state(plug_h, interval_h):
    """R-03: наробіток свічки до інтервалу: ≥ 95 % «Замінити», ≥ 80 % «Зношується», інакше «Норма» → (%, підпис)."""
    if plug_h is None or not interval_h:
        return None, None
    pct = plug_h / interval_h * 100
    return round(pct), "Замінити" if pct >= 95 else "Зношується" if pct >= 80 else "Норма"
