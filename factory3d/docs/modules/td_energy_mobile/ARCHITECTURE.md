> **Розміщення (W4).** Єдине технічне рішення W4 для двох модулів: `td_energy_analytics` (FR-01…FR-24, A-01…A-18, Q-01…Q-09) і `td_energy_mobile` (FR-H1…FR-H10, A-H1…A-H6, Q-H1…Q-H3). Цей файл — копія основного [../td_energy_analytics/ARCHITECTURE.md](../td_energy_analytics/ARCHITECTURE.md); для `td_energy_mobile` належать розд. 2.1–2.8 із позначкою H (FR-H…, M-H…, UI-H…), воркер C. Змінювати спільний текст — в основному файлі.
> Специфікації модулів: [SPEC.md](SPEC.md) (мобільний) і [../td_energy_analytics/SPEC.md](../td_energy_analytics/SPEC.md) (аналітика). Контракти C-01…C-08, API-01, API-H1 заморожені в `odoo_addons/*/contracts/` — зміни лише через менеджера. Читати лише шматками: `grep -nE '^#{2,3} ' <файл>`.

# td_energy_mobile — технічне рішення (W4 «Аналітика й мобільний»: модулі `td_energy_analytics` і `td_energy_mobile`)

Версія 0.2 · 19.10.2026 (v0.1 — 18.10.2026) · автор: агент-аналітик (хвиля W4 блоку «Енергетика») · статус: **погоджено, збудовано (гілка `claude/td-energy-w4`, W1–W4)**.
Вхід: `build/energy/GAP.md` (E-01…E-11, §5 «Аналітика», матриці AN-01…AN-23 і MB-08, MB-09), макети `Analytics.dc.html` і `Mobile.dc.html`. Каркас: `docs/ARCHITECTURE.md` §3, §5, D-18; `build/energy/W1_ARCH.md`, `W1_SPEC.md` (контракти C-30…C-37), [../td_energy_resources/ARCHITECTURE.md](../td_energy_resources/ARCHITECTURE.md), [../td_energy_resources/SPEC.md](../td_energy_resources/SPEC.md) (контракт C-01), код `odoo_addons/td_energy` на гілці `claude/factory3d-build` (`d14d13c`). Специфікація: [SPEC.md](SPEC.md) (далі SPEC). Імена — td (E-04, E-09).
Мова: проза — українською (`docs/DOC_STANDARD.md`), рядки інтерфейсу й `string=` — українські.
Паралельна робота: W2 «Керування» ([../td_energy_control/ARCHITECTURE.md](../td_energy_control/ARCHITECTURE.md)) писалася незалежно; тут на неї посилання **лише через контракти** (дії резервів `control` — W3 C-02).
Перелік змін документа й рішень збірки — у «Журналі змін документа» в кінці файлу.

## Загальна інформація

| Етап ToDo | Що здається | Люд.-год (оцінка автора) |
|---|---|---|
| ТР | `SPEC.md` + цей документ | 30 |
| Архітектура | погодження A-01…A-18, A-H1…A-H6, Q-01…Q-09, Q-H1…Q-H3; контракти C-01…C-08; API-01, API-H1 | 8 |
| Розробка | A «бекенд аналітики» ≈ 56, B «фронтенд і звіти» ≈ 44, C «мобільний» ≈ 32 | 132 |
| Тестування | 88 AC: UT ≈ 76, hoot ≈ 4, стенд ТК-01…ТК-05, ТК-H1…ТК-H3 ≈ 14, DEPLOY_TEST ≈ 6 | 40 |
| Інструкція | §4 цього документа + README/CHANGELOG | 8 |
| **Разом** | | **218** |

Факти середовища (перевірено 18.10.2026, лише читання; на момент написання): W1 у коді (`td_energy` `19.0.1.1.0`; мобільний екран із реєстром вкладок `td_energy.mobile_tabs`, запис `{id, label, sequence, component, [title], [badge(mobile)], [icon]}`; `capabilities.report=False` і жорсткий xml-id `td_energy.action_td_energy_report` у `tools/dashboard.py:216`, `static/src/pult/pult.js:345`); W3 — документи готові (`td.energy.usage`, `td.energy.opportunity`, `tools/shifts.py`), код ще не написаний (нині збудований); `td.energy.interval` містить `role`, `node_id`, `day`, `hour_local`, `kwh`, `kwh_export`, `cost`; `td.energy.alloc` — `kind` (`direct/shared/idle/unallocated/overhead`), `workorder_id`, `production_id`, `node_id`, `kwh`, `minutes`, `cost`; у `mrp.production` є `td_energy_cost` (stored); поля площі плити в продукту **немає** (у `td_machine_connect` — розміри аркуша `td_sheet_*_mm`); Odoo 19: вартість рухів — `stock.move.value` (Monetary, `stock_account`); `td.reading.hour` зберігає годинні агрегати 400 діб, сирі `td.reading` — 30 діб; `td.energy.event.kind` — фіксований `Selection` (`threshold, peak, balance, meter, ats, outage, pfc, trip, manual`); шина `td_energy`: види `kpi, alarm, profile, state, advice`.

## 1. Опис процесу й функціональні вимоги

### 1.1 Контекст

**Макет (затверджено замовником).** `Analytics.dc.html`: шапка з періодами (7 днів / 30 днів / квартал / рік) і кнопкою «Звіт для керівництва»; 7 KPI з Δ до бази; стовпці електроенергії за 8 ділянками; теплокарта «година × день тижня»; EnPI-графік і бюджет місяця; таблиця «Розріз» за 5 вимірами з колонкою «До бази»; «Резерви економії» з чекбоксами «у плані». `Mobile.dc.html`: екран чергового енергетика — 4 вкладки (Стан, Тривоги, Схема, **Обхід**). Відхилення — SPEC «D-51…D-69» (аналітика) і «D-70…D-78» (мобільний): KPI «Електроенергія» — споживання заводу, «Вартість» — вартість купівлі; Δ до моделі бази ISO 50001; «до бази» за зрізами — порівняння з вікном бази; драйвер «м² плити» — оцінка з MRP; фіксовані вікна EnPI і бюджету; реальні PDF і дії резервів; пункти обходу — дані, підказки з нормою й поточним значенням, журнал і події.

**Що вже є (гілка `claude/factory3d-build`) і що дає W4.**

