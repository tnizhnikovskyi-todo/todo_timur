# DEPLOY_TEST — td_bms 19.0.1.0.0 (SPEC §13.5, «одна зона → усі»)

Чек-лист установки на копію демо-бази і відтворення стендових перевірок. Результати з числами — `TEST_REPORT.md`.
Код стенда — `factory3d/odoo_addons/td_bms/tests/stand/` (`stand.sh`, `seed_odoo.py`, `test_tk_a.py`, `test_tk_b.py`,
`test_tb.py`, `test_tp.py`).

## Середовище стенда

Стенд піднімається **без docker build** (процесний режим, як у `td_telemetry`):

| Компонент | Як |
|---|---|
| Odoo 19 CE | `tools/odoo/new_db.sh f3d_factory3d_bms_w7` → `F3D_TEST_INSTALL=td_factory3d,td_telemetry,td_bms tools/odoo/update.sh …` → `serve.sh` (порт 18070) |
| Емулятор | `services/iot_sim` (`python -m iot_sim run`, venv `$F3D_VENVS/iot_sim`), REST `127.0.0.1:8090/sim/v1`, BACnet `127.0.0.1:47808`, HelvarNet `:50000` |
| Колектор | `f3d-collector run` з venv `$F3D_VENVS/collector` (`pip install --no-deps ./collector ./collector_plugins/f3d_collector_bms`), `F3D_ALLOW_HOSTS=iot-sim,mosquitto`, `F3D_WRITE_ENABLED=0`, BACnet-bind `127.0.0.2:47808` |
| MQTT | `eclipse-mosquitto:2.0.20` у docker (`--network host`); якщо образ не завантажується (ліміт реєстру) — запасний брокер `amqtt` з `$F3D_VENVS/broker` (`pip install amqtt`, анонімний доступ, лише стенд) |
| Імена | `iot-sim mosquitto collector` → `127.0.0.1` у `/etc/hosts` (робить `stand.sh up`) |

```bash
export F3D_VENVS=/tmp/f3dvenv          # venv: iot_sim, collector (+ плагін bms), broker (amqtt)
T=factory3d/odoo_addons/td_bms/tests/stand
$T/stand.sh up                          # брокер + емулятор + Odoo + seed + колектор; down — зупинка
$F3D_VENVS/collector/bin/pytest -q -s -m stand $T/test_tk_a.py $T/test_tk_b.py $T/test_tb.py $T/test_tp.py
```

`seed_odoo.py` (запускається в `stand.sh up/seed`): команда «Служба головного механіка» (+ `default_team_id`), календарі «Цілодобово (ТК)» і
«Без робочого часу (ТК)», затримки перевірок 1 хв, `realarm_cooldown_s=60`, **обладнання `maintenance.equipment` з `td_code`**
(на чистій базі його немає — у демо воно з'являється після міграції `td_factory3d`; без нього телеметрія не створює заявок) і повторний
`run_install` для прив'язки `equipment_id`. Календар перевірок стенд ставить сам у тестах, що його потребують
(`full_calendar`/`no_calendar`), годинник емулятора — 10:00 за Києвом (`sim_clock`).

## Чек-лист §13.5

| № | Крок | Команда / перевірка | Результат на стенді |
|---|---|---|---|
| 1 | Дамп `odoo` → `odoo_f3d_bms`; знімок `td_signal ventilation/%` | `createdb -T odoo odoo_f3d_bms`; `psql -c "SELECT code,last_value,status,maintenance_request_id FROM td_signal WHERE code LIKE 'ventilation/%'"` | ⏭ копії демо-бази в середовищі немає; замість неї — чиста база з `f3d_template` |
| 2 | Установка `td_bms`; лог без ERROR; `install_report.state='done'`; лічильники §5.3 | `update.sh <db>`; `grep -c ERROR` лога; параметр `td.bms.install_report` | ✅ 11 с, лог без ERROR, `state='done'` (чиста база: 549 сигналів bms, 33 джерела, 66 обладнання після seed); 468/81 — лише на демо ⏭ |
| 3 | `--test-tags /td_bms`; `pytest` плагіна; `test_data_sync.py` | `F3D_TEST_INSTALL=td_factory3d,td_telemetry,td_bms tools/odoo/run_tests.sh <db> /td_bms`; `pytest services/collector_plugins/f3d_collector_bms` | ✅ 139/139; плагін 28 passed |
| 4 | **Одна зона:** `read_enabled` лише для `BAC-108-RV-08`, `BAC-109-RV-09`, `HN-LP-2`; колектор; ТК-12 для RV-08, RV-09, LT-CUT; ТК-03 (лише LT-CUT) | масово «Читати» у списку джерел; `stand.sh collector-restart`; `test_tk_a.py -k tk12` | див. TEST_REPORT («Одна зона») |
| 5 | **Усі:** увімкнути решту джерел; ТК-01, ТК-02, ТК-04…ТК-08 | список джерел → «Читати»; `pytest test_tk_a.py test_tk_b.py` | див. TEST_REPORT |
| 6 | ТК-09 — лише на стенді з емулятором | `F3D_WRITE_ENABLED=1` перезапуск колектора + `res.config.settings` (`test_tk09_control`) | ✅ на стенді; на копії проду керування не вмикається |
| 7 | Відкат: `neutralize.sql`; деінсталяція §5.4; база `odoo` не змінювалась | `psql -d <db> -f odoo_addons/td_bms/data/neutralize.sql`; `test_tb.py::test_tb07_neutralize`; `test_hooks::test_uninstall_hook` | ✅ нейтралізація на окремій базі; деінсталяція — UT |
| 8 | Фактичні числа — у `CHANGELOG.md` («Установка на копію демо 14.10.2026») | — | ⏭ копії демо немає; числа стенда — у `TEST_REPORT.md` (рядок для CHANGELOG додає власник модуля) |

## Відомі особливості стенда

- `iot_sim` стартує з RV-05 `filter_dp_pa≈120` (а не 285, як у §13.2 ТК-01): ТК-02 спершу чекає `ok`.
- Для заявок потрібне обладнання з `td_code` (див. `seed_odoo.py`).
- ТК-05, ТК-11 потребують календарів «Без робочого часу (ТК)» / «Цілодобово (ТК)» — створює seed, ставить тест.
- `pkill -f` у скриптах використовує шаблон `[a]mqtt`, щоб не вбити власний shell.
