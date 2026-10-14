# factory3d_yard — технічне рішення

Версія 0.1 · 14.10.2026 · автор: агент-архітектор модуля `factory3d_yard` (хвиля 2, фаза 4) · статус: **чернетка на погодження**.
Каркас: `docs/ARCHITECTURE.md` (далі «каркас»: §3 залежності, §5 конвенції, §6.1–6.2 код сцени й ворота,
§6.4–6.5 телеметрія й плагіни, §6.6 рядок **P-11**, §6.7 провайдер переглядача, §6.8 заявки ТО, §9 п. 7).
Специфікація: `docs/modules/factory3d_yard/SPEC.md`. Спирається на контракти `factory3d_base` CB-01…CB-06,
CB-09, CB-10, CB-12 (SPEC base §2, Додатки C.2 і D), `factory3d_viewer` M-01 (хук провайдера), M-03 (шина),
Додаток A (`docks`, `pickings[].dock/truck`, `ship_chain`, `sheet_chain`), `factory3d_telemetry` CT-01…CT-10
(ARCH telemetry §2.1; SPEC telemetry ще пишеться — розбіжності в Q-01…Q-04) і «документацію вендора»
`factory3d_iot_sim` SPEC §8.4 (Modbus, unit id 86), **§8.13 P-11** (ADAM-6060, Axis LPV, SICS), §9.3 S-05/S-06,
Додаток A рядки 654–661. Рішення автора — **A-xx** (§5.2), відкриті питання — **Q-xx** (§5.1).

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора; `docs/оцінки` в репозиторії немає) |
|---|---|---|
| ТР | цей документ + SPEC.md | 20 |
| Архітектура | погодження A-xx/Q-xx з менеджером, фіксація контрактів CY-01…CY-08 для access/viewer/telemetry/iot_sim | 8 |
| Розробка | Odoo-модуль `odoo_addons/factory3d_yard` (моделі, диспетчерська, екран КПП, провайдер, міграція) — 88; плагін колектора `sics` — 16 | 104 |
| Тестування | юніт-тести, ТК на емуляторі (`truck_arrival`, `truck_no_booking`, SICS, команда шлагбаума), безпека, продуктивність, DEPLOY_TEST | 40 |
| Інструкція | §4 цього документа + README модуля + CHANGELOG | 6 |
| **Разом** | | **178** |

Факти з живої демо-бази (тестовий сервер timur-o19demo, база `odoo`, лише читання, 14.10.2026): Odoo 19.0+e;
установлені `stock_picking_batch`, `stock_fleet` («Dispatch Management System»), **`stock_fleet_enterprise`**
(Gantt диспетчеризації `stock_fleet_enterprise.view_stock_picking_batch_gantt`: `date_start="scheduled_date"`,
`date_stop="end_date"`, `default_group_by="picking_type_id,dock_id"`, `color="vehicle_id"`; kanban
`stock_picking_batch_view_kanban` з `dock_id`, `scheduled_date → end_date`; форма «План» з `daterange`
`scheduled_date`/`end_date`), `fleet`, `hr_fleet`, `delivery`, `stock_delivery`, `web_gantt`, `portal`,
`purchase_stock`, `sale_stock`. Поля `stock.picking.batch`: `dock_id` (`stock.location`), `allowed_dock_ids`,
`vehicle_id` (`fleet.vehicle`), `vehicle_category_id` (`fleet.vehicle.model.category`), `driver_id`
(`res.partner`), `scheduled_date`, `end_date`, `estimated_shipping_weight`, `vehicle_weight_capacity`,
`has_dispatch_management`. Категорія техніки «Фура» (id 1); перевізники `delivery.carrier`: «Власний транспорт»,
«Нова Пошта Вантаж (демо)», «Standard delivery»; партнер «Нова Пошта Вантаж (демо)» є і як `res.partner` (id 11).
6 пакетів `BATCH/IN/00001…00003`, `BATCH/OUT/00004…00006` з `dock_id`, `vehicle_category_id=Фура`,
`description="TRUCK-IN-1 · DOCK-W1"`, вікна `scheduled_date…end_date` по 60 хв (UTC 06:30–07:30, 07:15–08:15,
07:40–08:40, 09:00–10:00, 09:00–10:00, 08:00–09:00), `driver_id`/`vehicle_id` порожні. Типи операцій:
`Receipts` (`dispatch_management=True`, `dock_ids=[]`), `Delivery Orders` (`dock_ids=[WH/Відвантаження]`) —
хук base (R-10) наповнює їх 7+7 воротами. `product.product.weight = 0` в усіх 57 товарів (вага документа не
рахується, R-12). На `stock.picking` є `x_dock/x_truck/x_vehicle` — мігрує base. Моделі `fleet.vehicle` — 0
записів. Жодних полів `f3d_*` ще немає (base не встановлений).

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що є в макеті

| Джерело | Що саме | Як використано |
|---|---|---|
| `plant/site.py:1411–1432` | 6 фур `TRUCK-IN-1…3` при `x=−7.3`, `y=5/25/35`, `rz=0` («Фура на розвантаженні»); `TRUCK-OUT-1…3` при `x=W+7.3=157.3`, `y=15/45/65`, `rz=180` («Машина під навантаженням»); напівпричіп 13,6 м | коди сцени рейсів (`stock.picking.batch.f3d_code`, CB-06), координати для провайдера (R-20) |
| `plant/infra.py:14–24` | `GATES = [("GATE-W", −20, 8 м, "Ворота приймання"), ("GATE-E", 168, 8, "Ворота відвантаження")]` на огорожі `y=−30`; `KPP=(98.4,−27)`; `PARKING`; `TRUCK_SCALE=(172,−14)` 18×3 м; камери `CAM-05` (−20,−28.5, 90°) і `CAM-06` (168,−28.5) — на в'їзді/виїзді | довідник воріт (`f3d.yard.gate`), ваг (`f3d.yard.scale`), камери LPR |
| `plant/infra.py:234–235, 368–371` | ролі `barrier` (GATE-W/E), `truck_scale`, `cctv_camera`, `nvr`; картки: ваги «Остання машина АА 4512 КТ · брутто 21 380 кг · WH/OUT/00413», «Сьогодні зважувань 9»; шлагбауми «Стан закритий», «Сьогодні проїздів 7/6» | міграція (§2.8), поля `today_count`, `passes_today`, приклади R-xx |
| `plant/site2.py:449–468` | шлагбаум: «Автоматичний шлагбаум; номер машини звіряється з документом приймання/відвантаження»; ваги: «Зважування фур на в'їзді й виїзді; вага йде в документ відвантаження Odoo» | FR-06, FR-11, FR-12 |
| `plant/equipment_specs.json[role=barrier]` | CAME GARD LS6 (803BB-0490, GLS60AGS): проїзд до 6,5 м, відкриття 4–6 с, 24 В DC з енкодером, 160 циклів/год, IP54, CAME Connect; сторінка CAME (переглянуто 14.10.2026): «can be integrated with third party systems through MODBUS protocol» | таймаут відкриття `open_timeout_s=10` (R-16), P-11 I/O-підключення (ПРИПУЩЕННЯ монтажу через ADAM) |
| `plant/equipment_specs.json[role=truck_scale]` | АКСІС 60-18-К-Е: НПВ 60 000 кг, НмПВ 400 кг, дискретність 20 кг, термінал AXIS ME-01 з RS-232 (RS-485/Ethernet під замовлення) | `f3d.yard.scale`: `max_kg=60000`, `min_kg=400`, `division_kg=20`; Q-05 (протокол індикатора) |
| `plant/equipment_specs.json[role=cctv_camera]` | Axis P1488-LE 4K, аналітика; `nvr` Axis S3016 (архів 30 діб) | знімок у події LPR — лише посилання/вкладення; відеоархів — поза Odoo |
| `plant/layout.py:100–127` | ворота 1–7 з кожного боку (`DOOR_Y`), `RCV_GOODS` (1–3 плити, 4 фурнітура, 5 крайка, 6 ЛФМ, 7 пакматеріали), `DOOR_H=4.5` | `f3d_accepts` воріт (base CB-05) → попередження при бронюванні (R-04) |
| `plant/odoo_demo.py:434–561` | 13 приймань `WH/IN/00123…00135` (`dock`, `truck`, `scheduled_date` 07:10…14:30 і завтра 09:00, `progress`), 8 відвантажень `WH/OUT/00412…00419` (`dock`, `truck` для k=1,4,6, `carrier` «Власний транспорт»/«Нова Пошта Вантаж (демо)», 11:00/12:00/13:00); `NOW = 2026-10-12 10:30` | приклади R-xx, міграція §2.8, ТК |
| `plant/odoo_demo.py:849–890` (`mo_delivery`) | шлях до клієнта: … → `Z-OUT-k` → ворота → фура клієнта → `TRUCK-SCALE` «контрольне зважування машини на виїзді» → `GATE-E` «виїзд через КПП відвантаження»; `material_paths[0]`: `GATE-W` «в'їзд» → `TRUCK-IN-1` → `UNLOAD-1` … | порядок станів рейсу (§2.5, SPEC §10) |
| `plant/odoo_flows.py:356–375, 652–676` | `step_carriers`: `delivery.carrier` на відвантаженнях і SO; `step_docks`: 14 воріт, категорія «Фура», пакет на кожну фуру з `dock_id`, `scheduled_date` | міграція §2.8 (джерело 6 рейсів і перевізників) |
| `dist/odoo_demo.json` | `docks` (14 → назва документа), `pickings[]` (`dock`, `truck`, `carrier`, `progress`), `ship_chain.steps[5]` «Фура клієнта: 3 машини біля воріт», `sheet_chain.steps[1]` «Вивантаження з фури» (`TRUCK-IN-1`, `UNLOAD-1`…), `material_paths` | контракт переглядача (viewer A.8, A.11, A.14) — не змінюється; розділ `yard` — новий |
| `viewer/index.html:1675–1736, 1807–1808` | вкладка «Логістика»: `pickRow` («ворота · час · машина біля воріт»), маршрут приймання «фура → вивантаження → контроль», картка воріт «Документ на воротах», картка фури «Документ» | картки рейсу/воріт у переглядачі — через розділ `yard` (CY-06) |
| `README.md` «Територія» | «автомобільні ваги АКСІС 60 т, шлагбауми CAME, 12 камер Axis P1488-LE і реєстратор Axis S3016»; «Прибуття фур із матеріалами» у стрічці «Потік зміни» | межі модуля |
| `factory3d_iot_sim` SPEC §8.13, §9.1 R-29/R-30, §9.3 S-05/S-06, Додаток A 654–661 | ADAM-6060 unit 86 (DI0/DI1/DI4, DO0/DO2/DO4 — GATE-W; DI2/DI3/DI5, DO1/DO3 — GATE-E); JSON Axis LPV (`plateText`, `plateUnicode`, `plateConfidence`, `carState`, `carMoveDirection`, `plateList`, `plateListDescription`, `sensorProviderID`, `GEOtarget`, `capture_timestamp`); SICS `S/SI/SIR/Z/T/TA/I2/I4/@`, дискретність 20 кг, НПВ 60 000; `bookings[]` з API-01; маси: аркуш ДСП16 56 кг, МДФ18 70, ХДФ3 12, палета ГП 420, тара фури 14 000 | адреси сигналів, формат подій, плагін `sics`, приклади чисел у R-12, ТК-01…ТК-06 |

