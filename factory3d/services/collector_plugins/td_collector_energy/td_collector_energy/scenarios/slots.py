"""Крок `slots`: виконання BESS-слотів розкладу (R-54 п.5); нижчий пріоритет за `peak`/`self` і ручне перекриття."""

from __future__ import annotations


from .. import limits
from ..config import Slot
from ..model import Env, Output
from ..timeutil import hours_of, local, weekday_ok
from . import common as c


def active_slots(env: Env, resource: str) -> list[Slot]:
    """Слоти ресурсу, у вікно яких потрапляє поточний місцевий час (дата/день тижня/година)."""
    t = local(env.now)
    h, day = hours_of(env.now), t.date()
    out = []
    for s in env.cfg.slots:
        if s.resource != resource:
            continue
        if s.date is not None and s.date != day:
            continue
        if s.date is None and not weekday_ok(s.weekdays, day):
            continue
        if s.start <= h < s.end:
            out.append(s)
    return out


def step(env: Env) -> Output:
    cfg, inp = env.cfg, env.inp
    st = env.scen.setdefault("slots", {"active": False})
    out = Output(state="armed")
    slots = [s for s in active_slots(env, "bess") if s.mode in ("charge", "discharge")]
    soc = inp.v("bess_soc")
    if not slots or soc is None or not c.bess_state_ok(env) or not env.free("bess"):
        if st["active"] and env.shared.get("bess_by") == "slots":
            out.requests.append(c.bess_release_request("slots"))
            env.shared["bess_by"] = None
            out.events.append(c.ev("slots", "auto_release", "Слот BESS завершено"))
        st["active"] = False
        return out
    slot = slots[0]
    p_max = min(float(cfg.params("peak")["bess_max_kw"]), limits.BESS_KW_MAX, cfg.limits.bess_kw_max)
    sp = min(float(slot.setpoint_kw or p_max), limits.BESS_KW_MAX, cfg.limits.bess_kw_max)
    if slot.mode == "charge":
        target = float(cfg.params("self")["bess_target_soc_pct"])
        if soc >= target:
            return out
        req = c.bess_request("slots", 1, sp, target)
    else:
        floor = c.bess_floor(env)
        if soc <= floor + 2:
            return out
        req = c.bess_request("slots", 2, sp, floor)
    out.requests.append(req)
    if not st["active"]:
        out.events.append(
            c.ev("slots", "auto_step", f"Слот BESS: {'заряд' if slot.mode == 'charge' else 'розряд'} {round(sp)} кВт")
        )
    st["active"] = True
    env.shared["bess_by"] = "slots"
    out.state = "active"
    return out