| Складова | Де | Що дає W4 |
|---|---|---|
| Електричні інтервали (`role`, `node_id`, `day`, `hour_local`), індекс `(day, role)` | `td_energy/models/td_energy_interval.py:23-69` | теплокарта (R-09), добові факти (R-02) |
| Розподіл на МО, простій РЦ | `td_energy/models/td_energy_alloc.py:15-58`, `mrp_production.py:15-43` | зрізи «Замовлення», «Продукти», «Обладнання» (R-12, R-13) |
| Календар змін, типовий профіль | `td_energy/models/td_energy_interval.py:251-275,411-433` | зміни (через W3 R-21), прогноз бюджету (R-06) |
| Генератор історії, `rnd` | `td_energy/tools/backfill.py` | демо-сид (R-20) |
| Пульт, кнопка «Звіт за зміну» | `td_energy/static/src/pult/pult.xml:24`, `tools/dashboard.py:216` | звіт за зміну (R-19), гак `_td_report_action` |
| Мобільна оболонка й реєстр вкладок | `td_energy/static/src/mobile/mobile.js:1-27,300-341` | вкладка «Обхід» (UI-H1) |
| Шина, дії, форматування | `td_energy/static/src/common/{bus,actions,format,advice}.js` | UI-H1, UI-07 (резерви), 3D |
| `td.energy.usage`, резерви, зміни | W3 (`td_energy_resources`) | KPI «Вартість», CO₂, газ, «Резерви економії», зміни |
| Вартість готової продукції | `stock_account` (`stock.move.value`) | KPI «Енергія в собівартості» |
| Годинні агрегати температури | `td_telemetry` (`td.reading.hour`) | драйвер HDD |
| qweb-pdf | `td_fire_safety/report/` | два звіти |

**Покриття матриці GAP:** AN-01 (періоди) — FR-08; AN-02 (PDF) — FR-16; AN-03…AN-09 (KPI) — FR-09, FR-05…FR-06; AN-10 (ділянки) — FR-01, FR-10; AN-11 (теплокарта) — FR-11; AN-12, AN-13 (EnPI, база) — FR-05, FR-06; AN-14 (бюджет) — FR-07; AN-15…AN-19 (зрізи) — FR-12, FR-13; AN-20 («до бази») — FR-24; AN-21 (деталізація) — FR-14; AN-22, AN-23 («резерви», «у плані») — FR-15; MB-08 (обхід, прогрес, журнал) — FR-H1…FR-H6; MB-09 (вхід, сповіщення) — FR-H8 (клієнтська дія й шина; Web Push — Q-08). Усі 23 + 2 елементи закрито.

### 1.2 Ролі й сценарії

| Роль (група) | Що робить у W4 | Меню |
|---|---|---|
| Перегляд (`td_energy.group_td_energy_user`) | дивиться «Аналітику» (без ₴), друкує звіти, читає журнал обходів | Енергетика → Аналітика, Журнал обходів |
| Вартість (`…_cost`) | то же + ₴, бюджет | то же + Бюджет енергії |
| **Енергетик** (`…_manager`) | підгонка моделі бази, драйвери вручну, чернетка бюджету, перерахунок, «у план» резервів; **виконує обходи** | + Налаштування → Аналітика |
| **Головний енергетик** (`…_chief`) | затверджує модель бази й бюджет; правит шаблони обходів; завершує/скасовує чужі обходи | + Шаблони обходів |
| Технолог/планувальник (`mrp.group_mrp_manager`) | вводить площу плити в продуктів | Склад → Продукти |
| Адміністратор (`td_factory3d.group_td_admin`) | демо-сид, перерахунок, видалення | Налаштування |

Сценарії: **S1** керівник відкриває «Аналітика», 30 днів, дивиться Δ до бази, EnPI і бюджет, друкує «Звіт для керівництва»; **S2** енергетик розбирає «Резерви економії»: ставить «у план», запускає дію; **S3** головний енергетик задає модель бази: період 2025, драйвер, «Розрахувати», перевіряє R², «Затвердити»; **S4** введення бюджету місяця й контроль прогнозу; **S5** зріз за замовленнями: «WH/MO/…» → деталізація; **S6** черговий на телефоні: «Стан» → «Тривоги» → «Обхід»: відмічає пункти, при відхиленні додає коментар, «Завершити обхід»; **S7** головний енергетик правит шаблон обходу й переглядає журнал; **S8** демо-стенд: адміністратор запускає `_td_seed_demo`.

### 1.3 Функціональні вимоги

| ID | Модуль | Вимога |
|---|---|---|
| FR-01 | td_energy_analytics | Вісім ділянок і прив'язка споживачів (`node.area_id`), дані редагуються без коду |
| FR-02 | td_energy_analytics | Драйвери нормалізації й добові значення: `plate_m2` з MRP (`estimated`), `hdd` з погоди, `manual` |
| FR-03 | td_energy_analytics | Поле площі плити на продукті |
| FR-04 | td_energy_analytics | Добові факти `td.energy.daily` (завод/вузол/ресурс): побудова, дозбір, ротація, зміни |
| FR-05 | td_energy_analytics | Модель бази ISO 50001: регресія за ≤ 3 драйверами або вручну, підгонка, затвердження, версії |
| FR-06 | td_energy_analytics | EnPI за добами й агрегати за тижнями/періодами, економія |
| FR-07 | td_energy_analytics | Бюджет місяця: план, факт, відсоток місяця, прогноз |
| FR-08 | td_energy_analytics | Періоди `w/m/q/y` і кошики |
| FR-09 | td_energy_analytics | Сім KPI з Δ до бази й тоном |
| FR-10 | td_energy_analytics | Стовпці електроенергії за ділянками (стек) |
| FR-11 | td_energy_analytics | Теплокарта «година × день тижня» |
| FR-12 | td_energy_analytics | Зрізи: ділянки, обладнання, замовлення, продукти, зміни |
| FR-13 | td_energy_analytics | Питомі показники (на м² плити, мотогодину, шт., зміну) |
| FR-14 | td_energy_analytics | Деталізація зрізу (стандартне подання з доменом) |
| FR-15 | td_energy_analytics | Резерви економії й чек-лист «у плані» поверх W3 |
| FR-16 | td_energy_analytics | PDF «Звіт для керівництва» |
| FR-17 | td_energy_analytics | PDF «Звіт за зміну» і ввімкнення кнопки Пульта (гак) |
| FR-18 | td_energy_analytics | Клієнтська дія «Аналітика» (OWL) |
| FR-19 | td_energy_analytics | Права, cost-gating, `neutralize.sql`, `uninstall_hook`, міграція |
| FR-20 | td_energy_analytics | Налаштування й параметри `td.energy_analytics.*` |
| FR-21 | td_energy_analytics | Демо-сид: продукти, драйвери, МО, `alloc`, база, EnPI, бюджет |
| FR-22 | td_energy_analytics | Продуктивність і обсяги (розд. 2.7) |
| FR-23 | td_energy_analytics | Меню й довідкові подання |
| FR-24 | td_energy_analytics | «До бази» за рядками зрізів |
| FR-H1 | td_energy_mobile | Шаблони обходів: слоти, пункти з нормою й джерелом значення; демо-шаблон макета |
| FR-H2 | td_energy_mobile | Обходи за розкладом (крон): `open → in_progress → done / missed`, знімок пунктів |
| FR-H3 | td_energy_mobile | Відмітка пункту: виконавець, норма, значення «зараз», відхилення |
| FR-H4 | td_energy_mobile | Завершення обходу: правила, журнал, події на відхилення, час сервера |
| FR-H5 | td_energy_mobile | Вкладка «Обхід» мобільного екрана: прогрес, пункти, завершення, «немає обходу», історія |
| FR-H6 | td_energy_mobile | Журнал обходів (list/search/pivot/form) |
| FR-H7 | td_energy_mobile | Права й блокування виконавця |
| FR-H8 | td_energy_mobile | Мобільний екран цілком: 4 вкладки, реєстр, шина, 390 × 844, кнопки ≥ 48 px |
| FR-H9 | td_energy_mobile | Параметри, `neutralize.sql`, `uninstall_hook`, міграція |
| FR-H10 | td_energy_mobile | Продуктивність і обсяги |

