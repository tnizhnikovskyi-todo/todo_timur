"""Збирання компонентів колектора, запуск і graceful shutdown (SPEC §8.1.1)."""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import inspect
import logging
import random
import signal
import sqlite3
import threading
from collections.abc import Awaitable, Callable
from typing import Any

from collector.core.allowlist import Allowlist
from collector.core.buffer import Buffer
from collector.core.commands import CommandLoop
from collector.core.config import Settings, resolve_secret
from collector.core.live import LiveCache
from collector.core.metrics import Metrics, MetricsServer
from collector.core.odoo_client import OdooClient, Pusher, StatusReporter
from collector.core.registry import Registry
from collector.core.scheduler import Emitter, Scheduler
from collector.core.types import SignalCfg, SourceCfg
from collector.plugins.base import PluginContext
from collector.util.tasks import cancel_tasks, run_bounded
from collector.util.timeutil import Clock, SystemClock

log = logging.getLogger("collector.app")

# Graceful shutdown вкладається в SHUTDOWN_TIMEOUT_S = сума фаз; завислі задачі/транспорти покидаються (з логом ERROR)
SHUTDOWN_CANCEL_S = 3.0  # скасування задач ядра й опитувань
SHUTDOWN_FLUSH_S = 3.0  # скидання Emitter у буфер і кілька останніх пакетів в Odoo
SHUTDOWN_CLOSE_S = 2.0  # `disconnect()` плагінів (паралельно)
SHUTDOWN_FINAL_S = 2.0  # приймач http_push, буфер, клієнт Odoo, сервер метрик
SHUTDOWN_TIMEOUT_S = SHUTDOWN_CANCEL_S + SHUTDOWN_FLUSH_S + SHUTDOWN_CLOSE_S + SHUTDOWN_FINAL_S
HARD_EXIT_S = SHUTDOWN_TIMEOUT_S + 5.0  # від початку зупинки: якщо процес усе ще живий (потоки бібліотек) — _exit
SHUTDOWN_PUSHES = 5  # не більше пакетів при зупинці: рестарт не впирається в 429 (ліміт Odoo 60/хв)
PUSH_MAX_LIMIT = 2000
MAINTENANCE_S = 60.0
RESTART_MAX_S = 30.0


