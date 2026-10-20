"""R-30: вузьке місце заводу (теорія обмежень). Чисті функції без ORM і без `env`.

Час — naive UTC `datetime`. Вхід збирає `td.bottleneck._td_collect`:

- `stations`: `{key: {"name", "codes": [код верстата…], "machines", "run_min", "avail_min"}}` — робота й доступний час
  (хв, сума за верстатами ділянки; джерело — журнал станів, а без нього журнал часу, як в OEE);
- `orders`: `[{"id", "mo", "seq", "station", "ready_at", "start_at", "finish_at", "qty"}]` — по одному на завдання
  (`mrp.workorder`): `ready_at` — коли завершилась попередня операція (для першої — початок МО), `start_at` — перший
  факт роботи, `finish_at` — завершення.
"""

from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
PERIODS = ("shift", "day", "week")
LOAD_MIN = 0.5  # нижче цього завантаження ділянка вузьким місцем не вважається
BOOST_DEFAULT = 20.0
VERDICTS = ("growing", "queue", "load", "low")


def period_window(period, now):
    """`(date_from, date_to)` для `shift` (київська доба до `now`), `day` (24 год), `week` (7 діб)."""
    if period == "shift":
        local = now.replace(tzinfo=timezone.utc).astimezone(KYIV)
        midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return midnight.astimezone(timezone.utc).replace(tzinfo=None), now
    if period == "day":
        return now - timedelta(days=1), now
    if period == "week":
        return now - timedelta(days=7), now
    raise ValueError("period: %r" % (period,))


def _minutes(a, b):
    return (b - a).total_seconds() / 60.0


def waiting_at(order, t):
    """Завдання чекає на `t`: попередня операція вже завершена (`ready_at <= t`), а ця ще не почата."""
    ready = order.get("ready_at")
    if ready is None or ready > t:
        return False
    started = order.get("start_at") or order.get("finish_at")
    return started is None or started > t


def order_wait(order, t0, t1):
    """Очікування перед ділянкою, хв: стартувало у вікні — до старту, ще чекає — до `t1`; інакше `None`."""
    ready = order.get("ready_at")
    if ready is None or ready > t1:
        return None
    started = order.get("start_at") or order.get("finish_at")
    if started is not None and started <= t1:
        return max(0.0, _minutes(ready, started)) if started >= t0 else None
    return max(0.0, _minutes(ready, t1))


def station_rows(stations, orders, t0, t1):
    """Показники ділянок за `[t0, t1]`: завантаження, черга (на `t1` і `t0`), очікування, випуск, потужність.

    Порожні ділянки (немає ні завантаження, ні завдань) пропускаються. `capacity` — випуск при 100 % завантаженні:
    `output / load` (одиниці виробу за вікно), `None`, якщо немає завантаження або випуску.
    """
    by_station = {}
    for order in orders:
        by_station.setdefault(order["station"], []).append(order)
    rows = []
    for key, st in stations.items():
        own = by_station.get(key, [])
        avail = float(st.get("avail_min") or 0.0)
        run = float(st.get("run_min") or 0.0)
        load = min(1.0, run / avail) if avail > 0 else None
        queue = sum(1 for o in own if waiting_at(o, t1))
        queue0 = sum(1 for o in own if waiting_at(o, t0))
        waits = [w for w in (order_wait(o, t0, t1) for o in own) if w is not None]
        done = [o for o in own if o.get("finish_at") is not None and t0 <= o["finish_at"] <= t1]
        output = float(sum(o.get("qty") or 0.0 for o in done))
        if load is None and not own:
            continue
        rows.append(
            {
                "key": key,
                "name": st["name"],
                "codes": list(st.get("codes", [])),
                "machines": int(st.get("machines") or 0),
                "run_min": run,
                "avail_min": avail,
                "load": load,
                "queue": queue,
                "queue_start": queue0,
                "queue_delta": queue - queue0,
                "wait_min": sum(waits) / len(waits) if waits else None,
                "wait_n": len(waits),
                "output": output,
                "done": len(done),
                "capacity": output / load if load and output > 0 else None,
            }
        )
    return rows


def find_bottleneck(rows, load_min=LOAD_MIN):
    """Ділянка з найбільшим завантаженням і чергою, що росте (ТОС): `(key | None, verdict | None)`.

    Серед ділянок із завантаженням `>= load_min`: `growing` — черга зросла за вікно (береться найбільш завантажена),
    `queue` — черга є, але не росте, `load` — черги немає (вузьке місце не виражене). Якщо жодна ділянка не досягає
    `load_min`, але черга десь є, — `low`: найбільш завантажена з чергою як імовірний кандидат; інакше `(None, None)`.
    Рівність — більша черга, потім ключ.
    """
    measured = [r for r in rows if r["load"] is not None and r["load"] > 0]
    high = [r for r in measured if r["load"] >= load_min]
    for verdict, pool in (
        ("growing", [r for r in high if r["queue"] > 0 and r["queue_delta"] > 0]),
        ("queue", [r for r in high if r["queue"] > 0]),
        ("load", high),
        ("low", [r for r in measured if r["queue"] > 0]),
    ):
        if pool:
            return sorted(pool, key=lambda r: (-r["load"], -r["queue"], r["key"]))[0]["key"], verdict
    return None, None


def rank_rows(rows, bottleneck=None):
    """Рейтинг: вузьке місце першим, далі за завантаженням, чергою; додає `rank` і `bottleneck`."""
    ordered = sorted(
        rows,
        key=lambda r: (
            r["key"] != bottleneck,
            -(r["load"] if r["load"] is not None else -1.0),
            -r["queue"],
            r["key"],
        ),
    )
    return [{**r, "rank": i, "bottleneck": r["key"] == bottleneck} for i, r in enumerate(ordered, 1)]


