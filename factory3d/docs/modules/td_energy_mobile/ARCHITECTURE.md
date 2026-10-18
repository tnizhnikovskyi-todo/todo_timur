> **Размещение (W4, каркас 6.0).** Копия `build/energy/W4_ARCH.md` (18.10.2026) — единое техническое решение W4 для двух модулей: `td_energy_analytics` (FR-01…FR-24, A-01…A-18, Q-01…Q-09) и `td_energy_mobile` (FR-H1…FR-H10, A-H1…A-H6, Q-H1…Q-H3). Этот модуль — строки FR-H…, C-06…C-08, A-H…, Q-H…, воркер W4-C; остальное — общий контекст.
> Спецификация модуля: `docs/modules/td_energy_mobile/SPEC.md`. Контракты C-01…C-08, API-01, API-H1 заморожены в `odoo_addons/*/contracts/` — изменения только через менеджера. Читать только кусками: `grep -nE '^#{2,3} ' <файл>`.

# W4 «Аналитика и мобильный» — техническое решение (модули `td_energy_analytics` и `td_energy_mobile`)

Версия 0.1 · 18.10.2026 · автор: агент-аналитик (волна W4 блока «Енергетика») · статус: **черновик на согласование**.
Вход: `build/energy/GAP.md` (E-01…E-11, §5 «Аналітика», матрицы AN-01…AN-23 и MB-08, MB-09), макеты `Analytics.dc.html` и `Mobile.dc.html`. Каркас: `docs/ARCHITECTURE.md` §3, §5, D-18; `build/energy/W1_ARCH.md`, `W1_SPEC.md` (контракты C-30…C-37), `W3_ARCH.md`, `W3_SPEC.md` (контракт C-01), код `odoo_addons/td_energy` на ветке `claude/factory3d-build` (`d14d13c`). Спецификация: `build/energy/W4_SPEC.md` (далее SPEC). Имена — td (E-04, E-09).
Язык: проза — русский (задание), строки интерфейса и `string=` — украинские.
Параллельная работа: W2 «Керування» (`claude/td-energy-w2-docs`) пишется независимо; здесь на неё ссылки **только через контракты** (действия резервов `control` — W3 C-02).
После приёмки файл раскладывается в `docs/modules/td_energy_analytics/ARCHITECTURE.md` и `docs/modules/td_energy_mobile/ARCHITECTURE.md`.

## Общая информация

| Этап ToDo | Что сдаётся | Люд./год (оценка автора) |
|---|---|---|
| ТР | `W4_SPEC.md` + этот документ | 30 |
| Архитектура | согласование A-01…A-18, A-H1…A-H6, Q-01…Q-09, Q-H1…Q-H3; контракты C-01…C-08; API-01, API-H1 | 8 |
| Разработка | A «бекенд аналитики» ≈ 56, B «фронтенд и отчёты» ≈ 44, C «мобильный» ≈ 32 | 132 |
| Тестирование | 88 AC: UT ≈ 76, hoot ≈ 4, стенд ТК-01…ТК-05, ТК-H1…ТК-H3 ≈ 14, DEPLOY_TEST ≈ 6 | 40 |
| Инструкция | §4 этого документа + README/CHANGELOG | 8 |
| **Итого** | | **218** |

Факты среды (проверено 18.10.2026, только чтение): W1 в коде (`td_energy` `19.0.1.1.0`; мобильный экран с реестром вкладок `td_energy.mobile_tabs`, запись `{id, label, sequence, component, [title], [badge(mobile)], [icon]}`; `capabilities.report=False` и жёсткий xml-id `td_energy.action_td_energy_report` в `tools/dashboard.py:216`, `static/src/pult/pult.js:345`); W3 — документы готовы (`td.energy.usage`, `td.energy.opportunity`, `tools/shifts.py`), код ещё не написан; `td.energy.interval` содержит `role`, `node_id`, `day`, `hour_local`, `kwh`, `kwh_export`, `cost`; `td.energy.alloc` — `kind` (`direct/shared/idle/unallocated/overhead`), `workorder_id`, `production_id`, `node_id`, `kwh`, `minutes`, `cost`; в `mrp.production` есть `td_energy_cost` (stored); поля площади плиты у продукта **нет** (в `td_machine_connect` — размеры листа `td_sheet_*_mm`); Odoo 19: стоимость движений — `stock.move.value` (Monetary, `stock_account`); `td.reading.hour` хранит почасовые агрегаты 400 суток, сырые `td.reading` — 30 суток; `td.energy.event.kind` — фиксированный `Selection` (`threshold, peak, balance, meter, ats, outage, pfc, trip, manual`); шина `td_energy`: виды `kpi, alarm, profile, state, advice`.

## 1. Описание процесса и функциональные требования

### 1.1 Контекст

**Макет (утверждён заказчиком).** `Analytics.dc.html`: шапка с периодами (7 дней / 30 дней / квартал / рік) и кнопкой «Звіт для керівництва»; 7 KPI с Δ к базе; столбцы электроэнергии по 8 участкам; теплокарта «година × день тижня»; EnPI-график и бюджет месяца; таблица «Розріз» по 5 измерениям с колонкой «До бази»; «Резерви економії» с чекбоксами «у плані». `Mobile.dc.html`: экран чергового энергетика — 4 вкладки (Стан, Тривоги, Схема, **Обхід**). Отклонения — SPEC «D-51…D-69» (аналитика) и «D-70…D-78» (мобильный): KPI «Електроенергія» — потребление завода, «Вартість» — стоимость покупки; Δ к модели базы ISO 50001; «до бази» по срезам — сравнение с окном базы; драйвер «м² плиты» — оценка из MRP; фиксированные окна EnPI и бюджета; реальные PDF и действия резервов; пункты обхода — данные, подсказки с нормой и текущим значением, журнал и события.

