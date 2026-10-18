# W3 «Энергоресурсы» — техническое решение (модули `td_energy_resources` и `td_energy_resources_bms`)

Версия 0.1 · 18.10.2026 · автор: агент-аналитик (волна W3 блока «Енергетика») · статус: **черновик на согласование**.
Вход: `build/energy/GAP.md` (E-01…E-11, §4 «Мультиресурсність», §5.3 «Резерви економії», матрица RS-01…RS-15), макет `Resources.dc.html`. Каркас: `docs/ARCHITECTURE.md` §3, §5, §6.4; D-18 (необязательные связи). Контракты и код W1: `build/energy/W1_SPEC.md`, `W1_ARCH.md`, `odoo_addons/td_energy` на ветке `claude/factory3d-build` (`d14d13c`). Спецификация: `build/energy/W3_SPEC.md` (далее SPEC). Имена — td (E-04, E-09): маршруты `/f3d/*` и коды сигналов не меняются.
Язык: проза — русский (задание), строки интерфейса и `string=` — украинские.
Параллельная работа: W2 «Керування» (`claude/td-energy-w2-docs`, модуль `td_energy_control`) пишется независимо; здесь на неё ссылки **только через контракты** (C-02).
После приёмки файл раскладывается в `docs/modules/td_energy_resources/ARCHITECTURE.md` и `docs/modules/td_energy_resources_bms/ARCHITECTURE.md`.

## Общая информация

| Этап ToDo | Что сдаётся | Люд./год (оценка автора) |
|---|---|---|
| ТР | `W3_SPEC.md` + этот документ | 24 |
| Архитектура | согласование A-01…A-16, Q-01…Q-08, фиксация контрактов C-01…C-06 и API-01, API-02, API-10 | 6 |
| Разработка | A «данные» ≈ 36, B «резервы и мост» ≈ 36, C «экран» ≈ 32, D «эмулятор и сигналы» ≈ 20, E «API экрана и экспорт» ≈ 24 | 148 |
| Тестирование | 74 AC: UT ≈ 63, hoot ≈ 1, стенд ТК-01…ТК-06 и ТК-B1 ≈ 12, DEPLOY_TEST ≈ 4 | 36 |
| Инструкция | §4 этого документа + README/CHANGELOG | 6 |
| **Итого** | | **220** |

Факты среды (проверено 18.10.2026, только чтение): W1 в коде (`td_energy` `19.0.1.1.0`: `td.energy.dashboard`, `td.energy.advice`, `tools/backfill.py`, мобильный экран с реестром вкладок); сигналы газа/воздуха/квар·ч, теплового баланса котельни и подпитки воды в демо **нет** (есть `infra/water/*`, `infra/chp/gas_m3h|heat_kw`, `equipment/BOILER/heat_kw|supply_c|return_c`, `equipment/COMPRESSOR/state|temp_c|pressure_bar|load`, `ventilation/units/*/heat_kw`, `ventilation/totals/outdoor_c`); `BOILER` в эмуляторе — **брикетный** (`silo_fill`); сырые `td.reading` хранятся 30 суток (`td.telemetry.keep_days`), часовые агрегаты — 400; свободные Modbus-unit: 74, 75; последний `n` в `signals.csv` эмулятора — 1177.

## 1. Описание процесса и функциональные требования

### 1.1 Контекст

**Макет (утверждён заказчиком).** `Resources.dc.html`: шапка с итогом «Сьогодні разом» и кнопкой «Вивантажити в Excel»; 5 вкладок ресурсов (Електрика, Газ, Тепло, Стиснене повітря, Вода) с подписью «зараз · ₴»; 4 KPI на вкладку; график суток 15 мин с лимитом и маркером «зараз»; список потребителей; блок «Що помітила система» с кнопками действий. Отклонения — SPEC «D-31…D-48» (кратко: итог и подписи строятся из данных, подписи графиков генерируются, числа демо ≠ числа макета, рекуперация — оценка, DOCK и OFFICE — оценка/остаток, на вкладке все открытые резервы ресурса, экспорт — реальный xlsx, оси графиков вычисляются).

**Что уже есть (ветка `claude/factory3d-build`).**

| Складова | Где | Что даёт W3 |
|---|---|---|
| Электрические интервалы, тариф, зоны, цена | `td_energy/models/td_energy_interval.py:23-69`, `td_energy_tariff.py` | электрическая вкладка, стоимость воздуха, цены резервов |
| Живые KPI, профиль доби, прогноз | `td_energy/tools/dashboard.py`, `models/td_energy_dashboard.py` (`get_pult`) | вкладка «Електрика» без дублирования расчётов |
| Реестр действий рекомендаций, обработчики | `td_energy/models/td_energy_advice.py:56-110` (`actions[]`, `_td_control_available`), `static/src/common/advice.js` | действия резервов (C-02, FR-15) |
| Шина, throttle | `td_energy/tools/bus.py` (`KINDS = kpi, alarm, profile, state, advice`) | обновление экрана по `kpi` |
| Счётчик с накопительным рядом | `td_energy/tools/counter.py` (`CounterSeries`) | режим `counter` для не-el (R-03) |
| Генератор истории, детерминированный шум | `td_energy/tools/backfill.py` (`rnd`, `target_p`, `sun_factor`, `Plan`) | расширение на ресурсы (R-22) |
| Распределение энергии на МО, простой | `td_energy/models/td_energy_alloc.py` (`kind='idle'`), `mrp_*` | детектор `idle_machines` |
| Телеметрия | `td_telemetry` (`td.signal`, `td.reading`, `td.reading.hour`, `td.source`) | счётчики и сигналы ресурсов |
| Тепловой баланс, установки | `td_bms/models/td_bms_heat_balance.py:117-137`, `td_bms_hvac_unit.py:143-167` | мост: тепловые счётчики и KPI |
| Эмулятор воды, котельни, компрессора, счётчиков | `services/iot_sim/iot_sim/models/{water,boiler,compressor,meter}.py` | новые сигналы, backfill |
| Шаблон qweb-pdf, xlsx | `td_fire_safety/report/`, `td_genset/data/ir_exports.xml` | экспорт (A-10) |

