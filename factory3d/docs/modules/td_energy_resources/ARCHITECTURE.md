# td_energy_resources — технічне рішення (W3 «Енергоресурси»: модулі `td_energy_resources` і `td_energy_resources_bms`)

Версія 0.2 · 19.10.2026 (v0.1 — 18.10.2026) · автор: агент-аналітик (хвиля W3 блоку «Енергетика») · статус: **погоджено, збудовано (гілка `claude/td-energy-w4`, W1–W4)**.
Вхід: `build/energy/GAP.md` (E-01…E-11, §4 «Мультиресурсність», §5.3 «Резерви економії», матриця RS-01…RS-15), макет `Resources.dc.html`. Каркас: `docs/ARCHITECTURE.md` §3, §5, §6.4; D-18 (необов'язкові зв'язки). Контракти й код W1: `build/energy/W1_SPEC.md`, `W1_ARCH.md`, `odoo_addons/td_energy` на гілці `claude/factory3d-build` (`d14d13c`). Специфікація: [SPEC.md](SPEC.md) (далі SPEC). Імена — td (E-04, E-09): маршрути `/f3d/*` і коди сигналів не змінюються.
Мова: проза — українською (`docs/DOC_STANDARD.md`), рядки інтерфейсу й `string=` — українські.
Паралельна робота: W2 «Керування» (модуль `td_energy_control`, [../td_energy_control/ARCHITECTURE.md](../td_energy_control/ARCHITECTURE.md)) писалася незалежно; тут на неї посилання **лише через контракти** (C-02).
Документ розкладено за модулями: `td_energy_resources` (цей файл і `SPEC.md`) і міст `td_energy_resources_bms` ([ARCHITECTURE.md](../td_energy_resources_bms/ARCHITECTURE.md) — виписка рішення A-01, контракту C-04 і воркера B); перелік змін — у «Журналі змін документа» в кінці файлу.

## Загальна інформація

| Етап ToDo | Що здається | Люд.-год (оцінка автора) |
|---|---|---|
| ТР | `SPEC.md` + цей документ | 24 |
| Архітектура | погодження A-01…A-16, Q-01…Q-08, фіксація контрактів C-01…C-06 і API-01, API-02, API-10 | 6 |
| Розробка | A «дані» ≈ 36, B «резерви й міст» ≈ 36, C «екран» ≈ 32, D «емулятор і сигнали» ≈ 20, E «API екрана й експорт» ≈ 24 | 148 |
| Тестування | 74 AC: UT ≈ 63, hoot ≈ 1, стенд ТК-01…ТК-06 і ТК-B1 ≈ 12, DEPLOY_TEST ≈ 4 | 36 |
| Інструкція | §4 цього документа + README/CHANGELOG | 6 |
| **Разом** | | **220** |

Факти середовища (перевірено 18.10.2026, лише читання; на момент написання): W1 у коді (`td_energy` `19.0.1.1.0`: `td.energy.dashboard`, `td.energy.advice`, `tools/backfill.py`, мобільний екран із реєстром вкладок); сигналів газу/повітря/квар·год, теплового балансу котельні й підживлення води в демо **немає** (є `infra/water/*`, `infra/chp/gas_m3h|heat_kw`, `equipment/BOILER/heat_kw|supply_c|return_c`, `equipment/COMPRESSOR/state|temp_c|pressure_bar|load`, `ventilation/units/*/heat_kw`, `ventilation/totals/outdoor_c`); `BOILER` в емуляторі — **брикетний** (`silo_fill`); сирі `td.reading` зберігаються 30 діб (`td.telemetry.keep_days`), годинні агрегати — 400; вільні Modbus-unit: 74, 75; останній `n` у `signals.csv` емулятора — 1177 (після W2 — 1205; сигнали W3 — n 1206…1215, див. SPEC §5.4).

## 1. Опис процесу й функціональні вимоги

### 1.1 Контекст

**Макет (затверджено замовником).** `Resources.dc.html`: шапка з підсумком «Сьогодні разом» і кнопкою «Вивантажити в Excel»; 5 вкладок ресурсів (Електрика, Газ, Тепло, Стиснене повітря, Вода) з підписом «зараз · ₴»; 4 KPI на вкладку; графік доби 15 хв із лімітом і маркером «зараз»; список споживачів; блок «Що помітила система» з кнопками дій. Відхилення — SPEC «D-31…D-48» (коротко: підсумок і підписи будуються з даних, підписи графіків генеруються, числа демо ≠ числа макета, рекуперація — оцінка, DOCK і OFFICE — оцінка/залишок, на вкладці всі відкриті резерви ресурсу, експорт — реальний xlsx, осі графіків обчислюються).

**Що вже є (гілка `claude/factory3d-build`).**

| Складова | Де | Що дає W3 |
|---|---|---|
| Електричні інтервали, тариф, зони, ціна | `td_energy/models/td_energy_interval.py:23-69`, `td_energy_tariff.py` | електрична вкладка, вартість повітря, ціни резервів |
| Живі KPI, профіль доби, прогноз | `td_energy/tools/dashboard.py`, `models/td_energy_dashboard.py` (`get_pult`) | вкладка «Електрика» без дублювання розрахунків |
| Реєстр дій рекомендацій, обробники | `td_energy/models/td_energy_advice.py:56-110` (`actions[]`, `_td_control_available`), `static/src/common/advice.js` | дії резервів (C-02, FR-15) |
| Шина, throttle | `td_energy/tools/bus.py` (`KINDS = kpi, alarm, profile, state, advice`) | оновлення екрана за `kpi` |
| Лічильник із накопичувальним рядом | `td_energy/tools/counter.py` (`CounterSeries`) | режим `counter` для не-el (R-03) |
| Генератор історії, детермінований шум | `td_energy/tools/backfill.py` (`rnd`, `target_p`, `sun_factor`, `Plan`) | розширення на ресурси (R-22) |
| Розподіл енергії на МО, простій | `td_energy/models/td_energy_alloc.py` (`kind='idle'`), `mrp_*` | детектор `idle_machines` |
| Телеметрія | `td_telemetry` (`td.signal`, `td.reading`, `td.reading.hour`, `td.source`) | лічильники й сигнали ресурсів |
| Тепловий баланс, установки | `td_bms/models/td_bms_heat_balance.py:117-137`, `td_bms_hvac_unit.py:143-167` | міст: теплові лічильники й KPI |
| Емулятор води, котельні, компресора, лічильників | `services/iot_sim/iot_sim/models/{water,boiler,compressor,meter}.py` | нові сигнали, backfill |
| Шаблон qweb-pdf, xlsx | `td_fire_safety/report/`, `td_genset/data/ir_exports.xml` | експорт (A-10) |