### 1.2 Ролі й сценарії використання

| Роль (група) | Що робить | Де (меню) |
|---|---|---|
| Диспетчер двору (`factory3d_yard.group_f3d_yard_dispatcher`) | планує рейси й бронює ворота (слоти), приймає заявки постачальників, керує чергою («викликати на ворота»), переносить/скасовує, відхиляє, бачить звіти; у ручному режимі може відкрити шлагбаум | Завод 3D → Двір → Диспетчерська (kanban), Бронювання (Gantt/календар), Рейси, Звіти |
| Охорона КПП (`group_f3d_yard_security`) | на планшеті бачить фури на КПП (LPR), пропускає/відхиляє, створює рейс для фури без броні (у межах ліміту), фіксує зважування, відкриває шлагбаум вручну | Завод 3D → Двір → Екран КПП |
| Комірник (`stock.group_stock_user`) | бачить рейс із документа приймання/відвантаження, нетто з автоваг і звірку з кількістю, підтверджує початок/кінець розвантаження | Склад → Приймання/Відвантаження (вкладка «Двір»), пакет |
| Менеджер двору (`group_f3d_yard_manager` ⊂ `factory3d_base.group_f3d_manager`) | налаштовує ворота/шлагбауми/ваги, допуски, ліміти, режим авто/ручний, строки зберігання | Завод 3D → Двір → Налаштування; Налаштування → Завод 3D → Двір |
| Адміністратор (`factory3d_base.group_f3d_admin`) | стоп-крани `read_enabled`/`write_enabled`, джерела телеметрії, токени | Налаштування → Завод 3D |
| Постачальник (портал) | **v1 — ні** (Q-06); модель бронювання має `source='supplier'` і стан `requested` під майбутній портал | — |
| Колектор (`services/collector`) | читає ADAM (Modbus), ваги (плагін `sics`), приймає POST Axis LPV (`http_push`), виконує команди на шлагбаум | без UI |
| Переглядач 3D | показує фури на КПП/у черзі/біля воріт, стан шлагбаумів, ваги | розділ `yard` payload |

Типові сценарії: (1) диспетчер бронює `DOCK-W2` 13:00–14:00 під `WH/IN/00131` → рейс `planned`; (2) фура
під'їжджає до `GATE-W`, камера `CAM-05` надсилає номер → рейс знайдено → стан `arrived`, у режимі `auto`
шлагбаум відкривається командою через колектор, рейс `queued`/`at_dock`; (3) фура без броні
(`truck_no_booking`) → охорона бачить тривогу на екрані КПП, створює рейс «без броні» або відхиляє;
(4) зважування брутто на в'їзді й тари на виїзді → нетто у приймання, звірка з кількістю документа ±2 %;
(5) кінець дня — звіт: час біля воріт, очікування, простої воріт, за перевізниками.

### 1.3 Функціональні вимоги

| ID | Вимога (перевірювана) |
|---|---|
| FR-01 | Модель `f3d.yard.visit` описує рейс сторонньої фури: номер `YV/рік/00001`, тип (`incoming`/`outgoing`/`other`), перевізник і водій (`res.partner`), держномер, пакет `stock.picking.batch` (→ документи), ворота, планове вікно, 10 станів (SPEC §10) з часовою міткою кожного переходу, зважування, події LPR, обчислені тривалості (очікування, біля воріт, загальна, запізнення). |
| FR-02 | Бронювання воріт — окрема модель `f3d.yard.booking` (A-01): слот (`slot_start`/`slot_end`), ворота, рейс, джерело (`dispatcher`/`supplier`/`walk_in`/`migration`), стан (`requested`/`confirmed`/`cancelled`); підтверджений слот записується в `stock.picking.batch.dock_id/scheduled_date/end_date` рейсу, тому стандартний Gantt диспетчеризації лишається істинним. |
| FR-03 | Два підтверджені бронювання на одні ворота не можуть перетинатися в часі (`ValidationError`); перетин із буфером `dock_turnaround_min` (15 хв) або поза робочим календарем — попередження, не блокування (R-03). |
| FR-04 | Бронювання воріт, що не приймають категорію товарів документів пакета (`stock.location.f3d_accepts`, CB-05), показує попередження base `f3d_dock_warning` і власне попередження в бронюванні; не блокує (R-04). |
| FR-05 | Черга на в'їзд: правило вибору наступної фури на вільні ворота (R-05): пріоритет диспетчера → заброньований слот (почався або починається за ≤ 30 хв), ранішій перший → без броні за часом прибуття; «Викликати на ворота» — кнопка диспетчера/охорони; авторежим — параметр. |
| FR-06 | Фура без броні: подія LPR без збігу → тривога на екрані КПП; охорона створює рейс `walk_in` (ліміт `walk_in_limit_per_day`, за ліміту — лише диспетчер) або відхиляє з причиною; шлагбаум для незбігу ніколи не відкривається автоматично (R-06). |
| FR-07 | Подія LPR (`f3d.yard.lpr.event`) приймається з телеметрії через хук `f3d.push.handler` (CT-08, маршрут `lpr`), зберігає номер (сирий, Unicode, нормалізований), довіру, камеру, напрямок, `carState`, час камери, знімок (вкладення або URL), результат зіставлення; дублікати за `carID`+`sensorProviderID`+`packetCounter` ігноруються (R-07, R-08). |
| FR-08 | Авто-ідентифікація рейсу за номером: нормалізація кирилиця/латиниця, пошук серед рейсів у станах `planned`/`arrived`/`queued` у вікні ±`lpr_match_window_h`, довіра ≥ `lpr_min_confidence`; резервне зіставлення за `plateListDescription` (назва пакета/документа), яке заповнює порожній держномер рейсу (R-08). |
| FR-09 | Команда шлагбауму (відкрити/закрити/тримати) створюється як `f3d.command` телеметрії на сигнал `yard/gates/<G>/cmd_*` лише якщо: `factory3d.yard.write_enabled=True`, користувач — охорона/диспетчер (або авторежим за збігом із бронню), фотоелемент не перекритий, немає незавершеної команди за `cmd_cooldown_s`; інакше `UserError` з причиною (R-15). |
| FR-10 | Безпека шлагбаума: після команди очікується `DI open=1` за `open_timeout_s` (10 с), інакше помилка воріт і активність охороні; «тримати відкритим» не довше `hold_max_min`; режим `manual` вимикає авто-відкриття; антипрохід — проїзд петлі без дозволу (лічильник `passes_today` > виданих дозволів) → тривога `tailgate`; друга поява номера після `left` — новий рейс/подія, не повтор (R-16, R-17). |
| FR-11 | Зважування `f3d.yard.weighing`: вид (`in`/`out`/`check`), ваги, брутто/тара/нетто, час, стабільність, джерело (`auto`/`manual`), рейс, документ; значення береться з сигналів `yard/scale/<S>/weight_kg` і `stable` не старіших `weigh_max_age_s`, ≥ `min_kg` і ≤ `max_kg` (R-10, R-11). |
| FR-12 | Нетто рейсу = |брутто − тара|; для приймання брутто — на в'їзді, тара — на виїзді; для відвантаження навпаки. Нетто пишеться в `stock.picking.f3d_net_weight_kg`; очікувана маса = Σ `product_uom_qty × product.weight` (кг); звірка `ok` / `deviation` (> max(`net_tolerance_pct`, `net_tolerance_kg`)) / `no_reference` (маса документа 0) — попередження комірнику, не блокування (R-12). |
| FR-13 | Автозахоплення зважування: два послідовні стабільні показання ≥ `min_kg` з різницею ≤ 2 дискретності → запис; прив'язка до єдиного рейсу, що чекає зважування; інакше «непризначене» зважування для охорони (R-11). |
| FR-14 | Розширення `stock.picking`: рейс (через пакет), нетто, очікувана маса, звірка, кнопка «Рейс»; `stock.picking.batch`: рейси, активний рейс, стан, держномер, кнопка «Створити рейс»; `res.partner`: ознаки перевізника/водія, документ водія, типовий держномер, лічильник рейсів; `delivery.carrier.f3d_partner_id` — контакт перевізника. |
| FR-15 | Довідник воріт/КПП `f3d.yard.gate`: код сцени (`GATE-W`, `GATE-E`), напрямок, обладнання, зона, камера LPR, джерело ADAM і PDU-адреси DI/DO (з P-11 §8.13.1), режим `auto`/`manual`, стан (із сигналів), лічильники, останній номер; ваги `f3d.yard.scale` (`TRUCK-SCALE`): джерело `sics`, межі, останнє показання, стан захоплення. |
| FR-16 | Сигнали двору (8 з каталогу iot_sim 654–661 + 10 нових: петля, фотоелемент, 3 команди на ворота) і 3 джерела (`modbus_tcp` ADAM unit 86, `sics` ваги, `http_push` маршрут `lpr`) створюються data-файлами модуля з `module='yard'` (CT-09), ідемпотентно за `code`. |
| FR-17 | Плагін колектора `sics` (`services/collector_plugins/f3d_collector_yard`): TCP ASCII MT-SICS Level 0/1 (`SI` опитування або `SIR` потік, `S`, `Z`, `T`, `TA`, `TAC`, `I2`, `I4`, `@`), розбір формату «ID␣статус␣вага(10)␣одиниця», одиниці `kg`/`t`/`lb` → кг, стабільність `S`/`D`, перевантаження `+`/`−` → якість `bad`; `write()` лише `Z`/`T`/`TAC`/`TA` при `write_enabled`; health. |
| FR-18 | Диспетчерська: kanban рейсів за станами (сьогодні), Gantt бронювань за воротами (`web_gantt`), календар бронювань, посилання на стандартний Gantt диспетчеризації `stock_fleet_enterprise`; форма рейсу з кнопками «Прибула», «Пропустити», «На ворота», «Початок/кінець операції», «Зважити», «Виїхала», «Відхилити», «Показати в 3D». |
| FR-19 | Екран КПП — клієнтська дія для планшета: три колонки (на КПП / у дворі / останні події LPR), великі кнопки «Пропустити», «Відхилити», «Створити рейс», «Зважити», «Відкрити шлагбаум», оновлення кожні `kpp_refresh_s` (10 с) і за шиною. |
| FR-20 | Журнали: події LPR (список/форма зі знімком), зважування (список/форма), команди на ворота (список `f3d.command` з фільтром двору, поля `f3d_yard_gate_id`, `f3d_yard_visit_id`). |
| FR-21 | Звіти: pivot/graph рейсів (очікування, час біля воріт, загальний час, запізнення; за перевізником, партнером, воротами, днем) і SQL-вид простоїв воріт `f3d.yard.dock.report` (зайнятість/простій воріт за день). |
| FR-22 | Меню «Завод 3D → Двір» (sequence 60, CB-09) з підпунктами (SPEC §3); права: читання — `group_f3d_user` (без персональних даних водія), дії — охорона/диспетчер, налаштування — менеджер двору, стоп-крани — адміністратор. |
| FR-23 | Провайдер переглядача `f3d.viewer.provider.yard` (`_f3d_sequence=160`, розділ `yard`): фури з координатами (біля воріт, у черзі, на КПП, на вагах — зони base C.2), стан воріт/шлагбаумів, ваги, черга, підсумки; дельти — через шину viewer M-03 (повідомлення при кожному переході рейсу/воріт). |
| FR-24 | Персональні дані водія мінімальні (ПІБ, телефон, номер документа); документ і телефон видно лише охороні/диспетчеру; крон очищає документ/телефон у рейсах старших `visit_pii_keep_days` (90) і видаляє події LPR зі знімками старші `lpr_keep_days` (30). |
| FR-25 | Стоп-крани `factory3d.yard.read_enabled` (умовчання за `factory3d.base.environment`, CB-10), `factory3d.yard.write_enabled` (`False`), `neutralize.sql` (крони, режим воріт → `manual`, `write_enabled` → `False`); жоден токен у модулі не зберігається (токени колектора/маршрутів — у telemetry). |
| FR-26 | Міграція (`post_init_hook`): 6 пакетів-фур демо → 6 рейсів у стані `handling` з бронюваннями (слоти з `scheduled_date…end_date`), партнерами з документів, перевізниками з `carrier_id`, держномер `АА4512КТ` для `TRUCK-OUT-1` (картка ваг макета), одне контрольне зважування 21 380 кг; ідемпотентно; очікувані кількості — §2.8. |
| FR-27 | Тести: кожен AC покритий юніт-тестом (`TransactionCase`/`HttpCase`, теги `post_install`, `-at_install`, `f3d`, `f3d_yard`) або ТК на емуляторі (`truck_arrival`, `truck_no_booking`, SICS, команда DO0); плагін `sics` — pytest з фейковим TCP-сервером. |
| FR-28 | Робота без телеметрії онлайн (колектор не підключений, `read_enabled=False`): усі ручні операції (бронювання, стани, ручне введення ваги з поля `manual_weight_kg`) працюють; кнопки команд неактивні з поясненням. |

