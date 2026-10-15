"""Двір: фури, шлагбауми GATE-W/GATE-E, LPR CAM-05/06, автоваги TRUCK-SCALE (R-29, R-30; SPEC §8.13, §10).

Один драйвер ``yard`` для всіх пристроїв двору; спільний контролер ``YardCtl`` (``world._yard``) крокує
фури й ворота (один раз за sim-епоху, першою моделлю), моделі лише публікують свої сигнали.

Джерела фур:

* ``world.trucks`` (API-01 ``bookings[]``): ``{"batch", "truck", "dock", "plate"|None, "scheduled" (ISO),
  "type": "incoming"|"outgoing", "picking", "partner", "lines": [{"product","qty"}] | "cargo_kg",
  "progress": 0…1 (follow_odoo: прогрес ``stock.picking``)}``. Прибуття — ``scheduled − 20 хв`` (incoming)
  або ``− 10 хв`` (outgoing); в'їзд завжди через GATE-W, виїзд через GATE-E (ASSUMPTION R-29).
* ``world.post("yard", {"kind": "truck_no_booking"|"truck_arrival", ...})`` (S-05/S-06).
* За прапором ``shift`` з ``trucks=true`` і порожнього ``world.trucks`` — демо-розклад ``DEMO_BOOKINGS``.

Послідовність: expected -> at_gate -> weigh_in (60 с) -> to_dock (180 с) -> at_dock -> to_exit (120 с) ->
weigh_out (60 с) -> at_gate_out -> left; без бронювання: at_gate -> rejected -> left (``wait_min``).
Шлагбаум відкривається за 5 с після ``cmd_open``/автовідкриття (``Settings.yard_autogate``), закривається
через 15 с після звільнення петлі, тримається відкритим при ``cmd_hold == 1`` (DO4 — лише GATE-W,
DO5 — лише GATE-E, X-47) і на кроці ``doors`` каскаду R-25.
Дані для протоколів: ``YardCtl.trucks``, ``gates``, ``scale()``, ``Yard.outbox`` (LPR-події камер).
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from typing import Any

from iot_sim.core.rng import det
from iot_sim.models import register_model
from iot_sim.models.base import Model
from iot_sim.models.facp import drill_view

TARE_KG = 14000.0
OVERLOAD_KG = 60000.0
OPEN_S, CLOSE_DELAY_S, CLOSING_S = 5.0, 15.0, 5.0
WEIGH_S, TO_DOCK_S, TO_EXIT_S, RAMP_S = 60.0, 180.0, 120.0, 3.0
ARRIVE_BEFORE_S = {"incoming": 20 * 60, "outgoing": 10 * 60}
DEFAULT_UNLOAD_MIN = 40
DEFAULT_CARGO_KG = 11200.0
LIST_NAME = "f3d_bookings"
CAMS = {"GATE-W": "CAM-05", "GATE-E": "CAM-06"}
LAT_TO_CYR = {"A": "А", "B": "В", "E": "Е", "I": "І", "K": "К", "M": "М", "H": "Н", "O": "О", "P": "Р",
              "C": "С", "T": "Т", "X": "Х"}
CYR_TO_LAT = {v: k for k, v in LAT_TO_CYR.items()}
LETTERS = "ABEIKMHOPCTX"
UNIT_KG = (("DSP", 56.0), ("MDF", 70.0), ("HDF", 12.0), ("PAL", 420.0), ("ДСП", 56.0), ("МДФ", 70.0),
           ("ХДФ", 12.0), ("палета", 420.0))
DEMO_BOOKINGS = (
    {"batch": "BATCH/IN/00001", "truck": "TRUCK-IN-1", "dock": "DOCK-W1", "plate": None,
     "type": "incoming", "picking": "WH/IN/00128", "partner": "Постачальник плит (демо)", "hhmm": (6, 50),
     "lines": [{"product": "DSP16-SON", "qty": 120}, {"product": "DSP16-WHT", "qty": 80}]},
    {"batch": "BATCH/OUT/00004", "truck": "TRUCK-OUT-1", "dock": "DOCK-E2", "plate": "АА4512КТ",
     "type": "outgoing", "picking": "WH/OUT/00413", "partner": "Меблі Дім (демо)", "hhmm": (13, 0),
     "lines": [{"product": "PAL-FG", "qty": 12}]},
)


def to_cyr(plate: str) -> str:
    return "".join(LAT_TO_CYR.get(c, c) for c in plate)


def to_lat(plate: str) -> str:
    return "".join(CYR_TO_LAT.get(c, c) for c in plate)


def gen_plate(truck: str) -> str:
    """X-49: ``AA`` + 4 цифри + 2 літери з ``det(truck)`` (кириличний запис)."""
    h = det(truck)
    return to_cyr(f"AA{h % 10000:04d}{LETTERS[(h // 10000) % len(LETTERS)]}{LETTERS[(h // 120000) % len(LETTERS)]}")


def unit_mass(product: str) -> float:
    p = product.upper() if product.isascii() else product
    for pref, kg in UNIT_KG:
        if p.startswith(pref.upper() if pref.isascii() else pref) or pref in p:
            return kg
    return 0.5  # фурнітура/крайка/ЛФМ: 0,02…1,2 кг/од — ASSUMPTION середнє


def cargo_kg(booking: dict[str, Any]) -> float:
    if booking.get("cargo_kg") is not None:
        return float(booking["cargo_kg"])
    lines = booking.get("lines")
    if not lines:
        return DEFAULT_CARGO_KG
    return sum(float(ln.get("qty", 0)) * float(ln.get("kg") or unit_mass(str(ln.get("product", "")))) for ln in lines)


def lpr_payload(cam: str, gate: str, truck: dict[str, Any], car_state: str, now: datetime) -> dict[str, Any]:
    """Тіло HTTP POST Axis LPV (§8.13.2); ``capture_timestamp`` = ``sim_now`` у мс UNIX (X-48)."""
    ms = round(now.timestamp() * 1000)
    plate = truck["plate"]
    booked = truck["booked"]
    return {
        "packetCounter": str(truck["seq"]), "capture_timestamp": str(ms), "frame_timestamp": str(ms),
        "capture_ts": str(ms * 1_000_000), "datetime": now.strftime("%Y%m%d %H%M%S") + f"{now.microsecond // 1000:03d}",
        "plateText": to_lat(plate), "plateUnicode": plate, "plateUTF8": plate, "plateASCII": to_lat(plate),
        "plateCountry": "UKR", "plateISO3166-2": "UA", "plateRegion": "", "plateRegionCode": "",
        "plateList": LIST_NAME if booked else "", "plateListMode": "allow" if booked else "none",
        "plateListDescription": (f"{truck['batch']} {truck['dock']} {truck.get('partner') or ''}".strip()
                                 if booked else ""),
        "plateConfidence": "0.912340", "carState": car_state, "roiID": "1",
        "carMoveDirection": "in" if gate == "GATE-W" else "out", "carID": str(truck["seq"]),
        "GEOtarget": gate, "sensorProviderID": cam,
        "vehicle_info": {"view": "front", "type": "TRUCK", "color": "WHITE"},
    }


class YardCtl:
    def __init__(self, world: Any) -> None:
        self.world = world
        self.trucks: list[dict[str, Any]] = []
        self.known: set[str] = set()
        self.gates: dict[str, dict[str, Any]] = {
            g: {"state": "closed", "t": 0.0, "free_at": None, "passes": 0, "loop": False, "pulse": None,
                "close_cmd": False} for g in CAMS}
        self.epoch_key: tuple[float, int] | None = None
        self.seq = 0
        self.lpr_out: dict[str, deque[dict[str, Any]]] = {c: deque(maxlen=500) for c in CAMS.values()}
        self.drill_hold: dict[str, bool] = dict.fromkeys(CAMS, False)
        self.demo_loaded = False
        self.day: Any = None

    # --- налаштування ---------------------------------------------------------------------
    @property
    def autogate(self) -> bool:
        return bool(getattr(self.world.settings, "yard_autogate", True))

    def now_dt(self, epoch: float) -> datetime:
        return datetime.fromtimestamp(epoch, self.world.clock.tz)

    # --- створення фур --------------------------------------------------------------------
    def make_truck(self, booking: dict[str, Any], arrival: float, booked: bool = True, gate: str = "GATE-W",
                   unload_min: float | None = None, run_id: str | None = None, wait_min: float = 10,
                   plate: str | None = None) -> dict[str, Any]:
        self.seq += 1
        code = booking.get("truck") or booking.get("code") or f"TRUCK-{'OUT' if booking.get('type') == 'outgoing' else 'IN'}-{self.seq}"
        incoming = booking.get("type", "incoming") != "outgoing"
        cargo = cargo_kg(booking)
        t = {"seq": self.seq, "id": code, "batch": booking.get("batch", ""), "picking": booking.get("picking"),
             "dock": booking.get("dock", "DOCK-W1"), "partner": booking.get("partner"), "kind":
             "incoming" if incoming else "outgoing", "plate": plate or booking.get("plate") or gen_plate(code),
             "booked": booked, "state": "expected", "t": arrival, "arrival": arrival, "gate_in": gate,
             "cargo_kg": cargo, "gross_kg": TARE_KG + cargo, "tare_kg": TARE_KG,
             "unload_min": unload_min if unload_min is not None else DEFAULT_UNLOAD_MIN,
             "run_id": run_id, "wait_s": wait_min * 60, "req": None, "booking": booking, "unloaded_pct": 0.0,
             "history": [("expected", arrival)]}
        self.trucks.append(t)
        return t

    def _sync_bookings(self, now: datetime) -> None:
        w = self.world
        src = w.trucks
        if not src and not self.demo_loaded:
            sh = w.flags.get("shift")
            if isinstance(sh, dict) and sh.get("trucks", True):
                self.demo_loaded = True
                base = datetime.combine(now.date(), datetime.min.time(), tzinfo=now.tzinfo)
                src = [dict(b, scheduled=(base + timedelta(hours=b["hhmm"][0], minutes=b["hhmm"][1])).isoformat())  # type: ignore[arg-type,index]
                       for b in DEMO_BOOKINGS]
                w.trucks.extend(src)
        for b in list(w.trucks):
            key = b.get("batch") or b.get("picking") or b.get("truck")
            if key in self.known:
                continue
            self.known.add(key)
            sched = b.get("scheduled")
            if sched is None:
                continue
            dt = datetime.fromisoformat(sched) if isinstance(sched, str) else sched
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=now.tzinfo)
            kind = "outgoing" if b.get("type") == "outgoing" else "incoming"
            self.make_truck(b, dt.timestamp() - ARRIVE_BEFORE_S[kind])

    def _commands(self, now: datetime) -> None:
        w = self.world
        for cmd in w.drain("yard"):
            ep = now.timestamp()
            if cmd.get("kind") == "truck_no_booking":
                self.make_truck({"truck": None, "type": "incoming", "batch": "", "dock": ""}, ep, booked=False,
                                gate=cmd.get("gate") or "GATE-W", run_id=cmd.get("run_id"),
                                wait_min=cmd.get("wait_min") or 10,
                                plate=to_cyr(cmd["plate"]) if cmd.get("plate") else None)
            elif cmd.get("kind") == "truck_arrival":
                ref = cmd.get("booking")
                waiting = next((t for t in self.trucks if t["state"] == "rejected"
                                and cmd.get("plate") and t["plate"] == to_cyr(cmd["plate"])), None)
                if waiting is not None:  # бронювання з'явилось: фуру біля воріт впускають
                    waiting["admit"] = True
                    continue
                b = next((x for x in w.trucks if ref in (x.get("batch"), x.get("picking"))), None)
                if b is None:
                    b = {"batch": ref, "picking": ref, "type": "outgoing" if "OUT" in str(ref) else "incoming",
                         "dock": "DOCK-W1" if "IN" in str(ref) else "DOCK-E2"}
                at = cmd.get("at")
                arrival = (datetime.fromisoformat(at) if isinstance(at, str) else at or now).timestamp()
                self.make_truck(b, arrival, run_id=cmd.get("run_id"), unload_min=cmd.get("unload_min"),
                                plate=to_cyr(cmd["plate"]) if cmd.get("plate") else None)

    # --- ворота ---------------------------------------------------------------------------
    def open_request(self, gate: str, at: float) -> None:
        g = self.gates[gate]
        if g["state"] in ("closed", "closing"):
            g["state"], g["t"] = "opening", at
        g["free_at"] = None

    def hold(self, gate: str) -> bool:
        dev = self.world.devices.get(gate)
        return bool(dev is not None and dev.signals.get("cmd_hold") is not None
                    and dev.signals["cmd_hold"].value in (1, True))

    def _pulses(self, epoch: float) -> None:
        for gate, g in self.gates.items():
            dev = self.world.devices.get(gate)
            if dev is None:
                continue
            for cmd in ("cmd_open", "cmd_close"):
                s = dev.signals.get(cmd)
                if s is not None and s.value in (1, True):
                    s.value, s.held_until = 0, None  # імпульс прийнято
                    if cmd == "cmd_open":
                        g["pulse"] = epoch
                        self.open_request(gate, epoch)
                        if not self._waiting(gate):
                            g["free_at"] = epoch + OPEN_S
                    else:
                        g["close_cmd"] = True

    def _waiting(self, gate: str) -> bool:
        return any((tr["state"] in ("at_gate", "rejected") and tr["gate_in"] == gate)
                   or (tr["state"] == "at_gate_out" and gate == "GATE-E") for tr in self.trucks)

    def _drill_hold(self) -> None:
        """R-25 +12 с: DO4 і DO5 = 1 (окремі канали); знімаються разом із відкатом каскаду."""
        view = drill_view(self.world)
        want = bool(view and view["steps"]["doors"])
        for gate in self.gates:
            dev = self.world.devices.get(gate)
            if dev is None or "cmd_hold" not in dev.signals:
                continue
            if want and not self.drill_hold[gate]:
                self.drill_hold[gate] = True
                dev.signals["cmd_hold"].value = 1
            elif not want and self.drill_hold[gate]:
                self.drill_hold[gate] = False
                dev.signals["cmd_hold"].value = 0

    def _gate_tick(self, gate: str, epoch: float) -> None:
        g = self.gates[gate]
        hold = self.hold(gate)
        if g["state"] == "open" and g["free_at"] is None and not g["loop"]:
            g["free_at"] = epoch
        for _ in range(4):
            if g["state"] == "opening" and epoch >= g["t"] + OPEN_S:
                g["state"], g["t"] = "open", g["t"] + OPEN_S
            elif g["state"] == "open" and not hold and not g["loop"] and (
                    (g["free_at"] is not None and epoch >= g["free_at"] + CLOSE_DELAY_S) or g["close_cmd"]):
                g["state"], g["t"] = "closing", (g["free_at"] + CLOSE_DELAY_S if g["free_at"] and not g["close_cmd"]
                                                else epoch)
                g["close_cmd"] = False
            elif g["state"] == "closing" and epoch >= g["t"] + CLOSING_S:
                g["state"], g["t"] = "closed", g["t"] + CLOSING_S
            elif hold and g["state"] in ("closed", "closing"):
                g["state"], g["t"] = "opening", epoch
            else:
                break
        g["close_cmd"] = False

    # --- фури -----------------------------------------------------------------------------
    def _event(self, truck: dict[str, Any], msg: str, **payload: Any) -> None:
        self.world.events.emit("yard", msg, device=truck["id"], payload={"truck": truck["id"],
                                                                        "state": truck["state"], **payload})

    def _lpr(self, truck: dict[str, Any], gate: str, car_state: str, epoch: float) -> None:
        cam = CAMS[gate]
        payload = lpr_payload(cam, gate, truck, car_state, self.now_dt(epoch))
        self.lpr_out[cam].append(payload)
        # контракт з LprPusher: подія yard з payload["lpr"] (тіло Axis LPV)
        self.world.events.emit("yard", f"LPR {payload['plateText']} {car_state}", device=cam,
                               payload={"lpr": payload, "truck": truck["id"]})
        dev = self.world.devices.get(cam)
        if dev is not None and car_state == "new" and "plate" in dev.signals:
            dev.signals["plate"].set(payload["plateText"], self.world.now())

    def _to(self, truck: dict[str, Any], state: str, t: float) -> None:
        truck["state"], truck["t"] = state, t
        truck["history"].append((state, t))

    def _pass_gate(self, truck: dict[str, Any], gate: str, t: float) -> None:
        g = self.gates[gate]
        g["passes"] += 1
        g["free_at"] = t

    def _advance(self, tr: dict[str, Any], epoch: float) -> None:
        for _ in range(16):
            st, t = tr["state"], tr["t"]
            if st == "expected":
                if epoch < tr["arrival"]:
                    return
                self._to(tr, "at_gate", tr["arrival"])
                self._lpr(tr, tr["gate_in"], "new", tr["arrival"])
                self._event(tr, f"Фура {tr['plate']} біля воріт {tr['gate_in']}")
                if not tr["booked"]:
                    self._to(tr, "rejected", tr["arrival"])
                    self._event(tr, f"Фура {tr['plate']} без бронювання біля воріт в'їзду", level="warn")
            elif st == "at_gate":
                g = self.gates[tr["gate_in"]]
                if tr["req"] is None:
                    if self.autogate:
                        tr["req"] = t
                    elif g["pulse"] is not None and g["pulse"] >= t:
                        tr["req"] = g["pulse"]
                    else:
                        return
                    self.open_request(tr["gate_in"], tr["req"])  # type: ignore[arg-type]
                if epoch < tr["req"] + OPEN_S:
                    return
                self._pass_gate(tr, tr["gate_in"], tr["req"] + OPEN_S)
                self._to(tr, "weigh_in", tr["req"] + OPEN_S)
                self._event(tr, f"Фура {tr['plate']}: ваги (в'їзд)")
            elif st == "rejected":
                if tr.pop("admit", False):
                    self._to(tr, "at_gate", t)
                    tr["booked"], tr["req"] = True, None
                    continue
                if epoch < t + tr["wait_s"]:
                    return
                self._to(tr, "left", t + tr["wait_s"])
                self._lpr(tr, tr["gate_in"], "lost", t + tr["wait_s"])
                self._event(tr, f"Фура {tr['plate']} поїхала без в'їзду")
            elif st in ("weigh_in", "weigh_out"):
                if epoch < t + WEIGH_S:
                    return
                if st == "weigh_in":
                    self._to(tr, "to_dock", t + WEIGH_S)
                else:
                    self._to(tr, "at_gate_out", t + WEIGH_S)
                    self._lpr(tr, "GATE-E", "new", t + WEIGH_S)
            elif st == "to_dock":
                if epoch < t + TO_DOCK_S:
                    return
                self._to(tr, "at_dock", t + TO_DOCK_S)
                self._event(tr, f"Фура {tr['plate']} біля дока {tr['dock']}")
            elif st == "at_dock":
                prog = tr["booking"].get("progress") if self.world.mode == "follow_odoo" else None
                if prog is not None:
                    tr["unloaded_pct"] = round(100 * float(prog), 1)
                    if prog < 1:
                        return
                    end = epoch
                else:
                    span = tr["unload_min"] * 60
                    tr["unloaded_pct"] = round(min(100.0, 100 * (epoch - t) / span), 1) if span else 100.0
                    if epoch < t + span:
                        return
                    end = t + span
                tr["unloaded_pct"] = 100.0
                self._to(tr, "to_exit", end)
            elif st == "to_exit":
                if epoch < t + TO_EXIT_S:
                    return
                self._to(tr, "weigh_out", t + TO_EXIT_S)
            elif st == "at_gate_out":
                if tr.get("req_out") is None:
                    tr["req_out"] = t
                    self.open_request("GATE-E", t)
                if epoch < tr["req_out"] + OPEN_S:
                    return
                self._pass_gate(tr, "GATE-E", tr["req_out"] + OPEN_S)
                self._to(tr, "left", tr["req_out"] + OPEN_S)
                self._lpr(tr, "GATE-E", "lost", tr["t"])
                self._event(tr, f"Фура {tr['plate']} виїхала")
                if tr["run_id"]:
                    self.world.run_results[tr["run_id"]] = {
                        "gross_kg": int(tr["gross_kg"]), "tare_kg": int(tr["tare_kg"]), "dock": tr["dock"],
                        "unloaded_pct": int(tr["unloaded_pct"])}
            else:
                return

    def step(self) -> None:
        w = self.world
        epoch = w.clock.epoch()
        key = (epoch, w.tick_count)
        if self.epoch_key == key:
            return
        self.epoch_key = key
        now = w.now()
        self._sync_bookings(now)
        self._commands(now)
        self._drill_hold()
        self._pulses(epoch)
        for tr in self.trucks:
            self._advance(tr, epoch)
        for gate, g in self.gates.items():
            g["loop"] = self._waiting(gate)
            self._gate_tick(gate, epoch)
        if self.day != now.date():
            if self.day is not None:
                for g in self.gates.values():
                    g["passes"] = 0
            self.day = now.date()
        # відпрацьованих фур не накопичуємо безмежно
        if len(self.trucks) > 200:
            self.trucks = [t for t in self.trucks if t["state"] != "left"][-100:]

    # --- ваги -----------------------------------------------------------------------------
    def scale(self) -> tuple[float, bool, bool]:
        """(вага кг, стабільна, перевантаження) за R-30."""
        epoch = self.world.clock.epoch()
        r = self.world.r("yard/scale/TRUCK-SCALE/weight_kg")
        jitter = round(r) * 20.0
        for tr in self.trucks:
            if tr["state"] in ("weigh_in", "weigh_out"):
                incoming = tr["kind"] == "incoming"
                target = tr["gross_kg"] if (tr["state"] == "weigh_in") == incoming else tr["tare_kg"]
                dt = epoch - tr["t"]
                if dt < RAMP_S:
                    return round(target * max(0.0, dt) / RAMP_S / 20) * 20.0, False, False
                w = target + jitter
                return w, True, w > OVERLOAD_KG
        return jitter, True, False


def ctl(world: Any) -> YardCtl:
    c = getattr(world, "_yard", None)
    if c is None:
        c = world._yard = YardCtl(world)
    return c


@register_model("yard")
class Yard(Model):
    """Публікує сигнали свого пристрою зі стану ``YardCtl`` (GATE-*, CAM-*, TRUCK-SCALE)."""

    @property
    def ctl(self) -> YardCtl:
        return ctl(self.world)

    @property
    def outbox(self) -> deque[dict[str, Any]]:
        """LPR-події камери (CAM-05/06) для HTTP-push; споживач забирає ``popleft()``."""
        return self.ctl.lpr_out[self.device.code]

    def tick(self, dt_s: float) -> None:
        c = self.ctl
        c.step()
        code = self.device.code
        if code in c.gates:
            g = c.gates[code]
            self.set("state", int(g["state"] == "open"))
            self.set("loop", int(g["loop"]))
            self.set("passes_today", g["passes"])
            self.set("photocell", 0)
        elif code == "TRUCK-SCALE":
            w, stable, over = c.scale()
            self.overload = over
            self.set("weight_kg", w)
            self.set("stable", int(stable))

    def get_state(self) -> dict[str, Any]:
        if self.device.code != "TRUCK-SCALE":
            return {}
        c = self.ctl
        return {"seq": c.seq, "passes": {k: v["passes"] for k, v in c.gates.items()}}

    def set_state(self, d: dict[str, Any]) -> None:
        if self.device.code == "TRUCK-SCALE" and d:
            c = self.ctl
            c.seq = d.get("seq", 0)
            for k, n in d.get("passes", {}).items():
                c.gates[k]["passes"] = n
