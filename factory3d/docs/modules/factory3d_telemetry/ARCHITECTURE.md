# factory3d_telemetry — технічне рішення

Версія 0.3 · 14.10.2026 (0.2 — 14.10.2026) · автор: агент-архітектор модуля (хвиля 2) · статус: **чернетка на погодження**.
Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-86 (CT-07: вбудований провайдер viewer `signals` 90 між machine_connect 75 і
telemetry 95), X-83 (§2.3: `f3d.reading.received_at` — час прийому; Q-15), X-81 (FR-25: рівневий запис без `pulse_ms`) (v0.3).
Зміни (v0.2): 14.10.2026 — правки за `docs/CONSISTENCY.md` v0.3: X-02 (CT-10: API-02/API-05 = `_f3d_ingest`), X-03 (CR-01: payload
команд, `call()` плагіна, CT-02, FR-21/FR-24; модуль 19.0.1.1.0), X-04 (FR-21, §2.6: `env.su`), X-05 (FR-29, A-17, A-23:
`bacnet_event`, `read_only` — лише Who-Is/RP/RPM), X-06 (FR-12: `stale` для COV), X-07 (A-25: `delta`), X-16 (A-10:
`origin='module'`), X-27 (CT-07: порядок провайдерів 75/155), X-34 (без жорсткої кількості рядків каталогу), X-46
(FR-25: `pulse_ms`), X-53 (FR-22: `/f3d/<route>[/<secret>]`), X-58 (§4.3), X-63 (масштаб — SPEC R-02); закрито Q-04
(X-42), Q-08 (X-28), Q-12 (X-21), Q-14 (X-58), Q-15 (X-48); нові A-23…A-25, у SPEC — AC-93…AC-103.
Каркас: `docs/ARCHITECTURE.md` (далі «каркас»: §4 топологія, §5 конвенції, §6.4 контракт телеметрії,
§6.5 колектор і плагіни, §6.6 протокольна матриця, §6.8 заявки ТО, рішення D-02, D-04, D-11; рішення менеджера
14.10.2026: плагін `bacnet_ip` належить цьому модулю, а не bms).
Специфікація: `docs/modules/factory3d_telemetry/SPEC.md`. Спирається на контракти `factory3d_base`
CB-01, CB-07, CB-08, CB-09, CB-10, CB-11 (SPEC base §2, ARCH base §2.1) і `factory3d_viewer` M-01
(хук провайдера), M-03 (шина), Додаток C (карта 196 шляхів), а також на «документацію вендора»
`factory3d_iot_sim` SPEC (2 381 рядок, завершений 14.10.2026) §8.4 (Modbus, unit id), §8.8 (P-06 MQTT), §8.9 (P-07),
§8.10 (BACnet/IP), §8.11 (P-09 BACnet панелі, тільки читання), §8.13.2 (Axis LPV JSON), Додаток A (каталог
сигналів з адресами — джерело міграції `f3d.sim.signal → f3d.signal`; кількість рядків веде iot_sim, з доповненнями
модулів за X-34). Рішення автора — **A-xx**
(§7), відкриті питання — **Q-xx** (§5.1).

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора; `docs/оцінки` в репозиторії ще немає) |
|---|---|---|
| ТР | цей документ + SPEC.md | 24 |
| Архітектура | погодження A-xx/Q-xx з менеджером, фіксація контрактів CT-01…CT-10 для модулів фаз 2–5 | 10 |
| Розробка | Odoo-модуль `odoo_addons/factory3d_telemetry` (56) + сервіс `services/collector` з чотирма плагінами `modbus_tcp`, `mqtt`, `http_push`, `bacnet_ip` (52) | 108 |
| Тестування | юніт-тести Odoo, тести колектора з фейковими серверами, ТК проти емулятора, безпека, продуктивність | 48 |
| Інструкція | §4 цього документа + README модуля й сервісу + CHANGELOG | 8 |
| **Разом** | | **198** |

Факти про тестовий сервер timur-o19demo, база `odoo` (перевірено 14.10.2026 01:50, лише читання):
Odoo 19.0+e; data-модуль `factory3d_iot_sim` 19.0.1.0.0 установлений: `x_f3d_signal` — 196 записів
(xml-id `factory3d.sig_<slug>`, усі 196 мають xml-id), `x_f3d_reading` — 7 448 записів (найстаріший
13.10 19:30, найновіший 14.10 01:50; крок 10 хв, ротація 2 доби), `maintenance.equipment.x_f3d_signal_ids`
(one2many, manual), крон `cron_iot_sim` активний (1 хв). Стани: 195 «норма», 1 «тривога»
(`ventilation/units/RV-05/filter_dp_pa` = 304,2 Па, заявка id 6 «Заміна фільтрів: перепад тиску 285 Па
при нормі до 250», стадія «New Request», `maintenance_type='preventive'`); `fire/groups/FA-FAC/dust` = 86,0 %
з заявкою id 5 (стадія «New Request»). Режими: `noise` 73, `energy` 40, `machine` 35, `drift` 28, `hours` 9,
`drain` 8, `level` 1, `solar` 1, `counter` 1. Одиниці: кВт 44, кВт·год 40, м³/год 30, °C 29, Па 26, % 12,
год 9, бар 3, кПа 2, шт 1. Обладнання 208, заявок ТО 17; стадії ТО: New Request, In Progress, Repaired
(done), Scrap (done); команди: «Internal Maintenance», «Служба головного механіка» (на всьому обладнанні
макета). У `maintenance.equipment` Odoo 19 **немає** полів `period`/`next_action_date` (планове ТО —
через `maintenance.request.recurring_maintenance`), тому ТО за лічильником — власні поля модуля (§2.3).

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що є в макеті

| Джерело | Що саме | Як використовується |
|---|---|---|
| `odoo_addons/factory3d_iot_sim/data/models.xml` | моделі `x_f3d_signal` (23 поля: `x_name`, `x_code`, `x_sequence`, `x_active`, `x_equipment_id`, `x_workcenter_id`, `x_source_id`, `x_kind`, `x_unit`, `x_mode`, `x_value`, `x_nominal`, `x_noise`, `x_rate`, `x_limit`, `x_alarm`, `x_threshold`, `x_state`, `x_charging`, `x_seed`, `x_updated`, `x_request_id`) і `x_f3d_reading` (`x_name`, `x_signal_id`, `x_equipment_id`, `x_value`, `x_unit`, `x_time`); поле `maintenance.equipment.x_f3d_signal_ids` | карта міграції полів у `f3d.signal`/`f3d.reading` (SPEC §5.3, Додаток D) |
| `odoo_addons/factory3d_iot_sim/data/actions.xml` | `action_iot_tick`: формули режимів, тривога `x_alarm ∈ {below, above}` проти `x_threshold`, заявка ТО `maintenance_type='corrective'` з назвою «Сигнал: <назва> — <значення> <од.>», дедуплікація «поки `x_request_id` відкрита — нової немає», `drift` скидається до номіналу, коли `x_request_id.stage_id.done`; журнал раз на 10 хв; ротація `x_time < now − 2 доби` | правила R-04…R-07 SPEC відтворюють цю поведінку в проді (пороги, дедуплікація, скидання, ротація) |
| `odoo_addons/factory3d_iot_sim/views/views.xml` | список сигналів з `decoration-danger`, форма з групами «Зараз/Звідки/Як поводиться/Тривога», графік показань `line` за годинами, вкладка «Сигнали» на обладнанні, меню «Обслуговування → Імітація IoT» | представлення V-xx SPEC замінюють їх без втрати функцій |
| `plant/odoo_flows.py: signal_specs` (рядки 680–762) | 196 сигналів: шлях, обладнання, величина, одиниця, режим, стартове значення, номінал, шум, швидкість, межа, тривога/поріг, посилання на заявку (`request=mrs.get(code)`) | Додаток B SPEC: власник кожного сигналу за префіксом; стартові пороги |
| `plant/odoo_pull.py: sync_signals` (рядки 270–296) | шлях → вузол payload; `%` → `/100` (3 знаки), інакше 2 знаки при `\|v\| < 20`, 1 знак інакше; `drain` + `x_charging` → `state=charging\|busy`; `energy.totals.pv_kw/chp_kw` = `infra.totals`; `meta.iot` | R-12 SPEC (провайдер переглядача) |
| `factory3d_viewer` SPEC M-01h, Додаток C | 196 шляхів за групами (35+35 `energy/consumers/<WC>`, 10 інженерних споживачів, 16 техніки, 2 портал, 3 компресор, 2 аспірація, 2 котельня, 2 спринклери/пневмокільце, 81 вентиляція, 1 пожежна, 4 трансформатори, 3 генерація) | ті самі коди, те саме правило застосування |
| `dist/odoo_demo.json: equipment` | `FL-1…FL-5, FL-C1, FL-C2, TUGGER-1` (`battery` 0,34…0,85, `hours` 921…4 594, `state` busy/charging, `next_maintenance`), `COMPRESSOR` (`pressure_bar` 6,81, `hours` 17 840,8, `load` 0,642), `DUST-1` (`filter_dp_kpa` 1,42, `airflow_m3h` 29 767,6), `BOILER` (`supply_c` 77,4, `silo_fill` 0,611), `GANTRY-1` (`cycles_today` 373, `vacuum_kpa` −71,9), `SPRINKLERS` 7,15 бар, `AIR-RING` 6,37 бар | номінали й приклади чисел у R-xx; ТО за лічильником (COMPRESSOR 17 840,8 → 18 000, заявка MR/00033) |
| `dist/odoo_demo.json: energy.transformers`, `infra.totals`, `infra.cards.WATER` | T1 333,3 кВт / 59,1 °C, T2 296,0 кВт / 55,6 °C (`temp_c = 38 + 60·S/Sн`, `plant/energy.py:327`); `bess_soc` 0,761, `chp_kw` 397,3, `pv_now` 0; лічильник води 18 642 м³, 2,1 м³/год | адреси емулятора для T1/T2 (ADAM-6015 unit 96), лічильника води (ADAM-6050 unit 84, DI8) |
| `plant/equipment_specs.json` (ролі `compressor`, `dust_extraction`, `biomass_boiler`, `forklift`, `board_forklift`, `tugger`, `transformer`, `water_meter`) | паспорти: Atlas Copco GA 37 VSD+ FF ×2 + ресивер LV911; NESTRO NKJ 32 000 м³/год; Kalvis K-500M; Jungheinrich EFG 216 / EZS 350; Linde X50/600; Trihal 1000 кВА; Apator MWN50-G NK | номінали через `f3d_get_num(key)` (CB-08), інтервали ТО за лічильником (ПРИПУЩЕННЯ, Q-06) |
| `factory3d_iot_sim` SPEC §8.4.1 (unit id), §8.8 (MQTT `f3d/mobile/<code>/telemetry`, схема `telemetry`), §8.9.3 (Elektronikon Mk5, unit 70, регістри 3001…3100), §8.9.6 (ADAM-6017 unit 90, ADAM-6015 unit 96, ADAM-6050 unit 84), §8.10.3 (BOILER BACnet dev 140), §8.13.2 (Axis LPV JSON → `/f3d/lpr`), Додаток A рядки 81–107, 189–196 (макет) і 335–365 (29 нових `telemetry`) | адреси емулятора для сигналів у моїй зоні (P-06, P-07, P-08 котельня) і формат адрес каталогу | Додаток C SPEC: прив'язка джерел на стенді; парсер адрес каталогу R-24 |
| `README.md` «Імітація IoT» | очікувана поведінка для користувача: графік за 2 доби, вкладка «Сигнали», тривога → заявка, закрили заявку — показник повертається | інструкції §4 |

### 1.2 Ролі й сценарії використання

