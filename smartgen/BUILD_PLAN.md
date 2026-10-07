# BUILD_PLAN — нічна паралельна збірка модуля `td_genset` (Odoo 18.0)

Джерела істини: `smartgen/SPEC.md` (AC-01…AC-69, моделі, інтерфейси), `smartgen/ТР_SmartGen_генератор.md` v1.2 (розділи 2 і АРХІТЕКТУРА — А.1…А.13), `smartgen/relay_api.md`, мокап `smartgen/mockup_odoo_genset.html` + `smartgen/shots/*.png`. Емулятор ретранслятора — `smartgen/tools/fake_relay.py` (API за `relay_api.md` + `POST /_sim`; підтримує `raw=1` і режими версій 1.1.1/1.1.3 — звірити з його шапкою).

Модуль лежить у `smartgen/td_genset/`. Усі документи й тексти UI — українською; код і коментарі — без ідентифікаторів ШІ-моделей. **Рішення 07.10 (вечір):** W2 і W4 робляться вночі в повному обсязі (поетапним є лише вмикання на проді); `catchup_from_date` за замовчуванням −30 днів; зняття тривоги — `_clear` (без перейменувань); оми датчиків і калібрування (ФВ-31, AC-68, AC-69) входять у W1/W4/W3.

## 0. Середовище в цьому контейнері

Готове середовище описане в **`smartgen/tools/odoo/ENV.md`** (скрипти в `smartgen/tools/odoo/`): Odoo 18.0 CE у `/home/user/odoo18`, venv `/home/user/odoo18-venv`, конфіг `/home/user/odoo18.conf` (`addons_path` уже містить `smartgen/`), PostgreSQL 16 (роль `odoo`/`odoo`), шаблонна база `td_template`, Chromium для HttpCase/турів (`ODOO_BROWSER_BIN`, виставляє `env.sh`). Користуйтесь скриптами, а не ручними командами:

| Дія | Команда (`T=/home/user/todo_timur/smartgen/tools/odoo`) |
| --- | --- |
| Підняти Postgres після рестарту контейнера | `$T/pg.sh start` |
| Свіжа база + `-i td_genset` + усі тести `/td_genset` | `$T/run_tests.sh td_<потік>` (клас/тег: `$T/run_tests.sh td_<потік> /td_genset:TestCommands`) |
| Оновити модуль (`-u td_genset`) | `$T/update.sh td_<потік>` |
| Стендові тести з емулятором (`td_genset_stand`) | `$T/run_stand_tests.sh td_<потік>` (сам запускає `fake_relay.py`) |
| Емулятор вручну | `python3 smartgen/tools/fake_relay.py --port 8081 --token <токен> --snapshot-sec 10`; керування — `POST http://127.0.0.1:8081/_sim` (ключі — у шапці `fake_relay.py`) |
| Сервер для скріншотів/ручної перевірки | `$T/serve.sh td_<потік> [порт]` (admin / admin), `$T/serve.sh stop td_<потік>` |
| Прибрати бази | `$T/drop_db.sh --pattern 'td_<потік>_%'` |

Імена баз — `[a-z0-9_-]`, у кожного потоку свій префікс (`td_w1_…`). Git: кожен потік — у власному `git worktree` на гілці `w<N>-<тема>` від `main` після злиття W0; коміти з осмисленими повідомленнями; **не коміть** бази, логи, `.pyc`, конфіги з `/home/user`, скріншоти поза `smartgen/shots/`. Жодних запитів до `gen-relay.todo.ltd` та інших реальних адрес; тільки `RelayMock` (unit) і `fake_relay.py` (стенд).

## 1. Правила для всіх потоків

