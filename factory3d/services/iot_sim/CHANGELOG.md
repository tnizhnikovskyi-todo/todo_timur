# Changelog — iot_sim

## Unreleased: повний емулятор КГУ TEDOM (модуль td_chp, SPEC td_chp §8)
- Модель `chp` (`iot_sim/models/chp.py`) переписана за мокапом `build/chp/mockup/b_sim.js`: штатно резерв; пуск — 9 кроків за R-13 (60 с, масштаб `chp_start_s/60`,
  «Попередній підігрів» 1,5 с при `t_jacket_out ≥ 55`), робота, охолодження 60 с; аварії 111…116 (тиск газу, перегрів ОЖ, гаряча зворотка зі зниженням потужності,
  загазованість 20 %, пожежа з гасінням через 3 с, аварійний стоп), зупинки без аварії `alarm/trip` 1…3 (мережа S2 при `chp_island=false`, ROCOF, зняття дозволу);
  16 циліндрів (A5 +27 К, `plug_h` 3560), ТО/газ/НТ/вихлоп/повітря/безпека/лічильники — 230 регістрів нової карти в інженерних одиницях (`Chp.regs`).
  Режими `ctl/mode` 0…3 за мокапом, **4 (за замовчуванням)** — старий профіль день/ніч: P ≈ 400/800 кВт, тепло/газ 497/109 і 856/199 рівно; сигнали `infra/chp/*`,
  `infra/totals/chp_kw` і дублі `chp/gen/p_kw`, `chp/ht/q_total`, `chp/gas/flow` ненульові лише в `state = 2` (як і раніше). Старі прапори `chp_run`, `chp_cmd`, `chp_ack`,
  `chp_permit`, `gas_bar`, `ctl_remote`, `chp_start_s` і вікно u73 230–233 працюють без змін; `chp/cmd` стоп у резерві — як і раніше `ack = 1`.
- Modbus u72 (`protocols/modbus_maps/tedom.py`): регістри 40000–40007, 40010–40015, 40020 без змін; решта 226 — з `catalog/chp_registers.json` (байт-в-байт копія
  `td_chp/data/chp_signals.json`, перевіряє `test_chp_map.py` і AC-26 у td_chp): `u16/i16/u32` за `scale`, запис `W/RW` (`ctl/cmd` 40900, `ctl/mode`, `sp_pct`, `cos_set`,
  `heat_dir`, `bypass_mode`) — `Chp.post_command`/`Chp.write_reg`; `write_accept=false` — виняток 4, значення поза межами — 3, місцевий режим — запис ігнорується,
  команда → `ack=2`, `ack_reason=3`. Нова команда скидає `ctl/ack` у 0; результат — не пізніше наступного тіку. Причини відмови `ctl/ack_reason` — R-06 (1…13).
  `Ctx.model(device)` у `modbus_maps/__init__.py`.
- Сценарії S-25…S-30 (група `energy`, 600 с): `chp_overheat`, `chp_hot_return`, `chp_gas_leak`, `chp_fire`, `chp_rocof`, `chp_no_permit` — прапори `chp_temp_fault`,
  `chp_ret_fault`, `chp_gas_leak`, `chp_fire`, `chp_rocof`, `chp_permit = 0`; відкат повертає прапори (аварію скидає лише `ctl/cmd = 4`). Реєстр — 30 сценаріїв.
- Тести: `tests/unit/test_chp_full.py` (AC-25, AC-27, режими, команди), `tests/unit/test_chp_map.py` (AC-24, AC-26 у частині копії карти); лічильники реєстра → 30
  (`test_scenarios.py`, `test_control_api.py`); `tests/protocols/test_chp_modbus.py` — нова карта по Modbus TCP (блоки, команда пуску, уставки, винятки 2/3). `test_catalog.py` і `catalog/signals.csv` без змін.

## Unreleased: живе виробництво — цілі станів верстатів від Odoo (контракт C-LP-01)
- `POST /api/v1/machines/targets` (дубль `/sim/v1/machines/targets`; `core/machine_targets.py`, `protocols/machine_targets_api.py`, у `control_api.py` лише рядки реєстрації):
  список `{"code", "state": "working|idle|down", "reason", "until"}` (або `{"targets": [...]}`), токен SIM API як у решти керувальних маршрутів (401/403/423); відповідь
  `{"ok", "unknown", "expired"}`; `GET` тих самих шляхів — чинні цілі з залишком, станом і потужністю верстата (для налагодження). Сховище — `world.flags["machine_targets"]`
  (у знімку; `reset` очищає). `until` — реальний час UTC (не sim-час); `until` у минулому знімає ціль; після `until` — автономна поведінка.
