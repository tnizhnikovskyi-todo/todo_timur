# factory3d_iot_sim — технічне рішення

Версія 0.3 · 14.10.2026 (0.2 — 14.10.2026, 0.1 — 13.10.2026) · автор: агент-архітектор модуля `factory3d_iot_sim` (хвиля 1) · статус: **чернетка — на погодження менеджера**.

Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-75 (§3: env і мережі `genset_relay` за td_genset §8.5 CI-02), X-76 (каталог 1 166: `equipment/GANTRY-1/stacks` і `equipment/CUTOPT/cmd` — `protocol=none` machine_connect; 1 015 веде емулятор, 151 — модулі-власники; 274 пристрої з пасивним `CUTOPT` — FR-02, FR-26, §2.7, §2.8), X-79 (FR-12: LSP id за fire R-23/A-09) (v0.3).

Зміни (v0.2): 14.10.2026 — правки за `docs/CONSISTENCY.md` v0.3: X-15 (`f3d_code`/`f3d_truck`/`f3d_plate` пакета), X-31 (меню під «Завод 3D», sequence 90), X-34/X-61 (каталог 1 165: +503 рядки з додатків модулів, +9 споживачів u51–59), X-35 (149 обчислюваних рядків не веде емулятор), X-37 (Cerberus — BV/PIV, Q-03), X-41 (ATyS p — Annexe III, Q-07 закрито), X-42/X-43/X-72 (Modbus — PDU за вендором, ADAM `little`), X-50 (BioStar 4102/4867, Q-13), X-56 (`read_enabled` за `factory3d.base.environment`), X-58 (`value` в інструкції 4.3), X-59 (CI-01 / API-F, Q-15 закрито), X-67 (навантаження генератора в острові); Q-09 закрито за X-53. Деталі решти рядків реєстру (X-36, X-38…X-40, X-47…X-49, X-51, X-54, X-60, X-64, X-65) — у SPEC v0.2.
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-01, Q-02, Q-03, Q-04, Q-05, Q-06, Q-08, Q-10, Q-11, Q-12, Q-13.
Зміни: 14.10.2026 — закрито рішеннями менеджера: Q-14.

Модуль складається з двох частин: **сервіс емулятора `services/iot_sim`** (Python 3.12, поза Odoo; говорить із колектором реальними протоколами P-01…P-12) і **Odoo-модуль `factory3d_iot_sim` 19.0.2.0.0** (пульт сценаріїв, реєстр пристроїв, експорт конфігурації емулятору, «рівень 0» — успадкований data-модуль). Специфікація для розробника й тестувальника — `SPEC.md` поруч; протокольні карти — її §8 (додатки P-01…P-12), каталог сигналів — її Додаток A.

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора) |
|---|---|---|
| ТР | Протокольна матриця §6.6 каркаса, цей документ §1 | 16 |
| Архітектура | `ARCHITECTURE.md`, `SPEC.md` з додатками P-01…P-12 і каталогом сигналів | 40 |
| Розробка | сервіс `services/iot_sim` (ядро, 11 протокольних серверів, REST, сценарії, compose) — 180; Odoo-модуль (пульт, API, міграція) — 48 | 228 |
| Тестування | юніт-тести моделей і протоколів, ТК-01…ТК-17, безпека, продуктивність, DEPLOY_TEST | 72 |
| Інструкція | §4 цього документа + README сервісу | 8 |
| **Разом** | | **364** |

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що є в макеті

Джерело істини для поведінки заводу — макет; усе нижче має відтворити емулятор.

