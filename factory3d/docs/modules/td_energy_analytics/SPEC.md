> **Размещение (W4, каркас 6.0).** Копия из `build/energy/W4_SPEC.md` (18.10.2026): общая преамбула (строки 1–64: обозначения, диапазоны ID, отклонения D-51…D-80) и Часть I — разделы 0–15 модуля `td_energy_analytics`. Связанный модуль — `td_energy_mobile` (`docs/modules/td_energy_mobile/SPEC.md`).
> Изменения контрактов C-01…C-08, API-01 и API-H1 — только через менеджера (JSON-эталоны: `odoo_addons/td_energy_analytics/contracts/`, `odoo_addons/td_energy_mobile/contracts/`). Ссылки на разделы «0», «H.0» и т. п. — внутри этого файла.
> Читать только кусками: `grep -nE '^#{2,3} ' <файл>`, затем Read с offset/limit.

# W4 «Аналитика и мобильный»: спецификация (модули `td_energy_analytics` и `td_energy_mobile`)

Версия 0.1 · 18.10.2026 · стандарт `docs/DOC_STANDARD.md` · техническое решение: `build/energy/W4_ARCH.md` (далее ARCH: FR-01…FR-24 и FR-H1…FR-H10, A-01…A-18 и A-H1…A-H6, Q-01…Q-09 и Q-H1…Q-H3).
Вход: `build/energy/GAP.md` (E-01…E-11, §5 «Аналітика», AN-01…AN-23, MB-08, MB-09), макеты `Analytics.dc.html` и `Mobile.dc.html` (вкладки «Стан», «Тривоги», «Схема», **«Обхід»**); контракты W1 (`W1_SPEC.md`: API-05/API-12, R-27, R-32 `actions[]` = C-32, R-33, R-36, реестр мобильных вкладок C-33, UI-09) и W3 (`W3_SPEC.md`: `td.energy.usage`, `td.energy.opportunity`, `tools/shifts.py`, `td.energy.price._td_price_at`, контракт C-01).
Опирается на: `docs/ARCHITECTURE.md` §3, §5, D-18; код `td_energy` на ветке `claude/factory3d-build` (`d14d13c`: `td.energy.interval`, `td.energy.alloc`, `td.energy.node`, `tools/{dates,forecast,backfill,bus}.py`, `static/src/mobile/mobile.js`); `td_telemetry` (`td.reading.hour`); `mrp`, `mrp_account`, `stock_account` (`stock.move.value`, Odoo 19).
Язык: проза — русский (задание), строки интерфейса, `string=` и тексты ошибок — украинские.
После приёмки файл раскладывается в `docs/modules/td_energy_analytics/SPEC.md` и `docs/modules/td_energy_mobile/SPEC.md`.

## Условные обозначения, диапазоны ID, отклонения от макета

**Имена (E-09).** Модули: `td_energy_analytics`, `td_energy_mobile`; модели `td.energy.*`; поля стандартных моделей — `td_*`; новые методы — `_td_*`; параметры — `td.energy_analytics.<param>` и `td.energy_mobile.<param>`; глобальные стоп-краны — `td.energy.read_enabled` (общий). Маршрутов HTTP нет (кроме стандартного `/report/pdf/...` Odoo).

**Диапазоны ID.** Нумерация модульная, как в W3: поза таблицами ID пишется с модулем (`td_energy_analytics M-08`). Для второго модуля документа — префикс `H` (mobile, «handheld»): FR-H1, M-H1, V-H1, API-H1, R-H1, AC-H01, UI-H1, A-H1, Q-H1, ТК-H1. Сквозные для блока D-xx: W1 D-01…D-18, W2 (резерв D-19…D-30), W3 D-31…D-50, **W4 D-51…D-80** (аналитика D-51…D-69, мобильный D-70…D-78).

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
| A (решения автора) | A-01…A-18 | A-H1…A-H6 |
| Q | Q-01…Q-09 | Q-H1…Q-H3 |

Обозначения: UT — юнит-тест `odoo.tests` (`TransactionCase`/`HttpCase`), UT-JS — hoot, TC — стенд (эмулятор + сборщик + Odoo + браузер), MAN — вручную. `req`=`required=True`, `idx`=`index=True`, `cost` = `groups="td_energy.group_td_energy_cost"`. Все `Datetime` — UTC naive; «Киев» — `Europe/Kyiv` (`td_energy/tools/dates.py`). Периоды: `w` (7 дней), `m` (30 дней), `q` (квартал), `y` (год).

### Отклонения от макета (D-xx)

