# DEPLOY_TEST — factory3d_yard 19.0.1.0.0 (SPEC §13.5)

Чек-лист розгортання. Виконано 15.10.2026 воркером W5 на локальному стенді без docker і без копії демо-бази. Протокол
стендових сценаріїв ТК-01…ТК-08 **не виконано** (причини нижче) — AC-75, AC-81…AC-86 лишаються відкритими до прогону на стенді.

## Обмеження прогону

* **Копії демо-бази `odoo` немає** (`psql -l` не показує її). Установку перевірено на чистій базі `f3d_template` →
  `f3d_factory3d_yard` (`-i factory3d_base,factory3d_telemetry,factory3d_yard`). На ній немає пакетів `TRUCK-*`, обладнання
  `GATE-W/GATE-E/TRUCK-SCALE/CCTV`, товарів `DSP16-*`/`MDF18-RAW`: очікування «копії демо» (§5.4: `visits 6`, `bookings 6`,
  `weighings 1`, `products_weighted 7`, `carriers_linked 2`, `linked_equipment 3`) **не перевірені**; кроки 3–7 хука на ній
  `skipped`/нулі. Міграцію покрито синтетичними тестами (AC-76, AC-77): пакети `TRUCK-T-1/2`, товари з кодами, перевізник.
* **docker недоступний** (`/var/run/docker.sock` немає). Стенд ТК (емулятор `iot_sim` + колектор з плагіном `sics` + Odoo
  HTTP + токен маршруту `lpr`) вимагає оркестрації, якої в середовищі немає (скрипту стенда для двору немає, на відміну від
  `factory3d_access/tests/stand`); сценарії `truck_arrival`/`truck_no_booking` емулятора не запускались.
  Зроблено замість цього: unit-тести Odoo (емулюють показання й події LPR), `pytest` плагіна з фейковим SICS-сервером.

## Кроки

| № | Крок (SPEC §13.5) | Виконано | Результат |
|---|---|---|---|
| 1 | Дамп і копія бази | **не виконано** | Немає тестового сервера; використано `createdb -T f3d_template` через `run_tests.sh` |
| 2 | Установка `-i factory3d_yard` | **виконано** (чиста база) | Журнал без `ERROR`/`Traceback` (0 збігів); хук: `params {read_enabled 1, calendar 1}`, `gates_and_scale {gates 2, scales 1, linked_equipment 0, cameras 0, zones 3}` (WARNING на відсутні обладнання), `signals_and_sources {sources_created 2, http_push_reused 1, signals_created 18, linked 16}`, кроки 3–7 нулі/`skipped` |
| 3 | `migration_state = done`; звіт = §5.4; 6 рейсів | **не виконано** | На чистій базі `migration_state='skipped'` (немає пакетів `TRUCK-*`); синтетично — `done`, 2 рейси `handling`, 2 бронювання `migration` |
| 4 | `read_enabled` за `environment` | **виконано** (тест `test_params_step`) | `test` → `True`, `prod` → `False`; після `done` крок 0 пропускається |
| 5 | Юніт-тести `--test-tags /factory3d_yard` | **виконано** | 152 тести, 0 failed, 0 error (`F3D_TEST_INSTALL=factory3d_base,factory3d_telemetry,factory3d_yard`); плагін: `pytest` 34 passed |
| 6 | ТК-01…ТК-08 на стенді | **ТК: ждут стенда** | Причини вище. AC-81…AC-86 — відкриті |
| 7 | `neutralize.sql` → AC-73 | **виконано** (тест `test_neutralize_sql`, у транзакції) | `write/read_enabled='False'`, 0 активних кронів двору, ворота `manual`, джерела `module='yard'` без читання/запису |
| 8 | Деінсталяція на копії | **не виконано** | Немає копії; код `uninstall_hook` (параметри + вкладення) не чіпає сигнали/джерела — перевірити на стенді |
| 9 | Відкат | **n/a** | Бази стенда видаляються `tools/odoo/drop_db.sh` |

## Що виконати на стенді (ТК)

1. Копія демо-бази + установка base → telemetry → yard: перевірити звіт §5.4 (`visits 6`, `bookings 6`, `conflicts 0`,
   `weighings 1`, `products_weighted 7`, `carriers_linked 2`, `signals_created 18`, `sources_created 2`, `linked_equipment 3`),
   `YV/2026/00001.wait_min = 20.0`; кнопка «Повторити міграцію двору» нічого не дублює (AC-75, AC-76, ТК-07).
2. Умови ТК-01…ТК-08 — SPEC §13.2: колектор `COL-MAIN` з токеном, `SIM_LPR_PUSH_URL=http://collector:8080/f3d/lpr`,
   `SIM_YARD_AUTOGATE=0`, `antipassback=False` для ТК-01/03, `write_enabled` на модулі, telemetry, джерелі й cmd-сигналах.
3. Для кожного ТК записати час, скриншот екрана КПП і результат у таблицю нижче.

| ТК | Дата | Стенд | Результат |
|---|---|---|---|
| ТК-01 `truck_arrival` | — | — | ждёт стенда |
| ТК-02 POST LPR (токен / без токена) | — | — | ждёт стенда |
| ТК-03 `truck_no_booking` | — | — | ждёт стенда |
| ТК-04 команда DO0, `F3D_WRITE_ENABLED=0` | — | — | ждёт стенда |
| ТК-05 SICS `stream`/`poll` | — | — | ждёт стенда (плагін: `pytest` з фейковим сервером — зелений) |
| ТК-06 пристрої офлайн | — | — | ждёт стенда (логіку offline/ручного циклу покрито unit: AC-42, AC-79) |
| ТК-07 міграція | — | — | ждёт копії демо-бази |
| ТК-08 переглядач | — | — | ждёт стенда (unit: AC-62…AC-65) |
