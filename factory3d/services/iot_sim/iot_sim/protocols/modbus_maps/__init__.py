"""Регістрові карти Modbus TCP (SPEC §8.4.1, §8.7, §8.9, §8.4.2, §8.11.3, §8.13.1).

Модель даних: ``UnitMap`` (один unit id) має три таблиці — ``h`` (holding, дзеркало fc4), ``c`` (coils;
DI теж видно через fc01 — SPEC §8.4.2) і ``d`` (discrete inputs). Адреса — **PDU на дроті**.
Кожен ``Entry`` — діапазон ``start..start+n`` зі значенням, що обчислюється *в момент читання*
з ``World`` (``getter() -> list[int]`` слів або ``list[bool]``), і необов'язковим ``setter(offset, value)``.
Невизначена адреса -> 0x02; запис у RO -> 0x02; ``ModbusError(code)`` у setter -> інший код (0x04).

Порядок побудови: специфічні карти пристроїв (``pm5560`` …, ``swbctl`` — вікно керування ГРЩ HR 200…291, W2) ->
``bind_catalog`` (усі інші Modbus-сигнали каталогу за ``SignalSpec.modbus``/dtype/scale; «перший зайняв — той і має»,
тож специфічні мають пріоритет; HR 100…123 контролера ГРЩ лишаються за ``bind_catalog``).
Команди запису не змінюють фізику самі: ``world.force`` (лише командний сигнал), ``world.post`` (тема
для моделі), подія ``command`` — як у SPEC §8.13.1 і ARCHITECTURE «Права».
"""

from __future__ import annotations

import math
import re
import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from iot_sim.core.registry import SignalSpec

TABLES = ("h", "c", "d")
METER_FIRST = "energy/cells/"  # при збігу адреси регістр віддає сигнал шафи (лічильник вводу), а не трансформатора


