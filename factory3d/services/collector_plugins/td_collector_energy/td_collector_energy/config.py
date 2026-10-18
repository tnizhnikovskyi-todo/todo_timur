"""Конфіг API-24 (C-39): перевірка схеми, типізація, значення за замовчуванням, межі коду (R-41 п.6, R-44 п.6).

`parse(raw)` не кидає винятків: повертає `Parsed(config, errors, warnings, events)`. Невалідний конфіг (`errors`) плагін
не застосовує — лишається попередній валідний (AC-239). Необов'язкові ключі отримують значення коду (AC-240):
невідомі ключі `params` сценаріїв дають попередження, слоти з `from ≥ to` й елементи `shed[]` без сигналу відкидаються.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import date
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from . import limits
from .timeutil import parse_hhmm

SCENARIO_CODES = ("peak", "self", "pfc", "night", "backup", "chp")

PARAM_DEFAULTS: dict[str, dict[str, Any]] = {
    "peak": {
        "limit_kw": 760.0,
        "activate_margin_kw": 30.0,
        "margin_kw": 20.0,
        "release_margin_kw": 40.0,
        "release_hold_s": 180.0,
        "stage_delay_s": 60.0,
        "bess_max_kw": 100.0,
        "bess_min_soc_pct": 30.0,
        "chp_allowed": True,
        "shed_allowed": True,
    },
    "self": {
        "export_max_kw": 20.0,
        "export_deadband_kw": 5.0,
        "bess_target_soc_pct": 95.0,
        "bess_max_kw": 100.0,
        "curtail_pv": True,
        "curtail_delay_s": 60.0,
        "restore_hold_s": 120.0,
    },
    "pfc": {"cos_target": 0.95},
    "night": {
        "from": "23:00",
        "to": "06:30",
        "days": [1, 2, 3, 4, 5, 6, 7],
        "vent_mode": "VEL",
        "day_vent_mode": "VE",
        "vent_pct": 30.0,
        "light_scene_number": 1,
        "light_scene_day_number": 2,
        "heat_setpoint_c": 16.0,
    },
    "backup": {"genset_capacity_kw": 507.0, "critical_kw": 180.0, "restore_delay_s": 120.0},
    "chp": {
        "min_run_h": 2.0,
        "min_off_min": 30.0,
        "gas_price_uah_m3": 19.80,
        "gas_m3_per_kwh": 0.25,
        "price_margin_uah_kwh": 0.5,
        "use_slots": True,
        "ramp_min": 6.0,
    },
}
PLANT_DEFAULTS = {
    "contract_kw": 800.0,
    "pv_kwp": 920.0,
    "bess_kwh": 387.0,
    "bess_max_kw": 200.0,
    "bess_reserve_pct": 30.0,
    "cos_phi_target": 0.95,
    "genset_kw": 507.0,
    "chp_kw": 800.0,
    "qs_rating_a": 1600.0,
}
# R-41 / SPEC 5.4: (hard, fail_closed, params) для перевірок `where ∈ {both, collector}`; конфіг лише уточнює
DEFAULT_INTERLOCKS: dict[str, tuple[bool, bool, dict[str, Any]]] = {
    "controller_remote": (True, True, {}),
    "data_fresh": (True, True, {"max_age_s": 60}),
    "no_island": (True, True, {}),
    "ats_parallel_lock": (True, True, {}),
    "qs_current_ok": (True, True, {"rating_a": 1600, "max_ratio": 0.8, "cos_phi": 0.95}),
    "bess_ok": (True, True, {}),
    "bess_soc_lt_limit": (True, True, {}),
    "bess_reserve_kept": (True, True, {"capacity_kwh": 387}),
    "bess_temp_ok": (True, False, {"max_c": 40}),
    "chp_ready": (True, True, {}),
    "chp_gas_pressure": (True, True, {"min_bar": 1.5}),
    "chp_permit": (True, True, {}),
    "chp_min_run": (True, False, {"min_run_h": 2}),
    "no_fire_alarm": (True, False, {}),
    "aisle_lux_ge": (False, False, {"min_lux": 75}),
    "co2_lt": (False, False, {"max_ppm": 1000}),
    "air_setpoint_min": (True, True, {"margin_bar": 0.2, "max_bar": 8.5}),
}
_SCHEMA = json.loads(
    resources.files("td_collector_energy").joinpath("schemas", "config.schema.json").read_text("utf-8")
)
_VALIDATOR = Draft202012Validator(_SCHEMA)


@dataclass(frozen=True)
class EngineCfg:
    tick_s: float = 2.0
    config_poll_s: float = 10.0
    stale_hold_s: float = 30.0
    min_write_interval_s: float = 10.0
    max_writes_per_min: int = 30
    exec_timeout_s: float = 60.0
    step_timeout_s: float = 8.0
    verify_timeout_s: float = 30.0
    shed_restore_step_s: float = 20.0


@dataclass(frozen=True)
class ShedItem:
    id: int
    seq: int
    node: str
    action: str
    param: float
    kw: float
    critical: bool
    signal: str
    condition: str = "none"
    condition_value: float | None = None


@dataclass(frozen=True)
class Slot:
    id: int
    resource: str
    date: date | None
    weekdays: str
    start: float
    end: float
    mode: str | None
    setpoint_kw: float | None


@dataclass(frozen=True)
class InterlockCfg:
    hard: bool
    fail_closed: bool
    params: dict[str, Any]


@dataclass(frozen=True)
class ScenarioCfg:
    enabled: bool
    params: dict[str, Any]


@dataclass(frozen=True)
class Limits:
    bess_kw_max: float = limits.BESS_KW_MAX
    pv_limit_min_pct: float = limits.PV_LIMIT_MIN_PCT
    air_bar_min: float = limits.AIR_BAR_MIN
    air_bar_max: float = limits.AIR_BAR_MAX


@dataclass(frozen=True)
class Config:
    version: int = 0
    etag: str = ""
    server_time: str = ""
    tz: str = "Europe/Kyiv"
    automation_enabled: bool = False
    write_enabled: bool = False
    remote_switching_enabled: bool = False
    engine: EngineCfg = field(default_factory=EngineCfg)
    plant: dict[str, float] = field(default_factory=lambda: dict(PLANT_DEFAULTS))
    scenarios: dict[str, ScenarioCfg] = field(default_factory=dict)
    shed: tuple[ShedItem, ...] = ()
    never_shed: frozenset[str] = frozenset(limits.NEVER_SHED_CODES)
    slots: tuple[Slot, ...] = ()
    tariff: tuple[tuple[float, float, float], ...] = ()
    bms: dict[str, Any] = field(default_factory=dict)
    signals: dict[str, str] = field(default_factory=dict)
    inputs: dict[str, str] = field(default_factory=dict)
    interlocks: dict[str, InterlockCfg] = field(default_factory=dict)
    limits: Limits = field(default_factory=Limits)
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    # --- доступ до логічних імен -------------------------------------------------------------
    def sig(self, name: str) -> str | None:
        """Код сигналу за логічним ім'ям (`signals`) або сам код, якщо передано шлях із «/»."""
        return self.signals.get(name) or (name if "/" in name else None)

    def inp(self, name: str) -> str | None:
        return self.inputs.get(name) or self.signals.get(name)

    def scenario(self, code: str) -> ScenarioCfg:
        return self.scenarios.get(code) or ScenarioCfg(False, copy.deepcopy(PARAM_DEFAULTS.get(code, {})))

    def params(self, code: str) -> dict[str, Any]:
        return self.scenario(code).params

    def interlock(self, code: str) -> InterlockCfg:
        got = self.interlocks.get(code)
        if got is not None:
            return got
        hard, closed, params = DEFAULT_INTERLOCKS.get(code, (False, False, {}))
        return InterlockCfg(hard, closed, dict(params))

    def writable_codes(self) -> frozenset[str]:
        """Єдині коди, у які збирач має право писати (R-60 п.2 б): `signals`, `shed[].signal`, `bms.*`."""
        codes = set(self.signals.values()) | {s.signal for s in self.shed}
        for group in self.bms.values():
            for items in (group or {}).values():
                for item in items or []:
                    codes.update(v for k, v in item.items() if k.endswith("_signal") and isinstance(v, str))
        return frozenset(codes)

    def bms_targets(self, group: str, kind: str) -> list[dict[str, Any]]:
        return list(((self.bms.get(group) or {}).get(kind)) or [])


