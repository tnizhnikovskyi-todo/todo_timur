> **Розміщення (W4).** Основний SPEC `td_energy_mobile`: спільна преамбула (позначення, діапазони ID, відхилення D-51…D-80; повторена з [../td_energy_analytics/SPEC.md](../td_energy_analytics/SPEC.md)) і Частина II — розділи H.0–H.15 модуля `td_energy_mobile`. Пов'язаний модуль — `td_energy_analytics` ([../td_energy_analytics/SPEC.md](../td_energy_analytics/SPEC.md), Частина I).
> Зміни контрактів C-01…C-08, API-01 і API-H1 — лише через менеджера (JSON-еталони: `odoo_addons/td_energy_analytics/contracts/`, `odoo_addons/td_energy_mobile/contracts/`). Посилання на розділи «0», «H.0» тощо — усередині цього файлу.
> Читати лише шматками: `grep -nE '^#{2,3} ' <файл>`, потім Read з offset/limit.

# td_energy_mobile — специфікація (W4 «Аналітика й мобільний»: модулі `td_energy_analytics` і `td_energy_mobile`)

Версія 0.2 · 19.10.2026 (v0.1 — 18.10.2026) · стандарт `docs/DOC_STANDARD.md` · технічне рішення: [ARCHITECTURE.md](ARCHITECTURE.md) (далі ARCH: FR-01…FR-24 і FR-H1…FR-H10, A-01…A-18 і A-H1…A-H6, Q-01…Q-09 і Q-H1…Q-H3) · статус: збудовано (гілка `claude/td-energy-w4`); відхилення збірки — у «Журналі змін документа» в кінці файлу.
Вхід: `build/energy/GAP.md` (E-01…E-11, §5 «Аналітика», AN-01…AN-23, MB-08, MB-09), макети `Analytics.dc.html` і `Mobile.dc.html` (вкладки «Стан», «Тривоги», «Схема», **«Обхід»**); контракти W1 (`W1_SPEC.md`: API-05/API-12, R-27, R-32 `actions[]` = C-32, R-33, R-36, реєстр мобільних вкладок C-33, UI-09) і W3 ([../td_energy_resources/SPEC.md](../td_energy_resources/SPEC.md): `td.energy.usage`, `td.energy.opportunity`, `tools/shifts.py`, `td.energy.price._td_price_at`, контракт C-01).
Спирається на: `docs/ARCHITECTURE.md` §3, §5, D-18; код `td_energy` на гілці `claude/factory3d-build` (`d14d13c`: `td.energy.interval`, `td.energy.alloc`, `td.energy.node`, `tools/{dates,forecast,backfill,bus}.py`, `static/src/mobile/mobile.js`); `td_telemetry` (`td.reading.hour`); `mrp`, `mrp_account`, `stock_account` (`stock.move.value`, Odoo 19).
Мова: проза — українською (`docs/DOC_STANDARD.md`), рядки інтерфейсу, `string=` і тексти помилок — українські.
Документ розкладено за модулями: `td_energy_analytics` ([../td_energy_analytics/SPEC.md](../td_energy_analytics/SPEC.md) — Частина I) і `td_energy_mobile` (цей файл — Частина II).

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


# ЧАСТИНА II. `td_energy_mobile` — мобільний екран «Чергування»: вкладка «Обхід» і журнал

Мобільний екран загалом (`td_energy.mobile`, W1 UI-09) складається з чотирьох вкладок. Вкладки «Стан», «Тривоги», «Схема» реалізовані в W1 (`td_energy`); модуль `td_energy_mobile` додає четверту — **«Обхід»** — через реєстр `registry.category("td_energy.mobile_tabs")` (контракт C-33, код `static/src/mobile/mobile.js`: запис `{id, label, sequence, component, [title], [badge(mobile)], [icon]}`, компонент отримує props `{mobile, meta, capabilities, reload, goTab}`), а також журнал обходів і службові дані. Приймання «екрана загалом» — таблиця H.3.1 і ТК-H1…ТК-H3.

## H.0 Дерево файлів

Власник — **C** (ARCH §6). Файли без літери — менеджер (каркас).

```
odoo_addons/td_energy_mobile/
├── __manifest__.py                        (менеджер) розділ H.1
├── __init__.py                            (менеджер) from . import models; from .hooks import post_init_hook, uninstall_hook
├── hooks.py                               C  post_init_hook: _seed_template (ідемпотентно); uninstall_hook: kind 'round' → 'manual'
├── models/
│   ├── __init__.py                        (менеджер)
│   ├── td_energy_round_template.py        C  M-H1, M-H2, M-H3
│   ├── td_energy_round.py                 C  M-H4, M-H5 (+ API-H1…API-H6, крон)
│   ├── td_energy_event.py                 C  M-H6 (`_inherit td.energy.event`: selection_add 'round')
│   └── res_config_settings.py             C  M-H7
├── tools/
│   ├── value.py                           C  R-H4 (джерела значень, норми)
│   └── schedule.py                        C  R-H1, R-H2 (слоти, вікна, DST)
├── data/
│   ├── round_template_data.xml            C  шаблон «Обхід ТП і ГРЩ» (6 пунктів, 2 слоти; noupdate=1)
│   ├── ir_config_parameter.xml            C  параметри (розд. H.5)
│   ├── ir_cron.xml                        C  3 крони (розд. H.6)
│   └── neutralize.sql                     C
├── security/
│   ├── td_energy_mobile_security.xml      C  record rules
│   └── ir.model.access.csv                C  M-H1…M-H5
├── static/src/mobile_round/               C  UI-H1…UI-H4: round.js, round.xml, round.scss; реєстрація вкладки
├── static/tests/round.test.js             C  hoot
├── views/
│   ├── td_energy_round_views.xml          C  V-H1…V-H5
│   └── menus.xml                          C  V-H6
└── tests/
    ├── common.py                          C  TestWHCommon
    ├── test_wh_template.py, test_wh_schedule.py, test_wh_round.py, test_wh_value.py,
    │   test_wh_api.py, test_wh_security.py, test_wh_ui.py, test_wh_hoot.py            C
    └── stand/test_wh_tk.py                                                           C  ТК-H1…ТК-H3
```

## H.1 Маніфест

`name`: «Чергування (телефон)»; `version`: `19.0.1.0.0`; `depends`: `["td_energy"]` (транзитивно `maintenance`, `bus`, `mail`); `data` (порядок): `security/td_energy_mobile_security.xml`, `security/ir.model.access.csv`, `data/ir_config_parameter.xml`, `data/round_template_data.xml`, `data/ir_cron.xml`, `views/td_energy_round_views.xml`, `views/menus.xml`; `assets`: `web.assets_backend`: `td_energy_mobile/static/src/mobile_round/**`, `web.assets_unit_tests`: `td_energy_mobile/static/tests/**`; `post_init_hook`: `hooks.post_init_hook`; `uninstall_hook`: `hooks.uninstall_hook`. Порядок завантаження асетів: після `td_energy` (реєстр `td_energy.mobile_tabs` уже створений модулем `td_energy`).

