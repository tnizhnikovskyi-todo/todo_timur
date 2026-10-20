"""R-08: чиста частина потоку команд — види, параметри, межі, тексти діалогу й журналу (без доступу до БД)."""

from odoo.exceptions import UserError, ValidationError
from odoo.addons.td_telemetry.tools.titles import fmt_num

STATES = [
    ("prepared", "Підготовлено"),
    ("awaiting_second", "Очікує другого підтвердження"),
    ("queued", "У черзі"),
    ("sent", "Передано збирачу"),
    ("executing", "Виконується"),
    ("done", "Виконано"),
    ("failed", "Не виконано"),
    ("blocked", "Заблоковано"),
    ("expired", "Прострочено"),
    ("cancelled", "Скасовано"),
]
STATE_LABELS = dict(STATES)
RANK = {"prepared": 0, "awaiting_second": 1, "queued": 2, "sent": 3, "executing": 4}
FINAL = ("done", "failed", "blocked", "expired", "cancelled")
ACTIVE = ("queued", "sent", "executing")  # одна активна команда на агрегат
JOURNAL_STATES = ("awaiting_second", "queued", "sent", "executing", "done", "failed", "blocked", "expired")

MODES = {"heat": 0, "el": 1, "peak": 2, "manual": 3}
MODE_LABELS = {
    "heat": "За тепловим графіком",
    "el": "За електричним графіком",
    "peak": "Зрізання піку",
    "manual": "Ручний",
}
HEAT_DIRS = {"auto": 0, "boiler": 1, "cooler": 2}
HEAT_LABELS = {"auto": "Авто (котельня, надлишок на градирню)", "boiler": "Котельня", "cooler": "Градирня"}
BYPASS_MODES = {"auto": 0, "ht": 1, "bypass": 2}
BYPASS_LABELS = {"auto": "Авто (на ТО при роботі)", "ht": "На ТО вихлопних газів", "bypass": "В обхід ТО"}

KINDS = {  # вид → клас (R-08 п.1), підпис, сигнал цілі (без `chp/`), значення (для видів без параметрів)
    "start": {"cls": "B", "label": "Пуск", "signal": "ctl/cmd", "value": 1},
    "stop": {"cls": "B", "label": "Стоп", "signal": "ctl/cmd", "value": 2},
    "estop": {"cls": "A", "label": "Аварійний стоп", "signal": "ctl/cmd", "value": 3},
    "reset": {"cls": "A", "label": "Скидання аварії", "signal": "ctl/cmd", "value": 4},
    "set_mode": {"cls": "A", "label": "Режим роботи", "signal": "ctl/mode"},
    "set_setpoint": {"cls": "A", "label": "Уставка потужності", "signal": "ctl/sp_pct"},
    "set_cos": {"cls": "A", "label": "Уставка cos φ", "signal": "ctl/cos_set"},
    "set_heat_dir": {"cls": "A", "label": "Напрямок тепла", "signal": "ctl/heat_dir"},
    "set_bypass": {"cls": "A", "label": "Заслінка вихлопу", "signal": "ctl/bypass_mode"},
}
PARAM_KEYS = {
    "set_mode": ("mode",),
    "set_setpoint": ("sp_pct",),
    "set_cos": ("cos",),
    "set_heat_dir": ("dir",),
    "set_bypass": ("mode",),
}
SETPOINT_RANGE = (50.0, 100.0)
COS_RANGE = (0.90, 1.00)


def kind_info(kind):
    info = KINDS.get(kind)
    if not info:
        raise UserError(f"Невідома команда: {kind}.")
    return info


def short_name(unit):
    """«КГУ-1 · TEDOM · 800 кВт» → «КГУ-1»."""
    return (unit.name or unit.code or "КГУ").split("·")[0].strip()


def _enum(kind, params, key, mapping):
    name = KINDS[kind]["label"]
    val = params.get(key)
    if val is None:
        raise UserError(f"Команда «{name}»: не вказано параметр {key}.")
    if val not in mapping:
        raise UserError(f"Команда «{name}»: недопустиме значення {val}; дозволено: {', '.join(mapping)}.")
    return val


def _number(kind, params, key, label, lo, hi):
    name = KINDS[kind]["label"]
    val = params.get(key)
    if val is None or isinstance(val, bool):
        raise UserError(f"Команда «{name}»: не вказано параметр {key}.")
    try:
        val = float(val)
    except (TypeError, ValueError) as e:
        raise UserError(f"Команда «{name}»: параметр {key} має бути числом.") from e
    if not lo - 1e-9 <= val <= hi + 1e-9:
        raise ValidationError(f"Команда {name}: параметр {label} поза межами {fmt_num(lo, 2)}…{fmt_num(hi, 2)}.")
    return val


