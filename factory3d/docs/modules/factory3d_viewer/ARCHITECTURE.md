# factory3d_viewer — технічне рішення

Версія 0.2 · 14.10.2026 (0.1 — 13.10.2026) · автор: агент-архітектор модуля (Fable) · статус: чернетка на погодження.
Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-08 (кнопки «Показати в 3D» носіїв домішки — у base CB-02, C-01, FR-22,
A-11), X-09 (`employees` з `hr.employee.public`, §2.6), X-14 (`f3d_loc_kind`/`f3d_capacity` з base), X-15 (код фури —
`stock.picking.batch.f3d_code`, C-08, FR-24, Q-03), X-19 (власний привілей групи кіоска, §2.6), X-22 (duck-typing контракт
провайдера, C-02, FR-43, A-05), X-23 і X-82 (глибоке злиття дельти, `deep_merge` у `tools/payload.py`, FR-42), X-24
(схема 1.1, FR-11, FR-37), X-25 (`energy_cost` лише з групою вартості energy, FR-44, §2.6), X-27 (sequence 75 і 155,
C-02), X-28 (FR-39, FR-40, §1.4 — x/y фаза 4), X-29 (45 зон, FR-41), X-30 (меню 10/12/14/16, налаштування під
`menu_f3d_config`, §1.2, §4).
Каркас: `docs/ARCHITECTURE.md` v0.2 (§5 конвенції, §6.1 код сцени, §6.7 контракт переглядача, §8 D-13…D-25).
Стандарт оформлення: `docs/DOC_STANDARD.md`. Специфікація: `docs/modules/factory3d_viewer/SPEC.md`.
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-06, Q-08.
Зміни: 14.10.2026 — закрито рішеннями менеджера: Q-01, Q-03, Q-04, Q-07.

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора; `docs/оцінки` в репозиторії ще немає) |
|---|---|---|
| ТР | цей документ + SPEC (погоджені менеджером) | 24 |
| Архітектура | рішення A-01…A-16, контракти C-01…C-09, план W0…W6 | 16 |
| Розробка | модуль `odoo_addons/factory3d_viewer` за SPEC §0–§11 | 180 |
| Тестування | SPEC §13: юніт, HttpCase, тури, продуктивність, кіоск, безпека | 60 |
| Інструкція | §4 цього документа + довідка в модулі | 8 |

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що є в макеті

Переглядач уже існує як статична сторінка `viewer/index.html` (2 693 рядки: 312 рядків CSS, 83 рядки
розмітки, 2 287 рядків JavaScript у одному `<script type="module">`, three.js 0.160.0 з CDN jsDelivr через
`importmap`). Він читає два джерела даних:

1. **Модель** — `dist/parts/manifest.json` (31 шар у 7 групах, 5 частин із кодами об'єктів) і
   `dist/parts/*.glb` (квантовані, `KHR_mesh_quantization`): `core` 9,8 МБ (README називає 5,7 МБ — застаріле
   число; актуальний розмір — у `manifest.parts[].bytes`), `engineering` 2,2 МБ,
   `fire` 1,4 МБ, `it` 0,1 МБ, `site` 0,2 МБ; разом 13,7 МБ. У glTF extras кожного клікабельного
   об'єкта: `code`, `kind`, `label`, `desc`, для верстатів `status` (`work`/`idle`/`stop` із
   `plant/layout.py:STATUS`), для комірок `state`, для зон `rect`, для вузлів-шарів `layer`, для
   маячків `role=status`, для частини об'єктів `model`/`maker`.
2. **Дані Odoo** — `dist/odoo_demo.json` (1,07 МБ, 122 КБ gzip; 26 ключів верхнього рівня, повна схема —
   SPEC Додаток A). Генерує `plant/odoo_demo.py` (`Demo.build()`, 0,11 с, без Blender і мережі) або
   `plant/odoo_pull.py` (`LiveDemo`: той самий збирач, після чого `sync_pickings`, `sync_production`,
   `sync_stock`, `sync_orders`, `sync_maintenance`, `sync_signals` підміняють стан документів живими
   даними з бази через XML-RPC; повна побудова з тестового сервера timur-o19demo, база `odoo` —
   8,4 с, з них ≈ 25 викликів по ≈ 0,4 с мережевої затримки).

Усе, що робить переглядач, зведено в реєстр — це основа FR і тестів. Імена функцій — з
`viewer/index.html`.

| # | Елемент інтерфейсу | Функції у `viewer/index.html` | Ключі даних, які читає | Дії |
|---|---|---|---|---|
| R1 | Заголовок: назва, габарити, лічильник верстатів | `loadPart`, рядок 586–588 | `manifest.dims`, `userData.kind=machine` | — |
| R2 | Індикатор «Odoo» (пульс, джерело, час синхронізації) | `tickClock`, рядки 1304–1322, 1938 | `meta.live`, `meta.source`, `meta.database`, `meta.pulled_at`, `meta.now` | клік → вкладка «Огляд» |
| R3 | Програвання зміни: ▶, повзунок 07:00–15:30 крок 5 хв, «Зараз» | `applySimTime`, `scheduleWOs`, `simMinutes`, `stopShift` | `workorders[].date_start/date_finished/duration_expected/date_planned_finished/blocked`, `productions[].state`, `energy.typical`, `meta.now` | рух повзунка перераховує стани завдань і МО, потужності; ▶ вмикає шар «Замовлення в роботі» |
| R4 | «Потік зміни» — стрічка часу над сценою | `flowBuild`, `flowRender`, `flowUpdate`, `flowCursor` | `workorders[]` (`_s`, `_f` з дат), `workcenters[].name`, `pickings[].type/scheduled_date/partner/lines/dock/origin/location_dest`, `products` | клік по смузі/події → картка МО / переміщення |
| R5 | Види (13, клавіші 1–9, 0) | `VIEWS`, `goView`, `viewPose`, `fitBox` | `userData.rect` зон (`Z-SHEETS`), код `EDGE-1` | вид «Дах і СЕС» вмикає шар `roofdeck`, решта ховає |
| R6 | Розфарбування: звичайне / заповненість / OEE / споживання / освітленість | `modeColor`, `repaintAll`, `legendHtml` | `locations[].fill`, `workcenters[].oee`, `energy.consumers[].p_now`, `energy.lines[].load`, `energy.transformers[].load`, `lighting.groups[].e_calc/e_norm/zone` | пороги: fill 0/0,3; OEE 0,5/0,75; кВт 10/30; load 0,6/0,8; lux 0,85/1,0 |
| R7 | Шар «Замовлення в роботі» (весь цикл кожного МО, точка «де зараз», гілки матеріалів, партії при програванні) | `drawProdOverlay`, `cyclePosition`, `trackAt`, `buildBatches`, `prodSimMove`, `prodFocus`, `setProdOverlay` | `productions[].state/workorders/supply.steps/delivery.steps/delivery.picking/components[].path/to/kind/receipt/product`, `workorders[].state/blocked`, `pickings[].scheduled_date` | ховає групи шарів «Інженерні мережі», «Пожежна безпека», «ІТ і Odoo», «Територія й охорона» і `roof`/`roofdeck`; вид згори; клік по мітці → картка МО |
| R8 | Шари (31, 7 груп, пресети «Усі», «Лише виробництво», «Інженерія») | `buildLayersUI`, `setLayer`, `syncLayerGroups`, `loadPart`, `ensureCode` | `manifest.layers/parts` | увімкнення шару з незавантаженої частини вантажить частину |
| R9 | Показ: підписи, анімація маршруту, тіні | `syncLabels`, `opt-motion`, `opt-shadows` | — | `prefers-reduced-motion` вимикає анімацію |
| R10 | Вкладка «Огляд»: 4 KPI, «Потребує уваги», пожежна безпека, парк обладнання, легенда, джерело | `renderOverview`, `fireSummary`, `fleetHtml` | `workcenters[].status/oee/maintenance_request/idle_reason/name`, `productions[].state/reservation_state`, `pickings[].type/state/scheduled_date/partner/note`, `quality_checks[].state/product/location`, `infra.cards[].warn`, `fire.groups[].state/warning/maintenance_request/zone_name`, `fire.totals`, `ventilation.units[].filter_dp_pa/maintenance_request`, `locations[].state`, `purchase_orders[].locations`, `passports`, `evacuation`, `meta.note` | кожен рядок → `obj:`/`mo:`/`pick:`/`locs:`; кнопка «Сценарій пожежної тривоги» |
| R11 | Вкладка «Виробництво»: список МО | `renderProduction`, `moCurrent` | `productions[].name/product_name/qty/state/origin/progress/workorders`, `workorders[].state/blocked/workcenter/name`, `workcenters[].name` | рядок → `showMO` |
| R12 | Картка МО + маршрут у 3D (шлях плити, операції, шлях до клієнта, гілки матеріалів) | `showMO`, `renderMO`, `showComponent`, `highlight`, `drawBranch` | `productions[]` усі поля, `workorders[]`, `sale_orders[].name/partner`, `products`, `workcenters[].name` | клік по кроку → `obj:`; по компоненту → підсвітити місця з залишком (`idx.prodLocs`) |
| R13 | Вкладка «Склад»: пошук + фільтр категорій + список товарів | `renderStock` | `products[].name/default_code/categ/uom`, `locations[].quants[].product/qty/reserved`, `locations[].state` | рядок → `showProduct` |
| R14 | Картка товару | `showProduct`, `renderProduct` | `products[]`, `locations[].complete_name/quants`, `purchase_orders[].lines/partner/date_planned`, `productions[].product/components` | підсвітити всі місця з кількістю (`prog`, якщо є резерв) |
| R15 | Вкладка «Логістика»: ланцюжок плит, ланцюжок відвантаження, шляхи матеріалів, «Весь цикл у 3D», 6 списків переміщень | `renderLogistics`, `pickRow`, `showChain`, `showMatPath` | `sheet_chain.steps/path`, `ship_chain.steps`, `material_paths`, `full_cycle_mo`, `pickings[]` | крок → підсвітити `codes`; `chain:all` → шлях з номерами; рядок → `showPicking` |
| R16 | Картка переміщення + маршрут у 3D за типом (incoming, outgoing, putaway, replenish, pick_components, store_finished) | `showPicking`, `renderPicking` | `pickings[].type/dock/truck/source_locations/location_dest/vehicle/lines/partner/origin/state/scheduled_date/carrier/progress/note`, `purchase_orders[].locations`, `locations[].quants` | маршрут: фура → `UNLOAD-k` → `QC-PLT-k`/`QC-1` → місце зберігання; ГП → `Z-OUT-k` → ворота → фура |
| R17 | Вкладка «Енергія»: 4 KPI, трансформатори, профіль доби, лінії, власна генерація, освітлення/вентиляція, найбільші споживачі, журнал подій | `renderEnergy`, `chartHtml`, `trafoRow`, `lineRow`, `backupSummary`, `lightVentSummary` | `energy.totals/transformers/lines/consumers/profile/typical/events/meta`, `infra.totals`, `lighting.groups/panels`, `ventilation.totals/units` | лінія → `showLine` (підсвітити шинопровід і споживачів); споживач → `obj:` або `line:` |
| R18 | Картка лінії живлення | `showLine`, `renderLine`, `lineBody` | `energy.lines/cells/consumers`, `passports` | — |
| R19 | Картка 3D-об'єкта (будь-який `code`) | `renderObject` + `wcHtml`, `locHtml`, `empHtml`, `eqHtml`, `zoneHtml`, `lightingHtml`, `ventHtml`, `fireHtml`, `infraHtml`, `energyHtml`, `passportHtml` | `workcenters[code]`, `locations[code]`, `employees[code]`, `equipment[code]`, `docks[code]`, `zones[code]`, `lighting.groups/panels[code]`, `ventilation.units[code]` + `HEAT-NET`, `fire.groups[code]` + `FACP-1`/`FA-MCP`/`FA-SND`/`FA-FLAME`/`SPARK-1`, `infra.cards[code]`, `energy.*[code]`, `passports[code]`, `maintenance_requests`, `quality_checks` (для `QC-*`), `meta.iot` | «Наблизити», «Закрити»; посилання `obj:`, `mo:`, `pick:`, `prod:`, `line:`, `etab:` |
| R20 | «Живі» дані: прогрес завдань і «дихання» потужності щo 3 с | `tick`, `energyTick`, `updateLive` | `workorders[].progress`, `productions[].progress`, `energy.consumers[].p_now/cos_phi`, `energy.lines`, `energy.transformers`, `energy.cells` | оновлює смуги `data-p`, значення `data-t`, `data-e`, `data-eb` без перемальовування панелі |
| R21 | Сценарій пожежної тривоги (евакуація) | `startDrill`, `renderDrill`, `stopDrill` | `evacuation.routes/exits/drill_origin/drill_zone/drill_detector/drill_steps/max_distance/norm_*`, `fire.totals` | вмикає шари `DRILL_LAYERS`, блимання `FA-SND`, `SMOKE-VENTS`, `EXITS`, точки по маршрутах |
| R22 | Вибір мишею, наведення, подвійний клік, Esc, телефонна розкладка | `pick`, `select`, `focusOn`, `closeSideOnPhone` | `userData.code/kind` | клік → картка об'єкта |
| R23 | Маячки стану верстатів (блимання при зупинці) | цикл рендера, рядки 2664–2668 | `userData.status` з GLB (`role=status`) | — |