| Роль (групи) | Що робить | Де в меню |
|---|---|---|
| Головний механік (`group_f3d_user` + `maintenance.group_equipment_manager`) | дивиться показники на картці обладнання (вкладка «Сигнали»), графік за 2 доби, отримує заявки ТО з порогів і за лічильником, закриває їх | Обслуговування → Обладнання → вкладка «Сигнали»; Обслуговування → Заявки |
| Інженер АСУ / енергетик (`group_f3d_manager`) | заводить джерела даних (адреса, параметри), прив'язує сигнали до джерел (адреса в джерелі), крутить пороги, інтервали ТО за лічильником, перевіряє стан джерел на дашборді | Завод 3D → Телеметрія → Джерела / Сигнали / Огляд |
| Адміністратор (`group_f3d_admin`) | реєструє колектори, генерує токени, вмикає/вимикає стоп-крани, запускає міграцію рівня 0, ротацію | Завод 3D → Телеметрія → Колектори; Налаштування → Завод 3D |
| Переглядач (будь-хто з `group_f3d_user`, кіоск) | бачить живі значення на картках 3D, тривоги, `meta.iot` | 3D-переглядач |
| Колектор (технічний клієнт, токен) | бере конфігурацію, шле показання й стан джерел, бере команди на запис | `/f3d/telemetry/*` |
| Модулі фаз 2–5 (код) | додають типи джерел і плагіни, правила й представлення поверх `f3d.signal`/`f3d.reading`, обробники `http_push`, команди на запис | контракти CT-01…CT-10 (§2.1) |

### 1.3 Функціональні вимоги

| ID | Вимога (перевірювана) |
|---|---|
| FR-01 | Модель `f3d.source` описує джерело даних одного з 8 типів (`modbus_tcp`, `mqtt`, `http_push`, `opcua`, `bacnet_ip`, `helvarnet`, `sics`, `rest_vendor`) з параметрами JSON, що перевіряються за схемою типу, станом (`online`/`offline`/`error`/`disabled`), прапорами `read_enabled`/`write_enabled` і прив'язкою до колектора. |
| FR-02 | Модель `f3d.collector` реєструє колектор: код, токен (зберігається хеш, показується один раз), версія, останній контакт, стан, лічильники буфера; один колектор обслуговує N джерел. |
| FR-03 | Модель `f3d.signal` містить усі поля §6.4 каркаса (`code` = шлях §5, `equipment_id`, `source_id`, `address` JSON за схемою типу джерела, `unit`, `kind`, `period_s`, `scale`, пороги `warn_low/warn_high/alarm_low/alarm_high/alarm_states`, `last_value`, `last_ts`, `status`, `maintenance_request_id`) плюс `origin`, `module`, `store_period_s`, `hysteresis`, `min_duration_s`, `alarm_title`. |
| FR-04 | Показання `f3d.reading` записуються ідемпотентно за `(signal_id, ts)`, зберігаються за політикою `store_period_s` (R-03), ротуються за `factory3d.telemetry.keep_days`. |
| FR-05 | Годинні агрегати `f3d.reading.hour` (`v_min/v_avg/v_max/v_sum/v_count/v_first/v_last`) рахуються кроном із показань і ротуються за `keep_hours_days`. |
| FR-06 | `GET /f3d/telemetry/config` віддає колектору його джерела й сигнали з адресами, з `ETag`; `If-None-Match` → `304`. |
| FR-07 | `POST /f3d/telemetry/push` приймає пакет ≤ 2 000 показань у UTC, ідемпотентно, оновлює `last_*` і `status`, повертає статистику й `config_etag`; при `read_enabled=False` — `423`. |
| FR-08 | `POST /f3d/telemetry/status` оновлює стан колектора й джерел; `GET /f3d/telemetry/health` без токена повертає `ok`/версію, з токеном — лічильники. |
| FR-09 | Пороги обчислюють `status` ∈ {`ok`, `warn`, `alarm`} з гістерезисом і мінімальною тривалістю; для `kind='state'` тривога — належність до `alarm_states`. |
| FR-10 | `alarm` створює `maintenance.request` за §6.8 каркаса (одна відкрита заявка на сигнал, `f3d_signal_id`, `f3d_equipment_code`, `maintenance_type='corrective'`, команда обладнання, текст українською з показником і порогом); відкрита заявка блокує нову. |
| FR-11 | Закриття заявки (стадія `done`) очищає `maintenance_request_id`, перераховує `status`, пише в чаттер сигналу; нова заявка на той самий сигнал — не раніше `realarm_cooldown_s`. |
| FR-12 | Сигнал без показань довше `stale_periods × period_s` (не менше `stale_min_s`; для BACnet-сигналів у режимі `cov` замість `period_s` — інтервал контрольного читання `max(period_s·10, 300)` с, X-06) отримує `status='stale'`; джерело `offline` переводить у `stale` усі його сигнали; перше показання повертає стан. |
| FR-13 | ТО за лічильником: на обладнанні `f3d_meter_signal_id` (сигнал `kind='counter'`), інтервал, значення/дата останнього ТО, обчислені «наступне» і «залишилось»; за `lead_pct` до межі створюється планова заявка (`maintenance_type='preventive'`), закриття якої фіксує нове «останнє ТО». |
| FR-14 | Вкладка «Сигнали» на `maintenance.equipment` (`f3d_signal_ids`) замінює `x_f3d_signal_ids` зі збереженням колонок і виділення тривог; статбокс «Сигнали/Тривоги». |
| FR-15 | Представлення: джерела (список, форма, kanban-дашборд стану), колектори, сигнали (список, форма, графік, зведена), показання (графік за 2 доби за замовчуванням, список), налаштування. |
| FR-16 | Меню «Завод 3D → Телеметрія» (`sequence=30` під `factory3d_base.menu_f3d_root`): Огляд, Сигнали, Показання, Джерела, Колектори, Команди. |
| FR-17 | Провайдер переглядача `f3d.viewer.provider.telemetry` (`_f3d_sequence=95`) вставляє `last_value` за шляхом (правила `odoo_pull.sync_signals`), `meta.iot`, стан техніки з сигналу `equipment/<code>/state`; дельти — через `f3d.viewer.event._notify('f3d.signal', codes, kind='signal')` з дебаунсом `bus_min_interval_s`. |
| FR-18 | `post_init_hook` переносить 196 `x_f3d_signal` → `f3d.signal` (`origin='sim_data'`, `source_id` порожній, `module` за префіксом) і весь журнал `x_f3d_reading` → `f3d.reading`, вимикає крон рівня 0, архівує `x_`-сигнали, ховає меню/представлення рівня 0, пише звіт; повторний запуск нічого не дублює. |
| FR-19 | Стоп-крани `factory3d.telemetry.read_enabled` (умовчання за `factory3d.base.environment`, CB-10), `factory3d.telemetry.write_enabled` (`False`), `neutralize.sql` (крони, джерела, токени колекторів, обидва прапори). |
| FR-20 | Права: читання — `group_f3d_user`; джерела, сигнали, пороги, інтервали ТО — `group_f3d_manager`; колектори, токени, стоп-крани, міграція — `group_f3d_admin`; токени не з'являються в логах і відповідях. |
| FR-21 | Команди на пристрої `f3d.command` (`signal_id`, значення або корисне навантаження `payload` JSON — CR-01, X-03; стан) створюються менеджером або модулем (під `sudo()`/`with_user(SUPERUSER_ID)` — без перевірки групи, X-04) лише при `write_enabled` на модулі, джерелі й сигналі; колектор забирає їх `GET /f3d/telemetry/commands`, виконує `write()` плагіна (для команди з `payload` — `call()`), звітує результат (для `call()` — з `data`). |
| FR-22 | Події `http_push` (Axis LPV, вебхуки) приймає колектор на `POST /f3d/<route>[/<secret>]` (напр. `/f3d/lpr`; X-53 — як SPEC §8.7, iot_sim, yard), ретранслює в `POST /f3d/telemetry/event`; Odoo диспетчеризує їх обробникам `f3d.push.handler` модулів-власників (yard — `f3d.push.handler.yard`, маршрут `lpr`) і, якщо є сигнал з адресою на цей маршрут, пише показання через `_f3d_ingest`. |
| FR-23 | Колектор `services/collector`: планувальник опитувань за `period_s`, підписки, буфер на диску (SQLite) при недоступності Odoo, пакетна відправка з бекофом, перечитування конфігурації за ETag, метрики Prometheus, JSON-логи без секретів. |
| FR-24 | Інтерфейс плагіна (`connect`, `subscribe`/`poll`, `write`, `call` — CR-01, X-03, `health`) з реєстрацією через entry points `factory3d_collector.plugins`; плагіни `modbus_tcp`, `mqtt`, `http_push`, `bacnet_ip` — у цьому модулі; плагіни інших модулів підключаються без змін ядра. |
| FR-25 | Плагін `modbus_tcp`: функції 01/02/03/04, типи `bool/u16/i16/u32/i32/f32/u64`, порядок слів, лінійне масштабування, агрегація кількох регістрів (`max/min/sum`), пул з'єднань на `host:port`, групування суміжних регістрів в один запит; запис імпульсом `write.pulse_ms` (пише 1, через `pulse_ms` — 0; X-46, CAME у yard) лише для імпульсних команд; без `pulse_ms` — рівневий запис (yard `cmd_hold`; X-81). |
| FR-26 | Плагін `mqtt`: paho 2.1, MQTT 3.1.1, підписка на топіки з параметрів джерела, вибір значення з JSON за `path`, відображення рядків у стани, `status`-топіки → стан джерела, LWT. |
| FR-27 | Безпека колектора: allow-list хостів пристроїв (`F3D_ALLOW_HOSTS`), запис вимкнений за замовчуванням (`F3D_WRITE_ENABLED=0`), токени й паролі лише з env, валідація адрес за JSON-схемами до з'єднання. |
| FR-28 | У data модуля — джерела й адреси стенда (емулятор) для сигналів моєї зони (P-06 техніка, P-07 компресор/аспірація/трансформатори/вода/спринклери/пневмокільце, P-08 котельня) та 29 нових сигналів `telemetry` з Додатка A iot_sim (№ 335–365: `equipment/<техніка>/state`, `/x`, `/y` ×8, `equipment/COMPRESSOR/state`, `/temp_c`, `equipment/DUST-1/state`, `infra/water/m3_total`, `/flow_m3h`); решта сигналів чекають прив'язки модулями-власниками через помічник CT-11. |
| FR-29 | Плагін `bacnet_ip` (bacpypes3): адресація `device/object/instance/property` (у т.ч. `positive-integer-value`/PIV — X-37), режими `cov` (SubscribeCOV з поновленням) і `poll` (ReadPropertyMultiple), читання `present-value`, `priority-array`, `status-flags`; запис `present-value` з пріоритетом лише при `write_enabled` (стан MSV — за зворотним `map`, X-66); пристрої з `read_only` (пожежна панель) — лише Who-Is/ReadProperty/ReadPropertyMultiple (D-07, X-05); ретрансляція `UnconfirmedEventNotification` у маршрут `bacnet_event` для fire_safety (X-05). |
| FR-30 | Помічник імпорту каталогу емулятора `env['f3d.signal']._f3d_import_sim_catalog(...)` (CT-11): створює/оновлює `f3d.signal` з `f3d.sim.signal` за кодами або модулем-споживачем, перетворюючи текстову адресу каталогу на JSON `address` (R-24); нерозібрані адреси — у звіт. |
| FR-31 | Локальні джерела без колектора (рішення менеджера 14.10.2026 за td_genset Q-20): типи з `f3d.source._f3d_local_types()` (базово порожньо, модулі розширюють через `super()`; міст генератора — `td_genset`) не потребують колектора, не потрапляють у `GET /f3d/telemetry/config` і крони stale/офлайну колектора, показання надходять лише через CT-10 `_f3d_ingest`, команди на них неможливі (SPEC R-26). |

### 1.4 Межі: що не входить

