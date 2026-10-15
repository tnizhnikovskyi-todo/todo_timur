"""`GenericAdapter` (§8.4 п. 4): GET path -> json_path -> Reading; база для адаптерів woodstore і cutopt."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from collector.core.errors import NotSupported, PollError
from collector.core.types import Reading, SignalCfg
from collector.util import jsonpath

if TYPE_CHECKING:
    from .rest_vendor import RestVendorPlugin


class GenericAdapter:
    def __init__(self, plugin: RestVendorPlugin) -> None:
        self.plugin = plugin

    async def start(self) -> None:
        """Фонові задачі адаптера (у generic — немає)."""

    async def stop(self) -> None:
        """Зупинка фонових задач."""

    async def command(self, signal: SignalCfg, payload: dict) -> dict:
        raise NotSupported("call")

    async def on_response(self, method: str, path: str, query: dict, body: Any) -> None:
        """Хук після успішної відповіді групи (woodstore: подія `status`)."""

    async def poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        groups: dict[tuple[str, str, str], list[SignalCfg]] = {}
        for sig in signals:
            addr = sig.address
            key = (addr.get("method", "GET"), addr["path"], json.dumps(addr.get("query") or {}, sort_keys=True))
            groups.setdefault(key, []).append(sig)
        out: list[Reading] = []
        for (method, path, query_json), sigs in groups.items():
            query = json.loads(query_json)
            body = await self._fetch(method, path, query)
            await self.on_response(method, path, query, body)
            now = self.plugin.clock.now()
            for sig in sigs:
                reading = self.to_reading(sig, body, now)
                if reading is not None:
                    out.append(reading)
        return out

    async def _fetch(self, method: str, path: str, query: dict) -> Any:
        from .rest_vendor import NetError

        try:
            resp = await self.plugin.request(method, path, params=query or None)
        except NetError as exc:
            raise PollError(str(exc)) from exc
        if resp.status >= 400:
            raise PollError(f"HTTP {resp.status} {path}")
        try:
            return resp.json()
        except ValueError as exc:
            raise PollError(f"bad json {path}") from exc

    @staticmethod
    def to_reading(sig: SignalCfg, body: Any, now: Any) -> Reading | None:
        addr = sig.address
        value = jsonpath.get(addr["json_path"], body, None) if addr.get("json_path") else body
        if value is None:
            if "default" not in addr:
                return None
            value = addr["default"]
        mapping = addr.get("map") or {}
        if isinstance(value, bool):
            return Reading(code=sig.code, ts=now, value=1.0 if value else 0.0, text=mapping.get("1" if value else "0"))
        if isinstance(value, int | float):
            key = str(int(value)) if float(value) == int(value) else str(value)
            return Reading(code=sig.code, ts=now, value=float(value), text=mapping.get(key))
        if isinstance(value, str):
            return Reading(code=sig.code, ts=now, value=None, text=mapping.get(value, value)[:64])
        return None
