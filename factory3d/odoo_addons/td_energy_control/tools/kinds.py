"""R-42, M-29, M-31: схеми параметрів сценаріїв і видів команд, нормалізація, шаблони тексту. Чисті функції (без ORM).

Схема параметра — dict `{"name","label","type","min","max","default","unit","choices"}`;
`type` ∈ float|int|bool|time|enum|days|list_int. `min`/`max` можуть бути рядком — ім'ям межі з контексту
(`bess_max_kw`), яку підставляє `resolve_bounds`.
"""

import re

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
VENT_MODES = ("VE", "VEL", "AQ", "REC", "EA", "SA", "ST", "Off")  # = td_bms.tools.hvac.MODE_LABELS (перевіряє тест)
SCENARIO_CODES = ("peak", "self", "pfc", "night", "backup", "chp")
SCENARIO_TITLES = {
    "peak": "Зрізання піку",
    "self": "Самоспоживання СЕС",
    "pfc": "Компенсація реактивної потужності",
    "night": "Нічний режим (BMS)",
    "backup": "Резервне живлення",
    "chp": "КГУ за графіком і ціною",
}
SCENARIO_SHORT = {
    "peak": "Пік",
    "self": "Самоспоживання",
    "pfc": "PFC",
    "night": "Ніч",
    "backup": "Резерв",
    "chp": "КГУ",
}
REMOTE_REFUSED = (
    "Дистанційне перемикання вимкнено: td.energy_control.remote_switching_enabled. Зверніться до адміністратора."
)


def P(name, label, type_, lo=None, hi=None, default=None, unit="", choices=None):  # noqa: N802
    return {
        "name": name,
        "label": label,
        "type": type_,
        "min": lo,
        "max": hi,
        "default": default,
        "unit": unit,
        "choices": list(choices) if choices else None,
    }


SCENARIO_PARAMS = {
    "peak": [
        P("limit_kw", "Уставка імпорту", "float", 100, 2000, 760, "кВт"),
        P("activate_margin_kw", "Запас активації", "float", 0, 200, 30, "кВт"),
        P("margin_kw", "Миттєвий запас", "float", 0, 100, 20, "кВт"),
        P("release_margin_kw", "Запас зняття", "float", 0, 200, 40, "кВт"),
        P("release_hold_s", "Утримання перед зняттям", "int", 30, 1800, 180, "с"),
        P("stage_delay_s", "Пауза між ступенями", "int", 10, 600, 60, "с"),
        P("bess_max_kw", "Макс. потужність BESS", "float", 0, 200, 100, "кВт"),
        P("bess_min_soc_pct", "Мін. заряд BESS", "float", 10, 90, 30, "%"),
        P("chp_allowed", "Дозволити КГУ", "bool", default=True),
        P("shed_allowed", "Дозволити скидання", "bool", default=True),
    ],
    "self": [
        P("export_max_kw", "Макс. експорт", "float", 0, 100, 20, "кВт"),
        P("export_deadband_kw", "Мертва зона експорту", "float", 0, 50, 5, "кВт"),
        P("bess_target_soc_pct", "Цільовий заряд BESS", "float", 50, 100, 95, "%"),
        P("bess_max_kw", "Макс. потужність BESS", "float", 0, 200, 100, "кВт"),
        P("curtail_pv", "Обмежувати СЕС", "bool", default=True),
        P("curtail_delay_s", "Затримка обмеження", "int", 10, 600, 60, "с"),
        P("restore_hold_s", "Утримання перед відновленням", "int", 10, 600, 120, "с"),
    ],
    "pfc": [],
    "night": [
        P("from", "Початок вікна", "time", default="23:00"),
        P("to", "Кінець вікна", "time", default="06:30"),
        P("days", "Дні початку вікна", "days", 1, 7, [1, 2, 3, 4, 5, 6, 7]),
        P("vent_mode", "Режим вентиляції вночі", "enum", default="VEL", choices=VENT_MODES),
        P("day_vent_mode", "Режим вентиляції вдень", "enum", default="VE", choices=VENT_MODES),
        P("vent_pct", "Вентиляція, % (довідково)", "int", 10, 100, 30, "%"),
        P("light_scene_number", "Сцена освітлення: черговий", "int", 1, 16, 1),
        P("light_scene_day_number", "Сцена освітлення: робочий", "int", 1, 16, 2),
        P("heat_setpoint_c", "Уставка опалення вночі", "float", 5, 30, 16.0, "°C"),
    ],
    "backup": [
        P("genset_capacity_kw", "Потужність ДГУ", "float", 50, 5000, 507, "кВт"),
        P("critical_kw", "Критичні навантаження (довідково)", "float", 0, 5000, 180, "кВт"),
        P("restore_delay_s", "Затримка відновлення", "int", 30, 1800, 120, "с"),
    ],
    "chp": [
        P("min_run_h", "Мін. час роботи", "float", 0.5, 24, 2.0, "год"),
        P("min_off_min", "Мін. пауза", "int", 0, 240, 30, "хв"),
        P("gas_price_uah_m3", "Ціна газу", "float", 0, 200, 19.80, "₴/м³"),
        P("gas_m3_per_kwh", "Витрата газу", "float", 0.1, 1.0, 0.25, "м³/кВт·год"),
        P("price_margin_uah_kwh", "Мін. вигода", "float", 0, 50, 0.5, "₴/кВт·год"),
        P("use_slots", "Запускати у слотах", "bool", default=True),
        P("ramp_min", "Вихід на потужність (довідково)", "int", 1, 30, 6, "хв"),
    ],
}
PARAM_DEFAULTS = {code: {s["name"]: s["default"] for s in schema} for code, schema in SCENARIO_PARAMS.items()}

