"""EnergyCtlPlugin: validate/connect/subscribe/call/health/disconnect (SPEC 8.1.3).

Тип джерела `energy_ctl` (єдиний екземпляр `ENERGY-CTL`), `push_mode = True`. Плагін об'єднує цикл автоматики
(`Engine`, R-44…R-51) і виконавця інтентів оператора (`Executor`, R-52); у пристрої пише через інші джерела збирача
(`ctx.write_signal`), тими самими запобіжниками й allowlist. Мережевого з'єднання з пристроями не відкриває.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
from importlib import resources
from typing import Any, ClassVar

from collector.core.errors import ConnectError, NotSupported
from collector.core.odoo_client import OdooError
from collector.core.types import Health, Reading, SignalCfg, SourceCfg
from collector.plugins.base import PluginContext, SourcePlugin
from collector.util.timeutil import SystemClock, parse_iso
from jsonschema import Draft202012Validator

from . import config as cfgmod
from .actuator import Actuator, Writer
from .engine import Engine
from .executor import Executor
from .model import Event
from .reporter import Reporter
from .scenarios import CARDS
from .store import Store

INTENT_SIGNAL = "energy_control/intent"
HEARTBEAT_SIGNAL = "energy_control/auto/heartbeat"
HEARTBEAT_S = 10.0
REPORT_S = 10.0
SKEW_WARN_S = 30.0


def _load(name: str) -> dict:
    return json.loads(resources.files("td_collector_energy").joinpath("schemas", name).read_text("utf-8"))


class EnergyCtlPlugin(SourcePlugin):
    type: ClassVar[str] = "energy_ctl"
    version: ClassVar[str] = "0.1.0"
    address_schema: ClassVar[dict] = _load("address.energy_ctl.json")
    params_schema: ClassVar[dict] = _load("params.energy_ctl.json")
    push_mode: ClassVar[bool] = True
    _active: ClassVar[EnergyCtlPlugin | None] = None  # єдиний екземпляр (R: «дублікат джерела»)

    def __init__(self, source: SourceCfg, ctx: PluginContext) -> None:
        super().__init__(source, ctx)
        self.log = ctx.log or logging.getLogger(f"collector.plugin.energy_ctl.{source.code}")
        self.clock = ctx.clock or SystemClock()
        self.cfg: cfgmod.Config | None = None
        self.config_error: str | None = None
        self.odoo_error: str | None = None
        self.tasks: list[asyncio.Task] = []
        self._config_wake = asyncio.Event()
        self._beat_states: dict[str, str] = {}
        self.store: Store | None = None
        self.engine: Engine | None = None
        self.executor: Executor | None = None
        self.reporter: Reporter | None = None

    # --- validate / connect -------------------------------------------------------------------------
    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        errs = [
            f"params: {'/'.join(map(str, e.path)) or '$'}: {e.message}"
            for e in Draft202012Validator(cls.params_schema).iter_errors(source.params or {})
        ]
        addr = Draft202012Validator(cls.address_schema)
        for sg in source.signals:
            errs += [f"{sg.code}: address: {e.message}" for e in addr.iter_errors(sg.address or {})]
        return errs

    def _write_enabled(self) -> bool:
        return bool(getattr(self.ctx.settings, "write_enabled", True))

    def _tick_s(self) -> float:
        if self.cfg is not None:
            return self.cfg.engine.tick_s
        return float(((self.source.params or {}).get("engine") or {}).get("tick_s", 2))

    def _poll_s(self) -> float:
        if self.cfg is not None:
            return self.cfg.engine.config_poll_s
        return float(((self.source.params or {}).get("engine") or {}).get("config_poll_s", 10))

    async def connect(self) -> None:
        active = EnergyCtlPlugin._active
        if active is not None and active is not self:
            raise ConnectError("energy_ctl: дублікат джерела")
        EnergyCtlPlugin._active = self
        ctx, now = self.ctx, self.clock.now()
        self.store = Store(ctx.state_dir, self.log)
        self.store.load(now)
        get_cfg = lambda: self.cfg  # noqa: E731
        writer = Writer(ctx.write_signal, get_cfg, ctx.live, self.clock.now, self._writer_event, self.log)
        self.reporter = Reporter(
            ctx.odoo,
            getattr(ctx.settings, "collector_code", "") or self.source.code,
            self.clock,
            lambda: self.engine.snapshot() if self.engine else {},
            self.log,
            self._on_report,
        )
        actuator = Actuator(writer, get_cfg, ctx.live, self.log)
        self.engine = Engine(
            store=self.store,
            reporter=self.reporter,
            writer=writer,
            actuator=actuator,
            live=ctx.live,
            clock=self.clock,
            get_cfg=get_cfg,
            write_enabled=self._write_enabled,
            log=self.log,
        )
        self.executor = Executor(
            store=self.store,
            reporter=self.reporter,
            writer=writer,
            live=ctx.live,
            clock=self.clock,
            get_cfg=get_cfg,
            read_signal=ctx.read_signal,
            emit=self._emit,
            write_enabled=self._write_enabled,
            log=self.log,
        )
        if self.store.problem:
            self._emit(Event(None, "config", f"Стан плагіна: {self.store.problem}", level="warn"))
        self.executor.recover()
        await self._load_config(first=True)

    def _emit(self, ev: Event) -> None:
        if self.reporter is not None:
            self.reporter.add_event(ev.to_dict(self.clock.now()))

    def _writer_event(self, kind: str, text: str, level: str, signal: str | None) -> None:
        self._emit(Event(None, kind, text, signal=signal, level=level))

    def _on_report(self, etag: str | None, version: int | None) -> None:
        """Відповідь API-25: інший `config_etag` → негайно перечитати конфіг (SPEC 7.4)."""
        if etag and self.cfg is not None and etag != self.cfg.etag:
            self._config_wake.set()

    # --- конфіг (API-24) ------------------------------------------------------------------------------
    async def _load_config(self, *, first: bool = False) -> None:
        odoo, now = self.ctx.odoo, self.clock.now()
        raw: dict | None = None
        version: int | None = None
        try:
            if odoo is None:
                raise OdooError(None, "odoo client unavailable")
            raw, version = await odoo.automation_config(self.cfg.etag if self.cfg else None)
            self.odoo_error = None
        except OdooError as exc:
            self.odoo_error = str(exc)
            if self.cfg is None and self.store is not None:
                cached = self.store.cached_config(now)
                if cached is not None:
                    self._apply(cached, cached=True)
            return
        if raw is None:  # 304: зміст не змінився; X-Config-Version оновлює лише номер (A-64)
            if version is not None and self.cfg is not None and version != self.cfg.version:
                self.cfg = dataclasses.replace(self.cfg, version=version)
            return
        self._apply(raw)

    def _apply(self, raw: dict[str, Any], *, cached: bool = False) -> None:
        parsed = cfgmod.parse(raw)
        if parsed.errors or parsed.config is None:
            self.config_error = "config invalid: " + "; ".join(parsed.errors[:3])
            self._emit(Event(None, "config", self.config_error, level="warn"))
            return
        old = self.cfg
        self.cfg, self.config_error = parsed.config, None
        if self.engine is not None and self.config_error is None and self.engine.mode == "off" and old is None:
            self.engine.reason = ""
        for text in parsed.events:
            self._emit(Event(None, "config", text, level="warn"))
        for text in parsed.warnings:
            self.log.warning("конфіг: %s", text)
        if old is None or old.version != self.cfg.version:
            self.log.info("config_version %s застосовано", self.cfg.version)
        if cached:
            self._emit(Event(None, "config", "Odoo недоступний: працюємо з кешованого конфігу", level="warn"))
        elif self.store is not None:
            self.store.cache_config(raw, self.clock.now())
        self._skew(raw)

    def _skew(self, raw: dict[str, Any]) -> None:
        try:
            skew = (parse_iso(str(raw["server_time"])) - self.clock.now()).total_seconds()
        except (KeyError, ValueError):
            return
        if self.executor is not None:
            self.executor.skew_s = skew if abs(skew) > SKEW_WARN_S else 0.0
        if abs(skew) > SKEW_WARN_S:
            self._emit(Event(None, "config", f"Розбіжність годинників із сервером {skew:.0f} с", level="warn"))

    # --- життєвий цикл -------------------------------------------------------------------------------------
    async def subscribe(self) -> None:
        self.tasks = [
            asyncio.create_task(self._config_loop(), name="energy_ctl:config"),
            asyncio.create_task(self._engine_loop(), name="energy_ctl:engine"),
            asyncio.create_task(self._report_loop(), name="energy_ctl:report"),
            asyncio.create_task(self._heartbeat_loop(), name="energy_ctl:heartbeat"),
        ]

    async def _sleep(self, total: float, wake: asyncio.Event | None = None) -> None:
        """Сон секундними зрізами; `wake` перериває його достроково."""
        left = total
        while left > 0:
            if wake is not None and wake.is_set():
                wake.clear()
                return
            step = min(1.0, left)
            await self.clock.sleep(step)
            left -= step

    async def _config_loop(self) -> None:
        backoff = 1.0
        while True:
            try:
                await self._load_config()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                self.log.exception("config loop")
            if self.cfg is None:
                await self._sleep(backoff)
                backoff = min(60.0, backoff * 2)
            else:
                backoff = 1.0
                await self._sleep(self._poll_s(), self._config_wake)

    async def _engine_loop(self) -> None:
        assert self.engine is not None and self.executor is not None
        while True:
            t0 = self.clock.monotonic()
            try:
                await self.engine.tick()
                await self.executor.tick()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                self.log.exception("тік рушія")
            spent = self.clock.monotonic() - t0
            if spent > self._tick_s():
                self.log.warning("тік тривав %.2f с > %.1f с", spent, self._tick_s())
            await self.clock.sleep(max(0.0, self._tick_s() - spent))

    async def _report_loop(self) -> None:
        assert self.reporter is not None
        while True:
            try:
                if self.reporter.due(REPORT_S):
                    await self.reporter.flush(self.clock.now())
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                self.log.exception("reporter")
            await self.clock.sleep(0.25)

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                self.beat()
            except Exception:  # noqa: BLE001
                self.log.exception("heartbeat")
            await self.clock.sleep(HEARTBEAT_S)

    def beat(self) -> None:
        """`energy_control/auto/heartbeat` (лічильник тіків) і стани сценаріїв при зміні (SPEC 8.1.3)."""
        assert self.engine is not None
        ts = self.clock.now()
        self.ctx.emit(Reading(HEARTBEAT_SIGNAL, ts, value=float(self.engine.ticks)))
        for code in CARDS:
            st = self.engine.states.get(code)
            if st is not None and self._beat_states.get(code) != st["state"]:
                self._beat_states[code] = st["state"]
                self.ctx.emit(Reading(f"energy_control/auto/{code}/state", ts, text=st["state"]))

    async def call(self, signal: SignalCfg, payload: dict) -> dict:
        if signal.code != INTENT_SIGNAL:
            raise NotSupported(f"call: {signal.code}")
        if self.executor is None:
            raise ConnectError("energy_ctl: плагін не підключено")
        return await self.executor.accept(payload)

    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        raise NotSupported("write")

    def health(self) -> Health:
        eng, now = self.engine, self.clock.now()
        stats: dict[str, Any] = {}
        if eng is not None:
            stats = {
                "ticks": eng.ticks,
                "tick_ms_p95": eng.tick_p95(),
                "writes_last_min": eng.writer.writes_last_min(now),
                "intents_total": self.executor.intents_total if self.executor else 0,
                "blocked_total": self.executor.blocked_total if self.executor else 0,
                "config_version": self.cfg.version if self.cfg else 0,
                "mode": eng.mode,
            }
        if eng is not None and eng.last_tick_at is not None:
            age = now.timestamp() - eng.last_tick_at
            if age > 3 * self._tick_s():
                return Health("error", f"рушій не тікає {age:.0f} с", stats=stats)
        if self.cfg is None and self.config_error:
            return Health("error", self.config_error, stats=stats)
        return Health("online", self.config_error, stats=stats)

    async def disconnect(self) -> None:
        for t in self.tasks:
            t.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks = []
        if self.executor is not None:
            await self.executor.stop()
        if self.store is not None:
            self.store.save(self.clock.now())  # у пристрої нічого не пишемо: безпеку дають сторожові таймери (R-53 №7)
        if EnergyCtlPlugin._active is self:
            EnergyCtlPlugin._active = None
