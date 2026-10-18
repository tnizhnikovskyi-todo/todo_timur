# W1 «Енергетика»: специфікація (вставки до SPEC `td_energy` і `td_genset_factory3d`)

Версія 0.1 · 18.10.2026 · стандарт `docs/DOC_STANDARD.md` · технічне рішення: `build/energy/W1_ARCH.md` (далі ARCH: FR-30…FR-45 і FR-18…FR-21, A-23…A-37 і A-19…A-23, Q-21…Q-25).
Вхід: `build/energy/GAP.md` (рішення E-01…E-11, матриця PU/ND/MB), макет `Main.dc.html`, `Feeder.dc.html`, `Mobile.dc.html` (вкладки «Стан», «Тривоги», «Схема»).
Спирається на: `docs/ARCHITECTURE.md` §5, §6.4–§6.8; `factory3d_energy` SPEC (R-04, R-06, R-07, R-13…R-16, M-01…M-20); `factory3d_genset` (у `docs/modules/td_genset/SPEC.md`: M-01, ADP-01…ADP-10, R-04…R-06); `factory3d_telemetry` CT-01, CT-05, CT-10; `factory3d_viewer` M-01.
Після злиття `claude/td-rename` цей файл розкладається в розділи `docs/modules/td_energy/SPEC.md` і `docs/modules/td_genset_factory3d/SPEC.md` (зараз ті документи не змінюються).

## Умовні позначення, діапазони ID, відхилення від макета

**Імена (E-09).** Усе — у td-іменах: модулі `td_energy`, `td_genset_factory3d`, `td_telemetry`, `td_bms`, `td_viewer3d`, `td_factory3d`, `td_iot_sim`; моделі `td.*`; поля стандартних моделей `td_*`; методи `_f3d_*` → `_td_*`; групи `td_factory3d.group_td_user|manager|admin`; корінь меню `td_factory3d.menu_td_root`. Маршрути `/f3d/*` і **коди сигналів не змінюються**. Ключі `ir.config_parameter` нових параметрів — `td.energy.<param>` (A-23, припущення). Посилання «поточний файл» (рядок) дано на гілку `claude/factory3d-build`.

**Діапазони ID.** Нумерація продовжує існуючі документи; між модулями ID **перетинаються за номерами**, тому поза таблицями ID завжди з модулем: `td_energy M-21`, `td_genset_factory3d M-10`.

| Тип | `td_energy` (останній був) | W1 бере | `td_genset_factory3d` (останній був) | W1 бере |
|---|---|---|---|---|
| FR | FR-29 | FR-30…FR-45 | FR-17 | FR-18…FR-21 |
| M | M-20 | M-21…M-28 | M-09 | M-10…M-11 |
| V | V-21 | V-22…V-34 | V-09 | V-10…V-11 |
| API | API-04 | API-05…API-15 | — | — |
| R | R-23 | R-24…R-38 | R-13 | R-14…R-16 |
| AC | AC-92 | AC-93…AC-158 | AC-73 | AC-74…AC-83 |
| ТК/ТБ/ТП | ТК-12 / ТБ-06 / ТП-06 | ТК-13…ТК-18 / ТБ-07…ТБ-10 / ТП-07…ТП-09 | ТК-G13 / ТБ-10 / ТП-06 | ТК-G14…ТК-G15 / ТБ-11 / ТП-07 |
| A (рішення автора) | A-22 | A-23…A-37 | A-18 | A-19…A-23 |
| Q | Q-20 | Q-21…Q-24 | Q-24 | Q-25 |
| ADP (адаптер td_genset) | — | — | ADP-10 | ADP-11 |
| UI (клієнтські компоненти) | — | UI-01…UI-11 | — | — |

Позначення: UT — юніт-тест `odoo.tests` (`TransactionCase`/`HttpCase`), UT-JS — hoot-тест (`web.assets_unit_tests`), TC — стенд (емулятор + збирач + Odoo), MAN — ручна перевірка. `req`=`required=True`, `idx`=`index=True`, `cost` у «Параметри» = `groups="td_energy.group_td_energy_cost"`. Усі `Datetime` — UTC naive; «Київ» — `Europe/Kyiv` (`tools/dates.py`). Рядки UI — українською в коді.

### Відхилення від макета (D-xx)