**Покриття матриці GAP (RS):** RS-01, RS-02 (вкладки, підсумок) — FR-08; RS-03 (реактивна енергія) — FR-07, FR-21; RS-04, RS-05 — FR-08, FR-09; RS-06, RS-07 (газ) — FR-04, FR-09; RS-08, RS-09 (тепло) — FR-16, FR-B1…B3; RS-10, RS-11 (повітря) — FR-04, FR-09; RS-12, RS-13 (вода) — FR-04, FR-09; RS-14 (резерви) — FR-13…FR-15; RS-15 (Excel) — FR-12. Усі 15 елементів закрито.

### 1.2 Ролі й сценарії

| Роль (група) | Що робить у W3 | Меню |
|---|---|---|
| Перегляд (`td_energy.group_td_energy_user`) | дивиться екран ресурсів, резерви, завантажує xlsx (без ₴) | Енергетика → Енергоресурси, Резерви економії |
| Вартість (`…_cost`) | то же + ₴ | то же |
| **Енергетик** (`…_manager`) | ставить резерв «у план», відхиляє, закриває; правит ціни, точки, пороги правил; запускає правило | + «Налаштування → Енергоресурси» |
| Головний енергетик (`…_chief`) | як «Енергетик» (окремих прав у W3 немає) | те саме |
| Адміністратор (`td_factory3d.group_td_admin`) | backfill ресурсів, створення правил, uninstall | Налаштування |

Сценарії: **S1** огляд ресурсів за зміну (екран «Енергоресурси», вкладки по черзі); **S2** розбір «Що помітила система»: відкрити резерв → дія (заявка ТО / сценарій W2, якщо встановлено); **S3** вивантаження 15-хв інтервалів за день в Excel; **S4** введення ціни газу й води (Налаштування → Ціни); **S5** налаштування порогів правила; **S6** демо-стенд: адміністратор запускає `res.interval._td_backfill(days=90)` після електричного backfill.

### 1.3 Функціональні вимоги

| ID | Модуль | Вимога |
|---|---|---|
| FR-01 | td_energy_resources | Довідник ресурсів (5 записів) з одиницями, коефіцієнтами, лімітами й прапорами екрана |
| FR-02 | td_energy_resources | Ціни неелектричних ресурсів за датами; електрика лишається в тарифі |
| FR-03 | td_energy_resources | Точки обліку ресурсу (джерело/гілка/споживач) з ієрархією й методом оцінки |
| FR-04 | td_energy_resources | Лічильники будь-якого ресурсу в режимах `counter`, `flow_integrate`, `estimate` на єдиному `td.energy.meter`; електричні розрахунки не зачеплені |
| FR-05 | td_energy_resources | 15-хвилинні інтервали ресурсів із якістю, ціною, вартістю, kWh-екв.; крон, ротація, ідемпотентність |
| FR-06 | td_energy_resources | SQL-зведення `td.energy.usage` за потоками (`import`, `export`, `generation`, `load`, `supply`, `branch`) для аналітики й експорту |
| FR-07 | td_energy_resources | Реактивна енергія вводів (квар·год), tg φ, оцінка доплати за тарифом |
| FR-08 | td_energy_resources | API екрана: вкладки, підсумок «разом», графік доби 96 слотів, список споживачів |
| FR-09 | td_energy_resources | KPI за ресурсами (по 4 на вкладку) з ознакою якості й тоном |
| FR-10 | td_energy_resources | Баланс «джерело − гілки» як індикатор без тривог |
| FR-11 | td_energy_resources | Клієнтська дія «Енергоресурси» (5 вкладок), оновлення за шиною, адаптив ≥ 360 px |
| FR-12 | td_energy_resources | «Вивантажити в Excel»: інтервали ресурсів за добу/діапазон; вартість — лише з групою |
| FR-13 | td_energy_resources | Рушій резервів: правила з порогами в налаштуваннях, життєвий цикл, «у плані», права |
| FR-14 | td_energy_resources(+bms) | Дев'ять детекторів (6 ядра + 3 моста) з оцінкою ₴/міс і числом-підставою |
| FR-15 | td_energy_resources | Дії резервів за контрактом C-32 (link/ticket/control), зв'язок із заявкою ТО |
| FR-16 | td_energy_resources(+bms) | Тепло: гаки ядра й теплові точки/лічильники з BMS (міст) |
| FR-17 | td_energy_resources + iot_sim | Сигнали газу, повітря, води котельні, квар·год (10 сигналів, 2 джерела) |
| FR-18 | td_energy_resources | Розширення backfill на ресурси (стик із W1 R-36) |
| FR-19 | td_energy_resources | Групи, ACL, cost-gating, record rules, `neutralize.sql`, `uninstall_hook` |
| FR-20 | td_energy_resources | Налаштування й параметри `td.energy_resources.*` |
| FR-21 | td_energy_resources | Параметри тарифу для реактивної енергії (`tg_phi_limit`, `react_rate`) |
| FR-22 | td_energy_resources | Спільний хелпер вікон змін і ночі (контракт для W4) |
| FR-23 | iot_sim | Сценарії `air_leak`, `gas_overuse`, `water_leak` (S-21…S-23 емулятора) |
| FR-24 | td_energy_resources | Продуктивність і обсяги (розд. 2.7) |
| FR-B1 | td_energy_resources_bms | Теплові точки й лічильники з `td.bms.heat.balance` і `td.bms.hvac.unit`, ідемпотентно, незалежно від порядку встановлення |
| FR-B2 | td_energy_resources_bms | KPI «Температура в цеху», «Рекуперація AHU-1», список «Куди йде тепло», примітка `{capacity}` |
| FR-B3 | td_energy_resources_bms | Детектори `preheat_early`, `ahu_recuperation`, `dock_gates` |

