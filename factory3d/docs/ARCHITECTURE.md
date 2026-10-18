# factory3d для Odoo 19 — архітектурний каркас

Версія 0.2 · 14.10.2026 (зведення після хвилі 2, див. `docs/CONSISTENCY.md`) · менеджер проєкту документації. Цей файл — спільна основа для
документів усіх модулів (`docs/modules/<module>/ARCHITECTURE.md` і `SPEC.md`). Правила
оформлення модульних документів — у `docs/DOC_STANDARD.md`.

## 1. Принцип

Усе робиться **як для проду**: ролі, права, тести, стоп-крани, тестовий сервер, прод,
експлуатація — усі 10 етапів, які пройшов `td_genset`. Різниця одна: замість живого обладнання
до системи підключений наш **емулятор обладнання** (`td_iot_sim`), який говорить
тими самими протоколами, що й справжні пристрої (OPC UA, Modbus TCP, BACnet/IP, MQTT, REST
вендорів). Модулі для проду **не знають**, що говорять з емулятором. Перехід на живий пристрій —
зміна адреси в налаштуваннях джерела даних і звірка, а не новий код.

Джерело істини для поведінки заводу — **макет**: 3D-модель і переглядач (`viewer/index.html`),
демо-дані `dist/odoo_demo.json` (генератор `plant/odoo_demo.py`), паспорти обладнання
`plant/equipment_specs.json`, розрахунки `plant/energy.py`, `lighting.py`, `ventilation.py`,
`fire.py`, `evacuation.py`, `infra.py`, заливка/читання Odoo `plant/odoo_push.py`,
`odoo_flows.py`, `odoo_pull.py`, data-модуль `odoo_addons/td_iot_sim` (196 сигналів).
Усе, що є в макеті, має з'явитися в Odoo; чого в макеті немає — не вигадуємо, а виносимо у
відкриті питання.

## 2. Склад і фази

| # | Модуль | Фаза | Призначення (один рядок) | Місце в репозиторії |
|---|---|---|---|---|
| 1 | `td_factory3d` | 1 | Коди сцени, зони цеху, ворота, паспорти обладнання, спільні групи прав | `odoo_addons/td_factory3d` |
| 2 | `td_viewer3d` | 1 | 3D-переглядач усередині Odoo: дані з ORM, живі оновлення, «Показати в 3D», журнал станів, кіоск | `odoo_addons/td_viewer3d` |
| 3 | `td_iot_sim` | 1 | Емулятор обладнання (окремий сервіс) + пульт сценаріїв в Odoo | `services/iot_sim` + `odoo_addons/td_iot_sim` |
| 4 | `td_telemetry` | 2 | Хребет збору даних: джерела, сигнали, показання, пороги → заявки ТО, ТО за лічильником; сервіс-колектор | `odoo_addons/td_telemetry` + `services/collector` |
| 5 | `td_machine_connect` | 2 | Верстати: стани → журнал часу, автостарт/стоп завдань, простої, OEE; портал STORETEQ; карти розкрою з МО | `odoo_addons/td_machine_connect` (+ плагіни колектора) |
| 6 | `td_energy` | 3 | Ієрархія електропостачання, лічильники, кВт·год і вартість на завдання/МО, СЕС, КГУ, накопичувач, тарифи | `odoo_addons/td_energy` (+ плагін) |
| 7 | `td_genset` (перенос) | 3 | Готовий модуль генератора SmartGen HGM6120N + CMM366B-4G: перенос на 19, зв'язка з моделлю | окремий репозиторій td_genset; тут — запит на зміни |
| 8 | `td_yard` | 4 | Двір: рейси сторонніх фур, черга і бронювання воріт, шлагбауми, розпізнавання номерів, автоваги | `odoo_addons/td_yard` (+ плагіни) |
| 9 | `td_access` | 4 | СКУД Suprema BioStar 2: відмітки → Відвідування, картки, турнікети, відвідувачі, люди по зонах | `odoo_addons/td_access` |
| 10 | `td_bms` | 5 | Освітлення (норми ДБН, DALI), вентиляція й опалення, тепловий баланс, BACnet | `odoo_addons/td_bms` (+ плагіни) |
| 11 | `td_fire_safety` | 5 | Пожежна сигналізація (тільки читання), іскрогасіння, димовидалення, евакуація за нормами, журнал навчальних тривог | `odoo_addons/td_fire_safety` (+ плагін) |

Фаза 1 потрібна всім: `td_factory3d` дає коди й зони, емулятор дає обладнання. Фази 3–5
незалежні одна від одної й можуть іти паралельно.

## 3. Граф залежностей (manifest `depends`)