| Джерело | Що беремо | Де використано |
|---|---|---|
| `odoo_addons/factory3d_iot_sim/data/actions.xml`, `action_iot_tick` | 9 режимів поведінки датчиків: `noise`, `machine`, `drain`, `hours`, `energy`, `counter`, `drift`, `level`, `solar`; формули з константами (0,3 — тяга до номіналу, ×4 — швидкість зарядки, 95 % — повний заряд, 1/60 — мотогодини за хвилину, 10 хв — крок журналу, 2 доби — ротація); поріг → `x_state='тривога'` і `maintenance.request` (`corrective`, одна відкрита заявка на сигнал); закриття заявки → `drift` скидається до номіналу | SPEC §9 R-01…R-11 (формули перенесено один до одного, час — безперервний) |
| `data/models.xml` | `x_f3d_signal` (21 поле), `x_f3d_reading`, `maintenance.equipment.x_f3d_signal_ids` | «рівень 0» (§2.8), джерело міграції для `factory3d_telemetry` |
| `plant/odoo_flows.py:signal_specs` | 196 сигналів: код-шлях, обладнання, одиниця, номінал, шум, швидкість, межа, поріг, джерело (`source`) | SPEC Додаток A (рядки 1–196 «макет») |
| `plant/odoo_pull.py:sync_signals`, `data["meta"]["iot"]` | як переглядач адресує сигнали: `x_code` = шлях у даних (`energy/consumers/SAW-1/p_now`), `%` → частка, `drain` + `x_charging` → `state=charging/busy`, `meta.iot = {source, signals, alarms, updated}` | конвенція імен §5 каркаса; емулятор віддає ті самі коди в `GET /sim/v1/signals` |
| `viewer/index.html:1903` | рядок «Дані: імітація IoT · HH:MM» у картці об'єкта з `meta.iot.updated` | переглядач не змінюється |
| `plant/odoo_demo.py` | `STATUS` верстатів (work/idle/stop; `CNC-2` — stop, MR/00031), простої (`losses`), OEE, черга завдань, 32 МО WH/MO/00231–00262, маршрути A–D/F1–F3, 6 фур біля воріт (`TRUCK-IN-1..3`, `TRUCK-OUT-1..3`), розклад приймань (`WH/IN/00128` 09:30 … `WH/IN/00134` завтра 09:00) і відвантажень, `docks`, `employees` (28 операторів + 7 комірників), `NOW = 2026-10-12 10:30` | «світ» режиму `scenario` (SPEC §9 R-14…R-19, R-28, R-29) |
| `plant/energy.py` | `PROFILE` (коефіцієнт завантаження, cos φ за типом), `IDLE_K`, `IDLE_DEFAULT=0,12`, `STOP_K=0,03`, `UTILITIES`, `day_profile` (ніч/зміна/обід), `TARIFF=8,4`, трансформатори `temp_c = 38 + 60·S/Sн`, секції, компенсація до cos φ 0,97, `events` | R-01…R-04, R-13; карта P-05 (вводи Q1/Q2, фідери QF-*, споживачі) |
| `plant/ventilation.py` | 25 `ROOFVENTS` із зонами, режими (Рекуперація / Приплив і витяжка / Рециркуляція), `k = 0,55…0,85` частка витрати, `supply_c`, `indoor_c`, `heating_valve`, `filter_dp_pa = 120…210` (RV-05 — 285 → MR/00035), AHU-1, EF-ELEC/EF-CMP/EF-CHG, тепловий баланс, котли 2 × 495 кВт, КГУ покриває 322 кВт | R-09, R-10, R-23; карта P-08 |
| `plant/lighting.py` | 32 групи `LT-*`, 3 щити `LP-1..3`, рівні 0,5…1,0 за зоною, 126 Вт × n світильників, керування DALI | R-24; карта HelvarNet |
| `plant/fire.py` | 4 шлейфи, 33 групи `FA-*` (212 сповіщувачів, 36 ручних, 41 оповіщувач, 3 полум'я), `FA-FAC` — попередження (2.FAC.07, 82 %), іскрогасіння `SPARK-1` (4 датчики, 3 вузли), журнал подій 08:47 / 09:58 / 07:00 / 23:10 | R-25, R-26; карта P-09 |
| `plant/infra.py` | СЕС 900 кВт пік (1552 × 580 Вт, 8 × 115 кВт), КГУ 800 кВт на 50 %, BESS 387 кВт·год SOC 76 % заряджається 200 кВт, GENSET D700 (паливо 82 %), ATS-1 (положення «Мережа»), вода (18 642 м³, 2,1 м³/год), ворота `GATE-W/E` (7/6 проїздів), LPR (12 камер Axis, `CAM-05`/`CAM-06` на в'їзді/виїзді), автоваги (`АА 4512 КТ`, 21 380 кг, 9 зважувань), турнікети (146 на території, 312 проходів), рідери `ACR-ELEC/CHG/PAINT/SRV/IN` | R-11…R-13, R-21, R-22, R-28…R-30; карти P-07, P-10, P-11 |
| `plant/equipment_specs.json` | 93 паспорти (виробник, модель, `connected_kw`, параметри) | реєстр пристроїв (`f3d.sim.device`), номінали в каталозі |
| `dist/odoo_demo.json` | ключі `workcenters` (35), `equipment` (15), `energy.consumers` (49), `energy.cells`, `energy.lines`, `energy.transformers`, `ventilation.units` (29), `lighting.groups` (32) і `panels` (3), `fire.loops/groups`, `infra.totals`, `docks` (14), `zones` (34), `pickings`, `employees` | структура шляхів каталогу |
| Жива демо-база (тестовий сервер timur-o19demo, база `odoo`, лише читання, 13.10.2026) | `x_f3d_signal` — 196 записів (1 тривога: `ventilation/units/RV-05/filter_dp_pa` = 289,4), `x_f3d_reading` — 1 568, крон «Імітація IoT: щохвилини» активний, `maintenance.equipment` — 208 (серійники = коди сцени; навантажувачі — `FL-4xxx`), `mrp.workcenter` — 35 (`CNC-2` `blocked`), `stock.picking.batch` — 6 фур із `dock_id`, `hr.attendance` — 35, календар «Зміна 1 (07:00–15:30)» `Europe/Kyiv`, модуль `factory3d_iot_sim` 19.0.1.0.0 встановлено | §2.8 міграція, §3 налаштування |

### 1.2 Ролі й сценарії використання

| Роль (група) | Що робить | Де |
|---|---|---|
| Адміністратор factory3d (`factory3d_base.group_f3d_admin`) | вводить адресу й токени сервісу, вмикає/вимикає стоп-крани, рівень 0, перевіряє здоров'я | Налаштування → Factory3D → Емулятор (або Завод 3D → Налаштування → Налаштування емулятора); Завод 3D → Емулятор → Пульт |
| Менеджер factory3d (`group_f3d_manager`) | запускає/зупиняє сценарії, ставить прискорення часу, перемикає режим `scenario`/`follow_odoo`, ставить збій на пристрій | Завод 3D → Емулятор → Пульт, Сценарії, Пристрої (меню під коренем base, sequence 90 — X-31); вкладка «Емулятор» на картці обладнання |
| Користувач factory3d (`group_f3d_user`) | бачить стан емулятора, журнал запусків, пристрої | ті самі меню, лише читання |
| Розробник/тестувальник модулів хвилі 2 | керує емулятором напряму через `REST /sim/v1/*`, підключає клієнти протоколів | compose `iot_sim`, SPEC §7–§8 |
| Колектор `services/collector` (фаза 2) | читає пристрої по P-01…P-11 | мережа `f3d_sim` |

Типові сценарії: (1) демо-показ зміни з прискоренням ×10 — верстати відпрацьовують завдання з Odoo, навантажувачі їздять заряджатися, фури приходять за розкладом; (2) перевірка заявок ТО — сценарій `filter_clogged RV-05` → через колектор/рівень 0 з'являється заявка «Заміна фільтрів»; (3) тренування двору — `truck_no_booking` → фура без броні на LPR і шлагбаумі; (4) пожежне навчання — `fire_drill Z-CNC` → події BACnet панелі; (5) розробка плагіна колектора — клієнт `asyncua` проти `opc.tcp://iot-sim:4840`.

### 1.3 Функціональні вимоги

| ID | Вимога (перевірювана) |
|---|---|
| FR-01 | Сервіс підіймає серверну сторону всіх рядків P-01…P-11 протокольної матриці на портах із SPEC §8.1 одним процесом (compose: `iot_sim` + `mosquitto`); P-12 — існуючий `fake_relay.py` з `td_genset` окремим контейнером. |
| FR-02 | Кожен сигнал каталогу з протоколом (1 015; з 196 сигналів макета — 155) доступний через свій протокол за адресою з Додатка A SPEC (Modbus — PDU за документом вендора, D-20, X-42) і через `GET /sim/v1/signals` під тим самим кодом-шляхом; 151 рядок, який ведуть модулі-власники (обчислюють — зокрема 41 сигнал макета: `kwh_shift` ×40, `pv_now` — і `equipment/GANTRY-1/stacks`; команда `equipment/CUTOPT/cmd`), емулятор не веде (X-34, X-35, X-76). |
| FR-03 | Поведінка кожного сигналу відтворює режим макета (R-01…R-11) безперервно в часі: значення не залежать від частоти опитування. |
| FR-04 | Верстат бере потужність лише коли на ньому є завдання «в роботі» (R-02); у режимі `follow_odoo` стан береться з `mrp.workorder`/`mrp.workcenter.working_state` Odoo, у `scenario` — з власного планувальника змін. |
| FR-05 | Навантажувач розряджається в роботі, на 20 % їде в зарядну (`CHARGING`), заряджається до 95 % і повертається (R-05); положення (x, y) рухається маршрутом між зонами (R-19). |
| FR-06 | Фільтри (RV-xx, AHU-1, DUST-1) і запиленість сповіщувача ростуть за `drift` і скидаються до номіналу після закриття заявки ТО в Odoo (R-09). |
| FR-07 | Бункер котельні спорожнюється до межі й поповнюється; котли вмикаються, коли КГУ не покриває тепло (R-10). |
| FR-08 | СЕС рахується за висотою сонця для Києва на час емулятора (R-11), 8 інверторів Huawei по 115 кВт, облік `kwh_today`. |
| FR-09 | Компресор тримає тиск 6,5–7,0 бар: завантаження росте з кількістю працюючих верстатів (R-08). |
| FR-10 | Портал виконує завдання з `woodStore API` (P-03): стоси ↔ залишки, лічильник циклів, вакуум; стан у OPC UA. |
| FR-11 | Трансформатори: `p_kw` = сума секції, температура `38 + 60·S/Sн` (R-04); КГУ/BESS/ATS за балансом R-12, R-13, R-22; ATyS p — карта Annexe III (D-21, X-41); в острові генератор бере `Σ критичних − chp_kw − pv_now + bess_kw` (0…558 кВт, X-67). |
| FR-12 | Пожежна панель віддає стан 33 зон (LSZ) і 4 шлейфів по BACnet **тільки читання** об'єктами LSZ/LSP/BV/MSV/PIV (BTL-лістинг FC726, X-37), LSP id усіх 292 адресних пристроїв (сповіщувачі, ручні, оповіщувачі, полум'я) — за fire R-23/A-09 (X-79); сценарії `fire_drill`, `spark` і збій зони (API-12, X-60) генерують події та зміну Present_Value. |
| FR-13 | СКУД: відмітки входу за розкладом зміни (06:40–07:00, вихід 15:30–15:50) для 35 працівників з бейджами з Odoo; `access_event` — довільна подія; BioStar 2 REST віддає їх у `/api/events/search`. |
| FR-14 | Двір: фури прибувають за `stock.picking.batch.scheduled_date` (або розкладом макета), проходять LPR (HTTP POST), шлагбаум (DI/DO), автоваги (SICS), ворота; `truck_no_booking` — фура без броні. |
| FR-15 | REST керування `/sim/v1/*` (SPEC API-10…API-19) з токеном `Bearer`: статус, пристрої, сигнали, сценарії, збої, час, режим, скидання, стоп-кран. |
| FR-16 | Сценарії SPEC §9.3 (`shift`, `machine_fault`, `blackout`, `filter_clogged`, `truck_no_booking`, `truck_arrival`, `fire_drill`, `spark`, `access_event`, `battery_low`, `compressor_fault`, `pv_cloudy`, `boiler_refill`, `genset_test`, `lighting_scene`) запускаються/зупиняються з REST і з пульта; кожен має параметри зі схемою. |
| FR-17 | Прискорення часу `factor` 0,1…60 без втрати цілісності лічильників (кВт·год, мотогодини, деталі); годинник `Europe/Kyiv`. |
| FR-18 | Режим `follow_odoo`: сервіс читає Odoo по XML-RPC лише читанням (`search_read`/`read`) з окремим користувачем; періоди й моделі — SPEC §8.9. |
| FR-19 | Конфігурація пристроїв завантажується з Odoo `GET /f3d/sim/devices` (API-01) або з локального `catalog/devices.yaml`, якщо Odoo недоступний; розбіжності каталогів логуються. |
| FR-20 | Сервіс ніколи не відкриває клієнтських з'єднань до адрес, яких немає в allow-list (`SIM_ALLOW_OUTBOUND`): лише брокер MQTT, Odoo, приймач LPR, ретранслятор генератора. |
| FR-21 | Усі показання детерміновані при фіксованому `SIM_SEED`: два запуски з тим самим зерном і тими самими командами дають однакові ряди (для тестів). |
| FR-22 | `GET /sim/v1/health` без токена повертає `ok`/`degraded` і стан кожного протокольного сервера; `GET /sim/v1/metrics` — Prometheus. |
| FR-23 | Odoo-модуль 19.0.2.0.0 оновлює data-модуль без втрати 196 сигналів і журналу показань; x_-моделі лишаються «рівнем 0» до появи `factory3d_telemetry`. |
| FR-24 | Пульт в Odoo: стан сервісу (онлайн, режим, час, прискорення, активні сценарії, тривоги), кнопки сценаріїв, прискорення, режим, скидання; журнал запусків із результатом. |
| FR-25 | Реєстр пристроїв `f3d.sim.device` (208 записів із `maintenance.equipment` + 2 камери LPR + 5 рідерів) з протоколом P-xx, драйвером, адресою; експорт API-01. |
| FR-26 | Каталог сигналів `f3d.sim.signal` (1 166 записів з Додатка A: 662 власні + 504 з додатків модулів-власників, X-34, X-61, X-76; 151 з `protocol=none`) завантажується з CSV модуля і віддається в API-01; один і той самий CSV лежить у сервісі. |
| FR-27 | Вкладка «Емулятор» на картці обладнання: стан пристрою в емуляторі, кнопки «Збій»/«Скинути» (лише `write_enabled`). |
| FR-28 | Крон пульта раз на хвилину опитує `GET /sim/v1/status` (лише коли `read_enabled`), пише стан і вимикає крон рівня 0, коли сервіс онлайн; при офлайні понад `level0_after_min` хвилин — вмикає рівень 0 назад. |
| FR-29 | Стоп-крани `factory3d.iot_sim.read_enabled` / `write_enabled` + `neutralize.sql`: на проді після встановлення всі команди на емулятор вимкнено; `read_enabled` хук ставить за `factory3d.base.environment` (`test` → True, інакше False; CB-10, X-56). |
| FR-30 | Токени в `ir.config_parameter`, видимі лише `group_f3d_admin`, у логах і в `GET /sim/v1/status` не з'являються. |

### 1.4 Межі: що не входить

- Клієнтська сторона протоколів (плагіни колектора) — `factory3d_telemetry` та модулі-власники (§6.5 каркаса).
- Моделі показань `f3d.signal`/`f3d.reading`, заявки ТО з порогів у проді — `factory3d_telemetry` (фаза 2). У фазі 1 заявки створює лише рівень 0 (успадкована логіка).
- P-13 (Odoo IoT Box: ваги PFA584, принтери, сканери) — поза емулятором.
- Генератор: логіка SmartGen — `td_genset` (`fake_relay.py`, `relay_api.md`); тут лише запуск контейнера й оркестрація сценаріїв `blackout`/`genset_test` через REST `fake_relay` API-F-01…F-09 за контрактом CI-01 (td_genset §8.4/§8.6; X-59), навантаження в острові — R-22 SPEC (X-67).
- Фізично точна модель (термодинаміка, аеродинаміка): використовуються формули макета, не CFD.
- Емулятор не є тренажером безпеки: жодної кореляції зі справжньою пожежною панеллю; «тільки читання» по BACnet дотримано і на стороні емулятора (запис у LSZ/LSP відхиляється).

## 2. Технічна реалізація

### 2.1 Місце в системі

- `depends`: `factory3d_base` (коди сцени `f3d_code`, `f3d_kind`, паспорти `f3d_role`/`f3d_manufacturer`/`f3d_model`/`f3d_power_kw`, зони `f3d.zone`, ворота `stock.location.f3d_side/f3d_dock_no`, групи прав). Через нього — `maintenance`, `mrp`, `mrp_maintenance`, `hr`, `stock_picking_batch`.
- Бере з Odoo стандарту (тільки читання, режим `follow_odoo`): `mrp.workorder` (`state`, `workcenter_id`, `production_id`, `qty_produced`, `duration`), `mrp.workcenter` (`code`, `working_state`), `stock.picking.batch` (`dock_id`, `scheduled_date`, `f3d_code` — код фури в 3D, `f3d_truck` — опис/назва, `state`; `f3d_plate` — держномер, якщо встановлено `factory3d_yard`; X-15, X-49), `hr.employee` (`barcode`, `resource_calendar_id`), `resource.calendar.attendance`, `maintenance.request` (`stage_id.done`, `f3d_signal_code` — поки немає телеметрії, рівень 0 читає своє `x_request_id`).
- Віддає іншим модулям: протокольні карти **P-01…P-12** (SPEC §8.3–§8.14), каталог сигналів **Додаток A** (код, пристрій, протокол, адреса, тип, масштаб, номінал, пороги), **API-01** `GET /f3d/sim/devices`, **API-10…API-19** `/sim/v1/*`, **API-20…API-27** woodStore, **API-30…API-34** `/jobs`, **API-40…API-46** BioStar 2, схема MQTT-телематики (P-06), формат HTTP POST LPR (P-11), SICS-діалог (P-11).
- Споживачі за матрицею: `factory3d_machine_connect` (P-01…P-04), `factory3d_energy` (P-05, P-07), `factory3d_telemetry` (P-06, P-07, http_push LPR), `factory3d_bms` (P-08, HelvarNet), `factory3d_fire_safety` (P-09), `factory3d_access` (P-10), `factory3d_yard` (P-11), `td_genset` (P-12).

### 2.2 Архітектурна схема

```
┌──────────────────────────────── docker compose: мережа f3d_sim (internal) ────────────────────────────────┐
│                                                                                                             │
│  ┌──────────── services/iot_sim (один процес, asyncio) ───────────────────────────────────────────────┐    │
│  │  core/clock.py      годинник Europe/Kyiv, factor, sun (astral)                                      │    │
│  │  core/world.py      «світ»: зміна, завдання, фури, люди, баланс енергії, сценарії                   │    │
│  │  core/registry.py   пристрої (devices.yaml / API-01) + каталог сигналів (signals.csv)              │    │
│  │  models/*.py        машини поведінки: machine, io_machine, gantry, mobile, compressor, dust,        │    │
│  │                     boiler, pv, bess, chp, ats, transformer, meter, roofvent, lighting, facp,      │    │
│  │                     spark, smoke, access, yard (gate, lpr, scale), water                            │    │
│  │  protocols/         opcua(4840) modbus(502) bacnet(47808 UDP) mqtt-pub(→mosquitto:1883)            │    │
│  │                     helvarnet(50000 TCP/50001 UDP) biostar(8443 TLS, 8081) woodstore(8082)          │    │
│  │                     jobs(8083) sics(4001) lpr-push(→collector) control(8090 /sim/v1)               │    │
│  │  odoo/follow.py     XML-RPC читання (режим follow_odoo), XML-RPC/HTTP GET /f3d/sim/devices          │    │
│  └──────────────────────────────────────────────────────────────────────────────────────────────────────┘    │
│        ▲ протоколи P-01…P-11            ▲ REST /sim/v1 (Bearer)         │ XML-RPC read-only, API-01       │
│  [collector (фаза 2) / клієнти тестів]  [Odoo: пульт factory3d_iot_sim]◄┘                                  │
│  [mosquitto 1883]   [genset_relay = td_genset/fake_relay.py (P-12)]                                        │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
          Odoo 19 (поруч, мережа odoo_default + f3d_sim): factory3d_base, factory3d_iot_sim (пульт, API-01)
```

Потоки: (1) колектор ← емулятор по протоколах (емулятор — сервер; виняток — MQTT, де емулятор публікує в брокер, і LPR, де емулятор POST-ить на приймач); (2) Odoo-пульт → емулятор `/sim/v1` (команди) і емулятор → Odoo `GET /f3d/sim/devices` (конфігурація) + `POST /f3d/sim/events` (події запусків); (3) `follow_odoo`: емулятор → Odoo XML-RPC лише читання.

### 2.3 Нові й розширені об'єкти

| Об'єкт | Де | Призначення | Пише | Читає |
|---|---|---|---|---|
| `f3d.sim.panel` (M-01) | Odoo | один запис «Пульт»: стан сервісу, режим, час, прискорення, активні сценарії, кнопки | крон статусу, кнопки | усі групи f3d |
| `f3d.sim.device` (M-02) | Odoo | реєстр пристроїв емулятора: код сцени, обладнання/РЦ, протокол P-xx, драйвер, адреса (unit/instance/топік), стан, збій | `post_init_hook`, крон статусу, кнопки «Збій/Скинути» | API-01, форми |
| `f3d.sim.signal` (M-03) | Odoo | каталог сигналів Додатка A (код, пристрій, протокол, адреса, тип, одиниця, масштаб, номінал, пороги, модель) | data CSV модуля | API-01, пізніше `factory3d_telemetry` (міграція) |
| `f3d.sim.scenario` (M-04) | Odoo | довідник сценаріїв із JSON-схемою параметрів | data XML | пульт |
| `f3d.sim.run` (M-05) | Odoo | журнал запусків сценаріїв: хто, коли, параметри, результат | кнопки, API-03 | пульт, тести |
| `f3d.sim.event` (M-06) | Odoo | події від емулятора (сценарій, збій, тривога) з `POST /f3d/sim/events` | API-03 | пульт, переглядач (пізніше) |
| `maintenance.equipment` (+поля) (M-07) | Odoo | `f3d_sim_device_id`, `f3d_sim_state`, кнопки | модуль | вкладка «Емулятор» |
| `mrp.workcenter` (+поле) (M-08) | Odoo | `f3d_sim_device_id` (related) | модуль | форма РЦ |
| `res.config.settings` (+поля) (M-09) | Odoo | адреса, токени, стоп-крани, режим за замовчуванням, рівень 0 | адміністратор | модуль |
| `x_f3d_signal`, `x_f3d_reading` (рівень 0) | Odoo (data) | незмінні моделі data-модуля; крон `cron_iot_sim` керується пультом | рівень 0 | переглядач `odoo_pull`, міграція телеметрії |
| `World`, `Device`, `Signal`, `Scenario`, `Run` | сервіс | об'єкти ядра; стан — у пам'яті + знімок `state/snapshot.json` раз на хвилину | ядро | протокольні сервери, REST |

### 2.4 Інтеграції

| P-xx | Пристрої (коди) | Протокол/порт емулятора | Напрямок | Частота | При недоступності споживача/джерела |
|---|---|---|---|---|---|
| P-01 | SAW-1..3, NEST-1, EDGE-1..3, CNC-1..4, BORE-1, DOWEL-1, SORT-1, ASMLINE-1 (15) + GANTRY-1 (стан) | OPC UA `opc.tcp://iot-sim:4840/f3d/`, один сервер, об'єкт на верстат, простір імен OPC 40550-1 v1.02 + Machinery Jobs | колектор читає/підписується; `JobOrderControl` — методи (запис лише з `write_enabled` споживача) | оновлення 1 с; події — миттєво | сервер тримає останні значення; підписки відновлюються клієнтом |
| P-02 | SLIDE-1, VSAW-1, SAND-1, PRESS-1, GLUE-1, SPRAY-1, AUTOSPRAY-1, DRY-1, UV-1, HINGE-1, BOX-1, PACK-1, PACK-2, PACKLINE-1, ASM-1..6 (20) | Modbus TCP 502, ADAM-6050 ×4 (unit 80–83) | колектор опитує | 1 с | — |
| P-03 | GANTRY-1 | REST `http://iot-sim:8082/api/v1/*` + OPC UA | колектор опитує; `machine_connect` пише завдання/коригування стосів | стан 5 с, стоси 60 с | 503 при `SIM_ENABLED=0` |
| P-04 | карти розкрою | REST `http://iot-sim:8083/jobs` | `machine_connect` надсилає CSV, отримує план/MPR | за подією | 503/422 |
| P-05 | Q1, Q2, QF-1..4, QF-C1, QF-C2, 49 споживачів (unit 11–59, включно з OFFICE, LP-1..3, RV-ALL, AHU-1, EF-* — X-61) | Modbus TCP 502, PM5560 unit 1–8, 11–59; адреси — PDU `N − 1` (D-20) | колектор опитує | 1–10 с | — |
| P-06 | FL-1..5, FL-C1, FL-C2, TUGGER-1 | MQTT → `mosquitto:1883`, `f3d/mobile/<code>/telemetry` (QoS 1), `…/status` (retained) | емулятор публікує | 5 с (у русі 1 с) | брокер офлайн → буфер 10 хв, потім втрата |
| P-07 | COMPRESSOR (u70), DUST-1 (u90 AI, u84 DI), BOILER (BACnet 140), T1/T2 (u96 RTD), SPRINKLERS/AIR-RING (u90), WATER (u84), PV-INV-1..8 (u61–68), BESS (u69), CHP (u72), ATS-1 (u71) | Modbus TCP 502 / BACnet | колектор опитує | 1–10 с | — |
| P-08 | RV-01..25 (dev 101–125), AHU-1 (130), EF-* (131–133), BOILER (140); LP-1..3 (HelvarNet @1.1–@1.3) | BACnet/IP UDP 47808 (роутер + віртуальна мережа 2); HelvarNet TCP 50000 / UDP 50001 | колектор читає (COV/опитування), пише AO/BV лише з `write_enabled` | 10 с | — |
| P-09 | FACP-1 (dev 200: LSZ 0–33, LSP, BV 1–4 / 10 / 11, PIV 1–3, PIV `<LSP>` — запиленість, MSV 1; X-37), SPARK-1 + SMOKE-CTRL (u85) | BACnet/IP **read-only**; Modbus TCP | колектор читає/підписується на події | COV; 10 с | запис у LSZ/LSP → `WriteAccessDenied` |
| P-10 | ACR-IN, ACR-ELEC, ACR-CHG, ACR-PAINT, ACR-SRV; турнікет TURN-1 | REST `https://iot-sim:8443/api/*` (BioStar 2) | `factory3d_access` опитує з Odoo | 60 с | 401 після закінчення сесії (30 хв) |
| P-11 | GATE-W, GATE-E (u86 ADAM-6060), CAM-05, CAM-06 (LPR), TRUCK-SCALE (SICS 4001) | Modbus TCP; HTTP POST → `SIM_LPR_PUSH_URL`; TCP ASCII | колектор опитує/приймає/запитує | 1 с; подія; за запитом | POST не доставлено → 3 повтори, журнал |
| P-12 | GENSET | контейнер `genset_relay` (`td_genset/fake_relay.py`); емулятор керує ним REST API-F-01…F-09 (td_genset §8.4) за контрактом CI-01 у `blackout`/`genset_test` (X-59) | `td_genset`; емулятор — оркестратор | API-F-01 щосекунди під час сценарію | запасний режим: генератор «готовий» через 15 с |
| API-01 | Odoo → емулятор (конфіг) | `GET https://odoo/f3d/sim/devices` (Bearer `export_token`) | емулятор читає при старті й щогодини | 1 год | fallback `catalog/devices.yaml` |
| API-03 | емулятор → Odoo (події) | `POST /f3d/sim/events` | емулятор пише | за подією, пакет ≤ 100 | буфер 1 000, повтор 30 с |
| follow_odoo | емулятор → Odoo XML-RPC | `search_read` моделей §8.9 SPEC | читання | 10 с завдання, 60 с фури/люди | режим деградує до `scenario` з прапором `odoo_stale` |

### 2.5 Потік даних від пристрою до екрана

Приклад: фільтр установки RV-05 (сигнал `ventilation/units/RV-05/filter_dp_pa`).

1. `core/clock.py` робить крок `dt = real_dt × factor`; `models/roofvent.py` для RV-05 застосовує R-09: `v += rate·(1 + 0,5·r)·dt_min` (`rate = 0,05 Па/хв`, `r` — детермінований шум із `SIM_SEED`), або `v = nominal (120)`, якщо `World.maintenance_closed("RV-05")` (закрита заявка прийшла через API-01/follow або рівень 0).
2. Значення кладеться в `Signal.value` (реєстр) і в об'єкт BACnet `device 105 / analog-input 4 / present-value` (одиниця Па); якщо `v > 250` — `BI:3 (filter alarm)` = 1 і подія `event.alarm`.
3. Колектор (фаза 2, плагін `bacnet_ip`) читає `AI:4` раз на 10 с → `POST /f3d/telemetry/push` → `f3d.reading`; поріг у `f3d.signal` → `maintenance.request` «Заміна фільтрів: перепад тиску 285 Па при нормі до 250» (`factory3d_telemetry` §6.8).
4. Фаза 1 без колектора: (а) `GET /sim/v1/signals?prefix=ventilation/units/RV-05` повертає `{code, value: 287.2, unit: "Па", status: "alarm", ts}`; (б) рівень 0 (крон `cron_iot_sim`) веде ту саму формулу в Odoo незалежно (вимикається, коли сервіс онлайн).
5. Переглядач: `plant/odoo_pull.sync_signals` (сьогодні) або `factory3d_viewer` (хвиля 1) кладе значення за шляхом `ventilation/units/RV-05/filter_dp_pa` у payload; картка RV-05 показує «Перепад на фільтрі 287 Па · Дані: імітація IoT · 10:31».

Приклад 2: завдання на верстаті (режим `follow_odoo`). `odoo/follow.py` раз на 10 с читає `mrp.workorder` (`state in (progress, ready, done)`, `workcenter_id.code`) → `World.workcenters["SAW-1"].job = WO00013` → `models/machine.py` ставить `Flags.RecipeInRun=True` → `CurrentState=WORKING(3)` → споживання `p_now = P_inst·k_work` (R-02) → PM5560 `u11 fc3 pdu3059+2` (документ 3060–3061); через 15 хв `WaitUnload`, `RelativePiecesOut += 1` на кожні `duration_expected/qty` хвилин.

### 2.6 Безпека

- **Ізоляція мережі.** Compose-мережа `f3d_sim` з `internal: true`; емулятор не має маршруту в мережу цеху. У проді контейнер `iot_sim` запускається лише на тестовому контурі або з профілем `demo`; у прод-compose сервіс позначений `profiles: ["demo"]` і за замовчуванням не стартує.
- **Allow-list вихідних з'єднань** (`SIM_ALLOW_OUTBOUND`, через список хостів): `mosquitto`, Odoo (`SIM_ODOO_URL`), приймач LPR (`SIM_LPR_PUSH_URL`), `genset_relay`. Будь-який інший адресат — відмова на рівні коду (`OutboundDenied`) і запис у лог. Емулятор не містить жодного Modbus/OPC UA/BACnet **клієнта** — лише сервери; отже навіть помилкова конфігурація не може «достукатись» до справжнього ПЛК.
- **Токени.** `/sim/v1/*` — `Authorization: Bearer <SIM_API_TOKEN>` (мін. 32 символи, генерується `openssl rand -hex 32`); `GET /sim/v1/health` і `/metrics` — без токена, але лише з мережі `f3d_sim`. Токен експорту Odoo `factory3d.iot_sim.export_token` — окремий. BioStar 2 емулятор має власний логін/пароль (`SIM_BIOSTAR_USER/PASS`), сесія `bs-session-id` 30 хв. Жоден токен не потрапляє в логи (фільтр `SecretFilter` у `logging`), у `GET /sim/v1/status` і у відповіді помилок.
- **Стоп-крани.** Сервіс: `SIM_ENABLED=0` — усі сервери відповідають, але значення заморожені, команди повертають `423 Locked`; `POST /sim/v1/stop-all` — те саме в рантаймі. Odoo: `factory3d.iot_sim.read_enabled` (опитування статусу; `post_init_hook` ставить `True`, якщо `factory3d.base.environment == 'test'`, інакше `False` — CB-10, X-56), `factory3d.iot_sim.write_enabled` (сценарії, збої, час, режим; за замовчуванням `False`), `neutralize.sql` вимикає крони модуля, стирає `url`/токени, ставить обидва прапори `False`, вимикає крон рівня 0.
- **Права.** Читання — `group_f3d_user`; запуск сценаріїв, час, режим, збої — `group_f3d_manager`; адреса, токени, стоп-крани, рівень 0, реєстр пристроїв (редагування) — `group_f3d_admin`. Запис у LSZ/LSP BACnet панелі заборонений у самому емуляторі (`WriteAccessDenied`), запис у ADAM-DO (шлагбауми, димовидалення) приймається, але логується як `command`.
- **Ін'єкції.** Коди сцени в REST валідуються регулярним виразом `^[A-Z0-9][A-Z0-9\-\.]{0,31}$`; параметри сценаріїв — JSON-схемами (pydantic); XML-RPC до Odoo — лише дозволені методи (`search_read`, `read`, `search_count`, `fields_get`) окремим користувачем `f3d_sim_reader` без прав запису.

### 2.7 Продуктивність і обсяги

- Сигналів: 1 166 у каталозі (196 макета + 970 нових; 1 015 веде емулятор, 151 ведуть модулі-власники — X-34, X-35, X-76), з них оновлюваних кожну секунду ≈ 500 (верстати, лічильники, рух техніки); решта — 10–60 с. Крок ядра — 1 с реального часу (при `factor > 1` внутрішній крок дрібніший: `dt_sim ≤ 10 с`).
- OPC UA: 16 об'єктів × ~45 вузлів = ~720 вузлів, оновлення 1 с → 720 записів/с у адресний простір (`asyncua` витримує > 10 000/с); підписки до 50 клієнтів.
- Modbus: один сервер, 78 unit id, ~2 000 регістрів; очікуване навантаження колектора ≤ 200 запитів/с — `pymodbus` async server (< 5 % CPU).
- BACnet: 30 пристроїв, ~400 об'єктів (панель — 290), COV на ~120 об'єктах; `bacpypes3` ≤ 10 % CPU.
- MQTT: 8 пристроїв × 1 повідомлення/с макс = 8 msg/с.
- Пам'ять процесу ≤ 400 МБ; CPU ≤ 1 ядро при `factor=10`. Знімок стану `state/snapshot.json` (≈ 300 КБ) раз на 60 с; буфер подій у пам'яті 10 000 записів.
- Odoo: `f3d.sim.event` — ≤ 2 000 записів/добу при активних сценаріях, ротація `factory3d.iot_sim.keep_days` (14); крон статусу — 1 запит/хв; `f3d.sim.run` — десятки на добу. Індекси: `f3d.sim.device.code` (unique), `f3d.sim.signal.code` (unique), `f3d.sim.event.ts`.

### 2.8 Міграція з демо-бази і деінсталяція

Факти: у демо-базі стоїть data-модуль `factory3d_iot_sim` 19.0.1.0.0 (ir.model `x_f3d_signal`, `x_f3d_reading`, поле `maintenance.equipment.x_f3d_signal_ids`, серверні дії `action_iot_tick/start/stop/tick_now`, крон `cron_iot_sim`, 7 представлень, 5 меню) — усі xml-id у просторі `factory3d_iot_sim.*`. 196 сигналів, 1 568 показань, 1 тривога.

Крок оновлення до 19.0.2.0.0 (рішення менеджера D-13, уточнення A-09):

1. Маніфест нового модуля **зберігає в `data` ті самі файли** `data/models.xml`, `data/actions.xml`, `views/views.xml` першими в списку — Odoo не видалить записи `ir.model`/`ir.model.fields`/дії/меню (зміна власника xml-id не потрібна, модуль той самий). Очікувано: 196 `x_f3d_signal` і всі `x_f3d_reading` лишаються, `x_value`/`x_state`/`x_request_id` не торкаються.
2. `data/level0.xml` (новий): `cron_iot_sim.active = False` через `noupdate=0`-запис **не робимо** — активність крона вирішує пульт у рантаймі (FR-28); у data лише перейменування крона в «Емулятор IoT: рівень 0 (без сервісу)» і перенесення старих меню під новий батьківський пункт `menu_f3d_sim_root` (`menu_iot_root` стає дочірнім «Рівень 0»); сам `menu_f3d_sim_root` — під коренем `factory3d_base.menu_f3d_root` («Завод 3D», зарезервований `sequence` 90, base CB-09; X-31), не в «Обслуговуванні».
3. `post_init_hook` (ідемпотентний, повторний запуск нічого не дублює):
   - створює 1 запис `f3d.sim.panel`;
   - ставить `factory3d.iot_sim.read_enabled` за `factory3d.base.environment` (`test` → `True`, інакше `False`; CB-10, X-56);
   - для кожного `maintenance.equipment` з `f3d_code` (base) створює `f3d.sim.device`: протокол/драйвер за таблицею ролей SPEC §5.2 (очікувано 208 + 5 рідерів `ACR-*` + турнікет `TURN-1` + 2 камери LPR `CAM-05`, `CAM-06` + `PV-INV-1..8` + 49 лічильників `<code>-PM` + пасивний `CUTOPT` (оптимізатор розкрою без обладнання, X-76) = 274, з них `passive` ≈ 100 — стелажі, двері, групи світильників і сповіщувачів, блискавкозахист…; SPEC §5.3);
   - завантажує `f3d.sim.signal` з `data/f3d_sim_signal.csv` (1 166, з них 151 `protocol=none` — X-34, X-35, X-76), прив'язуючи `device_id` за кодом; для 196 рядків «макет» проставляє `level0_signal_id` → `x_f3d_signal` за `x_code` (очікувано 196 збігів, 0 без пари — інакше лог WARNING із переліком);
   - створює 15 сценаріїв із `data/f3d_sim_scenario.xml` (xml-id `scenario_<name>`).
4. Пізніше `factory3d_telemetry` (фаза 2) у своєму `post_init_hook` читає `f3d.sim.signal` (визначення, адреси) і `x_f3d_signal`/`x_f3d_reading` (значення, журнал) → `f3d.signal`/`f3d.reading`; після цього версія 19.0.3.0.0 цього модуля прибирає `data/models.xml` з маніфесту (data-файл переноситься в `migrations/19.0.3.0.0/` з перевіркою, що міграцію виконано).
5. `uninstall_hook`: вимикає свої крони, стирає `ir.config_parameter` `factory3d.iot_sim.*`; **не** видаляє `f3d.sim.run`/`f3d.sim.event` як бізнес-дані? — видаляє (це журнал емулятора, не бізнес-дані; A-11), але `x_*`-моделі й сигнали не чіпає (їх видалить лише видалення data-файлів у наступній версії за планом п. 4).

## 3. Налаштування системи

| Об'єкт | Параметр | Значення для тестового сервера (timur-o19demo) | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `factory3d.iot_sim.url` | `http://iot-sim:8090` | адреса REST `/sim/v1` з контейнера Odoo; порожнє = сервіс не налаштовано |
| `ir.config_parameter` | `factory3d.iot_sim.token` | 64 hex | = `SIM_API_TOKEN` сервісу; лише `group_f3d_admin` |
| `ir.config_parameter` | `factory3d.iot_sim.export_token` | 64 hex | токен для API-01/API-03 (емулятор → Odoo); = `SIM_ODOO_EXPORT_TOKEN` |
| `ir.config_parameter` | `factory3d.iot_sim.read_enabled` | `True` (тест) / `False` (прод) — ставить `post_init_hook` за `factory3d.base.environment` (X-56) | стоп-кран опитування статусу |
| `ir.config_parameter` | `factory3d.iot_sim.write_enabled` | `True` (тест) / `False` (прод) | стоп-кран команд (сценарії, збої, час, режим) |
| `ir.config_parameter` | `factory3d.iot_sim.mode` | `follow_odoo` | режим за замовчуванням, який пульт ставить сервісу після старту; на стенді без `machine_connect` — `follow_odoo` |
| `ir.config_parameter` | `factory3d.iot_sim.level0_enabled` | `True` | дозволити автоматичне вмикання рівня 0 при офлайні сервісу |
| `ir.config_parameter` | `factory3d.iot_sim.level0_after_min` | `5` | через скільки хвилин офлайну вмикати рівень 0 |
| `ir.config_parameter` | `factory3d.iot_sim.timeout_s` | `5` | таймаут HTTP до сервісу |
| `ir.config_parameter` | `factory3d.iot_sim.keep_days` | `14` | ротація `f3d.sim.event` |
| `res.users` | `f3d_sim_reader` | користувач без права писати: групи `base.group_user`, `factory3d_base.group_f3d_user`, `mrp.group_mrp_user` (читання), API-ключ | для `follow_odoo` (XML-RPC лише читання); пароль не входить у документацію |
| `ir.cron` | `factory3d_iot_sim.cron_f3d_sim_status` | 1 хв, активний | опитування `GET /sim/v1/status`, керування рівнем 0 |
| `ir.cron` | `factory3d_iot_sim.cron_iot_sim` (рівень 0) | 1 хв, **керується пультом** | активний лише коли сервіс офлайн або примусово з пульта |
| `ir.cron` | `factory3d_iot_sim.cron_f3d_sim_gc` | 1 доба | ротація подій |
| `f3d.sim.scenario` | 15 записів | з `data/f3d_sim_scenario.xml` | параметри за замовчуванням — SPEC §9.3 |
| compose `iot_sim` env | `SIM_API_TOKEN`, `SIM_ODOO_URL=http://odoo19:8069`, `SIM_ODOO_DB=odoo`, `SIM_ODOO_USER=f3d_sim_reader`, `SIM_ODOO_APIKEY`, `SIM_ODOO_EXPORT_TOKEN`, `SIM_MODE=follow_odoo`, `SIM_FACTOR=1`, `SIM_SEED=20261012`, `SIM_TZ=Europe/Kyiv`, `SIM_MQTT_URL=mqtt://mosquitto:1883`, `SIM_LPR_PUSH_URL=http://collector:8080/f3d/lpr` (на стенді фази 1 — `http://iot-sim:8090/sim/v1/lpr-sink`), `SIM_ALLOW_OUTBOUND=mosquitto,odoo19,collector,genset_relay`, `SIM_GENSET_RELAY_TOKEN` (= `RELAY_SIM_TOKEN`), `SIM_GENSET_AMF_MASTER=hgm`, `SIM_GENSET_KW_MAX=558`, `SIM_HELVAR_VERSION=2`, `SIM_BIOSTAR_USER=admin`, `SIM_BIOSTAR_PASS=…`, `SIM_LOG_LEVEL=INFO`, `SIM_ENABLED=1` | повний перелік — SPEC §8.2 | |
| compose `genset_relay` env (td_genset §8.5 CI-02, X-75) | `RELAY_PROFILE=d700`, `RELAY_PORT=8000`, `RELAY_SIM_TOKEN=${RELAY_SIM_TOKEN}` (той самий, що `SIM_GENSET_RELAY_TOKEN`; `.env` проєкту compose), `RELAY_TIME_FACTOR=1`, `RELAY_TZ=Europe/Kyiv`; мережі `f3d_sim`, `odoo_default` | `build: ${TD_GENSET_PATH}/relay`; healthcheck `http://localhost:8000/health`; порожній токен → емулятор у запасному режимі (SPEC §8.14) | SPEC §8.1.4 |
| compose порти | 4840, 502, 47808/udp, 50000, 50001/udp, 8443, 8081, 8082, 8083, 4001, 8090, 1883 (mosquitto) | публікуються лише в мережу `f3d_sim`; на хост — тільки 8090 і 4840 для розробника (профіль `dev`) | |

## 4. Інструкція

**4.1 Увімкнути емулятор на тестовому сервері** (адміністратор factory3d). 1) `docker compose --profile demo up -d iot_sim mosquitto genset_relay`; 2) Налаштування → Factory3D → Емулятор: адреса `http://iot-sim:8090`, токен (той самий, що `SIM_API_TOKEN`), токен експорту, «Опитувати стан» = увімкнено, «Дозволити команди» = увімкнено; 3) Завод 3D → Емулятор → Пульт → «Перевірити зв'язок»: статус «онлайн», версія, режим; 4) переконатися, що «Рівень 0» показує «вимкнено автоматично (сервіс онлайн)».