**Покрытие матрицы GAP (RS):** RS-01, RS-02 (вкладки, итог) — FR-08; RS-03 (реактивная энергия) — FR-07, FR-21; RS-04, RS-05 — FR-08, FR-09; RS-06, RS-07 (газ) — FR-04, FR-09; RS-08, RS-09 (тепло) — FR-16, FR-B1…B3; RS-10, RS-11 (воздух) — FR-04, FR-09; RS-12, RS-13 (вода) — FR-04, FR-09; RS-14 (резервы) — FR-13…FR-15; RS-15 (Excel) — FR-12. Все 15 элементов закрыты.

### 1.2 Роли и сценарии

| Роль (группа) | Что делает в W3 | Меню |
|---|---|---|
| Перегляд (`td_energy.group_td_energy_user`) | смотрит экран ресурсов, резервы, скачивает xlsx (без ₴) | Енергетика → Енергоресурси, Резерви економії |
| Вартість (`…_cost`) | то же + ₴ | то же |
| **Енергетик** (`…_manager`) | ставит резерв «у план», отклоняет, закрывает; правит цены, точки, пороги правил; запускает правило | + «Налаштування → Енергоресурси» |
| Головний енергетик (`…_chief`) | как «Енергетик» (отдельных прав в W3 нет) | то же |
| Администратор (`td_factory3d.group_td_admin`) | backfill ресурсов, создание правил, uninstall | Налаштування |

Сценарии: **S1** обзор ресурсов за смену (экран «Енергоресурси», вкладки по очереди); **S2** разбор «Що помітила система»: открыть резерв → действие (заявка ТО / сценарий W2, если установлен); **S3** выгрузка 15-мин интервалов за день в Excel; **S4** ввод цены газа и воды (Налаштування → Ціни); **S5** настройка порогов правила; **S6** демо-стенд: администратор запускает `res.interval._td_backfill(days=90)` после электрического backfill.

### 1.3 Функциональные требования

| ID | Модуль | Требование |
|---|---|---|
| FR-01 | td_energy_resources | Справочник ресурсов (5 записей) с единицами, коэффициентами, лимитами и флагами экрана |
| FR-02 | td_energy_resources | Цены неэлектрических ресурсов по датам; электричество остаётся в тарифе |
| FR-03 | td_energy_resources | Точки учёта ресурса (источник/ветка/потребитель) с иерархией и методом оценки |
| FR-04 | td_energy_resources | Счётчики любого ресурса в режимах `counter`, `flow_integrate`, `estimate` на едином `td.energy.meter`; электрические расчёты не затронуты |
| FR-05 | td_energy_resources | 15-минутные интервалы ресурсов с качеством, ценой, стоимостью, kWh-экв.; крон, ротация, идемпотентность |
| FR-06 | td_energy_resources | SQL-сводка `td.energy.usage` по потокам (`import`, `export`, `generation`, `load`, `supply`, `branch`) для аналитики и экспорта |
| FR-07 | td_energy_resources | Реактивная энергия вводов (квар·ч), tg φ, оценка доплаты по тарифу |
| FR-08 | td_energy_resources | API экрана: вкладки, итог «разом», график суток 96 слотов, список потребителей |
| FR-09 | td_energy_resources | KPI по ресурсам (по 4 на вкладку) с признаком качества и тоном |
| FR-10 | td_energy_resources | Баланс «источник − ветки» как индикатор без тревог |
| FR-11 | td_energy_resources | Клиентская действие «Енергоресурси» (5 вкладок), обновление по шине, адаптив ≥ 360 px |
| FR-12 | td_energy_resources | «Вивантажити в Excel»: интервалы ресурсов за сутки/диапазон; стоимость — только с группой |
| FR-13 | td_energy_resources | Движок резервов: правила с порогами в настройках, жизненный цикл, «у плані», права |
| FR-14 | td_energy_resources(+bms) | Девять детекторов (6 ядра + 3 моста) с оценкой ₴/мес и числом-основанием |
| FR-15 | td_energy_resources | Действия резервов по контракту C-32 (link/ticket/control), связь с заявкой ТО |
| FR-16 | td_energy_resources(+bms) | Тепло: хуки ядра и тепловые точки/счётчики из BMS (мост) |
| FR-17 | td_energy_resources + iot_sim | Сигналы газа, воздуха, воды котельной, квар·ч (10 сигналов, 2 источника) |
| FR-18 | td_energy_resources | Расширение backfill на ресурсы (стык с W1 R-36) |
| FR-19 | td_energy_resources | Группы, ACL, cost-gating, record rules, `neutralize.sql`, `uninstall_hook` |
| FR-20 | td_energy_resources | Настройки и параметры `td.energy_resources.*` |
| FR-21 | td_energy_resources | Параметры тарифа для реактивной энергии (`tg_phi_limit`, `react_rate`) |
| FR-22 | td_energy_resources | Общий хелпер окон смен и ночи (контракт для W4) |
| FR-23 | iot_sim | Сценарии `air_leak`, `gas_overuse`, `water_leak` |
| FR-24 | td_energy_resources | Производительность и объёмы (разд. 2.7) |
| FR-B1 | td_energy_resources_bms | Тепловые точки и счётчики из `td.bms.heat.balance` и `td.bms.hvac.unit`, идемпотентно, независимо от порядка установки |
| FR-B2 | td_energy_resources_bms | KPI «Температура в цеху», «Рекуперація AHU-1», список «Куди йде тепло», примечание `{capacity}` |
| FR-B3 | td_energy_resources_bms | Детекторы `preheat_early`, `ahu_recuperation`, `dock_gates` |

