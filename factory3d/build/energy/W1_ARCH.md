# W1 «Енергетика» — технічне рішення (вставки до ARCHITECTURE `td_energy` і `td_genset_factory3d`)

Версія 0.1 · 18.10.2026 · автор: агент-аналітик (хвиля W1 блоку «Енергетика») · статус: **чернетка на погодження**.
Вхід: `build/energy/GAP.md` (E-01…E-11, матриця), макет `Main.dc.html`, `Feeder.dc.html`, `Mobile.dc.html` (вкладки «Стан», «Тривоги», «Схема»). Каркас: `docs/ARCHITECTURE.md` §5, §6.4–§6.8. Специфікація: `build/energy/W1_SPEC.md` (далі SPEC). Імена — td (E-04, E-09): модулі `td_energy`, `td_genset_factory3d`, `td_telemetry`, `td_bms`, `td_viewer3d`, `td_factory3d`; маршрути `/f3d/*` і коди сигналів не змінюються. Рішення автора — A-xx (SPEC розд. 15 і B.15), питання — Q-21…Q-25 (§5), контракти — C-xx (§2.1).
Після злиття `claude/td-rename` файл розкладається в розділи `docs/modules/td_energy/ARCHITECTURE.md` і `docs/modules/td_genset_factory3d/ARCHITECTURE.md`.

## Загальна інформація

| Етап ToDo | Що здається | Люд./год (оцінка автора) |
|---|---|---|
| ТР | `W1_SPEC.md` + цей документ | 24 |
| Архітектура | погодження A-xx/Q-xx, фіксація контрактів API-05…API-13 | 6 |
| Розробка | `td_energy` W1 (A бекенд ≈ 40, B фронтенд ≈ 40), `td_genset_factory3d` + емулятор (C ≈ 16) | 96 |
| Тестування | 76 AC: UT ≈ 12, hoot ≈ 4, стенд ТК-13…ТК-18, ТК-G14/G15 ≈ 12, DEPLOY_TEST ≈ 4 | 32 |
| Інструкція | §4 цього документа + README/CHANGELOG | 6 |
| **Разом** | | **164** |

Факти середовища (перевірено 18.10.2026, лише читання): демо-БД `f3d_full2` на цьому хості — 123 вузли, 67 лічильників, 297 сигналів `energy`, 0 інтервалів/подій/показань, `install_report.state=partial` (`equipment_linked=0`); тестовий сервер — Odoo 19.0+e (за `factory3d_energy` ARCHITECTURE «Загальна інформація»). Гілка перейменування `claude/td-rename` (коміт 95bf195) містить лише `git mv` файлів (імена `td_energy_node.py`, `td_energy_security.xml`, `menus.xml`).

## 1. Опис процесу і функціональні вимоги

### 1.1 Контекст

**Макет (затверджений замовником).** W1 відтворює: `Main.dc.html` (Пульт: шапка з періодом, 6 KPI, банер рекомендації, однолінійна схема з вибором вузла, профіль доби 15 хв, тривоги, найбільші споживачі, енергія на виробництво, ТО й відключення), `Feeder.dc.html` (картка вузла ШР-2: 5 KPI, графік струму, відгалуження, облік, захист, події, обслуговування, планове відключення, діалоги заявки ТО й відключення), `Mobile.dc.html` (вкладки «Стан», «Тривоги», «Схема»; «Обхід» — W4). Відхилення — SPEC «D-01…D-18».

**Що вже є (поточні файли, `claude/factory3d-build`).**

| Складова | Де | Що дає W1 |
|---|---|---|
| Вузли/лічильники/інтервали/баланс/події/відключення | `factory3d_energy/models/f3d_energy_*.py` | усі розрахунки Пульту (R-04, R-06, R-07, R-15) |
| Живі сигнали `energy/*`, `infra/*` | `EN/models/f3d_energy_node_live.py:21,38` | KPI, схема, факти |
| Провайдери 3D | `EN/models/viewer_provider.py:10-31`, `EN/tools/payload.py:162` | «Показати в 3D», лишаються без змін |
| `f3d.command`, збирач | `TL/models/f3d_command.py:14`, `COL/core/commands.py:76` | **не використовуються в W1** (команди — W2) |
| Меню енергетики | `EN/views/menus.xml:9-35` | перегрупування (SPEC 3.3) |
| `td_genset` (продукт) і міст | `GS/views/menu.xml:16`, `GB/views/menus.xml:4`, `GB/adapters/td_genset.py` | розділ «Генерація й резерв», факти ДГУ |
| Шаблон OWL + RPC | `factory3d_bms/static/src/overview/*`, `f3d_bms_overview.py:54` | зразок клієнтської дії |
| Шина | `factory3d_yard/models/f3d_yard_notify.py`, `kpp.js:36-60` | зразок рядкового каналу й дебаунсу |
| hoot-тести | `factory3d_bms/tests/test_hoot.py` | зразок запуску JS-тестів |

