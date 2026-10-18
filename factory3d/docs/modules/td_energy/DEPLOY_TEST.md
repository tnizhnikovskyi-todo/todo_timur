# DEPLOY_TEST — td_energy 19.0.1.0.0 (SPEC §13.5)

Чек-лист розгортання. Виконано 15.10.2026 воркером W6 на локальному стенді без docker і без копії демо-бази (див.
«Обмеження»). Результати ТК/ТБ/ТП — у `TEST_REPORT.md`. Код стенда — `factory3d/odoo_addons/td_energy/tests/stand/`
(`pytest -m stand`; у Odoo test-tags не потрапляє: `tests/__init__.py` його не імпортує, у каталозі немає `__init__.py`).

## Обмеження прогону

* **Копії демо-бази `odoo` (timur-o19demo) немає.** Установка виконана на чистій базі (`f3d_template` → `f3d_energy_stand`:
  `td_energy` і залежності `td_factory3d`, `td_viewer3d`-незалежно: `td_telemetry`, `mrp_account`, `analytic`,
  `web_hierarchy`). Тому звіт хука `partial` (`equipment_linked 0`, `unmatched_equipment 80`, `workcenter_linked 0`,
  `direct_without_wc 35`): обладнання й робочих центрів демо в базі немає. Очікування AC-13 (`equipment_linked 80`,
  `workcenter_linked 35`, `signals.created 210 / updated 87`) і сценарії, що потребують МО 00231 / BOM лінії A / АВСО-категорії
  (ТК-03, ТК-04, AC-53), — **не виконані** (тести написані й позначені `skip` без `F3D_STAND_DEMO=1`).
* **docker недоступний** (`/var/run/docker.sock` немає). Емулятор `td_iot_sim` (v0.1.0) і колектор telemetry запущено
  локально без контейнерів (Python 3.13, venv `/tmp/simvenv`); `mosquitto`/`genset_relay` не піднімались (MQTT вимкнено).
  Адреса джерел енергетики `host=iot-sim port=502`: у `/etc/hosts` додано `127.0.0.1 iot-sim`; Modbus емулятора слухає :502.
* Колектор `COL-MAIN`: токен видано прямим записом SHA-256 у `td_collector.token_hash` (скрипт `reset_stand.sh`), далі
  стандартний цикл API-01…05. Плагіни колектора знаходяться лише після `pip install -e services/collector --no-deps`.
* Розрив із чек-листом: `td_viewer3d`, `td_genset`/`td_genset_factory3d`, `mrp_workorder` (Enterprise) відсутні → ТК-06 (td_genset),
  ТК-12 (viewer, MAN), `denied` у ТБ-06 і «міст `island=true`» (CE-05) не виконуються; ТК-05/ТК-07/ТК-08 перевіряють CE-03
  через виклик `tools/payload.build_infra` в `odoo shell` (`tests/stand/payload_shell.py`) — він не залежить від viewer.
* Дані для ТП генеруються SQL (`generate_series`); ТП виконано на окремій базі `f3d_energy_stand2` (Odoo :18081) без колектора.
* Крок 3 «Етап 1 / Етап 2» (по 2 години реального часу на копії демо з увімкненням/вимкненням джерел) **не виконано**;
  замість нього ТК-02 (20 хв) на чистій базі зі всіма 68 джерелами.

## Кроки

| № | Крок (SPEC §13.5) | Виконано | Результат |
|---|---|---|---|
| 1 | Дамп `odoo` → `odoo_energy_test`; `level0_migrated.state='done'` | **не виконано** | Немає копії демо. Замінник: чиста база `f3d_energy_stand` (`f3d_template` + `td_energy`) |
| 2 | Установка (ТК-01), звіт хука, лог без ERROR | **виконано** (чиста база) | Звіт хука див. «Фактичні кількості»; у `update-*.log` установки ERROR немає (0). Під час роботи колектора один ERROR «could not serialize access due to concurrent update» (див. TEST_REPORT, O-3) |
| 3 | Етап 1 «один ввід і три фідери» (2 год), баланс Q1 і фідерів `ok` (AC-92) | **не виконано** | 2 год реального часу + копія демо; баланс Q1 перевіряється AC-92 лише на копії |
| 4 | Етап 2 «весь ГРЩ» (2 год), ТК-02 | **частково** | ТК-02 (20 хв, 68 джерел увімкнено) — результат у TEST_REPORT |
| 5 | ТК-03…ТК-12; UT на копії `--test-tags /td_energy` | **частково** | Стенд: див. TEST_REPORT. UT на чистій базі: `F3D_TEST_INSTALL=td_energy run_tests.sh f3d_factory3d_energy_w6 /td_energy` → **0 failed, 109 tests** (147 у статистиці `odoo.tests.stats`); на копії демо — не виконано |
| 6 | Відкат: деінсталяція → сигнали без джерел, 87 мігрованих активні; повторна установка → ТК-01 | **виконано на чистій базі** (`tests/stand/lifecycle_shell.py`) | Було: 299 сигналів `energy/*`+`infra/*`, 20 параметрів `td.energy.%`, 72 джерела `MB-U*` (68 енергетики + 4 telemetry); після деінсталяції: 2 сигнали (власні сигнали telemetry), 0 параметрів, 4 джерела (telemetry), модуль `uninstalled`; повторна установка (`update.sh`) → `installed`, ТК-01 зелений. «87 мігрованих активні» — не перевірено (на чистій базі мігрованих немає) |
| 7 | Видалити копію; робоча база `odoo` не змінювалась | **виконано** | `drop_db.sh f3d_energy_stand f3d_energy_stand2 f3d_factory3d_energy_w6`; демо-бази немає. Фактичні кількості — у CHANGELOG (лишається менеджеру: файл не мій) |