**Что уже есть (ветка `claude/factory3d-build`) и что даёт W4.**

| Складова | Где | Что даёт W4 |
|---|---|---|
| Электрические интервалы (`role`, `node_id`, `day`, `hour_local`), индекс `(day, role)` | `td_energy/models/td_energy_interval.py:23-69` | теплокарта (R-09), суточные факты (R-02) |
| Распределение на МО, простой РЦ | `td_energy/models/td_energy_alloc.py:15-58`, `mrp_production.py:15-43` | срезы «Замовлення», «Продукти», «Обладнання» (R-12, R-13) |
| Календарь смен, типовой профиль | `td_energy/models/td_energy_interval.py:251-275,411-433` | смены (через W3 R-21), прогноз бюджета (R-06) |
| Генератор истории, `rnd` | `td_energy/tools/backfill.py` | демо-сид (R-20) |
| Пульт, кнопка «Звіт за зміну» | `td_energy/static/src/pult/pult.xml:24`, `tools/dashboard.py:216` | отчёт за смену (R-19), хук `_td_report_action` |
| Мобильная оболочка и реестр вкладок | `td_energy/static/src/mobile/mobile.js:1-27,300-341` | вкладка «Обхід» (UI-H1) |
| Шина, действия, форматирование | `td_energy/static/src/common/{bus,actions,format,advice}.js` | UI-H1, UI-07 (резервы), 3D |
| `td.energy.usage`, резервы, смены | W3 (`td_energy_resources`) | KPI «Вартість», CO₂, газ, «Резерви економії», смены |
| Стоимость готовой продукции | `stock_account` (`stock.move.value`) | KPI «Енергія в собівартості» |
| Часовые агрегаты температуры | `td_telemetry` (`td.reading.hour`) | драйвер HDD |
| qweb-pdf | `td_fire_safety/report/` | два отчёта |

**Покрытие матрицы GAP:** AN-01 (периоды) — FR-08; AN-02 (PDF) — FR-16; AN-03…AN-09 (KPI) — FR-09, FR-05…FR-06; AN-10 (участки) — FR-01, FR-10; AN-11 (теплокарта) — FR-11; AN-12, AN-13 (EnPI, база) — FR-05, FR-06; AN-14 (бюджет) — FR-07; AN-15…AN-19 (срезы) — FR-12, FR-13; AN-20 («до бази») — FR-24; AN-21 (деталізація) — FR-14; AN-22, AN-23 («резерви», «у плані») — FR-15; MB-08 (обход, прогресс, журнал) — FR-H1…FR-H6; MB-09 (вход, сповіщення) — FR-H8 (клиентская действие и шина; Web Push — Q-08). Все 23 + 2 элемента закрыты.

### 1.2 Роли и сценарии

| Роль (группа) | Что делает в W4 | Меню |
|---|---|---|
| Перегляд (`td_energy.group_td_energy_user`) | смотрит «Аналітику» (без ₴), печатает отчёты, читает журнал обходов | Енергетика → Аналітика, Журнал обходів |
| Вартість (`…_cost`) | то же + ₴, бюджет | то же + Бюджет енергії |
| **Енергетик** (`…_manager`) | подгонка модели базы, драйверы вручную, черновик бюджета, пересчёт, «у план» резервов; **выполняет обходы** | + Налаштування → Аналітика |
| **Головний енергетик** (`…_chief`) | утверждает модель базы и бюджет; правит шаблоны обходов; завершает/отменяет чужие обходы | + Шаблони обходів |
| Технолог/планировщик (`mrp.group_mrp_manager`) | вводит площадь плиты у продуктов | Склад → Продукти |
| Администратор (`td_factory3d.group_td_admin`) | демо-сид, пересчёт, удаление | Налаштування |

Сценарии: **S1** руководитель открывает «Аналітика», 30 дней, смотрит Δ к базе, EnPI и бюджет, печатает «Звіт для керівництва»; **S2** энергетик разбирает «Резерви економії»: ставит «у план», запускает действие; **S3** главный энергетик задаёт модель базы: период 2025, драйвер, «Розрахувати», проверяет R², «Затвердити»; **S4** ввод бюджета месяца и контроль прогноза; **S5** срез по замовленнях: «WH/MO/…» → деталізація; **S6** чергувальний на телефоне: «Стан» → «Тривоги» → «Обхід»: отмечает пункты, при отклонении добавляет комментарий, «Завершити обхід»; **S7** главный энергетик правит шаблон обхода и просматривает журнал; **S8** демо-стенд: администратор запускает `_td_seed_demo`.

### 1.3 Функциональные требования