| ID | Де в макеті | Що в реалізації | Чому |
|---|---|---|---|
| D-01 | Main: кнопка «Звіт за зміну» | Прихована до W4 (`capabilities.report=false`) | Звіт — W4 (GAP PU-04) |
| D-02 | Main: рекомендація — «Зарядити BESS 50 кВт», «Увімкнути QS…», «Скасувати» | Банер і слот даних є; кнопки `kind='control'` не показуються, поки не встановлено `td_energy_control` (`control_available=false`); «Пізніше» працює; «Скасувати» (undo) — W2 | E-02: правила й команди — W2 |
| D-03 | Main: панель вузла QS/BESS — кнопки «Увімкнути QS…», «Зарядити 50 кВт» | Не показуються до W2 | Те саме |
| D-04 | Main: «Підтверджено вами о 14:22» | «Підтверджено: {ім'я} о HH:MM» (для себе — «вами») | Кілька користувачів |
| D-05 | Main: BESS бурштиновий лише при заряді | Бурштиновий (`gen`) при \|P\| ≥ 1 кВт (заряд або розряд); у спокої — норма | Однакове кодування активності |
| D-06 | Main: факти вузлів (тиск SF6, огляд 12.09, «блокування паралельної роботи від АВР — увімкнено», «Резерв на відключення мережі: 30 %» як дані пристрою) | Лише факти, які є в даних/сигналах; відсутні — пропускаються; «резерв BESS 30 %» — параметр `td.energy.bess_reserve_pct` | У моделях немає цих полів/сигналів |
| D-07 | Main: «Діагностика» — «Шлюз Modbus GW-SWB-1…» | Текст зі `td.source` лічильника: код джерела, `host:port`, unit, стан колектора, час останньої відповіді | «Шлюзу» як об'єкта немає |
| D-08 | Main: блок «ТО й відключення» зі статусом «Чернетка» для повірки | Повірка лічильників — рядок зі статусом «Заплановано» (`next_verification`); «Чернетка» лише для планових відключень | Повірка не має чернетки |
| D-09 | Main: PFC «5 ступенів з 10», крок 35 квар | Параметри вузла `pfc_step_kvar=35`, `pfc_steps_total=10` (A-33); змінює fallback-округлення R-06 п.2 (було 50) і текст `steps` R-16 п.4 | Макет затверджено замовником; старий SPEC мав «50 + 3 × 100» |
| D-10 | Main: перемикач `showForecast` (проп дизайну) | Прогноз завжди розраховується; показ/приховання — клік по елементу легенди | Проп не є функцією |
| D-11 | Feeder: події фідера «CNC-4 переведено в ТО», «Пуск GANTRY-1» | Стрічка = `td.energy.event` вузла + створення/закриття `maintenance.request` по обладнанню піддерева; пуски верстатів не входять | Це події machine_connect, не енергетики |
| D-12 | Feeder: «Спрацювань за рік: 0», «Уставка Ir 0,9 × In» | Поля вузла `protection_trip_unit`, `protection_ir_ratio` + лічильник подій `kind='trip'` | Нових сигналів уставки немає |
| D-13 | Feeder: «Тепловізійний огляд 21.10 · заплановано» | Найближча планова `maintenance.request` (`maintenance_type='preventive'`) по обладнанню вузла або «—» | План ТО — стандартний модуль |
| D-14 | Feeder: ШР-3 «6 відгалужень», ШР-4 «14» | З даних: 8 і 11 (`EN/data/energy_nodes.csv`) | Демо-числа макета ≠ даних |
| D-15 | Mobile: «Закрити: зв'язок є» повертає в «Тривога» | Вирішення — автоматичне (R-25) або вручну виконавцем (`action_resolve`) | Демо-перемикач макета |
| D-16 | Mobile: вкладка «Обхід» | Не входить у W1 (W4, `td_energy_mobile` через реєстр вкладок, A-26) | E-02 |
| D-17 | Main: меню «Генератор» у верхньому рядку | Немає (E-01): розділ «Генерація й резерв» у «Енергетика» | E-01 |
| D-18 | Main: підменю «Керування», «Енергоресурси», «Аналітика» | З'являються з W2/W3/W4; у W1 підменю: Пульт, Вузли мережі, Події, Генерація й резерв, Налаштування (+ існуючі) | Хвилі |

---

# ЧАСТИНА I. `td_energy`

## 0. Дерево файлів (дельта до `td_energy`)

Власники: **A** — бекенд, **B** — фронтенд, **C** — міст і емулятор (ARCH §6). Файли без літери — менеджер (злиття).

```
odoo_addons/td_energy/
├── __manifest__.py                    (менеджер) version → 19.0.1.1.0; data/assets — розд. 1
├── hooks.py                           A  post_init_hook: + _load_sld_layout, _ensure_w1_signals; uninstall без змін
├── migrations/19.0.1.1.0/post-migration.py   A  R-24 (існуючі події), SLD-геометрія, сигнали, пороги cos φ
├── models/
│   ├── td_energy_event.py             A  M-21 (поля, _td_log(+title,detail), action_*, auto-resolve) — існуючий файл
│   ├── td_energy_node.py              A  M-22 (поля sld_*, protection_*, pfc_*, sld_state) — існуючий
│   ├── td_energy_meter.py             A  M-23 (повірка) — існуючий
│   ├── td_energy_interval.py          A  M-24 (is_backfill, _td_backfill → tools/backfill.py) — існуючий
│   ├── td_energy_node_live.py         A  R-35 (cos φ секцій, pfc_q_now із сигналу), тік шини — існуючий
│   ├── td_energy_outage_plan.py       A  M-25
│   ├── td_energy_advice.py            A  M-26
│   ├── td_energy_dashboard.py         A  M-27 (AbstractModel: API-05…API-07, API-12, API-13, хуки)
│   ├── res_config_settings.py         A  розд. 5.1 (cos φ, пульт, прогноз) — існуючий
│   └── __init__.py                    A  (+ імпорти нових файлів; рядки, інших воркерів немає)
├── wizard/td_energy_ticket_wizard.py  A  M-28; wizard/__init__.py — A
├── tools/
│   ├── dashboard.py                   A  збирання `get_pult` (R-27, R-28)
│   ├── forecast.py                    A  R-28
│   ├── sld.py                         A  R-26 (стани, ребра, факти R-29)
│   ├── node_card.py                   A  R-30
│   ├── bus.py                         A  R-33 (throttle + _sendone)
│   ├── backfill.py                    A  R-36 (генератор історії)
│   └── dates.py                       A  (+ weekday_slots, shift_start уже є) — існуючий
├── data/
│   ├── sld_layout.csv                 A  21 рядок (розд. 5.2)
│   ├── energy_signals.csv             A  +15 рядків (розд. 5.3)
│   ├── energy_sources.csv             A  +1 рядок `MB-U73-SWB-CTRL`
│   ├── ir_cron.xml                    A  +3 крони (розд. 6)
│   └── ir_config_parameter.xml        A  +14 параметрів (розд. 5.1)
├── security/td_energy_security.xml    A  + група `group_td_energy_chief`
├── security/ir.model.access.csv       A  + 8 рядків (розд. 4.1)
├── static/src/
│   ├── common/{bus.js,format.js,chart.js,td_energy.scss}   B  UI-10, UI-11, спільні SVG-хелпери
│   ├── pult/{pult.js,pult.xml,sld.js,sld.xml,profile.js,profile.xml,alarms.js,alarms.xml}   B  UI-01…UI-04
│   ├── node_card/{node_card.js,node_card.xml,dialogs.js,dialogs.xml}                        B  UI-05…UI-07
│   ├── generation/{generation.js,generation.xml}                                            B  UI-08
│   └── mobile/{mobile.js,mobile.xml,mobile.scss}                                            B  UI-09
├── static/tests/{pult.test.js,sld.test.js,node_card.test.js,mobile.test.js}                 B  hoot
├── views/
│   ├── td_energy_pult_views.xml       B  V-22…V-25 (client actions)
│   ├── td_energy_event_views.xml      B  V-26 (існуючий)
│   ├── td_energy_node_views.xml       B  V-27 (існуючий)
│   ├── td_energy_meter_views.xml      B  V-28 (існуючий)
│   ├── td_energy_outage_plan_views.xml B V-29
│   ├── td_energy_advice_views.xml     B  V-30
│   ├── td_energy_ticket_wizard_views.xml B V-31
│   ├── res_config_settings_views.xml  B  V-32 (існуючий)
│   └── menus.xml                      B  V-33 (існуючий)
└── tests/
    ├── test_w1_event.py, test_w1_node_sld.py, test_w1_dashboard.py, test_w1_forecast.py, test_w1_card.py,
    │   test_w1_outage_plan.py, test_w1_advice.py, test_w1_signals.py, test_w1_backfill.py, test_w1_security.py, test_w1_bus.py   A
    ├── test_w1_ui.py, test_w1_hoot.py B  (HttpCase: client actions, меню; hoot-набір за зразком `td_bms/tests/test_hoot.py`)
    └── stand/test_w1_tk.py            A  ТК-13…ТК-18 (pytest проти стенда)
```

Файл `odoo_addons/td_genset_factory3d/**` і `services/iot_sim/**`, `odoo_addons/td_iot_sim/data/**` — власник C (Частина II, розд. 8).

## 1. Маніфест (дельта)

- `version`: `19.0.1.1.0`; `depends`: без змін (`td_telemetry`, `mrp_account`, `analytic`, `web_hierarchy`) **+ `mail`** (вже через telemetry), `bus` (транзитивно); нових зовнішніх залежностей немає.
- `data` (порядок): `security/td_energy_security.xml`, `security/ir.model.access.csv`, `data/ir_config_parameter.xml`, `data/ir_cron.xml`, `views/td_energy_ticket_wizard_views.xml` (до `td_energy_node_views.xml`, бо кнопка вузла посилається на дію), `views/td_energy_node_views.xml`, `views/td_energy_meter_views.xml`, `views/td_energy_event_views.xml`, `views/td_energy_outage_plan_views.xml`, `views/td_energy_advice_views.xml`, `views/td_energy_pult_views.xml` (клієнтські дії), `views/res_config_settings_views.xml`, `views/menus.xml` (останнім).
- `assets`: `web.assets_backend`: `td_energy/static/src/common/**`, `td_energy/static/src/pult/**`, `…/node_card/**`, `…/generation/**`, `…/mobile/**`; `web.assets_unit_tests`: `td_energy/static/tests/**`.
- `post_init_hook` — існуючий + виклики `hooks._load_sld_layout(env)` і `hooks._ensure_w1_signals(env)` (ідемпотентні; ті самі функції викликає міграція).

## 2. Моделі

### M-21 `td.energy.event` — розширення (FR-36, R-24, R-25)

Існуюча модель (`EN/models/f3d_energy_event.py:21`, `_log_access=False`, `_order="ts desc, id desc"`). Додається:

| Поле | Тип | Параметри |
|---|---|---|
| `title` | Char | size=128, «Заголовок»; заповнюється в `create` (R-24) |
| `detail` | Char | size=256, «Деталі» |
| `state` | Selection | `na`/«Інформація», `active`/«Активна», `acked`/«Підтверджена», `resolved`/«Вирішена»; req, default `na`, idx; початкове значення — R-24 |
| `acked_by` | Many2one `res.users` | ondelete=set null, readonly |
| `acked_at` | Datetime | readonly |
| `assigned_user_id` | Many2one `res.users` | ondelete=set null, idx, readonly, «Виконавець» |
| `taken_at` | Datetime | readonly |
| `resolved_at` | Datetime | readonly |
| `request_id` | Many2one `maintenance.request` | **compute без store**: найновіша відкрита (`stage_id.done=False`) заявка з `td_signal_id = signal_id`; без сигналу — порожньо |
| `action_code` | Char | compute без store: `'diag'` якщо `kind='meter'` і `state != 'resolved'`; інакше `'request'` якщо `request_id`; інакше `False` |
| `is_backfill` | Boolean | default False, idx, readonly (R-36) |

`kind` — `selection_add`: `('trip', 'Спрацювання захисту')` (ND-14; подію створює R-30 п.9). Індекс `(state, ts)` у `init()`.

**Constraint `_check_state`:** `level='info'` → `state='na'`; `level in (warn, bad)` → `state in (active, acked, resolved)`; інакше `ValidationError("Некоректний стан події: %s.")`.

**`_td_log(level, kind, code, text, ts=None, node=None, signal=None, outage=None, dedup_min=0, title=None, detail=None)`** (API-03 розширено; старі виклики працюють без змін): після дедуплікації (поточна логіка) створює запис; `title`/`detail` за R-24; після `create` — `tools.bus.tick(env, 'alarm')`.

Методи (група «Енергетик» = `td_energy.group_td_energy_manager`; клас A, E-06):

| Метод | Алгоритм | Помилки |
|---|---|---|
| `action_ack()` | немає групи → `AccessError("Підтверджувати тривоги може лише енергетик.")`; для записів `state='active'`: `acked_by=uid`, `acked_at=now`, `state='acked'`; інші стани — пропустити без помилки; `bus.tick('alarm')`; повертає `True` | AccessError |
| `action_take()` | група як вище; запис не в `active/acked` → `UserError("Подію вже закрито.")`; `assigned_user_id` задано й ≠ uid → `UserError("Уже в роботі: %s.")`; інакше `assigned_user_id=uid`, `taken_at=now`, і якщо `state='active'` — ack-поля; `bus.tick('alarm')` | UserError |
| `action_release()` | виконавець або `group_td_energy_chief` → `assigned_user_id=False`, `taken_at=False`; стан лишається `acked` | AccessError |
| `action_resolve()` | виконавець або `group_td_energy_chief` → `state='resolved'`, `resolved_at=now`; `info` → `UserError("Інформаційну подію закривати не потрібно.")` | AccessError, UserError |
| `_td_auto_resolve(kind, code=None, node=None, signal=None)` | `api.model`; знаходить `state in (active, acked)` за `kind` і (`code` або `node` або `signal`), ставить `resolved` (R-25) | — |

### M-22 `td.energy.node` — розширення (FR-33, FR-38, R-26, R-35)

Існуюча модель (`EN/models/f3d_energy_node.py:17`). Додається:

| Поле | Тип | Параметри |
|---|---|---|
| `sld_show` | Boolean | default False, «На схемі Пульту» |
| `sld_shape` | Selection | `box`/«Блок», `bar`/«Шина», `switch`/«Вимикач», `label`/«Підпис»; default `box` |
| `sld_x`, `sld_y`, `sld_w`, `sld_h` | Integer | default 0; координати в полотні 1320 × 452 px (A-27) |
| `sld_label` | Char | size=32, «Підпис на схемі» (порожньо → `name`) |
| `sld_anchor_id` | Many2one `td.energy.node` | ondelete=set null, «Вузол-батько на схемі» (замість найближчого видимого предка) |
| `sld_state` | Selection | `ok`/«Норма», `warn`/«Увага», `alarm`/«Тривога», `off`/«Резерв / вимкнено», `gen`/«Генерація»; **compute без store** (`tools.sld.states(env, nodes)` — один знімок на виклик, R-26) |
| `protection_trip_unit` | Char | size=64, «Розчіплювач» |
| `protection_ir_ratio` | Float | digits=(4,2), «Уставка Ir, × In» |
| `trip_count_year` | Integer | compute без store: кількість подій `kind='trip'`, `node_id=self`, `ts ≥ now − 365 діб` |
| `pfc_step_kvar` | Integer | default 35, «Крок ступеня, квар» (A-33) |
| `pfc_steps_total` | Integer | default 10, «Ступенів»; значущі лише для `cell_type='pfc'` |

Constraints: `_check_sld` — `sld_x, sld_y, sld_w, sld_h ≥ 0`; `sld_show` і `sld_shape in (box, bar, switch)` → `sld_w > 0` і `sld_h > 0` (`ValidationError("Задайте розміри блоку на схемі для %s.")`); `sld_anchor_id ≠ self`. `_check_pfc` — для `cell_type='pfc'` і `rating_kvar > 0`: `pfc_step_kvar × pfc_steps_total == rating_kvar` (`ValidationError("Ступені PFC %s не відповідають номіналу %s квар.")`); інакше поля ігноруються.

Зміна `sld_*` і `sld_show` лише `group_td_energy_manager` (існуючий ACL запису вузла).

### M-23 `td.energy.meter` — розширення (ND-13, R-34)

| Поле | Тип | Параметри |
|---|---|---|
| `last_verification` | Date | «Остання повірка» |
| `verification_months` | Integer | default 12, «Міжповірочний інтервал, міс.»; constraint `> 0` |
| `next_verification` | Date | «Наступна повірка»; stored; compute з `last_verification + verification_months` (`@api.depends`), `readonly=False` (можна задати вручну); якщо обидва порожні — порожньо |

### M-24 `td.energy.interval` — розширення (R-36)

`is_backfill` Boolean default False, idx, readonly, «Синтетичні дані». Метод `_td_backfill(self, days=90, until=None, seed=20261018, purge=False, with_balance=True, with_events=True, with_advice=False, meters=None)` → делегує `tools.backfill.run(...)`; `api.model`; дозволено `env.is_superuser()` або `td_factory3d.group_td_admin`, інакше `AccessError("Генерувати історію може лише адміністратор.")`; повертає словник статистики (R-36 п.10).

### M-25 `td.energy.outage.plan` — планове відключення (FR-39, R-31)

`_name = "td.energy.outage.plan"`, `_description = "Енергетика: планове відключення"`, `_inherit = ["mail.thread", "mail.activity.mixin"]`, `_order = "start desc, id desc"`.

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | compute store: «{node.sld_label or node.name} · DD.MM HH:MM–HH:MM» (Київ) |
| `node_id` | Many2one `td.energy.node` | req, ondelete=restrict, idx, tracking; domain `kind in (line, cell, transformer, section, switchboard)` |
| `reason` | Selection | `busway`/«Протяжка з'єднань шинопроводу», `thermo`/«Тепловізійний огляд і ремонт», `replace`/«Заміна відгалуження», `other`/«Інша»; req, default `busway` |
| `reason_text` | Char | size=128; обов'язкове при `reason='other'` |
| `start`, `end` | Datetime | req, tracking |
| `state` | Selection | `draft`/«Чернетка», `pending`/«На узгодженні», `approved`/«Узгоджено», `rejected`/«Відхилено», `done`/«Виконано», `cancelled`/«Скасовано»; default `draft`, idx, tracking |
| `affected_node_ids` | Many2many `td.energy.node` | rel `td_energy_outage_plan_node_rel`; readonly; пишеться в `action_submit` (піддерево `node_id`, `kind in (tapoff, consumer)`) |
| `affected_count` | Integer | compute store: `len(affected_node_ids)` |
| `production_ids` | Many2many `mrp.production` | rel `td_energy_outage_plan_mo_rel`; readonly; R-31 п.2 |
| `production_count` | Integer | compute store |
| `requested_by` | Many2one `res.users` | default uid, readonly |
| `approver_id` | Many2one `res.users` | readonly |
| `approved_at` | Datetime | readonly |
| `reject_reason` | Char | size=256, readonly |
| `company_id` | Many2one `res.company` | req, default `env.company` |
| `note` | Text | — |

Constraints: `_check_period` — `end > start` («Кінець має бути пізніше за початок.»); `_check_overlap` — для `state in (pending, approved)` не може перетинатися інтервал іншого плану того ж `node_id` у цих станах («Для %s вже є відключення в цей час.»); `_check_reason` — `reason='other'` → `reason_text` непорожнє.

Методи:

| Метод | Алгоритм | Помилки |
|---|---|---|
| `preview(node_code, start, end)` | `api.model`; `node` за кодом; повертає `{"tap_codes": [...], "tap_count": n, "orders": [{"name", "product", "date_start"}], "order_count": m}` (R-31 п.1–2) без запису | невідомий код → `UserError("Невідомий вузол: %s.")` |
| `action_submit()` | група «Енергетик»; `state='draft'`; `start ≥ now` (`UserError("Початок має бути в майбутньому.")`); заповнює `affected_node_ids`, `production_ids`; `state='pending'`; `mail.activity` (тип `mail.mail_activity_data_todo`, «Узгодити відключення …», термін `start.date()`) кожному користувачу `mrp.group_mrp_manager`; підписує й сповіщає (`message_post`) користувачів `stock.group_stock_manager` (R-31 п.4); `bus.tick('state')` | AccessError, UserError |
| `action_approve()` | користувач у `mrp.group_mrp_manager` (інакше `AccessError("Узгоджує керівник виробництва.")`); `state='pending'`; `approver_id=uid`, `approved_at=now`, `state='approved'`; закрити свої activity; `message_post` енергетикам (підписники) «Узгоджено: …»; `bus.tick('state')` | AccessError, UserError |
| `action_reject(reason)` | як `approve`; `reason` непорожня (`UserError("Вкажіть причину відхилення.")`); `state='rejected'`, `reject_reason` | — |
| `action_cancel()` | група «Енергетик» або автор; `state in (draft, pending, approved)` → `cancelled` | UserError |
| `_cron_close()` | `state='approved'` і `end < now` → `done`; `state in (draft, pending)` і `end < now` → `cancelled` | — |

### M-26 `td.energy.advice` — рекомендація (слот; FR-32, R-32)

`_name = "td.energy.advice"`, `_description = "Енергетика: рекомендація"`, `_order = "level desc, create_date desc"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char | size=32, idx, req (напр. `EXPORT-T2`) |
| `dedup_key` | Char | size=64, idx; унікальний серед відкритих (частковий індекс у `init()`: `UNIQUE(dedup_key) WHERE state IN ('open','snoozed') AND dedup_key IS NOT NULL`) |
| `kind` | Selection | `rule`/«Правило», `manual`/«Вручну»; default `manual` |
| `title` | Char | size=128, req |
| `text` | Text | req |
| `level` | Selection | `info`, `warn`; default `warn` |
| `node_id` | Many2one `td.energy.node` | ondelete=set null |
| `state` | Selection | `open`/«Відкрита», `snoozed`/«Відкладена», `done`/«Виконана», `dismissed`/«Відхилена», `expired`/«Прострочена»; default `open`, idx |
| `snooze_until` | Datetime | — |
| `expires_at` | Datetime | після цього часу відкрита/відкладена → `expired` (крон) |
| `actions` | Json | default `[]`; **контракт дій** (нижче) |
| `result_note` | Char | size=256 |
| `resolved_at`, `resolved_by` | Datetime / Many2one `res.users` | readonly |

**Контракт `actions[]`** (W2 `td_energy_control` додає `kind='control'`): `{"code": str (a-z0-9_), "label": str ≤ 48, "kind": "link"|"ticket"|"control", "class": null|"A"|"B", "params": object}`. `link` — `params={"xmlid": "<module>.<action>", "res_id": int|null}` (клієнт відкриває `ir.actions.act_window`); `ticket` — `params={"node_code": str, "description": str}` (відкриває діалог UI-07); `control` — `params={"command_kind": str, ...}` (W2). Клієнт показує `control` лише при `meta.control_available=true`.

Методи: `get_open()` (`api.model`; повертає найсерйозніший запис `state='open'` або `snoozed` із `snooze_until ≤ now`, інакше `False`; формат — API-05 `advice`); `action_snooze(minutes=None)` (за замовчуванням `td.energy.advice_snooze_min`=30; `state='snoozed'`, `snooze_until=now+minutes`; група «Енергетик»; `bus.tick('advice')`); `action_dismiss()` (`state='dismissed'`); `action_done(note=None)` (`done`, `resolved_*`); `_cron_advice()` — **реєстр правил**: збирає методи `_td_advice_rule_*` (`api.model`, сигнатура `(self, now) -> list[dict]`, елемент `{code, dedup_key, title, text, level, node_code, actions, expires_in_min}`); для кожного елемента створює запис, якщо відкритого з тим `dedup_key` немає; відкриті `kind='rule'`, чий `dedup_key` більше не повернуто правилами, переводить у `expired`. У W1 вбудованих правил **немає** (крон ні на що не діє); перший рядок правил додасть W2. `_td_demo_seed()` — створює демо-рекомендацію `EXPORT-T2` («СЕС віддає {X} кВт у мережу через T2.» + текст макета; `actions=[{"code":"open_event","label":"Відкрити подію","kind":"link",…},{"code":"charge_bess","label":"Зарядити BESS 50 кВт","kind":"control","class":"A","params":{"command_kind":"bess_charge"}},{"code":"qs_on","label":"Увімкнути QS…","kind":"control","class":"B","params":{"command_kind":"qs_close"}}]`); викликається лише з R-36 при `with_advice=True`.

### M-27 `td.energy.dashboard` — API Пульту, картки, мобільного, розділу генерації (AbstractModel; FR-30…FR-35, FR-37, FR-42)

`_name = "td.energy.dashboard"`, `_description = "Енергетика: дані Пульту"`. Методи — API-05…API-07, API-12, API-13 (розд. 7). **Хуки розширення** (порожні в базі; міст `td_genset_factory3d` перевизначає):

| Хук | Сигнатура | Повертає в базі |
|---|---|---|
| `_td_genset_summary` | `(self) -> dict \| None` | `None` |
| `_td_generation_cards` | `(self) -> list[dict]` | картки СЕС, КГУ, BESS, АВР (R-38) |
| `_td_node_facts_extra` | `(self, node) -> list[str]` | `[]` |
| `_td_node_card_extra` | `(self, node) -> dict` | `{}` (додаткові блоки картки; ключ → блок) |

Доступ: усі публічні методи на вході — `if not self.env.user.has_group("td_energy.group_td_energy_user"): raise AccessError("Немає доступу до Енергетики.")`; читання сигналів/інтервалів — `sudo()` лише для `td.signal`, `td.reading`, `td.energy.interval` (як `EN/tools/payload.py`), ключі вартості без групи `group_td_energy_cost` видаляються з відповіді (не лише ховаються).

### M-28 `td.energy.ticket.wizard` — заявка ТО з картки вузла (Transient; FR-40)

| Поле | Тип | Параметри |
|---|---|---|
| `node_id` | Many2one `td.energy.node` | req |
| `equipment_id` | Many2one `maintenance.equipment` | compute з `node_id.equipment_id`, readonly |
| `maintenance_type` | Selection | `corrective`/«Коригувальне», `preventive`/«Планове»; default `corrective` |
| `description` | Text | req; default з контексту `default_description` |
| `team_id` | Many2one `maintenance.team` | default — команда з назвою «Електрики», інакше перша за `sequence` |
| `priority` | Selection | `2`/«Звичайний», `3`/«Високий»; default `2` (значення `maintenance.request.priority`) |

`action_create()`: створює `maintenance.request` `{name: "{node.sld_label or node.name}: {перший рядок description ≤ 80}", description, equipment_id (може бути порожнім), maintenance_type, maintenance_team_id: team_id, priority, user_id: False, td_origin: 'manual' (якщо поле є)}`; `message_post` «Створено з картки вузла {code}»; повертає `act_window` на створену заявку (`form`). `equipment_id` порожнє → у `description` додається рядок «Вузол мережі: {code}».

## 3. Представлення й меню

### 3.1 Представлення V-22…V-34

| ID | XML-id (`td_energy.`) | Тип / модель | Структура |
|---|---|---|---|
| V-22 | `action_td_energy_pult` | `ir.actions.client`, `tag="td_energy.pult"`, `name="Пульт енергетика"`, `context={"td_energy_period": "now"}` | відкриває UI-01 |
| V-23 | `action_td_energy_node_card` | `ir.actions.client`, `tag="td_energy.node_card"`; параметри `params={"code": "BW-2"}` у `context.active_code` або `params.code` | відкриває UI-05; у формі вузла кнопка «Картка вузла» (`action_open_card()`, повертає цю дію з `params.code=self.code`) |
| V-24 | `action_td_energy_mobile` | `ir.actions.client`, `tag="td_energy.mobile"` | UI-09 |
| V-25 | `action_td_energy_generation` | `ir.actions.client`, `tag="td_energy.generation"` | UI-08 |
| V-26 | `view_td_energy_event_list` / `_search` / `_form` | list / search / form `td.energy.event` (зміна існуючих) | list (readonly): `ts`, `level` (badge), `state` (badge: `active` — danger, `acked` — warning, `resolved` — success, `na` — muted), `kind`, `code`, `title`, `detail`, `assigned_user_id` (optional show); кнопки заголовка списку «Підтвердити» (`action_ack`), «Взяти в роботу» (`action_take`), «Закрити» (`action_resolve`) для вибраних; search: фільтри «Активні» (`state in (active,acked)`, default), «Непідтверджені» (`state='active'`), «Мої» (`assigned_user_id = uid`), «Рівень», групування `state`, `kind`, `node_id`; form: усі нові поля readonly + кнопки |
| V-27 | `view_td_energy_node_form` (зміна), `action_td_energy_node_list` (нова) | form/list `td.energy.node` | form: у `<header>` кнопка «Картка вузла» (`action_open_card`); нова вкладка «Схема Пульту» (`sld_show`, `sld_shape`, `sld_x/y/w/h`, `sld_label`, `sld_anchor_id`; усе `readonly` без групи «Енергетик»); група «Захист» (`protection_trip_unit`, `protection_ir_ratio`, `trip_count_year` readonly; `invisible="kind not in ('cell','line')"`); група «PFC» (`pfc_step_kvar`, `pfc_steps_total`; `invisible="cell_type != 'pfc'"`); `sld_state` — badge у заголовку. Дія `action_td_energy_node_list`: `view_mode="list,form"`, domain `kind in (line, cell, transformer, section, switchboard, input, substation)`, context `search_default_group_kind`; list колонки `code`, `name`, `kind`, `parent_id`, `p_now`, `sld_state` (badge), `live_status` |
| V-28 | `view_td_energy_meter_form`/`_list` (зміна) | `td.energy.meter` | форма: група «Повірка» (`last_verification`, `verification_months`, `next_verification`); list: `next_verification` (optional show, `decoration-warning="next_verification and next_verification < today + 30"`) |
| V-29 | `view_td_energy_outage_plan_list` / `_form` / `_search`, `action_td_energy_outage_plan` | `td.energy.outage.plan` | list: `name`, `node_id`, `start`, `end`, `state` (badge: draft muted, pending warning, approved success, rejected danger, done muted, cancelled muted), `affected_count`, `production_count`; form: статусбар `state`; header: «Надіслати на узгодження» (`action_submit`, `invisible="state != 'draft'"`), «Узгодити» (`action_approve`, `invisible="state != 'pending'"`, група `mrp.group_mrp_manager`), «Відхилити» (wizard причини → `action_reject`), «Скасувати»; поля `node_id`, `reason`, `reason_text` (`invisible="reason != 'other'"`), `start`, `end`, `note`; вкладки «Зачеплені відгалуження» (`affected_node_ids` list readonly), «Замовлення на виробництво» (`production_ids` list readonly), чаттер; search: «Мої», «На узгодженні», «Майбутні» |
| V-30 | `view_td_energy_advice_list` / `_form`, `action_td_energy_advice` | `td.energy.advice` | list: `code`, `title`, `level`, `node_id`, `state` (badge), `snooze_until`, `expires_at`; form: усі поля, `actions` — Text (JSON) readonly; кнопки «Відкласти» (`action_snooze`), «Відхилити» (`action_dismiss`); меню лише для `group_td_energy_manager` у «Налаштування» |
| V-31 | `view_td_energy_ticket_wizard_form`, `action_td_energy_ticket_wizard` | form `td.energy.ticket.wizard`, `target="new"` | поля як M-28; кнопки «Створити заявку» (`action_create`, `btn-primary`), «Скасувати» |
| V-32 | `res_config_settings_view_form_td_energy` (зміна) | `res.config.settings` | у блоці `app name="td_energy"`: група «cos φ» — `td_energy_cos_phi_target` (0,95), `td_energy_cos_phi_warn` (0,92), `td_energy_cos_phi_alarm` (0,90) з підказкою «Пороги застосовуються до сигналів `energy/totals/cos_phi` і `energy/sections/S1|S2/cos_phi`»; група «Пульт» — `td_energy_pult_refresh_s`, `td_energy_alarm_list_limit`, `td_energy_load_warn_pct`, `td_energy_load_alarm_pct`; група «Прогноз» — `td_energy_forecast_weeks`, `td_energy_forecast_min_days`; група «Накопичувач» — `td_energy_bess_reserve_pct`; група «Повірка» — `td_energy_verify_warn_days` |
| V-33 | `views/menus.xml` | `ir.ui.menu` | таблиця 3.3 |
| V-34 | `view_td_energy_interval_list` (зміна) | list `td.energy.interval` | `is_backfill` — optional hide (badge «Синтетичні»); фільтр «Синтетичні» |

### 3.2 Клієнтські компоненти (OWL) UI-01…UI-11

Усе — `@odoo/owl`, реєстрація `registry.category("actions")`; дані — `orm.call("td.energy.dashboard", …)`; текст UI українською; кожен інтерактивний вузол — `<button>` з `aria-label`; кольори станів — не лише колір (текстовий чип/пунктир) як у макеті.

| ID | Компонент / тег | Вміст і поведінка |
|---|---|---|
| UI-01 | `Pult` (`td_energy.pult`) | Шапка (крихти «Енергетика / АРМ енергетика», h1 «Пульт енергетика», підзаголовок з `meta.subtitle`, індикатор «Живі дані · HH:MM» / «Немає даних · {вік}», перемикач періоду `Зараз/Зміна/Доба/Місяць`, кнопки «Відкрити в 3D»); смуга KPI (6 карток, R-27); банер рекомендації (`advice`); `Sld`; блок «Профіль доби · 15 хв»; «Тривоги й події · активних N» (`AlarmList`); «Найбільші споживачі зараз»; «Енергія на виробництво · сьогодні»; «ТО й відключення». Підписка на шину (UI-10), дебаунс 2 с, резервне опитування `meta.refresh_s` (30). Стан: `period`, `parts`, `selNode`. Кнопка «Звіт за зміну» — лише `capabilities.report` |
| UI-02 | `SldCanvas` | Полотно `canvas[0]×canvas[1]` (1320×452). Блоки — абсолютно позиціоновані `<button>` (текст `lines`), шини (`bar`) — смуги, `switch` — малий прямокутник, `label` — текст. Ребра — SVG-ламані (R-26 п.4). Вибраний вузол — обведення `0 0 0 3px accent`; повторний клік знімає вибір. Панель під полотном: `title`, `facts[]`, «Відкрити картку вузла» (якщо `card=true`), «Показати в 3D», «×» |
| UI-03 | `ProfileChart` | SVG 880×250, вісь 0–24 год, `X(h)=40+h/24·820`, `Y(v)=230−v/900·210` (масштаб — `max(contract, піки)×1,125`); серії: споживання (лінія), з мережі (заливка), СЕС (заливка), договірна (пунктир), прогноз (пунктир `cons_fc`, `grid_fc`), вертикаль «зараз», маркер піку; легенда-перемикачі (D-10); підсумок «Прогноз до кінця доби», «Експорт сьогодні», «Небаланс обліку за {година}» |
| UI-04 | `AlarmList` | Рядки `level` (чип «Тривога/Увага/Інфо/Вирішено»), час, заголовок, деталі, діагностика (розгортається), кнопки за `actions[]` і «Підтвердити» / «Взяти в роботу» (лише з `capabilities.ack`), текст «Підтверджено: {користувач} о HH:MM» |
| UI-05 | `NodeCard` (`td_energy.node_card`) | Шапка (шлях «← АРМ енергетика / ГРЩ 0,4 кВ / Секція 1 / QF-2 / ШР-2», h1, чипи, кнопки «Показати в 3D», «Запланувати відключення», «Створити заявку ТО»); 5 KPI; `CurrentChart`; таблиця відгалужень із фільтром Усі/Працюють/Не працюють; блоки «Облік», «Захист {QF}», «Події фідера», «Обслуговування», «Планове відключення» |
| UI-06 | `CurrentChart` | SVG: струм (А) за добу 15 хв, лінії «увага 80 %» і «номінал», маркер максимуму, «зараз» |
| UI-07 | `OutageDialog`, `TicketDialog` | `OutageDialog`: дата, причина (4 значення), початок, кінець, динамічний підрахунок «Під відключення потрапляють N відгалужень: … На цей час заплановано M замовлень…» через `preview`; «Надіслати на узгодження» = `create` + `action_submit`; `TicketDialog`: відкриває `td.energy.ticket.wizard` через `action.doAction` |
| UI-08 | `Generation` (`td_energy.generation`) | Сітка карток `cards[]` (R-38): заголовок, чип стану, KPI, факти, посилання на картку вузла/«Показати в 3D»; дані — API-13 |
| UI-09 | `Mobile` (`td_energy.mobile`) | Адаптивний (≥ 360 px) екран: шапка «Енергетика · чергування», 3 вкладки (Стан, Тривоги·N, Схема), реєстр вкладок `registry.category("td_energy.mobile_tabs")` (W4 додає «Обхід»); кнопки не менше 48 px; дані — API-12 |
| UI-10 | `useEnergyBus(callback, parts)` | Підписка `bus_service.addChannel("td_energy")` + `subscribe("td_energy/update", …)`; дебаунс 2 с; відписка в `onWillUnmount` |
| UI-11 | `td_energy.scss` | Токени кольорів станів: `ok #017E84`, `warn #c2410c`, `alarm #b91c1c` (пунктир), `off #9ca3af` (пунктир), `gen #b45309`; `accent #714B67` |

### 3.3 Меню після W1 (`views/menus.xml`)

Корінь: `td_factory3d.menu_td_root`; `menu_td_energy` (seq 50) як зараз.

| XML-id (`td_energy.`) | Назва | Батько | seq | Групи | Дія |
|---|---|---|---|---|---|
| `menu_td_energy_pult` | Пульт | `menu_td_energy` | 5 | `group_td_energy_user` | `action_td_energy_pult` |
| `menu_td_energy_overview` | Завантаження вузлів | `menu_td_energy` | 15 | `group_td_energy_user` | `action_td_energy_overview` (існуюча; **перейменовано** з «Огляд», seq було 10) |
| `menu_td_energy_scheme` | Схема мережі | `menu_td_energy` | 20 | user | без змін |
| `menu_td_energy_nodes` | Вузли мережі | `menu_td_energy` | 25 | user | `action_td_energy_node_list` |
| `menu_td_energy_generation` | Генерація й резерв | `menu_td_energy` | 35 | user | — (розділ) |
| `menu_td_energy_generation_overview` | Огляд | `menu_td_energy_generation` | 10 | user | `action_td_energy_generation` |
| `menu_td_energy_event` | Події | `menu_td_energy` | 80 | user | `action_td_energy_event` (default filter «Активні»; перейменовано з «Журнал подій») |
| `menu_td_energy_outage_plan` | Планові відключення | `menu_td_energy` | 72 | user | `action_td_energy_outage_plan` |
| `menu_td_energy_advice` | Рекомендації | `menu_td_energy_config` | 40 | `group_td_energy_manager` | `action_td_energy_advice` |
| `menu_td_energy_mobile` | Чергування (телефон) | `menu_td_energy` | 6 | user | `action_td_energy_mobile` |

Решта існуючих меню (`menu_td_energy_meter`, `_profile`, `_peak`, `_alloc`, `_balance`, `_outage`, `_config`, `_tariff`, `_pool`, `_recompute`, `_settings`) — без змін. Розділ «Генерація й резерв» створює `td_energy` (A-25); міст додає дочірні пункти (Частина II).

## 4. Права

### 4.1 `security/ir.model.access.csv` — додані рядки

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_energy_outage_plan_user,td.energy.outage.plan user,model_td_energy_outage_plan,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_outage_plan_manager,td.energy.outage.plan manager,model_td_energy_outage_plan,td_energy.group_td_energy_manager,1,1,1,0
access_td_energy_outage_plan_mrp,td.energy.outage.plan mrp manager,model_td_energy_outage_plan,mrp.group_mrp_manager,1,0,0,0
access_td_energy_outage_plan_admin,td.energy.outage.plan admin,model_td_energy_outage_plan,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_advice_user,td.energy.advice user,model_td_energy_advice,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_advice_manager,td.energy.advice manager,model_td_energy_advice,td_energy.group_td_energy_manager,1,1,0,0
access_td_energy_advice_admin,td.energy.advice admin,model_td_energy_advice,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_ticket_wizard_manager,td.energy.ticket.wizard manager,model_td_energy_ticket_wizard,td_energy.group_td_energy_manager,1,1,1,1
```

Існуючі рядки `td.energy.event` (user 1,0,0,0; manager 1,1,1,0; admin 1,1,1,1) і `td.energy.node` (manager 1,1,1,1) достатні. `td.energy.dashboard` — AbstractModel без ACL (контроль у методах, M-27). Користувач `mrp.group_mrp_manager` без групи енергетики читає лише `td.energy.outage.plan` (посилання з activity); методи `action_approve/reject` пишуть через `sudo()` після перевірки групи.

### 4.2 Групи (`security/td_energy_security.xml`) — додано

```xml
<record id="group_td_energy_chief" model="res.groups">
    <field name="name">Енергетика: головний енергетик</field><field name="privilege_id" ref="privilege_td_energy"/><field name="sequence">40</field>
    <field name="implied_ids" eval="[Command.link(ref('group_td_energy_manager'))]"/>
</record>
<record id="td_factory3d.group_td_admin" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_td_energy_chief'))]"/>
</record>
```

Ролі E-06: «Енергетик» = `group_td_energy_manager` (існуюча, «Енергетика: енергетик»); «Головний енергетик» = `group_td_energy_chief` (імпліцитно містить «Енергетика: енергетик»). Дві особи для підтвердження класу B (E-06) — «ще один користувач із `group_td_energy_manager`» — реалізує W2; W1 лише створює групу й використовує її в `action_release/resolve`. Адміністратор (`td_factory3d.group_td_admin`) отримує `chief`.

### 4.3 Record rules

`td_energy_outage_plan_rule_company` — модель `td.energy.outage.plan`, домен `['|', ('company_id','=',False), ('company_id','in',company_ids)]`, глобальне. Події, поради (`advice`) — без компанії.

### 4.4 Захист даних і дій

- Ключі вартості (`cost_uah`, `tariff_uah`, `price`) без `group_td_energy_cost` **видаляються** з відповідей API-05, API-07, API-12 (AC-107).
- `action_ack/take` — `group_td_energy_manager`; `action_release/resolve` — виконавець або `group_td_energy_chief`; `action_approve/reject` — `mrp.group_mrp_manager`; `_td_backfill` — адміністратор.
- Повідомлення шини не містять даних (A-28), тож безпеки читання шина не змінює.

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`) — нові параметри

