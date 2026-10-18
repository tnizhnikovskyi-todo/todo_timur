"""Сценарій «Нічний режим (BMS)» (R-48, CT-07): вентиляція RoofVent і чергове освітлення за місцевим часом Києва."""

from __future__ import annotations

from typing import Any

from ..model import Env, Output, Request, W
from ..timeutil import in_window, next_window_start, parse_hhmm, window_key
from . import common as c

OVERRIDE_AFTER_S = 60.0  # розбіжність читання назад довше цього, коли рушій ціль не змінював → ручне втручання
EXIT_PENDING_S = 600.0  # скільки хвилин після виходу з вікна повторюємо денні значення, поки не підтвердяться
FADE = "fade=2.0"


def _defaults() -> dict[str, Any]:
    return {"key": None, "was_in": False, "overridden": [], "exit_until": 0.0}


def _targets(env: Env) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return env.cfg.bms_targets("night", "vent"), env.cfg.bms_targets("night", "light")


def desired(
    p: dict[str, Any], vent: list[dict[str, Any]], light: list[dict[str, Any]], *, night: bool
) -> tuple[list[W], list[W]]:
    """Бажані записи: вхід у вікно — `vent_mode`, `heat_setpoint_c`, дежурна сцена; вихід — денні значення."""
    v: list[W] = []
    for u in vent:
        v.append(W(u["mode_signal"], None, p["vent_mode"] if night else p["day_vent_mode"]))
        if night and u.get("sp_night_signal"):
            v.append(W(u["sp_night_signal"], float(p["heat_setpoint_c"])))
    scene = p["light_scene_number"] if night else p["light_scene_day_number"]
    lt = [W(g["scene_signal"], float(scene), FADE) for g in light]
    return v, lt


def _manual_touch(env: Env, writes: list[W], overridden: list[str], since: float) -> list[str]:
    """Цілі, що змінили вручну: читання назад після нашого запису (у поточному вікні) розходиться довше 60 с (п.5)."""
    out = []
    live = env.inp.live
    for w in writes:
        if w.target in overridden or live is None:
            continue
        last, reading = live.last_write(w.target), env.inp.reading(w.target)
        if last is None or reading is None or reading.ts <= last[1]:
            continue
        diff = (
            (reading.text != w.text)
            if w.value is None
            else (reading.value is None or abs(float(reading.value) - float(w.value)) > 0.006)
        )
        written = last[1].timestamp()
        if diff and written >= since and env.epoch - written > OVERRIDE_AFTER_S:
            out.append(w.target)
    return out


def step(env: Env) -> Output:
    cfg, now = env.cfg, env.epoch
    sc, p = cfg.scenario("night"), cfg.params("night")
    st = env.scen.setdefault("night", _defaults())
    for k, v in _defaults().items():
        st.setdefault(k, v)
    out = Output()
    if not sc.enabled:
        out.state = "off"
        return out
    vent, light = _targets(env)
    if not vent and not light:
        out.state, out.facts = "warn", {"reason": "немає цілей BMS"}
        return out
    start, end = parse_hhmm(p["from"]), parse_hhmm(p["to"])
    assert start is not None and end is not None
    days = [int(d) for d in p["days"]]
    in_win = in_window(env.now, start, end, days)
    key = window_key(env.now, start, end)
    if in_win and st["key"] != key:  # нове вікно: скидаємо ознаки ручного втручання
        st.update(key=key, overridden=[], exit_until=0.0, window_since=now)
    if in_win and not st["was_in"]:
        out.events.append(
            c.ev(
                "night",
                "auto_step",
                (
                    f"Нічний режим: вентиляція RoofVent {len(vent)} шт. → {round(float(p['vent_pct']))} %, "
                    "освітлення — черговий сценарій"
                ),
            )
        )
    if not in_win and st["was_in"]:
        st["exit_until"] = now + EXIT_PENDING_S
        out.events.append(c.ev("night", "auto_release", f"Вентиляція · денний режим: RoofVent {len(vent)} шт. → 100 %"))
    st["was_in"] = in_win

    fire_blocked = {"vent", "light"} & env.blocked
    if fire_blocked and (in_win or now < float(st["exit_until"])):
        out.state, out.facts = "warn", {"reason": "пожежна тривога"}
        return out
    out.facts = {"until": p["to"]} if in_win else {"next_run": next_window_start(env.now, start, days)}
    out.state = "active" if in_win else "armed"
    if not in_win and now >= float(st["exit_until"]):
        return out
    v_writes, l_writes = desired(p, vent, light, night=in_win)
    if in_win:
        touched = _manual_touch(env, v_writes + l_writes, st["overridden"], float(st.get("window_since", now)))
        st["overridden"] = sorted(set(st["overridden"]) | set(touched))
        for code in st["overridden"]:
            if c.once(env, f"night:override:{code}:{key}", True):
                out.events.append(
                    c.ev(
                        "night",
                        "override",
                        f"BMS: ручна зміна {code}, нічний режим її не перезаписує",
                        "warn",
                        signal=code,
                    )
                )
    for res, writes in (("vent", v_writes), ("light", l_writes)):
        writes = [w for w in writes if w.target not in st["overridden"]]
        if not writes or env.overridden(res):
            continue
        out.requests.append(Request(res, writes, "night"))
    return out
