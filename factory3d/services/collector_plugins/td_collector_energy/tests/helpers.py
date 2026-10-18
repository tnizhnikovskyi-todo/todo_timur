"""Спільні помічники тестів плагіна: годинник, конфіг, живі показання, фейковий пристрій і Odoo."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from collector.core.errors import WriteError, WriteRefused
from collector.core.live import LiveCache
from collector.core.odoo_client import OdooError
from collector.core.types import Reading, SignalCfg, SourceCfg
from collector.plugins.base import PluginContext

from td_collector_energy import config as cfgmod
from td_collector_energy.interlocks import Ctx
from td_collector_energy.model import Env, Output

CONTRACTS = Path(__file__).resolve().parents[4] / "odoo_addons" / "td_energy_control" / "contracts"
T0 = datetime(2026, 10, 14, 6, 0, 0, tzinfo=UTC)  # 09:00 Київ (EEST, UTC+3)


class FakeClock:
    """Віртуальний годинник: sleep() просуває час і віддає керування циклу."""

    def __init__(self, start: datetime = T0) -> None:
        self._now, self._mono = start, 1000.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    def advance(self, s: float) -> None:
        self._now += timedelta(seconds=s)
        self._mono += s

    async def sleep(self, s: float) -> None:
        self.advance(s)
        await asyncio.sleep(0)


def contract(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text("utf-8"))


SHED = [
    {
        "id": 1,
        "seq": 1,
        "node": "CHARGING",
        "action": "defer",
        "param": 30,
        "kw": 48,
        "critical": False,
        "signal": "energy_control/shed/CHARGING/limit_pct",
        "condition": "none",
        "condition_value": None,
    },
    {
        "id": 2,
        "seq": 2,
        "node": "RV-ALL",
        "action": "reduce",
        "param": 70,
        "kw": 60,
        "critical": False,
        "signal": "energy_control/shed/RV-ALL/limit_pct",
        "condition": "none",
        "condition_value": None,
    },
    {
        "id": 3,
        "seq": 3,
        "node": "DRY-1",
        "action": "pause",
        "param": 20,
        "kw": 17,
        "critical": False,
        "signal": "energy_control/shed/DRY-1/limit_pct",
        "condition": "no_active_cycle",
        "condition_value": None,
    },
    {
        "id": 4,
        "seq": 4,
        "node": "COMPRESSOR",
        "action": "off",
        "param": 0,
        "kw": 37,
        "critical": True,
        "signal": "energy_control/shed/COMPRESSOR/limit_pct",
        "condition": "air_pressure_min",
        "condition_value": 6.5,
    },
    {
        "id": 5,
        "seq": 5,
        "node": "LP-1",
        "action": "reduce",
        "param": 50,
        "kw": 12,
        "critical": True,
        "signal": "energy_control/shed/LP-1/limit_pct",
        "condition": "none",
        "condition_value": None,
    },
]
BMS = {
    "night": {
        "vent": [
            {
                "unit": "RV-01",
                "mode_signal": "ventilation/units/RV-01/mode",
                "sp_night_signal": "ventilation/units/RV-01/setpoint_night_c",
            },
            {"unit": "RV-02", "mode_signal": "ventilation/units/RV-02/mode"},
        ],
        "light": [
            {"group": "LT-01", "scene_signal": "lighting/groups/LT-01/scene", "aisle": False},
            {"group": "LT-02", "scene_signal": "lighting/groups/LT-02/scene", "aisle": False},
            {"group": "LT-A1", "scene_signal": "lighting/groups/LT-A1/scene", "aisle": True},
        ],
    },
    "vent_eco": {
        "vent": [
            {"unit": "RV-01", "mode_signal": "ventilation/units/RV-01/mode"},
            {"unit": "RV-02", "mode_signal": "ventilation/units/RV-02/mode"},
        ]
    },
    "light_break": {
        "light": [
            {"group": "LT-01", "scene_signal": "lighting/groups/LT-01/scene", "aisle": False},
            {"group": "LT-02", "scene_signal": "lighting/groups/LT-02/scene", "aisle": False},
        ]
    },
}


def base_raw(**over: Any) -> dict[str, Any]:
    """Конфіг API-24 за еталоном C-39 (`contracts/api24_config.json`) + 5 пріоритетів скидання й цілі BMS."""
    raw = copy.deepcopy(contract("api24_config.json"))
    raw["server_time"] = "2026-10-14T06:00:00Z"  # годинник Odoo = FakeClock (без поправки на розбіжність)
    raw["flags"] = {"automation_enabled": True, "write_enabled": True, "remote_switching_enabled": True}
    raw["scenarios"]["peak"] = {"enabled": True, "params": {"limit_kw": 760}}
    raw["scenarios"]["self"] = {"enabled": True, "params": {}}
    raw["scenarios"]["chp"] = {"enabled": True, "params": {}}
    raw["shed"] = copy.deepcopy(SHED)
    raw["slots"] = []
    raw["bms"] = copy.deepcopy(BMS)
    raw["interlocks"] = {}
    for key, val in over.items():
        if key in ("peak", "self", "pfc", "night", "backup", "chp"):
            raw["scenarios"][key].update(val)
        else:
            raw[key] = val
    return raw


def base_cfg(**over: Any) -> cfgmod.Config:
    parsed = cfgmod.parse(base_raw(**over))
    assert not parsed.errors, parsed.errors
    assert parsed.config is not None
    return parsed.config


def set_params(raw: dict[str, Any], scenario: str, **params: Any) -> dict[str, Any]:
    raw["scenarios"][scenario]["params"].update(params)
    return raw


def live_with(cfg: cfgmod.Config, now: datetime, **values: Any) -> LiveCache:
    """`values` — логічні імена входів/сигналів: число, `"текст"` або `(число, "текст")`; `None` — немає показань."""
    live = LiveCache(SimpleNamespace(now=lambda: now))  # type: ignore[arg-type]
    put(live, cfg, now, **values)
    return live


def put(live: LiveCache, cfg: cfgmod.Config, now: datetime, **values: Any) -> None:
    for name, val in values.items():
        code = cfg.inp(name) or name
        if val is None:
            continue
        v, t = val if isinstance(val, tuple) else (None, val) if isinstance(val, str) else (val, None)
        live.update([Reading(code, now, value=v, text=t)])


def make_env(
    cfg: cfgmod.Config | None = None,
    now: datetime = T0,
    *,
    shared: dict | None = None,
    scen: dict | None = None,
    overrides: dict | None = None,
    blocked: set | None = None,
    **values: Any,
) -> Env:
    from td_collector_energy.inputs import Inputs

    cfg = cfg or base_cfg()
    live = live_with(cfg, now, **values)
    return Env(
        Inputs(cfg, live, now),
        cfg,
        now,
        shared if shared is not None else {},
        scen if scen is not None else {},
        overrides or {},
        blocked or set(),
    )


def advance(env: Env, seconds: float, **values: Any) -> Env:
    """Новий `Env` через `seconds` (стан сценаріїв/спільний стан зберігається, живі значення оновлюються)."""
    from td_collector_energy.inputs import Inputs

    now = env.now + timedelta(seconds=seconds)
    live = env.inp.live
    put(live, env.cfg, now, **values)
    for code in list(live._last):  # решту показань «освіжаємо», щоб вони не старіли
        r = live._last[code]
        live._last[code] = Reading(code, now, r.value, r.text, r.q)
    for name, val in values.items():
        if val is None:
            live._last.pop(env.cfg.inp(name) or name, None)
    return Env(Inputs(env.cfg, live, now), env.cfg, now, env.shared, env.scen, env.overrides, env.blocked)


def interlock_ctx(values: dict | None = None, texts: dict | None = None, absent: tuple = ()) -> Ctx:
    return Ctx(values, texts, absent)


def reqs(out: Output, resource: str) -> list:
    return [r for r in out.requests if r.resource == resource]


def writes_of(out: Output, resource: str) -> dict[str, Any]:
    """{логічне ім'я: значення|текст} першого запиту ресурсу (для стислих перевірок)."""
    rs = reqs(out, resource)
    if not rs:
        return {}
    return {w.target: (w.value if w.value is not None else w.text) for w in rs[0].writes}


def kinds(out: Output, kind: str) -> list:
    return [e for e in out.events if e.kind == kind]


# --- фейкові пристрій, Odoo, контекст плагіна -------------------------------------------------------------
class FakeDevice:
    """Регістри «пристроїв»: `write_signal`/`read_signal` ядра. `hooks[code](value, text)` емулює реакцію пристрою."""

    def __init__(self, cfg_getter: Any, live: LiveCache, clock: FakeClock) -> None:
        self.cfg_getter, self.live, self.clock = cfg_getter, live, clock
        self.regs: dict[str, Any] = {}
        self.writes: list[tuple[str, float | None, str | None]] = []
        self.hooks: dict[str, Any] = {}
        self.fail: dict[str, int] = {}  # код → скільки найближчих записів провалити
        self.reads = 0

    def _code(self, name: str) -> str:
        cfg = self.cfg_getter()
        return (cfg.inp(name) if cfg else None) or name

    def set(self, name: str, value: Any = None, text: str | None = None) -> None:
        self.regs[self._code(name)] = (value, text)
        self.sync()

    def sync(self) -> None:
        now = self.clock.now()
        for code, (v, t) in self.regs.items():
            self.live.update([Reading(code, now, value=v, text=t)])

    async def write(self, code: str, value: float | None = None, text: str | None = None, **kw: Any) -> str:
        if self.fail.get(code, 0) > 0:
            self.fail[code] -= 1
            raise WriteError("пристрій не відповідає")
        self.writes.append((code, value, text))
        self.regs[code] = (value, text if value is None else self.regs.get(code, (None, None))[1])
        hook = self.hooks.get(code)
        if hook is not None:
            hook(value, text)
        self.sync()
        return "ok"

    async def read(self, code: str) -> Reading | None:
        self.reads += 1
        item = self.regs.get(code)
        if item is None:
            return None
        r = Reading(code, self.clock.now(), value=item[0], text=item[1])
        self.live.update([r])
        return r

    def last(self, code: str) -> Any:
        for c, v, t in reversed(self.writes):
            if c == code:
                return v if v is not None else t
        return None


class FakeOdoo:
    """`automation_config` / `automation_state` (API-24/25) із керованими відповідями."""

    def __init__(self, raw: dict[str, Any] | None = None) -> None:
        self.raw = raw
        self.version: int | None = None
        self.down = False
        self.status: int | None = None
        self.retry_after: float | None = None
        self.config_calls: list[str | None] = []
        self.states: list[dict[str, Any]] = []
        self.state_response: dict[str, Any] = {"accepted_actions": 0, "accepted_events": 0, "rejected": []}

    async def automation_config(self, etag: str | None = None):
        self.config_calls.append(etag)
        if self.down:
            raise OdooError(self.status, "down", self.retry_after)
        assert self.raw is not None
        if etag and etag == self.raw.get("etag"):
            return None, self.version or self.raw["config_version"]
        return copy.deepcopy(self.raw), self.version or self.raw["config_version"]

    async def automation_state(self, body: dict[str, Any]) -> dict[str, Any]:
        if self.down:
            raise OdooError(self.status, "down", self.retry_after)
        self.states.append(copy.deepcopy(body))
        return {**self.state_response, "config_version": 1, "config_etag": (self.raw or {}).get("etag")}


def make_ctx(
    clock: FakeClock,
    live: LiveCache,
    device: FakeDevice | None,
    odoo: FakeOdoo | None,
    state_dir: Path | None,
    *,
    write_enabled: bool = True,
) -> tuple[PluginContext, SimpleNamespace]:
    box = SimpleNamespace(readings=[], events=[])
    settings = SimpleNamespace(write_enabled=write_enabled, collector_code="COL-T")

    async def guarded_write(code: str, value: float | None = None, text: str | None = None, **kw: Any) -> str:
        if not settings.write_enabled:  # як CommandLoop.write_direct: F3D_WRITE_ENABLED вимкнено → WriteRefused
            raise WriteRefused("write disabled in collector (F3D_WRITE_ENABLED)")
        return await device.write(code, value, text, **kw)

    ctx = PluginContext(
        settings=settings,
        secrets=lambda n: "",
        allowlist=lambda h: None,
        emit=box.readings.append,
        emit_event=box.events.append,
        metrics=None,
        log=logging.getLogger("collector.plugin.energy_ctl.test"),
        live=live,
        write_signal=guarded_write if device else None,
        read_signal=device.read if device else None,
        odoo=odoo,
        clock=clock,
        state_dir=state_dir,  # type: ignore[arg-type]
    )
    box.settings = settings
    return ctx, box


def source_cfg(params: dict | None = None) -> SourceCfg:
    sig = SignalCfg("energy_control/intent", "event", "", 10, 1.0, True, None, 0, {}, "ENERGY-CTL")
    return SourceCfg(
        "ENERGY-CTL", "energy_ctl", True, True, params or {"engine": {"tick_s": 2, "config_poll_s": 10}}, (sig,)
    )


INTENT_SIGNAL = SignalCfg("energy_control/intent", "event", "", 10, 1.0, True, None, 0, {}, "ENERGY-CTL")


def intent(
    kind: str,
    params: dict | None = None,
    *,
    idem: str = "3f9a7c0e1d2b4a5f6e7d8c9b",
    action_id: int = 55,
    ttl_s: float = 120,
    now: datetime = T0,
    **extra: Any,
) -> dict[str, Any]:
    from collector.util.timeutil import to_iso_z

    return {
        "v": 1,
        "action_id": action_id,
        "idem": idem,
        "kind": kind,
        "cls": "A",
        "params": params or {},
        "requested_by": "ivanenko",
        "requested_at": to_iso_z(now),
        "expires_at": to_iso_z(now + timedelta(seconds=ttl_s)),
        "tz": "Europe/Kyiv",
        "limits": {"bess_kw_max": 200},
        **extra,
    }


class Harness:
    """Плагін із фейковими ядром/пристроєм/Odoo; `tick()` — один тік рушія з синхронізацією «опитування» пристрою."""

    def __init__(
        self, plugin: Any, clock: FakeClock, live: LiveCache, device: FakeDevice, odoo: FakeOdoo, box: Any
    ) -> None:
        self.plugin, self.clock, self.live, self.device, self.odoo, self.box = plugin, clock, live, device, odoo, box

    @property
    def engine(self):
        return self.plugin.engine

    @property
    def executor(self):
        return self.plugin.executor

    @property
    def reporter(self):
        return self.plugin.reporter

    @property
    def cfg(self):
        return self.plugin.cfg

    async def tick(self, seconds: float = 2.0, *, sync: bool = True) -> None:
        self.clock.advance(seconds)
        if sync:
            self.device.sync()
        await self.engine.tick()

    async def run(self, ticks: int, seconds: float = 2.0) -> None:
        for _ in range(ticks):
            await self.tick(seconds)

    def events(self, kind: str | None = None) -> list[dict[str, Any]]:
        evs = list(self.reporter.events)
        return [e for e in evs if kind is None or e["kind"] == kind]

    def written(self, code: str) -> list[Any]:
        return [(v if v is not None else t) for c, v, t in self.device.writes if c == code]


async def make_plugin(
    tmp_path: Path | None,
    raw: dict[str, Any] | None = None,
    *,
    odoo_down: bool = False,
    write_enabled: bool = True,
    connect: bool = True,
    clock: FakeClock | None = None,
    initial: dict[str, Any] | None = None,
) -> Harness:
    from td_collector_energy.plugin import EnergyCtlPlugin

    EnergyCtlPlugin._active = None  # кілька плагінів в одному тесті (сторож «єдиного екземпляра» перевіряє test_plugin)
    clock = clock or FakeClock()
    live = LiveCache(clock)  # type: ignore[arg-type]
    holder: dict[str, Any] = {}
    device = FakeDevice(lambda: holder["plugin"].cfg, live, clock)
    odoo = FakeOdoo(raw if raw is not None else base_raw())
    odoo.down = odoo_down
    ctx, box = make_ctx(clock, live, device, odoo, tmp_path, write_enabled=write_enabled)
    plugin = EnergyCtlPlugin(source_cfg(), ctx)
    holder["plugin"] = plugin
    h = Harness(plugin, clock, live, device, odoo, box)
    if connect:
        await plugin.connect()
        for name, val in (initial or {}).items():
            v, t = val if isinstance(val, tuple) else (None, val) if isinstance(val, str) else (val, None)
            device.set(name, v, t)
    return h


def standard_inputs(**over: Any) -> dict[str, Any]:
    """Типовий «спокійний» стан об'єкта: дистанційний режим, мережа є, BESS і КГУ готові."""
    vals = {
        "remote": 1,
        "grid_kw": 300,
        "export_kw": 0,
        "pv_kw": 0,
        "bess_kw": 0,
        "bess_soc": 82,
        "bess_state": 1,
        "chp_state": 0,
        "chp_kw": 0,
        "chp_hours": 0,
        "ats_pos": 2,
        "src1_ok": 1,
        "p_total": 400,
        "air_bar": 6.8,
        "s1_p": 150,
        "s2_p": 100,
        "pfc1_fault": 0,
        "pfc2_fault": 0,
        "ats_lock": 1,
        "chp_gas": 2.1,
        "chp_permit": 1,
        "bess_temp": 25,
        "bess_mode": 0,
        "bess_ack": 0,
        "chp_ack": 0,
        "qs_ack": 0,
        "air_sp": 6.8,
        "air_min": 6.2,
        "qs_state": "open",
        "pv_limit": 100,
    }
    vals.update(over)
    return vals


def feed(h: Harness, **values: Any) -> None:
    for name, val in values.items():
        v, t = val if isinstance(val, tuple) else (None, val) if isinstance(val, str) else (val, None)
        h.device.regs[h.device._code(name)] = (v, t)
    h.device.sync()


def wire_device(h: Harness) -> None:
    """Емулює реакцію пристроїв на команди: QS перемикається, КГУ стартує, решта регістрів повертає записане."""
    dev = h.device

    def qs(value, text):
        dev.regs["energy/cells/QS/state"] = (None, "closed" if value == 2 else "open")

    def chp(value, text):
        if value == 1:
            dev.regs["infra/chp/state"] = (1.0, None)
        elif value == 2:
            dev.regs["infra/chp/state"] = (4.0, None)

    dev.hooks["energy_control/qs/cmd"] = qs
    dev.hooks["energy_control/chp/cmd"] = chp


async def run_intent(h: Harness, kind: str, params: dict | None = None, **kw: Any) -> tuple[dict, dict | None]:
    """Приймає інтент через `plugin.call` і чекає завершення задачі; повертає (result_data, остання дія для API-25)."""
    payload = intent(kind, params, now=h.clock.now(), **kw)
    res = await h.plugin.call(INTENT_SIGNAL, payload)
    tasks = [t for t in h.executor.running.values()]
    if tasks:
        await asyncio.gather(*tasks)
    return res, h.reporter.actions.get(payload["action_id"])


async def boot_ready(tmp_path: Path | None = None, raw: dict[str, Any] | None = None, **inputs: Any) -> Harness:
    h = await make_plugin(tmp_path, raw)
    feed(h, **standard_inputs(**inputs))
    wire_device(h)
    return h
