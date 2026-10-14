# factory3d_access — технічне рішення

Версія 0.2 · 14.10.2026 (0.1 — 14.10.2026) · автор: агент-архітектор модуля (хвиля 2, фаза 4) · статус: **чернетка на погодження**.
Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-23 і X-87 (CA-05, §2.5: дельта переглядача доповнює `patch` через
`deep_merge` — картки `infra`, `employees[code]`, `zones[code].people_now`; A-07, Q-10), X-33 (міст
`factory3d_access_telemetry` створює 7 сигналів `access/*`: §2.1, FR-15, §2.3, §2.4, §6, Q-11), X-09 (A-21: `f3d_code`
працівника — у `hr.employee.public` з base M-10a), X-89 (правило X-32: пункт «Налаштування СКУД» під
`factory3d_base.menu_f3d_config`, sequence 70 — FR-12, §1.2, §3, A-16).
Каркас: `docs/ARCHITECTURE.md` (далі «каркас»: §3 залежності `factory3d_access ← factory3d_base, hr_attendance`,
§4 топологія — Odoo сам ходить REST до BioStar 2, §5 конвенції, §6.1 код сцени працівника, §6.2 зони,
§6.5 плагін `biostar2` «опитування REST прямо з Odoo, без колектора», §6.6 **P-10**, §6.7 провайдер переглядача,
§8 D-01, D-10). Специфікація: `docs/modules/factory3d_access/SPEC.md`. Спирається на контракти `factory3d_base`
CB-01 (домішка, `hr.employee.f3d_code`/`barcode`), CB-03 (`f3d.zone`, `zone_at`), CB-09 (меню, sequence 70),
CB-10 (групи, `environment`), CB-12 (територія) (SPEC base §2, §3, §4, Додатки B, C.2, F); `factory3d_viewer`
M-01 (хук провайдера, `_f3d_sequence=170`), M-03 (шина `_notify`), Додаток A.11 (`employees[]`, `zones[]`),
R-14 (дельти); «документацію вендора» `factory3d_iot_sim` SPEC §8.12 (P-10: API-40…API-46, коди подій, R-28),
§9.3 S-09 `access_event`, Додаток A рядки 647–653 (7 сигналів `access/*`), ARCH iot_sim Q-13;
`factory3d_telemetry` ARCH CT-09, CT-10 (опційна публікація сигналів; сигнали створює міст `factory3d_access_telemetry`, X-33). Рішення автора — **A-xx** (§7),
відкриті питання — **Q-xx** (§5.1). Усі імена остаточні; рядки інтерфейсу — українською в коді (D-14 менеджера).
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-01, Q-02, Q-04, Q-05, Q-14.
Зміни: 14.10.2026 — закрито рішеннями менеджера: Q-03, Q-09, Q-12, Q-13.

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора; `docs/оцінки` в репозиторії ще немає) |
|---|---|---|
| ТР | цей документ + SPEC.md | 20 |
| Архітектура | погодження A-xx/Q-xx з менеджером, фіксація контрактів CA-01…CA-09 для fire_safety, yard, viewer | 8 |
| Розробка | Odoo-модуль `odoo_addons/factory3d_access`: 7 моделей + SQL-представлення «Люди по зонах», 5 розширень (з `hr.employee.public`), REST-клієнт BioStar 2, 6 кронів, провайдер переглядача, мости telemetry/fire_safety, міграція | 96 |
| Тестування | юніт-тести з мок-клієнтом BioStar, ТК проти емулятора (P-10, S-09), безпека (персональні дані, стоп-крани), продуктивність | 40 |
| Інструкція | §4 цього документа + README модуля + CHANGELOG | 6 |
| **Разом** | | **170** |

Факти про тестовий сервер timur-o19demo, база `odoo` (перевірено 14.10.2026, лише читання):
`hr` 19.0.1.1, `hr_attendance` 19.0.2.0, `hr_skills` 19.0.1.0, `hr_attendance_gantt`, `hr_homeworking`,
`hr_org_chart` установлені. `hr.employee`: 36 записів, 35 з `barcode` (`OPSAW1`…`OPW7`), `pin` порожній у всіх,
`resource_calendar_id` = «Зміна 1 (07:00–15:30)» (id 2, `tz=Europe/Kyiv`, пн–пт 07:00–11:30 і 12:00–15:30,
`hours_per_day=8`), `tz=Europe/Kyiv`, `work_location_id` порожній, `user_id` порожній (крім Administrator).
`hr.attendance`: 35 записів, усі за 2026-10-12 з `check_in` 03:40…03:59 UTC (06:40…06:59 за Києвом, крок
`det(code, mod=20)` макета), `check_out` порожній (`attendance_state='checked_in'` у всіх 35), `in_mode='manual'`,
`expected_hours=0`. Поля `hr.attendance` 19.0: `in_mode`/`out_mode` Selection
(`kiosk`, `systray`, `manual`, `technical`; `out_mode` ще `auto_check_out`), `in_ip_address`, `in_latitude`…,
`worked_hours`, `expected_hours`, `overtime_hours`, `validated_overtime_hours`, `overtime_status`,
`linked_overtime_ids` (`hr.attendance.overtime.line`), `attendance_manager_id`, `date`. Налаштування компанії:
`attendance_kiosk_mode='barcode_manual'`, `attendance_barcode_source='front'`, `attendance_kiosk_use_pin=False`,
`attendance_from_systray=False`, `auto_check_out=False` (`auto_check_out_tolerance=2.0` год),
`absence_management=False`, `attendance_overtime_validation='no_validation'`, `overtime_company_threshold=0`,
`overtime_employee_threshold=0`, `hr_presence_control_attendance=True`. Групи: `hr_attendance.group_hr_attendance_own_reader`
(id 76), `group_hr_attendance_officer` (77 «Officer: Manage attendances» — лише підлеглі за
`attendance_manager_id`), `group_hr_attendance_user` (78 «Officer: Manage all attendances»),
`group_hr_attendance_manager` (79 «Administrator»). Меню: `hr_attendance.menu_hr_attendance_root` (205),
`menu_hr_attendance_overview` (5), `menu_hr_attendance_view_attendances_management` (6), `menu_action_open_form`
(кіоск, 10), `menu_hr_attendance_reporting` (15), `menu_hr_attendance_configuration` (99) → `menu_hr_attendance_settings`
(10). Представлення: `hr_attendance.hr_attendance_view_form`, `view_attendance_tree`, `hr_attendance_view_filter`,
`view_employee_form_inherit_hr_attendance`, `res_config_settings_view_form`. Полів `x_*`, пов'язаних зі СКУД,
у базі немає; модуля `factory3d_base` на сервері ще немає (хвиля 1).

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що є в макеті

| Джерело | Що саме | Куди йде в модулі |
|---|---|---|
| `plant/infra.py:15–28` | `KPP=(98.4,−27.0)` прохідна персоналу навпроти входу `EX-IN` (`plant/evacuation.py:22`: `("EX-IN", 98.4, 0.0, "S")`); `STAFF_ENTRANCE_X=98.4`; `DOOR_READERS` — 5 зчитувачів Suprema з координатами: `ACR-ELEC (129.0, 62.25) Електрощитова`, `ACR-CHG (117.0, 59.88) Зарядна`, `ACR-PAINT (61.0, 65.88) Склад ЛФМ`, `ACR-SRV (99.6, 48.6) Серверна`, `ACR-IN (99.3, 0.12) Вхід персоналу`; `CAMERAS` 12 камер (`CAM-07` на прохідній) | `f3d.access.device` (5 записів data з координатами; зона — зона «з» дверей, A-23), граф зон дверей §2.3 |
| `plant/site2.py:470–479, 494–525` | `build_territory`: будівля КПП 3×4 м при (101.4,−27), навіс над турнікетами; `build_security`: **два турнікети** при `kx−0.9` і `kx+0.4` з рідерами (`TURNSTILES`, desc «Вхід і вихід за картками: відмітки йдуть в Odoo Attendances»), об'єкт `ACCESS` («Рідери на дверях електрощитової, зарядної, складу ЛФМ, серверної й входу персоналу»), `CCTV` | у сцені зчитувачі — частини мешів `ACCESS`/`TURNSTILES`; «Показати в 3D» веде на ці об'єкти або на зону (A-01) |
| `plant/infra.py:361–366` | картки макета: `TURNSTILES` → «На території зараз: 146 працівників · 3 відвідувачі», «Сьогодні проходів 312», «Odoo Attendances: відмітки входу й виходу щохвилини»; `ACCESS` → «Дверей з рідерами 5», «Останній доступ: електрощитова, 09:51 — черговий електрик» | лічильники `on_site`, `events_today`, `last_event` провайдера §2.5; продуктивність §2.7 (прод ≈ 150 людей) |
| `plant/equipment_specs.json` | ролі `turnstile` (Gunnebo SlimStile EV: контролер LL2001Lite, входи відкриття по напрямках, виходи лічильника, RS-485, fail-safe + вхід пожежної тривоги), `access_reader` (Suprema BioEntry W3: обличчя AI + картки MIFARE/DESFire/EM/HID, 30 000 облич, 1 000 000 подій), `cctv_camera`, `nvr` | паспорти вже в base (CB-07); модуль лише посилається `equipment_id` → `ACCESS`, `TURNSTILES` (base Додаток F: `TURNSTILES → Z-KPP`, `ACCESS` без зони) |
| `plant/site.py:1341–1373` `build_people` | 28 операторів `OP-<РЦ>` біля верстатів і 7 складських `OP-W1…W7` з координатами: `OP-W1 (22,50.2)`, `OP-W2 (18,58.6)`, `OP-W3 (8,12)`, `OP-W4 (10,32.2)`, `OP-W5 (40,44.8)`, `OP-W6 (116,44)`, `OP-W7 (140,24)` | «домашня зона» працівника `hr.employee.f3d_home_zone_id` (R-08): оператори — зона РЦ; `OP-W*` — `zone_at` координат → `Z-HW`, `Z-HW`, `Z-RCV-2`, `Z-RCV-4`, `Z-SHEETS`, `Z-POST`, `Z-OUT-3` |
| `plant/odoo_demo.py:609–628` | `employees` (35): `name`, `job` (Оператор/Налагоджувальник/Комірник…), `department`, `workcenter`, `shift="Зміна 1 (07:00–15:30)"`, `current_workorder` | нічого нового не створюємо; читаємо `hr.employee` |
| `plant/odoo_flows.py:103–113` `step_calendar`, `469–479` `step_attendance` | календар «Зміна 1 (07:00–15:30)» пн–пт, обід 11:30–12:00; бейдж `barcode = code.replace("-", "")`; 35 відміток `check_in = 06:40 + det(code, mod=20)` хв (без `check_out`) | джерело правила зв'язку BioStar `user_id` ↔ працівник (A-03) і дедуплікації з демо-відмітками (R-04) |
| `dist/odoo_demo.json` ключі `employees` (35), `zones` (34) | формат переглядача; `meta.now = 2026-10-12 10:30` (демо-годинник) | провайдер §2.5: додає `employees[].present/zone/last_event`, `zones[].people_now`, розділ `access` |
| `viewer/index.html:1802–1835` (`renderObject`, `empHtml`, `wcHtml` — картка працівника з РЦ через `D.employees["OP-"+wc.code]`), `1923–1934` `zoneHtml` (місця, заповненість, РЦ, документи), шар `people` (`CORE`, рядок 669) | клік по людині — картка; шар людей; зона — зведення | нові рядки картки людини («На території з», «Зона», «Останній прохід») і зони («Людей зараз») — зміни в переглядачі робить автор viewer за контрактом CA-05 |
| `README.md` «Вода, ІТ і Odoo, територія й охорона» (423–434), «Люди» (540) | «прохідна з турнікетами Gunnebo і рідерами Suprema (відмітки → Odoo Attendances)»; «у Suprema немає готової інтеграції з Odoo — відмітки йдуть імпортом або конектором»; «35 співробітників відмітились на зміну 1, бейдж = код у сцені без дефісів» | обґрунтування модуля: конектор = цей модуль |
| `factory3d_iot_sim` SPEC §8.12 (P-10), §9.3 S-09, Додаток A 647–653, ARCH Q-13 | емулятор BioStar 2: `https://iot-sim:8443` (TLS self-signed) / `http://iot-sim:8081` (тести); `POST /api/login` → `bs-session-id` (30 хв бездіяльності); `GET /api/users` (`user_id` = `hr.employee.barcode`, + «1» Administrator); `GET /api/devices` (ACR-IN 5390001, ACR-ELEC 5390002, ACR-CHG 5390003, ACR-PAINT 5390004, ACR-SRV 5390005); `GET /api/doors` (двері 1 «Турнікет TURN-1» entry_device 5390001, 2 Електрощитова, 3 Зарядна, 4 Склад ЛФМ, 5 Серверна); `POST /api/events/search` (умови `datetime` BETWEEN, `device_id.id`…, `limit ≤ 2000`, `offset`); коди подій 4102/4100/4867/4865/5120/4352/6400–6405/20480…21760/26368/12544/15104; `tna_key` «1» вхід, «2» вихід; R-28 (вхід 06:40 + det mod 20, вихід 15:30 + det mod 20; електрик `OP-W1` → ACR-ELEC 09:51; `OP-W2` → ACR-PAINT 10:20; ACR-SRV адміністратор 1 раз/день); сценарій `access_event {device, user, code, tna_key, door_open}` | весь §2.4 і правила R-01…R-07 SPEC; ТК-01…ТК-10 |

