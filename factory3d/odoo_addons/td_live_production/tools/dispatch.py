"""Диспетчер (LP-03): наступні кроки нарядів, простоїв, закриття МО й відвантаження. Без ORM.

`simulate` — дискретна симуляція від поточного стану (його ORM збирає з бази на кожному тику) до `now`: видає події з
часовими мітками в хронологічному порядку. Тому один тик після паузи дає ті самі записи, що й тики щохвилини, а перший
запуск посеред доби одразу закриває все, що за планом мало закінчитись. Кроки ідемпотентні: стан береться з бази, а
фактична тривалість — функція ключа наряду (`noise`).

Стан:
- `wos[id] = {mo, wc, state, plan_start, minutes, start, end}`, `state` ∈ blocked/ready/progress/done;
- `mos[id] = {wos: [id у порядку маршруту], so, done_at}`;
- `sos[id] = {mos: [id], shipped}`;
- `dts[id] = {wc, plan_start, minutes, kind, reason, state, start, end}`, `state` ∈ planned/active/done.
"""

import copy
from datetime import datetime, timedelta

from . import clock
from .noise import NOISE_PCT, noisy_minutes

SHIP_DELAY_MIN = 20
HORIZON_MIN = 15  # `until` цілі не далі за стільки хвилин від тику: цілі оновлюються щохвилини й не закінчуються
IDLE_REASON = "Немає завдання"
OFF_REASON = "Поза зміною"
TARGET_PAD_MIN = 2  # запас `until` понад плановий кінець стану (C-LP-01: `until` у минулому знімає ціль)
MAX_EVENTS = 20000
# порядок подій з однаковим часом: завершення, закінчення простою, МО, початок простою, початок наряду, відвантаження
ORDER = {"wo_finish": 0, "dt_end": 1, "mo_done": 2, "dt_start": 3, "wo_start": 4, "ship": 5}


def actual_minutes(wo_id, planned, pct=NOISE_PCT):
    """Фактична тривалість наряду: план ±15 % за ключем `wo<id>`."""
    return noisy_minutes(planned, "wo%s" % wo_id, pct)


def _prev_end(state, wo_id):
    """Коли завершилась попередня операція МО; `None` — ще ні; `datetime.min` — попередньої немає (перша)."""
    mo = state["mos"][state["wos"][wo_id]["mo"]]
    idx = mo["wos"].index(wo_id)
    if idx == 0:
        return datetime.min
    prev = state["wos"][mo["wos"][idx - 1]]
    return prev["end"] if prev["state"] == "done" else None


def simulate(state, now, shift, workdays="0123456", pct=NOISE_PCT, ship_delay=SHIP_DELAY_MIN):
    """`(події, підсумковий стан)`; подія — `{"t", "kind", "id"}`, `kind` ∈ ORDER, `id` — наряд/простій/МО/SO."""
    st = copy.deepcopy(state)
    wos, mos, sos, dts = st["wos"], st["mos"], st["sos"], st["dts"]
    busy = {}  # (тип, id) → (верстат, коли звільниться): верстат може мати кілька таких (наряд запустили ззовні)
    free_at = {}
    for wid, wo in wos.items():
        if wo["state"] == "progress":
            start = wo["start"] or now
            wo["start"] = start
            busy[("wo", wid)] = (wo["wc"], start + timedelta(minutes=actual_minutes(wid, wo["minutes"], pct)))
        elif wo["state"] == "done" and wo["end"]:
            free_at[wo["wc"]] = max(free_at.get(wo["wc"], wo["end"]), wo["end"])
    for did, dt in dts.items():
        if dt["state"] == "active":
            busy[("dt", did)] = (dt["wc"], dt["start"] + timedelta(minutes=dt["minutes"]))
        elif dt["state"] == "done" and dt["end"]:
            free_at[dt["wc"]] = max(free_at.get(dt["wc"], dt["end"]), dt["end"])
    events = []
    for _ in range(MAX_EVENTS):
        best = None

        def offer(t, kind, ident):
            nonlocal best
            key = (t, ORDER[kind], ident)
            if best is None or key < best[0]:
                best = (key, t, kind, ident)

        taken = {wc for wc, _ in busy.values()}
        for (typ, ident), (_, end) in busy.items():
            offer(end, "wo_finish" if typ == "wo" else "dt_end", ident)
        for did, dt in dts.items():
            if dt["state"] == "planned" and dt["wc"] not in taken:
                t = clock.next_shift_start(
                    max(dt["plan_start"], free_at.get(dt["wc"], dt["plan_start"])), shift, workdays
                )
                offer(t, "dt_start", did)
        for wid, wo in wos.items():
            if wo["state"] in ("done", "progress") or wo["wc"] in taken:
                continue
            prev = _prev_end(st, wid)
            if prev is None:
                continue
            t = max(wo["plan_start"] or now, prev, free_at.get(wo["wc"], datetime.min))
            offer(clock.next_shift_start(t, shift, workdays), "wo_start", wid)
        for sid, so in sos.items():
            if so["shipped"] or not so["mos"] or any(mos[m]["done_at"] is None for m in so["mos"] if m in mos):
                continue
            ready = max(mos[m]["done_at"] for m in so["mos"] if m in mos) + timedelta(minutes=ship_delay)
            offer(clock.next_shift_start(ready, shift, workdays), "ship", sid)
        if best is None or best[1] > now:
            break
        _, t, kind, ident = best
        events.append({"t": t, "kind": kind, "id": ident})
        _apply(st, busy, free_at, t, kind, ident, events, pct)
    else:
        raise RuntimeError("simulate: перевищено %s подій" % MAX_EVENTS)
    return events, st


