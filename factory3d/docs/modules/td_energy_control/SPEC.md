# td_energy_control — специфікація (W2 «Енергетика · Керування»: модуль `td_energy_control`, плагін збирача `td_collector_energy`, емулятор; шар «Енергетика в 3D» — міст `td_energy_viewer3d`)

Версія 0.2 · 19.10.2026 (v0.1 — 18.10.2026) · стандарт `docs/DOC_STANDARD.md` · технічне рішення: [ARCHITECTURE.md](ARCHITECTURE.md) (далі ARCH: FR-46…FR-70, A-38…A-67, Q-26…Q-33, C-38…C-47, план збирання §6) · статус: збудовано (гілка `claude/td-energy-w4`), відхилення збірки — у «Журналі змін документа» в кінці файлу.
Вхід: `build/energy/GAP.md` (рішення E-01…E-11, §2 шлях керування, §6 моделі, §7 хвилі; матриця CT-01…CT-15), макет `Control.dc.html` (екран «Керування») і `Main.dc.html` (дії рекомендації «Зарядити BESS 50 кВт», «Увімкнути QS…», діалог підтвердження QS, «Скасувати», кнопка «Відкрити в 3D»).
Спирається на: `build/energy/W1_SPEC.md` і `W1_ARCH.md` (C-30…C-37; слот рекомендації M-26/R-32; групи §4.2; R-26 стани вузлів; R-33 шина; провайдер 3D `td.viewer.provider.energy`); `docs/ARCHITECTURE.md` §5, §6.4, §6.5, §6.7; `docs/modules/td_telemetry` (`td.command`, API-01…API-07, «чотири запобіжники» AC-88); `docs/modules/td_viewer3d` (M-01 контракт провайдера, R-25 точка розширення, A.12 `energy`); `docs/modules/td_genset_factory3d` (ADP-11).
Документ розкладено за модулями: `td_energy_control` (цей файл і `ARCHITECTURE.md`); міст 3D — `docs/modules/td_energy_viewer3d/` ([SPEC.md](../td_energy_viewer3d/SPEC.md): M-41, M-42, V-46, V-47, UI-23…UI-27, R-57, R-58, розд. 8.4 з R-26/VX `td_viewer3d`, AC-278…AC-293); ADP-12 (розд. 8.3) — для `td_genset_factory3d` (текст лишається тут; у `docs/modules/td_genset_factory3d/SPEC.md` перенесення — окремою правкою менеджера).

**Мова документа.** Проза, заголовки й таблиці — українською (`docs/DOC_STANDARD.md`); рядки інтерфейсу, тексти макета, повідомлення про помилки в коді й підписи в журналі (усе в «ялинках» і в `"…"` усередині коду) — українською, як у продукті (`docs/DOC_STANDARD.md`: «Рядки UI — українською в коді»). Технічні імена — англійською.

**Безпека (рамка всього документа).** Модуль керує лише електропостачанням і енергоспоживанням заводу (QS, BESS, КГУ, PFC, скидання навантажень, уставка тиску повітря, сцени освітлення/вентиляції через BMS, пробний пуск ДГУ). **Він не керує пожежною сигналізацією, спринклерами, димовидаленням, евакуаційним і аварійним освітленням, захистом людей, СКУД, захистом верстатів і життєзабезпечувальними блокуваннями** (R-60, AC-165, ТБ-12). Усі ці системи — лише входи (читання) для блокувань. Автоматика працює в збирачі/контролері, Odoo задає режими, уставки, розклад і пріоритети (E-03, E-05).

## Умовні позначення, діапазони ID, відхилення від макета

**Імена (E-09, A-23 W1).** Модулі `td_energy_control` (новий), `td_energy_viewer3d` (міст 3D, новий), `td_energy`, `td_telemetry`, `td_bms`, `td_viewer3d`, `td_genset_factory3d`, `td_iot_sim`; моделі `td.*`; поля стандартних моделей `td_*`; групи й меню — як у W1. Параметри `ir.config_parameter` модуля — `td.energy_control.<param>` (конвенція `docs/ARCHITECTURE.md` §5: `td.<module>.<param>`; відмінність від рядка 13 таблиці GAP §6 `td.energy.control_enabled` — рішення A-38). Маршрути `/f3d/*` і коди наявних сигналів **не змінюються**; нові HTTP-маршрути колектора — `/td/energy/automation/*` (GAP §2.3). Python-пакет плагіна збирача — `td_collector_energy` (pip `td-collector-energy`, entry points у групі `factory3d_collector.plugins`; група й пакет `f3d_collector` лишаються за RENAME §2.4).

**Діапазони ID** (нумерація блоку «Енергетика» продовжується після W1; поза таблицями ID завжди з модулем: `td_energy_control M-33`, `td_viewer3d R-26`):

| Тип | W1 закінчив на | W2 бере | Де діє |
|---|---|---|---|
| FR | FR-45 (`td_energy`) | FR-46…FR-68 | `td_energy_control`, `td_energy_viewer3d`, збирач, емулятор |
| M | M-28 | M-29…M-42 | M-29…M-40 `td_energy_control`; M-41, M-42 `td_energy_viewer3d` |
| V | V-34 | V-35…V-47 | `td_energy_control` (V-35…V-45), `td_energy_viewer3d` (V-46, V-47) |
| UI | UI-11 | UI-12…UI-28 | клієнтські компоненти |
| API | API-15 | API-16…API-28 | ORM-RPC (16…23, 27, 28), HTTP (24, 25), інтент збирача (26) |
| R | R-38 | R-39…R-67 | алгоритми й правила (R-39…R-66 — `td_energy_control`, шар 3D, збирач, емулятор; R-67 — міст ДГУ) |
| AC | AC-158 | AC-159…AC-310 | `td_energy_control`, плагін, ядро збирача, емулятор, міст 3D, стенд (розд. 12; ADP-12 — AC-275…AC-277, `td_viewer3d` R-26 — AC-278…AC-281) |
| ТК / ТБ / ТП | ТК-18 / ТБ-10 / ТП-09 | ТК-19…ТК-28 / ТБ-11…ТБ-15 / ТП-10…ТП-12 | стенд, безпека, продуктивність (розд. 13) |
| A (рішення автора) | A-37 | A-38…A-62 (+A-63 міст ДГУ; A-64…A-67 — рішення збірки) | розд. 15 |
| Q | Q-25 | Q-26…Q-33 | ARCH §5, розд. 15 |
| D (відхилення від макета) | D-18 | D-19…D-49 | нижче |
| C (контракти) | C-37 | C-38…C-47 | ARCH §2.1 |
| `td_genset_factory3d` | FR-21, M-11, ADP-11, R-16, AC-83, A-23 | FR-69, ADP-12, R-67, AC-275…AC-277, A-63 | міст ДГУ (розд. 8.3, R-67) |
| `td_viewer3d` | FR-44, R-25, AC-67, X-92 | FR-70, R-26 (VX-01…VX-05), AC-278…AC-281, X-93 | розд. 8.4 |

Уточнення нумерації: AC для `td_genset_factory3d` (ADP-12) і `td_viewer3d` (R-26) взято зі наскрізного діапазону W2 (AC-275…AC-281), щоб не перетинатися з AC-74…AC-83 моста й AC-01…AC-67 переглядача. Разом **AC-159…AC-308 = 150 критеріїв** у початковій редакції; AC-309 і AC-310 додано за D-46 (дистанційне перемикання) — разом 152; FR-69 (міст ДГУ) і FR-70 (розширення переглядача) — додаткові вимоги (ARCH §1.3).

Позначення: UT — юніт-тест `odoo.tests` (`TransactionCase`/`HttpCase`); UT-JS — hoot-тест (`web.assets_unit_tests`); UT-PY — pytest збирача/плагіна/емулятора (без Odoo); TC — стенд (емулятор + збирач + Odoo); MAN — ручна перевірка (скріншот, браузер). `req`=`required=True`, `idx`=`index=True`. Усі `Datetime` — UTC naive; «Київ» — `Europe/Kyiv` (`tools/dates.py` `td_energy`). Рядки UI — українською в коді. Класи команд A/B — розд. 9 R-39.

### Відхилення від макета (D-xx)

