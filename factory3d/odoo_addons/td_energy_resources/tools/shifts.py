"""R-21: вікна змін і «ніч» (контракт C-01 для W4; A-15). Календар — `td.energy.shift_calendar_id`.

`load_windows(env)` → `ShiftWindows`: `shift_of(local_dt)`, `is_shift(local_dt)`, `windows_for(day)`,
`night_window(day)`. `local_dt` — момент за Києвом (naive = місцевий, aware — переводиться); межі, що повертаються
(`windows_for`, `night_window`), — UTC naive (`tools/dates.to_utc`), тож перехід на літній/зимовий час враховано.
"""

import re
from datetime import datetime, time, timedelta

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy.tools.tariff import KYIV

# Типове ім'я рядка календаря Odoo: «Monday Morning» / «Tuesday Afternoon» — усі рядки дня — одна зміна «Зміна»
STANDARD_NAME = re.compile(r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", re.IGNORECASE)
STANDARD_SHIFT = "Зміна"
# Умовчання (макет, Q-23): пн–пт «Зміна 1» 07:00–16:00 і «Зміна 2» 16:00–23:00
DEFAULT_WINDOWS = tuple(
    (wd, name, h_from, h_to)
    for wd in range(5)
    for name, h_from, h_to in (("Зміна 1", 7.0, 16.0), ("Зміна 2", 16.0, 23.0))
)


def _hours(env, name, default):
    val = env["ir.config_parameter"].sudo().get_param("td.energy_resources." + name)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def calendar_windows(calendar):
    """R-21 п. 1: `[(weekday, name, from_h, to_h)]` з `attendance_ids` (без обіду й секцій); порожньо — немає змін."""
    groups = {}
    for att in calendar.attendance_ids:
        if att.display_type or att.day_period == "lunch":
            continue
        name = STANDARD_SHIFT if STANDARD_NAME.match(att.name or "") else (att.name or STANDARD_SHIFT)
        key = (int(att.dayofweek), name)
        lo, hi = groups.get(key, (att.hour_from, att.hour_to))
        groups[key] = (min(lo, att.hour_from), max(hi, att.hour_to))
    return sorted((wd, name, lo, hi) for (wd, name), (lo, hi) in groups.items() if hi > lo)


def load_windows(env):
    """Календар із параметра `td.energy.shift_calendar_id`; не заданий або порожній — умовчання макета."""
    windows = ()
    cal_id = env["ir.config_parameter"].sudo().get_param("td.energy.shift_calendar_id")
    if cal_id and str(cal_id).isdigit():
        calendar = env["resource.calendar"].sudo().browse(int(cal_id)).exists()
        if calendar:
            windows = calendar_windows(calendar)
    return ShiftWindows(
        windows or DEFAULT_WINDOWS,
        night_from_h=_hours(env, "night_from_h", 23.0),
        night_to_h=_hours(env, "night_to_h", 6.5),
    )


def _as_local(local_dt):
    if local_dt.tzinfo is not None:
        return local_dt.astimezone(KYIV).replace(tzinfo=None)
    return local_dt


def _local_to_utc(day, hours):
    return dates.to_utc(datetime.combine(day, time(0, 0)) + timedelta(hours=hours))


class ShiftWindows:
    """Вікна змін тижня: `windows` — `[(weekday, name, from_h, to_h)]` (годинні межі, 0 = пн)."""

    def __init__(self, windows, night_from_h=23.0, night_to_h=6.5):
        self.windows = list(windows)
        self.night_from_h = night_from_h
        self.night_to_h = night_to_h

    def shift_of(self, local_dt):
        """Назва зміни, що діє в місцевий момент `local_dt`, інакше `None`; права межа виключається."""
        local = _as_local(local_dt)
        hour = local.hour + local.minute / 60.0 + local.second / 3600.0
        for wd, name, h_from, h_to in self.windows:
            if wd == local.weekday() and h_from <= hour < h_to:
                return name
        return None

    def is_shift(self, local_dt):
        return self.shift_of(local_dt) is not None

    def windows_for(self, day):
        """Зміни місцевої дати `day` (`date`): `[(name, from_utc, to_utc)]` за порядком початку."""
        return [
            (name, _local_to_utc(day, h_from), _local_to_utc(day, h_to))
            for wd, name, h_from, h_to in sorted(self.windows, key=lambda w: (w[0], w[2]))
            if wd == day.weekday()
        ]

    def night_window(self, day):
        """Ніч, що закінчується вранці місцевої дати `day`: `[вчора night_from_h, сьогодні night_to_h)` у UTC naive."""
        return _local_to_utc(day - timedelta(days=1), self.night_from_h), _local_to_utc(day, self.night_to_h)

    def first_start(self, day):
        """Початок першої зміни дня `day` (UTC naive) або `None` (вихідний)."""
        wins = self.windows_for(day)
        return wins[0][1] if wins else None
