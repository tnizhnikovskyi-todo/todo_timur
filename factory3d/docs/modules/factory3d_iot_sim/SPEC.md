# factory3d_iot_sim — специфікація

Версія 0.1 · 13.10.2026 · технічне рішення — `ARCHITECTURE.md` (поруч). Мова: українська; технічні імена — англійською.

Контракти, на які спирається документ: `docs/ARCHITECTURE.md` §5 (конвенції імен сигналів, стоп-крани, права), §6.1–6.3 (`f3d.scene.mixin.f3d_code`, `f3d.zone`, ворота-`stock.location`, паспорт `maintenance.equipment.f3d_*`), §6.6 (протокольна матриця P-01…P-13, REST `/sim/v1/*`, режими `scenario`/`follow_odoo`), §6.7 (шляхи даних переглядача), §6.8 (заявки ТО), рішення D-01, D-05…D-09, D-13; рішення автора A-01…A-12 (`ARCHITECTURE.md` §7).

Що цей документ **віддає** іншим модулям (посилатися за ідентифікаторами `factory3d_iot_sim <ID>`): протокольні карти **P-01…P-12** (§8.3–§8.14), каталог сигналів **Додаток A** (662 рядки), **API-01…API-03** (Odoo), **API-10…API-19** (`/sim/v1`), **API-20…API-27** (woodStore), **API-30…API-34** (`/jobs`), **API-40…API-46** (BioStar 2), схема MQTT P-06 (§8.8), формат LPR і SICS (§8.13), правила R-01…R-30 (§9), сценарії S-01…S-15 (§9.3).

---

## 0. Дерево файлів модуля

### 0.1 Сервіс `services/iot_sim`

```
services/iot_sim/
├── README.md                       запуск, порти, змінні середовища (коротко; повно — тут §8.1–8.2)
├── pyproject.toml                  пакет iot_sim, Python 3.12, entry point `iot-sim`
├── requirements.txt                закріплені версії (§8.1.2)
├── Dockerfile                      python:3.12-slim, non-root user `sim`, HEALTHCHECK → GET /sim/v1/health
├── docker-compose.sim.yml          сервіси iot_sim, mosquitto, genset_relay; мережа f3d_sim (internal); профілі demo/dev
├── mosquitto/mosquitto.conf        listener 1883, allow_anonymous false, password_file
├── catalog/
│   ├── signals.csv                 каталог сигналів = Додаток A (генерується tools/gen_catalog.py)
│   ├── devices.yaml                резервний реєстр пристроїв (якщо Odoo API-01 недоступний)
│   ├── zones.json                  полігони зон (резерв; основне джерело — API-01)
│   └── passports.json              витяг із plant/equipment_specs.json (номінали)
├── tools/
│   ├── gen_catalog.py              генерує signals.csv і data/f3d_sim_signal.csv Odoo-модуля з правил §5.2/§8
│   ├── gen_devices.py              генерує devices.yaml з dist/odoo_demo.json + equipment_specs.json
│   └── mkcert.sh                   самопідписані сертифікати для OPC UA і BioStar (dev)
├── iot_sim/
│   ├── __init__.py                 __version__
│   ├── __main__.py                 CLI: `python -m iot_sim run|check-config|dump-catalog`
│   ├── config.py                   Settings (pydantic-settings) — усі SIM_* (§8.2.1)
│   ├── core/
│   │   ├── clock.py                SimClock: tz Europe/Kyiv, factor, now(), sleep(), sun (astral)
│   │   ├── rng.py                  детермінований шум (seed, код сигналу) — R-00
│   │   ├── registry.py             Device, Signal, Catalog; завантаження API-01 / devices.yaml / signals.csv
│   │   ├── world.py                World: зміна, завдання, фури, люди, баланс енергії, події, знімок
│   │   ├── events.py               Event, EventBus (кільце 10 000), типи подій (§8.2.4)
│   │   ├── scenarios.py            ScenarioRunner: реєстр S-01…S-15, запуск/зупинка/параметри
│   │   └── snapshot.py             збереження/відновлення state/snapshot.json
│   ├── models/                     машини поведінки (одна на клас пристрою), усі — підкласи Model (§8.2.3)
│   │   ├── base.py                 Model: tick(dt), signals(), fault(reason)/clear()
│   │   ├── machine.py              верстат HOMAG: стан/прапори/лічильники/завдання (R-02, R-14…R-17)
│   │   ├── io_machine.py           верстат без інтерфейсу: DI/лічильник (R-02, R-14…R-16)
│   │   ├── gantry.py               портал STORETEQ: стоси, завдання, цикли, вакуум (R-07, R-18)
│   │   ├── mobile.py               навантажувачі/тягач: АКБ, мотогодини, рух (R-05, R-06, R-19)
│   │   ├── compressor.py           Atlas Copco GA 37 (R-08)
│   │   ├── dust.py                 NESTRO NKJ (R-09)
│   │   ├── boiler.py               Kalvis K-500M ×2 (R-10)
│   │   ├── pv.py                   8 × SUN2000-115KTL (R-11)
│   │   ├── bess.py                 LUNA2000 (R-13)
│   │   ├── chp.py                  TEDOM Quanto D800 (R-12)
│   │   ├── ats.py                  Socomec ATyS p (R-22)
│   │   ├── transformer.py          T1/T2 (R-04)
│   │   ├── meter.py                PM5560: агрегація споживачів у фідери/вводи (R-01, R-03)
│   │   ├── roofvent.py             Hoval RoofVent / VTS AHU / витяжні вентилятори (R-09, R-23)
│   │   ├── lighting.py             групи DALI, щити (R-24)
│   │   ├── facp.py                 Cerberus PRO: зони, сповіщувачі, шлейфи, тривоги (R-25)
│   │   ├── spark.py                GreCon BS 7 (R-26)
│   │   ├── smoke.py                D+H димовидалення (R-27)
│   │   ├── access.py               BioStar 2: користувачі, пристрої, події (R-28)
│   │   ├── yard.py                 фури, шлагбауми, LPR, ваги (R-29, R-30)
│   │   └── water.py                водомір (R-21)
│   ├── protocols/
│   │   ├── base.py                 ProtocolServer: start(), stop(), health()
│   │   ├── opcua_server.py         P-01/P-03 (asyncua) — §8.3
│   │   ├── modbus_server.py        P-02/P-05/P-07/P-09/P-11 (pymodbus) — §8.4, §8.7, §8.9
│   │   ├── modbus_maps/            один модуль на карту: pm5560.py, sun2000.py, luna2000.py,
│   │   │                           elektronikon.py, atys.py, tedom.py, adam6050.py, adam6060.py, adam6017.py, adam6015.py
│   │   ├── bacnet_server.py        P-08/P-09 (bacpypes3) — §8.10, §8.11
│   │   ├── helvarnet_server.py     P-08 (asyncio TCP/UDP) — §8.10.4
│   │   ├── mqtt_publisher.py       P-06 (paho) — §8.8
│   │   ├── biostar_api.py          P-10 (FastAPI, TLS) — §8.12
│   │   ├── woodstore_api.py        P-03 (FastAPI) — §8.5
│   │   ├── jobs_api.py             P-04 (FastAPI) — §8.6
│   │   ├── lpr_push.py             P-11 (httpx POST) — §8.13.2
│   │   ├── sics_server.py          P-11 (asyncio TCP) — §8.13.3
│   │   └── control_api.py          REST /sim/v1 (FastAPI) — §7.2
│   ├── odoo/
│   │   ├── devices_client.py       GET /f3d/sim/devices (API-01), POST /f3d/sim/events (API-03)
│   │   └── follow.py               режим follow_odoo: XML-RPC лише читання (§8.9.10)
│   └── logging_conf.py             JSON-логи, SecretFilter
├── state/                          snapshot.json (volume)
└── tests/
    ├── unit/                       test_rng.py, test_clock.py, test_models_*.py, test_world.py, test_scenarios.py
    ├── protocols/                  test_opcua.py, test_modbus_*.py, test_bacnet.py, test_helvarnet.py, test_mqtt.py,
    │                               test_biostar.py, test_woodstore.py, test_jobs.py, test_sics.py, test_lpr.py, test_control_api.py
    ├── stand/                      ТК-01…ТК-16 проти compose (pytest -m stand)
    └── conftest.py                 фікстури: world(seed), running servers (порти з SIM_TEST_PORT_BASE)
```

### 0.2 Odoo-модуль `odoo_addons/factory3d_iot_sim`

```
odoo_addons/factory3d_iot_sim/
├── __manifest__.py                 19.0.2.0.0 (§1)
├── __init__.py                     models, controllers, hooks (post_init_hook, uninstall_hook)
├── hooks.py                        post_init_hook / uninstall_hook (§5.3)
├── neutralize.sql                  стоп-крани, крони, токени (§4.4)
├── data/
│   ├── models.xml                  ← без змін, успадковано (рівень 0: x_f3d_signal, x_f3d_reading)
│   ├── actions.xml                 ← без змін (action_iot_tick, cron_iot_sim, start/stop/tick_now)
│   ├── level0.xml                  перейменування крона/меню рівня 0 (§5.1)
│   ├── ir_config_parameter.xml     параметри factory3d.iot_sim.* (§5.1)
│   ├── ir_cron.xml                 cron_f3d_sim_status, cron_f3d_sim_gc (§6)
│   ├── ir_sequence.xml             f3d.sim.run
│   ├── f3d_sim_scenario.xml        15 сценаріїв (§5.1)
│   └── f3d_sim_signal.csv          каталог = Додаток A (копія services/iot_sim/catalog/signals.csv)
├── models/
│   ├── __init__.py
│   ├── sim_panel.py                M-01
│   ├── sim_device.py               M-02
│   ├── sim_signal.py               M-03
│   ├── sim_scenario.py             M-04
│   ├── sim_run.py                  M-05
│   ├── sim_event.py                M-06
│   ├── maintenance_equipment.py    M-07
│   ├── mrp_workcenter.py           M-08
│   ├── res_config_settings.py      M-09
│   └── sim_client.py               AbstractModel f3d.sim.client: HTTP до /sim/v1 (§2.10)
├── wizard/
│   ├── __init__.py
│   ├── sim_fault_wizard.py         M-10
│   └── sim_run_wizard.py           M-11
├── controllers/
│   ├── __init__.py
│   └── sim_api.py                  API-01, API-02, API-03
├── security/
│   ├── ir.model.access.csv         §4.1
│   └── security.xml                правила записів (§4.2) — порожньо, крім коментаря
├── views/
│   ├── views.xml                   ← без змін, успадковано (рівень 0)
│   ├── sim_panel_views.xml         V-01
│   ├── sim_device_views.xml        V-02…V-04
│   ├── sim_signal_views.xml        V-05, V-06
│   ├── sim_scenario_views.xml      V-07
│   ├── sim_run_views.xml           V-08
│   ├── sim_event_views.xml         V-09
│   ├── maintenance_equipment_views.xml  V-10
│   ├── mrp_workcenter_views.xml    V-13
│   ├── res_config_settings_views.xml    V-11
│   ├── wizard_views.xml            V-12
│   └── menus.xml                   меню (§3.14)
├── static/description/icon.png
├── migrations/19.0.2.0.0/pre-migrate.py   фіксація версії data-модуля (§5.3 крок 0)
└── tests/
    ├── __init__.py
    ├── common.py                   SimCase: TransactionCase + мок HTTP /sim/v1
    ├── test_panel.py
    ├── test_device.py
    ├── test_signal_catalog.py
    ├── test_scenario_run.py
    ├── test_api_devices.py         HttpCase API-01…API-03
    ├── test_security.py
    └── test_migration.py
```

---

## 1. Маніфест

```python
{
    "name": "Factory3D: емулятор обладнання (пульт)",
    "version": "19.0.2.0.0",
    "summary": "Пульт емулятора обладнання factory3d: реєстр пристроїв, каталог сигналів, сценарії, рівень 0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "license": "LGPL-3",
    "website": "https://todo.ltd",
    "depends": ["factory3d_base"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        # рівень 0 — успадковані файли data-модуля, ПЕРШИМИ і без змін (інакше Odoo видалить записи)
        "data/models.xml",
        "data/actions.xml",
        "views/views.xml",
        # новий модуль
        "security/ir.model.access.csv",
        "security/security.xml",
        "data/ir_config_parameter.xml",
        "data/ir_sequence.xml",
        "data/level0.xml",
        "data/f3d_sim_scenario.xml",
        "data/ir_cron.xml",
        "views/sim_panel_views.xml",
        "views/sim_device_views.xml",
        "views/sim_signal_views.xml",
        "views/sim_scenario_views.xml",
        "views/sim_run_views.xml",
        "views/sim_event_views.xml",
        "views/wizard_views.xml",
        "views/maintenance_equipment_views.xml",
        "views/mrp_workcenter_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
}
```

Примітки: `factory3d_base` транзитивно дає `maintenance`, `mrp`, `mrp_maintenance`, `hr`, `stock`, `stock_picking_batch`; `data/f3d_sim_signal.csv` завантажує `post_init_hook` (не через `data`, бо потрібні `device_id` за кодом); `requests` є в стандартній поставці Odoo.

---

## 2. Моделі

Спільне: усі нові моделі `_description` українською, `_order` як зазначено, без `x_`-полів. Доступ до сервісу — лише через домішку `f3d.sim.client` (§2.10): вона перевіряє стоп-крани й ховає токен.

### 2.1 M-01 `f3d.sim.panel` — пульт

`_name = "f3d.sim.panel"`, `_description = "Пульт емулятора обладнання"`, `_order = "id"`, `_rec_name = "name"`, домішки: `f3d.sim.client`, `mail.thread` (журнал дій у чаттері). Один запис на базу (SQL-constraint `panel_single` через `_check_single`).

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | string «Назва», default «Пульт емулятора», required |
| `state` | Selection | string «Стан сервісу»; `[("unconfigured","Не налаштовано"),("offline","Офлайн"),("online","Онлайн"),("locked","Стоп-кран сервісу"),("degraded","Частково")]`; default `unconfigured`; readonly; tracking |
| `last_contact` | Datetime | «Останній контакт», readonly |
| `last_error` | Char | «Остання помилка», readonly |
| `version` | Char | «Версія сервісу», readonly |
| `mode` | Selection | «Режим»: `[("scenario","Сценарій"),("follow_odoo","За Odoo")]`, readonly (фактичний режим сервісу) |
| `mode_new` | Selection | «Новий режим», ті самі значення, default з `factory3d.iot_sim.mode` |
| `factor` | Float | «Прискорення (факт)», digits (6,2), readonly |
| `factor_new` | Float | «Нове прискорення», default 1.0; `_check_factor`: 0,1 ≤ x ≤ 60, інакше `ValidationError("Прискорення має бути від 0,1 до 60")` |
| `sim_time` | Datetime | «Час емулятора», readonly |
| `uptime_s` | Integer | «Аптайм, с», readonly |
| `seed` | Integer | «Зерно», readonly |
| `active_run_ids` | One2many | `f3d.sim.run`, `panel_id`, domain `[("state","in",["queued","running","stopping"])]`, «Активні запуски» |
| `alarm_count` | Integer | «Сигналів у тривозі», readonly |
| `device_count` | Integer | «Пристроїв», compute `_compute_counts` (search_count `f3d.sim.device`) |
| `signal_count` | Integer | «Сигналів», compute |
| `protocol_status` | Json | «Стан протоколів», readonly: `{"opcua": "ok", "modbus": "ok", …}` з API-10 |
| `odoo_stale` | Boolean | «Дані Odoo застарілі (follow_odoo)», readonly |
| `level0_state` | Selection | «Рівень 0»: `[("auto_off","Авто: вимкнено (сервіс онлайн)"),("auto_on","Авто: увімкнено (сервіс офлайн)"),("forced_on","Примусово увімкнено"),("forced_off","Примусово вимкнено")]`, default `auto_off`, tracking |
| `level0_signal_count` | Integer | compute: `search_count` у `x_f3d_signal`, якщо модель є в `self.env`, інакше 0 |
| `read_enabled` | Boolean | compute non-stored з `factory3d.iot_sim.read_enabled` (для `invisible` у формі) |
| `write_enabled` | Boolean | compute non-stored з `factory3d.iot_sim.write_enabled` |

Методи (усі з `self.ensure_one()`):