### 1.4 Межі (не входить у W3)

Команди, сценарії, блокування, розклади й уставки (W2: `td_energy_control` — тут лише контракт C-02); аналітика, EnPI, бюджет, зрізи, PDF-звіти, мобільний «Обхід» (W4); події й тривоги за балансами й лімітами ресурсів (A-14); реальні прилади газу/повітря/тепла (E-07: оцінки й сигнали емулятора, заміна на об'єкті без правки UI); автоматична зміна уставок і графіків (лише через W2); Web Push; запис у пристрої (`write_enabled` не змінюється).

### 1.5 Критерії приймання (зведення; повний текст — SPEC розд. 12)

Усього **74 критерії**: ядро AC-01…AC-64, міст AC-B01…AC-B10. Типи перевірки: UT (юніт-тест `odoo.tests`, зокрема HttpCase і pytest емулятора) / UT-JS (hoot) / TC (стенд на емуляторі) / DEPLOY_TEST.

| FR | AC | Разом | Тип перевірки |
|---|---|---|---|
| FR-01 | AC-01, 02 | 2 | UT |
| FR-02 | AC-03 | 1 | UT |
| FR-03 | AC-04 | 1 | UT |
| FR-04 | AC-05, 06, 11…15 | 7 | UT (AC-05 + DEPLOY_TEST) |
| FR-05 | AC-07…10, 16…18 | 7 | UT |
| FR-06 | AC-19 | 1 | UT |
| FR-07 | AC-20 | 1 | UT |
| FR-08 | AC-21, 26…28, 30, 31 | 6 | UT |
| FR-09 | AC-22…25 | 4 | UT (числа макета у фікстурах) |
| FR-10 | AC-29 | 1 | UT |
| FR-11 | AC-57, 58, 59 | 3 | UT-JS, UT (HttpCase), TC |
| FR-12 | AC-44, 45 | 2 | UT (HttpCase), TC |
| FR-13 | AC-32, 33, 42, 43 | 4 | UT |
| FR-14 | AC-34…39, 62 | 7 | UT (6), TC (1) |
| FR-15 | AC-40, 41 | 2 | UT |
| FR-16 | AC-64 | 1 | UT |
| FR-17 | AC-54, 55 | 2 | UT, UT-pytest |
| FR-18 | AC-46…48 | 3 | UT |
| FR-19 | AC-49, 50, 63 | 3 | UT (AC-50 + DEPLOY_TEST) |
| FR-20 | AC-51 | 1 | UT |
| FR-21 | AC-52 | 1 | UT |
| FR-22 | AC-53 | 1 | UT |
| FR-23 | AC-56 | 1 | UT-pytest + TC |
| FR-24 | AC-60, 61 | 2 | UT (ТП-01…ТП-04) |
| FR-B1 | AC-B01, B02, B09 | 3 | UT, UT + DEPLOY_TEST |
| FR-B2 | AC-B03…B05, B10 | 4 | UT (3), TC (1) |
| FR-B3 | AC-B06…B08 | 3 | UT |

## 2. Технічна реалізація

### 2.1 Місце в системі, контракти й рішення за модулем

`td_energy_resources` (`depends`: `td_energy` → транзитивно `td_telemetry`, `mrp_account`, `analytic`, `web_hierarchy`, `maintenance`; `td_bms`, `td_yard`, `td_genset` — **не** залежності). `td_energy_resources_bms` (`depends`: `td_energy_resources`, `td_bms`; `auto_install`). Нові зовнішні залежності Python: `xlsxwriter` (входить в Odoo).

**Рішення за модулем (A-01).** GAP пропонував єдиний модуль `td_energy_resources` у хвилі W3. Варіанти:

| Варіант | Плюси | Мінуси |
|---|---|---|
| 1. Усе в `td_energy` | немає нового модуля | роздуває електричний модуль (142 тести, W1), усі клієнти отримують газ/повітря/воду; відкат неможливий без міграцій |
| 2. Один `td_energy_resources` із жорсткою залежністю від `td_bms` | простіше: немає моста | тягне BMS (світло, HVAC, пожежні зв'язки) у будь-яке встановлення енергетики; порушує D-18 |
| **3. Ядро `td_energy_resources` + міст `td_energy_resources_bms` (обрано)** | незалежне встановлення; тепло з BMS — за `auto_install` у будь-якому порядку; `hvac_unit_id` — справжній FK; ядро тестується без BMS (AC-64) | +1 малий модуль (S ≈ 600 рядків із тестами); менеджер може згорнути міст у ядро заміною `depends` |

Модуль ресурсів відокремлено від `td_energy` (A-02…A-03): електричні таблиці та їхні запити не змінюються; єдина правка структури — `td.energy.meter.node_id` стає необов'язковим (з перевіркою за ресурсом).

| Контракт | Хто → кому | Зміст |
|---|---|---|
| C-01 | `td_energy_resources` → W4 `td_energy_analytics` | `td.energy.usage` і його семантика (R-07), прапори ресурсу (`in_energy_cost`, `is_derived`, `co2_kg_per_unit`), `td.energy.price._td_price_at`, `td.energy.opportunity` API-02…API-06, `_td_totals` (API-10), `tools/shifts.py` (R-21), `res.interval._td_backfill` |
| C-02 | `td_energy_resources` → W2 `td_energy_control` | **контракт дій:** формат `actions[]` = W1 C-32 (`link`/`ticket`/`control`), `rule.control_intent` — непрозорий ключ наміру, `enabled` за `td.energy.advice._td_control_available()`, запасна дія `fallback_action`; сигнал `air/setpoint_bar` **зарезервовано за W2** (W3 лише читає). W3 **не** задає сценарії, команди та їхні коди; W2 прив'язує наміри (`vent_night_mode`, `heat_schedule_shift`, `air_pressure_setpoint`, `pv_self_consumption`) власними даними й обробником `td_energy.advice_handlers` |
| C-03 | `td_energy_resources` ← `td_energy` (W1) | `td.energy.dashboard.get_pult(parts=['kpis','profile','side'])` (вкладка «Електрика»), `td.energy.interval`/`alloc`/`node`/`tariff`, `tools/{dates,counter,backfill}`, шина (`kpi`), `td.energy.ticket.wizard`, `td_energy.advice_handlers`, `res.config.settings` блок `td_energy` |
| C-04 | міст ← `td_bms` | `td.bms.heat.balance` (сигнали подачі/зворота/тепла, `t_in_set`, `capacity_kw`, `air_wh_m3k`), `td.bms.hvac.unit` (`heat_signal_id`, `indoor_c`, `filter_dp_pa`, `airflow`) |
| C-05 | ядро ← `td_telemetry` | `td.signal`, `td.reading`, `td.source`; CT-10 не використовується (обчислюваних сигналів W3 не створює, A-06) |
| C-06 | ядро ↔ `iot_sim` | 2 пристрої, 10 сигналів, 3 сценарії (SPEC 5.4, 8.1) |

### 2.2 Архітектурна схема

```
 iot_sim:  GAS-MAIN(u74) · AIR-MAIN(u75) · BOILER(gas_m3h) · WATER(boiler) · PM5560 Q1/Q2(kvarh) ──Modbus/BACnet──▶ collector ──push──▶ td.signal / td.reading
                                                                                                                         │
   BMS: heat_kw, indoor_c, filter_dp_pa, outdoor_c ───────────────────────────────────────────────────────────────────▶ td.signal
                                                                                                                         ▼
   cron_td_energy_res_build (5 хв)  ──R-03/R-04──▶  td.energy.res.interval (+ metric='react')  ◀── backfill (R-22, is_backfill)
        ▲ meter(counter | flow_integrate | estimate) · point(source/branch/consumer)                      │
        │                                                                                                  ▼
   td.energy.interval (електрика, W1) ─────────────────────────────────────────────────────▶  td.energy.usage (SQL-view, R-07)
        │                                                                                      │            │
        ▼                                                                                      ▼            ▼
   td.energy.res.dashboard (API-01) ◀── get_pult (W1)         td.energy.opportunity.rule ──▶ td.energy.opportunity ──▶ W4 (C-01)
        │  гаки C: heat (міст)                                    9 детекторів (R-15…R-20, R-B4)    │ actions[] (C-32)
        ▼                                                                                            ▼
   OWL «Енергоресурси» ◀── bus kpi ── cron_live (W1)                                      W1 ticket wizard · (W2 control)
   xlsx /td/energy/resources/export ◀── usage
```

### 2.3 Нові й розширені об'єкти

| Об'єкт | Призначення | Пише | Читає |
|---|---|---|---|
| `td.energy.resource` (M-01) | довідник ресурсів, одиниці, прапори екрана | адмін/менеджер | усе |
| `td.energy.price` (M-02) | ціни газу й води | менеджер | інтервали, KPI |
| `td.energy.point` (M-03) | точки обліку, методи оцінки | менеджер, гак, міст | збирач інтервалів, список споживачів |
| `td.energy.meter` (розш., M-04) | лічильники будь-якого ресурсу | менеджер, гак | збирач |
| `td.energy.tariff` (розш., M-05) | параметри доплати за реактивну енергію | менеджер | R-06, детектор |
| `td.energy.res.interval` (M-06) | 15-хв ряд не-електрики й `react` | крон, backfill | usage, API, експорт |
| `td.energy.usage` (M-07) | SQL-зведення | — | W4, експорт, `_td_totals` |
| `td.energy.res.dashboard` (M-08) | API екрана | — | OWL |
| `td.energy.opportunity.rule` (M-09), `.opportunity` (M-10) | правила й резерви | крон, менеджер | екран, W4 |
| сигнали (+10), джерела (+2) | газ, повітря, вода котельні, квар·год | збирач | KPI, інтервали |
| `td.energy.point`/`res.dashboard`/`opportunity.rule` (розш. моста) | тепло з BMS, 3 детектори | гак моста | екран |

### 2.4 Інтеграції

| Система | Протокол | Напрям | Частота | При недоступності |
|---|---|---|---|---|
| Коректор газу `GAS-MAIN` (unit 74, регістри — ПРИПУЩЕННЯ) | P-07 Modbus TCP | читання | 60 с | сигнали stale → `data_state='stale'`, слоти `missing` |
| Витратомір повітря `AIR-MAIN` (unit 75) | P-07 | читання | 10 с | те саме |
| BAC-140-BOILER (`gas_m3h`, AI:7 `BOILER_GasFlow`), `MB-U84-IO5` (підживлення), PM5560 (`kvarh`) | BACnet / Modbus | читання | 30–60 с | те саме |
| `td_bms` (міст) | ORM | читання | за запитом/крон | немає BMS — гаки порожні, вкладка «Тепло» на ручних лічильниках |
| `td_yard` (`DOCK`) | `env.get` | читання сигналу | крон | немає — точка не створюється |
| `maintenance` | ORM | читання/створення через W1-майстер | — | — |
| `bus` | websocket | Odoo → клієнт | ≤ 1 за 5 с (W1) | клієнт на резервному опитуванні 30 с |

### 2.5 Потік даних від пристрою до екрана

1. Збирач опитує нові джерела й наявні (BOILER, WATER, PM-Q1/Q2) → `td.signal.last_value`, `td.reading` (зберігання за `store_period_s`).
2. `cron_td_energy_res_build` (5 хв): для кожного неелектричного лічильника будує слоти від `res_last_interval_start` (R-05): `counter` (різниця накопичувача), `flow_integrate` (трапеція, покриття, мультисигнал), `estimate` (навантаження вузла, розклад, залишок, втрати воріт); `react` — для вводів; пише `qty`, `rate_avg`, `kwh_eq`, `price`, `cost`, `quality`.
3. `bus.tick('kpi')` → відкрита сесія екрана за 2 с дебаунсу викликає `td.energy.res.dashboard.get_resources(code)`.
4. API-01: вкладки й підсумок (R-12), KPI (R-09), графік (R-10), список (R-11), нотатки з `td.energy.opportunity.get_list` (API-02); електрика — з `get_pult` W1.
5. Уночі `cron_td_energy_opportunity`: детектори читають `td.energy.interval`, `alloc`, `res.interval`, сирі показання (≤ 30 діб) → upsert резервів → `td.energy.opportunity`.
6. Дія резерву: `link` (xml-id), `ticket` (майстер W1 з тегом `[OPP-id]`), `control` (обробник W2, якщо встановлено). Закриття заявки → резерв `done` (`_td_link_requests`).
7. Excel: `GET /td/energy/resources/export` → `td.energy.usage` → xlsx.

### 2.6 Безпека

- Групи без нових: перегляд, вартість (₴), енергетик (резерви, ціни, пороги), адмін (backfill, правила). Ключі вартості **видаляються** з відповідей і xlsx без `group_td_energy_cost`.
- Стоп-крани: `td.energy.read_enabled` керує кронами; `write_enabled` **не змінюється** (W3 у пристрої не пише); `neutralize.sql` вимикає 4 крони й 2 джерела.
- HTTP: єдиний маршрут `/td/energy/resources/export` — `auth='user'`, перевірка групи, валідація дат і кодів, ліміт рядків; токени не потрібні, SQL-параметри лише біндяться.
- Заявки ТО — через W1-майстер за правами користувача; детектори читають дані від імені `base.user_root`.
- Заблоковано: запис у `td.energy.interval` (електрика), правка `td_genset`, `x_`-поля, `safe_eval` над даними БД.

### 2.7 Продуктивність і обсяги

| Об'єкт | Обсяг | Примітка |
|---|---|---|
| `td.energy.res.interval` | 24 лічильники × 96 = **2 304 рядки/добу** (16 ядро + 6 тепло + 2 `react`); 90 діб backfill ≈ **207 000**; 400 діб ≈ **921 600** (≈ 230 МБ з індексами) | індекси `(day, resource_id)`, `(point_id, ts_start)`, `UNIQUE(meter_id, metric, ts_start)`; ротація `keep_interval_days=400` |
| `td.energy.usage` (view) | електричні рядки (17 лічильників × 96 × 400 ≈ 650 000) + ресурсні ≈ 920 000 | фільтри за `day` проштовхуються (id без `row_number`) |
| Сигнали | +10; показань ≈ **8 600/добу**, сирі 30 діб ≈ 260 000 | `td.reading`, ротація телеметрії |
| `td.energy.opportunity` | ≤ 9 правил, ≤ 20 відкритих резервів; історія десятки на рік | |
| API-01 | відповідь ≤ 25 КБ; `get_resources(code)` ≤ **400 мс**, ≤ 30 SQL | AC-60 |
| `_cron_build` | ≤ **5 с** на 24 лічильники | AC-60 |
| `_td_backfill(days=90)` | ≤ **60 с**, ≤ 400 МБ; 400 діб ≤ 300 с | AC-61, R-22 |
| `_cron_detect` | ≤ 60 с (6+3 правила), ≤ 10 с на правило | ТП-05 |
| xlsx | доба ≈ 4 000 рядків, ≤ 3 с; 31 доба ≤ 20 с; межа 200 000 рядків | API-07 |
| Опитування UI | ≤ 12 RPC/хв на сесію (шина + резерв 30 с) | W1 ТП-09 |

### 2.8 Міграція й деінсталяція

`19.0.1.0.0` (SPEC 5.5): `post_init_hook`/`post-migration` — `resource_id=el` і `mode='counter'` у наявних лічильників, сигнали (+10) і джерела (+2), демо-точки (16) і лічильники (16), прив'язка `e_react_signal_id`, параметри (+12), 6 правил (+3 міст). Очікувано на `f3d_full2` із W1: сигнали `energy` 312 → 322, `td.source` 136 → 138, неелектричних лічильників 16, точок 16; електричні дані не змінюються. Повторне `-u` — без змін. `uninstall_hook`: видаляє неелектричні лічильники (повертає `node_id required`), електричні дані, сигнали й події зберігаються. Міст: `-u` створює теплові точки (5–6) і лічильники (5–6); видалення моста залишає їх (дані ядра), гаки перестають працювати. **Сервер із уже встановленим `td_iot_sim`:** нові сигнали емулятора W3 потрапляють у реєстр симулятора через `td_iot_sim.hooks.refresh_registry` (міграція `td_iot_sim` `19.0.2.0.1`+/оновлення модуля `-u td_iot_sim`), без перевстановлення.

## 3. Налаштування системи (тестовий сервер)

| Об'єкт | Параметр | Значення (як заповнювати) | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `td.energy_resources.boiler_eff` | 0,91 | ККД для ціни тепла; пізніше — розрахунок |
| | `td.energy_resources.boiler_eff_norm` | 90 | норма KPI «ККД котельні» |
| | `td.energy_resources.night_from_h` / `night_to_h` | 23,0 / 6,5 | ніч для витоків |
| | `td.energy_resources.air_spec_norm` | 6,0 | кВт/(м³/хв) |
| | `td.energy_resources.water_night_norm` / `boiler_makeup_norm` | 0,05 м³/год / 0,5 м³/добу | норми KPI |
| | `td.energy_resources.air_setpoint_bar` | 7,0 | до появи `air/setpoint_bar` (W2) |
| | `td.energy_resources.gap_max_s` / `min_coverage` | 900 / 0,3 | інтегрування |
| | `td.energy_resources.export_max_days` / `weeks_per_month` | 31 / 4,33 | |
| | `td.energy_resources_bms.recovery_norm_pct` / `filter_dp_limit_pa` | 70 / 250 | міст |
| | `td.energy.shift_calendar_id` (W1) | календар зі «Зміна 1 07:00–16:00» і «Зміна 2 16:00–23:00» | Q-23 W1; без календаря — типове значення макета |
| Дані | `td.energy.price` | газ 19,80; вода 60,00 (демо) | реальні — з договорів (Q-05) |
| | тариф `tg_phi_limit`, `react_rate` | за договором | без значень правило реактивної енергії вимкнене (Q-03) |
| Крон | `cron_td_energy_res_build` (5 хв), `_res_rotate` (03:10), `_opportunity` (03:30), `_opportunity_links` (1 год) | активні | SPEC розд. 6 |
| Джерела | `MB-U74-GAS-MAIN`, `MB-U75-AIR-MAIN` | `iot-sim:502`, unit 74/75 | на об'єкті — адреси приладів |
| Права | `group_td_energy_manager` | енергетики | керування резервами |
| Сервіси стенда (E-11) | емулятор + збирач | постійні | працює менеджер |
| Історія | електричний `_td_backfill(days=90)`, потім `td.energy.res.interval._td_backfill(days=90)` | один раз | порядок обов'язковий (R-22) |
| Меню | «Енергетика → Енергоресурси» (seq 10), «Резерви економії» (74) | `group_td_energy_user` | |

## 4. Інструкція

**4.1 Екран «Енергоресурси» (Перегляд/Енергетик).** 1) «Енергетика → Енергоресурси». 2) Оберіть вкладку ресурсу: 4 показники, графік доби (лінія «зараз», пунктир — ліміт), список споживачів. 3) Крапка біля значення «оцінка» означає оцінку, а не вимірювання. 4) Якщо вкладки немає — ресурс або його лічильники вимкнені (Налаштування → Енергоресурси → Ресурси).

