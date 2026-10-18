# DEPLOY_TEST — td_access 19.0.1.0.0 (SPEC §13.5)

Чек-лист розгортання. Виконано 15.10.2026 воркером W5 на локальному стенді без docker і без копії демо-бази (див.
«Обмеження»). Результати ТК/ТБ/ТП — у `TEST_REPORT.md`. Код стенда — `factory3d/odoo_addons/td_access/tests/stand/`
(`pytest -m stand`; у Odoo test-tags не потрапляє: `tests/__init__.py` його не імпортує, у каталозі немає `__init__.py`).

## Обмеження прогону

* **Копії демо-бази `odoo` (timur-o19demo) немає.** ТК-01 виконано на чистій базі (`f3d_template` → `f3d_access_stand`:
  `td_factory3d` + `td_access`). Очікування «копії демо» (`links 35`, `home_zones 35`, `presence_seeded 35`,
  `hr_attendance` 35 рядків демо) **не перевірені**; замість них на чистій базі засіяно 35 працівників зі штрих-кодами сцени
  (`tests/stand/seed.py`: `OPSAW1…4`, `OPEB1…3`, `OPCNC1…5`, `OPFAC1…6`, `OPASM1…6`, `OPPACK1…4`, `OPW1…7`) і 35 відкритих
  демо-відміток 12.10 (`in_mode='manual'`).
* **docker недоступний** (`/var/run/docker.sock` немає). Емулятор `td_iot_sim` (сервіс `factory3d/services/iot_sim`,
  v0.1.0) запущено локально без контейнера: Python 3.13 + `requirements.txt`, `python -m iot_sim run`, режим старту
  `follow_odoo` (щоб підхопити 35 працівників з Odoo), далі `/sim/v1/mode scenario`. Порти: HTTPS 8443 / HTTP 8081 (BioStar),
  REST 8090. `docker compose --profile demo` на стенді не піднімали (його перевірено в iot_sim DEC-18).
* Odoo → емулятор іде через **журналюючий TLS-проксі** `https://127.0.0.1:18443` (`tests/stand/logging_proxy.py`; той самий
  самопідписаний сертифікат емулятора; пересилає на HTTP-порт 8081): емулятор не логує запити, а ТБ-08 потребує лічильника
  записів. Сервер доступу: `environment='test'`, `verify_ssl=False` (правило R-01/AC-01 дозволяє лише в test), пароль
  BioStar = `SIM_BIOSTAR_PASS`, `read_enabled=True`, `write_enabled=False`.
* Дата sim-сценаріїв ТК-03/04 — **учора**, а не «сьогодні»: реальний «зараз» стенда ≈ 13:00, вихід 15:30 «сьогодні» був би
  «майбутньою» подією (`future_tolerance_s`). Для першого опитування `initial_lookback_h=72` (максимум параметра — 168 год).
* Крони модуля на стенді активні, але `_cron_poll`/`_cron_sync_*` падають через дефект D-1 (див. TEST_REPORT), тому опитування
  виконувалось викликом `action_poll_now` («Опитати зараз», XML-RPC), як передбачає §13.2.
* ТК-06: «зупинити емулятор на 5 хв» неможливо без docker — виконано варіанти зі SPEC «невірний пароль» і «недосяжний порт».
* `td_viewer3d`, `td_fire_safety`, `td_telemetry` відсутні: ТК-09 — skip, `drill` у ТК-10 і міст
  `td_access_telemetry` (крок 3) — не перевірені.

## Кроки

| № | Крок (SPEC §13.5) | Виконано | Результат |
|---|---|---|---|
| 1 | Дамп `odoo` → `odoo_f3d_test`; знімки S1 (`hr_attendance`), S2 (`hr_employee`) | **не виконано** | Немає копії демо-бази. Замінник: чиста база, S1 = 0 рядків до установки (`attendances_total: 0`) |
| 2 | `td_factory3d` встановлено, `td.base.environment='test'` | **виконано** | `environment='test'` на `f3d_access_stand` |
| 3 | Установка модуля (ТК-01), звіт хука; S1 після = до; міст telemetry | **частково** | Звіт хука (чиста база): `servers 1, devices 5, doors 5, equipment_bound 0, links 0, home_zones 0, presence_seeded 0, attendances_touched 0, attendances_total 0, migration_state 'skipped'`; без ERROR у лозі установки. Міст telemetry — не перевірено (модуля немає) |
| 4 | Емулятор, пароль BioStar, ТК-02…ТК-08; ТК-09; ТК-10 | **виконано** (ТК-09 — skip) | `tests/stand/test_tk.py`, числа — нижче |
| 5 | Юніт-тести: на копії / на чистій базі | **частково** | Чиста база: `F3D_TEST_INSTALL=td_access run_tests.sh f3d_factory3d_access_w5 /td_access` → **0 failed, 154 tests**; на копії демо — не виконано |
| 6 | `odoo-bin neutralize -d` | **виконано** (на копії стенда `createdb -T`) | 0 активних кронів `td_access`, `read_enabled=False`, `write_enabled=False`, `biostar_password` видалено, `session_id` стерто; плюс ТБ-03 (`psql` у транзакції з ROLLBACK) |
| 7 | Деінсталяція → S1; повторна установка → ТК-01 | **виконано** (`tests/stand/lifecycle_shell.py`) | До: 70 відміток (35 `in_mode='biostar'`, 35 `out_mode='biostar'`), 27 параметрів `td.access.%`. Після: 70 відміток, `biostar` у режимах 0 (→ `manual`), параметрів 0, модуль `uninstalled`. Повторна установка на базі з даними: звіт `links 35, home_zones 7 (з CSV), home_zone_missing 30, attendances_touched 0, attendances_total 70, migration_state 'partial'`. Примітка: під час деінсталяції в лозі ERROR «violates foreign key td_access_card_server_id_fkey» (картки `ondelete='restrict'`), модуль усе одно видалено — див. TEST_REPORT O-1 |
| 8 | Відкат: видалити тестову базу | **виконано** | `drop_db.sh f3d_access_stand f3d_access_neut f3d_factory3d_access_w5`; демо-база не чіпалась (її немає) |
| 9 | Кількості й час опитування → CHANGELOG, `TEST_REPORT.md` | **частково** | `TEST_REPORT.md` — так; запис у CHANGELOG «Міграція демо» (файл не мій) — лишається менеджеру: зазначити, що числа демо-копії не отримані |