**4.2 Прогнати демо-зміну з прискоренням** (менеджер factory3d). Пульт → Прискорення `10` → «Застосувати»; Сценарії → `shift` → «Запустити» (параметри: дата зміни — сьогодні, лінія — усі). Спостерігати: картки верстатів (потужність, стан), навантажувачі (заряд), фури (ворота), «Енергія» (профіль). Зупинити: «Зупинити сценарій»; повернути прискорення `1`.

**4.3 Перевірити заявку ТО з порогу** (менеджер). Завод 3D → Емулятор → Сценарії → `filter_clogged`, параметри `device=RV-05`, `value=285` (X-58) → «Запустити». Через ≤ 2 хв: Обслуговування → Заявки — «Заміна фільтрів: перепад тиску 285 Па при нормі до 250» (у фазі 1 — від рівня 0 або телеметрії фази 2). Закрити заявку (стадія «Відремонтовано») → через ≤ 2 хв показник повертається до 120 Па.

**4.4 Поставити й зняти збій на пристрої** (менеджер). Обслуговування → Обладнання → CNC-2 → вкладка «Емулятор» → «Збій» (причина — зі списку: `spindle`, `emergency`, `power`, `comm`). У 3D верстат — червоне кільце, OPC UA `Flags.Error=True`, `CurrentState=ERROR`. «Скинути» повертає стан.

