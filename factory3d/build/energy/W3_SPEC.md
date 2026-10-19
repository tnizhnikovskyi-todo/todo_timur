# W3 «Энергоресурсы»: спецификация (модули `td_energy_resources` и `td_energy_resources_bms`)

Версия 0.1 · 18.10.2026 · стандарт `docs/DOC_STANDARD.md` · техническое решение: `build/energy/W3_ARCH.md` (далее ARCH: FR-01…FR-24 и FR-B1…FR-B3, A-01…A-16, Q-01…Q-08).
Вход: `build/energy/GAP.md` (E-01…E-11, §4, §5.3, RS-01…RS-15), макет `Resources.dc.html`; контракты W1: `W1_SPEC.md` (M-26 `td.energy.advice.actions[]` = C-32, API-05, R-27, R-33, R-36, UI-10) и код `td_energy` на ветке `claude/factory3d-build` (`d14d13c`, W1 реализован).
Опирается на: `docs/ARCHITECTURE.md` §3 (граф), §5 (конвенции), §6.4 (телеметрия), D-18 (необязательные связи через `env.get` и мост `auto_install`); `td_energy` (M-01…M-28, R-04, R-15, `tools/counter.py`, `tools/backfill.py`); `td_telemetry` (`td.signal`, `td.reading`, `td.reading.hour`, CT-10); `td_bms` (`td.bms.heat.balance`, `td.bms.hvac.unit`); `td_iot_sim` и `services/iot_sim`.
Язык: проза — русский (задание), строки интерфейса, `string=` полей и тексты ошибок — украинские (как в W1 и в макете).
После приёмки файл раскладывается в `docs/modules/td_energy_resources/SPEC.md` и `docs/modules/td_energy_resources_bms/SPEC.md`.

## Условные обозначения, диапазоны ID, отклонения от макета

**Имена (E-09).** Всё в td-именах. Модули: `td_energy_resources` (ядро ресурсов), `td_energy_resources_bms` (мост к `td_bms`, `auto_install`). Модели `td.energy.*`; поля стандартных моделей — `td_*`; новые методы — `_td_*` (существующие `_td_*` вызываются как в коде). Параметры `ir.config_parameter` — `td.energy_resources.<param>` (конвенция §5: `td.<module>.<param>`; глобальные стоп-краны `td.energy.read_enabled` общие). Маршруты `/f3d/*` и коды сигналов не меняются; новый маршрут — `/td/energy/resources/export` (A-10).

**Диапазоны ID.** Нумерация модульная: новый модуль начинает с 01; между модулями номера пересекаются, поэтому вне таблиц ID пишется с модулем: `td_energy_resources M-03`. Мост — префикс `B`. Сквозные для блока «Энергетика»: D-xx (ниже), чтобы не пересекаться с W1 (D-01…D-18) и W2 (резерв D-19…D-30): W3 берёт **D-31…D-50**, W4 — D-51…D-80.

| Тип | `td_energy_resources` | `td_energy_resources_bms` |
|---|---|---|
| FR | FR-01…FR-24 | FR-B1…FR-B3 |
| M | M-01…M-11 | M-B1…M-B2 |
| V | V-01…V-13 | — |
| API | API-01…API-10 | — |
| R | R-01…R-25 | R-B1…R-B5 |
| AC | AC-01…AC-64 | AC-B01…AC-B10 |
| UI | UI-01…UI-08 | UI-B1 |
| ТК / ТБ / ТП | ТК-01…ТК-06 / ТБ-01…ТБ-04 / ТП-01…ТП-05 | ТК-B1 / — / — |
| A (решения автора) | A-01…A-16 | A-B1…A-B2 |
| Q | Q-01…Q-08 | Q-B1 |
| C (контракты) | C-01…C-06 | — |

Обозначения: UT — юнит-тест `odoo.tests` (`TransactionCase`/`HttpCase`), UT-JS — hoot-тест (`web.assets_unit_tests`), TC — стенд (эмулятор + сборщик + Odoo), MAN — ручная проверка. `req`=`required=True`, `idx`=`index=True`, `cost` в «Параметры» = `groups="td_energy.group_td_energy_cost"`. Все `Datetime` — UTC naive; «Киев» — `Europe/Kyiv` (`td_energy/tools/dates.py`). Слот = 15 минут по UTC-сетке; сутки, смена, «ночь» — по киевскому времени. Единицы величин: ресурс-ориентированные (кВт·ч, м³, норм. м³), «скорость» (rate) — кВт, м³/ч, м³/мин.

### Отклонения от макета (D-xx)

| ID | Где в макете | Что в реализации | Почему |
|---|---|---|---|
| D-31 | Шапка: «Сьогодні разом: 65 156 ₴ за електрику, газ і воду · тепло й стиснене повітря вже враховані в газі й електриці» | Формат: «Сьогодні разом: {сума} ₴ · {назви ресурсів з is_derived=False через «, »}. Похідні не додаються: {назви похідних}.» Суммируется стоимость ресурсов с `is_derived=False`; без группы стоимости — «Сьогодні: {n} ресурсів» без ₴ | Склонение названий программно невозможно; состав ресурсов конфигурируемый (A-12) |
| D-32 | Подписи вкладок «358 кВт · 52 786 ₴», «390 кВт · з BMS» | Подпись = текущая скорость + стоимость за сегодня; для ресурса с `show_tab_cost=False` (тепло) вместо ₴ — `source_note` («з BMS»); без группы стоимости — только скорость | Макет |
| D-33 | Подписи под графиками — готовая проза | Генерируются по данным (R-10): пик, начало экспорта, ночной расход, «норма/выше нормы»; шаблоны — в `td.energy.resource.foot_template` | В макете текст статичен, а цифры живые |
| D-34 | Демо-числа (вода 0,4 м³/ч, 4,2 м³; газ 46 м³/ч) | Экран показывает данные эмулятора/истории; воспроизводится арифметика макета (6 284 × 8,40 = 52 786 ₴; 612 × 19,80 = 12 118 ₴; 4,2 × 60 = 252 ₴; сумма 65 156 ₴) только в фикстурах AC; на стенде числа другие (вода эмулятора 2,1 м³/ч в смене, R-23) | У эмулятора и макета разные профили |
| D-35 | Газ: «ККД котельні 91,4 %», котельня на газе | Газовый канал котельни в демо — сигнал эмулятора `equipment/BOILER/gas_m3h` (E-07), хотя физическая модель `BOILER` в `iot_sim` — брикетная (`silo_fill`, `boiler.py`); бункер не меняется; η = тепло котлов / (газ × теплотворность) | E-07; Q-01 (топливо реального объекта) |
| D-36 | Тепло: «Рекуперація AHU-1 64 %» | Оценка по тепловому балансу установки (R-B3), бейдж «оцінка»; нет сигналов — «—». Датчика вытяжки в BMS нет | GAP §4.4 |
| D-37 | «Куди йде тепло»: «Втрати через ворота», «Офіс і побутові» | `DOCK` — оценка по сигналу открытия ворот (`gate_loss`), точка создаётся, только если есть сигнал; `OFFICE` = остаток (≥ 0). Ворота `td.yard.gate` — шлагбаумы, не доковые ворота (Q-08) | Нет датчиков доков |
| D-38 | Примечание над графиком: «2 × Atlas Copco GA 37 VSD+», «ліміт години — 80 м³/год» | Хранится в `td.energy.resource.chart_note` (шаблон с `{limit}`, `{contract}`, `{capacity}`) | Конфигурируемо |
| D-39 | Вода: список потребителей в м³ за день, остальные — в скорости | Сохранено: `resource.list_basis` = `qty_day` (вода) / `rate` (остальные) | Как в макете |
| D-40 | «Що помітила система» — 2 заметки на вкладке «Електрика» | На вкладке — все открытые резервы ресурса (в т. ч. `vent_offshift`, `idle_machines` на «Електрика»); кнопка = действие из контракта C-32; без `td_energy_control` действия `control` скрыты и показывается запасное действие «Відкрити» (карточка резерва) | Макет упрощён: в аналитике те же 8 правил |
| D-41 | «Вивантажити в Excel» (тост) | Реальный xlsx за выбранные сутки (по умолчанию сегодня), 15-мин интервалы всех ресурсов; стоимость — только с группой | RS-15 |
| D-42 | Фиксированные деления осей (900/90/600/15/1) | Деления считаются: `y_max = nice_ceil(1,1·max(limit, peak))`, три равных деления | Данные разного масштаба |
| D-43 | Вкладка «Тепло» без линии лимита | Без линии; мощность котлов (`capacity_kw` из `td.bms.heat.balance`) — в `chart_note` | GAP §4.4 п. 3 предлагал линию; макет её не содержит |
| D-44 | «Реактивна енергія… tg φ 0,40 · ризик доплати» | «ризик доплати» показывается только если в тарифе задан `tg_phi_limit > 0` и фактический tg φ выше; иначе заметка «tg φ {x}» без тона | Q-03 (договор не известен) |
| D-45 | «Найбільші споживачі зараз» на «Електрика» | Живая `p_now` потребителей (как в Пульте W1); на остальных вкладках — измеренные/оценённые скорости с точкой качества («оцінка») | Нет подсчётчиков |
| D-46 | В навигации макета «Енергоресурси» — вкладка раздела | Пункт меню `td_energy.menu_td_energy` → «Енергоресурси» (клиентское действие); настройки — в «Налаштування» | W1 D-18 |
| D-47 | Правило «Ворота відвантаження відкриті довго» есть на вкладке «Тепло», но не входит в 8 правил «Резерви економії» | Правило 9 (`dock_gates`) добавлено в данные моста; в W4 оно попадает в общий список | Расхождение внутри макета |
| D-48 | Всегда 5 вкладок | Вкладка скрыта, если ресурс неактивен (`active=False`) или у него нет ни одного активного счётчика | Площадка без воздуха/газа |

---

# ЧАСТЬ I. `td_energy_resources`

## 0. Дерево файлов

Владельцы: **A** — слой данных, **B** — резервы (движок, детекторы) и мост, **C** — фронтенд, **D** — эмулятор и контракт сигналов, **E** — API экрана и экспорт (ARCH §6). Файлы без буквы — менеджер (каркас). Менеджер создаёт все файлы пустыми с заголовком-комментарием, включая `models/__init__.py`, `tools/detectors/__init__.py`, `controllers/__init__.py` с полным списком импортов, — воркеры эти `__init__.py` не правят.

```
odoo_addons/td_energy_resources/
├── __manifest__.py                         (менеджер) раздел 1
├── __init__.py                             (менеджер) from . import models, controllers; from .hooks import post_init_hook, uninstall_hook
├── hooks.py                                A  post_init_hook (разд. 5.5: `_set_el_on_meters`, `_ensure_resource_signals`, `_seed_points_meters`, `_bind_react_signals`), uninstall_hook (5.6)
├── migrations/19.0.1.0.0/post-migration.py  A  заполнение `resource_id=el` у существующих счётчиков (идемпотентно)
├── models/
│   ├── __init__.py                         (менеджер)
│   ├── td_energy_resource.py               A  M-01
│   ├── td_energy_price.py                  A  M-02
│   ├── td_energy_point.py                  A  M-03
│   ├── td_energy_meter.py                  A  M-04 (_inherit)
│   ├── td_energy_tariff.py                 A  M-05 (_inherit)
│   ├── td_energy_res_interval.py           A  M-06 (+ крон, ротация, _td_backfill)
│   ├── td_energy_usage.py                  A  M-07 (SQL-view)
│   ├── td_energy_res_dashboard.py          E  M-08 (AbstractModel, API-01 + хуки)
│   ├── res_config_settings.py              A  M-11
│   ├── td_energy_opportunity_rule.py       B  M-09
│   └── td_energy_opportunity.py            B  M-10
├── controllers/
│   ├── __init__.py                         (менеджер)
│   └── export.py                           E  API-07 (xlsx)
├── tools/
│   ├── integrate.py                        A  R-03 (трапеция, покрытие, мультисигнал)
│   ├── estimate.py                         A  R-04 (load_share, schedule, residual, gate_loss)
│   ├── build.py                            A  R-05 (порядок построения слота)
│   ├── resource_data.py                    E  R-08…R-12, R-25 (сборка JSON экрана)
│   ├── shifts.py                           A  R-21 (окна смен; контракт C-01 для W4)
│   ├── backfill_resources.py               A  R-22
│   └── detectors/
│       ├── __init__.py                     (менеджер)  реестр `DETECTORS = {…}` строкой на детектор
│       ├── common.py                       B  R-14 (окна, цены, 4,33, схема параметров)
│       ├── vent_offshift.py, idle_machines.py, air_leaks.py,
│       │   air_pressure.py, react_section.py, pv_export.py          B  R-15…R-20
├── data/
│   ├── td_energy_resource.xml              A  5 записей (noupdate=1)
│   ├── td_energy_price_data.xml            A  демо-цены (газ 19,80; вода 60,00), noupdate=1
│   ├── resource_points.csv, resource_meters.csv   A  демо-точки и счётчики газа/воздуха/воды (разд. 5.3)
│   ├── ir_config_parameter.xml             A  12 параметров (разд. 5.1)
│   ├── ir_cron.xml                         A  2 крона (разд. 6)
│   ├── neutralize.sql                      A  отключение кронов
│   ├── resource_signals.csv, resource_sources.csv   D  +10 сигналов, +2 источника (разд. 5.4)
│   ├── opportunity_rules.xml               B  6 правил ядра (noupdate=1)
│   └── ir_cron_opportunity.xml             B  крон резервов
├── security/
│   ├── td_energy_resources_security.xml    A  record rules (разд. 4.3)
│   ├── ir.model.access.csv                 A  M-01…M-08, M-11
│   └── ir.model.access-opportunity.csv     B  M-09, M-10 (суффикс после «-» не влияет на модель, `odoo/tools/convert.py:722`)
├── static/src/resources/                   C  UI-01…UI-08: resources.js/.xml/.scss, tabs, kpis, chart, list, notes
├── static/tests/resources.test.js          C  hoot
├── views/
│   ├── td_energy_resources_views.xml       C  V-01…V-07, V-10, V-11 (действия, списки, формы)
│   ├── td_energy_opportunity_views.xml     C  V-08, V-09
│   ├── res_config_settings_views.xml       C  V-12
│   └── menus.xml                           C  V-13
└── tests/
    ├── common.py                           A  TestW3Common (фикстуры)
    ├── test_w3_data.py, test_w3_integrate.py, test_w3_estimate.py, test_w3_cost.py, test_w3_usage.py,
    │   test_w3_backfill.py                                                            A
    ├── test_w3_dashboard.py, test_w3_export.py, test_w3_security.py                      E
    ├── test_w3_opportunity.py, test_w3_detectors.py      B
    ├── test_w3_ui.py, test_w3_hoot.py                    C  (HttpCase, hoot — по образцу `td_energy/tests/test_w1_hoot.py`)
    └── stand/test_w3_tk.py                               D  ТК-01…ТК-06 (pytest против стенда)

odoo_addons/td_energy_resources_bms/           B  (мост, Часть II)
services/iot_sim/                              D  (разд. 8)
odoo_addons/td_iot_sim/data/                   D  td_sim_signal.csv (+10 строк), td_sim_scenario_resources.xml (новый)
```

Фиксы по ownership: строки сигналов для эмулятора и для Odoo синхронизируются **только** по таблице разд. 5.4/8.1; `td_energy/data/energy_signals.csv`, `energy_sources.csv` не правятся (новые сигналы — в собственных CSV модуля); `td_telemetry/data/signal_catalog.csv` не правится.

## 1. Манифест

- `name`: «Енергоресурси»; `version`: `19.0.1.0.0`; `author`: `ToDo`; `license`: `LGPL-3`; `category`: `Manufacturing/Maintenance`; `installable`: True; `application`: False.
- `depends`: `["td_energy"]` (транзитивно `td_telemetry`, `mrp_account`, `analytic`, `maintenance`, `mail`, `bus`). Жёстких зависимостей от `td_bms`, `td_yard`, `td_genset` нет (D-18): связи — через `env.get(...)` и мост.
- `external_dependencies`: `{"python": ["xlsxwriter"]}` (входит в зависимости Odoo; используется в API-07).
- `data` (порядок): `security/td_energy_resources_security.xml`, `security/ir.model.access.csv`, `security/ir.model.access-opportunity.csv`, `data/ir_config_parameter.xml`, `data/td_energy_resource.xml`, `data/td_energy_price_data.xml`, `data/opportunity_rules.xml`, `data/ir_cron.xml`, `data/ir_cron_opportunity.xml`, `views/td_energy_resources_views.xml`, `views/td_energy_opportunity_views.xml`, `views/res_config_settings_views.xml`, `views/menus.xml` (последним).
- `assets`: `web.assets_backend`: `td_energy_resources/static/src/resources/**`; `web.assets_unit_tests`: `td_energy_resources/static/tests/**`.
- `post_init_hook`: `hooks.post_init_hook` (R-22 прим.: `_ensure_resource_signals`, `_seed_points_meters`, `_bind_react_signals`, `_set_el_on_meters`); `uninstall_hook`: `hooks.uninstall_hook` (разд. 5.6).
- CSV сигналов/источников **не** входят в `data`: их загружает `hooks._ensure_resource_signals(env)` (идемпотентно) — тот же приём, что `_ensure_w1_signals` в `td_energy`.

## 2. Модели

Общее: все модели — `company_id` (кроме справочника ресурсов и SQL-view); `_log_access=False` только у `td.energy.res.interval`; `mail.thread` — у `td.energy.resource`, `.point`, `.opportunity`.

### M-01 `td.energy.resource` — ресурс (FR-01)

`_name = "td.energy.resource"`, `_description = "Енергетика: ресурс"`, `_inherit = ["mail.thread"]`, `_order = "sequence, id"`, `_rec_name = "name"`. Записи справочника — XML с xml-id `resource_el|gas|heat|air|water` (`noupdate="1"`); удаление записей `el` запрещено (`unlink` → `UserError("Ресурс «Електрика» видаляти не можна.")`).

| Поле | Тип | Параметры |
|---|---|---|
| `code` | Char | size=8, req, idx, «Код»; `UNIQUE(code)`; значения `el`, `gas`, `heat`, `air`, `water` (произвольные коды разрешены) |
| `name` | Char | size=64, req, «Назва» |
| `sequence` | Integer | default 10 |
| `active` | Boolean | default True, tracking; архивирование скрывает вкладку (D-48) |
| `uom_label` | Char | size=16, req, «Одиниця кількості» («кВт·год», «м³», «норм. м³») |
| `rate_label` | Char | size=16, req, «Одиниця швидкості» («кВт», «м³/год», «м³/хв») |
| `rate_hour_factor` | Float | digits (8,3), req, default 1.0, «Швидкість → кількість за годину»: `qty_per_hour = rate × factor`; constraint `> 0`; el 1, gas 1, heat 1, air **60**, water 1 |
| `kwh_per_unit` | Float | digits (8,3), default 0, «кВт·год на одиницю» (газ 10,5; el/heat 1 неприменимо — 0 = «нет эквивалента»; kWh-eq для el и heat = qty, R-01) |
| `co2_kg_per_unit` | Float | digits (8,4), default 0, «кг CO₂ на одиницю» (el 0,37; gas 1,96; heat/air/water 0); Q-02 уточнение |
| `is_derived` | Boolean | default False, «Похідний (не додається до загальної вартості)» — heat, air |
| `in_energy_cost` | Boolean | default False, «Входить у вартість енергії (W4)» — el, gas |
| `show_tab_cost` | Boolean | default True, «Вартість у підписі вкладки» — heat False |
| `source_note` | Char | size=32, «Підпис замість вартості», heat «з BMS» |
| `price_source` | Selection | `tariff` (el), `price` (gas, water), `derived_gas` (heat), `derived_el` (air), `none`; req |
| `limit_kind` | Selection | `none`, `fixed`, `tariff_contract`; default `none`; el — `tariff_contract`, gas — `fixed` |
| `rate_limit` | Float | digits (10,2), «Ліміт швидкості» (gas 80; el — из тарифа `contract_kw`) |
| `daily_limit` | Float | digits (12,2), «Ліміт доби за договором» (gas 1 200 м³; 0 = нет) |
| `list_basis` | Selection | `rate` / `qty_day`; default `rate`; water `qty_day` (D-39) |
| `color` | Char | size=7, «Колір», el `#714B67`, gas `#b45309`, heat `#c2410c`, air `#0369a1`, water `#0f766e` (токены UI-11 W1 расширены) |
| `chart_title` | Char | size=64, «Заголовок графіка»: «Імпорт з мережі, кВт», «Витрата газу, м³/год», «Теплова потужність, кВт», «Витрата стисненого повітря, м³/хв», «Витрата води, м³/год» |
| `chart_note` | Char | size=128, шаблон: «ліміт — договірна {contract} кВт», «ліміт години — {limit} м³/год», «теплобаланс цеху з BMS · котли {capacity} кВт», «2 × Atlas Copco GA 37 VSD+», «ввід і підживлення котельні» |
| `list_title` | Char | size=64: «Найбільші споживачі зараз», «Споживачі газу», «Куди йде тепло», «Споживачі повітря зараз», «Споживачі води» |
| `foot_template` | Text | шаблон подписи под графиком (R-10), плейсхолдеры `{peak_kw}`, `{peak_time}`, `{night}`, `{day}`, `{norm}`, `{export_time}` |
| `meter_ids` | One2many | `td.energy.meter.resource_id`, readonly |
| `meter_count`, `point_count` | Integer | compute |

Constraints: `_check_codes` (`^[a-z0-9_]{1,8}$`), `_check_el` (ровно один активный ресурс с `code='el'`: «Ресурс «Електрика» має бути єдиним.»), `limit_kind='fixed'` → `rate_limit > 0`.
Методы: `get_by_code(code)` (`api.model`, ormcache, `False` если нет); `_td_active_with_meters()` → записи, у которых есть активный счётчик (R-12); `_td_rate_to_qty(rate, hours)`: `rate × rate_hour_factor × hours`.

### M-02 `td.energy.price` — цена неэлектрического ресурса (FR-02)

`_name = "td.energy.price"`, `_description = "Енергетика: ціна ресурсу"`, `_inherit = ["mail.thread"]`, `_order = "resource_id, date_from desc"`.

| Поле | Тип | Параметры |
|---|---|---|
| `resource_id` | Many2one `td.energy.resource` | req, ondelete=restrict, idx, tracking; domain `price_source = 'price'` |
| `date_from` | Date | req, tracking |
| `date_to` | Date | tracking; пусто — бессрочно |
| `price` | Float | digits (12,4), req, `cost`, tracking, «Ціна за одиницю (₴)» |
| `currency_id` | Many2one `res.currency` | req, default валюта компании |
| `company_id` | Many2one `res.company` | req, default `env.company` |
| `note` | Char | size=128 |
| `active` | Boolean | default True |

