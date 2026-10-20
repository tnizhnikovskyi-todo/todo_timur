"""R-05: аварії, зупинки без аварії й вузли мокапу (`S.hl`). Значення — зі знімка `v` (код без `chp/`)."""

from odoo.addons.td_telemetry.tools.titles import fmt_num

STATE_NAMES = {0: "Резерв", 1: "Пуск", 2: "Робота", 3: "Аварія", 4: "Охолодження"}
START_STEPS = (  # R-13: 9 кроків пуску
    ("vent", "Вентиляція контейнера"),
    ("warm", "Попередній підігрів ОЖ"),
    ("lube", "Попереднє змащення"),
    ("proving", "Перевірка герметичності клапанів"),
    ("crank", "Прокрутка стартером"),
    ("ign", "Запалювання"),
    ("idle", "Холостий хід"),
    ("sync", "Синхронізація з мережею"),
    ("load", "Набір навантаження"),
)
ACK_REASONS = {  # R-06
    1: "немає дозволу КГУ",
    2: "тиск газу нижче мінімуму",
    3: "на щиті не «Дистанційне»",
    4: "немає мережі S2",
    5: "спрацював ROCOF",
    6: "загазованість ≥ 10 % НКПР",
    7: "пожежа або гасіння",
    8: "t зворотки > уставки",
    9: "t ОЖ ≥ 95 °C",
    10: "АКБ < 23,5 В",
    11: "рівень масла або контур аварійного стопу",
    12: "стан не допускає команду",
    13: "значення поза діапазоном",
}


def _f(v, key, nd):
    return fmt_num(v.get(key), nd) if v.get(key) is not None else "—"


def alarm_info(code, v, th):
    """`alarm/code` → (текст, вузол)."""
    code = int(code)
    if code == 111:
        return f"Низький тиск газу: {_f(v, 'gas/p_in', 2)} бар < {fmt_num(th['gas_min_bar'], 2)} бар", "gasramp"
    if code == 112:
        return f"Перегрів ОЖ: {_f(v, 'eng/t_jacket_out', 1)} °C ≥ 97 °C", "engine"
    if code == 113:
        return (
            f"Висока температура зворотки: {_f(v, 'ht/t_ret', 1)} °C > {fmt_num(th['ret_set_c'], 0)} °C (уставка)",
            "mixv",
        )
    if code == 114:
        return (
            f"Загазованість у контейнері: {_f(v, 'safe/lel', 0)} % НКПР ≥ {fmt_num(th['lel_alarm_pct'], 0)} %",
            "gasdet",
        )
    if code == 115:
        return "Пожежа в контейнері: спрацювала пожежна сигналізація", "fire"
    if code == 116:
        return "Аварійний стоп оператора", "estop"
    return f"Невідома аварія {code}", "cabinet"


def trip_info(code, v, th):
    """`alarm/trip` → (рівень `warn|alarm`, текст, вузол)."""
    code = int(code)
    if code == 1:
        return (
            "warn",
            "Зникла мережа S2: QF-CHP відключено, острівний режим не передбачено → охолодження",
            "qf",
        )
    if code == 2:
        return (
            "alarm",
            f"Захист ROCOF / векторний зсув: df/dt = {_f(v, 'safe/rocof_dfdt', 2)} Гц/с (> 1,0), "
            f"Δφ = {_f(v, 'safe/rocof_dphi', 1)}° (> 12°). QF-CHP відключено → охолодження",
            "qf",
        )
    if code == 3:
        return "warn", "Дозвіл КГУ знято: контрольована зупинка", "cabinet"
    return "warn", f"Невідома зупинка {code}", "cabinet"


def state_name(code):
    return STATE_NAMES.get(int(code), f"Стан {int(code)}")


def step_name(k):
    """Крок 1…9 → назва R-13."""
    return START_STEPS[k - 1][1] if 1 <= k <= len(START_STEPS) else f"Крок {k}"