- Модель `machine`/`io_machine`: при цілі стан береться з неї (`working` → WORKING, `idle` → READY, `down` → ERROR з повідомленням за `reason`: E0421/A0201/E0430/A0202/E0440,
  інше — E0400), навантаження за R-02 (номінал із шумом / холостий хід / 0) і через `p_now` — лінії щитів, лічильники, компресор; фізичні збої, блекаут і `fire_drill` первинні;
  синтетичні `SIM-…` завдання при цілі не створюються. Зміна цілі — подія (`payload.target`). Без цілі поведінка не змінилась. Відповідність кодів: `td.machine.code` = код
  пристрою (35 з 35, таблиця не потрібна). Тести: `tests/unit/test_machine_targets.py`, `tests/protocols/test_machine_targets_api.py` (у т. ч. OPC UA).

## Unreleased: пожежна евакуація (вау №8 «Евакуація в 3D»)
- Сценарій S-24 `fire_evacuation` (`iot_sim/core/scenarios_evac.py`, реєструється рядком імпорту в кінці `scenarios.py`): каскад `fire_drill` + люди з СКУД ідуть своїм маршрутом
  до виходів і проходять через двері виходів (подія BioStar на `ACR-IN`, `tna_key=2`, `door_id` виходу: турнікет `1` або аварійні двері `11…21`); частина людей — не своїм виходом
  (`wrong_exit_pct`), `stuck` людей із зони пожежі не виходять («застряглі»); після `duration_s` каскад відкочується, люди повертаються турнікетом, двері зачиняються на замок
  (20736), зупинка робить те саме негайно. Каталог `catalog/evac_routes.json` (генератор `tools/gen_evac_catalog.py`). Тести `tests/unit/test_scenario_evac.py`; реєстр — 24 сценарії.

## Unreleased: портал STORETEQ (вау №19)
- Авто-завдання порталу: `protocols/woodstore_auto.py` — РЦ розкрою (SAW-1…3, NEST-1) у WORKING без завдання в черзі отримує `feed` на 2…5 листів із `external_ref` = МО активного завдання РЦ
  (REST woodStore раніше віддавав лише завдання від Odoo); `GET /status` показує фази `moving/picking/placing`. `SIM_WOODSTORE_AUTOFEED=0` вимикає. Тести: `tests/protocols/test_woodstore_auto.py`.
- Стоси woodStore стенда: `catalog/woodstore_stacks.json` — 27 стосів `PLT-01A…PLT-09C`, 23 з листами, як залишки демо-бази Odoo (раніше 36 синтетичних зі стосами `PLT-04E`, яких в Odoo немає;
  `SIM_WOODSTORE_STACKS` — інший файл). Тести `test_woodstore.py` перейшли на непорожній стос `PLT-01B`.

## Unreleased
- Штатний стан «Енергетики» як у макеті W1: КГУ **в резерві** (`state=0`, `chp_kw=0`); запуск — прапор світу `chp_run`
  або запис ненульового «Load setpoint» у HR 40007 (Modbus u72), 0 — зупинка. СЕС: сезонна амплітуда `season`
  (жовтень ≈ 0,75 літнього). BESS: розряд на дефіцит лише понад `bess_shave_kw` (600 кВт; 0 — R-13 макета).
  У робочу добу `Q1 + Q2 > 0` (імпорт +), невеликий експорт лише на T2 вдень. Тести: `test_models_energy`, `test_models_pv`.

## 0.1.0
- Перший випуск емулятора обладнання factory3d: ядро (World, сигнали, сценарії S-01…S-15, знімок), моделі (РЦ, енергетика,
  інженерія, пожежна панель, двір, СКУД, мобільна техніка), протоколи (OPC UA, Modbus TCP, BACnet/IP, HelvarNet, MQTT, BioStar 2,
  SICS, woodStore, jobs, LPR push), REST керування `/sim/v1`, режим `follow_odoo`.
- Стенд (W6): `tests/stand` (`pytest -m stand`, ТК/ТБ/ТП), compose `dev`/`demo`, `TEST_REPORT.md`, `DEPLOY_TEST.md`.
- Виправлено за результатами стенду: образ (макет BACnet), `read_only` ФС, compose (ports лише в dev), BACnet (інтерфейс
  `f3d_sim`, 302 LSP, сегментація `object-list` перевірена), OPC UA (26 прапорів, заборона клієнтського Write),
  знімок РЦ (`shift_key`), MQTT (`status` при зміні, `to_charge`), `battery_low`, `reset` моделей і двору, поріг `QF-*`,
  код 401 BioStar, метрика tick lag, `SIM_HELVAR_VERSION` з env.
- `fire_drill` без `detector` для `FA-CNC` піднімає `2.CNC.05` (AC-15); Modbus 2020 (Reset All Energies) обнуляє лічильники.
- `mypy --strict`, `ruff`, `pre-commit` (корінь репозиторію).