**Покриття матриці GAP у W1:** PU-01…PU-03, PU-05…PU-10, PU-13…PU-23, PU-25 (повністю), PU-11/12/24/26 (лише слот і контракт, D-02, D-03), PU-04 (W4); ND-01…ND-18 (повністю); MB-01…MB-07 (повністю), MB-08/09 (W4; «вхід у мобільний» — клієнтська дія є).

### 1.2 Ролі й сценарії

| Роль (група) | Що робить у W1 | Меню |
|---|---|---|
| Перегляд (`td_energy.group_td_energy_user`) | дивиться Пульт, схему, картку вузла, події, генерацію; без вартості (`group_td_energy_cost`) | Енергетика |
| Вартість (`…_cost`) | те саме + ₴ | Енергетика |
| **Енергетик** (`…_manager`) | підтверджує тривоги, бере в роботу, створює відключення, заявки ТО, правит схему/повірку | Енергетика, Налаштування |
| **Головний енергетик** (`…_chief`, нова, E-06) | усе вище + закриває чужі тривоги; команди класу B — у W2 | Енергетика |
| Керівник виробництва (`mrp.group_mrp_manager`) | узгоджує/відхиляє планові відключення | Планові відключення |
| Склад (`stock.group_stock_manager`) | отримує сповіщення про відключення | чат/activity |
| Адміністратор (`td_factory3d.group_td_admin`) | налаштування, `_td_backfill` | Налаштування |

Сценарії: **S1** ранковий огляд (Пульт → період «Зміна»); **S2** тривога «лічильник PM-QF-C2 не на зв'язку» → «Діагностика» → «Взяти в роботу» (десктоп і телефон); **S3** планове відключення ШР-2: картка вузла → «Запланувати відключення» → узгодження виробництвом → статус на картці й Пульті; **S4** рекомендація (слот): банер з дією-посиланням і «Пізніше»; **S5** генерація: «Енергетика → Генерація й резерв» (СЕС, КГУ, BESS, АВР, ДГУ); **S6** демо-стенд: адміністратор запускає генератор історії.

### 1.3 Функціональні вимоги

