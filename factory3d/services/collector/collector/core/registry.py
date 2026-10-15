"""Реєстр джерел: API-01, diff за ETag, створення/зупинка плагінів (SPEC §0.3, §8.3.2–§8.3.3)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import timedelta
from importlib.metadata import entry_points
from typing import Any

from collector.core.config import Settings
from collector.core.odoo_client import OdooClient, OdooError
from collector.core.types import Health, SignalCfg, SourceCfg
from collector.plugins.base import PluginContext, SourcePlugin
from collector.util.timeutil import Clock, SystemClock, parse_iso, to_iso_z

log = logging.getLogger("collector.registry")

PLUGIN_GROUP = "factory3d_collector.plugins"
CACHE_MAX_AGE = timedelta(days=7)
LOAD_BACKOFF_MAX = 60.0


def load_plugins() -> dict[str, type[SourcePlugin]]:
    """entry points `factory3d_collector.plugins` -> {type: class}."""
    out: dict[str, type[SourcePlugin]] = {}
    for ep in entry_points(group=PLUGIN_GROUP):
        try:
            out[ep.name] = ep.load()
        except Exception as exc:  # noqa: BLE001 - зламаний плагін не валить процес
            log.warning("plugin %s failed to load: %s", ep.name, exc)
    return out


def parse_config(data: dict) -> list[SourceCfg]:
    """API-01 `sources[]` -> SourceCfg (frozen; порівнюються за значенням)."""
    out = []
    for s in data.get("sources") or []:
        code = s["code"]
        signals = tuple(
            SignalCfg(
                code=g["code"], kind=g.get("kind", "gauge"), unit=g.get("unit", ""), period_s=int(g.get("period_s", 10)),
                scale=float(g.get("scale", 1.0)), write_enabled=bool(g.get("write_enabled", False)),
                states=g.get("states"), decimals=int(g.get("decimals", 2)), address=g.get("address") or {},
                source_code=code)
            for g in s.get("signals") or []
        )
        out.append(SourceCfg(
            code=code, type=s["type"], read_enabled=bool(s.get("read_enabled", True)),
            write_enabled=bool(s.get("write_enabled", False)), params=s.get("params") or {}, signals=signals))
    return out


class Registry:
    def __init__(
        self,
        client: OdooClient,
        settings: Settings,
        ctx_factory: Callable[[SourceCfg], PluginContext],
        clock: Clock | None = None,
        metrics: Any = None,
        plugin_classes: dict[str, type[SourcePlugin]] | None = None,
    ) -> None:
        self.client = client
        self.settings = settings
        self.ctx_factory = ctx_factory
        self.clock: Clock = clock or SystemClock()
        self.metrics = metrics
        self.plugin_classes = load_plugins() if plugin_classes is None else plugin_classes
        self.etag: str | None = None
        self.read_enabled = True
        self.write_enabled = True  # відсутній у конфігурації -> дозволяє Odoo вирішувати (API-06 порожній)
        self.collector: dict = {}
        self.params: dict = {}
        self.sources: dict[str, SourceCfg] = {}
        self.plugins: dict[str, SourcePlugin] = {}
        self.errors: dict[str, Health] = {}
        self.connected: set[str] = set()
        self.signal_index: dict[str, tuple[SourceCfg, SignalCfg]] = {}
        self.listeners: list[Callable[[], Awaitable[None]]] = []
        self._built: dict[str, SourceCfg] = {}
        self._lock = asyncio.Lock()

    # --- завантаження ---
    async def load(self) -> None:
        """Перший запуск: API-01; при недоступності Odoo — кеш (≤ 7 діб), інакше очікування з бекофом."""
        backoff = 1.0
        while True:
            try:
                data = await self.client.config(None)
                if data is not None:
                    self._save_cache(data)
                    break
            except OdooError as exc:
                log.warning("Odoo config unavailable: %s", exc)
            cached = self._load_cache()
            if cached is not None:
                log.warning("using cached configuration %s", self.settings.state_file)
                data = cached
                break
            await self.clock.sleep(backoff)
            backoff = min(LOAD_BACKOFF_MAX, backoff * 2)
        async with self._lock:
            await self._apply(data)

    async def refresh(self) -> bool:
        """Перечитує API-01 з If-None-Match; True, якщо конфігурація змінилась і застосована."""
        async with self._lock:
            try:
                data = await self.client.config(self.etag)
            except OdooError as exc:
                log.warning("config refresh failed: %s", exc)
                return False
            if data is None:
                return False
            self._save_cache(data)
            await self._apply(data)
            return True

    async def run_refresh(self) -> None:
        while True:
            interval = self.collector.get("config_poll_s") or self.settings.config_poll_s
            await self.clock.sleep(interval)
            await self.refresh()

    async def set_flags(self, read_enabled: bool, write_enabled: bool | None = None) -> None:
        async with self._lock:
            changed = read_enabled != self.read_enabled
            self.read_enabled = read_enabled
            if write_enabled is not None:
                self.write_enabled = write_enabled
            if changed:
                await self._reconcile()

    # --- кеш ---
    def _save_cache(self, data: dict) -> None:
        path = self.settings.state_file
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"saved_at": to_iso_z(self.clock.now()), "config": data}), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            log.warning("cannot write config cache: %s", exc)

    def _load_cache(self) -> dict | None:
        path = self.settings.state_file
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            saved = parse_iso(raw["saved_at"])
            config = raw["config"]
        except (OSError, ValueError, KeyError, TypeError):
            return None
        if self.clock.now() - saved > CACHE_MAX_AGE or not isinstance(config, dict):
            return None
        return config  # type: ignore[no-any-return]

    # --- застосування ---
    async def _apply(self, data: dict) -> None:
        self.etag = data.get("etag") or data.get("config_etag")
        self.read_enabled = bool(data.get("read_enabled", True))
        self.write_enabled = bool(data.get("write_enabled", True))
        self.collector = data.get("collector") or {}
        self.params = data.get("params") or {}
        self.sources = {s.code: s for s in parse_config(data)}
        if self.metrics is not None and self.etag:
            self.metrics.config_etag_info.clear()
            self.metrics.config_etag_info.labels(self.etag).set(1)
        await self._reconcile()

    async def _reconcile(self) -> None:
        active = {c: s for c, s in self.sources.items() if s.read_enabled and self.read_enabled}
        for code in list(self._built):
            if code not in active or active[code] != self._built[code]:
                await self._stop_source(code)
        for code in list(self.errors):
            if code not in self.sources:
                self.errors.pop(code)
        for code, src in active.items():
            if code not in self._built:
                await self._start_source(src)
        self.signal_index = {sg.code: (s, sg) for s in self.sources.values() for sg in s.signals}
        for cb in self.listeners:
            await cb()

    async def _stop_source(self, code: str) -> None:
        plugin = self.plugins.pop(code, None)
        self._built.pop(code, None)
        self.errors.pop(code, None)
        was_connected = code in self.connected
        self.connected.discard(code)
        if self.metrics is not None:
            self.metrics.forget_source(code)
        if plugin is not None and was_connected:
            try:
                await plugin.disconnect()
            except Exception as exc:  # noqa: BLE001
                log.warning("disconnect %s failed: %s", code, exc)

    async def _start_source(self, src: SourceCfg) -> None:
        code = src.code
        self._built[code] = src
        cls = self.plugin_classes.get(src.type)
        if cls is None:
            log.warning("plugin %s not installed (source %s)", src.type, code)
            self._set_error(src, f"plugin {src.type} not installed")
            return
        try:
            errs = cls.validate(src)
        except Exception as exc:  # noqa: BLE001
            errs = [str(exc)]
        if errs:
            self._set_error(src, "schema: " + "; ".join(errs))
            return
        for key, ref in src.params.items():
            if key.endswith("_ref") and isinstance(ref, str) and ref and ref not in os.environ:
                self._set_error(src, f"secret {ref} not set")
                return
        try:
            self.plugins[code] = cls(src, self.ctx_factory(src))
        except Exception as exc:  # noqa: BLE001 - TypeError для абстрактних плагінів тощо
            self._set_error(src, f"plugin init failed: {exc}")
            return
        await self.connect_source(code)

    def _set_error(self, src: SourceCfg, message: str) -> None:
        log.warning("source %s: %s", src.code, message, extra={"source": src.code})
        self.errors[src.code] = Health(state="error", error=message)
        if self.metrics is not None:
            self.metrics.set_source(src.code, src.type, "error")

    async def connect_source(self, code: str) -> bool:
        """connect() (і subscribe() для push-плагінів); невдача -> Health error, джерело лишається."""
        plugin = self.plugins.get(code)
        if plugin is None:
            return False
        try:
            await plugin.connect()
            if plugin.push_mode:
                await plugin.subscribe()
        except Exception as exc:  # noqa: BLE001
            self.errors[code] = Health(state="error", error=f"connect: {exc}")
            if self.metrics is not None:
                self.metrics.set_source(code, plugin.source.type, "error")
            return False
        self.connected.add(code)
        self.errors.pop(code, None)
        if self.metrics is not None:
            self.metrics.set_source(code, plugin.source.type, "online")
        return True

    def find_signal(self, code: str) -> tuple[SourceCfg, SignalCfg] | None:
        return self.signal_index.get(code)

    async def close(self) -> None:
        async with self._lock:
            for code in list(self._built):
                await self._stop_source(code)