| ID | Модуль | Требование |
|---|---|---|
| FR-01 | td_energy_analytics | Восемь участков и привязка потребителей (`node.area_id`), данные редактируются без кода |
| FR-02 | td_energy_analytics | Драйверы нормализации и суточные значения: `plate_m2` из MRP (`estimated`), `hdd` из погоды, `manual` |
| FR-03 | td_energy_analytics | Поле площади плиты на продукте |
| FR-04 | td_energy_analytics | Суточные факты `td.energy.daily` (завод/узел/ресурс): построение, догон, ротация, смены |
| FR-05 | td_energy_analytics | Модель базы ISO 50001: регрессия по ≤ 3 драйверам или вручную, подгонка, утверждение, версии |
| FR-06 | td_energy_analytics | EnPI по суткам и агрегаты по неделям/периодам, экономия |
| FR-07 | td_energy_analytics | Бюджет месяца: план, факт, процент месяца, прогноз |
| FR-08 | td_energy_analytics | Периоды `w/m/q/y` и корзины |
| FR-09 | td_energy_analytics | Семь KPI с Δ к базе и тоном |
| FR-10 | td_energy_analytics | Столбцы электроэнергии по участкам (стек) |
| FR-11 | td_energy_analytics | Теплокарта «година × день тижня» |
| FR-12 | td_energy_analytics | Срезы: участки, обладнання, замовлення, продукти, зміни |
| FR-13 | td_energy_analytics | Удельные показатели (на м² плиты, мотогод, шт., смену) |
| FR-14 | td_energy_analytics | Деталізація среза (стандартное представление с доменом) |
| FR-15 | td_energy_analytics | Резервы экономии и чек-лист «у плані» поверх W3 |
| FR-16 | td_energy_analytics | PDF «Звіт для керівництва» |
| FR-17 | td_energy_analytics | PDF «Звіт за зміну» и включение кнопки Пульта (хук) |
| FR-18 | td_energy_analytics | Клиентское действие «Аналітика» (OWL) |
| FR-19 | td_energy_analytics | Права, cost-gating, `neutralize.sql`, `uninstall_hook`, миграция |
| FR-20 | td_energy_analytics | Настройки и параметры `td.energy_analytics.*` |
| FR-21 | td_energy_analytics | Демо-сид: продукты, драйверы, МО, `alloc`, база, EnPI, бюджет |
| FR-22 | td_energy_analytics | Производительность и объёмы (разд. 2.7) |
| FR-23 | td_energy_analytics | Меню и справочные представления |
| FR-24 | td_energy_analytics | «До бази» по строкам срезов |
| FR-H1 | td_energy_mobile | Шаблоны обходов: слоты, пункты с нормой и источником значения; демо-шаблон макета |
| FR-H2 | td_energy_mobile | Обходы по расписанию (крон): `open → in_progress → done / missed`, снимок пунктов |
| FR-H3 | td_energy_mobile | Отметка пункта: исполнитель, норма, значение «зараз», отклонения |
| FR-H4 | td_energy_mobile | Завершение обхода: правила, журнал, события на отклонения, время сервера |
| FR-H5 | td_energy_mobile | Вкладка «Обхід» мобильного экрана: прогресс, пункты, завершение, «немає обходу», история |
| FR-H6 | td_energy_mobile | Журнал обходов (list/search/pivot/form) |
| FR-H7 | td_energy_mobile | Права и блокировка исполнителя |
| FR-H8 | td_energy_mobile | Мобильный экран целиком: 4 вкладки, реестр, шина, 390 × 844, кнопки ≥ 48 px |
| FR-H9 | td_energy_mobile | Параметры, `neutralize.sql`, `uninstall_hook`, миграция |
| FR-H10 | td_energy_mobile | Производительность и объёмы |

### 1.4 Границы (не входит в W4)

Команды, сценарии и уставки (W2); сам электрический backfill (W1 R-36) и ресурсные данные (W3); Web Push и PWA-настройка (Q-08); геолокация и фото в обходах; расписание обходов по календарю смен (слоты — в шаблоне, A-H6); автоматическое создание заявок ТО из отклонений (только событие и ручная заявка W1-мастером); анализ «до/после» эффекта выполненных резервов; мультикомпания в фактах `td.energy.daily` (Q-09); драйвер «м² фасада» (Q-05); погодный прогноз; машинное обучение вместо регрессии; запись в устройства (`write_enabled` не меняется).

### 1.5 Критерии приёмки (сводка; полный текст — SPEC разд. 12 и H.12)

Всего **88 критериев**: `td_energy_analytics` — AC-01…AC-62 (62), `td_energy_mobile` — AC-H01…AC-H26 (26). Типы проверки: UT (юнит-тест `odoo.tests`, в т. ч. HttpCase) / UT-JS (hoot) / TC (стенд на эмуляторе и браузере) / DEPLOY_TEST.

| FR | AC | Всего | Тип проверки |
|---|---|---|---|
| FR-01 | AC-01, 02 | 2 | UT |
| FR-02 | AC-03, 05, 06, 07 | 4 | UT |
| FR-03 | AC-04 | 1 | UT |
| FR-04 | AC-08…13, 61 | 7 | UT (6), TC (AC-61) |
| FR-05 | AC-14…17, 60 | 5 | UT |
| FR-06 | AC-18…21 | 4 | UT |
| FR-07 | AC-22…24 | 3 | UT (числа макета в фикстурах) |
| FR-08 | AC-25 | 1 | UT |
| FR-09 | AC-26…32 | 7 | UT (числа макета в фикстурах) |
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

## 2. Техническая реализация

### 2.1 Место в системе, контракты и решение по модулям

`td_energy_analytics` (`depends`: `td_energy`, `td_energy_resources`, `mrp_account` → транзитивно `mrp`, `stock_account`, `maintenance`, `td_telemetry`). `td_energy_mobile` (`depends`: `td_energy`). Новых зависимостей Python нет; для PDF — системный `wkhtmltopdf`.

**Решение по модулям (A-01, A-H1).** GAP предлагал `td_energy_analytics` и `td_energy_mobile`; проверено на альтернативах:

| Вариант | Плюсы | Минусы |
|---|---|---|
| 1. Всё в `td_energy` (W4-расширение) | нет новых модулей | 142 теста и W1; клиенты без аналитики и чергових получают таблицы и экраны; тяжёлый апгрейд |
| 2. Аналитика и мобильный в одном модуле | один модуль | обход — операционная функция без связи с аналитикой; разные пользователи и жизненные циклы; аналитика тянет `td_energy_resources`, а мобильному он не нужен |
| **3. Два модуля (выбрано)** | независимая установка; мобильный зависит только от `td_energy`; `td_energy_mobile` — будущий дом Web Push/PWA; аналитика зависит от W3 жёстко ради «усіх ресурсів» | +1 малый модуль (≈ 1 400 строк) |

| Контракт | Кто → кому | Содержание |
|---|---|---|
| C-01 | W3 `td_energy_resources` → W4 | `td.energy.usage` и семантика потоков (W3 R-07), флаги ресурса (`in_energy_cost`, `is_derived`, `co2_kg_per_unit`), `td.energy.price._td_price_at`, `td.energy.opportunity` (API-02…API-06, W3), `tools/shifts.py` (W3 R-21), `res.interval._td_backfill` (для сида) |
| C-02 | `td_energy_analytics` → `td_energy` (W1) | **правка W1 менеджером:** хук `td.energy.dashboard._td_report_action()` (определён в W4 через `_inherit`) + использование в `tools/dashboard.py:216` (`capabilities.report`, `meta.report_action`) и `static/src/pult/pult.js:345` (`openReport`); поле `td.energy.node.area_id`, `td.energy.alloc.product_id`, блок настроек и меню — собственные расширения модуля |
| C-03 | `td_energy_analytics` ← `td_energy` | `td.energy.interval`, `alloc`, `node`, `tariff`, `event`, `outage.plan`, `mrp.production.td_energy_cost`, `td.energy.shift_calendar_id`, `tools/{dates,backfill}`, `td.energy.day.mixin` |
| C-04 | `td_energy_analytics` ← MRP/склад | `stock.move` (`production_id`, `quantity`, `value`, `date`), `product.template.td_plate_area_m2` (собственное поле), `mrp.production`, `mrp.workorder`, `mrp.workcenter.productivity` |
| C-05 | `td_energy_analytics` ← `td_telemetry` | `td.reading.hour` (температура для HDD) |
| C-06 | `td_energy_mobile` → `td_energy` (W1 C-33) | запись реестра `td_energy.mobile_tabs` `{id, label, sequence, component, [title], [badge], [icon]}`; props вкладки `{mobile, meta, capabilities, reload, goTab}`; тик шины `state` (A-H3); `useEnergyActions()` (`notify`, `fail`, `show3d`) |
| C-07 | `td_energy_mobile` ← `td_energy` | `td.energy.event._td_log`, `td.energy.dashboard.get_pult(kpis)`, `td.signal`, `td.energy.node`, `tools/dates` |
| C-08 | W4 ↔ W4 (опционально) | отчёт смены читает `env.get("td.energy.round")`; без `td_energy_mobile` блок «Обходи» пропускается |

### 2.2 Архитектурная схема

```
 td_energy:  td.energy.interval ──┐        td.energy.alloc (МО, простой) ─┐         mrp / stock_account (stock.move.value, qty, date)
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
  td_energy_mobile:  round.template ─ cron_open ─▶ td.energy.round (+ item, снимок) ─ get_mobile ─▶ OWL вкладка «Обхід» ─▶ td_energy.mobile (4 вкладки)
                         │  cron_close ──▶ missed ─▶ td.energy.event(kind='round')   action_finish ─▶ журнал + події на відхилення
                         └── значення: td.signal | get_pult(kpis…genset.fuel_pct)           bus.tick('state') ◀──▶ інші сесії
```

### 2.3 Новые и расширенные объекты

| Объект | Назначение | Пишет | Читает |
|---|---|---|---|
| `td.energy.area` (M-01), `node.area_id` (M-11) | участки | данные, менеджер | факты, срезы |
| `td.energy.driver` (M-02), `.driver.value` (M-03) | драйверы и значения по суткам | кроны, менеджер | база, EnPI, KPI |
| `product.template.td_plate_area_m2` (M-10) | площадь плиты продукта | технолог | драйвер `plate_m2` |
| `td.energy.alloc.product_id` (M-09) | продукт для среза | stored related | срезы |
| `td.energy.daily` (M-08) | суточные факты | крон `_cron_daily` | API, отчёты |
| `td.energy.baseline` (+ `.line`) (M-04, M-05) | модель базы ISO 50001 | менеджер (подгонка), главный (утверждение) | EnPI, KPI |
| `td.energy.enpi` (M-06) | EnPI по суткам | крон, мастер | график, KPI, отчёт |
| `td.energy.budget` (M-07) | бюджет месяца | менеджер, главный | блок бюджета |
| `td.energy.analytics` (M-12) | API | — | OWL, отчёты |
| `td.energy.report.wizard` (M-13), `daily.rebuild.wizard` (M-16) | отчёты, пересчёт | пользователь | — |
| `td.energy.dashboard` (расш., M-14) | хук `_td_report_action` | — | Пульт |
| `td.energy.round.template` / `.slot` / `.template.item` (M-H1…M-H3) | шаблоны обходов | главный энергетик | кроны |
| `td.energy.round` / `.round.item` (M-H4, M-H5) | обходы и пункты | крон, чергувальний (через методы) | вкладка, журнал, отчёт смены |
| `td.energy.event` (расш., M-H6) | вид `round` | `action_finish`, крон | Пульт, «Події» |

### 2.4 Интеграции

