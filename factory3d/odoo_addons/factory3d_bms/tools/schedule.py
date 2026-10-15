"""R-18: робочий час за календарем (resource.calendar) на момент `dt`."""

from datetime import timedelta, timezone


def work_interval_at(calendar, dt, cache=None):
    """`(start, stop)` (UTC naive) інтервалу календаря з `start <= dt < stop` або `None`.

    `dt` — UTC naive. Кеш `cache` (dict) — на прогін крона за `(calendar_id, хвилина)`."""
    if not calendar:
        return None
    minute = dt.replace(second=0, microsecond=0)
    key = (calendar.id, minute)
    if cache is not None and key in cache:
        return cache[key]
    aware = minute.replace(tzinfo=timezone.utc)
    intervals = calendar._work_intervals_batch(aware - timedelta(hours=12), aware + timedelta(hours=12))[False]
    result = None
    for start, stop, _recs in intervals:
        if start <= aware < stop:
            result = (
                start.astimezone(timezone.utc).replace(tzinfo=None),
                stop.astimezone(timezone.utc).replace(tzinfo=None),
            )
            break
    if cache is not None:
        cache[key] = result
    return result
