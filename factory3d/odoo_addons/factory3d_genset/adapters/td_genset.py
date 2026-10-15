"""Адаптер td_genset: ADP-01…ADP-10 (SPEC §2.0.1). Єдине місце звірки імен з td_genset.

Тіла функцій — заглушки (W2). Константа ``None`` = ще не звірено.
"""

# ADP-01
GENSET_MODEL = "td.genset"  # ЗВІРИТИ з td_genset (ADP-01, Q-10…Q-19) — збігається з models/genset.py
READING_MODEL = "td.genset.reading"  # ЗВІРИТИ з td_genset (ADP-03)
EVENT_MODEL = "td.genset.event"  # ЗВІРИТИ з td_genset (ADP-04)

# ADP-03: поля знімка на td.genset (ключ знімка -> поле)
FIELD_TS = "last_reading_at"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_ONLINE = "relay_online"  # ЗВІРИТИ з td_genset (ADP-03): свіжість за правилом td_genset
FIELD_STATE_RAW = "genset_status"  # ЗВІРИТИ з td_genset (ADP-03, ADP-10)
FIELD_MODE_RAW = "controller_mode"  # ЗВІРИТИ з td_genset (ADP-03, ADP-10)
FIELD_MAINS_OK = "mains_ok"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_BREAKER_RAW = "feed_source"  # ЗВІРИТИ з td_genset (ADP-03, ADP-10)
FIELD_P_KW = "active_power"  # ЗВІРИТИ з td_genset (ADP-03): сумарна чи по фазах
FIELD_U_V = None  # ЗВІРИТИ з td_genset (ADP-03): середня лінійна = (gen_uab+gen_ubc+gen_uca)/3
FIELD_F_HZ = "gen_freq"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_I_A = None  # ЗВІРИТИ з td_genset (ADP-03): max(current_a, current_b, current_c)
FIELD_PF = "power_factor"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_KWH = "energy_kwh"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_FUEL_PCT = "fuel_level"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_FUEL_L = "fuel_liters"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_HOURS = "run_hours_total"  # ЗВІРИТИ з td_genset (ADP-03, ADP-05)
FIELD_STARTS = "start_count"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_COOLANT_C = "water_temp"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_OIL_BAR = "oil_pressure"  # ЗВІРИТИ з td_genset (ADP-03): одиниці (кПа → /100)
FIELD_BATT_V = "battery_v"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_CHARGER_V = "dplus_v"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_RPM = "speed"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_MAINS_U_V = None  # ЗВІРИТИ з td_genset (ADP-03): середня з mains_uab/ubc/uca
FIELD_MAINS_F_HZ = "mains_freq"  # ЗВІРИТИ з td_genset (ADP-03)
FIELD_ALARMS_MODEL = "td.genset.alarm"  # ЗВІРИТИ з td_genset (ADP-03): code/name/severity/since
FIELD_EQUIPMENT = "equipment_id"  # ЗВІРИТИ з td_genset (ADP-02)

# ADP-05
FIELD_SERVICE_INTERVAL_H = "maint_interval_hours"  # ЗВІРИТИ з td_genset (ADP-05)
FIELD_NEXT_SERVICE_H = None  # ЗВІРИТИ з td_genset (ADP-05)
FIELD_LAST_SERVICE_H = None  # ЗВІРИТИ з td_genset (ADP-05)
FIELD_LAST_SERVICE_DATE = None  # ЗВІРИТИ з td_genset (ADP-05)
FIELD_SERVICE_DUE = None  # ЗВІРИТИ з td_genset (ADP-05)

# ADP-06 / ADP-07
SCHEDULE_MODEL = "td.genset.schedule"  # ЗВІРИТИ з td_genset (ADP-06)
LAST_TEST_MODEL = None  # ЗВІРИТИ з td_genset (ADP-07)

# ADP-09
FIELD_FUEL_RATE_LPH = None  # ЗВІРИТИ з td_genset (ADP-09, CR-05)

# ADP-10: сирі значення td_genset (нижній регістр) -> коди R-03
STATE_MAP: dict = {}  # ЗВІРИТИ з td_genset (ADP-10)
MODE_MAP: dict = {}  # ЗВІРИТИ з td_genset (ADP-10)
BREAKER_MAP: dict = {}  # ЗВІРИТИ з td_genset (ADP-10)


def generators(env):
    """ADP-02: активні генератори, порядок за id."""
    raise NotImplementedError("звірити ADP-02")


def snapshot(gen) -> dict:
    """ADP-03: останній знімок показань."""
    raise NotImplementedError("звірити ADP-03")


def events_since(gen, since=None, limit: int = 200) -> list:
    """ADP-04: події журналу td_genset новіші за since."""
    raise NotImplementedError("звірити ADP-04")


def service_info(gen) -> dict:
    """ADP-05: ТО за мотогодинами."""
    raise NotImplementedError("звірити ADP-05")


def schedule_info(gen) -> dict:
    """ADP-06: розклад."""
    raise NotImplementedError("звірити ADP-06")


def last_test(gen):
    """ADP-07: останній тестовий пуск."""
    raise NotImplementedError("звірити ADP-07")


def open_action(gen) -> dict:
    """ADP-08: act_window на запис генератора td_genset."""
    raise NotImplementedError("звірити ADP-08")


def set_fuel_rate(gen, lph: float) -> bool:
    """ADP-09: записати еквівалентну витрату (лише з кнопки профілю)."""
    raise NotImplementedError("звірити ADP-09")