Чого в макеті **немає** (не вигадуємо, виносимо в Q): номерів карток (CSN) працівників (Q-03), окремого
зчитувача на вихід (у макеті один `ACR-IN` з `tna_key`, Q-04), відвідувачів як записів (лише цифра «3 відвідувачі»
на картці — Q-06), правил робочого часу понад календар «Зміна 1» (Q-05), нічних змін (Q-05), окремих зон
для комор ЛФМ/серверної (двері 4 і 5 ведуть у приміщення всередині `Z-FAC`/`Z-MAINT` — A-05).

### 1.2 Ролі й сценарії використання

| Роль (група) | Сценарій | Меню |
|---|---|---|
| Охорона (`factory3d_access.group_f3d_access_security`) | бачить, хто зараз на території і в якій зоні; відкриває людину в 3D; читає журнал проходів і відмов (антипрохід, прострочений, заблокована картка); реєструє відвідувача, видає тимчасову картку, відмічає прихід/вихід; бачить стан дверей/турнікета (форсовано відчинені — підсвічено) | Завод 3D → Доступ → Люди по зонах, Журнал подій, Відвідувачі, Двері |
| HR-офіцер відвідуваності (`hr_attendance.group_hr_attendance_user`) | перевіряє відмітки: кожна відмітка з `in_mode='biostar'` має посилання на подію й пристрій; бачить відмітки, закриті правилом (без виходу); виправляє вручну як завжди в Odoo | Відвідування → Управління / Звітність → «Проходи СКУД» |
| Адміністратор СКУД (`factory3d_access.group_f3d_access_admin`) | веде пристрої й двері (BioStar id ↔ код сцени ↔ зони «з → в», периметр), зв'язки користувачів, картки (видача/блокування; запис у BioStar лише під стоп-краном), запускає синхронізацію, дивиться стан опитування | Завод 3D → Доступ → Пристрої, Двері, Користувачі BioStar, Картки |
| Адміністратор Завод 3D (`factory3d_base.group_f3d_admin`) | підключення до BioStar 2 (URL, логін, пароль), стоп-крани `read_enabled`/`write_enabled`, строки зберігання, `neutralize.sql` | Відвідування → Налаштування → блок «СКУД Suprema BioStar 2» (або Завод 3D → Налаштування → Налаштування СКУД — X-89); Завод 3D → Доступ → Сервери BioStar |
| Усі внутрішні (`base.group_user`, `group_f3d_user`) | на формі працівника бачать «На території», «Зона», «Останній прохід»; у 3D — людей по зонах і лічильники | Співробітники; переглядач |
| Інші модулі | `fire_safety`: список присутніх на момент тривоги й час виходу кожного через периметр (CA-03); `yard`: водії як відвідувачі (CA-07); `viewer`: провайдер (CA-05) | — |

### 1.3 Функціональні вимоги

| ID | Вимога |
|---|---|
| FR-01 | Модель `f3d.access.server` описує підключення до BioStar 2 (URL, обліковий запис у `ir.config_parameter` лише для `group_f3d_admin`, сесія `bs-session-id`, стан `online/offline/error`, останній оброблений `event_id`/`ts`) з кнопкою «Перевірити з'єднання» |
| FR-02 | Модель `f3d.access.device` пов'язує пристрій BioStar (`device_id`) з кодом сцени (`ACR-IN`…), одиницею `maintenance.equipment` (`ACCESS`/`TURNSTILES`), координатами й зоною; список і стан пристроїв синхронізуються з `GET /api/devices` |
| FR-03 | Модель `f3d.access.door` описує двері/турнікет BioStar (`door_id`) з графом зон «з → в», ознакою периметра, напрямком проходу (`in`/`out`/за `tna_key`) і станом дверей, що ведеться з подій 20480…21760 |
| FR-04 | Модель `f3d.access.user.link` зв'язує користувача BioStar (`user_id`) з `hr.employee` за бейджем (`barcode`, далі `f3d_alias`, далі `f3d_code` без дефісів) або з відвідувачем; зберігає лише факт наявності шаблону обличчя (`face_count > 0`), ніколи — біометрію |
| FR-05 | Крон щохвилини опитує `POST /api/events/search` вікном за `datetime` з перекриттям і пагінацією, дедуплікує за `(server, biostar_id)`, відновлює сесію після 401, при недоступності переходить у `error` з експоненційною паузою і продовжує з останнього вікна без втрат |
| FR-06 | Кожна подія класифікується за кодом BioStar у тип (`pass`, `fail`, `denied`, `door`, `alarm`, `system`, `other`), спосіб ідентифікації (`card`, `face`, `finger`, `id_face`, `id_finger`, `pin`), причину відмови (`access_group`, `disabled`, `expired`, `blacklist`, `apb`, `timed_apb`, `scheduled_lock`, `other`) і напрямок |
| FR-07 | Успішний прохід через периметр створює/закриває `hr.attendance` (`in_mode`/`out_mode='biostar'`, посилання на подію й пристрій): вхід без відкритої відмітки → `check_in`; вихід із відкритою → `check_out`; повторний вхід → дублікат без нової відмітки; відкрита відмітка з попереднього дня закривається за кінцем графіка (`out_mode='technical'`); вхід у межах ±20 хв від уже наявної відкритої відмітки (демо, кіоск) прив'язується, а не дублюється |
| FR-08 | Для кожного працівника/відвідувача ведеться присутність (`present`) і зона за останнім проходом (граф дверей), «вийшов із заводу» обнуляє зону; після `dwell_min` хвилин у технічному приміщенні людина повертається в домашню зону; `f3d.zone` рахує людей зараз |
| FR-09 | Відмови доступу й підозри на антипрохід (вхід уже присутнього, код 6405) фіксуються в журналі з фільтрами «Відмови», «Антипрохід», «Нерозпізнані користувачі» |
| FR-10 | Модель `f3d.access.card` веде картки (номер, тип, кому, стан `draft/active/blocked/returned/lost`); видача/блокування записуються в BioStar (`POST /api/cards`, `PUT /api/users/{id}`) **лише** при `factory3d.access.write_enabled=True`, інакше лишаються локальними з `sync_state='local'`; результат запису — `synced`/`error` з текстом |
| FR-11 | Модель `f3d.access.visitor` веде відвідувачів (ПІБ, компанія, хто приймає, строк, тимчасова картка, дозволені зони, стан `draft/expected/on_site/left/closed/cancelled`); користувач BioStar створюється під стоп-краном або прив'язується вручну; події відвідувача ведуть присутність/зону і порушення дозволених зон, але не відмітки |
| FR-12 | Меню «Завод 3D → Доступ» (sequence 70): Люди по зонах (kanban за зонами + «Показати в 3D»), Журнал подій, Двері, Пристрої, Картки, Відвідувачі, Користувачі BioStar, Сервери BioStar; у «Відвідуванні»: «Проходи СКУД» (звітність) і блок налаштувань; «Завод 3D → Налаштування → Налаштування СКУД» (`menu_f3d_access_settings`, sequence 70 — резерв CB-09, лише `group_f3d_admin`) веде до цього блоку (X-32, X-89) |
| FR-13 | Права: охорона — журнал, люди по зонах, відвідувачі, стан дверей; адміністратор СКУД — довідники, картки, зв'язки; HR-офіцер — читання журналу; `group_f3d_admin` — сервер, облікові дані, стоп-крани; номери карток і BioStar `user_id` — лише охороні/адміністратору; події зберігаються `keep_days` (90) і видаляються кроном |
| FR-14 | Провайдер `f3d.viewer.provider.access` (170) додає в payload `employees[code].present/zone/zone_since/last_event`, `zones[code].people_now`, розділ `access` (зчитувачі, двері, лічильники, останні події — останні лише охороні); зміни присутності/зони/стану дверей ідуть у шину `f3d_viewer` |
| FR-15 | Якщо встановлено `factory3d_telemetry` і `factory3d.access.publish_signals=True`, після кожного опитування модуль передає значення 7 сигналів `access/*` (iot_sim Додаток A 647–653) через `env['f3d.signal']._f3d_ingest(..., src='module')` (CT-10); самі 7 сигналів (`module='access'`, `origin='module'`, без джерела) створює міст `factory3d_access_telemetry` (auto_install, `depends` access + telemetry; X-33, SPEC M-17); без telemetry — нічого |
| FR-16 | Стоп-крани `factory3d.access.read_enabled` (умовчання з `factory3d.base.environment`) і `write_enabled` (`False`); `neutralize.sql` вимикає крони, стирає пароль і сесію, ставить сервер `offline`; секрети не потрапляють у логи |
| FR-17 | `post_init_hook` створює 1 сервер (емулятор), 5 пристроїв і 5 дверей P-10 із зонами, 35 зв'язків користувачів за бейджем, домашні зони 35 працівників, початкову присутність 35 працівників з відкритих відміток (A-22); наявні 35 демо-відміток не змінюються й не дублюються; `uninstall_hook` не видаляє відмітки й працівників |
| FR-18 | Щоденний крон господарства: ротація подій, закриття відкритих відміток попередніх днів за графіком, завершення прострочених відвідувачів, повторна перевірка вікна за останні 24 год (події, доставлені на сервер із запізненням) |
| FR-19 | Ручні дії адміністратора: «Опитати зараз», «Перевірити з'єднання», «Синхронізувати користувачів/пристрої/двері», «Обробити подію повторно», «Позначити синхронізованим» (картка) |
| FR-20 | Службові методи для інших модулів: `f3d.access.event.f3d_on_site_at(ts)` (хто був на території в момент), `f3d_passes_between(t0, t1, door_codes)` — для журналу навчальної тривоги `fire_safety` і КПП `yard` |