| ID | Модуль | Вимога |
|---|---|---|
| FR-30 | td_energy | Клієнтська дія «Пульт енергетика» (`td_energy.pult`) у меню «Енергетика», доступна `group_td_energy_user`, з резервним опитуванням і підпискою на шину |
| FR-31 | td_energy | Шість KPI (з мережі, споживання, енергія за період, пік, власна генерація, cos φ) і перемикач періоду Зараз/Зміна/Доба/Місяць за R-27; вартість лише з групою вартості |
| FR-32 | td_energy | Слот рекомендації: модель `td.energy.advice`, банер у Пульті, «Пізніше», реєстр правил `_td_advice_rule_*`, контракт `actions[]`; дії керування приховані без W2 |
| FR-33 | td_energy | Однолінійна схема з топології вузлів (геометрія `sld_*`), стани за R-26, оновлення через шину `td_energy` (R-33) |
| FR-34 | td_energy | Панель вибраного вузла: факти за R-29, «Відкрити картку вузла», «Показати в 3D» |
| FR-35 | td_energy | Профіль доби 15 хв (факт + прогноз типового дня), прогноз до кінця доби, експорт, небаланс за R-28 |
| FR-36 | td_energy | Тривоги й події з життєвим циклом (`active/acked/resolved`): підтвердити, взяти в роботу, повернути, закрити; авто-вирішення (R-25); діагностика лічильника |
| FR-37 | td_energy | «Відкрити в 3D» з Пульту, схеми, картки, тривоги |
| FR-38 | td_energy | Картка вузла (ШР-2) за R-30: KPI, графік струму, відгалуження, облік (+повірка), захист, події, обслуговування, планове відключення |
| FR-39 | td_energy | Планове відключення: створення, попередній перегляд зачеплених відгалужень і МО, узгодження виробництвом, сповіщення (R-31) |
| FR-40 | td_energy | Заявка ТО з картки вузла (діалог → `maintenance.request`) |
| FR-41 | td_energy | Пульт: «Найбільші споживачі зараз», «Енергія на виробництво · сьогодні», «ТО й відключення» |
| FR-42 | td_energy | Розділ «Генерація й резерв» з огляд-екраном СЕС, КГУ, BESS, АВР (R-38) і точками розширення для моста |
| FR-43 | td_energy | Групи (нова `group_td_energy_chief`), ACL нових моделей, налаштування Пульту, `neutralize.sql`, `uninstall_hook` без втрати даних |
| FR-44 | td_energy | Сигнали QS і PFC (джерело `MB-U73-SWB-CTRL`), секційний cos φ з порогами E-10 (0,95/0,92/0,90), інструмент історії (backfill) для демо |
| FR-45 | td_energy | Мобільна клієнтська дія (Стан, Тривоги, Схема) з «Беру в роботу» і «Призначити на себе» |
| FR-18 | td_genset_factory3d | Хостинг меню й екранів `td_genset` у розділі «Генерація й резерв»; верхнє меню «Генератор» відсутнє |
| FR-19 | td_genset_factory3d | Коренева плитка `td_genset` прихована за наявності моста й відновлюється при його видаленні; `td_genset` без моста працює як раніше |
| FR-20 | td_genset_factory3d | Факти ДГУ (паливо, стан, тест, наступна подія) у картці «ДГУ», KPI Пульту, фактах вузла АВР |
| FR-21 | td_genset_factory3d | «Енергетик» отримує доступ до екранів `td_genset`; «Перегляд» — ні |

### 1.4 Межі (не входить у W1)

Команди й сценарії автоматики, інтерлоки, розклад, пріоритети скидання (W2); ресурси газ/тепло/повітря/вода, ціни, правила резервів економії (W3); EnPI, бюджет, теплокарта, зрізи, PDF-звіти й «Звіт за зміну» (W4); вкладка «Обхід», Web Push, PWA (W4); автоматичне перенесення МО при відключенні; зміна `td_genset` (продукт не чіпаємо); запис у пристрої (`write_enabled` без змін, `module='energy'` лишається read-only, AC-81 попереднього SPEC чинний).

## 2. Технічна реалізація

### 2.1 Місце в системі й контракти

`td_energy` (`depends`: `td_telemetry`, `mrp_account`, `analytic`, `web_hierarchy` — без змін; `bus`, `mail` — транзитивно). `td_genset_factory3d` (`depends`: `td_genset`, `td_factory3d`, `td_telemetry`, `td_energy`). `td_genset` — не змінюється.

| Контракт | Хто → кому | Зміст |
|---|---|---|
| C-30 | `td_energy` → клієнт | JSON API-05/06/07/12/13 (SPEC розд. 7); ключі вартості лише з групою вартості |
| C-31 | `td_energy` → міст | хуки `td.energy.dashboard._td_genset_summary`, `_td_generation_cards`, `_td_node_facts_extra`, `_td_node_card_extra` (SPEC M-27, M-10) |
| C-32 | `td_energy` → W2 | `td.energy.advice.actions[]` (`kind='control'`), реєстр правил `_td_advice_rule_*`, прапор `meta.control_available` |
| C-33 | `td_energy` → W4 | реєстр мобільних вкладок `registry.category("td_energy.mobile_tabs")`, `td.energy.interval.is_backfill` |
| C-34 | `td_energy` → шина | канал `td_energy`, тип `td_energy/update`, повідомлення без даних (R-33) |
| C-35 | `td_energy` ← `td_telemetry` | `td.signal._td_ingest` (CT-10, обчислювані сигнали `energy/sections/*`), `td.source`, CT-05 (заявки з порогів PFC) |
| C-36 | `td_energy` ← `td_bms`/`td_viewer3d` | `action_td_show` (3D), сигнали BMS не потрібні в W1 |
| C-37 | міст ← `td_genset` | адаптер `adapters/td_genset.py` ADP-03/05/06/07/08 + **ADP-11** |

### 2.2 Архітектурна схема

