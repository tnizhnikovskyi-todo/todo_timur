"""Цикл команд: GET commands -> plugin.write()/call() -> результат через буфер (R-18, SPEC §8.4)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from collector.core.buffer import Buffer
from collector.core.config import Settings
from collector.core.errors import NotSupported, WriteError, WriteRefused
from collector.core.live import LiveCache
from collector.core.odoo_client import OdooClient, OdooError, flush_results
from collector.core.scheduler import apply_signal_scale
from collector.core.types import Command, CommandResult, Reading
from collector.util.timeutil import Clock, SystemClock

log = logging.getLogger("collector.commands")

CALL_TIMEOUT_S = 10.0
MAX_DATA_BYTES = 64 * 1024
RESULT_MAX_CHARS = 256


class CommandLoop:
    def __init__(
        self,
        client: OdooClient,
        registry: Any,
        buffer: Buffer,
        settings: Settings,
        *,
        clock: Clock | None = None,
        metrics: Any = None,
        call_timeout_s: float = CALL_TIMEOUT_S,
        live: LiveCache | None = None,
    ) -> None:
        self.client = client
        self.registry = registry
        self.buffer = buffer
        self.settings = settings
        self.clock: Clock = clock or SystemClock()
        self.metrics = metrics
        self.call_timeout_s = call_timeout_s
        self.live = live

    async def poll_once(self) -> int:
        """Один цикл. Нічого не робить (і не звертається до Odoo), якщо запис вимкнено на боці колектора."""
        if not self.settings.write_enabled:
            return 0
        if self.registry.write_enabled:
            try:
                commands, odoo_write = await self.client.commands()
            except OdooError as exc:
                log.warning("commands poll failed: %s", exc)
                commands, odoo_write = [], True
            if odoo_write:
                for cmd in commands:
                    await self.process(cmd)
        await flush_results(self.client, self.buffer)
        return 0

    async def run(self) -> None:
        while True:
            await self.poll_once()
            await self.clock.sleep(self.settings.commands_poll_s)

    async def process(self, cmd: Command) -> CommandResult:
        res = await self._execute(cmd)
        if self.metrics is not None:
            self.metrics.commands.labels(res.state).inc()
        log.info("command %s -> %s", cmd.id, res.state, extra={"cmd": cmd.id, "code": cmd.code})
        await self.buffer.put_result(res)
        return res

    def _failed(self, cmd: Command, error: str) -> CommandResult:
        return CommandResult(id=cmd.id, state="failed", ts=self.clock.now(), error=error)

    async def _execute(self, cmd: Command) -> CommandResult:
        found = self.registry.find_signal(cmd.code)
        if found is None:
            return self._failed(cmd, "unknown signal")
        source, signal = found
        if not source.write_enabled:
            return self._failed(cmd, "source write disabled")
        if not signal.write_enabled:
            return self._failed(cmd, "signal write disabled")
        if cmd.expires_at <= self.clock.now():
            return self._failed(cmd, "expired")
        plugin = self.registry.plugins.get(source.code)
        if plugin is None:
            return self._failed(cmd, f"source {source.code} unavailable")
        pulse_ms = (
            (signal.address.get("write") or {}).get("pulse_ms", 0)
            if isinstance(signal.address.get("write"), dict)
            else 0
        )
        timeout = self.call_timeout_s + float(pulse_ms or 0) / 1000.0
        try:
            if cmd.payload is None:
                text = await asyncio.wait_for(plugin.write(signal, cmd.value, cmd.text), timeout)
                return CommandResult(id=cmd.id, state="done", ts=self.clock.now(), result=str(text))
            data = await asyncio.wait_for(plugin.call(signal, cmd.payload), timeout)
        except NotSupported:
            if cmd.payload is None:
                return self._failed(cmd, f"write not supported by {source.type}")
            return self._failed(cmd, f"call not supported by {source.type}")
        except TimeoutError:
            return self._failed(cmd, "timeout")
        except Exception as exc:  # noqa: BLE001 - WriteError та будь-які інші помилки плагіна
            return self._failed(cmd, str(exc) or type(exc).__name__)
        try:
            if not isinstance(data, dict):
                raise TypeError
            dumped = json.dumps(data, ensure_ascii=False, sort_keys=True)
            if len(dumped.encode("utf-8")) > MAX_DATA_BYTES:
                raise ValueError
        except (TypeError, ValueError):
            return self._failed(cmd, "call returned invalid data")
        return CommandResult(id=cmd.id, state="done", ts=self.clock.now(), result=dumped[:RESULT_MAX_CHARS], data=data)

    # --- C-40 (W2): пряме читання/запис для плагінів, яким потрібні чужі сигнали (energy_ctl) ---
    async def read_now(self, code: str) -> Reading | None:
        """Разове читання сигналу через `plugin.poll([signal])`: масштаб ядра, оновлення `LiveCache`; у буфер не пише.

        `None` — сигналу немає, джерело недоступне/push, показань немає або опитування не вдалося (`call_timeout_s`).
        """
        found = self.registry.find_signal(code)
        if found is None:
            return None
        source, signal = found
        plugin = self.registry.plugins.get(source.code)
        if plugin is None or plugin.push_mode:
            return None
        try:
            readings = await asyncio.wait_for(plugin.poll([signal]), self.call_timeout_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - таймаут/помилка пристрою: для викликача це «немає значення»
            log.debug("read_now %s failed: %s", code, exc or type(exc).__name__)
            return None
        readings = apply_signal_scale(readings, {signal.code: signal})
        if self.live is not None:
            self.live.update(readings)
        return next((r for r in readings if r.code == code), None)

    async def write_direct(
        self, code: str, value: float | None = None, text: str | None = None, *, expires_at: datetime | None = None
    ) -> str:
        """Запис сигналу без черги Odoo й без запису в буфер результатів: ті самі запобіжники, що в `_execute`.

        Відмова до звернення до пристрою — `WriteRefused(reason)`; таймаут — `WriteError("timeout")`;
        помилки плагіна пробрасуються як є.
        """
        found = self.registry.find_signal(code)
        if found is None:
            raise WriteRefused("unknown signal")
        source, signal = found
        if not source.write_enabled:
            raise WriteRefused(f"source write disabled: {source.code}")
        if not signal.write_enabled:
            raise WriteRefused(f"signal write disabled: {code}")
        if not self.registry.write_enabled:
            raise WriteRefused("write disabled by registry")
        if not self.settings.write_enabled:
            raise WriteRefused("write disabled in collector (F3D_WRITE_ENABLED)")
        if expires_at is not None and expires_at <= self.clock.now():
            raise WriteRefused("expired")
        plugin = self.registry.plugins.get(source.code)
        if plugin is None:
            raise WriteRefused(f"source {source.code} unavailable")
        write = signal.address.get("write")
        pulse_ms = write.get("pulse_ms", 0) if isinstance(write, dict) else 0
        timeout = self.call_timeout_s + float(pulse_ms or 0) / 1000.0
        try:
            return str(await asyncio.wait_for(plugin.write(signal, value, text), timeout))
        except TimeoutError:
            raise WriteError("timeout") from None
