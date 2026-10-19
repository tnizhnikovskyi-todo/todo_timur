# Блок «Енергетика» — gap-аналіз макета АРМ енергетика проти factory3d

Дата: 2026-10-18. База: `origin/claude/factory3d-build` (d5df3dd). Тільки аналіз: код модулів не змінювався.
Макет (затверджений замовником): 6 артбордів — Пульт (`Main`), Вузол мережі (`Feeder`), Керування (`Control`),
Енергоресурси (`Resources`), Аналітика (`Analytics`), Мобільний (`Mobile`).

## 0. Рішення замовника і угоди документа

| ID | Рішення | Наслідок для плану |
|---|---|---|
| E-01 | Генератор: `td_genset` лишається окремим інсталюваним продуктом. В застосунку «Енергетика» він з'являється розділом «Генерація й резерв» разом із СЕС, КГУ, BESS, АВР. Верхнє меню «Генератор» зникає, коли встановлено енергетику. Інтеграція — через міст-модуль. | Розд. 3. **Уточнено менеджером:** обрано саме цей зміст (окремий продукт OPL-1 + нові меню моста в «Генерація й резерв»); розбіжність літер («варіант A» у формулюванні) — лише позначення, за змістом це **варіант B** розд. 3 цього документа; фізичне злиття відхилено. |
| E-02 | Хвилі затверджено: W1 Пульт + картка вузла + генератор всередині + події; W2 Керування; W3 Енергоресурси; W4 Аналітика + мобільний. Кожна хвиля: SPEC/ARCH → код → тести → сервер. | Розд. 7. |
| E-03 | Шлях керування: автоматика виконується в збирачі/контролері. Odoo лише задає режими, уставки, розклад. Ручні команди — з блокуваннями, підтвердженням і журналом. На демо-стенді виконуються через емулятор `iot_sim`. | Розд. 2. |
| E-04 | Перейменування (гілка `claude/td-rename`, ще не злита й не опублікована на remote): `factory3d_energy`→`td_energy`, `factory3d_genset`→`td_genset_factory3d`, `factory3d_bms`→`td_bms`, `factory3d_telemetry`→`td_telemetry`, `factory3d_viewer`→`td_viewer3d`, `factory3d_base`→`td_factory3d`; моделі `f3d.*`→`td.*`, поля `f3d_*`→`td_*`. | Цитати нижче — за **поточними** файлами (`file:line`); **нові** сутності названо по-новому (`td.energy.scenario`, `td_energy_control`). Повної таблиці перейменування (xml-id, групи, ключі `ir.config_parameter`, URL `/f3d/telemetry/*`) я не бачив — нові ключі в цьому документі подано як `td.energy.<param>` (припущення, див. E-09 і `W1_SPEC.md` A-23). |
| E-05 | v1-автоматика виконується в плагіні збирача `td_collector_energy`; PLC може перейняти пізніше через той самий контракт уставок/розкладу. | Закриває Q-02; розд. 2.3–2.4. |
| E-06 | Класи команд. **A** (роль «Енергетик»): заряд/стоп BESS, сцени освітлення, вентиляція «Економ», підтвердження тривог. **B** («Головний енергетик» або друге підтвердження іншим «Енергетиком»): перемикання QS, пуск КГУ, розряд BESS, тест ДГУ, уставка тиску, зміна пріоритетів скидання, вмикання/вимикання сценарію. | Закриває Q-03 (склад класів уточнено: тест ДГУ й уставка тиску — клас B, а не A); групи — з W1, команди — з W2. |
| E-07 | Драйвер «м² плити» — з MRP: вироблена кількість × поле площі продукту, якість `estimated`. Газ, повітря, тепло на демо — сигнали емулятора; реальні лічильники налаштовуються на об'єкті. | Закриває Q-05, Q-06. |
| E-08 | Кореневу плитку td_genset ховати, коли встановлено міст. | Закриває Q-01; розд. 3.3. |
| E-09 | SPEC пишемо в td-іменах зараз; код стартує після злиття `claude/td-rename`. Маршрути `/f3d/*` і коди сигналів **не змінюються**. | Закриває Q-13. Гілка `claude/td-rename` (локально, коміт 95bf195) поки містить лише `git mv` файлів. |
| E-10 | cos φ: ціль 0,95 (PFC); попередження нижче 0,92; тривога нижче 0,90; одна група налаштувань. | Закриває Q-09. |
| E-11 | Демо-стенд — постійні сервіси на тестовому сервері (емулятор + збирач) + генератор історії 90 діб інтервалів; серверну частину робить менеджер, інструмент визначає SPEC W1. | `W1_SPEC.md` R-36. |

**Скорочення шляхів** (каталог `factory3d/odoo_addons/`, якщо не вказано інакше):
`EN`=`factory3d_energy`, `TL`=`factory3d_telemetry`, `BM`=`factory3d_bms`, `GS`=`td_genset`, `GB`=`factory3d_genset`,
`SIM`=`factory3d/services/iot_sim/iot_sim`, `COL`=`factory3d/services/collector/collector`,
`SPEC`=`docs/modules/factory3d_energy/SPEC.md` (читався лише розділами R-06, R-14…R-16, §3, §7).

**Статуси матриці** (оцінюється серверна готовність; UI-оболонка Пульту/Керування/Ресурсів/Аналітики/Мобільного нова скрізь,
бо у `EN` лише kanban «Огляд», hierarchy «Схема мережі», pivot/graph/list — `SPEC:710-729`):
**E** — дані й розрахунок є, потрібна лише віддача в UI; **P** — є частково (сирі дані/модель без поля чи розрахунку);
**M** — немає.

**Стан демо-БД** (`f3d_full2`, Postgres на цьому хості; `f3d_full` ідентична за складом): установлено 16 модулів
`factory3d_*` + `td_genset`; вузлів енергетики 123, лічильників 67, сигналів 1 162 (з них `energy` 297, `bms` 549),
пулів 5, тариф 1 з однією зоною; **інтервалів, подій, відключень, розподілів, показань (`f3d_reading`) — 0**;
`factory3d.energy.install_report`: `state=partial`, `equipment_linked=0`, `unmatched_equipment=80`, `workcenter_linked=0`.
Висновок: без запущеного емулятора+збирача (або сіда історії) екрани порожні; для W4 потрібен генератор історії (розд. 5.5).

## 1. Матриця «екран → елемент макета»

### 1.1 Пульт енергетика (`Main.dc.html`)

