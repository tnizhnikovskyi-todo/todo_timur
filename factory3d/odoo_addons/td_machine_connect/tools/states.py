"""R-01: нормалізація стану верстата (чиста функція, без `env`) і розбір часу показань."""

import logging
from datetime import datetime, timedelta, timezone

_logger = logging.getLogger(__name__)

WARN_EVERY = timedelta(hours=1)
_warned = {}  # ключ верстата -> час останнього WARNING про невідомий стан

_UA_READY = ("READY", "STANDBY")


def parse_ts(value):
    """ISO-рядок з зоною / aware datetime → naive UTC; naive — як є; нерозбірливе → `None`."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _warn_unknown(state, key, now):
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    last = _warned.get(key)
    if last is not None and now - last < WARN_EVERY:
        return
    _warned[key] = now
    _logger.warning("невідомий стан %s (верстат %s)", state, key)


def normalize(protocol, raw, key=None, now=None):
    """`raw = {"state", "mode", "alarm", "bad"}` → один зі станів `f3d.machine.state` (R-01).

    `key` — код верстата для обмеження WARNING «невідомий стан» (раз на годину); `now` — naive UTC.
    """
    state = raw.get("state")
    mode = raw.get("mode")
    alarm = bool(raw.get("alarm"))
    if raw.get("bad") or state is None:
        return "nodata"
    if protocol == "opcua":
        if state == "ERROR":
            return "fault"
        if state == "WORKING":
            return "working"
        if alarm and state in ("READY", "STANDBY", "OFFLINE"):
            return "fault"
        if state in _UA_READY:
            return "setup" if mode == "SETUP" else "idle"
        if state == "OFFLINE":
            return "off"
    elif protocol == "io":
        if alarm:
            return "fault"
        if state == "run":
            return "working"
        if state == "stop":
            return "idle"
    elif protocol == "manual":
        return "nodata"
    _warn_unknown(state, key, now)
    return "nodata"
