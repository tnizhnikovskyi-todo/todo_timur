"""Ціни й собівартість демо-компанії (LP-07): оцінка вартості компонентів у ₴ і ціна під планову маржу. Без ORM."""

import math

from .noise import rng

MARGIN_MIN = 0.25
MARGIN_MAX = 0.40
# ₴ за одиницю обліку компонента, за префіксом коду; перший збіг із початку коду. Оцінка для демо: на типових
# специфікаціях виробу вона дає собівартість матеріалів ≈ 60…75 % прайсової ціни виробу.
COST_BY_PREFIX = (
    ("DSP18", 2300.0),
    ("DSP16", 2050.0),
    ("MDF18", 2600.0),
    ("HDF3", 560.0),
    ("EB04", 11.0),
    ("EB2", 34.0),
    ("LFM-ENA", 640.0),
    ("LFM-ENW", 610.0),
    ("LFM-GLUE", 470.0),
    ("LFM-PR", 380.0),
    ("LFM-UV", 560.0),
    ("PVC-", 120.0),
    ("PAL-", 480.0),
    ("PK-COR", 14.0),
    ("PK-FF", 52.0),
    ("PK-STR", 430.0),
    ("FR-", 980.0),
    ("FUR-CF", 2.6),
    ("FUR-CP", 1.3),
    ("FUR-AN", 7.5),
    ("FUR-DM", 68.0),
    ("FUR-DW", 1.1),
    ("FUR-EXS", 4.2),
    ("FUR-EX", 5.4),
    ("FUR-GL", 520.0),
    ("FUR-GS", 340.0),
    ("FUR-HD", 118.0),
    ("FUR-HG", 140.0),
    ("FUR-HN", 230.0),
    ("FUR-LG", 46.0),
    ("FUR-MB", 780.0),
    ("FUR-PL", 320.0),
    ("FUR-SC", 0.8),
    ("FUR-SL", 520.0),
    ("FUR-SP", 1.5),
    ("FUR-TB", 1050.0),
)
COST_BY_CATEGORY = (
    ("Плитні", 2100.0),
    ("Крайка", 30.0),
    ("ЛФМ", 500.0),
    ("Пакування", 120.0),
    ("Фасади", 980.0),
    ("Фурнітура", 90.0),
)
COST_DEFAULT = 150.0


def guess_unit_cost(code, categ=""):
    """Оцінка собівартості одиниці компонента, ₴: за префіксом коду, інакше за назвою категорії, інакше 150."""
    code = (code or "").upper()
    for prefix, cost in COST_BY_PREFIX:
        if code.startswith(prefix):
            return cost
    for key, cost in COST_BY_CATEGORY:
        if key.lower() in (categ or "").lower():
            return cost
    return COST_DEFAULT


def margin_pct(price, cost):
    """Маржа, %: `(ціна − собівартість) / ціна`; 0 за нульової ціни."""
    return (price - cost) / price * 100.0 if price else 0.0


def order_price(list_price, unit_cost, key):
    """Ціна одиниці у замовленні: прайс ±8 %, але так, щоб планова маржа лишилась у 25…40 %.

    Спершу `прайс × (0,95…1,08)`, потім затиснення до `[cost/0,75; cost/0,60]` (межі округлені досередини до 10 ₴).
    Немає собівартості — ціна з прайсу. Округлення до 10 ₴.
    """
    price = list_price * (0.95 + 0.13 * rng("price:%s" % key).random())
    if unit_cost <= 0:
        return float(round(price, -1)) or round(price, 2)
    lo = math.ceil(unit_cost / (1.0 - MARGIN_MIN) / 10.0) * 10.0
    hi = math.floor(unit_cost / (1.0 - MARGIN_MAX) / 10.0) * 10.0
    if hi < lo:  # дрібна собівартість: десяток ₴ грубіший за вікно маржі
        return round(min(max(price, unit_cost / (1.0 - MARGIN_MIN)), unit_cost / (1.0 - MARGIN_MAX)), 2)
    return min(max(float(round(price, -1)), lo), hi)