| Система | Протокол | Направление | Частота | При недоступности |
|---|---|---|---|---|
| `td_energy`, `td_energy_resources` | ORM / SQL | чтение | крон 15 мин, запрос экрана | нет W3 — модуль не установится (жёсткая зависимость) |
| `mrp`, `stock_account` | ORM / SQL | чтение (`stock.move`) | суточный крон | нет цен/площадей — драйвер без строки, KPI «—» |
| `td_telemetry` | SQL | чтение `td.reading.hour` | суточный крон | нет температуры — `hdd` без строки, база газа не строится |
| `wkhtmltopdf` | процесс Odoo | PDF | по клику | ошибка формирования → уведомление (UI-10), HTML проверяется тестом |
| `bus` | websocket | Odoo → клиент | тик `state` (≤ 1/5 с, W1) | клиент на резервном опросе 30 с |
| `td_genset_factory3d` | `get_pult(kpis…)` | чтение (паливо ДГУ) | при отметке пункта | значение «немає даних» |
| `td_energy_control` (W2) | через W3 C-02 | действия `control` | по клику | кнопка скрыта, запасное «Відкрити» |

### 2.5 Потоки данных

**Аналитика.** 1) `cron_td_energy_drivers` (02:10): `plate_m2` по готовым движениям МО × площадь продукта, `hdd` по часовым температурам. 2) `cron_td_energy_daily` (15 мин): суточные факты завода, узлов, ресурсов (смены — из календаря). 3) `cron_td_energy_enpi` (02:30): `actual/expected/enpi` по утверждённым базам. 4) Открытие экрана: `get_dashboard(period, dim)` → KPI, стек, теплокарта, EnPI/бюджет, срез, резервы (W3). 5) «У план» → `td.energy.opportunity.action_plan_toggle` (W3). 6) «Звіт для керівництва» → `create_and_print` → qweb → PDF.
**Мобильный.** 1) `cron_td_energy_round_open` (10 мин) создаёт обход слота; 2) вкладка «Обхід»: `get_mobile` → отметки `action_toggle_item` (исполнитель блокируется, тик `state`); 3) «Завершити» → журнал + события на отклонения; 4) `cron_td_energy_round_close` помечает просроченные `missed` и создаёт предупреждение.

### 2.6 Безопасность

- Группы без новых: утверждение базы и бюджета — только «Головний енергетик»; подгонка, драйверы, пересчёт — «Енергетик»; чтение — «Перегляд»; ₴ — «Вартість». Ключи стоимости **удаляются** из API и PDF без группы.
- Стоп-краны: `td.energy.read_enabled` управляет кронами; `write_enabled` **не меняется** (запись в устройства отсутствует); `neutralize.sql` отключает 4 + 3 крона.
- Мобильный: запись пунктов — только методы (`sudo()` после проверки группы и исполнителя); чужой обход без `chief` не изменяется; журнал не удаляется пользователями.
- Заблокировано: прямой `write` клиента в `td.energy.round.item`, `safe_eval` над данными БД, HTTP-маршруты, `x_`-поля, зависимость мобильного модуля от `td_genset`.

### 2.7 Продуктивность и обсяги

| Объект | Обсяг | Примечание |
|---|---|---|
| `td.energy.daily` | 1 `plant` + 49 `node` + ≤ 5 `resource` ≈ **55 строк/сутки**; 400 суток ≈ **22 000** (≈ 6 МБ) | индексы `(day, scope)`, `(day, area_id)`, `(node_id, day)` |
| `td.energy.enpi` | ≤ 3 базы × 400 = **1 200** | `UNIQUE(baseline, day)` |
| `td.energy.driver.value` | 2 драйвера × 400 = 800 | |
| `td.energy.baseline` / `.budget` | единицы / 12 в год | |
| `td.energy.alloc` | рост за счёт сида: ≈ 4 800 нарядов × ~10 строк | существующая таблица; `product_id` — stored related |
| `get_dashboard` | `m` ≤ **600 мс**, `y` ≤ **1,5 с**, ≤ 60 SQL; ответ ≤ 60 КБ | теплокарта ≤ 400 мс по 210 000 строкам фидеров |
| `_td_build_days` | 1 сутки ≤ **3 с**; 400 суток ≤ **5 мин** | AC-57 |
| `action_fit` | ≤ **2 с** | 400 суток × 3 драйвера |
| PDF | ≤ **15 с**, ≤ 3 МБ, ≤ 6 страниц | `wkhtmltopdf` |
| `_td_seed_demo` | 90 суток ≤ **4 мин**; 400 суток ≤ **15 мин** | R-20 |
| Обходы | 2 слота × 5 дней × 52 = **520 обходов/год**, 3 120 пунктов; `get_mobile` ≤ **250 мс**, ответ ≤ **10 КБ**, отметка ≤ 150 мс, завершение ≤ 300 мс | `UNIQUE(template, slot, date)`; ротация 730 суток |
| Опрос UI аналитики | 1 запрос на смену периода + автообновление 300 с | |

### 2.8 Миграция и деинсталляция

`td_energy_analytics` `19.0.1.0.0`: восемь участков и карта 49 узлов, `alloc.product_id` для существующих строк (SQL-пакеты 5 000), два драйвера, параметры (+9), 4 крона; **базу и бюджет установка не создаёт** (утверждает человек; демо — сид). `td_energy_mobile` `19.0.1.0.0`: шаблон макета (1 / 2 / 6), параметры (+4), 3 крона. Повторный `-u` — без изменений. Деинсталляция: аналитика — собственные таблицы удаляются штатно, электрические данные и узлы остаются; мобильный — `uninstall_hook` переводит события `round` в `manual`. Правка W1 (`_td_report_action`) возвращается откатом коммита менеджера.

