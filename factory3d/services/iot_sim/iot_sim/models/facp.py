"""Пожежна панель FACP-1 і зони FA-* (R-25, SPEC §8.11.1), каскад навчальної тривоги.

Драйвери: ``facp`` (панель FACP-1, агрегат: ``AGGREGATE``) і ``facp_zone`` (кожна зона ``FA-*``:
LSZ, сповіщувачі, запиленість R-09).

* Ключі сигналів FACP-1: ``totals/state``; чотири шлейфи ``1/state``…``4/state``
  (колізія листів, ``base.py``); решта — ``alarms``, ``faults``, ``disabled``, ``system_state``,
  ``sounders_active``, ``brigade``. Значення LSZ: quiet 0, pre-alarm 1, alarm 2, fault 3,
  not-ready 6, test-alarm 9; MSV:1: 1 normal, 2 alarm, 3 fault, 4 test, 5 disabled.
* ``drill_view(world)`` — спільний для моделей каскад (R-25): кроки ``alarm`` (0 с), ``sounders``
  (3), ``vent_stop`` (6), ``dampers`` (9), ``doors`` (12), ``machines`` (20) за прапором
  ``world.flags["fire_drill"]`` (S-07); після зняття прапора / ``phase=="restoring"`` кроки
  знімаються у зворотному порядку за 30 с. Читають: машини (``ExternalEmergency``), ``smoke``,
  ``yard`` (DO4/DO5), ``access`` (20480), вентиляція (``vent_stop`` -> ``BV:1=0``).
* Об'єкти BACnet: ``Facp.lsp_catalog()`` (302 LSP за fire R-23: ``lsp_id``), ``Zone.lsp``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from iot_sim.core.rng import det
from iot_sim.models import register_model
from iot_sim.models.base import AGGREGATE, Model

QUIET, PRE_ALARM, ALARM, FAULT, NOT_READY, TEST_ALARM = 0, 1, 2, 3, 6, 9
RELIABLE, UNRELIABLE = 0, 7
DRILL_STEPS = (
    ("alarm", 0.0),
    ("sounders", 3.0),
    ("vent_stop", 6.0),
    ("dampers", 9.0),
    ("doors", 12.0),
    ("machines", 20.0),
)
RESTORE_OFFSET = {
    "machines": 0.0,
    "doors": 5.0,
    "dampers": 10.0,
    "vent_stop": 15.0,
    "sounders": 20.0,
    "alarm": 25.0,
}  # зворотний порядок, разом 30 с
RESTORE_S = 30.0
PSEUDO_ORDINAL = {"MCP": 90, "SND": 91, "FLM": 92}
DUST_ALARM = 90.0


def lsp_id(loop: int, ordinal: int, nn: int) -> int:
    """fire R-23: ``loop·10000 + ordinal·100 + nn``."""
    if not (1 <= loop <= 8 and 1 <= ordinal <= 99 and 1 <= nn <= 99):
        raise ValueError((loop, ordinal, nn))
    return loop * 10000 + ordinal * 100 + nn


def drill_view(world: Any) -> dict[str, Any] | None:
    """Стан каскаду навчальної/справжньої тривоги на поточний тік (кешується на ``world``)."""
    epoch = world.clock.epoch()
    flag = world.flags.get("fire_drill")
    ckey = (epoch, id(flag), flag.get("phase") if flag else None)
    cache = getattr(world, "_drill_cache", None)
    if cache is not None and cache[0] == ckey:
        return cache[1]  # type: ignore[no-any-return]
    st = getattr(world, "_drill", None)
    if flag:
        t0 = datetime.fromisoformat(flag["t0"]).timestamp()
        if (st is None or st["t0"] != t0) and flag.get("phase") != "restoring":
            st = world._drill = {
                "t0": t0,
                "zone": flag.get("zone"),
                "detector": flag.get("detector"),
                "real": bool(flag.get("real")),
                "restore0": None,
            }
        if st is not None and flag.get("phase") == "restoring" and st["restore0"] is None:
            st["restore0"] = epoch
    elif st is not None and st["restore0"] is None:
        st["restore0"] = epoch  # прапор знято (stop/cleanup) -> відкат
    view = None
    if st is not None:
        rel = None if st["restore0"] is None else epoch - st["restore0"]
        if rel is not None and rel >= RESTORE_S:
            world._drill = None
        else:
            reached = (epoch if rel is None else st["restore0"]) - st["t0"]
            steps = {}
            for name, at in DRILL_STEPS:
                on = reached >= at
                if rel is not None:
                    on = on and rel < RESTORE_OFFSET[name]
                steps[name] = on
            view = {
                "zone": st["zone"],
                "detector": st["detector"],
                "real": st["real"],
                "t": epoch - st["t0"],
                "restoring": rel is not None,
                "steps": steps,
                "id": st["t0"],
            }
    world._drill_cache = (ckey, view)
    return view


def zone_of_machine(zone_code: str | None) -> str | None:
    """``Z-CNC`` -> ``FA-CNC`` (група пожежної зони)."""
    return None if not zone_code else "FA-" + zone_code[2:] if zone_code.startswith("Z-") else zone_code


@register_model("facp_zone")
class FacpZone(Model):
    """Зона FA-*: LSZ ``state``, запиленість сповіщувачів (R-09), несправність (R-25)."""

    def attach(self) -> None:
        p = self.device.params
        self.lsz: int = p.get("lsz", 0)
        self.detectors: list[str] = list(p.get("detectors", []))
        # PIV Contamination для кожного сповіщувача зони: 5…30 %, повільний дрейф (R-09)
        self.contamination = {a: 5.0 + det(a) % 26 for a in self.detectors}
        # детектор, прив'язаний до сигналу ``dust`` (FA-FAC: 2.FAC.07), інакше перший у зоні
        self.main_detector: str | None = p.get("dust_detector") or (self.detectors[0] if self.detectors else None)
        if self.has("dust") and p.get("dust_initial") is not None:
            self.sig("dust").value = float(p["dust_initial"])
        if self.has("dust") and self.main_detector:
            self.contamination[self.main_detector] = float(self.val("dust"))
        self.lsp: dict[str, dict[str, Any]] = {
            a: {"present_value": QUIET, "reliability": RELIABLE} for a in self.detectors
        }
        self.dust_alerted = False
        self.drill_id: float | None = None
        self.state_value = QUIET
        self.loop_fault = False

    # --- збої ---------------------------------------------------------------------------
    @property
    def first_detector(self) -> str | None:
        return self.detectors[0] if self.detectors else None

    @property
    def drill_detector(self) -> str | None:
        """Сповіщувач навчальної тривоги за умовчанням: AC-15 — для FA-CNC це 2.CNC.05 (LSP:21405), інакше перший у
        зоні."""
        pref = {"FA-CNC": "2.CNC.05"}.get(self.device.code)
        return pref if pref in self.detectors else self.first_detector

    def detector_loop(self, addr: str | None = None) -> int:
        a = addr or self.first_detector
        return int(a.split(".")[0]) if a else 1

    def on_fault(self, reason: str, **kw: Any) -> None:
        det_addr = self.main_detector
        loop = self.detector_loop(det_addr)
        if reason == "loop":
            self.loop_fault = True
            self.world.events.emit(
                "fault",
                f"Несправність шлейфу {loop}",
                device=self.device.code,
                payload={"loop": loop, "reason": reason},
            )
        elif reason not in ("comm",):
            self.world.events.emit(
                "fault",
                f"Несправність сповіщувача {det_addr} (зона {self.device.code}, шлейф {loop})",
                device=self.device.code,
                payload={"detector": det_addr, "loop": loop, "reason": reason},
            )

    def on_clear(self) -> None:
        self.loop_fault = False

    # --- тік ----------------------------------------------------------------------------
    def tick(self, dt_s: float) -> None:
        self._dust()
        view = drill_view(self.world)
        alarm = None
        if view and view["zone"] == self.device.code and view["steps"]["alarm"]:
            alarm = ALARM if view["real"] else TEST_ALARM
        fault = self.device.fault in ("sensor", "generic", "loop", "power", "emergency", "spindle")
        if alarm is not None:
            self.state_value = alarm
        elif fault:
            self.state_value = FAULT
        else:
            self.state_value = QUIET
        self.set("state", self.state_value)
        for addr, obj in self.lsp.items():
            pv = QUIET
            if alarm is not None and addr == (view["detector"] or self.drill_detector):  # type: ignore[index]
                pv = alarm
            obj["present_value"] = pv
            bad = self.contamination[addr] > DUST_ALARM or (
                fault and self.device.fault in ("sensor", "generic") and addr == self.main_detector
            )
            obj["reliability"] = UNRELIABLE if bad else RELIABLE

    def _dust(self) -> None:
        code = self.device.code
        if self.has("dust"):
            if code in self.world.maintenance_closed:
                s = self.sig("dust")
                self.world.maintenance_closed.discard(code)
                s.held_until = None
                s.value = s.params["nominal"] if s.params["nominal"] is not None else 0
                if self.main_detector:
                    self.contamination[self.main_detector] = float(s.value)
                self.dust_alerted = False
            else:
                rate = self.sig("dust").params["rate"] or 0.01
                self.set("dust", self.val("dust") + rate * (1 + 0.5 * self.r("dust")) * self.dt_min)
            if self.main_detector:
                self.contamination[self.main_detector] = float(self.val("dust"))
        for addr in self.detectors:
            if not (self.has("dust") and addr == self.main_detector):
                self.contamination[addr] += 0.0005 * (1 + 0.5 * self.world.r(addr)) * self.dt_min
        if self.has("dust"):
            v = float(self.val("dust"))
            if v > DUST_ALARM and not self.dust_alerted:
                self.dust_alerted = True
                self.world.events.emit(
                    "alarm",
                    f"Очистити сповіщувач {self.main_detector} (запиленість {round(v)} %)",
                    device=code,
                    payload={"detector": self.main_detector, "dust_pct": round(v)},
                )
            elif v <= DUST_ALARM:
                self.dust_alerted = False

    def piv(self, addr: str) -> int:
        """PIV:<id LSP> — ціле % (``round()`` моделі R-09)."""
        return round(self.contamination[addr])

    def get_state(self) -> dict[str, Any]:
        return {"contamination": dict(self.contamination), "dust_alerted": self.dust_alerted}

    def set_state(self, d: dict[str, Any]) -> None:
        self.contamination.update(d.get("contamination", {}))
        self.dust_alerted = bool(d.get("dust_alerted"))


@register_model("facp")
class Facp(Model):
    """Панель FACP-1: зведені LSZ:0, PIV 1…3, BV шлейфів/сирен/пульту, MSV:1; каскад R-25."""

    phase = AGGREGATE

    def attach(self) -> None:
        p = self.device.params
        self.mcp: list[str] = list(p.get("mcp", []))
        self.sounders: list[str] = list(p.get("sounders", []))
        self.flame: list[str] = list(p.get("flame", []))
        self.drill_id: float | None = None
        self.sounders_active = False
        self.brigade = False

    def zones(self) -> list[FacpZone]:
        return [d.model for d in self.world.devices.values() if isinstance(d.model, FacpZone)]

    def lsp_catalog(self) -> list[dict[str, Any]]:
        """302 LSP: 222 сповіщувачі + 36 ручних + 3 полум'я + 41 оповіщувач (``piv`` — лише сповіщувачі)."""
        out: list[dict[str, Any]] = []
        for z in self.zones():
            for a in z.detectors:
                loop, _, nn = a.split(".")
                out.append(
                    {
                        "address": a,
                        "id": lsp_id(int(loop), z.lsz, int(nn)),
                        "kind": "detector",
                        "zone": z.device.code,
                        "piv": True,
                    }
                )
        for kind, tag, items in (
            ("mcp", "MCP", self.mcp),
            ("sounder", "SND", self.sounders),
            ("flame", "FLM", self.flame),
        ):
            for a in items:
                loop, _, nn = a.split(".")
                out.append(
                    {
                        "address": a,
                        "id": lsp_id(int(loop), PSEUDO_ORDINAL[tag], int(nn)),
                        "kind": kind,
                        "zone": None,
                        "piv": False,
                    }
                )
        return out

    def tick(self, dt_s: float) -> None:
        zones = self.zones()
        view = drill_view(self.world)
        alarms = sum(1 for z in zones if z.state_value in (ALARM, TEST_ALARM))
        faults = sum(1 for z in zones if z.state_value == FAULT)
        real = any(z.state_value == ALARM for z in zones)
        test = any(z.state_value == TEST_ALARM for z in zones)
        if real:
            total, system = ALARM, 2
        elif test:
            total, system = TEST_ALARM, 4
        elif faults:
            total, system = FAULT, 3
        else:
            total, system = QUIET, 1
        self.set("totals/state", total)
        self.set("system_state", system)
        self.set("alarms", alarms)
        self.set("faults", faults)
        self.set("disabled", 0)
        loops_bad = {1: 0, 2: 0, 3: 0, 4: 0}
        for z in zones:
            if z.loop_fault:
                loops_bad[z.detector_loop()] = 1
        for n, v in loops_bad.items():
            self.set(f"{n}/state", v)
        self.sounders_active = bool(view and view["steps"]["sounders"])
        self.brigade = bool(view and view["real"] and view["steps"]["sounders"])
        self.set("sounders_active", int(self.sounders_active))
        self.set("brigade", int(self.brigade))
        did = view["id"] if view else None
        if did is not None and did != self.drill_id:
            zone = self.world.devices.get(view["zone"]) if view["zone"] else None  # type: ignore[index]
            det_addr = view["detector"] or (zone.model.drill_detector if zone else None)  # type: ignore[attr-defined,index]
            label = "Тривога" if view["real"] else "Навчальна тривога"  # type: ignore[index]
            self.world.events.emit(
                "fire",
                f"{label}: сповіщувач {det_addr}, зона {view['zone']}",
                device=self.device.code,  # type: ignore[index]
                payload={"zone": view["zone"], "detector": det_addr, "real": view["real"]},
            )  # type: ignore[index]
        self.drill_id = did