### 1.4 Границы (не входит в W3)

Команды, сценарии, интерлоки, расписания и уставки (W2: `td_energy_control` — здесь только контракт C-02); аналитика, EnPI, бюджет, срезы, PDF-отчёты, мобильный «Обхід» (W4); события и тревоги по балансам и лимитам ресурсов (A-14); реальные приборы газа/воздуха/тепла (E-07: оценки и сигналы эмулятора, замена на объекте без правки UI); автоматическое изменение уставок и графиков (только через W2); Web Push; запись в устройства (`write_enabled` не меняется).

### 1.5 Критерии приёмки (сводка; полный текст — SPEC разд. 12)

Всего **74 критерия**: ядро AC-01…AC-64, мост AC-B01…AC-B10. Типы проверки: UT (юнит-тест `odoo.tests`, в т. ч. HttpCase и pytest эмулятора) / UT-JS (hoot) / TC (стенд на эмуляторе) / DEPLOY_TEST.

| FR | AC | Всего | Тип проверки |
|---|---|---|---|
| FR-01 | AC-01, 02 | 2 | UT |
| FR-02 | AC-03 | 1 | UT |
| FR-03 | AC-04 | 1 | UT |
| FR-04 | AC-05, 06, 11…15 | 7 | UT (AC-05 + DEPLOY_TEST) |
| FR-05 | AC-07…10, 16…18 | 7 | UT |
| FR-06 | AC-19 | 1 | UT |
| FR-07 | AC-20 | 1 | UT |
| FR-08 | AC-21, 26…28, 30, 31 | 6 | UT |
| FR-09 | AC-22…25 | 4 | UT (числа макета в фикстурах) |
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

## 2. Техническая реализация

### 2.1 Место в системе, контракты и решение по модулю

`td_energy_resources` (`depends`: `td_energy` → транзитивно `td_telemetry`, `mrp_account`, `analytic`, `web_hierarchy`, `maintenance`; `td_bms`, `td_yard`, `td_genset` — **не** зависимости). `td_energy_resources_bms` (`depends`: `td_energy_resources`, `td_bms`; `auto_install`). Новые внешние зависимости Python: `xlsxwriter` (входит в Odoo).

**Решение по модулю (A-01).** GAP предлагал единый модуль `td_energy_resources` в волне W3. Варианты:

| Вариант | Плюсы | Минусы |
|---|---|---|
| 1. Всё в `td_energy` | нет нового модуля | раздувает электрический модуль (142 теста, W1), все клиенты получают газ/воздух/воду; откат невозможен без миграций |
| 2. Один `td_energy_resources` с жёсткой зависимостью от `td_bms` | проще: нет моста | тянет BMS (свет, HVAC, пожарные связи) в любую установку энергетики; нарушает D-18 |
| **3. Ядро `td_energy_resources` + мост `td_energy_resources_bms` (выбрано)** | независимая установка; тепло из BMS — по `auto_install` в любом порядке; `hvac_unit_id` — настоящий FK; ядро тестируется без BMS (AC-64) | +1 малый модуль (S ≈ 600 строк с тестами); менеджер может свернуть мост в ядро заменой `depends` |

Модуль ресурсов отделён от `td_energy` (A-02…A-03): электрические таблицы и их запросы не меняются; единственная правка структуры — `td.energy.meter.node_id` становится необязательным (с проверкой по ресурсу).