| Ключ | За замовчуванням | Призначення |
|---|---|---|
| `td.energy.cos_phi_target` | `0.95` | ціль PFC (E-10) |
| `td.energy.cos_phi_warn` | `0.92` | попередження (`warn_low` сигналів cos φ) |
| `td.energy.cos_phi_alarm` | `0.90` | тривога (`alarm_low`) |
| `td.energy.pult_refresh_s` | `30` | резервне опитування UI-01 |
| `td.energy.bus_throttle_s` | `5` | мінімальний інтервал тіків шини (R-33) |
| `td.energy.alarm_list_limit` | `8` | рядків у списку тривог Пульту |
| `td.energy.load_warn_pct` | `80` | `warn` вузла за завантаженням (R-26) |
| `td.energy.load_alarm_pct` | `100` | `alarm` |
| `td.energy.forecast_weeks` | `8` | глибина історії для прогнозу (однакові дні тижня) |
| `td.energy.forecast_min_days` | `3` | мінімум днів для прогнозу |
| `td.energy.advice_snooze_min` | `30` | відкладання рекомендації |
| `td.energy.bess_reserve_pct` | `30` | «резерв на відключення мережі» (лише показ у фактах) |
| `td.energy.verify_warn_days` | `30` | за скільки днів нагадувати про повірку |
| `td.energy.pv_kwp` | `920` | потужність СЕС для відсотка «% піку» і backfill |

`res.config.settings` (розширення, V-32): поля `td_energy_*` з `config_parameter`; `set_values` для `cos_phi_warn/alarm` викликає `_td_apply_cos_thresholds()` — записує `warn_low`/`alarm_low` (і `warn_low_on=True`, `alarm_low_on=True`) у сигнали `energy/totals/cos_phi`, `energy/sections/S1/cos_phi`, `energy/sections/S2/cos_phi` (патерн `_f3d_apply_contract_thresholds`, `EN/models/f3d_energy_tariff.py:118`). Валідація: `alarm < warn ≤ target ≤ 1` інакше `ValidationError("Пороги cos φ: тривога < попередження ≤ ціль ≤ 1.")`.

### 5.2 `data/sld_layout.csv` (з геометрії `geo` у `Main.dc.html`, полотно 1320 × 452)

Колонки: `code,shape,x,y,w,h,label,anchor`. Завантажується `hooks._load_sld_layout(env)`: для вузла за `code` виставляє `sld_show=True` і решту полів **лише якщо** `sld_show=False` і `sld_x=sld_y=0` (правки користувача не перезаписуються); відсутній код → пропуск із `_logger.warning`. Очікувано 21 вузол.

| code | shape | x | y | w | h | label | anchor |
|---|---|---|---|---|---|---|---|
| GRID-10KV | box | 580 | 24 | 160 | 44 | Ввід 10 кВ | |
| RM6-1 | box | 580 | 100 | 160 | 44 | RM6-1 | |
| T1 | box | 230 | 192 | 200 | 64 | T1 | |
| T2 | box | 890 | 192 | 200 | 64 | T2 | |
| SEC-1 | bar | 40 | 298 | 590 | 6 | Секція шин 1 · 0,4 кВ | |
| SEC-2 | bar | 690 | 298 | 590 | 6 | Секція шин 2 · 0,4 кВ | |
| Q1 | label | 342 | 266 | 0 | 0 | Q1 · 1600 А | |
| Q2 | label | 1002 | 266 | 0 | 0 | Q2 · 1600 А | |
| QS | switch | 636 | 289 | 48 | 24 | QS | |
| PV-INV | box | 1110 | 192 | 88 | 64 | СЕС |  |
| CHP | box | 1214 | 192 | 88 | 64 | КГУ |  |
| PFC-1 | box | 50 | 336 | 120 | 84 | PFC-1 |  |
| BW-3 | box | 190 | 336 | 120 | 84 | ШР-3 |  |
| BW-2 | box | 330 | 336 | 120 | 84 | ШР-2 |  |
| C1 | box | 470 | 336 | 120 | 84 | C1 |  |
| BW-1 | box | 694 | 336 | 90 | 84 | ШР-1 |  |
| BW-4 | box | 792 | 336 | 90 | 84 | ШР-4 |  |
| C2 | box | 890 | 336 | 90 | 84 | C2 |  |
| PFC-2 | box | 988 | 336 | 90 | 84 | PFC-2 |  |
| BESS | box | 1086 | 336 | 90 | 84 | BESS |  |
| ATS-1 | box | 1184 | 336 | 90 | 84 | АВР · ДГУ | SEC-2 |

Вузли `SWB-1`, `QF-1…QF-4`, `QF-C1`, `QF-C2`, `SEC-*` (крім шин) на схемі не показуються (`sld_show=False`): лінії `BW-x`, `C1`, `C2` підʼєднуються до шин через найближчого видимого предка (R-26 «Ребра»). Колонка `anchor` потрібна лише там, де найближчий видимий предок не збігається з візуальним батьком: `ATS-1` (батько `SWB-1` не показано) → `SEC-2`.

### 5.3 Сигнали W1 (`data/energy_signals.csv` + `data/energy_sources.csv`), `_ensure_w1_signals(env)`

Джерело `MB-U73-SWB-CTRL` (`type=modbus_tcp`, `module=energy`, unit 73, host `iot-sim`, порт 502, `timeout_s=3`, `retries=2`, `max_block=125`, `gap_max=8`, обладнання `SWB-1`) — **контролер ГРЩ** (QS, PFC); карта регістрів — ПРИПУЩЕННЯ для емулятора (A-24), на об'єкті — за документом контролера. Функція `_ensure_w1_signals(env)` ідемпотентно створює відсутні сигнали та джерело (ті самі кроки, що `_load_signals` post_init_hook), не змінює існуючі.

| Код | kind / одиниця | Адреса (FC3, HR; u16) | Пороги / примітка |
|---|---|---|---|
| `energy/cells/QS/state` | `state`, states `["open","closed"]` | 100; map `{"0":"open","1":"closed"}` | період 10 с, `store_period_s` 300 |
| `energy/cells/PFC-1/q_kvar` | gauge, квар | 110 | підключена потужність |
| `energy/cells/PFC-1/steps_on` | gauge | 111 | вимкнено = 0 |
| `energy/cells/PFC-1/steps_total` | gauge | 112 | 10 |
| `energy/cells/PFC-1/fault_step` | gauge | 113 | `alarm_high=0.5`, `min_duration_s=60`, `alarm_title` «PFC-1: ступінь {value} не вмикається»; створює заявку ТО (CT-05) |
| `energy/cells/PFC-2/q_kvar` | gauge, квар | 120 | |
| `energy/cells/PFC-2/steps_on` | gauge | 121 | |
| `energy/cells/PFC-2/steps_total` | gauge | 122 | |
| `energy/cells/PFC-2/fault_step` | gauge | 123 | як PFC-1, «PFC-2: …» |
| `energy/sections/S1/cos_phi` | gauge (обчислюваний, `src=module`) | — | `warn_low=0.92`, `alarm_low=0.90`, `min_duration_s=300`, без `alarm_title` (заявка не створюється; подія R-13 п.4) |
| `energy/sections/S2/cos_phi` | gauge (обчислюваний) | — | те саме |
| `energy/sections/S1/p_kw`, `…/S2/p_kw` | gauge, кВт (обчислюваний) | — | без порогів |
| `energy/sections/S1/q_kvar`, `…/S2/q_kvar` | gauge, квар (обчислюваний) | — | без порогів, після компенсації (`Q_s − q_pfc_s`) |

Разом **+14 сигналів, +1 джерело** (у БД: `energy` 297 → 311; `td.source` 135 → 136). Зміна існуючого сигналу `energy/totals/cos_phi`: `warn_low` 0,95 → **0,92** (тримається `_td_apply_cos_thresholds`). Для інсталяцій, де сигналів ще немає (свіжа установка), рядки додаються до `energy_signals.csv` (колонка `origin`: `sim_data` для 9 регістрових, `module` для 5 обчислюваних…). *Примітка до підрахунку:* 9 регістрових (QS + 2×4) + 6 обчислюваних (cos ×2, p ×2, q ×2) = 15 сигналів; рядків у CSV — 15; у таблиці вище `p_kw`/`q_kvar` секцій згруповано. **Очікувано +15 сигналів, +1 джерело; `energy` 297 → 312.**

### 5.4 `post_init_hook` і міграція `19.0.1.1.0`

Кроки (ідемпотентні; міграція — `post-migration.py`, модуль у стані `to upgrade`):
1. `_ensure_w1_signals(env)` (5.3);
2. `_td_apply_cos_thresholds()` із поточних параметрів (за замовчуванням 0,92/0,90);
3. `_load_sld_layout(env)` (5.2);
4. події: для кожного `td.energy.event` з `title IS NULL` застосувати R-24 (SQL-пакетами 5 000), `state` за R-24 (старі `warn/bad` → `resolved`, щоб не вигадувати «активних»); `resolved_at = ts`;
5. параметри (5.1) — створюються XML (noupdate), для існуючих БД — `ir.config_parameter` записи з xml-id; `pfc_*` на вузлах `PFC-1`, `PFC-2` — дефолти колонки (35, 10);
6. група `group_td_energy_chief` — XML-дані при оновленні модуля.

Очікувані кількості на демо-БД (`f3d_full2` після міграції): вузлів з `sld_show=True` — 21; нових сигналів — 15; джерел +1; подій оновлено — N (0 на демо); параметрів +14.

### 5.5 `uninstall_hook`

Без змін; нові сигнали/джерело — видаляє існуючий крок деінсталяції сигналів `module='energy'`; бізнес-дані (`td.energy.event`, `.outage.plan`, `.advice`, інтервали) не видаляються. `neutralize.sql`: додати `UPDATE ir_cron SET active=false WHERE id IN (… 3 нових кронів …)` і вимкнення джерела `MB-U73-SWB-CTRL` (як для решти `energy` джерел).

## 6. Крони й фонові процеси

Усі — `user_id=base.user_root`, `try/except` із `_logger.exception`, без підйому винятку; за вимкненого `td.energy.read_enabled` не діють.

| XML-id | Назва | Інтервал | Метод | Один прогін | Ліміт |
|---|---|---|---|---|---|
| `cron_td_energy_advice` | Енергетика: рекомендації | 5 хв | `td.energy.advice._cron_advice` | реєстр `_td_advice_rule_*` (R-32); у W1 — порожній | ≤ 3 с |
| `cron_td_energy_outage_plan` | Енергетика: планові відключення | 15 хв | `td.energy.outage.plan._cron_close` | R-31 п.7 | ≤ 2 с |
| `cron_td_energy_verification` | Енергетика: повірка лічильників | 1 доба, `nextcall` 06:00 Київ | `td.energy.meter._cron_verification` | R-34 | ≤ 2 с |

Існуючий `cron_td_energy_live` (1 хв) додатково: R-35 (cos φ секцій) і `bus.tick('kpi')`; `cron_td_energy_intervals` (5 хв) після `_after_build`: `bus.tick('profile')` — один раз за прогін.

## 7. HTTP/JSON API

Нових HTTP-маршрутів немає (E-09: `/f3d/*` не змінюється). Виклики — ORM-RPC (`orm.call`) від імені користувача; ключ `cost` описано в M-27. Усі методи — `@api.model`, якщо не вказано.

| ID | Сигнатура | Вхід → вихід | Помилки |
|---|---|---|---|
| API-05 | `td.energy.dashboard.get_pult(period="now", parts=None)` | `period ∈ {now, shift, day, month}`; `parts` — підмножина `{"kpis","sld","profile","alarms","side","advice"}` або `None` (усе) → JSON «Пульт» (нижче) | невідомий `period` → `UserError("Невідомий період: %s.")`; без групи → `AccessError` |
| API-06 | `td.energy.dashboard.get_alarms(limit=None, scope="all")` | `scope ∈ {all, active, mine}` → `{"active_count": n, "items": [alarm…]}` (формат `alarms` API-05) | — |
| API-07 | `td.energy.dashboard.get_node_card(code, period="day")` | `code` вузла → JSON картки (нижче); `period ∈ {day}` (W1) | невідомий код → `UserError("Невідомий вузол: %s.")`; для будь-якого відомого вузла — картка зі скороченим набором блоків за видом (R-30 п.1) |
| API-08 | `td.energy.event.action_ack/action_take/action_release/action_resolve` (M-21) | список id → `True` | `AccessError`, `UserError` (M-21) |
| API-09 | `td.energy.outage.plan.preview(node_code, start, end)` (M-25) | → `{"tap_codes","tap_count","orders","order_count"}` | `UserError` |
| API-10 | `td.energy.outage.plan.create(vals)` + `action_submit/approve/reject/cancel` (M-25) | стандартні | `AccessError`, `UserError`, `ValidationError` |
| API-11 | `td.energy.advice.action_snooze(minutes=None)`, `action_dismiss()`, `get_open()` (M-26) | → `True` / `dict` / `False` | `AccessError` |
| API-12 | `td.energy.dashboard.get_mobile(tab="state")` | `tab ∈ {state, alarms, scheme}` → JSON мобільного (нижче) | як API-05 |
| API-13 | `td.energy.dashboard.get_generation()` | → `{"cards": [card…], "ts": iso}` (R-38) | `AccessError` |
| API-14 | `td.energy.ticket.wizard.action_create()` (M-28) | → `act_window` | — |
| API-15 | `td.energy.interval._td_backfill(...)` (M-24) | → статистика R-36 п.10 | `AccessError` |