## 3. Настройки системы (тестовый сервер)

| Объект | Параметр | Значение (как заполнять) | Комментарий |
|---|---|---|---|
| `ir.config_parameter` | `td.energy_analytics.daily_close_h` / `catchup_days` | 2 / 14 | пересчёт вчерашних суток и догон |
| | `td.energy_analytics.forecast_weeks` / `forecast_min_days` | 8 / 3 | прогноз бюджета |
| | `td.energy_analytics.r2_min` / `baseline_min_days` | 0,6 / 30 | проверка модели базы |
| | `td.energy_analytics.refresh_s` / `top_equipment` / `top_mo` | 300 / 15 / 20 | экран |
| | `td.energy_mobile.keep_days` / `value_fresh_s` | 730 / 120 | хранение, свежесть значения |
| | `td.energy_mobile.missed_event` / `history_limit` | 1 / 3 | событие «не виконано», история |
| | `td.energy.shift_calendar_id` (W1) | календарь «Зміна 1 07:00–16:00» + «Зміна 2 16:00–23:00» | Q-06; без календаря — умолчание макета |
| Данные | участки и карта узлов | `data/td_energy_area.csv`, `area_map.csv` (правит менеджер) | 8 + 49 |
| | площадь плиты (`td_plate_area_m2`) | у каждого продукта, входящего в выработку | без неё `plate_m2` не строится (Q-01) |
| | модель базы | период 2025, драйвер `plate_m2` (электричество), `hdd` (газ) | подгонка — «Енергетик», утверждение — «Головний енергетик» |
| | бюджет | по месяцам | утверждает «Головний енергетик» |
| | шаблон обхода | демо-шаблон макета; правит «Головний енергетик» | Q-H1 |
| Крон | `cron_td_energy_daily` (15 мин), `_drivers` (02:10), `_enpi` (02:30), `_analytics_rotate` (03:20); `cron_td_energy_round_open` (10 мин), `_close` (15 мин), `_rotate` (вс 03:40) | активны | SPEC разд. 6, H.6 |
| Группы | `group_td_energy_manager`, `group_td_energy_chief`, `group_td_energy_cost` | назначить по ролям | |
| Система | `wkhtmltopdf` | установлен на сервере Odoo | AC-45 |
| Сервисы стенда (E-11) | эмулятор + сборщик | постоянные | W1/W3 |
| История | электрический `_td_backfill(days=400)`, ресурсный `_td_backfill(days=400)` (W3), затем `td.energy.analytics._td_seed_demo(days=400)` | один раз, в таком порядке | R-20 |
| Меню | «Енергетика → Аналітика» (12), «Журнал обходів» (76), «Налаштування → Аналітика / Шаблони обходів» | `group_td_energy_user` / manager / chief | |

## 4. Инструкция

**4.1 Аналітика (Перегляд/Вартість).** 1) «Енергетика → Аналітика». 2) Переключатель «7 днів / 30 днів / квартал / рік» перечитывает KPI, стек, теплокарту, срез и резервы. 3) «Розріз»: вкладки Ділянки / Обладнання / Замовлення / Продукти / Зміни; имя строки открывает стандартный список с отбором за период. 4) «—» в «До бази» — нет утверждённой базы или данных за её период.

**4.2 Модель бази (Енергетик → Головний енергетик).** 1) «Налаштування → Аналітика → Моделі бази» → «Створити»: ресурс (електрика/газ), период (например, 2025), драйверы (`plate_m2`; для газа — `hdd`). 2) «Розрахувати модель»: проверьте `R²`, коэффициенты, число суток. 3) Главный энергетик — «Затвердити» (R² ≥ 0,6, коэффициенты ≥ 0); прежняя утверждённая уходит в архив. 4) EnPI пересчитывается автоматически.

**4.3 Бюджет (Енергетик → Головний енергетик).** «Налаштування → Аналітика → Бюджет енергії»: месяц (первое число), сумма ₴; «Затвердити». Блок бюджета на экране показывает факт, процент месяца и прогноз.

**4.4 Площадь плит.** На форме продукта, группа «Енергетика», поле «Площа плити, м²/од.» (технолог). Драйвер «м² плити» считается по готовым МО (оценка); без площадей EnPI и «Питома енергоємність» пусты.

**4.5 Резервы «у плані» (Енергетик).** В блоке «Резерви економії» отметьте резерв (чекбокс «у план»), запустите действие; «У плані: X з Y ₴/міс» обновляется.

**4.6 Звіти.** «Звіт для керівництва» (кнопка на экране, период берётся с переключателя); «Звіт за зміну» — кнопка Пульта (после правки W1) или серверное действие. Суммы ₴ — только с группой «Вартість».

**4.7 Демо-история (администратор).** 1) Эмулятор и сборщик ≥ 5 мин; 2) электрический `_td_backfill(days=400)` и ресурсный `_td_backfill(days=400)`; 3) `echo 'env["td.energy.analytics"]._td_seed_demo(days=400)' | odoo-bin shell -d <db> --no-http` (≤ 15 мин); 4) откройте «Аналітика»: EnPI ≈ 0,94, бюджет, срезы по замовленнях. `purge=True` удаляет только сидированное.

