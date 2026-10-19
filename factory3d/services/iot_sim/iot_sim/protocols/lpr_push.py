"""P-11: Axis License Plate Verifier — HTTP POST JSON на ``SIM_LPR_PUSH_URL`` (SPEC §8.13.2).

Модель двору (yard) кладе подію ``world.events.emit("yard", ..., payload={"lpr": <dict>})``.
``<dict>`` — або готове тіло Axis (є ``plateText``), або компактний опис, який розгортає
``build_axis_payload``: ``camera`` (CAM-05/06), ``plate``, ``state`` (new|lost), ``booking``
(``{"batch","dock","partner"}`` або ``None``), ``ts`` (необов'язково), ``confidence``, ``truck_type``.
Помилка доставки: 3 повтори через 2/5/10 с, далі подія ``error`` (подія фури не переривається).
Автентифікація (стенд, ST-2): якщо задано ``SIM_LPR_PUSH_TOKEN`` — заголовок ``X-F3D-Token`` (як чекає http_push
колектора,
telemetry SPEC §8.7, ``token_ref`` джерела); порожній токен — без заголовка.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import httpx

from iot_sim.core.events import Event
from iot_sim.core.world import World
from iot_sim.protocols.base import ProtocolServer

log = logging.getLogger("iot_sim.lpr")

RETRY_DELAYS_S = (2.0, 5.0, 10.0)
CAMERAS = {
    "CAM-05": {"geo": "GATE-W", "dir": "in", "serial": "B8A44F000005", "ip": "10.90.2.5", "mac": "B8:A4:4F:00:00:05"},
    "CAM-06": {"geo": "GATE-E", "dir": "out", "serial": "B8A44F000006", "ip": "10.90.2.6", "mac": "B8:A4:4F:00:00:06"},
}
_CYR = str.maketrans("ABCEHIKMOPTXY", "АВСЕНІКМОРТХУ")


def build_axis_payload(spec: dict[str, Any], now: datetime, counter: int = 1) -> dict[str, Any]:
    """Плоский JSON Axis LPV (значення — рядки, як в Axis)."""
    cam = CAMERAS.get(spec.get("camera", "CAM-05"), CAMERAS["CAM-05"])
    code = spec.get("camera", "CAM-05")
    plate = str(spec["plate"])
    ts = spec.get("ts") or now
    ms = int(ts.timestamp() * 1000)
    book = spec.get("booking")
    local = ts.astimezone(now.tzinfo) if now.tzinfo else ts
    return {
        "packetCounter": str(counter),
        "capture_timestamp": str(ms),
        "frame_timestamp": str(ms),
        "capture_ts": str(ms * 1_000_000),
        "datetime": local.strftime("%Y%m%d %H%M%S") + f"{local.microsecond // 1000:03d}",
        "plateText": plate,
        "plateUnicode": plate.translate(_CYR),
        "plateUTF8": plate.translate(_CYR),
        "plateASCII": plate,
        "plateCountry": "UKR",
        "plateISO3166-2": "UA",
        "plateRegion": "",
        "plateRegionCode": "",
        "plateList": "f3d_bookings" if book else "",
        "plateListMode": "allow" if book else "none",
        "plateListDescription": (f"{book.get('batch', '')} {book.get('dock', '')} {book.get('partner', '')}").strip()
        if book
        else "",
        "plateConfidence": f"{float(spec.get('confidence', 0.91234)):.6f}",
        "carState": spec.get("state", "new"),
        "roiID": "1",
        "geotag": {"lat": 50.45, "lon": 30.52},
        "imageType": "plate",
        "plateImageType": "jpeg",
        "plateImageSize": "0",
        "carMoveDirection": cam["dir"],
        "timeProcessing": "41",
        "plateCoordinates": [514, 570, 120, 28],
        "plateCoordinatesRelative": [0, 0, 120, 28],
        "carID": str(spec.get("car_id", counter)),
        "GEOtarget": cam["geo"],
        "imagesURI": [],
        "imageArray": [],
        "imageFile": "",
        "imageFile2": "",
        "profileID": "1",
        "vehicle_info": {"view": "front", "type": spec.get("truck_type", "TRUCK"), "color": "WHITE"},
        "camera_info": {
            "SerialNumber": cam["serial"],
            "ProdShortName": "AXIS P1488-LE",
            "IPAddress": cam["ip"],
            "MACAddress": cam["mac"],
        },
        "sensorProviderID": code,
    }


class LprPusher(ProtocolServer):
    name = "lpr"

    def __init__(
        self,
        world: World,
        *,
        url: str,
        guard: Any = None,
        client: httpx.AsyncClient | None = None,
        token: str = "",
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        delays: tuple[float, ...] = RETRY_DELAYS_S,
    ) -> None:
        self.world, self.url, self.guard = world, url, guard
        self.token = token
        self._client = client
        self._own_client = client is None
        self._sleep = sleep
        self.delays = delays
        self.sent = 0
        self.failed = 0
        self.counter = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._tasks: set[asyncio.Task[Any]] = set()
        self._up = False

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        if self._client is None:
            hooks = [self.guard.httpx_hook] if self.guard is not None else []
            self._client = httpx.AsyncClient(timeout=5.0, event_hooks={"request": hooks})
        self.world.events.subscribe(self._on_event)
        self._up = True

    async def stop(self) -> None:
        self._up = False
        if self._on_event in self.world.events.subscribers:
            self.world.events.subscribers.remove(self._on_event)
        for t in list(self._tasks):
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        if self._client is not None and self._own_client:
            await self._client.aclose()

    def health(self) -> dict[str, Any]:
        return {"proto": self.name, "up": self._up, "sent": self.sent, "failed": self.failed}

    # --- події ------------------------------------------------------------------------
    def _on_event(self, ev: Event) -> None:
        lpr = ev.payload.get("lpr") if isinstance(ev.payload, dict) else None
        if not isinstance(lpr, dict) or self._loop is None:
            return
        self.counter += 1
        body = lpr if "plateText" in lpr else build_axis_payload(lpr, self.world.now(), self.counter)
        self._spawn(body, ev)

    def _spawn(self, body: dict[str, Any], ev: Event) -> None:
        task = asyncio.ensure_future(self.deliver(body, ev.device), loop=self._loop)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-F3D-Token"] = self.token
        return headers

    async def deliver(self, body: dict[str, Any], device: str | None = None) -> bool:
        attempts = (0.0, *self.delays)
        last = ""
        for i, delay in enumerate(attempts):
            if delay:
                await self._sleep(delay)
            try:
                assert self._client is not None
                r = await self._client.post(self.url, json=body, headers=self._headers())
                if r.status_code < 300:
                    self.sent += 1
                    return True
                last = f"HTTP {r.status_code}"
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - будь-яка помилка транспорту -> повтор
                last = f"{type(exc).__name__}: {exc}"
            log.warning("LPR push failed (%s), attempt %d", last, i + 1, extra={"proto": "lpr"})
        self.failed += 1
        self.world.events.emit(
            "error",
            f"LPR не доставлено ({body.get('plateText')}): {last}",
            device=device or body.get("sensorProviderID"),
            payload={"url_failed": True},
        )
        return False