```
td_factory3d          ← stock, mrp, maintenance, mrp_maintenance, hr, stock_picking_batch, stock_fleet, fleet, web
td_viewer3d        ← td_factory3d, bus, web          (решта модулів — optional, §6.7)
td_iot_sim       ← td_factory3d                    (пульт сценаріїв; сам емулятор — поза Odoo)
td_telemetry     ← td_factory3d, maintenance, mail, web
td_machine_connect ← td_telemetry, mrp_workorder
td_energy        ← td_telemetry, mrp_account, mrp_workorder, analytic, web_hierarchy
td_genset_factory3d (міст) ← td_genset, td_factory3d, td_telemetry, td_energy   (без viewer — X-20)
td_yard          ← td_factory3d, td_telemetry, stock_picking_batch, stock_fleet, delivery,
                          stock_delivery, web_gantt, mail, bus
td_access        ← td_factory3d, hr_attendance, mail
td_bms           ← td_telemetry, web
td_fire_safety   ← td_telemetry, hr_attendance

Містки auto_install (необов'язкові зв'язки без жорсткої залежності):
td_viewer3d_sale            ← td_viewer3d, sale
td_telemetry_viewer3d       ← td_telemetry, td_viewer3d
td_fire_safety_viewer3d     ← td_fire_safety, td_viewer3d
td_access_telemetry       ← td_access, td_telemetry        (7 сигналів СКУД — X-33)
```

Необов'язкові зв'язки між модулями — або провайдер/джерело за префіксом імені моделі без `_inherit`
(`td.viewer.provider.*`, `td.fire.passage.source.*`), або `env.get(...)`, або місток auto_install (D-18).

Циклів немає. Усе, що пишеться на стандартні моделі (`stock.location`, `mrp.workcenter`,
`maintenance.equipment`, `hr.employee`, `stock.picking.batch`), робить **тільки** `td_factory3d`
або модуль-власник функції; два модулі не додають поле з однаковим значенням.

Факти з демо-бази (Odoo 19.0+e, перевірено 13.10.2026): установлені `stock`, `stock_picking_batch`
(диспетчеризація: `stock.picking.batch.dock_id → stock.location`, `vehicle_category_id`,
`driver_id`), `stock_fleet`, `fleet`, `delivery`, `mrp`, `mrp_workorder`, `mrp_account`
(`mrp.production.extra_cost`), `mrp_maintenance` (`maintenance.equipment.workcenter_id`),
`maintenance`, `quality_control`, `hr`, `hr_attendance`, `iot`, `stock_barcode`,
`spreadsheet_dashboard`, `web_gantt`, `web_map`. Моделі `stock.dock` **немає** — ворота в Odoo 19 =
`stock.location` з ознакою доку. На `stock.picking` у демо є тимчасові поля `x_dock`, `x_truck`,
`x_vehicle` (Char), на `maintenance.equipment` — `x_f3d_signal_ids` (data-модуль). Усі `x_*`
підлягають міграції в прод-модулі (§6.1, §6.4).

## 4. Топологія розгортання

