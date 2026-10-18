# TEST_REPORT — td_bms 19.0.1.0.0 (стенд, ТК/ТБ/ТП, SPEC §13.2–13.5)

Воркер W7, 15.10.2026, гілка `claude/f3d-td_bms`. Код стенда — `odoo_addons/td_bms/tests/stand/`; відтворення — `DEPLOY_TEST.md`.

## Середовище

Чиста база з `f3d_template` + `td_factory3d`, `td_telemetry`, `td_bms` (+ seed: обладнання з `td_code`, команда, календарі ТК).
iot_sim (процес), колектор з плагіном `f3d-collector-bms` (процес), MQTT — `amqtt` (образ mosquitto не завантажився: ліміт реєстру 429).
**Копії демо-бази немає** → кроки/AC «на демо» — ⏭. Годинник емулятора — 10:00 Київ; Odoo — реальний час.

## Підсумок

- UT `/td_bms`: **139/139** (0 failed), плагін pytest: **28 passed**.
- Стенд: ТК-01…ТК-10, ТК-12 — пройшли (з відхиленнями нижче); ТК-11 ⏭; ТБ-01…03, 05…07, 09, 10 — стенд пройшов; ТБ-04, ТБ-08 — UT; ТП-01…05 — виконані.
- DoD: `grep x_f3d` порожній; `ruff check` (модуль і плагін, line-length 120) чистий; `write_enabled` за замовчуванням `False` (параметр і всі джерела).

## ТК

| ТК | Результат | Числа / примітка |
|---|---|---|
| ТК-01 | ✅ з відхиленнями | 33 джерела online (32 + BMS-DERIVED), 32 групи `live`, 29 установок без stale. **Відхилення:** у alarm ще LT-OUT-2…7, LT-RCV-7 `check «нижче норми»` (D-1) і LT-FAC `faults=2` (D-2); RV-05 фільтр на старті емулятора ≈120 Па (не 285), тому alarm RV-05 не спостерігається |
| ТК-02 | ✅ | alarm за 140 с; заявка «Заміна фільтрів: перепад тиску **271** Па при нормі до 250» (значення на момент перетину порога під час розгону, не 285 — O-1), команда «Служба головного механіка», `filter_supply`, епізод open→closed, `alarm_count≥1`/`plan_state=alarm`; після `stop` ok і епізод closed ≤ 4 хв |
| ТК-03 | ✅ | LT-CUT level=0 в Odoo за 2–4 с (push); заявка «вимкнено в робочий час … 500 лк» за 114–122 с; LT-EB `e_now=329`, заявка «≈ 329 лк при нормі 500 лк (рівень 60 %)»; після stop — норма, епізоди closed |
| ТК-04 | ✅ | `faults=1`, `faulty=1.2.1.5`, заявка «несправних 1 шт.», опис містить LP-2 і G:12 (збагачується кроном ≤ 1 хв), щит LP-2 `fault`, після stop `faults=0` |
| ТК-05 | ✅ | standby/«Очікування», `heat_kw=0`, `setpoint_night_c=14.0`, нових заявок 0; з календарем «Цілодобово» — **26** заявок `unit_off` |
| ТК-06 | ✅ | `BOILER state=fault` → заявка `boiler_fault`, `boilers_on=0`, `boiler_state=fault`, дефіциту 0; clear → епізод closed |
| ТК-07 | ✅ | HN-LP-2 `error` («Connection refused») ≤ 10 с, 5 груп LP-2 stale, щит `offline`, нових заявок 0; повернення порту → online, не stale |
| ТК-08 | ⚠ частково | Крок SPEC (`/device/RV-07/fault comm`) **не відтворюється емулятором**: BACnet-сервер лише піднімає BI Fault і далі відповідає (D-3). «Мовчання» відтворено `params.device=999`: error за 20–30 с, сигнали stale, перевірка «немає даних», заявок по RV-07 немає, повернення → online/«норма» |
| ТК-09 | ✅ | LT-MAINT сцена 3: `done` за 3 с, `result="C11 G19 S3 F200 ack"`, `scene=3`; RV-05 `VEL` за 11 с; після вимкнення — `UserError «Керування вимкнено»`, прапори `write_enabled` 0/0 |
| ТК-10 | ◐ | Дані `get_overview_data` збігаються з формами (LT-CUT `e_now=509`, баланс **753 кВт з 990 кВт**, KPI 32 групи/29 установок). Картки переглядача, «Показати в 3D», живе оновлення ≤ 15 с — ⏭ браузер/`td_viewer3d` у стенді не встановлено |
| ТК-11 | ⏭ | `td_fire_safety` з'явився в дереві лише в кінці роботи; не встановлювався в стендову базу в межах ліміту часу. AC-33 покрито UT (тестовий сигнал) |
| ТК-12 | ✅ | `supply_c`/`indoor_c` RV-08 у межах шуму, рівень LT-CUT збігається з емулятором точно |