## H.2 Моделі

### M-H1 `td.energy.round.template` — шаблон обходу (FR-H1)

`_name = "td.energy.round.template"`, `_description = "Енергетика: шаблон обходу"`, `_order = "sequence, id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | size=64, req («Обхід ТП і ГРЩ») |
| `code` | Char | size=32, req, `UNIQUE(code)` |
| `sequence` | Integer | default 10 |
| `active` | Boolean | default True |
| `slot_ids` | One2many `td.energy.round.slot` | розклад (M-H2) |
| `item_ids` | One2many `td.energy.round.template.item` | пункти (M-H3) |
| `note` | Text | |
| `company_id` | Many2one `res.company` | req, default `env.company` |

### M-H2 `td.energy.round.slot` — слот розкладу

| Поле | Тип | Параметри |
|---|---|---|
| `template_id` | Many2one | req, ondelete=cascade |
| `name` | Char | size=32, req («Зміна 2») |
| `time_from`, `time_to` | Float | req; години доби (7,0 — 07:00); constraint `0 ≤ time_from < time_to ≤ 24` («Слот не може перетинати північ.») |
| `weekdays` | Char | size=13, default `0,1,2,3,4` (пн = 0); constraint — список цифр 0…6 без повторів |
| `sequence` | Integer | default 10 |

### M-H3 `td.energy.round.template.item` — пункт шаблону

| Поле | Тип | Параметри |
|---|---|---|
| `template_id` | Many2one | req, ondelete=cascade |
| `sequence` | Integer | default 10 |
| `code` | Char | size=16, req; `UNIQUE(template_id, code)` |
| `title` | Char | size=128, req |
| `hint` | Char | size=128, «Підказка (без норми)» |
| `source` | Char | size=96, «Джерело значення»: `signal:<код сигналу>` або `pult:<шлях JSON у get_pult(kpis)>` (напр. `pult:kpis.generation.genset.fuel_pct`); порожньо — без значення |
| `norm_kind` | Selection | `none`, `max`/«до», `min`/«від», `range`/«діапазон»; default `none` |
| `norm_min`, `norm_max` | Float | межі норми |
| `unit` | Char | size=16 («°C», «%») |
| `precision` | Integer | default 0, знаків після коми в підказці |
| `node_id` | Many2one `td.energy.node` | для «Де це в 3D» |
| `required` | Boolean | default True |

Constraints: `source` — формат `^(signal|pult):.+$` або порожньо; `norm_kind='max'` ⇒ `norm_max`, `'min'` ⇒ `norm_min`, `'range'` ⇒ `norm_min ≤ norm_max` (`ValidationError("Норма пункту «%s» некоректна.")`).

### M-H4 `td.energy.round` — обхід (екземпляр; FR-H2…FR-H4)

`_name = "td.energy.round"`, `_description = "Енергетика: обхід"`, `_inherit = ["mail.thread"]`, `_order = "date desc, starts_at desc, id desc"`.

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | compute store: «{template.name} · {slot.name} · {DD.MM}» |
| `template_id` | Many2one | req, idx, ondelete=restrict |
| `slot_id` | Many2one `td.energy.round.slot` | ondelete=set null |
| `slot_name` | Char | snapshot імені слота |
| `date` | Date | req, idx (Київ) |
| `starts_at`, `due_at` | Datetime | req (UTC): початок і кінець слота |
| `state` | Selection | `open`/«Відкритий», `in_progress`/«У роботі», `done`/«Завершено», `missed`/«Не виконано», `cancelled`/«Скасовано»; default `open`, idx, tracking |
| `performer_id` | Many2one `res.users` | виконавець (перший, хто відмітив), readonly |
| `started_at`, `finished_at` | Datetime | readonly |
| `item_ids` | One2many `td.energy.round.item` | |
| `total_count`, `done_count` | Integer | compute store |
| `progress_pct` | Integer | compute store: `round(done/total·100)` (0 при `total = 0`) |
| `deviation_count` | Integer | compute store: пунктів з `result='deviation'` |
| `note` | Char | size=256 |
| `company_id` | Many2one `res.company` | req, default `env.company` |

`UNIQUE(template_id, slot_id, date)`. Методи — API-H1…API-H6.

### M-H5 `td.energy.round.item` — пункт обходу

| Поле | Тип | Параметри |
|---|---|---|
| `round_id` | Many2one | req, idx, ondelete=cascade |
| `sequence`, `code`, `title`, `hint` | — | знімок шаблону на момент створення |
| `source`, `norm_kind`, `norm_min`, `norm_max`, `unit`, `precision`, `required` | — | знімок |
| `node_id` | Many2one `td.energy.node` | знімок |
| `done` | Boolean | default False |
| `done_at` | Datetime | readonly |
| `done_by` | Many2one `res.users` | readonly |
| `value` | Float | значення в момент відмітки (знімок) |
| `value_text` | Char | size=32: «58 °C» або «немає даних» |
| `result` | Selection | `pending`/«Очікує», `ok`/«У нормі», `deviation`/«Поза нормою»; default `pending` |
| `comment` | Char | size=256 |
| `event_id` | Many2one `td.energy.event` | ondelete=set null, readonly |
| `request_id` | Many2one `maintenance.request` | ondelete=set null |

### M-H6 `td.energy.event` — розширення

`kind` отримує значення `("round", "Обхід")` (`selection_add`, `ondelete={"round": lambda recs: recs.write({"kind": "manual"})}` — при видаленні модуля події переводяться в `manual`; `uninstall_hook` дублює це як страховку).

### M-H7 `res.config.settings` — розширення

Поля `td_energy_mobile_*` з `config_parameter` (розд. H.5); блок «Чергування» в `td_energy` (V-H5).

## H.3 Подання та мобільний екран

### H.3.1 Мобільний екран загалом (карта та приймання)

Екран — клієнтська дія `td_energy.mobile` (`action_td_energy_mobile`, меню «Енергетика → Чергування (телефон)»), адаптивний ≥ 360 px (еталон 390 × 844), кнопки ≥ 48 px, дані — ORM-RPC + шина `td_energy`. Вхід «на телефон»: адреса `/odoo/action-td_energy.action_td_energy_mobile` і стандартне встановлення PWA Odoo («Додати на головний екран»); Web Push не входить (Q-08).

| № | Елемент (макет `Mobile.dc.html`) | Де реалізовано | Джерело даних | AC |
|---|---|---|---|---|
| 1 | Шапка: «Енергетика · чергування», назва вкладки, чип часу `HH:MM` (живе/часткове/застаріле) | `td_energy` (W1) | `get_mobile().meta` | W1 AC-145, AC-146 |
| 2 | Вкладка «Стан»: «З мережі» кВт і %, смуга, плитки СЕС / BESS / ДГУ·АВР / cos φ, блок «Активні» | `td_energy` (W1) | `get_mobile().state` | W1 AC-146 |
| 3 | Вкладка «Тривоги · N»: картки (Беру в роботу, Де це в 3D, Відкласти, Призначити на себе), «Інфо за сьогодні» | `td_energy` (W1) | `get_mobile().alarms` | W1 AC-146 |
| 4 | Вкладка «Схема»: вузли зі статусом | `td_energy` (W1) | `get_mobile().scheme` | W1 AC-146 |
| 5 | **Вкладка «Обхід»:** заголовок «Обхід ТП і ГРЩ · {зміна}», лічильник «{done} / {total}», смуга прогресу, пункти (чекбокс 22 px, назва, підказка з нормою і значенням), «Завершити обхід» | `td_energy_mobile` | `td.energy.round.get_mobile()` | AC-H12…AC-H15, AC-H19 |
| 6 | Нижня навігація з 4 колонок (Стан, Тривоги · N, Схема, Обхід), активна — акцентом | `td_energy` (оболонка, реєстр) + `td_energy_mobile` (запис) | `registry td_energy.mobile_tabs` | AC-H18 |
| 7 | Тост-сповіщення («Обхід завершено й записано в журнал о 14:40», «Позначте всі пункти обходу: залишилось N») | `td_energy` (`useEnergyActions().notify`) + `td_energy_mobile` | відповідь `action_finish`/клієнт | AC-H15, AC-H24 |
| 8 | «Де це в 3D» у пункту обходу | `td_energy_mobile` через `useEnergyActions().show3d(node_code)` | `item.node_code`, `can_3d` | AC-H25 |

Наскрізне приймання — ТК-H1 (усі чотири вкладки в одному сценарії), ТК-H2 (дві сесії), ТК-H3 (прострочений слот).

### H.3.2 Подання V-H1…V-H6

| ID | XML-id (`td_energy_mobile.`) | Тип / модель | Структура |
|---|---|---|---|
| V-H1 | `view_td_energy_round_list` / `_form` / `_search` / `_pivot`, `action_td_energy_round` | `td.energy.round` | **Журнал обходів.** list (readonly): `date`, `name`, `slot_name`, `state` (badge: open — info, in_progress — warning, done — success, missed — danger, cancelled — muted), `performer_id`, `finished_at`, `done_count`/`total_count` (progressbar), `deviation_count` (decoration danger при > 0); form: статусбар `state`, шапка (шаблон, слот, дата, виконавець, початок/кінець), вкладка «Пункти» (`item_ids`: назва, `done`, `value_text`, `result`, `comment`, `event_id`, `request_id`), `note`, чаттер; кнопки «Завершити» (`action_finish_form` — обгортка над `action_finish` для кнопки `type=object`, збірка W4; chief), «Скасувати» (chief); search: «Сьогодні», «Мої» (`performer_id = uid`), «Не виконані» (`state='missed'`), «З відхиленнями» (`deviation_count > 0`), групування `state`, `template_id`, `performer_id`, `date:month`; pivot: рядки `date:week`, стовпці `state`, міра `count`; доступ read-only для `…_user`/`…_manager`, запис — через методи |
| V-H2 | `view_td_energy_round_template_list` / `_form`, `action_td_energy_round_template` | `td.energy.round.template` | form: `name`, `code`, `active`, вкладки «Слоти» (editable list `name`, `time_from`, `time_to`, `weekdays`), «Пункти» (editable list усіх полів M-H3), `note`; редагування — `group_td_energy_chief` і `td_factory3d.group_td_admin` |
| V-H3 | `view_td_energy_round_item_list` | `td.energy.round.item` | readonly list для звітів (`round_id`, `title`, `value_text`, `result`, `comment`), фільтр «Відхилення» |
| V-H4 | `action_td_energy_round_open` (server action) | `ir.actions.server` | «Запустити обхід зараз» (`td.energy.round.action_start_now` → `action_start`: перший активний шаблон без відкритого обходу, після чого відкривається форма обходу; збірка W4) для чергового без автослота; `group_td_energy_manager` |
| V-H5 | `res_config_settings_view_form_td_energy_mobile` (успадковує `td_energy.res_config_settings_view_form_td_energy`) | form | група «Чергування»: `td_energy_mobile_keep_days`, `…_value_fresh_s`, `…_missed_event`, `…_history_limit` |
| V-H6 | `views/menus.xml` | `ir.ui.menu` | таблиця H.3.3 |

### H.3.3 Меню

| XML-id (`td_energy_mobile.`) | Назва | Батько | seq | Групи | Дія |
|---|---|---|---|---|---|
| `menu_td_energy_round` | Журнал обходів | `td_energy.menu_td_energy` | 76 | `td_energy.group_td_energy_user` | `action_td_energy_round` |
| `menu_td_energy_round_template` | Шаблони обходів | `td_energy.menu_td_energy_config` | 70 | `…group_td_energy_chief` | `action_td_energy_round_template` |
| `menu_td_energy_round_open` | Запустити обхід зараз | `td_energy.menu_td_energy_config` | 71 | `…group_td_energy_manager` | `action_td_energy_round_open` |

### H.3.4 Клієнтські компоненти UI-H1…UI-H4

| ID | Компонент | Вміст і поведінка |
|---|---|---|
| UI-H1 | `MobileRound` (запис реєстру `td_energy.mobile_tabs`: `{id: "round", label: "Обхід", title: "Обхід", sequence: 40, component: MobileRound, icon: "M9 4h6M9 4a2 2 0 0 0-2 2H5v15h14V6h-2a2 2 0 0 0-2-2M9 12l2 2 4-4"}`; `badge` не задається — D-78) | Вкладка: завантаження `orm.call("td.energy.round", "get_mobile", [])` (`onWillStart`, після дій і за тиком шини `state`, `useEnergyBus(cb, ["state"])`), стани: «Завантаження», помилка («Не вдалося завантажити: …», кнопка «Повторити»), «немає обходу» (D-74), обхід. Заголовок: «{template} · {slot}» ліворуч, лічильник «{done} / {total}» праворуч; смуга прогресу висотою 6 px (`#714B67`, ширина `progress_pct`); банер «Обхід виконує {ім'я}» (лише читання). **Збірка W4:** запис реєструється **завжди** — `registerRoundTab()` викликає `mobileTabs.add("round", ROUND_TAB, {force: true})` без перевірки сторінки тестів (AC-H18) |
| UI-H2 | `RoundItem` | Рядок-кнопка `<label>` мінімальної висоти 44 px: чекбокс 22 px (`accent-color: #714B67`), назва (вага 500), підказка 12,5 px; при `result='deviation'` — чип «поза нормою» і поле коментаря (необов'язково); «Де це в 3D» — кнопка 48 px, якщо `can_3d`; відмітка викликає `action_toggle_item(item_id, done)` з оптимістичним оновленням і відкатом при помилці |
| UI-H3 | `RoundFinish` | Кнопка «Завершити обхід» (≥ 48 px): при `finish_blocked` — сіра (`aria-disabled="true"`), клік показує тост «Позначте всі пункти обходу: залишилось {N}» (D-72); при готовності — основна; успіх → тост «Обхід завершено й записано в журнал о {finished_at_local}», перезавантаження вкладки |
| UI-H4 | `RoundHistory` | Секція «Останні обходи» (≤ `history_limit`, за замовчуванням 3): дата, назва зміни, статус, `done/total`, відхилення; показується в стані «немає обходу» і під поточним обходом (згорнуто) |

## H.4 Права

### H.4.1 `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_energy_round_template_user,td.energy.round.template user,model_td_energy_round_template,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_round_template_chief,td.energy.round.template chief,model_td_energy_round_template,td_energy.group_td_energy_chief,1,1,1,1
access_td_energy_round_slot_user,td.energy.round.slot user,model_td_energy_round_slot,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_round_slot_chief,td.energy.round.slot chief,model_td_energy_round_slot,td_energy.group_td_energy_chief,1,1,1,1
access_td_energy_round_template_item_user,td.energy.round.template.item user,model_td_energy_round_template_item,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_round_template_item_chief,td.energy.round.template.item chief,model_td_energy_round_template_item,td_energy.group_td_energy_chief,1,1,1,1
access_td_energy_round_user,td.energy.round user,model_td_energy_round,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_round_manager,td.energy.round manager,model_td_energy_round,td_energy.group_td_energy_manager,1,1,1,0
access_td_energy_round_admin,td.energy.round admin,model_td_energy_round,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_round_item_user,td.energy.round.item user,model_td_energy_round_item,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_round_item_manager,td.energy.round.item manager,model_td_energy_round_item,td_energy.group_td_energy_manager,1,1,0,0
access_td_energy_round_item_admin,td.energy.round.item admin,model_td_energy_round_item,td_factory3d.group_td_admin,1,1,1,1
```

### H.4.2 Групи та правила

Нових груп немає: «Енергетик» (`group_td_energy_manager`) виконує обходи (відмічає пункти, завершує свій обхід, запускає вручну); «Головний енергетик» (`…_chief`) править шаблони, завершує/скасовує чужі обходи; `…_user` — читає журнал. Запис у `td.energy.round.item` виконують **методи** (`sudo()` після перевірки групи й виконавця), а не прямий `write` клієнта. Record rules: `td_energy_round_rule_company`, `td_energy_round_template_rule_company` — `['|', ('company_id','=',False), ('company_id','in',company_ids)]`, глобальні.

## H.5 Дані

### H.5.1 `data/ir_config_parameter.xml` (`noupdate="1"`) — `td.energy_mobile.*`

| Ключ | За замовчуванням | Призначення |
|---|---|---|
| `td.energy_mobile.keep_days` | `730` | зберігання обходів (ротація) |
| `td.energy_mobile.value_fresh_s` | `120` | значення сигналу «свіже», якщо не старше (с); при `3·period_s` більше — береться воно |
| `td.energy_mobile.missed_event` | `1` | створювати `td.energy.event` при `missed` |
| `td.energy_mobile.history_limit` | `3` | кількість «останніх обходів» у відповіді |

### H.5.2 Шаблон `data/round_template_data.xml` (`noupdate="1"`; з макета `Mobile.dc.html`, `roundItems`)

Шаблон `round_tpl_tp_grsh` (`code='TP-GRSH'`, «Обхід ТП і ГРЩ»), слоти: «Зміна 1» 07:00–16:00 і «Зміна 2» 16:00–23:00, `weekdays=0,1,2,3,4` (зміни макета, Q-H1). Пункти:

| code | title | hint | source | norm | unit | node |
|---|---|---|---|---|---|---|
| `t1` | T1: огляд, температура олії | — | `signal:energy/transformers/T1/temp_c` | `max` 85 | °C | `T1` |
| `t2` | T2: огляд, температура олії | — | `signal:energy/transformers/T2/temp_c` | `max` 85 | °C | `T2` |
| `swb` | ГРЩ SWB-1: нагрів з'єднань | тепловізор, точки Q1, Q2, QS | — | `none` | — | `SWB-1` |
| `pfc` | Компенсація PFC-1 і PFC-2 | ступені, контактори, запобіжники | — | `none` | — | `PFC-1` |
| `dgu` | ДГУ: паливо, підігрів, акумулятор | — | `pult:kpis.generation.genset.fuel_pct` | `min` 60 | % | `ATS-1` |
| `bess` | BESS: стан, вентиляція шафи | журнал помилок інвертора | — | `none` | — | `BESS` |

Вузли відсутні — `node_id` порожній, пункт залишається (кнопки 3D немає). Джерела — `energy/transformers/T*/temp_c` (W1 R-29), паливо ДГУ — KPI моста `td_genset_factory3d` (`kpis.generation.genset.fuel_pct`, W1 API-05). Усі — **ПРИПУЩЕННЯ** щодо складу пунктів до узгодження з електриками (Q-H1).

### H.5.3 `post_init_hook` і міграція

`_seed_template(env)` — завантажує шаблон, якщо немає `code='TP-GRSH'` (XML `noupdate`, функція лише перевіряє); створює крон-записи; нічого не створює в обходах. Очікувано на демо-БД: шаблонів 1, слотів 2, пунктів 6, параметрів +4, обходів 0 до першого крона.

### H.5.4 `uninstall_hook`

Переводить `td.energy.event.kind='round'` у `manual`; знімає власні крон-записи й параметри; таблиці модуля видаляються штатно (журнал обходів губиться — за потреби експортується перед видаленням). Решта даних `td_energy` не зачіпається.

## H.6 Крон-завдання

Усі — `user_id=base.user_root`, `try/except`; при `td.energy.read_enabled = False` не діють.

| XML-id | Назва | Інтервал | Метод | За один прогін | Ліміт |
|---|---|---|---|---|---|
| `cron_td_energy_round_open` | Енергетика: відкриття обходів | 10 хв | `td.energy.round._cron_open` | R-H1: для кожного слота активних шаблонів, чиє вікно містить `now` і день тижня збігається, створити обхід (якщо немає `(template, slot, date)`) | ≤ 2 с |
| `cron_td_energy_round_close` | Енергетика: закриття обходів | 15 хв | `td.energy.round._cron_close` | R-H2: `open`/`in_progress` з `due_at < now` → `missed`, подія | ≤ 2 с |
| `cron_td_energy_round_rotate` | Енергетика: ротація обходів | 7 діб, `nextcall` нд 03:40 Київ | `td.energy.round._cron_rotate` | видалити обходи старші за `keep_days` | ≤ 10 с |

## H.7 API

Нового HTTP немає; ORM-RPC від імені користувача; усі методи `api.model`, якщо не вказано інше; перевірка групи — в методі (`AccessError("Немає доступу до Енергетики.")` без `…_user`; дії — `…_manager`).

| ID | Сигнатура | Вхід → вихід | Помилки |
|---|---|---|---|
| API-H1 | `td.energy.round.get_mobile(round_id=None)` | → JSON вкладки (нижче) | `AccessError` |
| API-H2 | `td.energy.round.action_toggle_item(item_id, done, comment=None)` | → `{"round": <як get_mobile.round>}` (R-H3) | `AccessError`, `UserError("Обхід виконує %s.")`, `UserError("Обхід уже закрито.")` |
| API-H3 | `td.energy.round.action_finish(round_id, note=None)` | → `{"finished_at_local": "14:40", "deviation_count": n}` (R-H5) | `UserError("Позначте всі пункти обходу: залишилось %s.")`, `AccessError` |
| API-H4 | `td.energy.round.action_start(template_id, slot_id=None)` | ручний запуск (якщо немає відкритого обходу): створює обхід «поза розкладом» → `round_id` | `AccessError`, `UserError("Обхід уже відкритий.")` |
| API-H5 | `td.energy.round.get_journal(limit=20, offset=0)` | → `{"items": [{id, name, date, state, performer, finished_at_local, done_count, total_count, deviation_count}], "total": n}` | `AccessError` |
| API-H6 | `td.energy.round.action_cancel()` (на записі) | chief → `True` | `AccessError` |

### Відповідь API-H1

```json
{
  "meta": {"now_local": "14:20", "refresh_s": 30, "can_edit": true},
  "round": {"id": 412, "title": "Обхід ТП і ГРЩ · зміна 2", "state": "in_progress", "slot": "Зміна 2", "due_local": "23:00",
            "performer": {"id": 7, "name": "Іваненко О.", "is_me": true},
            "done_count": 2, "total_count": 6, "progress_pct": 33, "can_edit": true, "can_finish": false, "finish_blocked": "залишилось 4",
            "items": [{"id": 3011, "code": "t1", "title": "T1: огляд, температура олії", "hint": "норма до 85 °C · зараз 58 °C",
                       "done": true, "result": "ok", "value_text": "58 °C", "comment": "", "node_code": "T1", "can_3d": true},
                      {"id": 3013, "code": "swb", "title": "ГРЩ SWB-1: нагрів з'єднань", "hint": "тепловізор, точки Q1, Q2, QS",
                       "done": false, "result": "pending", "value_text": "", "comment": "", "node_code": "SWB-1", "can_3d": true}]},
  "next": null,
  "history": [{"id": 398, "title": "Обхід ТП і ГРЩ · зміна 1", "state": "done", "finished_at_local": "15:52", "done_count": 6, "total_count": 6, "deviation_count": 0, "performer": "Іваненко О."}]
}
```

Правила форми: `round = null`, `next = {"slot": "Зміна 2", "starts_local": "16:00"}` (або `null`, якщо слотів сьогодні більше немає), коли немає `open`/`in_progress` обходу; при кількох відкритих — обхід слота, що містить `now` (ранній — першим); `can_edit` — користувач `…_manager` і (виконавець порожній/це він сам/chief); `can_finish = (finish_blocked is null)`; `finish_blocked` — «залишилось N» за обов'язковими пунктами; `hint` — R-H4; `history` — `≤ history_limit` закритих (`done`/`missed`) обходів, нові першими. Розмір відповіді ≤ 10 КБ. Ключів вартості немає.

## H.9 Алгоритми та правила

### R-H1 Відкриття обходів за розкладом (FR-H2)

`_cron_open` (10 хв): `now_local`; для кожного активного шаблону та слота: `weekday ∈ slot.weekdays` і `time_from ≤ local_hour(now) < time_to` і немає запису `(template, slot, date)` → створити `td.energy.round`: `date = today`, `starts_at/due_at = to_utc(date + time_from/time_to)`, `state='open'`, `slot_name`, пункти копіюються з шаблону (**знімок**: наступні правки шаблону на створений обхід не впливають). Ідемпотентно (`UNIQUE`). Доба переходу DST — межі слота через `dates.to_utc`. Якщо крон не працював і вікно слота частково минуло — обхід створюється з колишнім `due_at`.

### R-H2 Закриття та «не виконано» (FR-H2)

`_cron_close` (15 хв): `state in (open, in_progress)` і `due_at < now` → `missed` (`finished_at = due_at`); при `td.energy_mobile.missed_event` — одна подія `td.energy.event._td_log('warn', 'round', 'ROUND-<id>', "Обхід не завершено: {name}", title=…, detail="Виконано {done}/{total}.", dedup_min=1440)` (`node` не задається); повторний прогін дублів не створює. `done`/`cancelled`/`missed` не переглядаються.

### R-H3 Відмітка пункту (FR-H3)

`action_toggle_item(item_id, done, comment=None)`:
1. Доступ: `…_manager`; обхід у `open`/`in_progress`, інакше `UserError("Обхід уже закрито.")`.
2. Блокування виконавця (`SELECT … FOR UPDATE` рядка обходу): якщо `performer_id` порожній — стає поточним користувачем, `state='in_progress'`, `started_at = now`; якщо він інший і користувач не `…_chief` — `UserError("Обхід виконує {ім'я}.")` (D-76).
3. `done=True`: `done_at = now`, `done_by = uid`, значення й результат — R-H4; `comment` (≤ 256) зберігається; `done=False`: поля скидаються (`result='pending'`, `value=0`, `value_text=''`), `event_id` не створений (події — лише при завершенні).
4. Перерахунок `done_count`, `progress_pct`, `deviation_count`; `bus.tick('state')`.
5. Повертає `{"round": <обхід як у get_mobile>}`.

### R-H4 Значення пункту та норма (FR-H3)

Джерело (`item.source`):
- `signal:<код>` — `td.signal` (через `sudo()`); значення «свіже», якщо `last_ts ≥ now − max(3·period_s, value_fresh_s)` (за замовчуванням 120 с); інакше — «немає даних»;
- `pult:<шлях>` — `td.energy.dashboard.get_pult(period='now', parts=['kpis'])`, потім обхід за точками шляху; `null` — немає даних;
- порожньо — значення немає.
**Підказка (`hint`):** без джерела — статична `hint`; з джерелом і нормою — «норма {до X | від X | X–Y} {unit} · зараз {value} {unit}» (число — за `precision`, кома як десятковий роздільник; за відсутності даних — «зараз —»); з джерелом без норми — «зараз {value} {unit}».
**Результат при відмітці:** `norm_kind='none'` або немає джерела → `ok`; немає значення (немає даних) → `ok`, `value_text = "немає даних"`; `max`: `value ≤ norm_max` → `ok`, інакше `deviation`; `min`: `value ≥ norm_min`; `range`: `norm_min ≤ value ≤ norm_max`. Граничне значення — в нормі (`85,0 ≤ 85` → `ok`; `85,1` → `deviation`; `min 60`: `59,9` → `deviation`). `value_text` — «58 °C» (за `precision`).
Приклад: T1, `temp_c = 58` → «норма до 85 °C · зараз 58 °C», при відмітці `ok`, `value_text='58 °C'`.

### R-H5 Завершення обходу (FR-H4)

`action_finish(round_id, note=None)`: виконавець або `…_chief`; стани `open`/`in_progress`. Усі пункти з `required=True` мають бути `done`, інакше `UserError("Позначте всі пункти обходу: залишилось %s.")` (N — кількість невідмічених обов'язкових). Далі: `state='done'`, `finished_at = now`, `note`; для кожного пункту з `result='deviation'` — `td.energy.event._td_log('warn', 'round', 'ROUND-<round>-<item.code>', "Обхід: {title} — поза нормою ({value_text})", node=item.node_id, dedup_min=1440)` → `item.event_id`; `message_post` («Обхід завершено: {done}/{total}, відхилень {n}»); `bus.tick('state')`. Повертає `{"finished_at_local": "HH:MM" (Київ), "deviation_count": n}`. **Збірка W4:** для кнопки «Завершити» у формі журналу додано `action_finish_form()` (безаргументна обгортка над `action_finish` для `type=object`, повертає `True`).

### R-H6 Відповідь `get_mobile` (FR-H5)

1. Вибір обходу: `open`/`in_progress` на сьогодні (спочатку слот, що містить `now`; потім за `starts_at`); немає — `round=null`, `next` — найближчий слот сьогодні за розкладом, інакше `null`.
2. Для обходу: `items` — за `sequence`; `hint` — R-H4 (значення читаються одним проходом: один `search_read` сигналів + одне звернення до `get_pult` на всі пункти); `can_edit`, `can_finish`, `finish_blocked`; `performer.is_me`.
3. `history` — останні закриті обходи шаблону (не більше `history_limit`).
4. Без звернення до вартості; розмір ≤ 10 КБ.

### R-H7 Журнал (FR-H6)

Серверне подання V-H1; `get_journal` — для мобільного «Усі обходи» (опційно). `finished_at_local` — київські `HH:MM`. Ротація — `_cron_rotate`.

### R-H8 Сумісність з оболонкою W1 (FR-H8)

Вкладка реєструється записом `td_energy.mobile_tabs` (UI-H1); оболонка `td_energy.mobile` (W1) сама малює N колонок нижньої навігації (`grid-template-columns: repeat(N, minmax(0, 1fr))`), тому за встановленого модуля — 4 колонки; без модуля — 3 (поведінка W1). Тик шини — `state` (у `tools/bus.KINDS` W1 виду `round` немає; вводити новий вид не потрібно — A-H3). Правок коду `td_energy` модуль не потребує. **Збірка W4:** вкладка реєструється завжди (`registerRoundTab()`, `{force: true}`); hoot-набір W1 (`mobile.test.js`) і AC-H18 самі знімають вкладку `round` на час перевірки трьох колонок без модуля.

## H.12 Acceptance Criteria — AC-H01…AC-H26

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-H01 | FR-H1 | Given встановлення; Then шаблон `TP-GRSH`: 2 слоти («Зміна 1» 07:00–16:00, «Зміна 2» 16:00–23:00, будні), 6 пунктів (`t1`, `t2`, `swb`, `pfc`, `dgu`, `bess`) з нормами/джерелами за H.5.2; `UNIQUE(code)`, `UNIQUE(template, item.code)`; повторний `-u` — без змін | UT |
| AC-H02 | FR-H1 | Given шаблон; When слот `time_to ≤ time_from` / перетинає північ, `weekdays` з повтором або цифрою 7, `norm_kind='max'` без `norm_max`, `source` неправильного формату; Then `ValidationError` з текстами M-H2/M-H3 | UT |
| AC-H03 | FR-H2 | Given вівторок 16:20 Київ; When `_cron_open`; Then створено обхід «Обхід ТП і ГРЩ · Зміна 2 · {DD.MM}», `state='open'`, `due_at = 23:00` (UTC), 6 пунктів-знімків; повторний прогін — без дубля (`UNIQUE`); субота — не створюється; правка шаблону не змінює створений обхід | UT |
| AC-H04 | FR-H2 | Given обхід `in_progress` (3/6) і `due_at < now`; When `_cron_close`; Then `missed`, `finished_at = due_at`, одна подія `kind='round'`, `level='warn'`; повтор без дублів; `missed_event=0` — події немає; `done` не змінюється | UT |
| AC-H05 | FR-H2 | Given доба переходу на літній/зимовий час; Then `starts_at/due_at` коректні за `dates.to_utc`; назва обходу — київська дата | UT |
| AC-H06 | FR-H3 | Given T1 з `temp_c = 58` свіжим, DGU з `fuel_pct = 78`, SWB без джерела, T2 з несвіжим сигналом; Then підказки: «норма до 85 °C · зараз 58 °C», «норма від 60 % · зараз 78 %», «тепловізор, точки Q1, Q2, QS», «норма до 85 °C · зараз —»; шлях `pult:` читає `get_pult(kpis)` (один виклик на всі пункти) | UT |
| AC-H07 | FR-H3 | Given обхід `open`; When `action_toggle_item` користувачем A, потім B, потім chief; Then A стає виконавцем (`in_progress`, `started_at`); B → `UserError("Обхід виконує A.")`; chief — успіх; закритий обхід → `UserError("Обхід уже закрито.")`; user без `…_manager` → `AccessError` | UT |
| AC-H08 | FR-H3 | Given T1 з нормою `max 85` і DGU з `min 60`; Then `temp_c = 85,0` → `ok`; `85,1` → `deviation`; `fuel 60,0` → `ok`; `59,9` → `deviation`; немає даних → `ok` з `value_text='немає даних'`; `range` — обидві межі включно | UT |
| AC-H09 | FR-H3 | Given відмічений пункт; When `done=False` до завершення; Then `result='pending'`, `value=0`, `value_text=''`, лічильники перераховані; після `done` обходу — `UserError` | UT |
| AC-H10 | FR-H4 | Given 5 із 6 обов'язкових відмічено; When `action_finish`; Then `UserError("Позначте всі пункти обходу: залишилось 1.")`; при 6/6 — `done`, `finished_at`, `finished_at_local = "HH:MM"` (Київ), повідомлення в чаттері, `bus.tick('state')`; необов'язковий пункт (`required=False`) не блокує | UT |
| AC-H11 | FR-H4 | Given два пункти з `deviation`; When `action_finish`; Then дві події `kind='round'`, `level='warn'`, `code='ROUND-<id>-<code>'`, `event_id` заповнений; повторне завершення неможливе; без відхилень — подій немає; `dedup_min` захищає від дублів | UT |
| AC-H12 | FR-H5 | Given обхід 2/6; When `get_mobile()`; Then `round.done_count=2`, `total_count=6`, `progress_pct=33`, `can_finish=false`, `finish_blocked="залишилось 4"`, `items` за `sequence`, `performer.is_me`, `history ≤ 3`; JSON ≤ 10 КБ; без ключів вартості | UT |
| AC-H13 | FR-H5 | Given немає відкритого обходу; Then `round=null`, `next = {"slot": "Зміна 2", "starts_local": "16:00"}` (або `null` після останнього слота), `history` останні закриті; при двох відкритих — обхід слота, що містить `now` | UT |
| AC-H14 | FR-H5 | Given користувач без груп енергетики / `…_user` / виконавець / інший manager; Then `AccessError` / `can_edit=false` / `can_edit=true` / `can_edit=false` з банером «Обхід виконує {ім'я}» (chief — `can_edit=true`) | UT |
| AC-H15 | FR-H5 | Given hoot з моком API-H1; Then запис реєстру `round` (sequence 40, label «Обхід», без `badge`); компонент малює заголовок, лічильник «2 / 6», смугу прогресу (ширина 33 %), 6 рядків, чекбокс викликає `action_toggle_item` (оптимістично, відкат при помилці); «Завершити обхід» неактивна візуально й показує тост «Позначте всі пункти обходу: залишилось 4»; при 6/6 — основна і після успіху тост «Обхід завершено й записано в журнал о 14:40» | UT-JS |
| AC-H16 | FR-H6 | Given журнал; Then list/search/pivot відкриваються; `…_user` і `…_manager` лише читають (запис — методами); видалення — `td_factory3d.group_td_admin`; фільтри «Сьогодні», «Мої», «Не виконані», «З відхиленнями» дають очікувані вибірки | UT |
| AC-H17 | FR-H7 | Given ACL і record rules; Then `…_user` читає, `…_manager` створює/пише обходи й пише пункти лише через методи, `…_chief` править шаблони та скасовує/завершує чужі, `admin` — усе; обходи іншої компанії не видно | UT |
| AC-H18 | FR-H8 | Given встановлені `td_energy` і `td_energy_mobile`; Then `registry td_energy.mobile_tabs` містить `state`, `alarms`, `scheme`, `round` у порядку `sequence` 10, 20, 30, 40; навігація — 4 колонки; без модуля — 3 (регресія W1); вкладка `round` реєструється завжди, тому тест сам знімає її на час перевірки «без модуля» й повертає (`{force: true}`) | UT-JS |
| AC-H19 | FR-H8 | Given viewport 390 × 844, стенд; When пройти «Стан» → «Тривоги» («Беру в роботу») → «Схема» → «Обхід» (відмітити всі, «Завершити»); Then 4 вкладки без горизонтального прокручування, кнопки ≥ 48 px (перевірка `getBoundingClientRect`), лічильник «Тривоги · N» зменшується, тост після завершення, запис з'являється в журналі | TC (ТК-H1) |
| AC-H20 | FR-H8 | Given дві сесії A і B; When A відмічає пункт; Then B ≤ 10 с бачить «Обхід виконує A» (лише читання) за тиком шини `state`; B не може відмітити; після завершення A — B бачить обхід в «Останніх» | TC (ТК-H2) |
| AC-H21 | FR-H9 | Given `neutralize.sql`, `uninstall_hook`; Then 3 крони неактивні; `uninstall` переводить події `kind='round'` у `manual`, решта даних `td_energy` цілі; `-u` ідемпотентний | UT + DEPLOY_TEST |
| AC-H22 | FR-H9 | Given `res.config.settings`; Then параметри `td.energy_mobile.*` редагує `…_manager`; `history_limit` змінює розмір `history`; `value_fresh_s` — вікно свіжості значення | UT |
| AC-H23 | FR-H10 | Given БД із 730 днями обходів (≈ 520 обходів/рік × 6 пунктів); Then `get_mobile` ≤ 250 мс, `action_toggle_item` ≤ 150 мс, `action_finish` ≤ 300 мс, ≤ 15 SQL на `get_mobile`; ротація ≤ 10 с | UT (ТП-H1, ТП-H2) |
| AC-H24 | FR-H4 | Given завершення о 14:40 Київ (11:40 UTC); Then `finished_at_local = "14:40"` у відповіді й у журналі; серверний час UTC не «протікає» в UI | UT |
| AC-H25 | FR-H3 | Given пункт з `node_id` (T1) і без нього; Then `can_3d` true/false; клік «Де це в 3D» викликає `useEnergyActions().show3d("T1")`; пункт без вузла — кнопка прихована | UT-JS |
| AC-H26 | FR-H2 | Given `td_energy_mobile` і ручний запуск; When `action_start(template_id)` за відсутності відкритого обходу; Then створено обхід «поза розкладом» (`slot_id` порожній, `due_at = now + 2 год`); при вже відкритому — `UserError("Обхід уже відкритий.")`; лише `…_manager`; серверна дія V-H4 викликає `action_start_now()` (перший шаблон без відкритого обходу) | UT |

**Разом `td_energy_mobile`: AC-H01…AC-H26 = 26 критеріїв** (UT 20, UT-JS 3 (AC-H15, AC-H18, AC-H25), TC 2 (AC-H19, AC-H20), UT + DEPLOY_TEST 1 (AC-H21)).

## H.13 План тестування (для Opus)

- Фікстури: `tests/common.py` (C): `TestWHCommon` — `_template()` (шаблон макета), `_signal(code, value, ts)`, `_pult_patch(fuel_pct)`, `_round(slot, state)`, `_user(groups)`, мок часу `patch("odoo.addons.td_energy.tools.dates.now_utc")`.
- Юніт-тести (C): `test_wh_template.py::TestWHTemplate` — AC-H01, AC-H02; `test_wh_schedule.py::TestWHSchedule` — AC-H03…AC-H05, AC-H26; `test_wh_value.py::TestWHValue` — AC-H06, AC-H08; `test_wh_round.py::TestWHRound` — AC-H07, AC-H09…AC-H11, AC-H24; `test_wh_api.py::TestWHApi` — AC-H12…AC-H14, AC-H16, AC-H22, AC-H23; `test_wh_security.py::TestWHSecurity` — AC-H17, AC-H21, ТБ-H1, ТБ-H2; `test_wh_ui.py::TestWHUi` (HttpCase: вкладка відкривається без JS-помилок); `test_wh_hoot.py::TestWHHoot.test_hoot_suite` — AC-H15, AC-H18, AC-H25.
- Стенд `tests/stand/test_wh_tk.py` (Playwright, viewport 390 × 844):

| ТК | Назва | Кроки | Очікується |
|---|---|---|---|
| ТК-H1 | Екран загалом | відкрити «Чергування (телефон)»; «Тривоги» → «Беру в роботу»; «Схема»; «Обхід»: відмітити 6 пунктів, «Завершити обхід»; відкрити «Журнал обходів» у десктопі | AC-H19: 4 вкладки, кнопки ≥ 48 px, тост «Обхід завершено…», запис у журналі, подія для відхилень |
| ТК-H2 | Дві сесії | A відмічає; B відкриває вкладку «Обхід» | AC-H20 |
| ТК-H3 | Прострочений слот | не завершити обхід; зсунути час/дочекатися `cron_close` (або викликати `_cron_close` з моком часу) | обхід `missed`, попередження в «Події», в «Останніх обходах» статус «Не виконано» |

- Тести безпеки: ТБ-H1 — користувач без груп/`…_user` не викликає `action_toggle_item`/`action_finish`; ТБ-H2 — чужий обхід не можна змінити без chief (AC-H07, AC-H17).
- Продуктивність: ТП-H1 — `get_mobile` ≤ 250 мс; ТП-H2 — `action_toggle_item` ≤ 150 мс (AC-H23).
- DEPLOY_TEST: копія демо-БД → `-i td_energy_mobile` → шаблон (1/2/6) → `_cron_open` → вкладка на 390 px → `uninstall` (події `round` → `manual`).

## H.14 Definition of Done (`td_energy_mobile`)

Усі UT/UT-JS AC-H01…AC-H26 зелені; ТК-H1…ТК-H3 пройдені; `ruff` без помилок; регресія `td_energy` (зокрема мобільний W1: 3 вкладки без модуля) зелена; `neutralize.sql`, CHANGELOG, README («Чергування», «Обхід»), DEPLOY_TEST; скриншоти чотирьох вкладок на 390 × 844.

## H.15 Відкриті питання та рішення автора

| ID | Питання | Кому | Рекомендація | Що робимо тим часом |
|---|---|---|---|---|
| Q-H1 | Реальні чек-листи обходів (пункти, норми температури олії T1/T2, періодичність, зміни) | електрики, головний енергетик | затвердити шаблон за макетом, потім уточнити норми й періодичність | демо-шаблон макета (H.5.2) |
| Q-H2 | Чи вважати невиконаний обхід тривогою («Події») | замовник | так, попередження рівня `warn` | увімкнено (`missed_event=1`) |
| Q-H3 | Хто може виконувати обходи (окрема роль «чергувальний»?) | замовник | група «Енергетик» | `group_td_energy_manager` |

| ID | Рішення | Обґрунтування |
|---|---|---|
| A-H1 | Окремий модуль `td_energy_mobile` (залежить лише від `td_energy`), а не частина `td_energy` чи `td_energy_analytics` | обхід — операційний функціонал; необов'язковий для клієнтів без чергових; майбутній дім для Web Push/PWA (Q-08); не чіпає 142 тести `td_energy`; GAP теж пропонував окремий модуль |
| A-H2 | Пункти обходу — знімок шаблону на момент створення; значення «зараз» беруться з `td.signal` або `get_pult` (`pult:`-шлях), без залежності від `td_genset` | паливо ДГУ — не сигнал; контракт W1 C-30 |
| A-H3 | Тик шини — вид `state` (наявний), новий вид не вводиться | `tools/bus.KINDS` W1 фіксований; зміни W1 не потрібні |
| A-H4 | Виконавець обходу блокується за першим, хто відмітив; `chief` може завершити/перехопити | кілька чергових на зміні; без втрати даних |
| A-H5 | Подія `kind='round'` на відхилення й прострочення (`selection_add` в `td.energy.event`) | видимість у «Подіях» і Пульті; відкат при деінсталяції |
| A-H6 | Розклад — слоти в шаблоні, а не календар змін | незалежність від W3/W4 і календаря; зміни макета — демо-дані |

## Журнал змін документа

| Дата | Версія | Зміна |
|---|---|---|
| 18.10.2026 | 0.1 | Перша редакція (`build/energy/W4_SPEC.md`, хвиля W4; Частина II) |
| 19.10.2026 | 0.2 | Переклад українською; виокремлено в самостійний документ модуля (преамбула повторена з [../td_energy_analytics/SPEC.md](../td_energy_analytics/SPEC.md)); рішення й відхилення збірки W4 (нижче) |

### Рішення й відхилення, прийняті при збірці W4 (`td_energy_mobile`)

Код: гілка `claude/td-energy-w4`. Відхилення внесено в текст відповідних розділів із позначкою «**Збірка W4**».

1. **Вкладка «Обхід» реєструється завжди.** `registerRoundTab()` викликає `mobileTabs.add("round", ROUND_TAB, {force: true})` без перевірки сторінки тестів (commit 105dbd3). Hoot-набір W1 (`mobile.test.js`) і AC-H18 самі знімають вкладку `round` на час перевірки «без модуля» й повертають її (UI-H1, R-H8, AC-H18).
2. **`action_finish_form()`** — безаргументна обгортка над `action_finish(self.id)` для кнопки «Завершити» у формі журналу (`type=object`, повертає `True`; V-H1, R-H5).
3. **`action_start_now()`** — серверна дія V-H4 «Запустити обхід зараз»: перший активний шаблон без відкритого обходу, `action_start(template.id)`, повертає `ir.actions.act_window` на форму обходу; за відсутності вільного шаблону — `UserError("Обхід уже відкритий.")`; право `…_manager` (V-H4, AC-H26).
4. **Нумерація D-xx:** D-70…D-78 належать документу W4 (мобільний); діапазони W2 і W3 перетинаються між собою, у модульних документах D-xx діє в межах свого документа.

Не виконано: окремий файл DEPLOY_TEST модуля не створено (AC-H21 — `UT + DEPLOY_TEST`, виконується вручну за сценарієм H.13); Web Push і PWA — поза обсягом (Q-08).

