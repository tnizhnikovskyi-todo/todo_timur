"""Спільні кроки сценаріїв: BESS, КГУ, скидання/відновлення навантажень (R-45, R-49, R-50, R-51)."""

from __future__ import annotations

from typing import Any

from .. import limits
from ..config import ShedItem
from ..interlocks import OK, Ctx, evaluate
from ..model import Env, Event, Request, W

BESS_OK_STATES = (1, 2, 4)
CHP_CHECKS = ({"code": "chp_ready"}, {"code": "chp_gas_pressure"}, {"code": "chp_permit"})


def ev(
    scenario: str,
    kind: str,
    text: str,
    level: str = "info",
    signal: str | None = None,
    value: float | None = None,
    result: str = "виконано",
) -> Event:
    return Event(scenario, kind, text, signal, value, result, level)


def once(env: Env, key: str, value: Any) -> bool:
    """`True`, якщо значення за ключем змінилося (подія «раз на зміну», R-44 п.4/п.5)."""
    seen = env.shared.setdefault("seen", {})
    if seen.get(key, False) == value:  # початкове значення — «ні»: перша подія лише при переході
        return False
    seen[key] = value
    return True


def written(env: Env, target: str, value: float | str | None) -> bool:
    """Останній наш запис у `target` має це значення (підтвердження доставки без читання назад)."""
    live, code = env.inp.live, env.cfg.sig(target)
    last = live.last_write(code) if live is not None and code else None
    return last is not None and last[0] == value


# --- BESS ------------------------------------------------------------------------------------------
def bess_floor(env: Env) -> float:
    """Ефективний пол SOC: `max(bess_min_soc_pct, plant.bess_reserve_pct, 10)` (R-45 п.4)."""
    return max(
        float(env.cfg.params("peak")["bess_min_soc_pct"]),
        float(env.cfg.plant["bess_reserve_pct"]),
        limits.SOC_FLOOR_PCT,
    )


def bess_state_ok(env: Env) -> bool:
    st = env.inp.v("bess_state")
    return st is not None and int(st) in BESS_OK_STATES


def bess_request(
    scenario: str, mode: int, setpoint: float, until: float, valid_s: int = limits.BESS_WATCHDOG_S
) -> Request:
    """Запис у порядку R-42: уставка, межа SOC, сторожовий таймер, режим — останнім."""
    return Request(
        "bess",
        [W("bess_sp", round(setpoint)), W("bess_until", round(until)), W("bess_valid", valid_s), W("bess_mode", mode)],
        scenario,
        watchdog="bess_valid",
        refresh_s=limits.BESS_REFRESH_S,
    )


def bess_release_request(scenario: str) -> Request:
    return Request("bess", [W("bess_mode", 0), W("bess_valid", 0)], scenario)


# --- КГУ -------------------------------------------------------------------------------------------
def chp_state(env: Env) -> dict[str, Any]:
    return env.shared.setdefault("chp", {"owner": None, "started_at": None, "stopped_at": None})


def chp_startable(env: Env, *, min_off_min: float) -> tuple[bool, str]:
    """КГУ готова до пуску: `chp_state = 0`, перевірки `chp_ready`/`chp_gas_pressure`/`chp_permit` — ok, пауза після
    останньої зупинки минула, власник не оператор і не інший сценарій (R-45 п.5, R-50 п.2)."""
    inp, chp = env.inp, chp_state(env)
    state = inp.v("chp_state")
    if state is None or int(state) != 0:
        return False, "КГУ не в резерві"
    ctx = Ctx.from_inputs(inp, ("chp_state", "chp_gas", "chp_permit"))
    rows, blocked, reason = evaluate(CHP_CHECKS, env.cfg, ctx)
    if any(r["state"] != OK for r in rows):
        bad = next(r for r in rows if r["state"] != OK)
        return False, f"{bad['code']}: {bad['detail']}"
    stopped = chp.get("stopped_at")
    if stopped is not None and env.epoch - float(stopped) < min_off_min * 60.0:
        return False, "пауза після зупинки"
    if chp.get("owner") == "manual":
        return False, "КГУ у владінні оператора"
    return not blocked, reason or ""


def chp_run_h(env: Env) -> float | None:
    started = chp_state(env).get("started_at")
    return None if started is None else (env.epoch - float(started)) / 3600.0


def chp_start_request(scenario: str) -> Request:
    return Request("chp", [W("chp_cmd", 1)], scenario)


def chp_stop_request(scenario: str) -> Request:
    return Request("chp", [W("chp_cmd", 2)], scenario)


# --- скидання/відновлення навантажень (R-51) ---------------------------------------------------------
def shed_list(env: Env) -> list[dict[str, Any]]:
    return env.shared.setdefault("shed_list", [])


