"""Реєстр сигналів і пристроїв: ``catalog/signals.csv`` (Додаток A, 1 168 рядків) + ``devices.yaml``.

``Registry.load(dir)`` читає локальний каталог (fallback, SPEC §11). Рядок CSV -> ``SignalSpec``
(номінал, шум, швидкість, поріг, межа, Modbus-адреса розібрані з тексту). ``driver_for()`` —
відповідність пристрій -> ім'я драйвера моделі (``iot_sim.models``); невідомі — ``passive``.
"""
from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROTOCOL_NONE = "—"
NUMERIC_DTYPES = {"REAL", "int", "F32", "I64", "U32", "U16", "I32", "U64", "UInt64", "number", "PIV"}
_NUM = r"[-+−]?\d+(?:[.,]\d+)?"
_MODBUS_RE = re.compile(r"u(\d+) fc(\d+) pdu(\d+)(?:\+(\d+))?")


def _f(s: str) -> float:
    return float(s.replace(",", ".").replace("−", "-"))


@dataclass
class SignalSpec:
    n: int
    code: str
    device: str
    protocol: str
    address: str
    dtype: str
    unit: str
    scale: str
    nominal_text: str
    thresholds_text: str
    model: str
    status: str
    nominal: float | None = None
    noise: float | None = None
    rate: float | None = None
    threshold: float | None = None
    alarm: str | None = None  # "above" | "below" | None
    limit: float | None = None
    modbus: tuple[int, int, int, int] | None = None  # unit, fc, pdu, count

    @property
    def emulated(self) -> bool:
        """151 рядок ``protocol=none`` (обчислюються споживачем/власником) емулятор не віддає."""
        return self.protocol != PROTOCOL_NONE

    @property
    def computed(self) -> bool:
        return self.model.startswith("обчислює") or self.model.startswith("власник")

    @property
    def group(self) -> str:
        return self.code.split("/", 1)[0]

    @property
    def leaf(self) -> str:
        return self.code.rsplit("/", 1)[-1]

    @property
    def rule(self) -> str:
        """Ідентифікатор правила поведінки: ``R-09``, ``noise``, ``machine``…"""
        m = re.match(r"(R-\d+|[a-zA-Z_]+)", self.model)
        return m.group(1) if m else ""

    @property
    def kind(self) -> str:
        """gauge | counter | state (ASSUMPTION: евристика за одиницею/листом)."""
        if self.leaf in {"kwh_total", "kwh_today", "kwh_shift", "hours", "cycles_today",
                         "m3_total", "pieces_out", "pieces_in"} or self.unit in {"кВт·год", "год"}:
            return "counter"
        if self.dtype in NUMERIC_DTYPES:
            return "gauge"
        return "state"

    def initial_value(self) -> Any:
        if self.nominal is not None:
            return self.nominal
        return "" if self.dtype == "text" else 0


def parse_spec(row: dict[str, str]) -> SignalSpec:
    nom, thr = row["nominal"], row["thresholds"]
    s = SignalSpec(
        n=int(row["n"]), code=row["code"], device=row["device"], protocol=row["protocol"],
        address=row["address"], dtype=row["dtype"], unit=row["unit"], scale=row["scale"],
        nominal_text=nom, thresholds_text=thr, model=row["model"], status=row["status"])
    m = re.match(rf"\s*({_NUM})", nom)
    if m:
        s.nominal = _f(m.group(1))
    m = re.search(rf"шум ({_NUM})", nom)
    if m:
        s.noise = _f(m.group(1))
    m = re.search(rf"швидк\. ({_NUM})", nom)
    if m:
        s.rate = _f(m.group(1))
    m = re.match(rf"\s*([<>])\s*({_NUM})", thr)
    if m:
        s.alarm = "above" if m.group(1) == ">" else "below"
        s.threshold = _f(m.group(2))
    m = re.match(rf"\s*межа ({_NUM})", thr)
    if m:
        s.limit = _f(m.group(1))
    m = _MODBUS_RE.search(row["address"])
    if m and s.protocol != PROTOCOL_NONE:
        s.modbus = (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4) or 1))
    return s


