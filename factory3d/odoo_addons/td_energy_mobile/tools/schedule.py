"""R-H1, R-H2: розклад обходів — чисті функції без ORM (слоти, вікна, доба за Києвом, перехід DST)."""

from datetime import datetime, time, timedelta

from odoo.addons.td_energy.tools import dates

WEEKDAYS_DEFAULT = "0,1,2,3,4"


def parse_weekdays(text):
    """«0,1,2» → [0, 1, 2]; `None`, якщо рядок некоректний (не цифри 0…6 або повтори)."""
    parts = [p.strip() for p in (text or "").split(",")]
    if any(len(p) != 1 or p not in "0123456" for p in parts):
        return None
    days = [int(p) for p in parts]
    return days if len(set(days)) == len(days) else None


def fmt_hhmm(hours):
    """Година доби `16.5` → «16:30» (24,0 → «24:00»)."""
    return "%02d:%02d" % divmod(int(round(hours * 60)), 60)


def local_dt(day, hours):
    """Місцевий (стінний) час Києва: дата + години доби (naive)."""
    return datetime.combine(day, time(0, 0)) + timedelta(minutes=int(round(hours * 60)))


def slot_bounds(day, time_from, time_to):
    """Місцева дата й години слота → (`starts_at`, `due_at`) в UTC naive через `dates.to_utc`: у добу переходу
    на літній/зимовий час границі точні (слот може бути на годину коротшим/довшим)."""
    return dates.to_utc(local_dt(day, time_from)), dates.to_utc(local_dt(day, time_to))


def slot_runs(day, weekdays, time_from, time_to, now_utc):
    """Слот діє (R-H1): день тижня збігається з `weekdays`, і `starts_at ≤ now < due_at`."""
    days = parse_weekdays(weekdays)
    if days is None or day.weekday() not in days:
        return False
    starts_at, due_at = slot_bounds(day, time_from, time_to)
    return starts_at <= now_utc < due_at


def next_slot_today(now_utc, slots):
    """R-H6 п. 1: найближчий слот сьогодні (за Києвом), що ще не почався. `slots` — [(name, time_from, weekdays)];
    результат — (name, «HH:MM») або `None`."""
    today = dates.local_day(now_utc)
    best = None
    for name, time_from, weekdays in slots:
        days = parse_weekdays(weekdays)
        if days is None or today.weekday() not in days:
            continue
        starts_at = dates.to_utc(local_dt(today, time_from))
        if starts_at > now_utc and (best is None or starts_at < best[0]):
            best = (starts_at, name, fmt_hhmm(time_from))
    return (best[1], best[2]) if best else None


def local_hhmm(dt_utc):
    """UTC naive → київське `HH:MM` (серверний час не «протікає» в UI: AC-H24)."""
    return dates.to_local(dt_utc).strftime("%H:%M")
