"""R-05: зона й ціна тарифу. Чисті функції без ORM; зона — будь-який об'єкт з атрибутами
`weekdays`, `hour_from`, `hour_to` (і, за наявності, `sequence`, `name`)."""

import re
from datetime import timezone
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
WEEKDAY_NAMES = ("пн", "вт", "ср", "чт", "пт", "сб", "нд")
WEEKDAYS_RE = re.compile(r"^[0-6]{1,7}$")


def to_local(dt_utc):
    """Naive datetime (UTC, як у Odoo) → aware за Києвом."""
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(KYIV)


def weekdays_valid(weekdays):
    return bool(weekdays) and bool(WEEKDAYS_RE.match(weekdays)) and len(set(weekdays)) == len(weekdays)


def hours_valid(hour_from, hour_to):
    return all(0 <= h <= 24 and abs(h * 4 - round(h * 4)) < 1e-9 for h in (hour_from, hour_to))


def zone_valid(zone):
    """Зона, яку можна враховувати в покритті: формат днів/годин і ненульова тривалість."""
    return (
        weekdays_valid(zone.weekdays)
        and hours_valid(zone.hour_from, zone.hour_to)
        and zone.hour_from != zone.hour_to
    )


def zone_matches(zone, weekday, hour):
    """R-05 п. 2: `weekday` 0 — понеділок; `hour` — година дня дробом."""
    if str(weekday) not in zone.weekdays:
        return False
    if zone.hour_from < zone.hour_to:
        return zone.hour_from <= hour < zone.hour_to
    return hour >= zone.hour_from or hour < zone.hour_to


def zone_for(local_dt, zones):
    """Перша (за `sequence`, далі за порядком у списку) зона, що відповідає місцевому часу, або None."""
    hour = local_dt.hour + local_dt.minute / 60
    ordered = sorted(zones, key=lambda z: getattr(z, "sequence", 0) or 0)
    for zone in ordered:
        if zone_matches(zone, local_dt.weekday(), hour):
            return zone
    return None


def check_coverage(zones):
    """R-05 п. 3: кожна 15-хв чверть тижня покрита рівно однією зоною.
    Повертає None або ('missing', wd, 'HH:MM') / ('double', wd, 'HH:MM', name1, name2)."""
    valid = [z for z in zones if zone_valid(z)]
    for wd in range(7):
        for k in range(96):
            hour = k / 4
            hit = [z for z in valid if zone_matches(z, wd, hour)]
            stamp = "%02d:%02d" % (k // 4, (k % 4) * 15)
            if not hit:
                return ("missing", WEEKDAY_NAMES[wd], stamp)
            if len(hit) > 1:
                return ("double", WEEKDAY_NAMES[wd], stamp, hit[0].name, hit[1].name)
    return None