«Одна зона → усі» (`test_deploy.py`): читання лише RV-08, RV-09, HN-LP-2 → 3 online, 29 disabled, заявок по інших об'єктах немає; потім усі 32 online. ✅

## ТБ

| ТБ | Результат |
|---|---|
| 01, 02 | ✅ `test_tb01_tb02_acl` (стенд) + UT `test_acl_matrix` |
| 03 | ✅ колектор `F3D_WRITE_ENABLED=0`: команда не забирається (`queued`→`expired`, ніколи `sent/done`); expired за 120 с (крок `expires_min=1`, крон 10 хв — запущено вручну); 5 запобіжників — UT `test_commands` |
| 04 | ✅ UT (`test_commands`, плагін `test_protocol` AC-73) |
| 05, 09 | ✅ `test_tb05_tb09_injection` (`;DROP`, `#`, `res.partner`, `res.users`) + UT |
| 06 | ✅ `host evil.example.com is not allowed (F3D_ALLOW_HOSTS)` |
| 07 | ✅ окрема база: до `1\|33\|1` (параметри\|джерела\|крон) → після `0\|0\|0` |
| 08 | ✅ UT `test_signal_definitions` (`test_hooks`) |
| 10 | ✅ лог колектора (INFO) без кадрів HelvarNet |

## ТП

| ТП | Норма | Факт |
|---|---|---|
| 01 | p95 ≤ 2 с, overrun 0 за 30 хв | вікно **600 с** (не 30 хв): p95 BACnet-опитування ≤ 0,025 с (n=695), `poll_overrun` 0 → 0 |
| 02 | обхід ≤ 30 с @20/с; 32 групи ≤ 10 с @100/с | PT з фейком 320 пристроїв: обхід **16,8 с**; рівень+потужність+сцена **1,0 с** |
| 03 | push p95 ≤ 1 с | p95 ≤ 0,25 с (123 пакети) |
| 04 | крон ≤ 2 с, огляд ≤ 0,5 с | крон max **0,142 с** (59 check-сигналів, 549 сигналів, 136 епізодів), огляд max **0,184 с** (перший виклик) |
| 05 | ≤ 60 000 рядків/добу | 543 за 900 с → ≈ **52 100/добу** (екстраполяція; доби не було). За вікно 30 хв під час ТК — ≈ 61 700 (вище норми, але з навантаженням сценаріями) |

## Дефекти / спостереження (код інших власників)

- **D-1** (дані bms/emulator): групи LT-OUT-2…7, LT-RCV-7 при рівні 80 % емулятора мають `e_now` 255–283 лк < норми 300 → `check «нижче норми»` у ТК-01 (очікувалося «норма»).
- **D-2** (`services/iot_sim/iot_sim/models/lighting.py`, відповідь C:164): для груп із кількома діапазонами (LT-FAC) адреси на стику склеєні без коми (`@1.2.3.64@1.2.4.1`) → плагін вважає 2 пристрої «відсутніми», `faults=2` постійно, заявка «Аварія світильників LT-FAC». Відтворення: `>V:2,C:164,G:16#` на :50000. Плагін міг би бути стійким (розбір за `@`).
- **D-3** (`services/iot_sim/iot_sim/protocols/bacnet_server.py`): `fault comm` для BACnet-пристрою не припиняє відповіді → крок ТК-08 SPEC неможливий.
- **O-1** (SPEC/telemetry): заголовок заявки фіксує значення при перетині порога (271), а SPEC ТК-02 очікує 285.
- **O-2**: на старті емулятора RV-05 `filter_dp_pa≈120`, а не 285 (SPEC ТК-01).
- Операційне: XML-RPC не віддає `get_overview_data` (повертає `None`) — клієнтам потрібен JSON-RPC.

## Матриця AC → тест

Тести: `T:` — Odoo UT (`tests/test_*.py`), `P:` — плагін (`collector_plugins/f3d_collector_bms/tests`), ТК/ТБ — стенд.