```
 iot_sim (SWB-CTRL u73, PM5560, SUN2000, LUNA2000, ATyS, TEDOM) ──Modbus──▶ collector ──push──▶ td.signal / td.reading
                                                                                              │
   td_energy crons: live(1 хв) ─▶ totals, sections cos φ, pfc ─▶ bus.tick('kpi')            │
                    intervals(5 хв) ─▶ td.energy.interval ─▶ bus.tick('profile')            │
                    balance(1 год)  ─▶ td.energy.balance                                      ▼
   td.energy.event (R-24/R-25) ◀── _td_log, _td_status_event ◀── ingest hooks        td.energy.dashboard (AbstractModel)
   td.energy.outage.plan, td.energy.advice, maintenance.request ─────────────────────▶  get_pult / get_node_card / get_alarms / get_mobile / get_generation
                                                                                              │  (хуки C-31)
   bus.bus ─ "td_energy/update" (тільки kinds, без даних) ─▶ OWL: Pult · NodeCard · Generation · Mobile ◀── orm.call (ACL, групи, cost-gating)
   td_genset ──ADP── td_genset_factory3d: меню в «Генерація й резерв», картка ДГУ, факти АВР
```

### 2.3 Нові й розширені об'єкти

| Об'єкт | Призначення | Пише | Читає |
|---|---|---|---|
| `td.energy.event` (розш., M-21) | тривоги з життєвим циклом | `_td_log`, auto-resolve, `action_*` | Пульт, мобільний, картка |
| `td.energy.node` (розш., M-22) | геометрія схеми, захист, PFC-кроки, `sld_state` | менеджер, `_load_sld_layout` | Пульт, картка |
| `td.energy.meter` (розш., M-23) | повірка | менеджер, крон | картка |
| `td.energy.interval` (розш., M-24) | `is_backfill`, `_td_backfill` | крон, backfill | усі розрахунки |
| `td.energy.outage.plan` (M-25) | планове відключення | менеджер, mrp-менеджер, крон | картка, Пульт |
| `td.energy.advice` (M-26) | слот рекомендацій | правила (W2), менеджер | Пульт, мобільний |
| `td.energy.dashboard` (M-27) | API | — | клієнти |
| `td.energy.ticket.wizard` (M-28) | заявка ТО з картки | менеджер | — |
| хуки/розширення міста (M-10) | ДГУ у розділі | — | дашборд |
| сигнали (+15), джерело `MB-U73-SWB-CTRL` | QS, PFC, секційний cos φ | збирач, `live` | схема, факти |

### 2.4 Інтеграції

| Пристрій / система | Протокол | Напрямок | Частота | При недоступності |
|---|---|---|---|---|
| Контролер ГРЩ `SWB-CTRL` (QS, PFC) | P-07 Modbus TCP (unit 73; регістри — припущення) | читання | 10 с | сигнали stale → `sld_state` QS `off`, PFC — теоретичний `q_pfc_s` (R-35) |
| Емулятор `iot_sim` | як вище | — | — | на стенді: модель `swb` + сценарій `pfc_step_fault` |
| `td_genset` | через адаптер | читання | при запиті | картка ДГУ не додається, лог warning |
| `bus` | websocket | Odoo → клієнт | не частіше 1 за 5 с | клієнт на резервному опитуванні 30 с |
| `maintenance` | ORM | читання/створення | — | — |
| `mrp.workorder` | ORM | читання | — | відсутні МО → «—», 0 замовлень |

### 2.5 Потік даних від пристрою до екрана

1. Збирач опитує `SWB-CTRL` (`energy/cells/QS/state` HR 100, `energy/cells/PFC-{1,2}/…` HR 110–123), PM5560, інвертори, BESS → `POST /f3d/telemetry/push` → `td.signal.last_value/last_ts`, `td.reading`.
2. `cron_td_energy_live` (1 хв): `_td_live_snapshot` → тотали (`energy/totals/p_now`, `infra/totals/grid_kw|export_kw|pv_now`), **секційні** `energy/sections/S*/{cos_phi,p_kw,q_kvar}`, `pfc_q_now` вузлів PFC → `bus.tick('kpi')`.
3. `cron_td_energy_intervals` (5 хв): `td.energy.interval` (15 хв) → R-11/R-15 → `bus.tick('profile')`.
4. Пороги сигналів/ingest-хуки → `td.energy.event._td_log(level, kind, code, text, …)` → R-24 (`title/detail/state`) → `bus.tick('alarm')`; CT-05 створює `maintenance.request` для PFC-fault.
5. Клієнт `Pult` отримує повідомлення `td_energy/update {"kinds": [...]}` → за 2 с дебаунсу викликає `td.energy.dashboard.get_pult(period, parts)` (тільки потрібні частини) → малює KPI, схему, профіль, тривоги.
6. Дія оператора («Підтвердити», «Взяти в роботу») → `td.energy.event.action_ack|take` → `bus.tick('alarm')` → усі відкриті сесії оновлюють список ≤ 10 с.
7. Планове відключення: діалог → `td.energy.outage.plan.preview` → `create` + `action_submit` → activity/сповіщення → `approve` → блок картки й рядок Пульту.

