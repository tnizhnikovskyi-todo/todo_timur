"""Календар зміни: київські доби й вікна змін у naive UTC (так Odoo зберігає `Datetime`). Без ORM.

`shift` — пара `(початок, кінець)` у годинах доби (7.0, 15.5), `workdays` — рядок цифр днів тижня (0 — понеділок).
"""

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
MAX_DAYS = 400  # скільки діб уперед шукаємо робочу (захист від порожнього `workdays`)


def to_local(dt):
    """naive UTC → aware за Києвом."""
    return dt.replace(tzinfo=timezone.utc).astimezone(KYIV)


def to_utc(local_dt):
    """aware (будь-яка зона) → naive UTC."""
    return local_dt.astimezone(timezone.utc).replace(tzinfo=None)


def local_date(dt):
    """Київська дата моменту `dt` (naive UTC)."""
    return to_local(dt).date()


def _at(day, hours):
    whole = int(hours)
    minutes = int(round((hours - whole) * 60))
    if minutes == 60:
        whole, minutes = whole + 1, 0
    if whole >= 24:
        return datetime.combine(day + timedelta(days=1), time(whole - 24, minutes), tzinfo=KYIV)
    return datetime.combine(day, time(whole, minutes), tzinfo=KYIV)


def shift_window(day, shift):
    """`(початок, кінець)` зміни київської дати `day` як naive UTC."""
    return to_utc(_at(day, shift[0])), to_utc(_at(day, shift[1]))


def is_workday(day, workdays="0123456"):
    return str(day.weekday()) in workdays


def in_shift(dt, shift, workdays="0123456"):
    """`dt` у вікні зміни своєї київської доби (кінець не входить)."""
    day = local_date(dt)
    if not is_workday(day, workdays):
        return False
    start, end = shift_window(day, shift)
    return start <= dt < end


def next_shift_start(dt, shift, workdays="0123456"):
    """Найближчий момент `>= dt`, що лежить у зміні: сам `dt`, якщо він у зміні, інакше початок наступної."""
    day = local_date(dt)
    for _ in range(MAX_DAYS):
        if is_workday(day, workdays):
            start, end = shift_window(day, shift)
            if dt < end:
                return max(dt, start)
        day += timedelta(days=1)
        dt = max(dt, to_utc(_at(day, 0)))
    raise ValueError("немає робочих днів: workdays=%r" % (workdays,))


def place(earliest, minutes, shift, workdays="0123456"):
    """`(початок, кінець)` операції на `minutes` хв не раніше `earliest`: цілком у вікні однієї зміни.

    Не вміщується в залишок зміни — переходить на початок наступної. Операція довша за зміну починає на початку
    вікна й іде безперервно (понаднормово): інакше вона не була б розміщена ніколи.
    """
    t = next_shift_start(earliest, shift, workdays)
    span = timedelta(minutes=minutes)
    for _ in range(MAX_DAYS):
        start, end = shift_window(local_date(t), shift)
        if t + span <= end or (t == start and span > end - start):
            return t, t + span
        t = next_shift_start(end, shift, workdays)
    raise ValueError("операцію не розміщено")


def shift_minutes(shift):
    return (shift[1] - shift[0]) * 60.0
