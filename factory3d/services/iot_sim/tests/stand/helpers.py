"""Спільні помічники стендових тестів: Modbus-клієнт, розбір регістрів."""
from __future__ import annotations

import struct

from pymodbus.client import ModbusTcpClient

NOON = "2026-10-12T10:30:00+03:00"


class Mb:
    def __init__(self, host: str, port: int = 502):
        self.c = ModbusTcpClient(host, port=port, timeout=5)
        assert self.c.connect()

    def close(self):
        self.c.close()

    def hr(self, unit, addr, count=1):
        r = self.c.read_holding_registers(addr, count=count, slave=unit)
        assert not r.isError(), f"u{unit} fc3 pdu{addr}+{count}: {r}"
        return r.registers

    def raw_hr(self, unit, addr, count=1):
        return self.c.read_holding_registers(addr, count=count, slave=unit)

    def di(self, unit, addr, count=1):
        r = self.c.read_discrete_inputs(addr, count=count, slave=unit)
        assert not r.isError(), f"u{unit} fc2 pdu{addr}+{count}: {r}"
        return [int(b) for b in r.bits[:count]]

    def coils(self, unit, addr, count=1):
        r = self.c.read_coils(addr, count=count, slave=unit)
        assert not r.isError(), f"u{unit} fc1 pdu{addr}+{count}: {r}"
        return [int(b) for b in r.bits[:count]]

    def f32(self, unit, addr):
        return struct.unpack(">f", struct.pack(">HH", *self.hr(unit, addr, 2)))[0]

    def i64(self, unit, addr):
        v = 0
        for r in self.hr(unit, addr, 4):
            v = (v << 16) | r
        return v - (1 << 64) if v >= 1 << 63 else v


def f32_of(regs):
    return struct.unpack(">f", struct.pack(">HH", *regs))[0]


def u32_le(regs):  # молодше слово першим (X-43)
    return regs[0] | (regs[1] << 16)


def s32(regs):
    v = (regs[0] << 16) | regs[1]
    return v - (1 << 32) if v >= 1 << 31 else v