### 2.6 Безпека

- Групи: нова `group_td_energy_chief` (E-06) → імпліцитно «Енергетик»; адміністратор → chief. Читання API — `group_td_energy_user`; вартість — `group_td_energy_cost`; підтвердження/взяття — «Енергетик»; закриття чужого — chief або виконавець; затвердження відключення — `mrp.group_mrp_manager`; `_td_backfill` — адміністратор.
- **Стоп-крани:** `td.energy.read_enabled` керує кронами (як раніше); `write_enabled` **не змінюється** (W1 не пише в пристрої); нових прапорців запису немає. `neutralize.sql`: +3 крони, джерело `MB-U73-SWB-CTRL`.
- Шина: рядковий канал (відкритий для підписки, зразок `f3d_yard`), тому повідомлення **не несуть даних** (A-28); безпеку дає RPC.
- Міст: `implied_ids` лише «Енергетик» → `td_genset.group_user` (A-21); факти ДГУ читає адаптер із `sudo()` лише на читання.
- Заборонено: запис у `td_genset`; зміна меню `td_genset`; нові HTTP-маршрути; `x_`-поля; `safe_eval` над даними БД.

### 2.7 Продуктивність і обсяги

| Об'єкт | Обсяг | Примітка |
|---|---|---|
| `td.energy.interval` (backfill 90 діб) | 67 × 96 × 90 = **578 880** рядків (+ ~6 880 на добу працюючого стенда: 67×96) | існуючий індекс `(day, role)`; ротація `keep_interval_days=400` |
| Backfill | ≤ 120 с, ≤ 500 МБ RAM, пакети ≤ 5 000 | R-36 |
| `td.energy.event` | десятки/добу + ≤ 3/добу від backfill | індекс `(state, ts)` |
| `get_pult` | ≤ 500 мс, ≤ 40 SQL; один `search_read` сигналів `energy/%`+`infra/%`, один `_read_group` інтервалів доби, один — типового дня | AC-154 |
| Шина | ≤ 1 повідомлення/5 с/воркер; клієнт ≤ 12 RPC/хв | ТП-09 |
| Нові сигнали | +15, 9 із них 10 с (≈ 78 000 показань/добу до політики `store_period_s=300` → ≈ 2 600/добу) | R-03 телеметрії |

### 2.8 Міграція й деінсталяція

`td_energy` `19.0.1.1.0` (SPEC 5.4): `post-migration` — сигнали (+15) і джерело (+1), пороги cos φ, SLD-геометрія (21 вузол), `title/detail/state` для наявних подій, група chief. Очікувано на `f3d_full2`: вузлів на схемі 21, `energy` сигналів 297 → 312, `td.source` 135 → 136, подій оновлено 0 (на демо), параметрів +14. Повторний `-u` нічого не змінює. `uninstall_hook` — без змін, бізнес-дані зберігаються.
`td_genset_factory3d`: `-u` замінює 6 меню на 25, ховає `td_genset.menu_root`; `ir_model_data` `td_genset` (1 082 записи) без змін; `uninstall` повертає плитку. Перейменування модуля/моделей/xml-id (E-04) виконує окрема гілка до старту коду W1 (E-09).

## 3. Налаштування системи (тестовий сервер)

