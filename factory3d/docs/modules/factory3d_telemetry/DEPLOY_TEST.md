# DEPLOY_TEST factory3d_telemetry (чек-лист SPEC §13.5)

Здає W7. Протокол прогону — `TEST_REPORT.md` (таблиці ТК/ТБ/ТП, AC-01…AC-104); тут — кроки розгортання на копії
демо-бази, команди й фактичні результати. Дата прогону: **2026-10-15**; середовище прогону — див. «Середовище стенда».

## Середовище стенда

Стенд (SPEC §13.2: емулятор `factory3d_iot_sim` + колектор + Odoo) піднято **процесним режимом** — Docker daemon у середовищі
розробки працює (`dockerd`, `docker run` — ок), але `docker build` образів не проходить (MITM-проксі: `pip install` у `RUN`
падає з `CERTIFICATE_VERIFY_FAILED`), тому:

| Компонент | Як піднято |
|---|---|
| iot_sim 0.1.0 | процес `python -m iot_sim run` з `services/iot_sim/.venv` (режим `scenario`, `factor=1`) |
| mosquitto 2.0.20 | контейнер `eclipse-mosquitto:2.0.20`, `--network host`, користувачі `sim`, `collector` |
| Odoo 19.0 | `factory3d/tools/odoo/serve.sh f3d_telemetry_w7 18069` (база з `factory3d_iot_sim`, `factory3d_telemetry`, `factory3d_telemetry_viewer`) |
| колектор 0.1.0 | процес `f3d-collector run` з `services/collector/.venv`; токен — `f3d.collector.action_generate_token` (XML-RPC) |

Імена `iot-sim`, `mosquitto`, `collector` додаються в `/etc/hosts` як `127.0.0.1` (адреси джерел у даних модуля
— `iot-sim`/`mosquitto` — лишаються як у Додатку C.1). BACnet: емулятор слухає `127.0.0.1:47808`, колектор —
`127.0.0.2:47808` (`F3D_BACNET_BIND`), бо два UDP-сокети одного хоста не можуть ділити порт.

Усе керується `services/collector/tests/stand/stand.sh`:

```bash
cd factory3d/services/collector
tests/stand/stand.sh up            # hosts, mosquitto, iot_sim, Odoo (serve.sh), seed_odoo.py, токен, колектор
.venv/bin/pytest -q -m stand tests/stand
tests/stand/stand.sh down          # зупинити колектор, iot_sim, mosquitto, Odoo
```

Змінні для `pytest -m stand` (SPEC §13.2): `F3D_STAND_ODOO_URL` (за умовчанням `http://127.0.0.1:18069`), `F3D_STAND_ODOO_DB`
(`f3d_telemetry_w7`), `F3D_STAND_ODOO_LOGIN`/`PASSWORD` (`admin`/`admin`), `F3D_STAND_SIM_URL`, `SIM_API_TOKEN`,
`F3D_STAND_COLLECTOR_METRICS` (`http://127.0.0.1:9108`), `F3D_STAND_DIR` (`/tmp/f3dstand`: логи й токен). Якщо стенд не піднято —
стендові тести пропускаються з причиною, а не падають.

Docker-варіант стенда (`docker compose -f docker-compose.sim.yml --profile dev up -d`, `docker-compose.collector.yml`)
пробується на сервері з доступом до PyPI з контейнерів; у цьому прогоні вне среды: `docker build` без доступу до PyPI.

## Чек-лист

Позначки: **OK** — виконано в цьому прогоні; **чиста база** — виконано на еквіваленті (нова база без рівня 0);
**вне среды** — потребує копії демо-бази `odoo` timur-o19demo, якої в середовищі розробки немає.

