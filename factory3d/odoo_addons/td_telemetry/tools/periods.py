"""Мінімальний ефективний період опитування й безпекові винятки (19.0.1.1.5).

Каталоги модулів задають періоди 1–2 с (ворота й ваги двору, СНЕ ТЕЦ, верстати, пожежна безпека). Для демо й
звичайної телеметрії це зайве навантаження на колектор і на БД, тому в конфігурації колектора період не менший за
`td.telemetry.min_period_s` (5 с за замовчуванням, 0 вимикає). Винятки — сигнали безпеки (затримка 5 с тут шкодить):

* код містить сегмент зі списку `td.telemetry.min_period_exempt` (за замовчуванням `fire`, `gas`, `safe`, `safety`,
  `alarm`, `alarms`, `estop`, `gates`, `scale`: пожежа, газ, захисти ТЕЦ, тривоги, аварійний стоп, ворота й ваги двору);
* `alarm_states` не порожні (дискретні тривоги: `workcenters/<C>/alarm`);
* `kind = event` (подія надходить пушем, період не визначає затримку).

Ті самі сигнали Ingester завжди пише в `td_signal.last_*` без відкладання (`ingest._needs_write`).
"""

DEFAULT_MIN_PERIOD_S = 5
DEFAULT_EXEMPT = "fire,gas,safe,safety,alarm,alarms,estop,gates,scale"


def _int(icp, key, default):
    try:
        return int(icp.get_param("td.telemetry." + key, str(default)) or 0)
    except (TypeError, ValueError):
        return default


def min_period_s(icp):
    """Глобальний мінімальний період, с (0 — вимкнено)."""
    return max(_int(icp, "min_period_s", DEFAULT_MIN_PERIOD_S), 0)


def exempt_segments(icp):
    raw = icp.get_param("td.telemetry.min_period_exempt", DEFAULT_EXEMPT)
    raw = DEFAULT_EXEMPT if raw is False or raw is None else raw
    return frozenset(s.strip().lower() for s in raw.split(",") if s.strip())


def is_safety(code, kind, alarm_states, segments):
    """Сигнал безпеки/тривоги: період не підвищується, `last_*` пишеться без відкладання."""
    if kind == "event" or alarm_states:
        return True
    return any(seg in segments for seg in (code or "").lower().split("/"))


def effective_period_s(period_s, safety, min_s):
    """Період, з яким колектор реально опитує сигнал."""
    period_s = period_s or 0
    if safety or min_s <= 0:
        return period_s
    return max(period_s, min_s)