**4.5 Робота без сервісу (рівень 0)** (адміністратор). Якщо сервіс офлайн > 5 хв, крон статусу сам вмикає «Імітація IoT: рівень 0»; 196 сигналів макета живуть в Odoo за старою логікою (заявки ТО створюються). Вручну: Пульт → «Рівень 0: увімкнути/вимкнути». Після повернення сервісу рівень 0 вимикається автоматично, значення сервіс підхоплює з Odoo (`x_value`) при наступному старті, якщо `SIM_LEVEL0_SYNC=1`.

**4.6 Стоп-кран на проді** (адміністратор). Налаштування → «Дозволити команди» = вимкнено (усі кнопки сценаріїв/збоїв стають неактивними, API повертає «вимкнено стоп-краном»); «Опитувати стан» = вимкнено (крон не ходить у сервіс). Повна нейтралізація копії бази — `neutralize.sql` модуля.

## 5. Ризики й відкриті питання

### 5.1 Відкриті питання (ті самі номери — у SPEC §15)

| ID | Питання | Кому | Рекомендована відповідь | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | **Закрито 14.10 (відповідь № 6, CONSISTENCY):** емулятор — за OPC 40550-1 і `JobManagement`; nodeset і серійні номери верстатів — вхідні дані ПНР. Чи мають верстати HOMAG на заводі ліцензію OPC UA (woodworking companion spec) і чи є `JobManagement`? | замовник / HOMAG | так, OPC 40550-1 + Machinery Jobs; без ліцензії — tapio (не в v1) | емулятор за стандартом v1.02.0; `JobManagement` — опційний профіль |
| Q-02 | **Закрито 14.10 (відповідь № 6, CONSISTENCY):** woodStore — наш контракт P-03, на проді — адаптер `woodstore` за описом HOMAG; карти — CSV P-04. Інтерфейс woodStore/STORETEQ для стосів і завдань порталу | HOMAG | отримати опис API; якщо закритий — обмін файлами CSV | контракт «woodStore API v1» — ПРИПУЩЕННЯ (SPEC §8.5) |
| Q-03 | **Закрито 14.10 (відповідь № 10, CONSISTENCY):** адреси — з емулятора; на проді `read_enabled=False` до дозволу монтажника; ключ S2 і PICS/EPICS — вхідні дані ПНР. Cerberus PRO FC726: який ключ BACnet (S2 FCA2034-A1 «monitoring only»), склад об'єктів (PICS/EPICS) і чи віддає запиленість | монтажник / Siemens (CONSISTENCY «Питання до замовника» № 10) | S2, типи об'єктів за BTL-лістингом 30841: LSZ, LSP, BV, MSV, PIV (X-37) | емулятор: LSZ на зону, LSP на сповіщувач, BV для шлейфів/сирен/пульта, PIV для лічильників і запиленості (запиленість — ПРИПУЩЕННЯ до PICS) |
| Q-04 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** BACnet напряму за §8.10.2 (ПРИПУЩЕННЯ) до переліку точок Hoval; при Modbus-шлюзі — ті самі коди сигналів. Hoval RoofVent / TopTronic C: BACnet/IP напряму чи через шлюз Hoval (Modbus TCP)? | Hoval / замовник | якщо лише Modbus — колектор перемикає тип джерела, карта об'єктів емулятора лишається еталоном сигналів | BACnet (D-08); перелік сигналів — з мануалу RoofVent (режими VE/VEL/AQ/REC/EA/SA/ST, реле перепаду фільтра 250/350 Па) |
| Q-05 | **Закрито 14.10 (відповідь № 8, CONSISTENCY):** карта-ПРИПУЩЕННЯ §8.9.3 до документа Atlas Copco. Карта регістрів Elektronikon Mk5 (Atlas Copco видає за серійним номером) | замовник / Atlas Copco | запросити; до того — ПРИПУЩЕННЯ SPEC §8.9.2 | наш макет регістрів 3000–3030 |
| Q-06 | **Закрито 14.10 (відповідь № 3, CONSISTENCY):** карта-ПРИПУЩЕННЯ §8.9.5 до документа TEDOM; в острові — виміряні значення. Точки даних TEDOM Quanto D800 (Modbus TCP ProCon) | TEDOM | запросити | ПРИПУЩЕННЯ §8.9.5 |
| ~~Q-07~~ | Таблиця Modbus ATyS p 1600 — **закрито X-41** (D-21) | — | карта — Socomec «ATyS p Instruction manual 542 001 D», Annexe III: 20482 режим, 20483 положення (1 = 0, 2 = I, 3 = II), 20484 реле пуску, 20486/20487 стани джерел (SPEC §8.9.4) | звірка з прошивкою ATyS p 1600 — CONSISTENCY «Питання до замовника» № 2 |
| Q-08 | **Закрито 14.10 (відповідь № 17, CONSISTENCY):** MT-SICS через шлюз RS-232→Ethernet до опису АКСІС ME-01; інший протокол — діалект плагіна `sics`. Ваговий індикатор автоваг АКСІС 60-18-К-Е і його протокол | постачальник ваг | якщо не SICS — «Toledo 8217»-подібний ASCII; `factory3d_yard` змінює діалект плагіна | SICS Level 0 (`S`, `SI`, `SIR`, `Z`, `T`) |
| ~~Q-09~~ | Куди Axis LPV має POST-ити події — **закрито X-53** | — | приймач `http_push` telemetry `POST /f3d/<route>[/<secret>]` (`/f3d/lpr`) | у фазі 1 — `SIM_LPR_PUSH_URL` → `/sim/v1/lpr-sink` |
| Q-10 | **Закрито 14.10 (відповідь № 9, CONSISTENCY):** MQTT-шлюз (D-09). Телематичний шлюз навантажувачів Linde/Jungheinrich (D-09) | замовник | шлюз із MQTT; схема P-06 — наша | ПРИПУЩЕННЯ |
| Q-11 | **Закрито 14.10 (відповідь № 14, CONSISTENCY):** календар «Зміна 1 (07:00–15:30)»; поза ним — попередження, не заборона. Чи є друга зміна і графік охорони/КПП (для відміток і фур поза зміною 1)? | замовник | одна зміна 07:00–15:30 у демо; друга — параметр сценарію `shift` | календар з Odoo |
| Q-12 | **Закрито 14.10 (відповідь № 15, CONSISTENCY):** IP і unit id — на ПНР; опитування P — 10 с, лічильники — 60 с. Unit id/IP для лічильників у проді (по IP на лічильник чи шлюз RS-485→TCP з unit id) | енергетик | шлюз Link150/IFE з unit id = адреса RS-485; каталог вже має унікальні unit id | один IP + unit id (A-03) |
| Q-13 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** обидва режими пагінації; два турнікети × вхід/вихід — даними у v1.1. BioStar 2: обличчя чи картки на прохідній; чи потрібні `tna_key` (T&A) у подіях | замовник | картка+обличчя; `tna_key` 1/2 вхід/вихід | емулятор дає і `Verify success (card)` **4102** (0x1006), і `Identify success (face)` **4867** (0x1303) за Device SDK — чергуються за `det(code) % 2` (0 → 4102, 1 → 4867), `tna_key`; події за зростанням часу з пагінацією `offset`/`hint` (X-50) |
| Q-14 | **Закрито 14.10 (рішення менеджера):** ні — автоматичне взаємовиключення FR-28 (D-13). Чи тримати рівень 0 паралельно із сервісом (два джерела значень) | менеджер | ні — автоматичне взаємовиключення (FR-28) | реалізовано як FR-28 |
| ~~Q-15~~ | `td_genset`: REST `fake_relay.py` для сценарію `blackout` — **закрито X-59** | — | REST `fake_relay` `/sim/v1/*` API-F-01…F-09 (td_genset §8.4), контракт CI-01 (td_genset §8.6): параметри `amf_master`, `genset_load_kw`, `test_on_load` (SPEC §8.14, S-03, S-14, R-22) | без ретранслятора — запасний режим (генератор «готовий» через 15 с) |