**4.2 Резерви економії (Енергетик).** 1) На екрані або «Енергетика → Резерви економії» відкрийте резерв. 2) Виконайте дію (заявка ТО, сценарій — якщо встановлено модуль «Керування», посилання). 3) «У план» — поставити в план (враховується в «Аналітиці»); «Відхилити» — сховати на 30 діб; «Виконано» — закрити. 4) Пороги правила: «Налаштування → Енергоресурси → Правила резервів». Кнопка «Запустити зараз» у формі правила — серверна дія, що виконує правило й показує сповіщення зі статистикою.

**4.3 Ціни ресурсів (Енергетик із групою «Вартість»).** «Налаштування → Енергоресурси → Ціни»: додайте запис із датою початку; попередній період закрийте датою «по». Без ціни вартість газу й води показується як 0.

**4.4 Вивантаження в Excel (Перегляд).** Кнопка «Вивантажити в Excel» — інтервали за сьогодні; для іншого дня — адреса `/td/energy/resources/export?day=РРРР-ММ-ДД` (до 31 доби через `day_to`). Колонки ціни й вартості — лише з групою «Вартість».

**4.5 Демо-історія (адміністратор).** 1) Запустіть емулятор і збирач, зачекайте 5 хв; 2) виконайте електричний `_td_backfill(days=90)` (W1); 3) `echo 'env["td.energy.res.interval"]._td_backfill(days=90)' | odoo-bin shell -d <db> --no-http` (≤ 1 хв); 4) відкрийте екран: графіки без дір. Повтор безпечний, `purge=True` видаляє лише синтетику.

