"""R-23: сценарії «Що якщо» — перенос навантаження ділянки (вузлів) на інший тарифний період.
Чисті функції без ORM.

Сітка часу — «плаский» ряд місцевих діб підряд по 96 слотів (15 хв); індекс `i = доба · 96 + слот`, доба 0 — перша
доба базового періоду. Енергія слота — кВт·год за 15 хв, потужність = кВт·год × 4. `net[i]` — імпорт із мережі за
вводами мінус віддача; сценарій додає до нього зміну навантаження вузлів. Ціна слота — за зоною тарифу для
пари (день тижня, слот). Зона — будь-який об'єкт з атрибутами `name, code, price, weekdays, hour_from, hour_to,
sequence` (`Zone`)."""

from collections import namedtuple
from datetime import timedelta

from odoo.addons.td_energy.tools.tariff import zone_matches

from .fmt import fmt_dec, fmt_int

SLOTS = 96
NORM_DAYS = 30  # економія нормується на 30 діб
MIN_DAYS = 5  # менше повних діб — розрахунок не має сенсу
NIGHT_FROM, NIGHT_TO = 22.0, 6.0  # години, коли на ділянці потрібна нічна зміна
EPS = 1e-9

Zone = namedtuple("Zone", "name code price weekdays hour_from hour_to sequence")


class WhatIfError(Exception):
    """Сценарій неможливо порахувати; текст — для користувача."""


# --- тариф ----------------------------------------------------------------------------------------------------
def price_table(zones):
    """R-23 п. 1: для кожної пари (день тижня 0…6, слот 0…95) — індекс зони й ціна. Зони впорядковані за
    `sequence`; перша зона, що відповідає слоту, виграє; не покрита чверть — зона −1, ціна 0."""
    ordered = sorted(zones, key=lambda z: z.sequence or 0)
    zone_idx = [[-1] * SLOTS for _ in range(7)]
    price = [[0.0] * SLOTS for _ in range(7)]
    for wd in range(7):
        for k in range(SLOTS):
            for i, zone in enumerate(ordered):
                if zone_matches(zone, wd, k / 4):
                    zone_idx[wd][k], price[wd][k] = i, zone.price
                    break
    return {"zones": ordered, "zone": zone_idx, "price": price}


def night_zone_indexes(zones):
    """R-23 п. 2: індекси «нічних» зон (за впорядкованим списком). Зони з кодом `night`, якщо їхня ціна нижча за
    найвищу; інакше — зони з найнижчою ціною. Однакові ціни всіх зон — нічної зони немає (порожня множина)."""
    prices = [z.price for z in zones]
    if not prices or max(prices) - min(prices) < EPS:
        return set()
    top, low = max(prices), min(prices)
    night = {i for i, z in enumerate(zones) if z.code == "night" and z.price < top - EPS}
    return night or {i for i, z in enumerate(zones) if abs(z.price - low) < EPS}


def flat_of(week_table, first_weekday, n_days):
    """Розгортає таблицю 7 × 96 у плаский ряд на `n_days` діб, перша доба — з днем тижня `first_weekday`."""
    out = []
    for d in range(n_days):
        out.extend(week_table[(first_weekday + d) % 7])
    return out


# --- вікно й зсув ---------------------------------------------------------------------------------------------
def window_slots(hour_from, hour_to):
    """R-23 п. 3: (початок, довжина) вікна в слотах. Перехід через північ: довжина = (по − з) mod 24; «0–24» і
    «з = по» — уся доба."""
    start = int(round(hour_from * 4)) % SLOTS
    length = int(round(((hour_to - hour_from) % 24) * 4)) or SLOTS
    return start, length


