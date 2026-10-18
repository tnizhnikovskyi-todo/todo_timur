# DEPLOY_TEST factory3d_machine_connect (чек-лист SPEC §13.5)

Здає W9. Протокол прогону стенда — `TEST_REPORT.md` (ТК/ТБ/ТП, AC-93…AC-100); тут — кроки розгортання «по одному верстату,
перший тиждень лише читання», команди й що з них виконано на стенді розробки. Дата прогону стенда: **2026-10-15**.

## Середовище стенда (процесний режим, без Docker)

Docker-стенд SPEC §13.2 (`docker-compose.sim.yml`, `docker-compose.collector.yml`, контейнер `stand-runner`) у середовищі
розробки не збирається (MITM-проксі ламає `pip install` у `docker build`, DEC-14 telemetry), тому — як у telemetry (DEC-15):
iot_sim і колектор — процеси на localhost з окремих venv, Odoo — `tools/odoo/serve.sh`. Керує всім
`services/collector_plugins/machine_connect/tests/stand/stand.sh`.

| Компонент | Як піднято |
|---|---|
| iot_sim 0.1.0 | `python -m iot_sim run` (venv `F3D_VENV_SIM`, режим `scenario`, `factor=1`), порти 4840/502/8082/8083/8090 |
| колектор + пакет | `f3d-collector run` (venv `F3D_VENV_MC`: `pip install -e services/collector -e services/collector_plugins/machine_connect`) |
| Odoo 19.0 CE | `serve.sh f3d_mc_tk 18070` на копії шаблона `f3d_mc_t0` |
| фейковий OPC UA | `tests/fakes/opcua_server.py` у потоці pytest (`iot-sim:4841`) — де iot_sim не підтримує сценарій (див. TEST_REPORT) |

Імена `iot-sim`, `odoo19` — `127.0.0.1` у `/etc/hosts`. Змінні колектора (SPEC §8.2): `F3D_OPCUA_PASSWORD=$SIM_OPCUA_PASS`,
`F3D_WOODSTORE_KEY=$SIM_WOODSTORE_APIKEY`, `F3D_CUTOPT_KEY=$SIM_JOBS_APIKEY`, `F3D_ALLOW_HOSTS=iot-sim,odoo19`,
`F3D_WRITE_ENABLED=0` (у ТК-04, 06, 07, 10, 15 — `1`), `F3D_MC_STATE_DIR` — каталог стану.

```bash
S=factory3d/services/collector_plugins/machine_connect/tests/stand
$S/stand.sh build          # f3d_mc_seed (telemetry + seed_pre.py) → f3d_mc_pre (+ factory3d_machine_connect, ТК-01 крок 2)
$S/stand.sh template       # f3d_mc_t0 — шаблон для ТК (п. 3 нижче)
$S/stand.sh up             # свіжа копія f3d_mc_tk + Odoo + колектор (емулятор — якщо не піднятий)
pytest factory3d/services/collector_plugins/machine_connect -m stand      # усі ТК/ТБ/ТП (години!)
pytest factory3d/services/collector_plugins/machine_connect -m stand -k "tk02 or tb02"   # вибірково
```

Вхід у UI стенда: `http://127.0.0.1:18070/web/login?db=f3d_mc_tk` (`admin/admin`; `stand_op`, `stand_master`, `stand_stock` —
оператор SAW-2, майстер, начальник складу; пароль = логін). Скорочення часу в прогонах: `F3D_STAND_TK03_MIN` (SPEC 60, типово 12),
`F3D_STAND_TP01_MIN` (SPEC 30, типово 5), `F3D_STAND_TP02_MIN` (SPEC 30, типово 8).

## Чек-лист (SPEC §13.5)