Constraints: `_check_resource` (ресурс не `el` — «Ціни електрики задаються в тарифі.»), `_check_period` (`date_to ≥ date_from`; периоды активных цен одного ресурса и компании не пересекаются — «Період ціни перетинається з іншою.»), `price ≥ 0`.
Метод `_td_price_at(resource, dt_local=None)` (`api.model`, контракт C-01): цена на локальную дату; вне периодов → `0.0` (стоимость 0, а не ошибка); для `price_source='derived_gas'` → R-02 п. 3; для `el`/`derived_el`/`none` → `0.0` (стоимость берётся из тарифа или из электроинтервалов, R-02).

### M-03 `td.energy.point` — точка учёта (FR-03)

`_name = "td.energy.point"`, `_description = "Енергетика: точка обліку ресурсу"`, `_inherit = ["mail.thread"]`, `_order = "resource_id, sequence, code"`, `_parent_name = "parent_id"`.

| Поле | Тип | Параметры |
|---|---|---|
| `resource_id` | Many2one `td.energy.resource` | req, idx, ondelete=restrict |
| `code` | Char | size=32, req, idx; `UNIQUE(resource_id, company_id, code)` |
| `name` | Char | size=128, req |
| `kind` | Selection | `source`/«Ввід (головний облік)», `branch`/«Гілка», `consumer`/«Споживач»; req, default `consumer` |
| `parent_id` | Many2one `td.energy.point` | ondelete=restrict; тот же ресурс (`_check_parent`: «Батько має бути з того самого ресурсу.»; без циклов — `_check_recursion`) |
| `sequence` | Integer | default 10 |
| `active` | Boolean | default True |
| `node_id` | Many2one `td.energy.node` | «Електричний вузол споживача» (для `load_share` и сопоставления с оборудованием); ondelete=set null |
| `cost_node_id` | Many2one `td.energy.node` | «Вузол, чия електрика формує вартість» (воздух: `COMPRESSOR`) |
| `equipment_id` | Many2one `maintenance.equipment` | ondelete=set null; default из `node_id.equipment_id` (onchange) |
| `workcenter_id` | Many2one `mrp.workcenter` | related `node_id.workcenter_id`, store=False |
| `rate_nominal` | Float | digits (10,3), «Паспортна швидкість при роботі» (воздух: м³/хв; газ: м³/год) — **ПРИПУЩЕННЯ** до появы паспортов (Q-02) |
| `min_pressure_bar` | Float | digits (5,2), «Мінімальний тиск споживача, бар» (воздух; R-18) |
| `hvac_ref` | Char | size=32, «Код установки BMS» (заполняет мост, M-B1) |
| `state_signal_id` | Many2one `td.signal` | сигнал состояния/открытия (для `gate_loss`) |
| `meter_ids` | One2many | `td.energy.meter.point_id` |
| `estimate_method` | Selection | `none`, `load_share`, `schedule`, `residual`, `gate_loss`; default `none` |
| `estimate_params` | Json | default `{}`; схема по методу (R-04): ключи и типы валидирует `_check_estimate` |
| `company_id` | Many2one `res.company` | req, default `env.company` |

`estimate_method` и `estimate_params` у точки — для **оценочного** счётчика (`mode='estimate'`) берутся отсюда; поле дублируется на точке, а не на счётчике, чтобы метод описывал сущность, а не канал (A-05). `_check_estimate`: `load_share` → `node_id` обязателен и `rate_nominal > 0`; `schedule` → `params.from_h/to_h/rate`; `residual` → `params.from` (непустой список кодов точек того же ресурса, чьи скорости суммируются как «приход»); `gate_loss` → `state_signal_id` и `params.loss_kw_per_k`.
Метод-хук `_td_bind_extra()` (`api.model`; в ядре возвращает `{}`) вызывается `post_init_hook` и серверным действием V-11 после `_seed_points_meters`; мост `td_energy_resources_bms` перекрывает его (R-B1).

### M-04 `td.energy.meter` — расширение (`_inherit = "td.energy.meter"`; FR-04, FR-07)

Существующая модель `td_energy` (`td.energy.meter`; поля повірки добавила W1 M-23) получает:

| Поле | Тип | Параметры |
|---|---|---|
| `resource_id` | Many2one `td.energy.resource` | req, idx, ondelete=restrict, **default = `resource_el`** (xml-id), «Ресурс»; у существующих счётчиков заполняется миграцией (разд. 5.5) |
| `point_id` | Many2one `td.energy.point` | idx, ondelete=restrict; обязательно при `resource_id.code != 'el'` |
| `mode` | Selection | `counter`/«Лічильник», `flow_integrate`/«Інтеграл витрати», `estimate`/«Оцінка»; default `counter`; req |
| `qty_signal_id` | Many2one `td.signal` | сигнал счётчика объёма/энергии (режим `counter` для не-el) |
| `flow_signal_ids` | Many2many `td.signal` | rel `td_energy_meter_flow_signal_rel`; сигналы скорости; режим `flow_integrate`: суммируются (R-03 п. 5) |
| `max_rate` | Float | digits (12,3), default 0, «Макс. швидкість (од. ресурсу/год) для скидань лічильника»; 0 = по умолчанию `rate_nominal` точки или 1000 |
| `e_react_signal_id` | Many2one `td.signal` | «Реактивна енергія, квар·год» — только `role='incomer'` электрических счётчиков (FR-07) |
| `res_last_interval_start` | Datetime | readonly, «Останній інтервал ресурсу» (не путать с `last_interval_start` электричества) |

Изменение существующего поля: `node_id = fields.Many2one(required=False)` (в базе `required=True`); новая проверка `_check_resource_binding` (`api.constrains('resource_id','node_id','point_id','mode', …)`):
- `resource.code == 'el'` → `node_id` обязателен («Для електричного лічильника потрібен вузол.»), `point_id` пусто, `mode='counter'`;
- иначе → `point_id` обязателен («Для лічильника ресурсу потрібна точка обліку.»); `node_id` пусто допускается; `e_import_signal_id`/`e_export_signal_id` должны быть пусты («Електричні сигнали лише для ресурсу «Електрика».»);
- `mode='counter'` (не-el) → `qty_signal_id` обязателен; `flow_integrate` → `flow_signal_ids` непусто; `estimate` → у точки `estimate_method != 'none'`;
- `e_react_signal_id` допустим только при `role='incomer'` и ресурсе `el`.

Дополнительные изменения существующих полей и методов (все нужны, чтобы код `td_energy` не ломался на счётчиках без узла и электрических сигналов):
- `role`: `selection_add [("resource", "Ресурс")]`; для не-el обязательно `role = 'resource'`, для `el` — любая роль, кроме `resource` (`_check_resource_binding`); существующие выборки по `role` (`incomer`, `feeder`, `consumer`, `generation`, `storage`) `resource`-счётчики не затрагивают;
- `model`: для не-el `model = 'other'` (в `_check_resource_binding`; сидом задаётся явно); значения `pm5560`/`sun2000`/… остаются только электрическим;
- `company_id`: переопределяется как `compute` store `node_id.company_id or point_id.company_id or env.company` (в базе — `related='node_id.company_id'`, для не-el был бы пуст);
- `_td_update_state()`: `cron_td_energy_live` (W1) вызывает его для **всех** активных счётчиков (`td_energy_node_live.py:165`); переопределение вызывает `super()` для `resource_id.code == 'el'`, а для не-el считает `data_state` сам: `counter` — по `qty_signal_id`, `flow_integrate` — по `flow_signal_ids` (свежесть: `last_ts ≥ now − 3·period_s`; несвежий хотя бы один — `stale`; нет показаний — `no_data`), `estimate` — по последнему слоту (`stale`, если последний построенный слот старше 30 мин; `gap`, если за 2 ч есть `missing`/`interpolated`), иначе `ok`; события `meter` для не-el **не** создаются (A-14);
- `last_value`, `last_ts` (related `e_import_signal_id`) у не-el пусты — экран ресурсов их не использует (берёт сигналы по R-08).

Критично для регрессии `td_energy` (A-02): все остальные выборки счётчиков (`td.energy.interval._cron_build`, `tools/backfill.Plan`, баланс, `_td_shift_kwh`) ищут по `e_import_signal_id != False` или по ролям; у не-el счётчиков `e_import_signal_id` пуст, поэтому они из электрических расчётов исключены без правки кода `td_energy`. AC-05 и AC-06 проверяют это: тесты `td_energy` (142) и W1 запускаются на БД с 16 неэлектрическими счётчиками.

### M-05 `td.energy.tariff` — расширение (`_inherit`; FR-21, Q-03)

| Поле | Тип | Параметры |
|---|---|---|
| `tg_phi_limit` | Float | digits (4,2), default 0, `cost`, «Допустимий tg φ (0 — доплати немає)» |
| `react_rate` | Float | digits (10,4), default 0, `cost`, «Ставка за реактивну енергію понад ліміт, ₴/квар·год» |

Constraint: `tg_phi_limit ≥ 0`, `react_rate ≥ 0`; `react_rate > 0` при `tg_phi_limit = 0` → `ValidationError("Ставка без ліміту tg φ не має сенсу.")`. Метод `_td_react_penalty(excess_kvarh)` → `excess × react_rate` (0 если лимит не задан).

### M-06 `td.energy.res.interval` — 15-минутный ряд не-электрики (FR-05, FR-07)

`_name = "td.energy.res.interval"`, `_inherit = ["td.energy.day.mixin"]` (фильтры «Сьогодні/Вчора/7 днів» из `td_energy`), `_description = "Енергетика: 15-хвилинний інтервал ресурсу"`, `_order = "ts_start desc, meter_id"`, `_log_access = False`, `_rec_name = "ts_start"`.

| Поле | Тип | Параметры |
|---|---|---|
| `meter_id` | Many2one `td.energy.meter` | req, ondelete=cascade, idx |
| `resource_id` | Many2one | related `meter_id.resource_id`, store, idx |
| `point_id` | Many2one `td.energy.point` | related `meter_id.point_id`, store, idx |
| `metric` | Selection | `main`/«Основна», `react`/«Реактивна»; req, default `main` (A-04); `react` — только для электрических вводов (kvarh) |
| `ts_start`, `ts_end` | Datetime | req; `ts_start` idx |
| `day` | Date | req, idx (Киев); `hour_local` Integer req |
| `qty` | Float | digits (14,3), «Кількість (од. ресурсу)» |
| `rate_avg` | Float | digits (12,3), «Середня швидкість» |
| `kwh_eq` | Float | digits (14,3), «кВт·год-еквівалент» (R-01; для воздуха и воды — 0) |
| `price` | Float | digits (12,4), `cost` |
| `cost` | Float | digits (14,2), `cost` |
| `quality` | Selection | `measured`, `estimated`, `interpolated`, `missing`; req, default `measured`, idx |
| `built_at` | Datetime | req |
| `is_backfill` | Boolean | default False, idx, readonly |

`_td_res_interval_uniq = models.Constraint("UNIQUE(meter_id, metric, ts_start)", "Інтервал ресурсу для лічильника вже є.")`. `init()`: индекс `(day, resource_id)`; индекс `(point_id, ts_start)`.
Методы: `_cron_build()` (R-05), `_cron_rotate()`, `_td_backfill(days=90, until=None, seed=20261018, purge=False, resources=None)` (R-22; API-08; доступ — `env.is_superuser()` или `td_factory3d.group_td_admin`, иначе `AccessError("Генерувати історію може лише адміністратор.")`).

### M-07 `td.energy.usage` — сводка (SQL-view; FR-06)

`_name = "td.energy.usage"`, `_description = "Енергетика: зведення використання"`, `_auto = False`, `_order = "ts_start desc"`. Создаётся в `init()` через `tools.drop_view_if_exists` + `CREATE VIEW`. Идентификатор строки — **без** `row_number()` (чтобы Postgres проталкивал фильтры): `id = i.id * 2` для электрических строк, `id = r.id * 2 + 1` для ресурсных.

| Поле | Тип | Значение |
|---|---|---|
| `resource_id` | Many2one `td.energy.resource` | `el` для электрических строк |
| `flow` | Selection | `import`, `export`, `generation`, `load` (электричество); `supply`, `branch` (ресурсы) — семантика R-07 |
| `ts_start` | Datetime | |
| `day`, `hour_local` | Date, Integer | |
| `node_id` | Many2one `td.energy.node` | электрические строки |
| `point_id` | Many2one `td.energy.point` | ресурсные строки |
| `meter_id` | Many2one `td.energy.meter` | |
| `qty` | Float | в единицах ресурса (`el` — кВт·ч) |
| `kwh_eq` | Float | R-01 |
| `cost` | Float | `cost`; `import`, `supply`, `branch` — по R-02; `load`, `generation`, `export` — 0 |
| `co2_kg` | Float | `qty × resource.co2_kg_per_unit` для `import` и `supply`; иначе 0 |
| `quality` | Char | |
| `is_backfill` | Boolean | |

Строки: `td_energy_interval` с `role='incomer'` → `import` (`qty = kwh`) и `export` (`qty = kwh_export`, если `> 0`); `role='feeder'` → `load`; `role='generation'` → `generation`; `td_energy_res_interval` с `metric='main'` и `point.kind='source'` → `supply`, остальные → `branch`. Роли `consumer`, `storage`, `metric='react'` в view **не** входят (A-03). Стоимость и CO₂ — только для `import`/`supply`; `groups="td_energy.group_td_energy_cost"` на `cost`.

### M-08 `td.energy.res.dashboard` — API экрана (AbstractModel; FR-08…FR-12)

`_name = "td.energy.res.dashboard"`, `_description = "Енергетика: дані екрана ресурсів"`. Доступ: `_td_check_access()` — `group_td_energy_user` или суперпользователь, иначе `AccessError("Немає доступу до Енергетики.")`; сигналы, показания, интервалы читаются через `sudo()`; ключи стоимости без `group_td_energy_cost` **удаляются** из ответа (как в W1 M-27). Методы — API-01. Хуки (пусты в ядре; перекрывает мост, C-04):

| Хук | Сигнатура | В ядре |
|---|---|---|
| `_td_heat_kpis` | `(self, ctx) -> list[dict]` | `[]` — KPI «Температура в цеху», «Рекуперація AHU-1» |
| `_td_heat_list` | `(self, ctx) -> list[dict] \| None` | `None` — «Куди йде тепло» из BMS |
| `_td_heat_chart_note` | `(self, ctx) -> str \| None` | `None` — подстановка `{capacity}` |
| `_td_resource_extra` | `(self, code, ctx) -> dict` | `{}` — дополнительные блоки ответа |

### M-09 `td.energy.opportunity.rule` — правило резерва (FR-13, FR-14)

`_name = "td.energy.opportunity.rule"`, `_description = "Енергетика: правило резерву економії"`, `_order = "sequence, code"`.

| Поле | Тип | Параметры |
|---|---|---|
| `code` | Char | size=32, req, `UNIQUE(code)`; = ключ детектора |
| `name` | Char | size=128, req, «Назва» |
| `sequence` | Integer | default 10 |
| `enabled` | Boolean | default True, «Увімкнено» |
| `resource_id` | Many2one `td.energy.resource` | req, «Вкладка, де показується» |
| `lookback_days` | Integer | default 7, constraint `1…60` (сырые показания хранятся 30 сут, `td.telemetry.keep_days`) |
| `min_saving_uah` | Float | default по правилу, `cost` — минимальная оценка ₴/мес |
| `params` | Json | default из XML; пороги (R-14) |
| `params_schema` | Json | список `{key, label, type: float\|int\|bool, min, max, unit, default}`; редактируется только разработчиком (`noupdate`) |
| `actions` | Json | default `[]`; **контракт C-32** (W1 M-26): `{code, label, kind: link\|ticket\|control, class: null\|A\|B, params}` |
| `fallback_action` | Json | default `{"code":"open","label":"Відкрити","kind":"link","params":{"xmlid":"td_energy_resources.action_td_energy_opportunity"}}` |
| `control_intent` | Char | size=48, «Намір керування» (непрозрачный ключ для W2: `vent_night_mode`, `heat_schedule_shift`, `air_pressure_setpoint`, `pv_self_consumption`; пусто — действия `control` нет); W3 его не интерпретирует (C-02) |
| `cooldown_days` | Integer | default 14 — после `done` повторное создание не раньше |
| `dismiss_days` | Integer | default 30 — после `dismissed` не создавать |
| `requires` | Char | size=64, «Потрібні модулі/сигнали» (текст для подсказки в UI; пример: `td_bms`) |
| `last_run`, `last_count`, `last_error` | Datetime / Integer / Char | readonly |
| `company_id` | Many2one `res.company` | default `env.company` |

Constraints: `_check_params` (каждый ключ из `params_schema` присутствует, тип и диапазон верны: `ValidationError("Параметр %s: очікується %s у діапазоні %s…%s.")`), `_check_actions` (для каждого элемента `kind ∈ {link, ticket, control}`, `code` по `^[a-z0-9_]{1,32}$`, `label` ≤ 48).
Методы: `_td_detector_methods()` — реестр `tools/detectors.DETECTORS` + методы моста (`_td_detect_<code>` в `_inherit` модели, A-08); `action_run()` (`group_td_energy_manager`; запускает одно правило, как крон, и возвращает статистику); `_td_detect(now)` → список находок (R-14).

### M-10 `td.energy.opportunity` — резерв экономии (FR-13…FR-15)

`_name = "td.energy.opportunity"`, `_description = "Енергетика: резерв економії"`, `_inherit = ["mail.thread"]`, `_order = "in_plan desc, est_saving_month desc, id"`.

| Поле | Тип | Параметры |
|---|---|---|
| `rule_id` | Many2one `td.energy.opportunity.rule` | req, idx, ondelete=restrict |
| `resource_id` | Many2one | related `rule_id.resource_id`, store, idx |
| `dedup_key` | Char | size=96, idx, req: `<rule.code>:<scope>` (`vent_offshift:*`, `ahu_recuperation:AHU-1`); `UNIQUE(dedup_key) WHERE state = 'open'` — частичный индекс в `init()` |
| `title` | Char | size=160, req |
| `text` | Text | req |
| `est_saving_month` | Float | digits (14,2), `cost`, «Економія, ₴/міс» |
| `est_qty_month` | Float | digits (14,2), «Економія в од. ресурсу/міс» |
| `evidence` | Json | default `{}`; числа, на которых построена оценка (R-14) |
| `state` | Selection | `open`/«Відкрите», `done`/«Виконано», `dismissed`/«Відхилено», `expired`/«Втратило актуальність»; default `open`, idx, tracking |
| `in_plan` | Boolean | default False, idx, tracking, «У плані» (A-07: отдельно от `state`) |
| `plan_user_id`, `plan_date` | Many2one `res.users` / Date | readonly |
| `found_at`, `last_seen_at` | Datetime | readonly |
| `node_id` | Many2one `td.energy.node` | ondelete=set null |
| `point_id` | Many2one `td.energy.point` | ondelete=set null |
| `request_id` | Many2one `maintenance.request` | ondelete=set null, readonly |
| `actions` | Json | копия `rule.actions` с подставленными параметрами (`node_code`, `description` с тегом `[OPP-<id>]`) |
| `result_note` | Char | size=256 |
| `resolved_at`, `resolved_by` | Datetime / Many2one `res.users` | readonly |
| `company_id` | Many2one `res.company` | default `env.company` |

Методы (API-02…API-06, R-13): `get_list(resource_code=None, states=("open",))`, `get_plan_summary()`, `action_plan_toggle(plan=None)`, `action_dismiss()`, `action_done(note=None)`, `_cron_detect()`, `_td_link_requests()`. Права: чтение — `group_td_energy_user`; `action_plan_toggle/dismiss/done` — `group_td_energy_manager`, иначе `AccessError("Керувати резервами може лише енергетик.")`.

### M-11 `res.config.settings` — расширение

Поля `td_energy_resources_*` с `config_parameter` (разд. 5.1), блок `app name="td_energy_resources"` не создаётся — группа «Енергоресурси» добавляется в блок `td_energy` (V-12). `set_values` валидирует `night_from_h < 24`, `night_to_h`, `gap_max_s ≥ 300`, `min_coverage ∈ (0,1]`.

## 3. Представления и меню

### 3.1 Представления V-01…V-13