| Об'єкт | Параметр | Значення | Коментар |
|---|---|---|---|
| `ir.config_parameter` | `td.energy.cos_phi_target` / `_warn` / `_alarm` | 0,95 / 0,92 / 0,90 | E-10 |
| | `td.energy.pult_refresh_s` | 30 | резервне опитування |
| | `td.energy.bus_throttle_s` | 5 | R-33 |
| | `td.energy.alarm_list_limit` | 8 | список тривог Пульту |
| | `td.energy.load_warn_pct` / `_alarm_pct` | 80 / 100 | `sld_state` |
| | `td.energy.forecast_weeks` / `_min_days` | 8 / 3 | прогноз |
| | `td.energy.advice_snooze_min` | 30 | «Пізніше» |
| | `td.energy.bess_reserve_pct` | 30 | лише показ |
| | `td.energy.verify_warn_days` | 30 | повірка |
| | `td.energy.pv_kwp` | 920 | % піку СЕС, backfill |
| | `td.energy.shift_calendar_id` (існує) | календар «Зміна 1 (07:00–15:30)» сервера → рекомендація Q-23 | перемикач «Зміна» |
| Групи | `group_td_energy_chief` | призначити головному енергетику | E-06 |
| | `group_td_energy_manager` | енергетики, чергові | підтвердження тривог |
| | `mrp.group_mrp_manager`, `stock.group_stock_manager` | керівник виробництва, склад | відключення |
| Крони | `cron_td_energy_advice` (5 хв), `_outage_plan` (15 хв), `_verification` (1 доба 06:00 Київ) | активні | SPEC розд. 6 |
| Джерело | `MB-U73-SWB-CTRL` | `iot-sim:502`, unit 73 | на об'єкті — адреса контролера ГРЩ |
| Сервіси стенда (E-11) | емулятор + збирач | постійні (systemd/compose) | робить менеджер |
| Історія | `_td_backfill(days=90)` | один раз після ≥ 5 хв роботи стенда | розд. 4, інструкція 4 |
| Меню | «Енергетика → Генерація й резерв» | видно `group_td_energy_user` | E-01; плитка `td_genset` прихована |

## 4. Інструкція

**4.1 Пульт: ранковий огляд (Перегляд/Енергетик).** 1) «Енергетика → Пульт». 2) Перемикач «Зміна» показує енергію й пік із початку зміни. 3) Клік на вузол схеми — факти й «Відкрити картку вузла»/«Показати в 3D». 4) Якщо зверху «Немає даних» — перевірте колектор («Телеметрія → Колектори»).

**4.2 Тривога: підтвердити й взяти в роботу (Енергетик).** 1) У блоці «Тривоги й події» натисніть «Підтвердити» (бачить уся зміна) або «Взяти в роботу» (стаєте виконавцем). 2) «Діагностика» розкриває стан джерела лічильника. 3) Після усунення причини подія закривається сама; інакше «Закрити» (виконавець або головний енергетик).

**4.3 Планове відключення (Енергетик → Керівник виробництва).** 1) Картка вузла (напр., ШР-2) → «Запланувати відключення». 2) Оберіть дату, причину, час; діалог показує зачеплені відгалуження й замовлення. 3) «Надіслати на узгодження» — керівник виробництва й склад отримують сповіщення. 4) Керівник відкриває відключення з нагадування й натискає «Узгодити» або «Відхилити» (з причиною). 5) Замовлення переносить планувальник вручну.

**4.4 Історія для демо (адміністратор/менеджер).** 1) Запустіть емулятор і збирач, зачекайте 5 хв. 2) `echo 'env["td.energy.interval"]._td_backfill(days=90)' | odoo-bin shell -d <db> --no-http` (≤ 2 хв). 3) Перевірте «Пульт»: профіль без дірок, прогноз з'явився. 4) Повтор безпечний; `purge=True` видаляє лише синтетичні дані.

**4.5 Чергування з телефону (Енергетик).** 1) «Енергетика → Чергування (телефон)». 2) Вкладка «Тривоги» → «Беру в роботу»; «Де це в 3D» відкриває місце на схемі цеху. 3) «Схема» — стани вузлів. 4) «Призначити на себе» для заявки ТО PFC.

**4.6 Де генератор (Енергетик).** «Енергетика → Генерація й резерв»: «Огляд» (СЕС, КГУ, BESS, АВР, ДГУ), далі «Генератор», «Показання», «Події генератора», «Заправка», «Аналітика генератора», «Налаштування». Окремої плитки «Генератори» немає.

## 5. Ризики й відкриті питання

