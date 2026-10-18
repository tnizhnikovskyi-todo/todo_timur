# td_factory3d — технічне рішення

Версія 0.2 · 14.10.2026 (0.1 — 13.10.2026) · автор: агент-архітектор модуля (хвиля 1) · статус: **чернетка на погодження**.
Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-09 (дзеркало коду сцени в `hr.employee.public`, CB-01, FR-14), X-15 (CB-06:
`td_truck` — опис/назва фури, не держномер; код фури в 3D — `td_code`; `td_truck_code` у §2.3 і A-14), X-32 і сторона base у X-69
(CB-09: резерв 55 genset, правило «Налаштування <модуля>» під `menu_td_config` з sequence резерву), сторона base у X-19
(CB-10: у `privilege_td` лише групи base, групи модулів — у власних привілеях категорії).
Каркас проєкту: `docs/ARCHITECTURE.md` (далі «каркас», контракти C-6.1…C-6.8, рішення D-xx).
Специфікація для реалізації й тестування: `docs/modules/td_factory3d/SPEC.md`.
Рішення автора, що відхиляються від каркаса або доповнюють його, позначені **A-xx** (§5.2); відкриті
питання — **Q-xx** (§5.1).
Зміни: 14.10.2026 — закрито рішеннями менеджера: Q-01, Q-02, Q-04, Q-05, Q-07, Q-08, Q-09, Q-10.
Зміни: 14.10.2026 — у макеті додано групи FA-SOC (LSZ 34) і FA-OFFICE (LSZ 35), відповідь № 12г: у базі 2 нові `maintenance.equipment` (паспорт `smoke_detector` Siemens OP720, команда «Служба головного механіка»): обладнання з `td_code` 208 → 210, з паспортом 205 → 207, `passports` макета 205 → 207, прив'язки `fire.groups` 33 → 35 (`FA-SOC` → `Z-SOC`, `FA-OFFICE` → `Z-OFFICE`), обладнання із зоною 168 → 170; §1.1, FR-04, FR-08, §2.8 (кроки 5–7), A-02.

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора; `docs/оцінки` в репозиторії ще немає) |
|---|---|---|
| ТР | цей документ + SPEC.md | 16 |
| Архітектура | погодження A-xx/Q-xx з менеджером, фіксація контрактів CB-xx | 8 |
| Розробка | модуль `odoo_addons/td_factory3d` за SPEC (план сборки §6) | 48 |
| Тестування | юніт-тести на кожен AC, ТК на копії демо-бази, тести прав | 32 |
| Інструкція | §4 цього документа + README модуля + CHANGELOG | 8 |
| **Разом** | | **112** |

Факти про тестовий сервер (перевірено 13.10.2026, лише читання): Odoo `19.0+e-20260926`, сервер
timur-o19demo, база `odoo`, 1 склад `WH` («Меблева фабрика»), 723 локації (697 зі штрихкодом),
35 робочих центрів, 36 співробітників (35 із бейджем), 208 одиниць обладнання (14.10 + `FA-SOC`, `FA-OFFICE` за № 12г — 210), 42 переміщення,
6 пакетних переміщень із доком, поля `x_dock`/`x_truck`/`x_vehicle` на `stock.picking` (manual),
data-модуль `td_iot_sim` установлений (`x_f3d_signal`, `x_f3d_reading`,
`maintenance.equipment.x_f3d_signal_ids` — його мігрує `td_telemetry`, не цей модуль).

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що є в макеті

`td_factory3d` — ядро фази 1: дає всім модулям єдиний ключ «код сцени» між Odoo і 3D, зони цеху,
ворота як доки Odoo 19 і паспорти реального обладнання. Жодного обладнання, протоколів, сервісів.