def night_shift(table, night, weekday, start):
    """Зсув (у слотах) від слота `start` доби з днем тижня `weekday` до найближчого слота нічної зони (включно);
    `None` — за 7 діб нічної зони немає."""
    for k in range(7 * SLOTS):
        wd = (weekday + (start + k) // SLOTS) % 7
        if table["zone"][wd][(start + k) % SLOTS] in night:
            return k
    return None


def plan_moves(n_days, window, move_day, shift, valid=None):
    """R-23 п. 3: пари (слот-джерело, слот-ціль). Вікно доби `d` переносять, якщо `move_day[d]`; `shift` — ціле або
    `f(d) → ціле|None`. Ряд замкнений у кільце: ціль за краєм базового періоду потрапляє на його початок (енергія
    зберігається, краї не спотворюють підсумок). Слот-джерело поза рядом (вікно через північ на останній добі) і пара
    з добою без повних даних пропускаються."""
    start, length = window
    total = len(move_day) * SLOTS
    pairs = []
    for d in range(n_days):
        if not move_day[d]:
            continue
        sh = shift(d) if callable(shift) else shift
        if not sh:
            continue
        for j in range(length):
            s = d * SLOTS + start + j
            if s >= total:
                continue
            t = (s + sh) % total
            if t == s or (valid is not None and not (valid[s // SLOTS] and valid[t // SLOTS])):
                continue
            pairs.append((s, t))
    return pairs


def apply_moves(base, pairs, share, cap=None):
    """R-23 п. 4: переносить частку `share` (0…1) енергії слота-джерела у слот-ціль. `cap` — номінал вузла,
    кВт·год за слот: ціль не перевищує його, зайве лишається в слоті-джерелі.
    Порядок: пари з додатним зсувом — від кінця ряду, з від'ємним — від початку (ціль у вікні вже віддала своє).
    Повертає `(новий ряд, [(s, t, кВт·год)…], не перенесено кВт·год)`."""
    cur = list(base)
    ordered = sorted((p for p in pairs if p[1] > p[0]), key=lambda p: -p[0]) + sorted(
        (p for p in pairs if p[1] < p[0]), key=lambda p: p[0]
    )
    flows, blocked = [], 0.0
    for s, t in ordered:
        want = base[s] * share
        if want <= 0:
            continue
        amount = want if cap is None else min(want, max(0.0, cap - cur[t]))
        blocked += want - amount
        if amount <= 0:
            continue
        cur[s] -= amount
        cur[t] += amount
        flows.append((s, t, amount))
    return cur, flows, blocked


# --- вартість, пік, зони --------------------------------------------------------------------------------------
def energy_cost(net, price, export_price=0.0, mask=None):
    """Σ імпорт · ціна зони − Σ віддача · ціна віддачі по слотах `mask` (грн). Імпорт слота = max(0, net)."""
    total = 0.0
    for i, v in enumerate(net):
        if mask is not None and not mask[i]:
            continue
        total += v * price[i] if v > 0 else v * export_price
    return total


def peak(net, mask=None):
    """(кВт, індекс слота) найбільшої 15-хв потужності імпорту; `(0.0, None)`, якщо імпорту немає."""
    best, idx = 0.0, None
    for i, v in enumerate(net):
        if (mask is None or mask[i]) and v * 4 > best + EPS:
            best, idx = v * 4, i
    return best, idx


def zone_energy(net, zone, mask=None):
    """Імпорт кВт·год за індексом зони (−1 — без зони)."""
    out = {}
    for i, v in enumerate(net):
        if v > 0 and (mask is None or mask[i]):
            out[zone[i]] = out.get(zone[i], 0.0) + v
    return out


def average_day(net, days):
    """Середня доба: 96 значень кВт імпорту (max(0, net) · 4) за добами `days`."""
    if not days:
        return [0.0] * SLOTS
    return [sum(max(0.0, net[d * SLOTS + k]) for d in days) * 4 / len(days) for k in range(SLOTS)]


def at_text(first_day, idx):
    """«23:15 (14.10)» для слота `idx`."""
    day = first_day + timedelta(days=idx // SLOTS)
    slot = idx % SLOTS
    return "%02d:%02d (%s)" % (slot // 4, (slot % 4) * 15, day.strftime("%d.%m"))


def kw_text(value):
    """Потужність у тексті: ціле або з одним знаком, коли < 10 кВт."""
    return fmt_int(value) if value >= 10 or abs(value - round(value)) < 0.05 else fmt_dec(value, 1)


def is_night_hour(slot):
    """Слот у нічні години 22:00–06:00."""
    hour = (slot % SLOTS) / 4
    return hour >= NIGHT_FROM or hour < NIGHT_TO


# --- сценарій -------------------------------------------------------------------------------------------------
def run(p):
    """R-23: повний розрахунок сценарію; винятки — `WhatIfError`. Вхід `p` (словник):
    `first_day` (date), `n_days`, `net` (кВт·год за слот), `data_ok` (прапорці повних діб), `nodes`
    (`[{code, name, kwh, cap_kw}]`), `zones`, `export_price`, `capacity_price` (₴/кВт·міс), `contract_kw`,
    `warn_pct`, `window` (з, по — години), `mode` (`shift`|`night`), `shift_h`, `share` (0…1), `days` (`work`|`all`),
    `respect_rating`, `scope_text` (для попереджень). Результат — словник: `tiles`, `zones`, `profile`,
    `warnings`, `meta`."""
    n, first = p["n_days"], p["first_day"]
    total, wd0 = n * SLOTS, p["first_day"].weekday()
    ok = list(p["data_ok"])
    used = [d for d in range(n) if ok[d]]
    if len(used) < MIN_DAYS:
        raise WhatIfError(
            "Замало повних діб даних у базовому періоді: %s (потрібно щонайменше %s)." % (len(used), MIN_DAYS)
        )
    if not p["zones"]:
        raise WhatIfError("Немає чинного тарифу із зонами: ціну слота визначити не можна.")
    if not p["nodes"]:
        raise WhatIfError("У сценарії немає вузлів-споживачів.")
    table = price_table(p["zones"])
    zones = table["zones"]
    night = night_zone_indexes(zones)
    differ = len({z.price for z in zones}) > 1
    price, zone = flat_of(table["price"], wd0, n), flat_of(table["zone"], wd0, n)
    mask = [ok[i // SLOTS] for i in range(total)]
    start, length = window_slots(*p["window"])
    if p["mode"] == "night":
        if not night:
            raise WhatIfError("У тарифі немає нічної зони: ціни всіх зон однакові.")

        def shift(d):
            return night_shift(table, night, (wd0 + d) % 7, start)

    else:
        shift = int(round(p["shift_h"] * 4))
    move_day = [bool(ok[d]) and (p["days"] == "all" or (wd0 + d) % 7 < 5) for d in range(n)]
    pairs = plan_moves(n, (start, length), move_day, shift, valid=ok)
    share = max(0.0, min(1.0, p["share"]))

    delta = [0.0] * total
    flows, blocked = [], 0.0
    for node in p["nodes"]:
        cap = node["cap_kw"] / 4 if p["respect_rating"] and node.get("cap_kw") else None
        new, node_flows, node_blocked = apply_moves(node["kwh"], pairs, share, cap)
        for i in range(total):
            delta[i] += new[i] - node["kwh"][i]
        flows += node_flows
        blocked += node_blocked
    moved = sum(a for _s, _t, a in flows)
    wanted = moved + blocked
    after = [a + b for a, b in zip(p["net"], delta, strict=True)]

    export_price = p.get("export_price", 0.0)
    k = NORM_DAYS / len(used)
    cost_before = energy_cost(p["net"], price, export_price, mask) * k
    cost_after = energy_cost(after, price, export_price, mask) * k
    peak_before, idx_before = peak(p["net"], mask)
    peak_after, idx_after = peak(after, mask)
    fee_before = p.get("capacity_price", 0.0) * peak_before
    fee_after = p.get("capacity_price", 0.0) * peak_after
    tiles = {
        "cost_before": round(cost_before + fee_before, 2),
        "cost_after": round(cost_after + fee_after, 2),
        "energy_cost_before": round(cost_before, 2),
        "energy_cost_after": round(cost_after, 2),
        "capacity_fee_before": round(fee_before, 2),
        "capacity_fee_after": round(fee_after, 2),
        "saving_month": round(cost_before + fee_before - cost_after - fee_after, 2),
        "peak_before_kw": round(peak_before, 1),
        "peak_after_kw": round(peak_after, 1),
        "peak_delta_kw": round(round(peak_after, 1) - round(peak_before, 1), 1),  # як різниця показаних значень
        "limit_kw": round(p["contract_kw"], 1),
        "moved_kwh_month": round(moved * k, 1),
    }

    zb, za = zone_energy(p["net"], zone, mask), zone_energy(after, zone, mask)
    tb, ta = sum(zb.values()), sum(za.values())
    merged = {}  # зони з однаковою назвою й ціною (час поділено на кілька записів) показуються одним рядком
    for i in sorted(set(zb) | set(za) | set(range(len(zones)))):
        info = zones[i] if i >= 0 else None
        key = (info.name, info.code, info.price) if info else ("Без зони", "none", 0.0)
        row = merged.setdefault(key, {"before": 0.0, "after": 0.0, "night": False})
        row["before"] += zb.get(i, 0.0)
        row["after"] += za.get(i, 0.0)
        row["night"] = row["night"] or i in night
    zone_rows = [
        {
            "name": name, "code": code, "price": price, "night": row["night"],
            "before_kwh": round(row["before"] * k, 1), "after_kwh": round(row["after"] * k, 1),
            "before_pct": round(row["before"] * 100 / tb, 1) if tb else 0.0,
            "after_pct": round(row["after"] * 100 / ta, 1) if ta else 0.0,
        }
        for (name, code, price), row in merged.items()
    ]  # fmt: skip

    shown = [d for d in used if move_day[d]] or used
    profile = {
        "base_kw": [round(v, 1) for v in average_day(p["net"], shown)],
        "scenario_kw": [round(v, 1) for v in average_day(after, shown)],
        "limit_kw": tiles["limit_kw"],
        "days": len(shown),
    }

    warnings = _warnings(p, tiles, flows, wanted, blocked, k, night, zone, idx_after, len(used), n, differ)
    meta = {
        "days_used": len(used), "days_skipped": n - len(used), "window": list(p["window"]), "mode": p["mode"],
        "has_night_zone": bool(night), "zone_prices_differ": differ,
        "peak_before_at": at_text(first, idx_before) if idx_before is not None else None,
        "peak_after_at": at_text(first, idx_after) if idx_after is not None else None,
    }  # fmt: skip
    return {"tiles": tiles, "zones": zone_rows, "profile": profile, "warnings": warnings, "meta": meta}


def _warnings(p, tiles, flows, wanted, blocked, k, night, zone, idx_after, n_used, n_days, prices_differ):
    out = []

    def add(level, code, text):
        out.append({"level": level, "code": code, "text": text})

    limit, after = tiles["limit_kw"], tiles["peak_after_kw"]
    first = p["first_day"]
    if limit and after > limit + EPS:
        text = "Пік перевищує ліміт договору (%s кВт) на %s кВт о %s." % (
            fmt_int(limit), kw_text(after - limit), at_text(first, idx_after),
        )  # fmt: skip
        if tiles["peak_before_kw"] > limit + EPS:
            text += " У базовому періоді ліміт уже перевищувався (пік %s кВт)." % fmt_int(tiles["peak_before_kw"])
        add("danger", "peak_over_limit", text)
    elif limit and after >= limit * p.get("warn_pct", 90) / 100 and after > tiles["peak_before_kw"] + EPS:
        add(
            "warning", "peak_near_limit",
            "Пік зростає до %s кВт — %s %% ліміту договору (%s кВт)." % (
                fmt_int(after), fmt_int(after * 100 / limit), fmt_int(limit)),
        )  # fmt: skip
    moved = sum(a for _s, _t, a in flows)
    if moved <= EPS:
        add(
            "warning",
            "nothing_moved",
            "Нічого не перенесено: у вікні немає споживання, немає робочих діб або цільовий слот поза даними.",
        )
    night_in = sum(a for s, t, a in flows if is_night_hour(t) and not is_night_hour(s))
    if night_in > EPS and night_in >= 0.05 * moved:
        add(
            "warning", "night_shift",
            "Нічна зміна: потрібні люди на %s (у нічні години 22:00–06:00 переноситься %s кВт·год/міс)." % (
                p.get("scope_text") or "ділянці", fmt_int(night_in * k)),
        )  # fmt: skip
    if blocked > 0.005 * max(wanted, EPS):
        add(
            "warning", "rating_limit",
            "Частину навантаження (%s кВт·год/міс, %s %%) не перенесено: цільовий слот перевищив би номінал вузла." % (
                fmt_int(blocked * k), fmt_dec(blocked * 100 / wanted, 1)),
        )  # fmt: skip
    if p["mode"] == "night" and moved > EPS:
        outside = sum(a for _s, t, a in flows if zone[t] not in night)
        if outside > 0.01 * moved:
            add(
                "warning", "outside_night",
                "Вікно довше за нічну зону: %s %% перенесеної енергії лишається поза нічною зоною тарифу." % fmt_dec(
                    outside * 100 / moved, 0),
            )  # fmt: skip
    if not prices_differ:
        add(
            "info",
            "flat_tariff",
            "Ціни зон тарифу однакові: економія можлива лише через власну генерацію (віддача не оплачується) "
            "і плату за потужність.",
        )
    if n_days - n_used:
        add("info", "days_skipped", "%s діб із неповними даними виключено з розрахунку." % (n_days - n_used))
    return out
