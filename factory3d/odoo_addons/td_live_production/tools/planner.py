"""Планувальник дня (LP-02): склад замовлень, навантаження ділянок, розклад нарядів, плановані простої. Без ORM.

Усі числа залежать лише від вхідних даних і `seed`: повторний виклик дає той самий день.
"""

from datetime import timedelta

from . import clock
from .noise import rng

DEFAULT_QTYS = (4, 6, 8, 10, 12, 14, 16, 20, 26, 32)
COLD_LIMIT = 0.85  # доля зміни, до якої звичайний верстат вважається «ще не повним»
DOWNTIME_REASONS = (
    # (ключ причини, стан верстата, вага, хв від, хв до); верстат підтверджує простій після `micro_stop_s` = 120 с,
    # тож найкоротший простій — 8 хв (контракт C-LP-01: не менше 3 хв)
    ("setup", "setup", 3.0, 10, 30),
    ("tool", "setup", 3.0, 8, 20),
    ("material", "idle", 3.0, 10, 40),
    ("break", "idle", 1.5, 10, 20),
    ("fault", "fault", 1.0, 25, 70),
)
REASON_LABELS = {
    "setup": "Налагодження",
    "tool": "Заміна інструменту",
    "material": "Очікування матеріалу",
    "break": "Перерва",
    "fault": "Поломка",
}
MAX_FAULTS = 2  # аварія піднімає тривогу й заявку ТО на кожну: не більше двох на добу на завод


def op_minutes(op, qty, slowdown=1.0):
    """Хвилини операції: налагодження + штуки × хвилини на штуку (`slowdown` — для перевантаженої ділянки)."""
    return (op.get("setup", 0.0) + op.get("cycle", 0.0) * qty) * slowdown


def variant_minutes(variant, qty, hot_wcs=(), slowdown=1.0):
    """`{верстат: хвилини}` варіанта маршруту (BOM) на `qty` штук."""
    res = {}
    for op in variant["ops"]:
        k = slowdown if op["wc"] in hot_wcs else 1.0
        res[op["wc"]] = res.get(op["wc"], 0.0) + op_minutes(op, qty, k)
    return res


def plan_orders(templates, n_orders, seed, shift_min, hot_wcs=(), overload=1.5, slowdown=1.0, lines_range=(2, 4)):
    """Склад замовлень дня з шаблонів.

    `templates = {"customers": [partner_id], "products": [{"id", "qtys": [..], "variants": [{"bom_id", "ops":
    [{"wc", "setup", "cycle"}]}]}]}`. Для кожного рядка замовлення вибирається варіант маршруту «жадібно»: той,
    що найменше переповнює найзавантаженіший верстат; перевантажені верстати (`hot_wcs`) вважаються «повними»
    лише на `overload × зміна`, решта — на 85 % зміни. Тому вибір тягне навантаження на гарячу ділянку, поки вона
    не набере `overload`, а решту розкладає по сусідніх лініях. Повертає
    `{"orders": [{"partner_id", "lines": [{"product_id", "bom_id", "qty"}]}], "load": {верстат: хв}}`.
    """
    r = rng("orders:%s" % seed)
    customers = list(templates["customers"])
    products = [p for p in templates["products"] if p["variants"]]
    if not customers or not products:
        return {"orders": [], "load": {}}
    r.shuffle(customers)
    load = {}
    orders = []
    for i in range(n_orders):
        lines = []
        for _ in range(r.randint(*lines_range)):
            product = r.choice(products)
            qty = r.choice(list(product.get("qtys") or DEFAULT_QTYS))
            variant = _best_variant(product["variants"], qty, load, shift_min, hot_wcs, overload, slowdown)
            for wc, minutes in variant_minutes(variant, qty, hot_wcs, slowdown).items():
                load[wc] = load.get(wc, 0.0) + minutes
            lines.append({"product_id": product["id"], "bom_id": variant["bom_id"], "qty": qty})
        orders.append({"partner_id": customers[i % len(customers)], "lines": lines})
    return {"orders": orders, "load": load}