class Collector:
    def __init__(
        self,
        settings: Settings,
        clock: Clock | None = None,
        rand: Callable[[], float] = random.random,
        hard_exit: Callable[[int], None] | None = None,
    ) -> None:
        self.settings = settings
        self.hard_exit = hard_exit  # CLI: os._exit; страховка, якщо після `stop()` процес не завершується
        self.clock: Clock = clock or SystemClock()
        self.metrics = Metrics(self.clock)
        self.buffer = Buffer(settings.buffer_dir / "buffer.sqlite", settings.buffer_max_mb, self.clock, self.metrics)
        self.metrics.buffer_rows.set_function(lambda: self.buffer.rows)  # завжди справжня кількість, не «останнє set()»
        self.allowlist = Allowlist(settings.allow_hosts, settings.odoo_url, self.metrics)
        self.client = OdooClient(
            settings.odoo_url,
            settings.collector_token,
            collector=settings.collector_code,
            clock=self.clock,
            metrics=self.metrics,
            skew_warn_s=settings.clock_skew_warn_s,
            ca=settings.odoo_ca,
        )
        self.live = LiveCache(self.clock)
        self.emitter = Emitter(self.buffer, self._signals, self.metrics, live=self.live)
        self.registry = Registry(self.client, settings, self._make_ctx, self.clock, self.metrics)
        self.scheduler = Scheduler(self.buffer, self.registry, self.metrics, self.clock, rand, live=self.live)
        self.pusher = Pusher(
            self.client,
            self.buffer,
            push_max=settings.push_max,
            push_interval_s=settings.push_interval_s,
            registry=self.registry,
            metrics=self.metrics,
            clock=self.clock,
            on_read_enabled=lambda v: self.registry.set_flags(v),
            stale_after_s=settings.push_stale_s,
            backlog_gap_s=settings.push_backlog_gap_s,
        )
        self.status = StatusReporter(
            self.client,
            self.registry,
            self.buffer,
            self.scheduler,
            interval_s=settings.status_interval_s,
            clock=self.clock,
            metrics=self.metrics,
            on_flags=self.registry.set_flags,
            pusher=self.pusher,
        )
        self.commands = CommandLoop(
            self.client, self.registry, self.buffer, settings, clock=self.clock, metrics=self.metrics, live=self.live
        )
        self.metrics_server = MetricsServer(self.metrics, settings.metrics_port, rows=lambda: self.buffer.rows)
        self.registry.listeners.append(self._on_config)
        self.http_push: Any = None
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()
        self._stopped_ok = False

    def _signals(self) -> dict[str, SignalCfg]:
        return {code: sg for code, (_s, sg) in self.registry.signal_index.items()}

    def _make_ctx(self, source: SourceCfg) -> PluginContext:
        return PluginContext(
            settings=self.settings,
            secrets=resolve_secret,
            allowlist=self.allowlist.check,
            emit=self.emitter.emit,
            emit_event=self.emitter.emit_event,
            metrics=self.metrics,
            log=logging.getLogger(f"collector.plugin.{source.type}.{source.code}"),
            live=self.live,
            write_signal=self.commands.write_direct,
            read_signal=self.commands.read_now,
            odoo=self.client,
            clock=self.clock,
            state_dir=self.settings.state_file.parent,
        )

    async def _on_config(self) -> None:
        c = self.registry.collector
        # конфіг Odoo (колектор у `td.collector`) має пріоритет над F3D_PUSH_INTERVAL_S / F3D_PUSH_MAX;
        # env — лише запасні значення, поки конфіг не отримано або в ньому порожньо
        self.pusher.configure(
            c.get("push_interval_s") or self.settings.push_interval_s,
            min(PUSH_MAX_LIMIT, c.get("push_max") or self.settings.push_max),
        )
        self.status.interval_s = c.get("status_interval_s") or self.settings.status_interval_s

    async def _maintenance_once(self) -> None:
        try:
            await self.buffer.enforce_limit()
            await self.buffer.recount()
        except sqlite3.Error as exc:
            log.warning("buffer maintenance failed (%s), will retry in %.0f s", exc, MAINTENANCE_S)

    async def _maintenance(self) -> None:
        while True:
            await self.clock.sleep(MAINTENANCE_S)
            await self._maintenance_once()

    async def _supervised(self, name: str, factory: Callable[[], Awaitable[None]]) -> None:
        """Фонова задача не вмирає мовчки: виняток -> лог і перезапуск з бекофом (1, 2, 4 ... 30 с)."""
        delay = 1.0
        while True:
            started = self.clock.monotonic()
            try:
                await factory()
                return
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - будь-яка помилка задачі -> перезапуск
                log.exception("task %s crashed, restarting in %.0f s", name, delay)
            if self.clock.monotonic() - started > 60:
                delay = 1.0
            await self.clock.sleep(delay)
            delay = min(RESTART_MAX_S, delay * 2)

    async def _start_http_push(self) -> None:
        """Приймач http_push (W6) підключається, якщо модуль `collector.core.http_push` присутній."""
        try:
            mod = importlib.import_module("collector.core.http_push")
        except ImportError:
            return
        cls = mod.HttpPushServer
        avail = {
            "settings": self.settings,
            "clock": self.clock,
            "buffer": self.buffer,
            "registry": self.registry,
            "metrics": self.metrics,
            "allowlist": self.allowlist,
            "emitter": self.emitter,
        }
        params = inspect.signature(cls).parameters
        self.http_push = cls(**{k: v for k, v in avail.items() if k in params})
        if hasattr(self.http_push, "start"):
            await self.http_push.start()

    async def start(self) -> None:
        await self.metrics_server.start()
        self.metrics.up.set(1)
        await self.buffer.open()
        await self._start_http_push()
        await self.registry.load()
        loops: list[tuple[str, Callable[[], Awaitable[None]]]] = [
            ("registry", self.registry.run_refresh),
            ("pusher", self.pusher.run),
            ("status", self.status.run),
            ("emitter", self.emitter.run),
            ("maintenance", self._maintenance),
        ]
        if self.settings.write_enabled:
            loops.append(("commands", self.commands.run))
        self._tasks = [asyncio.create_task(self._supervised(n, f), name=f"f3d-{n}") for n, f in loops]
        log.info("collector %s started", self.settings.collector_code)

    async def stop(self) -> None:
        """Graceful shutdown не довше `SHUTDOWN_TIMEOUT_S`, навіть якщо опитування/плагіни зависли на з'єднанні з
        пристроєм (reconnect-цикли pymodbus/paho/bacpypes ковтають скасування): кожна фаза обмежена, завислі
        задачі й транспорти покидаються, а те, що можна скинути (буфер, останні пакети), скидається."""
        self.metrics.up.set(0)
        tasks, self._tasks = self._tasks, []
        await asyncio.gather(
            cancel_tasks(tasks, SHUTDOWN_CANCEL_S, "task"),
            self.scheduler.stop(SHUTDOWN_CANCEL_S),
            return_exceptions=True,
        )
        await run_bounded(self._flush(), SHUTDOWN_FLUSH_S, "final flush")
        await run_bounded(self.registry.close(SHUTDOWN_CLOSE_S), SHUTDOWN_CLOSE_S + 0.5, "plugin close")
        final = [self.buffer.close(), self.client.close(), self.metrics_server.stop()]
        if self.http_push is not None and hasattr(self.http_push, "stop"):
            final.append(self.http_push.stop())
        await asyncio.gather(*(run_bounded(c, SHUTDOWN_FINAL_S, "shutdown") for c in final))
        self._stopped_ok = True

    async def _flush(self) -> None:
        await self.emitter.flush()
        for _ in range(SHUTDOWN_PUSHES):
            await self.pusher.backlog_pause()  # цикл відправки щойно міг слати: тримаємо паузу між пакетами
            if await self.pusher.push_once() != "ok" or self.buffer.rows <= 0:
                break

    async def run(self) -> int:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self._stop.set)
        await self.start()
        await self._stop.wait()
        log.info("shutting down")
        self._arm_watchdog()
        await self.stop()
        return 0

    def _arm_watchdog(self) -> None:
        """Страховка: якщо після `stop()` процес не завершується (бібліотечний потік/`to_thread` не відпускає
        інтерпретатор), через `HARD_EXIT_S` від початку зупинки — примусовий вихід."""
        if self.hard_exit is None:
            return
        timer = threading.Timer(HARD_EXIT_S, self._force_exit)
        timer.daemon = True
        timer.start()

    def _force_exit(self) -> None:
        code = 0 if self._stopped_ok else 1
        log.critical("process still alive %.0f s after shutdown started: forced exit (code %d)", HARD_EXIT_S, code)
        if self.hard_exit is not None:
            self.hard_exit(code)