### 1.4 Межі (не входить у W4)

Команди, сценарії й уставки (W2); сам електричний backfill (W1 R-36) і ресурсні дані (W3); Web Push і PWA-налаштування (Q-08); геолокація й фото в обходах; розклад обходів за календарем змін (слоти — у шаблоні, A-H6); автоматичне створення заявок ТО з відхилень (лише подія й ручна заявка W1-майстром); аналіз «до/після» ефекту виконаних резервів; мультикомпанія в фактах `td.energy.daily` (Q-09); драйвер «м² фасаду» (Q-05); погодний прогноз; машинне навчання замість регресії; запис у пристрої (`write_enabled` не змінюється).

### 1.5 Критерії приймання (зведення; повний текст — SPEC розд. 12 і H.12)

Усього **88 критеріїв**: `td_energy_analytics` — AC-01…AC-62 (62), `td_energy_mobile` — AC-H01…AC-H26 (26). Типи перевірки: UT (юніт-тест `odoo.tests`, зокрема HttpCase) / UT-JS (hoot) / TC (стенд на емуляторі й браузері) / DEPLOY_TEST.

| FR | AC | Разом | Тип перевірки |
|---|---|---|---|
| FR-01 | AC-01, 02 | 2 | UT |
| FR-02 | AC-03, 05, 06, 07 | 4 | UT |
| FR-03 | AC-04 | 1 | UT |
| FR-04 | AC-08…13, 61 | 7 | UT (6), TC (AC-61) |
| FR-05 | AC-14…17, 60 | 5 | UT |
| FR-06 | AC-18…21 | 4 | UT |
| FR-07 | AC-22…24 | 3 | UT (числа макета у фікстурах) |
| FR-08 | AC-25 | 1 | UT |
| FR-09 | AC-26…32 | 7 | UT (числа макета у фікстурах) |
| FR-10 | AC-33 | 1 | UT |
| FR-11 | AC-34 | 1 | UT |
| FR-12 | AC-35…39 | 5 | UT |
| FR-13 | AC-40 | 1 | UT |
| FR-14 | AC-42 | 1 | UT |
| FR-15 | AC-43 | 1 | UT |
| FR-16 | AC-44, 45, 47 | 3 | UT (HTML), TC (PDF) |
| FR-17 | AC-46 | 1 | UT |
| FR-18 | AC-48, 49, 50 | 3 | UT-JS, UT (HttpCase), TC |
| FR-19 | AC-51, 52, 62 | 3 | UT, UT + DEPLOY_TEST, TC (DEPLOY_TEST) |
| FR-20 | AC-53 | 1 | UT |
| FR-21 | AC-54, 55 | 2 | UT |
| FR-22 | AC-56, 57, 58 | 3 | UT (ТП-01…ТП-03) |
| FR-23 | AC-59 | 1 | UT |
| FR-24 | AC-41 | 1 | UT |
| FR-H1 | AC-H01, H02 | 2 | UT |
| FR-H2 | AC-H03…H05, H26 | 4 | UT |
| FR-H3 | AC-H06…H09, H25 | 5 | UT (4), UT-JS (AC-H25) |
| FR-H4 | AC-H10, H11, H24 | 3 | UT |
| FR-H5 | AC-H12…H15 | 4 | UT (3), UT-JS (AC-H15) |
| FR-H6 | AC-H16 | 1 | UT |
| FR-H7 | AC-H17 | 1 | UT |
| FR-H8 | AC-H18…H20 | 3 | UT-JS (AC-H18), TC (AC-H19, H20) |
| FR-H9 | AC-H21, H22 | 2 | UT, UT + DEPLOY_TEST |
| FR-H10 | AC-H23 | 1 | UT (ТП-H1, ТП-H2) |

## 2. Технічна реалізація

### 2.1 Місце в системі, контракти й рішення за модулями

`td_energy_analytics` (`depends`: `td_energy`, `td_energy_resources`, `mrp_account` → транзитивно `mrp`, `stock_account`, `maintenance`, `td_telemetry`). `td_energy_mobile` (`depends`: `td_energy`). Нових залежностей Python немає; для PDF — системний `wkhtmltopdf`.

**Рішення за модулями (A-01, A-H1).** GAP пропонував `td_energy_analytics` і `td_energy_mobile`; перевірено на альтернативах:

| Варіант | Плюси | Мінуси |
|---|---|---|
| 1. Усе в `td_energy` (W4-розширення) | немає нових модулів | 142 тести й W1; клієнти без аналітики й чергових отримують таблиці й екрани; важке оновлення |
| 2. Аналітика й мобільний в одному модулі | один модуль | обхід — операційна функція без зв'язку з аналітикою; різні користувачі й життєві цикли; аналітика тягне `td_energy_resources`, а мобільному він не потрібен |
| **3. Два модулі (обрано)** | незалежне встановлення; мобільний залежить лише від `td_energy`; `td_energy_mobile` — майбутній дім Web Push/PWA; аналітика залежить від W3 жорстко заради «усіх ресурсів» | +1 малий модуль (≈ 1 400 рядків) |

| Контракт | Хто → кому | Зміст |
|---|---|---|
| C-01 | W3 `td_energy_resources` → W4 | `td.energy.usage` і семантика потоків (W3 R-07), прапори ресурсу (`in_energy_cost`, `is_derived`, `co2_kg_per_unit`), `td.energy.price._td_price_at`, `td.energy.opportunity` (API-02…API-06, W3), `tools/shifts.py` (W3 R-21), `res.interval._td_backfill` (для сиду) |
| C-02 | `td_energy_analytics` → `td_energy` (W1) | **правка W1 менеджером:** гак `td.energy.dashboard._td_report_action()` (визначений у W4 через `_inherit`) + використання в `tools/dashboard.py:216` (`capabilities.report`, `meta.report_action`) і `static/src/pult/pult.js:345` (`openReport`); поле `td.energy.node.area_id`, `td.energy.alloc.product_id`, блок налаштувань і меню — власні розширення модуля |
| C-03 | `td_energy_analytics` ← `td_energy` | `td.energy.interval`, `alloc`, `node`, `tariff`, `event`, `outage.plan`, `mrp.production.td_energy_cost`, `td.energy.shift_calendar_id`, `tools/{dates,backfill}`, `td.energy.day.mixin` |
| C-04 | `td_energy_analytics` ← MRP/склад | `stock.move` (`production_id`, `quantity`, `value`, `date`), `product.template.td_plate_area_m2` (власне поле), `mrp.production`, `mrp.workorder`, `mrp.workcenter.productivity` |
| C-05 | `td_energy_analytics` ← `td_telemetry` | `td.reading.hour` (температура для HDD) |
| C-06 | `td_energy_mobile` → `td_energy` (W1 C-33) | запис реєстру `td_energy.mobile_tabs` `{id, label, sequence, component, [title], [badge], [icon]}`; props вкладки `{mobile, meta, capabilities, reload, goTab}`; тік шини `state` (A-H3); `useEnergyActions()` (`notify`, `fail`, `show3d`) |
| C-07 | `td_energy_mobile` ← `td_energy` | `td.energy.event._td_log`, `td.energy.dashboard.get_pult(kpis)`, `td.signal`, `td.energy.node`, `tools/dates` |
| C-08 | W4 ↔ W4 (опційно) | звіт зміни читає `env.get("td.energy.round")`; без `td_energy_mobile` блок «Обходи» пропускається |

### 2.2 Архітектурна схема

```
 td_energy:  td.energy.interval ──┐        td.energy.alloc (МО, простій) ─┐         mrp / stock_account (stock.move.value, qty, date)
 td_energy_resources: td.energy.usage ─┤                                 │                         │
 td_telemetry: td.reading.hour (T) ───┤                                  ▼                         ▼
                                      ▼                        td.energy.driver.value  ◀── cron_drivers (02:10)  [plate_m2, hdd, manual]
        cron_daily (15 хв) ──▶  td.energy.daily (plant · node · resource) ──┐
                                      │                                      ▼
                                      ├──────────────▶ td.energy.baseline (OLS, ≤3 драйверів; approve=chief) ──▶ td.energy.enpi (cron 02:30)
                                      ▼                                                                   │
   td.energy.budget (план) ───▶ td.energy.analytics (AbstractModel)  ◀───────────────────────────────────┘
        get_dashboard: kpis · stack · heatmap · enpi · budget · cut · opps ──▶ OWL «Аналітика»   ──▶ qweb-pdf: «для керівництва» / «за зміну»
        opps ◀── td.energy.opportunity (W3, C-32 actions) ──▶ W1 ticket wizard · (W2 control)
 ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  td_energy_mobile:  round.template ─ cron_open ─▶ td.energy.round (+ item, знімок) ─ get_mobile ─▶ OWL вкладка «Обхід» ─▶ td_energy.mobile (4 вкладки)
                         │  cron_close ──▶ missed ─▶ td.energy.event(kind='round')   action_finish ─▶ журнал + події на відхилення
                         └── значення: td.signal | get_pult(kpis…genset.fuel_pct)           bus.tick('state') ◀──▶ інші сесії
```

### 2.3 Нові й розширені об'єкти

| Об'єкт | Призначення | Пише | Читає |
|---|---|---|---|
| `td.energy.area` (M-01), `node.area_id` (M-11) | ділянки | дані, менеджер | факти, зрізи |
| `td.energy.driver` (M-02), `.driver.value` (M-03) | драйвери й значення за добами | крони, менеджер | база, EnPI, KPI |
| `product.template.td_plate_area_m2` (M-10) | площа плити продукту | технолог | драйвер `plate_m2` |
| `td.energy.alloc.product_id` (M-09) | продукт для зрізу | stored related | зрізи |
| `td.energy.daily` (M-08) | добові факти | крон `_cron_daily` | API, звіти |
| `td.energy.baseline` (+ `.line`) (M-04, M-05) | модель бази ISO 50001 | менеджер (підгонка), головний (затвердження) | EnPI, KPI |
| `td.energy.enpi` (M-06) | EnPI за добами | крон, майстер | графік, KPI, звіт |
| `td.energy.budget` (M-07) | бюджет місяця | менеджер, головний | блок бюджету |
| `td.energy.analytics` (M-12) | API | — | OWL, звіти |
| `td.energy.report.wizard` (M-13), `daily.rebuild.wizard` (M-16) | звіти, перерахунок | користувач | — |
| `td.energy.dashboard` (розш., M-14) | гак `_td_report_action` | — | Пульт |
| `td.energy.round.template` / `.slot` / `.template.item` (M-H1…M-H3) | шаблони обходів | головний енергетик | крони |
| `td.energy.round` / `.round.item` (M-H4, M-H5) | обходи й пункти | крон, черговий (через методи) | вкладка, журнал, звіт зміни |
| `td.energy.event` (розш., M-H6) | вид `round` | `action_finish`, крон | Пульт, «Події» |

### 2.4 Інтеграції