## Фактичні кількості стенда (ТК, прогін 15.10.2026, чиста база + 35 засіяних працівників)

| ТК | Кількості |
|---|---|
| ТК-01 | сервер 1, пристроїв 5, дверей 5; `attendances_touched 0`; `biostar`-відміток 0 |
| ТК-02 | `online`; користувачів 36; пристроїв 5 (усі `online`, «BioEntry W3»); дверей 5 (`open_duration_s=5`); зв'язків 36 = 35 `barcode` + `"1"` «Не зв'язано» |
| ТК-03 | 140 подій (35 проходів TURN-1 `in` на ACR-IN + 105 подій дверей); 35 відміток `in_mode='biostar'`, `check_in` 06:40–06:59 (Київ); 35 демо-відміток 12.10 закрито R-07 (`td_closed_by_rule`); «Люди по зонах» — 35 карток; помилок обробки 0; дублів немає |
| ТК-04 | 35 виходів; 35 відміток закрито `out_mode='biostar'`, `check_out` 15:30–15:49; людей по зонах 0; `TURN-1` `closed` |
| ТК-05 | OP-W1: `Z-ELEC` → (dwell-крон) `Z-HW`; відмітка не змінилась; подій 6400 OP-W2: 1 (`denied`, `DOOR-ELEC`); `DOOR-ELEC` 20480 → 20992 → 21248, стан `closed` |
| ТК-06 | `error_count` 2 при невірному паролі, `next_try_at` виставлено, пароль не потрапив у `last_error`; після відновлення `online`, `error_count 0`; подій в Odoo 311 = у BioStar 311; недосяжний порт → `error` → відновлено |
| ТК-07 | `on_site` → порушення зон (1) → `left`; відміток відвідувача 0; бейдж «Відвідувач» у «Люди по зонах» 1 |
| ТК-08 | `write_enabled=False` → `local`, підказка про стоп-кран у чаттері, «Позначити синхронізованим» → `synced`; `write_enabled=True` → `blocked`, `sync_state='error'`: картка — `PUT /api/users/…` → **404** (див. D-2), користувач відвідувача — `POST /api/users` → **405** «Метод не підтримується сервером BioStar (405)» |
| ТК-09 | skip (немає `td_viewer3d`) |
| ТК-10 | усі 5 дверей `unlocked`, `alarm=True`, `alarm_reason='fire'`, подія 26368 є; «Зняти тривогу» → тривог 0 |

## Відтворення

```bash
# змінні (значення — лише в середовищі, не в репозиторії)
export SIM_API_TOKEN=<>=32 символи> SIM_BIOSTAR_PASS=<пароль> SIM_VENV=<venv з services/iot_sim/requirements.txt> STAND_TMP=<каталог поза репо>
factory3d/odoo_addons/td_access/tests/stand/reset_stand.sh up     # нова база + serve.sh :18079 + емулятор + проксі :18443
export F3D_ODOO_URL=http://127.0.0.1:18079 F3D_ODOO_DB=f3d_access_stand F3D_ODOO_USER=admin F3D_ODOO_PASSWORD=admin \
       SIM_API_URL=http://127.0.0.1:8090 F3D_SIM_BIOSTAR_URL=https://127.0.0.1:18443 F3D_PROXY_LOG=$STAND_TMP/biostar-proxy.log \
       F3D_ODOO_PID_FILE=$ODOO_RUN_DIR/f3d_access_stand.pid F3D_ENV_SH=factory3d/tools/odoo/env.sh PGHOST=127.0.0.1 PGUSER=odoo
cd factory3d/odoo_addons/td_access/tests/stand
python -m pytest -m stand -q -s test_tk.py test_tb.py test_tp.py            # ≈ 11 хв; порядок файлів важливий
./reset_stand.sh down; factory3d/tools/odoo/drop_db.sh f3d_access_stand
```

Змінні стенда: `F3D_ODOO_URL/DB/USER/PASSWORD`, `SIM_API_URL`, `SIM_API_TOKEN`, `SIM_BIOSTAR_PASS` (обов'язкові); `F3D_SIM_BIOSTAR_URL`
(адреса BioStar для Odoo, за замовчуванням `https://127.0.0.1:8443`), `F3D_PROXY_LOG` (ТБ-08), `F3D_ODOO_PID_FILE` (CPU, ТП-02),
`F3D_ENV_SH` (odoo shell для ТП-03/04), `F3D_ODOO_LOG` (перевірка паролів у лозі, ТБ-02), `F3D_STAND_DAY` (день ТК-03/04).
Без `F3D_ODOO_URL` усі стендові тести пропускаються (skip).
