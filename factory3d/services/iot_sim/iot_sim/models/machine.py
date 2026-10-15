"""Верстат-РЦ (R-02, R-14…R-17; SPEC §8.3, §8.4.2, §10): драйвер ``machine`` (P-01, OPC UA).

Джерела завдань (контракт з ядром/follow_odoo):

* ``world.jobs`` — список словників, по одному на завдання; ключі: ``workcenter`` (код РЦ), ``state``
  (Odoo: ``pending|waiting|ready|progress|done|cancel``; ``blocked: true`` -> Interrupted/Held),
  ``wo_id`` (id ``mrp.workorder`` -> ``WO%05d``) або ``job_order_id`` (``cj-…``) або ``id`` рядком;
  ``name``, ``qty``, ``qty_produced``, ``duration_expected`` (хв), ``order`` (``WH/MO/00231``),
  ``origin`` (``odoo|sim``). У ``scenario`` порожній РЦ у зміні отримує синтетичне ``SIM-%05d``
  (планувальник S-01, R-17); завершене завдання лишається ``Ended/Completed`` до початку зміни.
* ``world.workcenters[code]`` — ``{"working_state": "blocked"|…}`` (Odoo ``mrp.workcenter``).
* ``world.flags["shift"]`` (S-01): ``speed`` множить темп завдань і лічильник деталей.

``kwh_total``/``kwh_shift`` споживача веде ``meter`` (R-03); тут лише ``p_now``.
Публічні атрибути для протоколів: ``flags`` (прапори §7.7), ``current_state``, ``values``
(лічильники/часи), ``job_list()`` (JobOrderList). ``IoMachine`` (``io_machine``, P-02) — той самий
автомат, але ``state``/``alarm`` віддаються бітом DI (``di_run``/``di_fault``).
"""
from __future__ import annotations

import math
import re
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model
from iot_sim.models.facp import drill_view, zone_of_machine

OFFLINE, STANDBY, READY, WORKING, ERROR = 0, 1, 2, 3, 4
STATE_NAMES = ("OFFLINE", "STANDBY", "READY", "WORKING", "ERROR")
MODE_AUTOMATIC, MODE_MANUAL, MODE_SLEEP = 1, 3, 5
IDLE_DEMO = frozenset({"SAW-3", "VSAW-1", "EDGE-3", "UV-1", "ASM-5"})  # демо 10:30: READY (простій)
MANUAL_PREFIXES = ("ASM-", "SLIDE-")
JOB_QTY = 60  # ASSUMPTION: розмір синтетичного завдання, шт
# MessageId каталогу §8.3.3: reason -> (id, категорія, ім'я, текст)
MESSAGES = {
    "spindle": ("E0421", "ERROR", "SpindleOverload", "Помилка шпинделя осі Z"),
    "emergency": ("A0201", "ALARM", "EmergencyStop", "Аварійна зупинка (кнопка 1)"),
    "power": ("E0430", "ERROR", "PowerLost", "Втрата живлення"),
    "generic": ("E0400", "ERROR", "GeneralError", "Загальна помилка верстата"),
    "sensor": ("A0202", "ALARM", "AxisCommLost", "Втрата зв'язку з приводом осі"),
    "loop": ("E0440", "ERROR", "GuardOpen", "Відкрито огородження"),
}
ISA_STATES = {"pending": ("NotAllowedToStart", None), "waiting": ("NotAllowedToStart", None),
              "ready": ("AllowedToStart", None), "progress": ("Running", None),
              "done": ("Ended", "Completed"), "cancel": ("Ended", "Cancelled")}
_ID_RE = re.compile(r"^(WO\d+|SIM-\d+|cj-.+)$")


def compute_state(on: bool, init: bool, energy_saving: bool, error: bool, calibrated: bool,
                  recipe: bool) -> int:
    """``CurrentState`` строго за логікою §7.7 (R-14)."""
    if not on:
        return OFFLINE
    if not init or energy_saving or (not error and not calibrated):
        return STANDBY
    if error:
        return ERROR
    return WORKING if recipe else READY


