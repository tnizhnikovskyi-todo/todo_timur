"""R-62, A-41: шина `td_energy_control` (копія механіки W1 R-33). Повідомлення БЕЗ даних: лише види змін.

`tick(env, kind)` накопичує види в `cr.precommit.data`; перед комітом — один `bus.bus._sendone`, але не частіше ніж
раз на `td.energy.bus_throttle_s` на воркер. Збій шини ковтається: UI живе на резервному опитуванні (30 с).
"""

import logging
import time
from functools import partial

from odoo import fields

_logger = logging.getLogger(__name__)

CHANNEL = "td_energy_control"
MESSAGE_TYPE = "td_energy_control/update"
KINDS = ("action", "scenario", "engine", "schedule", "shed")
_KEY = "td_energy_control.bus.kinds"
_STATE = {}  # dbname → {"last": monotonic, "pending": set}


def tick(env, kind):
    """Зареєструвати вид зміни; відправка — у precommit (один раз на транзакцію)."""
    if kind not in KINDS:
        return
    try:
        kinds = env.cr.precommit.data.get(_KEY)
        if kinds is None:
            kinds = env.cr.precommit.data[_KEY] = set()
            env.cr.precommit.add(partial(_flush, env))
        kinds.add(kind)
    except Exception:  # pragma: no cover - шина не повинна ламати бізнес-операцію
        _logger.warning("td_energy_control: тік шини не зареєстровано", exc_info=True)


def reset():
    """Для тестів: скинути лічильник throttle воркера."""
    _STATE.clear()


def _throttle(env):
    val = env["ir.config_parameter"].sudo().get_param("td.energy.bus_throttle_s")
    try:
        return float(val)
    except (TypeError, ValueError):
        return 5.0


def _flush(env):
    kinds = env.cr.precommit.data.pop(_KEY, set())
    try:
        if "bus.bus" not in env:
            return
        state = _STATE.setdefault(env.cr.dbname, {"last": 0.0, "pending": set()})
        kinds = set(kinds) | state["pending"]
        now = time.monotonic()
        if now - state["last"] < _throttle(env):
            state["pending"] = kinds
            return
        state["last"], state["pending"] = now, set()
        payload = {"kinds": [k for k in KINDS if k in kinds], "ts": fields.Datetime.to_string(fields.Datetime.now())}
        env["bus.bus"].sudo()._sendone(CHANNEL, MESSAGE_TYPE, payload)
    except Exception:
        _logger.warning("td_energy_control: шина недоступна, повідомлення пропущено", exc_info=True)