### 5.2 Ризики

| Ризик | Вплив | Пом'якшення |
|---|---|---|
| Карти регістрів вендорів без публічних документів (Elektronikon, TEDOM, LUNA2000 C&I, NESTRO, Kalvis) не збігаються із залізом (ATyS p — уже за Annexe III, X-41) | при переході на живий пристрій колектор треба переналаштувати | адреси винесено в `f3d.signal.address` (телеметрія), не в код; у каталозі позначено ПРИПУЩЕННЯ; де можливо — стандартні I/O-модулі ADAM з опублікованими картами (A-05) |
| `bacpypes3` з ~400 об'єктами й COV може їсти CPU | уповільнення всього процесу | BACnet у окремому asyncio-таску з власним циклом 10 с; тест продуктивності ТП-03; за потреби — окремий процес `bacnet_server` |
| Прискорення часу ламає часові мітки протоколів (SourceTimestamp OPC UA, `datetime` BioStar) | споживачі бачать «майбутнє» | усі мітки — час емулятора `sim_now`; у `follow_odoo` `factor` фіксовано 1 (FR-17 обмеження), у `scenario` — споживачі отримують `sim_now` у `GET /sim/v1/status` |
| Демо-годинник Odoo зупинено на 2026-10-12 10:30, а емулятор живе в реальному часі | у `follow_odoo` відкриті таймери завдань «добігають» | емулятор бере стан завдань, а не час; `shift` сценарій планує за календарем поточного дня |
| Версії бібліотек (asyncua, pymodbus 3.x API, bacpypes3) змінюють API | збірка ламається | закріплені версії в `requirements.txt` (SPEC §8.1), CI з тестами протоколів |
| Два джерела показань (рівень 0 і сервіс) розходяться | плутанина в заявках ТО | FR-28 взаємовиключення; при старті сервіс читає `x_value` (`SIM_LEVEL0_SYNC`) |
| Обсяг каталогу (1 166 сигналів, з них 504 — з додатків модулів-власників) важко підтримувати вручну | розсинхронізація SPEC/сервіс/Odoo | один CSV генерується скриптом `tools/gen_catalog.py` з правил SPEC і додатків модулів-власників (energy C, fire B, yard A, machine_connect C.2, bms B — X-34); тест ТБ-05 порівнює хеші трьох копій |

