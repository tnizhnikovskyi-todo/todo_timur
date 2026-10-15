"""R-22a: тексти заявок і журналу відхилень (українською; десяткова кома; час — Київ)."""

from datetime import timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")


def num(x, decimals=0):
    """Число з комою: `decimals=0` — ціле (half-up), інакше з фіксованою кількістю знаків."""
    q = Decimal(1).scaleb(-decimals)
    d = Decimal(repr(float(x or 0))).quantize(q, rounding=ROUND_HALF_UP)
    text = format(d, "f").replace(".", ",")
    return "0" + text[1:] if text.startswith("-0") and d == 0 else text


def kyiv(dt):
    """UTC naive → «дд.мм.рррр гг:хх» (Київ)."""
    if not dt:
        return "—"
    return dt.replace(tzinfo=timezone.utc).astimezone(KYIV).strftime("%d.%m.%Y %H:%M")


def light_off(code, zone, level, e_norm, e_now, group_dali, panel, since):
    return {
        "name": "Освітлення %s (%s): вимкнено в робочий час — рівень %s %% при нормі %s лк"
        % (code, zone, num(level), num(e_norm)),
        "value": float(e_now),
        "threshold": float(e_norm),
        "line": "Група DALI G:%s, щит %s; вимкнено з %s." % (group_dali, panel, kyiv(since)),
    }


def light_low(code, zone, level, e_norm, e_now, e_calc, tol_pct, since):
    return {
        "name": "Освітлення %s (%s): ≈ %s лк при нормі %s лк (рівень %s %%)"
        % (code, zone, num(e_now), num(e_norm), num(level)),
        "value": float(e_now),
        "threshold": float(e_norm),
        "line": "Розрахунок: %s лк при 100 %%, допуск %s %%; з %s." % (num(e_calc), num(tol_pct, 0), kyiv(since)),
    }


def unit_off(code, zone, mode_label, airflow, state, since):
    return {
        "name": "Установка %s (%s): не працює в робочий час — режим «%s»" % (code, zone, mode_label or "—"),
        "value": float(airflow or 0.0),
        "threshold": 0.0,
        "line": "Стан %s; з %s." % (state, kyiv(since)),
    }


def cold(code, zone, indoor, t_min, setpoint_day, since):
    return {
        "name": "Установка %s (%s): у зоні %s °C при нормі від %s °C" % (code, zone, num(indoor, 1), num(t_min, 1)),
        "value": float(indoor),
        "threshold": float(t_min),
        "line": "Уставка %s °C; з %s." % (num(setpoint_day, 1), kyiv(since)),
    }


def heat_deficit(deficit, need, available, threshold, chp, chp_source, boilers_on, boilers, boiler_state):
    return {
        "name": "Котельня: дефіцит тепла %s кВт (потреба %s кВт, джерела %s кВт)"
        % (num(deficit), num(need), num(available)),
        "value": float(deficit),
        "threshold": float(threshold),
        "line": "КГУ %s кВт (%s), котлів у роботі %s з %s, стан «%s»."
        % (num(chp), chp_source, boilers_on, boilers, boiler_state),
    }


def faults_line(faulty, panel, dali_group):
    return "Несправні світильники: %s; щит %s, DALI-група G:%s." % (faulty or "—", panel, dali_group)