**4.8 Обхід на телефоне (чергувальний — Енергетик).** 1) «Енергетика → Чергування (телефон)» → вкладка «Обхід». 2) Отмечайте пункты (подсказка показывает норму и значение «зараз»); при «поза нормою» добавьте комментарий. 3) «Завершити обхід» доступно после отметки всех обов'язкових пунктов; «Де це в 3D» открывает место на схеме. 4) Если обход выполняет коллега — вкладка в режиме чтения.

**4.9 Шаблони та журнал (Головний енергетик).** «Налаштування → Аналітика/Чергування → Шаблони обходів»: слоты (смена, время, дни) и пункты (источник значения `signal:…` или `pult:…`, норма). «Енергетика → Журнал обходів» — все обходы, фильтры «Не виконані», «З відхиленнями».

## 5. Риски и открытые вопросы

| ID | Вопрос | Кому | Рекомендация | Что делаем тем временем |
|---|---|---|---|---|
| Q-01 | Источник «м² плиты»: поле на продукте (E-07) или площадь листов из карт раскроя | заказчик | поле на продукте; карты раскроя — позже как драйвер | `plate_m2` из готовой продукции МО (`estimated`) |
| Q-02 | Данные 2025 для базы (суточное потребление и выпуск ≥ 3 мес.) | заказчик | подгонка на реальных данных | демо: база на 60 % истории |
| Q-03 | Источник месячного бюджета | бухгалтерия | общий бюджет, затем по газу | ручной ввод |
| Q-04 | Коэффициенты CO₂ | заказчик | официальные значения | 0,37 и 1,96 (макет) |
| Q-05 | Драйвер «м² фасада» для среза «Фасади МДФ» | технологи | позже | удельное на м² плиты (D-61) |
| Q-06 | Календарь смен | заказчик | две смены макета | календарь `td.energy.shift_calendar_id` + умолчание |
| Q-07 | Кто утверждает базу и бюджет | заказчик | главный энергетик | `group_td_energy_chief` |
| Q-08 | Web Push, PWA | менеджер | отдельное решение после W4 (стандартный PWA Odoo доступен) | не входит |
| Q-09 | Мультикомпания в `td.energy.daily` | менеджер | `company_id` при двух компаниях | одна компания |
| Q-H1 | Реальные чек-листы обходов, нормы, смены | электрики | утвердить шаблон макета, затем уточнить | демо-шаблон |
| Q-H2 | Просроченный обход — тревога? | заказчик | да (`warn`) | включено |
| Q-H3 | Кто выполняет обходы | заказчик | «Енергетик» | `group_td_energy_manager` |

**Блокирующих вопросов нет.**
**Риски.** R1 — качество `plate_m2`: зависит от заполнения площадей и готовых МО; без них EnPI и «Питома» пусты (Q-01). R2 — нет данных 2025 для базы: до их появления база строится на демо/текущих данных. R3 — **правка W1** (`_td_report_action`, 3 места) нужна для кнопки «Звіт за зміну» Пульта; без неё остальное работает (менеджер). R4 — слияние с W3 и W2: `td_energy_analytics` использует `td.energy.usage`, `td.energy.opportunity`, `tools/shifts.py` W3 — W4-A стартует после слияния W3 (A, E); общие файлы эмулятора W4 не трогает. R5 — `wkhtmltopdf` может отсутствовать — AC-45 только на стенде. R6 — `stock.move.value` равна 0 без оценки склада → KPI «Енергія в собівартості» «—». R7 — сид тяжёлый (МО/наряды через ORM): 400 суток до 15 мин; допущение «МО завершены SQL без складских проводок». R8 — `alloc.product_id` — stored related на большой таблице: миграция SQL-пакетами. R9 — реестр вкладок W1 (C-33) зафиксирован кодом `mobile.js`; смена формы записи в W1 потребует правки `td_energy_mobile`. R10 — `selection_add` у `td.energy.event.kind`: при удалении модуля события `round` переводятся в `manual`. R11 — «до бази» и срезы по МО приблизительны (A-14); числа демо отличаются от макета (D-69).

## 6. План сборки агентами

### 6.0 Каркас (менеджер, до воркеров)

1. Создать модули `td_energy_analytics` и `td_energy_mobile`: `__manifest__.py` (SPEC 1, H.1), пустые файлы с заголовком-комментарием по деревьям SPEC 0 и H.0, включая `models/__init__.py`, `wizard/__init__.py`, `report/__init__.py` с полным списком импортов — **воркеры эти `__init__.py` и манифесты не правят**.
2. Вставить SPEC/ARCH в `docs/modules/td_energy_analytics/`, `docs/modules/td_energy_mobile/`.
3. Зафиксировать контракты C-01…C-08 и JSON API-01, API-H1 (SPEC разд. 7, H.7): изменения только через менеджера.
4. **Правка W1 (менеджер, 3 места):** определить пустой хук `td.energy.dashboard._td_report_action` (`return None`) и использовать его в `tools/dashboard.py:216` (`"report": bool(hook())`, `meta.report_action`) и `static/src/pult/pult.js:345` (`openXml(meta.report_action)`); тест W1 AC-121 обновить.
5. Предусловие для W4-A, W4-B: `td_energy_resources` (W3) влит; W4-C не зависит от W3 и может стартовать раньше.
6. Проверка среды: `T=factory3d/tools/odoo`; `$T/run_tests.sh td_w4_scaffold /td_energy_analytics` и `/td_energy_mobile` (пустые тесты зелёные).

### 6.1 Воркеры (все три параллельно, без общих файлов)