### Відповідь API-05 (ключі й типи; значення — приклад із макета, 14:20)

```json
{
  "meta": {"now": "2026-10-17T11:20:00", "now_local": "14:20", "period": "now",
           "data_state": "ok", "age_s": 12, "subtitle": "Меблеве підприємство · ввід 10 кВ · T1 і T2 по 1000 кВА · ГРЩ 0,4 кВ, дві секції · договірна потужність 800 кВт",
           "contract_kw": 800, "tariff_uah": 8.4, "refresh_s": 30, "control_available": false,
           "capabilities": {"ack": true, "take": true, "cost": true, "outage_plan": true, "report": false}},
  "kpis": {
    "grid": {"kw": 358, "pct": 45, "reserve_kw": 442, "export_kw": 0},
    "load": {"kw": 667, "pv_share_pct": 46, "chp_state": "stop"},
    "energy": {"label": "З мережі сьогодні", "kwh": 6284, "cost_uah": 52786, "price_uah": 8.4},
    "peak": {"label": "Пік доби (15 хв)", "kw": 631, "note": "о 07:30 · 79 % договірної"},
    "generation": {"pv_kw": 309, "pv_pct_kwp": 34, "bess_soc_pct": 82, "bess_kw": 0, "genset": null},
    "cos_phi": {"plant": 0.93, "sections": [0.95, 0.88], "target": 0.95, "warn": 0.92, "alarm": 0.90, "low_sections": [2]}},
  "advice": null,
  "sld": {"canvas": [1320, 452],
          "nodes": [{"code": "BW-2", "label": "ШР-2", "shape": "box", "x": 330, "y": 336, "w": 120, "h": 84, "state": "ok",
                     "lines": ["ШР-2", "192 А · 30 %", "лінії C–D"], "title": "ШР-2 · лінії C–D, нестинг, портал",
                     "facts": ["192 А з 630 А · 30 %", "124 кВт · 10 відгалужень, 2 не працюють"], "card": true, "anchor": "SEC-1"}],
          "edges": [{"from": "SEC-1", "to": "BW-2", "state": "ok"}]},
  "profile": {"step_min": 15, "now_slot": 57, "contract_kw": 800,
              "cons": [210.0, "…96 значень або null після now_slot…"], "grid": ["…"], "pv": ["…"],
              "cons_fc": ["null до now_slot; далі прогноз або всі null"], "grid_fc": ["…"],
              "peak": {"kw": 631, "slot": 30}, "forecast_days_used": 8},
  "foot": {"forecast_kwh": 9120, "export_kwh": 118, "imbalance": {"pct": 1.8, "hour": "13:00–14:00", "tol_pct": 3}},
  "alarms": {"active_count": 3, "items": [{"id": 101, "level": "alarm", "time": "13:47", "title": "Лічильник PM-QF-C2 не на зв'язку",
              "detail": "33 хв без даних (Modbus). Енергія фідера C2 рахується як оцінка.", "state": "active",
              "acked_by": null, "acked_at": null, "assigned": null, "node_code": "C2",
              "actions": [{"code": "diag", "label": "Діагностика"}], "diag": "Джерело MB-U14-PM-QF-C2 (iot-sim:502, unit 14): немає відповіді з 13:47:12 · колектор COL-MAIN на зв'язку · перевірте лінію й комірку QF-C2."}]},
  "top": [{"code": "DUST-1", "name": "Вентилятори аспірації", "kw": 96}],
  "mo": {"rows": [{"name": "WH/MO/00418", "product": "Корпус шафи-купе 2000", "kwh": 214, "cost_uah": 1798, "share_pct": 3.4}], "pools_kwh": 1120},
  "maint": [{"title": "PFC-2 · ступінь 3 не вмикається", "sub": "заявка з тривоги · 14:06", "state": "Нова", "kind": "request", "id": 77}]
}
```

Правила форми: `kpis.energy`/`kpis.peak`/`foot` залежать від `period` (R-27); `cost_uah`, `price_uah`, `tariff_uah`, `mo.rows[].cost_uah`, `capabilities.cost` — лише з `group_td_energy_cost`, інакше ключі **відсутні**; `kpis.generation.genset` — `null` без моста або `{"state": "reserve|running|fault|offline", "label": str, "fuel_pct": int|null}`; `profile.*` масиви довжини 96 (`null` — немає даних); `data_state ∈ {ok, partial, stale}` (`stale` — немає свіжих сигналів `energy/totals/p_now` і обох вводів; `partial` — несвіжих фідерів > 0); значення без свіжих даних — `null`.

### Відповідь API-07 (картка вузла, `BW-2`)

```json
{"node": {"code": "BW-2", "name": "ШР-2 · лінії C–D, нестинг, портал", "kind": "line", "kind_label": "Шинопровід 630 А",
          "path": [{"code": "SWB-1", "name": "ГРЩ 0,4 кВ"}, {"code": "SEC-1", "name": "Секція 1"}, {"code": "QF-2", "name": "QF-2"}, {"code": "BW-2", "name": "ШР-2"}],
          "chips": [{"text": "Під напругою", "state": "ok"}, {"text": "Шинопровід 630 А · живиться від QF-2", "state": "ok"}, {"text": "Лічильник PM-QF-2 на зв'язку", "state": "ok"}],
          "can_3d": true},
 "kpis": {"current": {"a": 192, "pct": 30, "phases": [188, 195, 193], "rating_a": 630},
          "power": {"kw": 124, "p_inst_kw": 217, "cos_phi": 0.91},
          "energy": {"kwh": 1384, "cost_uah": 11626, "orders": 7},
          "peak": {"a": 328, "time": "07:45", "warn_a": 504},
          "idle": {"kw": 2.4, "names": ["VSAW-1", "CNC-4"]}},
 "chart": {"step_min": 15, "now_slot": 57, "a": ["96 значень або null"], "warn_a": 504, "rating_a": 630, "peak": {"a": 328, "slot": 31}},
 "taps": {"sum_kw": 120.7, "aux_kw": 3.3, "count": 10, "rows": [{"tap": "TAP-SAW-3", "code": "SAW-3", "name": "Пакетний розкрій", "inst_kw": 45, "now_kw": 31, "state": "run", "job": "WH/MO/00418 · розкрій плит", "node_code": "SAW-3"}]},
 "meter": {"code": "PM-QF-2", "model": "Schneider PM5560", "ct_ratio": "630/5", "last_ts": "14:20:05", "last_kwh": 1284517, "next_verification": "2026-10-30", "balance_pct": -1.2},
 "protection": {"breaker": "QF-2", "rating_a": 630, "trip_unit": "електронний", "ir": {"ratio": 0.9, "a": 567}, "trips_year": 0, "thermography": {"date": "2026-10-21", "state": "Заплановано"}},
 "events": [{"time": "07:45", "text": "Максимум доби 328 А, нижче порогу уваги", "kind": "peak"}],
 "maintenance": [{"title": "CNC-4 · заміна шпинделя", "when": "у роботі", "state": "У роботі", "id": 12}],
 "outage": {"plan_id": 5, "when": "25.10 · 07:00–09:00", "reason": "протяжка з'єднань шинопроводу", "orders": 3, "state": "pending", "state_label": "на узгодженні"},
 "extra": {}}
```
Форма: ключі `taps`, `meter`, `protection`, `outage`, `maintenance`, `chart` відсутні, якщо для `kind` вузла блок не передбачений (R-30 п.1); `cost_uah` — за групою; `extra` — результат хука `_td_node_card_extra`.

### Відповідь API-12 (мобільний, `get_mobile(tab)`)

`state`: `{"grid_kw","pct","pv_kw","bess":{"soc_pct","kw","text"},"genset_ats":{"text"},"cos_phi":{"plant","low_sections"}}`; `alarms`: `{"active_count", "active":[alarm…], "info_today":[{"time","text"}], "advice": advice|null}`; `scheme`: `[{"code","name","value","state"}…]` — вузли `sld_show` видів `input`, `transformer`, `line`, `generator`, `storage`, `ats`, `cell` (`cell_type='pfc'`) у порядку `sld_y, sld_x` (на демо: `GRID-10KV, T1, T2, BW-2, C2, PFC-2, PV-INV, BESS, ATS-1` та решта ліній); `tab` обмежує обсяг відповіді (усі три — для `tab=None`). Розмір відповіді ≤ 20 КБ. Без `cost` ключів.

## 8. Сервісна частина

### 8.1 Емулятор `iot_sim` (власник C, `factory3d/services/iot_sim/` → після перейменування `services/iot_sim/`)

Новий пристрій `SWB-CTRL` (`catalog/devices.yaml`: `code: SWB-CTRL`, `role: switchboard_ctrl`, `protocols: [P-07]`, `unit_id: 73`, `driver: swb`) і модель `iot_sim/models/swb.py` (`@register_model("swb")`, фаза `AGGREGATE`):

| Регістр (FC3, u16) | Сигнал | Поведінка |
|---|---|---|
| 100 | `energy/cells/QS/state` | `0` (open) завжди в W1; параметр сценарію `qs_closed=true` → `1` (для ТК-14) |
| 110/111/112/113 | `energy/cells/PFC-1/{q_kvar,steps_on,steps_total,fault_step}` | `need = max(0, Q_s − P_s·tan(acos(target)))`, `target=0.95` (параметр світу); `steps_on = min(10, ceil(need/35))`; `q_kvar = steps_on·35`; `steps_total=10`; `fault_step` — див. нижче |
| 120/121/122/123 | `…/PFC-2/…` | те саме для секції 2 |

`P_s`, `Q_s` секції — із наявних значень сигналів `energy/lines/*/p_now`, `cos_phi` (як `tools/live` R-06 п.2). Сценарій `pfc_step_fault` (`catalog` + `td_iot_sim/data/td_sim_scenario.xml`, група `energy`, параметри `{"section": 2, "step": 3}`, тривалість 0 = до зупинки): коли `steps_on` досягає `step`, лишається `step−1`, `fault_step = step`; після зупинки сценарію `fault_step=0`. Нові рядки `catalog/signals.csv` і `td_iot_sim/data/td_sim_signal.csv` (9 регістрових сигналів, «новий»); `cos φ` секції в емуляторі — після компенсації (`cos_after`, R-06 п.2).

### 8.2 Збирач

Змін коду збирача немає: нове джерело `MB-U73-SWB-CTRL` підхоплюється з `GET /f3d/telemetry/config` (ETag) за `config_poll_s` (60 с). Навантаження: +1 джерело, 9 сигналів / 10 с.

## 9. Алгоритми й правила

### R-24 Розбиття `text` на `title`/`detail` і початковий `state` (FR-36)

1. Якщо передано `title` — `detail = detail or ''`. Інакше: `text` обрізати по пробілах; знайти перший роздільник «. » (крапка+пробіл) **або** «: » (двокрапка+пробіл) на позиції ≤ 100; є — `title = text[:pos]` (без роздільника, без кінцевої крапки), `detail = text[pos+2:]`; немає — `title = text[:128]`, `detail = ''`. `title` > 128 символів → обрізати до 125 + «…».
2. Приклад: `text = "Лічильник PM-QF-C2 не на зв'язку. 33 хв без даних."` → `title = "Лічильник PM-QF-C2 не на зв'язку"`, `detail = "33 хв без даних."`.
3. `state`: `level='info'` → `na`; `warn/bad` → `active`. Явно передане допустиме `state` (backfill, міграція) — зберігається.

### R-25 Життєвий цикл події (FR-36)

Стани: `active → acked → resolved` (`na` лише для `info`). Переходи: `action_ack` (`active→acked`), `action_take` (`active|acked→acked` + виконавець), `action_release` (виконавець скинуто), `action_resolve` (`active|acked→resolved`, ручне), авто-вирішення (`_td_auto_resolve`):

| `kind` | Умова авто-вирішення | Хто викликає |
|---|---|---|
| `meter` | `meter.data_state` стало `ok` (`_td_update_state`, `EN/models/f3d_energy_meter.py:218`); збіг за `node` | `td.energy.meter` |
| `threshold` | статус сигналу повернувся в `ok` (хук `_td_status_event`, `EN/models/f3d_energy_event.py:129`); збіг за `signal` | event |
| `pfc` | `fault_step = 0` і `cos φ секції ≥ cos_phi_warn` | R-35 |
| `balance` | наступна година для вузла — `state='ok'` (R-07) | balance |
| `trip` | створюється як `warn`; авто-вирішується через 24 год (`now − ts > 24 год`) | `cron_td_energy_verification` (разом із R-34) |
| `ats`, `outage`, `peak`, `manual` | не вирішуються автоматично; `warn/bad` закриває людина | — |

`bad`/`warn` події без явного вирішення — `active`. Кожна зміна стану → `bus.tick('alarm')` (R-33).

### R-26 Стан вузла схеми, ребра, шини (FR-33, R-26)

Вхід: знімок живих значень (`td.energy.node._td_fresh_values()` — `EN/models/f3d_energy_node_live.py:21`), відкриті події `state in (active, acked)`, відкрите `td.energy.outage`. Обчислення `states(env, nodes)` — один знімок на виклик. Пріоритет: **(1)** відкрита `bad`-подія вузла (`node_id`) → `alarm`; **(2)** відкрита `warn`-подія → `warn`; **(3)** правило за видом; **(4)** `ok`.

| Вузол / вид | Правило (3) |
|---|---|
| `generator` `pv_inverters` (`PV-INV`) | `infra/totals/pv_now ≥ 1` → `gen`, інакше `off` |
| `generator` `chp` | `infra/chp/state ∈ {running, starting}` → `gen`; `fault` → `alarm`; інакше `off` |
| `generator` `genset` | острів (`infra/ats/position = 3`) → `gen`, інакше `off` |
| `storage` | `infra/bess/state ∈ {offline, fault}` → `alarm`; `\|infra/totals/bess_kw\| ≥ 1` → `gen` (D-05); інакше `ok` |
| `ats` (`ATS-1`) | відкрите `td.energy.outage` без `gen_started` → `alarm`; `position = 3` → `gen`; інакше `off` (резерв) |
| `cell` `coupler` (`QS`, шаф) | `energy/cells/QS/state = closed` → `ok`; `open` → `off`; сигналу немає → `off` |
| `cell` `pfc` (`PFC-1/2`) | `fault_step > 0` → `warn`; `cos φ секції < cos_phi_alarm` → `alarm`; `< cos_phi_warn` → `warn`; інакше `ok` |
| `transformer`, `line`, `cell` (feeder/cable/incomer), `consumer` | завантаження `load = p_now / номінал` (`rating_kva` для T, `rating_a`-еквівалент для ліній за R-06 п.1, `p_inst_kw` для споживача): `≥ load_alarm_pct` → `alarm`; `≥ load_warn_pct` → `warn`; даних немає (вузол має лічильник і `live_status in (stale, no_data)`) → `alarm`; `gap` → `warn`; без лічильника й без даних → `off` |
| `input`, `substation`, `section`, `switchboard` | відкрите відключення без `gen_started` → `alarm`; інакше `ok` |

**Ребра.** Для кожного вузла `N` із `sld_show` і `shape ∈ {box, bar}`: батько `P = N.sld_anchor_id` або найближчий предок (`parent_id` вгору) із `sld_show` і `shape ∈ {box, bar}` (мітки `label` і `switch` пропускаються). Немає `P` → ребра немає. Стан ребра: `gen`, якщо `N.sld_state='gen'`; `off`, якщо `N.sld_state='off'`; інакше `ok`. Геометрія (клієнт, `sld.js`, функція `edgePath(P, N)`):
- `P.shape='bar'`: вертикаль у `x = N.x + N.w/2`, затиснутому в `[P.x, P.x+P.w]`, від `N.y+N.h` до `P.y` (шина нижче вузла) або від `P.y+P.h` до `N.y` (шина вище);
- `N.shape='bar'`: вертикаль у `x = P.x + P.w/2`, затиснутому в `[N.x, N.x+N.w]`, між `P.y+P.h` і `N.y` (або `P.y` і `N.y+N.h`, якщо шина вище);
- `box→box`: вертикаль від центру низу `P` до `y_mid = (P.y+P.h+N.y)/2`, горизонталь до `N.x+N.w/2`, вертикаль до верху `N` (прямий відрізок, якщо центри збігаються).
Мітки `label` ребер не мають. **Шина** `bar` має стан `alarm` при відкритому відключенні без генерації, інакше `ok`. Вимикач `QS`: при `closed` між `SEC-1.x+w` і `SEC-2.x` малюється перемичка (смуга 6 px) і підпис «QS увімкнено», інакше «QS вимкнено».

Приклад (14:20 макета): `C2` лічильник `stale` 33 хв → `alarm`; `PFC-2` cos 0,88 < 0,92 і `fault_step=3` → `warn`; `PV-INV` 309 кВт → `gen`; `CHP` `stop` → `off`; `ATS-1` `position=2` → `off`; `QS` `open` → `off`; `T2` експорт 26 кВт → `ok`.

### R-27 KPI Пульту за періодом (FR-31)

Позначення: слот = 15 хв (UTC); `net(s) = Σ_{incomer}(kwh − kwh_export)` кВт·год; `p_net(s) = net·4` кВт; `cur` — поточний неповний слот: `partial = Σ delta(cur_start, now)` лічильників вводів (`meter._td_counter_series`, як R-15 п.1). Вікно `W`: `now` → від 00:00 Київ сьогодні; `shift` → `dates.shift_start(now, shift_hours)` (`EN/models/f3d_energy_interval.py:256,271`); `day` → 00:00…24:00; `month` → від 1-го числа 00:00 Київ.

1. `import_kwh = Σ_{s∈W} max(0, net(s)) + max(0, partial)`; `export_kwh = Σ max(0, −net(s))`.
2. `cost_uah = Σ max(0, net(s))·price(s)` (`price` — з рядка `td.energy.interval` вводу, для `cur` — `tariff._td_price_at(cur)`); лише з групою вартості.
3. `peak_kw = max_{s∈W} p_net(s)`, `peak_time` — місцевий початок слота `HH:MM` (для `month`: `DD.MM о HH:MM`); `peak_pct = round(peak_kw / contract_kw · 100)`, `contract_kw` — активний тариф на слот (`td.energy.tariff.contract_kw`); `day`: `peak_kw = max(факт, max прогнозу)`.
4. `day`: `energy.kwh = import_kwh(00:00…now) + Σ_{s>now} max(0, grid_fc(s))·0,25` (R-28); підписи: `now` — «З мережі сьогодні» / «Пік доби (15 хв)»; `shift` — «З мережі за зміну (з HH:MM)» / «Пік зміни»; `day` — «Прогноз на добу» / «Пік доби з прогнозом»; `month` — «З мережі за {назва місяця}» (українською, називний відмінок, як у макеті: «З мережі за жовтень») / «Пік місяця».
5. Живі (не залежать від `period`): `grid.kw = infra/totals/grid_kw`, `grid.export_kw = infra/totals/export_kw`, `grid.pct = round(grid_kw/contract·100)`, `grid.reserve_kw = contract − grid_kw`; `load.kw = energy/totals/p_now`; `load.pv_share_pct = min(100, round(pv_now/load·100))` (при `load=0` → `null`); `generation.pv_kw = infra/totals/pv_now`, `pv_pct_kwp = round(pv_now/td.energy.pv_kwp·100)`, `bess_soc_pct = infra/totals/bess_soc`, `bess_kw = infra/totals/bess_kw`; `cos_phi.plant = energy/totals/cos_phi`, `sections = [S1, S2]` із `energy/sections/S*/cos_phi`, `low_sections` — номери секцій із `cos < cos_phi_warn`.
6. Несвіжі/відсутні сигнали → `null` (UI «—»); `data_state` за M-27/API-05.

