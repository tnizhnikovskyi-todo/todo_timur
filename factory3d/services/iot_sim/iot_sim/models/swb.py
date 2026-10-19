"""Контролер ГРЩ SWB-CTRL (Modbus unit 73): положення QS і конденсаторні установки PFC-1/PFC-2 (W1 «Енергетика», §8.1).

Карта регістрів — ПРИПУЩЕННЯ для емулятора (A-24), на об'єкті діє документ контролера. FC3, u16:
``100`` — ``energy/cells/QS/state``; ``110…113`` / ``120…123`` — ``energy/cells/PFC-{1,2}/{q_kvar, steps_on,
steps_total, fault_step}``.

* **PFC** (на секцію ``s``): ``need = max(0, Q_s − P_s·tan(acos(target)))``, ``target = 0,95``
  (``settings.pfc_cos_target``); ``steps_on = min(10, ceil(need/35))``; ``q_kvar = steps_on·35``; ``steps_total = 10``.
  ``P_s``, ``Q_s`` — з ``energy/lines/*/p_now`` і ``cos_phi`` ліній секції (як ``td_energy.tools.live``, R-06 п. 2;
  несвіже/нульове ``cos_phi`` — 0,9). ASSUMPTION: в острові (``blackout``) і при збої пристрою ступені вимкнені.
* **QS**: ``0`` (open) завжди; ``1`` лише за параметром сценарію ``qs_closed`` (прапор ``swb``).
* **Сценарій** ``pfc_step_fault`` (прапор ``swb = {section, step, qs_closed}``): коли розрахункових ступенів секції
  стає ≥ ``step``, ступінь не вмикається — лишається ``step−1``, ``fault_step = step`` (тримається до зупинки
  сценарію); після зупинки ``fault_step = 0``. ``step = 0`` — без збою (лише ``qs_closed``).

W2 (SPEC §8.2, R-59, C-47): вікно керування HR 200…291 (``protocols/modbus_maps/swbctl.py``) змінює прапори світу, а
модель їх споживає: ``qs_cmd`` (1 розімкнути — завжди; 2 замкнути — якщо ``ats_parallel_lock == 1`` і немає острова,
інакше ``qs_ack = 2``; регістр самоочищається в тіку), ``pfc_mode`` (0 — ступені вимкнені), ``pfc_cos_target`` (замість
лише ``settings.pfc_cos_target``), ``ctl_remote`` (0 — команди ігноруються з ``ack = 2``), heartbeat ``ctl/heartbeat``
(+1 за симульовану секунду: ``epoch`` часу світу mod 65536). Кожен тік модель віддзеркалює прапори у сигнали ``energy_control/*`` (``/sim/v1/signals``).
"""

from __future__ import annotations

import math
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import AGGREGATE, Model
from iot_sim.models.meter import (
    SECTIONS,
    SHED_NODES,
    bess_temp_c,
    ctl,
    get,
    island,
    put,
    qs_closed,
    remote,
)

STEP_KVAR = 35.0
STEPS_TOTAL = 10
COS_TARGET = 0.95
COS_NOMINAL = 0.9
QS_STATE = "energy/cells/QS/state"
PFC_SECTIONS = (1, 2)
CTL = "energy_control/"
LOCK = CTL + "ats/parallel_lock"
HEARTBEAT = CTL + "ctl/heartbeat"


def pfc_code(section: int, leaf: str) -> str:
    return f"energy/cells/PFC-{section}/{leaf}"


def section_pq(world: Any, section: int) -> tuple[float, float]:
    """``(P_s, Q_s)`` секції за сигналами ліній (кВт, квар) до компенсації."""
    p = q = 0.0
    for line in SECTIONS[section]:
        p_l = float(get(world, f"energy/lines/{line}/p_now", 0.0) or 0.0)
        cos = float(get(world, f"energy/lines/{line}/cos_phi", COS_NOMINAL) or COS_NOMINAL)
        p += p_l
        q += p_l * math.tan(math.acos(min(max(cos, 0.01), 1.0)))
    return p, q


def steps_needed(p: float, q: float, target: float = COS_TARGET) -> int:
    """Скільки ступенів по 35 квар потрібно, щоб довести cos φ секції до ``target`` (0…10)."""
    need = max(0.0, q - p * math.tan(math.acos(target)))
    return min(STEPS_TOTAL, math.ceil(need / STEP_KVAR - 1e-9))


