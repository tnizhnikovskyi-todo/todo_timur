"""Види інтентів: границі `params`, перевірки, кроки виконання, верифікація, fail-safe (R-42 п.3, R-52)."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from collector.core.types import Reading

from . import limits
from .config import Config
from .model import W
from .timeutil import hours_of, parse_hhmm

KINDS = (
    "qs_close",
    "qs_open",
    "bess_charge",
    "bess_discharge",
    "bess_stop",
    "chp_start",
    "chp_stop",
    "light_break",
    "light_restore",
    "vent_eco",
    "vent_restore",
    "air_setpoint",
)
RESOURCE = {
    "qs_close": "qs",
    "qs_open": "qs",
    "bess_charge": "bess",
    "bess_discharge": "bess",
    "bess_stop": "bess",
    "chp_start": "chp",
    "chp_stop": "chp",
    "light_break": "light",
    "light_restore": "light",
    "vent_eco": "vent",
    "vent_restore": "vent",
    "air_setpoint": "air",
}
REMOTE_GATED = ("qs_close", "qs_open", "chp_start", "bess_discharge")  # D-46 (genset_test — не інтент збирача)
# R-41 / SPEC 5.3: перевірки виду; `soft` лише послаблює жорсткість реєстру
KIND_CHECKS: dict[str, tuple[tuple[str, bool], ...]] = {
    "qs_close": (
        ("controller_remote", False),
        ("data_fresh", False),
        ("no_island", False),
        ("ats_parallel_lock", False),
        ("qs_current_ok", False),
    ),
    "qs_open": (("controller_remote", False), ("data_fresh", False)),
    "bess_charge": (
        ("controller_remote", False),
        ("data_fresh", False),
        ("no_island", False),
        ("bess_ok", False),
        ("bess_soc_lt_limit", False),
        ("bess_temp_ok", False),
    ),
    "bess_discharge": (
        ("controller_remote", False),
        ("data_fresh", False),
        ("bess_ok", False),
        ("bess_reserve_kept", False),
        ("bess_temp_ok", False),
    ),
    "bess_stop": (("controller_remote", False),),
    "chp_start": (
        ("controller_remote", False),
        ("data_fresh", False),
        ("no_island", False),
        ("chp_ready", False),
        ("chp_gas_pressure", False),
        ("chp_permit", False),
    ),
    "chp_stop": (("controller_remote", False), ("chp_min_run", False)),
    "light_break": (("controller_remote", False), ("no_fire_alarm", False), ("aisle_lux_ge", True)),
    "light_restore": (("no_fire_alarm", False),),
    "vent_eco": (("controller_remote", False), ("no_fire_alarm", False), ("co2_lt", True)),
    "vent_restore": (("no_fire_alarm", False),),
    "air_setpoint": (("controller_remote", False), ("data_fresh", False), ("air_setpoint_min", False)),
}
# входи, свіжість яких вимагає `data_fresh` (логічні імена; дзеркало kinds.KIND_INPUTS в Odoo)
KIND_INPUTS: dict[str, tuple[str, ...]] = {
    "qs_close": ("remote", "ats_pos", "src1_ok", "ats_lock", "s1_p", "s2_p"),
    "qs_open": ("remote",),
    "bess_charge": ("remote", "ats_pos", "src1_ok", "bess_state", "bess_soc"),
    "bess_discharge": ("remote", "bess_state", "bess_soc"),
    "chp_start": ("remote", "ats_pos", "src1_ok", "chp_state", "chp_gas", "chp_permit"),
    "air_setpoint": ("remote", "air_sp", "air_min"),
}
# перевірки, чиї входи змінюються між прийомом і активуючим кроком (R-52 п.2)
RECHECK = ("bess_ok", "no_island", "ats_parallel_lock", "no_fire_alarm")
VERIFY_S = {"qs": 10.0, "bess": 10.0, "chp": 30.0, "air": 10.0, "light": 15.0, "vent": 15.0}
SOFT_VERIFY_S = 30.0
BMS_SHARE = 0.8  # частка цілей BMS, що мають підтвердитися при читанні назад


class ParamError(ValueError):
    """`bad params: …` — текст помилки без префікса."""


def _num(params: dict[str, Any], key: str, lo: float, hi: float, default: float, *, integer: bool = False) -> float:
    raw = params.get(key, default)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ParamError(f"{key} не число")
    if integer and float(raw) != int(raw):
        raise ParamError(f"{key} не ціле")
    if raw < lo:
        raise ParamError(f"{key} < {lo:g}")
    if raw > hi:
        raise ParamError(f"{key} > {hi:g}")
    return float(raw)


def bess_kw_max(cfg: Config, payload_limits: dict[str, Any] | None) -> float:
    cap = [limits.BESS_KW_MAX, cfg.limits.bess_kw_max, cfg.plant.get("bess_max_kw", limits.BESS_KW_MAX)]
    if payload_limits and isinstance(payload_limits.get("bess_kw_max"), (int, float)):
        cap.append(float(payload_limits["bess_kw_max"]))
    return min(cap)


def validate_params(
    kind: str, params: dict[str, Any], cfg: Config, payload_limits: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Границі `params` вказаного виду (R-42 п.1); невалідне → `ParamError("<ключ> > 200")`."""
    p = params or {}
    if kind == "bess_charge":
        until = p.get("until", "16:00")
        if parse_hhmm(until) is None:
            raise ParamError("until не HH:MM")
        return {
            "power_kw": _num(p, "power_kw", 1, bess_kw_max(cfg, payload_limits), 50),
            "until": until,
            "soc_limit_pct": _num(p, "soc_limit_pct", 50, 100, 95),
        }
    if kind == "bess_discharge":
        return {
            "power_kw": _num(p, "power_kw", 1, bess_kw_max(cfg, payload_limits), 100),
            "duration_min": _num(p, "duration_min", 1, 240, 60, integer=True),
        }
    if kind == "light_break":
        return {
            "level_pct": _num(p, "level_pct", 10, 100, 50, integer=True),
            "duration_min": _num(p, "duration_min", 1, 120, 30, integer=True),
            "scene_number": _num(p, "scene_number", 1, 16, 3, integer=True),
        }
    if kind == "vent_eco":
        return {
            "vent_pct": _num(p, "vent_pct", 30, 100, 70, integer=True),
            "duration_min": _num(p, "duration_min", 1, 480, 120, integer=True),
        }
    if kind == "air_setpoint":
        return {"setpoint_bar": _num(p, "setpoint_bar", cfg.limits.air_bar_min, cfg.limits.air_bar_max, 6.5)}
    return {}