| ID | XML-id (`td_energy_resources.`) | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `action_td_energy_resources` | `ir.actions.client`, `tag="td_energy_resources.resources"`, `name="Енергоресурси заводу"`, `context={"td_energy_resource": "el"}` | UI-01 |
| V-02 | `view_td_energy_resource_list` / `_form`, `action_td_energy_resource` | list/form `td.energy.resource` | list: `sequence` (handle), `code`, `name`, `uom_label`, `rate_label`, `is_derived`, `active`; form: группы «Одиниці» (`uom_label`, `rate_label`, `rate_hour_factor`, `kwh_per_unit`, `co2_kg_per_unit`), «Вартість» (`price_source`, `is_derived`, `in_energy_cost`, `show_tab_cost`, `source_note`), «Ліміти» (`limit_kind`, `rate_limit`, `daily_limit`), «Екран» (`color`, `chart_title`, `chart_note`, `list_title`, `list_basis`, `foot_template`); smart-кнопки «Лічильники», «Точки», «Ціни»; редактирование — `group_td_energy_manager` |
| V-03 | `view_td_energy_price_list` / `_form`, `action_td_energy_price` | `td.energy.price` | list: `resource_id`, `date_from`, `date_to`, `price` (`cost`), `currency_id`; группировка по ресурсу; без группы стоимости цена скрыта |
| V-04 | `view_td_energy_point_list` / `_form` / `_search` / `_kanban`, `action_td_energy_point` | `td.energy.point` | list с группировкой по ресурсу и `kind`, колонки `code`, `name`, `kind`, `parent_id`, `node_id`, `estimate_method`, `meter_count`; form: вкладки «Облік» (`kind`, `parent_id`, `meter_ids`), «Оцінка» (`estimate_method`, `estimate_params` JSON, `rate_nominal`, `min_pressure_bar`, `state_signal_id`), «Зв'язки» (`node_id`, `cost_node_id`, `equipment_id`, `hvac_ref`), чаттер |
| V-05 | `view_td_energy_meter_form_resources` (наследует `td_energy.view_td_energy_meter_form`), `view_td_energy_meter_list_resources`, `action_td_energy_meter_resources` | `td.energy.meter` | в форме: группа «Ресурс» (`resource_id`, `point_id`, `mode`, `qty_signal_id`, `flow_signal_ids`, `max_rate`; `invisible="resource_id.code == 'el'"` для не-электрических полей), поле `e_react_signal_id` — `invisible="role != 'incomer'"`; `node_id` — `required="resource_id.code == 'el'"`; действие `action_td_energy_meter_resources`: domain `[("resource_id.code", "!=", "el")]`, list-колонки `code`, `point_id`, `mode`, `data_state`, `res_last_interval_start`, `next_verification` (optional) |
| V-06 | `view_td_energy_res_interval_list` / `_pivot` / `_graph` / `_search`, `action_td_energy_res_interval` | `td.energy.res.interval` | readonly; list: `ts_start`, `meter_id`, `qty`, `rate_avg`, `quality` (badge), `cost` (`cost`), `is_backfill` (optional hide); pivot: строки `day`, столбцы `resource_id`, мера `qty`; search: «Сьогодні», «Вчора», «Синтетичні», группировка `resource_id`, `point_id`, `quality` |
| V-07 | `view_td_energy_usage_pivot` / `_graph` / `_search`, `action_td_energy_usage` | `td.energy.usage` (readonly) | pivot: строки `day`, столбцы `flow`, мера `qty`, `cost`; graph: bar по `day`; search по `resource_id`, `flow`, `is_backfill`; меню — только `group_td_energy_manager` |
| V-08 | `view_td_energy_opportunity_rule_list` / `_form`, `action_td_energy_opportunity_rule` | `td.energy.opportunity.rule` | list: `sequence`, `code`, `name`, `resource_id`, `enabled` (toggle), `lookback_days`, `min_saving_uah`, `last_run`, `last_count`; form: `enabled`, `resource_id`, `lookback_days`, `min_saving_uah`, `cooldown_days`, `dismiss_days`, блок «Пороги» (`params` — JSON-редактор + таблица `params_schema` readonly), блок «Дії» (`actions`, `fallback_action`), кнопка «Запустити зараз» (`action_run`); создавать/удалять — `group_td_admin` |
| V-09 | `view_td_energy_opportunity_list` / `_form` / `_search` / `_kanban`, `action_td_energy_opportunity` | `td.energy.opportunity` | list: `in_plan` (toggle-чекбокс), `title`, `resource_id`, `est_saving_month` (`cost`), `state` (badge: open — warning, done — success, dismissed — muted, expired — muted), `request_id`; form: статусбар `state`; кнопки «У план / З плану» (`action_plan_toggle`), «Відхилити», «Виконано» (wizard примечания → `action_done`); вкладка «Підстава» (`evidence` JSON) и «Дії» (`actions`); search: «Відкриті» (default), «У плані», «Ресурс»; group by `resource_id`, `rule_id` |
| V-10 | `view_td_energy_tariff_form_resources` (наследует форму тарифа td_energy) | form | группа «Реактивна енергія» (`tg_phi_limit`, `react_rate`) под блоком договорной мощности; подсказка «0 — доплати немає; правило «Реактивна енергія секції» вимкнене» |
| V-11 | `action_td_energy_resources_rebind` (server action) | `ir.actions.server` | «Оновити прив'язку ресурсів»: вызывает `hooks._seed_points_meters(env)` и `_bind_react_signals(env)` (идемпотентно); пункт в «Налаштування», `group_td_energy_manager` |
| V-12 | `res_config_settings_view_form_td_energy_resources` (наследует `td_energy.res_config_settings_view_form_td_energy`) | `res.config.settings` | группа «Енергоресурси»: `td_energy_resources_boiler_eff`, `…_boiler_eff_norm`, `…_night_from_h`, `…_night_to_h`, `…_air_spec_norm`, `…_water_night_norm`, `…_boiler_makeup_norm`, `…_air_setpoint_bar`, `…_gap_max_s`, `…_min_coverage`, `…_export_max_days`, `…_weeks_per_month` |
| V-13 | `views/menus.xml` | `ir.ui.menu` | таблица 3.3 |

### 3.2 Клиентские компоненты (OWL) UI-01…UI-08

Всё — `@odoo/owl`, регистрация `registry.category("actions").add("td_energy_resources.resources", Resources)`; данные — `orm.call("td.energy.res.dashboard", "get_resources", [], {code})`; шина — `useEnergyBus` из `td_energy` (`@td_energy/common/bus`, подписка на `kpi`), резервный опрос `meta.refresh_s`; запуск действий резервов — `runAdviceAction` и реестр `td_energy.advice_handlers` из W1 (`@td_energy/common/advice`). Каждый интерактивный узел — `<button>` с `aria-label`; состояние — не только цветом (текстовый чип, точка качества «оцінка» пунктиром); кнопки ≥ 36 px как в макете.

| ID | Компонент | Содержимое и поведение |
|---|---|---|
| UI-01 | `Resources` (`td_energy_resources.resources`) | Шапка: крошки «Енергетика / Енергоресурси», h1 «Енергоресурси заводу», строка итога `meta.total.text` (D-31), кнопка «Вивантажити в Excel» (открывает `/td/energy/resources/export?day=<день>` как загрузку). Ниже `ResTabs`, `ResKpis`, блок «график + список», `ResNotes`. Состояние: `code` (по умолчанию `context.td_energy_resource` или первая вкладка), `data`, `failed`. Подписка на шину (дебаунс 2 с) |
| UI-02 | `ResTabs` | `role="tablist"`: кнопки по `tabs[]` (название + подпись `sub`); выбранная — рамка 2 px `accent`; переключение перезагружает `get_resources(code)` |
| UI-03 | `ResKpis` | Карточки (`flex: 1 1 220px`): метка, значение 26 px, единица, примечание; цвет примечания по `tone` (`good` зелёный, `bad` оранжевый, `neutral`); точка качества у значений `quality='estimated'` |
| UI-04 | `ResChart` | SVG `viewBox 0 0 880 262`: сетка (4 линии), подписи оси Y (0, y1, y2, y3) и часов 00…24 каждые 3 ч, область + линия цвета ресурса (`resource.color`), пунктир лимита (`limit`), вертикаль «зараз» в `X(now)`, `X(h)=40+h/24·820`, `Y(v)=230−v/y_max·210`; `null`-слоты разрывают линию; подпись `foot` под графиком |
| UI-05 | `ResList` | Заголовок `list.title`; строки: код · название, значение (`value unit`), полоса 6 px шириной `share·100 %`; точка качества |
| UI-06 | `ResNotes` | Секция «Що помітила система»; строка: заголовок, текст, «≈ N ₴/міс» (только если ключ есть), кнопка по первому доступному действию (`actions[]` с `enabled !== false`; `control` — только при обработчике в `td_energy.advice_handlers`); при пустом списке — «Відхилень немає» + «Налаштувати пороги» (виден `capabilities.manage`, ведёт на `action_td_energy_opportunity_rule`) |
| UI-07 | `useResourceDay` | Хелпер: форматирование `fmtInt/fmtDec/fmtMoney` из `@td_energy/common/format`; единицы и знаки uk-UA |
| UI-08 | `td_energy_resources.scss` | Токены цветов ресурсов (`--td-res-el|gas|heat|air|water`), остальные — `td_energy.scss` (W1 UI-11); адаптив ≥ 360 px (колонки сворачиваются, график 100 % ширины) |

### 3.3 Меню (`views/menus.xml`)

Корень: `td_factory3d.menu_td_root` → `td_energy.menu_td_energy` (как в W1). Порядок по макету: Пульт (5) → [«Чергування» 6] → «Керування» (W2) → **«Енергоресурси» (10)** → «Аналітика» (W4, 12) → «Завантаження вузлів» (15).

| XML-id (`td_energy_resources.`) | Название | Родитель | seq | Группы | Действие |
|---|---|---|---|---|---|
| `menu_td_energy_resources` | Енергоресурси | `td_energy.menu_td_energy` | 10 | `td_energy.group_td_energy_user` | `action_td_energy_resources` |
| `menu_td_energy_resources_config` | Енергоресурси | `td_energy.menu_td_energy_config` | 50 | `…group_td_energy_manager` | — (раздел) |
| `menu_td_energy_resource` | Ресурси | `…_config` (этот раздел) | 10 | manager | `action_td_energy_resource` |
| `menu_td_energy_price` | Ціни | `…_config` | 20 | `…group_td_energy_cost` | `action_td_energy_price` |
| `menu_td_energy_point` | Точки обліку | `…_config` | 30 | manager | `action_td_energy_point` |
| `menu_td_energy_meter_resources` | Лічильники ресурсів | `…_config` | 40 | manager | `action_td_energy_meter_resources` |
| `menu_td_energy_res_interval` | Інтервали ресурсів | `…_config` | 50 | manager | `action_td_energy_res_interval` |
| `menu_td_energy_usage` | Зведення використання | `…_config` | 60 | manager | `action_td_energy_usage` |
| `menu_td_energy_opportunity_rule` | Правила резервів | `…_config` | 70 | manager | `action_td_energy_opportunity_rule` |
| `menu_td_energy_opportunity` | Резерви економії | `td_energy.menu_td_energy` | 74 | user | `action_td_energy_opportunity` |
| `menu_td_energy_resources_rebind` | Оновити прив'язку ресурсів | `…_config` | 80 | manager | `action_td_energy_resources_rebind` |

## 4. Права

### 4.1 `security/ir.model.access.csv` (A) и `security/ir.model.access-opportunity.csv` (B)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_energy_resource_user,td.energy.resource user,model_td_energy_resource,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_resource_manager,td.energy.resource manager,model_td_energy_resource,td_energy.group_td_energy_manager,1,1,0,0
access_td_energy_resource_admin,td.energy.resource admin,model_td_energy_resource,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_price_user,td.energy.price user,model_td_energy_price,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_price_manager,td.energy.price manager,model_td_energy_price,td_energy.group_td_energy_manager,1,1,1,0
access_td_energy_price_admin,td.energy.price admin,model_td_energy_price,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_point_user,td.energy.point user,model_td_energy_point,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_point_manager,td.energy.point manager,model_td_energy_point,td_energy.group_td_energy_manager,1,1,1,1
access_td_energy_res_interval_user,td.energy.res.interval user,model_td_energy_res_interval,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_res_interval_admin,td.energy.res.interval admin,model_td_energy_res_interval,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_usage_user,td.energy.usage user,model_td_energy_usage,td_energy.group_td_energy_user,1,0,0,0
```

`-opportunity.csv`:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_energy_opportunity_rule_user,td.energy.opportunity.rule user,model_td_energy_opportunity_rule,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_opportunity_rule_manager,td.energy.opportunity.rule manager,model_td_energy_opportunity_rule,td_energy.group_td_energy_manager,1,1,0,0
access_td_energy_opportunity_rule_admin,td.energy.opportunity.rule admin,model_td_energy_opportunity_rule,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_opportunity_user,td.energy.opportunity user,model_td_energy_opportunity,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_opportunity_manager,td.energy.opportunity manager,model_td_energy_opportunity,td_energy.group_td_energy_manager,1,1,0,0
access_td_energy_opportunity_admin,td.energy.opportunity admin,model_td_energy_opportunity,td_factory3d.group_td_admin,1,1,1,1
```

`td.energy.meter` и `td.energy.tariff` — права `td_energy` достаточны (новые поля наследуют); `td.energy.res.dashboard` — AbstractModel без ACL (контроль в методах); запись в `td.energy.res.interval` — только крон/backfill/`sudo()` (потому write/create/unlink — только `group_td_admin`).

### 4.2 Группы

Новых групп нет: «Перегляд» = `td_energy.group_td_energy_user`; ₴ = `…_cost`; «Енергетик» = `…_manager` (действия над резервами, настройки); «Головний енергетик» = `…_chief` (наследует manager; в W3 отдельных прав не имеет); адм. операции (backfill, создание правил) — `td_factory3d.group_td_admin`.

### 4.3 Record rules

`td_energy_price_rule_company`, `td_energy_point_rule_company`, `td_energy_opportunity_rule_company`, `td_energy_opportunity_company` — домен `['|', ('company_id','=',False), ('company_id','in',company_ids)]`, глобальные. `td.energy.res.interval`, `td.energy.usage` — без company (изоляция через `meter_id`, `point_id`).

### 4.4 Защита данных и действий

- Ключи стоимости (`cost_uah`, `price_uah`, `save_uah_month`, колонка `cost` в xlsx) без `group_td_energy_cost` **удаляются** из ответов API-01, API-02, API-10 и xlsx (AC-21, AC-47).
- Управление резервами — `group_td_energy_manager`; запуск детекторов — крон (`base.user_root`) или manager.
- Записей в устройства нет: `write_enabled` не меняется, эмулятор и сборщик только читают.
- Заявки ТО из резервов создаются через W1-мастер `td.energy.ticket.wizard` (права как в W1).
- Экспорт (API-07): `auth='user'`, проверка группы, параметры валидируются (дата, коды ресурсов — только из справочника), нет произвольных SQL-параметров.

## 5. Данные

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`) — параметры `td.energy_resources.*`

| Ключ | По умолчанию | Назначение |
|---|---|---|
| `td.energy_resources.boiler_eff` | `0.91` | проектный КПД котельной: цена тепла (R-02 п. 3) до появления измерений |
| `td.energy_resources.boiler_eff_norm` | `90` | норма КПД, %: KPI «ККД котельні» (R-09) |
| `td.energy_resources.night_from_h` | `23.0` | начало «ночи» (местные часы) для ночных расходов и утечек |
| `td.energy_resources.night_to_h` | `6.5` | конец «ночи» (06:30) |
| `td.energy_resources.air_spec_norm` | `6.0` | норма удельной мощности воздуха, кВт/(м³/мин) |
| `td.energy_resources.water_night_norm` | `0.05` | норма ночного расхода воды, м³/ч |
| `td.energy_resources.boiler_makeup_norm` | `0.5` | норма подпитки котельной, м³/сутки |
| `td.energy_resources.air_setpoint_bar` | `7.0` | уставка давления воздуха, пока нет сигнала `air/setpoint_bar` (Q-07; владелец сигнала — W2) |
| `td.energy_resources.gap_max_s` | `900` | максимальный разрыв между показаниями, внутри которого ряд линейно интерполируется (R-03) |
| `td.energy_resources.min_coverage` | `0.3` | минимальная доля слота с данными, при которой слот строится (иначе `missing`) |
| `td.energy_resources.export_max_days` | `31` | максимум суток в одном xlsx (API-07) |
| `td.energy_resources.weeks_per_month` | `4.33` | перевод недельных величин в месячные (R-14) |

Существующие параметры `td_energy`, используемые модулем: `td.energy.read_enabled` (стоп-кран кронов), `td.energy.keep_interval_days` (ротация, 400), `td.energy.shift_calendar_id` (календарь смен, R-21), `td.energy.pv_kwp`, `td.energy.pult_refresh_s` (опрос UI), `td.energy.load_warn_pct`.

### 5.2 `data/td_energy_resource.xml` (`noupdate="1"`): 5 записей

| xml-id | code | name | uom / rate | rate_hour_factor | kwh_per_unit | co2 | is_derived | in_energy_cost | show_tab_cost | source_note | price_source | limit_kind / rate_limit / daily_limit | list_basis | color |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `resource_el` | `el` | Електрика | кВт·год / кВт | 1 | 0 | 0,37 | нет | да | да | — | `tariff` | `tariff_contract` / — / 0 | rate | `#714B67` |
| `resource_gas` | `gas` | Газ | м³ / м³/год | 1 | 10,5 | 1,96 | нет | да | да | — | `price` | `fixed` / 80 / 1200 | rate | `#b45309` |
| `resource_heat` | `heat` | Тепло | кВт·год / кВт | 1 | 0 | 0 | да | нет | нет | з BMS | `derived_gas` | `none` | rate | `#c2410c` |
| `resource_air` | `air` | Стиснене повітря | норм. м³ / м³/хв | 60 | 0 | 0 | да | нет | да | — | `derived_el` | `none` | rate | `#0369a1` |
| `resource_water` | `water` | Вода | м³ / м³/год | 1 | 0 | 0 | нет | нет | да | — | `price` | `none` | `qty_day` | `#0f766e` |

Заголовки графиков, `chart_note`, `list_title`, `foot_template` — по тексту макета (M-01). Источники чисел: газ 10,5 кВт·ч/м³ и 19,80 ₴/м³ (`GAP.md` §4.2, §4.3, макет `Resources.dc.html`, ключ `gas`); CO₂: сеть 0,37 кг/кВт·ч и газ 1,96 кг/м³ выведены из макета «Викиди CO₂» (`Analytics.dc.html`: 186 400 кВт·ч → 69 т, 18 400 м³ → 36 т); вода 60 ₴/м³ (макет `water`: 252 ₴ / 4,2 м³). `foot_template` (R-10): `el` «Пік доби {peak_kw} кВт о {peak_time}.{export_sentence}», `gas` «Нічна витрата {night} м³/год, у зміну {day} м³/год. Пік {peak} м³/год о {peak_time}.», `heat` «Найбільша частка тепла — {top_name} ({top_share} %).», `air` «{leak_sentence}», `water` «Нічна витрата {night} м³/год {norm_sentence}.»

`data/td_energy_price_data.xml` (`noupdate="1"`, демо): `td.energy.price` газ 19,80 ₴/м³ и вода 60,00 ₴/м³, `date_from = 2025-01-01`, без `date_to`.

### 5.3 Демо-точки и счётчики (`data/resource_points.csv`, `data/resource_meters.csv`; загружает `hooks._seed_points_meters(env)`, идемпотентно по `(resource, code)`)

Точки (`kind`: S — source, C — consumer; `nominal` — `rate_nominal`; метод — `estimate_method`):

| Ресурс | Код | Название | kind | node_id (код вузла) | Метод оценки и параметры |
|---|---|---|---|---|---|
| gas | `GAS-MAIN` | Головний газовий лічильник | S | — | — |
| gas | `BOILER` | Котельня цеху | C | `BOILER` | — (измеряется) |
| gas | `DRY-1` | Сушильна камера (газовий пальник) | C | `DRY-1` | `load_share`, nominal 6,0 м³/год |
| gas | `CHP` | КГУ TEDOM (резерв) | C | `CHP` | — (измеряется) |
| gas | `CANTEEN` | Їдальня | C | — | `schedule` `{"from_h":8,"to_h":16,"weekdays":[0,1,2,3,4],"rate":1.0}` |
| air | `AIR-MAIN` | Магістраль стисненого повітря | S | — (`cost_node_id` = `COMPRESSOR`) | — |
| air | `EDGE-1` | Крайкооблицювання A | C | `EDGE-1` | `load_share`, nominal 3,0 м³/хв, `min_pressure_bar` 6,0 |
| air | `NEST-1` | Нестинг ЧПК | C | `NEST-1` | `load_share`, 2,25, 6,0 |
| air | `PRESS-1` | Мембранний прес | C | `PRESS-1` | `load_share`, 1,9, 6,2 |
| air | `SPRAY-1` | Фарбувальна камера | C | `SPRAY-1` | `load_share`, 1,6, 5,5 |
| air | `CNC-1` | Присадка ЧПК A | C | `CNC-1` | `load_share`, 1,1, 5,5 |
| water | `WATER-MAIN` | Основний ввід води | S | — | — |
| water | `SOCIAL` | Побутові приміщення | C | — | `residual` `{"from":["WATER-MAIN"]}` |
| water | `CANTEEN` | Їдальня | C | — | `schedule` `{"from_h":10,"to_h":15,"weekdays":[0,1,2,3,4],"rate":0.22}` |
| water | `BOILER` | Підживлення котельні | C | `BOILER` | — (измеряется) |
| water | `SPRAY-1` | Фарбувальна камера | C | `SPRAY-1` | `load_share`, nominal 1,5 м³/год |

Значения `rate_nominal` и `min_pressure_bar` — **ПРИПУЩЕННЯ** до появления паспортных данных (Q-02); числа подобраны так, чтобы при электрической нагрузке макета (EDGE-1 41 кВт) получить его скорости (R-04 п. 1: 2,4 м³/мин).

Счётчики (`code`, точка, `mode`, сигналы): `GM-MAIN` (`GAS-MAIN`, `counter`, `qty_signal` `infra/gas/m3_total`); `GM-BOILER` (`BOILER`, `flow_integrate`, `equipment/BOILER/gas_m3h`); `GM-CHP` (`CHP`, `flow_integrate`, `infra/chp/gas_m3h`); `GM-DRY1`, `GM-CANTEEN` (`estimate`); `AM-MAIN` (`AIR-MAIN`, `flow_integrate`, `air/flow_m3min`, `rate_hour_factor` ресурса 60); `AM-EDGE1`, `AM-NEST1`, `AM-PRESS1`, `AM-SPRAY1`, `AM-CNC1` (`estimate`); `WM-MAIN` (`WATER-MAIN`, `counter`, `infra/water/m3_total`); `WM-BOILER` (`counter`, `infra/water/boiler_m3_total`); `WM-CANTEEN`, `WM-SOCIAL`, `WM-SPRAY` (`estimate`). Итого 16 счётчиков, 16 точек. Реактивные сигналы привязываются к существующим `PM-Q1` и `PM-Q2` (`e_react_signal_id`: `energy/cells/Q1/kvarh_total`, `…/Q2/…`) функцией `_bind_react_signals(env)`; новых счётчиков для них нет. Тепловые точки и счётчики — мост (Часть II).

### 5.4 Сигналы и источники (`data/resource_signals.csv`, `data/resource_sources.csv`; владелец D; загружает `hooks._ensure_resource_signals(env)`)

Формат CSV сигналов — как `td_energy/data/energy_signals.csv` (колонки `code,name,quantity,kind,unit,equipment,source,address,period_s,store_period_s,decimals,states,warn_low,…,derived_from,origin,binding`). Источники — колонки `code,name,unit,equipment,host,port,timeout_s,retries,max_block,gap_max`. Функция идемпотентно создаёт отсутствующие записи, существующие не меняет.

Источники: `MB-U74-GAS-MAIN` (Modbus TCP, unit 74, `iot-sim:502`, `max_block=125`, `gap_max=8`, оборудование `GAS-MAIN`), `MB-U75-AIR-MAIN` (unit 75, оборудование `AIR-MAIN`). Адреса — **ПРИПУЩЕННЯ** для эмулятора (на объекте — по документу вендора корректора газа и расходомера воздуха; Q-02). Существующие: `MB-U84-IO5` (вода), `BAC-140-BOILER` (котельня), `MB-U01-PM-Q1`, `MB-U02-PM-Q2`, `MB-U72-CHP`, `MB-U70-COMPRESSOR`.