class ModbusError(Exception):
    """Виняток Modbus із кодом (0x02 Illegal Data Address, 0x04 Slave Failure)."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


# --- кодування значень у слова ---------------------------------------------------------
def to_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return 0
        return round(value)
    if isinstance(value, str):
        try:
            return round(float(value.replace(",", ".")))
        except ValueError:
            return 0
    return 0


def to_float(value: Any) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "."))
        except ValueError:
            return 0.0
    return 0.0


def to_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() not in ("", "0", "false", "off", "no", "none")
    return bool(value)


def words_of(raw: int, nwords: int, little: bool = False, signed: bool = False) -> list[int]:
    """Ціле -> ``nwords`` 16-бітних слів (старше слово першим, якщо не ``little``)."""
    bits = 16 * nwords
    lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
    raw = max(lo, min(hi, raw))
    raw &= (1 << bits) - 1
    out = [(raw >> (16 * (nwords - 1 - i))) & 0xFFFF for i in range(nwords)]
    return out[::-1] if little else out


def f32_words(x: float, little: bool = False) -> list[int]:
    b = struct.pack(">f", x)
    w = [int.from_bytes(b[:2], "big"), int.from_bytes(b[2:], "big")]
    return w[::-1] if little else w


def str_words(text: str, nwords: int) -> list[int]:
    """ASCII/UTF-8 у ``nwords`` слів (2 символи на слово, добито нулями)."""
    b = text.encode("utf-8")[: nwords * 2].ljust(nwords * 2, b"\0")
    return [int.from_bytes(b[i : i + 2], "big") for i in range(0, len(b), 2)]


_TYPES = {  # dtype -> (слів, знаковий)
    "u16": (1, False),
    "i16": (1, True),
    "u32": (2, False),
    "i32": (2, True),
    "u64": (4, False),
    "i64": (4, True),
}


def encode(value: Any, dtype: str, little: bool = False) -> list[int]:
    dtype = dtype.lower()
    if dtype == "f32":
        return f32_words(to_float(value), little)
    n, signed = _TYPES[dtype]
    return words_of(to_int(value), n, little, signed)


def parse_scale(text: str) -> float:
    """``×0,001`` -> 0.001; ``×1``/``—``/інше -> 1.0."""
    m = re.match(r"\s*×\s*([0-9]+(?:[.,][0-9]+)?)", text)
    return float(m.group(1).replace(",", ".")) if m else 1.0


# --- модель таблиць --------------------------------------------------------------------
@dataclass
class Entry:
    start: int
    n: int
    get: Callable[[], list[Any]]
    set: Callable[[int, int], None] | None = None  # (зміщення у діапазоні, слово/біт)
    name: str = ""


@dataclass
class UnitMap:
    unit: int
    name: str = ""
    tables: dict[str, dict[int, tuple[Entry, int]]] = field(default_factory=lambda: {t: {} for t in TABLES})

    def free(self, table: str, start: int, n: int) -> bool:
        t = self.tables[table]
        return all(a not in t for a in range(start, start + n))

    def add(
        self,
        table: str,
        start: int,
        n: int,
        get: Callable[[], list[Any]],
        set: Callable[[int, int], None] | None = None,
        name: str = "",
        force: bool = False,
    ) -> Entry | None:
        if not force and not self.free(table, start, n):
            return None
        e = Entry(start, n, get, set, name)
        for i in range(n):
            self.tables[table][start + i] = (e, i)
        return e

    # зручні обгортки
    def add_hr(
        self,
        start: int,
        words: Callable[[], list[int]],
        n: int,
        set: Callable[[int, int], None] | None = None,
        name: str = "",
    ) -> Entry | None:
        return self.add("h", start, n, words, set, name)

    def add_const(self, start: int, words: list[int], name: str = "") -> Entry | None:
        return self.add("h", start, len(words), lambda w=tuple(words): list(w), None, name)  # type: ignore[misc]

    def add_bit(
        self,
        table: str,
        addr: int,
        get: Callable[[], bool],
        set: Callable[[int, int], None] | None = None,
        name: str = "",
    ) -> None:
        self.add(table, addr, 1, lambda: [bool(get())], set, name)
        if table == "d":  # DI видно й через fc01 (SPEC §8.4.2)
            self.add("c", addr, 1, lambda: [bool(get())], None, name)

    def read(self, table: str, start: int, count: int) -> list[Any]:
        t = self.tables[table]
        cache: dict[int, list[Any]] = {}
        out: list[Any] = []
        for a in range(start, start + count):
            hit = t.get(a)
            if hit is None:
                raise ModbusError(2)
            e, off = hit
            vals = cache.get(id(e))
            if vals is None:
                vals = cache[id(e)] = e.get()
            out.append(vals[off] if off < len(vals) else 0)
        return out

    def write(self, table: str, start: int, values: list[Any]) -> None:
        t = self.tables[table]
        for i in range(len(values)):  # спершу перевірка, потім запис (атомарно)
            hit = t.get(start + i)
            if hit is None or hit[0].set is None:
                raise ModbusError(2)
        for i, v in enumerate(values):
            e, off = t[start + i]
            e.set(off, int(v))  # type: ignore[misc]


# --- контекст побудови -----------------------------------------------------------------
class Ctx:
    """Спільний доступ до World для карт: значення сигналів, запис-команди, налаштування."""

    def __init__(self, world: Any) -> None:
        self.world = world
        self.maps: dict[int, UnitMap] = {}
        self._by_addr: dict[tuple[int, int, int], Any] | None = None

    def unit(self, unit: int, name: str = "") -> UnitMap:
        m = self.maps.get(unit)
        if m is None:
            m = self.maps[unit] = UnitMap(unit, name)
        elif name and not m.name:
            m.name = name
        return m

    @property
    def write_accept(self) -> bool:
        return bool(getattr(self.world.settings, "write_accept", True))

    def val(self, code: str, default: Any = 0) -> Any:
        sig = self.world.signals.get(code)
        return default if sig is None else sig.value

    def model(self, device: str) -> Any:
        """Модель пристрою світу за кодом (``Ctx.model("CHP")``) або ``None``."""
        dev = self.world.devices.get(device)
        return None if dev is None else dev.model

    def sig_at(self, unit: int, pdu: int, fc: int = 3) -> Any:
        """Сигнал каталогу за (unit, fc, початковий PDU) — перший у порядку каталогу, або ``None``.

        Колізія адрес: каталог має дві пари сигналів на одному регістрі PM5560 u1/u2 (``energy/transformers/T*/p_kw`` і
        ``i_a`` — старий «макет» — та ``energy/cells/Q*/p_now``, ``i_now``). Регістр — це лічильник вводу, тож
        перевагу має сигнал шафи ``energy/cells/``: інакше Odoo читає P вводу без СЕС/КГУ/BESS."""
        if self._by_addr is None:
            self._by_addr = {}
            for sp in signal_specs(self.world):
                key = sp.modbus[:3]  # type: ignore[index]
                held = self._by_addr.get(key)
                if held is None or (sp.code.startswith(METER_FIRST) and not held.code.startswith(METER_FIRST)):
                    self._by_addr[key] = self.world.signals[sp.code]
        return self._by_addr.get((unit, fc, pdu))

    def sig_num(self, unit: int, pdu: int, default: float = 0.0) -> float:
        sig = self.sig_at(unit, pdu)
        return default if sig is None else to_float(sig.value)

    def num(self, code: str, default: float = 0.0) -> float:
        return to_float(self.val(code, default))

    def command(self, unit: int, what: str, payload: dict[str, Any] | None = None) -> None:
        """Подія ``command`` (SPEC AC-44): запис у ADAM-DO/ATyS/… логується."""
        self.world.events.emit("command", f"Modbus u{unit}: {what}", payload={"unit": unit, **(payload or {})})

    def flag_store(self, unit: int, addr: int, default: int = 0) -> tuple[Callable[[], int], Callable[[int], None]]:
        key = f"modbus.u{unit}.{addr}"
        return (lambda: int(self.world.flag(key, default)), lambda v: self.world.set_flag(key, int(v)))


def signal_specs(world: Any) -> list[SignalSpec]:
    return [s.spec for s in world.signals.values() if s.spec.modbus and s.spec.emulated]


_TOKEN_RE = re.compile(r"pdu\d+(?:\+\d+)? (\w+)(?: (little|max))?")


def parse_dtype(address: str) -> tuple[str, bool, bool]:
    """Із тексту адреси: (dtype, little, max). ``bool`` -> ``bit``."""
    m = _TOKEN_RE.search(address)
    if not m:
        return "u16", False, False
    return m.group(1).lower(), m.group(2) == "little", m.group(2) == "max"


def bind_catalog(ctx: Ctx) -> int:
    """Прив'язує всі Modbus-сигнали каталогу, адреси яких ще вільні (власні карти мають пріоритет)."""
    world, n_bound = ctx.world, 0
    for spec in signal_specs(world):
        unit, fc, pdu, _count = spec.modbus  # type: ignore[misc]
        um = ctx.unit(unit)
        dtype, little, _ = parse_dtype(spec.address)
        sig = world.signals[spec.code]
        if dtype in ("bool", "bit"):
            if fc == 2:
                um.add_bit("d", pdu, lambda s=sig: to_bool(s.value), None, spec.code)  # type: ignore[misc]
            else:  # fc1: coil; запис FC05 — командний сигнал (SPEC §8.13.1)
                um.add_bit(
                    "c",
                    pdu,
                    lambda s=sig: to_bool(s.value),  # type: ignore[misc]
                    coil_cmd(ctx, unit, spec),
                    spec.code,
                )
            n_bound += 1
            continue
        if dtype not in _TYPES and dtype != "f32":
            continue
        scale = parse_scale(spec.scale)
        words = {"f32": 2, "u16": 1, "i16": 1, "u32": 2, "i32": 2, "u64": 4, "i64": 4}[dtype]

        def get(s: Any = sig, sc: Any = scale, dt: Any = dtype, lt: Any = little) -> list[int]:
            v = to_float(s.value)
            return encode(v / sc, dt, lt)

        if um.add_hr(pdu, get, words, None, spec.code):
            n_bound += 1
    return n_bound


