"""Сценарій «КГУ за графіком і ціною» (R-50, CT-09)."""

from __future__ import annotations

from typing import Any

from ..model import Env, Output
from ..timeutil import hours_of
from . import common as c
from .slots import active_slots


def grid_price(env: Env) -> float | None:
    """Ціна поточної зони тарифу (місцевий час, R-63)."""
    h = hours_of(env.now)
    for lo, hi, price in env.cfg.tariff:
        if lo <= h < hi:
            return price
    return None


def sync_owner(env: Env) -> None:
    """Власність КГУ скидається, коли вона зупинилася (не раніше 30 с після нашого пуску); фіксуємо час зупинки."""
    chp, state = c.chp_state(env), env.inp.v("chp_state")
    if state is None:
        return
    s = int(state)
    if s in (1, 2):
        chp["running_seen"] = True
    elif s == 0 and chp.get("running_seen"):
        chp["running_seen"] = False
        chp["stopped_at"] = chp.get("stopped_at") or env.epoch
        chp["owner"], chp["started_at"] = None, None
    elif s == 0 and chp.get("owner") and env.epoch - float(chp.get("started_at") or 0.0) > 90.0:
        chp["owner"], chp["started_at"] = None, None  # запуск так і не відбувся


def step(env: Env) -> Output:
    cfg, inp, now = env.cfg, env.inp, env.epoch
    sc, p = cfg.scenario("chp"), cfg.params("chp")
    out = Output()
    state = inp.v("chp_state")
    chp = c.chp_state(env)
    if state is None:
        out.state = "off" if not sc.enabled else "warn"
        out.facts = {"reason": "немає даних: " + ", ".join(inp.code_list(["chp_state"]))} if sc.enabled else {}
        return out
    s = int(state)
    price = grid_price(env)
    cost = float(p["gas_price_uah_m3"]) * float(p["gas_m3_per_kwh"])
    price_ok = price is not None and (price - cost) >= float(p["price_margin_uah_kwh"])
    slot_on = bool(p["use_slots"]) and bool(active_slots(env, "chp"))
    wanted = sc.enabled and (slot_on or price_ok)
    facts: dict[str, Any] = {}
    if s == 3:
        out.state, out.facts = "warn", {"reason": "КГУ в аварії"}
        return out
    if wanted and s == 0 and env.free("chp") and chp.get("owner") in (None, "chp"):
        ok, _why = c.chp_startable(env, min_off_min=float(p["min_off_min"]))
        if ok:
            chp.update(owner="chp", started_at=now)
            out.requests.append(c.chp_start_request("chp"))
            why = "за графіком" if slot_on else f"за ціною ({price:g} ₴ проти {cost:g} ₴)"
            out.events.append(c.ev("chp", "auto_step", f"КГУ: пуск {why}", signal=cfg.sig("chp_cmd"), value=1))
    elif not wanted and s == 2 and chp.get("owner") == "chp":
        run_h = c.chp_run_h(env)
        if run_h is not None and run_h >= float(p["min_run_h"]) and env.free("chp"):
            chp.update(owner=None, stopped_at=now, started_at=None)
            out.requests.append(c.chp_stop_request("chp"))
            out.events.append(
                c.ev("chp", "auto_release", "КГУ: зупинка (немає вигоди)", signal=cfg.sig("chp_cmd"), value=2)
            )
    if s == 2:
        facts["chp_kw"] = round(inp.v("chp_kw") or 0.0)
        out.state = "active"
    elif not sc.enabled:
        out.state = "off"
    else:
        out.state = "armed"
        facts["reason"] = "Очікує вигідної ціни"
    out.facts = facts
    return out
