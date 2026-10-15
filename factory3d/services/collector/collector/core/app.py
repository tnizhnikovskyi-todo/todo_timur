"""Збирання компонентів колектора, запуск і graceful shutdown (SPEC §8.1.1)."""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import inspect
import logging
import random
import signal
from collections.abc import Callable
from typing import Any

from collector.core.allowlist import Allowlist
from collector.core.buffer import Buffer
from collector.core.commands import CommandLoop
from collector.core.config import Settings, resolve_secret
from collector.core.metrics import Metrics, MetricsServer
from collector.core.odoo_client import OdooClient, Pusher, StatusReporter
from collector.core.registry import Registry
from collector.core.scheduler import Emitter, Scheduler
from collector.core.types import SignalCfg, SourceCfg
from collector.plugins.base import PluginContext
from collector.util.timeutil import Clock, SystemClock

log = logging.getLogger("collector.app")

FLUSH_TIMEOUT_S = 10.0
PUSH_MAX_LIMIT = 2000
MAINTENANCE_S = 60.0


class Collector:
    def __init__(
        self, settings: Settings, clock: Clock | None = None, rand: Callable[[], float] = random.random
    ) -> None:
        self.settings = settings
        self.clock: Clock = clock or SystemClock()
        self.metrics = Metrics(self.clock)
        self.buffer = Buffer(settings.buffer_dir / "buffer.sqlite", settings.buffer_max_mb, self.clock, self.metrics)
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
        self.emitter = Emitter(self.buffer, self._signals, self.metrics)
        self.registry = Registry(self.client, settings, self._make_ctx, self.clock, self.metrics)
        self.scheduler = Scheduler(self.buffer, self.registry, self.metrics, self.clock, rand)
        self.pusher = Pusher(
            self.client,
            self.buffer,
            push_max=settings.push_max,
            push_interval_s=settings.push_interval_s,
            registry=self.registry,
            metrics=self.metrics,
            clock=self.clock,
            on_read_enabled=lambda v: self.registry.set_flags(v),
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
        )
        self.commands = CommandLoop(
            self.client, self.registry, self.buffer, settings, clock=self.clock, metrics=self.metrics
        )
        self.metrics_server = MetricsServer(self.metrics, settings.metrics_port)
        self.registry.listeners.append(self._on_config)
        self.http_push: Any = None
        self._tasks: list[asyncio.Task] = []
        self._stop = asyncio.Event()

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
        )

    async def _on_config(self) -> None:
        c = self.registry.collector
        self.pusher.push_interval_s = c.get("push_interval_s") or self.settings.push_interval_s
        self.pusher.push_max = min(PUSH_MAX_LIMIT, c.get("push_max") or self.settings.push_max)
        self.status.interval_s = c.get("status_interval_s") or self.settings.status_interval_s

    async def _maintenance(self) -> None:
        while True:
            await self.clock.sleep(MAINTENANCE_S)
            await self.buffer.enforce_limit()
            self.metrics.buffer_rows.set(await self.buffer.count())

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
        self.metrics_server.rows = lambda: int(self.metrics.buffer_rows._value.get())
        await self.metrics_server.start()
        self.metrics.up.set(1)
        await self.buffer.open()
        await self._start_http_push()
        await self.registry.load()
        coros = [
            self.registry.run_refresh(),
            self.pusher.run(),
            self.status.run(),
            self.emitter.run(),
            self._maintenance(),
        ]
        if self.settings.write_enabled:
            coros.append(self.commands.run())
        self._tasks = [asyncio.create_task(c) for c in coros]
        log.info("collector %s started", self.settings.collector_code)

    async def stop(self) -> None:
        self.metrics.up.set(0)
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        await self.scheduler.stop()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self._flush(), FLUSH_TIMEOUT_S)
        if self.http_push is not None and hasattr(self.http_push, "stop"):
            await self.http_push.stop()
        await self.registry.close()
        await self.buffer.close()
        await self.client.close()
        await self.metrics_server.stop()

    async def _flush(self) -> None:
        await self.emitter.flush()
        while await self.pusher.push_once() == "ok":
            pass

    async def run(self) -> int:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, self._stop.set)
        await self.start()
        await self._stop.wait()
        log.info("shutting down")
        await self.stop()
        return 0