- Плагіни `opcua`, `woodstore` (machine_connect), `helvarnet` (bms), `sics` (yard), `biostar2` (access), `relay_genset` (td_genset) — лише інтерфейс і схема адреси для них (CT-02, CT-03). `bacnet_ip` — мій (рішення менеджера 14.10), але об'єкти вентустановок (dev 101–133) прив'язує bms, панелі FACP-1 (dev 200) — fire_safety.
- Прив'язка джерел для сигналів `energy/*`, `infra/*` (крім лічильника води), `ventilation/*`, `lighting/*`, `fire/*`, `workcenters/*`, `equipment/GANTRY-1/*` (P-03 woodStore — machine_connect) — модулі-власники через CT-11; до прив'язки сигнали живуть як `sim_data` без джерела (значення не оновлюються, `status='stale'` після міграції не ставиться — R-07 п. 4).
- Розподіл енергії на МО, тарифи, OEE, простої — energy/machine_connect.
- Сирі ряди 1 с (стани верстатів) у `f3d.reading` — не зберігаються (D-11); machine_connect веде їх у власному журналі часу і пише в `f3d.reading` за `store_period_s`.
- Сповіщення (e-mail/SMS) про тривоги — стандартні підписки чаттера на `maintenance.request`; окремого механізму немає.
- Видалення `x_`-моделей рівня 0 — робить `factory3d_iot_sim` 19.0.3.0.0 (його ARCH §2.8 п. 4); модуль лише вимикає і архівує (A-07), необов'язкове видалення — за параметром `drop_level0`.
- Керування емулятором (`/sim/v1`) — пульт `factory3d_iot_sim`.

## 2. Технічна реалізація

### 2.1 Місце в системі

`depends`: `factory3d_base` (домішка CB-01 для кодів обладнання/РЦ, паспорти CB-07/CB-08, меню CB-09,
групи й параметр середовища CB-10, утиліти міграції CB-11), `maintenance` (заявки, стадії, команди),
`mail` (чаттер на сигналах і джерелах), `web`. Через base — `mrp`, `mrp_maintenance` (`workcenter_id`
на обладнанні). `factory3d_viewer` — **optional**: провайдер живе в міст-модулі `factory3d_telemetry_viewer` (`depends`
telemetry + viewer, `auto_install`, A-20); `factory3d_iot_sim` — optional: міграція рівня 0 виконується, якщо є `x_f3d_signal`.

Контракти, які **задає** цей модуль (посилатися як `factory3d_telemetry CT-xx`):

| ID | Контракт | Споживачі |
|---|---|---|
| CT-01 | Моделі `f3d.collector` (M-01), `f3d.source` (M-02), `f3d.signal` (M-03), `f3d.reading` (M-04), `f3d.reading.hour` (M-05), `f3d.command` (M-06) з іменами полів SPEC §2; інші модулі **не** створюють власних журналів показань (D-04), а додають записи джерел/сигналів через data/хуки і розширюють моделі через `_inherit` | усі модулі фаз 2–5 |
| CT-02 | Інтерфейс плагіна колектора: клас `SourcePlugin` (`services/collector/collector/plugins/base.py`) з `connect(source)`, `subscribe()` (push-плагіни; показання — через `ctx.emit()`, SPEC §8.3.2), `poll(signals)`, `write(signal, value, text) -> str`, `call(signal, payload: dict) -> dict` (CR-01, X-03: команда з `f3d.command.payload`; умовчання — `NotSupported`; реалізують `opcua`/`rest_vendor` machine_connect), `health()`; плагін повертає інженерне значення за ключами адреси, `signal.scale` застосовує ядро (X-63, SPEC R-02); реєстрація entry point `factory3d_collector.plugins` = `<type> = <pkg>:<Class>`; типи даних `SourceCfg`, `SignalCfg`, `Reading`, `Health` (SPEC §8.3) | machine_connect (`opcua`, `woodstore`), bms (`helvarnet`; користується `bacnet_ip`), fire_safety (користується `bacnet_ip`), yard (`sics`; користується `http_push`), energy (користується `modbus_tcp`) |
| CT-03 | JSON-схема `f3d.signal.address` на кожен тип джерела і `f3d.source.params` (SPEC Додаток A): обов'язкові ключі зафіксовані тут; модуль-власник плагіна може додавати ключі, але не змінювати обов'язкові (ключі-розширення `opcua`/`rest_vendor`/`helvarnet` перелічено в Додатку A довідково, X-52); виняток — `sics`: власник схеми yard (§8.2), Додаток A — її копія (X-45); спільні ключі адреси всіх типів — `scale`, `offset` (застосовує плагін, X-63); Modbus-адреси — **PDU (0-based)** у ключі `addr` за документом вендора (D-20, X-42), вендорська нотація — довідково в `doc` | ті самі |
| CT-04 | API-01…API-07 `/f3d/telemetry/*` (SPEC §7): формат пакетів, коди відповідей, ETag, токен `Authorization: Bearer <token колектора>` | колектор, тести, емулятор (режим без колектора — Q-02) |
| CT-05 | Правило заявок ТО R-05/R-06 (SPEC §9) — єдине для всіх модулів: модуль-власник лише ставить пороги/`alarm_states`/`alarm_title` на сигналі; створення, дедуплікація, скидання — тут | bms, fire_safety, energy, yard |
| CT-06 | Поля на стандартних моделях: `maintenance.equipment.f3d_signal_ids`, `f3d_signal_count`, `f3d_alarm_count`, `f3d_meter_*`; `maintenance.request.f3d_signal_id`, `f3d_equipment_code`, `f3d_origin`, `f3d_value`, `f3d_threshold` | viewer (картки), machine_connect, energy |
| CT-07 | Провайдер переглядача `f3d.viewer.provider.telemetry` (95): правило R-12 (шлях → вузол, `%`→частка, округлення, стани). Порядок провайдерів (каркас §6.7, viewer M-01; X-27, X-86): вбудовані 20…70, machine_connect 75, вбудований `signals` 90, **telemetry 95**, energy 100, lighting 110, ventilation 120, fire 130, evacuation 140, infra 150, genset 155, yard 160, access 170. Провайдери з `_f3d_sequence > 95` (energy, bms, fire, genset, yard, access) викликаються **після** telemetry й можуть перекрити значення своїми обчисленнями, але не дублюють логіку сигналів. Провайдери модулів з `_f3d_sequence < 95` (machine_connect 75) працюють **до** telemetry: шляхи, які такий провайдер обчислює сам, не мають видимих сигналів — їхні сигнали ставлять `viewer_visible=False` (machine_connect `mc_state` → `workcenters/<C>/machine_state`), інакше R-12 перезапише значення. Вбудований провайдер viewer `signals` (90, viewer M-01h — значення рівня 0 `x_f3d_signal`) теж працює до telemetry: після міграції він не має активних записів, без неї обидва пишуть ті самі шляхи й останнім — telemetry (SPEC M-10; X-86) | viewer, machine_connect, energy, bms, fire_safety, td_genset, yard, access |
| CT-08 | Хук `f3d.push.handler` (AbstractModel): атрибут `_f3d_push_routes: tuple[str]`, метод `_f3d_handle_push(route, event: dict) -> None`; модуль реалізує для своїх маршрутів (`lpr` — yard, `tapio` — machine_connect за потреби) | yard, machine_connect |
| CT-09 | Класифікатор `module` сигналу (Selection) і правило R-15 (префікс шляху → модуль): `energy/*`, `infra/*` → `energy` (крім `infra/water/*` → `telemetry`); `ventilation/*`, `lighting/*` → `bms`; `fire/*` → `fire_safety`; `equipment/*` → `telemetry`; `workcenters/*` → `machine_connect`; `yard/*`, `access/*` → `yard`/`access`; `infra/genset/*` → `genset` | усі |
| CT-10 | Метод `env['f3d.signal']._f3d_ingest(readings: list[dict], src='module', collector=None) -> dict` — **єдиний вхід усіх показань** (D-19, X-02): API-02 і API-05 викликають `env['f3d.signal'].sudo()._f3d_ingest(readings, src='collector', collector=c)`, модулі з даними в Odoo (`factory3d_access`, `td_genset`, похідні energy/bms) — `src='module'`; `tools/ingest.Ingester` напряму не викликається. Точка розширення: модулі перевизначають метод через `_inherit` з тією самою сигнатурою, викликають `super()` з незміненими аргументами першою дією, що змінює дані, і повертають його результат без змін (власні дії — у `savepoint`); та сама валідація, пороги, шина (SPEC M-03, R-17 п. 0) | access, td_genset, fire_safety, energy, machine_connect, yard, bms |
| CT-11 | Помічник `env['f3d.signal']._f3d_import_sim_catalog(codes=None, module=None, source_map=None, defaults=None) -> dict` — імпорт рядків каталогу емулятора `f3d.sim.signal` (iot_sim M-03, Додаток A) у `f3d.signal`: `code`, `name`, `kind`, `unit`, `scale`, `nominal`, пороги, `sim_mode/sim_params`, `address` (R-24 — парсер текстових адрес Додатка A), `source_id` за `source_map` (`{"u70": "MB-U70-COMPRESSOR", "dev105": "BAC-105-RV-05", "mqtt": "MQTT-MOBILE"}`); результат `{created, updated, unparsed: [codes]}` | energy, bms, fire_safety, machine_connect, yard |
| CT-12 | Хук `f3d.source._f3d_local_types() -> list[str]` (базово `[]`, розширення через `super()`) і правило SPEC R-26: для локальних типів `collector_id` не обов'язковий, `params` перевіряється лише як об'єкт JSON без секретів, `address` не перевіряється; API-01 і крони R-07/R-25 їх не бачать; показання — лише CT-10; команди — `UserError` | td_genset (міст `factory3d_genset`, тип `td_genset`); інші модулі з даними, що вже є в Odoo |

