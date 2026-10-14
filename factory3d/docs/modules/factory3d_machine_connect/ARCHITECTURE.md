# factory3d_machine_connect — технічне рішення

Версія 0.2 · 14.10.2026 (0.1 — 14.10.2026) · автор: агент-архітектор модуля (хвиля 2) · статус: **чернетка на погодження**.
Зміни: 14.10.2026 — правки за `docs/CONSISTENCY.md` v0.3: X-03 (канал команд — `f3d.command.payload` telemetry 19.0.1.1.0,
CR-01: CM-08, A-14, §2.1, §2.2, §2.5 приклад 3, §2.6, ризики; текстова граматика — запасна; плагіни — `call()`, CM-06),
X-16 (сигнали модуля — `origin='module'`, SPEC Додаток C.2), X-18 (код команд оптимізатора `equipment/CUTOPT/cmd`, §2.4),
X-27 (`machine_state` — `viewer_visible=False`, CM-02), X-32 (пункт «Налаштування верстатів» під «Завод 3D →
Налаштування», sequence 40: §1.2, FR-31), X-57 (тіла запуску сценаріїв у ТК SPEC), X-76 (`equipment/CUTOPT/cmd` і
`equipment/GANTRY-1/stacks` у каталозі iot_sim — `protocol=none`, §2.4); §5.1 — закрито Q-09 (X-03), Q-16 (X-52; CM-06 —
повний перелік ключів-розширень), Q-17 (X-38), частково Q-15 (X-34, X-38, X-43; A-19, A-28 — узгоджено).
Каркас: `docs/ARCHITECTURE.md` (далі «каркас»: §1 принцип, §3 `factory3d_machine_connect ← factory3d_telemetry,
mrp_workorder`, §4 топологія, §5 конвенції й стоп-крани, §6.4 телеметрія, §6.5 плагіни `opcua` і `woodstore`,
§6.6 P-01…P-04, §6.7 переглядач, §6.8 заявки ТО, рішення D-01, D-02, D-04, **D-05** (OPC 40550-1, tapio не в v1),
D-11, §9 питання 2). Специфікація: `docs/modules/factory3d_machine_connect/SPEC.md`.
Спирається на контракти `factory3d_base` CB-01 (домішка, коди `SAW-1`…), CB-03 (зони), CB-05 (`f3d_loc_kind`,
`f3d_capacity` — стоси `PLT-*`), CB-07/CB-08 (паспорти, `get_num`), CB-09 (меню, sequence 40; пункт налаштувань під
`menu_f3d_config` — X-32), CB-10 (групи,
`factory3d.base.environment`), Додаток B base (коди операторів `OP-<РЦ>`); `factory3d_telemetry` CT-01…CT-12
(моделі, інтерфейс плагіна CT-02, схеми адрес CT-03 / Додаток A, API-01…07, правило заявок CT-05, `_f3d_ingest`
CT-10, імпорт каталогу CT-11, локальні джерела CT-12, хук `f3d.push.handler` CT-08); `factory3d_viewer` M-01
(провайдер), M-03 (шина), API-03 (дельта), Додаток A.4/A.5/A.10/A.14; telemetry 19.0.1.1.0 — M-06 `f3d.command.payload`,
`SourcePlugin.call` (CR-01, X-03); «документацію вендора» `factory3d_iot_sim`
SPEC §8.3 (P-01 OPC UA), §8.4.2 (P-02 ADAM-6050), §8.5 (P-03 woodStore API-20…27), §8.6 (P-04 `/jobs`
API-30…34), §9.1 R-14…R-18, §9.3 S-01/S-02, Додаток A (рядки 97–98, 197–334). Рішення автора — **A-xx** (§7),
відкриті питання — **Q-xx** (§5.1), контракти цього модуля — **CM-xx** (§2.1).

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора; `docs/оцінки` в репозиторії ще немає) |
|---|---|---|
| ТР | цей документ + SPEC.md | 32 |
| Архітектура | погодження A-xx/Q-xx з менеджером і авторами telemetry/viewer/iot_sim/energy | 12 |
| Розробка | Odoo-модуль `odoo_addons/factory3d_machine_connect` (моделі 14 + 9 розширень, представлення 34, крони 5, API 1, провайдер переглядача, міграція) — 150; пакет плагінів колектора `services/collector_plugins/machine_connect` (`opcua`, `rest_vendor` з адаптерами `woodstore`/`cutopt`) — 56 | 206 |
| Тестування | юніт-тести Odoo, тести плагінів проти фейкових серверів OPC UA/REST, ТК на емуляторі (`shift`, `machine_fault`, портал, карта розкрою), безпека, продуктивність 35 × 1 с, DEPLOY_TEST | 80 |
| Інструкція | §4 цього документа + README модуля й пакета + CHANGELOG | 10 |
| **Разом** | | **340** |

Факти з тестового сервера timur-o19demo, база `odoo` (перевірено 14.10.2026, лише читання): Odoo 19.0+e-20260926;
установлені `mrp`, `mrp_workorder`, `mrp_workorder_iot`, `quality_mrp_workorder`, `mrp_maintenance`, `mrp_account`,
`hr_attendance`, `iot`, `factory3d_iot_sim`; мова користувачів `uk_UA`, календар «Зміна 1 (07:00–15:30)»
(пн–пт, обід 11:30–12:00, `tz=Europe/Kyiv`). `mrp.workcenter` — 35 (поле `default_capacity` в Odoo 19
**відсутнє**, місткість — `capacity_ids`; стандартні `oee`, `performance`, `blocked_time`, `productive_time` —
за останній місяць, не збережені; `working_state` — збережене обчислення з відкритого запису журналу);
`mrp.workorder` — 199 (стани Odoo 19: `blocked` 87, `ready` 2, `progress` 30, `done` 80; поля `employee_ids`,
`employee_assigned_ids`, `qty_produced`, `qty_producing`, `scrap_ids`, `time_ids`); `mrp.routing.workcenter` — 171
операція (`time_mode='manual'`, `time_cycle_manual` 0,5…6,0 хв/шт: Розкрій 2,2, Пакетний розкрій 0,9,
Крайкооблицювання 1,6, Присадка 2,0, Збирання 6,0, Пакування 3,0, інші 1,5), налагодження `time_start=15` хв на
кожному РЦ (тому `duration_expected` = 15 + хв/шт × к-сть: WO00013 SAW-1 = 15 + 2,2 × 14 = 45,8); `mrp.bom` — 27
(коди «лінія A…D», «фасади F1…F3»). Журнал `mrp.workcenter.productivity` — **184 записи**: 110 «Fully Productive
Time» по завданнях (81 закритий, 29 відкритих — по одному на працюючий РЦ), **73 закриті простої** без завдання
(«Material Availability» 30, «Setup and Adjustments» 26, «Заміна інструменту» 17), **1 відкритий** «Equipment
Failure» на CNC-2 з 09:42 (опис «MR/00031»). Причин втрат 9: стандартні `mrp.block_reason0…7` (англійські назви без
перекладу uk) і демо `factory3d.loss_tool` «Заміна інструменту», `factory3d.loss_break` «Перерва» — **у двох
демо-причин порожня категорія `loss_id`**, тому `loss_type=False` (у 19 `loss_type` — related від категорії;
генератор `odoo_flows.step_losses` писав `loss_type` напряму) — 17 простоїв випадають із підрахунків за типом.
Демо-журнал синтетичний: продуктивні записи починаються до зміни (SAW-1 з 03:04 за Києвом) і перекриваються з
простоями (07:00–07:26). Заявка MR/00031 «Помилка шпинделя осі Z, чекаємо сервісного інженера» (CNC-2, `corrective`,
стадія «In Progress»). Портал: 27 локацій `PLT-01A…PLT-09C` у `WH/Stock/Сировина/Плити/Портал`, 23 кванти
(750 арк.), 23 правила поповнення `min 10 / max 60`, маршрут «Поповнення під портал» (правило pull «Стелажі →
портал», тип «Поповнення під портал» `WH/INT`), переміщення WH/INT/00071 (done), 00072, 00073 (assigned);
плити МО резервуються зі стосів (WH/MO/00233: 4 арк. DSP16-ANT з `PLT-03C`, партія DSP16-ANT-2613-130;
`bom_line_id` у демо-рухах порожній). `stock.scrap` — 0. `maintenance.equipment` GANTRY-1 (id 44) без
`workcenter_id`. Технічних користувачів `f3d*` немає. Моделей `f3d.*` ще немає (хвилі 1–2 не встановлені).

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст: що є в макеті

| Джерело | Що саме | Як використовується |
|---|---|---|
| `plant/layout.py:MACHINES` (рядки 182–250), `STATUS` (251–253), `LINE_Y` | 35 РЦ з типами (`saw`, `saw_book`, `slide`, `vsaw`, `nest`, `edge_robot`, `edge`, `cnc`, `bore`, `dowel`, `sortbot`, `sand`, `autospray`, `uv`, `hinge`, `glue`, `press`, `spray`, `dry`, `asmline`, `asm`, `pack`, `box`, `packline`), лінії A–D (y 5/14/23/32), E (NEST-1); статуси демо: `work` 29, `idle` 5 (`SAW-3`, `EDGE-3`, `ASM-5`, `VSAW-1`, `UV-1`), `stop` 1 (`CNC-2`) | 35 записів `f3d.machine` (R-27 SPEC), очікуваний стан після підключення в ТК-01 |
| `plant/layout.py:GANTRY_*`, `SHEET_COLS_X`, `SHEET_ROWS_Y`, `sheet_slot()` | портал STORETEQ P-500: проліт 15,9 м, 3 колонки × 9 рядів = 27 стосів `PLT-<01-09><A-C>`; ряди 1–8 — на осях ліній стелажів R1–R8, ряд 9 — лише для порталу; кількість у стосі `5·(2 + (7i+3j) mod 11)`, порожній при `(i+2j) mod 7 = 0` (4 стоси), ряди ≥ 8 — МДФ | 27 `f3d.gantry.stack`; ТК-06…ТК-09 |
| `plant/odoo_demo.py:Demo.build_stock` (рядки 158–170) | стос під порталом `capacity=60`, `kind="stack"`, лот `"<товар>-<2609…2613>-<n>"`, резерв ≤ 10 у кожному 4-му стосі; ДСП 18 Бетон ≤ 10 арк. (дефіцит) | звірка стосів R-15, приклади R-15/R-16 SPEC |
| `plant/odoo_demo.py:Demo.build_production` (рядки 238–352) | маршрути A, B, C, D, F1–F3 (операції й РЦ), хв/шт за операцією, `duration_expected = 15 + хв/шт × к-сть`; рівно одне завдання `progress` на працюючому РЦ; CNC-2 `blocked` | правило автостарту «одне завдання в черзі» (R-09), ідеальний цикл для продуктивності OEE (R-13) |
| `plant/odoo_demo.py:Demo.build_workcenters` (рядки 395–430) | причини втрат «Налагодження», «Очікування матеріалу», «Заміна інструменту», «Перерва», «Поломка»; OEE демо `work 0,74…0,91`, `idle 0,38…0,52`, `stop 0,31`; `productive_minutes = round(210 × oee)` (07:00…10:30 = 210 хв); причини простою (`idle_reason`) SAW-3, EDGE-3, ASM-5, VSAW-1, UV-1; MR/00031 CNC-2 | довідник причин (Додаток B SPEC), формула доступності, яка відтворює 0,84 SAW-1 (R-13) |
| `plant/odoo_flows.py:LOSS_STD` (рядок 18), `step_losses` (332–354), `step_calendar` (103–113), `step_routes` (214–288, маршрут «Поповнення під портал»), `step_orderpoints` (290–311, 23 стоси min 10 / max `capacity`) | відповідність укр. назв стандартним причинам Odoo (`Material Availability`, `Setup and Adjustments`, `Equipment Failure`), 73 простої послідовно з 07:00, календар зміни, поповнення порталу | міграція журналу демо без дублювання (R-27), переклади uk, правила поповнення (R-18) |
| `plant/odoo_push.py:run_workorder` (рядки 452–495), `operator` (444–450), `step_finish` (655–683) | старт/стоп завдання від імені оператора `OP-<РЦ>` (`start_employee`/`stop_employee`, інакше `button_start`), відкритий простій «Поломка» блокує CNC-2, таймер завдання зупинено в момент поломки | правило вибору працівника (R-09), блокування РЦ при аварії (R-05) |
| `plant/odoo_pull.py:sync_production` (рядки 117–201) | прогрес завдань за журналом часу до демо-годинника (`minutes_until`), `working_state=blocked` → `status=stop` | провайдер переглядача: живий стан доповнює, а не дублює (R-25) |
| `dist/odoo_demo.json` | `workcenters[SAW-1]`: `status=work`, `oee=0.84`, `productive_minutes=176`, втрати 16 + 10 хв, `current_workorder=WO00013`; `CNC-2`: `oee=0.31`, 65 хв, втрати 11/5/23/48, `maintenance_request=MR/00031`; `locations[PLT-*]`; `sheet_chain` (5 кроків, крок 4 «Склад під порталом»: 23 стоси · 750 арк., крок 5 «портал подає по одному листу») | приклади R-13, провайдер R-25 |
| `viewer/index.html` | режим «OEE верстатів» (рядки 802–806: ≥ 0,75 зелений, ≥ 0,5 жовтий, < 0,5 червоний), KPI «середній OEE за зміну» (1441), картка верстата `wcHtml` (1825–1849: OEE за зміну, продуктивно, оператор `OP-<код>`, `idle_reason`, заявка, поточне завдання, черга, «Втрати часу»), «Ланцюжок плит» | поля, які провайдер доповнює (CM-05), пороги кольорів OEE (параметри `oee_good`, `oee_warn`) |
| `plant/equipment_specs.json` (ролі `beam_saw`, `beam_saw_book`, `nesting_cnc`, `board_storage`, `edgebander*`, `ptp_cnc`, `throughfeed_drilling`, `dowel_inserting`, `sorting_cell`, `case_clamp_*`) | HOMAG SAWTEQ S-310/S-510, CENTATEQ N-510/P-110, STORETEQ P-500 (довжина заготовки 1200–4300 мм), EDGETEQ, DRILLTEQ, SORTBOT, CABTEQ; верстати без інтерфейсу — Altendorf, Striebig, SCM, Orma, Ardesia, Cefla, Blum, Panotec, Robopac, Smipack, Mosca | протокол верстата (OPC UA — HOMAG, I/O — решта), перевірка розмірів листа для карти розкрою (`get_num` не потрібен: ключі не числові) |
| README «Реальне обладнання» | портал переносить по одному листу; стоси ставить навантажувач цілими через ворота зі світловою завісою; поки ворота відчинені, портал у прохід не заходить; ланцюжок плит 1–5 | стан проходів порталу (R-23), поповнення під портал (R-18) |