| AC | Покриття |
|---|---|
| 01 | T:test_hooks 13_norms_effective_lux; test_lighting_calc norm_* |
| 02 | T:test_hooks 32_groups_match_macro; test_lighting_calc groups_match_macro |
| 03 | T:test_lighting_calc formula_synthetic, min_one |
| 04 | T:test_lighting_calc passport_values, defaults_without_passport, manual_override |
| 05 | T:test_lighting_calc pack_dali_function, devices_valid; test_hooks devices_match_appendix |
| 06 | T:test_lighting_calc unique_dali_group, code_and_checks |
| 07 | T:test_lighting_live design_fallback, live_values |
| 08 | T:test_lighting_live sheets_design, design_sums |
| 09 | T:test_lighting_live state |
| 10 | T:test_lighting_live plan_state_table |
| 11 | T:test_lighting_live light_power |
| 12 | T:test_lighting_live search_deviation |
| 13 | T:test_hooks balance_753; test_heat_balance macro_753 |
| 14 | T:test_heat_balance param_change_recompute, internal_gains |
| 15 | T:test_heat_balance chp_heat_table |
| 16 | T:test_heat_balance live_balance_table, live_model |
| 17 | T:test_viewer_provider ventilation_static_equal_demo; test_data_sync |
| 18 | T:test_heat_balance constraints |
| 19 | T:test_hvac_live nominals; test_hooks units |
| 20 | T:test_hvac_live mode_labels_states |
| 21 | T:test_hvac_live fallback_formulas |
| 22 | T:test_hvac_live live_precedence |
| 23 | T:test_hvac_live heat_now_contract |
| 24 | T:test_hvac_live constraints |
| 25 | T:test_rules_lighting work_interval |
| 26 | T:test_rules_lighting off_in_work_delay, off_since_yesterday; ТК-03 |
| 27 | T:test_rules_lighting below_norm, tolerance_zero; ТК-03 |
| 28 | T:test_rules_lighting no_data, mains_suppression; ТК-07 |
| 29 | T:test_rules_lighting since_from_reading_ts, internal_context_skips |
| 30 | T:test_rules_lighting local_source, not_stale_by_telemetry, foreign_push_rejected |
| 31 | T:test_rules_hvac not_running, vel_ok, fault_separate; ТК-05 |
| 32 | T:test_rules_hvac cold_work, cold_off_hours |
| 33 | T:test_rules_hvac fire_suppression_signal (ТК-11 ⏭) |
| 34 | T:test_rules_hvac filter_supply_rv05; ТК-02 |
| 35 | T:test_rules_hvac unit_fault_frost, ef_chg_charging, ef_elec_overheat, ahu_pressure, boiler_fault; ТК-06 |
| 36 | T:test_rules_hvac heat_deficit, heat_no_data, boiler_fault; ТК-06 |
| 37 | T:test_requests light_off_title; ТК-03 |
| 38 | T:test_requests titles_table, unit_off_and_cold, cold_off_hours_title, heat_deficit_title; ТК-05 |
| 39 | T:test_requests faults_description; ТК-04 |
| 40 | T:test_requests open_update_close, new_episode; ТК-02 |
| 41 | T:test_requests cooldown_new_request, idempotent |
| 42–45 | T:test_viewer_provider (lighting/ventilation_static_equal_demo, live_values, delta, contract) |
| 46, 47 | T:test_overview structure_counts, action_open; test_hoot; ТК-10 (дані) |
| 48 | T:test_hooks counts, 6_scenes, 32_groups…; test_data_sync signal_count |
| 49 | T:test_hooks signal_count_and_origins; знімок 468/81 на демо — ⏭ (немає копії) |
| 50 | T:test_hooks links (на seed-обладнанні); на демо — ⏭ |
| 51 | T:test_hooks signal_definitions, sources |
| 52 | **без автотесту на демо — ⏭** (TC на копії демо: епізод для заявки id 6); логіку епізодів покриває test_requests |
| 53 | T:test_hooks reinstall_idempotent |
| 54 | T:test_hooks params_environment |
| 55 | T:test_hooks uninstall_hook |
| 56 | T:test_hooks neutralize; ТБ-07 (стенд) |
| 57 | T:test_hooks write_flags; test_commands enable_disable |
| 58 | T:test_commands light_scene, light_level_multi; ТК-09 |
| 59 | T:test_commands refusals; ТК-09 (UserError), ТБ-03 |
| 60 | T:test_commands hvac_mode_setpoint, forbidden_write_flags; test_hvac_live command_refused_for_fans |
| 61 | T:test_security acl_matrix; ТБ-01/02 (стенд) |
| 62 | T:test_install groups_chain, menus; test_security groups_chain, menus |
| 63 | T:test_security reinstall_admin_only; test_overview action_open; test_lighting_calc injection_rejected; ТБ-05/09 |
| 64–67 | P:test_protocol |
| 68–72, 74–78 | P:test_plugin_helvarnet |
| 73 | P:test_protocol, test_plugin_helvarnet |

**AC без автоматичного покриття в середовищі:** AC-52 (потребує копії демо); AC-49/AC-50 — лише на чистій базі (знімок/лічильники 468/81 на демо ⏭); AC-33 — ТК-11 ⏭ (є UT на тестовому сигналі).
