"""Часові пояси двору (SPEC §11.5): БД — UTC naive, «доба» — Europe/Kyiv."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
UTC = timezone.utc


def to_local(dt):
    """UTC naive -> aware Kyiv."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(KYIV)


def local_hm(dt):
    return to_local(dt).strftime("%H:%M")


def local_day(dt):
    return to_local(dt).date()


def local_today(now=None):
    """Поточна київська доба; `now` — UTC naive (сервер передає `fields.Datetime.now()`, у тестах він підміняється)."""
    return local_day(now or datetime.now(UTC))


def today_domain(operator, value, now=None, field="day"):
    """Домен пошуку «Сьогодні» для поля київської доби `field` (замість `context_today()` браузера, Y-2)."""
    if operator not in ("=", "!=") or not isinstance(value, bool):
        raise NotImplementedError("Пошук «Сьогодні» підтримує лише = / != True/False")
    return [(field, "=" if (operator == "=") == value else "!=", local_today(now))]


def _to_utc_naive(local_naive):
    return local_naive.replace(tzinfo=KYIV).astimezone(UTC).replace(tzinfo=None)


def day_bounds_utc(day):
    """[00:00, 24:00) місцевої доби як пара UTC naive (25.10.2026 має 25 год)."""
    start = datetime(day.year, day.month, day.day)
    return _to_utc_naive(start), _to_utc_naive(start + timedelta(days=1))


def parse_axis_ts(value):
    """capture_timestamp (епоха мс UTC, число або рядок) -> UTC naive; невалідне -> None."""
    try:
        ms = int(str(value).strip())
        if ms <= 0:
            return None
        return datetime.fromtimestamp(ms / 1000.0, UTC).replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