### 1.4 Межі: що не входить

- Керування дверима/турнікетами з Odoo (відчинити, заблокувати двері) — v1 лише читає; у BioStar пишуться
  тільки картки й користувачі-відвідувачі під стоп-краном (Q-07).
- Біометричні шаблони, фото облич, документи відвідувачів — не зберігаються й не передаються (A-09).
- Розрахунок понаднормових, табель, відпустки — стандартний `hr_attendance` (`overtime_*`, `auto_check_out`);
  модуль лише створює/закриває відмітки.
- Відеоспостереження (`CCTV`, Axis S3016) — поза модулем (опційно камери як обладнання вже є в base).
- Розпізнавання номерів, шлагбауми, водії — `factory3d_yard` (CA-07 — лише запис відвідувача).
- Пожежне розблокування дверей — апаратно (FACP → BioStar; емулятор `fire_drill` → 20480); модуль лише
  показує стан; журнал тривоги веде `factory3d_fire_safety` на наших даних (CA-03).
- Колектор і плагін `collector/plugins/biostar2.py` — **не пишуться** (каркас §6.5: «опитування REST прямо з Odoo,
  без колектора»; A-02).

## 2. Технічна реалізація

### 2.1 Місце в системі

`depends = ["factory3d_base", "hr_attendance", "mail"]` (`hr_attendance` тягне `hr`, `resource`; `mail` потрібен
для чаттера відвідувачів/карток і вже є в `hr`). Опційні (через `'<model>' in self.env`): `factory3d_viewer`
(провайдер, шина), `factory3d_telemetry` (CT-10). Без них модуль повністю працездатний.

Міст `factory3d_access_telemetry` (X-33, каркас §3, за зразком `factory3d_telemetry_viewer`): `auto_install=True`,
`depends = ["factory3d_access", "factory3d_telemetry"]`; ставиться автоматично, коли встановлені обидва модулі, і
створює 7 сигналів `access/*` (iot_sim Додаток A 647–653: `module='access'`, `origin='module'` — telemetry X-16, без
джерела) хуком і при появі нового пристрою (SPEC M-17, §5.3). Публікацію значень (R-18) робить сам `factory3d_access`
через `'f3d.signal' in self.env`, тож жорсткої залежності від telemetry немає.

Бере з `factory3d_base`: `f3d.scene.mixin` на `hr.employee` (`f3d_code`, `f3d_alias`, `search_f3d`,
`action_f3d_show`), `f3d.zone` (`zone_at`, коди Додатка C/C.2, xml-id `factory3d_base.zone_<slug>`),
`maintenance.equipment.f3d_code` (`ACCESS`, `TURNSTILES`), групи CB-10, `factory3d.base.environment`,
меню CB-09. Бере з `hr_attendance`: `hr.attendance` (`check_in/check_out/in_mode/out_mode`),
`hr.employee.barcode/attendance_state/last_attendance_id/resource_calendar_id/tz`, групи, меню, налаштування
`auto_check_out`.

Контракти, які **задає** цей модуль (посилатися як `factory3d_access CA-xx`):

| ID | Контракт | Споживачі |
|---|---|---|
| CA-01 | Поля `hr.employee`: `f3d_access_present` (Boolean, stored), `f3d_access_zone_id` (Many2one `f3d.zone`, stored — ефективна зона за R-08), `f3d_access_zone_since` (Datetime), `f3d_access_last_in`, `f3d_access_last_out` (Datetime UTC), `f3d_home_zone_id`, `f3d_access_last_event_id` | fire_safety (евакуація: хто на території), viewer, yard |
| CA-02 | `f3d.zone.f3d_people_now` (Integer, compute), `f3d_people_employee_ids`, `f3d_people_visitor_ids` (compute), `action_view_people()` | fire_safety (пункт збору), viewer |
| CA-03 | `env['f3d.access.event'].f3d_on_site_at(ts: datetime, company=None) -> dict` (`{'employees': recordset, 'visitors': recordset, 'ts': ts}`) і `f3d_passes_between(t0, t1, door_codes=None, direction=None) -> recordset` подій типу `pass` з полями `ts`, `employee_id`, `visitor_id`, `door_id.code`, `direction` | fire_safety (журнал навчальної тривоги: хто був усередині, коли вийшов через `TURN-1`), yard |
| CA-04 | `f3d.access.door`: `code` (`TURN-1`, `DOOR-ELEC`, `DOOR-CHG`, `DOOR-PAINT`, `DOOR-SRV`), `state` (`locked/unlocked/open/closed/forced/held/unknown`), `alarm`, `is_perimeter`, `zone_from_id`, `zone_to_id`; зміна стану → `f3d.viewer.event._notify('f3d.access.door', [code], 'state')` | fire_safety (двері на евакуаційних шляхах), viewer |
| CA-05 | Провайдер `f3d.viewer.provider.access` (`_f3d_sequence=170`, `_f3d_sections=('access',)`): ключі `employees[code].present` (bool), `.zone` (код зони або `null`), `.zone_since` («YYYY-MM-DD HH:MM» Київ), `.last_event` (`{ts, door, direction, type}`); `zones[code].people_now` (int); розділ `access` (SPEC §9 R-12 — схема); картки `infra.cards.TURNSTILES/ACCESS.rows`. Дельта (SPEC R-12 п. 7, X-23, X-87): розділ `access` — цілком, `employees`, `zones`, `infra` — лише доповнення через спільний `deep_merge` viewer (`factory3d_viewer/tools/payload.py`) | viewer (картки людини/зони, шар людей) |
| CA-06 | `hr.attendance.in_mode/out_mode` отримують значення `biostar` («СКУД BioStar 2»); поля `f3d_in_event_id`, `f3d_out_event_id`, `f3d_in_device_id`, `f3d_out_device_id`, `f3d_closed_by_rule` (Boolean) | HR-звіти, fire_safety |
| CA-07 | `f3d.access.visitor`: створення з інших модулів через ORM з `origin` (`manual/yard/portal`) і `origin_ref` (Char); метод `f3d_visitor_register(vals) -> record` робить `expected` і резервує картку з пулу | yard (водії сторонніх фур) |
| CA-08 | Групи `factory3d_access.group_f3d_access_security` ⊂ `group_f3d_access_admin` ⊂ `factory3d_base.group_f3d_admin`; `group_f3d_access_security` ⊃ `factory3d_base.group_f3d_user` | fire_safety, yard (видимість людей по зонах) |
| CA-09 | Джерело проходів для навчальної тривоги (відповідь на fire CF-02, Q-10, Q-15): `AbstractModel` `f3d.fire.passage.source.access` (`_f3d_priority=10`, `_f3d_on_site(at)`, `_f3d_passages(start, end)`, `_f3d_drill_active(ts)`); модуль питає `f3d.fire.drill._f3d_is_active_at(ts) -> bool`, і під час навчання виходи не закривають відмітки (SPEC R-04, R-05, R-21; A-24, Q-13) | fire_safety |

### 2.2 Архітектурна схема

```
┌─ Odoo 19 ──────────────────────────────────────────────────────────────────────────────────────────────┐
│  factory3d_access                                                                                      │
│  ┌───────────────┐  cron 1 хв   ┌──────────────────────┐   R-01…R-10   ┌─────────────────────────────┐ │
│  │ f3d.access.   │ ───────────► │ tools/biostar_client │ ────────────► │ f3d.access.event (журнал)   │ │
│  │ server        │  login/      │ (requests, TLS,      │  нові рядки   │  ├─ hr.attendance (R-04…07) │ │
│  │ (сесія, стан, │  events/     │  bs-session-id,      │               │  ├─ hr.employee.present/zone│ │
│  │ last_event)   │  users/      │  пагінація, 401→re-  │               │  ├─ f3d.access.door.state   │ │
│  └───────────────┘  devices/    │  login, тайм-аути)   │               │  └─ f3d.access.visitor      │ │
│          ▲          doors       └──────────┬───────────┘               └───────────┬─────────────────┘ │
│  write_enabled                             │ POST /api/cards, PUT /api/users (лише write_enabled)      │
│  (картки, відвідувачі) ◄───────────────────┘                                       │                   │
│                                                                                    ▼                   │
│  f3d.viewer.provider.access (170) ──► payload.employees/zones/access ──► bus f3d_viewer (M-03)        │
│  f3d.signal._f3d_ingest (CT-10, опційно) ──► access/readers/*/last_event, access/turnstiles/*/on_site  │
└──────────────────────────────────────────────┬─────────────────────────────────────────────────────────┘
                                               │ HTTPS REST BioStar 2 (P-10): https://iot-sim:8443 (стенд)
                                               ▼                               https://<biostar>:443 (прод)
                     [ емулятор factory3d_iot_sim: biostar_api.py ]   або   [ сервер BioStar 2 + BioEntry W3 + Gunnebo ]
```