@dataclass
class Parsed:
    config: Config | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)  # тексти подій `config` (межі коду тощо)


def _num(v: Any, default: float) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else default


def _clamp(parsed: Parsed, key: str, value: float, lo: float | None = None, hi: float | None = None) -> float:
    out = value
    if hi is not None and out > hi:
        out = hi
    if lo is not None and out < lo:
        out = lo
    if out != value:
        parsed.events.append(f"значення {key} обмежено: {value:g} → {out:g}")
    return out


def _params(parsed: Parsed, code: str, given: dict[str, Any]) -> dict[str, Any]:
    defaults = PARAM_DEFAULTS[code]
    out = copy.deepcopy(defaults)
    for key, val in given.items():
        if key not in defaults:
            parsed.warnings.append(f"сценарій {code}: невідомий параметр {key}")
            continue
        want = defaults[key]
        if isinstance(want, bool):
            ok = isinstance(val, bool)
        elif isinstance(want, (int, float)):
            ok = isinstance(val, (int, float)) and not isinstance(val, bool)
        elif isinstance(want, list):
            ok = isinstance(val, list) and bool(val) and all(isinstance(d, int) and 1 <= d <= 7 for d in val)
        else:
            ok = isinstance(val, str)
        if key in ("from", "to") and ok and parse_hhmm(val) is None:
            ok = False
        if ok:
            out[key] = val
        else:
            parsed.warnings.append(f"сценарій {code}: параметр {key} некоректний, взято {want!r}")
    return out


