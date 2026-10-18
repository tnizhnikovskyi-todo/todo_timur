"""Сценарій «Срезание пика» (BESS → КГУ → скидання; R-45, CT-04)."""

from __future__ import annotations

from typing import Any

from .. import limits
from ..model import Env, Event, Output
from ..timeutil import BLOCK_S, block_start
from . import common as c

REQUIRED = ("grid_kw", "bess_soc")
MAX_GAP_S = 60.0  # пропуск між тіками довший — акумулятор не інтегрує (рестарт, зависання)
FIRST_S = 30.0  # перші 30 с блока прогноз = миттєвий імпорт


def _defaults(now: float) -> dict[str, Any]:
    return {
        "stage": "idle",
        "acc_kws": 0.0,
        "block_start": block_start(now),
        "last_t": now,
        "uncovered_since": None,
        "last_escalation": 0.0,
        "release_since": None,
        "release_phase": None,
        "bess_cmd": 0.0,
        "bess_ramp_t": 0.0,
    }


def forecast(st: dict[str, Any], grid: float, now: float) -> float:
    """Прогноз 15-хв інтервалу: блок вирівняний за UTC-епохою, `proj = (acc + grid·remaining) / 900` (R-45 п.1)."""
    block = block_start(now)
    if st.get("block_start") != block:
        st["block_start"], st["acc_kws"] = block, 0.0
    dt = now - float(st.get("last_t", now))
    if 0 < dt <= MAX_GAP_S:
        st["acc_kws"] += grid * dt
    st["last_t"] = now
    elapsed = now - block
    if elapsed < FIRST_S:
        return grid
    return (float(st["acc_kws"]) + grid * (BLOCK_S - elapsed)) / BLOCK_S


def _release_ready(st: dict[str, Any], p: dict[str, Any], proj: float, grid: float, now: float, enabled: bool) -> bool:
    """Умова відпускання: прогноз і імпорт нижче `limit − release_margin` безперервно `release_hold_s` (п.7)."""
    if not enabled:
        return True
    low = float(p["limit_kw"]) - float(p["release_margin_kw"])
    if not (proj <= low and grid <= low):
        st["release_since"] = None
        return False
    st["release_since"] = st["release_since"] if st["release_since"] is not None else now
    return now - float(st["release_since"]) >= float(p["release_hold_s"])


def step(env: Env) -> Output:
    cfg, inp, now = env.cfg, env.inp, env.epoch
    sc, p = cfg.scenario("peak"), cfg.params("peak")
    st = env.scen.setdefault("peak", _defaults(now))
    for k, v in _defaults(now).items():
        st.setdefault(k, v)
    out = Output()
    if env.shared.get("backup_active"):  # R-49 п.1: на час резерву сценарій призупинено, скидання лишаються
        out.state, out.facts = "armed", {"reason": "резервне живлення"}
        st.update(stage="idle", release_phase=None, release_since=None, uncovered_since=None, bess_cmd=0.0)
        return out
    holding = st["stage"] != "idle" or bool(c.shed_list(env))
    if not sc.enabled and not holding:
        out.state = "off"
        return out
    missing = [n for n in REQUIRED if inp.v(n) is None]
    if missing:
        out.state, out.facts = "warn", {"reason": "немає даних: " + ", ".join(inp.code_list(missing))}
        return out
    grid, soc = float(inp.v("grid_kw") or 0.0), float(inp.v("bess_soc") or 0.0)
    proj = forecast(st, grid, now)
    limit = float(p["limit_kw"])
    facts: dict[str, Any] = {"margin_kw": round(limit - grid), "proj_kw": round(proj), "grid_kw": round(grid)}

    if st["stage"] == "idle":
        if sc.enabled and (proj >= limit - float(p["activate_margin_kw"]) or grid >= limit):
            st.update(
                stage="bess",
                uncovered_since=None,
                last_escalation=now,
                release_since=None,
                release_phase=None,
                bess_cmd=0.0,
            )
            out.events.append(c.ev("peak", "auto_step", f"Зрізання піку: старт, прогноз {round(proj)} кВт"))
        else:
            out.events += _idle_housekeeping(env, out)
            out.state, out.facts = ("armed" if sc.enabled else "off"), facts
            return out

    # --- ступінь 1: BESS ------------------------------------------------------------------------
    excess = grid - (limit - float(p["margin_kw"]))
    p_max = min(float(p["bess_max_kw"]), limits.BESS_KW_MAX, cfg.limits.bess_kw_max)
    floor = c.bess_floor(env)
    bess_kw = inp.v("bess_kw") or 0.0
    bess_now = max(0.0, -bess_kw)
    avail = c.bess_state_ok(env) and soc > floor + 2 and env.free("bess")
    if c.bess_state_ok(env) and env.free("bess") and soc <= floor + 2:
        if c.once(env, "peak:reserve", True):
            out.events.append(c.ev("peak", "interlock", f"BESS на резерві {round(soc)} %", "warn"))
    else:
        c.once(env, "peak:reserve", False)
    if c.bess_state_ok(env) and not env.free("bess"):
        if c.once(env, "peak:override", True):
            out.events.append(c.ev("peak", "override", "Зрізання піку: BESS під ручним керуванням", "warn"))
    else:
        c.once(env, "peak:override", False)
    p_target = min(max(bess_now + excess, 0.0), p_max)
    uncovered = excess - (p_target - bess_now) if avail else excess

    # --- відпускання (п.7) чи ескалація (п.5, п.6) ------------------------------------------------
    phase = st["release_phase"]
    if phase is not None and grid >= limit:  # лімит знову порушено: відпускання скасовано
        phase, st["release_phase"], st["release_since"] = None, None, None
    if phase is None and _release_ready(st, p, proj, grid, now, sc.enabled):
        phase = st["release_phase"] = "shed"
    if phase is None:
        if avail and (excess > 0 or st["bess_cmd"] > 0 or abs(p_target - float(st["bess_cmd"])) >= 5):
            st["bess_cmd"] = p_target
            out.requests.append(c.bess_request("peak", 2, p_target, floor))
            env.shared["bess_by"] = "peak"
        out.events += _escalate(env, st, p, uncovered, out) if sc.enabled else []
    else:
        out.events += _release(env, st, p, out)
        if avail and st["release_phase"] == "shed" or avail and st["release_phase"] == "chp":
            if st["bess_cmd"] > 0 and not any(r.resource == "bess" for r in out.requests):
                out.requests.append(c.bess_request("peak", 2, p_target, floor))

    facts.update(stage=st["stage"], bess_kw=round(bess_kw), shed_n=sum(1 for i in c.shed_list(env) if i["pct"] != 100))
    out.state, out.facts = "active", facts
    return out