Приклад (`now`, 14:20): `Q1 384`, `Q2 −26` → `grid.kw 358`, `pct 45`, `reserve 442`; слотова логіка експорту: у слоті `net=+358·0,25` → `export_kwh` не росте (експорт вільний лише коли `net<0`).

### R-28 Профіль доби 15 хв і прогноз (FR-35)

1. **Факт.** Для слотів `0…now_slot−1` (локальна доба, 96 слотів): `cons[s] = Σ_{feeder} kwh·4`; `pv[s] = Σ_{generation, model sun2000} kwh·4`; `grid[s] = max(0, p_net(s))`. Для `now_slot` — живі: `cons = energy/totals/p_now`, `pv = infra/totals/pv_now`, `grid = infra/totals/grid_kw`. Слоти після `now_slot` — `null`.
2. **Типовий день** `typical15[w][s]` для дня тижня `w` сьогодні: останні `forecast_weeks` (8) таких самих днів тижня (без сьогодні), де ≥ 90 % слотів фідерів не `missing`; середнє `cons` і `pv` за слот. Днів `< forecast_min_days` (3) → прогнозні масиви `null`, `forecast_days_used = n`, у підвалі «Прогноз недоступний: замало історії».
3. **Прогноз.** `cons_fc[s] = typical.cons[s]` для `s ≥ now_slot`; `pv_fc[s] = typical.pv[s]·k_pv`, `k_pv = clamp(Σ_{s<now_slot} pv[s] / Σ_{s<now_slot} typical.pv[s], 0,3, 1,5)` (при знаменнику 0 → 1); `grid_fc[s] = cons_fc[s] − pv_fc[s]` (може бути < 0 — експорт). Перша прогнозна точка = поточна (лінія неперервна).
4. `foot.forecast_kwh = import_kwh(00:00…now) + Σ_{s>now_slot} max(0, grid_fc[s])·0,25`; `foot.export_kwh = export_kwh(00:00…now)`; `foot.imbalance` — останній `td.energy.balance` вузла `Q1` або `Q2` з `state in (ok, deviation)` за останню закриту годину: `pct = diff_pct`, `hour = "HH:00–HH+1:00"`, `tol_pct = balance_tol_pct`.
5. `profile.peak` — слот максимуму `p_net` сьогодні.

### R-29 Факти вузла (панель під схемою; `sld.nodes[].facts`)

Лише факти з даних; без даних — пропуск рядка (D-06).

| Вузол / вид | Рядки |
|---|---|
| `GRID-10KV` | «З мережі {grid_kw} кВт · договірна {contract} кВт»; «Лічильники вводу: PM-Q1, PM-Q2» |
| `RM6-1` | `note` вузла, якщо є; «{n} відгалужень» (число дітей) |
| `T1`/`T2` | «{p_kw} кВт · {s_kva/rating_kva %} %» або «експорт {X} кВт» при `p_kw<0`; «cos φ {cos}»; «Температура масла {temp_c} °C» (сигнал `energy/transformers/T/temp_c`); «Наступне ТО: {дата найближчої планової заявки}» |
| `PV-INV` | «{pv_now} кВт зараз · {pct} % піку»; «Виробіток сьогодні {Σ kwh_today} кВт·год»; «Інверторів на зв'язку: {n} з 8» (`status` сигнали `infra/pv/PV-INV-k/status` свіжі) |
| `CHP` | «{state_label}»; «Мотогодини {infra/chp/hours}» |
| `QS` | «Увімкнено: секції 1 і 2 працюють разом» / «Вимкнено: секції живляться окремо від T1 і T2» |
| `PFC-1/2` | «Увімкнено {q_kvar} квар ({steps_on} з {steps_total} ступенів)»; «cos φ секції {cos}»; при `fault_step>0` — «Ступінь {fault_step} не вмикається» |
| `BW-*`, `C1`, `C2` | «{i} А з {rating_a} А · {pct} %»; «{p} кВт · {n} відгалужень{, m не працюють}»; для `C*` — Σ споживачів лінії (топ-3 за потужністю); при несвіжому лічильнику — «Лічильник {code} не на зв'язку з {HH:MM}» і «Оцінка за балансом секції: ≈ {X} кВт» (`X = Σ секції − Σ інших фідерів секції`) |
| `BESS` | «Заряд {soc} %»; «{Заряджається|Розряджається} {|kW|} кВт» / «Очікування, 0 кВт»; «Резерв на відключення мережі: {bess_reserve_pct} %» |
| `ATS-1` | «Положення: {мережа|ДГУ}»; плюс `_td_node_facts_extra` (міст: паливо, тест, наступна подія ДГУ) |

Заголовок панелі (`title`) = `name` вузла (повна назва); `card=true` лише для `kind in (line, transformer, cell)` з `sld_show` (є картка).

### R-30 Картка вузла (FR-38, API-07)

1. **Перелік блоків за видом.** `line` (BW-x, C1/C2) і `cell` (feeder/cable): усі блоки; `transformer`: шапка, KPI (`current` — `i_a` сигнал, `power`, `energy`, `peak`; без `idle`), `chart`, `meter` (лічильник вводу `PM-Q*`), `events`, `maintenance`; `consumer`/`tapoff`: шапка, `power`, `energy`, `events`, `maintenance`; інші види — шапка, `events`, `maintenance`, `extra`. Невідомий код → `UserError`.
2. **Шлях** (`path`): предки вгору до першого `kind='switchboard'` включно, у порядку зверху вниз; для вузла нижче ГРЩ — від ГРЩ; для `transformer` — від `RM6-1`.
3. **Чипи:** «Під напругою» (`state ok`) якщо `sld_state != alarm` і вузол не `off`; «{line_kind_label} {rating_a} А · живиться від {QF}»; «Лічильник {code} на зв'язку|не на зв'язку» (`meter.data_state`).
4. **Струм:** `current.a = energy/lines/L/i_now` (або `p·1000/(√3·380·cos)` за R-16 п.6, DEC-15, якщо сигналу нема); `pct = round(a/rating_a·100)`; `phases` — `i_a/i_b/i_c` сигнали шафи вузла; `rating_a` — вузол.
5. **Потужність:** `kw = p_now`, `p_inst_kw` = Σ споживачів піддерева, `cos_phi` — сигнал лінії або `cos_phi_nominal`.
6. **Енергія:** `kwh = node._td_kwh_by_code(code, 00:00 Київ, now)` (API-02); `cost_uah = Σ cost`; `orders` = distinct `production_id` у `td.energy.alloc` за добу для РЦ піддерева.
7. **Максимум доби:** `a_peak = max(chart.a)` з урахуванням живого `current.a`; `time` — слот; `warn_a = round(0,8·rating_a)`.
8. **Простій:** `idle.kw = Σ p_now` споживачів піддерева зі станом `idle|mnt`; `idle.names` — їх коди (до 5).
9. **Графік:** `a[s] = kw_avg(feeder meter)·1000/(√3·380·cos_phi)` для слотів до `now_slot` (інакше `null`); для ліній без лічильника — Σ споживачів. **Спрацювання захисту:** якщо сигнал стану автомата вузла (`energy/lines/L/state`, `energy/cells/Q*/state`) перейшов у `tripped` — створити подію `kind='trip'`, `level='warn'`, `title «Спрацював захист {QF}»` (у `_td_status_event`).
10. **Таблиця відгалужень:** вузли `kind in (tapoff, consumer)` піддерева (прямі діти лінії; для `tapoff` — його споживач); колонки: `tap` (код відгалуження), `code`/`name` (споживач), `inst_kw` (`p_inst_kw`), `now_kw` (`p_now`), `state`: `mnt` («На ТО») якщо є відкрита `maintenance.request` на `equipment_id` споживача (`stage_id.done=False`, `maintenance_type='corrective'`); інакше `idle` якщо `payload._consumer_status = idle`/`p_now < 0,05·p_inst`; інакше `run`; `job`: для `run` — `mrp.workorder` у `progress` на `workcenter_id` («{MO.name} · {workorder.name}»), для `idle` — «немає завдання», для `mnt` — «заявка ТО · {name}», немає mrp-даних — «—». `sum_kw = Σ now_kw`, `aux_kw = p_now − sum_kw` (≥ 0 показувати як є).
11. **Облік:** `meter` — лічильник вузла (шафа лінії) за `node.meter_id`; `last_ts` Київ `HH:MM:SS`; `last_kwh = meter.last_value`; `balance_pct` — `td.energy.balance` лінії за останню закриту годину (знак: `(measured − expected)/max(|measured|,|expected|)·100`).
12. **Захист:** `breaker` — код шафи (`QF-2`), `rating_a`, `trip_unit`, `ir.ratio`, `ir.a = ratio·rating_a`, `trips_year = trip_count_year`, `thermography` — найближча планова заявка (`maintenance_type='preventive'`, `schedule_date ≥ now`) на `equipment_id` шафи/лінії.
13. **Події:** останні 6 `td.energy.event` вузла і піддерева (`node_id child_of`) за 7 діб + події створення/закриття `maintenance.request` по обладнанню піддерева (рядок «{equipment} переведено в ТО», «заявку закрито»); сортування за `ts` спадно; формат `time`: сьогодні — `HH:MM`, вчора — «учора HH:MM», раніше — `DD.MM HH:MM`.
14. **Обслуговування:** відкриті заявки по обладнанню піддерева (нові — «Нова»), `У роботі`; плюс найближчі планові («План»); максимум 6.
15. **Планове відключення:** найближчий `td.energy.outage.plan` вузла зі `state in (pending, approved)` і `end ≥ now`.

### R-31 Планове відключення (FR-39)

1. **Зачеплені:** `affected` = усі вузли `kind in (tapoff, consumer)` піддерева `node_id` (`child_of`), без дублів; `tap_codes` — коди `tapoff` (якщо відгалуження немає — коди споживачів); для `node_id` без піддерева (споживач) — сам вузол.
2. **Замовлення:** `mrp.workorder` із `workcenter_id ∈ {affected.workcenter_id}` і `state ∉ (done, cancel)` та перетином інтервалів `[date_start, date_finished) ∩ [start, end) ≠ ∅` (`date_start`/`date_finished` — поля Odoo 19; порожні — не враховуються); `production_ids = distinct production_id`.
3. `action_submit`: перевірки M-25, заповнення M2M, activity мрп-менеджерам, `state='pending'`.
4. `approve`/`reject`: M-25; сповіщення підписникам — `message_post` із `subtype mail.mt_comment`; підписуються автор і всі `group_td_energy_manager` (як `EN/models/maintenance_request.py:12`); при `action_submit` додатково підписуються й отримують `message_post` користувачі `stock.group_stock_manager` («виробництво й склад отримали сповіщення», макет Feeder; Q-21).
5. Автоматичного перенесення МО **немає** (A-32): текст діалогу «Їх буде запропоновано перенести» — повідомлення виробництву; перенесення робить планувальник вручну.
6. Блок у картці вузла (R-30 п.15) і рядок «ТО й відключення» на Пульті: «{вузол} · планове відключення — {DD.MM HH:MM–HH:MM} · {N} замовлення перенесено|на узгодженні» + статус.
7. `_cron_close` (M-25).

### R-32 Рекомендації — слот і контракт (FR-32)

1. `get_pult().advice` — результат `td.energy.advice.get_open()`: `{"id", "code", "title", "text", "level", "node_code", "actions": [{"code","label","kind","class","enabled"}]}`; `enabled = (kind != 'control') or meta.control_available`; дії `enabled=false` клієнт не малює.
2. «Пізніше» → `action_snooze()` → блок зникає до `snooze_until`, потім повертається (стан `snoozed→open` за часом при `get_open`). `expires_at < now` → `expired` (крон).
3. Реєстр правил — розд. 2 M-26. Контракт для W2: правило повертає `actions` із `kind='control'`; виконання — `td_energy_control` через `td.energy.action.prepare/confirm` (W2); результат виконання повертається в `advice` викликом `action_done(note)`.
4. Банер при `advice=null` не показується.

### R-33 Шина `td_energy` (FR-33, A-28)

1. Канал `td_energy` (рядковий), тип `td_energy/update`, повідомлення `{"kinds": ["kpi"|"alarm"|"profile"|"state"|"advice"], "ts": iso_utc}` — **без значень**.
2. `tools.bus.tick(env, kind)`: акумулює види в `cr.precommit.data`; у `postcommit` — один `env["bus.bus"]._sendone("td_energy", "td_energy/update", {...})`; **throttle** — не частіше ніж раз на `td.energy.bus_throttle_s` (5 с) на воркер (module-level `dict` `last_sent[dbname]`), із накопиченням пропущених видів (відправляються в наступному тіку); без `bus` — нічого.
3. Хто викликає: `cron_td_energy_live` (`kpi`) після запису тоталів; `cron_td_energy_intervals` (`profile`); `td.energy.event.create`/`action_*` (`alarm`); `td.energy.outage.plan` переходи і `td.energy.advice` (`state`, `advice`).
4. Клієнт: за типом оновлює `parts` (`kpi`→`kpis,sld,alarms`; `alarm`→`alarms`; `profile`→`profile,side`; `state`→`side,sld`; `advice`→`advice`), дебаунс 2 с, резерв — таймер `refresh_s`.

### R-34 Повірка лічильників (FR-38)

`cron_td_energy_verification` щодоби: для лічильників із `next_verification − today ≤ verify_warn_days` і без відкритої події `code='VERIFY-<meter.code>'` — `_td_log('warn', 'meter', 'VERIFY-<code>', "Повірка лічильника {code}: до {DD.MM.YYYY}. Заплануйте повірку.", node=meter.node_id, dedup_min=1440)`; прострочена (`next_verification < today`) — `level='bad'`, текст «… прострочена з {дата}»; після оновлення `last_verification` подія авто-вирішується. Також `kind='trip'` старіші за 24 год → `resolved` (R-25).

### R-35 cos φ секцій, PFC (FR-44, E-10)

Доповнює R-06 п.2 (`EN/tools/live.py`):
1. Після обчислення `cos_after_s` і `P_s`, `Q_s − q_pfc_s` — записати обчислювані сигнали `energy/sections/S{s}/cos_phi` (= `cos_after_s`), `…/p_kw`, `…/q_kvar` (CT-10, `src='module'`, контекст `f3d_energy_internal`, `ts=floor_minute(now)`).
2. `q_pfc_s`: якщо свіжий сигнал `energy/cells/PFC-s/q_kvar` — `q_pfc_s = clamp(його, 0, rating_kvar)` (замість `Q_s − q_kvar_s` із вводу); інакше теоретична за R-06 п.2. `pfc_q_now` вузла PFC-s = `q_pfc_s`, **округлений до кроку**: `round(q_pfc_s / pfc_step_kvar)·pfc_step_kvar`, `≤ rating_kvar` (замість кроку 50; D-09).
3. Подія `kind='pfc'`: (а) `fault_step` перейшов 0→k>0 → `warn`, `title «PFC-{s}: ступінь {k} не вмикається»`, `dedup_min=60`; (б) `cos φ секції < cos_phi_warn` довше `min_duration_s` (300) → `warn` «cos φ секції {s} — {cos}» (`< cos_phi_alarm` → `bad`); авто-вирішення — R-25.
4. Параметри E-10 — `cos_phi_target` (ціль PFC, лише для емулятора й підказки в UI), `cos_phi_warn`, `cos_phi_alarm`: застосовуються до порогів сигналів (розд. 5.1).

### R-36 Генератор історії (backfill) для демо-стенда (FR-44, E-11, A-35)

**Призначення:** заповнити демо-БД 15-хв інтервалами за `days` діб (за замовчуванням 90) так, щоб Пульт, прогноз (R-28), баланс (R-07) і типовий день (R-15 п.5) працювали на стенді. **Запуск:** `echo 'env["td.energy.interval"]._td_backfill(days=90)' | odoo-bin shell -d <db> --no-http` (обгортку-скрипт робить менеджер). **Передумова:** емулятор і збирач працюють ≥ 5 хв (щоб існували перші `td.reading` лічильників), інакше метод попереджає і працює з `until = floor15(now)` (можливі `missing` на стику — ТК-14).

