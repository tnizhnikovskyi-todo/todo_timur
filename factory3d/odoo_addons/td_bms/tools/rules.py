"""R-19…R-24: чисті функції оцінки умов (без ORM). Час — UTC naive; затримки — у хвилинах."""

from datetime import timedelta

LIGHT_NORMAL = "норма"
OFF_HOURS = "поза робочим часом"
LIGHT_OFF = "вимкнено в робочий час"
LIGHT_LOW = "нижче норми"
NO_DATA = "немає даних"
NO_MAINS = "немає мережі (живлення від резерву)"
UNIT_OFF = "не працює в робочий час"
COLD = "холодно в зоні"
FIRE = "зупинено пожежною сигналізацією"
DEFICIT = "дефіцит тепла"

LIVE_STATUSES = ("ok", "warn", "alarm")
NOT_RUNNING_MODES = ("ST", "Off")


def is_live(status):
    return status in LIVE_STATUSES


def rule_of(code, text=None):
    """R-22 п. 1: правило журналу/заявки за кодом сигналу й (для `check`) текстом стану."""
    code = code or ""
    parts = code.split("/")
    tail = parts[-1]
    if code.startswith("ventilation/units/"):
        unit = parts[2] if len(parts) > 3 else ""
        if tail == "filter_dp_pa":
            return "filter_supply"
        if tail == "filter_extract_dp_pa":
            return "filter_extract"
        if tail == "room_pressure_pa":
            return "pressure"
        if tail == "state":
            return "charging_vent" if unit == "EF-CHG" else "unit_fault"
        if tail == "indoor_c" and unit == "EF-ELEC":
            return "overheat"
        if tail == "check":
            return {UNIT_OFF: "unit_off", COLD: "cold"}.get(text or "", "other")
    elif code.startswith("lighting/groups/"):
        if tail == "faults":
            return "light_fault"
        if tail == "check":
            return {LIGHT_OFF: "light_off", LIGHT_LOW: "light_low"}.get(text or "", "other")
    elif code == "equipment/BOILER/state":
        return "boiler_fault"
    elif code == "ventilation/heat_plant/check":
        return "heat_deficit"
    return "other"


def object_of(code):
    """`(object_kind, object_code)` за кодом сигналу; `(False, False)` — не об'єкт модуля."""
    parts = (code or "").split("/")
    if code.startswith("lighting/groups/") and len(parts) > 3:
        return "group", parts[2]
    if code.startswith("lighting/panels/") and len(parts) > 3:
        return "panel", parts[2]
    if code.startswith("ventilation/units/") and len(parts) > 3:
        return "unit", parts[2]
    if code.startswith("equipment/BOILER/") or code == "ventilation/heat_plant/check":
        return "boiler", "BOILER"
    return False, False


def elapsed(now, since, start, delay_min):
    """`now − max(since, start) ≥ delay`; без `since` — ні."""
    if not since:
        return False
    return now - max(since, start) >= timedelta(minutes=delay_min)


def light_check(
    *,
    live,
    level_pct,
    e_now_raw,
    e_norm,
    tol,
    interval,
    mains_lost,
    off_since,
    low_since,
    delay_min,
    now,
    check_off=True,
    check_norm=True,
):
    """R-19. `tol` — частка (0,05)."""
    if not live:
        return NO_DATA
    if interval is None:
        return OFF_HOURS
    if mains_lost:
        return NO_MAINS
    start = interval[0]
    if check_off and level_pct < 1 and elapsed(now, off_since, start, delay_min):
        return LIGHT_OFF
    if check_norm and level_pct >= 1 and e_now_raw < e_norm * (1 - tol) and elapsed(now, low_since, start, delay_min):
        return LIGHT_LOW
    return LIGHT_NORMAL


def light_since(*, live, level_pct, e_calc_raw, e_norm, tol, off_since, low_since, ts, suppressed=False):
    """R-20: нові `(off_since, low_since)` для групи за рівнем (`ts` — час показання або `now`)."""
    if suppressed:
        return False, False
    if not live:
        return off_since or False, low_since or False
    if level_pct < 1:
        return off_since or ts, False
    low = e_calc_raw * level_pct / 100.0 < e_norm * (1 - tol)
    return False, (low_since or ts) if low else False


def not_running(state_text, mode_text):
    """R-20: `stopped` або режим ST/Off (не `fault`/`frost`)."""
    return state_text == "stopped" or (mode_text in NOT_RUNNING_MODES and state_text not in ("fault", "frost"))


def unit_since(
    *, running_off, indoor, min_work, min_off, off_since, cold_since, cold_off_since, ts_off, ts_cold, suppressed=False
):
    """R-20: нові `(off_since, cold_since, cold_off_since)` установки; `indoor=None` — немає живого значення."""
    off = False if suppressed or not running_off else (off_since or ts_off)
    cold = (cold_since or ts_cold) if indoor is not None and indoor < min_work else False
    cold_off = (cold_off_since or ts_cold) if indoor is not None and indoor < min_off else False
    return off, cold, cold_off


def unit_check(
    *,
    live,
    mains_lost,
    fire_active,
    running_off,
    interval,
    indoor,
    min_work,
    min_off,
    required_in_work,
    off_since,
    cold_since,
    cold_off_since,
    hvac_delay_min,
    cold_delay_min,
    now,
):
    """R-23 (лише RV/AHU). `indoor=None` — немає живого значення."""
    if not live:
        return NO_DATA
    if mains_lost:
        return NO_MAINS
    if fire_active and running_off:
        return FIRE
    if interval is None:
        if (
            indoor is not None
            and indoor < min_off
            and cold_off_since
            and now - cold_off_since >= timedelta(minutes=cold_delay_min)
        ):
            return COLD
        return OFF_HOURS
    start = interval[0]
    if required_in_work and running_off and elapsed(now, off_since, start, hvac_delay_min):
        return UNIT_OFF
    if indoor is not None and indoor < min_work and elapsed(now, cold_since, start, cold_delay_min):
        return COLD
    return LIGHT_NORMAL


def heat_check(*, live, deficit, threshold, deficit_since, delay_min, now):
    """R-24: `(text, new_deficit_since)`."""
    if not live:
        return NO_DATA, deficit_since or False
    if deficit > threshold:
        since = deficit_since or now
    else:
        since = False
    if since and now - since >= timedelta(minutes=delay_min):
        return DEFICIT, since
    return LIGHT_NORMAL, since


def worst(old, new, rel):
    """R-22 п. 2: гірше з двох значень (`rel` — «до» верхній поріг, «від» нижній)."""
    if old is None or old is False:
        return new
    return max(old, new) if rel == "до" else min(old, new) if rel == "від" else new