**4.6 Тепло й BMS (енергетик).** Встановіть `td_bms`: міст поставиться автоматично й створить теплові точки. Якщо встановлення BMS з'явилося пізніше — «Налаштування → Енергоресурси → Оновити прив'язку ресурсів» (серверна дія V-11 `action_td_energy_resources_rebind`).

## 5. Ризики й відкриті питання

| ID | Питання | Кому | Рекомендація | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | Паливо реальної котельні: газ (макет) чи брикети (демо `BOILER`) | замовник | газ; демо зберігає обидва канали (D-35) | газовий канал емулятора за E-07 |
| Q-02 | Які реальні прилади газу/повітря/води/тепла, протоколи, паспортні витрати повітря | замовник, електрики | оцінки зараз; прилади — заміною режиму лічильника без правки UI | `ПРИПУЩЕННЯ` в SPEC 5.3/5.4; «оцінка» в UI |
| Q-03 | Доплата за реактивну енергію в договорі (`tg φ`, ставка) | замовник | параметри в тарифі | правило й «ризик доплати» вимкнені без параметрів |
| Q-04 | Калориметри (прихід тепла) окремо від BMS | замовник | пізніше; точка `source` у режимі `counter` | інтеграл BMS-сигналів |
| Q-05 | Джерело цін газу й води | бухгалтерія | ручна таблиця цін із датами | 19,80 / 60,00 (демо) |
| Q-06 | Допустимий новий HTTP-маршрут експорту | менеджер | так | реалізовано (A-10) |
| Q-07 | Власник сигналу `air/setpoint_bar` | менеджер W2 | W2 | параметр уставки, читання сигналу при появі |
| Q-08 | Сигнал відкриття доквих воріт (`td.yard.gate` — шлагбауми) | замовник | датчик воріт відвантаження | `DOCK` і `dock_gates` активні лише за наявності сигналу |
| Q-B1 | Датчик температури витяжки AHU-1 | замовник | так | оцінка рекуперації за тепловим балансом |