Потоки: (1) Odoo → BioStar: опитування (читання) щохвилини, синхронізація довідників щогодини/щодоби;
(2) Odoo → BioStar: запис карток/відвідувачів лише під стоп-краном; (3) Odoo → переглядач: шина й payload;
(4) Odoo → telemetry: опційно 7 сигналів (створює міст `factory3d_access_telemetry`, X-33). Колектора немає (A-02). Емулятор нічого не «пушить» в Odoo —
усе ініціює Odoo (на відміну від Axis LPR у yard).

### 2.3 Нові й розширені об'єкти — огляд

| Модель | Призначення | Хто пише | Хто читає |
|---|---|---|---|
| `f3d.access.server` (M-01) | підключення до BioStar 2, сесія, стан, курсор опитування, лічильники | `group_f3d_admin` (дані), крон | адмін СКУД (стан) |
| `f3d.access.device` (M-02) | зчитувач/контролер BioStar ↔ код сцени ↔ обладнання ↔ зона; статус | адмін СКУД, синхронізація | усі `f3d_user` |
| `f3d.access.door` (M-03) | двері/турнікет BioStar: граф зон «з → в», периметр, напрямок, стан, тривога | адмін СКУД, події | усі `f3d_user`; fire_safety |
| `f3d.access.user.link` (M-04) | користувач BioStar ↔ працівник/відвідувач, спосіб збігу, факт біометрії | синхронізація, адмін СКУД | охорона, HR-офіцер |
| `f3d.access.event` (M-05) | подія BioStar: id, час, пристрій, двері, користувач, тип, спосіб, причина, напрямок, результат для відмітки/зони | крон (тільки `create`), «обробити повторно» | охорона, HR-офіцер, fire_safety, yard |
| `f3d.access.card` (M-06) | картка працівника/відвідувача: номер, тип, стан, синхронізація з BioStar | адмін СКУД, охорона (відвідувачам) | охорона |
| `f3d.access.visitor` (M-07) | відвідувач: приймаючий, строк, картка, зони, присутність, стан | охорона, yard (CA-07) | охорона, HR |
| `hr.employee` (+поля, M-08) | присутність, зона, домашня зона, останні проходи, картки, зв'язок BioStar | події, хук | усі |
| `hr.attendance` (+поля, M-09) | `in_mode/out_mode='biostar'`, посилання на події/пристрої, `f3d_closed_by_rule` | R-04…R-07 | HR |
| `f3d.zone` (+поля, M-10) | людей зараз, список присутніх, дія «Люди в зоні» | compute | усі, fire_safety |
| `res.config.settings` (M-11) | стоп-крани, інтервали, строки, режими правил | `group_f3d_admin` | — |
| `f3d.viewer.provider.access` (M-12) | провайдер переглядача (лише якщо viewer) | — | переглядач |
| `f3d.access.event.reprocess.wizard` (M-13, Transient) | повторна обробка подій за період і опитування періоду | адмін СКУД | — |
| `f3d.access.presence` (M-14, SQL-представлення) | «Люди по зонах»: працівники на території + відвідувачі `on_site` (A-17; охорона без `hr.group_hr_user` не читає `hr.employee`) | — | охорона, HR-офіцер |
| `hr.employee.public` (+поля, M-08a) | дзеркало полів присутності для публічного профілю | — | усі внутрішні |
| `f3d.access.telemetry` (M-15, Abstract) | публікація 7 сигналів `access/*` (FR-15) | опитування | — |
| міст `factory3d_access_telemetry` (M-17: `_inherit` `f3d.access.telemetry`, `f3d.access.device`) | створення 7 сигналів `f3d.signal` `access/*` (X-33) | `post_init_hook`, `create` пристрою | telemetry |
| `f3d.fire.passage.source.access` (M-16, Abstract) | джерело проходів для навчальної тривоги (CA-09) | — | fire_safety |

Граф зон дверей (data, з координат `plant/infra.py:DOOR_READERS` і макета КПП; A-05). Зона пристрою = зона «з»
дверей і задається в data (A-23): `zone_at` для зчитувачів на стінах (`ACR-IN y=0.12`, `ACR-ELEC y=62.25`,
`ACR-CHG y=59.88`) потрапляє в зазор між зонами й повертає порожньо.

| Двері (`code`) | BioStar door | Зчитувач | Зона «з» | Зона «в» | Периметр | Напрямок | `dwell_min` |
|---|---|---|---|---|---|---|---|
| `TURN-1` Турнікет прохідної | 1 | `ACR-IN` (5390001) | `Z-KPP` | `Z-ASM` (вхід `EX-IN` при x=98.4 відкривається в зону збирання; далі R-08 підставляє домашню зону) | так | за `tna_key` (1 вхід, 2 вихід) | 0 |
| `DOOR-ELEC` Електрощитова | 2 | `ACR-ELEC` (5390002), (129.0, 62.25) | `Z-FG` | `Z-ELEC` | ні | `in` | 30 |
| `DOOR-CHG` Зарядна | 3 | `ACR-CHG` (5390003), (117.0, 59.88) | `Z-POST` | `Z-CHG` | ні | `in` | 30 |
| `DOOR-PAINT` Склад ЛФМ | 4 | `ACR-PAINT` (5390004), (61.0, 65.88) | `Z-FAC` | `Z-FAC` (комора `PAINT-STORE` всередині зони) | ні | `in` | 30 (A-25) |
| `DOOR-SRV` Серверна | 5 | `ACR-SRV` (5390005), (99.6, 48.6) | `Z-MAINT` | `Z-MAINT` (засклена серверна всередині) | ні | `in` | 30 (A-25) |

### 2.4 Інтеграції

| Канал | Пристрої | Протокол, адреса (стенд) | Напрямок | Частота | При недоступності |
|---|---|---|---|---|---|
| P-10 BioStar 2 події | `ACR-IN`, `ACR-ELEC`, `ACR-CHG`, `ACR-PAINT`, `ACR-SRV` (BioEntry W3), двері 1–5 (у т. ч. турнікет Gunnebo через контролер) | HTTPS REST `https://iot-sim:8443/api/*` (TLS самопідписаний → `verify_ssl=False` лише на тесті; прод — `True` з CA), JSON, заголовок `bs-session-id`; `POST /api/events/search` умови `datetime BETWEEN [since−overlap, now + future_tolerance_s (300 с)]`, `orders datetime asc`, `limit=page_size (500)`, `offset` (або `hint`, A-10) | Odoo → BioStar (опитування) | крон `cron_f3d_access_poll` 1 хв; `overlap_s=120`; ≤ `max_pages_per_run=20` сторінок | 5xx/таймаут/з'єднання → `state='error'`, `error_count+1`, наступна спроба через `min(60·2^n, 600)` с; курсор не рухається; 401 → `login()` один раз і повтор; після відновлення — та сама логіка вікна, пропусків немає (дедуплікація за `biostar_id`) |
| P-10 користувачі | — | `GET /api/users?limit=100&offset=n` | Odoo → BioStar | крон щогодини + кнопка | як вище; зв'язки не змінюються |
| P-10 пристрої й двері | — | `GET /api/devices`, `GET /api/doors` | Odoo → BioStar | крон щодоби 03:10 + кнопка | як вище; `status` пристроїв → `unknown` після 2 невдалих синхронізацій |
| P-10 запис | — | `POST /api/cards` (card_type 0 CSN), `PUT /api/users/{id}` (`cards[]` з `is_blocked`), `POST /api/users` (відвідувач з `expiry_datetime`) — статті Suprema 24000091098, 24000082780, 24000072555 (переглянуто 14.10.2026); точний формат `is_blocked` — **ПРИПУЩЕННЯ** (у статті про мобільний доступ `"is_blocked": "false"` у `cards[]`) | Odoo → BioStar | за дією користувача; черга `sync_state='pending'`, крон 10 хв повторює | лише при `write_enabled`; емулятор відповідає 405 на POST незмінних ресурсів (iot_sim §11) → `sync_state='error'`, текст помилки на картці; локальний стан лишається |
| viewer | — | ORM-хук M-01, шина `bus.bus` канал `f3d_viewer` | Odoo → клієнт | при зміні | без viewer — нічого |
| telemetry (опційно) | сигнали `access/readers/<code>/last_event` ×5, `access/turnstiles/TURNSTILES/on_site`, `access/events` | `env['f3d.signal']._f3d_ingest([{code, ts, value\|text}], src='module')` (CT-10); сигнали створює міст `factory3d_access_telemetry` (X-33) | Odoo → Odoo | після кожного опитування, якщо були нові події | без telemetry — пропуск; архівний/видалений сигнал — `rejected`, DEBUG |

Прод: та сама конфігурація з `url=https://<biostar-host>:443`, `verify_ssl=True`, обліковим записом
оператора BioStar з правом читання журналу (і запису користувачів/карток, якщо `write_enabled`), `read_enabled`
за умовчанням `False` (CB-10) — адміністратор вмикає після звірки.

### 2.5 Потік даних від пристрою до екрана

Приклад: Олег Мельник (`OP-SAW-1`, бейдж `OPSAW1`) прикладає картку до `ACR-IN` о 06:52 за Києвом 2026-10-12.

1. BioEntry W3 → BioStar 2: подія `event_type_id.code=4102` (Verify success, card), `user_id.user_id="OPSAW1"`,
   `device_id.id="5390001"`, `door_id=[{id:"1"}]`, `datetime="2026-10-12T03:52:10.00Z"`, `tna_key="1"`; далі
   `20480` (door unlocked), `20992` (opened), `21248` (closed) на дверях 1.
2. Крон (`f3d.access.server._cron_poll`) через ≤ 60 с: `search_events(since=last_event_ts−120 с, until=now)`
   → 4 рядки; дедуплікація за `(server_id, biostar_id)` → 4 нові `f3d.access.event` (`ts=2026-10-12 03:52:10`
   UTC naive, `code=4102`, `event_type='pass'`, `credential='card'`, `tna_key='1'`, `device_id=ACR-IN`,
   `door_id=TURN-1`, `raw_user_id='OPSAW1'`).
