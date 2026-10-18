"""Золоті випадки R-41 п.5 — єдина таблиця для збирача (AC-241); дзеркало `td_energy_control/tests/test_interlocks.py`.

Рядок: (перевірка, значення входів, тексти входів, `params`, `extra`, очікуваний стан, фрагмент `detail` або `None`).
`—` у SPEC = вхід відсутній (`None`).
"""

OK, FAIL, UNK = "ok", "fail", "unknown"
QS = {"rating_a": 1600, "max_ratio": 0.8, "cos_phi": 0.95}
RESERVE = {"capacity_kwh": 387}
AIR = {"margin_bar": 0.2, "max_bar": 8.5}

GOLDEN = [
    ("controller_remote", {"remote": 1}, {}, {}, {}, OK, None),
    ("controller_remote", {"remote": 0}, {}, {}, {}, FAIL, None),
    ("controller_remote", {"remote": None}, {}, {}, {}, UNK, None),
    ("no_island", {"ats_pos": 2, "src1_ok": 1}, {}, {}, {}, OK, None),
    ("no_island", {"ats_pos": 3, "src1_ok": 1}, {}, {}, {}, FAIL, None),
    ("no_island", {"ats_pos": 2, "src1_ok": 0}, {}, {}, {}, FAIL, None),
    ("no_island", {"ats_pos": 2, "src1_ok": None}, {}, {}, {}, UNK, None),
    ("ats_parallel_lock", {"ats_lock": 1}, {}, {}, {}, OK, None),
    ("ats_parallel_lock", {"ats_lock": 0}, {}, {}, {}, FAIL, "lock=0"),
    ("ats_parallel_lock", {"ats_lock": None}, {}, {}, {}, UNK, None),
    ("qs_current_ok", {"s1_p": 150, "s2_p": 100}, {}, QS, {}, OK, "≈ 40 А з 1600 А"),  # 25/(√3·0,4·0,95) ≈ 38 А → 40
    ("qs_current_ok", {"s1_p": 1700, "s2_p": 0}, {}, QS, {}, FAIL, None),  # ≈ 1292 А > 1280 А
    ("qs_current_ok", {}, {"qs_state": "closed"}, QS, {}, OK, "QS уже замкнений"),
    ("qs_current_ok", {"s1_p": None, "s2_p": 0}, {}, QS, {}, UNK, None),
    ("bess_ok", {"bess_state": 1}, {}, {}, {}, OK, None),
    ("bess_ok", {"bess_state": 2}, {}, {}, {}, OK, None),
    ("bess_ok", {"bess_state": 4}, {}, {}, {}, OK, None),
    ("bess_ok", {"bess_state": 0}, {}, {}, {}, FAIL, None),
    ("bess_ok", {"bess_state": 3}, {}, {}, {}, FAIL, None),
    ("bess_ok", {"bess_state": None}, {}, {}, {}, UNK, None),
    ("bess_soc_lt_limit", {"bess_soc": 82}, {}, {}, {"soc_limit_pct": 95}, OK, "Заряд 82 % < 95 %"),
    ("bess_soc_lt_limit", {"bess_soc": 95}, {}, {}, {"soc_limit_pct": 95}, FAIL, None),
    (
        "bess_reserve_kept",
        {"bess_soc": 82, "bess_reserve": 30},
        {},
        RESERVE,
        {"power_kw": 100, "duration_min": 60},
        OK,
        "56.2",
    ),  # 82 − 25,84 = 56,2
    (
        "bess_reserve_kept",
        {"bess_soc": 50, "bess_reserve": 30},
        {},
        RESERVE,
        {"power_kw": 100, "duration_min": 60},
        FAIL,
        "24.2",
    ),
    ("bess_temp_ok", {"bess_temp": 24}, {}, {"max_c": 40}, {}, OK, None),
    ("bess_temp_ok", {"bess_temp": 41}, {}, {"max_c": 40}, {}, FAIL, None),
    ("bess_temp_ok", {"bess_temp": None}, {}, {"max_c": 40}, {}, UNK, None),
    ("chp_ready", {"chp_state": 0}, {}, {}, {}, OK, None),
    ("chp_ready", {"chp_state": 1}, {}, {}, {}, FAIL, None),
    ("chp_ready", {"chp_state": 2}, {}, {}, {}, FAIL, None),
    ("chp_ready", {"chp_state": 3}, {}, {}, {}, FAIL, None),
    ("chp_gas_pressure", {"chp_gas": 2.10}, {}, {"min_bar": 1.5}, {}, OK, None),
    ("chp_gas_pressure", {"chp_gas": 0.80}, {}, {"min_bar": 1.5}, {}, FAIL, None),
    ("chp_permit", {"chp_permit": 1}, {}, {}, {}, OK, None),
    ("chp_permit", {"chp_permit": 0}, {}, {}, {}, FAIL, None),
    ("chp_permit", {"chp_permit": None}, {}, {}, {}, UNK, None),
    ("chp_min_run", {"chp_state": 0}, {}, {"min_run_h": 2}, {}, OK, None),
    ("chp_min_run", {"chp_state": 2, "chp_hours": 1.2}, {}, {"min_run_h": 2}, {}, FAIL, None),
    ("chp_min_run", {"chp_state": 2, "chp_hours": 2.3}, {}, {"min_run_h": 2}, {}, OK, None),
    ("no_fire_alarm", {}, {}, {}, {"absent": True}, OK, "не підключено"),
    ("no_fire_alarm", {"fire_state": 1}, {"fire_state": "alarm"}, {}, {}, FAIL, None),
    ("no_fire_alarm", {"fire_state": 0}, {"fire_state": "ok"}, {}, {}, OK, None),
    ("no_fire_alarm", {"fire_state": None}, {}, {}, {}, UNK, None),  # несвіже
    ("air_setpoint_min", {"air_min": 6.2}, {}, AIR, {"setpoint_bar": 6.5}, OK, None),
    ("air_setpoint_min", {"air_min": 6.2}, {}, AIR, {"setpoint_bar": 6.3}, FAIL, None),
    ("air_setpoint_min", {"air_min": 6.2}, {}, AIR, {"setpoint_bar": 8.6}, FAIL, None),
    ("aisle_lux_ge", {}, {}, {"min_lux": 75}, {"lux": [80]}, OK, None),
    ("aisle_lux_ge", {}, {}, {"min_lux": 75}, {"lux": [60]}, FAIL, None),
    ("aisle_lux_ge", {}, {}, {"min_lux": 75}, {"lux": []}, UNK, None),
    ("co2_lt", {"co2_ppm": 620}, {}, {"max_ppm": 1000}, {}, OK, None),
    ("co2_lt", {"co2_ppm": 1200}, {}, {"max_ppm": 1000}, {}, FAIL, None),
    ("co2_lt", {"co2_ppm": None}, {}, {"max_ppm": 1000}, {}, UNK, None),
    ("data_fresh", {"remote": 1}, {}, {}, {"fresh_names": ["remote"]}, OK, None),
    ("data_fresh", {"remote": 1}, {}, {}, {"fresh_names": ["remote", "s1_p"]}, FAIL, "немає свіжих даних: s1_p"),
]