| Система | Протокол | Напрям | Частота | При недоступності |
|---|---|---|---|---|
| `td_energy`, `td_energy_resources` | ORM / SQL | читання | крон 15 хв, запит екрана | немає W3 — модуль не встановиться (жорстка залежність) |
| `mrp`, `stock_account` | ORM / SQL | читання (`stock.move`) | добовий крон | немає цін/площ — драйвер без рядка, KPI «—» |
| `td_telemetry` | SQL | читання `td.reading.hour` | добовий крон | немає температури — `hdd` без рядка, база газу не будується |
| `wkhtmltopdf` | процес Odoo | PDF | за кліком | помилка формування → сповіщення (UI-10), HTML перевіряється тестом |
| `bus` | websocket | Odoo → клієнт | тік `state` (≤ 1/5 с, W1) | клієнт на резервному опитуванні 30 с |
| `td_genset_factory3d` | `get_pult(kpis…)` | читання (паливо ДГУ) | при відмітці пункту | значення «немає даних» |
| `td_energy_control` (W2) | через W3 C-02 | дії `control` | за кліком | кнопка прихована, запасне «Відкрити» |

### 2.5 Потоки даних

**Аналітика.** 1) `cron_td_energy_drivers` (02:10): `plate_m2` за готовими рухами МО × площа продукту, `hdd` за годинними температурами. 2) `cron_td_energy_daily` (15 хв): добові факти заводу, вузлів, ресурсів (зміни — з календаря). 3) `cron_td_energy_enpi` (02:30): `actual/expected/enpi` за затвердженими базами. 4) Відкриття екрана: `get_dashboard(period, dim)` → KPI, стек, теплокарта, EnPI/бюджет, зріз, резерви (W3). 5) «У план» → `td.energy.opportunity.action_plan_toggle` (W3). 6) «Звіт для керівництва» → `create_and_print` → qweb → PDF.
**Мобільний.** 1) `cron_td_energy_round_open` (10 хв) створює обхід слота; 2) вкладка «Обхід»: `get_mobile` → відмітки `action_toggle_item` (виконавець блокується, тік `state`); 3) «Завершити» → журнал + події на відхилення; 4) `cron_td_energy_round_close` позначає прострочені `missed` і створює попередження.

### 2.6 Безпека

- Групи без нових: затвердження бази й бюджету — лише «Головний енергетик»; підгонка, драйвери, перерахунок — «Енергетик»; читання — «Перегляд»; ₴ — «Вартість». Ключі вартості **видаляються** з API і PDF без групи.
- Стоп-крани: `td.energy.read_enabled` керує кронами; `write_enabled` **не змінюється** (запису в пристрої немає); `neutralize.sql` вимикає 4 + 3 крони.
- Мобільний: запис пунктів — лише методи (`sudo()` після перевірки групи й виконавця); чужий обхід без `chief` не змінюється; журнал не видаляється користувачами.
- Заблоковано: прямий `write` клієнта в `td.energy.round.item`, `safe_eval` над даними БД, HTTP-маршрути, `x_`-поля, залежність мобільного модуля від `td_genset`.

### 2.7 Продуктивність і обсяги

| Об'єкт | Обсяг | Примітка |
|---|---|---|
| `td.energy.daily` | 1 `plant` + 49 `node` + ≤ 5 `resource` ≈ **55 рядків/добу**; 400 діб ≈ **22 000** (≈ 6 МБ) | індекси `(day, scope)`, `(day, area_id)`, `(node_id, day)` |
| `td.energy.enpi` | ≤ 3 бази × 400 = **1 200** | `UNIQUE(baseline, day)` |
| `td.energy.driver.value` | 2 драйвери × 400 = 800 | |
| `td.energy.baseline` / `.budget` | одиниці / 12 на рік | |
| `td.energy.alloc` | зростання за рахунок сиду: ≈ 4 800 нарядів × ~10 рядків | наявна таблиця; `product_id` — stored related |
| `get_dashboard` | `m` ≤ **600 мс**, `y` ≤ **1,5 с**, ≤ 60 SQL; відповідь ≤ 60 КБ | теплокарта ≤ 400 мс за 210 000 рядками фідерів |
| `_td_build_days` | 1 доба ≤ **3 с**; 400 діб ≤ **5 хв** | AC-57 |
| `action_fit` | ≤ **2 с** | 400 діб × 3 драйвери |
| PDF | ≤ **15 с**, ≤ 3 МБ, ≤ 6 сторінок | `wkhtmltopdf` |
| `_td_seed_demo` | 90 діб ≤ **4 хв**; 400 діб ≤ **15 хв** | R-20 |
| Обходи | 2 слоти × 5 днів × 52 = **520 обходів/рік**, 3 120 пунктів; `get_mobile` ≤ **250 мс**, відповідь ≤ **10 КБ**, відмітка ≤ 150 мс, завершення ≤ 300 мс | `UNIQUE(template, slot, date)`; ротація 730 діб |
| Опитування UI аналітики | 1 запит на зміну періоду + автооновлення 300 с | |

### 2.8 Міграція й деінсталяція

`td_energy_analytics` `19.0.1.0.0`: вісім ділянок і карта 49 вузлів, `alloc.product_id` для наявних рядків (SQL-пакети 5 000), два драйвери, параметри (+9), 4 крони; **базу й бюджет встановлення не створює** (затверджує людина; демо — сид). `td_energy_mobile` `19.0.1.0.0`: шаблон макета (1 / 2 / 6), параметри (+4), 3 крони. Повторне `-u` — без змін. Деінсталяція: аналітика — власні таблиці видаляються штатно, електричні дані й вузли лишаються; мобільний — `uninstall_hook` переводить події `round` у `manual`. Правка W1 (`_td_report_action`) повертається відкатом коміту менеджера.

## 3. Налаштування системи (тестовий сервер)