### 1.4 Межі: що не входить

- Турнікети, зчитувачі, відвідувачі-пішоходи, люди на території — `factory3d_access` (P-10). Двір лише
  публікує стан фур/воріт і читає нічого з access (CY-07 — інтерфейс для майбутнього зв'язку «водій на
  прохідній»).
- Власний транспорт заводу (навантажувачі, тягач) — `factory3d_telemetry` P-06 і base CB-06
  (`f3d_vehicle_id`); `fleet.vehicle` для сторонніх фур не створюємо (A-05).
- Відеоархів, перегляд потоку камер, NVR — поза Odoo; у події LPR лише знімок/URL.
- Портал постачальника для самостійного бронювання — Q-06 (модель готова, контролера немає).
- Керування списками дозволених номерів у самій камері (Axis LPV allow-list через VAPIX) — Q-07.
- Розрахунок вартості доставки, маршрути, карта (`stock_fleet_enterprise` Map/Mapbox) — стандарт.
- Сигнали пожежі → «тримати відкритим» шлагбаум — виконує емулятор/контролер (iot_sim R-25 ставить DO4
  сам); модуль лише показує стан `held`. Зв'язка з `factory3d_fire_safety` — поза v1.

## 2. Технічна реалізація

### 2.1 Місце в системі

`depends`: `factory3d_base`, `factory3d_telemetry`, `stock_picking_batch`, `stock_fleet` (поля `dock_id`,
`driver_id`, `vehicle_category_id`, `end_date` — живуть у `stock_fleet`, не в `stock_picking_batch`; A-02),
`delivery`, `web_gantt`, `mail`. `factory3d_viewer` — optional (провайдер і шина через перевірку реєстру).
`stock_fleet_enterprise` — не в `depends` (бере участь лише як посилання на стандартний Gantt, якщо
встановлений).

Що бере з інших модулів:

| Звідки | Що | Для чого |
|---|---|---|
| base CB-01 | домішка `f3d.scene.mixin` (`f3d_code`, `search_f3d`, `f3d_resolve`), R-01 формат коду | `f3d.yard.gate.code`, `f3d.yard.scale.code`, пошук обладнання `GATE-W`, `TRUCK-SCALE`, `CAM-05` |
| base CB-05 | ворота = `stock.location` з `f3d_kind='dock'`, `f3d_side`, `f3d_dock_no`, `f3d_accepts`, `f3d_x`, `f3d_y`, `f3d_zone_id`; `stock.picking.type.dock_ids` | домен `dock_id` бронювання/рейсу, попередження категорій, координати фур біля воріт |
| base CB-06 | `stock.picking.batch.f3d_code` (`TRUCK-IN-1`), `f3d_truck`, `f3d_vehicle_id`; related на `stock.picking` | код сцени фури в провайдері; міграція |
| base CB-09, CB-10, CB-12 | меню `menu_f3d_root` (sequence 60), групи `group_f3d_user/manager/admin`, `factory3d.base.environment`, межі території | меню, права, умовчання стоп-кранів, перевірка координат |
| base Додаток C.2 | зони `Z-GATE-W`, `Z-GATE-E`, `Z-YARD-W`, `Z-YARD-E`, `Z-KPP`, `Z-PARKING` (`zone_at`) | зона рейсу за координатою, провайдер |
| telemetry CT-01 | `f3d.source`, `f3d.signal` (`code`, `address`, `last_value`, `last_ts`, `status`, `module`), `f3d.command` (`queued→sent→done/failed/expired`) | сигнали двору, команди на ворота |
| telemetry CT-02, CT-03 | інтерфейс `SourcePlugin`, entry point `factory3d_collector.plugins`, JSON-схеми адрес (Modbus `addr` — PDU 0-based) | плагін `sics`, адреси ADAM |
| telemetry CT-05 | пороги/заявки ТО — лише поля на сигналі | «шлагбаум відкритий > 10 хв» (warn без заявки), «ваги офлайн» |
| telemetry CT-08 | хук `f3d.push.handler`: `_f3d_push_routes=('lpr',)`, `_f3d_handle_push(route, event)` | приймання подій Axis LPV |
| telemetry CT-09 | `module='yard'` за префіксом `yard/*` | власність сигналів |
| telemetry FR-21/A-08 | команди на пристрої лише через `f3d.command` + колектор; 4 запобіжники `write` | команди шлагбаума |
| viewer M-01, M-03 | `f3d.viewer.provider` (`_f3d_sequence`, `_f3d_sections`, `_f3d_viewer_collect`), `f3d.viewer.event._notify(model, codes, kind)` | розділ `yard`, живі оновлення |
| viewer C-05 | `ir.actions.client` `f3d_viewer.action` з `params.code`/`picking` | «Показати в 3D» на рейсі |
| iot_sim P-11 §8.13 | адреси ADAM-6060 unit 86, формат Axis LPV, діалект SICS, S-05/S-06, API-01 `bookings[]` | data сигналів, плагін, ТК |

Що віддає іншим (контракти **CY-xx**, посилатися як `factory3d_yard CY-xx`):