### 1.2 Ролі й сценарії використання

| Роль (групи) | Що робить | Де в меню |
|---|---|---|
| Оператор верстата (`mrp.group_mrp_user`) | бачить на планшеті «Цех» (`mrp_workorder`), що завдання стартувало саме; при простої обирає причину: стандартна кнопка «Заблокувати» в «Цеху» або форма «Причина простою» з великими кнопками; не натискає «Старт», якщо верстат підключений і автостарт увімкнено | Цех; Завод 3D → Верстати → Простої → «Без причини» |
| Майстер зміни (`mrp.group_mrp_manager`) | дивиться живий стан 35 верстатів, підтверджує або змінює причини простоїв, вирішує долю неповних партій, бачить OEE зміни | Завод 3D → Верстати → Огляд / Простої / OEE |
| Технолог (`group_f3d_manager` + `mrp.group_mrp_manager`) | заводить деталі виробів для карт розкрою, формує карту з МО, відправляє на оптимізацію, випускає план на пилу | Завод 3D → Верстати → Карти розкрою / Деталі виробів |
| Комірник плит / оператор порталу (`stock.group_stock_user`; OP-W5 «Оператор порталу») | бачить стоси під порталом із залишком Odoo й порталу, розбіжності, завдання порталу; запускає поповнення під портал | Завод 3D → Верстати → Портал: стоси / завдання |
| Начальник складу (`stock.group_stock_manager`) | приймає розбіжність стосу інвентаризацією або виправляє стос у woodStore | Портал: стоси → «Розбіжності» |
| Інженер АСУ (`group_f3d_manager`) | налаштовує підключення верстата (джерело, сигнали, режим автостарту, поріг мікрозупинки), довідник повідомлень OPC UA → причина | Завод 3D → Верстати → Налаштування |
| Адміністратор (`group_f3d_admin`) | стоп-крани читання/автостарту/запису, режим карт розкрою, міграція | Завод 3D → Налаштування → Налаштування верстатів (`res.config.settings`, sequence 40 — X-32), Параметри системи |
| Колектор (технічний клієнт, токен telemetry) | плагіни `opcua`, `rest_vendor` читають верстати, портал, оптимізатор; виконують команди; беруть експорт карти розкрою (API-01) | `/f3d/telemetry/*` (telemetry), `/f3d/machine/cutmap/*` |
| Модуль `factory3d_energy` (код) | бере інтервали роботи й налагодження завдань для кВт·год на завдання/МО | CM-03 |

### 1.3 Функціональні вимоги

