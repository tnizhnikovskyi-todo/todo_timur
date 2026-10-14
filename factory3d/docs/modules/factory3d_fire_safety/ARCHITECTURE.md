# factory3d_fire_safety — технічне рішення

Версія 0.1 · 14.10.2026 · автор: агент-архітектор модуля (хвиля 2) · статус: **чернетка на погодження**.
Каркас: `docs/ARCHITECTURE.md` (далі «каркас»: §3 залежності, §5 конвенції, §6.2 зони, §6.3 паспорти,
§6.4 телеметрія, §6.5 плагіни зі зміною менеджера «`bacnet_ip` належить `factory3d_telemetry`», §6.6 P-09,
§6.7 переглядач, §6.8 заявки ТО, рішення **D-07** «жодних записів у прилад», §9 питання 3).
Специфікація: `docs/modules/factory3d_fire_safety/SPEC.md`. Спирається на контракти `factory3d_base`
CB-01, CB-03, CB-04, CB-07, CB-08, CB-09, CB-10, CB-12; `factory3d_viewer` M-01 (хук провайдера), M-03
(шина), API-03 (дельта), Додаток A.13 (структура `fire`/`evacuation`); `factory3d_telemetry` CT-01…CT-07,
CT-09 (ARCHITECTURE telemetry §2.1, SPEC telemetry пишеться паралельно — розбіжності в Q-06…Q-08);
«документацію вендора» `factory3d_iot_sim` SPEC §8.11 (P-09), §8.4.1 (unit 85), §9.1 R-25…R-27, §9.3
S-07/S-08, Додаток A (сигнали 603–646). Рішення автора — **A-xx** (§7), відкриті питання — **Q-xx** (§5.1).

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора; `docs/оцінки` в репозиторії ще немає) |
|---|---|---|
| ТР | цей документ + SPEC.md | 20 |
| Архітектура | погодження A-xx/Q-xx з менеджером і авторами telemetry/iot_sim/viewer/access | 8 |
| Розробка | Odoo-модуль `odoo_addons/factory3d_fire_safety` (моделі 12, представлення 20, генератор даних, провайдери, звіт) | 72 |
| Тестування | юніт-тести (норми, маршрути, мапінг BACnet, події, навчання), ТК проти емулятора, безпека (жодного запису), DEPLOY_TEST | 36 |
| Інструкція | §4 цього документа + README модуля + CHANGELOG | 6 |
| **Разом** | | **142** |

Факти про тестовий сервер timur-o19demo, база `odoo` (перевірено 14.10.2026, лише читання): Odoo 19.0+e;
`maintenance.equipment` — 208, з них у категорії «Пожежна безпека» 41 (`FACP-1`, `FA-MCP`, `FA-SND`,
`FA-FLAME`, `SPARK-1`, `FA-<зона>` ×32, `FA-BOILER`, `SMOKE-VENTS`, `SMOKE-CTRL`, `EXITS`), `SPRINKLERS`
у категорії «Безпека» (id 49, сигнал `equipment/SPRINKLERS/pressure_bar` = 7,25 бар, поріг `< 6.5`), `LPS`
у «Електропостачання»; сигнал рівня 0 `fire/groups/FA-FAC/dust` (id 189) = 86,1 % (`drift`, поріг `> 90`,
обладнання `FA-FAC` id 51), заявка ТО id 5 «Очистити сповіщувач 2.FAC.07 (запиленість 82 %)» на `FA-FAC`
(стадія «New Request», `corrective`, команда «Служба головного механіка» id 2); `hr.attendance` — 35 записів
(усі 35 працівників із бейджами, `check_in` 12.10.2026 06:58–07:00 за Києвом, `check_out` порожній,
`in_mode='manual'`); стадії ТО: New Request, In Progress, Repaired (done), Scrap (done); `res.users` tz
`Europe/Kyiv`. Моделей `f3d.*` ще немає (хвиля 1 не встановлена) — усі кількості нижче рахуються за
data-файлами base і макетом.

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що є в макеті