1. **Odoo 18.0 API**: `<list>` (не `<tree>`), `invisible`/`readonly`/`required` з Python-виразами (без `attrs`/`states`), `<chatter/>`, kanban `<templates><t t-name="card">`, `aggregator` (не `group_operator`), `t-out` (не `t-raw`), `_sql_constraints` як список кортежів, `fields.Json`, `check_access`/`has_access`, `@api.ondelete`, `@tagged`.
2. **Рядки** — лише через `_()`; у кожного поля — `help`; українські тексти з мокапа/ТР дослівно; `string` без двокрапок.
3. **Права**: без `sudo()` без потреби; технічні записи — `sudo()` лише після явної перевірки групи (`self.env.user.has_group('td_genset.group_…')` → інакше `AccessError`).
4. **Без `sleep`**, без довгих циклів у cron (крок — секунди), без звернень до реального ретранслятора, без секретів і без жорстко зашитих адрес/токенів (лише `ir.config_parameter`/змінні оточення тестів).
5. **Імена** — як у SPEC розділ 9 / ТР А.11: не перейменовувати інтерфейсні методи; нові приватні методи — з префіксом `_` у файлі свого потоку.
6. **Нульові конфлікти (рішення 07.10):** W0 заздалегідь створює **все спільне**, і потоки його **не правлять**: `__manifest__.py` перелічує ВСІ xml-файли всіх потоків (W0 кладе порожні заготовки `<odoo/>`), `security/ir.model.access.csv` — повний (34 рядки, ТР А.10), `models/__init__.py`, `wizard/__init__.py`, `tests/__init__.py`, `tests/stand/__init__.py` — імпортують усі файли заздалегідь. Модель `td.genset`: **поля — лише в `models/genset.py` (W0)**, методи — у файлі потоку-власника через `_inherit = 'td.genset'` (`genset_monitoring.py` W1, `genset_scheduler.py` W2, `genset_ui.py` W3, `genset_fuel.py` W4); заглушки compute/кнопок у `genset.py` перекриваються реалізаціями (inherit-файли імпортуються після `genset.py`). Кожен файл має рівно одного власника (таблиці нижче). Потрібне нове поле — додати в кінець `genset.py`, повідомити у звіті. `i18n/uk_UA.po` править лише W5 (наприкінці).
7. **Тести**: ім'я `test_acNN_<що>`; у докстрингу — номер AC; файли `tests/test_w<N>_*.py`; детерміновані дані (`snapshot()`); час — `freezegun.freeze_time`. **Перед звітом кожен потік зобов'язаний прогнати `$T/run_tests.sh td_w<N>` (увесь `/td_genset`, не лише свої файли) з кодом виходу 0 і вказати у звіті кількість виконаних тестів** (рядок `… tests` з логу).
8. **Коміти**: малі, за темою («W1: події run/outage з послідовностей знімків (AC-38, AC-39)»); без ідентифікаторів ШІ-моделей у повідомленнях і файлах.
9. **Звіт** потоку (коротко): що зроблено (файли), AC покриті тестами (зелені/червоні), результат `run_tests.sh` (код виходу, кількість тестів), що не встигли, нові поля в `genset.py` (якщо були), відкриті питання для архітектора.

## 2. W0 «Каркас» — послідовно, першим

**Вхід:** SPEC.md (розділи 5–7, 9, 12, 13, Додаток A), ТР А.2 (структура файлів із власниками), А.10, А.11.

