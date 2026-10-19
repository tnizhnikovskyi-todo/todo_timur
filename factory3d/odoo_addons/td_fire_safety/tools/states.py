"""Стани BACnetLifeSafetyState (SPEC R-11) і типи подій (R-14 п. 1)."""

import logging

from .etypes import ETYPE_TABLE, ETYPES, KINDS  # noqa: F401  (R-14: ETYPES живе в etypes.py)

_logger = logging.getLogger(__name__)

# № → текст (ASHRAE 135 BACnetLifeSafetyState)
LS_NAMES = {
    0: "quiet",
    1: "pre-alarm",
    2: "alarm",
    3: "fault",
    4: "fault-pre-alarm",
    5: "fault-alarm",
    6: "not-ready",
    7: "active",
    8: "tamper",
    9: "test-alarm",
    10: "test-active",
    11: "test-fault",
    12: "test-fault-alarm",
    13: "holdup",
    14: "duress",
    15: "tamper-alarm",
    16: "abnormal",
    17: "emergency-power",
    18: "delayed",
    19: "blocked",
    20: "local-alarm",
    21: "general-alarm",
    22: "supervisory",
    23: "test-supervisory",
}

# текст → (зона/прилад, пристрій)
_TABLE = {
    "quiet": ("normal", "normal"),
    "pre-alarm": ("prealarm", "prealarm"),
    "alarm": ("alarm", "alarm"),
    "fault": ("fault", "fault"),
    "fault-pre-alarm": ("prealarm", "prealarm"),
    "fault-alarm": ("alarm", "alarm"),
    "not-ready": ("disabled", "disabled"),
    "active": ("alarm", "active"),
    "tamper": ("fault", "fault"),
    "test-alarm": ("test", "test"),
    "test-active": ("test", "test"),
    "test-fault": ("test", "test"),
    "test-fault-alarm": ("test", "test"),
    "holdup": ("alarm", "alarm"),
    "duress": ("alarm", "alarm"),
    "tamper-alarm": ("alarm", "alarm"),
    "abnormal": ("fault", "fault"),
    "emergency-power": ("fault", "fault"),
    "delayed": ("prealarm", "prealarm"),
    "blocked": ("disabled", "disabled"),
    "local-alarm": ("prealarm", "prealarm"),
    "general-alarm": ("alarm", "alarm"),
    "supervisory": ("fault", "fault"),
    "test-supervisory": ("test", "test"),
}
ZONE_MAP = {k: v[0] for k, v in _TABLE.items()}
DEVICE_MAP = {k: v[1] for k, v in _TABLE.items()}
FAULT_STATES = ["fault", "tamper", "abnormal", "emergency-power", "supervisory"]
PRIORITY = {"alarm": 6, "prealarm": 5, "fault": 4, "disabled": 3, "test": 2, "normal": 1, "unknown": 0}
MSV_STATES = {1: "normal", 2: "alarm", 3: "fault", 4: "test", 5: "disabled"}

_warned = set()


def normalize(text):
    """Канонічний текст стану: числовий рядок («9») → за номером; решта — нижній регістр без пробілів."""
    if text is None:
        return ""
    t = str(text).strip().lower().replace("_", "-")
    if t.isdigit():
        return LS_NAMES.get(int(t), t)
    return t


def _lookup(table, text, label):
    t = normalize(text)
    state = table.get(t)
    if state is None:
        if t not in _warned:  # WARNING раз на текст за процес
            _warned.add(t)
            _logger.warning("Невідомий текст стану %s: %r", label, text)
        return "unknown"
    return state


def zone_state(text):
    return _lookup(ZONE_MAP, text, "LSZ")


def device_state(text):
    return _lookup(DEVICE_MAP, text, "LSP")


def is_fault_state(text):
    return normalize(text) in FAULT_STATES
