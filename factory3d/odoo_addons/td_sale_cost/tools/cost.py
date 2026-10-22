"""Чисті функції собівартості замовлення (без ORM): підсумки, відхилення, маржа, прогрес, колір, прогноз.

`None` у статті означає «немає даних» і не дорівнює нулю: підсумок із самих `None` теж `None`.
"""

ARTICLES = ("machine", "energy", "material", "waste")
WARN_PCT = 5.0  # відхилення факту від плану, % — жовтий
ALERT_PCT = 15.0  # відхилення, % — червоний
# Енергія: план — статистична оцінка (середні ₴/год верстата за останні дні), а факт — вимір лічильника за завдання,
# що коливається від доби до доби (тариф, навантаження), тож допуск ширший за загальний.
ENERGY_WARN_PCT = 25.0
ENERGY_ALERT_PCT = 50.0
ENERGY_RATE_DAYS = 7  # вікно історії для ₴/год плану енергії, днів


def total(values):
    """Сума значень, що не `None`; усі `None` (або порожньо) — `None`."""
    vals = [v for v in values if v is not None]
    return sum(vals) if vals else None


def add(a, b):
    """Сума двох значень із `None` = немає даних."""
    return total((a, b))


def num(value):
    """`None` → 0.0 для арифметики підсумків."""
    return value or 0.0


def deviation_pct(fact, plan):
    """Відхилення факту від плану, %: `(факт − план) / план × 100`; без плану — `None`."""
    if not plan or plan <= 0:
        return None
    return (num(fact) - plan) / plan * 100.0


def level(fact, plan, warn=WARN_PCT, alert=ALERT_PCT):
    """Колір відхилення: `ok` (до `warn` %), `warn` (до `alert` %), `alert` (більше), `none` (ні плану, ні факту).
    Є факт, але немає плану — `warn`. Недовитрата — `ok`."""
    fact, plan = num(fact), num(plan)
    if not fact and not plan:
        return "none"
    if plan <= 0:
        return "warn"
    dev = deviation_pct(fact, plan)
    if dev > alert:
        return "alert"
    return "warn" if dev > warn else "ok"


def margin_pct(price, cost):
    """Маржа до ціни замовлення, %: `(ціна − собівартість) / ціна × 100`; без ціни — `None`."""
    if not price or price <= 0:
        return None
    return (price - cost) / price * 100.0


def fraction(state, expected, duration):
    """Частка виконання операції: виконана — 1; інакше `min(тривалість / план, 1)`; без плану чи роботи — 0."""
    if state == "done":
        return 1.0
    if expected > 0 and duration > 0:
        return min(duration / expected, 1.0)
    return 0.0


def progress(rows):
    """Прогрес МО, 0…1: середнє `fraction` операцій, зважене плановим часом; `rows` — `[(план_хв, частка)]`.
    Без планового часу — `None` (рішення за станом МО приймає викликач)."""
    expected = sum(e for e, _f in rows)
    if expected <= 0:
        return None
    return sum(e * f for e, f in rows) / expected


def forecast(fact, plan, plan_now):
    """Прогноз собівартості на завершення: факт + решта плану (`план − план на поточний стан`, не менше 0)."""
    return fact + max(plan - plan_now, 0.0)