def seconds_until(now: datetime, hhmm: str) -> float:
    """Секунди до `hhmm` сьогодні за Києвом (≤ 0, якщо час уже минув)."""
    target = parse_hhmm(hhmm)
    assert target is not None
    return (target - hours_of(now)) * 3600.0


@dataclass
class Verify:
    reads: list[str]
    ok: Callable[[dict[str, Reading | None]], bool]
    timeout_s: float
    what: str  # «Не підтверджено пристроєм: {що}»
    refuse: Callable[[dict[str, Reading | None]], str | None] = lambda _r: None  # миттєва відмова пристрою
    hard: bool = True


@dataclass
class Step:
    label: str
    writes: list[W]
    activating: bool = False


@dataclass
class Plan:
    kind: str
    resource: str
    steps: list[Step]
    verify: Verify
    summary: str
    soft: Verify | None = None
    failsafe: list[W] = field(default_factory=list)
    override_s: float | None = None  # перекриття ресурсу від успішного виконання
    targets: list[str] = field(default_factory=list)  # BMS: коди цілей


def _v(r: Reading | None) -> float | None:
    return None if r is None or r.value is None else float(r.value)


def _closed(r: Reading | None) -> bool | None:
    if r is None:
        return None
    if r.text is not None:
        return str(r.text).lower() == "closed"
    return None if r.value is None else float(r.value) == 1


def _share_ok(reads: dict[str, Reading | None], codes: list[str], want: Callable[[Reading | None], bool]) -> bool:
    if not codes:
        return True
    return sum(1 for c in codes if want(reads.get(c))) >= math.ceil(BMS_SHARE * len(codes))