| Об'єкт | Параметр | Значення (як заповнювати) | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `td.energy_analytics.daily_close_h` / `catchup_days` | 2 / 14 | перерахунок учорашніх діб і дозбір |
| | `td.energy_analytics.forecast_weeks` / `forecast_min_days` | 8 / 3 | прогноз бюджету |
| | `td.energy_analytics.r2_min` / `baseline_min_days` | 0,6 / 30 | перевірка моделі бази |
| | `td.energy_analytics.refresh_s` / `top_equipment` / `top_mo` | 300 / 15 / 20 | екран |
| | `td.energy_mobile.keep_days` / `value_fresh_s` | 730 / 120 | зберігання, свіжість значення |
| | `td.energy_mobile.missed_event` / `history_limit` | 1 / 3 | подія «не виконано», історія |
| | `td.energy.shift_calendar_id` (W1) | календар «Зміна 1 07:00–16:00» + «Зміна 2 16:00–23:00» | Q-06; без календаря — типове значення макета |
| Дані | ділянки й карта вузлів | `data/td_energy_area.csv`, `area_map.csv` (правит менеджер) | 8 + 49 |
| | площа плити (`td_plate_area_m2`) | у кожного продукту, що входить у випуск | без неї `plate_m2` не будується (Q-01) |
| | модель бази | період 2025, драйвер `plate_m2` (електрика), `hdd` (газ) | підгонка — «Енергетик», затвердження — «Головний енергетик» |
| | бюджет | за місяцями | затверджує «Головний енергетик» |
| | шаблон обходу | демо-шаблон макета; правит «Головний енергетик» | Q-H1 |
| Крон | `cron_td_energy_daily` (15 хв), `_drivers` (02:10), `_enpi` (02:30), `_analytics_rotate` (03:20); `cron_td_energy_round_open` (10 хв), `_close` (15 хв), `_rotate` (нд 03:40) | активні | SPEC розд. 6, H.6 |
| Групи | `group_td_energy_manager`, `group_td_energy_chief`, `group_td_energy_cost` | призначити за ролями | |
| Система | `wkhtmltopdf` | встановлено на сервері Odoo | AC-45 |
| Сервіси стенда (E-11) | емулятор + збирач | постійні | W1/W3 |
| Історія | електричний `_td_backfill(days=400)`, ресурсний `_td_backfill(days=400)` (W3), потім `td.energy.analytics._td_seed_demo(days=400)` | один раз, у такому порядку | R-20 |
| Меню | «Енергетика → Аналітика» (12), «Журнал обходів» (76), «Налаштування → Аналітика / Шаблони обходів» | `group_td_energy_user` / manager / chief | |

## 4. Інструкція

**4.1 Аналітика (Перегляд/Вартість).** 1) «Енергетика → Аналітика». 2) Перемикач «7 днів / 30 днів / квартал / рік» перечитує KPI, стек, теплокарту, зріз і резерви. 3) «Розріз»: вкладки Ділянки / Обладнання / Замовлення / Продукти / Зміни; ім'я рядка відкриває стандартний список із відбором за період. 4) «—» у «До бази» — немає затвердженої бази або даних за її період.

**4.2 Модель бази (Енергетик → Головний енергетик).** 1) «Налаштування → Аналітика → Моделі бази» → «Створити»: ресурс (електрика/газ), період (наприклад, 2025), драйвери (`plate_m2`; для газу — `hdd`). 2) «Розрахувати модель»: перевірте `R²`, коефіцієнти, кількість діб. 3) Головний енергетик — «Затвердити» (R² ≥ 0,6, коефіцієнти ≥ 0); попередня затверджена йде в архів. 4) EnPI перераховується автоматично.

**4.3 Бюджет (Енергетик → Головний енергетик).** «Налаштування → Аналітика → Бюджет енергії»: місяць (перше число), сума ₴; «Затвердити». Блок бюджету на екрані показує факт, відсоток місяця й прогноз.

**4.4 Площа плит.** На формі продукту, група «Енергетика», поле «Площа плити, м²/од.» (технолог). Драйвер «м² плити» рахується за готовими МО (оцінка); без площ EnPI і «Питома енергоємність» порожні.

**4.5 Резерви «у плані» (Енергетик).** У блоці «Резерви економії» відмітьте резерв (чекбокс «у план»), запустіть дію; «У плані: X з Y ₴/міс» оновлюється.

**4.6 Звіти.** «Звіт для керівництва» (кнопка на екрані, період береться з перемикача); «Звіт за зміну» — кнопка Пульта (після правки W1) або серверна дія. Суми ₴ — лише з групою «Вартість».

**4.7 Демо-історія (адміністратор).** 1) Емулятор і збирач ≥ 5 хв; 2) електричний `_td_backfill(days=400)` і ресурсний `_td_backfill(days=400)`; 3) `echo 'env["td.energy.analytics"]._td_seed_demo(days=400)' | odoo-bin shell -d <db> --no-http` (≤ 15 хв); 4) відкрийте «Аналітика»: EnPI ≈ 0,94, бюджет, зрізи за замовленнями. `purge=True` видаляє лише сидоване.

**4.8 Обхід на телефоні (черговий — Енергетик).** 1) «Енергетика → Чергування (телефон)» → вкладка «Обхід». 2) Відмічайте пункти (підказка показує норму й значення «зараз»); при «поза нормою» додайте коментар. 3) «Завершити обхід» доступно після відмітки всіх обов'язкових пунктів; «Де це в 3D» відкриває місце на схемі. 4) Якщо обхід виконує колега — вкладка в режимі читання.

**4.9 Шаблони та журнал (Головний енергетик).** «Налаштування → Аналітика/Чергування → Шаблони обходів»: слоти (зміна, час, дні) і пункти (джерело значення `signal:…` або `pult:…`, норма). «Енергетика → Журнал обходів» — усі обходи, фільтри «Не виконані», «З відхиленнями». У формі обходу — кнопки «Завершити» (`action_finish_form`); з меню — серверна дія «Запустити обхід зараз» (`action_start_now`).

## 5. Ризики й відкриті питання

| ID | Питання | Кому | Рекомендація | Що робимо тим часом |
|---|---|---|---|---|
| Q-01 | Джерело «м² плити»: поле на продукті (E-07) чи площа аркушів із карт розкрою | замовник | поле на продукті; карти розкрою — пізніше як драйвер | `plate_m2` з готової продукції МО (`estimated`) |
| Q-02 | Дані 2025 для бази (добове споживання й випуск ≥ 3 міс.) | замовник | підгонка на реальних даних | демо: база на 60 % історії |
| Q-03 | Джерело місячного бюджету | бухгалтерія | загальний бюджет, потім за газом | ручне введення |
| Q-04 | Коефіцієнти CO₂ | замовник | офіційні значення | 0,37 і 1,96 (макет) |
| Q-05 | Драйвер «м² фасаду» для зрізу «Фасади МДФ» | технологи | пізніше | питоме на м² плити (D-61) |
| Q-06 | Календар змін | замовник | дві зміни макета | календар `td.energy.shift_calendar_id` + типове значення |
| Q-07 | Хто затверджує базу й бюджет | замовник | головний енергетик | `group_td_energy_chief` |
| Q-08 | Web Push, PWA | менеджер | окреме рішення після W4 (стандартний PWA Odoo доступний) | не входить |
| Q-09 | Мультикомпанія в `td.energy.daily` | менеджер | `company_id` при двох компаніях | одна компанія |
| Q-H1 | Реальні чек-листи обходів, норми, зміни | електрики | затвердити шаблон макета, потім уточнити | демо-шаблон |
| Q-H2 | Прострочений обхід — тривога? | замовник | так (`warn`) | увімкнено |
| Q-H3 | Хто виконує обходи | замовник | «Енергетик» | `group_td_energy_manager` |