# Види команд: схеми параметрів (SPEC 5.3). Межа-рядок — ім'я з контексту (`bess_max_kw`).
KIND_PARAMS = {
    "bess_charge": [
        P("power_kw", "Потужність", "float", 1, "bess_max_kw", 50, "кВт"),
        P("until", "До", "time", default="16:00"),
        P("soc_limit_pct", "Межа заряду", "float", 50, 100, 95, "%"),
    ],
    "bess_discharge": [
        P("power_kw", "Потужність", "float", 1, "bess_max_kw", 100, "кВт"),
        P("duration_min", "Тривалість", "int", 1, 240, 60, "хв"),
    ],
    "genset_test": [P("mode", "Варіант тесту", "enum", default="idle", choices=("idle",))],
    "light_break": [
        P("level_pct", "Рівень", "int", 10, 100, 50, "%"),
        P("duration_min", "Тривалість", "int", 1, 120, 30, "хв"),
        P("scene_number", "Номер сцени", "int", 1, 16, 3),
    ],
    "vent_eco": [
        P("vent_pct", "Продуктивність", "int", 30, 100, 70, "%"),
        P("duration_min", "Тривалість", "int", 1, 480, 120, "хв"),
    ],
    "air_setpoint": [P("setpoint_bar", "Уставка тиску", "float", 5.0, 8.5, 6.5, "бар")],
}