| № | Крок | Команда / дія | Стенд розробки |
|---|---|---|---|
| 1 | Дамп `odoo` timur-o19demo → `odoo_f3d_mc`; `factory3d_base`, `factory3d_telemetry` (і `factory3d_viewer`) за їхніми DEPLOY_TEST. Жива база не змінюється | `pg_dump -Fc odoo > odoo.dump`; `createdb odoo_f3d_mc && pg_restore -d odoo_f3d_mc odoo.dump`; встановити модулі `update.sh` | **ЛЮДИНА** — копії демо-бази в середовищі розробки немає. Замінник: `stand.sh build` (чиста база + telemetry + `seed_pre.py`: 35 РЦ, обладнання `f3d_code`, оператори `OP-*`, 36 стосів `PLT-*` за станом woodStore, специфікації «Комод 4 шухляди» й «Шухляда») |
| 2 | Знімки S0–S5 (до установки модуля) | `S0 SELECT count(*) FROM mrp_workcenter_productivity` (демо: 184); `S1 … date_end IS NULL GROUP BY 1`; `S2 SELECT id,state,qty_produced FROM mrp_workorder`; `S3 … maintenance_request`; `S4 SELECT max(write_date) FROM mrp_workorder` і productivity; `S5 stock_quant ⨝ stock_location WHERE f3d_code LIKE 'PLT-%'` | виконано в ТК-01 (`snapshots()`): порожні/нульові на посіяній базі |
| 3 | Установка (ТК-01 кроки 2–3): час хука, `migration_report`; S0 = 184, S2/S3/S5 без змін, S1 — без змін, крім `f3d_source='demo'`. Шаблон ТК | `odoo-bin -d odoo_f3d_mc -i factory3d_machine_connect --stop-after-init`; `createdb -T odoo_f3d_mc odoo_f3d_mc_t0` | виконано на `f3d_mc_seed`: S0…S5 без змін; `migration_report.state=done`, 35 верстатів; шаблон `f3d_mc_t0`. 184/74 простої — **ЛЮДИНА** на копії демо |
| 4 | Стоп-крани: `read_enabled=True`, `auto_start_enabled=False`, `write_enabled=False`, `cutting_mode=manual`; по одному верстату: `f3d.machine.read_enabled=False` для 34, `True` — лише SAW-1 | Налаштування → Завод 3D → Верстати; або `UPDATE`-скрипт у Odoo shell | значення за замовчуванням з `ir_config_parameter.xml`; «по одному верстату» — **ЛЮДИНА** (демо-копія); ТК-15 перевіряє `read_enabled`/`auto_start_enabled` |
| 5 | Юніт-тести на копії → 0 падінь (`TestMigrationDemo` — на шаблоні `odoo_f3d_mc_t0`) | `F3D_TEST_INSTALL=factory3d_machine_connect tools/odoo/run_tests.sh <db> /factory3d_machine_connect` | `0 failed, 0 error of 127 tests` на чистій базі (`TestMigrationDemo` пропущено — немає копії демо) |
| 6 | Перший тиждень — лише читання: д1 SAW-1; д2 + SAW-2/3, NEST-1, CNC-1…4; д3 + `u80` (SLIDE-1, VSAW-1, SAND-1, PRESS-1, GLUE-1; перевірка проводки DI як у ТК-05 з `hold`); д4 + `u81…u83`; д5 — усі 35, OEE за тиждень. Щодня: `SELECT count(*) FROM mrp_workorder WHERE write_uid = <user_f3d_machine>` = 0; `f3d.command` модуля = 0 | емулятор `follow_odoo`, далі `scenario`+`shift` | **ЛЮДИНА** — 5 діб; на стенді його скорочену версію виконує ТК-03 (`write_uid = user_f3d_machine` — 0, команд 0) |
| 7 | Тиждень 2: `auto_start_enabled=True`; `auto_start_mode='job_or_single'` лише SAW-1, решта `off`; щодня — подвійних таймерів 0 (`SELECT workorder_id,count(*) FROM mrp_workcenter_productivity WHERE date_end IS NULL GROUP BY 1 HAVING count(*) > 1`) | | **ЛЮДИНА**; ТК-04, ТК-05 перевіряють автостарт на стенді |
| 8 | Портал: `write_enabled` і запобіжники `equipment/GANTRY-1/cmd` — лише після зелених ТК-06…08 і відповіді на Q-02; спершу `stack`, потім `feed` | | **ЛЮДИНА** (Q-02 — відповідь HOMAG); ТК-06…08, ТК-15 — на стенді |
| 9 | Карти розкрою: `cutting_mode=manual` до закриття Q-03; ТК-10 — лише на стенді | | **ЛЮДИНА** (Q-03 — звірка формату CSV з intelliDivide) |
| 10 | Нейтралізація: `psql -d odoo_f3d_mc -f data/neutralize.sql` (разом з base/telemetry/viewer/iot_sim) → AC-92, ТБ-10 | | ТБ-10 на стенді |
| 11 | Деінсталяція/повторна установка на копії (§5.4, §5.5): після повторної установки 74 простої, S0 не зменшився | `odoo-bin -d <копія> -u`/деінсталяція з UI, повторна установка | покрито Odoo-тестами `test_hooks`; 74 простої — **ЛЮДИНА** на копії демо |
| 12 | Відкат на живій базі = вимкнути три стоп-крани → деінсталяція (стандартний журнал часу лишається; простої й OEE модуля зникають — вивантажити до того). Фактичні кількості, час хука, результати ТК/ТБ/ТП — у `CHANGELOG.md` («Міграція демо») і `TEST_REPORT.md` | | **ЛЮДИНА** — на живій базі |

## Що лишилось для виконання людиною / на сервері timur-o19demo

1. Пп. 1–3, 11 на копії демо-бази: `TestMigrationDemo`, S0 = 184, 74 простої, 29 `working` / 5 `idle` / CNC-2 `fault` (AC-93).
2. П. 6–7 — тиждень читання й тиждень автостарту по одному верстату; щоденні перевірки `write_uid`/команд/подвійних таймерів.
3. Сертифікати OPC UA (`F3D_OPCUA_CERT`, `F3D_OPCUA_KEY`, `F3D_OPCUA_SERVER_CERT`), nodeset HOMAG і серійні номери (Q-01, Q-12) —
   вхідні дані пуско-налагодження; ТБ-07 на стенді виконано з самопідписаними сертифікатами емулятора.
4. UI-перевірки (MAN): меню «Завод 3D → Верстати» від `user_plain`, ТК-02 крок 4, ТК-11 кроки 3–5 на планшеті, ТК-14 (3D, потрібен
   `factory3d_viewer`).
5. `docker build` образів колектора з пакетом (`requirements-extra.txt`) і `docker compose` стенд §13.2 — на машині без MITM-проксі.