Що **бере** модуль: iot_sim M-03 `f3d.sim.signal` (поля `code`, `name`, `device_id.code`, `protocol`, `address`, `dtype`, `unit`,
`scale`, `nominal`, `thresholds`, `model_rule`, `origin`, `level0_code`, `kind`) як джерело каталогу (optional); CB-01 (`f3d_code` обладнання/РЦ для текстів заявок і `f3d_equipment_code`),
CB-07/CB-08 (`f3d_get_num('power_kw')` для умовчань номіналів у майстрі нового сигналу), CB-09 (меню),
CB-10 (групи, `factory3d.base.environment`), CB-11 (`read_manual_field`, `drop_manual_fields` при
`drop_level0`); viewer M-01 (`_f3d_viewer_collect`, `_f3d_viewer_delta`, `ctx`), M-03 (`_notify`), API-03
(`patch.signals`); iot_sim §8.4.1 (unit id), §8.8 (топіки/схема P-06), §8.9.3/§8.9.6 (регістри P-07), §8.10
(об'єкти BACnet), §8.13.2 (JSON Axis LPV), Додаток A (каталог).

### 2.2 Архітектурна схема

```
 мережа цеху / f3d_sim                      docker compose поруч з Odoo (/opt/timur-o19)
┌──────────────────────┐   Modbus TCP 502   ┌───────────────── services/collector (один процес asyncio) ─────────────────┐
│ емулятор iot_sim     │◄───── poll ────────│ plugins/modbus_tcp  (pymodbus 3.9.2; пул з'єднань host:port; групування регістрів)│
│  unit 70 Elektronikon│◄─ UDP 47808 ──────│ plugins/bacnet_ip   (bacpypes3; Who-Is, RPM, SubscribeCOV; запис із пріоритетом)   │
│  unit 84/90/96 ADAM  │                    │ plugins/mqtt        (paho 2.1; підписки f3d/mobile/+/telemetry, status, LWT)    │
│  BACnet dev 101…200  │                    │ plugins/http_push   (aiohttp server :8080  POST /f3d/<route>, напр. /f3d/lpr)│
│  …                   │   MQTT 1883        │ plugins/<інших модулів> через entry points factory3d_collector.plugins       │
│ mosquitto            │─── subscribe ─────►│ core/scheduler  core/buffer(SQLite WAL)  core/odoo_client  core/commands     │
│ Axis LPV / вебхуки   │─── HTTP POST ─────►│ metrics :9108   logging(JSON, SecretFilter)   config: env F3D_*              │
└──────────────────────┘                    └───────┬──────────────────────────────▲──────────────────────────────────────┘
                                 push/status/event/commands-result  │              │  config (ETag), commands (Bearer <token колектора>)
                                                                    ▼              │
┌──────────────────────────────── Odoo 19 + factory3d_telemetry ───────────────────┴──────────────────────────────────────┐
│ controllers/telemetry.py  API-01 config · API-02 push · API-03 status · API-04 health · API-05 event · API-06/07 commands │
│ f3d.collector ─1:N─ f3d.source ─1:N─ f3d.signal ─1:N─ f3d.reading (raw, keep_days) ─крон─► f3d.reading.hour (агрегати)   │
│                                        │ пороги R-04 ─► maintenance.request (R-05/R-06)   │ ТО за лічильником R-11      │
│                                        │ f3d.viewer.event._notify(kind=signal) ─► bus ─► переглядач (/f3d/viewer/delta) │
│                                        └ f3d.viewer.provider.telemetry (95): payload[шлях] = last_value (R-12)           │
│ f3d.push.handler (хук) ◄── API-05 ── маршрути lpr/tapio → yard/machine_connect                                           │
│ рівень 0 (x_f3d_signal/x_f3d_reading) ── post_init_hook ──► f3d.signal/f3d.reading; крон рівня 0 → off; x_active=False   │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Потоки: (1) колектор ← пристрої (опитування Modbus/BACnet/OPC UA, підписка MQTT, прийом HTTP POST);
(2) колектор → Odoo пакетами `push` (кожні `push_interval_s` або при `push_max`); (3) Odoo → колектор
`config` (ETag, опитування `config_poll_s` = 60 с і одразу, коли `push` повернув інший `config_etag`);
(4) Odoo → колектор `commands` (лише при `write_enabled`); (5) Odoo → переглядач через шину.

### 2.3 Нові й розширені об'єкти

| Об'єкт | Призначення | Пише | Читає |
|---|---|---|---|
| `f3d.collector` (M-01) | реєстрація колектора, токен (хеш), версія, `last_seen`, стан, буфер | адміністратор, API-03 | API-01/02, дашборд |
| `f3d.source` (M-02) | джерело: тип, `params` JSON (схема типу), колектор, `read_enabled`/`write_enabled`, стан, `last_ok`, `last_error` | менеджер, data модулів, API-03 | API-01, дашборд, форма сигналу |
| `f3d.signal` (M-03) | визначення сигналу §6.4 + `address` JSON, пороги, `last_*`, `status`, `origin`, `module`, `store_period_s`, `alarm_title`, `derived_from_id`, `sim_mode/sim_params` | менеджер, data, хук міграції, API-02 (`last_*`, `status`) | API-01, провайдер, вкладка «Сигнали», графіки |
| `f3d.reading` (M-04) | показання: `signal_id`, `ts` (час пристрою), `value`, `text`, `quality`, `src`, `received_at` (час прийому в Odoo, X-83); `_log_access=False`; унікальність `(signal_id, ts)` | API-02 (SQL batch), хук міграції, CT-10 | графік «Показання», крон агрегатів |
| `f3d.reading.hour` (M-05) | годинні агрегати `v_min/v_avg/v_max/v_sum/v_count/v_first/v_last`; `(signal_id, hour)` унікальні | крон `cron_f3d_telemetry_hour` | зведена, energy (кВт·год за годину), звіти |
| `f3d.command` (M-06) | команда на запис у пристрій: сигнал, значення або `payload` (JSON ≤ 64 КБ, CR-01), стан `queued→sent→done/failed/expired`, хто, результат (`result`, `result_data`) | менеджер/модулі (`write_enabled`; модулі — під `sudo()`), API-06/07 | колектор, меню «Команди» |
| `f3d.push.handler` (M-11, AbstractModel) | хук диспетчеризації подій `http_push` до модулів | — | API-05 |
| `f3d.viewer.provider.telemetry` (M-10) | провайдер переглядача (95) у міст-модулі `factory3d_telemetry_viewer` (A-20, `auto_install`) | — | переглядач |
| `maintenance.equipment` (+поля, M-07) | `f3d_signal_ids`, `f3d_signal_count`, `f3d_alarm_count`, `f3d_meter_signal_id`, `f3d_meter_interval`, `f3d_meter_last_value`, `f3d_meter_last_date`, `f3d_meter_next_value`, `f3d_meter_remaining`, `f3d_meter_lead_pct`, `f3d_meter_request_id`, `f3d_meter_unit` | менеджер, R-11 | вкладка «Сигнали», «ТО за лічильником» |
| `maintenance.request` (+поля, M-08) | `f3d_signal_id`, `f3d_equipment_code`, `f3d_origin` (`threshold`/`meter`/`manual`), `f3d_value`, `f3d_threshold`; перевизначення `write` (закриття → R-06/R-11) | R-05, R-11 | механік, переглядач (`maintenance_requests`) |
| `res.config.settings` (+поля, M-09) | стоп-крани, `keep_days`, `keep_hours_days`, `stale_periods`, `bus_min_interval_s`, `realarm_cooldown_s`, `default_store_period_s`, команда ТО за замовчуванням | адміністратор | модуль |
| `f3d.collector.token.wizard` (M-12, Transient) | показ нового токена один раз | адміністратор | — |

### 2.4 Інтеграції

| P-xx / канал | Пристрої (коди) | Протокол, адреса на стенді (емулятор) | Напрямок | Частота (`period_s`) | При недоступності |
|---|---|---|---|---|---|
| P-06 | FL-1…FL-5, FL-C1, FL-C2, TUGGER-1 | MQTT 3.1.1 `mosquitto:1883`, топіки `f3d/mobile/<code>/telemetry` (QoS 1), `…/status` (retained, LWT) — iot_sim §8.8 | підписка (push від шлюзу) | 5 с (1 с у русі) — приймаємо все, зберігаємо за `store_period_s` | без брокера → джерело `offline`, сигнали `stale` через 3×5 с ≥ 60 с (R-07); LWT `online:false` → `offline` одразу |
| P-07 компресор | COMPRESSOR | Modbus TCP `iot-sim:502`, unit 70 (Elektronikon Mk5, iot_sim §8.9.3 — ПРИПУЩЕННЯ, Q-05 iot_sim); регістри: тиск addr 3001, завантаження 3009, мотогодини 3019–3020 (u32), стан 3000, температура 3002 | опитування | 10 с; мотогодини 60 с | повтор з бекофом 1→30 с; 3 помилки поспіль → `error`; сигнали `stale` |
| P-07 аспірація | DUST-1 | ADAM-6017 unit 90: AI0 витрата (raw addr 0), AI1 перепад (addr 1); ADAM-6050 unit 84: DI0 run, DI1 fault (fc 02, addr 0–1) — iot_sim §8.9.6 | опитування | 10 с | як вище |
| P-07 спринклери, пневмокільце | SPRINKLERS, AIR-RING | ADAM-6017 unit 90: AI2 (addr 2), AI3 (addr 3), 0…16 бар | опитування | 10 с | як вище |
| P-07 трансформатори | T1, T2 | ADAM-6015 unit 96: RTD0–2 → T1 (addr 0–2, `agg=max`), RTD3–5 → T2 (addr 3–5); −50…+150 °C | опитування | 30 с | як вище |
| P-07 лічильник води | WATER | ADAM-6050 unit 84: лічильник DI8 (fc 03, addr 16–17, u32, порядок слів **little** — ADAM), 1 імп = 10 л | опитування | 60 с | як вище; лічильник монотонний, пропуски не ламають дельту (R-08) |
| P-08 котельня | BOILER | BACnet/IP `iot-sim:47808`, роутер → мережа 2, device 140 (iot_sim §8.10.3): AI:1 `BOILER_SupplyTemp` → `equipment/BOILER/supply_c`, AI:3 `BOILER_SiloLevel` → `/silo_fill`; COV (`cov-increment` 0,2 °C / 1 %) з резервним опитуванням | COV-підписка / резервне опитування | 30 с; COV — за зміною | COV не відновлюється 2×lifetime → опитування; `reliability ≠ no-fault-detected` → `quality='bad'`; пристрій не відповідає → `error`, `stale` |
| P-08/P-09 через мій плагін (джерела — bms/fire_safety) | RV-01…25, AHU-1, EF-* (dev 101–133), FACP-1 (dev 200) | ті самі механізми; для dev 200 `write_enabled=False` жорстко (плагін відмовляє, навіть якщо прапор увімкнули — D-07) | COV | — | — |
| http_push | CAM-05, CAM-06 (Axis LPV), вебхуки | колектор слухає `http://collector:8080/f3d/lpr` (= iot_sim `SIM_LPR_PUSH_URL`, Q-09 iot_sim); JSON за iot_sim §8.13.2 (`sensorProviderID`, `plateText`, `carState`, `GEOtarget`); камера автентифікації не має → allow-list IP маршруту (`allow_ips`) і/або токен `X-F3D-Token` для вебхуків | прийом POST → ретрансляція в Odoo API-05 | за подією | буфер SQLite, повтор; дублікати за `event_id` (sha256 тіла + маршрут) |
| Odoo ↔ колектор | — | `GET /f3d/telemetry/config` (ETag), `POST …/push`, `POST …/status`, `GET …/commands`, `POST …/commands/result`, `POST …/event`, `GET …/health` | — | push 5 с / ≤ 1 000 показань; status 60 с; config 60 с; commands 5 с (лише при `write_enabled`) | буфер до `F3D_BUFFER_MAX_MB` (200 МБ ≈ 4 М показань), далі — найстаріші видаляються з WARNING |
| Odoo → переглядач | — | `bus.bus` канал `f3d_viewer`, `kind='signal'` (viewer C-03) | — | не частіше `bus_min_interval_s` (10 с) на сигнал | без viewer — нічого |
| Рівень 0 (`x_f3d_*`) | 196 сигналів | ORM (моделі в реєстрі) | читання при міграції | один раз | якщо моделей немає — крок `skipped` |

Усі P-05 (PM5560), Huawei/TEDOM/ATyS (P-07 енергетичні), P-01…P-04, P-08 вентиляція/освітлення, P-09…P-12 —
через ті самі моделі й API, але джерела додають модулі-власники (CT-11); плагіни `modbus_tcp`, `bacnet_ip`,
`mqtt`, `http_push` вони перевикористовують.

### 2.5 Потік даних від пристрою до екрана

Приклад 1 — тиск компресора (Modbus): 1) колектор за конфігурацією має сигнал
`equipment/COMPRESSOR/pressure_bar` з `address={"unit":70,"fc":3,"addr":3001,"type":"u16","scale":0.001}`
на джерелі `MB-U70-COMPRESSOR` (`params={"host":"iot-sim","port":502,"unit":70}`), `period_s=10`;
2) `core/scheduler` кожні 10 с викликає `modbus_tcp.poll([...сигнали unit 70 з однаковим періодом])`;
плагін читає один блок `addr 3000…3020` (групування R-20), декодує `u16` 6772 → `6.772` бар;
3) `Reading(code, ts=UTC now, value=6.772, q='good')` потрапляє в буфер; 4) раз на 5 с `odoo_client` шле
`POST /f3d/telemetry/push` ≤ 1 000 показань; 5) контролер перевіряє токен, валідує, пише `f3d.reading`
(якщо минуло `store_period_s=300` від останнього збереженого — R-03), оновлює `last_value=6.772`,
`last_ts`, рахує `status` (R-04: `alarm_low=6.0`, гістерезис 0,1 → `ok`), 6) змінені коди йдуть у
`f3d.viewer.event._notify('f3d.signal', codes, 'signal')` (R-13); 7) переглядач отримує з шини подію,
запитує `/f3d/viewer/delta`, провайдер (95) віддає `signals: [{path: "equipment/COMPRESSOR/pressure_bar",
value: 6.77}]`; картка COMPRESSOR показує «Тиск 6,77 бар». Якщо значення впаде до 5,9 → `status='alarm'`,
після 30 с утримання (`min_duration_s`) заявка «Компресорна станція: тиск 5,9 бар при нормі від 6» (R-05, A-21) на обладнанні COMPRESSOR, команда «Служба
головного механіка».