def _shed(parsed: Parsed, raw: list[dict[str, Any]]) -> tuple[ShedItem, ...]:
    items = []
    for i, it in enumerate(sorted(raw, key=lambda x: x.get("seq", 0))):
        if not it.get("signal"):
            parsed.warnings.append(f"shed[{it.get('node')}]: немає сигналу обмеження — пропущено")
            continue
        items.append(
            ShedItem(
                id=int(it.get("id", i)),
                seq=int(it.get("seq", i + 1)),
                node=it["node"],
                action=it.get("action", "off"),
                param=_num(it.get("param"), 0.0),
                kw=_num(it.get("kw"), 0.0),
                critical=bool(it.get("critical")),
                signal=it["signal"],
                condition=it.get("condition", "none"),
                condition_value=it.get("condition_value"),
            )
        )
    return tuple(items)


def _slots(parsed: Parsed, raw: list[dict[str, Any]]) -> tuple[Slot, ...]:
    out = []
    for it in raw:
        start, end = float(it["from"]), float(it["to"])
        if not 0 <= start < end <= 24:
            parsed.warnings.append(f"слот {it.get('id')}: from ≥ to — відкинуто")
            continue
        try:
            day = date.fromisoformat(it["date"]) if it.get("date") else None
        except ValueError:
            parsed.warnings.append(f"слот {it.get('id')}: некоректна дата — відкинуто")
            continue
        out.append(
            Slot(
                int(it.get("id", 0)),
                str(it["resource"]),
                day,
                it.get("weekdays") or "1111111",
                start,
                end,
                it.get("mode"),
                it.get("setpoint_kw"),
            )
        )
    return tuple(out)


def _interlocks(parsed: Parsed, raw: dict[str, Any]) -> dict[str, InterlockCfg]:
    out: dict[str, InterlockCfg] = {}
    for code, (hard, closed, params) in DEFAULT_INTERLOCKS.items():
        item = raw.get(code) or {}
        merged = {**params, **(item.get("params") or {})}
        for (c, key), hi in limits.INTERLOCK_MAX.items():
            if c == code and key in merged:
                merged[key] = _clamp(parsed, f"{code}.{key}", _num(merged[key], hi), hi=hi)
        for (c, key), lo in limits.INTERLOCK_MIN.items():
            if c == code and key in merged:
                merged[key] = _clamp(parsed, f"{code}.{key}", _num(merged[key], lo), lo=lo)
        out[code] = InterlockCfg(bool(item.get("hard", hard)), bool(item.get("fail_closed", closed)), merged)
    for code in raw:
        if code not in out:
            parsed.warnings.append(f"interlocks.{code}: невідома перевірка")
    return out


def _engine(parsed: Parsed, raw: dict[str, Any]) -> EngineCfg:
    d = EngineCfg()
    e = {k: _num(raw.get(k), getattr(d, k)) for k in EngineCfg.__dataclass_fields__}
    e["tick_s"] = _clamp(parsed, "engine.tick_s", e["tick_s"], limits.TICK_S_MIN, limits.TICK_S_MAX)
    e["config_poll_s"] = _clamp(
        parsed, "engine.config_poll_s", e["config_poll_s"], limits.CONFIG_POLL_S_MIN, limits.CONFIG_POLL_S_MAX
    )
    e["min_write_interval_s"] = _clamp(
        parsed, "engine.min_write_interval_s", e["min_write_interval_s"], limits.MIN_WRITE_INTERVAL_S
    )
    e["max_writes_per_min"] = int(
        _clamp(parsed, "engine.max_writes_per_min", e["max_writes_per_min"], 1, limits.MAX_WRITES_PER_MIN)
    )
    return EngineCfg(**e)