| ID | Питання | Кому | Рекомендація | Що робимо тим часом |
|---|---|---|---|---|
| Q-21 | Хто окрім виробництва отримує сповіщення про відключення? (макет: «виробництво й склад») | замовник | `mrp.group_mrp_manager` — activity (узгоджує); `stock.group_stock_manager` — підписка й повідомлення | реалізовано як рекомендовано (SPEC R-31 п.4) |
| Q-22 | Реальна схема PFC (макет: 10 × 35 квар; старий SPEC: 50 + 3 × 100) і джерело стану QS/PFC на об'єкті (контролер ГРЩ?) | замовник, електрики | параметри вузла `pfc_step_kvar/steps_total`; сигнали з контролера ГРЩ | демо: емулятор `SWB-CTRL`, 35 × 10 |
| Q-23 | Календар змін для перемикача «Зміна» (сервер: «Зміна 1 07:00–15:30»; макет аналітики: зміна 1 07:00–16:00, зміна 2 16:00–23:00) | замовник | календар із двома змінами за макетом | використовується налаштований `shift_calendar_id` |
| Q-24 | Чи створювати заявку ТО автоматично для тривоги «лічильник не на зв'язку»? (макет: заявка лише для PFC) | замовник | ні (кнопка «Створити заявку» вручну), так для PFC | як рекомендовано |
| Q-25 | Префікс моделей моста (`td.genset.link|profile|event.map` у просторі `td.genset.*`) | менеджер | `td.genset3d.*`, рішення до злиття `td-rename` | лишаємо `td.genset.*` |

**Ризики.** R1 — перейменування (E-04) у польоті: SPEC у td-іменах, код після злиття гілки (E-09); припущення A-23 (методи `_td_*`, ключі `td.energy.*`) може змінитись — механічна заміна. R2 — демо-БД без прив'язки обладнання (`equipment_linked=0`): ND-04/ND-11 повноцінно перевіряються лише на БД із демо-обладнанням (тестовий сервер, прив'язка `action_td_energy_rebind`). R3 — геометрія схеми — дані (A-27): інша топологія вимагає нового `sld_layout.csv`. R4 — відкрита шина без даних — прийнято (A-28). R5 — регресія: 142 тести `td_energy`, 223 `td_genset`, 101 моста мають лишитись зеленими. R6 — унікальність Modbus unit 73 (перевірено: у каталозі емулятора не зайнятий). R7 — розбіжність формулювання E-01 («усе через міст») і A-25 (розділ у `td_energy`): менеджер може скасувати.

## 6. План сборки агентами

### 6.0 Каркас (менеджер, до воркерів)

Після злиття `td-rename`: (1) вставити SPEC/ARCH у `docs/modules/td_energy`, `docs/modules/td_genset_factory3d`; (2) оновити `__manifest__.py` (`version`, `data`, `assets` — SPEC 1, B.1) і створити порожні файли з розд. 0 із заголовками-коментарями, щоб воркери не змагалися за `__init__.py`; (3) зафіксувати контракти C-30…C-37 (JSON з SPEC розд. 7 — зміни лише через менеджера). Воркери **не змінюють** `__manifest__.py`, `menus.xml` (крім B), `ir.model.access.csv` (лише A), `models/__init__.py`/`wizard/__init__.py` (лише A).

### 6.1 Воркери (паралельно, ≤ 3, без спільних файлів)