def normalize(kind, params):
    """Перевірити й нормалізувати параметри виду. Невідомі `kind`/ключі → UserError, поза межами → ValidationError."""
    kind_info(kind)
    if params is not None and not isinstance(params, dict):
        raise UserError("Параметри команди мають бути об'єктом.")
    params = dict(params or {})
    allowed = PARAM_KEYS.get(kind, ())
    for key in params:
        if key not in allowed:
            raise UserError(f"Команда «{KINDS[kind]['label']}»: невідомий параметр {key}.")
    if kind == "set_mode":
        return {"mode": _enum(kind, params, "mode", MODES)}
    if kind == "set_heat_dir":
        return {"dir": _enum(kind, params, "dir", HEAT_DIRS)}
    if kind == "set_bypass":
        return {"mode": _enum(kind, params, "mode", BYPASS_MODES)}
    if kind == "set_setpoint":
        return {"sp_pct": round(_number(kind, params, "sp_pct", "уставка P, %", *SETPOINT_RANGE), 1)}
    if kind == "set_cos":
        val = _number(kind, params, "cos", "cos φ", *COS_RANGE)
        if abs(val * 100 - round(val * 100)) > 1e-6:
            raise ValidationError(f"Команда {KINDS[kind]['label']}: cos φ задається з кроком 0,01.")
        return {"cos": round(val, 2)}
    return {}


def target_value(kind, params):
    """Інженерне значення, яке йде в `td.command.value` (регістр = round(інж / scale) — на колекторі)."""
    info = KINDS[kind]
    if "value" in info:
        return float(info["value"])
    if kind == "set_mode":
        return float(MODES[params["mode"]])
    if kind == "set_setpoint":
        return float(params["sp_pct"])
    if kind == "set_cos":
        return float(params["cos"])
    if kind == "set_heat_dir":
        return float(HEAT_DIRS[params["dir"]])
    return float(BYPASS_MODES[params["mode"]])


def render(kind, params, unit):
    """Тексти діалогу й журналу: `{label, title, text, sub}`."""
    info = KINDS[kind]
    name = short_name(unit)
    title = f"{info['label']} {name}"
    sub = ""
    if kind == "start":
        text = (
            f"Пуск {name} за 9 кроків: вентиляція, підігрів, змащення, перевірка клапанів, прокрутка, запалювання, "
            "холостий хід, синхронізація, набір навантаження."
        )
        sub = "Команда класу Б: два підтвердження — енергетика й головного енергетика."
    elif kind == "stop":
        text = f"{name} розвантажиться й охолоджуватиметься 60 с."
        sub = "Команда класу Б: два підтвердження — енергетика й головного енергетика."
    elif kind == "estop":
        text = f"Негайна зупинка {name} без охолодження."
        sub = "Клас А: одне підтвердження."
    elif kind == "reset":
        text = f"Аварію {name} буде скинуто, агрегат перейде в «Резерв»."
        sub = "Клас А: одне підтвердження."
    elif kind == "set_mode":
        text = f"Режим роботи: {MODE_LABELS[params['mode']]}."
    elif kind == "set_setpoint":
        text = f"Уставка навантаження: {fmt_num(params['sp_pct'], 1)} % (діє лише в режимі «Ручний»)."
    elif kind == "set_cos":
        text = f"Уставка cos φ: {fmt_num(params['cos'], 2)}."
    elif kind == "set_heat_dir":
        text = f"Напрямок тепла: {HEAT_LABELS[params['dir']]}."
    else:
        text = f"Заслінка вихлопу: {BYPASS_LABELS[params['mode']]}."
    if kind.startswith("set_"):
        sub = "Клас А: значення зміниться лише після підтвердження."
    return {"label": f"{info['label']}", "title": title, "text": text, "sub": sub}


def journal_text(label, state, prepared_by=None, second_by=None):
    """R-12: «Команда «{вид}»: {стан}» (+ « · 1/2 {prepared_by}, 2/2 {second_by}»)."""
    text = f"Команда «{label}»: {STATE_LABELS.get(state, state)}"
    if second_by:
        text += f" · 1/2 {prepared_by or '—'}, 2/2 {second_by}"
    return text