1. **Параметри:** `days` (1…400), `until` (Datetime UTC; за замовчуванням = `ceil15(min(ts першого td.reading по e_import-сигналах лічильників))`, а без `td.reading` — `floor15(now)`), `seed` (детермінізм), `purge` (видалити `is_backfill=True` у діапазоні й вийти без генерації), `with_balance`, `with_events`, `with_advice`, `meters` (коди; за замовчуванням усі активні 67). `since = until − days·1 доба`, вирівняно до `floor15`.
2. **Ключ невипадковості:** `rnd(*key) = hash(seed, *key) → [0,1)` (SHA-1, перші 8 байт); жодного глобального `random`.
3. **Цільове навантаження заводу** `P(t)`, кВт (локальний час `h`, день тижня `wd`, `d` — номер доби від `since`): будній (пн–пт): `h<6,5`: 210; `<7,5`: `210+(h−6,5)·440`; `<12`: 650; `<12,75`: 430; `<16`: 667; `<16,5`: 520; `<22,5`: 560; `<23,5`: `560−(h−22,5)·350`; інакше 210. Субота: 210 + 220 при `7 ≤ h < 14`, інакше 210. Неділя: 210. Денний коефіцієнт `kd = 1 + 0,05·sin(1,7·d)` застосовується до `(P−210)`; слотовий шум `±2 %` (`rnd(slot)`). Свят немає (A-35).
4. **Споживачі** (49 лічильників ролі `consumer`): сирове `raw_c(t)`: `direct` — `p_inst·load_factor` (за замовчуванням 0,75), якщо «машина ввімкнена» (`rnd(c, hour) < 0,8` у зміну буднів 07:00–23:00; у суботу 07:00–14:00 — `< 0,5`; інакше вимкнена), а вимкнена — `p_inst·idle_factor` (за замовчуванням 0,05); `shared`: `COMPRESSOR`, `DUST-1`, `GANTRY-1` — `p_inst·(0,05 + 0,75·activity)`, `activity = (P(t)−210)/(667−210)`; `RV-ALL`, `AHU-1` — у зміну `0,45·p_inst`, поза зміною `rv_offshift_ratio·0,45·p_inst` (`rv_offshift_ratio = 0,9`: у даних лишається «нічна/вихідна» витрата для правила W3); `LP-*` — `0,7·p_inst` у зміну, `0,3·p_inst` поза; `overhead` — `0,7·p_inst` день, `0,5·p_inst` ніч. Нормалізація: `f(t) = P(t) / Σ_c raw_c(t)`; `kw_c = raw_c·f(t)`; `kwh_c = kw_c·0,25`. Σ споживачів = `P(t)` (з точністю до шуму).
5. **Фідери** (6): `kwh_feeder = Σ_{c ∈ піддерево} kwh_c · (1 + ε)`, `ε = 0,008 + 0,004·(2·rnd(f, slot) − 1)`; аномалія (`with_events`): кожен 11-й будній день (`d % 11 == 5`) у слотах 10:00–10:45 фідер `QF-1` отримує `ε = 0,035` (породжує `deviation` у R-07).
6. **Генерація:** `pv_total = pv_kwp·0,8·sun(t)·cloud(d)`; `sun = sin(π(h−sr)/(ss−sr))^1,3` при `sr<h<ss`, інакше 0; `L(doy) = 12 + 4,5·cos(2π(doy−172)/365)`; `sr = 13,2 − L/2`, `ss = 13,2 + L/2`; `cloud(d) = 0,25 + 0,75·rnd(day)^0,7`; кожен із 8 `SUN-k`: `kwh = pv_total/8·(1+0,02·(2·rnd(k,slot)−1))·0,25`. `CHP` (`TEDOM-1`): у кожен будній день з ймовірністю `0,1` (`rnd(day,'chp')`) працює 16:00–19:00 на 400 кВт, інакше 0. `GENSET` — без лічильника (немає).
7. **BESS** (`LUNA-1`, ємність 200 кВт·год, ±100 кВт, SoC початковий 60 %, межі 10–95 %), послідовно по слотах: `surplus2 = Σ feeders(sec 2) − pv_total − chp` (кВт); якщо `surplus2 < −5` і SoC < 95 → заряд `min(−surplus2, 100)`; інакше якщо `grid_net > 0,95·contract_kw` і SoC > 15 → розряд `min(grid_net − 0,95·contract, 100)`; інакше якщо буднів день 07:30–11:00 і SoC > 40 → розряд 60; інакше 0. `SoC += (charge·0,95 − discharge/0,95)·0,25/200·100`. Запис: `kwh = заряд·0,25`, `kwh_export = розряд·0,25` (R-07 таблиця).
8. **Вводи:** `Q1.kwh = Σ feeders(секція 1)` (QF-3, QF-2, QF-C1), `kwh_export = 0`; `net2 = Σ feeders(секція 2) (QF-1, QF-4, QF-C2) − Σ SUN − TEDOM + BESS.kwh − BESS.kwh_export`; `Q2.kwh = max(0, net2)`, `Q2.kwh_export = max(0, −net2)`; шум вводів ±0,2 %.
9. **Поля рядка:** `ts_start`, `ts_end = +15 хв`, `day`/`hour_local` (Київ, `tools/dates`), `e_start = e0_m + Σ попередніх kwh`, `e_end = e_start + kwh` (`e0_m = 50 000 + 137·idx` кВт·год), `kwh`, `kwh_export`, `kw_avg = round(kwh·4, 2)`, `zone_id`/`price` = `tariff._td_price_at(ts_start)`, `cost = round(kwh·price, 2)` для ролей `incomer`, `feeder`, `consumer` (інші — 0), `quality='measured'`, `built_at=now`, `is_backfill=True`.
10. **Запис:** по добах, пакетами ≤ 5 000 рядків, `INSERT … ON CONFLICT (meter_id, ts_start) DO NOTHING` (існуючі «реальні» слоти не чіпаються); `meter.last_interval_start = max(існуюче, останній записаний слот)` **лише якщо** в діапазоні немає рядків із `is_backfill=False` пізніше. Після запису — `interval._td_after_build(now)` (R-11, R-15). `with_balance` — для останніх 7 діб викликати `balance._td_balance_hour(hour)` за кожну закриту годину. `with_events` — події (`is_backfill=True`, `state='na'` для `info`, `resolved` для `warn`): щодня `kind='peak'` («Пік доби {kw} кВт», «{pct} % договірної потужності {contract} кВт.»), буднями 07:02 `kind='ats'` («Тест АВР і ДГУ пройдено.», «Перемикання на ДГУ 8,4 с, повернення на мережу без зауважень.»), для кожної аномалії п.5 `kind='balance'` `warn`. `with_advice` — `td.energy.advice._td_demo_seed()`. Повертає `{"meters": n, "slots": n, "rows": n, "skipped": n, "events": n, "balance": n, "since": iso, "until": iso, "seconds": float}`.
11. **Перевірені властивості (AC-148…AC-152):** тотожність R-07 для кожної години `|diff| ≤ balance_tol` (`Q1`, `Q2`, лінії); будній пік 600–700 кВт, нічна база 210 ± 20 кВт, неділя ≈ база; детермінізм за `seed`; ідемпотентність; `purge` видаляє лише `is_backfill`; ≤ 120 с на 90 діб (ТП-07).

### R-37 Мобільні дані (FR-45)

`get_mobile`: `state` — з `kpis.grid/generation/cos_phi` (R-27 п.5) і ДГУ-тексту (`_td_genset_summary`; без моста — «ДГУ · АВР: мережа»); `alarms.active` — `alarms.items` зі `state in (active, acked)` без `info`; кожен елемент має `taken_by_me` (bool) і кнопки: `take` (`action_take`), `resolve` (лише виконавцю), `where3d`; `info_today` — події `info` за сьогодні; `scheme` — вузли `sld_show` видів `input|transformer|line|generator|storage|ats|cell(pfc)` у порядку `sld_y, sld_x`, рядок `{name, value (перший рядок lines), state}`; лічильник вкладки «Тривоги · N» = `active_count` (активні без виконавця: `state='active'`). «Призначити на себе» для заявки ТО PFC — `maintenance.request.write({'user_id': uid})` кнопкою «Призначити на себе» у картці тривоги (якщо `request_id` без `user_id`).

### R-38 «Генерація й резерв» (FR-42)

`get_generation()` повертає `cards` із `_td_generation_cards()`. Базові картки (`td_energy`, без `td_genset`):

| Картка | Стан (R-26) | KPI | Факти |
|---|---|---|---|
| СЕС (`PV-INV`) | `gen`/`off` | потужність (кВт), % від `pv_kwp`, виробіток сьогодні (кВт·год), інверторів на зв'язку «N з 8» | «Пік сьогодні {kW} о HH:MM» |
| КГУ (`CHP`) | `gen`/`off`/`alarm` | стан, потужність, мотогодини, витрата газу (`infra/chp/gas_m3h`) | «Пуск лише за командою оператора КГУ» (статичний рядок з макета лише як текст вузла `note`) |
| BESS (`BESS`) | `gen`/`ok`/`alarm` | SoC %, потужність (знак: + заряд), режим (`bess_mode`: заряд/розряд/очікування) | «Резерв на відключення мережі {bess_reserve_pct} %» |
| АВР (`ATS-1`) | `off`/`gen`/`alarm` | положення (`мережа`/`ДГУ`), режим АВР (`infra/ats/mode`), джерело 1/2 (`src1_state`, `src2_state`) | критичне навантаження (`critical_kw`, R-06 п.7) |

Картка: `{"code","title","kind","state","kpis":[{"label","value","unit"}],"facts":[str],"node_code","can_3d":true}`. Міст додає картку «ДГУ» (Частина II R-15).

## 10. Стани й переходи

| Об'єкт | Стани | Переходи (хто) |
|---|---|---|
| `td.energy.event.state` | `na`; `active → acked → resolved` | `action_ack`, `action_take`, `action_release` (лишає `acked`), `action_resolve`, `_td_auto_resolve` (R-25) |
| `td.energy.outage.plan.state` | `draft → pending → approved → done`; `pending → rejected`; `draft/pending/approved → cancelled` | `action_submit`, `action_approve`, `action_reject`, `action_cancel`, `_cron_close` |
| `td.energy.advice.state` | `open ⇄ snoozed → done/dismissed`; `open/snoozed → expired` | `action_snooze`, `action_dismiss`, `action_done`, `_cron_advice` |
| `sld_state` | `ok/warn/alarm/off/gen` | обчислюється (R-26), не зберігається |

## 11. Обробка помилок

- Сигнали несвіжі/відсутні (stale, unknown, bad) — значення `null`, `data_state` `partial|stale`, UI «—»; методи **не кидають** винятків через відсутність даних.
- `get_pult` частково: помилка в одній частині (`parts`) не ламає інші — частина повертає `{"error": "…"}`, помилка логується `_logger.exception` (UI показує «Не вдалося завантажити: {частина}» і далі працює).
- Дубль подій — `dedup_min` (існуюча логіка); гонка `action_take` двох користувачів — `SELECT … FOR UPDATE` на записі подій у методі; програв другий (`UserError("Уже в роботі: …")`).
- Часові пояси: збереження UTC naive; доба/зміна/місяць/«години» — `Europe/Kyiv` (`tools/dates.py`); перехід на літній/зимовий час: добові масиви завжди 96 слотів за **локальними** індексами (`dates.local_slot_index`), слот без даних (в добу 23 год) — `null`, у добу 25 год — останній слот об'єднується (A-30).
- Шина недоступна (`bus` не встановлено/збій) — `tick` ковтає виняток (`_logger.warning`), UI працює на резервному опитуванні.
- Міграція: SQL-кроки в одній транзакції; повторний запуск не змінює результат.

## 12. Acceptance Criteria

Позначення колонки «Тип»: UT / UT-JS / TC / MAN. Усі тести `post_install`, теги `-at_install`, `td`. Фікстури — розд. 13.0.

### 12.1 `td_energy` — AC-93…AC-152

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-93 | FR-36 | Given подія `warn`, `kind='meter'`, `text="Лічильник PM-QF-C2 не на зв'язку. 33 хв без даних."`; When `_td_log(...)`; Then `title="Лічильник PM-QF-C2 не на зв'язку"`, `detail="33 хв без даних."`, `state='active'`; текст без роздільника ≤ 100 → `title=text`, `detail=''`; `title` > 128 → 125 + «…» | UT |
| AC-94 | FR-36 | Given `_td_log('info', 'peak', …)`; Then `state='na'`; Given явні `title/detail` — не перезаписуються; Given `level='info'` і `state='active'` — `ValidationError` | UT |
| AC-95 | FR-36 | Given подія `active` і користувач `group_td_energy_manager`; When `action_ack()`; Then `state='acked'`, `acked_by=uid`, `acked_at≈now`; повторний `ack` — без змін і без помилки; користувач лише `group_td_energy_user` → `AccessError("Підтверджувати тривоги може лише енергетик.")` | UT |
| AC-96 | FR-36 | Given подія `active`; When `action_take()` користувачем A; Then `assigned_user_id=A`, `state='acked'`, `taken_at`; When `action_take()` користувачем B → `UserError("Уже в роботі: A.")`; подія `resolved` → `UserError("Подію вже закрито.")` | UT |
| AC-97 | FR-36 | Given подія взята A; When `action_resolve()` користувачем A → `state='resolved'`, `resolved_at`; користувачем B без `chief` → `AccessError`; користувачем з `group_td_energy_chief` → успіх; `info` → `UserError`; `action_release()` виконавцем скидає `assigned_user_id`, стан лишається `acked` | UT |
| AC-98 | FR-36 | Given відкрита подія `kind='meter'` для вузла C2; When лічильник `PM-QF-C2` переходить у `data_state='ok'`; Then подія `resolved`, `resolved_at` заповнено; інші події не змінено | UT |
| AC-99 | FR-36 | Given відкрита подія `kind='threshold'` по сигналу X; When статус X → `ok`; Then `resolved`. Given подія `kind='ats'` `warn` — не вирішується автоматично | UT |
| AC-100 | FR-36 | Given база з 3 подіями до міграції (`title IS NULL`, `warn`, `info`, `bad`); When `post-migration` 19.0.1.1.0 двічі; Then `title/detail` за R-24, `warn/bad → resolved` (`resolved_at=ts`), `info → na`; друга міграція нічого не змінює | UT |
| AC-101 | FR-33 | Given 10 викликів `tools.bus.tick('alarm')` за 3 с; When commit; Then до `bus.bus` пішло **1** повідомлення `td_energy/update` з `kinds=['alarm']`; після 5 с наступний `tick('kpi')` → друге повідомлення; payload без ключів `cost`, `price`, `kwh`, значень сигналів | UT |
| AC-102 | FR-33 | Given `td.energy.event.create(warn)`, `action_ack`, `action_take`, зміна стану плану відключення; Then кожна дія додає вид у тік (`alarm`/`state`) | UT |
| AC-103 | FR-33 | Given `data/sld_layout.csv`; When `_load_sld_layout(env)` на БД із 123 вузлами; Then рівно 21 вузол `sld_show=True`; `GRID-10KV`: `(580, 24, 160, 44)`, `T1`: `(230, 192, 200, 64)`, `SEC-1`: `shape='bar'`, `(40, 298, 590, 6)`; користувач змінив `sld_x` вузла `BW-2` → повторне завантаження його не перезаписує; відсутній код → warning, без винятку | UT |
| AC-104 | FR-33 | Given фікстура сигналів; When `tools.sld.states(...)`; Then: `QS=closed → ok`, `open → off`; `PV pv_now=309 → gen`, `0 → off`; `CHP state=stop → off`, `running → gen`; `ATS position=2 → off`, `3 → gen`; лічильник C2 `stale` → `alarm`; `PFC-2` cos 0,88 → `warn`, cos 0,86 → `warn`, cos `< 0,90` → `alarm`; `fault_step=3` → `warn`; `T1` завантаження 85 % → `warn`, 101 % → `alarm`, 50 % → `ok` | UT |
| AC-105 | FR-33 | Given `BESS` `bess_kw=+50` і `−50` → `gen`; `0` → `ok`; `state=fault` → `alarm` | UT |
| AC-106 | FR-33 | Given пара вузлів і шина; When `sld.js: edgePath(parent, child)`; Then для `bar` над вузлом — вертикаль від `bar.y+bar.h` до `child.y` на `x=child.x+child.w/2` (затиснуто в межі шини); для `box→box` — ламана з `y_mid=(P.y+P.h+N.y)/2` (приклад RM6-1 → T1: `M660 144 V168 H330 V192`) | UT-JS |
| AC-107 | FR-31 | Given користувач без `group_td_energy_cost`; When `get_pult()`, `get_node_card('BW-2')`, `get_mobile()`; Then ключі `cost_uah`, `price_uah`, `tariff_uah`, `mo.rows[].cost_uah`, `capabilities.cost` **відсутні** у відповіді; з групою вартості — є | UT |
| AC-108 | FR-31 | Given `Q1`: 384 кВт, `Q2`: −26 кВт (15-хв рядки інтервалів) і `infra/totals/grid_kw=358`, `contract_kw=800`; When `get_pult('now')`; Then `kpis.grid = {kw: 358, pct: 45, reserve_kw: 442, export_kw: 0}`; `kpis.load.pv_share_pct = round(309/667·100) = 46` | UT |
| AC-109 | FR-31 | Given слоти з `net` +300·0,25, −40·0,25, +100·0,25 кВт·год; When `get_pult('now')`; Then `energy.kwh = 100` (позитивні частини 75+25), `export_kwh` рахує −10; `cost_uah = 100·8,4 = 840`; peak = 300 кВт | UT |
| AC-110 | FR-31 | Given зміна з 07:00 (`shift_hours`); When `get_pult('shift')` о 14:20; Then період із 07:00 Київ, підпис «З мережі за зміну (з 07:00)»; `peak.label = «Пік зміни»` | UT |
| AC-111 | FR-31 | Given дані за сьогодні й типовий день; When `get_pult('day')`; Then `energy.label = «Прогноз на добу»`, `kwh = факт + Σ max(0, grid_fc)·0,25`; `peak` ≥ факту | UT |
| AC-112 | FR-31 | Given дані за жовтень, пік 742 кВт 09.10 о 08:15; When `get_pult('month')`; Then `peak = {kw: 742, note: "09.10 о 08:15 · 93 % договірної"}`, `energy.label = «З мережі за жовтень»` | UT |
| AC-113 | FR-31 | Given сигнали `energy/totals/p_now` і обидва вводи несвіжі; When `get_pult()`; Then `meta.data_state='stale'`, `kpis.*` числа `null`, виняток не кидається; один несвіжий фідер → `partial` | UT |
| AC-114 | FR-35 | Given інтервали сьогодні до слота 57 і 8 попередніх таких самих днів тижня; When `get_pult(parts=['profile'])`; Then масиви довжини 96; `cons[s]=null` для `s>57`; `cons_fc[s]` для `s≥57` = середнє типового; перша точка прогнозу = поточна | UT |
| AC-115 | FR-35 | Given факт PV 60 % від типового до `now`; Then `pv_fc = typical.pv·0,6` (clamp 0,3…1,5); `grid_fc = cons_fc − pv_fc`; днів `< 3` → усі `*_fc = null`, `forecast_days_used < 3`, `foot.forecast_kwh = null` | UT |
| AC-116 | FR-32 | Given відкрита `td.energy.advice` (EXPORT-T2, 3 дії: `link`, `control`, `control`); When `get_pult()`; Then `advice.actions` містить усі 3, `enabled=true` лише для `link` (бо `control_available=false`); `action_snooze()` → `advice=null` у відповіді, через 30 хв (час просунуто) — повертається; `action_dismiss()` → `null` | UT |
| AC-117 | FR-32 | Given тестовий клас-спадкоємець додає `_td_advice_rule_test(self, now)` із елементом `{code, dedup_key, title, text, level, node_code, actions, expires_in_min}`; When `_cron_advice()` двічі; Then створено 1 запис (дедуплікація за `dedup_key`); коли правило перестало повертати елемент — запис `expired` | UT |
| AC-118 | FR-36 | Given 2 `active` (`bad`, `warn`), 1 `acked`, 4 `info` за сьогодні, `alarm_list_limit=8`; When `get_alarms()`; Then порядок: `active bad`, `active warn`, `acked`, потім `info`/`resolved` за `ts` спадно; `active_count` = кількість `active` без `info`; `scope='mine'` — лише з `assigned_user_id=uid` | UT |
| AC-119 | FR-36 | Given подія `kind='meter'`, вузол C2, джерело лічильника `MB-U14-PM-QF-C2` (`host=iot-sim`, `port=502`, `unit=14`), `last_ok=13:47:12`; Then `diag` містить код джерела, `iot-sim:502`, `unit 14`, «13:47:12», стан колектора, «комірку QF-C2» | UT |
| AC-120 | FR-30 | Given стенд (емулятор+збирач+Odoo, 90 діб історії); When адміністратор відкриває «Енергетика → Пульт»; Then видно 6 KPI, схему з 21 вузлом, профіль доби з прогнозом, тривоги; «Підтвердити» змінює рядок на «Підтверджено: …» ≤ 10 с без перезавантаження (шина) | TC |
| AC-121 | FR-30…FR-34 | Given hoot-тести `pult.test.js`, `sld.test.js`; Then: перемикач періоду змінює підписи KPI; вибір вузла показує факти й «Відкрити картку вузла» лише для `card=true`; повторний клік знімає вибір; кнопка «Підтвердити» прихована без `capabilities.ack`; кнопки `kind='control'` не малюються; при `data_state='stale'` — «—» і чип «Немає даних» | UT-JS |
| AC-122 | FR-38 | Given `BW-2` і фікстура сигналів (i_now 192 А, p 124 кВт, cos 0,91, фази 188/195/193); When `get_node_card('BW-2')`; Then `kpis.current = {a: 192, pct: 30, phases: [188,195,193], rating_a: 630}`, `kpis.power.kw=124`, `p_inst_kw` = Σ споживачів піддерева, `chart.a` довжини 96 | UT |
| AC-123 | FR-38 | Given 10 відгалужень `BW-2`, `CNC-4` має відкриту коригувальну заявку, `VSAW-1` — `p_now=0,6`; Then `taps.rows` = 10, `CNC-4.state='mnt'`, `VSAW-1.state='idle'`, інші `run`; `job` для `run` — `{MO} · {workorder}`; `sum_kw`, `aux_kw = p_now − sum` | UT |
| AC-124 | FR-38 | Given `idle` споживачі `VSAW-1` (0,6) і `CNC-4` (0); Then `kpis.idle = {kw: 0,6, names: ["VSAW-1","CNC-4"]}` | UT |
| AC-125 | FR-38 | Given лічильник `PM-QF-2` із `next_verification=2026-10-30`, `ct_ratio='630/5'` і `td.energy.balance` −1,2 %; Then `meter = {…, next_verification: "2026-10-30", balance_pct: -1.2}`; `verification_months ≤ 0` → `ValidationError` | UT |
| AC-126 | FR-38 | Given вузол `QF-2` (`protection_ir_ratio=0,9`, `rating_a=630`) і 2 події `kind='trip'` за рік; Then `protection.ir = {ratio: 0.9, a: 567}`, `trips_year = 2`; перехід сигналу стану автомата в `tripped` створює подію `trip` `warn` | UT |
| AC-127 | FR-38 | Given події вузла, `maintenance.request` по CNC-4 (створено/закрито); Then `events` ≤ 6, відсортовано за `ts` спадно, формат часу: сьогодні `HH:MM`, вчора «учора HH:MM», раніше `DD.MM HH:MM` | UT |
| AC-128 | FR-38 | Given `T1`; Then картка має `kpis.current/power/energy/peak`, `chart`, `meter`, `events`, `maintenance`, без `taps`/`protection`/`idle`; `consumer` — лише шапка, `power`, `energy`, `events`, `maintenance` | UT |
| AC-129 | FR-38 | Given невідомий код; Then `UserError("Невідомий вузол: X.")`; користувач без групи → `AccessError` | UT |
| AC-130 | FR-39 | Given `BW-2` (10 відгалужень), 3 `mrp.workorder` на РЦ піддерева у вікні; When менеджер створює план і `action_submit()`; Then `state='pending'`, `affected_count=10`, `production_count=3`, `mail.activity` створено кожному користувачу `mrp.group_mrp_manager`; `start < now` → `UserError("Початок має бути в майбутньому.")` | UT |
| AC-131 | FR-39 | Given план `pending`; When користувач `mrp.group_mrp_manager` — `action_approve()`; Then `state='approved'`, `approver_id`, `approved_at`, activity закриті, підписникам — повідомлення; користувач без групи → `AccessError("Узгоджує керівник виробництва.")`; `action_reject('')` → `UserError("Вкажіть причину відхилення.")`; з причиною → `rejected` | UT |
| AC-132 | FR-39 | Given `end ≤ start` → `ValidationError`; два плани одного вузла в `pending/approved` з перетином → `ValidationError("Для … вже є відключення в цей час.")`; `reason='other'` без `reason_text` → `ValidationError` | UT |
| AC-133 | FR-39 | Given затверджений план; When `get_node_card('BW-2')`; Then `outage = {when: "25.10 · 07:00–09:00", orders: 3, state: "approved", state_label: "узгоджено", …}`; на Пульті блок «ТО й відключення» містить рядок «ШР-2 · планове відключення» | UT |
| AC-134 | FR-39 | Given план `approved` із `end < now` → `_cron_close` ставить `done`; `pending/draft` із `end < now` → `cancelled` | UT |
| AC-135 | FR-39 | Given `preview('BW-2', start, end)`; Then `tap_count=10`, `order_count` = кількість МО у вікні, запис не створюється | UT |
| AC-136 | FR-40 | Given діалог заявки з картки `BW-2`; When `td.energy.ticket.wizard.action_create()`; Then створено `maintenance.request` (`equipment_id`, `maintenance_type`, `maintenance_team_id`, `priority`, опис); без `equipment_id` у `description` додано «Вузол мережі: BW-2»; повернуто `act_window` форми заявки | UT |
| AC-137 | FR-38 | Given `cron_td_energy_verification`, лічильник з `next_verification = today + 20 днів`, `verify_warn_days=30`; Then подія `VERIFY-<код>` `warn`, повторний запуск дубль не створює (`dedup`); прострочена → `bad`; `last_verification` оновлено → подія `resolved` | UT |
| AC-138 | FR-44 | Given установка/міграція; Then існують сигнали `energy/cells/QS/state`, `energy/cells/PFC-{1,2}/{q_kvar,steps_on,steps_total,fault_step}`, `energy/sections/S{1,2}/{cos_phi,p_kw,q_kvar}` (разом +15), джерело `MB-U73-SWB-CTRL`; `_ensure_w1_signals` повторно нічого не змінює | UT |
| AC-139 | FR-44 | Given `td_energy_cos_phi_warn=0.92`, `alarm=0.90`; When `set_values`; Then `warn_low`/`alarm_low` сигналів `energy/totals/cos_phi` і `energy/sections/S1|S2/cos_phi` = 0,92/0,90; `alarm ≥ warn` → `ValidationError("Пороги cos φ: тривога < попередження ≤ ціль ≤ 1.")`; міграція застосовує пороги на існуючій БД (було `warn_low=0,95`) | UT |
| AC-140 | FR-44 | Given свіжий `energy/cells/PFC-2/q_kvar=120`; Then `pfc_q_now = round(120/35)·35 = 105`; без свіжого сигналу — теоретична за R-06 п.2, округлена до кроку 35 і ≤ `rating_kvar`; `pfc_step_kvar·pfc_steps_total ≠ rating_kvar` → `ValidationError` | UT |
| AC-141 | FR-44 | Given `fault_step` PFC-2 переходить 0→3; Then подія `kind='pfc'` `warn` «PFC-2: ступінь 3 не вмикається» (одна за `dedup_min=60`) і, за CT-05, `maintenance.request` «PFC-2: ступінь 3 не вмикається»; при `fault_step=0` і cos ≥ 0,92 подія `resolved` | UT |
| AC-142 | FR-43 | Given група `group_td_energy_chief`; Then `implied_ids ⊇ {group_td_energy_manager}`; `td_factory3d.group_td_admin` має `chief`; користувач `group_td_energy_user` не має прав запису `td.energy.outage.plan`, `td.energy.advice`; `mrp.group_mrp_manager` читає `outage.plan` без запису | UT |
| AC-143 | FR-42 | Given `td_energy` без `td_genset`; When `get_generation()`; Then `cards` = 4 (СЕС, КГУ, BESS, АВР) зі станами за R-26; жодної картки ДГУ | UT |
| AC-144 | FR-42 | Given меню після W1; Then `td_energy.menu_td_energy_generation` («Генерація й резерв», parent `menu_td_energy`, seq 35) і `menu_td_energy_generation_overview` існують і видимі `group_td_energy_user`; нових верхніх меню «Генератор» немає | UT |
| AC-145 | FR-45 | Given `get_mobile(tab=None)`; Then ключі `state`, `alarms`, `scheme`; розмір JSON ≤ 20 КБ; без ключів вартості; `scheme` містить `GRID-10KV, T1, T2, BW-2, C2, PFC-2, PV-INV, BESS, ATS-1`; активні тривоги мають `taken_by_me` | UT |
| AC-146 | FR-45 | Given viewport 390 × 844; When відкрити «Чергування (телефон)»; Then 3 вкладки; «Беру в роботу» змінює картку на «У роботі · ви» і зменшує лічильник вкладки; «Де це в 3D» відкриває viewer на вузлі; кнопки ≥ 48 px | TC |
| AC-147 | FR-37 | Given вузол `BW-2` з `equipment_id`; When `node.action_td_show()` через панель; Then повертається client-дія viewer із кодом сцени; вузол без обладнання → `UserError` (поточна поведінка `action_f3d_show`, `EN/models/f3d_energy_node.py:254`); кнопка «Показати в 3D» на Пульті/картці прихована, коли `can_3d=false` | UT |
| AC-148 | FR-44 | Given порожня БД з вузлами/лічильниками; When `_td_backfill(days=2, seed=1)`; Then рядки `td.energy.interval` для 67 лічильників за 2 доби × 96 слотів — рівно `67·192 = 12 864`, всі `is_backfill=True`, `quality='measured'`, `cost` лише для ролей `incomer/feeder/consumer`; `meter.last_interval_start` = останній слот | UT |
| AC-149 | FR-44 | Given історія 7 діб; Then для кожної години: `|Q1 − Σ feeders(sec1)| ≤ max(balance_tol_kwh, balance_tol_pct%)`, те саме для `Q2` за формулою R-07, для кожної лінії; з `with_events` аномалія у 11-й будній день породжує `deviation` у `td.energy.balance` вузла `QF-1` | UT |
| AC-150 | FR-44 | Given дві підряд виклики з однаковими параметрами; Then другий вставляє 0 рядків (`skipped` = перший `rows`); `purge=True` видаляє лише `is_backfill` рядки діапазону (реальні лишаються); `seed` однаковий → ті самі `kwh` (SHA-256 набору рядків збігається) | UT |
| AC-151 | FR-44 | Given історія 14 діб; Then будній максимум Σ споживачів у 600…700 кВт, нічна база 210 ± 20, неділя ≈ база (≤ 230), PV нуль уночі, `SUN` Σ ≤ `pv_kwp` | UT |
| AC-152 | FR-44 | Given наявні реальні інтервали (лічильник із `is_backfill=False` після `until`); When backfill; Then `last_interval_start` не зменшується й не перескакує реальних слотів; `until` за замовчуванням = `ceil15(перший td.reading)`; слоти `≥ until` не створюються | UT |