| № | Крок | Команда / дія | Результат (2026-10-15) |
|---|---|---|---|
| 1 | Дамп `odoo` → `odoo_f3d_tel`; `factory3d_base` за його DEPLOY_TEST | `pg_dump -Fc odoo`, `pg_restore -d odoo_f3d_tel`, `odoo-bin -d odoo_f3d_tel -i factory3d_base` | вне среды: немає доступу до timur-o19demo. Чиста база: `tools/odoo/run_tests.sh f3d_telemetry_w7` (шаблон `f3d_template` + `factory3d_base` як залежність) — OK |
| 2 | Знімки S0–S3 | SQL §13.5 п. 2 (`x_f3d_reading`, `x_f3d_signal`, `maintenance_request`, `cron_iot_sim`) | вне среды (рівня 0 немає); для еквівалента — знімки таблиць `f3d_*` до/після п. 6 |
| 3 | Установка (ТК-01) | `odoo-bin -d odoo_f3d_tel -i factory3d_telemetry --log-level=info` | чиста база: установка OK, звіт `factory3d.telemetry.level0_migrated`: `state=skipped`, `mismatches=[]` (`tests/stand/test_deploy.py::test_dep03_install_report`). AC-58 (`signals_migrated=196`, `readings_migrated=N`) — вне среды (демо-копія); логіку покривають синтетичні юніт-тести `tests/test_migration.py::TestLevel0` |
| 4 | Юніт-тести на копії | `F3D_TEST_INSTALL=factory3d_telemetry,factory3d_telemetry_viewer tools/odoo/run_tests.sh f3d_telemetry_w7 /factory3d_telemetry,/factory3d_telemetry_viewer` | OK — результат у `TEST_REPORT.md` (класи синтетичного рівня 0 — `skipIf`, AC-58 — у ТК-01) |
| 5 | Стенд ТК-02…ТК-16 | `pytest -q -m stand tests/stand` | див. `TEST_REPORT.md` |
| 6 | Повтор міграції | Налаштування → «Повторити міграцію рівня 0» (`hooks.run_level0_migration`) | чиста база: `mismatches=[]`, `created=0`, кількості `f3d_signal/f3d_source/f3d_reading` незмінні (`test_dep06_rerun_migration`) |
| 7 | Деінсталяція й повторна установка | `button_immediate_uninstall` (viewer, telemetry) → перевірка → `tools/odoo/update.sh` | чиста база: таблиць `f3d_signal/source/collector/reading/reading_hour/command/push_event` немає, параметрів `factory3d.telemetry.*` немає; повторна установка → звіт без розбіжностей (`test_dep07_uninstall_reinstall`). На демо (`x_f3d_signal.x_active = true` для 196, меню «Імітація IoT», `cron_iot_sim` вимкнений) — вне среды |
| 8 | Нейтралізація | `psql -d <copy> -f data/neutralize.sql` (base, iot_sim, telemetry, viewer) | OK: токени колекторів стерто, `read_enabled/write_enabled='False'`, крони модуля вимкнені, джерела `disabled` (`test_dep08_neutralize`) |
| 9 | Відкат | видалити копію; жива база не змінювалась | OK: копії `f3d_w7_dep`, `f3d_w7_neu` — окремі бази; на живій базі відкат = п. 7 + ручне ввімкнення `cron_iot_sim` (A-07) — вне среды |
| 10 | Фактичні кількості, час хука, результати ТК/ТП | `CHANGELOG.md` («Міграція демо»), `TEST_REPORT.md` | ТК/ТБ/ТП — `TEST_REPORT.md`; час хука й кількості на демо (≤ 120 с, `signals_migrated=196`) — вне среды |

## Що лишилось для виконання на сервері timur-o19demo

1. п. 1–3: дамп `odoo` → `odoo_f3d_tel`, знімки S0–S3, установка `factory3d_telemetry`; звірити `level0_migrated`
   з AC-58 (`signals_migrated=196`, `by_module={"energy": 87, "bms": 81, "fire_safety": 1, "telemetry": 27}`, `alarm=1`,
   `with_request=2`, `readings_migrated=S0`, `skipped_null_ts=0`, `requests_linked=2`, `signals_catalog.created=29`,
   `bound=55`, `meters=9`), час хука ≤ 120 с.
2. п. 7 на демо-копії: `x_f3d_signal.x_active = true` для 196; меню «Імітація IoT» видно; S3 лишається `false`.
3. Запуск стенда в Docker (`docker compose` для `iot_sim` і колектора) з `.env` за ARCH §3 і повторення ТК-02…ТК-16
   на копії (у цьому прогоні ТК виконано проти бази зі свіжою установкою й посівом `seed_odoo.py`, див. TEST_REPORT).