| Код сигнала | kind / ед. | Источник и адрес | Период / хранение | Примечание |
|---|---|---|---|---|
| `infra/gas/m3_total` | counter, м³ | `MB-U74-GAS-MAIN`, FC3 HR 0–1, u32 little, scale 0,01 | 60 / 60 с | показание счётчика газа (импульс 0,01 м³) |
| `infra/gas/flow_m3h` | gauge, м³/ч | — (производный от `m3_total`, `derive_rule=rate_h`, окно 5 мин) | 60 / 300 с | как `infra/water/flow_m3h` |
| `equipment/BOILER/gas_m3h` | gauge, м³/ч | `BAC-140-BOILER`, AI instance 6 (**ПРИПУЩЕННЯ**: проверить свободный номер; занято AI 1, 2, 3, 5) | 30 / 300 с | `module='energy'`, read-only |
| `air/flow_m3min` | gauge, м³/мин | `MB-U75-AIR-MAIN`, FC3 HR 0, u16, scale 0,01 | 10 / 300 с | расход магистрали |
| `air/m3_total` | counter, норм. м³ | `MB-U75-AIR-MAIN`, HR 2–3, u32 little, scale 0,1 | 60 / 60 с | |
| `air/pressure_bar` | gauge, бар | `MB-U75-AIR-MAIN`, HR 4, u16, scale 0,01 | 10 / 300 с | давление магистрали; `warn_low=5.8`, `min_duration_s=300`, без заявки |
| `infra/water/boiler_m3_total` | counter, м³ | `MB-U84-IO5`, FC3 HR 18–19, u32 little, scale 0,01 (канал DI, **ПРИПУЩЕННЯ**) | 60 / 60 с | подпитка котельной |
| `infra/water/boiler_flow_m3h` | gauge, м³/ч | производный от `boiler_m3_total`, `rate_h` | 60 / 300 с | |
| `energy/cells/Q1/kvarh_total` | counter, квар·ч | `MB-U01-PM-Q1`, FC3 HR 3219, i64, scale 0,001 (PM5560 «Reactive Energy Delivered», **ПРИПУЩЕННЯ**: подтвердить по `PM5500 series user manual`, регистры 3220…) | 60 / 60 с | реактивная энергия ввода |
| `energy/cells/Q2/kvarh_total` | counter, квар·ч | `MB-U02-PM-Q2`, тот же адрес | 60 / 60 с | |

Итого **+10 сигналов, +2 источника**; у всех десяти `module='energy'` (read-only, `write_enabled=False`), `origin` — `sim_data` для регистровых и `module` для производных. Сигнал `air/setpoint_bar` **не** создаётся: его вводит W2 (контракт C-02). Пороги сигналов не создают заявок ТО (`create_request=False`, `alarm_title` пусто).

### 5.5 `post_init_hook` и миграция `19.0.1.0.0`

Шаги (идемпотентные; одни и те же функции вызывает миграция `post-migration.py` при `-u`):
1. `_set_el_on_meters(env)`: SQL `UPDATE td_energy_meter SET resource_id = <id resource_el>, mode = 'counter' WHERE resource_id IS NULL` (пакетами 5 000); колонка добавляется с `default` Odoo, но существующие строки обязательно проверяются явным UPDATE;
2. загрузка ресурсов/цен — XML (`noupdate`), для существующих БД записи создаются при `-u`;
3. `_ensure_resource_signals(env)` (5.4);
4. `_seed_points_meters(env)` (5.3), затем `env["td.energy.point"]._td_bind_extra()` (хук моста);
5. `_bind_react_signals(env)`: `PM-Q1.e_react_signal_id`, `PM-Q2.e_react_signal_id` (если сигналы есть и поле пусто);
6. параметры (5.1) — XML.

Ожидаемые количества на демо-БД после установки (`f3d_full2`, 67 электрических счётчиков): `td.energy.resource` 5; `td.energy.meter` 67 → у всех `resource_id=el`, +16 неэлектрических; `td.energy.point` 16; сигналов `energy` +10 (всего 312 + 10 = 322 при установленном W1), `td.source` +2 (136 → 138); `td.energy.price` 2; правил резервов 6 (+3 мост); параметров +12; `td.energy.interval` не изменяется (число строк до/после — AC-05).

### 5.6 `uninstall_hook`

Удаляет неэлектрические счётчики (`resource_id.code != 'el'`; они не могут существовать без модуля: `node_id` возвращается в `required=True`), снимает `e_react_signal_id`, удаляет собственные крон-записи и параметры `td.energy_resources.*`. Таблицы модуля (`td_energy_res_interval`, точки, цены, резервы) удаляются штатно Odoo вместе с моделями. Электрические данные (`td.energy.interval`, `td.energy.alloc`, события) и сигналы **не** удаляются. `neutralize.sql`: отключить крон `cron_td_energy_res_build`, `…_res_rotate`, `…_opportunity`, `…_opportunity_links`; источники `MB-U74-GAS-MAIN`, `MB-U75-AIR-MAIN` — `read_enabled=false` (как у остальных `energy`-источников).

## 6. Крон-задачи и фоновые процессы

Все — `user_id=base.user_root`, `try/except` с `_logger.exception`, без проброса исключения; при `td.energy.read_enabled = False` не действуют.

| XML-id | Название | Интервал | Метод | За один прогон | Лимит |
|---|---|---|---|---|---|
| `cron_td_energy_res_build` | Енергетика: інтервали ресурсів | 5 мин | `td.energy.res.interval._cron_build` | R-05: все активные неэлектрические счётчики + реактивные, слоты от `res_last_interval_start`, повтор двух последних слотов; затем `bus.tick('kpi')` | ≤ 5 с, ≤ 192 слота на счётчик |
| `cron_td_energy_res_rotate` | Енергетика: ротація інтервалів ресурсів | 1 сут, `nextcall` 03:10 Киев | `td.energy.res.interval._cron_rotate` | удалить `ts_start` старше `td.energy.keep_interval_days` пакетами 10 000 | ≤ 60 с |
| `cron_td_energy_opportunity` | Енергетика: резерви економії | 1 сут, `nextcall` 03:30 Киев | `td.energy.opportunity._cron_detect` | R-13: все включённые правила, upsert находок, истечение, привязка заявок | ≤ 60 с суммарно, ≤ 10 с на правило |
| `cron_td_energy_opportunity_links` | Енергетика: заявки резервів | 1 час | `td.energy.opportunity._td_link_requests` | R-13 п. 6 | ≤ 5 с |

## 7. HTTP/JSON API

Единственный новый HTTP-маршрут — API-07. Остальное — ORM-RPC от имени пользователя. Если не указано иное, методы — `@api.model`.

| ID | Сигнатура | Вход → выход | Ошибки |
|---|---|---|---|
| API-01 | `td.energy.res.dashboard.get_resources(code=None)` | `code` — код ресурса (по умолчанию первая вкладка) → JSON «Енергоресурси» (ниже) | неизвестный код → `UserError("Невідомий ресурс: %s.")`; без группы → `AccessError("Немає доступу до Енергетики.")` |
| API-02 | `td.energy.opportunity.get_list(resource_code=None, states=("open",))` | → `{"items": [opportunity…], "plan_sum": n, "all_sum": n}` (контракт C-01; формат элемента — ниже) | `AccessError` |
| API-03 | `td.energy.opportunity.action_plan_toggle(plan=None)` (на записи) | `plan=None` — инвертировать → `True` | `AccessError("Керувати резервами може лише енергетик.")`, `UserError("Резерв уже закрито.")` |
| API-04 | `td.energy.opportunity.action_dismiss()` / `action_done(note=None)` | → `True` | как API-03 |
| API-05 | `td.energy.opportunity.rule.action_run()` | → `{"found": n, "created": n, "expired": n, "seconds": f}` | `AccessError` |
| API-06 | `td.energy.opportunity.get_plan_summary()` | → `{"plan_sum": n, "all_sum": n, "plan_count": n, "open_count": n}` (₴/мес; без группы стоимости ключи сумм отсутствуют) | — |
| API-07 | `GET /td/energy/resources/export?day=YYYY-MM-DD[&day_to=YYYY-MM-DD][&resources=gas,air]` (`auth="user"`) | → `200` xlsx, `Content-Disposition: attachment; filename="energoresursy_<day>.xlsx"` | `400` неверная дата/код ресурса/`day_to-day+1 > export_max_days`; `403` без `group_td_energy_user`; `413` строк > 200 000 |
| API-08 | `td.energy.res.interval._td_backfill(days=90, until=None, seed=20261018, purge=False, resources=None)` | → статистика R-22 | `AccessError`, `UserError("Кількість діб має бути від 1 до 400.")` |
| API-09 | `td.energy.price._td_price_at(resource, dt_local=None)` | → `float` (C-01) | — |
| API-10 | `td.energy.res.dashboard._td_totals(day_from, day_to, resource_codes=None)` (внутренний, для W4/отчётов; `sudo`-чтение) | → `[{"resource","qty","kwh_eq","cost","co2_kg"}…]` по `td.energy.usage` | `AccessError` без группы |

### Ответ API-01 (вкладка «Газ», 14:20; значения — пример на основе макета)

```json
{
  "meta": {"now": "2026-10-17T11:20:00", "now_local": "14:20", "data_state": "ok", "age_s": 18, "refresh_s": 30,
           "control_available": false,
           "capabilities": {"cost": true, "export": true, "manage": true},
           "total": {"cost_uah": 65156, "text": "Сьогодні разом: 65 156 ₴ · Електрика, Газ, Вода. Похідні не додаються: Тепло, Стиснене повітря."}},
  "tabs": [
    {"code": "el", "name": "Електрика", "rate": 358, "rate_unit": "кВт", "cost_uah": 52786, "sub": "358 кВт · 52 786 ₴"},
    {"code": "gas", "name": "Газ", "rate": 46, "rate_unit": "м³/год", "cost_uah": 12118, "sub": "46 м³/год · 12 118 ₴"},
    {"code": "heat", "name": "Тепло", "rate": 390, "rate_unit": "кВт", "sub": "390 кВт · з BMS"},
    {"code": "air", "name": "Стиснене повітря", "rate": 9.8, "rate_unit": "м³/хв", "cost_uah": 5393, "sub": "9,8 м³/хв · 5 393 ₴"},
    {"code": "water", "name": "Вода", "rate": 0.4, "rate_unit": "м³/год", "cost_uah": 252, "sub": "0,4 м³/год · 252 ₴"}],
  "resource": {
    "code": "gas", "name": "Газ", "color": "#b45309",
    "kpis": [
      {"id": "rate", "label": "Витрата зараз", "value": 46, "unit": "м³/год", "note": "котельня BOILER · КГУ стоїть", "tone": "neutral", "quality": "measured"},
      {"id": "today", "label": "Сьогодні", "value": 612, "unit": "м³", "note": "12 118 ₴ · 19,80 ₴/м³", "tone": "neutral", "quality": "measured"},
      {"id": "limit", "label": "Ліміт доби за договором", "value": 1200, "unit": "м³", "note": "використано 51 %", "tone": "good", "quality": "measured"},
      {"id": "eff", "label": "ККД котельні", "value": 91.4, "unit": "%", "note": "норма ≥ 90 %", "tone": "good", "quality": "estimated"}],
    "chart": {"title": "Витрата газу, м³/год", "note": "ліміт години — 80 м³/год", "unit": "м³/год", "y_max": 90, "ticks": [30, 60, 90],
              "step_min": 15, "now_slot": 57, "series": [22.1, 21.8, "…96 значень, null після now_slot або без даних…"],
              "limit": 80, "foot": "Нічна витрата 22 м³/год, у зміну 46 м³/год. Пік 48 м³/год о 11:15."},
    "list": {"title": "Споживачі газу", "basis": "rate", "unit": "м³/год",
             "items": [{"code": "BOILER", "name": "Котельня цеху", "value": 41, "share": 1.0, "quality": "measured"},
                       {"code": "DRY-1", "name": "Сушильна камера (газовий пальник)", "value": 4, "share": 0.098, "quality": "estimated"},
                       {"code": "CHP", "name": "КГУ TEDOM (резерв)", "value": 0, "share": 0.0, "quality": "measured"},
                       {"code": "CANTEEN", "name": "Їдальня", "value": 1, "share": 0.024, "quality": "estimated"}],
             "unaccounted": {"value": 0.0, "pct": 0.0}},
    "notes": [{"id": 31, "title": "Розігрів перед зміною починається зарано", "text": "Цех досягає 18 °C о 06:05, а зміна о 07:00. Пізніший старт на 40 хв.",
               "save_uah_month": 6900,
               "actions": [{"code": "heat_schedule", "label": "Змінити графік", "kind": "control", "class": null, "params": {"intent": "heat_schedule_shift"}, "enabled": false},
                           {"code": "open", "label": "Відкрити", "kind": "link", "class": null, "params": {"xmlid": "td_energy_resources.action_td_energy_opportunity", "res_id": 31}, "enabled": true}]}]}
}
```

Правила формы: `tabs[].cost_uah`, `kpis[].note` с ₴, `meta.total.cost_uah`, `notes[].save_uah_month` — только с группой стоимости (иначе ключи отсутствуют, подписи без ₴); числа без свежих данных — `null`, подпись «—»; `chart.series` — 96 значений по **локальным** слотам (R-10); `quality ∈ {measured, estimated}` (оценочные — с точкой в UI); `tone ∈ {good, bad, neutral}`; `capabilities.manage` = группа «Енергетик»; `meta.data_state ∈ {ok, partial, stale}` (как W1: `stale` — нет свежих сигналов ресурса; `partial` — часть счётчиков ресурса без свежих данных). Размер ответа ≤ 25 КБ.

### Формат элемента API-02 `items[]`

`{"id", "code" (rule.code), "resource": "gas", "title", "text", "save_uah_month" (cost), "est_qty_month", "in_plan": bool, "state", "found_at": iso, "request_id": int|null, "actions": [{"code","label","kind","class","params","enabled"}…]}`; `enabled = (kind != 'control') or td.energy.advice._td_control_available()`; если для резерва нет ни одного `enabled`-действия, в конец добавляется `rule.fallback_action`.

## 8. Сервисная часть

### 8.1 Эмулятор `iot_sim` (владелец D; `factory3d/services/iot_sim/`)

Новые устройства (`catalog/devices.yaml`, добавить в конец, не меняя существующие):

| code | role | protocols | unit_id | driver | params |
|---|---|---|---|---|---|
| `GAS-MAIN` | `gas_meter` | P-07 | 74 | `gas` | `{"dry_nom": 6.0, "canteen": 1.0}` |
| `AIR-MAIN` | `air_meter` | P-07 | 75 | `air` | `{"leak": 1.6, "q_ref": 9.8, "load_ref": 66.0, "load_min": 25.0, "drop": 0.1}` |

Новые строки `catalog/signals.csv` и `td_iot_sim/data/td_sim_signal.csv` (формат `n,code,device,protocol,address,dtype,unit,scale,nominal,thresholds,model,status`; `n` — продолжение нумерации (последний 1177 → 1178…1187; при слиянии с W2 `n` пересчитывает менеджер); `status = новый`): 10 сигналов из таблицы 5.4; `nominal`: `infra/gas/m3_total` 31 870, `equipment/BOILER/gas_m3h` 0, `air/flow_m3min` 9,8, `air/m3_total` 6 420, `air/pressure_bar` 6,8, `infra/water/boiler_m3_total` 1 205, `energy/cells/Q1/kvarh_total` 21 500, `…/Q2/…` 18 300.

Модели (файлы `services/iot_sim/iot_sim/models/`): новые `gas.py`, `air.py`; правки `boiler.py` (+3 строки), `water.py`, `meter.py`; **не** правятся `compressor.py`, `chp.py`, `bess.py`, `ats.py`, `transformer.py`, `swb.py` (владелец W2/W1).

| Модель | Фаза | Алгоритм (на тик `dt`, c) |
|---|---|---|
| `boiler` (правка) | как есть | `gas_m3h = heat_kw / (0,914 × 10,5)` (η и теплотворность — константы `BOILER_ETA`, `GAS_KWH_M3`; при `heat_kw = 0` → 0); не влияет на `silo_fill` (D-35). Пример: `heat_kw = 390` → `40,6 м³/ч` |
| `gas` (`GAS-MAIN`, `@register_model("gas")`) | `AGGREGATE` | `q = gas_m3h(BOILER) + infra/chp/gas_m3h + dry + canteen` · `(1 + ε)`; `dry = dry_nom` при `is_working(DRY-1)` (функция `models/water.is_working`), иначе 0; `canteen = 1,0` в будни 08:00–16:00 Киев, иначе 0; `ε = 0,01 + 0,004·(2r−1)` (`r` — детерминированный шум модели); флаг `gas_extra` (сценарий) прибавляет `extra_m3h`; `m3_total += q·dt/3600` с квантом 0,01 м³ (остаток переносится) |
| `air` (`AIR-MAIN`) | `AGGREGATE` | `act = clamp((load − load_min)/(load_ref − load_min), 0, 1,3)`, `load` = `equipment/COMPRESSOR/load`; `flow = leak + leak_extra + (q_ref − leak)·act` (`leak_extra` из флага `air_leak`, м³/мин); `pressure = equipment/COMPRESSOR/pressure_bar − drop`; `m3_total += flow·dt/60`, квант 0,1 норм. м³. Пример: `load=66` → `flow=9,8`; `load=25` (ночь) → `flow=1,6` |
| `water` (правка) | как есть | `boiler_m3_total += 0,0125·max(1, boilers_on)·dt/3600` (`boilers_on = max(0, equipment/BOILER/state − 1)`), квант 0,01 м³; основной расход `q` увеличивается на эту подпитку; флаг `water_leak`: `+extra_m3h` при `23:00 ≤ t < 06:30` |
| `meter` (правка, PM5560 вводов) | как есть | `kvarh_total += |energy/cells/Qn/q_kvar|·dt/3600`, регистр i64 (`scale 0,001`) |

Сценарии (`td_iot_sim/data/td_sim_scenario_resources.xml`, новый файл, группа `energy`, `duration=0` — до остановки): `air_leak` (`params={"leak_extra": 3.0}`, флаг `air_leak`), `gas_overuse` (`{"extra_m3h": 45.0}`, флаг `gas_extra`; BOILER 41 + 45 = 86 > лимита 80 м³/ч), `water_leak` (`{"extra_m3h": 0.5}`, флаг `water_leak`). Тесты эмулятора: `services/iot_sim/tests/unit/test_gas.py`, `test_air.py`, `test_water_boiler.py`, `test_meter_kvarh.py`.

### 8.2 Сборщик

Изменений кода нет: новые источники и сигналы подхватываются из `GET /f3d/telemetry/config` (ETag) за `config_poll_s` (60 с). Нагрузка: +2 источника, 10 сигналов, ≈ 8 600 показаний/сутки после `store_period_s` (5 счётчиков × 1 440 + 5 «газуч» × 288), хранение сырых — 30 сут (`td.telemetry.keep_days`).

## 9. Алгоритмы и правила

Общие обозначения: слот `s` — 15 минут по UTC-сетке (`floor15`); `K_month(L) = weeks_per_month × 7 / L` (перевод суммы за окно `L` суток в месяц); локальные сутки/часы — `Europe/Kyiv`.

### R-01 Единицы и пересчёты (FR-01, FR-05)

1. Из скорости в количество за слот: `qty = rate × rate_hour_factor × 0,25`; обратно: `rate_avg = qty × 4 / rate_hour_factor`. Для `air` (`rate_hour_factor = 60`): `qty` в норм. м³, `rate` в м³/мин: `rate_avg = qty × 4 / 60`.
2. `kwh_eq`: `el`, `heat` → `qty`; `gas` → `qty × kwh_per_unit`; `air`, `water` → 0.
3. `co2_kg = qty × co2_kg_per_unit` — только для потоков `import` и `supply` (R-07), чтобы не считать дважды потребление по веткам.
Пример: газ, слот с `qty = 11,083 м³` → `rate_avg = 44,33 м³/ч`, `kwh_eq = 116,37`, `co2_kg = 21,72`.

### R-02 Цена и стоимость (FR-02, FR-05)

1. `el`: цена и стоимость — в `td.energy.interval` (`price`, `cost`); в `td.energy.usage` для `import` берётся `interval.cost`.
2. `price_source='price'` (газ, вода): `price = td.energy.price._td_price_at(resource, local_date(ts_start))`; `cost = round(qty × price, 2)`; нет цены на дату → `price = 0`, `cost = 0`.
3. `derived_gas` (тепло): `price_heat = price_gas / (kwh_per_unit_gas × boiler_eff)`, `price_gas` по п. 2 на ту же дату; `cost = round(qty × price_heat, 2)`. Пример: `19,80 / (10,5 × 0,91) = 2,0722 ₴/кВт·ч`.
4. `derived_el` (воздух): `cost = Σ cost` строк `td.energy.interval` с `role='consumer'` и `node_id = point.cost_node_id` за тот же слот; `price = cost / qty` при `qty > 0`, иначе 0. Пример: `COMPRESSOR`, 642 кВт·ч × 8,40 = 5 392,80 ₴ за сутки.
5. Ключи `price`/`cost` в API и экспорте — только с `group_td_energy_cost` (M-08).

### R-03 Построение интервала: `counter` и `flow_integrate` (FR-04, FR-05)

Параметры: `gap_max_s` (900), `min_coverage` (0,3).

**`counter`** (не-el: `qty_signal_id`; el-реактивная: `e_react_signal_id`): точки = `td.reading` сигнала за `[t0 − gap_max, t1 + gap_max]`; `CounterSeries.build(points, base=0, reset_tol=td.energy.reset_tol_kwh, max_kw=max_rate или rate_nominal или 1000, gap_max_s)` из `td_energy/tools/counter.py`; `qty = series.delta(t0, t1)`; качество: `measured`→`measured`, `interpolated`→`interpolated`, `reset`→`interpolated`, `None`→`missing` (`qty=0`).

**`flow_integrate`** (`flow_signal_ids`, единицы — `rate_label` ресурса): для слота `[t0, t1)`
1. по каждому сигналу — показания `quality ok` за `[t0 − gap_max, t1 + gap_max]`, по времени; интервалы между соседними показаниями с разрывом `> gap_max_s` — «дыры»;
2. вне дыр функция скорости `f_k(t)` — линейная интерполяция между показаниями; сумма `F(t) = Σ_k f_k(t)` определена только там, где определены все `f_k`;
3. `covered` = длина `[t0, t1)`, где `F` определена; `coverage = covered / 900 с`; интеграл `∫F dt` по `covered` — трапециями по объединённым узлам;
4. при `coverage ≥ min_coverage`: `qty = ∫F dt × rate_hour_factor / 3600 / coverage` (масштабирование на полный слот), `rate_avg` по R-01 п. 1; иначе `qty = 0`, `quality = missing`;
5. качество: `coverage ≥ 0,9` → `measured`; `[min_coverage, 0,9)` → `interpolated`.
Пример 1 (газ, `rate_hour_factor = 1`): показания в 0, 300, 600, 900 с: 40; 44; 46; 46 м³/ч → интеграл = `(40+44)/2·300 + (44+46)/2·300 + (46+46)/2·300 = 12 600 + 13 500 + 13 800 = 39 900` (м³/ч·с) → `qty = 39 900 / 3 600 = 11,083 м³`, `rate_avg = 44,33`, `coverage = 1,0`, `measured`.
Пример 2: показания в 0 и 300 с (следующее — через 1 000 с, дыра `[300, 1300]`) → `coverage = 300/900 = 0,333`, `qty` = интеграл по `[0, 300]` / 0,333, `interpolated`; при единственном показании в слоте и разрыве с обеих сторон > 900 с → `coverage = 0` → `missing`.
Пример 3 (воздух, `rate_hour_factor = 60`): показания 9,6; 9,8; 10,0; 9,8 м³/мин в 0/300/600/900 с → интеграл = `(9,6+9,8)/2·300 + (9,8+10,0)/2·300 + (10,0+9,8)/2·300 = 2 910 + 2 970 + 2 970 = 8 850` (м³/мин·с) → `qty = 8 850 × 60 / 3 600 = 147,5 норм. м³`, `rate_avg = 147,5·4/60 = 9,83 м³/мин`.
Мультисигнальный счётчик (теплота RV): 25 сигналов `heat_kw` суммируются по п. 2; пропажа одного сигнала делает слот `interpolated`/`missing` (A-06).