def _apply(st, busy, free_at, t, kind, ident, events, pct):
    wos, mos, sos, dts = st["wos"], st["mos"], st["sos"], st["dts"]
    if kind == "wo_start":
        wo = wos[ident]
        wo.update(state="progress", start=t)
        busy[("wo", ident)] = (wo["wc"], t + timedelta(minutes=actual_minutes(ident, wo["minutes"], pct)))
    elif kind == "wo_finish":
        wo = wos[ident]
        wo.update(state="done", end=t)
        busy.pop(("wo", ident), None)
        free_at[wo["wc"]] = t
        mo = mos[wo["mo"]]
        if all(wos[w]["state"] == "done" for w in mo["wos"]):
            mo["done_at"] = t
            events.append({"t": t, "kind": "mo_done", "id": wo["mo"]})
    elif kind == "dt_start":
        dt = dts[ident]
        dt.update(state="active", start=t)
        busy[("dt", ident)] = (dt["wc"], t + timedelta(minutes=dt["minutes"]))
    elif kind == "dt_end":
        dt = dts[ident]
        dt.update(state="done", end=t)
        busy.pop(("dt", ident), None)
        free_at[dt["wc"]] = t
    elif kind == "ship":
        sos[ident]["shipped"] = True


def machine_targets(
    state,
    now,
    pad_min=TARGET_PAD_MIN,
    pct=NOISE_PCT,
    machines=None,
    shift=None,
    workdays="0123456",
    horizon_min=HORIZON_MIN,
    calendar=None,
):
    """Цілі верстатам для емулятора (C-LP-01) за станом ПІСЛЯ `simulate`: `[{"wc", "state", "reason", "until"}]`.

    Пріоритет: наряд у роботі → `working`; активний простій → `idle` (налагодження, очікування) або `down` (лише
    аварія) із причиною; інакше верстат без роботи → `idle` «Немає завдання», а поза зміною → `idle` «Поза зміною».
    `machines` — усі верстати демо (id РЦ): ціль отримує КОЖЕН, інакше емулятор веде «вільні» верстати сам і майже всі
    вони «працюють», що не збігається з планом. Без `machines` — лише зайняті (старий режим).

    Додатково до `wc/state/reason/until` кожна ціль має `kind` (`work`/`downtime`/`no_task`/`off`) і для простою `dt`
    (id запланованого простою): за ними диспетчер ставить машинному шару причину простою; емулятору вони не шлються.

    «Поза зміною» визначає календар РЦ (`calendar = {id РЦ: [(початок, кінець)] планового часу}`, той самий, що в
    `td_machine_connect` для OEE й ₴: обід і вихідні теж «поза зміною»); для РЦ без календаря — зміна `shift`.

    `until` = найближча зміна стану за планом + `pad_min` хв запасу (емулятор знімає ціль, коли `until` минув), але не
    пізніше `now + horizon_min`: тик оновлює цілі щохвилини, тож вони не закінчуються.
    """
    pad = timedelta(minutes=pad_min)
    cap = now + timedelta(minutes=horizon_min)

    def until(change):
        return min(max(change, now) + pad, cap)

    by_wc = {}
    for wid, wo in state["wos"].items():
        if wo["state"] == "progress" and wo["start"]:
            end = wo["start"] + timedelta(minutes=actual_minutes(wid, wo["minutes"], pct))
            by_wc.setdefault(
                wo["wc"], {"wc": wo["wc"], "state": "working", "reason": None, "until": until(end), "kind": "work"}
            )
    for did, dt in state["dts"].items():
        if dt["state"] == "active" and dt["start"] and dt["wc"] not in by_wc:
            end = dt["start"] + timedelta(minutes=dt["minutes"])
            by_wc[dt["wc"]] = {
                "wc": dt["wc"],
                "state": "down" if dt["kind"] == "fault" else "idle",
                "reason": dt["reason"],
                "until": until(end),
                "kind": "downtime",
                "dt": did,
            }
    if machines is not None:
        for wc in machines:
            if wc in by_wc:
                continue
            known, boundary = _plan_boundary(calendar, wc, now, shift, workdays)
            off = known and boundary[0] == "off"
            by_wc[wc] = {
                "wc": wc,
                "state": "idle",
                "reason": OFF_REASON if off else IDLE_REASON,
                "until": until(_next_change(state, wc, now, boundary[1], horizon_min)),
                "kind": "off" if off else "no_task",
            }
    return [by_wc[wc] for wc in sorted(by_wc)]