| Що | Файли | Вимоги |
| --- | --- | --- |
| Маніфест, ініти | `__manifest__.py`, `__init__.py`, `models/__init__.py`, `wizard/__init__.py`, `tests/__init__.py`, `tests/stand/__init__.py` | `depends: ['base', 'mail', 'bus', 'web', 'maintenance']`, `application: True`, `version: '18.0.1.0.0'`, `assets: {'web.assets_backend': ['td_genset/static/src/**/*']}`; `data` перелічує **всі** файли security/data/views/wizard-views з А.2 (порожні заготовки для тих, що наповнять потоки); порядок імпорту моделей: `relay_client, genset, genset_monitoring, genset_scheduler, genset_ui, genset_fuel, genset_reading, genset_event, genset_alarm, genset_command, genset_schedule, genset_config, genset_controller_model, maintenance_ext, res_config_settings, ir_websocket` (inherit-файли `td.genset` після `genset.py`) |
| Усі моделі з **усіма** полями SPEC (5.1–5.15 + Додаток A, включно з `td.genset.fuel.calibration`, омами датчиків, `fuel_source`, `raw_regs_mode`) | `models/*.py` за А.2 (усі 17 файлів існують, навіть якщо inherit-файл містить лише заглушки), `wizard/*.py` | типи/required/default/selection/constrains/`_sql_constraints` — як у SPEC; `READING_FIELD_MAP` повний; `init()` з індексами А.4; compute-поля — з коректними `@api.depends`, нейтральні значення |
| Заглушки методів SPEC §9 (= ТР А.11) у файлах власників | `genset_monitoring.py`, `genset_scheduler.py`, `genset_ui.py`, `genset_fuel.py`, `genset_reading.py`, `genset_event.py`, `genset_alarm.py`, `genset_command.py`, `genset_config.py`, `maintenance_ext.py`, `relay_client.py`, `ir_websocket.py`, `wizard/*.py` | повна сигнатура + докстринг з контрактом і `# TODO: W<N>` + номери AC; **викликувані**: повертають нейтральний результат (`None`, `False`, `0`, порожній recordset/dict), не кидають `NotImplementedError`; cron-методи — порожні, але успішні; `_notify_bus` і `_bus_send` — робочі вже у W0 |
| Security | `security/groups.xml` (категорія, 3 групи з `implied_ids`), `security/ir.model.access.csv` (34 рядки з ТР А.10) | установка без попереджень «no access rules»; потоки файл не змінюють |
| Data | `data/ir_cron.xml` (4 задачі), `data/ir_sequence.xml` (3), `data/mail_data.xml` (3 підтипи, 2 типи активності), `data/maintenance_data.xml` (категорія, команда, `noupdate`), `data/controller_model_data.xml` (2, `noupdate`), `data/config_data.xml` (singleton + `level_1/2/3`, `noupdate`), `data/ir_exports.xml` («Генератори: усі значення» з усіма полями Додатка A + оми + `fuel_source`) | усі xml id — як у SPEC §6 |
| Меню і базові подання для кожної моделі | `views/menu.xml` (кореневе меню, усі підменю/дії), `views/*_views.xml` (мінімальні form/list/search для всіх моделей), `wizard/*_views.xml` (форми майстрів з кнопками), `views/res_config_settings_views.xml`, `views/analytics_actions.xml` (заготовка) | кожен пункт меню відкривається без помилок; детальні подання за мокапом робить W3 (він переписує `views/*.xml` повністю) |
| Пульт-плейсхолдер | `static/src/pult/pult_widget.js/.xml/.scss` — віджет `td_genset_pult` з текстом «Пульт: у розробці» + підписка на bus (каркас А.9) | assets збираються без помилок |
| Тестовий каркас | `tests/common.py` (`TdGensetCase`, `RelayMock` з режимами 1.1.1/1.1.3 і `raw=1`, `snapshot()`, `push_reading`, `set_status`, `run_pull/run_commands/run_scheduler`), `tests/test_w0_smoke.py` | `RelayMock` емулює `/status`, `/readings` (+`raw`), `/latest`, `POST /commands`, `/commands/<id>`, помилки (`fail_with=409/403/401/500/timeout`, `controller_executes=False`, `relay_restart()`) |
| i18n, README | `i18n/uk_UA.po` — скелет (`--i18n-export`); `README.md` модуля — 10 рядків | W5 доповнить |

**Definition of Done W0:** `$T/run_tests.sh td_w0` → код 0 (установка на 18 CE без помилок і без попереджень ACL/assets, `test_w0_smoke` зелений); `$T/update.sh td_w0` повторно — без помилок; усі пункти меню відкриваються; усі методи SPEC §9 існують із тими самими сигнатурами у файлах власників; злито в `main`; тег `w0-done`.

## 3. Паралельні потоки після W0

Кожен потік: `git worktree add ../td_genset-w<N> -b w<N>-<тема> main`; володіє **тільки** своїми файлами; спільні файли (п. 1.6) не править.

### W1 «Моніторинг» (етап 1 сервер)