# Логічні входи/сигнали (єдине джерело для Odoo-перевірок і конфігу API-24): логічне ім'я → код сигналу.
SIGNALS = {
    "qs_cmd": "energy_control/qs/cmd",
    "qs_ack": "energy_control/qs/ack",
    "qs_state": "energy/cells/QS/state",
    "ats_lock": "energy_control/ats/parallel_lock",
    "pfc_mode": "energy_control/pfc/mode",
    "pfc_cos": "energy_control/pfc/cos_target",
    "bess_mode": "energy_control/bess/mode",
    "bess_sp": "energy_control/bess/setpoint_kw",
    "bess_until": "energy_control/bess/until_soc",
    "bess_valid": "energy_control/bess/valid_s",
    "bess_ack": "energy_control/bess/ack",
    "bess_temp": "energy_control/bess/temp_c",
    "chp_cmd": "energy_control/chp/cmd",
    "chp_ack": "energy_control/chp/ack",
    "chp_permit": "energy_control/chp/permit",
    "chp_gas": "energy_control/chp/gas_bar",
    "air_sp": "energy_control/air/setpoint_bar",
    "air_min": "energy_control/air/min_consumer_bar",
    "pv_limit": "energy_control/pv/limit_pct",
    "shed_valid": "energy_control/shed/valid_s",
    "remote": "energy_control/ctl/remote",
    "ctl_hb": "energy_control/ctl/heartbeat",
    "auto_hb": "energy_control/auto/heartbeat",
}
INPUTS = {
    "p_total": "energy/totals/p_now",
    "air_bar": "equipment/COMPRESSOR/pressure_bar",
    "grid_kw": "infra/totals/grid_kw",
    "export_kw": "infra/totals/export_kw",
    "pv_kw": "infra/totals/pv_now",
    "bess_kw": "infra/totals/bess_kw",
    "bess_soc": "infra/totals/bess_soc",
    "bess_state": "infra/bess/state",
    "chp_state": "infra/chp/state",
    "chp_kw": "infra/totals/chp_kw",
    "chp_hours": "infra/chp/hours",
    "ats_pos": "infra/ats/position",
    "src1_ok": "infra/ats/src1_ok",
    "s1_p": "energy/sections/S1/p_kw",
    "s2_p": "energy/sections/S2/p_kw",
    "pfc1_fault": "energy/cells/PFC-1/fault_step",
    "pfc2_fault": "energy/cells/PFC-2/fault_step",
    "fire_state": "fire/panel/state",
}
# Додаткові входи лише для Odoo-перевірок (у конфіг API-24 не публікуються)
ODOO_INPUTS = {"co2_ppm": "ventilation/totals/co2_ppm", "bess_reserve": "energy_control/bess/reserve_pct"}
# Які входи потрібні виду (для `data_fresh`): логічні імена
KIND_INPUTS = {
    "qs_close": ("remote", "ats_pos", "src1_ok", "ats_lock", "s1_p", "s2_p"),
    "qs_open": ("remote",),
    "bess_charge": ("remote", "ats_pos", "src1_ok", "bess_state", "bess_soc"),
    "bess_discharge": ("remote", "bess_state", "bess_soc"),
    "chp_start": ("remote", "ats_pos", "src1_ok", "chp_state", "chp_gas", "chp_permit"),
    "air_setpoint": ("remote", "air_sp", "air_min"),
}

# Дистанційне перемикання (D-46, Q-27): види з `remote_gated`
REMOTE_GATED = ("qs_close", "qs_open", "chp_start", "bess_discharge", "genset_test")

# Сумісність з рекомендаціями W3 (R-55 п.6): `params.intent` → (вид, параметри) або None (не підтримується)
ADVICE_INTENT_ALIASES = {
    "vent_night_mode": ("scenario_toggle", {"scenario": "night", "enabled": True}),
    "pv_self_consumption": ("scenario_toggle", {"scenario": "self", "enabled": True}),
    "air_pressure_setpoint": ("air_setpoint", {}),
    "heat_schedule_shift": None,
}
# Вузли, які не скидаються ніколи (поряд із критичними без активного рядка пріоритету)
NEVER_SHED_CODES = ("EF-ELEC", "EF-CHG", "DUST-1")
NEVER_TEXT = [
    "аспірація під час роботи верстатів",
    "ІТ і зв'язок",
    "охорона",
    "пожежна автоматика",
    "аварійне освітлення",
]


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def resolve_bounds(schema, ctx=None):
    """Підставити іменовані межі (`"max": "bess_max_kw"`) із контексту; повертає копію схеми."""
    ctx = ctx or {}
    out = []
    for spec in schema:
        spec = dict(spec)
        for key in ("min", "max"):
            if isinstance(spec.get(key), str):
                spec[key] = ctx.get(spec[key])
        out.append(spec)
    return out


