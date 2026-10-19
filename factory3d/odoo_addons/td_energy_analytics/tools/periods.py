"""R-01: періоди й кошики екрана «Аналітика». Чисті функції без ORM."""

import calendar
from datetime import date, timedelta

PERIODS = ("w", "m", "q", "y")
DIMS = ("area", "eq", "mo", "prod", "shift")
PERIOD_LABELS = {"w": "7 днів", "m": "30 днів", "q": "13 тижнів", "y": "12 місяців"}
UNITS = {"w": "кВт·год за день", "m": "кВт·год за день", "q": "кВт·год за тиждень", "y": "кВт·год за місяць"}
BAR_UNITS = {"w": "day", "m": "day", "q": "week", "y": "month"}
WEEKDAYS = ("пн", "вт", "ср", "чт", "пт", "сб", "нд")
MONTHS = ("січ", "лют", "бер", "кві", "тра", "чер", "лип", "сер", "вер", "жов", "лис", "гру")
MONTH_NAMES = (
    "січень", "лютий", "березень", "квітень", "травень", "червень", "липень", "серпень", "вересень", "жовтень",
    "листопад", "грудень",
)  # fmt: skip


def shift_months(day, delta):
    """Перше число місяця `day` зі зсувом на `delta` місяців."""
    index = day.year * 12 + day.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


def window(period, today):
    """`(date_from, date_to)` включно для періоду `w|m|q|y` (R-01)."""
    if period == "w":
        return today - timedelta(days=6), today
    if period == "m":
        return today - timedelta(days=29), today
    if period == "q":
        return today - timedelta(days=90), today
    if period == "y":
        return shift_months(today, -11), today
    raise ValueError(period)


def buckets(period, today):
    """Кошики вікна: `[{key, label, date_from, date_to}]` за зростанням дати (R-01)."""
    out = []
    if period in ("w", "m"):
        first, last = window(period, today)
        n = (last - first).days + 1
        for i in range(n):
            day = first + timedelta(days=i)
            if period == "w":
                label = WEEKDAYS[day.weekday()]
            else:
                label = str(day.day) if i % 5 == 0 else ""
            out.append({"key": day.isoformat(), "label": label, "date_from": day, "date_to": day})
    elif period == "q":
        for pos, i in enumerate(range(12, -1, -1)):
            end = today - timedelta(days=7 * i)
            out.append(
                {
                    "key": end.isoformat(), "label": "т%d" % (pos + 1) if pos % 2 == 0 else "",
                    "date_from": end - timedelta(days=6), "date_to": end,
                }
            )  # fmt: skip
    else:
        for k in range(11, -1, -1):
            first = shift_months(today, -k)
            last = today if k == 0 else date(first.year, first.month, calendar.monthrange(first.year, first.month)[1])
            out.append(
                {"key": first.strftime("%Y-%m"), "label": MONTHS[first.month - 1], "date_from": first, "date_to": last}
            )
    return out


def weeks(today, n=12):
    """`n` ковзних тижнів `[today − 6 − 7i, today − 7i]`, `i = n−1…0` (за зростанням; R-05 п. 3)."""
    return [
        {"key": (today - timedelta(days=7 * i)).isoformat(), "date_from": today - timedelta(days=6 + 7 * i),
         "date_to": today - timedelta(days=7 * i)}
        for i in range(n - 1, -1, -1)
    ]  # fmt: skip


def bucket_index(period, today):
    """`day → індекс кошика` для вікна періоду (для швидкого групування суток)."""
    index = {}
    for i, bucket in enumerate(buckets(period, today)):
        day = bucket["date_from"]
        while day <= bucket["date_to"]:
            index[day] = i
            day += timedelta(days=1)
    return index


def parse_month(value, today):
    """`YYYY-MM` / `date` / `None` → перше число місяця (`None` — поточний)."""
    if value is None or value is False or value == "":
        return today.replace(day=1)
    if isinstance(value, date):
        return value.replace(day=1)
    year, month = str(value)[:7].split("-")
    return date(int(year), int(month), 1)


def month_days(first):
    return calendar.monthrange(first.year, first.month)[1]


def param(env, name, default=None):
    """Параметр `td.energy_analytics.<name>` (рядок) або `default`."""
    value = env["ir.config_parameter"].sudo().get_param("td.energy_analytics." + name)
    return default if value in (None, False, "") else value


def param_int(env, name, default=0):
    try:
        return int(float(param(env, name, default)))
    except (TypeError, ValueError):
        return default


def param_float(env, name, default=0.0):
    try:
        return float(param(env, name, default))
    except (TypeError, ValueError):
        return default