| | |
| --- | --- |
| Входи | SPEC §4, §5.1–5.4, §5.8–5.9, §5.15, §8, §9, §12, Додаток A; ТР 2.6.1–2.6.2, 2.8, 2.12, А.7, А.8, А.13; `relay_api.md` (у т. ч. `raw=1`) |
| Володіє | `models/relay_client.py`, `models/genset_monitoring.py`, `models/genset_reading.py`, `models/genset_event.py`, `models/genset_alarm.py`, `models/genset_config.py`; тести `tests/test_w1_relay_client.py`, `test_w1_pull_readings.py`, `test_w1_semantics.py`, `test_w1_journal_slots.py`, `test_w1_link_health.py`, `test_w1_events.py`, `test_w1_alarms_escalation.py`, `test_w1_cleanup.py` |
| Реалізує | клієнт + винятки (`readings(..., raw=False)`); `_cron_pull_readings`, `_apply_status`, `_pull_readings_page`, `_find_cursor_for_date`, `_need_raw`, `_apply_reading`, `_update_link_state`, `_check_relay_health`, `_finish_catchup`, `action_check_relay`, `action_refresh`; `READING_FIELD_MAP`, `_create_from_payload`, `_derive` (виклик `_liters_from_ohm` з W4 — до його появи заглушка повертає `None` → літри за %), `_extract_sensor_ohms` (ключі або `regs["22"|"18"|"20"]/10`, решта відкидається — AC-68), `_mark_journal`, `_cron_cleanup`; `_process_readings`, `_open`, `_close`, `_detect_external_control`; `_raise`, `_clear`, `_can_ack`, `action_ack`, `_cron_escalate`, `_evaluate_current`; `config.get/_quiet_now/_quiet_end/action_send_test_notification`; активність «Долити паливо» (AC-63) |
| Споживає | поля/стани команд W2 (лише читання полів), `td.genset.refuel._reconcile_pending` і `_check_maintenance` (заглушки W0 до появи W4), `_notify_bus` (W0), `_liters_from_ohm` (W4) |
| Особливості | догон без лавини тривог (`catchup_mode`, `_notify_progress`); «тех.» тривоги — `group_tech`; сторінка = транзакція; жодних винятків назовні cron; маскування токена (AC-57); `raw=1` лише коли треба (`raw_regs_mode`) |
| DoD | AC-01…AC-11, AC-38…AC-46, AC-57, AC-58, AC-63, AC-68 зелені; `$T/run_tests.sh td_w1` → код 0, кількість тестів у звіті |

### W2 «Керування» (етап 2 сервер, повний обсяг)

| | |
| --- | --- |
| Входи | SPEC §5.5–5.7, §5.14 (command/timer wizard), §8, §9; ТР 2.6.3, 2.7, 2.3.13, А.5, А.6, А.7 |
| Володіє | `models/genset_command.py`, `models/genset_schedule.py`, `models/genset_scheduler.py`, `wizard/command_wizard.py`, `wizard/timer_wizard.py`, `wizard/command_wizard_views.xml`, `wizard/timer_wizard_views.xml`; тести `tests/test_w2_commands.py`, `test_w2_scheduler.py`, `test_w2_timer_test.py` |
| Реалізує | `_enqueue`, `_enqueue_batch`, `_cron_process_commands`, `_step`, `_precheck`, `_check_confirmation`, `_cancel_pending`, `_count_inflight`; стан-машина А.5 повністю (транспортні повтори, повтори підтвердження, `waiting_link`, `done_late`, 403/401/400, `crank_failure`, автомати-перемикачі зі свіжим знімком ≤ 2 хв, батч «Ручний + Стоп», ліміт 2, `cancelled`); `_cron_scheduler`, `_in_window`, `_window_bounds`, `_next_transition`, `_follow_schedule`, `_timer_start/_timer_extend/_timer_stop`, `_test_start/_test_finish`, `kyiv_localize`, `_compute_next_event_text`, `action_open_command_wizard`, `action_open_timer_wizard`, `action_timer_*`; планувальник А.6 (переходи, винятки, пропущені переходи з `late_transition_at`, політика `until_next`/`window_only`, таймер, тест, DST) |
| Споживає | `relay.client.post_command/command/latest` (W1; до злиття — `RelayMock`), `_raise/_clear` (W1; заглушки → перевірка через `patch.object`), `_notify_bus` (W0), поля стану генератора |
| Особливості | `FOR NO KEY UPDATE SKIP LOCKED` у кроці cron; `_trigger()` після `_enqueue`; `first_sent_at` — перша спроба; `deadline_at` подовжується на час без зв'язку; тексти `result_note` — дослівно (2.4.4, 2.8.4); «лише на переходах» і `external_control` після переходу |
| DoD | AC-12…AC-37, AC-66, AC-67 зелені; `$T/run_tests.sh td_w2` → код 0, кількість тестів у звіті |

### W3 «UI» (усі етапи)

