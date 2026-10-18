> **Размещение (W4, каркас 6.0).** Копия из `build/energy/W4_SPEC.md` (18.10.2026): общая преамбула (строки 1–64: обозначения, диапазоны ID, отклонения D-51…D-80) и Часть II — разделы H.0–H.15 модуля `td_energy_mobile`. Связанный модуль — `td_energy_analytics` (`docs/modules/td_energy_analytics/SPEC.md`).
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


# ЧАСТЬ II. `td_energy_mobile` — мобильный экран «Чергування»: вкладка «Обхід» и журнал

Мобильный экран целиком (`td_energy.mobile`, W1 UI-09) состоит из четырёх вкладок. Вкладки «Стан», «Тривоги», «Схема» реализованы в W1 (`td_energy`); модуль `td_energy_mobile` добавляет четвёртую — **«Обхід»** — через реестр `registry.category("td_energy.mobile_tabs")` (контракт C-33, код `static/src/mobile/mobile.js`: запись `{id, label, sequence, component, [title], [badge(mobile)], [icon]}`, компонент получает props `{mobile, meta, capabilities, reload, goTab}`), а также журнал обходов и сервисные данные. Приёмка «экрана целиком» — таблица H.3.1 и ТК-H1…ТК-H3.

## H.0 Дерево файлов

Владелец — **C** (ARCH §6). Файлы без буквы — менеджер (каркас).

