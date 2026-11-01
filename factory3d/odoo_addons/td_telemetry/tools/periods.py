"""Мінімальний ефективний період опитування, безпекові винятки й вікна свіжості (19.0.1.1.5, 19.0.1.1.6).

Каталоги модулів задають періоди 1–2 с (ворота й ваги двору, СНЕ ТЕЦ, верстати, пожежна безпека). Для демо й
звичайної телеметрії це зайве навантаження на колектор і на БД, тому в конфігурації колектора період не менший за
`td.telemetry.min_period_s` (5 с за замовчуванням, 0 вимикає). Винятки — сигнали безпеки (затримка 5 с тут шкодить):

* код містить сегмент зі списку `td.telemetry.min_period_exempt` (за замовчуванням `fire`, `gas`, `safe`, `safety`,
  `alarm`, `alarms`, `estop`, `gates`, `scale`: пожежа, газ, захисти ТЕЦ, тривоги, аварійний стоп, ворота й ваги двору);
* `alarm_states` не порожні (дискретні тривоги: `workcenters/<C>/alarm`);
* `kind = event` (подія надходить пушем, період не визначає затримку).

Ті самі сигнали Ingester завжди пише в `td_signal.last_*` без відкладання (`ingest._needs_write`).

Вікна свіжості (19.0.1.1.6). Споживачі міряють `now − last_ts` власним вікном: АВР `td_energy` і генсет —
`3·period_s` (15 с для `infra/ats/*`), `td_chp` — `max(3·period_s, 30 с)`, решта (енергетика, ресурси, інтерлоки) —
60…120 с, `_cron_stale` — `max(3·період, 60 с, 2·push_interval_s)`. Усі вони не вужчі за
`fresh_window_s(period_s) = min(30 с, 3·period_s)`, тому відкладений запис `last_ts` (ingest) тримає вік збереженого
`last_ts` у цьому вікні, а якщо вікно вужче за затримку доставки (період опитування + `push_interval_s`) — не відкладає
запис узагалі.
"""

DEFAULT_MIN_PERIOD_S = 5
FRESH_CAP_S = 30.0  # найвужче фіксоване вікно споживачів (td_chp `stale_s`)
FRESH_PERIODS = 3  # споживачі з вікном `k·period_s` (АВР td_energy, генсет)
FRESH_MARGIN_S = 2.0  # запас на прийом пакета й округлення часу
DEFAULT_PUSH_S = 5  # `td.collector.push_interval_s` за замовчуванням
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


def fresh_window_s(period_s, cap_s=FRESH_CAP_S):
    """Вікно свіжості `last_ts`, у яке вкладаються споживачі сигналу: `min(cap_s, 3·period_s)`.

    `period_s` — період із каталогу (споживачі беруть саме його, а не ефективний); без періоду — `cap_s`.
    """
    period_s = period_s or 0
    return min(cap_s, FRESH_PERIODS * period_s) if period_s > 0 else cap_s


def max_skip_gap_s(period_s, eff_period_s, push_interval_s, cap_s=FRESH_CAP_S):
    """На скільки секунд після збереженого `last_ts` показання ще можна не писати (від'ємне — не відкладати взагалі).

    Якщо пропустити показання, наступне (через `eff_period_s`, прийом до `push_interval_s` пізніше) стане записаним
    найраніше через `gap + eff_period_s + push_interval_s`; цей вік плюс запас має вкластися у `fresh_window_s`.
    """
    return fresh_window_s(period_s, cap_s) - FRESH_MARGIN_S - (push_interval_s or 0) - eff_period_s


def stale_window_s(eff_period_s, n_periods, min_s, push_interval_s=0):
    """Вікно `stale` сигналу колектора: не вужче за `n·період`, `stale_min_s` і подвійний період відправки
    (дані не можуть бути свіжішими за пакет: інакше колектор із `push_interval_s` ≥ 40 с «мигає» stale ↔ ok)."""
    return max(n_periods * eff_period_s, min_s, 2 * (push_interval_s or 0))