| | |
| --- | --- |
| Входи | SPEC §10, §11, §5, §7; ТР 2.10, 2.11, А.9; мокап (`FIELD`/`COLS` в останньому `<script>`), `shots/*.png` (світла/темна, 1440/390) |
| Володіє | усі `views/*.xml` (переписує повністю, крім `menu.xml`, де додає лише рядки в кінець), `wizard/refuel_wizard_views.xml` і `wizard/fuel_receipt_wizard_views.xml` — **ні** (W4), `static/src/**` (OWL-віджет, SCSS), `models/genset_ui.py` (`get_pult_state`, `_compute_current_data_html`, `_compute_timer_progress`, `_compute_is_tech/_compute_is_admin`), `models/res_config_settings.py`, `models/ir_websocket.py`; тести `tests/test_w3_ui_http.py`, `tests/test_w3_security.py` |
| Реалізує | форма генератора за мокапом (statusbar, button box, групи, блок «Робота поза графіком», вкладки Розклад/Поточні дані (з омами датчиків поруч із %/°C/kPa і літрами з `fuel_source`)/Тривоги/Обслуговування/Журнал команд/Паливо (KPI, кнопки майстрів, таблиця калібрування `fuel_calibration_ids` з підказкою і кнопкою «Перерахувати літри», лише `group_tech`)/Аналітика, `<chatter/>`), «Показання» (list/graph/pivot/search), дії «Аналітика», «Події» (list/calendar/graph), «Заправка» (kanban `card`/list/form), сторінка `td.genset.config` (секції, `raw_regs_mode` у «Зв'язок», `readonly="not is_tech"`, банер), `res.config.settings` (`groups="base.group_system"`, `password`, «токен встановлено»), OWL-віджет `td_genset_pult` з bus-підпискою і резервним опитуванням, `_build_bus_channel_list`, `get_pult_state`, адаптив 390 px, `ir.exports` (перевірити колонки омів/`fuel_source`), порожні стани; матриця прав через RPC (AC-56) |
| Споживає | усі поля (W0), `action_open_command_wizard`/`action_timer_*` (W2), `action_recompute_liters` (W4), події `_notify_bus` (W1/W2) |
| DoD | AC-24 (видимість), AC-55, AC-56, AC-59, AC-60, AC-61, AC-62 — HttpCase/tour + ручна перевірка; скріншоти форми/показань/подій/заправки/налаштувань на 1440 і 390 (світла і темна) у `smartgen/shots/odoo_*.png`; жодного `attrs`/`<tree>`; assets без помилок у консолі; `$T/run_tests.sh td_w3` → код 0, кількість тестів у звіті |

### W4 «Паливо і ТО» (етап 3, повний обсяг)

| | |
| --- | --- |
| Входи | SPEC §5.12–5.14 (calibration, refuel/receipt wizard), §9; ТР 2.3.11, 2.3.12, 2.9, А.11; ФВ-31 (оми, калібрування) |
| Володіє | `models/genset_fuel.py` (моделі палива + inherit `td.genset`), `models/maintenance_ext.py`, `wizard/refuel_wizard.py`, `wizard/fuel_receipt_wizard.py`, `wizard/refuel_wizard_views.xml`, `wizard/fuel_receipt_wizard_views.xml`, `views/maintenance_views.xml`; тести `tests/test_w4_fuel.py`, `tests/test_w4_maintenance.py` |
| Реалізує | `fuel.move._post`, каністри (`write()` → рухи `fix`/`loc`, `action_write_off`), місця (`@api.ondelete`), майстри заправки/надходження з валідаціями і підказками, `refuel._reconcile_pending` (±2 год; допуск 2 % бака або 1 L при калібруванні; `unconfirmed` + тривога), KPI 7/30 і витрата, мінімальний запас; **калібрування:** `td.genset.fuel.calibration` (constrains: монотонність, unique, ≥ 2 точок), `_compute_fuel_calibrated`, `_liters_from_ohm` (лінійна інтерполяція, крайні точки, 0,1 L), `action_recompute_liters` (перерахунок `fuel_liters`/`fuel_source` партіями по 10 000 через `_trigger()`/`_notify_progress`) — AC-69; ТО: `_ensure_equipment`, `_compute_maint`, `_check_maintenance`, `maintenance.request.write` → `_td_on_done`, поле `td_partner_id` |
| Споживає | події `refuel`/`run` (W1; у тестах створювати напряму), `_raise/_clear` (W1), `run_hours_total`, `fuel_sensor_ohm` у знімках (W1 `_extract_sensor_ohms`; у тестах — `snapshot(fuel_sensor_ohm=…)`) |
| DoD | AC-47…AC-54, AC-69 зелені; `maintenance_data.xml` створюється в компанії встановлення; `$T/run_tests.sh td_w4` → код 0, кількість тестів у звіті |

### W5 «Стенд і документація»

| | |
| --- | --- |
| Входи | ТР «Інструкція» (ТК-01…ТК-14), А.13; `relay_api.md` §10; `fake_relay.py` (API + `POST /_sim`, режими 1.1.1/1.1.3), SPEC §15 |
| Володіє | `tests/stand/test_w5_stand_*.py` (`@tagged('post_install', '-at_install', '-standard', 'td_genset_stand')`; `skipTest` без `TD_GENSET_STAND_URL`), `i18n/uk_UA.po` (повний переклад — останнім перед інтеграцією), `td_genset/README.md` (установка на тест, параметри, стенд, тести, стоп-крани, калібрування датчика, перший догон), оновлення `smartgen/README.md` (статус ТР «Погодження клієнта», посилання на SPEC/BUILD_PLAN/модуль), `smartgen/tools/run_stand.sh` (якщо потрібен понад `run_stand_tests.sh`) |
| Реалізує | стендові сценарії ТК-01…ТК-14 у скороченому часі (`--snapshot-sec 10`, повтори 1/3 хв): 201→done→підтвердження, 409, 403, 401, перезапуск, відновлення курсору, «контролер не виконує», `crank_failure`, `remote_lock`, заправка/злив, низький рівень, зв'язок, оми з `raw=1` при 1.1.1 і з ключів при 1.1.3 (AC-68), калібрування (AC-69) — через `POST /_sim` |
| Споживає | усе; стендові тести можуть бути червоними до злиття W1–W4 — у звіті позначити |
| DoD | стендові тести зелені після інтеграції (AC-65); `uk_UA.po` без `fuzzy` і без порожніх `msgstr` для видимих рядків; README-и актуальні; `$T/run_tests.sh td_w5` і `$T/run_stand_tests.sh td_w5` → код 0, кількість тестів у звіті |

## 4. Інтеграція (після завершення W1–W5)

1. **Порядок злиття в `main`:** W1 → W2 → W4 → W3 → W5. Завдяки п. 1.6 конфлікти очікуються лише в `views/menu.xml` (додані рядки) — зливати обидві сторони.
2. **Після кожного злиття:** `$T/run_tests.sh td_int` (чиста база, `-i`), `$T/update.sh td_int` (`-u`), відсутність попереджень ACL/assets у логах.
3. **Після повного злиття:** `$T/run_stand_tests.sh td_int` (емулятор, тег `td_genset_stand`); установка з нуля на 18 CE і `-u`; security-review (ACL 34 рядки, `sudo()`, SQL у `init()`/cron/перерахунку літрів, відсутність контролерів, маскування токена — `grep -r` по репозиторію на токени/адреси); ревʼю коду проти SPEC/AC (кожен AC → тест, кожен метод А.11 — реалізований у файлі власника, імена не змінені; `grep -rn "attrs=\|<tree\|t-raw\|group_operator\|time.sleep"` — порожньо); скріншоти UI 1440/390 (світла/темна) → `smartgen/shots/odoo_*.png`; ручний прогін ТК-01…ТК-14 з емулятором.
4. **Звіт інтеграції:** таблиця AC → тест → статус (69 AC); підсумок `run_tests.sh` (код виходу, кількість тестів); відхилення від SPEC (з обґрунтуванням); відкриті питання; що лишилось на ранок.

## 5. Що робити, якщо щось не збігається

- Суперечність між SPEC і ТР — пріоритет ТР (1.5/2/АРХІТЕКТУРА); виправлення в SPEC — окремим комітом «SPEC fix».
- Потрібен новий інтерфейсний метод між блоками — додати як `_`-метод у файлі свого потоку, задокументувати у звіті; сигнатури наявних не змінювати. Потрібне нове поле `td.genset` — у кінець `genset.py` + звіт.
- Емулятор не покриває сценарій — стендовий тест пишеться за `relay_api.md`, помічається `skipTest` з причиною; у звіті — запит до автора емулятора.
- Odoo-поведінка неясна — дивитись вихідний код `/home/user/odoo18` (гілка 18.0), а не памʼять.