# --- модель пропускної здатності ---------------------------------------------------------------------------------


def build_routes(orders):
    """Маршрути МО: `[{"stations": [k1, k2, …], "orders": n}]`; сусідні однакові ділянки зливаються."""
    by_mo = {}
    for order in orders:
        by_mo.setdefault(order["mo"], []).append(order)
    count = {}
    for steps in by_mo.values():
        route = []
        for order in sorted(steps, key=lambda o: (o.get("seq", 0), o["id"])):
            if not route or route[-1] != order["station"]:
                route.append(order["station"])
        count[tuple(route)] = count.get(tuple(route), 0) + 1
    return [
        {"stations": list(route), "orders": n} for route, n in sorted(count.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def main_upstream(routes, key):
    """Ділянка, з якої найчастіше (за замовленнями) приходять до `key`; `None` — `key` завжди перша або її немає."""
    count = {}
    for route in routes:
        steps = route["stations"]
        for prev, cur in zip(steps, steps[1:], strict=False):
            if cur == key and prev != key:
                count[prev] = count.get(prev, 0) + route["orders"]
    return sorted(count, key=lambda k: (-count[k], k))[0] if count else None


def line_capacity(capacity, routes):
    """Пропускна здатність лінії: кожен маршрут бере частку потужності ділянки пропорційно своїм замовленням.

    `capacity` — `{key: одиниць за вікно | None}`; маршрут обмежує найменша частка (`limiter`), лінія = сума маршрутів.
    Ділянки без потужності (немає даних) не обмежують. Спрощення: спільна ділянка ділиться між маршрутами назавжди.
    """
    served = {}
    for route in routes:
        for key in set(route["stations"]):
            served[key] = served.get(key, 0) + route["orders"]
    items = []
    for route in routes:
        parts = {}
        for key in dict.fromkeys(route["stations"]):
            cap = capacity.get(key)
            if cap:
                parts[key] = cap * route["orders"] / served[key]
        if parts:
            limiter = min(parts, key=lambda k: (parts[k], k))
            items.append(
                {
                    "stations": route["stations"],
                    "orders": route["orders"],
                    "capacity": parts[limiter],
                    "limiter": limiter,
                    "parts": parts,
                }
            )
    return {"total": sum(i["capacity"] for i in items), "routes": items}


def what_if(capacity, routes, key, boost_pct=BOOST_DEFAULT):
    """«Що якщо»: `+boost_pct %` потужності ділянки `key` → приріст випуску лінії і наступне обмеження.

    `{"station", "boost_pct", "base", "after", "gain_pct", "next", "capped"}` або `None` (немає потужності, маршрутів).
    `next` — що обмежуватиме далі на найбільшому маршруті через `key`; `capped` — приріст менший за підвищення, бо
    це обмеження спрацьовує вже в межах `+boost_pct %`.
    """
    if not capacity.get(key):
        return None
    base = line_capacity(capacity, routes)
    if not base["total"]:
        return None
    boosted = {**capacity, key: capacity[key] * (1.0 + boost_pct / 100.0)}
    after = line_capacity(boosted, routes)
    through = [r for r in after["routes"] if key in r["parts"]]
    if not through:
        return None
    main = sorted(through, key=lambda r: (-r["orders"], r["stations"]))[0]
    capped = main["limiter"] != key
    if capped:
        nxt = main["limiter"]
    else:
        others = {k: v for k, v in main["parts"].items() if k != key}
        nxt = min(others, key=lambda k: (others[k], k)) if others else None
    return {
        "station": key,
        "boost_pct": float(boost_pct),
        "base": base["total"],
        "after": after["total"],
        "gain_pct": (after["total"] / base["total"] - 1.0) * 100.0,
        "next": nxt,
        "capped": capped,
    }


def fmt_num(value):
    """`14.0` → `14`, `14.25` → `14,3` (десяткова кома, один знак)."""
    text = ("%.1f" % value).rstrip("0").rstrip(".")
    return text.replace(".", ",") if text not in ("", "-0") else "0"


def hint_text(res, names):
    """«+20 % потужності на Розкрій → +14 % випуску, далі обмежує Присадка»; порожньо без `res`."""
    if not res:
        return ""
    text = "+%s %% потужності на %s → +%s %% випуску" % (
        fmt_num(res["boost_pct"]),
        names.get(res["station"], res["station"]),
        fmt_num(max(0.0, res["gain_pct"])),
    )
    if res.get("next"):
        return "%s, далі обмежує %s" % (text, names.get(res["next"], res["next"]))
    return "%s, інших обмежень у даних немає" % text


def analyze(stations, orders, t0, t1, boost_pct=BOOST_DEFAULT, load_min=LOAD_MIN):
    """Повний розрахунок: рейтинг ділянок, вузьке місце, «що якщо» і підказка.

    `{"rows": [рейтинг], "bottleneck": key | None, "verdict": …, "what_if": …, "hint": str, "routes": [...]}`.
    """
    rows = station_rows(stations, orders, t0, t1)
    key, verdict = find_bottleneck(rows, load_min)
    routes = build_routes(orders)
    capacity = {r["key"]: r["capacity"] for r in rows}
    res = what_if(capacity, routes, key, boost_pct) if key else None
    names = {r["key"]: r["name"] for r in rows}
    return {
        "rows": rank_rows(rows, key),
        "bottleneck": key,
        "verdict": verdict,
        "what_if": res,
        "hint": hint_text(res, names),
        "routes": routes,
        "upstream": main_upstream(routes, key) if key else None,
    }
