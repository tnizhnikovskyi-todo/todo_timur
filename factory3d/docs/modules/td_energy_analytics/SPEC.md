> **Розміщення (W4).** Основний SPEC `td_energy_analytics`: спільна преамбула (позначення, діапазони ID, відхилення D-51…D-80) і Частина I — розділи 0–15 модуля `td_energy_analytics`. Пов'язаний модуль — `td_energy_mobile` ([../td_energy_mobile/SPEC.md](../td_energy_mobile/SPEC.md), Частина II; преамбула повторена в ньому).
> Зміни контрактів C-01…C-08, API-01 і API-H1 — лише через менеджера (JSON-еталони: `odoo_addons/td_energy_analytics/contracts/`, `odoo_addons/td_energy_mobile/contracts/`). Посилання на розділи «0», «H.0» тощо — усередині цього файлу.
> Читати лише шматками: `grep -nE '^#{2,3} ' <файл>`, потім Read з offset/limit.

# td_energy_analytics — специфікація (W4 «Аналітика й мобільний»: модулі `td_energy_analytics` і `td_energy_mobile`)

Версія 0.2 · 19.10.2026 (v0.1 — 18.10.2026) · стандарт `docs/DOC_STANDARD.md` · технічне рішення: [ARCHITECTURE.md](ARCHITECTURE.md) (далі ARCH: FR-01…FR-24 і FR-H1…FR-H10, A-01…A-18 і A-H1…A-H6, Q-01…Q-09 і Q-H1…Q-H3) · статус: збудовано (гілка `claude/td-energy-w4`); відхилення збірки — у «Журналі змін документа» в кінці файлу.
Вхід: `build/energy/GAP.md` (E-01…E-11, §5 «Аналітика», AN-01…AN-23, MB-08, MB-09), макети `Analytics.dc.html` і `Mobile.dc.html` (вкладки «Стан», «Тривоги», «Схема», **«Обхід»**); контракти W1 (`W1_SPEC.md`: API-05/API-12, R-27, R-32 `actions[]` = C-32, R-33, R-36, реєстр мобільних вкладок C-33, UI-09) і W3 ([../td_energy_resources/SPEC.md](../td_energy_resources/SPEC.md): `td.energy.usage`, `td.energy.opportunity`, `tools/shifts.py`, `td.energy.price._td_price_at`, контракт C-01).
Спирається на: `docs/ARCHITECTURE.md` §3, §5, D-18; код `td_energy` на гілці `claude/factory3d-build` (`d14d13c`: `td.energy.interval`, `td.energy.alloc`, `td.energy.node`, `tools/{dates,forecast,backfill,bus}.py`, `static/src/mobile/mobile.js`); `td_telemetry` (`td.reading.hour`); `mrp`, `mrp_account`, `stock_account` (`stock.move.value`, Odoo 19).
Мова: проза — українською (`docs/DOC_STANDARD.md`), рядки інтерфейсу, `string=` і тексти помилок — українські.
Документ розкладено за модулями: `td_energy_analytics` (цей файл — Частина I) і `td_energy_mobile` ([../td_energy_mobile/SPEC.md](../td_energy_mobile/SPEC.md) — Частина II).

## Умовні позначення, діапазони ID, відхилення від макета

**Імена (E-09).** Модулі: `td_energy_analytics`, `td_energy_mobile`; моделі `td.energy.*`; поля стандартних моделей — `td_*`; нові методи — `_td_*`; параметри — `td.energy_analytics.<param>` і `td.energy_mobile.<param>`; глобальні стоп-крани — `td.energy.read_enabled` (спільний). HTTP-маршрутів немає (окрім стандартного `/report/pdf/...` Odoo).

**Діапазони ID.** Нумерація модульна, як у W3: поза таблицями ID пишеться з модулем (`td_energy_analytics M-08`). Для другого модуля документа — префікс `H` (mobile, «handheld»): FR-H1, M-H1, V-H1, API-H1, R-H1, AC-H01, UI-H1, A-H1, Q-H1, ТК-H1. Наскрізні для блоку D-xx: W1 D-01…D-18, W2 (D-19…D-49), W3 D-31…D-50 (нумерація W2 і W3 перетинається — у модульних документах D-xx діє в межах свого документа), **W4 D-51…D-80** (аналітика D-51…D-69, мобільний D-70…D-78).

| Тип | `td_energy_analytics` | `td_energy_mobile` |
|---|---|---|
| FR | FR-01…FR-24 | FR-H1…FR-H10 |
| M | M-01…M-16 | M-H1…M-H7 |
| V | V-01…V-16 | V-H1…V-H6 |
| API | API-01…API-15 | API-H1…API-H6 |
| R | R-01…R-22 | R-H1…R-H8 |
| AC | AC-01…AC-62 | AC-H01…AC-H26 |
| UI | UI-01…UI-10 | UI-H1…UI-H4 |
| ТК / ТБ / ТП | ТК-01…ТК-05 / ТБ-01…ТБ-04 / ТП-01…ТП-05 | ТК-H1…ТК-H3 / ТБ-H1…ТБ-H2 / ТП-H1…ТП-H2 |
| A (рішення автора) | A-01…A-18 | A-H1…A-H6 |
| Q | Q-01…Q-09 | Q-H1…Q-H3 |

Позначення: UT — юніт-тест `odoo.tests` (`TransactionCase`/`HttpCase`), UT-JS — hoot, TC — стенд (емулятор + збирач + Odoo + браузер), MAN — вручну. `req`=`required=True`, `idx`=`index=True`, `cost` = `groups="td_energy.group_td_energy_cost"`. Усі `Datetime` — UTC naive; «Київ» — `Europe/Kyiv` (`td_energy/tools/dates.py`). Періоди: `w` (7 днів), `m` (30 днів), `q` (квартал), `y` (рік).

### Відхилення від макета (D-xx)