**Блокуючих питань немає.**
**Ризики.** R1 — якість `plate_m2`: залежить від заповнення площ і готових МО; без них EnPI і «Питома» порожні (Q-01). R2 — немає даних 2025 для бази: до їх появи база будується на демо/поточних даних. R3 — **правка W1** (`_td_report_action`, 3 місця) потрібна для кнопки «Звіт за зміну» Пульта; без неї решта працює (менеджер). R4 — злиття з W3 і W2: `td_energy_analytics` використовує `td.energy.usage`, `td.energy.opportunity`, `tools/shifts.py` W3 — W4-A стартує після злиття W3 (A, E); спільні файли емулятора W4 не чіпає. R5 — `wkhtmltopdf` може бути відсутній — AC-45 лише на стенді. R6 — `stock.move.value` дорівнює 0 без оцінки складу → KPI «Енергія в собівартості» «—». R7 — сид важкий (МО/наряди через ORM): 400 діб до 15 хв; припущення «МО завершені SQL без складських проводок» — **уточнено при збірці:** розподіл енергії сид пише власним SQL-пакетом (штатний `td.energy.alloc._td_alloc_days` на 400 діб не вкладається: ≈ 2,5–4 с на добу для вікон старших за 30 діб), а для KPI «Енергія в собівартості» сид додає **оцінкові проводки** `stock.move` готової продукції зі `value` (D-68 зберігається; без рядків руху й залишків, склад не чіпається; `purge` їх видаляє). R8 — `alloc.product_id` — stored related на великій таблиці: міграція SQL-пакетами. R9 — реєстр вкладок W1 (C-33) зафіксований кодом `mobile.js`; зміна форми запису в W1 потребуватиме правки `td_energy_mobile`. R10 — `selection_add` у `td.energy.event.kind`: при видаленні модуля події `round` переводяться в `manual`. R11 — «до бази» і зрізи за МО наближені (A-14); числа демо відрізняються від макета (D-69).

## 6. План збирання агентами

### 6.0 Каркас (менеджер, до воркерів)

1. Створити модулі `td_energy_analytics` і `td_energy_mobile`: `__manifest__.py` (SPEC 1, H.1), порожні файли із заголовком-коментарем за деревами SPEC 0 і H.0, зокрема `models/__init__.py`, `wizard/__init__.py`, `report/__init__.py` із повним списком імпортів — **воркери ці `__init__.py` і маніфести не правлять**.
2. Вставити SPEC/ARCH у `docs/modules/td_energy_analytics/`, `docs/modules/td_energy_mobile/`.
3. Зафіксувати контракти C-01…C-08 і JSON API-01, API-H1 (SPEC розд. 7, H.7): зміни лише через менеджера.
4. **Правка W1 (менеджер, 3 місця):** визначити порожній гак `td.energy.dashboard._td_report_action` (`return None`) і використати його в `tools/dashboard.py:216` (`"report": bool(hook())`, `meta.report_action`) і `static/src/pult/pult.js:345` (`openXml(meta.report_action)`); тест W1 AC-121 оновити.
5. Передумова для W4-A, W4-B: `td_energy_resources` (W3) влито; W4-C не залежить від W3 і може стартувати раніше.
6. Перевірка середовища: `T=factory3d/tools/odoo`; `$T/run_tests.sh td_w4_scaffold /td_energy_analytics` і `/td_energy_mobile` (порожні тести зелені).

### 6.1 Воркери (усі три паралельно, без спільних файлів)

| Воркер | Файли (володіє) | Розділи SPEC (ID) | Здає | Тести (команда) |
|---|---|---|---|---|
| **W4-A «Бекенд аналітики»** | `td_energy_analytics/{hooks.py, migrations/**, models/*.py, tools/{periods,daily,drivers,ols,enpi,budget,kpis,stack,heatmap,cuts,seed,fmt}.py, data/{td_energy_area.csv,area_map.csv,td_energy_driver_data.xml,ir_config_parameter.xml,ir_cron.xml,neutralize.sql}, security/{td_energy_analytics_security.xml,ir.model.access.csv}, tests/{common,test_w4_area,test_w4_driver,test_w4_daily,test_w4_ols,test_w4_baseline,test_w4_enpi,test_w4_budget,test_w4_kpis,test_w4_stack_heatmap,test_w4_cuts,test_w4_seed,test_w4_security,test_w4_perf}.py, tests/stand/test_w4_tk.py}` | M-01…M-12, M-14, M-15, API-01…API-11, API-13…API-15, R-01…R-17, R-20…R-22, розд. 4 (крім `-report.csv`), 5, 6, 9; AC-01…AC-43, AC-51…AC-62 (крім AC-44…AC-50), ТБ-01…ТБ-04, ТП-01…ТП-05, ТК-01…ТК-05 | моделі, розрахунки, API, сид | `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics $T/run_tests.sh td_w4a /td_energy_analytics:TestW4Daily` … за класами; регрес `…/td_energy` і `…/td_energy_resources` |
| **W4-B «Фронтенд і звіти»** | `td_energy_analytics/{static/src/analytics/**, static/tests/analytics.test.js, views/{td_energy_analytics_views,td_energy_budget_views,product_template_views,res_config_settings_views}.xml, views/menus.xml, wizard/*.py, report/**, security/ir.model.access-report.csv, tests/{test_w4_report,test_w4_ui,test_w4_hoot}.py}` | M-13, M-16, API-12, V-01…V-16, UI-01…UI-10, R-18, R-19, розд. 3, `-report.csv`; AC-44…AC-50 | клієнтська дія, подання, меню, звіти, hoot | `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics $T/run_tests.sh td_w4b /td_energy_analytics:TestW4Report` (і `…TestW4Ui`, `…TestW4Hoot`); візуально `$T/serve.sh td_w4b` |
| **W4-C «Мобільний»** | `td_energy_mobile/**` (усе дерево H.0: `hooks.py`, `models/*.py`, `tools/*.py`, `data/**`, `security/**`, `static/src/mobile_round/**`, `static/tests/round.test.js`, `views/**`, `tests/**`, `tests/stand/test_wh_tk.py`) | M-H1…M-H7, V-H1…V-H6, UI-H1…UI-H4, API-H1…API-H6, R-H1…R-H8, H.4…H.9; AC-H01…AC-H26, ТБ-H1, ТБ-H2, ТП-H1, ТП-H2, ТК-H1…ТК-H3 | вкладка «Обхід», журнал, крони, події | `F3D_TEST_INSTALL=td_energy,td_energy_mobile $T/run_tests.sh td_w4c /td_energy_mobile:TestWHRound` (і решта класів, `…TestWHHoot`); візуально `$T/serve.sh td_w4c` (390 × 844); регрес `…/td_energy` (мобільний W1: 3 вкладки без модуля) |