@register_model("swb")
class Swb(Model):
    phase = AGGREGATE

    def attach(self) -> None:
        self.stuck: dict[int, int] = {}  # секція → ступінь, що не вмикається (із початку сценарію)

    def _cfg(self) -> dict[str, Any]:
        cfg = self.world.flags.get("swb")
        return cfg if isinstance(cfg, dict) else {}

    def _section(self, section: int, cfg: dict[str, Any], dead: bool) -> None:
        step = int(cfg.get("step") or 0) if int(cfg.get("section") or 0) == section else 0
        if not step:
            self.stuck.pop(section, None)  # сценарій зупинено (або інша секція) → fault_step = 0
        want = 0
        if not dead and int(ctl(self.world, "pfc_mode")):
            want = steps_needed(*section_pq(self.world, section), self.cos_target())
        if step and (section in self.stuck or want >= step):
            self.stuck[section] = step
        fault = self.stuck.get(section, 0)
        steps = min(want, fault - 1) if fault else want
        put(self.world, pfc_code(section, "steps_on"), steps)
        put(self.world, pfc_code(section, "q_kvar"), steps * STEP_KVAR)
        put(self.world, pfc_code(section, "steps_total"), STEPS_TOTAL)
        put(self.world, pfc_code(section, "fault_step"), fault)

    def cos_target(self) -> float:
        """Ціль cos φ: прапор контролера ``pfc_cos_target`` або ``settings.pfc_cos_target`` (0,95)."""
        flag = ctl(self.world, "pfc_cos_target")
        return float(flag if flag is not None else getattr(self.world.settings, "pfc_cos_target", COS_TARGET))

    def _qs_command(self) -> None:
        """``qs/cmd``: 1 — розімкнути (завжди), 2 — замкнути (лише при ``ats_parallel_lock == 1`` і без острова)."""
        w = self.world
        cmd = int(ctl(w, "qs_cmd"))
        if not cmd:
            return
        w.set_flag("qs_cmd", 0)
        if not remote(w):
            w.set_flag("qs_ack", 2)
        elif cmd == 1:
            w.set_flag("qs_closed", False)
            w.set_flag("qs_ack", 1)
        elif float(get(w, LOCK, 1)) == 1 and not island(w):
            w.set_flag("qs_closed", True)
            w.set_flag("qs_ack", 1)
        else:
            w.set_flag("qs_ack", 2)

    def _mirror(self) -> None:
        """Прапори керування → сигнали ``energy_control/*`` (регістри вікна читають прапори напряму)."""
        w = self.world
        left = float(ctl(w, "bess_valid_left"))
        values = {
            "ctl/heartbeat": int(w.clock.epoch()) % 65536,
            "ctl/remote": int(remote(w)),
            "qs/cmd": int(ctl(w, "qs_cmd")),
            "qs/ack": int(ctl(w, "qs_ack")),
            "pfc/mode": int(ctl(w, "pfc_mode")),
            "pfc/cos_target": self.cos_target(),
            "bess/mode": int(ctl(w, "bess_mode")),
            "bess/setpoint_kw": float(ctl(w, "bess_setpoint_kw")),
            "bess/until_soc": float(ctl(w, "bess_until_soc")),
            "bess/valid_s": float(ctl(w, "bess_valid_s")),
            "bess/remaining_s": math.ceil(left) if int(ctl(w, "bess_mode")) else 0,
            "bess/reserve_pct": float(ctl(w, "bess_reserve_pct")),
            "bess/ack": int(ctl(w, "bess_ack")),
            "bess/temp_c": bess_temp_c(w),
            "chp/cmd": int(ctl(w, "chp_cmd")),
            "chp/ack": int(ctl(w, "chp_ack")),
            "chp/permit": int(ctl(w, "chp_permit")),
            "chp/gas_bar": float(ctl(w, "gas_bar")),
            "air/setpoint_bar": float(ctl(w, "air_setpoint_bar")),
            "pv/limit_pct": float(ctl(w, "pv_limit_pct")),
            "shed/valid_s": float(ctl(w, "shed_valid_s")),
        }
        limits = w.flags.get("shed_limit")
        for node in SHED_NODES:
            values[f"shed/{node}/limit_pct"] = float(limits.get(node, 100.0)) if isinstance(limits, dict) else 100.0
        for leaf, value in values.items():
            put(w, CTL + leaf, value)

    def tick(self, dt_s: float) -> None:
        cfg = self._cfg()
        dead = island(self.world) or self.device.fault is not None
        self._qs_command()
        put(self.world, QS_STATE, 1 if qs_closed(self.world) else 0)
        for section in PFC_SECTIONS:
            self._section(section, cfg, dead)
        self._mirror()

    def get_state(self) -> dict[str, Any]:
        return {"stuck": {str(s): step for s, step in self.stuck.items()}}

    def set_state(self, d: dict[str, Any]) -> None:
        self.stuck = {int(s): int(step) for s, step in (d.get("stuck") or {}).items()}
