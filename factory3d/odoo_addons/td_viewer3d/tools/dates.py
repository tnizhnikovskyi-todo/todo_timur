"""R-02: час і часовий пояс. Усі обчислення в UTC (naive), рендер — за Києвом."""

import logging
import calendar
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_logger = logging.getLogger(__name__)

TZ = ZoneInfo("Europe/Kyiv")
FMT = "%Y-%m-%d %H:%M"
CLOCK_RE = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
PARAM_CLOCK = "td.viewer.demo_clock"


def local(dt_utc):
    """datetime (UTC, naive) -> "YYYY-MM-DD HH:MM" за Києвом."""
    return dt_utc.replace(tzinfo=timezone.utc).astimezone(TZ).strftime(FMT)


def epoch_ms(dt_utc):
    """datetime (UTC, naive) -> epoch у мілісекундах (UTC): `meta.now_ms` — «зараз» із точністю до секунди,
    бо `local()` обрізає до хвилини (годинник «синхр.» у клієнті бере з нього секунди)."""
    return calendar.timegm(dt_utc.timetuple()) * 1000 + dt_utc.microsecond // 1000


def utc(s_local):
    """ "YYYY-MM-DD HH:MM" за Києвом -> datetime (UTC, naive)."""
    naive = datetime.strptime(s_local[:16], FMT)
    return naive.replace(tzinfo=TZ).astimezone(timezone.utc).replace(tzinfo=None)


def real_now():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def now(env):
    """UTC naive: `demo_clock`, якщо валідний, інакше реальний час."""
    clock = env["ir.config_parameter"].sudo().get_param(PARAM_CLOCK)
    if clock:
        if CLOCK_RE.match(clock):
            try:
                return utc(clock)
            except ValueError:
                pass
        _logger.warning("td.viewer.demo_clock невалідний (%r): ігнорується", clock)
    return real_now()


def today(env):
    return local(now(env))[:10]


def iso_utc(dt_utc):
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso_utc(s):
    """ "2026-10-12T07:30:12Z" (або без Z, або з дробовою частиною) -> datetime UTC naive; ValueError."""
    s = s.rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(s)


def date_to_local(value, create_dt=None):
    """Поле Date -> "YYYY-MM-DD 00:00"; якщо передано create_dt (UTC) — його час за Києвом."""
    if create_dt:
        return local(create_dt)
    return f"{value} 00:00" if value else None
