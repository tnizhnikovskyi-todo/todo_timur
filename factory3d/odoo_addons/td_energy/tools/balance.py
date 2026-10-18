"""R-07: оцінка балансу обліку за годину. Чисті функції без ORM."""


def diff_pct(measured, expected):
    """`|diff| / max(|measured|, |expected|) · 100`; обидва 0 — 0."""
    denom = max(abs(measured), abs(expected))
    if denom == 0:
        return 0.0
    return abs(measured - expected) / denom * 100.0


def evaluate(measured, expected, tol_pct, tol_kwh):
    """Повертає `(diff, pct, state)`; `deviation`, якщо `pct > tol_pct` **і** `|diff| > tol_kwh`."""
    diff = measured - expected
    pct = diff_pct(measured, expected)
    state = "deviation" if pct > tol_pct and abs(diff) > tol_kwh else "ok"
    return diff, pct, state


def expected_q1(feeders_kwh):
    """Ввід Q1: Σ фідерів секції 1."""
    return sum(feeders_kwh)


def expected_q2(feeders_kwh, pv_kwh, chp_kwh, charge_kwh, discharge_kwh):
    """Ввід Q2: Σ фідерів секції 2 − СЕС − КГУ + заряд LUNA − розряд LUNA."""
    return sum(feeders_kwh) - sum(pv_kwh) - chp_kwh + charge_kwh - discharge_kwh