### 12.2 AC-153…AC-158 — безпека, продуктивність, експлуатація, додаткові `td_energy` (продовження таблиці 12.1)

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-153 | FR-30 | Given користувач `base.group_user` без груп енергетики; When `get_pult`, `get_node_card`, `get_mobile`, `get_generation`; Then `AccessError`; пункт «Енергетика» в меню не видно | UT |
| AC-154 | FR-30 | Given `get_pult()` на демо-БД із 90 діб історії; Then ≤ 500 мс (медіана з 10 викликів), ≤ 40 SQL-запитів, без N+1 за вузлами; `get_node_card('BW-2')` ≤ 300 мс | UT (ТП-08) |
| AC-155 | FR-43 | Given `neutralize.sql`; Then 3 нові крони вимкнено, джерело `MB-U73-SWB-CTRL` `read_enabled=false`; `uninstall_hook` не видаляє `td.energy.event`, `.outage.plan`, `.advice` | UT |
| AC-156 | FR-43 | Given `res.config.settings` форма; Then група «cos φ» і «Пульт» редагуються `group_td_energy_manager`; зміна `td_energy_pult_refresh_s` береться з `meta.refresh_s` | UT |
| AC-157 | FR-34 | Given фікстура сигналів (BW-2: 192 А, 124 кВт, 2 відгалуження не працюють; PFC-2: `q_kvar=105`, `steps_on=3`, `steps_total=10`, cos секції 0,88; QS `open`; BESS 82 %, `bess_kw=0`); When `get_pult().sld.nodes`; Then факти: `BW-2` — «192 А з 630 А · 30 %», «124 кВт · 10 відгалужень, 2 не працюють»; `PFC-2` — «Увімкнено 105 квар (3 з 10 ступенів)», «cos φ секції 0,88»; `QS` — «Вимкнено: секції живляться окремо від T1 і T2»; `BESS` — «Заряд 82 %», «Очікування, 0 кВт», «Резерв на відключення мережі: 30 %»; кожен вузол має `title` = повна назва, `card=true` лише для `line/transformer/cell` | UT |
| AC-158 | FR-41 | Given споживачі з `p_now` (DUST-1 96, RV-ALL 88, COMPRESSOR 52, EDGE-1 41, SAW-3 31, NEST-1 26, решта менше), 3 МО з `alloc` за сьогодні, 2 відкриті заявки ТО, 1 затверджене відключення, лічильник із повіркою через 9 днів; When `get_pult()`; Then `top` = 6 записів за спаданням `kw`; `mo.rows` = МО за спаданням `kwh` з `cost_uah` (за групою), `pools_kwh` = Σ `kind='shared'`; `maint` містить заявки, відключення, повірку (статус «Заплановано», D-08) | UT |

**Разом `td_energy`: AC-93…AC-158 = 66 критеріїв; `td_genset_factory3d`: AC-74…AC-83 = 10; усього W1 — 76.**

### 12.3 `td_genset_factory3d` — AC-74…AC-83 (Частина II)

Подано в Частині II, розд. 12.

## 13. План тестування (для Opus)

### 13.0 Фікстури й вимоги до тестованості

- `tests/common.py` (існує) розширити `TestW1Common(TransactionCase)`: `_fresh(code, value, text=None)` (запис `td.signal.last_value/last_ts=now/status='ok'`), `_interval(meter_code, ts_start, kwh, kwh_export=0)`, `_user(groups)`; фікстура часу — `freezegun`-подібний `patch("odoo.fields.Datetime.now")`; вузли/лічильники — з `data/energy_nodes.csv` (post_init_hook).
- Часові функції викликаються через `tools.dates.now(env)` (мокується); бекфіл детермінований за `seed`.
- JS: hoot, `web.assets_unit_tests`; мок `orm.call` повертає JSON з прикладів розд. 7.

### 13.1 Юніт-тести (бекенд — A)

| Файл | Клас | Покриває |
|---|---|---|
| `test_w1_event.py` | `TestW1Event` | AC-93…AC-100, AC-118, AC-119 (тести `test_title_split`, `test_state_initial`, `test_ack`, `test_take_race`, `test_resolve_release`, `test_auto_resolve_meter`, `test_auto_resolve_threshold`, `test_migration_events`, `test_alarm_order`, `test_diag_text`) |
| `test_w1_bus.py` | `TestW1Bus` | AC-101, AC-102 (`test_throttle_one_message`, `test_payload_no_values`) |
| `test_w1_node_sld.py` | `TestW1NodeSld` | AC-103…AC-105, AC-126, AC-140 (`test_layout_load`, `test_states_table`, `test_bess_states`, `test_protection_trips`, `test_pfc_steps`) |
| `test_w1_dashboard.py` | `TestW1Dashboard` | AC-107…AC-113, AC-124, AC-145, AC-147, AC-153, AC-157, AC-158 |
| `test_w1_forecast.py` | `TestW1Forecast` | AC-114, AC-115 |
| `test_w1_card.py` | `TestW1Card` | AC-122…AC-129, AC-133 |
| `test_w1_outage_plan.py` | `TestW1OutagePlan` | AC-130…AC-135 |
| `test_w1_advice.py` | `TestW1Advice` | AC-116, AC-117 |
| `test_w1_signals.py` | `TestW1Signals` | AC-138…AC-141, AC-137 |
| `test_w1_backfill.py` | `TestW1Backfill` | AC-148…AC-152 |
| `test_w1_security.py` | `TestW1Security` | AC-142, AC-153, AC-155, AC-156, AC-143, AC-144 |
| `test_w1_ticket.py` | `TestW1Ticket` | AC-136 |

Тести B: `test_w1_ui.py::TestW1Ui` (HttpCase: client-дії відкриваються без JS-помилок, меню в браузері — AC-144); `test_w1_hoot.py::TestW1Hoot.test_hoot_suite` (запускає `/web/tests?headless…&id=<hash('@td_energy')>` за зразком `td_bms/tests/test_hoot.py`) — AC-106, AC-121.

### 13.2 Стендові сценарії ТК-13…ТК-18 (`tests/stand/test_w1_tk.py`)

Передумови: емулятор + збирач + Odoo (постійні сервіси тестового сервера, E-11); `td_energy`, `td_bms`, `td_genset`, `td_genset_factory3d` установлено; `_td_backfill(days=90)` виконано після ≥ 5 хв роботи стенда.

| ТК | Назва | Кроки | Очікується |
|---|---|---|---|
| ТК-13 | Пульт живий | відкрити «Пульт»; почекати 90 с | KPI мають значення; `data_state='ok'`; схема 21 вузол; значення КПІ змінюються без перезавантаження (шина) |
| ТК-14 | Стик історії й живих даних | після backfill — `get_pult(parts=['profile'])` | профіль без дірок: слотів `missing` на стику 0; прогноз є (≥ 3 дні); `forecast_kwh` > факт |
| ТК-15 | Підтвердження двома сесіями | дві сесії (A, B); емулятор: `POST /sim/v1/…` відключення лічильника C2 (сценарій `machine_fault`-аналог для лічильника) → подія `active`; A «Взяти в роботу»; B бачить «У роботі: A» ≤ 10 с | `UserError` у B при спробі взяти; після відновлення лічильника — подія `resolved` автоматично |
| ТК-16 | Планове відключення | менеджер створює відключення `BW-2` на завтра 07:00–09:00; мрп-менеджер узгоджує | картка вузла показує статус; Пульт — рядок; activity створено й закрито |
| ТК-17 | PFC | запустити сценарій `pfc_step_fault` (`section=2, step=3`) | `PFC-2` `warn`, подія й заявка «PFC-2: ступінь 3 не вмикається», cos φ секції 2 нижче 0,92 → чип «Секція 2: … нижче 0,92»; зупинка сценарію → подія `resolved` |
| ТК-18 | Мобільний | viewport 390×844: Стан → Тривоги → «Беру в роботу» → Схема | відповідає AC-146 |

### 13.3 Тести безпеки (ТБ-07…ТБ-10)

- ТБ-07: користувач `group_td_energy_user` — `action_ack`/`action_take` → `AccessError`; `td.energy.outage.plan.create` → `AccessError` (AC-142, AC-95).
- ТБ-08: відповіді API-05/07/12 без `group_td_energy_cost` не мають ключів вартості (AC-107).
- ТБ-09: повідомлення шини не містять значень (AC-101); `td_energy` канал не віддає даних при підписці користувача без групи (клієнт лише дістає «тік»).
- ТБ-10: `_td_backfill` без адміністратора → `AccessError` (AC-148).

### 13.4 Тести продуктивності (ТП-07…ТП-09)

- ТП-07: `_td_backfill(days=90)` ≤ 120 с, ≤ 600 000 рядків, пам'ять процесу ≤ 500 МБ (AC-148, ТК-14).
- ТП-08: `get_pult` ≤ 500 мс, `get_node_card` ≤ 300 мс, `get_mobile` ≤ 250 мс (AC-154).
- ТП-09: 20 одночасних сесій Пульту: навантаження RPC ≤ 12 викликів/хв на сесію (дебаунс 2 с, throttle 5 с), без росту черги `bus`.

### 13.5 DEPLOY_TEST (доповнення до `DEPLOY_TEST.md` td_energy)

1. Копія демо-БД (`f3d_full2`/`td_demo_tpl`) → `-u td_energy` → міграція 19.0.1.1.0: перевірити кількості (21 вузол на схемі, +15 сигналів, +1 джерело); 2. повторне `-u` — без змін; 3. відкат: `uninstall` не видаляє бізнес-дані; 4. `neutralize.sql`.

## 14. Definition of Done (W1, `td_energy`)

- Усі UT/UT-JS AC-93…AC-158 зелені; ТК-13…ТК-18 пройдено на стенді; ruff без помилок; 142 існуючих тести `td_energy` зелені (регресія);
- `neutralize.sql` оновлено; CHANGELOG, `README` розділ «Пульт»; DEPLOY_TEST доповнено; перегляд безпеки (ТБ-07…ТБ-10);
- Міграція 19.0.1.1.0 перевірена на копії БД; backfill виконано на стенді, скріншот Пульту з історією.

## 15. Відкриті питання

Див. ARCH §5 (Q-21…Q-24 `td_energy`, Q-25 `td_genset_factory3d`) і нижче рішення автора.

### Рішення автора `td_energy` (A-23…A-37)