### R-04 Оценочные методы (`mode='estimate'`; FR-04)

Качество результата всегда `estimated`; слот без исходных данных → `missing`.
1. **`load_share`** (`node_id`, `rate_nominal`): `run_kw = node.p_inst_kw × node.load_factor` (по умолчанию 0,75), `idle_kw = node.p_inst_kw × node.idle_factor` (0,05); `kw = kw_avg` строки `td.energy.interval` (`role='consumer'`, этот узел, этот слот); `active = clamp((kw − idle_kw)/(run_kw − idle_kw), 0, 1)`; `rate = rate_nominal × active`. Пример: EDGE-1 (`p_inst 67,5`: `run 50,625`, `idle 3,375`), `kw_avg = 41` → `active = 0,796` → `rate = 3,0 × 0,796 = 2,39 м³/мин`.
2. **`schedule`**: `rate = params.rate`, если локальный день недели ∈ `params.weekdays` и `params.from_h ≤ local_hour(ts_start) < params.to_h`, иначе 0. Пример: `CANTEEN` газ, вторник 09:30 → 1,0 м³/ч.
3. **`residual`**: `rate = max(0, Σ rate(params.from) − Σ rate(siblings))`, где `siblings` = остальные `consumer`-точки того же ресурса с тем же `parent_id`, что у данной (включая оценённые); любой нужный слот `missing` → `missing`. Пример (вода): `WATER-MAIN 2,1`, `BOILER 0,0125`, `CANTEEN 0,22`, `SPRAY-1 0,3` → `SOCIAL = 2,1 − 0,5325 = 1,5675 м³/ч`.
4. **`gate_loss`** (`state_signal_id`, `params.loss_kw_per_k`, `params.t_in_signal`/`t_out_signal`, по умолчанию `t_in = 18,0`, `t_out = ventilation/totals/outdoor_c`): `open_frac` = доля слота, когда `state_signal ≥ 0,5` (ступенчатое удержание); `ΔT = max(0, t_in − t_out)`; `rate_kw = loss_kw_per_k × ΔT × open_frac`. Пример: `loss_kw_per_k = 3,5`, `open_frac = 0,5`, `ΔT = 11` → `19,25 кВт`. Нужны «сырые» показания (хранятся 30 сут); старше — `missing`.

### R-05 Порядок построения слота, крон, ротация (FR-05)

1. `now = floor15(now_utc)`; для каждого активного счётчика с активным ресурсом и `mode` любого: слоты от `res_last_interval_start + 15 мин` (первый прогон — `now − 24 ч`) до `now` (не включая), максимум 192 на счётчик за прогон; последние **два** построенных слота пересчитываются повторно (уточнение по поздним показаниям).
2. Порядок внутри слота: `counter`/`flow_integrate` → `load_share`/`schedule`/`gate_loss` → `residual` (по глубине зависимости; цикл `residual` невозможен — `_check_estimate` требует `from` без самого себя).
3. Запись — `INSERT … ON CONFLICT (meter_id, metric, ts_start) DO UPDATE` (поля `qty`, `rate_avg`, `kwh_eq`, `price`, `cost`, `quality`, `built_at`); `kwh_eq`, `price`, `cost` — R-01, R-02; `is_backfill=False`; строки `is_backfill=True` живыми данными не перезаписываются: в `DO UPDATE` стоит `WHERE td_energy_res_interval.is_backfill = false`, поэтому при конфликте с синтетической строкой обновление не выполняется (стык «история / живые» остаётся чистым, ТК-03).
4. Электрические вводы с `e_react_signal_id`: тот же цикл создаёт строки `metric='react'` (R-03 `counter`, `price=cost=0`, `kwh_eq=0`).
5. После прогона: `res_last_interval_start`, `bus.tick('kpi')` (один раз).
6. `_cron_rotate`: `DELETE … WHERE ts_start < now − keep_interval_days` пакетами 10 000, не дольше 60 с.
7. Любой сбой по счётчику изолируется `savepoint`; лог `_logger.exception`; остальные счётчики продолжают.

### R-06 Реактивная энергия и tg φ (FR-07, FR-21)

За сутки (киевские) по вводам: `Q = Σ qty` строк `metric='react'`, `P = Σ kwh` строк `td.energy.interval` `role='incomer'` (импорт); `tg φ = Q / P` (`P ≤ 0` → `null`); `cos φ = 1/√(1+tg²)`. «Ризик доплати» (D-44): `tariff.tg_phi_limit > 0` и `tg φ > tg_phi_limit`; `excess_kvarh = max(0, Q − tg_phi_limit × P)`; `penalty = tariff._td_react_penalty(excess_kvarh)`.
Пример: `Q = 2 514 квар·ч`, `P = 6 284 кВт·ч` → `tg φ = 0,40`, `cos φ = 0,928`; при `tg_phi_limit = 0,30`: `excess = 2 514 − 1 885,2 = 628,8`; при `react_rate = 0,24` → `150,9 ₴`.

### R-07 Семантика `td.energy.usage` (FR-06)

| flow | Источник | qty | cost | co2 | Входит в «разом» |
|---|---|---|---|---|---|
| `import` | `td.energy.interval`, `role='incomer'` | `kwh` | `interval.cost` | `kwh × co2(el)` | да (затраты на покупку энергии) |
| `export` | то же, `kwh_export > 0` | `kwh_export` | 0 | 0 | нет |
| `generation` | `role='generation'` | `kwh` | 0 | 0 | нет |
| `load` | `role='feeder'` | `kwh` | `interval.cost` | 0 | нет (потребление заводом; не суммировать с `import`) |
| `supply` | `res.interval`, `metric='main'`, точка `kind='source'` (и ресурс без источника: `consumer`, если у ресурса нет `source`-точек) | `qty` | `cost` (R-02) | `qty × co2` | да (если `resource.is_derived = False`) |
| `branch` | прочие точки `res.interval` (`metric='main'`) | `qty` | `cost` | 0 | нет |

Правило для потребителей W4: «стоимость энергии» = `Σ cost` по `import` и `supply` ресурсов с `in_energy_cost`; «потребление электроэнергии заводом» = `Σ qty` по `load`; «из сети» = `Σ qty` по `import`.

### R-08 Живые значения и «сегодня» (FR-08, FR-09)

1. Один `search_read` `td.signal` по списку кодов, нужных вкладке; значение «свежее», если `last_ts ≥ now − max(3·period_s, 120 с)`, иначе `null`.
2. «Сегодня» = `Σ` строк `res.interval` с `day = сегодня (Киев)` по `metric='main'` + «неполный слот»: те же правила R-03 на `[floor15(now), now)` (если прошло < 60 с — не добавляется; `coverage` считается относительно прошедшего времени).
3. Электричество («Електрика») берётся из W1: `td.energy.dashboard.get_pult(period="now", parts=["kpis","profile","side"])` — `kpis.grid`, `kpis.energy`, `kpis.generation`, `profile.grid`, `profile.peak`, `foot.export_kwh`, `top`, `meta.contract_kw` (контракт C-03); дублирования расчётов нет.
4. `data_state`: `stale` — нет свежих сигналов ни у одного счётчика ресурса; `partial` — часть счётчиков без свежих данных; иначе `ok`. Отсутствие данных **не** вызывает исключений.

### R-09 KPI по ресурсам (FR-09)

Каждый KPI: `{id, label, value, unit, note, tone, quality}`. Округление — R-25.

| Ресурс | KPI | Формула | note / tone |
|---|---|---|---|
| el | `grid_now` | `kpis.grid.kw` (W1 R-27 п. 5) | «{pct} % договірної {contract} кВт»; `bad`, если `pct ≥ tariff.peak_warn_pct` |
| el | `today` | `kpis.energy.kwh` (импорт с 00:00) | «{cost} ₴ · {price} ₴/кВт·год» (cost-группа); `neutral` |
| el | `generation` | `Σ kwh` `role='generation'` за сегодня + неполный слот | «СЕС {pv %} % · КГУ {chp %} % · частка {gen/load %} %», `gen/load` = генерация / `Σ feeder`; `good` |
| el | `reactive` | `Q` кварч (R-06) | «tg φ {tg}» + « · ризик доплати» (D-44); `bad` при риске; нет `react`-строк → `null` |
| gas | `rate` | `infra/gas/flow_m3h` (свежий), иначе последний `rate_avg` источника | «котельня {top_name} · КГУ {стоїть\|працює}», `top_name` — потребитель с максимальной скоростью, КГУ — `infra/chp/state` (`running` → «працює») |
| gas | `today` | `Σ qty` источника (R-08 п. 2) | «{cost} ₴ · {price} ₴/м³» |
| gas | `limit` | `resource.daily_limit` | «використано {today/limit} %»; `bad` при ≥ 90 % |
| gas | `eff` | `100 × Σ qty(HM-BOILER, сегодня) / (Σ qty(GM-BOILER, сегодня) × kwh_per_unit)`; нет теплосчётчика котельной → `null` | «норма ≥ {boiler_eff_norm} %»; `good` при ≥ нормы; `quality=estimated` |
| heat | `power` | `Σ` скорости `source`-точек сейчас | ядро: «—»; мост: «подача {t} °C · зворот {t} °C» |
| heat | `today` | `Σ qty` источников | `source_note` «теплобаланс BMS» |
| heat | `indoor`, `recovery` | хук `_td_heat_kpis` (мост, R-B2) | ядро — не выводятся |
| air | `rate` | `air/flow_m3min` | «тиск {air/pressure_bar} бар · уставка {setpoint}» (сигнал `air/setpoint_bar`, иначе параметр) |
| air | `spec` | `energy/consumers/COMPRESSOR/p_now / flow`, при `flow < 1` → `null` | «норма ≤ {air_spec_norm}»; `good` ≤ нормы. Пример: `52 / 9,8 = 5,31` |
| air | `today_el` | `Σ kwh` узла `cost_node_id` за сегодня | «{cost} ₴» (cost-группа) |
| air | `night_leak` | `night_rate` (R-09 п. ниже) | «{share} % від денної витрати»; `bad`, если `share > 10 %` |
| water | `rate` | `infra/water/flow_m3h` | «основний ввід» |
| water | `today` | `Σ qty` источника | «{cost} ₴» |
| water | `night` | `night_rate` | «норма ≤ {water_night_norm}»; `good` ≤ нормы |
| water | `boiler` | `Σ qty` `WM-BOILER` за сегодня | «норма ≤ {boiler_makeup_norm} м³/добу»; `good` ≤ нормы |

**`night_rate`**: окно `[вчера night_from, сегодня night_to)` (если сейчас раньше `night_to` — до `now`); `night_rate = min rate_avg` слотов окна источника с `quality != missing`, при покрытии окна < 70 % слотов → `null`. **`day_mean`**: среднее `rate_avg` слотов внутри смен (R-21) сегодня; если смен сегодня ещё не было — вчерашний рабочий день. `share = night_rate / day_mean × 100`.
Фикстуры AC: см. разд. 12 (числа макета).

### R-10 График суток (FR-08)

1. `series[i]`, `i = 0…95` — **локальные** слоты (R-21 `local_slot_index`, добавка/пропуск слота в сутки перехода на летнее/зимнее время — как W1 A-30); значение — сумма `rate_avg` по источникам ресурса; слот без данных → `null`; слоты после `now_slot` → `null`; слот `now_slot` — живое значение (R-08).
2. `limit`: `el` → `tariff.contract_kw` на момент `now`; `fixed` → `rate_limit`; иначе `null`.
3. `y_max = 3 × step`, `step = nice(1,1 × max(limit, max(series)) / 3)`, где `nice(x)` — наименьшее из `{1; 1,5; 2; 2,5; 3; 4; 5; 6; 7,5; 10}·10^k`, не меньшее `x`; `ticks = [step, 2·step, 3·step]`. Примеры: газ (макс 46, лимит 80): `1,1·80/3 = 29,3 → 30 → y_max 90`; электричество (лимит 800, пик 631): `293 → 300 → 900`; воздух (пик 9,8): `3,59 → 4 → 12`; вода (0,42): `0,154 → 0,2 → 0,6`.
4. `chart_note` — подстановка `{limit}`, `{contract}`, `{capacity}` (последний — хук `_td_heat_chart_note`, иначе подстрока «котли {capacity} кВт» удаляется вместе с « · »).
5. `foot` (D-33) = `foot_template.format(**vars)`; `vars`: `peak_kw`/`peak_time` (максимум `series` с локальным временем слота), `export_sentence` (el: если `foot.export_kwh > 0` — « З {export_time} частина енергії СЕС віддавалась у мережу ({export_kwh} кВт·год).», иначе «»), `night`, `day` (R-09), `top_name`/`top_share` (тепло: потребитель с максимальной скоростью и доля от `Σ`), `leak_sentence` (воздух: `share > 10 %` → «Вночі витрата {night} м³/хв — це витоки в мережі.», иначе «Нічна витрата {night} м³/хв в межах норми.»), `norm_sentence` (вода: `night ≤ norm` → «в нормі», иначе «вища за норму {norm}»). Если для подстановки нет данных — вся фраза опускается.

### R-11 Список «Споживачі», баланс (FR-08, FR-10)

1. Элементы — активные точки `kind='consumer'` ресурса; `value`: `basis='rate'` — скорость в последнем построенном слоте (для измеряемых с живым сигналом — живое значение; для `load_share` — расчёт по живой `p_now` узла); `basis='qty_day'` — `Σ qty` за сегодня; сортировка по убыванию, максимум 8; значения 0 показываются.
2. `share = value / max(value)` (длина полосы, как в макете); `quality` — по методу (`measured` / `estimated`).
3. Баланс: `unaccounted = Σ rate(source) − Σ rate(consumer)`, `pct = unaccounted / Σ rate(source) × 100`; если нет `source`-точки — не считается (`null`). Событий и тревог нет (A-14); `pct < −5 %` (потребители в сумме больше ввода) добавляет в `list.unaccounted` флаг `inconsistent: true` (UI — предупреждающая подпись «Оцінка перевищує облік»).

### R-12 Вкладки, подписи и итог (FR-08; D-31, D-32, D-48)

`tabs` = активные ресурсы с хотя бы одним активным счётчиком, по `sequence`. `rate` — значение KPI `rate` (el — `kpis.grid.kw`). `sub = "{rate} {rate_unit}"` + (« · {cost} ₴», если `show_tab_cost` и есть группа стоимости, иначе « · {source_note}», если задан). Стоимость вкладки за сегодня: el — `kpis.energy.cost_uah`; `price`-ресурсы — `Σ cost` источника; `derived_el` — R-02 п. 4; `derived_gas` — не показывается (D-32). `meta.total.cost_uah = Σ cost_uah` вкладок с `is_derived=False`; `total.text` — формат D-31.

### R-13 Жизненный цикл резерва (FR-13, FR-15)

`_cron_detect` (и `action_run`): для каждого `enabled` правила, у которого нашёлся метод детектора (`_td_detector_methods()`; нет метода — `last_error='Детектор недоступний'`, пропуск):
1. `findings = detector(rule, now)` (R-14); исключение → `last_error`, остальные правила продолжаются;
2. фильтр: `est_saving_month ≥ min_saving_uah`; находка отбрасывается, если по тому же `dedup_key` есть запись `dismissed` с `resolved_at > now − dismiss_days` или `done` с `resolved_at > now − cooldown_days`;
3. upsert по `dedup_key` среди `state='open'`: есть — обновить `title`, `text`, `est_*`, `evidence`, `actions`, `last_seen_at` (**`in_plan` и `plan_*` сохраняются**); нет — создать (`found_at = last_seen_at = now`);
4. открытые резервы правила, чей `dedup_key` не вернулся, → `expired` (`resolved_at = now`); `in_plan` сохраняется как история;
5. `actions` собираются из `rule.actions` + `control` (если задан `control_intent`: `{"code": "control", "label": rule.control_label, "kind": "control", "class": null, "params": {"intent": rule.control_intent}}`) + `ticket`-параметры: `description` содержит тег `[OPP-<id>]` (после `create` — переформатируется);
6. `_td_link_requests()`: заявки `maintenance.request` с тегом `[OPP-<id>]` в описании → `request_id`; если заявка в стадии `done` (`stage_id.done`) — резерв → `done` (`result_note = "Заявку закрито"`, `resolved_by = заявка.user_id`); при выполнении действия `ticket` через мастер W1 заявка появляется с тегом (мастер копирует `description`);
7. `bus.tick('advice')` не вызывается (банер Пульта — отдельный слот W1); экран ресурсов обновляется по `kpi`.
`action_plan_toggle`: `in_plan := not in_plan` (для `state='open'`), `plan_user_id`, `plan_date`; `message_post` в чаттер «Додано до плану / Прибрано з плану».
`action_done(note)` → `state='done'`, `in_plan` не сбрасывается; `action_dismiss` → `dismissed`.

### R-14 Общие правила детекторов (FR-14)

- Сигнатура: `detect(env, rule, now) -> list[dict]`; элемент `{"dedup_key", "title", "text", "est_saving_month", "est_qty_month", "evidence", "node_code", "point_code"}`; `text` ≤ 400 символов, числа форматируются по R-25.
- Окно: `L = rule.lookback_days` **полных** киевских суток, заканчивающихся вчера; недостаточно данных (менее 70 % слотов нужных рядов или менее 3 суток) → `[]` без ошибки (`last_count=0`).
- Цена энергии: взвешенная `Σ(kwh·price) / Σ kwh` по затронутым слотам (поле `price` интервалов; нет цены — 0 → находка отбрасывается).
- Месяц: `est_qty_month = qty_window × K_month(L)`; `est_saving_month = est_qty_month × price`; округление `round(x, 0)` для ₴.
- `params_schema` каждого правила — разд. R-15…R-20, R-B2…R-B4; все пороги редактируются в V-08 (`group_td_energy_manager`).
- `evidence` — числа, из которых получена оценка (для проверки инженером), без персональных данных.

### R-15 `vent_offshift` — «Вентиляція працює поза змінами» (вкладка el; FR-14)

Параметры: `group="vent"`, `ratio_min=0,35`, `target_ratio=0,30`; `lookback_days=7`, `min_saving_uah=1000`, `control_intent="vent_night_mode"`.
1. Узлы: `td.energy.node` `kind='consumer'`, `group = params.group`; нет — `[]`.
2. По слотам окна: `kw = Σ kwh × 4` этих узлов (`td.energy.interval`, `role='consumer'`, `quality != missing`).
3. Разбивка по R-21: `day_level` = среднее `kw` внутри смен (нужен хотя бы один рабочий день), `off_level` = среднее `kw` вне смен.
4. `off_level < ratio_min × day_level` → `[]`.
5. `saving_kw = off_level − target_ratio × day_level`; `off_hours = (число слотов вне смен)/4`; `saving_kwh_window = saving_kw × off_hours`; `est_qty_month = saving_kwh_window × K_month`; цена — по слотам вне смен.
6. `dedup_key = "vent_offshift:*"`; заголовок «Вентиляція працює поза змінами»; `evidence = {day_level_kw, off_level_kw, ratio, off_hours, nodes}`.
Фикстура: `L=7`, `day_level=100 кВт`, `off_level=50 кВт` (`ratio 0,5`), `off_hours=88`, цена вне смен `6,00` → `saving_kw = 50 − 30 = 20`; `saving_kwh_window = 1 760`; `est_qty_month = 1 760 × 4,33 = 7 620,8 кВт·ч`; `est_saving = 45 725 ₴`.

### R-16 `idle_machines` — «Холостий хід верстатів під напругою» (el)

Параметры: `idle_share_min=0,05`, `recoverable=0,70`; `lookback_days=7`, `min_saving_uah=1000`; действие `link` на `td_energy.action_td_energy_alloc_pivot` («Звіт по РЦ»).
1. `td.energy.alloc` за дни окна: `idle_kwh = Σ kwh` (`kind='idle'`), `rc_kwh = Σ kwh` (`kind in (direct, idle)`); `rc_kwh = 0` → `[]`.
2. `share = idle_kwh/rc_kwh`; `< idle_share_min` → `[]`.
3. `est_qty_month = idle_kwh × K_month × recoverable`; цена = `Σ alloc.cost / Σ alloc.kwh` по `idle`-строкам.
4. `evidence = {idle_kwh, rc_kwh, share, top_nodes: [3 узла с наибольшим idle]}`; текст «Між завданнями верстати стоять увімкненими: {idle_kwh} кВт·год за {L} діб, найбільше {top}.»
Фикстура: `idle_kwh=410`, `rc_kwh=6 000` (`share 6,8 %`), `price 8,40`, `L=7` → `est_qty_month = 410 × 4,33 × 0,7 = 1 242,7 кВт·ч`; `est_saving = 10 439 ₴`.

### R-17 `air_leaks` — «Витоки стисненого повітря» (air)

Параметры: `ratio_min=0,10`, `min_flow=0,2` м³/мин, `reducible=0,65`; `lookback_days=7`, `min_saving_uah=1000`; действие `ticket` (`node_code="COMPRESSOR"`, описание «Пошук витоків стисненого повітря [OPP-<id>]»).
1. Источник — счётчик `source`-точки воздуха; для каждой ночи окна — `night_min_d` = минимум `rate_avg` слотов ночного окна (покрытие ≥ 70 %).
2. `night_flow = медиана(night_min_d)` (не менее 3 ночей); `day_flow` = среднее `rate_avg` внутри смен.
3. Находка, если `night_flow ≥ min_flow` и `night_flow/day_flow ≥ ratio_min`.
4. `spec = Σ kwh(cost_node) / Σ qty(air main)` за окно (кВт·ч на норм. м³; нет данных — `0,0883` = 5,3/60); `saved_flow = night_flow × reducible`; `qty_month_m3 = saved_flow × 60 × 730` (утечки работают круглосуточно); `est_qty_month = qty_month_m3 × spec` (кВт·ч); цена — `Σ cost / Σ kwh` узла `cost_node`.
5. `evidence = {night_flow, day_flow, share_pct, spec, reducible}`.
Фикстура: `night_flow=1,6`, `day_flow=10,0` (16 %), `spec=0,0883`, цена `8,40` → `saved_flow = 1,04`; `qty_month_m3 = 45 552`; `est_qty_month = 4 022,2 кВт·ч`; `est_saving = 33 787 ₴`.

### R-18 `air_pressure` — «Тиск стисненого повітря завищений» (air)