Приклад 2 — заряд АКБ резервного навантажувача (MQTT): телематичний шлюз (емулятор) публікує
`f3d/mobile/FL-C1/telemetry` `{"ts":…,"code":"FL-C1","state":"busy","battery_pct":23.6,"hours":2306.2,…}`;
плагін `mqtt` на джерелі `MQTT-MOBILE` для сигналу `equipment/FL-C1/battery` з `address={"topic":
"f3d/mobile/FL-C1/telemetry","path":"battery_pct"}` дає `23.6`; для `equipment/FL-C1/state`
(`kind='state'`, `address={"topic":…,"path":"state","map":{"to_charge":"busy"}}`) — текст `busy`; Odoo:
`warn_low=25` → `status='warn'` (без заявки), переглядач показує `battery: 0.236`, `state: "busy"`;
при 14,2 % (`alarm_low=15`) — заявка «Зарядити АКБ: заряд 14,2 % при нормі від 15» (R-05).

Приклад 3 — ТО за лічильником: `COMPRESSOR.f3d_meter_signal_id = equipment/COMPRESSOR/hours`,
`f3d_meter_interval=2000`, `f3d_meter_last_value=16000` → `next=18000`; при `last_value=17900`
(`lead_pct=5` → 100 год до межі) створюється планова заявка «ТО за лічильником: COMPRESSOR — 18 000 год
(зараз 17 900)»; після закриття `f3d_meter_last_value=17 9xx` (значення на момент закриття), `next=19 9xx`.

Усі кроки — SPEC R-03…R-13; без `factory3d_viewer` кроки 6–7 пропускаються (`'f3d.viewer.event' in env`).

### 2.6 Безпека

- **Групи** (CB-10): `group_f3d_user` — читання всього; `group_f3d_manager` — `f3d.source`, `f3d.signal`,
  пороги, `f3d.command` (створення), поля ТО за лічильником; `group_f3d_admin` — `f3d.collector`, токени,
  стоп-крани, міграція рівня 0, `drop_level0`. Токен-хеш і підказка — поля з `groups=group_f3d_admin`.
- **Токени колекторів** (A-02): сирий токен генерується `secrets.token_urlsafe(32)`, показується один раз у
  майстрі; в базі — `sha256` hex; перевірка `hmac.compare_digest`; `neutralize.sql` стирає хеші.
  Контролери — `auth="public"`, `csrf=False`, перевірка `Authorization: Bearer` до будь-якого звернення
  до ORM, далі `sudo()` з контекстом `f3d_collector_id`. Без токена/невірний → `401`; колектор
  `active=False` → `403`; `read_enabled=False` → `423` на `push`/`event`, `config` віддає всі джерела з
  `read_enabled:false`.
- **Стоп-крани**: `factory3d.telemetry.read_enabled` (умовчання `environment == 'test'`), `write_enabled`
  (`False`), на джерелі `read_enabled`/`write_enabled`, на сигналі `write_enabled`; команда створюється
  лише коли всі три `write` прапори `True` і в колектора `F3D_WRITE_ENABLED=1` (чотири незалежні запобіжники).
  Перевірка групи `group_f3d_manager` при створенні команди пропускається під `env.su` (`sudo()`,
  `with_user(SUPERUSER_ID)` — модулі yard, bms, machine_connect після власних перевірок ролі), прапори — ні (X-04, як
  base R-04).
  `neutralize.sql`: обидва параметри `False`, крони модуля `active=False`, `f3d.source.read_enabled=False`,
  `f3d.collector.token_hash=NULL`, `f3d.command` у `queued` → `expired`.
- **Ін'єкції**: `code` — regex R-01 до SQL; `address`/`params` — валідатори схем (чисті функції
  `tools/address.py`, без `eval`); у SQL лише параметризовані запити (`execute_values` для показань);
  `path` у MQTT-адресі — лише `[A-Za-z0-9_.\[\]]`; маршрути `http_push` — `^[a-z][a-z0-9_]{0,31}$`.
- **Ліміти**: пакет ≤ 2 000 показань і ≤ 1 МБ; ≤ 60 push/хв на колектор (понад — `429`); `ts` не з
  майбутнього (> 60 с) і не старше `keep_days`.
- **Колектор**: без root у контейнері, `read_only` ФС (крім `state/`), allow-list хостів
  `F3D_ALLOW_HOSTS` (перевірка перед кожним `connect`), жодних записів у пристрої без
  `F3D_WRITE_ENABLED=1`, логи через `SecretFilter` (маскування токенів/паролів), `/metrics` без
  секретів, TLS до Odoo (`https://`), перевірка сертифіката (`F3D_ODOO_CA` для самопідписаних).
- **Заборонено**: Odoo сам не ходить у мережу цеху (§4 каркаса); колектор не пише в Odoo нічого, крім
  `push/status/event/commands-result`; команди на пристрої пожежної панелі — неможливі (у bms/fire
  сигнали `write_enabled=False` за правилом D-07; модуль це не перевизначає); до джерела `bacnet_ip` з
  `params.read_only=true` плагін ініціює лише Who-Is/ReadProperty/ReadPropertyMultiple — `SubscribeCOV`,
  `AcknowledgeAlarm`, `LifeSafetyOperation`, `WriteProperty*`, `DeviceCommunicationControl`, `ReinitializeDevice` тощо
  блокуються в коді до відправки (X-05, SPEC §8.8, ТБ-06).

### 2.7 Продуктивність і обсяги

Періоди за типами сигналів (умовчання `period_s` у data; верстати 1 с — не тут):