Що з реєстру **не має джерела в Odoo** й лишається з моделі (статика): `energy` (крім `p_now` верстатів
із сигналів), `lighting`, `ventilation`, `fire`, `infra`, `evacuation`, `passports`, геометрія зон, шаблони
шляхів матеріалів, норми. Ці розділи в Odoo 19 без розробки не існують (README «Чого в базі немає»); їх
дають модулі фаз 2–5 через хук C-02, а до того — файл `static/data/model_static.json`.

Що в макеті **імітується на клієнті** й у модулі замінюється живими даними: R20 (прогрес завдань +0,2 %
кожні 3 с, випадкове «дихання» потужності ±6 %) — у модулі клієнт нічого не імітує, коли `meta.live=true`;
стан приходить з `/f3d/viewer/delta` за повідомленнями шини (C-03).

Що в макеті **запечено в GLB** і в модулі має перекриватися даними: `userData.status` верстатів (R1, R19,
R23) і `userData.state` комірок (R19) — у модулі беруться з `workcenters[code].status` і
`locations[code].state`, GLB лишається незмінним.

### 1.2 Ролі й сценарії використання

| Роль (група) | Сценарій | Де в меню |
|---|---|---|
| Майстер зміни, диспетчер (`factory3d_base.group_f3d_user` + `mrp.group_mrp_user`) | відкрити «Завод 3D → Переглядач», вкладка «Виробництво», бачити МО, де зараз, які верстати стоять, клацнути по верстату → відкрити робочий центр в Odoo | Завод 3D → Переглядач; кнопка «Показати в 3D» на формі МО / робочого центру |
| Комірник, логіст (`group_f3d_user` + `stock.group_stock_user`) | вкладки «Склад», «Логістика»: де лежить товар, що на воротах, маршрут відвантаження; кнопка «Показати в 3D» на формі переміщення, місця зберігання, пакетного переміщення | Склад → … → «Показати в 3D» |
| Головний механік (`group_f3d_user` + `maintenance.group_equipment_manager`) | картки обладнання: заряд, мотогодини, тиск, заявки ТО; кнопка «Показати в 3D» на формі обладнання | Обслуговування → Обладнання → «Показати в 3D» |
| Енергетик, інженер (`group_f3d_user`) | вкладка «Енергія», шари інженерних мереж, картки ГРЩ, шинопроводів, вентустановок, пожежних груп | Завод 3D → Переглядач |
| HR / начальник дільниці (`group_f3d_user` + `hr.group_hr_user`) | люди на дільницях, кнопка «Показати в 3D» на формі співробітника | Співробітники → форма → «Показати в 3D» |
| Менеджер 3D (`factory3d_base.group_f3d_manager`) | налаштувати знімки й ротацію, запустити «Перевірку циклу», дивитись журнал станів, програвати зміну за знімками | Завод 3D → Налаштування → Налаштування переглядача; Завод 3D → Журнал станів; Завод 3D → Перевірка циклу |
| Адміністратор (`factory3d_base.group_f3d_admin`) | згенерувати/змінити токен кіоска, завантажити демо (лише тестовий сервер), стоп-крани | Завод 3D → Налаштування → Налаштування переглядача (`factory3d_base.menu_f3d_config`, sequence 10; X-30); Завод 3D → Демо-дані |
| Екран у цеху (технічний користувач `factory3d_viewer.user_kiosk`, група `factory3d_viewer.group_f3d_kiosk`) | планшет Samsung Galaxy Tab Active5 Pro або телевізор відкриває `/f3d/kiosk/<token>?tab=production&mode=oee`, без входу й навігації, автооновлення | URL кіоска |
| Продавець (`sales_team.group_sale_salesman` + `group_f3d_user`) | з форми замовлення клієнта «Показати в 3D» → маршрут його МО й відвантаження | Продажі → форма → «Показати в 3D» |

### 1.3 Функціональні вимоги

Клієнтська дія й модель:

