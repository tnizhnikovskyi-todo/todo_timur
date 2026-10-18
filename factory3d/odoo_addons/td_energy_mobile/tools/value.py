"""R-H4: значення пункту обходу й норма — чисті функції без ORM (джерела, свіжість, підказка, результат)."""

import re
from datetime import timedelta

SOURCE_RE = re.compile(r"^(signal|pult):.+$")
NO_DATA = "немає даних"
OK, DEVIATION, PENDING = "ok", "deviation", "pending"


def parse_source(source):
    """`signal:<код>` / `pult:<шлях>` → (вид, посилання); порожній або некоректний → `None`."""
    if not source or not SOURCE_RE.match(source):
        return None
    kind, ref = source.split(":", 1)
    return kind, ref


def walk_path(data, path):
    """Обхід JSON за точковим шляхом (`kpis.generation.genset.fuel_pct`); відсутній/`null`/нечисло → `None`."""
    node = data
    for key in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        return None
    return float(node)


def is_fresh(last_ts, now, period_s, fresh_s):
    """Сигнал «свіжий», якщо `last_ts ≥ now − max(3·period_s, fresh_s)` (за замовчуванням 120 с)."""
    if not last_ts:
        return False
    return last_ts >= now - timedelta(seconds=max(3 * (period_s or 0), fresh_s))


def fmt_number(value, precision=0):
    """58.0 → «58», 58.46 (precision 1) → «58,5»; десяткова кома."""
    return ("%.*f" % (max(int(precision or 0), 0), value)).replace(".", ",")


def _fmt_norm_number(value):
    """Межа норми без зайвих нулів: 85 → «85», 85,5 → «85,5»."""
    return ("%.2f" % value).rstrip("0").rstrip(".").replace(".", ",")


def _with_unit(text, unit):
    return "%s %s" % (text, unit) if unit else text


def fmt_value(value, unit, precision=0):
    """«58 °C»; `None` → «немає даних» (R-H4)."""
    if value is None:
        return NO_DATA
    return _with_unit(fmt_number(value, precision), unit)


def norm_text(norm_kind, norm_min, norm_max, unit):
    """«до 85 °C» / «від 60 %» / «10–20 °C»; без норми — порожній рядок."""
    if norm_kind == "max":
        return _with_unit("до " + _fmt_norm_number(norm_max), unit)
    if norm_kind == "min":
        return _with_unit("від " + _fmt_norm_number(norm_min), unit)
    if norm_kind == "range":
        return _with_unit("%s–%s" % (_fmt_norm_number(norm_min), _fmt_norm_number(norm_max)), unit)
    return ""


def hint(static_hint, has_source, norm_kind, norm_min, norm_max, unit, precision, value):
    """R-H4: підказка пункту. Без джерела — статична; з джерелом і нормою — «норма … · зараз …»; без норми —
    «зараз …»; немає даних — «зараз —»."""
    if not has_source:
        return static_hint or ""
    now_text = "—" if value is None else fmt_value(value, unit, precision)
    norm = norm_text(norm_kind, norm_min, norm_max, unit)
    if norm:
        return "норма %s · зараз %s" % (norm, now_text)
    return "зараз %s" % now_text


def evaluate(norm_kind, norm_min, norm_max, value):
    """Результат при відмітці (R-H4): немає норми/значення → `ok`; границі включно."""
    if value is None or norm_kind == "none":
        return OK
    if norm_kind == "max":
        return OK if value <= norm_max else DEVIATION
    if norm_kind == "min":
        return OK if value >= norm_min else DEVIATION
    if norm_kind == "range":
        return OK if norm_min <= value <= norm_max else DEVIATION
    return OK