def _limits(parsed: Parsed, raw: dict[str, Any]) -> Limits:
    return Limits(
        bess_kw_max=_clamp(
            parsed, "limits.bess_kw_max", _num(raw.get("bess_kw_max"), limits.BESS_KW_MAX), hi=limits.BESS_KW_MAX
        ),
        pv_limit_min_pct=_clamp(
            parsed,
            "limits.pv_limit_min_pct",
            _num(raw.get("pv_limit_min_pct"), limits.PV_LIMIT_MIN_PCT),
            lo=limits.PV_LIMIT_MIN_PCT,
        ),
        air_bar_min=_clamp(
            parsed, "limits.air_bar_min", _num(raw.get("air_bar_min"), limits.AIR_BAR_MIN), lo=limits.AIR_BAR_MIN
        ),
        air_bar_max=_clamp(
            parsed, "limits.air_bar_max", _num(raw.get("air_bar_max"), limits.AIR_BAR_MAX), hi=limits.AIR_BAR_MAX
        ),
    )


def _scenarios(parsed: Parsed, raw: dict[str, Any], plant: dict[str, float], lim: Limits) -> dict[str, ScenarioCfg]:
    out = {}
    for code in SCENARIO_CODES:
        item = raw.get(code) or {}
        params = _params(parsed, code, item.get("params") or {})
        if code == "pfc":
            params["cos_target"] = _num((item.get("params") or {}).get("cos_target"), plant["cos_phi_target"])
        if code in ("peak", "self"):
            params["bess_max_kw"] = _clamp(parsed, f"{code}.bess_max_kw", params["bess_max_kw"], hi=lim.bess_kw_max)
        if code == "peak":
            params["bess_min_soc_pct"] = _clamp(
                parsed, "peak.bess_min_soc_pct", params["bess_min_soc_pct"], lo=limits.SOC_FLOOR_PCT
            )
        out[code] = ScenarioCfg(bool(item.get("enabled", False)), params)
    for code in raw:
        if code not in SCENARIO_CODES:
            parsed.warnings.append(f"сценарій {code}: невідомий — пропущено")
    return out


def parse(raw: Any) -> Parsed:
    """Конфіг API-24 → `Config` (або `errors`, якщо схема порушена)."""
    parsed = Parsed(None)
    if not isinstance(raw, dict):
        parsed.errors.append("конфіг не є об'єктом")
        return parsed
    parsed.errors = [f"{'/'.join(str(p) for p in e.path) or '$'}: {e.message}" for e in _VALIDATOR.iter_errors(raw)]
    if parsed.errors:
        return parsed
    lim = _limits(parsed, raw.get("limits") or {})
    plant = {k: _num((raw.get("plant") or {}).get(k), v) for k, v in PLANT_DEFAULTS.items()}
    plant["bess_max_kw"] = min(plant["bess_max_kw"], lim.bess_kw_max)
    plant["bess_reserve_pct"] = _clamp(
        parsed, "plant.bess_reserve_pct", plant["bess_reserve_pct"], lo=limits.SOC_FLOOR_PCT
    )
    flags = raw.get("flags") or {}
    zones = (raw.get("tariff") or {}).get("zones", [])
    parsed.config = Config(
        version=int(raw["config_version"]),
        etag=str(raw.get("etag", "")),
        server_time=str(raw.get("server_time", "")),
        tz=str(raw.get("tz", "Europe/Kyiv")),
        automation_enabled=bool(flags.get("automation_enabled", False)),
        write_enabled=bool(flags.get("write_enabled", False)),
        remote_switching_enabled=bool(flags.get("remote_switching_enabled", False)),
        engine=_engine(parsed, raw.get("engine") or {}),
        plant=plant,
        scenarios=_scenarios(parsed, raw.get("scenarios") or {}, plant, lim),
        shed=_shed(parsed, raw.get("shed") or []),
        never_shed=frozenset(raw.get("never_shed") or ()) | frozenset(limits.NEVER_SHED_CODES),
        slots=_slots(parsed, raw.get("slots") or []),
        tariff=tuple((float(z["from"]), float(z["to"]), float(z["price"])) for z in zones),
        bms=copy.deepcopy(raw.get("bms") or {}),
        signals=dict(raw.get("signals") or {}),
        inputs=dict(raw.get("inputs") or {}),
        interlocks=_interlocks(parsed, raw.get("interlocks") or {}),
        limits=lim,
        raw=raw,
    )
    return parsed