| Клас | Сигнали | `period_s` | `store_period_s` | Показань/добу (сирих, усі) | Збережених/добу |
|---|---|---|---|---|---|
| Телеметрія інженерії (P-07/P-08 gauge+state) | ≈ 15 (компресор, аспірація, тиск, T1/T2, котельня) | 10–30 | 300 | 86 400…129 600 | 4 320 |
| Лічильники (hours, kwh_shift, cycles, water) | 52 | 60 | 300 | 74 880 | 14 976 |
| Техніка P-06 | 40 (battery, hours, state, x, y) | 5 (push, 1 с у русі) | 300 (state — за зміною; x/y — 60) | ≈ 700 000 | ≈ 28 000 |
| Вентиляція/пожежна/енергетика (інші модулі, після прив'язки) | ≈ 118 | 10–60 | 300 | ≈ 400 000 | 34 000 |
| **Разом 225 сигналів** | | | | ≈ 1,3 М/добу через API (≈ 15/с) | **≈ 81 000/добу** |

`f3d.reading`: рядок ≈ 56 Б даних + індекси ≈ 70 Б → 81 000/добу ≈ 10 МБ/добу; **30 днів ≈ 2,4 М рядків
≈ 310 МБ; 90 днів ≈ 7,3 М ≈ 920 МБ** (`keep_days` за замовчуванням 30; без `x/y` техніки — на 40 % менше,
їх `store_period_s=60` можна підняти). `f3d.reading.hour`: 225 × 24 = 5 400/добу, 400 днів ≈ 2,2 М рядків
≈ 220 МБ. Індекси: `f3d_reading_signal_ts_uniq (signal_id, ts)`
(унікальний, покриває графіки за сигналом), `f3d_reading_ts_idx (ts)` (ротація), `f3d_reading_hour_uniq
(signal_id, hour)`. Навантаження на Odoo: push 12 показань/с у пакетах по ≤ 1 000 кожні 5 с → ≤ 1 запит/5 с
на колектор; обробка пакета 1 000 показань ≤ 1 с (один `search_read` сигналів, один `execute_values`,
один `executemany` для `last_*`). Ротація — батчами по 50 000 рядків, ≤ 60 с за прогін. Сирі ряди 1 с
(верстати, 35 × 86 400 = 3 М/добу) — не в `f3d.reading` (D-11, Q-01: TimescaleDB поруч із колектором, коли
знадобиться); поріг перегляду — > 20 М рядків у `f3d_reading` або `keep_days > 90`.

### 2.8 Міграція з демо-бази і деінсталяція

`post_init_hook` (SPEC §5.3), ідемпотентно, у транзакції установки:

1. Параметри, джерела й нові сигнали з data (29 нових `telemetry` за Додатком A iot_sim, джерела стенда).
2. Якщо `'x_f3d_signal' in env`: 196 `x_f3d_signal` → `f3d.signal` (ключ `code = x_code`; поля — SPEC
   Додаток D; `origin='sim_data'`, `module` за R-15, `kind` за `x_mode`, пороги з `x_alarm/x_threshold`,
   `last_value/last_ts/status`, `maintenance_request_id = x_request_id`, `derived_from_id = x_source_id`);
   xml-id `factory3d_telemetry.sig_<slug>` (той самий slug, що `factory3d.sig_<slug>`). Очікувано:
   `signals_migrated: 196`, з них `alarm: 1` (RV-05), з заявкою: 2.
3. 8 сигналів `drain` → `equipment/<code>/state` (`kind='state'`, `last_text` = `charging`, якщо `x_charging`,
   інакше `busy`) — входять у 29 нових (вони в data, хук лише ставить `last_text`). Якщо встановлено
   iot_sim 19.0.2.0.0 (`'f3d.sim.signal' in env`): для всіх 225 кодів моєї зони — `_f3d_import_sim_catalog`
   (CT-11) доповнює `address`/`sim_params` з каталогу, не змінюючи `last_*`; інакше адреси — з data модуля
   (Додаток C SPEC, ті самі значення).
3а. ТО за лічильником (SPEC §5.3 крок 3а, Додаток C.4, A-22): COMPRESSOR — `equipment/COMPRESSOR/hours`, інтервал
   2 000 год, останнє ТО 16 000; FL-*, TUGGER-1 — 1 000 год, останнє = `floor(мотогодини / 1000) · 1000`; наявні
   відкриті планові заявки (демо: id 3, 7–14) прив'язуються як `f3d_meter_request_id`, нових хук не створює.
   Очікувано: `meters: 9`, `meter_requests_linked: 9`.
4. `x_f3d_reading` → `f3d.reading` батчами по 5 000 через `execute_values` (`signal_id` за `x_signal_id` →
   `f3d.signal`, `ts = x_time`, `value = x_value`, `quality='good'`, `src='sim_data'`), дублікати `(signal_id,
   ts)` пропускаються. Очікувано: стільки, скільки в `x_f3d_reading` на момент установки (7 448 на 14.10 01:50,
   14 112 на 14.10 ≈07:30 UTC; ≤ 56 448 за повні 2 доби); потім `f3d.reading.hour` за цими показаннями (≈ 196 × 7 = 1 372 на 14.10).
5. `maintenance.request` з `x_request_id`: проставити `f3d_signal_id`, `f3d_origin='threshold'`,
   `f3d_value`, `f3d_threshold` (`f3d_equipment_code` — related); очікувано 2.
6. Рівень 0: `cron_iot_sim.active=False`; `UPDATE x_f3d_signal SET x_active=false`; `ir.ui.menu`
   `factory3d_iot_sim.menu_iot_root` → `active=False` (діти ховаються разом із батьком); `ir.ui.view`
   `factory3d_iot_sim.view_equipment_form_signals` → `active=False`; якщо є параметр
   `factory3d.iot_sim.level0_enabled` → `False` (емулятор більше не вмикає рівень 0, iot_sim FR-28);
   `maintenance.equipment.x_f3d_signal_ids` не чіпається (його приберуть разом із моделями, A-07).
7. Якщо `factory3d.telemetry.drop_level0 = True` (за замовчуванням `False`): `ir.ui.view` рівня 0 `unlink`,
   `drop_manual_fields(env, 'maintenance.equipment', ['x_f3d_signal_ids'])` (CB-11), `ir.model`
   `x_f3d_reading`, `x_f3d_signal` `unlink` — лише після звірки кількостей кроку 8.
8. Звірка: `count(f3d.signal origin=sim_data) == count(x_f3d_signal)`; для кожного — `last_value == x_value`;
   `count(f3d.reading src=sim_data) == count(x_f3d_reading)`; розбіжності → `mismatches`, стан `partial`,
   рівень 0 **не** вимикається (крок 6 відкочується в межах транзакції через повторний `write`).
9. Звіт у `factory3d.telemetry.level0_migrated` (JSON: лічильники, `ts`, `state ∈ {skipped, partial, done}`).

Чиста база без рівня 0: кроки 2–8 `skipped`, 29 нових сигналів (`origin='catalog'`) і 7 джерел стенда з data; ТО за
лічильником — 0.

`uninstall_hook`: крони модуля `active=False`; параметри `factory3d.telemetry.*` видалити; якщо є
`x_f3d_signal` і крон `cron_iot_sim` — `x_active=True` повернути всім, крон не вмикати (адміністратор
вирішує; пишемо WARNING); меню/представлення рівня 0 → `active=True`; `maintenance.request.f3d_*`
зникають разом із полями; `f3d.reading` видаляються Odoo разом із моделлю (журнал — технічні дані, як у
iot_sim A-11); заявки ТО лишаються.

## 3. Налаштування системи

| Об'єкт | Параметр | Значення для тестового сервера | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `factory3d.telemetry.read_enabled` | `True` (тест) / `False` (прод одразу після встановлення) | стоп-кран прийому показань; умовчання з `factory3d.base.environment` (CB-10) |
| `ir.config_parameter` | `factory3d.telemetry.write_enabled` | `False` | стоп-кран команд на пристрої |
| `ir.config_parameter` | `factory3d.telemetry.keep_days` | `30` | ротація `f3d.reading` |
| `ir.config_parameter` | `factory3d.telemetry.keep_hours_days` | `400` | ротація `f3d.reading.hour` |
| `ir.config_parameter` | `factory3d.telemetry.default_store_period_s` | `300` | умовчання `store_period_s` нового сигналу |
| `ir.config_parameter` | `factory3d.telemetry.stale_periods` | `3` | `stale` після `3 × period_s` |
| `ir.config_parameter` | `factory3d.telemetry.stale_min_s` | `60` | нижня межа вікна `stale` |
| `ir.config_parameter` | `factory3d.telemetry.bus_min_interval_s` | `10` | дебаунс шини на сигнал |
| `ir.config_parameter` | `factory3d.telemetry.realarm_cooldown_s` | `3600` | пауза перед повторною заявкою після закриття |
| `ir.config_parameter` | `factory3d.telemetry.push_max_readings` | `2000` | ліміт пакета |
| `ir.config_parameter` | `factory3d.telemetry.push_rate_per_min` | `60` | ліміт частоти на колектор |
| `ir.config_parameter` | `factory3d.telemetry.default_team_id` | id команди «Служба головного механіка» | команда заявок, якщо в обладнання немає своєї |
| `ir.config_parameter` | `factory3d.telemetry.meter_lead_pct` | `5` | за скільки % інтервалу створювати планову заявку |
| `ir.config_parameter` | `factory3d.telemetry.drop_level0` | `False` | видаляти `x_`-моделі при міграції (інакше — iot_sim 19.0.3.0.0) |
| `ir.config_parameter` | `factory3d.telemetry.level0_migrated` | `{}` → звіт хука | стан міграції рівня 0 |
| `f3d.collector` | `COL-MAIN` | токен згенерувати майстром; `push_interval_s=5`, `push_max=1000`, `status_interval_s=60` | один колектор на стенді |
| `f3d.source` | 7: `MQTT-MOBILE`, `MB-U70-COMPRESSOR`, `MB-U84-IO5`, `MB-U90-AI1`, `MB-U96-RTD1`, `BAC-140-BOILER`, `HTTP-PUSH` | з data (SPEC Додаток C), `collector_id=COL-MAIN`, `read_enabled=True` | адреси контейнерів `iot-sim`, `mosquitto` |
| `ir.cron` | `cron_f3d_telemetry_stale` | 1 хв, активний | R-07 |
| `ir.cron` | `cron_f3d_telemetry_hour` | 10 хв, активний | R-09 (агрегати за закриті години) |
| `ir.cron` | `cron_f3d_telemetry_rotate` | щодня 02:40 (Київ) | R-10 |
| `ir.cron` | `cron_f3d_telemetry_commands_gc` | 10 хв | `queued/sent` старіші `expires_at` → `expired` |
| `ir.cron` | `factory3d_iot_sim.cron_iot_sim` (рівень 0) | **вимкнено хуком** | емулятор пише через колектор |
| compose `collector` env | `F3D_ODOO_URL=http://odoo19:8069`, `F3D_COLLECTOR_CODE=COL-MAIN`, `F3D_COLLECTOR_TOKEN=<з майстра>`, `F3D_CONFIG_POLL_S=60`, `F3D_PUSH_INTERVAL_S=5`, `F3D_PUSH_MAX=1000`, `F3D_STATUS_INTERVAL_S=60`, `F3D_BUFFER_DIR=/app/state`, `F3D_BUFFER_MAX_MB=200`, `F3D_WRITE_ENABLED=0`, `F3D_ALLOW_HOSTS=iot-sim,mosquitto`, `F3D_HTTP_PUSH_PORT=8080`, `F3D_HTTP_PUSH_TOKEN_LPR=<hex>`, `F3D_MQTT_PASSWORD=<пароль користувача collector у mosquitto>`, `F3D_METRICS_PORT=9108`, `F3D_LOG_LEVEL=INFO`, `F3D_LOG_JSON=1`, `F3D_TZ=Europe/Kyiv` | повний перелік — SPEC §8.2 | |
| compose мережі/порти | `collector` у `f3d_sim` (до емулятора/брокера) і `odoo_default` (до Odoo); порти 8080 (http_push) і 9108 (metrics) лише в мережі `f3d_sim`; на хост — нічого | | |
| mosquitto | користувач `collector` (subscribe `f3d/#`) | ACL у `services/iot_sim/mosquitto/acl` (iot_sim) | пароль у `F3D_MQTT_PASSWORD`, не в Odoo |
| `maintenance.team` | «Служба головного механіка» | існує в демо (id 2) | `default_team_id` |

## 4. Інструкція

**4.1 Зареєструвати колектор і запустити його** (адміністратор). 1) Завод 3D → Телеметрія → Колектори →
Створити: код `COL-MAIN`, назва; «Згенерувати токен» → скопіювати токен з вікна (показується один раз);
2) у `services/collector/.env`: `F3D_ODOO_URL`, `F3D_COLLECTOR_CODE=COL-MAIN`, `F3D_COLLECTOR_TOKEN=<токен>`,
`F3D_MQTT_PASSWORD`; 3) `docker compose -f docker-compose.collector.yml up -d collector`; 4) через ≤ 2 хв у
картці колектора: стан «онлайн», версія, час контакту; Огляд → джерела зелені.

**4.2 Підключити новий пристрій Modbus** (інженер АСУ). 1) Джерела → Створити: тип `Modbus TCP`,
колектор, параметри `{"host": "10.0.3.21", "port": 502, "unit": 1}` (хост має бути в `F3D_ALLOW_HOSTS`
колектора — інакше джерело стане `error` з текстом «хост не в allow-list»); 2) Сигнали → Створити або
відкрити існуючий (`equipment/COMPRESSOR/pressure_bar`): джерело, адреса `{"fc": 3, "addr": 3001, "type":
"u16", "scale": 0.001}`, період 10 с; «Перевірити адресу» показує помилки схеми; 3) зберегти — колектор
перечитає конфігурацію протягом 60 с; 4) на формі сигналу «Останнє значення/час» оновлюються, графік росте.

**4.3 Налаштувати поріг і перевірити заявку** (інженер АСУ, механік). На сигналі
`ventilation/units/RV-05/filter_dp_pa`: «Тривога, вище» = 250, гістерезис 10, мін. тривалість 0, заголовок
заявки «Заміна фільтрів: перепад тиску {value} Па при нормі до {threshold}». На стенді: пульт емулятора →
сценарій `filter_clogged` (`device=RV-05`, `value=285` — лише `value`, X-58) — після прив'язки RV-05 модулем bms або за SPEC ТК-06. Через ≤ 30 с сигнал червоний, у Обслуговування →
Заявки — «Заміна фільтрів: перепад тиску 285 Па при нормі до 250» (команда «Служба головного механіка»).
Закрити заявку («Repaired») → на сигналі заявка зникає, стан перераховується; емулятор скидає перепад до
120 Па (його FR-06) → «норма».

**4.4 ТО за лічильником** (механік). Обслуговування → Обладнання → COMPRESSOR → вкладка «Сигнали» → група
«ТО за лічильником»: сигнал `equipment/COMPRESSOR/hours`, інтервал 2 000 год, останнє ТО 16 000 год
(дата). «Наступне» = 18 000, «Залишилось» = 18 000 − поточні мотогодини. За 100 год до межі з'явиться
заявка «ТО за лічильником: COMPRESSOR — 18 000 год (зараз 17 900)». Після закриття — «Останнє ТО» =
показник на момент закриття.

**4.5 Стоп-крани на проді** (адміністратор). Налаштування → Завод 3D → Телеметрія: «Приймати показання»
вимкнено → колектор отримує `423`, буферизує (до 200 МБ), індикатор у картці колектора «Odoo відхиляє»;
«Дозволяти команди» вимкнено → кнопка «Записати в пристрій» неактивна, черга команд не віддається.
Копія проду для тестів — `neutralize.sql` модуля (разом із base/viewer/iot_sim).

**4.6 Переглянути журнал і графік** (будь-хто з `group_f3d_user`). Завод 3D → Телеметрія → Показання: за
замовчуванням графік-лінія за останні 2 доби, групування за годинами; фільтр «Обладнання», «Сигнал»;
перемикач «Список». Для довших періодів — «Годинні агрегати» (зведена: min/avg/max за днями).

## 5. Ризики й відкриті питання

### 5.1 Відкриті питання (ті самі номери — у SPEC §15)