- `get_panel()` (`@api.model`): повертає єдиний запис, створює при відсутності.
- `action_check()`: `self._sim_get("/status")` → `_apply_status(payload)`; при помилці — `state="offline"`, `last_error`. Повертає `ir.actions.client` `display_notification`.
- `_apply_status(payload)`: пише `state` (`online`, або `locked`, якщо `payload["enabled"] is False`, або `degraded`, якщо в `payload["protocols"]` є не `ok`), `last_contact=now`, `version`, `mode`, `factor`, `sim_time` (ISO → UTC), `uptime_s`, `seed`, `alarm_count`, `protocol_status`, `odoo_stale`; синхронізує `f3d.sim.run.state` за `payload["runs"]` (§7.2 API-10); оновлює `f3d.sim.device.state` за `payload["devices_fault"]` (список кодів у збої).
- `action_apply_factor()`: вимагає `write_enabled` (інакше `UserError("Команди на емулятор вимкнено стоп-краном factory3d.iot_sim.write_enabled")`); якщо `mode == "follow_odoo"` і `factor_new != 1` → `UserError("У режимі «За Odoo» прискорення фіксовано 1 (A-12)")`; `POST /time {"factor": factor_new}`; `message_post`.
- `action_apply_mode()`: `write_enabled`; `POST /mode {"mode": mode_new}`; після зміни на `follow_odoo` ставить `factor_new=1` і викликає `action_apply_factor()`.
- `action_reset()`: `write_enabled`; `POST /reset {"keep_time": true}`; закриває всі активні `f3d.sim.run` → `stopped`.
- `action_stop_all()`: `write_enabled`; `POST /stop-all`; `state="locked"`.
- `action_level0_force_on()` / `action_level0_force_off()` / `action_level0_auto()`: пишуть `level0_state` і негайно викликають `_sync_level0()`.
- `_sync_level0()`: вирішує активність крона `factory3d_iot_sim.cron_iot_sim`: `forced_on` → active True; `forced_off` → False; `auto_*`: якщо `state == "online"` → False і `level0_state="auto_off"`; якщо сервіс офлайн довше `factory3d.iot_sim.level0_after_min` хвилин і `factory3d.iot_sim.level0_enabled` → True і `auto_on`. Пише в чаттер лише при зміні.
- `_cron_poll_status()` (`@api.model`): якщо `read_enabled` і `url` заданий → `action_check()` (без сповіщення), потім `_sync_level0()`; якщо `read_enabled` False → нічого, крім `_sync_level0()` з припущенням «офлайн».
- `action_open_signals()`: act_window на `f3d.sim.signal`.
- `action_refresh_signals()`: `write_enabled` не потрібен (читання); `GET /signals` (пакетно, `?limit=1000&offset=`) → оновлює `f3d.sim.signal.last_value/last_status/last_ts` (`write` батчами по 200); не частіше ніж раз на 60 с (`last_signals_refresh` у `ir.config_parameter`), інакше `UserError("Оновлення сигналів — не частіше ніж раз на хвилину")`.

### 2.2 M-02 `f3d.sim.device` — пристрій емулятора

`_name = "f3d.sim.device"`, `_description = "Пристрій емулятора"`, `_order = "protocol, code"`, `_rec_name = "code"`, домішки `f3d.sim.client`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char | «Код сцени», required, index; SQL `device_code_uniq UNIQUE(code)` «Код пристрою має бути унікальним»; `_check_code`: regex `^[A-Z0-9][A-Z0-9\-\.]{0,31}$` |
| `name` | Char | «Назва», required |
| `equipment_id` | Many2one | `maintenance.equipment`, «Обладнання», ondelete `set null`, index |
| `workcenter_id` | Many2one | `mrp.workcenter`, «Робочий центр», ondelete `set null` |
| `zone_id` | Many2one | `f3d.zone`, «Зона», ondelete `set null` |
| `protocol` | Selection | «Протокол»: `P-01`…`P-13`, `none` (пасивне); required; default `none` |
| `driver` | Selection | «Драйвер»: `opcua_ww`, `modbus_pm5560`, `modbus_sun2000`, `modbus_luna2000`, `modbus_elektronikon`, `modbus_atys`, `modbus_tedom`, `modbus_adam6050`, `modbus_adam6060`, `modbus_adam6017`, `modbus_adam6015`, `bacnet_roofvent`, `bacnet_ahu`, `bacnet_fan`, `bacnet_boiler`, `bacnet_facp`, `helvarnet_router`, `mqtt_mobile`, `rest_woodstore`, `rest_biostar`, `http_lpr`, `sics_scale`, `genset_relay`, `passive`; required; default `passive` |
| `unit_id` | Integer | «Modbus unit id» (0 = н/д); `_check_unit`: 0…247; SQL `device_unit_uniq UNIQUE(unit_id) WHERE unit_id > 0` реалізовано як `_check_unit_unique` (пошук дублікатів) |
| `instance` | Integer | «BACnet device instance» (0 = н/д); унікальність як для `unit_id` |
| `address` | Char | «Адреса»: префікс NodeId / топік / `host:port` / адреса HelvarNet |
| `params` | Json | «Параметри» (наприклад `{"channels": {"run": 0, "fault": 1, "counter": 0}}`) |
| `enabled` | Boolean | «Увімкнено в емуляторі», default True |
| `state` | Selection | «Стан»: `unknown`, `ok`, `fault`, `offline`, `passive`; default `unknown`; readonly |
| `fault_reason` | Char | «Причина збою», readonly |
| `last_update` | Datetime | readonly |
| `signal_ids` | One2many | `f3d.sim.signal`, `device_id` |
| `signal_count` | Integer | compute |
| `note` | Text | «Примітка» |
| `role` | Char | related `equipment_id.f3d_role`, readonly |
| `model` | Char | related `equipment_id.f3d_model`, readonly |

Методи: `action_fault()` → відкриває M-10 з `default_device_id`; `action_clear()`: `write_enabled`; `POST /device/{code}/clear`; `state="ok"`, `fault_reason=False`; `message_post`. `_set_fault(reason, note)`: `write_enabled`; `POST /device/{code}/fault {"reason": reason, "note": note}`; `state="fault"`. `action_open_signals()`. `name_get` → `"{code} — {name}"`.

### 2.3 M-03 `f3d.sim.signal` — каталог сигналів

`_name = "f3d.sim.signal"`, `_description = "Сигнал емулятора (каталог)"`, `_order = "device_id, code"`, `_rec_name = "code"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char | «Код-шлях», required, index; SQL `signal_code_uniq UNIQUE(code)` «Код сигналу має бути унікальним»; regex `^[a-z_]+(/[A-Za-z0-9_\-\.]+)+$` |
| `name` | Char | «Назва» |
| `device_id` | Many2one | `f3d.sim.device`, required, ondelete `cascade` |
| `protocol` | Selection | як у M-02, required |
| `address` | Char | «Адреса в джерелі», required |
| `dtype` | Char | «Тип» (`F32`, `I64`, `U16`, `Boolean`, `enum`, `event`…) |
| `unit` | Char | «Одиниця» |
| `scale` | Char | «Масштаб» |
| `nominal` | Char | «Номінал (старт)» |
| `thresholds` | Char | «Пороги» |
| `model_rule` | Char | «Модель поведінки» (R-xx) |
| `origin` | Selection | `[("mock","Макет"),("new","Новий")]`, required |
| `level0_code` | Char | «Код сигналу рівня 0» (= `x_code`), index |
| `level0_value` | Float | compute non-stored: `x_f3d_signal.x_value` за `level0_code`, якщо модель `x_f3d_signal` є в реєстрі |
| `last_value` | Float | «Останнє значення (сервіс)», readonly |
| `last_status` | Selection | `ok`, `warn`, `alarm`, `stale`, readonly |
| `last_ts` | Datetime | readonly |
| `kind` | Selection | «Вид»: `gauge`, `counter`, `state`, `event`; required; default `gauge` |

Методи: `action_read_now()`: `GET /signals/{code}` → `last_*`. `@api.model _load_catalog(path)`: читає CSV (§5.1), `create`/`write` за `code` (ідемпотентно), прив'язує `device_id` за колонкою `device`; невідомий пристрій → `WARNING` у лог і створення пристрою `passive` з цим кодом (щоб каталог не губився).

### 2.4 M-04 `f3d.sim.scenario` — сценарій

`_name = "f3d.sim.scenario"`, `_description = "Сценарій емулятора"`, `_order = "sequence, code"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char | required, unique (SQL `scenario_code_uniq`), = ім'я в `/sim/v1/scenario/{name}` |
| `name` | Char | required (uk) |
| `description` | Html | що робить, що видно в 3D |
| `group` | Selection | `production`, `energy`, `logistics`, `safety`, `access`, `bms`; required |
| `params_schema` | Json | JSON-схема параметрів (копія §9.3) |
| `params_default` | Json | значення за замовчуванням |
| `duration_s` | Integer | 0 = до зупинки |
| `sequence` | Integer | default 10 |
| `active` | Boolean | default True |
| `run_ids` | One2many | `f3d.sim.run`, `scenario_id` |
| `last_run_id` | Many2one | compute |

Методи: `action_start()` → відкриває M-11 з `default_scenario_id`.

### 2.5 M-05 `f3d.sim.run` — запуск сценарію

`_name = "f3d.sim.run"`, `_description = "Запуск сценарію"`, `_order = "start_ts desc, id desc"`, домішки `f3d.sim.client`, `mail.thread`.

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | sequence `f3d.sim.run` (`RUN/%(year)s/0001`), readonly |
| `panel_id` | Many2one | `f3d.sim.panel`, default `get_panel()` |
| `scenario_id` | Many2one | `f3d.sim.scenario`, required, ondelete `restrict` |
| `params` | Json | фактичні параметри |
| `user_id` | Many2one | `res.users`, default поточний |
| `start_ts` | Datetime | default now |
| `stop_ts` | Datetime | |
| `state` | Selection | `queued`, `running`, `stopping`, `done`, `failed`, `stopped`; default `queued`; tracking |
| `sim_run_id` | Char | id запуску в сервісі (відповідь API-13) |
| `message` | Text | результат / помилка |
| `event_ids` | One2many | `f3d.sim.event`, `run_id` |
| `duration_s` | Integer | compute `stop_ts - start_ts` |

Методи: `action_stop()`: `write_enabled`; `POST /scenario/{code}/stop {"run_id": sim_run_id}`; `state="stopping"` (до підтвердження статусом) або `stopped`, якщо сервіс відповів `stopped`. `_create_and_start(scenario, params)` (`@api.model`): валідує `params` проти `params_schema` (jsonschema-lite: тип, enum, min/max — власна функція `_validate_params`), створює запис, `POST /scenario/{code}/start {"run_ref": name, "params": params}` → `sim_run_id`, `state="running"`; помилка → `state="failed"`, `message`.

### 2.6 M-06 `f3d.sim.event` — подія від емулятора

`_name = "f3d.sim.event"`, `_description = "Подія емулятора"`, `_order = "ts desc, id desc"`.

| Поле | Тип | Параметри |
|---|---|---|
| `ts` | Datetime | required, index |
| `kind` | Selection | `scenario`, `fault`, `alarm`, `info`, `error`, `command`; required |
| `device_code` | Char | index |
| `device_id` | Many2one | `f3d.sim.device`, compute stored за `device_code` |
| `run_id` | Many2one | `f3d.sim.run`, ondelete `set null` |
| `message` | Char | required |
| `payload` | Json | |

`_gc(days)` (`@api.model`): `unlink` подій старіших за `days`; крон C-02.

### 2.7 M-07 `maintenance.equipment` (розширення)

Додані поля: `f3d_sim_device_id` (Many2one `f3d.sim.device`, compute stored `_compute_f3d_sim_device` за `f3d_code` = `device.code`, readonly), `f3d_sim_state` (related `f3d_sim_device_id.state`), `f3d_sim_fault_reason` (related), `f3d_sim_protocol` (related). Методи: `action_f3d_sim_fault()` / `action_f3d_sim_clear()` — делегують у M-02. Без перевизначення `create/write`.

### 2.8 M-08 `mrp.workcenter` (розширення)

`f3d_sim_device_id` (Many2one, compute non-stored: пристрій, у якого `workcenter_id == self`), `f3d_sim_state` (related). Кнопка «Емулятор» відкриває пристрій.

### 2.9 M-09 `res.config.settings` (розширення)

| Поле | Тип | `config_parameter` |
|---|---|---|
| `f3d_sim_url` | Char «Адреса сервісу емулятора» | `factory3d.iot_sim.url` |
| `f3d_sim_token` | Char (widget password) «Токен /sim/v1» | `factory3d.iot_sim.token` |
| `f3d_sim_export_token` | Char (password) «Токен експорту (емулятор → Odoo)» | `factory3d.iot_sim.export_token` |
| `f3d_sim_read_enabled` | Boolean «Опитувати стан сервісу» | `factory3d.iot_sim.read_enabled` |
| `f3d_sim_write_enabled` | Boolean «Дозволити команди (сценарії, збої, час)» | `factory3d.iot_sim.write_enabled` |
| `f3d_sim_mode` | Selection «Режим за замовчуванням» | `factory3d.iot_sim.mode` |
| `f3d_sim_level0_enabled` | Boolean «Рівень 0 при офлайні» | `factory3d.iot_sim.level0_enabled` |
| `f3d_sim_level0_after_min` | Integer «Вмикати рівень 0 через, хв» | `factory3d.iot_sim.level0_after_min` |
| `f3d_sim_timeout_s` | Integer | `factory3d.iot_sim.timeout_s` |
| `f3d_sim_keep_days` | Integer | `factory3d.iot_sim.keep_days` |

Методи: `action_f3d_sim_generate_export_token()` — `secrets.token_hex(32)`; `action_f3d_sim_check()` — `panel.action_check()`. Читати/писати ці поля може лише `group_f3d_admin` (`groups` на полях).

### 2.10 Домішка `f3d.sim.client` (AbstractModel)

`_sim_url()`: `factory3d.iot_sim.url` без кінцевого `/` + `/sim/v1`; порожнє → `UserError("Адресу сервісу емулятора не налаштовано (Налаштування → Factory3D → Емулятор)")`.
`_sim_headers()`: `{"Authorization": "Bearer " + token, "Accept": "application/json"}`; токен ніколи не логуються.
`_sim_get(path, params=None)` / `_sim_post(path, json=None)`: `requests` з `timeout = factory3d.iot_sim.timeout_s`; `POST` вимагає `write_enabled` (інакше `UserError`), `GET` — `read_enabled`; відповіді: 2xx → `json()`, 401 → `UserError("Емулятор відхилив токен")`, 423 → `UserError("Емулятор заблоковано стоп-краном (SIM_ENABLED=0)")`, 404 → `UserError("Невідомий об'єкт: …")`, 422 → `UserError(detail)`, інше/мережа → `UserError("Сервіс емулятора недоступний: …")`. Усі виклики пишуть `f3d.sim.event(kind="command")` для POST (без токена в payload).

### 2.11 M-10 `f3d.sim.fault.wizard` (TransientModel)

Поля: `device_id` (required), `reason` Selection `[("generic","Загальний збій"),("spindle","Шпиндель/привід"),("emergency","Аварійна кнопка"),("power","Втрата живлення"),("comm","Втрата зв'язку"),("sensor","Датчик")]` default `generic`, `note` Char. `action_confirm()` → `device_id._set_fault(reason, note)`.

### 2.12 M-11 `f3d.sim.run.wizard` (TransientModel)

Поля: `scenario_id` (required), `params_text` Text (JSON, default = `params_default` сценарію, красиво відформатований), `device_id` Many2one `f3d.sim.device` (для сценаріїв із параметром `device`; domain із `params_schema.properties.device.enum`, якщо є), `zone_id` Many2one `f3d.zone` (для `fire_drill`). `action_confirm()`: збирає `params` (JSON + `device`/`zone` → code), `f3d.sim.run._create_and_start(...)`, повертає act_window на створений запуск.

---

## 3. Представлення й меню