| Контракт | Кто → кому | Содержание |
|---|---|---|
| C-01 | `td_energy_resources` → W4 `td_energy_analytics` | `td.energy.usage` и его семантика (R-07), флаги ресурса (`in_energy_cost`, `is_derived`, `co2_kg_per_unit`), `td.energy.price._td_price_at`, `td.energy.opportunity` API-02…API-06, `_td_totals` (API-10), `tools/shifts.py` (R-21), `res.interval._td_backfill` |
| C-02 | `td_energy_resources` → W2 `td_energy_control` | **контракт действий:** формат `actions[]` = W1 C-32 (`link`/`ticket`/`control`), `rule.control_intent` — непрозрачный ключ намерения, `enabled` по `td.energy.advice._td_control_available()`, запасное действие `fallback_action`; сигнал `air/setpoint_bar` **зарезервирован за W2** (W3 только читает). W3 **не** задаёт сценарии, команды и их коды; W2 привязывает намерения (`vent_night_mode`, `heat_schedule_shift`, `air_pressure_setpoint`, `pv_self_consumption`) собственными данными и обработчиком `td_energy.advice_handlers` |
| C-03 | `td_energy_resources` ← `td_energy` (W1) | `td.energy.dashboard.get_pult(parts=['kpis','profile','side'])` (вкладка «Електрика»), `td.energy.interval`/`alloc`/`node`/`tariff`, `tools/{dates,counter,backfill}`, шина (`kpi`), `td.energy.ticket.wizard`, `td_energy.advice_handlers`, `res.config.settings` блок `td_energy` |
| C-04 | мост ← `td_bms` | `td.bms.heat.balance` (сигналы подачи/зворота/тепла, `t_in_set`, `capacity_kw`, `air_wh_m3k`), `td.bms.hvac.unit` (`heat_signal_id`, `indoor_c`, `filter_dp_pa`, `airflow`) |
| C-05 | ядро ← `td_telemetry` | `td.signal`, `td.reading`, `td.source`; CT-10 не используется (вычисляемых сигналов W3 не создаёт, A-06) |
| C-06 | ядро ↔ `iot_sim` | 2 устройства, 10 сигналов, 3 сценария (SPEC 5.4, 8.1) |

### 2.2 Архитектурная схема

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
        │  хуки C: heat (мост)                                    9 детекторов (R-15…R-20, R-B4)    │ actions[] (C-32)
        ▼                                                                                            ▼
   OWL «Енергоресурси» ◀── bus kpi ── cron_live (W1)                                      W1 ticket wizard · (W2 control)
   xlsx /td/energy/resources/export ◀── usage