3. R-03: `f3d.access.user.link(server, 'OPSAW1')` → `employee_id` = Олег Мельник (створено хуком за `barcode`).
4. R-02: двері `TURN-1`, пристрій `direction='tna'`, `tna_key='1'` → `direction='in'`.
5. R-04: відкритої відмітки немає → `hr.attendance.create({employee_id, check_in='2026-10-12 03:52:10',
   in_mode='biostar', f3d_in_event_id, f3d_in_device_id})`; подія: `attendance_id`, `attendance_action='checked_in'`.
   (На копії демо відкрита відмітка з `check_in=03:52:00` уже є → R-04 крок 3: `|03:52:10 − 03:52:00| ≤ 20 хв`
   → прив'язка `attached`, нова не створюється.)
6. R-08: `TURN-1.is_perimeter`, `in` → `employee.f3d_access_present=True`, `f3d_access_last_in=ts`,
   `f3d_access_zone_id` = домашня зона `Z-CUT` (оператор `SAW-1`; якщо домашньої немає — `zone_to=Z-ASM`),
   `f3d_access_zone_since=ts`, `f3d_access_zone_door_id=False`.
7. R-10: події дверей 20480/20992/21248 → `TURN-1.state` `unlocked → open → closed`, `alarm=False`.
8. Шина (якщо viewer): `_notify('hr.employee', ['OP-SAW-1'], 'state')`, `_notify('f3d.access.door', ['TURN-1'], 'state')`;
   переглядач дозапитує `/f3d/viewer/delta` → провайдер people віддає повний запис `employees['OP-SAW-1']`,
   провайдер access через `deep_merge` (X-23, X-87) додає до нього `present: true, zone: "Z-CUT", zone_since: "2026-10-12 06:52",
   last_event: {…}`, `zones` (`Z-CUT.people_now` = 4) і рядки карток `infra.cards.TURNSTILES/ACCESS`, а розділ `access`
   (`on_site.employees` +1, `doors.TURN-1.state`) — цілком; клієнт зливає дельту глибоко.
9. Екран: Завод 3D → Доступ → Люди по зонах — картка Олега у колонці «Розкрій»; форма працівника — «На території
   з 06:52», «Зона: Розкрій»; Відвідування — відмітка 06:52 з іконкою «СКУД BioStar 2» і посиланням на подію;
   3D — людина підсвічена в зоні, лічильник «Людей зараз: 4» на картці `Z-CUT` (оператори SAW-1, SAW-2, SLIDE-1,
   NEST-1; у SAW-3 і VSAW-1 оператора в демо немає — base Додаток B).
10. 15:42 вихід (`tna_key="2"`): R-05 → `check_out='2026-10-12 12:42:xx'`, `out_mode='biostar'`; `worked_hours`
    = 8,83 (рахує Odoo); R-08 → `present=False`, `zone=False`, `last_out=ts`.

### 2.6 Безпека

- **Групи** (CB-10, CA-08): `group_f3d_access_security` «Охорона» (implied `factory3d_base.group_f3d_user`):
  читання подій, пристроїв, дверей, зв'язків; CRUD відвідувачів; читання карток і видача карток відвідувачам;
  `group_f3d_access_admin` «Адміністратор СКУД» (implied `group_f3d_access_security`, `factory3d_base.group_f3d_manager`):
  CRUD пристроїв, дверей, зв'язків, карток працівників; кнопки синхронізації; `factory3d_base.group_f3d_admin`
  (implied `group_f3d_access_admin`): сервер, облікові дані, стоп-крани, параметри. HR-офіцер
  (`hr_attendance.group_hr_attendance_user`): читання подій і зв'язків (без номерів карток).
- **Облікові дані BioStar**: `factory3d.access.biostar_login`, `factory3d.access.biostar_password` в
  `ir.config_parameter` (читання/запис — `group_f3d_admin`; у налаштуваннях поле `password` з
  `password="True"`); `session_id` на сервері — поле з `groups="factory3d_base.group_f3d_admin"`; у логах
  `SecretFilter` замінює `bs-session-id`, `password` на `***`; у чаттер і повідомлення помилок секрети не
  потрапляють (тільки HTTP-код і `Response.message`). Пароль не хешується (потрібен для `login`) — тому
  `neutralize.sql` його стирає (A-11).
- **Стоп-крани**: `factory3d.access.read_enabled` (умовчання `environment == 'test'`; `False` → крони нічого не
  роблять, кнопки «Опитати зараз» → `UserError`), `factory3d.access.write_enabled` (`False`; усі методи
  клієнта з `POST/PUT` перевіряють прапор до з'єднання), на сервері `active`; `neutralize.sql` (SPEC §5.5).
- **Персональні дані (мінімум)**: модуль зберігає BioStar `user_id` (= бейдж), час/двері проходів, номер картки
  (CSN), ПІБ відвідувача, компанію, приймаючого, строк. **Не зберігає**: шаблони обличчя/пальців, фото
  (`photo_exists` ігнорується), документи відвідувачів, `raw` JSON подій (лише при `keep_raw=True`,
  умовчання `False`, і тоді без поля `user_id.name`). Строк зберігання подій — `keep_days=90` (Q-08), подій
  відвідувачів — той самий; картки відвідувачів після `returned` не прив'язані до особи (`visitor_id` лишається
  для історії до `keep_days`, далі `set null` кроном). Хто бачить: номери карток, `user_id`, список подій —
  охорона/адмін СКУД/HR-офіцер; присутність/зона — усі внутрішні (як `hr_presence`); зовнішнім (портал) — нічого.
- **Ін'єкції/валідація**: коди пристроїв/дверей — regex R-01 base; `biostar_id` — `^[0-9A-Za-z_\-]{1,64}$`;
  URL сервера — `https?://`; усі SQL — ORM або параметризовані (`execute_values` для масового створення подій
  не використовується — ORM `create` пакетами по 500, обсяг малий); JSON від BioStar читається через
  `response.json()` без `eval`; значення `event_type_id.code` приводиться `int()` з обробкою `ValueError`.
- **Мережа**: Odoo звертається лише до `url` сервера; `verify_ssl=False` дозволено тільки при
  `environment='test'` (constraint).

### 2.7 Продуктивність і обсяги

- Макет: 35 працівників → 70 проходів периметра/добу + 3 події дверей на прохід (20480/20992/21248) + ≈ 10
  внутрішніх проходів ×4 = **≈ 320 подій/добу**; прод (картка макета: 146 працівників, 312 проходів/добу) →
  ≈ 1 400 подій/добу; за `keep_days=90` ≈ 130 000 рядків `f3d.access.event` (≈ 60 МБ з індексами).
- Опитування: 1 запит/хв + 1 сторінка (500) — ≈ 1 500 запитів/добу; обробка 320 подій/добу — мілісекунди.
  Ліміт за прогін `max_pages_per_run=20` (10 000 подій) захищає від лавини після простою; решта — наступними
  прогонами (курсор рухається по мірі обробки).
- Індекси: `f3d_access_event (server_id, biostar_id)` unique; `(ts)`, `(employee_id, ts)`, `(door_id, ts)`,
  `(event_type)`; `hr_attendance (employee_id, check_in)` — стандарт; `f3d_access_user_link (server_id, biostar_user_id)` unique.
- Ротація: крон господарства щодоби видаляє події старіші за `keep_days` пакетами по 5 000 (`unlink` через
  `_gc`), `f3d.viewer.event` — не наша ротація.
- Провайдер переглядача: 35 (прод 150) працівників + 5 дверей — < 20 мс; `f3d_people_now` — один `read_group`
  по `f3d_access_zone_id`.
- Шина: не частіше 1 повідомлення на транзакцію обробки (коалесценція viewer R-15).

### 2.8 Міграція з демо-бази і деінсталяція

`x_*`-полів у СКУД немає. `post_init_hook` (SPEC §5.3): 1) параметри; 2) сервер «BioStar 2 (емулятор)»
`https://iot-sim:8443`, `verify_ssl=False`, `active=True`, `state='offline'`; 3) 5 пристроїв + 5 дверей з
data (xml-id), прив'язка `equipment_id` через `env['maintenance.equipment'].search_f3d('ACCESS'|'TURNSTILES')`
(`ACR-IN` → `TURNSTILES`, решта → `ACCESS`; на чистій базі без обладнання — порожньо, WARNING), `zone_id` пристроїв —
з data (зона «з» дверей, A-23);
4) 35 `f3d.access.user.link` для `hr.employee` з `barcode` (`biostar_user_id=barcode`, `match='barcode'`,
`synced=False` до першої синхронізації); 5) домашні зони: 28 операторів — `f3d_zone_id` робочого центру, де
`employee ∈ workcenter.employee_ids` (base R-06 крок 4 дає РЦ; якщо `f3d_code = OP-<wc>` — `search_f3d(wc)`),
7 складських — `data/scene_home_zones.csv` (`OP-W1,Z-HW` … `OP-W7,Z-OUT-3`); 6) демо-відмітки: **нічого не
змінюємо** (35 відкритих `in_mode='manual'` лишаються; R-04 крок 3 прив'яже їх до подій емулятора, якщо той
відтворює 2026-10-12; інакше R-07 закриє їх за кінцем графіка 2026-10-12 15:30 при першому проході наступного
дня/кроном господарства); 7) початкова присутність (A-22): працівники з відкритою відміткою → `present=True`,
зона = домашня, «у зоні з» = `check_in` (відмітки не змінюються); 8) звіт у `factory3d.access.migration_report`.
Очікувані кількості на копії демо: `servers: 1`, `devices: 5`, `doors: 5`, `links: 35`, `home_zones: 35` (28 + 7),
`equipment_bound: 5` (2 різні одиниці `TURNSTILES`, `ACCESS`), `presence_seeded: 35`, `attendances_touched: 0`.

`uninstall_hook`: вимикає крони (стандарт видаляє свої), видаляє параметри `factory3d.access.*`; відмітки
`hr.attendance` лишаються — поля `in_mode/out_mode` зі значенням `biostar` Odoo при видаленні `selection_add`
переводить на `set default` (`manual`) — це задекларовано в `ondelete`; події, картки, відвідувачі, зв'язки —
видаляються разом із таблицями (бізнес-даних для інших модулів вони не несуть; A-12). Поля `f3d_access_*`
на працівниках зникають з полями.

## 3. Налаштування системи

