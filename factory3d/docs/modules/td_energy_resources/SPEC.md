# td_energy_resources — специфікація (W3 «Енергоресурси»: ядро ресурсів; міст до BMS — `td_energy_resources_bms`)

Версія 0.2 · 19.10.2026 (v0.1 — 18.10.2026) · стандарт `docs/DOC_STANDARD.md` · технічне рішення: [ARCHITECTURE.md](ARCHITECTURE.md) (далі ARCH: FR-01…FR-24 і FR-B1…FR-B3, A-01…A-16, Q-01…Q-08) · статус: збудовано (гілка `claude/td-energy-w4`); відхилення збірки — у «Журналі змін документа» в кінці файлу.
Вхід: `build/energy/GAP.md` (E-01…E-11, §4, §5.3, RS-01…RS-15), макет `Resources.dc.html`; контракти W1: `W1_SPEC.md` (M-26 `td.energy.advice.actions[]` = C-32, API-05, R-27, R-33, R-36, UI-10) і код `td_energy` на гілці `claude/factory3d-build` (`d14d13c`, W1 реалізовано).
Спирається на: `docs/ARCHITECTURE.md` §3 (граф), §5 (конвенції), §6.4 (телеметрія), D-18 (необов'язкові зв'язки через `env.get` і міст `auto_install`); `td_energy` (M-01…M-28, R-04, R-15, `tools/counter.py`, `tools/backfill.py`); `td_telemetry` (`td.signal`, `td.reading`, `td.reading.hour`, CT-10); `td_bms` (`td.bms.heat.balance`, `td.bms.hvac.unit`); `td_iot_sim` і `services/iot_sim`.
Мова: проза — українською (`docs/DOC_STANDARD.md`), рядки інтерфейсу, `string=` полів і тексти помилок — українські (як у W1 і в макеті).
Документ розкладено за модулями: `td_energy_resources` (цей файл — Частина I вихідного `W3_SPEC.md`) і міст `td_energy_resources_bms` ([SPEC.md](../td_energy_resources_bms/SPEC.md) — Частина II).

## Умовні позначення, діапазони ID, відхилення від макета

**Імена (E-09).** Усе в td-іменах. Модулі: `td_energy_resources` (ядро ресурсів), `td_energy_resources_bms` (міст до `td_bms`, `auto_install`). Моделі `td.energy.*`; поля стандартних моделей — `td_*`; нові методи — `_td_*` (наявні `_td_*` викликаються як у коді). Параметри `ir.config_parameter` — `td.energy_resources.<param>` (конвенція §5: `td.<module>.<param>`; глобальні стоп-крани `td.energy.read_enabled` спільні). Маршрути `/f3d/*` і коди сигналів не змінюються; новий маршрут — `/td/energy/resources/export` (A-10).

**Діапазони ID.** Нумерація модульна: новий модуль починає з 01; між модулями номери перетинаються, тому поза таблицями ID пишеться з модулем: `td_energy_resources M-03`. Міст — префікс `B`. Наскрізні для блоку «Енергетика»: D-xx (нижче), щоб не перетинатися з W1 (D-01…D-18) і W2 (резерв D-19…D-30): W3 бере **D-31…D-50**, W4 — D-51…D-80.

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
| A (рішення автора) | A-01…A-16 | A-B1…A-B2 |
| Q | Q-01…Q-08 | Q-B1 |
| C (контракти) | C-01…C-06 | — |

Позначення: UT — юніт-тест `odoo.tests` (`TransactionCase`/`HttpCase`), UT-JS — hoot-тест (`web.assets_unit_tests`), TC — стенд (емулятор + збирач + Odoo), MAN — ручна перевірка. `req`=`required=True`, `idx`=`index=True`, `cost` у «Параметри» = `groups="td_energy.group_td_energy_cost"`. Усі `Datetime` — UTC naive; «Київ» — `Europe/Kyiv` (`td_energy/tools/dates.py`). Слот = 15 хвилин за UTC-сіткою; доба, зміна, «ніч» — за київським часом. Одиниці величин: ресурсо-орієнтовані (кВт·год, м³, норм. м³), «швидкість» (rate) — кВт, м³/год, м³/хв.

### Відхилення від макета (D-xx)