def _how(item: ShedItem) -> str:
    if item.action == "reduce":
        return f"знижено до {item.param:g} %"
    if item.action == "off":
        return "вимкнено"
    return f"{'пауза' if item.action == 'pause' else 'відкладено'} на {item.param:g} хв"


def shed_more(env: Env, scenario: str, need_kw: float, *, allow_critical: bool) -> tuple[float, list[Event]]:
    """R-51 п.2: скинути ще не скинуті елементи за пріоритетом, поки сума `kw` не покриє `need_kw`."""
    cfg, inp, now = env.cfg, env.inp, env.epoch
    lst = shed_list(env)
    done = {s["node"] for s in lst}
    cumulative, events = 0.0, []
    for item in sorted(cfg.shed, key=lambda i: i.seq):
        if cumulative >= need_kw:
            break
        if item.node in done:
            continue
        if item.node in cfg.never_shed:
            if once(env, f"shed:never:{item.node}", True):
                events.append(ev(scenario, "interlock", f"Скидання {item.node} заборонено (never_shed)", "warn"))
            continue
        if item.critical and not allow_critical:
            continue
        if item.condition == "air_pressure_min":
            air = inp.v("air_bar")
            if air is None or air < float(item.condition_value or 0.0):
                continue
        elif item.condition == "no_active_cycle":  # у v1 немає сигналу стану циклу → unknown → пропускаємо (Q-32)
            if once(env, f"shed:cycle:{item.node}", True):
                events.append(
                    ev(scenario, "interlock", f"Скидання пропущено: немає даних про цикл {item.node}", "warn")
                )
            continue
        pct = float(item.param) if item.action == "reduce" else 0.0
        timer = now + float(item.param) * 60.0 if item.action in ("pause", "defer") else None
        lst.append(
            {
                "node": item.node,
                "signal": item.signal,
                "pct": pct,
                "by": scenario,
                "t": now,
                "kw": item.kw,
                "timer_until": timer,
            }
        )
        cumulative += float(item.kw)
        events.append(ev(scenario, "auto_step", f"Скинуто: {item.node} — {_how(item)}", signal=item.signal, value=pct))
    return cumulative, events


def restore_one(env: Env, scenario: str, *, step_s: float | None = None) -> list[Event]:
    """R-51 п.3: у зворотному порядку, один елемент за `shed_restore_step_s`."""
    step = env.cfg.engine.shed_restore_step_s if step_s is None else step_s
    shared = env.shared
    if env.epoch - float(shared.get("last_restore", 0.0)) < step:
        return []
    for it in reversed(shed_list(env)):
        if it["pct"] != 100.0:
            it["pct"] = 100.0
            shared["last_restore"] = env.epoch
            return [ev(scenario, "auto_release", f"Повернуто: {it['node']}", signal=it["signal"], value=100)]
    return []


def housekeeping(env: Env) -> list[Event]:
    """Таймери `pause`/`defer` (R-51 п.2 в) і прибирання вже відновлених елементів (запис 100 % підтверджено)."""
    events, lst = [], shed_list(env)
    for it in lst:
        if it["pct"] != 100.0 and it.get("timer_until") is not None and env.epoch >= float(it["timer_until"]):
            it["pct"] = 100.0
            events.append(
                ev(it["by"], "auto_release", f"Повернуто за таймером: {it['node']}", signal=it["signal"], value=100)
            )
    keep = [it for it in lst if not (it["pct"] == 100.0 and written(env, it["signal"], 100.0))]
    if len(keep) != len(lst):
        lst[:] = keep
        if not keep:
            env.shared["shed_zero_pending"] = True
    if env.shared.get("shed_zero_pending") and written(env, "shed_valid", 0.0):
        env.shared["shed_zero_pending"] = False
    return events


def shed_request(env: Env) -> Request | None:
    """Бажаний стан ресурсу `shed`: усі скинуті елементи + сторожовий таймер 60 с (перезапис кожні 20 с)."""
    lst = shed_list(env)
    if lst:
        writes = [W("shed_valid", limits.SHED_WATCHDOG_S)] + [W(it["signal"], it["pct"]) for it in lst]
        return Request("shed", writes, lst[-1]["by"], watchdog="shed_valid", refresh_s=limits.SHED_REFRESH_S)
    if env.shared.get("shed_zero_pending") and not env.shared.get("pv_limited"):  # shed_valid ділить із pv_limit
        return Request("shed", [W("shed_valid", 0)], "")
    return None


def shed_kw(env: Env) -> float:
    return sum(float(it["kw"]) for it in shed_list(env) if it["pct"] != 100.0)