| Об'єкт | Параметр | Значення (тестовий сервер) | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `factory3d.access.read_enabled` | `True` (умовчання = `factory3d.base.environment == 'test'`) | прод: `False` після встановлення; вмикає крони опитування/синхронізації |
| `ir.config_parameter` | `factory3d.access.write_enabled` | `False` | запис карток/користувачів у BioStar; на стенді лишати `False` (емулятор → 405), вмикати лише для ТК-08 |
| `ir.config_parameter` | `factory3d.access.biostar_login` | `admin` | обліковий запис BioStar (емулятор: `SIM_BIOSTAR_USER`) |
| `ir.config_parameter` | `factory3d.access.biostar_password` | з `SIM_BIOSTAR_PASS` стенду | лише `group_f3d_admin`; стирається `neutralize.sql` |
| `ir.config_parameter` | `factory3d.access.poll_interval_s` | `60` | інформативно (інтервал крону міняється у `ir.cron`); використовується для `stale` сервера (3 інтервали без контакту) |
| `ir.config_parameter` | `factory3d.access.page_size` | `500` | `Query.limit` (емулятор ≤ 2000; Suprema радить ≤ 2000) |
| `ir.config_parameter` | `factory3d.access.max_pages_per_run` | `20` | захист від лавини |
| `ir.config_parameter` | `factory3d.access.overlap_s` | `120` | перекриття вікна `datetime` |
| `ir.config_parameter` | `factory3d.access.initial_lookback_h` | `24` | перше опитування: від `now − 24 год` |
| `ir.config_parameter` | `factory3d.access.paging_mode` | `offset` | `offset` (емулятор) або `hint` (BioStar 2 ≥ 2.8, стаття 24000106474, A-10) |
| `ir.config_parameter` | `factory3d.access.dup_window_min` | `20` | R-04: прив'язка до вже відкритої відмітки |
| `ir.config_parameter` | `factory3d.access.merge_gap_min` | `0` | R-06: злиття коротких виходів (0 = вимкнено; кожен вихід закриває відмітку) |
| `ir.config_parameter` | `factory3d.access.max_shift_h` | `16` | R-05: вихід у межах 16 год після входу закриває відмітку навіть через північ (A-20) |
| `ir.config_parameter` | `factory3d.access.future_tolerance_s` | `300` | верхня межа вікна опитування `now + 300 с` (R-11, R-15) |
| `ir.config_parameter` | `factory3d.access.recheck_hours` | `24` | добова перевірка вікна (FR-18, R-20) |
| `ir.config_parameter` | `factory3d.access.last_events_limit` | `20` | останні події в переглядачі (лише охороні, R-12) |
| `ir.config_parameter` | `factory3d.access.card_sync_max_attempts` | `10` | повтори запису карток (R-13) |
| `ir.config_parameter` | `factory3d.access.visitor_user_group_id` | `1` | `user_group_id` відвідувача в BioStar (ПРИПУЩЕННЯ, Q-06) |
| `ir.config_parameter` | `factory3d.access.stale_close_enabled` | `True` | R-07: закриття відкритих відміток попередніх днів за графіком |
| `ir.config_parameter` | `factory3d.access.stale_close_fallback_min` | `60` | R-07: якщо вхід пізніше кінця графіка — закрити через N хв після входу |
| `ir.config_parameter` | `factory3d.access.keep_days` | `90` | ротація подій (Q-08) |
| `ir.config_parameter` | `factory3d.access.keep_raw` | `False` | зберігати сирий JSON події (без імені користувача) |
| `ir.config_parameter` | `factory3d.access.publish_signals` | `True` | FR-15; без telemetry — ігнорується |
| `ir.config_parameter` | `factory3d.access.visitor_default_hours` | `8` | строк відвідувача за умовчанням |
| `ir.config_parameter` | `factory3d.access.visitor_user_prefix` | `V-` | BioStar `user_id` відвідувача `V-<id>` |
| `ir.config_parameter` | `factory3d.access.migration_state`, `migration_report` | `pending` / `{}` | як у base |
| `f3d.access.server` | «BioStar 2 (емулятор)»: `url=https://iot-sim:8443`, `verify_ssl=False`, `timeout_connect_s=5`, `timeout_read_s=30` | data | прод: URL сервера BioStar, `verify_ssl=True` |
| `f3d.access.device` | 5 записів §2.3 (`biostar_id` 5390001…5390005) | data | прод: `biostar_id` з `GET /api/devices` після синхронізації |
| `f3d.access.door` | 5 записів §2.3 (зони, периметр, напрямок, `dwell_min`) | data | прод: уточнити граф зон з монтажником (Q-04) |
| `ir.cron` | `cron_f3d_access_poll` 1 хв; `cron_f3d_access_sync_users` 1 год; `cron_f3d_access_sync_devices` 1 день 03:10; `cron_f3d_access_zone_dwell` 5 хв; `cron_f3d_access_card_sync` 10 хв; `cron_f3d_access_housekeeping` 1 день 02:30 | `active=True` на тесті | `neutralize.sql` → `active=False` |
| `res.company` (стандарт `hr_attendance`) | `auto_check_out=True`, `auto_check_out_tolerance=2.0`; `overtime_company_threshold=20`, `overtime_employee_threshold=10` | рекомендація (ручна зміна адміністратором; модуль не пише в компанію) | авто-вихід Odoo закриває забуті відмітки через 2 год після кінця графіка; тоді R-07 спрацьовує лише як резерв |
| `res.groups` | `group_f3d_access_security` → охоронці; `group_f3d_access_admin` → адміністратор СКУД; `hr_attendance.group_hr_attendance_user` → HR | вручну | тест: користувачі `security`, `access_admin` з `tests/common.py` |
| `ir.ui.menu` | `factory3d_access.menu_f3d_access_settings` «Налаштування СКУД» | батько `factory3d_base.menu_f3d_config`, sequence 70, група `factory3d_base.group_f3d_admin` | створює модуль; дія `action_f3d_access_settings` відкриває налаштування «Відвідування» з блоком СКУД (X-32, X-89) |

## 4. Інструкція

**4.1 Підключити BioStar 2 (адміністратор Завод 3D).** Відвідування → Налаштування → блок «СКУД Suprema
BioStar 2»: URL сервера, логін, пароль, «Перевіряти сертифікат» (на тесті — вимкнено), «Приймати події»
(стоп-кран). Зберегти → Завод 3D → Доступ → Сервери BioStar → «Перевірити з'єднання»: стан `online`, кількість
користувачів/пристроїв (версії BioStar P-10 не віддає). «Синхронізувати пристрої» → у Пристроях з'являються BioStar id; для кожного
задати код сцени й обладнання (на стенді — уже з data). «Синхронізувати користувачів» → Користувачі BioStar:
35 зв'язаних за бейджем, незв'язані — підсвічені (дати працівнику бейдж = `user_id` BioStar і повторити).

**4.2 Перевірити відмітку (HR-офіцер).** Відвідування → Управління: відмітки з режимом «СКУД BioStar 2» мають
поля «Подія входу/виходу» і «Пристрій входу/виходу»; клік — подія з часом сервера й дверима. Фільтр «Закриті за
правилом» показує відмітки без відмітки виходу, закриті кінцем графіка (`out_mode` «Технічний», позначка
«Закрито правилом R-07») — перевірити й, за потреби, виправити `check_out` вручну (стандартно).

**4.3 Хто зараз на території (охорона).** Завод 3D → Доступ → Люди по зонах: kanban, колонка = зона, картка =
людина (час входу, останній прохід), лічильники в заголовках колонок; «Показати в 3D» на колонці відкриває зону
в переглядачі з підсвіченими людьми; фільтри «Відвідувачі», «Без домашньої зони». Форма працівника → вкладка
«Доступ»: присутність, зона, останні проходи, картки.

**4.4 Зареєструвати відвідувача (охорона).** Завод 3D → Доступ → Відвідувачі → Створити: ПІБ, компанія, хто
приймає, з/до (умовчання 8 год), дозволені зони, картка з пулу (стан `draft` → «Видати»). «Очікується» →
при першому проході `TURN-1` стан стає «На території» автоматично (якщо BioStar `user_id` відвідувача прив'язано:
під стоп-краном модуль створює користувача сам; інакше охорона створює його в BioStar і вводить `user_id` у полі
«Користувач BioStar»). «Вийшов» — автоматично за проходом на вихід або кнопкою; «Закрити» повертає картку в пул.
Прострочені (після `date_to` + 1 год) закриває крон із позначкою «Прострочено».

**4.5 Заблокувати картку (адміністратор СКУД).** Картки → картка → «Заблокувати» (причина). Локально стан
`blocked` одразу; якщо стоп-кран «Запис у BioStar» увімкнено — запис іде в BioStar (`sync_state` → `synced`),
інакше `local` і підказка «Заблокуйте картку в BioStar вручну і натисніть „Позначити синхронізованим“».
При помилці (`error`) — текст відповіді BioStar, крон повторює кожні 10 хв; «Повторити» вручну.

**4.6 Недоступність BioStar (адміністратор).** Сервер у стані `error` з часом останньої помилки й текстом;
крон повторює з паузою до 10 хв; після відновлення відмітки за весь час простою з'являються самі (вікно від
останньої обробленої події). Якщо простій > 24 год — натиснути «Опитати період…» (майстер M-13) із датами.
Стоп-крани на проді: «Приймати події» вимкнено → крони мовчать, кнопки → повідомлення; копія проду для тестів
— `neutralize.sql` модуля (разом із base/viewer/telemetry).

## 5. Ризики й відкриті питання

### 5.1 Відкриті питання (ті самі номери — у SPEC §15)