| ID | Контракт | Споживач |
|---|---|---|
| CY-01 | `f3d.yard.visit` (SPEC M-01): поля `name`, `state`, `visit_type`, `plate`, `plate_norm`, `partner_id`, `carrier_id`, `driver_id`, `batch_id`, `dock_id`, `planned_start`, `planned_end`, часові мітки `*_at`, `gross_kg`/`tare_kg`/`net_kg`, `scene_code`; методи `action_arrive`, `action_admit`, `action_call_to_dock`, `action_reject`, `action_leave`; пошук `_find_by_plate(plate_norm, ts)` | access (водій на прохідній), viewer, звіти |
| CY-02 | `stock.picking.batch.f3d_visit_id`, `f3d_visit_state`, `f3d_plate`; `stock.picking.f3d_visit_id`, `f3d_net_weight_kg`, `f3d_expected_weight_kg`, `f3d_weight_check` | viewer (`pickings[].truck` лишається base CB-06), stock |
| CY-03 | `f3d.yard.gate` (`code`, `direction`, `state`, `mode`, `last_plate`, `passes_today`) і метод `action_command(kind)` (`open`/`close`/`hold`/`release`) з усіма перевірками R-15 | access (евакуація — Q-10), viewer |
| CY-04 | Сигнали `yard/gates/<G>/{state,loop,photocell,passes_today,cmd_open,cmd_close,cmd_hold}`, `yard/lpr/<CAM>/plate`, `yard/scale/<S>/{weight_kg,stable}`; джерела `SRC-ADAM-IO7`, `SRC-TRUCK-SCALE`, `SRC-LPR` (xml-id SPEC §5) | telemetry (каталог), iot_sim (звірка адрес) |
| CY-05 | Плагін `sics` (SPEC §8): тип джерела `sics`, `params` `{host, port, mode, period_s, timeout_s, unit}`, адреса сигналу `{"cmd": "SI", "field": "weight"|"stable"}`, запис `{"cmd": "Z"|"T"|"TAC"|"TA", "value": kg}` | telemetry (реєстр плагінів), колектор |
| CY-06 | Розділ `yard` payload переглядача (SPEC §9 R-20): `gates{}`, `scale{}`, `trucks[]` (з `x`, `y`, `rz`, `zone`, `state`, `dock`, `picking`), `queue{west[],east[]}`, `stats{}`; шина: `_notify('f3d.yard.visit', [name, scene_code, dock_code], 'doc')`, `_notify('f3d.yard.gate', [code], 'state')` | viewer (клієнт малює фури без коду сцени за `x/y` — Q-08) |
| CY-07 | `res.partner.f3d_is_driver`, `f3d_is_carrier`, `f3d_carrier_id`; `f3d.yard.visit.driver_id` — єдине місце «водій рейсу» | access (пропуск водія на КПП-пішохідній — поза v1) |
| CY-08 | `f3d.command.f3d_yard_gate_id`, `f3d_yard_visit_id` (M-18) — журнал команд шлагбаума в стандартному журналі телеметрії | telemetry (меню «Команди» показує й двір) |

### 2.2 Архітектурна схема