| ID | Рішення | Обґрунтування |
|---|---|---|
| A-23 | Нові ключі параметрів/xml-id/методи — у td-іменах (`td.energy.*`, `view_td_energy_*`, `_td_*`); якщо `claude/td-rename` вирішить інакше — механічна заміна | E-04/E-09; повної карти немає |
| A-24 | Стан QS і PFC — нове джерело `MB-U73-SWB-CTRL` (контролер ГРЩ), карта регістрів — припущення для емулятора | У моделі немає сигналів QS/PFC; на об'єкті адреси задасть документ контролера |
| A-25 | Розділ «Генерація й резерв» і екран «Огляд» (СЕС/КГУ/BESS/АВР) — у `td_energy`, міст додає ДГУ й меню td_genset | Клієнти без ДГУ не втрачають СЕС/КГУ/BESS/АВР; відрізняється від формулювання «усе через міст» — менеджер може скасувати |
| A-26 | Мобільні вкладки «Стан/Тривоги/Схема» — у `td_energy` (W1); «Обхід» і push — W4 через реєстр `td_energy.mobile_tabs` | W1 включає «беру в роботу» (E-02) |
| A-27 | Схема — дані (`sld_*` на вузлі + `sld_layout.csv`); шини й підписи — теж вузли (`shape`) | Без жорсткого коду топології; правка менеджером |
| A-28 | Шина — рядковий канал `td_energy`, повідомлення без даних, клієнт перечитує RPC | Рядкові канали відкриті для підписки (зразок `f3d_yard`); безпеку тримає RPC |
| A-29 | Підтвердження тривог — клас A (група «Енергетик»); `take` = `ack` + виконавець | E-06; Mobile: «У роботі» знімає з активних |
| A-30 | Прогноз — типовий день за днем тижня (8 тижнів), PV масштабується фактом; без погоди; добу 23/25 год — за локальними слотами | Без зовнішніх залежностей |
| A-31 | Планове відключення — окрема модель | Інша семантика, ніж `td.energy.outage` (аварійне за АВР) |
| A-32 | Затверджує `mrp.group_mrp_manager`; МО автоматично не переносяться | «узгодження виробництвом» у макеті; перенесення — вручну |
| A-33 | Крок ступеня PFC — параметри вузла (35 × 10) | Макет затверджено; старий «50 + 3×100» |
| A-34 | Повірка — поля + нагадування подією, без окремого модуля метрології | Мінімум для макета |
| A-35 | Backfill — метод моделі + `tools/backfill.py`, `is_backfill`, `ON CONFLICT DO NOTHING`; свят немає | E-11; безпечний повтор |
| A-36 | Бусина BESS — амбер за активності (D-05) | Єдине кодування «активний» |
| A-37 | Версія модуля `19.0.1.1.0` + міграція | Нові поля/сигнали/група |

---

# ЧАСТИНА II. `td_genset_factory3d`

Міст `td_genset_factory3d` (було `factory3d_genset`; `docs/modules/td_genset/SPEC.md` M-01…M-09, V-01…V-09). E-01, E-08: `td_genset` лишається окремим продуктом (OPL-1); міст **хостить** меню й екрани td_genset у розділі «Генерація й резерв» застосунку «Енергетика» й ховає кореневу плитку td_genset. Модуль `td_genset` **не змінюється**.

## B.0 Дерево файлів (дельта; власник C)

```
odoo_addons/td_genset_factory3d/
├── __manifest__.py                    (менеджер) depends: + "td_energy" уже є; version 19.0.1.1.0; data — B.1
├── hooks.py                           C  + _restore_td_genset_root (uninstall_hook)
├── models/td_energy_dashboard.py      C  M-10: _inherit td.energy.dashboard (3 хуки)
├── adapters/td_genset.py              C  + ADP-11 next_event
├── data/menu_hide.xml                 C  приховання td_genset.menu_root (noupdate=0)
├── security/td_genset_factory3d_security.xml  C  implied_ids: manager → td_genset.group_user
├── views/menus.xml                    C  V-10 (замінює верхнє меню «Генератор»)
├── views/res_config_settings_views.xml  (без змін)
└── tests/test_w1_section.py, test_w1_hooks.py, stand/test_w1_tk_g.py   C
```

Також C: `services/iot_sim/**` і `td_iot_sim/data/**` (Частина I, розд. 8.1).

## B.1 Маніфест (дельта)

`depends`: без змін (`td_genset`, `td_factory3d`, `td_telemetry`, `td_energy`); `data` додати: `security/td_genset_factory3d_security.xml` (після `ir.model.access.csv`), `data/menu_hide.xml` (перед `views/menus.xml`), `views/menus.xml` замінити; `uninstall_hook` розширити `_restore_td_genset_root`.

## B.2 Моделі

### M-10 `td.energy.dashboard` — розширення міста (R-15)

`_inherit = "td.energy.dashboard"` (AbstractModel). Перевизначає хуки (`super()` обов'язковий):

| Хук | Алгоритм |
|---|---|
| `_td_genset_summary()` | для першої активної `td.genset.link` (`online`, `state_code` за R-03): `not online` або код 0 → `offline` («немає зв'язку»); код 10 → `fault` («аварія»); код 1 → `reserve` («резерв»); коди 2…9 → `running` («працює»); `fuel_pct` — з ADP-03 `snapshot().fuel_pct`; результат `{"state", "label", "fuel_pct"}`; зв'язку немає → `None` |
| `_td_generation_cards()` | `super()` + картка «ДГУ» (R-15) |
| `_td_node_facts_extra(node)` | для `node.code in ("ATS-1", "GENSET")` — рядки R-15 п.2 |
| `_td_node_card_extra(node)` | для `GENSET`: `{"genset": {"link_id", "open_action": ADP-08}}` (для кнопки «Відкрити пульт генератора») |

Читання `td_genset` — лише через `adapters.td_genset` (виклик через атрибут модуля, `SPEC` §2.0 «Тестованість»), `sudo()` — лише всередині адаптера для read-only фактів.

### M-11 Групи (дані, без моделі)

`implied_ids`: `td_energy.group_td_energy_manager` → `td_genset.group_user` (A-21). `group_td_energy_user` **не** отримує прав td_genset.

## B.2a Адаптер: ADP-11

| ID | Сигнатура | Повертає | Алгоритм |
|---|---|---|---|
| ADP-11 | `next_event(gen) -> str \| None` | текст найближчої події генератора (розклад/таймер/тест), напр. «19.10 06:30 · пробний пуск 30 хв» | читає `td.genset.next_event_text` (компут. поле `GS/models/genset.py:373`); порожнє → `None`. Константа `FIELD_NEXT_EVENT = "next_event_text"` (`# ЗВІРИТИ`, `test_adapter_contract`) |

Існуючі ADP-03 (`fuel_pct`, `online`, `state_raw`), ADP-06 (`windows`), ADP-07 (`last_test`: `ts`, `duration_min`, `result`), ADP-08 (`open_action`) — без змін.

## B.3 Представлення й меню

| ID | XML-id | Тип | Структура |
|---|---|---|---|
| V-10 | `td_genset_factory3d.menus` (`views/menus.xml`) | menu | **видалено** верхнє меню «Генератор» (`menu_f3d_genset` → `menu_td_genset_factory3d`, parent `menu_td_root`, seq 55) і його 4 пункти; нові — таблиця B.3.1 |
| V-11 | `data/menu_hide.xml` | data | `<record id="td_genset.menu_root" model="ir.ui.menu"><field name="active" eval="False"/></record>` у `noupdate="0"` (E-08, A-20) |

### B.3.1 Меню міста (parent `td_energy.menu_td_energy_generation`, групи `td_genset.group_user`, якщо не вказано)

| XML-id | Назва | seq | Дія / батько |
|---|---|---|---|
| `menu_gf_genset` | Генератор | 20 | `td_genset.action_td_genset_main` |
| `menu_gf_reading` | Показання | 30 | `td_genset.action_td_genset_reading` |
| `menu_gf_event` | Події генератора | 40 | `td_genset.action_td_genset_event` |
| `menu_gf_fuel` | Заправка | 50 | — (розділ) |
| `menu_gf_fuel_canister` | Каністри | 10 | `td_genset.action_td_genset_canister` (батько `menu_gf_fuel`) |
| `menu_gf_fuel_refuel` | Заправки | 20 | `td_genset.action_td_genset_refuel` |
| `menu_gf_fuel_move` | Рух запасу | 30 | `td_genset.action_td_genset_fuel_move` |
| `menu_gf_analytics` | Аналітика генератора | 60 | — (розділ) |
| `menu_gf_analytics_run_outage` | Робота і відключення по днях | 10 | `td_genset.action_td_genset_analytics_run_outage` (батько `menu_gf_analytics`) |
| `menu_gf_analytics_energy` | Вироблено по днях | 20 | `td_genset.action_td_genset_analytics_energy` |
| `menu_gf_analytics_cranks` | Пуски і АКБ при прокрутці | 30 | `td_genset.action_td_genset_analytics_cranks` |
| `menu_gf_analytics_fuel_used` | Витрата по днях | 40 | `td_genset.action_td_genset_analytics_fuel_used` |
| `menu_gf_analytics_fuel_level` | Рівень палива | 50 | `td_genset.action_td_genset_analytics_fuel_level` |
| `menu_gf_analytics_battery` | Напруга АКБ | 60 | `td_genset.action_td_genset_analytics_battery` |
| `menu_gf_analytics_load` | Навантаження під час роботи | 70 | `td_genset.action_td_genset_analytics_last_run` |
| `menu_gf_link` | Зв'язка з заводом | 70 | `action_td_genset_link` (бувше `action_f3d_genset_link`), групи `td_factory3d.group_td_user` |
| `menu_gf_requests` | Заявки ТО генератора | 80 | `action_td_genset_requests` |
| `menu_gf_config` | Налаштування | 90 | — (розділ), групи `td_energy.group_td_energy_manager` |
| `menu_gf_config_profile` | Профілі генераторів | 10 | `action_td_genset_profile`, групи `td_factory3d.group_td_manager` |
| `menu_gf_config_event_map` | Події → ТО | 20 | `action_td_genset_event_map`, `group_td_manager` |
| `menu_gf_config_td` | Налаштування генератора | 30 | `td_genset.action_td_genset_config` |
| `menu_gf_config_gensets` | Генератори | 40 | `td_genset.action_td_genset` |
| `menu_gf_config_levels` | Ланцюжок ескалації | 50 | `td_genset.action_td_genset_notify_level` |
| `menu_gf_config_locations` | Місця зберігання | 60 | `td_genset.action_td_genset_storage_location` |
| `menu_gf_config_controllers` | Моделі контролерів | 70 | `td_genset.action_td_genset_controller_model`, групи `td_genset.group_tech` |

Меню td_genset **не перепідпорядковуються** (A-19): при `-u td_genset` їхній `parent_id` повертається; хостовані пункти — власні записи міста. `menu_f3d_genset_settings` («Налаштування генератора» під `td_factory3d.menu_td_config`, адмін) лишається без змін. Кількість нових пунктів: **25** (з них 3 розділи-контейнери з дітьми — `menu_gf_fuel`, `menu_gf_analytics`, `menu_gf_config`).

## B.4 Права

Нових моделей немає. Група: `security/td_genset_factory3d_security.xml`:

```xml
<record id="td_energy.group_td_energy_manager" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('td_genset.group_user'))]"/>
</record>
```

Наслідок: «Енергетик» бачить екрани td_genset (як «Співробітник»); перегляд енергетики (`group_td_energy_user`) бачить розділ, картку ДГУ й факти (читання через адаптер із `sudo()` лише для фактів), але не меню td_genset і не її дані.

## B.5 Дані й хуки

- `data/menu_hide.xml` (V-11) — застосовується при встановленні/оновленні міста; **`uninstall_hook`** `_restore_td_genset_root(env)`: `ir.ui.menu` `td_genset.menu_root` → `active=True` (якщо запис є). Якщо `td_genset` видаляється раніше за місто — хук не падає (`env.ref(..., raise_if_not_found=False)`).
- Міграція БД `f3d_full2` (E-04: перейменування моста виконує гілка `claude/td-rename`; тут лише меню): `-u td_genset_factory3d` видаляє застарілі `menu_*genset*` (не `noupdate`) і створює 25 нових; перевірити `ir_ui_menu` (6 записів моста → 25 нових), `ir_model_data` для `td_genset` (1 082 записи) **без змін**.

## B.9 Алгоритми й правила

### R-14 Розділ «Генерація й резерв»: структура й приховування (FR-18, FR-19)

1. Контейнер `td_energy.menu_td_energy_generation` створює `td_energy`; міст лише додає дітей (B.3.1). Без моста розділ має єдиний пункт «Огляд».
2. Верхнього меню «Генератор» у корені `td_factory3d.menu_td_root` у БД з установленим мостом **немає** (AC-74).
3. `td_genset.menu_root` — `active=False`, поки встановлено міст (AC-75); `uninstall_hook` повертає `active=True`; `-u td_genset` не скидає (AC-83).
4. `td_genset` без `td_energy`/моста — повністю працездатний, його плитка активна (AC-82).

### R-15 Факти ДГУ для розділу, Пульту, АВР (FR-20)

1. **Картка «ДГУ»** (`_td_generation_cards`): `{"code":"GENSET","title":"ДГУ","kind":"genset","state":…,"kpis":[…],"facts":[…],"node_code":"GENSET","can_3d":true,"link":{"open_action": ADP-08}}`: `state` — `gen` (`running`), `alarm` (`fault`), `off` (`reserve`, `offline` — «резерв / вимкнено»), KPI: «Паливо» `fuel_pct` %, «Потужність» `p_kw`, «Мотогодини» `hours`; факти: «Тест: {ADP-07 ts · result}» (якщо є), «Наступна подія: {ADP-11}», «До ТО: {ADP-05 hours_left} мотогод» (якщо `service_info`).
2. **Факти вузла `ATS-1`/`GENSET`** (`_td_node_facts_extra`): «ДГУ в резерві · паливо {fuel_pct} % · тест {ts} {result}»; «Наступна подія: {ADP-11}»; для `GENSET` — додатково «Мотогодини {hours}».
3. Помилки адаптера (`NotImplementedError`, `td_genset` без запису) → хук повертає порожньо й пише `_logger.warning` (Пульт не падає).

### R-16 Групи й видимість (FR-21)

1. `group_td_energy_manager` → `td_genset.group_user` (B.4); `group_td_energy_user` — ні.
2. Пункти меню B.3.1 мають свої `groups` (`td_genset.group_user`), тому користувач без них бачить у розділі лише «Огляд» (і «Зв'язку»/«Заявки» за `td_factory3d.group_td_user`).

## B.10 Стани

Нових станів немає.

## B.11 Помилки

Адаптер недоступний/незвірений — картка «ДГУ» не додається, `genset=null` у KPI, лог `warning`; відсутній `td_genset` у БД (міст не встановлено) — хуки не активні (міст не завантажено).

## B.12 Acceptance Criteria `td_genset_factory3d` (AC-74…AC-83)

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-74 | FR-18 | Given `td_genset`, `td_energy`, міст встановлено; Then немає `ir.ui.menu` з назвою «Генератор» і `parent_id = td_factory3d.menu_td_root`; `td_energy.menu_td_energy_generation` має дітей `menu_gf_genset`, `menu_gf_reading`, `menu_gf_event`, `menu_gf_fuel`, `menu_gf_analytics`, `menu_gf_link`, `menu_gf_requests`, `menu_gf_config` | UT |
| AC-75 | FR-19 | Given міст встановлено; Then `td_genset.menu_root.active=False`; When видалити міст; Then `active=True` | UT |
| AC-76 | FR-18 | Given 25 нових меню; Then кожне з `action` має валідний xml-id дії `td_genset` або мосту, `groups` як B.3.1; меню td_genset (`menu_genset`, …) лишаються з первинним `parent_id` (не перепідпорядковано) | UT |
| AC-77 | FR-21 | Given користувачі: A — `group_td_energy_manager`, B — `group_td_energy_user`; Then A має `td_genset.group_user`, B — ні; B бачить розділ, але не бачить `menu_gf_genset`; A бачить | UT |
| AC-78 | FR-20 | Given адаптер замокано (`fuel_pct=78`, `online=True`, `state_code=1`, `last_test`, `next_event`); When `get_generation()`; Then 5 карток (СЕС, КГУ, BESS, АВР, ДГУ); картка ДГУ: `state='off'`, паливо 78 %, факти тесту й наступної події | UT |
| AC-79 | FR-20 | Given те саме; When `get_pult()`; Then `kpis.generation.genset = {state: "reserve", label: "резерв", fuel_pct: 78}`; факти вузла `ATS-1` містять рядок «ДГУ в резерві · паливо 78 %…» | UT |
| AC-80 | FR-20 | Given `td.genset.link` `online=False`; Then `genset.state='offline'`, `label «немає зв'язку»`; адаптер кидає `NotImplementedError` → картки ДГУ немає, `genset=null`, виняток не поширюється | UT |
| AC-81 | FR-18 | Given лише `td_energy` (без моста); Then жодних посилань на `td_genset` у `td_energy` (grep модуля), `get_generation()` — 4 картки (AC-143), `get_pult()` — `genset=null` | UT |
| AC-82 | FR-19 | Given БД лише з `td_genset` (без `td_energy`/моста); Then `td_genset.menu_root.active=True`, 223 тести `td_genset` зелені, жодної залежності від моста | TC |
| AC-83 | FR-19 | Given міст встановлено; When `-u td_genset`; Then `td_genset.menu_root` лишається `active=False`; хостовані меню на місці | TC |

## B.13 План тестування

- **UT (`tests/test_w1_section.py::TestW1Section`):** AC-74…AC-77; **(`test_w1_hooks.py::TestW1Hooks`):** AC-78…AC-81 (адаптер — `patch.object(td, "snapshot", …)`, `td.next_event`, `td.last_test`; `test_adapter_contract.py` розширити константою `FIELD_NEXT_EVENT`).
- **ТК-G14** (стенд): БД з `td_genset` + `fake_relay` (профіль D700) + міст + `td_energy`: меню розділу відкриваються, пульт td_genset працює як client action під «Генерація й резерв»; Пульт енергетики показує «ДГУ · резерв». **ТК-G15:** встановити лише `td_genset` — плитка активна, 223 тести; додати міст — плитка прихована; `-u td_genset` — лишається прихованою; видалити міст — повертається.
- **ТБ-11:** користувач `group_td_energy_user` не читає `td.genset.*` напряму (`AccessError`), але отримує факти ДГУ через `get_generation()`.
- **ТП-07 (міст):** `get_generation()` з мостом ≤ 100 мс додатково до базового.
- **DEPLOY_TEST (міст):** `-u td_genset_factory3d` на копії БД: 25 меню, `td_genset.menu_root` прихований; відкат (`uninstall`) — плитка повертається.

## B.14 DoD (міст W1)

AC-74…AC-83 зелені; 101 існуючий тест моста й 223 тести `td_genset` зелені (регресія); `ruff`; `neutralize.sql` без змін; CHANGELOG; перегляд безпеки (ТБ-11).

## B.15 Відкриті питання

Q-25 (`td_genset_factory3d`): префікс моделей моста (`td.genset.link|profile|event.map`) займає простір імен `td.genset.*` модуля `td_genset` (колізій назв немає, 16 моделей td_genset: `td.genset`, `.command`, `.reading`, `.relay.client`, `.alarm`, `.event`, `.schedule`, `.schedule.exception`, `.storage.location`, `.canister`, `.fuel.move`, `.refuel`, `.fuel.calibration`, `.config`, `.notify.level`, `.controller.model`). Рекомендація: окремий префікс `td.genset3d.*` (`link`, `profile`, `event.map`) — вирішити до злиття `claude/td-rename`. Поки відповіді — міст лишається `td.genset.link|profile|event.map` (як у карті перейменування).

### Рішення автора `td_genset_factory3d` (A-19…A-23)

| ID | Рішення | Обґрунтування |
|---|---|---|
| A-19 | Нові власні меню в розділі; меню `td_genset` не перепідпорядковуються | `-u td_genset` повертає `parent_id` |
| A-20 | Корінь td_genset ховається `active=False` (V-11) і відновлюється в `uninstall_hook` | E-08; не змінює `td_genset` |
| A-21 | `implied_ids` лише «Енергетик» → `td_genset.group_user` | Читачі енергетики не отримують прав на дані генератора |
| A-22 | Розширення дашборда `td.energy.dashboard` через `_inherit` і 4 хуки | Один контракт з `td_energy` без імпорту моделей td_genset у `td_energy` |
| A-23 | Відхилення від B.3.1: меню `menu_gf_requests` («Заявки ТО генератора») — група `td_factory3d.group_td_user` (не `td_genset.group_user`); AC-76 перевіряє саме її | R-16 п. 2: розділ показує «Зв'язку»/«Заявки» читачам за `group_td_user` (як було в меню «Генератор»); заявки — стандартні `maintenance.request`, а не дані td_genset |