Параметры: `margin_bar=0,3`, `k_per_bar=0,07` (7 %/бар), `min_save_bar=0,2`; `control_intent="air_pressure_setpoint"`.
1. `p_set` = свежий `air/setpoint_bar` (контракт C-02), иначе параметр `air_setpoint_bar`.
2. `p_need = max(min_pressure_bar)` по активным `consumer`-точкам с `min_pressure_bar > 0`, чья средняя `rate_avg` за окно `> 5 %` от `rate_nominal` (реально работают).
3. `p_target = p_need + margin_bar`; `dp = p_set − p_target`; `dp < min_save_bar` → `[]`.
4. `kwh_window = Σ kwh` узла `cost_node_id` за окно; `est_qty_month = kwh_window × K_month × k_per_bar × dp`; цена — узла.
5. Текст: «Найвибагливіший споживач ({name}) потребує {p_need} бар; уставка {p_set}. Можна знизити до {p_target} бар.»
Фикстура: `p_set=7,0`, `p_need=6,2 (PRESS-1)`, `p_target=6,5`, `dp=0,5`, `kwh_window=4 494` (7 × 642), цена `8,40` → `est_qty_month = 4 494 × 4,33 × 0,07 × 0,5 = 681,0 кВт·ч`; `est_saving = 5 721 ₴`.

### R-19 `react_section` — «Реактивна енергія на секції» (el)

Включается только при `tariff.tg_phi_limit > 0` и `react_rate > 0` (Q-03; иначе `[]` и `last_error='Немає параметрів доплати в тарифі'`). Параметры: `cos_target=0,92`, `min_hours_day=2,0`; `lookback_days=7`, `min_saving_uah=500`; действие — `link` на открытую заявку ТО по узлу `PFC-{s}` (`maintenance.hr_equipment_request_action`, `res_id`), иначе `ticket` (`node_code="PFC-{s}"`).
1. По секциям `s ∈ {1, 2}`: показания `energy/sections/S{s}/cos_phi` (сырые, окно ≤ 30 сут): `h_low_d` — часы суток с `cos < cos_target` (ступенчатое удержание); `h_low_avg = mean(h_low_d)`; `< min_hours_day` → секция пропускается.
2. По суткам: `P_d` = интеграл `energy/sections/S{s}/p_kw`, `Q_d` = интеграл `…/q_kvar` (кВт·ч, квар·ч; расчёт после компенсации — W1 R-35); `excess_d = max(0, Q_d − tg_phi_limit × P_d)`.
3. `penalty_month = mean(excess_d) × 30 × react_rate`; `est_saving_month = penalty_month`, `est_qty_month = mean(excess_d) × 30` (квар·ч).
4. `dedup_key = "react_section:S{s}"`; текст «cos φ секції {s} — {cos_min}. Компенсація PFC-{s} не досягає цілі.».
Фикстура: `P_d=3 000`, `Q_d=1 650` (`tg 0,55`), `tg_phi_limit=0,40`, `react_rate=0,24` → `excess_d = 450`; `est_qty_month = 13 500 квар·ч`; `est_saving = 3 240 ₴`.

### R-20 `pv_export` — «Експорт СЕС дешевше закупівлі» (el)

Параметры: `min_export_kw=10`, `capture=1,0`; `lookback_days=7`, `min_saving_uah=500`; `control_intent="pv_self_consumption"`, запасное действие — `link` на `td_energy.action_td_energy_generation`.
1. Слоты вводов, где `kwh_export × 4 ≥ min_export_kw`; `E = Σ kwh_export`.
2. `buy` — взвешенная цена слотов (`interval.price` ввода), `export_price = tariff.export_price` на слоты; `diff = buy − export_price`; `diff ≤ 0` → `[]`.
3. `est_qty_month = E × K_month × capture`; `est_saving = est_qty_month × diff`.
Фикстура: `E=118 кВт·ч` за 7 сут, `buy=8,40`, `export=2,00` → `est_qty_month = 118 × 4,33 = 510,9 кВт·ч`; `est_saving = 510,9 × 6,40 = 3 270 ₴`.

### R-21 Окна смен `tools/shifts.py` (FR-22; контракт C-01 для W4)

1. `load_windows(env)`: календарь — `td.energy.shift_calendar_id` (`resource.calendar`); строки `attendance_ids` (`display_type` пусто, `day_period != 'lunch'`) группируются по `(dayofweek, name)`; окно = `[min(hour_from), max(hour_to)]`; если у календаря стандартные имена строк («Monday Morning» и т. п.) — все строки дня образуют одну смену «Зміна»; календарь не задан или пуст — умолчание: пн–пт «Зміна 1» 07:00–16:00 и «Зміна 2» 16:00–23:00 (по макету, Q-23).
2. API: `shift_of(local_dt) -> str | None`, `is_shift(local_dt) -> bool`, `windows_for(date) -> [(name, dt_from, dt_to)]`, `night_window(date) -> (dt_from, dt_to)` по `night_from_h`, `night_to_h`.
3. Все границы — местное время; переход DST учитывается через `tools/dates.to_utc`.
Пример (умолчание): вторник 15:59 → «Зміна 1»; 16:00 → «Зміна 2»; 23:00 → `None`; суббота 10:00 → `None`.

### R-22 Backfill ресурсов `td.energy.res.interval._td_backfill` (FR-18)

Назначение: дать экрану W3 и аналитике W4 историю за `days` суток (по умолчанию 90, максимум 400) в стыке с электрическим backfill W1 (R-36). **Предусловие:** электрический `_td_backfill` за тот же период выполнен (оценочные точки берут нагрузку из `td.energy.interval`); иначе оценочные слоты — `missing`, в лог — предупреждение.
1. Параметры: `days`, `until` (по умолчанию `ceil15` первого показания `td.reading` сигналов ресурсов, иначе `floor15(now)`), `seed` (детерминизм: `rnd(seed, *key)` из `td_energy/tools/backfill.py`), `purge` (удалить `is_backfill=True` в диапазоне и выйти), `resources` (коды; по умолчанию все активные).
2. Генераторы (`act(t) = clamp((P(t) − 210)/(667 − 210), 0, 1,3)`, `P(t)` — `backfill.target_p`; `sd(d) = clamp(0,5 + 0,5·cos(2π(doy − 15)/365), 0,1, 1)` — сезонность отопления):
   - газ: `heat_need = sd × (0,35 + 0,65·shift(t)) × 390 кВт` (+30 % при разогреве 05:30–07:00); `GM-BOILER = heat_boiler/(10,5·0,914)`, где `heat_boiler = max(0, heat_need − heat_chp)`; `GM-CHP = 109 м³/ч`, когда КГУ работает (тот же критерий, что R-36 п. 6: 10 % будних дней 16:00–19:00); `GM-MAIN = (GM-BOILER + GM-CHP + оценки DRY-1, CANTEEN) × (1 + ε)`, `ε = 0,01 + 0,004·(2·rnd − 1)`;
   - воздух: `AM-MAIN = leak·(1 + 0,05·rnd) + (9,8 − leak)·act`, `leak = 1,6`; оценочные потребители — R-04;
   - вода: `WM-MAIN = (2,1 если смена иначе 0,3) + 1,5·paint(t) + 0,0125`, `paint = 1`, когда `active(SPRAY-1) ≥ 0,5`; `WM-BOILER = 0,0125`; счётчики-накопители с квантом 0,01 м³;
   - реактивная энергия: `P_s` из `td.energy.interval` вводов, `cos_s = 0,95` (секция 1) и `0,88` (секция 2) после компенсации, `Q = P·tan(acos cos_s)`;
   - тепло — хук `_td_backfill_extra(plan, seed, since, until)` (в ядре пуст, мост — R-B5).
3. Запись: сутки за сутками, пакеты ≤ 5 000, `INSERT … ON CONFLICT (meter_id, metric, ts_start) DO NOTHING`; `is_backfill=True`, `quality='measured'` для `counter`/`flow_integrate`-подобных рядов и `estimated` для оценочных; `res_last_interval_start = max(существующее, последний слот)` — только если нет живых слотов позже (как R-36 п. 10).
4. Возвращает `{"meters": n, "slots": n, "rows": n, "skipped": n, "since": iso, "until": iso, "seconds": f}`.
5. Ограничения: 90 суток × 24 счётчика × 96 ≈ 207 000 строк, ≤ 60 с; 400 суток ≈ 920 000 строк, ≤ 300 с, ≤ 400 МБ RAM (ТП-04).
6. Проверяемые свойства: Σ `GM-MAIN` ≈ Σ ветвей ± 3 %; суточный расход воздуха коррелирует с `COMPRESSOR` кВт·ч (ρ ≥ 0,9); ночной минимум воздуха ≈ 1,6 м³/мин; детерминизм; идемпотентность; `purge` не трогает `is_backfill=False`.

### R-23 Эмулятор — см. разд. 8.1

### R-24 Экспорт xlsx (API-07; FR-12)

1. Параметры: `day` (обязательно, `YYYY-MM-DD`, не в будущем), `day_to` (по умолчанию = `day`), `resources` (по умолчанию все активные); `Σ суток ≤ export_max_days`.
2. Источник — `td.energy.usage` (`sudo()`) за `[day, day_to]` и выбранные ресурсы, сортировка `ts_start, resource, flow`; электрические потоки — `import`, `export`, `generation`, `load`.
3. Лист «Ресурси»: колонки «Ресурс», «Потік», «Об'єкт» (код вузла/точки), «Початок (Київ)», «Кількість», «Одиниця», «Ціна, ₴», «Вартість, ₴», «Якість»; колонки цены/стоимости — только с `group_td_energy_cost`. Лист «Підсумок»: `Σ qty/cost` по ресурсу и потоку.
4. Формирование `xlsxwriter` (`constant_memory`); строк > 200 000 → `413`. Нет данных — файл с заголовками и пустым листом.
5. Время в ячейках — локальное (Киев), форматирование `dd.mm.yyyy hh:mm`.

### R-25 Форматы чисел в ответах API

| Величина | Правило |
|---|---|
| кВт, кВт·ч, ₴ | целое (`round`) |
| м³/ч, м³/мин, м³/ч в списках | `≥ 10` → целое; `< 10` → 1 знак; вода `< 1` → 2 знака (0,05) |
| м³ за сутки | `≥ 100` → целое; иначе 1 знак |
| `eff`, `share`, `%` | 1 знак |
| `tg φ`, `cos φ` | 2 знака |
Значения в JSON — числа (не строки); форматирование строк `note` — `fmt_dec`/`fmt_int` из `td_energy/tools` (запятая — десятичный разделитель, узкий пробел — разделитель тысяч).

## 10. Состояния и переходы

| Объект | Состояния | Переходы (кто) |
|---|---|---|
| `td.energy.opportunity.state` | `open → done / dismissed / expired` | `action_done`, `action_dismiss` (manager), `_cron_detect` (истечение), `_td_link_requests` (заявка закрыта → `done`); `done`/`dismissed` повторно открываются **созданием новой записи** после `cooldown_days`/`dismiss_days` |
| `td.energy.opportunity.in_plan` | `False ⇄ True` | `action_plan_toggle` (manager) только для `state='open'`; при истечении сохраняется |
| `td.energy.res.interval.quality` | `measured / interpolated / estimated / missing` | пересчёт последних двух слотов (R-05) может улучшить качество; `is_backfill` строки не перезаписываются |
| `td.energy.meter.mode` | `counter / flow_integrate / estimate` | смена режима — вручную manager; смена очищает `res_last_interval_start` (пересборка последних 24 ч) |

## 11. Обработка ошибок

- **Нет данных / несвежие сигналы:** значения `null`, `data_state` `partial|stale`, UI «—»; методы **не** бросают исключений из-за отсутствия данных (как W1).
- **Нет цены:** `price=0`, `cost=0`; в `res.config.settings` счётчик «ресурсів без ціни»; KPI без суммы ₴ не обнуляются (показывается «—»).
- **Нет сигнала `air/setpoint_bar`:** используется `td.energy_resources.air_setpoint_bar`, в KPI примечание «уставка {x} (задана в налаштуваннях)».
- **Сбой одной точки/счётчика:** изолируется `savepoint`, лог `_logger.exception`, остальные продолжаются; `get_resources` по частям: ошибка в `kpis`/`chart`/`list`/`notes` не ломает остальные (часть → `{"error": "…"}`, UI «Не вдалося завантажити: …»).
- **Дубликаты:** `UNIQUE(meter_id, metric, ts_start)`; гонка двух кронов — `ON CONFLICT`.
- **Часовые пояса:** хранение UTC naive; `day`, `hour_local`, смены, ночи — Киев; сутки 23/25 ч — по локальным слотам (W1 A-30).
- **Стык «история / живые данные»:** живые строки не перезаписывают синтетические; после `until` backfill слоты строит только крон; ТК-03 проверяет отсутствие дыр.
- **Удалённая точка/счётчик:** `td.energy.res.interval` — `ondelete=cascade` по счётчику; резервы ссылаются на `point_id` с `set null`.
- **Многокомпанейность:** `company_id` у точек, цен, правил, резервов (record rules 4.3); счётчики наследуют `company_id` узла/точки.
- **Мост отсутствует:** хуки возвращают пустое; вкладка «Тепло» работает на счётчиках, если они заданы вручную.

## 12. Acceptance Criteria

Колонка «Тип»: UT (в т. ч. HttpCase и pytest эмулятора) / UT-JS / TC / MAN. Все `odoo`-тесты — `post_install`, теги `-at_install`, `td`, `td_w3`. Фикстуры — разд. 13.0. Числа в фикстурах взяты из макета `Resources.dc.html` (14:20) там, где арифметика макета самосогласованна.