| ID | XML-id | Тип | Модель | Структура |
|---|---|---|---|---|
| V-01 | `factory3d_iot_sim.view_f3d_sim_panel_form` | form | `f3d.sim.panel` | заголовок `name`; статусбар `state` (readonly); кнопки у `header`: «Перевірити зв'язок» (`action_check`, завжди), «Застосувати прискорення» (`action_apply_factor`, `invisible: not write_enabled`), «Застосувати режим» (`action_apply_mode`), «Скинути світ» (`action_reset`, confirm «Скинути стан емулятора до початкового?»), «Стоп-кран сервісу» (`action_stop_all`, `btn-danger`, confirm), «Рівень 0: увімкнути» / «вимкнути» / «авто»; `group` «Сервіс»: `version`, `last_contact`, `last_error`, `uptime_s`, `seed`, `odoo_stale`; `group` «Час і режим»: `mode`, `mode_new`, `factor`, `factor_new`, `sim_time`; `group` «Лічильники»: `device_count` (кнопка → пристрої), `signal_count` (кнопка `action_open_signals`), `alarm_count`, `level0_state`, `level0_signal_count`; `notebook`: «Активні запуски» (`active_run_ids`, list readonly з кнопкою «Зупинити»), «Протоколи» (`protocol_status` widget `json`), «Сценарії» (вбудований list `f3d.sim.scenario` з кнопкою «Запустити»); чаттер |
| V-02 | `view_f3d_sim_device_list` | list | `f3d.sim.device` | `code`, `name`, `protocol`, `driver`, `unit_id`, `instance`, `address`, `state` (decoration-danger `state=='fault'`, muted `passive`), `equipment_id`, `workcenter_id`, `signal_count`; `default_order="protocol, code"` |
| V-03 | `view_f3d_sim_device_form` | form | `f3d.sim.device` | header: «Збій» (`action_fault`, invisible `state=='fault' or not write_enabled`), «Скинути» (`action_clear`, invisible `state!='fault'`); статусбар `state`; group «Пристрій»: `code`, `name`, `equipment_id`, `workcenter_id`, `zone_id`, `role`, `model`; group «Протокол»: `protocol`, `driver`, `unit_id`, `instance`, `address`, `params` (json), `enabled`; group «Стан»: `fault_reason`, `last_update`; notebook «Сигнали» (`signal_ids` list: `code`, `address`, `dtype`, `unit`, `last_value`, `last_status`, `last_ts`); «Примітка» |
| V-04 | `view_f3d_sim_device_search` | search | `f3d.sim.device` | поля `code`, `name`, `address`; фільтри «У збої» (`state='fault'`), «Активні» (`enabled`), по протоколах P-01…P-12; групування за `protocol`, `driver`, `state` |
| V-05 | `view_f3d_sim_signal_list` | list | `f3d.sim.signal` | `code`, `device_id`, `protocol`, `address`, `dtype`, `unit`, `scale`, `nominal`, `thresholds`, `model_rule`, `origin`, `last_value`, `last_status` (decoration-danger `alarm`, warning `warn`, muted `stale`), `last_ts`; `create="false"`, `editable` ні |
| V-06 | `view_f3d_sim_signal_form` + `view_f3d_sim_signal_search` | form/search | `f3d.sim.signal` | усі поля readonly, кнопка «Прочитати зараз» (`action_read_now`); пошук за `code`, `device_id`, `address`; фільтри «Макет» / «Нові», «Тривога»; групування за `device_id`, `protocol`, `origin` |
| V-07 | `view_f3d_sim_scenario_list/form/kanban` | list, form, kanban | `f3d.sim.scenario` | list: `sequence` (handle), `code`, `name`, `group`, `duration_s`, `last_run_id`, кнопка «Запустити» (`action_start`, invisible `not write_enabled`); form: `code` (readonly після створення), `name`, `group`, `description`, `params_schema`, `params_default` (json), `duration_s`, `active`; notebook «Запуски» (`run_ids`); kanban — картки по `group` з кнопкою «Запустити» |
| V-08 | `view_f3d_sim_run_list/form/search` | list/form/search | `f3d.sim.run` | list: `name`, `scenario_id`, `state` (decoration), `user_id`, `start_ts`, `stop_ts`, `duration_s`, кнопка «Зупинити» (`action_stop`, invisible `state not in ('queued','running')`); form: header «Зупинити», статусбар; `params` (json readonly), `sim_run_id`, `message`; notebook «Події» (`event_ids`); чаттер; search: фільтри «Активні», «Невдалі», групування за `scenario_id`, `state`, `user_id` |
| V-09 | `view_f3d_sim_event_list/search` | list/search | `f3d.sim.event` | `ts`, `kind` (decoration-danger `error`/`alarm`, warning `fault`), `device_code`, `device_id`, `run_id`, `message`; `create="false" edit="false"`; search: `device_code`, `message`, фільтри за `kind`, «Сьогодні» |
| V-10 | `view_maintenance_equipment_form_f3d_sim` | form inherit `maintenance.hr_equipment_view_form` | `maintenance.equipment` | `xpath //notebook` → page «Емулятор» (`invisible: not f3d_sim_device_id`): `f3d_sim_device_id`, `f3d_sim_protocol`, `f3d_sim_state`, `f3d_sim_fault_reason`; кнопки «Збій»/«Скинути» (`groups="factory3d_base.group_f3d_manager"`); стоїть **після** успадкованої сторінки «Сигнали» (рівень 0) |
| V-11 | `res_config_settings_view_form_f3d_sim` | form inherit `base.res_config_settings_view_form` | `res.config.settings` | блок `app_settings_block` `data-string="Factory3D"` (створює `factory3d_base`; якщо відсутній — власний `data-key="factory3d_base"`), секція «Емулятор обладнання»: поля M-09, кнопки «Перевірити зв'язок», «Згенерувати токен експорту»; `groups="factory3d_base.group_f3d_admin"` |
| V-12 | `view_f3d_sim_fault_wizard_form`, `view_f3d_sim_run_wizard_form` | form (wizard) | M-10, M-11 | fault: `device_id` (readonly), `reason`, `note`, footer «Поставити збій»/«Скасувати»; run: `scenario_id` (readonly), `device_id` (invisible якщо схема без `device`), `zone_id` (invisible якщо без `zone`), `params_text` (widget `ace` mode json), footer «Запустити» |
| V-13 | `view_mrp_workcenter_form_f3d_sim` | form inherit `mrp.mrp_workcenter_view` | `mrp.workcenter` | у `button_box` кнопка-статистика «Емулятор» (`f3d_sim_state`), відкриває `f3d_sim_device_id` |

### 3.14 Меню й дії

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_f3d_sim_root` | Емулятор | `maintenance.menu_maintenance_title` | 6 | `group_f3d_user` | — |
| `menu_f3d_sim_panel` | Пульт | `menu_f3d_sim_root` | 1 | `group_f3d_user` | `action_f3d_sim_panel` (`ir.actions.server`, код: `action = env['f3d.sim.panel'].get_panel().get_formview_action()`) |
| `menu_f3d_sim_scenarios` | Сценарії | root | 2 | `group_f3d_user` | `action_f3d_sim_scenario` (kanban,list,form) |
| `menu_f3d_sim_runs` | Запуски | root | 3 | `group_f3d_user` | `action_f3d_sim_run` (list,form) |
| `menu_f3d_sim_devices` | Пристрої | root | 4 | `group_f3d_user` | `action_f3d_sim_device` (list,form), context `search_default_group_protocol` |
| `menu_f3d_sim_signals` | Каталог сигналів | root | 5 | `group_f3d_user` | `action_f3d_sim_signal` (list,form) |
| `menu_f3d_sim_events` | Події | root | 6 | `group_f3d_user` | `action_f3d_sim_event` (list) |
| `menu_iot_root` (успадковане) | Рівень 0 (без сервісу) | **перенесено** під `menu_f3d_sim_root` | 9 | `group_f3d_admin` | — (дочірні «Сигнали обладнання», «Журнал показань», «Оновити зараз», «Увімкнути/Зупинити імітацію» лишаються) |
| `menu_f3d_sim_settings` | Налаштування емулятора | root | 10 | `group_f3d_admin` | `action_f3d_sim_settings` (`res.config.settings`, context `module=factory3d_iot_sim`) |

---

## 4. Права

### 4.1 `security/ir.model.access.csv`

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_f3d_sim_panel_user,f3d.sim.panel user,model_f3d_sim_panel,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_sim_panel_manager,f3d.sim.panel manager,model_f3d_sim_panel,factory3d_base.group_f3d_manager,1,1,0,0
access_f3d_sim_panel_admin,f3d.sim.panel admin,model_f3d_sim_panel,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_sim_device_user,f3d.sim.device user,model_f3d_sim_device,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_sim_device_manager,f3d.sim.device manager,model_f3d_sim_device,factory3d_base.group_f3d_manager,1,1,0,0
access_f3d_sim_device_admin,f3d.sim.device admin,model_f3d_sim_device,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_sim_signal_user,f3d.sim.signal user,model_f3d_sim_signal,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_sim_signal_manager,f3d.sim.signal manager,model_f3d_sim_signal,factory3d_base.group_f3d_manager,1,1,0,0
access_f3d_sim_signal_admin,f3d.sim.signal admin,model_f3d_sim_signal,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_sim_scenario_user,f3d.sim.scenario user,model_f3d_sim_scenario,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_sim_scenario_manager,f3d.sim.scenario manager,model_f3d_sim_scenario,factory3d_base.group_f3d_manager,1,1,1,0
access_f3d_sim_scenario_admin,f3d.sim.scenario admin,model_f3d_sim_scenario,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_sim_run_user,f3d.sim.run user,model_f3d_sim_run,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_sim_run_manager,f3d.sim.run manager,model_f3d_sim_run,factory3d_base.group_f3d_manager,1,1,1,0
access_f3d_sim_run_admin,f3d.sim.run admin,model_f3d_sim_run,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_sim_event_user,f3d.sim.event user,model_f3d_sim_event,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_sim_event_admin,f3d.sim.event admin,model_f3d_sim_event,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_sim_fault_wizard,f3d.sim.fault.wizard,model_f3d_sim_fault_wizard,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_sim_run_wizard,f3d.sim.run.wizard,model_f3d_sim_run_wizard,factory3d_base.group_f3d_manager,1,1,1,1
```

Успадковані рядки `access_x_f3d_signal_user`, `access_x_f3d_reading_user` (`base.group_user`, повні права) лишаються в `data/models.xml` без змін до міграції телеметрією (A-09).

### 4.2 Правила записів

Немає (одна компанія в демо; модель не мультикомпанійна). `f3d.sim.event` створюється контролером API-03 через `sudo()` після перевірки токена.

### 4.3 Групи

Власних груп модуль не створює; використовує `factory3d_base.group_f3d_user` ⊂ `group_f3d_manager` ⊂ `group_f3d_admin` (⊂ `base.group_system`). Поля токенів у M-09 — `groups="factory3d_base.group_f3d_admin"`.

### 4.4 `neutralize.sql`

```sql
UPDATE ir_cron SET active = false WHERE id IN (
  SELECT res_id FROM ir_model_data WHERE module = 'factory3d_iot_sim' AND model = 'ir.cron');
UPDATE ir_config_parameter SET value = 'False' WHERE key IN
  ('factory3d.iot_sim.read_enabled', 'factory3d.iot_sim.write_enabled', 'factory3d.iot_sim.level0_enabled');
UPDATE ir_config_parameter SET value = '' WHERE key IN
  ('factory3d.iot_sim.url', 'factory3d.iot_sim.token', 'factory3d.iot_sim.export_token');
UPDATE f3d_sim_panel SET state = 'unconfigured', level0_state = 'forced_off';
```

---

## 5. Дані

### 5.1 Файли `data/`

| Файл | Що створює | Джерело | xml-id | Ідемпотентність |
|---|---|---|---|---|
| `models.xml`, `actions.xml`, `views/views.xml` | рівень 0 (без змін) | data-модуль 19.0.1.0.0 | `factory3d_iot_sim.model_x_f3d_signal`, …, `cron_iot_sim`, `menu_iot_root`… | повторне завантаження не змінює значень полів (`ir.model.fields` без `noupdate`, але значення сигналів — у записах, яких data не торкається) |
| `level0.xml` | `cron_iot_sim`: `name` → «Емулятор IoT: рівень 0 (без сервісу)»; `menu_iot_root`: `parent_id` → `menu_f3d_sim_root`, `name` → «Рівень 0 (без сервісу)», `sequence` 9, `groups_id` → `group_f3d_admin` | — | ті самі xml-id (оновлення) | так |
| `ir_config_parameter.xml` | 10 параметрів §3 ARCHITECTURE з `noupdate="1"`: `url=""`, `token=""`, `export_token=""`, `read_enabled=True`, `write_enabled=False`, `mode=follow_odoo`, `level0_enabled=True`, `level0_after_min=5`, `timeout_s=5`, `keep_days=14` | — | `param_f3d_iot_sim_<key>` | `noupdate` |
| `ir_sequence.xml` | `f3d.sim.run`: prefix `RUN/%(year)s/`, padding 4 | — | `seq_f3d_sim_run` | `noupdate` |
| `ir_cron.xml` | C-01, C-02 (§6) | — | `cron_f3d_sim_status`, `cron_f3d_sim_gc` | так |
| `f3d_sim_scenario.xml` | 15 сценаріїв S-01…S-15 (§9.3) з `code`, `name`, `group`, `params_schema`, `params_default`, `duration_s` | §9.3 | `scenario_<code>` | `noupdate="0"` (схеми можуть оновлюватись) |
| `f3d_sim_signal.csv` | 662 рядки каталогу; колонки: `code,name,device,protocol,address,dtype,unit,scale,nominal,thresholds,model_rule,origin,level0_code,kind` | Додаток A (`tools/gen_catalog.py`) | — (завантажує hook, ключ `code`) | upsert за `code` |

### 5.2 Таблиця «роль паспорта → протокол/драйвер» (для `post_init_hook`)

