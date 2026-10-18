"""Сценарій «Самоспоживання СЕС» (BESS-заряд → обмеження інверторів; R-46, CT-05)."""

from __future__ import annotations

import math
from typing import Any

from .. import limits
from ..model import Env, Output, Request, W
from . import common as c

REQUIRED = ("export_kw", "pv_kw", "bess_soc")


def _defaults() -> dict[str, Any]:
    return {"limit_pct": None, "curtail_since": None, "restore_since": None, "last_pct_write": 0.0, "charging": False}


def step(env: Env) -> Output:
    cfg, inp, now = env.cfg, env.inp, env.epoch
    sc, p = cfg.scenario("self"), cfg.params("self")
    st = env.scen.setdefault("self", _defaults())
    for k, v in _defaults().items():
        st.setdefault(k, v)
    out = Output()
    limit_now = st["limit_pct"]
    if limit_now is None:
        limit_now = st["limit_pct"] = float(inp.v("pv_limit") if inp.v("pv_limit") is not None else 100.0)
    holding = bool(st["charging"]) or limit_now < 100
    if not sc.enabled and not holding:
        out.state = "off"
        return out
    missing = [n for n in REQUIRED if inp.v(n) is None]
    if missing:
        out.state, out.facts = "warn", {"reason": "немає даних: " + ", ".join(inp.code_list(missing))}
        return out
    export, pv, soc = float(inp.v("export_kw") or 0.0), float(inp.v("pv_kw") or 0.0), float(inp.v("bess_soc") or 0.0)
    bess_kw = float(inp.v("bess_kw") or 0.0)
    exp_max, dead = float(p["export_max_kw"]), float(p["export_deadband_kw"])
    target_soc = float(p["bess_target_soc_pct"])
    out.facts = {"export_kw": round(export)}
    charged = 0.0

    # --- BESS: заряд надлишку (п.2) ---------------------------------------------------------------
    peak_busy = env.scen.get("peak", {}).get("stage", "idle") != "idle"
    owner_ok = env.shared.get("bess_by") in (None, "self")
    can_charge = c.bess_state_ok(env) and soc < target_soc - 0.5 and env.free("bess") and not peak_busy and owner_ok
    wants_charge = sc.enabled and pv >= 1 and export > exp_max + dead
    if wants_charge and not env.free("bess") and c.once(env, "self:override", True):
        out.events.append(c.ev("self", "override", "Самоспоживання: BESS під ручним керуванням", "warn"))
    elif not wants_charge or env.free("bess"):
        c.once(env, "self:override", False)
    if wants_charge and can_charge:
        charge_now = max(0.0, bess_kw)
        p_kw = min(
            max(charge_now + (export - exp_max), 0.0),
            float(p["bess_max_kw"]),
            limits.BESS_KW_MAX,
            cfg.limits.bess_kw_max,
        )
        out.requests.append(c.bess_request("self", 1, p_kw, target_soc))
        env.shared["bess_by"] = "self"
        st["charging"] = True
        charged = p_kw - charge_now
        out.facts["bess_kw"] = round(p_kw)
    elif st["charging"] and (not sc.enabled or (export <= 0.0 and (soc >= target_soc or pv < 1)) or peak_busy):
        out.requests.append(c.bess_release_request("self"))
        st["charging"] = False
        if env.shared.get("bess_by") == "self":
            env.shared["bess_by"] = None
        out.events.append(c.ev("self", "auto_release", "Самоспоживання: заряд BESS завершено"))
    elif st["charging"]:
        out.requests.append(c.bess_request("self", 1, max(bess_kw, 0.0), target_soc))

    # --- обмеження СЕС (п.3) і відпускання (п.4) ----------------------------------------------------
    interval = cfg.engine.min_write_interval_s
    uncovered = export - exp_max - charged
    lim_min = max(cfg.limits.pv_limit_min_pct, limits.PV_LIMIT_MIN_PCT)
    if sc.enabled and bool(p["curtail_pv"]) and uncovered > dead:
        st["curtail_since"] = st["curtail_since"] if st["curtail_since"] is not None else now
        st["restore_since"] = None
        if (
            now - float(st["curtail_since"]) >= float(p["curtail_delay_s"])
            and now - float(st["last_pct_write"]) >= interval
        ):
            new = max(lim_min, limit_now - math.ceil(100.0 * uncovered / max(cfg.plant["pv_kwp"], 1.0)))
            if new < limit_now:
                st.update(limit_pct=new, last_pct_write=now)
                out.events.append(
                    c.ev("self", "auto_step", f"Обмеження СЕС {round(new)} %", signal=cfg.sig("pv_limit"), value=new)
                )
    else:
        st["curtail_since"] = None
        if limit_now < 100 and (not sc.enabled or export < exp_max - dead):
            st["restore_since"] = st["restore_since"] if st["restore_since"] is not None else now
            if now - float(st["restore_since"]) >= (float(p["restore_hold_s"]) if sc.enabled else 0.0) and (
                now - float(st["last_pct_write"]) >= interval
            ):
                new = min(100.0, limit_now + 5.0)
                st.update(limit_pct=new, last_pct_write=now)
                if new >= 100.0:
                    out.events.append(
                        c.ev("self", "auto_release", "Обмеження СЕС знято", signal=cfg.sig("pv_limit"), value=100)
                    )
        else:
            st["restore_since"] = None
    limit_now = float(st["limit_pct"])
    env.shared["pv_limited"] = limit_now < 100
    if limit_now < 100:
        st["curtailed"] = True
        out.requests.append(
            Request(
                "pv",
                [W("shed_valid", limits.SHED_WATCHDOG_S), W("pv_limit", round(limit_now))],
                "self",
                watchdog="shed_valid",
                refresh_s=limits.SHED_REFRESH_S,
            )
        )
        out.facts["limit_pct"] = round(limit_now)
    elif st.get("curtailed"):  # обмеження знято: записати 100 % і обнулити спільний сторожовий таймер
        if c.written(env, "pv_limit", 100):
            st["curtailed"] = False
            env.shared["shed_zero_pending"] = not c.shed_list(env)
        else:
            out.requests.append(Request("pv", [W("pv_limit", 100)], "self"))
    out.state = "active" if st["charging"] or limit_now < 100 else ("armed" if pv >= 1 or sc.enabled else "off")
    return out
