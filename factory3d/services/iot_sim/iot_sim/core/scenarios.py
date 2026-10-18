"""Рушій сценаріїв S-01…S-15 (SPEC §8.15, §9.3, §10 «Запуск сценарію»), S-16 ``pfc_step_fault`` (W1 §8.1) і S-17…S-20
(W2 §8.2: ``peak_load``, ``export_demo``, ``ctl_local``, ``chp_no_gas``).

``ScenarioRunner(world).start(name, params, run_ref)`` (потрібен запущений asyncio-цикл):
валідація pydantic (``ScenarioParamsError`` -> 422), режим і конфлікти (``ScenarioConflict`` -> 409),
``Run{id: "r-<ulid>"}``, корутина сценарію. ``await stop(run_id)`` ставить ``stop_event`` і чекає
відкату (``cleanup``). Час у сценаріях — sim-час ``World`` (``ctx.sleep`` вирішується в ``World.step``).

Ефекти, яким потрібні ще не написані моделі, виражені через ``World`` (моделі читають їх самі):

* ``world.flags[<name>]`` — стан: ``shift``, ``blackout``, ``pv_cf`` (float), ``compressor_fault``,
  ``boiler_force_on`` (int), ``fire_drill``, ``genset_test``, ``swb`` (S-16), ``extra_load_kw``/``bess_auto_idle``/
  ``export_target_kw``/``ctl_remote``/``gas_bar`` (S-17…S-20, ``models.meter.CTL_DEFAULTS``); словники за ключем пристрою/групи:
  ``filter_clogged[dev]``, ``lighting_scene[group]``, ``battery_low[dev]``.
* ``world.fault(device, reason)`` / ``clear`` — S-02 (R-15).
* ``world.post(topic, payload)`` — одноразові команди: ``yard`` (truck_no_booking/truck_arrival),
  ``spark``, ``access``; модель забирає ``world.drain(topic)``; результат запуску — у
  ``world.run_results[run_id]``.
* Сигнали, що їх явно веде сценарій (S-04, S-10, S-13), пишуться ``Signal.force``.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
import re
from datetime import datetime, timedelta
from typing import Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
)

from iot_sim.core.events import ulid
from iot_sim.core.world import World

log = logging.getLogger("iot_sim.scenarios")

RUN_ACTIVE = ("running", "stopping")
FAULT_REASONS = Literal["generic", "spindle", "emergency", "power", "comm", "sensor", "loop"]


# --- помилки -----------------------------------------------------------------------------
class ScenarioError(Exception):
    status = 400


class UnknownScenario(ScenarioError):
    status = 404


class ScenarioConflict(ScenarioError):
    status = 409


class ScenarioParamsError(ScenarioError):
    status = 422

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("invalid params")
        self.errors = errors


# --- запуск ------------------------------------------------------------------------------
class Run:
    def __init__(self, run_id: str, name: str, params: dict[str, Any], started: datetime,
                 ends: datetime | None, run_ref: str | None) -> None:
        self.id = run_id
        self.name = name
        self.params = params
        self.state = "running"
        self.started = started
        self.ends = ends
        self.result: dict[str, Any] | None = None
        self.error: str | None = None
        self.run_ref = run_ref
        self.timeline: list[dict[str, Any]] = []
        self.owned_flags: list[tuple[str, str | None]] = []
        self.stop_event = asyncio.Event()
        self.task: asyncio.Task[Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "state": self.state, "params": self.params,
                "started": self.started.isoformat(), "ends": self.ends.isoformat() if self.ends else None,
                "result": self.result, "error": self.error, "run_ref": self.run_ref,
                "timeline": self.timeline,
                "owned_flags": [list(x) for x in self.owned_flags]}


class ScenarioContext:
    """Інструменти сценарію; усе, що зроблено через ctx, відкочується у ``cleanup()``."""

    def __init__(self, world: World, run: Run, params: BaseModel) -> None:
        self.world = world
        self.run = run
        self.params = params
        self.stop = run.stop_event
        self._faults: list[str] = []
        self._forced: list[str] = []

    async def sleep(self, sim_s: float) -> bool:
        """Чекає sim-секунди; ``True``, якщо перервано ``stop``."""
        return await self.sleep_until(self.world.clock.epoch() + sim_s)

    async def sleep_until(self, epoch: float) -> bool:
        if self.stop.is_set():
            return True
        fut = self.world.sleep_until(epoch)
        waiter = asyncio.ensure_future(self.stop.wait())
        await asyncio.wait({fut, waiter}, return_when=asyncio.FIRST_COMPLETED)
        waiter.cancel()
        return self.stop.is_set()

    async def wait_or_stop(self, duration_s: int) -> bool:
        if duration_s > 0:
            return await self.sleep(duration_s)
        await self.stop.wait()
        return True

    def step(self, step: str, message: str, **payload: Any) -> None:
        self.run.timeline.append({"ts": self.world.now().isoformat(), "step": step,
                                  "message": message})
        self.world.events.emit("scenario", message, run_id=self.run.id,
                               payload={"state": "progress", "step": step, "name": self.run.name,
                                        **payload})

    async def timeline(self, steps: list[tuple[float, str, str]]) -> bool:
        """[(t_с_від_початку, step, повідомлення)…] — за абсолютними дедлайнами (нагнати при
        великому ``advance``); ``False``, якщо перервано."""
        t0 = self.world.clock.epoch()
        for at, step, msg in steps:
            if await self.sleep_until(t0 + at):
                return False
            self.step(step, msg)
        return True

    def flag(self, name: str, value: Any, key: str | None = None) -> None:
        if key is None:
            self.world.set_flag(name, value)
        else:
            self.world.flags.setdefault(name, {})[key] = value
        self.run.owned_flags.append((name, key))

    def fault(self, device: str, reason: str) -> None:
        self.world.fault(device, reason)
        self._faults.append(device)

    def force(self, code: str, value: Any, hold_s: float = 0.0) -> None:
        self.world.force(code, value, hold_s)
        if code not in self._forced:
            self._forced.append(code)

    def cleanup(self) -> None:
        clear_flags(self.world, self.run.owned_flags)
        for dev in self._faults:
            if self.world.devices[dev].fault:
                self.world.clear(dev)
        for code in self._forced:
            sig = self.world.signals[code]
            sig.held_until = None
            if sig.params["nominal"] is not None:
                sig.value = sig.params["nominal"]
        self._faults, self._forced = [], []


def clear_flags(world: World, owned: list[Any]) -> None:
    for name, key in owned:
        if key is None:
            world.clear_flag(name)
        else:
            d = world.flags.get(name)
            if isinstance(d, dict):
                d.pop(key, None)
                if not d:
                    world.clear_flag(name)


# --- параметри ---------------------------------------------------------------------------
class BaseParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_s: int = Field(0, ge=0)
    note: str = ""


def _device_check(v: str, info: ValidationInfo, pattern: str, label: str) -> str:
    if not re.fullmatch(pattern, v):
        raise ValueError(f"unknown {label} {v!r}")
    return v


class ShiftParams(BaseParams):
    date: dt.date | None = None
    lines: list[Literal["A", "B", "C", "D", "F"]] = Field(default_factory=lambda: list("ABCDF"))  # type: ignore[arg-type]
    speed: float = Field(1.0, ge=0.5, le=3)
    trucks: bool = True
    people: bool = True


class MachineFaultParams(BaseParams):
    device: str
    reason: FAULT_REASONS = "generic"
    auto_clear_s: int = Field(0, ge=0)

    @field_validator("device")
    @classmethod
    def _dev(cls, v: str, info: ValidationInfo) -> str:
        world = (info.context or {}).get("world")
        if world is not None:
            ok = v == "GANTRY-1" or any(s.code.startswith("workcenters/")
                                        for s in (world.devices[v].signals.values()
                                                  if v in world.devices else []))
            if not ok:
                raise ValueError(f"unknown device {v!r}")
        return v


class BlackoutParams(BaseParams):
    duration_s: int = Field(600, ge=0)
    genset: bool = True
    restore_delay_s: int = Field(60, ge=0)
    amf_master: Literal["hgm", "ats"] | None = None  # None -> SIM_GENSET_AMF_MASTER (hgm)
    genset_load_kw: float | None = Field(None, ge=0, le=558)
    chp_island: bool = False


class FilterParams(BaseParams):
    device: str
    value: float | None = None
    ramp_min: int = Field(2, ge=0)

    @field_validator("device")
    @classmethod
    def _dev(cls, v: str, info: ValidationInfo) -> str:
        m = re.fullmatch(r"RV-(\d\d)", v)
        if v in ("AHU-1", "DUST-1", "FA-FAC") or (m and 1 <= int(m.group(1)) <= 25):
            return v
        raise ValueError(f"unknown device {v!r}")


class TruckNoBookingParams(BaseParams):
    plate: str | None = None
    gate: Literal["GATE-W", "GATE-E"] = "GATE-W"
    wait_min: int = Field(10, ge=0)


class TruckArrivalParams(BaseParams):
    booking: str = Field(min_length=1)
    plate: str | None = None
    at: datetime | None = None
    unload_min: int = Field(40, ge=0)


class FireDrillParams(BaseParams):
    duration_s: int = Field(300, ge=0)
    zone: str = "FA-CNC"
    detector: str | None = None
    real: bool = False

    @field_validator("zone")
    @classmethod
    def _zone(cls, v: str, info: ValidationInfo) -> str:
        return _device_check(v, info, r"FA-[A-Z0-9]+(-\d+)?", "zone")


class SparkParams(BaseParams):
    fault: bool = False
    count: int = Field(1, ge=1, le=5)
    interval_s: int = Field(30, ge=0)


class AccessEventParams(BaseParams):
    device: str = "ACR-IN"
    user: str | None = None
    code: int = Field(4102, ge=1000, le=9999)  # ASSUMPTION: перелік кодів §8.12 не звужуємо
    tna_key: Literal["1", "2", ""] = "1"
    door_open: bool = True

    @field_validator("device")
    @classmethod
    def _dev(cls, v: str, info: ValidationInfo) -> str:
        return _device_check(v, info, r"ACR-[A-Z]+", "device")


class BatteryLowParams(BaseParams):
    device: str
    level_pct: float = Field(18, ge=0, le=100)

    @field_validator("device")
    @classmethod
    def _dev(cls, v: str, info: ValidationInfo) -> str:
        return _device_check(v, info, r"FL-(C?\d+)|TUGGER-1", "device")


class CompressorFaultParams(BaseParams):
    duration_s: int = Field(900, ge=0)
    kind: Literal["pressure_drop", "overtemp", "comm"] = "pressure_drop"


class PvCloudyParams(BaseParams):
    duration_s: int = Field(1800, ge=0)
    cf: float = Field(0.3, ge=0.05, le=1)


class BoilerRefillParams(BaseParams):
    level_pct: float = Field(95, ge=0, le=100)
    force_on: int = Field(-1, ge=-1, le=2)


class GensetTestParams(BaseParams):
    duration_s: int = Field(900, ge=0)
    test_on_load: bool = False


class PfcStepFaultParams(BaseParams):
    """W1 §8.1: ``step = 0`` — без збою ступеня (лише ``qs_closed``); ``duration_s = 0`` — до зупинки."""

    section: Literal[1, 2] = 2
    step: int = Field(3, ge=0, le=10)
    qs_closed: bool = False


class PeakLoadParams(BaseParams):
    """W2 §8.2 (S-17): додаткове навантаження ``extra_kw`` кВт (від'ємне — зменшення, але не нижче нуля)."""

    duration_s: int = Field(900, ge=0)
    extra_kw: float = Field(250.0, ge=-1000, le=2000)


class ExportDemoParams(BaseParams):
    """W2 §8.2 (S-18): експорт рівно ``export_kw`` (BESS «авто» в утриманні 0 кВт, навантаження підганяється)."""

    duration_s: int = Field(900, ge=0)
    export_kw: float = Field(26.0, ge=0, le=500)


class CtlLocalParams(BaseParams):
    """W2 §8.2 (S-19): контролер ГРЩ у місцевому режимі (``ctl_remote = 0``)."""

    duration_s: int = Field(600, ge=0)


class ChpNoGasParams(BaseParams):
    """W2 §8.2 (S-20): тиск газу КГУ нижче мінімуму (``gas_bar``, за замовчуванням 0,80 бар)."""

    duration_s: int = Field(600, ge=0)
    gas_bar: float = Field(0.80, ge=0, le=1.4)


class LightingSceneParams(BaseParams):
    duration_s: int = Field(600, ge=0)
    group: str = "all"
    scene: int | None = Field(None, ge=1, le=16)
    level: int | None = Field(None, ge=0, le=100)
    fault_device: str | None = Field(None, pattern=r"^@\d+\.\d+\.\d+\.\d+$")

    @field_validator("group")
    @classmethod
    def _grp(cls, v: str, info: ValidationInfo) -> str:
        return _device_check(v, info, r"all|LT-[A-Z0-9-]+", "group")

    @field_validator("level")
    @classmethod
    def _excl(cls, v: int | None, info: ValidationInfo) -> int | None:
        if v is not None and info.data.get("scene") is not None:
            raise ValueError("scene і level взаємовиключні")
        return v


# --- сценарії ----------------------------------------------------------------------------
class Scenario:
    name: ClassVar[str]
    title_uk: ClassVar[str]
    group: ClassVar[str]
    Params: ClassVar[type[BaseParams]] = BaseParams
    conflict_groups: ClassVar[frozenset[str]] = frozenset()  # група запущених, з якими конфлікт

    def conflicts(self, p: Any) -> set[str]:
        """Теги ресурсів (``dev:X``, ``energy``, ``loop:GATE-W``, ``lt:*``…); збіг -> 409."""
        return set()

    def check_mode(self, world: World) -> None:
        """Перевірка режиму; ``ScenarioConflict`` -> 409."""

    async def run(self, ctx: ScenarioContext) -> dict[str, Any] | None:
        await self.apply(ctx, ctx.params)
        await ctx.wait_or_stop(ctx.params.duration_s)  # type: ignore[attr-defined]
        return None

    async def apply(self, ctx: ScenarioContext, p: Any) -> None:
        """Виставляє ефекти; відкат — автоматично (``ctx.cleanup``)."""

    @classmethod
    def default_duration(cls) -> int:
        return cls.Params.model_fields["duration_s"].default  # type: ignore[no-any-return]


class Shift(Scenario):
    name, title_uk, group, Params = "shift", "Робоча зміна", "production", ShiftParams

    def conflicts(self, p: Any) -> Any:
        return {"shift"}

    def check_mode(self, world: Any) -> None:
        if world.mode == "follow_odoo":
            raise ScenarioConflict("shift недоступний у follow_odoo")

    async def apply(self, ctx: Any, p: Any) -> None:
        ctx.flag("shift", {"date": (p.date or ctx.world.now().date()).isoformat(),
                           "lines": p.lines, "speed": p.speed, "trucks": p.trucks,
                           "people": p.people})


class MachineFault(Scenario):
    name, title_uk, group, Params = "machine_fault", "Збій верстата", "production", MachineFaultParams

    def conflicts(self, p: Any) -> Any:
        return {f"dev:{p.device}"}

    async def run(self, ctx: Any) -> None:
        p = ctx.params
        ctx.fault(p.device, p.reason)
        ctx.step("fault", f"Збій {p.device}: {p.reason}")
        if p.auto_clear_s > 0:
            if await ctx.sleep(p.auto_clear_s):
                return
            ctx.world.clear(p.device)
            ctx.step("auto_clear", f"Збій {p.device} усунено автоматично")
            return
        await ctx.wait_or_stop(p.duration_s)
        return


class Blackout(Scenario):
    name, title_uk, group, Params = "blackout", "Блекаут (втрата мережі)", "energy", BlackoutParams

    def conflicts(self, p: Any) -> Any:  # ASSUMPTION: «усе енергетичне», у т.ч. COMPRESSOR/AIR-RING (S-11)
        return {"energy", "dev:COMPRESSOR", "dev:AIR-RING"}

    async def run(self, ctx: Any) -> Any:
        p = ctx.params
        amf = p.amf_master or getattr(ctx.world.settings, "genset_amf_master", "hgm")
        ctx.flag("blackout", {"t0": ctx.world.now().isoformat(), "phase": "outage",
                              "genset": p.genset, "amf_master": amf,
                              "restore_delay_s": p.restore_delay_s,
                              "genset_load_kw": p.genset_load_kw, "chp_island": p.chp_island})
        ctx.step("mains_lost", "Зникнення мережі (blackout)", amf_master=amf)
        stopped = await ctx.wait_or_stop(p.duration_s)
        ctx.world.flags["blackout"]["phase"] = "restoring"
        ctx.step("mains_restored", "Повернення мережі")
        return {"stopped": stopped}


class FilterClogged(Scenario):
    name, title_uk, group, Params = "filter_clogged", "Забивання фільтра", "bms", FilterParams
    TARGETS: ClassVar[dict[str, str]] = {"AHU-1": "ventilation/units/AHU-1/filter_dp_pa",
               "DUST-1": "equipment/DUST-1/filter_dp_kpa",
               "FA-FAC": "fire/groups/FA-FAC/dust"}
    DEFAULTS: ClassVar[dict[str, float]] = {"DUST-1": 1.9, "FA-FAC": 92.0}

    def conflicts(self, p: Any) -> Any:
        return {f"dev:{p.device}"}

    def code(self, dev: str) -> str:
        return self.TARGETS.get(dev, f"ventilation/units/{dev}/filter_dp_pa")

    async def run(self, ctx: Any) -> None:
        p = ctx.params
        target = p.value if p.value is not None else self.DEFAULTS.get(p.device, 285.0)
        code = self.code(p.device)
        ctx.flag("filter_clogged", target, key=p.device)
        sig = ctx.world.signals.get(code)
        if sig is not None:
            start = float(sig.value)
            n = max(1, int(p.ramp_min * 60 / 10))
            for i in range(1, n + 1):
                ctx.force(code, start + (target - start) * i / n, hold_s=15)
                if i < n and await ctx.sleep(10):
                    return
            sig.held_until = None  # далі R-09 продовжує
        ctx.step("clogged", f"Фільтр {p.device}: значення {target:g}")
        await ctx.wait_or_stop(p.duration_s)
        return


class TruckNoBooking(Scenario):
    name, title_uk, group, Params = "truck_no_booking", "Фура без бронювання", "logistics", TruckNoBookingParams

    def conflicts(self, p: Any) -> Any:
        return {f"loop:{p.gate}"}

    async def run(self, ctx: Any) -> Any:
        p = ctx.params
        plate = p.plate or f"AA{ctx.world.minute % 10000:04d}KT"
        ctx.world.post("yard", {"kind": "truck_no_booking", "plate": plate, "gate": p.gate,
                                "wait_min": p.wait_min, "run_id": ctx.run.id})
        ctx.step("rejected", f"Фура {plate} без бронювання біля воріт {p.gate}", plate=plate)
        if await ctx.sleep(p.wait_min * 60):
            return {"plate": plate}
        ctx.step("left", f"Фура {plate} поїхала")
        return {"plate": plate}


class TruckArrival(Scenario):
    name, title_uk, group, Params = "truck_arrival", "Прибуття фури з бронюванням", "logistics", TruckArrivalParams
    # R-29: відкриття 5 с, ваги 60 с, до дока 3 хв, розвантаження, до виїзду 2 хв, ваги 60 с

    def conflicts(self, p: Any) -> Any:
        return {"loop:GATE-W"}

    async def run(self, ctx: Any) -> Any:
        p = ctx.params
        ctx.world.post("yard", {"kind": "truck_arrival", "booking": p.booking, "plate": p.plate,
                                "at": p.at.isoformat() if p.at else None,
                                "unload_min": p.unload_min, "run_id": ctx.run.id})
        ok = await ctx.timeline([
            (0, "at_gate", f"Фура {p.booking} біля воріт"), (5, "weigh_in", "Ваги: брутто"),
            (65, "to_dock", "До дока"), (245, "at_dock", "Розвантаження")])
        if not ok or await ctx.sleep(p.unload_min * 60):
            return None
        ok = await ctx.timeline([(0, "to_exit", "До виїзду"), (120, "weigh_out", "Ваги: тара"),
                                 (180, "left", "Фура виїхала")])
        return ctx.world.run_results.pop(ctx.run.id, {}) if ok else None


class FireDrill(Scenario):
    name, title_uk, group, Params = "fire_drill", "Пожежні навчання/тривога", "safety", FireDrillParams
    conflict_groups = frozenset({"safety", "bms"})
    STEPS: ClassVar[list[tuple[int, str, str]]] = [(0, "alarm", "Тривога на панелі"), (3, "sounders", "Сирени"),
             (6, "vent_stop", "Зупинка вентиляції"), (9, "dampers", "Димовидалення"),
             (12, "doors", "Двері й шлагбауми"), (20, "machines", "Верстати зони → ERROR")]

    def conflicts(self, p: Any) -> Any:
        return {f"zone:{p.zone}"}

    async def run(self, ctx: Any) -> Any:
        p = ctx.params
        ctx.flag("fire_drill", {"zone": p.zone, "detector": p.detector, "real": p.real,
                                "t0": ctx.world.now().isoformat(), "phase": "active"})
        if await ctx.timeline(self.STEPS):
            await ctx.wait_or_stop(max(p.duration_s - 20, 0))
        ctx.world.flags["fire_drill"]["phase"] = "restoring"  # відкат у зворотному порядку за 30 с
        ctx.step("restoring", "Відновлення нормального стану (30 с)")
        return {"alarm_latency_s": 0, "sounders_s": 3, "vent_stop_s": 6, "doors_s": 12}


class Spark(Scenario):
    name, title_uk, group, Params = "spark", "Іскра в аспірації", "safety", SparkParams

    async def run(self, ctx: Any) -> Any:
        p = ctx.params
        for i in range(p.count):
            ctx.world.post("spark", {"fault": p.fault, "index": i, "run_id": ctx.run.id})
            ctx.step("spark", f"Іскра {i + 1}/{p.count}")
            if i < p.count - 1 and await ctx.sleep(p.interval_s):
                break
        return {"count": p.count}


class AccessEvent(Scenario):
    name, title_uk, group, Params = "access_event", "Подія СКУД", "access", AccessEventParams

    async def run(self, ctx: Any) -> None:
        p = ctx.params
        ctx.world.post("access", {"device": p.device, "user": p.user, "code": p.code,
                                  "tna_key": p.tna_key, "door_open": p.door_open,
                                  "run_id": ctx.run.id})
        ctx.step("access", f"Подія {p.code} на {p.device}")


class BatteryLow(Scenario):
    name, title_uk, group, Params = "battery_low", "Низький заряд АКБ", "logistics", BatteryLowParams

    def conflicts(self, p: Any) -> Any:
        return {f"dev:{p.device}"}

    async def run(self, ctx: Any) -> None:
        p = ctx.params
        ctx.flag("battery_low", p.level_pct, key=p.device)
        code = f"equipment/{p.device}/battery"
        if code in ctx.world.signals:
            ctx.world.signals[code].force(p.level_pct, ctx.world.now())  # без утримання: R-05 далі
        ctx.step("battery", f"{p.device}: заряд {p.level_pct:g} %")
        await ctx.wait_or_stop(p.duration_s)


class CompressorFault(Scenario):
    name, title_uk, group, Params = "compressor_fault", "Збій компресора", "energy", CompressorFaultParams

    def conflicts(self, p: Any) -> Any:
        return {"dev:COMPRESSOR", "dev:AIR-RING"}

    async def apply(self, ctx: Any, p: Any) -> None:
        ctx.flag("compressor_fault", {"kind": p.kind})


class PvCloudy(Scenario):
    name, title_uk, group, Params = "pv_cloudy", "Хмарність (СЕС)", "energy", PvCloudyParams

    def conflicts(self, p: Any) -> Any:
        return {"energy"}

    async def apply(self, ctx: Any, p: Any) -> None:
        ctx.flag("pv_cf", p.cf)


class BoilerRefill(Scenario):
    name, title_uk, group, Params = "boiler_refill", "Поповнення бункера котельні", "bms", BoilerRefillParams
    SILO = "equipment/BOILER/silo_fill"

    def conflicts(self, p: Any) -> Any:
        return {"dev:BOILER"}

    async def run(self, ctx: Any) -> None:
        p = ctx.params
        if self.SILO in ctx.world.signals:
            ctx.world.signals[self.SILO].force(p.level_pct, ctx.world.now())
        if p.force_on >= 0:
            ctx.flag("boiler_force_on", p.force_on)
        ctx.step("refill", f"Бункер: {p.level_pct:g} %")
        await ctx.wait_or_stop(p.duration_s)


class GensetTest(Scenario):
    name, title_uk, group, Params = "genset_test", "Тестовий пуск ДГУ", "energy", GensetTestParams

    def conflicts(self, p: Any) -> Any:
        return {"energy"}

    async def run(self, ctx: Any) -> None:
        p = ctx.params
        ctx.flag("genset_test", {"on_load": p.test_on_load, "phase": "running"})
        ctx.world.events.emit("info", "Тестовий пуск генератора", run_id=ctx.run.id)
        ctx.step("start", "Тестовий пуск", on_load=p.test_on_load)
        await ctx.wait_or_stop(p.duration_s)
        ctx.step("stop", "Тестовий пуск завершено")


class LightingScene(Scenario):
    name, title_uk, group, Params = "lighting_scene", "Сцена освітлення", "bms", LightingSceneParams

    def conflicts(self, p: Any) -> Any:
        return {"lt:*" if p.group == "all" else f"lt:{p.group}"}

    async def run(self, ctx: Any) -> None:
        p = ctx.params
        ctx.flag("lighting_scene", {"scene": p.scene, "level": p.level,
                                    "fault_device": p.fault_device}, key=p.group)
        ctx.step("scene", f"Освітлення {p.group}")
        await ctx.wait_or_stop(p.duration_s)


class PfcStepFault(Scenario):
    """W1 §8.1 (S-16): ступінь PFC секції не вмикається; модель — ``iot_sim.models.swb`` (прапор ``swb``)."""

    name, title_uk, group, Params = "pfc_step_fault", "Збій ступеня PFC", "energy", PfcStepFaultParams

    def conflicts(self, p: Any) -> Any:
        return {"dev:SWB-CTRL"}

    async def apply(self, ctx: Any, p: Any) -> None:
        ctx.flag("swb", {"section": p.section, "step": p.step, "qs_closed": p.qs_closed})
        if p.step:
            ctx.step("pfc_fault", f"PFC-{p.section}: ступінь {p.step} не вмикається", section=p.section, pfc_step=p.step)
        else:
            ctx.step("swb", "Контролер ГРЩ: параметри сценарію", qs_closed=p.qs_closed)


class PeakLoad(Scenario):
    """W2 §8.2 (S-17): ``extra_load_kw`` — модель ``meter`` додає його до навантаження (імпорт росте до піку)."""

    name, title_uk, group, Params = "peak_load", "Пік навантаження", "energy", PeakLoadParams

    def conflicts(self, p: Any) -> Any:
        return {"load"}

    async def apply(self, ctx: Any, p: Any) -> None:
        ctx.flag("extra_load_kw", p.extra_kw)
        ctx.step("peak_load", f"Додаткове навантаження {p.extra_kw:g} кВт", extra_kw=p.extra_kw)


class ExportDemo(Scenario):
    """W2 §8.2 (S-18): ``bess_auto_idle`` + ``export_target_kw`` — експорт рівно ``export_kw`` (``load = gen − export``)."""

    name, title_uk, group, Params = "export_demo", "Демо експорту СЕС", "energy", ExportDemoParams

    def conflicts(self, p: Any) -> Any:
        return {"load", "dev:BESS"}

    async def apply(self, ctx: Any, p: Any) -> None:
        ctx.flag("bess_auto_idle", True)
        ctx.flag("export_target_kw", p.export_kw)
        ctx.step("export_demo", f"Експорт {p.export_kw:g} кВт", export_kw=p.export_kw)


class CtlLocal(Scenario):
    """W2 §8.2 (S-19): ``ctl_remote = 0`` — контролер у місцевому режимі, команди дають ``ack = 2``."""

    name, title_uk, group, Params = "ctl_local", "Контролер ГРЩ у місцевому режимі", "energy", CtlLocalParams

    def conflicts(self, p: Any) -> Any:
        return {"ctl"}

    async def apply(self, ctx: Any, p: Any) -> None:
        ctx.flag("ctl_remote", 0)
        ctx.step("ctl_local", "Контролер ГРЩ: місцевий режим")


class ChpNoGas(Scenario):
    """W2 §8.2 (S-20): ``gas_bar`` нижче 1,5 бар — пуск КГУ відхиляється (``chp/ack = 2``)."""

    name, title_uk, group, Params = "chp_no_gas", "КГУ: немає газу", "energy", ChpNoGasParams

    def conflicts(self, p: Any) -> Any:
        return {"dev:CHP"}

    async def apply(self, ctx: Any, p: Any) -> None:
        ctx.flag("gas_bar", p.gas_bar)
        ctx.step("chp_no_gas", f"Тиск газу КГУ {p.gas_bar:g} бар", gas_bar=p.gas_bar)


SCENARIOS: list[type[Scenario]] = [
    Shift, MachineFault, Blackout, FilterClogged, TruckNoBooking, TruckArrival, FireDrill, Spark,
    AccessEvent, BatteryLow, CompressorFault, PvCloudy, BoilerRefill, GensetTest, LightingScene,
    PfcStepFault, PeakLoad, ExportDemo, CtlLocal, ChpNoGas]


def _tags_conflict(a: set[str], b: set[str]) -> str | None:
    for x in a:
        for y in b:
            if x == y or (x.endswith("*") and y.startswith(x[:-1])) or (
                    y.endswith("*") and x.startswith(y[:-1])):
                return x if x == y else (y if x.endswith("*") else x)
    return None


class ScenarioRunner:
    def __init__(self, world: World) -> None:
        self.world = world
        self.scenarios: dict[str, Scenario] = {c.name: c() for c in SCENARIOS}
        self.runs = world.runs
        self._tags: dict[str, set[str]] = {}

    def list(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "title_uk": s.title_uk, "group": s.group,
                 "duration_s": s.default_duration(),
                 "params_schema": s.Params.model_json_schema()} for s in self.scenarios.values()]

    def active(self) -> list[Run]:  # type: ignore[valid-type]
        return [r for r in self.runs.values() if r.state in RUN_ACTIVE]

    def validate(self, name: str, params: dict[str, Any] | None) -> tuple[Scenario, BaseModel]:
        sc = self.scenarios.get(name)
        if sc is None:
            raise UnknownScenario(f"unknown scenario {name}")
        try:
            p = sc.Params.model_validate(params or {}, context={"world": self.world})
        except ValidationError as exc:
            raise ScenarioParamsError(exc.errors(include_url=False, include_context=False)) from exc  # type: ignore[arg-type]
        return sc, p

    def start(self, name: str, params: dict[str, Any] | None = None, run_ref: str | None = None) -> Run:
        sc, p = self.validate(name, params)
        sc.check_mode(self.world)
        tags = sc.conflicts(p)
        for other in self.active():  # type: ignore[attr-defined]
            osc = self.scenarios[other.name]
            hit = _tags_conflict(tags, self._tags[other.id])
            if hit is None and (sc.group in osc.conflict_groups or osc.group in sc.conflict_groups):
                hit = f"group:{osc.group}"
            if hit is not None:
                what = f"device {hit[4:]}" if hit.startswith("dev:") else hit
                raise ScenarioConflict(f"{what} busy by run {other.id}")
        now = self.world.now()
        dur = p.duration_s  # type: ignore[attr-defined]
        run = Run(f"r-{ulid()}", name, p.model_dump(mode="json"), now,
                  now + timedelta(seconds=dur) if dur else None, run_ref)
        self.runs[run.id] = run
        self._tags[run.id] = tags
        self._emit(run, "started", f"Сценарій {name} запущено")
        ctx = ScenarioContext(self.world, run, p)
        # eager: ефекти (прапори, збої) застосовуються до повернення з start()
        run.task = asyncio.Task(self._execute(sc, ctx), loop=asyncio.get_running_loop(),
                                eager_start=True)
        return run

    async def _execute(self, sc: Scenario, ctx: ScenarioContext) -> None:
        run = ctx.run
        try:
            run.result = await sc.run(ctx)
            state = "stopped" if ctx.stop.is_set() else "done"
        except Exception as exc:  # сценарій -> failed + подія error
            log.exception("scenario %s failed", run.name)
            run.error = str(exc)
            state = "failed"
            self.world.events.emit("error", f"Сценарій {run.name}: {exc}", run_id=run.id)
        finally:
            ctx.cleanup()
        run.state = state
        self._tags.pop(run.id, None)
        self._emit(run, state, f"Сценарій {run.name}: {state}")

    def _emit(self, run: Run, state: str, msg: str) -> None:
        self.world.events.emit("scenario", msg, run_id=run.id,
                               payload={"state": state, "name": run.name, "run_ref": run.run_ref})

    async def stop(self, run_id: str) -> Run:
        run = self.runs.get(run_id)
        if run is None:
            raise UnknownScenario(f"unknown run {run_id}")
        if run.state == "running" and run.task is not None:
            run.state = "stopping"
            run.stop_event.set()
            await run.task
        return run  # type: ignore[no-any-return]

    async def stop_all(self) -> list[Run]:  # type: ignore[valid-type]
        return [await self.stop(r.id) for r in self.active()]  # type: ignore[attr-defined]

    def restore_runs(self, saved: dict[str, dict[str, Any]]) -> None:
        """Після рестарту запуски не відновлюються: закриваються як ``stopped`` (AC-48),
        їхні прапори знімаються."""
        for rid, d in saved.items():
            clear_flags(self.world, [tuple(x) for x in d.get("owned_flags", [])])
            run = Run(rid, d["name"], d["params"], datetime.fromisoformat(d["started"]), None,
                      d.get("run_ref"))
            run.state = "stopped"
            self.runs[rid] = run
            self._emit(run, "stopped", f"Сценарій {run.name}: stopped (рестарт сервісу)")