**Ризики.** R1 — демо-`BOILER` брикетний (D-35): газовий канал синтетичний, при зміні моделі емулятора переглянути `gas_m3h`. R2 — число `td.energy.meter` росте, а електричні форми/фільтри показують усі ресурси (колонка «Ресурс» і групування додано; окреме меню «Лічильники ресурсів» фільтрує не-el). R3 — стик із W2: `signals.csv`/`devices.yaml` емулятора правлять обидві хвилі (порядок злиття W2 → W3, перенумерація `n`); `air/setpoint_bar` не створюється W3. R4 — зростання `td.energy.res.interval` (~0,92 млн рядків за 400 діб): ротація та індекси обов'язкові (ТП-03). R5 — оцінкові гілки (повітря, вода, DOCK) можуть не сходитися з головним лічильником — лише індикатор `unaccounted`. R6 — сирі показання зберігаються 30 діб: детектори з `lookback_days > 30` і `gate_loss` старше 30 діб не працюють. R7 — перейменування: код W3 пишеться в td-іменах, ключі параметрів `td.energy_resources.*`. R8 — код `td_energy`, що перебирає **всі** лічильники (`cron_td_energy_live` → `_td_update_state`, `td_energy_node_live.py:165`): в M-04 перевизначено `_td_update_state`, `role`, `model`, `company_id`; регресія — прогін 142 тестів `td_energy` і W1 на БД із неелектричними лічильниками (AC-05). R9 — `td.energy.meter.node_id` перестає бути `required` на рівні БД: відкат модуля можливий лише після видалення неелектричних лічильників (A-16).