- FR-01 Клієнтська дія `f3d_viewer.action` (`ir.actions.client`, xml-id `factory3d_viewer.action_f3d_viewer`) відкриває переглядач на весь робочий простір Odoo (`target: fullscreen` у кіоску, `current` у бекенді) з меню «Завод 3D → Переглядач».
- FR-02 Дія приймає `params`: `code` (код сцени — вибрати об'єкт і наблизити), `tab` (`overview|production|stock|logistics|energy`), `mode` (`none|fill|oee|power|lux`), `mo` (назва МО), `picking` (назва переміщення), `so` (назва замовлення клієнта), `lite` (`0|1|auto`), `layers` (список ключів шарів через кому); невідомі ключі ігноруються, невідомий `code` → повідомлення «Об'єкта … немає в моделі» без помилки.
- FR-03 three.js 0.160.0 і 4 додатки (OrbitControls, GLTFLoader, CSS2DRenderer, RoomEnvironment) постачаються в модулі одним ESM-файлом `static/lib/three/three-bundle.esm.js` без CDN, без мережевого доступу назовні (A-01).
- FR-04 Частини моделі `static/model/parts/*.glb` і `manifest.json` віддаються статикою Odoo з `ETag`/`Last-Modified`; URL частини містить хеш вмісту (`?v=<sha1[:12]>`), тому браузер і планшет кешують частини назавжди, а нова збірка змінює URL.
- FR-05 Завантаження частин як у макеті: перша (`core`) — одразу, решта — у фоні по черзі або при вмиканні шару / переході до об'єкта з ще не завантаженої частини.
- FR-06 Усі 23 елементи реєстру R1–R23 працюють у модулі так само, як у `viewer/index.html`, з даними з `/f3d/viewer/static` + `/f3d/viewer/data` (єдина відмінність — R20: без імітації при `meta.live=true`).
- FR-07 Стан верстата (`status`) і комірки (`state`) у підписах, маячках і картці береться з даних Odoo, а не з GLB (GLB лишається старим).
- FR-08 У картці об'єкта є кнопка «Відкрити в Odoo», яка за кодом сцени відкриває форму запису (резолвер C-05 зворотний); для документів у картках (МО, переміщення, замовлення, заявки ТО) — посилання «Відкрити в Odoo» за назвою документа.
- FR-09 Переглядач працює в темній і світлій темі Odoo (змінні `--f3d-*` перевизначаються від `o_web_client` теми), на ширині від 360 px (телефонна розкладка макета: панель видів ховається, картка внизу).

Дані:

- FR-10 `GET /f3d/viewer/static` віддає статичну частину контракту (розділи `zones`, `docks` без документів, `energy`, `lighting`, `ventilation`, `fire`, `infra`, `evacuation`, `passports`, `layout`, `path_templates`, `meta.schema`) з `ETag`; `304 Not Modified` при збігу.
- FR-11 `GET /f3d/viewer/data` віддає живу частину контракту (`meta`, `products`, `locations`, `workcenters`, `productions`, `workorders`, `sale_orders`, `purchase_orders`, `pickings`, `quality_checks`, `maintenance_requests`, `equipment`, `employees`, `docks`, `sheet_chain`, `ship_chain`, `material_paths`, `full_cycle_mo`, живі поля в `zones`, значення сигналів у статичних розділах); з `?full=1` — повний документ схеми `meta.schema = "1.1"` (X-24): 26 базових ключів `dist/odoo_demo.json` у тому самому порядку, сумісні за типами, + додаткові ключі модулів (SPEC Додаток A.15), нові ключі верхнього рівня (`yard`, `access`) — лише після 26 базових.
- FR-12 Payload будується з ORM послідовно: статика з `model_static.json` → вбудовані провайдери модуля (`stock`, `production`, `logistics`, `quality`, `maintenance`, `people`, `chains`, `signals`) → провайдери інших модулів (моделі `f3d.viewer.provider.<key>`, метод `_f3d_viewer_collect(payload, ctx)`) — усі разом за `_f3d_sequence`: вбудовані 20…70, machine_connect 75, `signals` 90, telemetry 95, energy 100, lighting 110, ventilation 120, fire 130, evacuation 140, infra 150, genset 155, yard 160, access 170 (C-02, X-27).
- FR-13 Помилка одного провайдера (виняток) не валить відповідь: його розділи лишаються як були (статика або порожні), у `meta.sections[<key>] = "error"`, у лог `factory3d_viewer` пишеться traceback, у відповіді — `meta.errors[]` з назвою провайдера й класом винятку (без тексту SQL і без traceback).
- FR-14 Payload не містить даних понад права користувача: кожен провайдер читає моделі через `env[model]` **користувача запиту** (без `sudo()`), перед читанням розділу перевіряє `check_access('read')` (Odoo 19) і записує `meta.sections[<key>] = "denied"`, якщо прав немає; record rules (мультикомпанія) застосовуються ORM автоматично.
- FR-15 Дати в payload — рядки `YYYY-MM-DD HH:MM` у часовому поясі `Europe/Kyiv` (як у файлі); `meta.now` — параметр `factory3d.viewer.demo_clock`, якщо заданий, інакше поточний час; відкриті таймери робочих завдань рахуються до `meta.now`.
- FR-16 `GET /f3d/viewer/delta?since=<ISO-UTC>&codes=<csv>` повертає лише змінені об'єкти з моменту `since` (`patch` за розділами + `removed` + новий `ts`); якщо `since` старіший за `factory3d.viewer.event_keep_hours` або подій більше 2 000 — відповідь `{"full": true}` і клієнт перечитує `/data`.
- FR-17 Значення сигналів (`x_f3d_signal` у фазі 1, `f3d.signal` у фазі 2 через провайдер `factory3d_telemetry`) кладуться в payload за шляхом `code` (`energy/consumers/SAW-1/p_now`), відсотки → частки, `drain`+`charging` → `state` (як `LiveDemo.sync_signals`); `meta.iot = {source, signals, alarms, updated}`.

Живі оновлення:

- FR-18 Зміни в `stock.quant`, `stock.move.line`, `stock.picking`, `stock.picking.batch`, `mrp.workorder`, `mrp.production`, `mrp.workcenter`, `mrp.workcenter.productivity`, `maintenance.request` публікуються в канал `bus.bus` `f3d_viewer` повідомленням `{model, codes, kind, ts}` (C-03), одне повідомлення на модель на транзакцію (коалесценція в `cr.precommit`).
- FR-19 Клієнт накопичує коди 1 500 мс (параметр `factory3d.viewer.delta_debounce_ms`), тримає не більше одного запиту `/delta` у польоті й застосовує патч до `D` на місці: смуги/значення оновлюються без перемальовування панелі (як `updateLive`), повна перемальовка панелі — лише якщо змінився об'єкт, що відкритий у картці.
- FR-20 Сигнали імітації IoT (`x_f3d_signal.x_updated`) публікуються в шину кроном раз на хвилину (поки немає `factory3d_telemetry`), повідомлення `kind="signal"`, `codes` = шляхи.
- FR-21 При розриві з'єднання шини індикатор «Odoo» стає червоним з текстом «немає зв'язку», клієнт переходить на опитування `/delta` кожні 30 с і повертається до шини, коли вона відновилась.

«Показати в 3D» і зворотний зв'язок:

- FR-22 Кнопка «Показати в 3D» (`type="object"`, `name="action_f3d_show"`, іконка `fa-cube`) цього модуля є у шапці форм документів `mrp.production`, `stock.picking` і `sale.order` (міст `factory3d_viewer_sale`), видима лише для `group_f3d_user` і лише коли є що показати (є МО або відвантаження, `f3d_has_3d`). На формах носіїв домішки (`stock.location`, `mrp.workcenter`, `maintenance.equipment`, `hr.employee`, `f3d.zone`, `stock.picking.batch`) кнопку й дію дає `factory3d_base` (CB-02: `params {code, alias, model, res_id, kind}`, без viewer — `display_notification`); viewer другої кнопки в ці форми не додає і читає з дії лише `params.code` (X-08).
- FR-23 Клік по об'єкту в 3D → «Відкрити в Odoo» → `GET /f3d/viewer/resolve?code=` → `{model, res_id, display_name}` → `action_window` з формою запису; якщо запису немає — повідомлення «У базі немає запису з кодом …» (не помилка).
- FR-24 Резолвер шукає код методом домішки `search_f3d(code)` (base M-01: `f3d_code` або `f3d_alias`) у моделях домішки в порядку base `_f3d_resolve_order` (M-01, R-03; X-85): `f3d.zone`, `stock.location`, `mrp.workcenter`, `maintenance.equipment`, `hr.employee`, `stock.picking.batch`; перший знайдений виграє (код фури `TRUCK-*` — `stock.picking.batch.f3d_code`, X-15); за назвою документа — `mrp.production`, `stock.picking`, `sale.order`, `purchase.order`, `maintenance.request`, `quality.check` (`name`), `mrp.workorder` (`WO<id:05d>`); з урахуванням прав користувача (`search` без `sudo`).

Журнал станів і програвання зміни:

- FR-25 Крон раз на N хв (`factory3d.viewer.snapshot_minutes`, 10) у вікні `factory3d.viewer.snapshot_hours` («06:30-16:00») зберігає знімок повного payload (`full=1`, користувач — технічний `user_kiosk`) у `f3d.viewer.snapshot` як gzip-вкладення; `kind=periodic`.
- FR-26 Події шини пишуться в `f3d.viewer.event` (`ts`, `model`, `codes`, `kind`); вони — джерело `/delta` і стрічки «Потік зміни» за реальний день.
- FR-27 Повзунок «Програвання зміни» має два режими: `plan` (як у макеті — інтерполяція за датами завдань) і `snapshots` (за знімками дня: `GET /f3d/viewer/snapshots?date=` → список, `GET /f3d/viewer/snapshot/<id>` → payload); режим `snapshots` вмикається автоматично, якщо на обрану дату є ≥ 3 знімків; перемикач у панелі «Показ».
- FR-28 Ротація: знімки й події старші за `factory3d.viewer.snapshot_keep_days` (14) видаляються кроном щоночі; сумарний розмір знімків видно в «Завод 3D → Журнал станів» (список з `ts`, `kind`, `size_kb`, кнопка «Відкрити в переглядачі»).

Кіоск і планшет:

- FR-29 `GET /f3d/kiosk/<token>` (`auth="public"`) показує переглядач без навігації Odoo (ні меню, ні systray, ні навігаційної панелі), з параметрами `tab`, `mode`, `code`, `layers`, `lite`; невірний токен → 404 без пояснень; токен — `factory3d.viewer.kiosk_token`, 32 hex, генерується при встановленні, змінюється кнопкою «Новий токен кіоска» в налаштуваннях (стара адреса одразу перестає працювати).
- FR-30 Дані кіоска читаються від імені технічного користувача `factory3d_viewer.user_kiosk` (`with_user`, не `sudo`), права якого обмежені групою `group_f3d_kiosk` (читання моделей payload, без документів з цінами: `sale_orders[].amount` і `energy_cost` не віддаються); кіоск опитує `/f3d/kiosk/<token>/delta` кожні `factory3d.viewer.kiosk_refresh_s` (15) с, шина не використовується (A-03).
- FR-31 Полегшений режим `lite`: тіні вимкнені, `pixelRatio=1`, без `PMREM`/`RoomEnvironment` (освітлення — `HemisphereLight` + `DirectionalLight`), без антиаліасингу, частинки гілок матеріалів ≤ 1 на гілку, підписи лише зон і вибраного, частини `it`, `site`, `fire` не вантажаться, поки їх шар не ввімкнули; ціль — ≥ 30 кадр/с на Samsung Galaxy Tab Active5 Pro у виді «Загальний вигляд» із шаром «Замовлення в роботі».
- FR-32 `lite=auto`: увімкнути, якщо `navigator.deviceMemory ≤ 8` або `(pointer: coarse)` і ширина ≤ 1 400 px або сторінка кіоска; користувач може перемкнути в панелі «Показ» (запам'ятовується в `localStorage`).
- FR-33 Кіоск автоматично перезавантажує дані після відновлення мережі й повністю перезавантажує сторінку о 04:00 (оновлення асетів після деплою) та після 5 поспіль помилок `/delta`.

Майстер демо й перевірка циклу:

- FR-34 Майстер `f3d.demo.wizard` (меню «Завод 3D → Демо-дані», лише `group_f3d_admin`) виконує 35 кроків заливки демо `plant/odoo_push.py:STEPS` через ORM (порт `Push`/`FlowSteps` з адаптером `OrmProxy`, A-08) з даними `static/data/demo_payload.json`; кроки ідемпотентні (зовнішні ID модуля `factory3d` через `ir.model.data`, як у `Push.ensure`); майстер показує прогрес (крок k/35, лог), дозволяє обрати підмножину кроків і запускається в черзі крон-завдання `ir.cron` «3D: заливка демо», щоб не впертися в тайм-аут HTTP.
- FR-35 На проді майстер заблокований: стоп-кран `factory3d.viewer.demo_enabled` (`False` за замовчуванням після встановлення на проді, `True` на тесті) — кнопка «Запустити» недоступна, метод кидає `UserError` «Заливка демо вимкнена на цій базі»; `neutralize.sql` ставить `False`.
- FR-36 Звіт «Перевірка циклу» (`f3d.viewer.cycle.check`, меню «Завод 3D → Перевірка циклу», `group_f3d_manager`): запускає `cycle_check.check(payload)` на поточному payload користувача (копія `plant/cycle_check.py` у `tools/cycle_check.py`), показує результат у вікні (OK або перелік проблем, кожен рядок — посилання на документ/об'єкт), той самий звіт — `POST /f3d/viewer/cycle_check` для тестів.

Міграція й сумісність:

- FR-37 `meta.schema` — версія контракту `"1.1"` (X-24: 26 базових ключів + додаткові ключі модулів, SPEC Додаток A.15); клієнт відмовляється працювати з іншою мажорною версією (повідомлення), мінорні — сумісні за правилом «нові ключі можна, старі не прибирати».
- FR-38 Статична сторінка `dist/index.html` і `dist/factory_viewer.html` лишаються для публікації (README «Файли»); ядро переглядача в модулі й у `viewer/index.html` — один код: `build_scene.py --embed` збирає статичну сторінку з того самого `static/src/viewer/*.js` (A-02 п. 4), тому відмінностей у поведінці не виникає.

Дані модулів у клієнті й контракт провайдерів (CONSISTENCY.md, 14.10.2026):

- FR-39 Пожежна безпека в 3D за `factory3d_fire_safety` CF-01 (X-28, fire Q-09): сценарій навчальної тривоги запускається й зупиняється автоматично за `evacuation.drill_active` (`null` ↔ об'єкт, синхронізація за `elapsed_s`); стани зон `alarm`/`fault` показуються червоним («Тривога»/«Несправність»), а не «Попередженням»; за наявності `fire.devices` шар пожежної сигналізації показує маркер кожного пристрою (`x`, `y`, `z`) замість підсвічування групи (SPEC §8.2 п. 10).
- FR-40 Картки людини й зони показують рядки СКУД за `factory3d_access` CA-05 (X-28): «На території», «Зона … з HH:MM», «Останній прохід» (`employees[code].present/zone/zone_since/last_event`) і «Людей зараз» (`zones[code].people_now`); без модуля рядків немає (SPEC §8.2 п. 11).
- FR-41 Розділ `zones` містить усі активні `f3d.zone` base — 45 (34 цеху + 11 надвірних, base Додаток C.2); геометрія надвірних зон — з `f3d.zone.polygon` (не зі статики), `Z-ROOF` з `is_roof` малюється на рівні покрівлі (X-29; SPEC M-01g, R-13, §8.2 п. 12).
- FR-42 Дельта зливається глибоко (X-23): провайдер, що пише в чужий або спільний розділ (`infra`, `workcenters`, `productions`, `employees`, `zones`), лише доповнює `patch` спільним хелпером `deep_merge` (рівно `factory3d_viewer/tools/payload.py`, імпорт `from odoo.addons.factory3d_viewer.tools.payload import deep_merge`; dict — рекурсивно, list/скаляр — заміна; X-82); клієнт зливає `patch` у дані глибоко й ніколи не замінює розділ цілком (SPEC M-01, R-14).
- FR-43 Провайдер даних — будь-яка модель `f3d.viewer.provider.<key>`: або `_inherit = "f3d.viewer.provider"` (вбудовані, містки auto_install), або `AbstractModel` за префіксом без `_inherit` (модулі, для яких viewer необов'язковий); контракт — duck-typing: обов'язкові `_f3d_sequence`, `_f3d_sections`, `_f3d_group`, `_f3d_viewer_collect`, `_f3d_viewer_delta`, необов'язковий `_f3d_viewer_bus_models`; збирач і дельта читають їх через `getattr` з умовчаннями (X-22; SPEC M-01, R-01, R-14).
- FR-44 `productions[].energy_cost` (вартість енергії МО) віддається лише користувачу групи `factory3d_energy.group_f3d_energy_cost` і не кіоску; без групи вартості (зокрема без `factory3d_energy`) viewer статичну вартість не віддає; `energy_kwh` — усім, хто бачить МО (X-25; SPEC §4.4, R-07).

### 1.4 Межі: що не входить

- Редагування даних з переглядача (запуск/зупинка завдань, переміщення, підтвердження) — лише перегляд і перехід у форму Odoo.
- Збирання GLB (Blender, `build_scene.py`) — поза модулем; модуль споживає готові `dist/parts/*`.
- Моделі показань, сигналів, порогів — `factory3d_telemetry`; виміряна енергія — `factory3d_energy`; стан пожежної сигналізації — `factory3d_fire_safety`; усе це приходить через хук C-02.
- Перенос полів `x_dock`, `x_truck`, `x_vehicle` у `stock.picking.batch` — `factory3d_base` (§6.2 каркаса); переглядач читає лише `batch_id`.
- Мобільний застосунок Odoo (web_mobile) — не підтримується окремо; планшет працює у браузері Chrome/Samsung Internet.
- AR/USDZ, експорт у Unity — не входить.
- Координати рухомої техніки в 3D (`equipment/<code>/x`, `/y`) — фаза 4; до того telemetry зберігає ці сигнали з `viewer_visible=False`, у payload і на сцені їх немає (X-28, telemetry Q-08).
- Кнопки «Показати в 3D» на формах носіїв домішки (`stock.location`, `mrp.workcenter`, `maintenance.equipment`, `hr.employee`, `f3d.zone`, `stock.picking.batch`) — `factory3d_base` CB-02 (X-08); viewer лише приймає дію.

## 2. Технічна реалізація

### 2.1 Місце в системі

`depends`: `factory3d_base`, `bus`, `web` (через base транзитивно: `stock`, `mrp`, `maintenance`,
`mrp_maintenance`, `hr`, `stock_picking_batch`, `stock_fleet`; `web_tour` — тільки в тестах, він
установлений разом із `web`). `sale`, `purchase`, `quality_control` — **не** в `depends`: розділи
`sale_orders`, `purchase_orders`, `quality_checks` будуються лише якщо модель є в `env` (A-04).

Що бере з `factory3d_base` (контракти каркаса §6.1–6.3):

| ID | Контракт | Хто дає | Як використовує viewer |
|---|---|---|---|
| C-01 | `f3d.scene.mixin`: `f3d_code`, `f3d_alias`, `f3d_kind`, `action_f3d_show()`, `search_f3d(code)` на `stock.location`, `mrp.workcenter`, `maintenance.equipment`, `hr.employee`, `f3d.zone`, `stock.picking.batch`; кнопки «Показати в 3D» на їхніх формах (base CB-02, X-08) | `factory3d_base` | ключ між payload і записами; резолвер FR-24 (`search_f3d`); `action_f3d_show()` (base CB-02) повертає `{type: "ir.actions.client", tag: "f3d_viewer.action", name: "Завод 3D", target: "current", params: {code, alias, model, res_id, kind}}`, а без viewer — `display_notification`; переглядач читає `params.code`, решта ключів довідкові |
| C-08 | `f3d.zone` (код, назва, тип, полігон, `is_roof`, `root_location_id`; 45 активних — 34 цеху + 11 надвірних), ворота = `stock.location` з `f3d_side`, `f3d_dock_no`, `f3d_accepts`, `f3d_zone_id`; `stock.location.f3d_loc_kind`, `f3d_capacity`; `stock.picking.batch.f3d_code` — єдиний код фури в 3D, `f3d_truck` — опис/назва фури (не код, не держномер), `f3d_vehicle_id` (base CB-06, X-15) | `factory3d_base` | розділи `zones` (усі 45, контури надвірних з `polygon`, X-29), `docks`, `locations[].kind/capacity` (X-14), поле `pickings[].dock/truck/vehicle` (`truck` = `batch_id.f3d_code`; R-05 у SPEC) |
| C-09 | паспорт обладнання (`f3d_role`, `f3d_manufacturer`, `f3d_model`, `f3d_spec_ids`) | `factory3d_base` | `equipment[code].manufacturer/model`; `passports` лишаються зі статики (повніші: джерела, вузли «у складі») |
| — | групи `group_f3d_user`, `group_f3d_manager`, `group_f3d_admin`; кореневе меню застосунку «Завод 3D» `factory3d_base.menu_f3d_root` | `factory3d_base` | меню модуля — під коренем base (Q-01) |

Що віддає іншим модулям (контракти §6.7 каркаса, деталі — SPEC §2 M-01, §7):

| ID | Контракт | Споживачі |
|---|---|---|
| C-02 | Хук постачальника (duck-typing, X-22; каркас §6.7): провайдер = будь-яка модель `f3d.viewer.provider.<key>` — або `_inherit = "f3d.viewer.provider"` (абстрактна модель viewer з умовчаннями; вбудовані провайдери й містки auto_install), або `AbstractModel` за префіксом **без** `_inherit` (модуль не залежить від viewer). Обов'язкові: `_f3d_sequence` (int), `_f3d_sections` (tuple ключів), `_f3d_group` (xml-id групи для читання), `_f3d_viewer_collect(self, payload: dict, ctx: dict) -> None`, `_f3d_viewer_delta(self, patch: dict, ctx: dict) -> None`; необов'язковий `_f3d_viewer_bus_models(self) -> list[str]`; viewer читає їх через `getattr` з умовчаннями. Чужі й спільні розділи провайдер лише доповнює хелпером `deep_merge` (`factory3d_viewer/tools/payload.py`; X-23, X-82). Порядок: вбудовані 20…70, machine_connect 75, вбудований `signals` 90, telemetry 95, energy 100, lighting 110, ventilation 120, fire 130, evacuation 140, infra 150, genset 155, yard 160, access 170 (X-27) | `factory3d_machine_connect` (`machines` 75, CM-05), `factory3d_telemetry` (`telemetry` 95 у містку `factory3d_telemetry_viewer` — перекриває `x_f3d_signal`), `factory3d_energy` (`energy` 100, `infra` 150), `factory3d_bms` (`lighting` 110, `ventilation` 120), `factory3d_fire_safety` (`fire` 130, `evacuation` 140, місток `factory3d_fire_safety_viewer`), міст `factory3d_genset` (`genset` 155), `factory3d_yard` (`yard` 160), `factory3d_access` (`access` 170) |
| C-03 | Канал шини `f3d_viewer`, повідомлення `{"model": str, "codes": [str], "kind": "state"|"stock"|"doc"|"signal"|"maintenance", "ts": ISO-UTC}`; публікація — `self.env["f3d.viewer.event"]._notify(model, codes, kind)` (коалесценція і запис події) | усі модулі, що змінюють стан об'єктів сцени |
| C-04 | `GET /f3d/viewer/static`, `/data`, `/delta`, `/resolve`, `/snapshots`, `/snapshot/<id>`, `POST /f3d/viewer/cycle_check`; `GET /f3d/kiosk/<token>[/static|/data|/delta]` | клієнт переглядача, кіоск, тести інших модулів |
| C-05 | Клієнтська дія `f3d_viewer.action` з `params` (FR-02); кнопка «Показати в 3D» | `factory3d_base` (метод домішки), інші модулі для своїх форм (`factory3d_yard` — рейси) |
| C-06 | `f3d.viewer.snapshot` (знімок payload), `f3d.viewer.event` (події) | `factory3d_fire_safety` (журнал навчальних тривог може посилатися на знімок), звіти |
| C-07 | Шлях сигналу в payload = `f3d.signal.code` (§5 каркаса): `energy/consumers/<code>/p_now`, `equipment/<code>/battery`, `ventilation/units/<code>/filter_dp_pa`, `infra/totals/pv_now`, `fire/groups/<code>/dust`, `energy/transformers/<code>/temp_c` (повний перелік 196 шляхів — SPEC Додаток C) | `factory3d_telemetry`, `factory3d_iot_sim` |

### 2.2 Архітектурна схема

```
 Браузер (бекенд Odoo)                                 Планшет / ТВ у цеху (кіоск)
 ┌──────────────────────────────────────────┐          ┌────────────────────────────────────────┐
 │ OWL F3dViewerAction (tag f3d_viewer.action)│          │ /f3d/kiosk/<token>  (auth=public)       │
 │   └─ F3dViewer core (static/src/viewer/*) │          │   └─ F3dViewer core, lite=auto,         │
 │        three-bundle.esm.js (import())     │          │      без шини: /delta кожні 15 с         │
 │        parts/*.glb (ETag, ?v=hash)        │          │      with_user(user_kiosk)               │
 │   DataClient: /static → /data → bus →     │          └───────────────┬────────────────────────┘
 │               /delta (debounce 1,5 с)     │                          │ HTTP
 └───────────┬───────────────▲───────────────┘                          │
   HTTP JSON │               │ websocket bus.bus, канал f3d_viewer      │
 ┌───────────▼───────────────┴──────────────────────────────────────────▼────────────────────────┐
 │ Odoo 19 · factory3d_viewer                                                                     │
 │  controllers/viewer.py   controllers/kiosk.py                                                  │
 │        │                                                                                       │
 │  tools/payload.py  PayloadBuilder(env_user, ctx)                                               │
 │   1. static/data/model_static.json  (зони, шаблони шляхів, energy/lighting/vent/fire/infra/   │
 │      evacuation/passports — з plant/ під час збирання)                                         │
 │   2. провайдери модуля:  stock(20) production(30) logistics(40) quality(45) maintenance(50)    │
 │                          people(60) chains(70) signals(90)                                     │
 │   3. провайдери f3d.viewer.provider.* інших модулів (за префіксом, duck-typing): mc 75,        │
 │      telemetry 95, energy 100, bms 110/120, fire 130/140, infra 150, genset 155, yard 160,     │
 │      access 170; спільні розділи — deep_merge (X-22, X-23, X-27)                               │
 │   кожен крок: check_access('read') → search_read як користувач → try/except → meta.sections    │
 │        │                                                                                       │
 │  bus емітери (write/create/unlink на stock.quant, stock.move.line, stock.picking, batch,       │
 │    mrp.workorder, mrp.production, mrp.workcenter, productivity, maintenance.request)           │
 │    → f3d.viewer.event._notify → cr.precommit коалесценція → bus.bus._sendone('f3d_viewer',…)  │
 │        │                                                                                       │
 │  f3d.viewer.event (журнал подій, джерело /delta)    f3d.viewer.snapshot (знімки, крон 10 хв)   │
 │  f3d.demo.wizard (35 кроків, OrmProxy, крон-черга)   f3d.viewer.cycle.check (звіт)             │
 │  x_f3d_signal (factory3d_iot_sim, фаза 1) ← крон щохвилини → bus kind=signal                   │
 └────────────────────────────────────────────────────────────────────────────────────────────────┘
   Збирання (поза Odoo, Node + Python):  plant/export_viewer_assets.py
   → static/data/model_static.json, static/data/demo_payload.json, static/model/parts/* (копія dist/parts),
     static/lib/three/three-bundle.esm.js (esbuild), static/model/parts/manifest.json з хешами
```

### 2.3 Нові й розширені об'єкти — огляд

| Модель | Тип | Призначення | Хто пише | Хто читає |
|---|---|---|---|---|
| `f3d.viewer.provider` | AbstractModel | хук C-02; умовчання атрибутів duck-typing: `_f3d_viewer_collect` нічого не робить, `_f3d_viewer_delta` — дельта за замовчуванням з `deep_merge` (SPEC M-01, R-14) | модулі-постачальники: наслідування (містки auto_install) або модель за префіксом без `_inherit` | `tools/payload.py` (`PayloadBuilder`, `DeltaBuilder`, `deep_merge`) |
| `f3d.viewer.provider.stock` … `.signals` (8 шт.) | AbstractModel | вбудовані провайдери розділів | — | збирач |
| `f3d.viewer.snapshot` | Model | знімок payload (gzip-вкладення), `ts`, `kind`, `size`, `shift_date` | крон, `_notify(kind=event)` для подій рівня «зупинка» | `/snapshots`, меню «Журнал станів» |
| `f3d.viewer.event` | Model | події шини: `ts`, `model`, `codes` (JSON), `kind`, `user_id` | емітери (`_notify`) | `/delta`, «Потік зміни», ротація |
| `f3d.demo.wizard` | TransientModel | майстер заливки демо: кроки, прогрес, лог, стоп-кран | адміністратор | крон «3D: заливка демо» |
| `f3d.viewer.cycle.check` | TransientModel | звіт перевірки циклу: результат HTML, кількість проблем | менеджер | — |
| `res.config.settings` (розширення) | TransientModel | параметри `factory3d.viewer.*`, кнопка «Новий токен кіоска», посилання на URL кіоска | адміністратор | — |
| `mrp.production`, `stock.picking`, `sale.order` (розширення) | Model | `action_f3d_show()` для документів (не домішка) | — | кнопки форм |
| `stock.quant`, `stock.move.line`, `stock.picking`, `stock.picking.batch`, `mrp.workorder`, `mrp.production`, `mrp.workcenter`, `mrp.workcenter.productivity`, `maintenance.request` (розширення) | Model | емітери шини: `create`/`write`/`unlink` → `_f3d_notify()` з кодами сцени | ORM | шина |
| `res.users` `factory3d_viewer.user_kiosk`, `res.groups` `group_f3d_kiosk` | дані | технічний користувач і група кіоска | `data/kiosk_user.xml` | контролер кіоска |

### 2.4 Інтеграції

Пристроїв у модулі немає (усі сигнали приходять через `factory3d_telemetry`/`factory3d_iot_sim`).
Зовнішні взаємодії:

| Що | Протокол | Напрямок | Частота | При недоступності |
|---|---|---|---|---|
| Браузер користувача ↔ Odoo | HTTP JSON (`/f3d/viewer/*`), websocket `bus.bus` | двонапрямно | `/static` раз на сесію (ETag), `/data` при відкритті, `/delta` за подіями (≥ 1,5 с між запитами) | шина впала → опитування `/delta` 30 с; `/data` 5xx → повідомлення, повтор через 10 с ×5 |
| Планшет кіоска ↔ Odoo | HTTP JSON `/f3d/kiosk/<token>/*` | планшет → Odoo | `/delta` кожні 15 с | мережі немає → банер «немає зв'язку», дані лишаються; після 5 помилок — перезавантаження сторінки |
| `factory3d_iot_sim` (`x_f3d_signal`) | ORM у тому ж процесі | читання | у кожному `/data` і `/delta`; крон публікації в шину раз на хвилину | моделі немає → `meta.iot` відсутній, значення зі статики |
| `factory3d_telemetry` (`f3d.signal`) — фаза 2 | хук C-02 | читання | як вище | модуль не встановлено → провайдер відсутній |

### 2.5 Потік даних від пристрою до екрана

Приклад: оператор на SAW-1 завершив операцію «Розкрій» (`mrp.workorder.button_finish`).

1. ORM пише `mrp.workorder.state = done`, `date_finished`, створює/закриває рядок
   `mrp.workcenter.productivity` (`date_end`), оновлює `mrp.production.state`/`reservation_state`,
   `mrp.workcenter.working_state`.
2. Перевизначені `write()` викликають `self.env["f3d.viewer.event"]._notify("mrp.workorder",
   codes=["WO00013"], kind="state")`, `_notify("mrp.workcenter", ["SAW-1"], "state")`,
   `_notify("mrp.production", ["WH/MO/00231"], "doc")`. `_notify` складає коди в
   `self.env.cr.precommit.data["f3d_viewer.notify"]` (ключ — модель) і реєструє один обробник
   precommit на транзакцію.
3. На precommit обробник створює рядки `f3d.viewer.event` (по одному на модель) і викликає
   `bus.bus._sendone("f3d_viewer", "f3d_viewer", {"model": "mrp.workorder", "codes": ["WO00013"],
   "kind": "state", "ts": "2026-10-12T07:30:12Z"})` для кожної моделі; `bus.bus` відправляє після commit.
4. Клієнт (`DataClient`) отримує 3 повідомлення, накопичує 1 500 мс, робить один
   `GET /f3d/viewer/delta?since=<ts останнього успішного патча>&codes=WO00013,SAW-1,WH/MO/00231`.
5. Контролер читає `f3d.viewer.event` після `since`, групує коди за моделями, викликає
   `_f3d_viewer_delta(patch, ctx)` провайдерів `production` (перебудовує `workorders["WO00013"]`,
   `workcenters["SAW-1"]`, `productions[name="WH/MO/00231"]` з `progress`, `supply`, `delivery`) і
   `chains` (якщо змінилось `full_cycle_mo`), повертає `{"ts": …, "patch": {...}, "removed": {}}`.
6. Клієнт зливає патч у дані глибоко (`deepMerge(D, patch)`, FR-42: `D.workorders.WO00013` доповнюється повним записом,
   ключі інших провайдерів у записах лишаються), оновлює смуги `data-p="wo:WO00013"`,
   перефарбовує `SAW-1` (`paint`), перемальовує шар «Замовлення в роботі» для цього МО
   (`drawProdOverlay` лише для `prodOv.byMo` цього МО), якщо відкрита картка цього МО — `renderPanel(true)`.
7. Кіоск робить те саме, але крок 4 — за таймером 15 с без шини.

### 2.6 Безпека

- Групи: читання переглядача — `factory3d_base.group_f3d_user`; налаштування знімків, перевірка
  циклу, журнал станів — `group_f3d_manager`; токен кіоска, демо, стоп-крани — `group_f3d_admin`
  (входить у `base.group_system`); кіоск — технічний користувач `user_kiosk` у групі
  `factory3d_viewer.group_f3d_kiosk` (implied: `base.group_user`, `stock.group_stock_user`,
  `mrp.group_mrp_user`, `factory3d_base.group_f3d_user`), пароль не задано (інтерактивний вхід неможливий),
  `share=False`. Група кіоска — у власному привілеї модуля `factory3d_viewer.privilege_f3d_viewer` категорії
  `factory3d_base.module_category_factory3d` (sequence 10; X-19), драбину груп base не змінює.
- `sudo()` у контролерах і провайдерах заборонений (lint-тест `test_no_sudo_in_payload` перевіряє
  grep по `tools/` і `controllers/`); єдине місце з підвищенням — `with_user(user_kiosk)` у
  `controllers/kiosk.py` після перевірки токена, і `ir.config_parameter.sudo().get_param` для читання
  параметрів (параметри не містять секретів, крім токена кіоска, який порівнюється через `hmac.compare_digest`).
- Розділи за групами (деталі — SPEC §4 таблиця «Розділи payload»): `locations`/`products`
  (`stock.group_stock_user`), `productions`/`workorders`/`workcenters` (`mrp.group_mrp_user`),
  `pickings`/`docks` (`stock.group_stock_user`), `sale_orders` (`sales_team.group_sale_salesman`;
  `amount` — лише `sales_team.group_sale_salesman_all_leads`), `purchase_orders`
  (`purchase.group_purchase_user`), `quality_checks` (`quality.group_quality_user`),
  `equipment`/`maintenance_requests` (`base.group_user`, як у стандартних правах maintenance),
  `employees` (`base.group_user`: лише `name`, `job`, `department`, `shift`, `workcenter`,
  `current_workorder` — поля публічного профілю; читання `hr.employee.public` без `sudo`, `f3d_code` — дзеркало
  base M-10a, X-09), статика — `group_f3d_user`. `productions[].energy_cost` — лише група
  `factory3d_energy.group_f3d_energy_cost` і не кіоск; без неї статична вартість не віддається (X-25).
- Стоп-крани: `factory3d.viewer.demo_enabled` (демо), `factory3d.viewer.bus_enabled` (публікація в
  шину; `False` — клієнт опитує `/delta` раз на 30 с), `factory3d.viewer.kiosk_enabled`
  (кіоск; `False` → 404). `neutralize.sql`: `demo_enabled=False`, `kiosk_enabled=False`, новий
  випадковий `kiosk_token`, вимкнути крони модуля.
- Токени/паролі в логах не друкуються; URL кіоска показується лише в налаштуваннях для `group_f3d_admin`.
- Ін'єкції: `code`, `codes`, `since`, `date` валідуються регулярними виразами
  (`^[A-Za-z0-9/_.-]{1,64}$` для коду, ISO-8601 для дат); домен ORM будується списком, не рядком.
- CSRF: усі маршрути — `GET` з `type="http"` + JSON-відповідь або `type="jsonrpc"` для `POST`
  (`cycle_check`), стандартний CSRF Odoo.
- Шина: повідомлення містять лише коди й назви документів, жодних значень; канал `f3d_viewer` — рядковий,
  доступний будь-якому автентифікованому користувачу (значення все одно йдуть через `/delta` з правами).

### 2.7 Продуктивність і обсяги

Виміряно 13.10.2026 на тестовому сервері timur-o19demo, база `odoo` (лише читання):

| Що | Значення |
|---|---|
| Записів: `stock.location` 723 (697 зі штрихкодом), `stock.quant` 1 434 (976 ненульових), `stock.move` 1 923, `stock.move.line` 1 917, `stock.picking` 42, `stock.picking.batch` 6, `mrp.production` 32, `mrp.workorder` 199, `mrp.workcenter` 35, `mrp.workcenter.productivity` 184, `maintenance.equipment` 208, `maintenance.request` 17, `hr.employee` 36, `product.product` 59, `stock.warehouse.orderpoint` 167, `sale.order` 8, `purchase.order` 13, `quality.check` 5, `x_f3d_signal` 196, `x_f3d_reading` 1 568 | база демо |
| Повна побудова payload через XML-RPC (`LiveDemo.build`) | 8,4 с (≈ 25 викликів × 0,4 с мережі) |
| Статична генерація `Demo().build()` | 0,11 с |
| Payload повний | 1,07 МБ raw / 122 КБ gzip |
| з них `passports` | 521 КБ / 65 КБ gzip (статика → `/static`) |
| `locations` 155 КБ / 12,7 КБ · `productions` 191 КБ / 10 КБ · `workorders` 45 КБ / 5 КБ · `pickings` 21 КБ / 3 КБ | жива частина ≈ 530 КБ raw / 55 КБ gzip |
| GLB частини | 13,7 МБ разом; `core` 9,8 МБ |

Цілі модуля (перевіряються в SPEC §13.4): `/data` (жива частина) ≤ 1,5 с і ≤ 80 SQL-запитів на демо-базі
(ORM у процесі, без мережевих затримок XML-RPC); `/static` ≤ 100 мс після першого читання (кеш у
пам'яті воркера, інвалідація за mtime файлу); `/delta` ≤ 300 мс при ≤ 50 кодах; перше відкриття
переглядача на ПК ≤ 6 с при ≥ 20 Мбіт/с (`core` 9,8 МБ), повторне ≤ 2 с (кеш); планшет у `lite`:
перше ≤ 12 с, повторне ≤ 3 с.

Обсяги в базі: `f3d.viewer.event` — на демо ≈ 300 подій/зміну, на проді оцінка ≤ 20 000/добу
(35 верстатів, ≈ 2 000 рядків переміщень/добу), ротація 14 днів → ≤ 300 000 рядків, індекс по `ts`;
`f3d.viewer.snapshot` — 51 знімок/зміну × ≈ 130 КБ gzip ≈ 6,6 МБ/добу, 14 днів ≈ 93 МБ у filestore.

### 2.8 Міграція з демо-бази і деінсталяція

`post_init_hook` (`hooks.py:post_init`), кожен крок ідемпотентний, виконується від `SUPERUSER_ID`
(дозволено для хуків установки):

1. Створити групу `group_f3d_kiosk`, користувача `user_kiosk` (дані XML, `noupdate=1`), згенерувати
   `factory3d.viewer.kiosk_token` (`secrets.token_hex(16)`), якщо параметра немає.
2. `factory3d.viewer.demo_enabled`: `True`, якщо в базі є `ir.module.module` `factory3d_iot_sim`
   у стані `installed` або компанія називається «Меблева фабрика (демо)» (ознака тестової бази), інакше
   `False`. `kiosk_enabled=True`, `bus_enabled=True`, `demo_clock`: `"2026-10-12 10:30"` на демо-базі
   (та сама ознака), інакше порожньо.
3. Перевірити наявність 697 кодів сцени в базі: для кожного коду з `manifest.parts[].codes` знайти запис
   через резолвер і записати в лог підсумок «кодів у моделі 1 089, знайдено записів 697, без запису 392
   (інженерні об'єкти без моделі в Odoo — норма)»; нічого не створювати (коди створює `factory3d_base`).
4. Зробити перший знімок `f3d.viewer.snapshot` (`kind=install`).

Демо-поля `x_dock`, `x_truck`, `x_vehicle` цей модуль не читає й не мігрує (власник — `factory3d_base`,
§6.2). Дані `x_f3d_signal` читаються динамічно через `self.env.get("x_f3d_signal")` і не мігруються
(власник — `factory3d_telemetry`, фаза 2).

`uninstall_hook`: вимкнути крони модуля (вони видаляються разом з XML-даними), видалити параметри
`factory3d.viewer.*`; знімки й події видаляються разом із таблицями моделей (бізнес-даних вони не
містять); користувач `user_kiosk` архівується (`active=False`), не видаляється.

## 3. Налаштування системи

| Об'єкт | Параметр | Значення (як заповнювати) | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `factory3d.viewer.snapshot_minutes` | `10` (тест і прод) | інтервал знімків, 5…60 |
| `ir.config_parameter` | `factory3d.viewer.snapshot_hours` | `06:30-16:00` | вікно знімків за Києвом; порожньо — цілодобово |
| `ir.config_parameter` | `factory3d.viewer.snapshot_keep_days` | `14` | ротація знімків і подій |
| `ir.config_parameter` | `factory3d.viewer.event_keep_hours` | `48` | після цього `/delta` відповідає `full` |
| `ir.config_parameter` | `factory3d.viewer.delta_debounce_ms` | `1500` | дебаунс клієнта |
| `ir.config_parameter` | `factory3d.viewer.kiosk_token` | генерується (32 hex) | показується лише `group_f3d_admin`; кнопка «Новий токен кіоска» |
| `ir.config_parameter` | `factory3d.viewer.kiosk_enabled` | тест `True`, прод `True` після приймання екранів | стоп-кран кіоска |
| `ir.config_parameter` | `factory3d.viewer.kiosk_refresh_s` | `15` | опитування кіоска, 5…120 |
| `ir.config_parameter` | `factory3d.viewer.bus_enabled` | `True` | стоп-кран публікації в шину |
| `ir.config_parameter` | `factory3d.viewer.demo_enabled` | тест `True`, прод `False` | стоп-кран майстра демо |
| `ir.config_parameter` | `factory3d.viewer.demo_clock` | тест `2026-10-12 10:30`, прод порожньо | демо-годинник для таймерів (README «Демо-годинник») |
| `ir.config_parameter` | `factory3d.viewer.lite_default` | `auto` | `0`/`1`/`auto` |
| `ir.cron` | «3D: знімок стану» | кожні 10 хв, активний | метод `f3d.viewer.snapshot._cron_snapshot` |
| `ir.cron` | «3D: ротація журналу станів» | щодня 02:30, активний | `_cron_rotate` |
| `ir.cron` | «3D: сигнали імітації в шину» | щохвилини, активний лише якщо є `x_f3d_signal` | `f3d.viewer.event._cron_signal_bus` |
| `ir.cron` | «3D: заливка демо» | вимкнений; вмикає майстер на один прогін | `f3d.demo.wizard._cron_run` |
| `res.users` | `user_kiosk` (логін `f3d_kiosk`) | без пароля, група `group_f3d_kiosk`, компанія — перша | одна ліцензія Enterprise (Q-02) |
| Планшет цеху | URL | `https://<сервер>/f3d/kiosk/<token>?tab=production&mode=oee&lite=1` | Chrome «Додати на головний екран», режим кіоска Knox |
| ТВ у диспетчерській | URL | `…/f3d/kiosk/<token>?tab=overview&layers=prod` | `layers=prod` = шар «Замовлення в роботі» |

## 4. Інструкція

**«Показати в 3D» з документа** (майстер, комірник, механік). 1. Відкрийте форму МО, переміщення,
робочого центру, місця зберігання, обладнання, співробітника, зони або замовлення клієнта. 2. У шапці
натисніть «Показати в 3D». 3. Переглядач відкриється з вибраним об'єктом або маршрутом документа; у картці
праворуч — ті самі дані, що на формі. 4. Кнопка «← Назад» у Odoo повертає на форму.

**З 3D у форму Odoo** (усі). 1. Клацніть по об'єкту в сцені або по рядку в панелі. 2. У картці
натисніть «Відкрити в Odoo». 3. Якщо запису в базі немає (інженерний об'єкт без моделі), з'явиться
повідомлення, переглядач лишається відкритим.

**Екран у цеху** (адміністратор, один раз на екран). 1. Завод 3D → Налаштування → Налаштування переглядача → скопіюйте «URL кіоска».
2. Додайте потрібні параметри: `?tab=production&mode=oee` (дільниця), `?tab=overview&layers=prod`
(диспетчерська), `&lite=1` для планшета. 3. На планшеті відкрийте URL у Chrome і «Додати на головний
екран» або закріпіть у Samsung Knox Kiosk. 4. Якщо токен скомпрометовано — «Новий токен кіоска», старі
адреси перестануть працювати одразу; оновіть URL на екранах.

**Програвання зміни** (менеджер, майстер). 1. У переглядачі натисніть ▶ або тягніть повзунок 07:00–15:30.
2. Якщо на цей день є знімки (Завод 3D → Журнал станів), повзунок показує реальні стани на той час; якщо
ні — план за датами завдань (позначка «план» біля часу). 3. «Зараз» повертає до живих даних.

**Перевірка циклу** (менеджер). 1. Завод 3D → Перевірка циклу → «Запустити». 2. «Цикл замкнений» —
усе гаразд; інакше список проблем, кожен рядок відкриває документ або об'єкт. 3. Типові причини:
приймання без воріт (немає пакетного переміщення з доком), відвантаження з рядками, що не збігаються
з замовленням, компонент МО без шляху (немає приймання цього товару).

**Демо-дані на тестовому сервері** (адміністратор). 1. Переконайтесь, що це не прод (у налаштуваннях
«Заливка демо дозволена» увімкнена лише на тесті). 2. Завод 3D → Демо-дані → «Запустити всі кроки» (або
оберіть кроки). 3. Майстер працює у фоні 10–20 хв; прогрес і лог — у тому ж вікні («Оновити»).
4. Повторний запуск нічого не дублює.

## 5. Ризики й відкриті питання

| ID | Питання | Кому | Рекомендована відповідь | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | **Закрито 14.10 (рішення менеджера):** імена каркаса підтверджено (base v0.2; кореневе меню «Завод 3D», X-88). Остаточні імена в `factory3d_base`: xml-id кореневого меню «Завод 3D» (`factory3d_base.menu_f3d_root`), груп, домішки `f3d.scene.mixin`, полів воріт `f3d_side`/`f3d_dock_no`, батча `f3d_code` (код фури в 3D; `f3d_truck` — лише опис, X-15)/`f3d_vehicle_id` — вони зафіксовані в каркасі §5–6.2, але SPEC base пишеться паралельно | автор SPEC base, менеджер | підтвердити імена каркаса без змін | SPEC viewer посилається на імена каркаса; при розбіжності — одна правка в `views/menus.xml` і `tools/payload.py` |
| Q-02 | Технічний користувач кіоска займає одну ліцензію Enterprise на базу (усі екрани — один користувач) | замовник, менеджер | погодити одну ліцензію; альтернатива (`share=True`/портальний користувач) не має прав на `mrp.*`/`stock.*` | створюємо `user_kiosk` як внутрішнього |
| Q-03 | **Закрито 14.10 (рішення менеджера):** так — base створює пакет на кожне переміщення з `x_dock` (base Q-02, R-11). Чи створює `factory3d_base` при міграції пакетні переміщення з `dock_id` для **всіх** переміщень з `x_dock` (зараз у демо лише 6 — тільки з фурами) | автор SPEC base | так: один батч на кожне переміщення з `x_dock`, без фури — `f3d_code` (код фури в 3D, CB-06, X-15) порожній | правило R-05 у SPEC: док без батча визначається за місцем `UNLOAD-k`/`DOCK-Ek` рядків переміщення |
| Q-04 | **Закрито 14.10 (рішення менеджера):** фіксований `2026-10-12 10:30`; зсув дат — крок майстра демо у фазі 2. Демо-годинник на тестовому сервері: лишати `2026-10-12 10:30` (документи демо прив'язані до цієї дати) чи щоночі зсувати документи демо на «сьогодні» | менеджер | лишати фіксований; зсув дат — окремий крок майстра демо у фазі 2 | параметр `demo_clock`, порожній на проді |
| Q-05 | Зберігання знімків: 14 днів ≈ 93 МБ у filestore — достатньо чи потрібно 30 днів для розборів змін | замовник | 14 днів; знімки з подіями «зупинка» позначати `kind=event` і зберігати 90 днів | параметр `snapshot_keep_days` |
| Q-06 | **Закрито 14.10 (відповідь № 19, CONSISTENCY):** Wi-Fi вважаємо наявним; без зв'язку — банер і lite-режим. Планшети цеху: Samsung Galaxy Tab Active5 Pro у Knox Kiosk — чи є корпоративний Wi-Fi у всіх зонах (`WIFI` у моделі — 12 точок) | замовник | так, інакше кіоск працює з банером «немає зв'язку» | режим offline-банера FR-33 |
| Q-07 | **Закрито 14.10 (рішення менеджера):** лишаємо як у SPEC: `amount` лише з `group_sale_salesman_all_leads`. Чи потрібен переглядачу розділ `sale_orders[].amount` (суми) взагалі — у макеті він лише в даних, у вкладках не показується | менеджер | не віддавати суми в payload | `amount` віддається лише з `group_sale_salesman_all_leads` |
| Q-08 | **Закрито 14.10 (відповідь № 19, CONSISTENCY):** `quality_control` на проді буде; розділ — за наявності моделі. `quality.check` — Enterprise `quality_control`; чи буде він на проді | замовник | так (контроль плит у макеті) | розділ умовний (A-04) |

Ризики:

- R-A Регресія поведінки макета при переносі 2 287 рядків JS у модулі: мітигація — ядро лишається одним
  файлом-класом, статична сторінка збирається з того самого ядра (FR-38), тести панелі в HOOT на
  зафіксованому `demo_payload.json`.
- R-B WebGL у headless Chrome тестів Odoo: тури не можуть покладатись на рендер; ядро має «нульовий
  рендерер» (`f3d_test=1`), тури перевіряють панель і дані, не пікселі.
- R-C Транспілятор Odoo й сторонній ESM: обійдено A-01 (бандл + `import()`), але CSP політики клієнта
  можуть блокувати `import()` з того самого домену — не блокують (same-origin), перевіряється в DEPLOY_TEST.
- R-D Навантаження шини на проді: 2 000 рядків переміщень/добу × коалесценція → ≤ 20 000 повідомлень/добу,
  прийнятно для `bus.bus`; стоп-кран `bus_enabled`.
- R-E Різниця між `check_access` (Odoo 19) і `check_access_rights` (≤ 17): використовуємо лише 19-й API.

## 6. План сборки агентами

Порядок злиття: W0 → (W1 ∥ W2 ∥ W3) → W4 → (W5 ∥ W6) → приймання. Межі файлів — за §0 SPEC.

| Воркер | Межі файлів | Що здає | Залежить від |
|---|---|---|---|
| W0 каркас | `__manifest__.py`, `__init__.py`, `hooks.py`, `security/*`, `data/params.xml`, `data/kiosk_user.xml`, `data/cron.xml`, `views/menus.xml`, `tools/__init__.py`, `tests/common.py` (фікстура з демо-базою), `static/lib/three/three-bundle.esm.js` (зібраний), `static/model/*`, `static/data/*` (зібрані скриптом `plant/export_viewer_assets.py`, який теж здає W0) | модуль встановлюється на копію демо-бази, порожнє меню, тести `test_install.py` зелені | — |
| W1 дані | `models/viewer_provider.py`, `tools/payload.py` (зокрема `deep_merge`, `default_delta`; X-22, X-23, X-82), `tools/cycle_check.py`, `tools/dates.py`, `controllers/viewer.py` (static/data/delta/resolve/cycle_check), `tests/test_payload_*.py`, `tests/test_resolver.py`, `tests/test_access.py`, допоміжний модуль `odoo_addons/test_factory3d_viewer/*` (провайдери `zz_test`, `zz_fail` для AC-12/13, `zz_duck` для AC-57…AC-59) | `/data?full=1` на демо-базі проходить `cycle_check` без проблем і збігається з `dist/odoo_demo.json` за схемою (Додаток A) | W0 |
| W2 клієнт | `static/src/viewer/*.js`, `static/src/viewer/viewer.scss`, `static/src/action/*`, `static/src/kiosk/*`, `views/templates_kiosk.xml`, `tests/static/tests/*.test.js` (HOOT) | клієнтська дія показує модель і панель на `demo_payload.json` (мок `/data`), всі R1–R23 за реєстром, lite-режим | W0 (асети); інтеграція з W1 через контракт API-01…03 |
| W3 шина/журнал | `models/viewer_event.py`, `models/viewer_snapshot.py`, `models/bus_emitters.py`, `data/cron.xml` (доповнення), `views/viewer_snapshot_views.xml`, `tests/test_bus.py`, `tests/test_snapshot.py` | події й знімки пишуться, `/delta` повертає патч, ротація працює | W0, W1 (delta провайдерів) |
| W4 кнопки/кіоск | `views/show_in_3d_views.xml`, `models/mrp_production.py`, `models/stock_picking.py`, міст-модуль `odoo_addons/factory3d_viewer_sale/*` (A-17), `controllers/kiosk.py`, `models/res_config_settings.py`, `views/res_config_settings_views.xml`, `tests/test_show_in_3d.py`, `tests/test_kiosk.py`, тури `static/tests/tours/*.js`, `tests/test_tours.py` | кнопки документів V-08a, V-08b, V-09 (кнопки носіїв домішки — base CB-02, X-08), резолвер з клієнта, кіоск з токеном, тури зелені | W1, W2, W3 |
| W5 демо | `wizard/demo_wizard.py`, `wizard/orm_proxy.py`, `wizard/demo_steps.py` (порт `Push`+`FlowSteps`), `wizard/demo_wizard_views.xml`, `wizard/cycle_check_wizard.py`, `wizard/cycle_check_views.xml`, `tests/test_demo_wizard.py` | на порожній базі з модулями каркаса майстер відтворює демо-базу, `cycle_check` OK; на проді — заблокований | W1 |
| W6 продуктивність і DEPLOY_TEST | `tests/test_perf.py`, `neutralize.sql`, `CHANGELOG.md`, `README.md` модуля, `docs/modules/factory3d_viewer/DEPLOY_TEST.md` | пороги §2.7 підтверджені на копії демо-бази; чек-лист §13.5 пройдений | усі |

## Рішення автора (A-xx)

| ID | Рішення | Обґрунтування | Альтернатива, яку відхилено |
|---|---|---|---|
| A-01 | three.js постачається одним ESM-бандлом `static/lib/three/three-bundle.esm.js` (esbuild на етапі збирання, ≈ 700 КБ мінімізовано), ядро вантажить його `await import(url)`; в асет-бандл Odoo потрапляє лише ядро переглядача | three 0.160 не має UMD-збірки (знято в r160), транспілятор Odoo перетворює ESM регулярними виразами й не гарантує коректність для 1,3 МБ `three.module.js`; `importmap` у бекенді не працює (модулі вже завантажені); CDN заборонений політикою «Odoo не ходить назовні» й недоступний у цеху без інтернету | CDN jsDelivr (як у макеті); `@odoo-module alias=three` над `three.module.js` |
| A-02 | Payload розбито на `/static` (кеш, ETag) + `/data` (жива частина); `?full=1` повертає документ за контрактом; клієнт зливає `D = {...static, ...live}` з перекриттям живих полів | `passports` — 521 КБ з 1,07 МБ і не змінюється між збірками; розділи фаз 2–5 без модулів теж статичні; кіоск на планшеті економить 65 КБ gzip на кожне повне оновлення | один `/data` на 1 МБ |
| A-03 | Кіоск — публічний маршрут з токеном у шляху, дані від `with_user(user_kiosk)`, оновлення опитуванням `/delta` 15 с замість шини | публічна сесія не має стабільної підписки `bus.bus` без входу; `hr_attendance` кіоск Odoo 19 використовує той самий патерн (`/hr_attendance/<token>`, `auth="public"`); `sudo` заборонений §5 | вхід кіоска паролем; websocket на публічній сесії |
| A-04 | `sale`, `purchase`, `quality_control` не додаються в `depends`; розділи будуються, якщо модель є в `env` | каркас §3 задає залежності viewer як `factory3d_base, bus, web`; на базі без продажів переглядач має працювати | тверді залежності |
| A-05 | Провайдери знаходяться скануванням реєстру: усі моделі з іменем `f3d.viewer.provider.<key>` (з `_inherit` чи без), відсортовані за `_f3d_sequence`, потім за іменем; атрибути читаються через `getattr` з умовчаннями (duck-typing, X-22) | прості тести й передбачуваний порядок; не потрібен окремий реєстр-запис; модулі, для яких viewer необов'язковий, не залежать від нього (D-18) | явна реєстрація у `data/*.xml`; обов'язкове `_inherit` |
| A-06 | Коалесценція повідомлень шини в `cr.precommit`, одне повідомлення на модель на транзакцію; клієнт — дебаунс 1,5 с і один запит у польоті | `action_assign` на 12 переміщеннях інакше дав би сотні повідомлень і запитів | повідомлення на кожен `write` |
| A-07 | GLB частини — у `static/model/parts/` модуля (не `ir.attachment`), URL з хешем | статика Odoo віддає `ETag`/`Last-Modified`/`max-age` без коду; 13,7 МБ у filestore ускладнили б бекап і деплой | вкладення модуля |
| A-08 | Майстер демо — порт `Push`/`FlowSteps` на ORM через адаптер `OrmProxy` з тією самою сигнатурою `o(model, method, *args, **kw)`; дані — `demo_payload.json` (= `Demo().build()`), згенерований під час збирання | 1 500 рядків перевіреної логіки заливки переносяться без переписування; генератор з `plant/` у модуль не вноситься (залежить від пакета `plant/`) | переписати кроки з нуля; вендорити `plant/` у модуль |
| A-09 | Знімки зберігаються gzip-JSON у `ir.attachment` (`Binary(attachment=True)`), не в `jsonb` | 130 КБ × 51/день; filestore, а не таблиця; ротація — `unlink` | поле `Json` |
| A-10 | `meta.now` з параметра `demo_clock` (тест) або реальний час (прод); клієнт не імітує прогрес при `meta.live=true` | README «Демо-годинник»; на проді живі дані і так рухаються | завжди реальний час |
| A-11 | **Змінено (X-08, base CB-02):** кнопки «Показати в 3D» на формах носіїв домішки і метод `action_f3d_show` — у `factory3d_base` (без viewer метод повертає `display_notification`); viewer додає кнопки й методи лише для документів `mrp.production`, `stock.picking`, `sale.order` (міст A-17) | base не залежить від viewer: перевіряє стан модуля й повертає dict дії (тег — рядок); дві кнопки на одній формі виключено | кнопки носіїв у viewer (було в 0.1) |
| A-12 | Lite-режим автоматичний за `deviceMemory`/`pointer: coarse`, а не за User-Agent | UA планшетів ненадійний; `deviceMemory` є в Chrome/Samsung Internet | список моделей |
| A-13 | Сигнали фази 1 читаються з `x_f3d_signal` динамічно (`env.get`), без залежності від data-модуля; у фазі 2 провайдер telemetry (sequence 95) перекриває | §5: жодних `x_` полів у прод-модулях — ми їх не створюємо, лише читаємо, поки немає `factory3d_telemetry` | залежність від `factory3d_iot_sim` |
| A-14 | Кореневе меню застосунку «Завод 3D» належить `factory3d_base` (`menu_f3d_root`); viewer додає пункти під ним | base встановлюється першим і має свої довідники (зони, паспорти) | корінь у viewer |
| A-15 | Режим програвання зміни — `plan` (як у макеті) + `snapshots` (новий), автоматичний вибір | знімки реальні лише там, де крон уже працював; план лишається для демо | тільки знімки |
| A-16 | Ядро переглядача — один ES-модуль-клас `F3dViewer` без OWL всередині; OWL — лише обгортка дії та кіоска | те саме ядро збирається в статичну сторінку `dist/` (FR-38) і тестується HOOT без Odoo | переписати панель на OWL-компоненти |
| A-17 | Кнопка і метод `action_f3d_show` для `sale.order` — в окремому міст-модулі `factory3d_viewer_sale` (`depends: factory3d_viewer, sale`, `auto_install: True`) | `_inherit = "sale.order"` неможливий без залежності від `sale`, а `sale` не входить у `depends` за A-04 і каркасом §3; міст — стандартний патерн Odoo | тверда залежність viewer від `sale` |

## Посилання

- Odoo 19 Developer: Assets — https://www.odoo.com/documentation/19.0/developer/reference/frontend/assets.html (бандли, `include`, lazy loading; перевірено 13.10.2026).
- Odoo 19 Developer: Registries (actions, services, systray) — https://www.odoo.com/documentation/19.0/developer/reference/frontend/registries.html.
- Odoo 19 Developer: Testing (HttpCase, тури `web_tour`, HOOT) — https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html.
- Odoo 19 Developer: Security (groups, access rights, record rules, `check_access`) — https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html.
- Odoo 19 Developer: Web controllers — https://www.odoo.com/documentation/19.0/developer/reference/backend/http.html.
- Код Odoo 19: `addons/bus/static/src/services/bus_service.js` (`addChannel`, `subscribe`), `addons/bus/models/bus.py` (`_sendone(channel, notification_type, message)`), `addons/hr_attendance/controllers/main.py` (кіоск з токеном, `auth="public"`), `odoo/tools/js_transpiler.py` (межі транспілятора ESM).
- three.js r160 release notes (видалення UMD-збірок) — https://github.com/mrdoob/three.js/releases/tag/r160.
- gltf-transform (квантування частин) — https://gltf-transform.dev/cli.
- Макет: `viewer/index.html`, `plant/odoo_demo.py`, `plant/odoo_pull.py`, `plant/odoo_push.py`, `plant/odoo_flows.py`, `plant/cycle_check.py`, `build_scene.py`, `dist/parts/manifest.json`, `odoo_addons/factory3d_iot_sim`.