| ID | Питання | Кому | Рекомендована відповідь | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | Сирі ряди 1 с (стани верстатів, струми) — TimescaleDB поруч із колектором (D-11) уже у фазі 2 чи після появи machine_connect? | менеджер | після: у фазі 2 `f3d.reading` зі `store_period_s` достатньо (§2.7); ввести TimescaleDB, коли `f3d_reading` > 20 М рядків або потрібні ряди 1 с | буфер колектора зберігає сирі показання лише до доставки; TimescaleDB — окремий сервіс `timeseries` (compose, профіль `ts`) з таблицею `reading(signal_code, ts, value)` і hypertable; плагін ядра `sink_timescale` (інтерфейс `Sink`, SPEC §8.3.6) — зарезервовано, не реалізується |
| Q-02 | Чи має емулятор у фазі 1 (без колектора) писати напряму в `POST /f3d/telemetry/push` (щоб рівень 0 можна було вимкнути раніше)? | менеджер, автор iot_sim | ні: емулятор говорить лише протоколами (D-01); до появи колектора — рівень 0 | крон рівня 0 вимикається лише хуком телеметрії, коли колектор уже є |
| Q-03 | Закрито рішенням менеджера 14.10 (`bacnet_ip` — мій): джерело `BAC-140-BOILER` і адреси `equipment/BOILER/supply_c`, `/silo_fill` створює цей модуль (Додаток C SPEC); нові `equipment/BOILER/return_c`, `/state` (Додаток A iot_sim № 362–363, споживач bms) — створює bms через CT-11 | — | — | — |
| Q-04 | **Закрито X-42** (рішення менеджера, D-20). Було: нотація Modbus-адрес у Додатку A iot_sim змішана (PM5560/Elektronikon 1-based, ADAM «40001», Huawei — уже PDU). Рішення: адреси — PDU за документом вендора, без загального «номер − 1»; правило за вендором (як energy R-01); у каталозі iot_sim — явна PDU-нотація `u<unit> fc<n> pdu<addr>` | — | — | парсер R-24 бере PDU-нотацію як є, інакше — правило за вендором за unit iot_sim §8.4.1; позначка `[notation?]` скасована; `address.addr` — PDU; звірка в ТК-03 |
| Q-05 | Карта Elektronikon Mk5 (Atlas Copco видає за серійним номером) | замовник / Atlas Copco | запросити; публічно описано лише Mk IV через ComBox-S (industrialmonitordirect.com, переглянуто 14.10.2026) | адреси = макет iot_sim §8.9.3 (ПРИПУЩЕННЯ); зміна — лише в `address` сигналів |
| Q-06 | Інтервали ТО за лічильником: компресор (GA 37 VSD+: 4 000 год за сервіс-планом Atlas Copco — ПРИПУЩЕННЯ), навантажувачі (Jungheinrich EFG 216: 1 000 год / 12 міс — ПРИПУЩЕННЯ), тягач | головний механік | затвердити з сервісними книжками | у data: COMPRESSOR 2 000 год (щоб відтворити MR/00033 «ТО на 18 000»), FL-* 1 000 год, TUGGER-1 1 000 год |
| Q-07 | Пороги для техніки: попередження 25 %, тривога 15 % заряду (емулятор іде на зарядку при 20 %) — чи потрібна заявка ТО взагалі, чи лише стан? | головний механік | warn 25 без заявки, alarm 15 із заявкою (означає несправність зарядки) | так і зроблено в data |
| Q-08 | **Закрито X-28**: координати техніки `equipment/<code>/x`, `/y` у 3D — фаза 4 (рух техніки, контракт viewer); до того — зберігати з `viewer_visible=False` | — | — | сигнали створюються (`store_period_s=60`, `viewer_visible=False`), провайдер їх не віддає |
| Q-09 | Хто є «джерелом істини» для `energy/consumers/<X>/kwh_shift`: лічильник PM5560 (energy) чи інтеграл `p_now` у телеметрії? | автор energy | лічильник; `derived_from_id` з рівня 0 — лише довідка | сигнали `energy/*` чекають energy |
| Q-10 | Частота опитування лічильників і термін зберігання сирих даних (каркас §9 п. 6) | замовник | 10 с / 30 днів сирих, 400 днів агрегатів | параметри §3 |
| Q-11 | Сповіщення механіку про `stale` джерела (пристрій «мовчить» > 10 хв) — активність у чаттері джерела чи лише дашборд? | головний механік | активність `mail.activity` на джерелі для `maintenance_team_id.member_ids` після `stale_notify_min` (10) | лише дашборд і стан; параметр зарезервовано (`stale_notify_min=0` — вимкнено) |
| Q-12 | **Закрито X-21**: каркас `docs/ARCHITECTURE.md` v0.2 містить D-13 (рівень 0 і пульт iot_sim), D-14 (рядки UI українською в коді) і D-16 (`bacnet_ip` у telemetry; рядок §6.5 оновлено) | — | — | діємо за D-13, D-14, D-16 і §2.8 цього документа |
| Q-13 | Axis LPV шле POST без автентифікації (iot_sim §8.13.2): обмежувати приймач `/f3d/lpr` за IP камер (`allow_ips`) чи вимагати секретний шлях `/f3d/lpr/<secret>`? | адміністратор мережі, автор yard | обидва: allow-list IP + секретний суфікс шляху, який камера має в URL | на стенді — allow-list `iot-sim`; суфікс підтримується (`F3D_HTTP_PUSH_SECRET_LPR`), порожній = вимкнено |
| Q-14 | **Закрито X-58**: параметр сценарію `filter_clogged` — `value` (схема iot_sim §9.3 — джерело істини; приклад §7.2 виправляє iot_sim) | — | — | SPEC ТК-05/ТК-06 передають лише `value` |
| Q-15 | **Закрито X-48**: час події LPR — `capture_timestamp` (епоха мс UTC); поза вікном (`ts_future`/`ts_too_old`) — час прийому (`f3d.reading.received_at` — `fields.Datetime.now()` у `_f3d_ingest`; X-83); приклад iot_sim §8.13.2 виправляє iot_sim (`capture_timestamp = sim_now`, `plateList` — назва списку), yard R-07 п. 4 — той самий порядок | — | — | `ts_path=$.capture_timestamp`; значення поза вікном → час прийому з `q='uncertain'` (SPEC R-22) |
| Q-16 | Чи є Docker у CI (тести колектора з mosquitto, `bacpypes3` на UDP, стенд)? | менеджер / DevOps | так: раннер із Docker; `pytest -m broker` у CI | `-m broker` пропускаються без `F3D_TEST_MQTT`/Docker; MQTT покривають фейковий клієнт (AC-79) і ТК-04 |
| Q-17 | Де розгортається стенд ТК (емулятор + колектор + Odoo з копією демо): на timur-o19demo поруч з Odoo (`/opt/timur-o19`) чи на окремому хості? | менеджер, адміністратор сервера | на timur-o19demo, compose-профіль `dev`, окрема база-копія `odoo_f3d_tel` | ТК виконуються локально: compose iot_sim + колектор + контейнер Odoo 19 з дампом копії |

### 5.2 Ризики

| Ризик | Вплив | Пом'якшення |
|---|---|---|
| Карти Modbus вендорів (Elektronikon, ADAM-канали) на заводі інші, ніж в емуляторі | після переходу на залізо значення сміттєві | адреси лише в даних (`address`), не в коді; ТК-11 «звірка з паспортом» перед увімкненням `read_enabled` джерела; `quality='bad'` при виході за фізичний діапазон (`range` в адресі) |
| Два джерела значень для одного сигналу (рівень 0 і колектор) | стрибки, подвійні заявки | хук вимикає крон рівня 0 і ставить `factory3d.iot_sim.level0_enabled=False`; `x_active=False`; AC-53, AC-58 |
| Зростання `f3d_reading` при малих `store_period_s` | гальмування графіків, ротації | умовчання 300 с, поле на сигналі з підказкою обсягу, ротація батчами, індекси §2.7, Q-01 |
| Відмова Odoo на годину — буфер колектора переповнюється | втрата історії | SQLite WAL до 200 МБ (≈ 4 М показань ≈ 3 доби при 12/с); найстаріші видаляються з лічильником у `/metrics` і `status.buffer_dropped` |
| Паралельні push двох воркерів Odoo для одного сигналу | гонка `last_value` | `UPDATE … WHERE id=%s AND (last_ts IS NULL OR last_ts < %s)` — старіше показання не перезапише новіше (R-17); унікальний індекс на показаннях |
| Заявка закрита без ремонту — поріг далі перевищений | лавина заявок | `realarm_cooldown_s` (1 год) + чаттер сигналу «тривога триває, заявку закрито» (R-06) |
| `pymodbus` 3.10+ перейменував `slave=` → `device_id=` | збірка ламається при оновленні | закріплено `pymodbus==3.9.2` (як в емуляторі); адаптер `_read()` в одному місці |
| Провайдер viewer M-01h (x_) і мій (95) обидва пишуть ті самі шляхи | подвійна робота, застарілі `meta.iot` | `x_active=False` після міграції → M-01h нічого не читає; мій іде пізніше й перекриває |

## 6. План сборки агентами

Межі файлів жорсткі; спільні файли (`__init__.py`, `__manifest__.py`, `security/ir.model.access.csv`,
`views/menus.xml`, `services/collector/collector/core/types.py`) належать W0 і правляться через нього.

| Воркер | Файли | Здає | Залежить від |
|---|---|---|---|
| W0 каркас | Odoo: `__manifest__.py`, `__init__.py`, `models/__init__.py`, `security/ir.model.access.csv`, `security/security.xml`, `data/ir_config_parameter.xml`, `data/ir_cron.xml`, `data/neutralize.sql`, `views/menus.xml`, `tests/__init__.py`, `tests/common.py`, `README.md`, `CHANGELOG.md`; сервіс: `services/collector/pyproject.toml`, `requirements.txt`, `Dockerfile`, `docker-compose.collector.yml`, `collector/__init__.py`, `collector/core/types.py`, `collector/plugins/base.py`, `tests/conftest.py` | модуль встановлюється порожнім; меню «Телеметрія»; параметри; типи CT-02 зафіксовані | SPEC §0, §1, §3 (меню), §4, §5.1, §8.3 |
| W1 моделі й інгест | `models/f3d_collector.py`, `models/f3d_source.py`, `models/f3d_signal.py`, `models/f3d_reading.py`, `models/f3d_reading_hour.py`, `models/f3d_command.py`, `tools/address.py`, `tools/thresholds.py`, `tools/titles.py`, `tools/ingest.py`, `wizard/collector_token_wizard.py`, `wizard/collector_token_wizard_views.xml`, `views/f3d_collector_views.xml`, `views/f3d_source_views.xml`, `views/f3d_signal_views.xml`, `views/f3d_reading_views.xml`, `views/f3d_reading_hour_views.xml`, `views/f3d_command_views.xml`, `tests/test_collector.py`, `tests/test_source.py`, `tests/test_signal.py`, `tests/test_readings.py`, `tests/test_thresholds.py` | M-01…M-06, M-12; CT-10, CT-12; R-01…R-04, R-07…R-10, R-13, R-14, R-16, R-17 (без HTTP), R-25, R-26; AC-01…AC-26, AC-91, AC-92, AC-98, AC-99, AC-103 (частини AC-24/AC-25 про заявки — зелені після W2) | W0 |
| W2 ТО й стандартні моделі | `models/maintenance_equipment.py`, `models/maintenance_request.py`, `models/res_config_settings.py`, `views/maintenance_equipment_views.xml`, `views/maintenance_request_views.xml`, `views/res_config_settings_views.xml`, `tests/test_requests.py`, `tests/test_meter.py` | M-07…M-09; R-05, R-06, R-11; AC-27…AC-34 | W1 |
| W3 API, події, міст переглядача | `controllers/__init__.py`, `controllers/telemetry.py`, `models/push_handler.py`, `models/f3d_push_event.py`, `views/f3d_push_event_views.xml`, `tests/test_api.py` (HttpCase), `tests/test_commands.py`, `tests/test_push_handler.py`; модуль `odoo_addons/factory3d_telemetry_viewer/*` (M-10, `tests/test_viewer_provider.py`) | API-01…API-07, M-10, M-11, M-13; R-12, R-17 (HTTP, п. 0), R-18, R-22; AC-35…AC-50, AC-68…AC-70, AC-93, AC-94, AC-96, AC-102 | W1, W2 |
| W4 міграція, дані, права | `hooks.py`, `data/f3d_source_data.xml`, `data/signal_catalog.csv`, `data/f3d_actions.xml`, `tools/sim_catalog.py`, `tools/gen_signal_data.py`, `tests/test_migration.py`, `tests/test_sim_catalog.py`, `tests/test_security.py`, `tests/test_views.py`, `tests/test_hooks.py` | §5.2–§5.6, R-15, R-24, CT-11; Додатки B–D; AC-51…AC-57, AC-59…AC-67; `neutralize.sql` перевірений | W1, W2 |
| W5 колектор — ядро | `collector/core/{config,registry,scheduler,buffer,odoo_client,commands,allowlist,metrics,logging_conf,app}.py`, `collector/util/{jsonpath,codec,timeutil}.py`, `collector/__main__.py` (фікстури `tests/conftest.py` SPEC §13.0.2 — через W0), `tests/unit/test_{config,scheduler,buffer,odoo_client,commands,registry,codec,jsonpath,allowlist,logging,cli,metrics}.py` | §8.1–§8.4, §8.9, §8.10; R-02 (ядро, `apply_signal_scale`), R-18 (колектор, `call()`), R-19; AC-71…AC-77, AC-82, AC-83, AC-95, AC-101 | W0 |
| W6 колектор — плагіни | `collector/plugins/{modbus_tcp,mqtt,http_push,bacnet_ip}.py`, `collector/plugins/schemas/*.json`, `tests/unit/test_plugin_{modbus,mqtt,http_push,bacnet}.py` (фейкові сервери: `pymodbus` server, фейковий paho-клієнт і mosquitto для `-m broker`, aiohttp test client, `bacpypes3` тестовий пристрій) | §8.5–§8.8; R-20…R-23; AC-78…AC-81, AC-97, AC-100, AC-101 (частини плагінів: масштаб адреси `mqtt`/`bacnet_ip`) | W5 |
| W7 стенд і ТК | `services/collector/tests/stand/*` (pytest -m stand проти compose iot_sim + collector + Odoo), `docs/modules/factory3d_telemetry/DEPLOY_TEST.md`, `TEST_REPORT.md` | ТК-01…ТК-16, ТБ-01…ТБ-10, ТП-01…ТП-07, DEPLOY_TEST (SPEC §13.2–§13.5); AC-58, AC-84…AC-90 | W3, W4, W6 |

