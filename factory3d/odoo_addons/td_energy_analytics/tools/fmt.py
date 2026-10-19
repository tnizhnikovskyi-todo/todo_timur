"""R-21, R-22: формати чисел і шкали осей. Чисті функції без ORM."""

import math

MINUS = "−"  # знак мінуса в підписах


def round_half_up(x, digits=0):
    """Округлення «від нуля» (на відміну від банківського `round`)."""
    if x is None:
        return None
    factor = 10.0**digits
    value = math.floor(abs(x) * factor + 0.5 + 1e-9) / factor
    return math.copysign(value, x) if value else 0.0


def r_int(x):
    return None if x is None else int(round_half_up(x))


def fmt_int(x):
    """Ціле: пробіл — роздільник тисяч."""
    return "{:,}".format(int(round_half_up(x))).replace(",", " ")


def fmt_dec(x, digits=1):
    """Кома — десятковий роздільник, пробіл — тисяч."""
    value = round_half_up(x, digits)
    return "{:,.{d}f}".format(value, d=digits).replace(",", " ").replace(".", ",")


def fmt_signed(x):
    """Ціле з явним знаком: «+2», «−6», «0» (мінус — U+2212)."""
    value = int(round_half_up(x))
    if value > 0:
        return "+%d" % value
    if value < 0:
        return "%s%d" % (MINUS, -value)
    return "0"


def spec_value(x):
    """Питомий показник у JSON: < 10 → 2 знаки, інакше 1 знак."""
    if x is None:
        return None
    return round_half_up(x, 2) if abs(x) < 10 else round_half_up(x, 1)


def spec_text(x):
    """Питомий показник у тексті: «0,68», «29,0»; `None` → «—»."""
    if x is None:
        return "—"
    return fmt_dec(x, 2 if abs(x) < 10 else 1)


def ceil_to(x, step):
    return math.ceil(x / step - 1e-12) * step


def floor_to(x, step):
    return math.floor(x / step + 1e-12) * step


def hhmm(hours):
    """Годинні межі зміни (`7.0`, `15.5`) → «07:00», «15:30»."""
    total = int(round(hours * 60))
    return "%02d:%02d" % (total // 60 % 24, total % 60)