```
┌──────────────────────────── docker compose (поруч з Odoo, як /opt/timur-o19) ───────────────────────────┐
│  odoo19 (Enterprise) + td_*        postgres                                                       │
│        ▲ JSON-RPC push /f3d/telemetry/*   ▲                                                              │
│        │ (токен)                          │                                                              │
│  collector  ── плагіни протоколів ──► [ емулятор iot_sim ]  або  [ живі пристрої в мережі цеху ]         │
│   (services/collector)                     (services/iot_sim: OPC UA, Modbus TCP, BACnet/IP, MQTT,       │
│                                             HelvarNet, SICS, REST BioStar 2 / woodStore / Axis / tapio) │
│  Odoo ◄── REST керування /sim/* ──► емулятор (пульт сценаріїв td_iot_sim)                         │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

- **Колектор** (`services/collector`) — довгоживучий Python-сервіс: тримає з'єднання з пристроями
  (підписки OPC UA, MQTT, опитування Modbus/BACnet), буферизує, відправляє показання в Odoo пакетами.
  Конфігурацію (які джерела, які сигнали, адреси) бере з Odoo (`GET /f3d/telemetry/config`).
  Один процес, плагін на протокол; плагіни належать модулям (таблиця §6.6).
- **Емулятор** (`services/iot_sim`) — один Python-сервіс, що підіймає сервери всіх протоколів
  із протокольної матриці (§6.6), має рушій сценаріїв і REST-керування. У тестовому й прод-контурі
  стоїть замість пристроїв; при переході на живий пристрій колектор перенацілюють на нього.
- **Odoo** зберігає конфігурацію, агрегати, документи, заявки; ніколи не ходить у мережу цеху сам
  (крім REST до емулятора з пульта сценаріїв і REST BioStar 2 з `td_access`).
- Сирі часові ряди великого обсягу (енергія, телеметрія) — у Odoo лише агрегати; сирі — у
  колекторі/окремому сховищі (TimescaleDB, фаза 3 за потреби). Деталі — у SPEC `td_telemetry`.

## 5. Конвенції (обов'язкові для всіх SPEC)

- **Імена.** Нові моделі `td.<name>` (`td.zone`, `td.signal`, `td.reading`); поля, додані до
  стандартних моделей, з префіксом `td_` (`td_code`, `td_zone_id`); XML-id
  `<module>.<model>_<what>` (`td_factory3d.view_td_zone_form`); групи
  `td_factory3d.group_td_user` / `group_td_manager` / `group_td_admin`; параметри
  `ir.config_parameter` з ключем `td.<module>.<param>`.
- **Жодних `x_`-полів** у прод-модулях. Демо-поля `x_*` мігрують у `post_init_hook` модуля-власника.
- **Мова.** Інтерфейс і документація — українська (`uk_UA`), технічні імена — англійська.
  Python 3.12, Odoo 19 ORM; маніфест: `version` `19.0.1.0.0`, `author` `ToDo`, `license` `LGPL-3`,
  `category` як у стандартних застосунків, `installable: True`.
- **Код сцени** (`td_code`) — єдиний ключ між Odoo і 3D (§6.1). Унікальний у межах моделі.
- **Сигнали** іменуються шляхом у даних переглядача: `energy/consumers/SAW-1/p_now`,
  `equipment/FL-1/battery`, `ventilation/units/RV-05/filter_dp_pa`, `infra/totals/pv_now`
  (так само, як `x_code` у data-модулі `td_iot_sim` — сумісність із переглядачем).
- **Стоп-крани.** У кожному модулі з обладнанням: `td.<module>.read_enabled` (за
  замовчуванням `True` на тесті, `False` одразу після встановлення на проді) і
  `td.<module>.write_enabled` (команди на пристрої; за замовчуванням `False`), плюс
  `neutralize.sql` (вимикає крони, джерела, токени) — як у `td_genset`.
- **Права.** Читання — `group_td_user`; налаштування джерел, порогів, зон — `group_td_manager`;
  токени, стоп-крани, емулятор — `group_td_admin` (входить у `base.group_system`). Операційні
  дії лишаються в стандартних групах (`mrp.group_mrp_user`, `stock.group_stock_user`,
  `maintenance.group_equipment_manager`, `hr_attendance.group_hr_attendance_officer`).
- **Тести.** `odoo.tests.TransactionCase`/`HttpCase` з тегами `post_install`, `-at_install`,
  `f3d`; стендові сценарії (ТК-xx) — проти емулятора. Мінімум: кожен AC покритий або юніт-тестом,
  або ТК.
- **Безпека.** Усі ендпоінти колектора/емулятора — з токеном (`Authorization: Bearer`), токени
  в `ir.config_parameter` лише для `group_td_admin`, у логах не друкуються; пристрої — тільки
  читання, якщо SPEC явно не дозволяє запис (стоп-кран `write_enabled`).
- **Міграція й деінсталяція.** `post_init_hook` переносить демо-дані без втрат; `uninstall_hook`
  не видаляє бізнес-дані (лише свої крони/параметри).

## 6. Наскрізні контракти

### 6.1 Код сцени — `td.scene.mixin` (`td_factory3d`)

Абстрактна модель-домішка: `td_code` (Char, index, unique per model через SQL-constraint),
`td_kind` (Selection: `location`, `workcenter`, `equipment`, `employee`, `dock`, `zone`,
`vehicle`, `other`), метод `action_f3d_show()` (повертає client action переглядача з
`{code}`), `search_f3d(code)`. Домішку отримують `stock.location`, `mrp.workcenter`,
`maintenance.equipment`, `hr.employee`, `td.zone`, `stock.picking.batch` (для фур).

Звідки береться код у демо (джерело міграції): `stock.location.barcode` (`PLT-04C`,
`RCK-R2-1C`, `FUR-R1-S02-L3`, `FG-R1-B01-L1`), `mrp.workcenter.code` (`SAW-1`, `CNC-2`),
`maintenance.equipment.serial_no` (`FL-1`, `COMPRESSOR`, `GENSET`, `RV-05`), `hr.employee.barcode`
(код без дефісів: `OPSAW1` → `OP-SAW-1`; таблиця відповідності — у SPEC base), ворота — `DOCK-W1…W7`,
`DOCK-E1…E7`, зони — `Z-RCV-1…`, `Z-SHEETS`, `Z-HW`, `Z-EDGE`, `Z-PKS`, `Z-CUT`… (повний перелік —
ключі `zones`, `docks`, `locations`, `workcenters`, `equipment`, `employees` в `dist/odoo_demo.json`).

### 6.2 Зони й ворота

- `td.zone` (`td_factory3d`): код, назва, тип (`receiving`, `storage`, `production`,
  `assembly`, `packing`, `shipping`, `technical`, `office`, `outdoor`), контур на плані
  (полігон у метрах, JSON), прив'язки: комірки (`stock.location.td_zone_id`), робочі центри,
  обладнання, ворота. Джерело: `zones` в `odoo_demo.json` і `plant/layout.py`.
- **Ворота = `stock.location`** з ознакою доку (стандартна диспетчеризація Odoo 19), плюс
  `td_code`, `td_side` (`west`/`east`), `td_dock_no` (1…7), `td_accepts` (категорії
  товарів: 1–3 плити, 4 фурнітура, 5 крайка, 6 ЛФМ і плівка, 7 пакматеріали), `td_zone_id`.
  Поля `x_dock`, `x_truck`, `x_vehicle` на `stock.picking` **замінюються** стандартним
  `batch_id` (пакетне переміщення з `dock_id`, `vehicle_category_id`, `driver_id`) і полями
  `td_factory3d`: `stock.picking.batch.td_truck` (Char, держномер або назва фури з макета),
  `td_vehicle_id` (техніка = `maintenance.equipment` навантажувача/тягача). Рейси сторонніх
  фур (водії, перевізники, бронювання) — це вже `td_yard`, який посилається на `batch_id`.

### 6.3 Паспорт обладнання

`maintenance.equipment` + поля `td_factory3d`: `td_role` (роль із `equipment_specs.json`:
`beam_saw`, `compressor`, `facp`…), `td_manufacturer`, `td_model`, `td_reason` (чому обрано),
`td_power_kw`, `td_connected_kw`, `td_dimensions` (Д×Ш×В мм), `td_spec_ids` (one2many
`td.equipment.spec`: параметр, значення, одиниця, джерело), `td_source_ids` (посилання на
джерела: URL + назва; PDF — вкладеннями), `td_units` (скільки одиниць під одним паспортом).
Зв'язок верстат ↔ обладнання — стандартний `workcenter_id` (`mrp_maintenance`). Імпорт 93
паспортів із `plant/equipment_specs.json` — крок `post_init_hook`/data-файл `td_factory3d`.
Поле `note`, куди зараз зливається паспорт текстом, після міграції лишається як є (не чистимо).

### 6.4 Телеметрія (`td_telemetry`) — спільний хребет

- `td.source` — джерело даних: тип (`opcua`, `modbus_tcp`, `bacnet_ip`, `mqtt`, `http_push`,
  `helvarnet`, `sics`, `rest_vendor`), адреса/порт/параметри (JSON), `collector_id`, стан
  (`online`/`offline`/`error`, останній контакт), `read_enabled`.
- `td.signal` — визначення сигналу: `code` (шлях, §5), `equipment_id`, `source_id`, адреса в
  джерелі (`address`: NodeId / регістр+тип / об'єкт BACnet / топік), `unit`, `kind`
  (`gauge`, `counter`, `state`, `event`), `period_s`, `scale`, пороги (`warn_low`, `warn_high`,
  `alarm_low`, `alarm_high`, `alarm_state`), `last_value`, `last_ts`, `status`
  (`ok`/`warn`/`alarm`/`stale`), `maintenance_request_id` (відкрита заявка).
- `td.reading` — показання (ts, signal, value, quality), ротація за `td.telemetry.keep_days`;
  агрегати `td.reading.hour` (min/avg/max/sum/count).
- Ендпоінти (JSON, токен колектора): `GET /f3d/telemetry/config` (джерела+сигнали для цього
  колектора, ETag), `POST /f3d/telemetry/push` (пакет `[{code, ts, value, q}]`, ідемпотентно),
  `POST /f3d/telemetry/status` (стан джерел), `GET /f3d/telemetry/health`.
- Пороги → `maintenance.request` (одна відкрита заявка на сигнал; закриття заявки скидає
  `status`), ТО за лічильником (`maintenance.equipment.td_meter_signal_id`, інтервал у
  мотогодинах/циклах → планова заявка).
- Інші модулі **не** створюють власних моделей показань: вони додають типи джерел, плагіни
  колектора, правила й представлення поверх `td.signal`/`td.reading`.

### 6.5 Колектор — протокол із Odoo і плагіни

Плагін = Python-пакет `collector/plugins/<protocol>.py` з інтерфейсом `connect(source)`,
`subscribe(signals)`/`poll()`, `write(signal, value)` (лише якщо `write_enabled`), `health()`.
Відповідальність:

| Плагін | Протокол | Належить модулю |
|---|---|---|
| `modbus_tcp` | Modbus TCP (pymodbus) | `td_telemetry` |
| `mqtt` | MQTT 3.1.1/5 (paho) | `td_telemetry` |
| `http_push` | приймач HTTP POST від пристроїв (Axis, tapio webhooks) | `td_telemetry` |
| `bacnet_ip` | BACnet/IP (bacpypes3); `read_only` для пожежної панелі | `td_telemetry` (рішення 14.10, D-16) |
| `opcua` | OPC UA клієнт (asyncua), companion spec Woodworking | `td_machine_connect` |
| `rest_vendor` | REST вендорів: адаптери `woodstore` (портал STORETEQ), `cutopt` (карти розкрою), `generic` | `td_machine_connect` |
| `helvarnet` | HelvarNet TCP (освітлення DALI) | `td_bms` |
| `sics` | METTLER TOLEDO SICS (TCP) для автоваг | `td_yard` |
| `biostar2` | REST Suprema BioStar 2 (опитування з Odoo, без колектора) | `td_access` |
| `relay_genset` | API ретранслятора SmartGen (існуючий, у `td_genset`) | `td_genset` |

### 6.6 Протокольна матриця емулятора (рішення менеджера)

Емулятор реалізує **серверну** сторону кожного рядка; модуль-споживач — клієнтську (через
плагін колектора). Карти регістрів/вузлів/об'єктів пише автор SPEC `td_iot_sim` як «документація
вендора» (додатки P-xx), а модулі-споживачі на них посилаються. Де є опублікований стандарт —
підмножина стандарту; де немає — наше припущення, позначене «ПРИПУЩЕННЯ, звірити з вендором».

| ID | Клас пристроїв (коди з макета) | Реальна модель | Протокол емулятора | Еталон | Споживач |
|---|---|---|---|---|---|
| P-01 | Верстати HOMAG: SAW-1..3, NEST-1, EDGE-1..3, CNC-1..4, BORE-1, DOWEL-1, SORT-1, ASMLINE-1 | SAWTEQ, CENTATEQ, EDGETEQ, DRILLTEQ, SORTBOT, CABTEQ | OPC UA (сервер на верстат або один сервер, простір імен на верстат) | OPC 40550-1 «OPC UA for Woodworking» (umati): MachineryItem, State (Machine/Location/Flags/Overview), Events, JobList/Production | `td_machine_connect` |
| P-02 | Верстати без інтерфейсу: SLIDE-1, VSAW-1, SAND-1, PRESS-1, GLUE-1, SPRAY-1, AUTOSPRAY-1, DRY-1, UV-1, HINGE-1, BOX-1, WRAP, SHRINK, STRAP, CLAMP-1..6 | Altendorf, Striebig, SCM, Orma, Ardesia, Cefla, Blum, Panotec, Robopac, Smipack, Mosca | Modbus TCP, модуль вводу/виводу (ретрофіт): дискретні входи «в роботі», «аварія», лічильник циклів | карта регістрів як у Advantech ADAM-6050/6060 (ПРИПУЩЕННЯ: конкретна модель I/O) | `td_machine_connect` |
| P-03 | Портал GANTRY-1 і склад плит | HOMAG STORETEQ P-500 + woodStore | REST JSON «woodStore API v1» (стоси ↔ залишки, завдання порталу, стан порталу) + OPC UA стан | ПРИПУЩЕННЯ (інтерфейс woodStore закритий; звірити з HOMAG) | `td_machine_connect` |
| P-04 | Карти розкрою й програми | HOMAG intelliDivide / woodWOP | файловий обмін: CSV списку деталей на оптимізацію, MPR для ЧПК; емулятор приймає файли через REST `/jobs` і відповідає планом | формат імпорту intelliDivide (звірити), MPR — відкритий формат | `td_machine_connect` |
| P-05 | Лічильники: вводи T1/T2, комірки ГРЩ QF-*, шинопроводи BW-1..4, споживачі (35 верстатів, компресор, аспірація…) | Schneider PowerLogic PM5560; MasterPact MTZ2 (Micrologic X, IFE) | Modbus TCP, unit id на лічильник | опублікована карта регістрів PM5560 (Schneider «PM5500 Modbus register list») | `td_energy` |
| P-06 | Рухоме обладнання FL-1..7, TUG-1 | Linde X50, Jungheinrich EFG 216 / EZS 350 | MQTT JSON: `f3d/mobile/<code>/telemetry` (battery_pct, hours, state, lat/x,y) | ПРИПУЩЕННЯ: телематичний шлюз із MQTT (Linde connect / Jungheinrich FleetControl не мають відкритого API) | `td_telemetry` |
| P-07 | Інженерія: COMPRESSOR (Atlas Copco GA 37 VSD+ Elektronikon Mk5), DUST-1 (NESTRO NKJ), BOILER (Kalvis K-500M), CHP (TEDOM), BESS (Huawei LUNA2000), PV-INV (Huawei SUN2000), ATS-1 (Socomec ATyS p), трансформатори T1/T2 (датчики температури), лічильник води | — | Modbus TCP, карти вендорів; СЕС і накопичувач — SunSpec/Huawei Modbus | карти Elektronikon Mk5, Huawei SUN2000 Modbus TCP, TEDOM, ATyS p Modbus — підмножина опублікованого | `td_telemetry`, `td_energy` |
| P-08 | Вентиляція й опалення RV-01..25, AHU-1, котельня; освітлення LP-1..3 (групи LT-*) | Hoval RoofVent RH-9C, VTS VENTUS, Helvar Imagine 950 DALI-2 | BACnet/IP (вентустановки, опалення); HelvarNet TCP (освітлення DALI: групи, сцени, рівень, стан) | BACnet об'єкти AI/AO/BI/BO/MSV; HelvarNet 2.x (опубліковано Helvar) | `td_bms` |
| P-09 | Пожежна сигналізація FACP, шлейфи 1–4, групи FA-*, іскрогасіння GreCon BS 7, димовидалення D+H CPS-M1 | Siemens Cerberus PRO FC726-ZA | BACnet/IP **тільки читання** (стан зон/сповіщувачів, події: тривога, несправність, запиленість, вимкнення); GreCon і D+H — дискретні входи через I/O (як P-02) | BACnet-інтерфейс Cerberus PRO (звірити назву модуля в Siemens); ПРИПУЩЕННЯ для GreCon/D+H | `td_fire_safety` |
| P-10 | СКУД: зчитувачі ACC-*, турнікети TURN-*, користувачі | Suprema BioEntry W3 + BioStar 2; Gunnebo SlimStile EV | REST BioStar 2 API (підмножина: `/api/login`, `/api/users`, `/api/devices`, `/api/events/search`, `/api/doors`) | опублікований BioStar 2 API | `td_access` |
| P-11 | Двір: шлагбауми GATE-W/GATE-E (CAME GARD LS6), камери LPR (Axis P1488-LE + License Plate Verifier), автоваги TRUCK-SCALE (АКСІС 60-18-К-Е), КПП | — | шлагбауми — Modbus TCP I/O (коїли «відкрити», входи «відкрито/перешкода»); LPR — HTTP POST JSON від Axis LPV на колектор; ваги — ASCII по TCP (SICS-сумісний діалект) | Axis LPV event format (опубліковано); SICS (METTLER TOLEDO); АКСІС — ПРИПУЩЕННЯ | `td_yard` |
| P-12 | Генератор GENSET | KOHLER-SDMO D700 + SmartGen HGM6120N + CMM366B-4G | API ретранслятора SmartGen — існуючий `fake_relay.py` з профілем D700 | `relay_api.md` у `td_genset` | `td_genset` |
| P-13 | Ваги PFA584, принтери ZT411, сканери TC22, планшети | Odoo IoT Box | стандартний Odoo IoT — **поза емулятором** | — | — |

Керування емулятором: REST `/sim/v1/*` (токен): `GET /status`, `GET /devices`,
`POST /scenario/<name>/start|stop` (сценарії: `shift`, `machine_fault <code>`, `blackout`,
`filter_clogged <code>`, `truck_no_booking`, `fire_drill <zone>`, `access_event`),
`POST /device/<code>/fault|clear`, `POST /time {factor}` (прискорення), `GET /signals`.
Режими: `scenario` (емулятор сам веде завод за змінами й завданнями, які отримав по P-03/P-04)
і `follow_odoo` (тільки читає стан завдань з Odoo по XML-RPC і веде верстати за ним — для демо
без `td_machine_connect`). Пульт в Odoo (`td_iot_sim`) — лише обгортка над `/sim/v1`.

### 6.7 Переглядач — контракт даних

- Формат даних переглядача = `dist/odoo_demo.json` (ключі `meta`, `products`, `locations`,
  `workcenters`, `productions`, `workorders`, `sale_orders`, `purchase_orders`, `pickings`,
  `quality_checks`, `maintenance_requests`, `equipment`, `employees`, `docks`, `zones`, `energy`,
  `lighting`, `ventilation`, `fire`, `infra`, `evacuation`, `sheet_chain`, `ship_chain`,
  `material_paths`, `full_cycle_mo`, `passports`). Еталон побудови з живої бази —
  `plant/odoo_pull.py` (`LiveDemo`); статична частина (розкладка, маршрути, норми) — з моделі.
- Хук постачальника даних: модель з префіксом імені `td.viewer.provider.<key>` (`AbstractModel`
  без `_inherit` моделей viewer) або містком auto_install з `_inherit` (D-18). Контракт — за
  атрибутами (duck typing, viewer M-01): `_f3d_sequence`, `_f3d_sections`, `_f3d_group`,
  `_f3d_viewer_collect(self, payload: dict, ctx: dict) -> None`, `_f3d_viewer_delta(self, patch, ctx)`;
  viewer читає їх через `getattr` з умовчаннями. Порядок: вбудовані 20…70, machine_connect 75, вбудований `signals` 90,
  telemetry 95, energy 100, lighting 110, ventilation 120, fire 130, evacuation 140, infra 150,
  genset 155, yard 160, access 170. Без модуля — розділ лишається з моделі (статика) або порожній.
- Спільні розділи (`infra`, `workcenters`, `employees`, `zones`) провайдери лише **доповнюють**
  через спільний `deep_merge`; клієнт зливає дельту глибоко (viewer R-14, X-23).
- Схема даних `meta.schema = "1.1"`: 26 базових ключів у фіксованому порядку + додаткові ключі
  модулів (перелік — viewer Додаток A); нові ключі верхнього рівня (`yard`, `access`) — після
  базових за `_f3d_sequence` (X-24). `zones` = усі активні `td.zone` base (45, з надвірними).
- Живі оновлення: канал шини `f3d_viewer` (`bus.bus`), повідомлення `{model, codes, kind}`;
  переглядач дозапитує лише змінені об'єкти (`/f3d/viewer/delta`).
- «Показати в 3D» — `action_f3d_show()` домішки (§6.1); кнопка на формах `stock.location`,
  `mrp.workcenter`, `maintenance.equipment`, `hr.employee`, `mrp.production`, `stock.picking`,
  `td.zone`, `sale.order` (за MO/відвантаженнями).
- Журнал станів (`td.viewer.snapshot`) для програвання зміни: знімок `payload` раз на N хв + події.
- Сигнали емуляції/телеметрії потрапляють у `payload` за шляхом = `td.signal.code` (§5).

### 6.8 Заявки ТО з обладнання

Єдине правило для всіх модулів: поріг/подія → `maintenance.request` із полями
`td_signal_id`, `td_equipment_code`, `maintenance_type='corrective'`, команда — з обладнання;
дедуплікація: поки відкрита заявка на сигнал, нова не створюється; закриття заявки → `status=ok`
і запис у журнал. Тексти заявок — українською, з показником і порогом («Заміна фільтрів:
перепад тиску 285 Па при нормі до 250»).

## 7. Порядок робіт і хвилі документації

- **Хвиля 1 (паралельно):** `td_factory3d`, `td_iot_sim`, `td_viewer3d`.
  Емулятор публікує «документацію вендора» (додатки P-01…P-12).
- **Хвиля 2 (паралельно, після хвилі 1):** `td_telemetry`, `td_machine_connect`,
  `td_energy`, `td_genset`, `td_yard`, `td_access`, `td_bms`,
  `td_fire_safety`. Посилаються на SPEC хвилі 1; суперечності вирішує менеджер
  (журнал рішень §8).

## 8. Журнал рішень менеджера

| ID | Рішення | Чому |
|---|---|---|
| D-01 | Емулятор — окремий сервіс поза Odoo, говорить реальними протоколами | інакше прод-модулі довелося б переписувати при переході на залізо; data-модуль у демо-базі стає макетом |
| D-02 | Один сервіс-колектор із плагінами замість драйверів усередині Odoo | довгі з'єднання (OPC UA, MQTT) не живуть у воркерах Odoo; як ретранслятор у `td_genset` |
| D-03 | Ворота = `stock.location`-док Odoo 19, не власна модель | `stock_picking_batch` уже дає `dock_id`, диспетчеризацію й Gantt |
| D-04 | `td_telemetry` — єдині моделі сигналів/показань для всіх | без цього 5 модулів зробили б 5 журналів показань |
| D-05 | Верстати HOMAG — OPC UA за OPC 40550-1 (umati); tapio — не в v1 | відкритий стандарт галузі, HOMAG його підтримує; tapio — хмара, платний доступ |
| D-06 | СЕС/накопичувач — Modbus TCP (Huawei/SunSpec), лічильники — PM5560 | опубліковані карти регістрів |
| D-07 | Пожежна панель — BACnet/IP тільки читання; жодних записів у прилад | вимога безпеки; узгодити з монтажником |
| D-08 | Освітлення — HelvarNet (Imagine 950), вентиляція — BACnet/IP | опубліковані протоколи вендорів із макета |
| D-09 | Мобільна техніка — MQTT-шлюз (припущення) | у Linde/Jungheinrich немає відкритого API; шлюз — типове рішення |
| D-10 | Документація модулів — українською, два файли на модуль (`ARCHITECTURE.md`, `SPEC.md`) | стандарт ToDo; SPEC має вистачати Sonnet для коду, Opus для тестів |
| D-11 | Сирі ряди — поза Odoo за потреби (TimescaleDB), в Odoo — агрегати й останні значення | обсяг даних (35 верстатів × 1 с) не для PostgreSQL Odoo |
| D-12 | `td_genset` переносять як є; у цьому проєкті — лише запит на зміни і зв'язка з моделлю | модуль пройшов 10 етапів і стоїть на проді |
| D-13 | `td_iot_sim` у демо-базі (data-модуль) лишається «рівнем 0»; новий модуль-пульт 19.0.2.0.0 + сервіс; крон рівня 0 взаємовиключний із сервісом | плавний перехід без втрати демо |
| D-14 | Рядки UI українською прямо в коді, без `.po` у v1 (усі модулі) | один мовний ринок замовника |
| D-15 | `plant/odoo_pull.py` і `cycle_check` макета правлять окремим завданням; до того `keep_x_fields=True` | не ламати живий переглядач під час міграції |
| D-16 | Плагін `bacnet_ip` — у telemetry (ним користуються bms і fire_safety) | спільне ядро протоколу |
| D-17 | Локальні джерела без колектора — хук `td.source._f3d_local_types()` (telemetry CT-12); модулі додають свої типи (`td_genset`, `f3d_energy`, `td_machine`, `f3d_bms`) | дані, що вже є в Odoo, не ходять через колектор |
| D-18 | Необов'язкові зв'язки між модулями — за префіксом імені моделі без `_inherit`, `env.get` або місток auto_install; жорсткі `depends` лише за §3 | модулі ставляться в будь-якому порядку фаз |
| D-19 | Вхід показань у модулі — перевизначення `td.signal._f3d_ingest` з `super()` першим; API колектора викликає саме його | telemetry пише `last_value` SQL-ом, `write()` не бачить показань |
| D-20 | Адреси Modbus — PDU за документом вендора, без загального «номер − 1»; ADAM — молодше слово першим | інакше емулятор і споживачі розійдуться на регістр |
| D-21 | ATyS p — за Socomec Annexe III (положення 20483, коди 1/2/3) | опублікована карта вендора |
| D-22 | Odoo лише ставить завдання в чергу верстата; пуск — тільки з пульта верстата | безпека людей біля верстатів |
| D-23 | AMF: робочий варіант A (HGM6120N веде, ATyS p у Remote control) до відповіді замовника | рекомендація td_genset |
| D-24 | Розподіл спільних споживачів на МО — драйвер на пул (повітря/аспірація/портал — за прямими кВт·год, світло/вентиляція — за часом, решта — накладні) | змінюється даними без коду |
| D-25 | Реєстр розбіжностей між модулями — `docs/CONSISTENCY.md` (X-01…X-66, з bms-проходом), усі рішення затверджені 14.10 | джерело правок модулів одним проходом |

## 9. Відкриті питання до замовника (зведені)

Повний зведений перелік (19 питань, без дублів, з модулями й тим, що робимо до відповіді) —
`docs/CONSISTENCY.md`, розділ «Питання до замовника». **14.10.2026 на всі 19 питань отримано відповіді** (розділ «Відповіді на питання до
замовника»; у модулях Q-xx закрито з посиланням на номер відповіді) — нижче лишається як історія. Найважливіші:

1. Генератор: хто веде AMF — HGM6120N чи ATyS p; репозиторій `td_genset` 18.0 і `relay_api.md`.
2. HOMAG: OPC UA (OPC 40550-1, JobManagement) на верстатах, woodStore API, формат intelliDivide.
3. Cerberus PRO FC726: ключ BACnet, склад об'єктів (PICS), запиленість, дозвіл монтажника.
4. Будівля: чи є BMS; Hoval — BACnet чи Modbus-шлюз.
5. Енергія: тариф і зони, договірна потужність, метод оцінки ГП (рекомендація AVCO).
6. Двір: протокол індикатора автоваг АКСІС, маси аркушів, хто бронює ворота.
7. СКУД: формат блокування картки в BioStar 2.
