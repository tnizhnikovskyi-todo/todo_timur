"""Час Києва, вікна через північ, переходи DST, 15-хвилинні блоки за UTC-епохою (R-45, R-48, R-63)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")
BLOCK_S = 900


def to_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def local(now: datetime, tz: ZoneInfo = KYIV) -> datetime:
    return to_utc(now).astimezone(tz)


def hours_of(now: datetime, tz: ZoneInfo = KYIV) -> float:
    """Поточний «настінний» час доби як година-float (14,333 = 14:20)."""
    t = local(now, tz)
    return t.hour + t.minute / 60.0 + t.second / 3600.0


def parse_hhmm(text: str) -> float | None:
    """`"06:30"` → 6.5; `None` для некоректного рядка."""
    try:
        hh, mm = str(text).split(":")
        h, m = int(hh), int(mm)
    except (ValueError, AttributeError):
        return None
    return h + m / 60.0 if 0 <= h <= 24 and 0 <= m < 60 else None


def block_start(epoch: float) -> float:
    """Початок 15-хвилинного блока, вирівняного за UTC-епохою (перехід DST не впливає)."""
    return (epoch // BLOCK_S) * BLOCK_S


def in_window(now: datetime, start_h: float, end_h: float, days: list[int], tz: ZoneInfo = KYIV) -> bool:
    """Чи в вікні `[start_h, end_h)` за місцевим часом; `start_h > end_h` — вікно через північ.

    `days` — дні тижня (1…7), З ЯКИХ починається вікно: частина після півночі належить попередній добі.
    """
    t = local(now, tz)
    h = t.hour + t.minute / 60.0 + t.second / 3600.0
    if start_h == end_h:
        return False
    if start_h < end_h:
        return start_h <= h < end_h and t.isoweekday() in days
    if h >= start_h:
        return t.isoweekday() in days
    if h < end_h:
        return (t - timedelta(days=1)).isoweekday() in days
    return False


def window_key(now: datetime, start_h: float, end_h: float, tz: ZoneInfo = KYIV) -> str:
    """Ідентифікатор вікна (дата його початку) — для «до наступної межі» (R-48 п.5)."""
    t = local(now, tz)
    h = t.hour + t.minute / 60.0
    day = t.date() - timedelta(days=1) if start_h > end_h and h < end_h else t.date()
    return day.isoformat()


def next_window_start(now: datetime, start_h: float, days: list[int], tz: ZoneInfo = KYIV) -> str:
    """Найближчий початок вікна, `HH:MM` за Києвом (R-48 п.7)."""
    t = local(now, tz)
    for add in range(0, 8):
        day = t.date() + timedelta(days=add)
        cand = datetime(day.year, day.month, day.day, tzinfo=tz) + timedelta(hours=start_h)
        if day.isoweekday() in days and cand > t:
            return cand.strftime("%H:%M")
    return f"{int(start_h):02d}:{int(round((start_h % 1) * 60)):02d}"


def weekday_ok(mask: str, day: date) -> bool:
    """`weekdays` слота: 7 символів «1111100», пн…нд."""
    mask = (mask or "1111111").ljust(7, "1")
    return mask[day.isoweekday() - 1] == "1"
