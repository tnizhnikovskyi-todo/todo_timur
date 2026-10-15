"""Спільні фікстури протокольних тестів: вільні порти (SIM_TEST_PORT_BASE)."""
import itertools
import os
import socket

import pytest

_counter = itertools.count()


def free_port() -> int:
    base = os.environ.get("SIM_TEST_PORT_BASE")
    if base:
        return int(base) + next(_counter)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def port():
    return free_port()


# --- W3: Modbus-клієнт на локальному сервері ---------------------------------------------
@pytest.fixture
async def modbus(world, port):
    """``ModbusServer`` на вільному порту + підключений ``AsyncModbusTcpClient`` (``srv.client``)."""
    from pymodbus.client import AsyncModbusTcpClient

    from iot_sim.protocols.modbus_server import ModbusServer

    srv = ModbusServer(world, port=port, host="127.0.0.1")
    await srv.start()
    client = AsyncModbusTcpClient("127.0.0.1", port=port)
    await client.connect()
    srv.client = client
    yield srv
    client.close()
    await srv.stop()