def _plan_boundary(calendar, wc, now, shift, workdays):
    """`(відомо, ("in"|"off", найближча межа планового часу або None))`: за календарем РЦ, інакше за зміною."""
    if calendar is not None and wc in calendar:
        plan = calendar[wc]
        cover = [e for s, e in plan if s <= now < e]
        if cover:
            return True, ("in", min(cover))
        later = [s for s, _e in plan if s > now]
        return True, ("off", min(later) if later else None)
    if shift is None:
        return False, ("in", None)
    if clock.in_shift(now, shift, workdays):
        return True, ("in", clock.shift_window(clock.local_date(now), shift)[1])
    return True, ("off", clock.next_shift_start(now, shift, workdays))


def _next_change(state, wc, now, boundary, horizon_min):
    """Коли за планом зміниться стан вільного верстата: межа планового часу, плановий старт його наряду чи простою."""
    changes = [boundary] if boundary else []
    for wo in state["wos"].values():
        if wo["wc"] == wc and wo["state"] not in ("done", "progress") and wo["plan_start"] and wo["plan_start"] > now:
            changes.append(wo["plan_start"])
    for dt in state["dts"].values():
        if dt["wc"] == wc and dt["state"] == "planned" and dt["plan_start"] > now:
            changes.append(dt["plan_start"])
    return min(changes) if changes else now + timedelta(minutes=horizon_min)


def catchup_chain(wos, floor=None):
    """Догнати минуле (LP-04): послідовність `(id, початок, кінець)` для нарядів однієї МО за датами їхніх планів.

    `wos = [{"id", "state", "start", "plan_start", "plan_end", "minutes"}]` у порядку маршруту. Початок — фактичний
    (у роботі/завершені), інакше плановий, інакше кінець попереднього; наряд не починається раніше за попередній;
    кінець — плановий, але не раніше за початок + 1 хв (немає плану — початок + `minutes`).
    """
    res = []
    prev_end = floor
    for wo in wos:
        start = wo.get("start") or wo.get("plan_start") or prev_end
        if start is None:
            continue
        if prev_end and start < prev_end:
            start = prev_end
        end = wo.get("plan_end")
        if not end or end < start + timedelta(minutes=1):
            end = start + timedelta(minutes=max(wo.get("minutes") or 0.0, 1.0))
        res.append((wo["id"], start, end))
        prev_end = end
    return res