| Джерело | Що саме | Як використовується |
|---|---|---|
| `plant/fire.py` | `ZONE_DETECTOR` (тип сповіщувача на зону: `multi` 9 зон, `smoke` 24, `heat` котельня), `LOOPS` (4 шлейфи за X: 0–42, 42–92, 92–122, 122–151), `detectors()` (сітка `s = min(smoke_spacing, 2·smoke_wall)` = 8,8 м, `nx = ceil(W/s)`, `ny = ceil(D/s)`, `_nudge` обходить ферми/прогони/дахові установки), `call_points()` (36 ручних), `sounders()` (41 оповіщувач), `max_mcp_distance()` (сітка 2 м → 26,9 м), `FLAME` (3 полум'я, (46/64/76, 71,8, 5,0)), `SPARK_DETECTORS` (4), `SPARK_EXTINGUISH` (3), `SPARK_PANEL` (52,0, 71,75), `FACP_POS` (97,2, 58,25), `Z_DET` 8,85, `Z_BOILER` 4,35, `fire_data()` (loops, groups, totals, events), `FIRE_ROLES` | генератор `tools/gen_data.py` → data-файли (M-02…M-04); правила R-01…R-04; адреси LSP (Додаток A SPEC) |
| `plant/fire_rules.json` | 10 норм: `smoke_spacing_6_12m` 8,8 м, `smoke_wall_6_12m` 4,4 м, `heat_spacing` 6,4 м, `mcp_spacing` 30 м, `sounder_level` 65 дБА, решта `null` з `ref`/`note`/`sources` (ДБН В.2.5-56:2014 зі Зміною № 2, ДСТУ-Н CEN/TS 54-14:2009, VdS 3845) | довідник норм `f3d.fire.norm` (M-08), формули R-01…R-04, тексти посилань у звітах |
| `plant/evacuation.py` | `EXITS` (12: `EX-S1…S6`, `EX-N1…N5`, `EX-IN`), `WALLS`, `STEP` 0,5 м, `DOOR_W` 1,2 м, `compute()` (Дейкстра по сітці) → `evac_routes.json` | виходи (M-09), маршрути (M-10) — імпорт готового `evac_routes.json` (A-05) |
| `plant/evac_routes.json` | 32 маршрути зона → вихід (`exit`, `length`, `path`), `max_distance` 45,3 м, `worst_point` (32,25, 33,75) | дані M-10; R-05 (норма довжини) |
| `plant/evac_rules.json` | `evac_distance_prod_B` 240 м (ДБН В.2.2-27:2025 табл. 8.2), `evac_exits_min` 2 (L = 1,5·√П), `exit_width_min` 1,0, `door_width_min` 0,8, `smoke_exhaust_required` 1, `smoke_vent_area` 1,5 м² Aa/400 м², `smoke_zone_max_area` 1600 м², `lightning_class` 2, `eyewash_required` null, `pv_roof_fire` null | довідник норм (M-08); R-05…R-09 |
| `plant/odoo_demo.py:evacuation()` (рядки 707–735) | `drill_origin` `FA-CNC`, `drill_zone` «Присадка», `drill_detector` `2.CNC.05`, `norm_distance` 240, `norm_alt` 50 (п. 8.2.11), `drill_steps` 8 кроків (t = 0, 3, 3, 6, 9, 12, 15, 20 с; `who`, `text`) | шаблон навчальної тривоги (M-11c), демо-навчання, секція `evacuation` payload |
| `plant/infra.py` | `SMOKE_ZONES` (8 димових зон SZ-1…SZ-8 ≤ 1 600 м²), `CURTAINS` (7 завіс, низ 7,9 м), `smoke_zone_vents()` (потреба `n = ceil(area/400·1,5/1,02)`, разом 44 люки на лініях `VENT_LINES`), `SMOKE_PANEL` (102,6, 58,37), `VENT_AA` 1,02 | димові зони (M-07), люки як пристрої (M-04, A-10), R-09 |
| `plant/site2.py` | `build_evacuation()` (двері 1,2 м, антипаніка, покажчик «Вихід», маршрути `EVAC-<зона>`), `build_smoke()` (люки `SV-01…44`, 5 щитів D+H `n = ceil(44·7,5/80)`, завіси), `build_lightning()` (LPS — лише довідка) | коди 3D-об'єктів для «Показати в 3D»: `EXITS`, `EVAC-<зона>`, `SMOKE-VENTS`, `SMOKE-CTRL`, `LPS` |
| `plant/site.py:build_fire()` (1271–1335) | сповіщувачі — один 3D-об'єкт на зону `FA-<зона>`; ручні — `FA-MCP`; оповіщувачі — `FA-SND`; полум'я — `FA-FLAME`; прилад `FACP-1`; іскрогасіння `SPARK-1` | «Показати в 3D» для пристрою показує груповий об'єкт (Q-09 — маркери окремих пристроїв) |
| `plant/equipment_specs.json` | паспорти `facp` (FC726-ZA, 1 512 адрес, 4 кільця, журнал 13 000 подій), `multi_detector` OOH740, `smoke_detector` OP720, `heat_detector` HI720 (A2S/A2R ≤ 6 м), `flame_detector` SharpEye 40/40C-I (100°×95°, 65 м), `mcp` FDM225-RP, `sounder_beacon` FDS226-RW (75–99 дБА, W-3.2-10), `spark_detection` GreCon BS 7 (FM 1/8, HUNTER IEM, 4–6 м до форсунки, гасіння ≈ 5 с), `smoke_vent` LAMILUX F100 (Aa 1,02 м², < 60 с), `smoke_control` D+H CPS-M1-080-1010-B (80 А, 72 год), `exit_door` Hörmann STU + `panic_bar` dormakaba PHA 2000, `fire_hydrant_cabinet` (лише довідник) | через base CB-07/CB-08: `f3d_get_num`, тексти карток |
| `dist/odoo_demo.json` ключі `fire`, `evacuation` | `fire.rules` (10), `fire.loops` {1: 64/10/11/0/0, 2: 68/10/13/3/4, 3: 34/7/7/0/0, 4: 46/9/10/0/0}, `fire.groups` (33 `FA-*`: zone, kind, n, spacing, area, loop, state; `FA-FAC` `warn`, `dust` 0,825, `maintenance_request` `MR/00036`), `fire.totals` {detectors 212, mcp 36, sounders 41, mcp_max_m 26,9, flame 3, spark_detectors 4, state «Норма, 1 попередження», sprinkler «…в режимі очікування»}, `fire.events` (4), `evacuation.*` (A.13 viewer) | контракт payload (CF-01); очікувані кількості §2.8; демо-події (M-05) |
| `viewer/index.html` | шар `fire` «Пожежна сигналізація» (рядок 428), `fireSummary()` (2243), `fireHtml()` (2254: картки зони/приладу/MCP/SND/FLAME/SPARK-1 — зона, тип, кількість, шлейф, стан, попередження, заявка; таблиця шлейфів; журнал приладу; текст норм), «Потребує уваги» з `fire.groups[*].state != ok` (1453), `startDrill()/renderDrill()` (2561–2605: маршрути, маркери виходів, блимання `FA-SND`, `SMOKE-VENTS`, зони й `EXITS`, кроки з `drill_steps` за секундами, таблиця маршрутів із нормами) | що саме має віддавати провайдер, щоб картки не змінились (CF-01); сценарій навчання в 3D (FR-15) |
| `README.md` «Пожежна сигналізація», «Евакуація, димовидалення, блискавкозахист» | опис системи, норми, застереження (аспіраційні сповіщувачі > 8 м, акустичний розрахунок, збіг двох сповіщувачів для АСПГ, іскрогасіння — страхова вимога) | тексти підказок у формах; Q-11 (README пише 192 сповіщувачі, макет дає 212) |
| `factory3d_iot_sim` SPEC §8.11, Додаток A | BACnet device 200: LSZ:0 панель, LSZ:1…33 зони (порядок = `fire.groups`), LSP id = `loop·10000 + ordinal·100 + nn` (`2.FAC.07` → 21607, `2.CNC.05` → 21405), AV:<id> Contamination, BI:1…4 шлейфи, AV:1/2/3 лічильники, BI:10 сирени, BI:11 передача на пульт, MSV:1 стан; ADAM-6050 unit 85 (DI0–DI6, DO0/DO1, HR 40001); R-25 (хронологія навчання 0/3/6/9/12/20 с), R-26 (іскра 0,6 с/2 с), R-27 (клапани 60 с); сценарії `fire_drill`, `spark`; усі записи → `write-access-denied` | адреси сигналів (SPEC Додаток B), стенд ТК-01…ТК-08 |
| Odoo стандарт | `maintenance` (заявки, стадії `done`, команди), `hr_attendance` (`check_in`/`check_out`/`in_mode`), `mail` (чаттер, активності, вкладення), `web` (звіт QWeb) | заявки через telemetry CT-05; журнал навчань; сповіщення охороні |

### 1.2 Ролі й сценарії використання

| Роль (групи) | Що робить | Де в меню |
|---|---|---|
| Інженер з пожежної безпеки (`group_f3d_user` + `factory3d_fire_safety.group_f3d_fire_drill`) | дивиться стан приладу, зон, пристроїв, журнал подій; перевіряє відповідність розстановки й маршрутів нормам (звіт); планує, проводить і закриває навчальні тривоги (кроки, люди, час евакуації, висновки, вкладення) | Завод 3D → Пожежна безпека → Огляд / Зони / Пристрої / Журнал / Евакуація / Навчальні тривоги |
| Охорона, черговий (`group_f3d_user`) | бачить дашборд стану (норма/тривога/несправність/вимкнення/тест/зв'язок), отримує активність «Пожежна тривога» на `f3d.fire.panel`, відкриває 3D із підсвіткою зони | Огляд; 3D-переглядач (шар «Пожежна безпека») |
| Головний механік (`maintenance.group_equipment_manager`) | отримує заявки ТО з несправностей, запиленості, втрати зв'язку, несправностей іскрогасіння/димовидалення; закриває їх після обслуговування монтажником | Обслуговування → Заявки |
| Монтажник сигналізації (зовнішній, без доступу в Odoo) | обслуговує прилад; надає дозвіл на читання BACnet (умова проду, D-07); переводить прилад у тест під час навчань | — (його дії видно в журналі як події `test`/`disabled`/`reset`) |
| Інженер АСУ (`group_f3d_manager`) | заводить/перевіряє джерело BACnet приладу та ADAM-входи (адреса в `f3d.source`), пороги запиленості, норми, параметри навчань; **не має** способу увімкнути запис | Завод 3D → Телеметрія → Джерела; Пожежна безпека → Налаштування |
| Адміністратор (`group_f3d_admin`) | стоп-кран читання, `neutralize.sql`, міграція даних, параметри | Налаштування → Завод 3D |
| Переглядач/кіоск | бачить живі стани зон, тривоги, сценарій навчання в 3D | 3D-переглядач |

### 1.3 Функціональні вимоги

| ID | Вимога (перевірювана) |
|---|---|
| FR-01 | Модель `f3d.fire.panel` описує прилад `FACP-1` (код сцени, обладнання base, джерело BACnet `f3d.source` типу `bacnet_ip`, device 200) і обчислює стан `normal/prealarm/alarm/fault/disabled/test` з об'єктів LSZ:0 і MSV:1 та стан зв'язку `online/stale/lost` з часу останнього показання. |
| FR-02 | Модель `f3d.fire.loop` містить 4 шлейфи (межі по X з макета, лічильники пристроїв за типами, модулі) зі станом несправності з BI:1…4. |
| FR-03 | Модель `f3d.fire.zone` містить 33 зони виявлення `FA-*` ↔ `f3d.zone` (обов'язково) з номером LSZ, типом сповіщувачів, кроком, площею, шлейфом, кількістю пристроїв і станом `normal/prealarm/alarm/fault/disabled/test` з LSZ:n; попередження `warn` — із запиленості пристроїв. |
| FR-04 | Модель `f3d.fire.device` містить 343 пристрої (212 сповіщувачів, 36 ручних, 41 оповіщувач, 3 полум'я, 4 датчики іскор, 3 форсунки, 44 люки) з адресою `<шлейф>.<ЗОНА>.<nn>`, типом, координатами CB-04, паспортом (CB-07 через обладнання групи), станом, запиленістю; сигнали пристрою створюються лише за прапором `monitor` (A-02). |
| FR-05 | Модель `f3d.fire.event` веде журнал подій приладу й систем лише для читання: `alarm/prealarm/fault/dust/disabled/test/reset/comm/spark/smoke/sprinkler/loop/drill`; джерело — переходи станів сигналів (первинно) і BACnet-повідомлення (вторинно); дедуплікація за ключем; записи не видаляються користувачем. |
| FR-06 | Модель `f3d.fire.system` описує іскрогасіння `SPARK-1` (ADAM u85 DI0–DI3, лічильник), димовидалення `SMOKE-CTRL` (DI4–DI6; 44 люки, 5 щитів, 8 димових зон) і спринклери `SPRINKLERS` (тиск з telemetry u90 AI2) зі станом `ok/active/fault/battery/low_pressure`. |
| FR-07 | Правила розстановки за ДБН обчислюються з даних: потрібна кількість сповіщувачів на зону (R-01), покриття зони (R-02), найбільша відстань до ручного сповіщувача ≤ 30 м (R-03), рівень оповіщення (R-04); результат — поля відповідності на зоні/приладі та звіт. |
| FR-08 | Моделі `f3d.fire.exit` (12) і `f3d.fire.route` (32) зберігають виходи й найкоротші шляхи з макета; відповідність нормам (R-05 довжина ≤ 240 м або ≤ 50 м, R-06 ≥ 2 розосереджені виходи, R-07 ширина дверей ≥ 0,8 і шляху ≥ 1,0 м) показується полями й зведеним звітом PDF «Перевірка евакуації». |
| FR-09 | Модель `f3d.fire.smoke.zone` (8) перевіряє площу ≤ 1 600 м² і кількість люків за орієнтиром Aa (R-09). |
| FR-10 | Несправність зони/шлейфу/приладу, запиленість > 90 %, несправність іскрогасіння або щита D+H створюють `maintenance.request` за правилом каркаса §6.8 через telemetry CT-05 (`alarm_states`/пороги/`alarm_title` на сигналах; одна відкрита заявка на сигнал); модуль сам заявок не створює, крім втрати зв'язку (FR-12). |
| FR-11 | Справжня тривога (`alarm`) **не** створює заявку ТО: пишеться подія рівня `alarm`, на `f3d.fire.panel` ставиться активність «Пожежна тривога: зона …» користувачам групи охорони (`factory3d.fire_safety.alert_group`), у шину йде подія для переглядача; скидання приладу закриває активність. |
| FR-12 | Втрата зв'язку з приладом (жодного показання довше `comm_lost_after_s`) → стан `lost`, подія `comm_lost`, заявка ТО на `FACP-1` (одна відкрита), у payload `fire.totals.state = "Зв'язок із приладом втрачено"`; відновлення → подія `comm_restored`, стан `online`. |
| FR-13 | Модель `f3d.fire.drill` веде навчальну тривогу: план (дата, зона, сповіщувач, спосіб: емулятор/тест приладу/настільне), старт/стоп, кроки з шаблону макета з плановим і фактичним часом (авто-відмітка за сигналами), список людей на об'єкті на момент старту і їхні виходи (hr.attendance або хук access), час евакуації, перелік тих, хто не вийшов, перекличка, висновки, результат, вкладення, звіт PDF. |
| FR-14 | Перехід LSZ у `test-alarm` без запланованого навчання у вікні ± `drill_match_window_min` створює навчання автоматично (`origin='panel'`), а наявне заплановане — стартує. |
| FR-15 | Провайдери переглядача `f3d.viewer.provider.fire` (130) і `.evacuation` (140) віддають розділи `fire` і `evacuation` у форматі viewer A.13 (статика з моделей + живі стани), дельти — через `f3d.viewer.event._notify`; активне навчання публікується як `evacuation.drill_active`. |
| FR-16 | Меню «Завод 3D → Пожежна безпека» (`sequence=85`, CB-09): Огляд, Зони сигналізації, Пристрої, Журнал подій, Системи, Евакуація (Виходи, Маршрути, Димові зони, Звіт), Навчальні тривоги, Норми; дашборд стану — kanban зон за станом і статбокси приладу. |
| FR-17 | Права: читання всього — `group_f3d_user`; створення/редагування навчань — `group_f3d_fire_drill`; норми, параметри, прапори `monitor` — `group_f3d_manager`; стоп-кран — `group_f3d_admin`; жодна група не має дії, що пише в пристрій. |
| FR-18 | Параметра `factory3d.fire_safety.write_enabled` не існує; джерела модуля створюються з `write_enabled=False` і прапором `f3d_fire_readonly=True`; спроба увімкнути запис на такому джерелі, на сигналі `module='fire_safety'` або створити `f3d.command` для нього → `ValidationError` незалежно від групи, включно з `sudo`. |
| FR-19 | Стоп-кран `factory3d.fire_safety.read_enabled` (умовчання за CB-10) вимикає обробку сигналів (стан приладу й зон не оновлюється, події не пишуться, провайдер віддає статику з позначкою); `neutralize.sql` вимикає крони, джерела модуля, прапор і прив'язку до емулятора. |
| FR-20 | Data-файли генеруються з макета (`tools/gen_data.py`): 4 шлейфи, 33 зони, 343 пристрої, 12 виходів, 32 маршрути, 8 димових зон, 3 системи, 20 норм, 52 сигнали, шаблон навчання (8 кроків); `post_init_hook` прив'язує 43 одиниці обладнання base, 4 демо-події, навчання-демо; повторний запуск нічого не дублює. |
| FR-21 | `res.config.settings` містить стоп-кран читання, `comm_lost_after_s`, пороги запиленості `dust_warn_pct`/`dust_alarm_pct`, `polymer_panels` (норма 50 м замість 240), `drill_time_limit_s`, `drill_auto_create`, `drill_match_window_min`, групу сповіщення, команду ТО; без `write_enabled`. |
| FR-22 | `f3d.zone` отримує поля `f3d_fire_zone_ids`, `f3d_fire_kind`, `f3d_fire_state`, `f3d_evac_route_id`, `f3d_evac_exit_code`, `f3d_evac_length_m` і статкнопку «Сигналізація». |
| FR-23 | Якщо встановлено `factory3d_iot_sim`, навчання з режимом «емулятор» запускає сценарій `fire_drill` через пульт (S-07) з параметрами зони/сповіщувача/тривалості і зберігає `run_ref`; без модуля кнопка прихована. |
| FR-24 | Персональні дані навчань (хто був на об'єкті, хто вийшов) видимі лише `group_f3d_fire_drill` і `hr.group_hr_user`; у звіті PDF — лише кількості, прізвища — за опцією; `neutralize.sql` відв'язує працівників від навчань на тестовій копії. |

### 1.4 Межі: що не входить

- Будь-який запис у прилад, модуль входу/виходу, щит D+H, пульт GreCon: ні команд, ні скидання, ні вимкнення зон, ні тесту — **ніколи** (D-07, FR-18). Навчальна тривога на реальному об'єкті запускається монтажником на приладі, Odoo лише спостерігає.
- Розрахунок найкоротших шляхів евакуації (Дейкстра по перешкодах) — лишається в макеті (`plant/evacuation.py`); Odoo імпортує результат і перевіряє норми (A-05). Розрахунок часу евакуації за ДСТУ 8828 (потокова модель) — не робиться (Q-03).
- Гасіння: спринклери лише стан тиску (сигнал telemetry); насосна станція, резервуари, пожежні крани й вогнегасники — позицій у макеті немає (Q-12).
- Блискавкозахист `LPS` — лише довідка на картці обладнання base; жодних моделей.
- Керування вентиляцією, дверима, шлагбаумами під час тривоги — апаратно від приладу (реле) та в модулях bms/access/yard; модуль лише фіксує кроки навчання за їхніми сигналами, якщо вони встановлені.
- Сповіщення e-mail/SMS — стандартні підписки чаттера й активності; окремого каналу немає.
- Аспіраційні сповіщувачі, акустичний розрахунок оповіщувачів, збіг двох сповіщувачів для АСПГ — застереження в підказках (README), не правила.
- Плагін `bacnet_ip` колектора — належить `factory3d_telemetry` (зміна менеджера до §6.5); тут — лише вимоги до нього (§2.4, Q-07) і адреси.

## 2. Технічна реалізація

### 2.1 Місце в системі

`depends`: `factory3d_telemetry` (через нього `factory3d_base`, `maintenance`, `mail`), `hr_attendance`.
Optional (перевірка `'<model>' in env`/`ir.module.module`): `factory3d_viewer` (провайдери, шина, «Показати
в 3D»), `factory3d_iot_sim` (кнопка запуску `fire_drill`), `factory3d_access` (хук проходів, фаза 4),
`factory3d_bms`/`factory3d_machine_connect` (авто-відмітка кроків навчання «вентиляція зупинена»/«верстати
зупинені» за їхніми сигналами, якщо вони є в `f3d.signal`).

Контракти, які **задає** цей модуль (посилатися як `factory3d_fire_safety CF-xx`):

| ID | Контракт | Споживачі |
|---|---|---|
| CF-01 | Розділи payload переглядача `fire` і `evacuation` строго за viewer A.13 плюс додаткові ключі: `fire.panel` {code, state, state_text, comm, last_seen, alarms, faults, disabled, sounders, brigade}, `fire.groups[*].alarm_state` (сирий стан LSZ), `fire.groups[*].compliance` (`ok`/`warn`/`fail`), `fire.systems` {SPARK-1, SMOKE-CTRL, SPRINKLERS → {state, text, count_today, pressure_bar}}, `fire.devices` (лише за параметром `viewer_devices`, A-02), `evacuation.drill_active` {name, zone, detector, started, elapsed_s, steps_done} або `null`, `evacuation.compliance` {routes_ok, routes_total, worst, norm} | viewer (Q-09), кіоск |
| CF-02 | Хук `f3d.fire.passage.source` (AbstractModel): `_f3d_priority` (int), `_f3d_on_site(at: datetime) -> list[dict(employee_id, since, point)]`, `_f3d_passages(start, end) -> list[dict(employee_id, ts, point, direction)]`; модуль дає реалізацію над `hr.attendance` (пріоритет 100); `factory3d_access` реєструє свою (пріоритет 10) — береться реалізація з найменшим пріоритетом | access |
| CF-03 | Коди сигналів `fire/*` (52, SPEC Додаток B) і коди пристроїв `<шлейф>.<ЗОНА>.<nn>`; сигнали мають `module='fire_safety'`, `write_enabled=False`, джерела з `f3d_fire_readonly=True` | telemetry (CT-09), iot_sim (каталог), bms |
| CF-04 | Події шини `f3d.viewer.event._notify('f3d.fire.zone', [FA-коди], 'state')`, `_notify('f3d.fire.panel', ['FACP-1'], 'state')`, `_notify('f3d.fire.drill', [name], 'state')` | viewer |
| CF-05 | `f3d.fire.event` як журнал для читання іншими модулями (`kind`, `level`, `object_code`, `ts`); bms/access можуть посилатися на `event_id` у своїх журналах | bms, access, yard |

Що **бере** модуль: CB-01 (`f3d_code`, `search_f3d`, `action_f3d_show`), CB-03 (`f3d.zone`, `zone_at`,
`polygon`, `area_m2`), CB-04 (координати), CB-07/CB-08 (паспорти: `f3d_get_num('…')` — не потрібні для
правил, лише картки), CB-09 (меню 85), CB-10 (групи, `factory3d.base.environment`), CB-12 (габарити
будівлі 150×72×9 для сітки R-03); telemetry CT-01 (`f3d.source`, `f3d.signal`, `f3d.reading`), CT-03
(схема адреси `bacnet_ip` — узгодити, Q-07), CT-05 (заявки з порогів), CT-06 (`maintenance.request.f3d_*`),
CT-07 (провайдер 95 іде раніше; мої 130/140 перекривають `fire.groups[*].dust`), CT-09 (`fire/*` →
`fire_safety`); viewer M-01, M-03, API-03; iot_sim §8.11, §8.4.1, API-13 (S-07), §9.3.

### 2.2 Архітектурна схема

```
 мережа цеху / f3d_sim                                 docker compose поруч з Odoo
┌──────────────────────────────┐  BACnet/IP UDP 47808  ┌──────────── services/collector (telemetry) ─────────────┐
│ Siemens Cerberus PRO FC726   │◄── ReadProperty / ────│ plugins/bacnet_ip  (bacpypes3; readonly: write → помилка │
│ (емулятор: device 200)       │    SubscribeCOV       │   до мережі; LSZ/LSP/AV/BI/MSV → текст/число)            │
│  LSZ:0 панель, LSZ:1…33 зони │─── COV / Event ─────►│ plugins/modbus_tcp (ADAM-6050 unit 85: DI0–DI6, HR40001) │
│  LSP:<id> елементи, AV dust  │   Notification        │ core: буфер, push ≤ 5 с                                   │
│  BI:1…4 шлейфи, BI:10/11     │                       └───────────────┬──────────────────────────────────────────┘
│  MSV:1 стан                  │  Modbus TCP 502                       │ POST /f3d/telemetry/push, /event
│ GreCon BS 7 + D+H CPS-M1 ──► ADAM-6050 u85 (сухі контакти)           ▼
└──────────────────────────────┘                ┌──────────── Odoo 19 + factory3d_telemetry ────────────────────┐
   жодного пакета у зворотний бік:              │ f3d.source BACNET-FACP-1 (f3d_fire_readonly) · MB-U85-IO6      │
   write_enabled=False на джерелі й сигналах,   │ f3d.signal fire/* (52) → last_text/last_value/status          │
   f3d.command для fire/* → ValidationError     │ пороги/alarm_states → maintenance.request (CT-05)             │
                                                └──────┬──────────────────────────┬─────────────────────────────┘
                                                       │ хук зміни стану (Q-06)   │ крон-звірка 1 хв (fallback)
┌──────────────────────────────── factory3d_fire_safety ┴──────────────────────────┴─────────────────────────────┐
│ f3d.fire.panel ─1:4─ f3d.fire.loop ─1:N─ f3d.fire.zone (33, ↔ f3d.zone) ─1:N─ f3d.fire.device (343)            │
│ f3d.fire.system (SPARK-1, SMOKE-CTRL, SPRINKLERS) · f3d.fire.smoke.zone (8) · f3d.fire.norm (20)               │
│ R-10…R-14: стан панелі/зон/систем із сигналів → f3d.fire.event (журнал, дедуплікація) → активність охороні     │
│ R-01…R-09: норми (розстановка, MCP, виходи, маршрути, димові зони) → поля compliance, звіт PDF                 │
│ f3d.fire.exit (12) · f3d.fire.route (32) ← evac_routes.json                                                     │
│ f3d.fire.drill (+step, +person) ← шаблон макета; люди ← f3d.fire.passage.source (hr.attendance | access)      │
│ f3d.viewer.provider.fire (130) / .evacuation (140) → payload; f3d.viewer.event._notify → bus → 3D              │
│ iot_sim (optional): кнопка «Запустити на емуляторі» → f3d.sim.run (fire_drill, S-07)                           │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Потоки: (1) прилад → колектор (COV на LSZ/LSP/BI/MSV, опитування AV 600 с, ADAM 2 с); (2) колектор → Odoo
`push`; (3) telemetry оновлює `f3d.signal.last_*`, пороги → заявки; (4) модуль отримує зміни станів
(хук або крон) → стани моделей, події, активності, шина; (5) переглядач — дельта `fire`/`evacuation`;
(6) навчання: пульт iot_sim → емулятор (`fire_drill`) → прилад у `test-alarm` → той самий шлях (1)–(5).
Жодного потоку в напрямку Odoo → прилад не існує.

### 2.3 Нові й розширені об'єкти

| Об'єкт | Призначення | Пише | Читає |
|---|---|---|---|
| `f3d.fire.panel` (M-01) | прилад: код, обладнання, джерело, стан, зв'язок, лічильники, активна тривога | хук/крон R-10, R-12; дані | дашборд, провайдер, охорона |
| `f3d.fire.loop` (M-02) | шлейфи 1–4: межі X, лічильники, стан | дані; R-11 | форма приладу, provider `fire.loops` |
| `f3d.fire.zone` (M-03) | 33 зони виявлення: LSZ, зона цеху, тип, крок, площа, n, стан, відповідність R-01/R-02 | дані; R-11; R-01/02 (compute) | kanban/список, провайдер `fire.groups`, `f3d.zone` |
| `f3d.fire.device` (M-04) | 343 пристрої: адреса, тип, шлейф, зона, x/y/z, стан, запиленість, `monitor` | дані; R-11 (device-level), R-13 | список/форма, R-02/R-03, провайдер (`fire.devices` opt) |
| `f3d.fire.event` (M-05) | журнал подій лише для читання | R-14 (з переходів), M-17 (BACnet notify), навчання | журнал, картки, провайдер `fire.events` |
| `f3d.fire.system` (M-06) | іскрогасіння, димовидалення, спринклери | дані; R-13 | список/форма, провайдер `fire.systems` |
| `f3d.fire.smoke.zone` (M-07) | 8 димових зон: контур, площа, потреба люків, фактично, відповідність | дані; R-09 | Евакуація → Димові зони, звіт |
| `f3d.fire.norm` (M-08) | 20 норм (fire_rules + evac_rules): ключ, значення, одиниця, ref, note, sources | дані; менеджер | R-01…R-09, звіти, підказки |
| `f3d.fire.exit` (M-09) | 12 виходів: код, x, y, бік, ширина, обладнання `EXITS` | дані | маршрути, R-06/R-07, провайдер `evacuation.exits` |
| `f3d.fire.route` (M-10) | 32 маршрути: зона, вихід, довжина, шлях, відповідність R-05 | дані; R-05 | список, звіт, провайдер `evacuation.routes` |
| `f3d.fire.drill` (M-11) + `.step` (M-11a) + `.person` (M-11b) + `.template` (M-11c) | навчальні тривоги | інженер ПБ; R-15…R-18 | форма, звіт PDF, провайдер `drill_active` |
| `f3d.fire.passage.source` (M-12, AbstractModel) + `…hr_attendance` (M-12a) | хук проходів (CF-02) | — | R-16 |
| `f3d.zone` (+поля, M-13) | зв'язок зони цеху із сигналізацією та маршрутом | compute | форма зони base, viewer |
| `maintenance.request` (+поля, M-14) | `f3d_fire_event_id`, `f3d_fire_zone_id`, `f3d_fire_device_id` | R-14 (прив'язка після створення telemetry) | механік |
| `f3d.source`, `f3d.signal`, `f3d.command` (+перевірки, M-15) | заборона запису (FR-18) | — | — |
| `res.config.settings` (M-16) | параметри FR-21 | адміністратор/менеджер | модуль |
| `f3d.viewer.provider.fire`, `.evacuation` (M-17) | провайдери (FR-15) | — | переглядач |
| `f3d.push.handler.fire` (M-18) | обробник BACnet-повідомлень (маршрут `bacnet_event`, якщо telemetry його дає — Q-06) | — | R-14 |

### 2.4 Інтеграції

| P-xx / канал | Пристрої (коди) | Протокол, адреса на стенді (емулятор) | Напрямок | Частота | При недоступності |
|---|---|---|---|---|---|
| P-09 BACnet | FACP-1 (device 200, через роутер device 99, мережа 2; у проді — IP приладу/модуля BACnet, Q-01) | `f3d.source` `BACNET-FACP-1`, тип `bacnet_ip`, `params={"host":"iot-sim","port":47808,"device_instance":200,"network":2,"readonly":true,"cov":true,"cov_lifetime_s":300,"poll_fallback_s":30}`; адреси сигналів — SPEC Додаток B (`{"object":"life-safety-zone","instance":14,"property":"present-value"}` тощо) | **лише читання** (ReadProperty, ReadPropertyMultiple, SubscribeCOV; прийом UnconfirmedEventNotification) | COV; опитування 30 с як резерв; AV запиленості 600 с | `stale` через 90 с (telemetry FR-12) → панель `stale`; `comm_lost_after_s` 180 с → `lost`, подія, заявка (FR-12); значення зон не змінюються (останній відомий стан + позначка) |
| P-09 ADAM | SPARK-1, SMOKE-CTRL (ADAM-6050 unit 85, iot_sim §8.11.3) | `f3d.source` `MB-U85-IO6`, тип `modbus_tcp`, `params={"host":"iot-sim","port":502,"unit":85}`; адреси: DI0–DI6 `fc 2 addr 0…6`, лічильник DI0 `fc 3 addr 0–1 u32 (порядок слів little, ADAM)`; DO0/DO1 **не** мають сигналів | читання | 2 с (DI), 10 с (лічильник) | `stale` через 60 с → система `unknown`, подія `comm_lost` на системі, заявка через `alarm_states` не створюється (стан, не несправність); відновлення — подія |
| telemetry | `equipment/SPRINKLERS/pressure_bar` (u90 AI2, власник telemetry) | лише посилання `f3d.fire.system.pressure_signal_id` | читання `last_value/status` | як у telemetry (10 с) | `status=stale` → система `unknown` |
| Odoo ↔ переглядач | — | `bus.bus` `f3d_viewer` через `f3d.viewer.event._notify` (CF-04) | — | на кожну зміну стану (коалесценція M-03) | без viewer — нічого |
| iot_sim (optional) | пульт `f3d.sim.panel` | `f3d.sim.run` сценарій `fire_drill` {zone, detector, real=false, duration_s} (API-13 через методи пульта iot_sim M-01/M-05) | Odoo → емулятор (це **не** запис у пристрій — емулятор, а не прилад; на проді модуля iot_sim немає) | за кнопкою | кнопка прихована без модуля; помилка пульта → `UserError` |
| access (optional) | TURN-1, ACR-* | хук CF-02 (`_f3d_passages`) | читання | під час навчання кожні 10 с (крон навчання) | реалізація за замовчуванням — `hr.attendance` |
| hr_attendance | — | `hr.attendance` (`check_in`, `check_out`, `in_mode`) | читання | під час навчання | — |
| bms / machine_connect (optional) | RV-*, AHU-1; РЦ зони | сигнали `ventilation/units/<RV>/mode`, `workcenters/<WC>/state`, якщо існують у `f3d.signal` | читання для авто-відмітки кроків | під час навчання | крок лишається «вручну» |

Вимоги до плагіна `bacnet_ip` (власник — `factory3d_telemetry`, Q-07): (1) типи об'єктів `life-safety-zone`,
`life-safety-point`, `analog-value`, `analog-input`, `binary-input`, `binary-value`, `multi-state-value`;
(2) `present-value` LSZ/LSP віддавати **текстом** переліку `BACnetLifeSafetyState` (`quiet`, `pre-alarm`,
`alarm`, `fault`, `fault-pre-alarm`, `fault-alarm`, `not-ready`, `active`, `tamper`, `test-alarm`,
`test-active`, `test-fault`, `test-fault-alarm`, `holdup`, `duress`, `general-alarm`, `supervisory`,
`test-supervisory`) і числом індексу (telemetry A-06 `kind='state'`); BI — `inactive/active` → 0/1; MSV —
індекс + текст зі `state-text`; (3) властивості `reliability`, `mode`, `silenced` — через адресу
`{"property": "reliability"}`; (4) `SubscribeCOV` з поновленням за `cov_lifetime_s`, при відмові — опитування
`poll_fallback_s`; (5) `params.readonly=true` → метод `write()` плагіна кидає `PermissionError` **до**
будь-якого пакета в мережу, не залежить від `F3D_WRITE_ENABLED`; (6) маршрутизована мережа (`network`) і
прямий IP (`host` без `network`) — обидва; (7) опційно `UnconfirmedEventNotification` → `POST /f3d/telemetry/event`
маршрут `bacnet_event` з `{device, object, event_type, from_state, to_state, message_text, ts}`.

### 2.5 Потік даних від пристрою до екрана

Приклад 1 — запиленість → заявка (макет 09:58, MR/00036). 1) `f3d.signal` `fire/groups/FA-FAC/dust`
(`kind='gauge'`, `unit='%'`, `alarm_high=90`, `warn_high=80`, `alarm_title="Очистити сповіщувач {device} ({zone}): запиленість {value} % при нормі до {threshold}"`, адреса `{"object":"analog-value","instance":21607,"property":"present-value"}`, джерело `BACNET-FACP-1`, `period_s=600`); 2) колектор читає AV:21607 = 82 → push; 3) telemetry: `status='warn'` (≥ 80), без заявки; модуль (R-13): `f3d.fire.device[2.FAC.07].dust_pct=82`, `state='warn'`, зона `FA-FAC.warn=True`, `warning="Сповіщувач 2.FAC.07 біля шліфування: запиленість камери 82 % — очистити…"`, подія `dust_warn` (один раз на перетин 80); 4) шина `f3d.fire.zone` `FA-FAC` → переглядач: картка FA-FAC «Попередження», «Потребує уваги» (як у макеті); 5) емулятор R-09 веде 82 → 90 за ≈ 800 хв; при 90,1 telemetry R-05 створює заявку «Очистити сповіщувач 2.FAC.07 (Дільниця фасадів МДФ): запиленість 90,1 % при нормі до 90» на обладнанні `FA-FAC`, команда з параметра; модуль (R-14) прив'язує `f3d_fire_device_id`, подію `dust_alarm`, у payload `fire.groups.FA-FAC.maintenance_request = "MR/000xx"`; 6) закриття заявки (telemetry R-06) → емулятор скидає AV до номіналу → `dust_pct` ≤ 80 → `warn=False`, подія `info` «повернувся в норму».

Приклад 2 — навчальна тривога (макет `drill_steps`). 1) інженер ПБ створює `f3d.fire.drill` (зона `FA-CNC`,
сповіщувач `2.CNC.05`, режим `sim`), натискає «Запустити на емуляторі» → iot_sim запускає `fire_drill`
(`zone=FA-CNC`, `detector=2.CNC.05`, `duration_s=300`), `run_ref` зберігається, стан `running`,
`start_ts` = час натискання; 2) емулятор R-25: LSP:21405 і LSZ:14 → `test-alarm`, LSZ:0 → `test-alarm`,
MSV:1 → 4; колектор → push; telemetry: `fire/groups/FA-CNC/state` `last_text='test-alarm'` (не в
`alarm_states` → заявки немає); 3) модуль R-11: зона `FA-CNC.state='test'`, панель `state='test'`, подія
`test` «Тест: сповіщувач 2.CNC.05, Присадка»; R-17: крок «Сповіщувач 2.CNC.05 … тривога на приладі»
`t_fact = ts − start_ts` (≈ 0–5 с), `done=True`; +3 с BI:10 → `fire/totals/sounders_active=1` → крок «Увімкнено
41 сирен-маяків» done; +9 с u85 DI4 → крок «Відкрито клапани» done; кроки «Зупинено вентиляцію» (+6),
«Розблоковано двері» (+12), «Аварійна зупинка верстатів» (+20) — за сигналами bms/access/machine_connect,
якщо є, інакше вручну; 4) R-16: `on_site` = `_f3d_on_site(start_ts)` (демо: 35 працівників з `hr.attendance`),
проходи кожні 10 с із `_f3d_passages(start_ts, now)`; 5) провайдер 140: `evacuation.drill_active =
{name, zone: "Присадка", detector: "2.CNC.05", started, elapsed_s, steps_done: 3}`; шина `f3d.fire.drill`
→ переглядач (Q-09: автозапуск `startDrill()`); 6) «Завершити» (або `duration_s` минув і LSZ повернулись у
`quiet` → авто-стоп через `drill_auto_stop_s`): `end_ts`, `evac_time_s = max(exit_ts) − start_ts`,
`evacuated/on_site`, `not_evacuated_ids`, стан `evaluating` → інженер робить перекличку й пише висновки →
`done`, звіт PDF.

Приклад 3 — втрата зв'язку. Емулятор `POST /device/FACP-1/fault {"reason":"comm"}` → BACnet device 200 не
відповідає (iot_sim R-15) → колектор не шле показань `fire/*` з `BACNET-FACP-1`; telemetry через 90 с
ставить `status='stale'` і джерело `error`; модуль R-12: панель `comm='stale'` (90 с), через
`comm_lost_after_s`=180 с → `comm='lost'`, подія `comm_lost` рівня `alarm`, активність охороні, заявка
«Втрата зв'язку з приладом FACP-1: немає даних з 10:31 (3 хв)» на `FACP-1` (одна відкрита), payload
`fire.totals.state = "Зв'язок із приладом втрачено"`, `fire.panel.comm = "lost"`; `clear` → перше показання →
`comm='online'`, подія `comm_restored`, активність закривається, заявка лишається механіку (закриває він).

### 2.6 Безпека

- **Групи** (CB-10 + модуль): `group_f3d_user` — читання всіх моделей модуля; `factory3d_fire_safety.group_f3d_fire_drill`
  («Пожежна безпека: ведення навчань», входить у `group_f3d_manager`) — `create/write` на `f3d.fire.drill*`,
  `f3d.fire.event` рівня `manual` (коментар у журналі), перекличка; `group_f3d_manager` — `f3d.fire.norm`,
  `monitor` на пристроях, параметри; `group_f3d_admin` — стоп-кран, `neutralize.sql`, повторна міграція.
  Жодної кнопки/дії/методу, що формує `f3d.command` або викликає `write()` плагіна.
- **Абсолютна заборона запису (D-07, FR-18).** Чотири рівні: (1) параметра `factory3d.fire_safety.write_enabled`
  **не існує** — конвенція §5 каркаса передбачає його «за замовчуванням False», тут він навіть не створюється,
  бо наявність перемикача = можливість його увімкнути (A-03); якщо хтось створить параметр вручну — модуль його
  не читає; (2) `f3d.source` модуля має `f3d_fire_readonly=True` і `params.readonly=true`; `@api.constrains`
  на `f3d.source.write_enabled`: `True` при `f3d_fire_readonly` → `ValidationError("Джерело пожежної сигналізації
  працює лише на читання (рішення D-07). Увімкнути запис неможливо.")`; `f3d_fire_readonly` не знімається
  (`write` з `f3d_fire_readonly=False` → той самий виняток); (3) `f3d.signal` з `module='fire_safety'` —
  `write_enabled` завжди `False` (constrains); (4) `f3d.command.create` для таких сигналів → `ValidationError`;
  усі чотири перевірки виконуються і під `sudo()`/`env.su` (явна перевірка без `self.env.su` обходу).
  Плюс плагін (п. 5 вимог §2.4) і колектор `F3D_WRITE_ENABLED=0` (telemetry FR-27). Тест ТБ-01…ТБ-04.
- **Умова проду:** джерело `BACNET-FACP-1` на проді створюється з `read_enabled=False`; у картці джерела
  чек-лист «Дозвіл монтажника на читання BACnet отримано (дата, особа, документ)» — поля `f3d_fire_consent_*`
  (M-15); без заповненого дозволу `read_enabled` увімкнути не можна (constrains). Це реалізує §9 п. 3 каркаса.
- **Стоп-кран** `factory3d.fire_safety.read_enabled`: умовчання `environment == 'test'`; `False` → хук/крон
  не обробляють сигнали, провайдер віддає статику з `fire.totals.state = "Обробка вимкнена"`, кнопки навчань
  «на емуляторі» неактивні. `neutralize.sql`: параметр `False`, крони модуля `active=False`, `f3d.source`
  модуля `read_enabled=False`, `f3d_fire_drill.sim_run_ref=NULL`, `f3d_fire_drill_person.employee_id=NULL`
  (FR-24), `mail.activity` модуля видалити.
- **Токени** — відсутні (усе через telemetry). **Ін'єкції**: адреси пристроїв — regex `^[1-4]\.[A-Z0-9-]{2,8}\.\d{2}$`;
  імпорт JSON шляхів маршрутів — валідація схемою (список пар чисел у межах CB-12); тексти подій з
  BACnet `message-text` обрізаються до 500 символів і екрануються.
- **Персональні дані** (FR-24): `f3d.fire.drill.person` — доступ `group_f3d_fire_drill` і `hr.group_hr_user`;
  звіт PDF друкує прізвища лише з опцією `print_names`; записи не копіюються у чаттер; `neutralize.sql`
  відв'язує працівників.
- **Журнал подій** — `f3d.fire.event` без `unlink` для всіх груп (ACL `perm_unlink=0`), без `write`
  (крім `note`/`ack` — підтвердження перегляду охороною); ротації немає (A-12).

### 2.7 Продуктивність і обсяги

| Клас | Сигнали | `period_s` | `store_period_s` | Показань/добу (сирих) | Збережених/добу |
|---|---|---|---|---|---|
| LSZ:0…33, BI:1…4, BI:10/11, MSV:1 (`kind='state'`) | 41 | COV (резерв 30) | 3600 (+ кожна зміна) | ≈ 118 000 при опитуванні / ≈ 100 при COV | ≈ 1 000 (переважно зміни під час навчань) |
| AV:1…3 лічильники | 3 | 30 | 3600 | 8 640 | 72 + зміни |
| AV запиленості (макет 1; `monitor` до 212) | 1 (до 213) | 600 | 3600 | 144 (до 30 700) | 24 (до 5 100) |
| ADAM u85 DI0–DI6 | 7 | 2 | 3600 (+ зміни) | 302 400 (один блок-запит на 7 сигналів = 43 200 запитів) | ≈ 200 |
| ADAM HR 40001 лічильник | 1 | 10 | 300 | 8 640 | 288 |
| **Разом** | **53** | | | ≈ 320 000 через API (≈ 3,7/с) | **≈ 1 600/добу** |

`f3d.fire.event`: у нормі 5–20 подій/добу, під час навчання ≈ 60; 400 днів ≈ 10 000 рядків — ротація не
потрібна (A-12; індекс `(ts, kind)`, `(object_code, ts)`). Правила R-01…R-03 (сітки 0,5 м по зоні й 2 м по
будівлі) рахуються лише при зміні даних пристроїв/норм (`@api.depends` + кнопка «Перерахувати»), не на
кожне показання: R-03 — 76×37 = 2 812 точок × 36 ручних = 101 232 відстаней, < 0,2 с; R-02 по всіх зонах —
≈ 43 000 точок × ≤ 24 сповіщувачів, < 1 с. Провайдер 130/140: `search_read` 33 зон + 4 шлейфи + 3 системи +
12 виходів + 32 маршрути + 50 останніх подій ≈ 40 КБ, < 100 мс; дельта — розділи цілком (viewer R-14 п. 5,
ліміт 200 КБ — укладаємось із запасом). Крон-звірка 1 хв: один `search_read` 53 сигналів.

### 2.8 Міграція з демо-бази і деінсталяція

`post_init_hook` (SPEC §5.4), ідемпотентно, у транзакції установки:

1. Data (порядок маніфесту): норми 20, шлейфи 4, зони 33, пристрої 343, системи 3, димові зони 8, виходи 12,
   маршрути 32, шаблон навчання 1 (8 кроків), джерела 2 (`BACNET-FACP-1`, `MB-U85-IO6`; `read_enabled` за
   середовищем), сигнали 52 (`origin='catalog'`, `module='fire_safety'`, `write_enabled=False`), параметри,
   крони, послідовність `f3d.fire.drill` (`DRILL/%(year)s/`), групи.
2. Прив'язка обладнання base за `search_f3d`: `FACP-1` → панель; 33 `FA-<зона>` → `f3d.fire.zone.equipment_id`
   (`FA-BOILER` теж); `FA-MCP`, `FA-SND`, `FA-FLAME` → `equipment_id` пристроїв відповідних типів; `SPARK-1`,
   `SMOKE-CTRL`, `SMOKE-VENTS`, `SPRINKLERS` → системи (вентиляційні люки — `SMOKE-VENTS`); `EXITS` → виходи;
   `LPS` — не чіпається. Очікувано: `linked: 43` (41 категорії «Пожежна безпека» + `SPRINKLERS` + `SMOKE-VENTS`
   як частина системи), `missing: 0` на копії демо; на чистій базі без base-міграції — `missing: 43` з WARNING,
   модуль працює (обладнання — лише посилання).
3. Сигнал рівня 0/telemetry `fire/groups/FA-FAC/dust`: якщо `f3d.signal` з таким `code` уже існує (міграція
   telemetry, `origin='sim_data'`) — **не** створюється дубль, а дописуються `source_id=BACNET-FACP-1`, `address`,
   `module='fire_safety'`, `warn_high=80`, `alarm_high=90`, `alarm_title`, `write_enabled=False`; інакше створюється
   з data. Пристрій `2.FAC.07`: `dust_signal_id` = цей сигнал, `monitor=True`, `dust_pct = last_value` (86,1 на
   14.10). Очікувано: `signals_total: 52`, `signals_reused: 1`.
4. Заявка ТО з `f3d_signal_id` = цей сигнал (телеметрія проставила при своїй міграції; на демо id 5) →
   `f3d_fire_device_id = 2.FAC.07`, `f3d_fire_zone_id = FA-FAC`; очікувано `requests_linked: 1`.
5. Демо-події `fire.events` макета (4: `SPARK-1` 12.10 08:47 іскра, `FA-FAC` 09:58 запиленість, `FACP-1` 07:00
   щотижнева перевірка, `SPARK-1` 11.10 23:10 самотест) → `f3d.fire.event` із `source='demo'`, ключ дедуплікації
   `demo:<n>`; очікувано `events_demo: 4` (повторно — 0).
6. Демо-навчання: `f3d.fire.drill` «Навчальна тривога — демо (Присадка)» у стані `done`, дата 2026-09-30
   (ПРИПУЩЕННЯ: дата останньої перевірки спринклерів із макета), зона `FA-CNC`, сповіщувач `2.CNC.05`, кроки
   з шаблону з `t_fact = t_plan`, `on_site=35`, `evacuated=35`, `evac_time_s=240`, результат `ok`, висновок
   «Демо-запис: показує структуру протоколу навчання»; очікувано `drills_demo: 1`.
7. Стани: панель/зони/системи — перший прогін крона-звірки R-19 одразу в хуку (`_f3d_fire_sync(full=True)`):
   без показань — усі `unknown`, панель `comm='lost'` **без** події/заявки (перший старт, `first_sync=True`).
8. Перерахунок норм R-01…R-09 (`action_recompute_compliance` для всіх) → очікувано: зони `ok: 33`
   (R-01 усі 33 збігаються з потрібною кількістю, R-02 усі в межах 6,22 м + допуск 0,5: найгірше `Z-FG`
   6,26 м у точці (122,0, 54,1)); MCP `max_m: 26.9` ≤ 30 (точка (60, 72)); маршрути `ok: 32` (макс. 38,6 м
   `Z-PRE`; `max_distance` 45,3 ≤ 240 і ≤ 50); виходи `ok` (12 ≥ 2; L = 31,6 м виконується для пар на різних
   стінах); димові зони `ok: 8` (усі ≤ 1 600; люків 44 = потреба 44).
9. Звіт у `factory3d.fire_safety.migration_report` (JSON лічильників, `ts`, `state ∈ {done, partial}`).

Повторний запуск (`upgrade`): data з `noupdate="0"` для довідкових записів (зони, пристрої, виходи,
маршрути — перезапис тими ж значеннями за xml-id), `noupdate="1"` для джерел/сигналів/параметрів/норм
(щоб не затерти правки менеджера); кроки 2–6 — за ключами, без дублікатів.

`uninstall_hook`: крони модуля `active=False`; параметри `factory3d.fire_safety.*` видалити; `f3d.source`
модуля → `read_enabled=False` (лишаються — належать telemetry за даними, але xml-id модуля → Odoo видалить
записи data разом із модулем; тому хук попередньо **відв'язує** `fire/groups/FA-FAC/dust` від джерела й
повертає йому `module` за CT-09 (`fire_safety` лишається — класифікатор telemetry) — сигнал макета
переживає деінсталяцію; решта 51 сигнал `catalog` видаляються як data); `maintenance.request.f3d_fire_*`
зникають з полями, заявки лишаються; `f3d.fire.event`, `f3d.fire.drill*` видаляються з моделями —
застереження в чаттері панелі й у логах WARNING перед видаленням (журнал навчань — юридично значущий
документ; перед деінсталяцією на проді експортувати звіти PDF, інструкція 4.6).

## 3. Налаштування системи

| Об'єкт | Параметр | Значення для тестового сервера | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `factory3d.fire_safety.read_enabled` | `True` (тест) / `False` (прод одразу після встановлення) | стоп-кран обробки сигналів; умовчання з `factory3d.base.environment` (CB-10) |
| `ir.config_parameter` | `factory3d.fire_safety.write_enabled` | **не існує і не створюється** | FR-18, A-03 |
| `ir.config_parameter` | `factory3d.fire_safety.comm_lost_after_s` | `180` | втрата зв'язку з приладом (після `stale` telemetry 90 с) |
| `ir.config_parameter` | `factory3d.fire_safety.dust_warn_pct` | `80` | попередження запиленості (макет 82 % → warn) |
| `ir.config_parameter` | `factory3d.fire_safety.dust_alarm_pct` | `90` | заявка ТО (поріг сигналу; емулятор R-25 `> 90`) |
| `ir.config_parameter` | `factory3d.fire_safety.polymer_panels` | `False` | `True` → норма шляху 50 м (ДБН В.2.2-27 п. 8.2.11) замість 240 м (Q-04) |
| `ir.config_parameter` | `factory3d.fire_safety.cover_tol_m` | `0.5` | допуск покриття R-02 (A-06) |
| `ir.config_parameter` | `factory3d.fire_safety.drill_time_limit_s` | `300` | ліміт часу евакуації для результату навчання (Q-03, ПРИПУЩЕННЯ) |
| `ir.config_parameter` | `factory3d.fire_safety.drill_auto_create` | `True` | FR-14 |
| `ir.config_parameter` | `factory3d.fire_safety.drill_match_window_min` | `30` | вікно зіставлення `test-alarm` із запланованим навчанням |
| `ir.config_parameter` | `factory3d.fire_safety.drill_auto_stop_s` | `120` | авто-завершення після повернення всіх зон у `quiet` |
| `ir.config_parameter` | `factory3d.fire_safety.drill_sim_duration_s` | `300` | `duration_s` для `fire_drill` емулятора |
| `ir.config_parameter` | `factory3d.fire_safety.alert_group_xmlid` | `factory3d_base.group_f3d_user` | кому активність «Пожежна тривога» (на проді — група охорони) |
| `ir.config_parameter` | `factory3d.fire_safety.team_id` | id «Служба головного механіка» (демо id 2) | команда заявок із пожежних сигналів (Q-02); порожньо → `factory3d.telemetry.default_team_id` |
| `ir.config_parameter` | `factory3d.fire_safety.viewer_devices` | `False` | віддавати `fire.devices` (343) у payload (Q-09) |
| `ir.config_parameter` | `factory3d.fire_safety.event_ack_required` | `True` | події рівня `alarm` потребують підтвердження охорони (`ack`) |
| `ir.config_parameter` | `factory3d.fire_safety.migration_report` | `{}` → звіт хука | §2.8 |
| `f3d.source` | `BACNET-FACP-1` | тип `bacnet_ip`, `collector_id=COL-MAIN`, `params` §2.4, `read_enabled=True` (тест), `write_enabled=False`, `f3d_fire_readonly=True`, `f3d_fire_consent_*` порожні на тесті (вимагаються лише при `environment='prod'`) | прилад |
| `f3d.source` | `MB-U85-IO6` | тип `modbus_tcp`, `{"host":"iot-sim","port":502,"unit":85}`, `read_enabled=True`, `write_enabled=False`, `f3d_fire_readonly=True` | GreCon + D+H |
| `f3d.signal` | 52 сигнали `fire/*` | з data (SPEC Додаток B), `write_enabled=False` | |
| `f3d.fire.norm` | 20 норм | з data (`fire_rules.json`, `evac_rules.json`) | менеджер може змінити значення; `ref` обов'язковий |
| `ir.cron` | `cron_f3d_fire_sync` | 1 хв, активний | R-19 звірка станів (fallback до хука Q-06), зв'язок R-12 |
| `ir.cron` | `cron_f3d_fire_drill_tick` | 1 хв, активний (працює лише при `running` навчанні; усередині — цикл до 50 с з кроком 10 с) | R-16/R-17 |
| `ir.cron` | `cron_f3d_fire_compliance` | щодня 03:10 (Київ) | перерахунок R-01…R-09 (на випадок правок норм/пристроїв без кнопки) |
| `ir.sequence` | `f3d.fire.drill` | `DRILL/%(year)s/0001` | |
| `res.groups` | `group_f3d_fire_drill` | інженер ПБ; на тесті — адміністратор | FR-17 |
| `maintenance.team` | «Служба головного механіка» | існує в демо (id 2) | `team_id` |
| iot_sim | `f3d.sim.panel` налаштований, сценарій `fire_drill` у списку | з модуля iot_sim | FR-23 |

## 4. Інструкція

**4.1 Увімкнути читання приладу на проді** (адміністратор, інженер АСУ). 1) Отримати від монтажника
письмовий дозвіл на підключення до BACnet-інтерфейсу Cerberus PRO (ключ S2 FCA2034-A1 «monitoring only»,
Q-01) і IP/порт/instance приладу; 2) Завод 3D → Телеметрія → Джерела → `BACNET-FACP-1`: вкладка «Пожежна
сигналізація» — заповнити «Дозвіл монтажника: дата, особа, документ» (вкладення PDF); `params.host` =
IP приладу, `network` прибрати, якщо прямий IP; 3) увімкнути «Читати» на джерелі (без дозволу — помилка);
4) Налаштування → Завод 3D → Пожежна безпека → «Обробляти сигнали» = увімкнено; 5) через ≤ 2 хв Огляд:
прилад «Норма», зв'язок «онлайн», 33 зони зелені; у журналі — подія `comm_restored`. Запис у прилад
увімкнути неможливо — так і має бути.

**4.2 Що робити при тривозі** (охорона). На `Завод 3D → Пожежна безпека → Огляд` прилад стає червоним
«Тривога», у зоні — назва зони й сповіщувач; у Odoo приходить активність «Пожежна тривога: Присадка,
сповіщувач 2.CNC.05» (дзвінок у верхньому меню); 1) діяти за інструкцією підприємства (виклик 101 — якщо
прилад не передав сам: поле «Передано на пульт» = ні); 2) «Показати в 3D» — зона підсвічена, маршрути
евакуації; 3) після скидання приладу монтажником/черговим подія `reset` закриє активність; у журналі
натиснути «Підтвердити» на події тривоги і за потреби дописати коментар. Odoo нічого не вимикає й не
скидає — лише показує.

**4.3 Несправність або запиленість — заявка ТО** (головний механік). Заявка з'являється в Обслуговування
→ Заявки з текстом «Несправність зони FA-CUT (Розкрій): стан fault» або «Очистити сповіщувач 2.FAC.07
(Дільниця фасадів МДФ): запиленість 90,3 % при нормі до 90»; у заявці — посилання на зону/пристрій/подію;
викликати монтажника, після робіт закрити заявку (стадія «Repaired»). Поки заявка відкрита, нова на той
самий сигнал не створюється; після закриття стан перераховується з приладу.

**4.4 Провести навчальну тривогу** (інженер ПБ). 1) Пожежна безпека → Навчальні тривоги → Створити:
дата, зона (`FA-CNC`), сповіщувач (`2.CNC.05`), спосіб: «Емулятор» (стенд) або «Тест приладу» (прод: монтажник
переводить прилад у тест і активує сповіщувач) або «Настільне»; кроки заповнюються з шаблону; 2) «Почати»
(для емулятора — «Запустити на емуляторі»): фіксується старт, список «На об'єкті» (з відміток/СКУД);
3) спостерігати: кроки відмічаються самі за сигналами (сирени, клапани), решту — кнопкою «Виконано» з
часом; люди, що пройшли турнікет/КПП, з'являються у вкладці «Евакуація» з часом; 4) «Завершити» → час
евакуації, відсоток, список «Не вийшли»; провести перекличку на місці збору: кнопка «Перекличка» → відмітити
присутніх вручну; 5) висновки, зауваження, фото/акт у вкладення, результат (пройшло/із зауваженнями/не
пройшло) → «Закрити»; «Друк → Протокол навчання» (PDF).

**4.5 Перевірити відповідність нормам** (інженер ПБ, проєктант). Пожежна безпека → Евакуація → «Звіт
перевірки» (PDF): таблиця маршрутів (зона, вихід, довжина, норма 240/50 м, статус), виходи (кількість,
розосередженість L ≥ 31,6 м, ширина), димові зони (площа ≤ 1 600 м², люки потреба/факт), розстановка
сповіщувачів по зонах (потрібно/є, покриття, найгірша точка), ручні сповіщувачі (макс. 26,9 м ≤ 30),
посилання на пункти ДБН з довідника норм. Змінити норму (напр., після нової редакції ДБН) — Пожежна безпека
→ Норми (менеджер) → значення і `ref`; «Перерахувати» на Огляді.

**4.6 Перед деінсталяцією або переносом** (адміністратор). Навчальні тривоги → вибрати всі → Друк
«Протокол навчання» → зберегти PDF у документах; Журнал подій → Експорт (xlsx) — журнал подій і навчань
видаляється разом із модулем; `neutralize.sql` на тестовій копії знімає прив'язку працівників до навчань.

## 5. Ризики й відкриті питання

### 5.1 Відкриті питання (ті самі номери — у SPEC §15)

| ID | Питання | Кому | Рекомендована відповідь | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | Cerberus PRO FC726 на об'єкті: чи є ключ BACnet (S2 FCA2034-A1 «BACnet output, monitoring-only, life-safety objects» — Siemens S1/S2/S3 License Keys datasheet, https://sid.siemens.com/api/khub/documents/EAQ9YtHpKnIPi1ssft0y4A/content, переглянуто 14.10.2026; один інтеграційний гайд третьої сторони каже «мінімум S3») і який склад об'єктів (LSZ на зону, LSP на елемент, AV запиленості — ПРИПУЩЕННЯ iot_sim Q-03); дозвіл монтажника на читання (каркас §9 п. 3) | монтажник / Siemens | S2 достатньо для читання; запросити експорт об'єктів (EPICS/PICS) після інсталяції ключа | адреси — за емулятором; усе в `f3d.signal.address`, не в коді; у проді `read_enabled=False` до дозволу (4.1) |
| Q-02 | Хто виконує ТО сигналізації (підрядник) і чи потрібна окрема `maintenance.team` «Пожежна сигналізація (підрядник)» замість «Служба головного механіка» | замовник / головний механік | окрема команда з e-mail підрядника; заявки підписує механік | параметр `team_id` = «Служба головного механіка» |
| Q-03 | Нормативний час евакуації для оцінки навчання (у макеті немає; ДСТУ 8828 — розрахунок) | інженер ПБ / проєктант | взяти розрахунковий час із проєкту СПЗ; інакше — внутрішній норматив підприємства | `drill_time_limit_s=300` (ПРИПУЩЕННЯ), результат `remarks` замість `failed` при перевищенні |
| Q-04 | Чи стінові/покрівельні панелі з полімерним утеплювачем (норма 50 м за п. 8.2.11 замість 240 м) | замовник / проєктант | за проєктом будівлі | `polymer_panels=False`; обидві норми в звіті (як у переглядачі) |
| Q-05 | Зони `Z-OFFICE` і `Z-SOC` у макеті без сповіщувачів (`ZONE_DETECTOR` їх не містить), хоча ДБН вимагає СПС в офісах | автор макета / проєктант | додати в макет 2 групи (OP720), перегенерувати data | 33 зони як у макеті; звіт показує «зони без сигналізації: Z-OFFICE, Z-SOC» як зауваження |
| Q-06 | **Узгодити з telemetry:** хук зміни стану сигналу. `push` оновлює `last_*` через SQL (telemetry R-17), тож `write()` не спрацьовує; потрібен контракт CT-11: після обробки пакета — `env['f3d.signal']._f3d_after_push(changes)` з `[{code, old_text, new_text, old_value, new_value, ts}]` для сигналів, у яких змінився `last_text`/`status`, або абстрактний хук `f3d.signal.listener` з `_f3d_modules` і `_f3d_on_change(...)` | автор telemetry | хук-слухач з фільтром за `module` | крон-звірка 1 хв (R-19): затримка подій ≤ 60 с, усі правила працюють; хук лише зменшує затримку до секунд |
| Q-07 | **Узгодити з telemetry:** плагін `bacnet_ip` — за рішенням менеджера належить telemetry, але telemetry ARCH §1.4 досі віддає його bms; вимоги §2.4 (7 пунктів, зокрема `readonly` на рівні плагіна і текстові стани LSZ/LSP) та схема `address` для `bacnet_ip` (CT-03): `{"object": "<тип>", "instance": int, "property": "present-value|reliability|mode", "index": int?}` | автор telemetry, менеджер | внести в telemetry SPEC §8 і Додаток A | у data адреси за цією схемою; якщо схема інша — змінюється лише генератор `gen_data.py` |
| Q-08 | **Узгодити з iot_sim:** (а) адреси LSP для ручних/оповіщувачів/полум'я (`<loop>.<ZONE>.<nn>` визначено лише для сповіщувачів зон) — пропозиція A-09; (б) у каталозі немає сигналів для BI:10/BI:11 і DI1/DI2/DI3/DI5/DI6 (сигнали 644/646 об'єднують 3 входи в одну адресу) — пропозиція 7 нових кодів (SPEC Додаток B); (в) `fire_drill real=true` → BI:11=1 і LSZ `alarm` — підтвердити | автор iot_sim | прийняти A-09 і 7 кодів у Додаток A iot_sim | працюємо за A-09; емулятор віддає об'єкти незалежно від каталогу |
| Q-09 | **Узгодити з viewer:** (а) автозапуск `startDrill()` при `evacuation.drill_active != null` і авто-стоп; (б) значення `fire.groups[*].state = "alarm"`/`"fault"` рендерити червоним (зараз усе, що не `ok`, — «Попередження»); (в) маркери окремих пристроїв із `fire.devices` (x, y, z) замість підсвітки групи `FA-<зона>` | автор viewer | так, у наступній версії клієнта; контракт CF-01 вже містить ключі | без змін клієнта: навчання запускається кнопкою, тривога показується як «Попередження» + текст |
| Q-10 | **Узгодити з access:** реалізація CF-02 (проходи через `TURN-1`/`ACR-*` з напрямком; чи буде зчитувач на місці збору); люди виходять через аварійні двері без бейджів — СКУД їх не бачить | автор access, замовник | реалізувати CF-02; на місці збору — мобільний зчитувач або перекличка | перекличка вручну (кнопка), `hr.attendance` як джерело |
| Q-11 | README (розділ «Пожежна сигналізація») каже 192 сповіщувачі, макет (`fire.totals.detectors`, сума `groups`) — 212 | автор макета | виправити README на 212 | у data 212 |
| Q-12 | Пожежні крани, вогнегасники, насосна й резервуари (`Z-FIREWATER`) — у макеті лише паспорт шафи `fire_hydrant_cabinet` без позицій; чи потрібен облік (перевірки, перезарядка) | замовник | фаза 6 або стандартний `maintenance` з категоріями | не входить (1.4) |
| Q-13 | Термін зберігання журналу подій і форма журналу (чи потрібна відповідність «Журналу обліку перевірок СПЗ» за правилами ПБ) | інженер ПБ | зберігати безстроково; форма — звіт PDF «Журнал подій за період» | ротації немає (A-12), звіт за період є |
| Q-14 | Реальна розкладка сухих контактів GreCon BS 7 (Mission Control) і D+H CPS-M1 (TMA/AM цифрові виходи) на ADAM — iot_sim §8.11.3 позначено ПРИПУЩЕННЯ; D+H публікує KNX/Modbus-шлюзи (CPS-M1-S) і BACnet (CPS-M1-MSE) | монтажник / D+H / GreCon | з'ясувати після вибору; якщо Modbus-шлюз D+H — змінюється лише джерело/адреси | адреси ADAM з емулятора в `address` |
| Q-15 | Чи зберігати в `hr.attendance` виходи під час навчання (турнікет на виході ставить `check_out` = людина «пішла з роботи») | автор access, HR | проходи навчання писати лише в `f3d.fire.drill.person`, не в attendance; access вирішує за прапором «навчання триває» (CF-02 дає `drill_active`) | читаємо лише; нічого не пишемо в attendance |

### 5.2 Ризики

| Ризик | Вплив | Пом'якшення |
|---|---|---|
| Прилад на об'єкті віддає інший склад об'єктів BACnet (не LSZ/LSP, а BI на зону) | мапінг станів не працює | мапінг у даних (`address`, таблиця станів R-10/R-11 з параметром `state_map` на джерелі); ТК-01 «звірка з приладом» перед `read_enabled`; тексти станів BACnet, не числа |
| Хтось обійде заборону запису (прямий `pymodbus`/`bacpypes` з контейнера колектора) | втручання у сигналізацію | плагін з `readonly`, `F3D_WRITE_ENABLED=0`, allow-list; організаційно — мережевий сегмент приладу лише на читання (ACL на комутаторі, рекомендація монтажнику); тест ТБ-05 (перехоплення пакетів під час усіх ТК: 0 Write) |
| Без хука telemetry (Q-06) події мають затримку до 60 с | охорона бачить тривогу пізніше | тривога на об'єкті сигналізується приладом (сирени, пульт) незалежно від Odoo; Odoo — журнал і 3D; хук після погодження знижує до ≤ 5 с |
| Навчання на реальному приладі: `test-alarm` ≠ `alarm`; якщо монтажник не переводить у тест, Odoo зафіксує справжню тривогу | хибна активність охороні, помилкова передача на пульт | FR-14 зіставляє зі запланованим навчанням: `alarm` у вікні навчання фіксується як крок навчання з позначкою «реальний стан приладу: alarm» і попередженням; передача на пульт — поза Odoo |
| Люди виходять через аварійні двері без бейджів — СКУД не бачить (Q-10) | час евакуації не вимірюється автоматично | перекличка вручну; `evac_time_s` рахується за тими, кого видно, з позначкою «неповні дані» |
| Емулятор BACnet через роутер (мережа 2) — реальний прилад з прямим IP | джерело не підключається після переходу | обидва варіанти в `params` (`network` опційний), ТК-01 на обох |
| Пороги запиленості: прилад сам переводить елемент у несправність при ~ 90 % (OOH740 має власну компенсацію) | подвійна заявка (dust_alarm і fault) | telemetry дедуплікує за сигналом; модуль R-14 зв'язує `fault` зони з відкритою заявкою `dust` того самого пристрою (не створює другу активність) |
| Зміна № 2 ДБН В.2.5-56 діє з 01.03.2026; наступні зміни змінять числа | правила застарівають | усі числа в `f3d.fire.norm` з `ref`, формули беруть значення з довідника; тести — на значення з data, не з коду |

## 6. План сборки агентами

Межі файлів жорсткі; спільні файли (`__init__.py`, `__manifest__.py`, `security/ir.model.access.csv`,
`views/menus.xml`) належать W0 і правляться через нього.

| Воркер | Файли | Здає | Залежить від |
|---|---|---|---|
| W0 каркас і дані | `__manifest__.py`, `__init__.py`, `hooks.py` (скелет), `models/__init__.py`, `security/security.xml`, `security/ir.model.access.csv`, `data/ir_config_parameter.xml`, `data/ir_cron.xml`, `data/ir_sequence.xml`, `data/neutralize.sql`, `views/menus.xml`, `tools/gen_data.py` + усі `data/f3d_fire_*.csv/xml` (згенеровані з макета), `tests/__init__.py`, `tests/common.py`, `README.md`, `CHANGELOG.md` | модуль встановлюється з усіма data; очікувані кількості §2.8 п. 1; генератор відтворює файли байт-у-байт | SPEC §0, §1, §3 (меню), §4, §5 |
| W1 моделі сигналізації | `models/f3d_fire_panel.py`, `f3d_fire_loop.py`, `f3d_fire_zone.py`, `f3d_fire_device.py`, `f3d_fire_system.py`, `f3d_fire_norm.py`, `f3d_fire_event.py`, `models/f3d_zone.py`, `tools/geometry.py` (сітки R-02/R-03), `views/f3d_fire_panel_views.xml`, `f3d_fire_zone_views.xml`, `f3d_fire_device_views.xml`, `f3d_fire_system_views.xml`, `f3d_fire_norm_views.xml`, `f3d_fire_event_views.xml`, `views/f3d_zone_views.xml`, `tests/test_norms.py`, `tests/test_event.py` | M-01…M-08, M-13; R-01…R-04, R-09 (частина), R-14 (дедуплікація); AC-01…AC-16 | W0 |
| W2 стани й телеметрія | `models/f3d_signal.py` (M-15: перевірки заборони, `_f3d_fire_on_change`), `models/f3d_source.py`, `models/f3d_command.py`, `models/maintenance_request.py`, `models/res_config_settings.py`, `models/push_handler.py` (M-18), `tools/sync.py` (R-10…R-13, R-19), `views/f3d_source_views.xml`, `views/maintenance_request_views.xml`, `views/res_config_settings_views.xml`, `tests/test_sync.py`, `tests/test_security_readonly.py`, `tests/test_requests.py` | M-14…M-16, M-18; R-10…R-14, R-19; AC-17…AC-32; ТБ-01…ТБ-04 | W1 |
| W3 евакуація | `models/f3d_fire_exit.py`, `f3d_fire_route.py`, `f3d_fire_smoke_zone.py`, `report/report_evac_compliance.xml` (+ `report/report_evac_compliance_templates.xml`), `views/f3d_fire_exit_views.xml`, `f3d_fire_route_views.xml`, `f3d_fire_smoke_zone_views.xml`, `tests/test_evacuation.py` | M-07, M-09, M-10; R-05…R-09; AC-33…AC-40 | W0 |
| W4 навчальні тривоги | `models/f3d_fire_drill.py` (+ step, person, template), `models/passage_source.py` (M-12, M-12a), `models/iot_sim_bridge.py` (FR-23), `wizard/drill_rollcall_wizard.py` + `wizard/drill_rollcall_views.xml`, `report/report_drill.xml` (+ templates), `views/f3d_fire_drill_views.xml`, `data/f3d_fire_drill_template.xml`, `tests/test_drill.py`, `tests/test_passage_source.py` | M-11…M-12; R-15…R-18; AC-41…AC-54 | W1, W2 |
| W5 провайдери й хуки | `models/viewer_provider.py` (M-17), `hooks.py` (повний: §2.8 кроки 2–9), `tests/test_viewer_provider.py`, `tests/test_hooks.py` | M-17; R-20, R-21; AC-55…AC-62; очікувані кількості §2.8 | W1–W4 |
| W6 стенд і ТК | `tests/stand/*` (`pytest -m stand` проти compose iot_sim + collector + Odoo), `docs/modules/factory3d_fire_safety/DEPLOY_TEST.md`, `TEST_REPORT.md` | ТК-01…ТК-10, ТБ-01…ТБ-06, ТП-01…ТП-04, DEPLOY_TEST | W5, telemetry W7 (колектор з `bacnet_ip`) |

Порядок злиття: W0 → (W1 ‖ W3) → W2 → W4 → W5 → W6. Кожен воркер здає зелені тести своїх файлів
(`odoo-bin -d test --test-tags /factory3d_fire_safety:<TestClass> --stop-after-init`) і не чіпає чужих.
Після W5 — повний прогін `--test-tags f3d` на чистій базі (без base-міграції) і на копії демо; після W6 — стенд.

## 7. Рішення автора (A-xx)

| ID | Рішення | Обґрунтування | Що змінює відносно каркаса |
|---|---|---|---|
| A-01 | Два провайдери: `f3d.viewer.provider.fire` (130, `fire`) і `.evacuation` (140, `evacuation`) зі спільним помічником | §6.7 каркаса і viewer M-01 резервують два sequence і два ключі; окремі розділи — окремі дельти (навчання не тягне 33 зони) | — |
| A-02 | Сигнали рівня зони (LSZ, 33) і системні (19) — обов'язкові в data; сигнали окремих пристроїв (LSP state, AV dust) — за прапором `monitor` на пристрої (дія «Створити сигнали»), крім `2.FAC.07` з макета | 343 × 2 сигнали без потреби навантажують telemetry (§2.7); прилад сам агрегує стан елементів у LSZ; запиленість цікава там, де пил (менеджер вмикає для FA-FAC/FA-CUT) | уточнює D-04: показання лише через `f3d.signal`, але не всі об'єкти BACnet стають сигналами |
| A-03 | Параметра `write_enabled` для модуля **немає**; заборона — constrains на `f3d.source`/`f3d.signal`/`f3d.command` (діють під `sudo`) + `readonly` у плагіні | §5 каркаса вимагає `write_enabled` «за замовчуванням False» — для сигналізації сама наявність вимикача суперечить D-07 | відхилення від §5 (стоп-крани), погоджене з D-07 |
| A-04 | Події журналу виводяться з переходів `last_text` сигналів (первинно) і з BACnet-повідомлень (вторинно); ключ дедуплікації `kind:object:ts_floor(2 с)` | COV/push доставляють стан надійно й без залежності від intrinsic reporting приладу; повідомлення дають текст приладу, коли є | — |
| A-05 | Маршрути евакуації імпортуються з `evac_routes.json` (Дейкстра лишається в макеті); Odoo перевіряє норми й рахує покриття MCP/сповіщувачів сам | перешкоди (`layout.OBST`) існують лише в сцені; переносити 3D-геометрію в Odoo — поза межами; норми й покриття потребують лише координат, які є | уточнює «усе, що є в макеті, має з'явитися в Odoo»: результат — так, алгоритм пошуку шляху — ні |
| A-06 | R-02 «покриття зони» — похідна перевірка: кожна точка сітки 0,5 м у контурі зони не далі `r = s/√2` (6,22 м для 8,8; 4,53 для 6,4) + допуск `cover_tol_m` 0,5 від найближчого сповіщувача своєї зони; це еквівалент квадратної схеми табл. 7.1/7.2 | ДБН задає крок/відстань до стіни для сітки; після `_nudge` макета сітка нерегулярна — потрібна перевірка, що не залежить від регулярності; у звіті позначено «похідна перевірка, не текст норми» | — |
| A-07 | Справжня тривога → подія + активність охороні + шина; заявка ТО **не** створюється; заявки — лише несправність/запиленість/зв'язок/системи | §6.8 — про ТО; пожежа — не обслуговування; пожежний сигнал у `maintenance` губиться серед заявок | уточнює §6.8 |
| A-08 | Люди на об'єкті й виходи — з хука CF-02; реалізація за замовчуванням над `hr.attendance` (`check_out` у вікні навчання = вихід); access підміняє; перекличка вручну | `hr_attendance` — обов'язкова залежність за §3; access — фаза 4; без перекличк навчання неможливо закрити коректно | — |
| A-09 | Адреси пристроїв не-сповіщувачів: `<loop>.MCP.<nn>`, `<loop>.SND.<nn>`, `2.FLM.<nn>`; LSP id = `loop·10000 + ord·100 + nn` з псевдо-порядковими MCP=90, SND=91, FLM=92 (`1.MCP.01` → 19001); `nn` — порядок у `call_points()`/`sounders()`/`FLAME` у межах шлейфу | iot_sim визначає схему лише для сповіщувачів зон; потрібні унікальні адреси без колізій (Q-08) | — |
| A-10 | Люки димовидалення — 44 записи `f3d.fire.device` типу `smoke_vent` (система `SMOKE-CTRL`, димова зона SZ-n) + модель `f3d.fire.smoke.zone` (8) | дає R-09 і координати для 3D; обладнання base `SMOKE-VENTS` лишається одним записом | — |
| A-11 | Норми — модель `f3d.fire.norm` (20 записів із JSON макета), не `ir.config_parameter` | у нормі є `ref`, `note`, `sources`, одиниця — потрібні у звітах і формах; менеджер править значення з підставою | уточнює §5 (параметри `factory3d.<module>.<param>` — лише для технічних) |
| A-12 | Журнал подій без ротації й без `unlink`; `_log_access=False` | обсяг ≈ 10 000/рік; журнал — документ з обліку СПЗ (Q-13) | — |
| A-13 | Події іскрогасіння — з приросту лічильника ADAM HR 40001 (`count_today`), а не з імпульсу DI0 0,6 с; DI0/DI1 опитуються 2 с як індикатор «зараз» | 0,6 с імпульс не ловиться опитуванням ≥ 1 с; лічильник ADAM апаратний | — |
| A-14 | `test-alarm` без запланованого навчання у вікні 30 хв → навчання створюється автоматично (`origin='panel'`, стан `running`) | тест монтажника — теж подія, яку треба запротоколювати; інженер потім заповнить або скасує | — |
| A-15 | `f3d.fire.device.equipment_id` = обладнання групи base (`FA-<зона>`, `FA-MCP`, `FA-SND`, `FA-FLAME`, `SPARK-1`, `SMOKE-VENTS`); 343 окремих `maintenance.equipment` не створюються | base зафіксував 208 одиниць; заявки ТО йдуть на групу з текстом адреси пристрою (як MR/00036 у демо) | — |
| A-16 | Втрата зв'язку → заявка ТО на `FACP-1` створюється **модулем** (єдиний виняток із CT-05), бо «немає показань» — не поріг сигналу; дедуплікація своя (одна відкрита заявка з `f3d_origin='fire_comm'`) | telemetry FR-12 дає лише `stale`, без заявки | уточнює §6.8 |
| A-17 | Стан зони при `stale`/`lost` — останній відомий + прапор `stale=True` у моделі й `fire.groups[*].stale` у payload; не скидається в `unknown` | охорона має бачити останній стан, а не «невідомо» на всіх 33 зонах | — |
| A-18 | Демо-навчання в хуку (один запис `done`) | показує структуру протоколу й дає виміряні AC для провайдера `drill_active=null` і списку навчань | — |