## 6. План сборки агентами

| Воркер | Межі файлів | Здає | Залежить від |
|---|---|---|---|
| W0 (каркас) | `services/iot_sim/` скелет пакета, `pyproject.toml`, `requirements.txt`, `docker-compose.sim.yml`, `catalog/signals.csv` (з Додатка A), `catalog/devices.yaml`, `tools/gen_catalog.py`; Odoo: `__manifest__.py`, `security/`, порожні `models/__init__.py` | збірка стартує, `GET /sim/v1/health` = ok, модуль встановлюється на копію демо-бази | — |
| W1 (ядро) | `iot_sim/core/*`, `iot_sim/models/*`, `iot_sim/scenarios/*`, `tests/unit/*` | R-01…R-30 як класи з детермінованим зерном, сценарії, знімок стану; юніт-тести §13.1 | W0 |
| W2 (OPC UA + woodStore + jobs) | `protocols/opcua_server.py`, `protocols/woodstore_api.py`, `protocols/jobs_api.py`, `tests/protocols/test_opcua.py`, `test_woodstore.py`, `test_jobs.py` | P-01, P-03, P-04 | W1 (інтерфейс `World`) |
| W3 (Modbus + BACnet + HelvarNet) | `protocols/modbus_server.py`, `protocols/bacnet_server.py`, `protocols/helvarnet_server.py`, відповідні тести | P-02, P-05, P-07, P-08, P-09 (панель), P-11 (шлагбауми) | W1 |
| W4 (MQTT + BioStar + LPR + SICS + control REST + follow_odoo) | `protocols/mqtt_publisher.py`, `biostar_api.py`, `lpr_push.py`, `sics_server.py`, `rest/control_api.py`, `odoo/follow.py`, `odoo/devices_client.py`, тести | P-06, P-10, P-11 (LPR, ваги), API-10…API-19, режим `follow_odoo` | W1 |
| W5 (Odoo-модуль) | `odoo_addons/factory3d_iot_sim/models/*`, `views/*`, `controllers/*`, `data/*`, `security/*`, `tests/*`, `migrations/`, `neutralize.sql` | M-01…M-09, V-01…V-12, API-01…API-03, крони, AC типу UT | W0 |
| W6 (стенд і ТК) | `tests/stand/*` (клієнти pymodbus/asyncua/bacpypes3/paho/requests проти compose), `docs/modules/factory3d_iot_sim/TEST_REPORT.md` | ТК-01…ТК-17, ТБ, ТП, DEPLOY_TEST | W2–W5 |

