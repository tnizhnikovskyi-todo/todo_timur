"""R-10…R-13: номінали, підписи режимів, стан і формули макета для установок вентиляції (без ORM)."""

MODE_LABELS = {
    "VE": "Приплив і витяжка",
    "VEL": "Знижена вентиляція",
    "AQ": "Рекуперація",
    "REC": "Рециркуляція",
    "EA": "Витяжка",
    "SA": "Приплив",
    "ST": "Очікування",
    "Off": "Вимкнено",
}
DESIGN_ONLY_LABELS = {"thermostat": "За термостатом", "charging": "Під час заряджання"}
AHU_VE_LABEL = "Приплив під витяжку фарбувальних камер"
OUTDOOR_C = 9.0
HEAT_FACTORS = {"AQ": 0.3, "VE": 0.8, "VEL": 0.8, "REC": 0.8, "EA": 0.8, "SA": 0.8}


def nominals(kind, fan_count, get_num):
    """R-10 п. 1. `get_num(key)` — значення паспорта або None. Повертає airflow_nom/heat_nom_kw/p_inst_kw[/required_m3h]."""
    fan_count = fan_count or 1
    air, heat, power = get_num("airflow_m3h"), get_num("heat_kw"), get_num("power_kw")
    if kind == "roofvent":
        res = {"airflow_nom": air or 8000.0, "heat_nom_kw": heat or 60.0, "p_inst_kw": power or 4.0}
    elif kind == "ahu":
        res = {"airflow_nom": air or 20000.0, "heat_nom_kw": 0.0, "p_inst_kw": power or 15.0}
    elif kind == "fan":
        res = {"airflow_nom": (air or 6000.0) * fan_count, "heat_nom_kw": 0.0, "p_inst_kw": (power or 0.6) * fan_count}
    else:  # exfan
        res = {"airflow_nom": air or 644.0, "heat_nom_kw": 0.0, "p_inst_kw": power or 0.18,
               "required_m3h": get_num("required_m3h") or 160.0}
    return res


def share(airflow, airflow_nom):
    """R-10 п. 2: частка номінальної витрати."""
    return airflow / airflow_nom if airflow_nom else 0.0


def mode_label(kind, mode_code, mode_design, running, fan_count=1, required_m3h=0.0):
    """R-10 п. 3: підпис режиму."""
    if kind == "fan":
        n = fan_count or 1
        return "Увімкнено %d з %d (термостат)" % (n, n) if running else "Чекає (термостат)"
    if kind == "exfan":
        return "Безперервно під час заряджання, не менше %d м³/год" % round(required_m3h) if running else "Зупинено"
    code = mode_code or mode_design
    if kind == "ahu" and code == "VE":
        return AHU_VE_LABEL
    return MODE_LABELS.get(code) or DESIGN_ONLY_LABELS.get(code) or False


def unit_state(kind, state_text, mode_code=None):
    """R-11: стан установки за текстом сигналу стану; None — немає живого стану."""
    if not state_text:
        return None
    if kind in ("roofvent", "ahu"):
        if state_text in ("fault", "frost"):
            return "fault"
        if state_text == "running":
            return "on"
        if state_text == "stopped":
            return "standby" if mode_code == "ST" else "off"
        return None
    if kind == "fan":
        return {"running": "on", "stopped": "standby", "fault": "fault"}.get(state_text)
    return {"running": "on", "stopped_charging": "fault", "stopped": "standby"}.get(state_text)


def fallback_heat(kind, k, mode, t_out, t_set=18.0, heat_nom=116.8, p_inst=8.6, airflow=0.0, t_supply=21.0):
    """R-13: {heat (без округлення), valve (0…1 або None), p_now}. Для RV — `k`, для AHU-1 — `airflow`."""
    if kind == "roofvent":
        f = HEAT_FACTORS.get(mode, 0.0)
        heat = heat_nom * k * (t_set - t_out) / (t_set + 15.0) * f if f else 0.0
        valve = round(min(1.0, heat / heat_nom), 2) if heat_nom else 0.0
        return {"heat": heat, "valve": valve, "p_now": round(p_inst * k**3 + 0.1, 2)}
    if kind == "ahu":
        return {"heat": airflow * 1.2 / 3600.0 * (t_supply - t_out), "valve": None,
                "p_now": round(p_inst * k**3 + 0.1, 2)}
    return {"heat": 0.0, "valve": None, "p_now": fallback_power(kind, k, p_inst, False)}


def fallback_power(kind, k, p_inst, running):
    """R-13: потужність зараз. Вентилятори — p_inst або 0; RV/AHU — p_inst·k³ + 0,1."""
    if kind in ("fan", "exfan"):
        return p_inst if running else 0.0
    return round(p_inst * k**3 + 0.1, 2)


def round_payload(value):
    """telemetry R-12: |v| < 20 → 2 знаки, інакше 1."""
    if value is None:
        return None
    return round(value, 2 if abs(value) < 20 else 1)
