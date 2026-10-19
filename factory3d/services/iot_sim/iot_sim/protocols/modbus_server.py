"""Modbus TCP (SPEC §8.4.1, A-03): один сервер, багато unit id; регістри обчислюються з ``World`` при читанні.

Функції 01/02/03/04(=03)/05/06/15/16. Невідомий unit -> 0x0B (pymodbus ``NoSuchSlaveException``),
невідома адреса й запис у RO -> 0x02, ``SIM_WRITE_ACCEPT=0`` для команд -> 0x04. Карти пристроїв —
``iot_sim.protocols.modbus_maps`` (PDU-адреси за §8.4.1). Порт у тестах — вільний (``SIM_TEST_PORT_BASE``).

Реєстрація у ``__main__ run``: ``ModbusServer(world, port=settings.port_modbus)``; ``await start()``.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from pymodbus.datastore import ModbusBaseSlaveContext, ModbusServerContext
from pymodbus.server import ModbusTcpServer

from iot_sim.core.world import World
from iot_sim.protocols.base import ProtocolServer
from iot_sim.protocols.modbus_maps import ModbusError, UnitMap, build_all

log = logging.getLogger("iot_sim.modbus")

_READ = {1: "c", 2: "d", 3: "h", 4: "h"}
_WRITE = {5: "c", 15: "c", 6: "h", 16: "h", 22: "h", 23: "h"}


class UnitContext(ModbusBaseSlaveContext):
    """Контекст одного unit id: делегує ``UnitMap`` (адреса = PDU, без зсувів)."""

    def __init__(self, umap: UnitMap) -> None:
        self.umap = umap

    def reset(self) -> None:  # pragma: no cover - інтерфейс pymodbus
        pass

    def validate(self, fc_as_hex: int, address: int, count: int = 1) -> bool:
        table = _READ.get(fc_as_hex) or _WRITE.get(fc_as_hex)
        if table is None:
            return False
        try:
            self.umap.read(table, address, count)
        except ModbusError:
            return False
        return True

    def getValues(self, fc_as_hex: int, address: int, count: int = 1) -> Any:
        table = _READ.get(fc_as_hex) or _WRITE.get(fc_as_hex)  # write-back після FC 05/06/16
        if table is None:
            return 1  # Illegal Function
        try:
            return self.umap.read(table, address, count)
        except ModbusError as e:
            return e.code

    def setValues(self, fc_as_hex: int, address: int, values: Sequence[int | bool]) -> Any:
        table = _WRITE.get(fc_as_hex)
        if table is None:
            return 1
        try:
            self.umap.write(table, address, [int(v) for v in values])
        except ModbusError as e:
            return e.code
        return None


class GatewayContext(UnitContext):
    """Невідомий unit: будь-який запит -> 0x0B Gateway Target Device Failed to Respond (SPEC §8.4.1).

    ``NoSuchSlaveException`` pymodbus 3.9.2 відповідає кадром із функцією 0x80, який клієнти не розбирають;
    тому відповідь формується штатно (``fc|0x80`` + код) через цей контекст.
    """

    def __init__(self) -> None:
        super().__init__(UnitMap(0))

    def validate(self, fc_as_hex: int, address: int, count: int = 1) -> bool:
        return False

    def getValues(self, fc_as_hex: int, address: int, count: int = 1) -> Any:
        return 0x0B

    def setValues(self, fc_as_hex: int, address: int, values: Any) -> Any:
        return 0x0B


class SimServerContext(ModbusServerContext):
    def __init__(self, slaves: dict[int, UnitContext]) -> None:
        super().__init__(slaves=slaves, single=False)  # type: ignore[no-untyped-call]
        self._gateway = GatewayContext()

    def __getitem__(self, slave: Any) -> Any:
        return self._slaves.get(slave) or self._gateway


class ModbusServer(ProtocolServer):
    name = "modbus"

    def __init__(self, world: World, *, port: int = 502, host: str = "0.0.0.0") -> None:
        self.world = world
        self.port, self.host = port, host
        self.up = False
        self.units: dict[int, UnitMap] = {}
        self._server: ModbusTcpServer | None = None

    async def start(self) -> None:
        self.units = build_all(self.world)
        slaves = {u: UnitContext(m) for u, m in self.units.items()}
        ctx = SimServerContext(slaves)
        self._server = ModbusTcpServer(ctx, address=(self.host, self.port))
        await self._server.serve_forever(background=True)
        self.up = True
        log.info("Modbus TCP %s:%d, units=%d", self.host, self.port, len(self.units))

    async def stop(self) -> None:
        if self._server is not None:
            await self._server.shutdown()  # type: ignore[no-untyped-call]
            self._server = None
        self.up = False

    def health(self) -> dict[str, Any]:
        return {"proto": self.name, "up": self.up, "port": self.port, "units": len(self.units)}
