"""Зведення станів із текстом до числа (kind=state з `map`: ядро віддає `Reading(text=…)` без `value`)."""

from __future__ import annotations

from collector.core.types import Reading

_REMOTE = {"local": 0.0, "remote": 1.0}
_QS = {"open": 0.0, "closed": 1.0}
_BESS = {"offline": 0.0, "standby": 1.0, "running": 2.0, "fault": 3.0, "sleep": 4.0}
_CHP = {"stop": 0.0, "starting": 1.0, "running": 2.0, "fault": 3.0, "cooling": 4.0}
_ATS_POS = {"unknown": 0.0, "pos_0": 1.0, "pos_i": 2.0, "pos_ii": 3.0}
_SRC1 = {"under": 0.0, "present": 1.0, "available": 2.0}  # infra/ats/src1_state (energy_signals.csv)
# ключ — логічне ім'я входу (`cfg.inputs`/`signals`) або код сигналу (терми `derived`); число = індекс стану
TEXT_NUM: dict[str, dict[str, float]] = {
    "remote": _REMOTE,
    "energy_control/ctl/remote": _REMOTE,
    "qs_state": _QS,
    "energy/cells/QS/state": _QS,
    "bess_state": _BESS,
    "infra/bess/state": _BESS,
    "chp_state": _CHP,
    "infra/chp/state": _CHP,
    "ats_pos": _ATS_POS,
    "infra/ats/position": _ATS_POS,
    "infra/ats/src1_state": _SRC1,
    "src1_ok": {"unavailable": 0.0, "lost": 0.0, "available": 1.0, "ok": 1.0},
}


def text_value(key: str, reading: Reading | None) -> float | None:
    """Число показання: `value`, а для станів з текстом — індекс за `TEXT_NUM` (`key` — ім'я входу або код)."""
    if reading is None:
        return None
    if reading.value is not None:
        return float(reading.value)
    return TEXT_NUM.get(key, {}).get(str(reading.text or "").lower())