**Перетини, які воркери НЕ роблять.** `models/__init__.py`, `wizard/__init__.py`, `report/__init__.py`, маніфести — менеджер; `security/ir.model.access.csv` — лише A, `ir.model.access-report.csv` (окремий файл через «-», `odoo/tools/convert.py:722`) — лише B; `views/menus.xml` — лише B; подання моделей A пише B за іменами полів SPEC (при розбіжності — правка в злитті менеджером); звіти B викликають API A через контракт (`env["td.energy.analytics"]`), у тестах B — `patch`; `td_energy_mobile` не чіпає файли `td_energy` (запис реєстру — на боці клієнта C); єдина правка W1 — розд. 6.0 п. 4 (менеджер).

### 6.2 Порядок злиття й приймання

1. **Паралельно (3 воркери):** W4-A, W4-B, W4-C. Умова старту A і B — W3 злито (`depends`); C стартує незалежно.
2. **Злиття:** A → `td_energy_analytics` (регрес `/td_energy`, `/td_energy_resources` зелений); потім B (rebase на A); C — у будь-який момент (rebase на `td_energy`).
3. **Інтеграція менеджером:** правка W1 (6.0 п. 4); `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics,td_energy_mobile $T/run_tests.sh td_w4_full`; стенд: емулятор + збирач → електричний і ресурсний `_td_backfill(days=400)` → `_td_seed_demo(days=400)` → ТК-01…ТК-05, ТК-H1…ТК-H3 (E-11: сервер — менеджер).
4. **Приймання Opus:** тести + `git diff --stat` (очікувано: A ≈ 2 600 рядків, B ≈ 1 900, C ≈ 1 400, крім CSV), перевірка D-51…D-78 на скріншотах («Аналітика», PDF, чотири вкладки мобільного на 390 × 844).

### 6.3 Оцінка обсягів за воркерами

| Воркер | Python/XML | JS/XML (OWL) | Тести | Орієнтовно |
|---|---|---|---|---|
| W4-A | ≈ 1 700 | — | ≈ 1 000 | 56 люд.-год |
| W4-B | ≈ 600 (подання, звіти) | ≈ 1 000 | ≈ 300 (hoot) | 44 люд.-год |
| W4-C | ≈ 700 | ≈ 450 | ≈ 550 (зокрема hoot і стенд) | 32 люд.-год |

## Журнал змін документа

| Дата | Версія | Зміна |
|---|---|---|
| 18.10.2026 | 0.1 | Перша редакція (`build/energy/W4_ARCH.md`, хвиля W4) |
| 19.10.2026 | 0.2 | Переклад українською; рішення й відхилення збірки W4 (нижче); посилання на документи W2/W3 у `docs/modules` |

### Рішення й відхилення, прийняті при збірці W4

**`td_energy_analytics`** (докладніше — у SPEC, «Журнал змін документа»):

1. **Сид — власний SQL-пакет розподілу енергії** (`tools/seed.py::_seed_alloc`) замість штатного `td.energy.alloc._td_alloc_days`: штатний рушій W1 на 400 діб не вкладається в 15 хв (вікна старші за 30 діб він читає з інтервалів повним скануванням, ≈ 2,5–4 с на добу). Результат ті самі рядки `td.energy.alloc` (R-20 п. 5, A-17, ризик R7).
2. **`EFF_GROWTH = 0,28`** (у SPEC R-20 п. 3 було 0,06): із 0,06 EnPI останніх 12 тижнів виходив ≈ 0,98, а не цільових ≈ 0,94 (D-69, AC-54).
3. **Оцінкові проводки `stock.move`** готової продукції зі `value` для KPI «Енергія в собівартості»: D-68 зберігається (`100·Σ td_energy_cost / Σ value` за МО в `done`); `value = вартість енергії МО / (7,3 % / eff)`; складські рухи й залишки не створюються; `purge` проводки видаляє. Уточнює припущення «МО завершені SQL без складських проводок» (ризик R7).
4. **База газу** у сиді — `method='manual'` (стала модель без драйвера, середнє за період): HDD у періоді бази сталий (літо) або модель слабка.
5. **EnPI за тижнями** — без неповної поточної доби; останній тиждень (≤ 6 повних діб) нормується до 7 діб (`7/n`); саме `enpi` від цього не залежить.
6. **`_td_stack_gap_pct(period)`** — окремий метод `td.energy.analytics` (джерело `meta.data_quality.stack_gap_pct`, R-10 п. 4).
7. **Звіти:** майстер викликає `report_action(self, config=False)` — звіти не використовують `external_layout` компанії, тож майстер «Налаштувати макет документа» не відкривається.
8. **KPI-картки екрана** — `flex: 1 1 180px` (`analytics.scss`), по два-три в ряд.

**`td_energy_mobile`:**

9. **Вкладка «Обхід» реєструється завжди** (`mobileTabs.add("round", …, {force: true})`, `registerRoundTab()`), без перевірки сторінки тестів; hoot-набір W1 і AC-H18 самі знімають чужу вкладку на час тесту.
10. **`action_start_now()`** (серверна дія V-H4 «Запустити обхід зараз») і **`action_finish_form()`** (кнопка «Завершити» у формі обходу V-H1) — безаргументні обгортки над `action_start`/`action_finish` для `type=object`.