def build_plan(kind: str, params: dict[str, Any], cfg: Config, now: datetime, memo: dict[str, Any]) -> Plan:
    """План виконання виду (кроки — рівневі, повтор безпечний; R-42 п.3). `memo` — запам'ятований стан BMS/повітря."""
    res = RESOURCE[kind]
    t = VERIFY_S[res]
    if kind in ("qs_close", "qs_open"):
        closing = kind == "qs_close"
        want = 2 if closing else 1
        return Plan(
            kind,
            res,
            [Step(f"qs_cmd = {want}", [W("qs_cmd", want)], activating=True)],
            Verify(
                ["qs_state", "qs_ack"],
                lambda r: _closed(r.get("qs_state")) is closing,
                t,
                "QS не змінив положення",
                refuse=lambda r: "Контролер відмовив: блокування" if _v(r.get("qs_ack")) == 2 else None,
            ),
            "QS замкнено" if closing else "QS розімкнено",
        )
    if kind == "bess_charge":
        valid = seconds_until(now, params["until"])
        if valid <= 0:
            raise ParamError("Час «до» має бути пізніше за поточний")
        valid_s = int(min(valid, limits.MAX_BESS_VALID_S))
        pw = float(params["power_kw"])
        steps = [
            Step("bess_sp", [W("bess_sp", pw)]),
            Step("bess_until", [W("bess_until", float(params["soc_limit_pct"]))]),
            Step("bess_valid", [W("bess_valid", valid_s)]),
            Step("bess_mode = 1", [W("bess_mode", 1)], True),
        ]
        return Plan(
            kind,
            res,
            steps,
            Verify(
                ["bess_mode", "bess_ack"],
                lambda r: _v(r.get("bess_mode")) == 1 and _v(r.get("bess_ack")) == 0,
                t,
                "режим BESS",
                refuse=lambda r: "Контролер відмовив: BESS" if _v(r.get("bess_ack")) == 2 else None,
            ),
            f"BESS: заряд {pw:g} кВт до {params['until']} (valid_s {valid_s})",
            soft=Verify(
                ["bess_kw"],
                lambda r: (_v(r.get("bess_kw")) or 0.0) >= 0.5 * pw,
                SOFT_VERIFY_S,
                f"потужність заряду < {0.5 * pw:g} кВт",
                hard=False,
            ),
            failsafe=[W("bess_mode", 0), W("bess_valid", 0)],
            override_s=float(valid_s),
        )
    if kind == "bess_discharge":
        floor = max(float(cfg.plant["bess_reserve_pct"]), limits.SOC_FLOOR_PCT)
        pw, dur = float(params["power_kw"]), float(params["duration_min"])
        steps = [
            Step("bess_sp", [W("bess_sp", pw)]),
            Step("bess_until", [W("bess_until", floor)]),
            Step("bess_valid", [W("bess_valid", int(dur * 60))]),
            Step("bess_mode = 2", [W("bess_mode", 2)], True),
        ]
        return Plan(
            kind,
            res,
            steps,
            Verify(
                ["bess_mode", "bess_ack"],
                lambda r: _v(r.get("bess_mode")) == 2 and _v(r.get("bess_ack")) == 0,
                t,
                "режим BESS",
                refuse=lambda r: "Контролер відмовив: BESS" if _v(r.get("bess_ack")) == 2 else None,
            ),
            f"BESS: розряд {pw:g} кВт на {dur:g} хв",
            soft=Verify(
                ["bess_kw"],
                lambda r: (_v(r.get("bess_kw")) or 0.0) <= -0.5 * pw,
                SOFT_VERIFY_S,
                f"потужність розряду < {0.5 * pw:g} кВт",
                hard=False,
            ),
            failsafe=[W("bess_mode", 0)],
            override_s=dur * 60.0,
        )
    if kind == "bess_stop":
        return Plan(
            kind,
            res,
            [Step("bess_mode = 0", [W("bess_mode", 0)]), Step("bess_valid = 0", [W("bess_valid", 0)])],
            Verify(["bess_mode"], lambda r: _v(r.get("bess_mode")) == 0, t, "режим BESS"),
            "BESS: автоматичний режим",
        )
    if kind == "chp_start":
        return Plan(
            kind,
            res,
            [Step("chp_cmd = 1", [W("chp_cmd", 1)], True)],
            Verify(
                ["chp_state", "chp_ack"],
                lambda r: _v(r.get("chp_state")) in (1.0, 2.0) and _v(r.get("chp_ack")) != 2,
                t,
                "КГУ не запустилась",
                refuse=lambda r: "Контролер відмовив: КГУ" if _v(r.get("chp_ack")) == 2 else None,
            ),
            "КГУ: пуск",
        )
    if kind == "chp_stop":
        return Plan(
            kind,
            res,
            [Step("chp_cmd = 2", [W("chp_cmd", 2)])],
            Verify(
                ["chp_state"],
                lambda r: _v(r.get("chp_state")) != 2.0 and r.get("chp_state") is not None,
                t,
                "КГУ не зупиняється",
            ),
            "КГУ: зупинка",
        )
    if kind == "air_setpoint":
        sp = float(params["setpoint_bar"])
        prior = memo.get("air_sp")
        return Plan(
            kind,
            res,
            [Step("air_sp", [W("air_sp", sp)], True)],
            Verify(
                ["air_sp"],
                lambda r: _v(r.get("air_sp")) is not None and abs(_v(r.get("air_sp")) - sp) <= 0.006,
                t,  # type: ignore[operator]
                "уставка тиску",
            ),
            f"Уставка тиску {sp:g} бар",
            failsafe=[W("air_sp", float(prior))] if prior is not None else [],
        )
    return _bms_plan(kind, params, cfg, memo)


