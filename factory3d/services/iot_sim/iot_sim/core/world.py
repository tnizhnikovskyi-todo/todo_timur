"""Ядро: ``Signal``, ``Device``, ``World`` (SPEC §8.2.3, §9.2).

Публічний інтерфейс для протокольних воркерів і моделей:

* ``world.signals[code] -> Signal`` (``.value/.status/.ts/.held_until/.params/.spec``),
  ``world.devices[code] -> Device`` (``.model``, ``.signals`` за коротким ключем, ``.fault``).
* ``world.events: EventBus`` (``emit/since/subscribe``); ``world.now()`` — tz-aware sim-час.
* ``world.step(dt_s)`` — тік за порядком §8.2.3; ``world.advance(sim_s)`` — кроками ≤ 10 с;
  ``world.tick_real(real_dt)`` — для циклу сервісу; ``world.on_tick(fn)`` — push протоколів.
* Керування: ``fault(device, reason)``, ``clear(device)``, ``set_flag/flag/clear_flag``,
  ``post(topic, payload)/drain(topic)`` (команди сценаріїв моделям), ``sleep(sim_s)`` (await у sim-часі),
  ``force(code, value, hold_s)``, ``add_hook(stage, fn)`` (stage: planner|balance|post).
* Стан для моделей: ``mode``, ``shift`` (календар), ``workcenters``, ``jobs``, ``trucks``, ``people``,
  ``balance``, ``maintenance_closed``, ``flags`` (JSON-сумісний словник), ``run_results``.
"""
from __future__ import annotations

import asyncio
import copy
import logging
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from iot_sim.core.clock import MAX_SUBSTEP_S, SimClock
from iot_sim.core.events import EventBus
from iot_sim.core.registry import Registry, SignalSpec
from iot_sim.core.rng import Rng
from iot_sim.models import model_class
from iot_sim.models.base import AGGREGATE, Model

log = logging.getLogger("iot_sim.world")

# теми команд, які протоколи вже застосували самі (force/flag) і ніхто з моделей не drain-ить: ліміт черги
BOUNDED_TOPICS = {"ats": 256, "hvac": 256, "boiler": 256, "meter": 256, "modbus_cmd": 256,
                  "opc_joborder": 256}
STATUSES = ("ok", "warn", "alarm", "stale")
HOOK_STAGES = ("planner", "balance", "post")


class Signal:
    """Один сигнал каталогу. ``set()`` — єдина точка запису моделей (поважає ``held_until``)."""

    def __init__(self, spec: SignalSpec, ts: datetime) -> None:
        self.spec = spec
        self.code = spec.code
        self.device = spec.device
        self.protocol = spec.protocol
        self.address = spec.address
        self.dtype = spec.dtype
        self.unit = spec.unit
        self.kind = spec.kind
        self.value: Any = spec.initial_value()
        self.status = "ok"
        self.ts = ts
        self.held_until: datetime | None = None
        self.params: dict[str, Any] = {
            "nominal": spec.nominal, "noise": spec.noise, "rate": spec.rate,
            "limit": spec.limit, "alarm": spec.alarm, "threshold": spec.threshold,
            "source": spec.status}

    @property
    def title(self) -> str:
        return f"{self.device} {self.spec.leaf}"

    def held(self, now: datetime) -> bool:
        return self.held_until is not None and self.held_until > now

    def set(self, value: Any, ts: datetime) -> bool:
        """Записує значення моделі; ``False`` (ігнор), якщо діє утримання ``held_until``."""
        if self.held(ts):
            return False
        self.value = value
        self.ts = ts
        return True

    def force(self, value: Any, ts: datetime, hold_s: float = 0.0) -> None:
        """Запис зверху моделі (сценарій/API): значення + утримання на ``hold_s`` sim-секунд."""
        self.value = value
        self.ts = ts
        self.held_until = ts + timedelta(seconds=hold_s) if hold_s > 0 else None

    def evaluate(self) -> str:
        """§9.2: alarm за порогом, warn — у межах 10 % до порога; ``stale`` ставить World."""
        thr, mode, v = self.params["threshold"], self.params["alarm"], self.value
        if thr is None or mode is None or isinstance(v, bool) or not isinstance(v, (int, float)):
            return "ok"
        margin = 0.1 * abs(thr)
        if mode == "above":
            return "alarm" if v > thr else ("warn" if v > thr - margin else "ok")
        return "alarm" if v < thr else ("warn" if v < thr + margin else "ok")

    def norm_text(self) -> str:
        thr = self.params["threshold"]
        word = "до" if self.params["alarm"] == "above" else "від"
        return f"{self.title}: {self.value:g} {self.unit} при нормі {word} {thr:g}"