def coil_cmd(ctx: Ctx, unit: int, spec: SignalSpec) -> Callable[[int, int], None]:
    def setter(_off: int, v: int) -> None:
        if not ctx.write_accept:
            raise ModbusError(4)
        ctx.world.force(spec.code, 1 if v else 0)
        ctx.world.post(
            "yard" if spec.code.startswith("yard/") else "modbus_cmd",
            {
                "kind": "gate_cmd" if spec.code.startswith("yard/") else "coil",
                "signal": spec.code,
                "gate": spec.device,
                "cmd": spec.code.rsplit("/", 1)[-1],
                "value": bool(v),
                "unit": unit,
            },
        )
        ctx.command(unit, f"{spec.code} = {int(bool(v))}", {"signal": spec.code})

    return setter


def build_all(world: Any) -> dict[int, UnitMap]:
    """Будує карти всіх unit id (специфічні карти -> каталог)."""
    from iot_sim.protocols.modbus_maps import (
        adam6015,
        adam6017,
        adam6050,
        adam6060,
        atys,
        elektronikon,
        luna2000,
        pm5560,
        sun2000,
        swbctl,
        tedom,
    )

    ctx = Ctx(world)
    for mod in (pm5560, sun2000, luna2000, elektronikon, atys, tedom, adam6050, adam6060, adam6017, adam6015, swbctl):
        mod.build(ctx)
    bind_catalog(ctx)
    return ctx.maps