def _best_variant(variants, qty, load, shift_min, hot_wcs, overload, slowdown):
    def score(variant):
        mins = variant_minutes(variant, qty, hot_wcs, slowdown)
        worst = 0.0
        for wc, minutes in mins.items():
            limit = shift_min * (overload if wc in hot_wcs else COLD_LIMIT)
            worst = max(worst, (load.get(wc, 0.0) + minutes) / limit)
        return (round(worst, 6), sum(mins.values()), variant["bom_id"])

    return min(variants, key=score)


def schedule(mos, shift, workdays, wc_free=None):
    """Розклад нарядів із кінцевою потужністю верстатів: один наряд на верстаті за раз, наряди МО — послідовно.

    `mos = [{"id", "release": naive UTC, "ops": [{"id", "wc", "minutes"}]}]` у порядку пріоритету;
    `wc_free = {верстат: коли вільний}` (залишок завантаження від попередніх діб). Повертає
    `{op_id: (початок, кінець)}`; `wc_free` оновлюється (передайте копію, якщо він ще потрібен).
    """
    wc_free = wc_free if wc_free is not None else {}
    plan = {}
    for mo in mos:
        prev_end = mo["release"]
        for op in mo["ops"]:
            earliest = max(prev_end, wc_free.get(op["wc"], prev_end))
            start, end = clock.place(earliest, op["minutes"], shift, workdays)
            plan[op["id"]] = (start, end)
            wc_free[op["wc"]] = end
            prev_end = end
    return plan


def utilisation(plan, ops_wc, shift_min):
    """`{верстат: хв}` запланованого навантаження (для звіту: який верстат/ділянка перевантажені)."""
    res = {}
    for op_id, (start, end) in plan.items():
        wc = ops_wc[op_id]
        res[wc] = res.get(wc, 0.0) + (end - start).total_seconds() / 60.0
    return res


def plan_downtimes(wc_ops, share, seed, reasons=DOWNTIME_REASONS, max_faults=MAX_FAULTS):
    """Простої дня: `share` (0…1) від зміни на кожному задіяному верстаті в середньому.

    `wc_ops = {верстат: [(початок, кінець) нарядів дня]}`. Простій ставиться одразу після кінця випадкового наряду
    верстата — між нарядами, не посередині (так розклад лишається чесним). Повертає список
    `{"wc", "start", "minutes", "reason", "kind"}`; порядок і числа визначає `seed`. Аварій (`kind == "fault"`) не
    більше `max_faults` за добу.
    """
    r = rng("downtimes:%s" % seed)
    wcs = sorted(w for w, ops in wc_ops.items() if ops)
    if not wcs or share <= 0:
        return []
    avg = sum(w * (lo + hi) / 2.0 for _, _, w, lo, hi in reasons) / sum(x[2] for x in reasons)
    total = share * sum(sum((e - s).total_seconds() / 60.0 for s, e in wc_ops[w]) for w in wcs)
    want = max(1, int(round(total / avg))) if total > 0 else 0
    r.shuffle(wcs)
    res = []
    for i in range(want):
        wc = wcs[i % len(wcs)]
        pool = (
            reasons if sum(d["kind"] == "fault" for d in res) < max_faults else [x for x in reasons if x[1] != "fault"]
        )
        reason = r.choices(pool, weights=[x[2] for x in pool])[0]
        ops = sorted(wc_ops[wc])
        taken = {d["start"] for d in res if d["wc"] == wc}
        free = [e for _, e in ops if e not in taken] or [ops[-1][1]]
        res.append(
            {
                "wc": wc,
                "start": r.choice(free),
                "minutes": float(r.randint(reason[3], reason[4])),
                "reason": reason[0],
                "kind": reason[1],
            }
        )
    return sorted(res, key=lambda d: (d["start"], d["wc"]))


def shift_release(day, shift):
    """Початок зміни доби `day` (naive UTC): з нього випускаються МО дня."""
    return clock.shift_window(day, shift)[0]


def spill_minutes(plan, day_end):
    """Хвилин нарядів, запланованих після `day_end` (перенос на наступну зміну)."""
    return sum(max(0.0, (e - max(s, day_end)).total_seconds() / 60.0) for s, e in plan.values())


def next_day(day):
    return day + timedelta(days=1)