Порядок злиття: W0 → (W1 ‖ W5) → (W2 ‖ W6) → W3 → W4 → W7. Кожен воркер здає зелені тести своїх файлів
(`odoo-bin -d test --test-tags /factory3d_telemetry:<TestClass> --stop-after-init`; `pytest services/collector
-m "not stand"`) і не чіпає чужих тестів. Після W4 — повний прогін `--test-tags f3d` на чистій базі й на копії
демо; після W7 — стенд.

## 7. Рішення автора (A-xx)

| ID | Рішення | Обґрунтування | Що змінює відносно каркаса |
|---|---|---|---|
| A-01 | `f3d.signal.address` — JSON зі схемою на тип джерела; Modbus-адреси в полі `addr` — **PDU (0-based)**, вендорська нотація — довідково в `doc` | емулятор і документи вендорів використовують три різні нотації (Q-04); на дроті завжди PDU; колектор не повинен вгадувати | уточнює §6.4 («регістр+тип») |
| A-02 | Токен колектора — на записі `f3d.collector` (хеш sha256), не в `ir.config_parameter` | колекторів може бути кілька (цех, двір, енергетика); відкликання одного не зачіпає інших; `neutralize.sql` стирає всі хеші | відхилення від §5 «токени в `ir.config_parameter`»; вимога «лише `group_f3d_admin`, не в логах» дотримана |
| A-03 | Пороги лишаються полями `f3d.signal` (без `f3d.threshold.rule`); додано `*_on` прапори, `hysteresis`, `min_duration_s`, `alarm_states`, `alarm_title`, `create_request` | макет має рівно один поріг на сигнал; окрема модель додала б join у гарячому шляху push і зайвий екран; Float в Odoo не відрізняє 0 від «не задано», тому прапори | розширює §6.4 |
| A-04 | Показання зберігаються не всі: `store_period_s` на сигналі (умовчання 300 с) + завжди при зміні `status`/тексту стану; `last_value` оновлюється кожним показанням | обсяги §2.7; графік за 2 доби (як у макеті, 10 хв) потребує ≤ 300 с; D-11 | уточнює §6.4 «показання (ts, signal, value, quality)» |
| A-05 | Оцінка порогів і створення заявок — в Odoo під час `push`, не в колекторі | єдине місце правил для всіх модулів (CT-05); колектор без бізнес-логіки; емулятор/стенд не потребують правил | — |
| A-06 | `kind='state'`: значення — `text` (рядок) + числовий індекс у `states`; тривога за `alarm_states` | §6.4 має `alarm_state`, але стан не число; індекс дає графіки/агрегати | уточнює §6.4 |
| A-07 | Рівень 0 після міграції **вимикається й архівується**, а не видаляється; видалення — iot_sim 19.0.3.0.0 або параметр `drop_level0` | data-файли `x_`-моделей належать маніфесту iot_sim; видалення з іншого модуля ламає його оновлення (iot_sim ARCH §2.8 п. 4) | узгоджено з iot_sim A-09 |
| A-08 | Команди на пристрої — модель `f3d.command` + API-06/07 (колектор забирає чергу), а не синхронний виклик | плагін `write()` живе в колекторі; Odoo не ходить у мережу цеху (§4); журнал команд — вимога безпеки | доповнює §6.5 («`write` лише при `write_enabled`») |
| A-09 | Приймач `http_push` у колекторі ретранслює події в Odoo (API-05) і Odoo диспетчеризує через хук `f3d.push.handler` | модулі-власники (yard) не повинні писати контролерів для пристроїв; токени маршрутів — в env колектора | уточнює §6.5 (`http_push`) |
| A-10 | Поля `origin` (`sim_data/catalog/manual/module`; `module` — сигнали, створені модулями з власних даних, `catalog` — лише рядки каталогу iot_sim; X-16) і `module` (власник) на сигналі; `module` виводиться з префікса шляху (CT-09) | 196 сигналів належать 5 модулям; без мітки неможливо розподілити прив'язку джерел і представлення | доповнює §6.4 |
| A-11 | `sim_mode`/`sim_params` зберігають параметри поведінки макета (`x_mode`, `x_nominal`, `x_noise`, `x_rate`, `x_limit`) як довідку | емулятор і тести звіряють ряди з макетом (iot_sim R-00); нічого в проді їх не читає | — |
| A-12 | Моделі `f3d.collector`, `f3d.source`, `f3d.signal` з чаттером (`mail.thread`), `f3d.reading` без `_log_access` | журнал змін порогів/адрес — вимога експлуатації; показання — обсяг | — |
| A-13 | Колектор: один HTTP-клієнт/сервер `aiohttp` (замість `httpx` + `fastapi` емулятора) | один пакет на обидві ролі (клієнт до Odoo і приймач `http_push`); менший образ | — |
| A-14 | Джерело = пристрій (host:port:unit для Modbus), не TCP-ендпоінт; плагін пулить з'єднання за `host:port` | стан «офлайн» потрібен на рівні пристрою (компресор vs лічильник води на одному шлюзі) | уточнює §6.4 («адреса/порт/параметри») |
| A-15 | Меню «Телеметрія» лише під «Завод 3D» (CB-09, sequence 30); меню рівня 0 під «Обслуговування» ховаються | один вхід; механік потрапляє до сигналів через картку обладнання | — |
| A-16 | 29 нових сигналів у data з `origin='catalog'` — рівно рядки Додатка A iot_sim зі споживачем `telemetry` (№ 335–365): `equipment/<техніка>/state`, `/x`, `/y` ×8, `equipment/COMPRESSOR/state`, `/temp_c`, `equipment/DUST-1/state` (складений стан з DI0/DI1), `infra/water/m3_total`, `/flow_m3h` (похідна R-08) | каталог емулятора — джерело істини для кодів; `x/y` — з `viewer_visible=False` (Q-08) | — |
| A-17 | Плагін `bacnet_ip` у ядрі (рішення менеджера 14.10): один BACnet-застосунок на колектор, `Who-Is` для резолву адреси пристрою через роутер (мережа 2 емулятора), `ReadPropertyMultiple` для опитування, `SubscribeCOV` (lifetime 300 с, поновлення на 2/3) для сигналів із `mode='cov'`, запис `WriteProperty` з пріоритетом 8 лише при `write_enabled`; для джерел із `params.read_only=true` (FACP-1) — запис неможливий у коді, а плагін ініціює лише Who-Is/ReadProperty/ReadPropertyMultiple (`SubscribeCOV` теж ні — `cov` діє як `poll`; X-05); `UnconfirmedEventNotification` ретранслюється в маршрут `bacnet_event` (A-23) | один плагін обслуговує bms і fire_safety; правило D-07 закріплене в коді, а не лише в даних | відповідає D-16 і §6.5 каркаса v0.2 |
| A-18 | Імпорт каталогу емулятора (CT-11, R-24): текстова адреса Додатка A розбирається регулярними виразами в JSON `address` (Modbus — PDU-нотація каталогу або правило за вендором, X-42); нерозібране не блокує імпорт, а повертається у `unparsed` | каталог має сотні рядків у людській нотації (кількість веде iot_sim, X-34); без парсера кожен модуль переписував би адреси вручну | — |
| A-19 | Поле `viewer_visible` на сигналі (default `True`): провайдер пропускає невидимі (x/y техніки, службові стани) | контракт viewer A.10 має фіксований набір ключів | — |
| A-20 | Провайдер переглядача — в окремому міст-модулі `factory3d_telemetry_viewer` (`depends: factory3d_telemetry, factory3d_viewer`, `auto_install=True`), а не умовною реєстрацією в ядрі | `_inherit = "f3d.viewer.provider"` неможливий без залежності від viewer; умовний клас ламає реєстр, коли viewer установлюють пізніше; `auto_install` ставить міст сам | уточнює §6.7 каркаса (viewer optional) |
| A-21 | Числа в заголовках заявок — `fmt_num(x, decimals)`: округлення до `decimals`, десяткова кома, зайві нулі дробової частини відкидаються, групи тисяч через пробіл при \|x\| ≥ 1 000; `{threshold}` — з тим самим `decimals` | приклади макета («285 Па при нормі до 250», «14,2 % при нормі від 15», «18 000 год») інакше суперечать один одному; тестам потрібні детерміновані рядки | уточнює §6.8 каркаса |
| A-22 | Хук налаштовує ТО за лічильником для COMPRESSOR і техніки (SPEC Додаток C.4) і прив'язує наявні відкриті планові заявки обладнання як `f3d_meter_request_id` | у демо вже є «ТО на 18 000 мотогодин» (COMPRESSOR) і «Планове ТО» на FL-*/TUGGER-1 (id 3, 7–14); без прив'язки R-11 створив би дублікати | — |
| A-23 | Ретрансляція подій BACnet (X-05): плагін `bacnet_ip` передає `UnconfirmedEventNotification` у маршрут `bacnet_event` за схемою fire_safety API-01; вмикає параметр джерела `events` з умовчанням = `read_only` (пожежна панель — так, вентустановки bms — ні, доки bms не ввімкне явно); `ts` події — час прийому колектором; `from_state` для `change-of-life-safety` — з кешу останнього стану об'єкта | fire_safety очікує події лише від панелі; для bms вони — шум у `f3d.push.event`; годинник панелі не синхронізований, а сповіщення `change-of-life-safety` не містить попереднього стану | доповнює §6.5 каркаса (`bacnet_ip`) |
| A-24 | Корисне навантаження команд (X-03, CR-01): `f3d.command.payload` — об'єкт JSON ≤ 64 КБ, результат `call()` — `result_data` (той самий ліміт); невалідні `data` в API-07 → `400` для всього запиту (колектор перевіряє `data` до відправки й перетворює невалідне на `failed`) | однозначна межа для JobOrder і завдань порталу; невалідні дані можуть прийти лише від несправного колектора | доповнює A-08 |
| A-25 | `delta` годинного агрегату лічильника (X-07): від `v_last` найближчої попередньої години з даними (не лише `h−1`), для першої години ряду і при зменшенні (скидання/ролловер) — `v_last − v_first` години | сума `delta` за період дорівнює приросту лічильника навіть за пропусків годин; добові лічильники (`cycles_today`) не дають від'ємних `delta` | уточнює §6.4 (агрегати) |