class Device:
    """Пристрій: ``signals`` — за коротким ключем (див. ``models.base``), ``fault`` — причина збою."""

    def __init__(self, code: str, driver: str, protocol: str | None, unit_id: int | None,
                 instance: str | None, address: str | None, params: dict[str, Any]) -> None:
        self.code = code
        self.driver = driver
        self.protocol = protocol
        self.unit_id = unit_id
        self.instance = instance
        self.address = address
        self.params = params
        self.model: Model
        self.state = "ok"
        self.fault: str | None = None
        self.signals: dict[str, Signal] = {}
        self.by_code: dict[str, Signal] = {}  # усі сигнали пристрою за повним кодом (без втрат при колізіях)


@dataclass
class ShiftCalendar:
    """Календар зміни (ASSUMPTION: пн–пт, 07:00–15:30, обід 11:30–12:00; R-03, R-14, R-24)."""

    start: time = time(7, 0)
    end: time = time(15, 30)
    lunch_from: time = time(11, 30)
    lunch_to: time = time(12, 0)
    workdays: tuple[int, ...] = (0, 1, 2, 3, 4)

    def in_shift(self, dt: datetime) -> bool:
        return dt.weekday() in self.workdays and self.start <= dt.time() < self.end

    def in_lunch(self, dt: datetime) -> bool:
        return self.lunch_from <= dt.time() < self.lunch_to

    def shift_start(self, dt: datetime) -> datetime:
        return datetime.combine(dt.date(), self.start, tzinfo=dt.tzinfo)


@dataclass
class _Timer:
    deadline: float
    seq: int
    fn: Callable[[], None] = field(compare=False)