| ID | Де в макеті | Що в реалізації | Чому |
|---|---|---|---|
| D-31 | Шапка: «Сьогодні разом: 65 156 ₴ за електрику, газ і воду · тепло й стиснене повітря вже враховані в газі й електриці» | Формат: «Сьогодні разом: {сума} ₴ · {назви ресурсів з is_derived=False через «, »}. Похідні не додаються: {назви похідних}.» Сумується вартість ресурсів з `is_derived=False`; без групи вартості — «Сьогодні: {n} ресурсів» без ₴ | Відмінювання назв програмно неможливе; склад ресурсів конфігурований (A-12) |
| D-32 | Підписи вкладок «358 кВт · 52 786 ₴», «390 кВт · з BMS» | Підпис = поточна швидкість + вартість за сьогодні; для ресурсу з `show_tab_cost=False` (тепло) замість ₴ — `source_note` («з BMS»); без групи вартості — лише швидкість | Макет |
| D-33 | Підписи під графіками — готова проза | Генеруються за даними (R-10): пік, початок експорту, нічна витрата, «норма/вище норми»; шаблони — в `td.energy.resource.foot_template` | У макеті текст статичний, а цифри живі |
| D-34 | Демо-числа (вода 0,4 м³/год, 4,2 м³; газ 46 м³/год) | Екран показує дані емулятора/історії; арифметика макета (6 284 × 8,40 = 52 786 ₴; 612 × 19,80 = 12 118 ₴; 4,2 × 60 = 252 ₴; сума 65 156 ₴) відтворюється лише у фікстурах AC; на стенді числа інші (вода емулятора 2,1 м³/год у зміну, R-23) | В емулятора й макета різні профілі |
| D-35 | Газ: «ККД котельні 91,4 %», котельня на газі | Газовий канал котельні в демо — сигнал емулятора `equipment/BOILER/gas_m3h` (E-07), хоча фізична модель `BOILER` в `iot_sim` — брикетна (`silo_fill`, `boiler.py`); бункер не змінюється; η = тепло котлів / (газ × теплотворність) | E-07; Q-01 (паливо реального об'єкта) |
| D-36 | Тепло: «Рекуперація AHU-1 64 %» | Оцінка за тепловим балансом установки (R-B3), бейдж «оцінка»; немає сигналів — «—». Датчика витяжки в BMS немає | GAP §4.4 |
| D-37 | «Куди йде тепло»: «Втрати через ворота», «Офіс і побутові» | `DOCK` — оцінка за сигналом відкриття воріт (`gate_loss`), точка створюється, лише якщо є сигнал; `OFFICE` = залишок (≥ 0). Ворота `td.yard.gate` — шлагбауми, не докові ворота (Q-08) | Немає датчиків доків |
| D-38 | Примітка над графіком: «2 × Atlas Copco GA 37 VSD+», «ліміт години — 80 м³/год» | Зберігається в `td.energy.resource.chart_note` (шаблон із `{limit}`, `{contract}`, `{capacity}`) | Конфігуровано |
| D-39 | Вода: список споживачів у м³ за день, решта — у швидкості | Збережено: `resource.list_basis` = `qty_day` (вода) / `rate` (решта) | Як у макеті |
| D-40 | «Що помітила система» — 2 нотатки на вкладці «Електрика» | На вкладці — усі відкриті резерви ресурсу (зокрема `vent_offshift`, `idle_machines` на «Електрика»); кнопка = дія з контракту C-32; без `td_energy_control` дії `control` приховані й показується запасна дія «Відкрити» (картка резерву) | Макет спрощений: в аналітиці ті самі 8 правил |
| D-41 | «Вивантажити в Excel» (тост) | Реальний xlsx за вибрану добу (за замовчуванням сьогодні), 15-хв інтервали всіх ресурсів; вартість — лише з групою | RS-15 |
| D-42 | Фіксовані поділки осей (900/90/600/15/1) | Поділки обчислюються: `y_max = nice_ceil(1,1·max(limit, peak))`, три рівні поділки | Дані різного масштабу |
| D-43 | Вкладка «Тепло» без лінії ліміту | Без лінії; потужність котлів (`capacity_kw` з `td.bms.heat.balance`) — у `chart_note` | GAP §4.4 п. 3 пропонував лінію; макет її не містить |
| D-44 | «Реактивна енергія… tg φ 0,40 · ризик доплати» | «ризик доплати» показується лише якщо в тарифі задано `tg_phi_limit > 0` і фактичний tg φ вищий; інакше нотатка «tg φ {x}» без тону | Q-03 (договір невідомий) |
| D-45 | «Найбільші споживачі зараз» на «Електрика» | Жива `p_now` споживачів (як у Пульті W1); на решті вкладок — виміряні/оцінені швидкості з крапкою якості («оцінка») | Немає підлічильників |
| D-46 | У навігації макета «Енергоресурси» — вкладка розділу | Пункт меню `td_energy.menu_td_energy` → «Енергоресурси» (клієнтська дія); налаштування — в «Налаштування» | W1 D-18 |
| D-47 | Правило «Ворота відвантаження відкриті довго» є на вкладці «Тепло», але не входить у 8 правил «Резерви економії» | Правило 9 (`dock_gates`) додано в дані моста; у W4 воно потрапляє в загальний список | Розбіжність усередині макета |
| D-48 | Завжди 5 вкладок | Вкладка прихована, якщо ресурс неактивний (`active=False`) або в нього немає жодного активного лічильника | Майданчик без повітря/газу |

---

# ЧАСТИНА I. `td_energy_resources`

## 0. Дерево файлів

Власники: **A** — шар даних, **B** — резерви (рушій, детектори) і міст, **C** — фронтенд, **D** — емулятор і контракт сигналів, **E** — API екрана й експорт (ARCH §6). Файли без літери — менеджер (каркас). Менеджер створює всі файли порожніми із заголовком-коментарем, зокрема `models/__init__.py`, `tools/detectors/__init__.py`, `controllers/__init__.py` із повним списком імпортів, — воркери ці `__init__.py` не правлять.

```
odoo_addons/td_energy_resources/
├── __manifest__.py                         (менеджер) розділ 1
├── __init__.py                             (менеджер) from . import models, controllers; from .hooks import post_init_hook, uninstall_hook
├── hooks.py                                A  post_init_hook (розд. 5.5: `_set_el_on_meters`, `_ensure_resource_signals`, `_seed_points_meters`, `_bind_react_signals`), uninstall_hook (5.6)
├── migrations/19.0.1.0.0/post-migration.py  A  заповнення `resource_id=el` у наявних лічильників (ідемпотентно)
├── models/
│   ├── __init__.py                         (менеджер)
│   ├── td_energy_resource.py               A  M-01
│   ├── td_energy_price.py                  A  M-02
│   ├── td_energy_point.py                  A  M-03
│   ├── td_energy_meter.py                  A  M-04 (_inherit)
│   ├── td_energy_tariff.py                 A  M-05 (_inherit)
│   ├── td_energy_res_interval.py           A  M-06 (+ крон, ротація, _td_backfill)
│   ├── td_energy_usage.py                  A  M-07 (SQL-view)
│   ├── td_energy_res_dashboard.py          E  M-08 (AbstractModel, API-01 + гаки)
│   ├── res_config_settings.py              A  M-11
│   ├── td_energy_opportunity_rule.py       B  M-09
│   └── td_energy_opportunity.py            B  M-10
├── controllers/
│   ├── __init__.py                         (менеджер)
│   └── export.py                           E  API-07 (xlsx)
├── tools/
│   ├── integrate.py                        A  R-03 (трапеція, покриття, мультисигнал)
│   ├── estimate.py                         A  R-04 (load_share, schedule, residual, gate_loss)
│   ├── build.py                            A  R-05 (порядок побудови слота)
│   ├── resource_data.py                    E  R-08…R-12, R-25 (збирання JSON екрана)
│   ├── shifts.py                           A  R-21 (вікна змін; контракт C-01 для W4)
│   ├── backfill_resources.py               A  R-22
│   └── detectors/
│       ├── __init__.py                     (менеджер)  реєстр `DETECTORS = {…}` рядком на детектор
│       ├── common.py                       B  R-14 (вікна, ціни, 4,33, схема параметрів)
│       ├── vent_offshift.py, idle_machines.py, air_leaks.py,
│       │   air_pressure.py, react_section.py, pv_export.py          B  R-15…R-20
├── data/
│   ├── td_energy_resource.xml              A  5 записів (noupdate=1)
│   ├── td_energy_price_data.xml            A  демо-ціни (газ 19,80; вода 60,00), noupdate=1
│   ├── resource_points.csv, resource_meters.csv   A  демо-точки й лічильники газу/повітря/води (розд. 5.3)
│   ├── ir_config_parameter.xml             A  12 параметрів (розд. 5.1)
│   ├── ir_cron.xml                         A  2 крони (розд. 6)
│   ├── neutralize.sql                      A  вимкнення кронів
│   ├── resource_signals.csv, resource_sources.csv   D  +10 сигналів, +2 джерела (розд. 5.4)
│   ├── opportunity_rules.xml               B  6 правил ядра (noupdate=1)
│   └── ir_cron_opportunity.xml             B  крон резервів
├── security/
│   ├── td_energy_resources_security.xml    A  record rules (розд. 4.3)
│   ├── ir.model.access.csv                 A  M-01…M-08, M-11
│   └── ir.model.access-opportunity.csv     B  M-09, M-10 (суфікс після «-» не впливає на модель, `odoo/tools/convert.py:722`)
├── static/src/resources/                   C  UI-01…UI-08: resources.js/.xml/.scss, tabs, kpis, chart, list, notes
├── static/tests/resources.test.js          C  hoot
├── views/
│   ├── td_energy_resources_views.xml       C  V-01…V-07, V-10, V-11 (дії, списки, форми)
│   ├── td_energy_opportunity_views.xml     C  V-08, V-09
│   ├── res_config_settings_views.xml       C  V-12
│   └── menus.xml                           C  V-13
└── tests/
    ├── common.py                           A  TestW3Common (фікстури)
    ├── test_w3_data.py, test_w3_integrate.py, test_w3_estimate.py, test_w3_cost.py, test_w3_usage.py,
    │   test_w3_backfill.py                                                            A
    ├── test_w3_dashboard.py, test_w3_export.py, test_w3_security.py                      E
    ├── test_w3_opportunity.py, test_w3_detectors.py      B
    ├── test_w3_ui.py, test_w3_hoot.py                    C  (HttpCase, hoot — за зразком `td_energy/tests/test_w1_hoot.py`)
    └── stand/test_w3_tk.py                               D  ТК-01…ТК-06 (pytest проти стенда)

odoo_addons/td_energy_resources_bms/           B  (міст, Частина II → [../td_energy_resources_bms/SPEC.md](../td_energy_resources_bms/SPEC.md))
services/iot_sim/                              D  (розд. 8)
odoo_addons/td_iot_sim/data/                   D  td_sim_signal.csv (+10 рядків), td_sim_scenario_resources.xml (новий)
```

Фікси за ownership: рядки сигналів для емулятора й для Odoo синхронізуються **лише** за таблицею розд. 5.4/8.1; `td_energy/data/energy_signals.csv`, `energy_sources.csv` не правляться (нові сигнали — у власних CSV модуля); `td_telemetry/data/signal_catalog.csv` не правиться.

## 1. Маніфест

- `name`: «Енергоресурси»; `version`: `19.0.1.0.0`; `author`: `ToDo`; `license`: `LGPL-3`; `category`: `Manufacturing/Maintenance`; `installable`: True; `application`: False.
- `depends`: `["td_energy"]` (транзитивно `td_telemetry`, `mrp_account`, `analytic`, `maintenance`, `mail`, `bus`). Жорстких залежностей від `td_bms`, `td_yard`, `td_genset` немає (D-18): зв'язки — через `env.get(...)` і міст.
- `external_dependencies`: `{"python": ["xlsxwriter"]}` (входить у залежності Odoo; використовується в API-07).
- `data` (порядок): `security/td_energy_resources_security.xml`, `security/ir.model.access.csv`, `security/ir.model.access-opportunity.csv`, `data/ir_config_parameter.xml`, `data/td_energy_resource.xml`, `data/td_energy_price_data.xml`, `data/opportunity_rules.xml`, `data/ir_cron.xml`, `data/ir_cron_opportunity.xml`, `views/td_energy_resources_views.xml`, `views/td_energy_opportunity_views.xml`, `views/res_config_settings_views.xml`, `views/menus.xml` (останнім).
- `assets`: `web.assets_backend`: `td_energy_resources/static/src/resources/**`; `web.assets_unit_tests`: `td_energy_resources/static/tests/**`.
- `post_init_hook`: `hooks.post_init_hook` (R-22 прим.: `_ensure_resource_signals`, `_seed_points_meters`, `_bind_react_signals`, `_set_el_on_meters`); `uninstall_hook`: `hooks.uninstall_hook` (розд. 5.6).
- CSV сигналів/джерел **не** входять у `data`: їх завантажує `hooks._ensure_resource_signals(env)` (ідемпотентно) — той самий прийом, що `_ensure_w1_signals` у `td_energy`.

## 2. Моделі

Загальне: усі моделі — `company_id` (крім довідника ресурсів і SQL-view); `_log_access=False` лише в `td.energy.res.interval`; `mail.thread` — у `td.energy.resource`, `.point`, `.opportunity`.

### M-01 `td.energy.resource` — ресурс (FR-01)

`_name = "td.energy.resource"`, `_description = "Енергетика: ресурс"`, `_inherit = ["mail.thread"]`, `_order = "sequence, id"`, `_rec_name = "name"`. Записи довідника — XML з xml-id `resource_el|gas|heat|air|water` (`noupdate="1"`); видалення записів `el` заборонено (`unlink` → `UserError("Ресурс «Електрика» видаляти не можна.")`).

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char | size=8, req, idx, «Код»; `UNIQUE(code)`; значення `el`, `gas`, `heat`, `air`, `water` (довільні коди дозволені) |
| `name` | Char | size=64, req, «Назва» |
| `sequence` | Integer | default 10 |
| `active` | Boolean | default True, tracking; архівування приховує вкладку (D-48) |
| `uom_label` | Char | size=16, req, «Одиниця кількості» («кВт·год», «м³», «норм. м³») |
| `rate_label` | Char | size=16, req, «Одиниця швидкості» («кВт», «м³/год», «м³/хв») |
| `rate_hour_factor` | Float | digits (8,3), req, default 1.0, «Швидкість → кількість за годину»: `qty_per_hour = rate × factor`; constraint `> 0`; el 1, gas 1, heat 1, air **60**, water 1 |
| `kwh_per_unit` | Float | digits (8,3), default 0, «кВт·год на одиницю» (газ 10,5; el/heat 1 незастосовно — 0 = «немає еквівалента»; kWh-eq для el і heat = qty, R-01) |
| `co2_kg_per_unit` | Float | digits (8,4), default 0, «кг CO₂ на одиницю» (el 0,37; gas 1,96; heat/air/water 0); Q-02 уточнення |
| `is_derived` | Boolean | default False, «Похідний (не додається до загальної вартості)» — heat, air |
| `in_energy_cost` | Boolean | default False, «Входить у вартість енергії (W4)» — el, gas |
| `show_tab_cost` | Boolean | default True, «Вартість у підписі вкладки» — heat False |
| `source_note` | Char | size=32, «Підпис замість вартості», heat «з BMS» |
| `price_source` | Selection | `tariff` (el), `price` (gas, water), `derived_gas` (heat), `derived_el` (air), `none`; req |
| `limit_kind` | Selection | «Вид ліміту» (`string="Вид ліміту"`): `none`/«Без ліміту», `fixed`/«Фіксований», `tariff_contract`/«Договірна потужність»; req, default `none`; el — `tariff_contract`, gas — `fixed` |
| `rate_limit` | Float | digits (10,2), «Ліміт швидкості» (gas 80; el — з тарифу `contract_kw`) |
| `daily_limit` | Float | digits (12,2), «Ліміт доби за договором» (gas 1 200 м³; 0 = немає) |
| `list_basis` | Selection | `rate` / `qty_day`; default `rate`; water `qty_day` (D-39) |
| `color` | Char | size=7, «Колір», el `#714B67`, gas `#b45309`, heat `#c2410c`, air `#0369a1`, water `#0f766e` (токени UI-11 W1 розширено) |
| `chart_title` | Char | size=64, «Заголовок графіка»: «Імпорт з мережі, кВт», «Витрата газу, м³/год», «Теплова потужність, кВт», «Витрата стисненого повітря, м³/хв», «Витрата води, м³/год» |
| `chart_note` | Char | size=128, шаблон: «ліміт — договірна {contract} кВт», «ліміт години — {limit} м³/год», «теплобаланс цеху з BMS · котли {capacity} кВт», «2 × Atlas Copco GA 37 VSD+», «ввід і підживлення котельні» |
| `list_title` | Char | size=64: «Найбільші споживачі зараз», «Споживачі газу», «Куди йде тепло», «Споживачі повітря зараз», «Споживачі води» |
| `foot_template` | Text | шаблон підпису під графіком (R-10), плейсхолдери `{peak_kw}`, `{peak_time}`, `{night}`, `{day}`, `{norm}`, `{export_time}` |
| `meter_ids` | One2many | `td.energy.meter.resource_id`, readonly |
| `meter_count`, `point_count` | Integer | compute |

Constraints: `_check_codes` (`^[a-z0-9_]{1,8}$`), `_check_el` (рівно один активний ресурс із `code='el'`: «Ресурс «Електрика» має бути єдиним.»), `limit_kind='fixed'` → `rate_limit > 0`.
Методи: `get_by_code(code)` (`api.model`, ormcache, `False` якщо немає); `_td_active_with_meters()` → записи, у яких є активний лічильник (R-12); `_td_rate_to_qty(rate, hours)`: `rate × rate_hour_factor × hours`.

### M-02 `td.energy.price` — ціна неелектричного ресурсу (FR-02)

`_name = "td.energy.price"`, `_description = "Енергетика: ціна ресурсу"`, `_inherit = ["mail.thread"]`, `_order = "resource_id, date_from desc"`.

| Поле | Тип | Параметри |
|---|---|---|
| `resource_id` | Many2one `td.energy.resource` | req, ondelete=restrict, idx, tracking; domain `price_source = 'price'` |
| `date_from` | Date | req, tracking |
| `date_to` | Date | tracking; порожнє — безстроково |
| `price` | Float | digits (12,4), req, `cost`, tracking, «Ціна за одиницю (₴)» |
| `currency_id` | Many2one `res.currency` | req, default валюта компанії |
| `company_id` | Many2one `res.company` | req, default `env.company` |
| `note` | Char | size=128 |
| `active` | Boolean | default True |

Constraints: `_check_resource` (ресурс не `el` — «Ціни електрики задаються в тарифі.»), `_check_period` (`date_to ≥ date_from`; періоди активних цін одного ресурсу й компанії не перетинаються — «Період ціни перетинається з іншою.»), `price ≥ 0`.
Метод `_td_price_at(resource, dt_local=None)` (`api.model`, контракт C-01): ціна на локальну дату; поза періодами → `0.0` (вартість 0, а не помилка); для `price_source='derived_gas'` → R-02 п. 3; для `el`/`derived_el`/`none` → `0.0` (вартість береться з тарифу або з електроінтервалів, R-02).

### M-03 `td.energy.point` — точка обліку (FR-03)

`_name = "td.energy.point"`, `_description = "Енергетика: точка обліку ресурсу"`, `_inherit = ["mail.thread"]`, `_order = "resource_id, sequence, code"`, `_parent_name = "parent_id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `resource_id` | Many2one `td.energy.resource` | req, idx, ondelete=restrict |
| `code` | Char | size=32, req, idx; `UNIQUE(resource_id, company_id, code)` |
| `name` | Char | size=128, req |
| `kind` | Selection | `source`/«Ввід (головний облік)», `branch`/«Гілка», `consumer`/«Споживач»; req, default `consumer` |
| `parent_id` | Many2one `td.energy.point` | ondelete=restrict; той самий ресурс (`_check_parent`: «Батько має бути з того самого ресурсу.»; без циклів — `_check_recursion`) |
| `sequence` | Integer | default 10 |
| `active` | Boolean | default True |
| `node_id` | Many2one `td.energy.node` | «Електричний вузол споживача» (для `load_share` і зіставлення з обладнанням); ondelete=set null |
| `cost_node_id` | Many2one `td.energy.node` | «Вузол, чия електрика формує вартість» (повітря: `COMPRESSOR`) |
| `equipment_id` | Many2one `maintenance.equipment` | ondelete=set null; default з `node_id.equipment_id` (onchange) |
| `workcenter_id` | Many2one `mrp.workcenter` | related `node_id.workcenter_id`, store=False |
| `rate_nominal` | Float | digits (10,3), «Паспортна швидкість при роботі» (повітря: м³/хв; газ: м³/год) — **ПРИПУЩЕННЯ** до появи паспортів (Q-02) |
| `min_pressure_bar` | Float | digits (5,2), «Мінімальний тиск споживача, бар» (повітря; R-18) |
| `hvac_ref` | Char | size=32, «Код установки BMS» (заповнює міст, M-B1) |
| `state_signal_id` | Many2one `td.signal` | сигнал стану/відкриття (для `gate_loss`) |
| `meter_ids` | One2many | `td.energy.meter.point_id` |
| `estimate_method` | Selection | `none`, `load_share`, `schedule`, `residual`, `gate_loss`; default `none` |
| `estimate_params` | Json | default `{}`; схема за методом (R-04): ключі й типи валідує `_check_estimate` |
| `company_id` | Many2one `res.company` | req, default `env.company` |

`estimate_method` і `estimate_params` у точки — для **оцінкового** лічильника (`mode='estimate'`) беруться звідси; поле дублюється на точці, а не на лічильнику, щоб метод описував сутність, а не канал (A-05). `_check_estimate`: `load_share` → `node_id` обов'язковий і `rate_nominal > 0`; `schedule` → `params.from_h/to_h/rate`; `residual` → `params.from` (непорожній список кодів точок того самого ресурсу, чиї швидкості сумуються як «прихід»); `gate_loss` → `state_signal_id` і `params.loss_kw_per_k`.
Метод-гак `_td_bind_extra()` (`api.model`; у ядрі повертає `{}`) викликається `post_init_hook` і серверною дією V-11 після `_seed_points_meters`; міст `td_energy_resources_bms` перекриває його (R-B1).

### M-04 `td.energy.meter` — розширення (`_inherit = "td.energy.meter"`; FR-04, FR-07)

Наявна модель `td_energy` (`td.energy.meter`; поля повірки додала W1 M-23) отримує:

| Поле | Тип | Параметри |
|---|---|---|
| `resource_id` | Many2one `td.energy.resource` | req, idx, ondelete=restrict, **default = `resource_el`** (xml-id), «Ресурс»; у наявних лічильників заповнюється міграцією (розд. 5.5) |
| `point_id` | Many2one `td.energy.point` | idx, ondelete=restrict; обов'язково при `resource_id.code != 'el'` |
| `mode` | Selection | `counter`/«Лічильник», `flow_integrate`/«Інтеграл витрати», `estimate`/«Оцінка»; default `counter`; req |
| `qty_signal_id` | Many2one `td.signal` | сигнал лічильника обсягу/енергії (режим `counter` для не-el) |
| `flow_signal_ids` | Many2many `td.signal` | rel `td_energy_meter_flow_signal_rel`; сигнали швидкості; режим `flow_integrate`: сумуються (R-03 п. 5) |
| `max_rate` | Float | digits (12,3), default 0, «Макс. швидкість (од. ресурсу/год) для скидань лічильника»; 0 = за замовчуванням `rate_nominal` точки або 1000 |
| `e_react_signal_id` | Many2one `td.signal` | «Реактивна енергія, квар·год» — лише `role='incomer'` електричних лічильників (FR-07) |
| `res_last_interval_start` | Datetime | readonly, «Останній інтервал ресурсу» (не плутати з `last_interval_start` електрики) |

Зміна наявного поля: `node_id = fields.Many2one(required=False)` (у базі `required=True`); нова перевірка `_check_resource_binding` (`api.constrains('resource_id','node_id','point_id','mode', …)`):
- `resource.code == 'el'` → `node_id` обов'язковий («Для електричного лічильника потрібен вузол.»), `point_id` порожнє, `mode='counter'`;
- інакше → `point_id` обов'язковий («Для лічильника ресурсу потрібна точка обліку.»); `node_id` порожнє допускається; `e_import_signal_id`/`e_export_signal_id` мають бути порожні («Електричні сигнали лише для ресурсу «Електрика».»);
- `mode='counter'` (не-el) → `qty_signal_id` обов'язковий; `flow_integrate` → `flow_signal_ids` непорожнє; `estimate` → у точки `estimate_method != 'none'`;
- `e_react_signal_id` допустимий лише при `role='incomer'` і ресурсі `el`.

Додаткові зміни наявних полів і методів (усі потрібні, щоб код `td_energy` не ламався на лічильниках без вузла й електричних сигналів):
- `role`: `selection_add [("resource", "Ресурс")]`; для не-el обов'язково `role = 'resource'`, для `el` — будь-яка роль, крім `resource` (`_check_resource_binding`); наявні вибірки за `role` (`incomer`, `feeder`, `consumer`, `generation`, `storage`) `resource`-лічильники не зачіпають;
- `model`: для не-el `model = 'other'` (у `_check_resource_binding`; сидом задається явно); значення `pm5560`/`sun2000`/… лишаються лише електричним;
- `company_id`: перевизначається як `compute` store `node_id.company_id or point_id.company_id or env.company` (у базі — `related='node_id.company_id'`, для не-el був би порожній);
- `_td_update_state()`: `cron_td_energy_live` (W1) викликає його для **всіх** активних лічильників (`td_energy_node_live.py:165`); перевизначення викликає `super()` для `resource_id.code == 'el'`, а для не-el рахує `data_state` сам: `counter` — за `qty_signal_id`, `flow_integrate` — за `flow_signal_ids` (свіжість: `last_ts ≥ now − 3·period_s`; несвіжий хоча б один — `stale`; немає показань — `no_data`), `estimate` — за останнім слотом (`stale`, якщо останній побудований слот старший за 30 хв; `gap`, якщо за 2 год є `missing`/`interpolated`), інакше `ok`; події `meter` для не-el **не** створюються (A-14);
- `last_value`, `last_ts` (related `e_import_signal_id`) у не-el порожні — екран ресурсів їх не використовує (бере сигнали за R-08).

Критично для регресії `td_energy` (A-02): усі решта вибірок лічильників (`td.energy.interval._cron_build`, `tools/backfill.Plan`, баланс, `_td_shift_kwh`) шукають за `e_import_signal_id != False` або за ролями; у не-el лічильників `e_import_signal_id` порожній, тому вони з електричних розрахунків виключені без правки коду `td_energy`. AC-05 і AC-06 це перевіряють: тести `td_energy` (142) і W1 запускаються на БД із 16 неелектричними лічильниками.

### M-05 `td.energy.tariff` — розширення (`_inherit`; FR-21, Q-03)

| Поле | Тип | Параметри |
|---|---|---|
| `tg_phi_limit` | Float | digits (4,2), default 0, `cost`, «Допустимий tg φ (0 — доплати немає)» |
| `react_rate` | Float | digits (10,4), default 0, `cost`, «Ставка за реактивну енергію понад ліміт, ₴/квар·год» |

Constraint: `tg_phi_limit ≥ 0`, `react_rate ≥ 0`; `react_rate > 0` при `tg_phi_limit = 0` → `ValidationError("Ставка без ліміту tg φ не має сенсу.")`. Метод `_td_react_penalty(excess_kvarh)` → `excess × react_rate` (0, якщо ліміт не задано).

### M-06 `td.energy.res.interval` — 15-хвилинний ряд неелектрики (FR-05, FR-07)

`_name = "td.energy.res.interval"`, `_inherit = ["td.energy.day.mixin"]` (фільтри «Сьогодні/Вчора/7 днів» з `td_energy`), `_description = "Енергетика: 15-хвилинний інтервал ресурсу"`, `_order = "ts_start desc, meter_id"`, `_log_access = False`, `_rec_name = "ts_start"`.

| Поле | Тип | Параметри |
|---|---|---|
| `meter_id` | Many2one `td.energy.meter` | req, ondelete=cascade, idx |
| `resource_id` | Many2one | related `meter_id.resource_id`, store, idx |
| `point_id` | Many2one `td.energy.point` | related `meter_id.point_id`, store, idx |
| `metric` | Selection | `main`/«Основна», `react`/«Реактивна»; req, default `main` (A-04); `react` — лише для електричних вводів (kvarh) |
| `ts_start`, `ts_end` | Datetime | req; `ts_start` idx |
| `day` | Date | req, idx (Київ); `hour_local` Integer req |
| `qty` | Float | digits (14,3), «Кількість (од. ресурсу)» |
| `rate_avg` | Float | digits (12,3), «Середня швидкість» |
| `kwh_eq` | Float | digits (14,3), «кВт·год-еквівалент» (R-01; для повітря й води — 0) |
| `price` | Float | digits (12,4), `cost` |
| `cost` | Float | digits (14,2), `cost` |
| `quality` | Selection | `measured`, `estimated`, `interpolated`, `missing`; req, default `measured`, idx |
| `built_at` | Datetime | req |
| `is_backfill` | Boolean | default False, idx, readonly |

`_td_res_interval_uniq = models.Constraint("UNIQUE(meter_id, metric, ts_start)", "Інтервал ресурсу для лічильника вже є.")`. `init()`: індекс `(day, resource_id)`; індекс `(point_id, ts_start)`.
Методи: `_cron_build()` (R-05), `_cron_rotate()`, `_td_backfill(days=90, until=None, seed=20261018, purge=False, resources=None)` (R-22; API-08; доступ — `env.is_superuser()` або `td_factory3d.group_td_admin`, інакше `AccessError("Генерувати історію може лише адміністратор.")`).

### M-07 `td.energy.usage` — зведення (SQL-view; FR-06)

`_name = "td.energy.usage"`, `_description = "Енергетика: зведення використання"`, `_auto = False`, `_order = "ts_start desc"`. Створюється в `init()` через `tools.drop_view_if_exists` + `CREATE VIEW`. Ідентифікатор рядка — **без** `row_number()` (щоб Postgres проштовхував фільтри): `id = i.id * 2` для електричних рядків, `id = r.id * 2 + 1` для ресурсних.

| Поле | Тип | Значення |
|---|---|---|
| `resource_id` | Many2one `td.energy.resource` | `el` для електричних рядків |
| `flow` | Selection | `import`, `export`, `generation`, `load` (електрика); `supply`, `branch` (ресурси) — семантика R-07 |
| `ts_start` | Datetime | |
| `day`, `hour_local` | Date, Integer | |
| `node_id` | Many2one `td.energy.node` | електричні рядки |
| `point_id` | Many2one `td.energy.point` | ресурсні рядки |
| `meter_id` | Many2one `td.energy.meter` | |
| `qty` | Float | в одиницях ресурсу (`el` — кВт·год) |
| `kwh_eq` | Float | R-01 |
| `cost` | Float | `cost`; `import`, `supply`, `branch` — за R-02; `load`, `generation`, `export` — 0 |
| `co2_kg` | Float | `qty × resource.co2_kg_per_unit` для `import` і `supply`; інакше 0 |
| `quality` | Char | |
| `is_backfill` | Boolean | |

Рядки: `td_energy_interval` із `role='incomer'` → `import` (`qty = kwh`) і `export` (`qty = kwh_export`, якщо `> 0`); `role='feeder'` → `load`; `role='generation'` → `generation`; `td_energy_res_interval` із `metric='main'` і `point.kind='source'` → `supply`, решта → `branch`. Ролі `consumer`, `storage`, `metric='react'` у view **не** входять (A-03). Вартість і CO₂ — лише для `import`/`supply`; `groups="td_energy.group_td_energy_cost"` на `cost`.

### M-08 `td.energy.res.dashboard` — API екрана (AbstractModel; FR-08…FR-12)

`_name = "td.energy.res.dashboard"`, `_description = "Енергетика: дані екрана ресурсів"`. Доступ: `_td_check_access()` — `group_td_energy_user` або суперкористувач, інакше `AccessError("Немає доступу до Енергетики.")`; сигнали, показання, інтервали читаються через `sudo()`; ключі вартості без `group_td_energy_cost` **видаляються** з відповіді (як у W1 M-27). Методи — API-01. Гаки (порожні в ядрі; перекриває міст, C-04):

| Гак | Сигнатура | В ядрі |
|---|---|---|
| `_td_heat_kpis` | `(self, ctx) -> list[dict]` | `[]` — KPI «Температура в цеху», «Рекуперація AHU-1» |
| `_td_heat_list` | `(self, ctx) -> list[dict] \| None` | `None` — «Куди йде тепло» з BMS |
| `_td_heat_chart_note` | `(self, ctx) -> str \| None` | `None` — підстановка `{capacity}` |
| `_td_resource_extra` | `(self, code, ctx) -> dict` | `{}` — додаткові блоки відповіді |

### M-09 `td.energy.opportunity.rule` — правило резерву (FR-13, FR-14)

`_name = "td.energy.opportunity.rule"`, `_description = "Енергетика: правило резерву економії"`, `_order = "sequence, code"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char | size=32, req, `UNIQUE(code)`; = ключ детектора |
| `name` | Char | size=128, req, «Назва» |
| `sequence` | Integer | default 10 |
| `enabled` | Boolean | default True, «Увімкнено» |
| `resource_id` | Many2one `td.energy.resource` | req, «Вкладка, де показується» |
| `lookback_days` | Integer | default 7, constraint `1…60` (сирі показання зберігаються 30 діб, `td.telemetry.keep_days`) |
| `min_saving_uah` | Float | default за правилом, `cost` — мінімальна оцінка ₴/міс |
| `params` | Json | default з XML; пороги (R-14) |
| `params_schema` | Json | список `{key, label, type: float\|int\|bool, min, max, unit, default}`; редагується лише розробником (`noupdate`) |
| `actions` | Json | default `[]`; **контракт C-32** (W1 M-26): `{code, label, kind: link\|ticket\|control, class: null\|A\|B, params}` |
| `fallback_action` | Json | default `{"code":"open","label":"Відкрити","kind":"link","params":{"xmlid":"td_energy_resources.action_td_energy_opportunity"}}` |
| `control_intent` | Char | size=48, «Намір керування» (непрозорий ключ для W2: `vent_night_mode`, `heat_schedule_shift`, `air_pressure_setpoint`, `pv_self_consumption`; порожньо — дії `control` немає); W3 його не інтерпретує (C-02) |
| `cooldown_days` | Integer | default 14 — після `done` повторне створення не раніше |
| `dismiss_days` | Integer | default 30 — після `dismissed` не створювати |
| `requires` | Char | size=64, «Потрібні модулі/сигнали» (текст для підказки в UI; приклад: `td_bms`) |
| `last_run`, `last_count`, `last_error` | Datetime / Integer / Char | readonly |
| `company_id` | Many2one `res.company` | default `env.company` |

Constraints: `_check_params` (кожен ключ із `params_schema` присутній, тип і діапазон вірні: `ValidationError("Параметр %s: очікується %s у діапазоні %s…%s.")`), `_check_actions` (для кожного елемента `kind ∈ {link, ticket, control}`, `code` за `^[a-z0-9_]{1,32}$`, `label` ≤ 48).
Методи: `_td_detector_methods()` — реєстр `tools/detectors.DETECTORS` + методи моста (`_td_detect_<code>` в `_inherit` моделі, A-08); `action_run()` (`group_td_energy_manager`; запускає одне правило, як крон, і повертає статистику); `_td_detect(now)` → список знахідок (R-14).

### M-10 `td.energy.opportunity` — резерв економії (FR-13…FR-15)

`_name = "td.energy.opportunity"`, `_description = "Енергетика: резерв економії"`, `_inherit = ["mail.thread"]`, `_order = "in_plan desc, est_saving_month desc, id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `rule_id` | Many2one `td.energy.opportunity.rule` | req, idx, ondelete=restrict |
| `resource_id` | Many2one | related `rule_id.resource_id`, store, idx |
| `dedup_key` | Char | size=96, idx, req: `<rule.code>:<scope>` (`vent_offshift:*`, `ahu_recuperation:AHU-1`); `UNIQUE(dedup_key) WHERE state = 'open'` — частковий індекс у `init()` |
| `title` | Char | size=160, req |
| `text` | Text | req |
| `est_saving_month` | Float | digits (14,2), `cost`, «Економія, ₴/міс» |
| `est_qty_month` | Float | digits (14,2), «Економія в од. ресурсу/міс» |
| `evidence` | Json | default `{}`; числа, на яких побудована оцінка (R-14) |
| `state` | Selection | `open`/«Відкрите», `done`/«Виконано», `dismissed`/«Відхилено», `expired`/«Втратило актуальність»; default `open`, idx, tracking |
| `in_plan` | Boolean | default False, idx, tracking, «У плані» (A-07: окремо від `state`) |
| `plan_user_id`, `plan_date` | Many2one `res.users` / Date | readonly |
| `found_at`, `last_seen_at` | Datetime | readonly |
| `node_id` | Many2one `td.energy.node` | ondelete=set null |
| `point_id` | Many2one `td.energy.point` | ondelete=set null |
| `request_id` | Many2one `maintenance.request` | ondelete=set null, readonly |
| `actions` | Json | копія `rule.actions` з підставленими параметрами (`node_code`, `description` із тегом `[OPP-<id>]`) |
| `result_note` | Char | size=256 |
| `resolved_at`, `resolved_by` | Datetime / Many2one `res.users` | readonly |
| `company_id` | Many2one `res.company` | default `env.company` |

Методи (API-02…API-06, R-13): `get_list(resource_code=None, states=("open",))`, `get_plan_summary()`, `action_plan_toggle(plan=None)`, `action_dismiss()`, `action_done(note=None)`, `_cron_detect()`, `_td_link_requests()`. Права: читання — `group_td_energy_user`; `action_plan_toggle/dismiss/done` — `group_td_energy_manager`, інакше `AccessError("Керувати резервами може лише енергетик.")`.

### M-11 `res.config.settings` — розширення

Поля `td_energy_resources_*` із `config_parameter` (розд. 5.1), блок `app name="td_energy_resources"` не створюється — група «Енергоресурси» додається в блок `td_energy` (V-12). `set_values` валідує `night_from_h < 24`, `night_to_h`, `gap_max_s ≥ 300`, `min_coverage ∈ (0,1]`.

## 3. Представлення й меню

### 3.1 Представлення V-01…V-13

| ID | XML-id (`td_energy_resources.`) | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `action_td_energy_resources` | `ir.actions.client`, `tag="td_energy_resources.resources"`, `name="Енергоресурси заводу"`, `context={"td_energy_resource": "el"}` | UI-01 |
| V-02 | `view_td_energy_resource_list` / `_form`, `action_td_energy_resource` | list/form `td.energy.resource` | list: `sequence` (handle), `code`, `name`, `uom_label`, `rate_label`, `is_derived`, `active`; form: групи «Одиниці» (`uom_label`, `rate_label`, `rate_hour_factor`, `kwh_per_unit`, `co2_kg_per_unit`), «Вартість» (`price_source`, `is_derived`, `in_energy_cost`, `show_tab_cost`, `source_note`), «Ліміти» (`limit_kind`, `rate_limit`, `daily_limit`), «Екран» (`color`, `chart_title`, `chart_note`, `list_title`, `list_basis`, `foot_template`); smart-кнопки «Лічильники», «Точки», «Ціни»; редагування — `group_td_energy_manager` |
| V-03 | `view_td_energy_price_list` / `_form`, `action_td_energy_price` | `td.energy.price` | list: `resource_id`, `date_from`, `date_to`, `price` (`cost`), `currency_id`; групування за ресурсом; без групи вартості ціна прихована |
| V-04 | `view_td_energy_point_list` / `_form` / `_search` / `_kanban`, `action_td_energy_point` | `td.energy.point` | list із групуванням за ресурсом і `kind`, колонки `code`, `name`, `kind`, `parent_id`, `node_id`, `estimate_method`, `meter_ids` (віджет `many2many_tags`; замість обчислюваного `meter_count` — у збірці лічильники показано тегами); form: вкладки «Облік» (`kind`, `parent_id`, `meter_ids`), «Оцінка» (`estimate_method`, `estimate_params` JSON, `rate_nominal`, `min_pressure_bar`, `state_signal_id`), «Зв'язки» (`node_id`, `cost_node_id`, `equipment_id`, `hvac_ref`), чаттер |
| V-05 | `view_td_energy_meter_form_resources` (успадковує `td_energy.view_td_energy_meter_form`), `view_td_energy_meter_list_resources`, `action_td_energy_meter_resources` | `td.energy.meter` | у формі: група «Ресурс» (`resource_id`, `point_id`, `mode`, `qty_signal_id`, `flow_signal_ids`, `max_rate`; `invisible="resource_id.code == 'el'"` для неелектричних полів), поле `e_react_signal_id` — `invisible="role != 'incomer'"`; `node_id` — `required="resource_id.code == 'el'"`; дія `action_td_energy_meter_resources`: domain `[("resource_id.code", "!=", "el")]`, list-колонки `code`, `point_id`, `mode`, `data_state`, `res_last_interval_start`, `next_verification` (optional) |
| V-06 | `view_td_energy_res_interval_list` / `_pivot` / `_graph` / `_search`, `action_td_energy_res_interval` | `td.energy.res.interval` | readonly; list: `ts_start`, `meter_id`, `qty`, `rate_avg`, `quality` (badge), `cost` (`cost`), `is_backfill` (optional hide); pivot: рядки `day`, стовпці `resource_id`, міра `qty`; search: «Сьогодні», «Вчора», «Синтетичні», групування `resource_id`, `point_id`, `quality` |
| V-07 | `view_td_energy_usage_pivot` / `_graph` / `_search`, `action_td_energy_usage` | `td.energy.usage` (readonly) | pivot: рядки `day`, стовпці `flow`, міра `qty`, `cost`; graph: bar за `day`; search за `resource_id`, `flow`, `is_backfill`; меню — лише `group_td_energy_manager` |
| V-08 | `view_td_energy_opportunity_rule_list` / `_form`, `action_td_energy_opportunity_rule` | `td.energy.opportunity.rule` | list: `sequence`, `code`, `name`, `resource_id`, `enabled` (toggle), `lookback_days`, `min_saving_uah`, `last_run`, `last_count`; form: `enabled`, `resource_id`, `lookback_days`, `min_saving_uah`, `cooldown_days`, `dismiss_days`, блок «Пороги» (`params` — JSON-редактор + таблиця `params_schema` readonly), блок «Дії» (`actions`, `fallback_action`), кнопка «Запустити зараз» — `type="action"` на серверну дію `action_td_energy_opportunity_rule_run`, бо `action_run` повертає словник статистики (API-05): серверна дія викликає `action_run` і загортає статистику в сповіщення `display_notification`; створювати/видаляти — `group_td_admin` |
| V-09 | `view_td_energy_opportunity_list` / `_form` / `_search` / `_kanban`, `action_td_energy_opportunity` | `td.energy.opportunity` | list: `in_plan` (toggle-чекбокс), `title`, `resource_id`, `est_saving_month` (`cost`), `state` (badge: open — warning, done — success, dismissed — muted, expired — muted), `request_id`; form: статусбар `state`; кнопки «У план / З плану» (`action_plan_toggle`), «Відхилити», «Виконано» (wizard примітки → `action_done`); вкладка «Підстава» (`evidence` JSON) і «Дії» (`actions`); search: «Відкриті» (default), «У плані», «Ресурс»; group by `resource_id`, `rule_id` |
| V-10 | `view_td_energy_tariff_form_resources` (успадковує форму тарифу td_energy) | form | група «Реактивна енергія» (`tg_phi_limit`, `react_rate`) під блоком договірної потужності; підказка «0 — доплати немає; правило «Реактивна енергія секції» вимкнене» |
| V-11 | `action_td_energy_resources_rebind` (server action) | `ir.actions.server` | «Оновити прив'язку ресурсів»: викликає `hooks._seed_points_meters(env)` і `_bind_react_signals(env)` (ідемпотентно); пункт у «Налаштування» (`menu_td_energy_resources_rebind`, seq 80), `group_td_energy_manager` |
| V-12 | `res_config_settings_view_form_td_energy_resources` (успадковує `td_energy.res_config_settings_view_form_td_energy`) | `res.config.settings` | група «Енергоресурси»: `td_energy_resources_boiler_eff`, `…_boiler_eff_norm`, `…_night_from_h`, `…_night_to_h`, `…_air_spec_norm`, `…_water_night_norm`, `…_boiler_makeup_norm`, `…_air_setpoint_bar`, `…_gap_max_s`, `…_min_coverage`, `…_export_max_days`, `…_weeks_per_month` |
| V-13 | `views/menus.xml` | `ir.ui.menu` | таблиця 3.3 |

### 3.2 Клієнтські компоненти (OWL) UI-01…UI-08

Усе — `@odoo/owl`, реєстрація `registry.category("actions").add("td_energy_resources.resources", Resources)`; дані — `orm.call("td.energy.res.dashboard", "get_resources", [], {code})`; шина — `useEnergyBus` з `td_energy` (`@td_energy/common/bus`, підписка на `kpi`), резервне опитування `meta.refresh_s`; запуск дій резервів — `runAdviceAction` і реєстр `td_energy.advice_handlers` з W1 (`@td_energy/common/advice`). Кожен інтерактивний вузол — `<button>` з `aria-label`; стан — не лише кольором (текстовий чип, крапка якості «оцінка» пунктиром); кнопки ≥ 36 px як у макеті.

| ID | Компонент | Вміст і поведінка |
|---|---|---|
| UI-01 | `Resources` (`td_energy_resources.resources`) | Шапка: крихти «Енергетика / Енергоресурси», h1 «Енергоресурси заводу», рядок підсумку `meta.total.text` (D-31), кнопка «Вивантажити в Excel» (відкриває `/td/energy/resources/export?day=<день>` як завантаження). Нижче `ResTabs`, `ResKpis`, блок «графік + список», `ResNotes`. Стан: `code` (за замовчуванням `context.td_energy_resource` або перша вкладка), `data`, `failed`. Підписка на шину (дебаунс 2 с) |
| UI-02 | `ResTabs` | `role="tablist"`: кнопки за `tabs[]` (назва + підпис `sub`); вибрана — рамка 2 px `accent`; перемикання перезавантажує `get_resources(code)` |
| UI-03 | `ResKpis` | Картки (`flex: 1 1 220px`): мітка, значення 26 px, одиниця, примітка; колір примітки за `tone` (`good` зелений, `bad` помаранчевий, `neutral`); крапка якості в значень `quality='estimated'` |
| UI-04 | `ResChart` | SVG `viewBox 0 0 880 262`: сітка (4 лінії), підписи осі Y (0, y1, y2, y3) і годин 00…24 кожні 3 год, область + лінія кольору ресурсу (`resource.color`), пунктир ліміту (`limit`), вертикаль «зараз» у `X(now)`, `X(h)=40+h/24·820`, `Y(v)=230−v/y_max·210`; `null`-слоти розривають лінію; підпис `foot` під графіком |
| UI-05 | `ResList` | Заголовок `list.title`; рядки: код · назва, значення (`value unit`), смуга 6 px шириною `share·100 %`; крапка якості |
| UI-06 | `ResNotes` | Секція «Що помітила система»; рядок: заголовок, текст, «≈ N ₴/міс» (лише якщо ключ є), кнопка за першою доступною дією (`actions[]` з `enabled !== false`; `control` — лише за наявності обробника в `td_energy.advice_handlers`); при порожньому списку — «Відхилень немає» + «Налаштувати пороги» (видно `capabilities.manage`, веде на `action_td_energy_opportunity_rule`) |
| UI-07 | `useResourceDay` | Хелпер: форматування `fmtInt/fmtDec/fmtMoney` з `@td_energy/common/format`; одиниці й знаки uk-UA |
| UI-08 | `td_energy_resources.scss` | Токени кольорів ресурсів (`--td-res-el|gas|heat|air|water`), решта — `td_energy.scss` (W1 UI-11); адаптив ≥ 360 px (колонки згортаються, графік 100 % ширини) |

### 3.3 Меню (`views/menus.xml`)

Корінь: `td_factory3d.menu_td_root` → `td_energy.menu_td_energy` (як у W1). Порядок за макетом: Пульт (5) → [«Чергування» 6] → «Керування» (W2) → **«Енергоресурси» (10)** → «Аналітика» (W4, 12) → «Завантаження вузлів» (15).

| XML-id (`td_energy_resources.`) | Назва | Батько | seq | Групи | Дія |
|---|---|---|---|---|---|
| `menu_td_energy_resources` | Енергоресурси | `td_energy.menu_td_energy` | 10 | `td_energy.group_td_energy_user` | `action_td_energy_resources` |
| `menu_td_energy_resources_config` | Енергоресурси | `td_energy.menu_td_energy_config` | 50 | `…group_td_energy_manager` | — (розділ) |
| `menu_td_energy_resource` | Ресурси | `…_config` (цей розділ) | 10 | manager | `action_td_energy_resource` |
| `menu_td_energy_price` | Ціни | `…_config` | 20 | `…group_td_energy_cost` | `action_td_energy_price` |
| `menu_td_energy_point` | Точки обліку | `…_config` | 30 | manager | `action_td_energy_point` |
| `menu_td_energy_meter_resources` | Лічильники ресурсів | `…_config` | 40 | manager | `action_td_energy_meter_resources` |
| `menu_td_energy_res_interval` | Інтервали ресурсів | `…_config` | 50 | manager | `action_td_energy_res_interval` |
| `menu_td_energy_usage` | Зведення використання | `…_config` | 60 | manager | `action_td_energy_usage` |
| `menu_td_energy_opportunity_rule` | Правила резервів | `…_config` | 70 | manager | `action_td_energy_opportunity_rule` |
| `menu_td_energy_opportunity` | Резерви економії | `td_energy.menu_td_energy` | 74 | user | `action_td_energy_opportunity` |
| `menu_td_energy_resources_rebind` | Оновити прив'язку ресурсів | `…_config` | 80 | manager | `action_td_energy_resources_rebind` |

## 4. Права

### 4.1 `security/ir.model.access.csv` (A) і `security/ir.model.access-opportunity.csv` (B)

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

`td.energy.meter` і `td.energy.tariff` — права `td_energy` достатні (нові поля успадковують); `td.energy.res.dashboard` — AbstractModel без ACL (контроль у методах); запис у `td.energy.res.interval` — лише крон/backfill/`sudo()` (тому write/create/unlink — лише `group_td_admin`).

### 4.2 Групи

Нових груп немає: «Перегляд» = `td_energy.group_td_energy_user`; ₴ = `…_cost`; «Енергетик» = `…_manager` (дії над резервами, налаштування); «Головний енергетик» = `…_chief` (успадковує manager; у W3 окремих прав не має); адм. операції (backfill, створення правил) — `td_factory3d.group_td_admin`.

### 4.3 Record rules

`td_energy_price_rule_company`, `td_energy_point_rule_company`, `td_energy_opportunity_rule_company`, `td_energy_opportunity_company` — домен `['|', ('company_id','=',False), ('company_id','in',company_ids)]`, глобальні. `td.energy.res.interval`, `td.energy.usage` — без company (ізоляція через `meter_id`, `point_id`).

### 4.4 Захист даних і дій

- Ключі вартості (`cost_uah`, `price_uah`, `save_uah_month`, колонка `cost` у xlsx) без `group_td_energy_cost` **видаляються** з відповідей API-01, API-02, API-10 і xlsx (AC-21, AC-47).
- Керування резервами — `group_td_energy_manager`; запуск детекторів — крон (`base.user_root`) або manager.
- Записів у пристрої немає: `write_enabled` не змінюється, емулятор і збирач лише читають.
- Заявки ТО з резервів створюються через W1-майстер `td.energy.ticket.wizard` (права як у W1).
- Експорт (API-07): `auth='user'`, перевірка групи, параметри валідуються (дата, коди ресурсів — лише з довідника), немає довільних SQL-параметрів.

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`) — параметри `td.energy_resources.*`