| Воркер | Файли (власні) | Розділи SPEC (ID) | Здає | Тести (команда) |
|---|---|---|---|---|
| **W1-A «Бекенд»** | `td_energy/models/*.py` (розд. 0 SPEC: `td_energy_event`, `_node`, `_meter`, `_interval`, `_node_live`, `_outage_plan`, `_advice`, `_dashboard`, `res_config_settings`, `__init__`), `wizard/td_energy_ticket_wizard.py`+`__init__`, `tools/{dashboard,forecast,sld,node_card,bus,backfill,dates}.py`, `hooks.py`, `migrations/19.0.1.1.0/*`, `data/{sld_layout.csv,energy_signals.csv,energy_sources.csv,ir_cron.xml,ir_config_parameter.xml}`, `security/*`, `neutralize.sql`, `tests/test_w1_{event,bus,node_sld,dashboard,forecast,card,outage_plan,advice,signals,backfill,security,ticket}.py`, `tests/stand/test_w1_tk.py` | M-21…M-28, API-05…API-15, R-24…R-38, 4 (права), 5, 6, AC-93…AC-105, AC-107…AC-119, AC-122…AC-145, AC-147…AC-158 (UT; AC-106 — hoot, B), ТБ-07, ТБ-08, ТБ-10, ТП-07, ТП-08 | моделі, API за схемою SPEC 7, міграція, backfill | `F3D_TEST_INSTALL=td_energy $T/run_tests.sh td_w1a /td_energy:TestW1Event` … по класах; повний регрес `$T/run_tests.sh td_w1a_full /td_energy` (142 + нові) |
| **W1-B «Фронтенд»** | `td_energy/static/src/{common,pult,node_card,generation,mobile}/**`, `static/tests/*.test.js`, `views/{td_energy_pult_views,td_energy_event_views,td_energy_node_views,td_energy_meter_views,td_energy_outage_plan_views,td_energy_advice_views,td_energy_ticket_wizard_views,res_config_settings_views}.xml`, `views/menus.xml`, `tests/{test_w1_ui,test_w1_hoot}.py` | V-22…V-34, UI-01…UI-11, 3.3, AC-106, AC-121 (hoot), AC-144 (браузерна перевірка меню; UT-частина — A), D-01…D-18; AC-120 і AC-146 — стенд (менеджер, ТК-13, ТК-18) | клієнтські дії, види, меню, hoot-набір | `F3D_TEST_INSTALL=td_energy $T/run_tests.sh td_w1b /td_energy:TestW1Ui` і `…:TestW1Hoot`; перевірка вручну `$T/serve.sh td_w1b` (десктоп + 390 px) |
| **W1-C «Міст і емулятор»** | `odoo_addons/td_genset_factory3d/{hooks.py,models/td_energy_dashboard.py,adapters/td_genset.py,data/menu_hide.xml,security/td_genset_factory3d_security.xml,views/menus.xml,tests/*}`; `services/iot_sim/{catalog/devices.yaml,catalog/signals.csv,iot_sim/models/swb.py}` + його юніт-тести `services/iot_sim/tests/unit/test_swb.py`; `odoo_addons/td_iot_sim/data/{td_sim_signal.csv,td_sim_scenario.xml}` | Частина II (M-10, M-11, V-10, V-11, ADP-11, R-14…R-16, AC-74…AC-83), SPEC 8.1 (`swb`, `pfc_step_fault`), ТБ-11, ТК-G14, ТК-G15 | міст, емулятор | `F3D_TEST_INSTALL=td_energy,td_genset,td_genset_factory3d $T/run_tests.sh td_w1c /td_genset_factory3d`; регрес моста й td_genset: `…/td_genset`; емулятор: `pytest services/iot_sim/tests/unit/test_swb.py` |

**Перетини, які воркери НЕ роблять:** `td_energy/data/energy_signals.csv` і `energy_sources.csv` — лише A; рядки емулятора для тих самих кодів — лише C (узгодження через таблицю SPEC 5.3/8.1); хуки дашборда — C наслідує `td.energy.dashboard` після злиття A (до тоді C користується `patch` у тестах); `menu_td_energy_generation` — лише B (`menus.xml`), C посилається на нього за xml-id.

### 6.2 Порядок злиття й приймання

1. **A** → `td_energy` (регрес `/td_energy` 142 + нові зелені).
2. **B** і **C** паралельно на базі A (rebase); B і C не перетинаються за файлами.
3. Інтеграція менеджером: `F3D_TEST_INSTALL=td_energy,td_bms,td_genset,td_genset_factory3d,td_iot_sim $T/run_tests.sh td_w1_full` (усі модулі), далі стенд: емулятор+збирач → `_td_backfill(days=90)` → ТК-13…ТК-18, ТК-G14/G15 (E-11: сервер — менеджер).
4. Приймання Opus: тести + `git diff --stat` (очікувано: A ≈ 2 800 рядків, B ≈ 2 000, C ≈ 700 за винятком CSV/JSON), перевірка D-xx відхилень на скріншотах Пульту й картки.

### 6.3 Оцінка обсягів по воркерах

| Воркер | Python/XML | JS/XML (OWL) | Тести | Орієнтовно |
|---|---|---|---|---|
| W1-A | ≈ 1 700 | — | ≈ 1 100 | 40 люд./год |
| W1-B | ≈ 450 (види) | ≈ 1 500 | ≈ 300 (hoot) | 40 люд./год |
| W1-C | ≈ 350 | — | ≈ 350 (+ емулятор ≈ 250) | 16 люд./год |
