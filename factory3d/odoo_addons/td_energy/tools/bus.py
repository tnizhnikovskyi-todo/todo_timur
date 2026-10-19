"""W1-A, R-33: шина `td_energy`. Повідомлення БЕЗ даних: лише види змін, клієнт сам перечитує RPC.

`tick(env, kind)` накопичує види в `cr.precommit.data`; перед комітом — один `bus.bus._sendone`, але не частіше ніж
раз на `td.energy.bus_throttle_s` на воркер (пропущені види копичаться й їдуть із наступним тіком).
Збій шини ковтається: UI живе на резервному опитуванні.
"""

import logging
import time
from functools import partial

from odoo import fields

from .dates import param_float

_logger = logging.getLogger(__name__)

CHANNEL = "td_energy"
MESSAGE_TYPE = "td_energy/update"
KINDS = ("kpi", "alarm", "profile", "state", "advice")
_KEY = "td_energy.bus.kinds"
_STATE = {}  # dbname → {"last": monotonic, "pending": set}  (на воркер)


def tick(env, kind):
    """Зареєструвати вид зміни; відправка — у precommit поточної транзакції (один раз на транзакцію)."""
    if kind not in KINDS:
        return
    try:
        kinds = env.cr.precommit.data.get(_KEY)
        if kinds is None:
            kinds = env.cr.precommit.data[_KEY] = set()
            env.cr.precommit.add(partial(_flush, env))
        kinds.add(kind)
    except Exception:  # pragma: no cover - шина не повинна ламати бізнес-операцію
        _logger.warning("td_energy: тік шини не зареєстровано", exc_info=True)


def reset():
    """Для тестів: скинути лічильник throttle воркера."""
    _STATE.clear()


def _flush(env):
    kinds = env.cr.precommit.data.pop(_KEY, set())
    try:
        if "bus.bus" not in env:
            return
        state = _STATE.setdefault(env.cr.dbname, {"last": 0.0, "pending": set()})
        kinds = set(kinds) | state["pending"]
        throttle = param_float(env, "bus_throttle_s", 5.0)
        now = time.monotonic()
        if now - state["last"] < throttle:
            state["pending"] = kinds
            return
        state["last"], state["pending"] = now, set()
        payload = {"kinds": [k for k in KINDS if k in kinds], "ts": fields.Datetime.to_string(fields.Datetime.now())}
        with env.cr.savepoint():  # SQL-помилка шини не повинна залишати транзакцію в aborted
            env["bus.bus"].sudo()._sendone(CHANNEL, MESSAGE_TYPE, payload)
    except Exception:
        _logger.warning("td_energy: шина недоступна, повідомлення пропущено", exc_info=True)
