"""Час BioStar і локальна доба (R-15). Усі Datetime — naive UTC."""
import re
from datetime import datetime, time, timedelta

import pytz

KYIV = 'Europe/Kyiv'
_BS_RE = re.compile(r'^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})?$')


def parse_bs_dt(value):
    """`2026-10-12T03:52:10.00Z` / `.000Z` / `10Z` / `+00:00` -> naive UTC; порожнє -> None; інше -> ValueError."""
    if value is None or value == '':
        return None
    match = _BS_RE.match(str(value).strip())
    if not match:
        raise ValueError("Невалідний час BioStar: %r" % (value,))
    dt = datetime.strptime('%sT%s' % (match.group(1), match.group(2)), '%Y-%m-%dT%H:%M:%S')
    zone = match.group(3)
    if zone and zone != 'Z':
        sign = 1 if zone[0] == '+' else -1
        dt -= sign * timedelta(hours=int(zone[1:3]), minutes=int(zone[4:6]))
    return dt


def fmt_bs_dt(dt):
    return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')


def _tz(tz):
    return pytz.timezone(tz) if isinstance(tz, str) else tz


def to_local(dt, tz=KYIV):
    return pytz.utc.localize(dt).astimezone(_tz(tz))


def to_local_str(dt, tz=KYIV, fmt='%Y-%m-%d %H:%M:%S'):
    return to_local(dt, tz).strftime(fmt) if dt else ''


def local_date(dt, tz=KYIV):
    return to_local(dt, tz).date()


def local_day_start_utc(dt, tz=KYIV):
    """Початок локальної доби, що містить `dt`, як naive UTC."""
    zone = _tz(tz)
    midnight = datetime.combine(local_date(dt, zone), time())
    return zone.localize(midnight).astimezone(pytz.utc).replace(tzinfo=None)


def local_day_bounds_utc(dt, tz=KYIV):
    """[початок, кінець) локальної доби, що містить `dt`, як naive UTC (у дні переходу на літній/зимовий час доба не 24 год)."""
    zone = _tz(tz)
    day = local_date(dt, zone)
    start = zone.localize(datetime.combine(day, time())).astimezone(pytz.utc).replace(tzinfo=None)
    end = zone.localize(datetime.combine(day + timedelta(days=1), time())).astimezone(pytz.utc).replace(tzinfo=None)
    return start, end


def schedule_end_utc(day, hour_to, tz=KYIV):
    """Кінець графіка: локальна північ дня `day` + `hour_to` годин -> naive UTC (R-07)."""
    zone = _tz(tz)
    local = zone.localize(datetime.combine(day, time()) + timedelta(hours=hour_to))
    return local.astimezone(pytz.utc).replace(tzinfo=None)
