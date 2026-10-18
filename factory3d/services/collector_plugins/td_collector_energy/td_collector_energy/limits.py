"""Константи-межі коду збирача (R-41 п.6, R-44 п.6, R-60): конфіг Odoo може лише звужувати їх."""

from __future__ import annotations

# --- R-44 п.6 / R-41 п.6: значення конфігу застосовуються як min(код, конфіг) (для нижніх меж — max) ---
BESS_KW_MAX = 200.0
PV_LIMIT_MIN_PCT = 10.0
AIR_BAR_MIN, AIR_BAR_MAX = 5.0, 8.5
SOC_FLOOR_PCT = 10.0
MIN_WRITE_INTERVAL_S = 2.0
MAX_WRITES_PER_MIN = 120
TICK_S_MIN, TICK_S_MAX = 1.0, 10.0
CONFIG_POLL_S_MIN, CONFIG_POLL_S_MAX = 5.0, 60.0

# межі параметрів блокувань: (верхня межа «≤» | нижня «≥»)
INTERLOCK_MAX = {
    ("qs_current_ok", "max_ratio"): 0.9,
    ("bess_temp_ok", "max_c"): 45.0,
    ("data_fresh", "max_age_s"): 120.0,
}
INTERLOCK_MIN = {("chp_gas_pressure", "min_bar"): 1.0}

# --- R-60: що не керується (дозволено писати лише у сигнали з API-24, і ніколи — у ці префікси) ---
DENY_PREFIXES = (
    "fire/",
    "evacuation/",
    "sprinklers/",
    "smoke/",
    "lightning/",
    "access/",
    "workcenters/",
    "security/",
    "yard/",
)
# вузли, які не скидаються ніколи (поряд із `never_shed` конфігу); R-51 п.1
NEVER_SHED_CODES = ("EF-ELEC", "EF-CHG", "DUST-1")

# --- R-44 / R-52: тривалості ---
HOLD_AFTER_RATE_S = 300.0  # `hold` після перевищення частоти записів
CONFIG_CACHE_MAX_AGE_S = 7 * 86400.0
STATE_MAX_AGE_S = 7 * 86400.0
INTENT_KEEP_S = 24 * 3600.0
INTENT_KEEP_N = 500
MAX_QUEUE = 4
BESS_WATCHDOG_S = 30  # valid_s автоматики
SHED_WATCHDOG_S = 60
SHED_REFRESH_S = 20.0
BESS_REFRESH_S = 10.0
MAX_BESS_VALID_S = 43200
