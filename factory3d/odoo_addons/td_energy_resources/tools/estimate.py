"""R-04: оцінні методи (`mode='estimate'`) — `load_share`, `schedule`, `residual`, `gate_loss`. Чисті функції без ORM.

Результат — швидкість у одиницях `rate_label` ресурсу (`None` — немає вихідних даних → слот `missing`).
"""

DEFAULT_LOAD_FACTOR = 0.75
DEFAULT_IDLE_FACTOR = 0.05
DEFAULT_T_IN = 18.0


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def load_share(kw_avg, p_inst_kw, rate_nominal, load_factor=0.0, idle_factor=0.0):
    """R-04 п. 1: `active = clamp((kw − idle)/(run − idle), 0, 1)`; `rate = rate_nominal × active`.

    `run = p_inst × load_factor` (0,75), `idle = p_inst × idle_factor` (0,05); `kw_avg` — 15-хв середня потужність вузла
    споживача (`td.energy.interval`, `role='consumer'`); `None` — немає інтервалу вузла.
    """
    if kw_avg is None:
        return None
    run = p_inst_kw * (load_factor or DEFAULT_LOAD_FACTOR)
    idle = p_inst_kw * (idle_factor or DEFAULT_IDLE_FACTOR)
    if run <= idle:
        active = 1.0 if kw_avg > idle else 0.0
    else:
        active = clamp((kw_avg - idle) / (run - idle), 0.0, 1.0)
    return rate_nominal * active


def schedule(local_dt, params):
    """R-04 п. 2: `rate = params.rate`, якщо день тижня ∈ `weekdays` і `from_h ≤ локальна година < to_h`; права
    межа виключається. `local_dt` — початок слота за Києвом (naive або aware)."""
    weekdays = params.get("weekdays")
    if weekdays is not None and local_dt.weekday() not in weekdays:
        return 0.0
    hour = local_dt.hour + local_dt.minute / 60.0
    if float(params["from_h"]) <= hour < float(params["to_h"]):
        return float(params["rate"])
    return 0.0


def residual(source_rates, sibling_rates):
    """R-04 п. 3: `max(0, Σ rate(from) − Σ rate(siblings))`; будь-який потрібний слот `None` — `None`."""
    values = list(source_rates) + list(sibling_rates)
    if not source_rates or any(v is None for v in values):
        return None
    return max(0.0, sum(source_rates) - sum(sibling_rates))


def open_fraction(points, t0, t1, threshold=0.5):
    """Частка слота `[t0, t1)`, коли стан ≥ `threshold` (ступінчасте утримання). `points` — `[(ts, value)]`
    відсортовані; значення до першого показання невідоме — береться перше. `None` — показань немає зовсім."""
    pts = sorted((t, v) for t, v in points if v is not None)
    if not pts:
        return None
    span = (t1 - t0).total_seconds()
    state = pts[0][1]
    for t, v in pts:
        if t <= t0:
            state = v
    marks = [t for t, _v in pts if t0 < t < t1]
    edges = [t0] + marks + [t1]
    opened = 0.0
    for a, b in zip(edges, edges[1:], strict=False):
        value = state
        for t, v in pts:
            if t <= a:
                value = v
        if value >= threshold:
            opened += (b - a).total_seconds()
    return opened / span if span else 0.0


def gate_loss(open_frac, t_in, t_out, loss_kw_per_k):
    """R-04 п. 4: `rate_kw = loss_kw_per_k × ΔT × open_frac`, `ΔT = max(0, t_in − t_out)`."""
    if open_frac is None or t_in is None or t_out is None:
        return None
    return loss_kw_per_k * max(0.0, t_in - t_out) * open_frac