| Ключ | За замовчуванням | Призначення |
|---|---|---|
| `td.energy_resources.boiler_eff` | `0.91` | проєктний ККД котельні: ціна тепла (R-02 п. 3) до появи вимірювань |
| `td.energy_resources.boiler_eff_norm` | `90` | норма ККД, %: KPI «ККД котельні» (R-09) |
| `td.energy_resources.night_from_h` | `23.0` | початок «ночі» (місцеві години) для нічних витрат і витоків |
| `td.energy_resources.night_to_h` | `6.5` | кінець «ночі» (06:30) |
| `td.energy_resources.air_spec_norm` | `6.0` | норма питомої потужності повітря, кВт/(м³/хв) |
| `td.energy_resources.water_night_norm` | `0.05` | норма нічної витрати води, м³/год |
| `td.energy_resources.boiler_makeup_norm` | `0.5` | норма підживлення котельні, м³/добу |
| `td.energy_resources.air_setpoint_bar` | `7.0` | уставка тиску повітря, поки немає сигналу `air/setpoint_bar` (Q-07; власник сигналу — W2) |
| `td.energy_resources.gap_max_s` | `900` | максимальний розрив між показаннями, всередині якого ряд лінійно інтерполюється (R-03) |
| `td.energy_resources.min_coverage` | `0.3` | мінімальна частка слота з даними, за якої слот будується (інакше `missing`) |
| `td.energy_resources.export_max_days` | `31` | максимум діб в одному xlsx (API-07) |
| `td.energy_resources.weeks_per_month` | `4.33` | переведення тижневих величин у місячні (R-14) |

Наявні параметри `td_energy`, що використовуються модулем: `td.energy.read_enabled` (стоп-кран кронів), `td.energy.keep_interval_days` (ротація, 400), `td.energy.shift_calendar_id` (календар змін, R-21), `td.energy.pv_kwp`, `td.energy.pult_refresh_s` (опитування UI), `td.energy.load_warn_pct`.

### 5.2 `data/td_energy_resource.xml` (`noupdate="1"`): 5 записів

| xml-id | code | name | uom / rate | rate_hour_factor | kwh_per_unit | co2 | is_derived | in_energy_cost | show_tab_cost | source_note | price_source | limit_kind / rate_limit / daily_limit | list_basis | color |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `resource_el` | `el` | Електрика | кВт·год / кВт | 1 | 0 | 0,37 | ні | так | так | — | `tariff` | `tariff_contract` / — / 0 | rate | `#714B67` |
| `resource_gas` | `gas` | Газ | м³ / м³/год | 1 | 10,5 | 1,96 | ні | так | так | — | `price` | `fixed` / 80 / 1200 | rate | `#b45309` |
| `resource_heat` | `heat` | Тепло | кВт·год / кВт | 1 | 0 | 0 | так | ні | ні | з BMS | `derived_gas` | `none` | rate | `#c2410c` |
| `resource_air` | `air` | Стиснене повітря | норм. м³ / м³/хв | 60 | 0 | 0 | так | ні | так | — | `derived_el` | `none` | rate | `#0369a1` |
| `resource_water` | `water` | Вода | м³ / м³/год | 1 | 0 | 0 | ні | ні | так | — | `price` | `none` | `qty_day` | `#0f766e` |

Заголовки графіків, `chart_note`, `list_title`, `foot_template` — за текстом макета (M-01). Поле `limit_kind` має підпис «Вид ліміту» (`string="Вид ліміту"`; значення `none`, `fixed`, `tariff_contract`). Джерела чисел: газ 10,5 кВт·год/м³ і 19,80 ₴/м³ (`GAP.md` §4.2, §4.3, макет `Resources.dc.html`, ключ `gas`); CO₂: мережа 0,37 кг/кВт·год і газ 1,96 кг/м³ виведені з макета «Викиди CO₂» (`Analytics.dc.html`: 186 400 кВт·год → 69 т, 18 400 м³ → 36 т); вода 60 ₴/м³ (макет `water`: 252 ₴ / 4,2 м³). `foot_template` (R-10): `el` «Пік доби {peak_kw} кВт о {peak_time}.{export_sentence}», `gas` «Нічна витрата {night} м³/год, у зміну {day} м³/год. Пік {peak} м³/год о {peak_time}.», `heat` «Найбільша частка тепла — {top_name} ({top_share} %).», `air` «{leak_sentence}», `water` «Нічна витрата {night} м³/год {norm_sentence}.»

`data/td_energy_price_data.xml` (`noupdate="1"`, демо): `td.energy.price` газ 19,80 ₴/м³ і вода 60,00 ₴/м³, `date_from = 2025-01-01`, без `date_to`.

### 5.3 Демо-точки й лічильники (`data/resource_points.csv`, `data/resource_meters.csv`; завантажує `hooks._seed_points_meters(env)`, ідемпотентно за `(resource, code)`)

Точки (`kind`: S — source, C — consumer; `nominal` — `rate_nominal`; метод — `estimate_method`):