```
odoo_addons/td_energy_mobile/
├── __manifest__.py                        (менеджер) раздел H.1
├── __init__.py                            (менеджер) from . import models; from .hooks import post_init_hook, uninstall_hook
├── hooks.py                               C  post_init_hook: _seed_template (идемпотентно); uninstall_hook: kind 'round' → 'manual'
├── models/
│   ├── __init__.py                        (менеджер)
│   ├── td_energy_round_template.py        C  M-H1, M-H2, M-H3
│   ├── td_energy_round.py                 C  M-H4, M-H5 (+ API-H1…API-H6, крон)
│   ├── td_energy_event.py                 C  M-H6 (`_inherit td.energy.event`: selection_add 'round')
│   └── res_config_settings.py             C  M-H7
├── tools/
│   ├── value.py                           C  R-H4 (источники значений, нормы)
│   └── schedule.py                        C  R-H1, R-H2 (слоты, окна, DST)
├── data/
│   ├── round_template_data.xml            C  шаблон «Обхід ТП і ГРЩ» (6 пунктов, 2 слота; noupdate=1)
│   ├── ir_config_parameter.xml            C  параметры (разд. H.5)
│   ├── ir_cron.xml                        C  3 крона (разд. H.6)
│   └── neutralize.sql                     C
├── security/
│   ├── td_energy_mobile_security.xml      C  record rules
│   └── ir.model.access.csv                C  M-H1…M-H5
├── static/src/mobile_round/               C  UI-H1…UI-H4: round.js, round.xml, round.scss; регистрация вкладки
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

## H.1 Манифест

`name`: «Чергування (телефон)»; `version`: `19.0.1.0.0`; `depends`: `["td_energy"]` (транзитивно `maintenance`, `bus`, `mail`); `data` (порядок): `security/td_energy_mobile_security.xml`, `security/ir.model.access.csv`, `data/ir_config_parameter.xml`, `data/round_template_data.xml`, `data/ir_cron.xml`, `views/td_energy_round_views.xml`, `views/menus.xml`; `assets`: `web.assets_backend`: `td_energy_mobile/static/src/mobile_round/**`, `web.assets_unit_tests`: `td_energy_mobile/static/tests/**`; `post_init_hook`: `hooks.post_init_hook`; `uninstall_hook`: `hooks.uninstall_hook`. Порядок загрузки ассетов: после `td_energy` (реестр `td_energy.mobile_tabs` уже создан модулем `td_energy`).

## H.2 Модели

### M-H1 `td.energy.round.template` — шаблон обхода (FR-H1)

`_name = "td.energy.round.template"`, `_description = "Енергетика: шаблон обходу"`, `_order = "sequence, id"`.

| Поле | Тип | Параметры |
|---|---|---|
| `name` | Char | size=64, req («Обхід ТП і ГРЩ») |
| `code` | Char | size=32, req, `UNIQUE(code)` |
| `sequence` | Integer | default 10 |
| `active` | Boolean | default True |
| `slot_ids` | One2many `td.energy.round.slot` | расписание (M-H2) |
| `item_ids` | One2many `td.energy.round.template.item` | пункты (M-H3) |
| `note` | Text | |
| `company_id` | Many2one `res.company` | req, default `env.company` |

### M-H2 `td.energy.round.slot` — слот расписания

| Поле | Тип | Параметры |
|---|---|---|
| `template_id` | Many2one | req, ondelete=cascade |
| `name` | Char | size=32, req («Зміна 2») |
| `time_from`, `time_to` | Float | req; часы суток (7,0 — 07:00); constraint `0 ≤ time_from < time_to ≤ 24` («Слот не може перетинати північ.») |
| `weekdays` | Char | size=13, default `0,1,2,3,4` (пн = 0); constraint — список цифр 0…6 без повторов |
| `sequence` | Integer | default 10 |

### M-H3 `td.energy.round.template.item` — пункт шаблона

| Поле | Тип | Параметры |
|---|---|---|
| `template_id` | Many2one | req, ondelete=cascade |
| `sequence` | Integer | default 10 |
| `code` | Char | size=16, req; `UNIQUE(template_id, code)` |
| `title` | Char | size=128, req |
| `hint` | Char | size=128, «Підказка (без норми)» |
| `source` | Char | size=96, «Джерело значення»: `signal:<код сигналу>` или `pult:<шлях JSON у get_pult(kpis)>` (напр. `pult:kpis.generation.genset.fuel_pct`); пусто — без значення |
| `norm_kind` | Selection | `none`, `max`/«до», `min`/«від», `range`/«діапазон»; default `none` |
| `norm_min`, `norm_max` | Float | границы нормы |
| `unit` | Char | size=16 («°C», «%») |
| `precision` | Integer | default 0, знаков после запятой в подсказке |
| `node_id` | Many2one `td.energy.node` | для «Де це в 3D» |
| `required` | Boolean | default True |

Constraints: `source` — формат `^(signal|pult):.+$` или пусто; `norm_kind='max'` ⇒ `norm_max`, `'min'` ⇒ `norm_min`, `'range'` ⇒ `norm_min ≤ norm_max` (`ValidationError("Норма пункту «%s» некоректна.")`).

### M-H4 `td.energy.round` — обход (экземпляр; FR-H2…FR-H4)

`_name = "td.energy.round"`, `_description = "Енергетика: обхід"`, `_inherit = ["mail.thread"]`, `_order = "date desc, starts_at desc, id desc"`.

| Поле | Тип | Параметры |
|---|---|---|
| `name` | Char | compute store: «{template.name} · {slot.name} · {DD.MM}» |
| `template_id` | Many2one | req, idx, ondelete=restrict |
| `slot_id` | Many2one `td.energy.round.slot` | ondelete=set null |
| `slot_name` | Char | snapshot имени слота |
| `date` | Date | req, idx (Киев) |
| `starts_at`, `due_at` | Datetime | req (UTC): начало и конец слота |
| `state` | Selection | `open`/«Відкритий», `in_progress`/«У роботі», `done`/«Завершено», `missed`/«Не виконано», `cancelled`/«Скасовано»; default `open`, idx, tracking |
| `performer_id` | Many2one `res.users` | исполнитель (первый отметивший), readonly |
| `started_at`, `finished_at` | Datetime | readonly |
| `item_ids` | One2many `td.energy.round.item` | |
| `total_count`, `done_count` | Integer | compute store |
| `progress_pct` | Integer | compute store: `round(done/total·100)` (0 при `total = 0`) |
| `deviation_count` | Integer | compute store: пунктов с `result='deviation'` |
| `note` | Char | size=256 |
| `company_id` | Many2one `res.company` | req, default `env.company` |

`UNIQUE(template_id, slot_id, date)`. Методы — API-H1…API-H6.

### M-H5 `td.energy.round.item` — пункт обхода

| Поле | Тип | Параметры |
|---|---|---|
| `round_id` | Many2one | req, idx, ondelete=cascade |
| `sequence`, `code`, `title`, `hint` | — | снимок шаблона на момент создания |
| `source`, `norm_kind`, `norm_min`, `norm_max`, `unit`, `precision`, `required` | — | снимок |
| `node_id` | Many2one `td.energy.node` | снимок |
| `done` | Boolean | default False |
| `done_at` | Datetime | readonly |
| `done_by` | Many2one `res.users` | readonly |
| `value` | Float | значение в момент отметки (снимок) |
| `value_text` | Char | size=32: «58 °C» или «немає даних» |
| `result` | Selection | `pending`/«Очікує», `ok`/«У нормі», `deviation`/«Поза нормою»; default `pending` |
| `comment` | Char | size=256 |
| `event_id` | Many2one `td.energy.event` | ondelete=set null, readonly |
| `request_id` | Many2one `maintenance.request` | ondelete=set null |

### M-H6 `td.energy.event` — расширение

`kind` получает значение `("round", "Обхід")` (`selection_add`, `ondelete={"round": lambda recs: recs.write({"kind": "manual"})}` — при удалении модуля события переводятся в `manual`; `uninstall_hook` дублирует это как страховку).

### M-H7 `res.config.settings` — расширение

Поля `td_energy_mobile_*` с `config_parameter` (разд. H.5); блок «Чергування» в `td_energy` (V-H5).

## H.3 Представления и мобильный экран

### H.3.1 Мобильный экран целиком (карта и приёмка)

Экран — клиентская действие `td_energy.mobile` (`action_td_energy_mobile`, меню «Енергетика → Чергування (телефон)»), адаптивный ≥ 360 px (эталон 390 × 844), кнопки ≥ 48 px, данные — ORM-RPC + шина `td_energy`. Вход «на телефон»: адрес `/odoo/action-td_energy.action_td_energy_mobile` и стандартная установка PWA Odoo («Додати на головний екран»); Web Push не входит (Q-08).

| № | Элемент (макет `Mobile.dc.html`) | Где реализован | Источник данных | AC |
|---|---|---|---|---|
| 1 | Шапка: «Енергетика · чергування», название вкладки, чип времени `HH:MM` (живое/частичное/устаревшее) | `td_energy` (W1) | `get_mobile().meta` | W1 AC-145, AC-146 |
| 2 | Вкладка «Стан»: «З мережі» кВт и %, полоса, плитки СЕС / BESS / ДГУ·АВР / cos φ, блок «Активні» | `td_energy` (W1) | `get_mobile().state` | W1 AC-146 |
| 3 | Вкладка «Тривоги · N»: карточки (Беру в роботу, Де це в 3D, Відкласти, Призначити на себе), «Інфо за сьогодні» | `td_energy` (W1) | `get_mobile().alarms` | W1 AC-146 |
| 4 | Вкладка «Схема»: вузли со статусом | `td_energy` (W1) | `get_mobile().scheme` | W1 AC-146 |
| 5 | **Вкладка «Обхід»:** заголовок «Обхід ТП і ГРЩ · {зміна}», счётчик «{done} / {total}», полоса прогресса, пункты (чекбокс 22 px, название, подсказка с нормой и значением), «Завершити обхід» | `td_energy_mobile` | `td.energy.round.get_mobile()` | AC-H12…AC-H15, AC-H19 |
| 6 | Нижняя навигация из 4 колонок (Стан, Тривоги · N, Схема, Обхід), активная — акцентом | `td_energy` (оболочка, реестр) + `td_energy_mobile` (запись) | `registry td_energy.mobile_tabs` | AC-H18 |
| 7 | Тост-уведомления («Обхід завершено й записано в журнал о 14:40», «Позначте всі пункти обходу: залишилось N») | `td_energy` (`useEnergyActions().notify`) + `td_energy_mobile` | ответ `action_finish`/клиент | AC-H15, AC-H24 |
| 8 | «Де це в 3D» у пункта обхода | `td_energy_mobile` через `useEnergyActions().show3d(node_code)` | `item.node_code`, `can_3d` | AC-H25 |

Сквозная приёмка — ТК-H1 (все четыре вкладки в одном сценарии), ТК-H2 (две сессии), ТК-H3 (просроченный слот).

### H.3.2 Представления V-H1…V-H6

| ID | XML-id (`td_energy_mobile.`) | Тип / модель | Структура |
|---|---|---|---|
| V-H1 | `view_td_energy_round_list` / `_form` / `_search` / `_pivot`, `action_td_energy_round` | `td.energy.round` | **Журнал обходів.** list (readonly): `date`, `name`, `slot_name`, `state` (badge: open — info, in_progress — warning, done — success, missed — danger, cancelled — muted), `performer_id`, `finished_at`, `done_count`/`total_count` (progressbar), `deviation_count` (decoration danger при > 0); form: статусбар `state`, шапка (шаблон, слот, дата, исполнитель, начало/конец), вкладка «Пункти» (`item_ids`: название, `done`, `value_text`, `result`, `comment`, `event_id`, `request_id`), `note`, чаттер; кнопки «Завершити» (`action_finish`, chief), «Скасувати» (chief); search: «Сьогодні», «Мої» (`performer_id = uid`), «Не виконані» (`state='missed'`), «З відхиленнями» (`deviation_count > 0`), группировка `state`, `template_id`, `performer_id`, `date:month`; pivot: строки `date:week`, столбцы `state`, мера `count`; доступ read-only для `…_user`/`…_manager`, запись — через методы |
| V-H2 | `view_td_energy_round_template_list` / `_form`, `action_td_energy_round_template` | `td.energy.round.template` | form: `name`, `code`, `active`, вкладки «Слоти» (editable list `name`, `time_from`, `time_to`, `weekdays`), «Пункти» (editable list всех полей M-H3), `note`; редактирование — `group_td_energy_chief` и `td_factory3d.group_td_admin` |
| V-H3 | `view_td_energy_round_item_list` | `td.energy.round.item` | readonly list для отчётов (`round_id`, `title`, `value_text`, `result`, `comment`), фильтр «Відхилення» |
| V-H4 | `action_td_energy_round_open` (server action) | `ir.actions.server` | «Запустити обхід зараз» (`td.energy.round.action_start`) для чергового без автослота; `group_td_energy_manager` |
| V-H5 | `res_config_settings_view_form_td_energy_mobile` (наследует `td_energy.res_config_settings_view_form_td_energy`) | form | группа «Чергування»: `td_energy_mobile_keep_days`, `…_value_fresh_s`, `…_missed_event`, `…_history_limit` |
| V-H6 | `views/menus.xml` | `ir.ui.menu` | таблица H.3.3 |

### H.3.3 Меню

| XML-id (`td_energy_mobile.`) | Название | Родитель | seq | Группы | Действие |
|---|---|---|---|---|---|
| `menu_td_energy_round` | Журнал обходів | `td_energy.menu_td_energy` | 76 | `td_energy.group_td_energy_user` | `action_td_energy_round` |
| `menu_td_energy_round_template` | Шаблони обходів | `td_energy.menu_td_energy_config` | 70 | `…group_td_energy_chief` | `action_td_energy_round_template` |
| `menu_td_energy_round_open` | Запустити обхід зараз | `td_energy.menu_td_energy_config` | 71 | `…group_td_energy_manager` | `action_td_energy_round_open` |

### H.3.4 Клиентские компоненты UI-H1…UI-H4

| ID | Компонент | Содержимое и поведение |
|---|---|---|
| UI-H1 | `MobileRound` (запись реестра `td_energy.mobile_tabs`: `{id: "round", label: "Обхід", title: "Обхід", sequence: 40, component: MobileRound, icon: "M9 4h6M9 4a2 2 0 0 0-2 2H5v15h14V6h-2a2 2 0 0 0-2-2M9 12l2 2 4-4"}`; `badge` не задаётся — D-78) | Вкладка: загрузка `orm.call("td.energy.round", "get_mobile", [])` (`onWillStart`, после действий и по тику шины `state`, `useEnergyBus(cb, ["state"])`), состояния: «Завантаження», ошибка («Не вдалося завантажити: …», кнопка «Повторити»), «немає обходу» (D-74), обход. Заголовок: «{template} · {slot}» слева, счётчик «{done} / {total}» справа; полоса прогресса высотой 6 px (`#714B67`, ширина `progress_pct`); баннер «Обхід виконує {ім'я}» (только чтение) |
| UI-H2 | `RoundItem` | Строка-кнопка `<label>` минимальной высоты 44 px: чекбокс 22 px (`accent-color: #714B67`), название (вес 500), подсказка 12,5 px; при `result='deviation'` — чип «поза нормою» и поле комментария (необязательно); «Де це в 3D» — кнопка 48 px, если `can_3d`; отметка вызывает `action_toggle_item(item_id, done)` с оптимистичным обновлением и откатом при ошибке |
| UI-H3 | `RoundFinish` | Кнопка «Завершити обхід» (≥ 48 px): при `finish_blocked` — серая (`aria-disabled="true"`), клик показывает тост «Позначте всі пункти обходу: залишилось {N}» (D-72); при готовности — основная; успех → тост «Обхід завершено й записано в журнал о {finished_at_local}», перезагрузка вкладки |
| UI-H4 | `RoundHistory` | Секция «Останні обходи» (≤ `history_limit`, по умолчанию 3): дата, название смены, статус, `done/total`, отклонения; показывается в состоянии «немає обходу» и под текущим обходом (свёрнуто) |

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

### H.4.2 Группы и правила

Новых групп нет: «Енергетик» (`group_td_energy_manager`) выполняет обходы (отмечает пункты, завершает свой обход, запускает вручную); «Головний енергетик» (`…_chief`) правит шаблоны, завершает/отменяет чужие обходы; `…_user` — читает журнал. Запись в `td.energy.round.item` выполняют **методы** (`sudo()` после проверки группы и исполнителя), а не прямой `write` клиента. Record rules: `td_energy_round_rule_company`, `td_energy_round_template_rule_company` — `['|', ('company_id','=',False), ('company_id','in',company_ids)]`, глобальные.

## H.5 Данные

### H.5.1 `data/ir_config_parameter.xml` (`noupdate="1"`) — `td.energy_mobile.*`

| Ключ | По умолчанию | Назначение |
|---|---|---|
| `td.energy_mobile.keep_days` | `730` | хранение обходов (ротация) |
| `td.energy_mobile.value_fresh_s` | `120` | значение сигнала «свежее», если не старше (с); при `3·period_s` больше — берётся оно |
| `td.energy_mobile.missed_event` | `1` | создавать `td.energy.event` при `missed` |
| `td.energy_mobile.history_limit` | `3` | число «останніх обходів» в ответе |

### H.5.2 Шаблон `data/round_template_data.xml` (`noupdate="1"`; из макета `Mobile.dc.html`, `roundItems`)

Шаблон `round_tpl_tp_grsh` (`code='TP-GRSH'`, «Обхід ТП і ГРЩ»), слоты: «Зміна 1» 07:00–16:00 и «Зміна 2» 16:00–23:00, `weekdays=0,1,2,3,4` (смены макета, Q-H1). Пункты:

| code | title | hint | source | norm | unit | node |
|---|---|---|---|---|---|---|
| `t1` | T1: огляд, температура масла | — | `signal:energy/transformers/T1/temp_c` | `max` 85 | °C | `T1` |
| `t2` | T2: огляд, температура масла | — | `signal:energy/transformers/T2/temp_c` | `max` 85 | °C | `T2` |
| `swb` | ГРЩ SWB-1: нагрів з'єднань | тепловізор, точки Q1, Q2, QS | — | `none` | — | `SWB-1` |
| `pfc` | Компенсація PFC-1 і PFC-2 | ступені, контактори, запобіжники | — | `none` | — | `PFC-1` |
| `dgu` | ДГУ: паливо, підігрів, акумулятор | — | `pult:kpis.generation.genset.fuel_pct` | `min` 60 | % | `ATS-1` |
| `bess` | BESS: стан, вентиляція шафи | журнал помилок інвертора | — | `none` | — | `BESS` |

Узлы отсутствуют — `node_id` пуст, пункт остаётся (кнопки 3D нет). Источники — `energy/transformers/T*/temp_c` (W1 R-29), паливо ДГУ — KPI моста `td_genset_factory3d` (`kpis.generation.genset.fuel_pct`, W1 API-05). Все — **ПРИПУЩЕННЯ** по составу пунктов до согласования с электриками (Q-H1).

### H.5.3 `post_init_hook` и миграция

`_seed_template(env)` — загружает шаблон, если нет `code='TP-GRSH'` (XML `noupdate`, функция лишь проверяет); создаёт крон-записи; ничего не создаёт в обходах. Ожидаемо на демо-БД: шаблонов 1, слотов 2, пунктов 6, параметров +4, обходов 0 до первого крона.

### H.5.4 `uninstall_hook`

Переводит `td.energy.event.kind='round'` в `manual`; снимает собственные крон-записи и параметры; таблицы модуля удаляются штатно (журнал обходов теряется — при необходимости экспортируется перед удалением). Остальные данные `td_energy` не затрагиваются.

## H.6 Крон-задачи

Все — `user_id=base.user_root`, `try/except`; при `td.energy.read_enabled = False` не действуют.

| XML-id | Название | Интервал | Метод | За один прогон | Лимит |
|---|---|---|---|---|---|
| `cron_td_energy_round_open` | Енергетика: відкриття обходів | 10 мин | `td.energy.round._cron_open` | R-H1: для каждого слота активных шаблонов, чьё окно содержит `now` и день недели совпадает, создать обход (если нет `(template, slot, date)`) | ≤ 2 с |
| `cron_td_energy_round_close` | Енергетика: закриття обходів | 15 мин | `td.energy.round._cron_close` | R-H2: `open`/`in_progress` с `due_at < now` → `missed`, событие | ≤ 2 с |
| `cron_td_energy_round_rotate` | Енергетика: ротація обходів | 7 сут, `nextcall` вс 03:40 Киев | `td.energy.round._cron_rotate` | удалить обходы старше `keep_days` | ≤ 10 с |

## H.7 API

Нового HTTP нет; ORM-RPC от имени пользователя; все методы `api.model`, если не указано иное; проверка группы — в методе (`AccessError("Немає доступу до Енергетики.")` без `…_user`; действия — `…_manager`).

| ID | Сигнатура | Вход → выход | Ошибки |
|---|---|---|---|
| API-H1 | `td.energy.round.get_mobile(round_id=None)` | → JSON вкладки (ниже) | `AccessError` |
| API-H2 | `td.energy.round.action_toggle_item(item_id, done, comment=None)` | → `{"round": <как get_mobile.round>}` (R-H3) | `AccessError`, `UserError("Обхід виконує %s.")`, `UserError("Обхід уже закрито.")` |
| API-H3 | `td.energy.round.action_finish(round_id, note=None)` | → `{"finished_at_local": "14:40", "deviation_count": n}` (R-H5) | `UserError("Позначте всі пункти обходу: залишилось %s.")`, `AccessError` |
| API-H4 | `td.energy.round.action_start(template_id, slot_id=None)` | ручной запуск (если нет открытого обхода): создаёт обход «поза розкладом» → `round_id` | `AccessError`, `UserError("Обхід уже відкритий.")` |
| API-H5 | `td.energy.round.get_journal(limit=20, offset=0)` | → `{"items": [{id, name, date, state, performer, finished_at_local, done_count, total_count, deviation_count}], "total": n}` | `AccessError` |
| API-H6 | `td.energy.round.action_cancel()` (на записи) | chief → `True` | `AccessError` |

### Ответ API-H1

```json
{
  "meta": {"now_local": "14:20", "refresh_s": 30, "can_edit": true},
  "round": {"id": 412, "title": "Обхід ТП і ГРЩ · зміна 2", "state": "in_progress", "slot": "Зміна 2", "due_local": "23:00",
            "performer": {"id": 7, "name": "Іваненко О.", "is_me": true},
            "done_count": 2, "total_count": 6, "progress_pct": 33, "can_edit": true, "can_finish": false, "finish_blocked": "залишилось 4",
            "items": [{"id": 3011, "code": "t1", "title": "T1: огляд, температура масла", "hint": "норма до 85 °C · зараз 58 °C",
                       "done": true, "result": "ok", "value_text": "58 °C", "comment": "", "node_code": "T1", "can_3d": true},
                      {"id": 3013, "code": "swb", "title": "ГРЩ SWB-1: нагрів з'єднань", "hint": "тепловізор, точки Q1, Q2, QS",
                       "done": false, "result": "pending", "value_text": "", "comment": "", "node_code": "SWB-1", "can_3d": true}]},
  "next": null,
  "history": [{"id": 398, "title": "Обхід ТП і ГРЩ · зміна 1", "state": "done", "finished_at_local": "15:52", "done_count": 6, "total_count": 6, "deviation_count": 0, "performer": "Іваненко О."}]
}
```

Правила формы: `round = null`, `next = {"slot": "Зміна 2", "starts_local": "16:00"}` (или `null`, если слотов сегодня больше нет), когда нет `open`/`in_progress` обхода; при нескольких открытых — обход слота, содержащего `now` (ранний — первым); `can_edit` — пользователь `…_manager` и (исполнитель пуст/он сам/chief); `can_finish = (finish_blocked is null)`; `finish_blocked` — «залишилось N» по обязательным пунктам; `hint` — R-H4; `history` — `≤ history_limit` закрытых (`done`/`missed`) обходов, новые первыми. Размер ответа ≤ 10 КБ. Ключей стоимости нет.

## H.9 Алгоритмы и правила

### R-H1 Открытие обходов по расписанию (FR-H2)

`_cron_open` (10 мин): `now_local`; для каждого активного шаблона и слота: `weekday ∈ slot.weekdays` и `time_from ≤ local_hour(now) < time_to` и нет записи `(template, slot, date)` → создать `td.energy.round`: `date = today`, `starts_at/due_at = to_utc(date + time_from/time_to)`, `state='open'`, `slot_name`, пункты копируются из шаблона (**снимок**: последующие правки шаблона на созданный обход не влияют). Идемпотентно (`UNIQUE`). Сутки перехода DST — границы слота через `dates.to_utc`. Если крон не работал и окно слота частично прошло — обход создаётся с прежним `due_at`.

### R-H2 Закрытие и «не выполнен» (FR-H2)

`_cron_close` (15 мин): `state in (open, in_progress)` и `due_at < now` → `missed` (`finished_at = due_at`); при `td.energy_mobile.missed_event` — одно событие `td.energy.event._td_log('warn', 'round', 'ROUND-<id>', "Обхід не завершено: {name}", title=…, detail="Виконано {done}/{total}.", dedup_min=1440)` (`node` не задаётся); повторный прогон дублей не создаёт. `done`/`cancelled`/`missed` не пересматриваются.

### R-H3 Отметка пункта (FR-H3)

`action_toggle_item(item_id, done, comment=None)`:
1. Доступ: `…_manager`; обход в `open`/`in_progress`, иначе `UserError("Обхід уже закрито.")`.
2. Блокировка исполнителя (`SELECT … FOR UPDATE` строки обхода): если `performer_id` пуст — становится текущим пользователем, `state='in_progress'`, `started_at = now`; если он другой и пользователь не `…_chief` — `UserError("Обхід виконує {ім'я}.")` (D-76).
3. `done=True`: `done_at = now`, `done_by = uid`, значение и результат — R-H4; `comment` (≤ 256) сохраняется; `done=False`: поля сбрасываются (`result='pending'`, `value=0`, `value_text=''`), `event_id` не создан (события — только при завершении).
4. Пересчёт `done_count`, `progress_pct`, `deviation_count`; `bus.tick('state')`.
5. Возвращает `{"round": <обход как в get_mobile>}`.

### R-H4 Значение пункта и норма (FR-H3)

Источник (`item.source`):
- `signal:<код>` — `td.signal` (через `sudo()`); значение «свежее», если `last_ts ≥ now − max(3·period_s, value_fresh_s)` (по умолчанию 120 с); иначе — «нет данных»;
- `pult:<путь>` — `td.energy.dashboard.get_pult(period='now', parts=['kpis'])`, затем обход по точкам пути; `null` — нет данных;
- пусто — значения нет.
**Подсказка (`hint`):** без источника — статический `hint`; с источником и нормой — «норма {до X | від X | X–Y} {unit} · зараз {value} {unit}» (число — по `precision`, запятая как десятичный разделитель; при отсутствии данных — «зараз —»); с источником без нормы — «зараз {value} {unit}».
**Результат при отметке:** `norm_kind='none'` или нет источника → `ok`; нет значения (нет данных) → `ok`, `value_text = "немає даних"`; `max`: `value ≤ norm_max` → `ok`, иначе `deviation`; `min`: `value ≥ norm_min`; `range`: `norm_min ≤ value ≤ norm_max`. Граничное значение — в норме (`85,0 ≤ 85` → `ok`; `85,1` → `deviation`; `min 60`: `59,9` → `deviation`). `value_text` — «58 °C» (по `precision`).
Пример: T1, `temp_c = 58` → «норма до 85 °C · зараз 58 °C», при отметке `ok`, `value_text='58 °C'`.

### R-H5 Завершение обхода (FR-H4)

`action_finish(round_id, note=None)`: исполнитель или `…_chief`; состояния `open`/`in_progress`. Все пункты с `required=True` должны быть `done`, иначе `UserError("Позначте всі пункти обходу: залишилось %s.")` (N — число неотмеченных обязательных). Затем: `state='done'`, `finished_at = now`, `note`; для каждого пункта с `result='deviation'` — `td.energy.event._td_log('warn', 'round', 'ROUND-<round>-<item.code>', "Обхід: {title} — поза нормою ({value_text})", node=item.node_id, dedup_min=1440)` → `item.event_id`; `message_post` («Обхід завершено: {done}/{total}, відхилень {n}»); `bus.tick('state')`. Возвращает `{"finished_at_local": "HH:MM" (Киев), "deviation_count": n}`.

### R-H6 Ответ `get_mobile` (FR-H5)

1. Выбор обхода: `open`/`in_progress` на сегодня (сначала слот, содержащий `now`; затем по `starts_at`); нет — `round=null`, `next` — ближайший слот сегодня по расписанию, иначе `null`.
2. Для обхода: `items` — по `sequence`; `hint` — R-H4 (значения читаются одним проходом: один `search_read` сигналов + одно обращение к `get_pult` на все пункты); `can_edit`, `can_finish`, `finish_blocked`; `performer.is_me`.
3. `history` — последние закрытые обходы шаблона (не более `history_limit`).
4. Без обращения к стоимости; размер ≤ 10 КБ.

### R-H7 Журнал (FR-H6)

Серверное представление V-H1; `get_journal` — для мобильного «Усі обходи» (опционально). `finished_at_local` — киевское `HH:MM`. Ротация — `_cron_rotate`.

### R-H8 Совместимость с оболочкой W1 (FR-H8)

Вкладка регистрируется записью `td_energy.mobile_tabs` (UI-H1); оболочка `td_energy.mobile` (W1) сама рисует N колонок нижней навигации (`grid-template-columns: repeat(N, minmax(0, 1fr))`), поэтому при установленном модуле — 4 колонки; без модуля — 3 (поведение W1). Тик шины — `state` (в `tools/bus.KINDS` W1 вида `round` нет; вводить новый вид не требуется — A-H3). Правок кода `td_energy` модуль не требует.

## H.12 Acceptance Criteria — AC-H01…AC-H26

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-H01 | FR-H1 | Given установка; Then шаблон `TP-GRSH`: 2 слота («Зміна 1» 07:00–16:00, «Зміна 2» 16:00–23:00, будни), 6 пунктов (`t1`, `t2`, `swb`, `pfc`, `dgu`, `bess`) с нормами/источниками по H.5.2; `UNIQUE(code)`, `UNIQUE(template, item.code)`; повторный `-u` — без изменений | UT |
| AC-H02 | FR-H1 | Given шаблон; When слот `time_to ≤ time_from` / пересекает полночь, `weekdays` с повтором или цифрой 7, `norm_kind='max'` без `norm_max`, `source` неверного формата; Then `ValidationError` с текстами M-H2/M-H3 | UT |
| AC-H03 | FR-H2 | Given вторник 16:20 Киев; When `_cron_open`; Then создан обход «Обхід ТП і ГРЩ · Зміна 2 · {DD.MM}», `state='open'`, `due_at = 23:00` (UTC), 6 пунктов-снимков; повторный прогон — без дубля (`UNIQUE`); суббота — не создаётся; правка шаблона не меняет созданный обход | UT |
| AC-H04 | FR-H2 | Given обход `in_progress` (3/6) и `due_at < now`; When `_cron_close`; Then `missed`, `finished_at = due_at`, одно событие `kind='round'`, `level='warn'`; повтор без дублей; `missed_event=0` — события нет; `done` не меняется | UT |
| AC-H05 | FR-H2 | Given сутки перехода на летнее/зимнее время; Then `starts_at/due_at` корректны по `dates.to_utc`; название обхода — киевская дата | UT |
| AC-H06 | FR-H3 | Given T1 с `temp_c = 58` свежим, DGU с `fuel_pct = 78`, SWB без источника, T2 с несвежим сигналом; Then подсказки: «норма до 85 °C · зараз 58 °C», «норма від 60 % · зараз 78 %», «тепловізор, точки Q1, Q2, QS», «норма до 85 °C · зараз —»; путь `pult:` читает `get_pult(kpis)` (один вызов на все пункты) | UT |
| AC-H07 | FR-H3 | Given обход `open`; When `action_toggle_item` пользователем A, затем B, затем chief; Then A становится исполнителем (`in_progress`, `started_at`); B → `UserError("Обхід виконує A.")`; chief — успех; закрытый обход → `UserError("Обхід уже закрито.")`; user без `…_manager` → `AccessError` | UT |
| AC-H08 | FR-H3 | Given T1 с нормой `max 85` и DGU с `min 60`; Then `temp_c = 85,0` → `ok`; `85,1` → `deviation`; `fuel 60,0` → `ok`; `59,9` → `deviation`; нет данных → `ok` с `value_text='немає даних'`; `range` — обе границы включительно | UT |
| AC-H09 | FR-H3 | Given отмеченный пункт; When `done=False` до завершения; Then `result='pending'`, `value=0`, `value_text=''`, счётчики пересчитаны; после `done` обход — `UserError` | UT |
| AC-H10 | FR-H4 | Given 5 из 6 обязательных отмечено; When `action_finish`; Then `UserError("Позначте всі пункти обходу: залишилось 1.")`; при 6/6 — `done`, `finished_at`, `finished_at_local = "HH:MM"` (Киев), сообщение в чаттере, `bus.tick('state')`; необязательный пункт (`required=False`) не блокирует | UT |
| AC-H11 | FR-H4 | Given два пункта с `deviation`; When `action_finish`; Then два события `kind='round'`, `level='warn'`, `code='ROUND-<id>-<code>'`, `event_id` заполнен; повторное завершение невозможно; без отклонений — событий нет; `dedup_min` защищает от дублей | UT |
| AC-H12 | FR-H5 | Given обход 2/6; When `get_mobile()`; Then `round.done_count=2`, `total_count=6`, `progress_pct=33`, `can_finish=false`, `finish_blocked="залишилось 4"`, `items` по `sequence`, `performer.is_me`, `history ≤ 3`; JSON ≤ 10 КБ; без ключей стоимости | UT |
| AC-H13 | FR-H5 | Given нет открытого обхода; Then `round=null`, `next = {"slot": "Зміна 2", "starts_local": "16:00"}` (или `null` после последнего слота), `history` последние закрытые; при двух открытых — обход слота, содержащего `now` | UT |
| AC-H14 | FR-H5 | Given пользователь без групп энергетики / `…_user` / исполнитель / другой manager; Then `AccessError` / `can_edit=false` / `can_edit=true` / `can_edit=false` с баннером «Обхід виконує {ім'я}» (chief — `can_edit=true`) | UT |
| AC-H15 | FR-H5 | Given hoot с моком API-H1; Then запись реестра `round` (sequence 40, label «Обхід», без `badge`); компонент рисует заголовок, счётчик «2 / 6», полосу прогресса (ширина 33 %), 6 строк, чекбокс вызывает `action_toggle_item` (оптимистично, откат при ошибке); «Завершити обхід» неактивна визуально и показывает тост «Позначте всі пункти обходу: залишилось 4»; при 6/6 — основная и после успеха тост «Обхід завершено й записано в журнал о 14:40» | UT-JS |
| AC-H16 | FR-H6 | Given журнал; Then list/search/pivot открываются; `…_user` и `…_manager` только читают (запись — методами); удаление — `td_factory3d.group_td_admin`; фильтры «Сьогодні», «Мої», «Не виконані», «З відхиленнями» дают ожидаемые выборки | UT |
| AC-H17 | FR-H7 | Given ACL и record rules; Then `…_user` читает, `…_manager` создаёт/пишет обходы и пишет пункты только через методы, `…_chief` правит шаблоны и отменяет/завершает чужие, `admin` — всё; обходы другой компании не видны | UT |
| AC-H18 | FR-H8 | Given установлены `td_energy` и `td_energy_mobile`; Then `registry td_energy.mobile_tabs` содержит `state`, `alarms`, `scheme`, `round` в порядке `sequence` 10, 20, 30, 40; навигация — 4 колонки; без модуля — 3 (регрессия W1) | UT-JS |
| AC-H19 | FR-H8 | Given viewport 390 × 844, стенд; When пройти «Стан» → «Тривоги» («Беру в роботу») → «Схема» → «Обхід» (отметить все, «Завершити»); Then 4 вкладки без горизонтальной прокрутки, кнопки ≥ 48 px (проверка `getBoundingClientRect`), счётчик «Тривоги · N» уменьшается, тост по завершению, запись появляется в журнале | TC (ТК-H1) |
| AC-H20 | FR-H8 | Given две сессии A и B; When A отмечает пункт; Then B ≤ 10 с видит «Обхід виконує A» (только чтение) по тику шины `state`; B не может отметить; после завершения A — B видит обход в «Останніх» | TC (ТК-H2) |
| AC-H21 | FR-H9 | Given `neutralize.sql`, `uninstall_hook`; Then 3 крона неактивны; `uninstall` переводит события `kind='round'` в `manual`, остальные данные `td_energy` целы; `-u` идемпотентен | UT + DEPLOY_TEST |
| AC-H22 | FR-H9 | Given `res.config.settings`; Then параметры `td.energy_mobile.*` редактирует `…_manager`; `history_limit` меняет размер `history`; `value_fresh_s` — окно свежести значения | UT |
| AC-H23 | FR-H10 | Given БД с 730 днями обходов (≈ 520 обходов/год × 6 пунктов); Then `get_mobile` ≤ 250 мс, `action_toggle_item` ≤ 150 мс, `action_finish` ≤ 300 мс, ≤ 15 SQL на `get_mobile`; ротация ≤ 10 с | UT (ТП-H1, ТП-H2) |
| AC-H24 | FR-H4 | Given завершение в 14:40 Киев (11:40 UTC); Then `finished_at_local = "14:40"` в ответе и в журнале; серверное время UTC не «протекает» в UI | UT |
| AC-H25 | FR-H3 | Given пункт с `node_id` (T1) и без него; Then `can_3d` true/false; клик «Де це в 3D» вызывает `useEnergyActions().show3d("T1")`; пункт без узла — кнопка скрыта | UT-JS |
| AC-H26 | FR-H2 | Given `td_energy_mobile` и ручной запуск; When `action_start(template_id)` при отсутствии открытого обхода; Then создан обход «поза розкладом» (`slot_id` пуст, `due_at = now + 2 ч`); при уже открытом — `UserError("Обхід уже відкритий.")`; только `…_manager` | UT |

**Итого `td_energy_mobile`: AC-H01…AC-H26 = 26 критериев** (UT 20, UT-JS 3 (AC-H15, AC-H18, AC-H25), TC 2 (AC-H19, AC-H20), UT + DEPLOY_TEST 1 (AC-H21)).

## H.13 План тестирования (для Opus)

- Фикстуры: `tests/common.py` (C): `TestWHCommon` — `_template()` (шаблон макета), `_signal(code, value, ts)`, `_pult_patch(fuel_pct)`, `_round(slot, state)`, `_user(groups)`, мок времени `patch("odoo.addons.td_energy.tools.dates.now_utc")`.
- Юнит-тесты (C): `test_wh_template.py::TestWHTemplate` — AC-H01, AC-H02; `test_wh_schedule.py::TestWHSchedule` — AC-H03…AC-H05, AC-H26; `test_wh_value.py::TestWHValue` — AC-H06, AC-H08; `test_wh_round.py::TestWHRound` — AC-H07, AC-H09…AC-H11, AC-H24; `test_wh_api.py::TestWHApi` — AC-H12…AC-H14, AC-H16, AC-H22, AC-H23; `test_wh_security.py::TestWHSecurity` — AC-H17, AC-H21, ТБ-H1, ТБ-H2; `test_wh_ui.py::TestWHUi` (HttpCase: вкладка открывается без JS-ошибок); `test_wh_hoot.py::TestWHHoot.test_hoot_suite` — AC-H15, AC-H18, AC-H25.
- Стенд `tests/stand/test_wh_tk.py` (Playwright, viewport 390 × 844):

| ТК | Название | Шаги | Ожидается |
|---|---|---|---|
| ТК-H1 | Экран целиком | открыть «Чергування (телефон)»; «Тривоги» → «Беру в роботу»; «Схема»; «Обхід»: отметить 6 пунктов, «Завершити обхід»; открыть «Журнал обходів» в десктопе | AC-H19: 4 вкладки, кнопки ≥ 48 px, тост «Обхід завершено…», запись в журнале, событие для отклонений |
| ТК-H2 | Две сессии | A отмечает; B открывает вкладку «Обхід» | AC-H20 |
| ТК-H3 | Просроченный слот | не завершить обход; сдвинуть время/дождаться `cron_close` (или вызвать `_cron_close` с моком времени) | обход `missed`, предупреждение в «Події», в «Останніх обходах» статус «Не виконано» |

- Тесты безопасности: ТБ-H1 — пользователь без групп/`…_user` не вызывает `action_toggle_item`/`action_finish`; ТБ-H2 — чужой обход нельзя изменить без chief (AC-H07, AC-H17).
- Производительность: ТП-H1 — `get_mobile` ≤ 250 мс; ТП-H2 — `action_toggle_item` ≤ 150 мс (AC-H23).
- DEPLOY_TEST: копия демо-БД → `-i td_energy_mobile` → шаблон (1/2/6) → `_cron_open` → вкладка на 390 px → `uninstall` (события `round` → `manual`).

## H.14 Definition of Done (`td_energy_mobile`)

Все UT/UT-JS AC-H01…AC-H26 зелёные; ТК-H1…ТК-H3 пройдены; `ruff` без ошибок; регрессия `td_energy` (в т. ч. мобильный W1: 3 вкладки без модуля) зелёная; `neutralize.sql`, CHANGELOG, README («Чергування», «Обхід»), DEPLOY_TEST; скриншоты четырёх вкладок на 390 × 844.

## H.15 Открытые вопросы и решения автора

| ID | Вопрос | Кому | Рекомендация | Что делаем тем временем |
|---|---|---|---|---|
| Q-H1 | Реальные чек-листы обходов (пункты, нормы температуры масла T1/T2, периодичность, смены) | электрики, главный энергетик | утвердить шаблон по макету, затем уточнить нормы и периодичность | демо-шаблон макета (H.5.2) |
| Q-H2 | Считать ли невыполненный обход тревогой («Події») | заказчик | да, предупреждение уровня `warn` | включено (`missed_event=1`) |
| Q-H3 | Кто может выполнять обходы (отдельная роль «чергувальний»?) | заказчик | группа «Енергетик» | `group_td_energy_manager` |

| ID | Решение | Обоснование |
|---|---|---|
| A-H1 | Отдельный модуль `td_energy_mobile` (зависит только от `td_energy`), а не часть `td_energy` или `td_energy_analytics` | обход — операционный функционал; необязателен для клиентов без чергових; будущий дом для Web Push/PWA (Q-08); не трогает 142 теста `td_energy`; GAP тоже предлагал отдельный модуль |
| A-H2 | Пункты обхода — снимок шаблона на момент создания; значения «зараз» берутся из `td.signal` или `get_pult` (`pult:`-путь), без зависимости от `td_genset` | паливо ДГУ — не сигнал; контракт W1 C-30 |
| A-H3 | Тик шины — вид `state` (существующий), новый вид не вводится | `tools/bus.KINDS` W1 фиксирован; изменения W1 не нужны |
| A-H4 | Исполнитель обхода блокируется за первым отметившим; `chief` может завершить/перехватить | несколько чергових на смене; без потери данных |
| A-H5 | Событие `kind='round'` на отклонения и просрочки (`selection_add` в `td.energy.event`) | видимость в «Подіях» и Пульте; откат при деинсталляции |
| A-H6 | Расписание — слоты в шаблоне, а не календарь смен | независимость от W3/W4 и календаря; смены макета — демо-данные |