def fmt(value, decimals=None):
    """Число з українською комою; ціле без знаків; `None` → «—»."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "так" if value else "ні"
    if isinstance(value, (int, float)):
        if decimals is not None:
            return ("%.*f" % (decimals, value)).replace(".", ",")
        if float(value).is_integer():
            return str(int(value))
        return ("%.1f" % value).replace(".", ",")
    return str(value)


def _fmt_range(spec):
    unit = (" " + spec["unit"]) if spec.get("unit") else ""
    return "%s…%s%s" % (fmt(spec.get("min")), fmt(spec.get("max")), unit)


def validate_value(spec, value):
    """Одне значення за специфікацією → (нормалізоване, текст помилки або None)."""
    t = spec["type"]
    if t in ("float", "int"):
        if not _is_num(value):
            return None, "має бути число"
        if t == "int":
            if isinstance(value, float) and not value.is_integer():
                return None, "має бути ціле число"
            value = int(value)
        else:
            value = float(value)
        lo, hi = spec.get("min"), spec.get("max")
        if (lo is not None and value < lo) or (hi is not None and value > hi):
            return None, "поза межами %s" % _fmt_range(spec)
        return value, None
    if t == "bool":
        return (value, None) if isinstance(value, bool) else (None, "має бути так/ні")
    if t == "time":
        return (value, None) if isinstance(value, str) and TIME_RE.match(value) else (None, "має бути час ГГ:ХХ")
    if t == "enum":
        return (value, None) if value in (spec.get("choices") or ()) else (None, "недопустиме значення")
    if t == "days":
        ok = (
            isinstance(value, list)
            and value
            and all(isinstance(d, int) and not isinstance(d, bool) and spec["min"] <= d <= spec["max"] for d in value)
        )
        return (sorted(set(value)), None) if ok else (None, "дні мають бути числами %s…%s" % (spec["min"], spec["max"]))
    if t == "list_int":
        ok = isinstance(value, list) and all(isinstance(d, int) and not isinstance(d, bool) for d in value)
        return (value, None) if ok else (None, "має бути список цілих")
    return None, "невідомий тип"


def validate(schema, params, ctx=None, fill_defaults=False):
    """→ (чисті параметри, [(ключ, помилка)]). Невідомі ключі — помилка. `fill_defaults` додає відсутні значення."""
    specs = {s["name"]: s for s in resolve_bounds(schema, ctx)}
    errors, clean = [], {}
    if not isinstance(params, dict):
        return {}, [("params", "має бути об'єкт")]
    for key, value in params.items():
        spec = specs.get(key)
        if spec is None:
            errors.append((key, "невідомий параметр"))
            continue
        val, err = validate_value(spec, value)
        if err:
            errors.append((key, err))
        else:
            clean[key] = val
    if fill_defaults:
        for name, spec in specs.items():
            if name not in clean and spec.get("default") is not None:
                clean[name] = spec["default"]
    return clean, errors


class _SafeDict(dict):
    def __missing__(self, key):
        return "—"


BAR_KEYS = ("setpoint_bar", "current_bar", "bar", "min_bar")


def render_template(template, values):
    """`{key}` → значення; відсутнє → «—»; числа з комою; бари — з одним знаком після коми."""
    if not template:
        return ""
    vals = _SafeDict()
    for key, value in (values or {}).items():
        vals[key] = fmt(value, 1 if key in BAR_KEYS and _is_num(value) else None)
    try:
        return template.format_map(vals)
    except (ValueError, IndexError, KeyError):
        return template


def until_seconds(until, now_local):
    """Секунди від `now_local` (aware, Київ) до `until` «HH:MM» сьогодні; ≤ 0 → None (час уже минув)."""
    hh, mm = (int(x) for x in until.split(":"))
    target = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    sec = (target - now_local).total_seconds()
    return int(sec) if sec > 0 else None
