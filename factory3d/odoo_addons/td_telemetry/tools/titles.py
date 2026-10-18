"""Заголовки заявок ТО (R-05, A-21): форматування чисел і шаблон `alarm_title`. Чисті функції."""

import re
from decimal import ROUND_HALF_UP, Decimal

TITLE_MAX = 256
DEFAULT_TITLE = "{name}: {value} {unit} при нормі {rel} {threshold} {unit}"
DEFAULT_STATE_TITLE = "{name}: стан «{text}»"
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def fmt_num(x, decimals=2):
    """A-21: округлення до `decimals`, десяткова кома, без зайвих нулів, групи тисяч через пробіл (|x| ≥ 1000)."""
    if x is None or x is False:
        return ""
    decimals = max(int(decimals or 0), 0)
    q = Decimal(1).scaleb(-decimals)
    d = Decimal(repr(float(x))).quantize(q, rounding=ROUND_HALF_UP)
    if d == 0:
        return "0"
    sign = "-" if d < 0 else ""
    int_part, _dot, frac = format(abs(d), "f").partition(".")
    int_part = "{:,}".format(int(int_part)).replace(",", " ")
    frac = frac.rstrip("0")
    return sign + int_part + ("," + frac if frac else "")


def render_title(signal, value, rel, threshold, text=None):
    """Заголовок заявки за шаблоном сигналу; невідомі плейсхолдери лишаються буквально; ≤ 256 символів."""
    decimals = signal.decimals if signal.decimals is not None else 2
    tpl = signal.alarm_title
    if not tpl:
        tpl = DEFAULT_STATE_TITLE if signal.kind == "state" else DEFAULT_TITLE
    equipment = signal.equipment_id
    values = {
        "name": signal.name or "",
        "equipment": equipment.name if equipment else "",
        "code": (equipment.td_code or "") if equipment else "",
        "quantity": signal.quantity or "",
        "value": fmt_num(value, decimals) if value is not None else "",
        "unit": signal.unit or "",
        "threshold": fmt_num(threshold, decimals) if threshold is not None else "",
        "rel": rel or "",
        "text": text if text is not None else (signal.last_text or ""),
    }
    title = _PLACEHOLDER.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), tpl)
    return title[:TITLE_MAX]