class World:
    def __init__(self, registry: Registry, *, seed: int = 20261012,
                 clock: SimClock | None = None, settings: Any = None,
                 mode: str = "scenario") -> None:
        self.registry = registry
        self.seed = seed
        self.clock = clock or SimClock()
        self.settings = settings
        self.mode = mode
        self.events = EventBus(self.now)
        self.shift = ShiftCalendar()
        self.workcenters: dict[str, dict[str, Any]] = {}
        self.jobs: list[dict[str, Any]] = []
        self.trucks: list[dict[str, Any]] = []
        self.people: list[dict[str, Any]] = []
        self.balance: dict[str, float] = {}
        self.maintenance_closed: set[str] = set()
        self.flags: dict[str, Any] = {}
        self.inbox: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
        self.run_results: dict[str, dict[str, Any]] = {}
        self.runs: dict[str, Any] = {}  # заповнює ScenarioRunner
        self.odoo_stale = False
        self.tick_count = 0
        self.last_tick_real: float | None = None
        self._hooks: dict[str, list[Callable[[World, float], None]]] = {s: [] for s in HOOK_STAGES}
        self._tick_cbs: list[Callable[[World], None]] = []
        self._timers: list[_Timer] = []
        self._timer_seq = 0
        self._rngs: dict[str, Rng] = {}
        self.minute0 = self.minute  # початок хвилинного шуму (R-00)
        self.signals: dict[str, Signal] = {}
        self.devices: dict[str, Device] = {}
        self._build()

    # --- побудова --------------------------------------------------------------------
    def _build(self) -> None:
        ts = self.now()
        for spec in self.registry.signals:
            self.signals[spec.code] = Signal(spec, ts)
        for ds in self.registry.devices.values():
            dev = Device(ds.code, ds.driver, ds.protocol, ds.unit_id, ds.instance, None,
                         dict(ds.params))
            leaves: dict[str, list[Signal]] = defaultdict(list)
            for code in ds.signals:
                dev.by_code[code] = self.signals[code]
                leaves[code.rsplit("/", 1)[-1]].append(self.signals[code])
            for leaf, sigs in leaves.items():
                if len(sigs) == 1:
                    dev.signals[leaf] = sigs[0]
                else:  # колізія листів (PV-INV-1…8): ключ ``<інстанс>/<лист>``
                    for s in sigs:
                        short = f"{s.code.split('/')[-2]}/{leaf}"
                        if short in dev.signals and dev.signals[short] is not s:
                            log.warning("колізія коротких ключів %s.signals[%r]: лишається %s, %s лише за повним кодом",
                                        ds.code, short, dev.signals[short].code, s.code)
                            continue
                        dev.signals[short] = s
            dev.model = model_class(ds.driver)(dev, self)
            self.devices[ds.code] = dev
        for dev in self.devices.values():
            dev.model.attach()
        self._initial_models = {c: copy.deepcopy(d.model.to_dict()) for c, d in self.devices.items()}

    def reset_models(self) -> None:
        """API-17 reset: внутрішній стан моделей (лічильники, АКБ, завдання) — початковий, ГПВЧ — за seed."""
        for code, dev in self.devices.items():
            init = self._initial_models.get(code)
            if init is not None:
                try:
                    dev.model.from_dict(copy.deepcopy(init))
                except Exception:
                    log.exception("reset моделі %s", code)
        if hasattr(self, "_yard"):  # двір: ворота, фури, імпульси, LPR-черги — спільний контролер (відтворюється ліниво)
            del self._yard
        self._rngs.clear()
        if self.mode == "scenario":
            self.jobs.clear()

    # --- час і шум -------------------------------------------------------------------
    def now(self) -> datetime:
        return self.clock.now()

    @property
    def minute(self) -> int:
        return self.clock.minute_index()

    def r(self, code: str) -> float:
        """R-00: ``r`` сигналу для поточної sim-хвилини."""
        rng = self._rngs.get(code)
        if rng is None:
            rng = self._rngs[code] = Rng(self.seed, code)
        return rng.at(self.minute, self.minute0)

    def set_mode(self, mode: str) -> None:
        if mode not in ("scenario", "follow_odoo"):
            raise ValueError(mode)
        self.mode = mode  # значення сигналів не скидаються (§8.15)

    # --- прапори, команди, таймери ---------------------------------------------------
    def set_flag(self, name: str, value: Any) -> None:
        self.flags[name] = value

    def flag(self, name: str, default: Any = None) -> Any:
        return self.flags.get(name, default)

    def clear_flag(self, name: str) -> None:
        self.flags.pop(name, None)

    def post(self, topic: str, payload: dict[str, Any]) -> None:
        """Команда моделі (``yard``, ``spark``, ``access``, ``lighting``…); модель забирає ``drain``."""
        q = self.inbox.get(topic)
        if q is None:  # команди без споживача-моделі (ats/hvac/meter/…) не мають рости безмежно
            q = self.inbox[topic] = deque(maxlen=BOUNDED_TOPICS.get(topic))
        q.append(payload)

    def drain(self, topic: str) -> list[dict[str, Any]]:
        q = self.inbox[topic]
        out = list(q)
        q.clear()
        return out

    def add_hook(self, stage: str, fn: Callable[[World, float], None]) -> None:
        self._hooks[stage].append(fn)

    def on_tick(self, fn: Callable[[World], None]) -> None:
        self._tick_cbs.append(fn)

    def call_later(self, sim_s: float, fn: Callable[[], None]) -> None:
        self._timer_seq += 1
        self._timers.append(_Timer(self.clock.epoch() + sim_s, self._timer_seq, fn))
        self._timers.sort(key=lambda t: (t.deadline, t.seq))

    def sleep_until(self, epoch: float) -> asyncio.Future[Any]:
        """Future, що вирішується, коли sim-епоха ≥ ``epoch`` (одразу, якщо вже минула)."""
        fut = asyncio.get_running_loop().create_future()
        if epoch <= self.clock.epoch():
            fut.set_result(None)
        else:
            self._timer_seq += 1
            self._timers.append(_Timer(epoch, self._timer_seq,
                                       lambda: fut.done() or fut.set_result(None)))  # type: ignore[arg-type,func-returns-value]
            self._timers.sort(key=lambda t: (t.deadline, t.seq))
        return fut

    def sleep(self, sim_s: float) -> asyncio.Future[Any]:
        """``await world.sleep(30)`` — чекає 30 sim-секунд (вирішується в ``step``)."""
        return self.sleep_until(self.clock.epoch() + sim_s)

    def force(self, code: str, value: Any, hold_s: float = 0.0) -> None:
        self.signals[code].force(value, self.now(), hold_s)

    # --- збої ------------------------------------------------------------------------
    def fault(self, device: str, reason: str = "generic", **kw: Any) -> None:
        self.devices[device].model.fault(reason, **kw)

    def clear(self, device: str) -> None:
        self.devices[device].model.clear()

    # --- тік -------------------------------------------------------------------------
    def step(self, dt_s: float) -> None:
        """Порядок §8.2.3: планувальник → джерела → агрегати → баланс → пороги → push."""
        if self.clock.manual:
            self.clock.advance(dt_s)
        self._run_hooks("planner", dt_s)
        devs = sorted(self.devices.values(), key=lambda d: d.code)
        for phase_aggregate in (False, True):
            for dev in devs:
                if (dev.model.phase == AGGREGATE) == phase_aggregate:
                    dev.model._tick(dt_s)
        self._run_hooks("balance", dt_s)
        self._update_status()
        self._run_hooks("post", dt_s)
        self._fire_timers()
        self.tick_count += 1
        for cb in self._tick_cbs:
            cb(self)

    def _run_hooks(self, stage: str, dt_s: float) -> None:
        for fn in self._hooks[stage]:
            fn(self, dt_s)

    def advance(self, sim_s: float) -> None:
        """Прокрутити ``sim_s`` sim-секунд кроками ≤ 10 с."""
        left = sim_s
        while left > 1e-9:
            sub = min(MAX_SUBSTEP_S, left)
            self.step(sub)
            left -= sub

    def tick_real(self, real_dt: float) -> None:
        self.advance(real_dt * self.clock.factor)

    def _fire_timers(self) -> None:
        now = self.clock.epoch()
        while self._timers and self._timers[0].deadline <= now:
            self._timers.pop(0).fn()

    def _update_status(self) -> None:
        for sig in self.signals.values():
            dev = self.devices.get(sig.device)
            if dev is not None and dev.fault == "comm":
                new = "stale"
            else:
                new = sig.evaluate()
            old = sig.status
            if new == old:
                continue
            sig.status = new
            if new == "alarm":
                self.events.emit("alarm", sig.norm_text(), device=sig.device,
                                 payload={"signal": sig.code, "value": sig.value})
            elif old == "alarm" and new in ("ok", "warn"):
                self.events.emit("info", f"{sig.title}: повернувся в норму", device=sig.device,
                                 payload={"signal": sig.code, "value": sig.value})

    # --- знімок ----------------------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        from iot_sim.core.snapshot import dump
        return dump(self)

    def restore(self, data: dict[str, Any]) -> None:
        from iot_sim.core.snapshot import restore
        restore(self, data)