## 6. План збирання агентами

### 6.0 Каркас (менеджер, до воркерів)

1. Створити модулі `td_energy_resources` і `td_energy_resources_bms`: `__manifest__.py` (SPEC 1, B.1), порожні файли із заголовком-коментарем за деревом SPEC 0 і B.0, зокрема `models/__init__.py`, `controllers/__init__.py`, `tools/detectors/__init__.py` (реєстр `DETECTORS` рядком на детектор) — **воркери ці `__init__.py` і маніфести не правлять**.
2. Вставити SPEC/ARCH у `docs/modules/td_energy_resources/`, `docs/modules/td_energy_resources_bms/`.
3. Зафіксувати контракти C-01…C-06 і JSON API-01, API-02 (SPEC розд. 7): зміни — лише через менеджера.
4. Перевірка середовища: `$T/run_tests.sh td_w3_scaffold /td_energy_resources` (порожні тести зелені).
`T=factory3d/tools/odoo`.

### 6.1 Воркери (паралельно ≤ 3 на стадію, без спільних файлів)

| Воркер | Файли (володіє) | Розділи SPEC (ID) | Здає | Тести (команда) |
|---|---|---|---|---|
| **W3-A «Дані»** (стадія 1) | `td_energy_resources/{hooks.py, migrations/**, models/{td_energy_resource,td_energy_price,td_energy_point,td_energy_meter,td_energy_tariff,td_energy_res_interval,td_energy_usage}.py, models/res_config_settings.py, tools/{integrate,estimate,build,shifts,backfill_resources}.py, data/{td_energy_resource.xml,td_energy_price_data.xml,resource_points.csv,resource_meters.csv,ir_config_parameter.xml,ir_cron.xml,neutralize.sql}, security/{td_energy_resources_security.xml,ir.model.access.csv}, tests/{common,test_w3_data,test_w3_integrate,test_w3_estimate,test_w3_cost,test_w3_usage,test_w3_backfill}.py}` | M-01…M-07, M-11, API-08, API-09, R-01…R-07, R-21, R-22 (крім тепла), розд. 4, 5.1…5.3, 5.5, 5.6, 6 (2 крони); AC-01…AC-20, AC-46…AC-48, AC-49…AC-54, AC-61 | моделі, інтервали, backfill, шифт-хелпер, міграція | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3a /td_energy_resources:TestW3Data` … за класами; регрес `…/td_energy` (142 + W1) |
| **W3-D «Емулятор і сигнали»** (стадія 1, паралельно з A) | `services/iot_sim/{catalog/devices.yaml, catalog/signals.csv, iot_sim/models/{gas,air,water,boiler,meter}.py, tests/unit/{test_gas,test_air,test_water_boiler,test_meter_kvarh}.py}`, `odoo_addons/td_iot_sim/data/{td_sim_signal.csv, td_sim_scenario_resources.xml}`, `odoo_addons/td_energy_resources/data/{resource_signals.csv,resource_sources.csv}`, `odoo_addons/td_energy_resources/tests/stand/test_w3_tk.py` | розд. 5.4, 8.1, R-23; AC-55, AC-56 (юніт-частина), ТК-01…ТК-06 (сценарії) | емулятор, рядки каталогу, CSV сигналів | `pytest services/iot_sim/tests/unit/test_gas.py test_air.py test_water_boiler.py test_meter_kvarh.py`; стенд — менеджер |
| **W3-E «API екрана й експорт»** (стадія 2) | `td_energy_resources/{models/td_energy_res_dashboard.py, controllers/export.py, tools/resource_data.py, tests/{test_w3_dashboard,test_w3_export,test_w3_security}.py}` | M-08, API-01, API-07, API-10, R-08…R-12, R-24, R-25; AC-21…AC-31, AC-44, AC-60, AC-63, AC-64, ТБ-01…ТБ-04 | JSON екрана, xlsx | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3e /td_energy_resources:TestW3Dashboard` (і `…TestW3Export`, `…TestW3Security`) |
| **W3-B «Резерви й міст»** (стадія 2) | `td_energy_resources/{models/{td_energy_opportunity_rule,td_energy_opportunity}.py, tools/detectors/{common,vent_offshift,idle_machines,air_leaks,air_pressure,react_section,pv_export}.py, data/{opportunity_rules.xml,ir_cron_opportunity.xml}, security/ir.model.access-opportunity.csv, tests/{test_w3_opportunity,test_w3_detectors}.py}`, `td_energy_resources_bms/**` | M-09, M-10, API-02…API-06, R-13…R-20, Частина II цілком (зокрема UI-B1: шаблон `heat_note.xml` за структурою `ResKpis`); AC-32…AC-43, AC-B01…AC-B09, AC-62 (сценарій) | рушій резервів, 6 детекторів, міст | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3b /td_energy_resources:TestW3Opportunity` (і `…TestW3Detectors`); міст: `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3bb /td_energy_resources_bms` |
| **W3-C «Екран (OWL)»** (стадія 2) | `td_energy_resources/{static/src/resources/**, static/tests/resources.test.js, views/{td_energy_resources_views,td_energy_opportunity_views,res_config_settings_views}.xml, views/menus.xml, tests/{test_w3_ui,test_w3_hoot}.py}` | V-01…V-13, UI-01…UI-08, D-31…D-48; AC-57, AC-58 | клієнтські дії, види, меню, hoot | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3c /td_energy_resources:TestW3Ui` і `…:TestW3Hoot`; візуально `$T/serve.sh td_w3c` (десктоп + 390 px) |

**Перетини, які воркери НЕ роблять.** `td_energy_resources/data/resource_signals.csv`, `resource_sources.csv` — лише D; функція `_ensure_resource_signals` у `hooks.py` — лише A (читає CSV за контрактом «ім'я файлу + колонки»); рядки емулятора й CSV Odoo синхронізуються за таблицею SPEC 5.4/8.1; `models/__init__.py`, `tools/detectors/__init__.py`, маніфести — менеджер; гаки `_td_heat_*`, `_td_bind_extra`, `_td_backfill_extra` ядра (A/E) успадковує міст (B) після злиття A і E (до цього — `patch` у тестах); `menu_td_energy_opportunity` і подання резервів — лише C (за xml-id моделі B); `td_energy_resources_bms/static/src/heat_note.xml` — лише B (C його не чіпає; контракт — ім'я блоку `ResKpis`, UI-03).

### 6.2 Порядок злиття й приймання

1. **Стадія 1 (паралельно):** W3-A і W3-D. Злиття A → `td_energy_resources` (регрес `/td_energy` 142 + W1 зелений; AC-05), D незалежно (pytest емулятора, CSV).
2. **Стадія 2 (паралельно ≤ 3):** W3-E, W3-B, W3-C на базі A (rebase). Блок `notes` в E і вкладки в C використовують API-02 з B за контрактом: у тестах E/C — `patch`; після злиття всіх — повний прогін.
3. **Злиття з W2** (якщо гілка `claude/td-energy-w2-docs`/код W2 раніше): спільні файли емулятора (`signals.csv`, `devices.yaml`, `td_sim_signal.csv`) — W2 першим, W3 перенумеровує `n` і дописує в кінець (фактично: сигнали W3 — n 1206…1215 після W2 n 1205).
4. **Інтеграція менеджера:** `F3D_TEST_INSTALL=td_energy,td_bms,td_genset,td_genset_factory3d,td_iot_sim,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3_full`; потім стенд: емулятор + збирач → електричний `_td_backfill(days=90)` → `res.interval._td_backfill(days=90)` → ТК-01…ТК-06, ТК-B1 (E-11: сервер — менеджер).
5. **Приймання Opus:** тести + `git diff --stat` (очікувано: A ≈ 1 900 рядків, B ≈ 1 500, C ≈ 1 300, D ≈ 800, E ≈ 1 100, крім CSV), перевірка D-31…D-48 на скріншотах п'яти вкладок.

### 6.3 Оцінка обсягів за воркерами

| Воркер | Python/XML | JS/XML (OWL) | Тести | Орієнтовно |
|---|---|---|---|---|
| W3-A | ≈ 1 100 | — | ≈ 800 | 36 люд.-год |
| W3-B | ≈ 900 (з мостом) | ≈ 30 | ≈ 700 | 36 люд.-год |
| W3-C | ≈ 450 (види) | ≈ 800 | ≈ 200 (hoot) | 32 люд.-год |
| W3-D | ≈ 350 (емулятор) | — | ≈ 450 (pytest + стенд) + CSV | 20 люд.-год |
| W3-E | ≈ 700 | — | ≈ 400 | 24 люд.-год |

## Журнал змін документа

| Дата | Версія | Зміна |
|---|---|---|
| 18.10.2026 | 0.1 | Перша редакція (`build/energy/W3_ARCH.md`, хвиля W3) |
| 19.10.2026 | 0.2 | Перенесено до `docs/modules/td_energy_resources/`, переклад українською; міст — [../td_energy_resources_bms/ARCHITECTURE.md](../td_energy_resources_bms/ARCHITECTURE.md); внесено рішення збірки (деталі — у «Журналі змін документа» SPEC): AI:7 для `BOILER_GasFlow`, n 1206…1215, сценарії S-21…S-23, `refresh_registry` для серверів із встановленим `td_iot_sim`, V-11, «Запустити зараз» як серверна дія |