| ID | Питання | Кому | Рекомендована відповідь | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** обидва режими `offset`/`hint`. Пагінація `events/search`: емулятор описує `offset` і «`id > last_id`» (iot_sim §8.12), стаття Suprema 24000106474 — лише `hint` з `limit` (без `offset`), стаття 24000072557 — колонки без `id`. Який режим на проді? | автор iot_sim, замовник (версія BioStar 2) | емулятор додати підтримку `Query.hint` (віддає `hint` у рядках уже зараз); модуль — `paging_mode` `offset`/`hint` (A-10) | `offset` на стенді; `hint` після перевірки на проді |
| Q-02 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** запізнілі події — добовим переглядом (FR-18). Чи має прод BioStar 2 колонку `server_datetime` в умовах пошуку, щоб ловити події, вивантажені з пристрою із запізненням (офлайн-пристрій)? | замовник, Suprema | так (стаття 24000072557: значення в лапках) | вікно за `datetime` + добовий перегляд 24 год (FR-18) |
| Q-03 | **Закрито 14.10 (рішення менеджера):** у v1.1 — синхронізація карток через `GET /api/cards`. Номери карток (CSN) 35 працівників у макеті відсутні; емулятор дає лише `card_count=1`. Чи потрібен імпорт карток із BioStar (`GET /api/cards`) у `f3d.access.card`? | менеджер, автор iot_sim | так, у v1.1: емулятор додає `GET /api/cards`; модуль — синхронізація карток | картки створюються вручну/не створюються; `card_count` на зв'язку |
| Q-04 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** два турнікети × вхід/вихід, `tna_key` лишається; в емуляторі — даними у v1.1. Прохідна: один зчитувач `ACR-IN` з `tna_key` (емулятор) чи два (вхід/вихід) на кожен із двох турнікетів макета? У макеті 2 турнікети, в емуляторі 1 двері `TURN-1` | замовник, монтажник, автор iot_sim | два турнікети × два зчитувачі (вхід/вихід), `tna_key` лишається; емулятор — `TURN-2` і `ACR-OUT` у v1.1 | `direction='tna'` на `ACR-IN`; `TURN-1` один; нові двері додаються даними без коду |
| Q-05 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** стандарт Odoo: відмітка = факт, понаднормові — пороги 20/10 хв. Правила робочого часу: ранній прихід (06:40 при зміні з 07:00) і пізній вихід рахувати як відпрацьовані (стандарт Odoo: так, з порогами `overtime_*_threshold`) чи «обрізати» відмітки до графіка ± допуск? Нічні зміни? | замовник (HR) | стандарт Odoo: відмітка = факт, понаднормові — пороги компанії (20/10 хв); нічних змін у макеті немає | R-04/R-05 без обрізання; нічні — R-07 закриває за календарем дня входу (`stale_close`) |
| Q-06 | Відвідувачі: чи заводити їх у BioStar автоматично (`POST /api/users`, під стоп-краном), чи охорона робить це в BioStar, а Odoo лише зв'язує за `user_id`? Чи зберігати документ (серія/номер)? | замовник (охорона, юрист) | автоматично під стоп-краном; документ — не зберігати (лише «документ перевірено» прапорець) | обидва шляхи реалізовано; документів немає |
| Q-07 | Чи потрібне керування дверима з Odoo (пожежне розблокування, відчинити турнікет для відвідувача)? | замовник, менеджер | ні у v1 (апаратно FACP → BioStar); у v2 — `POST /api/doors/open` під `write_enabled` | лише читання стану |
| Q-08 | Строк зберігання журналу проходів (персональні дані): 90 днів чи за політикою замовника (до 1 року для розслідувань)? | замовник (юрист/HR) | 90 днів; для розслідувань — експорт охороною | `keep_days=90` |
| Q-09 | **Закрито 14.10 (рішення менеджера):** нові зони не створюємо; `zone_to` — зона-контейнер. Граф зон: вхід персоналу `EX-IN` відкривається в `Z-ASM` (макет); чи є в реальному цеху побутовий блок/коридор між входом і цехом (зона `Z-SOC`)? Двері 4 і 5 ведуть у приміщення без власних зон (`PAINT-STORE` у `Z-FAC`, серверна в `Z-MAINT`) — створювати зони? | менеджер, автор base | не створювати; `zone_to` = зона-контейнер, R-08 з домашньою зоною | як у §2.3 |
| Q-10 | Переглядач: де показувати «людей зараз» — у `zones[code].people_now` (розділ `zones` належить chains, у дельтах часткові записи) чи лише в `access.zones`? Нові рядки карток людини/зони робить автор viewer? | автор viewer | **закрито X-87 (X-23)**: обидва ключі і в повному payload, і в дельті (`employees`/`zones`/`infra.cards` — через `deep_merge`, `access` — цілком); картки — автор viewer за CA-05 | SPEC R-12 п. 7 |
| Q-11 | Сигнали `access/*` у telemetry: підтвердити сигнатуру `_f3d_ingest(readings, src)` і що каталог (iot_sim Додаток A 647–653) має `module='access'` (CT-09: префікс `access/` не згаданий) | автор telemetry | `access/*` → `module='access'`; `_f3d_ingest` приймає `text` для `kind='event'` | **закрито SPEC telemetry** (M-03 `_f3d_ingest(readings, src='module', collector=None)`, R-15 `access/*` → `access`); публікуємо лише коли `'f3d.signal' in env`; сигнали створює міст `factory3d_access_telemetry` (**X-33**); архівний/видалений сигнал — DEBUG |
| Q-12 | **Закрито 14.10 (рішення менеджера):** невідомий `user` → подія без `name`; `POST /api/users` — v1.1. Емулятор: `user_id` відвідувачів (`V-…`) і прохід користувача, якого немає в `GET /api/users` (сценарій `access_event` з довільним `user`) — чи віддає `user_id.name`? Чи підтримує `POST /api/users` (для ТК відвідувача) | автор iot_sim | `access_event` з невідомим `user` → подія з `user_id.user_id` і без `name`; `POST /api/users` у v1.1 | ТК-07 (відвідувач) — ручне введення `user_id`; ТК-08 (блокування) очікує 405 |
| Q-13 | **Закрито 14.10 (рішення менеджера):** так: fire_safety надає CF-02 (префікс `f3d.fire.passage.source.`) і CF-06 `_f3d_is_active_at`. `factory3d_fire_safety`: знаходити джерела CF-02 за префіксом імені `f3d.fire.passage.source.` (access не може успадкувати модель fire без залежності) і надати `f3d.fire.drill._f3d_is_active_at(ts) -> bool` для прапора «навчання триває» (fire Q-15) | автор fire_safety | так (CA-09, A-24) | M-16 і `_f3d_drill_active` реалізовані; без методу у fire — `False` |
| Q-14 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** у v1 блокування лише в Odoo; запис у BioStar — після перевірки на тестовому сервері замовника. Формат блокування картки в BioStar 2: `PUT /api/users/{id}` з `cards[].is_blocked` чи окремий ендпоінт блокування/чорного списку | замовник, Suprema | перевірити на тестовому BioStar замовника до вмикання `write_enabled` | запис за ПРИПУЩЕННЯМ (SPEC API-08), ручний шлях «Позначити синхронізованим»; на стенді — 405 |

### 5.2 Ризики

