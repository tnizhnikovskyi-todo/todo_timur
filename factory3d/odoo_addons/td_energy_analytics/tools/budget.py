"""R-06: бюджет і прогноз (чисті функції; дані подає модель)."""

from datetime import timedelta

from .fmt import fmt_int, round_half_up
from .periods import MONTH_NAMES, month_days


def typical_by_weekday(rows, today, weeks, min_days):
    """Типові доби: `rows` — `{day: cost}` (за окно `[today − 7·weeks, today − 1]`, без сьогодні).

    `typical[w]` (w = 0…6, 0 = пн) — середнє для дня тижня; зразків `< min_days` — середнє всіх діб вікна;
    даних немає — `None`.
    """
    first = today - timedelta(days=7 * weeks)
    window = {d: v for d, v in rows.items() if first <= d < today}
    if not window:
        return None
    overall = sum(window.values()) / len(window)
    out = []
    for w in range(7):
        samples = [v for d, v in window.items() if d.weekday() == w]
        out.append(sum(samples) / len(samples) if len(samples) >= min_days else overall)
    return out


def status(plan, first, today, actual, typical):
    """`get_status` (R-06): `actual` — `{day: cost}` за місяць; `typical` — `typical_by_weekday` або `None`.

    Повертає `{fact, fact_pct, month_share, forecast, delta_pct, text}` (суми — без округлення до ₴ у `text`).
    """
    days = month_days(first)
    last = first + timedelta(days=days - 1)
    ref = min(max(today, first), last)  # доба «станом на»
    fact = sum(v for d, v in actual.items() if first <= d <= ref)
    fact_pct = int(round_half_up(fact / plan * 100)) if plan else 0
    month_share = int(round_half_up(ref.day / days * 100))
    forecast = None
    if today > last:
        forecast = fact
    elif typical is not None:
        forecast = sum(actual.get(first + timedelta(days=i), 0.0) for i in range(ref.day - 1))
        forecast += max(actual.get(ref, 0.0), typical[ref.weekday()])
        for i in range(ref.day, days):
            forecast += typical[(first + timedelta(days=i)).weekday()]
    delta = int(round_half_up((forecast - plan) / plan * 100)) if forecast is not None and plan else None
    text = "Факт на %s — %s ₴ (%d %% при %d %% місяця)" % (ref.strftime("%d.%m"), fmt_int(fact), fact_pct, month_share)
    if forecast is not None:
        if delta:
            text += " · прогноз %s ₴, на %d %% %s бюджету" % (
                fmt_int(forecast),
                abs(delta),
                "нижче" if delta < 0 else "вище",
            )
        else:
            text += " · прогноз %s ₴, відповідає бюджету" % fmt_int(forecast)
    return {
        "fact": fact, "fact_pct": fact_pct, "month_share": month_share, "forecast": forecast, "delta_pct": delta,
        "text": text,
    }  # fmt: skip


def month_label(first):
    return MONTH_NAMES[first.month - 1]