Порядок злиття: W0 → W1 → (W2 ‖ W3 ‖ W4 ‖ W5) → W6. Інтерфейс між W1 і протокольними воркерами — `World.signals[code].value`, `World.devices[code]`, `World.events` (SPEC §8.2.3) — фіксується W1 першим комітом.

## 7. Рішення автора (A-xx)

| ID | Рішення | Обґрунтування | Що змінює відносно каркаса |
|---|---|---|---|
| A-01 | Один OPC UA сервер на всі верстати HOMAG (об'єкт на верстат у теці `Machines`), а не сервер на верстат | один порт, однаковий адресний простір; реальний верстат = окремий endpoint — у колектора змінюється лише `source.url` і префікс NodeId | дозволено §6.6 («або один сервер, простір імен на верстат») |
| A-02 | Каталог сигналів з адресами — один CSV (`services/iot_sim/catalog/signals.csv` = `odoo_addons/factory3d_iot_sim/data/f3d_sim_signal.csv`), згенерований скриптом з правил; в Odoo — модель `f3d.sim.signal` як джерело для API-01 і для міграції в `factory3d_telemetry` | без цього каталог жив би в трьох місцях; `f3d.sim.signal` не є журналом показань (D-04 не порушено) | нове в модулі пульта |
| A-03 | Modbus TCP: один сервер порт 502, глобально унікальні unit id за таблицею SPEC §8.4 (лічильники 1–59, PV 61–68, BESS 69, Elektronikon 70, ATyS 71, TEDOM 72, ADAM 80–96) | у проді кожен пристрій має свій IP (unit 1 або адреса RS-485 за шлюзом); перехід — лише `host`/`unit` у `f3d.source` | уточнення P-05/P-07 |
| A-04 | BACnet/IP: роутер на UDP 47808 + віртуальна мережа 2 з пристроями instance 101–200 (стандартна маршрутизація BACnet) | один UDP-порт на контейнер; `Who-Is` через роутер знаходить усі пристрої, як у реальній мережі з BBMD/роутерами | уточнення P-08/P-09 |
| A-05 | Для пристроїв без опублікованих карт (NESTRO NKJ, Kalvis, GreCon BS 7, D+H CPS-M1, CAME GARD, Apator NK, температура Trihal) — опубліковані карти I/O-модулів Advantech ADAM-6050/6060/6017/6015 замість вигаданих «вендорських» регістрів | карти перевірені з ADAM-6000 User Manual Ed.12 (Advantech, 2022); у реальному монтажі саме так підключають «сухі контакти» й 4–20 мА | розширює «ПРИПУЩЕННЯ ADAM» з P-02 на P-07/P-09/P-11 |
| A-06 | Котельня — BACnet (dev 140), не Modbus | §6.6 P-08 відносить «котельню» до BACnet; Kalvis K-500M штатно має контролер без Modbus — у проді це буде контролер котельні/шлюз | уточнення P-07/P-08 |
| A-07 | BioStar 2 емулятор на HTTPS 8443 (самопідписаний) + HTTP 8081 для тестів; сесія 30 хв | реальний BioStar 2 — HTTPS 443; у compose порти < 1024 уникаємо | — |
| A-08 | `follow_odoo` читає Odoo раз на 10 с (завдання) і 60 с (фури, люди, заявки) окремим користувачем `f3d_sim_reader` через XML-RPC з API-ключем | навантаження ≤ 0,2 запиту/с; без прав запису — безпека | — |
| A-09 | Уточнення D-13: x_-моделі лишаються без змін і без посилань із Python (крім читання `x_value`/`x_code` для синхронізації та `x_request_id` рівня 0); крон рівня 0 взаємовиключений із сервісом (FR-28) | два незалежні генератори значень неприпустимі; видалення x_ лише після міграції телеметрією | — |
| A-10 | Перелік сценаріїв розширено відносно §6.6: + `truck_arrival`, `spark`, `battery_low`, `compressor_fault`, `pv_cloudy`, `boiler_refill`, `genset_test`, `lighting_scene` | потрібні макету (події 08:47 іскра, зарядка на 20 %, бункер, СЕС) і модулям фаз 3–5 | розширення |
| A-11 | `uninstall_hook` видаляє `f3d.sim.run`/`f3d.sim.event` (журнал емулятора), не чіпає x_-дані й обладнання | це технічний журнал стенда, не бізнес-дані | — |
| A-12 | Прискорення часу в режимі `follow_odoo` зафіксовано на 1 | інакше час емулятора розходиться з Odoo, таймери завдань стають безглуздими | уточнення FR-17 |