| ID | Де в макеті | Що в реалізації | Чому |
|---|---|---|---|
| D-19 | Control: журнал, виконавець «ви» | Ім'я користувача; для не-людей — «автоматика», «сценарій «Пік»», «розклад», «скасування»; чип результату: «виконано», «створено», «збережено, очікує збирач», «не виконано», «заблоковано», «скасовано» | Кілька користувачів; бізнес-журнал із джерелами `origin` (R-56) |
| D-20 | Control: перемикач сценарію змінюється одним кліком, тост «записано в журнал» | Увімкнення/вимкнення — клас B: діалог (prepare/confirm), потім стан «Очікує застосування» до підтвердження збирачем (`applied_version`); перемикач показує стан Odoo, чип — стан рушія | E-06; Odoo не виконує автоматику — істину про стан дає збирач |
| D-21 | Control: усі плитки команд доступні всім | Права E-06: клас A — «Енергетик»; клас B — «Головний енергетик» або друге підтвердження іншим «Енергетиком»; недоступні дії — `disabled` з поясненням «потрібне друге підтвердження» | E-06 |
| D-22 | Control: діалог — усі перевірки «гаразд» | Перевірки обчислюються: `гаразд` / `не виконано` / `немає даних`; жорстка перевірка «не виконано» або «немає даних» (fail-closed) блокує «Виконати» з причиною; м'які — попередження | R-41; hard-блокування лише в збирачі, Odoo — підказка |
| D-23 | Control: «Розклад на сьогодні» — лише перегляд; вертикаль «зараз» на 59,7 % | Перегляд в OWL; план (`source='plan'`) будується з прогнозу W1 R-28; ручні слоти (`manual`) — стандартні list/form для «Головного енергетика»; «зараз» — поточний час Києва | Макет без редагування; E-06 (зміна розкладу — клас B) |
| D-24 | Control: кнопки ↑/↓ одразу змінюють порядок | Режим «Змінити порядок»: ↑/↓ локально, «Зберегти порядок» — одна дія `shed_reorder` (клас B), «Скасувати» — відкат | Одна дія журналу замість N; клас B |
| D-25 | Control: пріоритети — п'ять навантажень із фіксованими кВт | Рядки `td.energy.shed.item`; вузли: `CHARGING`, `RV-ALL`, `DRY-1`, `COMPRESSOR` («Компресор 2 (резервний)» → єдиний вузол «Компресорна 2 × GA 37»), `LP-1` («Освітлення складів»); `kw_reducible` — довідник, що налаштовується (сид 48/60/17/37/12 = 174), поруч фактичний `p_now` | У даних немає окремого вузла «Компресор 2» і «Освітлення складів»; встановлені потужності W0 (`CHARGING` 13,5 кВт, `LP-1` 6,3 кВт) не збігаються з макетом, тому `kw_reducible` — оцінка, а не обмеження |
| D-26 | Control: «Не відключаються ніколи» — статичний текст | Динамічний список: вузли `is_critical`, яких немає серед активних пріоритетів, + постійний перелік (аспірація під час роботи верстатів, ІТ і зв'язок, охорона, пожежна автоматика, аварійне освітлення — R-60). Критичні вузли, присутні в пріоритетах (компресорна, склади), скидаються лише частково або за умовою і лише в «Зрізанні піку», не при резервному живленні (R-49, R-51) | Дані W0 позначають компресорну й щити освітлення `is_critical` (живляться від ДГУ), а макет скидає «Компресор 2» і «Освітлення складів» |
| D-27 | Control: чипи статусу сценаріїв | Текст чипа складається в Odoo за шаблоном (R-43) з фактів рушія; приклади макета відтворюються: «Чергування · запас 402 кВт», «Активний · заряд BESS 26 кВт», «Збій: PFC-2 ступінь 3» (з W1 `fault_step`), «Наступний запуск о 23:00», «Готовий · паливо 78 %» (з `_td_genset_summary`), «Вимкнено» | Мова й факти — в Odoo; рушій віддає лише числа |
| D-28 | Control: чип «Контролер ГРЩ і збирач на зв'язку · 14:20» | Три стани: «на зв'язку · HH:MM», «не на зв'язку · {вік}» (heartbeat старший за `td.energy_control.heartbeat_stale_s`), «автоматику призупинено» (`automation_enabled=false` або рушій у `hold`) | CT-01 |
| D-29 | Main: «Зарядити BESS 50 кВт» одразу виконує команду | Та сама послідовність prepare → діалог → confirm; для класу A діалог короткий (Enter підтверджує) | Control: «кожна ручна команда проходить блокування й підтвердження» |
| D-30 | Main: банер «Виконано … Скасувати» | Скасування — окрема дія `undo` (`origin='undo'`), доступна `td.energy_control.undo_window_min` (15 хв); банер будується з останньої виконаної дії рекомендації (R-55 п.4) | Журнал і права для скасування |
| D-31 | Main: тост «Команду надіслано: BESS заряджається…» | Тост за станами: «Надіслано» → «Виконується» → «Виконано»/«Не виконано: {причина}» (до `verify_timeout_s`) | Реальне підтвердження пристроєм |
| D-32 | Control: «Тест ДГУ без навантаження · 10 хв» | Виконується `td_genset` (`_test_start('idle')`, ADP-12); тривалість — `td.genset.config.test_minutes` (на стенді 10); у журналі «Енергетики» — «прийнято td_genset» + посилання; підтвердження пуску — власна стейт-машина `td_genset` | E-01: `td_genset` — окремий продукт |
| D-33 | Control: «КГУ … вийде на 400 кВт за 6 хв» | Число — параметр `chp_ramp_min` (6); емулятор за замовчуванням виходить за 60 с (прапор світу `chp_start_s=360` дає 6 хв) | Модель W0 емулятора |
| D-34 | Control: перевірки КГУ «Тиск газу 2,1 бар», «Охолодження й вентиляція готові», «Дозвіл оператора КГУ» | Сигнали `energy_control/chp/gas_bar`, `…/permit` (регістри контролера) і `infra/chp/state` (готовність: `stop`, не `cooling`); окремого сигналу «вентиляція КГУ» немає — перевірка входить у `chp_ready` | У даних немає окремих сигналів |
| D-35 | Control: «Освітленість проходів ≥ 75 лк», «CO₂ 620 ppm < 1000» | М'які перевірки `aisle_lux_ge`, `co2_lt`: немає сигналу → «немає даних» без блокування | Сигнали BMS є не на кожному об'єкті |
| D-36 | Control: «Мінімальний тиск споживачів 6,2 бар» | Регістр `energy_control/air/min_consumer_bar` (емулятор 6,2; на об'єкті — параметр контролера) | Єдине джерело правди для hard-перевірки в збирачі |
| D-37 | Main: тост «Відкривається «Переглядач» із шаром «Енергетика»» | Реальний перехід у `f3d_viewer.action`: режим розфарбовування «Електромережа: стан вузлів», маркери тривог, шари GLB `energy`, `backup`; вузол підсвічується й вибирається (FR-62…FR-64) | Вимога W2 |
| D-38 | Main: у панелі вузла QS/BESS кнопки «Увімкнути QS…», «Зарядити 50 кВт» | Кнопки реєструє `td_energy_control` через `registry.category("td_energy.node_actions")`; для замкненого QS — «Вимкнути QS…», для заряду BESS — «Зупинити заряд» | C-46; симетричні дії |
| D-39 | Control: BESS 100 кВт / 200 кВт·год | Параметр сценарію `bess_max_kw` (сид 100) обмежує автоматику; емулятор технічно здатний на 200 кВт (`BESS_KW_MAX`); ручна команда `bess_discharge` — до `bess_max_kw` | Макет і модель W0 розходяться |
| D-40 | Control: «Нічний режим · вентиляція RoofVent на 30 %» | Дія — режим BMS «Знижена вентиляція» (`VEL`) і уставка ночі `sp_night` для кожної установки `kind='roofvent'`; «30 %» — довідковий текст чипа з параметра `vent_pct`; окремого сигналу «обмеження вентилятора, %» у `td_bms` немає | Те, що вміє `td_bms` |
| D-41 | Control: «ціна газу 19,80 ₴/м³» | Параметр сценарію `gas_price_uah_m3` (19,80); ціна мережі — зона тарифу `td.energy.tariff` (W1); `td.energy.price` (W3) підмінить параметр без зміни рушія | Q-31 |
| D-42 | Control: рядок журналу «Заявка ТО · PFC-2 … · автоматика · створено» | Журнал об'єднує `td.energy.action` і події `td.energy.event` (`kind in ('pfc','control')`) з посиланням на заявку ТО; результат «створено» — якщо є `maintenance_request_id` | R-56 п.2 |
| D-43 | Control: нічого про друге підтвердження | Банер «Очікує другого підтвердження: {дія} — {хто готував}» і кнопка «Підтвердити (2/2)» для іншого «Енергетика»; сповіщення через `mail.activity`/шину | E-06 |
| D-44 | Control: меню «Налаштування» вгорі | У W2 — підрозділ «Керування» в меню «Енергетика» (seq 8) і «Журнал команд» (seq 9, стандартний list); налаштування — блок у `res.config.settings` | Меню W1 §3.3 |
| D-45 | Рішення менеджера (скасовує R-66/AC-232/A-51 у початковій редакції) | **Архівних таблиць немає.** Деінсталяція `td_energy_control` видаляє його дані як у будь-якого модуля Odoo: `td.energy.action` (журнал), сценарії, пріоритети, слоти, блокування, види команд, сигнали/джерела `energy_control`, крони, параметри. `_restore_archive` і таблиці `td_energy_*_archive` не створюються; `uninstall_hook` лише скидає прапори й публікує збирачу порожню конфігурацію | Простіше й передбачуваніше; журнал команд — бізнес-журнал модуля, а не дані інших модулів (аудит — резервна копія БД) |
| D-46 | Рішення менеджера (Q-27) | Параметр `td.energy_control.remote_switching_enabled` (**default `False`**): «Дистанційне перемикання комутаційних апаратів дозволено». Поки він `False`, команди дистанційного перемикання — `qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test` (поле `remote_gated=True` виду команди, M-31) — **відхиляються** з `UserError("Дистанційне перемикання вимкнено: td.energy_control.remote_switching_enabled. Зверніться до адміністратора.")` у `prepare`, `confirm` і `confirm_second`; плитка `enabled=false` з тією самою причиною; прапор публікується збирачу в API-24 `flags.remote_switching_enabled`, плагін додатково відмовляє (`rejected`). Решта команд (заряд/зупинка BESS, `chp_stop`, сцени BMS, уставка повітря, конфігурація) не зачіпаються. Demo-дані (`demo/ir_config_parameter_demo.xml`) і `hooks._td_enable_stand` ставлять `True`; `neutralize.sql` повертає `False` | Регламент об'єкта (Q-27) не підтверджений: дистанційне перемикання окремо від `write_enabled` |
| D-47 | Рішення менеджера (змінює заморожений API-24, C-39) | Збирач не отримує EN-DERIVED-значення (їх обчислює Odoo), а автоматика має працювати без Odoo (E-03). API-24 віддає блок `derived` — формули для входів `inputs`, які обчислює Odoo: `energy/totals/p_now`, `energy/sections/S1/p_kw`, `energy/sections/S2/p_kw` (сума `energy/lines/<код>/p_now` за лініями; секція — `line.section` або секція батька), `infra/ats/src1_ok` (`ge`: `infra/ats/src1_state` ≥ 1), `infra/totals/grid_kw`, `infra/totals/export_kw` (Q1/Q2 `energy/cells/Q{1,2}/p_now`, острів `infra/ats/position = 3` → 0), `infra/totals/pv_now` (сума `infra/pv/PV-INV-n/p_kw` з нижньою межею терма 0). Блок входить у канонічний JSON, `config_version` і ETag (R-43). Семантика плагіна: значення обчислюється з `LiveCache`; будь-який терм відсутній або старший за `max_age_s` — похідний вхід відсутній (fail-closed, як в Odoo); див. §7.3 п.8, R-41 п.2, R-44 п.3 | Рушій не залежить від доступності Odoo; формули — ті самі сирі сигнали й знаки, що в `td_energy` (R-06, R-14) |
| D-48 | Рішення менеджера | Пожежна тривога (`fire_state = alarm`) **не** переводить рушій у `hold`: режим лишається `auto`, блокуються лише записи ресурсів `vent`/`light` (сценарій `night` → `warn`), подія `interlock` (R-44 п.8 вірний; AC-244 виправлено) | Решта ресурсів (BESS, КГУ, QS, PFC) від пожежної тривоги не залежать (R-60) |
| D-49 | Рішення менеджера | Сценарій `night` не потребує `remote`: цілі BMS ідуть не через контролер ГРЩ (R-48 п.6 вірний); зі списку критичних входів R-44 п.3 `night` прибрано (критичний вхід `remote` — лише в `pfc`) | Місцевий режим контролера ГРЩ не повинен зупиняти нічний режим BMS |

---

# ЧАСТИНА I. `td_energy_control` (новий модуль)

## 0. Дерево файлів

Власники: **A** — бекенд `td_energy_control` + адаптер ДГУ, **B** — фронтенд `td_energy_control` + правки клієнта `td_energy`, **C** — рушій збирача, ядро збирача (розширення контексту плагіна), емулятор, **D** — міст 3D `td_energy_viewer3d` + розширення `td_viewer3d` (ARCH §6). Файли без літери — менеджер (каркас, розд. 6.0 ARCH).

```
odoo_addons/td_energy_control/
├── __manifest__.py                       (менеджер) розд. 1
├── __init__.py                           (менеджер) from . import models, controllers; from .hooks import post_init_hook, uninstall_hook
├── hooks.py                              A  post_init_hook: _load_sources_signals, _seed_defaults, _bump_config; uninstall_hook (архівних таблиць немає, D-45)
├── models/
│   ├── __init__.py                       A
│   ├── td_source_signal.py               A  M-38 (selection_add `energy_ctl`, `energy_control`; реєстрація валідаторів; вид події `control`)
│   ├── td_energy_scenario.py             A  M-29
│   ├── td_energy_shed_item.py            A  M-30
│   ├── td_energy_command_kind.py         A  M-31
│   ├── td_energy_interlock.py            A  M-32
│   ├── td_energy_action.py               A  M-33 (журнал + потік prepare/confirm/undo)
│   ├── td_energy_schedule_slot.py        A  M-34
│   ├── td_energy_control.py              A  M-35 (AbstractModel, API екрана)
│   ├── td_energy_advice.py               A  M-36 (правила R-55)
│   ├── td_command.py                     A  M-37
│   ├── td_energy_control_state.py        A  M-39
│   └── res_config_settings.py            A  M-40
├── controllers/{__init__.py, automation.py}   A  API-24, API-25
├── tools/
│   ├── __init__.py                       A
│   ├── interlocks.py                     A  R-41 (чисті перевірки)
│   ├── kinds.py                          A  R-42 (параметри, схеми, текст діалогу)
│   ├── config_builder.py                 A  R-43 (JSON конфігу, канонічний вигляд, ETag)
│   ├── status_text.py                    A  R-43 п.5 (чипи сценаріїв)
│   ├── planner.py                        A  R-54 (план дня)
│   ├── journal.py                        A  R-56
│   ├── bus.py                            A  шина `td_energy_control` (A-41)
│   └── genset_link.py                    A  м'який виклик ADP-12 (розд. 8.3)
├── data/
│   ├── ir_config_parameter.xml           A  розд. 5.1
│   ├── ir_cron.xml                       A  розд. 6
│   ├── td_energy_scenario_data.xml       A  6 сценаріїв (розд. 5.2)
│   ├── td_energy_command_kind_data.xml   A  види команд (розд. 5.3)
│   ├── td_energy_interlock_data.xml      A  реєстр блокувань (розд. 5.4)
│   ├── td_energy_shed_item_data.xml      A  5 пріоритетів (розд. 5.5)
│   ├── energy_control_sources.csv        A  2 джерела (розд. 5.6)
│   ├── energy_control_signals.csv        A  сигнали керування (розд. 5.6)
│   └── neutralize.sql                    A
├── security/{ir.model.access.csv, td_energy_control_security.xml}   A  розд. 4 (нових груп немає)
├── static/src/control/{control.js, control.xml, scenarios.js, scenarios.xml, shed.js, shed.xml, commands.js, commands.xml,
│                        confirm_dialog.js, confirm_dialog.xml, params_dialog.js, params_dialog.xml, bus.js, schedule.js, schedule.xml, journal.js, journal.xml, control.scss}   B  UI-12…UI-20
├── static/src/handlers/{advice_handler.js, node_actions.js, done_banner.js}   B  UI-21, UI-22
├── static/tests/{control.test.js, confirm_dialog.test.js, advice_handler.test.js, node_actions.test.js, fixtures/contracts.js}   B  hoot
├── views/
│   ├── td_energy_control_views.xml       B  V-35 (client action), V-36 (стан керування)
│   ├── td_energy_scenario_views.xml      B  V-37
│   ├── td_energy_shed_item_views.xml     B  V-38
│   ├── td_energy_command_kind_views.xml  B  V-39
│   ├── td_energy_interlock_views.xml     B  V-40
│   ├── td_energy_action_views.xml        B  V-41
│   ├── td_energy_schedule_slot_views.xml B  V-42
│   ├── td_command_views.xml              B  V-43 (поле «Дія енергетики» у формі команди)
│   ├── res_config_settings_views.xml     B  V-44
│   └── menus.xml                         B  V-45
└── tests/
    ├── test_scenario.py, test_shed.py, test_kinds.py, test_interlocks.py, test_action_flow.py, test_action_second.py,
    │   test_undo.py, test_journal.py, test_schedule.py, test_advice_rules.py, test_config_api.py, test_state_api.py,
    │   test_intent_payload.py, test_security.py, test_source_signal.py, test_hooks.py, test_neutralize.py,
    │   test_crons.py, test_genset_exec.py, common.py     A
    ├── test_ui.py, test_hoot.py          B  (HttpCase: клієнтська дія й меню; hoot-набір за зразком `td_energy/tests/test_w1_hoot.py`)
    └── stand/test_tk_control.py          A  ТК-19…ТК-28 (pytest проти стенда)

odoo_addons/td_energy_viewer3d/            D  міст 3D → [../td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §0 (разом із файлами `td_viewer3d` для VX-01…VX-05)

odoo_addons/td_genset_factory3d/adapters/td_genset.py     A  +ADP-12 (розд. 8.3), tests/test_adp12.py   A

odoo_addons/td_energy/static/src/            B  мінімальні правки клієнта W1 (розд. 3.4)
├── common/actions.js                                B  deep-link у 3D (C-45), реєстри
├── pult/{sld.js, sld.xml, pult.xml, pult.js}        B  реєстр дій панелі вузла (C-46), банер «Виконано»
└── tests/…                                          B  нові hoot-тести td_energy: `static/tests/control_hooks.test.js`

services/collector_plugins/td_collector_energy/       C  розд. 8.1
services/collector/collector/{plugins/base.py, core/app.py, core/scheduler.py, core/commands.py, core/errors.py, core/odoo_client.py, core/live.py}   C  розд. 8.1.2 (C-40)
services/collector/{requirements-extra.txt}           C
services/iot_sim/iot_sim/{models/{swb,bess,chp,compressor,meter,pv}.py, protocols/modbus_maps/{__init__,swbctl}.py}   C  розд. 8.2
services/iot_sim/{catalog/signals.csv, tests/unit/{test_swbctl.py, test_control_models.py}}                           C
odoo_addons/td_iot_sim/data/{td_sim_signal.csv, td_sim_scenario.xml}                C
```

## 1. Маніфест `td_energy_control` (дельта від шаблону)

- `name` «Енергетика — Керування»; `summary` «Сценарії автоматики, пріоритети скидання, ручні команди з блокуваннями й підтвердженням, розклад і журнал»; `version` `19.0.1.0.0`; `author` `ToDo`; `license` `LGPL-3`; `category` `Manufacturing/Manufacturing`; `application` `False`; `installable` `True`; `auto_install` `False`.
- `depends`: `td_energy` (≥ 19.0.1.1.0, W1), `td_telemetry` (`td.command`, збирач), `td_bms` (цілі нічного режиму й сцен; `depends` td_telemetry, web — легкий). Необов'язкові (м'яка залежність через `self.env.get(...)`/`importlib`): `td_genset_factory3d` (тест ДГУ, ADP-12), `td_viewer3d` (не потрібен: 3D — окремий міст).
- `data` (порядок): `security/td_energy_control_security.xml`, `security/ir.model.access.csv`, `data/ir_config_parameter.xml`, `data/td_energy_interlock_data.xml`, `data/td_energy_command_kind_data.xml`, `data/td_energy_scenario_data.xml`, `data/td_energy_shed_item_data.xml`, `data/ir_cron.xml`, `views/td_energy_scenario_views.xml`, `views/td_energy_shed_item_views.xml`, `views/td_energy_command_kind_views.xml`, `views/td_energy_interlock_views.xml`, `views/td_energy_action_views.xml`, `views/td_energy_schedule_slot_views.xml`, `views/td_command_views.xml`, `views/res_config_settings_views.xml`, `views/td_energy_control_views.xml` (клієнтська дія), `views/menus.xml` (останнім).
- `assets`: `web.assets_backend`: `td_energy_control/static/src/control/**`, `td_energy_control/static/src/handlers/**`; `web.assets_unit_tests`: `td_energy_control/static/tests/**/*.js`.
- `post_init_hook`: `hooks.post_init_hook` (ідемпотентний): `_load_sources_signals(env)` (розд. 5.6), `_seed_defaults(env)` (розд. 5.2…5.5 — лише якщо записів немає), `_bump_config(env)` (`config_version`+1). `uninstall_hook`: **архівних таблиць немає** (D-45) — модуль видаляється разом зі своїми даними, як будь-який модуль Odoo; гак видаляє сигнали й джерела `module='energy_control'` та `type='energy_ctl'` (зокрема залежні записи `td.command` `origin='energy'`), крон-завдання, параметри `td.energy_control.*`, скидає `write_enabled`/`automation_enabled`/`remote_switching_enabled` у `False` і публікує збирачу порожню конфігурацію (A-51).
- Зовнішніх Python-залежностей в Odoo-частини немає. Збирач: `td-collector-energy` (розд. 8.1).

## 2. Моделі

Усі ідентифікатори моделей — `td.energy.*` (простір W1 `td.energy.*` лишається за `td_energy`; нові назви не перетинаються з W1: `scenario`, `shed.item`, `command.kind`, `interlock`, `action`, `schedule.slot`, `control`, `control.state`). Читання моделей — `group_td_energy_user`; усі зміни бізнес-даних — лише через методи моделей під `sudo()` після перевірки прав (розд. 4), прямий `write/create/unlink` з клієнта заборонено ACL (user/manager мають лише `read`), окрім випадків, указаних у таблицях.

### M-29 `td.energy.scenario` — сценарій автоматики (FR-46, FR-47, R-43, R-45…R-50)

`_name = "td.energy.scenario"`, `_description = "Енергетика: сценарій автоматики"`, `_order = "sequence, id"`. Рівно 6 записів, створюються даними (розд. 5.2); `create`/`unlink` для не-адміністратора заборонені (`AccessError`).

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Selection | `peak`/«Зрізання піку», `self`/«Самоспоживання СЕС», `pfc`/«Компенсація реактивної потужності», `night`/«Нічний режим (BMS)», `backup`/«Резервне живлення», `chp`/«КГУ за графіком і ціною»; req, idx, readonly; `UNIQUE(code)` |
| `name` | Char | size=64, req (назва картки = мітка значення `code`) |
| `description` | Text | req; тексти карток макета (розд. 5.2) |
| `sequence` | Integer | default 10 (порядок карток: peak 10, self 20, pfc 30, night 40, backup 50, chp 60) |
| `enabled` | Boolean | default за сидом (peak ✓, self ✗, pfc ✓, night ✓, backup ✓, chp ✗ — стан макета); змінюється лише дією `scenario_toggle` (контекст `td_energy_control_internal`) |
| `params` | Json | default `PARAM_DEFAULTS[code]`; валідація `@api.constrains("params")` за таблицею нижче → `ValidationError("Сценарій {name}: параметр {key} — {помилка}.")`; невідомі ключі відхиляються |
| `params_text` | Text | compute/inverse (JSON, як `td.command.payload_text`), лише для форми адміністратора |
| `config_version` | Integer | readonly: значення `td.energy.control.state.config_version` на момент останньої зміни `enabled`/`params` |
| `applied` | Boolean | compute (не зберігається): `state.applied_version >= config_version` |
| `engine_state` | Selection | `unknown`/«Немає даних» (default), `off`/«Вимкнено», `armed`/«Чергування», `active`/«Активний», `warn`/«Збій»; readonly; пише API-25 |
| `engine_facts` | Json | readonly: числа від рушія (`margin_kw`, `bess_kw`, `export_kw`, `reason`, `next_run`, …) |
| `engine_ts` | Datetime | readonly: час останнього звіту рушія |
| `state_signal_id` | Many2one `td.signal` | readonly, `energy_control/auto/<code>/state` |
| `state_kind` | Selection | compute: `act`/`arm`/`warn`/`off` (колір чипа макета; R-43 п.5) |
| `state_text` | Char | compute: текст чипа за шаблоном (R-43 п.5) |
| `changed_by`, `changed_at` | Many2one `res.users` / Datetime | readonly |

**Параметри сценаріїв** (`params`; тип, межі «мін…макс», сид; **«межа коду»** — значення, яке збирач не перевищує незалежно від конфігу, R-44 п.6):

| Сценарій | Ключ | Тип, межі | Сид | Примітка |
|---|---|---|---|---|
| `peak` | `limit_kw` | float 100…2000 | 760 | уставка імпорту (макет: «уставка 760 кВт · 95 %» = 95 % від `contract_kw` 800); відсоток у чипі = `limit_kw / contract_kw` |
| | `activate_margin_kw` | float 0…200 | 30 | рушій активується, коли прогноз 15 хв ≥ `limit_kw − activate_margin_kw` або миттєвий імпорт ≥ `limit_kw` |
| | `margin_kw` | float 0…100 | 20 | миттєва ціль `limit_kw − margin_kw` |
| | `release_margin_kw` | float 0…200 | 40 | |
| | `release_hold_s` | int 30…1800 | 180 | |
| | `stage_delay_s` | int 10…600 | 60 | пауза між ступенями BESS → КГУ → скидання |
| | `bess_max_kw` | float 0…200 | 100 | межа коду 200 (D-39) |
| | `bess_min_soc_pct` | float 10…90 | 30 | ефективна підлога = `max(це, td.energy.bess_reserve_pct)` |
| | `chp_allowed`, `shed_allowed` | bool | true, true | ступені 2 і 3 |
| `self` | `export_max_kw` | float 0…100 | 20 | «експорт ≤ 20 кВт» |
| | `export_deadband_kw` | float 0…50 | 5 | |
| | `bess_target_soc_pct` | float 50…100 | 95 | «BESS до 95 %» |
| | `bess_max_kw` | float 0…200 | 100 | |
| | `curtail_pv` | bool | true | «далі обмеження інверторів» |
| | `curtail_delay_s`, `restore_hold_s` | int 10…600 | 60, 120 | |
| `pfc` | — | — | — | уставка cos φ береться з `td.energy.cos_phi_target` (E-10, одна група налаштувань) і додається в `scenarios.pfc.params.cos_target` конфігу API-24; сценарій лише вмикає автоматичний режим контролера (R-47); чип показує «ціль cos φ 0,95», «крок 35 квар» (з `pfc_step_kvar` вузла) |
| `night` | `from`, `to` | рядок `HH:MM` | `23:00`, `06:30` | локальний час Києва; вікно може перетинати північ |
| | `days` | list[int 1…7] | `[1..7]` | дні, з яких **починається** вікно |
| | `vent_mode`, `day_vent_mode` | рядок із `td_bms.tools.hvac.MODE_LABELS` | `VEL`, `VE` | режими BMS (D-40) |
| | `vent_pct` | int 10…100 | 30 | довідково для чипа «RoofVent 30 %» |
| | `light_scene_number`, `light_scene_day_number` | int 1…16 | 1, 2 | номери `td.bms.light.scene.number` (черговий/робочий) |
| | `heat_setpoint_c` | float 5…30 | 16.0 | запис у `sp_night_signal_id` установок |
| `backup` | `genset_capacity_kw` | float 50…5000 | 507 | `p_inst_kw` вузла `GENSET` |
| | `critical_kw` | float 0…5000 | 180 | довідково: «критичні 180 кВт» |
| | `restore_delay_s` | int 30…1800 | 120 | стабільна мережа перед відновленням |
| `chp` | `min_run_h` | float 0.5…24 | 2.0 | «мін. робота 2 год» |
| | `min_off_min` | int 0…240 | 30 | |
| | `gas_price_uah_m3` | float 0…200 | 19.80 | D-41 |
| | `gas_m3_per_kwh` | float 0.1…1.0 | 0.25 | 199 м³/год ÷ 800 кВт (емулятор R-12) |
| | `price_margin_uah_kwh` | float 0…50 | 0.5 | |
| | `use_slots` | bool | true | пуск у слотах `resource='chp'`, `executes=True` |
| | `ramp_min` | int 1…30 | 6 | довідково для діалогу (D-33) |

Методи: `_td_apply_change(vals, action)` (internal, `sudo`, контекст `td_energy_control_internal`): записує `enabled`/`params`, `changed_by/at`, `config_version = state.bump()`; `write()` без контексту й не від `base.group_system` → `AccessError("Зміна сценарію можлива лише дією керування (клас B).")`; `_td_engine_update(item)` (API-25): оновлює `engine_*` (ігнорує звіт із `config_version_applied` меншою за поточну для `enabled`); `_td_state_text()` (R-43 п.5).

### M-30 `td.energy.shed.item` — пріоритет скидання навантаження (FR-48, R-51)

`_name = "td.energy.shed.item"`, `_description = "Енергетика: пріоритет скидання"`, `_order = "sequence, id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `sequence` | Integer | req, default 10; порядок = пріоритет (менше — скидається першим) |
| `name` | Char | size=96, req («Зарядна станція навантажувачів») |
| `node_id` | Many2one `td.energy.node` | req, ondelete restrict, domain `[('kind','=','consumer')]` |
| `action` | Selection | `off`/«Вимкнути», `reduce`/«Знизити», `pause`/«Пауза», `defer`/«Відкласти»; req |
| `param_value` | Float | `reduce`: 1…99 (%), `pause`/`defer`: 1…120 (хв), `off`: 0 |
| `kw_reducible` | Float | ≥ 0, кВт, що знімаються (сид макета) |
| `condition` | Selection | `none`/«Без умов» (default), `air_pressure_min`/«Тиск повітря не нижче уставки», `no_active_cycle`/«Без втрати циклу» |
| `condition_value` | Float | для `air_pressure_min` — бар (6,5) |
| `how` | Char | compute: «відкласти заряд до 30 хв» / «знизити до 70 %» / «пауза до 20 хв, без втрати циклу» / «вимкнути, тиск ≥ 6,5 бар» / «знизити до 50 %» (шаблони за `action`, `param_value`, `condition`) |
| `signal_id` | Many2one `td.signal` | domain `module='energy_control'`, `energy_control/shed/<node.code>/limit_pct`; req, якщо `active` |
| `active` | Boolean | default True |
| `p_now_kw` | Float | compute (не зберігається): `node_id.p_now` (якщо сигнал свіжий) |

Обмеження: (1) `UNIQUE(node_id) WHERE active` (частковий індекс у `init()`); (2) вузол `is_critical` допускається лише для часткового або умовного скидання: `action='reduce'` або `condition != 'none'`; інакше `ValidationError("Вузол {code} критичний: скидання лише часткове або за умовою.")` (елемент отримує `critical=True` у конфігу й пропускається при резервному живленні, R-49); (3) вузол із `workcenter_id` і `condition != 'no_active_cycle'` → `ValidationError("Вузол {code} пов'язаний із робочим центром: потрібна умова «Без втрати циклу».")`; (4) вузол, код якого входить у `NEVER_SHED_CODES` (константа `tools/kinds.py`; сид порожній, розширюється кодом) — заборона; (5) `kw_reducible` — довідкова оцінка (сид макета: 48/60/17/37/12), може перевищувати `p_inst_kw` вузла (дані W0: `CHARGING` 13,5 кВт, `LP-1` 6,3 кВт проти макета) — у формі лише попередження, не помилка; реальний ефект видно за `p_now`. Зміна порядку — лише дією `shed_reorder` (API-17, `params={"order":[id,…]}`, клас B). Склад і параметри рядків (створення, видалення, `action`, `param_value`, `kw_reducible`, `condition`) редагує лише `group_td_energy_chief` у списку V-38; `create/write/unlink` для рядків із полями-налаштуваннями автоматично створює запис `td.energy.action` (`origin='config'`, `kind_code='shed_edit'`, `cls='B'`, `state='done'`, `confirmed_by=uid`) і `state.bump()`; для не-chief — `AccessError`.

### M-31 `td.energy.command.kind` — вид команди (FR-49, FR-50, R-39, R-42)

`_name = "td.energy.command.kind"`, `_description = "Енергетика: вид команди"`, `_order = "sequence, id"`. Дані (розд. 5.3), редагує лише адміністратор (поля `cls`, `checks`, `executor`, `resource` — `readonly` у формі решти ролей).

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char | size=32, req, idx, `UNIQUE`; `[a-z0-9_]+` |
| `name` | Char | size=96, req (заголовок плитки: «Заряд BESS 50 кВт» — шаблон із `{power_kw}`) |
| `sub_template` | Char | size=128 («до {until} або {soc_limit_pct} %») |
| `sequence` | Integer | |
| `tile` | Boolean | плитка на екрані (8 з макета) |
| `cls` | Selection | `A`/`B`, req (R-39) |
| `executor` | Selection | `intent`/«Збирач (інтент)», `config`/«Конфігурація Odoo», `genset`/«ДГУ (td_genset)», req |
| `resource` | Selection | `bess`, `qs`, `chp`, `pfc`, `air`, `light`, `vent`, `genset`, `config`; req (ключ арбітражу, R-44 п.4) |
| `params_schema` | Json | список `{"name","label","type":"float\|int\|time\|enum\|bool","min","max","default","unit","choices"}` (R-42 п.1) |
| `checks` | Json | упорядкований список `{"code": "<interlock.code>", "soft": bool}`; `hard` визначає реєстр M-32, `soft` може лише послабити |
| `confirm_title`, `confirm_text` | Char / Text | шаблони діалогу із `{param}` («Увімкнути секційний вимикач QS?» / «Секції 1 і 2 працюватимуть разом…») |
| `undo_kind_id` | Many2one self | зворотний вид (R-56 п.4) |
| `valid_s` | Integer | TTL команди в черзі (`expires_at = now + valid_s`), default `td.energy_control.command_ttl_s` |
| `active` | Boolean | default True |
| `remote_gated` | Boolean | D-46: команда дистанційного перемикання (`qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test`); при `td.energy_control.remote_switching_enabled=False` `prepare`/`confirm`/`confirm_second` → `UserError`, `available` не змінюється, плитка `enabled=false` |
| `available` | Boolean | compute: R-42 п.2 (`genset` — міст встановлено; `light`/`vent` — є цілі BMS; `intent` — джерело `ENERGY-CTL` активне) |
| `unavailable_reason` | Char | compute |

Методи: `normalize(params)` → dict (приведення типів, межі, `ValidationError("Команда {name}: параметр {label} поза межами {min}…{max} {unit}.")`); `render(params)` → `{"title","sub","text"}`; `build_checks(params)` → список для M-33 (R-41).

### M-32 `td.energy.interlock` — реєстр блокувань (FR-51, R-41)

`_name = "td.energy.interlock"`, `_description = "Енергетика: блокування"`, `_order = "sequence, id"`. Рядок — **налаштування іменованої перевірки**; код перевірки — в реєстрі `tools/interlocks.CHECKS` (Odoo) і `td_collector_energy/interlocks.py` (збирач) під тим самим `code`; `safe_eval` і код із БД заборонені.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char | size=32, req, idx, `UNIQUE`; має бути ключем `CHECKS`, інакше `ValidationError("Невідома перевірка {code}.")` |
| `name` | Char | size=128, req: шаблон рядка діалогу, напр. «Заряд {soc} % < {limit} %» |
| `hard` | Boolean | `True` — блокує виконання **в збирачі**; у діалозі Odoo блокує «Виконати» |
| `fail_closed` | Boolean | для `hard`: «немає даних» теж блокує (default True) |
| `where` | Selection | `both` (Odoo+збирач, default), `odoo` (лише підказка; напр. паливо ДГУ), `collector` (лише збирач) |
| `inputs` | Json | список кодів сигналів, потрібних перевірці (для конфігу збирача й `data_fresh`) |
| `params` | Json | пороги (R-41); змінює лише адміністратор (`td_factory3d.group_td_admin`), кожна зміна — `td.energy.action` `origin='config'`, `kind_code='interlock_param'` і `state.bump()` (R-41 п.7) |
| `sequence`, `active` | Integer, Boolean | |

### M-33 `td.energy.action` — дія оператора, автоматики й конфігурації; журнал (FR-50, FR-52, R-40, R-56)

`_name = "td.energy.action"`, `_description = "Енергетика: дія керування"`, `_order = "create_date desc, id desc"`, `_inherit = ["mail.thread"]` (чаттер: «Створено», «Підтверджено», «Результат»). Одна дія оператора = одна команда `td.command` (інтент) або одна зміна конфігурації; N кроків пристрою виконує збирач (R-52).

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | readonly, `copy=False`, послідовність `ir.sequence` `ACT/%(y)s/#####` (`td_energy_control.seq_action`) |
| `kind_id` | Many2one `td.energy.command.kind` | idx, ondelete restrict; порожнє для подій автоматики |
| `kind_code` | Char | size=48, idx, stored: код виду або `auto_<scenario>_<step>` (R-56 п.3) |
| `origin` | Selection | `manual`/«Вручну», `advice`/«Рекомендація», `schedule`/«Розклад», `auto`/«Автоматика», `undo`/«Скасування», `config`/«Конфігурація»; default `manual`, idx |
| `cls` | Selection | `A`/`B`; для `auto` — порожнє |
| `state` | Selection | `prepared`/«Підготовлено», `awaiting_second`/«Очікує другого підтвердження», `queued`/«У черзі», `sent`/«Передано збирачу», `executing`/«Виконується», `done`/«Виконано», `failed`/«Не виконано», `blocked`/«Заблоковано», `expired`/«Прострочено», `cancelled`/«Скасовано»; default `prepared`, idx, tracking |
| `params` | Json | нормалізовані параметри виду |
| `checks` | Json | результат перевірок Odoo останнього `prepare/confirm`: `[{"code","label","state":"ok\|fail\|unknown","hard","detail"}]` |
| `collector_checks` | Json | результат перевірок збирача (API-25 `actions[].checks`) |
| `token_hash` | Char | size=64, idx: `sha256(token)`; токен не зберігається (R-40 п.2) |
| `token_expires_at` | Datetime | |
| `needs_second` | Boolean | виставляється в `prepare`: `cls='B'` і `prepared_by` без `group_td_energy_chief`; далі не змінюється |
| `prepared_by`, `confirmed_by`, `second_by` | Many2one `res.users` | readonly; `second_by ≠ prepared_by`, `≠ confirmed_by` (constraint) |
| `prepared_at`, `confirmed_at`, `second_at`, `second_expires_at`, `started_at`, `finished_at` | Datetime | readonly |
| `command_id` | Many2one `td.command` | ondelete set null |
| `scenario_id`, `node_id`, `advice_id` | Many2one | ondelete set null |
| `undo_of_id` | Many2one self | ondelete set null; `undone_by_id` Many2one self (readonly) |
| `undo_params` | Json | параметри зворотної дії (попередня уставка, попередній порядок, попередній стан сценарію) — фіксуються на `confirm` |
| `undo_available` | Boolean | compute (не зберігається): R-56 п.5 |
| `config_version` | Integer | для `executor='config'`: версія після публікації |
| `applied` | Boolean | compute: для `config` — `state.applied_version >= config_version`; для решти — `state = 'done'` |
| `idem` | Char | size=40: `sha1("<id>:<kind_code>")`, частковий `UNIQUE WHERE idem IS NOT NULL` |
| `summary`, `detail`, `actor_text`, `result_text`, `error` | Char | size 128/256/96/96/256: рядки журналу (D-19) |
| `ref_model`, `ref_id` | Char / Integer | зовнішній об'єкт (`td.genset.command`, `maintenance.request`) для посилання |

Індекси: `(state, create_date)`, `(kind_code, state)`, `(node_id, create_date)`.

Методи (повна семантика — R-40; публічні обгортки — M-35/API-17…API-21):
`_td_prepare(kind, params, origin='manual', advice=None, scenario=None)` → запис `prepared` + токен; `_td_confirm(token)`; `_td_confirm_second()`; `_td_cancel(token)`; `_td_enqueue()` (створює `td.command`, R-40 п.6); `_td_on_command(cmd)` (виклик із M-37 при зміні стану команди); `_td_on_engine(item)` (API-25: `actions[]`); `_td_undo()`; `_td_close(state, result_text, error=None)` (єдина точка завершення: `finished_at`, `bus.tick(env, 'action')` шини `td_energy_control`, `advice.action_done`, повідомлення в чаттер); `_cron_expire()` (розд. 6); `_td_log_auto(ev)` (з `events[]` API-25 → запис `origin='auto'`; порожній `scenario` — без сценарію, підпис «автоматика» і нейтральний `summary` за видом події). Публічні безаргументні методи для кнопок форми V-41 (Odoo 19 валідує `type=object`): `action_confirm_second()`, `action_cancel()`, `action_undo()` — обгортки над тим самим потоком (права, D-46-гейт, інтерлоки, журнал), повертають `display_notification` (`action_undo` = `undo` + `confirm`: клік по кнопці — підтвердження, клас B без chief іде на друге підтвердження).

Права на запис: `create/write/unlink` — лише `sudo()` усередині методів; ACL для всіх груп — `read`; `unlink` заборонено всім, окрім адміністратора (журнал не видаляється; ротація — не в W2, Q-33).

### M-34 `td.energy.schedule.slot` — слот розкладу (FR-53, R-54)

`_name = "td.energy.schedule.slot"`, `_description = "Енергетика: слот розкладу"`, `_order = "resource, time_from, id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `resource` | Selection | `bess`/«BESS», `chp`/«КГУ», `vent`/«Вентиляція RoofVent», `light`/«Освітлення цеху», `charging`/«Зарядна станція», `genset`/«ДГУ»; req, idx |
| `date` | Date | порожнє = повторюється за `weekdays` |
| `weekdays` | Char | size=7, default `1111111` (пн…нд), лише коли `date` порожня |
| `time_from`, `time_to` | Float | 0…24 (години Києва; `7.5` = 07:30); `time_to > time_from`, інакше `ValidationError("Слот не може перетинати північ: розділіть його.")` |
| `mode` | Selection | `charge`/«заряд», `discharge`/«розряд», `run`/«пуск», `night`/«ніч», `day`/«день», `duty`/«черговий», `work`/«робочий», `test`/«тест» |
| `label` | Char | size=48 (текст смуги: «розряд · пік», «заряд від СЕС», «ніч 30 %», «день 100 %», «черговий», «робочий», «заряд», «тест», «пуск за ціною») |
| `setpoint_kw` | Float | для BESS/КГУ |
| `source` | Selection | `plan`/«План (прогноз)», `scenario`/«Сценарій», `manual`/«Вручну», `genset`/«td_genset»; default `manual`, idx |
| `executes` | Boolean | compute stored: `source='manual'` і `resource in ('bess','chp')` — слот виконується рушієм (BESS — крок `slots` R-54 п.5; КГУ — R-50); решта слотів — лише відображення |
| `bar_class` | Selection | compute: `c` (charge), `d` (discharge), `n` (night, duty), `g` (run, test), `o` (day, work) — кольори смуг макета |
| `scenario_id` | Many2one | set null |
| `active` | Boolean | default True |

Створення/зміна слотів із `source='manual'` — `group_td_energy_chief` (список/форма V-42; кожна зміна — запис `td.energy.action` `kind_code='schedule_edit'`, клас B, автоматично: override `create/write/unlink` логує й бампить `config_version`); `plan/scenario/genset` пише лише планувальник (R-54).

### M-35 `td.energy.control` — API екрана «Керування» (AbstractModel; FR-46…FR-54)

`_name = "td.energy.control"`, `_description = "Енергетика: дані екрана Керування"`. Усі методи `@api.model`; на вході — перевірка групи (`group_td_energy_user` для читання, `group_td_energy_manager` для `prepare/confirm/…`). Сигнатури — API-16…API-23, API-27, API-28 (розд. 7). Гаки розширення (порожні в базі): `_td_control_extra(self) -> dict` (додаткові блоки відповіді `get_control`).

### M-36 `td.energy.advice` — розширення: правила й банер «Виконано» (FR-54, R-55)

`_inherit = "td.energy.advice"`. Додає: `_td_advice_rule_export_t2(now)`, `_td_advice_rule_peak_risk(now)`, `_td_advice_rule_chp_price(now)` (реєстр R-32 W1 збирає їх без змін); `get_open()` (override): якщо відкритої рекомендації немає, а остання виконана дія `origin='advice'` перебуває у вікні `undo_window_min` і `undo_available` — повертає банер «Виконано» (R-55 п.4); `_td_on_action_done(action)` — `action_done(note)` через `with_user(action.confirmed_by)`.

### M-37 `td.command` — розширення (R-40 п.6, R-52)

`_inherit = "td.command"`. Додає `energy_action_id` (Many2one `td.energy.action`, idx, ondelete set null, readonly). `write()` (override, після `super`): якщо змінився `state` і є `energy_action_id` — `action._td_on_command(self)`. `create()` (override): `origin='energy'` без `energy_action_id` або без контексту `td_energy_control_internal` → `UserError("Команди енергетики створює лише модуль керування.")`; команда на сигнал `module='energy_control'` від не-`sudo` → `AccessError` (наявна перевірка `td.command` лишається: група менеджера телеметрії; модуль створює команди через `sudo()`).

### M-38 `td.source` / `td.signal` / `td.energy.event` — розширення (C-41, FR-60, FR-68)

`td.source.type`: `selection_add=[("energy_ctl", "Керування енергетикою (збирач)")]`, `ondelete={"energy_ctl": "cascade"}`; `td.source.module` і `td.signal.module`: `selection_add=[("energy_control", "Керування енергетикою")]`, `ondelete={"energy_control": "set default"}`. Тип `energy_ctl` **не локальний** (`_td_local_types` не змінюється): потрібен `collector_id`. Валідація параметрів/адрес: модуль при імпорті реєструє `tools.address.PARAMS_VALIDATORS["energy_ctl"] = _params_energy_ctl` (допустимі ключі `engine` {`tick_s` int 1…10, `config_poll_s` int 5…60}, `doc`; секрети заборонені — стандартна `_secret_errors`) і `ADDRESS_VALIDATORS["energy_ctl"] = lambda a: []`; це тимчасове рішення A-40 (офіційну точку розширення типів у `td_telemetry` запитано в Q-30). Обмеження: `td.signal` із `module='energy'` лишається read-only (W1 M-15, AC-81 діє); `module='energy_control'` допускає `write_enabled`; `td.signal` модуля `energy_control` не може мати `source_id.module in ('fire_safety','access','machine_connect')` і `code`, що починається з `fire/`, `evacuation/`, `sprinklers/`, `access/`, `workcenters/` (R-60 п.2) → `ValidationError("Сигнал {code}: керування цією системою заборонене.")`. `td.energy.event.kind` (W1 M-21): `selection_add=[("control", "Керування")]`, `ondelete={"control": "cascade"}` — події рушія, блокувань і `CTRL-HEARTBEAT` створюються через `td.energy.event._td_log(level, 'control', code, text, dedup_min=…)` (W1), `warn`/`bad`; авторозв'язання (`_td_auto_resolve('control', code)`) — при відновленні (`CTRL-HEARTBEAT`, `mode` → `auto`), решта закриваються автоматично через 24 год (`cron_td_energy_control_watch`) або вручну (`action_resolve`, W1 R-25). Усе — у файлі `models/td_source_signal.py`.

### M-39 `td.energy.control.state` — стан керування (singleton; FR-57, R-43)

`_name = "td.energy.control.state"`, `_description = "Енергетика: стан керування"`. Один запис (`xml-id td_energy_control.state_main`, `get()` створює за відсутності).

| Поле | Тип | Параметри |
|---|---|---|
| `config_version` | Integer | default 1; лише `bump()` |
| `config_etag` | Char | size=64: sha256 канонічного JSON конфігу (R-43 п.2) |
| `applied_version` | Integer | default 0: максимум `config_version_applied` зі звітів збирача |
| `engine_mode` | Selection | `unknown` (default), `off`, `hold`, `auto` |
| `engine_reason` | Char | size=128 (причина `hold`/`off`) |
| `engine_info` | Json | `{"started_at","ticks","tick_ms_p95","writes_last_min","collector"}` |
| `heartbeat_at`, `last_state_at`, `last_config_pull_at` | Datetime | readonly |
| `collector_id` | Many2one `td.collector` | readonly |
| `connected` | Boolean | compute (не зберігається): `now − heartbeat_at ≤ heartbeat_stale_s` |

Методи: `get()`, `bump()` (атомарно, `UPDATE … RETURNING`; перераховує `config_etag`), `_td_report(body)` (API-25).

### M-40 `res.config.settings` — розширення (V-44)

Поля `td_energy_control_*` з `config_parameter` для параметрів розд. 5.1 (групи: «Запобіжники», «Підтвердження», «Виконання», «Автоматика»). `set_values`: зміна `write_enabled`/`automation_enabled` — лише адміністратор (`td_factory3d.group_td_admin`), пише запис журналу `td.energy.action` `origin='config'`, `kind_code='switch_flag'`, і `state.bump()`.

### M-41, M-42 — міст 3D (`td_energy_viewer3d`)

M-41 `td.viewer.provider.energy_layer` і M-42 (`td.energy.node`, `res.config.settings`) перенесено до [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §2 (єдина нумерація W2; FR-62, R-57, V-46, V-47, R-58).

## 3. Представлення й меню

### 3.1 Представлення V-35…V-47

| ID | XML-id (`td_energy_control.`, міст — `td_energy_viewer3d.`) | Тип / модель | Структура |
|---|---|---|---|
| V-35 | `action_td_energy_control` | `ir.actions.client`, `tag="td_energy_control.control"`, `name="Керування енергетикою заводу"` | відкриває UI-12 |
| V-36 | `view_td_energy_control_state_form`, `action_td_energy_control_state` | form `td.energy.control.state` (readonly) | поля: `engine_mode`, `engine_reason`, `connected`, `heartbeat_at`, `config_version`, `applied_version`, `config_etag`, `last_state_at`, `last_config_pull_at`, `collector_id`, `engine_info` (Text JSON); кнопка «Опублікувати конфігурацію» (`bump`, адміністратор) |
| V-37 | `view_td_energy_scenario_list` / `_form`, `action_td_energy_scenario` | list/form `td.energy.scenario` | list: `sequence` (handle), `name`, `enabled` (badge), `engine_state` (badge: `active` success, `armed` info, `warn` warning, `off` muted), `applied` (boolean), `engine_ts`; form (readonly для всіх, крім `params_text` адміністратора): `description`, `params_text`, `engine_facts` (Text JSON), `config_version`, `state_signal_id`; без кнопок увімкнення (увімкнення — екран «Керування», клас B) |
| V-38 | `view_td_energy_shed_item_list` / `_form`, `action_td_energy_shed_item` | list (editable="bottom", `group_td_energy_chief`) / form | list: `sequence` (handle), `name`, `node_id`, `action`, `param_value`, `condition`, `condition_value`, `kw_reducible`, `p_now_kw` (readonly), `signal_id`, `active`, `how` (readonly); для не-chief — без редагування |
| V-39 | `view_td_energy_command_kind_list` / `_form`, `action_td_energy_command_kind` | list/form | list: `sequence`, `code`, `name`, `cls` (badge A/B), `executor`, `resource`, `tile`, `available`; form: усі поля, `params_schema`/`checks` — Text JSON; редагування — адміністратор |
| V-40 | `view_td_energy_interlock_list` / `_form`, `action_td_energy_interlock` | list/form | list: `sequence`, `code`, `name`, `hard`, `fail_closed`, `where`, `active`; form: `params` (Text JSON), `inputs`; редагування — адміністратор |
| V-41 | `view_td_energy_action_list` / `_form` / `_search` / `_pivot`, `action_td_energy_action` | list/form/search/pivot `td.energy.action` | list (readonly): `create_date`, `name`, `summary`, `kind_code` (optional hide), `origin`, `cls` (badge), `state` (badge: `done` success, `executing`/`sent`/`queued` info, `awaiting_second` warning, `failed`/`blocked` danger, `expired`/`cancelled` muted), `prepared_by`, `confirmed_by`, `second_by`, `result_text`; form: statusbar `state`, блоки «Дія» (`params`, `checks`, `collector_checks` — таблиці з Text JSON), «Підтвердження», «Результат», чаттер; header-кнопки: «Підтвердити (2/2)» (`action_confirm_second`, `invisible="state != 'awaiting_second'"`), «Скасувати» (`action_cancel`, state ∈ `prepared/awaiting_second/queued`), «Скасувати дію» (`action_undo`, `invisible="not undo_available"`); search: фільтри «Мої» (`prepared_by = uid`), «Очікують підтвердження» (`state = awaiting_second`), «Помилки» (`state in (failed, blocked, expired)`), «Автоматика» (`origin = auto`), «Сьогодні», групування `origin`, `state`, `kind_code`, `node_id`; pivot: рядки `kind_code`, колонки `state`, міра `count` |
| V-42 | `view_td_energy_schedule_slot_list` / `_form` / `_search`, `action_td_energy_schedule_slot` | list (editable bottom для chief)/form/search | list: `resource`, `date`, `weekdays`, `time_from`, `time_to` (widget `float_time`), `mode`, `label`, `setpoint_kw`, `source` (badge), `executes`, `active`; кнопка списку «Перебудувати план» (`action_rebuild_plan`, chief) |
| V-43 | `view_td_command_form_td_energy_control` | form `td.command` (зміна) | поле `energy_action_id` у групі «Керування» (`invisible="not energy_action_id"`) |
| V-44 | `res_config_settings_view_form_td_energy_control` | `res.config.settings` (зміна) | у блоці `app name="td_energy"` розділ «Керування»: «Запобіжники» (`write_enabled`, `automation_enabled`; лише адміністратор, підказка про 5 запобіжників), «Підтвердження» (`confirm_ttl_s`, `second_ttl_s`, `undo_window_min`), «Виконання» (`command_ttl_s`, `exec_timeout_s`, `step_timeout_s`, `verify_timeout_s`, `apply_timeout_s`), «Автоматика» (`engine_tick_s`, `config_poll_s`, `stale_hold_s`, `min_write_interval_s`, `max_writes_per_min`, `shed_restore_step_s`), «Рекомендації» (`export_advice_min`) |
| V-45 | `views/menus.xml` | `ir.ui.menu` | таблиця 3.3 |
| V-46, V-47 | `td_energy_viewer3d.…` | налаштування шару й серверна дія «Енергетика в 3D» | Перенесено до [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §3 (V-46: блок налаштувань `td_energy_viewer3d_layers`, `…_marker_limit`, `…_show_markers`; V-47: дія `action_td_energy_3d` і меню) |

### 3.2 Клієнтські компоненти (OWL) UI-12…UI-28

Усе — `@odoo/owl`, `registry.category("actions")`; дані — `orm.call("td.energy.control", …)`; рядки UI українською; кожен інтерактивний елемент — `<button>` з `aria-label`, мінімум 36 px (кнопки ↑/↓ як у макеті), перемикачі — `role="switch"` + `aria-checked`; стан не лише кольором (текст чипа). Токени кольорів — `td_energy.scss` W1 (UI-11): чипи `act`: фон `#ecfdf5`, текст `#065f46`; `arm`: `#eff6ff`/`#1e40af`; `warn`: `#fff7ed`/`#9a3412`; `off`: `#f3f4f6`/`#374151`; перемикач увімкнений `#0f766e`, вимкнений `#d1d5db`; акцент `#714B67`.

| ID | Компонент / тег | Вміст і поведінка |
|---|---|---|
| UI-12 | `Control` (`td_energy_control.control`) | Шапка (крихти «Енергетика / Керування», h1 «Керування енергетикою заводу», підзаголовок «Режими, сценарії автоматики, пріоритети навантажень і ручні команди», `EngineChip`); інформаційна смуга з текстом макета («Сценарії виконує контролер ГРЩ і збирач сигналів, без затримок Odoo. Тут задаються режими, уставки й розклад. Кожна ручна команда проходить блокування й підтвердження і пишеться в журнал. Захист людей і пожежна автоматика працюють окремо й тут не керуються.»); банер очікування другого підтвердження (D-43); секції UI-14, UI-15 і UI-16 поруч, UI-19, UI-20. Дані: `get_control()` (API-16); оновлення: підписка на шину `td_energy_control` (гак `useControlBus(callback, kinds)` у `static/src/control/bus.js`: канал `td_energy_control`, повідомлення `td_energy_control/update` `{"kinds": ["action","scenario","engine","schedule","shed"], "ts"}` без даних, A-41; дебаунс 2 с), резервний таймер 30 с. Стан: `data`, `dialog`, `reorder`, `busy`. Тости — за станами D-31 |
| UI-13 | `EngineChip` | `engine.connected && mode=='auto'` → зелений «Контролер ГРЩ і збирач на зв'язку · HH:MM»; `connected && mode in (hold, off)` → бурштиновий «Автоматику призупинено: {reason}»; `!connected` → червоний «Збирач не на зв'язку · {вік}» (D-28) |
| UI-14 | `ScenarioGrid`, `ScenarioCard` | Заголовок секції «Сценарії автоматики» і «увімкнено N з 6»; сітка `repeat(auto-fill, minmax(320px, 1fr))`; картка: `h3` назва, чип `state_text` (колір `state_kind`), `role="switch"` (клас B: клік відкриває `ConfirmDialog` для `scenario_toggle`; стан перемикача = `enabled` з Odoo; якщо `!applied` — додатковий чип «Очікує застосування»), опис, чипи параметрів (`chips[]`), кнопка «Параметри» (UI-18) |
| UI-15 | `ShedList` | Заголовок «Пріоритети відключення навантажень», підзаголовок «Що зменшувати першим, коли не вистачає BESS і КГУ, щоб утримати {limit_kw} кВт»; `ol` рядків: круглий номер, `name`, `how`, `−{kw_reducible} кВт`, кнопки «Вище»/«Нижче» (`aria-label`, 36 × 36) лише в режимі «Змінити порядок» (D-24); підвал «Разом можна зняти **{sum} кВт**. Не відключаються ніколи: {never_text}.» (D-26); кнопки «Змінити порядок» (chief/manager) → «Зберегти порядок» (відкриває `ConfirmDialog` `shed_reorder`) / «Скасувати» |
| UI-16 | `CommandTiles` | Заголовок «Ручні команди», підзаголовок «Права: енергетик і головний енергетик · кожна команда з підтвердженням»; сітка 2 колонки, плитка `min-height: 56px`: `label` (жирний) і `sub`; клас B — бейдж «B» і підказка; `available=false` або немає прав — `disabled` + `title` причини; клік → `prepare` → `ConfirmDialog` |
| UI-17 | `ConfirmDialog` | `role="dialog" aria-modal="true"`, максимальна ширина 500 px; заголовок «{title}?», абзац `text`, підзаголовок «Перевірка блокувань», список «{label} — **гаразд**» (зелений) / «**не виконано**» (червоний, причина) / «**немає даних**» (бурштиновий; для `hard+fail_closed` блокує); для класу B без `chief`: рядок «Потрібне друге підтвердження іншим енергетиком» і кнопка «Підтвердити (1/2)»; кнопки «Скасувати», «Виконати» (`disabled`, якщо `blocked`); зворотний відлік TTL токена (`confirm_ttl_s`), після спливу — «Час підтвердження минув, відкрийте діалог знову»; після `confirm` — блок прогресу «Надіслано → Виконується → Виконано / Не виконано: {error}» (опитування `get_action(id)` кожні 2 с до `finished_at`, не довше `verify_timeout_s + 30`); Esc = «Скасувати» (`cancel(token)`), Enter підтверджує клас A без блокувань; фокус у діалозі, повернення фокуса на плитку |
| UI-18 | `ParamsDialog` | Форма параметрів сценарію за `params_schema` сценарію (поля з API-16 `scenarios[].schema`), підказки з межами; «Зберегти» → `prepare('scenario_params', …)` → `ConfirmDialog` |
| UI-19 | `ScheduleTimeline` | Секція «Розклад на сьогодні», праворуч «зараз {HH:MM} · план складено з прогнозу навантаження й СЕС»; сітка `200px 1fr`, мінімальна ширина 860 px, шкала 00…24 крок 3 год, 6 рядків (BESS, КГУ, Вентиляція RoofVent, Освітлення цеху, Зарядна станція, ДГУ), смуги `left = from/24`, `width = (to−from)/24`, кольори `bar_class` (`c` `#99f6e4/#134e4a`, `d` `#c4b5fd/#3b0764`, `n` `#bfdbfe/#1e3a8a`, `g` `#fde68a/#78350f`, `o` `#e5e7eb/#374151`), підпис у смузі й `title`; вертикаль «зараз» (чорна, 2 px) на `now/24`; під таблицею — текстова таблиця для скрінрідерів (`visually-hidden`) |
| UI-20 | `Journal` | Секція «Журнал команд і перемикань»; рядок: час `HH:MM` (52 px), `<b>{summary}</b> · {detail}`, `actor_text`, чип результату (`виконано` зелений, `створено`/`збережено, очікує збирач` синій, `не виконано`/`заблоковано` червоний, `скасовано` сірий); для дій з `undo_available` — кнопка «Скасувати дію» (відкриває `ConfirmDialog` для `undo`); для `awaiting_second` — «Підтвердити (2/2)» (лише інший `manager`); кнопка «Показати більше» (50 записів за крок, `before_id`) і посилання «Усі записи» → V-41 |
| UI-21 | `ControlAdviceHandler` | Реєструє `registry.category("td_energy.advice_handlers").add("control", handler)`: `handler({action, advice, component})` викликає `prepare(command_kind, params, {advice_id})` і показує `ConfirmDialog`; після `done` повертає `true` (Пульт перечитує `advice`, `alarms`); для `act.code='undo'` — `undo(action_id)` (R-55 п.4) |
| UI-22 | `NodeActions` | Реєструє `registry.category("td_energy.node_actions").add("td_energy_control", {match, actions})`: для вузла `QS` — «Увімкнути QS…» (`qs_close`) або «Вимкнути QS…» (`qs_open`) за `sld_state`; для `BESS` — «Зарядити 50 кВт» (`bess_charge`) або «Зупинити заряд» (`bess_stop`) за станом; дії з `get_node_actions(code)` (API-27) і стилем `o_td_en_btn--teal` (D-38) |
| UI-28 | `DoneBanner` | Варіант банера Пульта `advice.state==='done'` (зелений, іконка «пташка», текст `title` жирним + `text`, кнопка «Скасувати»; без «Пізніше»): класи `o_td_en_advice--done` у `pult.xml`, стиль у `control.scss` |
| UI-23…UI-27 | `td_energy_viewer3d` | Описані в [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §8.4.3 (`EnergyLayerExtension`, `StateColors`, `AlarmMarkers`, `NodeBlock`, `ViewerLinks`) |

### 3.3 Меню (`views/menus.xml`)

| XML-id | Назва | Батько | seq | Групи | Дія |
|---|---|---|---|---|---|
| `td_energy_control.menu_td_energy_control` | Керування | `td_energy.menu_td_energy` | 8 | `td_energy.group_td_energy_user` | `action_td_energy_control` |
| `td_energy_control.menu_td_energy_action` | Журнал команд | `td_energy.menu_td_energy` | 9 | `td_energy.group_td_energy_user` | `action_td_energy_action` |
| `td_energy_control.menu_td_energy_scenario` | Сценарії автоматики | `td_energy.menu_td_energy_config` | 50 | `td_energy.group_td_energy_manager` | `action_td_energy_scenario` |
| `td_energy_control.menu_td_energy_shed_item` | Пріоритети скидання | `td_energy.menu_td_energy_config` | 51 | `td_energy.group_td_energy_manager` | `action_td_energy_shed_item` |
| `td_energy_control.menu_td_energy_schedule_slot` | Розклад (слоти) | `td_energy.menu_td_energy_config` | 52 | `td_energy.group_td_energy_manager` | `action_td_energy_schedule_slot` |
| `td_energy_control.menu_td_energy_interlock` | Блокування | `td_energy.menu_td_energy_config` | 53 | `td_energy.group_td_energy_manager` | `action_td_energy_interlock` |
| `td_energy_control.menu_td_energy_command_kind` | Види команд | `td_energy.menu_td_energy_config` | 54 | `td_factory3d.group_td_admin` | `action_td_energy_command_kind` |
| `td_energy_control.menu_td_energy_control_state` | Стан керування | `td_energy.menu_td_energy_config` | 55 | `td_factory3d.group_td_admin` | `action_td_energy_control_state` |
| `td_energy_viewer3d.menu_td_energy_3d` | Енергетика в 3D | `td_energy.menu_td_energy` | 90 | `td_energy.group_td_energy_user` | `action_td_energy_3d` |

Пункт «Керування» з'являється лише після встановлення модуля (W1 D-18). Порядок верхнього меню: Пульт (5), Чергування (6), Керування (8), Журнал команд (9), Завантаження вузлів (15), …

### 3.4 Правки клієнта `td_energy` (власник B; мінімальні, адитивні; AC-292, AC-301, AC-302)

1. `static/src/common/actions.js`: експортується `viewerLinks = registry.category("td_energy.viewer_links")`; `openViewer(opts)` — якщо є запис `default`, викликає `link.open({code: opts?.code})`; інакше поведінка W1 (сповіщення або `f3d_viewer.action` з `params.layers`, виправлення ключа `layer` → `layers: ["energy"]`); `show3d(code)` — якщо є запис `default`, `link.open({code})` (працює й для вузлів без `equipment_id`, якщо в шарі є `scene`), інакше наявний шлях `action_f3d_show` (C-45).
2. `static/src/pult/sld.js`, `sld.xml`: під кнопками панелі вузла — цикл за записами реєстру `td_energy.node_actions` (контракт: `{match(node) → bool, actions(node, ctx) → Promise<[{code, label, cls, onClick}]>}`), кнопки класу `o_td_en_btn` (C-46).
3. `static/src/pult/pult.xml`, `pult.js`: варіант банера `advice.state === 'done'` (UI-28): клас `o_td_en_advice--done`, приховано «Пізніше».
4. `static/tests/control_hooks.test.js`: hoot-тести пунктів 1–3 (AC-292, AC-301, AC-302). Інших змін W1-коду немає; бекенд `td_energy` не змінюється (A-41).

## 4. Права

### 4.1 `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_energy_scenario_user,td.energy.scenario user,model_td_energy_scenario,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_scenario_admin,td.energy.scenario admin,model_td_energy_scenario,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_shed_item_user,td.energy.shed.item user,model_td_energy_shed_item,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_shed_item_chief,td.energy.shed.item chief,model_td_energy_shed_item,td_energy.group_td_energy_chief,1,1,1,1
access_td_energy_shed_item_admin,td.energy.shed.item admin,model_td_energy_shed_item,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_command_kind_user,td.energy.command.kind user,model_td_energy_command_kind,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_command_kind_admin,td.energy.command.kind admin,model_td_energy_command_kind,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_interlock_user,td.energy.interlock user,model_td_energy_interlock,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_interlock_admin,td.energy.interlock admin,model_td_energy_interlock,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_action_user,td.energy.action user,model_td_energy_action,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_action_admin,td.energy.action admin,model_td_energy_action,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_schedule_slot_user,td.energy.schedule.slot user,model_td_energy_schedule_slot,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_schedule_slot_chief,td.energy.schedule.slot chief,model_td_energy_schedule_slot,td_energy.group_td_energy_chief,1,1,1,1
access_td_energy_schedule_slot_admin,td.energy.schedule.slot admin,model_td_energy_schedule_slot,td_factory3d.group_td_admin,1,1,1,1
access_td_energy_control_state_user,td.energy.control.state user,model_td_energy_control_state,td_energy.group_td_energy_user,1,0,0,0
access_td_energy_control_state_admin,td.energy.control.state admin,model_td_energy_control_state,td_factory3d.group_td_admin,1,1,1,1
```

`td.energy.control` — `AbstractModel` без ACL (перевірка в методах, M-35). «Енергетик» (`group_td_energy_manager`) успадковує `group_td_energy_user` і напряму лише читає ці моделі; усі його дії — через M-35/M-33 під `sudo()`. Нових груп немає (E-06: групи з W1; `group_td_energy_chief` — «Головний енергетик»). Record rules не потрібні (моделі без компанії; як `td.energy.event` W1 §4.3).

### 4.2 Матриця прав (R-39)

| Операція | `…_user` | `…_manager` («Енергетик») | `…_chief` («Головний енергетик») | адміністратор |
|---|---|---|---|---|
| Бачити екран, журнал, розклад, перевірки | ✓ | ✓ | ✓ | ✓ |
| `prepare` команди класу A, `confirm` A | ✗ | ✓ | ✓ | ✓ |
| `prepare` команди/дії класу B | ✗ | ✓ | ✓ | ✓ |
| `confirm` B, одноосібно | ✗ | ✗ (стає `awaiting_second`) | ✓ | ✓ |
| `confirm_second` B (інша особа) | ✗ | ✓ (≠ готував, ≠ підтверджував) | ✓ (≠ …) | ✓ |
| `undo` | ✗ | за класом зворотного виду | за класом | ✓ |
| Змінювати склад/параметри `shed.item`, слоти `manual` | ✗ | ✗ | ✓ | ✓ |
| Змінювати `command.kind`, `interlock.params`, прапори `write_enabled`/`automation_enabled`, `config_poll_s` | ✗ | ✗ | ✗ | ✓ |
| Тест ДГУ (`genset_test`, B) | ✗ | перша особа | ✓ | ✓ + права `td_genset` (`group_tech`, ADP-12 R-67) |

### 4.3 Запобіжники («п'ять + один»)

Щоб пристрій отримав запис: (1) `td.telemetry.write_enabled`; (2) `td.energy_control.write_enabled`; (3) `td.source.write_enabled` джерела (`MB-U73-SWB-CMD`, `ENERGY-CTL`, а для BMS — відповідні джерела `td_bms`; плюс `td.bms.write_enabled`); (4) `td.signal.write_enabled`; (5) `F3D_WRITE_ENABLED=true` у збирачі. Для автономних дій сценаріїв додатково (6) `td.energy_control.automation_enabled`. Окремо від запобіжників — перемикач `td.energy_control.remote_switching_enabled` (D-46, Q-27, default `False`): при `False` команди дистанційного перемикання (`remote_gated`) відхиляються з `UserError` незалежно від решти прапорів. За замовчуванням усі `False` (прод) — на тестовому сервері вмикання робить менеджер скриптом `hooks._td_enable_stand(env)` (R-61; ставить і `remote_switching_enabled=True`). `neutralize.sql` скидає (2), (3), (4), (6) і `remote_switching_enabled` (розд. 5.7). Стоп-кран `module='energy'` (W1 AC-81) не змінюється: усі сигнали цього модуля, що записуються, мають `module='energy_control'`.

### 4.4 Захист даних і дій

- Токен `prepare` — випадкові 24 байти (`secrets.token_urlsafe`), у БД лише `sha256`; порівняння `hmac.compare_digest`; токен належить користувачу (`prepared_by`), інший користувач із токеном → `AccessError`.
- `confirm` атомарний: `SELECT … FOR UPDATE` на записі дії; повторний `confirm` того самого токена повертає той самий результат без нової команди (R-40 п.4).
- Конфіг для збирача не містить секретів і вартості; `/td/energy/automation/*` — Bearer-токен колектора (`td.collector._authenticate`), `auth="public"`, `csrf=False`, rate-limit `collector._rate_check()`.
- Вартість (`group_td_energy_cost`) на екрані «Керування» не показується.
- Заборонено: запис у `td_genset` (лише адаптер ADP-12), зміна меню `td_genset`, `x_`-поля, `safe_eval` над даними БД, керування сигналами системної безпеки (R-60).

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)

| Ключ | За замовчуванням | Призначення |
|---|---|---|
| `td.energy_control.write_enabled` | `False` | запобіжник (2): ручні команди пристроям |
| `td.energy_control.automation_enabled` | `False` | запобіжник (6): автоматика збирача виконує дії; інакше рушій у режимі `off` (моніторинг) |
| `td.energy_control.confirm_ttl_s` | `60` | TTL токена `prepare` → `confirm` |
| `td.energy_control.second_ttl_s` | `600` | очікування другого підтвердження |
| `td.energy_control.command_ttl_s` | `120` | `expires_at` команди в черзі `td.command` |
| `td.energy_control.exec_timeout_s` | `60` | максимальний час виконання інтента в збирачі |
| `td.energy_control.step_timeout_s` | `8` | запис одного кроку |
| `td.energy_control.verify_timeout_s` | `30` | очікування підтвердження пристроєм (сума кроків ≤ `exec_timeout_s`) |
| `td.energy_control.apply_timeout_s` | `60` | очікування застосування конфігурації збирачем |
| `td.energy_control.undo_window_min` | `15` | вікно скасування й банер «Виконано» |
| `td.energy_control.heartbeat_stale_s` | `30` | heartbeat рушія старший — «не на зв'язку» |
| `td.energy_control.engine_tick_s` | `2` | період циклу рушія |
| `td.energy_control.config_poll_s` | `10` | період опитування конфігу рушієм |
| `td.energy_control.stale_hold_s` | `30` | вхід несвіжий → рушій у `hold` |
| `td.energy_control.min_write_interval_s` | `10` | мінімальний інтервал повторного запису того самого сигналу |
| `td.energy_control.max_writes_per_min` | `30` | запобіжник частоти записів рушія |
| `td.energy_control.shed_restore_step_s` | `20` | крок відновлення скинутих навантажень |
| `td.energy_control.plan_horizon_days` | `2` | на скільки діб уперед будується план (R-54) |
| `td.energy_control.export_advice_min` | `5` | хвилин експорту для правила EXPORT-T2 (R-55) |
| `td.energy_control.journal_limit` | `50` | записів журналу за один запит |
| `td.energy_control.remote_switching_enabled` | `False` (demo/стенд — `True`) | D-46 / Q-27: дистанційне перемикання (`qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test`) дозволено; інакше `UserError` |

### 5.2 `data/td_energy_scenario_data.xml` — 6 сценаріїв (noupdate; тексти й параметри макета `Control.dc.html`)

| `code` | `name` | `description` (макет) | `enabled` | Чипи параметрів (макет → джерело) |
|---|---|---|---|---|
| `peak` | Зрізання піку | «Тримати імпорт нижче уставки: спершу розряд BESS, потім пуск КГУ, далі відключення за пріоритетами.» | ✓ | «уставка {limit_kw} кВт · {limit_pct} %», «прогноз 15 хв» |
| `self` | Самоспоживання СЕС | «Надлишок СЕС заряджає BESS. Експорт у мережу не більше 20 кВт, далі обмеження інверторів.» | ✗ | «експорт ≤ {export_max_kw} кВт», «BESS до {bess_target_soc_pct} %» |
| `pfc` | Компенсація реактивної потужності | «Автоматичні ступені PFC-1 і PFC-2 тримають цільовий cos φ на кожній секції.» | ✓ | «ціль cos φ {cos_phi_target}», «крок {pfc_step_kvar} квар» |
| `night` | Нічний режим (BMS) | «Поза змінами: вентиляція RoofVent на 30 %, у цеху — черговий сценарій освітлення, опалення на 16 °C.» | ✓ | «{from}–{to}», «RoofVent {vent_pct} %», «{heat_setpoint_c} °C» |
| `backup` | Резервне живлення | «Зникла мережа: АВР переводить на ДГУ, неважливі навантаження вимикаються, критичні лишаються.» | ✓ | «АВР → ДГУ», «критичні {critical_kw} кВт» |
| `chp` | КГУ за графіком і ціною | «Пуск КГУ, коли газ дешевший за мережу або коли BESS не вистачає для зрізання піку.» | ✗ | «мін. робота {min_run_h} год», «ціна газу {gas_price_uah_m3} ₴/м³» |

Чипи формуються в `tools/status_text.py` (`chips(scenario)`; числа форматуються `0,0` з комою, `95 %` = округлене `limit_kw / contract_kw · 100`).

### 5.3 `data/td_energy_command_kind_data.xml` — 16 видів команд

Колонки: `code` · заголовок плитки / sub · клас · виконавець · ресурс · перевірки (R-41; «м» — м'яка) · параметри (`name` тип межі, default) · зворотний вид.

| `code` | Плитка (`name` / `sub_template`) | `cls` | `executor` | `resource` | Перевірки | Параметри | `undo_kind` |
|---|---|---|---|---|---|---|---|
| `qs_close` | «Увімкнути секційний вимикач QS» / «секції 1 і 2 разом» | B | intent | qs | `controller_remote`, `data_fresh`, `no_island`, `ats_parallel_lock`, `qs_current_ok` | — | `qs_open` |
| `qs_open` | «Вимкнути секційний вимикач QS» / «секції окремо» | B | intent | qs | `controller_remote`, `data_fresh` | — | `qs_close` |
| `bess_charge` | «Заряд BESS {power_kw} кВт» / «до {until} або {soc_limit_pct} %» | A | intent | bess | `controller_remote`, `data_fresh`, `no_island`, `bess_ok`, `bess_soc_lt_limit`, `bess_temp_ok` | `power_kw` float 1…`bess_max_kw`, 50; `until` time `HH:MM`, 16:00; `soc_limit_pct` float 50…100, 95 | `bess_stop` |
| `bess_discharge` | «Розряд BESS {power_kw} кВт» / «на {duration_min} хв» | B | intent | bess | `controller_remote`, `data_fresh`, `bess_ok`, `bess_reserve_kept`, `bess_temp_ok` | `power_kw` float 1…`bess_max_kw`, 100; `duration_min` int 1…240, 60 | `bess_stop` |
| `bess_stop` | «Зупинити BESS» / «повернути автоматичний режим» | A | intent | bess | `controller_remote` | — | — |
| `chp_start` | «Пуск КГУ» / «TEDOM Quanto D800» | B | intent | chp | `controller_remote`, `data_fresh`, `no_island`, `chp_ready`, `chp_gas_pressure`, `chp_permit` | — | `chp_stop` |
| `chp_stop` | «Зупинка КГУ» / «з охолодженням» | B | intent | chp | `controller_remote`, `chp_min_run` | — | `chp_start` |
| `genset_test` | «Тест ДГУ без навантаження» / «{test_minutes} хв» | B | genset | genset | `genset_fuel` (м), `genset_heater` (м), `no_island`, `genset_idle` | `mode` enum `idle`, `idle` | — |
| `light_break` | «Освітлення цеху · сценарій «Перерва»» / «{level_pct} % на {duration_min} хв» | A | intent | light | `controller_remote`, `no_fire_alarm`, `aisle_lux_ge` (м) | `level_pct` int 10…100, 50; `duration_min` int 1…120, 30; `scene_number` int 1…16, 3 | `light_restore` |
| `light_restore` | «Освітлення цеху · повернути режим» / «за розкладом» | A | intent | light | `no_fire_alarm` | — | — |
| `vent_eco` | «Вентиляція · режим «Економ»» / «RoofVent {vent_pct} %» | A | intent | vent | `controller_remote`, `no_fire_alarm`, `co2_lt` (м) | `vent_pct` int 30…100, 70; `duration_min` int 1…480, 120 | `vent_restore` |
| `vent_restore` | «Вентиляція · повернути режим» / «за розкладом» | A | intent | vent | `no_fire_alarm` | — | — |
| `air_setpoint` | «Компресорна · тиск {setpoint_bar} бар» / «змінити уставку з {current_bar} до {setpoint_bar} бар» | B | intent | air | `controller_remote`, `data_fresh`, `air_setpoint_min` | `setpoint_bar` float 5,0…8,5, 6,5 | `air_setpoint` (с `undo_params.setpoint_bar = current_bar`) |
| `scenario_toggle` | «Сценарій «{scenario}»: {on_off}» | B | config | config | — | `scenario` enum, `enabled` bool | `scenario_toggle` |
| `scenario_params` | «Параметри сценарію «{scenario}»» | B | config | config | — | за схемою сценарію (M-29) | `scenario_params` |
| `shed_reorder` | «Порядок скидання навантажень» | B | config | config | — | `order` list[int] | `shed_reorder` |

Плитки (`tile=True`, порядок і підписи як у макеті): `qs_close`, `bess_charge`, `bess_discharge`, `chp_start`, `genset_test`, `light_break`, `vent_eco`, `air_setpoint` — 8 штук. `confirm_title`/`confirm_text` — тексти діалогів макета: QS «Увімкнути секційний вимикач QS?» / «Секції 1 і 2 працюватимуть разом. Генерація СЕС піде на навантаження секції 1, експорт через T2 припиниться.»; `bess_charge` «BESS заряджатиметься від надлишку СЕС і мережі до {until}.»; `bess_discharge` «BESS віддаватиме {power_kw} кВт у секцію 2 протягом {duration_min} хв.»; `chp_start` «КГУ запуститься й вийде на {chp_kw} кВт за {ramp_min} хв. Мінімальний час роботи — {min_run_h} год.»; `genset_test` «ДГУ запуститься на холостому ходу на {test_minutes} хв, АВР лишається на мережі.»; `light_break` «Освітлення ліній знизиться до {level_pct} % на {duration_min} хв, проходи лишаються на 100 %.»; `vent_eco` «Дахові установки знизять продуктивність до {vent_pct} %, CO₂ контролюється.»; `air_setpoint` «Уставка тиску мережі стисненого повітря знизиться з {current_bar} до {setpoint_bar} бар.».

### 5.4 `data/td_energy_interlock_data.xml` — реєстр блокувань (20 рядків)

Колонки: `code` · `name` (шаблон рядка діалогу) · `hard` · `fail_closed` · `where` · `inputs` (коди сигналів) · `params` (сид). Алгоритми — R-41.

| `code` | `name` | hard | f_closed | where | inputs | `params` |
|---|---|---|---|---|---|---|
| `controller_remote` | «Контролер у дистанційному режимі» | ✓ | ✓ | both | `energy_control/ctl/remote` | — |
| `data_fresh` | «Дані свіжі» | ✓ | ✓ | both | (решта входів перевірки) | `max_age_s` 60 |
| `no_island` | «Мережа є, острівного режиму немає» | ✓ | ✓ | both | `infra/ats/position`, `infra/ats/src1_ok` | — |
| `ats_parallel_lock` | «Блокування паралельної роботи T1 і T2 від АВР — увімкнено» | ✓ | ✓ | both | `energy_control/ats/parallel_lock` | — |
| `qs_current_ok` | «Струм через QS після вмикання ≈ {i_a} А з {rating_a} А» | ✓ | ✓ | both | `energy/sections/S1/p_kw`, `energy/sections/S2/p_kw`, `energy/cells/QS/state` | `rating_a` 1600, `max_ratio` 0.8, `cos_phi` 0.95 |
| `bess_ok` | «BESS на зв'язку, без аварії» | ✓ | ✓ | both | `infra/bess/state` | — |
| `bess_soc_lt_limit` | «Заряд {soc} % < {limit} %» | ✓ | ✓ | both | `infra/totals/bess_soc` | — |
| `bess_reserve_kept` | «Резерв на відключення мережі {reserve} % збережено» | ✓ | ✓ | both | `infra/totals/bess_soc`, `energy_control/bess/reserve_pct` | `capacity_kwh` 387 |
| `bess_temp_ok` | «Температура шафи {t} °C» | ✓ | ✗ | both | `energy_control/bess/temp_c` | `max_c` 40 |
| `chp_ready` | «КГУ зупинена й готова до пуску» | ✓ | ✓ | both | `infra/chp/state` | — |
| `chp_gas_pressure` | «Тиск газу {bar} бар» | ✓ | ✓ | both | `energy_control/chp/gas_bar` | `min_bar` 1.5 |
| `chp_permit` | «Дозвіл оператора КГУ» | ✓ | ✓ | both | `energy_control/chp/permit` | — |
| `chp_min_run` | «Мінімальний час роботи КГУ {h} год відпрацьовано» | ✓ | ✗ | collector | `infra/chp/state`, `infra/chp/hours` | `min_run_h` 2 |
| `no_fire_alarm` | «Пожежної тривоги немає» | ✓ | ✗ | both | `fire/panel/state` (якщо є) | — |
| `genset_fuel` | «Паливо ДГУ {pct} %» | ✗ | — | odoo | (адаптер ADP-03) | `min_pct` 30 |
| `genset_heater` | «Підігрів двигуна увімкнено» | ✗ | — | odoo | (адаптер) | — |
| `genset_idle` | «ДГУ не в роботі й тест не йде» | ✓ | ✗ | odoo | (адаптер) | — |
| `aisle_lux_ge` | «Освітленість проходів ≥ {lux} лк» | ✗ | — | both | `lighting/groups/*/e_now` (проходи за BMS) | `min_lux` 75 |
| `co2_lt` | «CO₂ у цеху {ppm} ppm < {limit} ppm» | ✗ | — | both | `ventilation/totals/co2_ppm` (якщо є) | `max_ppm` 1000 |
| `air_setpoint_min` | «Мінімальний тиск споживачів {min} бар» | ✓ | ✓ | both | `energy_control/air/min_consumer_bar` | `margin_bar` 0.2, `max_bar` 8.5 |

`hard` при `where='odoo'` блокує лише «Виконати» в Odoo (у збирача цих перевірок немає: `td_genset` має власні `_precheck`); `where='collector'` — у діалозі рядок «перевіряє збирач» (стан `unknown`, не блокує) і жорстка перевірка в збирачі (R-41 п.3).

### 5.5 `data/td_energy_shed_item_data.xml` — пріоритети (макет `loads`, порядок `prio`)

| № | `name` | `node_id` (код) | `action` | `param_value` | `kw_reducible` | `condition` | `how` (обчислюється) |
|---|---|---|---|---|---|---|---|
| 1 | Зарядна станція навантажувачів | `CHARGING` | `defer` | 30 | 48 | `none` | «відкласти заряд до 30 хв» |
| 2 | Дахова вентиляція RoofVent | `RV-ALL` | `reduce` | 70 | 60 | `none` | «знизити до 70 %» |
| 3 | Сушильна камера DRY-1 | `DRY-1` | `pause` | 20 | 17 | `no_active_cycle` | «пауза до 20 хв, без втрати циклу» |
| 4 | Компресор 2 (резервний) | `COMPRESSOR` | `off` | 0 | 37 | `air_pressure_min` (6,5) | «вимкнути, тиск ≥ 6,5 бар» |
| 5 | Освітлення складів | `LP-1` | `reduce` | 50 | 12 | `none` | «знизити до 50 %» |

Сума `kw_reducible` = 174 кВт (макет: «Разом можна зняти 174 кВт»). `COMPRESSOR` і `LP-1` — вузли `is_critical` (W0): рядки допускаються M-30 п.2 (`condition` / `reduce`), мають `critical=True` і виконуються лише в `peak`. Вузол `DRY-1` має `workcenter_id` → умова `no_active_cycle` обов'язкова (M-30 п.3). Сигнали `signal_id` — `energy_control/shed/<node.code>/limit_pct` (розд. 5.6).

### 5.6 `data/energy_control_sources.csv`, `energy_control_signals.csv`, `hooks._load_sources_signals(env)`

Джерела (колонки як у W1 `energy_sources.csv`; `module='energy_control'`, `read_enabled=1`, `write_enabled=0`; створюються ідемпотентно, наявні не змінюються):

| `code` | Тип | Параметри | Обладнання |
|---|---|---|---|
| `MB-U73-SWB-CMD` | `modbus_tcp`, unit 73, host `iot-sim`, порт 502, `timeout_s=3`, `retries=2`, `max_block=125`, `gap_max=8` | вікно керування контролера ГРЩ (HR 200…299; ПРИПУЩЕННЯ A-45, на об'єкті — документ контролера) | `SWB-1` |
| `ENERGY-CTL` | `energy_ctl`, `params={"engine": {"tick_s": 2, "config_poll_s": 10}}` | віртуальне «джерело» рушія й інтентів у збирачі | — |

Сигнали `MB-U73-SWB-CMD` (Modbus FC3 читання HR; запис FC6 в ту саму адресу; тип u16; `R/W`; `kind=gauge`, якщо не вказано; `period_s=10`, `store_period_s=300`, `viewer_visible=0`; `write_enabled=0` у даних для всіх):

| Код сигналу | HR | R/W | Одиниця / масштаб | Семантика |
|---|---|---|---|---|
| `energy_control/ctl/heartbeat` | 290 | R | лічильник | контролер живий (росте щосекунди, 0…65535) |
| `energy_control/ctl/remote` | 291 | R | 0/1 | 1 — дистанційне керування дозволено (перемикач «Місцеве/Дистанційне»), `kind=state` `["local","remote"]` |
| `energy_control/qs/cmd` | 200 | W | 0 нічого, 1 розімкнути, 2 замкнути | контролер виконує й скидає в 0 |
| `energy_control/qs/ack` | 201 | R | 0 немає, 1 виконано, 2 відмовлено блокуванням контролера, 3 збій | результат останньої команди |
| `energy_control/ats/parallel_lock` | 202 | R | 0/1 | блокування паралельної роботи T1/T2 від АВР |
| `energy_control/pfc/mode` | 210 | RW | 0 ручний (ступені вимкнені), 1 авто | |
| `energy_control/pfc/cos_target` | 211 | RW | ×0,01 | 95 = 0,95 (E-10) |
| `energy_control/bess/mode` | 220 | RW | 0 авто, 1 примусовий заряд, 2 примусовий розряд, 3 утримання (0 кВт) | |
| `energy_control/bess/setpoint_kw` | 221 | RW | кВт 0…200 | |
| `energy_control/bess/until_soc` | 222 | RW | % 0…100 (0 — без межі) | заряд зупиняється при ≥, розряд — при ≤ |
| `energy_control/bess/valid_s` | 223 | RW | с 0…65535 | **сторожовий таймер**: після спливу контролер повертає режим 0 (авто) |
| `energy_control/bess/remaining_s` | 224 | R | с | залишок `valid_s` |
| `energy_control/bess/reserve_pct` | 225 | R | % | підлога розряду контролера (30) |
| `energy_control/bess/ack` | 226 | R | 0 прийнято, 2 відмовлено (підлога SOC/температура), 3 збій | |
| `energy_control/bess/temp_c` | 227 | R | ×0,1 °C | температура шафи |
| `energy_control/chp/cmd` | 230 | W | 0 нічого, 1 пуск, 2 зупинка | |
| `energy_control/chp/ack` | 231 | R | 0 немає, 1 виконано, 2 відмовлено (газ/дозвіл/збій), 3 збій | |
| `energy_control/chp/permit` | 232 | R | 0/1 | дозвіл оператора КГУ |
| `energy_control/chp/gas_bar` | 233 | R | ×0,01 бар | тиск газу (210 = 2,10) |
| `energy_control/air/setpoint_bar` | 240 | RW | ×0,01 бар | уставка тиску (700 = 7,00) |
| `energy_control/air/min_consumer_bar` | 241 | R | ×0,01 бар | мінімальний тиск споживачів (620) |
| `energy_control/pv/limit_pct` | 250 | RW | % 0…100 | обмеження потужності інверторів СЕС (100 — без обмеження) |
| `energy_control/shed/CHARGING/limit_pct` | 260 | RW | % 0…100 | ліміт навантаження (100 — без ліміту, 0 — вимкнено) |
| `energy_control/shed/RV-ALL/limit_pct` | 261 | RW | % | те саме |
| `energy_control/shed/DRY-1/limit_pct` | 262 | RW | % | |
| `energy_control/shed/COMPRESSOR/limit_pct` | 263 | RW | % | |
| `energy_control/shed/LP-1/limit_pct` | 264 | RW | % | |
| `energy_control/shed/valid_s` | 270 | RW | с | **сторожовий таймер** обмежень скидання й `pv/limit_pct`: після спливу всі ліміти повертаються до 100 % |

**Формат `address`** (JSON за `td_telemetry` Додаток A.1; запис — як у плагіна `modbus_tcp`: `raw = (value − offset) / scale`, `address.write.fc/addr`): `{"fc":3,"addr":221,"type":"u16","write":{"fc":6,"addr":221}}`; для сигналів із масштабом ×0,01 — додатково `"scale":0.01` (`pfc/cos_target`, `air/setpoint_bar`, `air/min_consumer_bar`, `chp/gas_bar`) або 0,1 (`bess/temp_c`); `kind=state` (`ctl/remote`) — `"map":{"0":"local","1":"remote"}`; сигнали лише для читання — без `write`. Рушій і Odoo оперують **інженерними** значеннями (кВт, бар, %, с), регістри — сирі u16. `unit` Modbus береться з параметрів джерела (73).

Сигнали `ENERGY-CTL`: `energy_control/intent` (`kind=event`, `write_enabled=0`; єдиний «сигнал, що записується» для інтентів; `address={}`), `energy_control/auto/heartbeat` (`counter`, 10 с; публікує рушій, значення — лічильник тіків), `energy_control/auto/{peak,self,pfc,night,backup,chp}/state` (`kind=state`, `states=["off","armed","active","warn"]`, `store_period_s=60`, пише рушій; `alarm_states` не задано). Усього **36 сигналів** (28 + 8) і **2 джерела**. Порогів і `alarm_states` для сигналів керування не задано (щоб не створювати заявки ТО): подія «Контролер у місцевому режимі» формується в R-44 п.5.

Очікуваний результат `post_init_hook` на демо-БД після W1 (`td.source` 136): `td.source` 138 (+2), `td.signal` модуля `energy_control` +36; `td.energy.scenario` 6; `td.energy.command.kind` 16; `td.energy.interlock` 20; `td.energy.shed.item` 5; `td.energy.schedule.slot` ≥ 10 (R-54); `td.energy.control.state` 1; повторне `-u` нічого не змінює (AC-229, AC-235).

### 5.7 `neutralize.sql`

`UPDATE ir_config_parameter SET value='False' WHERE key IN ('td.energy_control.write_enabled','td.energy_control.automation_enabled','td.energy_control.remote_switching_enabled');` `UPDATE td_source SET write_enabled=false, read_enabled=false WHERE module='energy_control';` `UPDATE td_signal SET write_enabled=false WHERE module='energy_control';` `UPDATE ir_cron SET active=false WHERE id IN (… 3 нових кронів …)`; `UPDATE td_command SET state='cancelled' WHERE origin='energy' AND state IN ('queued','sent');`.

## 6. Крони й фонові процеси

Усі — `user_id=base.user_root`, `try/except` із `_logger.exception`, без проброса виключення.

| XML-id | Назва | Інтервал | Метод | Один прогін | Ліміт |
|---|---|---|---|---|---|
| `cron_td_energy_control_expire` | Керування: завершення прострочених | 1 хв | `td.energy.action._cron_expire` | R-40 п.12: `prepared` із `token_expires_at < now` → `expired`; `awaiting_second` із `second_expires_at < now` → `expired`; `queued/sent` команда прострочена → `expired`; `executing` довше за `exec_timeout_s + 30` без звіту → `failed` (`error="Немає підтвердження виконання від збирача: перевірте пристрій вручну"`) і подія `td.energy.event` `kind='control'`; конфіг-дії з `now − finished_at > apply_timeout_s` і `applied=False` → подія «Збирач не застосував конфігурацію v{N}» (одноразово) | ≤ 2 с |
| `cron_td_energy_control_plan` | Керування: план дня | 60 хв (`nextcall` hh:05) | `td.energy.schedule.slot._cron_plan` | R-54 для `plan_horizon_days` діб; видалення планових слотів старших за 2 доби | ≤ 3 с |
| `cron_td_energy_control_watch` | Керування: нагляд за рушієм | 1 хв | `td.energy.control.state._cron_watch` | якщо `automation_enabled` і `heartbeat_at` старший за `heartbeat_stale_s·4` — подія `td.energy.event` `level='bad'`, `kind='control'`, `code='CTRL-HEARTBEAT'`, «Рушій автоматики не на зв'язку» (`dedup_min=15`); авторозв'язання при відновленні (`_td_auto_resolve`); події `kind='control'` старші за 24 год → `resolved`; перерахунок `config_etag` (R-43 п.1); `bus.tick('engine')` | ≤ 1 с |

Не діють при вимкненому `td.energy.read_enabled` лише `plan` і `watch`; `expire` — завжди.

## 7. HTTP/JSON API

Виклики ORM-RPC (`orm.call`) — від імені користувача (методи `@api.model` моделі `td.energy.control`, M-35); усі відповіді — JSON-сумісні dict. HTTP-маршрути — для збирача (Bearer-токен `td.collector`). Помилки Odoo — `AccessError`/`UserError`/`ValidationError` з українським текстом (наведені нижче). Часові поля відповідей — ISO UTC (`…Z`), «години Києва» — `HH:MM`.

| ID | Сигнатура / маршрут | Вхід → вихід | Помилки |
|---|---|---|---|
| API-16 | `td.energy.control.get_control()` | → JSON екрана (7.1) | без групи → `AccessError("Немає доступу до Енергетики.")` |
| API-17 | `td.energy.control.prepare(kind, params=None, advice_id=None)` | `kind` — `td.energy.command.kind.code` або ключ інтента рекомендації W3 (R-55 п.6); → відповідь `prepare` (7.2) | не `manager` → `AccessError("Керувати енергетикою може лише енергетик.")`; невідомий/неактивний вид → `UserError("Невідома команда: %s.")`; `available=False` → `UserError("Команда «%s» недоступна: %s.")`; `ValidationError` параметрів (M-31); `executor in (intent, genset)` і `write_enabled=False` → `UserError("Керування вимкнено: td.energy_control.write_enabled. Зверніться до адміністратора.")` |
| API-18 | `td.energy.control.confirm(token)` | → `{"action_id","state","state_label","needs_second","message","blocked_reason"}` | токен невідомий → `UserError("Підтвердження не знайдено. Відкрийте діалог знову.")`; чужий токен → `AccessError("Токен належить іншому користувачу.")`; прострочений → `UserError("Час підтвердження минув. Відкрийте діалог знову.")`; жорстка перевірка → дія `blocked`, відповідь (без виключення) з `blocked_reason` |
| API-19 | `td.energy.control.confirm_second(action_id)` | → як API-18 | той самий користувач → `UserError("Друге підтвердження має дати інший енергетик.")`; стан ≠ `awaiting_second` → `UserError("Дія не очікує другого підтвердження.")`; прострочено → `UserError("Час другого підтвердження минув.")`; не `manager` → `AccessError` |
| API-20 | `td.energy.control.cancel(token)` | → `{"action_id","state":"cancelled"}` (ідемпотентно) | чужий токен → `AccessError` |
| API-21 | `td.energy.control.undo(action_id)` | → відповідь `prepare` для зворотної дії (`origin='undo'`) | `undo_available=False` → `UserError("Скасування недоступне: %s.")` |
| API-22 | `td.energy.control.get_action(action_id)` | → `{"id","name","state","state_label","summary","detail","result_text","error","finished_at","needs_second","checks","collector_checks","undo_available"}` | чужа дія без групи → `AccessError` |
| API-23 | `td.energy.control.get_schedule(day=None)` | `day` `YYYY-MM-DD` (Київ), default сьогодні → `{"day","now","rows":[…]}` (R-54 п.8) | — |
| API-24 | `GET /td/energy/automation/config` | Bearer; `If-None-Match` → 200 JSON (7.3) або 304 | 401 `unauthorized`, 403 `forbidden`, 405 `method_not_allowed`, 429 `rate_limited` |
| API-25 | `POST /td/energy/automation/state` | Bearer; тіло 7.4 → `{"accepted_actions","accepted_events","rejected":[…],"config_version","config_etag","server_time"}` | 400 `bad_json`/`bad_schema`, 401, 403 `collector_mismatch`, 413 `payload_too_large` (> 256 КБ), 429 |
| API-26 | `td.command.payload` для `energy_control/intent` → `plugin.call(signal, payload)` (7.5) | → `result_data` збирача | див. 7.5 |
| API-27 | `td.energy.control.get_node_actions(code)` | `code` вузла схеми → `[{"code","label","kind","cls","enabled","disabled_reason"}]` (для `QS`, `BESS`; інші вузли — `[]`) | — |
| API-28 | `td.energy.control.get_journal(limit=None, before_id=None, origin=None)` | → `{"items":[journal…],"more":bool}` (R-56) | — |

### 7.1 Відповідь API-16 (ключі й типи; приклад — 14:20 макета)

```json
{"ts":"2026-10-18T11:20:03Z","now_local":"14:20",
 "meta":{"role":"manager","can_prepare":true,"can_confirm_b":false,"write_enabled":true,"automation_enabled":true,"remote_switching_enabled":true,
         "limit_kw":760,"contract_kw":800,"refresh_s":30},
 "engine":{"connected":true,"mode":"auto","reason":null,"heartbeat_at":"2026-10-18T11:20:01Z","age_s":2,
           "config_version":17,"applied_version":17,"label":"Контролер ГРЩ і збирач на зв'язку · 14:20","level":"ok"},
 "scenarios":{"on_count":4,"total":6,"items":[
   {"id":1,"code":"peak","title":"Зрізання піку","text":"Тримати імпорт нижче уставки: …","enabled":true,"applied":true,
    "state":"armed","state_kind":"arm","status":"Чергування · запас 402 кВт","chips":["уставка 760 кВт · 95 %","прогноз 15 хв"],
    "params":{"limit_kw":760,"margin_kw":20},"schema":[{"name":"limit_kw","label":"Уставка імпорту","type":"float","min":100,"max":2000,"unit":"кВт"}],
    "can_toggle":true,"pending_action_id":null}]},
 "shed":{"items":[{"id":1,"n":1,"name":"Зарядна станція навантажувачів","how":"відкласти заряд до 30 хв","kw":48,"p_now_kw":13.5,"node_code":"CHARGING","active":true}],
         "sum_kw":174,"never":["аспірація під час роботи верстатів","ІТ і зв'язок","охорона","пожежна автоматика","аварійне освітлення"],
         "never_nodes":["DUST-1","LP-2","LP-3","OFFICE","BOILER"],"can_reorder":true,"limit_kw":760},
 "commands":[{"code":"qs_close","label":"Увімкнути секційний вимикач QS","sub":"секції 1 і 2 разом","cls":"B","resource":"qs","enabled":true,"disabled_reason":null}],
 "pending":[{"id":55,"summary":"Пуск КГУ","prepared_by":"Іваненко І.","second_expires_at":"2026-10-18T11:30:00Z","can_confirm_second":true}],
 "schedule":{"now":14.333,"rows":[{"resource":"bess","name":"BESS","bars":[{"from":7.5,"to":11.0,"label":"розряд · пік","cls":"d","source":"plan"}]}]},
 "journal":[{"id":812,"time":"14:06","what":"Заявка ТО","detail":"PFC-2: ступінь 3 не вмикається","who":"автоматика","result":"створено","result_kind":"info","state":"done","undo_available":false,"awaiting_second":false,"ref":{"model":"maintenance.request","id":48}}],
 "journal_more":false}
```

Правила полів: `engine.level` — `ok` (зв'язок і режим `auto`), `warn` (`hold`/`off`), `bad` (немає зв'язку); `engine.label` — за UI-13; `scenarios.items[].status` — R-43 п.5; `pending` — лише дії `awaiting_second`, видимі `manager`; `commands[].enabled=false` + `disabled_reason` («Немає прав: потрібна роль «Енергетик»», «Керування вимкнено адміністратором», «Команда недоступна: …»); `shed.never` — D-26; без вартості; розмір відповіді ≤ 40 КБ (ТП-10).

### 7.2 Відповідь API-17 `prepare`

```json
{"action_id":55,"token":"Zm9v…","ttl_s":60,"verify_timeout_s":30,"kind":"qs_close","cls":"B","title":"Увімкнути секційний вимикач QS?",
 "text":"Секції 1 і 2 працюватимуть разом. Генерація СЕС піде на навантаження секції 1, експорт через T2 припиниться.",
 "sub":"секції 1 і 2 разом",
 "checks":[{"code":"ats_parallel_lock","label":"Блокування паралельної роботи T1 і T2 від АВР — увімкнено","state":"ok","hard":true,"detail":""},
           {"code":"qs_current_ok","label":"Струм через QS після вмикання ≈ 40 А з 1600 А","state":"ok","hard":true,"detail":"40 А ≤ 1280 А"}],
 "blocked":false,"blocked_reason":null,"needs_second":true,"confirm_label":"Підтвердити (1/2)","disabled_reason":null}
```

`checks[].label` — шаблон `td.energy.interlock.name` з підставленими значеннями; `state` ∈ `ok|fail|unknown`; `blocked` — є `hard` зі `state='fail'` або (`hard`, `fail_closed`, `unknown`); `blocked_reason` — перша така перевірка; `confirm_label` — «Виконати» (клас A або `chief`) / «Підтвердити (1/2)»; `verify_timeout_s` — `td.energy_control.verify_timeout_s` (клієнт обмежує опитування `get_action`: `verify_timeout_s + 30`); повторний `prepare` того самого користувача з тим самим `kind` і `params` протягом 5 с повертає той самий запис з новим токеном без створення дубля (R-40 п.1).

### 7.3 Відповідь API-24 `GET /td/energy/automation/config` (контракт збирача; C-39)

```json
{"schema":1,"config_version":17,"etag":"9f2c…","server_time":"2026-10-18T11:20:03Z","tz":"Europe/Kyiv",
 "flags":{"automation_enabled":true,"write_enabled":true,"remote_switching_enabled":true},
 "engine":{"tick_s":2,"config_poll_s":10,"stale_hold_s":30,"min_write_interval_s":10,"max_writes_per_min":30,
           "exec_timeout_s":60,"step_timeout_s":8,"verify_timeout_s":30,"shed_restore_step_s":20},
 "plant":{"contract_kw":800,"pv_kwp":920,"bess_kwh":387,"bess_max_kw":200,"bess_reserve_pct":30,"cos_phi_target":0.95,
          "genset_kw":507,"chp_kw":800,"qs_rating_a":1600},
 "scenarios":{"peak":{"enabled":true,"params":{"limit_kw":760,"…":0}},"self":{"enabled":false,"params":{}},"pfc":{"enabled":true,"params":{"cos_target":0.95}},
              "night":{"enabled":true,"params":{"from":"23:00","to":"06:30","days":[1,2,3,4,5,6,7],"vent_mode":"VEL","day_vent_mode":"VE","vent_pct":30,"light_scene_number":1,"light_scene_day_number":2,"heat_setpoint_c":16.0}},
              "backup":{"enabled":true,"params":{}},"chp":{"enabled":false,"params":{}}},
 "shed":[{"id":1,"seq":1,"node":"CHARGING","action":"defer","param":30,"kw":48,"critical":false,"signal":"energy_control/shed/CHARGING/limit_pct","condition":"none","condition_value":null}],
 "never_shed":["DUST-1","LP-2","LP-3","OFFICE","BOILER","EF-ELEC","EF-CHG"],
 "slots":[{"id":9,"resource":"chp","date":null,"weekdays":"1111100","from":16.0,"to":19.0,"mode":"run","setpoint_kw":null}],
 "tariff":{"zones":[{"from":0.0,"to":7.0,"price":3.4},{"from":7.0,"to":23.0,"price":8.4},{"from":23.0,"to":24.0,"price":3.4}],"currency":"UAH"},
 "bms":{"night":{"vent":[{"unit":"RV-01","mode_signal":"ventilation/units/RV-01/mode","sp_night_signal":"ventilation/units/RV-01/setpoint_night_c"}],
                 "light":[{"group":"LT-01","scene_signal":"lighting/groups/LT-01/scene","aisle":false}]},
        "vent_eco":{"vent":[{"unit":"RV-01","mode_signal":"ventilation/units/RV-01/mode"}]},
        "light_break":{"light":[{"group":"LT-01","scene_signal":"lighting/groups/LT-01/scene","aisle":false}]}},
 "signals":{"qs_cmd":"energy_control/qs/cmd","qs_ack":"energy_control/qs/ack","qs_state":"energy/cells/QS/state","ats_lock":"energy_control/ats/parallel_lock",
            "pfc_mode":"energy_control/pfc/mode","pfc_cos":"energy_control/pfc/cos_target","bess_mode":"energy_control/bess/mode","bess_sp":"energy_control/bess/setpoint_kw",
            "bess_until":"energy_control/bess/until_soc","bess_valid":"energy_control/bess/valid_s","bess_ack":"energy_control/bess/ack","bess_temp":"energy_control/bess/temp_c",
            "chp_cmd":"energy_control/chp/cmd","chp_ack":"energy_control/chp/ack","chp_permit":"energy_control/chp/permit","chp_gas":"energy_control/chp/gas_bar",
            "air_sp":"energy_control/air/setpoint_bar","air_min":"energy_control/air/min_consumer_bar","pv_limit":"energy_control/pv/limit_pct",
            "shed_valid":"energy_control/shed/valid_s","remote":"energy_control/ctl/remote","ctl_hb":"energy_control/ctl/heartbeat",
            "auto_hb":"energy_control/auto/heartbeat"},
 "inputs":{"p_total":"energy/totals/p_now","air_bar":"equipment/COMPRESSOR/pressure_bar","grid_kw":"infra/totals/grid_kw","export_kw":"infra/totals/export_kw","pv_kw":"infra/totals/pv_now","bess_kw":"infra/totals/bess_kw",
           "bess_soc":"infra/totals/bess_soc","bess_state":"infra/bess/state","chp_state":"infra/chp/state","chp_kw":"infra/totals/chp_kw","chp_hours":"infra/chp/hours",
           "ats_pos":"infra/ats/position","src1_ok":"infra/ats/src1_ok","s1_p":"energy/sections/S1/p_kw","s2_p":"energy/sections/S2/p_kw",
           "pfc1_fault":"energy/cells/PFC-1/fault_step","pfc2_fault":"energy/cells/PFC-2/fault_step","fire_state":"fire/panel/state"},
 "derived":{"energy/totals/p_now":{"op":"sum","terms":[{"code":"energy/lines/C1/p_now","k":1.0},{"code":"energy/lines/C2/p_now","k":1.0}]},
            "energy/sections/S1/p_kw":{"op":"sum","terms":[{"code":"energy/lines/C1/p_now","k":1.0}]},
            "infra/ats/src1_ok":{"op":"ge","code":"infra/ats/src1_state","value":1},
            "infra/totals/grid_kw":{"op":"sum","terms":[{"code":"energy/cells/Q1/p_now","k":1.0},{"code":"energy/cells/Q2/p_now","k":1.0}],"clamp_min":0.0,"zero_if":{"code":"infra/ats/position","eq":3}},
            "infra/totals/pv_now":{"op":"sum","terms":[{"code":"infra/pv/PV-INV-1/p_kw","k":1.0,"min":0.0}]}},
 "interlocks":{"qs_current_ok":{"hard":true,"fail_closed":true,"params":{"rating_a":1600,"max_ratio":0.8,"cos_phi":0.95}}},
 "limits":{"bess_kw_max":200,"pv_limit_min_pct":10,"air_bar_min":5.0,"air_bar_max":8.5}}
```

Правила: (1) **Ключі `schema`, `config_version`, `etag`, `server_time` не входять у канонічний JSON для ETag** (R-43 п.2); (2) значення `flags.*` читаються з `ir.config_parameter` при кожному запиті; (3) `signals`/`inputs` — логічні імена → коди сигналів; плагін не містить жорстко закодованих кодів (окрім назв логічних ключів); (4) `bms` будується з `td.bms.hvac.unit` (`kind='roofvent'`, `mode_signal_id`, `sp_night_signal_id`) і `td.bms.light.group` (`scene_signal_id`; `aisle = (fixture_kind == 'highbay_rack')`; групи `aisle` не димуються й не вимикаються сценою «Перерва»); якщо в `td_bms` порожні сигнали — відповідні масиви порожні (нічний режим → стан `warn` «немає цілей BMS»); (5) `limits` — *межі, які Odoo може лише звужувати* відносно констант коду збирача (R-44 п.6); (6) розмір відповіді ≤ 64 КБ; (7) відповідь не містить вартості, токенів, паролів; (8) **`derived` (D-47)** — формули для входів `inputs`, які обчислює Odoo (EN-DERIVED), щоб автоматика працювала без Odoo: ключ — код входу, значення — `{"op": …}`. Операції: `sum` — `terms:[{"code","k"[,"min"]}]`, значення `Σ k·max(min, x)` (`min` необов'язковий — нижня межа сирого значення терма), необов'язкові `clamp_min` (нижня межа результату) і `zero_if:{"code","eq"}` (результат 0, якщо сигнал дорівнює `eq`; сигналу немає — умова ігнорується, як `position is not None` в Odoo); `ge` — `1.0`, якщо значення сигналу `code` ≥ `value`, інакше `0.0`. Значення обчислюється плагіном із `LiveCache`; будь-який терм (окрім `zero_if`) відсутній або старший за `max_age_s` → похідний вхід відсутній (fail-closed). Блок входить у канонічний JSON, `config_version` і ETag. Коди термів — сирі сигнали за лініями `kind='line'` (`energy/lines/<код>/p_now`), вводами (`energy/cells/Q1|Q2/p_now`), АВР (`infra/ats/src1_state`, `infra/ats/position`) та інверторами СЕС (`infra/pv/PV-INV-<n>/p_kw`)

### 7.4 Тіло API-25 `POST /td/energy/automation/state` (раз на 10 с або негайно при зміні дії)

```json
{"collector":"COL-1","config_version_applied":17,"sent_at":"2026-10-18T11:20:03Z",
 "engine":{"mode":"auto","reason":null,"started_at":"2026-10-18T06:00:00Z","ticks":19401,"tick_ms_p95":14,"writes_last_min":2,
           "controller_remote":true},
 "scenarios":{"peak":{"state":"armed","ts":"…","facts":{"margin_kw":402,"proj_kw":358,"grid_kw":356}},
              "self":{"state":"off","ts":"…","facts":{}},
              "pfc":{"state":"warn","ts":"…","facts":{"fault":"PFC-2 ступінь 3"}}},
 "actions":[{"id":55,"idem":"3f…","state":"done","step":4,"steps_total":4,"ts":"…","result":"BESS: заряд 50 кВт до 16:00 (valid_s 5700)","error":null,
             "checks":[{"code":"bess_soc_lt_limit","state":"ok","hard":true,"detail":"82 % < 95 %"}]}],
 "events":[{"event_id":"b9…(uuid4 hex)","ts":"…","scenario":"peak","kind":"auto_step","text":"BESS · розряд 62 кВт","signal":"energy_control/bess/mode","value":2,"result":"виконано"}]}
```

Відповідь: `accepted_actions` — кількість застосованих елементів `actions[]` (стан дії лише «вперед» у порядку `executing < done|failed|blocked`; повторний звіт того самого стану — ідемпотентний, без ефектів); `accepted_events` — нові `event_id` (повторні ігноруються); `rejected` — `[{"id" | "event_id", "reason": "unknown_action|already_final|bad_state|duplicate"}]`; `config_version`, `config_etag` — для негайного `GET config`, коли `etag` відрізняється від кешу плагіна. Обмеження: `actions` ≤ 100, `events` ≤ 200 за запит, тіло ≤ 256 КБ. Оновлює: `td.energy.control.state` (`heartbeat_at`, `engine_mode`, `engine_info`, `applied_version = max(applied_version, config_version_applied)`), `td.energy.scenario._td_engine_update`, `td.energy.action._td_on_engine`/`_td_log_auto`, `bus.tick('engine'|'scenario'|'action')`.

### 7.5 API-26: інтент (`td.command.payload`) і результат (`result_data`)

Odoo створює **одну** `td.command` на дію: `signal_id = energy_control/intent`, `payload`, `value=0`, `origin='energy'`, `expires_at = now + command_ttl_s`, `energy_action_id`.

```json
{"v":1,"action_id":55,"idem":"3f9a…(sha1)","kind":"bess_charge","cls":"A","params":{"power_kw":50,"until":"16:00","soc_limit_pct":95},
 "requested_by":"ivanenko","requested_at":"2026-10-18T11:20:30Z","expires_at":"2026-10-18T11:22:30Z","tz":"Europe/Kyiv","limits":{"bess_kw_max":200}}
```

`kind` ∈ `qs_close, qs_open, bess_charge, bess_discharge, bess_stop, chp_start, chp_stop, light_break, light_restore, vent_eco, vent_restore, air_setpoint` (виконавці `intent`); решта видів інтентом не передаються. Схема й межі `params` — R-42 (збирач перевіряє незалежно від Odoo; JSON-схема `intent.schema.json` у пакеті плагіна). Ядро збирача (`CommandLoop`) викликає `plugin.call()` (`CALL_TIMEOUT_S = 10 с`): плагін **лише приймає й ставить у чергу** інтент і повертає `result_data` ≤ 64 КБ:

```json
{"accepted":true,"run_id":"r-3f9a","state":"executing","checks":[{"code":"controller_remote","state":"ok","detail":"remote=1"}]}
```

або відмова без виконання: `{"accepted":false,"state":"blocked","reason":"Блокування: ats_parallel_lock — не виконано (lock=0)","checks":[…]}`, `{"accepted":false,"state":"rejected","reason":"unknown kind"|"bad params: …"|"expired"|"busy: bess"}`; повторна доставка того самого `idem` — відповідь зі збереженого результату (`"duplicate":true`) без повторного виконання (R-52 п.6). Підсумковий стан виконання (`done|failed`) приходить окремо через API-25 `actions[]`. `td.command` отримує `done` (транспорт прийнято), `failed` — лише якщо плагін викинув виключення/тайм-аут `call()`.

### 7.6 Формат запису журналу (API-28)

`{"id","time":"HH:MM" (Київ; для старших за добу "DD.MM HH:MM"),"what","detail","who","result","result_kind":"ok|info|bad|muted","state","undo_available","awaiting_second","ref":{"model","id"}|null}`; `what`/`detail`/`who`/`result` — D-19; сортування за часом спадання; ключів вартості немає.

## 8. Сервісна частина

### 8.1 Плагін збирача `td_collector_energy` (власник C; E-03, E-05, FR-55…FR-57)

**Місце в збирачі.** `td_collector_energy` — Python-пакет-плагін у групі entry points `factory3d_collector.plugins` (як `f3d_collector_bms`, `f3d_collector_yard`): тип джерела `energy_ctl`, клас `EnergyCtlPlugin(SourcePlugin)`, `push_mode = True`. Єдине джерело цього типу — `ENERGY-CTL` (розд. 5.6). Плагін об'єднує **цикл автоматики** (6 сценаріїв, R-44…R-51) і **виконавця інтентів** оператора (R-52); пише в пристрої через інші джерела збирача (Modbus `MB-U73-SWB-CMD`, BMS), використовуючи ті самі плагіни протоколів, прапори запису й allowlist. PLC зможе перехопити автоматику пізніше через той самий контракт конфігу/уставок/розкладу (E-05): плагін — лише одна з реалізацій API-24/25.

#### 8.1.1 Структура пакета

```
services/collector_plugins/td_collector_energy/
├── pyproject.toml            name `td-collector-energy`, requires-python >=3.12, залежностей немає (aiohttp, jsonschema — з ядра/тесту),
│                             [project.entry-points."factory3d_collector.plugins"] energy_ctl = "td_collector_energy:EnergyCtlPlugin"
├── README.md, CHANGELOG.md
├── td_collector_energy/
│   ├── __init__.py           експорт EnergyCtlPlugin
│   ├── plugin.py             EnergyCtlPlugin: validate/connect/subscribe/call/health/disconnect
│   ├── config.py             завантаження API-24 (ETag, кеш, перевірка схеми, диф версій), клас Config (frozen dataclass)
│   ├── inputs.py             Inputs: знімок живих значень з ctx.live зі свіжістю; похідні (прогноз 15 хв, ковзні вікна)
│   ├── derived.py            похідні входи за блоком `derived` API-24 (D-47): `sum` (з `min` терма, `clamp_min`, `zero_if`) і `ge`; терм відсутній/несвіжий → вхід відсутній
│   ├── engine.py             Engine: цикл, режими off/hold/auto, арбітраж ресурсів, перекриття (override)
│   ├── actuator.py           Actuator: запис «лише за зміни», мін. інтервал, запобіжник частоти, зворотне читання
│   ├── scenarios/{__init__,common,peak,selfcons,pfc,night,backup,chp}.py   чисті функції step(...) за R-45…R-50
│   ├── interlocks.py         реєстр CHECKS (R-41), оцінка за Inputs
│   ├── intents.py            kind → кроки/перевірки/межі params (R-42), JSON-схеми
│   ├── executor.py           Executor: черга інтентів, кроки, верифікація, fail-safe, ідемпотентність (R-52)
│   ├── store.py              атомарне збереження стану (JSON), відновлення після рестарту
│   ├── reporter.py           пакетний POST API-25, буфер при збої, дедуп подій
│   ├── timeutil.py           Europe/Kyiv, вікна через північ, DST
│   └── schemas/{params.energy_ctl.json, address.energy_ctl.json, config.schema.json, intent.schema.json}
└── tests/                    розд. 13.1 (UT-PY), `tests/stand/test_tk_energy.py` (ТК)
```

#### 8.1.2 Розширення ядра збирача (C-40; адитивне, зворотно сумісне; власник C)

| Файл | Зміна |
|---|---|
| `collector/core/live.py` (новий) | `LiveCache`: `update(readings: Iterable[Reading])`, `get(code) -> Reading \| None`, `age_s(code, now) -> float \| None`, `snapshot(codes) -> dict`, `note_write(code, value, ts)`, `last_write(code)`; потокобезпечність не потрібна (один event loop); пам'ять — рядок на код, без історії |
| `collector/core/scheduler.py` | після `apply_signal_scale` у циклі опитування й в `Emitter.emit` — виклик `live.update(...)` (якщо `live` передано; `Scheduler`/`Emitter` отримують необов'язковий аргумент `live=None`) |
| `collector/core/commands.py` | новий `CommandLoop.read_now(code) -> Reading \| None`: разове читання сигналу через `plugin.poll([signal])` з масштабом ядра й оновленням `LiveCache` (тайм-аут `call_timeout_s`; без запису в буфер); новий `CommandLoop.write_direct(code, value=None, text=None, *, expires_at=None) -> str`: ті самі перевірки, що `_execute` (знайти сигнал; `source.write_enabled`; `signal.write_enabled`; `registry.write_enabled`; `settings.write_enabled`; `expires_at`), виклик `plugin.write()` з тайм-аутом `call_timeout_s`; помилки — `WriteRefused(reason)` (новий клас у `core/errors.py`) або виключення плагіна; **без** запису в буфер результатів |
| `collector/plugins/base.py` | `PluginContext` отримує необов'язкові поля `live: LiveCache \| None = None`, `write_signal: Callable[..., Awaitable[str]] \| None = None` (= `write_direct`), `read_signal: Callable[[str], Awaitable[Reading \| None]] \| None = None` (= `read_now`), `odoo: OdooClient \| None = None`, `clock: Clock \| None = None`, `state_dir: Path \| None = None` (каталог `settings.state_file`); старі плагіни не змінюються |
| `collector/core/app.py` | `Collector` створює `LiveCache`, передає в `Scheduler`/`Emitter`; `_make_ctx` заповнює нові поля |
| `collector/core/odoo_client.py` | якщо загального `request(method, path, …)` недостатньо — тонкі методи `automation_config(etag)` і `automation_state(body)` (ті самі заголовки Bearer, `If-None-Match`, тайм-аути, `OdooError`) |
| `requirements-extra.txt` | рядок `td-collector-energy @ file:///opt/plugins/td_collector_energy` |

Тести ядра: `tests/unit/test_live.py`, `test_ctx_extension.py`, `test_write_direct.py` (AC-236…AC-238); наявні тести ядра лишаються зеленими.

#### 8.1.3 Життєвий цикл плагіна

- `validate(source)`: `params` за `params.energy_ctl.json` (`engine.tick_s` 1…10, `engine.config_poll_s` 5…60); єдиний екземпляр: другий `connect()` → `ConnectError("energy_ctl: дублікат джерела")`.
- `connect()`: завантажує `Store` (стан із диска; відкидає старший за 7 діб), першу конфігурацію API-24 (з кешу `Store`, якщо Odoo недоступна ≤ 7 діб; інакше — стан `off`, `health=online` без дій; повторні спроби з бекофом 1→60 с); мережевого з'єднання з пристроями не відкриває (це роблять їхні плагіни).
- `subscribe()`: створює задачі `_config_loop` (опитування API-24 раз на `config_poll_s`, `If-None-Match`), `_engine_loop` (R-44; період `tick_s`), `_report_loop` (API-25 раз на 10 с або негайно при зміні стану дії), `_heartbeat_loop` (раз на 10 с `ctx.emit(Reading("energy_control/auto/heartbeat", value=ticks))` і станів сценаріїв при зміні). Повертається одразу.
- `call(signal, payload)`: лише для `energy_control/intent`; перевірки `v`, схеми, `expires_at`, `idem` (повтор → збережений результат), жорстких блокувань (R-41) **синхронно**; ставить у чергу `Executor`; повертає `result_data` API-26 за ≤ 1 с (ніколи не чекає виконання кроків). Невідомий сигнал → `NotSupported`.
- `write()` — `NotSupported`. `health()` — `online`, якщо живий `_engine_loop` (тік не старший за `3·tick_s`) і конфіг валідний; інакше `error` з причиною.
- `disconnect()`: зупиняє задачі; **не** виконує записів у пристрої (безпечний стан забезпечують сторожові таймери контролера, R-53 №7); зберігає `Store`.

#### 8.1.4 Логування, метрики, оточення

Логер `collector.plugin.energy_ctl.ENERGY-CTL`; рівні: `INFO` — зміна режиму рушія, зміна `config_version`, запуск/завершення інтента, зміна ступеня сценарію; `WARNING` — блокування, відмови пристрою, несвіжі входи; `DEBUG` — тік. Токени/секрети не друкуються. У `Health.stats` — `ticks`, `tick_ms_p95`, `writes_last_min`, `intents_total`, `blocked_total`, `config_version`, `mode`. Змінні оточення збирача (наявні): `F3D_WRITE_ENABLED` (запобіжник 5), `F3D_COMMANDS_POLL_S` (стенд 2 с замість 5), `F3D_STATE_FILE` (каталог стану плагіна `td_energy_ctl.json`).

### 8.2 Емулятор `iot_sim`: вікно керування контролера ГРЩ і реакції моделей (власник C; FR-59, R-59, C-47)

Карта регістрів — ПРИПУЩЕННЯ для емулятора (A-45); на об'єкті діє документ контролера, зміни лише в `address` сигналів (дані), код плагіна не змінюється. Адреси, типи й семантика регістрів — таблиця розд. 5.6 (unit 73, HR 200…291, u16, FC3/FC6).

| Файл | Зміна |
|---|---|
| `iot_sim/protocols/modbus_maps/swbctl.py` (новий) | `UNIT = 73`; `build(ctx)` додає HR 200…291 у `ctx.unit(73, "SWB-CTRL")`: читання з прапорів світу (`ctl.*`) і сигналів; запис через `set`-колбеки; `ctx.write_accept == False` → `ModbusError(4)`; значення поза межами → `ModbusError(3)`; команди (QS, КГУ) пишуть `ctx.command(UNIT, "QS cmd = 2")` у події світу; регістри `cmd` самоочищаються на наступному тіку |
| `iot_sim/protocols/modbus_maps/__init__.py` | `swbctl` додається до списку `mod` у `build_all` (перед `bind_catalog`, власні карти мають пріоритет; HR 100…123 лишаються за `bind_catalog` W1) |
| `iot_sim/models/swb.py` | споживає прапори: `qs_closed` (команда), `pfc_mode`, `pfc_cos_target` (замість лише `settings.pfc_cos_target`); QS: команда `2` (замкнути) виконується, якщо `ats_parallel_lock == 1` і немає острова, інакше `ack = 2`; `1` (розімкнути) — завжди; heartbeat `ctl/heartbeat` (+1 за симульовану секунду); `ctl/remote` (прапор `ctl_remote`, default 1): при `0` усі команди ігноруються з `ack = 2` |
| `iot_sim/models/bess.py` | режими `bess_mode`: `0` авто (наявна поведінка; прапор `bess_auto_idle` → 0 кВт), `1` примусовий заряд `+min(setpoint, 200)` до `until_soc` або SOC 100, `2` примусовий розряд `−min(setpoint, 200)`, поки SOC > `max(until_soc, reserve_pct)`, `3` утримання 0 кВт; сторожовий таймер `valid_s` (зменшується на `dt`; у 0 → режим `0`, `remaining_s` = залишок); відмова `ack = 2` для розряду при SOC ≤ `reserve_pct` (30) або температурі шафи > 40 °C; `temp_c = 25 + 0,05·\|P\|` |
| `iot_sim/models/chp.py` | `chp/cmd`: `1` → `chp_run = True`, якщо `permit == 1` і `gas_bar ≥ 1,5`, інакше `ack = 2`; `2` → `chp_run = False`; тривалість запуску — прапор `chp_start_s` (default 60; D-33); `gas_bar` — прапор (default 2,10; сценарій `chp_no_gas` → 0,80); наявний HR 40007 лишається джерелом тих самих прапорів |
| `iot_sim/models/compressor.py` | номінальний тиск = `air_setpoint_bar − 0,19` (default уставка 7,00 → 6,81, поведінку W0 збережено); `min_consumer_bar` = 6,20 (const-регістр) |
| `iot_sim/models/pv.py` | потужність кожного інвертора множиться на `pv_limit_pct / 100` (default 100) |
| `iot_sim/models/meter.py` | `consumer_p(world, code)` множиться на `shed_factor(code) = limit_pct / 100` (default 1); сума навантаження додає прапор `extra_load_kw` (може бути від'ємним, лише ≥ `−load`); при `qs_closed` потужності вводів Q1 і Q2 вирівнюються `(P1 + P2) / 2`; сторожовий таймер скидання `shed_valid_s` (у 0 → усі ліміти й `pv_limit_pct` повертаються до 100) |
| `catalog/signals.csv`, `td_iot_sim/data/td_sim_signal.csv` | +28 рядків «новий» для сигналів `MB-U73-SWB-CMD` (розд. 5.6) із номерами `n`, починаючи з наступного вільного; `bind_catalog` не конфліктує з `swbctl.py` |
| `td_iot_sim/data/td_sim_scenario.xml` + `catalog/…` | сценарії: `peak_load` `{extra_kw, duration_s}` (додає `extra_load_kw`), `export_demo` `{export_kw}` (BESS авто в режимі утримання 0 кВт, навантаження підганяється так, щоб експорт = `export_kw`: `load_eff = gen − export_kw` при `gen > export_kw`), `ctl_local` (`ctl_remote = 0`), `chp_no_gas` (`gas_bar = 0,80`) |

Тести: `tests/unit/test_swbctl.py` (регістри, межі, `write_accept`, самоочищення `cmd`, heartbeat), `tests/unit/test_control_models.py` (реакції BESS/КГУ/QS/PFC/повітря/PV/скидання, сторожові таймери, `peak_load`, `export_demo`). Стенд: пакетні сценарії ТК-20…ТК-27 (розд. 13.2).

### 8.3 Тест ДГУ: адаптер ADP-12 у `td_genset_factory3d` (FR-66, R-67; власник A)

Адаптер `adapters/td_genset.py` (єдине місце доступу до `td_genset`, W1 R-14…R-16) отримує `start_test(gen, mode, user) -> dict` (**ADP-12**): (1) `mode == 'idle'` (W2 — лише без навантаження; `load` — Q-29); (2) `gen.sudo()._test_start('idle', user)` (метод `td_genset` `genset_scheduler.py`; група `td_genset.group_tech` перевіряється `td_energy_control` через права «Енергетик»/«Головний енергетик» — у `td_genset` виклик іде з `sudo()`, `_td_check_group` пропускає `env.su`); (3) повертає `{"accepted": True, "minutes": <config.test_minutes>, "test_end": "<iso UTC>", "ref": {"model": "td.genset", "id": gen.id}}`; помилки `UserError` з `td_genset` («Тест уже йде.», «Оберіть варіант тесту…») адаптер пробрасує без змін. Додатково `test_facts(gen) -> dict` (`fuel_pct`, `running`, `test_running` (`gen.test_end`), `island` (`not mains_ok`), `coolant_c`) для перевірок `genset_fuel`, `genset_heater` (`coolant_c ≥ 30` °C), `genset_idle`. Доступ із `td_energy_control` — м'який: `tools/genset_link.py` (`importlib.import_module("odoo.addons.td_genset_factory3d.adapters.td_genset")` за наявності модуля в `ir.module.module` зі станом `installed`; інакше вид `genset_test` має `available=False`, причина «Не встановлено міст td_genset_factory3d»). Тест адаптера — `td_genset_factory3d/tests/test_adp12.py` (AC-275, AC-276; AC-277 — виконавець у `td_energy_control`). `td_genset` не змінюється.

### 8.4 «Енергетика в 3D»: міст `td_energy_viewer3d` і розширення `td_viewer3d` (власник D; FR-62…FR-65, FR-70, C-44, C-45)

Розділ перенесено до [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §8 зі збереженням нумерації 8.4.1…8.4.4: рішення A-52 (окремий міст-модуль `td_energy_viewer3d`, `auto_install`), розширення ядра `td_viewer3d` R-26 (VX-01…VX-05, 8.4.1), payload `energy.layer` (8.4.2), клієнт UI-23…UI-27 (8.4.3), «Відкрити в 3D» (8.4.4).


## 9. Алгоритми й правила

### R-39 Класи команд і права (E-06, A-39; FR-53)

1. Клас задає `td.energy.command.kind.cls` (M-31, розд. 5.3), користувач його не змінює. **Клас A** (роль «Енергетик»): заряд BESS, зупинка BESS, сцена освітлення «Перерва» та її відновлення, вентиляція «Економ» та її відновлення, підтвердження/«взяти в роботу» тривог (W1 A-29). **Клас B** («Головний енергетик» або друге підтвердження іншим «Енергетиком»): перемикання QS (обидва напрями), пуск і зупинка КГУ, розряд BESS, тест ДГУ, уставка тиску повітря, зміна пріоритетів скидання, увімкнення/вимкнення сценарію. За рішенням A-39 до класу B віднесено також дії тієї самої природи, яких E-06 прямо не називає: зміна параметрів сценарію (`scenario_params`), редагування складу скидання (`shed_edit`), ручних слотів (`schedule_edit`) і порогів блокувань (`interlock_param`).
2. Права за матрицею 4.2. «Енергетик» = `group_td_energy_manager`, «Головний енергетик» = `group_td_energy_chief` (W1 §4.2; chief успадковує manager).
3. **Друге підтвердження.** Дія класу B, підготовлена користувачем без `group_td_energy_chief`, після `confirm` отримує стан `awaiting_second` (`needs_second=True`), `second_expires_at = now + second_ttl_s` (600 с). Друге підтвердження (`confirm_second`) дає **інша особа** з `group_td_energy_manager`: `second_by ∉ {prepared_by, confirmed_by}` (SQL-перевірка + Python). Адміністратор без групи енергетика не підтверджує. Після другого підтвердження дія виконується (R-40 п.6). Спливання `second_expires_at` → `expired`.
4. Дія, підготовлена й підтверджена `chief`, виконується одноосібно (`needs_second=False`). `chief` може бути другою особою для дії `manager`.
5. Сповіщення про `awaiting_second`: `bus.tick('action')` (банер на екрані «Керування», D-43) і `mail.activity` (тип «До виконання», строк `second_expires_at`) для ≤ 10 користувачів `group_td_energy_manager`, окрім ініціатора; activity закривається при виконанні, відхиленні або спливанні.
6. Клас скасування (`undo`) — клас зворотного виду (`undo_kind`).
7. Токен належить користувачу, який викликав `prepare` (R-40 п.2); `confirm` чужого токена заборонений.
8. **Дистанційне перемикання (D-46, Q-27).** Види з `remote_gated=True` (`qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test`) при `td.energy_control.remote_switching_enabled=False` відхиляються в `prepare`, `confirm`, `confirm_second` і `undo` з `UserError("Дистанційне перемикання вимкнено: td.energy_control.remote_switching_enabled. Зверніться до адміністратора.")` (перевірка стоїть раніше за перевірки блокувань); плитка й кнопки вузла — `enabled=false` з причиною «Дистанційне перемикання вимкнено адміністратором».

### R-40 Потік `prepare → confirm → виконання` (FR-50, FR-55; M-33)

1. **`prepare(kind, params, advice_id)`** (API-17): перевірка прав (R-39) і `available`; `params = kind.normalize(params)` (дефолти з `params_schema`, межі, приведення типів; `bess_charge.until` — час Києва `HH:MM`); дедуплікація: запис цього самого користувача з тим самим `kind_code` і хешем `params`, `state='prepared'`, створений ≤ 5 с тому, використовується повторно (новий токен); інакше новий запис `prepared` (`prepared_by`, `prepared_at`, `cls`, `summary`, `detail` за `kind.render`); для виконавців `intent`/`genset` перевіряється `td.energy_control.write_enabled`; обчислюються перевірки Odoo (R-41) → `checks`; токен `secrets.token_urlsafe(24)`; `token_hash = sha256`; `token_expires_at = now + confirm_ttl_s`. Відповідь — 7.2.
2. **Токен**: у БД лише хеш; порівняння сталого часу; після `confirm`/`cancel`/спливання токен недійсний (`token_hash` не очищається — для ідемпотентності п.4).
3. **`confirm(token)`** (API-18), у транзакції із `SELECT … FOR UPDATE` запису: (а) токен невідомий → `UserError`; чужий → `AccessError`; (б) стан `prepared` і `token_expires_at < now` → `expired` + `UserError("Час підтвердження минув…")`; (в) повторний розрахунок перевірок Odoo; жорстке блокування → `_td_close('blocked', reason)` і відповідь `blocked_reason` (без виключення); (г) конфлікт ресурсу (п.9) → `blocked`; (д) фіксація `undo_params` (поточна уставка повітря з сигналу; попередні `enabled/params` сценарію; попередній порядок скидання; попередні сцени освітлення — лише в збирача); (е) `confirmed_by`, `confirmed_at`; (ж) клас B без chief → `awaiting_second` (R-39 п.3), інакше `_td_enqueue` (п.6).
4. **Ідемпотентність `confirm`:** повторний виклик із тим самим токеном тим самим користувачем, коли стан уже ≠ `prepared` і ≠ `expired/cancelled`, повертає поточний стан без нової команди (`message` «Уже надіслано»); подвійний клік у UI не створює двох `td.command` (SQL: частковий `UNIQUE(idem)`; `idem = sha1("<id>:<kind_code>")`).
5. **`confirm_second(action_id)`** (API-19): блокування рядка; права й відмінність осіб; не прострочено; повторний розрахунок перевірок (жорстке блокування → `blocked`); `second_by`, `second_at`; `_td_enqueue`.
6. **`_td_enqueue()`** за `kind.executor`: **`intent`** — перевірки наявності сигналу `energy_control/intent`, `write_enabled` сигналу й джерела (інакше `blocked` «Запис вимкнено: {що}»); `td.command.create` (`sudo`, контекст `td_energy_control_internal`): `signal_id`, `value=0`, `payload` (7.5), `origin='energy'`, `expires_at=now+command_ttl_s`, `requested_by=confirmed_by`, `note=name`, `energy_action_id`; дія → `queued`, `started_at=now`. **`genset`** — `tools/genset_link.start_test(...)` (ADP-12): успіх → `done`, `result_text="Тест ДГУ прийнято td_genset"`, `ref_model/ref_id`; `UserError` → `blocked` (текст помилки). **`config`** — застосувати зміну (`scenario._td_apply_change`, порядок `shed_item`, `interlock`), `config_version = state.bump()`, дія → `done`, `result_text="збережено, очікує збирач"` (стає «виконано», коли `applied`; обчислюється в `_td_result_text()`), `started_at=finished_at=now`.
7. **Стани транспорту** (`td.command` → дія, через M-37): `sent` → `sent`; `done` з `result_data.accepted=true` → `executing`; `done` з `accepted=false` → `blocked` (`state='blocked'`) або `failed` (`state='rejected'`) з `reason`; `failed` → `failed` (`error` команди); `expired` → `expired`; `cancelled` → `cancelled`.
8. **Фінал від збирача** (API-25 `actions[]`): `executing` (оновлює `step`), `done`/`failed`/`blocked` → `_td_close`. Стан змінюється лише «вперед» (`queued < sent < executing < done|failed|blocked`); виняток — звіт збирача вважається **авторитетним** і для дії у стані `expired` (збирач виконав інтент, але результат транспорту втрачено: R-53 №6): `expired → executing/done/failed/blocked` дозволено, коли `idem` збігається; інші кінцеві стани не змінюються.
9. **Конфлікт ресурсу:** для виконавців `intent` дозволено одну дію в станах `queued/sent/executing` на `kind.resource`; нова дія на той самий ресурс → `blocked` «Для ресурсу «{resource}» уже виконується дія {name}». Збирач додатково відмовляє `rejected: busy: <resource>`.
10. **`_td_close(state, result_text, error)`**: `finished_at=now`, `state`, `result_text`, `error`; чаттер; `bus.tick('action')` (шина `td_energy_control`), для дій над QS/BESS/КГУ — `td_energy.tools.bus.tick(env, 'state')`; якщо `advice_id` і `state='done'` — `advice._td_on_action_done(self)`; закриття `mail.activity`; для `blocked/failed/expired` — подія `td.energy.event` `kind='control'`, `level='warn'` (не для `blocked` із перевірок оператора: лише запис у журналі).
11. **`cancel(token)`**: `prepared/awaiting_second` → `cancelled` (Esc у діалозі); команда `queued` → `td.command.action_cancel()` і дія `cancelled`; інші стани → `UserError("Скасувати можна лише підготовлену або таку, що очікує, дію.")`.
12. **`_cron_expire`** — розд. 6 (прострочення `prepared`, `awaiting_second`, `queued/sent`, `executing`, конфіг без застосування).

### R-41 Реєстр блокувань (FR-51; M-32; C-39)

1. Блокування — **іменовані перевірки** (`CHECKS[code](ctx, params) -> Result(state, detail, values)`) у двох реалізаціях: `td_energy_control/tools/interlocks.py` (Odoo, підказка в діалозі) і `td_collector_energy/interlocks.py` (збирач, **жорстке виконання**). Обидві мають проходити таблицю золотих випадків нижче (AC-195…AC-199, AC-241, AC-242). Код перевірок не береться з БД; рядок `td.energy.interlock` лише налаштовує `hard`, `fail_closed`, `params`, `where`.
2. **Свіжість.** Значення сигналу вважається відсутнім (`None`), якщо `age > max(3·period_s, max_age_s)`; `max_age_s` = 60 с (`data_fresh.params`), на боці Odoo `age = now − td.signal.last_ts`, на боці збирача — `LiveCache.age_s`. Стан `unknown` — коли потрібний вхід `None`. Входи блоку `derived` (D-47) плагін обчислює з `LiveCache` сам; терм відсутній або старший за `max_age_s` → вхід `None`.
3. **Підсумок дії.** `blocked = any(c.hard and (c.state == 'fail' or (c.state == 'unknown' and c.fail_closed)))`. М'які (`soft` у виді або `hard=False`) лише показуються. Перевірка `where='odoo'` не виконується збирачем; `where='collector'` у діалозі має `state='unknown'` і текст «перевіряє збирач» (не блокує); `where='both'` — в обох місцях за тими самими правилами.
4. **У збирачі** перевірки видів інтентів виконуються синхронно в `call()` перед постановкою в чергу, а перевірки `post`-умов (наприклад, `bess_ok`) повторюються перед **активуючим** кроком виконання (R-52 п.2). Будь-яка жорстка невдача → `blocked`, жодного запису в пристрій.
5. **Золоті випадки** (вхід → очікуваний `state`; «—» — вхід відсутній/несвіжий):

| Перевірка | Вхід | Очікування |
|---|---|---|
| `controller_remote` | `remote=1` | ok |
| | `remote=0` | fail |
| | — | unknown (блокує: hard, fail_closed) |
| `no_island` | `ats_pos=2`, `src1_ok=1` | ok |
| | `ats_pos=3` (острів) | fail |
| | `ats_pos=2`, `src1_ok=0` | fail |
| `ats_parallel_lock` | `lock=1` / `0` / — | ok / fail / unknown |
| `qs_current_ok` | `p1=150`, `p2=100`, `cos=0,95`, `rating=1600`, `max_ratio=0,8` → I = 25 / (√3·0,4·0,95) ≈ 38 А | ok, підпис «≈ 40 А з 1600 А» (округлення до 5 А) |
| | `p1=1700`, `p2=0` → I ≈ 1292 А > 1280 А | fail |
| | QS уже `closed` | ok, detail «QS уже замкнений» |
| `bess_ok` | `bess_state ∈ {1,2,4}` / `{0,3}` / — | ok / fail / unknown |
| `bess_soc_lt_limit` | `soc=82`, `limit=95` | ok, «Заряд 82 % < 95 %» |
| | `soc=95`, `limit=95` | fail |
| `bess_reserve_kept` | `soc=82`, `P=100`, `T=60 хв`, `cap=387`, `reserve=30` → `82 − 25,84 = 56,2` | ok |
| | `soc=50`, ті самі → `24,2` | fail |
| `bess_temp_ok` | `t=24` / `t=41` / — | ok / fail / unknown (не блокує: fail_closed=false) |
| `chp_ready` | `chp_state=0` / `1`,`2`,`3` | ok / fail |
| `chp_gas_pressure` | `gas=2,10`, `min=1,5` / `0,80` | ok / fail |
| `chp_permit` | `1` / `0` / — | ok / fail / unknown |
| `chp_min_run` | КГУ не працює | ok; працює 1,2 год при `min_run_h=2` → fail; 2,3 год → ok |
| `no_fire_alarm` | сигналу немає (модуль пожежної не встановлено) | ok, «не підключено» |
| | `alarm` / `ok` | fail / ok; stale → unknown (не блокує) |
| `air_setpoint_min` | `setpoint=6,5`, `min=6,2`, `margin=0,2`, `max=8,5` | ok |
| | `6,3` / `8,6` | fail / fail |
| `aisle_lux_ge` | min `e_now = 80` / `60` / сигналів немає | ok / fail (м'яка) / unknown |
| `co2_lt` | `620` ppm / `1200` / — | ok / fail (м'яка) / unknown |
| `genset_fuel` | `fuel=78`, `min=30` / `25` | ok / fail (м'яка) |
| `genset_idle` | не працює, не тест, мережа є / працює | ok / fail (жорстка в Odoo) |
| `data_fresh` | усі входи виду свіжі / один несвіжий | ok / fail, detail «немає свіжих даних: {коди}» |

6. **Межі коду збирача (config може лише звужувати):** `max_ratio ≤ 0,9`, `min_bar ≥ 1,0`, `max_c ≤ 45`, `max_age_s ≤ 120`, `bess_kw_max ≤ 200`, `air_bar ∈ [5,0; 8,5]`, `pv_limit_min_pct ≥ 10`, `soc_floor_pct ≥ 10`. Значення конфігу поза межею — застосовується межа коду, подія `config` «значення {k} обмежено».
7. Пороги `td.energy.interlock.params` змінює лише адміністратор; зміна → запис журналу `td.energy.action` (`origin='config'`, `kind_code='interlock_param'`, клас B, `confirmed_by` — адміністратор, який за W1 §4.2 має групу `chief`) і `state.bump()`.

### R-42 Види команд: параметри, кроки виконання, верифікація (FR-49, FR-55; M-31; C-39)

1. **Параметри.** Поле `params_schema` (M-31) описує форму діалогу й межі в Odoo; збирач перевіряє ті самі межі незалежно (JSON-схема `intent.schema.json`) і застосовує «межі коду» (R-41 п.6). Невалідний параметр → `rejected: bad params: {ключ}`.
2. **`available`** (M-31): `intent` — активні джерело `ENERGY-CTL` і сигнал `energy_control/intent`, для `light_*`/`vent_*` — непорожній список цілей BMS у конфігу (API-24 `bms`), для `air_setpoint` — сигнали `air_sp`, `air_min` у конфігу; `genset` — міст ADP-12; `config` — завжди.
3. **Кроки виконання** — власність збирача (`intents.py`); Odoo передає лише `kind` і `params`. Усі кроки **рівневі** (встановлюють значення, а не перемикають), тому повтор безпечний. Верифікація — читання назад через `ctx.read_signal` (разове опитування сигналу щосекунди до `verify_timeout_s`; `LiveCache` оновлюється так само):

| `kind` | Кроки (логічні сигнали, API-24 `signals`) | Верифікація | Fail-safe | Перекриття ресурсу |
|---|---|---|---|---|
| `qs_close` | `qs_cmd = 2` | `qs_state == closed` ≤ 10 с; `qs_ack ≠ 2` (інакше `failed: «Контролер відмовив: блокування»`) | немає (команда атомарна) | — |
| `qs_open` | `qs_cmd = 1` | `qs_state == open` ≤ 10 с | — | — |
| `bess_charge` | `bess_sp = power_kw`; `bess_until = soc_limit_pct`; `bess_valid = valid_s`, де `valid_s = секунди до until` (Київ; `until` ≤ now → `rejected: «Час «до» має бути пізніше за поточний»`; максимум 43 200); `bess_mode = 1` | читання `bess_mode == 1` і `bess_ack == 0` ≤ 10 с; **м'яко**: через 30 с `bess_kw ≥ 0,5·power_kw` (інакше попередження в `result`) | `bess_mode = 0`, `bess_valid = 0` | ручне перекриття `bess` до `now + valid_s` |
| `bess_discharge` | `bess_sp = power_kw`; `bess_until = floor_soc` (`max(reserve_pct, 10)`); `bess_valid = duration_min·60`; `bess_mode = 2` | `bess_mode == 2`, `bess_ack == 0`; м'яко `bess_kw ≤ −0,5·power_kw` | `bess_mode = 0` | перекриття `bess` на `duration_min` |
| `bess_stop` | `bess_mode = 0`; `bess_valid = 0` | `bess_mode == 0` | — | знімає перекриття `bess` |
| `chp_start` | `chp_cmd = 1` | ≤ 30 с: `chp_state ∈ {1,2}` і `chp_ack ≠ 2` | немає: при невдачі пуск не повторюється, результат `failed`; КГУ в стані `1/2` автоматично не зупиняється | КГУ «у володінні оператора» (сценарій `chp` її не зупиняє) |
| `chp_stop` | `chp_cmd = 2` | ≤ 30 с: `chp_state ≠ 2` | — | знімає володіння |
| `air_setpoint` | `air_sp = setpoint_bar` (інженерні одиниці, бар; адреса сигналу має `scale=0,01`, плагін Modbus ділить: `raw = value/scale`) | читання `air_sp` дорівнює ≤ 10 с | повернення попередньої уставки (`undo_params`) при невдалій верифікації | перекриття `air` немає |
| `light_break` | для кожної цілі `bms.light_break.light` (`aisle=false`): запис `scene_signal = scene_number`, `text="fade=2.0"`; запам'ятати попередню сцену | ≥ 80 % цілей читаються назад ≤ 15 с | відновити запам'ятовані сцени | перекриття `light` на `duration_min`; по спливанні — автоматичне відновлення (R-52 п.8) |
| `light_restore` | відновити запам'ятовані сцени, інакше `light_scene_day_number` | як вище | — | знімає перекриття |
| `vent_eco` | для кожної цілі `bms.vent_eco.vent`: `mode_signal` (текст) = `eco_mode` (`VEL`); запам'ятати попередній режим | ≥ 80 % цілей ≤ 15 с | відновити режими | перекриття `vent` на `duration_min`; автовідновлення до `day_vent_mode` |
| `vent_restore` | `mode_signal` = запам'ятований або `day_vent_mode` | як вище | — | знімає перекриття |

4. **Тексти діалогу** (`confirm_title`, `confirm_text`, `sub`) — шаблони розд. 5.3, значення `{chp_kw}` = `plant.chp_kw / 2` (400 кВт, D-33 «вийде на 400 кВт»), `{ramp_min}` = параметр `chp.ramp_min`, `{test_minutes}` — адаптер ADP-12, `{current_bar}` — із сигналу `air_sp`.

### R-43 Публікація конфігурації й статус сценаріїв (FR-47, FR-57; C-39)

1. **`config_version`.** Лічильник у `td.energy.control.state` (M-39); `bump()` викликається зміною: `td.energy.scenario` (`enabled`, `params`), `td.energy.shed.item` (будь-яке поле), слотів `executes=True`, `td.energy.interlock` (`params`, `hard`, `fail_closed`, `active`), прапорів `write_enabled`/`automation_enabled`, параметрів `td.energy_control.*` рушія, `td.energy.cos_phi_target`, `td.energy.bess_reserve_pct`, `td.energy.pv_kwp`. Зміни зовнішніх даних (цілі BMS, тариф, `is_critical` вузлів) ловить `cron_td_energy_control_watch`: перераховує канонічний JSON, порівнює `config_etag`, при розбіжності — `bump()`.
2. **Канонічний JSON:** `json.dumps(cfg, sort_keys=True, ensure_ascii=False, separators=(",", ":"))` без ключів `server_time`, `etag`, `config_version`; `etag = sha256(canonical).hexdigest()`; `ETag: "<etag>"`.
3. **Застосування.** Плагін валідує конфіг за `config.schema.json`; невалідний → лишає попередній валідний, в API-25 `engine.reason="config invalid: …"`, подія `config`. `config_version_applied` — версія конфігу, за якою рушій працює зараз. `td.energy.control.state.applied_version = max(…)`.
4. Дія `executor='config'` вважається **застосованою**, коли `applied_version ≥ action.config_version` (`applied`, `result_text`: «виконано» / «збережено, очікує збирач»). Картка сценарію: перемикач = `enabled` (Odoo), додатковий чип «Очікує застосування» при `!applied`.
5. **Чипи сценаріїв** (`state_text`, `state_kind`): `enabled=False` → «Вимкнено», `off`; немає звіту рушія ≥ `2·heartbeat_stale_s` → «Немає даних від рушія», `off`; далі за таблицею (`{…}` — з `engine_facts`; числа з комою, `0,0`):

| Сценарій | `armed` (`arm`) | `active` (`act`) | `warn` (`warn`) |
|---|---|---|---|
| `peak` | «Чергування · запас {margin_kw} кВт» | «Зрізання піку · {stage}» (`bess`: «BESS {bess_kw} кВт»; `chp`: «BESS + КГУ»; `shed`: «скинуто {shed_n}»; `…` комбінація через « + ») | «Збій: {reason}» |
| `self` | «Очікування · експорт {export_kw} кВт» | «Активний · заряд BESS {bess_kw} кВт» або «Обмеження СЕС {pv_limit_pct} %» | «Збій: {reason}» |
| `pfc` | — | «Активний · cos φ {cos1} / {cos2}» | «Збій: {fault}» (напр. «PFC-2 ступінь 3»; з `engine_facts.fault` або W1 `fault_step`) |
| `night` | «Наступний запуск о {from}» | «Активний до {to}» | «Збій: {reason}» (напр. «немає цілей BMS») |
| `backup` | «Готовий · паливо {fuel_pct} %» (`fuel_pct` — W1 `_td_genset_summary`; без нього «Готовий») | «Мережі немає · скинуто {shed_n}» | «Збій: {reason}» |
| `chp` | «Очікує вигідної ціни» | «Працює · {chp_kw} кВт» | «Збій: {reason}» |

### R-44 Рушій автоматики: цикл, режими, входи, арбітраж (FR-56, FR-57; C-39, C-40)

1. **Режими.** `off` — немає валідної конфігурації, або `flags.automation_enabled=false`, або `flags.write_enabled=false`: рушій лише читає й звітує (стани сценаріїв — `off`, чипи показують «Вимкнено»/факти без дій). `hold` — рушій живий, але **не пише** (причини: контролер у місцевому режимі `remote=0`; несвіжий критичний вхід довше за `stale_hold_s`; перевищено `max_writes_per_min`; помилка конфігу). Пожежна тривога режим **не** змінює (D-48): блокує лише записи `vent`/`light` (п.8). `auto` — норма. Перехід у `hold` залишає наявні примусові режими пристроїв до спливання їхніх сторожових таймерів (R-53 №7). Кожна зміна режиму — подія `mode`.
2. **Тік** (`tick_s`, 2 с; якщо тік триває довше за період — наступний стартує одразу, лог `WARNING`, але без накопичення): (а) `Inputs` з `ctx.live`; (б) визначити режим (п.1); (в) якщо `auto` — виконати сценарії в порядку **`backup`, `peak`, `self`, `slots` (крок BESS-слотів, R-54 п.5), `chp`, `night`, `pfc`** (кожен — чиста функція `step(inputs, cfg, state, now) → Output(requests, status, events)`); (г) арбітраж запитів (п.4); (д) `Actuator` застосовує бажані значення (п.7); (е) оновлення станів і подій; (ж) heartbeat кожні 10 с. Виключення сценарію перехоплюється: сценарій → `warn` «внутрішня помилка», решта продовжують.
3. **Входи й свіжість.** Критичні входи: `peak` — `grid_kw`, `bess_soc`; `self` — `export_kw`, `pv_kw`, `bess_soc`; `backup` — `ats_pos`, `src1_ok`; `chp` — `chp_state`; `pfc` — `remote`; `night` — критичних входів немає (D-49: цілі BMS ідуть не через контролер ГРЩ). Входи блоку `derived` (D-47) обчислюються з `LiveCache` за формулами конфігу; терм відсутній або старший за `max_age_s` → вхід відсутній. Відсутній критичний вхід → сценарій `warn` «немає даних: {коди}» без записів; `grid_kw` відсутній довше за `stale_hold_s` → рушій `hold`.
4. **Арбітраж.** Ресурси: `bess`, `chp`, `shed`, `pv`, `vent`, `light`, `pfc`, `qs`, `air`. Порядок пріоритету: **ручне перекриття оператора** (R-52 п.8) > `backup` > `peak` > `self` > `slots` > `chp` > `night` > `pfc`. Запит нижчого пріоритету на ресурс, який у цьому тіку вже захоплений вищим або заблокований перекриттям, відкидається (подія `override`, раз на зміну). `bess`: розряд (`peak`, `backup`) завжди перемагає заряд (`self`).
5. **Місцевий режим контролера** (`remote=0`): `hold`, причина «контролер у місцевому режимі», подія `interlock` раз на зміну, `td.energy.event` `kind='control'` `level='warn'` (з Odoo через API-25 `events`, дедуп 60 хв).
6. **Межі коду** (константи `limits.py`): `bess_kw_max=200`, `pv_limit_min_pct=10`, `air_bar ∈ [5,0; 8,5]`, `soc_floor_pct ≥ 10`, `min_write_interval_s ≥ 2`, `max_writes_per_min ≤ 120`, `tick_s ∈ [1,10]`. Значення конфігу застосовуються як `min(code, cfg)` (для нижніх меж — `max`).
7. **Політика запису (`Actuator`).** Бажане значення `desired[signal]` записується, якщо `desired ≠ readback` (або `≠ last_write`, коли читання назад недоступне) і `now − last_write(signal) ≥ min_write_interval_s`; примусові режими BESS і ліміти скидання **перезаписуються** кожні `valid_s / 3` (сторожовий таймер контролера, R-53 №7); перша невдача запису → повтор через `min_write_interval_s`, третя поспіль → сценарій `warn`, ресурс звільняється, подія `failsafe`. Запобіжник частоти: `> max_writes_per_min` записів за ковзну хвилину → `hold` на 5 хв, подія `failsafe`.
8. **Пожежна тривога** (`fire_state = alarm`): записи для `vent`, `light` припиняються (рушій не конфліктує з протипожежною логікою), `night` → `warn` «пожежна тривога», подія `interlock`; **режим рушія лишається `auto`** (D-48); після скидання — продовжується. Решта ресурсів не змінюється (R-60).
9. **Володіння.** Рушій пам'ятає, чим він керує (`bess_owner ∈ {None, scenario, manual}`, `chp.started_by`, список скинутих навантажень із часом, `night.applied`, перекриття), і зберігає в `Store`; після рестарту стан відновлюється й **звіряється з пристроєм** (читання назад): розбіжність → володіння скидається, примусові режими пристрою не чіпаються до спливання `valid_s`.
10. **Події рушія** (`events[]` API-25; `kind`): `auto_step` (рушій змінив стан пристрою: «BESS · розряд 62 кВт»), `auto_release` (відновлення), `interlock` (блокування/відмова), `override` (ручне перекриття), `failsafe`, `mode`, `config`. Odoo пише їх у журнал як `origin='auto'` (R-56 п.3); `interlock`/`failsafe`/`mode(hold)` додатково створюють `td.energy.event` `kind='control'`.

### R-45 Сценарій «Зрізання піку» (BESS → КГУ → скидання; FR-56; CT-04)

Параметри — M-29 `peak`; входи: `grid_kw`, `bess_kw`, `bess_soc`, `bess_state`, `chp_state`, `air_bar`, `ctl_remote`. Стан у `Store`: `stage ∈ {idle, bess, chp, shed}`, `stage_since`, `acc_kws`, `block_start`, `release_since`, `shed_list`, `chp_started_by_peak`.

1. **Прогноз інтервалу попиту.** Блок 15 хв вирівняний за UTC-епохою (`block_start = floor(epoch/900)·900`, перехід DST не впливає). Кожен тік: `acc += grid_kw·dt`; `remaining = 900 − (now − block_start)`; `proj_kw = (acc + grid_kw·remaining) / 900`. На початку блоку `acc=0`; перші 30 с блоку `proj_kw = grid_kw`.
2. **Активація.** `active_cond = proj_kw ≥ limit_kw − activate_margin_kw  або  grid_kw ≥ limit_kw`. З `idle` при `active_cond` → `stage = bess` (подія `auto_step` «Зрізання піку: старт, прогноз {proj} кВт»).
3. **Ціль.** Поки `stage ≠ idle`: `target_grid = limit_kw − margin_kw`; `excess = grid_kw − target_grid` (кВт; `grid_kw` уже враховує поточну роботу BESS/КГУ/скидання).
4. **Ступінь 1 — BESS.** `p_max = min(bess_max_kw, 200)`; `floor_soc = max(bess_min_soc_pct, bess_reserve_pct)`; `bess_available = bess_state ∈ {1,2,4} ∧ soc > floor_soc + 2 ∧ ¬manual_override(bess)`; `bess_now = max(0, −bess_kw)`; `p_target = clamp(bess_now + excess, 0, p_max)`; якщо `bess_available ∧ excess > 0` (або `p_target` відрізняється від бажаного ≥ 5 кВт): запит ресурсу `bess` = `{mode: 2, setpoint_kw: round(p_target), until_soc: floor_soc, valid_s: 30}` (перезапис кожні 10 с). SOC ≤ `floor_soc` → BESS недоступний, подія `interlock` «BESS на резерві {soc} %» (раз на зміну). `uncovered = excess − (p_target − bess_now)`.
5. **Ступінь 2 — КГУ.** Якщо `chp_allowed ∧ uncovered > 0` триває ≥ `stage_delay_s` і КГУ готова (`chp_state = 0`, перевірки `chp_ready`, `chp_gas_pressure`, `chp_permit` — ok, мінімальна пауза `min_off_min` минула, сценарій `chp` не володіє КГУ): запит `chp` = `start`, `chp.started_by = 'peak'`, `stage = chp`. КГУ ще розганяється (`chp_state = 1`) — чекати (не ескалювати) до `stage_delay_s`.
6. **Ступінь 3 — скидання.** Якщо `shed_allowed ∧ uncovered > 0` триває ≥ `stage_delay_s` після ступеня 2 (або КГУ недоступна/заборонена): `stage = shed`; `need = uncovered`; виконати R-51 `shed(items, need)`; далі кожні `stage_delay_s` (якщо `uncovered` усе ще > 0) — наступні елементи.
7. **Відпускання.** Якщо `proj_kw ≤ limit_kw − release_margin_kw ∧ grid_kw ≤ limit_kw − release_margin_kw` безперервно `release_hold_s`: послідовно **у зворотному порядку** — відновлення скинутих (R-51 `restore`, крок `shed_restore_step_s`); потім КГУ: `stop` лише якщо `started_by = 'peak'` і відпрацьовано `min_run_h` (інакше лишається, володіння переходить до сценарію `chp`, якщо він увімкнений, або зупиняється пізніше за тим самим правилом); потім BESS: `setpoint` зменшується кроками по `p_max/4` кожні 10 с до 0 і `mode = 0`; `stage = idle`; подія `auto_release` «Зрізання піку завершено».
8. **Статус.** `idle` → `armed`, факти `margin_kw = limit_kw − grid_kw`, `proj_kw`, `grid_kw`; `bess|chp|shed` → `active`, факти `stage`, `bess_kw`, `shed_n`; відмова пристрою (`bess_ack = 2` двічі, помилка запису 3 рази) → `warn`, `reason`.
9. Перевірки сценарію: `bess_ok`, `controller_remote`, `no_island` (в острові сценарій призупиняє `backup`, R-49).

### R-46 Сценарій «Самоспоживання СЕС» (FR-56; CT-05)

Входи: `pv_kw`, `export_kw`, `bess_kw`, `bess_soc`, `bess_state`; параметри — M-29 `self`.

1. Активно, коли `pv_kw ≥ 1`. Інакше `armed`, факти `export_kw`.
2. Якщо `export_kw > export_max_kw + export_deadband_kw` ∧ BESS доступний для заряду (`bess_state ∈ {1,2,4}`, `soc < bess_target_soc_pct − 0,5`, `¬manual_override(bess)`, BESS не розряджається за R-45): `charge_now = max(0, bess_kw)`; `p = clamp(charge_now + (export_kw − export_max_kw), 0, min(bess_max_kw, 200))`; запит `bess` = `{mode: 1, setpoint_kw: round(p), until_soc: bess_target_soc_pct, valid_s: 30}`.
3. **Обмеження СЕС** (`curtail_pv`): якщо після кроку 2 залишок `uncovered = export_kw − export_max_kw − (p − charge_now) > export_deadband_kw` тримається `curtail_delay_s`: інтегральний крок `limit_pct = max(pv_limit_min_pct, limit_pct_now − ceil(100·uncovered / pv_kwp))` (не частіше за `min_write_interval_s`), запит `pv` = `{pv_limit_pct, shed_valid_s: 60}`; `limit_pct_now` береться з читання `pv_limit` назад (спочатку 100).
4. **Відпускання:** якщо `export_kw < export_max_kw − export_deadband_kw` безперервно `restore_hold_s`: `limit_pct = min(100, limit_pct_now + 5)` кожні `min_write_interval_s`; BESS: при `export_kw = 0` і (`soc ≥ target` або `pv_kw < 1`) → `mode = 0`.
5. Статус: `active` — «заряд BESS {p} кВт» або «Обмеження СЕС {limit_pct} %»; `armed` — експорт у нормі; `warn` — відмова BESS/інверторів.

### R-47 Сценарій «Компенсація реактивної потужності (PFC)» (FR-56; CT-06)

Регулювання ступенів виконує PFC-контролер; рушій лише задає режим і ціль та контролює відмови.

1. Сценарій `enabled` і `auto`: бажані `pfc_mode = 1`, `pfc_cos = cos_phi_target` (інженерні одиниці, напр. 0,95; адреса сигналу має `scale=0,01`, регістр = 95; значення з `plant.cos_phi_target`, E-10: єдина група налаштувань); запис при старті, зміні цілі, розбіжності з читанням назад.
2. Сценарій вимкнений (`enabled=false`) і рушій у `auto`/`off` з дозволеним записом: `pfc_mode = 0` (ручний режим; на стенді емулятор вимикає ступені — A-45). Зміна — дія класу B, тому випадкове вимкнення виключене.
3. Моніторинг: `pfc1_fault`, `pfc2_fault > 0` → сценарій `warn`, `fault = "PFC-{s} ступінь {k}"`; значення `cos φ` секцій (`energy/sections/S{1,2}/cos_phi`) — у фактах `cos1`, `cos2`. Заявку ТО й події створює W1 (CT-05, R-35); рушій їх **не** дублює.
4. `hold` через місцевий режим не змінює стан PFC.

### R-48 Сценарій «Нічний режим (BMS)» (FR-56; CT-07)

Параметри — M-29 `night`; цілі — API-24 `bms.night` (`vent[]` — установки `roofvent` із `mode_signal`, `sp_night_signal`; `light[]` — групи зі `scene_signal`; групи `aisle` теж переводяться в черговий сценарій уночі).

1. **Вікно:** `from`/`to` — місцевий час Києва (R-63); `from > to` — перетинає північ. `in_window(now)`: день початку вікна ∈ `days` (для частини після півночі — попередня календарна доба).
2. **Вхід у вікно:** для кожної установки `mode_signal = vent_mode` (текст, напр. `VEL`) і, якщо є, `sp_night_signal = heat_setpoint_c`; для кожної групи `scene_signal = light_scene_number`, `text = "fade=2.0"`. Запис ідемпотентний; запам'ятовується час запису. Подія `auto_step` «Нічний режим: вентиляція RoofVent {n} шт. → {vent_pct} %, освітлення — черговий сценарій».
3. **Вихід із вікна:** `mode_signal = day_vent_mode`, `scene_signal = light_scene_day_number`; подія `auto_release` «Вентиляція · денний режим: RoofVent {n} шт. → 100 %» (текст макета).
4. **Старт/зміна конфігу всередині вікна:** якщо читання назад ≠ бажаному — записати (ідемпотентно). Поза вікном нічого не пишеться (сценарій не «тримає» день).
5. **Ручне втручання в BMS:** якщо після запису читання назад цілі відрізняється від бажаного довше за 60 с, а рушій цю ціль не змінював — ціль позначається `overridden` до наступної межі вікна, подія `override`; рушій її не перезаписує.
6. Пропуски записів: пожежна тривога (R-44 п.8), ручне перекриття ресурсу `vent`/`light` (R-52 п.8); `remote=0` не впливає (цілі BMS ідуть не через контролер ГРЩ); `bms.night` порожній → `warn` «немає цілей BMS».
7. Статус: у вікні `active`, факти `until` (`to`); поза вікном `armed`, факти `next_run` (найближчий початок вікна, Київ `HH:MM`).

### R-49 Сценарій «Резервне живлення» (АВР → ДГУ; FR-56; CT-08)

АВР перемикає **апаратно**; рушій лише скидає навантаження й відновлює їх.

1. `mains_lost = (src1_ok == 0) ∨ (ats_pos == 3)`; стійка умова ≥ 2 тіків (дебаунс 4 с) → `active`; ресурси пріоритету `backup` > усі (R-44 п.4); сценарій `peak` призупиняється, його ресурси звільняються (скидання R-45 відновлюються лише після відновлення мережі).
2. Дія при `active`: `need = max(0, p_total − 0,9·genset_capacity_kw)` (`p_total` — `energy/totals/p_now`; відсутній → `need = ∞`); виконати R-51 `shed(items, need)` одразу й далі кожні `stage_delay_s` (з `peak.params`, інакше 10 с), доки `need` не покрито або список не вичерпано. Елементи з `critical=true` (вузол `is_critical`: компресорна, склади) пропускаються — критичні навантаження живляться від ДГУ; вузли з `never_shed` не чіпаються за побудовою. BESS лишається в `mode = 0` (острівним режимом BESS керує сам контролер BESS; рушій не форсує).
3. Відновлення: `src1_ok = 1 ∧ ats_pos = 2` безперервно `restore_delay_s` → R-51 `restore` крок за кроком; `stage = armed`; подія `auto_release` «Мережа відновлена: навантаження повернено».
4. Статус: `armed` (мережа є), факти `fuel_pct` додає Odoo (W1 `_td_genset_summary`); `active` — факти `shed_n`; `warn` — немає даних `ats_pos`/`src1_ok`.
5. Тест ДГУ (`genset_test`) і планові відключення (W1 `td.energy.outage.plan`) сценарій не запускають.

### R-50 Сценарій «КГУ за графіком і ціною» (FR-56; CT-09)

Параметри — M-29 `chp`; входи: `chp_state`, `chp_kw`, `chp_hours`; конфіг: `tariff.zones`, `slots` (`resource='chp'`).

1. `chp_cost = gas_price_uah_m3 · gas_m3_per_kwh` (₴/кВт·год; сид: 19,80 · 0,25 = 4,95); `grid_price` — ціна поточної зони тарифу (місцевий час, R-63); `price_ok = (grid_price − chp_cost) ≥ price_margin_uah_kwh`; `slot_active` — поточний час у слоті `resource='chp'`, `executes=True`, дозволеному за днем (`use_slots=true`). `wanted = slot_active ∨ price_ok` (у вимкненому сценарії — `wanted=false`).
2. **Пуск:** `wanted ∧ chp_state = 0 ∧ ¬hold`, пауза `min_off_min` після останньої зупинки минула, перевірки `chp_ready`, `chp_gas_pressure`, `chp_permit` — ok, КГУ не у володінні оператора → запит `chp = start`, `started_by = 'chp'`, подія `auto_step` «КГУ: пуск за ціною ({grid_price} ₴ проти {chp_cost} ₴)».
3. **Зупинка:** `¬wanted ∧ chp_state = 2 ∧ started_by = 'chp' ∧ відпрацьовано ≥ min_run_h` → `stop`. КГУ з `started_by ∈ {'peak','manual'}` цим сценарієм не зупиняється.
4. `chp_state = 3` (аварія) → `warn` «КГУ в аварії». Пуск «Зрізання піку» ступінь 2 (R-45) не залежить від `enabled` цього сценарію (лише від `chp_allowed`), але враховує паузу `min_off_min` і володіння.
5. Статус: `armed` — «Очікує вигідної ціни»; `active` — працює (факти `chp_kw`); `off` — сценарій вимкнений.

### R-51 Скидання й відновлення навантажень (FR-48; CT-10; використовують R-45, R-49)

1. **Список:** `shed[]` з API-24 за `seq`; елементи з вузлом у `never_shed` або поза списком сигналів пропускаються (подія `interlock` раз на зміну). Елементи з `critical=true` (допускаються M-30 лише для часткового/умовного скидання) виконуються лише сценарієм `peak`; `backup` їх пропускає. `never_shed` — коди `is_critical` вузлів **без** активного рядка пріоритету плюс `NEVER_SHED_CODES`; рушій перевіряє ще раз.
2. **`shed(items, need_kw)`:** для кожного елемента за порядком, ще не скинутого: (а) умова — `air_pressure_min`: `air_bar ≥ condition_value`; `no_active_cycle`: у v1 немає сигналу стану циклу → `unknown` → елемент **пропускається** (подія «пропущено: немає даних про цикл {вузол}», Q-32); `none` — ок; (б) запис: `off`, `pause`, `defer` → `limit_pct = 0`; `reduce` → `limit_pct = param`; разом із `shed_valid_s = 60` (перезапис кожні 20 с, сторожовий таймер контролера); (в) `pause`/`defer` ставлять таймер `param` хвилин, після якого елемент відновлюється автоматично; (г) `cumulative += kw_reducible`; зупинка, коли `cumulative ≥ need_kw`; подія `auto_step` «Скинуто: {name} — {how}».
3. **`restore()`:** у зворотному порядку скидання, один елемент за `shed_restore_step_s` (20 с): `limit_pct = 100`; коли відновлено всі — `shed_valid_s = 0`. Подія `auto_release` «Повернуто: {name}».
4. Стан скидання (`shed_list` із часом) зберігається в `Store`; після рестарту рушій читає `limit_pct` назад і узгоджує список.
5. Ліміти навантажень виконують пристрої/контролер (на стенді — емулятор, R-59); при зникненні рушія сторожовий таймер `shed_valid_s` повертає навантаження (R-53 №7).

### R-52 Виконання інтента оператора в збирачі (FR-55; C-39; `executor.py`)

1. **Прийом (`call`).** Синхронно, ≤ 1 с: схема `intent.schema.json` (`v=1`, обов'язкові ключі, межі); `expires_at` (з поправкою на розбіжність годинників за `server_time` конфігу) > now; `idem` уже відомий → збережений результат (`duplicate: true`); `kind` відомий; `params` у межах (R-42); жорсткі перевірки R-41 (`where ∈ {both, collector}`) **за свіжими входами**; ресурс вільний (R-40 п.9) і в черзі ≤ 4 інтентів; запобіжники (`write_enabled`, `controller_remote`). Невдача → `result_data` `accepted=false` (7.5); успіх → запис у `Store` (`state=executing`) і постановка в чергу ресурсу.
2. **Виконання** (задача на інтент; один інтент, що виконується, на ресурс): перед **першим** кроком — повторити жорсткі перевірки; перед **активуючим** кроком (запис, що змінює потік енергії: `bess_mode`, `chp_cmd`, `qs_cmd`, `air_sp`, сцени/режими BMS) — повторити перевірки, чиї входи змінилися (`bess_ok`, `no_island`, `ats_parallel_lock`, `no_fire_alarm`).
3. **Крок:** `ctx.write_signal(code, value, text)` з тайм-аутом `step_timeout_s` (8 с); помилка → один повтор через 1 с; друга помилка → `failed` + fail-safe. Далі верифікація (R-42): `ctx.read_signal` раз на секунду до `verify_s` кроку (за замовчуванням 10 с; КГУ 30 с; BMS 15 с), предикат із таблиці R-42.
4. **Результат.** Усі кроки й обов'язкова верифікація пройдені → `done`, `result` — рядок ≤ 256 символів («BESS: заряд 50 кВт до 16:00 (valid_s 5700)»). **М'яка** верифікація (наприклад, `bess_kw ≥ 0,5·power_kw` через 30 с) не пройдена → `done` із приміткою «попередження: …». **Жорстка** не пройдена → fail-safe → `failed` («Не підтверджено пристроєм: {що}»); у `result` — підсумок fail-safe.
5. **Fail-safe** — кроки з таблиці R-42 (`bess_mode = 0`, відновлення уставки/сцен/режимів): best-effort, по одному повтору, без блокування черги; невдача fail-safe → подія `failsafe` і текст «стан пристрою невідомий: перевірте вручну».
6. **Ідемпотентність.** `Store.intents[idem] = {state, run_id, result, ts}` (зберігання 24 год або 500 записів); повторний `call` із тим самим `idem` повертає збережений результат без повторного виконання; усі кроки рівневі, тому навіть повторне виконання безпечне.
7. **Тайм-аути.** Загальний `exec_timeout_s` (60 с) від прийому; перевищення → `failed` + fail-safe. Рестарт плагіна під час `executing` → при старті такі інтенти звітуються `failed` («рушій перезапущено під час виконання; стан пристрою невідомий — перевірте»); автоматичного продовження немає.
8. **Ручне перекриття (`override`).** Успішні `bess_charge`/`bess_discharge` → `override[bess] = {until, action_id}` (до `now + valid_s` / тривалості); `light_break`, `vent_eco` → `override[light|vent]` до кінця `duration_min`, після чого виконавець **сам** запускає відновлення (`light_restore`/`vent_restore` за запам'ятованим станом; подія `auto_release` «Освітлення: перерва завершена»); `bess_stop`, `light_restore`, `vent_restore` знімають перекриття; `chp_start` → `chp.owner='manual'`, `chp_stop` знімає. Перекриття зберігаються в `Store`, блокують записи сценаріїв на ресурс (R-44 п.4), подія `override` один раз.
9. **Звітність.** Кожна зміна стану (`executing` → крок N з M, `done`, `failed`, `blocked`) ставиться в чергу `Reporter` і надсилається негайно (API-25).
10. **Лічильники записів.** Записи виконавця враховуються в `max_writes_per_min`, але запобіжник частоти вимикає лише автоматику (оператор має пріоритет).

### R-53 Режими відмов (FR-55, FR-57)

| № | Подія | Поведінка | Стан пристрою | Що бачить оператор |
|---|---|---|---|---|
| 1 | Odoo недоступна | Рушій працює на кешованій конфігурації (≤ 7 діб, `Store`); `Reporter` буферизує до 200 дій і 1000 подій (старіші відкидаються з лічильником), надсилає після відновлення; нові ручні команди неможливі | не змінюється; сценарії діють | екран недоступний; після відновлення журнал поповнюється |
| 2 | Збирач недоступний | `td.command` лишається `queued` → `expired` (`command_ttl_s`); дія `expired` «Збирач не забрав команду»; автоматика не працює | сторожові таймери контролера повертають BESS (30 с) і скидання (60 с) | чип «Збирач не на зв'язку · {вік}», подія `CTRL-HEARTBEAT` |
| 3 | Контролер ГРЩ не відповідає (Modbus) | Запис → `failed` («пристрій не відповідає»); входи несвіжі → R-44 п.3: `warn`/`hold` | невідомо; сторожові таймери | дія «не виконано», картки `warn` |
| 4 | Місцевий режим (`remote=0`) | `blocked` для інтентів; рушій `hold` | не змінюється | «Контролер у дистанційному режимі — не виконано», чип «автоматику призупинено» |
| 5 | Несвіжі входи | Сценарій `warn`; `grid_kw` > `stale_hold_s` → `hold`; жорсткі перевірки fail-closed | не змінюється | «немає даних: {коди}» |
| 6 | Втрата результату транспорту (збирач виконав інтент, `POST result` не дійшов, `td.command` став `expired`) | Збирач в API-25 звітує про остаточний стан дії за `idem`; Odoo приймає його як авторитетний (R-40 п.8) | відповідає результату | дія переходить `expired → done/failed` |
| 7 | Падіння рушія/збирача під час примусового режиму | Сторожові таймери: BESS `valid_s` (автоматика 30 с, ручні — задані оператором), `shed/valid_s` 60 с (скидання й обмеження СЕС повертаються до 100 %); КГУ, QS, уставка повітря **не** мають таймера (фізичні стани) | BESS авто; навантаження повернено; КГУ/QS лишаються | чип «Збирач не на зв'язку» |
| 8 | Частковий збій кроків інтента | Fail-safe (R-52 п.5), `failed` | безпечний (авто) | «Не виконано: {крок}» |
| 9 | Верифікація не пройдена | Fail-safe, `failed` | безпечний | «Не підтверджено пристроєм» |
| 10 | Інтент прострочений до виконання | `rejected: expired` | не змінюється | «Прострочено» |
| 11 | Ручна й автоматична дії конфліктують | Перекриття оператора (R-44 п.4, R-52 п.8); подія `override` | як задав оператор | рядок журналу «ручний режим BESS до {час}» |
| 12 | Невалідний конфіг | Плагін лишає попередній валідний; `engine.reason="config invalid: …"`; подія `config` | не змінюється | чип `warn` на екрані |
| 13 | Розбіжність годинників (> 30 с між `server_time` і годинником збирача) | `expires_at` порівнюється зі скоригованим часом; подія `config` `warn`; розрахунки блоків 15 хв — за годинником збирача | — | подія в журналі |
| 14 | Вимкнено запобіжник під час роботи | Виконавець: решта кроків скасовуються (`failed` «Запис вимкнено під час виконання») + fail-safe, якщо запис ще дозволений; рушій → `off`: активного відновлення немає, повертають сторожові таймери | поступово авто | чип «автоматику призупинено» |
| 15 | Пристрій відмовив (`ack = 2`) | `failed` з причиною; сценарій — `warn` після 2 відмов | не змінюється | причина в журналі |
| 16 | Перевищено частоту записів | `hold` на 5 хв, подія `failsafe` | не змінюється; таймери повертають | чип «призупинено: частота записів» |
| 17 | Рестарт плагіна | `Store` відновлює володіння; звірка з пристроєм (R-44 п.9); `executing` інтенти → `failed` (R-52 п.7) | не змінюється | «рушій перезапущено» |
| 18 | Стоп-кран джерела вимкнений | `WriteRefused` → як №14 | — | дія `blocked` «Запис вимкнено: джерело {code}» |

### R-54 Розклад і план дня (FR-53; M-34)

1. **Вхід планувальника** `_td_plan_day(day)` (метод `td.energy.schedule.slot`): типовий профіль споживання `cons[96]` (кВт) і профіль СЕС `pv[96]` (кВт) за локальними індексами 15 хв — функції W1 R-28 (`td_energy/tools/forecast.py`: типова доба за днем тижня, `forecast_weeks`/`forecast_min_days`); при браку історії (< `forecast_min_days`) — запасний план зі сиду (розряд 07:30–11:00, заряд від СЕС 11:00–16:00, розряд 16:00–17:30).
2. **Перебудова.** Для кожної доби горизонту (`plan_horizon_days`): видалити слоти `source in ('plan','scenario')` цієї доби (за `date`), створити заново (п.3–п.6); `manual` не чіпати; `plan`-смуги, що перетинаються й накриті `manual`, обрізаються при виводі (п.7). Ідемпотентно; запуск — `cron_td_energy_control_plan`, `post_init_hook`, кнопка «Перебудувати план», після зміни `enabled/params` сценаріїв.
3. **BESS (`plan`).** Розряд: інтервали 15 хв, де `cons − pv ≥ peak.limit_kw − peak.activate_margin_kw` → злити сусідні (розрив ≤ 30 хв), мітка «розряд · пік» (для вікна, що закінчується на межі зміни, — «розряд · зміна»), `mode='discharge'`, `setpoint_kw = peak.bess_max_kw`; заряд: інтервали, де `pv − cons > self.export_max_kw` (тривалістю ≥ 30 хв) → «заряд від СЕС», `mode='charge'`.
4. **КГУ (`scenario`).** Лише при `chp.enabled`: інтервали, де `price_ok` за зонами тарифу, і ручні слоти `chp`; мітка «пуск за ціною». При `chp.enabled = false` — без смуг (макет).
5. **Виконання слотів.** Слоти `executes` (`manual`, `resource ∈ {bess, chp}`) публікуються в конфіг (`slots[]`); крок рушія `slots`: у вікні `bess`-слота з `mode='charge'` → запит `bess` `{mode:1, setpoint_kw, until_soc: self.bess_target_soc_pct, valid_s:30}`, `mode='discharge'` → `{mode:2, setpoint_kw, until_soc: floor_soc, valid_s:30}`; пріоритет нижчий за `peak`/`self` і ручне перекриття. Слоти `chp` обробляє R-50. Решта слотів (`plan`, `scenario`, `genset`, `charging`, `vent`, `light`) виконання не мають.
6. **Нічні смуги.** `night.enabled`: `vent` — «ніч {vent_pct} %» `[0, to]`, «день 100 %» `[to, from]`, «ніч {vent_pct} %» `[from, 24]`; `light` — «черговий» / «робочий» / «черговий» (`mode='duty'`/`'work'`); `night.enabled=false` — одна смуга «день 100 %» / «робочий» на всю добу. Вікно через північ розбивається на два слоти (`time_to > time_from`).
7. **ДГУ (`genset`).** Якщо є міст: з `adapters.schedule_info(gen)` (W1 ADP-07) слоти `mode='test'` на добу (мітка «тест»); інакше порожньо. **Не реалізовано в збірці:** слоти «тест ДГУ» планувальник не будує — рядок «ДГУ» в API-23 без смуг (див. «Журнал змін документа»).
8. **Вивід `get_schedule(day)`** (API-23): рядки в порядку `bess, chp, vent, light, charging, genset` із назвами «BESS», «КГУ», «Вентиляція RoofVent», «Освітлення цеху», «Зарядна станція», «ДГУ»; `bars[]` — `{from, to, label, cls, source}`, відсортовано за `from`; `manual` перекриває `plan` у конфліктному інтервалі (`plan` обрізається); `now` = поточні години Києва як float (14,333 = 14:20).
9. **Сид** (post_init): `charging` — два `manual`-слоти `mode='charge'` 00:00–06:00 і 22:00–24:00, мітка «заряд», `weekdays='1111111'`; решта — після першого прогону планувальника; усього ≥ 10 слотів на демо-БД.

### R-55 Правила рекомендацій і банер «Виконано» (FR-54; M-36; C-38)

1. **`_td_advice_rule_export_t2(now)`** → `EXPORT-T2`. Умови (усі): мінімальне значення `infra/totals/export_kw` за останні `export_advice_min` хв (за `td.reading`; запасне — `last_value` зі `status='ok'` і свіжим `last_ts`) `> self.export_max_kw`; `energy/cells/QS/state = open`; `infra/totals/pv_now ≥ 1`. Результат: `{code:"EXPORT-T2", dedup_key:"EXPORT-T2", level:"info", node_code:"T2", expires_in_min:60, title:"СЕС віддає {export} кВт у мережу через T2.", text:"Секційний вимикач QS вимкнено, і генерація СЕС більша за навантаження секції 2. Заряд BESS 50 кВт збереже до {until} приблизно {kwh} кВт·год на старт другої зміни.", actions:[{"code":"open_event","label":"Відкрити подію","kind":"link",…}, {"code":"charge_bess","label":"Зарядити BESS 50 кВт","kind":"control","class":"A","params":{"command_kind":"bess_charge","power_kw":50,"until":"{until}","soc_limit_pct":95}}, {"code":"qs_on","label":"Увімкнути QS…","kind":"control","class":"B","params":{"command_kind":"qs_close"}}]}`; `until` — найближче з `16:00`, `23:00`, яке пізніше за `now + 30 хв` (Київ); `kwh = round(50·hours_until / 10)·10` (макет: «приблизно 80 кВт·год»); дія `charge_bess` не повертається, якщо `bess_soc ≥ 95`.
2. **`_td_advice_rule_peak_risk(now)`** → `PEAK-RISK`: сценарій `peak` вимкнений, `grid_kw ≥ peak.limit_kw − peak.activate_margin_kw` безперервно ≥ 2 хв; `level:"warn"`; дії: `enable_peak` (`scenario_toggle`, B), `discharge_bess` (`bess_discharge` 100 кВт, 60 хв, B); текст: «Імпорт {grid} кВт наближається до уставки {limit} кВт. Увімкніть «Зрізання піку» або розрядіть BESS.».
3. **`_td_advice_rule_chp_price(now)`** → `CHP-PRICE`: сценарій `chp` вимкнений; `grid_price − chp_cost ≥ 2·price_margin`; КГУ `chp_state = 0`, `permit = 1`, `gas ≥ min`; `level:"info"`; дії: `enable_chp` (`scenario_toggle`, B), `chp_start` (B); текст: «Газ дешевший за мережу: КГУ вигідно запустити ({grid_price} ₴ проти {chp_cost} ₴ за кВт·год).».
4. **Результат дії → рекомендація.** `td.energy.action` з `advice_id` у стані `done` → `advice._td_on_action_done(action)`: `action_done(note=result_text)` (`state='done'`). **Банер «Виконано»:** override `get_open()` — якщо відкритої рекомендації немає і є `td.energy.action` `origin='advice'`, `state='done'`, `finished_at ≥ now − undo_window_min`, `undo_available` — повертає `{id, code, title, text, level:"info", state:"done", node_code, actions:[{"code":"undo","label":"Скасувати","kind":"control","class":<клас зворотного виду>,"params":{"command_kind":"undo","action_id":<id>},"enabled":true}]}` (`title/text`: BESS — «BESS заряджається {power_kw} кВт.» / «Експорт через T2 усунено, до {until} накопичиться ≈ {kwh} кВт·год.»; QS — «QS увімкнено.» / «Секції працюють разом, генерація СЕС іде на навантаження заводу.»). Після `undo` або спливання вікна банер зникає.
5. Правила виконуються `cron_td_energy_advice` (W1, 5 хв) через реєстр `_td_advice_rule_*`; кожне ≤ 1 с; виключення правила логується й не зупиняє решту; без `read_enabled` не діють.
6. **Сумісність із рекомендаціями W3.** Дії `kind='control'` із правил W3 (`td_energy_resources`) несуть `params={"intent": <ключ>}` замість W1-формату `params.command_kind`. `prepare` приймає такий ключ як `kind` і розгортає через константу `ADVICE_INTENT_ALIASES` (модуль `models/td_energy_control.py`, M-35): `vent_night_mode` → `scenario_toggle` `{scenario:'night', enabled:true}`; `pv_self_consumption` → `scenario_toggle` `{scenario:'self', enabled:true}`; `air_pressure_setpoint` → `air_setpoint` (значення — `params.setpoint_bar`, інакше підставляється `current_bar` і оператор задає значення в діалозі); `heat_schedule_shift` — у W2 немає виду команди (графіки опалення не керуються) → `UserError("Команда «heat_schedule_shift» не підтримується в цій версії.")`, клієнт показує сповіщення, дію не створено. Клас визначається видом (`class: null` у дії W3 допустимий); `advice_id` передається як зазвичай. Контракт розширюється без змін W1/W3 (ризик R9).

### R-56 Журнал і скасування (FR-52; D-19, D-42)

1. **Склад.** `get_journal` (API-28) об'єднує: (а) `td.energy.action` у станах `awaiting_second`, `queued`, `sent`, `executing`, `done`, `failed`, `blocked`, `expired` (`prepared`, `cancelled` не показуються); (б) `td.energy.event` за 24 год із `kind in ('pfc','control')`. Порядок — за часом спадання; пагінація `before_id` (єдиний лічильник: id дії або `-id події`).
2. **Рядки подій.** `what` = «Заявка ТО», якщо в події є заявка (`maintenance_request_id`/посилання W1), інакше `title`; `detail` = `detail` або `title`; `who` = «автоматика»; `result` = «створено» (є заявка) / «виконано» (`resolved`) / «активно»; `ref` = `maintenance.request`.
3. **Рядки автоматики.** `_td_log_auto(ev)` створює `td.energy.action` (`origin='auto'`, `kind_code='auto_<scenario>_<kind>'`, `state='done'`, `idem=ev.event_id`, `summary`, `detail=ev.text`, `actor_text='сценарій «{Пік|Самоспоживання|PFC|Ніч|Резерв|КГУ}»'`, `result_text='виконано'`); `summary` за сигналом: BESS — «BESS · розряд/заряд/зупинка», КГУ — «КГУ · пуск/зупинка», скидання — «Скидання · {name}», `night` — «Вентиляція · нічний/денний режим», інше — за `ev.kind`. Дедуплікація за `event_id`; однакові події ≥ 60 с одна від одної.
4. **Чипи результату:** `done` → «виконано» (`ok`); `done`+`config`+`!applied` → «збережено, очікує збирач» (`info`); `queued/sent/executing` → «виконується» (`info`); `awaiting_second` → «очікує 2-го підтвердження» (`info`); `failed` → «не виконано» (`bad`); `blocked` → «заблоковано» (`bad`); `expired` → «прострочено» (`muted`).
5. **`undo_available`** (обчислюється): `state='done'`; є `undo_kind`; `finished_at ≥ now − undo_window_min`; немає пізнішої дії на тому самому `resource` у `queued…done`; `undone_by_id` порожнє.
6. **`undo(action_id)`**: створює `prepared`-дію `origin='undo'`, `undo_of_id`, вид = `undo_kind`, `params = undo_params` (уставка повітря — попереднє значення; `scenario_toggle` — зворотне `enabled`; `scenario_params` — попередні `params`; `shed_reorder` — попередній порядок; для `qs_*`/`bess_*`/`chp_*` — без параметрів), `summary = "Скасування: {summary оригіналу}"`; далі звичайний `confirm` (права за класом зворотного виду); успіх → `undone_by_id` оригіналу.
7. Журнал не видаляється (ротація — Q-33).

### R-57 Шар «Енергетика в 3D»: правила payload

Перенесено до [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §9 (R-57) і §8.4.2.

### R-58 «Відкрити в 3D» і підсвічування вузла

Перенесено до [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §9 (R-58) і §8.4.4.

### R-59 Емулятор: реакції моделей

Описано в розд. 8.2 (регістри 5.6 і таблиця моделей). Додаткові правила: (1) `cmd`-регістри (QS, КГУ) самоочищаються в наступному тіку; ігнорування команди при `ctl_remote=0` дає `ack=2`; (2) сторожові таймери рахуються за симульованим часом світу (`world.clock`), тому прискорення часу (`POST /sim/v1/time`) прискорює й їх; (3) після `POST /sim/v1/reset` усі прапори керування повертаються до значень за замовчуванням (`bess_mode=0`, `chp_run=False`, `qs_closed=False`, ліміти 100 %, уставка повітря 7,00, `pfc_mode=1`, `pfc_cos_target` із налаштувань світу, `ctl_remote=1`).

### R-60 Безпека: що не керується й як це забезпечено (FR-58; AC-165)

1. **Не керуються взагалі:** пожежна сигналізація, спринклери, димовидалення, блискавкозахист, евакуаційне й аварійне освітлення, СКУД, захист людей, захист верстатів і виробничі зупинки (`workcenters/…`), охоронні системи, ІТ і зв'язок; автоматичні вимикачі фідерів (QF), релейний захист; повне відключення «критичних» навантажень (`is_critical`) — заборонено (частковий/умовний скид пріоритетних критичних вузлів — лише в `peak`, R-51).
2. **Три рівні заборони:** (а) Odoo: `td.signal` модуля `energy_control` не може мати код із префіксами `fire/`, `evacuation/`, `sprinklers/`, `smoke/`, `lightning/`, `access/`, `workcenters/`, `security/`, `yard/` або джерело модулів `fire_safety`, `access`, `machine_connect` (M-38); `td.energy.shed.item` не приймає вузол `is_critical` і виробничі верстати без умови циклу (M-30); (б) конфіг: збирач пише **лише** в сигнали, перелічені в `signals`, `shed[].signal`, `bms.*` API-24; (в) збирач: константа `DENY_PREFIXES` — спроба запису в код із забороненим префіксом → `WriteRefused("заборонено: {префікс}")` і подія `interlock`, навіть якщо він потрапив у конфіг.
3. Пожежна тривога (`fire_state = alarm`) — **вхід**: призупиняє записи ресурсів `vent`/`light` (R-44 п.8) і блокує `light_*`/`vent_*` (`no_fire_alarm`); рушій ніколи не «скидає» її й не взаємодіє з протипожежною логікою.
4. QS — єдина комутаційна операція, лише клас B, лише при `remote=1`, блокуванні АВР і струмі ≤ 80 % номіналу (R-41); дистанційне керування QS на об'єкті — Q-27.
5. У документації й UI — застереження D-26/інформаційна смуга UI-12.

### R-61 Стенд і демо-дані (E-11; FR-67)

1. `hooks._td_enable_stand(env)` (викликає менеджер через `odoo-bin shell`; **не** з `post_init_hook`): `td.telemetry.write_enabled=True`, `td.energy_control.write_enabled=True`, `td.energy_control.automation_enabled=True`, `td.energy_control.remote_switching_enabled=True` (D-46); `write_enabled=True` для джерел `MB-U73-SWB-CMD`, `ENERGY-CTL` і для сигналів `module='energy_control'` з R/W і W (`qs/cmd`, `pfc/*`, `bess/{mode,setpoint_kw,until_soc,valid_s}`, `chp/cmd`, `air/setpoint_bar`, `pv/limit_pct`, `shed/*`, `intent`); для цілей BMS нічного режиму — відповідні сигнали й `td.bms.write_enabled`; повертає перелік змін. Збирач: `F3D_WRITE_ENABLED=true`, `F3D_COMMANDS_POLL_S=2`; емулятор: `SIM_WRITE_ACCEPT=1`.
2. Приймання на стенді (ТК-19…ТК-28): відтворення макета — `export_demo` (експорт 26 кВт, BESS 82 %, QS відкритий), рекомендація EXPORT-T2 → «Зарядити BESS 50 кВт» → діалог → виконано → «Скасувати»; QS: діалог із перевіркою «блокування АВР — гаразд», друге підтвердження; `peak_load` → BESS → КГУ → скидання; `mains_loss` → резервне живлення; нічний режим на межі `23:00` (час світу `POST /sim/v1/time`); `pfc_step_fault` лишається сценарієм W1.
3. Генератор історії (W1 R-36) уже наповнює профіль для плану (R-54).

### R-62 Шина `td_energy_control` і оновлення клієнтів (A-41)

Рядковий канал `td_energy_control`, тип `td_energy_control/update`, повідомлення `{"kinds": ["action"|"scenario"|"engine"|"schedule"|"shed"], "ts": iso_utc}` без даних; `tools/bus.py` модуля копіює механіку W1 R-33 (накопичення в `precommit`, `_sendone` у `postcommit`, throttle `td.energy.bus_throttle_s` на воркер, збій шини ковтається); хто тікає: `td.energy.action._td_close`/переходи (`action`), `scenario._td_apply_change`/`_td_engine_update` (`scenario`), `control.state._td_report` (`engine`), планувальник (`schedule`), зміни `shed.item` (`shed`). Клієнт: `kind → частини get_control` (`action` → `journal`, `pending`; `scenario` → `scenarios`; `engine` → `engine`; `schedule` → `schedule`; `shed` → `shed`), дебаунс 2 с, резервне опитування 30 с. Додатково — тіки W1 `td_energy.tools.bus` (`state`, `advice`) після дій над QS/BESS/КГУ і рекомендаціями, щоб оновлювався Пульт.

### R-63 Час і часовий пояс

Зберігання — UTC naive; «Київ» — `Europe/Kyiv` (`tools/dates.py` W1, `zoneinfo` у плагіні). `time_from/time_to` слотів, вікна `night`, зони тарифу, `bess_charge.until` — **настінний** місцевий час. Доба 23/25 год (перехід DST): шкала `get_schedule` лишається 00…24; нічне вікно слідує за настінними годинами; `valid_s` для `bess_charge` = різниця абсолютних UTC-моментів (не годин на шкалі); блок попиту 15 хв (R-45) — за UTC-епохою; тіки DST не створюють подвійних/пропущених блоків. День тижня слотів і `night.days` — локальний (1 = понеділок).

### R-64 Продуктивність і обсяги

`get_control` ≤ 400 мс і ≤ 40 SQL (один `search_read` сигналів керування, один пошук дій/подій для журналу); `prepare` ≤ 300 мс, `confirm` ≤ 300 мс; API-24 ≤ 200 мс (ETag-кеш у `state`, перерахунок не частіше 1 разу на хвилину й після `bump`); API-25 ≤ 300 мс для 100 дій і 200 подій; тік рушія ≤ 50 мс p95, пам'ять плагіна ≤ 60 МБ, записів у пристрої ≤ 30/хв; обсяги: `td.energy.action` ≈ 100–300/доба (події автоматики тротляться ≥ 60 с), ≈ 70 000/рік, індекси `(state, create_date)`, `(kind_code, state)`; `td.command` ≈ 1 на дію; `Store` ≤ 1 МБ.

### R-65 Некоректні дані й конфіг

(1) Odoo: `ValidationError` для `params` сценаріїв/слотів/пріоритетів (M-29…M-34); API-24 завжди віддає валідний JSON за схемою (порожні масиви замість `null`); (2) збирач: невідомі ключі в `scenarios.*.params` ігноруються з попередженням, відсутні — дефолти коду; значення поза межами — межа коду (R-41 п.6, R-44 п.6) і подія `config`; `slots` із `from ≥ to` відкидаються; `shed[]` із відсутнім сигналом пропускається; (3) інтент із невідомим `kind`/`v` → `rejected`; (4) читання назад із `q != good` вважається відсутнім значенням.

### R-66 Міграція й деінсталяція

Нове встановлення (перша версія `19.0.1.0.0`): `post_init_hook` (розд. 1, 5.6) — ідемпотентний; міграцій немає. Повторне `-u` не змінює кількостей (AC-235). **Деінсталяція (D-45):** архівних таблиць немає — модуль видаляється разом зі своїми даними, як будь-який модуль Odoo. `uninstall_hook` видаляє службові дані (сигнали й джерела `energy_control`/`energy_ctl`, крони, параметри), скидає прапори `write_enabled`/`automation_enabled`/`remote_switching_enabled` і публікує порожню конфігурацію; журнал `td.energy.action`, сценарії, пріоритети скидання, слоти, блокування й види команд видаляються разом із моделями. Повторне встановлення створює дані заново (`post_init_hook`). `td_energy` після видалення модуля: `meta.control_available=false` (W1 `_td_control_available` дивиться на `ir.module.module`), кнопки `kind='control'` у Пульті зникають (обробник не зареєстровано; D-02).

### R-67 Тест ДГУ через адаптер (`td_genset_factory3d`; FR-66, FR-69; ADP-12)

1. Виконавець `genset` (R-40 п.6): `tools/genset_link.start_test()` → `adapters.td_genset.start_test(gen, 'idle', user)`; `gen` — перший активний `td.genset` (`adapters.generators(env)`); генератора немає → `blocked` «Генератор не налаштовано».
2. Перевірки діалогу (Odoo): `genset_fuel` (м'яка, ≥ `min_pct`), `genset_heater` (м'яка, `coolant_c ≥ 30` або `unknown`), `no_island` (жорстка), `genset_idle` (жорстка: `not running`, `not test_running`, `mains_ok`) — значення з `adapters.test_facts`.
3. Результат: `UserError` `td_genset` (наприклад, «Тест уже йде.») → дія `blocked` із текстом; успіх → `done`, `result_text="Тест ДГУ прийнято td_genset: {minutes} хв"`, `ref` на запис `td.genset`; фактичний пуск і підтвердження — скінченний автомат `td.genset.command` (до `done`/`failed` із тривогою `td_genset`) — поза журналом W2.
4. Клас B; права — `group_td_energy_manager` + друге підтвердження або `chief`; `td_genset` не змінюється.

## 10. Стани й переходи

| Об'єкт | Стани | Переходи (хто) |
|---|---|---|
| `td.energy.action.state` | `prepared → awaiting_second → queued → sent → executing → done`; `prepared/awaiting_second → expired/cancelled`; `queued/sent/executing → failed/blocked/expired`; `prepared/awaiting_second/queued → blocked`; `expired → executing/done/failed/blocked` (лише звіт збирача за `idem`) | `prepare`, `confirm`, `confirm_second`, `_td_enqueue`, `td.command` (M-37), API-25, `_cron_expire`, `cancel` |
| `td.command.state` (команди W2) | `queued → sent → done/failed/expired/cancelled` | збирач (`GET commands`, `POST commands/result`), `_cron_expire` `td_telemetry` |
| `td.energy.scenario.engine_state` | `unknown ⇄ off/armed/active/warn` | API-25 (рушій); `unknown` — немає звіту `2·heartbeat_stale_s` |
| `td.energy.control.state.engine_mode` | `unknown/off/hold/auto` | API-25 |
| Інтент у збирачі | `accepted → executing → done/failed`; `rejected/blocked` (без виконання) | `Executor` |
| Режим рушія | `off ⇄ auto ⇄ hold` | R-44 п.1 |
| Етап `peak` | `idle → bess → chp → shed → idle` | R-45 |

## 11. Обробка помилок

- Усі публічні методи `td.energy.control` на вході: група; `AccessError("Немає доступу до Енергетики.")`; частини `get_control` ізольовані — помилка однієї (`scenarios`, `shed`, `commands`, `schedule`, `journal`) → `{"error": "…"}` у цій частині, решта віддаються, `_logger.exception` (UI: «Не вдалося завантажити: {частина}»).
- Сигнали несвіжі/відсутні → перевірки `unknown`, `null` у значеннях; методи не кидають виключень через відсутність даних.
- Перегони: `confirm`/`confirm_second` — `FOR UPDATE`; два «других» підтвердження — програв другий (`UserError("Дія вже підтверджена.")`).
- Часові пояси — R-63. Шина недоступна — ковтається (резервне опитування).
- Помилки збирача — таблиця R-53; тексти українською, без внутрішніх шляхів і токенів.
- HTTP: тіло JSON-конверт `{"error": {"code","message"}}` (як `td_telemetry`).

## 12. Acceptance Criteria

Колонка «Тип»: UT (юніт-тест Odoo), UT-JS (hoot), UT-PY (pytest збирача/плагіна/емулятора, без Odoo), TC (стенд), MAN (ручна перевірка). Усі тести Odoo — `post_install`, `-at_install`, тег `td`. Фікстури — розд. 13.0. Колонка «FR» — вимога ARCH §1.3. **Разом: AC-159…AC-310 = 152 критерії** (AC-159…AC-308 = 150 у початковій редакції + AC-309, AC-310 за D-46): `td_energy_control` + плагін + емулятор + міст 3D — AC-159…AC-274, AC-282…AC-310; `td_genset_factory3d` ADP-12 — AC-275…AC-277; `td_viewer3d` R-26 — AC-278…AC-281.

### 12.1 Сценарії й конфігурація — AC-159…AC-170

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-159 | FR-46 | Given чиста установка; Then `td.energy.scenario` має рівно 6 записів `peak,self,pfc,night,backup,chp`; `enabled`: peak, pfc, night, backup — `True`, self, chp — `False`; `description` рівно як у макеті (5.2); `create`/`unlink` не-адміністратором → `AccessError` | UT |
| AC-160 | FR-46 | Given `scenario.params`; When `limit_kw=50`, або `night.from="25:00"`, або невідомий ключ, або `days=[0,8]`; Then `ValidationError` «Сценарій {name}: параметр {key} — …»; значення за замовчуванням — валідні для всіх 6 сценаріїв | UT |
| AC-161 | FR-47 | Given `engine_state='armed'`, `facts.margin_kw=402` для `peak`; When `_td_state_text()`; Then «Чергування · запас 402 кВт», `state_kind='arm'`; `enabled=False` → «Вимкнено», `off`; `pfc` `warn` із `fault="PFC-2 ступінь 3"` → «Збій: PFC-2 ступінь 3», `warn`; `night` `armed` із `next_run="23:00"` → «Наступний запуск о 23:00»; `self` `active`, `bess_kw=26` → «Активний · заряд BESS 26 кВт»; `backup` `armed` `fuel_pct=78` → «Готовий · паливо 78 %»; немає звіту ≥ `2·heartbeat_stale_s` → «Немає даних від рушія» | UT |
| AC-162 | FR-47 | Given сид; Then `chips()` відтворює макет: peak «уставка 760 кВт · 95 %», «прогноз 15 хв»; self «експорт ≤ 20 кВт», «BESS до 95 %»; pfc «ціль cos φ 0,95», «крок 35 квар»; night «23:00–06:30», «RoofVent 30 %», «16 °C»; backup «АВР → ДГУ», «критичні 180 кВт»; chp «мін. робота 2 год», «ціна газу 19,80 ₴/м³» | UT |
| AC-163 | FR-47, FR-53 | Given manager; When `scenario.write({'enabled': True})` без контексту дії → `AccessError`; When `prepare('scenario_toggle', {scenario:'peak', enabled:False})` + `confirm` (chief) → `enabled=False`, `config_version` = поточна версія стану, `changed_by`; зворотна зміна через `undo` | UT |
| AC-164 | FR-57 | Given `state`; When двічі `bump()` (також два паралельні UPDATE) → +2 без дублів; зміна `scenario.params`, `shed.item.sequence`, `interlock.params`, слота `executes`, `td.energy.cos_phi_target` → `config_version` зростає; зміна `engine_facts`/`engine_ts` — ні | UT |
| AC-165 | FR-58 | Given сигнал `module='energy_control'`; When код `fire/panel/x`, `workcenters/SAW-1/x`, `access/x`, або джерело `module='fire_safety'`; Then `ValidationError` «Сигнал {code}: керування цією системою заборонене.»; `module='energy'` + `write_enabled=True` → `ValidationError` (W1 AC-81 діє) | UT |
| AC-166 | FR-57 | Given збирач із токеном; When `GET /td/energy/automation/config`; Then 200 JSON з усіма ключами 7.3 (`schema=1`, `config_version`, `etag`, `flags`, `engine`, `plant`, `scenarios`, `shed`, `never_shed`, `slots`, `tariff`, `bms`, `signals`, `inputs`, `derived`, `interlocks`, `limits`) і заголовками `ETag`, `X-Config-Version`; повторний з `If-None-Match` → 304; після `bump()` → 200 з новим `etag`; без токена/з невірним → 401; вимкнений збирач → 403; `POST` → 405 JSON; відповідь не містить `cost`, токенів, паролів | UT |
| AC-167 | FR-57 | Given конфіг; Then `etag` не залежить від `server_time`/порядку ключів; зміна `limit_kw` змінює `etag`; розмір відповіді на демо-даних (6 сценаріїв, 5 скидань, ≤ 40 слотів, 25 RoofVent) ≤ 64 КБ | UT |
| AC-168 | FR-47 | Given `td_bms` із 25 установками `roofvent` (`mode_signal_id`, `sp_night_signal_id`) і групами освітлення; Then `bms.night.vent` має 25 елементів із `mode_signal`, `bms.night.light` — групи зі `scene_signal`, `aisle=true` лише для `fixture_kind='highbay_rack'`; `light_break` не містить `aisle`-груп; відсутні сигнали → порожні масиви | UT |
| AC-169 | FR-57 | Given `scenario_toggle` виконано; When до `POST state` → `applied=False` (чип «Очікує застосування»); після `POST state` з `config_version_applied ≥ config_version` → `applied=True`; `state.applied_version` не зменшується | UT |
| AC-170 | FR-51 | Given `get_control().engine`; Then heartbeat свіжий + `mode=auto` → `level='ok'`, `label="Контролер ГРЩ і збирач на зв'язку · HH:MM"`; `mode=hold` → `warn`; heartbeat старший за `heartbeat_stale_s` → `bad`, «Збирач не на зв'язку · {вік}»; `automation_enabled=False` → `warn`, «автоматику призупинено» | UT |

### 12.2 Пріоритети скидання — AC-171…AC-176

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-171 | FR-48 | Given сид; Then 5 рядків у порядку макета (CHARGING, RV-ALL, DRY-1, COMPRESSOR, LP-1), `kw_reducible` 48/60/17/37/12, `how` рівно: «відкласти заряд до 30 хв», «знизити до 70 %», «пауза до 20 хв, без втрати циклу», «вимкнути, тиск ≥ 6,5 бар», «знизити до 50 %» | UT |
| AC-172 | FR-48, FR-58 | Given `shed.item`; When вузол `is_critical` з `action='off'` і `condition='none'` (з `reduce` або з умовою — дозволено, `critical=True`); або `DRY-1` з `condition≠no_active_cycle`; або другий активний рядок на той самий вузол; Then `ValidationError` (або `IntegrityError` для дубля) з текстами M-30; `kw_reducible > p_inst_kw` — лише попередження | UT |
| AC-173 | FR-48 | Given `prepare('shed_reorder', {order:[…]})`; When `confirm` (chief) → порядок змінено, `config_version` +1; manager → `awaiting_second` і порядок не змінено до другого підтвердження; зворотний `undo` відновлює порядок | UT |
| AC-174 | FR-48 | Given `get_control().shed`; Then `sum_kw=174`; `never` містить 5 фраз макета; `never_nodes` = коди вузлів `is_critical` без активного рядка пріоритету; `limit_kw=760` | UT |
| AC-175 | FR-57 | Given API-24; Then `shed[]` за `seq`, кожен елемент має `signal=energy_control/shed/<node>/limit_pct`; неактивні не віддаються; `critical` = `node.is_critical`; `never_shed` = критичні вузли без активного рядка + `NEVER_SHED_CODES` | UT |
| AC-176 | FR-48, FR-53 | Given ролі; When `create/write/unlink` `shed.item`: manager → `AccessError`; chief → дозволено й створює `td.energy.action` (`kind_code='shed_edit'`, `cls='B'`, `state='done'`) і `bump()`; user → `AccessError` | UT |

### 12.3 Види команд, потік, класи й права — AC-177…AC-194

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-177 | FR-49 | Given сид; Then 16 видів; 8 `tile=True` у порядку макета (qs_close, bess_charge, bess_discharge, chp_start, genset_test, light_break, vent_eco, air_setpoint); клас A — bess_charge, bess_stop, light_break, light_restore, vent_eco, vent_restore; решта B; `executor/resource/checks` за 5.3 | UT |
| AC-178 | FR-49, FR-53 | Given `get_control().commands`; Then 8 плиток із `label/sub` макета («Заряд BESS 50 кВт» / «до 16:00 або 95 %», «Освітлення цеху · сценарій «Перерва»» / «50 % на 30 хв», …); user → `enabled=False`, `disabled_reason` «Немає прав: потрібна роль «Енергетик»»; `write_enabled=False` → `enabled=False` для `intent`/`genset` | UT |
| AC-179 | FR-50 | Given manager; When `prepare('qs_close')`; Then ключі відповіді 7.2, `ttl_s=60`, `checks` у порядку виду, `needs_second=True` (chief → `False`), токен ≥ 32 символів; у БД лише `token_hash` (sha256), токена немає | UT |
| AC-180 | FR-50 | Given `prepare`; When повтор ≤ 5 с тим самим користувачем/`kind`/`params`; Then той самий `action_id`, новий токен, старий недійсний; після 5 с — новий запис | UT |
| AC-181 | FR-49 | Given `bess_charge`; When `power_kw=500`, або `until` у минулому, або `soc_limit_pct=40`; Then `ValidationError`/`UserError` («параметр … поза межами 1…100 кВт») | UT |
| AC-182 | FR-50, FR-55 | Given клас A, manager; When `confirm(token)`; Then дія `queued`; створено **одну** `td.command` (`signal=energy_control/intent`, `payload.v=1`, `payload.kind='bess_charge'`, `origin='energy'`, `expires_at ≈ now+120 с`, `energy_action_id`); повторний `confirm` того самого токена повертає той самий стан без нової команди | UT |
| AC-183 | FR-50 | Given токен; When чужий користувач → `AccessError`; прострочений → дія `expired` + `UserError`; невідомий → `UserError`; після `cancel` → `UserError` | UT |
| AC-184 | FR-53 | Given клас B; When manager `confirm` → `awaiting_second`, `second_expires_at ≈ now+600`, `td.command` немає; chief → одразу `queued` | UT |
| AC-185 | FR-53 | Given `awaiting_second`; When той самий користувач → `UserError`; інший manager → `queued`, `second_by`; view-only → `AccessError`; іншому chief дозволено; після `second_expires_at` → `expired` | UT |
| AC-186 | FR-53 | Given `awaiting_second`; Then `mail.activity` ≤ 10 manager-ам, окрім ініціатора; закривається при виконанні/спливанні; `get_control().pending` показує дію лише manager-ам, `can_confirm_second=False` для ініціатора | UT |
| AC-187 | FR-50 | Given дія на ресурс `bess` у `queued/sent/executing`; When `confirm` нової дії на `bess`; Then вона `blocked` «Для ресурсу «bess» уже виконується дія …» | UT |
| AC-188 | FR-55 | Given `td.command`; When стан `sent` → дія `sent`; `done` з `result_data.accepted=true` → `executing`; `done` з `accepted=false,state=blocked` → `blocked`; `state=rejected` → `failed`; `failed` → `failed`; `expired` → `expired`; `cancelled` → `cancelled` | UT |
| AC-189 | FR-55 | Given API-25 `actions[]`; When `done` → `finished_at`, `result_text`, `bus` `action`; дія з `advice_id` → `advice.state='done'`; повтор того самого стану — без ефекту; стан «назад» → `rejected: already_final`; дія `expired` + звіт `done` за `idem` → `done` | UT |
| AC-190 | FR-47, FR-57 | Given `scenario_toggle`; When `confirm`; Then одразу `done`, `config_version` збільшено, `applied=False`, `result_text` «збережено, очікує збирач»; після звіту збирача — «виконано» | UT |
| AC-191 | FR-50 | Given `cancel(token)`; Then `prepared` → `cancelled`; повтор ідемпотентний; `queued` → `td.command` `cancelled` і дія `cancelled`; `executing` → `UserError` | UT |
| AC-192 | FR-58 | Given `td.energy_control.write_enabled=False`; When `prepare('qs_close')` → `UserError` «Керування вимкнено…»; When `write_enabled=True`, але `write_enabled` джерела `ENERGY-CTL`/сигналу `False` → `confirm` дає `blocked` «Запис вимкнено: …», `td.command` не створена | UT |
| AC-193 | FR-55 | Given `td.command.create` з `origin='energy'`; When поза модулем (без контексту й `energy_action_id`) → `UserError`; без групи менеджера телеметрії й не `sudo` → `AccessError` (наявне правило) | UT |
| AC-194 | FR-66 | Given без моста `td_genset_factory3d`; Then `genset_test.available=False`, причина «Не встановлено міст td_genset_factory3d», `prepare` → `UserError`; з мостом — `available=True` | UT |
| AC-309 | FR-58 | Given `td.energy_control.remote_switching_enabled=False` (D-46); When `prepare` для `qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test`; Then `UserError` «Дистанційне перемикання вимкнено: td.energy_control.remote_switching_enabled…»; ті самі дії, підготовлені до вимкнення прапора, не проходять `confirm`/`confirm_second`; `get_control().commands[]` для них `enabled=false` з причиною; `bess_charge`, `bess_stop`, `chp_stop`, `light_*`, `vent_*`, `air_setpoint`, `scenario_*`, `shed_reorder` не зачеплені | UT |
| AC-310 | FR-58 | Given прапор `True`; Then `prepare('qs_close')` проходить як в AC-177…AC-194; `API-24 flags.remote_switching_enabled` дорівнює значенню параметра й змінює ETag; `neutralize.sql` і нове встановлення без demo дають `False`; demo-дані й `_td_enable_stand` дають `True` | UT |

### 12.4 Реєстр блокувань — AC-195…AC-204

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-195 | FR-51 | Given реалізація Odoo; When золоті випадки R-41 п.5 для `controller_remote`, `no_island`, `ats_parallel_lock`, `data_fresh`; Then очікувані `ok/fail/unknown` | UT |
| AC-196 | FR-51 | When `qs_current_ok`: `p1=150,p2=100,cos=0,95` → `ok`, підпис «≈ 40 А з 1600 А»; `p1=1700,p2=0` → `fail`; QS уже `closed` → `ok` | UT |
| AC-197 | FR-51 | When `bess_ok`, `bess_soc_lt_limit` (82<95 ok; 95 fail), `bess_reserve_kept` (82 %, 100 кВт, 60 хв → 56,2 ok; 50 % → 24,2 fail), `bess_temp_ok` (24 ok, 41 fail, — unknown) | UT |
| AC-198 | FR-51 | When `chp_ready` (0 ok; 1/2/3 fail), `chp_gas_pressure` (2,10 ok; 0,80 fail), `chp_permit` (1/0/—), `chp_min_run` | UT |
| AC-199 | FR-51 | When `air_setpoint_min` (6,5 ok; 6,3 fail; 8,6 fail), `aisle_lux_ge` (80 ok; 60 fail; — unknown), `co2_lt` (620 ok; 1200 fail), `genset_fuel`, `genset_idle`, `no_fire_alarm` (немає сигналу → ok «не підключено») | UT |
| AC-200 | FR-51 | Given комбінації `hard/fail_closed/state`; Then `blocked` за R-41 п.3: `hard`+`fail` → блок; `hard`+`unknown`+`fail_closed` → блок; `hard`+`unknown`+`¬fail_closed` → не блок; м'яка `fail` → не блок; `where='collector'` → `unknown` «перевіряє збирач» без блоку | UT |
| AC-201 | FR-51 | Given сигнал із `last_ts` старшим за `max(3·period_s, 60 с)` або `status='stale'`; Then значення `None` → `unknown` | UT |
| AC-202 | FR-51 | Given `td.energy.interlock`; When `code` невідомий → `ValidationError`; `params` змінює не-адмін → `AccessError`; адмін → запис `interlock_param` у журналі й `bump()` | UT |
| AC-203 | FR-51 | Given `lock=0`; When `prepare('qs_close')` → `blocked=True`, `blocked_reason` «Блокування паралельної роботи T1 і T2 від АВР — не виконано»; `confirm` → дія `blocked`, `td.command` не створена | UT |
| AC-204 | FR-51 | Given `light_break`; When lux-сигналів немає → `aisle_lux_ge='unknown'`, `blocked=False`; `fire/panel/state=alarm` → `no_fire_alarm='fail'`, `blocked=True` | UT |

### 12.5 Журнал і скасування — AC-205…AC-210

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-205 | FR-52 | Given дії в різних станах; When `get_journal`; Then спадання за часом; `prepared`/`cancelled` відсутні; рядок має `what/detail/who/result/result_kind` за D-19; `before_id` дає наступну сторінку; `limit` ≤ `journal_limit` | UT |
| AC-206 | FR-52 | Given подія `kind='pfc'` із заявкою ТО; Then рядок «Заявка ТО» · деталь події · «автоматика» · «створено», `ref` на `maintenance.request` | UT |
| AC-207 | FR-52, FR-68 | Given `events[]` API-25; When `_td_log_auto(ev)`; Then запис `origin='auto'`, `actor_text='сценарій «Пік»'`, `summary` «BESS · розряд», `result_text='виконано'`; повторний `event_id` ігнорується | UT |
| AC-208 | FR-52, FR-54 | Given виконана `bess_charge`; When ≤ 15 хв → `undo_available=True`; `undo(id)` → `prepared`-дія `bess_stop`, `origin='undo'`, `undo_of_id`; після `done` в оригіналу `undone_by_id`, `undo_available=False`; > 15 хв або нова дія на `bess` → `False` | UT |
| AC-209 | FR-52 | When `undo` для `qs_close` → `qs_open` (клас B), `air_setpoint` → повернення `current_bar`, `scenario_toggle` → зворотне `enabled`, `scenario_params` → попередні `params`, `shed_reorder` → попередній порядок | UT |
| AC-210 | FR-52 | Given дія; Then чаттер містить «Підготовлено», «Підтверджено», «Результат»; форма `td.command` показує `energy_action_id` (V-43) | UT |

### 12.6 Розклад — AC-211…AC-216

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-211 | FR-53 | When `get_schedule()`; Then 6 рядків у порядку «BESS», «КГУ», «Вентиляція RoofVent», «Освітлення цеху», «Зарядна станція», «ДГУ»; `now` — години Києва float; `bars[]` відсортовано за `from`, `0 ≤ from < to ≤ 24` | UT |
| AC-212 | FR-53 | Given історія `_td_backfill`; When `_td_plan_day`; Then BESS-смуги `discharge`/`charge` за R-54 п.3 у межах 0…24; без історії (< `forecast_min_days`) — запасний план (07:30–11:00 розряд, 11:00–16:00 заряд, 16:00–17:30 розряд) | UT |
| AC-213 | FR-53 | Given `night.enabled`; Then `vent`: «ніч 30 %» 0–06:30, «день 100 %» 06:30–23:00, «ніч 30 %» 23:00–24; `light`: «черговий»/«робочий»/«черговий»; `night.enabled=False` — одна смуга; `chp.enabled=False` → рядок КГУ порожній, `True` → смуги за ціною | UT |
| AC-214 | FR-53 | When слот `time_to ≤ time_from` → `ValidationError`; `manual`-слот створює/змінює не-chief → `AccessError`; chief → дія `schedule_edit` (B) і `bump()` | UT |
| AC-215 | FR-53 | Given `manual`-слот BESS у вікні `plan`; Then у виводі `plan` обрізано; `executes=True` лише для `manual` `bess/chp`; `slots[]` конфігу містить лише `executes=True`, `active` | UT |
| AC-216 | FR-53 | When `_td_plan_day` двічі; Then та сама кількість слотів; `plan` старший за 2 доби видаляються; доба 25 год (DST) не дає слотів поза 0…24 | UT |

### 12.7 Рекомендації — AC-217…AC-222

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-217 | FR-54 | Given `export_kw` > 20 щонайменше 5 хв, `QS=open`, `pv_now ≥ 1` (14:20); When `_cron_advice`; Then `EXPORT-T2` із `title` «СЕС віддає 26 кВт у мережу через T2.», `text` макета (`until=16:00`, «приблизно 80 кВт·год»), діями `open_event`, `charge_bess` (control, A), `qs_on` (control, B); QS `closed` або експорту немає → рекомендації немає; `soc ≥ 95` → дії `charge_bess` немає | UT |
| AC-218 | FR-54 | Given `peak` вимкнений, `grid_kw ≥ limit−30` ≥ 2 хв → `PEAK-RISK`; `chp` вимкнений, `grid_price − chp_cost ≥ 2·margin`, КГУ готова → `CHP-PRICE`; умова зникла → `expired`; дубль за `dedup_key` не створюється | UT |
| AC-219 | FR-54 | Given `td_energy_control` встановлено; When `get_open()`; Then дії `kind='control'` мають `enabled=True` і `class` (`A`/`B`), `meta.control_available=true` | UT |
| AC-220 | FR-54 | Given `prepare('bess_charge', …, advice_id)` → `confirm` → `done`; Then `advice.state='done'`, `result_note=result_text`; Given дія W3 з `params.intent`: `vent_night_mode`, `pv_self_consumption`, `air_pressure_setpoint` → `prepare` створює `scenario_toggle night`, `scenario_toggle self`, `air_setpoint`; `heat_schedule_shift` → `UserError` без створення дії (R-55 п.6) | UT |
| AC-221 | FR-54 | Given виконана дія рекомендації; When `get_open()`; Then банер `state='done'` (BESS: «BESS заряджається 50 кВт.» / «Експорт через T2 усунено, до 16:00 накопичиться ≈ 80 кВт·год.») з дією `undo`; після `undo` або спливання `undo_window_min` → `False` | UT |
| AC-222 | FR-54 | Given `td_energy_control` не встановлено; Then `meta.control_available=false`, кнопки `control` не віддаються (W1 AC-116/AC-117 лишаються зеленими) | UT |

### 12.8 HTTP, безпека, дані, крони — AC-223…AC-235

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-223 | FR-57 | When `POST state` валідний; Then оновлено `engine_mode`, `heartbeat_at`, `scenario.engine_*`, `applied_version`; відповідь `accepted_actions/accepted_events/rejected`; повтор `event_id` ігнорується; «назад» → `rejected: already_final`; невідомий `id` → `rejected: unknown_action` | UT |
| AC-224 | FR-57 | When `actions` > 100 або `events` > 200 → 400 `bad_schema`; тіло > 256 КБ → 413; не JSON → 400 `bad_json`; `collector` ≠ токен → 403 `collector_mismatch`; без токена → 401; `GET` → 405 | UT |
| AC-225 | FR-68 | Given `events[]` `interlock`/`failsafe`/`mode(hold)`; Then запис журналу `origin='auto'` і `td.energy.event` `kind='control'` (значення `kind` додано `selection_add`; dedup 60 хв; `_td_log` W1); `auto_step`/`auto_release` — лише журнал; події `control` старші за 24 год → `resolved` | UT |
| AC-226 | FR-53 | Given матриця 4.2; Then user не може `prepare`; manager не може `confirm` B одноосібно; chief може; admin редагує `command.kind`/`interlock.params`; прямий `write` на `action`, `scenario`, `control.state` заборонений усім, окрім контексту модуля | UT |
| AC-227 | FR-58 | When токен іншого користувача; повторне використання після `cancel`; рядки з лапками/`;--` у `kind`/`params`; `params` не dict; Then відмови без побічних ефектів, SQL-ін'єкцій немає | UT |
| AC-228 | FR-60 | Given `td.source` `type='energy_ctl'`; When з `collector_id` і `params={"engine":{"tick_s":2}}` → OK; без колектора → `ValidationError`; `tick_s=50` або секрет у `params` → `ValidationError`; `module='energy_control'` допустимий | UT |
| AC-229 | FR-60, FR-61 | Given демо-БД після W1; When `post_init_hook`; Then `td.source` 138, `td.signal` `energy_control` +36 з адресами HR 200…291 (28 на `MB-U73-SWB-CMD` + 8 на `ENERGY-CTL`), scenarios 6, kinds 16, interlocks 20, shed 5, slots ≥ 10, state 1; `write_enabled=False` скрізь; повтор не змінює кількостей | UT |
| AC-230 | FR-67 | When `hooks._td_enable_stand(env)`; Then прапори `td.telemetry.write_enabled`, `td.energy_control.write_enabled`, `automation_enabled` = `True`, `write_enabled` джерел і сигналів `energy_control`, що записуються; повертає перелік змін; `post_init_hook` цього не робить | UT |
| AC-231 | FR-61 | When `neutralize.sql`; Then прапори `write_enabled`/`automation_enabled` = `False`, джерела й сигнали `energy_control` без запису/читання, 3 крон-завдання вимкнені, команди `origin='energy'` у `queued/sent` → `cancelled` | UT |
| AC-232 | FR-61 | When `uninstall_hook` і видалення модуля (D-45); Then джерела/сигнали `energy_control`, крон-завдання, параметри видалені, прапори скинуті; таблиць `td_energy_*_archive` **немає**; дані моделей модуля видалені разом із ними; `meta.control_available=false` у `td_energy`; повторне встановлення створює дані заново (`post_init_hook`), `_restore_archive` не існує | UT |
| AC-233 | FR-50 | When `_cron_expire`; Then прострочені `prepared` → `expired`; `awaiting_second` > 600 с → `expired`; `queued/sent` прострочена команда → `expired`; `executing` довше за `exec_timeout_s + 30` → `failed` і `td.energy.event kind='control'`; конфіг-дія без застосування > 60 с → подія один раз | UT |
| AC-234 | FR-57 | When `_cron_watch`; Then `automation_enabled` і heartbeat старший за `4·heartbeat_stale_s` → подія `CTRL-HEARTBEAT` (dedup 15 хв), авторозв'язання при відновленні; зміна BMS-цілей/тарифу → `config_etag` змінюється й `bump()` | UT |
| AC-235 | FR-61 | Given `td_energy_control` встановлено; Then регресія: `td_energy` (W0 142 + W1), `td_telemetry` (`td.command`), `td_bms` зелені; повторне `-u td_energy_control` не змінює кількостей | UT |

### 12.9 Ядро збирача — AC-236…AC-238

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-236 | FR-55 | Given `LiveCache`; When `update/get/age_s/snapshot/note_write`; Then вік обчислюється за годинником; `Scheduler`/`Emitter` подають показання після масштабу ядра; без `live` поведінка не змінюється (наявні тести ядра зелені) | UT-PY |
| AC-237 | FR-55 | Given `PluginContext`; Then нові поля `live/write_signal/read_signal/odoo/clock/state_dir` мають `None` за замовчуванням; `_make_ctx` заповнює їх для будь-якого джерела; плагіни `modbus_tcp`, `bacnet_ip`, `mqtt`, `http_push`, `helvarnet`, `sics` працюють без змін | UT-PY |
| AC-238 | FR-55, FR-58 | When `write_direct`: пише лише при всіх запобіжниках (`source.write_enabled`, `signal.write_enabled`, `registry.write_enabled`, `settings.write_enabled`, `expires_at`), інакше `WriteRefused` із причиною; тайм-аут; не пише в буфер результатів; `read_now` повертає `Reading` із масштабом ядра й оновлює `LiveCache` | UT-PY |

### 12.10 Плагін `td_collector_energy`: конфіг, блокування, режими — AC-239…AC-248

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-239 | FR-57 | Given fake Odoo; When завантаження API-24: 200, потім `If-None-Match` → 304; Odoo недоступна ≤ 7 діб → працює з кешу `Store`; невалідний конфіг → лишається попередній валідний, `engine.reason="config invalid: …"`, подія `config` | UT-PY |
| AC-240 | FR-57 | When конфіг без необов'язкових ключів → дефолти коду; невідомі ключі `params` → попередження; `slots` із `from ≥ to` відкинуті; `shed[]` без сигналу пропущені | UT-PY |
| AC-241 | FR-51 | Given реєстр CHECKS збирача; When золоті випадки R-41 п.5 (усі перевірки `where ∈ {both, collector}`); Then ті самі очікування, що в AC-195…AC-199 | UT-PY |
| AC-242 | FR-51 | When `hard`+`unknown`+`fail_closed` → блок; `soft`+`unknown` → не блок; `where='odoo'` не виконується; свіжість `max(3·period, max_age_s)` | UT-PY |
| AC-243 | FR-58 | When значення конфігу поза межею (`bess_kw_max=500`, `air_bar_max=9,5`, `min_bar=0,5`, `max_ratio=0,95`); Then застосовано межу коду (200; 8,5; 1,0; 0,9) і подія `config` | UT-PY |
| AC-244 | FR-56 | When `automation_enabled=false` або `write_enabled=false` → `off` (0 записів); `remote=0`, `grid_kw` несвіжий > `stale_hold_s`, перевищено частоту записів → `hold`; інакше `auto`; пожежна тривога режим не змінює (D-48): режим `auto`, записи `vent/light` блокуються, подія `interlock`; `night` не залежить від `remote` (D-49); кожен перехід режиму — подія `mode` | UT-PY |
| AC-245 | FR-56 | Given ручне перекриття `bess`; Then `peak/self` не пишуть BESS (подія `override` раз); `backup` > `peak` > `self` > `slots` > `chp` > `night`; розряд `peak` перемагає заряд `self` | UT-PY |
| AC-246 | FR-56 | When `Actuator`: запис лише при зміні й не частіше за `min_write_interval_s`; примусові режими перезаписуються кожні `valid_s/3`; невдалий запис → повтор, 3 поспіль → сценарій `warn` + `failsafe`; `> max_writes_per_min` → `hold` 5 хв | UT-PY |
| AC-247 | FR-57 | Given Odoo недоступна 10 хв (fake clock); Then рушій діє за кешем, `Reporter` буферизує ≤ 200 дій / 1000 подій (старіші відкидаються з лічильником) і надсилає після відновлення | UT-PY |
| AC-248 | FR-56 | When рестарт; Then `Store` відновлює володіння, перекриття, `shed_list`; розбіжність із пристроєм (читання назад) скидає володіння; інтенти `executing` звітуються `failed` «рушій перезапущено…» | UT-PY |

### 12.11 Плагін: сценарії — AC-249…AC-258

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-249 | FR-56 | `peak`: блок 15 хв за UTC-епохою; `proj=(acc+grid·remaining)/900`; активація при `proj ≥ limit−30` або `grid ≥ limit`; перехід DST не створює подвійних/пропущених блоків | UT-PY |
| AC-250 | FR-56 | `peak` ступінь 1: `limit=760`, `grid=800`, SOC 82 → запит BESS `{mode:2, setpoint=clamp(bess_now+excess,0,100), until_soc=30, valid_s=30}`; SOC ≤ 32 → BESS недоступний, подія `interlock`; перезапис кожні 10 с | UT-PY |
| AC-251 | FR-56 | `peak` ступені 2–3: `uncovered>0` ≥ `stage_delay_s` → `chp start` (перевірки ok, `started_by='peak'`); КГУ недоступна/заборонена → скидання за пріоритетами до покриття `uncovered`; не ескалює, поки КГУ розганяється | UT-PY |
| AC-252 | FR-56 | `peak` відпускання: `release_hold_s` → відновлення у зворотному порядку з кроком `shed_restore_step_s`; КГУ `stop` лише після `min_run_h`; BESS ramp-down до `mode=0`; подія `auto_release` | UT-PY |
| AC-253 | FR-56 | `self`: експорт 26 кВт, SOC 82 → BESS `{mode:1, setpoint=clamp(…), until_soc=95}`; експорт ≤ 25 — без дій; обмеження СЕС інтегральне після `curtail_delay_s`; відновлення +5 % після `restore_hold_s` | UT-PY |
| AC-254 | FR-56 | `self`: SOC ≥ 95 → лише curtail; `peak` активний → `self` не заряджає | UT-PY |
| AC-255 | FR-56 | `pfc`: enabled → `pfc_mode=1`, `pfc_cos=0,95` (регістр 95; з `plant.cos_phi_target`); disabled → `pfc_mode=0`; `fault_step=3` → `warn` «PFC-2 ступінь 3»; рушій не створює подій-заявок | UT-PY |
| AC-256 | FR-56 | `night`: вікно 23:00–06:30 через північ і `days`; вхід — `vent_mode`, `sp_night`, сцена чергового; вихід — `day_vent_mode`, `light_scene_day_number`; старт усередині вікна ідемпотентний; DST (остання неділя жовтня/березня) — за настінним часом; ручна зміна цілі → `overridden` до межі; `bms.night` порожній → `warn` | UT-PY |
| AC-257 | FR-56 | `backup`: `src1_ok=0` ≥ 2 тіків (4 с) → скидання за пріоритетами до `need=max(0,p_total−0,9·507)`; елементи `critical=true` і `never_shed` пропускаються; `peak` призупинено; відновлення після `restore_delay_s` за кроками | UT-PY |
| AC-258 | FR-56 | `chp`: `grid 8,4 − (19,80·0,25=4,95) ≥ 0,5` → пуск (перевірки ok, `min_off_min` минув); слот `chp`; зупинка лише після `min_run_h` і `started_by='chp'`; КГУ `peak`/manual не зупиняється; `chp_state=3` → `warn` | UT-PY |

### 12.12 Плагін: інтенти й виконавець — AC-259…AC-268

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-259 | FR-55 | When `call()` валідного інтента → `accepted=true` ≤ 1 с; `v≠1`, невідомий `kind`, `params` поза межами, `expires_at` у минулому → `rejected` із причиною; дубль `idem` → `duplicate:true`; ресурс зайнятий → `rejected: busy: bess` | UT-PY |
| AC-260 | FR-55 | Given fake `write_signal/read_signal`; Then для кожного з 12 видів інтентів послідовність записів і верифікація відповідають таблиці R-42 п.3 | UT-PY |
| AC-261 | FR-55 | `qs_close`: `qs_ack=2` → `failed` «Контролер відмовив: блокування»; `qs_state=closed` ≤ 10 с → `done`; `qs_state` не змінився → `failed` | UT-PY |
| AC-262 | FR-55 | `bess_charge`: `valid_s` = секунди до `until` (Київ; максимум 43 200), `until ≤ now` → `rejected`; невдала верифікація → fail-safe `bess_mode=0`; м'яка перевірка `bess_kw` → примітка в `result` | UT-PY |
| AC-263 | FR-55 | When помилка запису → 1 повтор; друга → `failed` + fail-safe; `exec_timeout_s` (60) → `failed`; тайм-аут верифікації → `failed` | UT-PY |
| AC-264 | FR-58 | Given `lock=0` → `blocked` без жодного запису; `remote=0` → `blocked`; код із `DENY_PREFIXES` або поза конфігом → `WriteRefused` + подія `interlock` | UT-PY |
| AC-265 | FR-56 | Given `bess_charge` done → перекриття `bess` до `valid_s`; `light_break` → автовідновлення через `duration_min` (подія `auto_release`); `bess_stop`/`light_restore` знімають; `chp_start` → володіння manual | UT-PY |
| AC-266 | FR-57 | When `Reporter`: пакетування, негайне надсилання зміни дії, повтор при 5xx/429 з бекофом, дедуп `event_id`, ліміти 100/200 за запит, throttle однакових подій ≥ 60 с | UT-PY |
| AC-267 | FR-57 | When `Store`: атомарний запис (tmp+rename), відкидання > 7 діб, ліміт 500 інтентів/24 год, пошкоджений файл → старт із порожнього стану й подія | UT-PY |
| AC-268 | FR-55 | When `EnergyCtlPlugin`: `validate`, єдиний екземпляр, `subscribe` створює 4 задачі, `health()` online/error, `disconnect` без записів у пристрої, heartbeat `Reading` `energy_control/auto/heartbeat` кожні 10 с | UT-PY |

### 12.13 Емулятор — AC-269…AC-274

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-269 | FR-59 | Given `swbctl`; When FC3/FC6 на HR 200…291; Then читання/запис за 5.6, значення поза межами → exception 3, `write_accept=False` → exception 4, `cmd` самоочищаються, heartbeat росте на симульовану секунду, `ctl_remote=0` → `ack=2` | UT-PY |
| AC-270 | FR-59 | BESS: режими 0–3, `until_soc`, `setpoint`; `valid_s` → 0 за часом світу повертає режим 0; розряд при SOC ≤ 30 → `ack=2`, режим не змінюється; температура = `25+0,05·\|P\|` | UT-PY |
| AC-271 | FR-59 | `qs/cmd=2` → QS замкнений лише при `parallel_lock=1` і без острова, `energy/cells/QS/state=1`, Q1=Q2; інакше `ack=2`; `pfc_mode=0` → `steps_on=0`; `pfc_cos_target` змінює `steps_on` | UT-PY |
| AC-272 | FR-59 | `chp/cmd=1` → `chp_run`, розгін за `chp_start_s`; відмова (`ack=2`) при `gas<1,5` або `permit=0`; `air/setpoint=6,50` → тиск ≈ 6,31 бар, `7,00` → 6,81 (W0 збережено) | UT-PY |
| AC-273 | FR-59 | `shed/<CODE>/limit_pct` зменшує `consumer_p` пропорційно; `pv/limit_pct` зменшує `p_kw` інверторів; `shed/valid_s` → 0 повертає всі ліміти й `pv/limit_pct` до 100 | UT-PY |
| AC-274 | FR-59, FR-67 | Сценарії `peak_load {extra_kw}`, `export_demo {export_kw}` (експорт рівно `export_kw`, BESS авто 0 кВт), `ctl_local`, `chp_no_gas`; `POST /sim/v1/reset` повертає значення за замовчуванням (R-59 п.3) | UT-PY |

### 12.14 Міст ДГУ — AC-275…AC-277 (розширення переглядача R-26, AC-278…AC-281, — [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §12.1)

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-275 | FR-69 | Given `td_genset_factory3d`; When `start_test(gen,'idle',user)`; Then викликається `_test_start('idle', user)` під `sudo`, відповідь `{accepted, minutes, test_end, ref}`; `mode='load'` → `UserError` «Лише тест без навантаження»; `UserError` `td_genset` («Тест уже йде.») пробрасується | UT |
| AC-276 | FR-69 | When `test_facts(gen)`; Then `fuel_pct`, `running`, `test_running`, `island`, `coolant_c`; без знімка — `None` без виключень | UT |
| AC-277 | FR-66, FR-69 | Given міст; When `genset_test` (manager + друге підтвердження або chief); Then `done` з `ref` на `td.genset`, `result_text` «Тест ДГУ прийнято td_genset: N хв»; «Тест уже йде.» → `blocked`; перевірки `genset_fuel`, `genset_heater`, `genset_idle`, `no_island` у діалозі | UT |

### 12.15 «Енергетика в 3D» — AC-282…AC-293

AC-282…AC-293 перенесено до [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §12.2 (єдина нумерація W2).


### 12.16 Екран «Керування» (UI) і правки клієнта td_energy — AC-294…AC-303

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-294 | FR-46 | Given `HttpCase`; When відкрити `action_td_energy_control`; Then без JS-помилок, h1 «Керування енергетикою заводу», інформаційна смуга, чип зв'язку (3 стани), меню «Керування» (seq 8) і «Журнал команд» | UT |
| AC-295 | FR-47 | hoot: 6 карток, чипи/текст, `role="switch"` + `aria-checked`, «увімкнено N з 6», клік по перемикачу відкриває діалог і **не** змінює стан без `confirm`, чип «Очікує застосування» при `!applied` | UT-JS |
| AC-296 | FR-48 | hoot: 5 пріоритетів, «Разом можна зняти 174 кВт», режим «Змінити порядок» (кнопки «Вище»/«Нижче» 36 × 36 з `aria-label`), «Зберегти порядок» відкриває діалог `shed_reorder`, «Скасувати» повертає порядок | UT-JS |
| AC-297 | FR-49 | hoot: 8 плиток у порядку макета, `disabled` + `title` за правами/запобіжником, бейдж «B» | UT-JS |
| AC-298 | FR-49, FR-50 | hoot: діалог — заголовок «{title}?», перевірки «гаразд/не виконано/немає даних», «Виконати» `disabled` при `blocked`, «Підтвердити (1/2)» для B manager, відлік TTL, Esc → `cancel`, прогрес «Надіслано → Виконується → Виконано/Не виконано», фокус у діалозі | UT-JS |
| AC-299 | FR-52, FR-53 | hoot: розклад — 6 рядків, `left/width` смуг за `from/to`, вертикаль «зараз», текстова таблиця; журнал — рядки з чипами, «Скасувати дію», «Підтвердити (2/2)», «Показати більше» | UT-JS |
| AC-300 | FR-54 | hoot: у `td_energy.advice_handlers` є `control`; клік «Зарядити BESS 50 кВт» → діалог `bess_charge` з `advice_id`; після `done` Пульт перечитує `advice`/`alarms`; банер «Виконано» зі «Скасувати» → діалог `undo` | UT-JS |
| AC-301 | FR-46 | hoot (td_energy client §3.4 п.2): панель вузла `QS`/`BESS` містить кнопки з реєстру `td_energy.node_actions` залежно від стану («Увімкнути QS…»/«Вимкнути QS…», «Зарядити 50 кВт»/«Зупинити заряд»); без реєстру — як у W1 | UT-JS |
| AC-302 | FR-54 | hoot (§3.4 п.3): `advice.state==='done'` → зелений банер без «Пізніше», зі «Скасувати» | UT-JS |
| AC-303 | FR-46 | MAN: десктоп 1440 і планшет 1024 — без горизонтального скролу (окрім розкладу), клавіатурна навігація, видимий фокус; скріншоти екрана й діалогу для приймання | MAN |

### 12.17 Наскрізні перевірки на стенді — AC-304…AC-308

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-304 | FR-54, FR-55 | ТК-20: `export_demo` (експорт 26 кВт, BESS 82 %, QS відкритий); When EXPORT-T2 → «Зарядити BESS 50 кВт» → діалог → «Виконати»; Then ≤ 30 с `td.energy.action` `done`, `bess_mode=1` в емуляторі, `bess_kw ≈ +50`, експорт зникає, банер «Виконано»; «Скасувати» → `bess_mode=0` | TC |
| AC-305 | FR-49, FR-51, FR-53 | ТК-21: «Увімкнути QS…» (manager): діалог із «Блокування паралельної роботи T1 і T2 від АВР — гаразд», «Підтвердити (1/2)» → другий енергетик «Підтвердити (2/2)» → `energy/cells/QS/state=closed`, Q1=Q2; `lock=0` в емуляторі → «заблоковано», 0 записів; `ctl_local` → «не виконано: контролер у місцевому режимі»; «Скасувати» → QS open | TC |
| AC-306 | FR-56 | ТК-23: `peak_load` (+300 кВт) при ввімкненому `peak`; Then BESS розряд → (≥ 60 с) КГУ пуск → (≥ 60 с) скидання в порядку списку; `grid_kw` ≤ `limit_kw`; після зняття навантаження — відновлення у зворотному порядку, КГУ зупиняється після `min_run_h`, BESS `mode=0`; журнал «сценарій «Пік»» | TC |
| AC-307 | FR-56 | ТК-25/26: (а) час світу 22:59 → 23:00: `night` → BMS-цілі отримали `VEL`/черговий сценарій; 06:30 — день; (б) `mains_loss`: `backup` скинув неважливі, критичні лишилися; після відновлення мережі +`restore_delay_s` — повернені | TC |
| AC-308 | FR-57 | ТК-27: зупинити збирач → ≤ 60 с BESS/скидання повернулися (сторожові таймери), чип «Збирач не на зв'язку», подія `CTRL-HEARTBEAT`; зупинити Odoo на 5 хв → автоматика діє, після запуску журнал і стани доповнені; рестарт збирача → володіння відновлено, `executing` інтенти `failed`; вимкнення `write_enabled` посеред виконання → решта кроків скасована | TC |

## 13. План тестування (для Opus)

### 13.0 Фікстури й вимоги до тестованості

- `td_energy_control/tests/common.py`: `TestControlCommon(TransactionCase)` — `_user(groups)` (користувачі `viewer` = `group_td_energy_user`, `en1`, `en2` = `group_td_energy_manager`, `chief` = `group_td_energy_chief`, `admin`); `_fresh(code, value, text=None, age_s=0)` (запис `td.signal.last_value/last_ts/status`); `_snapshot_1420()` — стан макета 14:20 (`grid_kw=356`, `export_kw=26`, `pv_now=309`, `bess_soc=82`, `bess_state=1`, `chp_state=0`, `ats_pos=2`, `src1_ok=1`, `QS=open`, `lock=1`, `remote=1`, `gas=2,10`, `permit=1`, `air_min=6,20`, `p1/p2` для струму QS 38 А); `_enable_control()` (прапори, `write_enabled` джерел/сигналів); `_collector()` (збирач із токеном для HTTP-тестів); час — мок `td_energy.tools.dates.now_utc`.
- Плагін: `tests/fakes.py` — `FakeClock` (кероване `sleep/now/monotonic`), `FakeLive`, `FakeDevice` (карта регістрів і реакції BESS/QS/КГУ за R-59), `FakeCtx` (записи `write_signal`, `read_signal` із `FakeDevice`, `emit`), `FakeOdoo` (aiohttp-сервер API-24/25 з керованими відповідями й збоями), `golden.py` (таблиця R-41 п.5 як дані); усі тести детерміновані (без реального часу й мережі).
- Емулятор: наявний `tests/conftest.py` (світ із каталогом, годинник, `world.set_flag`).
- JS: hoot (`web.assets_unit_tests`), мок `orm.call` повертає JSON із розд. 7; фікстура `static/tests/fixtures/contracts.js`.
- Часові функції викликаються через `dates.now_utc(env)`/`Clock`, які мокуються; генератор історії (`_td_backfill`) — детермінований за `seed`.

### 13.1 Юніт-тести

**Бекенд Odoo (A)** — `F3D_TEST_INSTALL=td_energy,td_bms,td_energy_control $T/run_tests.sh <db> /td_energy_control:<Клас>`:

| Файл | Клас | Покриває |
|---|---|---|
| `test_scenario.py` | `TestScenario` | AC-159…AC-164, AC-169 |
| `test_shed.py` | `TestShed` | AC-171…AC-176 |
| `test_kinds.py` | `TestKinds` | AC-177, AC-178, AC-181, AC-194 |
| `test_action_flow.py` | `TestActionFlow` | AC-179, AC-180, AC-182, AC-183, AC-187…AC-193 |
| `test_action_second.py` | `TestActionSecond` | AC-184…AC-186 |
| `test_interlocks.py` | `TestInterlocks` | AC-195…AC-204 |
| `test_undo.py` | `TestUndo` | AC-208, AC-209 |
| `test_journal.py` | `TestJournal` | AC-205…AC-207, AC-210, AC-225 |
| `test_schedule.py` | `TestSchedule` | AC-211…AC-216 |
| `test_advice_rules.py` | `TestAdviceRules` | AC-217…AC-222 |
| `test_config_api.py` | `TestConfigApi` | AC-166…AC-168, AC-175 |
| `test_state_api.py` | `TestStateApi` | AC-170, AC-223, AC-224 |
| `test_intent_payload.py` | `TestIntentPayload` | AC-182 (форма `payload`), AC-188 |
| `test_security.py` | `TestSecurity` | AC-226, AC-227 |
| `test_source_signal.py` | `TestSourceSignal` | AC-165, AC-228 |
| `test_hooks.py` | `TestHooks` | AC-229, AC-230, AC-232, AC-235 |
| `test_neutralize.py` | `TestNeutralize` | AC-231 |
| `test_crons.py` | `TestCrons` | AC-233, AC-234 |
| `test_genset_exec.py` | `TestGensetExec` | AC-194, AC-277 (з імітацією адаптера, якщо міст не встановлено) |
| `test_remote_switching.py` | `TestRemoteSwitching` | AC-309, AC-310 |
| `test_contracts.py` | `TestContracts` | набір ключів API-16/17/18/22/24/25/26/28 дорівнює `contracts/*.json` (заморозка C-38…C-47) |
| `td_genset_factory3d/tests/test_adp12.py` | `TestAdp12` | AC-275, AC-276 (`F3D_TEST_INSTALL=td_energy,td_genset,td_genset_factory3d $T/run_tests.sh <db> /td_genset_factory3d:TestAdp12`) |

**Фронтенд (B)**: `test_ui.py::TestControlUi` (HttpCase, AC-294); `test_hoot.py::TestControlHoot.test_hoot_suite` (запускає `/web/tests?headless…&id=<hash('@td_energy_control')>` за зразком `td_energy/tests/test_w1_hoot.py`) — AC-295…AC-302 (файли `control.test.js`, `confirm_dialog.test.js`, `advice_handler.test.js`, `node_actions.test.js`); `td_energy/static/tests/control_hooks.test.js` — AC-292, AC-301 (гаки), AC-302 (виконується наявним hoot-набором `td_energy` `TestW1Hoot`); AC-303 — MAN.

**Збирач, плагін, емулятор (C)**, pytest (`pytest -q`):

| Файл | Покриває |
|---|---|
| `services/collector/tests/unit/test_live.py`, `test_ctx_extension.py`, `test_write_direct.py` | AC-236…AC-238 |
| `td_collector_energy/tests/test_config.py` | AC-239, AC-240, AC-243 |
| `test_interlocks.py` | AC-241, AC-242 (золоті випадки з `golden.py`) |
| `test_engine.py` | AC-244, AC-245, AC-247, AC-248 |
| `test_actuator.py` | AC-246 |
| `test_scenario_peak.py` | AC-249…AC-252 |
| `test_scenario_self.py`, `test_scenario_pfc.py` | AC-253…AC-255 |
| `test_scenario_night.py` | AC-256 (зокрема DST) |
| `test_scenario_backup.py`, `test_scenario_chp.py` | AC-257, AC-258 |
| `test_intents.py` | AC-259…AC-262 |
| `test_executor.py` | AC-263…AC-265 |
| `test_reporter.py`, `test_store.py`, `test_plugin.py` | AC-266…AC-268 |
| `services/iot_sim/tests/unit/test_swbctl.py` | AC-269 |
| `services/iot_sim/tests/unit/test_control_models.py` | AC-270…AC-274 |

**Міст 3D і переглядач (D)**: тести `td_energy_viewer3d` і `td_viewer3d` (AC-278…AC-293) — [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §13.1.

### 13.2 Стендові сценарії ТК-19…ТК-28 (`td_energy_control/tests/stand/test_tk_control.py` + Playwright)

Передумови (E-11): постійні сервіси тестового сервера — емулятор `iot_sim` і збирач із плагіном `td_collector_energy`; встановлено `td_energy`, `td_energy_control`, `td_bms`, `td_genset`, `td_genset_factory3d`, `td_viewer3d`, `td_energy_viewer3d`, `td_iot_sim`; виконано `_td_backfill(days=90)` (W1); `hooks._td_enable_stand(env)`; збирач `F3D_WRITE_ENABLED=true`, `F3D_COMMANDS_POLL_S=2`; емулятор `SIM_WRITE_ACCEPT=1`; користувачі `viewer`, `en1`, `en2`, `chief`.

| ТК | Назва | Кроки | Очікується |
|---|---|---|---|
| ТК-19 | Екран живий | `en1`: «Енергетика → Керування», чекати 90 с | чип «Контролер ГРЩ і збирач на зв'язку · HH:MM»; 6 карток, «увімкнено 4 з 6» (peak, pfc, night, backup); пріоритети (5, «174 кВт»); 8 плиток; розклад із 6 рядків і лінією «зараз»; журнал; без помилок консолі; значення оновлюються без перезавантаження (шина) |
| ТК-20 | Рекомендація → BESS → «Скасувати» (AC-304) | `POST /sim/v1/scenario/export_demo/start {"export_kw": 26}`; QS відкритий; чекати 5 хв → Пульт показує EXPORT-T2; «Зарядити BESS 50 кВт» → діалог → «Виконати» | ≤ 30 с дія `done`; емулятор `bess_mode=1`, `bess_kw ≈ +50`; експорт ≈ 0; банер «Виконано … Скасувати»; «Скасувати» → `bess_mode=0`, журнал «Скасування» |
| ТК-21 | QS: діалог, друге підтвердження, блокування (AC-305) | `en1`: «Увімкнути QS…» → діалог із «Блокування … — гаразд», «Струм ≈ N А з 1600 А» → «Підтвердити (1/2)»; `en2`: банер/журнал «Підтвердити (2/2)»; повтор із `lock=0` (прапор емулятора) і `ctl_local` | QS `closed`, Q1=Q2; з `lock=0` — «заблоковано», у журналі 0 записів пристрою; `ctl_local` — «Контролер у дистанційному режимі — не виконано»; `chief` виконує без другого підтвердження; «Скасувати» → QS open |
| ТК-22 | Інші команди | `chief`: `bess_discharge` 100 кВт/60 хв; `chp_start`; `air_setpoint` 6,5; `genset_test`; `en1`: `light_break`, `vent_eco`; `en1` пробує `chp_start` | розряд −100 кВт і режим 2 (до `valid_s`); КГУ `run` (прискорення часу — D-33); тиск ≈ 6,31 бар, `undo` → 6,81; td_genset приймає тест (`td.genset.command`); BMS-сигнали записані, після `duration_min` (час світу) відновлено автоматично; `en1` → `awaiting_second` |
| ТК-23 | Зрізання піку (AC-306) | `peak` увімкнений; `POST /sim/v1/scenario/peak_load/start {"extra_kw": 300}` | BESS розряд → (≥ 60 с) КГУ → (≥ 60 с) скидання за списком; `grid_kw ≤ limit_kw`; після `stop` — відновлення у зворотному порядку; журнал «сценарій «Пік»»; чип `peak` «Зрізання піку · …» → «Чергування · запас … кВт» |
| ТК-24 | Самоспоживання й PFC | увімкнути `self` (клас B, 2 особи); `export_demo` 26; SOC → 95; вимкнути/ввімкнути `pfc`; `pfc_step_fault {section:2, step:3}` | BESS заряджається за експортом, при SOC 95 — обмеження СЕС і повернення; `pfc` вимкнений → `pfc_mode=0`, ступені 0, cos φ нижче норми (W1 чип), ввімкнений → відновлено; з несправністю — чип «Збій: PFC-2 ступінь 3», заявка ТО від W1 |
| ТК-25 | Нічний режим (AC-307а) | `POST /sim/v1/time` → 22:59, потім 23:00; потім 06:30 | о 23:00 цілі BMS отримали `VEL`/черговий сценарій/16 °C, журнал «Вентиляція · нічний режим»; о 06:30 — день (`VE`), «RoofVent 25 шт. → 100 %»; чип «Наступний запуск о 23:00» ↔ «Активний до 06:30» |
| ТК-26 | Резервне живлення (AC-307б) | `mains_loss` (сценарій W0), після — відновлення | `backup` `active`, неважливі навантаження скинуті, критичні лишилися; після відновлення + `restore_delay_s` — повернені; чип «Мережі немає · скинуто N» → «Готовий · паливо 78 %» |
| ТК-27 | Відмови (AC-308) | зупинити збирач; запустити; зупинити Odoo на 5 хв; вимкнути `write_enabled` посеред виконання | сторожові таймери повертають BESS/скидання ≤ 60 с; чип «Збирач не на зв'язку», подія `CTRL-HEARTBEAT`; автономія за кешем; після рестарту володіння відновлено; решта кроків скасована |
| ТК-28 | 3D (AC-293) | див. [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §13.2 | — |

### 13.3 Тести безпеки (ТБ-11…ТБ-15)

- ТБ-11: токени й ідемпотентність — чужий/прострочений/повторний токен, ін'єкції в `kind`/`params`, подвійний `confirm` (AC-183, AC-182, AC-227).
- ТБ-12: заборона керування системами безпеки — Odoo (AC-165, AC-172), конфіг (`signals`-allowlist), збирач `DENY_PREFIXES` і запис поза конфігом (AC-264); пожежна тривога блокує `vent/light` (AC-204, AC-244).
- ТБ-13: права E-06 — user/manager/chief/admin за матрицею 4.2, друге підтвердження іншою особою, заборона самопідтвердження й обходу адміністратором (AC-184…AC-186, AC-226).
- ТБ-14: запобіжники — кожен із шести окремо вимикає запис (`td.telemetry.write_enabled`, `td.energy_control.write_enabled`, `source.write_enabled`, `signal.write_enabled`, `F3D_WRITE_ENABLED`, `automation_enabled` для автоматики); `neutralize.sql`; `module='energy'` лишається read-only (AC-192, AC-238, AC-244, AC-231, AC-165); перемикач `remote_switching_enabled` (AC-309, AC-310).
- ТБ-15: HTTP — Bearer, `collector_mismatch`, ліміти, rate-limit, відсутність секретів/вартості у відповідях API-24/25 (AC-166, AC-224).

### 13.4 Тести продуктивності (ТП-10…ТП-12)

- ТП-10: `get_control` ≤ 400 мс і ≤ 40 SQL, `prepare`/`confirm` ≤ 300 мс, API-24 ≤ 200 мс, API-25 (100 дій + 200 подій) ≤ 300 мс (R-64).
- ТП-11 (`energy.layer`, 3D) — [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §13.4.
- ТП-12: тік рушія ≤ 50 мс p95 на 1000 тіків; пам'ять ≤ 60 МБ за 1 год із `FakeOdoo`; записів у пристрої ≤ 30/хв; `Store` ≤ 1 МБ.

### 13.5 DEPLOY_TEST (новий `docs/modules/td_energy_control/DEPLOY_TEST.md`)

1. Копія демо-БД після W1 → `-i td_energy_control,td_energy_viewer3d`: кількості (розд. 5.6: `td.source` 138, сигнали `energy_control` +36, scenarios 6, kinds 16, interlocks 20, shed 5, slots ≥ 10); `write_enabled=False` і `automation_enabled=False`; екран відкривається, плитки показують «Керування вимкнено адміністратором».
2. Повторне `-u`: без змін; `neutralize.sql`; відкат: `uninstall` видаляє дані модуля без архівних таблиць (D-45), Пульт `td_energy` без кнопок керування, 3D-шар зникає, `td_viewer3d` працює; повторне встановлення створює дані заново (AC-232).
3. Стенд: встановити плагін збирача (`pip install`), перезапустити збирач, `ENERGY-CTL` стає `online`; `_td_enable_stand`; ТК-19…ТК-28.
4. Регресія: `/td_energy`, `/td_telemetry`, `/td_bms`, `/td_viewer3d`, `/td_constructor_viewer3d`, `/td_genset_factory3d`; `pytest` збирача, плагінів і емулятора.

## 14. Definition of Done (W2)

- Усі UT/UT-JS/UT-PY AC-159…AC-302 (окрім MAN/TC) зелені; ТК-19…ТК-28 пройдені на стенді; AC-303 (скріншоти) прийнято.
- Регресія зелена: `td_energy` (W0 142 + W1), `td_telemetry`, `td_bms`, `td_viewer3d` (AC-01…AC-67), `td_constructor_viewer3d`, `td_genset_factory3d` (101), `td_genset` (223), збирач (`pytest tests/unit`), плагіни `f3d_collector_*`, емулятор (`tests/unit`).
- `ruff` без помилок (модулі Odoo, плагін, ядро збирача, емулятор); JS — перевірка `rjsmin` (без вкладених шаблонних літералів у `core.js`).
- `neutralize.sql`, `CHANGELOG`/`README` модулів (`td_energy_control`, `td_energy_viewer3d`, `td_collector_energy`), `DEPLOY_TEST`; огляд безпеки ТБ-11…ТБ-15; інструкція ARCH §4.
- Запобіжники за замовчуванням вимкнені в `post_init_hook`; `_td_enable_stand` не викликається автоматично.
- Документи розкладено в `docs/modules/*`: `td_energy_control`, `td_energy_viewer3d` (R-26/VX `td_viewer3d` — у `td_energy_viewer3d/SPEC.md`), ADP-12 `td_genset_factory3d` — розд. 8.3 цього файлу.

## 15. Відкриті питання й рішення автора

Питання Q-26…Q-33 — ARCH §5 (ті самі номери).

### Рішення автора (A-38…A-62; A-63 — міст ДГУ; A-64…A-67 — рішення збірки)

| ID | Рішення | Обґрунтування |
|---|---|---|
| A-38 | Параметри модуля — `td.energy_control.*` (`write_enabled`, `automation_enabled`, …), а не `td.energy.control_enabled` із GAP §6 п.13 | Конвенція `docs/ARCHITECTURE.md` §5 (`td.<module>.<param>`); стоп-кран `write_enabled` = «п'ятий запобіжник» |
| A-39 | До класу B віднесено також `scenario_params`, `shed_edit`, `schedule_edit`, `interlock_param`, `chp_stop`, `qs_open` | E-06 називає частину дій; решта — тієї самої природи (зміна уставок/складу/станів) |
| A-40 | Тип джерела `energy_ctl` реєструється валідаторами `PARAMS_VALIDATORS/ADDRESS_VALIDATORS` при імпорті `td_energy_control` | Не змінюємо `td_telemetry` у W2; офіційна точка розширення — Q-30 |
| A-41 | Власна шина `td_energy_control` (kinds `action/scenario/engine/schedule/shed`); бекенд `td_energy` не змінюється; клієнтські правки `td_energy` мінімальні (розд. 3.4) | Білий список `KINDS` у W1 `tools/bus.py`; ізоляція модуля |
| A-42 | Новий модуль `td_energy_control`, а не розширення `td_energy` (обґрунтування ARCH §2.1) | Керування вимикається/видаляється без втрати читального застосунку; запобіжники за замовчуванням; окремий цикл тестів і ризиків; слот `control_available` уже передбачено W1 (C-32) |
| A-43 | Рушій — `push_mode`-плагін `energy_ctl` у збирачі + адитивне розширення `PluginContext` (`live`, `write_signal`, `read_signal`, `odoo`) | Мінімальні зміни ядра, зворотна сумісність, ті самі запобіжники запису; без окремого процесу |
| A-44 | Кроки виконання видів інтентів і межі `params` — **власність збирача**; Odoo передає `kind` + `params` | Hard-блокування й безпека не залежать від довіри до даних Odoo; перевірка Odoo — підказка (GAP §2.3) |
| A-45 | Вікно керування на `SWB-CTRL` (unit 73, HR 200…291) — єдине джерело `MB-U73-SWB-CMD` для стенда. **Підтверджено менеджером (Q-26): припущення зберігається; карти регістрів реальних об'єктів — пізніше (дані `address`, код не змінюється)** | Один контролер ГРЩ як точка керування (E-03); на об'єкті змінюється лише `address` (Q-26) |
| A-46 | Усі команди пристроям — рівневі (встановлюють значення), не перемикачі | Безпечний повтор, ідемпотентність при дублюванні доставки |
| A-47 | Сторожові таймери: `bess/valid_s`, `shed/valid_s` (разом із `pv/limit_pct`) — «мертва рука» контролера | Fail-safe при падінні збирача/рушія (R-53 №7) |
| A-48 | Тексти чипів сценаріїв складає Odoo за шаблоном із чисел рушія | Мова й узгодженість із макетом; рушій без UI-рядків |
| A-49 | Двокроковий потік `prepare → confirm` з токеном (TTL 60 с), `confirm` ідемпотентний; діалог показує перевірки з Odoo | Діалог макета; захист від подвійних кліків |
| A-50 | Дії `config` застосовуються в Odoo одразу, «застосованість» — за `applied_version` збирача; чип «Очікує застосування» | Істину про виконання дає збирач (D-20) |
| A-51 | Журнал = `td.energy.action` + події W1; скасування — окрема дія в межах `undo_window_min`; **при деінсталяції дані модуля видаляються разом із ним, архівних таблиць немає (D-45, рішення менеджера)** (R-66) | Єдиний бізнес-журнал (GAP CT-14); права за класом; поведінка як у будь-якого модуля Odoo |
| A-54 | Нічний режим — режими BMS `VEL`/`VE` і `sp_night`; «30 %» — довідковий текст | Що вміє `td_bms` (D-40) |
| A-55 | Емулятор: скидання через `consumer_p` у `meter.py`; `export_demo`, `peak_load`; ручний режим PFC вимикає ступені | Відтворюваність макета на стенді |
| A-56 | Обмеження СЕС (`pv/limit_pct`) ділить сторожовий таймер зі скиданням (`shed/valid_s`) | Менше регістрів; однакова семантика fail-safe |
| A-57 | «Зрізання піку» v1 — ступінчастий гістерезисний алгоритм за прогнозом 15-хв блока; не оптимізатор | Простота, перевірюваність, безпека |
| A-58 | План дня (`plan`/`scenario`) інформаційний; виконуються лише ручні слоти BESS/КГУ | Прогноз не є командою; E-06 для редагування |
| A-59 | Вимкнення сценарію `pfc` пише `pfc_mode=0` (клас B) | Семантика перемикача макета |
| A-60 | Друге підтвердження — інша особа, TTL 600 с, без обходу адміністратором | E-06 |
| A-61 | Жорсткі перевірки: `fail_closed` для безпекокритичних, `fail_open` для комфортних; прапори на рядку реєстру | Доступність без втрати безпеки (R-41) |
| A-62 | Тест ДГУ — через адаптер моста (ADP-12), лише `idle`, `td_genset` не змінюється | E-01 |
| A-63 | (`td_genset_factory3d`) ADP-12 викликає `_test_start('idle')` під `sudo`; права перевіряє `td_energy_control` | `td_genset._td_check_group` пропускає `env.su`; права «Енергетика» ≠ `group_tech` |
| A-64 | (реалізація A) Відповідь API-24 несе заголовок `X-Config-Version` (і при 200, і при 304): `config_version` не входить в ETag (R-43 п.2), тому при `bump()` без зміни вмісту збирач інакше не дізнався б нову версію й `applied_version` відстав би | Чип «Очікує застосування» не повинен зависати; адитивно, старі клієнти заголовок ігнорують |
| A-65 | (реалізація A) `never_shed` API-24 = критичні вузли без активного рядка пріоритетів + константа `NEVER_SHED_CODES` (`EF-ELEC`, `EF-CHG`, `DUST-1`); `shed.item` без сигналу обмеження не створюється (сигнали є лише в 5 вузлів таблиці 5.5) | Збирач пише лише в сигнали, перелічені в конфігу (R-60 п.2 б) |
| A-66 | (реалізація A) План дня (R-54 п.7): слоти `genset` режиму `test` не будуються — `adapters.schedule_info` віддає текстові вікна, а не тест-слоти; рядок «ДГУ» розкладу порожній | ADP-06 не містить структурованих вікон; рядок лишається у виводі (6 рядків, AC-211) |
| A-67 | (реалізація A) Номер дії — `ir.sequence` `td.energy.action` (`seq_action`, `ACT/%(y)s/#####`), `idem = sha1("<id>:<kind_code>")`; для подій автоматики `idem = event_id` (≤ 40 символів) | Єдина унікальність `idem` (частковий `UNIQUE`) і дедуплікація подій |
| A-52, A-53, X-93 | (міст 3D) | Перенесено до [td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) §15 (рішення про шар 3D, вибір `scene`, адитивність VX-01…VX-05) | Єдина нумерація W2 |

## Журнал змін документа

| Дата | Версія | Зміна |
|---|---|---|
| 18.10.2026 | 0.1 | Перша редакція (`build/energy/W2_SPEC.md`, хвиля W2) |
| 19.10.2026 | 0.2 | Перенесено до `docs/modules/td_energy_control/`, переклад українською (технічні імена, ID, код, JSON — без змін); міст 3D (M-41, M-42, V-46, V-47, розд. 8.4 з R-26/VX, R-57, R-58, AC-278…AC-293, ТК-28, ТП-11, A-52, A-53, X-93) виокремлено в [../td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md) із збереженням нумерації; рішення й відхилення збірки внесено в тіло документа (нижче) |

### Рішення й відхилення, прийняті при збірці W2

1. **D-45 — архівних таблиць немає** (скасовує R-66/AC-232/A-51 у початковій редакції). Деінсталяція видаляє дані модуля як у будь-якого модуля Odoo; `uninstall_hook` лише видаляє сигнали/джерела `energy_control`, крони, параметри, скидає прапори й публікує збирачу порожню конфігурацію. Відображено: FR-61, розд. 1, R-66, AC-232, A-51, DEPLOY_TEST (розд. 13.5).
2. **D-46 — `td.energy_control.remote_switching_enabled`** (default `False`; demo-дані й стенд — `True`; `neutralize.sql` повертає `False`). Блокуються `qs_close`, `qs_open`, `chp_start`, `bess_discharge`, `genset_test` (поле `remote_gated`, M-31) у `prepare`/`confirm`/`confirm_second`/`undo` (R-39 п.8); прапор іде збирачу в API-24 `flags.remote_switching_enabled`. Додано AC-309, AC-310 (разом AC-159…AC-310 = 152).
3. **D-47 — похідні входи** (змінює заморожений API-24, C-39). Збирач не бачить значень EN-DERIVED, тож API-24 віддає блок `derived` (розд. 7.3 п.8): плагін сам обчислює `energy/totals/p_now`, `energy/sections/S1/p_kw`, `energy/sections/S2/p_kw` (сума `energy/lines/<код>/p_now`), `infra/ats/src1_ok` (`ge`), `infra/totals/grid_kw`, `infra/totals/export_kw` (Q1/Q2, острів → 0), `infra/totals/pv_now`. Операції: `sum` (`terms[].min`, `clamp_min`, `zero_if`), `ge`; терм відсутній/несвіжий → вхід відсутній (fail-closed). Плагін: `derived.py` (розд. 8.1.1).
4. **D-48 — пожежна тривога** (`fire_state = alarm`) не переводить рушій у `hold`: режим лишається `auto`, блокуються лише записи `vent`/`light`, сценарій `night` → `warn`, подія `interlock` (R-44 п.8; AC-244).
5. **D-49 — сценарій `night` не потребує `remote`** (цілі BMS ідуть не через контролер ГРЩ); у R-44 п.3 критичний вхід `remote` лишився лише в `pfc`.
6. **A-64…A-67** — рішення реалізації A (заголовок `X-Config-Version`, `never_shed`/`NEVER_SHED_CODES`, порожній рядок «ДГУ» розкладу, нумерація дій і `idem`); розд. 15.
7. **`verify_timeout_s`** — у відповіді API-17 `prepare` (розд. 7.2) і в параметрах (розд. 5.1, V-44): клієнт обмежує опитування `get_action` значенням `verify_timeout_s + 30`.
8. **Публічні методи `action_confirm_second()`, `action_cancel()`, `action_undo()`** (M-33): безаргументні обгортки над тим самим потоком (права, гейт D-46, блокування, журнал) для кнопок форми V-41 — Odoo 19 валідує методи `type=object`; повертають `display_notification`.
9. **Міст 3D** ([td_energy_viewer3d/SPEC.md](../td_energy_viewer3d/SPEC.md)): ключ `show_markers` (`layer.show_markers`, параметр `td.energy_viewer3d.show_markers`), прапор `colorModes[].hidden` (VX-01), геттер `api.canOpenAction` (VX-05); AC-291 виправлено — `PFC-2` **є** в сцені (код `null` дає вузол без об'єкта в сцені, напр. `BW-4` з `equipment_id.td_code` поза сценою).
10. **Не реалізовано в збірці:** підказка маркера при наведенні (UI-25; `userData.tooltip` готовий, ядро tooltip не показує); слоти «тест ДГУ» в розкладі (R-54 п.7, A-66 — `adapters.schedule_info` віддає текстові вікна); `DEPLOY_TEST.md` модуля (розд. 13.5) окремим файлом не створено.