### 12.1 `td_energy_resources` — AC-01…AC-64

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given установленный модуль; When читаем `td.energy.resource`; Then 5 записей (`resource_el|gas|heat|air|water`) со значениями таблицы 5.2: `rate_hour_factor` air = 60, остальные 1; `kwh_per_unit` gas = 10,5; `co2_kg_per_unit` el 0,37 / gas 1,96; `is_derived` у heat и air; `in_energy_cost` у el и gas; `list_basis='qty_day'` у water | UT |
| AC-02 | FR-01 | Given справочник; When `code` дублируется / `rate_hour_factor ≤ 0` / `unlink` записи `el` / второй активный `el`; Then `ValidationError` / `ValidationError` / `UserError("Ресурс «Електрика» видаляти не можна.")` / `ValidationError("Ресурс «Електрика» має бути єдиним.")` | UT |
| AC-03 | FR-02 | Given цена газа 19,80 с 2025-01-01; When `td.energy.price.create` для `el`; Then `ValidationError("Ціни електрики задаються в тарифі.")`; пересекающийся период той же компании — `ValidationError`; `_td_price_at(gas, 2026-10-17) = 19,80`; дата вне периодов → `0.0`; `heat` при `boiler_eff = 0,91` → `2,0722` (допуск 1e-4) | UT |
| AC-04 | FR-03 | Given точки; When дубль `(resource, company, code)`, `parent_id` другого ресурса, цикл родителей, `estimate_method` без обязательных `params` (`load_share` без `node_id`, `schedule` без `from_h`, `residual` без `from`, `gate_loss` без `state_signal_id`); Then `ValidationError`/`IntegrityError` с текстами M-03 | UT |
| AC-05 | FR-04 | Given копия демо-БД (67 электрических счётчиков, N интервалов, M балансов); When `-u td_energy_resources`; Then у всех 67 `resource_id = el`, `mode = 'counter'`; `count(td.energy.interval)` и `count(td.energy.balance)` не изменились; повторный `-u` — без изменений; `td_energy` 142 + W1 тестов зелёные **и при наличии 16 неэлектрических счётчиков** (`cron_td_energy_live` не падает и не меняет их `data_state` на ложные события) | UT + DEPLOY_TEST |
| AC-06 | FR-04 | Given счётчики; When создаём: `el` без `node_id`; не-`el` без `point_id`; не-`el` с `e_import_signal_id`; `counter` без `qty_signal_id`; `flow_integrate` без `flow_signal_ids`; `estimate` у точки без метода; `e_react_signal_id` на `role='feeder'`; Then `ValidationError` с текстами M-04. Регрессия: счётчик газа (с `qty_signal_id`) **не** попадает в `td.energy.interval._cron_build` и `tools/backfill.Plan.meters` | UT |
| AC-07 | FR-05 | Given `td.energy.res.interval`; When вставляем дубль `(meter, metric, ts_start)`; Then нарушение `UNIQUE`; индексы `(day, resource_id)` и `(point_id, ts_start)` есть в `pg_indexes` | UT |
| AC-08 | FR-05 | Given показания газа 0/300/600/900 с = 40/44/46/46 м³/ч; When `integrate.flow(slot)`; Then `qty = 11,083`, `rate_avg = 44,33`, `coverage = 1,0`, `quality = measured` (допуск 1e-3) | UT |
| AC-09 | FR-05 | Given показания в 0 и 300 с (следующее через 1 000 с); Then `coverage = 0,333`, `interpolated`; единственное показание с разрывами > 900 с — `missing`, `qty = 0`. Воздух: 9,6/9,8/10,0/9,8 м³/мин → `qty = 147,5`, `rate_avg = 9,83` | UT |
| AC-10 | FR-05 | Given `counter` газа с показаниями 100,00 → 100,35 → 100,70; When слот; Then `qty = 0,35`; сброс (100,70 → 0,10) — `interpolated`, `qty ≥ 0`; разрыв > `gap_max_s` — `interpolated` | UT |
| AC-11 | FR-04 | Given счётчик теплоты из 25 сигналов (по 9,1 кВт); When слот; Then `rate_avg = 227,5`; один сигнал без показаний — `interpolated`/`missing` по `coverage` | UT |
| AC-12 | FR-04 | Given EDGE-1 (`p_inst 67,5`, `load_factor 0,75`, `idle_factor 0,05`), `kw_avg = 41`, `rate_nominal = 3,0`; When `load_share`; Then `rate = 2,39` (`estimated`); нет интервала узла → `missing`; `kw_avg` выше `run_kw` → `active = 1`, ниже `idle_kw` → 0 | UT |
| AC-13 | FR-04 | Given `schedule` `{"from_h":8,"to_h":16,"weekdays":[0..4],"rate":1.0}`; When вторник 09:30 → 1,0; суббота → 0; 16:00 → 0 (правая граница исключается) | UT |
| AC-14 | FR-04 | Given вода: `WATER-MAIN 2,1`, `BOILER 0,0125`, `CANTEEN 0,22`, `SPRAY-1 0,3`; When `residual` `SOCIAL`; Then `1,5675`; если сумма ветвей > ввода — `0`; сиблинг `missing` → `missing` | UT |
| AC-15 | FR-04 | Given `loss_kw_per_k = 3,5`, `state_signal` открыт половину слота, `t_in = 18`, `t_out = 7`; Then `rate_kw = 19,25`; нет сырых показаний за слот → `missing` | UT |
| AC-16 | FR-05 | Given цены; When строим слоты; Then газ: `612 × 19,80 = 12 117,60`; вода: `4,2 × 60 = 252,00`; тепло: `qty × 2,0722`; воздух: `Σ cost COMPRESSOR = 642 × 8,40 = 5 392,80` (R-02 п. 4); нет цены — `price = cost = 0` | UT |
| AC-17 | FR-05 | Given `_cron_build`; When два прогона подряд; Then второй создаёт 0 новых строк, но пересчитывает два последних слота; строки `is_backfill=True` не перезаписываются; `td.energy.read_enabled = False` → 0 строк; исключение на одном счётчике логируется, остальные строятся | UT |
| AC-18 | FR-05 | Given строки старше `keep_interval_days`; When `_cron_rotate`; Then удалены (и синтетические), свежие целы; пакеты по 10 000 | UT |
| AC-19 | FR-06 | Given: ввод (kwh 100, export 20, cost 840), фидер (kwh 90), генерация (kwh 30), источник газа (qty 612), ветка газа (qty 41), consumer-интервал, `storage`-интервал, `react`-строка; When читаем `td.energy.usage`; Then потоки: `import` 100/840/37 кг, `export` 20, `load` 90, `generation` 30, `supply` 612 (cost 12 117,60, CO₂ 1 199,5), `branch` 41; `consumer`, `storage`, `react` отсутствуют; `id` уникальны; без группы cost поле `cost` недоступно | UT |
| AC-20 | FR-07 | Given `PM-Q1.e_react_signal_id` и показания kvarh; When построение; Then строки `metric='react'`, `price = cost = 0`; сутки `Q = 2 514`, `P = 6 284` → `tg φ = 0,40`, `cos φ = 0,93`; при `tg_phi_limit = 0,30`, `react_rate = 0,24` → `excess = 628,8`, `penalty = 150,9`; `tg_phi_limit = 0` → `penalty = 0` | UT |
| AC-21 | FR-08 | Given пользователь `base.group_user` без групп энергетики / только `group_td_energy_user` / с `…_cost`; When `get_resources()`; Then `AccessError` / ответ без ключей `cost_uah`, `save_uah_month`, без «₴» в `note` и `tabs[].sub` / ключи присутствуют | UT |
| AC-22 | FR-09 | Given фикстура el (`grid_kw=358`, `contract=800`, `kwh=6 284`, `price=8,40`, `cost=52 786`); Then `grid_now.value=358`, note «45 % договірної 800 кВт»; `today.value=6 284`, note «52 786 ₴ · 8,40 ₴/кВт·год»; `reactive` по AC-20; данные берутся из `get_pult` W1 без дублирования расчёта | UT |
| AC-23 | FR-09 | Given фикстура gas (`flow=46`, `today=612`, `price=19,80`, `GM-BOILER=540 м³`, `HM-BOILER=5 183 кВт·ч`, `infra/chp/state=stop`); Then `rate` note «котельня BOILER · КГУ стоїть»; `today` note «12 118 ₴ · 19,80 ₴/м³»; `limit.value=1 200`, note «використано 51 %»; `eff.value=91,4`, note «норма ≥ 90 %», tone `good`, `quality='estimated'` | UT |
| AC-24 | FR-09 | Given фикстура air (`flow=9,8`, `p_now=52`, `pressure=7,1`, `setpoint=7,0`, `COMPRESSOR 642 кВт·ч`, ночной минимум 1,6, `day_mean=10,0`); Then `spec=5,3`, note «норма ≤ 6,0», `good`; `rate` note «тиск 7,1 бар · уставка 7,0»; `today_el` note «5 393 ₴»; `night_leak.value=1,6`, note «16 % від денної витрати», tone `bad` | UT |
| AC-25 | FR-09 | Given фикстура water (`today=4,2`, `night=0,05`, `boiler=0,3`); Then `today` note «252 ₴»; `night` note «норма ≤ 0,05», `good`; `boiler` note «норма ≤ 0,5 м³/добу», `good`; покрытие ночного окна < 70 % → `night.value = null` | UT |
| AC-26 | FR-08 | Given суточная стоимость el 52 786, gas 12 118, water 252, air 5 393, heat без цены; Then `meta.total.cost_uah = 65 156` (air и heat не суммируются); текст по D-31; без группы cost — «Сьогодні: 5 ресурсів» | UT |
| AC-27 | FR-08 | Given `now_slot=57`; Then `chart.series` длины 96, слоты после 57 — `null`, слот 57 — живое значение; `limit` el = `contract_kw`, gas = 80; `y_max`: газ 90, el 900, воздух 12, вода 0,6; `foot` для el/gas/air/water по R-10 (в т. ч. при `leak_sentence` ветвях) | UT |
| AC-28 | FR-08 | Given точки газа (41 / 4 / 0 / 1 м³/ч) и воды (qty_day 2,6 / 1,1 / 0,3 / 0,2); Then список по убыванию, `basis` gas = `rate`, water = `qty_day`, `share` = `value/max`, нулевые показаны, максимум 8 | UT |
| AC-29 | FR-10 | Given `source 46`, потребители `41+4+0+1`; Then `unaccounted = {0,0; 0,0}`; потребители больше ввода на 8 % → `inconsistent=true`; нет `source`-точки → `null` | UT |
| AC-30 | FR-08 | Given все сигналы ресурса несвежие; Then `data_state='stale'`, значения `null`, исключений нет; часть счётчиков несвежая — `partial` | UT |
| AC-31 | FR-08 | Given ресурс `air` с `active=False` / без активных счётчиков; Then вкладка отсутствует в `tabs`; `get_resources('air')` → `UserError("Невідомий ресурс: air.")` | UT |
| AC-32 | FR-13 | Given данные модуля; Then 6 правил ядра (`vent_offshift`, `idle_machines`, `air_leaks`, `air_pressure`, `react_section`, `pv_export`) с `enabled`, `lookback_days`, порогами из R-15…R-20 и `resource`; `params_schema` корректна; `params` вне диапазона → `ValidationError`; `actions` с неверным `kind` → `ValidationError` | UT |
| AC-33 | FR-13 | Given детектор возвращает находку; When `_cron_detect`: 1-й прогон; 2-й с другим числом; 3-й без находки; Then создан → обновлён (`in_plan` сохранён) → `expired`; `dismissed` подавляет повтор `dismiss_days`, `done` — `cooldown_days`; находка ниже `min_saving_uah` отбрасывается; исключение детектора пишет `last_error`, остальные правила работают | UT |
| AC-34 | FR-14 | Given фикстура R-15 (`day 100`, `off 50`, `off_hours 88`, цена `6,00`); Then `est_qty_month = 7 620,8`, `est_saving = 45 725`; `ratio < 0,35` → `[]`; нет узлов `vent` → `[]`; данных < 3 суток → `[]` | UT |
| AC-35 | FR-14 | Given фикстура R-16 (`idle 410`, `rc 6 000`, цена 8,40); Then `est_qty_month = 1 242,7`, `est_saving = 10 439`; `share < 5 %` → `[]`; `evidence.top_nodes` — 3 узла | UT |
| AC-36 | FR-14 | Given фикстура R-17 (`night 1,6`, `day 10,0`, `spec 0,0883`, цена 8,40); Then `est_qty_month = 4 022,2`, `est_saving = 33 787`, действие `ticket` на `COMPRESSOR` с тегом; менее 3 ночей → `[]`; `ratio < 10 %` → `[]` | UT |
| AC-37 | FR-14 | Given фикстура R-18 (`p_set 7,0`, `p_need 6,2`, `margin 0,3`, `kWh 4 494`, цена 8,40); Then `est_qty_month = 681,0`, `est_saving = 5 721`; уставка берётся из сигнала `air/setpoint_bar`, иначе из параметра; `dp < 0,2` → `[]` | UT |
| AC-38 | FR-14 | Given фикстура R-19 (`P 3 000`, `Q 1 650`, `tg_limit 0,40`, `rate 0,24`); Then `est_qty_month = 13 500`, `est_saving = 3 240`; без `tg_phi_limit` → `[]` и `last_error`; `h_low_avg < 2` → `[]`; действие ведёт на открытую заявку PFC | UT |
| AC-39 | FR-14 | Given фикстура R-20 (`E 118`, `buy 8,40`, `export 2,00`); Then `est_qty_month = 510,9`, `est_saving = 3 270`; `buy ≤ export` → `[]` | UT |
| AC-40 | FR-15 | Given правило с `control_intent`; Then в `get_list` действие `control` имеет `enabled=false` (нет `td_energy_control`) и в список добавлено `fallback_action`; при `_td_control_available=True` — `enabled=true`; `ticket`-действие содержит `[OPP-<id>]` | UT |
| AC-41 | FR-15 | Given заявка ТО с тегом `[OPP-<id>]`; When `_td_link_requests`; Then `request_id` заполнен; перевод заявки в стадию `done` → резерв `done`, `result_note="Заявку закрито"` | UT |
| AC-42 | FR-13 | Given пользователь `…_user` / `…_manager`; When `action_plan_toggle`, `action_dismiss`, `action_done`; Then `AccessError("Керувати резервами може лише енергетик.")` / успех; для закрытого резерва — `UserError("Резерв уже закрито.")`; сообщение в чаттере | UT |
| AC-43 | FR-13 | Given 3 открытых резерва (в плане 1); When `get_list`, `get_plan_summary`; Then `plan_sum`, `all_sum` равны суммам `est_saving_month`; без группы cost суммы и `save_uah_month` отсутствуют; сортировка по `in_plan desc, est_saving desc` | UT |
| AC-44 | FR-12 | Given 2 суток данных; When `GET /td/energy/resources/export?day=…`; Then `200`, xlsx с листами «Ресурси», «Підсумок»; колонки цены/стоимости — только с группой cost; `400` — неверная дата, неизвестный код, диапазон > `export_max_days`; `403` — без группы; `413` — строк > 200 000 (лимит подменяется в тесте) | UT |
| AC-45 | FR-12 | Given стенд, сутки данных; When скачать xlsx за вчера через UI; Then файл открывается `openpyxl`, число строк = число слотов × активных потоков; значения совпадают с `td.energy.usage` | TC |
| AC-46 | FR-18 | Given БД с электрическим backfill и 16 неэлектрическими счётчиками; When `_td_backfill(days=2, seed=1)`; Then создано `18 × 192 = 3 456` строк (16 счётчиков + 2 `react`-метрики), все `is_backfill=True`; `quality='estimated'` только у оценочных | UT |
| AC-47 | FR-18 | Given история 7 суток; Then `Σ GM-MAIN` отличается от суммы ветвей ≤ 3 %; ночной минимум воздуха 1,6 ± 0,2 м³/мин; корреляция суточного расхода воздуха с `COMPRESSOR` кВт·ч ≥ 0,9; одинаковый `seed` → одинаковый SHA-256 набора строк; повторный вызов — `rows = 0`, `skipped = rows₁`; `purge=True` удаляет только `is_backfill` | UT |
| AC-48 | FR-18 | Given живые строки после `until`; When backfill; Then живые не перезаписываются, `res_last_interval_start` не уменьшается; слоты `≥ until` не создаются | UT |
| AC-49 | FR-19 | Given пользователи `user`/`manager`/`admin`; Then `user` не пишет в `resource`, `price`, `point`, `rule`, `opportunity`; `manager` — цены, точки, правила (write), резервы (write); `admin` — всё; `td.energy.res.interval` пишет только `admin`/`sudo`; record rules по компании | UT |
| AC-50 | FR-19 | Given `neutralize.sql`; Then 4 крона неактивны, источники `MB-U74-GAS-MAIN`, `MB-U75-AIR-MAIN` — `read_enabled=false`; `uninstall_hook` удаляет неэлектрические счётчики и возвращает `node_id required`, электрические `interval`, `alloc`, события и сигналы целы | UT + DEPLOY_TEST |
| AC-51 | FR-20 | Given `res.config.settings`; Then параметры блока «Енергоресурси» редактирует `…_manager`; `night_from_h ≥ 24`, `gap_max_s < 300`, `min_coverage ∉ (0, 1]` → `ValidationError`; смена `night_to_h` меняет `night_rate` в R-09 | UT |
| AC-52 | FR-21 | Given тариф; Then `tg_phi_limit < 0` или `react_rate < 0` → `ValidationError`; `react_rate > 0` при `tg_phi_limit = 0` → `ValidationError("Ставка без ліміту tg φ не має сенсу.")`; `_td_react_penalty(100)` при `react_rate=0,24` → `24,0`; поля скрыты без группы cost | UT |
| AC-53 | FR-22 | Given календарь не задан / два блока «Зміна 1»+«Зміна 2» / стандартные имена строк; Then `shift_of` по R-21 (вт 15:59 → «Зміна 1»; 16:00 → «Зміна 2»; 23:00 → `None`; сб 10:00 → `None`); сутки перехода DST — границы смен корректны | UT |
| AC-54 | FR-17 | Given свежая и существующая БД; When `_ensure_resource_signals`; Then создано 10 сигналов и 2 источника, повтор — без изменений; адреса/масштабы по 5.4; `air/pressure_bar` `warn_low=5,8`, `min_duration_s=300`, `create_request=False`; `air/setpoint_bar` **не** создаётся | UT |
| AC-55 | FR-17 | Given модели эмулятора; Then `heat_kw=390` → `gas_m3h = 40,6`; `load=66` → `air flow = 9,8`; `load=25` → `1,6`; `air pressure = compressor − 0,1`; `boiler_m3_total` растёт на `0,0125·max(1, boilers_on)` м³/ч; `kvarh_total` растёт на `|q_kvar|·dt/3600`; `gas` = `BOILER + CHP + dry + canteen` | UT (pytest) |
| AC-56 | FR-23 | Given сценарии `air_leak`, `gas_overuse`, `water_leak`; Then файл `td_sim_scenario_resources.xml` содержит их с параметрами; `air_leak` повышает ночной расход на 3,0 м³/мин; `gas_overuse` поднимает расход источника выше 80 м³/ч; `water_leak` — ночной расход воды +0,5 м³/ч | UT (pytest) + TC |
| AC-57 | FR-11 | Given hoot с моком API-01; Then `Resources` переключает вкладки; KPI и `tone`; график строит 96 слотов, `null` разрывает линию, `limit` пунктиром; заметки: `control` без обработчика скрыт, показывается запасное действие; «Налаштувати пороги» — только при `capabilities.manage`; ссылка экспорта содержит `day` | UT-JS |
| AC-58 | FR-11 | Given `HttpCase`; When открыть `action_td_energy_resources` для каждого из 5 ресурсов; Then без JS-ошибок; пункт меню «Енергоресурси» виден `group_td_energy_user`, разделы настроек — `…_manager` | UT |
| AC-59 | FR-11 | Given стенд, 10 минут работы; When открыть экран; Then 5 вкладок с данными, `data_state='ok'`, значения меняются без перезагрузки (шина, ≤ 10 с после тика) | TC |
| AC-60 | FR-24 | Given БД с 90 сутками истории; Then `get_resources(code)` ≤ 400 мс (медиана 10 вызовов), ≤ 30 SQL, без N+1 по точкам; `_cron_build` ≤ 5 с; запрос `usage` за сутки ≤ 200 мс | UT (ТП-01…03) |
| AC-61 | FR-24 | Given backfill 90 суток; Then ≤ 60 с, ≈ 207 000 ± 10 % строк, ≤ 400 МБ RAM процесса | UT/TC (ТП-04) |
| AC-62 | FR-14 | Given стенд, запущен `air_leak`; When `action_run` правила `air_leaks` после ≥ 3 ночей истории; Then появляется резерв `air_leaks`, KPI «Витоки вночі» выше нормы; остановка сценария → резерв переходит в `expired` при следующем прогоне | TC |
| AC-63 | FR-19 | Given запросы к API-07 с `day='2026-10-17;DROP…'`, `resources='gas,../x'`, огромным диапазоном; Then `400`, без SQL-исполнения, без утечки данных в тексте ошибки | UT |
| AC-64 | FR-16 | Given только `td_energy_resources` (без моста); Then хуки `_td_heat_kpis`, `_td_heat_list`, `_td_heat_chart_note`, `_td_bind_extra` возвращают пустое; вкладка «Тепло» работает на вручную созданных тепловых счётчиках; `get_resources('heat')` не падает при отсутствии BMS | UT |

**Итого `td_energy_resources`: AC-01…AC-64 = 64 критерия** (UT 55 — в т. ч. HttpCase, UT-JS 1 (AC-57), TC 3 (AC-45, AC-59, AC-62), UT+DEPLOY_TEST 2 (AC-05, AC-50), UT-pytest 1 (AC-55), UT-pytest+TC 1 (AC-56), UT/TC 1 (AC-61)).

## 13. План тестирования (для Opus)

### 13.0 Фикстуры и требования к тестируемости

- `tests/common.py` (A): `TestW3Common(TransactionCase)` — `_resource(code)`, `_point(code, resource, kind, **vals)`, `_meter(code, point, mode, signals=..)`, `_signal(code, value, ts=now, status='ok')`, `_reading(code, ts, value)`, `_node_interval(node_code, ts, kwh, price=8.40)` (электрические `consumer`/`incomer`/`feeder`), `_res_interval(meter, ts, qty, quality='measured')`, `_user(groups)`, мок времени `patch("odoo.addons.td_energy.tools.dates.now_utc")`.
- Время всегда через `td_energy.tools.dates.now_utc(env)` (мокается); детерминизм backfill — `seed`.
- Фикстура «Макет 14:20» (`TestW3Common._mockup_1420()`): сигналы и интервалы под числа AC-22…AC-26 (358 кВт, 6 284 кВт·ч, 46 м³/ч, 612 м³, 9,8 м³/мин, 4,2 м³ и т. д.); используется тестами `test_w3_dashboard.py`.
- JS: hoot, мок `orm.call` с JSON из разд. 7.

### 13.1 Юнит-тесты (A, B, C)

| Файл | Класс | Покрывает |
|---|---|---|
| `test_w3_data.py` (A) | `TestW3Data` | AC-01…AC-07, AC-49, AC-50, AC-52, AC-53, AC-54 (`test_resources_seed`, `test_resource_constraints`, `test_price_rules`, `test_point_constraints`, `test_meter_default_el_migration`, `test_meter_binding`, `test_electric_cron_untouched`, `test_signals_ensure`, `test_tariff_react`, `test_uninstall_hook`) |
| `test_w3_integrate.py` (A) | `TestW3Integrate` | AC-08…AC-11 (`test_flow_trapezoid`, `test_flow_coverage`, `test_flow_air`, `test_counter_reset`, `test_multisignal`) |
| `test_w3_estimate.py` (A) | `TestW3Estimate` | AC-12…AC-15 |
| `test_w3_cost.py` (A) | `TestW3Cost` | AC-16, AC-17, AC-18, AC-20, AC-51, AC-60 (ТП-02, ТП-03) |
| `test_w3_usage.py` (A) | `TestW3Usage` | AC-19 |
| `test_w3_dashboard.py` (E) | `TestW3Dashboard` | AC-21…AC-31, AC-64 (блок `notes` — через `patch` на `td.energy.opportunity.get_list`, если модель резервов ещё не влита) |
| `test_w3_export.py` (E) | `TestW3Export` | AC-44, AC-63 |
| `test_w3_backfill.py` (A) | `TestW3Backfill` | AC-46…AC-48, AC-61 |
| `test_w3_security.py` (E) | `TestW3Security` | AC-60 (ТП-01), ТБ-01…ТБ-04 |
| `test_w3_opportunity.py` (B) | `TestW3Opportunity` | AC-32, AC-33, AC-40…AC-43 |
| `test_w3_detectors.py` (B) | `TestW3Detectors` | AC-34…AC-39 (по методу на детектор: `test_vent_offshift`, `test_idle_machines`, `test_air_leaks`, `test_air_pressure`, `test_react_section`, `test_pv_export`) |
| `test_w3_ui.py` (C) | `TestW3Ui` | AC-58 |
| `test_w3_hoot.py` (C) | `TestW3Hoot.test_hoot_suite` | AC-57 (запуск `/web/tests?headless…&id=<hash('@td_energy_resources')>` по образцу `td_energy/tests/test_w1_hoot.py`) |
| `services/iot_sim/tests/unit/test_gas.py`, `test_air.py`, `test_water_boiler.py`, `test_meter_kvarh.py` (D) | pytest | AC-55, AC-56 |

### 13.2 Стендовые сценарии ТК-01…ТК-06 (`tests/stand/test_w3_tk.py`, D)

Предусловие: стенд E-11 (эмулятор + сборщик + Odoo), установлены `td_energy`, `td_energy_resources`, `td_bms`, `td_energy_resources_bms`; электрический `_td_backfill(days=90)` выполнен ≥ 5 мин после старта сборщика; затем `td.energy.res.interval._td_backfill(days=90)`.

| ТК | Название | Шаги | Ожидается |
|---|---|---|---|
| ТК-01 | Экран живой | открыть «Енергоресурси», 10 мин | 5 вкладок, KPI заполнены, `data_state='ok'`, график без разрывов за последний час, значения обновляются по шине |
| ТК-02 | Новые сигналы | `td.signal` по 10 кодам разд. 5.4 | `status='ok'`, `last_ts` ≤ 2 мин, счётчики растут, `infra/gas/flow_m3h` ≈ сумме ветвей ±5 % |
| ТК-03 | Стык истории и живых | `get_resources` + запрос `res.interval` на границе `until` | слотов `missing` на стыке 0; графики газа/воздуха/воды непрерывны; `is_backfill` меняется на `False` одним переходом |
| ТК-04 | Утечка воздуха | запустить `air_leak` на ≥ 1 ночь (или ускоренные часы эмулятора), затем `action_run` правила | KPI «Витоки вночі» > 10 % дневной; резерв `air_leaks` создан; остановка сценария → `expired` |
| ТК-05 | Перерасход газа | запустить `gas_overuse` | расход источника > 80 м³/ч, линия лимита пересечена, KPI «Ліміт доби» растёт |
| ТК-06 | Экспорт | скачать xlsx за вчера | AC-45 |

### 13.3 Тесты безопасности (ТБ-01…ТБ-04)

- ТБ-01: `base.group_user` без групп → `AccessError` на всех публичных методах `td.energy.res.dashboard`, `td.energy.opportunity` и `403` на экспорте (AC-21, AC-44).
- ТБ-02: ключи стоимости отсутствуют у пользователя без `group_td_energy_cost` в API-01, API-02, API-06, API-10, xlsx (AC-21, AC-43, AC-44).
- ТБ-03: ACL: `user` не меняет резервы/правила/цены/точки (AC-42, AC-49).
- ТБ-04: параметры экспорта не приводят к SQL-инъекции и произвольным путям (AC-63).

### 13.4 Тесты производительности (ТП-01…ТП-05)

- ТП-01: `get_resources(code)` ≤ 400 мс, ≤ 30 SQL на любой вкладке (AC-60).
- ТП-02: `_cron_build` ≤ 5 с для 24 счётчиков (AC-60).
- ТП-03: запрос `td.energy.usage` за сутки ≤ 200 мс; за 30 суток ≤ 1,5 с на БД с 90 сутками (AC-60).
- ТП-04: `_td_backfill(days=90)` ≤ 60 с, ≤ 400 МБ (AC-61).
- ТП-05: `_cron_detect` (6 правил) ≤ 60 с на БД с 90 сутками истории.

### 13.5 DEPLOY_TEST

1. Копия демо-БД с W1 (`td_demo_tpl`) → `-i td_energy_resources` → проверить количества (разд. 5.5), `td_energy` тесты зелёные (AC-05).
2. Повторное `-u td_energy_resources` — без изменений.
3. Откат: `uninstall` → AC-50 (электрическое цело, `node_id required`).
4. `neutralize.sql`.
5. Установка с `td_bms` (мост авто-ставится) и без него (AC-64).

### 13.6 Распределение тестов и команд по воркерам (выписка из ARCH §6)

Шаг 0 — каркас менеджера (пустые файлы, `__init__.py`, манифесты); `T=factory3d/tools/odoo`. Не более 3 воркеров параллельно на стадию; общих файлов нет (владельцы — разд. 0).

| Стадия | Воркер | Тесты | Команда |
|---|---|---|---|
| 1 | A «Данные» | `test_w3_data`, `test_w3_integrate`, `test_w3_estimate`, `test_w3_cost`, `test_w3_usage`, `test_w3_backfill` | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3a /td_energy_resources:TestW3Data` (затем `…TestW3Integrate`, `…TestW3Estimate`, `…TestW3Cost`, `…TestW3Usage`, `…TestW3Backfill`); регресс `$T/run_tests.sh td_w3a_reg /td_energy` |
| 1 | D «Эмулятор и сигналы» | `services/iot_sim/tests/unit/test_{gas,air,water_boiler,meter_kvarh}.py`; стенд `tests/stand/test_w3_tk.py` | `pytest services/iot_sim/tests/unit/test_gas.py services/iot_sim/tests/unit/test_air.py services/iot_sim/tests/unit/test_water_boiler.py services/iot_sim/tests/unit/test_meter_kvarh.py`; стенд — менеджер |
| 2 | E «API экрана и экспорт» | `test_w3_dashboard`, `test_w3_export`, `test_w3_security` | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3e /td_energy_resources:TestW3Dashboard` (затем `…TestW3Export`, `…TestW3Security`) |
| 2 | B «Резервы и мост» | `test_w3_opportunity`, `test_w3_detectors`, `test_wb_bridge` | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3b /td_energy_resources:TestW3Opportunity` (затем `…TestW3Detectors`); мост: `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3bb /td_energy_resources_bms` |
| 2 | C «Экран (OWL)» | `test_w3_ui`, `test_w3_hoot` | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3c /td_energy_resources:TestW3Ui` и `…:TestW3Hoot` |
| — | менеджер (интеграция) | всё | `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3_full`; затем стенд ТК-01…ТК-06, ТК-B1 |

## 14. Definition of Done (W3, `td_energy_resources`)

- Все UT/UT-JS AC-01…AC-64 зелёные; ТК-01…ТК-06 пройдены на стенде; `ruff` без ошибок; регрессия `td_energy` (142 теста + W1) зелёная;
- `neutralize.sql` обновлён; CHANGELOG, README (разделы «Енергоресурси», «Резерви економії»), DEPLOY_TEST дополнен; обзор безопасности (ТБ-01…ТБ-04);
- миграция 19.0.1.0.0 проверена на копии БД; backfill выполнен на стенде, скриншоты пяти вкладок;
- строки эмулятора в `catalog/signals.csv` и `td_iot_sim/data/td_sim_signal.csv` идентичны (сверка скриптом), `n` пересчитан при слиянии с W2.

## 15. Открытые вопросы и решения автора

### Вопросы Q-01…Q-08