| ID | Де в макеті | Що в реалізації | Чому |
|---|---|---|---|
| D-51 | Analytics: KPI «Електроенергія 186 400 кВт·год», «Вартість 1 937 880 ₴» (= 186 400 × 8,40 + газ) | «Електроенергія» = споживання заводу (Σ фідерів); «Вартість» = вартість **купівлі** (імпорт за зонами тарифу + газ); арифметика макета відтворюється лише у фікстурах AC | Макет рахує все за плоскою ціною, реальний тариф зональний |
| D-52 | «−6 % до бази» | Δ до моделі бази ISO 50001: `Σ факт / Σ очікування − 1` за період; без затвердженої бази — «—» і підказка «База не задана» | GAP AN-03, AN-13 |
| D-53 | «Газ +2 % до бази · похолодання» | база газу — окрема модель із драйвером HDD; підпис «похолодання»/«тепліше» обчислюється (R-07) | AN-04 |
| D-54 | «Власна генерація 18 %, СЕС 41 000 кВт·год» | `(генерація − експорт) / споживання`; підпис «СЕС {кВт·год}» — з `gen_pv_qty` | Формула в макеті не вказана; значення 18 % відтворюється |
| D-55 | «Викиди CO₂ 105 т · мережа 69 т · газ 36 т на місяць» | рахується за вибраний період; електрика — за імпортом із мережі (самогенерація без викидів), газ — за `co2_kg_per_unit` ресурсу | Підпис «на місяць» невірний для періодів 7 днів…рік |
| D-56 | Стовпці: рівно 8 категорій | 8 ділянок + при ненульовому залишку 9-й сірий сегмент «Без ділянки» (вузли без `area_id`) | Дані не зобов'язані бути повністю розмічені |
| D-57 | Теплокарта: фіксований масштаб 700 кВт | `max_ref = ceil50(максимум комірки)`, 5 рівнів; базове навантаження — мінімум комірок, округлення до 5 | Масштаб за даними |
| D-58 | EnPI-графік і бюджет — за місяцем/12 тижнями за будь-якого періоду | Збережено: вікна EnPI (12 ковзних тижнів) і бюджету (календарний місяць) не залежать від перемикача періоду | Як у макеті |
| D-59 | «56 % при 55 % місяця» | `part_місяця = день_місяця / кількість_днів`; прогноз = факт + типові доби за днем тижня (R-06) | Макет не розкриває формулу |
| D-60 | Колонка «До бази» в зрізах (−4 %, +3 %…) | Для кожного рядка: відносна зміна питомого показника до того самого ключа у вікні бази (R-15); немає даних у вікні — «—»; для замовлень — до питомого показника продукту у вікні бази | GAP AN-20 «спрощено» |
| D-61 | «Фасади МДФ — 3,10 кВт·год/м²» (на м² фасаду) | питоме — на м² плити (`plate_m2`) за замовчуванням; драйвер «м² фасаду» не створюється (Q-05) | У даних немає площі фасадів |
| D-62 | Зміни: «Зміна 1 07:00–16:00», «Зміна 2 16:00–23:00», «Ночі й вихідні» | вікна — календар `td.energy.shift_calendar_id` (W3 R-21, типове значення — зміни макета); площа плит за змінами — пропорційно енергії прямих верстатів | Немає часу доби у виробничих проводках (A-12) |
| D-63 | «Резерви економії» — 8 рядків | показуються всі відкриті резерви (9 правил W3: додано `dock_gates`); «У плані» зберігається (поле `in_plan` W3), а не живе в стані сторінки | W3 D-47 |
| D-64 | Кнопки дій резервів: тости | реальні дії за контрактом C-32 (link/ticket/control); `control` прихований без `td_energy_control` (запасне — «Відкрити») | W1 D-02 |
| D-65 | Деталізація: тост «профіль, події, обладнання за 30 днів» | відкривається стандартний список/зведена таблиця з доменом зрізу (`ir.actions.act_window`) | Немає довільної «панелі» в Odoo без кастомного OWL; стандартних подань достатньо |
| D-66 | «квартал», «рік» | квартал = 13 ковзних тижнів (91 день, вікно закінчується сьогодні); рік = 12 календарних місяців, останній — неповний | Однозначні вікна |
| D-67 | «Звіт для керівництва» — тост | PDF qweb (A4, ≤ 6 сторінок): KPI, EnPI, бюджет, ділянки, топ-обладнання, резерви; кнопка працює одним кліком | AN-02 |
| D-68 | KPI «Енергія в собівартості 6,8 %, база 7,3 %» | `Σ td_energy_cost МО / Σ вартість готової продукції МО` (`stock.move.value`); без оцінки складу — «—»; у демо-сиді вартість випуску задають **оцінкові проводки** `stock.move` (R-20 п. 5; склад не чіпається) | Odoo 19: вартість — `stock.move.value` |
| D-69 | Числа демо (186 400 кВт·год/30 дн., 4,85 кВт·год/м² тощо) | екран показує дані стенда й демо-сид (R-20); макет не відтворюється, окрім фікстур AC; EnPI демо прямує до 0,94 за рахунок сидованого зростання випуску (`EFF_GROWTH = 0,28`) | Немає реальних даних 2025 року |
| D-70 | Mobile: «Обхід ТП і ГРЩ · зміна 2», 6 пунктів | заголовок і пункти з шаблону й слота (дані); демо — 6 пунктів макета, 2 слоти (зміна 1 і 2) | Шаблони задає енергетик |
| D-71 | Підказка «норма до 85 °C · зараз 58 °C», «паливо ≥ 60 % · зараз 78 %» | значення «зараз» береться із сигналу або з `get_pult` (паливо ДГУ — KPI моста); немає джерела — статичний текст без «зараз» | Паливо ДГУ не `td.signal` |
| D-72 | «Завершити обхід» сіра, поки не відмічено все; тост «Позначте всі пункти обходу: залишилось N» | Збережено: кнопка візуально неактивна (`aria-disabled`), але натискається й показує тост; при повному виконанні — основна кнопка | Доступність |
| D-73 | Пункт без «норми» | додано: відмітка «поза нормою» з коментарем (необов'язково) і подія енергетики `kind='round'` при завершенні | MB-08 |
| D-74 | Вкладка «Обхід» завжди з активним обходом | немає відкритого обходу — «Зараз обходу немає. Наступний: {зміна} о {HH:MM}» і три останні обходи | Розклад за слотами |
| D-75 | «записано в журнал о 14:40» | час — серверний (Київ), з відповіді `action_finish` | |
| D-76 | Один користувач | виконавець блокується за першим, хто відмітив; інший бачить «Обхід виконує {ім'я}» (лише читання); головний енергетик може завершити чужий | Кілька чергових |
| D-77 | Немає статусу «не виконано» | після спливання слота обхід переходить у `missed`, створюється попередження (`td.energy.event`, `kind='round'`) | Журнал і контроль |
| D-78 | Вкладка «Обхід» без лічильника | збережено: бейджа немає (`badge` не задається) | Як у макеті |

---


# ЧАСТИНА I. `td_energy_analytics`

## 0. Дерево файлів

Власники: **A** — бекенд (моделі, розрахунки, дані, сид), **B** — фронтенд, подання, звіти (ARCH §6). Файли без літери — менеджер (каркас: порожні файли із заголовком; `__init__.py` і маніфест воркери не правлять).

```
odoo_addons/td_energy_analytics/
├── __manifest__.py                        (менеджер) розділ 1
├── __init__.py                            (менеджер) from . import models, wizard, report; from .hooks import post_init_hook, uninstall_hook
├── hooks.py                               A  post_init_hook: _load_areas, _assign_areas, _fill_alloc_product; uninstall_hook
├── migrations/19.0.1.0.0/post-migration.py A  ідемпотентний виклик тих самих функцій
├── models/
│   ├── __init__.py                        (менеджер)
│   ├── td_energy_area.py                  A  M-01 (+ `td.energy.node.area_id`, M-11)
│   ├── td_energy_driver.py                A  M-02, M-03 (+ `_cron_values`)
│   ├── product_template.py                A  M-10 (`td_plate_area_m2`)
│   ├── td_energy_daily.py                 A  M-08 (+ `_cron_daily`, `_cron_rotate`)
│   ├── td_energy_baseline.py              A  M-04, M-05
│   ├── td_energy_enpi.py                  A  M-06 (+ `_cron_enpi`)
│   ├── td_energy_budget.py                A  M-07
│   ├── td_energy_alloc.py                 A  M-09 (`td.energy.alloc` + `product_id`)
│   ├── td_energy_analytics.py             A  M-12 (AbstractModel: API-01…API-09)
│   ├── td_energy_dashboard.py             A  M-14 (`_inherit td.energy.dashboard`: гак `_td_report_action`)
│   └── res_config_settings.py             A  M-15
├── tools/
│   ├── periods.py                         A  R-01
│   ├── daily.py                           A  R-02 (SQL-побудова)
│   ├── drivers.py                         A  R-03
│   ├── ols.py                             A  R-04 (чистий Python, без numpy)
│   ├── enpi.py                            A  R-05
│   ├── budget.py                          A  R-06
│   ├── kpis.py                            A  R-07
│   ├── stack.py, heatmap.py               A  R-08, R-09
│   ├── cuts.py                            A  R-10…R-16
│   ├── seed.py                            A  R-20 (демо-сид)
│   └── fmt.py                             A  R-21, R-22
├── wizard/
│   ├── __init__.py                        (менеджер)
│   ├── td_energy_report_wizard.py         B  M-13 (Transient; `create_and_print`)
│   └── td_energy_daily_rebuild_wizard.py  B  M-16 → перерахунок фактів (Transient)
├── report/
│   ├── __init__.py                        (менеджер)
│   ├── report_data.py                     B  R-18, R-19 (AbstractModel-обробники `report.td_energy_analytics.*`)
│   ├── report_management.xml              B  `ir.actions.report` (V-12)
│   ├── report_management_templates.xml    B  qweb A4
│   ├── report_shift.xml                   B  `ir.actions.report` зміни (V-13)
│   └── report_shift_templates.xml         B
├── data/
│   ├── td_energy_area.csv                 A  8 ділянок
│   ├── area_map.csv                       A  49 вузлів → ділянка
│   ├── td_energy_driver_data.xml          A  драйвери `plate_m2`, `hdd` (noupdate=1)
│   ├── ir_config_parameter.xml            A  параметри (розд. 5.1)
│   ├── ir_cron.xml                        A  4 крони (розд. 6)
│   └── neutralize.sql                     A
├── security/
│   ├── td_energy_analytics_security.xml   A  record rules
│   ├── ir.model.access.csv                A  M-01…M-09, M-15
│   └── ir.model.access-report.csv         B  M-13, M-16 (суфікс після «-» — `odoo/tools/convert.py:722`)
├── static/src/analytics/                  B  UI-01…UI-10: analytics.js/.xml/.scss, kpis, stack, heatmap, enpi, cut, opps
├── static/tests/analytics.test.js         B  hoot
├── views/
│   ├── td_energy_analytics_views.xml      B  V-01 (client action), V-02…V-09 (форми/списки)
│   ├── td_energy_budget_views.xml         B  V-07, V-08
│   ├── product_template_views.xml         B  V-10
│   ├── res_config_settings_views.xml      B  V-14
│   └── menus.xml                          B  V-15
└── tests/
    ├── common.py                          A  TestW4Common (фікстури)
    ├── test_w4_area.py, test_w4_driver.py, test_w4_daily.py, test_w4_ols.py, test_w4_baseline.py,
    │   test_w4_enpi.py, test_w4_budget.py, test_w4_kpis.py, test_w4_stack_heatmap.py, test_w4_cuts.py,
    │   test_w4_seed.py, test_w4_security.py, test_w4_perf.py                           A
    ├── test_w4_report.py, test_w4_ui.py, test_w4_hoot.py                              B
    └── stand/test_w4_tk.py                                                           A  ТК-01…ТК-05 (pytest проти стенда)

odoo_addons/td_energy_mobile/                  C  (Частина II → [../td_energy_mobile/SPEC.md](../td_energy_mobile/SPEC.md))
```

Правки наявного коду `td_energy` (менеджер, не воркери; див. ARCH §6.0): `td.energy.dashboard._td_report_action()` + використання в `tools/dashboard.py` і `static/src/pult/pult.js` (розд. 2.M-14).

## 1. Маніфест

- `name`: «Аналітика енергетики»; `version`: `19.0.1.0.0`; `author`: `ToDo`; `license`: `LGPL-3`; `category`: `Manufacturing/Maintenance`.
- `depends`: `["td_energy", "td_energy_resources", "mrp_account"]` (транзитивно `mrp`, `stock_account`, `maintenance`).
- `external_dependencies`: немає Python-залежностей; для PDF потрібен системний `wkhtmltopdf` (штатний для Odoo; перевірка — AC-45).
- `data` (порядок): `security/td_energy_analytics_security.xml`, `security/ir.model.access.csv`, `security/ir.model.access-report.csv`, `data/td_energy_driver_data.xml`, `data/ir_config_parameter.xml`, `data/ir_cron.xml`, `views/td_energy_analytics_views.xml`, `views/td_energy_budget_views.xml`, `views/product_template_views.xml`, `views/res_config_settings_views.xml`, `report/report_management.xml`, `report/report_management_templates.xml`, `report/report_shift.xml`, `report/report_shift_templates.xml`, `views/menus.xml` (останнім). CSV ділянок і карти вузлів у `data` **не** входять — їх завантажує `hooks._load_areas(env)` (ідемпотентно, після встановлення вузлів).
- `assets`: `web.assets_backend`: `td_energy_analytics/static/src/analytics/**`; `web.assets_unit_tests`: `td_energy_analytics/static/tests/**`.
- `post_init_hook`: `hooks.post_init_hook` (`_load_areas`, `_assign_areas`, `_fill_alloc_product`); `uninstall_hook`: `hooks.uninstall_hook`.

## 2. Моделі

Загальне: `company_id` — у моделей із грошима й налаштуваннями (baseline, budget); фактичні таблиці (`daily`, `enpi`, `driver.value`) — без `company_id` (ізоляція через вузли/правила). `_log_access=False` — у `td.energy.daily`, `td.energy.enpi`, `td.energy.driver.value`.

### M-01 `td.energy.area` — ділянка (FR-01)

`_name = "td.energy.area"`, `_description = "Енергетика: ділянка"`, `_order = "sequence, id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char | size=16, req, idx, `UNIQUE(code)` |
| `name` | Char | size=64, req |
| `sequence` | Integer | default 10 |
| `color` | Char | size=7, req, «Колір» |
| `active` | Boolean | default True |
| `spec_driver_id` | Many2one `td.energy.driver` | «Драйвер питомого показника»; порожнє — питоме «—» (освітлення й офіс) |
| `node_ids` | One2many `td.energy.node` | `area_id`, readonly |
| `node_count` | Integer | compute |

Дані — розд. 5.2. `unlink` ділянки, у якої є вузли → `UserError("Ділянка використовується вузлами.")`.

### M-11 `td.energy.node` — розширення (`_inherit`)

`area_id` — Many2one `td.energy.area` (idx, ondelete=set null, «Ділянка»); заповнюється для вузлів `kind='consumer'` (карта 5.2); редагується `group_td_energy_manager`; форма вузла (`td_energy.view_td_energy_node_form`) отримує поле в групі «Облік» (V-09).

### M-02 `td.energy.driver` — драйвер нормалізації (FR-02)

`_name = "td.energy.driver"`, `_description = "Енергетика: драйвер"`, `_order = "sequence, id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char | size=16, req, idx, `UNIQUE(code)`; `plate_m2`, `hdd`, довільні для `manual` |
| `name` | Char | size=64, req |
| `source_kind` | Selection | `mrp_area`/«Площа плит з MRP», `weather_hdd`/«Градусо-доби опалення», `manual`/«Вручну»; req |
| `uom` | Char | size=16, «Одиниця» («м²», «°C·доба») |
| `base_temp_c` | Float | digits (4,1), default 18.0; для `weather_hdd` |
| `temp_signal_code` | Char | size=64, default `ventilation/totals/outdoor_c`; для `weather_hdd` |
| `sequence` | Integer | default 10 |
| `active` | Boolean | default True |
| `value_ids` | One2many `td.energy.driver.value` | |

Дані: `plate_m2` (`mrp_area`, «м²», `sequence 10`) і `hdd` (`weather_hdd`, «°C·доба», 18, `sequence 20`) — `noupdate=1`. Видалення драйвера, що використовується базою, заборонено (`ondelete=restrict` у рядках бази).

### M-03 `td.energy.driver.value` — добове значення драйвера (FR-02)

`_name = "td.energy.driver.value"`, `_log_access = False`, `_order = "day desc, driver_id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `driver_id` | Many2one `td.energy.driver` | req, idx, ondelete=cascade |
| `day` | Date | req, idx (Київ) |
| `value` | Float | digits (14,3), req |
| `quality` | Selection | `measured`, `estimated`, `manual`; req |
| `source_note` | Char | size=128 |

`UNIQUE(driver_id, day)`. Методи: `_cron_values()` (R-03), `get_series(driver_code, day_from, day_to)` → `{day: value}`.

### M-10 `product.template` — розширення (FR-03)

`td_plate_area_m2` — Float, digits (10,4), default 0.0, «Площа плити, м²/од.», constraint `≥ 0`. У формі продукту — група «Енергетика» (V-10). Для листових матеріалів td_machine_connect поля `td_sheet_length_mm × td_sheet_width_mm` **не** використовуються (Q-01).

### M-09 `td.energy.alloc` — розширення (FR-12)

`product_id` — Many2one `product.product`, `related="production_id.product_id"`, `store=True`, idx, readonly («Продукт»). Поле перераховується при встановленні для наявних рядків (SQL-пакетами 5 000, `post_init_hook` → `hooks._fill_alloc_product`).

### M-08 `td.energy.daily` — добові факти (FR-04)

`_name = "td.energy.daily"`, `_description = "Енергетика: добовий факт"`, `_log_access = False`, `_order = "day desc, scope, node_id"`, `_inherit = ["td.energy.day.mixin"]`.

| Поле | Тип | Параметри |
|---|---|---|
| `day` | Date | req, idx (Київ) |
| `scope` | Selection | `plant`/«Завод», `node`/«Вузол», `resource`/«Ресурс»; req, idx |
| `resource_id` | Many2one `td.energy.resource` | `plant` і `node` — `el`; `resource` — будь-який |
| `node_id` | Many2one `td.energy.node` | лише `scope='node'`, idx |
| `area_id` | Many2one `td.energy.area` | фіксується при побудові (історія не «переїжджає» при зміні розмітки), idx |
| `qty` | Float | digits (16,3): `plant` — споживання заводу (Σ фідерів, кВт·год); `node` — кВт·год вузла; `resource` — кількість (імпорт для `el`) |
| `cost` | Float | digits (14,2), `cost`: `plant` — вартість імпорту; `node` — вартість споживання; `resource` — вартість купівлі |
| `co2_kg` | Float | digits (14,2): `resource` — за R-07 W3 (`import`, `supply`); інакше 0 |
| `import_qty`, `export_qty` | Float | `plant`: імпорт і експорт (кВт·год) |
| `gen_pv_qty`, `gen_chp_qty` | Float | `plant`: генерація СЕС (`model='sun2000'`) і КГУ (`model='tedom'`) |
| `shift1_qty`, `shift2_qty`, `off_qty` | Float | `plant`: споживання (Σ фідерів) за змінами й поза змінами (W3 R-21) |
| `cost_s1`, `cost_s2`, `cost_off` | Float | digits (14,2), `cost`: `plant` — вартість споживання фідерів за змінами (`Σ feeder.cost`) |
| `direct_s1`, `direct_s2`, `direct_off` | Float | `plant`: споживання «прямих» верстатів за змінами (для розподілу площі плит) |
| `plate_s1`, `plate_s2`, `plate_off` | Float | `plant`: площа плит за змінами (R-14) |
| `minutes` | Float | `node`: Σ `td.energy.alloc.minutes` (`kind='direct'`) за добу |
| `idle_qty` | Float | `node`: Σ `alloc.kwh` (`kind='idle'`) |
| `quality` | Selection | `ok`, `partial` (частка `missing`-слотів > 10 %); default `ok` |
| `built_at` | Datetime | req |

Індекси: `(day, scope)`, `(day, area_id)`, `(node_id, day)`. `UNIQUE(day, scope, resource_id, node_id)` через часткові індекси в `init()` (NULL у `node_id` для `plant` і `resource`).
Методи: `_td_build_days(days)` (R-02, `api.model`), `action_rebuild(date_from, date_to)` (manager), `_cron_daily()`, `_cron_rotate()`.

### M-04 `td.energy.baseline` — модель бази ISO 50001 (FR-05)

`_name = "td.energy.baseline"`, `_description = "Енергетика: модель бази (EnPB)"`, `_inherit = ["mail.thread"]`, `_order = "state, period_to desc, id desc"`.

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | req, compute store: «{resource} · {scope} · {period_from:%Y-%m}…{period_to:%Y-%m}» |
| `resource_id` | Many2one `td.energy.resource` | req, default `resource_el`; допустимі `el`, `gas` |
| `scope` | Selection | `plant`/«Завод», `area`/«Ділянка»; default `plant` |
| `area_id` | Many2one `td.energy.area` | req при `scope='area'` |
| `period_from`, `period_to` | Date | req; `period_to − period_from + 1 ≥ baseline_min_days` (30) |
| `const_per_day` | Float | digits (14,3), «Постійна складова, од./добу» |
| `line_ids` | One2many `td.energy.baseline.line` | 1…3 рядки (обмеження) |
| `n_days` | Integer | readonly, кількість діб у підгонці |
| `r2`, `rmse` | Float | readonly |
| `method` | Selection | `ols`/«Регресія», `manual`/«Вручну»; default `ols` |
| `state` | Selection | `draft`/«Чернетка», `approved`/«Затверджено», `archived`/«В архіві»; default `draft`, tracking |
| `fitted_at`, `approved_at` | Datetime | readonly |
| `approved_by` | Many2one `res.users` | readonly |
| `warning` | Char | readonly: «Від'ємний коефіцієнт {driver}.» тощо |
| `company_id` | Many2one `res.company` | req, default `env.company` |
| `note` | Text | |

`M-05 td.energy.baseline.line`: `baseline_id` (req, cascade), `driver_id` (req, restrict), `coef` (Float digits (14,6), «Коефіцієнт, од. на одиницю драйвера»), `sequence`; `UNIQUE(baseline_id, driver_id)`.
Constraints: `_check_lines` (кількість рядків ≤ 3: `ValidationError("Не більше 3 драйверів.")`), `_check_scope` (`area` ⇒ `area_id`), `_check_resource` (`el`/`gas`: «Модель бази підтримується для електрики та газу.»), `_check_unique_approved`: на `(resource, scope, area, company)` не більше одного запису `approved`.
Методи: `action_fit()` (R-04; `group_td_energy_manager`; стани `draft`), `action_approve()` (`group_td_energy_chief`; R-04 п. 7), `action_archive()`, `action_to_draft()`, `expected(day_values)` (`const + Σ coef·value`), `_td_expected_series(day_from, day_to)`.

### M-06 `td.energy.enpi` — EnPI за добами (FR-06)

`_name = "td.energy.enpi"`, `_log_access = False`, `_order = "day desc, baseline_id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `baseline_id` | Many2one `td.energy.baseline` | req, idx, ondelete=cascade |
| `day` | Date | req, idx |
| `actual` | Float | digits (16,3), req |
| `expected` | Float | digits (16,3) — порожнє, якщо немає значення драйвера |
| `enpi` | Float | digits (8,4), compute store: `actual/expected` при `expected > 0`, інакше порожнє |
| `drivers` | Json | `{"plate_m2": 1286.0, …}` |
| `quality` | Selection | `ok`, `no_driver`, `partial` |

`UNIQUE(baseline_id, day)`. Методи: `_cron_enpi()`, `recompute(date_from, date_to, baseline=None)` (метод `manager`), `period_totals(baseline, day_from, day_to)` (R-05).

### M-07 `td.energy.budget` — бюджет енергії (FR-07)

`_name = "td.energy.budget"`, `_description = "Енергетика: бюджет"`, `_inherit = ["mail.thread"]`, `_order = "month desc, resource_id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `month` | Date | req, idx, перше число місяця; constraint `day == 1` |
| `resource_id` | Many2one `td.energy.resource` | порожнє = «Усі ресурси (вартість енергії)»: Σ ресурсів із `in_energy_cost` |
| `amount_uah` | Float | digits (14,2), req, `cost`, `> 0` |
| `amount_qty` | Float | digits (14,2), опційно, план в одиницях ресурсу |
| `state` | Selection | `draft`, `approved`; default `draft`, tracking |
| `approved_by`, `approved_at` | Many2one / Datetime | readonly |
| `company_id` | Many2one `res.company` | req, default `env.company` |
| `note` | Char | size=256 |

`UNIQUE(company_id, month, coalesce(resource_id, 0))` — через індекс в `init()`. `action_approve()` — `group_td_energy_chief`. Метод `get_status(month=None, resource_code=None)` (R-06).

### M-12 `td.energy.analytics` — API екрана (AbstractModel; FR-08…FR-15)

`_name = "td.energy.analytics"`, `_description = "Енергетика: дані аналітики"`. Доступ — `_td_check_access()`: `group_td_energy_user` або суперкористувач, інакше `AccessError("Немає доступу до Енергетики.")`; читання таблиць — через `sudo()`; ключі вартості без `group_td_energy_cost` **видаляються** з відповіді. Методи — API-01…API-09. Допоміжний метод `_td_stack_gap_pct(period)` — окремий метод моделі (джерело `meta.data_quality.stack_gap_pct`, R-10 п. 4).

### M-13 `td.energy.report.wizard` — звіти (Transient; FR-16, FR-17)

| Поле | Тип | Параметри |
|---|---|---|
| `kind` | Selection | `management`/«Для керівництва», `shift`/«За зміну»; req, default `management` |
| `period` | Selection | `w`, `m`, `q`, `y`; default `m` (`management`) |
| `shift_date` | Date | default сьогодні (Київ) (`shift`) |
| `shift_name` | Char | size=32; порожнє — поточна/остання завершена зміна (R-19) |

`create_and_print(kind, period=None, shift_name=None)` (`api.model`): створює запис, повертає `ir.actions.report` (`report_action(self, config=False)` — звіти не використовують `external_layout` компанії, тож майстер «Налаштувати макет документа» не відкривається); `action_print()` — те саме для відкритої форми. Права: `group_td_energy_user` (суми ₴ — за групою вартості, R-18).

### M-14 `td.energy.dashboard` — розширення (`_inherit`; FR-17)

Метод `_td_report_action()` (`api.model`) визначений у W4 і повертає `"td_energy_analytics.action_td_energy_shift_report"`. Щоб кнопка «Звіт за зміну» Пульта (W1 D-01) запрацювала, `td_energy` має викликати цей гак: `capabilities.report = bool(self._td_report_action())`, `meta.report_action = self._td_report_action()`, а `pult.js openReport()` — відкривати `meta.report_action` (правка менеджера в коді W1, ARCH §6.0; у W1 зараз `capabilities.report=False` і жорсткий xml-id `td_energy.action_td_energy_report`, `tools/dashboard.py:216`, `static/src/pult/pult.js:345`). Без правки модуль аналітики працює, кнопка Пульта лишається прихованою.

### M-15 `res.config.settings` — розширення

Поля `td_energy_analytics_*` із `config_parameter` (розд. 5.1); група «Аналітика» в блоці `td_energy` (V-14). Валідація: `r2_min ∈ [0, 1]`, `forecast_min_days ≤ forecast_weeks`, `daily_close_h ∈ [0, 12]`.

### M-16 `td.energy.daily.rebuild.wizard` — перерахунок фактів (Transient)

`date_from`, `date_to` (Date, req, діапазон ≤ 400 діб), `action_rebuild()` → `td.energy.daily._td_build_days` і `td.energy.enpi.recompute`; `group_td_energy_manager`.

## 3. Представлення й меню

### 3.1 Представлення V-01…V-16

| ID | XML-id (`td_energy_analytics.`) | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `action_td_energy_analytics` | `ir.actions.client`, `tag="td_energy_analytics.analytics"`, `name="Аналітика енергетики заводу"`, `context={"td_energy_period": "m"}` | UI-01 |
| V-02 | `view_td_energy_area_list` / `_form`, `action_td_energy_area` | `td.energy.area` | list: `sequence` (handle), `code`, `name`, `color`, `spec_driver_id`, `node_count`, `active`; form: поля + вкладка «Вузли» (`node_ids` list readonly) |
| V-03 | `view_td_energy_driver_list` / `_form`, `action_td_energy_driver` | `td.energy.driver` | поля, вкладка «Значення» (`value_ids` list, редагована для `manual`) |
| V-04 | `view_td_energy_driver_value_list` / `_pivot` / `_search`, `action_td_energy_driver_value` | `td.energy.driver.value` | list: `day`, `driver_id`, `value`, `quality`; `quality=manual` редагує менеджер |
| V-05 | `view_td_energy_baseline_list` / `_form`, `action_td_energy_baseline` | `td.energy.baseline` | статусбар `state`; кнопки: «Розрахувати модель» (`action_fit`, `state=draft`), «Затвердити» (`action_approve`, chief, `invisible="state != 'draft'"`), «В архів», «У чернетку»; поля: `resource_id`, `scope`, `area_id`, `period_from/to`, `method`; блок «Модель»: `const_per_day`, `line_ids` (editable list: `driver_id`, `coef`), `n_days`, `r2`, `rmse`, `warning`; чаттер |
| V-06 | `view_td_energy_enpi_list` / `_graph` / `_pivot` / `_search`, `action_td_energy_enpi` | `td.energy.enpi` | readonly; list: `day`, `baseline_id`, `actual`, `expected`, `enpi` (decoration: `> 1.05` danger, `< 0.95` success); graph: лінії `actual`/`expected` за тижнями; пункт — «Перерахувати» (`td.energy.daily.rebuild.wizard`) |
| V-07 | `view_td_energy_budget_list` / `_form`, `action_td_energy_budget` | `td.energy.budget` | list: `month`, `resource_id`, `amount_uah` (`cost`), `state`; form: статусбар, «Затвердити» (chief); без групи вартості суми приховані |
| V-08 | `view_td_energy_daily_list` / `_pivot` / `_graph` / `_search`, `action_td_energy_daily` | `td.energy.daily` | readonly; pivot: рядки `day`, стовпці `scope`; search: «Сьогодні», «Вчора», «7 днів» (`day.mixin`), `scope`, `area_id`; меню — `group_td_energy_manager` |
| V-09 | `view_td_energy_node_form_area` (успадковує `td_energy.view_td_energy_node_form`) | form | поле `area_id` у групі «Облік» |
| V-10 | `view_product_template_form_energy` (успадковує `product.product_template_only_form_view`) | form | група «Енергетика»: `td_plate_area_m2` |
| V-11 | `action_td_energy_daily_rebuild` | `ir.actions.act_window`, wizard M-16 | `target="new"` |
| V-12 | `report_td_energy_management` | `ir.actions.report` | `model="td.energy.report.wizard"`, `report_type="qweb-pdf"`, `report_name="td_energy_analytics.report_management_document"`, `print_report_name="'Енергетика_звіт_%s' % time.strftime('%Y-%m-%d')"` |
| V-13 | `report_td_energy_shift`, `action_td_energy_shift_report` | `ir.actions.report` + `ir.actions.server` | `report_name="td_energy_analytics.report_shift_document"`; серверна дія `action_td_energy_shift_report`: `code = "action = env['td.energy.report.wizard'].create_and_print('shift')"` (її запускає кнопка «Звіт за зміну» Пульта) |
| V-14 | `res_config_settings_view_form_td_energy_analytics` (успадковує `td_energy.res_config_settings_view_form_td_energy`) | form | група «Аналітика»: `td_energy_analytics_daily_close_h`, `…_catchup_days`, `…_forecast_weeks`, `…_forecast_min_days`, `…_r2_min`, `…_baseline_min_days`, `…_refresh_s`, `…_top_equipment`, `…_top_mo` |
| V-15 | `views/menus.xml` | `ir.ui.menu` | таблиця 3.3 |
| V-16 | `view_td_energy_alloc_search_product` (успадковує пошук `td.energy.alloc`) | search | групування «Продукт» (`product_id`) |

### 3.2 Клієнтські компоненти (OWL) UI-01…UI-10

Усе — `@odoo/owl`, `registry.category("actions").add("td_energy_analytics.analytics", Analytics)`; дані — `orm.call("td.energy.analytics", "get_dashboard", [], {period, dim, parts})`; шина не потрібна (оновлення раз на `refresh_s` = 300 с і при зміні періоду); тексти — українські; кожен інтерактивний вузол — `<button>` з `aria-label`; стан — не лише кольором.

| ID | Компонент | Вміст і поведінка |
|---|---|---|
| UI-01 | `Analytics` | Шапка: крихти «Енергетика / Аналітика», h1 «Аналітика енергетики заводу», підзаголовок `meta.subtitle`, група періоду `7 днів / 30 днів / квартал / рік` (`role="group"`, `aria-pressed`), кнопка «Звіт для керівництва» (`create_and_print('management', period)` → `action.doAction`). Стан: `period`, `dim`, `data`, `failed`; зміна періоду перезавантажує `kpis, stack, heatmap, cut, opps`; зміна зрізу — лише `cut`; `enpi`/`budget` вантажаться один раз |
| UI-02 | `AnKpis` | 7 карток (`flex: 1 1 180px` у збірці; у початковій редакції 190px): мітка, значення 24 px + одиниця, рядок Δ із тоном `good/bad/neutral`; порожнє значення — «—» |
| UI-03 | `AnStack` | SVG `viewBox 0 0 880 250`: сітка 4 лінії, підписи Y (0, ⅓, ⅔, max), стовпці за `bars[]` (стек за `areas[]`, кольори `areas[].color`), підписи X через `bars[].label`; легенда з `areas[]`; заголовок «Електроенергія за ділянками · {unit}» |
| UI-04 | `AnHeatmap` | сітка `28px + 24 колонки`, 7 рядків; комірка 18 px; колір за рівнем (`#f5f3f5 #e3d5df #c9b0c2 #9a7392 #5a3b52`); `title` «{день} {HH}:00 · {kW} кВт»; легенда «менше … більше · вихідні й ночі — базове навантаження {base_load_kw} кВт» |
| UI-05 | `AnEnpi` | SVG `viewBox 0 0 440 200`: сітка, вісь Y (3 мітки), дві лінії: факт (суцільна `#714B67`), очікування (пунктир `#9ca3af`), підписи «12 тижнів тому» / «цей тиждень»; легенда й рядок «EnPI {x} · економія {y} % до бази»; блок бюджету: «Бюджет енергії · {місяць}» із сумою, смугою факту й маркером `month_share_pct`, текст `budget.text` |
| UI-06 | `AnCut` | заголовок «Розріз · {dim_name}», вкладки (`role="tablist"`) Ділянки / Обладнання / Замовлення / Продукти / Зміни; таблиця: ім'я (кнопка деталізації → `action_open_cut`), «Енергія, кВт·год», «Вартість, ₴» (лише з `capabilities.cost`), «Частка» (смуга + %), питоме (заголовок `col_spec`), «До бази» (колір за знаком) |
| UI-07 | `AnOpps` | «Резерви економії» + «У плані: **{plan_sum} ₴/міс** з {all_sum} ₴/міс»; рядок: чекбокс (`action_plan_toggle`, з оптимістичним оновленням і відкатом при помилці), заголовок, текст, «{save} ₴/міс», кнопка дії за першою доступною (`runAdviceAction` з `@td_energy/common/advice`; `control` — лише за наявності обробника в `td_energy.advice_handlers`, інакше запасне «Відкрити»); без прав «Енергетик» чекбокс `disabled` |
| UI-08 | `useAnalytics` | хелпер завантаження частин, форматування (`fmtInt/fmtDec` з `@td_energy/common/format`), nice-ticks на клієнті не рахуються (приходять у `ticks`) |
| UI-09 | `td_energy_analytics.scss` | токени кольорів ділянок і теплової шкали; адаптив ≥ 360 px (картки й таблиця прокручуються по горизонталі); друкованих стилів не потрібно |
| UI-10 | `ReportButton` | окремий компонент кнопки звіту з індикатором очікування (звіт ≤ 15 с), блокування повторного кліку, `notify` про помилку (`wkhtmltopdf` недоступний — «Не вдалося сформувати PDF.») |

### 3.3 Меню (`views/menus.xml`)

| XML-id (`td_energy_analytics.`) | Назва | Батько | seq | Групи | Дія |
|---|---|---|---|---|---|
| `menu_td_energy_analytics` | Аналітика | `td_energy.menu_td_energy` | 12 | `td_energy.group_td_energy_user` | `action_td_energy_analytics` |
| `menu_td_energy_analytics_config` | Аналітика | `td_energy.menu_td_energy_config` | 60 | `…group_td_energy_manager` | — (розділ) |
| `menu_td_energy_area` | Ділянки | `…_config` (цей розділ) | 10 | manager | `action_td_energy_area` |
| `menu_td_energy_driver` | Драйвери | `…_config` | 20 | manager | `action_td_energy_driver` |
| `menu_td_energy_driver_value` | Значення драйверів | `…_config` | 25 | manager | `action_td_energy_driver_value` |
| `menu_td_energy_baseline` | Моделі бази (ISO 50001) | `…_config` | 30 | manager | `action_td_energy_baseline` |
| `menu_td_energy_enpi` | EnPI за добами | `…_config` | 40 | manager | `action_td_energy_enpi` |
| `menu_td_energy_budget` | Бюджет енергії | `…_config` | 50 | `…group_td_energy_cost` | `action_td_energy_budget` |
| `menu_td_energy_daily` | Добові факти | `…_config` | 60 | manager | `action_td_energy_daily` |
| `menu_td_energy_daily_rebuild` | Перерахувати добові факти | `…_config` | 70 | manager | `action_td_energy_daily_rebuild` |

## 4. Права

### 4.1 `security/ir.model.access.csv` (A) і `security/ir.model.access-report.csv` (B)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_energy_area_user,td.energy.area user,model_td_energy_area,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_area_manager,td.energy.area manager,model_td_energy_area,td_energy.group_td_energy_manager,1,1,1,0
access_td_energy_area_admin,td.energy.area admin,model_td_energy_area,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_driver_user,td.energy.driver user,model_td_energy_driver,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_driver_manager,td.energy.driver manager,model_td_energy_driver,td_energy.group_td_energy_manager,1,1,1,0
access_td_energy_driver_admin,td.energy.driver admin,model_td_energy_driver,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_driver_value_user,td.energy.driver.value user,model_td_energy_driver_value,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_driver_value_manager,td.energy.driver.value manager,model_td_energy_driver_value,td_energy.group_td_energy_manager,1,1,1,1
access_td_energy_daily_user,td.energy.daily user,model_td_energy_daily,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_daily_admin,td.energy.daily admin,model_td_energy_daily,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_baseline_user,td.energy.baseline user,model_td_energy_baseline,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_baseline_manager,td.energy.baseline manager,model_td_energy_baseline,td_energy.group_td_energy_manager,1,1,1,0
access_td_energy_baseline_chief,td.energy.baseline chief,model_td_energy_baseline,td_energy.group_td_energy_chief,1,1,1,1
access_td_energy_baseline_line_user,td.energy.baseline.line user,model_td_energy_baseline_line,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_baseline_line_manager,td.energy.baseline.line manager,model_td_energy_baseline_line,td_energy.group_td_energy_manager,1,1,1,1
access_td_energy_enpi_user,td.energy.enpi user,model_td_energy_enpi,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_enpi_admin,td.energy.enpi admin,model_td_energy_enpi,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_budget_cost,td.energy.budget cost,model_td_energy_budget,td_energy.group_td_energy_cost,1,0,0,0
access_td_energy_budget_manager,td.energy.budget manager,model_td_energy_budget,td_energy.group_td_energy_manager,1,1,1,0
access_td_energy_budget_chief,td.energy.budget chief,model_td_energy_budget,td_energy.group_td_energy_chief,1,1,1,1
```

`-report.csv`: `td.energy.report.wizard` і `td.energy.daily.rebuild.wizard`: перша — `group_td_energy_user` (1,1,1,1), друга — `group_td_energy_manager` (1,1,1,1) (Transient, права на створення). `td.energy.analytics` — AbstractModel без ACL (контроль у методах). Бюджет читають `group_td_energy_cost` і вище (без вартості бюджет безглуздий; у `user` без cost читання немає). Наявні права `td.energy.alloc` і `td.energy.node` достатні.

### 4.2 Групи

Нових груп немає. «Енергетик» = `group_td_energy_manager`: підгонка моделі, перерахунок, введення драйверів `manual`, редагування бюджету (чернетка). «Головний енергетик» = `group_td_energy_chief`: **затвердження** моделі бази й бюджету, видалення моделей/бюджетів. Адміністратор — усе.

### 4.3 Record rules

`td_energy_baseline_rule_company`, `td_energy_budget_rule_company` — домен `['|', ('company_id','=',False), ('company_id','in',company_ids)]`, глобальні. `td.energy.daily` ізолюється через вузли (`node_id.company_id`), для `plant`/`resource` — за `td.energy.node` компанії через `sudo()` в API (у таблиці немає `company_id`; мультикомпанія — Q-09).

### 4.4 Захист даних і дій

- Ключі вартості (`cost_uah`, `save_uah_month`, `plan_sum`, `all_sum`, KPI «Вартість», колонка «Вартість, ₴», суми бюджету) без `group_td_energy_cost` **видаляються** з відповідей API і PDF (AC-51); KPI «Вартість енергії» повністю виключається зі списку.
- Затвердження бази й бюджету — лише `chief`; підгонка й перерахунок — `manager`; читання — `user`.
- Звіти: PDF формується з правами користувача; суми ₴ — лише з групою вартості.
- Запису в пристрої немає.

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`) — `td.energy_analytics.*`

| Ключ | За замовчуванням | Призначення |
|---|---|---|
| `td.energy_analytics.daily_close_h` | `2` | до цієї місцевої години вчорашні доби перераховуються кроном |
| `td.energy_analytics.catchup_days` | `14` | глибина дозбору пропущених діб (факти, драйвери, EnPI) |
| `td.energy_analytics.forecast_weeks` | `8` | кількість тижнів для «типових діб» (прогноз бюджету) |
| `td.energy_analytics.forecast_min_days` | `3` | мінімум діб одного дня тижня для типових |
| `td.energy_analytics.r2_min` | `0.6` | мінімальний R² для затвердження моделі `ols` |
| `td.energy_analytics.baseline_min_days` | `30` | мінімальна довжина періоду бази |
| `td.energy_analytics.refresh_s` | `300` | автооновлення екрана |
| `td.energy_analytics.top_equipment` | `15` | рядків у зрізі «Обладнання» |
| `td.energy_analytics.top_mo` | `20` | рядків у зрізі «Замовлення» |

Використовуються наявні: `td.energy.read_enabled`, `td.energy.keep_interval_days` (ротація фактів, 400), `td.energy.shift_calendar_id` (зміни, W3 R-21), `td.energy_resources.weeks_per_month` (W3).

### 5.2 Ділянки й карта вузлів (`data/td_energy_area.csv`, `data/area_map.csv`; завантажує `hooks._load_areas(env)`)

`td_energy_area.csv` (`code,name,sequence,color,spec_driver`): `CUT,Розкрій,10,#5a3b52,plate_m2`; `EDGE,Крайка,20,#8a6383,plate_m2`; `DRILL,Присадка ЧПК,30,#b79ab0,plate_m2`; `FACADE,Фасади МДФ,40,#b45309,plate_m2`; `ASSY,Збирання й пакування,50,#f59e0b,plate_m2`; `AIR_DUST,Аспірація й повітря,60,#0369a1,plate_m2`; `HVAC,Вентиляція й опалення,70,#38bdf8,plate_m2`; `LIGHT_OFFICE,Освітлення й офіс,80,#9ca3af,` (без драйвера — питоме «—»). Кольори й назви — з `Analytics.dc.html` (`catDefs`).

`area_map.csv` (`node_code,area_code`; 49 вузлів `kind='consumer'`, `data/energy_nodes.csv` `td_energy`): `CUT` — `SAW-1, SAW-2, SAW-3, SLIDE-1, VSAW-1, NEST-1, GANTRY-1, SORT-1` (8); `EDGE` — `EDGE-1, EDGE-2, EDGE-3` (3); `DRILL` — `CNC-1, CNC-2, CNC-3, CNC-4, BORE-1, DOWEL-1` (6); `FACADE` — `SAND-1, AUTOSPRAY-1, UV-1, PRESS-1, SPRAY-1, DRY-1, GLUE-1` (7); `ASSY` — `HINGE-1, ASMLINE-1, ASM-1…ASM-6, PACK-1, PACK-2, BOX-1, PACKLINE-1` (12); `AIR_DUST` — `DUST-1, COMPRESSOR` (2); `HVAC` — `RV-ALL, AHU-1, BOILER, EF-ELEC, EF-CMP, EF-CHG` (6); `LIGHT_OFFICE` — `LP-1, LP-2, LP-3, OFFICE, CHARGING` (5). Разом 8 + 3 + 6 + 7 + 12 + 2 + 6 + 5 = 49. Віднесення — рішення автора (A-02): макет називає категорії, але не перелічує вузли; менеджер може скоригувати CSV.
`_assign_areas(env)`: `area_id` проставляється **лише** якщо порожній (правки користувача не перезаписуються); відсутній код вузла — пропуск із `_logger.warning`.

### 5.3 Дані драйверів (`data/td_energy_driver_data.xml`, `noupdate="1"`)

`driver_plate_m2` (`code='plate_m2'`, `source_kind='mrp_area'`, `uom='м²'`), `driver_hdd` (`code='hdd'`, `source_kind='weather_hdd'`, `uom='°C·доба'`, `base_temp_c=18`, `temp_signal_code='ventilation/totals/outdoor_c'`).

### 5.4 `post_init_hook` і міграція `19.0.1.0.0`

Кроки (ідемпотентні; міграція викликає ті самі функції):
1. `_load_areas(env)` (5.2): 8 ділянок;
2. `_assign_areas(env)`: 49 вузлів;
3. `_fill_alloc_product(env)`: `product_id` у наявних рядків `td.energy.alloc` (SQL, пакети 5 000);
4. драйвери (XML);
5. параметри (5.1), крон-записи (розд. 6).
Очікувано на демо-БД (`f3d_full2` після W1+W3): ділянок 8; вузлів із `area_id` 49; драйверів 2; `td.energy.daily` 0 до першого прогону крона/сиду; параметрів +9. Встановлення **не** створює модель бази й бюджет (їх затверджує людина; демо-сид R-20 — окремо).

### 5.5 `uninstall_hook`

Видаляє власні крон-записи й параметри. Таблиці модуля (ділянки, драйвери, факти, бази, EnPI, бюджети) видаляються штатно Odoo; електричні дані, `alloc` і вузли лишаються (поле `area_id` зникає разом із модулем). `neutralize.sql`: вимкнути 4 крони.

## 6. Крони й фонові процеси

Усі — `user_id=base.user_root`, `try/except` із `_logger.exception`; при `td.energy.read_enabled = False` не діють.

| XML-id | Назва | Інтервал | Метод | За один прогін | Ліміт |
|---|---|---|---|---|---|
| `cron_td_energy_daily` | Енергетика: добові факти | 15 хв | `td.energy.daily._cron_daily` | перерахунок сьогоднішньої доби; вчорашньої — поки місцева година < `daily_close_h` або немає рядка `plant`; дозбір до `catchup_days` діб без рядка `plant` (R-02) | ≤ 3 с на добу, ≤ 20 с сумарно |
| `cron_td_energy_drivers` | Енергетика: драйвери | 1 доба, `nextcall` 02:10 Київ | `td.energy.driver._cron_values` | значення драйверів за вчора й пропуски останніх `catchup_days` (R-03) | ≤ 10 с |
| `cron_td_energy_enpi` | Енергетика: EnPI | 1 доба, `nextcall` 02:30 Київ | `td.energy.enpi._cron_enpi` | EnPI за вчора й пропуски за кожною затвердженою базою (R-05) | ≤ 10 с |
| `cron_td_energy_analytics_rotate` | Енергетика: ротація аналітики | 1 доба, `nextcall` 03:20 Київ | `td.energy.daily._cron_rotate` | видалити `daily`, `enpi`, `driver.value` старші за `td.energy.keep_interval_days` | ≤ 30 с |

## 7. HTTP/JSON API

Нових HTTP-маршрутів немає: виклики — ORM-RPC від імені користувача. Якщо не вказано інше, методи — `@api.model`.

| ID | Сигнатура | Вхід → вихід | Помилки |
|---|---|---|---|
| API-01 | `td.energy.analytics.get_dashboard(period="m", dim="area", parts=None)` | `period ∈ {w, m, q, y}`, `dim ∈ {area, eq, mo, prod, shift}`, `parts` ⊂ `{"kpis","stack","heatmap","enpi","budget","cut","opps"}` або `None` → JSON «Аналітика» (нижче) | невідомий період/зріз → `UserError("Невідомий період: %s.")` / `UserError("Невідомий розріз: %s.")`; без групи → `AccessError` |
| API-02 | `td.energy.analytics.get_kpis(period)` | → `list[kpi]` (R-07) | як API-01 |
| API-03 | `td.energy.analytics.get_stack(period)` | → `stack` (R-08) | |
| API-04 | `td.energy.analytics.get_heatmap(period)` | → `heatmap` (R-09) | |
| API-05 | `td.energy.analytics.get_enpi()` | → `enpi`: 12 тижнів, EnPI, економія | |
| API-06 | `td.energy.analytics.get_budget(month=None)` | `month` — `YYYY-MM`, за замовчуванням поточний → `budget` або `null` | |
| API-07 | `td.energy.analytics.get_cut(dim, period)` | → `cut` (R-10…R-15) | |
| API-08 | `td.energy.analytics.action_open_cut(dim, key, period)` | → `ir.actions.act_window` (R-16) | `UserError("Невідомий ключ: %s.")` |
| API-09 | `td.energy.analytics.get_opportunities()` | → `{"items": [...], "plan_sum", "all_sum", "plan_count", "open_count"}` — обгортка над W3 API-02, API-06 (контракт C-01) | без модуля W3 не можна (жорстка залежність) |
| API-10 | `td.energy.baseline.action_fit()` / `action_approve()` / `action_archive()` (на записі) | → `True` | `UserError` (R-04), `AccessError` |
| API-11 | `td.energy.budget.action_approve()`, `get_status(month=None, resource_code=None)` | → `True` / `dict` (R-06) | `AccessError`, `UserError` |
| API-12 | `td.energy.report.wizard.create_and_print(kind, period=None, shift_name=None)` | → `ir.actions.report` (dict) | `AccessError`, `UserError("Невідомий вид звіту: %s.")` |
| API-13 | `td.energy.daily._td_build_days(days)` / `action_rebuild(date_from, date_to)` | → `{"days": n, "rows": n, "seconds": f}` | `AccessError`; діапазон > 400 → `UserError("Не більше 400 діб.")` |
| API-14 | `td.energy.analytics._td_seed_demo(days=400, seed=20261018, purge=False, with_mo=True, with_baseline=True, with_budget=True)` | → статистика R-20 (лише `env.is_superuser()` або `td_factory3d.group_td_admin`) | `AccessError("Генерувати демо-дані може лише адміністратор.")` |
| API-15 | `td.energy.driver.value.get_series(driver_code, day_from, day_to)` | → `{iso_day: value}` | |

### Відповідь API-01 (період `m`, зріз `area`; значення — приклад на основі макета, 17.10)

```json
{
  "meta": {"period": "m", "period_label": "30 днів", "date_from": "2026-09-18", "date_to": "2026-10-17", "now_local": "14:20",
           "subtitle": "Усі ресурси, усі ділянки, у зв'язці з виробництвом · база для порівняння — 2025 рік",
           "baseline": {"id": 3, "label": "2025", "const_per_day": 1820.0, "coefs": [{"driver": "plate_m2", "coef": 4.1}], "r2": 0.93, "state": "approved"},
           "capabilities": {"cost": true, "plan": true, "report": true}, "refresh_s": 300,
           "data_quality": {"days": 30, "partial_days": 0}},
  "kpis": [
    {"id": "el", "label": "Електроенергія", "value": 186400, "unit": "кВт·год", "delta_pct": -6.0, "note": "−6 % до бази", "tone": "good"},
    {"id": "gas", "label": "Газ", "value": 18400, "unit": "м³", "delta_pct": 2.0, "note": "+2 % до бази · похолодання", "tone": "bad"},
    {"id": "cost", "label": "Вартість енергії", "value": 1937880, "unit": "₴", "delta_pct": null, "note": "електрика 81 % · газ 19 %", "tone": "neutral"},
    {"id": "spec", "label": "Питома енергоємність", "value": 4.85, "unit": "кВт·год/м² плити", "delta_pct": -5.9, "note": "база 5,16 · −6 %", "tone": "good"},
    {"id": "cogs", "label": "Енергія в собівартості", "value": 6.8, "unit": "%", "delta_pct": null, "note": "база 7,3 %", "tone": "good"},
    {"id": "selfgen", "label": "Власна генерація", "value": 18, "unit": "%", "delta_pct": null, "note": "СЕС 41 000 кВт·год", "tone": "good"},
    {"id": "co2", "label": "Викиди CO₂", "value": 93, "unit": "т", "delta_pct": null, "note": "мережа 57 т · газ 36 т за період", "tone": "neutral"}],
  "stack": {"bar_unit": "day", "unit": "кВт·год за день", "y_max": 8100, "ticks": [2700, 5400, 8100],
            "areas": [{"code": "CUT", "name": "Розкрій", "color": "#5a3b52"}, "…8 ділянок…"],
            "bars": [{"key": "2026-09-18", "label": "18", "total": 7200, "values": {"CUT": 1008, "EDGE": 864, "…": 0}}, "…30 стовпців…"]},
  "heatmap": {"days": ["пн", "вт", "ср", "чт", "пт", "сб", "нд"], "cells": [[210.0, "…24 значення (кВт) або null…"], "…7 рядків…"],
              "max_ref": 700, "levels": 5, "base_load_kw": 210},
  "enpi": {"weeks": [{"key": "2026-10-17", "label": "цей тиждень", "expected_mwh": 49.64, "actual_mwh": 48.15}, "…12 тижнів, за зростанням дати…"],
           "y_min": 35, "y_max": 50, "enpi": 0.94, "saving_pct": 6.0, "saving_kwh": 11260.0, "saving_uah": 94584},
  "budget": {"month": "2026-10", "month_label": "жовтень", "plan_uah": 1950000, "fact_uah": 1096000, "fact_pct": 56, "month_share_pct": 55,
             "forecast_uah": 1912000, "delta_pct": -2,
             "text": "Факт на 17.10 — 1 096 000 ₴ (56 % при 55 % місяця) · прогноз 1 912 000 ₴, на 2 % нижче бюджету"},
  "cut": {"dim": "area", "dim_name": "Ділянки", "col_name": "Ділянка", "col_spec": "кВт·год/м²",
          "rows": [{"key": "CUT", "name": "Розкрій", "kwh": 26100, "cost_uah": 219240, "share_pct": 14, "bar": 0.70, "spec": 0.68, "spec_text": "0,68", "delta_pct": -4}, "…"]},
  "opps": {"items": [{"id": 31, "code": "vent_offshift", "resource": "el", "title": "Вентиляція працює поза змінами", "text": "…", "save_uah_month": 15500, "in_plan": true, "actions": [{"code": "night_mode", "label": "Сценарій BMS", "kind": "control", "class": null, "params": {"intent": "vent_night_mode"}, "enabled": false}, {"code": "open", "label": "Відкрити", "kind": "link", "class": null, "params": {"xmlid": "td_energy_resources.action_td_energy_opportunity", "res_id": 31}, "enabled": true}]}],
           "plan_sum": 33000, "all_sum": 57500, "plan_count": 3, "open_count": 8}
}
```

Правила форми: частини відсутні, якщо не запрошені (`parts`); частина, що впала з помилкою, повертає `{"error": "…"}` (решта не ламаються); `kpis[].delta_pct`/`note` — `null`/«—» без бази; `budget = null` без затвердженого бюджету на місяць; ключі ₴ — лише з групою вартості (інакше відсутні; KPI `cost` виключається); `cut.rows[].bar` — відносна довжина смуги (`kwh / max kwh`); `enpi.weeks` — 12 ковзних тижнів по 7 діб, що закінчуються сьогодні; `heatmap.cells[i][h]` — кВт; розмір відповіді ≤ 60 КБ (період `y`).

## 8. Сервісна частина

Відсутня (емулятор і збирач не змінюються). Серверна вимога: системний `wkhtmltopdf` (у складі оточення Odoo) для PDF; без нього AC-45 виконується на стенді, юніт-перевірка звіту йде за HTML (`_render_qweb_html`).

## 9. Алгоритми й правила

Загальні позначення: `today` — київська дата зараз; `daily` — таблиця `td.energy.daily`; «споживання заводу» = `Σ kwh` рядків `td.energy.interval` із `role='feeder'`; «імпорт» = `Σ kwh` вводів (`role='incomer'`); ціна й CO₂ — за W3 (`td.energy.usage`, R-07 W3). Округлення й формати — R-21.

### R-01 Періоди й кошики (FR-08)

| Період | Вікно (включно) | Кошики | Підписи |
|---|---|---|---|
| `w` | `[today−6, today]` | 7 днів | скорочення дня тижня фактичної дати: пн, вт, ср, чт, пт, сб, нд |
| `m` | `[today−29, today]` | 30 днів | номер дня; показується кожна 5-та корзина (індекси 0, 5, 10…), решта — `""` |
| `q` | `[today−90, today]` (91 день) | 13 ковзних тижнів `[today−6−7·i, today−7·i]`, `i = 12…0` (за зростанням) | «т1»…«т13»; показується кожна 2-га (індекси 0, 2, 4…) |
| `y` | `[1-ше число місяця (today) − 11 міс., today]` | 12 календарних місяців, останній неповний | січ, лют, бер, кві, тра, чер, лип, сер, вер, жов, лис, гру |

Одиниця осі: `w`, `m` — «кВт·год за день»; `q` — «кВт·год за тиждень»; `y` — «кВт·год за місяць». Приклад (`today = 2026-10-17`): `m` = 2026-09-18…2026-10-17; `q` починається 2026-07-19; `y` — 2025-11-01…2026-10-17.

### R-02 Добові факти `td.energy.daily` (FR-04)

`_td_build_days(days)` для кожної київської доби `D` (`[d0, d1)` UTC, `dates.local_day_bounds`):
1. **Рядок `plant`** (`resource = el`): один SQL за `td_energy_interval` за `[d0, d1)` і ролями `incomer`, `feeder`, `generation`:
   `qty = Σ kwh (feeder)`; `import_qty = Σ kwh (incomer)`; `export_qty = Σ kwh_export (incomer)`; `cost = Σ cost (incomer)`; `gen_pv_qty = Σ kwh` лічильників `generation` з `model='sun2000'`; `gen_chp_qty` — `model='tedom'`; `quality='partial'`, якщо частка слотів фідерів із `quality='missing'` > 10 %.
2. **Зміни (R-21 W3):** за кожним рядком фідерів за добу — зміна за **початком** слота (`shift_of(local(ts_start))`); зміни доби впорядковані за початком: перша → `shift1`, друга й далі → `shift2`, поза змінами → `off`. Заповнюються `shift1_qty/shift2_qty/off_qty` і `cost_s1/cost_s2/cost_off` (`Σ feeder.cost`); аналогічно `direct_s1/direct_s2/direct_off` — за рядками `role='consumer'` вузлів із `alloc_role='direct'`.
3. **Площа плит за змінами:** `plate = значення драйвера plate_m2 за D` (0, якщо рядка немає); `plate_sN = plate × direct_sN / Σ direct`; при `Σ direct = 0` усе відноситься до `plate_s1` (A-12).
4. **Рядки `node`** (`resource = el`): `qty = Σ kwh`, `cost = Σ cost` за `role='consumer'` кожного вузла; `area_id` = поточний `node.area_id` **на момент побудови**; `minutes = Σ alloc.minutes` (`kind='direct'`) та `idle_qty = Σ alloc.kwh` (`kind='idle'`) за `td.energy.alloc` за `D` і вузлом.
5. **Рядки `resource`:** з `td.energy.usage` (W3) за `D`: для кожного активного ресурсу — `qty`, `cost`, `co2_kg` за потоками `import` (`el`) і `supply` (решта); похідні (`heat`, `air`) входять зі своєю вартістю (до «вартості енергії» не сумуються — прапорець `in_energy_cost`).
6. Запис: `DELETE … WHERE day = D` + `INSERT` в одній транзакції; `built_at = now`. Ідемпотентно.
**Крон `_cron_daily` (15 хв):** завжди перераховує сьогоднішню добу; вчорашню — доки місцева година `< daily_close_h` або в неї немає рядка `plant`; донавантаження — доби останніх `catchup_days` без рядка `plant`. **Ротація** — `td.energy.keep_interval_days`.
**Контрольна тотожність:** `plant.qty = Σ feeder kwh` за добу (допуск 0,001); `Σ resource(el).qty = import_qty`.

### R-03 Драйвери (FR-02)

`_cron_values` (02:10 Київ): доба = вчора + пропуски останніх `catchup_days`; для кожного активного драйвера:
- **`mrp_area`** (`plate_m2`): якщо в жодного продукту немає `td_plate_area_m2 > 0` — рядок не створюється. Інакше `value = Σ (stock_move.quantity × product_template.td_plate_area_m2)` за рухами `stock.move` з `production_id IS NOT NULL` (готова продукція МО), `state='done'`, `date ∈ [d0, d1)` (кількість — в ОВ продукту; обмеження за `Date` — за київською добою); `quality='estimated'`, `source_note='MRP'`; нульове значення допустиме.
- **`weather_hdd`** (`hdd`): `T_mean` = середнє `v_avg` годинних агрегатів `td.reading.hour` сигналу `temp_signal_code` за добу (потрібно ≥ 18 годин); інакше — середнє сирих `td.reading` (≥ 50 показань); інакше рядок не створюється. `hdd = max(0, base_temp_c − T_mean)`, `quality='measured'`.
- **`manual`** — значення вводить `group_td_energy_manager`.
Приклад: 3 рухи (10 × 3,1 + 5 × 8,4 + 20 × 1,0) → `plate_m2 = 31 + 42 + 20 = 93,0`; `T_mean = 7,0`, база 18 → `hdd = 11,0`.

### R-04 Модель бази: регресія та затвердження (FR-05)

`action_fit()` (стан `draft`, `method='ols'`):
1. **Ряд `y`:** за добами періоду — `el/plant`: `daily.plant.qty`; `el/area`: `Σ daily.node.qty` ділянки; `gas/plant`: `daily.resource(gas).qty`. Беруться доби з рядком `daily` (`quality='ok'`) і значеннями **всіх** драйверів моделі (`td.energy.driver.value`).
2. **Розмір вибірки:** `n_min = max(baseline_min_days, 10·(k+1))`, де `k` — кількість драйверів; `n < n_min` → `UserError("Замало даних для моделі бази: потрібно ≥ %s діб, є %s.")`.
3. **Розв'язання:** нормальні рівняння `(XᵀX)β = Xᵀy`, `X = [1, x₁…x_k]`, метод Гаусса з частковим вибором головного елемента (чистий Python, без numpy; `tools/ols.py`); провідний елемент за модулем `< 1e-9·scale` → `UserError("Драйвери лінійно залежні або сталі.")`; `k = 0` → `β₀ = mean(y)`.
4. **Метрики:** `ŷ = Xβ`; `SSE = Σ(y−ŷ)²`; `SST = Σ(y−ȳ)²`; `r2 = 1 − SSE/SST` (`SST = 0` → 0); `rmse = √(SSE/n)`; `const_per_day = β₀`; `line_ids` замінюються на `(driver, β_i)`; `n_days`, `fitted_at`.
5. **Попередження (`warning`):** будь-який `β_i < 0` або `β₀ < 0` — «Від'ємний коефіцієнт {…}.»; `r2 < r2_min` — «R² {r2} нижче порогу {r2_min}.»
6. `expected(day) = const_per_day + Σ coef_i · x_i(day)`.
7. **Затвердження** (`action_approve`, `group_td_energy_chief`, стан `draft`): при `method='ols'` — `r2 ≥ r2_min` і всі коефіцієнти `≥ 0`, інакше `UserError("Модель не може бути затверджена: %s.")`; попередня `approved` тієї самої пари `(resource, scope, area, company)` → `archived`; `approved_by/at`; потім `td.energy.enpi.recompute(period_from, yesterday)`.
Приклад: 30 діб, `x_i = 800 + 20·i`, `y_i = 1820 + 4,1·x_i` → `β₀ = 1820,000 ± 0,001`, `β₁ = 4,100 ± 1e-6`, `r2 = 1`, `rmse = 0`; два драйвери: `y = 1500 + 4,0·plate + 35·hdd` відновлюється; драйвери `plate` і `2·plate` → `UserError`.

### R-05 EnPI (FR-06)

1. `_cron_enpi` (02:30 Київ): для кожної затвердженої бази — вчора та пропуски останніх `catchup_days`: `actual` — за тим самим визначенням, що й `y` у R-04 п. 1; `drivers` — `{code: value}` з `driver.value`; якщо немає значення хоча б одного драйвера — рядок з `expected = NULL`, `quality='no_driver'`; інакше `expected = baseline.expected(drivers)`, `enpi = actual/expected`; `quality='partial'` при `daily.quality='partial'`.
2. **Підсумки періоду** `period_totals(baseline, d_from, d_to)`: за рядками з `expected` і `quality != 'no_driver'`: `Σa`, `Σe`, `enpi = Σa/Σe`, `saving_pct = (1 − enpi)·100`, `saving_qty = Σe − Σa`, `coverage = n/(кількість діб вікна)`; `coverage < 0,5` → `enpi = null`. Вартість економії (`cost`): `saving_qty × avg_price`, де `avg_price` = `Σ plant.cost / Σ plant.import_qty` за період (електроенергія) або `Σ cost/Σ qty` ресурсу `gas`.
3. **Тижневий ряд** (`enpi.weeks`): 12 ковзних тижнів (як `q` у R-01, 12 кошиків), для кожного `expected_mwh = Σe/1000`, `actual_mwh = Σa/1000`; вісь `y_min = floor5(0,95·min)`, `y_max = ceil5(1,05·max)` (кратно 5 МВт·год); мітки `label` — «12 тижнів тому» (перша) і «цей тиждень» (остання), решта `""`. Тижневий EnPI-блок — за затвердженою базою `el/plant`; немає її — `enpi = null`. **Збірка (`_td_enpi`):** неповна поточна доба в точки не входить — беруться доби до вчора, а останній тиждень (у ньому ≤ 6 повних діб, `n`) нормується до 7 діб (`Σe·7/n`, `Σa·7/n`; сам `enpi` від цього не залежить), щоб «цей тиждень» не мав хибного провалу на графіку.
Приклад: 7 діб по 1 286 м² плит: `expected = 7·1820 + 4,1·9000 = 49 640 кВт·год = 49,64 МВт·год`; `actual = 48 150` → `enpi = 0,9700`, `saving_pct = 3,0`, `saving_qty = 1 490`.

### R-06 Бюджет і прогноз (FR-07)

`get_status(month, resource_code)` — лише за **затвердженим** бюджетом (`state='approved'`), інакше `null`.
1. `fact = Σ daily.resource.cost` за `[1-е число, today]` за ресурсами з `in_energy_cost` (або за одним ресурсом при бюджеті на ресурс); `fact_pct = round(fact/plan·100)`; `month_share = round(день_місяця / кількість_днів_місяця · 100)` (доби рахуються цілком; D-59).
2. **Типові доби:** `typical[w]`, `w = 0…6` — середнє `daily.resource.cost` (ті самі ресурси) за останні `forecast_weeks` тижнів до `today` (без сьогоднішньої доби) для дня тижня `w`; якщо зразків `< forecast_min_days` — середнє всіх діб цього вікна; немає даних — `forecast = null`.
3. `forecast = Σ_{d < today} actual(d) + max(actual(today), typical[wd(today)]) + Σ_{d > today в місяці} typical[wd(d)]`; `delta_pct = round((forecast − plan)/plan·100)`.
4. `text`: «Факт на {ДД.ММ} — {fact} ₴ ({fact_pct} % при {month_share} % місяця) · прогноз {forecast} ₴, на {|delta|} % {нижче|вище} бюджету» (при `delta = 0` — «… прогноз {forecast} ₴, відповідає бюджету»).
Приклад (`today = 2026-10-17`, субота): `факт 1–16 = 1 036 000`, сьогодні `60 000`; типові доби: пн–пт 62 000, сб 60 000, нд 38 000; залишок місяця: 5 + 5 будніх, 2 суботи (24, 31 жовт.), 2 неділі (18, 25 жовт.) → `forecast = 1 036 000 + max(60 000, 60 000) + 2·38 000 + 10·62 000 + 2·60 000 = 1 912 000`; `fact = 1 096 000`, `plan = 1 950 000` → `fact_pct = 56`, `month_share = 17/31 = 55`, `delta = −1,95 → −2` ⇒ «Факт на 17.10 — 1 096 000 ₴ (56 % при 55 % місяця) · прогноз 1 912 000 ₴, на 2 % нижче бюджету».

### R-07 KPI (FR-09)

Вікно — R-01; дані — `daily`; «база» — затверджена модель `el/plant` (і `gas/plant` для газу). Без бази `delta_pct = null`, `note` «База не задана».

| id | value | delta_pct / note | tone |
|---|---|---|---|
| `el` «Електроенергія» | `Σ plant.qty` (кВт·год) | `(Σa/Σe − 1)·100` за `enpi`-рядками вікна → note «{±N} % до бази» (знак U+2212 для мінуса) | `good` при `delta ≤ −1`, `bad` при `delta ≥ +1`, інакше `neutral` |
| `gas` «Газ» | `Σ resource(gas).qty` (м³) | той самий розрахунок за базою `gas/plant` (драйвер HDD); до note додається « · похолодання», якщо `avg_hdd(вікно) > 1,10·avg_hdd(вікно бази)`, і « · тепліше», якщо `< 0,90·…` | як `el` |
| `cost` «Вартість енергії» (`cost`-група) | `Σ resource.cost` ресурсів з `in_energy_cost` | note «{name₁} {share₁} % · {name₂} {share₂} %», `name` у нижньому регістрі; `delta_pct = null` | `neutral` |
| `spec` «Питома енергоємність» | `Σ plant.qty / Σ plate_m2` за доби вікна з `plate > 0` (кВт·год/м²) | `base = Σ y/Σ plate` за період бази; `delta = (value/base − 1)·100`; note «база {base} · {±N} %» | `good` при `delta < 0` |
| `cogs` «Енергія в собівартості» | `100·Σ td_energy_cost / Σ value` за МО з `date_finished` у вікні та `state='done'` (`value` — `stock.move.value` готових рухів МО) | note «база {base} %» — те саме відношення в періоді бази; знаменник 0 — `value = null` | `good` при `value ≤ base` |
| `selfgen` «Власна генерація» | `100·(Σ(gen_pv_qty+gen_chp_qty) − Σ export_qty)/Σ plant.qty` | note «СЕС {Σ gen_pv_qty} кВт·год» | `good` |
| `co2` «Викиди CO₂» | `Σ resource.co2_kg / 1000` (т): електроенергія — за імпортом | note «мережа {el} т · газ {gas} т за період» | `neutral` |

Приклад (30 діб, фікстура): `Σa = 186 400`, `Σe = 198 298` → `delta = −6,0`; газ `18 400` при очікуванні `18 039` → `+2,0`, `avg_hdd` вікна 9,1 проти 7,9 бази (+15 %) → «похолодання»; `cost = 1 569 600 + 368 280 = 1 937 880` (81 % / 19 %); `spec = 186 400/38 400 = 4,854` (4,85), база `5,16` → `−5,9 %` («база 5,16 · −6 %»); `cogs = 68 000/1 000 000 = 6,8 %`; `selfgen = (41 000 − 7 440)/186 400 = 18,0 %`; `co2`: імпорт `152 840 × 0,37 = 56 551 кг` (57 т), газ `18 400 × 1,96 = 36 064 кг` (36 т), `value = 93`.

### R-08 Стовпці за ділянками (FR-10)

1. Кошики R-01; для кожного — `Σ daily.node.qty` за `area_id` (`area.code`); вузли без ділянки сумуються в сірий сегмент `NONE` («Без ділянки», `#d1d5db`), якщо сума > 0.
2. `bars[].total = Σ values`; порядок серій — `area.sequence`.
3. `y_max = round(1,08 · max(total))`, `ticks = [round(y_max/3), round(2·y_max/3), y_max]` (як у макеті: `max · 1,08`). Для `w`, `m` — на добу, `q` — на тиждень, `y` — на місяць.
4. Інформативно: `meta.data_quality.stack_gap_pct = (Σ plant.qty − Σ усіх сегментів)/Σ plant.qty · 100` (на демо ≤ 3 %). **Збірка:** розрив рахує окремий метод `td.energy.analytics._td_stack_gap_pct(period)` (на `tools/stack.gap_pct`), а не `get_stack`: рядок `stack` лишається чистою серією для графіка.
Приклад: максимум стовпця 7 500 → `y_max = 8 100`, `ticks = [2 700, 5 400, 8 100]`.

### R-09 Теплокарта «година × день тижня» (FR-11)

1. SQL за `td_energy_interval`: `role='feeder'`, `day ∈ вікно`, `quality != 'missing'`; групування `EXTRACT(ISODOW FROM day)` (1 = пн) і `hour_local`: `Σ kwh`, `count(DISTINCT day)`.
2. Комірка: `kW = Σ kwh / count(DISTINCT day)` (кВт·год за одну годину = середній кВт); немає даних — `null`.
3. `max_ref = ceil50(max(cell))`, `levels = 5`; клієнтський рівень `lvl = min(4, floor(v / max_ref · 5))`; `base_load_kw = round5(min(cell))`.
Приклад: чотири понеділки з кВт·год за 12:00 = 400, 410, 390, 400 → комірка `[пн][12] = 400`.

### R-10 Зрізи: загальні правила (FR-12, FR-13)

- Рядок: `{key, name, kwh, cost_uah (cost), share_pct, bar, spec, spec_text, delta_pct}`; `share_pct = round(kwh/Σkwh·100)` (Σ — за рядками зрізу, включно з «Інші»); `bar = kwh / max(kwh)`; сортування за `kwh` спад.
- Питомий показник — ділення; знаменник `0` або `null` → `spec = null`, `spec_text = "—"`; винятків немає.
- «Інші» — сумарний рядок за межами ліміту (`top_equipment`, `top_mo`), без питомого.
- Заголовки: `area` — «Ділянка» / «кВт·год/м²»; `eq` — «Обладнання» / «кВт·год/мотогод»; `mo` — «Замовлення» / «кВт·год/шт» (якщо всі МО в одній ОВ — «кВт·год/{ОВ}»); `prod` — «Продукт» / «кВт·год/од.»; `shift` — «Зміна» / «кВт·год/м²».

### R-11 Зріз «Ділянки»

`kwh = Σ daily.node.qty`, `cost = Σ daily.node.cost` за `area_id` за вікно; `spec = kwh / Σ plate_m2(вікно)` для ділянок з `spec_driver_id` (`plate_m2`), інакше `null`. Рядок «Без ділянки» — за ненульової суми. Приклад: `CUT: 26 100 / 38 400 = 0,68`; `LIGHT_OFFICE` — «—».

### R-12 Зріз «Обладнання»

За вузлами `kind='consumer'`: `kwh`, `cost` — з `daily.node`; `hours = Σ minutes / 60`; `spec = kwh / hours` при `hours ≥ 1`, інакше `null` (загальні вузли без нарядів: `RV-ALL`, `DUST-1`, `COMPRESSOR`). Ім'я — «{code} · {name}»; ліміт `top_equipment` + «Інші». Приклад: `SAW-3: 7 400 кВт·год`, `15 300 хв = 255 год` → `7 400/255 = 29,0 кВт·год/мотогод`.

### R-13 Зрізи «Замовлення» і «Продукти»

З `td.energy.alloc` за вікно (`day`) з `production_id`: **МО** — `kwh = Σ kwh`, `cost = Σ cost`, `qty = production.qty_produced or product_qty`, `spec = kwh/qty`; ім'я «{mo.name} · {product} × {qty:g}»; ліміт `top_mo`. **Продукти** — групування за `alloc.product_id`: `kwh`, `cost`; `spec = Σ kwh / Σ qty` **різних** МО продукту у вікні (МО, що перетинають межу вікна, враховуються повністю — припущення A-14). Приклад: `WH/MO/00391`, `kwh 2 470`, `qty 60` → `41,17`.

### R-14 Зріз «Зміни»

Три рядки з `daily.plant`: «{Зміна 1} · {HH:MM}–{HH:MM}», «{Зміна 2} · …», «Ночі й вихідні · без виробництва» (назви й час — R-21 W3). `kwh = Σ shift1_qty / shift2_qty / off_qty`, `cost = Σ cost_s1 / cost_s2 / cost_off`; `spec` змін — `kwh / Σ plate_s1 (plate_s2)`; для «Ночі й вихідні» `spec_text = "база {avg_kw} кВт"`, `avg_kw = off_qty / off_hours` (`off_hours` — кількість годин вікна поза змінами за календарем).

### R-15 «До бази» (FR-24, D-60)

Вікно бази `Wb = [baseline.period_from, baseline.period_to]` (затверджена `el/plant`); для рядка з ключем `K`:
- `area`, `shift` (зміни 1 і 2): `spec_base` — те саме відношення (`kwh/Σ plate`) за `Wb` для того самого ключа;
- `eq`: `kwh/мотогод` за `Wb`; `prod`: `Σ kwh/Σ qty` продукту за `Wb`; `mo`: порівняння зі `spec` **продукту** МО за `Wb`;
- «Ночі й вихідні»: `avg_kw` за `Wb`.
`delta_pct = (spec_now/spec_base − 1)·100`, округлення до цілого; немає бази або даних у `Wb` → `null` («—»). Агрегати вікна бази рахуються один раз на запит.
Приклад: `CUT`: `spec_now = 0,68`, `spec_base = 0,7083` → `−4 %`.

### R-16 Деталізація (FR-14)

`action_open_cut(dim, key, period)` → `ir.actions.act_window` (список + зведена + графік) з доменом за вікном `[date_from, date_to]` (поле `day`):
- `area` — `td.energy.interval`, `[('role','=','consumer'), ('node_id.area_id.code','=',key)]`, групування `day`/`node_id`;
- `eq` — `td.energy.interval`, `[('role','=','consumer'), ('node_id.code','=',key)]`;
- `mo` — `td.energy.alloc`, `[('production_id.name','=',key)]` (ключ зрізу — ім'я МО);
- `prod` — `td.energy.alloc`, `[('product_id','=',int(key))]`;
- `shift` — `td.energy.interval`, `[('role','=','feeder')]`, групування `hour_local` (інтервали періоду, не відфільтровані за зміною — D-65).
`key = "OTHER"` («Інші») — `UserError("Невідомий ключ: OTHER.")`. Поля вартості приховані `groups` моделі.

### R-17 Резерви та чек-лист «у плані» (FR-15)

`get_opportunities()` = `td.energy.opportunity.get_list(None, ("open",))` (≤ 20, W3 API-02) + `get_plan_summary()` (W3 API-06). Екран показує «У плані: {plan_sum} ₴/міс з {all_sum} ₴/міс» (`plan_sum` — за `in_plan`); зміна прапорця — `action_plan_toggle` W3 (право «Енергетик»); дії — за контрактом C-32 (W1/W3); W4 власного стану не зберігає. Без групи вартості суми та `save_uah_month` відсутні, рядки показуються без ₴.

### R-18 Звіт «Звіт для керівництва» (FR-16)

`report.td_energy_analytics.report_management_document._get_report_values(docids, data)`: з запису майстра бере `period` і викликає `get_dashboard(period, "area", parts=[kpis, stack, enpi, budget, cut, opps])` та `get_cut("eq", period)` (топ-5).
Структура (A4, портрет, поля 12 мм, ≤ 6 сторінок, без зовнішніх ресурсів):
1. Заголовок: «Звіт для керівництва · Енергетика», компанія, період (дати), дата й час формування (Київ), автор (користувач).
2. «Підсумки періоду» — таблиця 7 KPI (значення, одиниця, Δ/примітка).
3. «EnPI проти бази (ISO 50001)» — SVG-лінії 12 тижнів (факт/очікування), рядок «EnPI {x} · економія {y} %», параметри моделі (константа, коефіцієнти, R², період бази).
4. «Бюджет енергії · {місяць}» — план/факт/прогноз/відсоток (лише з групою вартості).
5. «Енергія за ділянками» — таблиця: ділянка, кВт·год, ₴ (cost), частка, кВт·год/м², до бази.
6. «Найбільші споживачі» — топ-5 обладнання: кВт·год, ₴, кВт·год/мотогод.
7. «Резерви економії» — таблиця «У плані» / «Інші» із сумою ₴/міс (cost) і діями текстом.
8. Примітки: кількість діб з якістю `partial`, модель бази не затверджена тощо.
Колонки/блоки з ₴ — лише за `group_td_energy_cost`. Час формування ≤ 15 с (`wkhtmltopdf`).

### R-19 Звіт «Звіт за зміну» (FR-17)

`_td_pick_shift(date, name)`: якщо `name` задано — вікно цієї зміни в `date`; інакше, якщо зараз усередині зміни (R-21 W3) — поточна (з початку до `now`), інакше остання, що завершилася сьогодні (за її відсутності — вчора). Вміст (1 сторінка A4): шапка (зміна, інтервал, автор); енергія `Σ feeder kwh` і `Σ incomer kwh` за вікно, пік (макс. 15-хв `kwh·4` фідерів), вартість (`cost`), відхилення від «типової» зміни — середнє `Σ feeder kwh` останніх 4 змін з тією самою назвою (`±N %`); події `td.energy.event` вікна (кількість за рівнями та ≤ 5 останніх: час, назва, стан); планові відключення `td.energy.outage.plan`, що перетинають вікно (назва, статус); обходи `td.energy.round` вікна (якщо модуль `td_energy_mobile` встановлено: назва, виконавець, `done/total`, статус); три найбільші відкриті резерви (cost).
Серверна дія `action_td_energy_shift_report` повертає `report_action` — її відкриває кнопка Пульта. **Збірка:** `action_print` викликає `ir.actions.report.report_action(self, config=False)`: звіти не використовують `external_layout` компанії, тож майстер «Налаштувати макет документа» (його Odoo показує адміністратору, коли макет не задано) не відкривається.

### R-20 Демо-сид (`_td_seed_demo`; FR-21)

Призначення: наповнити стенд так, щоб екран і PDF «Аналітика» були змістовними. **Передумови:** електричний `_td_backfill(days ≥ days)` (W1 R-36) виконано; за `with_baseline` і газу — ресурсний backfill W3 (інакше газова база пропускається); користувач — адміністратор.
1. Вузли прив'язані до ділянок (`_assign_areas`).
2. Продукти (якщо немає за `default_code`): `DEMO-ENR-1…5` — «Шафа-купе 2000» (3,1 м²/од.), «Кухня «Модерн» (комплект)» (8,4), «Фасад МДФ «Лофт», м²» (1,0), «Тумба ТВ-1600» (1,7), «Стіл письмовий» (1,2); категорія — за замовчуванням.
3. Для кожної доби `D`: `act(D) = max(0, E_D − 5 040)/E_ref`, `E_D` — споживання заводу (Σ фідерів) за добу, `E_ref` — медіана `E_D − 5 040` за буднями (5 040 = 210 кВт × 24 год); `plate(D) = 1 290 · act(D) · eff(D)`, `eff(D) = 1 + EFF_GROWTH·r(D)`, `r(D) = clamp((D − (until − 84))/84, 0, 1)` (для останніх 12 тижнів: випуск зростає за тієї самої енергії, EnPI → ≈ 0,94, D-69). **Збірка:** `EFF_GROWTH = 0,28` (у v0.1 було `0,06`; з ним EnPI виходив ≈ 0,98, а не цільові ≈ 0,94).
4. `td.energy.driver.value`: `plate_m2 = plate(D)` (`quality='estimated'`, `source_note='демо-сид'`); `hdd` за `T_mean(D) = 8,5 + 11,5·cos(2π(doy − 200)/365)`, `hdd = max(0, 18 − T_mean)` (`quality='estimated'`).
5. (`with_mo`) МО: для робочих діб з `plate(D) > 0` — `n = 3 + ⌊3·rnd(seed, D, "n")⌋` замовлень `mrp.production` (`origin='td_energy_seed'`, продукти за вагами 0,35/0,2/0,25/0,1/0,1, `product_qty` так, щоб `Σ qty·area = plate(D)` з розподілом за замовленнями); по 2–4 `mrp.workorder` на робочих центрах прямих вузлів (`workcenter_id` вузла; немає — створюється `mrp.workcenter` з `td_energy_node_id`), журнал `mrp.workcenter.productivity` усередині вікон змін (R-21 W3); завершення МО — SQL (`state='done'`, `date_finished`; складських проводок немає, припущення для демо). **Збірка:** (а) для KPI «Енергія в собівартості» (D-68) сид створює **оцінкові** `stock.move` готової продукції МО зі `value` (вартість випуску); склад і залишки не чіпаються. (б) Замість `td.energy.alloc._td_alloc_days(days)` сид будує `td.energy.alloc` власною пакетною SQL-вставкою (`_seed_alloc`): штатний рушій W1 (`_td_alloc_days`; R-08, R-09 `td_energy`) для вікон старіших за 30 діб читає інтервали повним скануванням (≈ 2,5–4 с на добу), тож 400 діб не вкладаються в 15 хв (ТП-04); результат за формою рядків той самий (`kind='direct'`/`'idle'`, `minutes`, `kwh`, `cost`).
6. `td.energy.daily._td_build_days(days)`.
7. (`with_baseline`) база `el/plant`: період — перші 60 % діб (мінімум 180); підгонка та затвердження (`sudo`; при `r2 < r2_min` — `UserError`); EnPI за всі доби; база `gas/plant` з драйвером `hdd` за наявності газових даних. **Збірка:** якщо `hdd` у періоді бази сталий (літо) або модель слабка і підгонка не вдається, газова база створюється **без драйвера**: `action_fit()` дає `β₀ = mean(y)`, далі `method='manual'` і затвердження (стала модель); електрична база без підгонки — `UserError`, газова — лише попередження в лозі.
8. (`with_budget`) бюджет на поточний і 3 попередні місяці: минулі місяці — `round(1,02 · факт, −3)`, поточний — `round(1,02 · прогноз, −3)`; `state='approved'`.
9. Повертає `{"days": n, "products": n, "mos": n, "workorders": n, "alloc_rows": n, "baselines": n, "budgets": n, "seconds": f}`.
Обмеження: 90 діб ≤ 4 хв, 400 діб ≤ 15 хв (ТП-04). Ідемпотентність: драйвери — `UPSERT`; МО з `origin='td_energy_seed'` у діапазоні перестворюються; `purge=True` видаляє **лише** засидоване (МО `td_energy_seed` та їхні наряди, оцінкові `stock.move` цих МО, значення драйверів із `source_note='демо-сид'`, затверджені бази/бюджети з `note='демо-сид'`). Детермінізм — `rnd(seed, …)` (`td_energy/tools/backfill.rnd`).
Перевіряні властивості: `plate_m2 > 0` у робочі доби; `R² ≥ 0,9`; EnPI останніх 12 тижнів ∈ [0,92; 0,96]; `stack_gap_pct ≤ 3`; Σ `alloc.kwh` доби ≤ споживання заводу.

### R-21 Формати чисел

Як W3 R-25 (кВт·год, ₴ — цілі; нечислові підписи — `fmt_dec`/`fmt_int`, кома, вузький пробіл); додатково: `delta_pct` у JSON — число з 1 знаком; у рядках `note` — ціле з явним знаком («−6 %», «+2 %»; мінус — U+2212); питомі: `< 10` → 2 знаки, інакше 1 знак; `hdd`, `tg`-подібні — 1 знак; `r2` — 2 знаки; `enpi` — 2 знаки (у JSON 4); тонни CO₂ — цілі.

### R-22 Шкали осей

Стовпці — R-08 п. 3; EnPI — R-05 п. 3; теплокарта — R-09; інші графіки — `nice` за W3 R-10 п. 3.

## 10. Стани та переходи

| Об'єкт | Стани | Переходи (хто) |
|---|---|---|
| `td.energy.baseline.state` | `draft → approved → archived`; `archived/approved → draft` | `action_fit` (manager, `draft`), `action_approve` (chief), `action_archive`, `action_to_draft` (chief; скидає EnPI бази); автоматично `approved → archived` при затвердженні нової для тієї самої пари |
| `td.energy.budget.state` | `draft → approved` | `action_approve` (chief); правка суми затвердженого — лише chief (скидання в `draft`) |
| `td.energy.daily.quality` | `ok / partial` | перерахунок (R-02) |
| `td.energy.enpi.quality` | `ok / no_driver / partial` | `_cron_enpi`, `recompute` |

## 11. Обробка помилок

- **Немає бази/бюджету/драйверів:** відповідні блоки й `delta_pct` — `null`, підписи «База не задана», блок бюджету відсутній; винятків немає.
- **Частина впала:** `get_dashboard` повертає `{"error": "…"}` лише для частини, що впала; UI показує «Не вдалося завантажити: {частина}» (як W1).
- **Недостатньо даних для підгонки:** `UserError` з кількістю діб; модель лишається в `draft`.
- **Дублікати:** `UNIQUE(day, scope, resource, node)`, `UNIQUE(baseline, day)`, `UNIQUE(driver, day)`; повторні прогони ідемпотентні.
- **Часові пояси:** зберігання UTC naive; доби/зміни — Київ; доби 23/25 год — за локальними слотами W1 A-30; ISODOW для теплокарти — за київською датою.
- **Зміна розмітки ділянок:** історія фактів не змінюється (поле `area_id` у `daily` фіксується); для перерахунку — `action_rebuild` (майстер M-16).
- **Мультикомпанія:** бази та бюджети — `company_id`; факти й EnPI ізолюються через вузли (Q-09).
- **Немає `wkhtmltopdf`:** `create_and_print` віддає `report_action`, помилку формування показує клієнт (UI-10); юніт-тест перевіряє HTML.
- **Відсутній `td_energy_mobile`:** звіт зміни пропускає блок «Обходи».
- **Відсутній `td_energy_control`:** дії `control` резервів приховані, показується запасне «Відкрити» (W3).

## 12. Acceptance Criteria

Колонка «Тип»: UT (зокрема HttpCase) / UT-JS / TC / MAN. Усі `odoo`-тести — `post_install`, теги `-at_install`, `td`, `td_w4`. Фікстури — розд. 13.0; числа взято з макета `Analytics.dc.html` там, де арифметика узгоджена.

### 12.1 `td_energy_analytics` — AC-01…AC-62

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given встановлення на БД із 49 споживачами; When читаємо `td.energy.area` і `node.area_id`; Then 8 ділянок (коди `CUT…LIGHT_OFFICE`, кольори та `spec_driver` за 5.2), вузлів із ділянкою за групами 8 / 3 / 6 / 7 / 12 / 2 / 6 / 5 = 49; повторний `_load_areas`/`_assign_areas` нічого не змінює; ручна правка `area_id` не перезаписується | UT |
| AC-02 | FR-01 | Given ділянка з вузлами; When `unlink`; Then `UserError("Ділянка використовується вузлами.")`; `code` дублюється — помилка унікальності; у `LIGHT_OFFICE` немає драйвера → питоме `null` | UT |
| AC-03 | FR-02 | Given встановлення; Then драйвери `plate_m2` (`mrp_area`, «м²») і `hdd` (`weather_hdd`, база 18, сигнал `ventilation/totals/outdoor_c`); `UNIQUE(code)`; `UNIQUE(driver, day)` у значень | UT |
| AC-04 | FR-03 | Given форма продукту; Then є `td_plate_area_m2` (default 0, `≥ 0`; від'ємне — `ValidationError`) | UT |
| AC-05 | FR-02 | Given 3 готових рухи МО доби (10 × 3,1; 5 × 8,4; 20 × 1,0), рух не `done`, рух без `production_id`, рух поза добою; When `_cron_values`; Then `plate_m2 = 93,0`, `quality='estimated'`, зайві не враховані; немає продуктів з `td_plate_area_m2 > 0` — рядка немає; повторний прогон без дублів | UT |
| AC-06 | FR-02 | Given 24 годинних `v_avg` сигналу температури із середнім 7,0, база 18; Then `hdd = 11,0`, `quality='measured'`; < 18 годин — розрахунок за сирими (≥ 50 показань); немає даних — рядка немає; `T_mean > 18` → `hdd = 0` | UT |
| AC-07 | FR-02 | Given драйвер `manual`; When manager додає значення / user намагається; Then `quality='manual'`, `UNIQUE(driver, day)`; user → `AccessError` | UT |
| AC-08 | FR-04 | Given доба: фідери 600 кВт·год, вводи 500 (вартість 4 200 ₴, експорт 20), СЕС 120, КГУ 0, 12 % слотів фідерів `missing`; When `_td_build_days`; Then рядок `plant`: `qty 600`, `import_qty 500`, `export_qty 20`, `gen_pv_qty 120`, `gen_chp_qty 0`, `cost 4 200`, `quality='partial'` | UT |
| AC-09 | FR-04 | Given 3 споживачі (ділянки CUT, CUT, HVAC) і `alloc` (хвилини, простій); Then рядки `node` з `qty`, `cost`, `area_id` на момент побудови, `minutes`, `idle_qty`; після зміни `node.area_id` побудовані доби не змінюються, а повторна побудова — змінює | UT |
| AC-10 | FR-04 | Given `td.energy.usage` за добу (імпорт 500; газ supply 612 м³, вартість 12 117,60; повітря й тепло); Then рядки `resource`: `el` (`import_qty`), `gas` (`qty 612`, `cost 12 117,60`, `co2_kg 1 199,52`), `air`, `heat`; `Σ resource(el).qty = import_qty` | UT |
| AC-11 | FR-04 | Given календар «Зміна 1» 07:00–16:00 і «Зміна 2» 16:00–23:00; Then `shift1_qty + shift2_qty + off_qty = qty` (допуск 0,001); слот 15:45–16:00 → `shift1`, 16:00–16:15 → `shift2`; `direct_*` за вузлами `alloc_role='direct'`; `plate_s1 + plate_s2 + plate_off = plate_m2`, пропорції — за `direct_*`; при `Σ direct = 0` — уся площа в `plate_s1` | UT |
| AC-12 | FR-04 | Given `_td_build_days`/`_cron_daily`; When два прогони; Then рядки не дублюються (видалення + вставка); сьогоднішня доба перераховується завжди, вчорашня — до `daily_close_h` або якщо немає `plant`; донавантаження ≤ `catchup_days`; `read_enabled=False` — нічого | UT |
| AC-13 | FR-04 | Given добові факти та ротація; Then `plant.qty = Σ feeder kwh` доби (±0,001); `_cron_rotate` видаляє `daily`, `enpi`, `driver.value` старші за `keep_interval_days` | UT |
| AC-14 | FR-05 | Given 30 діб `x_i = 800 + 20·i`, `y_i = 1820 + 4,1·x_i`; When `action_fit`; Then `const_per_day = 1 820,000 ± 0,001`, `coef = 4,100 ± 1e-6`, `r2 = 1`, `rmse = 0`, `n_days = 30`; два драйвери (`y = 1500 + 4,0·plate + 35·hdd`) відновлюються; `k = 0` → `mean(y)` | UT |
| AC-15 | FR-05 | Given `action_fit`; When діб менше за `n_min`; драйвери `plate` і `2·plate`; 4 драйвери; Then `UserError("Замало даних для моделі бази: потрібно ≥ 30 діб, є 25.")`; `UserError("Драйвери лінійно залежні або сталі.")`; `ValidationError("Не більше 3 драйверів.")` | UT |
| AC-16 | FR-05 | Given база `draft`; When approve: user/manager → `AccessError`; chief: `r2 < r2_min` → `UserError`; коефіцієнт `< 0` → `UserError`; коректна → `approved`; Then попередня `approved` пари `(resource, scope, area, company)` → `archived`, одна `approved` на пару, `method='manual'` обходить перевірку R², після затвердження EnPI перераховано | UT |
| AC-17 | FR-05 | Given газ, `y = 120 + 25·hdd` за 40 діб; Then база `gas/plant` з драйвером `hdd`: `const 120`, `coef 25`; `expected(hdd = 11) = 395` | UT |
| AC-18 | FR-06 | Given затверджена база; When `_cron_enpi`; Then рядок доби: `actual`, `expected`, `enpi`; немає значення драйвера → `expected = NULL`, `quality='no_driver'`; `daily.quality='partial'` → `partial`; повтор ідемпотентний | UT |
| AC-19 | FR-06 | Given 7 діб по 1 286 м² (`expected = 49 640`), `actual = 48 150`; When `period_totals`; Then `enpi = 0,9700`, `saving_pct = 3,0`, `saving_qty = 1 490`; вартість економії — з групою cost; `coverage < 0,5` → `enpi = null` | UT |
| AC-20 | FR-06 | Given 12 тижнів EnPI; When `get_enpi`; Then 12 ковзних тижнів за зростанням, `expected_mwh`/`actual_mwh`, `y_min = floor5(0,95·min)`, `y_max = ceil5(1,05·max)`, підписи «12 тижнів тому» / «цей тиждень»; немає бази → `enpi = null`; неповна поточна доба в точки не входить, а останній тиждень нормується `7/n` (R-05 п. 3) | UT |
| AC-21 | FR-06 | Given крон і майстер M-16; Then `_cron_enpi` — вчора та пропуски за кожною затвердженою базою; `draft`/`archived` не рахуються; діапазон майстра > 400 діб → `UserError("Не більше 400 діб.")` | UT |
| AC-22 | FR-07 | Given бюджети; Then `month` — перше число; `amount_uah > 0`; унікальність `(company, month, resource)`; `draft` не враховується в статусі; approve — лише chief | UT |
| AC-23 | FR-07 | Given фікстура R-06 (`today = 2026-10-17`, факт 1–16 = 1 036 000, сьогодні 60 000, типові: пн–пт 62 000, сб 60 000, нд 38 000, план 1 950 000); When `get_status`; Then `fact 1 096 000`, `fact_pct 56`, `month_share 55`, `forecast 1 912 000`, `delta_pct −2`, `text` = «Факт на 17.10 — 1 096 000 ₴ (56 % при 55 % місяця) · прогноз 1 912 000 ₴, на 2 % нижче бюджету» | UT |
| AC-24 | FR-07 | Given граничні випадки; Then зразків дня тижня `< 3` → середнє всіх діб вікна; перший день місяця; останній день (`forecast = fact`); бюджет на ресурс (газ); немає затвердженого — `null`; без групи вартості блок відсутній | UT |
| AC-25 | FR-08 | Given `today = 2026-10-17`; Then вікна й кошики R-01: `w` — 7 (пн…нд за фактичними датами), `m` — 30 (мітки в індексів 0, 5, 10…), `q` — 13 (початок 2026-07-19; «т1», «т3»…), `y` — 12 (початок 2025-11-01, місяці) | UT |
| AC-26 | FR-09 | Given `Σa = 186 400`, `Σe = 198 298`; Then KPI `el`: `value 186 400`, `delta_pct −6,0`, note «−6 % до бази», tone `good`; немає бази — `delta_pct null`, note «База не задана» | UT |
| AC-27 | FR-09 | Given газ `18 400`, очікування `18 039`, `avg_hdd` 9,1 проти 7,9; Then `delta +2,0`, tone `bad`, note «+2 % до бази · похолодання»; HDD −15 % — «тепліше»; `|Δ| ≤ 10 %` — без суфікса; немає бази газу — «—» | UT |
| AC-28 | FR-09 | Given `el cost 1 569 600`, `gas cost 368 280`; Then KPI `cost`: `1 937 880`, note «електрика 81 % · газ 19 %»; без групи вартості KPI відсутній у списку | UT |
| AC-29 | FR-09 | Given споживання 186 400, плит 38 400, база 5,16; Then KPI `spec`: `4,85`, `delta −5,9`, note «база 5,16 · −6 %»; `plate = 0` → `value null` | UT |
| AC-30 | FR-09 | Given `Σ td_energy_cost = 68 000`, `Σ value = 1 000 000`, база 7,3 %; Then KPI `cogs`: `6,8`, tone `good`; знаменник 0 → `null` («—») | UT |
| AC-31 | FR-09 | Given генерація СЕС 41 000, експорт 7 440, споживання 186 400; Then KPI `selfgen`: `18` %, note «СЕС 41 000 кВт·год» | UT |
| AC-32 | FR-09 | Given імпорт 152 840 кВт·год (0,37), газ 18 400 м³ (1,96); Then KPI `co2`: `93` т, note «мережа 57 т · газ 36 т за період» | UT |
| AC-33 | FR-10 | Given 30 діб `daily.node`; Then `stack`: значення серій = `Σ node.qty` ділянки, сірий «Без ділянки» за залишку, `y_max = round(1,08·max)`, `ticks` — треті (7 500 → 8 100 / 2 700, 5 400, 8 100), `unit` за періодом; `stack_gap_pct ≤ 3` на сид-даних (рахує `_td_stack_gap_pct`, R-08 п. 4) | UT |
| AC-34 | FR-11 | Given чотири понеділки з 400/410/390/400 кВт·год о 12:00; Then `cells[0][12] = 400,0`; порядок рядків пн…нд (ISO); порожня комірка — `null`; `max_ref = ceil50(max)`; `base_load_kw = round5(min)` | UT |
| AC-35 | FR-12 | Given зріз `area` за 30 діб (CUT 26 100, плит 38 400); Then `kwh 26 100`, `spec 0,68`, `share_pct` за Σ, `LIGHT_OFFICE` без питомого («—»), сортування за `kwh` спад.; `cost_uah` лише з групою | UT |
| AC-36 | FR-12 | Given `SAW-3`: 7 400 кВт·год, 15 300 хв; Then зріз `eq`: `spec = 29,0 кВт·год/мотогод`; загальний вузол без нарядів — «—»; рядки понад `top_equipment` згортаються в «Інші» | UT |
| AC-37 | FR-12 | Given `WH/MO/00391`: `kwh 2 470`, `qty 60`; Then зріз `mo`: `spec 41,17`, `name = «WH/MO/00391 · … × 60»`; понад `top_mo` — «Інші»; МО без рядків `alloc` не показується | UT |
| AC-38 | FR-12 | Given два МО одного продукту (по 30 шт., 1 200 і 1 270 кВт·год); Then зріз `prod`: `kwh 2 470`, `spec = 2 470/60 = 41,17`; одиниця — з UoM | UT |
| AC-39 | FR-12 | Given дві зміни календаря й доба поза змінами; Then зріз `shift`: три рядки «Зміна 1 · 07:00–16:00», «Зміна 2 · 16:00–23:00», «Ночі й вихідні · без виробництва»; `spec` змін = `kwh/plate_sN`; у третього `spec_text = "база {avg_kw} кВт"` | UT |
| AC-40 | FR-13 | Given нульовий знаменник (плит 0, хвилин 0, `qty 0`); Then `spec = null`, `spec_text = "—"`, винятку немає | UT |
| AC-41 | FR-24 | Given база `Wb` і поточний період; Then `CUT`: `spec_now 0,68`, `spec_base 0,7083` → `delta −4 %`; немає даних у `Wb` → `null`; немає бази — усі `null`; для `mo` порівняння з питомим продукту в `Wb` | UT |
| AC-42 | FR-14 | Given `action_open_cut` за кожним зрізом; Then `act_window` з доменами R-16 (`area`/`eq` — `td.energy.interval`, `mo`/`prod` — `td.energy.alloc`, `shift` — інтервали фідерів з групуванням за `hour_local`); невідомий ключ — `UserError("Невідомий ключ: …")`; поля вартості приховані без групи | UT |
| AC-43 | FR-15 | Given 3 відкриті резерви W3 (у плані 1); When `get_dashboard(parts=['opps'])`; Then `items`, `plan_sum`, `all_sum`, `plan_count`, `open_count` збігаються з W3 API-02/06; без групи вартості суми відсутні; `control` без `td_energy_control` → `enabled=false` + запасна дія; `action_plan_toggle` через W3 змінює `plan_sum` | UT |
| AC-44 | FR-16 | Given дані 30 діб і затверджена база; When `_render_qweb_html` звіту `report_management_document`; Then є таблиця 7 KPI (186 400; «−6 %»), блок EnPI, бюджет, таблиця ділянок, топ-5 обладнання, резерви; без групи вартості немає ₴-колонок і блока бюджету; формат A4 | UT |
| AC-45 | FR-16 | Given стенд із сидом; When «Звіт для керівництва»; Then PDF (`%PDF`) формується ≤ 15 с, розмір < 3 МБ, ≤ 6 сторінок | TC |
| AC-46 | FR-17 | Given поточна зміна / поза зміною; When `create_and_print('shift')`; Then звіт за поточну (з початку зміни) або останню завершену зміну; є енергія, пік, події, відключення, топ-3 резервів; блок обходів — за встановленого `td_energy_mobile`; `action_td_energy_shift_report` повертає `report_action`; `td.energy.dashboard._td_report_action()` повертає його xml-id (з правкою W1 — `capabilities.report = true`) | UT |
| AC-47 | FR-16 | Given користувач `…_user` / без групи; Then `create_and_print` доступний `user`, суми ₴ — лише з групою cost; невідомий `kind` → `UserError("Невідомий вид звіту: x.")`; користувач без груп енергетики — `AccessError` | UT |
| AC-48 | FR-18 | Given hoot з моком API-01; Then зміна періоду перезавантажує `kpis, stack, heatmap, cut, opps`, зміна зрізу — лише `cut`; KPI з тоном; стек 30 стовпців і 8 серій; теплокарта 7×24; EnPI — дві лінії; бюджет — смуга й маркер `month_share_pct`; чекбокс плану оптимістичний і відкочується при помилці; кнопка звіту блокується на час формування; `control` без обробника прихований | UT-JS |
| AC-49 | FR-18 | Given `HttpCase`; When відкрити `action_td_energy_analytics` для періодів `w`, `m`, `q`, `y`; Then без JS-помилок; пункт «Аналітика» видимий `group_td_energy_user`, розділи налаштувань — `…_manager`, «Бюджет» — `…_cost` | UT |
| AC-50 | FR-18 | Given стенд із сидом (R-20); When відкрити «Аналітика»; Then усі блоки заповнені, 7 KPI зі значеннями, EnPI 12 точок, теплокарта 7×24, таблиця зрізу не порожня; скриншот додано | TC (ТК-01) |
| AC-51 | FR-19 | Given ролі `user`/`manager`/`chief`/`admin`; Then `user` нічого не пише; `manager` — підгонка, драйвери `manual`, чернетка бюджету, перерахунок; `chief` — затвердження бази/бюджету; `admin` — усе; record rules за компанією; ключі вартості відсутні в `user` без cost в усіх API та в PDF | UT |
| AC-52 | FR-19 | Given `neutralize.sql`, `-u`, `uninstall`; Then 4 крони неактивні; міграція ідемпотентна й заповнює `alloc.product_id`; `uninstall_hook` не зачіпає електричні дані та вузли; повторний `-u` без змін | UT + DEPLOY_TEST |
| AC-53 | FR-20 | Given `res.config.settings`; Then параметри блока «Аналітика» редагує `…_manager`; `r2_min ∉ [0,1]`, `forecast_min_days > forecast_weeks`, `daily_close_h ∉ [0,12]` → `ValidationError`; зміна `forecast_weeks` змінює типові доби | UT |
| AC-54 | FR-21 | Given БД з електричним backfill 90 діб; When `_td_seed_demo(days=90)`; Then значення `plate_m2` за всі доби, ≥ 3 МО в робочі доби, рядки `td.energy.alloc`, база `el/plant` затверджена з `r2 ≥ 0,9`, EnPI останніх 12 тижнів ∈ [0,92; 0,96] (на збірці — за `EFF_GROWTH = 0,28`), бюджети на 4 місяці затверджені, `stack_gap_pct ≤ 3` | UT |
| AC-55 | FR-21 | Given сид; Then повтор не дублює МО (`origin='td_energy_seed'`), однаковий `seed` → однаковий набір `driver.value` (SHA-256); `purge=True` видаляє лише засидоване; без електричного backfill — `UserError` з підказкою; не адміністратор — `AccessError` | UT |
| AC-56 | FR-22 | Given БД з 400 добами історії та сидом; Then `get_dashboard('m')` ≤ 600 мс, `get_dashboard('y')` ≤ 1,5 с (медіана 10 викликів), ≤ 60 SQL, без N+1 за вузлами й ділянками; теплокарта ≤ 400 мс | UT (ТП-01) |
| AC-57 | FR-22 | Given побудова; Then `_td_build_days` 1 доби ≤ 3 с; 400 діб ≤ 5 хв; `action_fit` ≤ 2 с; `_cron_rotate` ≤ 30 с | UT (ТП-02, ТП-03) |
| AC-58 | FR-22 | Given 400 діб; Then `td.energy.daily` ≈ 55 рядків/доба (≈ 22 000), `td.energy.enpi` ≤ 1 200 (3 бази); розмір відповіді `get_dashboard('y')` ≤ 60 КБ | UT |
| AC-59 | FR-23 | Given меню; Then «Аналітика» (seq 12) іде перед «Завантаження вузлів» (15); розділи «Налаштування → Аналітика» видимі `…_manager`, «Бюджет енергії» — `…_cost` | UT |
| AC-60 | FR-05 | Given `tools/ols.py`; Then немає імпорту `numpy`/`scipy`; функція `fit(X, y)` покрита AC-14/15; на 400 діб × 3 драйвери ≤ 100 мс | UT |
| AC-61 | FR-04 | Given стенд, доба роботи; When крон `_cron_daily`; Then рядок `plant` доби й 49 рядків `node`; `plant.qty` = Σ фідерів; донавантаження після зупинки крона на добу відновлює рядки | TC |
| AC-62 | FR-19 | Given копія демо-БД з W1 і W3; When встановлення `td_energy_analytics`, сид, відкриття екрана, повторний `-u`; Then кількості за 5.4 (8 ділянок, 49 вузлів, 2 драйвери), екран без помилок, повтор без змін | TC (DEPLOY_TEST) |

**Разом `td_energy_analytics`: AC-01…AC-62 = 62 критерії** (UT 56 — зокрема HttpCase і ТП, UT-JS 1 (AC-48), TC 4 (AC-45, AC-50, AC-61, AC-62 = DEPLOY_TEST), UT + DEPLOY_TEST 1 (AC-52)).

## 13. План тестування (для Opus)

### 13.0 Фікстури та вимоги до тестованості

- `tests/common.py` (A): `TestW4Common(TransactionCase)` — `_area(code)`, `_node(code, area)`, `_interval(meter_code, ts_start, kwh, role=..., kwh_export=0, price=8.40)`, `_driver_value(code, day, value)`, `_daily(day, **vals)` (пряма вставка фактів), `_baseline(period, coefs)`, `_budget(month, amount)`, `_alloc(production, node, day, kwh, minutes, kind)`, `_user(groups)`; мок часу `patch("odoo.addons.td_energy.tools.dates.now_utc")`; календар змін — `_calendar_two_shifts()`.
- Фікстура «Макет 17.10» (`TestW4Common._mockup_1710()`): 30 діб фактів під числа AC-26…AC-32 (186 400 / 198 298 / 18 400 / 1 937 880 / 4,85 / 6,8 % / 18 % / 93 т), бюджет 1 950 000 і типові доби для AC-23.
- Детермінізм — `seed`; розрахунки — чисті функції в `tools/*` (тестуються без ORM: `ols`, `periods`, `fmt`).
- JS: hoot, мок `orm.call` з JSON із розд. 7.

### 13.1 Юніт-тести (A, B)

| Файл | Клас | Покриває |
|---|---|---|
| `test_w4_area.py` (A) | `TestW4Area` | AC-01, AC-02, AC-04 |
| `test_w4_driver.py` (A) | `TestW4Driver` | AC-03, AC-05, AC-06, AC-07 |
| `test_w4_daily.py` (A) | `TestW4Daily` | AC-08…AC-13, AC-61 (стенд — окремо) |
| `test_w4_ols.py` (A) | `TestW4Ols` | AC-14, AC-15, AC-60 |
| `test_w4_baseline.py` (A) | `TestW4Baseline` | AC-16, AC-17 |
| `test_w4_enpi.py` (A) | `TestW4Enpi` | AC-18…AC-21 |
| `test_w4_budget.py` (A) | `TestW4Budget` | AC-22…AC-24 |
| `test_w4_kpis.py` (A) | `TestW4Kpis` | AC-25…AC-32 |
| `test_w4_stack_heatmap.py` (A) | `TestW4StackHeatmap` | AC-33, AC-34 |
| `test_w4_cuts.py` (A) | `TestW4Cuts` | AC-35…AC-43 |
| `test_w4_seed.py` (A) | `TestW4Seed` | AC-54, AC-55 |
| `test_w4_security.py` (A) | `TestW4Security` | AC-51, AC-52, AC-53, AC-59, ТБ-01…ТБ-04 |
| `test_w4_perf.py` (A) | `TestW4Perf` | AC-56…AC-58 |
| `test_w4_report.py` (B) | `TestW4Report` | AC-44, AC-46, AC-47 |
| `test_w4_ui.py` (B) | `TestW4Ui` | AC-49 |
| `test_w4_hoot.py` (B) | `TestW4Hoot.test_hoot_suite` | AC-48 (запуск `/web/tests?headless…&id=<hash('@td_energy_analytics')>` за зразком `td_energy/tests/test_w1_hoot.py`) |

### 13.2 Стендові сценарії ТК-01…ТК-05 (`tests/stand/test_w4_tk.py`, A)

Передумови: стенд E-11, встановлені `td_energy`, `td_energy_resources`, `td_energy_analytics`; виконані електричний `_td_backfill(days=400)`, ресурсний `_td_backfill(days=400)` (W3), `_td_seed_demo(days=400)`.

| ТК | Назва | Кроки | Очікується |
|---|---|---|---|
| ТК-01 | Екран «Аналітика» | відкрити екран, пройти періоди `w/m/q/y` і п'ять зрізів | AC-50: блоки заповнені, немає помилок, перемикання ≤ 1,5 с |
| ТК-02 | EnPI і бюджет | перевірити блок EnPI і бюджет; змінити бюджет місяця; затвердити | EnPI 0,92…0,96; блок бюджету оновився після затвердження; chief-only |
| ТК-03 | Резерви та «у плані» | позначити резерв «у плані»; виконати `ticket`-дію | `plan_sum` перераховано; заявку створено з тегом `[OPP-id]`; після закриття заявки резерв `done` |
| ТК-04 | PDF | «Звіт для керівництва», потім «Звіт за зміну» з Пульта (після правки W1) | AC-45, AC-46: PDF відкривається, суми ₴ лише з групою |
| ТК-05 | Жива добудова | після доби роботи крона | AC-61: рядки доби, донавантаження після зупинки |

### 13.3 Тести безпеки (ТБ-01…ТБ-04)

- ТБ-01: користувач `base.group_user` без груп енергетики → `AccessError` на всіх публічних методах `td.energy.analytics` і майстрі звіту.
- ТБ-02: ключі вартості відсутні (KPI «Вартість», `cost_uah`, суми резервів, бюджет, колонка зрізу) без `group_td_energy_cost` в API та PDF (AC-51).
- ТБ-03: затвердження бази й бюджету — лише `chief` (AC-16, AC-22, AC-51).
- ТБ-04: `_td_seed_demo`, `_td_build_days`, `action_rebuild` — лише адміністратор/manager за таблицею прав.

### 13.4 Тести продуктивності (ТП-01…ТП-05)

- ТП-01: `get_dashboard('m')` ≤ 600 мс, `('y')` ≤ 1,5 с, теплокарта ≤ 400 мс, ≤ 60 SQL (AC-56).
- ТП-02: `_td_build_days` — 1 доба ≤ 3 с, 400 діб ≤ 5 хв (AC-57).
- ТП-03: `action_fit` ≤ 2 с; `_cron_rotate` ≤ 30 с (AC-57).
- ТП-04: `_td_seed_demo(days=90)` ≤ 4 хв, `days=400` ≤ 15 хв (R-20).
- ТП-05: PDF «для керівництва» ≤ 15 с, ≤ 3 МБ (AC-45).

### 13.5 DEPLOY_TEST

1. Копія демо-БД з W1 і W3 (`td_demo_tpl`) → `-i td_energy_analytics` → кількості 5.4 (AC-62).
2. Повторне `-u` — без змін.
3. Сид → екран → PDF.
4. Відкат: `uninstall` → електричні дані цілі (AC-52).
5. `neutralize.sql`.

### 13.6 Розподіл тестів і команд за виконавцями (витяг з ARCH §6)

Крок 0 — каркас менеджера (порожні файли, `__init__.py`, маніфести, правка W1 `_td_report_action`); `T=factory3d/tools/odoo`. Усі три виконавці паралельно (≤ 3), спільних файлів немає (власники — розд. 0 і H.0); A і B стартують після злиття W3.

| Виконавець | Тести | Команда |
|---|---|---|
| A «Бекенд аналітики» | `test_w4_area`, `test_w4_driver`, `test_w4_daily`, `test_w4_ols`, `test_w4_baseline`, `test_w4_enpi`, `test_w4_budget`, `test_w4_kpis`, `test_w4_stack_heatmap`, `test_w4_cuts`, `test_w4_seed`, `test_w4_security`, `test_w4_perf` | `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics $T/run_tests.sh td_w4a /td_energy_analytics:TestW4Daily` (та решта класів за списком); регрес `$T/run_tests.sh td_w4a_reg /td_energy` і `/td_energy_resources` |
| B «Фронтенд і звіти» | `test_w4_report`, `test_w4_ui`, `test_w4_hoot` | `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics $T/run_tests.sh td_w4b /td_energy_analytics:TestW4Report` (потім `…TestW4Ui`, `…TestW4Hoot`) |
| C «Мобільний» (Частина II) | `test_wh_template`, `test_wh_schedule`, `test_wh_round`, `test_wh_value`, `test_wh_api`, `test_wh_security`, `test_wh_ui`, `test_wh_hoot` | `F3D_TEST_INSTALL=td_energy,td_energy_mobile $T/run_tests.sh td_w4c /td_energy_mobile:TestWHRound` (та решта класів); регрес W1: `$T/run_tests.sh td_w4c_reg /td_energy` |
| менеджер (інтеграція) | усе | `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics,td_energy_mobile $T/run_tests.sh td_w4_full`; потім стенд ТК-01…ТК-05, ТК-H1…ТК-H3 |

## 14. Definition of Done (W4, `td_energy_analytics`)

- Усі UT/UT-JS AC-01…AC-62 зелені; ТК-01…ТК-05 пройдені; `ruff` без помилок; регресія `td_energy` (142 + W1) і `td_energy_resources` зелена;
- `neutralize.sql`, CHANGELOG, README («Аналітика», «Модель бази ISO 50001», «Бюджет»), DEPLOY_TEST доповнені; огляд безпеки (ТБ-01…ТБ-04);
- міграція `19.0.1.0.0` перевірена на копії БД; сид виконано на стенді, скриншот екрана й приклад PDF додано;
- правку W1 (`_td_report_action`) внесено менеджером і перевірено (ТК-04).

## 15. Відкриті питання та рішення автора

### Питання Q-01…Q-09

| ID | Питання | Кому | Рекомендація | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | Джерело «м² плити»: поле на продукті (E-07) чи площа листів з карт розкрою `td.cut.map` (`td_machine_connect`)? | замовник | поле на продукті зараз; карти розкрою — пізніше як драйвер `cut_map_area` без залежності | `plate_m2` з готової продукції МО × `td_plate_area_m2` (`estimated`) |
| Q-02 | Дані за 2025 рік для моделі бази (≥ 3 міс. добового споживання й випуску) | замовник | підгонка на реальних даних, затвердження головним енергетиком | демо: сид і база на перших 60 % історії |
| Q-03 | Місячний бюджет енергії: звідки (фінанси), у розрізі ресурсів? | бухгалтерія | загальний бюджет + за бажання за газом | уведення вручну (`td.energy.budget`) |
| Q-04 | Офіційні коефіцієнти CO₂ мережі та газу | замовник | значення методики/оператора мережі | 0,37 кг/кВт·год і 1,96 кг/м³ з макета (W3 M-01) |
| Q-05 | Драйвер «м² фасаду» для «Фасади МДФ» (макет 3,10 кВт·год/м²) | технологи | додати драйвер `manual`/MRP пізніше | питоме на м² плити (D-61) |
| Q-06 | Календар змін (дві зміни макета проти «Зміна 1 07:00–15:30» сервера) | замовник | календар із двома змінами | `td.energy.shift_calendar_id` + типове значення макета (W3 R-21) |
| Q-07 | Хто затверджує базу й бюджет | замовник | головний енергетик | `group_td_energy_chief` |
| Q-08 | Web Push і PWA для телефона (GAP Q-14) | менеджер | окреме рішення після W4; стандартний PWA Odoo доступний | не входить |
| Q-09 | Мультикомпанія: факти без `company_id` | менеджер | за двох компаній в одній БД додати `company_id` у `daily` | одна компанія; ізоляція через вузли |

### Рішення автора (A-01…A-18)

| ID | Рішення | Обґрунтування |
|---|---|---|
| A-01 | Два модулі: `td_energy_analytics` (жорстко залежить від `td_energy_resources`) і `td_energy_mobile` (залежить лише від `td_energy`) | аналітика «усі ресурси» потребує `usage`, цін, CO₂, резервів W3; мобільний «Обхід» — операційна функція, не аналітика, і ставиться окремо (Частина II, A-H1) |
| A-02 | Карта «вузол → ділянка» — дані (`area_map.csv`), розмітка за логікою технологічного ланцюга | макет називає категорії, але не вузли; правка менеджером без коду |
| A-03 | Добові факти в таблиці `td.energy.daily` (≈ 55 рядків/доба) замість запитів до 15-хв таблиць | річні зрізи за 49 споживачами — 1,9 млн рядків інтервалів; доби — ≈ 20 тис. рядків |
| A-04 | `area_id` у фактах фіксується при побудові | історія не «переїжджає» при переразмітці |
| A-05 | Модель бази — регресія за ≤ 3 драйверами, чистий Python, нормальні рівняння | ISO 50001; без numpy (як у GAP §5.1) |
| A-06 | Затверджує базу/бюджет `chief`; підгонка — `manager` | E-06: розділення ролей |
| A-07 | EnPI зберігається за добами; тижні/періоди — агрегати `Σa/Σe` | одне джерело правди; перерахунок майстром |
| A-08 | Драйвер `plate_m2` — з готової продукції МО × поле продукту; `quality='estimated'` | E-07 |
| A-09 | Драйвер `hdd` — з годинних агрегатів `td.reading.hour` (зберігаються 400 діб) | сирі читаються лише 30 діб |
| A-10 | Прогноз бюджету — типові доби за днем тижня, як W1 A-30 | єдиний підхід без погоди |
| A-11 | KPI «Електроенергія» — споживання заводу; «Вартість» — купівля (D-51) | зональний тариф |
| A-12 | Площа плит за змінами — пропорційно енергії прямих верстатів | у проводках МО немає часу доби |
| A-13 | Зріз «До бази» — порівняння з тим самим ключем у вікні бази (D-60) | замінює «спрощено» GAP AN-20 перевірюваною формулою |
| A-14 | МО, що перетинають межу вікна, беруться цілком у питомому «на шт.» | спрощення; похибка на межах |
| A-15 | Звіти — qweb-pdf поверх API (ті самі числа, що на екрані) | узгодженість екрана й PDF |
| A-16 | Кнопка «Звіт за зміну» Пульта вмикається хуком `_td_report_action` (правка W1) | W1 D-01; жорсткий `False` і xml-id у коді W1 |
| A-17 | Сид — метод моделі `_td_seed_demo`, МО через ORM, завершення SQL, склад не зачіпається | демо-інструмент; припущення задокументовані (R-20); на збірці додано оцінкові `stock.move` (D-68) і власний SQL-розподіл `alloc` (R-20 п. 5) |
| A-18 | Версії, параметри та ID — модульні; D-xx наскрізні (D-51…D-69) | W3 A-11 |

---

## Журнал змін документа

| Дата | Версія | Зміна |
|---|---|---|
| 18.10.2026 | 0.1 | Перша редакція (`build/energy/W4_SPEC.md`, хвиля W4) |
| 19.10.2026 | 0.2 | Переклад українською; Частина II (мобільний) винесена в [../td_energy_mobile/SPEC.md](../td_energy_mobile/SPEC.md); рішення й відхилення збірки W4 (нижче) |

### Рішення й відхилення, прийняті при збірці W4 (`td_energy_analytics`)

Код: гілка `claude/td-energy-w4`. Рішення збірки внесено в текст розділів із позначкою «**Збірка**»; тут — зведення з посиланнями.

1. **Сид: власний SQL-пакет розподілу.** `tools/seed.py::_seed_alloc` будує `td.energy.alloc` одним пакетом замість `td.energy.alloc._td_alloc_days` (штатний рушій W1 для вікон старших за 30 діб читає інтервали повним скануванням, ≈ 2,5–4 с на добу, тож 400 діб не вкладаються в 15 хв, ТП-04). Форма рядків та сама (R-20 п. 5, A-17).
2. **`EFF_GROWTH = 0,28`** замість 0,06 у R-20 п. 3: з 0,06 EnPI останніх 12 тижнів виходив ≈ 0,98, а не цільових ≈ 0,94 (D-69, AC-54).
3. **Оцінкові `stock.move`** готової продукції зі `value` для KPI «Енергія в собівартості»: D-68 зберігається (`100·Σ td_energy_cost / Σ value`); `value = вартість енергії МО / (7,3 % / eff)`; складські рухи й залишки не створюються; `purge` проводки видаляє (R-20 п. 5 та абзац про ідемпотентність; A-17).
4. **База газу в сиді** — `method='manual'`: коли `hdd` у періоді бази сталий (літо) або модель слабка, створюється стала модель без драйвера (середнє за період); для електричної бази таке не допускається (R-20 п. 7).
5. **EnPI за тижнями:** неповна поточна доба в точки не входить, останній тиждень (≤ 6 повних діб) нормується до 7 діб (`Σ·7/n`); `enpi` від цього не залежить (R-05 п. 3, AC-20).
6. **`_td_stack_gap_pct(period)`** — окремий метод `td.energy.analytics` (джерело `meta.data_quality.stack_gap_pct`; рядок `stack` лишається чистою серією графіка; R-08 п. 4, AC-33).
7. **Звіти:** `report_action(self, config=False)` — звіти не використовують `external_layout` компанії, тож майстер «Налаштувати макет документа» не відкривається (R-19).
8. **KPI-картки екрана** — `flex: 1 1 180px` (`analytics.scss`; у v0.1 — 190px), по два-три в ряд (UI-02).
9. **Нумерація D-xx:** у документах W2 і W3 діапазони D-19…D-50 перетинаються між собою і з `docs/ARCHITECTURE.md` §8 (D-01…D-25); у модульних документах D-xx діє в межах свого документа (див. «Діапазони ID»).

Не зроблено в цій редакції збірки: окремий файл DEPLOY_TEST модуля не створено (AC-52 і AC-62 виконуються вручну за сценарієм 13.5).