def job_order_id(job: dict[str, Any]) -> str | None:
    """``WO%05d`` з id ``mrp.workorder``; ``cj-…`` (випуск ``/jobs``); ``SIM-%05d`` синтетичне."""
    if job.get("job_order_id"):
        return str(job["job_order_id"])
    if job.get("wo_id") is not None:
        return f"WO{int(job['wo_id']):05d}"
    jid = job.get("id")
    if isinstance(jid, int):
        return f"WO{jid:05d}"
    if isinstance(jid, str) and _ID_RE.match(jid):
        return jid
    return None


def isa95_state(job: dict[str, Any]) -> tuple[str, str | None]:
    """Стан Odoo -> ISA-95 (§8.3.2): ``progress + blocked -> Interrupted/Held``."""
    st = job.get("state", "pending")
    if st == "progress" and job.get("blocked"):
        return "Interrupted", "Held"
    return ISA_STATES.get(st, ("NotAllowedToStart", None))


@register_model("machine")
class Machine(Model):
    kind = "opcua"

    def attach(self) -> None:
        p = self.device.params
        self.zone: str | None = p.get("zone")
        self.per_unit: float = float(p.get("per_unit") or 1.5)
        pn = self.sig("p_now").params if self.has("p_now") else {}
        p_inst = float(p.get("p_inst") or 0)
        self.nominal = pn.get("nominal") if pn.get("nominal") is not None else 0.55 * p_inst
        self.rate = pn.get("rate") if pn.get("rate") is not None else 0.08 * p_inst
        self.noise = pn.get("noise") if pn.get("noise") is not None else 0.08
        self.flags: dict[str, bool] = dict.fromkeys(
            ("MachineOn", "MachineInitialized", "PowerPresent", "Emergency", "Calibrated", "Error",
             "Alarm", "Warning", "RecipeInRun", "EnergySaving", "ExternalEmergency"), False)
        self.flags["Calibrated"] = True
        self.current_state = OFFLINE
        self.pieces_acc = 0.0
        self.pieces_in = 0
        self.values: dict[str, float] = {
            k: 0.0 for k in ("MachineOnTime", "ProductionTime", "WorkingTime", "StandbyTime", "ReadyTime",
                             "ErrorTime", "PowerPresentTime", "PiecesOut", "PiecesIn", "RunsGood",
                             "RunsTotal")}
        self.relative: dict[str, float] = dict(self.values)
        self.shift_key: Any = None
        self.msg_id = ""
        self.fault_msg: tuple[str, str, str, str] | None = None
        self.mode = MODE_SLEEP

    # --- прапори значення сигналів (P-01: Boolean/enum; P-02: біти) ---------------------
    def flag_value(self, b: bool) -> Any:
        return bool(b)

    def state_value(self, cs: int) -> Any:
        return cs

    # --- завдання -----------------------------------------------------------------------
    def my_jobs(self) -> list[dict[str, Any]]:
        code = self.device.code
        return [j for j in self.world.jobs if j.get("workcenter") == code]

    def active_job(self) -> dict[str, Any] | None:
        return next((j for j in self.my_jobs() if j.get("state") == "progress"), None)

    def job_list(self) -> list[dict[str, Any]]:
        """JobOrderList §8.3.2: ``JobOrderID``, ``State``/``SubState``, час, кількість."""
        out = []
        for j in self.my_jobs():
            st, sub = isa95_state(j)
            out.append({"JobOrderID": job_order_id(j), "State": st, "SubState": sub,
                        "Description": j.get("name", ""), "PlannedOrderQuantity": j.get("qty"),
                        "OrderNumbers": [j["order"]] if j.get("order") else [],
                        "StartTime": j.get("started"), "EndTime": j.get("ended")})
        return out

    def _next_sim_id(self) -> str:
        w = self.world
        used = [int(str(j["id"])[4:]) for j in w.jobs if str(j.get("id", "")).startswith("SIM-")]
        n = max([getattr(w, "_sim_seq", 0), *used]) + 1
        w._sim_seq = n
        return f"SIM-{n:05d}"

    def _speed(self) -> float:
        sh = self.world.flags.get("shift")
        return float(sh.get("speed", 1.0)) if isinstance(sh, dict) else 1.0

    def _plan(self, in_shift: bool, blocked: bool) -> None:
        """Планувальник (R-17): синтетичне завдання, старт ``ready``, завершення за тривалістю."""
        jobs = self.my_jobs()
        job = self.active_job()
        now_ep = self.world.clock.epoch()
        if job is not None and job.get("origin") == "sim" and not blocked:
            job["elapsed_s"] = job.get("elapsed_s", 0.0) + self.dt_s * self._speed()
            if job["elapsed_s"] >= job["duration_expected"] * 60:
                job.update(state="done", ended=self.world.now().isoformat(), qty_produced=job["qty"])
                self.relative["RunsGood"] += 1
                self.relative["RunsTotal"] += 1
                self.world.events.emit("info", f"Завдання {job_order_id(job)} завершено, деталей {job['qty']}",
                                       device=self.device.code, payload={"message_id": "I0002"})
                job = None
        if job is None and in_shift and self.world.mode == "scenario" and not blocked:
            ready = next((j for j in self.my_jobs() if j.get("state") == "ready"), None)
            if ready is not None:
                ready["state"], ready["started"] = "progress", self.world.now().isoformat()
            elif self.device.code not in IDLE_DEMO and not any(
                    j.get("state") in ("ready", "progress", "pending", "waiting") for j in jobs):
                qty = JOB_QTY
                self.world.jobs.append({
                    "id": self._next_sim_id(), "workcenter": self.device.code, "state": "progress",
                    "name": "Операція", "qty": qty, "qty_produced": 0, "origin": "sim",
                    "duration_expected": 15 + self.per_unit * qty, "elapsed_s": 0.0,
                    "started": self.world.now().isoformat(), "t": now_ep})

    def _new_shift(self) -> None:
        """Початок зміни: прибрати завершені завдання, обнулити ``Relative*`` (R-16)."""
        code = self.device.code
        self.world.jobs[:] = [j for j in self.world.jobs
                              if not (j.get("workcenter") == code and j.get("state") in ("done", "cancel"))]
        for k in ("PiecesOut", "PiecesIn", "RunsGood", "RunsTotal"):
            self.values[k] += self.relative[k]  # Absolute* — ніколи не обнуляються
        self.pieces_acc = 0.0
        self.pieces_in = 0
        self.relative = dict.fromkeys(self.relative, 0.0)

    # --- тік ----------------------------------------------------------------------------
    def tick(self, dt_s: float) -> None:
        w = self.world
        now = w.now()
        code = self.device.code
        in_shift = w.shift.in_shift(now)
        key = (now.date(), in_shift)
        if in_shift and key != self.shift_key:
            self._new_shift()
        self.shift_key = key
        wc = w.workcenters.get(code, {})
        blackout = w.flags.get("blackout")
        power = not (isinstance(blackout, dict) and blackout.get("phase") == "outage") \
            and self.device.fault != "power"
        blocked = wc.get("working_state") == "blocked"
        view = drill_view(w)
        ext_emergency = bool(view and view["steps"]["machines"]
                             and view["zone"] == zone_of_machine(self.zone))
        error = (self.device.fault not in (None, "comm")) or blocked or not power or ext_emergency
        self._plan(in_shift, error)
        task = self.active_job() is not None
        f = self.flags
        f["MachineOn"] = in_shift or task
        f["MachineInitialized"] = f["MachineOn"]
        f["PowerPresent"] = power
        f["Calibrated"] = True
        f["ExternalEmergency"] = ext_emergency
        f["Emergency"] = self.device.fault == "emergency" or ext_emergency
        f["Error"] = error
        f["Alarm"] = error
        f["RecipeInRun"] = task and not error
        f["EnergySaving"] = not in_shift and not task
        cs = compute_state(f["MachineOn"], f["MachineInitialized"], f["EnergySaving"], f["Error"],
                           f["Calibrated"], f["RecipeInRun"])
        if self.device.fault == "comm":
            cs = OFFLINE
        self.current_state = cs
        self._power(cs)
        self._counters(cs, dt_s)
        self._publish(cs)

    def _power(self, cs: int) -> None:
        if cs == WORKING:
            p = self.nominal * (1 + self.noise * self.r("p_now"))
        elif cs == READY:
            p = self.rate * (1 + 0.05 * self.r("p_now"))
        else:
            p = 0.0
        self.p_now = p
        self.set("p_now", p)

    def _counters(self, cs: int, dt_s: float) -> None:
        for name, on in (("MachineOnTime", cs != OFFLINE), ("WorkingTime", cs == WORKING),
                         ("ProductionTime", cs == WORKING), ("StandbyTime", cs == STANDBY),
                         ("ReadyTime", cs == READY), ("ErrorTime", cs == ERROR),
                         ("PowerPresentTime", self.flags["PowerPresent"])):
            if on:
                self.values[name] += dt_s
                self.relative[name] += dt_s
        if cs == WORKING:
            self.pieces_acc += self._speed() * dt_s / (60 * self.per_unit)
        job = self.active_job()
        done = math.floor(self.pieces_acc)
        if job is not None and self.world.mode == "follow_odoo":
            done = max(done, int(job.get("qty_produced") or 0))
            self.pieces_acc = max(self.pieces_acc, float(done))
        self.pieces_in = done + (1 if cs == WORKING else 0)
        self.relative["PiecesOut"], self.relative["PiecesIn"] = done, self.pieces_in

    def _publish(self, cs: int) -> None:
        self.mode = MODE_SLEEP if cs in (OFFLINE, STANDBY) else (
            MODE_MANUAL if self.device.code.startswith(MANUAL_PREFIXES) else MODE_AUTOMATIC)
        self.set("state", self.state_value(cs))
        self.set("mode", self.mode)
        self.set("alarm", self.flag_value(self.flags["Alarm"]))
        self.set("pieces_out", int(self.relative["PiecesOut"]))
        job = self.active_job() or next(
            (j for j in self.my_jobs() if j.get("state") == "ready"), None)
        jid = job_order_id(job) if job else ""
        self.set("job", jid or "")
        self.set("event", self.msg_id)

    # --- збої (R-15) --------------------------------------------------------------------
    def on_fault(self, reason: str, **kw: Any) -> None:
        if reason == "comm":
            return
        mid, cat, name, text = MESSAGES.get(reason, MESSAGES["generic"])
        self.fault_msg = (mid, cat, name, text)
        self.msg_id = mid
        self.world.events.emit(
            "alarm" if cat == "ALARM" else "fault", f"{self.device.code}: {text}", device=self.device.code,
            payload={"message_id": mid, "category": cat, "message_name": name, "reason": reason,
                     "arguments": kw})

    def on_clear(self) -> None:
        self.fault_msg = None
        self.msg_id = ""

    # --- знімок -------------------------------------------------------------------------
    def get_state(self) -> dict[str, Any]:
        return {"pieces_acc": self.pieces_acc, "values": self.values,
                "relative": self.relative, "msg_id": self.msg_id}

    def set_state(self, d: dict[str, Any]) -> None:
        self.pieces_acc = d.get("pieces_acc", 0.0)
        self.values.update(d.get("values", {}))
        self.relative.update(d.get("relative", {}))
        self.msg_id = d.get("msg_id", "")