| ID | Вопрос | Кому | Рекомендация | Что делаем пока |
|---|---|---|---|---|
| Q-01 | Какое топливо у реальной котельни: газ (макет) или брикеты (демо-модель `BOILER`)? | заказчик | газ; демо оставляет оба канала (D-35) | газовый канал эмулятора — по E-07 |
| Q-02 | Какие приборы учёта газа/воздуха/воды/тепла есть и их протоколы/регистры; паспортные расходы воздуха | заказчик, электрики | строить на оценках (`estimated`), реальные приборы подключать заменой счётчика на `counter`/`flow_integrate` без правки UI | `ПРИПУЩЕННЯ` в 5.3/5.4; пометка «оцінка» в UI |
| Q-03 | Есть ли в договоре доплата за реактивную энергию (`tg φ` лимит, ставка) | заказчик | да/нет; параметры в тарифе | правило `react_section` и «ризик доплати» выключены без параметров |
| Q-04 | Нужны ли калориметры на тепло (приход) отдельно от модели BMS | заказчик | позже; точка `source` с `counter` заменяет интеграл | теплосчётчики из BMS-сигналов |
| Q-05 | Источник цен газа и воды (договор, индексация) | бухгалтерия | ручная таблица `td.energy.price` с датами | цены демо 19,80 и 60,00 |
| Q-06 | Допустим ли новый HTTP-маршрут `/td/energy/resources/export` (раньше блок обходился ORM) | менеджер | да (аутентифицированный GET, проверка группы) | реализован (A-10) |
| Q-07 | Владелец сигнала `air/setpoint_bar` | менеджер W2 | W2 (уставка и команды компрессора) | параметр `air_setpoint_bar`, чтение сигнала, если появится |
| Q-08 | Сигнал открытия доковых ворот (`td.yard.gate` — шлагбаумы) | заказчик | датчик открытия ворот отгрузки в BMS/Yard | точка `DOCK` и правило `dock_gates` активны только при наличии сигнала |

### Решения автора (A-01…A-16)

| ID | Решение | Обоснование |
|---|---|---|
| A-01 | Два модуля: `td_energy_resources` (ядро ресурсов) + `td_energy_resources_bms` (`auto_install`) | D-18: связь с `td_bms` необязательна; мост решает порядок установки и даёт `hvac_ref` без жёсткой зависимости; GAP предлагал один модуль — менеджер может свернуть мост в ядро (тогда `depends += td_bms`) |
| A-02 | Не-электрические счётчики — тот же `td.energy.meter` (`_inherit`), `node_id required=False` + `_check_resource_binding`; у них нет `e_import_signal_id`, поэтому электрические расчёты их не видят | единый реестр счётчиков и повірка; регрессия `td_energy` исключена (AC-06) |
| A-03 | Отдельная таблица `td.energy.res.interval` + SQL-view `td.energy.usage` (без `row_number`) | GAP Q-04; электрические запросы и 142 теста не затрагиваются; view даёт единую сводку для W4 |
| A-04 | Реактивная энергия — `metric='react'` в `res.interval` на электрических вводах, не новая таблица и не роль счётчика | не меняет семантику `td.energy.interval`, не попадает в электрический крон |
| A-05 | Оценочные методы описываются на **точке** (`estimate_method`, `estimate_params`), счётчик режима `estimate` лишь ссылается на неё | метод — свойство сущности, а не канала; один набор данных для backfill и крона |
| A-06 | Мультисигнальный счётчик (`flow_signal_ids`, сумма) вместо вычисляемого сигнала `ventilation/totals/heat_kw` | не плодить вычисляемые сигналы; 25 установок RV считаются одной строкой |
| A-07 | `in_plan` — отдельный булев флаг резерва, `state` — только жизненный цикл | чекбокс «У плані» (W4) не должен менять статус; плановая история сохраняется при `expired` |
| A-08 | Реестр детекторов — модуль `tools/detectors/` + методы `_td_detect_<code>` у `td.energy.opportunity.rule`, мост добавляет свои через `_inherit` | как реестр правил `_td_advice_rule_*` W1; расширяемость без правок ядра |
| A-09 | Тепло — через мост: точки/счётчики из `td.bms.heat.balance` и `td.bms.hvac.unit`, KPI «Температура»/«Рекуперація», 3 детектора | GAP §4.4; BMS-сигналы не дублируются |
| A-10 | Экспорт — собственный маршрут xlsx (`xlsxwriter`), а не стандартный экспорт Odoo | стандартный экспорт работает по одной модели и не даёт «в один клик» всех ресурсов (RS-15) |
| A-11 | Параметры — `td.energy_resources.*`; модульная нумерация ID, сквозные D-xx с диапазоном D-31…D-50 | конвенция §5 (`td.<module>.<param>`); отличие от W1, где параметры `td.energy.*` |
| A-12 | Флаги ресурса (`is_derived`, `in_energy_cost`, `show_tab_cost`) задают состав сумм: «разом» (heat, air — нет), «вартість енергії» W4 (el, gas) | в макете два разных набора |
| A-13 | Вкладка показывает **все** открытые резервы своего ресурса (D-40) | единый источник с аналитикой |
| A-14 | Балансы газа/воды (источник против ветвей) — только индикатор в списке, без событий и тревог | нет согласованных допусков; события — Q при появлении реальных приборов |
| A-15 | Окна смен — общий хелпер `tools/shifts.py` в `td_energy_resources` (используется W4) на календаре `td.energy.shift_calendar_id`; умолчание — смены макета | Q-23 W1; один источник правды |
| A-16 | `uninstall_hook` удаляет неэлектрические счётчики (и тем самым возвращает `node_id required`) | иначе откат модуля ломает схему `td.energy.meter`; электрические данные не затрагиваются |

---

# ЧАСТЬ II. `td_energy_resources_bms` — мост «Енергоресурси — Будівля»

Мост (`auto_install`: `td_energy_resources` + `td_bms`) добавляет вкладке «Тепло» данные BMS: точки и счётчики тепла, KPI температуры и рекуперации, список «Куди йде тепло», три детектора. Отсутствие `td_bms` — ядро работает без тепла (AC-64).

## B.0 Дерево файлов

```
odoo_addons/td_energy_resources_bms/              B
├── __manifest__.py                               (менеджер) version 19.0.1.0.0; depends [td_energy_resources, td_bms]; auto_install True
├── __init__.py                                   (менеджер)
├── hooks.py                                      B  post_init_hook → env["td.energy.point"]._td_bind_extra()
├── models/
│   ├── __init__.py                               (менеджер)
│   ├── td_energy_point.py                        B  M-B1 (_inherit: hvac_ref → связи, `_td_bind_extra`)
│   ├── td_energy_res_dashboard.py                B  M-B2 (_inherit: хуки тепла)
│   ├── td_energy_res_interval.py                 B  `_td_backfill_extra` (R-B5)
│   └── td_energy_opportunity_rule.py             B  `_td_detect_preheat_early`, `_td_detect_ahu_recuperation`, `_td_detect_dock_gates`
├── tools/heat.py                                 B  R-B2, R-B3 (η, индикаторы), R-B5 (генераторы)
├── data/opportunity_rules.xml                    B  3 правила (noupdate=1)
├── data/neutralize.sql                           B  (пусто, комментарий)
├── static/src/heat_note.xml                      B  UI-B1 (подпись «оцінка» у KPI «Рекуперація»; шаблон-наследник `ResKpis`)
└── tests/test_wb_bridge.py, tests/stand/test_wb_tk.py   B
```

## B.1 Манифест

`depends: ["td_energy_resources", "td_bms"]`, `auto_install: True`, `data`: `data/opportunity_rules.xml`; `assets`: `web.assets_backend`: `td_energy_resources_bms/static/src/**`; `post_init_hook`: `hooks.post_init_hook`.

## B.2 Модели

### M-B1 `td.energy.point` — расширение

Поле `hvac_unit_id` — Many2one `td.bms.hvac.unit` (ondelete=set null, «Установка BMS»); `hvac_ref` ядра остаётся как текстовый код (источник для `_td_bind_extra`). Метод `_td_bind_extra()` (R-B1): идемпотентно создаёт точки и счётчики тепла.

### M-B2 `td.energy.res.dashboard` — расширение

Реализация хуков ядра: `_td_heat_kpis(ctx)` (R-B2), `_td_heat_list(ctx)` (R-B2 п. 4), `_td_heat_chart_note(ctx)` → `capacity_kw` из `td.bms.heat.balance` (активная запись компании).

### UI-B1 Бейдж «оцінка» у KPI «Рекуперація»

Шаблон-наследник `td_energy_resources.ResKpis` (`static/src/heat_note.xml`, `t-inherit`): у карточки с `quality='estimated'` показывается точка и подпись «оцінка» (подсказка «Розрахунок за тепловим балансом установки»); ядро показывает только точку. Хуков и состояния JS нет.

## B.3 Данные

`data/opportunity_rules.xml` (`noupdate="1"`): правила `preheat_early` (`resource=gas`), `ahu_recuperation` (`resource=heat`), `dock_gates` (`resource=heat`) с `params`, `params_schema`, `actions`, `control_intent` (`heat_schedule_shift` для первого; у остальных пусто).
Точки и счётчики тепла создаёт `_td_bind_extra()` (не XML), потому что зависят от установленных сигналов BMS.

## B.4 Алгоритмы

### R-B1 Привязка BMS (FR-B1)

`_td_bind_extra()`:
1. `balance = env["td.bms.heat.balance"].search([("company_id", "=", env.company.id)], limit=1)`; нет — выход (`{}`).
2. Точки `heat`: `HEAT-BOILER` (`source`; сигнал `balance.boiler_heat_signal_id`), `HEAT-CHP` (`source`; `balance.chp_heat_signal_id`), потребители `RV-ALL` (`hvac_ref='RV-*'`), `AHU-1` (`hvac_unit_id` по `code='AHU-1'`), `OFFICE` (остаток), `DOCK` — только если найден сигнал открытия ворот: `env.get("td.yard.gate")` → первый шлагбаум/ворота с `state_signal_id` и `direction` отгрузки (`side='east'`), иначе точка не создаётся (Q-08).
3. Счётчики: `HM-BOILER`, `HM-CHP` (`flow_integrate`, один сигнал); `HM-RV` (`flow_integrate`, `flow_signal_ids` = `heat_signal_id` всех `td.bms.hvac.unit` с `code like 'RV-%'`); `HM-AHU1` (`heat_signal_id` установки `AHU-1`); `HM-DOCK` (`estimate`, `gate_loss`: `loss_kw_per_k=3,5`, `t_out_signal=ventilation/totals/outdoor_c`, `t_in` = `balance.t_in_set`); `HM-OFFICE` (`estimate`, `residual` `{"from": ["HEAT-BOILER","HEAT-CHP"]}`).
4. Идемпотентность по `(resource, code)`; изменённые вручную поля существующих записей не перезаписываются.
Ожидаемые количества на демо-БД: точек тепла 5 (без `DOCK`) или 6; счётчиков 5 или 6; `HM-RV` — 25 сигналов.

### R-B2 Тепловые KPI и список (FR-B2)

1. `_td_heat_kpis(ctx)`: 
   - `power.note` = «подача {boiler_supply_signal.last_value} °C · зворот {boiler_return_signal.last_value} °C»;
   - `indoor` = среднее `indoor_c` установок с `required_in_work` (RV + AHU-1), значение 1 знак, `unit="°C"`, note «уставка {t_in_set} °C · зовні {outdoor_c} °C» (`outdoor_c` — `ventilation/totals/outdoor_c`), `good` при `|indoor − t_in_set| ≤ 1`;
   - `recovery` — R-B3 (AHU-1), note «норма ≥ {recovery_norm_pct} %» + « · фільтр брудний», если `filter_dp_pa > filter_dp_limit_pa`; `bad` при `η < recovery_norm`; `quality='estimated'`.
2. Параметры (`ir.config_parameter`, мост): `td.energy_resources_bms.recovery_norm_pct = 70`, `td.energy_resources_bms.filter_dp_limit_pa = 250`.
3. `power.value` — `Σ` скорости `source`-точек (ядро), `today` — `Σ qty` источников.
4. `_td_heat_list(ctx)`: потребители `RV-ALL`, `AHU-1`, `DOCK`, `OFFICE` (значение — скорость сейчас, кВт; `OFFICE` = max(0, Σ источников − остальные)).
5. Пример (14:20, макет): источники 390 кВт; `RV-ALL 228`, `AHU-1 74`, `DOCK 46`, `OFFICE = 390 − 228 − 74 − 46 = 42`.

### R-B3 Рекуперация AHU-1 (оценка; D-36)

`T_after = T_supply − Q_heat × 1000 / (air_wh_m3k × airflow_m3h)`; `η = (T_after − T_out)/(T_in − T_out)`, где `T_supply = supply_c`, `Q_heat = heat_kw`, `airflow_m3h` — сигнал `airflow_m3h` установки, `air_wh_m3k` — `td.bms.heat.balance.air_wh_m3k` (0,34), `T_in = indoor_c` (замена температуры вытяжки; если появится сигнал `ventilation/units/AHU-1/extract_c` — используется он), `T_out = ventilation/totals/outdoor_c`. Защита: `T_in − T_out < 5 К`, `airflow < 10 %` от `airflow_nom` или `η ∉ [0, 1]` → `η = null`.
Пример: `airflow 32 000 м³/ч`, `Q_heat 74 кВт`, `T_supply 21,0`, `T_in 18,4`, `T_out 7,0` → `ΔT = 74 000/(0,34·32 000) = 6,80`; `T_after = 14,2`; `η = (14,2 − 7)/(18,4 − 7) = 0,632` (63 %).

### R-B4 Детекторы моста (FR-B3)

**`preheat_early`** (газ): параметры `t_ready` = `balance.t_in_set` (18 °C), `margin_min=30`, `lookback_days=7`, `min_saving_uah=1000`, `control_intent="heat_schedule_shift"`.
1. Для каждого рабочего дня окна: `ready_time` = первый момент до начала первой смены, когда среднее `indoor_c` по установкам `required_in_work` ≥ `t_ready` (сырые показания, шаг 5 мин); `margin = shift_start − ready_time` (мин, R-21).
2. `margin_med` = медиана по дням (≥ 3 дней); `margin_med − margin_min ≤ 0` → `[]`.
3. Газ разогрева: `preheat_rate` = средняя скорость `GM-BOILER` в окне `[shift_start − margin_med − 60 мин, ready_time]` (м³/ч); `extra_h = (margin_med − margin_min)/60`; `qty_window = preheat_rate × extra_h × (число рабочих дней окна)`; `est_qty_month = qty_window × K_month`; `est_saving = est_qty_month × price_gas`.
4. Текст: «Цех досягає {t_ready} °C о {ready_time}, а зміна о {shift_start}. Пізніший старт на {margin_med − margin_min} хв.»
Фикстура: `margin_med = 55`, `margin_min = 30`, `preheat_rate = 46`, 5 рабочих дней, `price_gas = 19,80`, `L=7` → `extra_h = 0,4167`; `qty_window = 46 × 0,4167 × 5 = 95,83 м³`; `est_qty_month = 95,83 × 4,33 = 415,0 м³`; `est_saving = 8 216 ₴`.

**`ahu_recuperation`** (тепло): параметры `eta_norm = recovery_norm_pct/100`, `dp_limit = filter_dp_limit_pa`, `lookback_days=7`, `min_saving_uah=500`; действие `ticket` (`node_code="AHU-1"`, «AHU-1: заміна фільтра [OPP-<id>]»).
1. За окно: `η_mean` — среднее R-B3 в рабочие часы (не `null`), `dp_mean` — среднее `filter_dp_pa`; находка при `η_mean < eta_norm` **или** `dp_mean > dp_limit`.
2. Потери: `loss_kw = (eta_norm − η_mean) × air_wh_m3k × airflow_m3h × (T_in − T_out)/1000` (кВт; `max(0, …)`), `run_hours = число рабочих часов окна`; `qty_window = loss_kw × run_hours` (кВт·ч тепла); `est_qty_month = qty_window × K_month`; `price_heat` — R-02 п. 3.
3. Если находка только из-за `dp` (η в норме) — `est_saving = 0` → отбрасывается по `min_saving`, остаётся предупреждение в `evidence` (не создаётся).
Фикстура: `η_mean = 0,632`, `eta_norm = 0,70`, `airflow 32 000`, `T_in − T_out = 11,4`, `run_hours = 80`, `price_heat = 2,0722` → `loss_kw = 0,068 × 0,34 × 32 000 × 11,4/1 000 = 8,43`; `qty_window = 674,7`; `est_qty_month = 2 921,6 кВт·ч`; `est_saving = 6 054 ₴`.

**`dock_gates`** (тепло; требует точку `DOCK`): параметры `long_open_min=10`, `min_events_day=3`, `open_norm_min_day=20`, `lookback_days=7`, `min_saving_uah=500`; действие `link` на `td_yard.action_td_yard_gate` («Показати у «Дворі»»), если `td_yard` установлен, иначе запасное.
1. По сырым показаниям `state_signal` точки: «открытия» — непрерывные интервалы `≥ 0,5`; `long` — длительностью `≥ long_open_min`; среднее число `long` в сутки `< min_events_day` → `[]`.
2. `open_min_day` = среднее суммарное время открытия в сутки; `excess_h = max(0, open_min_day − open_norm_min_day)/60` в сутки.
3. `loss_kw_per_k × ΔT_mean = loss_kw` (средняя разница температур окна); `qty_window = loss_kw × excess_h × L`; `est_qty_month = qty_window × K_month`; `price_heat` — R-02 п. 3.
Фикстура: `long = 4/сут`, `open_min_day = 52`, `norm 20`, `loss_kw_per_k = 3,5`, `ΔT = 11`, `L = 7`, `price_heat = 2,0722` → `excess_h = 0,5333`; `loss_kw = 38,5`; `qty_window = 38,5 × 0,5333 × 7 = 143,7`; `est_qty_month = 622,3 кВт·ч`; `est_saving = 1 290 ₴`.

### R-B5 Backfill тепла (хук `_td_backfill_extra`)

Генераторы (дополняют R-22): `HM-BOILER = heat_boiler` (R-22 п. 2, «газ»); `HM-CHP = 497 кВт`, когда КГУ работает; `HM-RV = 0,585 × heat_need`; `HM-AHU1 = 0,19 × heat_need`; оценки `HM-DOCK`, `HM-OFFICE` — R-04 (для `DOCK` без сырых показаний слоты `missing`, поэтому в backfill `HM-DOCK` генерируется напрямую: `open_frac = 0,05` в смену, 0 вне смен, `rate_kw = 3,5 × ΔT × open_frac`). Нужна температура: `t_out(d, h) = 7,0 + 8·cos(2π(doy − 200)/365) + 3·sin(π(h − 9)/12)` (демо-приближение; квалитет `estimated`).

## B.5 Acceptance Criteria — AC-B01…AC-B10

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-B01 | FR-B1 | Given `td_bms` с `td.bms.heat.balance` и 26 установками (RV + AHU-1); When установка моста; Then точки `HEAT-BOILER`, `HEAT-CHP`, `RV-ALL`, `AHU-1`, `OFFICE` (+ `DOCK` при наличии сигнала ворот) и счётчики `HM-*` созданы; `HM-RV.flow_signal_ids` = 25 сигналов; повторный `_td_bind_extra` — без дублей и без перезаписи ручных правок | UT |
| AC-B02 | FR-B1 | Given мост установлен до/после `td_bms` (порядок установки обоих модулей); Then результат одинаков (`auto_install` срабатывает при появлении второго) | UT + DEPLOY_TEST |
| AC-B03 | FR-B2 | Given фикстура (`boiler_heat 390`, `RV 228`, `AHU 74`, `DOCK 46`); Then `power.value=390`, note «подача 70 °C · зворот 52 °C»; список: `RV-ALL 228`, `AHU-1 74`, `DOCK 46`, `OFFICE 42` | UT |
| AC-B04 | FR-B2 | Given фикстура R-B3 (32 000 м³/ч, 74 кВт, 21,0/18,4/7,0); Then `recovery.value=63` (63,2), tone `bad`, `quality='estimated'`, note «норма ≥ 70 %» (+ « · фільтр брудний» при ΔP 280 Па); `T_in − T_out < 5` → `null`, `η ∉ [0,1]` → `null` | UT |
| AC-B05 | FR-B2 | Given `indoor_c` установок и `t_in_set=18`; Then `indoor.value` = среднее, note «уставка 18 °C · зовні 7 °C», tone `good` при отклонении ≤ 1 К; `_td_heat_chart_note` подставляет `{capacity}` из баланса | UT |
| AC-B06 | FR-B3 | Given фикстура `preheat_early` (`margin_med 55`, `margin_min 30`, 46 м³/ч, 5 дней, 19,80); Then `est_qty_month = 415,0 м³`, `est_saving = 8 216`; `margin_med ≤ margin_min` → `[]`; дней < 3 → `[]` | UT |
| AC-B07 | FR-B3 | Given фикстура `ahu_recuperation` (η 0,632; норма 0,70; 32 000; ΔT 11,4; 80 ч; 2,0722); Then `est_saving = 6 054`; находка только по ΔP → не создаётся | UT |
| AC-B08 | FR-B3 | Given фикстура `dock_gates` (4/сут; 52 мин; норма 20; 3,5 кВт/К; ΔT 11); Then `est_saving = 1 290`; `long < 3/сут` → `[]`; нет точки `DOCK` → правило пропущено без ошибки | UT |
| AC-B09 | FR-B1 | Given backfill тепла; Then `HM-BOILER ≈ gas·10,5·0,914` ± 3 %; `Σ ветвей` ≈ источников ± 5 %; идемпотентность и `purge` как AC-47 | UT |
| AC-B10 | FR-B2 | Given стенд, мост установлен; When открыть «Тепло»; Then 4 KPI, список «Куди йде тепло», подпись «оцінка» у «Рекуперація AHU-1»; график без линии лимита, `chart_note` содержит «котли {capacity} кВт» | TC (ТК-B1) |

**Итого мост: AC-B01…AC-B10 = 10 критериев (UT 8, UT+DEPLOY_TEST 1 (AC-B02), TC 1 (AC-B10)).**

Тесты моста: `tests/test_wb_bridge.py::TestWbBridge` (AC-B01…AC-B09), `tests/stand/test_wb_tk.py` (ТК-B1 = AC-B10). Команда: `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3b /td_energy_resources_bms`.

### Решения автора и вопрос моста

| ID | Решение | Обоснование |
|---|---|---|
| A-B1 | Тепловые точки создаются кодом (`_td_bind_extra`), а не XML | зависят от сигналов и установок BMS конкретной базы |
| A-B2 | `η` рекуперации — оценка по тепловому балансу установки; сигнал вытяжки зарезервирован (`extract_c`) | датчика вытяжки в BMS нет (GAP §4.4 п. 5) |
| Q-B1 | Добавить датчик температуры вытяжки AHU-1 в BMS (для измеряемой рекуперации) | рекомендация: да; пока оценка |