| ID | Вимога (перевірювана) |
|---|---|
| FR-01 | Сирий стан верстата нормалізується в один з 6 станів `working` (в роботі), `setup` (налагодження), `idle` (очікування), `fault` (аварія), `off` (вимкнено), `nodata` (немає даних): для OPC UA — за `CurrentState` і `CurrentMode` (OPC 40550-1), для I/O — за входами «в роботі»/«аварія» ADAM-6050 (таблиця R-01). |
| FR-02 | Неробочий стан, коротший за поріг мікрозупинки (`micro_stop_s`, 120 с), поглинається станом «в роботі»; аварія і вимкнення фіксуються одразу (R-02). |
| FR-03 | Кожен зафіксований стан пишеться інтервалом у журнал станів `f3d.machine.state.log` (верстат, стан, початок/кінець, завдання, лічильник на початку/кінці) і обчисленим сигналом телеметрії `workcenters/<код>/machine_state` (`kind='state'`). |
| FR-04 | Аварія відкриває запис журналу часу Odoo `mrp.workcenter.productivity` з причиною доступності (підказка або «Поломка»), що блокує робочий центр і закриває таймери завдань; відновлення закриває запис. |
| FR-05 | Очікування, налагодження й вимкнення в межах планового часу зміни довші за поріг створюють простій `f3d.downtime`; після закінчення простою модуль пише закритий запис втрати в `mrp.workcenter.productivity` (налагодження — з завданням) і не блокує робочий центр, поки простій триває. |
| FR-06 | Причину простою вводить оператор (кнопка «Заблокувати» в «Цеху» або форма «Причина простою») чи майстер; запис оператора зливається з простоєм верстата (R-06), причина поширюється на всі записи простою; майстер підтверджує причину (стан `confirmed`). |
| FR-07 | Підказка причини береться з події OPC UA (довідник `f3d.machine.message`: `MessageId` → причина), з режиму `SETUP` («Налагодження») або з черги (завдання РЦ чекає компонентів/попередньої операції → «Очікування матеріалу»); підказка з `auto_apply` ставиться причиною зі станом «потребує підтвердження». |
| FR-08 | Тривога верстата створює заявку ТО через правило telemetry CT-05 на сигналі `workcenters/<код>/alarm`; модуль прив'язує заявку до простою й дописує в неї текст події OPC UA; сигнал стану заявок не створює. |
| FR-09 | Автостарт: коли верстат перейшов у `working`, модуль запускає `mrp.workorder` цього РЦ, якщо (а) завдання верстата (`JobOrderID`) збігається із завданням Odoo, або (б) у режимі `job_or_single` у РЦ рівно одне завдання `ready` і немає `progress`. |
| FR-10 | Автостарт виконується від імені працівника за порядком R-09 (поточний на РЦ сьогодні → оператор `OP-<код>` → працівник верстата → перший дозволений РЦ → без працівника) технічним користувачем «Верстати (автоматично)». |
| FR-11 | Захист від подвійного старту: запуск ідемпотентний (ключ `wo:<id>@<ts>`), не створює другого відкритого таймера, блокування рядка верстата на час переходу; два пакети з тим самим станом не дають двох стартів. |
| FR-12 | Автопауза: аварія закриває таймери завдання одразу, очікування/вимкнення — через `pause_after_min` (10 хв); повернення в `working` відновлює таймер того самого завдання. |
| FR-13 | Лічильник деталей верстата накопичується на активному завданні (`mrp.workorder.f3d_qty_counted`) з обробкою скидання лічильника; у `qty_produced` пишеться при завершенні (режим `finish`) або з тротлінгом (режим `live`). |
| FR-14 | Автозавершення: завдання завершується (`button_finish`), коли завдання верстата змінилося/закінчилося і лічильник ≥ залишку, або (I/O) лічильник ≥ залишку і верстат не працює `finish_idle_s`; неповна партія не завершується й не розбиває МО — ставиться прапор «неповна партія» і діяльність майстру. |
| FR-15 | Стоп-крани: `factory3d.machine_connect.read_enabled` (журнал станів і простоїв), `auto_start_enabled` (старт/пауза/завершення завдань), `write_enabled` (команди на верстати, портал, оптимізатор); на верстаті — `read_enabled`, `auto_start_mode`, `auto_finish`, `auto_pause`; `neutralize.sql` вимикає все. |
| FR-16 | OEE за фактом рахується за зміну й довільний період: доступність = час роботи / плановий час, продуктивність = Σ(ідеальний цикл × к-сть) / час роботи із завданням, якість = придатні / усі; плановий час — календар РЦ мінус планові простої; «немає даних» виключається з планового часу з показником повноти. |
| FR-17 | Результати OEE зберігаються по верстату й зміні `f3d.oee.shift` (поточна зміна — оновлення кожні 5 хв, минулі — закриті); звіти: зведена/графік за РЦ/лініями/датами, Парето втрат, kanban «Огляд верстатів» з кольором за порогами переглядача. |
| FR-18 | Стоси порталу: 27 записів `f3d.gantry.stack` із залишком Odoo (`stock.quant`), залишком порталу (woodStore P-03), «подано, але не списано» і розбіжністю; стала розбіжність (`stack_diff_confirm_min`) → стан «розбіжність» і діяльність начальнику складу з діями «прийняти з порталу» (інвентаризація) / «виправити портал» (команда). |
| FR-19 | Завдання порталу `f3d.gantry.job`: створення з МО/карти розкрою (подати N листів товару зі стосу на стіл SAW-x/NEST-1), відправка в woodStore командою, дзеркало завдань порталу з подій (у т. ч. створених не з Odoo, прив'язка до МО за `external_ref`), стани до «виконано». |
| FR-20 | Списання плит: виконане завдання порталу ставить у сировинному русі МО рядки зі стосу й партії, з яких портал фактично взяв листи (`picked=True`). |
| FR-21 | Поповнення під портал: стос нижче мінімуму правила (10) → стандартне поповнення (`action_replenish`, за параметром — автоматично); виконане WH/INT у стос `PLT-*` → команда оновлення стосу у woodStore (або діяльність, якщо запис вимкнено). |
| FR-22 | Стан порталу (`idle/moving/picking/placing/blocked/error`), відкриті проходи (ворота зі світловою завісою), тривоги, цикли й вакуум — сигнали `equipment/GANTRY-1/*` і картка порталу. |
| FR-23 | Деталі виробу `f3d.cut.part` на специфікацію (назва, довжина × ширина, к-сть на виріб, роль матеріалу, текстура, крайки, програма ЧПК) з імпортом CSV; розміри листа — поля товару-плити. |
| FR-24 | Карта розкрою `f3d.cut.map` з МО: рядки деталей × к-сть МО за матеріалом, CSV у форматі P-04 (вкладення), перевірка розмірів листа. |
| FR-25 | Оптимізація: режим `collector` (CSV → оптимізатор через колектор, план: аркуші, відхід %, довжина різу, час; MPR для ЧПК — вкладення) або `manual` (завантажити CSV, імпортувати план JSON); порівняння аркушів плану з потребою МО. |
| FR-26 | Випуск плану на верстат: `release` створює `JobOrder` верстата й завдання порталу на `total_sheets`; ідентифікатор `cj-…` зіставляється з завданням Odoo для автостарту. |
| FR-27 | Плагін колектора `opcua` (asyncua): підписки на стани/лічильники, події (`WwBaseEventType`, `WwAlarmConditionType`), резолв простору імен за URI, переп'єднання з бекофом і відновленням підписок, безпека `None`/`SignAndEncrypt` з сертифікатами, виклики методів `JobOrderControl` лише при всіх запобіжниках запису. |
| FR-28 | Плагін колектора `rest_vendor` з адаптерами `woodstore` (статус, стоси, завдання, події, команди) і `cutopt` (завантаження списку деталей, статус, план, MPR, випуск) та загальним опитуванням `path/json_path`. |
| FR-29 | Дані: 35 верстатів, 22 джерела (15 OPC UA, 4 ADAM, 2 REST, 1 локальне), 207 сигналів (140 з каталогу емулятора + 67 нових), 10 повідомлень OPC UA → причини, причина «Не вказано», переклади причин uk, розміри 7 листових товарів. |
| FR-30 | Міграція демо: 73 закриті простої й відкрита аварія CNC-2 стають простоями `f3d.downtime` без створення нових записів журналу часу; виправлення категорії двох демо-причин; прив'язка MR/00031; повторний запуск нічого не дублює. |
| FR-31 | Меню «Завод 3D → Верстати» (`sequence=40`): Огляд, Простої, OEE, Журнал станів, Портал (стоси, завдання), Карти розкрою, Деталі виробів, Налаштування (довідники); пункт параметрів модуля «Налаштування верстатів» (`res.config.settings`) — під «Завод 3D → Налаштування» (`factory3d_base.menu_f3d_config`, `sequence=40`, X-32). |
| FR-32 | Права: читання — `group_f3d_user`; причини — `mrp.group_mrp_user`; підтвердження, неповні партії — `mrp.group_mrp_manager`; налаштування верстатів, карти розкрою, деталі — `group_f3d_manager`; стоп-крани — `group_f3d_admin`; розбіжності стосів — `stock.group_stock_manager`. |
| FR-33 | Провайдер переглядача `f3d.viewer.provider.machines` (`_f3d_sequence=75`) доповнює `workcenters[код]` живим станом, OEE (A×P×Q), поточним простоєм і лічильником, `equipment["GANTRY-1"]` — станом порталу, `locations["PLT-*"]` — залишком порталу, `productions[]` — картою розкрою й завданням порталу, `sheet_chain` — завданнями порталу; не дублює полів вбудованих провайдерів. |
| FR-34 | Контракт для energy: інтервали роботи й налагодження кожного завдання (`_f3d_wo_intervals`) і хвилини роботи/налагодження на `mrp.workorder`. |
| FR-35 | API-01 `GET /f3d/machine/cutmap/<id>/export` віддає колектору CSV карти розкрою лише з токеном колектора й одноразовим токеном карти (TTL 10 хв). |
| FR-36 | Крони: такт верстатів (1 хв: мікрозупинки, автопауза, автозавершення, межі зміни, «працює без завдання»), OEE (5 хв), портал (1 хв: звірка, відправка, поповнення), карти розкрою (1 хв: статус оптимізації), ротація (щодня). |

### 1.4 Межі: що не входить

- tapio (хмара HOMAG) — не в v1 (D-05); маршрут `tapio` хука `f3d.push.handler` не реалізується.
- Планування й перепланування МО/завдань (Gantt, вибір альтернативного РЦ) — стандарт Odoo; модуль лише стартує,
  ставить на паузу й завершує вже заплановані завдання.
- Розбиття МО на часткові партії (backorder) автоматично — ні (A-10); рішення приймає майстер стандартними
  засобами Odoo.
- Сирі ряди 1 с у `f3d.reading` — ні (D-11): у телеметрію йдуть лише зміни станів і показання за `store_period_s`;
  журнал верстата — інтервали станів.
- Енергія на завдання (кВт·год, вартість) — `factory3d_energy` (цей модуль дає інтервали, CM-03).
- Власний OPC UA сервер, генерація програм woodWOP, власний оптимізатор розкрою — ні; MPR лише зберігається.
- Облік деталей поштучно (етикетки, сортування SORTBOT за деталями) — ні; лічильник — кількість циклів/деталей
  верстата на завдання.
- Зміна OWL-інтерфейсу планшета «Цех» (`mrp_workorder`) — ні; оператор користується стандартним блокуванням і
  окремою формою «Причина простою» (V-08).
- Друга зміна, графік вихідних — календар РЦ у стандарті (iot_sim Q-11).
- Інтеграція з Odoo IoT Box (`mrp_workorder_iot`, тригери `iot.trigger` на РЦ) — не чіпається; модуль з нею не
  конфліктує (різні моделі).

## 2. Технічна реалізація

### 2.1 Місце в системі

`depends`: `factory3d_telemetry` (через нього `factory3d_base`, `maintenance`, `mail`, `mrp`, `mrp_maintenance`,
`stock`, `hr`), `mrp_workorder` (планшет «Цех», `start_employee`/`stop_employee`, `employee_ids` на завданні).
`factory3d_viewer` і `factory3d_iot_sim` — **не** в `depends`: провайдер переглядача — звичайна `AbstractModel` з
іменем `f3d.viewer.provider.machines` без `_inherit` моделей viewer (viewer M-01 збирає провайдери за префіксом
імені, A-18); шина — `if 'f3d.viewer.event' in env`. Каталог емулятора (`f3d.sim.signal`) не потрібен: адреси
сигналів — у даних модуля (Додаток C SPEC).

Що **бере** модуль: CB-01 (`f3d_code` РЦ/обладнання/локацій/працівників, `search_f3d`), CB-03 (`f3d_zone_id` РЦ для
групування дашборда), CB-05 (`f3d_loc_kind='stack'`, `f3d_capacity=60` стосів `PLT-*`), CB-09 (меню 40), CB-10
(групи, `factory3d.base.environment` для умовчань стоп-кранів), Додаток B base (оператор `OP-<код>`);
telemetry CT-01 (моделі), CT-02 (інтерфейс плагіна, entry points, `call()` — CR-01), CT-03/Додаток A (`opcua`: `nodeid`, `mode`,
`sampling_ms`, `map`; `rest_vendor`: `method`, `path`, `json_path`, `query`, `map`; `modbus_tcp` для ADAM), CT-04
(API-01…07 — колектор), CT-05 (заявки з тривог), CT-08 (`f3d.push.handler`), CT-10 (`_f3d_ingest`), CT-12
(локальний тип джерела для обчислених станів), M-06 (`f3d.command` — канал команд; з 19.0.1.1.0 — `payload`/`result_data`,
CR-01, X-03), M-11 (маршрути подій);
viewer M-01 (контракт провайдера), M-03 (`_notify`), Додаток A.4, A.5, A.10, A.14; iot_sim P-01…P-04 (адреси,
формати), S-01/S-02 (стендові сценарії).

Контракти, які **задає** цей модуль (посилатися як `factory3d_machine_connect CM-xx`):

| ID | Контракт | Споживачі |
|---|---|---|
| CM-01 | Моделі `f3d.machine` (M-01), `f3d.machine.state.log` (M-02), `f3d.downtime` (M-03), `f3d.machine.event` (M-04), `f3d.machine.message` (M-05), `f3d.oee.shift` (M-06), `f3d.gantry.stack` (M-07), `f3d.gantry.job` (M-08), `f3d.cut.part` (M-09), `f3d.cut.map` (M-10), `f3d.cut.map.line` (M-11) з іменами полів SPEC §2 | energy, viewer, звіти |
| CM-02 | Нормалізовані стани верстата `working\|setup\|idle\|fault\|off\|nodata` (R-01) і часовий ряд у телеметрії — сигнал `workcenters/<код>/machine_state` (`kind='state'`, `states` = 6 значень, джерело `MC-DERIVED` локального типу `f3d_machine`, CT-12; `viewer_visible=False` — у payload переглядача `machine_state` ставить провайдер CM-05, X-27) | energy, viewer, звіти, bms (освітлення за роботою верстатів — за потреби) |
| CM-03 | Енергія на завдання: `env['f3d.machine']._f3d_wo_intervals(workorders, date_from=None, date_to=None) -> dict[int, list[tuple[datetime, datetime, str]]]` (UTC naive, стани `working` і `setup`, обрізані вікном) і збережені `mrp.workorder.f3d_run_min`, `f3d_setup_min`; інтервали без завдання — `_f3d_wc_intervals(workcenter, date_from, date_to)` | `factory3d_energy` (кВт·год і вартість на завдання/МО = ∫ `energy/consumers/<код>/p_now` по інтервалах) |
| CM-04 | OEE: `f3d.oee.shift` (поля `availability`, `performance`, `quality`, `oee`, хвилини за категоріями, `coverage`) і метод `f3d.machine._f3d_oee(date_from, date_to) -> dict` (R-13) | viewer, energy (питома енергія на придатну деталь — за потреби), звіти |
| CM-05 | Провайдер переглядача `f3d.viewer.provider.machines` (`_f3d_sequence=75`, `_f3d_sections=()`): додаткові ключі `workcenters[код].machine_state/state_since/availability/performance/quality/downtime/pieces_shift/link/online`, перекриття `oee` і `status` (R-25); `equipment["GANTRY-1"].gantry`; `locations["PLT-*"].gantry`; `productions[].cut_map`, `productions[].supply.gantry`; `sheet_chain.steps[4].stock` | viewer |
| CM-06 | Пакет плагінів колектора `f3d_collector_mc` (`services/collector_plugins/machine_connect`), entry points `factory3d_collector.plugins`: `opcua = f3d_collector_mc.opcua:OpcUaPlugin`, `rest_vendor = f3d_collector_mc.rest_vendor:RestVendorPlugin` (адаптери `woodstore`, `cutopt`, `generic`); ключі-розширення адрес/параметрів (CT-03 дозволяє; довідково в telemetry Додатку A — X-52): `opcua.address.ns_uri`, `events`, `io`, `call`, `job_select`; `opcua.params.ns_uri`, `app_uri`, `heartbeat_s`; `rest_vendor.params.vendor`, `events_period_s`, `stacks_period_s`, `jobs_period_s`; `rest_vendor.address.cmd`, `default`, `io`; команди плагіни виконують методом `call(signal, payload) -> dict` (CR-01, X-03), `write()` — запасна текстова граматика CM-08 | telemetry (колектор), access (може вживати `generic` адаптер) |
| CM-07 | Маршрути подій колектора → Odoo (telemetry API-05): `mc_opcua` (EV-01 — подія/тривога OPC UA), `mc_woodstore` (EV-02 — події, стоси, завдання порталу), `mc_cutopt` (EV-03 — стан, план, MPR оптимізатора); обробник `f3d.push.handler.machine_connect` | telemetry |
| CM-08 | Команди Odoo → пристрої — корисне навантаження `f3d.command.payload` (telemetry M-06, CR-01, 19.0.1.1.0, X-03): схеми CMD-01 `JobOrderControl` верстата (`{"method", "job", "qty", "ref", "priority"}`), CMD-02 портал (`{"op": "feed"\|"cancel"\|"stack", …}`), CMD-03 оптимізатор (`{"op": "upload"\|"status"\|"release"\|"mpr", …}`) і об'єкти результату `call()` → `f3d.command.result_data` (SPEC R-21); текстова граматика `f3d.command.text` (≤ 64 символи, роздільник `;`) — запасна: `write()` плагінів її приймає, Odoo створює текстову команду лише без поля `payload` | telemetry (колектор) |
| CM-09 | Причини втрат: стандартні `mrp.block_reason0/1/2` з перекладами uk, `factory3d_machine_connect.loss_unknown` «Не вказано» (доступність), поле `mrp.workcenter.productivity.loss.f3d_planned` (плановий простій — не входить у плановий час); поля `mrp.workcenter.productivity.f3d_downtime_id`, `f3d_source`, `f3d_auto` | viewer (втрати в картці), energy |

### 2.2 Архітектурна схема

```
 мережа цеху / f3d_sim                                   docker compose поруч з Odoo
┌──────────────────────────────┐   OPC UA 4840 (opc.tcp)  ┌──────────── services/collector (telemetry) ─────────────────────┐
│ HOMAG ×15 (P-01): SAWTEQ,    │◄── subscribe/events/call ─│ f3d_collector_mc.opcua    (asyncua 1.1.6; сесія на endpoint,    │
│  CENTATEQ, EDGETEQ, DRILLTEQ,│                           │   підписки DataChange+Event, переп'єднання, JobOrderControl)    │
│  SORTBOT, CABTEQ             │   Modbus TCP 502          │ modbus_tcp (telemetry)    ADAM-6050 u80…u83 (P-02), опит. 1 с   │
│ ADAM-6050 IO-1…IO-4 (P-02)   │◄── poll fc 2 / fc 3 ──────│ f3d_collector_mc.rest_vendor                                    │
│ woodStore STORETEQ P-500     │   HTTP 8082 X-Api-Key     │   ├ woodstore: /status 5 с, /stacks 30 с, /events 2 с, команди  │
│  (P-03)                      │◄── GET/POST/PATCH/DELETE ─│   └ cutopt: POST /jobs (CSV), GET /jobs/{id}, /plan, /mpr,      │
│ intelliDivide/woodWOP (P-04) │   HTTP 8083 X-Api-Key     │            POST /release                                        │
└──────────────────────────────┘◄───────────────────────────│ core (telemetry): scheduler, buffer, odoo_client, commands      │
                                                             └───────┬─────────────────────────────────────▲──────────────────┘
                      push (API-02) · status (API-03) · event (API-05: mc_*) · commands (API-06/07) │    │ GET API-01 cutmap export
                                                                     ▼                                     │ (Bearer + t=…)
┌───────────────────────────────── Odoo 19 + factory3d_machine_connect ─────────────────────────────────────┴──────────────────┐
│ f3d.signal._f3d_ingest (override, super() перше) ─► f3d.machine._f3d_dispatch(readings)                                     │
│    R-01 нормалізація ─► R-02 мікрозупинки ─► f3d.machine.state.log (інтервали) + workcenters/<код>/machine_state (CT-10)   │
│    ├─► R-05 простій f3d.downtime ─► mrp.workcenter.productivity (втрата; аварія — відкрита й блокує РЦ)                    │
│    ├─► R-09…R-12 автостарт/пауза/завершення mrp.workorder (start_employee / end_all / button_finish) як «Верстати (авто)» │
│    └─► R-11 лічильник ─► mrp.workorder.f3d_qty_counted ─► qty_produced                                                     │
│ f3d.push.handler.machine_connect: mc_opcua ─► f3d.machine.event (підказка R-07) · mc_woodstore ─► f3d.gantry.stack/job      │
│                                    mc_cutopt ─► f3d.cut.map (план, MPR — вкладення)                                        │
│ mrp.workcenter.productivity.create (override) ─► R-06 злиття з причиною оператора                                         │
│ maintenance.request (telemetry CT-05 з сигналу alarm) ─► R-08 прив'язка до простою, текст події                           │
│ f3d.gantry.job / f3d.cut.map / JobOrder ─► f3d.command (payload CMD-01…03) ─► колектор (API-06) ─► пристрій             │
│ крони: такт 1 хв · OEE 5 хв (f3d.oee.shift) · портал 1 хв · карти 1 хв · ротація                                        │
│ f3d.viewer.provider.machines (75) ─► payload переглядача; f3d.viewer.event._notify('mrp.workcenter', [код], 'state')     │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

Потоки: (1) верстати й портал → колектор (підписки OPC UA, опитування Modbus/REST); (2) колектор → Odoo
показаннями (API-02) і подіями (API-05); (3) Odoo → пристрої лише командами `f3d.command` (API-06/07) при всіх
запобіжниках запису; (4) Odoo → колектор: експорт карти розкрою (API-01 цього модуля, читання); (5) Odoo → переглядач
через шину.

### 2.3 Нові й розширені об'єкти

| Об'єкт | Призначення | Пише | Читає |
|---|---|---|---|
| `f3d.machine` (M-01) | підключення РЦ: протокол, сигнали, режими автостарту, пороги; живий стан, поточні інтервал/простій/завдання, сирі значення | дані, інженер АСУ, диспетчер R-01…R-12 | дашборд, провайдер, energy |
| `f3d.machine.state.log` (M-02) | інтервали станів (журнал часу верстата) з завданням і лічильником | диспетчер, міграція (ні — історія демо не будується) | OEE, energy, «Журнал станів» |
| `f3d.downtime` (M-03) | простій: причина, джерело причини, стан класифікації, підказка, подія, заявка, записи журналу часу | диспетчер, оператор, майстер, міграція (74) | журнал простоїв, OEE (Парето), провайдер |
| `f3d.machine.event` (M-04) | подія/тривога OPC UA (`MessageId`, категорія, текст) | обробник `mc_opcua` | підказки, заявки, журнал |
| `f3d.machine.message` (M-05) | довідник `MessageId` → причина втрати, автоприйняття | дані (10), інженер АСУ | R-07 |
| `f3d.oee.shift` (M-06) | OEE верстата за зміну: хвилини, кількості, A/P/Q/OEE, повнота | крон R-14 | звіти, дашборд, провайдер, energy |
| `f3d.gantry.stack` (M-07) | стос під порталом: залишок Odoo, порталу, «подано не списано», розбіжність | обробник `mc_woodstore`, крон | «Портал: стоси», провайдер |
| `f3d.gantry.job` (M-08) | завдання порталу: подача листів зі стосу на стіл РЦ | технолог/автоматика (з МО, карти), обробник подій | «Портал: завдання», списання R-17 |
| `f3d.cut.part` (M-09) | деталь виробу для розкрою (на специфікацію) | технолог, імпорт CSV | карта розкрою |
| `f3d.cut.map` (M-10), `f3d.cut.map.line` (M-11) | карта розкрою з МО: деталі, CSV, план, MPR, випуск | технолог, обробник `mc_cutopt` | МО, завдання, провайдер |
| `mrp.workcenter` (+M-12) | `f3d_machine_id`, related стан/OEE, кнопка «Верстат» | — | форми, дашборд |
| `mrp.workorder` (+M-13) | `f3d_qty_counted`, `f3d_auto_started`, `f3d_partial_hold`, `f3d_run_min`, `f3d_setup_min`, карти й завдання порталу | диспетчер | «Цех», energy |
| `mrp.production` (+M-14) | лічильники й кнопки карт розкрою / завдань порталу; «Створити карту розкрою», «Подати плити порталом» | технолог | — |
| `mrp.workcenter.productivity` (+M-15) | `f3d_downtime_id`, `f3d_source`, `f3d_auto`; `create` — злиття R-06 | стандарт + диспетчер | OEE, viewer |
| `mrp.workcenter.productivity.loss` (+M-16) | `f3d_planned` | дані | OEE |
| `product.template` (+M-17) | `f3d_sheet_length_mm`, `f3d_sheet_width_mm`, `f3d_thickness_mm` | хук (7 товарів), технолог | карта розкрою |
| `f3d.signal` (+M-18) | перевизначення `_f3d_ingest` і `_mark_stale` (super() перше) | — | диспетчер |
| `f3d.source` (+M-19) | `selection_add` типу `f3d_machine` (локальний, CT-12) | дані | — |
| `f3d.command` (+M-20) | `f3d_machine_id`, `f3d_gantry_job_id`, `f3d_cut_map_id`; реакція на `done/failed` | модуль | колектор |
| `f3d.push.handler.machine_connect` (M-21) | маршрути `mc_opcua`, `mc_woodstore`, `mc_cutopt` | — | telemetry API-05 |
| `f3d.viewer.provider.machines` (M-22) | провайдер переглядача (75) | — | viewer |
| `res.config.settings` (+M-23) | стоп-крани й параметри | адміністратор | модуль |
| `f3d.downtime.reason.wizard` (M-24), `f3d.cut.plan.import.wizard` (M-25), `f3d.cut.part.import.wizard` (M-26) | причина простою на планшеті; ручний імпорт плану; імпорт деталей | оператор, технолог | — |
| `stock.picking` (+M-27) | після `_action_done` поповнення стосу `PLT-*` → команда оновлення стосу | стандарт | — |
| `maintenance.request` (+M-28) | `create`: заявка з сигналу `workcenters/*/alarm` → простій, текст події | telemetry R-05 | — |

### 2.4 Інтеграції

| P-xx / канал | Пристрої | Протокол, адреса на стенді | Напрямок | Частота | При недоступності |
|---|---|---|---|---|---|
| P-01 | SAW-1…3, NEST-1, EDGE-1…3, CNC-1…4, BORE-1, DOWEL-1, SORT-1, ASMLINE-1 (15) | OPC UA `opc.tcp://iot-sim:4840/f3d/`, простір `http://todo.ltd/f3d/iot_sim/instances/` (індекс резолвиться за URI), вузли `<C>.State.Machine.Overview.CurrentState/CurrentMode`, `…Flags.Alarm`, `…Values.RelativePiecesOut`, `<C>.JobManagement.JobOrderControl.JobOrderList`, `<C>.Events` (iot_sim §8.3.2–8.3.3); 15 джерел `UA-<C>` (джерело = верстат, A-14 telemetry), одна сесія на endpoint | підписка DataChange (1 с) і Event; виклик методів (запис) | за зміною; `publishing_interval_ms=1000` | бекоф 1→60 с, повторне створення підписок; вузли з `Bad_*` → `q='bad'`; усі вузли джерела погані → джерело `error`; сигнали `stale` (telemetry R-07) → верстат `nodata` (R-03 SPEC) |
| P-02 | SLIDE-1, VSAW-1, SAND-1, PRESS-1, GLUE-1, SPRAY-1, AUTOSPRAY-1, DRY-1, UV-1, HINGE-1, BOX-1, PACK-1, PACK-2, PACKLINE-1, ASM-1…6 (20) | Modbus TCP `iot-sim:502`, unit 80…83 (ADAM-6050 IO-1…IO-4): DI(2m) «в роботі», DI(2m+1) «аварія» (fc 2, PDU `2m`, `2m+1`), лічильник DI(2m) HR 40001+4m (fc 3, PDU `4m`, u32, `wordorder=little`) — iot_sim §8.4.2; плагін `modbus_tcp` telemetry | опитування | стан/аварія 1 с, лічильник 5 с | як у telemetry R-19; `stale` → `nodata` |
| P-03 | GANTRY-1 + 27 стосів | REST `http://iot-sim:8082`, `X-Api-Key` (`F3D_WOODSTORE_KEY`): API-20 `/api/v1/status`, API-21 `/stacks`, API-24 `/jobs`, API-27 `/events?since=`; команди API-23 PATCH стос, API-25 POST завдання, API-26 DELETE (сигнал `equipment/GANTRY-1/cmd`); `equipment/GANTRY-1/stacks` обчислює модуль зі стосів API-21 на `MC-DERIVED` (у каталозі iot_sim — `protocol=none`, X-76) | опитування + події + команди | статус 5 с, події 2 с, стоси 30 с (і лише при зміні хешу — подія) | бекоф; `error` джерела; стоси `unknown` через 10 хв без даних; завдання `sent` без підтвердження 10 хв → `error` |
| P-04 | оптимізатор розкрою (intelliDivide) і програми (woodWOP MPR) | REST `http://iot-sim:8083`, `X-Api-Key` (`F3D_CUTOPT_KEY`): API-30 POST `/jobs` (multipart CSV), API-31 GET `/jobs/{id}`, API-32 `/plan`, API-33 `/release`, API-34 `/mpr` | лише команди (CMD-03, сигнал `equipment/CUTOPT/cmd` — X-18; у каталозі iot_sim — `protocol=none`, X-76) і події `mc_cutopt` | на запит (крон 1 хв для `optimizing`) | команда `failed` → карта `error` з текстом; ручний режим (FR-25) |
| telemetry API-02/03/05/06/07 | — | Bearer токен колектора `COL-MAIN` | колектор ↔ Odoo | push 5 с, події при надходженні, команди 5 с (лише при `write_enabled` telemetry) | буфер колектора (telemetry R-19) |
| API-01 цього модуля | — | `GET /f3d/machine/cutmap/<id>/export?t=<одноразовий>` з Bearer токеном колектора | колектор → Odoo (читання) | на команду `upload` | `401/403/404/409/410` → команда `failed` |
| Шина переглядача | — | `f3d.viewer.event._notify` (viewer M-03), `kind='state'` (РЦ), `'stock'` (стоси), `'doc'` (МО) | Odoo → переглядач | при зміні (одне повідомлення на транзакцію) | без viewer — нічого |

### 2.5 Потік даних від пристрою до екрана

Приклад 1 — автостарт SAW-1 (P-01, режим емулятора `scenario`, автостарт увімкнено). 1) О 09:55:00 (Київ) емулятор
ставить у `SAW-1.JobManagement.JobOrderControl.JobOrderList[0]` завдання `JobOrderID="WO00013"` (`PlannedOrderQuantity`
14, `OrderNumbers=["WH/MO/00233"]`) і переводить `CurrentState` 2 → 3 (WORKING), `CurrentMode=1` (AUTOMATIC).
2) Плагін `opcua` отримує DataChange і дає `Reading(code="workcenters/SAW-1/job", text="WO00013")`,
`Reading("workcenters/SAW-1/state", value=3, text="WORKING")` з `ts=06:55:00Z`. 3) За ≤ 5 с колектор шле
`POST /f3d/telemetry/push`; telemetry `_f3d_ingest` пише `last_*`, зберігає показання стану (зміна тексту), повертає
`changed_codes`. 4) Перевизначення `_f3d_ingest` цього модуля після `super()` групує показання з префіксом
`workcenters/` за верстатом → `f3d.machine(SAW-1)._f3d_dispatch`: сирий стан WORKING/AUTOMATIC → `working` (R-01);
перехід у `working` фіксується одразу (R-02): інтервал `idle` закривається о 09:55:00, відкривається `working` з
`pieces_start=0`; простій очікування (якщо був ≥ 120 с) закривається й пише закриту втрату. 5) Автостарт (R-09):
`WO00013` → `mrp.workorder(13)`, РЦ збігається, стан `ready`; працівник — Олег Мельник (`OP-SAW-1`, дозволений на РЦ);
`wo.with_user(user_f3d_machine).start_employee(2)` → стандарт створює продуктивний запис журналу часу, завдання
`progress`; ключ `wo:13@2026-10-12T06:55:00` зберігається на верстаті. 6) Сигнал `workcenters/SAW-1/machine_state =
"working"` пишеться через `_f3d_ingest(src='module')`; `f3d.viewer.event._notify('mrp.workcenter', ['SAW-1'],
'state')`. 7) Переглядач запитує дельту: провайдер production (30) дає `workcenters["SAW-1"]` (`status=work`,
`current_workorder=WO00013`), провайдер machines (75) додає `machine_state="working"`, `state_since="… 09:55"`,
`pieces_shift`, `oee` зміни. 8) Лічильник `RelativePiecesOut` росте кожні 2,2 хв → `f3d_qty_counted` 1…14; о 10:25:48
емулятор знімає завдання (`JobOrderList` порожній, `job=""`) і переходить у READY: завдання змінилося і `14 ≥ 14` →
`qty_produced=14`, `stop_employee([2])`, `button_finish()` (R-12); наступне завдання МО (EDGE-1) стає `ready`.

Приклад 2 — аварія CNC-2 (S-02 `machine_fault device=CNC-2 reason=spindle`). Емулятор: `Flags.Error=True`,
`CurrentState=ERROR(4)`, подія `WwAlarmConditionType` `MessageId="E0421"`, «Помилка шпинделя осі Z», `Severity=1000`.
Плагін: показання `state=4/ERROR`, `alarm=1/on` і подія `mc_opcua` (EV-01). Odoo: стан `fault` фіксується одразу →
`f3d.downtime` (стан `fault`, підказка «Поломка» з `f3d.machine.message(E0421)`, `auto_apply` → причина «Поломка»,
`reason_state='to_confirm'`) → відкритий запис `mrp.workcenter.productivity` (`loss_id=mrp.block_reason1`,
`description="E0421 Помилка шпинделя осі Z"`, `f3d_auto=True`) і `button_block()` → таймери WO00051 закриті,
`working_state='blocked'`. Telemetry на сигналі `workcenters/CNC-2/alarm` (`alarm_states=["on"]`) створює заявку
«Присадка ЧПК B: аварія верстата» (R-05 telemetry); `maintenance.request.create` цього модуля прив'язує її до простою
і дописує «Подія верстата: E0421 Помилка шпинделя осі Z (09:42)». У 3D CNC-2 червоний, `status=stop`, у картці —
простій «Поломка · 48 хв». Після `clear`: `CurrentState=READY`, далі WORKING → запис втрати закривається, простій
закритий, таймер WO00051 відновлено (R-10).

Приклад 3 — завдання порталу для WH/MO/00233 (4 арк. DSP16-ANT зі стосу PLT-03C на SAW-1). Технолог натискає в МО
«Подати плити порталом» (або карта розкрою випущена): `f3d.gantry.job` ПОРТ/00007 `feed`, стос `PLT-03C` (з
резерву руху МО), ціль `SAW-1`, 4 арк., `external_ref=WH/MO/00233` → крон порталу створює `f3d.command` на сигналі
`equipment/GANTRY-1/cmd` з `payload` `{"op": "feed", "stack": "PLT-03C", "target": "SAW-1", "sheets": 4, "product":
"DSP16-ANT", "priority": 5, "ref": "WH/MO/00233"}` (CR-01, X-03; при всіх запобіжниках) → колектор: `call()` плагіна
`rest_vendor` → `POST /api/v1/jobs` → `result_data` `{"id": "wj-00412", "state": "queued"}` → завдання `queued`; події woodStore `job_started`,
`sheet_placed` ×4, `job_finished` → `done=4`, `done`; списання: рядок руху МО 128 = `PLT-03C`, партія
DSP16-ANT-2613-130, 4 арк., `picked=True` (R-17); стос: портал 21 → 17, Odoo 21 (не списано, МО не закрите),
«подано не списано» 4 → очікуване 17, розбіжність 0 (R-15).

### 2.6 Безпека

- **Групи** (CB-10 + стандартні): `group_f3d_user` — читання всіх моделей модуля; `mrp.group_mrp_user` — причина
  простою (поля `loss_id`, `note`, майстер M-24), створення завдання порталу з МО; `mrp.group_mrp_manager` —
  підтвердження причин, зняття «неповної партії», скасування завдань порталу; `group_f3d_manager` — `f3d.machine`,
  `f3d.machine.message`, `f3d.cut.part`, `f3d.cut.map`; `stock.group_stock_manager` — дії розбіжності стосу;
  `group_f3d_admin` — стоп-крани, повтор міграції, ротація.
- **Стоп-крани** (каркас §5, CB-10): `factory3d.machine_connect.read_enabled` (умовчання `environment == 'test'`;
  `False` — диспетчер ігнорує показання, журнал не пишеться, telemetry показання все одно зберігає),
  `auto_start_enabled` (`False` на проді й тесті після установки — «перший тиждень лише читання»),
  `write_enabled` (`False`); на верстаті `read_enabled`, `auto_start_mode`, `auto_finish`, `auto_pause`. Команда на
  пристрій створюється лише при **п'яти** запобіжниках: `machine_connect.write_enabled`, `telemetry.write_enabled`,
  `f3d.source.write_enabled`, `f3d.signal.write_enabled`, у колектора `F3D_WRITE_ENABLED=1`.
- **Технічний користувач** `factory3d_machine_connect.user_f3d_machine` «Верстати (автоматично)»: `active=False`
  (не займає ліцензію, не входить в інтерфейс), групи `mrp.group_mrp_user`, `stock.group_stock_user`,
  `group_f3d_user`; автодії виконуються `with_user(user_f3d_machine)`, щоб у журналі часу й чатері було видно
  «хто» (A-21).
- **API-01**: `auth="public"`, `csrf=False`; Bearer токен колектора (`f3d.collector._authenticate`, telemetry) +
  одноразовий токен карти (`secrets.token_hex(8)`, у базі sha256, TTL 600 с, стирається після видачі); інакше
  `401/403/410`. Жодних інших даних (лише CSV однієї карти).
- **Команди**: поля `payload` CMD-xx (CR-01, X-03) валідуються за схемою й регулярними виразами SPEC R-21 (точний
  набір ключів, керівні символи заборонені; у запасній текстовій граматиці — також `;` і довжина ≤ 64); коди
  стосів/РЦ — лише наявні `f3d_code`; плагін повторно валідує і відмовляє (`failed: bad_command`) до будь-якого
  мережевого виклику.
- **Плагіни**: позаду allow-list `F3D_ALLOW_HOSTS` (telemetry); секрети лише з env (`F3D_OPCUA_PASSWORD`,
  `F3D_WOODSTORE_KEY`, `F3D_CUTOPT_KEY`, сертифікати за шляхами з env); OPC UA на проді — `SignAndEncrypt`
  `Basic256Sha256` з сертифікатом клієнта (Q-12); `nodeid` — лише формат CT-03, без `eval`; методи
  `JobOrderControl` викликаються лише з команди (запис).
- **Заборонено**: Odoo сам не ходить у мережу цеху; модуль не змінює `qty_production`, не розбиває МО, не
  закриває МО, не пише в стандартні поля `mrp.workcenter`; плагін не викликає інших методів OPC UA, крім
  `JobOrderControl.*` з білого списку.

### 2.7 Продуктивність і обсяги

| Потік | Обсяг | Оцінка |
|---|---|---|
| Показання верстатів у telemetry | P-01: зміни станів ≈ 60/верстат/зміну, лічильник ≈ 220/верстат/зміну (кожна деталь); P-02: опитування 1 с → 40 показань/с на вході (зберігаються лише зміни) | ≈ 50 показань/с у пікові секунди на вході API-02 (35 × 1 с, D-11), ≈ 12 000 збережених/добу |
| Диспетчер (`_f3d_dispatch`) | один `search_read` верстатів за кодами (кеш `ormcache` мапи код → верстат, скидається при зміні сигналів верстата), порівняння з сирими значеннями в пам'яті, запис лише при переході | ≤ 150 мс додатково на пакет 1 000 показань; ≤ 60 мс на перехід стану (з автостартом ≤ 400 мс) |
| `f3d.machine.state.log` | ≈ 40 інтервалів/верстат/зміну → 1 400/добу → 350 тис/рік | ротація `keep_log_days=400`; індекси `(machine_id, date_start)`, частковий унікальний `WHERE date_end IS NULL` |
| `f3d.downtime` | ≈ 10/верстат/зміну → 350/добу | без ротації (бізнес-дані) |
| `mrp.workcenter.productivity` | +≈ 15 записів/верстат/зміну | стандарт |
| `f3d.machine.event` | ≈ 5/верстат/зміну | ротація 90 днів |
| `f3d.oee.shift` | 35/добу → 8 750/рік | без ротації |
| `f3d.gantry.stack` / `job` | 27 / ≈ 60 завдань на добу | — |
| Провайдер переглядача | 35 верстатів, 27 стосів, ≤ 32 МО — читання збережених полів, 4 запити | ≤ 80 мс |

Сирі ряди 1 с — не в Odoo (D-11, telemetry Q-01).

### 2.8 Міграція з демо-бази і деінсталяція

`post_init_hook` (SPEC §5.3), ідемпотентно, у транзакції установки; звіт — `factory3d.machine_connect.migration_report`:

1. Причини втрат: переклади uk стандартних `mrp.block_reason0…7` (лише якщо uk-значення = en); категорія
   «Доступність» демо-причинам `factory3d.loss_tool`, `factory3d.loss_break`, якщо порожня (**2**);
   `f3d_planned=True` для «Перерва»; причина «Не вказано» з data. Очікувано: `loss_translated: 7`,
   `loss_category_fixed: 2`.
2. Розміри листа 7 товарів категорії «Плитні матеріали» з назви (`2800×2070`, «16 мм»): `sheets_sized: 7`.
3. 35 `f3d.machine` за `data/mc_machines.csv` (код → протокол, джерело, позиція в модулі I/O, оператор).
4. Джерела (22) і сигнали (207) — з data/CSV (Додаток C SPEC); наявні сигнали з тими самими кодами (рівень 0
   `equipment/GANTRY-1/cycles_today`, `vacuum_kpa`, перенесені telemetry) отримують джерело й адресу, `last_*` і
   пороги не змінюються. Очікувано: `signals_created: 205`, `signals_bound: 2`.
5. 27 `f3d.gantry.stack` (локації `f3d_loc_kind='stack'` з кодом `PLT-*`), прив'язка 23 правил поповнення.
6. Журнал демо (**без нових записів журналу часу**): 184 записи `mrp.workcenter.productivity` → `f3d_source='demo'`;
   73 закриті простої і 1 відкритий → **74** `f3d.downtime` (`reason_source='demo'`, `reason_state='confirmed'`,
   CNC-2 — `state_kind='fault'`, відкритий, `maintenance_request_id` = MR/00031); верстат CNC-2 —
   `state='fault'`, `current_downtime_id`. Історія станів і OEE за 12.10 не будується (журнал демо
   синтетичний — A-24).
7. Технічний користувач, параметри, крони — з data.

Чиста база: кроки 1–2 частково (без демо-причин), 3–5 — 0 верстатів/стосів (немає кодів), 6 `skipped`.
`uninstall_hook`: крони вимикаються, параметри `factory3d.machine_connect.*` видаляються, сигнали й джерела
модуля **не** видаляються (технічна історія телеметрії, telemetry CT-01), стандартні записи журналу часу
лишаються, поля `f3d_*` зникають разом із модулем.

## 3. Налаштування системи

| Об'єкт | Параметр | Значення для тестового сервера | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `factory3d.machine_connect.read_enabled` | `True` (тест) / `False` (прод одразу після встановлення) | стоп-кран журналу станів і простоїв; умовчання — `factory3d.base.environment == 'test'` (CB-10) |
| `ir.config_parameter` | `factory3d.machine_connect.auto_start_enabled` | `False` перший тиждень, далі `True` по одному верстату (§4.6) | старт/пауза/завершення завдань |
| `ir.config_parameter` | `factory3d.machine_connect.write_enabled` | `False` | команди на верстати, портал, оптимізатор (разом із `factory3d.telemetry.write_enabled`) |
| `ir.config_parameter` | `factory3d.machine_connect.micro_stop_s` | `120` | умовчання порогу мікрозупинки нового верстата |
| `ir.config_parameter` | `factory3d.machine_connect.pause_after_min` | `10` | умовчання автопаузи на очікуванні |
| `ir.config_parameter` | `factory3d.machine_connect.finish_idle_s` | `60` | умовчання автозавершення для I/O |
| `ir.config_parameter` | `factory3d.machine_connect.qty_sync_mode` | `finish` | `finish` — `qty_produced` лише при завершенні; `live` — з тротлінгом (A-10, Q-08) |
| `ir.config_parameter` | `factory3d.machine_connect.qty_sync_s` | `300` | тротлінг режиму `live` |
| `ir.config_parameter` | `factory3d.machine_connect.coverage_min` | `0.95` | нижче — зміна OEE позначається «неповні дані» |
| `ir.config_parameter` | `factory3d.machine_connect.oee_good` / `oee_warn` | `0.75` / `0.5` | пороги кольорів (як `viewer/index.html:802–806`) |
| `ir.config_parameter` | `factory3d.machine_connect.no_job_activity_min` | `15` | «працює без завдання» довше → діяльність майстру |
| `ir.config_parameter` | `factory3d.machine_connect.stack_diff_tolerance` | `0` | допустима розбіжність стосу, арк. |
| `ir.config_parameter` | `factory3d.machine_connect.stack_diff_confirm_min` | `10` | розбіжність має триматися стільки хвилин |
| `ir.config_parameter` | `factory3d.machine_connect.gantry_auto_replenish` | `False` | `True` — крон сам запускає поповнення стосу нижче мінімуму |
| `ir.config_parameter` | `factory3d.machine_connect.gantry_auto_feed` | `False` | `True` — завдання порталу створюється саме, коли завдання розкрою на SAW-x/NEST-1 стало першим у черзі |
| `ir.config_parameter` | `factory3d.machine_connect.cutting_mode` | `collector` (тест) / `manual` (прод до Q-03) | режим оптимізації карт розкрою |
| `ir.config_parameter` | `factory3d.machine_connect.export_token_ttl_s` | `600` | TTL одноразового токена API-01 |
| `ir.config_parameter` | `factory3d.machine_connect.keep_log_days` / `keep_event_days` | `400` / `90` | ротація журналу станів і подій |
| `ir.config_parameter` | `factory3d.machine_connect.migration_report` | `{}` → звіт хука | стан міграції |
| `ir.config_parameter` | `factory3d.telemetry.write_enabled` | `False` (telemetry) | другий запобіжник команд |
| `f3d.machine` ×35 | `auto_start_mode`, `auto_finish`, `auto_pause`, `micro_stop_s`, `pause_after_min`, `finish_idle_s`, `employee_id` | з `data/mc_machines.csv`: P-01 — `job_or_single`, P-02 — `job_or_single` (діє правило «одне в черзі»); пороги — з параметрів | Додаток A SPEC |
| `f3d.source` | `UA-SAW-1` … `UA-ASMLINE-1` (15), `MB-U80-IO1` … `MB-U83-IO4` (4), `REST-WOODSTORE`, `REST-CUTOPT`, `MC-DERIVED` | з data (Додаток C SPEC), `collector_id=COL-MAIN` (крім `MC-DERIVED`), `read_enabled=True`, `write_enabled=False` | адреси контейнера `iot-sim` |
| `f3d.machine.message` | 10 рядків каталогу iot_sim §8.3.3 | з data | Додаток B SPEC |
| `mrp.workcenter.productivity.loss` | «Не вказано» (новий), переклади uk стандартних, «Перерва» `f3d_planned` | з data/хука | CM-09 |
| `res.users` | «Верстати (автоматично)» `user_f3d_machine` | з data, `active=False` | технічний |
| `ir.cron` | `cron_f3d_mc_tick` (1 хв), `cron_f3d_mc_oee` (5 хв), `cron_f3d_mc_gantry` (1 хв), `cron_f3d_mc_cutmap` (1 хв), `cron_f3d_mc_rotate` (щодня 03:10 Київ) | активні | §6 SPEC |
| collector env | `F3D_OPCUA_PASSWORD`, `F3D_WOODSTORE_KEY` (= `SIM_WOODSTORE_APIKEY`), `F3D_CUTOPT_KEY` (= `SIM_JOBS_APIKEY`), `F3D_OPCUA_CERT`, `F3D_OPCUA_KEY` (лише прод), `F3D_ALLOW_HOSTS=iot-sim,mosquitto` | секрети — у `.env` колектора | пакет `f3d_collector_mc` — у `requirements-extra.txt` образу колектора |
| емулятор | `SIM_MODE=scenario` для ТК автостарту; `follow_odoo` — лише для ТК читання (A-26) | — | iot_sim §8.15 |

## 4. Інструкція

**4.1 Підключити верстат (інженер АСУ).** 1) Завод 3D → Верстати → Налаштування → Верстати → відкрити `SAW-1`:
протокол «OPC UA», джерело `UA-SAW-1`, сигнали стану/режиму/тривоги/лічильника/завдання/подій заповнені з даних;
2) «Перевірити підключення» → показує останні значення сигналів і стан джерела; 3) режим автостарту
«За завданням або єдиним у черзі», мікрозупинка 120 с, автопауза 10 хв; 4) «Читати» увімкнено. Через ≤ 1 хв у
«Огляді верстатів» картка SAW-1 зелена/жовта зі станом і часом «з 09:55». 5) Майстер може поставити завдання в
чергу верстата з форми завдання — «Надіслати на верстат» (лише OPC UA з `JobManagement` і дозволеному записі); пуск —
оператор на пульті, Odoo підхопить таймер автостартом (A-29).

**4.2 Вказати причину простою (оператор).** Варіант 1 — «Цех» → робочий центр → «Заблокувати» → обрати причину
(стандарт Odoo); модуль сам прив'яже її до простою верстата. Варіант 2 — Завод 3D → Верстати → Простої → «Без
причини» (kanban для планшета) → картка простою SAW-1 → кнопка причини («Очікування матеріалу», «Налагодження»,
«Заміна інструменту», «Поломка», «Перерва»…) → «Зберегти». Майстер бачить простій у стані «Потребує
підтвердження».

**4.3 Підтвердити простої зміни (майстер).** Простої → фільтр «Сьогодні», «Не підтверджено» → перевірити
причину (підказку верстата видно в колонці «Підказка») → виділити → дія «Підтвердити». Неповні партії: Огляд →
фільтр «Неповна партія» → у завданні «Завершити як є» (стандартно, з залишком) або «Зняти позначку» (дозапуск).

**4.4 Карта розкрою (технолог).** 1) Деталі виробів: для специфікації «лінія A: Шафа нижня 600» внести деталі
(вручну або «Імпорт CSV»); 2) МО WH/MO/00233 → «Створити карту розкрою» → перевірити рядки й лист (2800 × 2070 × 16);
3) «На оптимізацію» (режим «через колектор») — за ≤ 1 хв стан «Оптимізується», потім «Сплановано»: аркушів, відхід %,
довжина різу; або (режим «вручну») «Завантажити CSV» → імпортувати в intelliDivide → «Імпорт плану»;
4) якщо аркушів більше, ніж у МО, — «Оновити потребу МО»; 5) «Випустити на верстат» → завдання з'являється на SAW-1,
портал отримує завдання на `total_sheets` листів.

**4.5 Стос не збігається з порталом (начальник складу).** Портал: стоси → фільтр «Розбіжність» → стос `PLT-01B`:
Odoo 45, «подано не списано» 7, портал 36 → розбіжність −2. Перерахувати стос фізично: якщо правий портал —
«Прийняти з порталу» (інвентаризація Odoo на 43 = 36 у порталі + 7 поданих, R-15 SPEC); якщо правий Odoo — «Виправити портал»
(команда woodStore, потрібен дозвіл запису), інакше виправити у woodStore вручну.

**4.6 Перший тиждень на проді (адміністратор).** День 0: установка, `read_enabled=False`, `auto_start_enabled=False`,
`write_enabled=False`; підключити колектор, перевірити джерела. День 1: `read_enabled=True` — лише журнал станів і
простоїв, вмикати по верстату (`f3d.machine.read_enabled`: SAW-1, далі групами — SPEC §13.5 п. 6), порівнювати з
планшетом. День 7: увімкнути `auto_start_enabled` і на одному верстаті (SAW-1)
`auto_start_mode="job_or_single"`, на решті — «Вимкнено»; далі по одному верстату на день за чек-листом DEPLOY_TEST.
Запис (`write_enabled`) — лише після письмового погодження HOMAG (Q-01, Q-02).

## 5. Ризики й відкриті питання

### 5.1 Відкриті питання (ті самі номери — у SPEC §15)

| ID | Питання | Кому | Рекомендована відповідь | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | Чи мають верстати HOMAG заводу OPC UA за OPC 40550-1 (umati, опція «OPC UA interface»/tapio-ready) і `JobManagement` (OPC 40001-3); які серійні номери/версії ПЗ | замовник / HOMAG | запросити підтвердження й nodeset кожного верстата; якщо `JobManagement` немає — автостарт лише за правилом «одне в черзі» | стани/лічильники — за OPC 40550-1 (нормативний nodeset 1.02.0); `JobManagement` — за iot_sim §8.3.2 (ПРИПУЩЕННЯ); запис методів вимкнено |
| Q-02 | woodStore API (закритий) — чи надасть HOMAG REST/OPC UA для стосів і завдань порталу | замовник / HOMAG | отримати опис інтерфейсу; адаптер `woodstore` ізольований у пакеті плагінів | контракт P-03 iot_sim (ПРИПУЩЕННЯ); команди вимкнено |
| Q-03 | Формат імпорту intelliDivide і передача MPR (iot_sim Q-02: CSV) | технолог / HOMAG | CSV P-04 + звірка на реальному intelliDivide; MPR — з woodWOP | на проді `cutting_mode=manual` (CSV вручну, план JSON вручну); на тесті — `collector` |
| Q-04 | Звідки деталі виробів (розміри, крайки, програми): CAD/imos/BAZIS чи ручне введення | технолог | імпорт CSV з CAD у `f3d.cut.part` (формат Додатка E SPEC) | ручне введення/CSV; у макеті деталей немає — для ТК використовуються тестові дані `tests/stand/data/parts_*.csv`, у модуль не потрапляють |
| Q-05 | Перелік причин простоїв і хто підтверджує; пороги мікрозупинки (120 с) і автопаузи (10 хв) | начальник виробництва | причини макета + «Не вказано»; підтверджує майстер зміни; пороги — як запропоновано | дані Додатка B SPEC, параметри §3 |
| Q-06 | Як оператор входить на планшет (бейдж/PIN) — від чийого імені автостарт, якщо на РЦ кілька людей | начальник виробництва | порядок R-09 (поточний на РЦ сьогодні → `OP-<код>`) | так і зроблено; у 7 РЦ без оператора — без працівника |
| Q-07 | Неповна партія: завершувати з backorder автоматично чи вирішує майстер | начальник виробництва | вирішує майстер (A-10) | прапор «неповна партія» + діяльність; МО не розбивається |
| Q-08 | `qty_produced` наживо чи при завершенні | начальник виробництва | при завершенні (`finish`): наживо Odoo 19 робить наступне завдання частково готовим, макет так не працює | `qty_sync_mode=finish`; лічильник видно наживо в `f3d_qty_counted` |
| Q-09 | **Закрито 14.10 (X-03):** CR-01 прийнято — telemetry 19.0.1.1.0 має `f3d.command.payload`/`result_data`, API-06 `payload`, API-07 `data`, метод плагіна `call(signal, payload) -> dict`; команди модуля — `payload` (CM-08, SPEC R-21), текстова граматика CMD-01…03 лишається запасною, GET API-01 лишається (CSV карти до 1 МБ більший за 64 КБ `payload`). Було: Запит на зміну telemetry (CR-01): поле `payload` (Json) у `f3d.command` і в API-06/07 (`payload` / `data`), метод плагіна `call(signal, payload) -> dict` | менеджер, автор telemetry | прийняти в telemetry 19.0.1.1.0 | команди — `payload` + `call()`; запасна граматика CMD-01…03 (≤ 64 символи) — `write()` плагінів і Odoo без поля `payload`; експорт CSV через API-01 (A-14) |
| Q-10 | Джерело якості для OEE: брак `stock.scrap` по завданню чи лічильники верстата (`RunsGood`/`RunsAborted`) | начальник виробництва | `stock.scrap` з `workorder_id` + втрати категорії «Якість» | так і зроблено (R-13); без браку `Q=1` |
| Q-11 | Що саме заведено на DI «в роботі» ADAM (сигнал циклу чи подачі), чи дає він імпульс на деталь | електрик / наладчик | реле «цикл» + лічильник = деталі | мікрозупинки 120 с поглинають паузи між циклами; лічильник — деталі (iot_sim R-16) |
| Q-12 | Безпека OPC UA на проді: `SignAndEncrypt`, сертифікати клієнта, облікові записи на верстатах | ІТ замовника / HOMAG | `Basic256Sha256` + сертифікат колектора, користувач лише на читання й окремий — для методів | на стенді `None` (iot_sim дозволяє), параметри безпеки вже в даних джерела |
| Q-13 | Плановий час зміни: лише календар (обід 11:30–12:00) чи ще регламентні перерви/прибирання | начальник виробництва | календар РЦ + причини з `f3d_planned` («Перерва») | так і зроблено |
| Q-14 | Коли списувати плиту: при подачі порталом (R-17) чи при закритті МО | головний бухгалтер / склад | при подачі (рядки руху МО з фактичного стосу, `picked`), проведення — при закритті МО (стандарт) | так і зроблено; параметр не потрібен |
| Q-15 | **Закрито частково 14.10:** ADAM — молодше слово першим, `little` (X-43, D-20); заявки ТО — лише з `alarm` (X-38); коди модуля (`workcenters/<код>/event`, `job_cmd`, `machine_state`, `equipment/GANTRY-1/cmd`, `equipment/CUTOPT/cmd`) каталог iot_sim доповнює з SPEC Додатка C.2 (X-34, X-76). Відкрите лише (а) — у реєстрі рядка немає. Було: Розбіжності з SPEC інших модулів: (а) viewer M-01b/R-06 читає `mrp.workcenter.default_capacity` (у Odoo 19 немає) і рахує `oee` як доступність; (б) iot_sim §8.4.1 vs §8.4.2 (порядок слів лічильника ADAM); (в) iot_sim каталог: на P-01 заявку дають і `state`, і `alarm`; (г) у каталозі немає сигналів подій OPC UA | менеджер, автори viewer/iot_sim | viewer — `capacity_ids`/1 і перекриття `oee` провайдером цього модуля | так і зроблено (§7 A-19, A-28); (а) — перекриття `oee` провайдером (CM-05) |
| Q-16 | **Закрито 14.10 (X-52):** ключі-розширення `opcua`/`rest_vendor` (CM-06) внесено в telemetry Додаток A як довідкові, власник — цей модуль. Було: Схема `opcua` telemetry (Додаток A): `mode` лише `subscribe\|poll`, без подій і без URI простору імен | автор telemetry | додати `mode: "events"` і `ns_uri` у схему | ключі-розширення `events: true`, `ns_uri` тощо (CT-03 дозволяє; перелік — CM-06) |
| Q-17 | **Закрито 14.10 (X-38):** емулятор формує `JobOrderID = "WO%05d"` у сценаріях і `follow_odoo`, завершені JobOrder лишаються в `JobOrderList` зі станом `Ended/Completed`. Було: Емулятор у `scenario` (планувальник `shift`) не визначає формат `JobOrderID` (iot_sim R-17) — автостарт OPC UA-верстатів у `shift` не знаходить завдань Odoo | автор iot_sim | `WO%05d` з id завдань Odoo | код без змін (R-09 п. 1 зіставляє `WO%05d`); ТК автостарту лишаються детермінованими: `Store` з Odoo (кнопка «Надіслати на верстат») + `Start` з пульта стенда (SPEC ТК-04, ТК-10) |

### 5.2 Ризики

| Ризик | Вплив | Пом'якшення |
|---|---|---|
| Реальні верстати не мають OPC 40550-1/`JobManagement` (Q-01) | немає автостарту за завданням | правило «одне в черзі»; ретрофіт I/O як P-02; адреси лише в даних |
| Автостарт «бореться» з оператором (оператор зупинив, верстат працює) | неправильні таймери | верстат — джерело істини про роботу (A-03); `auto_start_mode="off"` на РЦ із ручними операціями; стоп-кран |
| Мікрозупинки (контакт «цикл» на I/O) дають тисячі простоїв | шум у журналі | поріг `micro_stop_s`, лише зміни в журналі, налаштування на верстаті |
| Емулятор у `follow_odoo` + автостарт = ехо | зациклення станів | у ТК автостарту — `scenario`; документовано A-26 |
| Текстова граматика команд (64 символи) — тісно | довгі назви МО не влізуть | CR-01 прийнято (X-03): команди — `payload` без обмеження 64 символи; обмеження діє лише в запасній граматиці (перевірка довжини до створення, `UserError`) |
| Демо-журнал синтетичний (перекриття, до початку зміни) | OEE за 12.10 неправдивий | історію OEE не будуємо (A-24); OEE з дня установки |
| Розбіжність стосу через подані, але не списані листи | хибні тривоги | «подано не списано» з завдань порталу (R-15), підтвердження 10 хв |
| asyncua 1.x/2.x несумісність API | збірка ламається | закріплено 1.1.6 (= емулятор), адаптер сесії в одному класі (A-20) |
| Odoo 19 `button_start` кидає помилку на заблокованому РЦ | автостарт падає | аварія — єдиний блокуючий запис; перед стартом закриваємо простій верстата (R-09 п. 6) |
| Гонка двох воркерів Odoo на одному верстаті | подвійний старт | `SELECT … FOR UPDATE` рядка верстата, ідемпотентний ключ (R-09) |

## 6. План сборки агентами

Спільні файли належать W0 і далі змінюються лише через нього: `__manifest__.py`, `__init__.py`, `models/__init__.py`,
`security/*`, `views/menus.xml` (меню й дії V-30), `data/*.xml` (крім `mc_machine_messages.xml`), `data/mc_signals.csv`,
`data/neutralize.sql`, `tools/commands.py`, `models/f3d_command.py`, `models/push_handler.py`, `tests/common.py`,
`pyproject.toml` і `requirements.txt` пакета плагінів. W0 створює **усі файли моделей §2 SPEC з полями, SQL-обмеженнями
й порожніми гачками**; воркер-власник файлу далі дописує в нього методи (злиття послідовне — конфліктів немає).
Межі між W1 і W2/W3 — гачки M-01 SPEC (`_f3d_after_commit`, `_f3d_tick_extra`, `_f3d_on_count`, `_f3d_on_job`,
`_f3d_apply_event`): W1 викликає, W2 і W3 перевизначають у власних файлах через `super()`.

| Воркер | Файли | Здає | Залежить від |
|---|---|---|---|
| W0 каркас | Odoo: `__manifest__.py`, `__init__.py`, `models/__init__.py`, усі `models/*.py` (поля §2, обмеження, гачки M-01 порожні), `security/*`, `views/menus.xml`, `data/ir_config_parameter.xml`, `ir_sequence.xml`, `res_users.xml`, `mrp_loss_data.xml`, `mc_sources.xml`, `ir_cron.xml`, `f3d_actions.xml`, `mc_signals.csv`, `neutralize.sql`, `hooks.py` (`_csv_rows`, `_signal_rows`, порожні хуки), `tools/commands.py` (R-21, `create_command`), `models/f3d_command.py` (M-20: поля, `_f3d_mc_on_result` викликає `_f3d_on_command` власника), `models/push_handler.py` (M-21: маршрутизація на методи власників), `tests/__init__.py`, `tests/common.py` (SPEC §13.0.1), `tests/test_commands.py`, `static/description/icon.png`, `README.md`, `CHANGELOG.md`; пакет: `pyproject.toml`, `requirements.txt`, `README.md`, `f3d_collector_mc/__init__.py` | модуль встановлюється на чисту базу й копію демо (хук — звіт `skipped`), меню й дії відкриваються, `setUpClass` фікстур проходить; AC-57, AC-58 | SPEC §0, §1, §2 (поля), §3 (V-30), §4, §5.1, §5.2, §13.0.1, Додатки C |
| W1 верстати й стани | `models/f3d_machine.py` (методи M-01: R-01…R-04, диспетчер, `_f3d_count`, `_f3d_tech_env`, виклики гачків), `models/f3d_machine_state_log.py`, `models/f3d_signal.py` (M-18), `models/f3d_source.py` (M-19), `tools/states.py`, `tools/ppt.py`, `views/f3d_machine_views.xml` (V-01…V-04, огляд-kanban), `views/f3d_machine_state_log_views.xml`, `tests/test_normalize.py`, `tests/test_state_log.py`, `tests/test_ppt.py` | M-01 (база), M-02, M-18, M-19; R-01…R-04, R-26; AC-01…AC-10 | W0 |
| W2 простої | `models/f3d_machine_downtime.py` (R-05…R-08 через гачки), `models/f3d_downtime.py`, `models/f3d_machine_event.py`, `models/f3d_machine_message.py`, `models/mrp_workcenter_productivity.py` (M-15, M-16), `models/maintenance_request.py`, `wizard/downtime_reason_wizard.py`, `wizard/downtime_reason_wizard_views.xml`, `data/mc_machine_messages.xml`, `views/f3d_downtime_views.xml`, `views/f3d_machine_event_views.xml` (V-10, V-11, V-24), `views/mrp_workcenter_views.xml` (V-29: РЦ, журнал часу, причини), `tests/test_downtime.py`, `tests/test_merge_operator.py`, `tests/test_hints.py` | M-03…M-05, M-15, M-16, M-24, M-28; R-05…R-08; AC-11…AC-24 | W1 |
| W3 автостарт | `models/f3d_machine_wo.py` (R-09…R-12 через гачки), `models/mrp_workorder.py` (M-13, у т. ч. «Надіслати на верстат»), `models/mrp_workcenter.py` (M-12), `views/mrp_workorder_views.xml` (V-26), `tests/test_autostart.py`, `tests/test_counter_finish.py` | M-12, M-13; R-09…R-12; AC-25…AC-38, AC-101 | W2 |
| W4 OEE | `models/f3d_oee_shift.py`, `tools/oee.py`, `views/f3d_oee_views.xml`, `tests/test_oee.py`, `tests/test_energy_contract.py` | M-06; R-13, R-14, R-28; AC-39…AC-46 | W1 (паралельно з W2/W3) |
| W5 портал | `models/f3d_gantry_stack.py`, `models/f3d_gantry_job.py` (у т. ч. `_f3d_on_command`), `models/stock_picking.py`, `views/f3d_gantry_views.xml`, `tests/test_gantry_stack.py`, `tests/test_gantry_job.py` | M-07, M-08, M-27; R-15…R-18, R-23 (сторона Odoo); AC-47…AC-56 | W1 |
| W6 карти розкрою | `models/f3d_cut_part.py`, `models/f3d_cut_map.py` (M-10, M-11, `_f3d_on_command`), `models/mrp_production.py`, `models/product_template.py`, `controllers/cutmap.py` (API-01), `tools/cutcsv.py`, `wizard/cut_plan_import_wizard.py`, `wizard/cut_part_import_wizard.py`, `wizard/cut_wizard_views.xml`, `views/f3d_cut_views.xml`, `views/mrp_production_views.xml` (V-25), `views/product_views.xml` (V-29 товар), `tests/test_cutmap.py`, `tests/test_api_export.py` | M-09…M-11, M-14, M-17, M-25, M-26; API-01; R-19, R-20; AC-59…AC-68 | W1, W5 (дзеркало завдань порталу) |
| W7 плагіни колектора | `f3d_collector_mc/{opcua,ua_session,nodeids,ua_values,rest_vendor,generic,woodstore,cutopt,cmdtext,events}.py`, `schemas/*.ext.json`, `tests/conftest.py`, `tests/fakes/{opcua_server,woodstore_app,cutopt_app}.py`, `tests/unit/test_{nodeids,opcua_subscribe,opcua_events,opcua_reconnect,opcua_call,woodstore,cutopt,cmdtext}.py` | CM-06…CM-08; R-21…R-24 (сторона колектора); AC-69…AC-80 | W0 (`tools/commands.py` для `cmdtext.py`); паралельно з W1–W6 |
| W8 дані, міграція, провайдер | `data/mc_machines.csv`, `tools/gen_mc_data.py`, `hooks.py` (кроки 0–7, `uninstall_hook`), `models/viewer_provider.py` (M-22), `tools/payload.py`, `models/res_config_settings.py`, `views/res_config_settings_views.xml`, `tests/test_migration.py`, `tests/test_viewer_provider.py`, `tests/test_security.py`, `tests/test_hooks.py` | M-22, M-23; §5 SPEC; R-25, R-27; AC-81…AC-92 | W2…W6 |
| W9 стенд | `tests/stand/*` (pytest `-m stand`: iot_sim + колектор з пакетом + Odoo; `load_machines.py`, `data/parts_BR-K4.csv`), `docs/modules/factory3d_machine_connect/DEPLOY_TEST.md`, `TEST_REPORT.md` | ТК-01…ТК-16, ТБ-01…ТБ-10, ТП-01…ТП-04; AC-93…AC-100 | W7, W8 |

Порядок злиття: W0 → (W1 ‖ W7) → (W2 ‖ W4 ‖ W5) → (W3 ‖ W6) → W8 → W9. Кожен воркер здає зелені тести своїх файлів
(`odoo-bin -d test --test-tags /factory3d_machine_connect:<Class> --stop-after-init`; `pytest
services/collector_plugins/machine_connect -m "not stand"`) і не чіпає чужих тестів; після W8 — повний прогін
`--test-tags f3d` на чистій базі й на копії демо.

## 7. Рішення автора (A-xx)

| ID | Рішення | Обґрунтування | Що змінює відносно каркаса/інших SPEC |
|---|---|---|---|
| A-01 | Окрема модель `f3d.machine` (1:1 з РЦ) для підключення і живого стану; на `mrp.workcenter` — лише `f3d_machine_id` і related | живий стан пишеться часто; `mrp.workcenter` — важка модель із збереженими обчисленнями й чатером | — |
| A-02 | Шість нормалізованих станів, у т. ч. `nodata` (таблиця R-01); `off`/`setup` для I/O не визначаються | у ТЗ п'ять станів; зв'язок може зникнути — це не стан верстата, але має бути видно й виключено з OEE | CM-02 |
| A-03 | Верстат — джерело істини про те, **чи** він працює (час), оператор/майстер — **чому** стоїть (причина) | правило злиття без конфліктів; машина не бреше про рух, людина знає причину | — |
| A-04 | Відкритий (блокуючий) запис втрати — лише при аварії; простої очікування/налагодження/вимкнення пишуться закритими записами після закінчення, поки триває — `f3d.downtime` | стандартний `button_start` кидає помилку на заблокованому РЦ — оператор не зміг би стартувати при «очікуванні» | — |
| A-05 | Мікрозупинки < `micro_stop_s` (120 с) поглинаються часом роботи (втрата продуктивності, не доступності) | паузи між циклами пили/преса; класика OEE (мікрозупинки — Performance) | — |
| A-06 | Модель простою `f3d.downtime` групує записи журналу часу одного простою і веде класифікацію причини | один простій може дати 2 записи (до й після вибору причини оператором); майстру потрібен робочий список | — |
| A-07 | OEE: A = робота / плановий час (без «немає даних»), P = Σ(ідеальний цикл × к-сть) / робота із завданням (обмеження 1,0, сире значення зберігається), Q = (усі − брак) / усі; ідеальний цикл — `time_cycle_manual` операції з `time_efficiency` і місткістю; без журналу станів (РЦ без підключення) — робота з продуктивних записів журналу часу | збігається з визначенням макета (`productive_minutes / 210` = A) і з категоріями втрат Odoo; на емуляторі P = Q = 1 → OEE = A = 0,84 для SAW-1 | viewer R-06 рахує `oee` як A — перекривається провайдером (CM-05) |
| A-08 | OEE зберігається на верстат × зміну (`f3d.oee.shift`), поточна зміна оновлюється кроном 5 хв; провайдер перекриває `oee` лише за наявності запису поточної зміни | провайдер не рахує OEE на кожен запит; без підключення лишається значення вбудованого провайдера | — |
| A-09 | Автостарт: завдання верстата (`JobOrderID` → `mrp.workorder`) або «рівно одне `ready` і жодного `progress`»; працівник за R-09; технічний користувач | без однозначного завдання автостарт шкодить; оператор макета `OP-<код>` = Додаток B base | — |
| A-10 | `qty_produced` — при завершенні (`qty_sync_mode=finish`); неповна партія не завершується автоматично й не розбиває МО | у Odoo 19 запис `qty_produced` під час роботи робить наступне завдання частково готовим і змінює `qty_producing` МО; макет веде партію цілком | — |
| A-11 | Odoo — головний за залишками плит; портал звіряється з урахуванням «подано не списано»; виправлення — лише явними діями (інвентаризація або команда) | залишок порталу змінюється при кожному листі, Odoo — при закритті МО | — |
| A-12 | Списання плити — рядками руху МО з фактичного стосу/партії (`picked=True`) при виконанні завдання порталу | портал знає, звідки взяв лист; резерв МО міг бути з іншого стосу | — |
| A-13 | Деталі для розкрою — модель `f3d.cut.part` на специфікацію з роллю матеріалу (`main` / `back` / `product`), бо `bom_line_id` у демо-рухах порожній і декор змінюється від МО до МО | у макеті деталей немає; роль дозволяє одну специфікацію на всі декори | — |
| A-14 | Канал команд — telemetry `f3d.command.payload` (CR-01, telemetry 19.0.1.1.0, X-03): об'єкти CMD-01…03 (SPEC R-21, ≤ 64 КБ), плагін виконує `call()`, результат — `result_data`; текстова граматика CMD-01…03 (≤ 64 символи) — запасна (`write()` плагінів; Odoo — лише без поля `payload`); великі дані назад — подіями `mc_*` (≤ 256 КБ); CSV карти колектор забирає GET API-01 цього модуля з одноразовим токеном | рішення реєстру X-03 (Q-09 закрито); CSV карти (до 1 МБ) більший за ліміт `payload` 64 КБ; GET — читання, як API-01 telemetry | доповнює telemetry §2.6 «колектор пише лише push/status/event/result»: тут колектор лише **читає** |
| A-15 | Плагіни — окремий pip-пакет `f3d_collector_mc` (telemetry §8.3.2); тип `rest_vendor` належить цьому пакету з адаптерами за `params.vendor` (`woodstore`, `cutopt`, `generic`) | тип джерела — Selection telemetry, нового типу `woodstore` не потрібно; access опитує BioStar з Odoo й плагіна не потребує | каркас §6.5 «плагін `woodstore`» = адаптер `woodstore` плагіна `rest_vendor` |
| A-16 | OPC UA: `nodeid` у формі `ns=2;s=…` (CT-03) + ключ `ns_uri` (адресі або параметрам джерела) — плагін підміняє індекс за `NamespaceArray`; події — ключ `events: true` при `mode="subscribe"`; команди — `io: "write"` (не читається), `call` | емулятор вимагає резолв за URI (iot_sim §8.3.1); схема telemetry не має подій (Q-16) | CT-03 розширено ключами; довідково — у telemetry Додатку A (X-52) |
| A-17 | Обчислений стан — сигнал на локальному джерелі `MC-DERIVED` типу `f3d_machine` (CT-12) | колектор не може писати в нього (`foreign_signal`), `stale` не ставиться кроном telemetry | — |
| A-18 | Провайдер переглядача — `AbstractModel` з іменем `f3d.viewer.provider.machines` у самому модулі, без `_inherit` viewer і без міст-модуля | viewer M-01 збирає провайдери за префіксом імені й атрибутами; вказівка координатора | на відміну від telemetry A-20 / fire_safety A-35 міст не потрібен |
| A-19 | Заявку ТО дає лише сигнал `workcenters/<код>/alarm` (`alarm_states=["on"]`, `create_request=True`); сигнал `state` — `create_request=False` | каталог iot_sim позначає «ERROR → заявка» і «True → заявка» — дві заявки на одну аварію | узгоджено з iot_sim: заявки ТО лише з `alarm` (X-38) |
| A-20 | Клієнт OPC UA — `asyncua==1.1.6` (та сама версія, що в емуляторі), Python 3.12 | версія 2.x змінює API; однакова версія клієнта й сервера на стенді | — |
| A-21 | Технічний користувач «Верстати (автоматично)» (`active=False`) для автодій | видно в журналі часу й чатері, хто стартував; не займає ліцензію | — |
| A-22 | Вхід показань — перевизначення `f3d.signal._f3d_ingest` (після `super()`), стани `nodata` — перевизначення `_mark_stale` | telemetry R-17 пише `last_*` сирим SQL — `write()` не викликається (вказівка координатора) | — |
| A-23 | Плановий час = календар РЦ мінус відпустки ресурсу (`time_type='leave'`) мінус простої з причиною `f3d_planned` | слоти завдань (`time_type='other'`) не є плановим простоєм | — |
| A-24 | Міграція не будує історії станів і OEE з демо-журналу; демо-простої стають `f3d.downtime` без нових записів журналу часу | журнал демо синтетичний (перекриття, записи до зміни) — OEE вийшов би > 1 | — |
| A-25 | Розміри листа — поля `f3d_sheet_*` на `product.template` (власник — цей модуль); заповнюються з назви товару | у демо розмір лише в назві («2800×2070», «16 мм») | — |
| A-26 | Для ТК автостарту емулятор — режим `scenario`; `follow_odoo` — лише читання | у `follow_odoo` емулятор віддзеркалює стан Odoo — автостарт дав би ехо | — |
| A-27 | Подія OPC UA приходить подією `mc_opcua` (повний зміст) і показанням `workcenters/<код>/event` (`kind='event'`, текст ≤ 64), яке пише обробник через CT-10 | для журналу телеметрії вистачає 64 символів; повний текст і категорія — для підказки й заявки | — |
| A-28 | Лічильник ADAM — `u32`, `wordorder=little` (низьке слово першим, ADAM-6000 Manual B.2) | iot_sim §8.4.1 і §8.4.2 суперечать; telemetry R-20 обрала `little` | узгоджено: ADAM — молодше слово першим (X-43, D-20) |
| A-29 | Odoo ставить завдання в чергу верстата лише методом `Store` (кнопка «Надіслати на верстат», AC-101); запуск — тільки оператор на пульті верстата; `StoreAndStart`/`Start` з Odoo не викликаються | віддалений пуск руху верстата без людини біля нього небезпечний; плагін підтримує всі методи (CMD-01) для налагодження й майбутніх рішень | — |
| A-30 | Сирий стан поза `states` сигналу (telemetry повертає `unknown_state`, але приймає показання) модуль обробляє сам — R-01 → `nodata` + WARNING; відкидаються лише справжні відмови telemetry | інакше невідомий `JobOrderID` чи `bad` не дійшли б до диспетчера; модуль бачить, що зв'язок погіршився | M-18 SPEC |
