"""R-54: план дня — чисті функції (години — настінний час Києва, 0…24). Без ORM."""

SLOTS = 96
SLOT_H = 0.25
RESOURCES = ("bess", "chp", "vent", "light", "charging", "genset")
RESOURCE_TITLES = {
    "bess": "BESS",
    "chp": "КГУ",
    "vent": "Вентиляція RoofVent",
    "light": "Освітлення цеху",
    "charging": "Зарядна станція",
    "genset": "ДГУ",
}
BAR_CLASS = {
    "charge": "c",
    "discharge": "d",
    "night": "n",
    "duty": "n",
    "run": "g",
    "test": "g",
    "day": "o",
    "work": "o",
}
FALLBACK_BESS = [
    (7.5, 11.0, "discharge", "розряд · пік"),
    (11.0, 16.0, "charge", "заряд від СЕС"),
    (16.0, 17.5, "discharge", "розряд · пік"),
]


def hhmm_to_h(text):
    hh, mm = text.split(":")
    return int(hh) + int(mm) / 60.0


def merge_slots(flags, max_gap=2):
    """Булів масив слотів → [(start_slot, end_slot_exclusive)]; сусідні з розривом ≤ `max_gap` слотів зливаються."""
    spans, start = [], None
    for i, flag in enumerate(flags + [False]):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            spans.append([start, i])
            start = None
    merged = []
    for s, e in spans:
        if merged and s - merged[-1][1] <= max_gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def bess_plan(cons, pv, peak, self_p):
    """Смуги BESS за типовим днем: розряд де `cons − pv ≥ limit − margin`, заряд де `pv − cons > export_max` ≥ 30 хв."""
    limit = peak["limit_kw"] - peak["activate_margin_kw"]
    dis = [c is not None and (c - (p or 0.0)) >= limit for c, p in zip(cons, pv, strict=True)]
    chg = [c is not None and p is not None and (p - c) > self_p["export_max_kw"] for c, p in zip(cons, pv, strict=True)]
    bars = []
    for s, e in merge_slots(dis):
        bars.append((s * SLOT_H, e * SLOT_H, "discharge", "розряд · пік", peak["bess_max_kw"]))
    for s, e in merge_slots(chg, max_gap=0):
        if e - s >= 2:
            bars.append((s * SLOT_H, e * SLOT_H, "charge", "заряд від СЕС", self_p["bess_max_kw"]))
    return sorted(bars)


def fallback_bess(peak):
    return [(f, t, mode, label, peak["bess_max_kw"]) for f, t, mode, label in FALLBACK_BESS]


def night_bars(night, enabled, weekday):
    """R-54 п.6: смуги вентиляції й освітлення. `weekday` — 0=пн; `days` — дні, з яких ПОЧИНАЄТЬСЯ вікно (1=пн)."""
    pct = night["vent_pct"]
    if not enabled:
        return {"vent": [(0.0, 24.0, "day", "день 100 %")], "light": [(0.0, 24.0, "work", "робочий")]}
    start, end = hhmm_to_h(night["from"]), hhmm_to_h(night["to"])
    today_starts = (weekday + 1) in night["days"]
    prev_starts = ((weekday - 1) % 7 + 1) in night["days"]
    vent, light = [], []

    def add(f, t, kind):
        if t <= f:
            return
        if kind == "night":
            vent.append((f, t, "night", "ніч %s %%" % pct))
            light.append((f, t, "duty", "черговий"))
        else:
            vent.append((f, t, "day", "день 100 %"))
            light.append((f, t, "work", "робочий"))

    if start > end:  # вікно через північ
        add(0.0, end, "night" if prev_starts else "day")
        add(end, start, "day")
        add(start, 24.0, "night" if today_starts else "day")
    else:
        add(0.0, start, "day")
        add(start, end, "night" if today_starts else "day")
        add(end, 24.0, "day")
    return {"vent": vent, "light": light}


def chp_bars(zones, gas_cost, margin):
    """КГУ за ціною: зони тарифу, де `ціна − вартість газу ≥ margin`; суміжні зливаються."""
    bars = []
    for z in sorted(zones, key=lambda z: z["from"]):
        if z["price"] - gas_cost >= margin:
            if bars and abs(bars[-1][1] - z["from"]) < 1e-9:
                bars[-1] = (bars[-1][0], z["to"], "run", "пуск за ціною")
            else:
                bars.append((z["from"], z["to"], "run", "пуск за ціною"))
    return bars


def subtract(bar, cutters):
    """Відняти від смуги `(from, to)` перекриття `cutters` → список смуг, що лишилися."""
    segs = [(bar[0], bar[1])]
    for cf, ct in cutters:
        nxt = []
        for f, t in segs:
            if ct <= f or cf >= t:
                nxt.append((f, t))
                continue
            if cf > f:
                nxt.append((f, cf))
            if ct < t:
                nxt.append((ct, t))
        segs = nxt
    return [(f, t) for f, t in segs if t - f > 1e-9]


def weekday_flag(weekdays, weekday):
    w = weekdays or "1111111"
    return len(w) > weekday and w[weekday] == "1"