| Що в макеті | Де саме | Що з цього лягає в Odoo через `td_factory3d` |
|---|---|---|
| Коди об'єктів сцени | glTF extras `code`/`kind` (`dist/parts/manifest.json`), ключі `dist/odoo_demo.json` | `td_code` на 6 моделях (C-6.1). Таксономія кодів — SPEC §9 R-01, додаток A |
| Місця зберігання | `odoo_demo.json → locations` (689: `FG-*` 360, `FUR-*` 144, `RCK-*` 96, `PLT-*` 27, `EB-*` 24, `KIT-*` 12, `FRONTS-*` 8, `UNLOAD-*` 7, `QC-*` 4, `PAL-*` 3, `PACK-STORE`, `PAINT-STORE`, `POST-STAGE`, `OUT-STAGE`); у базі — `stock.location.barcode` (697: ті самі 689 + `DOCK-E1…E7` + `WHSTOCK`) | `stock.location.td_code := barcode` (крім `WH/Stock`), прив'язка до зони `td_zone_id` за префіксом коду (R-08); вид місця `td_loc_kind` і місткість `td_capacity` з `locations[*].kind` / `capacity` (689 / 654 записів, R-21, рішення менеджера 13.10) |
| Робочі центри | `odoo_demo.json → workcenters` (35), `plant/layout.py:MACHINES` (координати, лінії A–E); у базі `mrp.workcenter.code` | `mrp.workcenter.td_code := code`, зона за `zones[*].workcenters` |
| Обладнання | `odoo_demo.json → equipment` (15 карток зі станом), `passports` (207 кодів), `plant/equipment_specs.json` (93 паспорти-ролі), `plant/equipment.py:ROLE_BY_CODE`, `EXTRA_ROLES`, `plant/energy.py:ENERGY_ROLES`, `plant/fire.py:FIRE_ROLES`, `plant/infra.py:INFRA_ROLES`; у базі 210 `maintenance.equipment` (`serial_no` = код сцени для 203; для 7 навантажувачів `serial_no` = демо-серійник `FL-4369`…, код — у xml-id `factory3d.eq_fl_1`) | `td_code` на 210 записах, паспорти як `td.equipment.passport` (93) + специфікації (999 рядків) + джерела (252 URL), зв'язок 207 одиниць → паспорт, 63 зв'язки «у складі» |
| Працівники | `odoo_demo.json → employees` (35, коди `OP-SAW-1`, `OP-W1`); у базі `hr.employee.barcode` без дефісів (`OPSAW1`, `OPW1`), 28 операторів прив'язані до `mrp.workcenter.employee_ids` | `hr.employee.td_code` за таблицею відповідності (SPEC додаток B, 35 рядків) |
| Ворота | `odoo_demo.json → docks` (14: `DOCK-W1…W7`, `DOCK-E1…E7` → документ на воротах), `plant/layout.py:DOOR_Y=[5,15,25,35,45,55,65]`, `DOORS` (ширина 3,4 м), `DOOR_H=4.5`, `RCV_GOODS` (що приймають ворота 1–7), `plant/site.py:167` (об'єкт `DOCK-{side}{k}`, kind `dock`); у базі західні ворота = `WH/Вхід/Ворота k` (barcode `UNLOAD-k`, id 16–22), східні = `WH/Відвантаження/Ворота k` (barcode `DOCK-Ek`, id 725–731) | `stock.location` з `td_kind='dock'`, `td_side`, `td_dock_no`, `td_accepts`, `td_x`/`td_y`, зона; доки зареєстровані в `stock.picking.type.dock_ids` типів Receipts/Delivery (D-03) |
| Фури й техніка на переміщеннях | `pickings[*].dock/truck/vehicle`; `plant/site.py:1425` (`TRUCK-IN-1…3`, `TRUCK-OUT-1…3`); у базі `stock.picking.x_dock` (21 документ), `x_truck` (6), `x_vehicle` (3: `FL-2`, `FL-6`), 6 `stock.picking.batch` з `dock_id` і `vehicle_category_id=«Фура»` (`BATCH/IN/00001…3`, `BATCH/OUT/00004…6`) | міграція у `stock.picking.batch` (C-6.2): `dock_id`, `td_code`/`td_truck` (фура), `td_vehicle_id` (техніка); `x_*` видаляються (§2.8) |
| Зони цеху | `odoo_demo.json → zones` (34: назва, `odoo_location`, `locations`, `workcenters`, `pickings`), `plant/layout.py:ZONES` + `DOOR_ZONES_W/E` (прямокутники в метрах, колір, опис), `ventilation.units[*].zone` (29), `fire.groups[*].zone` (35), `lighting.groups[*].zone` (32) | `td.zone` (34) з контуром, типом, кореневою локацією Odoo, прив'язками комірок/РЦ/обладнання/воріт, лічильниками |
| Надвірні зони (територія) | `plant/infra.py`: `SITE=(-32,-30,182,100)`, `GATES` (`GATE-W` x=−20, `GATE-E` x=168 на південній огорожі y=−30, ширина 8 м), `KPP=(98.4,−27)`, `PARKING=(106,−27,150,−6)`, `TRUCK_SCALE=(172,−14)` 3×18 м, `WASTE=(158,78,176,92)`, `GENSET_POS=(128.5,76.2)`, `BESS_POS=(140,75.4)`, `CHP_POS=(118.6,76.6)`, `CHP_EXH_POS`, `CHP_COOLER_POS=(118.6,81.6)`, `CHP_GRP_POS=(112.5,81)`, `PV_INVERTERS_X=95…106.2` (y=72.5), `ATS_POS=(135.1,68.5)` — усередині будівлі; `plant/site.py:881–919` (силос стружки (62.6,78) r=2, котельня 12×6 при (73.6,78), брикетувальний прес (61.6,82), пожежні резервуари r=3.5 при (8,79) і (17,79), насосна 4×3 при (25,77.5)); `plant/site2.py:build_territory/build_backup/build_chp`; фури `TRUCK-IN-*` при x=−7.3, `TRUCK-OUT-*` при x=157.3; `plant/fire.py:171` уже використовує код зони `Z-BOILER` | `td.zone` типу `outdoor` (11): контур = габарит об'єктів моделі + 1 м (A-19); дах `Z-ROOF` з позначкою `is_roof` (рішення менеджера 13.10, Q-06) |
| Переглядач | `viewer/index.html`: `passportHtml()` (рядки 1910–1922: виробник, модель, причина, таблиця `specs`, `sources`, `connected_note`/`connected_kw`/`connected_sources`, блоки «У складі» з `units`), `zoneHtml()` (1923–1934: «Місце в Odoo», кількість місць, порожні, заповненість, робочі центри з OEE), картка воріт (1807: «Документ на воротах» з `docks[code]`), `pickRow` (1681: ворота · час · «машина біля воріт») | поля паспорта й зони підібрані так, щоб `td_viewer3d` міг зібрати ті самі картки з ORM без статичних даних (контракти CB-05…CB-08) |
| Система координат | `plant/layout.py` рядок 12: «Координати в метрах. X — уздовж будівлі (потік), Y — поперек, Z — угору»; будівля `W, D, H = 150.0, 72.0, 9.0`; захід (приймання) — `x=0`, схід (відвантаження) — `x=150`, південь — `y=0` | `td.zone.polygon` і `stock.location.td_x/td_y` — у цій самій системі (CB-04) |

Чого в макеті **немає** і що не вигадуємо (винесено в Q-xx): держномерів фур, водіїв, перевізників
для воріт, PDF паспортів (лише URL), окремих кодів сцени для силосу, преса, резервуарів і насосної
(вони — частина об'єкта `BOILER`). Контури надвірних зон у `ZONES` відсутні — їх виведено з габаритів
об'єктів території (A-19).

### 1.2 Ролі й сценарії використання

| Роль | Група | Що робить, де |
|---|---|---|
| Будь-який користувач Складу/Виробництва/ТО | `td_factory3d.group_td_user` (входить через `stock.group_stock_user`, `mrp.group_mrp_user`, A-07) | бачить код сцени на формах місця, РЦ, обладнання, працівника, пакета; вкладку «Паспорт» на обладнанні; натискає «Показати в 3D» (працює після встановлення `td_viewer3d`, інакше повідомлення); меню «Завод 3D → Завод → Зони / Ворота / Обладнання / Паспорти» — лише перегляд |
| Технолог / менеджер цеху | `group_td_manager` | правит зони (назва, тип, контур, прив'язки), ворота (сторона, номер, категорії, координати), призначає коди сцени новим об'єктам, редагує паспорти й специфікації |
| Адміністратор системи | `group_td_admin` (входить у `base.group_system`) | параметри `td.base.*`, повторний запуск міграції, видалення/відновлення `x_*` полів, параметр середовища `test`/`prod` |
| Інші модулі factory3d | — | споживають контракти CB-xx: домішку, резолвер кодів, зони, доки, паспорти, меню, групи, параметр середовища |

Меню: кореневе **«Завод 3D»** (`td_factory3d.menu_td_root`), під ним «Завод» → «Зони», «Ворота»,
«Обладнання зі сцени», «Паспорти обладнання»; «Налаштування» → «Параметри» (посилання на
`ir.config_parameter` з фільтром `factory3d.`). Інші модулі додають свої пункти під `menu_td_root`
за зарезервованими `sequence` (§2.1, CB-09), а пункт своїх налаштувань — під «Налаштування» з тим самим `sequence` (X-32).

### 1.3 Функціональні вимоги

| ID | Вимога (перевірювана) | AC у SPEC |
|---|---|---|
| FR-01 | Кожен запис `stock.location`, `mrp.workcenter`, `maintenance.equipment`, `hr.employee`, `td.zone`, `stock.picking.batch` може мати код сцени `td_code`, унікальний у межах моделі, формату `^[A-Z0-9]+(-[A-Z0-9]+)*$`, довжиною ≤ 32 | AC-01…AC-04 |
| FR-02 | За кодом сцени можна знайти запис у межах моделі (`search_f3d`) і серед усіх моделей (`f3d_resolve`) у фіксованому порядку пріоритету; пошук за псевдонімом `td_alias` працює так само | AC-05…AC-07 |
| FR-03 | Кнопка «Показати в 3D» на всіх формах носіїв коду повертає client action переглядача з кодом; без `td_viewer3d` — повідомлення українською, без помилки | AC-08, AC-09 |
| FR-04 | Після встановлення на копію демо-бази коди сцени заповнені: 696 локацій, 14 воріт, 35 РЦ, 210 одиниць обладнання, 35 працівників, 6 фур; жоден запис не продубльовано | AC-10…AC-14 |
| FR-05 | `td.zone` зберігає 45 зон макета (34 цехових + 11 надвірних типу `outdoor`, серед них дах `Z-ROOF` з `is_roof`) з контуром у метрах (система `plant/layout.py`, межі — `SITE` з `plant/infra.py`), типом, кольором, описом, площею (обчислюється), кореневою локацією Odoo, прив'язками й лічильниками | AC-15…AC-19 |
| FR-06 | Ворота — `stock.location` з `td_kind='dock'`, стороною, номером 1–7, категоріями товарів, координатами, зоною; усі 14 зареєстровані в `dock_ids` відповідних типів операцій, тож вибираються у полі «Док» пакета стандартним Odoo 19 | AC-20…AC-24 |
| FR-07 | Демо-поля `x_dock`, `x_truck`, `x_vehicle` перенесено в пакетні переміщення без втрат (21 документ з воротами, 6 фур, 3 техніки → 24 пакети), після звірки поля видалено; при деінсталяції значення повертаються у знову створені `x_*` | AC-25…AC-31 |
| FR-08 | 93 паспорти з `equipment_specs.json` імпортовано як `td.equipment.passport` зі специфікаціями й джерелами; 207 одиниць обладнання прив'язано до паспорта за кодом сцени, 61 одиниця має складові «у складі»; поля `td_*` на `maintenance.equipment` відповідають C-6.3; `note` не чиститься | AC-32…AC-38 |
| FR-09 | Коди працівників відповідають таблиці SPEC додаток B (35 рядків); правило виведення коду з бейджа задокументоване й покрите тестом | AC-39, AC-40 |
| FR-10 | Групи `group_td_user/manager/admin`, категорія «Завод 3D», кореневе меню з зафіксованими xml-id і sequence; права на моделі — за таблицею SPEC §4 | AC-41…AC-45 |
| FR-11 | Параметри `td.base.*` створені зі значеннями за замовчуванням; `post_init_hook` ідемпотентний (повторний запуск не створює дублікатів); `uninstall_hook` не видаляє бізнес-дані; `neutralize.sql` переводить середовище в `test` | AC-46…AC-50 |
| FR-12 | Переглядач/інші модулі отримують для кожного переміщення ворота, фуру й техніку через стандартні поля (`batch_id.dock_id.td_code`, `batch_id.td_code`, `batch_id.td_vehicle_id.td_code`) і пов'язані поля-довідки на `stock.picking` | AC-51, AC-52 |
| FR-13 | `stock.location` має `td_loc_kind` (Selection із 6 видів `locations[*].kind` макета: `stack`, `bin`, `shelf`, `pallet_cell`, `kit`, `area`) і `td_capacity` (Float, місткість в одиницях товару, що там зберігається); після установки на копію демо вид заповнено на 689 локаціях, місткість — на 654; переглядач рахує заповненість як `qty / td_capacity` | AC-53, AC-54 |
| FR-14 | Користувач без прав HR (`base.group_user` без `hr.group_hr_user`) читає й шукає `td_code`, `td_alias`, `td_kind` працівника без `sudo()` — через дзеркало в `hr.employee.public` (X-09); читання інших полів працівника таким користувачем не ламається | AC-55 |

### 1.4 Межі: що не входить

- Жодних сигналів, показань, джерел даних, кронів, ендпоінтів (`td_telemetry`), міграції
  `x_f3d_signal*` (теж `td_telemetry`).
- Сам 3D-переглядач, client action `f3d_viewer`, шина — `td_viewer3d`.
- Рейси сторонніх фур, бронювання воріт, водії, перевізники, шлагбауми — `td_yard`.
- Координати/габарити верстатів, стелажів, світильників — статика моделі (переглядач бере з
  `plant/layout.py`, C-6.7); у base лише контури зон і координати воріт.
- Геометрія комірок (координати, габарити стелажів) — статика моделі; у base лише вид і місткість
  (FR-13).
- Зміна стандартних маршрутів, типів операцій (крім заповнення `dock_ids`), складу.

## 2. Технічна реалізація

### 2.1 Місце в системі

`__manifest__.py → depends`: `stock`, `stock_picking_batch`, `stock_fleet`, `mrp`, `mrp_workorder`
(не потрібен base — прибрано; РЦ дає `mrp`), `maintenance`, `mrp_maintenance`, `hr`, `fleet`
(тягне `stock_fleet`), `web`. Усі встановлені на тестовому сервері.

Що base **бере** від стандарту: `stock.location` (локації, `barcode`), `stock.picking.type.dock_ids`
і `dispatch_management` (`stock_fleet`), `stock.picking.batch.dock_id/vehicle_id/vehicle_category_id/
driver_id` (`stock_fleet`), `maintenance.equipment.workcenter_id` (`mrp_maintenance`),
`hr.employee.barcode`, `mrp.workcenter.code`.

Що base **віддає** іншим модулям (контракти; на них посилаються SPEC хвилі 2):

| ID | Контракт | Для кого |
|---|---|---|
| CB-01 | Домішка `td.scene.mixin`: поля `td_code`, `td_alias`, `td_kind`, `td_viewer_available`; методи `search_f3d(code)`, `f3d_resolve(code)` (`@api.model`), `action_f3d_show()`, `f3d_codes()`; атрибут класу `_f3d_kind`. Носії: `stock.location`, `mrp.workcenter`, `maintenance.equipment`, `hr.employee`, `td.zone`, `stock.picking.batch`. Для `hr.employee` поля `td_code`, `td_alias`, `td_kind` продубльовано в `hr.employee.public` (SPEC M-10a, X-09): провайдери й кіоск читають їх без `sudo()` | усі |
| CB-02 | Кнопка «Показати в 3D»: якщо модуль `td_viewer3d` встановлений (`ir.module.module` `name='td_viewer3d'`, `state='installed'`), `action_f3d_show()` повертає `{'type':'ir.actions.client','tag':'f3d_viewer.action','name':'Завод 3D','target':'current','params':{'code':<td_code>,'alias':<td_alias|False>,'model':<_name>,'res_id':<id>,'kind':<td_kind>}}` (переглядач читає `params.code`; решта ключів — довідкові); інакше `ir.actions.client` `display_notification` з заголовком «Модуль 3D-переглядача не встановлено» (рішення менеджера 13.10) | `td_viewer3d` |
| CB-03 | `td.zone`: поля `td_code` (= код зони, обов'язковий), `name`, `zone_type`, `polygon` (JSON `[[x,y],…]` у метрах), `area_m2`, `x_min/y_min/x_max/y_max`, `color`, `root_location_id`, `location_ids`, `workcenter_ids`, `equipment_ids`, `dock_location_ids`, лічильники; `td_zone_id` на `stock.location`, `mrp.workcenter`, `maintenance.equipment`; метод `zone_at(x, y)` | viewer, access (люди по зонах), bms, fire_safety, yard |
| CB-04 | Система координат: метри, X уздовж будівлі (0 — західна стіна приймання, 150 — східна відвантаження), Y поперек (0 — південна стіна, 72 — північна), Z угору; збігається з `plant/layout.py` і glTF (там Y угору — конвертація `(x, y, z)→(x, z, −y)` лежить у переглядачі, не в base) | усі |
| CB-05 | Ворота: `stock.location` з `td_kind='dock'`, `td_side` (`west`/`east`), `td_dock_no` (1–7), `td_accepts` (many2many `product.category`; порожньо = будь-що), `td_x`, `td_y`, `td_zone_id`; домен доків `[('td_kind','=','dock')]`; док присутній у `stock.picking.type.dock_ids` свого типу (`in_type_id` для `west`, `out_type_id` для `east`). Усі локації: `td_loc_kind`, `td_capacity` (FR-13) | yard, viewer |
| CB-06 | Фура/техніка на переміщенні: `stock.picking.batch.td_code` — **єдиний** код фури в 3D (код об'єкта сцени, напр. `TRUCK-IN-1`; резолвер — `search_f3d`), `td_truck` (Char: опис/назва фури з макета, не держномер і не код; X-15), `td_vehicle_id` (`maintenance.equipment`, навантажувач/тягач); довідкові related на `stock.picking`: `td_dock_id`, `td_dock_code`, `td_truck`, `td_truck_code`, `td_vehicle_id`. Держномер — не в base: `td_yard` `td.yard.visit.plate` (на пакеті related `td_plate`, yard M-07) | viewer, yard, iot_sim, `plant/odoo_pull.py` |
| CB-07 | Паспорт: `td.equipment.passport` (ключ `role`), `td.equipment.spec` (`key`, `name`, `value_text`, `value_num`, `uom`), `td.equipment.source` (`url`, `name`, `kind`); на `maintenance.equipment`: `td_passport_id`, `td_component_passport_ids` і related `td_role`, `td_manufacturer`, `td_model`, `td_reason`, `td_power_kw`, `td_connected_kw`, `td_dimensions`, `td_spec_ids`, `td_source_ids`, `td_units` (C-6.3). Числові параметри для розрахунків — `spec_ids` з `key` (`connected_kw`, `lumen`, `watt`, `airflow_m3h`, `heat_kw`, `kva`, `kwh`, `wp`, `kw_ac`, …) | energy, bms, fire_safety, telemetry |
| CB-08 | Метод `td.equipment.passport.get_num(key)` → `float|None` (значення `value_num` специфікації за ключем) і `maintenance.equipment.f3d_get_num(key)` (з паспорта одиниці) | energy, bms |
| CB-09 | Меню: `td_factory3d.menu_td_root` («Завод 3D», sequence 75 серед кореневих), діти з зарезервованими sequence: 10 viewer, 20 `menu_td_plant` (base), 30 telemetry, 40 machine_connect, 50 energy, 55 genset (міст `td_genset_factory3d`), 60 yard, 70 access, 80 bms, 85 fire_safety, 90 iot_sim (пульт), 99 `menu_td_config` (base). Правило (X-32): пункт «Налаштування <модуля>» (`res.config.settings` модуля або підменю його параметрів) — під `td_factory3d.menu_td_config` з `sequence` = резерв модуля; довідники модуля можуть лишатися в його корені під `menu_td_root`; власні пункти base під `menu_td_config` — 20, 21, 95, 96 (поза чужим резервом) | усі |
| CB-10 | Групи `td_factory3d.group_td_user` ⊂ `group_td_manager` ⊂ `group_td_admin` ⊂ `base.group_system`; категорія `td_factory3d.module_category_factory3d`; у привілеї `td_factory3d.privilege_td` — лише ці три групи base, групи інших модулів — `group_td_<модуль>_<роль>` у власному `res.groups.privilege` цієї категорії (X-19); параметр `td.base.environment` ∈ {`test`,`prod`} — модулі зі стоп-кранами беруть з нього значення за замовчуванням (`read_enabled = environment == 'test'`); `neutralize.sql` base ставить `test` | усі |
| CB-11 | Міграційні утиліти в `td_factory3d/hooks/`: `x_fields.read_manual_field(env, model, name)`, `drop_manual_fields(env, model, names)`, `restore_manual_fields(env, model, spec)` — для міграції `x_*` в інших модулях (telemetry: `x_f3d_signal*`) | telemetry |
| CB-12 | Параметри `td.base.plant_length_m=150`, `plant_width_m=72`, `plant_height_m=9` — будівля (перевірка координат воріт); `td.base.site_x0_m=-32`, `site_y0_m=-30`, `site_x1_m=182`, `site_y1_m=100` — територія (`plant/infra.py:SITE`; перевірка контурів зон) | viewer, bms, fire_safety, yard |

### 2.2 Архітектурна схема

```
┌──────────────────────────────── Odoo 19 (один процес, без сервісів) ─────────────────────────────────┐
│                                                                                                       │
│  td.scene.mixin (CB-01) ──┬── stock.location (+dock: td_side/no/accepts/x/y, td_zone_id)           │
│   td_code / td_alias     ├── mrp.workcenter (td_zone_id)                                           │
│   td_kind / resolve       ├── maintenance.equipment (td_passport_id → td.equipment.passport         │
│   action_f3d_show ─────┐   │        ├── td.equipment.spec (999)   ├── td.equipment.source (252))     │
│                        │   ├── hr.employee                                                            │
│                        │   ├── td.zone (polygon, type, root_location_id, лічильники)                  │
│                        │   └── stock.picking.batch (dock_id [std], td_code=фура, td_truck,           │
│                        │            td_vehicle_id → maintenance.equipment)  ◄── stock.picking.batch_id│
│                        ▼                                                                               │
│  ir.actions.client td_viewer3d.action_td_viewer (якщо є)  ── інакше display_notification         │
│                                                                                                       │
│  post_init_hook: 1 docks → 2 codes(loc/wc/emp/eq) → 3 passports → 4 zones+links → 5 x_*→batch →       │
│                  6 verify → 7 drop x_* → 8 params/report          (усе в одній транзакції установки)   │
│  uninstall_hook: batch → x_* (відновлення), чистка своїх параметрів                                   │
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
          ▲ XML-RPC read (plant/odoo_pull.py, cycle_check)            ▲ UI: форми/списки/меню «Завод 3D»
```

Потоків даних із пристроїв немає; протоколи P-xx не задіяні.

### 2.3 Нові й розширені об'єкти — огляд

| Модель | Тип | Призначення | Пише | Читає |
|---|---|---|---|---|
| `td.scene.mixin` | abstract | код сцени, псевдонім, вид, резолвер, «Показати в 3D» | base (міграція), manager (форми) | усі модулі, viewer |
| `td.zone` | нова | зона цеху: контур, тип, прив'язки, лічильники | data-файл + hook; manager | viewer, access, bms, fire, yard |
| `stock.location` | розширення | `td_*` домішки + `td_zone_id` + вид/місткість місця + поля воріт | hook; manager | viewer, yard, stock |
| `stock.picking.batch` | розширення | домішка (фура), `td_truck`, `td_vehicle_id`, `td_dock_warning` | hook; stock user (стандартно) | viewer, yard |
| `stock.picking` | розширення | related-довідки `td_dock_id`, `td_dock_code`, `td_truck`, `td_truck_code` (= `batch_id.td_code`, код фури в 3D — X-15), `td_vehicle_id` (readonly) | — | viewer, `odoo_pull`, списки |
| `mrp.workcenter` | розширення | домішка + `td_zone_id` | hook; manager | viewer, machine_connect |
| `maintenance.equipment` | розширення | домішка + паспорт (CB-07) + `td_zone_id` | hook; manager/equipment manager | усі |
| `hr.employee` | розширення | домішка | hook; HR | viewer, access |
| `hr.employee.public` | розширення (SQL-представлення стандарту) | дзеркало `td_code`, `td_alias`, `td_kind` (readonly, X-09) | — (з `hr_employee`) | viewer (`people`, кіоск), access, усі внутрішні |
| `td.equipment.passport` | нова | паспорт ролі обладнання (93) | CSV data; manager | усі |
| `td.equipment.spec` | нова | параметр паспорта (назва, значення, число, одиниця, ключ) | CSV data; manager | energy, bms, viewer |
| `td.equipment.source` | нова | джерело паспорта (URL, назва, вид) | CSV data; manager | viewer |

### 2.4 Інтеграції

Немає: base не спілкується з пристроями чи зовнішніми системами. Єдина «інтеграція» —
опційний client action переглядача (CB-02): якщо модуль `td_viewer3d` не встановлений,
повертається `ir.actions.client` з тегом `display_notification` («Модуль 3D-переглядача не
встановлено»), тип `warning`, без винятку.

### 2.5 Потік даних «від макета до екрана»

1. Збирання даних модуля (одноразово, розробник): `tools/gen_data.py` читає `dist/odoo_demo.json`,
   `plant/layout.py`, `plant/equipment_specs.json`, `plant/equipment.py`, `plant/odoo_flows.py:NAMES`
   і генерує `data/*.csv`/`data/td_zone_data.xml` (SPEC §5). Файли комітяться; Odoo макет не читає.
2. Установка на базу: Odoo вантажить `security/`, `data/` (групи, параметри, зони, паспорти,
   специфікації, джерела), `views/`; далі `post_init_hook` (§2.8) заповнює коди, доки, прив'язки,
   мігрує `x_*`.
3. Користувач відкриває, напр., `maintenance.equipment` `SAW-1`: форма показує `td_code`, вкладку
   «Паспорт» (`td_passport_id` → `spec_ids`, `source_ids`, `component_passport_ids`), зону, кнопку
   «Показати в 3D» → `action_f3d_show()` → client action переглядача з `{'code':'SAW-1',
   'model':'maintenance.equipment','res_id':<id>,'kind':'equipment'}`.
4. Переглядач (інший модуль) будує картки з тих самих полів: зона — `zoneHtml` (CB-03), ворота —
   `batch_id.dock_id` (CB-05/06), паспорт — CB-07.

### 2.6 Безпека

- Групи: `group_td_user` (читання всього f3d; implied із `stock.group_stock_user` і
  `mrp.group_mrp_user`, A-07), `group_td_manager` (запис зон, воріт, кодів, паспортів; implied:
  user), `group_td_admin` (параметри, повторна міграція; implied: manager; `base.group_system`
  → implied `group_td_admin`). Операційні дії (пакети, переміщення, ТО) — стандартні групи.
- Поля `td_code`/`td_alias`/`td_kind` на стандартних моделях редагує лише `group_td_manager`
  (`groups=` на полях у формах + `_check_f3d_write_rights` у `write()`; SPEC R-04).
- Код сцени працівника — публічне поле: дзеркало в `hr.employee.public` (SPEC M-10a, X-09) читає кожен внутрішній
  користувач; без дзеркала Odoo 19 (`hr.employee._check_private_fields`) відмовив би користувачам без `hr.group_hr_user`
  у будь-якому читанні працівника. Інших полів працівника base не публікує.
- Стоп-кранів, токенів, кронів, ендпоінтів у base немає. Параметр `td.base.environment`
  читають інші модулі (CB-10). `td.base.keep_x_fields='True'` блокує видалення `x_*`.
- Коди валідуються регулярним виразом (R-01) — ін'єкцій через код у доменах/SQL немає: SQL у
  хуках лише параметризований (`cr.execute(query, params)`), коди ніколи не конкатенуються.
- Record rule для `td.zone` по `company_id` (multi-company-safe, хоча демо — одна компанія).

### 2.7 Продуктивність і обсяги

Довідкові обсяги: 45 зон, 14 воріт, ≈700 кодів локацій, 93 паспорти, 999 специфікацій, 252 джерела,
24 пакети. Індекси: `td_code` (btree на кожній моделі-носії, `index=True`), `td_alias`,
`td_zone_id` (m2o — індекс автоматично), `td.equipment.spec.key`. Лічильники зон —
`compute` без `store` (count за індексом, ≤ 50 мс на 34 зони). Жодних кронів, ротацій, рядів.
`post_init_hook` на демо-базі — ≤ 60 с (≈ 1 300 записів, усі в пам'яті, запис пачками по моделі).

### 2.8 Міграція з демо-бази й деінсталяція

Повний алгоритм із очікуваними кількостями — SPEC §5.3 і §9 R-10…R-16. Стисло:

| Крок | Джерело в демо-базі | Дія | Очікувано на копії демо |
|---|---|---|---|
| 1 Доки в типах операцій | `stock.picking.type` Receipts (id 1, `dispatch_management=True`, `dock_ids=[]`), Delivery Orders (id 2, `dock_ids=[WH/Відвантаження]`) | `in_type_id.dock_ids := 7 західних воріт`; `out_type_id.dock_ids := 7 східних` (замість батьківської, щоб «Коридори» не можна було вибрати доком) | 7 + 7 |
| 2 Коди локацій | `stock.location.barcode` під `WH`, крім `lot_stock_id` (`WHSTOCK`) | `td_code := barcode`; західні ворота `WH/Вхід/Ворота k` (barcode `UNLOAD-k`): `td_code='DOCK-Wk'`, `td_alias='UNLOAD-k'` (A-01); східні: `td_code='DOCK-Ek'`; `td_kind='dock'`, сторона/номер/категорії/координати з `data/scene_docks.csv`; вид і місткість із `data/scene_locations.csv` (R-21) | 696 кодів, 14 воріт (7 з псевдонімом), 689 видів, 654 місткості |
| 3 Коди РЦ | `mrp.workcenter.code` | `td_code := code` | 35 |
| 4 Коди працівників | `hr.employee.barcode` | за таблицею `data/scene_employee_codes.csv`; решта — правило R-06 | 35 (Administrator без бейджа — пропуск) |
| 5 Коди обладнання | `maintenance.equipment.serial_no`; для 7 навантажувачів — колонка `legacy_serial` таблиці `data/scene_equipment_codes.csv` (`FL-4369→FL-1`, `FL-4912→FL-2`, `FL-4731→FL-3`, `FL-4374→FL-4`, `FL-4193→FL-5`, `FL-4606→FL-C1`, `FL-4787→FL-C2`), резерв — xml-id `factory3d.eq_<slug>` | `td_code` за R-07 SPEC (`serial_no` → xml-id → `legacy_serial`), лише порожнім | 210, дублікатів 0, нових записів 0 |
| 6 Паспорти | data-файли (93/999/252) + `scene_equipment_codes.csv` (code → role, components) | `td_passport_id` на 207 одиницях, 63 зв'язки «у складі»; `note` не змінюється | 207; 3 без паспорта (`CHARGING`, `SPRINKLERS`, `AIR-RING`) |
| 7 Зони | `data/td_zone_data.xml` (45: 34 цехових + 11 надвірних) + `data/scene_zone_links.csv` | `root_location_id` (21 зона), `td_zone_id` на 695 локаціях, 35 РЦ, 170 одиницях обладнання (156 + 13 надвірних/A-19 + `ATS-1`→`Z-ELEC`) | 45 зон |
| 8 `x_*` → пакети | `stock.picking.x_dock` (21), `x_truck` (6), `x_vehicle` (3); 6 пакетів із `dock_id` | існуючі 6 пакетів: `td_code := x_truck`, `td_truck := x_truck`; нові пакети — по одному на переміщення з `x_dock` без фури (15) і на переміщення з `x_vehicle` (3); прив'язка переміщень — прямим SQL `UPDATE stock_picking SET batch_id` (R-12: ORM відкидає `done`-документи через `_sanity_check`, а `stock_fleet` при `batch_id`/`dock_id` переписує локації рухів `_set_moves_destination_to_dock`), далі `invalidate` + перерахунок `state`/`scheduled_date`; підтвердження пакетів із незавершеними документами | 24 пакети (6 оновлено, 18 створено), 24 переміщення в пакетах |
| 9 Звірка | для кожного переміщення з `x_*` | `x_dock == batch_id.dock_id.td_code`, `x_truck == batch_id.td_code`, `x_vehicle == batch_id.td_vehicle_id.td_code`; локації рухів не змінилися (порівняння знімка до/після) | 0 розбіжностей |
| 10 Видалення `x_*` | `ir.ui.view` `factory3d.view_picking_form_dock`, `factory3d.view_picking_list_dock`; `ir.model.fields` `x_dock/x_truck/x_vehicle` (state `manual`) | спершу 2 представлення, потім 3 поля; лише якщо крок 9 без розбіжностей і `keep_x_fields='False'`; звіт у `td.base.migration_report` (JSON), стан у `td.base.migration_state` | `done` |

Ідемпотентність: усі кроки шукають існуюче (за `td_code`, xml-id, `role`, `description` пакета);
повторний запуск `env['td.scene.mixin'].f3d_run_migration()` (admin) нічого не дублює.
Якщо `x_*` полів немає (чиста база) — кроки 8–10 пропускаються, `migration_state='skipped'`.

Деінсталяція (`uninstall_hook`): якщо `td.base.uninstall_restore_x_fields='True'` і поля
`x_dock/x_truck/x_vehicle` відсутні — створює їх (manual Char) і записує значення з пакетів
(`dock_id.td_code`, `td_code or td_truck`, `td_vehicle_id.td_code`) для всіх переміщень із
`batch_id`; пакети, зони (як дані модуля), паспорти видаляє стандартний механізм деінсталяції;
`stock.picking.batch`, `stock.location`, `maintenance.equipment` залишаються (поля `td_*` зникають
із колонками). Видаляє лише параметри `td.base.*`. Бізнес-дані (переміщення, пакети, локації,
обладнання, працівники) не чіпає.

## 3. Налаштування системи

| Об'єкт | Параметр | Значення (тестовий сервер timur-o19demo, база odoo) | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `td.base.environment` | `test` | на проді адміністратор ставить `prod` одразу після встановлення; `neutralize.sql` повертає `test`; читають стоп-крани інших модулів (CB-10) |
| `ir.module.module` | `td_viewer3d` | не встановлений на тесті до хвилі 1 | кнопка «Показати в 3D» перевіряє `state='installed'` (CB-02); параметрів для цього немає |
| `ir.config_parameter` | `td.base.plant_length_m` / `plant_width_m` / `plant_height_m` | `150` / `72` / `9` | з `plant/layout.py:W, D, H`; перевірка контурів зон і координат воріт (R-09) |
| `ir.config_parameter` | `td.base.keep_x_fields` | `False` | `True` — міграція переносить дані, але не видаляє `x_*` (для відкату) |
| `ir.config_parameter` | `td.base.uninstall_restore_x_fields` | `True` | відновлення `x_*` при деінсталяції |
| `ir.config_parameter` | `td.base.migration_state` | `done` (після установки) | `skipped` / `partial` / `done`; пише хук, вручну не міняти |
| `ir.config_parameter` | `td.base.migration_report` | JSON | кількості по кроках §2.8 |
| `res.groups` | `group_td_user` / `group_td_manager` / `group_td_admin` | admin → admin; користувачі Складу/Виробництва → user автоматично | manager призначає адміністратор вручну (технологу) |
| `stock.picking.type` | Receipts.`dock_ids` / Delivery Orders.`dock_ids` | 7 західних / 7 східних воріт | заповнює хук; `dispatch_management` уже `True` на обох |
| `stock.location` (ворота) | `td_accepts` | W1–W3: «Плитні матеріали»; W4: «Фурнітура»; W5: «Крайка»; W6: «ЛФМ»; W7: «Пакування»; E1–E7: порожньо (будь-що) | з `plant/layout.py:RCV_GOODS` і ліній документів приймання; порожньо = без обмежень |
| `stock.location` (усі) | `td_loc_kind` / `td_capacity` | з `data/scene_locations.csv` (689 / 654) | одиниці місткості — одиниця товару місця: стос — аркуші (60 під порталом, 55 у стелажі), комірка фурнітури — шт (10…66), полиця крайки — м (2 200), комірка ГП — палети (2), `PAL-*` — палети (14) |
| `td.zone` | 45 записів (34 цехових, 11 надвірних) | з `data/td_zone_data.xml` | `noupdate="1"`: правки технолога не перезаписуються оновленням модуля |
| `ir.config_parameter` | `td.base.site_x0_m` / `site_y0_m` / `site_x1_m` / `site_y1_m` | `-32` / `-30` / `182` / `100` | з `plant/infra.py:SITE`; межі перевірки контурів зон (R-09) |
| `td.equipment.passport` | 93 записи | з `data/td.equipment.passport.csv` | `noupdate="0"`: оновлення модуля оновлює паспорти з макета (A-05) |

## 4. Інструкція

**4.1 Призначити код сцени новому об'єкту** (технолог, `group_td_manager`). Відкрити форму
(місце зберігання / робочий центр / обладнання / працівник) → вкладка «Завод 3D» → `Код сцени`
у форматі `ВЕЛИКІ-ЛІТЕРИ-ЦИФРИ` (R-01) → зберегти. Код має існувати в 3D-моделі (`dist/parts/manifest.json`),
інакше «Показати в 3D» покаже порожню сцену. Дублікат у межах моделі система відхилить.

**4.2 Додати або змінити ворота** (технолог). Склад → Конфігурація → Місця зберігання → відкрити
`WH/Вхід/Ворота k` або `WH/Відвантаження/Ворота k` → вкладка «Завод 3D» → `Вид = Ворота`,
`Сторона`, `№ воріт`, `Приймає категорії`, `X/Y, м` → зберегти. Перевірити, що ворота є у
Склад → Конфігурація → Типи операцій → Receipts/Delivery Orders → «Dock locations» (хук додає
автоматично при встановленні; нові — додати вручну). У пакетному переміщенні поле «Док» пропонує
лише ці локації.

**4.3 Поставити фуру до воріт** (комірник, стандартний Odoo). Склад → Операції → Пакетні
переміщення → створити → тип операції, «Док» = ворота, «Категорія транспорту» = Фура, додати
документи приймання/відвантаження → вкладка «Завод 3D»: `Код фури в 3D` (якщо об'єкт є в сцені,
напр. `TRUCK-IN-1`), `Фура` (опис або назва фури, не держномер — його веде рейс двору `td_yard`), `Техніка` (навантажувач). Попередження
«Категорія товару не відповідає воротам» — інформаційне, не блокує.

**4.4 Виправити зону** (технолог). Завод 3D → Завод → Зони → відкрити → змінити контур
(JSON `[[x,y],…]` у метрах, ≥ 3 точок, у межах 0…150 × 0…72), тип, кореневу локацію, прив'язки
(вкладки «Місця», «Робочі центри», «Обладнання»). Площа і лічильники перераховуються самі.

**4.5 Паспорт обладнання** (механік/технолог). Обслуговування → Обладнання → картка → вкладка
«Паспорт»: паспорт ролі (спільний для всіх одиниць цієї моделі; `Одиниць під паспортом` показує,
скільки), складові «У складі», параметри, джерела. Змінювати параметри — у паспорті (Завод 3D →
Завод → Паспорти), зміна торкнеться всіх одиниць ролі. Примітка `note` зі старим текстом паспорта
лишається.

**4.6 Повторна міграція / відкат** (адміністратор). Налаштування → Технічні → Параметри системи:
`td.base.migration_state`, `migration_report`. Повторний запуск: Завод 3D → Налаштування →
«Повторити міграцію демо-даних» (`f3d_run_migration`, лише `group_td_admin`); не дублює. Щоб
зберегти `x_*` поля для відкату — заздалегідь `td.base.keep_x_fields=True`. Деінсталяція
повертає `x_*` з пакетів (4.7 у SPEC §13.5).

**4.7 Прод** (адміністратор). Після встановлення на проді: `td.base.environment=prod`.
Base сам нічого не вмикає; значення читають модулі зі стоп-кранами.

## 5. Ризики й відкриті питання

### 5.1 Відкриті питання Q-xx

| ID | Питання | Кому | Рекомендована відповідь | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | **Закрито 14.10 (рішення менеджера):** одна локація з псевдонімом (A-01). Західні ворота = існуюча локація вивантаження (`WH/Вхід/Ворота k`, barcode `UNLOAD-k`) з псевдонімом `UNLOAD-k`, чи окрема локація-док над майданчиком? | менеджер | Залишити одну локацію з псевдонімом (A-01): стандартний `stock_fleet` при призначенні дока переписує `location_dest_id` рухів приймання на док, тож окремий док забрав би товар із майданчика вивантаження | реалізуємо A-01 |
| Q-02 | **Закрито 14.10 (рішення менеджера):** один пакет на документ (R-11). Чи робити один пакет на документ для переміщень з воротами без фури (15 штук), чи групувати за (ворота, дата)? | менеджер | один пакет на документ: у макеті кожен документ — окремий візит фури; групування за годиною дало б ті самі 15 пакетів | один на документ (R-11) |
| Q-03 | **ЗАКРИТО** рішенням менеджера 13.10: вид (`kind`) і місткість (`capacity`) комірок — у base (`td_loc_kind`, `td_capacity`, FR-13); переглядач рахує заповненість з них | — | — | реалізовано FR-13, A-16 |
| Q-04 | **Закрито 14.10 (рішення менеджера):** лише URL + поле `attachment_id` для ручного завантаження. PDF-джерела паспортів вкладеннями (C-6.3 «PDF — вкладеннями»): завантажувати з інтернету при установці? | менеджер | ні: сервер без виходу в інтернет і ліцензії вендорів; лишити URL; поле `attachment_id` у `td.equipment.source` для ручного завантаження | лише URL + порожнє `attachment_id` |
| Q-05 | **Закрито 14.10 (рішення менеджера):** внутрішнє обладнання — за README (A-06), надвірне — у надвірні зони base C.2 (A-19). Прив'язка до зон обладнання енергетики/інфраструктури, якої немає в `zones`/`ventilation`/`fire`/`lighting` (ГРЩ, трансформатори, компресорна, зарядна, портал, стелажі, FACP, фонтанчики, принтери пакування) — за описом README (A-06) чи лишити порожнім? | менеджер | прив'язати за README (16 одиниць → `Z-ELEC`, `COMPRESSOR→Z-CMP`, `CHARGING/EYE-CHG→Z-CHG`, `GANTRY-1/BOARD-RACKS→Z-SHEETS`, `FACP-1→Z-OFFICE`, `EYE-PAINT→Z-FAC`, `PRN-PACK1/2, IOT-PACK→Z-PACK`); надвірне (GENSET, CHP, BESS, PV, DUST-1, BOILER, ваги, шлагбауми) — без зони до появи `outdoor`-зон у yard | A-06 у data-файлі, 26 одиниць |
| Q-06 | **ВИРІШЕНО менеджером 13.10** інакше, ніж рекомендував автор: надвірні зони належать base (єдиний власник довідника зон; yard/energy/fire лише посилаються). Додано 11 зон `outdoor` з контурами за моделлю території (A-19, SPEC додаток C) | — | — | реалізовано: `Z-GATE-W`, `Z-GATE-E`, `Z-YARD-W`, `Z-YARD-E`, `Z-KPP`, `Z-PARKING`, `Z-BOILER`, `Z-FIREWATER`, `Z-ENERGY`, `Z-WASTE`, `Z-ROOF` |
| Q-07 | **Закрито 14.10 (рішення менеджера):** `OUT-STAGE` без зони. `OUT-STAGE` (`WH/Відвантаження/Коридори`) — спільний для всіх 7 зон відвантаження. Прив'язати до жодної зони чи до всіх (m2m)? | менеджер | без зони; `td.zone.zone_at(x,y)` не потрібен для нього | без зони |
| Q-08 | **Закрито 14.10 (рішення менеджера):** `string=` одразу українською, `.po` не ведемо. Мова рядків інтерфейсу: писати `string=` одразу українською (як у `td_iot_sim`) чи англійською + `i18n/uk_UA.po`? | менеджер | українською одразу (каркас §5, практика data-модуля); `.po` не ведемо | українською (A-08) |
| Q-09 | **Закрито 14.10 (рішення менеджера):** правка `plant/odoo_pull.py` під поля CB-06 — завдання репозиторію макета; до неї — `keep_x_fields=True`. `plant/odoo_pull.py` читає `x_dock/x_truck/x_vehicle` — після міграції зламається. Хто правит: автор viewer чи окреме завдання в макеті? | менеджер | окреме завдання в репозиторії макета: читати `batch_id.dock_id.td_code`, `batch_id.td_code`, `batch_id.td_vehicle_id.td_code` (CB-06) | у SPEC §11 зафіксовано заміну полів; до правки `odoo_pull` запускати з `keep_x_fields=True` |
| Q-10 | **Закрито 14.10 (рішення менеджера):** прийнятно для фази 1; у фазі 2 фура малюється за `dock_id`/`yard.trucks` (yard Q-08). Коди фур `TRUCK-IN-1…3`, `TRUCK-OUT-1…3` — статичні об'єкти сцени на фіксованих місцях (біля воріт 1/3/4 і 2/5/7). Коли пакет переставлять на інші ворота, 3D-об'єкт лишиться на старому місці. Прийнятно для фази 1? | менеджер / автор viewer | так; viewer у фазі 2 малює фуру за `dock_id`, а `td_code` фури стає необов'язковим | `td_code` на пакеті необов'язковий |

### 5.2 Рішення автора A-xx (відхилення/уточнення каркаса)

| ID | Рішення | Обґрунтування |
|---|---|---|
| A-01 | Домішка має поле `td_alias` (другий код сцени того самого запису). Західні ворота: `td_code='DOCK-Wk'`, `td_alias='UNLOAD-k'`, `barcode` лишається `UNLOAD-k` | У 3D ворота (`DOCK-Wk`, kind dock) і майданчик вивантаження (`UNLOAD-k`, area) — два об'єкти, в Odoo — одна локація `WH/Вхід/Ворота k`, бо `stock_fleet._set_moves_destination_to_dock` робить док місцем призначення рухів приймання (перевірено в джерелах 19.0). Штрихкод не міняємо: він на етикетках і в `odoo_pull` |
| A-02 | Паспорт нормалізовано: модель `td.equipment.passport` (одна на роль, 93), `maintenance.equipment.td_passport_id` + `td_component_passport_ids`; поля C-6.3 на обладнанні — `related` (readonly) | 93 паспорти на 207 одиниць: копіювання дало б 207 × ≈11 рядків специфікацій і розбіжності при правках; `units`/«у складі» в макеті задані на код, не на роль (`EXTRA_ROLES`, `ENERGY_ROLES`), тому складові — m2m на одиниці. Контракт C-6.3 (імена полів на `maintenance.equipment`) збережено |
| A-03 | `td_units` = обчислена кількість одиниць, прив'язаних до паспорта (`passport.unit_count`), а не поле введення | у макеті `units` — список складових, а «кількість» виводиться; введення вручну розійшлося б із фактом |
| A-04 | Числові параметри паспорта (`connected_kw`, `lumen`, `watt`, `airflow_m3h`, `heat_kw`, `kva`, `kwh`, `wp`, `kw_ac`, …, 48 значень) зберігаються як `td.equipment.spec` із `key` і `value_num`, а не окремими полями | ключі різні для кожної ролі (`equipment_specs.json` має 40+ різних), модулі фаз 3–5 беруть їх через `get_num(key)` (CB-08); окремі поля — лише `power_kw`, `connected_kw` (C-6.3) |
| A-05 | Паспорти/специфікації/джерела — `noupdate="0"` (оновлюються з модуля), зони — `noupdate="1"` | паспорти — довідник вендорів, джерело істини — макет; зони править технолог |
| A-06 | 26 одиниць обладнання прив'язано до зон за описом README (§5.1 Q-05), решта надвірних — без зони | README — частина макета; не вигадуємо координат, лише належність |
| A-07 | `group_td_user` неявно входить у `stock.group_stock_user` і `mrp.group_mrp_user` | інакше комірник не побачить вкладку «Завод 3D» і ворота в меню; читання безпечне |
| A-08 | Рядки інтерфейсу — українською в коді (`string="Код сцени"`), без `.po` | як у `td_iot_sim`; каркас §5 «Інтерфейс — українська» |
| A-09 | Переміщення в пакети при міграції прив'язуються SQL-оновленням `stock_picking.batch_id`, не через ORM | `stock_picking_batch._sanity_check` відкидає `done`-документи (5 приймань), `stock_fleet.stock.picking.write` при `batch_id` переписує локації рухів; після SQL — `invalidate_recordset`, перерахунок `state`, звірка знімка локацій рухів (R-12) |
| A-10 | `dock_ids` типу Delivery Orders замінюється з `[WH/Відвантаження]` на 7 воріт | стандарт реєструє батьківську локацію, і `child_of` дозволяє вибрати доком `WH/Відвантаження/Коридори`; явний список прибирає помилку оператора |
| A-11 | `mrp_workorder` не в `depends` (каркас §3 згадує лише для machine_connect); `fleet` доданий явно | base використовує лише `mrp.workcenter`; `stock.picking.batch.vehicle_id → fleet.vehicle` потребує `fleet` |
| A-12 | Параметр `td.base.environment` і правило для стоп-кранів інших модулів (CB-10) | каркас §5 вимагає різні умовчання на тесті/проді, але не каже, звідки модуль знає середовище |
| A-13 | `neutralize.sql` містить один `UPDATE` (`environment='test'`), не порожній файл | psycopg2 відхиляє порожній запит; нейтралізована копія проду — тестова |
| A-14 | На `stock.picking` додано related-довідки `td_dock_id`, `td_dock_code`, `td_truck`, `td_truck_code`, `td_vehicle_id` (readonly, не збережені) | повертають у список/форму переміщень колонки «Ворота/Фура/Техніка», які демо давало через `x_*`; `odoo_pull` і viewer читають без join'ів |
| A-15 | Крос-модельні однакові коди дозволені (РЦ `SAW-1` і обладнання `SAW-1`): унікальність лише в межах моделі; `f3d_resolve` повертає перший за порядком `_f3d_resolve_order` | так у макеті: 35 РЦ = 35 одиниць обладнання з тим самим кодом, зв'язок — `workcenter_id` |
| A-16 | `td_loc_kind` — рівно 6 значень ключа `locations[*].kind` макета (`stack`, `bin`, `shelf`, `pallet_cell`, `kit`, `area`), не дрібніший перелік («стос під порталом» ↔ «стос у стелажі», «вивантаження» ↔ «карантин») | менеджер попросив узяти з ключа `kind`; дрібніший поділ у макеті виражений префіксом коду (`PLT-`/`RCK-`, `UNLOAD-`/`QC-`) і зоною `td_zone_id`, тож він доступний без другого довідника; нічого не вигадуємо |
| A-17 | `td_accepts` (назва з C-6.2) реалізовано як many2many до `product.category` | у макеті ворота приймають «категорії товарів» (1–3 плити, 4 фурнітура…); категорії демо вже є в базі; Selection довелося б дублювати довідник |
| A-18 | `params` client action — надмножина контракту менеджера (`code` + `alias`, `model`, `res_id`, `kind`) | переглядач читає лише `code`; решта дозволяє відкрити картку об'єкта без другого запиту |
| A-19 | Контури 11 надвірних зон виведено з моделі території так: прямокутник = габарит об'єктів моделі (`plant/infra.py`, `site.py:881–919`, `site2.py`) + 1 м з кожного боку; смуги КПП — ширина шлагбаума 8 м + 1 м з боків, від лінії огорожі (y=−30) до двору (y=0); двори фур — від огорожі (x=−32 / 182) до стіни (x=0 / 150) на всю довжину стіни (y 0…72); `Z-PARKING`, `Z-WASTE` — прямокутники `PARKING`, `WASTE` як є; дах `Z-ROOF` — контур будівлі з `is_roof`. `ATS-1` (`ATS_POS=(135.1,68.5)`) стоїть усередині електрощитової → `Z-ELEC`, хоча менеджер перелічив його серед надвірних | у `ZONES` контурів немає, а об'єкти мають точні координати; правило виведення зафіксоване, щоб не вигадувати площ; код `Z-BOILER` уже є в `plant/fire.py` |

### 5.3 Ризики

| Ризик | Вплив | Пом'якшення |
|---|---|---|
| Після видалення `x_*` ламається `plant/odoo_pull.py` і `cycle_check` на живій базі (Q-09) | переглядач-макет не перезбирається з `--live` | до правки `odoo_pull` встановлювати з `keep_x_fields=True`; SPEC §11 дає точну заміну полів |
| SQL-прив'язка переміщень оминає перевірки Odoo | розбіжність `batch.state`/`picking_type` | крок 9 звірки + тест ТК-03; `picking_type_id` пакета = тип документа; mixed-state пакетів не створюємо |
| `stock_fleet` переписує локації рухів при будь-якому `write({'dock_id'})` на пакеті | зміна дока вручну на відкритому прийманні змінює призначення рухів | це стандартна поведінка Odoo 19 (документована в §4.3); міграція пише `dock_id` лише при створенні порожнього пакета |
| Оновлення `equipment_specs.json` у макеті розходиться з `data/*.csv` | застарілі паспорти в Odoo | `tools/gen_data.py` + тест `test_data_in_sync` (порівняння CSV із JSON у репозиторії, запускається поза Odoo) |
| Технолог введе код, якого немає в 3D | «Показати в 3D» показує порожню сцену | base не знає сцени; viewer у фазі 1 показує попередження «об'єкт не знайдено в моделі» (контракт для viewer) |
| `hr.employee.barcode` змінять (новий бейдж) | код сцени лишиться — це правильно (код не залежить від бейджа) | у SPEC R-06: правило виведення застосовується лише при порожньому `td_code` |

## 6. План сборки агентами

Межі файлів жорсткі: воркер змінює лише свої файли; спільні (`__init__.py`, `__manifest__.py`,
`security/ir.model.access.csv`, `views/td_menus.xml`) належать W0 і правляться через нього.

| Воркер | Файли | Здає | Залежить від |
|---|---|---|---|
| W0 каркас | `__manifest__.py`, `__init__.py`, `models/__init__.py`, `hooks/__init__.py`, `security/td_security.xml`, `security/ir.model.access.csv`, `data/ir_config_parameter.xml`, `data/neutralize.sql`, `views/td_menus.xml`, `static/description/icon.png`, `tests/__init__.py`, `tests/common.py`, `README.md`, `CHANGELOG.md` | модуль встановлюється порожнім на чисту базу; групи, категорія, меню, параметри; `tests/common.py` з фікстурами (`F3DCase`) | SPEC §1, §3 (меню), §4, §5.1 |
| W1 домішка | `models/td_scene_mixin.py`, `models/hr_employee.py`, `models/mrp_workcenter.py` (без зон), `views/hr_employee_views.xml`, `views/mrp_workcenter_views.xml`, `tests/test_scene_mixin.py`, `tests/test_employee.py` | M-01, M-09 (частина), M-10, M-10a (дзеркало `hr.employee.public`); AC-01…AC-09, AC-39, AC-40, AC-55 | W0 |
| W2 зони | `models/td_zone.py`, `views/td_zone_views.xml`, `data/td_zone_data.xml`, `data/scene_zone_links.csv`, `hooks/zones.py`, `tests/test_zone.py` | M-02; поля `td_zone_id` на трьох моделях (у своїх файлах через `_inherit` у `td_zone.py`); AC-15…AC-19 | W1 (домішка) |
| W3 ворота й пакети | `models/stock_location.py`, `models/stock_picking_batch.py`, `models/stock_picking.py`, `views/stock_location_views.xml`, `views/stock_picking_batch_views.xml`, `views/stock_picking_views.xml`, `data/scene_docks.csv`, `hooks/docks.py`, `hooks/batches.py`, `hooks/x_fields.py`, `tests/test_dock.py`, `tests/test_batch.py`, `tests/test_migration.py` | M-03, M-04, M-11; AC-20…AC-31, AC-51, AC-52; утиліти CB-11 | W1, W2 (поле зони на локації — W2 додає `td_zone_id` через `_inherit` у своєму файлі, W3 не чіпає) |
| W4 паспорти | `models/td_equipment_passport.py` (passport, spec, source), `models/maintenance_equipment.py`, `views/td_equipment_passport_views.xml`, `views/maintenance_equipment_views.xml`, `data/td.equipment.passport.csv`, `data/td.equipment.spec.csv`, `data/td.equipment.source.csv`, `data/scene_equipment_codes.csv`, `data/scene_employee_codes.csv`, `data/scene_locations.csv`, `tools/gen_data.py`, `hooks/passports.py`, `hooks/codes.py`, `tests/test_passport.py`, `tests/test_data_sync.py` | M-05…M-08; генератор data-файлів з макета; AC-10…AC-14 (коди), AC-32…AC-38, AC-53, AC-54 (вид/місткість — поля в `stock_location.py` W3, дані й хук — W4) | W1 |
| W5 хук і тести прав | `hooks/__init__.py` (оркестратор `post_init_hook`, `uninstall_hook`, `f3d_run_migration`), `tests/test_hooks.py`, `tests/test_security.py`, `docs/modules/td_factory3d/DEPLOY_TEST.md` (чек-лист §13.5) | AC-41…AC-50; прогін ТК-01…ТК-05 на копії демо-бази | W2, W3, W4 |

Порядок злиття: W0 → W1 → (W2 ‖ W4) → W3 → W5. Кожен воркер здає зелені тести свого файлу
(`odoo-bin -d test --test-tags /td_factory3d:<TestClass> --stop-after-init`) і не змінює чужі
тести. Після W5 — повний прогін `--test-tags f3d` на чистій базі й на копії демо-бази.