| Ресурс | Код | Назва | kind | node_id (код вузла) | Метод оцінки й параметри |
|---|---|---|---|---|---|
| gas | `GAS-MAIN` | Головний газовий лічильник | S | — | — |
| gas | `BOILER` | Котельня цеху | C | `BOILER` | — (вимірюється) |
| gas | `DRY-1` | Сушильна камера (газовий пальник) | C | `DRY-1` | `load_share`, nominal 6,0 м³/год |
| gas | `CHP` | КГУ TEDOM (резерв) | C | `CHP` | — (вимірюється) |
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
| water | `BOILER` | Підживлення котельні | C | `BOILER` | — (вимірюється) |
| water | `SPRAY-1` | Фарбувальна камера | C | `SPRAY-1` | `load_share`, nominal 1,5 м³/год |

Значення `rate_nominal` і `min_pressure_bar` — **ПРИПУЩЕННЯ** до появи паспортних даних (Q-02); числа підібрано так, щоб при електричному навантаженні макета (EDGE-1 41 кВт) отримати його швидкості (R-04 п. 1: 2,4 м³/хв).

Лічильники (`code`, точка, `mode`, сигнали): `GM-MAIN` (`GAS-MAIN`, `counter`, `qty_signal` `infra/gas/m3_total`); `GM-BOILER` (`BOILER`, `flow_integrate`, `equipment/BOILER/gas_m3h`); `GM-CHP` (`CHP`, `flow_integrate`, `infra/chp/gas_m3h`); `GM-DRY1`, `GM-CANTEEN` (`estimate`); `AM-MAIN` (`AIR-MAIN`, `flow_integrate`, `air/flow_m3min`, `rate_hour_factor` ресурсу 60); `AM-EDGE1`, `AM-NEST1`, `AM-PRESS1`, `AM-SPRAY1`, `AM-CNC1` (`estimate`); `WM-MAIN` (`WATER-MAIN`, `counter`, `infra/water/m3_total`); `WM-BOILER` (`counter`, `infra/water/boiler_m3_total`); `WM-CANTEEN`, `WM-SOCIAL`, `WM-SPRAY` (`estimate`). Разом 16 лічильників, 16 точок. Реактивні сигнали прив'язуються до наявних `PM-Q1` і `PM-Q2` (`e_react_signal_id`: `energy/cells/Q1/kvarh_total`, `…/Q2/…`) функцією `_bind_react_signals(env)`; нових лічильників для них немає. Теплові точки й лічильники — міст (Частина II).

### 5.4 Сигнали й джерела (`data/resource_signals.csv`, `data/resource_sources.csv`; власник D; завантажує `hooks._ensure_resource_signals(env)`)

Формат CSV сигналів — як `td_energy/data/energy_signals.csv` (колонки `code,name,quantity,kind,unit,equipment,source,address,period_s,store_period_s,decimals,states,warn_low,…,derived_from,origin,binding`). Джерела — колонки `code,name,unit,equipment,host,port,timeout_s,retries,max_block,gap_max`. Функція ідемпотентно створює відсутні записи, наявні не змінює.