def _bms_plan(kind: str, params: dict[str, Any], cfg: Config, memo: dict[str, Any]) -> Plan:
    res = RESOURCE[kind]
    night = cfg.params("night")
    t = VERIFY_S[res]
    if res == "light":
        targets = cfg.bms_targets("light_break", "light")
        codes = [g["scene_signal"] for g in targets if not g.get("aisle")]
        if kind == "light_break":
            scene = float(params["scene_number"])
            writes = {c: scene for c in codes}
            summary, override = f"Освітлення: сцена «Перерва» ({len(codes)} груп)", float(params["duration_min"]) * 60.0
        else:
            day = float(night["light_scene_day_number"])
            writes = {c: float((memo.get("light") or {}).get(c, day)) for c in codes}
            summary, override = f"Освітлення: режим повернено ({len(codes)} груп)", None
        steps = [Step(f"scene {c}", [W(c, v, "fade=2.0")], i == 0) for i, (c, v) in enumerate(writes.items())]
        verify = Verify(
            codes,
            lambda r: _share_ok(
                r,
                codes,
                lambda x: x is not None and x.value is not None and abs(float(x.value) - writes[x.code]) <= 0.006,
            ),
            t,
            "сцени освітлення",
        )
        failsafe = (
            [W(c, float((memo.get("light") or {}).get(c, night["light_scene_day_number"])), "fade=2.0") for c in codes]
            if kind == "light_break"
            else []
        )
        return Plan(kind, res, steps, verify, summary, failsafe=failsafe, override_s=override, targets=codes)
    kind_group = "vent_eco"
    codes = [u["mode_signal"] for u in cfg.bms_targets(kind_group, "vent")]
    eco = str(night["vent_mode"])
    day = str(night["day_vent_mode"])
    modes = {c: (eco if kind == "vent_eco" else str((memo.get("vent") or {}).get(c, day))) for c in codes}
    steps = [Step(f"mode {c}", [W(c, None, m)], i == 0) for i, (c, m) in enumerate(modes.items())]
    verify = Verify(
        codes,
        lambda r: _share_ok(r, codes, lambda x: x is not None and x.text == modes[x.code]),
        t,
        "режими вентиляції",
    )
    failsafe = [W(c, None, str((memo.get("vent") or {}).get(c, day))) for c in codes] if kind == "vent_eco" else []
    summary = (
        f"Вентиляція: економ-режим {params['vent_pct']} % ({len(codes)} установок)"
        if kind == "vent_eco"
        else f"Вентиляція: режим повернено ({len(codes)} установок)"
    )
    override = float(params["duration_min"]) * 60.0 if kind == "vent_eco" else None
    return Plan(kind, res, steps, verify, summary, failsafe=failsafe, override_s=override, targets=codes)