| ID | Елемент макета | С | Що є (файл:рядок) | Чого бракує / джерело і розрахунок |
|---|---|---|---|---|
| PU-01 | Перемикач періоду Зараз / Зміна / Доба / Місяць | E | `EN/models/f3d_energy_interval.py:271` (`_td_shift_kwh`), `:372` (`_td_day_profile`), поля `day`,`hour_local` (`:42-43`) | Один серверний метод `td.energy.dashboard.get_data(period)`. «Місяць: пік 742 кВт» = max Σ слотів вводів за місяць (≤ 2 880 рядків `_read_group`). |
| PU-02 | Індикатор «Живі дані · 14:20» | E | `TL/models/f3d_collector.py:34-37` (`last_seen`,`state`), `TL/controllers/telemetry.py:206` (health) | Вік останнього пакета колектора; поріг stale — з колектора. |
| PU-03 | «Відкрити в 3D» / «Показати в 3D» (шар «Енергетика») | E | `EN/models/f3d_energy_node.py:254` (`action_f3d_show`), провайдер `EN/models/viewer_provider.py:10-31`, `EN/tools/payload.py:162` | Перевірити контракт viewer (передача шару/коду вузла). |
| PU-04 | «Звіт за зміну» | M | — | qweb-звіт: енергія за зміну (`_td_shift_kwh`), пік, події, МО (`f3d.energy.alloc`). W4 разом зі звітом керівництву. |
| PU-05 | KPI «З мережі зараз», % договірної, запас | E | сигнал `infra/totals/grid_kw` (R-06 п.6, `SPEC:1125`), `contract_kw` `EN/models/f3d_energy_tariff.py:32` | % = grid/contract; запас = contract − grid. |
| PU-06 | KPI «Споживання заводу», частка СЕС | E | `energy/totals/p_now`, `infra/totals/pv_now` (R-06 п.3,5, `SPEC:1119,1123`) | pv_share = pv_now / p_now. |
| PU-07 | KPI енергія за період, ₴, тариф | E | R-15 п.2 (`SPEC:1332`), `EN/models/f3d_energy_tariff.py:107` (`_td_price_at`) | Гроші лише для `group_f3d_energy_cost` (`EN/models/f3d_energy_interval.py:50-51`). |
| PU-08 | KPI «Пік 15 хв», час, % договірної | E | `EN/models/f3d_energy_interval.py:329` (`_td_peak_event`), R-15 п.3 (`SPEC:1334`) | — |
| PU-09 | KPI «Власна генерація» (СЕС, BESS %, ДГУ резерв) | P | R-06 п.5 (`pv_now`, `bess_soc`, `bess_mode`), ДГУ: `GB/models/genset_link.py:129` (`_compute_live`: `online`,`state_label`) | Паливо/тест ДГУ — з моста через адаптер `GB/adapters/td_genset.py`; експортувати в dashboard. |
| PU-10 | KPI cos φ заводу + «Секція 2: 0,88 нижче 0,92» | P | `energy/totals/cos_phi` (R-06 п.3); пороги 0,95/0,90 у `EN/data/energy_signals.csv` | cos φ по секціях лише в пам'яті (`cos_after_s`, `SPEC:1118`) — не пишеться. Додати сигнали `energy/sections/S{1,2}/cos_phi`. Норма 0,92 (текст макета) ≠ 0,95 (уставка PFC) ≠ 0,95/0,90 (сигнал) — Q-09. |
| PU-11 | Банер-рекомендація (експорт СЕС 26 кВт через T2, QS вимкнено) | M | дані є: `p_kw` T2 < 0 (R-06 п.4), стан QS у `cells` (R-16 п.4, `SPEC:1355`) | Rule-based `td.energy.advice` (правило «експорт > N кВт й QS=off»), стани open/snoozed/done. |
| PU-12 | Дії рекомендації: «Зарядити BESS 50 кВт», «Увімкнути QS…», «Пізніше», «Скасувати» | M | «Пізніше» — клієнтське | Решта — шлях керування (розд. 2). У W1 банер без кнопок керування, кнопки вмикає `td_energy_control` (W2). |
| PU-13 | Однолінійна схема: вузли, лінії, 5 кольорів стану | P | Дерево 123 вузлів (`EN/data/energy_nodes.csv`), V-01 hierarchy (`SPEC:710`); `live_status` (`EN/models/f3d_energy_node.py:117-129`) — це свіжість даних, **не** електричний стан | Поля геометрії `sld_x,sld_y,sld_w,sld_h,sld_show` на `td.energy.node` (≈19 блоків макета) + обчислюваний `sld_state` (ok/warn/alarm/off/gen) з відкритих тривог, `state` автоматів, `bess_mode`, генерації. |
| PU-14 | Вибір вузла: панель фактів, «Відкрити картку вузла», «Показати в 3D» | P | факти з сигналів вузла (R-06), `action_view_meters/intervals` (`EN/models/f3d_energy_node.py:224-244`) | Шаблони «фактів» за видом вузла; перехід у картку (ND); кнопки QS/BESS — W2. |
| PU-15 | «Профіль доби · 15 хв»: споживання, з мережі, СЕС, договірна, прогноз | P | `load15_kw`,`grid15_kw` (R-15 п.3-4, `SPEC:1334-1336`), СЕС — інтервали ролі `generation`, `typical[h]` (`EN/models/f3d_energy_interval.py:405`, R-15 п.5) | Прогноз = типовий день за днем тижня (годинний→15 хв); СЕС — крива за кліматичною моделлю; поле `profile15` у dashboard API. |
| PU-16 | Прогноз до кінця доби, експорт сьогодні, небаланс за годину | P | `kwh_export` (`EN/models/f3d_energy_interval.py:47`), `EN/models/f3d_energy_balance.py:20` (`diff_pct`, R-07) | Прогноз = факт + Σ typical по залишку доби. |
| PU-17 | «Тривоги й події» (рівень, час, заголовок, деталі) | P | `EN/models/f3d_energy_event.py:21-47` (level info/warn/bad, kind, `text`), `_td_log` `:51` | Немає розбиття `title`/`detail` і життєвого циклу активна→підтверджена→вирішена. |
| PU-18 | «Підтвердити» / «Підтверджено вами о…» | M | — | Поля `state`, `acked_by`, `acked_at`, `resolved_at` + `action_ack` на `td.energy.event`. |
| PU-19 | Діагностика лічильника (шлюз, адреса, останній пакет, RS-485) | P | `EN/models/f3d_energy_meter.py:73-88` (`data_state`,`data_state_since`), `TL/models/f3d_source.py:86-88` (`last_ok`,`last_error`), `source.params` | Скласти текст із source+meter; «оцінка за балансом секції» — `quality='interpolated'`/R-07. |
| PU-20 | Дії по тривозі («Відкрити заявку ТО», «Зарядити BESS») | P | заявка з порога: `EN/models/maintenance_request.py:5-20`, `f3d_signal_id` | Кнопка → заявка; BESS — W2. |
| PU-21 | «Найбільші споживачі зараз» | E | `energy/consumers/*/p_now`, `node.p_now` (`EN/models/f3d_energy_node.py:114`), payload п.6 (`SPEC:1363`) | top-N за `p_now` споживачів; RV-ALL/DUST-1 — групи/пули. |
| PU-22 | «Енергія на виробництво · сьогодні» (МО, кВт·год, ₴, частка) | P | `EN/models/mrp_production.py:17-43`, `f3d.energy.alloc` (`EN/models/f3d_energy_alloc.py:22`, kind direct/shared/idle/overhead), пули `EN/models/f3d_energy_pool.py:10` | «Частка 3,4 %» = енергія / собівартість МО — нове обчислюване поле (`mrp_account`). |
| PU-23 | «ТО й відключення» (заявки, планові ТО, відключення, повірка) | P | `maintenance.request`, `f3d.energy.outage` (`EN/models/f3d_energy_outage.py:25`, лише аварійні) | Планові відключення — `td.energy.outage.plan` (ND-16); повірка — `next_verification` на лічильнику. |
| PU-24 | Діалог «Увімкнути QS?» з переліком блокувань | M | — | Розд. 2 (interlock + підтвердження). |
| PU-25 | Підменю Енергетики: Пульт, Керування, Енергоресурси, Аналітика, Вузли мережі, Події, Налаштування | P | `EN/views/menus.xml:9-35` (Огляд, Схема, Лічильники, Профіль, Енергія на виробництво, Баланс, Відключення, Події, Налаштування) | Реструктуризація меню; пункт «Генерація й резерв» (E-01) у макеті відсутній — Q-08. |
| PU-26 | Тости й «Скасувати» (undo) виконаної дії | M | `TL/models/f3d_command.py:107` скасовує лише `queued` | Undo = зворотна команда (`reverts_action_id`), розд. 2. |

### 1.2 Картка вузла мережі (`Feeder.dc.html`, ШР-2)

Відповідність даним: ШР-2 = лінія `BW-2` (живиться від шафи `QF-2`, `EN/data/energy_nodes.csv`), лічильник `PM-QF-2`,
10 відгалужень `TAP-*` (збігається з макетом). Розбіжності демо-чисел макета з даними (ШР-3: 6 vs 8, ШР-4: 14 vs 11) — не блокери.