| `f3d_role` (base) / код | protocol | driver | unit_id / instance / address |
|---|---|---|---|
| `beam_saw`, `beam_saw_book`, `nesting_cnc`, `edgebander_laser`, `edgebander`, `ptp_cnc`, `throughfeed_drilling`, `dowel_inserting`, `sorting_cell`, `case_clamp_auto` (15 РЦ HOMAG) | P-01 | `opcua_ww` | address `ns=2;s=<code>` |
| `board_storage` (GANTRY-1) | P-03 | `rest_woodstore` | address `http://iot-sim:8082/api/v1`; також OPC UA `ns=2;s=GANTRY-1` |
| `sliding_table_saw`, `vertical_panel_saw`, `wide_belt_sander`, `membrane_press`, `glue_spray_booth`, `manual_spray_booth`, `automatic_spraying`, `drying`, `uv_line`, `hinge_insertion`, `box_machine`, `stretch_wrapper`, `shrink_line`, `case_clamp_manual` (20 РЦ) | P-02 | `modbus_adam6050` | unit 80–83, params `{"di_run": n, "di_fault": n+1, "counter": n}` за §8.4.2 |
| `power_meter`, `acb` (Q1, Q2), `main_switchboard` з `power_meter` у складі (QF-1..4, QF-C1, QF-C2), споживачі-верстати й інженерія (лічильник на відгалуженні) | P-05 | `modbus_pm5560` | unit за §8.4.1 (окремий пристрій `<code>-PM` на кожен лічильник споживача, 49 шт.) |
| `forklift`, `board_forklift`, `tugger` (FL-1..5, FL-C1, FL-C2, TUGGER-1; `FL-6` = `FL-2` паспорт плит — у демо FL-6 без сигналів, пасивний) | P-06 | `mqtt_mobile` | address `f3d/mobile/<code>` |
| `compressor` | P-07 | `modbus_elektronikon` | unit 70 |
| `dust_extraction` | P-07 | `modbus_adam6017` (u90) + `modbus_adam6050` (u84) | params `{"ai_airflow":0,"ai_dp":1,"di_run":0,"di_fault":1}` |
| `biomass_boiler` (+ `briquetting_press` у складі) | P-08 | `bacnet_boiler` | instance 140 |
| `pv_inverter` (PV-INV → 8 пристроїв `PV-INV-1..8`), `pv_module` (PV-ROOF — пасивний) | P-07 | `modbus_sun2000` | unit 61–68 |
| `bess` | P-07 | `modbus_luna2000` | unit 69 |
| `chp` | P-07 | `modbus_tedom` | unit 72 |
| `ats` | P-07 | `modbus_atys` | unit 71 |
| `transformer` (T1, T2) | P-07 | `modbus_adam6015` | unit 96, params `{"rtd": [0,1,2]}` / `[3,4,5]` |
| `SPRINKLERS`, `AIR-RING` (equipment без ролі) | P-07 | `modbus_adam6017` | unit 90, params `{"ai": 2}` / `{"ai": 3}` |
| `water_meter` | P-07 | `modbus_adam6050` | unit 84, params `{"counter": 8}` |
| `roofvent` (RV-01..25) | P-08 | `bacnet_roofvent` | instance 101…125 |
| `make_up_ahu` (AHU-1) | P-08 | `bacnet_ahu` | 130 |
| `wall_fan`, `ex_fan` (EF-ELEC, EF-CMP, EF-CHG) | P-08 | `bacnet_fan` | 131, 132, 133 |
| `lighting_control` (LP-1..3) | P-08 | `helvarnet_router` | address `@1.1`, `@1.2`, `@1.3` |
| `highbay`, `highbay_rack` (LT-*) | P-08 | `passive` (група DALI; сигнали — на LP) | params `{"group": n, "router": "@1.x"}` |
| `facp` (FACP-1) | P-09 | `bacnet_facp` | instance 200 |
| `smoke_detector`, `multi_detector`, `heat_detector` (FA-*), `mcp`, `sounder_beacon`, `flame_detector` | P-09 | `passive` (об'єкти всередині FACP-1) | params `{"lsz": n}` |
| `spark_detection` (SPARK-1) | P-09 | `modbus_adam6050` | unit 85, params `{"di_spark":0,"di_ext":1,"di_fault":2}` |
| `smoke_control` (SMOKE-CTRL), `smoke_vent` (SMOKE-VENTS — пасивний) | P-09 | `modbus_adam6050` | unit 85, params `{"di_open":4,"di_fault":5,"do_open":0}` |
| `access_reader` (ACCESS → 5 пристроїв `ACR-IN`, `ACR-ELEC`, `ACR-CHG`, `ACR-PAINT`, `ACR-SRV`), `turnstile` (TURNSTILES → `TURN-1`) | P-10 | `rest_biostar` | params `{"biostar_device_id": 5390001…}` |
| `barrier` (GATE-W, GATE-E) | P-11 | `modbus_adam6060` | unit 86, params `{"di_open":0,"di_loop":1,"do_open":0}` / `{2,3,1}` |
| `cctv_camera` (CCTV → `CAM-05`, `CAM-06` активні LPR; решта 10 — пасивні) | P-11 | `http_lpr` | address `SIM_LPR_PUSH_URL`, params `{"gate": "GATE-W"}` |
| `truck_scale` | P-11 | `sics_scale` | address `iot-sim:4001` |
| `genset` | P-12 | `genset_relay` | address з `relay_api.md` |
| усе інше (`iot_box`, `label_printer`, `scale`, `shopfloor_tablet`, `handheld_scanner`, `wifi_ap`, `server_rack`, `substation`, `busbar_dist`, `pfc`, `emergency`, `exit_door`, `lightning_air`, `eyewash`, `board_rack`, `highbay_rack`, `nvr`, …) | P-13/`none` | `passive` | — |

### 5.3 `post_init_hook` (кроки, очікувані кількості на копії демо-бази)

0. `migrations/19.0.2.0.0/pre-migrate.py`: якщо в `ir_module_module` версія `19.0.1.0.0` — записати в лог «upgrade from data module»; перевірити, що `ir_model` з `model='x_f3d_signal'` існує, інакше лише WARNING (свіжа база без рівня 0 допустима).
1. Створити `f3d.sim.panel` (1).
2. Для кожного `maintenance.equipment` з `f3d_code` (після `factory3d_base` — 208): створити/оновити `f3d.sim.device` за таблицею §5.2 (ключ `code = f3d_code`); для `ACCESS`, `CCTV`, `PV-INV` створити похідні пристрої (`ACR-*` ×5, `TURN-1`, `CAM-05/06`, `PV-INV-1..8`), для лічильників споживачів — `<code>-PM` (49) з `equipment_id` того самого обладнання. Очікувано: 208 + 5 + 1 + 2 + 8 + 49 = **273** пристроїв, з них `passive` ≈ 100 (стелажі, світильники-групи, сповіщувачі-групи, ІТ, принтери, ваги Odoo IoT, двері…).
3. Завантажити `data/f3d_sim_signal.csv` → `f3d.sim.signal` (**662**), прив'язка `device_id` за колонкою `device` (пристрої з кроку 2; для `energy/consumers/<X>/*` — пристрій `<X>-PM`; для `energy/cells/Q1` — `Q1`; для `energy/lines/BW-1` — `QF-1`); очікувано 0 рядків без пристрою.
4. Для `origin=mock` (196): `level0_code = code`; перевірити наявність `x_f3d_signal` з таким `x_code` — очікувано 196/196; невідповідності → WARNING зі списком.
5. Сценарії — з data (15).
6. Крон рівня 0: не чіпати (стан вирішить перший прогін C-01).
7. `ir.config_parameter`: якщо `factory3d.iot_sim.url` порожній — `state="unconfigured"` у пульті.

Повторний запуск hook (reinstall/upgrade) не створює дублікатів (ключі `code`).

`uninstall_hook`: `ir.cron` модуля → `active=False` (рівень 0 теж), `ir.config_parameter factory3d.iot_sim.*` → видалити, `f3d.sim.run`/`f3d.sim.event` — видалити (A-11). Моделі `f3d.sim.*` видаляються Odoo разом із модулем; `x_*` лишаються (їх data-файли належать модулю, тож Odoo **видалить** і їх при повній деінсталяції — це задокументоване застереження: деінсталяцію до міграції телеметрією робити лише на копії; `uninstall_hook` пише WARNING у лог і в чаттер пульта перед видаленням).

---

## 6. Крони й фонові процеси

| ID | xml-id | Назва | Інтервал | Метод | Що робить за прогін | Ліміти |
|---|---|---|---|---|---|---|
| C-01 | `cron_f3d_sim_status` | Емулятор: опитати стан сервісу | 1 хв | `f3d.sim.panel._cron_poll_status` | 1 × `GET /sim/v1/status` (якщо `read_enabled` і `url`), `_apply_status`, `_sync_level0` | таймаут `timeout_s`; помилка → `state=offline`, не кидає виняток |
| C-02 | `cron_f3d_sim_gc` | Емулятор: ротація подій | 1 доба 03:10 | `f3d.sim.event._gc(keep_days)` | `unlink` подій старіших за `factory3d.iot_sim.keep_days` | батчами по 5 000 |
| рівень 0 | `cron_iot_sim` (успадкований) | Емулятор IoT: рівень 0 (без сервісу) | 1 хв | `action_iot_tick` (без змін) | 196 сигналів за старими формулами, показання раз на 10 хв, ротація 2 доби, заявки ТО | `active` керується C-01/пультом |

У сервісі фонові таски (asyncio): `clock` (1 с), `world.tick` (1 с), `snapshot` (60 с), `odoo.follow` (10 с / 60 с), `devices_client.refresh` (1 год), `events_push` (API-03, 10 с або 100 подій), `mqtt_publisher` (1–5 с), `lpr_push` (за подією), протокольні сервери — постійно.

---

## 7. HTTP/JSON API

### 7.1 Odoo-контролери (модуль пульта), `controllers/sim_api.py`

Спільне: `type="http"`, `auth="public"`, `csrf=False`, перевірка `Authorization: Bearer <factory3d.iot_sim.export_token>` (порожній токен у налаштуваннях = API вимкнено → 503 `{"error":"export token not configured"}`); порівняння `hmac.compare_digest`; усі відповіді `application/json; charset=utf-8`; помилки `{"error": "<код>", "detail": "<текст>"}`; 401 при невірному токені; `sudo()` після перевірки.

#### API-01 `GET /f3d/sim/devices`

Параметри запиту: `?protocol=P-05` (фільтр), `?since=<ETag>` не підтримується; заголовок `If-None-Match: "<etag>"` → 304. `ETag` = sha256 від `write_date` max по `f3d.sim.device`, `f3d.sim.signal`, `f3d.zone`, `stock.picking.batch`, `hr.employee` + кількості.

Відповідь 200 (JSON-схема, скорочено; повні обов'язкові поля позначено `*`):

```json
{
  "version": 1,
  "generated_at": "2026-10-13T20:05:11+03:00",
  "odoo": {"db": "odoo", "company": "Меблева фабрика (демо)", "tz": "Europe/Kyiv", "base_url": "https://…"},
  "devices": [
    {
      "code": "SAW-1", "name": "Розкрій 1", "kind": "workcenter", "role": "beam_saw",
      "protocol": "P-01", "driver": "opcua_ww", "unit_id": 0, "instance": 0, "address": "ns=2;s=SAW-1",
      "params": {}, "enabled": true,
      "equipment": {"id": 101, "manufacturer": "HOMAG", "model": "SAWTEQ S-310 …", "serial": "SAW-1", "power_kw": 11.0, "units": 1},
      "workcenter": {"code": "SAW-1", "name": "Розкрій 1", "id": 12},
      "zone": {"code": "Z-CUT", "name": "Розкрій"},
      "signals": [
        {"code": "workcenters/SAW-1/state", "address": "ns=2;s=SAW-1.State.Machine.Overview.CurrentState",
         "dtype": "WwUnitStateEnumeration", "unit": "", "scale": "", "nominal": "READY", "thresholds": "ERROR → заявка",
         "model_rule": "R-14", "kind": "state"}
      ]
    }
  ],
  "zones": [{"code": "Z-CUT", "name": "Розкрій", "type": "production", "polygon": [[44.0, 9.0], [62.0, 9.0], [62.0, 46.0], [44.0, 46.0]]}],
  "docks": [{"code": "DOCK-W1", "side": "west", "no": 1, "accepts": ["sheets"], "location_id": 16, "x": 0.0, "y": 8.0}],
  "shifts": [{"name": "Зміна 1 (07:00–15:30)", "tz": "Europe/Kyiv",
              "attendances": [{"weekday": 0, "from": "07:00", "to": "11:30"}, {"weekday": 0, "from": "12:00", "to": "15:30"}]}],
  "employees": [{"code": "OP-SAW-1", "name": "Олег Мельник", "barcode": "OPSAW1", "job": "Оператор", "workcenter": "SAW-1", "shift": "Зміна 1 (07:00–15:30)"}],
  "bookings": [{"batch": "BATCH/IN/00001", "truck": "TRUCK-IN-1", "plate": null, "dock": "DOCK-W1", "type": "incoming",
                "scheduled": "2026-10-12T06:30:00Z", "state": "in_progress", "pickings": ["WH/IN/00128"], "partner": "Плитсервіс (демо)"}]
}
```

Обов'язкові: `version*`, `generated_at*`, `devices[]*` з `code*`, `name*`, `protocol*`, `driver*`, `enabled*`, `signals[]*` (можливо порожній) з `code*`, `address*`, `dtype*`, `kind*`; `zones[]*` (`code*`, `polygon*` ≥ 3 точок; береться з `f3d.zone` base; якщо полігонів у base ще немає — порожній список, емулятор бере `catalog/zones.json`); `docks[]*`; `shifts[]*` (з `resource.calendar` компанії); `employees[]*` (усі `hr.employee` з `barcode`); `bookings[]*` (`stock.picking.batch` у станах `draft/in_progress` з `dock_id`, `scheduled_date` ± 2 доби).

Коди: 200, 304, 401, 503. Ідемпотентно; ліміт — без пагінації (≈ 273 пристрої × ~3 сигнали ≈ 400 КБ).

#### API-02 `GET /f3d/sim/health`

Без токена. 200 `{"ok": true, "module": "factory3d_iot_sim", "version": "19.0.2.0.0", "devices": 273, "signals": 662, "panel_state": "online"}`.

#### API-03 `POST /f3d/sim/events`

Тіло: `{"events": [{"ts": "2026-10-13T20:05:11+03:00", "kind": "scenario|fault|alarm|info|error", "device": "RV-05", "run_ref": "RUN/2026/0007", "sim_run_id": "r-01J…", "message": "Фільтр RV-05: 285 Па", "payload": {}}]}` (≤ 100 подій, ≤ 256 КБ). Дія: створити `f3d.sim.event` (прив'язка `run_id` за `run_ref` або `sim_run_id`); події `kind=scenario` з `payload.state in (done, failed, stopped)` переводять `f3d.sim.run.state`. Відповідь 200 `{"accepted": n, "rejected": [{"index": i, "reason": "…"}]}`; 400 при невалідному JSON; 413 при перевищенні; 401. Ідемпотентність: за `payload.event_id` (UUID від сервісу) — дублікати відкидаються з `reason="duplicate"`.

### 7.2 REST керування емулятором `/sim/v1/*` (сервіс, порт 8090, FastAPI)

Спільне: `Authorization: Bearer <SIM_API_TOKEN>` для всього, крім `GET /health`, `GET /metrics`, `POST /lpr-sink`; помилки — `{"detail": "..."}` з кодами 401 (токен), 403 (`write`-операція при `SIM_READONLY_API=1`), 404 (код не знайдено), 409 (конфлікт стану: сценарій уже запущено на тому ж пристрої), 422 (валідація pydantic), 423 (`SIM_ENABLED=0` / `stop-all`), 500. Усі часи — ISO 8601 з зоною `+03:00`/`+02:00` (`sim_now`). Коди пристроїв/сигналів — regex §2.6 ARCHITECTURE.

| ID | Метод і шлях | Тіло запиту | Відповідь 200 | Примітки |
|---|---|---|---|---|
| API-10 | `GET /status` | — | `{"enabled": true, "version": "0.1.0", "mode": "follow_odoo", "factor": 1.0, "sim_now": "…", "real_now": "…", "uptime_s": 3600, "seed": 20261012, "tick_ms": 1000, "devices": 273, "signals": 662, "alarms": 1, "devices_fault": ["CNC-2"], "runs": [{"id": "r-01J…", "run_ref": "RUN/2026/0007", "scenario": "filter_clogged", "state": "running", "started": "…", "params": {…}}], "protocols": {"opcua": "ok", "modbus": "ok", "bacnet": "ok", "mqtt": "ok", "helvarnet": "ok", "biostar": "ok", "woodstore": "ok", "jobs": "ok", "sics": "ok", "lpr": "ok", "control": "ok"}, "odoo": {"configured": true, "last_ok": "…", "stale": false, "catalog_source": "odoo"}, "catalog_hash": "sha256:…"}` | без токенів |
| API-11 | `GET /devices`, `GET /devices/{code}` | — | список/об'єкт: `{"code", "name", "protocol", "driver", "unit_id", "instance", "address", "enabled", "state": "ok|fault|offline|passive", "fault": {"reason", "note", "since"} \| null, "model": "machine", "signals": ["…"], "extra": {…стан моделі…}}` | `?protocol=`, `?state=` |
| API-12 | `POST /device/{code}/fault` / `POST /device/{code}/clear` | `{"reason": "generic|spindle|emergency|power|comm|sensor", "note": "…"}` / `{}` | `{"code": "CNC-2", "state": "fault"}` / `{"state": "ok"}` | `fault` на `passive` → 422; повторний `fault` → 200 без змін |
| API-13 | `GET /scenarios`; `POST /scenario/{name}/start`; `POST /scenario/{name}/stop`; `GET /runs`, `GET /runs/{id}` | start: `{"run_ref": "RUN/2026/0007", "params": {…}}`; stop: `{"run_id": "r-…"}` (без `run_id` — усі запуски цього сценарію) | start 201 `{"id": "r-01J…", "scenario", "state": "running", "started", "ends": "…|null"}`; stop `{"id", "state": "stopped"}`; runs: список об'єктів як у `status.runs` + `"events": n`, `"result": {…}` | `GET /scenarios` → `[{"name", "title_uk", "group", "params_schema", "params_default", "duration_s"}]` (= §9.3) |
| API-14 | `POST /time` | `{"factor": 10.0}` і/або `{"set": "2026-10-12T07:00:00+03:00"}` | `{"factor": 10.0, "sim_now": "…"}` | `factor` 0,1…60; у `follow_odoo` `factor != 1` → 409; `set` переставляє годинник (кроком, без «розмотування» лічильників) |
| API-15 | `POST /mode` | `{"mode": "scenario|follow_odoo"}` | `{"mode": "…", "factor": 1.0}` | перехід у `follow_odoo` ставить `factor=1`; без налаштованого Odoo → 422 |
| API-16 | `GET /signals`; `GET /signals/{code}`; `PUT /signals/{code}` | PUT: `{"value": 285.0, "hold_s": 600}` або `{"release": true}` | `GET /signals`: `{"count": 662, "items": [{"code", "value", "unit", "status": "ok|warn|alarm|stale", "ts", "device", "protocol", "kind"}]}` з `?prefix=`, `?device=`, `?status=`, `?limit=1000&offset=0`; PUT → `{"code", "value", "held_until"}` | PUT — «утримати значення» для тестів споживачів; `hold_s` ≤ 86 400; після закінчення модель знову веде значення |
| API-17 | `POST /reset`; `POST /stop-all`; `POST /resume` | reset: `{"keep_time": true, "seed": 20261012}` | `{"ok": true, "sim_now": "…"}` | `reset` зупиняє всі запуски, відновлює початковий стан каталогу (номінали), не чіпає конфіг; `stop-all` = стоп-кран (значення заморожуються, 423 на команди), `resume` знімає |
| API-18 | `GET /health`; `GET /metrics` | — | health: `{"status": "ok|degraded|locked", "protocols": {…}, "uptime_s"}`; metrics: Prometheus text (`iot_sim_signal_value{code=…}`, `iot_sim_tick_seconds`, `iot_sim_protocol_up{proto=…}`, `iot_sim_events_total{kind=…}`) | без токена, лише з мережі `f3d_sim` |
| API-19 | `GET /events` | — | `{"items": [{"id": "e-…", "ts", "kind", "device", "run_id", "message", "payload"}], "next": "e-…"}` з `?since=<id>`, `?kind=`, `?device=`, `?limit=500` | кільцевий буфер 10 000 |
| — | `POST /lpr-sink` | JSON Axis (§8.13.2) | `{"received": true}` | заглушка приймача LPR для фази 1; складає у `events` як `kind=info, device=CAM-xx` |
| — | `GET /catalog/signals.csv`, `GET /catalog/devices.json` | — | файли каталогу (для `factory3d_telemetry` і тестів) | токен |

Приклад запуску сценарію:

```http
POST /sim/v1/scenario/filter_clogged/start HTTP/1.1
Authorization: Bearer 3f1c…
Content-Type: application/json

{"run_ref": "RUN/2026/0007", "params": {"device": "RV-05", "dp_pa": 285, "ramp_min": 2}}

HTTP/1.1 201 Created
{"id": "r-01JA7Z3K9Q", "scenario": "filter_clogged", "state": "running", "started": "2026-10-13T20:10:00+03:00", "ends": null}
```

### 7.3 Вендорські REST-інтерфейси емулятора

Описані в §8: woodStore **API-20…API-27** (§8.5), `/jobs` **API-30…API-34** (§8.6), BioStar 2 **API-40…API-46** (§8.12).

<!-- PART2 -->

---

## 8. Сервісна частина `services/iot_sim`

### 8.1 Пакет, залежності, порти, compose

#### 8.1.1 Запуск

`python -m iot_sim run` (або entry point `iot-sim run`) — один процес asyncio: створює `World`, завантажує каталог (`registry`), стартує протокольні сервери (кожен — `ProtocolServer` з `start()/stop()/health()`), фонові таски §6, REST керування. `iot-sim check-config` — перевіряє env і каталоги, виходить 0/1. `iot-sim dump-catalog` — друкує `signals.csv` з адресами (для звірки з Додатком A).

#### 8.1.2 Залежності (`requirements.txt`, Python 3.12; мінімальні перевірені версії, закріпити «==» при першому збиранні)

| Пакет | Версія | Для чого |
|---|---|---|
| `asyncua` | 1.1.6 | OPC UA сервер (P-01, P-03) |
| `pymodbus` | 3.9.2 | Modbus TCP сервер (P-02, P-05, P-07, P-09, P-11) |
| `bacpypes3` | 0.0.102 | BACnet/IP (P-08, P-09) |
| `paho-mqtt` | 2.1.0 | MQTT-публікація (P-06) |
| `fastapi` | 0.115.12 | REST: `/sim/v1`, woodStore, `/jobs`, BioStar 2 |
| `uvicorn[standard]` | 0.34.2 | ASGI (кілька інстансів на різних портах в одному циклі) |
| `httpx` | 0.28.1 | клієнт API-01/API-03, LPR push |
| `pydantic`, `pydantic-settings` | 2.11.x / 2.9.x | схеми, конфіг |
| `astral` | 3.2 | висота сонця (Київ) |
| `PyYAML` | 6.0.2 | `devices.yaml` |
| `cryptography` | 44.x | самопідписані сертифікати (OPC UA, BioStar TLS) |
| `prometheus-client` | 0.21.x | `/metrics` |
| `pytest`, `pytest-asyncio`, `pytest-timeout` | 8.3.x / 0.25.x / 2.3.x | тести |

Жодних `requests` (лише `httpx`), жодних Modbus/OPC UA/BACnet **клієнтів** у коді сервісу (тести використовують клієнти з тих самих бібліотек у `tests/`).

#### 8.1.3 Порти й адреси (contract для колектора і тестів)

| Протокол | Транспорт | Порт | Сервіс/примітка |
|---|---|---|---|
| OPC UA (P-01, P-03) | TCP | 4840 | endpoint `opc.tcp://iot-sim:4840/f3d/` |
| Modbus TCP (P-02, P-05, P-07, P-09, P-11) | TCP | 502 | unit id за §8.4.1 |
| BACnet/IP (P-08, P-09) | UDP | 47808 (0xBAC0) | роутер + віртуальна мережа 2 (A-04) |
| HelvarNet (P-08) | TCP / UDP | 50000 / 50001 | 3 роутери за одним IP, адреси `@1.1`, `@1.2`, `@1.3` |
| MQTT (P-06) | TCP | 1883 (контейнер `mosquitto`) | емулятор — клієнт-публікатор `iot_sim`, колектор — підписник `collector` |
| BioStar 2 (P-10) | HTTPS / HTTP | 8443 / 8081 | HTTP — лише для тестів (A-07) |
| woodStore API v1 (P-03) | HTTP | 8082 | `X-Api-Key` |
| `/jobs` (P-04) | HTTP | 8083 | `X-Api-Key` |
| SICS (P-11) | TCP | 4001 | ASCII, CRLF |
| LPR push (P-11) | HTTP клієнт | → `SIM_LPR_PUSH_URL` | заглушка `/sim/v1/lpr-sink` |
| REST керування | HTTP | 8090 | `/sim/v1/*` |
| SmartGen relay (P-12) | за `relay_api.md` | контейнер `genset_relay` | з `td_genset` |

#### 8.1.4 `docker-compose.sim.yml` (істотне)

```yaml
networks:
  f3d_sim: {internal: true}
  odoo_default: {external: true}
services:
  iot_sim:
    build: ./services/iot_sim
    profiles: ["demo", "dev"]
    networks: [f3d_sim, odoo_default]      # odoo_default — лише для API-01/follow_odoo (allow-list)
    env_file: ./services/iot_sim/.env      # SIM_* (§8.2.1); у репозиторії — .env.example без секретів
    volumes: ["iot_sim_state:/app/state"]
    ports: ["127.0.0.1:8090:8090", "127.0.0.1:4840:4840"]   # лише профіль dev; у demo — без ports
    healthcheck: {test: ["CMD", "curl", "-fsS", "http://localhost:8090/sim/v1/health"], interval: 30s, timeout: 5s, retries: 3}
    depends_on: [mosquitto]
    cap_drop: [ALL]
    read_only: true
    tmpfs: ["/tmp"]
    user: "10001:10001"
  mosquitto:
    image: eclipse-mosquitto:2.0.20
    profiles: ["demo", "dev"]
    networks: [f3d_sim]
    volumes: ["./services/iot_sim/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro", "./services/iot_sim/mosquitto/passwd:/mosquitto/config/passwd:ro"]
  genset_relay:
    build: ${TD_GENSET_PATH}/relay          # з репозиторію td_genset, профіль D700 (fake_relay.py)
    profiles: ["demo", "dev"]
    networks: [f3d_sim]
volumes: {iot_sim_state: {}}
```

Порт 502 і 47808 усередині контейнера — непривілейовані завдяки `CAP_NET_BIND_SERVICE`? Ні: контейнер без capabilities; тому процес слухає 1502/47808 **усередині**, а compose публікує в мережу `f3d_sim` як 502 через `ports` не можна (internal). Рішення: `sysctl net.ipv4.ip_unprivileged_port_start=0` для контейнера `iot_sim` (compose `sysctls`), сервіс слухає 502 напряму. Тест ТБ-01 перевіряє, що на хості порти не опубліковані в профілі `demo`.

### 8.2 Конфігурація, ядро, стан-машини

#### 8.2.1 Змінні середовища (`config.py`, префікс `SIM_`)

| Змінна | Тип / default | Призначення |
|---|---|---|
| `SIM_ENABLED` | bool / `1` | стоп-кран: `0` — сервери живі, значення заморожені, команди → 423 |
| `SIM_API_TOKEN` | str / **обов'язково** (≥ 32 симв., інакше вихід з кодом 2) | Bearer для `/sim/v1` |
| `SIM_READONLY_API` | bool / `0` | `1` — усі POST/PUT `/sim/v1` → 403 (прод-демо без керування) |
| `SIM_MODE` | `scenario` \| `follow_odoo` / `scenario` | режим при старті |
| `SIM_FACTOR` | float / `1.0` | прискорення при старті |
| `SIM_SEED` | int / `20261012` | зерно детермінованого шуму |
| `SIM_TZ` | str / `Europe/Kyiv` | годинник |
| `SIM_START_AT` | ISO / порожньо | якщо задано — початковий `sim_now` (інакше реальний час) |
| `SIM_SUN_MODEL` | `astral` \| `parabola` / `astral` | R-11 |
| `SIM_TICK_MS` | int / `1000` | крок ядра (реальний час) |
| `SIM_CATALOG_SOURCE` | `odoo` \| `local` / `odoo` | звідки реєстр пристроїв (`odoo` → API-01 з fallback на `local`) |
| `SIM_CATALOG_DIR` | path / `./catalog` | локальні файли |
| `SIM_STATE_DIR` | path / `./state` | знімок |
| `SIM_SNAPSHOT_S` | int / `60` | період знімка; `0` — вимкнено |
| `SIM_RESTORE_SNAPSHOT` | bool / `1` | відновлювати стан після рестарту |
| `SIM_LEVEL0_SYNC` | bool / `1` | при старті в режимі з Odoo читати `x_f3d_signal.x_value` як стартові значення 196 сигналів макета |
| `SIM_ODOO_URL`, `SIM_ODOO_DB`, `SIM_ODOO_USER`, `SIM_ODOO_APIKEY` | str / порожньо | XML-RPC (follow_odoo, API-01 через HTTP) |
| `SIM_ODOO_EXPORT_TOKEN` | str / порожньо | Bearer для API-01/API-03 |
| `SIM_ODOO_FOLLOW_S`, `SIM_ODOO_FOLLOW_SLOW_S` | int / `10`, `60` | періоди follow_odoo |
| `SIM_ODOO_STALE_S` | int / `120` | після скількох секунд без успішного читання прапор `odoo_stale` |
| `SIM_MQTT_URL` | `mqtt://user:pass@mosquitto:1883` | брокер |
| `SIM_MQTT_PREFIX` | str / `f3d` | префікс топіків |
| `SIM_LPR_PUSH_URL` | URL / `http://127.0.0.1:8090/sim/v1/lpr-sink` | приймач подій LPR |
| `SIM_ALLOW_OUTBOUND` | CSV хостів / `mosquitto,odoo19,collector,genset_relay,127.0.0.1` | allow-list вихідних з'єднань (перевірка hostname перед кожним connect) |
| `SIM_GENSET_RELAY_URL` | URL / `http://genset_relay:8000` | P-12 |
| `SIM_BIOSTAR_USER`, `SIM_BIOSTAR_PASS` | str / `admin`, **обов'язково** | логін емулятора BioStar 2 |
| `SIM_WOODSTORE_APIKEY`, `SIM_JOBS_APIKEY` | str / **обов'язково** | ключі P-03/P-04 |
| `SIM_OPCUA_CERT_DIR` | path / `./certs` | сертифікати (генеруються при старті, якщо немає) |
| `SIM_OPCUA_USER`, `SIM_OPCUA_PASS` | str / `collector`, **обов'язково** | користувач для методів OPC UA |
| `SIM_PORT_*` | int | перевизначення портів §8.1.3 (`SIM_PORT_OPCUA=4840` …) |
| `SIM_YARD_AUTOGATE` | bool / `1` | шлагбаум відкривається сам для фури з бронюванням (інакше чекає DO від споживача) |
| `SIM_LOG_LEVEL`, `SIM_LOG_JSON` | `INFO`, `1` | логування |

#### 8.2.2 Годинник і шум

- `SimClock`: `real_t0`, `sim_t0`, `factor`; `now() = sim_t0 + (real_now − real_t0)·factor` (tz-aware, `SIM_TZ`); `set(dt)` переставляє `sim_t0`; `set_factor(f)` фіксує поточний `now()` як нову точку відліку. Тік ядра — кожні `SIM_TICK_MS` реального часу, `dt_sim = tick·factor`, обмежений зверху 10 с (при `factor=60` і тіку 1 с — 6 підкроків по 10 с). Усі моделі отримують `tick(dt_s)` у sim-секундах.
- Сонце: `astral.LocationInfo("Kyiv", "Ukraine", "Europe/Kyiv", 50.45, 30.52)`, `elevation(sim_now)`.
- **R-00 детермінований шум**: `r = Rng(seed, code).next()` ∈ [−1, 1): LCG `s = (s·1103515245 + 12345) mod 2³¹`, `r = s/2³⁰ − 1`, початкове `s = fnv1a32(code) ⊕ seed` — та сама послідовність, що в макеті (`x_seed`, `det()`), тож юніт-тести можуть звіряти ряди з `action_iot_tick`.

#### 8.2.3 Ядро

- `Signal`: `code`, `device`, `protocol`, `address`, `dtype`, `unit`, `kind`, `value`, `status` (`ok|warn|alarm|stale`), `ts`, `held_until`, `params` (nominal, noise, rate, limit, alarm, threshold, source, nominal_src…). `set(value, ts)` — єдина точка запису; якщо `held_until > now` — ігнорує модель.
- `Device`: `code`, `driver`, `protocol`, `unit_id`, `instance`, `address`, `params`, `model: Model`, `state`, `fault`.
- `Model.tick(dt)`: порядок у тіку: (1) `World` оновлює зміну/завдання/фури/людей (планувальник), (2) моделі-джерела (machines, io_machines, gantry, mobile, roofvent, lighting, compressor, dust, boiler, pv, chp, water, facp, spark, smoke, access, yard), (3) моделі-агрегати (meter, transformer, ats, bess) — бо залежать від (2), (4) `World.balance()` (R-13), (5) пороги → `status`, події, (6) протокольні сервери читають `Signal.value` (push: OPC UA DataChange, BACnet COV, MQTT publish, HelvarNet push).
- `World`: `mode`, `shift` (календар), `workcenters[code]` (job, state, pieces), `jobs` (черга з Odoo або планувальника), `trucks`, `people`, `maintenance_closed` (множина кодів пристроїв/сигналів, по яких у Odoo закрито заявку — з follow або з API-01/рівня 0), `balance`, `events: EventBus`, `runs`.
- Знімок: JSON усіх `Signal.value/ts/status/held_until`, стани моделей (`to_dict()`), `World` (завдання, фури, черги), `clock` (`sim_now`), активні запуски. Відновлення при старті, якщо `SIM_RESTORE_SNAPSHOT=1` і знімок не старіший за 24 год реального часу; інакше — старт від каталогу (`nominal`) або від `x_value` (`SIM_LEVEL0_SYNC`).

#### 8.2.4 Події (`events.py`)

`Event {id: "e-<ulid>", ts, kind: scenario|fault|alarm|info|error|command|access|yard|fire, device, run_id, message (uk), payload}`. Кожна подія йде в: кільцевий буфер (API-19), лог (JSON), API-03 (пакетно, якщо Odoo налаштовано), і в протокол, де це передбачено (OPC UA event, BACnet COV/LSZ, BioStar лог, MQTT). Повідомлення — українською, з показником і порогом, як вимагає §6.8 каркаса («Фільтр RV-05: перепад тиску 285 Па при нормі до 250»).

### 8.3 Додаток P-01 — OPC UA (верстати HOMAG і портал)

**Еталон:** OPC 40550-1 «OPC UA for Woodworking Machines — Part 1: Vertical Interface», v1.02.0 (2025-06-01), namespace `http://opcfoundation.org/UA/Woodworking/` — https://reference.opcfoundation.org/Woodworking/v100/docs/ (переглянуто 13.10.2026); OPC 40001-1 «Machinery — Part 1: Basic Building Blocks» (`MachineIdentificationType`, тека `Machines`); OPC 40001-3 «Machinery — Part 3: Job Management» v1.0.1 (`http://opcfoundation.org/UA/Machinery/Jobs/`), на основі OPC 10031-4 (ISA-95 Job Control). Імена вузлів нижче — з тексту стандарту (§7.1–7.18); частина JobManagement, якої не вдалося прочитати на сайті (методи `ISA95JobOrderReceiverObjectType`), позначена «ПРИПУЩЕННЯ — звірити з OPC 10031-4».

#### 8.3.1 Сервер

- Endpoint `opc.tcp://iot-sim:4840/f3d/`; `ApplicationUri = urn:todo.ltd:f3d:iot_sim`; security policies: `None/None` (анонімне читання, підписки) і `Basic256Sha256/SignAndEncrypt` (сертифікат самопідписаний, `certs/`); користувач `SIM_OPCUA_USER` потрібен для виклику методів `JobOrderControl.*`. Анонімний запис у змінні заборонений (усі `State.*` — `AccessLevel=CurrentRead`).
- Простори імен (індекси фіксовані емулятором; клієнт має резолвити за URI): `0` UA, `1` `urn:todo.ltd:f3d:iot_sim`, `2` `http://todo.ltd/f3d/iot_sim/instances/` (екземпляри; **усі NodeId нижче — `ns=2;s=…`**), `3` `http://opcfoundation.org/UA/DI/`, `4` `http://opcfoundation.org/UA/Machinery/`, `5` `http://opcfoundation.org/UA/Machinery/Jobs/`, `6` `http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/`, `7` `http://opcfoundation.org/UA/Woodworking/`. Nodeset-файли стандартів завантажуються з пакета (`iot_sim/protocols/nodesets/*.xml`).
- Структура: `Objects → 4:Machines (FolderType)` → 16 об'єктів типу `7:WwMachineType`: `SAW-1`, `SAW-2`, `SAW-3`, `NEST-1`, `EDGE-1`, `EDGE-2`, `EDGE-3`, `CNC-1`, `CNC-2`, `CNC-3`, `CNC-4`, `BORE-1`, `DOWEL-1`, `SORT-1`, `ASMLINE-1`, `GANTRY-1` (портал — стан по P-01, стоси/завдання — по P-03).
- Оновлення змінних — кожен тік (1 с sim); `SourceTimestamp = sim_now`; `StatusCode = Good`; при збої `comm` (сценарій/`fault reason=comm`) змінні отримують `Bad_CommunicationError` і `CurrentState=OFFLINE`.

#### 8.3.2 Адресний простір об'єкта верстата (`<C>` = код)

| BrowsePath від `Machines/<C>` | NodeId | Тип даних | Доступ | Значення в емуляторі |
|---|---|---|---|---|
| `3:Identification` | `ns=2;s=<C>.Identification` | `3:MachineIdentificationType` | — | |
| `…/Manufacturer` | `<C>.Identification.Manufacturer` | LocalizedText | R | `"HOMAG"` |
| `…/Model` | `<C>.Identification.Model` | LocalizedText | R | з паспорта (`SAWTEQ S-310 …`) |
| `…/ProductInstanceUri` | `<C>.Identification.ProductInstanceUri` | String | R | `urn:homag:<model>:<serial>` |
| `…/SerialNumber` | `<C>.Identification.SerialNumber` | String | R | `= <C>` (як `serial_no` в Odoo) |
| `…/DeviceClass` | `<C>.Identification.DeviceClass` | String | R | `"PanelSaw"`, `"NestingMachine"`, `"EdgeBander"`, `"CNCMachiningCenter"`, `"ThroughfeedDrilling"`, `"DowelInserting"`, `"SortingCell"`, `"CaseClamp"`, `"StorageSystem"` |
| `…/YearOfConstruction` | `<C>.Identification.YearOfConstruction` | UInt16 | R | 2024 |
| `…/SoftwareRevision`, `HardwareRevision`, `ProductCode`, `AssetId`, `ComponentName`, `Location` | … | String/LocalizedText | R (AssetId, ComponentName, Location — RW) | `AssetId = <C>` (= `f3d_code`), `Location = "<zone code>"` |
| `State` | `<C>.State` | BaseObjectType (`IWwStateType`) | — | |
| `State/Machine` | `<C>.State.Machine` | (`IWwBaseStateType`) | — | |
| `State/Machine/Overview/CurrentState` | `<C>.State.Machine.Overview.CurrentState` | `7:WwUnitStateEnumeration` | R | `OFFLINE=0, STANDBY=1, READY=2, WORKING=3, ERROR=4` за R-14 |
| `State/Machine/Overview/CurrentMode` | `<C>.State.Machine.Overview.CurrentMode` | `7:WwUnitModeEnumeration` | R | `OTHER=0, AUTOMATIC=1, SEMIAUTOMATIC=2, MANUAL=3, SETUP=4, SLEEP=5`; емулятор: `AUTOMATIC` у роботі, `SETUP` під час простою «Налагодження», `SLEEP` поза зміною, `MANUAL` для ASM-/SLIDE-типів |
| `State/Machine/Flags/<Flag>` | `<C>.State.Machine.Flags.<Flag>` | Boolean | R | обов'язкові (M): `MachineOn`, `MachineInitialized`, `PowerPresent`, `Emergency`, `Calibrated`, `Error`, `Alarm`, `Warning`, `RecipeInRun`; опційні, які емулятор теж публікує: `AirPresent`, `DustChipSuction`, `Safety`, `Remote`, `WorkpiecePresent`, `Moving`, `Hold`, `RecipeInSetup`, `RecipeInHold`, `ManualActivityRequired`, `LoadingEnabled`, `WaitUnload`, `WaitLoad`, `EnergySaving`, `ExternalEmergency`, `MaintenanceRequired`, `FeedRuns` (лише EDGE-*, BORE-1, ASMLINE-1) — значення за R-14/R-15 |
| `State/Machine/Values/<Value>` | `<C>.State.Machine.Values.<Value>` | за стандартом | R | `AbsoluteMachineOnTime`, `RelativeMachineOnTime`, `AbsoluteProductionTime`, `RelativeProductionTime`, `AbsoluteWorkingTime`, `RelativeWorkingTime`, `AbsoluteStandbyTime`, `RelativeStandbyTime`, `AbsoluteReadyTime`, `RelativeReadyTime`, `AbsoluteErrorTime`, `RelativeErrorTime`, `AbsolutePowerPresentTime`, `RelativePowerPresentTime`, `AbsoluteMachineOffTime` (UInt64, секунди); `AbsolutePiecesIn/Out`, `RelativePiecesIn/Out`, `AbsoluteRunsGood/Total/Aborted`, `RelativeRunsGood/Total/Aborted` (UInt64); `AbsoluteLength`, `RelativeLength` (UInt64, мм — EDGE-*); `FeedSpeed` (Double, м/хв — EDGE-*, BORE-1), `ActualCycle` (Double, с), `AxisOverride`, `SpindleOverride` (UInt32, %, 100). «Relative» обнуляються на початку зміни (R-16) |
| `State/SubUnits/<SubUnit>` | `<C>.State.SubUnits.<Name>` | `IWwBaseStateType` | R | EDGE-1: `Robot` (KUKA повернення), `LaserUnit`; SORT-1: `Robot`, `Racks`; ASMLINE-1: `Clamp`; інші — без SubUnits |
| `Events` | `<C>.Events` | `7:WwEventsDispatcherType`, `EventNotifier=SubscribeToEvents` | — | джерело подій §8.3.3 |
| `5:JobManagement` | `<C>.JobManagement` | `5:JobManagementType` | — | лише для 15 верстатів (не для GANTRY-1) |
| `JobManagement/JobOrderControl` | `<C>.JobManagement.JobOrderControl` | `6:ISA95JobOrderReceiverObjectType` | — | |
| `…/JobOrderControl/JobOrderList` | `<C>.JobManagement.JobOrderControl.JobOrderList` | `ISA95JobOrderAndStateDataType[]` | R | черга завдань: `JobOrder.JobOrderID` (= `mrp.workorder.id` як рядок або `WO00013`), `Description` (назва операції), `WorkMasterID` (= маршрут/специфікація), `StartTime`, `EndTime`, `Priority`, `JobOrderParameters` (`PlannedOrderQuantity`, `OrderNumbers=[WH/MO/00231]`, `JobName`), `State` — `6:ISA95StateDataType` з `BrowsePath` до стану |
| `…/JobOrderControl/{Store, StoreAndStart, Start, Update, Stop, Cancel, Clear, Pause, Resume, Abort, RevokeStart}` | `<C>.JobManagement.JobOrderControl.<Method>` | Method | виклик з логіном | ПРИПУЩЕННЯ (OPC 10031-4): вхід `JobOrder: ISA95JobOrderDataType` (Store/StoreAndStart/Update) або `JobOrderID: String` + `Comment: LocalizedText[]`; вихід `ReturnStatus: UInt64` (0 = ok). У режимі `follow_odoo` виклики приймаються, але завдання веде Odoo (`ReturnStatus=0`, подія INFORMATION «ignored in follow_odoo») |
| `JobManagement/JobOrderResults` | `<C>.JobManagement.JobOrderResults` | `6:ISA95JobResponseProviderObjectType` | — | `JobOrderResponseList: ISA95JobResponseDataType[]` (`JobOrderID`, `JobResponseID`, `StartTime`, `EndTime`, `JobState`, `JobResponseData`: `RunsCompleted`, `GoodQuantity`, `ActualProductionTime`); методи `RequestJobResponseByJobOrderID(JobOrderID) → JobResponse`, `RequestJobResponseByJobOrderState(JobOrderStateList[]) → JobResponses[]` |
| `ManufacturerSpecific` | `<C>.ManufacturerSpecific` | FolderType | R | `PowerActive` (Double, кВт — дзеркало PM5560), `SpindleRpm` (CNC/NEST), `VacuumKpa` (GANTRY-1), `CyclesToday` (GANTRY-1) |

Стани ISA-95 завдання (`State[].StateText`, ПРИПУЩЕННЯ за OPC 10031-4): `NotAllowedToStart`, `AllowedToStart`, `Running`, `Interrupted` (під-стани `Held`, `Suspended`), `Ended` (`Completed`, `Cancelled`), `Aborted`. Відповідність Odoo: `pending/waiting → NotAllowedToStart`, `ready → AllowedToStart`, `progress → Running`, `progress + blocked → Interrupted/Held`, `done → Ended/Completed`, `cancel → Ended/Cancelled`.

#### 8.3.3 Події

Типи: `7:WwBaseEventType` (підтип `0:BaseEventType`) і `7:WwAlarmConditionType` (підтип `0:AlarmConditionType`, з `ActiveState`, `AckedState`, `EnabledState`), обидва з інтерфейсом `IWwEventMessageType`: `EventCategory` (`WwEventCategoryEnumeration`: `OTHER=0, DIAGNOSTIC=1, INFORMATION=2, WARNING=3, ALARM=4, ERROR=5`), `MessageId` (String, напр. `"E0421"`), `MessageName` (String, `"SpindleOverload"`), `PathParts` (String[], `["SAW-1", "Saw", "MainSpindle"]`), `Group` (String, `"Drive"`), `LocalizedMessages` (LocalizedText[], uk/en), `Arguments` (`WwMessageArgumentDataType[]`). Стандартні поля події: `SourceNode = <C>.Events`, `SourceName = <C>`, `Time = sim_now`, `Severity` (INFORMATION 200, WARNING 500, ALARM 800, ERROR 1000), `Message` = перше з `LocalizedMessages`.

Каталог повідомлень емулятора (`MessageId` → категорія → текст uk): `I0001 INFORMATION «Завдання {job} запущено»`, `I0002 «Завдання {job} завершено, деталей {n}»`, `I0003 «Зміна розпочата»`, `W0101 WARNING «Низький тиск повітря: {bar} бар»`, `W0102 «Потрібне ТО через {h} мотогодин»`, `A0201 ALARM «Аварійна зупинка (кнопка {n})»`, `A0202 «Втрата зв'язку з приводом осі {axis}»`, `E0421 ERROR «Помилка шпинделя осі Z»` (= MR/00031 у демо для CNC-2), `E0430 «Втрата живлення»`, `E0440 «Відкрито огородження»`. Збій `fault reason=spindle` → `E0421` (ALARM-condition активна до `clear`), `emergency` → `A0201` + `Flags.Emergency`, `power` → `E0430` + `PowerPresent=False` → `CurrentState=ERROR`, `comm` → `OFFLINE`.

#### 8.3.4 Приклад читання (asyncua)

```python
async with Client("opc.tcp://iot-sim:4840/f3d/") as c:
    ns = await c.get_namespace_index("http://todo.ltd/f3d/iot_sim/instances/")
    state = await c.get_node(f"ns={ns};s=SAW-1.State.Machine.Overview.CurrentState").read_value()   # 3 == WORKING
    pieces = await c.get_node(f"ns={ns};s=SAW-1.State.Machine.Values.RelativePiecesOut").read_value()
```

### 8.4 Modbus TCP — спільне, карта unit id, Додаток P-02 (I/O-модулі верстатів)

#### 8.4.1 Спільне

- Один сервер, порт 502, Modbus TCP (MBAP, protocol id 0), функції: 01 Read Coils, 02 Read Discrete Inputs, 03 Read Holding Registers, 04 Read Input Registers (дзеркало 03), 05 Write Single Coil, 06 Write Single Register, 15, 16. Невідомий unit → виняток 0x0B (Gateway Target Device Failed to Respond); невідома адреса → 0x02 (Illegal Data Address); запис у R-регістр → 0x02.
- Адресація в документі — **1-based «40001»-нотація** для holding (HR) і «00001» для coils/DI (як у документах вендорів); на дроті PDU-адреса = номер − 40001 (або − 1). Порядок байтів: big-endian; 32/64-бітні — старше слово першим (PM5560, Huawei, ADAM — усі так).
- Таблиця unit id (A-03):

| unit id | Пристрій | Карта |
|---|---|---|
| 1, 2 | PM5560 на вводах Q1 (T1), Q2 (T2) | §8.7 |
| 3–8 | PM5560 на фідерах QF-1, QF-2, QF-3, QF-4, QF-C1, QF-C2 | §8.7 |
| 11–59 | PM5560 споживачів у порядку `energy.consumers` макета: 11 SAW-1, 12 SAW-2, 13 SAW-3, 14 SLIDE-1, 15 VSAW-1, 16 NEST-1, 17 EDGE-1, 18 EDGE-2, 19 EDGE-3, 20 CNC-3, 21 CNC-1, 22 CNC-2, 23 BORE-1, 24 CNC-4, 25 DOWEL-1, 26 SORT-1, 27 SAND-1, 28 AUTOSPRAY-1, 29 UV-1, 30 HINGE-1, 31 GLUE-1, 32 PRESS-1, 33 SPRAY-1, 34 DRY-1, 35 ASMLINE-1, 36 ASM-1, 37 ASM-2, 38 ASM-3, 39 ASM-4, 40 ASM-5, 41 ASM-6, 42 PACK-1, 43 PACK-2, 44 BOX-1, 45 PACKLINE-1, 46 GANTRY-1, 47 COMPRESSOR, 48 DUST-1, 49 BOILER, 50 CHARGING, 51 OFFICE, 52 LP-1, 53 LP-2, 54 LP-3, 55 RV-ALL, 56 AHU-1, 57 EF-ELEC, 58 EF-CMP, 59 EF-CHG | §8.7 |
| 61–68 | Huawei SUN2000-115KTL-M2 PV-INV-1 … PV-INV-8 | §8.9.1 |
| 69 | Huawei LUNA2000 (BESS) | §8.9.2 |
| 70 | Atlas Copco Elektronikon Mk5 (COMPRESSOR) | §8.9.3 |
| 71 | Socomec ATyS p (ATS-1) | §8.9.4 |
| 72 | TEDOM Quanto D800 (CHP) | §8.9.5 |
| 80–83 | ADAM-6050 IO-1…IO-4 (верстати P-02) | §8.4.2 |
| 84 | ADAM-6050 IO-5: DUST-1 (DI0 run, DI1 fault), WATER (DI8 імпульси) | §8.9.6 |
| 85 | ADAM-6050 IO-6: SPARK-1 (DI0–DI2), SMOKE-CTRL (DI4, DI5, DO0) | §8.11.3 |
| 86 | ADAM-6060 IO-7: GATE-W (DI0, DI1, DO0), GATE-E (DI2, DI3, DO1) | §8.13.1 |
| 90 | ADAM-6017 AI-1: DUST-1 витрата (AI0), перепад (AI1), SPRINKLERS (AI2), AIR-RING (AI3) | §8.9.6 |
| 96 | ADAM-6015 RTD-1: T1 (RTD0–2), T2 (RTD3–5) | §8.9.6 |

У проді кожен пристрій має свою IP-адресу (`f3d.source.address = host:502`, unit 1 або адреса RS-485 за шлюзом); каталог сигналів лишається тим самим — змінюється лише `source`.

#### 8.4.2 Додаток P-02 — ADAM-6050 для верстатів без інтерфейсу

**Еталон:** Advantech «ADAM-6000 Series User Manual», Ed. 12 (листопад 2022), Appendix B.2 «ADAM-6000 I/O Modbus Mapping Tables» — https://advdownload.advantech.com/productfile/Downloadfile4/1-2B6FKTG/ADAM-6000_User_Manaul_Ed.12-FINAL.pdf (переглянуто 13.10.2026). Карта модуля ADAM-6050 (12 DI, 6 DO, лічильники 32 біт на кожному DI):

| Адреса | Функція | Опис | R/W |
|---|---|---|---|
| 00001–00012 | 01/02 | DI value, канали 0–11 (1 = замкнено/активно) | R |
| 00017–00022 | 01/05 | DO value, канали 0–5 | R/W |
| 00033 + 4·k | 01/05 | Counter start (1)/stop (0) каналу k (k = 0…11) | R/W |
| 00034 + 4·k | 05 | Clear counter (1) | W |
| 00035 + 4·k | 01/05 | Clear overflow | R/W |
| 00036 + 4·k | 01/05 | DI latch status | R/W |
| 40001 + 2·k … 40002 + 2·k | 03 | Counter/Frequency value каналу k, 32 біт (низьке слово — перший регістр, за ADAM) | R |
| 40301 | 03 | DI value всі канали (біти 0–11) | R |
| 40303 | 03/06 | DO value всі канали (біти 0–5) | R/W |
| 40211–40212 | 03 | Module name (`0x6050`) | R |

Розкладка верстатів (кожен верстат: `DI(2m)` = «в роботі» (сухий контакт реле «цикл/подача»), `DI(2m+1)` = «аварія» (контакт реле несправності), лічильник на `DI(2m)` = цикли/деталі; `m` = порядок у модулі 0…4):

| unit | модуль | m=0 | m=1 | m=2 | m=3 | m=4 |
|---|---|---|---|---|---|---|
| 80 | IO-1 | SLIDE-1 (DI0/1, cnt 40001) | VSAW-1 (DI2/3, 40005) | SAND-1 (DI4/5, 40009) | PRESS-1 (DI6/7, 40013) | GLUE-1 (DI8/9, 40017) |
| 81 | IO-2 | SPRAY-1 | AUTOSPRAY-1 | DRY-1 | UV-1 | HINGE-1 |
| 82 | IO-3 | BOX-1 | PACK-1 | PACK-2 | PACKLINE-1 | ASM-1 |
| 83 | IO-4 | ASM-2 | ASM-3 | ASM-4 | ASM-5 | ASM-6 |

DI10/DI11 кожного модуля — резерв (0). DO0–DO5 — резерв (запис приймається, без ефекту, логується). Поведінка: `DI(run)=1` ⇔ `CurrentState=WORKING` за R-14; `DI(fault)=1` ⇔ збій (R-15); лічильник += 1 на кожну деталь/цикл (R-16); `Clear counter` обнуляє. Модуль відповідає на `40211 = 0x6050`.

### 8.5 Додаток P-03 — «woodStore API v1» (портал STORETEQ P-500)

**ПРИПУЩЕННЯ, звірити з HOMAG** (інтерфейс woodStore закритий; Q-02). Контракт наш; клієнт — `factory3d_machine_connect` (плагін `woodstore`). Базова адреса `http://iot-sim:8082/api/v1`, заголовок `X-Api-Key: <SIM_WOODSTORE_APIKEY>`, JSON UTF-8, часи ISO 8601. Помилки: `{"error": {"code": "NOT_FOUND|CONFLICT|VALIDATION|LOCKED", "message": "…"}}`.

| ID | Метод і шлях | Запит | Відповідь | Примітки |
|---|---|---|---|---|
| API-20 | `GET /status` | — | `{"state": "idle|moving|picking|placing|blocked|error", "position": {"x": 36.2, "y": 27.5, "z": 4.8}, "vacuum_kpa": -71.9, "cycles_today": 373, "cycles_total": 184210, "hours": 11240.5, "current_job": "wj-00412" \| null, "aisles": [{"no": 1, "gate_open": false}, …9], "alarms": [], "ts": "…"}` | `blocked` — прохід відкрито (ворота зі світловою завісою), портал не заходить (README макета) |
| API-21 | `GET /stacks` | `?product=DSP16-SON`, `?row=3` | `[{"id": "PLT-04C", "row": 4, "col": 3, "product": "DSP16-SON", "lot": "DSP16-SON-2610-114", "qty": 38, "max": 60, "reserved": 10, "locked": false, "updated": "…"}, …]` (23 стоси з ненульовим `qty` у демо + порожні місця) | `id` = код комірки `PLT-xx` = `stock.location.barcode` |
| API-22 | `GET /stacks/{id}` | — | об'єкт як вище | 404 |
| API-23 | `PATCH /stacks/{id}` | `{"qty": 35, "product": "DSP16-SON", "lot": "…", "reason": "odoo_inventory"}` | 200 об'єкт | коригування з Odoo (після інвентаризації/поповнення WH/INT); у емуляторі — повна заміна |
| API-24 | `GET /jobs` | `?state=queued|active|done|cancelled|error`, `?since=` | `[{"id": "wj-00412", "type": "feed|restack|return|count", "source": "PLT-04C", "target": "SAW-1", "sheets": 12, "done": 7, "product": "DSP16-SON", "lot": "…", "priority": 5, "external_ref": "WH/MO/00231", "state": "active", "created": "…", "started": "…", "finished": null}]` | |
| API-25 | `POST /jobs` | `{"type": "feed", "source": "PLT-04C" \| null (авто за product/lot), "target": "SAW-1|SAW-2|SAW-3|NEST-1", "sheets": 12, "product": "DSP16-SON", "lot": null, "priority": 5, "external_ref": "WH/MO/00231"}` | 201 об'єкт `state="queued"` | 409, якщо `sheets > qty` доступних; `feed` зменшує `qty` стосу на кожен покладений лист (R-18) |
| API-26 | `GET /jobs/{id}`; `DELETE /jobs/{id}` | — | об'єкт / `{"id", "state": "cancelled"}` | DELETE активного → завершити поточний лист і скасувати |
| API-27 | `GET /events` | `?since=<id>` | `[{"id", "ts", "type": "job_started|job_finished|sheet_placed|stack_empty|aisle_opened|aisle_closed|alarm|stack_updated", "job": "…", "stack": "…", "target": "…", "message": "…"}]` | кільце 2 000 |

Стартові дані — `dist/odoo_demo.json → locations["PLT-*"]` (product, lot, qty, capacity 60). Режим `follow_odoo`: емулятор сам створює `feed`-завдання для РЦ `SAW-*/NEST-1`, у яких є завдання в роботі (1 лист на `per_unit` хвилин, R-18); у `scenario` — за планувальником.

### 8.6 Додаток P-04 — файловий обмін картами розкрою `/jobs`

**ПРИПУЩЕННЯ** для формату списку деталей (intelliDivide імпорт — звірити з HOMAG); MPR — відкритий текстовий формат woodWOP (генерується мінімальний валідний файл). Базова адреса `http://iot-sim:8083`, `X-Api-Key: <SIM_JOBS_APIKEY>`.

| ID | Метод і шлях | Запит | Відповідь |
|---|---|---|---|
| API-30 | `POST /jobs` | `multipart/form-data`: `parts` (CSV, §8.6.1), `material` (`DSP16-SON`), `sheet` (`2800x2070x16`), `external_ref` (`WH/MO/00231`), `machine` (`SAW-1`) — або JSON `{"parts": [{…}], …}` | 202 `{"job_id": "cj-00077", "state": "optimizing", "eta_s": 5}` |
| API-31 | `GET /jobs/{id}` | — | `{"job_id", "state": "optimizing|planned|released|running|done|error", "external_ref", "machine", "material", "parts": 48, "plan": {"sheets": 7, "waste_pct": 11.4, "cut_length_m": 182.6, "est_min": 31}, "created", "updated", "error": null}` |
| API-32 | `GET /jobs/{id}/plan` | — | `{"sheets": [{"no": 1, "product": "DSP16-SON", "parts": [{"id": "P001", "x": 0, "y": 0, "w": 600, "h": 400, "rot": 0}], "waste_pct": 9.8, "cuts": [{"dir": "x", "pos": 600, "from": 0, "to": 2070}]}], "total_sheets": 7, "waste_pct": 11.4}` |
| API-33 | `POST /jobs/{id}/release` | `{"machine": "SAW-1", "priority": 5}` | 200 `{"job_id", "state": "released", "job_order_id": "cj-00077"}` — створює `JobOrder` у OPC UA `JobOrderList` верстата (стан `AllowedToStart`) і `feed`-завдання порталу на `total_sheets` листів |
| API-34 | `GET /jobs/{id}/mpr` | `?part=P001` | `text/plain` MPR для деталі (CNC/NEST) або 404 для пилок |

#### 8.6.1 CSV списку деталей (ПРИПУЩЕННЯ за полями intelliDivide)

Роздільник `;`, UTF-8 з заголовком: `PartId;Description;Material;Length;Width;Quantity;Grain;EdgeTop;EdgeBottom;EdgeLeft;EdgeRight;Program`. `Length/Width` — мм (цілі), `Grain` — `0|1|2` (без/вздовж/поперек), `Edge*` — код крайки (`EB2-SON`) або порожньо, `Program` — ім'я MPR для ЧПК або порожньо. Валідація: ≥ 1 рядок, `Length ≤ 2800`, `Width ≤ 2070`, `Quantity ≥ 1`; помилка → 422 `{"detail": [{"row": 3, "error": "Width > 2070"}]}`. Оптимізатор емулятора — жадібне гільйотинне розкладання (FFDH) за 1–5 с; детермінований.

### 8.7 Додаток P-05 — Schneider PowerLogic PM5560 (лічильники вводів, фідерів, споживачів)

**Еталон:** Schneider Electric «PM5560 / PM5563 / PM5563RD Modbus Register List» (xlsx у FAQ FA234017 «Modbus register list for PM5000 series» — https://www.se.com/ww/en/faqs/FA234017/, переглянуто 13.10.2026) і FAQ FA237865 «Formula to Calculate the Energy 64-bit INT in PM5000 Series» (https://www.se.com/ww/en/faqs/FA237865/: енергія — INT64, приклад регістрів 3204/3206; Float32-копії з прошивки 1.3.7 від 2700). Адреси нижче — 1-based holding registers, Float32 big-endian (старше слово першим), INT64 — 4 регістри, старше слово першим. **Авторитетне джерело — xlsx; підмножина нижче звірена з публічними витягами; звірити при закупівлі прошивки (Q-12).** MasterPact MTZ2 / Micrologic X (IFE) у емуляторі **не** окремий unit: вводи Q1/Q2 представлені PM5560 unit 1/2 (вимірювання) — стан вимикача дає регістр 2x18 нижче (ПРИПУЩЕННЯ, замість карти IFE).

#### 8.7.1 Карта регістрів (однакова для всіх unit 1–8, 11–59)

| Регістр | Назва | Тип | Одиниця | Масштаб | R/W | Емулятор |
|---|---|---|---|---|---|---|
| 30–49 | Meter Name | UTF-8 (20 рег.) | — | — | R | `"PM-<код>"` (`PM-SAW-1`, `PM-Q1`) |
| 50–69 | Meter Model | UTF-8 | — | — | R | `"PM5560"` |
| 70–89 | Manufacturer | UTF-8 | — | — | R | `"Schneider Electric"` |
| 130–131 | Serial Number | UINT32 | — | — | R | `2026000000 + unit` |
| 1637–1639 | Firmware X.Y.Z | UINT16 ×3 | — | — | R | 2, 7, 4 |
| 2014 | Number of Phases | UINT16 | — | — | R | 3 |
| 2015 | Number of Wires | UINT16 | — | — | R | 4 |
| 2016 | Power System Configuration | UINT16 | — | — | R | 11 (3PH4W Wye Gnd) |
| 2017 | Nominal Frequency | UINT16 | Гц | 1 | R | 50 |
| 2029–2030 | CT Primary / CT Secondary | UINT16 | А | 1 | R | вводи 1600/5, фідери 630/5, споживачі 100/5 |
| 2025–2026, 2027 | VT Primary / Secondary | F32 / UINT16 | В | 1 | R | 400 / 400 (без ТН) |
| 3000–3001 | Current A | F32 | А | 1 | R | R-01 |
| 3002–3003 | Current B | F32 | А | 1 | R | |
| 3004–3005 | Current C | F32 | А | 1 | R | |
| 3006–3007 | Current N | F32 | А | 1 | R | ≈ 2 % від фазного |
| 3010–3011 | Current Avg | F32 | А | 1 | R | `S·1000/(√3·400)` |
| 3020–3021 / 3022–3023 / 3024–3025 | Voltage A-B / B-C / C-A | F32 | В | 1 | R | 400 ± 1 % |
| 3026–3027 | Voltage L-L Avg | F32 | В | 1 | R | |
| 3028–3029 / 3030–3031 / 3032–3033 | Voltage A-N / B-N / C-N | F32 | В | 1 | R | 230 ± 1 % |
| 3036–3037 | Voltage L-N Avg | F32 | В | 1 | R | |
| 3054–3055 / 3056–3057 / 3058–3059 | Active Power A / B / C | F32 | кВт | 1 | R | P/3 ± 3 % |
| 3060–3061 | **Active Power Total** | F32 | кВт | 1 | R | `energy/…/p_now`; від'ємне = віддача в мережу (вводи, R-13) |
| 3062–3067 | Reactive Power A/B/C | F32 | кВАр | 1 | R | |
| 3068–3069 | Reactive Power Total | F32 | кВАр | 1 | R | `P·tan(acos cosφ)` |
| 3070–3075 | Apparent Power A/B/C | F32 | кВА | 1 | R | |
| 3076–3077 | Apparent Power Total | F32 | кВА | 1 | R | `√(P²+Q²)` |
| 3078–3083 | Power Factor A/B/C | F32 | — | 1 | R | |
| 3084–3085 | **Power Factor Total** | F32 (знак — чотириквадрантний) | — | 1 | R | cos φ за `PROFILE` (0,82–0,97) |
| 3110–3111 | Frequency | F32 | Гц | 1 | R | 50,00 ± 0,02 |
| 3204–3207 | **Active Energy Delivered (Into Load)** | INT64 | Вт·год | 1 | R | накопичувальний лічильник R-03 (`kwh_shift` = різниця за зміну) |
| 3208–3211 | Active Energy Received (Out of Load) | INT64 | Вт·год | 1 | R | > 0 лише на вводах при експорті |
| 3212–3215 | Active Energy Delivered + Received | INT64 | Вт·год | 1 | R | |
| 3220–3223 | Reactive Energy Delivered | INT64 | ВАр·год | 1 | R | |
| 2700–2701 | Active Energy Delivered (Float32-копія) | F32 | кВт·год | 1 | R | те саме, що 3204 / 1000 |
| 2704–2705 | Active Energy Received (Float32) | F32 | кВт·год | 1 | R | |
| 2018 (ПРИПУЩЕННЯ) | Breaker state (лише unit 1–8) | UINT16 | — | — | R | 0 open / 1 closed / 2 tripped — замість карти Micrologic X/IFE; на проді — інший `f3d.source` |
| 5680 | Command Semaphore (FAQ FA234017) | UINT16 | — | — | R/W | повертається, запис логується; команда 2020 «Reset All Energies» → обнулення 3204+ (лише `write_enabled` споживача) |

Невизначені регістри в діапазоні 0–6000 повертають 0 (не виняток) — так поводиться реальний PM5xxx для зарезервованих адрес? **Ні** — емулятор повертає виняток 0x02 поза описаними діапазонами, щоб тести ловили хибні адреси.

#### 8.7.2 Агрегація (R-01, R-13)

`meter.py` рахує: споживач (unit 11–59) — `P` з моделі пристрою (верстат R-02, інженерія `noise`), `Q = P·tan(acos PF)`; фідер (unit 3–8) — сума своїх споживачів за `energy.lines` макета (BW-1: SAW-1, SAW-2, EDGE-1, EDGE-2, CNC-1, CNC-2, SORT-1; BW-2: SAW-3, SLIDE-1, VSAW-1, NEST-1, EDGE-3, CNC-3, BORE-1, CNC-4, DOWEL-1, GANTRY-1; BW-3: SAND-1, AUTOSPRAY-1, UV-1, HINGE-1, GLUE-1, PRESS-1, SPRAY-1, DRY-1; BW-4: ASMLINE-1, ASM-1…6, PACK-1, PACK-2, BOX-1, PACKLINE-1; C1: COMPRESSOR, DUST-1, BOILER; C2: CHARGING, OFFICE, LP-1..3, RV-ALL, AHU-1, EF-*); ввід (unit 1/2) — сума секції (секція 1: QF-3, QF-2, QF-C1; секція 2: QF-1, QF-4, QF-C2) мінус СЕС/КГУ/BESS за R-13 (генерація приєднана до секції 2: PV, CHP, BESS — ПРИПУЩЕННЯ однолінійної схеми). cos φ вводу після компенсації = 0,97.

### 8.8 Додаток P-06 — MQTT-телематика рухомої техніки

**ПРИПУЩЕННЯ** (D-09): телематичний шлюз публікує JSON у брокер. Брокер `mosquitto` (користувачі `iot_sim` — publish, `collector` — subscribe; ACL у `mosquitto/acl`). Протокол MQTT 3.1.1 (сумісно з 5.0).

| Топік | QoS | Retain | Період | Схема |
|---|---|---|---|---|
| `f3d/mobile/<code>/telemetry` | 1 | ні | 5 с; 1 с у русі; одразу при зміні `state` | §8.8.1 |
| `f3d/mobile/<code>/status` | 1 | так | при з'єднанні/зміні; LWT → `{"online": false}` | `{"code": "FL-1", "online": true, "ts": "…", "fw": "1.4.2", "model": "Jungheinrich EFG 216", "gateway": "sim"}` |
| `f3d/mobile/<code>/event` | 1 | ні | за подією | `{"ts", "code", "type": "charge_start|charge_end|low_battery|fault|shock|task_start|task_end", "detail": {…}}` |
| `f3d/mobile/_all/heartbeat` | 0 | ні | 60 с | `{"ts", "online": ["FL-1", …]}` |

`<code>` ∈ {`FL-1`, `FL-2`, `FL-3`, `FL-4`, `FL-5`, `FL-C1`, `FL-C2`, `TUGGER-1`}.

#### 8.8.1 Схема `telemetry` (JSON Schema, скорочено)

```json
{"type": "object", "required": ["ts", "code", "state", "battery_pct", "hours", "x", "y"],
 "properties": {
   "ts": {"type": "string", "format": "date-time"},
   "code": {"type": "string"},
   "state": {"enum": ["idle", "busy", "to_charge", "charging", "offline", "fault"]},
   "battery_pct": {"type": "number", "minimum": 0, "maximum": 100},
   "battery_v": {"type": "number"},
   "charging": {"type": "boolean"},
   "hours": {"type": "number"},
   "odometer_km": {"type": "number"},
   "x": {"type": "number"}, "y": {"type": "number"}, "heading_deg": {"type": "number"},
   "speed_kmh": {"type": "number", "minimum": 0, "maximum": 20},
   "zone": {"type": ["string", "null"]},
   "task": {"type": ["string", "null"]},
   "load_kg": {"type": "number"},
   "operator": {"type": ["string", "null"]},
   "faults": {"type": "array", "items": {"type": "string"}}
 }}
```

Приклад: `{"ts":"2026-10-14T08:15:03+03:00","code":"FL-1","state":"busy","battery_pct":57.1,"battery_v":48.6,"charging":false,"hours":2069.8,"odometer_km":1842.3,"x":112.4,"y":37.8,"heading_deg":90,"speed_kmh":6.2,"zone":"Z-FG","task":"WH/SFP/00201","load_kg":640,"operator":"OP-W6","faults":[]}`. Відповідність каталогу: `equipment/<code>/battery ← battery_pct`, `…/hours ← hours`, `…/state ← state` (`to_charge` для переглядача = `busy`), `…/x`, `…/y`.

### 8.9 Додаток P-07 — інженерне обладнання (Modbus TCP) і режим follow_odoo

#### 8.9.1 Huawei SUN2000-115KTL-M2 (PV-INV-1…8, unit 61–68)

**Еталон:** Huawei «SUN2000MB Modbus Interface Definitions», V200R023C10, Issue 02, 2024-02-01 (копія — https://community.jeedom.com/uploads/short-url/cEJpNRU5j3k0LvPW43eRU7nKzfr.pdf, переглянуто 13.10.2026); документ охоплює моделі SUN2000-12…25KTL-M5/MB0 — для SUN2000-115KTL-M2 карта **ідентична за цими регістрами** (спільний простір 30000/32000/40000 серії SUN2000; ПРИПУЩЕННЯ щодо повної тотожності, звірити з «SUN2000-(100KTL-115KTL) Modbus Interface Definitions»). Modbus TCP порт 502; у проді unit = «communication address» інвертора (за замовчуванням 1, документ §7.2.2.3), у емуляторі 61–68. Типи: U16/I16/U32/I32/STR, gain — дільник.

| Регістр | К-сть | Назва | Тип | Gain | Одиниця | R/W | Емулятор |
|---|---|---|---|---|---|---|---|
| 30000 | 15 | Model | STR | — | — | RO | `"SUN2000-115KTL-M2"` |
| 30015 | 10 | SN | STR | — | — | RO | `"HV2240…0<n>"` |
| 30073 | 2 | Rated power Pn | U32 | 1000 | кВт | RO | 115,000 |
| 30075 | 2 | Maximum active power Pmax | U32 | 1000 | кВт | RO | 125,000 |
| 32016 + 2·(k) | 1 | PV<k+1> voltage (k = 0…9) | I16 | 10 | В | RO | 650–780 вдень, 0 вночі |
| 32017 + 2·(k) | 1 | PV<k+1> current | I16 | 100 | А | RO | за потужністю |
| 32064 | 2 | DC power | I32 | 1000 | кВт | RO | `P_ac / 0,986` |
| 32066 / 32067 / 32068 | 1 | Grid line voltage AB / BC / CA | U16 | 10 | В | RO | 400 ± 1 % |
| 32069 / 32070 / 32071 | 1 | Phase A / B / C voltage | U16 | 10 | В | RO | 230 |
| 32072 / 32074 / 32076 | 2 | Phase A / B / C current | I32 | 1000 | А | RO | `P/(√3·400)` |
| 32078 | 2 | Peak active power of current day | I32 | 1000 | кВт | RO | макс за добу |
| 32080 | 2 | **Active power** | I32 | 1000 | кВт | RO | R-11 (`infra/pv/PV-INV-k/p_kw`); сума ×8 = `infra/totals/pv_now` |
| 32082 | 2 | Reactive power | I32 | 1000 | кВАр | RO | 0 |
| 32084 | 1 | Power factor | I16 | 1000 | — | RO | 1,000 |
| 32085 | 1 | Grid frequency | U16 | 100 | Гц | RO | 50,00 |
| 32086 | 1 | Efficiency | U16 | 100 | % | RO | 98,4 |
| 32087 | 1 | Internal temperature | I16 | 10 | °C | RO | 25 + 0,25·P% |
| 32088 | 1 | Insulation resistance | U16 | 1000 | МОм | RO | 3,000 |
| 32089 | 1 | **Device status** | E16 | — | — | RO | enum нижче |
| 32090 | 1 | Fault code | U16 | — | — | RO | 0; при збої — 2032 (Grid loss) / 2064 (Internal fault) |
| 32091 / 32093 | 2 / 2 | Startup time / Shutdown time | Epoch s | 1 | с | RO | схід/захід сонця |
| 32106 | 2 | Accumulated energy yield | U32 | 100 | кВт·год | RO | накопич. |
| 32114 | 2 | **Daily energy yield** | U32 | 100 | кВт·год | RO | `infra/pv/PV-INV-k/kwh_today`; обнулення о 00:00 |
| 40000 | 2 | System time (local) | Epoch s | 1 | с | RW | `sim_now`; запис приймається (лише `write_enabled` споживача) |
| 42000 | 1 | Power grid standard code | U16 | — | — | RW | 0 |

Enum `Device status` (32089), підмножина, яку використовує емулятор (значення за документом Huawei): `0x0000` Standby: initializing; `0x0001` Standby: detecting insulation resistance; `0x0002` Standby: detecting irradiation; `0x0003` Standby: grid detecting; `0x0100` Starting; `0x0200` **On-grid**; `0x0201` Grid connection: power limited; `0x0300` Shutdown: fault; `0x0301` Shutdown: command; `0x0303` Shutdown: communication disconnected (blackout); `0xA000` Standby: no irradiation (ніч). Повний перелік — документ, §4 «Device status».

#### 8.9.2 Huawei LUNA2000 (BESS, unit 69)

**Еталон (частково):** регістри 37000+ описані в «SUN2000 (3–10KTL-M1) Modbus Interface Definitions» (ESS через інвертор) і широко використовуються інтеграціями; для промислової LUNA2000-200KWH-2H1 з PCS LUNA2000-100KTL-M1 Huawei публікує «LUNA2000B ESS Modbus Port Definitions» (https://support.huawei.com/enterprise/en/doc/EDOC1100311915, 2023-06-13; текст недоступний без входу) — **ПРИПУЩЕННЯ: C&I-система віддає ті самі регістри 37000-серії; звірити.**

| Регістр | К-сть | Назва | Тип | Gain | Одиниця | Емулятор |
|---|---|---|---|---|---|---|
| 37000 | 1 | Running status | U16 | — | 0 offline, 1 standby, 2 running, 3 fault, 4 sleep | `infra/bess/state` (R-13) |
| 37001 | 2 | Charge/Discharge power | I32 | 1 | Вт (+ заряд, − розряд) | `infra/totals/bess_kw·1000` |
| 37002 | 1 | Bus voltage | U16 | 10 | В | 760 |
| 37004 | 1 | **SOC** | U16 | 10 | % | `infra/totals/bess_soc` |
| 37006 | 1 | Working mode | U16 | — | 2 = maximise self-consumption, 4 = time-of-use | 4 |
| 37014 | 2 | Total charge | U32 | 100 | кВт·год | накопич. |
| 37016 | 2 | Total discharge | U32 | 100 | кВт·год | накопич. |
| 37015 / 37017 | 2 | Current-day charge / discharge capacity | U32 | 100 | кВт·год | обнулення 00:00 |
| 37022 | 1 | Battery temperature | I16 | 10 | °C | 25 + 0,05·|P| |
| 37046 | 2 | Rated capacity | U32 | 1 | Вт·год | 387 000 (2 шафи) |
| 37050 | 1 | SOH | U16 | 10 | % | 99,0 |

#### 8.9.3 Atlas Copco GA 37 VSD+ / Elektronikon Mk5 (COMPRESSOR, unit 70)

**ПРИПУЩЕННЯ, звірити з Atlas Copco** (карту Modbus TCP Mk5 вендор видає за серійним номером — Q-05; публічно доступний лише опис Mk IV через ComBox-S). Макет регістрів емулятора (holding, 1-based):

| Регістр | Назва | Тип | Масштаб | Одиниця | Емулятор (R-08) |
|---|---|---|---|---|---|
| 3001 | Machine status | U16 | — | 0 stopped, 1 running loaded, 2 running unloaded, 3 shutdown/fault, 4 standby (VSD мін.) | `equipment/COMPRESSOR/state` |
| 3002 | Outlet pressure | U16 | ×0,001 | бар | `pressure_bar` (6,5–7,0) |
| 3003 | Element outlet temperature | U16 | ×0,1 | °C | `temp_c` 78–88; > 110 → fault |
| 3004 | Dew point | I16 | ×0,1 | °C | 3,0 |
| 3005 | Ambient temperature | I16 | ×0,1 | °C | 24,0 (компресорна) |
| 3010 | Load (VSD output) | U16 | ×1 | % | `load` |
| 3011 | Motor speed | U16 | ×1 | об/хв | 1 200 + 36·load |
| 3012 | Motor current | U16 | ×0,1 | А | `37·load/100·1000/(√3·400·0,95)` |
| 3020–3021 | Running hours | U32 | ×1 | год | `hours` |
| 3022–3023 | Loaded hours | U32 | ×1 | год | ≈ 0,65·hours |
| 3024–3025 | Load cycles | U32 | ×1 | — | +1 на цикл load/unload |
| 3030 | Service timer (до ТО) | U16 | ×1 | год | 160 (= 18 000 − 17 840, MR/00033) |
| 3040 | Shutdown code | U16 | — | 0 / 11 (high temp) / 12 (motor overload) / 20 (comm) | за збоєм |
| 3100 | Setpoint pressure | U16 | ×0,001 | бар | 7,000; RW (лише `write_enabled`) |

Дві машини GA 37 (×2 у паспорті) представлені одним контролером-майстром (ES-керування) — unit 70; розподіл навантаження між машинами всередині моделі.

#### 8.9.4 Socomec ATyS p 1600 (ATS-1, unit 71)

**ПРИПУЩЕННЯ** за структурою опублікованих таблиць Socomec для ATyS g / ATyS C65 (блок стану від 20480; https://www.socomec.co.in/… «ATYS-G COMMUNICATION TABLE 2021-08», переглянуто 13.10.2026, повний доступ обмежений) — звірити з «ATyS p communication table» (Q-07).

| Регістр | Назва | Тип | Значення | Емулятор (R-22) |
|---|---|---|---|---|
| 20480 | Switch position | U16 | 0 = 0 (обидва вимкнені), 1 = I (мережа), 2 = II (генератор) | `infra/ats/position` |
| 20481 | Source 1 available | U16 | 0/1 | `src1_ok` |
| 20482 | Source 2 available | U16 | 0/1 | `src2_ok` (генератор запущений) |
| 20483 | Operating mode | U16 | 0 auto, 1 manual, 2 test | 0 |
| 20484 | Fault summary | U16 (біти) | bit0 transfer failure, bit1 motor fault, bit2 comm | 0 |
| 20485 | Transfer in progress | U16 | 0/1 | під час переключення (3 с) |
| 20490–20492 | Source 1 voltage L1-L2 / L2-L3 / L3-L1 | U16 | В | 400 / 0 при blackout |
| 20493 | Source 1 frequency | U16 ×0,1 | Гц | 50,0 |
| 20500–20502 | Source 2 voltage | U16 | В | 400, коли генератор працює |
| 20503 | Source 2 frequency | U16 ×0,1 | Гц | 50,0 |
| 20510–20511 | Transfer counter | U32 | — | 17 (+1 на переключення) |
| 20512–20513 | Last transfer time | Epoch s | — | 05.10.2026 18:42 (`infra.py` картка) |
| 20520 | Timer: genset start delay | U16 | с | 10 (RW) |
| 20521 | Timer: return delay | U16 | с | 60 (RW) |

#### 8.9.5 TEDOM Quanto D800 NG (CHP, unit 72)

**ПРИПУЩЕННЯ, звірити з TEDOM** (точки даних ProCon не опубліковано — Q-06).

| Регістр | Назва | Тип | Масштаб | Одиниця | Емулятор (R-12) |
|---|---|---|---|---|---|
| 40000 | State | U16 | — | 0 stop, 1 starting, 2 running, 3 fault, 4 cooling down | `infra/chp/state` |
| 40001 | Electrical power | U16 | ×1 | кВт | `infra/totals/chp_kw` (400 удень, 800 увечері) |
| 40002 | Heat output | U16 | ×1 | кВт | `heat_kw` (497 / 856) |
| 40003 | Gas consumption | U16 | ×0,1 | м³/год | 109 / 199 |
| 40004 / 40005 | Supply / return water temperature | U16 | ×0,1 | °C | 90 / 70 |
| 40006 | Engine speed | U16 | ×1 | об/хв | 1 500 |
| 40007 | Load setpoint | U16 | ×1 | % | 50 (RW, `write_enabled`) |
| 40010–40011 | Running hours | U32 | ×1 | год | 3 412 |
| 40012–40013 | Number of starts | U32 | ×1 | — | 211 |
| 40014–40015 | Energy produced total | U32 | ×1 | кВт·год | накопич. |
| 40020 | Alarm code | U16 | — | 0 / 101 (gas pressure low) / 205 (overtemp) | за збоєм |

#### 8.9.6 Аналогові й дискретні модулі ADAM для інженерії (unit 84, 90, 96)

**Еталон:** ADAM-6000 User Manual Ed.12, Appendix B.2 (карти ADAM-6017: AI 40001–40008 raw U16, float IEEE754 40031–40046, burnout 00121–00128, high/low alarm 00131–00148; ADAM-6015: 7 каналів RTD, AI 40001–40007, float 40031–40044, burnout 00121–00127; ADAM-6050 — §8.4.2).

| unit | Модуль | Канал | Сигнал | Діапазон (R-20) | Адреси |
|---|---|---|---|---|---|
| 90 | ADAM-6017 (4–20 мА, type code `0x0107`) | AI0 | `equipment/DUST-1/airflow_m3h` | 0…32 000 м³/год | raw 40001, float 40031–40032 (мА) |
| 90 | | AI1 | `equipment/DUST-1/filter_dp_kpa` | 0…4 кПа | raw 40002, float 40033–40034 |
| 90 | | AI2 | `equipment/SPRINKLERS/pressure_bar` | 0…16 бар | raw 40003, float 40035–40036 |
| 90 | | AI3 | `equipment/AIR-RING/pressure_bar` | 0…16 бар | raw 40004, float 40037–40038 |
| 90 | | AI4–AI7 | резерв | — | raw 40005–40008 = 0, burnout 00125–00128 = 1 |
| 96 | ADAM-6015 (PT100, type code `0x0020`, −50…+150 °C) | RTD0–RTD2 | `energy/transformers/T1/temp_c` (макс. з трьох обмоток) | −50…+150 °C | raw 40001–40003, float 40031–40036 (°C) |
| 96 | | RTD3–RTD5 | `energy/transformers/T2/temp_c` | | raw 40004–40006, float 40037–40042 |
| 96 | | RTD6 | резерв (burnout 00127 = 1) | | 40007 |
| 84 | ADAM-6050 | DI0 / DI1 | `equipment/DUST-1/state` (вентилятори в роботі / аварія) | — | 00001 / 00002 |
| 84 | | DI8 (лічильник) | `infra/water/m3_total` (1 імп = 10 л, Apator MWN50 NK) | — | лічильник 40017–40018; старт 00065 |
| 84 | | DI2–DI7, DI9–DI11, DO0–DO5 | резерв | — | 0 |

**R-20 масштабування ADAM:** `raw = round(65535·(mA − 4)/16)` для 4–20 мА, де `mA = 4 + 16·(eng − lo)/(hi − lo)`; для RTD `raw = round(65535·(t + 50)/200)`; float-регістри — інженерна одиниця (мА або °C) IEEE754, старше слово першим (`40031` = старше). Споживач читає або raw (і масштабує за каталогом `lo/hi`), або float.

#### 8.9.7 Режим `follow_odoo` (XML-RPC лише читання)

Користувач `SIM_ODOO_USER` (`f3d_sim_reader`) з API-ключем; дозволені методи — `search_read`, `read`, `search_count`, `fields_get`; будь-який інший виклик у коді неможливий (клієнт-обгортка `OdooReadOnly` має лише ці методи). Період `SIM_ODOO_FOLLOW_S` (10 с) — «швидкі» запити, `SIM_ODOO_FOLLOW_SLOW_S` (60 с) — «повільні».

| Період | Модель | Домен | Поля | Куди в емулятор |
|---|---|---|---|---|
| 10 с | `mrp.workorder` | `[("state","in",["ready","progress","done"]), ("date_finished",">=", sim_now − 1 день) або state != done]` | `id, name, state, workcenter_id, production_id, qty_produced, qty_production, duration, duration_expected, date_start, working_state` | `World.workcenters[code].job`, стани ISA-95 (§8.3.2), R-14, R-16 (`pieces_out` ← `qty_produced` як нижня межа) |
| 10 с | `mrp.workcenter` | `[]` | `code, working_state` | `blocked` → `Flags.Error`/`DI fault`, `CurrentState=ERROR` (CNC-2 у демо) |
| 60 с | `stock.picking.batch` | `[("dock_id","!=",False), ("state","in",["draft","in_progress"])]` | `name, description, dock_id, scheduled_date, state, f3d_truck (якщо є в base), picking_ids` | `World.trucks` (R-29): фура `description`/`f3d_truck`, ворота `dock_id.barcode` |
| 60 с | `stock.picking` | `[("id","in", batch.picking_ids)]` | `name, state, picking_type_code, move_ids.quantity/product_uom_qty` | прогрес розвантаження/завантаження (R-29) |
| 60 с | `hr.employee` | `[("barcode","!=",False)]` | `name, barcode, resource_calendar_id, job_title` | `World.people` (R-28) |
| 60 с | `resource.calendar.attendance` | календарі з попереднього запиту | `dayofweek, hour_from, hour_to` | розклад зміни (R-28, R-24) |
| 60 с | `maintenance.request` | `[("stage_id.done","=",True), ("write_date",">=", last_poll)]` + поле `x_request_id` рівня 0 через `x_f3d_signal` (`[("x_request_id","!=",False)]` → `x_code`, `x_request_id.stage_id.done`) | `equipment_id.f3d_code`, `f3d_signal_id.code` (якщо телеметрія є) | `World.maintenance_closed` → скидання `drift` (R-09) |
| 1 год | `GET /f3d/sim/devices` (API-01) | — | весь реєстр | перезавантаження каталогу (без переривання значень) |

При помилці читання > `SIM_ODOO_STALE_S` — `odoo_stale=true` в `/status`, емулятор продовжує з останнім відомим станом (не переходить у `scenario` сам); після відновлення — повна синхронізація. У `follow_odoo` планувальник зміни/фур/людей **не** генерує власних завдань і фур, але продовжує фізику (АКБ, фільтри, баланс) і рух техніки за завданнями з Odoo (`current_task` ← `stock.picking` з `vehicle`?) — у фазі 1 рух техніки в `follow_odoo` іде за розкладом R-19 без прив'язки до документів.