## Фактичні кількості стенда (чиста база)

| Що | Значення |
|---|---|
| Звіт хука (15.10 13:06) | `state=partial`, `nodes 123`, `critical 10`, `pools 5`, `meters 67`, `sources 68`, `signals.created 297`, `signals.updated 0`, `derived_source.created 1`, `equipment_linked 0`, `unmatched_equipment 80`, `workcenter_linked 0`, `direct_without_wc 35`, `wc_missing 4` |
| ТК-01 | 68 джерел енергетики (без `EN-DERIVED`), 220 сигналів з адресою; API-01 `GET /f3d/telemetry/config` COL-MAIN: 68 джерел / 220 сигналів, `EN-DERIVED` відсутнє, `ETag` є |
| Колектор | реальний обмін Modbus TCP з емулятором (`iot-sim:502`): `last_ts` сигналів оновлюється з періодом, колектор `online` |

## Відтворення

```bash
# змінні (значення — лише в середовищі, не в репозиторії)
export SIM_API_TOKEN=<>=32 символи> F3D_COLLECTOR_TOKEN=<>=32 символи> SIM_VENV=<venv> STAND_TMP=<каталог поза репо>
# venv: pip install -r services/iot_sim/requirements.txt -r services/collector/requirements.txt; pip install -e services/collector --no-deps
factory3d/odoo_addons/td_energy/tests/stand/reset_stand.sh up    # база + Odoo :18079 + емулятор :8090/:502 + колектор
export F3D_ODOO_URL=http://127.0.0.1:18079 F3D_ODOO_DB=f3d_energy_stand F3D_ODOO_USER=admin F3D_ODOO_PASSWORD=admin \
       SIM_API_URL=http://127.0.0.1:8090 F3D_STAND_COLLECTOR=1 PGHOST=127.0.0.1 PGUSER=odoo \
       F3D_ENV_SH=factory3d/tools/odoo/env.sh
cd factory3d/odoo_addons/td_energy/tests/stand
python -m pytest -m stand -q -s test_tk.py                  # ≈ 70 хв (ТК-02 20 хв, ТК-05 ≈ 12 хв, ТК-07 12 хв, ТК-09 до 20 хв)
# ТБ і ТП — на окремій базі без колектора (f3d_template + td_energy, serve.sh <db> 18081):
F3D_ODOO_URL=http://127.0.0.1:18081 F3D_ODOO_DB=f3d_energy_stand2 python -m pytest -m stand -q -s test_tb.py test_tp.py
./reset_stand.sh down; factory3d/tools/odoo/drop_db.sh f3d_energy_stand f3d_energy_stand2
```

Змінні стенда: `F3D_ODOO_URL/DB/USER/PASSWORD`, `SIM_API_URL`, `SIM_API_TOKEN`, `F3D_COLLECTOR_TOKEN` (для API-01 у ТК-01),
`F3D_ENV_SH` (odoo shell для payload/ТП), `PGHOST/PGUSER` (ТБ-05, `psql`). Прапорці: `F3D_STAND_COLLECTOR=1` (колектор працює),
`F3D_STAND_DEMO=1` (копія демо), `F3D_STAND_LONG=1` (ТК-10, 90 хв), `F3D_STAND_TD_GENSET=1`, `F3D_STAND_VIEWER=1`;
тривалість: `F3D_STAND_WAIT_MIN` (ТК-02, 20), `F3D_STAND_BLACKOUT_S` (ТК-05, 600), `F3D_STAND_WO_MIN` (ТК-03, 30).
Без `F3D_ODOO_URL` усі стендові тести пропускаються (skip).