# ASSUMPTION: імена драйверів — за переліком SPEC §8.2.3; перший збіг за префіксом коду сигналу.
DRIVER_RULES: list[tuple[str, str]] = [
    ("workcenters/", "machine"), ("equipment/GANTRY", "gantry"), ("equipment/FL-", "mobile"),
    ("equipment/TUGGER", "mobile"), ("equipment/COMPRESSOR", "compressor"),
    ("equipment/BOILER", "boiler"), ("equipment/DUST", "dust"),
    ("equipment/SPRINKLERS", "passive"), ("equipment/CUTOPT", "passive"),
    ("ventilation/units/", "roofvent"), ("lighting/", "lighting"), ("infra/pv/", "pv"),
    ("infra/chp/", "chp"), ("infra/ats/", "ats"), ("infra/bess/", "bess"),
    ("infra/water/", "water"), ("energy/transformers/", "transformer"),
    ("energy/lines/", "meter"), ("energy/cells/", "meter"), ("fire/", "facp"),
    ("access/", "access"), ("yard/", "yard"),
]


def driver_for(codes: list[str]) -> str:
    for prefix, drv in DRIVER_RULES:
        if any(c.startswith(prefix) for c in codes):
            return drv
    return "passive"


@dataclass
class DeviceSpec:
    code: str
    driver: str = ""  # "" -> driver_for(signals) при завантаженні
    protocols: list[str] = field(default_factory=list)
    unit_id: int | None = None
    instance: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    signals: list[str] = field(default_factory=list)  # коди сигналів

    @property
    def protocol(self) -> str | None:
        return self.protocols[0] if self.protocols else None


class Registry:
    def __init__(self, signals: list[SignalSpec], devices: list[DeviceSpec],
                 catalog_hash: str = "") -> None:
        self.signals = signals
        self.by_code = {s.code: s for s in signals}
        self.devices = {d.code: d for d in devices}
        self.catalog_hash = catalog_hash

    @classmethod
    def load(cls, catalog_dir: str | Path = "catalog") -> Registry:
        d = Path(catalog_dir)
        csv_bytes = (d / "signals.csv").read_bytes()
        with (d / "signals.csv").open(encoding="utf-8", newline="") as f:
            specs = [parse_spec(r) for r in csv.DictReader(f)]
        yaml_path = d / "devices.yaml"
        yaml_bytes = yaml_path.read_bytes() if yaml_path.exists() else b""
        raw = (yaml.safe_load(yaml_bytes) or {}).get("devices", []) if yaml_bytes else []
        devs: dict[str, DeviceSpec] = {}
        for item in raw:
            devs[item["code"]] = DeviceSpec(
                code=item["code"], driver=item.get("driver", ""),
                protocols=list(item.get("protocols", [])), unit_id=item.get("unit_id"),
                instance=item.get("instance"), params=dict(item.get("params", {})))
        for s in specs:  # пристрої, відомі лише з каталогу сигналів
            dev = devs.setdefault(s.device, DeviceSpec(code=s.device))
            dev.signals.append(s.code)
            if s.protocol != PROTOCOL_NONE and s.protocol not in dev.protocols:
                dev.protocols.append(s.protocol)
            if dev.unit_id is None and s.modbus:
                dev.unit_id = s.modbus[0]
        for dev in devs.values():
            if not dev.driver:
                dev.driver = driver_for(dev.signals)
        h = hashlib.sha256(csv_bytes + yaml_bytes).hexdigest()
        return cls(specs, list(devs.values()), h)

    def served(self) -> list[SignalSpec]:
        """Сигнали, які віддає ``/signals`` (без ``protocol=none``, X-35)."""
        return [s for s in self.signals if s.emulated]