def _escalate(env: Env, st: dict[str, Any], p: dict[str, Any], uncovered: float, out: Output) -> list[Event]:
    """Ступінь 2 (КГУ) і 3 (скидання), якщо `uncovered > 0` довше `stage_delay_s`; під час розгону КГУ не ескалуємо."""
    now, cfg, events = env.epoch, env.cfg, []
    if uncovered <= 0:
        st["uncovered_since"] = None
        return events
    st["uncovered_since"] = st["uncovered_since"] if st["uncovered_since"] is not None else now
    delay = float(p["stage_delay_s"])
    if now - float(st["uncovered_since"]) < delay or now - float(st["last_escalation"]) < delay:
        return events
    chp_state = env.inp.v("chp_state")
    startable, _why = c.chp_startable(env, min_off_min=float(cfg.params("chp")["min_off_min"]))
    if bool(p["chp_allowed"]) and startable:
        c.chp_state(env).update(owner="peak", started_at=now)
        out.requests.append(c.chp_start_request("peak"))
        st.update(stage="chp", last_escalation=now)
        events.append(c.ev("peak", "auto_step", "Зрізання піку: пуск КГУ", signal=cfg.sig("chp_cmd"), value=1))
    elif chp_state is not None and int(chp_state) == 1:
        return events  # КГУ розганяється: чекаємо (AC-251)
    elif bool(p["shed_allowed"]):
        added, more = c.shed_more(env, "peak", uncovered, allow_critical=True)
        events += more
        if added > 0:
            st.update(stage="shed", last_escalation=now)
    return events


def _release(env: Env, st: dict[str, Any], p: dict[str, Any], out: Output) -> list[Event]:
    """У зворотному порядку: скинуті навантаження → КГУ (лише власна й після `min_run_h`) → BESS (рампа до 0)."""
    now, cfg, events = env.epoch, env.cfg, []
    if any(i["pct"] != 100 for i in c.shed_list(env)):
        st["release_phase"] = "shed"
        return c.restore_one(env, "peak")
    chp, chp_state = c.chp_state(env), env.inp.v("chp_state")
    if chp.get("owner") == "peak" and chp_state is not None and int(chp_state) in (1, 2):
        run_h = c.chp_run_h(env)
        if run_h is not None and run_h >= float(cfg.params("chp")["min_run_h"]):
            chp.update(owner=None, stopped_at=now, started_at=None)
            out.requests.append(c.chp_stop_request("peak"))
            events.append(
                c.ev("peak", "auto_release", "Зрізання піку: КГУ зупинено", signal=cfg.sig("chp_cmd"), value=2)
            )
            return events
        if cfg.scenario("chp").enabled:
            chp["owner"] = "chp"  # власність переходить до сценарію «КГУ за графіком і ціною»
    st["release_phase"] = "bess"
    cmd = float(st["bess_cmd"])
    if cmd > 0 and env.free("bess") and c.bess_state_ok(env):
        if now - float(st["bess_ramp_t"]) >= limits.BESS_REFRESH_S:
            p_max = min(float(p["bess_max_kw"]), limits.BESS_KW_MAX)
            st["bess_cmd"] = cmd = max(0.0, cmd - p_max / 4.0)
            st["bess_ramp_t"] = now
        if cmd > 0:
            out.requests.append(c.bess_request("peak", 2, cmd, c.bess_floor(env)))
            return events
    out.requests.append(c.bess_release_request("peak"))
    st.update(stage="idle", release_since=None, release_phase=None, bess_cmd=0.0, uncovered_since=None)
    env.shared["bess_by"] = None
    events.append(c.ev("peak", "auto_release", "Зрізання піку завершено"))
    return events


def _idle_housekeeping(env: Env, out: Output) -> list[Event]:
    """Залишки після рестарту/вимкнення: відновити скинуте; зупинити власну КГУ, коли відпрацьовано `min_run_h`."""
    events = c.restore_one(env, "peak") if c.shed_list(env) else []
    chp, state = c.chp_state(env), env.inp.v("chp_state")
    if chp.get("owner") == "peak" and state is not None and int(state) == 2 and not events:
        run_h = c.chp_run_h(env)
        if run_h is not None and run_h >= float(env.cfg.params("chp")["min_run_h"]):
            chp.update(owner=None, stopped_at=env.epoch, started_at=None)
            out.requests.append(c.chp_stop_request("peak"))
            events.append(c.ev("peak", "auto_release", "Зрізання піку: КГУ зупинено", value=2))
    return events