| Ризик | Наслідок | Пом'якшення |
|---|---|---|
| Формат `PUT /api/users/{id}` з `cards[].is_blocked` і `POST /api/cards` не підтверджений офіційною документацією (лише статті підтримки) | блокування картки на проді не спрацює | запис під стоп-краном, `sync_state='error'` з текстом; перевірка на тестовому BioStar замовника до вмикання `write_enabled`; ручний шлях «Позначити синхронізованим» |
| Подвійні відмітки: кіоск Odoo + СКУД одночасно (режим `barcode_manual` у компанії) | дубль/плутанина | R-04 крок 3 прив'язує СКУД-вхід до відкритої відмітки будь-якого режиму в межах 20 хв; рекомендація — вимкнути кіоск для працівників зі СКУД (§3) |
| Авто-вихід Odoo (`auto_check_out`) і R-07 закривають одну відмітку різними часами | неузгоджені години | R-07 лише для відкритих відміток попередніх днів; якщо Odoo закрив раніше — R-07 нічого не робить; у звітах `out_mode` показує, хто закрив |
| Втрата сесії/перезапуск BioStar під час пагінації | пропуск сторінки | курсор `last_event_ts` рухається лише після успішної обробки всього прогону; наступний прогін повторює вікно з перекриттям; дедуплікація |
| Прискорений час емулятора (`factor=60`) дає «стрибки» подій (iot_sim §9.4) | події з майбутнім `datetime` відносно `now` Odoo | вікно `until = now + 5 хв` допуск; події з `ts > now + 5 хв` зберігаються, але відмітки з майбутнім `check_in` не створюються (`attendance_action='future'`), обробляються наступним прогоном (R-15) |
| Персональні дані в журналі (ім'я + час проходу) | вимоги захисту ПД | мінімум полів, ретенція, групи, `keep_raw=False`, Q-08 |
| Велика кількість дверей на проді (не 5) без зон | люди «зникають» із зон | двері без `zone_to` не змінюють зону (лише журнал); звіт «Двері без зон» у формі сервера |

## 6. План сборки агентами

Межі файлів жорсткі; спільні файли (`__init__.py`, `__manifest__.py`, `security/*`, `data/ir_config_parameter.xml`,
`views/menus.xml`) пише W0, інші воркери лише додають рядки у свої блоки (позначені коментарями `# W1`…).

| Воркер | Файли | Здає | Залежить від |
|---|---|---|---|
| W0 каркас | `__manifest__.py`, `__init__.py`, `models/__init__.py`, `security/f3d_access_security.xml`, `security/ir.model.access.csv`, `data/ir_config_parameter.xml`, `data/ir_cron.xml`, `data/neutralize.sql`, `views/menus.xml`, `tests/__init__.py`, `tests/common.py`, `tests/fixtures/*.json` (відповіді P-10), `README.md`, `CHANGELOG.md` | модуль встановлюється порожнім; меню «Доступ»; групи; параметри; крони (вимкнені до W2) | SPEC §0, §1, §3 (меню), §4, §5.1, §6 |
| W1 клієнт і сервер | `tools/biostar_client.py`, `tools/event_codes.py`, `tools/dates.py`, `tools/params.py`, `models/f3d_access_server.py`, `models/f3d_access_device.py`, `models/f3d_access_door.py`, `models/f3d_access_user_link.py`, `views/f3d_access_server_views.xml`, `views/f3d_access_device_views.xml`, `views/f3d_access_door_views.xml`, `views/f3d_access_user_link_views.xml`, `tests/test_client.py`, `tests/test_server.py`, `tests/test_sync.py` | M-01…M-04; R-01, R-09, R-11, R-15, R-16, R-19; AC-01…AC-14 | W0 |
| W2 події й відмітки | `models/f3d_access_event.py`, `models/hr_attendance.py`, `models/hr_employee.py`, `models/f3d_zone.py`, `models/f3d_access_presence.py`, `models/fire_passage_source.py`, `wizard/event_reprocess_wizard.py`, `views/f3d_access_event_views.xml`, `views/f3d_access_presence_views.xml`, `views/hr_attendance_views.xml`, `views/hr_employee_views.xml`, `views/f3d_zone_views.xml`, `wizard/event_reprocess_wizard_views.xml`, `tests/test_events.py`, `tests/test_attendance.py`, `tests/test_presence.py` | M-05, M-08…M-10, M-13, M-14, M-16; R-02…R-08, R-10, R-17, R-20, R-21; AC-15…AC-38 | W1 |
| W3 картки й відвідувачі | `models/f3d_access_card.py`, `models/f3d_access_visitor.py`, `views/f3d_access_card_views.xml`, `views/f3d_access_visitor_views.xml`, `tests/test_cards.py`, `tests/test_visitors.py` | M-06, M-07; R-13, R-14; AC-39…AC-48 | W1, W2 |
| W4 провайдер, налаштування, хуки | `models/viewer_provider.py`, `models/res_config_settings.py`, `models/telemetry_bridge.py`, `hooks.py`, `data/f3d_access_server_data.xml`, `data/f3d_access_device_data.xml`, `data/scene_home_zones.csv`, `views/res_config_settings_views.xml`, `tests/test_viewer_provider.py`, `tests/test_settings.py`, `tests/test_hooks.py`, `tests/test_security.py`; міст `factory3d_access_telemetry/*` (SPEC §0) | M-11, M-12, M-15, M-17; R-12 (payload і дельта), R-18; SPEC §5.2–§5.5; AC-49…AC-69 | W2, W3 |
| W5 стенд і ТК | `tests/stand/*` (pytest -m stand проти compose iot_sim + Odoo), `docs/modules/factory3d_access/DEPLOY_TEST.md`, `TEST_REPORT.md` | ТК-01…ТК-10, ТБ-01…ТБ-08, ТП-01…ТП-04, DEPLOY_TEST | W4 |

Порядок злиття: W0 → W1 → W2 → W3 → W4 → W5. Кожен воркер здає зелені тести своїх файлів
(`odoo-bin -d test -i factory3d_access --test-tags /factory3d_access:<TestClass> --stop-after-init`) і не чіпає
чужих тестів. Після W4 — повний прогін `--test-tags f3d_access` на чистій базі й на копії демо; після W5 — стенд.

## 7. Рішення автора (A-xx)

| ID | Рішення | Обґрунтування | Що змінює відносно каркаса/завдання |
|---|---|---|---|
| A-01 | Коди пристроїв — `ACR-IN`, `ACR-ELEC`, `ACR-CHG`, `ACR-PAINT`, `ACR-SRV`, двері `TURN-1` (макет `plant/infra.py:DOOR_READERS`, iot_sim §8.12), а не `ACC-*`/`TURN-*` із завдання менеджера; `f3d.access.device.code`/`f3d.access.door.code` — власні Char-поля (не домішка), бо в сцені окремих об'єктів немає (рідери — частини мешів `ACCESS`/`TURNSTILES`); «Показати в 3D» — через `equipment_id.action_f3d_show()` або зону | джерело істини — макет | завдання: `ACC-*` → `ACR-*` |
| A-02 | Жодного плагіна колектора: REST-клієнт у `tools/biostar_client.py` усередині модуля, виклики з кронів (`requests`, тайм-аути 5/30 с) | каркас §6.5 рядок `biostar2`: «опитування REST прямо з Odoo, без колектора»; запити короткі, стан у БД | рядок таблиці §6.5 реалізовано як код Odoo, пакет `collector/plugins/biostar2.py` не створюється |
| A-03 | Зв'язок BioStar `user_id` ↔ працівник: `barcode` (емулятор API-42: `user_id = barcode`), потім `f3d_alias`, потім `f3d_code` без дефісів, потім ручний; збіг за іменем заборонено (імена в демо повторюються — base Додаток B) | README «бейдж = код у сцені без дефісів» | — |
| A-04 | Відмітки створюють лише двері з `is_perimeter=True`; внутрішні двері — тільки зона/журнал | інакше кожен вхід у щитову закривав би відмітку | — |
| A-05 | Граф зон задано на дверях (`zone_from_id`, `zone_to_id`), напрямок — на пристрої (`in`/`out`/`tna`); зони дверей 2–5 виведені з положення зчитувачів (стіна між двома зонами або приміщення всередині зони, A-23); `TURN-1` веде з `Z-KPP` у `Z-ASM`, далі домашня зона | модель даних BioStar: двері мають entry/exit device | завдання: «пристрій: зона з → в» → двері: зона з → в, пристрій: напрямок |
| A-06 | Одна відмітка на пару вхід/вихід (стандарт Odoo — кілька відміток на день); обідній вихід через турнікет дає 2 відмітки; злиття коротких виходів — параметр `merge_gap_min` (0 = вимкнено) | стандарт `hr_attendance` рахує `worked_hours` сумою; ТОВ не вимагало іншого (Q-05) | — |
| A-07 | Присутність/зона зберігаються на `hr.employee` (`present`, `zone_id` ефективна, `zone_since`, `zone_door_id`), а не обчислюються з подій при кожному запиті; «повернення з технічного приміщення» після `dwell_min` робить крон 5 хв; `f3d.zone.f3d_people_now` — `read_group` | kanban за зонами потребує збереженого поля для групування; події можуть бути видалені ротацією | дельта переглядача несе ці поля (`employees[code]`, `zones[code].people_now`) через `deep_merge` (SPEC R-12 п. 7, X-87) |
| A-08 | Антипрохід: апаратний (6405/6406) — тип `denied`; програмний — вхід уже присутнього → `apb_suspect=True` без нової відмітки; жодних блокувань в Odoo | Odoo — облік, не контролер | — |
| A-09 | Біометрія: лише `face_count`/`finger_count` з `GET /api/users` → `has_face`/`has_finger` (Boolean); `photo_exists` і `raw` ігноруються; `keep_raw=False` | захист ПД; вимога завдання | — |
| A-10 | Пагінація за `datetime` BETWEEN (вікно з перекриттям) + `offset`/`hint` (`paging_mode`) + дедуплікація за `biostar_id`; курсор `last_event_ts` = максимальний `datetime` обробленого прогону | розбіжність емулятора й статті Suprema (Q-01); будь-який режим безпечний завдяки дедуплікації | — |
| A-11 | Пароль BioStar зберігається відкрито в `ir.config_parameter` (admin-only), не хешується; `neutralize.sql` стирає | для `login` потрібен сам пароль; хешування неможливе | каркас §5 «токени» — тут логін/пароль |
| A-12 | `uninstall_hook` не зберігає події/картки/відвідувачів (видаляються з таблицями); відмітки лишаються | бізнес-дані для інших модулів — лише відмітки (стандартна модель) | — |
| A-13 | `in_mode`/`out_mode` розширені значенням `biostar` через `selection_add` (`ondelete='set default'`), окремого поля «джерело» немає | стандартні звіти Odoo групують за `in_mode` | завдання «джерело подія, пристрій» → `in_mode` + `f3d_in_event_id/f3d_in_device_id` |
| A-14 | Картка макета «146 працівників · 3 відвідувачі», «312 проходів» — не копіюються як статика; лічильники рахуються з подій (на макеті 35 і 0) | «усе, що є в макеті, має з'явитися в Odoo» — як живі лічильники, не як числа | — |
| A-15 | Домашня зона працівника `f3d_home_zone_id` — нове поле модуля (не base), заповнюється хуком з РЦ і `scene_home_zones.csv` | потрібна лише СКУД/евакуації; base не чіпаємо (каркас §3: поле додає модуль-власник функції) | — |
| A-16 | Меню в «Відвідуванні»: «Проходи СКУД» під `menu_hr_attendance_reporting` (sequence 20) і «Сервери BioStar» під `menu_hr_attendance_configuration` (sequence 50); блок налаштувань у `app name="hr_attendance"` | HR працює у своєму застосунку | X-89: блок лишається тут; пункт «Налаштування СКУД» під `factory3d_base.menu_f3d_config` (sequence 70) лише відкриває налаштування «Відвідування» (`context={'module': 'hr_attendance'}`) |
| A-17 | «Люди по зонах» — SQL-представлення `f3d.access.presence` (працівники + відвідувачі); поля присутності продубльовано в `hr.employee.public` | охорона без `hr.group_hr_user` не читає `hr.employee` (Odoo 19 `_check_private_fields`); один kanban для працівників і відвідувачів | додано M-14, M-08a (SPEC) |
| A-18 | «Перевірити з'єднання» (лише `group_f3d_admin`) працює і при `read_enabled=False`, окремою сесією | перевірка доступу до вмикання опитування на проді | — |
| A-19 | Провайдер переглядача — `AbstractModel` без `_inherit` (інтерфейс viewer M-01, пошук за префіксом імені) | viewer не є залежністю; `_inherit` на відсутню модель зламав би установку | уточнює «опційно» з §2.1 |
| A-20 | `max_shift_h=16`: вихід у межах 16 год закриває відмітку через північ; довше — R-07 | нічна робота без втрати відмітки; 16 год — поріг фільтра «Errors» `hr_attendance` | Q-05 «що робимо тим часом» |
| A-21 | Провайдер читає присутність через `sudo()` лише нечутливих полів; імена — тільки охороні | `f3d_access_last_event_id` (група охорони) не входить у `hr.employee.public`; `f3d_code` там є з base M-10a (X-09) | — |
| A-22 | Хук засіває присутність із 35 відкритих демо-відміток, відмітки не змінює | інакше провайдер (170) обнулив би `present` провайдера `people` і 3D-демо спорожніло б | FR-17, §2.8 |
| A-23 | Зона пристрою — з data (зона «з» дверей), не `zone_at` | 3 з 5 зчитувачів на стінах у зазорах між зонами | §2.3, §2.8 |
| A-24 | Відповідь на fire CF-02 — `f3d.fire.passage.source.access` (`_f3d_priority=10`) і прапор навчання `_f3d_is_active_at` (CA-09) | модулі не залежать один від одного; fire Q-10, Q-15 | Q-13 |
| A-25 | `dwell_min=30` для всіх внутрішніх дверей, включно з DOOR-PAINT/DOOR-SRV | з `0` комірник після складу ЛФМ лишався б у `Z-FAC` до виходу | §2.3 (було 0) |
| A-26 | Запізнілі події (старші за останню оброблену подію людини) — лише журнал (`late`) | порядок доставки не гарантований (Q-02); стандарт відхилив би перетин відміток | — |
| A-27 | Класифікація кодів за `code >> 8` | iot_sim ARCH Q-13 / Додаток A («4096/4864») і SPEC iot_sim §8.12 («4102/4867») розходяться | — |
| A-28 | Сигнали телеметрії без `user_id` (`text` = «код двері») | `f3d.signal` читає кожен `group_f3d_user` | уточнює FR-15 |
