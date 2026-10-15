"""P-11: автоваги TRUCK-SCALE — SICS-сумісний ASCII по TCP, порт 4001 (SPEC §8.13.3).

Кадр: команда + CR LF; відповідь + CR LF; вага — 10 символів праворуч, одиниця ``kg``, дискретність
20 кг, НПВ 60 000 кг. Вага й стабільність — сигнали ``yard/scale/TRUCK-SCALE/{weight_kg,stable}``
(їх веде модель двору, R-29/R-30). Запис тари (``TA <v> kg``) — лише при ``write_accept``.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from typing import Any

from iot_sim.core.world import World
from iot_sim.protocols.base import ProtocolServer

log = logging.getLogger("iot_sim.sics")

DEVICE = "TRUCK-SCALE"
STEP_KG = 20
MAX_KG = 60000
STABLE_WAIT_S = 5.0
STREAM_PERIOD_S = 0.5
ZERO_BAND_KG = 100
IDENT = {
    "I0": 'I0 B 0 "I0"', "I1": 'I1 A "01" "2.30"', "I2": 'I2 A "AKSIS 60-18 (sim) 60000 kg"',
    "I3": 'I3 A "sim-0.1"', "I4": 'I4 A "AX2026-0001"'}
_TA_SET = re.compile(r"^TA\s+(-?\d+(?:\.\d+)?)\s*kg$", re.IGNORECASE)


def fmt_weight(w: float) -> str:
    return f"{int(round(w / STEP_KG) * STEP_KG):>10} kg"


class SicsServer(ProtocolServer):
    name = "sics"

    def __init__(self, world: World, *, port: int = 4001, host: str = "0.0.0.0",
                 write_accept: bool = False, stable_wait_s: float = STABLE_WAIT_S,
                 stream_period_s: float = STREAM_PERIOD_S) -> None:
        self.world, self.port, self.host = world, port, host
        self.write_accept = write_accept
        self.stable_wait_s = stable_wait_s
        self.stream_period_s = stream_period_s
        self.tare = 0.0
        self.zero_offset = 0.0
        self.requests = 0
        self._server: asyncio.AbstractServer | None = None
        self._tasks: set[asyncio.Task[Any]] = set()

    # --- сигнали ------------------------------------------------------------------------
    def _gross(self) -> float:
        dev = self.world.devices.get(DEVICE)
        s = dev.signals.get("weight_kg") if dev else self.world.signals.get(f"yard/scale/{DEVICE}/weight_kg")
        return float(s.value) if s is not None else 0.0

    def _stable(self) -> bool:
        dev = self.world.devices.get(DEVICE)
        s = dev.signals.get("stable") if dev else None
        return bool(s.value) if s is not None else True

    def _weight(self) -> float:
        return self._gross() - self.zero_offset

    def _wstate(self, w: float) -> str | None:
        """None — норма; ``+``/``-`` — межа діапазону."""
        if w > MAX_KG:
            return "+"
        if w < -STEP_KG * 9:
            return "-"
        return None

    # --- команди ------------------------------------------------------------------------
    async def command(self, line: str) -> str | None:
        """Відповідь на одну команду (``None`` — немає відповіді)."""
        cmd = line.strip()
        up = cmd.upper()
        self.requests += 1
        if up in IDENT:
            return IDENT[up]
        if up == "@":
            return IDENT["I4"]
        w = self._weight()
        edge = self._wstate(w)
        if up == "S":
            if edge:
                return f"S {edge}"
            deadline = asyncio.get_running_loop().time() + self.stable_wait_s
            while not self._stable():
                if asyncio.get_running_loop().time() >= deadline:
                    return "S I"
                await asyncio.sleep(0.05)
            return f"S S {fmt_weight(self._weight())}"
        if up == "SI":
            return f"S {edge}" if edge else f"S {'S' if self._stable() else 'D'} {fmt_weight(w)}"
        if up == "Z":
            if edge:
                return f"Z {edge}"
            if abs(w) > ZERO_BAND_KG:  # на вагах машина
                return "Z I"
            self.zero_offset = self._gross()
            return "Z A"
        if up == "ZI":
            if abs(w) <= ZERO_BAND_KG:
                self.zero_offset = self._gross()
            return f"ZI {'S' if self._stable() else 'D'}"
        if up == "T":
            if edge:
                return f"T {edge}"
            if not self._stable():
                return "T I"
            self.tare = w
            return f"T S {fmt_weight(self.tare)}"
        if up == "TI":
            self.tare = w
            return f"TI {'S' if self._stable() else 'D'} {fmt_weight(self.tare)}"
        if up == "TA":
            return f"TA A {fmt_weight(self.tare)}"
        m = _TA_SET.match(cmd)
        if m:
            if not self.write_accept:
                log.warning("SICS tare write denied", extra={"proto": "sics"})
                return "TA I"
            self.tare = float(m.group(1))
            return f"TA A {fmt_weight(self.tare)}"
        if up.startswith("TA "):  # синтаксично схожа, але не розпізнана установка тари
            return "EL"
        return "ES"

    # --- з'єднання ----------------------------------------------------------------------
    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        stream: asyncio.Task[Any] | None = None

        async def send(text: str) -> None:
            writer.write(text.encode("ascii", "replace") + b"\r\n")
            await writer.drain()

        async def stream_loop() -> None:
            while True:
                w = self._weight()
                edge = self._wstate(w)
                await send(f"S {edge}" if edge else f"S {'S' if self._stable() else 'D'} {fmt_weight(w)}")
                await asyncio.sleep(self.stream_period_s)

        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                line = raw.decode("ascii", "replace").strip("\r\n")
                if stream is not None:
                    stream.cancel()
                    stream = None
                if line.strip().upper() == "SIR":
                    self.requests += 1
                    stream = asyncio.create_task(stream_loop())
                    continue
                resp = await self.command(line)
                if resp is not None:
                    await send(resp)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            if stream is not None:
                stream.cancel()
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, self.host, self.port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._server.wait_closed(), 2)
            self._server = None

    def health(self) -> dict[str, Any]:
        return {"proto": self.name, "up": self._server is not None and self._server.is_serving(),
                "port": self.port, "requests": self.requests}
