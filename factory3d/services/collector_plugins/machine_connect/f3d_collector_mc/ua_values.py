"""R-22 п. 2–5: значення OPC UA -> Reading, список завдань -> текст, подія UA -> payload EV-01."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from asyncua import ua
from collector.core.types import Reading, SignalCfg

FUTURE_TOLERANCE = timedelta(seconds=60)
FINISHED_STATES = ("Ended", "Completed", "Aborted", "Cancelled")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def quality(status: Any) -> str:
    """StatusCode -> `good` | `uncertain` | `bad` (R-22 п. 2)."""
    if status is None:
        return "good"
    if status.is_good():
        return "good"
    if status.is_uncertain():
        return "uncertain"
    return "bad"


def value_ts(dv: Any, now: datetime) -> tuple[datetime, bool]:
    """SourceTimestamp, інакше ServerTimestamp, інакше `now`; > 60 с у майбутньому -> `now` (другий елемент True)."""
    now = _aware(now)
    ts = getattr(dv, "SourceTimestamp", None) or getattr(dv, "ServerTimestamp", None)
    if ts is None:
        return now, False
    ts = _aware(ts)
    if ts - now > FUTURE_TOLERANCE:
        return now, True
    return ts, False


def _text_of(v: Any) -> str:
    if isinstance(v, ua.LocalizedText):
        return v.Text or ""
    return str(v)


def _states(item: Any) -> list[str]:
    out = []
    for st in getattr(item, "State", None) or []:
        out.append(_text_of(getattr(st, "StateText", "")))
    return out


def select_job(items: Any) -> str:
    """Елемент `Running`, інакше перший незавершений; порожній список або всі завершені -> `-` (R-22 п. 3)."""
    items = list(items or [])
    for it in items:
        if "Running" in _states(it):
            return _job_id(it)
    for it in items:
        if not any(s in FINISHED_STATES for s in _states(it)):
            return _job_id(it)
    return "-"


def _job_id(item: Any) -> str:
    order = getattr(item, "JobOrder", None)
    return str(getattr(order, "JobOrderID", "") or "-")[:64]


def bad_reading(signal: SignalCfg, ts: datetime) -> Reading | None:
    """Показання при втраті зв'язку: `text="bad"` для state-сигналів, для лічильників — пропуск."""
    if signal.kind == "state":
        return Reading(code=signal.code, ts=ts, value=None, text="bad", q="bad")
    return None


def to_reading(signal: SignalCfg, dv: Any, now: datetime) -> Reading | None:
    """DataValue -> Reading (R-22 п. 2–3). `None` — показання пропускається (Bad для лічильників)."""
    addr = signal.address or {}
    ts, _future = value_ts(dv, now)
    q = quality(getattr(dv, "StatusCode", None))
    if q == "bad":
        return bad_reading(signal, ts)
    variant = getattr(dv, "Value", None)
    val = getattr(variant, "Value", variant)
    mapping = addr.get("map") or {}
    if addr.get("job_select") == "running_or_first":
        return Reading(code=signal.code, ts=ts, value=None, text=select_job(val), q=q)
    if val is None:
        return bad_reading(signal, ts)
    if isinstance(val, bool):
        return Reading(code=signal.code, ts=ts, value=1.0 if val else 0.0, text=mapping.get("1" if val else "0"), q=q)
    if isinstance(val, int):
        if mapping or signal.kind == "state":
            return Reading(code=signal.code, ts=ts, value=float(val), text=mapping.get(str(val), str(val)), q=q)
        return Reading(code=signal.code, ts=ts, value=float(val), q=q)
    if isinstance(val, float):
        return Reading(code=signal.code, ts=ts, value=float(val), q=q)
    if isinstance(val, str | ua.LocalizedText):
        return Reading(code=signal.code, ts=ts, value=None, text=_text_of(val)[:64], q=q)
    return Reading(code=signal.code, ts=ts, value=None, text=str(val)[:64], q=q)


def jobs(job_order_list: Any) -> str:
    """Скорочення для тестів/використання поза плагіном: текст для `JobOrderList`."""
    return select_job(job_order_list)


def _iso_ms(dt: datetime) -> str:
    dt = _aware(dt).astimezone(UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _get(event: Any, name: str, default: Any = None) -> Any:
    val = getattr(event, name, None)
    return default if val is None else val


def event_payload(
    source_code: str, machine_code: str | None, event: Any, alarm_types: frozenset | set | None = None
) -> dict:
    """Подія/тривога UA -> payload EV-01 (R-22 п. 5)."""
    etype = getattr(event, "EventType", None)
    active_id = getattr(event, "ActiveState/Id", None)
    is_alarm = (alarm_types is not None and etype in alarm_types) or active_id is not None
    kind = "alarm" if is_alarm else "event"
    machine = str(getattr(event, "SourceName", "") or "") or (machine_code or source_code.removeprefix("UA-"))
    texts: dict[str, str] = {}
    for lm in _get(event, "LocalizedMessages", []) or []:
        if isinstance(lm, ua.LocalizedText) and lm.Locale:
            texts[lm.Locale] = lm.Text or ""
    msg = _get(event, "Message")
    text = (texts.get("uk") or (_text_of(msg) if msg is not None else ""))[:256]
    t = _get(event, "Time")
    time_iso = _iso_ms(t if isinstance(t, datetime) else datetime.now(UTC))
    try:
        severity = int(_get(event, "Severity", 1))
    except (TypeError, ValueError):
        severity = 1
    category = _get(event, "EventCategory", 4 if is_alarm else 0)
    args = _get(event, "Arguments", []) or []
    return {
        "kind": kind,
        "source": source_code,
        "machine": machine,
        "time": time_iso,
        "message_id": str(_get(event, "MessageId", ""))[:16],
        "message_name": str(_get(event, "MessageName", "")),
        "category": max(0, min(5, int(category))),
        "severity": max(1, min(1000, severity)),
        "text": text,
        "texts": texts,
        "path": [str(p) for p in (_get(event, "PathParts", []) or [])],
        "group": str(_get(event, "Group", "")),
        "active": bool(active_id) if active_id is not None else False,
        "acked": bool(getattr(event, "AckedState/Id", False)),
        "args": {str(i): str(a) for i, a in enumerate(args)},
    }
