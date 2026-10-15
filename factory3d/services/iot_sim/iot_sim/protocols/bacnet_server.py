"""P-08/P-09 BACnet/IP (SPEC §8.10, §8.11, A-04): BIP-роутер + віртуальна мережа 2 з пристроями 101…200.

Схема: ``router`` (device 99, «F3D Sim Router») слухає UDP ``port`` (47808) як мережа ``bip_network`` і
з'єднаний з віртуальною LAN (``vnet``, за умовчанням 2), у якій кожен пристрій — окремий ``Application``:
RV-01…RV-25 = 101…125, AHU-1 = 130, EF-ELEC/EF-CMP/EF-CHG = 131/132/133, BOILER = 140, FACP-1 = 200.
``Who-Is`` крізь роутер повертає ``I-Am`` усіх; ``Who-Is 101 125`` — лише RoofVent.

Значення читаються з ``World`` (``ventilation/units/<C>/*``, ``equipment/BOILER/*``, ``fire/*``) і
переносяться в локальні об'єкти ``bacpypes3`` на кожен тік (``world.on_tick``) та ``sync()`` — тому COV
працює штатно. Запис ``present-value`` (AO/AV/BV/MSV, пріоритет 8…16) ставить команду у ``World``:
``world.force`` для сигналів каталогу, ``world.set_flag("bacnet.<C>.<об'єкт>")`` для решти,
``world.post("hvac"|"boiler", {...})`` і подія ``command``. Об'єкти панелі 200 (LSZ/LSP/PIV/BV/MSV) —
лише читання (``writeAccessDenied``); ``ReinitializeDevice``/``DeviceCommunicationControl`` -> ``serviceRequestDenied``.

Розкладка LSP/LSZ береться з ``dist/odoo_demo.json`` (``fire.groups``: ``n`` і ``loop`` зон), шлях — параметр
``layout`` / змінна ``SIM_LAYOUT_PATH``; без нього — лише LSZ із каталогу сигналів (ПРИПУЩЕННЯ).

Реєстрація у ``__main__ run``: ``BacnetServer(world, address=f"{ip}/{prefix}:{settings.port_bacnet}")``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bacpypes3.app import Application
from bacpypes3.errors import ExecutionError, PropertyError
from bacpypes3.ipv4.link import NormalLinkLayer
from bacpypes3.local.analog import AnalogInputObject, AnalogValueObject
from bacpypes3.local.binary import BinaryInputObject, BinaryValueObject
from bacpypes3.local.cov import GenericCriteria
from bacpypes3.local.device import DeviceObject
from bacpypes3.local.multistate import MultiStateValueObject
from bacpypes3.local.object import Object as LocalObject
from bacpypes3.object import (
    AnalogOutputObject as _AnalogOutputObject,
)
from bacpypes3.object import (
    LifeSafetyPointObject as _LifeSafetyPointObject,
)
from bacpypes3.object import (
    LifeSafetyZoneObject as _LifeSafetyZoneObject,
)
from bacpypes3.object import (
    PositiveIntegerValueObject as _PositiveIntegerValueObject,
)
from bacpypes3.pdu import IPv4Address, LocalStation
from bacpypes3.vlan import VirtualNetwork
from bacpypes3.vlan.link import VirtualLinkLayer

from iot_sim.core.world import World
from iot_sim.protocols.base import ProtocolServer

log = logging.getLogger("iot_sim.bacnet")

VENDOR_ID = 999  # ПРИПУЩЕННЯ: тестовий vendor id bacpypes3
ROUTER_INSTANCE = 99
ROUTER_VADDR = 250
ADMIN_DENIED = ("services", "serviceRequestDenied")
FOREVER_S = 10 ** 9
MODES = {"VE": 1, "VEL": 2, "AQ": 3, "REC": 4, "EA": 5, "SA": 6, "ST": 7, "OFF": 8}
LSS = {"quiet": 0, "pre-alarm": 1, "prealarm": 1, "alarm": 2, "fault": 3, "not-ready": 6,
       "notready": 6, "test-alarm": 9, "testalarm": 9}
LSS_NAME = {0: "quiet", 1: "preAlarm", 2: "alarm", 3: "fault", 6: "notReady", 9: "testAlarm"}


# --- опис точок ------------------------------------------------------------------------
@dataclass
class Point:
    kind: str                       # ai ao av bi bv msv lsz lsp piv
    inst: int
    name: str
    read: Callable[[], Any]
    desc: str = ""
    units: str | None = None
    cov: float = 1.0
    write: Callable[[Any], None] | None = None
    states: list[str] | None = None
    members: list[int] = field(default_factory=list)


@dataclass
class DeviceDef:
    instance: int
    name: str
    vendor: str
    model: str
    points: list[Point] = field(default_factory=list)


def _num(v: Any, default: float = 0.0) -> float:
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.replace(",", "."))
        except ValueError:
            return default
    return default


def _truthy(v: Any) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "on", "running", "run", "yes", "active")
    return bool(v)


def _lss(v: Any) -> int:
    if isinstance(v, str):
        return LSS.get(v.strip().lower().replace("_", "-"), 0)
    n = int(_num(v))
    return n if n in LSS_NAME else 0


def load_layout(path: str | Path | None = None) -> dict[str, Any]:
    """``dist/odoo_demo.json`` (макет): ``fire.groups``, ``lighting``. Порожній словник, якщо файлу немає."""
    cands = [path, os.environ.get("SIM_LAYOUT_PATH"),
             Path(__file__).resolve().parents[4] / "dist" / "odoo_demo.json",
             Path("dist/odoo_demo.json")]
    for c in cands:
        if c and Path(c).is_file():
            try:
                return json.loads(Path(c).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                log.warning("не вдалося прочитати макет %s", c)
    return {}


class Builder:
    """Збирає ``DeviceDef`` для всіх пристроїв за SPEC §8.10–§8.11 (значення — живі лямбди над World)."""

    def __init__(self, world: World, layout: dict[str, Any]) -> None:
        self.w = world
        self.layout = layout

    # --- доступ до World ---
    def val(self, code: str, default: Any = 0) -> Any:
        s = self.w.signals.get(code)
        return default if s is None else s.value

    def num(self, code: str, default: float = 0.0) -> float:
        return _num(self.val(code, default), default)

    def has(self, code: str) -> bool:
        return code in self.w.signals

    def flag_num(self, key: str, default: float) -> Callable[[], float]:
        return lambda: _num(self.w.flag(key, default), default)

    def command(self, dev: str, what: str, payload: dict | None = None) -> None:
        self.w.events.emit("command", f"BACnet {dev}: {what}", device=dev, payload=payload or {})

    def setter_signal(self, dev: str, code: str, hold_s: float, what: str) -> Callable[[Any], None]:
        def write(v: Any) -> None:
            if self.has(code):
                self.w.force(code, v, hold_s)
            self.w.post("hvac", {"device": dev, "signal": code, "value": v})
            self.command(dev, f"{what} = {v}", {"signal": code, "value": v})
        return write

    def setter_flag(self, dev: str, key: str, what: str, topic: str = "hvac") -> Callable[[Any], None]:
        def write(v: Any) -> None:
            self.w.set_flag(key, v)
            self.w.post(topic, {"device": dev, "key": key, "value": v})
            self.command(dev, f"{what} = {v}", {"key": key, "value": v})
        return write

    # --- RoofVent / AHU / EF ---
    def ventilation(self) -> list[DeviceDef]:
        out: list[DeviceDef] = []
        codes = sorted({c.split("/")[2] for c in self.w.signals if c.startswith("ventilation/units/")})
        rvs = [c for c in codes if c.startswith("RV-")]
        for i, code in enumerate(rvs):
            out.append(self._air_unit(code, 100 + 1 + i if not code[3:].isdigit() else 100 + int(code[3:]),
                                      "Hoval", "RoofVent/TopTronic C"))
        if "AHU-1" in codes:
            out.append(self._air_unit("AHU-1", 130, "VTS", "AHU", ahu=True))
        for code, inst in (("EF-ELEC", 131), ("EF-CMP", 132), ("EF-CHG", 133)):
            if code in codes:
                out.append(self._fan(code, inst))
        return out

    def _air_unit(self, c: str, inst: int, vendor: str, model: str, ahu: bool = False) -> DeviceDef:
        base = f"ventilation/units/{c}"
        d = DeviceDef(inst, c, vendor, model)
        P = d.points.append
        n = lambda leaf, default=0.0: (lambda: self.num(f"{base}/{leaf}", default))
        ekey = f"bacnet.{c}.enable"

        def enabled() -> bool:
            return bool(self.w.flag(ekey, 1))

        def dp4() -> float:
            return self.num(f"{base}/filter_dp_pa")

        def dp5() -> float:
            return self.num(f"{base}/filter_extract_dp_pa", 0.8 * dp4()) if self.has(
                f"{base}/filter_extract_dp_pa") else 0.8 * dp4()

        def state() -> str:
            return str(self.val(f"{base}/state", "running")).strip().lower()

        def running() -> bool:
            return enabled() and state() in ("running", "on", "1", "frost") and not _lowmode()

        def _lowmode() -> bool:
            return self._mode(base) == 8

        P(Point("ai", 1, f"{c}_SupplyAirTemp", n("supply_c"), "Температура припливу", "degreesCelsius", 0.2))
        P(Point("ai", 2, f"{c}_ExtractAirTemp", n("indoor_c"), "Температура витяжки", "degreesCelsius", 0.2))
        P(Point("ai", 3, f"{c}_SupplyAirFlow",
                lambda: self.num(f"{base}/airflow_m3h") if enabled() else 0.0,
                "Витрата припливу", "cubicMetersPerHour", 50))
        P(Point("ai", 4, f"{c}_FreshAirFilterDp", dp4, "Перепад на фільтрі припливу", "pascals", 5))
        P(Point("ai", 5, f"{c}_ExtractAirFilterDp", dp5, "Перепад на фільтрі витяжки", "pascals", 5))
        P(Point("ai", 6, f"{c}_OutdoorTemp", lambda: self.num("ventilation/totals/outdoor_c", 9.0),
                "Зовнішня температура", "degreesCelsius", 0.2))
        P(Point("ai", 7, f"{c}_HeatOutput", n("heat_kw"), "Теплова потужність", "kilowatts", 1))
        P(Point("ai", 8, f"{c}_FanPower", n("p_now"), "Потужність вентиляторів", "kilowatts", 0.5))
        if ahu:
            P(Point("ai", 9, f"{c}_RoomPressure", n("room_pressure_pa", -10.0), "Тиск у приміщенні",
                    "pascals", 5))
        P(Point("ao", 1, f"{c}_HeatingValve", n("heating_valve"), "Клапан нагрівача", "percent", 1,
                write=self.setter_signal(c, f"{base}/heating_valve", 600, "HeatingValve")))
        P(Point("ao", 2, f"{c}_FanSpeedSetpoint", self.flag_num(f"bacnet.{c}.fan_speed", 100.0),
                "Задана швидкість вентилятора", "percent", 1,
                write=self.setter_flag(c, f"bacnet.{c}.fan_speed", "FanSpeedSetpoint")))
        P(Point("av", 1, f"{c}_RoomSetpointDay", n("setpoint_day_c", 18.0), "Уставка день", "degreesCelsius",
                0.5, write=self.setter_signal(c, f"{base}/setpoint_day_c", FOREVER_S, "RoomSetpointDay")))
        P(Point("av", 2, f"{c}_RoomSetpointNight", n("setpoint_night_c", 14.0), "Уставка ніч",
                "degreesCelsius", 0.5,
                write=self.setter_signal(c, f"{base}/setpoint_night_c", FOREVER_S, "RoomSetpointNight")))
        P(Point("bi", 1, f"{c}_Running", running, "В роботі"))
        P(Point("bi", 2, f"{c}_Fault", lambda: state() == "fault" or self.w.devices[c].fault is not None
                if c in self.w.devices else state() == "fault", "Несправність"))
        P(Point("bi", 3, f"{c}_FilterAlarmFresh", lambda: dp4() > 250, "Фільтр припливу забитий"))
        P(Point("bi", 4, f"{c}_FilterAlarmExtract", lambda: dp5() > 350, "Фільтр витяжки забитий"))
        P(Point("bi", 5, f"{c}_FrostProtection", lambda: state() == "frost", "Захист від замерзання"))
        if ahu:
            P(Point("bi", 6, f"{c}_BoothExtractInterlock",
                    lambda: _truthy(self.val(f"{base}/booth_interlock", 1)), "Блокування витяжки камер"))
        P(Point("bv", 1, f"{c}_Enable", lambda: enabled(), "Дозвіл роботи",
                write=self._enable_writer(c, ekey)))
        modes = ["VE", "VEL", "AQ", "REC", "EA", "SA", "ST", "Off"]
        P(Point("msv", 1, f"{c}_OperatingMode", lambda: self._mode(base), "Режим роботи", states=modes,
                write=self._mode_writer(c, f"{base}/mode")))
        P(Point("msv", 2, f"{c}_AQState", lambda: 2, "Стан AQ", states=["AQ_REC", "AQ_ECO", "AQ_VE"]))
        P(Point("msv", 3, f"{c}_LocalMode", self.flag_num(f"bacnet.{c}.local_mode", 1), "Місцевий режим",
                states=["Auto", "Off", "REC", "SA", "EA", "VE"],
                write=self.setter_flag(c, f"bacnet.{c}.local_mode", "LocalMode")))
        return d

    def _mode(self, base: str) -> int:
        v = self.val(f"{base}/mode", 1)
        if isinstance(v, str):
            return MODES.get(v.strip().upper(), 1)
        n = int(_num(v, 1))
        return n if 1 <= n <= 8 else 1

    def _mode_writer(self, c: str, code: str) -> Callable[[Any], None]:
        def write(v: Any) -> None:
            v = int(v)
            if self.has(code):
                self.w.force(code, v, 3600)
            self.w.post("hvac", {"device": c, "signal": code, "value": v})
            self.command(c, f"OperatingMode = {v}", {"value": v})
        return write

    def _enable_writer(self, c: str, key: str) -> Callable[[Any], None]:
        def write(v: Any) -> None:
            on = 1 if _truthy(v) or v in (1, True) else 0
            self.w.set_flag(key, on)
            self.w.post("hvac", {"device": c, "cmd": "enable", "value": on})
            self.command(c, f"Enable = {on}", {"value": on})
        return write

    def _fan(self, c: str, inst: int) -> DeviceDef:
        base = f"ventilation/units/{c}"
        d = DeviceDef(inst, c, "VENTS/Systemair", "EF")
        P = d.points.append
        ekey = f"bacnet.{c}.enable"

        def state() -> str:
            return str(self.val(f"{base}/state", "running")).strip().lower()

        P(Point("bi", 1, f"{c}_Running", lambda: bool(self.w.flag(ekey, 1)) and state() in (
            "running", "on", "1"), "В роботі"))
        P(Point("ai", 2, f"{c}_RoomTemp", lambda: self.num(f"{base}/indoor_c", 24.0),
                "Температура приміщення", "degreesCelsius", 0.2))
        P(Point("ai", 3, f"{c}_AirFlow", lambda: self.num(f"{base}/airflow_m3h"), "Витрата",
                "cubicMetersPerHour", 50))
        P(Point("bv", 1, f"{c}_Enable", lambda: bool(self.w.flag(ekey, 1)), "Дозвіл роботи",
                write=self._enable_writer(c, ekey)))
        if c != "EF-CHG":
            sp = {"EF-ELEC": 28.0, "EF-CMP": 30.0}[c]
            P(Point("av", 1, f"{c}_ThermostatSetpoint", self.flag_num(f"bacnet.{c}.thermostat", sp),
                    "Уставка термостата", "degreesCelsius", 0.5,
                    write=self.setter_flag(c, f"bacnet.{c}.thermostat", "ThermostatSetpoint")))
        else:
            def charging() -> bool:
                f = self.w.flag("charging_active")
                return state() == "stopped_charging" if f is None else bool(f)

            P(Point("bi", 7, "EF-CHG_ChargingActive", charging, "Заряджання активне"))
        return d

    # --- котельня ---
    def boiler(self) -> DeviceDef:
        b = "equipment/BOILER"
        d = DeviceDef(140, "BOILER", "Kalvis (emulated)", "K-series")
        P = d.points.append

        def st() -> int:
            v = self.val(f"{b}/state", 1)
            return int(_num(v, 1)) if not isinstance(v, str) else {"standby": 1, "k1": 2, "k1+k2": 3,
                                                                    "fault": 4}.get(v.lower(), 1)

        P(Point("ai", 1, "BOILER_SupplyTemp", lambda: self.num(f"{b}/supply_c"), "Подача", "degreesCelsius", 0.2))
        P(Point("ai", 2, "BOILER_ReturnTemp", lambda: self.num(f"{b}/return_c"), "Зворотка", "degreesCelsius", 0.2))
        P(Point("ai", 3, "BOILER_SiloLevel", lambda: self.num(f"{b}/silo_fill"), "Рівень бункера", "percent", 1))
        P(Point("ai", 4, "BOILER_FlueGasTemp", lambda: 160.0 if st() in (2, 3) else 25.0, "Димові гази",
                "degreesCelsius", 1))
        P(Point("ai", 5, "BOILER_HeatOutput", lambda: self.num(f"{b}/heat_kw"), "Теплова потужність",
                "kilowatts", 1))
        P(Point("ai", 6, "BOILER_BriquettesToday", self.flag_num("bacnet.BOILER.briquettes", 860.0),
                "Брикети за добу", "kilograms", 1))
        P(Point("av", 1, "BOILER_SupplySetpoint", self.flag_num("bacnet.BOILER.setpoint", 80.0),
                "Уставка подачі", "degreesCelsius", 0.5,
                write=self.setter_flag("BOILER", "bacnet.BOILER.setpoint", "SupplySetpoint", "boiler")))
        P(Point("bi", 1, "BOILER_K1_Running", lambda: st() in (2, 3), "Котел 1 в роботі"))
        P(Point("bi", 2, "BOILER_K2_Running", lambda: st() == 3, "Котел 2 в роботі"))
        P(Point("bi", 3, "BOILER_Fault", lambda: st() == 4, "Несправність"))
        P(Point("bi", 4, "BOILER_AugerRunning", lambda: bool(self.w.flag("bacnet.BOILER.auger", st() in (2, 3))),
                "Шнек подає"))
        P(Point("bi", 5, "BOILER_SiloLow", lambda: self.num(f"{b}/silo_fill") < 20, "Бункер майже порожній"))
        P(Point("bv", 1, "BOILER_Enable", lambda: bool(self.w.flag("bacnet.BOILER.enable", 1)), "Дозвіл",
                write=self.setter_flag("BOILER", "bacnet.BOILER.enable", "Enable", "boiler")))
        P(Point("msv", 1, "BOILER_State", st, "Стан", states=["standby", "K1", "K1+K2", "fault"]))
        return d

    # --- панель FACP-1 (тільки читання) ---
    def facp(self) -> DeviceDef:
        d = DeviceDef(200, "FACP-1", "Siemens", "Cerberus PRO FC726")
        P = d.points.append
        groups = sorted({c.split("/")[2] for c in self.w.signals if c.startswith("fire/groups/")})
        lay = (self.layout.get("fire") or {}).get("groups") or {}
        order = [g for g in lay if g in groups] + [g for g in groups if g not in lay]
        P(Point("lsz", 0, "FACP-1_Panel", lambda: _lss(self.val("fire/totals/state", 0)),
                "Панель FACP-1, зведений стан", members=list(range(1, len(order) + 1))))
        for z, g in enumerate(order, 1):
            info = lay.get(g, {})
            desc = f"{info.get('zone_name', g)}, {info.get('kind_name', 'сповіщувачі')}, {info.get('n', '?')} сповіщувачів"
            P(Point("lsz", z, g.replace("FA-", "FA-"), (lambda gg=g: _lss(self.val(f"fire/groups/{gg}/state", 0))),
                    desc))
            loop, n = int(info.get("loop", 0) or 0), int(info.get("n", 0) or 0)
            code = g[3:]
            for nn in range(1, n + 1):
                addr = f"{loop}.{code}.{nn:02d}"
                pid = loop * 10000 + z * 100 + nn
                P(Point("lsp", pid, addr, self._lsp_reader(g, addr, nn), f"Сповіщувач {addr}"))
                P(Point("piv", pid, f"{addr}_Contamination", self._dust_reader(g, addr, pid),
                        f"Запиленість сповіщувача {addr}", "percent"))
        for lp in range(1, 5):
            code = f"fire/loops/{lp}/state"
            P(Point("bv", lp, f"FACP-1_Loop{lp}_Fault",
                    (lambda c=code: _truthy(self.val(c, 0)) or str(self.val(c, "")).lower() == "fault"),
                    f"Несправність лінії {lp}"))
        for i, (leaf, nm) in enumerate((("alarms", "ActiveAlarms"), ("faults", "Faults"),
                                        ("disabled", "Disablements")), 1):
            P(Point("piv", i, f"FACP-1_{nm}", (lambda lf=leaf: int(self.num(f"fire/totals/{lf}"))), nm))
        P(Point("bv", 10, "FACP-1_SoundersActive", lambda: _truthy(self.val("fire/totals/sounders_active", 0)),
                "Сирени активні"))
        P(Point("bv", 11, "FACP-1_FireBrigadeTransmitted", lambda: _truthy(self.val("fire/totals/brigade", 0)),
                "Передача на пульт"))
        P(Point("msv", 1, "FACP-1_SystemState", lambda: max(1, min(5, int(self.num("fire/totals/system_state", 1)))),
                "Стан системи", states=["Normal", "Alarm", "Fault", "Test", "Disabled"]))
        return d

    def _lsp_reader(self, g: str, addr: str, nn: int) -> Callable[[], int]:
        def read() -> int:
            pts = self.w.flag("fire.points")
            if isinstance(pts, dict) and addr in pts:
                return _lss(pts[addr])
            zone = _lss(self.val(f"fire/groups/{g}/state", 0))
            trig = self.w.flag("fire.trigger")
            drill = self.w.flag("fire_drill")
            if trig is None and isinstance(drill, dict):
                trig = drill.get("detector")
            if zone in (1, 2, 9) and (trig == addr or (trig is None and nn == 1)):
                return zone
            return 0
        return read

    def _dust_reader(self, g: str, addr: str, pid: int) -> Callable[[], int]:
        base = 5 + zlib.crc32(addr.encode()) % 26  # 5…30 %, детерміновано

        def read() -> int:
            if addr.endswith(".FAC.07") and self.has("fire/groups/FA-FAC/dust"):
                v = self.num("fire/groups/FA-FAC/dust")
                return max(0, min(100, round(v * 100 if v <= 1.0 else v)))
            return base
        return read

    def all(self) -> list[DeviceDef]:
        return [*self.ventilation(), self.boiler(), self.facp()]


# --- локальні об'єкти ------------------------------------------------------------------
class SimGuard:
    """Запис present-value: лише точки з ``write`` (пріоритет 8…16), решта -> writeAccessDenied."""

    _point: Point | None = None
    _on_write: Callable[[], None] | None = None
    _accept: Callable[[], bool] | None = None  # SIM_WRITE_ACCEPT

    async def write_property(self, attr, value, index=None, priority=None):  # type: ignore[no-untyped-def]
        name = self._property_identifier_class(attr).attr if isinstance(attr, int) else attr  # type: ignore[attr-defined]
        p = self._point
        if name != "presentValue" or p is None or p.write is None:
            raise PropertyError("writeAccessDenied")
        if priority is not None and not 8 <= priority <= 16:
            raise PropertyError("writeAccessDenied")
        if self._accept is not None and not self._accept():
            raise PropertyError("writeAccessDenied")
        await super().write_property(attr, value, index, priority)  # type: ignore[misc]
        p.write(_py(value, p))
        if self._on_write is not None:
            self._on_write()


def _py(v: Any, p: Point) -> Any:
    if p.kind in ("bv", "bi"):
        return str(v).lower() in ("active", "1", "true")
    if p.kind == "msv":
        return int(v)
    return float(v)


class SimAI(SimGuard, AnalogInputObject):
    pass


class SimAV(SimGuard, AnalogValueObject):
    _cov_criteria = GenericCriteria


class SimAO(SimGuard, LocalObject, _AnalogOutputObject):
    _cov_criteria = GenericCriteria


class SimBI(SimGuard, BinaryInputObject):
    pass


class SimBV(SimGuard, BinaryValueObject):
    _cov_criteria = GenericCriteria


class SimMSV(SimGuard, MultiStateValueObject):
    pass


class SimLSZ(SimGuard, LocalObject, _LifeSafetyZoneObject):
    _cov_criteria = GenericCriteria


class SimLSP(SimGuard, LocalObject, _LifeSafetyPointObject):
    _cov_criteria = GenericCriteria


class SimPIV(SimGuard, LocalObject, _PositiveIntegerValueObject):
    _cov_criteria = GenericCriteria


OBJ = {"ai": (SimAI, "analogInput"), "ao": (SimAO, "analogOutput"), "av": (SimAV, "analogValue"),
       "bi": (SimBI, "binaryInput"), "bv": (SimBV, "binaryValue"), "msv": (SimMSV, "multiStateValue"),
       "lsz": (SimLSZ, "lifeSafetyZone"), "lsp": (SimLSP, "lifeSafetyPoint"),
       "piv": (SimPIV, "positiveIntegerValue")}


def make_object(p: Point):  # type: ignore[no-untyped-def]
    cls, otype = OBJ[p.kind]
    kw: dict[str, Any] = {"objectIdentifier": (otype, p.inst), "objectName": p.name,
                          "description": p.desc or p.name}
    kw["statusFlags"] = [0, 0, 0, 0]
    kw["eventState"] = "normal"
    kw["outOfService"] = False
    v = p.read()
    if p.kind in ("ai", "ao", "av"):
        kw.update(presentValue=float(_num(v)), units=p.units or "noUnits", covIncrement=float(p.cov))
        if p.kind == "ai":
            kw["reliability"] = "noFaultDetected"
    elif p.kind in ("bi", "bv"):
        kw["presentValue"] = "active" if _truthy(v) else "inactive"
    elif p.kind == "msv":
        kw.update(presentValue=int(v) or 1, numberOfStates=len(p.states or [1]),
                  stateText=list(p.states or []))
    elif p.kind == "piv":
        kw.update(presentValue=int(v), units=p.units or "noUnits")
    elif p.kind in ("lsz", "lsp"):
        kw.update(presentValue=LSS_NAME[int(v)], trackingValue=LSS_NAME[int(v)], mode="on",
                  acceptedModes=["on"], silenced="unsilenced", operationExpected="none",
                  reliability="noFaultDetected")
    obj = cls(**kw)
    obj._point = p
    return obj


def sync_object(obj: Any) -> None:
    p: Point = obj._point
    v = p.read()
    if p.kind in ("ai", "ao", "av"):
        obj.presentValue = float(_num(v))
    elif p.kind in ("bi", "bv"):
        obj.presentValue = "active" if _truthy(v) else "inactive"
    elif p.kind == "msv":
        obj.presentValue = max(1, int(v))
    elif p.kind == "piv":
        obj.presentValue = int(v)
    else:
        obj.presentValue = LSS_NAME[int(v)]
        obj.trackingValue = LSS_NAME[int(v)]


class SimApp(Application):
    """Application, що забороняє службові сервіси (SPEC §8.11.2)."""

    async def do_ReinitializeDeviceRequest(self, apdu):  # type: ignore[no-untyped-def]
        raise ExecutionError(errorClass=ADMIN_DENIED[0], errorCode=ADMIN_DENIED[1])

    async def do_DeviceCommunicationControlRequest(self, apdu):  # type: ignore[no-untyped-def]
        raise ExecutionError(errorClass=ADMIN_DENIED[0], errorCode=ADMIN_DENIED[1])


_seq = iter(range(1, 10 ** 6))


class BacnetServer(ProtocolServer):
    name = "bacnet"

    def __init__(self, world: World, *, address: str = "0.0.0.0:47808", bip_network: int = 1,
                 vnet: int = 2, layout: dict[str, Any] | str | Path | None = None) -> None:
        self.world = world
        self.address = address
        self.bip_network, self.vnet = bip_network, vnet
        self.layout = layout if isinstance(layout, dict) else load_layout(layout)
        self.up = False
        self.defs: dict[int, DeviceDef] = {}
        self.apps: dict[int, Application] = {}
        self.objects: list[Any] = []
        self.router: Application | None = None
        self._links: list[Any] = []
        self._vname = f"f3d-sim-vlan-{vnet}-{next(_seq)}"
        self._unsub: Callable[[], None] | None = None

    @property
    def port(self) -> int:
        m = re.search(r":(\d+)$", self.address)
        return int(m.group(1)) if m else 47808

    def _device_object(self, inst: int, name: str, vendor: str, model: str) -> DeviceObject:
        return DeviceObject(
            objectIdentifier=("device", inst), objectName=name, vendorIdentifier=VENDOR_ID,
            vendorName=vendor, modelName=model, firmwareRevision="sim-0.1",
            applicationSoftwareVersion="sim-0.1", protocolVersion=1, protocolRevision=19,
            maxApduLengthAccepted=1476, segmentationSupported="segmentedBoth",
            description=f"{name} (emulated)")

    async def start(self) -> None:
        # роутер: device 99, BIP-мережа + віртуальна
        VirtualNetwork(self._vname)
        router_dev = self._device_object(ROUTER_INSTANCE, "F3D Sim Router", "F3D", "sim-router")
        self.router = SimApp.from_object_list([router_dev])
        bip = NormalLinkLayer(IPv4Address(self.address))
        self._links.append(bip)
        self.router.nsap.bind(bip, net=self.bip_network, address=IPv4Address(self.address))
        rlink = VirtualLinkLayer(LocalStation(ROUTER_VADDR), self._vname)
        self._links.append(rlink)
        self.router.nsap.bind(rlink, net=self.vnet)
        # пристрої на віртуальній мережі
        for d in Builder(self.world, self.layout).all():
            self.defs[d.instance] = d
            objs = [self._device_object(d.instance, d.name, d.vendor, d.model)]
            for p in d.points:
                o = make_object(p)
                o._on_write = self.sync
                o._accept = self._write_accept
                self.objects.append(o)
                objs.append(o)
            app = SimApp.from_object_list(objs)
            link = VirtualLinkLayer(LocalStation(d.instance), self._vname)
            self._links.append(link)
            app.nsap.bind(link, address=LocalStation(d.instance))
            self.apps[d.instance] = app
        self.world.on_tick(self._on_tick)
        await asyncio.sleep(0)  # дати завершитись _post_init об'єктів
        self.sync()
        self.up = True
        log.info("BACnet/IP %s: роутер net %d -> vnet %d, пристроїв %d, об'єктів %d", self.address,
                 self.bip_network, self.vnet, len(self.apps), len(self.objects))

    def _on_tick(self, _world: World) -> None:
        if self.up:
            self.sync()

    def _write_accept(self) -> bool:
        return bool(getattr(self.world.settings, "write_accept", True))

    def sync(self) -> None:
        """Переносить значення World у локальні об'єкти (викликає COV-детектори)."""
        for o in self.objects:
            try:
                sync_object(o)
            except Exception:  # pragma: no cover - один об'єкт не має валити тік
                log.exception("sync %s", getattr(o, "objectName", "?"))

    async def stop(self) -> None:
        self.up = False
        for link in self._links:
            try:
                link.close()
            except OSError:  # pragma: no cover
                log.debug("link.close", exc_info=True)
        self._links.clear()
        VirtualNetwork._networks.pop(self._vname, None)
        self.apps.clear()
        self.objects.clear()
        self.router = None

    def health(self) -> dict:
        return {"proto": self.name, "up": self.up, "port": self.port, "devices": len(self.apps),
                "objects": len(self.objects)}