```
 Axis P1488-LE + LPV      CAME GARD LS6 ×2        АКСІС 60-18-К-Е (термінал)          [емулятор iot_sim: ті самі протоколи]
   CAM-05 / CAM-06          GATE-W / GATE-E          TRUCK-SCALE
        │ HTTP POST JSON         │ сухі контакти / вхід      │ RS-232 → TCP-шлюз (ПРИПУЩЕННЯ Q-05)
        │ (carState new/lost)    ▼                           ▼
        │                 ADAM-6060 (unit 86)          SICS ASCII TCP :4001
        │                 DI0..5 / DO0..5                    │
        ▼                        │ Modbus TCP :502           │
┌───────────────────────────── services/collector (telemetry) ───────────────────────────────────────────┐
│ plugins/http_push  POST /f3d/push/lpr ──► event ──► Odoo API-05 /f3d/telemetry/event                   │
│ plugins/modbus_tcp  poll 1 с: DI (fc 2), passes (fc 3); write coil (fc 5) ◄── commands API-06/07       │
│ plugins_yard: sics  SI/SIR 1–2 Гц → weight_kg, stable; write Z/T (лише F3D_WRITE_ENABLED=1)            │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
        │ push показань (API-02)        ▲ config (API-01)       │ event (API-05)         │ commands (API-06/07)
        ▼                               │                        ▼                        ▼
┌──────────────────────────────────────── Odoo 19 (factory3d_telemetry) ─────────────────────────────────┐
│ f3d.source (3 двору) · f3d.signal (18 двору, module=yard) · f3d.reading · f3d.command (черга)          │
│ f3d.push.handler ──route 'lpr'──► factory3d_yard                                                        │
└───────────────┬───────────────────────────────┬────────────────────────────────┬───────────────────────┘
                ▼                               ▼                                ▼
┌───────────────────────────────────────── factory3d_yard ───────────────────────────────────────────────┐
│ f3d.yard.lpr.event ──R-08 зіставлення──► f3d.yard.visit (стани §10) ◄── f3d.yard.booking (слоти, R-03)  │
│        │ незбіг → екран КПП (walk-in R-06)        │ admit → f3d.yard.gate.action_command('open') R-15  │
│ f3d.signal(write last_value) ──► f3d.yard.scale ──R-11──► f3d.yard.weighing ──R-12──► stock.picking     │
│ stock.picking.batch (dock_id/scheduled_date/end_date ⇐ booking) · res.partner (перевізник, водій)      │
│ f3d.viewer.provider.yard (160) → payload.yard · f3d.viewer.event._notify → bus f3d_viewer              │
│ Екран КПП (OWL client action, RPC kpp_data/kpp_action) · Диспетчерська (kanban/gantt/calendar)         │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Потоки: (1) пристрої → колектор → Odoo (показання, події); (2) Odoo → колектор → ADAM/ваги (команди,
лише `write_enabled`); (3) Odoo → переглядач (шина); (4) користувачі (диспетчерська, КПП, склад).
Odoo ніколи не ходить у мережу двору сам (каркас §4).

### 2.3 Нові й розширені об'єкти — огляд

| Модель | Тип | Призначення | Хто пише | Хто читає |
|---|---|---|---|---|
| `f3d.yard.visit` (M-01) | нова, `mail.thread`, `mail.activity.mixin` | рейс сторонньої фури: стани, мітки часу, ваги, зв'язок із пакетом | диспетчер, охорона, хук LPR, автозахоплення ваги, міграція | усі (без PII), viewer, звіти |
| `f3d.yard.booking` (M-02) | нова, `mail.thread` | слот воріт: час, ворота, рейс, джерело, стан; конфлікти | диспетчер (портал — Q-06), міграція | диспетчер, Gantt, рейс |
| `f3d.yard.gate` (M-03) | нова (+ `f3d.scene.mixin`) | КПП/шлагбаум: адреси I/O, камера, режим, стан, лічильники | data, менеджер двору | КПП, провайдер, команди |
| `f3d.yard.lpr.event` (M-04) | нова, `_log_access=False` | подія розпізнавання номера | хук `lpr` | охорона, рейс, журнал |
| `f3d.yard.weighing` (M-05) | нова | зважування на автовагах | автозахоплення, охорона/комірник (ручне) | рейс, приймання, звіти |
| `f3d.yard.scale` (M-06) | нова (+ `f3d.scene.mixin`) | автоваги: джерело, межі, останнє показання, стан захоплення | data, сигнали (через M-13) | КПП, провайдер |
| `stock.picking.batch` (M-07) | розширення | рейси пакета, активний рейс, держномер; синхронізація слоту; кнопка «Створити рейс» | бронювання (sync), диспетчер | стандартний Gantt, viewer |
| `stock.picking` (M-08) | розширення | рейс, нетто, очікувана маса, звірка | зважування (R-12) | комірник |
| `res.partner` (M-09), `delivery.carrier` (M-10) | розширення | перевізник/водій, документ водія, контакт перевізника | диспетчер | рейс |
| `res.config.settings` (M-11) | розширення | стоп-крани, допуски, ліміти, строки зберігання | адміністратор/менеджер | модуль |
| `f3d.push.handler.yard` (M-12) | реалізація хука CT-08 | маршрут `lpr` → `f3d.yard.lpr.event` | telemetry API-05 | — |
| `f3d.signal` (M-13) | розширення `write()` | `yard/scale/*` → `f3d.yard.scale._on_reading` | telemetry push | — |
| `f3d.viewer.provider.yard` (M-14) | провайдер (160) | розділ `yard` | — | viewer |
| `f3d.yard.dock.report` (M-15) | SQL-вид | зайнятість/простій воріт за день | — | звіти |
| `f3d.yard.walkin.wizard` (M-16), `f3d.yard.reject.wizard` (M-17) | transient | створення рейсу без броні з події LPR; причина відхилення | охорона/диспетчер | — |
| `f3d.command` (M-18) | розширення | `f3d_yard_gate_id`, `f3d_yard_visit_id` | команди воріт | журнал |

### 2.4 Інтеграції

| Пристрій/система | Код | Протокол (P-xx) | Напрямок | Частота | При недоступності |
|---|---|---|---|---|---|
| Шлагбауми CAME GARD LS6 через ADAM-6060 | GATE-W, GATE-E | P-11 §8.13.1: Modbus TCP, unit 86: DI0/DI2 «стріла відкрита», DI1/DI3 «петля», DI4/DI5 «фотоелемент», лічильники DI1/DI3 (HR 40003–40004 / 40007–40008, u32, молодше слово перше — ADAM); DO0/DO1 «відкрити» (імпульс ≥ 1 с), DO2/DO3 «закрити», DO4 «тримати»; плагін `modbus_tcp` telemetry; PDU-адреси в `f3d.signal.address.addr` (CT-03) | читання DI/лічильників; запис DO лише при 4 запобіжниках `write` (telemetry §2.6) | опитування 1 с (DI), 10 с (лічильники); команди — за подією, `expires_at` 30 с | сигнали `stale` → ворота `state='unknown'`, кнопки команд неактивні, охорона відкриває стрілу з пульта CAME вручну; рейси ведуться вручну (FR-28) |
| Камери Axis P1488-LE + License Plate Verifier | CAM-05 (GATE-W, `carMoveDirection=in`), CAM-06 (GATE-E, `out`) | P-11 §8.13.2: HTTP POST JSON (Axis «License plate verifier API», developer.axis.com, переглянуто 14.10.2026: `carState` `new`/`update`/`lost`, `plateText`, `plateUnicode`, `plateConfidence`, `plateList`, `plateListDescription`, `capture_timestamp` UNIX мс, `sensorProviderID`, `GEOtarget`, `imageFile`/`imageArray` base64 за `skip_image_in_post=false`; автентифікація `x_auth_key`/basic) → колектор `POST /f3d/push/lpr` (telemetry §2.4) → Odoo API-05 → хук `lpr` | пристрій → Odoo | за подією (≈ 2–3 POST на фуру) | камера буферизує (`use_event_buffer`); колектор — буфер SQLite; дублікати відкидаються (R-07); без камери — охорона вводить номер вручну |
| Автоваги АКСІС 60-18-К-Е, термінал ME-01 | TRUCK-SCALE | P-11 §8.13.3: ASCII MT-SICS по TCP :4001 (METTLER TOLEDO «MT-SICS Reference Manual IND400», 30881805 A, 2024, mt.com, переглянуто 14.10.2026: §2.2.1 формат відповіді з вагою, §4.7 `S`, §4.8 `SI`, §4.9 `SIR`, §4.10 `Z`, §4.11 `ZI`, §4.12 `@`, §5.6 `T`, §5.7 `TA`, §5.8 `TAC`); плагін `sics` цього модуля; ПРИПУЩЕННЯ: індикатор АКСІС підтримує SICS або RS-232→TCP-шлюз із SICS-сумісним діалектом (Q-05) | читання; запис `Z`/`T` лише `write_enabled` (не використовується модулем у v1 — нетто рахуємо в Odoo) | `SI` 1 с (режим `poll`) або `SIR` ≈ 2 Гц (режим `stream`); показання в Odoo — пакет 5 с | ваги `offline` → кнопка «Зважити» бере ручне введення (`manual_weight_kg`, `source='manual'`), активність менеджеру; автозахоплення вимкнене |
| Емулятор `factory3d_iot_sim` | ті самі коди | ті самі протоколи; сценарії S-05 `truck_no_booking`, S-06 `truck_arrival`; API-01 `bookings[]` ← `stock.picking.batch` (+ `f3d_plate`, Q-02) | як вище | — | — |
| `factory3d_telemetry` (Odoo) | — | ORM: `f3d.source`, `f3d.signal`, `f3d.command`, хук `f3d.push.handler` | обидва | — | без телеметрії модуль не встановлюється (`depends`) |
| `factory3d_viewer` (Odoo, optional) | — | хук провайдера, шина | yard → viewer | за зміною | без viewer — провайдер і шина пропускаються (`'f3d.viewer.event' in env`) |

### 2.5 Потік даних від пристрою до екрана

Приклад 1 — фура з бронюванням (сценарій S-06 `truck_arrival BATCH/IN/00001`):
1. Диспетчер створив рейс `YV/2026/00001` (`TRUCK-IN-1`, `Плитсервіс (демо)`, пакет `BATCH/IN/00001`,
   `WH/IN/00128`) і підтвердив бронювання `DOCK-W1` 09:30–10:30 (Київ) → `stock.picking.batch.dock_id=
   WH/Вхід/Ворота 1`, `scheduled_date=2026-10-12 06:30 UTC`, `end_date=07:30 UTC`; стан рейсу `planned`.
2. 09:10 камера `CAM-05` надсилає POST (`carState=new`, `plateText="AA4512KT"`, `plateUnicode="АА4512КТ"`,
   `plateConfidence="0.912340"`, `GEOtarget="GATE-W"`, `capture_timestamp="1791961800000"`); колектор →
   `POST /f3d/telemetry/event {route:'lpr', body:{…}}` → telemetry викликає
   `env['f3d.push.handler.yard']._f3d_handle_push('lpr', event)`.
3. M-12 створює `f3d.yard.lpr.event` (`plate_norm="AA4512KT"`, `gate_id=GATE-W`, `direction='in'`,
   `confidence=0.912`), R-08 знаходить рейс за `plate_norm` (або за `plateListDescription="BATCH/IN/00001 …"`)
   → `event.visit_id`, `match_state='matched'`; рейс `planned → arrived` (`arrived_at` = час камери).
4. Ворота `GATE-W` у режимі `auto`, `write_enabled=True`: R-15 перевіряє фотоелемент (`yard/gates/GATE-W/photocell`
   `last_value=0`, не `stale`), відсутність команди за 30 с, рейс `arrived` з підтвердженим бронюванням, час
   у вікні [`planned_start − early_min`, `planned_end + late_min`] → `f3d.command` на `yard/gates/GATE-W/cmd_open`
   (`value=1`, `expires_at=+30 с`, `f3d_yard_gate_id`, `f3d_yard_visit_id`); рейс → `queued`
   (`admitted_at`), `gate.admitted_today += 1`.
5. Колектор забирає команду (API-06), `modbus_tcp.write` coil PDU 16 unit 86 = 1 (імпульс), звіт `done`
   (API-07). Через ≤ 5 с емулятор ставить DI0=1 → сигнал `yard/gates/GATE-W/state=1` → ворота `state='open'`;
   якщо за `open_timeout_s=10` DI0 не став 1 → `gate.last_error='Немає підтвердження відкриття'`, активність
   охороні (R-16).
6. Петля DI1 → лічильник `passes_today` 7→8; R-17: `passes_today − passes_day_start (7) = 1 ≤ admitted_today (1)`
   — норма.
7. На вагах: `SIR` потік → `yard/scale/TRUCK-SCALE/weight_kg` 0 → 25 200 (`S D` 3 с, далі `S S`);
   M-13 передає кожен `last_value` у `f3d.yard.scale._on_reading`; R-11: два стабільні показання ≥ 400 кг
   із різницею ≤ 40 кг → `f3d.yard.weighing` (`kind='in'`, `gross_kg=25200`, `source='auto'`) → єдиний рейс
   у `queued` з політикою `in_out` і без зважування `in` → `visit.gross_kg=25200`, `weighed_in_at`.
8. Диспетчер/авторежим: ворота `DOCK-W1` вільні → «На ворота» → `at_dock` (`at_dock_at`); комірник
   починає приймання → `handling` (`handling_start_at`; автоматично, коли перший `stock.move.line.quantity>0`
   у документах пакета — R-09); `WH/IN/00128` → `done` → `handling_end_at`, рейс → `weighed`? ні: →
   стан лишається `handling` до зважування на виїзді.
9. Виїзд: `CAM-06` POST (`out`) → подія зіставлена з тим самим рейсом (стан `handling`) → очікується тара;
   ваги: 14 000 кг стабільно → `weighing kind='out'`, `tare_kg=14000`; `net_kg=11200`; R-12:
   очікувана маса `WH/IN/00128` = (120+80)×56 = 11 200 кг (після кроку заповнення мас, §2.8) → `ok`
   (0 %); рейс → `weighed` (`weighed_out_at`); `GATE-E` авто-відкриття за R-15 → `left` (`left_at`),
   коли DI3 (петля) звільнилась або подія `lost` від `CAM-06`.
10. Кожен перехід → `f3d.viewer.event._notify('f3d.yard.visit', ['YV/2026/00001','TRUCK-IN-1','DOCK-W1'], 'doc')`
    → переглядач перечитує `yard` (provider 160) і показує фуру біля `DOCK-W1` з прогресом 0,6.

Приклад 2 — фура без броні (S-05 `truck_no_booking plate=АА1234КТ`): крок 3 не знаходить рейсу →
`match_state='unmatched'`, `kpp_alert=True`; екран КПП показує «Фура АА1234КТ без бронювання біля GATE-W»;
команда шлагбауму не створюється (R-06); охорона натискає «Створити рейс» → майстер M-16 (тип, партнер,
ворота за замовчуванням вільні того ж боку) → рейс `walk_in` у стані `arrived` з `booking_source='walk_in'`
(якщо `walk_in_count_today < walk_in_limit_per_day=5`; інакше кнопка недоступна, активність диспетчеру) →
далі як приклад 1 з кроку 4 (у режимі `auto` — відкриття після явного «Пропустити», бо броні немає); або
«Відхилити» → M-17 причина → рейс `rejected` (для журналу) і подія `handled`. Емулятор через `wait_min=10`
забирає фуру (`carState=lost`) → подія `lost_at`; відкритий unmatched без дії через `arrival_timeout_min`
→ `kpp_alert=False`, `match_state='expired'`.

### 2.6 Безпека

- **Групи** (`security/f3d_yard_security.xml`, привілей «Двір» у категорії `factory3d_base.module_category_factory3d`):
  `group_f3d_yard_security` (Охорона КПП) ⊂ `group_f3d_yard_dispatcher` (Диспетчер двору) ⊂
  `group_f3d_yard_manager` (Менеджер двору; також ⊂ `factory3d_base.group_f3d_manager`);
  `factory3d_base.group_f3d_admin` ⊃ `group_f3d_yard_manager`. Читання рейсів/бронювань/воріт/ваг —
  `factory3d_base.group_f3d_user` і `stock.group_stock_user`; персональні поля водія (`driver_doc`,
  `driver_phone`) — `groups` на полях для охорони/диспетчера.
- **Стоп-крани**: `factory3d.yard.read_enabled` (умовчання `environment == 'test'`, CB-10; при `False`
  модуль ігнорує показання/події: хук `lpr` пише подію з `ignored=True`, автозахоплення вимкнене, ворота
  `unknown`), `factory3d.yard.write_enabled` (`False`; команди на ворота/ваги не створюються). Додатково
  telemetry вимагає `write_enabled` на модулі-власнику сигналу, джерелі, сигналі й `F3D_WRITE_ENABLED=1`
  у колекторі — команда шлагбаума проходить лише через усі п'ять запобіжників.
- **Команди**: лише `action_command()` воріт (серверна перевірка групи `group_f3d_yard_security` або авторежим
  із `uid` технічного користувача `SUPERUSER_ID`, але з `f3d_yard_visit_id` та `reason='auto_booking'`);
  журнал — `f3d.command` + chatter воріт і рейсу; `hold` обмежено `hold_max_min` (крон знімає, пише
  `release`).
- **Токени**: у модулі немає; токен маршруту `lpr` і колектора — telemetry (`F3D_HTTP_PUSH_TOKEN_LPR`,
  хеш колектора). Axis LPV підтримує `x_auth_key`-заголовок — у проді камера шле токен; емулятор — Q-03.
- **Персональні дані**: мінімум (ПІБ водія як `res.partner`, телефон, номер документа — Char без копій
  документів); знімки LPR — вкладення на події з ротацією `lpr_keep_days` (30), текст номера — `visit_pii_keep_days`
  (90) для подій без рейсу; у рейсі держномер лишається (операційні дані), документ/телефон водія
  очищаються кроном (FR-24). Експорт персональних полів — лише диспетчер. Логи без номерів документів.
- **Валідація входу**: `plate` — `^[A-ZА-ЯІЇЄ0-9 -]{2,16}$` після `upper()`; JSON Axis — лише перелічені ключі,
  розмір тіла ≤ 2 МБ (telemetry обмежує), base64 знімків ≤ 1 МБ; `sensorProviderID` → лише відомі камери
  воріт (інакше подія `unknown_camera`, без зіставлення); адреси DI/DO — Integer 0…65535, `unit` 1…247.
- **Що заборонено**: прямі з'єднання Odoo з ADAM/вагами/камерами; запис тари в ваги (`TA`) у v1; авто-відкриття
  для незбігу/без броні; відкриття при перекритому фотоелементі; `sudo()` у контролерах (контролерів немає);
  видалення рейсів зі станом ≥ `arrived` (лише `cancelled` через кнопку).
- `neutralize.sql`: `write_enabled=False`, усі крони модуля `active=false`, `f3d_yard_gate.mode='manual'`
  (SPEC §5.5).

### 2.7 Продуктивність і обсяги

- Рейси: 14 воріт × ≤ 6 слотів = до ≈ 40 рейсів/добу (демо — 6); бронювань ≈ 50/добу з переносами;
  зважувань ≈ 60/добу; подій LPR ≈ 3 на рейс × 2 камери ≈ 150/добу (+ незбіги); команд ≈ 80/добу.
  За рік: ≈ 15 000 рейсів, 55 000 подій LPR — без партиціонування.
- Знімки: 2 × ≤ 100 КБ на подію → ≈ 30 МБ/добу → ротація 30 діб ≈ 1 ГБ у `ir.attachment` (файлове
  сховище); параметр `lpr_store_images=False` вимикає.
- Індекси: `f3d_yard_visit (state, planned_start)`, `(plate_norm)`, `(batch_id)`; `f3d_yard_booking
  (dock_id, slot_start, slot_end)` + `(state)`; `f3d_yard_lpr_event (ts)`, `(plate_norm, ts)`,
  `(dedup_key)` unique; `f3d_yard_weighing (scale_id, ts)`, `(visit_id)`.
- Гарячий шлях: `f3d.signal.write()` (M-13) виконується на кожному push телеметрії (18 сигналів, 5 с) —
  перевірка префікса в Python без запитів, ORM-читання ваг лише для `yard/scale/*` (2 сигнали).
- Екран КПП: RPC `kpp_data` ≤ 50 мс (сьогоднішні рейси ≤ 50, події ≤ 20); оновлення 10 с → ≤ 0,1 запиту/с
  на планшет. Провайдер `yard` ≤ 20 КБ, ≤ 30 мс.
- Ротація: крон добовий — події LPR > 30 діб, PII > 90 діб, непризначені зважування > 7 діб.

### 2.8 Міграція з демо-бази (x_* поля, data-модуль) і деінсталяція

`x_*`-полів у двору немає (їх мігрує base). `post_init_hook(env)` (`hooks/migrate.py`, ідемпотентно,
на чистій базі — усі кроки `skipped`):

| # | Крок | Джерело | Результат | Очікувано (копія демо після base) |
|---|---|---|---|---|
| 1 | `gates_and_scale` | data-файли (`GATE-W`, `GATE-E`, `TRUCK-SCALE`) + `maintenance.equipment.search_f3d` | `equipment_id`, `zone_id` (`Z-GATE-W`, `Z-GATE-E`), `camera_equipment_id` (`CAM-05`/`CAM-06` або `CCTV`) | `gates: 2`, `scales: 1`, `linked_equipment: 3` |
| 2 | `signals_and_sources` | data `f3d.source` (3), `f3d.signal` (18) з upsert за `code` (якщо telemetry уже імпортувала каталог iot_sim — оновлюються `address`, `module='yard'`, `source_id`) | сигнали прив'язані до джерел і обладнання | `signals: 18` (8 оновлених або створених + 10 нових), `sources: 3` |
| 3 | `product_weights` | iot_sim R-30 маси (ДСП16 56 кг, ДСП18 — 63 кг за пропорцією товщини 16→18 ПРИПУЩЕННЯ, МДФ18 70, ХДФ3 12) → `product.product.weight` **лише якщо 0** і `factory3d.yard.seed_product_weights=True` (умовчання `True` на тесті, `False` на проді) | звірка нетто має еталон для плит | `products_weighted: 7` (DSP16-SON, DSP16-WHT, DSP16-ANT, DSP16-WNG, DSP18-CON, MDF18-RAW, HDF3-WHT) — A-11, Q-09 |
| 4 | `visits_from_batches` | `stock.picking.batch` з `f3d_code` виду `TRUCK-*` (CB-06; 6) | рейс на пакет: `visit_type` за `picking_type_code` (`incoming`/`outgoing`), `partner_id` = `picking_ids[0].partner_id`, `carrier_id`: incoming → `partner_id`; outgoing → `delivery.carrier.f3d_partner_id` (крок 5) або партнер з такою ж назвою («Нова Пошта Вантаж (демо)» id 11) або партнер компанії для «Власний транспорт»; `plate='АА4512КТ'` лише для `TRUCK-OUT-1` (картка макета `infra.py:368`), решта порожні; `scene_code=f3d_code`; `state='handling'`, `arrived_at = scheduled_date − 20 хв`, `admitted_at = −15 хв`, `at_dock_at = scheduled_date`, `handling_start_at = scheduled_date`; `weighing_policy` за стороною | `visits: 6` (3 `incoming`, 3 `outgoing`), `with_plate: 1` |
| 5 | `carrier_partners` | `delivery.carrier` «Нова Пошта Вантаж (демо)» → `f3d_partner_id` = партнер id 11 (за назвою); «Власний транспорт» → партнер компанії; `res.partner.f3d_is_carrier=True` для них | | `carriers_linked: 2` |
| 6 | `bookings_from_batches` | `scheduled_date`, `end_date`, `dock_id` пакета | `f3d.yard.booking` `confirmed`, `source='migration'`; `visit.planned_start/end`, `dock_id` | `bookings: 6`, `conflicts: 0` |
| 7 | `weighing_from_card` | `infra.py:368` «АА 4512 КТ · брутто 21 380 кг · WH/OUT/00413» | `f3d.yard.weighing` `kind='check'`, `gross_kg=21380`, `source='migration'`, `visit` = рейс `TRUCK-OUT-1`, `picking_id=WH/OUT/00413`, `ts = scheduled_date` пакета; стан рейсу не змінюється | `weighings: 1` |
| 8 | `report` | — | `factory3d.yard.migration_report` JSON, `migration_state=done/skipped` | `done` |

Без base-міграції (пакети без `f3d_code`) крок 4 бере пакети з `description` виду `TRUCK-… · DOCK-…`
(формат `odoo_flows.step_docks`) — запасний шлях, `by_description: n`. Повторний запуск — «Повторити міграцію
двору» (меню Налаштування, `group_f3d_admin`) — лише доповнює відсутнє.

`uninstall_hook`: видаляє параметри `factory3d.yard.%`, свої крони; рейси, бронювання, зважування, події —
видаляє стандартна деінсталяція моделей модуля; `stock.picking.batch.dock_id/scheduled_date/end_date`,
`product.weight`, партнери, `f3d.source`/`f3d.signal` двору (належать telemetry-моделям) — не чіпаються
(сигнали лишаються з `module='yard'`; telemetry показує їх як «без власника»).

## 3. Налаштування системи

| Об'єкт | Параметр | Значення (тестовий сервер) | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `factory3d.yard.read_enabled` | `True` (бо `factory3d.base.environment=test`) | на проді після встановлення `False`; вмикає обробку показань/подій |
| `ir.config_parameter` | `factory3d.yard.write_enabled` | `False` → для ТК-04 ставити `True` | команди на шлагбаум; на проді вмикати лише після наладки з монтажником CAME |
| `ir.config_parameter` | `factory3d.yard.walk_in_allowed` / `walk_in_limit_per_day` | `True` / `5` | охорона створює рейси без броні до ліміту; далі — диспетчер |
| `ir.config_parameter` | `factory3d.yard.lpr_min_confidence` / `lpr_match_window_h` / `lpr_store_images` / `lpr_keep_days` | `0.80` / `4` / `True` / `30` | Axis віддає `plateConfidence` 0…1; вікно пошуку рейсу ± год від часу події; знімки |
| `ir.config_parameter` | `factory3d.yard.camera_tz` | `Europe/Kyiv` | розбір `datetime` камери, якщо немає `capture_timestamp` |
| `ir.config_parameter` | `factory3d.yard.net_tolerance_pct` / `net_tolerance_kg` / `weigh_max_age_s` / `scale_auto_capture` | `2.0` / `100` / `15` / `True` | допуск нетто = max(2 %, 100 кг); показання не старіше 15 с; автозахоплення |
| `ir.config_parameter` | `factory3d.yard.weighing_policy_west` / `weighing_policy_east` | `in_out` / `in_out` | політика нового рейсу за стороною воріт; `none` вимикає очікування зважування |
| `ir.config_parameter` | `factory3d.yard.slot_default_min` / `dock_turnaround_min` / `enforce_calendar` | `60` / `15` / `False` | тривалість слоту за замовчуванням; буфер між слотами (попередження); календар «Зміна 1» — лише попередження |
| `ir.config_parameter` | `factory3d.yard.early_min` / `late_min` | `60` / `120` | авто-допуск за бронню: не раніше ніж за 60 хв до слоту і не пізніше ніж 120 хв після початку |
| `ir.config_parameter` | `factory3d.yard.open_timeout_s` / `cmd_cooldown_s` / `hold_max_min` | `10` / `30` / `30` | CAME відкривається за 4–6 с, емулятор 5 с |
| `ir.config_parameter` | `factory3d.yard.auto_call_next` / `queue_slot_window_min` / `arrival_timeout_min` / `no_show_min` | `False` / `30` / `30` / `120` | авто «на ворота» при звільненні; вікно «слот починається»; незбіг без дії → `expired`; рейс без прибуття → позначка `is_no_show` |
| `ir.config_parameter` | `factory3d.yard.visit_pii_keep_days` / `kpp_refresh_s` / `seed_product_weights` | `90` / `10` / `True` | PII; оновлення екрана КПП; крок 3 міграції |
| `f3d.yard.gate` | `GATE-W`: `direction=in`, `mode` | `auto` (тест; після встановлення `manual`) | для ТК-04/ТК-05 менеджер ставить `auto` |
| `f3d.yard.gate` | `GATE-E`: `direction=out`, `mode`, `scale_id` | `auto`, `TRUCK-SCALE` | |
| `f3d.source` | `SRC-ADAM-IO7` (`modbus_tcp`): `params` | `{"host":"iot-sim","port":502,"unit":86,"timeout_s":2}` | у проді — IP модуля ADAM |
| `f3d.source` | `SRC-TRUCK-SCALE` (`sics`): `params` | `{"host":"iot-sim","port":4001,"mode":"stream","period_s":1,"timeout_s":5,"unit":"kg"}` | `mode=poll` для індикаторів без `SIR` |
| `f3d.source` | `SRC-LPR` (`http_push`): `params` | `{"route":"lpr"}` | токен маршруту — в env колектора (telemetry) |
| compose `iot_sim` env | `SIM_LPR_PUSH_URL` / `SIM_YARD_AUTOGATE` | `http://collector:8080/f3d/push/lpr` / `0` | `0` — шлагбаум чекає DO від Odoo (інакше ТК-04 не перевіряє команду) |
| compose `collector` env | `F3D_WRITE_ENABLED` / `F3D_ALLOW_HOSTS` | `1` на стенді ТК-04 / `iot-sim,mosquitto` | telemetry §3 |
| `ir.cron` | `cron_f3d_yard_queue` / `cron_f3d_yard_gc` / `cron_f3d_yard_day_reset` | 5 хв / 1 доба 03:00 / 1 доба 00:05 | §SPEC 6 |
| `res.users` | `f3d_yard_kpp` (планшет КПП) | групи: `group_f3d_yard_security`, `base.group_user` | створює адміністратор уручну; не в data |

## 4. Інструкція

**4.1 Забронювати ворота під приймання** (диспетчер). Завод 3D → Двір → Бронювання → «Створити» (або з
пакета `BATCH/IN/…` кнопка «Створити рейс»): ворота (список лише доків потрібної сторони), початок/кінець
(за замовчуванням 60 хв), рейс (новий: тип, постачальник, держномер якщо відомий, пакет із документами) →
«Підтвердити». Перетин із чужим слотом — помилка з назвою конфліктного бронювання; попередження про
категорію товарів («Ворота DOCK-W1 приймають: Плитні матеріали…») — перевірити ворота. Після підтвердження
рейс у стані «Заплановано», на Gantt «Диспетчеризація» з'являється смуга на воротах.

**4.2 Пропустити фуру на КПП** (охорона). Екран КПП (планшет): у колонці «На КПП» картка з номером, рейсом,
воротами та часом слоту. Зелена картка — номер збігся з бронюванням: «Пропустити» (у режимі «авто» стріла
вже відкрилася сама, картка показує «пропущено автоматично»). Жовта «Без бронювання»: «Створити рейс»
(тип, постачальник/клієнт; якщо кнопка сіра — ліміт на день вичерпано, дзвонити диспетчеру) або «Відхилити»
(причина). Червона «Помилка воріт»: стріла не відкрилась за 10 с — відкрити з пульта CAME, натиснути
«Відкрито вручну».

**4.3 Зважування** (охорона/комірник). Фура на вагах — на екрані КПП «Ваги: 25 200 кг · стабільно»;
за 5–10 с запис з'являється сам у колонці рейсу («Брутто 25 200»). Якщо не з'явився (ваги офлайн) —
«Зважити» → ввести показання з табло → «Записати». На виїзді — так само; нетто рахується і показується
в документі приймання (вкладка «Двір»): «Нетто 11 200 кг · за документом 11 200 · відхилення 0 %».
Відхилення понад допуск — помаранчева позначка й активність комірнику; документ не блокується.

**4.4 Фура без броні — рішення** (охорона, диспетчер). Охорона може впустити до 5 фур на день без броні
(налаштування). Диспетчер бачить такі рейси у kanban із позначкою «Без броні» і призначає ворота кнопкою
«На ворота»; якщо вільних воріт немає — рейс чекає у «Черга», порядок — спочатку заброньовані.

**4.5 Відкрити/закрити шлагбаум вручну** (охорона). Форма воріт або екран КПП → «Відкрити» / «Закрити» /
«Тримати відкритим» (до 30 хв, далі знімається саме). Кнопки неактивні, якщо адміністратор не ввімкнув
«Дозволяти команди на ворота», якщо перекритий фотоелемент або вже є незавершена команда. Усі команди — у
журналі «Команди» (Телеметрія) з ім'ям, часом, результатом.

**4.6 Кінець дня** (диспетчер). Двір → Звіти → «Рейси» (pivot: середнє очікування, час біля воріт за
перевізниками) і «Ворота» (зайнятість/простій); рейси без прибуття позначені «Не приїхала». Звіт за
перевізниками — групування за «Перевізник».

## 5. Ризики й відкриті питання

### 5.1 Відкриті питання Q-xx

| ID | Питання | Кому | Рекомендована відповідь | Поки відповіді немає |
|---|---|---|---|---|
| Q-01 | Маршрут приймача LPR: iot_sim Додаток A (658–659) пише `<collector>/f3d/lpr`, telemetry §2.4 — `POST /f3d/push/lpr` (`http_push` з маршрутом `lpr`). Зафіксувати один | менеджер, автори telemetry та iot_sim | `/f3d/push/<route>` telemetry; iot_sim виправляє рядки 658–659 і `SIM_LPR_PUSH_URL` у compose | модуль реалізує лише хук CT-08 для маршруту `lpr`; URL — справа колектора |
| Q-02 | Держномер для емулятора: API-01 iot_sim віддає `bookings[].plate=null` і генерує номер сам (`AA`+det(code)); Odoo їх не знає. Чи бере емулятор `plate` з `stock.picking.batch.f3d_plate` (CY-02), коли не null? | автор iot_sim | так; при `null` — генерує, як зараз, і пише назву пакета в `plateListDescription` | резервне зіставлення R-08 за `plateListDescription` заповнює номер рейсу |
| Q-03 | Токен на маршруті `lpr`: telemetry вимагає `X-F3D-Token`/Bearer, емулятор шле POST без автентифікації (§8.13.2). Додати `SIM_LPR_PUSH_TOKEN` у емулятор чи allow-list за IP у колекторі? | автори telemetry та iot_sim | емулятор додає заголовок `X-F3D-Token` (Axis LPV так само вміє `x_auth_key`); IP allow-list — другий запобіжник | ТК-02 запускається з токеном, виставленим у env обох сервісів; без токена — 401 і ТК не проходить |
| Q-04 | Імпульс на DO: CAME очікує імпульс ≥ 1 с; плагін `modbus_tcp` telemetry пише одне значення. Додати `pulse_ms` у схему адреси coil (`write 1 → sleep → 0`) чи налаштувати ADAM-6060 DO у режим «pulse output»? | автор telemetry, монтажник | `pulse_ms` у схемі (`{"fc":5,"addr":16,"pulse_ms":1500}`); у проді ADAM DO також у pulse-режимі як апаратний запобіжник | команда = одне значення `1`; емулятор трактує як імпульс (§8.13.1); ТК-04 проходить |
| Q-05 | Протокол індикатора АКСІС ME-01 (RS-232): чи є SICS-сумісний режим або «Toledo»-подібний ASCII; чи буде RS-232→Ethernet-шлюз | постачальник ваг (vagi-axis.ua) | запросити опис протоколу; шлюз Moxa NPort/USR-TCP232; якщо не SICS — другий діалект у плагіні `sics` (`dialect` у `params`) | плагін `sics` за MT-SICS (iot_sim Q-08 те саме); діалект-заглушка не пишеться |
| Q-06 | Хто бронює ворота для сторонніх фур (каркас §9 п. 7): (а) лише диспетчер; (б) постачальник через портал `/my/yard` за своїми замовленнями; (в) e-mail-посилання без входу | замовник | (а) у v1; (б) у v1.1 — модель уже має `source='supplier'`, стан `requested`, диспетчер підтверджує; (в) ні (безпека) | (а) |
| Q-07 | Чи пушити список дозволених номерів у камери Axis LPV (VAPIX list API), щоб `plateList='allow'` формувалось на камері | замовник, інтегратор відео | так, але після v1: окремий крон `lpr_push_allowlist` (поза v1) | камера шле всі номери; рішення — в Odoo (R-08) |
| Q-08 | Переглядач малює лише 6 фур макета (`TRUCK-IN-1…3`, `TRUCK-OUT-1…3` як об'єкти glTF). Рейси без коду сцени — показувати спільним мешем фури за `x/y/rz` із розділу `yard`? | автор viewer | так: `yard.trucks[]` з `x/y/rz` → інстанс спільного меша `truck`; коди сцени — як є | провайдер віддає обидва варіанти; у переглядачі фази 1 видно лише 6 фур |
| Q-09 | Маси товарів для звірки нетто: у демо `product.weight=0`; крок 3 міграції заповнює плити за R-30 iot_sim (ПРИПУЩЕННЯ для ДСП18) | замовник (технолог) | підтвердити маси аркушів і палет; фурнітура/крайка/ЛФМ — вагою з накладних постачальника | плити — за R-30; решта → `no_reference` |
| Q-10 | Пожежа/евакуація: «тримати відкритим» для шлагбаумів — робить контролер/емулятор (DO4) чи Odoo за сигналом `fire_safety`? | менеджер, автор fire_safety | контролер (апаратно, без Odoo); Odoo лише показує `held` | модуль читає DO4 як стан `held` через DI? ні — DO4 без зворотного зв'язку; стан `held` лише за власною командою |
| Q-11 | Друга зміна/графік КПП (iot_sim Q-11): рейси поза «Зміна 1 (07:00–15:30)» — попередження чи заборона | замовник | попередження (`enforce_calendar=False`) | так і зроблено |
| Q-12 | Де фізично ваги для фур приймання: макет ставить `TRUCK-SCALE` у `Z-GATE-E` (виїзд), емулятор R-29 зважує incoming одразу після `GATE-W`. Чи є проїзд від GATE-W до ваг? | замовник | уточнити схему руху; для v1 — ваги спільні, порядок станів від геометрії не залежить | стани не залежать від місця ваг; координата ваг — (172, −14) |

### 5.2 Рішення автора A-xx (відхилення/уточнення каркаса)

| ID | Рішення | Чому |
|---|---|---|
| A-01 | Бронювання — окрема модель `f3d.yard.booking`, а не поля рейсу | життєвий цикл слоту відрізняється від рейсу (запит → підтвердження → скасування/перенос зі збереженням історії), конфлікти перевіряються між слотами одних воріт без рейсів, майбутній портал постачальника створює запит ще без рейсу; при цьому підтверджений слот дзеркалиться в стандартні `dock_id/scheduled_date/end_date` пакета (D-03 каркаса — ворота й диспетчеризація лишаються стандартними) |
| A-02 | У `depends` явно `stock_fleet` поруч зі `stock_picking_batch` | поля `dock_id`, `driver_id`, `vehicle_category_id`, `end_date` оголошені в `stock_fleet` (перевірено `fields_get` і представлення `stock_fleet.stock_picking_batch_form`); каркас §3 перелічує лише `stock_picking_batch`, `delivery` |
| A-03 | Стани рейсу: `draft`, `planned`, `arrived`, `queued`, `at_dock`, `handling`, `weighed`, `left`, `rejected`, `cancelled`; зважування на в'їзді — не стан, а запис `kind='in'` з міткою `weighed_in_at` | список менеджера (заплановано → … → зважена → виїхала / відхилена) відтворено дослівно; два окремі стани для ваг подвоїли б переходи |
| A-04 | Перевізник і водій — `res.partner` (водій — контакт-особа з `f3d_is_driver`, перевізник — компанія з `f3d_is_carrier`); `delivery.carrier` отримує `f3d_partner_id` | `delivery.carrier` — спосіб доставки, не контрагент; стандартний `stock.picking.batch.driver_id` теж `res.partner` — узгоджено |
| A-05 | `fleet.vehicle` для сторонніх фур не створюється; держномер — Char `plate` на рейсі | `fleet` веде власний парк; сторонніх машин сотні, їх облік — PII й сміття в Fleet |
| A-06 | Команди на ворота — тільки через `f3d.command` telemetry; власної черги/контролера немає | telemetry A-08 (Odoo не ходить у мережу цеху); журнал команд єдиний (CY-08) |
| A-07 | Автозахоплення зважування — через перевизначення `f3d.signal.write()` для `yard/scale/*`, а не крон | показання приходять пакетом раз на 5 с, фура стоїть на вагах 60 с; крон раз на хвилину пропускав би; `f3d.reading` зберігається лише раз на `store_period_s` (telemetry A-04), тому гачок потрібен на `last_value` |
| A-08 | Сигнал каталогу 654/656 об'єднує DI0 і DI1 в одному рядку; модуль розділяє: `state` ← DI0, нові `loop` ← DI1, `photocell` ← DI4, команди `cmd_open/close/hold` ← DO0/DO2/DO4 (PDU 0/1/4/16/18/20 для W; 2/3/5/17/19/20 для E) | один сигнал = одна адреса (telemetry CT-03); розбіжність — у звіті менеджеру |
| A-09 | Ваги — окрема модель `f3d.yard.scale`, не поле воріт | одні ваги обслуговують обидва напрямки (Q-12); у воріт лише посилання `scale_id` |
| A-10 | Екран КПП — OWL client action з двома RPC (`kpp_data`, `kpp_action`), без власних HTTP-маршрутів | планшет під логіном `f3d_yard_kpp`; стандартна сесія і права; тестується `HttpCase` без контролерів |
| A-11 | Крок 3 міграції заповнює `product.weight` плит за масами R-30 iot_sim лише коли вага 0 і параметр увімкнений | інакше FR-12 не має еталона на демо; на проді вимкнено (Q-09) |
| A-12 | Антипрохід — за лічильником петлі ADAM (`passes_today`), без окремого датчика | лічильник є в P-11 і каталозі (655/657); точність — 1 проїзд |
| A-13 | Провайдер `yard` додає **новий** розділ верхнього рівня `yard` у payload, не змінюючи `pickings[].truck`/`docks` | viewer A.0 має 26 ключів; `yard` зарезервований у viewer C-02 (160); сумісність зі статичною сторінкою |
| A-14 | Знімок LPR — `ir.attachment` на події (base64 з `imageArray`/`imageFile`, якщо надіслано) або URL `imagesURI[0]`; відеоархів поза Odoo | мінімум PII і обсягу; NVR уже є (Axis S3016) |

### 5.3 Ризики

| Ризик | Вплив | Пом'якшення |
|---|---|---|
| Індикатор АКСІС не підтримує SICS (Q-05) | автозважування не працює на проді | плагін із `dialect` у `params`; ручне введення ваги (FR-28) працює завжди |
| Монтаж CAME через ADAM відрізняється від P-11 (інші канали, інверсія контактів) | команди/стани воріт неправильні | адреси DI/DO — поля воріт (не код); `invert_di` на воротах; наладка з монтажником до вмикання `write_enabled` |
| Камера не передає `plateUnicode` або читає кирилицю латиницею | незбіг номерів | нормалізація R-08 (таблиця схожих літер); резервне зіставлення за описом; ручна прив'язка охороною |
| Телеметрійний SPEC змінить імена полів `f3d.command`/хука | зміна коду M-12/M-18 | посилання лише на CT-xx; поля — через `_fields` перевірка при установці (тест `test_contracts`) |
| Конфлікт провайдера `yard` з майбутнім `access` (черговість 160/170) | дублювання людей/фур | `yard` пише лише ключ `yard`; access — `access` |

## 6. План сборки агентами

| Воркер | Файли (межі) | Здає | Залежить від |
|---|---|---|---|
| W0 каркас | `__manifest__.py`, `__init__.py`, `models/__init__.py`, `security/f3d_yard_security.xml`, `security/ir.model.access.csv`, `data/ir_config_parameter.xml`, `data/ir_sequence.xml`, `views/f3d_yard_menus.xml` (порожні дії-заглушки), `tests/common.py`, `README.md`, `CHANGELOG.md` | модуль встановлюється на копію демо після base і telemetry; групи, меню, параметри | base, telemetry (ARCH CT-xx) |
| W1 рейси й бронювання | `models/f3d_yard_visit.py`, `models/f3d_yard_booking.py`, `models/stock_picking_batch.py`, `models/stock_picking.py`, `models/res_partner.py`, `models/delivery_carrier.py`, `wizard/f3d_yard_reject_wizard.py`, `views/f3d_yard_visit_views.xml`, `views/f3d_yard_booking_views.xml`, `views/stock_picking_batch_views.xml`, `views/stock_picking_views.xml`, `views/res_partner_views.xml`, `tests/test_visit.py`, `tests/test_booking.py`, `tests/test_picking.py` | M-01, M-02, M-07…M-10, M-17; R-01…R-05, R-09, R-12 (звірка за даними ваг), §10; AC-01…AC-22 | W0 |
| W2 ворота, LPR, команди | `models/f3d_yard_gate.py`, `models/f3d_yard_lpr_event.py`, `models/f3d_push_handler.py`, `models/f3d_command.py`, `wizard/f3d_yard_walkin_wizard.py`, `data/f3d_yard_gate_data.xml`, `data/f3d_signal_data.xml` (частина воріт і LPR), `views/f3d_yard_gate_views.xml`, `views/f3d_yard_lpr_event_views.xml`, `tests/test_lpr.py`, `tests/test_gate.py`, `tests/test_commands.py` | M-03, M-04, M-12, M-16, M-18; R-06…R-08, R-15…R-17; AC-23…AC-40 | W0, W1 (рейс) |
| W3 ваги й плагін `sics` | `models/f3d_yard_scale.py`, `models/f3d_yard_weighing.py`, `models/f3d_signal.py`, `data/f3d_yard_scale_data.xml`, `data/f3d_signal_data.xml` (частина ваг), `views/f3d_yard_weighing_views.xml`, `views/f3d_yard_scale_views.xml`, `tests/test_scale.py`; `services/collector_plugins/f3d_collector_yard/` (`pyproject.toml`, `f3d_collector_yard/sics.py`, `schemas/sics_source.json`, `schemas/sics_address.json`, `tests/test_sics.py`, `tests/fake_sics_server.py`) | M-05, M-06, M-13; R-10…R-14; §8; AC-41…AC-52 | W0, W1 |
| W4 диспетчерська, КПП, провайдер, звіти | `static/src/kpp/*` (OWL), `views/f3d_yard_kpp_action.xml`, `views/f3d_yard_dashboard_views.xml` (kanban/gantt/calendar), `report/f3d_yard_dock_report.py`, `report/f3d_yard_report_views.xml`, `models/f3d_viewer_provider.py`, `tests/test_kpp.py`, `tests/test_provider.py`, `tests/test_reports.py` | V-xx, M-14, M-15; R-18…R-21; AC-53…AC-66 | W1, W2, W3 |
| W5 міграція, крони, безпека, DEPLOY_TEST | `hooks/__init__.py`, `hooks/migrate.py`, `data/ir_cron.xml`, `data/neutralize.sql`, `models/res_config_settings.py`, `views/res_config_settings_views.xml`, `tests/test_migration.py`, `tests/test_security.py`, `tests/test_cron.py`, `docs/modules/factory3d_yard/DEPLOY_TEST.md` | M-11; §5, §6; AC-67…AC-80; ТК на стенді | усі |

Порядок злиття: W0 → W1 → (W2 ∥ W3) → W4 → W5. Кожен воркер здає зелені тести свого файлу з тегом
`f3d_yard`; W5 проганяє повний набір і ТК-01…ТК-08 на стенді з емулятором і колектором.