```

### 2.3 Новые и расширенные объекты

| Объект | Назначение | Пишет | Читает |
|---|---|---|---|
| `td.energy.resource` (M-01) | справочник ресурсов, единицы, флаги экрана | админ/менеджер | всё |
| `td.energy.price` (M-02) | цены газа и воды | менеджер | интервалы, KPI |
| `td.energy.point` (M-03) | точки учёта, методы оценки | менеджер, хук, мост | сборщик интервалов, список потребителей |
| `td.energy.meter` (расш., M-04) | счётчики любого ресурса | менеджер, хук | сборщик |
| `td.energy.tariff` (расш., M-05) | параметры доплаты за реактивную энергию | менеджер | R-06, детектор |
| `td.energy.res.interval` (M-06) | 15-мин ряд не-электрики и `react` | крон, backfill | usage, API, экспорт |
| `td.energy.usage` (M-07) | SQL-сводка | — | W4, экспорт, `_td_totals` |
| `td.energy.res.dashboard` (M-08) | API экрана | — | OWL |
| `td.energy.opportunity.rule` (M-09), `.opportunity` (M-10) | правила и резервы | крон, менеджер | экран, W4 |
| сигналы (+10), источники (+2) | газ, воздух, вода котельной, квар·ч | сборщик | KPI, интервалы |
| `td.energy.point`/`res.dashboard`/`opportunity.rule` (расш. моста) | тепло из BMS, 3 детектора | хук моста | экран |

### 2.4 Интеграции

| Система | Протокол | Направление | Частота | При недоступности |
|---|---|---|---|---|
| Корректор газа `GAS-MAIN` (unit 74, регистры — ПРИПУЩЕННЯ) | P-07 Modbus TCP | чтение | 60 с | сигналы stale → `data_state='stale'`, слоты `missing` |
| Расходомер воздуха `AIR-MAIN` (unit 75) | P-07 | чтение | 10 с | то же |
| BAC-140-BOILER (`gas_m3h`), `MB-U84-IO5` (подпитка), PM5560 (`kvarh`) | BACnet / Modbus | чтение | 30–60 с | то же |
| `td_bms` (мост) | ORM | чтение | при запросе/крон | нет BMS — хуки пусты, вкладка «Тепло» на ручных счётчиках |
| `td_yard` (`DOCK`) | `env.get` | чтение сигнала | крон | нет — точка не создаётся |
| `maintenance` | ORM | чтение/создание через W1-мастер | — | — |
| `bus` | websocket | Odoo → клиент | ≤ 1 за 5 с (W1) | клиент на резервном опросе 30 с |

### 2.5 Поток данных от устройства до экрана

1. Сборщик опрашивает новые источники и существующие (BOILER, WATER, PM-Q1/Q2) → `td.signal.last_value`, `td.reading` (хранение по `store_period_s`).
2. `cron_td_energy_res_build` (5 мин): для каждого неэлектрического счётчика строит слоты от `res_last_interval_start` (R-05): `counter` (разность накопителя), `flow_integrate` (трапеция, покрытие, мультисигнал), `estimate` (нагрузка узла, расписание, остаток, потери ворот); `react` — для вводов; пишет `qty`, `rate_avg`, `kwh_eq`, `price`, `cost`, `quality`.
3. `bus.tick('kpi')` → открытая сессия экрана за 2 с дебаунса вызывает `td.energy.res.dashboard.get_resources(code)`.
4. API-01: вкладки и итог (R-12), KPI (R-09), график (R-10), список (R-11), заметки из `td.energy.opportunity.get_list` (API-02); электричество — из `get_pult` W1.
5. Ночью `cron_td_energy_opportunity`: детекторы читают `td.energy.interval`, `alloc`, `res.interval`, сырые показания (≤ 30 сут) → upsert резервов → `td.energy.opportunity`.
6. Действие резерва: `link` (xml-id), `ticket` (мастер W1 с тегом `[OPP-id]`), `control` (обработчик W2, если установлен). Закрытие заявки → резерв `done` (`_td_link_requests`).
7. Excel: `GET /td/energy/resources/export` → `td.energy.usage` → xlsx.

### 2.6 Безопасность

- Группы без новых: просмотр, вартість (₴), енергетик (резервы, цены, пороги), админ (backfill, правила). Ключи стоимости **удаляются** из ответов и xlsx без `group_td_energy_cost`.
- Стоп-краны: `td.energy.read_enabled` управляет кронами; `write_enabled` **не меняется** (W3 в устройства не пишет); `neutralize.sql` отключает 4 крона и 2 источника.
- HTTP: единственный маршрут `/td/energy/resources/export` — `auth='user'`, проверка группы, валидация дат и кодов, лимит строк; токены не требуются, SQL-параметры только биндятся.
- Заявки ТО — через W1-мастер под правами пользователя; детекторы читают данные от имени `base.user_root`.
- Заблокировано: запись в `td.energy.interval` (электрика), правка `td_genset`, `x_`-поля, `safe_eval` над данными БД.

### 2.7 Продуктивность и обсяги

| Объект | Обсяг | Примечание |
|---|---|---|
| `td.energy.res.interval` | 24 счётчика × 96 = **2 304 строки/сутки** (16 ядро + 6 тепло + 2 `react`); 90 суток backfill ≈ **207 000**; 400 суток ≈ **921 600** (≈ 230 МБ с индексами) | индексы `(day, resource_id)`, `(point_id, ts_start)`, `UNIQUE(meter_id, metric, ts_start)`; ротация `keep_interval_days=400` |
| `td.energy.usage` (view) | электрические строки (17 счётчиков × 96 × 400 ≈ 650 000) + ресурсные ≈ 920 000 | фильтры по `day` проталкиваются (id без `row_number`) |
| Сигналы | +10; показаний ≈ **8 600/сутки**, сырые 30 суток ≈ 260 000 | `td.reading`, ротация телеметрии |
| `td.energy.opportunity` | ≤ 9 правил, ≤ 20 открытых резервов; история десятки в год | |
| API-01 | ответ ≤ 25 КБ; `get_resources(code)` ≤ **400 мс**, ≤ 30 SQL | AC-60 |
| `_cron_build` | ≤ **5 с** на 24 счётчика | AC-60 |
| `_td_backfill(days=90)` | ≤ **60 с**, ≤ 400 МБ; 400 суток ≤ 300 с | AC-61, R-22 |
| `_cron_detect` | ≤ 60 с (6+3 правила), ≤ 10 с на правило | ТП-05 |
| xlsx | сутки ≈ 4 000 строк, ≤ 3 с; 31 сутки ≤ 20 с; предел 200 000 строк | API-07 |
| Опрос UI | ≤ 12 RPC/мин на сессию (шина + резерв 30 с) | W1 ТП-09 |

### 2.8 Миграция и деинсталляция

`19.0.1.0.0` (SPEC 5.5): `post_init_hook`/`post-migration` — `resource_id=el` и `mode='counter'` у существующих счётчиков, сигналы (+10) и источники (+2), демо-точки (16) и счётчики (16), привязка `e_react_signal_id`, параметры (+12), 6 правил (+3 мост). Ожидаемо на `f3d_full2` с W1: сигналы `energy` 312 → 322, `td.source` 136 → 138, неэлектрических счётчиков 16, точек 16; электрические данные не меняются. Повторный `-u` — без изменений. `uninstall_hook`: удаляет неэлектрические счётчики (возвращает `node_id required`), электрические данные, сигналы и события сохраняются. Мост: `-u` создаёт тепловые точки (5–6) и счётчики (5–6); удаление моста оставляет их (данные ядра), хуки перестают работать.

## 3. Настройки системы (тестовый сервер)

| Объект | Параметр | Значение (как заполнять) | Комментарий |
|---|---|---|---|
| `ir.config_parameter` | `td.energy_resources.boiler_eff` | 0,91 | КПД для цены тепла; позже — расчёт |
| | `td.energy_resources.boiler_eff_norm` | 90 | норма KPI «ККД котельні» |
| | `td.energy_resources.night_from_h` / `night_to_h` | 23,0 / 6,5 | ночь для утечек |
| | `td.energy_resources.air_spec_norm` | 6,0 | кВт/(м³/мин) |
| | `td.energy_resources.water_night_norm` / `boiler_makeup_norm` | 0,05 м³/ч / 0,5 м³/сут | нормы KPI |
| | `td.energy_resources.air_setpoint_bar` | 7,0 | до появления `air/setpoint_bar` (W2) |
| | `td.energy_resources.gap_max_s` / `min_coverage` | 900 / 0,3 | интегрирование |
| | `td.energy_resources.export_max_days` / `weeks_per_month` | 31 / 4,33 | |
| | `td.energy_resources_bms.recovery_norm_pct` / `filter_dp_limit_pa` | 70 / 250 | мост |
| | `td.energy.shift_calendar_id` (W1) | календарь с «Зміна 1 07:00–16:00» и «Зміна 2 16:00–23:00» | Q-23 W1; без календаря — умолчание макета |
| Данные | `td.energy.price` | газ 19,80; вода 60,00 (демо) | реальные — из договоров (Q-05) |
| | тариф `tg_phi_limit`, `react_rate` | по договору | без значений правило реактивной энергии выключено (Q-03) |
| Крон | `cron_td_energy_res_build` (5 мин), `_res_rotate` (03:10), `_opportunity` (03:30), `_opportunity_links` (1 ч) | активны | SPEC разд. 6 |
| Источники | `MB-U74-GAS-MAIN`, `MB-U75-AIR-MAIN` | `iot-sim:502`, unit 74/75 | на объекте — адреса приборов |
| Права | `group_td_energy_manager` | энергетики | управление резервами |
| Сервисы стенда (E-11) | эмулятор + сборщик | постоянные | работает менеджер |
| История | электрический `_td_backfill(days=90)`, затем `td.energy.res.interval._td_backfill(days=90)` | один раз | порядок обязателен (R-22) |
| Меню | «Енергетика → Енергоресурси» (seq 10), «Резерви економії» (74) | `group_td_energy_user` | |

## 4. Инструкция

**4.1 Экран «Енергоресурси» (Перегляд/Енергетик).** 1) «Енергетика → Енергоресурси». 2) Выберите вкладку ресурса: 4 показателя, график суток (линия «зараз», пунктир — лимит), список потребителей. 3) Точка у значения «оцінка» означает оценку, а не измерение. 4) Если вкладки нет — ресурс или его счётчики выключены (Налаштування → Енергоресурси → Ресурси).

**4.2 Резервы экономии (Енергетик).** 1) На экране или «Енергетика → Резерви економії» откройте резерв. 2) Выполните действие (заявка ТО, сценарий — если установлен модуль «Керування», ссылка). 3) «У план» — поставить в план (учитывается в «Аналітиці»); «Відхилити» — скрыть на 30 сут; «Виконано» — закрыть. 4) Пороги правила: «Налаштування → Енергоресурси → Правила резервів».

**4.3 Цены ресурсов (Енергетик с группой «Вартість»).** «Налаштування → Енергоресурси → Ціни»: добавьте запись с датой начала; предыдущий период закройте датой «по». Без цены стоимость газа и воды показывается как 0.

**4.4 Выгрузка в Excel (Перегляд).** Кнопка «Вивантажити в Excel» — интервалы за сегодня; для другого дня — адрес `/td/energy/resources/export?day=ГГГГ-ММ-ДД` (до 31 суток через `day_to`). Колонки цены и стоимости — только с группой «Вартість».

**4.5 Демо-история (администратор).** 1) Запустите эмулятор и сборщик, подождите 5 мин; 2) выполните электрический `_td_backfill(days=90)` (W1); 3) `echo 'env["td.energy.res.interval"]._td_backfill(days=90)' | odoo-bin shell -d <db> --no-http` (≤ 1 мин); 4) откройте экран: графики без дыр. Повтор безопасен, `purge=True` удаляет только синтетику.

**4.6 Тепло и BMS (энергетик).** Установите `td_bms`: мост поставится автоматически и создаст тепловые точки. Если установка BMS появилась позже — «Налаштування → Енергоресурси → Оновити прив'язку ресурсів».

## 5. Риски и открытые вопросы

| ID | Вопрос | Кому | Рекомендация | Что делаем тем временем |
|---|---|---|---|---|
| Q-01 | Топливо реальной котельни: газ (макет) или брикеты (демо `BOILER`) | заказчик | газ; демо хранит оба канала (D-35) | газовый канал эмулятора по E-07 |
| Q-02 | Какие реальные приборы газа/воздуха/воды/тепла, протоколы, паспортные расходы воздуха | заказчик, электрики | оценки сейчас; приборы — заменой режима счётчика без правки UI | `ПРИПУЩЕННЯ` в SPEC 5.3/5.4; «оцінка» в UI |
| Q-03 | Доплата за реактивную энергию в договоре (`tg φ`, ставка) | заказчик | параметры в тарифе | правило и «ризик доплати» выключены без параметров |
| Q-04 | Калориметры (приход тепла) отдельно от BMS | заказчик | позже; точка `source` в режиме `counter` | интеграл BMS-сигналов |
| Q-05 | Источник цен газа и воды | бухгалтерия | ручная таблица цен с датами | 19,80 / 60,00 (демо) |
| Q-06 | Допустим новый HTTP-маршрут экспорта | менеджер | да | реализован (A-10) |
| Q-07 | Владелец сигнала `air/setpoint_bar` | менеджер W2 | W2 | параметр уставки, чтение сигнала при появлении |
| Q-08 | Сигнал открытия доковых ворот (`td.yard.gate` — шлагбаумы) | заказчик | датчик ворот отгрузки | `DOCK` и `dock_gates` активны только при сигнале |
| Q-B1 | Датчик температуры вытяжки AHU-1 | заказчик | да | оценка рекуперации по тепловому балансу |

**Риски.** R1 — демо-`BOILER` брикетный (D-35): газовый канал синтетический, при смене модели эмулятора пересмотреть `gas_m3h`. R2 — число `td.energy.meter` растёт, а электрические формы/фильтры показывают все ресурсы (колонка «Ресурс» и группировка добавлены; отдельное меню «Лічильники ресурсів» фильтрует не-el). R3 — стык с W2: `signals.csv`/`devices.yaml` эмулятора правят обе волны (порядок слияния W2 → W3, перенумерация `n`); `air/setpoint_bar` не создаётся W3. R4 — рост `td.energy.res.interval` (~0,92 млн строк на 400 суток): ротация и индексы обязательны (ТП-03). R5 — оценочные ветки (воздух, вода, DOCK) могут не сходиться с главным счётчиком — только индикатор `unaccounted`. R6 — сырые показания хранятся 30 суток: детекторы с `lookback_days > 30` и `gate_loss` старше 30 сут не работают. R7 — переименование: код W3 пишется в td-именах, ключи параметров `td.energy_resources.*`. R8 — код `td_energy`, перебирающий **все** счётчики (`cron_td_energy_live` → `_f3d_update_state`, `td_energy_node_live.py:165`): в M-04 переопределены `_f3d_update_state`, `role`, `model`, `company_id`; регрессия — прогон 142 тестов `td_energy` и W1 на БД с неэлектрическими счётчиками (AC-05). R9 — `td.energy.meter.node_id` перестаёт быть `required` на уровне БД: откат модуля возможен только после удаления неэлектрических счётчиков (A-16).

## 6. План сборки агентами

### 6.0 Каркас (менеджер, до воркеров)

1. Создать модули `td_energy_resources` и `td_energy_resources_bms`: `__manifest__.py` (SPEC 1, B.1), пустые файлы с заголовком-комментарием по дереву SPEC 0 и B.0, включая `models/__init__.py`, `controllers/__init__.py`, `tools/detectors/__init__.py` (реестр `DETECTORS` строкой на детектор) — **воркеры эти `__init__.py` и манифесты не правят**.
2. Вставить SPEC/ARCH в `docs/modules/td_energy_resources/`, `docs/modules/td_energy_resources_bms/`.
3. Зафиксировать контракты C-01…C-06 и JSON API-01, API-02 (SPEC разд. 7): изменения — только через менеджера.
4. Проверка среды: `$T/run_tests.sh td_w3_scaffold /td_energy_resources` (пустые тесты зелёные).
`T=factory3d/tools/odoo`.

### 6.1 Воркеры (параллельно ≤ 3 на стадию, без общих файлов)

| Воркер | Файлы (владеет) | Разделы SPEC (ID) | Сдаёт | Тесты (команда) |
|---|---|---|---|---|
| **W3-A «Данные»** (стадия 1) | `td_energy_resources/{hooks.py, migrations/**, models/{td_energy_resource,td_energy_price,td_energy_point,td_energy_meter,td_energy_tariff,td_energy_res_interval,td_energy_usage}.py, models/res_config_settings.py, tools/{integrate,estimate,build,shifts,backfill_resources}.py, data/{td_energy_resource.xml,td_energy_price_data.xml,resource_points.csv,resource_meters.csv,ir_config_parameter.xml,ir_cron.xml,neutralize.sql}, security/{td_energy_resources_security.xml,ir.model.access.csv}, tests/{common,test_w3_data,test_w3_integrate,test_w3_estimate,test_w3_cost,test_w3_usage,test_w3_backfill}.py}` | M-01…M-07, M-11, API-08, API-09, R-01…R-07, R-21, R-22 (кроме тепла), разд. 4, 5.1…5.3, 5.5, 5.6, 6 (2 крона); AC-01…AC-20, AC-46…AC-48, AC-49…AC-54, AC-61 | модели, интервалы, backfill, шифт-хелпер, миграция | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3a /td_energy_resources:TestW3Data` … по классам; регресс `…/td_energy` (142 + W1) |
| **W3-D «Эмулятор и сигналы»** (стадия 1, параллельно с A) | `services/iot_sim/{catalog/devices.yaml, catalog/signals.csv, iot_sim/models/{gas,air,water,boiler,meter}.py, tests/unit/{test_gas,test_air,test_water_boiler,test_meter_kvarh}.py}`, `odoo_addons/td_iot_sim/data/{td_sim_signal.csv, td_sim_scenario_resources.xml}`, `odoo_addons/td_energy_resources/data/{resource_signals.csv,resource_sources.csv}`, `odoo_addons/td_energy_resources/tests/stand/test_w3_tk.py` | разд. 5.4, 8.1, R-23; AC-55, AC-56 (юнит-часть), ТК-01…ТК-06 (сценарии) | эмулятор, строки каталога, CSV сигналов | `pytest services/iot_sim/tests/unit/test_gas.py test_air.py test_water_boiler.py test_meter_kvarh.py`; стенд — менеджер |
| **W3-E «API экрана и экспорт»** (стадия 2) | `td_energy_resources/{models/td_energy_res_dashboard.py, controllers/export.py, tools/resource_data.py, tests/{test_w3_dashboard,test_w3_export,test_w3_security}.py}` | M-08, API-01, API-07, API-10, R-08…R-12, R-24, R-25; AC-21…AC-31, AC-44, AC-60, AC-63, AC-64, ТБ-01…ТБ-04 | JSON экрана, xlsx | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3e /td_energy_resources:TestW3Dashboard` (и `…TestW3Export`, `…TestW3Security`) |
| **W3-B «Резервы и мост»** (стадия 2) | `td_energy_resources/{models/{td_energy_opportunity_rule,td_energy_opportunity}.py, tools/detectors/{common,vent_offshift,idle_machines,air_leaks,air_pressure,react_section,pv_export}.py, data/{opportunity_rules.xml,ir_cron_opportunity.xml}, security/ir.model.access-opportunity.csv, tests/{test_w3_opportunity,test_w3_detectors}.py}`, `td_energy_resources_bms/**` | M-09, M-10, API-02…API-06, R-13…R-20, Часть II целиком (включая UI-B1: шаблон `heat_note.xml` по структуре `ResKpis`); AC-32…AC-43, AC-B01…AC-B09, AC-62 (сценарий) | движок резервов, 6 детекторов, мост | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3b /td_energy_resources:TestW3Opportunity` (и `…TestW3Detectors`); мост: `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3bb /td_energy_resources_bms` |
| **W3-C «Экран (OWL)»** (стадия 2) | `td_energy_resources/{static/src/resources/**, static/tests/resources.test.js, views/{td_energy_resources_views,td_energy_opportunity_views,res_config_settings_views}.xml, views/menus.xml, tests/{test_w3_ui,test_w3_hoot}.py}` | V-01…V-13, UI-01…UI-08, D-31…D-48; AC-57, AC-58 | клиентские действия, виды, меню, hoot | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3c /td_energy_resources:TestW3Ui` и `…:TestW3Hoot`; визуально `$T/serve.sh td_w3c` (десктоп + 390 px) |

**Перетины, которые воркеры НЕ делают.** `td_energy_resources/data/resource_signals.csv`, `resource_sources.csv` — только D; функция `_ensure_resource_signals` в `hooks.py` — только A (читает CSV по контракту «имя файла + колонки»); строки эмулятора и CSV Odoo синхронизируются по таблице SPEC 5.4/8.1; `models/__init__.py`, `tools/detectors/__init__.py`, манифесты — менеджер; хуки `_td_heat_*`, `_td_bind_extra`, `_td_backfill_extra` ядра (A/E) наследует мост (B) после слияния A и E (до этого — `patch` в тестах); `menu_td_energy_opportunity` и представления резервов — только C (по xml-id модели B); `td_energy_resources_bms/static/src/heat_note.xml` — только B (C его не трогает; контракт — имя блока `ResKpis`, UI-03).

### 6.2 Порядок слияния и приёмки

1. **Стадия 1 (параллельно):** W3-A и W3-D. Слияние A → `td_energy_resources` (регресс `/td_energy` 142 + W1 зелёный; AC-05), D независимо (pytest эмулятора, CSV).
2. **Стадия 2 (параллельно ≤ 3):** W3-E, W3-B, W3-C на базе A (rebase). Блок `notes` в E и вкладки в C используют API-02 из B по контракту: в тестах E/C — `patch`; после слияния всех — полный прогон.
3. **Слияние с W2** (если ветка `claude/td-energy-w2-docs`/код W2 раньше): общие файлы эмулятора (`signals.csv`, `devices.yaml`, `td_sim_signal.csv`) — W2 первым, W3 перенумеровывает `n` и дописывает в конец.
4. **Интеграция менеджером:** `F3D_TEST_INSTALL=td_energy,td_bms,td_genset,td_genset_factory3d,td_iot_sim,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3_full`; затем стенд: эмулятор + сборщик → электрический `_td_backfill(days=90)` → `res.interval._td_backfill(days=90)` → ТК-01…ТК-06, ТК-B1 (E-11: сервер — менеджер).
5. **Приёмка Opus:** тесты + `git diff --stat` (ожидаемо: A ≈ 1 900 строк, B ≈ 1 500, C ≈ 1 300, D ≈ 800, E ≈ 1 100, кроме CSV), проверка D-31…D-48 на скриншотах пяти вкладок.

### 6.3 Оценка объёмов по воркерам

| Воркер | Python/XML | JS/XML (OWL) | Тесты | Орієнтовно |
|---|---|---|---|---|
| W3-A | ≈ 1 100 | — | ≈ 800 | 36 люд./год |
| W3-B | ≈ 900 (с мостом) | ≈ 30 | ≈ 700 | 36 люд./год |
| W3-C | ≈ 450 (виды) | ≈ 800 | ≈ 200 (hoot) | 32 люд./год |
| W3-D | ≈ 350 (эмулятор) | — | ≈ 450 (pytest + стенд) + CSV | 20 люд./год |
| W3-E | ≈ 700 | — | ≈ 400 | 24 люд./год |
