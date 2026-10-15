"""Декодування/кодування регістрів Modbus (SPEC R-20)."""
from __future__ import annotations

import struct
from typing import Literal

_SIZES = {"bool": 1, "u16": 1, "i16": 1, "u32": 2, "i32": 2, "f32": 2, "u64": 4, "i64": 4, "f64": 4}
_FMT = {"u16": "H", "i16": "h", "u32": "I", "i32": "i", "f32": "f", "u64": "Q", "i64": "q", "f64": "d"}


def reg_count(type_: str) -> int:
    try:
        return _SIZES[type_]
    except KeyError:
        raise ValueError(f"unknown type {type_!r}") from None


def decode_registers(
    regs: list[int], type: str, wordorder: str = "big", byteorder: str = "big"
) -> float | int:
    """Регістри -> «сире» значення. `wordorder=little`: молодше слово першим."""
    n = reg_count(type)
    if type == "bool":
        return 1 if regs[0] else 0
    if len(regs) < n:
        raise ValueError(f"{type} needs {n} registers, got {len(regs)}")
    words = list(regs[:n]) if wordorder == "big" else list(reversed(regs[:n]))
    order: Literal["big", "little"] = "big" if byteorder == "big" else "little"
    raw = b"".join((w & 0xFFFF).to_bytes(2, order) for w in words)
    return struct.unpack(">" + _FMT[type], raw)[0]  # type: ignore[no-any-return]


def encode_registers(
    value: float, type: str, wordorder: str = "big", byteorder: str = "big"
) -> list[int]:
    """Обернена до decode_registers."""
    n = reg_count(type)
    if type == "bool":
        return [1 if value else 0]
    raw = struct.pack(">" + _FMT[type], value if type in ("f32", "f64") else int(value))
    order: Literal["big", "little"] = "big" if byteorder == "big" else "little"
    words = [int.from_bytes(raw[i:i + 2], order) for i in range(0, 2 * n, 2)]
    return words if wordorder == "big" else list(reversed(words))


def decode_bit(reg: int, bit: int) -> int:
    return (reg >> bit) & 1