| Воркер | Файлы (владеет) | Разделы SPEC (ID) | Сдаёт | Тесты (команда) |
|---|---|---|---|---|
| **W4-A «Бекенд аналитики»** | `td_energy_analytics/{hooks.py, migrations/**, models/*.py, tools/{periods,daily,drivers,ols,enpi,budget,kpis,stack,heatmap,cuts,seed,fmt}.py, data/{td_energy_area.csv,area_map.csv,td_energy_driver_data.xml,ir_config_parameter.xml,ir_cron.xml,neutralize.sql}, security/{td_energy_analytics_security.xml,ir.model.access.csv}, tests/{common,test_w4_area,test_w4_driver,test_w4_daily,test_w4_ols,test_w4_baseline,test_w4_enpi,test_w4_budget,test_w4_kpis,test_w4_stack_heatmap,test_w4_cuts,test_w4_seed,test_w4_security,test_w4_perf}.py, tests/stand/test_w4_tk.py}` | M-01…M-12, M-14, M-15, API-01…API-11, API-13…API-15, R-01…R-17, R-20…R-22, разд. 4 (кроме `-report.csv`), 5, 6, 9; AC-01…AC-43, AC-51…AC-62 (кроме AC-44…AC-50), ТБ-01…ТБ-04, ТП-01…ТП-05, ТК-01…ТК-05 | модели, расчёты, API, сид | `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics $T/run_tests.sh td_w4a /td_energy_analytics:TestW4Daily` … по классам; регресс `…/td_energy` и `…/td_energy_resources` |
| **W4-B «Фронтенд и отчёты»** | `td_energy_analytics/{static/src/analytics/**, static/tests/analytics.test.js, views/{td_energy_analytics_views,td_energy_budget_views,product_template_views,res_config_settings_views}.xml, views/menus.xml, wizard/*.py, report/**, security/ir.model.access-report.csv, tests/{test_w4_report,test_w4_ui,test_w4_hoot}.py}` | M-13, M-16, API-12, V-01…V-16, UI-01…UI-10, R-18, R-19, разд. 3, `-report.csv`; AC-44…AC-50 | клиентское действие, представления, меню, отчёты, hoot | `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics $T/run_tests.sh td_w4b /td_energy_analytics:TestW4Report` (и `…TestW4Ui`, `…TestW4Hoot`); визуально `$T/serve.sh td_w4b` |
| **W4-C «Мобильный»** | `td_energy_mobile/**` (всё дерево H.0: `hooks.py`, `models/*.py`, `tools/*.py`, `data/**`, `security/**`, `static/src/mobile_round/**`, `static/tests/round.test.js`, `views/**`, `tests/**`, `tests/stand/test_wh_tk.py`) | M-H1…M-H7, V-H1…V-H6, UI-H1…UI-H4, API-H1…API-H6, R-H1…R-H8, H.4…H.9; AC-H01…AC-H26, ТБ-H1, ТБ-H2, ТП-H1, ТП-H2, ТК-H1…ТК-H3 | вкладка «Обхід», журнал, кроны, события | `F3D_TEST_INSTALL=td_energy,td_energy_mobile $T/run_tests.sh td_w4c /td_energy_mobile:TestWHRound` (и остальные классы, `…TestWHHoot`); визуально `$T/serve.sh td_w4c` (390 × 844); регресс `…/td_energy` (мобильный W1: 3 вкладки без модуля) |

**Перетины, которые воркеры НЕ делают.** `models/__init__.py`, `wizard/__init__.py`, `report/__init__.py`, манифесты — менеджер; `security/ir.model.access.csv` — только A, `ir.model.access-report.csv` (отдельный файл через «-», `odoo/tools/convert.py:722`) — только B; `views/menus.xml` — только B; представления моделей A пишет B по именам полей SPEC (при расхождении — правка в слиянии менеджером); отчёты B вызывают API A через контракт (`env["td.energy.analytics"]`), в тестах B — `patch`; `td_energy_mobile` не трогает файлы `td_energy` (запись реестра — на стороне клиента C); единственная правка W1 — разд. 6.0 п. 4 (менеджер).

### 6.2 Порядок слияния и приёмки

1. **Параллельно (3 воркера):** W4-A, W4-B, W4-C. Условие старта A и B — W3 слит (`depends`); C стартует независимо.
2. **Слияние:** A → `td_energy_analytics` (регресс `/td_energy`, `/td_energy_resources` зелёный); затем B (rebase на A); C — в любой момент (rebase на `td_energy`).
3. **Интеграция менеджером:** правка W1 (6.0 п. 4); `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics,td_energy_mobile $T/run_tests.sh td_w4_full`; стенд: эмулятор + сборщик → электрический и ресурсный `_td_backfill(days=400)` → `_td_seed_demo(days=400)` → ТК-01…ТК-05, ТК-H1…ТК-H3 (E-11: сервер — менеджер).
4. **Приёмка Opus:** тесты + `git diff --stat` (ожидаемо: A ≈ 2 600 строк, B ≈ 1 900, C ≈ 1 400, кроме CSV), проверка D-51…D-78 на скриншотах («Аналітика», PDF, четыре вкладки мобильного на 390 × 844).

### 6.3 Оценка объёмов по воркерам

| Воркер | Python/XML | JS/XML (OWL) | Тесты | Орієнтовно |
|---|---|---|---|---|
| W4-A | ≈ 1 700 | — | ≈ 1 000 | 56 люд./год |
| W4-B | ≈ 600 (представления, отчёты) | ≈ 1 000 | ≈ 300 (hoot) | 44 люд./год |
| W4-C | ≈ 700 | ≈ 450 | ≈ 550 (в т. ч. hoot и стенд) | 32 люд./год |