| ID | Где в макете | Что в реализации | Почему |
|---|---|---|---|
| D-51 | Analytics: KPI «Електроенергія 186 400 кВт·год», «Вартість 1 937 880 ₴» (= 186 400 × 8,40 + газ) | «Електроенергія» = потребление завода (Σ фидеров); «Вартість» = стоимость **покупки** (импорт по зонам тарифа + газ); арифметика макета воспроизводится только в фикстурах AC | Макет считает всё по плоской цене, реальный тариф зональный |
| D-52 | «−6 % до бази» | Δ к модели базы ISO 50001: `Σ факт / Σ ожидание − 1` за период; без утверждённой базы — «—» и подсказка «База не задана» | GAP AN-03, AN-13 |
| D-53 | «Газ +2 % до бази · похолодання» | база газа — отдельная модель с драйвером HDD; подпись «похолодання»/«тепліше» вычисляется (R-07) | AN-04 |
| D-54 | «Власна генерація 18 %, СЕС 41 000 кВт·год» | `(генерація − експорт) / споживання`; подпись «СЕС {кВт·год}» — из `gen_pv_qty` | Формула в макете не указана; значение 18 % воспроизводится |
| D-55 | «Викиди CO₂ 105 т · мережа 69 т · газ 36 т на місяць» | считается за выбранный период; электричество — по импорту из сети (самогенерация без выбросов), газ — по `co2_kg_per_unit` ресурса | Подпись «на місяць» неверна для периодов 7 дней…год |
| D-56 | Стовпці: 8 категорий ровно | 8 участков + при ненулевом остатке 9-й серый сегмент «Без ділянки» (узлы без `area_id`) | Данные не обязаны быть полностью размечены |
| D-57 | Теплокарта: фиксированный масштаб 700 кВт | `max_ref = ceil50(максимум ячейки)`, 5 уровней; базовая нагрузка — минимум ячеек, округление до 5 | Масштаб по данным |
| D-58 | EnPI-график и бюджет — по месяцу/12 неделям при любом периоде | Сохранено: окна EnPI (12 скользящих недель) и бюджета (календарный месяц) не зависят от переключателя периода | Как в макете |
| D-59 | «56 % при 55 % місяця» | `part_месяца = день_месяца / число_дней`; прогноз = факт + типовые сутки по дню недели (R-06) | Макет не раскрывает формулу |
| D-60 | Колонка «До бази» в срезах (−4 %, +3 %…) | Для каждой строки: относительное изменение удельного показателя к тому же ключу в окне базы (R-15); нет данных в окне — «—»; для замовлень — к удельному показателю продукта в окне базы | GAP AN-20 «спрощено» |
| D-61 | «Фасади МДФ — 3,10 кВт·год/м²» (на м² фасада) | удельное — на м² плиты (`plate_m2`) по умолчанию; драйвер «м² фасада» не создаётся (Q-05) | В данных нет площади фасадов |
| D-62 | Зміни: «Зміна 1 07:00–16:00», «Зміна 2 16:00–23:00», «Ночі й вихідні» | окна — календарь `td.energy.shift_calendar_id` (W3 R-21, умолчание — смены макета); площадь плиты по сменам — пропорционально энергии прямых станков | Нет времени суток в производственных проводках (A-12) |
| D-63 | «Резерви економії» — 8 строк | показываются все открытые резервы (9 правил W3: добавлено `dock_gates`); «У плані» сохраняется (поле `in_plan` W3), а не живёт в состоянии страницы | W3 D-47 |
| D-64 | Кнопки действий резервов: тосты | реальные действия по контракту C-32 (link/ticket/control); `control` скрыт без `td_energy_control` (запасное — «Відкрити») | W1 D-02 |
| D-65 | Деталізація: тост «профіль, події, обладнання за 30 днів» | открывается стандартный список/сводная таблица с доменом среза (`ir.actions.act_window`) | Нет произвольной «панели» в Odoo без кастомного OWL; стандартные представления достаточны |
| D-66 | «квартал», «рік» | квартал = 13 скользящих недель (91 день, окно заканчивается сегодня); год = 12 календарных месяцев, последний — неполный | Однозначные окна |
| D-67 | «Звіт для керівництва» — тост | PDF qweb (A4, ≤ 6 страниц): KPI, EnPI, бюджет, участки, топ-обладнание, резервы; кнопка работает одним кликом | AN-02 |
| D-68 | KPI «Енергія в собівартості 6,8 %, база 7,3 %» | `Σ td_energy_cost МО / Σ вартость готової продукції МО` (`stock.move.value`); без оценки склада — «—» | Odoo 19: стоимость — `stock.move.value` |
| D-69 | Числа демо (186 400 кВт·год/30 дн., 4,85 кВт·год/м² и т. д.) | экран показывает данные стенда и демо-сид (R-20); макет не воспроизводится, за исключением фикстур AC; EnPI демо стремится к 0,94 за счёт сидированного роста выпуска | Нет реальных данных 2025 года |
| D-70 | Mobile: «Обхід ТП і ГРЩ · зміна 2», 6 пунктов | заголовок и пункты из шаблона и слота (данные); демо — 6 пунктов макета, 2 слота (смена 1 и 2) | Шаблоны задаёт энергетик |
| D-71 | Подсказка «норма до 85 °C · зараз 58 °C», «паливо ≥ 60 % · зараз 78 %» | значение «зараз» берётся из сигнала или из `get_pult` (паливо ДГУ — KPI моста); нет источника — статический текст без «зараз» | Паливо ДГУ не `td.signal` |
| D-72 | «Завершити обхід» серая, пока не отмечено всё; тост «Позначте всі пункти обходу: залишилось N» | Сохранено: кнопка визуально неактивна (`aria-disabled`), но нажимается и показывает тост; при полном выполнении — основная кнопка | Доступность |
| D-73 | Пункт без «норми» | добавлены: отметка «поза нормою» с комментарием (необязательно) и событие энергетики `kind='round'` при завершении | MB-08 |
| D-74 | Вкладка «Обхід» всегда с активным обходом | нет открытого обхода — «Зараз обходу немає. Наступний: {зміна} о {HH:MM}» и три последних обхода | Расписание по слотам |
| D-75 | «записано в журнал о 14:40» | время — серверное (Киев), из ответа `action_finish` | |
| D-76 | Один пользователь | исполнитель блокируется за первым отметившим; другой видит «Обхід виконує {ім'я}» (только чтение); главный энергетик может завершить чужой | Несколько чергових |
| D-77 | Нет статуса «не виконано» | по истечении слота обход переходит в `missed`, создаётся предупреждение (`td.energy.event`, `kind='round'`) | Журнал и контроль |
| D-78 | Вкладка «Обхід» без счётчика | сохранено: бейджа нет (`badge` не задаётся) | Как в макете |

---


# ЧАСТЬ I. `td_energy_analytics`

## 0. Дерево файлов

Владельцы: **A** — бекенд (модели, расчёты, данные, сид), **B** — фронтенд, представления, отчёты (ARCH §6). Файлы без буквы — менеджер (каркас: пустые файлы с заголовком; `__init__.py` и манифест воркеры не правят).

```
odoo_addons/td_energy_analytics/
├── __manifest__.py                        (менеджер) раздел 1
├── __init__.py                            (менеджер) from . import models, wizard, report; from .hooks import post_init_hook, uninstall_hook
├── hooks.py                               A  post_init_hook: _load_areas, _assign_areas, _fill_alloc_product; uninstall_hook
├── migrations/19.0.1.0.0/post-migration.py A  идемпотентный вызов тех же функций
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
│   ├── td_energy_dashboard.py             A  M-14 (`_inherit td.energy.dashboard`: хук `_td_report_action`)
│   └── res_config_settings.py             A  M-15
├── tools/
│   ├── periods.py                         A  R-01
│   ├── daily.py                           A  R-02 (SQL-построение)
│   ├── drivers.py                         A  R-03
│   ├── ols.py                             A  R-04 (чистый Python, без numpy)
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
│   └── td_energy_daily_rebuild_wizard.py  B  M-16 → пересчёт фактов (Transient)
├── report/
│   ├── __init__.py                        (менеджер)
│   ├── report_data.py                     B  R-18, R-19 (AbstractModel-обработчики `report.td_energy_analytics.*`)
│   ├── report_management.xml              B  `ir.actions.report` (V-12)
│   ├── report_management_templates.xml    B  qweb A4
│   ├── report_shift.xml                   B  `ir.actions.report` смены (V-13)
│   └── report_shift_templates.xml         B
├── data/
│   ├── td_energy_area.csv                 A  8 участков
│   ├── area_map.csv                       A  49 узлов → участок
│   ├── td_energy_driver_data.xml          A  драйверы `plate_m2`, `hdd` (noupdate=1)
│   ├── ir_config_parameter.xml            A  параметры (разд. 5.1)
│   ├── ir_cron.xml                        A  4 крона (разд. 6)
│   └── neutralize.sql                     A
├── security/
│   ├── td_energy_analytics_security.xml   A  record rules
│   ├── ir.model.access.csv                A  M-01…M-09, M-15
│   └── ir.model.access-report.csv         B  M-13, M-16 (суффикс после «-» — `odoo/tools/convert.py:722`)
├── static/src/analytics/                  B  UI-01…UI-10: analytics.js/.xml/.scss, kpis, stack, heatmap, enpi, cut, opps
├── static/tests/analytics.test.js         B  hoot
├── views/
│   ├── td_energy_analytics_views.xml      B  V-01 (client action), V-02…V-09 (формы/списки)
│   ├── td_energy_budget_views.xml         B  V-07, V-08
│   ├── product_template_views.xml         B  V-10
│   ├── res_config_settings_views.xml      B  V-14
│   └── menus.xml                          B  V-15
└── tests/
    ├── common.py                          A  TestW4Common (фикстуры)
    ├── test_w4_area.py, test_w4_driver.py, test_w4_daily.py, test_w4_ols.py, test_w4_baseline.py,
    │   test_w4_enpi.py, test_w4_budget.py, test_w4_kpis.py, test_w4_stack_heatmap.py, test_w4_cuts.py,
    │   test_w4_seed.py, test_w4_security.py, test_w4_perf.py                           A
    ├── test_w4_report.py, test_w4_ui.py, test_w4_hoot.py                              B
    └── stand/test_w4_tk.py                                                           A  ТК-01…ТК-05 (pytest против стенда)

odoo_addons/td_energy_mobile/                  C  (Часть II)
```

Правки существующего кода `td_energy` (менеджер, не воркеры; см. ARCH §6.0): `td.energy.dashboard._td_report_action()` + использование в `tools/dashboard.py` и `static/src/pult/pult.js` (разд. 2.M-14).

## 1. Манифест

- `name`: «Аналітика енергетики»; `version`: `19.0.1.0.0`; `author`: `ToDo`; `license`: `LGPL-3`; `category`: `Manufacturing/Maintenance`.
- `depends`: `["td_energy", "td_energy_resources", "mrp_account"]` (транзитивно `mrp`, `stock_account`, `maintenance`).
- `external_dependencies`: нет Python-зависимостей; для PDF нужен системный `wkhtmltopdf` (штатный для Odoo; проверка — AC-45).
- `data` (порядок): `security/td_energy_analytics_security.xml`, `security/ir.model.access.csv`, `security/ir.model.access-report.csv`, `data/td_energy_driver_data.xml`, `data/ir_config_parameter.xml`, `data/ir_cron.xml`, `views/td_energy_analytics_views.xml`, `views/td_energy_budget_views.xml`, `views/product_template_views.xml`, `views/res_config_settings_views.xml`, `report/report_management.xml`, `report/report_management_templates.xml`, `report/report_shift.xml`, `report/report_shift_templates.xml`, `views/menus.xml` (последним). CSV участков и карты узлов в `data` **не** входят — их загружает `hooks._load_areas(env)` (идемпотентно, после установки узлов).
- `assets`: `web.assets_backend`: `td_energy_analytics/static/src/analytics/**`; `web.assets_unit_tests`: `td_energy_analytics/static/tests/**`.
- `post_init_hook`: `hooks.post_init_hook` (`_load_areas`, `_assign_areas`, `_fill_alloc_product`); `uninstall_hook`: `hooks.uninstall_hook`.

## 2. Модели

Общее: `company_id` — у моделей с деньгами и настройками (baseline, budget); фактические таблицы (`daily`, `enpi`, `driver.value`) — без `company_id` (изоляция через узлы/правила). `_log_access=False` — у `td.energy.daily`, `td.energy.enpi`, `td.energy.driver.value`.

### M-01 `td.energy.area` — участок (FR-01)

`_name = "td.energy.area"`, `_description = "Енергетика: ділянка"`, `_order = "sequence, id"`.

| Поле | Тип | Параметры |
|---|---|---|
| `code` | Char | size=16, req, idx, `UNIQUE(code)` |
| `name` | Char | size=64, req |
| `sequence` | Integer | default 10 |
| `color` | Char | size=7, req, «Колір» |
| `active` | Boolean | default True |
| `spec_driver_id` | Many2one `td.energy.driver` | «Драйвер питомого показника»; пусто — удельное «—» (освещение и офис) |
| `node_ids` | One2many `td.energy.node` | `area_id`, readonly |
| `node_count` | Integer | compute |

Данные — разд. 5.2. `unlink` участка, у которого есть узлы → `UserError("Ділянка використовується вузлами.")`.

### M-11 `td.energy.node` — расширение (`_inherit`)

`area_id` — Many2one `td.energy.area` (idx, ondelete=set null, «Ділянка»); заполняется для узлов `kind='consumer'` (карта 5.2); редактируется `group_td_energy_manager`; форма узла (`td_energy.view_td_energy_node_form`) получает поле в группе «Облік» (V-09).

### M-02 `td.energy.driver` — драйвер нормализации (FR-02)

`_name = "td.energy.driver"`, `_description = "Енергетика: драйвер"`, `_order = "sequence, id"`.

| Поле | Тип | Параметры |
|---|---|---|
| `code` | Char | size=16, req, idx, `UNIQUE(code)`; `plate_m2`, `hdd`, произвольные для `manual` |
| `name` | Char | size=64, req |
| `source_kind` | Selection | `mrp_area`/«Площа плит з MRP», `weather_hdd`/«Градусо-доби опалення», `manual`/«Вручну»; req |
| `uom` | Char | size=16, «Одиниця» («м²», «°C·доба») |
| `base_temp_c` | Float | digits (4,1), default 18.0; для `weather_hdd` |
| `temp_signal_code` | Char | size=64, default `ventilation/totals/outdoor_c`; для `weather_hdd` |
| `sequence` | Integer | default 10 |
| `active` | Boolean | default True |
| `value_ids` | One2many `td.energy.driver.value` | |

Данные: `plate_m2` (`mrp_area`, «м²», `sequence 10`) и `hdd` (`weather_hdd`, «°C·доба», 18, `sequence 20`) — `noupdate=1`. Удаление драйвера, используемого базой, запрещено (`ondelete=restrict` в строках базы).

### M-03 `td.energy.driver.value` — суточное значение драйвера (FR-02)

`_name = "td.energy.driver.value"`, `_log_access = False`, `_order = "day desc, driver_id"`.

| Поле | Тип | Параметры |
|---|---|---|
| `driver_id` | Many2one `td.energy.driver` | req, idx, ondelete=cascade |
| `day` | Date | req, idx (Киев) |
| `value` | Float | digits (14,3), req |
| `quality` | Selection | `measured`, `estimated`, `manual`; req |
| `source_note` | Char | size=128 |

`UNIQUE(driver_id, day)`. Методы: `_cron_values()` (R-03), `get_series(driver_code, day_from, day_to)` → `{day: value}`.

### M-10 `product.template` — расширение (FR-03)

`td_plate_area_m2` — Float, digits (10,4), default 0.0, «Площа плити, м²/од.», constraint `≥ 0`. В форме продукта — группа «Енергетика» (V-10). Для листовых материалов td_machine_connect поля `td_sheet_length_mm × td_sheet_width_mm` **не** используются (Q-01).

### M-09 `td.energy.alloc` — расширение (FR-12)

`product_id` — Many2one `product.product`, `related="production_id.product_id"`, `store=True`, idx, readonly («Продукт»). Поле пересчитывается при установке для существующих строк (SQL-пакетами 5 000, `post_init_hook` → `hooks._fill_alloc_product`).

### M-08 `td.energy.daily` — суточные факты (FR-04)

`_name = "td.energy.daily"`, `_description = "Енергетика: добовий факт"`, `_log_access = False`, `_order = "day desc, scope, node_id"`, `_inherit = ["td.energy.day.mixin"]`.

| Поле | Тип | Параметры |
|---|---|---|
| `day` | Date | req, idx (Киев) |
| `scope` | Selection | `plant`/«Завод», `node`/«Вузол», `resource`/«Ресурс»; req, idx |
| `resource_id` | Many2one `td.energy.resource` | `plant` и `node` — `el`; `resource` — любой |
| `node_id` | Many2one `td.energy.node` | только `scope='node'`, idx |
| `area_id` | Many2one `td.energy.area` | фиксируется при построении (история не «переезжает» при смене разметки), idx |
| `qty` | Float | digits (16,3): `plant` — потребление завода (Σ фидеров, кВт·ч); `node` — кВт·ч узла; `resource` — количество (импорт для `el`) |
| `cost` | Float | digits (14,2), `cost`: `plant` — стоимость импорта; `node` — стоимость потребления; `resource` — стоимость покупки |
| `co2_kg` | Float | digits (14,2): `resource` — по R-07 W3 (`import`, `supply`); иначе 0 |
| `import_qty`, `export_qty` | Float | `plant`: импорт и экспорт (кВт·ч) |
| `gen_pv_qty`, `gen_chp_qty` | Float | `plant`: генерация СЕС (`model='sun2000'`) и КГУ (`model='tedom'`) |
| `shift1_qty`, `shift2_qty`, `off_qty` | Float | `plant`: потребление (Σ фидеров) по сменам и вне смен (W3 R-21) |
| `cost_s1`, `cost_s2`, `cost_off` | Float | digits (14,2), `cost`: `plant` — стоимость потребления фидеров по сменам (`Σ feeder.cost`) |
| `direct_s1`, `direct_s2`, `direct_off` | Float | `plant`: потребление «прямых» станков по сменам (для распределения площади плит) |
| `plate_s1`, `plate_s2`, `plate_off` | Float | `plant`: площадь плит по сменам (R-14) |
| `minutes` | Float | `node`: Σ `td.energy.alloc.minutes` (`kind='direct'`) за сутки |
| `idle_qty` | Float | `node`: Σ `alloc.kwh` (`kind='idle'`) |
| `quality` | Selection | `ok`, `partial` (доля `missing`-слотов > 10 %); default `ok` |
| `built_at` | Datetime | req |

Индексы: `(day, scope)`, `(day, area_id)`, `(node_id, day)`. `UNIQUE(day, scope, resource_id, node_id)` через частичные индексы в `init()` (NULL в `node_id` для `plant` и `resource`).
Методы: `_td_build_days(days)` (R-02, `api.model`), `action_rebuild(date_from, date_to)` (manager), `_cron_daily()`, `_cron_rotate()`.

### M-04 `td.energy.baseline` — модель базы ISO 50001 (FR-05)

`_name = "td.energy.baseline"`, `_description = "Енергетика: модель бази (EnPB)"`, `_inherit = ["mail.thread"]`, `_order = "state, period_to desc, id desc"`.

| Поле | Тип | Параметры |
|---|---|---|
| `name` | Char | req, compute store: «{resource} · {scope} · {period_from:%Y-%m}…{period_to:%Y-%m}» |
| `resource_id` | Many2one `td.energy.resource` | req, default `resource_el`; допустимы `el`, `gas` |
| `scope` | Selection | `plant`/«Завод», `area`/«Ділянка»; default `plant` |
| `area_id` | Many2one `td.energy.area` | req при `scope='area'` |
| `period_from`, `period_to` | Date | req; `period_to − period_from + 1 ≥ baseline_min_days` (30) |
| `const_per_day` | Float | digits (14,3), «Постійна складова, од./добу» |
| `line_ids` | One2many `td.energy.baseline.line` | 1…3 строки (ограничение) |
| `n_days` | Integer | readonly, число суток в подгонке |
| `r2`, `rmse` | Float | readonly |
| `method` | Selection | `ols`/«Регресія», `manual`/«Вручну»; default `ols` |
| `state` | Selection | `draft`/«Чернетка», `approved`/«Затверджено», `archived`/«В архіві»; default `draft`, tracking |
| `fitted_at`, `approved_at` | Datetime | readonly |
| `approved_by` | Many2one `res.users` | readonly |
| `warning` | Char | readonly: «Від'ємний коефіцієнт {driver}.» и т. п. |
| `company_id` | Many2one `res.company` | req, default `env.company` |
| `note` | Text | |

`M-05 td.energy.baseline.line`: `baseline_id` (req, cascade), `driver_id` (req, restrict), `coef` (Float digits (14,6), «Коефіцієнт, од. на одиницю драйвера»), `sequence`; `UNIQUE(baseline_id, driver_id)`.
Constraints: `_check_lines` (число строк ≤ 3: `ValidationError("Не більше 3 драйверів.")`), `_check_scope` (`area` ⇒ `area_id`), `_check_resource` (`el`/`gas`: «Модель бази підтримується для електрики та газу.»), `_check_unique_approved`: на `(resource, scope, area, company)` не более одной записи `approved`.
Методы: `action_fit()` (R-04; `group_td_energy_manager`; состояния `draft`), `action_approve()` (`group_td_energy_chief`; R-04 п. 7), `action_archive()`, `action_to_draft()`, `expected(day_values)` (`const + Σ coef·value`), `_td_expected_series(day_from, day_to)`.

### M-06 `td.energy.enpi` — EnPI по суткам (FR-06)

`_name = "td.energy.enpi"`, `_log_access = False`, `_order = "day desc, baseline_id"`.

| Поле | Тип | Параметры |
|---|---|---|
| `baseline_id` | Many2one `td.energy.baseline` | req, idx, ondelete=cascade |
| `day` | Date | req, idx |
| `actual` | Float | digits (16,3), req |
| `expected` | Float | digits (16,3) — пусто, если нет значения драйвера |
| `enpi` | Float | digits (8,4), compute store: `actual/expected` при `expected > 0`, иначе пусто |
| `drivers` | Json | `{"plate_m2": 1286.0, …}` |
| `quality` | Selection | `ok`, `no_driver`, `partial` |

`UNIQUE(baseline_id, day)`. Методы: `_cron_enpi()`, `recompute(date_from, date_to, baseline=None)` (manager), `period_totals(baseline, day_from, day_to)` (R-05).

### M-07 `td.energy.budget` — бюджет энергии (FR-07)

`_name = "td.energy.budget"`, `_description = "Енергетика: бюджет"`, `_inherit = ["mail.thread"]`, `_order = "month desc, resource_id"`.

| Поле | Тип | Параметры |
|---|---|---|
| `month` | Date | req, idx, первое число месяца; constraint `day == 1` |
| `resource_id` | Many2one `td.energy.resource` | пусто = «Усі ресурси (вартість енергії)»: Σ ресурсов с `in_energy_cost` |
| `amount_uah` | Float | digits (14,2), req, `cost`, `> 0` |
| `amount_qty` | Float | digits (14,2), опционально, план в единицах ресурса |
| `state` | Selection | `draft`, `approved`; default `draft`, tracking |
| `approved_by`, `approved_at` | Many2one / Datetime | readonly |
| `company_id` | Many2one `res.company` | req, default `env.company` |
| `note` | Char | size=256 |

`UNIQUE(company_id, month, coalesce(resource_id, 0))` — через индекс в `init()`. `action_approve()` — `group_td_energy_chief`. Метод `get_status(month=None, resource_code=None)` (R-06).

### M-12 `td.energy.analytics` — API экрана (AbstractModel; FR-08…FR-15)

`_name = "td.energy.analytics"`, `_description = "Енергетика: дані аналітики"`. Доступ — `_td_check_access()`: `group_td_energy_user` или суперпользователь, иначе `AccessError("Немає доступу до Енергетики.")`; чтение таблиц — через `sudo()`; ключи стоимости без `group_td_energy_cost` **удаляются** из ответа. Методы — API-01…API-09.

### M-13 `td.energy.report.wizard` — отчёты (Transient; FR-16, FR-17)

| Поле | Тип | Параметры |
|---|---|---|
| `kind` | Selection | `management`/«Для керівництва», `shift`/«За зміну»; req, default `management` |
| `period` | Selection | `w`, `m`, `q`, `y`; default `m` (`management`) |
| `shift_date` | Date | default сегодня (Киев) (`shift`) |
| `shift_name` | Char | size=32; пусто — текущая/последняя завершённая смена (R-19) |

`create_and_print(kind, period=None, shift_name=None)` (`api.model`): создаёт запись, возвращает `ir.actions.report` (`report_action`); `action_print()` — то же для открытой формы. Права: `group_td_energy_user` (суммы ₴ — по группе стоимости, R-18).

### M-14 `td.energy.dashboard` — расширение (`_inherit`; FR-17)

Метод `_td_report_action()` (`api.model`) определён в W4 и возвращает `"td_energy_analytics.action_td_energy_shift_report"`. Чтобы кнопка «Звіт за зміну» Пульта (W1 D-01) заработала, `td_energy` должен вызывать этот хук: `capabilities.report = bool(self._td_report_action())`, `meta.report_action = self._td_report_action()`, а `pult.js openReport()` — открывать `meta.report_action` (правка менеджера в коде W1, ARCH §6.0; в W1 сейчас `capabilities.report=False` и жёсткий xml-id `td_energy.action_td_energy_report`, `tools/dashboard.py:216`, `static/src/pult/pult.js:345`). Без правки модуль аналитики работает, кнопка Пульта остаётся скрытой.

### M-15 `res.config.settings` — расширение

Поля `td_energy_analytics_*` с `config_parameter` (разд. 5.1); группа «Аналітика» в блоке `td_energy` (V-14). Валидация: `r2_min ∈ [0, 1]`, `forecast_min_days ≤ forecast_weeks`, `daily_close_h ∈ [0, 12]`.

### M-16 `td.energy.daily.rebuild.wizard` — пересчёт фактов (Transient)

`date_from`, `date_to` (Date, req, диапазон ≤ 400 суток), `action_rebuild()` → `td.energy.daily._td_build_days` и `td.energy.enpi.recompute`; `group_td_energy_manager`.

## 3. Представления и меню

### 3.1 Представления V-01…V-16

| ID | XML-id (`td_energy_analytics.`) | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `action_td_energy_analytics` | `ir.actions.client`, `tag="td_energy_analytics.analytics"`, `name="Аналітика енергетики заводу"`, `context={"td_energy_period": "m"}` | UI-01 |
| V-02 | `view_td_energy_area_list` / `_form`, `action_td_energy_area` | `td.energy.area` | list: `sequence` (handle), `code`, `name`, `color`, `spec_driver_id`, `node_count`, `active`; form: поля + вкладка «Вузли» (`node_ids` list readonly) |
| V-03 | `view_td_energy_driver_list` / `_form`, `action_td_energy_driver` | `td.energy.driver` | поля, вкладка «Значення» (`value_ids` list, редактируемая для `manual`) |
| V-04 | `view_td_energy_driver_value_list` / `_pivot` / `_search`, `action_td_energy_driver_value` | `td.energy.driver.value` | list: `day`, `driver_id`, `value`, `quality`; `quality=manual` редактируется менеджером |
| V-05 | `view_td_energy_baseline_list` / `_form`, `action_td_energy_baseline` | `td.energy.baseline` | статусбар `state`; кнопки: «Розрахувати модель» (`action_fit`, `state=draft`), «Затвердити» (`action_approve`, chief, `invisible="state != 'draft'"`), «В архів», «У чернетку»; поля: `resource_id`, `scope`, `area_id`, `period_from/to`, `method`; блок «Модель»: `const_per_day`, `line_ids` (editable list: `driver_id`, `coef`), `n_days`, `r2`, `rmse`, `warning`; чаттер |
| V-06 | `view_td_energy_enpi_list` / `_graph` / `_pivot` / `_search`, `action_td_energy_enpi` | `td.energy.enpi` | readonly; list: `day`, `baseline_id`, `actual`, `expected`, `enpi` (decoration: `> 1.05` danger, `< 0.95` success); graph: линии `actual`/`expected` по неделям; пункт — «Пересчитати» (`td.energy.daily.rebuild.wizard`) |
| V-07 | `view_td_energy_budget_list` / `_form`, `action_td_energy_budget` | `td.energy.budget` | list: `month`, `resource_id`, `amount_uah` (`cost`), `state`; form: статусбар, «Затвердити» (chief); без группы стоимости суммы скрыты |
| V-08 | `view_td_energy_daily_list` / `_pivot` / `_graph` / `_search`, `action_td_energy_daily` | `td.energy.daily` | readonly; pivot: строки `day`, столбцы `scope`; search: «Сьогодні», «Вчора», «7 днів» (`day.mixin`), `scope`, `area_id`; меню — `group_td_energy_manager` |
| V-09 | `view_td_energy_node_form_area` (наследует `td_energy.view_td_energy_node_form`) | form | поле `area_id` в группе «Облік» |
| V-10 | `view_product_template_form_energy` (наследует `product.product_template_only_form_view`) | form | группа «Енергетика»: `td_plate_area_m2` |
| V-11 | `action_td_energy_daily_rebuild` | `ir.actions.act_window`, wizard M-16 | `target="new"` |
| V-12 | `report_td_energy_management` | `ir.actions.report` | `model="td.energy.report.wizard"`, `report_type="qweb-pdf"`, `report_name="td_energy_analytics.report_management_document"`, `print_report_name="'Енергетика_звіт_%s' % time.strftime('%Y-%m-%d')"` |
| V-13 | `report_td_energy_shift`, `action_td_energy_shift_report` | `ir.actions.report` + `ir.actions.server` | `report_name="td_energy_analytics.report_shift_document"`; серверное действие `action_td_energy_shift_report`: `code = "action = env['td.energy.report.wizard'].create_and_print('shift')"` (его запускает кнопка «Звіт за зміну» Пульта) |
| V-14 | `res_config_settings_view_form_td_energy_analytics` (наследует `td_energy.res_config_settings_view_form_td_energy`) | form | группа «Аналітика»: `td_energy_analytics_daily_close_h`, `…_catchup_days`, `…_forecast_weeks`, `…_forecast_min_days`, `…_r2_min`, `…_baseline_min_days`, `…_refresh_s`, `…_top_equipment`, `…_top_mo` |
| V-15 | `views/menus.xml` | `ir.ui.menu` | таблица 3.3 |
| V-16 | `view_td_energy_alloc_search_product` (наследует поиск `td.energy.alloc`) | search | группировка «Продукт» (`product_id`) |

### 3.2 Клиентские компоненты (OWL) UI-01…UI-10

Всё — `@odoo/owl`, `registry.category("actions").add("td_energy_analytics.analytics", Analytics)`; данные — `orm.call("td.energy.analytics", "get_dashboard", [], {period, dim, parts})`; шина не нужна (обновление раз в `refresh_s` = 300 с и при смене периода); тексты — украинские; каждый интерактивный узел — `<button>` с `aria-label`; состояние — не только цветом.

| ID | Компонент | Содержимое и поведение |
|---|---|---|
| UI-01 | `Analytics` | Шапка: крошки «Енергетика / Аналітика», h1 «Аналітика енергетики заводу», подзаголовок `meta.subtitle`, группа периода `7 днів / 30 днів / квартал / рік` (`role="group"`, `aria-pressed`), кнопка «Звіт для керівництва» (`create_and_print('management', period)` → `action.doAction`). Состояние: `period`, `dim`, `data`, `failed`; смена периода перезагружает `kpis, stack, heatmap, cut, opps`; смена среза — только `cut`; `enpi`/`budget` грузятся один раз |
| UI-02 | `AnKpis` | 7 карточек (`flex: 1 1 190px`): метка, значение 24 px + единица, строка Δ с тоном `good/bad/neutral`; пустое значение — «—» |
| UI-03 | `AnStack` | SVG `viewBox 0 0 880 250`: сетка 4 линии, подписи Y (0, ⅓, ⅔, max), столбцы по `bars[]` (стек по `areas[]`, цвета `areas[].color`), подписи X через `bars[].label`; легенда из `areas[]`; заголовок «Електроенергія за ділянками · {unit}» |
| UI-04 | `AnHeatmap` | сетка `28px + 24 колонки`, 7 строк; ячейка 18 px; цвет по уровню (`#f5f3f5 #e3d5df #c9b0c2 #9a7392 #5a3b52`); `title` «{день} {HH}:00 · {kW} кВт»; легенда «менше … більше · вихідні й ночі — базове навантаження {base_load_kw} кВт» |
| UI-05 | `AnEnpi` | SVG `viewBox 0 0 440 200`: сетка, ось Y (3 метки), две линии: факт (сплошная `#714B67`), ожидание (пунктир `#9ca3af`), подписи «12 тижнів тому» / «цей тиждень»; легенда и строка «EnPI {x} · економія {y} % до бази»; блок бюджета: «Бюджет енергії · {місяць}» с суммой, полосой факта и маркером `month_share_pct`, текст `budget.text` |
| UI-06 | `AnCut` | заголовок «Розріз · {dim_name}», вкладки (`role="tablist"`) Ділянки / Обладнання / Замовлення / Продукти / Зміни; таблица: имя (кнопка деталізації → `action_open_cut`), «Енергія, кВт·год», «Вартість, ₴» (только с `capabilities.cost`), «Частка» (полоса + %), удельное (заголовок `col_spec`), «До бази» (цвет по знаку) |
| UI-07 | `AnOpps` | «Резерви економії» + «У плані: **{plan_sum} ₴/міс** з {all_sum} ₴/міс»; строка: чекбокс (`action_plan_toggle`, с оптимистичным обновлением и откатом при ошибке), заголовок, текст, «{save} ₴/міс», кнопка действия по первому доступному (`runAdviceAction` из `@td_energy/common/advice`; `control` — только при обработчике в `td_energy.advice_handlers`, иначе запасное «Відкрити»); без прав «Енергетика» чекбокс `disabled` |
| UI-08 | `useAnalytics` | хелпер загрузки частей, форматирование (`fmtInt/fmtDec` из `@td_energy/common/format`), nice-ticks на клиенте не считаются (приходят в `ticks`) |
| UI-09 | `td_energy_analytics.scss` | токены цветов участков и тепловой шкалы; адаптив ≥ 360 px (карточки и таблица прокручиваются по горизонтали); печатные стили не нужны |
| UI-10 | `ReportButton` | отдельный компонент кнопки отчёта с индикатором ожидания (отчёт ≤ 15 с), блокировка повторного клика, `notify` об ошибке (`wkhtmltopdf` недоступен — «Не вдалося сформувати PDF.») |

### 3.3 Меню (`views/menus.xml`)

| XML-id (`td_energy_analytics.`) | Название | Родитель | seq | Группы | Действие |
|---|---|---|---|---|---|
| `menu_td_energy_analytics` | Аналітика | `td_energy.menu_td_energy` | 12 | `td_energy.group_td_energy_user` | `action_td_energy_analytics` |
| `menu_td_energy_analytics_config` | Аналітика | `td_energy.menu_td_energy_config` | 60 | `…group_td_energy_manager` | — (раздел) |
| `menu_td_energy_area` | Ділянки | `…_config` (этот раздел) | 10 | manager | `action_td_energy_area` |
| `menu_td_energy_driver` | Драйвери | `…_config` | 20 | manager | `action_td_energy_driver` |
| `menu_td_energy_driver_value` | Значення драйверів | `…_config` | 25 | manager | `action_td_energy_driver_value` |
| `menu_td_energy_baseline` | Моделі бази (ISO 50001) | `…_config` | 30 | manager | `action_td_energy_baseline` |
| `menu_td_energy_enpi` | EnPI за добами | `…_config` | 40 | manager | `action_td_energy_enpi` |
| `menu_td_energy_budget` | Бюджет енергії | `…_config` | 50 | `…group_td_energy_cost` | `action_td_energy_budget` |
| `menu_td_energy_daily` | Добові факти | `…_config` | 60 | manager | `action_td_energy_daily` |
| `menu_td_energy_daily_rebuild` | Перерахувати добові факти | `…_config` | 70 | manager | `action_td_energy_daily_rebuild` |

## 4. Права

### 4.1 `security/ir.model.access.csv` (A) и `security/ir.model.access-report.csv` (B)

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

`-report.csv`: `td.energy.report.wizard` и `td.energy.daily.rebuild.wizard`: первая — `group_td_energy_user` (1,1,1,1), вторая — `group_td_energy_manager` (1,1,1,1) (Transient, права на создание). `td.energy.analytics` — AbstractModel без ACL (контроль в методах). Бюджет читают `group_td_energy_cost` и выше (без стоимости бюджет бессмыслен; у `user` без cost чтения нет). Существующие права `td.energy.alloc` и `td.energy.node` достаточны.

### 4.2 Группы

Новых групп нет. «Енергетик» = `group_td_energy_manager`: подгонка модели, перерасчёт, ввод драйверов `manual`, редактирование бюджета (черновик). «Головний енергетик» = `group_td_energy_chief`: **утверждение** модели базы и бюджета, удаление моделей/бюджетов. Администратор — всё.

### 4.3 Record rules

`td_energy_baseline_rule_company`, `td_energy_budget_rule_company` — домен `['|', ('company_id','=',False), ('company_id','in',company_ids)]`, глобальные. `td.energy.daily` изолируется через узлы (`node_id.company_id`), для `plant`/`resource` — по `td.energy.node` компании через `sudo()` в API (в таблице нет `company_id`; мультикомпания — Q-09).

### 4.4 Защита данных и действий

- Ключи стоимости (`cost_uah`, `save_uah_month`, `plan_sum`, `all_sum`, KPI «Вартість», колонка «Вартість, ₴», суммы бюджета) без `group_td_energy_cost` **удаляются** из ответов API и PDF (AC-51); KPI «Вартість енергії» целиком исключается из списка.
- Утверждение базы и бюджета — только `chief`; подгонка и пересчёт — `manager`; чтение — `user`.
- Отчёты: PDF формируется с правами пользователя; суммы ₴ — только с группой стоимости.
- Записи в устройства нет.

## 5. Данные

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`) — `td.energy_analytics.*`

| Ключ | По умолчанию | Назначение |
|---|---|---|
| `td.energy_analytics.daily_close_h` | `2` | до этого местного часа вчерашние сутки пересчитываются кроном |
| `td.energy_analytics.catchup_days` | `14` | глубина догона пропущенных суток (факты, драйверы, EnPI) |
| `td.energy_analytics.forecast_weeks` | `8` | число недель для «типовых суток» (прогноз бюджета) |
| `td.energy_analytics.forecast_min_days` | `3` | минимум суток одного дня недели для типовых |
| `td.energy_analytics.r2_min` | `0.6` | минимальный R² для утверждения модели `ols` |
| `td.energy_analytics.baseline_min_days` | `30` | минимальная длина периода базы |
| `td.energy_analytics.refresh_s` | `300` | автообновление экрана |
| `td.energy_analytics.top_equipment` | `15` | строк в срезе «Обладнання» |
| `td.energy_analytics.top_mo` | `20` | строк в срезе «Замовлення» |

Используются существующие: `td.energy.read_enabled`, `td.energy.keep_interval_days` (ротация фактов, 400), `td.energy.shift_calendar_id` (смены, W3 R-21), `td.energy_resources.weeks_per_month` (W3).

### 5.2 Участки и карта узлов (`data/td_energy_area.csv`, `data/area_map.csv`; загружает `hooks._load_areas(env)`)

`td_energy_area.csv` (`code,name,sequence,color,spec_driver`): `CUT,Розкрій,10,#5a3b52,plate_m2`; `EDGE,Крайка,20,#8a6383,plate_m2`; `DRILL,Присадка ЧПК,30,#b79ab0,plate_m2`; `FACADE,Фасади МДФ,40,#b45309,plate_m2`; `ASSY,Збирання й пакування,50,#f59e0b,plate_m2`; `AIR_DUST,Аспірація й повітря,60,#0369a1,plate_m2`; `HVAC,Вентиляція й опалення,70,#38bdf8,plate_m2`; `LIGHT_OFFICE,Освітлення й офіс,80,#9ca3af,` (без драйвера — удельное «—»). Цвета и названия — из `Analytics.dc.html` (`catDefs`).

`area_map.csv` (`node_code,area_code`; 49 узлов `kind='consumer'`, `data/energy_nodes.csv` `td_energy`): `CUT` — `SAW-1, SAW-2, SAW-3, SLIDE-1, VSAW-1, NEST-1, GANTRY-1, SORT-1` (8); `EDGE` — `EDGE-1, EDGE-2, EDGE-3` (3); `DRILL` — `CNC-1, CNC-2, CNC-3, CNC-4, BORE-1, DOWEL-1` (6); `FACADE` — `SAND-1, AUTOSPRAY-1, UV-1, PRESS-1, SPRAY-1, DRY-1, GLUE-1` (7); `ASSY` — `HINGE-1, ASMLINE-1, ASM-1…ASM-6, PACK-1, PACK-2, BOX-1, PACKLINE-1` (12); `AIR_DUST` — `DUST-1, COMPRESSOR` (2); `HVAC` — `RV-ALL, AHU-1, BOILER, EF-ELEC, EF-CMP, EF-CHG` (6); `LIGHT_OFFICE` — `LP-1, LP-2, LP-3, OFFICE, CHARGING` (5). Итого 8 + 3 + 6 + 7 + 12 + 2 + 6 + 5 = 49. Отнесение — решение автора (A-02): макет называет категории, но не перечисляет узлы; менеджер может скорректировать CSV.
`_assign_areas(env)`: `area_id` проставляется **только** если пуст (правки пользователя не перезаписываются); отсутствующий код узла — пропуск с `_logger.warning`.

### 5.3 Данные драйверов (`data/td_energy_driver_data.xml`, `noupdate="1"`)

`driver_plate_m2` (`code='plate_m2'`, `source_kind='mrp_area'`, `uom='м²'`), `driver_hdd` (`code='hdd'`, `source_kind='weather_hdd'`, `uom='°C·доба'`, `base_temp_c=18`, `temp_signal_code='ventilation/totals/outdoor_c'`).

### 5.4 `post_init_hook` и миграция `19.0.1.0.0`

Шаги (идемпотентные; миграция вызывает те же функции):
1. `_load_areas(env)` (5.2): 8 участков;
2. `_assign_areas(env)`: 49 узлов;
3. `_fill_alloc_product(env)`: `product_id` у существующих строк `td.energy.alloc` (SQL, пакеты 5 000);
4. драйверы (XML);
5. параметры (5.1), крон-записи (разд. 6).
Ожидаемо на демо-БД (`f3d_full2` после W1+W3): участков 8; узлов с `area_id` 49; драйверов 2; `td.energy.daily` 0 до первого прогона крона/сида; параметров +9. Установка **не** создаёт модель базы и бюджет (их утверждает человек; демо-сид R-20 — отдельно).

### 5.5 `uninstall_hook`

Удаляет собственные крон-записи и параметры. Таблицы модуля (участки, драйверы, факты, базы, EnPI, бюджеты) удаляются штатно Odoo; электрические данные, `alloc` и узлы остаются (поле `area_id` исчезает вместе с модулем). `neutralize.sql`: отключить 4 крона.

## 6. Крон-задачи и фоновые процессы

Все — `user_id=base.user_root`, `try/except` с `_logger.exception`; при `td.energy.read_enabled = False` не действуют.

| XML-id | Название | Интервал | Метод | За один прогон | Лимит |
|---|---|---|---|---|---|
| `cron_td_energy_daily` | Енергетика: добові факти | 15 мин | `td.energy.daily._cron_daily` | пересчёт сегодняшних суток; вчерашних — пока локальный час < `daily_close_h` или нет строки `plant`; догон до `catchup_days` суток без строки `plant` (R-02) | ≤ 3 с на сутки, ≤ 20 с суммарно |
| `cron_td_energy_drivers` | Енергетика: драйвери | 1 сут, `nextcall` 02:10 Киев | `td.energy.driver._cron_values` | значения драйверов за вчера и пропуски последних `catchup_days` (R-03) | ≤ 10 с |
| `cron_td_energy_enpi` | Енергетика: EnPI | 1 сут, `nextcall` 02:30 Киев | `td.energy.enpi._cron_enpi` | EnPI за вчера и пропуски по каждой утверждённой базе (R-05) | ≤ 10 с |
| `cron_td_energy_analytics_rotate` | Енергетика: ротація аналітики | 1 сут, `nextcall` 03:20 Киев | `td.energy.daily._cron_rotate` | удалить `daily`, `enpi`, `driver.value` старше `td.energy.keep_interval_days` | ≤ 30 с |

## 7. HTTP/JSON API

Новых HTTP-маршрутов нет: вызовы — ORM-RPC от имени пользователя. Если не указано иное, методы — `@api.model`.

| ID | Сигнатура | Вход → выход | Ошибки |
|---|---|---|---|
| API-01 | `td.energy.analytics.get_dashboard(period="m", dim="area", parts=None)` | `period ∈ {w, m, q, y}`, `dim ∈ {area, eq, mo, prod, shift}`, `parts` ⊂ `{"kpis","stack","heatmap","enpi","budget","cut","opps"}` или `None` → JSON «Аналітика» (ниже) | неизвестный период/срез → `UserError("Невідомий період: %s.")` / `UserError("Невідомий розріз: %s.")`; без группы → `AccessError` |
| API-02 | `td.energy.analytics.get_kpis(period)` | → `list[kpi]` (R-07) | как API-01 |
| API-03 | `td.energy.analytics.get_stack(period)` | → `stack` (R-08) | |
| API-04 | `td.energy.analytics.get_heatmap(period)` | → `heatmap` (R-09) | |
| API-05 | `td.energy.analytics.get_enpi()` | → `enpi`: 12 недель, EnPI, экономия | |
| API-06 | `td.energy.analytics.get_budget(month=None)` | `month` — `YYYY-MM`, по умолчанию текущий → `budget` или `null` | |
| API-07 | `td.energy.analytics.get_cut(dim, period)` | → `cut` (R-10…R-15) | |
| API-08 | `td.energy.analytics.action_open_cut(dim, key, period)` | → `ir.actions.act_window` (R-16) | `UserError("Невідомий ключ: %s.")` |
| API-09 | `td.energy.analytics.get_opportunities()` | → `{"items": [...], "plan_sum", "all_sum", "plan_count", "open_count"}` — обёртка над W3 API-02, API-06 (контракт C-01) | без модуля W3 нельзя (жёсткая зависимость) |
| API-10 | `td.energy.baseline.action_fit()` / `action_approve()` / `action_archive()` (на записи) | → `True` | `UserError` (R-04), `AccessError` |
| API-11 | `td.energy.budget.action_approve()`, `get_status(month=None, resource_code=None)` | → `True` / `dict` (R-06) | `AccessError`, `UserError` |
| API-12 | `td.energy.report.wizard.create_and_print(kind, period=None, shift_name=None)` | → `ir.actions.report` (dict) | `AccessError`, `UserError("Невідомий вид звіту: %s.")` |
| API-13 | `td.energy.daily._td_build_days(days)` / `action_rebuild(date_from, date_to)` | → `{"days": n, "rows": n, "seconds": f}` | `AccessError`; диапазон > 400 → `UserError("Не більше 400 діб.")` |
| API-14 | `td.energy.analytics._td_seed_demo(days=400, seed=20261018, purge=False, with_mo=True, with_baseline=True, with_budget=True)` | → статистика R-20 (только `env.is_superuser()` или `td_factory3d.group_td_admin`) | `AccessError("Генерувати демо-дані може лише адміністратор.")` |
| API-15 | `td.energy.driver.value.get_series(driver_code, day_from, day_to)` | → `{iso_day: value}` | |

### Ответ API-01 (период `m`, срез `area`; значения — пример на основе макета, 17.10)

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
            "areas": [{"code": "CUT", "name": "Розкрій", "color": "#5a3b52"}, "…8 участков…"],
            "bars": [{"key": "2026-09-18", "label": "18", "total": 7200, "values": {"CUT": 1008, "EDGE": 864, "…": 0}}, "…30 столбцов…"]},
  "heatmap": {"days": ["пн", "вт", "ср", "чт", "пт", "сб", "нд"], "cells": [[210.0, "…24 значения (кВт) или null…"], "…7 строк…"],
              "max_ref": 700, "levels": 5, "base_load_kw": 210},
  "enpi": {"weeks": [{"key": "2026-10-17", "label": "цей тиждень", "expected_mwh": 49.64, "actual_mwh": 48.15}, "…12 недель, по возрастанию даты…"],
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

Правила формы: части отсутствуют, если не запрошены (`parts`); часть, упавшая с ошибкой, возвращает `{"error": "…"}` (остальные не ломаются); `kpis[].delta_pct`/`note` — `null`/«—» без базы; `budget = null` без утверждённого бюджета на месяц; ключи ₴ — только с группой стоимости (иначе отсутствуют; KPI `cost` исключается); `cut.rows[].bar` — относительная длина полосы (`kwh / max kwh`); `enpi.weeks` — 12 скользящих недель по 7 суток, заканчивающихся сегодня; `heatmap.cells[i][h]` — кВт; размер ответа ≤ 60 КБ (период `y`).

## 8. Сервисная часть

Отсутствует (эмулятор и сборщик не меняются). Серверное требование: системный `wkhtmltopdf` (в составе окружения Odoo) для PDF; без него AC-45 выполняется на стенде, юнит-проверка отчёта идёт по HTML (`_render_qweb_html`).

## 9. Алгоритмы и правила

Общие обозначения: `today` — киевская дата сейчас; `daily` — таблица `td.energy.daily`; «потребление завода» = `Σ kwh` строк `td.energy.interval` с `role='feeder'`; «импорт» = `Σ kwh` вводов (`role='incomer'`); цена и CO₂ — по W3 (`td.energy.usage`, R-07 W3). Округления и форматы — R-21.

### R-01 Периоды и корзины (FR-08)

| Период | Окно (включительно) | Корзины | Подписи |
|---|---|---|---|
| `w` | `[today−6, today]` | 7 дней | сокращения дня недели фактической даты: пн, вт, ср, чт, пт, сб, нд |
| `m` | `[today−29, today]` | 30 дней | номер дня; показывается каждая 5-я корзина (индексы 0, 5, 10…), остальные — `""` |
| `q` | `[today−90, today]` (91 день) | 13 скользящих недель `[today−6−7·i, today−7·i]`, `i = 12…0` (по возрастанию) | «т1»…«т13»; показывается каждая 2-я (индексы 0, 2, 4…) |
| `y` | `[1-е число месяца (today) − 11 мес., today]` | 12 календарных месяцев, последний неполный | січ, лют, бер, кві, тра, чер, лип, сер, вер, жов, лис, гру |

Единица оси: `w`, `m` — «кВт·год за день»; `q` — «кВт·год за тиждень»; `y` — «кВт·год за місяць». Пример (`today = 2026-10-17`): `m` = 2026-09-18…2026-10-17; `q` начинается 2026-07-19; `y` — 2025-11-01…2026-10-17.

### R-02 Суточные факты `td.energy.daily` (FR-04)

`_td_build_days(days)` для каждых киевских суток `D` (`[d0, d1)` UTC, `dates.local_day_bounds`):
1. **Строка `plant`** (`resource = el`): один SQL по `td_energy_interval` за `[d0, d1)` и ролям `incomer`, `feeder`, `generation`:
   `qty = Σ kwh (feeder)`; `import_qty = Σ kwh (incomer)`; `export_qty = Σ kwh_export (incomer)`; `cost = Σ cost (incomer)`; `gen_pv_qty = Σ kwh` счётчиков `generation` с `model='sun2000'`; `gen_chp_qty` — `model='tedom'`; `quality='partial'`, если доля слотов фидеров с `quality='missing'` > 10 %.
2. **Смены (R-21 W3):** по каждой строке фидеров за сутки — смена по **началу** слота (`shift_of(local(ts_start))`); смены суток упорядочены по началу: первая → `shift1`, вторая и далее → `shift2`, вне смен → `off`. Заполняются `shift1_qty/shift2_qty/off_qty` и `cost_s1/cost_s2/cost_off` (`Σ feeder.cost`); аналогично `direct_s1/direct_s2/direct_off` — по строкам `role='consumer'` узлов с `alloc_role='direct'`.
3. **Площадь плит по сменам:** `plate = значение драйвера plate_m2 за D` (0, если строки нет); `plate_sN = plate × direct_sN / Σ direct`; при `Σ direct = 0` всё относится к `plate_s1` (A-12).
4. **Строки `node`** (`resource = el`): `qty = Σ kwh`, `cost = Σ cost` по `role='consumer'` каждого узла; `area_id` = текущее `node.area_id` **на момент построения**; `minutes = Σ alloc.minutes` (`kind='direct'`) и `idle_qty = Σ alloc.kwh` (`kind='idle'`) по `td.energy.alloc` за `D` и узлу.
5. **Строки `resource`:** из `td.energy.usage` (W3) за `D`: для каждого активного ресурса — `qty`, `cost`, `co2_kg` по потокам `import` (`el`) и `supply` (остальные); производные (`heat`, `air`) входят со своей стоимостью (в «стоимость энергии» не суммируются — флаг `in_energy_cost`).
6. Запись: `DELETE … WHERE day = D` + `INSERT` в одной транзакции; `built_at = now`. Идемпотентно.
**Крон `_cron_daily` (15 мин):** всегда пересчитывает сегодняшние сутки; вчерашние — пока местный час `< daily_close_h` или у них нет строки `plant`; догон — сутки последних `catchup_days` без строки `plant`. **Ротация** — `td.energy.keep_interval_days`.
**Контрольное тождество:** `plant.qty = Σ feeder kwh` за сутки (допуск 0,001); `Σ resource(el).qty = import_qty`.

### R-03 Драйверы (FR-02)

`_cron_values` (02:10 Киев): сутки = вчера + пропуски последних `catchup_days`; для каждого активного драйвера:
- **`mrp_area`** (`plate_m2`): если ни у одного продукта нет `td_plate_area_m2 > 0` — строка не создаётся. Иначе `value = Σ (stock_move.quantity × product_template.td_plate_area_m2)` по движениям `stock.move` с `production_id IS NOT NULL` (готовая продукция МО), `state='done'`, `date ∈ [d0, d1)` (количество — в ЕИ продукта; `Date`-ограничение по киевским суткам); `quality='estimated'`, `source_note='MRP'`; нулевое значение допустимо.
- **`weather_hdd`** (`hdd`): `T_mean` = среднее `v_avg` часовых агрегатов `td.reading.hour` сигнала `temp_signal_code` за сутки (нужно ≥ 18 часов); иначе — среднее сырых `td.reading` (≥ 50 показаний); иначе строка не создаётся. `hdd = max(0, base_temp_c − T_mean)`, `quality='measured'`.
- **`manual`** — значения вводит `group_td_energy_manager`.
Пример: 3 движения (10 × 3,1 + 5 × 8,4 + 20 × 1,0) → `plate_m2 = 31 + 42 + 20 = 93,0`; `T_mean = 7,0`, база 18 → `hdd = 11,0`.

### R-04 Модель базы: регрессия и утверждение (FR-05)

`action_fit()` (состояние `draft`, `method='ols'`):
1. **Ряд `y`:** по суткам периода — `el/plant`: `daily.plant.qty`; `el/area`: `Σ daily.node.qty` участка; `gas/plant`: `daily.resource(gas).qty`. Берутся сутки со строкой `daily` (`quality='ok'`) и значениями **всех** драйверов модели (`td.energy.driver.value`).
2. **Размер выборки:** `n_min = max(baseline_min_days, 10·(k+1))`, где `k` — число драйверов; `n < n_min` → `UserError("Замало даних для моделі бази: потрібно ≥ %s діб, є %s.")`.
3. **Решение:** нормальные уравнения `(XᵀX)β = Xᵀy`, `X = [1, x₁…x_k]`, метод Гаусса с частичным выбором главного элемента (чистый Python, без numpy; `tools/ols.py`); ведущий элемент по модулю `< 1e-9·scale` → `UserError("Драйвери лінійно залежні або сталі.")`; `k = 0` → `β₀ = mean(y)`.
4. **Метрики:** `ŷ = Xβ`; `SSE = Σ(y−ŷ)²`; `SST = Σ(y−ȳ)²`; `r2 = 1 − SSE/SST` (`SST = 0` → 0); `rmse = √(SSE/n)`; `const_per_day = β₀`; `line_ids` заменяются на `(driver, β_i)`; `n_days`, `fitted_at`.
5. **Предупреждения (`warning`):** любой `β_i < 0` или `β₀ < 0` — «Від'ємний коефіцієнт {…}.»; `r2 < r2_min` — «R² {r2} нижче порогу {r2_min}.»
6. `expected(day) = const_per_day + Σ coef_i · x_i(day)`.
7. **Утверждение** (`action_approve`, `group_td_energy_chief`, состояние `draft`): при `method='ols'` — `r2 ≥ r2_min` и все коэффициенты `≥ 0`, иначе `UserError("Модель не може бути затверджена: %s.")`; предыдущая `approved` той же пары `(resource, scope, area, company)` → `archived`; `approved_by/at`; затем `td.energy.enpi.recompute(period_from, yesterday)`.
Пример: 30 суток, `x_i = 800 + 20·i`, `y_i = 1820 + 4,1·x_i` → `β₀ = 1820,000 ± 0,001`, `β₁ = 4,100 ± 1e-6`, `r2 = 1`, `rmse = 0`; два драйвера: `y = 1500 + 4,0·plate + 35·hdd` восстанавливается; драйверы `plate` и `2·plate` → `UserError`.

### R-05 EnPI (FR-06)

1. `_cron_enpi` (02:30 Киев): для каждой утверждённой базы — вчера и пропуски последних `catchup_days`: `actual` — по тому же определению, что `y` в R-04 п. 1; `drivers` — `{code: value}` из `driver.value`; если нет значения хотя бы одного драйвера — строка с `expected = NULL`, `quality='no_driver'`; иначе `expected = baseline.expected(drivers)`, `enpi = actual/expected`; `quality='partial'` при `daily.quality='partial'`.
2. **Итоги периода** `period_totals(baseline, d_from, d_to)`: по строкам с `expected` и `quality != 'no_driver'`: `Σa`, `Σe`, `enpi = Σa/Σe`, `saving_pct = (1 − enpi)·100`, `saving_qty = Σe − Σa`, `coverage = n/(число суток окна)`; `coverage < 0,5` → `enpi = null`. Стоимость экономии (`cost`): `saving_qty × avg_price`, где `avg_price` = `Σ plant.cost / Σ plant.import_qty` за период (электричество) или `Σ cost/Σ qty` ресурса `gas`.
3. **Недельный ряд** (`enpi.weeks`): 12 скользящих недель (как `q` в R-01, 12 корзин), для каждой `expected_mwh = Σe/1000`, `actual_mwh = Σa/1000`; ось `y_min = floor5(0,95·min)`, `y_max = ceil5(1,05·max)` (кратно 5 МВт·ч); метки `label` — «12 тижнів тому» (первая) и «цей тиждень» (последняя), остальные `""`. Недельный EnPI-блок — по утверждённой базе `el/plant`; нет её — `enpi = null`.
Пример: 7 суток по 1 286 м² плит: `expected = 7·1820 + 4,1·9000 = 49 640 кВт·ч = 49,64 МВт·ч`; `actual = 48 150` → `enpi = 0,9700`, `saving_pct = 3,0`, `saving_qty = 1 490`.

### R-06 Бюджет и прогноз (FR-07)

`get_status(month, resource_code)` — только по **утверждённому** бюджету (`state='approved'`), иначе `null`.
1. `fact = Σ daily.resource.cost` за `[1-е число, today]` по ресурсам с `in_energy_cost` (или по одному ресурсу при бюджете на ресурс); `fact_pct = round(fact/plan·100)`; `month_share = round(день_месяца / число_дней_месяца · 100)` (сутки считаются целиком; D-59).
2. **Типовые сутки:** `typical[w]`, `w = 0…6` — среднее `daily.resource.cost` (те же ресурсы) за последние `forecast_weeks` недель до `today` (без сегодняшних суток) для дня недели `w`; если образцов `< forecast_min_days` — среднее всех суток этого окна; нет данных — `forecast = null`.
3. `forecast = Σ_{d < today} actual(d) + max(actual(today), typical[wd(today)]) + Σ_{d > today в месяце} typical[wd(d)]`; `delta_pct = round((forecast − plan)/plan·100)`.
4. `text`: «Факт на {ДД.ММ} — {fact} ₴ ({fact_pct} % при {month_share} % місяця) · прогноз {forecast} ₴, на {|delta|} % {нижче|вище} бюджету» (при `delta = 0` — «… прогноз {forecast} ₴, відповідає бюджету»).
Пример (`today = 2026-10-17`, суббота): `факт 1–16 = 1 036 000`, сегодня `60 000`; типовые сутки: пн–пт 62 000, сб 60 000, нд 38 000; остаток месяца: 5 + 5 будних, 2 субботы (24, 31 окт.), 2 воскресенья (18, 25 окт.) → `forecast = 1 036 000 + max(60 000, 60 000) + 2·38 000 + 10·62 000 + 2·60 000 = 1 912 000`; `fact = 1 096 000`, `plan = 1 950 000` → `fact_pct = 56`, `month_share = 17/31 = 55`, `delta = −1,95 → −2` ⇒ «Факт на 17.10 — 1 096 000 ₴ (56 % при 55 % місяця) · прогноз 1 912 000 ₴, на 2 % нижче бюджету».

### R-07 KPI (FR-09)

Окно — R-01; данные — `daily`; «база» — утверждённая модель `el/plant` (и `gas/plant` для газа). Без базы `delta_pct = null`, `note` «База не задана».

| id | value | delta_pct / note | tone |
|---|---|---|---|
| `el` «Електроенергія» | `Σ plant.qty` (кВт·год) | `(Σa/Σe − 1)·100` по `enpi`-строкам окна → note «{±N} % до бази» (знак U+2212 для минуса) | `good` при `delta ≤ −1`, `bad` при `delta ≥ +1`, иначе `neutral` |
| `gas` «Газ» | `Σ resource(gas).qty` (м³) | тот же расчёт по базе `gas/plant` (драйвер HDD); к note добавляется « · похолодання», если `avg_hdd(окно) > 1,10·avg_hdd(окно базы)`, и « · тепліше», если `< 0,90·…` | как `el` |
| `cost` «Вартість енергії» (`cost`-группа) | `Σ resource.cost` ресурсов с `in_energy_cost` | note «{name₁} {share₁} % · {name₂} {share₂} %», `name` в нижнем регистре; `delta_pct = null` | `neutral` |
| `spec` «Питома енергоємність» | `Σ plant.qty / Σ plate_m2` за сутки окна с `plate > 0` (кВт·год/м²) | `base = Σ y/Σ plate` за период базы; `delta = (value/base − 1)·100`; note «база {base} · {±N} %» | `good` при `delta < 0` |
| `cogs` «Енергія в собівартості» | `100·Σ td_energy_cost / Σ value` по МО с `date_finished` в окне и `state='done'` (`value` — `stock.move.value` готовых движений МО) | note «база {base} %» — то же отношение в периоде базы; знаменатель 0 — `value = null` | `good` при `value ≤ base` |
| `selfgen` «Власна генерація» | `100·(Σ(gen_pv_qty+gen_chp_qty) − Σ export_qty)/Σ plant.qty` | note «СЕС {Σ gen_pv_qty} кВт·год» | `good` |
| `co2` «Викиди CO₂» | `Σ resource.co2_kg / 1000` (т): электричество — по импорту | note «мережа {el} т · газ {gas} т за період» | `neutral` |

Пример (30 суток, фикстура): `Σa = 186 400`, `Σe = 198 298` → `delta = −6,0`; газ `18 400` при ожидании `18 039` → `+2,0`, `avg_hdd` окна 9,1 против 7,9 базы (+15 %) → «похолодання»; `cost = 1 569 600 + 368 280 = 1 937 880` (81 % / 19 %); `spec = 186 400/38 400 = 4,854` (4,85), база `5,16` → `−5,9 %` («база 5,16 · −6 %»); `cogs = 68 000/1 000 000 = 6,8 %`; `selfgen = (41 000 − 7 440)/186 400 = 18,0 %`; `co2`: импорт `152 840 × 0,37 = 56 551 кг` (57 т), газ `18 400 × 1,96 = 36 064 кг` (36 т), `value = 93`.

### R-08 Столбцы по участкам (FR-10)

1. Корзины R-01; для каждой — `Σ daily.node.qty` по `area_id` (`area.code`); узлы без участка суммируются в серый сегмент `NONE` («Без ділянки», `#d1d5db`), если сумма > 0.
2. `bars[].total = Σ values`; порядок серий — `area.sequence`.
3. `y_max = round(1,08 · max(total))`, `ticks = [round(y_max/3), round(2·y_max/3), y_max]` (как в макете: `max · 1,08`). Для `w`, `m` — на сутки, `q` — на неделю, `y` — на месяц.
4. Информативно: `meta.data_quality.stack_gap_pct = (Σ plant.qty − Σ всех сегментов)/Σ plant.qty · 100` (на демо ≤ 3 %).
Пример: максимум столбца 7 500 → `y_max = 8 100`, `ticks = [2 700, 5 400, 8 100]`.

### R-09 Теплокарта «година × день тижня» (FR-11)

1. SQL по `td_energy_interval`: `role='feeder'`, `day ∈ окно`, `quality != 'missing'`; группировка `EXTRACT(ISODOW FROM day)` (1 = пн) и `hour_local`: `Σ kwh`, `count(DISTINCT day)`.
2. Ячейка: `kW = Σ kwh / count(DISTINCT day)` (кВт·ч за один час = средний кВт); нет данных — `null`.
3. `max_ref = ceil50(max(cell))`, `levels = 5`; клиентский уровень `lvl = min(4, floor(v / max_ref · 5))`; `base_load_kw = round5(min(cell))`.
Пример: четыре понедельника с кВт·ч за 12:00 = 400, 410, 390, 400 → ячейка `[пн][12] = 400`.

### R-10 Срезы: общие правила (FR-12, FR-13)

- Строка: `{key, name, kwh, cost_uah (cost), share_pct, bar, spec, spec_text, delta_pct}`; `share_pct = round(kwh/Σkwh·100)` (Σ — по строкам среза, включая «Інші»); `bar = kwh / max(kwh)`; сортировка по `kwh` убыв.
- Удельный показатель — деление; знаменатель `0` или `null` → `spec = null`, `spec_text = "—"`; исключений нет.
- «Інші» — суммарная строка за пределами лимита (`top_equipment`, `top_mo`), без удельного.
- Заголовки: `area` — «Ділянка» / «кВт·год/м²»; `eq` — «Обладнання» / «кВт·год/мотогод»; `mo` — «Замовлення» / «кВт·год/шт» (если все МО в одной ЕИ — «кВт·год/{ЕИ}»); `prod` — «Продукт» / «кВт·год/од.»; `shift` — «Зміна» / «кВт·год/м²».

### R-11 Срез «Ділянки»

`kwh = Σ daily.node.qty`, `cost = Σ daily.node.cost` по `area_id` за окно; `spec = kwh / Σ plate_m2(окно)` для участков с `spec_driver_id` (`plate_m2`), иначе `null`. Строка «Без ділянки» — при ненулевой сумме. Пример: `CUT: 26 100 / 38 400 = 0,68`; `LIGHT_OFFICE` — «—».

### R-12 Срез «Обладнання»

По узлам `kind='consumer'`: `kwh`, `cost` — из `daily.node`; `hours = Σ minutes / 60`; `spec = kwh / hours` при `hours ≥ 1`, иначе `null` (общие узлы без нарядов: `RV-ALL`, `DUST-1`, `COMPRESSOR`). Имя — «{code} · {name}»; лимит `top_equipment` + «Інші». Пример: `SAW-3: 7 400 кВт·год`, `15 300 мин = 255 ч` → `7 400/255 = 29,0 кВт·год/мотогод`.

### R-13 Срезы «Замовлення» и «Продукти»

Из `td.energy.alloc` за окно (`day`) с `production_id`: **МО** — `kwh = Σ kwh`, `cost = Σ cost`, `qty = production.qty_produced or product_qty`, `spec = kwh/qty`; имя «{mo.name} · {product} × {qty:g}»; лимит `top_mo`. **Продукты** — группировка по `alloc.product_id`: `kwh`, `cost`; `spec = Σ kwh / Σ qty` **различных** МО продукта в окне (МО, пересекающие границу окна, учитываются полностью — допущение A-14). Пример: `WH/MO/00391`, `kwh 2 470`, `qty 60` → `41,17`.

### R-14 Срез «Зміни»

Три строки из `daily.plant`: «{Зміна 1} · {HH:MM}–{HH:MM}», «{Зміна 2} · …», «Ночі й вихідні · без виробництва» (названия и время — R-21 W3). `kwh = Σ shift1_qty / shift2_qty / off_qty`, `cost = Σ cost_s1 / cost_s2 / cost_off`; `spec` смен — `kwh / Σ plate_s1 (plate_s2)`; для «Ночі й вихідні» `spec_text = "база {avg_kw} кВт"`, `avg_kw = off_qty / off_hours` (`off_hours` — число часов окна вне смен по календарю).

### R-15 «До бази» (FR-24, D-60)

Окно базы `Wb = [baseline.period_from, baseline.period_to]` (утверждённая `el/plant`); для строки с ключом `K`:
- `area`, `shift` (смены 1 и 2): `spec_base` — то же отношение (`kwh/Σ plate`) за `Wb` для того же ключа;
- `eq`: `kwh/мотогод` за `Wb`; `prod`: `Σ kwh/Σ qty` продукта за `Wb`; `mo`: сравнение со `spec` **продукта** МО за `Wb`;
- «Ночі й вихідні»: `avg_kw` за `Wb`.
`delta_pct = (spec_now/spec_base − 1)·100`, округление до целого; нет базы или данных в `Wb` → `null` («—»). Агрегаты окна базы считаются один раз на запрос.
Пример: `CUT`: `spec_now = 0,68`, `spec_base = 0,7083` → `−4 %`.

### R-16 Деталізація (FR-14)

`action_open_cut(dim, key, period)` → `ir.actions.act_window` (список + сводная + график) с доменом по окну `[date_from, date_to]` (поле `day`):
- `area` — `td.energy.interval`, `[('role','=','consumer'), ('node_id.area_id.code','=',key)]`, группировка `day`/`node_id`;
- `eq` — `td.energy.interval`, `[('role','=','consumer'), ('node_id.code','=',key)]`;
- `mo` — `td.energy.alloc`, `[('production_id.name','=',key)]` (ключ среза — имя МО);
- `prod` — `td.energy.alloc`, `[('product_id','=',int(key))]`;
- `shift` — `td.energy.interval`, `[('role','=','feeder')]`, группировка `hour_local` (интервалы периода, не отфильтрованные по смене — D-65).
`key = "OTHER"` («Інші») — `UserError("Невідомий ключ: OTHER.")`. Поля стоимости скрыты `groups` модели.

### R-17 Резервы и чек-лист «у плані» (FR-15)

`get_opportunities()` = `td.energy.opportunity.get_list(None, ("open",))` (≤ 20, W3 API-02) + `get_plan_summary()` (W3 API-06). Экран показывает «У плані: {plan_sum} ₴/міс з {all_sum} ₴/міс» (`plan_sum` — по `in_plan`); изменение флага — `action_plan_toggle` W3 (право «Енергетик»); действия — по контракту C-32 (W1/W3); W4 собственного состояния не хранит. Без группы стоимости суммы и `save_uah_month` отсутствуют, строки показываются без ₴.

### R-18 Отчёт «Звіт для керівництва» (FR-16)

`report.td_energy_analytics.report_management_document._get_report_values(docids, data)`: из записи мастера берёт `period` и вызывает `get_dashboard(period, "area", parts=[kpis, stack, enpi, budget, cut, opps])` и `get_cut("eq", period)` (топ-5).
Структура (A4, портрет, поля 12 мм, ≤ 6 страниц, без внешних ресурсов):
1. Заголовок: «Звіт для керівництва · Енергетика», компания, период (даты), дата и время формирования (Киев), автор (пользователь).
2. «Підсумки періоду» — таблица 7 KPI (значение, единица, Δ/примечание).
3. «EnPI проти бази (ISO 50001)» — SVG-линии 12 недель (факт/ожидание), строка «EnPI {x} · економія {y} %», параметры модели (константа, коэффициенты, R², период базы).
4. «Бюджет енергії · {місяць}» — план/факт/прогноз/процент (только с группой стоимости).
5. «Енергія за ділянками» — таблица: участок, кВт·год, ₴ (cost), частка, кВт·год/м², до бази.
6. «Найбільші споживачі» — топ-5 оборудования: кВт·год, ₴, кВт·год/мотогод.
7. «Резерви економії» — таблица «У плані» / «Інші» с суммой ₴/міс (cost) и действиями текстом.
8. Примечания: число суток с `partial`-качеством, модель базы не утверждена и т. п.
Колонки/блоки с ₴ — только при `group_td_energy_cost`. Время формирования ≤ 15 с (`wkhtmltopdf`).

### R-19 Отчёт «Звіт за зміну» (FR-17)

`_td_pick_shift(date, name)`: если `name` задано — окно этой смены в `date`; иначе, если сейчас внутри смены (R-21 W3) — текущая (с начала до `now`), иначе последняя завершившаяся сегодня (при её отсутствии — вчера). Содержимое (1 страница A4): шапка (смена, интервал, автор); энергия `Σ feeder kwh` и `Σ incomer kwh` за окно, пик (макс. 15-мин `kwh·4` фидеров), вартість (`cost`), отклонение от «типовой» смены — среднее `Σ feeder kwh` последних 4 смен с тем же названием (`±N %`); события `td.energy.event` окна (число по уровням и ≤ 5 последних: время, название, состояние); плановые отключения `td.energy.outage.plan`, пересекающие окно (название, статус); обходы `td.energy.round` окна (если модуль `td_energy_mobile` установлен: название, исполнитель, `done/total`, статус); три крупнейших открытых резерва (cost).
Серверное действие `action_td_energy_shift_report` возвращает `report_action` — его открывает кнопка Пульта.

### R-20 Демо-сид (`_td_seed_demo`; FR-21)

Назначение: наполнить стенд так, чтобы экран и PDF «Аналітика» были осмысленными. **Предусловия:** электрический `_td_backfill(days ≥ days)` (W1 R-36) выполнен; при `with_baseline` и газе — ресурсный backfill W3 (иначе газовая база пропускается); пользователь — администратор.
1. Узлы привязаны к участкам (`_assign_areas`).
2. Продукты (если нет по `default_code`): `DEMO-ENR-1…5` — «Шафа-купе 2000» (3,1 м²/од.), «Кухня «Модерн» (комплект)» (8,4), «Фасад МДФ «Лофт», м²» (1,0), «Тумба ТВ-1600» (1,7), «Стіл письмовий» (1,2); категория — по умолчанию.
3. Для каждых суток `D`: `act(D) = max(0, E_D − 5 040)/E_ref`, `E_D` — потребление завода (Σ фидеров) за сутки, `E_ref` — медиана `E_D − 5 040` по будням (5 040 = 210 кВт × 24 ч); `plate(D) = 1 290 · act(D) · eff(D)`, `eff(D) = 1 + 0,06·r(D)`, `r(D) = clamp((D − (until − 84))/84, 0, 1)` (для последних 12 недель: выпуск растёт при той же энергии, EnPI → ≈ 0,94, D-69).
4. `td.energy.driver.value`: `plate_m2 = plate(D)` (`quality='estimated'`, `source_note='демо-сид'`); `hdd` по `T_mean(D) = 8,5 + 11,5·cos(2π(doy − 200)/365)`, `hdd = max(0, 18 − T_mean)` (`quality='estimated'`).
5. (`with_mo`) МО: для рабочих суток с `plate(D) > 0` — `n = 3 + ⌊3·rnd(seed, D, "n")⌋` заказов `mrp.production` (`origin='td_energy_seed'`, продукты по весам 0,35/0,2/0,25/0,1/0,1, `product_qty` так, чтобы `Σ qty·area = plate(D)` с распределением по заказам); по 2–4 `mrp.workorder` на рабочих центрах прямых узлов (`workcenter_id` узла; нет — создаётся `mrp.workcenter` с `td_energy_node_id`), журнал `mrp.workcenter.productivity` внутри окон смен (R-21 W3); завершение МО — SQL (`state='done'`, `date_finished`; складских проводок нет, допущение для демо). Затем `td.energy.alloc._f3d_alloc_days(days)` строит `td.energy.alloc` штатным движком (R-08, R-09 `td_energy`).
6. `td.energy.daily._td_build_days(days)`.
7. (`with_baseline`) база `el/plant`: период — первые 60 % суток (минимум 180); подгонка и утверждение (`sudo`; при `r2 < r2_min` — `UserError`); EnPI за все сутки; база `gas/plant` с драйвером `hdd` при наличии газовых данных.
8. (`with_budget`) бюджет на текущий и 3 предыдущих месяца: прошлые месяцы — `round(1,02 · факт, −3)`, текущий — `round(1,02 · прогноз, −3)`; `state='approved'`.
9. Возвращает `{"days": n, "products": n, "mos": n, "workorders": n, "alloc_rows": n, "baselines": n, "budgets": n, "seconds": f}`.
Ограничения: 90 суток ≤ 4 мин, 400 суток ≤ 15 мин (ТП-04). Идемпотентность: драйверы — `UPSERT`; МО с `origin='td_energy_seed'` в диапазоне пересоздаются; `purge=True` удаляет **только** сидированное (МО `td_energy_seed` и их наряды, значения драйверов с `source_note='демо-сид'`, утверждённые базы/бюджеты с `note='демо-сид'`). Детерминизм — `rnd(seed, …)` (`td_energy/tools/backfill.rnd`).
Проверяемые свойства: `plate_m2 > 0` в рабочие дни; `R² ≥ 0,9`; EnPI последних 12 недель ∈ [0,92; 0,96]; `stack_gap_pct ≤ 3`; Σ `alloc.kwh` суток ≤ потребление завода.

### R-21 Форматы чисел

Как W3 R-25 (кВт·ч, ₴ — целые; нечисловые подписи — `fmt_dec`/`fmt_int`, запятая, узкий пробел); дополнительно: `delta_pct` в JSON — число с 1 знаком; в строках `note` — целое с явным знаком («−6 %», «+2 %»; минус — U+2212); удельные: `< 10` → 2 знака, иначе 1 знак; `hdd`, `tg`-подобные — 1 знак; `r2` — 2 знака; `enpi` — 2 знака (в JSON 4); тонны CO₂ — целые.

### R-22 Шкалы осей

Столбцы — R-08 п. 3; EnPI — R-05 п. 3; теплокарта — R-09; прочие графики — `nice` по W3 R-10 п. 3.

## 10. Состояния и переходы

| Объект | Состояния | Переходы (кто) |
|---|---|---|
| `td.energy.baseline.state` | `draft → approved → archived`; `archived/approved → draft` | `action_fit` (manager, `draft`), `action_approve` (chief), `action_archive`, `action_to_draft` (chief; сбрасывает EnPI базы); автоматически `approved → archived` при утверждении новой для той же пары |
| `td.energy.budget.state` | `draft → approved` | `action_approve` (chief); правка суммы утверждённого — только chief (сброс в `draft`) |
| `td.energy.daily.quality` | `ok / partial` | пересчёт (R-02) |
| `td.energy.enpi.quality` | `ok / no_driver / partial` | `_cron_enpi`, `recompute` |

## 11. Обработка ошибок

- **Нет базы/бюджета/драйверов:** соответствующие блоки и `delta_pct` — `null`, подписи «База не задана», блок бюджета отсутствует; исключений нет.
- **Часть упала:** `get_dashboard` возвращает `{"error": "…"}` только для упавшей части; UI показывает «Не вдалося завантажити: {частина}» (как W1).
- **Недостаток данных для подгонки:** `UserError` с числом суток; модель остаётся в `draft`.
- **Дубликаты:** `UNIQUE(day, scope, resource, node)`, `UNIQUE(baseline, day)`, `UNIQUE(driver, day)`; повторные прогоны идемпотентны.
- **Часовые пояса:** хранение UTC naive; сутки/смены — Киев; сутки 23/25 ч — по локальным слотам W1 A-30; ISODOW для теплокарты по киевской дате.
- **Смена разметки участков:** история фактов не меняется (поле `area_id` в `daily` фиксируется); для пересчёта — `action_rebuild` (wizard M-16).
- **Мультикомпания:** базы и бюджеты — `company_id`; факты и EnPI изолируются через узлы (Q-09).
- **Нет `wkhtmltopdf`:** `create_and_print` отдаёт `report_action`, ошибку формирования показывает клиент (UI-10); юнит-тест проверяет HTML.
- **Отсутствует `td_energy_mobile`:** отчёт смены пропускает блок «Обходи».
- **Отсутствует `td_energy_control`:** действия `control` резервов скрыты, показывается запасное «Відкрити» (W3).

## 12. Acceptance Criteria

Колонка «Тип»: UT (в т. ч. HttpCase) / UT-JS / TC / MAN. Все `odoo`-тесты — `post_install`, теги `-at_install`, `td`, `td_w4`. Фикстуры — разд. 13.0; числа взяты из макета `Analytics.dc.html` там, где арифметика согласована.

### 12.1 `td_energy_analytics` — AC-01…AC-62

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given установка на БД с 49 потребителями; When читаем `td.energy.area` и `node.area_id`; Then 8 участков (коды `CUT…LIGHT_OFFICE`, цвета и `spec_driver` по 5.2), узлов с участком по группам 8 / 3 / 6 / 7 / 12 / 2 / 6 / 5 = 49; повторный `_load_areas`/`_assign_areas` ничего не меняет; ручная правка `area_id` не перезаписывается | UT |
| AC-02 | FR-01 | Given участок с узлами; When `unlink`; Then `UserError("Ділянка використовується вузлами.")`; `code` дублируется — ошибка уникальности; у `LIGHT_OFFICE` нет драйвера → удельное `null` | UT |
| AC-03 | FR-02 | Given установка; Then драйверы `plate_m2` (`mrp_area`, «м²») и `hdd` (`weather_hdd`, база 18, сигнал `ventilation/totals/outdoor_c`); `UNIQUE(code)`; `UNIQUE(driver, day)` у значений | UT |
| AC-04 | FR-03 | Given форма продукта; Then есть `td_plate_area_m2` (default 0, `≥ 0`; отрицательное — `ValidationError`) | UT |
| AC-05 | FR-02 | Given 3 готовых движения МО суток (10 × 3,1; 5 × 8,4; 20 × 1,0), движение не `done`, движение без `production_id`, движение вне суток; When `_cron_values`; Then `plate_m2 = 93,0`, `quality='estimated'`, лишние не учтены; нет продуктов с `td_plate_area_m2 > 0` — строки нет; повторный прогон без дублей | UT |
| AC-06 | FR-02 | Given 24 часовых `v_avg` сигнала температуры со средним 7,0, база 18; Then `hdd = 11,0`, `quality='measured'`; < 18 часов — расчёт по сырым (≥ 50 показаний); нет данных — строки нет; `T_mean > 18` → `hdd = 0` | UT |
| AC-07 | FR-02 | Given драйвер `manual`; When manager добавляет значение / user пытается; Then `quality='manual'`, `UNIQUE(driver, day)`; user → `AccessError` | UT |
| AC-08 | FR-04 | Given сутки: фидеры 600 кВт·ч, вводы 500 (стоимость 4 200 ₴, экспорт 20), СЕС 120, КГУ 0, 12 % слотов фидеров `missing`; When `_td_build_days`; Then строка `plant`: `qty 600`, `import_qty 500`, `export_qty 20`, `gen_pv_qty 120`, `gen_chp_qty 0`, `cost 4 200`, `quality='partial'` | UT |
| AC-09 | FR-04 | Given 3 потребителя (участки CUT, CUT, HVAC) и `alloc` (минуты, простой); Then строки `node` с `qty`, `cost`, `area_id` на момент построения, `minutes`, `idle_qty`; после смены `node.area_id` построенные сутки не меняются, а повторное построение — меняет | UT |
| AC-10 | FR-04 | Given `td.energy.usage` за сутки (импорт 500; газ supply 612 м³, стоимость 12 117,60; воздух и тепло); Then строки `resource`: `el` (`import_qty`), `gas` (`qty 612`, `cost 12 117,60`, `co2_kg 1 199,52`), `air`, `heat`; `Σ resource(el).qty = import_qty` | UT |
| AC-11 | FR-04 | Given календарь «Зміна 1» 07:00–16:00 и «Зміна 2» 16:00–23:00; Then `shift1_qty + shift2_qty + off_qty = qty` (допуск 0,001); слот 15:45–16:00 → `shift1`, 16:00–16:15 → `shift2`; `direct_*` по узлам `alloc_role='direct'`; `plate_s1 + plate_s2 + plate_off = plate_m2`, пропорции — по `direct_*`; при `Σ direct = 0` — вся площадь в `plate_s1` | UT |
| AC-12 | FR-04 | Given `_td_build_days`/`_cron_daily`; When два прогона; Then строки не дублируются (удаление + вставка); сегодняшние сутки пересчитываются всегда, вчерашние — до `daily_close_h` или если нет `plant`; догон ≤ `catchup_days`; `read_enabled=False` — ничего | UT |
| AC-13 | FR-04 | Given суточные факты и ротация; Then `plant.qty = Σ feeder kwh` суток (±0,001); `_cron_rotate` удаляет `daily`, `enpi`, `driver.value` старше `keep_interval_days` | UT |
| AC-14 | FR-05 | Given 30 суток `x_i = 800 + 20·i`, `y_i = 1820 + 4,1·x_i`; When `action_fit`; Then `const_per_day = 1 820,000 ± 0,001`, `coef = 4,100 ± 1e-6`, `r2 = 1`, `rmse = 0`, `n_days = 30`; два драйвера (`y = 1500 + 4,0·plate + 35·hdd`) восстанавливаются; `k = 0` → `mean(y)` | UT |
| AC-15 | FR-05 | Given `action_fit`; When суток меньше `n_min`; драйверы `plate` и `2·plate`; 4 драйвера; Then `UserError("Замало даних для моделі бази: потрібно ≥ 30 діб, є 25.")`; `UserError("Драйвери лінійно залежні або сталі.")`; `ValidationError("Не більше 3 драйверів.")` | UT |
| AC-16 | FR-05 | Given база `draft`; When approve: user/manager → `AccessError`; chief: `r2 < r2_min` → `UserError`; коэффициент `< 0` → `UserError`; корректная → `approved`; Then прежняя `approved` пары `(resource, scope, area, company)` → `archived`, одна `approved` на пару, `method='manual'` обходит проверку R², после утверждения EnPI пересчитан | UT |
| AC-17 | FR-05 | Given газ, `y = 120 + 25·hdd` за 40 суток; Then база `gas/plant` с драйвером `hdd`: `const 120`, `coef 25`; `expected(hdd = 11) = 395` | UT |
| AC-18 | FR-06 | Given утверждённая база; When `_cron_enpi`; Then строка суток: `actual`, `expected`, `enpi`; нет значения драйвера → `expected = NULL`, `quality='no_driver'`; `daily.quality='partial'` → `partial`; повтор идемпотентен | UT |
| AC-19 | FR-06 | Given 7 суток по 1 286 м² (`expected = 49 640`), `actual = 48 150`; When `period_totals`; Then `enpi = 0,9700`, `saving_pct = 3,0`, `saving_qty = 1 490`; стоимость экономии — с группой cost; `coverage < 0,5` → `enpi = null` | UT |
| AC-20 | FR-06 | Given 12 недель EnPI; When `get_enpi`; Then 12 скользящих недель по возрастанию, `expected_mwh`/`actual_mwh`, `y_min = floor5(0,95·min)`, `y_max = ceil5(1,05·max)`, подписи «12 тижнів тому» / «цей тиждень»; нет базы → `enpi = null` | UT |
| AC-21 | FR-06 | Given крон и мастер M-16; Then `_cron_enpi` — вчера и пропуски по каждой утверждённой базе; `draft`/`archived` не считаются; диапазон мастера > 400 суток → `UserError("Не більше 400 діб.")` | UT |
| AC-22 | FR-07 | Given бюджеты; Then `month` — первое число; `amount_uah > 0`; уникальность `(company, month, resource)`; `draft` не учитывается в статусе; approve — только chief | UT |
| AC-23 | FR-07 | Given фикстура R-06 (`today = 2026-10-17`, факт 1–16 = 1 036 000, сегодня 60 000, типовые: пн–пт 62 000, сб 60 000, нд 38 000, план 1 950 000); When `get_status`; Then `fact 1 096 000`, `fact_pct 56`, `month_share 55`, `forecast 1 912 000`, `delta_pct −2`, `text` = «Факт на 17.10 — 1 096 000 ₴ (56 % при 55 % місяця) · прогноз 1 912 000 ₴, на 2 % нижче бюджету» | UT |
| AC-24 | FR-07 | Given граничные случаи; Then образцов дня недели `< 3` → среднее всех суток окна; первый день месяца; последний день (`forecast = fact`); бюджет на ресурс (газ); нет утверждённого — `null`; без группы стоимости блок отсутствует | UT |
| AC-25 | FR-08 | Given `today = 2026-10-17`; Then окна и корзины R-01: `w` — 7 (пн…нд по фактическим датам), `m` — 30 (метки у индексов 0, 5, 10…), `q` — 13 (начало 2026-07-19; «т1», «т3»…), `y` — 12 (начало 2025-11-01, месяцы) | UT |
| AC-26 | FR-09 | Given `Σa = 186 400`, `Σe = 198 298`; Then KPI `el`: `value 186 400`, `delta_pct −6,0`, note «−6 % до бази», tone `good`; нет базы — `delta_pct null`, note «База не задана» | UT |
| AC-27 | FR-09 | Given газ `18 400`, ожидание `18 039`, `avg_hdd` 9,1 против 7,9; Then `delta +2,0`, tone `bad`, note «+2 % до бази · похолодання»; HDD −15 % — «тепліше»; `|Δ| ≤ 10 %` — без суффикса; нет базы газа — «—» | UT |
| AC-28 | FR-09 | Given `el cost 1 569 600`, `gas cost 368 280`; Then KPI `cost`: `1 937 880`, note «електрика 81 % · газ 19 %»; без группы стоимости KPI отсутствует в списке | UT |
| AC-29 | FR-09 | Given потребление 186 400, плит 38 400, база 5,16; Then KPI `spec`: `4,85`, `delta −5,9`, note «база 5,16 · −6 %»; `plate = 0` → `value null` | UT |
| AC-30 | FR-09 | Given `Σ td_energy_cost = 68 000`, `Σ value = 1 000 000`, база 7,3 %; Then KPI `cogs`: `6,8`, tone `good`; знаменатель 0 → `null` («—») | UT |
| AC-31 | FR-09 | Given генерация СЕС 41 000, экспорт 7 440, потребление 186 400; Then KPI `selfgen`: `18` %, note «СЕС 41 000 кВт·год» | UT |
| AC-32 | FR-09 | Given импорт 152 840 кВт·ч (0,37), газ 18 400 м³ (1,96); Then KPI `co2`: `93` т, note «мережа 57 т · газ 36 т за період» | UT |
| AC-33 | FR-10 | Given 30 суток `daily.node`; Then `stack`: значения серий = `Σ node.qty` участка, серый «Без ділянки» при остатке, `y_max = round(1,08·max)`, `ticks` — трети (7 500 → 8 100 / 2 700, 5 400, 8 100), `unit` по периоду; `stack_gap_pct ≤ 3` на сид-данных | UT |
| AC-34 | FR-11 | Given четыре понедельника с 400/410/390/400 кВт·ч в 12:00; Then `cells[0][12] = 400,0`; порядок строк пн…нд (ISO); пустая ячейка — `null`; `max_ref = ceil50(max)`; `base_load_kw = round5(min)` | UT |
| AC-35 | FR-12 | Given срез `area` за 30 суток (CUT 26 100, плит 38 400); Then `kwh 26 100`, `spec 0,68`, `share_pct` по Σ, `LIGHT_OFFICE` без удельного («—»), сортировка по `kwh` убыв.; `cost_uah` только с группой | UT |
| AC-36 | FR-12 | Given `SAW-3`: 7 400 кВт·ч, 15 300 мин; Then срез `eq`: `spec = 29,0 кВт·год/мотогод`; общий узел без нарядов — «—»; строки сверх `top_equipment` сворачиваются в «Інші» | UT |
| AC-37 | FR-12 | Given `WH/MO/00391`: `kwh 2 470`, `qty 60`; Then срез `mo`: `spec 41,17`, `name = «WH/MO/00391 · … × 60»`; сверх `top_mo` — «Інші»; МО без строк `alloc` не показывается | UT |
| AC-38 | FR-12 | Given два МО одного продукта (по 30 шт., 1 200 и 1 270 кВт·ч); Then срез `prod`: `kwh 2 470`, `spec = 2 470/60 = 41,17`; единица — из UoM | UT |
| AC-39 | FR-12 | Given две смены календаря и сутки вне смен; Then срез `shift`: три строки «Зміна 1 · 07:00–16:00», «Зміна 2 · 16:00–23:00», «Ночі й вихідні · без виробництва»; `spec` смен = `kwh/plate_sN`; у третьей `spec_text = "база {avg_kw} кВт"` | UT |
| AC-40 | FR-13 | Given нулевой знаменатель (плит 0, минут 0, `qty 0`); Then `spec = null`, `spec_text = "—"`, исключения нет | UT |
| AC-41 | FR-24 | Given база `Wb` и текущий период; Then `CUT`: `spec_now 0,68`, `spec_base 0,7083` → `delta −4 %`; нет данных в `Wb` → `null`; нет базы — все `null`; для `mo` сравнение с удельным продукта в `Wb` | UT |
| AC-42 | FR-14 | Given `action_open_cut` по каждому срезу; Then `act_window` с доменами R-16 (`area`/`eq` — `td.energy.interval`, `mo`/`prod` — `td.energy.alloc`, `shift` — интервалы фидеров с группировкой по `hour_local`); неизвестный ключ — `UserError("Невідомий ключ: …")`; поля стоимости скрыты без группы | UT |
| AC-43 | FR-15 | Given 3 открытых резерва W3 (в плане 1); When `get_dashboard(parts=['opps'])`; Then `items`, `plan_sum`, `all_sum`, `plan_count`, `open_count` совпадают с W3 API-02/06; без группы стоимости суммы отсутствуют; `control` без `td_energy_control` → `enabled=false` + запасное действие; `action_plan_toggle` через W3 меняет `plan_sum` | UT |
| AC-44 | FR-16 | Given данные 30 суток и утверждённая база; When `_render_qweb_html` отчёта `report_management_document`; Then есть таблица 7 KPI (186 400; «−6 %»), блок EnPI, бюджет, таблица участков, топ-5 оборудования, резервы; без группы стоимости нет ₴-колонок и блока бюджета; формат A4 | UT |
| AC-45 | FR-16 | Given стенд с сидом; When «Звіт для керівництва»; Then PDF (`%PDF`) формируется ≤ 15 с, размер < 3 МБ, ≤ 6 страниц | TC |
| AC-46 | FR-17 | Given текущая смена / вне смены; When `create_and_print('shift')`; Then отчёт за текущую (с начала смены) или последнюю завершённую смену; есть энергия, пик, события, отключения, топ-3 резервов; блок обходов — при установленном `td_energy_mobile`; `action_td_energy_shift_report` возвращает `report_action`; `td.energy.dashboard._td_report_action()` возвращает его xml-id (с правкой W1 — `capabilities.report = true`) | UT |
| AC-47 | FR-16 | Given пользователь `…_user` / без группы; Then `create_and_print` доступен `user`, суммы ₴ — только с группой cost; неизвестный `kind` → `UserError("Невідомий вид звіту: x.")`; пользователь без групп энергетики — `AccessError` | UT |
| AC-48 | FR-18 | Given hoot с моком API-01; Then смена периода перезагружает `kpis, stack, heatmap, cut, opps`, смена среза — только `cut`; KPI с тоном; стек 30 столбцов и 8 серий; теплокарта 7×24; EnPI — две линии; бюджет — полоса и маркер `month_share_pct`; чекбокс плана оптимистичен и откатывается при ошибке; кнопка отчёта блокируется на время формирования; `control` без обработчика скрыт | UT-JS |
| AC-49 | FR-18 | Given `HttpCase`; When открыть `action_td_energy_analytics` для периодов `w`, `m`, `q`, `y`; Then без JS-ошибок; пункт «Аналітика» виден `group_td_energy_user`, разделы настроек — `…_manager`, «Бюджет» — `…_cost` | UT |
| AC-50 | FR-18 | Given стенд с сидом (R-20); When открыть «Аналітика»; Then все блоки заполнены, 7 KPI со значениями, EnPI 12 точек, теплокарта 7×24, таблица среза не пуста; скриншот приложен | TC (ТК-01) |
| AC-51 | FR-19 | Given роли `user`/`manager`/`chief`/`admin`; Then `user` ничего не пишет; `manager` — подгонка, драйверы `manual`, черновик бюджета, пересчёт; `chief` — утверждение базы/бюджета; `admin` — всё; record rules по компании; ключи стоимости отсутствуют у `user` без cost во всех API и в PDF | UT |
| AC-52 | FR-19 | Given `neutralize.sql`, `-u`, `uninstall`; Then 4 крона неактивны; миграция идемпотентна и заполняет `alloc.product_id`; `uninstall_hook` не затрагивает электрические данные и узлы; повторный `-u` без изменений | UT + DEPLOY_TEST |
| AC-53 | FR-20 | Given `res.config.settings`; Then параметры блока «Аналітика» редактирует `…_manager`; `r2_min ∉ [0,1]`, `forecast_min_days > forecast_weeks`, `daily_close_h ∉ [0,12]` → `ValidationError`; смена `forecast_weeks` меняет типовые сутки | UT |
| AC-54 | FR-21 | Given БД с электрическим backfill 90 суток; When `_td_seed_demo(days=90)`; Then значения `plate_m2` за все сутки, ≥ 3 МО в рабочие сутки, строки `td.energy.alloc`, база `el/plant` утверждена с `r2 ≥ 0,9`, EnPI последних 12 недель ∈ [0,92; 0,96], бюджеты на 4 месяца утверждены, `stack_gap_pct ≤ 3` | UT |
| AC-55 | FR-21 | Given сид; Then повтор не дублирует МО (`origin='td_energy_seed'`), одинаковый `seed` → одинаковый набор `driver.value` (SHA-256); `purge=True` удаляет только сидированное; без электрического backfill — `UserError` с подсказкой; не администратор — `AccessError` | UT |
| AC-56 | FR-22 | Given БД с 400 сутками истории и сидом; Then `get_dashboard('m')` ≤ 600 мс, `get_dashboard('y')` ≤ 1,5 с (медиана 10 вызовов), ≤ 60 SQL, без N+1 по узлам и участкам; теплокарта ≤ 400 мс | UT (ТП-01) |
| AC-57 | FR-22 | Given построение; Then `_td_build_days` 1 суток ≤ 3 с; 400 суток ≤ 5 мин; `action_fit` ≤ 2 с; `_cron_rotate` ≤ 30 с | UT (ТП-02, ТП-03) |
| AC-58 | FR-22 | Given 400 суток; Then `td.energy.daily` ≈ 55 строк/сутки (≈ 22 000), `td.energy.enpi` ≤ 1 200 (3 базы); размер ответа `get_dashboard('y')` ≤ 60 КБ | UT |
| AC-59 | FR-23 | Given меню; Then «Аналітика» (seq 12) идёт перед «Завантаження вузлів» (15); разделы «Налаштування → Аналітика» видны `…_manager`, «Бюджет енергії» — `…_cost` | UT |
| AC-60 | FR-05 | Given `tools/ols.py`; Then нет импорта `numpy`/`scipy`; функция `fit(X, y)` покрыта AC-14/15; на 400 суток × 3 драйвера ≤ 100 мс | UT |
| AC-61 | FR-04 | Given стенд, сутки работы; When крон `_cron_daily`; Then строка `plant` суток и 49 строк `node`; `plant.qty` = Σ фидеров; догон после остановки крона на сутки восстанавливает строки | TC |
| AC-62 | FR-19 | Given копия демо-БД с W1 и W3; When установка `td_energy_analytics`, сид, открытие экрана, повторный `-u`; Then количества по 5.4 (8 участков, 49 узлов, 2 драйвера), экран без ошибок, повтор без изменений | TC (DEPLOY_TEST) |

**Итого `td_energy_analytics`: AC-01…AC-62 = 62 критерия** (UT 56 — в т. ч. HttpCase и ТП, UT-JS 1 (AC-48), TC 4 (AC-45, AC-50, AC-61, AC-62 = DEPLOY_TEST), UT + DEPLOY_TEST 1 (AC-52)).

## 13. План тестирования (для Opus)

### 13.0 Фикстуры и требования к тестируемости

- `tests/common.py` (A): `TestW4Common(TransactionCase)` — `_area(code)`, `_node(code, area)`, `_interval(meter_code, ts_start, kwh, role=..., kwh_export=0, price=8.40)`, `_driver_value(code, day, value)`, `_daily(day, **vals)` (прямая вставка фактов), `_baseline(period, coefs)`, `_budget(month, amount)`, `_alloc(production, node, day, kwh, minutes, kind)`, `_user(groups)`; мок времени `patch("odoo.addons.td_energy.tools.dates.now_utc")`; календарь смен — `_calendar_two_shifts()`.
- Фикстура «Макет 17.10» (`TestW4Common._mockup_1710()`): 30 суток фактов под числа AC-26…AC-32 (186 400 / 198 298 / 18 400 / 1 937 880 / 4,85 / 6,8 % / 18 % / 93 т), бюджет 1 950 000 и типовые сутки для AC-23.
- Детерминизм — `seed`; расчёты — чистые функции в `tools/*` (тестируются без ORM: `ols`, `periods`, `fmt`).
- JS: hoot, мок `orm.call` с JSON из разд. 7.

### 13.1 Юнит-тесты (A, B)

| Файл | Класс | Покрывает |
|---|---|---|
| `test_w4_area.py` (A) | `TestW4Area` | AC-01, AC-02, AC-04 |
| `test_w4_driver.py` (A) | `TestW4Driver` | AC-03, AC-05, AC-06, AC-07 |
| `test_w4_daily.py` (A) | `TestW4Daily` | AC-08…AC-13, AC-61 (стенд — отдельно) |
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
| `test_w4_hoot.py` (B) | `TestW4Hoot.test_hoot_suite` | AC-48 (запуск `/web/tests?headless…&id=<hash('@td_energy_analytics')>` по образцу `td_energy/tests/test_w1_hoot.py`) |

### 13.2 Стендовые сценарии ТК-01…ТК-05 (`tests/stand/test_w4_tk.py`, A)

Предусловия: стенд E-11, установлены `td_energy`, `td_energy_resources`, `td_energy_analytics`; выполнены электрический `_td_backfill(days=400)`, ресурсный `_td_backfill(days=400)` (W3), `_td_seed_demo(days=400)`.

| ТК | Название | Шаги | Ожидается |
|---|---|---|---|
| ТК-01 | Экран «Аналітика» | открыть экран, пройти периоды `w/m/q/y` и пять срезов | AC-50: блоки заполнены, нет ошибок, переключения ≤ 1,5 с |
| ТК-02 | EnPI и бюджет | проверить блок EnPI и бюджет; изменить бюджет месяца; утвердить | EnPI 0,92…0,96; блок бюджета обновился после утверждения; chief-only |
| ТК-03 | Резервы и «у плані» | отметить резерв «у плані»; выполнить `ticket`-действие | `plan_sum` пересчитан; заявка создана с тегом `[OPP-id]`; после закрытия заявки резерв `done` |
| ТК-04 | PDF | «Звіт для керівництва», затем «Звіт за зміну» с Пульта (после правки W1) | AC-45, AC-46: PDF открывается, суммы ₴ только с группой |
| ТК-05 | Живая достройка | после суток работы крона | AC-61: строки суток, догон после остановки |

### 13.3 Тесты безопасности (ТБ-01…ТБ-04)

- ТБ-01: пользователь `base.group_user` без групп энергетики → `AccessError` на всех публичных методах `td.energy.analytics` и мастере отчёта.
- ТБ-02: ключи стоимости отсутствуют (KPI «Вартість», `cost_uah`, суммы резервов, бюджет, колонка среза) без `group_td_energy_cost` в API и PDF (AC-51).
- ТБ-03: утверждение базы и бюджета — только `chief` (AC-16, AC-22, AC-51).
- ТБ-04: `_td_seed_demo`, `_td_build_days`, `action_rebuild` — только администратор/manager по таблице прав.

### 13.4 Тесты производительности (ТП-01…ТП-05)

- ТП-01: `get_dashboard('m')` ≤ 600 мс, `('y')` ≤ 1,5 с, теплокарта ≤ 400 мс, ≤ 60 SQL (AC-56).
- ТП-02: `_td_build_days` — 1 сутки ≤ 3 с, 400 суток ≤ 5 мин (AC-57).
- ТП-03: `action_fit` ≤ 2 с; `_cron_rotate` ≤ 30 с (AC-57).
- ТП-04: `_td_seed_demo(days=90)` ≤ 4 мин, `days=400` ≤ 15 мин (R-20).
- ТП-05: PDF «для керівництва» ≤ 15 с, ≤ 3 МБ (AC-45).

### 13.5 DEPLOY_TEST

1. Копия демо-БД с W1 и W3 (`td_demo_tpl`) → `-i td_energy_analytics` → количества 5.4 (AC-62).
2. Повторное `-u` — без изменений.
3. Сид → экран → PDF.
4. Откат: `uninstall` → электрические данные целы (AC-52).
5. `neutralize.sql`.

### 13.6 Распределение тестов и команд по воркерам (выписка из ARCH §6)

Шаг 0 — каркас менеджера (пустые файлы, `__init__.py`, манифесты, правка W1 `_td_report_action`); `T=factory3d/tools/odoo`. Все три воркера параллельно (≤ 3), общих файлов нет (владельцы — разд. 0 и H.0); A и B стартуют после слияния W3.

| Воркер | Тесты | Команда |
|---|---|---|
| A «Бекенд аналитики» | `test_w4_area`, `test_w4_driver`, `test_w4_daily`, `test_w4_ols`, `test_w4_baseline`, `test_w4_enpi`, `test_w4_budget`, `test_w4_kpis`, `test_w4_stack_heatmap`, `test_w4_cuts`, `test_w4_seed`, `test_w4_security`, `test_w4_perf` | `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics $T/run_tests.sh td_w4a /td_energy_analytics:TestW4Daily` (и остальные классы по списку); регресс `$T/run_tests.sh td_w4a_reg /td_energy` и `/td_energy_resources` |
| B «Фронтенд и отчёты» | `test_w4_report`, `test_w4_ui`, `test_w4_hoot` | `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics $T/run_tests.sh td_w4b /td_energy_analytics:TestW4Report` (затем `…TestW4Ui`, `…TestW4Hoot`) |
| C «Мобильный» (Часть II) | `test_wh_template`, `test_wh_schedule`, `test_wh_round`, `test_wh_value`, `test_wh_api`, `test_wh_security`, `test_wh_ui`, `test_wh_hoot` | `F3D_TEST_INSTALL=td_energy,td_energy_mobile $T/run_tests.sh td_w4c /td_energy_mobile:TestWHRound` (и остальные классы); регресс W1: `$T/run_tests.sh td_w4c_reg /td_energy` |
| менеджер (интеграция) | всё | `F3D_TEST_INSTALL=td_energy,td_energy_resources,td_energy_analytics,td_energy_mobile $T/run_tests.sh td_w4_full`; затем стенд ТК-01…ТК-05, ТК-H1…ТК-H3 |

## 14. Definition of Done (W4, `td_energy_analytics`)

- Все UT/UT-JS AC-01…AC-62 зелёные; ТК-01…ТК-05 пройдены; `ruff` без ошибок; регрессия `td_energy` (142 + W1) и `td_energy_resources` зелёная;
- `neutralize.sql`, CHANGELOG, README («Аналітика», «Модель бази ISO 50001», «Бюджет»), DEPLOY_TEST дополнены; обзор безопасности (ТБ-01…ТБ-04);
- миграция `19.0.1.0.0` проверена на копии БД; сид выполнен на стенде, скриншот экрана и пример PDF приложены;
- правка W1 (`_td_report_action`) внесена менеджером и проверена (ТК-04).

## 15. Открытые вопросы и решения автора

### Вопросы Q-01…Q-09

| ID | Вопрос | Кому | Рекомендация | Что делаем тем временем |
|---|---|---|---|---|
| Q-01 | Источник «м² плиты»: поле на продукте (E-07) или площадь листов из карт раскроя `td.cut.map` (`td_machine_connect`)? | заказчик | поле на продукте сейчас; карты раскроя — позже как драйвер `cut_map_area` без зависимости | `plate_m2` из готовой продукции МО × `td_plate_area_m2` (`estimated`) |
| Q-02 | Данные за 2025 для модели базы (≥ 3 мес. суточного потребления и выпуска) | заказчик | подгонка на реальных данных, утверждение главным энергетиком | демо: сид и база на первых 60 % истории |
| Q-03 | Месячный бюджет энергии: откуда (финансы), в разрезе ресурсов? | бухгалтерия | общий бюджет + при желании по газу | ввод вручную (`td.energy.budget`) |
| Q-04 | Официальные коэффициенты CO₂ сети и газа | заказчик | значения методики/оператора сети | 0,37 кг/кВт·ч и 1,96 кг/м³ из макета (W3 M-01) |
| Q-05 | Драйвер «м² фасада» для «Фасади МДФ» (макет 3,10 кВт·год/м²) | технологи | добавить драйвер `manual`/MRP позже | удельное на м² плиты (D-61) |
| Q-06 | Календарь смен (две смены макета vs «Зміна 1 07:00–15:30» сервера) | заказчик | календарь с двумя сменами | `td.energy.shift_calendar_id` + умолчание макета (W3 R-21) |
| Q-07 | Кто утверждает базу и бюджет | заказчик | главный энергетик | `group_td_energy_chief` |
| Q-08 | Web Push и PWA для телефона (GAP Q-14) | менеджер | отдельное решение после W4; стандартный PWA Odoo доступен | не входит |
| Q-09 | Мультикомпания: факты без `company_id` | менеджер | при двух компаниях в одной БД добавить `company_id` в `daily` | одна компания; изоляция через узлы |

### Решения автора (A-01…A-18)

| ID | Решение | Обоснование |
|---|---|---|
| A-01 | Два модуля: `td_energy_analytics` (жёстко зависит от `td_energy_resources`) и `td_energy_mobile` (зависит только от `td_energy`) | аналитика «усі ресурси» требует `usage`, цен, CO₂, резервов W3; мобильный «Обхід» — операционная функция, не аналитика, и ставится отдельно (Часть II, A-H1) |
| A-02 | Карта «узел → участок» — данные (`area_map.csv`), разметка по логике технологической цепочки | макет называет категории, но не узлы; правка менеджером без кода |
| A-03 | Суточные факты в таблице `td.energy.daily` (≈ 55 строк/сутки) вместо запросов к 15-мин таблицам | годовые срезы по 49 потребителям — 1,9 млн строк интервалов; сутки — ≈ 20 тыс. строк |
| A-04 | `area_id` в фактах фиксируется при построении | история не «переезжает» при переразметке |
| A-05 | Модель базы — регрессия по ≤ 3 драйверам, чистый Python, нормальные уравнения | ISO 50001; без numpy (как в GAP §5.1) |
| A-06 | Утверждает база/бюджет `chief`; подгонка — `manager` | E-06: разделение ролей |
| A-07 | EnPI хранится по суткам; недели/периоды — агрегаты `Σa/Σe` | один источник правды; пересчёт мастером |
| A-08 | Драйвер `plate_m2` — из готовой продукции МО × поле продукта; `quality='estimated'` | E-07 |
| A-09 | Драйвер `hdd` — из часовых агрегатов `td.reading.hour` (хранятся 400 суток) | сырые читаются лишь 30 суток |
| A-10 | Прогноз бюджета — типовые сутки по дню недели, как W1 A-30 | единый подход без погоды |
| A-11 | KPI «Електроенергія» — потребление завода; «Вартість» — покупка (D-51) | зональный тариф |
| A-12 | Площадь плит по сменам — пропорционально энергии прямых станков | в проводках МО нет времени суток |
| A-13 | Срез «До бази» — сравнение с тем же ключом в окне базы (D-60) | заменяет «спрощено» GAP AN-20 проверяемой формулой |
| A-14 | МО, пересекающие границу окна, берутся целиком в удельном «на шт.» | упрощение; погрешность на границах |
| A-15 | Отчёты — qweb-pdf поверх API (одни числа с экраном) | согласованность экрана и PDF |
| A-16 | Кнопка «Звіт за зміну» Пульта включается хуком `_td_report_action` (правка W1) | W1 D-01; жёсткий `False` и xml-id в коде W1 |
| A-17 | Сид — метод модели `_td_seed_demo`, МО через ORM, завершение SQL, склад не затрагивается | демо-инструмент; допущения документированы (R-20) |
| A-18 | Версии, параметры и ID — модульные; D-xx сквозные (D-51…D-69) | W3 A-11 |

---
