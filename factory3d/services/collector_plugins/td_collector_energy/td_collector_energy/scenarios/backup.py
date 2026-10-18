"""Сценарій «Резервне живлення» (АВР → ДГУ; R-49, CT-08): АВР перемикає апаратно, рушій лише скидає/повертає."""

from __future__ import annotations

from typing import Any

from ..model import Env, Output
from . import common as c

DEBOUNCE_TICKS = 2  # стійка умова ≥ 2 тіків (4 с)
STAGE_DELAY_DEFAULT_S = 10.0


def _defaults() -> dict[str, Any]:
    return {"lost_ticks": 0, "active": False, "restored_since": None, "last_shed": 0.0}


def step(env: Env) -> Output:
    cfg, inp, now = env.cfg, env.inp, env.epoch
    sc, p = cfg.scenario("backup"), cfg.params("backup")
    st = env.scen.setdefault("backup", _defaults())
    for k, v in _defaults().items():
        st.setdefault(k, v)
    out = Output()
    env.shared["backup_active"] = bool(st["active"])
    if not sc.enabled and not st["active"]:
        out.state = "off"
        return out
    missing = [n for n in ("ats_pos", "src1_ok") if inp.v(n) is None]
    if missing:
        out.state, out.facts = "warn", {"reason": "немає даних: " + ", ".join(inp.code_list(missing))}
        return out
    src, pos = float(inp.v("src1_ok") or 0.0), float(inp.v("ats_pos") or 0.0)
    lost = src == 0 or pos == 3
    st["lost_ticks"] = st["lost_ticks"] + 1 if lost else 0
    if not st["active"] and st["lost_ticks"] >= DEBOUNCE_TICKS and sc.enabled:
        st.update(active=True, restored_since=None, last_shed=0.0)
        out.events.append(c.ev("backup", "auto_step", "Втрата мережі: резервне живлення, скидання навантажень"))
    env.shared["backup_active"] = bool(st["active"])
    if not st["active"]:
        out.state, out.facts = "armed", {}
        return out
    if lost:
        st["restored_since"] = None
        delay = float(cfg.params("peak").get("stage_delay_s", STAGE_DELAY_DEFAULT_S))
        if now - float(st["last_shed"]) >= delay:
            st["last_shed"] = now
            p_total = inp.v("p_total")
            need = float("inf") if p_total is None else max(0.0, p_total - 0.9 * float(p["genset_capacity_kw"]))
            if need > 0:
                _added, events = c.shed_more(env, "backup", need, allow_critical=False)
                out.events += events
    else:
        st["restored_since"] = st["restored_since"] if st["restored_since"] is not None else now
        if now - float(st["restored_since"]) >= float(p["restore_delay_s"]):
            events = c.restore_one(env, "backup")
            out.events += events
            if not events and not any(i["pct"] != 100 for i in c.shed_list(env)):
                st.update(active=False, restored_since=None, lost_ticks=0)
                env.shared["backup_active"] = False
                out.events.append(c.ev("backup", "auto_release", "Мережа відновлена: навантаження повернено"))
    out.state = "active"
    out.facts = {"shed_n": sum(1 for i in c.shed_list(env) if i["pct"] != 100)}
    return out
