"""Інтерфейс плагіна джерела (SPEC §8.3.2, CT-02)."""

from __future__ import annotations

import logging
from abc import ABC
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from collector.core.errors import NotSupported
from collector.core.types import Health, PushEvent, Reading, SignalCfg, SourceCfg

if TYPE_CHECKING:  # pragma: no cover
    from collector.core.live import LiveCache
    from collector.core.odoo_client import OdooClient
    from collector.util.timeutil import Clock


@dataclass
class PluginContext:
    """Що плагін отримує від ядра."""

    settings: Any  # Settings (лише читання)
    secrets: Callable[[str], str]  # resolve("F3D_MQTT_PASSWORD") -> значення або KeyError
    allowlist: Callable[[str], None]  # None або AllowlistDenied
    emit: Callable[[Reading], None]  # push-протоколи: ядро множить value на signal.scale (R-02)
    emit_event: Callable[[PushEvent], None]  # для http_push
    metrics: Any  # Metrics
    log: logging.Logger  # "collector.plugin.<type>.<source>"
    # C-40 (W2): адитивні поля для плагінів, що читають/пишуть чужі сигнали (energy_ctl); старі плагіни їх не чіпають
    live: LiveCache | None = None  # останні показання (після масштабу ядра)
    write_signal: Callable[..., Awaitable[str]] | None = None  # CommandLoop.write_direct
    read_signal: Callable[[str], Awaitable[Reading | None]] | None = None  # CommandLoop.read_now(code)
    odoo: OdooClient | None = None
    clock: Clock | None = None
    state_dir: Path | None = None  # каталог settings.state_file


class SourcePlugin(ABC):
    type: ClassVar[str]
    version: ClassVar[str] = "0.1.0"
    address_schema: ClassVar[dict]
    params_schema: ClassVar[dict]
    push_mode: ClassVar[bool] = False  # True -> ядро викликає subscribe(), poll() не планується

    def __init__(self, source: SourceCfg, ctx: PluginContext) -> None:
        self.source = source
        self.ctx = ctx

    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        """Помилки схем params/address усіх сигналів; порожній список = ок. Викликається до connect()."""
        return []

    async def connect(self) -> None:
        """Відкрити з'єднання; перед мережевим викликом — ctx.allowlist(host). Може кидати ConnectError."""

    async def disconnect(self) -> None: ...

    async def poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        """Прочитати групу сигналів з однаковим period_s; часткові помилки — Reading(q='bad')."""
        raise NotSupported("poll")

    async def subscribe(self) -> None:
        """Для push_mode: запустити підписки; показання віддаються через ctx.emit(). Повертається одразу."""
        raise NotSupported("subscribe")

    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        """Записати значення; повертає рядок результату. Ядро перевіряє прапори до виклику."""
        raise NotSupported("write")

    async def call(self, signal: SignalCfg, payload: dict) -> dict:
        """CR-01 (X-03): команда-виклик; повертає JSON-dict <= 64 КБ. Ті самі передумови, що write()."""
        raise NotSupported("call")

    def health(self) -> Health:
        return Health(state="online")