Джерела: `MB-U74-GAS-MAIN` (Modbus TCP, unit 74, `iot-sim:502`, `max_block=125`, `gap_max=8`, обладнання `GAS-MAIN`), `MB-U75-AIR-MAIN` (unit 75, обладнання `AIR-MAIN`). Адреси — **ПРИПУЩЕННЯ** для емулятора (на об'єкті — за документом вендора коректора газу й витратоміра повітря; Q-02). Наявні: `MB-U84-IO5` (вода), `BAC-140-BOILER` (котельня), `MB-U01-PM-Q1`, `MB-U02-PM-Q2`, `MB-U72-CHP`, `MB-U70-COMPRESSOR`.

| Код сигналу | kind / од. | Джерело й адреса | Період / зберігання | Примітка |
|---|---|---|---|---|
| `infra/gas/m3_total` | counter, м³ | `MB-U74-GAS-MAIN`, FC3 HR 0–1, u32 little, scale 0,01 | 60 / 60 с | показання лічильника газу (імпульс 0,01 м³) |
| `infra/gas/flow_m3h` | gauge, м³/год | — (похідний від `m3_total`, `derive_rule=rate_h`, вікно 5 хв) | 60 / 300 с | як `infra/water/flow_m3h` |
| `equipment/BOILER/gas_m3h` | gauge, м³/год | `BAC-140-BOILER`, AI instance **7** (`BOILER_GasFlow`): у початковій редакції було припущення «AI instance 6» (вільні номери перевірити; зайняті AI 1, 2, 3, 5), але за картою `BOILER` емулятора AI:4 і AI:6 теж зайняті (`FlueGasTemp`, `BriquettesToday`) — у збірці прийнято AI:7 (`resource_signals.csv`, `td_sim_signal.csv`); адреса лишається **ПРИПУЩЕННЯМ** (Q-02) | 30 / 300 с | `module='energy'`, read-only |
| `air/flow_m3min` | gauge, м³/хв | `MB-U75-AIR-MAIN`, FC3 HR 0, u16, scale 0,01 | 10 / 300 с | витрата магістралі |
| `air/m3_total` | counter, норм. м³ | `MB-U75-AIR-MAIN`, HR 2–3, u32 little, scale 0,1 | 60 / 60 с | |
| `air/pressure_bar` | gauge, бар | `MB-U75-AIR-MAIN`, HR 4, u16, scale 0,01 | 10 / 300 с | тиск магістралі; `warn_low=5.8`, `min_duration_s=300`, без заявки |
| `infra/water/boiler_m3_total` | counter, м³ | `MB-U84-IO5`, FC3 HR 18–19, u32 little, scale 0,01 (канал DI, **ПРИПУЩЕННЯ**) | 60 / 60 с | підживлення котельні |
| `infra/water/boiler_flow_m3h` | gauge, м³/год | похідний від `boiler_m3_total`, `rate_h` | 60 / 300 с | |
| `energy/cells/Q1/kvarh_total` | counter, квар·год | `MB-U01-PM-Q1`, FC3 HR 3219, i64, scale 0,001 (PM5560 «Reactive Energy Delivered», **ПРИПУЩЕННЯ**: підтвердити за `PM5500 series user manual`, регістри 3220…) | 60 / 60 с | реактивна енергія вводу |
| `energy/cells/Q2/kvarh_total` | counter, квар·год | `MB-U02-PM-Q2`, той самий адрес | 60 / 60 с | |

Разом **+10 сигналів, +2 джерела**; у всіх десяти `module='energy'` (read-only, `write_enabled=False`), `origin` — `sim_data` для регістрових і `module` для похідних. Сигнал `air/setpoint_bar` **не** створюється: його вводить W2 (контракт C-02). Пороги сигналів не створюють заявок ТО (`create_request=False`, `alarm_title` порожній).

### 5.5 `post_init_hook` і міграція `19.0.1.0.0`

Кроки (ідемпотентні; ті самі функції викликає міграція `post-migration.py` при `-u`):
1. `_set_el_on_meters(env)`: SQL `UPDATE td_energy_meter SET resource_id = <id resource_el>, mode = 'counter' WHERE resource_id IS NULL` (пакетами 5 000); колонка додається з `default` Odoo, але наявні рядки обов'язково перевіряються явним UPDATE;
2. завантаження ресурсів/цін — XML (`noupdate`), для наявних БД записи створюються при `-u`;
3. `_ensure_resource_signals(env)` (5.4);
4. `_seed_points_meters(env)` (5.3), потім `env["td.energy.point"]._td_bind_extra()` (гак моста);
5. `_bind_react_signals(env)`: `PM-Q1.e_react_signal_id`, `PM-Q2.e_react_signal_id` (якщо сигнали є й поле порожнє);
6. параметри (5.1) — XML.

Очікувані кількості на демо-БД після встановлення (`f3d_full2`, 67 електричних лічильників): `td.energy.resource` 5; `td.energy.meter` 67 → у всіх `resource_id=el`, +16 неелектричних; `td.energy.point` 16; сигналів `energy` +10 (усього 312 + 10 = 322 при встановленому W1), `td.source` +2 (136 → 138); `td.energy.price` 2; правил резервів 6 (+3 міст); параметрів +12; `td.energy.interval` не змінюється (кількість рядків до/після — AC-05).

### 5.6 `uninstall_hook`

Видаляє неелектричні лічильники (`resource_id.code != 'el'`; вони не можуть існувати без модуля: `node_id` повертається в `required=True`), знімає `e_react_signal_id`, видаляє власні крон-записи й параметри `td.energy_resources.*`. Таблиці модуля (`td_energy_res_interval`, точки, ціни, резерви) видаляються штатно Odoo разом із моделями. Електричні дані (`td.energy.interval`, `td.energy.alloc`, події) і сигнали **не** видаляються. `neutralize.sql`: вимкнути крон `cron_td_energy_res_build`, `…_res_rotate`, `…_opportunity`, `…_opportunity_links`; джерела `MB-U74-GAS-MAIN`, `MB-U75-AIR-MAIN` — `read_enabled=false` (як у решти `energy`-джерел).

## 6. Крони й фонові процеси

Усі — `user_id=base.user_root`, `try/except` із `_logger.exception`, без проброса виключення; при `td.energy.read_enabled = False` не діють.

| XML-id | Назва | Інтервал | Метод | За один прогін | Ліміт |
|---|---|---|---|---|---|
| `cron_td_energy_res_build` | Енергетика: інтервали ресурсів | 5 хв | `td.energy.res.interval._cron_build` | R-05: усі активні неелектричні лічильники + реактивні, слоти від `res_last_interval_start`, повтор двох останніх слотів; потім `bus.tick('kpi')` | ≤ 5 с, ≤ 192 слоти на лічильник |
| `cron_td_energy_res_rotate` | Енергетика: ротація інтервалів ресурсів | 1 доба, `nextcall` 03:10 Київ | `td.energy.res.interval._cron_rotate` | видалити `ts_start` старші за `td.energy.keep_interval_days` пакетами 10 000 | ≤ 60 с |
| `cron_td_energy_opportunity` | Енергетика: резерви економії | 1 доба, `nextcall` 03:30 Київ | `td.energy.opportunity._cron_detect` | R-13: усі ввімкнені правила, upsert знахідок, спливання, прив'язка заявок | ≤ 60 с сумарно, ≤ 10 с на правило |
| `cron_td_energy_opportunity_links` | Енергетика: заявки резервів | 1 год | `td.energy.opportunity._td_link_requests` | R-13 п. 6 | ≤ 5 с |

## 7. HTTP/JSON API

Єдиний новий HTTP-маршрут — API-07. Решта — ORM-RPC від імені користувача. Якщо не вказано інше, методи — `@api.model`.

| ID | Сигнатура | Вхід → вихід | Помилки |
|---|---|---|---|
| API-01 | `td.energy.res.dashboard.get_resources(code=None)` | `code` — код ресурсу (за замовчуванням перша вкладка) → JSON «Енергоресурси» (нижче) | невідомий код → `UserError("Невідомий ресурс: %s.")`; без групи → `AccessError("Немає доступу до Енергетики.")` |
| API-02 | `td.energy.opportunity.get_list(resource_code=None, states=("open",))` | → `{"items": [opportunity…], "plan_sum": n, "all_sum": n}` (контракт C-01; формат елемента — нижче) | `AccessError` |
| API-03 | `td.energy.opportunity.action_plan_toggle(plan=None)` (на записі) | `plan=None` — інвертувати → `True` | `AccessError("Керувати резервами може лише енергетик.")`, `UserError("Резерв уже закрито.")` |
| API-04 | `td.energy.opportunity.action_dismiss()` / `action_done(note=None)` | → `True` | як API-03 |
| API-05 | `td.energy.opportunity.rule.action_run()` | → `{"found": n, "created": n, "expired": n, "seconds": f}` | `AccessError` |
| API-06 | `td.energy.opportunity.get_plan_summary()` | → `{"plan_sum": n, "all_sum": n, "plan_count": n, "open_count": n}` (₴/міс; без групи вартості ключі сум відсутні) | — |
| API-07 | `GET /td/energy/resources/export?day=YYYY-MM-DD[&day_to=YYYY-MM-DD][&resources=gas,air]` (`auth="user"`) | → `200` xlsx, `Content-Disposition: attachment; filename="energoresursy_<day>.xlsx"` | `400` невірна дата/код ресурсу/`day_to-day+1 > export_max_days`; `403` без `group_td_energy_user`; `413` рядків > 200 000 |
| API-08 | `td.energy.res.interval._td_backfill(days=90, until=None, seed=20261018, purge=False, resources=None)` | → статистика R-22 | `AccessError`, `UserError("Кількість діб має бути від 1 до 400.")` |
| API-09 | `td.energy.price._td_price_at(resource, dt_local=None)` | → `float` (C-01) | — |
| API-10 | `td.energy.res.dashboard._td_totals(day_from, day_to, resource_codes=None)` (внутрішній, для W4/звітів; `sudo`-читання) | → `[{"resource","qty","kwh_eq","cost","co2_kg"}…]` за `td.energy.usage` | `AccessError` без групи |

### Відповідь API-01 (вкладка «Газ», 14:20; значення — приклад на основі макета)

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

Правила форми: `tabs[].cost_uah`, `kpis[].note` із ₴, `meta.total.cost_uah`, `notes[].save_uah_month` — лише з групою вартості (інакше ключі відсутні, підписи без ₴); числа без свіжих даних — `null`, підпис «—»; `chart.series` — 96 значень за **локальними** слотами (R-10); `quality ∈ {measured, estimated}` (оцінкові — з крапкою в UI); `tone ∈ {good, bad, neutral}`; `capabilities.manage` = група «Енергетик»; `meta.data_state ∈ {ok, partial, stale}` (як W1: `stale` — немає свіжих сигналів ресурсу; `partial` — частина лічильників ресурсу без свіжих даних). Розмір відповіді ≤ 25 КБ.

### Формат елемента API-02 `items[]`

`{"id", "code" (rule.code), "resource": "gas", "title", "text", "save_uah_month" (cost), "est_qty_month", "in_plan": bool, "state", "found_at": iso, "request_id": int|null, "actions": [{"code","label","kind","class","params","enabled"}…]}`; `enabled = (kind != 'control') or td.energy.advice._td_control_available()`; якщо для резерву немає жодної `enabled`-дії, в кінець додається `rule.fallback_action`.

## 8. Сервісна частина

### 8.1 Емулятор `iot_sim` (власник D; `factory3d/services/iot_sim/`)

Нові пристрої (`catalog/devices.yaml`, додати в кінець, не змінюючи наявні):

| code | role | protocols | unit_id | driver | params |
|---|---|---|---|---|---|
| `GAS-MAIN` | `gas_meter` | P-07 | 74 | `gas` | `{"dry_nom": 6.0, "canteen": 1.0}` |
| `AIR-MAIN` | `air_meter` | P-07 | 75 | `air` | `{"leak": 1.6, "q_ref": 9.8, "load_ref": 66.0, "load_min": 25.0, "drop": 0.1}` |

Нові рядки `catalog/signals.csv` і `td_iot_sim/data/td_sim_signal.csv` (формат `n,code,device,protocol,address,dtype,unit,scale,nominal,thresholds,model,status`; `n` — продовження нумерації (останній W3-початку 1177 → у початковій редакції 1178…1187, «при злитті з W2 `n` перераховує менеджер»; **після злиття W2 (n 1178…1205 — вікно керування `SWB-CTRL`) сигнали W3 мають n 1206…1215**); `status = новий`): 10 сигналів із таблиці 5.4; `nominal`: `infra/gas/m3_total` 31 870, `equipment/BOILER/gas_m3h` 0, `air/flow_m3min` 9,8, `air/m3_total` 6 420, `air/pressure_bar` 6,8, `infra/water/boiler_m3_total` 1 205, `energy/cells/Q1/kvarh_total` 21 500, `…/Q2/…` 18 300.

Моделі (файли `services/iot_sim/iot_sim/models/`): нові `gas.py`, `air.py`; правки `boiler.py` (+3 рядки), `water.py`, `meter.py`; **не** правляться `compressor.py`, `chp.py`, `bess.py`, `ats.py`, `transformer.py`, `swb.py` (власник W2/W1).

| Модель | Фаза | Алгоритм (на тік `dt`, с) |
|---|---|---|
| `boiler` (правка) | як є | `gas_m3h = heat_kw / (0,914 × 10,5)` (η і теплотворність — константи `BOILER_ETA`, `GAS_KWH_M3`; при `heat_kw = 0` → 0); не впливає на `silo_fill` (D-35). Приклад: `heat_kw = 390` → `40,6 м³/год` |
| `gas` (`GAS-MAIN`, `@register_model("gas")`) | `AGGREGATE` | `q = gas_m3h(BOILER) + infra/chp/gas_m3h + dry + canteen` · `(1 + ε)`; `dry = dry_nom` при `is_working(DRY-1)` (функція `models/water.is_working`), інакше 0; `canteen = 1,0` у будні 08:00–16:00 Київ, інакше 0; `ε = 0,01 + 0,004·(2r−1)` (`r` — детермінований шум моделі); прапор `gas_extra` (сценарій) додає `extra_m3h`; `m3_total += q·dt/3600` із квантом 0,01 м³ (залишок переноситься) |
| `air` (`AIR-MAIN`) | `AGGREGATE` | `act = clamp((load − load_min)/(load_ref − load_min), 0, 1,3)`, `load` = `equipment/COMPRESSOR/load`; `flow = leak + leak_extra + (q_ref − leak)·act` (`leak_extra` з прапора `air_leak`, м³/хв); `pressure = equipment/COMPRESSOR/pressure_bar − drop`; `m3_total += flow·dt/60`, квант 0,1 норм. м³. Приклад: `load=66` → `flow=9,8`; `load=25` (ніч) → `flow=1,6` |
| `water` (правка) | як є | `boiler_m3_total += 0,0125·max(1, boilers_on)·dt/3600` (`boilers_on = max(0, equipment/BOILER/state − 1)`), квант 0,01 м³; основна витрата `q` збільшується на це підживлення; прапор `water_leak`: `+extra_m3h` при `23:00 ≤ t < 06:30` |
| `meter` (правка, PM5560 вводів) | як є | `kvarh_total += |energy/cells/Qn/q_kvar|·dt/3600`, регістр i64 (`scale 0,001`) |

Сценарії (`td_iot_sim/data/td_sim_scenario_resources.xml`, новий файл, група `energy`, `duration=0` — до зупинки; номери сценаріїв емулятора **S-21…S-23**): `air_leak` (S-21; `params={"leak_extra": 3.0}`, прапор `air_leak`), `gas_overuse` (S-22; `{"extra_m3h": 45.0}`, прапор `gas_extra`; BOILER 41 + 45 = 86 > ліміту 80 м³/год), `water_leak` (S-23; `{"extra_m3h": 0.5}`, прапор `water_leak`). Тести емулятора: `services/iot_sim/tests/unit/test_gas.py`, `test_air.py`, `test_water_boiler.py`, `test_meter_kvarh.py`. **Сервер із уже встановленим `td_iot_sim`:** нові сигнали й сценарії потрапляють у реєстр симулятора через `td_iot_sim.hooks.refresh_registry` (міграція `19.0.2.0.x`/`-u td_iot_sim`), без перевстановлення.

### 8.2 Збирач

Змін коду немає: нові джерела й сигнали підхоплюються з `GET /f3d/telemetry/config` (ETag) за `config_poll_s` (60 с). Навантаження: +2 джерела, 10 сигналів, ≈ 8 600 показань/добу після `store_period_s` (5 лічильників × 1 440 + 5 «газових» × 288), зберігання сирих — 30 діб (`td.telemetry.keep_days`).

## 9. Алгоритми й правила

Загальні позначення: слот `s` — 15 хвилин за UTC-сіткою (`floor15`); `K_month(L) = weeks_per_month × 7 / L` (переведення суми за вікно `L` діб у місяць); локальні доби/години — `Europe/Kyiv`.

### R-01 Одиниці й перерахунки (FR-01, FR-05)

1. Зі швидкості в кількість за слот: `qty = rate × rate_hour_factor × 0,25`; навпаки: `rate_avg = qty × 4 / rate_hour_factor`. Для `air` (`rate_hour_factor = 60`): `qty` у норм. м³, `rate` у м³/хв: `rate_avg = qty × 4 / 60`.
2. `kwh_eq`: `el`, `heat` → `qty`; `gas` → `qty × kwh_per_unit`; `air`, `water` → 0.
3. `co2_kg = qty × co2_kg_per_unit` — лише для потоків `import` і `supply` (R-07), щоб не рахувати двічі споживання за гілками.
Приклад: газ, слот із `qty = 11,083 м³` → `rate_avg = 44,33 м³/год`, `kwh_eq = 116,37`, `co2_kg = 21,72`.

### R-02 Ціна й вартість (FR-02, FR-05)

1. `el`: ціна й вартість — у `td.energy.interval` (`price`, `cost`); у `td.energy.usage` для `import` береться `interval.cost`.
2. `price_source='price'` (газ, вода): `price = td.energy.price._td_price_at(resource, local_date(ts_start))`; `cost = round(qty × price, 2)`; немає ціни на дату → `price = 0`, `cost = 0`.
3. `derived_gas` (тепло): `price_heat = price_gas / (kwh_per_unit_gas × boiler_eff)`, `price_gas` за п. 2 на ту саму дату; `cost = round(qty × price_heat, 2)`. Приклад: `19,80 / (10,5 × 0,91) = 2,0722 ₴/кВт·год`.
4. `derived_el` (повітря): `cost = Σ cost` рядків `td.energy.interval` із `role='consumer'` і `node_id = point.cost_node_id` за той самий слот; `price = cost / qty` при `qty > 0`, інакше 0. Приклад: `COMPRESSOR`, 642 кВт·год × 8,40 = 5 392,80 ₴ за добу.
5. Ключі `price`/`cost` в API й експорті — лише з `group_td_energy_cost` (M-08).

### R-03 Побудова інтервалу: `counter` і `flow_integrate` (FR-04, FR-05)

Параметри: `gap_max_s` (900), `min_coverage` (0,3).

**`counter`** (не-el: `qty_signal_id`; el-реактивна: `e_react_signal_id`): точки = `td.reading` сигналу за `[t0 − gap_max, t1 + gap_max]`; `CounterSeries.build(points, base=0, reset_tol=td.energy.reset_tol_kwh, max_kw=max_rate або rate_nominal або 1000, gap_max_s)` з `td_energy/tools/counter.py`; `qty = series.delta(t0, t1)`; якість: `measured`→`measured`, `interpolated`→`interpolated`, `reset`→`interpolated`, `None`→`missing` (`qty=0`).

**`flow_integrate`** (`flow_signal_ids`, одиниці — `rate_label` ресурсу): для слота `[t0, t1)`
1. за кожним сигналом — показання `quality ok` за `[t0 − gap_max, t1 + gap_max]`, за часом; інтервали між сусідніми показаннями з розривом `> gap_max_s` — «діри»;
2. поза дірами функція швидкості `f_k(t)` — лінійна інтерполяція між показаннями; сума `F(t) = Σ_k f_k(t)` визначена лише там, де визначені всі `f_k`;
3. `covered` = довжина `[t0, t1)`, де `F` визначена; `coverage = covered / 900 с`; інтеграл `∫F dt` за `covered` — трапеціями за об'єднаними вузлами;
4. при `coverage ≥ min_coverage`: `qty = ∫F dt × rate_hour_factor / 3600 / coverage` (масштабування на повний слот), `rate_avg` за R-01 п. 1; інакше `qty = 0`, `quality = missing`;
5. якість: `coverage ≥ 0,9` → `measured`; `[min_coverage, 0,9)` → `interpolated`.
Приклад 1 (газ, `rate_hour_factor = 1`): показання в 0, 300, 600, 900 с: 40; 44; 46; 46 м³/год → інтеграл = `(40+44)/2·300 + (44+46)/2·300 + (46+46)/2·300 = 12 600 + 13 500 + 13 800 = 39 900` (м³/год·с) → `qty = 39 900 / 3 600 = 11,083 м³`, `rate_avg = 44,33`, `coverage = 1,0`, `measured`.
Приклад 2: показання в 0 і 300 с (наступне — через 1 000 с, діра `[300, 1300]`) → `coverage = 300/900 = 0,333`, `qty` = інтеграл за `[0, 300]` / 0,333, `interpolated`; при єдиному показанні в слоті й розриві з обох боків > 900 с → `coverage = 0` → `missing`.
Приклад 3 (повітря, `rate_hour_factor = 60`): показання 9,6; 9,8; 10,0; 9,8 м³/хв у 0/300/600/900 с → інтеграл = `(9,6+9,8)/2·300 + (9,8+10,0)/2·300 + (10,0+9,8)/2·300 = 2 910 + 2 970 + 2 970 = 8 850` (м³/хв·с) → `qty = 8 850 × 60 / 3 600 = 147,5 норм. м³`, `rate_avg = 147,5·4/60 = 9,83 м³/хв`.
Мультисигнальний лічильник (теплота RV): 25 сигналів `heat_kw` сумуються за п. 2; зникнення одного сигналу робить слот `interpolated`/`missing` (A-06).

### R-04 Оцінкові методи (`mode='estimate'`; FR-04)

Якість результату завжди `estimated`; слот без вихідних даних → `missing`.
1. **`load_share`** (`node_id`, `rate_nominal`): `run_kw = node.p_inst_kw × node.load_factor` (за замовчуванням 0,75), `idle_kw = node.p_inst_kw × node.idle_factor` (0,05); `kw = kw_avg` рядка `td.energy.interval` (`role='consumer'`, цей вузол, цей слот); `active = clamp((kw − idle_kw)/(run_kw − idle_kw), 0, 1)`; `rate = rate_nominal × active`. Приклад: EDGE-1 (`p_inst 67,5`: `run 50,625`, `idle 3,375`), `kw_avg = 41` → `active = 0,796` → `rate = 3,0 × 0,796 = 2,39 м³/хв`.
2. **`schedule`**: `rate = params.rate`, якщо локальний день тижня ∈ `params.weekdays` і `params.from_h ≤ local_hour(ts_start) < params.to_h`, інакше 0. Приклад: `CANTEEN` газ, вівторок 09:30 → 1,0 м³/год.
3. **`residual`**: `rate = max(0, Σ rate(params.from) − Σ rate(siblings))`, де `siblings` = решта `consumer`-точок того самого ресурсу з тим самим `parent_id`, що в даної (зокрема оцінені); будь-який потрібний слот `missing` → `missing`. Приклад (вода): `WATER-MAIN 2,1`, `BOILER 0,0125`, `CANTEEN 0,22`, `SPRAY-1 0,3` → `SOCIAL = 2,1 − 0,5325 = 1,5675 м³/год`.
4. **`gate_loss`** (`state_signal_id`, `params.loss_kw_per_k`, `params.t_in_signal`/`t_out_signal`, за замовчуванням `t_in = 18,0`, `t_out = ventilation/totals/outdoor_c`): `open_frac` = частка слота, коли `state_signal ≥ 0,5` (ступінчасте утримання); `ΔT = max(0, t_in − t_out)`; `rate_kw = loss_kw_per_k × ΔT × open_frac`. Приклад: `loss_kw_per_k = 3,5`, `open_frac = 0,5`, `ΔT = 11` → `19,25 кВт`. Потрібні «сирі» показання (зберігаються 30 діб); старші — `missing`.

### R-05 Порядок побудови слота, крон, ротація (FR-05)

1. `now = floor15(now_utc)`; для кожного активного лічильника з активним ресурсом і `mode` будь-яким: слоти від `res_last_interval_start + 15 хв` (перший прогін — `now − 24 год`) до `now` (не включно), максимум 192 на лічильник за прогін; останні **два** побудовані слоти перераховуються повторно (уточнення за пізніми показаннями).
2. Порядок усередині слота: `counter`/`flow_integrate` → `load_share`/`schedule`/`gate_loss` → `residual` (за глибиною залежності; цикл `residual` неможливий — `_check_estimate` вимагає `from` без самого себе).
3. Запис — `INSERT … ON CONFLICT (meter_id, metric, ts_start) DO UPDATE` (поля `qty`, `rate_avg`, `kwh_eq`, `price`, `cost`, `quality`, `built_at`); `kwh_eq`, `price`, `cost` — R-01, R-02; `is_backfill=False`; рядки `is_backfill=True` живими даними не перезаписуються: у `DO UPDATE` стоїть `WHERE td_energy_res_interval.is_backfill = false`, тому при конфлікті із синтетичним рядком оновлення не виконується (стик «історія / живі» лишається чистим, ТК-03).
4. Електричні вводи з `e_react_signal_id`: той самий цикл створює рядки `metric='react'` (R-03 `counter`, `price=cost=0`, `kwh_eq=0`).
5. Після прогону: `res_last_interval_start`, `bus.tick('kpi')` (один раз).
6. `_cron_rotate`: `DELETE … WHERE ts_start < now − keep_interval_days` пакетами 10 000, не довше 60 с.
7. Будь-який збій за лічильником ізолюється `savepoint`; лог `_logger.exception`; решта лічильників продовжують.

### R-06 Реактивна енергія й tg φ (FR-07, FR-21)

За добу (київську) за вводами: `Q = Σ qty` рядків `metric='react'`, `P = Σ kwh` рядків `td.energy.interval` `role='incomer'` (імпорт); `tg φ = Q / P` (`P ≤ 0` → `null`); `cos φ = 1/√(1+tg²)`. «Ризик доплати» (D-44): `tariff.tg_phi_limit > 0` і `tg φ > tg_phi_limit`; `excess_kvarh = max(0, Q − tg_phi_limit × P)`; `penalty = tariff._td_react_penalty(excess_kvarh)`.
Приклад: `Q = 2 514 квар·год`, `P = 6 284 кВт·год` → `tg φ = 0,40`, `cos φ = 0,928`; при `tg_phi_limit = 0,30`: `excess = 2 514 − 1 885,2 = 628,8`; при `react_rate = 0,24` → `150,9 ₴`.

### R-07 Семантика `td.energy.usage` (FR-06)

| flow | Джерело | qty | cost | co2 | Входить у «разом» |
|---|---|---|---|---|---|
| `import` | `td.energy.interval`, `role='incomer'` | `kwh` | `interval.cost` | `kwh × co2(el)` | так (витрати на купівлю енергії) |
| `export` | те саме, `kwh_export > 0` | `kwh_export` | 0 | 0 | ні |
| `generation` | `role='generation'` | `kwh` | 0 | 0 | ні |
| `load` | `role='feeder'` | `kwh` | `interval.cost` | 0 | ні (споживання заводом; не сумувати з `import`) |
| `supply` | `res.interval`, `metric='main'`, точка `kind='source'` (і ресурс без джерела: `consumer`, якщо в ресурсу немає `source`-точок) | `qty` | `cost` (R-02) | `qty × co2` | так (якщо `resource.is_derived = False`) |
| `branch` | решта точок `res.interval` (`metric='main'`) | `qty` | `cost` | 0 | ні |

Правило для споживачів W4: «вартість енергії» = `Σ cost` за `import` і `supply` ресурсів із `in_energy_cost`; «споживання електроенергії заводом» = `Σ qty` за `load`; «з мережі» = `Σ qty` за `import`.

### R-08 Живі значення й «сьогодні» (FR-08, FR-09)

1. Один `search_read` `td.signal` за списком кодів, потрібних вкладці; значення «свіже», якщо `last_ts ≥ now − max(3·period_s, 120 с)`, інакше `null`.
2. «Сьогодні» = `Σ` рядків `res.interval` із `day = сьогодні (Київ)` за `metric='main'` + «неповний слот»: ті самі правила R-03 на `[floor15(now), now)` (якщо минуло < 60 с — не додається; `coverage` рахується відносно часу, що минув).
3. Електрика («Електрика») береться з W1: `td.energy.dashboard.get_pult(period="now", parts=["kpis","profile","side"])` — `kpis.grid`, `kpis.energy`, `kpis.generation`, `profile.grid`, `profile.peak`, `foot.export_kwh`, `top`, `meta.contract_kw` (контракт C-03); дублювання розрахунків немає.
4. `data_state`: `stale` — немає свіжих сигналів у жодного лічильника ресурсу; `partial` — частина лічильників без свіжих даних; інакше `ok`. Відсутність даних **не** спричиняє виключень.

### R-09 KPI за ресурсами (FR-09)

Кожен KPI: `{id, label, value, unit, note, tone, quality}`. Округлення — R-25.

| Ресурс | KPI | Формула | note / tone |
|---|---|---|---|
| el | `grid_now` | `kpis.grid.kw` (W1 R-27 п. 5) | «{pct} % договірної {contract} кВт»; `bad`, якщо `pct ≥ tariff.peak_warn_pct` |
| el | `today` | `kpis.energy.kwh` (імпорт з 00:00) | «{cost} ₴ · {price} ₴/кВт·год» (cost-група); `neutral` |
| el | `generation` | `Σ kwh` `role='generation'` за сьогодні + неповний слот | «СЕС {pv %} % · КГУ {chp %} % · частка {gen/load %} %», `gen/load` = генерація / `Σ feeder`; `good` |
| el | `reactive` | `Q` квар·год (R-06) | «tg φ {tg}» + « · ризик доплати» (D-44); `bad` при ризику; немає `react`-рядків → `null` |
| gas | `rate` | `infra/gas/flow_m3h` (свіжий), інакше останній `rate_avg` джерела | «котельня {top_name} · КГУ {стоїть\|працює}», `top_name` — споживач із максимальною швидкістю, КГУ — `infra/chp/state` (`running` → «працює») |
| gas | `today` | `Σ qty` джерела (R-08 п. 2) | «{cost} ₴ · {price} ₴/м³» |
| gas | `limit` | `resource.daily_limit` | «використано {today/limit} %»; `bad` при ≥ 90 % |
| gas | `eff` | `100 × Σ qty(HM-BOILER, сьогодні) / (Σ qty(GM-BOILER, сьогодні) × kwh_per_unit)`; немає тепловичислювача котельні → `null` | «норма ≥ {boiler_eff_norm} %»; `good` при ≥ норми; `quality=estimated` |
| heat | `power` | `Σ` швидкості `source`-точок зараз | ядро: «—»; міст: «подача {t} °C · зворот {t} °C» |
| heat | `today` | `Σ qty` джерел | `source_note` «тепловий баланс BMS» |
| heat | `indoor`, `recovery` | гак `_td_heat_kpis` (міст, R-B2) | ядро — не виводяться |
| air | `rate` | `air/flow_m3min` | «тиск {air/pressure_bar} бар · уставка {setpoint}» (сигнал `air/setpoint_bar`, інакше параметр) |
| air | `spec` | `energy/consumers/COMPRESSOR/p_now / flow`, при `flow < 1` → `null` | «норма ≤ {air_spec_norm}»; `good` ≤ норми. Приклад: `52 / 9,8 = 5,31` |
| air | `today_el` | `Σ kwh` вузла `cost_node_id` за сьогодні | «{cost} ₴» (cost-група) |
| air | `night_leak` | `night_rate` (R-09 п. нижче) | «{share} % від денної витрати»; `bad`, якщо `share > 10 %` |
| water | `rate` | `infra/water/flow_m3h` | «основний ввід» |
| water | `today` | `Σ qty` джерела | «{cost} ₴» |
| water | `night` | `night_rate` | «норма ≤ {water_night_norm}»; `good` ≤ норми |
| water | `boiler` | `Σ qty` `WM-BOILER` за сьогодні | «норма ≤ {boiler_makeup_norm} м³/добу»; `good` ≤ норми |

**`night_rate`**: вікно `[учора night_from, сьогодні night_to)` (якщо зараз раніше за `night_to` — до `now`); `night_rate = min rate_avg` слотів вікна джерела з `quality != missing`, при покритті вікна < 70 % слотів → `null`. **`day_mean`**: середнє `rate_avg` слотів усередині змін (R-21) сьогодні; якщо змін сьогодні ще не було — вчорашній робочий день. `share = night_rate / day_mean × 100`.
Фікстури AC: див. розд. 12 (числа макета).

### R-10 Графік доби (FR-08)

1. `series[i]`, `i = 0…95` — **локальні** слоти (R-21 `local_slot_index`, додавання/пропуск слота в добу переходу на літній/зимовий час — як W1 A-30); значення — сума `rate_avg` за джерелами ресурсу; слот без даних → `null`; слоти після `now_slot` → `null`; слот `now_slot` — живе значення (R-08).
2. `limit`: `el` → `tariff.contract_kw` на момент `now`; `fixed` → `rate_limit`; інакше `null`.
3. `y_max = 3 × step`, `step = nice(1,1 × max(limit, max(series)) / 3)`, де `nice(x)` — найменше з `{1; 1,5; 2; 2,5; 3; 4; 5; 6; 7,5; 10}·10^k`, не менше за `x`; `ticks = [step, 2·step, 3·step]`. Приклади: газ (макс 46, ліміт 80): `1,1·80/3 = 29,3 → 30 → y_max 90`; електрика (ліміт 800, пік 631): `293 → 300 → 900`; повітря (пік 9,8): `3,59 → 4 → 12`; вода (0,42): `0,154 → 0,2 → 0,6`.
4. `chart_note` — підстановка `{limit}`, `{contract}`, `{capacity}` (останній — гак `_td_heat_chart_note`, інакше підрядок «котли {capacity} кВт» видаляється разом із « · »).
5. `foot` (D-33) = `foot_template.format(**vars)`; `vars`: `peak_kw`/`peak_time` (максимум `series` із локальним часом слота), `export_sentence` (el: якщо `foot.export_kwh > 0` — « З {export_time} частина енергії СЕС віддавалась у мережу ({export_kwh} кВт·год).», інакше «»), `night`, `day` (R-09), `top_name`/`top_share` (тепло: споживач із максимальною швидкістю й частка від `Σ`), `leak_sentence` (повітря: `share > 10 %` → «Вночі витрата {night} м³/хв — це витоки в мережі.», інакше «Нічна витрата {night} м³/хв в межах норми.»), `norm_sentence` (вода: `night ≤ norm` → «в нормі», інакше «вища за норму {norm}»). Якщо для підстановки немає даних — вся фраза опускається.

### R-11 Список «Споживачі», баланс (FR-08, FR-10)

1. Елементи — активні точки `kind='consumer'` ресурсу; `value`: `basis='rate'` — швидкість в останньому побудованому слоті (для вимірюваних із живим сигналом — живе значення; для `load_share` — розрахунок за живою `p_now` вузла); `basis='qty_day'` — `Σ qty` за сьогодні; сортування за спаданням, максимум 8; значення 0 показуються.
2. `share = value / max(value)` (довжина смуги, як у макеті); `quality` — за методом (`measured` / `estimated`).
3. Баланс: `unaccounted = Σ rate(source) − Σ rate(consumer)`, `pct = unaccounted / Σ rate(source) × 100`; якщо немає `source`-точки — не рахується (`null`). Подій і тривог немає (A-14); `pct < −5 %` (споживачі разом більші за ввід) додає в `list.unaccounted` прапор `inconsistent: true` (UI — попереджувальний підпис «Оцінка перевищує облік»).

### R-12 Вкладки, підписи й підсумок (FR-08; D-31, D-32, D-48)

`tabs` = активні ресурси з принаймні одним активним лічильником, за `sequence`. `rate` — значення KPI `rate` (el — `kpis.grid.kw`). `sub = "{rate} {rate_unit}"` + (« · {cost} ₴», якщо `show_tab_cost` і є група вартості, інакше « · {source_note}», якщо задано). Вартість вкладки за сьогодні: el — `kpis.energy.cost_uah`; `price`-ресурси — `Σ cost` джерела; `derived_el` — R-02 п. 4; `derived_gas` — не показується (D-32). `meta.total.cost_uah = Σ cost_uah` вкладок із `is_derived=False`; `total.text` — формат D-31.

### R-13 Життєвий цикл резерву (FR-13, FR-15)

`_cron_detect` (і `action_run`): для кожного `enabled` правила, у якого знайшовся метод детектора (`_td_detector_methods()`; немає методу — `last_error='Детектор недоступний'`, пропуск):
1. `findings = detector(rule, now)` (R-14); виключення → `last_error`, решта правил продовжуються;
2. фільтр: `est_saving_month ≥ min_saving_uah`; знахідка відкидається, якщо за тим самим `dedup_key` є запис `dismissed` із `resolved_at > now − dismiss_days` або `done` із `resolved_at > now − cooldown_days`;
3. upsert за `dedup_key` серед `state='open'`: є — оновити `title`, `text`, `est_*`, `evidence`, `actions`, `last_seen_at` (**`in_plan` і `plan_*` зберігаються**); немає — створити (`found_at = last_seen_at = now`);
4. відкриті резерви правила, чий `dedup_key` не повернувся, → `expired` (`resolved_at = now`); `in_plan` зберігається як історія;
5. `actions` збираються з `rule.actions` + `control` (якщо задано `control_intent`: `{"code": "control", "label": rule.control_label, "kind": "control", "class": null, "params": {"intent": rule.control_intent}}`) + `ticket`-параметри: `description` містить тег `[OPP-<id>]` (після `create` — переформатовується);
6. `_td_link_requests()`: заявки `maintenance.request` із тегом `[OPP-<id>]` в описі → `request_id`; якщо заявка в стадії `done` (`stage_id.done`) — резерв → `done` (`result_note = "Заявку закрито"`, `resolved_by = заявка.user_id`); при виконанні дії `ticket` через майстер W1 заявка з'являється з тегом (майстер копіює `description`);
7. `bus.tick('advice')` не викликається (банер Пульта — окремий слот W1); екран ресурсів оновлюється за `kpi`.
`action_plan_toggle`: `in_plan := not in_plan` (для `state='open'`), `plan_user_id`, `plan_date`; `message_post` у чаттер «Додано до плану / Прибрано з плану».
`action_done(note)` → `state='done'`, `in_plan` не скидається; `action_dismiss` → `dismissed`.

### R-14 Спільні правила детекторів (FR-14)

- Сигнатура: `detect(env, rule, now) -> list[dict]`; елемент `{"dedup_key", "title", "text", "est_saving_month", "est_qty_month", "evidence", "node_code", "point_code"}`; `text` ≤ 400 символів, числа форматуються за R-25.
- Вікно: `L = rule.lookback_days` **повних** київських діб, що закінчуються вчора; недостатньо даних (менше 70 % слотів потрібних рядів або менше 3 діб) → `[]` без помилки (`last_count=0`).
- Ціна енергії: зважена `Σ(kwh·price) / Σ kwh` за зачепленими слотами (поле `price` інтервалів; немає ціни — 0 → знахідка відкидається).
- Місяць: `est_qty_month = qty_window × K_month(L)`; `est_saving_month = est_qty_month × price`; округлення `round(x, 0)` для ₴.
- `params_schema` кожного правила — розд. R-15…R-20, R-B2…R-B4; усі пороги редагуються у V-08 (`group_td_energy_manager`).
- `evidence` — числа, з яких отримано оцінку (для перевірки інженером), без персональних даних.

### R-15 `vent_offshift` — «Вентиляція працює поза змінами» (вкладка el; FR-14)

Параметри: `group="vent"`, `ratio_min=0,35`, `target_ratio=0,30`; `lookback_days=7`, `min_saving_uah=1000`, `control_intent="vent_night_mode"`.
1. Вузли: `td.energy.node` `kind='consumer'`, `group = params.group`; немає — `[]`.
2. За слотами вікна: `kw = Σ kwh × 4` цих вузлів (`td.energy.interval`, `role='consumer'`, `quality != missing`).
3. Розбивка за R-21: `day_level` = середнє `kw` усередині змін (потрібен принаймні один робочий день), `off_level` = середнє `kw` поза змінами.
4. `off_level < ratio_min × day_level` → `[]`.
5. `saving_kw = off_level − target_ratio × day_level`; `off_hours = (кількість слотів поза змінами)/4`; `saving_kwh_window = saving_kw × off_hours`; `est_qty_month = saving_kwh_window × K_month`; ціна — за слотами поза змінами.
6. `dedup_key = "vent_offshift:*"`; заголовок «Вентиляція працює поза змінами»; `evidence = {day_level_kw, off_level_kw, ratio, off_hours, nodes}`.
Фікстура: `L=7`, `day_level=100 кВт`, `off_level=50 кВт` (`ratio 0,5`), `off_hours=88`, ціна поза змінами `6,00` → `saving_kw = 50 − 30 = 20`; `saving_kwh_window = 1 760`; `est_qty_month = 1 760 × 4,33 = 7 620,8 кВт·год`; `est_saving = 45 725 ₴`.

### R-16 `idle_machines` — «Холостий хід верстатів під напругою» (el)

Параметри: `idle_share_min=0,05`, `recoverable=0,70`; `lookback_days=7`, `min_saving_uah=1000`; дія `link` на `td_energy.action_td_energy_alloc_pivot` («Звіт по РЦ»).
1. `td.energy.alloc` за дні вікна: `idle_kwh = Σ kwh` (`kind='idle'`), `rc_kwh = Σ kwh` (`kind in (direct, idle)`); `rc_kwh = 0` → `[]`.
2. `share = idle_kwh/rc_kwh`; `< idle_share_min` → `[]`.
3. `est_qty_month = idle_kwh × K_month × recoverable`; ціна = `Σ alloc.cost / Σ alloc.kwh` за `idle`-рядками.
4. `evidence = {idle_kwh, rc_kwh, share, top_nodes: [3 вузли з найбільшим idle]}`; текст «Між завданнями верстати стоять увімкненими: {idle_kwh} кВт·год за {L} діб, найбільше {top}.»
Фікстура: `idle_kwh=410`, `rc_kwh=6 000` (`share 6,8 %`), `price 8,40`, `L=7` → `est_qty_month = 410 × 4,33 × 0,7 = 1 242,7 кВт·год`; `est_saving = 10 439 ₴`.

### R-17 `air_leaks` — «Витоки стисненого повітря» (air)

Параметри: `ratio_min=0,10`, `min_flow=0,2` м³/хв, `reducible=0,65`; `lookback_days=7`, `min_saving_uah=1000`; дія `ticket` (`node_code="COMPRESSOR"`, опис «Пошук витоків стисненого повітря [OPP-<id>]»).
1. Джерело — лічильник `source`-точки повітря; для кожної ночі вікна — `night_min_d` = мінімум `rate_avg` слотів нічного вікна (покриття ≥ 70 %).
2. `night_flow = медіана(night_min_d)` (не менше 3 ночей); `day_flow` = середнє `rate_avg` усередині змін.
3. Знахідка, якщо `night_flow ≥ min_flow` і `night_flow/day_flow ≥ ratio_min`.
4. `spec = Σ kwh(cost_node) / Σ qty(air main)` за вікно (кВт·год на норм. м³; немає даних — `0,0883` = 5,3/60); `saved_flow = night_flow × reducible`; `qty_month_m3 = saved_flow × 60 × 730` (витоки працюють цілодобово); `est_qty_month = qty_month_m3 × spec` (кВт·год); ціна — `Σ cost / Σ kwh` вузла `cost_node`.
5. `evidence = {night_flow, day_flow, share_pct, spec, reducible}`.
Фікстура: `night_flow=1,6`, `day_flow=10,0` (16 %), `spec=0,0883`, ціна `8,40` → `saved_flow = 1,04`; `qty_month_m3 = 45 552`; `est_qty_month = 4 022,2 кВт·год`; `est_saving = 33 787 ₴`.

### R-18 `air_pressure` — «Тиск стисненого повітря завищений» (air)

Параметри: `margin_bar=0,3`, `k_per_bar=0,07` (7 %/бар), `min_save_bar=0,2`; `control_intent="air_pressure_setpoint"`.
1. `p_set` = свіжий `air/setpoint_bar` (контракт C-02), інакше параметр `air_setpoint_bar`.
2. `p_need = max(min_pressure_bar)` за активними `consumer`-точками з `min_pressure_bar > 0`, чия середня `rate_avg` за вікно `> 5 %` від `rate_nominal` (реально працюють).
3. `p_target = p_need + margin_bar`; `dp = p_set − p_target`; `dp < min_save_bar` → `[]`.
4. `kwh_window = Σ kwh` вузла `cost_node_id` за вікно; `est_qty_month = kwh_window × K_month × k_per_bar × dp`; ціна — вузла.
5. Текст: «Найвибагливіший споживач ({name}) потребує {p_need} бар; уставка {p_set}. Можна знизити до {p_target} бар.»
Фікстура: `p_set=7,0`, `p_need=6,2 (PRESS-1)`, `p_target=6,5`, `dp=0,5`, `kwh_window=4 494` (7 × 642), ціна `8,40` → `est_qty_month = 4 494 × 4,33 × 0,07 × 0,5 = 681,0 кВт·год`; `est_saving = 5 721 ₴`.

### R-19 `react_section` — «Реактивна енергія на секції» (el)

Вмикається лише при `tariff.tg_phi_limit > 0` і `react_rate > 0` (Q-03; інакше `[]` і `last_error='Немає параметрів доплати в тарифі'`). Параметри: `cos_target=0,92`, `min_hours_day=2,0`; `lookback_days=7`, `min_saving_uah=500`; дія — `link` на відкриту заявку ТО за вузлом `PFC-{s}` (`maintenance.hr_equipment_request_action`, `res_id`), інакше `ticket` (`node_code="PFC-{s}"`).
1. За секціями `s ∈ {1, 2}`: показання `energy/sections/S{s}/cos_phi` (сирі, вікно ≤ 30 діб): `h_low_d` — години доби з `cos < cos_target` (ступінчасте утримання); `h_low_avg = mean(h_low_d)`; `< min_hours_day` → секція пропускається.
2. За добами: `P_d` = інтеграл `energy/sections/S{s}/p_kw`, `Q_d` = інтеграл `…/q_kvar` (кВт·год, квар·год; розрахунок після компенсації — W1 R-35); `excess_d = max(0, Q_d − tg_phi_limit × P_d)`.
3. `penalty_month = mean(excess_d) × 30 × react_rate`; `est_saving_month = penalty_month`, `est_qty_month = mean(excess_d) × 30` (квар·год).
4. `dedup_key = "react_section:S{s}"`; текст «cos φ секції {s} — {cos_min}. Компенсація PFC-{s} не досягає цілі.».
Фікстура: `P_d=3 000`, `Q_d=1 650` (`tg 0,55`), `tg_phi_limit=0,40`, `react_rate=0,24` → `excess_d = 450`; `est_qty_month = 13 500 квар·год`; `est_saving = 3 240 ₴`.

### R-20 `pv_export` — «Експорт СЕС дешевше закупівлі» (el)

Параметри: `min_export_kw=10`, `capture=1,0`; `lookback_days=7`, `min_saving_uah=500`; `control_intent="pv_self_consumption"`, запасна дія — `link` на `td_energy.action_td_energy_generation`.
1. Слоти вводів, де `kwh_export × 4 ≥ min_export_kw`; `E = Σ kwh_export`.
2. `buy` — зважена ціна слотів (`interval.price` вводу), `export_price = tariff.export_price` на слоти; `diff = buy − export_price`; `diff ≤ 0` → `[]`.
3. `est_qty_month = E × K_month × capture`; `est_saving = est_qty_month × diff`.
Фікстура: `E=118 кВт·год` за 7 діб, `buy=8,40`, `export=2,00` → `est_qty_month = 118 × 4,33 = 510,9 кВт·год`; `est_saving = 510,9 × 6,40 = 3 270 ₴`.

### R-21 Вікна змін `tools/shifts.py` (FR-22; контракт C-01 для W4)

1. `load_windows(env)`: календар — `td.energy.shift_calendar_id` (`resource.calendar`); рядки `attendance_ids` (`display_type` порожній, `day_period != 'lunch'`) групуються за `(dayofweek, name)`; вікно = `[min(hour_from), max(hour_to)]`; якщо в календаря стандартні імена рядків («Monday Morning» тощо) — усі рядки дня утворюють одну зміну «Зміна»; календар не заданий або порожній — типове значення: пн–пт «Зміна 1» 07:00–16:00 і «Зміна 2» 16:00–23:00 (за макетом, Q-23).
2. API: `shift_of(local_dt) -> str | None`, `is_shift(local_dt) -> bool`, `windows_for(date) -> [(name, dt_from, dt_to)]`, `night_window(date) -> (dt_from, dt_to)` за `night_from_h`, `night_to_h`.
3. Усі межі — місцевий час; перехід DST враховується через `tools/dates.to_utc`.
Приклад (типове): вівторок 15:59 → «Зміна 1»; 16:00 → «Зміна 2»; 23:00 → `None`; субота 10:00 → `None`.

### R-22 Backfill ресурсів `td.energy.res.interval._td_backfill` (FR-18)

Призначення: дати екрану W3 і аналітиці W4 історію за `days` діб (за замовчуванням 90, максимум 400) у стику з електричним backfill W1 (R-36). **Передумова:** електричний `_td_backfill` за той самий період виконано (оцінкові точки беруть навантаження з `td.energy.interval`); інакше оцінкові слоти — `missing`, у лог — попередження.
1. Параметри: `days`, `until` (за замовчуванням `ceil15` першого показання `td.reading` сигналів ресурсів, інакше `floor15(now)`), `seed` (детермінізм: `rnd(seed, *key)` з `td_energy/tools/backfill.py`), `purge` (видалити `is_backfill=True` у діапазоні й вийти), `resources` (коди; за замовчуванням усі активні).
2. Генератори (`act(t) = clamp((P(t) − 210)/(667 − 210), 0, 1,3)`, `P(t)` — `backfill.target_p`; `sd(d) = clamp(0,5 + 0,5·cos(2π(doy − 15)/365), 0,1, 1)` — сезонність опалення):
   - газ: `heat_need = sd × (0,35 + 0,65·shift(t)) × 390 кВт` (+30 % при розігріві 05:30–07:00); `GM-BOILER = heat_boiler/(10,5·0,914)`, де `heat_boiler = max(0, heat_need − heat_chp)`; `GM-CHP = 109 м³/год`, коли КГУ працює (той самий критерій, що R-36 п. 6: 10 % будніх днів 16:00–19:00); `GM-MAIN = (GM-BOILER + GM-CHP + оцінки DRY-1, CANTEEN) × (1 + ε)`, `ε = 0,01 + 0,004·(2·rnd − 1)`;
   - повітря: `AM-MAIN = leak·(1 + 0,05·rnd) + (9,8 − leak)·act`, `leak = 1,6`; оцінкові споживачі — R-04;
   - вода: `WM-MAIN = (2,1 якщо зміна інакше 0,3) + 1,5·paint(t) + 0,0125`, `paint = 1`, коли `active(SPRAY-1) ≥ 0,5`; `WM-BOILER = 0,0125`; лічильники-накопичувачі з квантом 0,01 м³;
   - реактивна енергія: `P_s` з `td.energy.interval` вводів, `cos_s = 0,95` (секція 1) і `0,88` (секція 2) після компенсації, `Q = P·tan(acos cos_s)`;
   - тепло — гак `_td_backfill_extra(plan, seed, since, until)` (у ядрі порожній, міст — R-B5).
3. Запис: доба за добою, пакети ≤ 5 000, `INSERT … ON CONFLICT (meter_id, metric, ts_start) DO NOTHING`; `is_backfill=True`, `quality='measured'` для `counter`/`flow_integrate`-подібних рядів і `estimated` для оцінкових; `res_last_interval_start = max(наявне, останній слот)` — лише якщо немає живих слотів пізніше (як R-36 п. 10).
4. Повертає `{"meters": n, "slots": n, "rows": n, "skipped": n, "since": iso, "until": iso, "seconds": f}`.
5. Обмеження: 90 діб × 24 лічильники × 96 ≈ 207 000 рядків, ≤ 60 с; 400 діб ≈ 920 000 рядків, ≤ 300 с, ≤ 400 МБ RAM (ТП-04).
6. Властивості, що перевіряються: Σ `GM-MAIN` ≈ Σ гілок ± 3 %; добова витрата повітря корелює з `COMPRESSOR` кВт·год (ρ ≥ 0,9); нічний мінімум повітря ≈ 1,6 м³/хв; детермінізм; ідемпотентність; `purge` не чіпає `is_backfill=False`.

### R-23 Емулятор — див. розд. 8.1

### R-24 Експорт xlsx (API-07; FR-12)

1. Параметри: `day` (обов'язково, `YYYY-MM-DD`, не в майбутньому), `day_to` (за замовчуванням = `day`), `resources` (за замовчуванням усі активні); `Σ діб ≤ export_max_days`.
2. Джерело — `td.energy.usage` (`sudo()`) за `[day, day_to]` і вибрані ресурси, сортування `ts_start, resource, flow`; електричні потоки — `import`, `export`, `generation`, `load`.
3. Аркуш «Ресурси»: колонки «Ресурс», «Потік», «Об'єкт» (код вузла/точки), «Початок (Київ)», «Кількість», «Одиниця», «Ціна, ₴», «Вартість, ₴», «Якість»; колонки ціни/вартості — лише з `group_td_energy_cost`. Аркуш «Підсумок»: `Σ qty/cost` за ресурсом і потоком.
4. Формування `xlsxwriter` (`constant_memory`); рядків > 200 000 → `413`. Немає даних — файл із заголовками й порожнім аркушем.
5. Час у клітинках — локальний (Київ), форматування `dd.mm.yyyy hh:mm`.

### R-25 Формати чисел у відповідях API

| Величина | Правило |
|---|---|
| кВт, кВт·год, ₴ | ціле (`round`) |
| м³/год, м³/хв, м³/год у списках | `≥ 10` → ціле; `< 10` → 1 знак; вода `< 1` → 2 знаки (0,05) |
| м³ за добу | `≥ 100` → ціле; інакше 1 знак |
| `eff`, `share`, `%` | 1 знак |
| `tg φ`, `cos φ` | 2 знаки |
Значення в JSON — числа (не рядки); форматування рядків `note` — `fmt_dec`/`fmt_int` з `td_energy/tools` (кома — десятковий роздільник, вузький пробіл — роздільник тисяч).

## 10. Стани й переходи

| Об'єкт | Стани | Переходи (хто) |
|---|---|---|
| `td.energy.opportunity.state` | `open → done / dismissed / expired` | `action_done`, `action_dismiss` (manager), `_cron_detect` (спливання), `_td_link_requests` (заявку закрито → `done`); `done`/`dismissed` повторно відкриваються **створенням нового запису** після `cooldown_days`/`dismiss_days` |
| `td.energy.opportunity.in_plan` | `False ⇄ True` | `action_plan_toggle` (manager) лише для `state='open'`; при спливанні зберігається |
| `td.energy.res.interval.quality` | `measured / interpolated / estimated / missing` | перерахунок останніх двох слотів (R-05) може поліпшити якість; рядки `is_backfill` не перезаписуються |
| `td.energy.meter.mode` | `counter / flow_integrate / estimate` | зміна режиму — вручну manager; зміна очищає `res_last_interval_start` (перезбірка останніх 24 год) |

## 11. Обробка помилок

- **Немає даних / несвіжі сигнали:** значення `null`, `data_state` `partial|stale`, UI «—»; методи **не** кидають виключень через відсутність даних (як W1).
- **Немає ціни:** `price=0`, `cost=0`; у `res.config.settings` лічильник «ресурсів без ціни»; KPI без суми ₴ не обнуляються (показується «—»).
- **Немає сигналу `air/setpoint_bar`:** використовується `td.energy_resources.air_setpoint_bar`, у KPI примітка «уставка {x} (задана в налаштуваннях)».
- **Збій однієї точки/лічильника:** ізолюється `savepoint`, лог `_logger.exception`, решта продовжуються; `get_resources` за частинами: помилка в `kpis`/`chart`/`list`/`notes` не ламає решту (частина → `{"error": "…"}`, UI «Не вдалося завантажити: …»).
- **Дублікати:** `UNIQUE(meter_id, metric, ts_start)`; перегони двох кронів — `ON CONFLICT`.
- **Часові пояси:** зберігання UTC naive; `day`, `hour_local`, зміни, ночі — Київ; доби 23/25 год — за локальними слотами (W1 A-30).
- **Стик «історія / живі дані»:** живі рядки не перезаписують синтетичні; після `until` backfill слоти будує лише крон; ТК-03 перевіряє відсутність дір.
- **Видалена точка/лічильник:** `td.energy.res.interval` — `ondelete=cascade` за лічильником; резерви посилаються на `point_id` із `set null`.
- **Багатокомпанійність:** `company_id` у точок, цін, правил, резервів (record rules 4.3); лічильники успадковують `company_id` вузла/точки.
- **Міст відсутній:** гаки повертають порожнє; вкладка «Тепло» працює на лічильниках, якщо їх задано вручну.

## 12. Acceptance Criteria

Колонка «Тип»: UT (зокрема HttpCase і pytest емулятора) / UT-JS / TC / MAN. Усі `odoo`-тести — `post_install`, теги `-at_install`, `td`, `td_w3`. Фікстури — розд. 13.0. Числа у фікстурах узято з макета `Resources.dc.html` (14:20) там, де арифметика макета самоузгоджена.

### 12.1 `td_energy_resources` — AC-01…AC-64

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given встановлений модуль; When читаємо `td.energy.resource`; Then 5 записів (`resource_el|gas|heat|air|water`) зі значеннями таблиці 5.2: `rate_hour_factor` air = 60, решта 1; `kwh_per_unit` gas = 10,5; `co2_kg_per_unit` el 0,37 / gas 1,96; `is_derived` у heat і air; `in_energy_cost` у el і gas; `list_basis='qty_day'` у water | UT |
| AC-02 | FR-01 | Given довідник; When `code` дублюється / `rate_hour_factor ≤ 0` / `unlink` запису `el` / другий активний `el`; Then `ValidationError` / `ValidationError` / `UserError("Ресурс «Електрика» видаляти не можна.")` / `ValidationError("Ресурс «Електрика» має бути єдиним.")` | UT |
| AC-03 | FR-02 | Given ціна газу 19,80 з 2025-01-01; When `td.energy.price.create` для `el`; Then `ValidationError("Ціни електрики задаються в тарифі.")`; період, що перетинається, тієї самої компанії — `ValidationError`; `_td_price_at(gas, 2026-10-17) = 19,80`; дата поза періодами → `0.0`; `heat` при `boiler_eff = 0,91` → `2,0722` (допуск 1e-4) | UT |
| AC-04 | FR-03 | Given точки; When дубль `(resource, company, code)`, `parent_id` іншого ресурсу, цикл батьків, `estimate_method` без обов'язкових `params` (`load_share` без `node_id`, `schedule` без `from_h`, `residual` без `from`, `gate_loss` без `state_signal_id`); Then `ValidationError`/`IntegrityError` з текстами M-03 | UT |
| AC-05 | FR-04 | Given копія демо-БД (67 електричних лічильників, N інтервалів, M балансів); When `-u td_energy_resources`; Then у всіх 67 `resource_id = el`, `mode = 'counter'`; `count(td.energy.interval)` і `count(td.energy.balance)` не змінилися; повторне `-u` — без змін; `td_energy` 142 + W1 тестів зелені **і за наявності 16 неелектричних лічильників** (`cron_td_energy_live` не падає й не змінює їхній `data_state` на хибні події) | UT + DEPLOY_TEST |
| AC-06 | FR-04 | Given лічильники; When створюємо: `el` без `node_id`; не-`el` без `point_id`; не-`el` з `e_import_signal_id`; `counter` без `qty_signal_id`; `flow_integrate` без `flow_signal_ids`; `estimate` у точки без методу; `e_react_signal_id` на `role='feeder'`; Then `ValidationError` з текстами M-04. Регресія: лічильник газу (з `qty_signal_id`) **не** потрапляє в `td.energy.interval._cron_build` і `tools/backfill.Plan.meters` | UT |
| AC-07 | FR-05 | Given `td.energy.res.interval`; When вставляємо дубль `(meter, metric, ts_start)`; Then порушення `UNIQUE`; індекси `(day, resource_id)` і `(point_id, ts_start)` є в `pg_indexes` | UT |
| AC-08 | FR-05 | Given показання газу 0/300/600/900 с = 40/44/46/46 м³/год; When `integrate.flow(slot)`; Then `qty = 11,083`, `rate_avg = 44,33`, `coverage = 1,0`, `quality = measured` (допуск 1e-3) | UT |
| AC-09 | FR-05 | Given показання в 0 і 300 с (наступне через 1 000 с); Then `coverage = 0,333`, `interpolated`; єдине показання з розривами > 900 с — `missing`, `qty = 0`. Повітря: 9,6/9,8/10,0/9,8 м³/хв → `qty = 147,5`, `rate_avg = 9,83` | UT |
| AC-10 | FR-05 | Given `counter` газу з показаннями 100,00 → 100,35 → 100,70; When слот; Then `qty = 0,35`; скидання (100,70 → 0,10) — `interpolated`, `qty ≥ 0`; розрив > `gap_max_s` — `interpolated` | UT |
| AC-11 | FR-04 | Given лічильник теплоти з 25 сигналів (по 9,1 кВт); When слот; Then `rate_avg = 227,5`; один сигнал без показань — `interpolated`/`missing` за `coverage` | UT |
| AC-12 | FR-04 | Given EDGE-1 (`p_inst 67,5`, `load_factor 0,75`, `idle_factor 0,05`), `kw_avg = 41`, `rate_nominal = 3,0`; When `load_share`; Then `rate = 2,39` (`estimated`); немає інтервалу вузла → `missing`; `kw_avg` вище за `run_kw` → `active = 1`, нижче за `idle_kw` → 0 | UT |
| AC-13 | FR-04 | Given `schedule` `{"from_h":8,"to_h":16,"weekdays":[0..4],"rate":1.0}`; When вівторок 09:30 → 1,0; субота → 0; 16:00 → 0 (права межа виключається) | UT |
| AC-14 | FR-04 | Given вода: `WATER-MAIN 2,1`, `BOILER 0,0125`, `CANTEEN 0,22`, `SPRAY-1 0,3`; When `residual` `SOCIAL`; Then `1,5675`; якщо сума гілок > вводу — `0`; сиблінг `missing` → `missing` | UT |
| AC-15 | FR-04 | Given `loss_kw_per_k = 3,5`, `state_signal` відкритий половину слота, `t_in = 18`, `t_out = 7`; Then `rate_kw = 19,25`; немає сирих показань за слот → `missing` | UT |
| AC-16 | FR-05 | Given ціни; When будуємо слоти; Then газ: `612 × 19,80 = 12 117,60`; вода: `4,2 × 60 = 252,00`; тепло: `qty × 2,0722`; повітря: `Σ cost COMPRESSOR = 642 × 8,40 = 5 392,80` (R-02 п. 4); немає ціни — `price = cost = 0` | UT |
| AC-17 | FR-05 | Given `_cron_build`; When два прогони поспіль; Then другий створює 0 нових рядків, але перераховує два останні слоти; рядки `is_backfill=True` не перезаписуються; `td.energy.read_enabled = False` → 0 рядків; виключення на одному лічильнику логується, решта будуються | UT |
| AC-18 | FR-05 | Given рядки старші за `keep_interval_days`; When `_cron_rotate`; Then видалені (й синтетичні), свіжі цілі; пакети по 10 000 | UT |
| AC-19 | FR-06 | Given: ввід (kwh 100, export 20, cost 840), фідер (kwh 90), генерація (kwh 30), джерело газу (qty 612), гілка газу (qty 41), consumer-інтервал, `storage`-інтервал, `react`-рядок; When читаємо `td.energy.usage`; Then потоки: `import` 100/840/37 кг, `export` 20, `load` 90, `generation` 30, `supply` 612 (cost 12 117,60, CO₂ 1 199,5), `branch` 41; `consumer`, `storage`, `react` відсутні; `id` унікальні; без групи cost поле `cost` недоступне | UT |
| AC-20 | FR-07 | Given `PM-Q1.e_react_signal_id` і показання kvarh; When побудова; Then рядки `metric='react'`, `price = cost = 0`; доба `Q = 2 514`, `P = 6 284` → `tg φ = 0,40`, `cos φ = 0,93`; при `tg_phi_limit = 0,30`, `react_rate = 0,24` → `excess = 628,8`, `penalty = 150,9`; `tg_phi_limit = 0` → `penalty = 0` | UT |
| AC-21 | FR-08 | Given користувач `base.group_user` без груп енергетики / лише `group_td_energy_user` / з `…_cost`; When `get_resources()`; Then `AccessError` / відповідь без ключів `cost_uah`, `save_uah_month`, без «₴» у `note` і `tabs[].sub` / ключі присутні | UT |
| AC-22 | FR-09 | Given фікстура el (`grid_kw=358`, `contract=800`, `kwh=6 284`, `price=8,40`, `cost=52 786`); Then `grid_now.value=358`, note «45 % договірної 800 кВт»; `today.value=6 284`, note «52 786 ₴ · 8,40 ₴/кВт·год»; `reactive` за AC-20; дані беруться з `get_pult` W1 без дублювання розрахунку | UT |
| AC-23 | FR-09 | Given фікстура gas (`flow=46`, `today=612`, `price=19,80`, `GM-BOILER=540 м³`, `HM-BOILER=5 183 кВт·год`, `infra/chp/state=stop`); Then `rate` note «котельня BOILER · КГУ стоїть»; `today` note «12 118 ₴ · 19,80 ₴/м³»; `limit.value=1 200`, note «використано 51 %»; `eff.value=91,4`, note «норма ≥ 90 %», tone `good`, `quality='estimated'` | UT |
| AC-24 | FR-09 | Given фікстура air (`flow=9,8`, `p_now=52`, `pressure=7,1`, `setpoint=7,0`, `COMPRESSOR 642 кВт·год`, нічний мінімум 1,6, `day_mean=10,0`); Then `spec=5,3`, note «норма ≤ 6,0», `good`; `rate` note «тиск 7,1 бар · уставка 7,0»; `today_el` note «5 393 ₴»; `night_leak.value=1,6`, note «16 % від денної витрати», tone `bad` | UT |
| AC-25 | FR-09 | Given фікстура water (`today=4,2`, `night=0,05`, `boiler=0,3`); Then `today` note «252 ₴»; `night` note «норма ≤ 0,05», `good`; `boiler` note «норма ≤ 0,5 м³/добу», `good`; покриття нічного вікна < 70 % → `night.value = null` | UT |
| AC-26 | FR-08 | Given добова вартість el 52 786, gas 12 118, water 252, air 5 393, heat без ціни; Then `meta.total.cost_uah = 65 156` (air і heat не сумуються); текст за D-31; без групи cost — «Сьогодні: 5 ресурсів» | UT |
| AC-27 | FR-08 | Given `now_slot=57`; Then `chart.series` довжини 96, слоти після 57 — `null`, слот 57 — живе значення; `limit` el = `contract_kw`, gas = 80; `y_max`: газ 90, el 900, повітря 12, вода 0,6; `foot` для el/gas/air/water за R-10 (зокрема за гілок `leak_sentence`) | UT |
| AC-28 | FR-08 | Given точки газу (41 / 4 / 0 / 1 м³/год) і води (qty_day 2,6 / 1,1 / 0,3 / 0,2); Then список за спаданням, `basis` gas = `rate`, water = `qty_day`, `share` = `value/max`, нульові показані, максимум 8 | UT |
| AC-29 | FR-10 | Given `source 46`, споживачі `41+4+0+1`; Then `unaccounted = {0,0; 0,0}`; споживачі більші за ввід на 8 % → `inconsistent=true`; немає `source`-точки → `null` | UT |
| AC-30 | FR-08 | Given усі сигнали ресурсу несвіжі; Then `data_state='stale'`, значення `null`, виключень немає; частина лічильників несвіжа — `partial` | UT |
| AC-31 | FR-08 | Given ресурс `air` з `active=False` / без активних лічильників; Then вкладка відсутня в `tabs`; `get_resources('air')` → `UserError("Невідомий ресурс: air.")` | UT |
| AC-32 | FR-13 | Given дані модуля; Then 6 правил ядра (`vent_offshift`, `idle_machines`, `air_leaks`, `air_pressure`, `react_section`, `pv_export`) з `enabled`, `lookback_days`, порогами з R-15…R-20 і `resource`; `params_schema` коректна; `params` поза діапазоном → `ValidationError`; `actions` із невірним `kind` → `ValidationError` | UT |
| AC-33 | FR-13 | Given детектор повертає знахідку; When `_cron_detect`: 1-й прогін; 2-й з іншим числом; 3-й без знахідки; Then створено → оновлено (`in_plan` збережено) → `expired`; `dismissed` пригнічує повтор `dismiss_days`, `done` — `cooldown_days`; знахідка нижче `min_saving_uah` відкидається; виключення детектора пише `last_error`, решта правил працюють | UT |
| AC-34 | FR-14 | Given фікстура R-15 (`day 100`, `off 50`, `off_hours 88`, ціна `6,00`); Then `est_qty_month = 7 620,8`, `est_saving = 45 725`; `ratio < 0,35` → `[]`; немає вузлів `vent` → `[]`; даних < 3 діб → `[]` | UT |
| AC-35 | FR-14 | Given фікстура R-16 (`idle 410`, `rc 6 000`, ціна 8,40); Then `est_qty_month = 1 242,7`, `est_saving = 10 439`; `share < 5 %` → `[]`; `evidence.top_nodes` — 3 вузли | UT |
| AC-36 | FR-14 | Given фікстура R-17 (`night 1,6`, `day 10,0`, `spec 0,0883`, ціна 8,40); Then `est_qty_month = 4 022,2`, `est_saving = 33 787`, дія `ticket` на `COMPRESSOR` з тегом; менше 3 ночей → `[]`; `ratio < 10 %` → `[]` | UT |
| AC-37 | FR-14 | Given фікстура R-18 (`p_set 7,0`, `p_need 6,2`, `margin 0,3`, `kWh 4 494`, ціна 8,40); Then `est_qty_month = 681,0`, `est_saving = 5 721`; уставка береться із сигналу `air/setpoint_bar`, інакше з параметра; `dp < 0,2` → `[]` | UT |
| AC-38 | FR-14 | Given фікстура R-19 (`P 3 000`, `Q 1 650`, `tg_limit 0,40`, `rate 0,24`); Then `est_qty_month = 13 500`, `est_saving = 3 240`; без `tg_phi_limit` → `[]` і `last_error`; `h_low_avg < 2` → `[]`; дія веде на відкриту заявку PFC | UT |
| AC-39 | FR-14 | Given фікстура R-20 (`E 118`, `buy 8,40`, `export 2,00`); Then `est_qty_month = 510,9`, `est_saving = 3 270`; `buy ≤ export` → `[]` | UT |
| AC-40 | FR-15 | Given правило з `control_intent`; Then в `get_list` дія `control` має `enabled=false` (немає `td_energy_control`) і до списку додано `fallback_action`; при `_td_control_available=True` — `enabled=true`; `ticket`-дія містить `[OPP-<id>]` | UT |
| AC-41 | FR-15 | Given заявка ТО з тегом `[OPP-<id>]`; When `_td_link_requests`; Then `request_id` заповнений; переведення заявки в стадію `done` → резерв `done`, `result_note="Заявку закрито"` | UT |
| AC-42 | FR-13 | Given користувач `…_user` / `…_manager`; When `action_plan_toggle`, `action_dismiss`, `action_done`; Then `AccessError("Керувати резервами може лише енергетик.")` / успіх; для закритого резерву — `UserError("Резерв уже закрито.")`; повідомлення в чаттері | UT |
| AC-43 | FR-13 | Given 3 відкриті резерви (у плані 1); When `get_list`, `get_plan_summary`; Then `plan_sum`, `all_sum` дорівнюють сумам `est_saving_month`; без групи cost суми й `save_uah_month` відсутні; сортування за `in_plan desc, est_saving desc` | UT |
| AC-44 | FR-12 | Given 2 доби даних; When `GET /td/energy/resources/export?day=…`; Then `200`, xlsx з аркушами «Ресурси», «Підсумок»; колонки ціни/вартості — лише з групою cost; `400` — невірна дата, невідомий код, діапазон > `export_max_days`; `403` — без групи; `413` — рядків > 200 000 (ліміт підміняється в тесті) | UT |
| AC-45 | FR-12 | Given стенд, доба даних; When завантажити xlsx за вчора через UI; Then файл відкривається `openpyxl`, кількість рядків = кількість слотів × активних потоків; значення збігаються з `td.energy.usage` | TC |
| AC-46 | FR-18 | Given БД з електричним backfill і 16 неелектричними лічильниками; When `_td_backfill(days=2, seed=1)`; Then створено `18 × 192 = 3 456` рядків (16 лічильників + 2 `react`-метрики), усі `is_backfill=True`; `quality='estimated'` лише в оцінкових | UT |
| AC-47 | FR-18 | Given історія 7 діб; Then `Σ GM-MAIN` відрізняється від суми гілок ≤ 3 %; нічний мінімум повітря 1,6 ± 0,2 м³/хв; кореляція добової витрати повітря з `COMPRESSOR` кВт·год ≥ 0,9; однаковий `seed` → однаковий SHA-256 набору рядків; повторний виклик — `rows = 0`, `skipped = rows₁`; `purge=True` видаляє лише `is_backfill` | UT |
| AC-48 | FR-18 | Given живі рядки після `until`; When backfill; Then живі не перезаписуються, `res_last_interval_start` не зменшується; слоти `≥ until` не створюються | UT |
| AC-49 | FR-19 | Given користувачі `user`/`manager`/`admin`; Then `user` не пише в `resource`, `price`, `point`, `rule`, `opportunity`; `manager` — ціни, точки, правила (write), резерви (write); `admin` — усе; `td.energy.res.interval` пише лише `admin`/`sudo`; record rules за компанією | UT |
| AC-50 | FR-19 | Given `neutralize.sql`; Then 4 крони неактивні, джерела `MB-U74-GAS-MAIN`, `MB-U75-AIR-MAIN` — `read_enabled=false`; `uninstall_hook` видаляє неелектричні лічильники й повертає `node_id required`, електричні `interval`, `alloc`, події й сигнали цілі | UT + DEPLOY_TEST |
| AC-51 | FR-20 | Given `res.config.settings`; Then параметри блоку «Енергоресурси» редагує `…_manager`; `night_from_h ≥ 24`, `gap_max_s < 300`, `min_coverage ∉ (0, 1]` → `ValidationError`; зміна `night_to_h` змінює `night_rate` в R-09 | UT |
| AC-52 | FR-21 | Given тариф; Then `tg_phi_limit < 0` або `react_rate < 0` → `ValidationError`; `react_rate > 0` при `tg_phi_limit = 0` → `ValidationError("Ставка без ліміту tg φ не має сенсу.")`; `_td_react_penalty(100)` при `react_rate=0,24` → `24,0`; поля приховані без групи cost | UT |
| AC-53 | FR-22 | Given календар не заданий / два блоки «Зміна 1»+«Зміна 2» / стандартні імена рядків; Then `shift_of` за R-21 (вт 15:59 → «Зміна 1»; 16:00 → «Зміна 2»; 23:00 → `None`; сб 10:00 → `None`); доба переходу DST — межі змін коректні | UT |
| AC-54 | FR-17 | Given свіжа й наявна БД; When `_ensure_resource_signals`; Then створено 10 сигналів і 2 джерела, повтор — без змін; адреси/масштаби за 5.4 (зокрема `equipment/BOILER/gas_m3h` — BACnet AI:7); `air/pressure_bar` `warn_low=5,8`, `min_duration_s=300`, `create_request=False`; `air/setpoint_bar` **не** створюється | UT |
| AC-55 | FR-17 | Given моделі емулятора; Then `heat_kw=390` → `gas_m3h = 40,6`; `load=66` → `air flow = 9,8`; `load=25` → `1,6`; `air pressure = compressor − 0,1`; `boiler_m3_total` росте на `0,0125·max(1, boilers_on)` м³/год; `kvarh_total` росте на `|q_kvar|·dt/3600`; `gas` = `BOILER + CHP + dry + canteen` | UT (pytest) |
| AC-56 | FR-23 | Given сценарії `air_leak` (S-21), `gas_overuse` (S-22), `water_leak` (S-23); Then файл `td_sim_scenario_resources.xml` містить їх із параметрами; `air_leak` підвищує нічну витрату на 3,0 м³/хв; `gas_overuse` піднімає витрату джерела вище за 80 м³/год; `water_leak` — нічна витрата води +0,5 м³/год | UT (pytest) + TC |
| AC-57 | FR-11 | Given hoot з моком API-01; Then `Resources` перемикає вкладки; KPI й `tone`; графік будує 96 слотів, `null` розриває лінію, `limit` пунктиром; нотатки: `control` без обробника прихований, показується запасна дія; «Налаштувати пороги» — лише при `capabilities.manage`; посилання експорту містить `day` | UT-JS |
| AC-58 | FR-11 | Given `HttpCase`; When відкрити `action_td_energy_resources` для кожного з 5 ресурсів; Then без JS-помилок; пункт меню «Енергоресурси» видно `group_td_energy_user`, розділи налаштувань — `…_manager` | UT |
| AC-59 | FR-11 | Given стенд, 10 хвилин роботи; When відкрити екран; Then 5 вкладок із даними, `data_state='ok'`, значення змінюються без перезавантаження (шина, ≤ 10 с після тіку) | TC |
| AC-60 | FR-24 | Given БД із 90 добами історії; Then `get_resources(code)` ≤ 400 мс (медіана 10 викликів), ≤ 30 SQL, без N+1 за точками; `_cron_build` ≤ 5 с; запит `usage` за добу ≤ 200 мс | UT (ТП-01…03) |
| AC-61 | FR-24 | Given backfill 90 діб; Then ≤ 60 с, ≈ 207 000 ± 10 % рядків, ≤ 400 МБ RAM процесу | UT/TC (ТП-04) |
| AC-62 | FR-14 | Given стенд, запущено `air_leak`; When `action_run` правила `air_leaks` після ≥ 3 ночей історії; Then з'являється резерв `air_leaks`, KPI «Витоки вночі» вище за норму; зупинка сценарію → резерв переходить у `expired` при наступному прогоні | TC |
| AC-63 | FR-19 | Given запити до API-07 із `day='2026-10-17;DROP…'`, `resources='gas,../x'`, величезним діапазоном; Then `400`, без виконання SQL, без витоку даних у тексті помилки | UT |
| AC-64 | FR-16 | Given лише `td_energy_resources` (без моста); Then гаки `_td_heat_kpis`, `_td_heat_list`, `_td_heat_chart_note`, `_td_bind_extra` повертають порожнє; вкладка «Тепло» працює на вручну створених теплових лічильниках; `get_resources('heat')` не падає за відсутності BMS | UT |

**Разом `td_energy_resources`: AC-01…AC-64 = 64 критерії** (UT 55 — зокрема HttpCase, UT-JS 1 (AC-57), TC 3 (AC-45, AC-59, AC-62), UT+DEPLOY_TEST 2 (AC-05, AC-50), UT-pytest 1 (AC-55), UT-pytest+TC 1 (AC-56), UT/TC 1 (AC-61)).

## 13. План тестування (для Opus)

### 13.0 Фікстури й вимоги до тестованості

- `tests/common.py` (A): `TestW3Common(TransactionCase)` — `_resource(code)`, `_point(code, resource, kind, **vals)`, `_meter(code, point, mode, signals=..)`, `_signal(code, value, ts=now, status='ok')`, `_reading(code, ts, value)`, `_node_interval(node_code, ts, kwh, price=8.40)` (електричні `consumer`/`incomer`/`feeder`), `_res_interval(meter, ts, qty, quality='measured')`, `_user(groups)`, мок часу `patch("odoo.addons.td_energy.tools.dates.now_utc")`.
- Час завжди через `td_energy.tools.dates.now_utc(env)` (мокується); детермінізм backfill — `seed`.
- Фікстура «Макет 14:20» (`TestW3Common._mockup_1420()`): сигнали й інтервали під числа AC-22…AC-26 (358 кВт, 6 284 кВт·год, 46 м³/год, 612 м³, 9,8 м³/хв, 4,2 м³ тощо); використовується тестами `test_w3_dashboard.py`.
- JS: hoot, мок `orm.call` із JSON з розд. 7.

### 13.1 Юніт-тести (A, B, C)

| Файл | Клас | Покриває |
|---|---|---|
| `test_w3_data.py` (A) | `TestW3Data` | AC-01…AC-07, AC-49, AC-50, AC-52, AC-53, AC-54 (`test_resources_seed`, `test_resource_constraints`, `test_price_rules`, `test_point_constraints`, `test_meter_default_el_migration`, `test_meter_binding`, `test_electric_cron_untouched`, `test_signals_ensure`, `test_tariff_react`, `test_uninstall_hook`) |
| `test_w3_integrate.py` (A) | `TestW3Integrate` | AC-08…AC-11 (`test_flow_trapezoid`, `test_flow_coverage`, `test_flow_air`, `test_counter_reset`, `test_multisignal`) |
| `test_w3_estimate.py` (A) | `TestW3Estimate` | AC-12…AC-15 |
| `test_w3_cost.py` (A) | `TestW3Cost` | AC-16, AC-17, AC-18, AC-20, AC-51, AC-60 (ТП-02, ТП-03) |
| `test_w3_usage.py` (A) | `TestW3Usage` | AC-19 |
| `test_w3_dashboard.py` (E) | `TestW3Dashboard` | AC-21…AC-31, AC-64 (блок `notes` — через `patch` на `td.energy.opportunity.get_list`, якщо модель резервів ще не влито) |
| `test_w3_export.py` (E) | `TestW3Export` | AC-44, AC-63 |
| `test_w3_backfill.py` (A) | `TestW3Backfill` | AC-46…AC-48, AC-61 |
| `test_w3_security.py` (E) | `TestW3Security` | AC-60 (ТП-01), ТБ-01…ТБ-04 |
| `test_w3_opportunity.py` (B) | `TestW3Opportunity` | AC-32, AC-33, AC-40…AC-43 |
| `test_w3_detectors.py` (B) | `TestW3Detectors` | AC-34…AC-39 (по методу на детектор: `test_vent_offshift`, `test_idle_machines`, `test_air_leaks`, `test_air_pressure`, `test_react_section`, `test_pv_export`) |
| `test_w3_ui.py` (C) | `TestW3Ui` | AC-58 |
| `test_w3_hoot.py` (C) | `TestW3Hoot.test_hoot_suite` | AC-57 (запуск `/web/tests?headless…&id=<hash('@td_energy_resources')>` за зразком `td_energy/tests/test_w1_hoot.py`) |
| `services/iot_sim/tests/unit/test_gas.py`, `test_air.py`, `test_water_boiler.py`, `test_meter_kvarh.py` (D) | pytest | AC-55, AC-56 |

### 13.2 Стендові сценарії ТК-01…ТК-06 (`tests/stand/test_w3_tk.py`, D)

Передумова: стенд E-11 (емулятор + збирач + Odoo), встановлено `td_energy`, `td_energy_resources`, `td_bms`, `td_energy_resources_bms`; електричний `_td_backfill(days=90)` виконано ≥ 5 хв після старту збирача; потім `td.energy.res.interval._td_backfill(days=90)`.

| ТК | Назва | Кроки | Очікується |
|---|---|---|---|
| ТК-01 | Екран живий | відкрити «Енергоресурси», 10 хв | 5 вкладок, KPI заповнені, `data_state='ok'`, графік без розривів за останню годину, значення оновлюються за шиною |
| ТК-02 | Нові сигнали | `td.signal` за 10 кодами розд. 5.4 | `status='ok'`, `last_ts` ≤ 2 хв, лічильники ростуть, `infra/gas/flow_m3h` ≈ сумі гілок ±5 % |
| ТК-03 | Стик історії й живих | `get_resources` + запит `res.interval` на межі `until` | слотів `missing` на стику 0; графіки газу/повітря/води безперервні; `is_backfill` змінюється на `False` одним переходом |
| ТК-04 | Витік повітря | запустити `air_leak` (S-21) на ≥ 1 ніч (або прискорені години емулятора), потім `action_run` правила | KPI «Витоки вночі» > 10 % денної; резерв `air_leaks` створено; зупинка сценарію → `expired` |
| ТК-05 | Перевитрата газу | запустити `gas_overuse` (S-22) | витрата джерела > 80 м³/год, лінію ліміту перетнуто, KPI «Ліміт доби» росте |
| ТК-06 | Експорт | завантажити xlsx за вчора | AC-45 |

### 13.3 Тести безпеки (ТБ-01…ТБ-04)

- ТБ-01: `base.group_user` без груп → `AccessError` на всіх публічних методах `td.energy.res.dashboard`, `td.energy.opportunity` і `403` на експорті (AC-21, AC-44).
- ТБ-02: ключі вартості відсутні в користувача без `group_td_energy_cost` в API-01, API-02, API-06, API-10, xlsx (AC-21, AC-43, AC-44).
- ТБ-03: ACL: `user` не змінює резерви/правила/ціни/точки (AC-42, AC-49).
- ТБ-04: параметри експорту не призводять до SQL-ін'єкції й довільних шляхів (AC-63).

### 13.4 Тести продуктивності (ТП-01…ТП-05)

- ТП-01: `get_resources(code)` ≤ 400 мс, ≤ 30 SQL на будь-якій вкладці (AC-60).
- ТП-02: `_cron_build` ≤ 5 с для 24 лічильників (AC-60).
- ТП-03: запит `td.energy.usage` за добу ≤ 200 мс; за 30 діб ≤ 1,5 с на БД із 90 добами (AC-60).
- ТП-04: `_td_backfill(days=90)` ≤ 60 с, ≤ 400 МБ (AC-61).
- ТП-05: `_cron_detect` (6 правил) ≤ 60 с на БД із 90 добами історії.

### 13.5 DEPLOY_TEST

1. Копія демо-БД із W1 (`td_demo_tpl`) → `-i td_energy_resources` → перевірити кількості (розд. 5.5), тести `td_energy` зелені (AC-05).
2. Повторне `-u td_energy_resources` — без змін.
3. Відкат: `uninstall` → AC-50 (електричне ціле, `node_id required`).
4. `neutralize.sql`.
5. Встановлення з `td_bms` (міст автоматично ставиться) і без нього (AC-64).

### 13.6 Розподіл тестів і команд за воркерами (виписка з ARCH §6)

Крок 0 — каркас менеджера (порожні файли, `__init__.py`, маніфести); `T=factory3d/tools/odoo`. Не більше 3 воркерів паралельно на стадію; спільних файлів немає (власники — розд. 0).

| Стадія | Воркер | Тести | Команда |
|---|---|---|---|
| 1 | A «Дані» | `test_w3_data`, `test_w3_integrate`, `test_w3_estimate`, `test_w3_cost`, `test_w3_usage`, `test_w3_backfill` | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3a /td_energy_resources:TestW3Data` (потім `…TestW3Integrate`, `…TestW3Estimate`, `…TestW3Cost`, `…TestW3Usage`, `…TestW3Backfill`); регрес `$T/run_tests.sh td_w3a_reg /td_energy` |
| 1 | D «Емулятор і сигнали» | `services/iot_sim/tests/unit/test_{gas,air,water_boiler,meter_kvarh}.py`; стенд `tests/stand/test_w3_tk.py` | `pytest services/iot_sim/tests/unit/test_gas.py services/iot_sim/tests/unit/test_air.py services/iot_sim/tests/unit/test_water_boiler.py services/iot_sim/tests/unit/test_meter_kvarh.py`; стенд — менеджер |
| 2 | E «API екрана й експорт» | `test_w3_dashboard`, `test_w3_export`, `test_w3_security` | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3e /td_energy_resources:TestW3Dashboard` (потім `…TestW3Export`, `…TestW3Security`) |
| 2 | B «Резерви й міст» | `test_w3_opportunity`, `test_w3_detectors`, `test_wb_bridge` | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3b /td_energy_resources:TestW3Opportunity` (потім `…TestW3Detectors`); міст: `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3bb /td_energy_resources_bms` |
| 2 | C «Екран (OWL)» | `test_w3_ui`, `test_w3_hoot` | `F3D_TEST_INSTALL=td_energy,td_energy_resources $T/run_tests.sh td_w3c /td_energy_resources:TestW3Ui` і `…:TestW3Hoot` |
| — | менеджер (інтеграція) | усе | `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_resources,td_energy_resources_bms $T/run_tests.sh td_w3_full`; потім стенд ТК-01…ТК-06, ТК-B1 |

## 14. Definition of Done (W3, `td_energy_resources`)

- Усі UT/UT-JS AC-01…AC-64 зелені; ТК-01…ТК-06 пройдені на стенді; `ruff` без помилок; регресія `td_energy` (142 тести + W1) зелена;
- `neutralize.sql` оновлено; CHANGELOG, README (розділи «Енергоресурси», «Резерви економії»), DEPLOY_TEST доповнено; огляд безпеки (ТБ-01…ТБ-04);
- міграцію 19.0.1.0.0 перевірено на копії БД; backfill виконано на стенді, скріншоти п'яти вкладок;
- рядки емулятора в `catalog/signals.csv` і `td_iot_sim/data/td_sim_signal.csv` ідентичні (звірка скриптом), `n` перераховано при злитті з W2 (сигнали W3 — n 1206…1215).

## 15. Відкриті питання й рішення автора

### Питання Q-01…Q-08

| ID | Питання | Кому | Рекомендація | Що робимо поки |
|---|---|---|---|---|
| Q-01 | Яке паливо в реальної котельні: газ (макет) чи брикети (демо-модель `BOILER`)? | замовник | газ; демо лишає обидва канали (D-35) | газовий канал емулятора — за E-07 |
| Q-02 | Які прилади обліку газу/повітря/води/тепла є та їхні протоколи/регістри; паспортні витрати повітря | замовник, електрики | будувати на оцінках (`estimated`), реальні прилади підключати заміною лічильника на `counter`/`flow_integrate` без правки UI | `ПРИПУЩЕННЯ` у 5.3/5.4; позначка «оцінка» в UI |
| Q-03 | Чи є в договорі доплата за реактивну енергію (`tg φ` ліміт, ставка) | замовник | так/ні; параметри в тарифі | правило `react_section` і «ризик доплати» вимкнені без параметрів |
| Q-04 | Чи потрібні калориметри на тепло (прихід) окремо від моделі BMS | замовник | пізніше; точка `source` із `counter` замінює інтеграл | тепловичислювачі з BMS-сигналів |
| Q-05 | Джерело цін газу й води (договір, індексація) | бухгалтерія | ручна таблиця `td.energy.price` із датами | ціни демо 19,80 і 60,00 |
| Q-06 | Чи допустимий новий HTTP-маршрут `/td/energy/resources/export` (раніше блок обходився ORM) | менеджер | так (автентифікований GET, перевірка групи) | реалізовано (A-10) |
| Q-07 | Власник сигналу `air/setpoint_bar` | менеджер W2 | W2 (уставка й команди компресора) | параметр `air_setpoint_bar`, читання сигналу, якщо з'явиться |
| Q-08 | Сигнал відкриття доквих воріт (`td.yard.gate` — шлагбауми) | замовник | датчик відкриття воріт відвантаження в BMS/Yard | точка `DOCK` і правило `dock_gates` активні лише за наявності сигналу |

### Рішення автора (A-01…A-16)

| ID | Рішення | Обґрунтування |
|---|---|---|
| A-01 | Два модулі: `td_energy_resources` (ядро ресурсів) + `td_energy_resources_bms` (`auto_install`) | D-18: зв'язок із `td_bms` необов'язковий; міст розв'язує порядок встановлення й дає `hvac_ref` без жорсткої залежності; GAP пропонував один модуль — менеджер може згорнути міст у ядро (тоді `depends += td_bms`) |
| A-02 | Неелектричні лічильники — той самий `td.energy.meter` (`_inherit`), `node_id required=False` + `_check_resource_binding`; у них немає `e_import_signal_id`, тому електричні розрахунки їх не бачать | єдиний реєстр лічильників і перевірка; регресію `td_energy` виключено (AC-06) |
| A-03 | Окрема таблиця `td.energy.res.interval` + SQL-view `td.energy.usage` (без `row_number`) | GAP Q-04; електричні запити й 142 тести не зачіпаються; view дає єдине зведення для W4 |
| A-04 | Реактивна енергія — `metric='react'` у `res.interval` на електричних вводах, не нова таблиця й не роль лічильника | не змінює семантику `td.energy.interval`, не потрапляє в електричний крон |
| A-05 | Оцінкові методи описуються на **точці** (`estimate_method`, `estimate_params`), лічильник режиму `estimate` лише посилається на неї | метод — властивість сутності, а не каналу; один набір даних для backfill і крона |
| A-06 | Мультисигнальний лічильник (`flow_signal_ids`, сума) замість обчислюваного сигналу `ventilation/totals/heat_kw` | не плодити обчислювані сигнали; 25 установок RV рахуються одним рядком |
| A-07 | `in_plan` — окремий булів прапор резерву, `state` — лише життєвий цикл | чекбокс «У плані» (W4) не повинен змінювати статус; планова історія зберігається при `expired` |
| A-08 | Реєстр детекторів — модуль `tools/detectors/` + методи `_td_detect_<code>` у `td.energy.opportunity.rule`, міст додає свої через `_inherit` | як реєстр правил `_td_advice_rule_*` W1; розширюваність без правок ядра |
| A-09 | Тепло — через міст: точки/лічильники з `td.bms.heat.balance` і `td.bms.hvac.unit`, KPI «Температура»/«Рекуперація», 3 детектори | GAP §4.4; BMS-сигнали не дублюються |
| A-10 | Експорт — власний маршрут xlsx (`xlsxwriter`), а не стандартний експорт Odoo | стандартний експорт працює за однією моделлю й не дає «в один клік» усіх ресурсів (RS-15) |
| A-11 | Параметри — `td.energy_resources.*`; модульна нумерація ID, наскрізні D-xx із діапазоном D-31…D-50 | конвенція §5 (`td.<module>.<param>`); відмінність від W1, де параметри `td.energy.*` |
| A-12 | Прапори ресурсу (`is_derived`, `in_energy_cost`, `show_tab_cost`) задають склад сум: «разом» (heat, air — ні), «вартість енергії» W4 (el, gas) | у макеті два різних набори |
| A-13 | Вкладка показує **усі** відкриті резерви свого ресурсу (D-40) | єдине джерело з аналітикою |
| A-14 | Баланси газу/води (джерело проти гілок) — лише індикатор у списку, без подій і тривог | немає узгоджених допусків; події — Q при появі реальних приладів |
| A-15 | Вікна змін — спільний хелпер `tools/shifts.py` у `td_energy_resources` (використовується W4) на календарі `td.energy.shift_calendar_id`; типове значення — зміни макета | Q-23 W1; одне джерело правди |
| A-16 | `uninstall_hook` видаляє неелектричні лічильники (і тим самим повертає `node_id required`) | інакше відкат модуля ламає схему `td.energy.meter`; електричні дані не зачіпаються |

---

## Журнал змін документа

| Дата | Версія | Зміна |
|---|---|---|
| 18.10.2026 | 0.1 | Перша редакція — Частина I `build/energy/W3_SPEC.md` (хвиля W3) |
| 19.10.2026 | 0.2 | Перенесено до `docs/modules/td_energy_resources/`, переклад українською (технічні імена, ID, код, JSON — без змін); Частина II (міст) — у [../td_energy_resources_bms/SPEC.md](../td_energy_resources_bms/SPEC.md); внесено відхилення збірки (нижче) |

### Рішення й відхилення, прийняті при збірці W3

1. **`equipment/BOILER/gas_m3h` — BACnet AI instance 7** (`BOILER_GasFlow`), а не AI:6 із початкового припущення: за картою `BOILER` емулятора AI:4 (`FlueGasTemp`) і AI:6 (`BriquettesToday`) зайняті (розд. 5.4, `resource_signals.csv`, `td_sim_signal.csv`, AC-54). Адреса лишається **ПРИПУЩЕННЯМ** (Q-02).
2. **Сигнали емулятора W3 мають n 1206…1215** (після W2: n 1178…1205 — вікно керування `SWB-CTRL`); джерела `GAS-MAIN` — Modbus unit 74, `AIR-MAIN` — unit 75; сценарії емулятора **S-21 `air_leak`, S-22 `gas_overuse`, S-23 `water_leak`** (розд. 5.4, 8.1, AC-56, ТК-04, ТК-05); версія `td_iot_sim` `19.0.2.0.4`.
3. **Нові сигнали `td_iot_sim` на сервері з уже встановленим модулем** потрапляють у реєстр симулятора через `td_iot_sim.hooks.refresh_registry` (міграція/оновлення `-u td_iot_sim`), без перевстановлення (розд. 2.8 ARCH, 8.1).
4. **V-11 `action_td_energy_resources_rebind`** — серверна дія «Оновити прив'язку ресурсів» (меню `menu_td_energy_resources_rebind`, seq 80, `group_td_energy_manager`): виконує `hooks._seed_points_meters` і `_bind_react_signals`, потім хук моста `_td_bind_extra` (розд. 3.1, 3.3).
5. **`limit_kind` має підпис «Вид ліміту»**; значення: `none` «Без ліміту», `fixed` «Фіксований», `tariff_contract` «Договірна потужність» (M-01).
6. **V-04: `meter_count` замінено на `meter_ids`** (віджет `many2many_tags`); поле `meter_count` (compute) лишається в M-01 для smart-кнопки ресурсу.
7. **«Запустити зараз» (V-08)** — не кнопка `type="object"`, а `type="action"` на серверну дію `action_td_energy_opportunity_rule_run`: `action_run` повертає словник статистики (API-05), серверна дія загортає його у сповіщення.