| ID | Елемент макета | С | Що є (файл:рядок) | Чого бракує / джерело і розрахунок |
|---|---|---|---|---|
| ND-01 | Заголовок: шлях ГРЩ/Секція/QF-2/ШР-2, чипи (під напругою, 630 А, лічильник на зв'язку) | E | `parent_id/parent_path` (`EN/models/f3d_energy_node.py:68-69`), `rating_a` (`:80`), `meter.data_state` (`EN/models/f3d_energy_meter.py:73`), V-02 (`SPEC:711`) | — |
| ND-02 | «Показати в 3D» | E | `EN/models/f3d_energy_node.py:254` | — |
| ND-03 | «Запланувати відключення» | M | див. ND-16 | — |
| ND-04 | «Створити заявку ТО» + діалог (обладнання, тип, опис, команда, пріоритет) | E | `maintenance.request` (`maintenance_type`, `maintenance_team_id`, `priority`), `node.equipment_id` (`EN/models/f3d_energy_node.py:76`) | Обгортка-wizard з префілом. На демо-БД `equipment_linked=0` — спершу прив'язка даних (`action_f3d_energy_rebind`, `:261`). |
| ND-05 | KPI «Струм зараз» (А, % від 630, по фазах) | E | `energy/lines/L/i_now`, `load` (R-06 п.1, `SPEC:1113`), `i_a/i_b/i_c` шафи (`EN/data/energy_signals.csv`) | — |
| ND-06 | KPI «Потужність» (кВт, встановлена, cos φ) | E | `p_inst_kw` (`EN/models/f3d_energy_node.py:84`), `energy/lines/L/p_now`,`cos_phi` | — |
| ND-07 | KPI «Енергія сьогодні», ₴, к-сть замовлень | E | `_td_kwh_by_code` (`EN/models/f3d_energy_node.py:212`, API-02 `SPEC:991`), alloc за РЦ підвузлів | К-сть МО — distinct `production_id` за добу. |
| ND-08 | KPI «Максимум доби» (А, час, поріг 80 %) | P | `kw_avg` (`EN/models/f3d_energy_interval.py:48`), `f3d.reading.hour` (TL), `warn_high` сигналу | Пік струму = max за добу з `reading.hour` або kW/(√3·U·cos φ) з 15-хв; новий метод. |
| ND-09 | KPI «Простій під напругою» (2,4 кВт) | P | `idle_factor` (`EN/models/f3d_energy_node.py:90`), `alloc.kind='idle'`, статус споживача `EN/tools/payload.py:148` | Live-сума `p_now` споживачів у статусі idle. |
| ND-10 | Графік «Струм за добу · 15 хв» з порогами | P | інтервали (`kw_avg`) або `f3d.reading` | Перерахунок кВт→А; пороги з сигналу. |
| ND-11 | Таблиця відгалужень: код, обладнання, встан., зараз, стан, завдання; фільтр | P | вузли `tapoff` 36 + `consumer` 49, `p_inst_kw`,`p_now`, статус `payload._consumer_status` (`EN/tools/payload.py:148`), `workcenter_id` (`:78`) | Стан «На ТО» — відкрита `maintenance.request` на `equipment_id`; «Завдання» — `mrp.workorder` у `progress` за РЦ. |
| ND-12 | «Сума відгалужень, втрати й допоміжні» | E | `node.p_now` − Σ дітей; баланс `EN/models/f3d_energy_balance.py:65` | — |
| ND-13 | Блок «Облік»: лічильник, ТС, останнє показання, повірка, баланс | P | `ct_ratio` (`EN/models/f3d_energy_meter.py:99`), `last_value/last_ts` (`:89-90`), balance | `next_verification` + період повірки (нові поля); нагадування. |
| ND-14 | Блок «Захист QF-2»: автомат, Ir, спрацювання за рік, тепловізор | M | лише `rating_a` | Поля `protection_trip_unit`, `protection_ir_ratio`; `trip_count_year` з подій нового виду `trip` (сигнал `state='tripped'` вводів); тепловізор — план ТО. |
| ND-15 | «Події фідера» (пік, перекіс фаз, пуск, ТО) | P | `f3d.energy.event.node_id` (`EN/models/f3d_energy_event.py:45`), асиметрія R-12 п.3 | Події верстатів (ТО, пуск GANTRY) — з `maintenance`/`machine_connect`; об'єднана стрічка. |
| ND-16 | Планове відключення: діалог, перелік зачеплених відгалужень, МО у вікні, узгодження виробництвом, сповіщення | M | аварійні `f3d.energy.outage` (`EN/models/f3d_energy_outage.py:25-54`) — інша семантика | `td.energy.outage.plan` (draft→pending→approved/rejected→done), `affected_node_ids` (піддерево), `production_ids` (`mrp.workorder` у вікні за РЦ підвузлів), `mail.activity` планувальнику/складу. |
| ND-17 | «Обслуговування» (заявки + план) | E | `maintenance.request/equipment`, статкнопка `f3d_energy_node_count` (`SPEC:726`) | — |
| ND-18 | Блок «Планове відключення» у боковій колонці | M | див. ND-16 | — |

### 1.3 Керування (`Control.dc.html`)

| ID | Елемент макета | С | Що є (файл:рядок) | Чого бракує / джерело і розрахунок |
|---|---|---|---|---|
| CT-01 | Індикатор «Контролер ГРЩ і збирач на зв'язку»; напис «автоматику виконує контролер, не Odoo» | P | збирач: `TL/models/f3d_collector.py:34-49` (`last_seen`,`buffer_rows`), health `TL/controllers/telemetry.py:206` | «Контролер ГРЩ» як об'єкт відсутній: сигнал-heartbeat `energy/auto/heartbeat` від рушія (розд. 2.4). |
| CT-02 | Картки сценаріїв (6): назва, опис, чип статусу, перемикач | M | жодної моделі; найближче `peak_shave_kw` (`EN/models/res_config_settings.py:40`, використано лише в тексті `EN/tools/payload.py:604`) | `td.energy.scenario` (code, enabled, `params` Json + схема, `state_signal_id`); статус — від збирача. |
| CT-03 | Параметри сценаріїв (уставка 760 кВт/95 %, експорт ≤ 20 кВт, cos φ 0,95, 23:00–06:30…) | M | — | У `params` сценарію, валідація схемою; публікація збирачу. |
| CT-04 | «Зрізання піку» (BESS → КГУ → відключення за пріоритетами) | M | дані: `grid15_kw`, `bess_soc`, `infra/chp/state` | Рушій у збирачі (розд. 2.4). |
| CT-05 | «Самоспоживання СЕС» | M | дані: `export_kw`, `bess_soc` | Те саме. |
| CT-06 | «Компенсація реактивної (PFC)» | M | стан: `pfc_q_now` (`EN/models/f3d_energy_node.py:116`), події `EN/models/f3d_energy_event.py:163` | Регулює сам PFC-контролер; Odoo — цільовий cos φ (уставка) + моніторинг відмови ступеня. |
| CT-07 | «Нічний режим (BMS)» (вентиляція 30 %, сцена освітлення, 16 °C) | P | `BM/models/f3d_bms_hvac_unit.py:151-154` (`mode_signal_id`,`sp_day/night_signal_id`), сцени `BM/models/f3d_bms_light_scene.py:5` | Виконання за розкладом у збирачі; зараз лише разові команди майстрами (`BM/wizard/command_common.py`). |
| CT-08 | «Резервне живлення» (АВР→ДГУ, критичні 180 кВт) | P | `is_critical` (`EN/models/f3d_energy_node.py:92`), `critical_kw` (R-06 п.7), АВР R-14 (`SPEC:1290`) | АВР апаратний; Odoo задає критичність і пріоритети скидання. |
| CT-09 | «КГУ за графіком і ціною» (газ 19,80 ₴/м³) | M | сигнали `infra/chp/state|gas_m3h|hours` | Ціна газу — W3 (`td.energy.price`); порівняння з ціною мережі. |
| CT-10 | Пріоритети відключення навантажень (порядок, «як», кВт, сума, «ніколи не відключаються») | M | `is_critical` для «ніколи» | `td.energy.shed.item` (sequence, вузол/обладнання, дія off/reduce/pause, `kw_reducible`, умова); порядок публікується контролеру. |
| CT-11 | 8 плиток ручних команд; права «енергетик / головний енергетик» | M | `f3d.command` (`TL/models/f3d_command.py:14`), BMS-майстри світла/вентиляції (`BM/wizard/command_common.py:1-67`), ДГУ — `GS/models/genset_command.py:135` | QS, BESS, КГУ, компресор — немає записуваних сигналів: заборона для `module='energy'` (`EN/models/f3d_signal.py:15-20`). |
| CT-12 | Діалог підтвердження з «Перевіркою блокувань» | M | BMS R-25 перевіряє лише прапорці (`BM/wizard/command_common.py:20-37`) | `td.energy.interlock` + обчислення в діалозі й повторно в збирачі. |
| CT-13 | «Розклад на сьогодні» (BESS, КГУ, вентиляція, освітлення, зарядна, ДГУ) | P | ДГУ: `td.genset.schedule` (`GS/models/genset_schedule.py:69,112`); BMS: `calendar_id` (`BM/models/f3d_bms_hvac_unit.py:140`) | `td.energy.schedule.slot`; рядок ДГУ — з td_genset через адаптер. |
| CT-14 | «Журнал команд і перемикань» | P | `f3d.command` (`TL/models/f3d_command.py:38-59`), `TL/views/f3d_command_views.xml`; `td.genset.command` (`GS/models/genset_command.py:135`) | Єдиний журнал `td.energy.action` (дія оператора → N команд). |
| CT-15 | Автоматика поза Odoo | M | колектор виконує лише поодинокі команди (`COL/core/commands.py:76`) | Плагін-рушій сценаріїв у збирачі (W2). |

### 1.4 Енергоресурси (`Resources.dc.html`)

Перевірка арифметики макета: 6 284 × 8,40 = 52 786 ₴; 612 м³ × 19,80 = 12 118 ₴; вода 252 ₴ / 4,2 м³ = 60 ₴/м³; разом 65 156 ₴.

| ID | Елемент макета | С | Що є (файл:рядок) | Чого бракує / джерело і розрахунок |
|---|---|---|---|---|
| RS-01 | 5 вкладок ресурсів з підписом «зараз · ₴» | P | електрика — є; решта нижче | `td.energy.resource` (5 записів) + агрегат «зараз/сьогодні». |
| RS-02 | «Сьогодні разом» (електрика+газ+вода; тепло й повітря враховані) | M | вартість електрики — R-15 | Ціни (`td.energy.price`), прапор `is_derived` для тепла/повітря (не сумуються). |
| RS-03 | Електрика: KPI (з мережі, сьогодні+₴, генерація+частка, реактивна енергія/tg φ) | P | перші три — E (R-06, R-15); сигнали `q_kvar` — лише потужність (`EN/data/energy_signals.csv`, `energy/cells/Q1/q_kvar`) | Лічильники квар·год (регістри PM5560) — нові сигнали та інтервали; tg φ = Q/P за період; ризик доплати — компонент тарифу (Q-10). |
| RS-04 | Електрика: графік імпорту з лінією договірної | E | `grid15_kw`, `contract_kw` | — |
| RS-05 | Електрика: «Найбільші споживачі» | E | див. PU-21 | — |
| RS-06 | Газ: KPI (витрата, сьогодні м³+₴, ліміт доби, ККД котельні) | M | лише `infra/chp/gas_m3h` (`EN/data/energy_signals.csv`); котельня — `equipment/BOILER/heat_kw` (BMS, у БД) | Сигнали `infra/gas/m3_total|flow_m3h`, `equipment/BOILER/gas_m3h`; ККД = тепло котлів / (газ × теплотворність); ціна й ліміт — ресурс/ціна. |
| RS-07 | Газ: графік; споживачі (BOILER, DRY-1, CHP, CANTEEN) | M | CHP є; решта нема | `td.energy.point` + лічильники/оцінки. |
| RS-08 | Тепло: KPI (потужність, подача/зворот, сьогодні кВт·год, T цеху/уставка/зовні, рекуперація AHU-1) | P | `BM/models/f3d_bms_heat_balance.py:128-133` (сигнали подачі, зворота, тепла котлів/КГУ, зовнішня), `hvac.unit.heat_signal_id` (`BM/models/f3d_bms_hvac_unit.py:149`), `indoor_c`,`filter_dp_pa` (`:160-165`) | Інтеграція кВт→кВт·год (`tools/integrate.py`); рекуперація % — розрахунок із T припливу/витяжки/зовнішньої (сигналу витяжки немає). |
| RS-09 | Тепло: графік; «Куди йде тепло» (RV-ALL, AHU-1, ворота, офіс) | P | RV/AHU `heat_kw` (сигнали BMS у БД) | «Втрати через ворота» — журнал воріт `factory3d_yard` × модель втрат; «офіс» — залишок. |
| RS-10 | Повітря: KPI (витрата м³/хв, тиск/уставка, питома потужність, ел. за добу, нічні витоки) | M | компресорна: лише `equipment/COMPRESSOR/state|temp_c` (БД), `energy/consumers/COMPRESSOR/p_now` | Сигнали `air/flow_m3min`, `air/pressure_bar`, `air/setpoint_bar`; питома = P/витрата; витоки = нічний min. |
| RS-11 | Повітря: графік; споживачі (EDGE-1, NEST-1, PRESS-1, SPRAY-1, CNC-1) | M | — | Оцінка: `machine_state` × паспортна витрата (`f3d_spec`). |
| RS-12 | Вода: KPI (витрата, сьогодні м³+₴, нічна, підживлення котельні) | P | `infra/water/flow_m3h`, `m3_total` (БД, модуль telemetry; `SIM/models/water.py`) | Ціна води; підживлення котельні — окремий лічильник (нема); нічна = min 23:00–06:30. |
| RS-13 | Вода: графік; споживачі (SOCIAL, CANTEEN, BOILER, SPRAY-1) | P | головний ввід є | Підлічильників нема — оцінка. |
| RS-14 | «Що помітила система» (зауваження з ₴/міс і кнопкою дії) | M | — | `td.energy.opportunity` + правила (розд. 5.3); дії: сценарій / заявка / уставка / графік. |
| RS-15 | «Вивантажити в Excel» (15-хв інтервали ресурсів) | P | стандартний export інтервалів електрики; `GS/data/ir_exports.xml` — зразок | Ресурсні інтервали — після W3; сам експорт стандартний. |

### 1.5 Аналітика (`Analytics.dc.html`)

| ID | Елемент макета | С | Що є (файл:рядок) | Чого бракує / джерело і розрахунок |
|---|---|---|---|---|
| AN-01 | Періоди 7 днів / 30 днів / квартал / рік | E | `day` (`EN/models/f3d_energy_interval.py:42`), зберігання 400 діб (`keep_interval_days`) | — |
| AN-02 | «Звіт для керівництва» (PDF) | M | — | qweb-звіт (W4). |
| AN-03 | KPI електроенергія, Δ до бази | P | факт — інтервали | База — AN-13. |
| AN-04 | KPI газ, Δ до бази (з поправкою на похолодання) | M | газ — W3; температура `ventilation/totals/outdoor_c` (BMS) | Драйвер HDD. |
| AN-05 | KPI вартість енергії (електрика 81 % / газ 19 %) | P | електрика E; газ — W3 | — |
| AN-06 | KPI питома енергоємність кВт·год/м² плити | M | немає «м² плити» | Драйвер `plate_m2` (Q-05). |
| AN-07 | KPI частка енергії в собівартості | P | `f3d_energy_cost` МО (`EN/models/mrp_production.py:25`), собівартість — `mrp_account` | Σ energy_cost / Σ cost МО. |
| AN-08 | KPI власна генерація % | E | інтервали ролі `generation` | — |
| AN-09 | KPI викиди CO₂ | M | — | `co2_kg_per_unit` ресурсу × кількість. |
| AN-10 | Стовпці електрики за ділянками (8 категорій) | P | інтервали `node_id` (`EN/models/f3d_energy_interval.py:38`), `group` (`EN/models/f3d_energy_node.py:110`), пул, зона (`:79`) | `td.energy.area` (8 записів) + `area_id` на 49 споживачах і пулах. |
| AN-11 | Теплокарта година × день тижня | E | `day`,`hour_local` (`:42-43`); `_read_group('day:day_of_week')` — `odoo/orm/models.py:2209` | — |
| AN-12 | EnPI: факт vs очікувано (тижні), значення, економія | M | — | `td.energy.baseline` + `td.energy.enpi` (розд. 5.1). |
| AN-13 | Модель бази (1 820 кВт·год/добу + 4,1 кВт·год/м²) | M | — | OLS-регресія за драйверами (5.1). |
| AN-14 | Бюджет місяця (план, факт, %, прогноз) | M | — | `td.energy.budget` (5.2). |
| AN-15 | Розріз: ділянки | P | див. AN-10 | — |
| AN-16 | Розріз: обладнання (кВт·год, ₴, частка, кВт·год/мотогод) | E | інтервали споживачів, `alloc.minutes` (`EN/models/f3d_energy_alloc.py:41`) | — |
| AN-17 | Розріз: замовлення (кВт·год/шт) | E | `alloc.production_id` (`:34`), `f3d_energy_unit_cost` (`EN/models/mrp_production.py:28`) | кВт·год/шт = kwh / `qty_produced`. |
| AN-18 | Розріз: продукти | P | alloc → `production_id.product_id` | Stored related `product_id` на alloc. |
| AN-19 | Розріз: зміни (1, 2, ночі й вихідні) | P | `kwh_shift` R-11, `shift_calendar_id` (`EN/models/res_config_settings.py:35`), `_td_shift_hours` (`EN/models/f3d_energy_interval.py:256`) | Групування за `hour_local`/днем тижня за календарем змін. |
| AN-20 | Колонка «До бази» за зрізами | M | — | Коефіцієнт зрізу відносно бази (спрощено). |
| AN-21 | Деталізація зрізу (профіль, події, обладнання) | P | `action_view_intervals` (`EN/models/f3d_energy_node.py:234`) | Action з доменом зрізу. |
| AN-22 | «Резерви економії» (8): ₴/міс, «у плані», дія | M | — | `td.energy.opportunity` (5.3). |
| AN-23 | «У плані: X з Y ₴/міс» | M | — | Сума за `in_plan`. |

### 1.6 Черговий енергетик, телефон (`Mobile.dc.html`)

| ID | Елемент макета | С | Що є (файл:рядок) | Чого бракує / джерело і розрахунок |
|---|---|---|---|---|
| MB-01 | Вкладка «Стан»: з мережі, %, СЕС, BESS, ДГУ·АВР, cos φ | P | як PU-05/09/10 | Легкий метод `get_mobile_state`. |
| MB-02 | Вкладка «Тривоги»: активні, «Усі тривоги», інфо за сьогодні | P | як PU-17 | Життєвий цикл (PU-18). |
| MB-03 | «Беру в роботу» / «Закрити: зв'язок є», час, диспетчер бачить | M | — | `assigned_user_id`, `taken_at` на події; сповіщення диспетчеру (`bus`). |
| MB-04 | «Де це в 3D» | E | `EN/models/f3d_energy_node.py:254` | Deep-link з мобільного. |
| MB-05 | Картка рекомендації (Зарядити BESS / Відкласти 30 хв) | M | — | `td.energy.advice` + snooze. |
| MB-06 | «Призначити на себе» (заявка ТО PFC-2) | E | `maintenance.request.user_id` | — |
| MB-07 | Вкладка «Схема»: вузли зі станом | P | вузли + `sld_state` (PU-13) | — |
| MB-08 | Вкладка «Обхід»: чекліст зміни, прогрес, «Завершити» → журнал | M | — | `td.energy.round` + `td.energy.round.item` (пункти з нормою й поточним значенням із сигналів, напр. «T1 ≤ 85 °C, зараз 58 °C»). |
| MB-09 | Мобільний вхід, сповіщення | M | `/odoo` responsive, `bus` | Клієнтська дія `td_energy_mobile`; Web Push — окреме рішення (Q-14). |

### 1.7 Підсумок матриці

| Екран | Елементів | E | P | M |
|---|---|---|---|---|
| Пульт (PU) | 26 | 8 | 12 | 6 |
| Вузол мережі (ND) | 18 | 8 | 6 | 4 |
| Керування (CT) | 15 | 0 | 5 | 10 |
| Енергоресурси (RS) | 15 | 2 | 7 | 6 |
| Аналітика (AN) | 23 | 5 | 8 | 10 |
| Мобільний (MB) | 9 | 2 | 3 | 4 |
| **Разом** | **106** | **25** | **41** | **40** |

Читається так: «Пульт» і «Вузол» — переважно віддача наявних даних; «Керування» і «Аналітика» — основна нова розробка;
«Ресурси» впираються в **відсутні сигнали** газу/повітря/реактивної енергії (дані, не код).

## 2. Шлях керування

### 2.1 Як іде команда сьогодні

1. **UI → `f3d.command`.** Майстри BMS (`BM/wizard/hvac_command_wizard.py:44`, `light_command_wizard.py`) викликають
   `BM/wizard/command_common.py`: `check_operator` (група «Будівля: оператор»), `check_switches`
   (`factory3d.bms.write_enabled`, `factory3d.telemetry.write_enabled`), `check_signals` (`signal.write_enabled`,
   `source.write_enabled`), `send` створює `f3d.command` від суперкористувача з `origin='bms'` та `expires_at`.
2. **Охорона в моделі.** `TL/models/f3d_command.py:84` (create): група менеджера, прапор модуля, `source.write_enabled`,
   `signal.write_enabled`, `params.read_only`, заборона для локальних джерел. Пожежна безпека блокується окремо
   (`factory3d_fire_safety/models/f3d_command.py:7-14`, D-07). Для **енергетики** запис заборонено конструкцією:
   `EN/models/f3d_signal.py:15-20` (constraint на `module='energy'`) і AC-81 (`EN/tests/stand/test_tb.py:103`).
3. **Транспорт.** Колектор опитує `GET /f3d/telemetry/commands` (`TL/controllers/telemetry.py:289`): віддає `queued`,
   непрострочені, з увімкненими прапорцями, ставить `sent`. `COL/core/commands.py:76` (`_execute`) повторно перевіряє
   прапорці й `expires_at`, викликає `plugin.write()` (`COL/plugins/modbus_tcp.py:408` — fc5/6/16 і імпульс,
   `mqtt.py:266`, `bacnet_ip.py:703`) або `plugin.call()` для payload (OPC UA-метод). Результат —
   `POST /f3d/telemetry/commands/result` (`:332`) → `done/failed` + `result_data`; `_cron_expire`
   (`TL/models/f3d_command.py:115`) закриває непідібрані як `expired`. «Чотири запобіжники» — AC-88 (`docs/modules/factory3d_telemetry/SPEC.md:1801`).
4. **Емулятор.** `SIM/protocols/modbus_server.py:48-61` приймає запис FC5/6/16 у карту регістрів, BACnet має записувані
   точки (`SIM/protocols/bacnet_server.py:238` — уставки RV, `:337` — уставка подачі котельні). Але **моделі пристроїв
   енергетики не читають командних регістрів**: BESS автономний (`SIM/models/bess.py:37-56` — баланс за надлишком),
   КГУ — автомат станів (`SIM/models/chp.py:34-52`), АВР — власна логіка (`SIM/models/ats.py:93,115`).
5. **Окремий шлях `td_genset`.** Пульт → `td.genset.command` (`GS/models/genset_command.py:135`) → HTTP ретранслятор →
   HGM6120N; стан-машина `to_send→sent→awaiting→confirmed` з підтвердженням **лише за наступним знімком**
   (`:857-903`), розклад/таймер/тест (`GS/models/genset_schedule.py:69`, `genset_scheduler.py`).

### 2.2 Чого немає для макета

| Потреба макета | Є | Прогалина |
|---|---|---|
| Блокування (interlocks) і їх відображення в діалозі | BMS перевіряє лише прапорці (R-25) | Немає моделі правил, обчислення «гаразд/ні» зі свіжих сигналів, повторної перевірки в збирачі |
| Підтвердження («Виконати») | td_genset — підтвердження виконання знімком; `f3d.command` — без двокрокового UI | Двокроковий потік `prepared → confirmed` з токеном і TTL |
| Журнал (хто, що, результат, блокування) | `f3d.command` + chatter; окремий `td.genset.command` | Єдиний бізнес-журнал дій; зв'язок дія → команди → результат; undo |
| Розклад (смуги BESS/КГУ/вент./світло/зарядка/ДГУ) | розклад лише ДГУ (td_genset), календар BMS | Слоти розкладу, публікація збирачу, план з прогнозу |
| Пріоритети скидання навантажень | `is_critical` (булеве) | Впорядкований список дій зі зменшення, умови, «ніколи» |
| Сценарії з уставками | `peak_shave_kw` (лише текст) | Модель сценаріїв, параметри, публікація, стан від рушія |
| Записувані сигнали QS/BESS/КГУ/PFC/компресор | заборона для `module='energy'` | Окремий клас керуючих сигналів + відповідні регістри в емуляторі |

### 2.3 Цільова схема (E-03)

```
Оператор → Odoo: td.energy.action.prepare(kind, params)   → результат блокувань (soft), текст, токен (TTL 60 с)
        → Odoo: .confirm(token)  → повторна перевірка, створення td.command (origin='energy', expires_at)
        → збирач: GET commands → [інтерлоки-hard у плагіні] → plugin.write() → пристрій (iot_sim на стенді)
        → збирач: POST commands/result → td.energy.action.state=done/failed → журнал
Автоматика: Odoo зберігає сценарії/уставки/розклад/пріоритети
        → збирач: GET /td/energy/automation/config (ETag, токен колектора) → рушій (цикл 1–5 с, живі сигнали в пам'яті)
        → plugin.write() у пристрої; рушій → POST event + сигнали стану `energy/auto/<code>/state`
Odoo лише відображає стан і журнал; зупинка Odoo не зупиняє автоматику (конфіг кешується, `config_version`).
```

Принципи: (1) **hard-блокування — лише в збирачі/контролері**; Odoo-перевірка — підказка для діалогу.
(2) Інтерлоки — іменовані перевірки в Python-реєстрі (`tools/interlocks.py`) з параметрами, **без `safe_eval` коду з БД**.
(3) Керуючі сигнали — окремий клас `module='energy_control'` (додати значення до `f3d.source.MODULES`, `TL/models/f3d_source.py:43-52`);
`module='energy'` лишається read-only, AC-81 зберігається. (4) Нові прапорці `td.energy.control_enabled`
(на проді `False`) поверх «чотирьох запобіжників». (5) Пожежна й захисна автоматика не керується (макет цього вимагає; D-07).
(6) Класи команд: A (світло, вентиляція, компресор, заряд BESS, тест ДГУ) — оператор; B (QS, пуск КГУ, розряд BESS, зміна пріоритетів) —
головний енергетик або підтвердження другою особою (Q-03).

### 2.4 Що будувати (W2)

| Об'єкт | Де | Розмір |
|---|---|---|
| Рушій сценаріїв: peak shave, self-consumption, night (BMS), backup, CHP-за-ціною; PFC — лише моніторинг | `factory3d/services/collector_plugins/td_collector_energy/` (за зразком `f3d_collector_bms`) | L |
| Ендпоїнти `GET /td/energy/automation/config` (ETag), `POST …/state` | `td_energy_control/controllers/` | M |
| Моделі: scenario, shed.item, interlock, command.kind, action (журнал), schedule.slot | `td_energy_control/models/` | L |
| Керуючі сигнали й адреси (QS cmd, BESS mode/setpoint, CHP start/stop, PFC target cos, `air/setpoint_bar`, ДГУ-тест через td_genset) | `td_energy_control/data/*.csv` | M |
| Емулятор: регістри команд і реакція моделей (BESS режим/уставка; QS — поділ навантаження T1/T2; CHP start/stop; PFC; компресор) | `SIM/models/{bess,chp,ats,transformer,compressor}.py`, `services/iot_sim/catalog/signals.csv` | M |
| Дії рекомендацій пульту (BESS 50 кВт, QS) як зареєстровані види команд | `td_energy_control/data/` + хук у `td.energy.advice` | S |

## 3. Генератор усередині «Енергетики»

### 3.1 Що є зараз

| | `td_genset` (GS) | `factory3d_genset` (GB, міст) |
|---|---|---|
| Призначення | моніторинг/керування HGM6120N через ретранслятор | зв'язка td_genset ↔ модель заводу: телеметрія, ТО, 3D, баланс при блекауті |
| Розмір | 91 файл, 20 965 рядків Python, 22 файли/223 тести, OWL (`static/src/pult` 454+163+437 рядків) | 3 978 рядків, 14 файлів/101 тест |
| Моделі | 16: `td.genset`, `.command`, `.reading`, `.alarm`, `.event`, `.schedule`, `.schedule.exception`, `.storage.location`, `.canister`, `.fuel.move`, `.refuel`, `.fuel.calibration`, `.config`, `.notify.level`, `.controller.model`, `.relay.client` | `f3d.genset.link` (`GB/models/genset_link.py:57`), `.profile` (`genset_profile.py:80`), `.event.map` (`genset_event_map.py:34`), `f3d.viewer.provider.genset` (`viewer_provider.py:47`); `_inherit` source/equipment/request/settings |
| Меню | **кореневе** `td_genset.menu_root` «Генератори», seq 45, `web_icon` (`GS/views/menu.xml:16`); 23 меню: Генератор, Показання, Аналітика (6), Події, Заправка (3), Налаштування (6) | верхнє «Генератор» під «Завод 3D», seq 55 (`GB/views/menus.xml:4`) + 4 підпункти + налаштування |
| Залежності | `base, mail, bus, web, maintenance`; python `requests`, `pytz`; `application: True`; ліцензія **OPL-1** (`GS/__manifest__.py:17,55`) | `td_genset, factory3d_base, factory3d_telemetry, factory3d_energy` (`GB/__manifest__.py:8`); LGPL-3 |
| Групи | `group_user`, `group_admin`, `group_tech` + privilege/category | використовує `factory3d_base.group_f3d_*` |
| Поза Odoo | `relay/` + `relay_api.md` (ретранслятор) | — |
| Зв'язок з енергетикою | — | R-14 п.10: енергетика читає `factory3d.genset.amf_master` (`SPEC:1318`); міст потребує `factory3d_energy` для балансу в острові |

Демо-БД `f3d_full2`: `td_genset` — **0** генераторів, 0 показань/подій/тривог/команд/розкладів, `td_genset_config` 1;
`ir_model_data`: `td_genset` 1 082 (671 `ir.model.fields`, 193 selections, 67 views, 24 act_window, 23 menu, 34 access, 5 cron,
3 sequence, 3 groups, 1 mail.alias), `factory3d_genset` 245 (48 `event.map`, 1 profile, 6 menu, 14 config-params);
`f3d_genset_link` 0; у `res_groups_users_rel` для груп `td_genset` 2 призначення; параметри `factory3d.genset.*` — 14.
Міграція даних бізнесу не потрібна (порожньо); важливі лише xml-id/меню/групи.

### 3.2 Варіанти

| | A. Фізичне злиття коду в `td_energy` | B. `td_genset` лишається продуктом, меню й екрани хостяться в «Енергетиці» (через міст) |
|---|---|---|
| Суть | перенести 21 k рядків, 16 моделей, OWL, ретранслятор у `td_energy` | міст `td_genset_factory3d` додає розділ «Генерація й резерв», ховає свої/чужі кореневі меню |
| Інстальована БД | `UPDATE ir_model_data SET module='td_energy'` для 1 082 записів + видалення рядка `ir_module_module`; перепідпорядкування 23 меню; xml-id груп `td_genset.group_*` → нові (права користувачів збережуться через id); `mail.alias`, `ir.sequence`, `ir.cron` — ті самі записи; потрібен pre-migration-скрипт і ручна перевірка | міграція `td_genset` **не потрібна**; лише перейменування моста (E-04: 245 xml-id) і заміна його меню (`-u` видаляє застарілі меню, бо вони не `noupdate`) |
| Тести | 223 тести td_genset переїжджають у `td_energy` (теги `/td_genset`→`/td_energy`, `post_install`-порядок); тести моста частково зникають | td_genset 223 — без змін; міст 101 — оновити тести меню (`test_views`, `test_install`, `test_access`) + ≈15 нових |
| Продаж td_genset окремо | **неможливий**: `td_genset` — окремий продукт, перенесений з Odoo 18 (`GS/MIGRATION_19.md`; `smartgen/` згадано в `tools/odoo/ENV.md`, у цьому репозиторії його немає); злиття = відрив від upstream і подвійна підтримка; ліцензія **OPL-1** не сумісна з LGPL-3 модуля `td_energy` | **зберігається** без змін; Енергетика не залежить від td_genset (міст ставиться лише коли є обидва модулі; можливий `auto_install`) |
| Енергетика без генератора | тягне 21 k рядків, `requests/pytz`, ретранслятор | не тягне нічого |
| Ризики | необоротність, регресії 223 тестів, юридичний конфлікт ліцензій | дублювання пунктів меню між продуктом і мостом; групи td_genset окремі від групи енергетики |

**Рекомендація: B** (= зміст рішення E-01). Блокує A саме ліцензія й окремий продаж.

### 3.3 Реалізація E-01 (W1, задача C)

1. `td_energy` створює порожній розділ-контейнер `menu_td_energy_generation` «Генерація й резерв» + екран огляду
   (kanban вузлів `kind in (generator, storage, ats)`: СЕС `PV-INV*`, `CHP`, `BESS`, `ATS-1`, `GENSET`) — власний, без залежності від td_genset.
2. Міст `td_genset_factory3d` (залежить від `td_genset` і `td_energy`):
   - **видаляє** власне верхнє меню «Генератор» (`GB/views/menus.xml:4`) — його підпункти (Зв'язка, Профілі, Події→ТО, Заявки ТО) стають дітьми розділу або «Налаштувань»;
   - **створює нові** меню в розділі для екранів td_genset (Генератор, Показання, Події, Заправка, Аналітика ×6) з `action=` на дії td_genset (xml-id із `GS/views/menu.xml:19-60`) — **не перепідпорядковує** меню td_genset (при `-u td_genset` вони б повернулись);
   - ховає `td_genset.menu_root` (`active=False`) і відновлює в `uninstall_hook` (Q-01);
   - `implied_ids`: група «енергетик» → `td_genset.group_user` (так само, як енергетика вже підʼєднує `mrp`-групи, `EN/security/f3d_energy_security.xml:28-38`);
   - адаптер `GB/adapters/td_genset.py` віддає факти ДГУ (паливо 78 %, тест о 07:02, пробний пуск 19.10 06:30) у картку вузла `ATS-1`/`GENSET` та Пульт.
3. Критичні ризики: пульт td_genset (OWL, `static/src/pult`) працює як client action під будь-яким меню — перевірити
   у тесті; `menu_root` td_genset лишається у автономній установці.

## 4. Мультиресурсність

### 4.1 Стан

`EN` — електрицентричний: `f3d.energy.node` має електричні види й поля (`EN/models/f3d_energy_node.py:26-39`, `rating_a/kva/kvar`, `cos_phi_nominal`),
`f3d.energy.meter` — ролі ввід/фідер/споживач/генерація/накопичувач і сигнали `e_import/e_export` (`EN/models/f3d_energy_meter.py:44-68`), `node_id` обовʼязковий (`:32`),
`f3d.energy.interval` — `kwh`, `kwh_export`, `kw_avg`, тарифна зона, ціна (`EN/models/f3d_energy_interval.py:46-51`), тариф — зони/договірна потужність
(`EN/models/f3d_energy_tariff.py`). Код вузла глобально унікальний (`:130`), перевірки прив'язані до `kind`. Не-електричні сигнали, що вже є:
вода (`infra/water/*`), `infra/chp/gas_m3h|heat_kw`, тепло BMS (`equipment/BOILER/heat_kw|return_c`, `ventilation/units/*/heat_kw`).
Немає: головний газовий лічильник, газ котельні, витрата й тиск стисненого повітря, квар·год, підлічильники води.

### 4.2 Пропозиція (модуль `td_energy_resources`, W3)

Принцип: **не змінювати семантику електричних таблиць**; розширити `td.energy.meter`, додати паралельну таблицю інтервалів ресурсів і SQL-зведення для аналітики.

| Об'єкт | Призначення | Ключові поля |
|---|---|---|
| `td.energy.resource` | довідник (5 записів: `el`, `gas`, `heat`, `air`, `water`) | `code`, `name`, `uom_label` («кВт·год», «м³»), `rate_label` («кВт», «м³/год»), `kwh_per_unit` (газ 10,5), `co2_kg_per_unit`, `is_derived` (тепло, повітря — не сумуються у вартості), `daily_limit`, `sequence` |
| `td.energy.price` | ціни неелектричних ресурсів | `resource_id`, `date_from/to`, `price`, `currency_id`, `company_id`; електрика лишається у `td.energy.tariff` |
| `td.energy.point` | точка обліку/споживач ресурсу (плоский список макета: BOILER, DRY-1, CANTEEN, SPRAY-1…) | `resource_id`, `code`, `name`, `kind` (source/branch/consumer), `parent_id`, `equipment_id`, `workcenter_id`, `area_id`, `hvac_unit_id` |
| `td.energy.meter` (`_inherit`) | узагальнення лічильника | `resource_id` (default = `el`), `point_id`, `mode` (`counter` / `flow_integrate` / `estimate`), `node_id` — `required` лише для `el` |
| `td.energy.res.interval` | 15-хв ряд для не-електрики | `meter_id`, `resource_id`, `ts_start`, `day`, `hour_local`, `qty`, `rate_avg`, `price`, `cost`, `quality` (measured/estimated/missing) |
| `td.energy.usage` (SQL-view, `_auto=False`) | зведення для аналітики: `UNION` `td.energy.interval` (role feeder/incomer/generation) і `res.interval` | `resource_id`, `day`, `hour_local`, `node_id/point_id`, `qty`, `kwh_eq`, `cost`, `co2_kg` |

Побудова інтервалів — той самий патерн, що R-04 (`EN/tools/counter.py`, `EN/models/f3d_energy_interval.py:73`): `counter` — через безперервний лічильник;
`flow_integrate` — трапецієвий інтеграл потужності/витрати (`tools/integrate.py`) для сигналів кВт та м³/год;
`estimate` — паспорт × стан обладнання (повітря, підлічильники води). Окремий крон; ротація як R-19.

### 4.3 Одиниці й ціни

| Ресурс | Кількість | Миттєва | У кВт·год | Ціна | Вартість |
|---|---|---|---|---|---|
| Електрика | кВт·год | кВт | 1 | `td.energy.tariff` (зони) — **є** | `Σ kwh × price` — є |
| Газ | м³ | м³/год | × `kwh_per_unit` (10,5) | `td.energy.price` (макет 19,80 ₴/м³) | `qty × price` |
| Тепло | кВт·год тепла | кВт | 1 | похідна: `price_gas / (kwh_per_unit × η_котельні)` або закупівля | `is_derived` — не додається до «разом» |
| Стиснене повітря | норм. м³ | м³/хв | — | похідна: вартість електрики компресорів | `is_derived` |
| Вода | м³ | м³/год | — | `td.energy.price` (макет 60 ₴/м³) | `qty × price` |

η котельні: до появи газового лічильника — параметр (дизайн-значення), потім — розрахунок (RS-06). Повітря: питома потужність = `P_COMPRESSOR / flow`.

### 4.4 Зв'язок із BMS

`f3d.bms.heat.balance` — **проєктний розрахунок** на розрахункову зовнішню температуру (`BM/models/f3d_bms_heat_balance.py:85-124`: `total_kw`, `capacity_kw`, `reserve`), не часовий ряд.
Для тепла: (1) `post_init_hook` створює `td.energy.meter(mode='flow_integrate')` на **ті самі сигнали** (`boiler_heat_signal_id`, `chp_heat_signal_id`, `hvac.unit.heat_signal_id`) — без дублювання сигналів;
(2) «Куди йде тепло» = Σ по `td.energy.point.hvac_unit_id`; (3) `capacity_kw`/`boiler_kw` — лінії ліміту на графіку;
(4) `indoor_c`/уставка/зовнішня — прямо з `BM` (`f3d_bms_hvac_unit.py:160-165`); (5) рекуперація = (T_приплив − T_зовн)/(T_витяжка − T_зовн), потрібен сигнал витяжки.

## 5. Аналітика

### 5.1 EnPI і база (ISO 50001), модуль `td_energy_analytics` (W4)

| Об'єкт | Поля / логіка |
|---|---|
| `td.energy.driver` | `code` (`plate_m2`, `hdd`, `days`, `manual`), `source_kind` (`mrp_area`, `weather_hdd`, `calendar`, `manual`), `uom`. `hdd` = max(0, 18 − T_середня) з `ventilation/totals/outdoor_c`; `plate_m2` — Σ площі плит, поданих у розкрій за добу (Q-05) |
| `td.energy.baseline` | `resource_id`, `scope` (завод/ділянка), `period_from/to` (2025), `const_per_day` (1 820), рядки `driver_id × coef` (4,1 кВт·год/м²), `r2`, `method` (`ols`/`manual`), `state` draft/approved, `fitted_at`. OLS — нормальні рівняння для ≤ 3 драйверів (чиста Python-реалізація, без numpy) |
| `td.energy.enpi` (зберігається щодобово) | `day`, `baseline_id`, `actual_kwh` (Σ інтервалів `role='feeder'`), `expected_kwh` (const + Σ coef × driver), `drivers` Json, `enpi` = actual/expected. Крон після закриття доби; перерахунок із wizard перерахунку (є: `f3d.energy.recompute.wizard`, `EN/wizard/recompute_wizard.py`); тижні/місяці — `_read_group('day:week')` |

Макет: EnPI 0,94, «економія 6 %» = 1 − Σ actual / Σ expected за період; на тиждень `expected = (1820×7 + 4,1×plate)/1000` МВт·год (формула у `Analytics.dc.html`).

### 5.2 Бюджет

`td.energy.budget`: `company_id`, `month`, `resource_id` (або «усі»), `amount_uah`, `amount_qty` (опц.), `state`. Факт = Σ `cost` місяця
(`td.energy.usage`); частка місяця = дні/календар змін; прогноз = факт + Σ typical-day (за днем тижня, R-15 п.5 `EN/models/f3d_energy_interval.py:405`) по залишку.
Індикатор макета «56 % при 55 % місяця» = факт/бюджет проти частки відпрацьованих днів.

### 5.3 Резерви економії (правила, пороги конфігуровані)

Модель правила `td.energy.opportunity.rule`: `code`, `name`, `enabled`, `detector` (ключ у реєстрі `tools/detectors/`), `params` Json + схема (пороги в UI «Налаштування»), `lookback_days`, `min_saving_uah`, `action_kind` (scenario / ticket / setpoint / schedule / report).
Результат `td.energy.opportunity`: `rule_id`, `found_at`, `state` (new / in_plan / done / dismissed), `est_saving_month`, `evidence` Json, `request_id`, `in_plan`. Крон щодоби; оцінка перераховується, `in_plan` зберігається.

| Правило макета | Детектор і формула | Пороги за замовчуванням | Джерело даних |
|---|---|---|---|
| Вентиляція поза змінами | Σ kWh вузлів `group='vent'` у слотах поза зміною (календар змін) − 30 % від денного рівня; × 4,33 тижня × ціна | рівень > 35 % денного; ≥ 1 000 ₴/міс | `td.energy.interval` (`hour_local`, `day`), `shift_calendar_id` |
| Холостий хід верстатів | Σ `alloc.kind='idle'` за 7 діб × 4,33 × ціна × 70 % зворотна частка | idle > 5 % енергії РЦ | `f3d.energy.alloc` (`EN/models/f3d_energy_alloc.py:22`) |
| Витоки стисненого повітря | нічна мін. витрата (або нічна потужність компресора при відсутності завдань) × години × ціна × 65 % | нічна частка > 10 % денної | `res.interval(air)` або інтервали COMPRESSOR + `mrp.workorder` |
| Розігрів цеху зарано | (T_start_зміни − T_готовності) × газ/год × ціна × робочі дні | запас > 30 хв | `ventilation/totals`, `indoor_c`, `equipment/BOILER/*`, календар |
| Реактивна енергія секції | cos φ секції < ціль > N год/добу; оцінка за формулою доплати тарифу | ціль 0,92; ≥ 2 год | сигнали `energy/sections/S*/cos_phi` (PU-10), тариф (Q-10) |
| AHU-1: низька рекуперація | (η_норма − η) × тепло AHU × дні × ціна тепла; фільтр ΔP > ліміту | η < 70 %; ΔP > 250 Па | BMS `filter_dp_pa`, `heat_kw`, T-сигнали |
| Тиск повітря завищений | (уставка − p_min_споживачів − запас) × 7 %/бар × кВт·год компресорів × ціна | запас > 0,3 бар | `air/setpoint_bar`, паспорти споживачів |
| Експорт СЕС дешевше закупівлі | Σ `kwh_export` × (ціна купівлі − ціна експорту) × 30 | експорт > 10 кВт | `EN/models/f3d_energy_interval.py:47`, `tariff.export_price` (`EN/models/f3d_energy_tariff.py:29`) |

### 5.4 Джерела даних для візуалізацій

| Візуал | Таблиця / запит | Група / міра |
|---|---|---|
| Стовпці за ділянками | `td.energy.interval` (`role='consumer'`) → `node_id.area_id` (нове) | `day:day/week/month` × `area`, `kwh:sum` |
| Теплокарта год×день | `td.energy.interval` (`role='feeder'`), індекс `(day, role)` (`EN/models/f3d_energy_interval.py:68`) | `_read_group(['day:day_of_week','hour_local'], ['kwh:sum'])`, середнє = Σ kwh / (к-сть днів тижня в періоді) |
| Розріз «обладнання» | інтервали споживачів + `alloc.minutes` | `node_id`; кВт·год/мотогод = kwh / (minutes/60) |
| Розріз «замовлення» | `f3d.energy.alloc` | `production_id`; кВт·год/шт = kwh / `qty_produced` |
| Розріз «продукти» | `alloc.production_id.product_id` (stored related) | `product_id` |
| Розріз «зміни» | інтервали за `hour_local` + календар змін; `kwh_shift` R-11 | зміна 1/2/ніч+вихідні |
| EnPI, бюджет | `td.energy.enpi`, `td.energy.budget` | тижні, місяць |
| Зв'язок з виробництвом | `mrp.production`/`mrp.workorder` ↔ `alloc` | `f3d_energy_*` поля МО (`EN/models/mrp_production.py:17-43`) |

### 5.5 Дані для демо

На демо-БД інтервалів 0 (розд. 0). Для екранів W4 потрібен **генератор історії** (`tools/gen_energy_history.py`, 400 діб 15-хв за профілем макета:
210 кВт база, зміни 07:00–23:00, вихідні, СЕС) — окрема підзадача W4-A; для W1 достатньо живого стенду `iot_sim`+колектор.

## 6. Нові моделі, поля, API (орієнтовні розміри: S ≤ 100, M ≤ 300, L ≤ 800 рядків разом з тестами)

| # | Об'єкт | Модуль | Хвиля | Розмір |
|---|---|---|---|---|
| 1 | `td.energy.event` (+`state`,`title`,`detail`,`acked_by/at`,`resolved_at`,`assigned_user_id`,`taken_at`,`action_kind`) | td_energy | W1 | S |
| 2 | `td.energy.node` (+`sld_x/y/w/h`,`sld_show`,`sld_state`,`protection_*`,`trip_count_year`) | td_energy | W1 | S |
| 3 | `td.energy.meter` (+`next_verification`,`verification_months`) | td_energy | W1 | S |
| 4 | `td.energy.outage.plan` | td_energy | W1 | M |
| 5 | `td.energy.advice` (рекомендації, snooze/done) | td_energy | W1 | M |
| 6 | `td.energy.dashboard` (AbstractModel: `get_data(period)`, `get_node_card(code)`, `get_alarms()`, `action_ack`) + `tools/dashboard.py` | td_energy | W1 | L |
| 7 | Сигнали `energy/sections/S{1,2}/cos_phi` (обчислювані) | td_energy | W1 | S |
| 8 | OWL «Пульт» (SLD SVG, KPI, профіль, тривоги) + картка вузла + розділ «Генерація й резерв» | td_energy | W1 | L |
| 9 | Меню розділу, приховування «Генератор», адаптер фактів ДГУ, `implied_ids` | td_genset_factory3d | W1 | M |
| 10 | `td.energy.scenario`, `.shed.item`, `.interlock`, `.command.kind`, `.schedule.slot` | td_energy_control | W2 | L |
| 11 | `td.energy.action` (журнал+підтвердження, токен) + `prepare/confirm/undo` | td_energy_control | W2 | M |
| 12 | `GET /td/energy/automation/config`, `POST …/state` | td_energy_control | W2 | M |
| 13 | `f3d.source.MODULES += energy_control`; параметр `td.energy.control_enabled` | td_energy_control | W2 | S |
| 14 | OWL «Керування» (сценарії, пріоритети, команди, розклад, журнал) + діалог підтвердження | td_energy_control | W2 | L |
| 15 | Плагін-рушій збирача `td_collector_energy` | services/collector_plugins | W2 | L |
| 16 | Емулятор: регістри/реакції BESS, QS, КГУ, PFC, компресор | services/iot_sim | W2 | M |
| 17 | `td.energy.resource`, `.price`, `.point`, `.res.interval`, `.usage` (SQL-view), `meter` (+`resource_id`,`point_id`,`mode`) | td_energy_resources | W3 | L |
| 18 | `tools/integrate.py`, крон інтервалів ресурсів, BMS-прив'язка (`post_init_hook`) | td_energy_resources | W3 | M |
| 19 | Нові сигнали: газ (головний/котельня), повітря (витрата/тиск/уставка), квар·год, підлічильники води + емулятор (`boiler.py`, `compressor.py`, `water.py`, `meter.py`) | td_energy_resources + services/iot_sim | W3 | M |
| 20 | `td.energy.opportunity.rule`, `.opportunity` + 8 детекторів, UI порогів | td_energy_resources | W3 | L |
| 21 | OWL «Енергоресурси» (5 вкладок) | td_energy_resources | W3 | L |
| 22 | `td.energy.area` + `node.area_id`; `td.energy.driver`, `.baseline`, `.enpi`, `.budget` | td_energy_analytics | W4 | L |
| 23 | Аналітичний API: KPI, стек, теплокарта, зрізи, прогноз бюджету | td_energy_analytics | W4 | M |
| 24 | OWL «Аналітика» + PDF «керівництву» і «за зміну» (qweb) + «у плані» | td_energy_analytics | W4 | L |
| 25 | Генератор історії для демо | td_energy_analytics | W4 | S |
| 26 | `td_energy_mobile`: клієнтська дія, `td.energy.round`, `.round.item`, «беру в роботу», `bus` | td_energy_mobile | W4 | L |

Орієнтовний обсяг: W1 ≈ 4 k, W2 ≈ 5 k, W3 ≈ 5 k, W4 ≈ 5,5 k рядків (код+тести). Нові групи: `group_td_energy_operator` («енергетик»,
команди класу A), `group_td_energy_chief` («головний енергетик», клас B); існуюча `group_f3d_energy_manager` («Енергетика: енергетик», `EN/security/f3d_energy_security.xml:21-22`) — кандидат у «оператор».

## 7. Хвилі постачання

Спільний порядок у кожній хвилі (E-02): **крок 0 — SPEC/ARCH** (до 3 SPEC-воркерів за модулями, приймання Opus) → код → тести (`run_tests.sh`) → сервер (`serve.sh` + Playwright-перевірка екрана).
Файли `__manifest__.py`, `ir.model.access.csv`, `menus.xml` модуля, що спільні між задачами, зливає менеджер (задачі описують потрібні рядки в відповіді).

### W1. Пульт + картка вузла + генератор усередині + події

| Задача | Файли (власні) | Залежності |
|---|---|---|
| W1-A бекенд Пульту | `td_energy/models/{event_alarm,node_sld,meter_verification,outage_plan,advice}.py`, `td_energy/tools/dashboard.py`, `td_energy/data/sld_geometry.csv`, `td_energy/tests/test_w1_*.py` | контракт API з SPEC (JSON-схема `get_data`) |
| W1-B фронтенд Пульту й картки | `td_energy/static/src/{pult,node_card}/**`, `td_energy/static/tests/**`, `td_energy/views/td_energy_pult_views.xml`, `td_energy/views/menus.xml` (власник меню, включно з `menu_td_energy_generation`) | W1-A (поля/метод) — паралельно за контрактом |
| W1-C генератор усередині | `td_genset_factory3d/{views/menus.xml,views/section_views.xml,models/*,adapters/*,data/*,hooks.py,tests/*}` | `menu_td_energy_generation` з W1-B; `td_genset` не змінюється |

### W2. Керування

| Задача | Файли (власні) | Залежності |
|---|---|---|
| W2-A бекенд керування | `td_energy_control/{models,tools/interlocks.py,controllers,data/*.csv,security,tests}` | W1-A (`advice`) |
| W2-B фронтенд керування | `td_energy_control/{static/src/control/**,views/*.xml,wizard/*}` | W2-A (методи `prepare/confirm`) |
| W2-C рушій і емулятор | `factory3d/services/collector_plugins/td_collector_energy/**`, `factory3d/services/iot_sim/iot_sim/models/{bess,chp,ats,transformer,compressor}.py`, `services/iot_sim/catalog/signals.csv`, `factory3d_iot_sim/data/f3d_sim_signal.csv` | конфіг-контракт з SPEC W2-A |

### W3. Енергоресурси

| Задача | Файли (власні) | Залежності |
|---|---|---|
| W3-A шар даних ресурсів + сигнали | `td_energy_resources/{models/resource*.py,tools/integrate.py,hooks.py,data/*}`, `services/iot_sim/iot_sim/models/{boiler,compressor,water,meter}.py` (газ/повітря/квар·год), `telemetry/data/signal_catalog.csv` | `td_bms` (сигнали тепла) |
| W3-B двигун резервів | `td_energy_resources/{models/opportunity*.py,tools/detectors/*.py,data/opportunity_rules.xml,views/opportunity_views.xml}` | W3-A (`usage`), W2 (дії-уставки) |
| W3-C екран «Енергоресурси» | `td_energy_resources/{static/src/resources/**,views/resources_views.xml,views/menus.xml}` | W3-A/W3-B (API) |

### W4. Аналітика + мобільний

| Задача | Файли (власні) | Залежності |
|---|---|---|
| W4-A бекенд аналітики | `td_energy_analytics/{models,tools,data,tests,tools/gen_energy_history.py}` | W3-A (`usage`) |
| W4-B фронтенд й звіти | `td_energy_analytics/{static/src/analytics/**,views,report/*.xml}` | W4-A |
| W4-C мобільний | `td_energy_mobile/**` (контролери, OWL, `round*`, тести) | W1-A (події/«беру в роботу») |

Ризики плану: (1) перейменування (E-04) ще в польоті — SPEC писати вже в td-іменах, код W1 стартує після злиття гілки (Q-13);
(2) порожня демо-БД (розд. 0) — потрібні стенд або сід; (3) продуктивність `get_data` на 123 вузлах/67 лічильниках — ціль < 500 мс (один `search_read` сигналів, як R-16, `SPEC:1344`);
(4) ліцензії OPL-1/LGPL-3 при будь-якому злитті коду (розд. 3.2).

## 8. Відкриті питання (лише реальні рішення, з рекомендацією)

| ID | Питання | Рекомендація |
|---|---|---|
| Q-01 | ~~Кореневу плитку td_genset ховати при мості?~~ **Закрито E-08** | `active=False` у мості, відновлення в `uninstall_hook`; меню td_genset не чіпати, у мості — нові меню. |
| Q-02 | ~~Хто виконує автоматику~~ **Закрито E-05** | v1 — плагін-рушій збирача; hard-блокування лише в пристроях/плагіні; той самий конфіг-контракт придатний для PLC пізніше. |
| Q-03 | ~~Класи команд і права~~ **Закрито E-06** | Клас A — оператор; клас B (QS, пуск КГУ, розряд BESS, зміна пріоритетів) — головний енергетик або друга особа; одна нова група. |
| Q-04 | Ресурсні інтервали: окрема таблиця чи узагальнення `interval`? | Окрема `td.energy.res.interval` + SQL-зведення `td.energy.usage` (електричні запити й 142 тести не чіпаємо). |
| Q-05 | ~~Звідки брати «м² плити»~~ **Закрито E-07** | Драйвер з МО: Σ площі плит у розкрої (атрибут площі продукту × `qty` за `mrp.workorder` розкрою); запасний — ручний ввід за добу. Потрібне підтвердження замовника, які дані є. |
| Q-06 | ~~Які лічильники газу/повітря/тепла існують~~ **Закрито E-07** | Будувати W3 на сигналах із якістю `estimated` (газ — за теплом котла/ККД, повітря — за P компресора/питомою), реальні лічильники підключати без зміни UI. |
| Q-07 | Гроші в Пульті/мобільному — за групою вартості? | Так: ключ `cost` приховувати без `group_f3d_energy_cost` (як зараз, `EN/models/f3d_energy_interval.py:50`), у kiosk — ніколи. |
| Q-08 | У макеті немає екрана «Генерація й резерв», «Події», «Налаштування», «Вузли мережі» | Стандартні Odoo list/kanban/form (не кастомні OWL): розділ — kanban вузлів генерації; «Події» — list; «Налаштування» — існуючі. Дизайн лише для Пульту, Керування, Ресурсів, Аналітики, Мобільного. |
| Q-09 | ~~Єдина норма cos φ~~ **Закрито E-10** | Одна норма в параметрі `td.energy.cos_phi_norm` (0,92), цільова уставка PFC — окремо (0,95); пороги сигналу вирівняти. |
| Q-10 | Реактивна енергія: чи є доплата в договорі (макет: «ризик доплати», tg φ 0,40)? | Додати в тариф параметри (`tg_phi_limit`, коефіцієнт); правило-резерв вмикати лише за наявності. |
| Q-11 | Планові відключення: що робить «узгодження виробництвом»? | v1 — сповіщення + `mail.activity` планувальнику/складу й статус; **без** автоматичного перенесення МО. |
| Q-12 | Прогноз профілю/СЕС | Типовий день за днем тижня (R-15) + кліматична крива СЕС; погодний прогноз — поза v1. |
| Q-13 | ~~Коли стартувати код W1~~ **Закрито E-09** (лишається відкритим лише префікс моделей моста: `W1_SPEC.md` Q-25). Раніше: коли стартувати код W1 відносно гілки `claude/td-rename`? Імена моделей моста (`td.genset.link|profile|event.map`) не колідують з `td_genset` за назвами, але займають його простір імен | SPEC — зараз у td-іменах; код — після злиття перейменування; для моста розглянути окремий префікс (`td.genset3d.*`). Потрібна повна таблиця перейменувань (xml-id, групи, ключі, URL). |
| Q-14 | Мобільний: що таке «додаток» і сповіщення? | v1 — адаптивна клієнтська дія Odoo + `bus`; Web Push — окремим рішенням після W4. |
