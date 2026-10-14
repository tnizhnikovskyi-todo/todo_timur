# factory3d_iot_sim — специфікація

Версія 0.3 · 14.10.2026 (0.2 — 14.10.2026, 0.1 — 13.10.2026) · технічне рішення — `ARCHITECTURE.md` (поруч). Мова: українська; технічні імена — англійською.

Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-75 (§8.1.3–8.1.4: `genset_relay` за td_genset §8.5 CI-02 — `RELAY_PROFILE=d700`, `RELAY_PORT=8000`, `RELAY_SIM_TOKEN`, `RELAY_TIME_FACTOR`, `RELAY_TZ`, healthcheck, мережі `f3d_sim` + `odoo_default`; `SIM_GENSET_RELAY_TOKEN` = `${RELAY_SIM_TOKEN}`), X-76 (Додаток A: рядок 334 `equipment/GANTRY-1/stacks` → `protocol=none`, обчислює machine_connect; новий рядок 1 166 `equipment/CUTOPT/cmd` `protocol=none`, пасивний пристрій `CUTOPT`; каталог 1 166 = 1 015 + 151, пристроїв 274), X-78 (межа генератора — ESP 558 кВт, перевірено; примітка в `SIM_GENSET_KW_MAX`), X-79 (§8.11.1 LSP id ручних/оповіщувачів/полум'я за fire R-23/A-09, 292 LSP; примітка про LSP-рядки в Додатку A); нові AC-66…AC-68, ТК-18 (v0.3).

Зміни (v0.2): 14.10.2026 — правки за `docs/CONSISTENCY.md` v0.3: X-15 (`bookings.truck` = `f3d_code`; follow_odoo читає `f3d_code`/`f3d_truck`/`f3d_plate`, ворота — `dock_id.f3d_code`), X-31 (меню під `factory3d_base.menu_f3d_root`, sequence 90; налаштування — під `menu_f3d_config`), X-34 (каталог +503 рядки № 663–1 165 з додатків energy/fire_safety/yard/machine_connect/bms; рядки 644/646/654/656 — по одному входу), X-35 (149 рядків `protocol=none` «обчислює <модуль>», не в `/signals`), X-36 (`fire/totals/state` = LSZ:0, MSV:1 → `fire/totals/system_state`; шлейф — лише `fault(reason=loop)`), X-37 (Cerberus — BV/PIV), X-38 (`…/state` без заявок, `JobOrderID = WO%05d`, завершені JobOrder у списку), X-39 (%-сигнали `scale` ×1), X-40 (стан щита — агрегат роутера, R-23 `heat_nom = 116,8`, біти C:110 за Helvar, EF-CHG — тривога), X-41 (ATyS p — Annexe III, §8.9.4), X-42 (Modbus — PDU за документом вендора, §8.4.1), X-43 (ADAM — молодше слово першим), X-47 (DO5 — «тримати» GATE-E), X-48 (LPR: `capture_timestamp = sim_now`, `plateList` — назва списку, `plateListMode`), X-49 (номер з `f3d_plate`; `АА4512КТ` — TRUCK-OUT-1), X-50 (BioStar 4102/4867 за `det % 2`, сортування за зростанням, `offset`/`hint`), X-51 (LUNA2000 без перекриттів), X-54 (приклад API-01 з base C/D), X-56 (`read_enabled` за `factory3d.base.environment`), X-58 (`value` у прикладі `filter_clogged`), X-59 (CI-01: `amf_master`, `genset_load_kw`, `test_on_load`, API-F-01…F-09), X-60 (`fault`/`clear` на пасивних `FA-*`), X-61 (+9 споживачів u51–59), X-64 (HelvarNet: `A:1`, відповідь у версії запиту, C:164 з кадрами `$`, `SIM_HELVAR_VERSION`), X-65 (розкладка DALI за bms R-06 / Додаток A.1), X-67 (острів: `P_genset = Σ критичних − chp_kw − pv_now + bess_kw`, 0…558 кВт; параметр `chp_island`), X-72 (Modbus-адреси в каталозі й таблицях — форма `u<unit> fc<n> pdu<addr>[+<count>]`); нові AC-51…AC-65, ТК-17; закрито Q-07 (X-41), Q-09 (X-53), Q-15 (X-59).
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-01, Q-02, Q-03, Q-04, Q-05, Q-06, Q-08, Q-10, Q-11, Q-12, Q-13.
Зміни: 14.10.2026 — у макеті додано групи FA-SOC (LSZ 34) і FA-OFFICE (LSZ 35), відповідь № 12г: Додаток A — нові рядки 1 167 `fire/groups/FA-SOC/state` (dev 200 LSZ:34) і 1 168 `fire/groups/FA-OFFICE/state` (LSZ:35), дописані в кінець без перенумерації; каталог 1 166 → 1 168 (веде емулятор 1 015 → 1 017, власні 662 → 664, P-09: 53 → 55, нові 970 → 972, з них fire_safety 52 → 54); §8.11.1 — LSZ:1…35, LSP 292 → 302 (сповіщувачів 212 → 222, усі нові — шлейф 3), PIV запиленості до 222; пристроїв 274 → 276 (обладнання base 208 → 210); §5.1, §5.3, API-01, API-02, API-10, API-16, S-07, AC-02, AC-05, AC-22, AC-24, AC-25, AC-62, AC-66, §13 (ТК-08, ТП-05, ТП-06, DEPLOY_TEST).
Зміни: 14.10.2026 — R-04: поріг тривоги температури трансформатора 140 °C (відповідь № 24).

Контракти, на які спирається документ: `docs/ARCHITECTURE.md` §5 (конвенції імен сигналів, стоп-крани, права), §6.1–6.3 (`f3d.scene.mixin.f3d_code`, `f3d.zone`, ворота-`stock.location`, паспорт `maintenance.equipment.f3d_*`), §6.6 (протокольна матриця P-01…P-13, REST `/sim/v1/*`, режими `scenario`/`follow_odoo`), §6.7 (шляхи даних переглядача), §6.8 (заявки ТО), рішення D-01, D-05…D-09, D-13, D-20 (адреси Modbus — PDU за вендором, ADAM — молодше слово першим), D-21 (ATyS p — Annexe III), D-23 (AMF — варіант A); реєстр `docs/CONSISTENCY.md` (X-xx); рішення автора A-01…A-12 (`ARCHITECTURE.md` §7).

Що цей документ **віддає** іншим модулям (посилатися за ідентифікаторами `factory3d_iot_sim <ID>`): протокольні карти **P-01…P-12** (§8.3–§8.14), каталог сигналів **Додаток A** (1 168 рядків: 1 017 веде емулятор, 151 ведуть модулі-власники — X-34, X-35, X-76; № 1 167–1 168 — зони `FA-SOC`, `FA-OFFICE`, № 12г), **API-01…API-03** (Odoo), **API-10…API-19** (`/sim/v1`), **API-20…API-27** (woodStore), **API-30…API-34** (`/jobs`), **API-40…API-46** (BioStar 2), схема MQTT P-06 (§8.8), формат LPR і SICS (§8.13), правила R-01…R-30 (§9), сценарії S-01…S-15 (§9.3).

---

## 0. Дерево файлів модуля

### 0.1 Сервіс `services/iot_sim`

```
services/iot_sim/
├── README.md                       запуск, порти, змінні середовища (коротко; повно — тут §8.1–8.2)
├── pyproject.toml                  пакет iot_sim, Python 3.12, entry point `iot-sim`
├── requirements.txt                закріплені версії (§8.1.2)
├── Dockerfile                      python:3.12-slim, non-root user `sim`, HEALTHCHECK → GET /sim/v1/health через `python -c` (urllib; curl в образі немає, X-90)
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
    ├── unit/                       test_rng.py, test_clock.py, test_models_*.py, test_world.py, test_scenarios.py, test_registry.py,
    │                               test_lighting_layout.py, test_outbound_guard.py
    ├── protocols/                  test_opcua.py, test_modbus_*.py, test_bacnet.py, test_helvarnet.py, test_mqtt.py,
    │                               test_biostar.py, test_woodstore.py, test_jobs.py, test_sics.py, test_lpr.py, test_control_api.py
    ├── stand/                      ТК-01…ТК-17 проти compose (pytest -m stand)
    ├── data/                       parts_48.csv (AC-43), bms_dali_devices.csv (копія bms Додаток A.1, AC-65)
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
| `protocol` | Selection | як у M-02, required; `none` — рядок, який обчислює модуль-власник або який є командою модуля-власника (Додаток A, колонка P-xx = «—»; X-34, X-35, X-76): емулятор його не веде й не віддає в `GET /sim/v1/signals`, рядок лишається довідковим для API-01 і міграції телеметрії |
| `address` | Char | «Адреса в джерелі», required; для Modbus — PDU-форма `u<unit> fc<n> pdu<addr>[+<count>] <type>[ little]` (telemetry Q-04, X-42), далі номер за документом вендора; для `protocol='none'` — текст «обчислює <модуль> (<правило>) — без адреси» або, для команди, «команда <плагін> <cmd>, власник <модуль> (…) — без адреси» (`equipment/CUTOPT/cmd`, X-76) |
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

Методи: `action_read_now()`: `GET /signals/{code}` → `last_*`; для `protocol='none'` — `UserError("Сигнал обчислює модуль-власник, емулятор його не веде")` без HTTP-запиту. `@api.model _load_catalog(path)`: читає CSV (§5.1), `create`/`write` за `code` (ідемпотентно), колонка `protocol` `—` → `none`, прив'язує `device_id` за колонкою `device`; невідомий пристрій → `WARNING` у лог і створення пристрою `passive` з цим кодом (щоб каталог не губився).

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

Поля: `device_id` (required), `reason` Selection `[("generic","Загальний збій"),("spindle","Шпиндель/привід"),("emergency","Аварійна кнопка"),("power","Втрата живлення"),("comm","Втрата зв'язку"),("sensor","Датчик"),("loop","Лінія (шлейф) пожежної сигналізації")]` default `generic` (для пасивних пристроїв P-09 з `params.lsz` — `sensor`; `loop` дозволено лише для них, інакше `ValidationError("Причина «Лінія» — лише для зон пожежної сигналізації")`; X-36, X-60), `note` Char. `action_confirm()` → `device_id._set_fault(reason, note)`.

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

Пульт емулятора — під коренем `factory3d_base.menu_f3d_root` («Завод 3D») із зарезервованим `sequence` 90 (base CB-09; X-31); рівень 0 (`menu_iot_root`) — його підпункт; пункт налаштувань — під `factory3d_base.menu_f3d_config` з тим самим `sequence` 90 (правило CB-09/X-32). У меню «Обслуговування» модуль пунктів не додає (там `sequence` 6 — ярлик telemetry).

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_f3d_sim_root` | Емулятор | `factory3d_base.menu_f3d_root` | 90 | `group_f3d_user` | — |
| `menu_f3d_sim_panel` | Пульт | `menu_f3d_sim_root` | 1 | `group_f3d_user` | `action_f3d_sim_panel` (`ir.actions.server`, код: `action = env['f3d.sim.panel'].get_panel().get_formview_action()`) |
| `menu_f3d_sim_scenarios` | Сценарії | root | 2 | `group_f3d_user` | `action_f3d_sim_scenario` (kanban,list,form) |
| `menu_f3d_sim_runs` | Запуски | root | 3 | `group_f3d_user` | `action_f3d_sim_run` (list,form) |
| `menu_f3d_sim_devices` | Пристрої | root | 4 | `group_f3d_user` | `action_f3d_sim_device` (list,form), context `search_default_group_protocol` |
| `menu_f3d_sim_signals` | Каталог сигналів | root | 5 | `group_f3d_user` | `action_f3d_sim_signal` (list,form) |
| `menu_f3d_sim_events` | Події | root | 6 | `group_f3d_user` | `action_f3d_sim_event` (list) |
| `menu_iot_root` (успадковане) | Рівень 0 (без сервісу) | **перенесено** під `menu_f3d_sim_root` | 9 | `group_f3d_admin` | — (дочірні «Сигнали обладнання», «Журнал показань», «Оновити зараз», «Увімкнути/Зупинити імітацію» лишаються) |
| `menu_f3d_sim_settings` | Налаштування емулятора | `factory3d_base.menu_f3d_config` | 90 | `group_f3d_admin` | `action_f3d_sim_settings` (`res.config.settings`, context `module=factory3d_iot_sim`) |

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
| `ir_config_parameter.xml` | 10 параметрів §3 ARCHITECTURE з `noupdate="1"`: `url=""`, `token=""`, `export_token=""`, `read_enabled=True` (умовчання XML; `post_init_hook` крок 1а перераховує за `factory3d.base.environment`, CB-10, X-56), `write_enabled=False`, `mode=follow_odoo`, `level0_enabled=True`, `level0_after_min=5`, `timeout_s=5`, `keep_days=14` | — | `param_f3d_iot_sim_<key>` | `noupdate` |
| `ir_sequence.xml` | `f3d.sim.run`: prefix `RUN/%(year)s/`, padding 4 | — | `seq_f3d_sim_run` | `noupdate` |
| `ir_cron.xml` | C-01, C-02 (§6) | — | `cron_f3d_sim_status`, `cron_f3d_sim_gc` | так |
| `f3d_sim_scenario.xml` | 15 сценаріїв S-01…S-15 (§9.3) з `code`, `name`, `group`, `params_schema`, `params_default`, `duration_s` | §9.3 | `scenario_<code>` | `noupdate="0"` (схеми можуть оновлюватись) |
| `f3d_sim_signal.csv` | 1 168 рядків каталогу (1 017 з протоколом + 151 з `protocol` `—` = `none`, X-34, X-35, X-61, X-76); колонки: `code,name,device,protocol,address,dtype,unit,scale,nominal,thresholds,model_rule,origin,level0_code,kind` | Додаток A (`tools/gen_catalog.py`; рядки 663…1 166 — з додатків модулів-власників; 1 167–1 168 — власні, зони LSZ 34–35) | — (завантажує hook, ключ `code`) | upsert за `code` |

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
| `barrier` (GATE-W, GATE-E) | P-11 | `modbus_adam6060` | unit 86, params GATE-W `{"di_open":0,"di_loop":1,"di_photo":4,"do_open":0,"do_close":2,"do_hold":4}`, GATE-E `{"di_open":2,"di_loop":3,"di_photo":5,"do_open":1,"do_close":3,"do_hold":5}` (окремі канали «тримати відкритим» DO4/DO5 — X-47, §8.13.1) |
| `cctv_camera` (CCTV → `CAM-05`, `CAM-06` активні LPR; решта 10 — пасивні) | P-11 | `http_lpr` | address `SIM_LPR_PUSH_URL`, params `{"gate": "GATE-W"}` |
| `truck_scale` | P-11 | `sics_scale` | address `iot-sim:4001` |
| `genset` | P-12 | `genset_relay` | address з `relay_api.md` |
| усе інше (`iot_box`, `label_printer`, `scale`, `shopfloor_tablet`, `handheld_scanner`, `wifi_ap`, `server_rack`, `substation`, `busbar_dist`, `pfc`, `emergency`, `exit_door`, `lightning_air`, `eyewash`, `board_rack`, `highbay_rack`, `nvr`, …) | P-13/`none` | `passive` | — |

### 5.3 `post_init_hook` (кроки, очікувані кількості на копії демо-бази)

0. `migrations/19.0.2.0.0/pre-migrate.py`: якщо в `ir_module_module` версія `19.0.1.0.0` — записати в лог «upgrade from data module»; перевірити, що `ir_model` з `model='x_f3d_signal'` існує, інакше лише WARNING (свіжа база без рівня 0 допустима).
1. Створити `f3d.sim.panel` (1).
1а. Стоп-кран опитування за середовищем (base CB-10, X-56; як у всіх модулів зі стоп-кранами): `factory3d.iot_sim.read_enabled = 'True'`, якщо `factory3d.base.environment == 'test'`, інакше `'False'` (перезапис при кожному запуску хука); `write_enabled` не змінюється (умовчання `False`); `neutralize.sql` — без змін. Очікувано на копії демо (`environment=test`): `read_enabled=True`; на проді (`prod`) — `False`.
2. Для кожного `maintenance.equipment` з `f3d_code` (після `factory3d_base` — 210, з `FA-SOC`, `FA-OFFICE`): створити/оновити `f3d.sim.device` за таблицею §5.2 (ключ `code = f3d_code`); для `ACCESS`, `CCTV`, `PV-INV` створити похідні пристрої (`ACR-*` ×5, `TURN-1`, `CAM-05/06`, `PV-INV-1..8`), для лічильників споживачів — `<code>-PM` (49) з `equipment_id` того самого обладнання; пасивний пристрій `CUTOPT` (оптимізатор розкрою P-04, без `equipment_id`, `protocol='none'`) — для довідкового рядка `equipment/CUTOPT/cmd` (X-76). Очікувано: 210 + 5 + 1 + 2 + 8 + 49 + 1 = **276** пристроїв, з них `passive` ≈ 100 (стелажі, світильники-групи, сповіщувачі-групи, ІТ, принтери, ваги Odoo IoT, двері…).
3. Завантажити `data/f3d_sim_signal.csv` → `f3d.sim.signal` (**1 168**: `protocol≠none` — 1 017, `none` — 151), прив'язка `device_id` за колонкою `device` (пристрої з кроку 2; для `energy/consumers/<X>/*` — пристрій `<X>-PM`, 49 шт. включно з unit 51–59, X-61; для `energy/cells/Q1` — `Q1`; для `energy/lines/BW-1` — `QF-1`; для `equipment/CUTOPT/cmd` — `CUTOPT`); очікувано 0 рядків без пристрою.
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
         "dtype": "WwUnitStateEnumeration", "unit": "", "scale": "", "nominal": "READY", "thresholds": "—",
         "model_rule": "R-14", "kind": "state"}
      ]
    }
  ],
  "zones": [{"code": "Z-CUT", "name": "Розкрій", "type": "production", "polygon": [[41.8, 0.6], [55.4, 0.6], [55.4, 45.4], [41.8, 45.4]]}],
  "docks": [{"code": "DOCK-W1", "side": "west", "no": 1, "accepts": ["Плитні матеріали"], "location_id": 16, "x": 0.0, "y": 5.0}],
  "shifts": [{"name": "Зміна 1 (07:00–15:30)", "tz": "Europe/Kyiv",
              "attendances": [{"weekday": 0, "from": "07:00", "to": "11:30"}, {"weekday": 0, "from": "12:00", "to": "15:30"}]}],
  "employees": [{"code": "OP-SAW-1", "name": "Олег Мельник", "barcode": "OPSAW1", "job": "Оператор", "workcenter": "SAW-1", "shift": "Зміна 1 (07:00–15:30)"}],
  "bookings": [{"batch": "BATCH/IN/00001", "truck": "TRUCK-IN-1", "plate": null, "dock": "DOCK-W1", "type": "incoming",
                "scheduled": "2026-10-12T06:30:00Z", "state": "in_progress", "pickings": ["WH/IN/00128"], "partner": "Плитсервіс (демо)"},
               {"batch": "BATCH/OUT/00004", "truck": "TRUCK-OUT-1", "plate": "АА4512КТ", "dock": "DOCK-E2", "type": "outgoing",
                "scheduled": "2026-10-12T09:00:00Z", "state": "in_progress", "pickings": ["WH/OUT/00413"], "partner": "Меблі Дім (демо)"}]
}
```

Обов'язкові: `version*`, `generated_at*`, `devices[]*` з `code*`, `name*`, `protocol*`, `driver*`, `enabled*`, `signals[]*` (можливо порожній) з `code*`, `address*`, `dtype*`, `kind*`; `zones[]*` (`code*`, `polygon*` ≥ 3 точок; береться з `f3d.zone` base; якщо полігонів у base ще немає — порожній список, емулятор бере `catalog/zones.json`); `docks[]*` (base Додаток D: `code` = `stock.location.f3d_code`, `x`/`y` — координати воріт, `accepts` — назви категорій `product.category` з `f3d_accepts`; X-54); `shifts[]*` (з `resource.calendar` компанії); `employees[]*` (усі `hr.employee` з `barcode`); `bookings[]*` (`stock.picking.batch` у станах `draft/in_progress` з `dock_id`, `scheduled_date` ± 2 доби): `batch` = `name`, `truck` = `f3d_code` (єдиний код фури в 3D, base CB-06; X-15), `dock` = `dock_id.f3d_code`, `plate` = `f3d_plate` (держномер рейсу двору, `factory3d_yard` M-07; поле читається, лише якщо воно є в моделі — yard необов'язковий), порожнє або без yard → `null` (емулятор генерує номер, §8.13.2; X-49); `f3d_truck` (опис/назва фури з макета, не номер) в API-01 не передається. Приклад вище — демо після міграції yard: `TRUCK-OUT-1` (`BATCH/OUT/00004`, `WH/OUT/00413`) має `f3d_plate = АА4512КТ` (картка ваг макета), `TRUCK-IN-1` — `null`.

Коди: 200, 304, 401, 503. Ідемпотентно; ліміт — без пагінації (≈ 276 пристроїв × ~3 сигнали ≈ 400 КБ).

#### API-02 `GET /f3d/sim/health`

Без токена. 200 `{"ok": true, "module": "factory3d_iot_sim", "version": "19.0.2.0.0", "devices": 276, "signals": 1168, "panel_state": "online"}` (`signals` — усі записи `f3d.sim.signal`, включно з 151 `protocol=none`).

#### API-03 `POST /f3d/sim/events`

Тіло: `{"events": [{"ts": "2026-10-13T20:05:11+03:00", "kind": "scenario|fault|alarm|info|error", "device": "RV-05", "run_ref": "RUN/2026/0007", "sim_run_id": "r-01J…", "message": "Фільтр RV-05: 285 Па", "payload": {}}]}` (≤ 100 подій, ≤ 256 КБ). Дія: створити `f3d.sim.event` (прив'язка `run_id` за `run_ref` або `sim_run_id`); події `kind=scenario` з `payload.state in (done, failed, stopped)` переводять `f3d.sim.run.state`. Відповідь 200 `{"accepted": n, "rejected": [{"index": i, "reason": "…"}]}`; 400 при невалідному JSON; 413 при перевищенні; 401. Ідемпотентність: за `payload.event_id` (UUID від сервісу) — дублікати відкидаються з `reason="duplicate"`.

### 7.2 REST керування емулятором `/sim/v1/*` (сервіс, порт 8090, FastAPI)

Спільне: `Authorization: Bearer <SIM_API_TOKEN>` для всього, крім `GET /health`, `GET /metrics`, `POST /lpr-sink`; помилки — `{"detail": "..."}` з кодами 401 (токен), 403 (`write`-операція при `SIM_READONLY_API=1`), 404 (код не знайдено), 409 (конфлікт стану: сценарій уже запущено на тому ж пристрої), 422 (валідація pydantic), 423 (`SIM_ENABLED=0` / `stop-all`), 500. Усі часи — ISO 8601 з зоною `+03:00`/`+02:00` (`sim_now`). Коди пристроїв/сигналів — regex §2.6 ARCHITECTURE.

| ID | Метод і шлях | Тіло запиту | Відповідь 200 | Примітки |
|---|---|---|---|---|
| API-10 | `GET /status` | — | `{"enabled": true, "version": "0.1.0", "mode": "follow_odoo", "factor": 1.0, "sim_now": "…", "real_now": "…", "uptime_s": 3600, "seed": 20261012, "tick_ms": 1000, "devices": 276, "signals": 1017, "alarms": 1, "devices_fault": ["CNC-2"], "runs": [{"id": "r-01J…", "run_ref": "RUN/2026/0007", "scenario": "filter_clogged", "state": "running", "started": "…", "params": {…}}], "protocols": {"opcua": "ok", "modbus": "ok", "bacnet": "ok", "mqtt": "ok", "helvarnet": "ok", "biostar": "ok", "woodstore": "ok", "jobs": "ok", "sics": "ok", "lpr": "ok", "control": "ok"}, "odoo": {"configured": true, "last_ok": "…", "stale": false, "catalog_source": "odoo"}, "catalog_hash": "sha256:…"}` | без токенів |
| API-11 | `GET /devices`, `GET /devices/{code}` | — | список/об'єкт: `{"code", "name", "protocol", "driver", "unit_id", "instance", "address", "enabled", "state": "ok|fault|offline|passive", "fault": {"reason", "note", "since"} \| null, "model": "machine", "signals": ["…"], "extra": {…стан моделі…}}` | `?protocol=`, `?state=` |
| API-12 | `POST /device/{code}/fault` / `POST /device/{code}/clear` | `{"reason": "generic|spindle|emergency|power|comm|sensor", "note": "…"}` / `{}` | `{"code": "CNC-2", "state": "fault"}` / `{"state": "ok"}` | `fault` на `passive` → 422, **крім** пасивних пристроїв P-09 з `params.lsz` (зони `FA-*`, §5.2): для них `fault`/`clear` приймаються з `reason` ∈ {`sensor` (умовчання), `generic`, `loop`} — несправність зони за R-25 (LSZ `fault`, X-36), `loop` — ще й несправність лінії (BV шлейфу); інший `reason` → 422 (X-60); повторний `fault` → 200 без змін |
| API-13 | `GET /scenarios`; `POST /scenario/{name}/start`; `POST /scenario/{name}/stop`; `GET /runs`, `GET /runs/{id}` | start: `{"run_ref": "RUN/2026/0007", "params": {…}}`; stop: `{"run_id": "r-…"}` (без `run_id` — усі запуски цього сценарію) | start 201 `{"id": "r-01J…", "scenario", "state": "running", "started", "ends": "…|null"}`; stop `{"id", "state": "stopped"}`; runs: список об'єктів як у `status.runs` + `"events": n`, `"result": {…}` | `GET /scenarios` → `[{"name", "title_uk", "group", "params_schema", "params_default", "duration_s"}]` (= §9.3) |
| API-14 | `POST /time` | `{"factor": 10.0}` і/або `{"set": "2026-10-12T07:00:00+03:00"}` | `{"factor": 10.0, "sim_now": "…"}` | `factor` 0,1…60; у `follow_odoo` `factor != 1` → 409; `set` переставляє годинник (кроком, без «розмотування» лічильників) |
| API-15 | `POST /mode` | `{"mode": "scenario|follow_odoo"}` | `{"mode": "…", "factor": 1.0}` | перехід у `follow_odoo` ставить `factor=1`; без налаштованого Odoo → 422 |
| API-16 | `GET /signals`; `GET /signals/{code}`; `PUT /signals/{code}` | PUT: `{"value": 285.0, "hold_s": 600}` або `{"release": true}` | `GET /signals`: `{"count": 1017, "items": [{"code", "value", "unit", "status": "ok|warn|alarm|stale", "ts", "device", "protocol", "kind"}]}` з `?prefix=`, `?device=`, `?status=`, `?limit=1000&offset=0` — лише рядки каталогу з протоколом (151 рядок `protocol=none` ведуть модулі-власники, X-35, X-76; `GET /signals/{code}` для них → 404 `{"detail": "computed by <модуль>"}`); PUT → `{"code", "value", "held_until"}` | PUT — «утримати значення» для тестів споживачів; `hold_s` ≤ 86 400; після закінчення модель знову веде значення |
| API-17 | `POST /reset`; `POST /stop-all`; `POST /resume` | reset: `{"keep_time": true, "seed": 20261012}` | `{"ok": true, "sim_now": "…"}` | `reset` зупиняє всі запуски, відновлює початковий стан каталогу (номінали), не чіпає конфіг; `stop-all` = стоп-кран (значення заморожуються, 423 на команди), `resume` знімає |
| API-18 | `GET /health`; `GET /metrics` | — | health: `{"status": "ok|degraded|locked", "protocols": {…}, "uptime_s"}`; metrics: Prometheus text (`iot_sim_signal_value{code=…}`, `iot_sim_tick_seconds`, `iot_sim_protocol_up{proto=…}`, `iot_sim_events_total{kind=…}`) | без токена, лише з мережі `f3d_sim` |
| API-19 | `GET /events` | — | `{"items": [{"id": "e-…", "ts", "kind", "device", "run_id", "message", "payload"}], "next": "e-…"}` з `?since=<id>`, `?kind=`, `?device=`, `?limit=500` | кільцевий буфер 10 000 |
| — | `POST /lpr-sink` | JSON Axis (§8.13.2) | `{"received": true}` | заглушка приймача LPR для фази 1; складає у `events` як `kind=info, device=CAM-xx` |
| — | `GET /catalog/signals.csv`, `GET /catalog/devices.json` | — | файли каталогу (для `factory3d_telemetry` і тестів) | токен |

Приклад запуску сценарію (параметр рівня фільтра — `value` за схемою S-04, не `dp_pa`; X-58):

```http
POST /sim/v1/scenario/filter_clogged/start HTTP/1.1
Authorization: Bearer 3f1c…
Content-Type: application/json

{"run_ref": "RUN/2026/0007", "params": {"device": "RV-05", "value": 285, "ramp_min": 2}}

HTTP/1.1 201 Created
{"id": "r-01JA7Z3K9Q", "scenario": "filter_clogged", "state": "running", "started": "2026-10-13T20:10:00+03:00", "ends": null}
```

### 7.3 Вендорські REST-інтерфейси емулятора

Описані в §8: woodStore **API-20…API-27** (§8.5), `/jobs` **API-30…API-34** (§8.6), BioStar 2 **API-40…API-46** (§8.12).


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
| SmartGen relay (P-12) | HTTP | 8000 (контейнер `genset_relay`, мережі `f3d_sim` і `odoo_default`, на хост не публікується) | з `td_genset`: `relay_api.md` — для `td_genset` (Odoo), `/sim/v1/*` API-F-01…F-09 — для емулятора (td_genset §8.4–8.5, CI-02, X-75) |

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
    environment: {SIM_GENSET_RELAY_TOKEN: "${RELAY_SIM_TOKEN}"}   # той самий токен, що в genset_relay (X-75)
    volumes: ["iot_sim_state:/app/state"]
    ports: ["127.0.0.1:8090:8090", "127.0.0.1:4840:4840"]   # лише профіль dev; у demo — без ports
    healthcheck: {test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8090/sim/v1/health', timeout=3)"], interval: 30s, timeout: 5s, retries: 3}   # без curl у python:3.12-slim (X-90)
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
  genset_relay:                            # td_genset §8.5, запит CI-02 (X-75)
    build: ${TD_GENSET_PATH}/relay          # з репозиторію td_genset, профіль D700 (fake_relay.py)
    profiles: ["demo", "dev"]
    networks: [f3d_sim, odoo_default]       # odoo_default — щоб Odoo (td_genset) достукався до genset_relay:8000
    environment: {RELAY_PROFILE: d700, RELAY_PORT: "8000", RELAY_SIM_TOKEN: "${RELAY_SIM_TOKEN}", RELAY_TIME_FACTOR: "1", RELAY_TZ: Europe/Kyiv}
    healthcheck: {test: ["CMD", "python", "-c", "import socket; socket.create_connection(('localhost', 8000), 3)"], interval: 30s, timeout: 5s, retries: 3}   # TCP-перевірка порту (td_genset §8.5, X-90)
volumes: {iot_sim_state: {}}
```

`genset_relay` (X-75, td_genset §8.5 CI-02): змінні `RELAY_PROFILE=d700`, `RELAY_PORT=8000`, `RELAY_SIM_TOKEN`, `RELAY_TIME_FACTOR=1`, `RELAY_TZ=Europe/Kyiv` (повний перелік змінних контейнера — td_genset §8.1); `RELAY_SIM_TOKEN` задається один раз у `.env` проєкту compose (поруч із `docker-compose.sim.yml`, не в репозиторії) і потрапляє в обидва контейнери: `genset_relay` (`RELAY_SIM_TOKEN`) і `iot_sim` (`SIM_GENSET_RELAY_TOKEN`, §8.2.1). Порожній токен — роутер `/sim/v1/*` у `fake_relay` вимкнений (404), емулятор працює в запасному режимі §8.14. Healthcheck — TCP-підключення до порту 8000 стандартною бібліотекою Python (`socket.create_connection`, як у td_genset §8.5): образи `python:3.12-slim` не мають `curl`, а TCP-перевірка не залежить від шляху health у `relay_api.md` (X-90). Мережа `odoo_default` потрібна Odoo (`td_genset` читає ретранслятор за `relay_api.md`); allow-list `SIM_ALLOW_OUTBOUND` стосується лише вихідних з'єднань емулятора. Власний compose стенда `td_genset` лишається для регресії ТК-01…ТК-14 (профілі `office` і `d700`).

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
| `SIM_GENSET_RELAY_URL` | URL / `http://genset_relay:8000` | P-12: REST `fake_relay` `/sim/v1/*` (td_genset §8.4, API-F-01…API-F-09) |
| `SIM_GENSET_RELAY_TOKEN` | str / порожньо | Bearer для API-F (= `RELAY_SIM_TOKEN` контейнера `genset_relay`; compose передає обом `${RELAY_SIM_TOKEN}`, §8.1.4, X-75); порожньо → запасний режим §8.14 (генератор «запущений» через 15 с), X-59 |
| `SIM_GENSET_AMF_MASTER` | `hgm` \| `ats` / `hgm` | умовчання параметра `amf_master` сценарію `blackout` (S-03): `hgm` — варіант A (HGM6120N веде AMF, ATyS у Remote control, D-23), `ats` — варіант B (td_genset CI-01) |
| `SIM_GENSET_KW_MAX` | float / `558` | верхня межа навантаження генератора в острові R-22 (= `rated.kw_esp` профілю D700, td_genset §8.2; API-F-04 відхиляє більше), X-67; межа — ESP 558 кВт (аварійний режим при втраті мережі), а не PRP 507 кВт, при якому td_genset рахує автономність (R-02 td_genset) — X-78 |
| `SIM_HELVAR_VERSION` | `1` \| `2` / `2` | версія HelvarNet, яку «прошито» в роутери емулятора (§8.10.4): `2` — приймає `V:1` і `V:2`, відповідає у версії запиту; `1` — на запит із `V:2` відповідає помилкою 18 (incompatible version) — для ТК фолбеку bms R-31 (X-64) |
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
| `…/JobOrderControl/JobOrderList` | `<C>.JobManagement.JobOrderControl.JobOrderList` | `ISA95JobOrderAndStateDataType[]` | R | черга завдань: `JobOrder.JobOrderID` = `"WO%05d" % mrp.workorder.id` (`WO00013`) у `follow_odoo` і в `scenario`, коли планувальник бере завдання з Odoo; синтетичні завдання планувальника без Odoo — `SIM-%05d`; випуск карти розкрою `/jobs` (API-33) — `cj-…` (machine_connect Q-17, X-38); завершені завдання лишаються в списку зі станом `Ended/Completed` до кінця зміни (R-17), `Description` (назва операції), `WorkMasterID` (= маршрут/специфікація), `StartTime`, `EndTime`, `Priority`, `JobOrderParameters` (`PlannedOrderQuantity`, `OrderNumbers=[WH/MO/00231]`, `JobName`), `State` — `6:ISA95StateDataType` з `BrowsePath` до стану |
| `…/JobOrderControl/{Store, StoreAndStart, Start, Update, Stop, Cancel, Clear, Pause, Resume, Abort, RevokeStart}` | `<C>.JobManagement.JobOrderControl.<Method>` | Method | виклик з логіном | ПРИПУЩЕННЯ (OPC 10031-4): вхід `JobOrder: ISA95JobOrderDataType` (Store/StoreAndStart/Update) або `JobOrderID: String` + `Comment: LocalizedText[]`; вихід `ReturnStatus: UInt64` (0 = ok). У режимі `follow_odoo` виклики приймаються, але завдання веде Odoo (`ReturnStatus=0`, подія INFORMATION «ignored in follow_odoo») |
| `JobManagement/JobOrderResults` | `<C>.JobManagement.JobOrderResults` | `6:ISA95JobResponseProviderObjectType` | — | `JobOrderResponseList: ISA95JobResponseDataType[]` (`JobOrderID`, `JobResponseID`, `StartTime`, `EndTime`, `JobState`, `JobResponseData`: `RunsCompleted`, `GoodQuantity`, `ActualProductionTime`); методи `RequestJobResponseByJobOrderID(JobOrderID) → JobResponse`, `RequestJobResponseByJobOrderState(JobOrderStateList[]) → JobResponses[]` |
| `ManufacturerSpecific` | `<C>.ManufacturerSpecific` | FolderType | R | `PowerActive` (Double, кВт — дзеркало PM5560), `SpindleRpm` (CNC/NEST), `VacuumKpa` (GANTRY-1), `CyclesToday` (GANTRY-1) |

Стани ISA-95 завдання (`State[].StateText`, ПРИПУЩЕННЯ за OPC 10031-4): `NotAllowedToStart`, `AllowedToStart`, `Running`, `Interrupted` (під-стани `Held`, `Suspended`), `Ended` (`Completed`, `Cancelled`), `Aborted`. Відповідність Odoo: `pending/waiting → NotAllowedToStart`, `ready → AllowedToStart`, `progress → Running`, `progress + blocked → Interrupted/Held`, `done → Ended/Completed`, `cancel → Ended/Cancelled`. Елемент зі станом `Ended/Completed` (і `Ended/Cancelled`) **не видаляється** з `JobOrderList` до початку наступної зміни (обидва режими) — споживач (machine_connect R-12) бачить завершення в списку; дубль `JobOrderResponseList` у `JobOrderResults` — як було (X-38).

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
- **Адреси — PDU за документом вендора, без загального «номер − 1»** (D-20, X-42). Правило перетворення номера з документа в PDU (на дроті) — за вендором, як energy R-01; для пристроїв без опублікованої карти (ПРИПУЩЕННЯ: Elektronikon, TEDOM, ADAM) — PDU як у telemetry Додаток C.2 / energy Додаток A.1:

| Пристрій (unit) | Нотація документа | PDU | Порядок слів 32/64 біт | Джерело |
|---|---|---|---|---|
| PM5560 (1–8, 11–59) | 1-based (`3060`) | `N − 1` (3060 → 3059) | старше слово першим (`big`) | Schneider «PM5560/PM5563 Modbus Register List» |
| SUN2000 (61–68), LUNA2000 (69) | у документі вже PDU (`32080`) | `N` | `big` | Huawei «SUN2000MB Modbus Interface Definitions» |
| Elektronikon Mk5 (70) | 1-based (`3002`), ПРИПУЩЕННЯ | `N − 1` (3002 → 3001) | `big` | telemetry Додаток C.2 |
| ATyS p (71) | Annexe III, десяткові (`20483`) — уже PDU | `N` | `big` | Socomec «ATyS p Instruction manual 542 001 D», Annexe III |
| TEDOM (72) | ПРИПУЩЕННЯ — адреси задано одразу в PDU (`40000…`) | `N` | `big` | energy Додаток A.1 |
| ADAM-6050/6060/6017/6015 (80–96) | Modicon `0xxxx` / `4xxxx` (`00001`, `40001`) | coil/DI `0000N` → `N − 1`; HR `4NNNN` → `N − 40001` | **молодше слово першим (`little`)** — лічильники й float (D-20, X-43) | ADAM-6000 User Manual Ed.12, Appendix B.2 |

  Байти в слові — big-endian для всіх. У цьому документі (таблиці §8.4–§8.13, AC, ТК, каталог Додатка A) адреса Modbus подається **PDU-формою** `u<unit> fc<n> pdu<addr>[+<count>]` (+ `<type>[ little]` у каталозі; telemetry Q-04, telemetry R-24 шаблон (0) — X-72; у картах пристроїв з кількома unit — без `u<unit>`, unit — за таблицею нижче); номер за документом вендора — довідково. Емулятор відповідає саме за PDU-адресами: запит на PDU = «номер документа» для PM5560/Elektronikon/ADAM отримає сусідній регістр або виняток 0x02.
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
| 85 | ADAM-6050 IO-6: SPARK-1 (DI0–DI3), SMOKE-CTRL (DI4–DI6, DO0, DO1) | §8.11.3 |
| 86 | ADAM-6060 IO-7: GATE-W (DI0, DI1, DI4, DO0, DO2, DO4), GATE-E (DI2, DI3, DI5, DO1, DO3, DO5) | §8.13.1 |
| 90 | ADAM-6017 AI-1: DUST-1 витрата (AI0), перепад (AI1), SPRINKLERS (AI2), AIR-RING (AI3) | §8.9.6 |
| 96 | ADAM-6015 RTD-1: T1 (RTD0–2), T2 (RTD3–5) | §8.9.6 |

У проді кожен пристрій має свою IP-адресу (`f3d.source.address = host:502`, unit 1 або адреса RS-485 за шлюзом); каталог сигналів лишається тим самим — змінюється лише `source`.

#### 8.4.2 Додаток P-02 — ADAM-6050 для верстатів без інтерфейсу

**Еталон:** Advantech «ADAM-6000 Series User Manual», Ed. 12 (листопад 2022), Appendix B.2 «ADAM-6000 I/O Modbus Mapping Tables» — https://advdownload.advantech.com/productfile/Downloadfile4/1-2B6FKTG/ADAM-6000_User_Manaul_Ed.12-FINAL.pdf (переглянуто 13.10.2026). Карта модуля ADAM-6050 (12 DI, 6 DO, лічильники 32 біт на кожному DI):

| Адреса (документ) | Адреса (PDU, X-72; `u80…u83`) | Функція | Опис | R/W |
|---|---|---|---|---|
| 00001–00012 | `fc2 pdu0+12` (або `fc1`) | 01/02 | DI value, канали 0–11 (1 = замкнено/активно) | R |
| 00017–00022 | `fc1 pdu16+6` (запис FC 05) | 01/05 | DO value, канали 0–5 | R/W |
| 00033 + 4·k | `fc1 pdu<32+4k>` | 01/05 | Counter start (1)/stop (0) каналу k (k = 0…11) | R/W |
| 00034 + 4·k | запис FC 05 `pdu<33+4k>` | 05 | Clear counter (1) | W |
| 00035 + 4·k | `fc1 pdu<34+4k>` | 01/05 | Clear overflow | R/W |
| 00036 + 4·k | `fc1 pdu<35+4k>` | 01/05 | DI latch status | R/W |
| 40001 + 2·k … 40002 + 2·k | `fc3 pdu<2k>+2` `u32 little` | 03 | Counter/Frequency value каналу k, 32 біт, **молодше слово першим** (`little`, D-20/X-43): перший регістр = біти 0–15 | R |
| 40301 | `fc3 pdu300` | 03 | DI value всі канали (біти 0–11) | R |
| 40303 | `fc3 pdu302` (запис FC 06) | 03/06 | DO value всі канали (біти 0–5) | R/W |
| 40211–40212 | `fc3 pdu210+2` | 03 | Module name (`0x6050`) | R |

Розкладка верстатів (кожен верстат: `DI(2m)` = «в роботі» (сухий контакт реле «цикл/подача»), `DI(2m+1)` = «аварія» (контакт реле несправності), лічильник на `DI(2m)` = цикли/деталі; `m` = порядок у модулі 0…4):

| unit | модуль | m=0 | m=1 | m=2 | m=3 | m=4 |
|---|---|---|---|---|---|---|
| 80 | IO-1 | SLIDE-1 (DI0/1, cnt 40001 = `u80 fc3 pdu0+2`) | VSAW-1 (DI2/3, 40005 = `pdu4+2`) | SAND-1 (DI4/5, 40009 = `pdu8+2`) | PRESS-1 (DI6/7, 40013 = `pdu12+2`) | GLUE-1 (DI8/9, 40017 = `pdu16+2`) |
| 81 | IO-2 | SPRAY-1 | AUTOSPRAY-1 | DRY-1 | UV-1 | HINGE-1 |
| 82 | IO-3 | BOX-1 | PACK-1 | PACK-2 | PACKLINE-1 | ASM-1 |
| 83 | IO-4 | ASM-2 | ASM-3 | ASM-4 | ASM-5 | ASM-6 |

DI10/DI11 кожного модуля — резерв (0). DO0–DO5 — резерв (запис приймається, без ефекту, логується). Поведінка: `DI(run)=1` ⇔ `CurrentState=WORKING` за R-14; `DI(fault)=1` ⇔ збій (R-15); лічильник += 1 на кожну деталь/цикл (R-16), після 65 535 перенос у старше слово (другий регістр; machine_connect ТК-05); `Clear counter` обнуляє. Модуль відповідає на `40211 = 0x6050` (`fc3 pdu210`).

### 8.5 Додаток P-03 — «woodStore API v1» (портал STORETEQ P-500)

**ПРИПУЩЕННЯ, звірити з HOMAG** (інтерфейс woodStore закритий; Q-02). Контракт наш; клієнт — `factory3d_machine_connect` (плагін `woodstore`). Базова адреса `http://iot-sim:8082/api/v1`, заголовок `X-Api-Key: <SIM_WOODSTORE_APIKEY>`, JSON UTF-8, часи ISO 8601. Помилки: `{"error": {"code": "NOT_FOUND|CONFLICT|VALIDATION|LOCKED", "message": "…"}}`.

| ID | Метод і шлях | Запит | Відповідь | Примітки |
|---|---|---|---|---|
| API-20 | `GET /status` | — | `{"state": "idle|moving|picking|placing|blocked|error", "position": {"x": 36.2, "y": 27.5, "z": 4.8}, "vacuum_kpa": -71.9, "cycles_today": 373, "cycles_total": 184210, "hours": 11240.5, "current_job": "wj-00412" \| null, "aisles": [{"no": 1, "gate_open": false}, …9], "alarms": [], "ts": "…"}` | `blocked` — прохід відкрито (ворота зі світловою завісою), портал не заходить (README макета) |
| API-21 | `GET /stacks` | `?product=DSP16-SON`, `?row=3` | `[{"id": "PLT-04C", "row": 4, "col": 3, "product": "DSP16-SON", "lot": "DSP16-SON-2610-114", "qty": 38, "max": 60, "reserved": 10, "locked": false, "updated": "…"}, …]` (23 стоси з ненульовим `qty` у демо + порожні місця) | `id` = код комірки `PLT-xx` = `stock.location.barcode`; кількість стосів з `qty > 0` — сигнал `equipment/GANTRY-1/stacks`, який обчислює machine_connect (`MC-DERIVED`, рядок 334 Додатка A; емулятор його не веде, X-76) |
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

**Еталон:** Schneider Electric «PM5560 / PM5563 / PM5563RD Modbus Register List» (xlsx у FAQ FA234017 «Modbus register list for PM5000 series» — https://www.se.com/ww/en/faqs/FA234017/, переглянуто 13.10.2026) і FAQ FA237865 «Formula to Calculate the Energy 64-bit INT in PM5000 Series» (https://www.se.com/ww/en/faqs/FA237865/: енергія — INT64, приклад регістрів 3204/3206; Float32-копії з прошивки 1.3.7 від 2700). Номери нижче — 1-based holding registers документа Schneider; на дроті — **PDU = номер − 1** (колонка «PDU», §8.4.1, X-42); Float32 big-endian (старше слово першим), INT64 — 4 регістри, старше слово першим. **Авторитетне джерело — xlsx; підмножина нижче звірена з публічними витягами; звірити при закупівлі прошивки (Q-12).** MasterPact MTZ2 / Micrologic X (IFE) у емуляторі **не** окремий unit: вводи Q1/Q2 представлені PM5560 unit 1/2 (вимірювання) — стан вимикача дає регістр 2x18 нижче (ПРИПУЩЕННЯ, замість карти IFE).

#### 8.7.1 Карта регістрів (однакова для всіх unit 1–8, 11–59)

| Регістр (документ) | Адреса (PDU, X-72) | Назва | Тип | Одиниця | Масштаб | R/W | Емулятор |
|---|---|---|---|---|---|---|---|
| 30–49 | `fc3 pdu29+20` | Meter Name | UTF-8 (20 рег.) | — | — | R | `"PM-<код>"` (`PM-SAW-1`, `PM-Q1`) |
| 50–69 | `fc3 pdu49+20` | Meter Model | UTF-8 | — | — | R | `"PM5560"` |
| 70–89 | `fc3 pdu69+20` | Manufacturer | UTF-8 | — | — | R | `"Schneider Electric"` |
| 130–131 | `fc3 pdu129+2` | Serial Number | UINT32 | — | — | R | `2026000000 + unit` |
| 1637–1639 | `fc3 pdu1636+3` | Firmware X.Y.Z | UINT16 ×3 | — | — | R | 2, 7, 4 |
| 2014 | `fc3 pdu2013` | Number of Phases | UINT16 | — | — | R | 3 |
| 2015 | `fc3 pdu2014` | Number of Wires | UINT16 | — | — | R | 4 |
| 2016 | `fc3 pdu2015` | Power System Configuration | UINT16 | — | — | R | 11 (3PH4W Wye Gnd) |
| 2017 | `fc3 pdu2016` | Nominal Frequency | UINT16 | Гц | 1 | R | 50 |
| 2029–2030 | `fc3 pdu2028+2` | CT Primary / CT Secondary | UINT16 | А | 1 | R | вводи 1600/5, фідери 630/5, споживачі 100/5 |
| 2025–2026, 2027 | `fc3 pdu2024+2`, `pdu2026` | VT Primary / Secondary | F32 / UINT16 | В | 1 | R | 400 / 400 (без ТН) |
| 3000–3001 | `fc3 pdu2999+2` | Current A | F32 | А | 1 | R | R-01 |
| 3002–3003 | `fc3 pdu3001+2` | Current B | F32 | А | 1 | R | |
| 3004–3005 | `fc3 pdu3003+2` | Current C | F32 | А | 1 | R | |
| 3006–3007 | `fc3 pdu3005+2` | Current N | F32 | А | 1 | R | ≈ 2 % від фазного |
| 3010–3011 | `fc3 pdu3009+2` | Current Avg | F32 | А | 1 | R | `S·1000/(√3·400)` |
| 3020–3021 / 3022–3023 / 3024–3025 | `fc3 pdu3019+2` / `pdu3021+2` / `pdu3023+2` | Voltage A-B / B-C / C-A | F32 | В | 1 | R | 400 ± 1 % |
| 3026–3027 | `fc3 pdu3025+2` | Voltage L-L Avg | F32 | В | 1 | R | |
| 3028–3029 / 3030–3031 / 3032–3033 | `fc3 pdu3027+2` / `pdu3029+2` / `pdu3031+2` | Voltage A-N / B-N / C-N | F32 | В | 1 | R | 230 ± 1 % |
| 3036–3037 | `fc3 pdu3035+2` | Voltage L-N Avg | F32 | В | 1 | R | |
| 3054–3055 / 3056–3057 / 3058–3059 | `fc3 pdu3053+2` / `pdu3055+2` / `pdu3057+2` | Active Power A / B / C | F32 | кВт | 1 | R | P/3 ± 3 % |
| 3060–3061 | `fc3 pdu3059+2` | **Active Power Total** | F32 | кВт | 1 | R | `energy/…/p_now`; від'ємне = віддача в мережу (вводи, R-13) |
| 3062–3067 | `fc3 pdu3061+6` | Reactive Power A/B/C | F32 | кВАр | 1 | R | |
| 3068–3069 | `fc3 pdu3067+2` | Reactive Power Total | F32 | кВАр | 1 | R | `P·tan(acos cosφ)` |
| 3070–3075 | `fc3 pdu3069+6` | Apparent Power A/B/C | F32 | кВА | 1 | R | |
| 3076–3077 | `fc3 pdu3075+2` | Apparent Power Total | F32 | кВА | 1 | R | `√(P²+Q²)` |
| 3078–3083 | `fc3 pdu3077+6` | Power Factor A/B/C | F32 | — | 1 | R | |
| 3084–3085 | `fc3 pdu3083+2` | **Power Factor Total** | F32 (знак — чотириквадрантний) | — | 1 | R | cos φ за `PROFILE` (0,82–0,97) |
| 3110–3111 | `fc3 pdu3109+2` | Frequency | F32 | Гц | 1 | R | 50,00 ± 0,02 |
| 3204–3207 | `fc3 pdu3203+4` | **Active Energy Delivered (Into Load)** | INT64 | Вт·год | 1 | R | накопичувальний лічильник R-03 → `…/kwh_total` (energy Додаток A.1, X-34); `kwh_shift` з нього обчислює energy (R-11 energy, X-35) |
| 3208–3211 | `fc3 pdu3207+4` | Active Energy Received (Out of Load) | INT64 | Вт·год | 1 | R | > 0 лише на вводах при експорті → `energy/cells/Q*/kwh_export` |
| 3212–3215 | `fc3 pdu3211+4` | Active Energy Delivered + Received | INT64 | Вт·год | 1 | R | |
| 3220–3223 | `fc3 pdu3219+4` | Reactive Energy Delivered | INT64 | ВАр·год | 1 | R | |
| 2700–2701 | `fc3 pdu2699+2` | Active Energy Delivered (Float32-копія) | F32 | кВт·год | 1 | R | те саме, що 3204 / 1000 |
| 2704–2705 | `fc3 pdu2703+2` | Active Energy Received (Float32) | F32 | кВт·год | 1 | R | |
| 2018 (ПРИПУЩЕННЯ) | `fc3 pdu2017` | Breaker state (лише unit 1–8) | UINT16 | — | — | R | 0 open / 1 closed / 2 tripped — замість карти Micrologic X/IFE; на проді — інший `f3d.source` |
| 5680 | `fc3 pdu5679` (запис FC 06/16) | Command Semaphore (FAQ FA234017) | UINT16 | — | — | R/W | повертається, запис логується; команда 2020 «Reset All Energies» → обнулення 3204+ (лише `write_enabled` споживача) |

Невизначені регістри в діапазоні 0–6000 повертають 0 (не виняток) — так поводиться реальний PM5xxx для зарезервованих адрес? **Ні** — емулятор повертає виняток 0x02 поза описаними діапазонами, щоб тести ловили хибні адреси.

#### 8.7.2 Агрегація (R-01, R-13)

`meter.py` рахує: споживач (unit 11–59) — `P` з моделі пристрою (верстат R-02, інженерія `noise`), `Q = P·tan(acos PF)`; фідер (unit 3–8) — сума своїх споживачів за `energy.lines` макета (BW-1: SAW-1, SAW-2, EDGE-1, EDGE-2, CNC-1, CNC-2, SORT-1; BW-2: SAW-3, SLIDE-1, VSAW-1, NEST-1, EDGE-3, CNC-3, BORE-1, CNC-4, DOWEL-1, GANTRY-1; BW-3: SAND-1, AUTOSPRAY-1, UV-1, HINGE-1, GLUE-1, PRESS-1, SPRAY-1, DRY-1; BW-4: ASMLINE-1, ASM-1…6, PACK-1, PACK-2, BOX-1, PACKLINE-1; C1: COMPRESSOR, DUST-1, BOILER; C2: CHARGING, OFFICE, LP-1..3, RV-ALL, AHU-1, EF-*); ввід (unit 1/2) — сума секції (секція 1: QF-3, QF-2, QF-C1; секція 2: QF-1, QF-4, QF-C2) мінус СЕС/КГУ/BESS за R-13 (генерація приєднана до секції 2: PV, CHP, BESS — ПРИПУЩЕННЯ однолінійної схеми). cos φ вводу після компенсації = 0,97.

**Обчислювані величини (X-35).** `energy/consumers/*/kwh_shift`, `infra/totals/pv_now`, `infra/totals/grid_kw`, `infra/totals/export_kw`, `infra/ats/src1_ok`/`src2_ok`, `infra/ats/fail_start` обчислює `factory3d_energy` на джерелі `EN-DERIVED` (energy CE-09) з регістрів пристроїв (PM5560 3204–3207/3208–3211, SUN2000 32080, ATyS 20486/20487); у каталозі це рядки з `protocol` «—» без адреси. Емулятор такі величини протоколами не віддає й у `GET /sim/v1/signals` не публікує; `meter.py`/`ats.py` рахують їх лише як внутрішні (`World.kwh_shift`, баланс R-13, стан АВР R-22) — для моделей і юніт-тестів (AC-06).

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

**Еталон:** Huawei «SUN2000MB Modbus Interface Definitions», V200R023C10, Issue 02, 2024-02-01 (копія — https://community.jeedom.com/uploads/short-url/cEJpNRU5j3k0LvPW43eRU7nKzfr.pdf, переглянуто 13.10.2026); документ охоплює моделі SUN2000-12…25KTL-M5/MB0 — для SUN2000-115KTL-M2 карта **ідентична за цими регістрами** (спільний простір 30000/32000/40000 серії SUN2000; ПРИПУЩЕННЯ щодо повної тотожності, звірити з «SUN2000-(100KTL-115KTL) Modbus Interface Definitions»). Modbus TCP порт 502; у проді unit = «communication address» інвертора (за замовчуванням 1, документ §7.2.2.3), у емуляторі 61–68. Типи: U16/I16/U32/I32/STR, gain — дільник. **Адреси в документі Huawei — уже PDU**: колонка «Регістр» = PDU на дроті (`N`, без «− 1»; §8.4.1, X-42).

| Адреса (PDU, X-72) | К-сть | Назва | Тип | Gain | Одиниця | R/W | Емулятор |
|---|---|---|---|---|---|---|---|
| `fc3 pdu30000+15` | 15 | Model | STR | — | — | RO | `"SUN2000-115KTL-M2"` |
| `fc3 pdu30015+10` | 10 | SN | STR | — | — | RO | `"HV2240…0<n>"` |
| `fc3 pdu30073+2` | 2 | Rated power Pn | U32 | 1000 | кВт | RO | 115,000 |
| `fc3 pdu30075+2` | 2 | Maximum active power Pmax | U32 | 1000 | кВт | RO | 125,000 |
| `fc3 pdu<32016+2k>` | 1 | PV<k+1> voltage (k = 0…9) | I16 | 10 | В | RO | 650–780 вдень, 0 вночі |
| `fc3 pdu<32017+2k>` | 1 | PV<k+1> current | I16 | 100 | А | RO | за потужністю |
| `fc3 pdu32064+2` | 2 | DC power | I32 | 1000 | кВт | RO | `P_ac / 0,986` |
| `fc3 pdu32066` / `pdu32067` / `pdu32068` | 1 | Grid line voltage AB / BC / CA | U16 | 10 | В | RO | 400 ± 1 % |
| `fc3 pdu32069` / `pdu32070` / `pdu32071` | 1 | Phase A / B / C voltage | U16 | 10 | В | RO | 230 |
| `fc3 pdu32072+2` / `pdu32074+2` / `pdu32076+2` | 2 | Phase A / B / C current | I32 | 1000 | А | RO | `P/(√3·400)` |
| `fc3 pdu32078+2` | 2 | Peak active power of current day | I32 | 1000 | кВт | RO | макс за добу |
| `fc3 pdu32080+2` | 2 | **Active power** | I32 | 1000 | кВт | RO | R-11 (`infra/pv/PV-INV-k/p_kw`); сума ×8 = `infra/totals/pv_now` |
| `fc3 pdu32082+2` | 2 | Reactive power | I32 | 1000 | кВАр | RO | 0 |
| `fc3 pdu32084` | 1 | Power factor | I16 | 1000 | — | RO | 1,000 |
| `fc3 pdu32085` | 1 | Grid frequency | U16 | 100 | Гц | RO | 50,00 |
| `fc3 pdu32086` | 1 | Efficiency | U16 | 100 | % | RO | 98,4 |
| `fc3 pdu32087` | 1 | Internal temperature | I16 | 10 | °C | RO | 25 + 0,25·P% |
| `fc3 pdu32088` | 1 | Insulation resistance | U16 | 1000 | МОм | RO | 3,000 |
| `fc3 pdu32089` | 1 | **Device status** | E16 | — | — | RO | enum нижче |
| `fc3 pdu32090` | 1 | Fault code | U16 | — | — | RO | 0; при збої — 2032 (Grid loss) / 2064 (Internal fault) |
| `fc3 pdu32091+2` / `pdu32093+2` | 2 / 2 | Startup time / Shutdown time | Epoch s | 1 | с | RO | схід/захід сонця |
| `fc3 pdu32106+2` | 2 | Accumulated energy yield | U32 | 100 | кВт·год | RO | накопич. → `infra/pv/PV-INV-k/kwh_total` (energy Додаток A.1) |
| `fc3 pdu32114+2` | 2 | **Daily energy yield** | U32 | 100 | кВт·год | RO | `infra/pv/PV-INV-k/kwh_today`; обнулення о 00:00 |
| `fc3 pdu40000+2` (запис FC 16/06) | 2 | System time (local) | Epoch s | 1 | с | RW | `sim_now`; запис приймається (лише `write_enabled` споживача) |
| `fc3 pdu42000` (запис FC 16/06) | 1 | Power grid standard code | U16 | — | — | RW | 0 |

Enum `Device status` (32089), підмножина, яку використовує емулятор (значення за документом Huawei): `0x0000` Standby: initializing; `0x0001` Standby: detecting insulation resistance; `0x0002` Standby: detecting irradiation; `0x0003` Standby: grid detecting; `0x0100` Starting; `0x0200` **On-grid**; `0x0201` Grid connection: power limited; `0x0300` Shutdown: fault; `0x0301` Shutdown: command; `0x0303` Shutdown: communication disconnected (blackout); `0xA000` Standby: no irradiation (ніч). Повний перелік — документ, §4 «Device status».

#### 8.9.2 Huawei LUNA2000 (BESS, unit 69)

**Еталон (частково):** регістри 37000+ описані в «SUN2000 (3–10KTL-M1) Modbus Interface Definitions» (ESS через інвертор) і широко використовуються інтеграціями; для промислової LUNA2000-200KWH-2H1 з PCS LUNA2000-100KTL-M1 Huawei публікує «LUNA2000B ESS Modbus Port Definitions» (https://support.huawei.com/enterprise/en/doc/EDOC1100311915, 2023-06-13; текст недоступний без входу) — **ПРИПУЩЕННЯ: C&I-система віддає ті самі регістри 37000-серії; звірити.**

Регістр = PDU (як SUN2000, §8.4.1). Діапазони регістрів **не перекриваються** (X-51): кожне 32-бітне значення займає два регістри `N…N+1`, і жодна інша величина не має адреси всередині цього діапазону.

| Адреса (PDU, X-72) | К-сть | Займає | Назва | Тип | Gain | Одиниця | Емулятор |
|---|---|---|---|---|---|---|---|
| `fc3 pdu37000` | 1 | 37000 | Running status | U16 | — | 0 offline, 1 standby, 2 running, 3 fault, 4 sleep | `infra/bess/state` (R-13) |
| `fc3 pdu37001+2` | 2 | 37001–37002 | Charge/Discharge power | I32 | 1 | Вт (+ заряд, − розряд) | `infra/totals/bess_kw·1000` |
| `fc3 pdu37003` | 1 | 37003 | Bus voltage | U16 | 10 | В | 760 (адреса — за документом Huawei SUN2000 ESS; X-51) |
| `fc3 pdu37004` | 1 | 37004 | **SOC** | U16 | 10 | % | `infra/totals/bess_soc` |
| `fc3 pdu37006` | 1 | 37006 | Working mode | U16 | — | 2 = maximise self-consumption, 4 = time-of-use | 4 |
| `fc3 pdu37014+2` | 2 | 37014–37015 | Total charge | U32 | 100 | кВт·год | накопич. → `infra/bess/kwh_charge_total` (energy Додаток A.1) |
| `fc3 pdu37016+2` | 2 | 37016–37017 | Total discharge | U32 | 100 | кВт·год | накопич. → `infra/bess/kwh_discharge_total` (energy Додаток A.1) |
| `fc3 pdu37018+2` / `pdu37020+2` | 2 / 2 | 37018–37019 / 37020–37021 | Current-day charge / discharge capacity | U32 | 100 | кВт·год | обнулення 00:00; ПРИПУЩЕННЯ емулятора — у документі SUN2000 ESS денні лічильники мають адреси 37015/37017, які тут зайняті лічильниками total (їх читає energy без змін, X-51) |
| `fc3 pdu37022` | 1 | 37022 | Battery temperature | I16 | 10 | °C | 25 + 0,05·\|P\| |
| `fc3 pdu37046+2` | 2 | 37046–37047 | Rated capacity | U32 | 1 | Вт·год | 387 000 (2 шафи) |
| `fc3 pdu37050` | 1 | 37050 | SOH | U16 | 10 | % | 99,0 |

#### 8.9.3 Atlas Copco GA 37 VSD+ / Elektronikon Mk5 (COMPRESSOR, unit 70)

**ПРИПУЩЕННЯ, звірити з Atlas Copco** (карту Modbus TCP Mk5 вендор видає за серійним номером — Q-05; публічно доступний лише опис Mk IV через ComBox-S). Макет регістрів емулятора (holding, номери 1-based; на дроті **PDU = номер − 1**, як telemetry Додаток C.2 — `HR 3002` → `addr 3001`; §8.4.1, X-42):

| Регістр | Адреса (PDU) | Назва | Тип | Масштаб | Одиниця | Емулятор (R-08) |
|---|---|---|---|---|---|---|
| 3001 | `fc3 pdu3000` | Machine status | U16 | — | 0 stopped, 1 running loaded, 2 running unloaded, 3 shutdown/fault, 4 standby (VSD мін.) | `equipment/COMPRESSOR/state` |
| 3002 | `fc3 pdu3001` | Outlet pressure | U16 | ×0,001 | бар | `pressure_bar` (6,5–7,0) |
| 3003 | `fc3 pdu3002` | Element outlet temperature | U16 | ×0,1 | °C | `temp_c` 78–88; > 110 → fault |
| 3004 | `fc3 pdu3003` | Dew point | I16 | ×0,1 | °C | 3,0 |
| 3005 | `fc3 pdu3004` | Ambient temperature | I16 | ×0,1 | °C | 24,0 (компресорна) |
| 3010 | `fc3 pdu3009` | Load (VSD output) | U16 | ×1 | % | `load` |
| 3011 | `fc3 pdu3010` | Motor speed | U16 | ×1 | об/хв | 1 200 + 36·load |
| 3012 | `fc3 pdu3011` | Motor current | U16 | ×0,1 | А | `37·load/100·1000/(√3·400·0,95)` |
| 3020–3021 | `fc3 pdu3019+2` | Running hours | U32 | ×1 | год | `hours` |
| 3022–3023 | `fc3 pdu3021+2` | Loaded hours | U32 | ×1 | год | ≈ 0,65·hours |
| 3024–3025 | `fc3 pdu3023+2` | Load cycles | U32 | ×1 | — | +1 на цикл load/unload |
| 3030 | `fc3 pdu3029` | Service timer (до ТО) | U16 | ×1 | год | 160 (= 18 000 − 17 840, MR/00033) |
| 3040 | `fc3 pdu3039` | Shutdown code | U16 | — | 0 / 11 (high temp) / 12 (motor overload) / 20 (comm) | за збоєм |
| 3100 | `fc3 pdu3099` (запис FC 06) | Setpoint pressure | U16 | ×0,001 | бар | 7,000; RW (лише `write_enabled`) |

Дві машини GA 37 (×2 у паспорті) представлені одним контролером-майстром (ES-керування) — unit 70; розподіл навантаження між машинами всередині моделі.

#### 8.9.4 Socomec ATyS p 1600 (ATS-1, unit 71)

**Еталон:** Socomec «ATyS p — Automatic Transfer Switching Equipment, Instruction manual 542 001 D», **Annexe III** (адреси Modbus, десяткові; https://www.nhp.com.au/public/assets/pim/Original/10043/Socomec-Transfer-Switch-ATyS-P-User-Manual.pdf, переглянуто 14.10.2026; перелік — td_genset ARCHITECTURE §1.1) — D-21, X-41. Адреси Annexe III — уже PDU (`N`, §8.4.1); FC 03 (читання), FC 06 (запис 21761). Коди значень — за Annexe III; ті самі, що читають energy (Додаток A.1/A.2, R-02 п. 4) і td_genset (R-05: `ats_position_i_value = 2`, `ats_position_ii_value = 3`).

| Адреса (PDU, X-72) | Назва (Annexe III) | Тип | Значення | Емулятор (R-22) | Сигнал |
|---|---|---|---|---|---|
| `fc3 pdu20480+2` | Date / time | U32 | секунди | `sim_now` (UNIX с; ПРИПУЩЕННЯ щодо формату поля — звірити з Annexe III) | — |
| `fc3 pdu20482` | Operating Mode | U16 | `0x0000` Manual, `0x0001` Locked, `0x0010` Auto, `0x0020` Remote, `0x0040` Inhibit | `0x0020` (32, Remote control) при `amf_master=hgm` (варіант A, D-23); `0x0010` (16, Auto) при `amf_master=ats` (варіант B) | `infra/ats/mode` |
| `fc3 pdu20483` | Switch Position | U16 | 0 Unknown, 1 Position 0, 2 Position I, 3 Position II | 2 (I, мережа) у нормі; 1 (0) — мертва зона ODT 3 с під час переключення; 3 (II, генератор) в острові | `infra/ats/position` |
| `fc3 pdu20484` | Source 2 Start Generator relay State | U16 | 0 / 1 | варіант B: 1 від наказу пуску (1FT після втрати мережі) до зупинки (після 2CT); варіант A — 0 (пуск веде HGM6120N) | `infra/ats/gen_start` |
| `fc3 pdu20485` | Priority | U16 | пріоритетне джерело | 1 (джерело 1 — мережа; ПРИПУЩЕННЯ щодо кодування) | — |
| `fc3 pdu20486` | Source 1 State | U16 | 0 Under threshold, 1 Present, 2 Available | 2 у нормі; 0 під час `blackout`; після повернення мережі — 1 на 2 с (стабілізація), далі 2 | `infra/ats/src1_state` |
| `fc3 pdu20487` | Source 2 State | U16 | 0 Under threshold, 1 Present, 2 Available | 0 (генератор стоїть); 1 — генератор запущений, `gen_ok` ще немає; 2 — `gen_ok` (API-F-01) або запасний режим §8.14 | `infra/ats/src2_state` |
| `fc3 pdu21761` (запис FC 06) | Set Operating Mode (запис) | U16 | коди як 20482 | запис FC 06 приймається лише при `SIM_WRITE_ACCEPT=1`, змінює 20482, подія `command`; інакше виняток 0x04 | — |
| `fc3 pdu57635` | Modbus slave address | U16 | 1…247 | 71 | — |

`infra/ats/src1_ok`, `src2_ok`, `fail_start` емулятор не віддає — їх обчислює energy з 20486/20487/20484 (R-14 energy, X-35). Таймери АВР емулятора — заводські умовчання мануалу 542 001 D, у регістрах не віддаються: 1FT 3 с, 2AT 5 с, ODT 3 с, 1RT 180 с, 2CT 180 с, 2ST 30 с (td_genset ARCHITECTURE §1.1); у варіанті A час переключення й повернення задає HGM6120N (`fake_relay`, R-22).

Додаткові регістри емулятора (**ПРИПУЩЕННЯ**, поза переліком Annexe III вище; споживачі їх не читають, на реальному ATyS p не використовувати): 20490–20492 Source 1 voltage L1-L2 / L2-L3 / L3-L1 (U16, В: 400 / 0 при `blackout`), 20493 Source 1 frequency (U16 ×0,1 Гц: 50,0), 20500–20502 Source 2 voltage (U16, В: 400, коли генератор працює), 20503 Source 2 frequency (U16 ×0,1 Гц), 20510–20511 Transfer counter (U32: 17, +1 на кожне переключення в II), 20512–20513 Last transfer time (U32 epoch s: 05.10.2026 18:42, картка `infra.py`). Колишні 20480 «Switch position», 20481/20482 «Source available», 20483 «Operating mode» (0/1/2), 20484 «Fault summary», 20485 «Transfer in progress», 20520/20521 «Timers» (ПРИПУЩЕННЯ за ATyS g) — **вилучено (X-41)**.

#### 8.9.5 TEDOM Quanto D800 NG (CHP, unit 72)

**ПРИПУЩЕННЯ, звірити з TEDOM** (точки даних ProCon не опубліковано — Q-06). Адреси задано одразу в **PDU** (колонка «Регістр» = адреса на дроті, як energy Додаток A.1; §8.4.1, X-42).

| Адреса (PDU, X-72) | Назва | Тип | Масштаб | Одиниця | Емулятор (R-12) |
|---|---|---|---|---|---|
| `fc3 pdu40000` | State | U16 | — | 0 stop, 1 starting, 2 running, 3 fault, 4 cooling down | `infra/chp/state` |
| `fc3 pdu40001` | Electrical power | U16 | ×1 | кВт | `infra/totals/chp_kw` (400 удень, 800 увечері) |
| `fc3 pdu40002` | Heat output | U16 | ×1 | кВт | `heat_kw` (497 / 856) |
| `fc3 pdu40003` | Gas consumption | U16 | ×0,1 | м³/год | 109 / 199 |
| `fc3 pdu40004` / `pdu40005` | Supply / return water temperature | U16 | ×0,1 | °C | 90 / 70 |
| `fc3 pdu40006` | Engine speed | U16 | ×1 | об/хв | 1 500 |
| `fc3 pdu40007` (запис FC 06) | Load setpoint | U16 | ×1 | % | 50 (RW, `write_enabled`) |
| `fc3 pdu40010+2` | Running hours | U32 | ×1 | год | 3 412 |
| `fc3 pdu40012+2` | Number of starts | U32 | ×1 | — | 211 |
| `fc3 pdu40014+2` | Energy produced total | U32 | ×1 | кВт·год | накопич. → `infra/chp/kwh_total` (energy Додаток A.1) |
| `fc3 pdu40020` | Alarm code | U16 | — | 0 / 101 (gas pressure low) / 205 (overtemp) | за збоєм |

#### 8.9.6 Аналогові й дискретні модулі ADAM для інженерії (unit 84, 90, 96)

**Еталон:** ADAM-6000 User Manual Ed.12, Appendix B.2 (карти ADAM-6017: AI 40001–40008 raw U16, float IEEE754 40031–40046, burnout 00121–00128, high/low alarm 00131–00148; ADAM-6015: 7 каналів RTD, AI 40001–40007, float 40031–40044, burnout 00121–00127; ADAM-6050 — §8.4.2).

| unit | Модуль | Канал | Сигнал | Діапазон (R-20) | Адреси (документ → PDU-форма, §8.4.1, X-72) |
|---|---|---|---|---|---|
| 90 | ADAM-6017 (4–20 мА, type code `0x0107`) | AI0 | `equipment/DUST-1/airflow_m3h` | 0…32 000 м³/год | raw 40001 → `u90 fc3 pdu0`, float 40031–40032 → `u90 fc3 pdu30+2` (мА) |
| 90 | | AI1 | `equipment/DUST-1/filter_dp_kpa` | 0…4 кПа | raw 40002 → `u90 fc3 pdu1`, float 40033–40034 → `pdu32+2` |
| 90 | | AI2 | `equipment/SPRINKLERS/pressure_bar` | 0…16 бар | raw 40003 → `u90 fc3 pdu2`, float 40035–40036 → `pdu34+2` |
| 90 | | AI3 | `equipment/AIR-RING/pressure_bar` | 0…16 бар | raw 40004 → `u90 fc3 pdu3`, float 40037–40038 → `pdu36+2` |
| 90 | | AI4–AI7 | резерв | — | raw 40005–40008 (`u90 fc3 pdu4+4`) = 0, burnout 00125–00128 (`u90 fc1 pdu124+4`) = 1 |
| 96 | ADAM-6015 (PT100, type code `0x0020`, −50…+150 °C) | RTD0–RTD2 | `energy/transformers/T1/temp_c` (макс. з трьох обмоток) | −50…+150 °C | raw 40001–40003 → `u96 fc3 pdu0+3`, float 40031–40036 → `u96 fc3 pdu30+6` (°C) |
| 96 | | RTD3–RTD5 | `energy/transformers/T2/temp_c` | | raw 40004–40006 → `u96 fc3 pdu3+3`, float 40037–40042 → `pdu36+6` |
| 96 | | RTD6 | резерв (burnout 00127 = 1) | | 40007 → `u96 fc3 pdu6` |
| 84 | ADAM-6050 | DI0 / DI1 | `equipment/DUST-1/state` (вентилятори в роботі / аварія) | — | 00001 / 00002 → `u84 fc2 pdu0` / `pdu1` |
| 84 | | DI8 (лічильник) | `infra/water/m3_total` (1 імп = 10 л, Apator MWN50 NK) | — | лічильник 40017–40018 → `u84 fc3 pdu16+2` (`u32 little`); старт 00065 → `u84 fc1 pdu64` |
| 84 | | DI2–DI7, DI9–DI11, DO0–DO5 | резерв | — | 0 |

**R-20 масштабування ADAM:** `raw = round(65535·(mA − 4)/16)` для 4–20 мА, де `mA = 4 + 16·(eng − lo)/(hi − lo)`; для RTD `raw = round(65535·(t + 50)/200)`; float-регістри — інженерна одиниця (мА або °C) IEEE754, **молодше слово першим** (`40031` = молодше, як лічильники ADAM; D-20, X-43). Споживач читає або raw (і масштабує за каталогом `lo/hi`), або float.

#### 8.9.7 Режим `follow_odoo` (XML-RPC лише читання)

Користувач `SIM_ODOO_USER` (`f3d_sim_reader`) з API-ключем; дозволені методи — `search_read`, `read`, `search_count`, `fields_get`; будь-який інший виклик у коді неможливий (клієнт-обгортка `OdooReadOnly` має лише ці методи). Період `SIM_ODOO_FOLLOW_S` (10 с) — «швидкі» запити, `SIM_ODOO_FOLLOW_SLOW_S` (60 с) — «повільні».

| Період | Модель | Домен | Поля | Куди в емулятор |
|---|---|---|---|---|
| 10 с | `mrp.workorder` | `[("state","in",["ready","progress","done"]), ("date_finished",">=", sim_now − 1 день) або state != done]` | `id, name, state, workcenter_id, production_id, qty_produced, qty_production, duration, duration_expected, date_start, working_state` | `World.workcenters[code].job`, стани ISA-95 (§8.3.2), R-14, R-16 (`pieces_out` ← `qty_produced` як нижня межа) |
| 10 с | `mrp.workcenter` | `[]` | `code, working_state` | `blocked` → `Flags.Error`/`DI fault`, `CurrentState=ERROR` (CNC-2 у демо) |
| 60 с | `stock.picking.batch` | `[("dock_id","!=",False), ("state","in",["draft","in_progress"])]` | `name, dock_id, scheduled_date, state, picking_ids, f3d_code, f3d_truck` (base M-04) + `f3d_plate` (yard M-07 — лише якщо поле є, перевірка `fields_get`) | `World.trucks` (R-29): код фури в 3D = `f3d_code` (base CB-06), опис = `f3d_truck` (назва з макета, не номер), держномер = `f3d_plate` (порожнє / немає yard → генерується, §8.13.2), ворота = `dock_id.f3d_code` (`DOCK-W1`; `barcode` воріт — `UNLOAD-1`, base Додаток D); X-15, X-49 |
| 60 с | `stock.picking` | `[("id","in", batch.picking_ids)]` | `name, state, picking_type_code, move_ids.quantity/product_uom_qty` | прогрес розвантаження/завантаження (R-29) |
| 60 с | `hr.employee` | `[("barcode","!=",False)]` | `name, barcode, resource_calendar_id, job_title` | `World.people` (R-28) |
| 60 с | `resource.calendar.attendance` | календарі з попереднього запиту | `dayofweek, hour_from, hour_to` | розклад зміни (R-28, R-24) |
| 60 с | `maintenance.request` | `[("stage_id.done","=",True), ("write_date",">=", last_poll)]` + поле `x_request_id` рівня 0 через `x_f3d_signal` (`[("x_request_id","!=",False)]` → `x_code`, `x_request_id.stage_id.done`) | `equipment_id.f3d_code`, `f3d_signal_id.code` (якщо телеметрія є) | `World.maintenance_closed` → скидання `drift` (R-09) |
| 1 год | `GET /f3d/sim/devices` (API-01) | — | весь реєстр | перезавантаження каталогу (без переривання значень) |

При помилці читання > `SIM_ODOO_STALE_S` — `odoo_stale=true` в `/status`, емулятор продовжує з останнім відомим станом (не переходить у `scenario` сам); після відновлення — повна синхронізація. У `follow_odoo` планувальник зміни/фур/людей **не** генерує власних завдань і фур, але продовжує фізику (АКБ, фільтри, баланс) і рух техніки за завданнями з Odoo (`current_task` ← `stock.picking` з `vehicle`?) — у фазі 1 рух техніки в `follow_odoo` іде за розкладом R-19 без прив'язки до документів.

### 8.10 Додаток P-08 — BACnet/IP (вентиляція, опалення, котельня) і HelvarNet (освітлення)

#### 8.10.1 BACnet/IP — спільне

- Еталон об'єктної моделі — ASHRAE/ANSI Standard 135 (BACnet), об'єкти `analog-input` (AI), `analog-output` (AO), `analog-value` (AV), `binary-input` (BI), `binary-value` (BV), `multi-state-value` (MSV), `life-safety-zone` (LSZ), `life-safety-point` (LSP), `device`. Транспорт BACnet/IP (Annex J), UDP 47808. Реалізація — `bacpypes3`: один `BIPRouter`-застосунок на 47808 з пристроєм-роутером (`device 99`, «F3D Sim Router») і віртуальна мережа номер 2, у якій живуть пристрої 101…200 (A-04). `Who-Is` без параметрів через роутер повертає `I-Am` усіх пристроїв; `Who-Is 101 125` — лише RoofVent.
- Властивості кожного об'єкта: `object-identifier`, `object-name` (ASCII, напр. `RV-05_SupplyAirTemp`), `object-type`, `present-value`, `status-flags`, `event-state`, `out-of-service`, `units` (`degrees-celsius`, `cubic-meters-per-hour`, `pascals`, `percent`, `kilowatts`), `description` (uk, UTF-8). Для AI/AO/AV — `cov-increment` (AI темп. 0,2; витрата 50; Па 5; % 1); COV-підписки (`SubscribeCOV`) підтримуються на всіх AI/BI/MSV/LSZ. Запис `present-value` в AO/AV/BV — дозволений з пріоритетом 8…16 (`priority-array`); у RO-об'єкти — `WriteAccessDenied`.
- Device-об'єкт: `vendor-name "Hoval"` (101–125), `"VTS"` (130), `"VENTS/Systemair"` (131–133), `"Kalvis (emulated)"` (140), `"Siemens"` (200); `model-name`, `firmware-revision "sim-0.1"`, `protocol-version 1`, `protocol-revision 19`, `max-apdu-length-accepted 1476`, `segmentation-supported both`. Hoval RoofVent / TopTronic C: вендорські списки точок BACnet публічно не знайдено (Q-04); режими й сигнали взяті з «Hoval RoofVent RH/RC/RHC/R Operation manual» 4 214 745-en-06 (https://d24wsxjsjg3bg4.cloudfront.net/PRODUCTS/VENTILATION/RoofVent/RoofVent-RC/BA_RoofVent_4214745_v06_en_2024-01-29-124839_rsiq.pdf, переглянуто 13.10.2026): режими `VE` Ventilation, `VEL` Ventilation reduced, `AQ` Air quality (`AQ_REC`, `AQ_ECO`, `AQ_VE`), `REC` Recirculation, `EA` Exhaust air, `SA` Supply air, `ST` Standby, локально `Off`; реле перепаду тиску фільтрів із заводським налаштуванням **250 Па (приплив) / 350 Па (витяжка)**. Перелік об'єктів нижче — ПРИПУЩЕННЯ на основі цього мануалу.

#### 8.10.2 Пристрої RV-01…RV-25 (device 101…125), AHU-1 (130), EF-ELEC/EF-CMP/EF-CHG (131/132/133)

| Об'єкт | object-name | Одиниця | R/W | Значення / правило |
|---|---|---|---|---|
| AI:1 | `<C>_SupplyAirTemp` | °C | R | `ventilation/units/<C>/supply_c` (R-23) |
| AI:2 | `<C>_ExtractAirTemp` | °C | R | `…/indoor_c` |
| AI:3 | `<C>_SupplyAirFlow` | м³/год | R | `…/airflow_m3h` |
| AI:4 | `<C>_FreshAirFilterDp` | Па | R | `…/filter_dp_pa` (R-09; RV-05 стартує з 285) |
| AI:5 | `<C>_ExtractAirFilterDp` | Па | R | 0,8·AI:4 |
| AI:6 | `<C>_OutdoorTemp` | °C | R | `World.outdoor_c` (9,0 у демо; добовий хід ±3) |
| AI:7 | `<C>_HeatOutput` | кВт | R | `heat_kw` |
| AI:8 | `<C>_FanPower` | кВт | R | `p_now` (= дзеркало PM5560 u55 RV-ALL частка) |
| AO:1 | `<C>_HeatingValve` | % | RW | `…/heating_valve` (у %, 0…100 — сигнал зберігається в %, `scale=1`, X-39; R-23); запис → утримання 10 хв, подія `command` |
| AO:2 | `<C>_FanSpeedSetpoint` | % | RW | `k·100` |
| AV:1 | `<C>_RoomSetpointDay` | °C | RW | 18,0 (`INDOOR_SET_C`) |
| AV:2 | `<C>_RoomSetpointNight` | °C | RW | 14,0 |
| BI:1 | `<C>_Running` | — | R | `state == "on"` |
| BI:2 | `<C>_Fault` | — | R | збій (`fault reason != None`) |
| BI:3 | `<C>_FilterAlarmFresh` | — | R | `AI:4 > 250` |
| BI:4 | `<C>_FilterAlarmExtract` | — | R | `AI:5 > 350` |
| BI:5 | `<C>_FrostProtection` | — | R | 0 |
| BV:1 | `<C>_Enable` | — | RW | 1; запис 0 → `state=standby`, AI:3 = 0 |
| MSV:1 | `<C>_OperatingMode` | states: 1 VE, 2 VEL, 3 AQ, 4 REC, 5 EA, 6 SA, 7 ST, 8 Off | RW | за календарем (R-23): RV у складах ГП (RV-21/22) — REC; приймання/відвантаження — VE («Приплив і витяжка» макета); решта — AQ (= «Рекуперація» макета → `AQ_ECO`); поза зміною — VEL; `Off` → BI:1=0 |
| MSV:2 | `<C>_AQState` | 1 AQ_REC, 2 AQ_ECO, 3 AQ_VE | R | для MSV:1=3 |
| MSV:3 | `<C>_LocalMode` | 1 Auto, 2 Off, 3 REC, 4 SA, 5 EA, 6 VE | RW | 1 |

AHU-1 (130): ті самі об'єкти з `object-name` `AHU-1_*`; додатково `AI:9 AHU-1_RoomPressure` (Па, −5…−15) і `BI:6 AHU-1_BoothExtractInterlock` (1 = витяжка камер працює). EF-ELEC/EF-CMP/EF-CHG (131–133): `BI:1 Running`, `AI:2 RoomTemp` (29,5 / 24,0 / 22,0), `AI:3 AirFlow`, `BV:1 Enable` (RW), `AV:1 ThermostatSetpoint` (RW, 28 / 30 / —), для EF-CHG `BI:7 EF-CHG_ChargingActive` (1 = є заряджання, вентилятор має працювати; `BI:1=0 ∧ BI:7=1` довше 60 с → подія `alarm` (рівень ALARM) «EF-CHG: не працює під час заряджання — водень!»; стан `stopped_charging` — тривога й заявка за bms A-20 / Додаток B.2, X-40). Складені стани для каталогу: RV/AHU `…/state` = BI:1 `running`/`stopped`, BI:2 → `fault`, BI:5 → `frost` (bms B.1); EF-CHG = BI:1 / BI:7 → `stopped_charging` (bms B.2).

#### 8.10.3 Котельня BOILER (device 140)

| Об'єкт | object-name | Одиниця | R/W | Значення (R-10) |
|---|---|---|---|---|
| AI:1 | `BOILER_SupplyTemp` | °C | R | `equipment/BOILER/supply_c` (78 ± 0,4) |
| AI:2 | `BOILER_ReturnTemp` | °C | R | `return_c` = supply − 20·load − 0 |
| AI:3 | `BOILER_SiloLevel` | % | R | `silo_fill` (62 → 15 → 95) |
| AI:4 | `BOILER_FlueGasTemp` | °C | R | 160 при роботі, 25 у резерві |
| AI:5 | `BOILER_HeatOutput` | кВт | R | `max(0, heat_need − chp_heat)` |
| AI:6 | `BOILER_BriquettesToday` | кг | R | 860 + витрата |
| AV:1 | `BOILER_SupplySetpoint` | °C | RW | 80 |
| BI:1 / BI:2 | `BOILER_K1_Running` / `BOILER_K2_Running` | — | R | за `boilers_on` (0/1/2) |
| BI:3 | `BOILER_Fault` | — | R | збій |
| BI:4 | `BOILER_AugerRunning` | — | R | 1 під час подачі |
| BI:5 | `BOILER_SiloLow` | — | R | `AI:3 < 20` |
| BV:1 | `BOILER_Enable` | — | RW | 1 |
| MSV:1 | `BOILER_State` | 1 standby, 2 K1, 3 K1+K2, 4 fault | R | `equipment/BOILER/state` |

#### 8.10.4 HelvarNet (щити освітлення LP-1…LP-3, групи LT-*)

**Еталон:** Helvar «HelvarNet Overview» (Designer 4.2.18 Help File, с. 409–503; https://aca.im/driver_docs/Helvar/HelvarNet-Overview.pdf, переглянуто 14.10.2026; номери команд, формат кадрів, параметр `A`, часткові кадри `$` і біти C:110 — за цим документом, як у плагіні bms §8.1; X-40, X-64). Підтверджено: TCP-порт роутера **50000** (за замовчуванням), UDP 50001; ASCII-повідомлення `>` … `#`, ≤ 1 500 байт; відповідь на запит у тому ж форматі; частковий кадр закінчується `$`; роутери DIGIDIM 905/910, IMAGINE 920/945/950; «Push Messages» увімкнено. Відкриті для заліза питання (чи підтримує прошивка Imagine 950 заводу `V:2`, C:161, C:164 і відповідь на `A:1`) — bms Q-04, CONSISTENCY «Питання до замовника» № 13.

Формат: запит `>V:<v>,C:<команда>[,<параметри>]#`, `v ∈ {1, 2}`; **відповідь — у версії запиту** (`>V:1,…#` → `?V:1,…#`; X-64): на запит `?V:<v>,C:<команда>[,…]=<значення>#`, помилка `!V:<v>,C:<команда>[,…]=<код>#`; довга відповідь ділиться на часткові кадри: усі, крім останнього, закінчуються `$` замість `#`, кожен починається з того самого заголовка `?V:<v>,C:<c>[,G:<g>|,@адреса]=`. Параметри: `G` група (1–16383), `B` блок (1–8), `S` сцена (1–16), `L` рівень (0–100), `P` пропорція (−100…100), `F` час переходу (1/100 с), `T` час, `K` constant light (0/1), `O` force store (0/1), `A` — підтвердження команди (`A:1`: роутер відповідає кадром `!…=0#` після виконання; без `A` — лише push), `@c.r.s.d` адреса пристрою (cluster.router.subnet.device). Версія роутерів емулятора — `SIM_HELVAR_VERSION` (§8.2.1): `2` — приймаються `V:1` і `V:2`; `1` — запит із `V:2` → `!V:2,C:<c>[,…]=18#` (incompatible version), `V:1` обробляється (ТК фолбеку bms R-31). Коди помилок: 0 ok, 1 invalid group, 2 invalid cluster, 3 invalid router, 4 invalid subnet, 5 invalid device, 6 invalid sub-device, 7 invalid block, 8 invalid scene, 9 cluster does not exist, 10 router does not exist, 11 device does not exist, 12 property does not exist, 13 invalid raw message size, 14 invalid message type, 15 invalid message command, 16 missing ASCII terminator, 17 missing ASCII parameter, 18 incompatible version.

Команди, які реалізує емулятор:

| C | Назва | Приклад | Відповідь емулятора |
|---|---|---|---|
| 11 | Recall Scene (Group) | `>V:2,C:11,G:12,B:1,S:3,F:500#`; з підтвердженням `>V:2,C:11,G:12,B:1,S:3,F:200,A:1#` | застосовує сцену групи (R-24: S1=100 %, S2=75, S3=50, S4=25, S5=10, S6=0 … S16); push `>V:2,C:11,G:12,B:1,S:3,F:500#` усім клієнтам; при `A:1` — ще й відповідь відправнику `!V:2,C:11,G:12,B:1,S:3,F:200,A:1=0#` (параметри запиту як отримано, код 0 = виконано; помилка — код ≠ 0, напр. 1 invalid group) |
| 12 | Recall Scene (Device) | `>V:2,C:12,@1.2.1.5,B:1,S:3,F:500#` | те саме для світильника |
| 13 | Direct Level (Group) | `>V:2,C:13,G:12,L:60,F:100#`; з підтвердженням `>V:2,C:13,G:19,L:50,F:200,A:1#` | рівень групи; push; при `A:1` — відповідь `!V:2,C:13,G:19,L:50,F:200,A:1=0#` (bms R-37) |
| 14 | Direct Level (Device) | `>V:2,C:14,@1.2.1.5,L:60,F:100#` | |
| 15 / 16 | Direct Proportion (Group / Device) | `>V:2,C:15,G:12,P:-20,F:100#` | |
| 17 / 18 | Modify Proportion (Group / Device) | | |
| 19 / 20 / 21 / 22 / 23 / 24 | Emergency Function/Duration Test (Group/Device), Stop Tests | `>V:2,C:19,G:40#` | лише для групи аварійного освітлення `EMERGENCY` (G:40): імітація тесту 60 с / 60 хв, результат у C:170+ |
| 101 | Query Clusters | `>V:2,C:101#` | `?V:2,C:101=1#` |
| 102 | Query Routers | `>V:2,C:102,@1#` | `?V:2,C:102,@1=1,2,3#` |
| 103 | Query LSIB (last scene in block) | `>V:2,C:103,G:12,B:1#` | `?…=3#` |
| 104 | Query Device Type | `>V:2,C:104,@1.2.1.5#` | `?…=1537#` (DALI LED driver, тип за Helvar) |
| 105 / 106 | Query Description (Group / Device) | `>V:2,C:105,G:12#` | `?…=Розкрій#` (назва зони) |
| 107 / 108 | Query Workgroup Name / Membership | | `F3D` / список |
| 109 | Query LSIG (last scene in group) | `>V:2,C:109,G:12#` | `?…=1#` |
| 110 | **Query Device State** | `>V:2,C:110,@1.2.1.5#` | 32-бітна маска за документом Helvar (X-40): `0x00000001` NSDisabled, `0x00000002` NSLampFailure, `0x00000004` NSMissing, `0x00000008` NSFaulty, `0x00000010` NSRefreshing, `0x00000100` NSEM_Resting (аварійний світильник вимкнений на живленні від АКБ), `0x00000400` NSEM_InEmergency (немає мережі, живлення від АКБ), `0x08000000` NSCommsError; маска несправностей споживача — `0x0800000E` (LampFailure, Missing, Faulty, CommsError; bms §8.2.2). Норма `=0#`; збій світильника (S-15 `fault_device`) → `=2#`; `blackout` — світильники групи EMERGENCY `=1024#` (`0x400`), решта — рівень 0 без бітів несправності; пристрій поза складом — помилка `!…=11#` |
| 111 / 112 / 113 / 114 | Query Device Is Disabled / Lamp Failure / Is Missing / Is Faulty | | `=0#` / `=1#` |
| 150 | Query Device Measurement | `>V:2,C:150,@1.2.1.65#` | датчик 322: освітленість лк (денне світло R-24) |
| 151 | Query Device Inputs | | присутність 0/1 |
| 152 | **Query Load Level** | `>V:2,C:152,@1.2.1.5#` | `?V:2,C:152,@1.2.1.5=75#` (`lighting/groups/LT-*/level` — рівень групи = рівень будь-якого її світильника) |
| 160 / 161 | Query Power Consumption (Device / Group) | `>V:2,C:161,G:12#` | Вт: `n·126·level/100` (`lighting/groups/LT-*/p_now`) |
| 164 | Query Group (склад групи) | `>V:2,C:164,G:12#` | адреси пристроїв групи через кому: `?V:2,C:164,G:12=@1.2.1.1,@1.2.1.2,…,@1.2.1.27#`; не більше 64 адрес (і ≤ 1 500 байт) у кадрі — довший склад ділиться на часткові кадри `$`: G:16 (91 пристрій) → `?V:2,C:164,G:16=@1.2.3.1,…,@1.2.3.64$` + `?V:2,C:164,G:16=@1.2.4.1,…,@1.2.4.27#` (bms R-35, X-64); група без пристроїв → `!…=1#` |
| 165 | Query Groups | `>V:2,C:165#` | `?…=1,2,…,32,40#` |
| 166 / 167 | Query Scene Names / Scene Info | | назви сцен uk («Зміна», «Прибирання», «Ніч»…) |
| 170…176 | Query Emergency test time/state, battery charge/time, lamp time | | результати тестів EMERGENCY |
| 185 / 186 / 187 / 188 / 189 | Query Time / Longitude / Latitude / Time Zone / DST | `>V:2,C:185#` | `sim_now` epoch; 30.52 / 50.45 / +120 / 1 |
| 190 / 191 | Query Software Version / HelvarNet Version | `>V:2,C:191#` | `?…=5.4.0#` / `=<SIM_HELVAR_VERSION>#` (умовчання `2`; bms R-31 визначає за нею версію сеансу) |

Адресація емулятора: cluster 1; router 1 = LP-1, 2 = LP-2, 3 = LP-3; subnet 1…4 = лінії DALI роутера (по 64 світильники на лінію, паспорт `lighting_control` Imagine 950). **Розкладка світильників по лініях — правило bms R-06** (X-65): для груп щита в порядку каталогу (`G` = 1…32): якщо на поточній лінії вже зайнято `used > 0` адрес і група з `n` світильників не вміщується в залишок (`n > 64 − used`) — група починається з нової лінії (`line += 1`, `used = 0`); далі `n` пристроїв поспіль з адреси `used + 1`, з переходом на наступну лінію при 64 (лише для групи, більшої за лінію). Результат — таблиця `dali_devices` **bms Додаток A.1** (джерело істини, як каталог за X-34); емулятор будує склад груп тим самим правилом і має збігатися з нею дослівно (AC-65). Приклади: LP-1 — `LT-RCV-1` `@1.1.1.1-4`, `LT-RCV-2` `@1.1.1.5-8` … `LT-PKS` `@1.1.1.49-50`; LP-2 — `LT-CUT` `@1.2.1.1-27`, `LT-EB` `@1.2.1.28-54`, `LT-CNC` `@1.2.2.1-27` (27 > 64 − 54), `LT-SORT` `@1.2.2.28-39`, `LT-FAC` `@1.2.3.1-64;@1.2.4.1-27`; LP-3 — `LT-ASM` `@1.3.1.1-15` … `LT-OUT-1` `@1.3.1.59-62`, `LT-OUT-2` `@1.3.2.1-4` (4 > 64 − 62) … `LT-OUT-7` `@1.3.2.21-24`. Склад групи віддається командою C:164; датчики 322 — пристрої 65…70 кожної лінії (presence/lux), без змін. Номери груп `G` = порядковий номер LT-* у каталозі (1…32), G:40 = EMERGENCY. Push при кожній зміні рівня групи: `>V:<v>,C:13,G:<n>,L:<lvl>,F:<f>#` усім TCP-клієнтам роутера (версія — `SIM_HELVAR_VERSION`).

### 8.11 Додаток P-09 — пожежна сигналізація Siemens Cerberus PRO (BACnet/IP тільки читання), GreCon BS 7, D+H CPS-M1

#### 8.11.1 Панель FACP-1 (device 200)

**Еталон:** BACnet life-safety об'єкти — ASHRAE 135 §12.15 (Life Safety Point), §12.16 (Life Safety Zone); Siemens: панель Cerberus PRO FC726 віддає BACnet з ліцензійним ключем **S2 FCA2034-A1 «BACnet output, monitoring-only, life-safety objects»** (Siemens «S1 | S2 | S3 License Keys» datasheet, https://sid.siemens.com/api/khub/documents/EAQ9YtHpKnIPi1ssft0y4A/content, переглянуто 13.10.2026); типи об'єктів — за BTL-лістингом 30841 «Siemens FS20 Fire Detection System» (FC721/FC722/FC724/FC726; https://www.bacnetinternational.net/btl/listings/siemens/BTL_Listing_30841_Siemens_FS20FireDetection.pdf, переглянуто 14.10.2026): Life Safety Zone, Life Safety Point, Binary Value, Multi-State Value, Positive Integer Value — **без** Analog Value і Binary Input (fire Q-16, X-37). Склад і іменування — **ПРИПУЩЕННЯ** (Q-03): зона = LSZ, адресний елемент = LSP, шлейф/сирени/пульт = BV, лічильники = PIV; запиленість — PIV (до PICS приладу; якщо прилад її не віддає — сигнал на проді деактивується, CONSISTENCY «Питання до замовника» № 10). Запис у будь-який об'єкт панелі → `WriteAccessDenied` (D-07, FR-12); `out-of-service` не змінюється.

| Об'єкт | object-name | Властивості | Значення |
|---|---|---|---|
| LSZ:0 | `FACP-1_Panel` | `present-value` (BACnetLifeSafetyState), `mode` (BACnetLifeSafetyMode), `tracking-value`, `reliability`, `silenced`, `operation-expected`, `member-of` (усі LSZ 1–35), `zone-members` | `fire/totals/state` (X-36): `quiet(0)` / `alarm(2)` / `fault(3)` / `test-alarm(9)` (навчання) |
| LSZ:1…35 | `FA-<zone>` у порядку `fire.groups` макета: 1 FA-RCV-1 … 7 FA-RCV-7, 8 FA-SHEETS, 9 FA-HW, 10 FA-EDGE, 11 FA-PKS, 12 FA-CUT, 13 FA-EB, 14 FA-CNC, 15 FA-SORT, 16 FA-FAC, 17 FA-ASM, 18 FA-PRE, 19 FA-MAINT, 20 FA-PACK, 21 FA-POST, 22 FA-CMP, 23 FA-CHG, 24 FA-FG, 25 FA-ELEC, 26…32 FA-OUT-1…7, 33 FA-BOILER, 34 FA-SOC, 35 FA-OFFICE (приміщення дописано після котельні — № 12г; 1…33 не змінились) | ті самі + `description` («Розкрій, оптико-теплові, 12 сповіщувачів») | `fire/groups/FA-*/state` (R-25): `quiet`, `pre-alarm(1)`, `alarm(2)`, `fault(3)`, `test-alarm(9)`, `not-ready(6)` (вимкнена) |
| LSP:<id> | адреса пристрою за fire R-23 (A-09; X-79): сповіщувач зони `<loop>.<code[3:]>.<nn>` (`nn` — порядок у `fire.detectors()[zone].points`, з 1), ручний `<loop>.MCP.<nn>`, оповіщувач `<loop>.SND.<nn>`, полум'я `2.FLM.<nn>` (`nn` — порядок у `call_points()`/`sounders()`/`FLAME` у межах шлейфу `loop_of(x)`); id = `lsp_id(loop, ordinal, nn)` = `loop·10000 + ordinal·100 + nn` (`1 ≤ loop ≤ 8`, `1 ≤ ordinal ≤ 99`, `1 ≤ nn ≤ 99`), `ordinal` — номер LSZ зони для сповіщувача, псевдо-порядкові MCP=90, SND=91, FLM=92: `2.FAC.07` → 21607, `2.CNC.05` → 21405, `1.RCV-1.01` → 10101, `2.BOILER.02` → 23302, `3.SOC.01` → 33401, `3.OFFICE.08` → 33508, `1.MCP.01` → 19001, `4.MCP.09` → 49009, `2.SND.13` → 29113, `2.FLM.01` → 29201; датчики іскор / форсунки / люки (`0.SPK.<nn>` / `0.NOZ.<nn>` / `0.SV.<nn>`) — не LSP (`lsp_instance` 0; ADAM u85, §8.11.3) | `present-value`, `mode`, `reliability` (`no-fault-detected(0)` / `unreliable-other(7)` при запиленості > 90 %), `device-type` («OOH740», «OP720», «HI720», «FDM225», «FDS226», «SharpEye 40/40C-I»), `member-of` (своя LSZ) | 302 LSP з унікальними id: 222 сповіщувачі + 36 ручних + 3 полум'я + 41 оповіщувач (`device-type FDS226`, `present-value active(7)` під час тривоги) |
| PIV:<id LSP> | `<det>_Contamination` (лише 222 сповіщувачів зон) | % (ціле 0–100; ПРИПУЩЕННЯ до PICS) | `fire/groups/FA-FAC/dust` для 2.FAC.07 (PIV:21607: 82 → 90 → заявка); для інших — 5…30 (R-09, повільно); значення — `round()` моделі R-09 |
| BV:1…4 | `FACP-1_Loop<n>_Fault` | — | `fire/loops/<n>/state`: 1 лише при несправності лінії (`fault(reason=loop)`); несправність сповіщувача шлейф не змінює (X-36) |
| PIV:1 / PIV:2 / PIV:3 | `FACP-1_ActiveAlarms` / `_Faults` / `_Disablements` | шт (ціле ≥ 0) | `fire/totals/alarms|faults|disabled` |
| BV:10 | `FACP-1_SoundersActive` | — | `fire/totals/sounders_active`: 1 під час тривоги/навчання |
| BV:11 | `FACP-1_FireBrigadeTransmitted` | — | `fire/totals/brigade`: передача на пульт (через 3 с після тривоги, крім навчання) |
| MSV:1 | `FACP-1_SystemState` | 1 Normal, 2 Alarm, 3 Fault, 4 Test, 5 Disabled | `fire/totals/system_state` (новий код, X-36; `fire/totals/state` — це LSZ:0) |

Події: COV на `present-value` LSZ/LSP; додатково `UnconfirmedEventNotification` (intrinsic reporting, `notification-class 1`) з `event-type change-of-life-safety`, `message-text` uk («Тривога: сповіщувач 2.CNC.05, Присадка»). Послідовність тривоги/навчання — R-25 (за `drill_steps` макета: t=0 тривога, +3 с сирени й пульт, +6 с стоп вентиляції (BACnet RV → BV:1=0 → `ST`), +9 с димовидалення (u85 DI4=1), +12 с розблокування дверей/турнікетів (BioStar події `DOOR_UNLOCKED` 20480 на всіх дверях), +20 с аварійна зупинка верстатів зони (`Flags.ExternalEmergency=True` → ERROR)).

#### 8.11.2 Siemens Cerberus — що віддається «тільки читання»

Усі об'єкти 200 — `AccessLevel` read; `WriteProperty`/`WritePropertyMultiple` → `Error: property, write-access-denied`; `ReinitializeDevice`, `DeviceCommunicationControl` → `service-request-denied`. Тест ТБ-04.

#### 8.11.3 GreCon BS 7 (SPARK-1) і D+H CPS-M1 (SMOKE-CTRL) — ADAM-6050 unit 85

Один вхід — один сигнал каталогу (рядки 644/646 звужено до DI0/DI4, решта входів — окремі коди 684–688; X-34, fire Додаток B).

| Канал | Адреса (документ → PDU-форма, X-72) | Сигнал | Поведінка |
|---|---|---|---|
| DI0 | 00001 → `u85 fc2 pdu0` | `fire/spark/SPARK-1/state` (іскра виявлена) | імпульс 0,6 с (R-26); лічильник 40001–40002 (`u85 fc3 pdu0+2`, `u32 little`) = `fire/spark/SPARK-1/count_today` |
| DI1 | 00002 → `u85 fc2 pdu1` | `fire/spark/SPARK-1/extinguishing` — гасіння активне | імпульс 2 с після DI0 |
| DI2 | 00003 → `u85 fc2 pdu2` | `fire/spark/SPARK-1/fault` — несправність іскрогасіння | 0; сценарій `spark fault=true` → 1 |
| DI3 | 00004 → `u85 fc2 pdu3` | `fire/spark/SPARK-1/water_ok` — тиск води гасіння в нормі | 1 |
| DI4 | 00005 → `u85 fc2 pdu4` | `fire/smoke/SMOKE-VENTS/state` — клапани відкриті (кінцевики, усі 44) | R-27 |
| DI5 | 00006 → `u85 fc2 pdu5` | `fire/smoke/SMOKE-CTRL/fault` — несправність щита D+H (АКБ/живлення) | 0 |
| DI6 | 00007 → `u85 fc2 pdu6` | `fire/smoke/SMOKE-CTRL/battery` — щит D+H на живленні від АКБ | 1 під час `blackout` |
| DO0 | 00017 → `u85 fc1 pdu16` (запис FC 05) | команда «відкрити клапани» (CPS-M1 вхід «вентиляція/пожежа»), без сигналу каталогу | приймається; виконується, якщо `SIM_WRITE_ACCEPT=1` (default) → DI4 через 60 с |
| DO1 | 00018 → `u85 fc1 pdu17` (запис FC 05) | команда «закрити» | |

### 8.12 Додаток P-10 — Suprema BioStar 2 REST (СКУД)

**Еталон:** Suprema BioStar 2 Local API (документація https://bs2api.biostar2.com/ і статті підтримки: «[BioStar 2 API] How to login» https://support.supremainc.com/en/support/solutions/articles/24000072553, «How To Retrieve Events Logs» …/24000072557, «How to implement pagination for event search» …/24000106474; коди подій — BioStar 2 Device SDK «Log Management API» https://kb.supremainc.com/bs2sdk/doku.php?id=en:log_management_api; усі переглянуто 13.10.2026). Емулятор реалізує підмножину; базова адреса `https://iot-sim:8443` (TLS, самопідписаний) і `http://iot-sim:8081` (тести); JSON; усі значення в JSON — рядки, як у BioStar 2.

| ID | Метод і шлях | Запит | Відповідь | Примітки |
|---|---|---|---|---|
| API-40 | `POST /api/login` | `{"User": {"login_id": "admin", "password": "…"}}` | 200 + заголовок `bs-session-id: <uuid>`; тіло `{"User": {"user_id": "1", "name": "Administrator", "login_id": "admin", …}, "Response": {"code": "0", "link": "…", "message": "Success"}}`; помилка `{"Response": {"code": "101", "message": "Failed to login for invalid username or password"}}` (HTTP 401 у емуляторі) | сесія 30 хв бездіяльності; ≤ 10 одночасних |
| API-41 | `POST /api/logout` | заголовок `bs-session-id` | `{"Response": {"code": "0"}}` | |
| API-42 | `GET /api/users?limit=100&offset=0` | `bs-session-id` | `{"UserCollection": {"total": "36", "rows": [{"user_id": "OPSAW1", "name": "Олег Мельник", "user_group_id": {"id": "1", "name": "Виробництво"}, "start_datetime": "2001-01-01T00:00:00.00Z", "expiry_datetime": "2030-12-31T23:59:00.00Z", "disabled": "false", "card_count": "1", "face_count": "1", "login_id": ""}]}}` | `user_id` = `hr.employee.barcode` з API-01 (OPSAW1…); + `1` Administrator |
| API-43 | `GET /api/devices` | | `{"DeviceCollection": {"rows": [{"id": "5390001", "name": "ACR-IN BioEntry W3 (прохідна)", "device_type_id": {"id": "62", "name": "BioEntry W3"}, "status": "1", "ip": "10.90.1.11", "port": "51211", "door": "1"}, …]}}` | id: ACR-IN 5390001, ACR-ELEC 5390002, ACR-CHG 5390003, ACR-PAINT 5390004, ACR-SRV 5390005; TURN-1 — не пристрій, а двері з рідером ACR-IN |
| API-44 | `GET /api/doors` | | `{"DoorCollection": {"rows": [{"id": "1", "name": "Турнікет TURN-1 (вхід персоналу)", "entry_device_id": {"id": "5390001"}, "status": "1" (closed/locked), "open_duration": "5"}, {"id": "2", "name": "Електрощитова"}, {"id": "3", "name": "Зарядна"}, {"id": "4", "name": "Склад ЛФМ"}, {"id": "5", "name": "Серверна"}]}}` | |
| API-45 | `POST /api/events/search` | `{"Query": {"limit": 100, "offset": 0, "conditions": [{"column": "datetime", "operator": 3, "values": ["2026-10-14T03:00:00.000Z", "2026-10-14T14:00:00.000Z"]}, {"column": "device_id.id", "operator": 0, "values": ["5390001"]}], "orders": [{"column": "datetime", "descending": false}]}}` | `{"EventCollection": {"total": "71", "rows": [{"id": "133", "server_datetime": "2026-10-14T03:52:11.00Z", "datetime": "2026-10-14T03:52:10.00Z", "index": "346", "user_id": {"user_id": "OPSAW1", "name": "Олег Мельник", "photo_exists": "false"}, "user_group_id": {"id": "1", "name": "Виробництво"}, "device_id": {"id": "5390001", "name": "ACR-IN BioEntry W3 (прохідна)"}, "door_id": [{"id": "1", "name": "Турнікет TURN-1"}], "event_type_id": {"code": "4102"}, "tna_key": "1", "is_dst": "0", "timezone": {"half": "0", "hour": "3", "negative": "0"}, "user_update_by_device": "false", "hint": "…"}]}}` | оператори: 0 EQUAL, 1 NOT_EQUAL, 2 CONTAINS, 3 BETWEEN, 4 LIKE, 5 GREATER, 6 LESS; колонки: `datetime`, `device_id.id`, `door_id.id`, `event_type_id.code`, `user_group_id.id`, `user_id.user_id`, `server_datetime`; `limit` ≤ 2000; `orders` — колонки `datetime` або `id`, `descending` `true`/`false` (без `orders` — за зростанням `datetime`, потім `id`); пагінація (X-50; стаття 24000106474; обидва режими access R-11): `offset` — рядки `offset…offset+limit−1` у порядку `orders` (рахуються від початку вибірки), `hint` (BioStar 2.8+, лише з `limit`, без `offset`) — рядки після рядка з цим `hint`; `total` — уся вибірка за умовами; також умова `id > last_id` |
| API-46 | `GET /api/event_types` | | `{"EventTypeCollection": {"rows": [{"code": "4102", "name": "Verify Success (Card)", "description": "…"}, …]}}` | коди нижче |

Коди подій (`event_type_id.code` = `mainCode·256 + subCode` за Device SDK; емулятор генерує саме їх): **4102** (0x1006) Verify success — card; **4100** (0x1004) Verify success — ID+face; **4867** (0x1303) Identify success — face; 4865 (0x1301) Identify success — fingerprint; **5120** (0x1400) Identify fail; 4352 (0x1100) Verify fail; **6400** (0x1900) Access denied (+subCode: 6401 not in access group, 6402 user inactive, 6403 expired, 6405 anti-passback); **20480** (0x5000) Door unlocked; 20736 (0x5100) Door locked; 20992 (0x5200) Door opened; 21248 (0x5300) Door closed; 21504 (0x5400) Door forced open; 21760 (0x5500) Door held open; 26368 (0x6700) Zone fire alarm; 12544 (0x3100) Device system started; 15104 (0x3B00) TCP connected. `tna_key`: «1» вхід, «2» вихід (прохідна); для дверей — порожньо. Часи — UTC `…Z`; `timezone.hour = 3` (Europe/Kyiv влітку; 2 взимку).

Поведінка (R-28): для кожного працівника з API-01 (`employees`, 35) о `06:40 + det(code) mod 20 хв` — `4102` (card), якщо `det(code) % 2 == 0`, інакше `4867` (face) (X-50), на ACR-IN з `tna_key=1`, після чого `20480` і `20992/21248` дверей TURN-1; о `15:30 + 0…20 хв` — вихід `tna_key=2`; 2–3 рази на зміну відкриття дверей ACR-ELEC/CHG/PAINT/SRV авторизованими ролями (електрик 09:51 — як у картці `infra.py`); сценарій `access_event` додає довільну подію; `fire_drill` → `20480` на всіх дверях + `26368`.

### 8.13 Додаток P-11 — двір: шлагбауми CAME (I/O), Axis License Plate Verifier (HTTP POST), автоваги (SICS)

#### 8.13.1 Шлагбауми GATE-W / GATE-E — ADAM-6060 unit 86

**Еталон:** ADAM-6000 User Manual Ed.12, Appendix B.2 (ADAM-6060: DI 00001–00006, релейні DO 00017–00022, лічильники на DI як у 6050: 40001–40012). CAME GARD LS6 має сухі контакти «відкрито/закрито» і вхід керування — тому I/O (ПРИПУЩЕННЯ щодо конкретного монтажу).

Канали — окремо для кожних воріт (GATE-W / GATE-E); адреса — документ ADAM → PDU (§8.4.1); кожен канал — окремий сигнал каталогу (рядки 654–657, 689–698; yard Додаток A).

| Канал GATE-W / GATE-E | Адреса (документ → PDU-форма, X-72) | Призначення | Сигнал (`<G>` = ворота) |
|---|---|---|---|
| DI0 / DI2 | 00001 / 00003 → `u86 fc2 pdu0` / `pdu2` | стріла відкрита (кінцевик) | `yard/gates/<G>/state` |
| DI1 / DI3 | 00002 / 00004 → `u86 fc2 pdu1` / `pdu3` | індукційна петля зайнята (машина під стрілою); лічильник 40003–40004 / 40007–40008 (`u86 fc3 pdu2+2` / `pdu6+2`, `u32 little`) = проїзди | `…/loop`, `…/passes_today` |
| DI4 / DI5 | 00005 / 00006 → `u86 fc2 pdu4` / `pdu5` | фотоелемент перешкоди | `…/photocell` |
| DO0 / DO1 | 00017 / 00018 → `u86 fc1 pdu16` / `pdu17` (запис FC 05) | команда «відкрити» (імпульс ≥ 1 с); емулятор: стріла відкривається за 5 с (DI0/DI2 = 1), закривається через 15 с після звільнення петлі | `…/cmd_open` |
| DO2 / DO3 | 00019 / 00020 → `u86 fc1 pdu18` / `pdu19` (запис FC 05) | «закрити примусово» | `…/cmd_close` |
| DO4 / DO5 | 00021 / 00022 → `u86 fc1 pdu20` / `pdu21` (запис FC 05) | «тримати відкритим» (пожежа/евакуація) — **окремий канал на ворота** (X-47): DO4 тримає лише GATE-W, DO5 — лише GATE-E; R-25 крок +12 с ставить обидва; ПРИПУЩЕННЯ монтажу — підтвердити в монтажника (CONSISTENCY «Питання до замовника» № 11, yard Q-13) | `…/cmd_hold` |

#### 8.13.2 Axis P1488-LE + AXIS License Plate Verifier — HTTP POST JSON

**Еталон:** Axis «License plate verifier API» (https://developer.axis.com/vapix/applications/license-plate-verifier-api/, переглянуто 13.10.2026): push подій HTTP POST `application/json` (або `multipart/form-data`) на налаштований URL; поля — як у документі. Емулятор (`lpr_push.py`) надсилає на `SIM_LPR_PUSH_URL` подію при `carState=new` (в'їзд у кадр) і `lost`; 3 повтори через 2/5/10 с при помилці; `Content-Type: application/json`; без автентифікації (як камера; споживач обмежує за IP/секретним шляхом). Приклад тіла (плоский JSON, значення — рядки, як в Axis):

```json
{"packetCounter": "2117397", "capture_timestamp": "1791954905507", "frame_timestamp": "1791954905507", "capture_ts": "1791954905507000000",
 "datetime": "20261014 081505507", "plateText": "AA4512KT", "plateUnicode": "АА4512КТ", "plateUTF8": "АА4512КТ", "plateASCII": "AA4512KT",
 "plateCountry": "UKR", "plateISO3166-2": "UA", "plateRegion": "", "plateRegionCode": "",
 "plateList": "f3d_bookings", "plateListMode": "allow", "plateListDescription": "BATCH/OUT/00004 DOCK-E2 Меблі Дім (демо)",
 "plateConfidence": "0.912340", "carState": "new", "roiID": "1", "geotag": {"lat": 50.45, "lon": 30.52},
 "imageType": "plate", "plateImageType": "jpeg", "plateImageSize": "0", "carMoveDirection": "in", "timeProcessing": "41",
 "plateCoordinates": [514, 570, 120, 28], "plateCoordinatesRelative": [0, 0, 120, 28], "carID": "12891",
 "GEOtarget": "GATE-W", "imagesURI": [], "imageArray": [], "imageFile": "", "imageFile2": "", "profileID": "1",
 "vehicle_info": {"view": "front", "type": "TRUCK", "color": "WHITE"},
 "camera_info": {"SerialNumber": "B8A44F000005", "ProdShortName": "AXIS P1488-LE", "IPAddress": "10.90.2.5", "MACAddress": "B8:A4:4F:00:00:05"},
 "sensorProviderID": "CAM-05"}
```

`sensorProviderID` = код камери (`CAM-05` в'їзд → `GEOtarget GATE-W`, `carMoveDirection in`; `CAM-06` виїзд → `GATE-E`, `out`). Час події (X-48): `capture_timestamp` = `frame_timestamp` = `sim_now` у мілісекундах UNIX (UTC), `capture_ts` — те саме в наносекундах, `datetime` — той самий момент у локальному часі камери (`Europe/Kyiv`, формат `YYYYMMDD HHMMSSmmm`); у прикладі — 14.10.2026 08:15:05,507 Київ = 05:15:05,507 UTC = `1791954905507`. Споживачі беруть `capture_timestamp`, поза вікном — час прийому (telemetry R-22, yard R-07 п. 4). Списки (X-48): в Axis LPV `plateList` — **назва** списку, у який потрапив номер, режим списку — `plateListMode`; емулятор веде один список дозволених номерів `f3d_bookings` (номери з `bookings` API-01 або розкладу макета): номер є в списку → `plateList="f3d_bookings"`, `plateListMode="allow"`, `plateListDescription` = «<batch> <dock> <partner>» бронювання; немає (сценарій `truck_no_booking`) → `plateList=""`, `plateListMode="none"`, `plateListDescription=""`. Номери фур (X-49): номер = `bookings[].plate` (API-01, з `stock.picking.batch.f3d_plate` yard M-07), якщо не `null`; інакше генерується детерміновано (`AA` + 4 цифри + 2 літери з det(`truck`)). Демо-номер `АА4512КТ` (картка ваг макета, `WH/OUT/00413`) належить `TRUCK-OUT-1`, а не `TRUCK-IN-1`; приклад вище — в'їзд `TRUCK-OUT-1` через GATE-W (R-29: в'їзд завжди через GATE-W). Кирилиця в `plateUnicode`, латиниця в `plateText`.

#### 8.13.3 Автоваги TRUCK-SCALE — SICS-сумісний ASCII по TCP (порт 4001)

**Еталон:** METTLER TOLEDO «MT-SICS Reference Manual» (IND400 SICS Commands, 30881805 A, 2024, https://mt.com/dam/ind/IND_PDF/2024/ind400-downloads/sics-reference-manual/30881805%20_A_MAN_RM_IND400_SICS%20Commands_EN.pdf, переглянуто 13.10.2026) — Level 0/1; ваги АКСІС 60-18-К-Е з невідомим індикатором — **ПРИПУЩЕННЯ, що індикатор підтримує SICS або еквівалент** (Q-08). Кадр: команда + `CR LF`; відповідь + `CR LF`; поля через пробіл; вага — 10 символів, вирівняна праворуч; одиниця `kg`; дискретність 20 кг; НПВ 60 000 кг.

| Команда | Відповідь | Значення |
|---|---|---|
| `S` | `S S      21380 kg` — стабільна; `S I` — не стабільно/не виконати; `S +` перевантаження (> 60 000); `S -` недовантаження | чекає стабілізації ≤ 5 с (R-30) |
| `SI` | `S S      21380 kg` або `S D      21360 kg` (динамічна) | негайно |
| `SIR` | потік `S D …`/`S S …` 2 рази/с до іншої команди | `yard/scale/TRUCK-SCALE/weight_kg`, `stable` |
| `Z` / `ZI` | `Z A` / `Z I` / `Z +` / `Z -`; `ZI D` / `ZI S` | обнулення (лише без машини) |
| `T` / `TI` | `T S      14000 kg` / `TI D …` | тара |
| `TA` / `TA <v> kg` | `TA A      14000 kg` | запит/установка тари (запис — лише `SIM_WRITE_ACCEPT`) |
| `I0` / `I1` / `I2` / `I3` / `I4` | `I0 B 0 "I0"` …; `I1 A "01" "2.30"`; `I2 A "AKSIS 60-18 (sim) 60000 kg"`; `I3 A "sim-0.1"`; `I4 A "AX2026-0001"` | ідентифікація |
| `@` | `I4 A "AX2026-0001"` | скидання |
| інше | `ES` (синтаксис) / `EL` (логіка) / `ET` (передача) | |

Поведінка: без машини — 0 ± 20 кг; при заїзді (R-29) вага зростає до брутто за 3 с (`S D`), далі стабільна (`S S`); брутто = тара 14 000 (фура) + вантаж (аркуші × 56 кг / палети × 420 кг з документа); виїзд — тара. «Остання машина АА 4512 КТ · брутто 21 380 кг» з картки макета — перший запис журналу.

### 8.14 Додаток P-12 — генератор GENSET (SmartGen HGM6120N + CMM366B-4G)

Не дублюється: використовується існуючий `fake_relay.py` з репозиторію `td_genset` (профіль D700), опис API ретранслятора — `td_genset/relay_api.md`. Емулятор запускає його як контейнер `genset_relay` (compose §8.1.4) і керує ним **лише** через REST `fake_relay` `/sim/v1/*` (td_genset §8.4, **API-F-01…API-F-09**; Bearer `SIM_GENSET_RELAY_TOKEN`, адреса `SIM_GENSET_RELAY_URL`, allow-list) у сценаріях `blackout` (S-03) і `genset_test` (S-14) за контрактом **CI-01** (td_genset §8.6; X-59). Напрямок — iot_sim → `fake_relay` (емулятор — оркестратор):

| Крок | Виклик API-F | Коли |
|---|---|---|
| стан генератора | API-F-01 `GET /sim/v1/state` → `gen_ok`, `breaker` (`mains`/`gen`), `state`, `p_kw`, `fuel_pct` | кожну 1 с, поки активний `blackout`/`genset_test`; ATyS `src2_state`, `position` (варіант A) і баланс R-13 — з нього |
| мережа (варіант `hgm`) | API-F-02 `POST /sim/v1/mains {"available": false}` / `{"available": true, "u_v": 400, "f_hz": 50.0}` | початок / кінець `blackout`; у варіанті `ats` **не** викликається (td_genset Додаток D.3) |
| пуск (варіант `ats`, `genset_test`) | API-F-03 `POST /sim/v1/remote_start {"on": true\|false}` | `ats`: через 1FT 3 с після втрати мережі (20484 = 1) / після 2CT 180 с повернення; `genset_test`: на `duration_s` |
| навантаження | API-F-04 `POST /sim/v1/load {"kw": P_genset}` | після `breaker == "gen"` (варіант A) або переключення ATyS у II (варіант B) і далі при зміні `P_genset` ≥ 1 кВт (R-22, X-67); `{"kw": 0}` — при поверненні мережі |
| збій, паливо, час, скидання, журнал | API-F-05 `fault`/`clear`, API-F-06 `fuel`, API-F-07 `time` (той самий `factor`, що API-14), API-F-08 `reset` (разом з API-17), API-F-09 `events` | сценарії/тести; `POST /time` емулятора дублюється в API-F-07, `POST /reset` — в API-F-08 |

Параметри CI-01: `blackout.amf_master` ∈ {`hgm`, `ats`} (умовчання `SIM_GENSET_AMF_MASTER=hgm`, D-23), `blackout.genset_load_kw` (явне навантаження генератора для тестів; без нього — `P_genset` за R-22), `blackout.chp_island` (X-67), `genset_test.test_on_load` (S-03, S-14). **Запасний режим** (без `fake_relay`: `SIM_GENSET_RELAY_TOKEN` порожній, контейнер недоступний або allow-list відмовив): генератор вважається запущеним через 15 с після наказу (`src2_state` 1 → 2), `P_genset` — за R-22, подія `info` «Ретранслятор генератора недоступний — запасний режим»; сценарій не стає `failed`. Сигнал `infra/genset/GENSET/state` (рядок 662, P-12) — довідковий: у `GET /sim/v1/signals` емулятор віддає `state` з останнього API-F-01 (у запасному режимі — `running`/`standby` моделі), сигнал телеметрії веде `td_genset` (міст).

### 8.15 Рушій сценаріїв і режими

- `ScenarioRunner` тримає реєстр сценаріїв (клас на сценарій, `name`, `title_uk`, `group`, `ParamsModel` (pydantic), `duration_s`, `conflicts` — множина пристроїв/ресурсів, які сценарій блокує). `start(name, params, run_ref)` → валідація → перевірка конфліктів (409) → `Run{id: "r-<ulid>", state: running, started, ends}` → корутина `run(world, params, stop_event)`; `stop(run_id)` ставить `stop_event`, сценарій зобов'язаний відкотити тимчасові зміни (`cleanup()`), стан `stopped`; природне завершення → `done` з `result`; виняток → `failed` (подія `error`). Кожна зміна стану запуску — подія `scenario` (API-03 → `f3d.sim.run.state`).
- Режим `scenario`: планувальник `World.shift_planner` генерує день за календарем (R-14: завдання на всіх РЦ за маршрутами макета; R-29: фури за `bookings` або, без Odoo, за розкладом `dist/odoo_demo.json → pickings`); сценарії накладаються на планувальник. Режим `follow_odoo`: планувальник вимкнено, стан беруть із Odoo (§8.9.7); сценарії дозволені, крім `shift` (409 «shift недоступний у follow_odoo»). Перемикання режиму (API-15) не скидає значень сигналів.
- Сценарії можуть виконуватись паралельно, якщо не конфліктують за пристроями (`machine_fault CNC-2` ∥ `filter_clogged RV-05`; `blackout` конфліктує з усім енергетичним).

### 8.16 Логування, стан, здоров'я

- Логи JSON (`SIM_LOG_JSON=1`) у stdout: `{"ts", "level", "logger", "msg", "device", "signal", "run", "proto"}`; `SecretFilter` замінює значення `SIM_*TOKEN*`, `*PASS*`, `*APIKEY*`, `bs-session-id`, `Authorization` на `***`. Рівень за замовчуванням INFO; протокольні бібліотеки — WARNING. Події (§8.2.4) — INFO; команди запису від споживачів — INFO з `proto` і адресою; відмови (`WriteAccessDenied`, 401, allow-list) — WARNING.
- `GET /sim/v1/health`: `ok` — усі сервери слухають і останній тік ≤ 3 с тому; `degraded` — хоч один сервер не стартував або тік запізнюється > 3 с, або `odoo_stale`; `locked` — `SIM_ENABLED=0`/`stop-all`. Docker HEALTHCHECK вважає `degraded` здоровим (щоб не перезапускати через Odoo), `locked` — теж.
- `GET /sim/v1/metrics`: `iot_sim_up`, `iot_sim_tick_seconds` (histogram), `iot_sim_tick_lag_seconds`, `iot_sim_signals_total`, `iot_sim_signal_value{code}` (лише для `kind=gauge|counter`), `iot_sim_alarms`, `iot_sim_protocol_up{proto}`, `iot_sim_protocol_requests_total{proto}`, `iot_sim_events_total{kind}`, `iot_sim_runs_active`, `iot_sim_odoo_last_ok_timestamp`, `iot_sim_outbound_denied_total`.
- Знімок стану — §8.2.3; при старті лог `restored snapshot from <ts> (age …)` або `fresh start from catalog`.

---

## 9. Алгоритми й правила

Позначення: `dt` — крок у sim-секундах; `dt_min = dt/60`; `r` — детермінований шум R-00 ∈ [−1, 1), новий на кожен крок **60 с sim-часу** (крок макета; між ними `r` не змінюється — так ряди з `factor=1` збігаються з кроном макета по хвилинах); `nominal`, `noise`, `rate`, `limit`, `alarm`, `threshold` — параметри сигналу з каталогу (= `x_nominal`, `x_noise`, `x_rate`, `x_limit`, `x_alarm`, `x_threshold` макета). Усі рівняння — для одного сигналу; формули для безперервного часу отримано з хвилинних формул макета множенням приросту на `dt_min`.

### 9.1 Правила поведінки сигналів (перенесення макета, `action_iot_tick`)

| ID | Правило | Формула / алгоритм | Приклад (вхід → вихід) |
|---|---|---|---|
| R-00 | Детермінований шум | `s₀ = fnv1a32(code) ⊕ seed`; на кожному хвилинному кроці `s = (s·1103515245 + 12345) mod 2³¹`, `r = s/2³⁰ − 1` | `code="equipment/COMPRESSOR/pressure_bar"`, `seed=20261012` → перші три `r`: обчислюються тестом і фіксуються як еталон (`tests/unit/golden_rng.json`) |
| R-01 | `noise` — коливання навколо номіналу | `v ← v + 0,3·(nominal − v)·dt_min + noise·r·dt_min` | тиск компресора: `v=6,5`, `nominal=6,81`, `noise=0,05`, `r=0,4`, `dt=60` → `6,5 + 0,093 + 0,02 = 6,613` |
| R-02 | `machine` — потужність верстата за станом РЦ | стан `blocked` (збій/`working_state=blocked`) → `v = 0`; стан `WORKING` (є завдання в роботі) → `v = nominal·(1 + noise·r)`; інакше (простій) → `v = rate·(1 + 0,05·r)`; `nominal` = `p_now` макета для працюючого або `0,55·P_inst`, `rate = 0,08·P_inst`, `noise = 0,08` (`signal_specs`) | SAW-1: `P_inst=24`, `nominal=12,18`, `rate=1,92`; WORKING, `r=−0,5` → `12,18·0,96 = 11,69 кВт`; простій → `1,92·0,975 = 1,87`; CNC-2 blocked → 0 |
| R-03 | `energy` — лічильник кВт·год | `E_Wh ← E_Wh + P_kW·1000·dt/3600` (PM5560 3204 INT64 Вт·год); `kwh_shift = (E_Wh − E_Wh_at_shift_start)/1000`, де початок зміни — перший `hour_from` календаря (07:00) — лише внутрішня величина емулятора (`World.kwh_shift`, для AC-06): сигнал `…/kwh_shift` обчислює energy (X-35), протоколом віддається накопичувальний 3204–3207 (`…/kwh_total`) | `P=12,18`, `dt=60` → `+203 Вт·год`; за 176 продуктивних хв + простої = `50,5 кВт·год` (як `kwh_shift` макета) |
| R-04 | Трансформатор | `S_kVA = √(P² + Q²)` секції (R-13), `temp_c = 38 + 60·S/1000 + 0,3·r` (`energy.py`), `i_a = S·1000/(√3·400)`, `cos_phi = 0,97` після компенсації; поріг `temp_c > 140` → alarm (відповідь № 24; попередження 130 — energy) | T1: `S=345` → `58,7 °C`, `i=498 А` (як у макеті 59,1/498) |
| R-05 | `drain` — АКБ навантажувача | у стані `charging`: `v ← min(95, v + 4·rate·dt_min)`; досягнуто 95 → `charging=False`, стан `idle` (повертається до завдання); не на зарядці: `v ← v − rate·(1 + 0,3·r)·dt_min`; `v ≤ limit` (20) → стан `to_charge` (їде в `Z-CHG` за R-19), на місці → `charging=True`; `rate = 0,15 %/хв` | FL-2: `v=33,9`, `r=0`, за 60 хв → `24,9`; ще 33 хв → 20 → їде заряджатися; зарядка 0→95 % за `95/(4·0,15) ≈ 158 хв` |
| R-06 | `hours` — мотогодини | `v ← v + dt/3600`, поки джерело працює: навантажувач — не `charging` і не `idle`; компресор/портал — `p_now > 0` | COMPRESSOR 17 840,8 → за зміну 8,5 год → 17 849,3 |
| R-07 | `counter` — цикли порталу | `v ← v + rate·(1 + 0,3·r)·dt_min`, поки `energy/consumers/GANTRY-1/p_now > 0`; `rate = 3 цикли/хв`; обнулення о 00:00 (`cycles_today`) | 214 → за 30 хв ≈ 304 |
| R-08 | Компресор | `load_% = clamp(25 + 60·P_prod/P_prod_max, 20, 100)`, де `P_prod` — сума `p_now` верстатів на шинопроводах, `P_prod_max = Σ P_inst·k_work`; `pressure` — R-01 навколо `nominal=6,81`, але якщо `load > 95` → `nominal` знижується на 0,02 бар/хв до 6,2; сценарій `compressor_fault` → `nominal=5,5`, `3001=3`; `pressure < 6,0` → alarm (заявка «Компресор: тиск 5,9 бар при нормі ≥ 6,0»); `temp_c = 70 + 0,2·load + 0,3·r` | макет: `load=63 %`, `pressure=6,81`; усі 35 РЦ у роботі → `load≈85 %` |
| R-09 | `drift` — забивання/запиленість | `v ← v + rate·(1 + 0,5·r)·dt_min`; після закриття заявки ТО по пристрою (`World.maintenance_closed`) або `clear` → `v = nominal`, `maintenance_closed.discard(code)`; поріг `v > threshold` → alarm, заявка (один раз, поки не закрито) | RV-05: `rate=0,05 Па/хв`, старт 285 (> 250 → alarm одразу); RV-01: 210 → 250 за ≈ 800 хв ≈ 1,7 зміни; DUST-1: `1,42 кПа`, `rate=0,0005` → 1,8 за ≈ 760 год; 2.FAC.07: 82 → 90 за 800 хв |
| R-10 | `level` — бункер котельні, котли | `v ← v − rate·(1 + 0,3·r)·dt_min·k_fire`, `rate=0,02 %/хв`, `k_fire = boilers_on` (0 → бункер не витрачається, лише 0,1·rate на обігрів шнека); `v ≤ limit (15)` → `v = nominal (95)` (поставка), подія «Бункер поповнено»; `boilers_on`: `need = heat_total_vent − chp_heat_now`; `need ≤ 0 → 0`; `need ≤ 0,85·495 → 1`; інакше `2`; `supply_c` — R-01 (78), при `boilers_on=0` `nominal=65` | макет: `heat=322`, `chp_heat=497` → 0 котлів, бункер 62 % майже не тане; `pv_cloudy` вночі взимку (`outdoor=−10`) → `need=600` → 2 котли, бункер −0,04 %/хв |
| R-11 | `solar` — СЕС | `SIM_SUN_MODEL=astral`: `elev = astral.sun.elevation(Kyiv, sim_now)`; `sun = max(0, sin(elev))/sin(elev_noon_today)`; `parabola` (макет): `h = локальна година десятковим числом`, `sun = max(0, 1 − ((h − 13)/6)²)`; `P_total = P_peak·sun·cf·(0,92 + 0,08·r)`, `P_peak = 900 кВт·0,85 = 765`, `cf` = 1 (ясно) або 0,25…0,4 (сценарій `pv_cloudy`); на інвертор `P_k = min(115, P_total/8)`; `kwh_today += P_k·dt/3600`; статус 32089: `sun=0 → 0xA000`, `0 < P < 1 кВт → 0x0001/0x0002` (старт), `≥ 1 → 0x0200`; при `blackout` → `0x0303` | 12.10 10:30 (ясно): astral `elev≈30°`, полудень ≈ 36° → `sun≈0,85` → `P≈650 кВт` (макет `pv_now` — за параболою 0,83·… ≈ 468); параболa: `h=10,5` → `sun=0,826` |
| R-12 | КГУ | `load = 0,5` вдень (`sun > 0,05`), `1,0` у темну пору і коли `outdoor_c < 0`; `P_el = 800·load ± 4·r`, `heat = 497 (50 %) / 856 (100 %)`, `gas = 109 / 199`; `hours += dt/3600`; `state=2`. **Острів** (`blackout`, X-67) — за параметром S-03 `chp_island` (ПРИПУЩЕННЯ до відповіді замовника про острівний режим TEDOM, CONSISTENCY «Питання до замовника» № 3; td_genset Q-02): `false` (умовчання) — КГУ зупиняється від втрати мережі: `state` 2 → 4 (cooling down, 60 с) → 0, `P_el = 0`, `heat = 0` (тепло — котли, R-10); після повернення мережі `state` 1 (starting, 60 с) → 2; `true` — КГУ лишається в роботі паралельно з ДГУ: `P_el = min(800·load ± 4·r, max(0, P_crit − pv_now))` (в острові не віддає більше за навантаження критичної шини, R-22). `chp_kw` (u72 40001) — завжди значення моделі, яке «вимірюють» споживачі; генератор бере решту (R-22) | макет: день → 400 кВт, 497 кВт тепла; острів, `chp_island=false` → 0 кВт; `chp_island=true`, день: `min(400, 348 − 0) = 348` кВт |
| R-13 | Баланс електроенергії | кожен тік: `load = Σ p_now усіх споживачів` (макет 626); `gen = pv + chp`; `surplus = gen − load`; `bess_kw = clamp(surplus, −200, +200)`, обмежено `SOC` (заряд лише при `SOC < 100`, розряд при `SOC > 10`); `SOC ← SOC + bess_kw·dt/3600/387·100`; `export = max(0, surplus − bess_kw)`; `grid = max(0, −surplus + max(0, bess_kw))`… спрощено: `grid = max(0, load − gen − max(0, −bess_kw))`; на вводи Q1/Q2: `P_Q1 = P_секції1`, `P_Q2 = P_секції2 − gen + bess_kw` (генерація на секції 2); якщо `P_Q2 < 0` → експорт (3060 < 0, 3208 росте). **Острів** (`blackout`, X-67): `grid = 0`, `export = 0`, `P_Q1 = P_Q2 = 0`; `load = P_crit` (Σ `p_now` критичних ліній, R-22; некритичні — 0); BESS: до переключення ATyS у II — розряд `bess_kw = −min(200, P_crit)` (лише при `SOC > 10`), після — `bess_kw = 0` (заряд від генератора в острові не моделюється, CONSISTENCY «Питання до замовника» № 4); баланс шини: `P_genset + chp_kw + pv_now − bess_kw = P_crit` (td_genset R-06) | макет: `load=626`, `pv=0` (ніч у знімку), `chp=397` → `surplus=−229` → `grid=229`, `bess_kw=0`…; при `pv=468`: `surplus=239` → `bess=200`, `export=39` (макет 42 при `bess_soc` 76 %); острів до переключення: `bess_kw = −200`, після: `0` |
| R-14 | Стан верстата | джерело завдання: `follow_odoo` — `mrp.workorder` РЦ зі `state=progress` (і `working_state != blocked`); `scenario` — планувальник; **прапори**: `MachineOn = sim у зміні ∨ є завдання`; `MachineInitialized = MachineOn`; `PowerPresent = ¬blackout_без_генератора`; `Calibrated = True`; `Error = збій ∨ working_state=blocked`; `Alarm = Error ∨ активна ALARM-подія`; `Warning` = є WARNING-подія; `RecipeInRun = є завдання в роботі ∧ ¬Error`; `EnergySaving = ¬у зміні ∧ ¬завдання` (після 15:30); `CurrentState` **строго за логікою стандарту §7.7**: `¬MachineOn → OFFLINE(0)`; `MachineOn ∧ (¬MachineInitialized ∨ EnergySaving ∨ (¬Error ∧ ¬Calibrated)) → STANDBY(1)`; `MachineOn ∧ MachineInitialized ∧ ¬EnergySaving ∧ ¬Error ∧ Calibrated ∧ ¬RecipeInRun → READY(2)`; `… ∧ RecipeInRun → WORKING(3)`; `MachineOn ∧ MachineInitialized ∧ ¬EnergySaving ∧ Error → ERROR(4)`; P-02: `DI(run) = (CurrentState == WORKING)`, `DI(fault) = Error`; `workcenters/<C>/state` — лише стан, заявки ТО споживачі створюють тільки з `…/alarm` (R-15; machine_connect R-08; X-38) | демо 10:30: 29 РЦ WORKING, SAW-3/VSAW-1/EDGE-3/UV-1/ASM-5 READY (простій), CNC-2 ERROR |
| R-15 | Збій пристрою | `fault(reason)`: верстат — `Error=True` + подія (§8.3.3), `p_now → 0` (R-02 blocked), `DI(fault)=1`; `reason=comm` — протокольний об'єкт недоступний (OPC UA Bad, Modbus виняток 0x0B на unit, BACnet `reliability=communication-failure`, MQTT `online=false`); `power` — `PowerPresent=False`; `clear()` — усе назад, `RecipeInRun` відновлюється, якщо завдання ще є | CNC-2 у демо = `fault(spindle)` при старті (з `working_state=blocked`); `clear` → READY/WORKING |
| R-16 | Лічильник деталей | під час WORKING: `pieces_acc += dt/(60·per_unit)`, `per_unit` хв/шт з маршрутів макета: Розкрій 2,2; Пакетний розкрій 0,9; Крайкооблицювання 1,6; Присадка 2,0; Прохідна присадка 0,8; Шкантування 1,0; Сортування 0,5; Збирання 6,0; Пакування 3,0; інше 1,5; `RelativePiecesOut = floor(pieces_acc)`; `RelativePiecesIn = RelativePiecesOut + (1 якщо WorkpiecePresent)`; `RunsGood = RunsTotal = завершені завдання`; обнулення `Relative*` о початку зміни; `Absolute*` — ніколи; `follow_odoo`: якщо `qty_produced` з Odoo > лічильника → лічильник = `qty_produced` | SAW-1 за 15 хв WORKING → `pieces_out += 6` |
| R-17 | Завдання (JobOrderList) | `follow_odoo`: елемент на кожен `mrp.workorder` РЦ у станах `ready/progress` (+ `done` за поточну зміну) з мапінгом станів §8.3.2; `scenario`: планувальник створює для кожного РЦ чергу з маршрутів макета (`routes` A–D, F1–F3) із `duration_expected = 15 + per_unit·qty` хв; завдання стартує, коли попередня операція МО завершена і РЦ READY; `StoreAndStart`/`Start` через OPC UA (API §8.3.2) або `POST /jobs/{id}/release` — ставлять завдання в чергу/запускають; `JobOrderID = "WO%05d" % mrp.workorder.id` (follow_odoo і завдання з Odoo в `scenario`), синтетичні — `SIM-%05d`, випуск `/jobs` — `cj-…` (X-38, machine_connect Q-17); завершене завдання лишається в `JobOrderList` зі станом `Ended/Completed` до початку наступної зміни в обох режимах (machine_connect R-12) | демо: WO00013 на SAW-1 `progress` → `Running`; WO00094 на SAW-3 `ready` (чекає бетон) → `AllowedToStart`; WO00013 `done` → лишається `Ended/Completed` до 07:00 наступного дня |
| R-18 | Портал | черга `feed`-завдань (P-03): цикл = 1 лист за `per_unit` хв цільового РЦ (SAW 2,2; NEST 1,5 → 20 с руху + решта очікування): `state` idle→moving (10 с)→picking (4 с)→moving (10 с)→placing (3 с)→idle; стос `qty −= 1`; `qty=0` → подія `stack_empty`, завдання шукає інший стос того ж `product` (інакше `error`); `cycles_today += 1`; `vacuum` R-01 (−72, `alarm > −60`); прохід `aisle.gate_open=True` (сценарій/API) → `blocked` для завдань з цього проходу; `follow_odoo` — `feed` для РЦ із завданням у роботі | демо: 3 РЦ розкрою в роботі → ≈ 1,3 цикл/хв (макет `rate=3` — верхня межа при повному завантаженні) |
| R-19 | Рух техніки | маршрут між центроїдами зон (API-01 `zones[].polygon`): навантажувач `busy` курсує між зоною свого завдання (FL-1: Z-POST↔Z-FG; FL-2: Z-RCV-1↔Z-SHEETS; FL-3: Z-FG↔Z-OUT-2; FL-4: Z-FG↔Z-OUT-5; FL-5: Z-PACK↔Z-POST; TUGGER-1: Z-HW→Z-PRE→Z-ASM; FL-C1/C2: Z-CHG), швидкість 6 км/год (1,67 м/с), стоянка 90 с на кінцях; `to_charge` → до Z-CHG; `charging` — нерухомо; поза зміною — `idle` у Z-CHG; `x,y` — лінійна інтерполяція, `heading` — напрям, `zone` — зона, у полігоні якої точка | FL-1: від (112,38) до (130,57) ≈ 26 м → 16 с |
| R-20 | Масштаб ADAM | §8.9.6: `raw = round(65535·(mA − 4)/16)`, `mA = 4 + 16·(eng − lo)/(hi − lo)`; RTD `raw = round(65535·(t + 50)/200)`; float-регістри — мА / °C | DUST airflow 29 768 → `mA = 18,88` → `raw = 60 950`; T1 59 °C → `raw = 35 716` |
| R-21 | Вода | витрата `q = 2,1 м³/год` у зміні, `0,3` поза зміною, `+1,5` під час роботи фарбування (SPRAY-1/AUTOSPRAY-1 WORKING); імпульси `n = floor(q·dt/3600·100)` (10 л/імп) на DI8 u84; `m3_total = 18 642 + Σ/100`; `flow_m3h` = ковзне середнє 5 хв | 1 год зміни → 210 імп → +2,1 м³ |
| R-22 | Blackout / АВР (ATyS p за Annexe III — §8.9.4, X-41; генератор — CI-01 / API-F, X-59) | `blackout(on)` (t0): мережа зникає — ATyS `20486 = 0` (Source 1 under threshold), `20490…=0`, PV → `0x0303` (`pv_now = 0`), PM5560 вводів `P = 0`, споживачі некритичних ліній → `PowerPresent=False` (ERROR); критичні лінії (BW-1, LP-1..3, DUST-1, COMPRESSOR, BOILER, OFFICE, EF-ELEC, EF-CHG — `CRITICAL` макета) вважаються живленими (критична шина за АВР; на інтервалі пуску — від BESS, R-13; недостачу емулятор не моделює — ПРИПУЩЕННЯ, td_genset Q-08); освітлення до переключення — аварійне (EMERGENCY 100 %, C:110 `0x400`, решта 0), після переключення в II LP-1..3 — за розкладом R-24; КГУ — R-12 (`chp_island`). **Варіант A** (`amf_master=hgm`, D-23; `20482 = 0x0020` Remote): API-F-02 `mains {"available": false}`; щосекунди API-F-01: двигун запущений → `20487 = 1`, `gen_ok` → `20487 = 2`; `breaker == "gen"` → `20483` 2 → 1 (ODT 3 с) → 3, `transfer_counter += 1`. **Варіант B** (`ats`; `20482 = 0x0010` Auto): через 1FT 3 с `20484 = 1` + API-F-03 `remote_start {"on": true}`; `gen_ok` → `20487 = 2`, через 2AT 5 с `20483` 2 → 1 (ODT 3 с) → 3; `gen_ok` немає за 2ST 30 с від наказу пуску → подія `alarm` «АВР: генератор не запустився (FAIL START)», `20483` лишається 2 (сигнал `fail_start` рахує energy, X-35). **Навантаження генератора в острові** (X-67; як energy R-14 п. 9 і td_genset R-06): з моменту переключення в II і далі щотіку `P_genset = min(SIM_GENSET_KW_MAX, max(0, P_crit − chp_kw − pv_now + bess_kw))`, де `P_crit` = Σ `p_now` споживачів критичних ліній, `chp_kw`, `pv_now`, `bess_kw` (+ заряд / − розряд) — значення моделей емулятора в тому самому тіку (те, що «вимірюють» energy і міст); результат → API-F-04 `load {"kw": P_genset}` при зміні ≥ 1 кВт; явний параметр `genset_load_kw` S-03 замінює формулу. `blackout(off)`: `20486` 1 (2 с) → 2; варіант A — API-F-02 `mains {"available": true}`, коли `breaker == "mains"` (таймери HGM) — `20483` 3 → 1 → 2, API-F-04 `{"kw": 0}`; варіант B — через 1RT 180 с `20483` 3 → 1 → 2, API-F-04 `{"kw": 0}`, через 2CT 180 с `20484 = 0` + API-F-03 `{"on": false}`; `20487 = 0` після `state == "standby"` (API-F-01); запасний режим без `fake_relay` (§8.14) — `20487 = 2` і переключення через 15 с після t0, повернення через 60 с після `blackout(off)`; КГУ перезапускається (R-12), PV — `0x0001` → `0x0200`; протокольно: RV/AHU — `BV:1=0` під час відсутності живлення на C2 → `ST` | `blackout`, варіант A, `chp_island=false`, макет 12.10 10:30: t0 `20486=0`, `bess_kw=−200`; ≈ t0 + 30 с (умовчання HGM, td_genset §8.4) `breaker=gen` → `20483=3`, `bess_kw=0`, `P_genset = 348 − 0 − 0 + 0 = 348` кВт (= td_genset R-06 / AC-56, energy R-14: `load_kw 348`, `shed 278`); `chp_island=true` (день): `chp_kw = min(400, 348) = 348` → `P_genset = 348 − 348 − 0 + 0 = 0` (ДГУ без навантаження, API-F-04 `{"kw": 0}`); тест із `P_crit = 600`, `chp_island=false` → `min(558, 600) = 558` |
| R-23 | Вентустановка | `k` (частка витрати) за режимом: `VE`/`AQ_VE` 0,85; `AQ_ECO` 0,55…0,85 (`k = 0,55 + det(code) mod 30/100` — як макет); `REC` 0,45; `VEL` 0,35; `ST/Off` 0; `airflow = 8000·k` (AHU-1: `20000·0,85`); `supply_c = 19,5 + det/10` ± 0,2 (R-01), поза зміною 16; `indoor_c` R-01 навколо `17,5 + det/10`; `heat = heat_nom·k·(18 − outdoor)/(18 + 15)·f`, `heat_nom = 116,8 кВт` (паспорт `roofvent`, bms R-10), `f = 0,3` для `AQ`, `0,8` для `VE`, `VEL`, `REC`, `EA`, `SA`, `heat = 0` для `ST`/`Off` (формула bms R-13; X-40); AHU-1: `heat = airflow·1,2/3600·(21 − outdoor)`; `heating_valve` — у **%**: `100·clamp(heat/heat_nom, 0, 1)` (сигнал і AO:1 — %, `scale=1`, частка — лише в payload переглядача; X-39); `p_now = 8,6·k³ + 0,1`; режим за календарем: зміна → макетний режим зони (`VE` для RCV/OUT, `AQ` решта, `REC` для RV-21/22), обід (11:30–12:00) → без змін, поза зміною → `VEL`, ніч 22:00–06:00 → `ST`; `filter_dp` R-09; `BI:3 = dp > 250` | RV-05: `k=0,74` → 5 913 м³/год (макет 5 912,6); тепло за bms R-13 з `k=0,72` (AQ, `outdoor=9`): `116,8·0,72·9/33·0,3 = 6,88` → **6,9 кВт** (= макет), клапан `6,9/116,8 = 0,06` → `heating_valve = 6 %`; RV-01 (VE, `k=0,68`): `116,8·0,68·9/33·0,8 = 17,3` кВт, клапан 15 %; AHU-1 17 000 м³/год, `outdoor=9`: `68,0` кВт |
| R-24 | Освітлення | рівень групи за розкладом: зміна → рівень макета (`level` 0,5…1,0: склади 0,6–0,8, цех 1,0, компресорна/зарядна/електрощитова 0,5); 06:00–07:00 і 15:30–17:00 → 0,5; ніч → 0,1 (склади з датчиками присутності — 0 без присутності, 1 при проході техніки R-19 у зоні); денне світло (`sun > 0,5`) знижує приймання/відвантаження на 20 %; сигнал `lighting/groups/<G>/level` і C:152 — у **%** (`100·level`, 0…100, `scale=1`; X-39); `p_now_W = n·126·level` (`level` — частка = % / 100); HelvarNet-команди (13/11/14) перекривають розклад до наступної зміни розкладу; `lighting_scene` сценарій — явна сцена | LT-CUT: 27 світильників, `level=1,0` → сигнал `100` %, 3,4 кВт; LT-FG: 12·126·0,6 = 0,9 кВт, сигнал `60` % |
| R-25 | Пожежна панель | стани зон `quiet`; `fire_drill(zone, detector)`: t=0 `LSP(det)=test-alarm(9)`, `LSZ(zone)=test-alarm`, `LSZ:0=test-alarm`, `MSV:1=4 Test`, `PIV:1 += 1`; +3 с `BV:10=1` (сирени), `BV:11=0` (навчання не передається на пульт; реальна тривога `real=true` — `BV:11=1`) (BV/PIV — X-37); +6 с всі RV/AHU `BV:1=0`; +9 с `u85 DI4=1` (клапани), `DI5=0`; +12 с BioStar `20480` на всіх дверях, `u86` DO4 = 1 і DO5 = 1 (`fc1 pdu20`, `pdu21` — «тримати відкритим» обидва шлагбауми, окремі канали, X-47); +20 с РЦ зони → `ExternalEmergency=True` → ERROR; закінчення (`duration_s` або `stop`) → усе назад у зворотному порядку за 30 с; несправність (`fault(reason=sensor\|generic)` на зоні `FA-*` через API-12 — X-60, або сценарій) → `LSP` першого сповіщувача зони `reliability=unreliable-other`, `LSZ(zone)=fault(3)`, `LSZ:0=fault` (якщо немає тривоги), `MSV:1=3 Fault`, `PIV:2 += 1`, подія `fault` «Несправність сповіщувача 2.FAC.07 (зона FA-FAC, шлейф 2)»; **BV шлейфу не змінюється** — несправність лінії лише для `fault(reason=loop)`: тоді ще `BV:<loop>=1` і подія `fault` «Несправність шлейфу 2» (X-36); `clear` — усе назад, `PIV:2 −= 1`. Емулятор заявок не створює: споживач (fire) створює одну заявку на пристрій, несправність шлейфу, спричинена пристроєм, — подія без заявки (X-36); запиленість R-09 → `PIV:<id LSP>` (ціле %) і при `> 90` `reliability=unreliable-other`, подія `alarm` «Очистити сповіщувач 2.FAC.07 (запиленість 91 %)» | макет: подія 09:58 попередження 82 % |
| R-26 | Іскрогасіння | фонові події: Пуассон із середнім 1 іскра/8 год у зміні, поки працюють SAW-*/NEST-1 (`det`-керований генератор, не випадковий); `spark` сценарій — негайно; DI0 імпульс 0,6 с, DI1 2 с, `count_today += 1`, подія WARNING «Іскрогасіння: іскру виявлено на магістралі аспірації над лінією A, гасіння 0,6 с»; `fault=true` → DI2=1, заявка | макет: 08:47 іскра |
| R-27 | Димовидалення | `u85 DI4` = 1, якщо тривога/навчання (R-25) або `DO0` отримав імпульс (`SIM_WRITE_ACCEPT`); відкриття 60 с; закриття після скидання за 90 с; `blackout` → DI6=1 (АКБ), через 72 год DI5=1 | |
| R-28 | СКУД | працівники з API-01 (`employees`, 35 з бейджами); вхід `06:40 + (det(code) mod 20) хв` (як `step_attendance` макета), подія 4102 (Verify success — card), якщо `det(code) % 2 == 0`, інакше 4867 (Identify success — face) (`det` — FNV-1a 32, як `plant/odoo_demo.py:det`; X-50, access §13.1); `tna_key=1`; вихід `15:30 + (det(code) mod 20)`, `tna_key=2`; під час зміни: електрик (`OP-W1` як черговий) → ACR-ELEC 09:51, комірники → ACR-PAINT (OP-W2 10:20), ACR-CHG (FL-C* повернення), ACR-SRV (адміністратор 1 раз/день); `access_event` сценарій — довільна подія (параметри `device`, `user`, `code`); `on_site = входи − виходи` за добу; `fire_drill` — R-25 | демо: 35 відміток входу 06:40–07:00 → `hr.attendance` у фазі 4; OP-SAW-1 → 06:52, код за `det % 2` |
| R-29 | Двір | фура з `bookings` (API-01) або розкладу макета: прибуття на GATE-W за `scheduled − 20 хв` (incoming) / на GATE-E `scheduled − 10 хв` (outgoing порожня → заїжджає через GATE-W; ПРИПУЩЕННЯ: в'їзд завжди через GATE-W, виїзд через GATE-E); послідовність incoming: `expected → at_gate` (LPR `new`, DI1=1 петля) → якщо бронювання є і (`SIM_YARD_AUTOGATE` або DO0 отримано) → `DI0=1` через 5 с → `weigh_in` (на вагах 60 с, брутто) → `to_dock` (3 хв) → `at_dock` (розвантаження за прогресом `stock.picking` у follow_odoo або 40 хв у scenario) → `to_exit` (2 хв) → `weigh_out` (тара) → GATE-E `at_gate → left` (LPR `CAM-06`); номер фури — `bookings[].plate` (API-01, `f3d_plate`), інакше генерується (§8.13.2, X-49); LPR з бронюванням — `plateList="f3d_bookings"`, `plateListMode="allow"` (X-48); без бронювання → `rejected`: стоїть на петлі, LPR `plateList=""`, `plateListMode="none"`, подія WARNING «Фура АА1234КТ без бронювання біля воріт в'їзду», через 10 хв їде (або `truck_arrival` з `booking=true` її впускає); `passes_today` — лічильник петлі | демо: TRUCK-IN-1 (`BATCH/IN/00001`, DOCK-W1, 06:30) → у знімку 10:30 стоїть `at_dock`, розвантажено 60 % |
| R-30 | Ваги | `weight = 0 ± 20`; при `weigh_in/out`: протягом 3 с `D` (динамічно) лінійно до цільової, далі `S` ± 20 кг; брутто = `14 000 + Σ(qty·маса_од)`: аркуш ДСП 16 мм 2800×2070 — 56 кг, МДФ 18 — 70, ХДФ 3 — 12, палета ГП — 420, фурнітура/крайка/ЛФМ — за документом 0,02–1,2 кг/од; `> 60 000` → `S +` | WH/IN/00128: 120 ДСП16 + 80 ДСП16 → 200·56 = 11 200 → брутто 25 200 кг |

### 9.2 Пороги й статуси

`status`: `alarm`, якщо `alarm=above ∧ v > threshold` або `alarm=below ∧ v < threshold` (макет) або для нових сигналів — правило з колонки «Пороги» Додатка A; `warn` — у межах 10 % до порога (`above`: `v > 0,9·threshold`); `stale` — модель не оновлювала значення > 3·період (лише при `fault reason=comm`); інакше `ok`. Перехід `ok/warn → alarm` — подія `alarm` з повідомленням `«<Назва>: <значення> <од> при нормі <до|від> <поріг>»`; `alarm → ok` — подія `info` «повернувся в норму». У фазі 1 заявки ТО створює лише рівень 0 (Odoo) — емулятор лише сигналізує; у фазі 2 — `factory3d_telemetry` за §6.8 каркаса.

### 9.3 Сценарії (S-01…S-15)

Загальні параметри всіх: `duration_s` (int, ≥ 0; 0 — до зупинки; default — у таблиці), `note` (string). Схеми — JSON Schema draft 2020-12 (у `f3d.sim.scenario.params_schema` і `GET /sim/v1/scenarios`).

| ID | `name` | Група | Параметри (`params_schema`) | Що робить | Що видно (3D/Odoo/протоколи) | Конфлікти |
|---|---|---|---|---|---|---|
| S-01 | `shift` | production | `date` (date, default сьогодні), `lines` (array of enum `A,B,C,D,F`, default усі), `speed` (number 0,5…3, default 1 — множник темпу завдань), `trucks` (bool, default true), `people` (bool, default true) | у режимі `scenario`: запускає планувальник на день — завдання за маршрутами макета на всіх РЦ обраних ліній, фури за розкладом, відмітки людей; `duration_s` default 0 | верстати WORKING/READY, OEE, потужність, фури біля воріт, заряд АКБ | `follow_odoo` → 409 |
| S-02 | `machine_fault` | production | `device` (enum: 35 РЦ + GANTRY-1, required), `reason` (enum §2.11, default `generic`), `auto_clear_s` (int, default 0) | `fault(reason)` на пристрій; після `auto_clear_s` або `stop` — `clear()`; `duration_s` default 0 | OPC UA ERROR + подія E04xx, DI fault, `p_now=0`, червоне кільце в 3D, заявка ТО (фаза 2 / рівень 0 — ні, бо стан не сигнал) | той самий пристрій |
| S-03 | `blackout` | energy | `duration_s` default 600, `genset` (bool, default true — чи стартує генератор), `restore_delay_s` (int, default 60 — повернення в запасному режимі §8.14), `amf_master` (enum `hgm`, `ats`; default `SIM_GENSET_AMF_MASTER` = `hgm`; CI-01, X-59), `genset_load_kw` (number 0…558, optional — явне навантаження генератора замість формули R-22; CI-01), `chp_island` (bool, default false — чи працює КГУ в острові; X-67) | R-22 (+ R-12, R-13 острів): API-F-01…F-04 `fake_relay` (td_genset §8.4/§8.6), `P_genset = min(558, max(0, P_crit − chp_kw − pv_now + bess_kw))` | ATyS u71 `20483 = 3` (II), `20486 = 0`, `20487 = 2`; варіант `ats` — `20484 = 1`; PM5560 вводи 0, PV 0x0303, освітлення аварійне до переключення, некритичні верстати ERROR; генератор у `td_genset` під навантаженням 348 кВт (`chp_island=false`) або 0 (`true`, день) | усе енергетичне (`pv_cloudy`, `genset_test`) |
| S-04 | `filter_clogged` | bms | `device` (enum RV-01…RV-25, AHU-1, DUST-1, FA-FAC, required), `value` (number — цільове значення в одиницях сигналу; default: RV 285 Па, DUST-1 1,9 кПа, FA-FAC 92 %), `ramp_min` (int, default 2) | лінійно підводить сигнал фільтра/запиленості до `value` за `ramp_min` хв і тримає (R-09 продовжує), доки не закриють заявку або `stop` (→ `nominal`) | BACnet AI:4/BI:3, заявка «Заміна фільтрів: перепад тиску 285 Па при нормі до 250» (рівень 0 / фаза 2) | той самий пристрій |
| S-05 | `truck_no_booking` | logistics | `plate` (string, default генерований), `gate` (enum GATE-W/GATE-E, default GATE-W), `wait_min` (int, default 10) | фура без бронювання за R-29 (`rejected`) | LPR `plateList=""`, `plateListMode="none"` (X-48), петля DI1=1, шлагбаум закритий, подія WARNING | петля тих самих воріт |
| S-06 | `truck_arrival` | logistics | `booking` (string — `batch` з API-01 або `picking`, required), `plate` (string, optional), `at` (datetime, default зараз), `unload_min` (int, default 40) | фура з бронюванням проходить повний цикл R-29 негайно | LPR `plateList="f3d_bookings"`, `plateListMode="allow"`, номер з `bookings[].plate` (X-49), шлагбаум, ваги SICS, фура біля воріт у 3D, прогрес документа (лише scenario) | петля воріт |
| S-07 | `fire_drill` | safety | `zone` (enum 35 зон FA-*, default FA-CNC), `detector` (string, default перший у зоні; демо `2.CNC.05`), `real` (bool, default false — справжня тривога замість навчальної), `duration_s` default 300 | R-25 | BACnet LSZ/LSP test-alarm/alarm, сирени, стоп вентиляції, димовидалення, двері, верстати ERROR, 3D: маршрути евакуації | усі safety/bms |
| S-08 | `spark` | safety | `fault` (bool, default false), `count` (int 1…5, default 1), `interval_s` (int, default 30) | R-26 | u85 DI0/DI1, подія WARNING | — |
| S-09 | `access_event` | access | `device` (enum ACR-*, default ACR-IN), `user` (string — `barcode`; default випадковий працівник), `code` (int, enum кодів §8.12, default 4102), `tna_key` (enum `1,2,""`, default `1`), `door_open` (bool, default true) | додає подію BioStar (+ `20480/20992/21248` дверей, якщо `door_open`) | `/api/events/search`, у фазі 4 — `hr.attendance` | — |
| S-10 | `battery_low` | logistics | `device` (enum FL-*, TUGGER-1, required), `level_pct` (number, default 18) | ставить заряд `level_pct` → R-05 веде на зарядку | MQTT `to_charge/charging`, 3D рух у зарядну | пристрій |
| S-11 | `compressor_fault` | energy | `kind` (enum `pressure_drop`, `overtemp`, `comm`, default `pressure_drop`), `duration_s` default 900 | R-08: `nominal=5,5` / `temp=115` / unit 70 недоступний | Modbus u70, тиск < 6,0 → alarm і заявка; `AIR-RING` тиск теж падає до 5,6 | COMPRESSOR, AIR-RING |
| S-12 | `pv_cloudy` | energy | `cf` (number 0,05…1, default 0,3), `duration_s` default 1800 | R-11 `cf` | PV 32080 падає, баланс R-13: BESS розряд, `grid` росте | енергетичне |
| S-13 | `boiler_refill` | bms | `level_pct` (number, default 95), `force_on` (int 0…2, default −1 = авто) | бункер → `level_pct`; `force_on ≥ 0` → примусово `boilers_on` | BACnet dev 140 AI:3, BI:1/2 | BOILER |
| S-14 | `genset_test` | energy | `duration_s` default 900, `test_on_load` (bool, default false; CI-01, X-59) | щотижневий тестовий пуск (07:30 у макеті): API-F-03 `remote_start {"on": true}` на `duration_s`, далі `{"on": false}` (`fake_relay` фіксує `last_test`); `test_on_load=false` — генератор без навантаження, ATyS лишається в I (`20483 = 2`); `true` — ATyS переключає критичну шину на генератор (`20483` 2 → 1 → 3, назад після `duration_s`), навантаження за R-22 (API-F-04) | P-12, подія INFO | blackout |
| S-15 | `lighting_scene` | bms | `group` (enum LT-* або `all`, default `all`), `scene` (int 1…16) або `level` (int 0…100), `fault_device` (string адреса `@c.r.s.d`, optional), `duration_s` default 600 | R-24: явна сцена/рівень; `fault_device` → C:110 біт1 | HelvarNet push, `lighting/groups/*/level`, 3D освітленість | група |

Усі сценарії пишуть події `scenario` (`started`, `progress` з `payload.step`, `done|stopped|failed`); `result` для S-06: `{"gross_kg": 25200, "tare_kg": 14000, "dock": "DOCK-W1", "unloaded_pct": 100}`; для S-07: `{"alarm_latency_s": 0, "sounders_s": 3, "vent_stop_s": 6, "doors_s": 12}`.

### 9.4 Прискорення часу

`factor` ∈ [0,1; 60]. Усі інтеграли (R-03, R-06, R-07, R-16, R-21) рахуються по `dt_sim`, тому значення за sim-добу не залежать від `factor`. Хвилинний шум R-00 прив'язаний до sim-хвилин (при `factor=60` — 60 нових `r` на реальну секунду). Протокольні позначки часу (`SourceTimestamp`, BACnet `time-stamp`, BioStar `datetime`, MQTT `ts`, LPR `datetime`) — `sim_now`. Push-частоти протоколів — у реальному часі (не частіше 1 с), тож при `factor=60` споживач бачить «стрибки» на 60 с — це очікувано і задокументовано для споживачів (ТК-14). `follow_odoo` → `factor=1` (A-12).

---

## 10. Стани й переходи

| Об'єкт | Стани | Переходи (хто/що) | Побічні ефекти |
|---|---|---|---|
| Верстат (OPC UA `CurrentState`) | OFFLINE(0), STANDBY(1), READY(2), WORKING(3), ERROR(4) | обчислюється з прапорів щотіку (R-14); джерела прапорів: календар (`MachineOn`, `EnergySaving`), завдання (`RecipeInRun`), збій/Odoo blocked (`Error`), blackout (`PowerPresent`) | WORKING → `p_now=nominal`, лічильники; ERROR → `p_now=0`, подія ALARM; READY → `p_now=rate`; OFFLINE/STANDBY → `p_now=0` |
| Завдання ISA-95 | NotAllowedToStart → AllowedToStart → Running → (Interrupted/Held ⇄ Running) → Ended/Completed; будь-який → Ended/Cancelled (Cancel), Running → Aborted (Abort) | Odoo (`follow_odoo`) або планувальник/методи OPC UA/`/jobs release` | Running ⇒ `RecipeInRun`; Completed ⇒ `RunsGood += 1`, JobResponse |
| Техніка (`state`) | idle → busy (завдання/зміна) → to_charge (`battery ≤ 20`) → charging (у Z-CHG) → idle (`battery ≥ 95`); будь-який → offline (`fault comm`) → попередній (`clear`); busy → fault (`fault`) | R-05, R-19, сценарії S-10, S-02 | MQTT `event` на кожен перехід; `hours` рахуються в busy/to_charge |
| Фура | expected → at_gate → (weigh_in → to_dock → at_dock → to_exit → weigh_out → at_gate_out → left) \| rejected → left | R-29; S-05, S-06; DO шлагбаума | LPR події, DI/DO, SICS, події `yard` |
| Запуск сценарію | queued → running → (stopping →) stopped \| done \| failed | API-13 start/stop, завершення `duration_s`, виняток | події `scenario`, API-03 → `f3d.sim.run` |
| Сервіс | starting → running ⇄ degraded; running → locked (`stop-all`/`SIM_ENABLED=0`) → running (`resume`); → stopped | health §8.16 | `/health`, Docker HEALTHCHECK |
| Зона пожежної (LSZ) | quiet → pre-alarm → alarm → quiet (reset); quiet → test-alarm → quiet; quiet ⇄ fault (API-12 `fault`/`clear` на `FA-*`, X-60); quiet → not-ready (вимкнена) | R-25; S-07; API-12 | COV, EventNotification, каскад R-25; `fault(reason=loop)` — ще й BV шлейфу (X-36) |
| АВР (ATyS) | `20483`: 2 (I, мережа) → 1 (Position 0, ODT 3 с) → 3 (II, генератор) → 1 → 2 (Annexe III, X-41) | R-22 (варіант A — за `breaker` HGM з API-F-01; B — таймери ATyS) | `20482` режим, `20484` реле пуску (варіант B), `20486`/`20487` стани джерел, лічильник 20510 |
| Котельня (MSV:1) | standby(1) ⇄ K1(2) ⇄ K1+K2(3); будь-який → fault(4) → standby (clear) | R-10, S-13 | BI:1/2, бункер |
| Шлагбаум | closed → opening (5 с) → open → closing (після петлі + 15 с) → closed; open (held), поки свій канал «тримати» = 1: GATE-W — DO4 (`u86 fc1 pdu20`), GATE-E — DO5 (`pdu21`) (X-47) | DO0/DO1, R-29, R-25 | DI0/DI2, лічильник проїздів |
| Пульт Odoo `f3d.sim.panel.state` | unconfigured → offline ⇄ online ⇄ degraded; online → locked (стоп-кран сервісу) | C-01, кнопки | `_sync_level0` |
| Рівень 0 (`level0_state`) | auto_off ⇄ auto_on (за офлайном > N хв); → forced_on / forced_off (кнопки) → auto_* («авто») | C-01, кнопки | `cron_iot_sim.active` |

---

## 11. Обробка помилок

| Ситуація | Поведінка сервісу | Поведінка Odoo-модуля |
|---|---|---|
| Odoo недоступний при старті (API-01) | `SIM_CATALOG_SOURCE=odoo` → fallback `catalog/devices.yaml` + `signals.csv`, лог WARNING, `/status.odoo.catalog_source="local"`; повтор щогодини | — |
| Odoo недоступний у `follow_odoo` | після `SIM_ODOO_STALE_S` → `odoo_stale=true`, стан завдань заморожено, фізика триває; відновлення — повна синхронізація, подія `info` | C-01 показує `odoo_stale` у пульті |
| Сервіс недоступний для Odoo | — | `state=offline`, `last_error`, без винятків у кроні; кнопки → `UserError` з текстом; рівень 0 вмикається через `level0_after_min` |
| Невірний токен | 401 `{"detail":"invalid token"}`; 5 помилок з однієї IP за хвилину → 429 на 60 с | `UserError("Емулятор відхилив токен")` |
| Стоп-кран | 423 на команди, значення заморожені; протоколи віддають останні значення з `StatusCode=UncertainLastUsableValue` (OPC UA) / `status-flags overridden` (BACnet) | `state=locked`; кнопки неактивні, якщо `write_enabled=False` |
| Запис у RO-об'єкт/регістр | OPC UA `BadNotWritable`; Modbus виняток 0x02 (RO-регістри) / 0x04 (DO без `SIM_WRITE_ACCEPT`); BACnet `write-access-denied`; BioStar POST на незмінні ресурси → 405; лог WARNING з адресою | — |
| Невідомий код у REST | 404 | `UserError` |
| Конфлікт сценаріїв | 409 `{"detail":"device CNC-2 busy by run r-…"}` | `state=failed`, `message` |
| Невалідні параметри | 422 (pydantic) з полем і причиною | валідація у `_validate_params` до виклику; `UserError` |
| Каталог Odoo ≠ локальний | `catalog_hash` різні → WARNING «catalog mismatch: odoo=…, local=…»; беруться Odoo-адреси, невідомі коди з локального ігноруються | тест ТБ-05 |
| Знімок пошкоджений/старий | ігнорується, старт від каталогу, WARNING | — |
| Повтор API-03 | дедуплікація за `payload.event_id` | `rejected: duplicate` |
| Часові пояси | усе внутрішнє — tz-aware `Europe/Kyiv`; на дріт: OPC UA/BACnet — UTC; BioStar — UTC `Z` + `timezone.hour`; MQTT/LPR/REST — ISO з офсетом; Modbus epoch — UTC секунди (Huawei 40000 — «local time» за документом: емулятор віддає локальні секунди, як Huawei) | Odoo зберігає UTC; показ у tz користувача |
| Перехід DST (26.10.2026 04:00 → 03:00) | sim-годинник монотонний у UTC; локальні розклади (зміна 07:00) рахуються в локальному часі; година повторення — без подвійних відміток | — |
| Прискорення й Odoo | `follow_odoo` + `factor≠1` → 409 | `UserError` (A-12) |
| MQTT брокер недоступний | буфер 10 хв, потім втрата з лічильником `iot_sim_mqtt_dropped_total`; `status` retain відновлюється при reconnect | — |
| LPR POST не доставлено | 3 повтори (2/5/10 с), далі подія `error`, подія фури продовжується | — |
| Вихідне з'єднання поза allow-list | `OutboundDenied`, лічильник метрики, WARNING; сценарій, що потребував його, → `failed` | — |
| Переповнення буферів подій | кільце 10 000: старі витісняються; API-19 `next` стає невалідним → 410 Gone з підказкою перечитати з початку | — |

---

## 12. Acceptance Criteria

Тип перевірки: **UT** — юніт-тест (сервіс `pytest`, Odoo `TransactionCase`/`HttpCase`), **TC** — стенд на емуляторі (compose, клієнти протоколів), **MAN** — ручна.

| ID | Given / When / Then | Тип | FR |
|---|---|---|---|
| AC-01 | Given `SIM_API_TOKEN` задано і compose запущено; When `GET /sim/v1/health`; Then 200, `status=ok`, усі 11 ключів `protocols` = `ok` протягом 60 с після старту | TC | FR-01, FR-22 |
| AC-02 | Given каталог `signals.csv`; When `GET /sim/v1/signals?limit=1000` з токеном; Then `count=1017` (усі коди Додатка A з протоколом; 151 рядок `protocol=none` відсутній — X-35, X-76), у кожного `value` не `null`, `ts` ≤ 5 с тому | TC | FR-02 |
| AC-03 | Given сигнал `energy/consumers/SAW-1/p_now`; When SAW-1 у WORKING; Then PM5560 `u11 fc3 pdu3059+2` (документ 3060–3061, F32; X-42) = значенню з `/signals` ± 0,01 і ∈ [10,9; 13,5] | TC | FR-02, FR-04 |
| AC-04 | Given `World(seed=20261012)` без Odoo, `SIM_SUN_MODEL=parabola`; When прокрутити 10 хвилинних кроків для `equipment/COMPRESSOR/pressure_bar`; Then ряд збігається з еталоном `golden_rng.json` (отриманим з формули `action_iot_tick`) з точністю 1e-6 | UT | FR-03, FR-21 |
| AC-05 | Given два `World` з однаковим `seed` і однаковою послідовністю команд; When прокрутити 1 sim-годину; Then усі 1017 значень рівні | UT | FR-21 |
| AC-06 | Given `factor=1` і `factor=10`; When прокрутити 1 sim-годину обома; Then `kwh_shift` SAW-1, `hours` FL-1, `pieces_out` SAW-1 рівні з точністю 0,1 % | UT | FR-17 |
| AC-07 | Given режим `follow_odoo`, у Odoo `mrp.workorder` SAW-1 у `progress`, CNC-2 `working_state=blocked`; When пройшло 15 с; Then OPC UA `SAW-1.State.Machine.Overview.CurrentState=3`, `CNC-2…CurrentState=4`, `CNC-2.State.Machine.Flags.Error=True`, PM5560 `u22 fc3 pdu3059+2` = 0 | TC | FR-04, FR-18 |
| AC-08 | Given FL-2 `battery=21 %` у `busy`; When прокрутити sim-час до `≤ 20 %`; Then MQTT `telemetry.state` стає `to_charge`, потім `charging` у зоні `Z-CHG` (x,y у полігоні), заряд росте 0,6 %/хв до 95 → `idle` | UT+TC | FR-05 |
| AC-09 | Given RV-05 `filter_dp_pa=285`; When `World.maintenance_closed.add("RV-05")` (або закрити MR/00035 в Odoo у follow_odoo); Then за ≤ 2 тіки BACnet dev 105 AI:4 = 120 ± 1, BI:3 = 0 | UT+TC | FR-06 |
| AC-10 | Given бункер 16 %; When крок зі витратою; Then `silo_fill` → 95, подія `info` «Бункер поповнено» | UT | FR-07 |
| AC-11 | Given `sim_now` = 12.10.2026 10:30 Київ, `cf=1`; When `SIM_SUN_MODEL=parabola`; Then `Σ u61…u68 fc3 pdu32080+2` = `765·0,826·(0,92…1,0)` ± 1 %; при 23:00 — 0 і 32089 = `0xA000` | UT | FR-08 |
| AC-12 | Given усі 35 РЦ WORKING; When тік; Then `u70 fc3 pdu3009` (load, документ 3010) ≥ 80; поріг `pressure < 6,0` не спрацьовує без сценарію | UT | FR-09 |
| AC-13 | Given стос `PLT-04C qty=38`; When `POST /api/v1/jobs {type: feed, source: PLT-04C, target: SAW-1, sheets: 3}`; Then job → `active` → `done`, `qty=35`, `cycles_today += 3`, подій `sheet_placed` = 3 | TC | FR-10 |
| AC-14 | Given `load=626`, `pv=468`, `chp=397`, `SOC=76`; When баланс; Then `bess_kw=200`, `export≈39`, `u2 fc3 pdu3059+2` < 0, `u69 fc3 pdu37001+2` = 200000, `u71 fc3 pdu20483` = 2 (Position I, Annexe III; X-41) | UT | FR-11 |
| AC-15 | Given панель у `quiet`; When `POST /scenario/fire_drill/start {zone: FA-CNC}`; Then за 1 с LSZ:14 `present-value=test-alarm`, LSP:21405 `test-alarm`, за 3 с BV:10=1 (X-37), за 6 с усі RV `BV:1=0`, за 9 с `u85 fc2 pdu4` = 1, за 12 с BioStar події 20480 на дверях 1–5 і `u86 fc1 pdu20` = `pdu21` = 1 (X-47), за 20 с CNC-1..4 `ExternalEmergency=True`; `WriteProperty` у LSZ:14 → `write-access-denied` | TC | FR-12 |
| AC-16 | Given 35 працівників з бейджами (API-01); When sim-час проходить 06:40–07:00; Then `POST /api/events/search` за `device_id.id=5390001` повертає 35 подій з кодами 4102/4867, `tna_key="1"`, унікальні `user_id.user_id` | TC | FR-13 |
| AC-17 | Given бронювання `BATCH/IN/00001` (DOCK-W1, 06:30); When `POST /scenario/truck_arrival/start {booking: "BATCH/IN/00001"}`; Then приймач LPR отримує POST з `plateList="f3d_bookings"`, `plateListMode="allow"`, `GEOtarget="GATE-W"`, `capture_timestamp` = `sim_now` (мс; X-48); `u86 fc2 pdu1` = 1, `pdu0` = 1 (≤ 6 с); SICS `S` → `S S      25200 kg` (± 20) на етапі `weigh_in`; фура доходить до `at_dock`; на виїзді `CAM-06` POST, `S S      14000 kg` | TC | FR-14 |
| AC-18 | Given `truck_no_booking`; When запущено; Then LPR `plateList=""`, `plateListMode="none"` (X-48), DI0 лишається 0 протягом `wait_min`, подія WARNING, `GET /runs/{id}` → `done`, `result.rejected=true` | TC | FR-14 |
| AC-19 | Given токен; When `POST /scenario/machine_fault/start {device: CNC-3, reason: spindle}`; Then 201, OPC UA подія `WwAlarmConditionType` з `MessageId=E0421`, `EventCategory=4`, `ActiveState=True`; `POST …/stop` → `ActiveState=False`, `CurrentState` повертається | TC | FR-15, FR-16 |
| AC-20 | Given `/scenario/blackout/start {duration_s: 120}` (умовчання: `amf_master=hgm`, `chp_island=false`; `genset_relay` з профілем D700); When `breaker == "gen"` в API-F-01 (≈ 30 с; у запасному режимі — 15 с); Then `u71 fc3 pdu20483` = 3 (II), `pdu20486` = 0, `pdu20487` = 2, `pdu20482` = 32, `u1`/`u2 fc3 pdu3059+2` = 0, `u61 fc3 pdu32089` = 0x0303, до переключення LT-* рівні 0, крім G:40 = 100, після — групи LP-1..3 за розкладом; `fake_relay` отримав `load {"kw": 348 ± 1}` (X-67); через 120 с + повернення (`breaker == "mains"`) — `pdu20483` = 2, `pdu20486` = 2, усе відновлено, `transfer_counter` (`pdu20510+2`) += 1 | TC | FR-16, FR-11 |
| AC-21 | Given `POST /time {factor: 10}`; When 6 реальних секунд; Then `sim_now` зріс на 60 ± 2 с; `POST /time {factor: 100}` → 422; у `follow_odoo` `{factor: 10}` → 409 | TC | FR-17 |
| AC-22 | Given `SIM_CATALOG_SOURCE=odoo`, Odoo віддає API-01; When старт; Then `/status.odoo.catalog_source="odoo"`, `devices=276`; при недоступному Odoo — `"local"`, `devices ≥ 276` з yaml | TC | FR-19 |
| AC-23 | Given `SIM_ALLOW_OUTBOUND=mosquitto`; When `SIM_LPR_PUSH_URL=http://10.0.0.1/`; Then жодного TCP-з'єднання до 10.0.0.1 (перевірка через `iot_sim_outbound_denied_total ≥ 1` і мок-сокет у юніт-тесті), подія `error` | UT+TC | FR-20 |
| AC-24 | Given запущений сервіс; When `GET /sim/v1/metrics`; Then є `iot_sim_up 1`, `iot_sim_protocol_up{proto="opcua"} 1`, `iot_sim_signals_total 1017` | TC | FR-22 |
| AC-25 | Given копія демо-бази з data-модулем 19.0.1.0.0 (196 `x_f3d_signal`, N `x_f3d_reading`); When оновити модуль до 19.0.2.0.0; Then `x_f3d_signal` = 196 з тими самими `x_value`, `x_f3d_reading` = N, крон `cron_iot_sim` існує, меню «Рівень 0 (без сервісу)» під «Емулятор», `f3d.sim.panel` = 1, `f3d.sim.device` = 276, `f3d.sim.signal` = 1 168 (з них `protocol=none` — 151), `origin=mock` = 196 і всі мають `level0_code` з існуючим `x_code`, `f3d.sim.scenario` = 15 | UT (`test_migration`, з фікстурою data-модуля) + DEPLOY_TEST | FR-23, FR-25, FR-26 |
| AC-26 | Given сервіс онлайн, `read_enabled=True`; When C-01; Then `panel.state=online`, `version`, `mode`, `factor`, `sim_time` заповнені, `cron_iot_sim.active=False`, `level0_state=auto_off` | UT (мок HTTP) | FR-24, FR-28 |
| AC-27 | Given сервіс офлайн 6 хв, `level0_enabled=True`, `level0_after_min=5`; When C-01; Then `cron_iot_sim.active=True`, `level0_state=auto_on`, чаттер пульта має запис | UT | FR-28 |
| AC-28 | Given `write_enabled=False`; When `panel.action_apply_factor()`; Then `UserError` зі словами «стоп-краном», HTTP-запит не виконано (мок не викликано) | UT | FR-29 |
| AC-29 | Given `write_enabled=True`, менеджер f3d; When майстер M-11 для `filter_clogged` з `device=RV-05`; Then `f3d.sim.run` створено `state=running`, `sim_run_id` з відповіді, подія `command` без токена в `payload` | UT (мок) | FR-24 |
| AC-30 | Given API-03 з валідним `export_token`; When POST 2 події, одна з `payload.state=done` і `run_ref` існуючого запуску; Then 200 `accepted=2`, `f3d.sim.run.state=done`, повтор тих самих `event_id` → `accepted=0`, `rejected[*].reason=duplicate` | UT HttpCase | FR-24 |
| AC-31 | Given `export_token` порожній; When `GET /f3d/sim/devices`; Then 503; з невірним токеном → 401; з вірним → 200, `devices` містить `SAW-1` з 8 сигналами `workcenters/SAW-1/*` (`state`, `mode`, `alarm`, `pieces_out`, `job`, `event`, `job_cmd`, `machine_state`) і `SAW-1-PM` з 3 (`energy/consumers/SAW-1/p_now`, `kwh_shift`, `kwh_total`; X-34), `bookings[]` з `truck` = `f3d_code`, `plate` = `f3d_plate` або `null` (X-15, X-49), `zones`, `docks` = 14, `shifts` = 1 («Зміна 1»), `employees` = 35, `bookings` = 6; `If-None-Match` з поточним ETag → 304 | UT HttpCase | FR-25, FR-26 |
| AC-32 | Given користувач лише `group_f3d_user`; When відкриває пульт/пристрої/сигнали; Then читає; `write` на `f3d.sim.device` → `AccessError`; кнопки сценаріїв невидимі | UT | §4 |
| AC-33 | Given обладнання CNC-2 з `f3d_code`; When відкрити форму; Then вкладка «Емулятор» показує `f3d_sim_state`; кнопка «Збій» (менеджер) → M-10 → запис `f3d.sim.device.state=fault` | UT | FR-27 |
| AC-34 | Given `neutralize.sql` на копії; When виконано; Then усі крони модуля неактивні, параметри стоп-кранів `False`, url/токени порожні, `panel.state=unconfigured` | DEPLOY_TEST | FR-29 |
| AC-35 | Given лог сервісу при `SIM_LOG_LEVEL=DEBUG`; When виконано запити з токенами/паролями; Then у логах жодного значення токена/пароля (grep за значенням = 0 збігів); `GET /status` не містить токенів | TC | FR-30 |
| AC-36 | Given OPC UA клієнт `asyncua`; When читає `Objects/Machines`; Then 16 об'єктів типу `WwMachineType`, у `SAW-1` є `Identification.Manufacturer="HOMAG"`, `State.Machine.Flags.*` 26 булевих, `Values.RelativePiecesOut` UInt64, `JobManagement.JobOrderControl.JobOrderList` масив; анонімний `write` у `CurrentState` → `BadNotWritable` | TC | P-01 |
| AC-37 | Given `pymodbus` клієнт; When читає `u80 fc2 pdu0+12`, `u80 fc3 pdu0+24`; Then `u80 fc2 pdu0` = 1 для SLIDE-1 WORKING, лічильник `pdu0+2` росте (молодше слово першим); unit 200 → виняток 0x0B; `u11 fc3 pdu9998` → 0x02; `u80 fc3 pdu210` = 0x6050 | TC | P-02 |
| AC-38 | Given `bacpypes3` клієнт; When `Who-Is`; Then `I-Am` від 99, 101–125, 130–133, 140, 200; `ReadProperty dev 105 AI:4 present-value` = число; `SubscribeCOV` на AI:4 → повідомлення при зміні ≥ 5 Па; `ReadPropertyMultiple` 25 пристроїв ≤ 2 с | TC | P-08, P-09 |
| AC-39 | Given TCP-клієнт на 50000; When `>V:2,C:152,@1.2.1.1#`; Then `?V:2,C:152,@1.2.1.1=<0..100>#`; `>V:2,C:13,G:12,L:30,F:100#` → push усім клієнтам і `GET /signals/lighting/groups/LT-CUT/level` = 30; `>V:2,C:152,@1.2.1.99#` → `!V:2,C:152,@1.2.1.99=11#` | TC | P-08 |
| AC-40 | Given `paho` підписник `f3d/mobile/#`; When 10 с; Then ≥ 8 різних `code`, кожен JSON валідний за схемою §8.8.1; `status` retained з `online=true`; після `fault comm` FL-3 → `online=false` | TC | P-06 |
| AC-41 | Given `requests` на 8081; When `POST /api/login` з `SIM_BIOSTAR_USER/PASS`; Then 200 з `bs-session-id`; `POST /api/events/search` з ним → `EventCollection.rows`; без заголовка → 401 (`Response.code="10"`); невірний пароль → 401 `code="101"`; після 30 хв бездіяльності → 401 | TC | P-10 |
| AC-42 | Given TCP на 4001; When `SI\r\n` без машини; Then `S S          0 kg\r\n` (або ± 20); `XYZ\r\n` → `ES\r\n`; `Z\r\n` → `Z A\r\n` | TC | P-11 |
| AC-43 | Given `POST /jobs` з CSV 48 деталей (`tests/data/parts_48.csv`); When ≤ 10 с; Then `state=planned`, `plan.sheets` ∈ [6; 9], `waste_pct` < 20; `POST /jobs/{id}/release {machine: SAW-1}` → у OPC UA `JobOrderList` з'являється `JobOrderID=cj-…` у `AllowedToStart`; CSV з `Width=2500` → 422 | TC | P-04 |
| AC-44 | Given `write_enabled` споживача (тест); When Modbus FC 05 `u86 pdu16` = 1 (DO0, документ 00017); Then `u86 fc2 pdu0` (DI0) = 1 через ≤ 6 с, подія `command`; FC 06 `u11 pdu3059` → виняток 0x02 | TC | P-11, безпека |
| AC-45 | Given `SIM_ENABLED=0`; When будь-який POST `/sim/v1`; Then 423; `GET /health.status="locked"`; значення сигналів не змінюються 60 с | TC | FR-29 |
| AC-46 | Given `factor=10`, усі протоколи, 3 клієнти (OPC UA підписка на 720 вузлів, Modbus опитування 78 unit × 1 с, BACnet COV 120 об'єктів); When 10 хв; Then `iot_sim_tick_lag_seconds` p95 < 0,5 с, CPU контейнера < 100 % одного ядра, RSS < 400 МБ | TC (ТП-01) | §2.7 ARCHITECTURE |
| AC-47 | Given кожен сценарій S-01…S-15; When `start` з `params_default` → `stop` через 30 с; Then `state` відповідно `running→stopped` (або `done` для коротких), жодних винятків у логах, `cleanup` повернув змінені сигнали до моделі (значення через 2 хв у межах R-01/нормального ходу) | TC | FR-16 |
| AC-48 | Given `SIM_RESTORE_SNAPSHOT=1`; When рестарт контейнера через 5 хв роботи; Then лічильники (`kwh`, `hours`, `pieces_out`) продовжуються з останнього знімка (різниця ≤ 60 с sim-часу), запуски сценаріїв відновлюються або закриваються як `stopped` з повідомленням | TC | §8.2.3 |
| AC-49 | Given `GET /f3d/sim/devices` і `GET /sim/v1/catalog/signals.csv`; When порівняти; Then множини `code` і `address` рівні (хеш `catalog_hash` у `/status` = хеш CSV модуля) | TC (ТБ-05) | A-02 |
| AC-50 | Given сигнал `fire/groups/FA-FAC/dust = 82`; When `PUT /signals/fire/groups/FA-FAC/dust {value: 91, hold_s: 120}`; Then BACnet PIV:21607 = 91 (X-37), LSP:21607 `reliability=unreliable-other`, подія `alarm` з текстом «…запиленість 91 % при нормі до 90»; через 120 с модель знову веде значення | TC | API-16, R-25 |
| AC-51 | Given сервіс без активних сценаріїв, `SIM_GENSET_AMF_MASTER=hgm`; When `pymodbus` читає `u71 fc3 pdu20480+8`; Then `20480–20481` = `sim_now` (UNIX с), `20482` = 32 (Remote), `20483` = 2 (Position I), `20484` = 0, `20485` = 1, `20486` = 2 (Available), `20487` = 0 (Under threshold); з `SIM_GENSET_AMF_MASTER=ats` — `20482` = 16 (Auto); `u71 fc3 pdu20520` → виняток 0x02 (вилучено, X-41) | UT+TC | FR-11 |
| AC-52 | Given клієнт `pymodbus`; When читає `u11 fc3 pdu3059+2`, `u61 fc3 pdu32080+2`, `u70 fc3 pdu3001`, `u72 fc3 pdu40001`; Then F32 = `energy/consumers/SAW-1/p_now`, I32 = `infra/pv/PV-INV-1/p_kw`·1000, U16 = `equipment/COMPRESSOR/pressure_bar`·1000, U16 = `infra/totals/chp_kw` (усі ± 1 %) — адреси за документом вендора без загального «− 1» (X-42); ADAM: лічильник `u80 fc3 pdu0+2` при 65 537 = `[0x0001, 0x0001]` (молодше слово першим, X-43); кожна Modbus-адреса Додатка A містить `u<unit> fc<n> pdu<addr>[+<count>]` (регулярка telemetry R-24 шаблон (0), X-72) | UT+TC | FR-02 |
| AC-53 | Given `write_enabled` споживача (тест); When FC 05 `u86 pdu21` = 1 (DO5); Then GATE-E лишається відкритим, поки DO5 = 1 (`u86 fc2 pdu2` = 1 після звільнення петлі), GATE-W не змінюється; FC 05 `u86 pdu20` = 1 (DO4) тримає лише GATE-W; `fire_drill` +12 с → `u86 fc1 pdu20+2` = `[1, 1]` (X-47) | TC | FR-14, FR-12 |
| AC-54 | Given API-01 `bookings` з `TRUCK-OUT-1` (`plate="АА4512КТ"`, `BATCH/OUT/00004`, DOCK-E2) і `TRUCK-IN-1` (`plate=null`), sim-час 14.10.2026 08:15:05,507 Київ; When `truck_arrival {"booking": "BATCH/OUT/00004"}`; Then POST LPR: `plateUnicode="АА4512КТ"`, `plateText="AA4512KT"`, `capture_timestamp="1791954905507"` (= `sim_now`, мс UTC), `datetime="20261014 081505507"`, `plateList="f3d_bookings"`, `plateListMode="allow"`, `plateListDescription` починається з `BATCH/OUT/00004` (X-48, X-49); для `TRUCK-IN-1` — згенерований детермінований номер ≠ `АА4512КТ` | UT | FR-14 |
| AC-55 | Given 35 працівників (API-01); When sim-час 06:40–07:00; Then код події входу кожного = 4102, якщо `det(code) % 2 == 0`, інакше 4867 (X-50); When `POST /api/events/search` з `orders [{"column": "datetime", "descending": false}]`, `limit=10`, `offset=0`, далі `offset=10`; Then `datetime` не спадає в межах і між сторінками, 20 різних `id` без пропусків; запит з `hint` = `rows[-1].hint` першої сторінки (без `offset`) дає ту саму другу сторінку; `descending=true` — спадання | UT+TC | FR-13 |
| AC-56 | Given панель у `quiet`; When `POST /sim/v1/device/FA-CUT/fault {"reason": "sensor"}`; Then 200, `LSZ:12` = fault(3), `LSZ:0` = fault, `MSV:1` = 3, `PIV:2` = 1, BV шлейфу FA-CUT = 0, подія `fault` (X-36, X-60); `POST …/clear` → `quiet`, `PIV:2` = 0; `{"reason": "loop"}` → ще й BV шлейфу = 1; `{"reason": "spindle"}` → 422; `fault` на `PV-ROOF` (пасивний без `lsz`) → 422 | TC | FR-12, FR-15 |
| AC-57 | Given TCP-клієнт на 50000, `SIM_HELVAR_VERSION=2`; When `>V:2,C:13,G:19,L:50,F:200,A:1#`; Then відповідь відправнику `!V:2,C:13,G:19,L:50,F:200,A:1=0#` і push `>V:2,C:13,G:19,L:50,F:200#` усім клієнтам; без `A` — лише push; `>V:1,C:152,@1.3.1.20#` → `?V:1,C:152,@1.3.1.20=50#` (версія відповіді = версії запиту); `>V:2,C:164,G:16#` → кадр `?V:2,C:164,G:16=@1.2.3.1,…,@1.2.3.64$` і кадр `?V:2,C:164,G:16=@1.2.4.1,…,@1.2.4.27#`; `>V:2,C:191#` → `?V:2,C:191=2#`. Given `SIM_HELVAR_VERSION=1`; Then `>V:2,C:152,@1.2.1.1#` → `!V:2,C:152,@1.2.1.1=18#`, `>V:1,C:191#` → `?V:1,C:191=1#` (X-64) | TC | P-08 |
| AC-58 | Given `factory3d.base.environment=prod`; When `post_init_hook`; Then `factory3d.iot_sim.read_enabled='False'`, `write_enabled` не змінено; Given `environment=test`; Then `read_enabled='True'`; повторний запуск хука — той самий результат (X-56) | UT | FR-29 |
| AC-59 | Given модуль установлено; Then `menu_f3d_sim_root.parent_id` = `factory3d_base.menu_f3d_root`, `sequence` = 90; `menu_iot_root.parent_id` = `menu_f3d_sim_root`, `sequence` = 9; `menu_f3d_sim_settings.parent_id` = `factory3d_base.menu_f3d_config`, `sequence` = 90; серед дочірніх `maintenance.menu_maintenance_title` пунктів модуля немає (X-31) | UT | §3.14 |
| AC-60 | Given мок `fake_relay` (API-F-01…F-09) і `blackout {"duration_s": 120}` з умовчаннями (`amf_master=hgm`, `chp_island=false`); When мок повертає `breaker="gen"`; Then емулятор викликав API-F-02 `mains {"available": false}` рівно раз, `u71 pdu20483` = 3, API-F-04 `load {"kw": 348 ± 1}` (`P_genset = P_crit − chp_kw − pv_now + bess_kw`, X-67); з `chp_island=true` (день) → `chp_kw = 348`, `load {"kw": 0}`; з `genset_load_kw=200` → `load {"kw": 200}`; з `amf_master=ats` → API-F-03 `remote_start {"on": true}` через 3 ± 1 с, API-F-02 не викликано, `20484` = 1, `20482` = 16; без `gen_ok` 30 с → подія «FAIL START», `20483` = 2; `genset_test {"test_on_load": false}` → `remote_start` on, через `duration_s` off, `20483` = 2 весь час; порожній `SIM_GENSET_RELAY_TOKEN` → запасний режим (переключення через 15 с), запуск не `failed` (X-59) | UT (мок HTTP) + TC | FR-16, FR-11 |
| AC-61 | Given клієнт `bacpypes3`; When `ReadProperty dev 200 object-list`; Then типи об'єктів ⊂ {`device`, `life-safety-zone`, `life-safety-point`, `binary-value`, `multi-state-value`, `positive-integer-value`} — жодного AI/AV/BI (X-37); `BV:1…4` = 0, `BV:10` = 0, `BV:11` = 0, `PIV:1…3` = 0, `PIV:21607` = 82, `MSV:1` = 1 (`fire/totals/system_state`), `LSZ:0` = quiet (`fire/totals/state`, X-36); `WriteProperty` у BV/PIV/MSV → `write-access-denied` | TC | FR-12, P-09 |
| AC-62 | Given `catalog/signals.csv`; Then 1 168 рядків, коди унікальні, № 1…662 — колишні коди без перенумерації; № 1 167–1 168 — `fire/groups/FA-SOC/state` (LSZ:34) і `fire/groups/FA-OFFICE/state` (LSZ:35), P-09 (№ 12г); 151 рядок `protocol=none` (energy 55, machine_connect 37, bms 59) з адресою «обчислює <модуль> …» (X-34, X-35; рядок 1 166 — «команда rest_vendor cutopt, власник machine_connect …», X-76); рядки 663–680 — `energy/consumers/<X>/p_now\|kwh_shift` для unit 51…59 (X-61); рядки 644/646/654/656 — по одному входу; рядки 600–602 — агрегат роутера `@1.<r>.0.0`; 58 рядків `…/level`, `…/heating_valve` — `scale` ×1 (X-39); `GET /sim/v1/signals` → `count=1017`, жодного коду `protocol=none`, `GET /signals/energy/consumers/SAW-1/kwh_shift` → 404; `u51 fc3 pdu3059+2` = `p_now` OFFICE (17,6 ± 10 %) | UT+TC | FR-02, FR-26 |
| AC-63 | Given `follow_odoo`, `mrp.workorder` id 13 на SAW-1 у `progress`; Then `SAW-1.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID = "WO00013"`; When WO 13 → `done`; Then елемент лишається в `JobOrderList` зі станом `Ended/Completed` до початку наступної зміни; у `scenario` без Odoo — `SIM-00001`…; рядки каталогу `workcenters/*/state` (P-01) мають поріг «—» (заявки лише з `…/alarm`) (X-38) | UT+TC | FR-04 |
| AC-64 | Given RV-05 `k=0,72`, режим AQ, `outdoor_c=9`; Then `heat_kw = 6,9 ± 0,1`, `heating_valve = 6` (%), BACnet dev 105 AO:1 = 6 (не 0,06); RV-01 (VE, `k=0,68`) → 17,3 кВт / 15 %; `lighting/groups/LT-CUT/level` = 100 при рівні 1,0 і C:152 = 100 (X-39, X-40); EF-CHG `BI:1=0 ∧ BI:7=1` 61 с → подія рівня `alarm`; S-15 `fault_device=@1.2.1.5` → `>V:2,C:110,@1.2.1.5#` = `=2#`; у `blackout` світильник групи EMERGENCY → `=1024#` | UT+TC | P-08 |
| AC-65 | Given склад груп емулятора за правилом §8.10.4 (bms R-06); Then для кожної з 32 груп список адрес C:164 дорівнює `dali_devices` bms Додаток A.1 (копія `tests/data/bms_dali_devices.csv`): `LT-EB` `@1.2.1.28-54`, `LT-CNC` `@1.2.2.1-27`, `LT-FAC` `@1.2.3.1-64;@1.2.4.1-27`, `LT-OUT-1` `@1.3.1.59-62`, `LT-OUT-2` `@1.3.2.1-4`; разом 320 світильників; датчики 322 — адреси 65…70 кожної лінії (X-65) | UT | P-08 |
| AC-66 | Given модель `facp` з `plant/fire.py` (222 сповіщувачі, 36 ручних, 41 оповіщувач, 3 полум'я); Then 302 об'єкти LSP з унікальними id за fire R-23 (A-09): `2.FAC.07` → LSP:21607, `2.CNC.05` → 21405, `1.RCV-1.01` → 10101, `1.MCP.01` → 19001, `4.MCP.09` → 49009, `2.SND.13` → 29113, `2.FLM.01` → 29201; `object-name` LSP = адреса пристрою; PIV:<id> — лише для 222 сповіщувачів; `0.SPK/NOZ/SV.*` LSP не мають; `3.SOC.01` → LSP:33401, `3.OFFICE.08` → LSP:33508 (LSZ 34/35); ReadProperty LSP:19001 `present-value` = `quiet` (X-79) | UT + TC | FR-12 |
| AC-67 | Given `catalog/signals.csv`; Then рядок 334 `equipment/GANTRY-1/stacks` і рядок 1 166 `equipment/CUTOPT/cmd` мають `protocol=none` (адреса «обчислює machine_connect з woodStore API-21 …» / «команда rest_vendor cutopt, власник machine_connect …»), пристрій `CUTOPT` пасивний без `equipment_id`; `GET /sim/v1/signals/equipment/GANTRY-1/stacks` → 404; `GET /api/v1/stacks` (API-21) віддає 23 стоси з `qty > 0` (X-76) | UT + TC | FR-10, FR-26 |
| AC-68 | Given `.env` проєкту compose з `RELAY_SIM_TOKEN`; When `docker compose -f docker-compose.sim.yml --profile dev config`; Then сервіс `genset_relay` має мережі `f3d_sim` і `odoo_default`, `environment` `RELAY_PROFILE=d700`, `RELAY_PORT=8000`, `RELAY_SIM_TOKEN`, `RELAY_TIME_FACTOR=1`, `RELAY_TZ=Europe/Kyiv`, healthcheck на порт 8000, без `ports`; `iot_sim.environment.SIM_GENSET_RELAY_TOKEN` = `RELAY_SIM_TOKEN`; When `up`; Then з контейнера Odoo `genset_relay:8000` досяжний, `GET /sim/v1/state` з токеном → `"profile": "D700"` (td_genset §8.5 CI-02, X-75) | TC | FR-01 |

---

## 13. План тестування (для Opus)

### 13.1 Юніт-тести

Сервіс (`services/iot_sim/tests/unit`, `pytest -m unit`, без мережі; фікстура `world(seed=20261012, clock=FakeClock(2026-10-12 10:30 Київ))`):

| Файл | Клас/тест | Фікстури | Що assert | AC |
|---|---|---|---|---|
| `test_rng.py` | `test_golden_sequence` | — | `Rng(20261012, "equipment/COMPRESSOR/pressure_bar")` перші 10 `r` = `golden_rng.json` (еталон згенеровано скриптом `tools/golden_from_mock.py`, який повторює формулу `action_iot_tick` у чистому Python) | AC-04 |
| `test_clock.py` | `test_factor_monotonic`, `test_set_time`, `test_dst_transition` | `FakeRealTime` | `now()` росте на `dt·factor`; `set()` не ламає монотонність UTC; 26.10.2026 03:00 локальний повтор без дублів хвилинних кроків | AC-06, §11 |
| `test_models_noise.py` | `test_noise_formula`, `test_noise_threshold_alarm` | сигнал compressor | значення за R-01 з точністю 1e-9; `alarm=below, threshold=6.0` → `status=alarm` при 5,99 | AC-04 |
| `test_models_machine.py` | `test_state_logic_table` (параметризований 32 комбінації прапорів), `test_power_by_state`, `test_pieces_counter`, `test_fault_clear`, `test_job_order_id_format`, `test_completed_job_stays_in_list` | `machine("SAW-1")`, фейкові WO з Odoo (id 13) і синтетичні | `CurrentState` за таблицею §7.7 стандарту; `p_now` R-02; `pieces_out` за 15 хв = 6; після `fault(spindle)` → ERROR, подія `E0421`; `clear` → WORKING, якщо завдання; `JobOrderID == "WO00013"`, синтетичне `SIM-00001`; після `done` елемент у списку зі станом `Ended/Completed` до зміни (X-38) | AC-07, AC-19, AC-63 |
| `test_models_mobile.py` | `test_drain_cycle`, `test_route_to_charge`, `test_hours_only_when_busy` | `mobile("FL-2")`, зони з `zones.json` | R-05 межі 20/95, швидкість зарядки 0,6 %/хв; точка (x,y) у полігоні Z-CHG; `hours` не росте в `charging` | AC-08 |
| `test_models_drift.py` | `test_drift_rate`, `test_reset_on_maintenance_closed` | `roofvent("RV-05")` | +0,05·(1+0,5r)/хв; `maintenance_closed` → 120 | AC-09 |
| `test_models_boiler.py` | `test_level_refill`, `test_boilers_on_logic` | | R-10 | AC-10 |
| `test_models_pv.py` | `test_parabola_matches_mock`, `test_astral_zero_at_night`, `test_inverter_status_enum` | | AC-11 значення; 23:00 → `0xA000` | AC-11 |
| `test_models_compressor.py` | `test_load_from_production`, `test_fault_pressure_drop` | 35 WORKING | load ≥ 80; `compressor_fault` → 5,5 за 15 хв | AC-12 |
| `test_models_energy.py` | `test_balance`, `test_meter_aggregation`, `test_transformer_temp`, `test_ats_annexe3_registers`, `test_island_genset_load`, `test_island_chp_variants` | значення макета; `ats(amf_master=hgm\|ats)`; `P_crit=348`, `P_crit=600` | AC-14; сума фідерів = ввід; `38 + 60·345/1000 = 58,7`; регістри 20480…20487 за §8.9.4 (`20483=2`, `20482=32\|16`); острів: `P_genset` = 348 (`chp_island=false`), 0 (`true`, день), 558 (`P_crit=600`), до переключення `bess_kw=−200` (X-41, X-67) | AC-14, AC-51, AC-60 |
| `test_models_facp.py` | `test_drill_timeline`, `test_contamination_reliability`, `test_zone_fault_sensor`, `test_zone_fault_loop`, `test_object_types`, `test_lsp_ids_fire_r23` | `FakeClock`, пристрій `FA-CUT` (`lsz=12`) | кроки 0/3/6/9/12/20 с (на 12 с — `u86` DO4 і DO5); `PIV > 90` → `unreliable-other`; `fault(sensor)` → LSZ:12 `fault`, `PIV:2=1`, BV шлейфу 0; `fault(loop)` → BV шлейфу 1; об'єкти dev 200 лише LSZ/LSP/BV/MSV/PIV (X-36, X-37, X-60); LSP id за fire R-23: 302 унікальні, `1.MCP.01` → 19001, `4.MCP.09` → 49009, `2.SND.13` → 29113, `2.FLM.01` → 29201, `2.FAC.07` → 21607, PIV лише для 222 сповіщувачів (X-79) | AC-15, AC-50, AC-56, AC-61, AC-66 |
| `test_models_access.py` | `test_checkin_schedule`, `test_event_codes`, `test_det_parity`, `test_search_order_offset_hint` | 35 employees | 35 подій 06:40–07:00, коди ∈ {4102, 4867}, `tna_key=1`; код = 4102 ⇔ `det(code) % 2 == 0`; сторінки за зростанням `datetime` через `offset` і через `hint` однакові (X-50) | AC-16, AC-55 |
| `test_models_yard.py` | `test_truck_state_machine`, `test_no_booking_rejected`, `test_scale_weights`, `test_lpr_payload`, `test_plate_from_bookings`, `test_hold_channels` | booking BATCH/IN/00001, BATCH/OUT/00004 (`plate="АА4512КТ"`) | послідовність станів R-29; `rejected` з `plateListMode="none"`; брутто 25 200; `capture_timestamp` = `sim_now` мс, `plateList="f3d_bookings"`, `plateListMode="allow"`; номер `TRUCK-OUT-1` = `АА4512КТ`, `TRUCK-IN-1` — згенерований; DO4 тримає лише GATE-W, DO5 — лише GATE-E (X-47…X-49) | AC-17, AC-18, AC-53, AC-54 |
| `test_world.py` | `test_determinism_two_worlds`, `test_factor_invariance`, `test_snapshot_roundtrip` | | AC-05, AC-06, AC-48 (без контейнера) | |
| `test_scenarios.py` | `test_each_scenario_start_stop` (параметризований 15), `test_conflict_409`, `test_params_validation`, `test_blackout_relay_calls`, `test_genset_test_on_load`, `test_relay_fallback` | мок `fake_relay` (`respx` для `httpx`) | AC-47 логіка, 409, 422; послідовність викликів API-F-02/F-03/F-04 за варіантами `hgm`/`ats`, `load.kw` за R-22, `genset_load_kw`, `test_on_load`; без токена — запасний режим (X-59, X-67) | AC-47, AC-60 |
| `test_registry.py` | `test_catalog_load_1168`, `test_computed_rows`, `test_owner_rows_x76`, `test_modbus_pdu_form`, `test_devices_yaml_fallback`, `test_catalog_hash` | `catalog/` | 1 168 сигналів (1 017 емульованих, 151 `protocol=none`), 276 пристроїв, хеш стабільний; кожна Modbus-адреса містить `u<unit> fc<n> pdu<addr>[+<count>]` (X-42, X-72); `/signals` без `protocol=none` (X-35); рядки 334 і 1 166 — `protocol=none` machine_connect, пристрій `CUTOPT` пасивний без обладнання (X-76) | AC-22, AC-49, AC-52, AC-62, AC-67 |
| `test_outbound_guard.py` | `test_denied_host` | мок `socket.create_connection` | `OutboundDenied`, метрика | AC-23 |
| `test_models_hvac.py` | `test_heat_formula_bms_r13`, `test_valve_percent`, `test_ef_chg_alarm`, `test_lighting_level_percent`, `test_c110_bits` | `roofvent("RV-05")`, `roofvent("RV-01")`, `fan("EF-CHG")`, `lighting` | `heat` 6,9 / 17,3 кВт, `heating_valve` 6 / 15 %, AO:1 у %; `level` 100 %; EF-CHG `stopped_charging` 61 с → `alarm`; C:110 `=2#`, у `blackout` EMERGENCY `=1024#` (X-39, X-40) | AC-64 |
| `test_lighting_layout.py` | `test_dali_layout_matches_bms` | `tests/data/bms_dali_devices.csv` (копія bms Додаток A.1) | склад 32 груп за правилом bms R-06 = таблиця bms A.1 дослівно (X-65) | AC-65 |

Odoo (`odoo_addons/factory3d_iot_sim/tests`, теги `post_install, -at_install, f3d`, `SimCase` з `responses`-подібним моком `requests` через `unittest.mock.patch("requests.Session.request")`):

| Файл | Тест | Фікстури | Assert | AC |
|---|---|---|---|---|
| `test_panel.py` | `test_poll_online_disables_level0`, `test_poll_offline_enables_level0_after_n_min`, `test_apply_factor_blocked_by_stop_crane`, `test_apply_factor_follow_odoo_409`, `test_menu_under_base_root` | параметри url/токен, мок `/status` | AC-26, AC-27, AC-28; `UserError` тексти; батьки й `sequence` меню (X-31) | AC-26…28, AC-59 |
| `test_device.py` | `test_fault_wizard_calls_api`, `test_clear`, `test_code_regex`, `test_unit_unique`, `test_reason_loop_only_lsz` | пристрій CNC-2, пасивний `FA-CUT` (`params.lsz=12`) | `state=fault`, тіло запиту `{"reason":"spindle"}`, `ValidationError` для `cnc 2`, дубль unit → помилка; `reason=loop` для CNC-2 → `ValidationError`, для `FA-CUT` — запит `{"reason":"loop"}` (X-60) | AC-33, AC-56 |
| `test_signal_catalog.py` | `test_csv_loaded_1168`, `test_mock_signals_have_level0`, `test_unknown_device_creates_passive`, `test_computed_protocol_none` | hook | 1 168, 196 з `level0_code`, WARNING; 151 запис `protocol='none'`, `action_read_now` на них → `UserError` без HTTP | AC-25, AC-62 |
| `test_scenario_run.py` | `test_run_wizard_creates_run`, `test_validate_params`, `test_stop` | мок 201 | AC-29 | AC-29 |
| `test_api_devices.py` (HttpCase) | `test_devices_401_503_200_304`, `test_events_post_dedup`, `test_health`, `test_bookings_truck_plate` | токен у параметрі; пакет з `f3d_code='TRUCK-OUT-1'` і (якщо yard) `f3d_plate` | AC-30, AC-31; `bookings[].truck` = `f3d_code`, `plate` = `f3d_plate` або `null`; `docks[].accepts` — назви категорій, `zones` Z-CUT за base C (X-15, X-49, X-54) | AC-30, AC-31 |
| `test_security.py` | `test_user_readonly`, `test_manager_no_settings`, `test_token_fields_admin_only` | користувачі 3 груп | `AccessError`; поля токенів недоступні менеджеру (`fields_get` без них) | AC-32 |
| `test_migration.py` | `test_upgrade_keeps_level0`, `test_hook_read_enabled_by_environment` | фікстура: встановити data-модуль з `odoo_addons/factory3d_iot_sim` 19.0.1.0.0 (копія в `tests/fixtures/level0/`), створити 196 `x_f3d_signal` через `signal_specs`, потім `upgrade`; параметр `factory3d.base.environment` = `test` / `prod` | AC-25 кількості; `read_enabled` = `'True'` / `'False'` після хука (X-56) | AC-25, AC-58 |

### 13.2 Стендові сценарії (ТК) — проти `docker compose --profile dev`

Передумови для всіх: `.env` з токенами; `tests/stand/conftest.py` чекає `GET /health = ok`; клієнти: `asyncua` (ТК-01, 05), `pymodbus` (02, 06, 07, 09, 12), `bacpypes3` (03, 08), `paho-mqtt` (04), `requests` (10, 11, 13), `socket` (11, 17). Після кожного ТК — `POST /reset`.

| ТК | Назва | Передумови (сценарій емулятора) | Кроки | Очікуваний результат | Де дивитися |
|---|---|---|---|---|---|
| ТК-01 | OPC UA: адресний простір і стани | `follow_odoo` з копією демо-бази (або `scenario` + `shift`) | 1) browse `Machines`; 2) read `SAW-1…CurrentState`, `CNC-2…CurrentState`, `Flags`, `Values`; 3) підписка DataChange на `RelativePiecesOut` 2 хв; 4) спроба write | AC-36, AC-07: 16 об'єктів, SAW-1=3, CNC-2=4, лічильник +6/15 хв, `BadNotWritable` | `/sim/v1/signals?prefix=workcenters/SAW-1`, UaExpert |
| ТК-02 | Modbus: лічильники PM5560 і I/O | `shift` | 1) read `u11 fc3 pdu2999+112`, `pdu3203+12`; 2) read `u1`/`u2`; 3) read `u80 fc2 pdu0+12`, `fc3 pdu0+24`; 4) помилкові unit/адреси; 5) write DO `u86` (FC 05 `pdu16`, `pdu20`, `pdu21`); 6) read `u51…u59 fc3 pdu3059+2` | AC-03, AC-37, AC-44, AC-52, AC-53, AC-62; сума `u3…u8 fc3 pdu3059+2` ≈ `u1` + `u2` (±1 %); INT64 росте; лічильник ADAM — молодше слово першим | `/signals?prefix=energy` |
| ТК-03 | BACnet: вентиляція й котельня | — | 1) Who-Is; 2) RPM 25 RV; 3) COV AI:4 dev 105; 4) write AO:1 dev 105 = 80 (пріоритет 8); 5) write MSV:1 = 7 (ST) | AC-38, AC-64; AI:3 dev 105 → 0 після ST, BI:1=0; AO:1 у % (80 = 80 %) утримується 10 хв | `/signals?prefix=ventilation/units/RV-05` |
| ТК-04 | MQTT: телематика | `shift`, `battery_low FL-2 level_pct=18` | 1) підписка `f3d/mobile/#`; 2) 3 хв; 3) `fault comm FL-3` | AC-08, AC-40 | mosquitto_sub, 3D (рух FL-2 у зарядну) |
| ТК-05 | Портал: woodStore + OPC UA | `shift` (SAW-1 WORKING) | 1) `GET /api/v1/stacks`; 2) `POST /jobs feed 3 аркуші`; 3) `GET /api/v1/status` кожні 5 с; 4) read OPC UA `GANTRY-1…CurrentState`; 5) `GET /sim/v1/signals/equipment/GANTRY-1/stacks` | AC-13, AC-67; стан moving/picking/placing; `qty −3`; крок 5 → 404 (сигнал обчислює machine_connect, X-76) | картка PLT-04C у переглядачі |
| ТК-06 | Інженерія: компресор, аспірація, трансформатори, вода | `compressor_fault pressure_drop` | 1) read `u70 fc3 pdu3000+30` до/після; 2) `u90 fc3 pdu0+4` (raw) і `pdu30+8` (float, молодше слово першим); 3) `u96 fc3 pdu0+6`; 4) `u84 fc2 pdu0+2`, лічильник `u84 fc3 pdu16+2` за 10 хв sim | AC-12; тиск < 6,0 через ≤ 15 хв → `status=alarm`, подія; AI масштаб R-20; вода +350 імп | `/signals?prefix=equipment/COMPRESSOR` |
| ТК-07 | Енергетика: СЕС, BESS, КГУ, АВР, blackout | `pv_cloudy cf=0.3` потім `blackout duration_s=120` (умовчання `hgm`), потім `blackout {"duration_s": 120, "amf_master": "ats", "chp_island": true}` | 1) read `u61…u68 fc3 pdu32080+2`, `pdu32089`, `pdu32114+2`, `pdu32106+2`; 2) `u69 fc3 pdu37000+51` (без перекриттів, X-51); 3) `u72 fc3 pdu40000+21`; 4) `u71 fc3 pdu20480+8` до/під час/після blackout; 5) `u1`/`u2 fc3 pdu3059+2`; 6) журнал `fake_relay` API-F-09 / `load` | AC-11, AC-14, AC-20, AC-51, AC-60; `load.kw` 348 (варіант A, КГУ стоїть), 0 (`chp_island=true`, день) | `/signals?prefix=infra` |
| ТК-08 | Пожежна панель: навчання і несправність | `fire_drill FA-CNC` ; потім `filter_clogged FA-FAC value=92` | 1) COV на LSZ:14, BV:10, dev 105 BV:1; 2) читання LSP:21405; 3) write LSZ/BV/PIV → denied; 4) PIV:21607 після другого сценарію; 5) `POST /device/FA-CUT/fault {"reason":"sensor"}` → `clear`, потім `{"reason":"loop"}`; 6) `object-list` dev 200; 7) RPM `object-name` LSP:19001, 29113, 29201 | AC-15, AC-50, AC-56, AC-61, AC-66 (302 LSP, `1.MCP.01`/`2.SND.13`/`2.FLM.01`, X-79); BioStar події 20480 на 5 дверях; u85 DI4 | `/events?kind=fire`, журнал подій 3D |
| ТК-09 | Іскрогасіння, димовидалення | `spark count=2 interval_s=30` | 1) опитування `u85 fc2 pdu0+7` кожні 0,2 с; 2) лічильник `u85 fc3 pdu0+2`; 3) write DO0 (FC 05 `pdu16`) | імпульси 0,6/2 с, `count_today += 2`, DI4 через 60 с після DO0 | — |
| ТК-10 | СКУД: BioStar 2 | sim-час 06:30 (`POST /time {set}`), `factor=10` | 1) login; 2) 5 хв реального часу; 3) `events/search` за ACR-IN; 4) `access_event ACR-ELEC code=6400`; 5) logout, повтор запиту | AC-16, AC-41, AC-55; сторінки `descending=false` через `offset` і `hint` однакові; `6400` з `user` і дверима 2; після logout → 401 | — |
| ТК-11 | Двір: LPR, шлагбаум, ваги | `truck_arrival BATCH/IN/00001`, потім `truck_no_booking` | 1) приймач LPR (`/lpr-sink` або тестовий HTTP-сервер у `SIM_LPR_PUSH_URL`); 2) опитування `u86 fc2 pdu0+6`, `fc1 pdu16+6`; 3) SICS `SIR` потік; 4) події; 5) `truck_arrival BATCH/OUT/00004` (номер з `f3d_plate`) | AC-17, AC-18, AC-42, AC-54 | 3D: фура біля воріт, `/events?kind=yard` |
| ТК-12 | Верстати без інтерфейсу: цикли | `shift`, `machine_fault ASM-3 reason=emergency` | 1) `u82`/`u83 fc2 pdu0+12`, `fc3 pdu0+20`; 2) 10 хв sim; 3) fault/clear | AC-37; ASM-3 coil fault=1, run=0; лічильник ASM-1 += 1 за 6 хв | — |
| ТК-13 | REST керування і стоп-крани | — | 1) усі ендпоінти API-10…API-19 з/без токена; 2) `stop-all` → POST → 423; `resume`; 3) `SIM_ENABLED=0` рестарт; 4) `PUT /signals/... hold` | AC-21, AC-24, AC-45, AC-50 | — |
| ТК-14 | Прискорення часу | `factor=10`, `shift` | 1) 10 хв реального часу; 2) порівняти лічильники з ТК при `factor=1` за 100 хв sim | AC-06, AC-21; підписники бачать стрибки ≤ 10 с sim на 1 с реального | — |
| ТК-15 | Odoo-пульт наскрізно | сервіс + копія демо-бази з модулем 19.0.2.0.0 | 1) Налаштування → url/токени → «Перевірити зв'язок»; 2) Пульт: прискорення 5 (у `scenario`), режим; 3) Сценарії → `filter_clogged` (`device=RV-05`, `value=285`) → запуск; 4) Обладнання CNC-2 → «Збій» → «Скинути»; 5) зупинити сервіс на 6 хв → рівень 0 увімкнувся; запустити → вимкнувся | AC-25…AC-29, AC-33, AC-58, AC-59; пульт — у меню «Завод 3D → Емулятор» (X-31); у `f3d.sim.event` — події запуску; заявка ТО від рівня 0 для RV-05 (якщо рівень 0 був активний) | Odoo UI, чаттер пульта |
| ТК-16 | Відновлення після рестарту | `shift` 5 хв, `machine_fault CNC-3` | 1) `docker restart iot_sim`; 2) `/status`, лічильники, стан CNC-3 | AC-48: лічильники продовжені, CNC-3 у fault (запуск `running` або закритий `stopped` з повідомленням «restored») | лог «restored snapshot» |
| ТК-17 | HelvarNet: версії, підтвердження, склад груп | `SIM_HELVAR_VERSION=2`, потім рестарт з `1`; `lighting_scene {"group": "LT-CUT", "fault_device": "@1.2.1.5"}` | 1) два TCP-клієнти на 50000; 2) C:13 з `A:1` і без; 3) C:152 з `V:1`/`V:2`; 4) C:164 для G:12, G:16 (кадри `$`); 5) C:110 `@1.2.1.5`; 6) C:191; 7) після рестарту з `1` — `V:2` → 18 | AC-39, AC-57, AC-64, AC-65; відповіді у версії запиту, `!…=0#` лише при `A:1`, склад груп = bms Додаток A.1 (X-64, X-65) | `/signals?prefix=lighting/groups/LT-CUT` |
| ТК-18 | Compose: `genset_relay` за CI-02 | `.env` з `RELAY_SIM_TOKEN` (32 симв.), `TD_GENSET_PATH` на клон `td_genset` | 1) `docker compose --profile dev config`; 2) `up -d iot_sim mosquitto genset_relay`; 3) `docker compose ps` (health); 4) з контейнера Odoo `curl http://genset_relay:8000/sim/v1/state` з токеном і без; 5) `GET /sim/v1/status` емулятора → `protocols`, стан генератора | AC-68: env і мережі за td_genset §8.5; з токеном 200 `profile=D700`, без — 401; емулятор не в запасному режимі (немає події «Ретранслятор генератора недоступний») (X-75) | `docker compose ps`, лог `iot_sim` |

### 13.3 Тести безпеки (ТБ)

| ТБ | Перевірка | Очікувано |
|---|---|---|
| ТБ-01 | `docker compose --profile demo config` і `docker ps`: порти 502/4840/47808/… не опубліковані на хост; мережа `f3d_sim` internal; контейнер без capabilities, read-only FS | так |
| ТБ-02 | REST без токена / з хибним / з токеном іншої довжини; 6 хибних за хвилину | 401; 429 на 60 с |
| ТБ-03 | Ін'єкції: `POST /device/../etc/passwd/fault`, `code="CNC-2; DROP"`, 10 КБ `note`, `params` з вкладеністю 100 | 404/422, сервіс живий, лог без трасувань |
| ТБ-04 | BACnet write у dev 200 (LSZ, LSP, PIV, BV, MSV), `ReinitializeDevice`, `DeviceCommunicationControl`; OPC UA write у `State.*`; Modbus write у PM5560/Huawei RO; BioStar `DELETE /api/users/1` | усі відхилені, подія/лог WARNING, стан не змінився |
| ТБ-05 | Хеші каталогу: `services/iot_sim/catalog/signals.csv`, `odoo_addons/.../data/f3d_sim_signal.csv`, `GET /sim/v1/catalog/signals.csv`, `GET /f3d/sim/devices` (сигнали) | 4 однакові множини `code+address`; тест падає при розсинхроні |
| ТБ-06 | Логи з `SIM_LOG_LEVEL=DEBUG` після 15 хв роботи і ТК-10/13 | `grep` за значеннями `SIM_API_TOKEN`, `SIM_BIOSTAR_PASS`, `SIM_ODOO_APIKEY`, `bs-session-id` → 0 збігів |
| ТБ-07 | Allow-list: `SIM_LPR_PUSH_URL` і `SIM_ODOO_URL` на хост поза списком | жодного з'єднання (tcpdump у контейнері-спостерігачі), метрика `outbound_denied` |
| ТБ-08 | Odoo: користувач `group_f3d_user` — спроби `write/create/unlink` на всіх моделях модуля; менеджер — доступ до `res.config.settings` полів токенів; `f3d_sim_reader` — спроба `write` через XML-RPC | `AccessError`; поля відсутні; `AccessError` |
| ТБ-09 | API-01/03 з `export_token` ≠ `token` (переплутані) | 401; жоден з токенів не приймається «навхрест» |
| ТБ-10 | `neutralize.sql` на копії, потім спроба кнопок | `UserError` «не налаштовано», крони неактивні |

### 13.4 Тести продуктивності (ТП)

| ТП | Навантаження | Критерій |
|---|---|---|
| ТП-01 | AC-46 (3 клієнти, `factor=10`, 10 хв) | tick lag p95 < 0,5 с; CPU < 1 ядра; RSS < 400 МБ |
| ТП-02 | 20 Modbus-клієнтів × 50 запитів/с (1 000 зап/с) по всіх unit | p99 відповіді < 50 мс, 0 помилок, tick lag < 1 с |
| ТП-03 | BACnet: `ReadPropertyMultiple` усіх ~400 об'єктів щосекунди + 120 COV | відповіді < 2 с за цикл; CPU BACnet-таска < 30 % |
| ТП-04 | OPC UA: 10 клієнтів × підписка на всі 720 вузлів, publishing 500 мс | DataChange затримка < 1 с; пам'ять стабільна 30 хв |
| ТП-05 | `GET /sim/v1/signals` (1017) 10 раз/с | p95 < 100 мс |
| ТП-06 | Odoo: C-01 протягом 24 год, 2 000 подій/добу через API-03 | крон ≤ 1 с на прогін; `f3d.sim.event` ротація працює; `f3d.sim.signal` refresh 1017 записів (без `protocol=none`) ≤ 5 с |
| ТП-07 | `factor=60`, 8 год sim за 8 хв | лічильники збігаються з `factor=1` еталоном ± 0,5 %; жодних пропущених подій зміни (06:40 відмітки, 07:00 старт) |

### 13.5 Чек-лист DEPLOY_TEST

1. Зняти копію демо-бази (`odoo` на timur-o19demo) → `odoo_test_sim`; зафіксувати: `x_f3d_signal`=196, `x_f3d_reading`=N, `maintenance.equipment`=210, стан крона рівня 0.
2. Встановити/оновити `factory3d_base` (хвиля 1), потім `factory3d_iot_sim` 19.0.2.0.0 (`-u factory3d_iot_sim`), перевірити лог hook: `devices=276`, `signals=1168` (`protocol=none` 151), `level0 matched=196/196`, `scenarios=15`, `read_enabled` за `factory3d.base.environment` (крок 1а).
3. AC-25 кількості; відкрити меню «Завод 3D → Емулятор» → 7 пунктів (у «Обслуговуванні» пункту «Емулятор» немає; налаштування — «Завод 3D → Налаштування → Налаштування емулятора»); «Рівень 0» — під ним успадковані (AC-59).
4. Підняти compose (`--profile dev`), заповнити Налаштування, «Перевірити зв'язок» → онлайн; переконатися, що крон рівня 0 вимкнувся (≤ 1 хв).
5. ТК-15 повністю; ТК-13 стоп-крани.
6. `neutralize.sql` на другій копії → ТБ-10.
7. Відкат: `-u` назад не підтримується Odoo — відновити копію з п. 1; перевірити, що x_-дані не змінилися (порівняти `x_value` 196 записів — очікувано відрізняються лише ті, що оновив крон рівня 0 за час тесту).
8. Записати результати в `docs/modules/factory3d_iot_sim/TEST_REPORT.md` (ТК/ТБ/ТП таблиця зелене/червоне, версії образів, хеш каталогу).

---

## 14. Definition of Done

- Усі AC-01…AC-65 мають зелену перевірку (UT у CI; TC/MAN — у `TEST_REPORT.md`); ТБ-01…ТБ-10 і ТП-01…ТП-07 пройдені.
- `pytest` сервісу: ≥ 90 % покриття `iot_sim/core` і `iot_sim/models`; `ruff`/`mypy --strict` без помилок; Odoo-тести з тегом `f3d` зелені; `pre-commit` (ruff, isort, xml lint) проходить.
- Каталог сигналів: три копії CSV + API-01 мають один хеш (ТБ-05); Додаток A SPEC = `signals.csv` (скрипт `tools/gen_catalog.py --check`).
- `docker compose --profile demo up` з чистого стану стартує за ≤ 60 с, `health=ok`; образ без root, read-only.
- `neutralize.sql` перевірено на копії; токени не в репозиторії (`.env.example` без значень); `SecretFilter` перевірено (ТБ-06).
- `CHANGELOG.md` модуля і сервісу (19.0.2.0.0 / 0.1.0); README сервісу; інструкції §4 ARCHITECTURE звірено з UI.
- Перегляд безпеки (чек-лист §2.6 ARCHITECTURE) підписаний менеджером; відкриті Q-xx мають рішення або залишаються з позначкою «припущення в силі».
- Відхилення від `docs/ARCHITECTURE.md` (A-01…A-12) погоджені менеджером або повернуті до каркаса.

---

## 15. Відкриті питання

Номери збігаються з `ARCHITECTURE.md` §5.1: **Q-01** OPC UA/JobManagement на верстатах HOMAG; **Q-02** woodStore API; **Q-03** Cerberus PRO — ключ S2 і склад BACnet-об'єктів (типи вже за BTL-лістингом: LSZ/LSP/BV/MSV/PIV — X-37; відкрито: PICS приладу і запиленість, CONSISTENCY «Питання до замовника» № 10); **Q-04** Hoval RoofVent — BACnet напряму чи Modbus-шлюз; **Q-05** карта Elektronikon Mk5; **Q-06** точки TEDOM; ~~**Q-07** таблиця ATyS p~~ — **закрито** X-41 / D-21: карта — Socomec 542 001 D, Annexe III (§8.9.4); звірка з прошивкою ATyS p 1600 — CONSISTENCY «Питання до замовника» № 2; **Q-08** протокол індикатора автоваг; ~~**Q-09** приймач LPR у колекторі~~ — **закрито** X-53: приймач `http_push` telemetry `POST /f3d/<route>[/<secret>]` (`/f3d/lpr`), у фазі 1 — `/sim/v1/lpr-sink`; **Q-10** телематичний шлюз техніки; **Q-11** друга зміна/графік КПП; **Q-12** IP/unit id лічильників у проді; **Q-13** BioStar: картка/обличчя, `tna_key` (коди емулятора уніфіковано — 4102/4867 за Device SDK, чергування `det % 2`, X-50; питання до замовника № 18 лишається); **Q-14** рівень 0 паралельно з сервісом (відповідь — ні, FR-28); ~~**Q-15** команди `fake_relay.py` для `blackout`~~ — **закрито** X-59: REST `fake_relay` API-F-01…F-09 (td_genset §8.4) і контракт CI-01 (§8.14, S-03, S-14, R-22); запасний режим без ретранслятора — §8.14. Для кожного відкритого — рекомендована відповідь і тимчасове рішення в ARCHITECTURE §5.1; у коді всі місця з припущеннями позначені `# ASSUMPTION Q-xx`.

**Закрито 14.10 відповідями замовника** (CONSISTENCY, «Відповіді на питання до замовника»): Q-01 (№ 6), Q-02 (№ 6), Q-03 (№ 10), Q-04 (№ 13), Q-05 (№ 8), Q-06 (№ 3), Q-08 (№ 17), Q-10 (№ 9), Q-11 (№ 14), Q-12 (№ 15), Q-13 (№ 18) — рішення в `ARCHITECTURE.md` §5. Рішенням менеджера закрито Q-14 (ні — взаємовиключення FR-28, D-13).

---

## Додаток A. Каталог сигналів

Джерело істини для `f3d.sim.signal` (Odoo), `services/iot_sim/catalog/signals.csv` і для `factory3d_telemetry M-02 f3d.signal` (міграція у фазі 2). Згенеровано `tools/gen_catalog.py` з `plant/odoo_flows.py:signal_specs` (рядки «макет», 196, значення «Номінал (старт)» = `x_value`/`x_nominal` демо-бази на 13.10.2026) і правил §5.2/§8 (рядки «новий» № 197…662 і 1 167–1 168, 468); рядки № 663…1 166 (504) — з додатків модулів-власників (X-34, X-61, X-76; джерело істини для цих рядків — додаток модуля): № 663–680 — споживачі unit 51…59 (energy Додаток C), 681–688 — fire_safety Додаток B, 689–698 — yard Додаток A, 699–807 — energy Додаток C, 808–873 — machine_connect Додаток C.2, 874–1 165 — bms Додаток B, 1 166 — machine_connect Додаток C.2 `cut_cmd` (`equipment/CUTOPT/cmd`, X-18, X-76; доданий у кінець, щоб не перенумеровувати), 1 167–1 168 — власні рядки P-09: стани зон `FA-SOC` (LSZ:34) і `FA-OFFICE` (LSZ:35), групи макета за відповіддю № 12г (дописані в кінець, щоб не перенумеровувати; fire_safety Додаток B № 53–54). Номери 1…662 не змінено (на них посилаються fire, yard, energy, telemetry); рядки 644, 646, 654, 656 звужено до одного входу, решта входів — нові рядки 684–698; рядок 334 `equipment/GANTRY-1/stacks` переведено в `protocol=none` — його обчислює machine_connect, сирі дані стосів — лише через woodStore REST (X-76). Колонки: код-шлях (= `x_code` макета / шлях у даних переглядача §6.7 каркаса) | пристрій (код сцени; для лічильників споживачів фактичний пристрій емулятора — `<код>-PM`) | протокол P-xx (`—` = `protocol='none'`: величину обчислює модуль-власник або це команда модуля-власника, емулятор її не веде — X-35, X-76) | адреса в джерелі (Modbus — **PDU-форма** `Modbus u<unit> fc<n> pdu<addr>[+<count>] <type>[ little]` за документом вендора (§8.4.1; telemetry R-24 шаблон (0), Q-04; X-42, X-72), після `·` — номер і назва за документом вендора; OPC UA NodeId `ns=2;s=…`; BACnet `dev <instance> <тип>:<instance>`; MQTT топік і JSON-шлях; REST шлях і JSON-шлях; HelvarNet команда; для `—` — «обчислює <модуль> (<правило>) — без адреси») | тип | одиниця | масштаб (множник для переглядача/споживача; `R-20` — за формулою ADAM; відсоткові сигнали — ×1, частка лише в payload, X-39) | номінал (старт; у дужках `шум`/`швидкість` макета) | пороги (`>`/`<` поріг → `alarm`; «межа» — `x_limit`) | модель поведінки (R-xx або «обчислює <модуль>») | статус (макет/новий).

Зведення: усього **1 168** сигналів, з них емулятор веде **1 017**, ведуть модулі-власники **151** (`protocol` «—»: energy 55 — `kwh_shift` ×49, `pv_now`, `grid_kw`, `export_kw`, `src1_ok`, `src2_ok`, `fail_start`; machine_connect 37 — `machine_state` ×35, `equipment/GANTRY-1/stacks` (обчислює), `equipment/CUTOPT/cmd` (команда rest_vendor) — X-76; bms 59 — `check`); за протоколами — P-01: 105, P-02: 60, P-03: 5, P-05: 172, P-06: 40, P-07: 62, P-08: 492 (BACnet 329 + HelvarNet 163), P-09: 55, P-10: 7, P-11: 18, P-12: 1, «—»: 151; макет — 196 (`noise` 73, `energy` 40, `machine` 35, `drift` 28, `hours` 9, `drain` 8, `counter` 1, `level` 1, `solar` 1; з них 41 — обчислювані energy: `kwh_shift` ×40 і `pv_now`), нові — 972 (для `machine_connect` 205, `energy` 190, `telemetry` 29, `bms` 468, `fire_safety` 54, `access` 7, `yard` 18, `td_genset` 1 — за колонкою P-xx і споживачем матриці §6.6).

LSP-рядки (X-79): сигнали окремих адресних пристроїв панелі FACP-1 — `fire/devices/<address>/state` (LSP:<id>) і, для сповіщувачів, `fire/devices/<address>/dust` (PIV:<id>) — у каталог не входять: їх створює `factory3d_fire_safety` (M-04 `action_create_signals`) з `lsp_instance` за правилом fire R-23 (A-09); емулятор віддає ці 302 об'єкти LSP (222 сповіщувачі, 36 ручних, 41 оповіщувач, 3 полум'я) з тими самими id — §8.11.1. У каталозі LSP id згадано лише в рядку 189 (`2.FAC.07` → PIV:21607 = LSP:21607).

| № | Код-шлях (`f3d.signal.code`) | Пристрій (код сцени) | P-xx | Адреса в джерелі | Тип | Одиниця | Масштаб | Номінал (старт) | Пороги | Модель поведінки | Статус |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `energy/consumers/SAW-1/p_now` | SAW-1 | P-05 | Modbus u11 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 12.18 (шум 0.08, швидк. 1.92/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 2 | `energy/consumers/SAW-1/kwh_shift` | SAW-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 50.5 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 3 | `energy/consumers/SAW-2/p_now` | SAW-2 | P-05 | Modbus u12 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 11.69 (шум 0.08, швидк. 1.92/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 4 | `energy/consumers/SAW-2/kwh_shift` | SAW-2 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 48.7 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 5 | `energy/consumers/SAW-3/p_now` | SAW-3 | P-05 | Modbus u13 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 24.8 (шум 0.08, швидк. 3.6/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 6 | `energy/consumers/SAW-3/kwh_shift` | SAW-3 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 58.8 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 7 | `energy/consumers/SLIDE-1/p_now` | SLIDE-1 | P-05 | Modbus u14 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 3.58 (шум 0.08, швидк. 0.6/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 8 | `energy/consumers/SLIDE-1/kwh_shift` | SLIDE-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 12.55 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 9 | `energy/consumers/VSAW-1/p_now` | VSAW-1 | P-05 | Modbus u15 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 4.0 (шум 0.08, швидк. 0.58/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 10 | `energy/consumers/VSAW-1/kwh_shift` | VSAW-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 6.46 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 11 | `energy/consumers/NEST-1/p_now` | NEST-1 | P-05 | Modbus u16 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 21.4 (шум 0.08, швидк. 3.12/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 12 | `energy/consumers/NEST-1/kwh_shift` | NEST-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 86.2 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 13 | `energy/consumers/EDGE-1/p_now` | EDGE-1 | P-05 | Modbus u17 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 41.6 (шум 0.08, швидк. 5.4/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 14 | `energy/consumers/EDGE-1/kwh_shift` | EDGE-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 170.2 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 15 | `energy/consumers/EDGE-2/p_now` | EDGE-2 | P-05 | Modbus u18 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 17.35 (шум 0.08, швидк. 2.24/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 16 | `energy/consumers/EDGE-2/kwh_shift` | EDGE-2 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 70.0 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 17 | `energy/consumers/EDGE-3/p_now` | EDGE-3 | P-05 | Modbus u19 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 15.4 (шум 0.08, швидк. 2.24/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 18 | `energy/consumers/EDGE-3/kwh_shift` | EDGE-3 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 48.2 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 19 | `energy/consumers/CNC-3/p_now` | CNC-3 | P-05 | Modbus u20 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 12.25 (шум 0.08, швидк. 1.76/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 20 | `energy/consumers/CNC-3/kwh_shift` | CNC-3 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 44.6 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 21 | `energy/consumers/CNC-1/p_now` | CNC-1 | P-05 | Modbus u21 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 10.58 (шум 0.08, швидк. 1.76/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 22 | `energy/consumers/CNC-1/kwh_shift` | CNC-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 44.4 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 23 | `energy/consumers/CNC-2/p_now` | CNC-2 | P-05 | Modbus u22 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 12.1 (шум 0.08, швидк. 1.76/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 24 | `energy/consumers/CNC-2/kwh_shift` | CNC-2 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 18.3 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 25 | `energy/consumers/BORE-1/p_now` | BORE-1 | P-05 | Modbus u23 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 8.56 (шум 0.08, швидк. 1.56/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 26 | `energy/consumers/BORE-1/kwh_shift` | BORE-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 36.4 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 27 | `energy/consumers/CNC-4/p_now` | CNC-4 | P-05 | Modbus u24 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 10.21 (шум 0.08, швидк. 1.76/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 28 | `energy/consumers/CNC-4/kwh_shift` | CNC-4 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 43.0 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 29 | `energy/consumers/DOWEL-1/p_now` | DOWEL-1 | P-05 | Modbus u25 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 5.27 (шум 0.08, швидк. 0.88/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 30 | `energy/consumers/DOWEL-1/kwh_shift` | DOWEL-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 18.25 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 31 | `energy/consumers/SORT-1/p_now` | SORT-1 | P-05 | Modbus u26 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 9.02 (шум 0.08, швидк. 1.6/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 32 | `energy/consumers/SORT-1/kwh_shift` | SORT-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 35.3 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 33 | `energy/consumers/SAND-1/p_now` | SAND-1 | P-05 | Modbus u27 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 19.13 (шум 0.08, швидк. 2.4/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 34 | `energy/consumers/SAND-1/kwh_shift` | SAND-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 76.8 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 35 | `energy/consumers/AUTOSPRAY-1/p_now` | AUTOSPRAY-1 | P-05 | Modbus u28 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 10.64 (шум 0.08, швидк. 1.44/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 36 | `energy/consumers/AUTOSPRAY-1/kwh_shift` | AUTOSPRAY-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 41.0 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 37 | `energy/consumers/UV-1/p_now` | UV-1 | P-05 | Modbus u29 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 32.4 (шум 0.08, швидк. 4.71/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 38 | `energy/consumers/UV-1/kwh_shift` | UV-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 76.2 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 39 | `energy/consumers/HINGE-1/p_now` | HINGE-1 | P-05 | Modbus u30 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.28 (шум 0.08, швидк. 0.09/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 40 | `energy/consumers/HINGE-1/kwh_shift` | HINGE-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 1.33 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 41 | `energy/consumers/GLUE-1/p_now` | GLUE-1 | P-05 | Modbus u31 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 1.64 (шум 0.08, швидк. 0.18/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 42 | `energy/consumers/GLUE-1/kwh_shift` | GLUE-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 6.16 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 43 | `energy/consumers/PRESS-1/p_now` | PRESS-1 | P-05 | Modbus u32 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 18.45 (шум 0.08, швидк. 2.24/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 44 | `energy/consumers/PRESS-1/kwh_shift` | PRESS-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 68.9 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 45 | `energy/consumers/SPRAY-1/p_now` | SPRAY-1 | P-05 | Modbus u33 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 3.49 (шум 0.08, швидк. 0.41/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 46 | `energy/consumers/SPRAY-1/kwh_shift` | SPRAY-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 13.98 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 47 | `energy/consumers/DRY-1/p_now` | DRY-1 | P-05 | Modbus u34 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 13.04 (шум 0.08, швидк. 1.36/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 48 | `energy/consumers/DRY-1/kwh_shift` | DRY-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 53.4 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 49 | `energy/consumers/ASMLINE-1/p_now` | ASMLINE-1 | P-05 | Modbus u35 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 3.4 (шум 0.08, швидк. 0.64/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 50 | `energy/consumers/ASMLINE-1/kwh_shift` | ASMLINE-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 12.86 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 51 | `energy/consumers/ASM-1/p_now` | ASM-1 | P-05 | Modbus u36 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.52 (шум 0.08, швидк. 0.12/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 52 | `energy/consumers/ASM-1/kwh_shift` | ASM-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 2.09 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 53 | `energy/consumers/ASM-2/p_now` | ASM-2 | P-05 | Modbus u37 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.61 (шум 0.08, швидк. 0.12/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 54 | `energy/consumers/ASM-2/kwh_shift` | ASM-2 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 2.18 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 55 | `energy/consumers/ASM-3/p_now` | ASM-3 | P-05 | Modbus u38 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.49 (шум 0.08, швидк. 0.12/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 56 | `energy/consumers/ASM-3/kwh_shift` | ASM-3 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 1.9 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 57 | `energy/consumers/ASM-4/p_now` | ASM-4 | P-05 | Modbus u39 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.51 (шум 0.08, швидк. 0.12/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 58 | `energy/consumers/ASM-4/kwh_shift` | ASM-4 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 1.89 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 59 | `energy/consumers/ASM-5/p_now` | ASM-5 | P-05 | Modbus u40 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.8 (шум 0.08, швидк. 0.12/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 60 | `energy/consumers/ASM-5/kwh_shift` | ASM-5 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 1.39 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 61 | `energy/consumers/ASM-6/p_now` | ASM-6 | P-05 | Modbus u41 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.57 (шум 0.08, швидк. 0.12/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 62 | `energy/consumers/ASM-6/kwh_shift` | ASM-6 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 2.07 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 63 | `energy/consumers/PACK-1/p_now` | PACK-1 | P-05 | Modbus u42 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.66 (шум 0.08, швидк. 0.15/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 64 | `energy/consumers/PACK-1/kwh_shift` | PACK-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 2.95 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 65 | `energy/consumers/PACK-2/p_now` | PACK-2 | P-05 | Modbus u43 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.75 (шум 0.08, швидк. 0.15/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 66 | `energy/consumers/PACK-2/kwh_shift` | PACK-2 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 3.02 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 67 | `energy/consumers/BOX-1/p_now` | BOX-1 | P-05 | Modbus u44 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 5.36 (шум 0.08, швидк. 0.8/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 68 | `energy/consumers/BOX-1/kwh_shift` | BOX-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 18.34 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 69 | `energy/consumers/PACKLINE-1/p_now` | PACKLINE-1 | P-05 | Modbus u45 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 13.71 (шум 0.08, швидк. 1.59/хв) | — | machine (R-02 потужність верстата за станом РЦ) | макет |
| 70 | `energy/consumers/PACKLINE-1/kwh_shift` | PACKLINE-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 49.1 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 71 | `energy/consumers/GANTRY-1/p_now` | GANTRY-1 | P-05 | Modbus u46 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 4.94 (шум 0.2) | — | noise (R-01) | макет |
| 72 | `energy/consumers/GANTRY-1/kwh_shift` | GANTRY-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 22.3 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 73 | `energy/consumers/COMPRESSOR/p_now` | COMPRESSOR | P-05 | Modbus u47 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 50.2 (шум 2.01) | — | noise (R-01) | макет |
| 74 | `energy/consumers/COMPRESSOR/kwh_shift` | COMPRESSOR | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 198.7 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 75 | `energy/consumers/DUST-1/p_now` | DUST-1 | P-05 | Modbus u48 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 134.6 (шум 5.38) | — | noise (R-01) | макет |
| 76 | `energy/consumers/DUST-1/kwh_shift` | DUST-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 544.4 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 77 | `energy/consumers/BOILER/p_now` | BOILER | P-05 | Modbus u49 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 10.35 (шум 0.41) | — | noise (R-01) | макет |
| 78 | `energy/consumers/BOILER/kwh_shift` | BOILER | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 42.7 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 79 | `energy/consumers/CHARGING/p_now` | CHARGING | P-05 | Modbus u50 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 9.63 (шум 0.39) | — | noise (R-01) | макет |
| 80 | `energy/consumers/CHARGING/kwh_shift` | CHARGING | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 38.4 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | макет |
| 81 | `equipment/FL-1/battery` | FL-1 | P-06 | MQTT f3d/mobile/FL-1/telemetry → $.battery_pct | number | % | ×1 | 57.1 (швидк. 0.15/хв) | межа 20 | drain (R-05 розряд/зарядка) | макет |
| 82 | `equipment/FL-1/hours` | FL-1 | P-06 | MQTT f3d/mobile/FL-1/telemetry → $.hours | number | год | ×1 | 2069.8 | — | hours (R-06 мотогодини) | макет |
| 83 | `equipment/FL-2/battery` | FL-2 | P-06 | MQTT f3d/mobile/FL-2/telemetry → $.battery_pct | number | % | ×1 | 33.9 (швидк. 0.15/хв) | межа 20 | drain (R-05 розряд/зарядка) | макет |
| 84 | `equipment/FL-2/hours` | FL-2 | P-06 | MQTT f3d/mobile/FL-2/telemetry → $.hours | number | год | ×1 | 3212.8 | — | hours (R-06 мотогодини) | макет |
| 85 | `equipment/FL-3/battery` | FL-3 | P-06 | MQTT f3d/mobile/FL-3/telemetry → $.battery_pct | number | % | ×1 | 71.3 (швидк. 0.15/хв) | межа 20 | drain (R-05 розряд/зарядка) | макет |
| 86 | `equipment/FL-3/hours` | FL-3 | P-06 | MQTT f3d/mobile/FL-3/telemetry → $.hours | number | год | ×1 | 1831.8 | — | hours (R-06 мотогодини) | макет |
| 87 | `equipment/FL-4/battery` | FL-4 | P-06 | MQTT f3d/mobile/FL-4/telemetry → $.battery_pct | number | % | ×1 | 45.1 (швидк. 0.15/хв) | межа 20 | drain (R-05 розряд/зарядка) | макет |
| 88 | `equipment/FL-4/hours` | FL-4 | P-06 | MQTT f3d/mobile/FL-4/telemetry → $.hours | number | год | ×1 | 2974.8 | — | hours (R-06 мотогодини) | макет |
| 89 | `equipment/FL-5/battery` | FL-5 | P-06 | MQTT f3d/mobile/FL-5/telemetry → $.battery_pct | number | % | ×1 | 81.0 (швидк. 0.15/хв) | межа 20 | drain (R-05 розряд/зарядка) | макет |
| 90 | `equipment/FL-5/hours` | FL-5 | P-06 | MQTT f3d/mobile/FL-5/telemetry → $.hours | number | год | ×1 | 4593.8 | — | hours (R-06 мотогодини) | макет |
| 91 | `equipment/FL-C1/battery` | FL-C1 | P-06 | MQTT f3d/mobile/FL-C1/telemetry → $.battery_pct | number | % | ×1 | 50.6 (швидк. 0.15/хв) | межа 20 | drain (R-05 розряд/зарядка) | макет |
| 92 | `equipment/FL-C1/hours` | FL-C1 | P-06 | MQTT f3d/mobile/FL-C1/telemetry → $.hours | number | год | ×1 | 2306.0 | — | hours (R-06 мотогодини) | макет |
| 93 | `equipment/FL-C2/battery` | FL-C2 | P-06 | MQTT f3d/mobile/FL-C2/telemetry → $.battery_pct | number | % | ×1 | 84.6 (швидк. 0.15/хв) | межа 20 | drain (R-05 розряд/зарядка) | макет |
| 94 | `equipment/FL-C2/hours` | FL-C2 | P-06 | MQTT f3d/mobile/FL-C2/telemetry → $.hours | number | год | ×1 | 3687.0 | — | hours (R-06 мотогодини) | макет |
| 95 | `equipment/TUGGER-1/battery` | TUGGER-1 | P-06 | MQTT f3d/mobile/TUGGER-1/telemetry → $.battery_pct | number | % | ×1 | 63.8 (швидк. 0.15/хв) | межа 20 | drain (R-05 розряд/зарядка) | макет |
| 96 | `equipment/TUGGER-1/hours` | TUGGER-1 | P-06 | MQTT f3d/mobile/TUGGER-1/telemetry → $.hours | number | год | ×1 | 920.8 | — | hours (R-06 мотогодини) | макет |
| 97 | `equipment/GANTRY-1/cycles_today` | GANTRY-1 | P-03 | GET /api/v1/status → $.cycles_today (+ OPC UA ns=2;s=GANTRY-1.State.Machine.Values.RelativeRunsTotal) | U64 | шт | ×1 | 373.0 (швидк. 3/хв) | — | counter (R-07 цикли порталу) | макет |
| 98 | `equipment/GANTRY-1/vacuum_kpa` | GANTRY-1 | P-03 | GET /api/v1/status → $.vacuum_kpa | number | кПа | ×1 | -71.9 (шум 0.5) | > -60 | noise (R-01) | макет |
| 99 | `equipment/COMPRESSOR/pressure_bar` | COMPRESSOR | P-07 | Modbus u70 fc3 pdu3001 u16 · Elektronikon Mk5 3002 Outlet pressure (ПРИПУЩЕННЯ) | U16 | бар | ×0,001 | 6.81 (шум 0.05) | < 6.0 | noise (R-08 тиск/завантаження) | макет |
| 100 | `equipment/COMPRESSOR/load` | COMPRESSOR | P-07 | Modbus u70 fc3 pdu3009 u16 · Elektronikon Mk5 3010 Load % (ПРИПУЩЕННЯ) | U16 | % | ×1 | 64 (шум 3) | — | noise (R-08) | макет |
| 101 | `equipment/COMPRESSOR/hours` | COMPRESSOR | P-07 | Modbus u70 fc3 pdu3019+2 u32 · Elektronikon Mk5 3020–3021 Running hours (ПРИПУЩЕННЯ) | U32 | год | ×1 | 17840.8 | — | hours (R-06) | макет |
| 102 | `equipment/DUST-1/airflow_m3h` | DUST-1 | P-07 | Modbus u90 fc3 pdu0 u16 · ADAM-6017 40001 AI0, 4–20 мА = 0…32 000 м³/год | U16 | м³/год | R-20 | 29767.6 (шум 300) | — | noise (R-01) | макет |
| 103 | `equipment/DUST-1/filter_dp_kpa` | DUST-1 | P-07 | Modbus u90 fc3 pdu1 u16 · ADAM-6017 40002 AI1, 4–20 мА = 0…4 кПа | U16 | кПа | R-20 | 1.0 (швидк. 0.0005/хв) | > 1.8 | drift (R-09 фільтр забивається) | макет |
| 104 | `equipment/BOILER/supply_c` | BOILER | P-08 | BACnet dev 140 AI:1 Present_Value (подача) | REAL | °C | ×1 | 77.4 (шум 0.4) | — | noise (R-01) | макет |
| 105 | `equipment/BOILER/silo_fill` | BOILER | P-08 | BACnet dev 140 AI:3 Present_Value (рівень бункера) | REAL | % | ×1 | 95 (швидк. 0.02/хв) | межа 15 | level (R-10 бункер) | макет |
| 106 | `equipment/SPRINKLERS/pressure_bar` | SPRINKLERS | P-07 | Modbus u90 fc3 pdu2 u16 · ADAM-6017 40003 AI2, 4–20 мА = 0…16 бар | U16 | бар | R-20 | 7.15 (шум 0.04) | < 6.5 | noise (R-01) | макет |
| 107 | `equipment/AIR-RING/pressure_bar` | AIR-RING | P-07 | Modbus u90 fc3 pdu3 u16 · ADAM-6017 40004 AI3, 4–20 мА = 0…16 бар | U16 | бар | R-20 | 6.37 (шум 0.04) | < 6.0 | noise (R-01) | макет |
| 108 | `ventilation/units/RV-01/airflow_m3h` | RV-01 | P-08 | BACnet dev 101 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5467.5 (шум 109) | — | noise (R-01) | макет |
| 109 | `ventilation/units/RV-01/supply_c` | RV-01 | P-08 | BACnet dev 101 AI:1 (подача) Present_Value | REAL | °C | ×1 | 19.53 (шум 0.2) | — | noise (R-01) | макет |
| 110 | `ventilation/units/RV-01/filter_dp_pa` | RV-01 | P-08 | BACnet dev 101 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 111 | `ventilation/units/RV-02/airflow_m3h` | RV-02 | P-08 | BACnet dev 102 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5387.4 (шум 108) | — | noise (R-01) | макет |
| 112 | `ventilation/units/RV-02/supply_c` | RV-02 | P-08 | BACnet dev 102 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.1 (шум 0.2) | — | noise (R-01) | макет |
| 113 | `ventilation/units/RV-02/filter_dp_pa` | RV-02 | P-08 | BACnet dev 102 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 114 | `ventilation/units/RV-03/airflow_m3h` | RV-03 | P-08 | BACnet dev 103 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5205.5 (шум 104) | — | noise (R-01) | макет |
| 115 | `ventilation/units/RV-03/supply_c` | RV-03 | P-08 | BACnet dev 103 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.1 (шум 0.2) | — | noise (R-01) | макет |
| 116 | `ventilation/units/RV-03/filter_dp_pa` | RV-03 | P-08 | BACnet dev 103 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 117 | `ventilation/units/RV-04/airflow_m3h` | RV-04 | P-08 | BACnet dev 104 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5878.7 (шум 118) | — | noise (R-01) | макет |
| 118 | `ventilation/units/RV-04/supply_c` | RV-04 | P-08 | BACnet dev 104 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.8 (шум 0.2) | — | noise (R-01) | макет |
| 119 | `ventilation/units/RV-04/filter_dp_pa` | RV-04 | P-08 | BACnet dev 104 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 120 | `ventilation/units/RV-05/airflow_m3h` | RV-05 | P-08 | BACnet dev 105 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5912.6 (шум 118) | — | noise (R-01) | макет |
| 121 | `ventilation/units/RV-05/supply_c` | RV-05 | P-08 | BACnet dev 105 AI:1 (подача) Present_Value | REAL | °C | ×1 | 19.32 (шум 0.2) | — | noise (R-01) | макет |
| 122 | `ventilation/units/RV-05/filter_dp_pa` | RV-05 | P-08 | BACnet dev 105 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 123 | `ventilation/units/RV-06/airflow_m3h` | RV-06 | P-08 | BACnet dev 106 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5713.8 (шум 114) | — | noise (R-01) | макет |
| 124 | `ventilation/units/RV-06/supply_c` | RV-06 | P-08 | BACnet dev 106 AI:1 (подача) Present_Value | REAL | °C | ×1 | 19.82 (шум 0.2) | — | noise (R-01) | макет |
| 125 | `ventilation/units/RV-06/filter_dp_pa` | RV-06 | P-08 | BACnet dev 106 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 126 | `ventilation/units/RV-07/airflow_m3h` | RV-07 | P-08 | BACnet dev 107 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5407.6 (шум 108) | — | noise (R-01) | макет |
| 127 | `ventilation/units/RV-07/supply_c` | RV-07 | P-08 | BACnet dev 107 AI:1 (подача) Present_Value | REAL | °C | ×1 | 19.85 (шум 0.2) | — | noise (R-01) | макет |
| 128 | `ventilation/units/RV-07/filter_dp_pa` | RV-07 | P-08 | BACnet dev 107 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 129 | `ventilation/units/RV-08/airflow_m3h` | RV-08 | P-08 | BACnet dev 108 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 6047.7 (шум 121) | — | noise (R-01) | макет |
| 130 | `ventilation/units/RV-08/supply_c` | RV-08 | P-08 | BACnet dev 108 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.4 (шум 0.2) | — | noise (R-01) | макет |
| 131 | `ventilation/units/RV-08/filter_dp_pa` | RV-08 | P-08 | BACnet dev 108 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 132 | `ventilation/units/RV-09/airflow_m3h` | RV-09 | P-08 | BACnet dev 109 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 6000.0 (шум 120) | — | noise (R-01) | макет |
| 133 | `ventilation/units/RV-09/supply_c` | RV-09 | P-08 | BACnet dev 109 AI:1 (подача) Present_Value | REAL | °C | ×1 | 19.78 (шум 0.2) | — | noise (R-01) | макет |
| 134 | `ventilation/units/RV-09/filter_dp_pa` | RV-09 | P-08 | BACnet dev 109 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 135 | `ventilation/units/RV-10/airflow_m3h` | RV-10 | P-08 | BACnet dev 110 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 6575.6 (шум 132) | — | noise (R-01) | макет |
| 136 | `ventilation/units/RV-10/supply_c` | RV-10 | P-08 | BACnet dev 110 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.2 (шум 0.2) | — | noise (R-01) | макет |
| 137 | `ventilation/units/RV-10/filter_dp_pa` | RV-10 | P-08 | BACnet dev 110 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 138 | `ventilation/units/RV-11/airflow_m3h` | RV-11 | P-08 | BACnet dev 111 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5575.6 (шум 112) | — | noise (R-01) | макет |
| 139 | `ventilation/units/RV-11/supply_c` | RV-11 | P-08 | BACnet dev 111 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.5 (шум 0.2) | — | noise (R-01) | макет |
| 140 | `ventilation/units/RV-11/filter_dp_pa` | RV-11 | P-08 | BACnet dev 111 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 141 | `ventilation/units/RV-12/airflow_m3h` | RV-12 | P-08 | BACnet dev 112 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5667.1 (шум 113) | — | noise (R-01) | макет |
| 142 | `ventilation/units/RV-12/supply_c` | RV-12 | P-08 | BACnet dev 112 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.9 (шум 0.2) | — | noise (R-01) | макет |
| 143 | `ventilation/units/RV-12/filter_dp_pa` | RV-12 | P-08 | BACnet dev 112 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 144 | `ventilation/units/RV-13/airflow_m3h` | RV-13 | P-08 | BACnet dev 113 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5601.5 (шум 112) | — | noise (R-01) | макет |
| 145 | `ventilation/units/RV-13/supply_c` | RV-13 | P-08 | BACnet dev 113 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.5 (шум 0.2) | — | noise (R-01) | макет |
| 146 | `ventilation/units/RV-13/filter_dp_pa` | RV-13 | P-08 | BACnet dev 113 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 147 | `ventilation/units/RV-14/airflow_m3h` | RV-14 | P-08 | BACnet dev 114 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5615.6 (шум 112) | — | noise (R-01) | макет |
| 148 | `ventilation/units/RV-14/supply_c` | RV-14 | P-08 | BACnet dev 114 AI:1 (подача) Present_Value | REAL | °C | ×1 | 19.69 (шум 0.2) | — | noise (R-01) | макет |
| 149 | `ventilation/units/RV-14/filter_dp_pa` | RV-14 | P-08 | BACnet dev 114 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 150 | `ventilation/units/RV-15/airflow_m3h` | RV-15 | P-08 | BACnet dev 115 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5768.3 (шум 115) | — | noise (R-01) | макет |
| 151 | `ventilation/units/RV-15/supply_c` | RV-15 | P-08 | BACnet dev 115 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.7 (шум 0.2) | — | noise (R-01) | макет |
| 152 | `ventilation/units/RV-15/filter_dp_pa` | RV-15 | P-08 | BACnet dev 115 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 153 | `ventilation/units/RV-16/airflow_m3h` | RV-16 | P-08 | BACnet dev 116 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5879.3 (шум 118) | — | noise (R-01) | макет |
| 154 | `ventilation/units/RV-16/supply_c` | RV-16 | P-08 | BACnet dev 116 AI:1 (подача) Present_Value | REAL | °C | ×1 | 19.92 (шум 0.2) | — | noise (R-01) | макет |
| 155 | `ventilation/units/RV-16/filter_dp_pa` | RV-16 | P-08 | BACnet dev 116 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 156 | `ventilation/units/RV-17/airflow_m3h` | RV-17 | P-08 | BACnet dev 117 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5943.6 (шум 119) | — | noise (R-01) | макет |
| 157 | `ventilation/units/RV-17/supply_c` | RV-17 | P-08 | BACnet dev 117 AI:1 (подача) Present_Value | REAL | °C | ×1 | 21.3 (шум 0.2) | — | noise (R-01) | макет |
| 158 | `ventilation/units/RV-17/filter_dp_pa` | RV-17 | P-08 | BACnet dev 117 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 159 | `ventilation/units/RV-18/airflow_m3h` | RV-18 | P-08 | BACnet dev 118 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5947.3 (шум 119) | — | noise (R-01) | макет |
| 160 | `ventilation/units/RV-18/supply_c` | RV-18 | P-08 | BACnet dev 118 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.6 (шум 0.2) | — | noise (R-01) | макет |
| 161 | `ventilation/units/RV-18/filter_dp_pa` | RV-18 | P-08 | BACnet dev 118 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 162 | `ventilation/units/RV-19/airflow_m3h` | RV-19 | P-08 | BACnet dev 119 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 6137.6 (шум 123) | — | noise (R-01) | макет |
| 163 | `ventilation/units/RV-19/supply_c` | RV-19 | P-08 | BACnet dev 119 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.8 (шум 0.2) | — | noise (R-01) | макет |
| 164 | `ventilation/units/RV-19/filter_dp_pa` | RV-19 | P-08 | BACnet dev 119 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 165 | `ventilation/units/RV-20/airflow_m3h` | RV-20 | P-08 | BACnet dev 120 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 6423.0 (шум 128) | — | noise (R-01) | макет |
| 166 | `ventilation/units/RV-20/supply_c` | RV-20 | P-08 | BACnet dev 120 AI:1 (подача) Present_Value | REAL | °C | ×1 | 19.39 (шум 0.2) | — | noise (R-01) | макет |
| 167 | `ventilation/units/RV-20/filter_dp_pa` | RV-20 | P-08 | BACnet dev 120 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 168 | `ventilation/units/RV-21/airflow_m3h` | RV-21 | P-08 | BACnet dev 121 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 3650.6 (шум 73) | — | noise (R-01) | макет |
| 169 | `ventilation/units/RV-21/supply_c` | RV-21 | P-08 | BACnet dev 121 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.6 (шум 0.2) | — | noise (R-01) | макет |
| 170 | `ventilation/units/RV-21/filter_dp_pa` | RV-21 | P-08 | BACnet dev 121 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 171 | `ventilation/units/RV-22/airflow_m3h` | RV-22 | P-08 | BACnet dev 122 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 3601.1 (шум 72) | — | noise (R-01) | макет |
| 172 | `ventilation/units/RV-22/supply_c` | RV-22 | P-08 | BACnet dev 122 AI:1 (подача) Present_Value | REAL | °C | ×1 | 19.8 (шум 0.2) | — | noise (R-01) | макет |
| 173 | `ventilation/units/RV-22/filter_dp_pa` | RV-22 | P-08 | BACnet dev 122 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 174 | `ventilation/units/RV-23/airflow_m3h` | RV-23 | P-08 | BACnet dev 123 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 6393.1 (шум 128) | — | noise (R-01) | макет |
| 175 | `ventilation/units/RV-23/supply_c` | RV-23 | P-08 | BACnet dev 123 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.3 (шум 0.2) | — | noise (R-01) | макет |
| 176 | `ventilation/units/RV-23/filter_dp_pa` | RV-23 | P-08 | BACnet dev 123 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 177 | `ventilation/units/RV-24/airflow_m3h` | RV-24 | P-08 | BACnet dev 124 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 6269.0 (шум 125) | — | noise (R-01) | макет |
| 178 | `ventilation/units/RV-24/supply_c` | RV-24 | P-08 | BACnet dev 124 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.6 (шум 0.2) | — | noise (R-01) | макет |
| 179 | `ventilation/units/RV-24/filter_dp_pa` | RV-24 | P-08 | BACnet dev 124 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 180 | `ventilation/units/RV-25/airflow_m3h` | RV-25 | P-08 | BACnet dev 125 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 5937.4 (шум 119) | — | noise (R-01) | макет |
| 181 | `ventilation/units/RV-25/supply_c` | RV-25 | P-08 | BACnet dev 125 AI:1 (подача) Present_Value | REAL | °C | ×1 | 20.6 (шум 0.2) | — | noise (R-01) | макет |
| 182 | `ventilation/units/RV-25/filter_dp_pa` | RV-25 | P-08 | BACnet dev 125 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 183 | `ventilation/units/AHU-1/airflow_m3h` | AHU-1 | P-08 | BACnet dev 130 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 16959.1 (шум 339) | — | noise (R-01) | макет |
| 184 | `ventilation/units/AHU-1/supply_c` | AHU-1 | P-08 | BACnet dev 130 AI:1 (подача) Present_Value | REAL | °C | ×1 | 21.0 (шум 0.2) | — | noise (R-01) | макет |
| 185 | `ventilation/units/AHU-1/filter_dp_pa` | AHU-1 | P-08 | BACnet dev 130 AI:4 (перепад на фільтрі припливу) Present_Value | REAL | Па | ×1 | 120 (швидк. 0.05/хв) | > 250 | drift (R-09) | макет |
| 186 | `ventilation/units/EF-ELEC/airflow_m3h` | EF-ELEC | P-08 | BACnet dev 131 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 14183.7 (шум 284) | — | noise (R-01) | макет |
| 187 | `ventilation/units/EF-CMP/airflow_m3h` | EF-CMP | P-08 | BACnet dev 132 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 0.0 | — | noise (R-01) | макет |
| 188 | `ventilation/units/EF-CHG/airflow_m3h` | EF-CHG | P-08 | BACnet dev 133 AI:3 (витрата) Present_Value | REAL | м³/год | ×1 | 159.7 (шум 3) | — | noise (R-01) | макет |
| 189 | `fire/groups/FA-FAC/dust` | FA-FAC | P-09 | BACnet dev 200 PIV:21607 Present_Value (запиленість сповіщувача 2.FAC.07 = LSP:21607; ПРИПУЩЕННЯ до PICS приладу, Q-03) | PIV | % | ×1 | 10 (швидк. 0.01/хв) | > 90 | drift (R-09, скидання після закриття заявки) | макет |
| 190 | `energy/transformers/T1/p_kw` | T1 | P-05 | Modbus u1 fc3 pdu3059+2 f32 · PM5560 3060–3061 ввід Q1 | F32 | кВт | ×1 | 333.3 (шум 10.0) | — | noise (R-01) = сума секції | макет |
| 191 | `energy/transformers/T1/temp_c` | T1 | P-07 | Modbus u96 fc3 pdu0+3 u16 max · ADAM-6015 40001–40003 RTD обмотки, макс. | U16 | °C | 0–65535 → −50…+150 °C (R-20) | 59.1 (шум 0.3) | > 140 (energy, відповідь № 24) | noise (R-04 38 + 60·S/Sн) | макет |
| 192 | `energy/transformers/T2/p_kw` | T2 | P-05 | Modbus u2 fc3 pdu3059+2 f32 · PM5560 3060–3061 ввід Q2 | F32 | кВт | ×1 | 296.0 (шум 8.9) | — | noise (R-01) = сума секції | макет |
| 193 | `energy/transformers/T2/temp_c` | T2 | P-07 | Modbus u96 fc3 pdu3+3 u16 max · ADAM-6015 40004–40006 RTD обмотки, макс. | U16 | °C | 0–65535 → −50…+150 °C (R-20) | 55.6 (шум 0.3) | > 140 (energy, відповідь № 24) | noise (R-04 38 + 60·S/Sн) | макет |
| 194 | `infra/totals/pv_now` | PV-INV | — | обчислює energy (R-06 = Σ `infra/pv/PV-INV-k/p_kw`) — без адреси (X-35) | number | кВт | — | 0 | — | обчислює energy (R-11 емулятора — сума інверторів) | макет |
| 195 | `infra/totals/chp_kw` | CHP | P-07 | Modbus u72 fc3 pdu40001 u16 · TEDOM 40001 P ел. (ПРИПУЩЕННЯ) | U16 | кВт | ×1 | 397.3 (шум 4) | — | noise (R-12 КГУ 50 % удень) | макет |
| 196 | `infra/totals/bess_soc` | BESS | P-07 | Modbus u69 fc3 pdu37004 u16 · LUNA2000 37004 SOC | U16 | % | ×0,1 | 76 (шум 0.3) | — | noise (R-13 баланс надлишку) | макет |
| 197 | `workcenters/SAW-1/state` | SAW-1 | P-01 | ns=2;s=SAW-1.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 198 | `workcenters/SAW-1/mode` | SAW-1 | P-01 | ns=2;s=SAW-1.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 199 | `workcenters/SAW-1/alarm` | SAW-1 | P-01 | ns=2;s=SAW-1.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 200 | `workcenters/SAW-1/pieces_out` | SAW-1 | P-01 | ns=2;s=SAW-1.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 201 | `workcenters/SAW-1/job` | SAW-1 | P-01 | ns=2;s=SAW-1.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 202 | `workcenters/SAW-2/state` | SAW-2 | P-01 | ns=2;s=SAW-2.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 203 | `workcenters/SAW-2/mode` | SAW-2 | P-01 | ns=2;s=SAW-2.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 204 | `workcenters/SAW-2/alarm` | SAW-2 | P-01 | ns=2;s=SAW-2.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 205 | `workcenters/SAW-2/pieces_out` | SAW-2 | P-01 | ns=2;s=SAW-2.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 206 | `workcenters/SAW-2/job` | SAW-2 | P-01 | ns=2;s=SAW-2.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 207 | `workcenters/SAW-3/state` | SAW-3 | P-01 | ns=2;s=SAW-3.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 208 | `workcenters/SAW-3/mode` | SAW-3 | P-01 | ns=2;s=SAW-3.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 209 | `workcenters/SAW-3/alarm` | SAW-3 | P-01 | ns=2;s=SAW-3.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 210 | `workcenters/SAW-3/pieces_out` | SAW-3 | P-01 | ns=2;s=SAW-3.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 211 | `workcenters/SAW-3/job` | SAW-3 | P-01 | ns=2;s=SAW-3.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 212 | `workcenters/NEST-1/state` | NEST-1 | P-01 | ns=2;s=NEST-1.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 213 | `workcenters/NEST-1/mode` | NEST-1 | P-01 | ns=2;s=NEST-1.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 214 | `workcenters/NEST-1/alarm` | NEST-1 | P-01 | ns=2;s=NEST-1.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 215 | `workcenters/NEST-1/pieces_out` | NEST-1 | P-01 | ns=2;s=NEST-1.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 216 | `workcenters/NEST-1/job` | NEST-1 | P-01 | ns=2;s=NEST-1.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 217 | `workcenters/EDGE-1/state` | EDGE-1 | P-01 | ns=2;s=EDGE-1.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 218 | `workcenters/EDGE-1/mode` | EDGE-1 | P-01 | ns=2;s=EDGE-1.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 219 | `workcenters/EDGE-1/alarm` | EDGE-1 | P-01 | ns=2;s=EDGE-1.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 220 | `workcenters/EDGE-1/pieces_out` | EDGE-1 | P-01 | ns=2;s=EDGE-1.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 221 | `workcenters/EDGE-1/job` | EDGE-1 | P-01 | ns=2;s=EDGE-1.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 222 | `workcenters/EDGE-2/state` | EDGE-2 | P-01 | ns=2;s=EDGE-2.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 223 | `workcenters/EDGE-2/mode` | EDGE-2 | P-01 | ns=2;s=EDGE-2.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 224 | `workcenters/EDGE-2/alarm` | EDGE-2 | P-01 | ns=2;s=EDGE-2.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 225 | `workcenters/EDGE-2/pieces_out` | EDGE-2 | P-01 | ns=2;s=EDGE-2.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 226 | `workcenters/EDGE-2/job` | EDGE-2 | P-01 | ns=2;s=EDGE-2.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 227 | `workcenters/EDGE-3/state` | EDGE-3 | P-01 | ns=2;s=EDGE-3.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 228 | `workcenters/EDGE-3/mode` | EDGE-3 | P-01 | ns=2;s=EDGE-3.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 229 | `workcenters/EDGE-3/alarm` | EDGE-3 | P-01 | ns=2;s=EDGE-3.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 230 | `workcenters/EDGE-3/pieces_out` | EDGE-3 | P-01 | ns=2;s=EDGE-3.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 231 | `workcenters/EDGE-3/job` | EDGE-3 | P-01 | ns=2;s=EDGE-3.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 232 | `workcenters/CNC-1/state` | CNC-1 | P-01 | ns=2;s=CNC-1.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 233 | `workcenters/CNC-1/mode` | CNC-1 | P-01 | ns=2;s=CNC-1.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 234 | `workcenters/CNC-1/alarm` | CNC-1 | P-01 | ns=2;s=CNC-1.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 235 | `workcenters/CNC-1/pieces_out` | CNC-1 | P-01 | ns=2;s=CNC-1.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 236 | `workcenters/CNC-1/job` | CNC-1 | P-01 | ns=2;s=CNC-1.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 237 | `workcenters/CNC-2/state` | CNC-2 | P-01 | ns=2;s=CNC-2.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 238 | `workcenters/CNC-2/mode` | CNC-2 | P-01 | ns=2;s=CNC-2.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 239 | `workcenters/CNC-2/alarm` | CNC-2 | P-01 | ns=2;s=CNC-2.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 240 | `workcenters/CNC-2/pieces_out` | CNC-2 | P-01 | ns=2;s=CNC-2.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 241 | `workcenters/CNC-2/job` | CNC-2 | P-01 | ns=2;s=CNC-2.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 242 | `workcenters/CNC-3/state` | CNC-3 | P-01 | ns=2;s=CNC-3.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 243 | `workcenters/CNC-3/mode` | CNC-3 | P-01 | ns=2;s=CNC-3.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 244 | `workcenters/CNC-3/alarm` | CNC-3 | P-01 | ns=2;s=CNC-3.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 245 | `workcenters/CNC-3/pieces_out` | CNC-3 | P-01 | ns=2;s=CNC-3.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 246 | `workcenters/CNC-3/job` | CNC-3 | P-01 | ns=2;s=CNC-3.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 247 | `workcenters/CNC-4/state` | CNC-4 | P-01 | ns=2;s=CNC-4.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 248 | `workcenters/CNC-4/mode` | CNC-4 | P-01 | ns=2;s=CNC-4.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 249 | `workcenters/CNC-4/alarm` | CNC-4 | P-01 | ns=2;s=CNC-4.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 250 | `workcenters/CNC-4/pieces_out` | CNC-4 | P-01 | ns=2;s=CNC-4.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 251 | `workcenters/CNC-4/job` | CNC-4 | P-01 | ns=2;s=CNC-4.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 252 | `workcenters/BORE-1/state` | BORE-1 | P-01 | ns=2;s=BORE-1.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 253 | `workcenters/BORE-1/mode` | BORE-1 | P-01 | ns=2;s=BORE-1.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 254 | `workcenters/BORE-1/alarm` | BORE-1 | P-01 | ns=2;s=BORE-1.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 255 | `workcenters/BORE-1/pieces_out` | BORE-1 | P-01 | ns=2;s=BORE-1.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 256 | `workcenters/BORE-1/job` | BORE-1 | P-01 | ns=2;s=BORE-1.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 257 | `workcenters/DOWEL-1/state` | DOWEL-1 | P-01 | ns=2;s=DOWEL-1.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 258 | `workcenters/DOWEL-1/mode` | DOWEL-1 | P-01 | ns=2;s=DOWEL-1.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 259 | `workcenters/DOWEL-1/alarm` | DOWEL-1 | P-01 | ns=2;s=DOWEL-1.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 260 | `workcenters/DOWEL-1/pieces_out` | DOWEL-1 | P-01 | ns=2;s=DOWEL-1.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 261 | `workcenters/DOWEL-1/job` | DOWEL-1 | P-01 | ns=2;s=DOWEL-1.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 262 | `workcenters/SORT-1/state` | SORT-1 | P-01 | ns=2;s=SORT-1.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 263 | `workcenters/SORT-1/mode` | SORT-1 | P-01 | ns=2;s=SORT-1.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 264 | `workcenters/SORT-1/alarm` | SORT-1 | P-01 | ns=2;s=SORT-1.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 265 | `workcenters/SORT-1/pieces_out` | SORT-1 | P-01 | ns=2;s=SORT-1.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 266 | `workcenters/SORT-1/job` | SORT-1 | P-01 | ns=2;s=SORT-1.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 267 | `workcenters/ASMLINE-1/state` | ASMLINE-1 | P-01 | ns=2;s=ASMLINE-1.State.Machine.Overview.CurrentState | WwUnitStateEnumeration | 0…4 | — | READY/WORKING/ERROR за R-14 | — (заявки ТО — лише з `…/alarm`, X-38) | R-14 стан верстата за завданням | новий |
| 268 | `workcenters/ASMLINE-1/mode` | ASMLINE-1 | P-01 | ns=2;s=ASMLINE-1.State.Machine.Overview.CurrentMode | WwUnitModeEnumeration | 0…5 | — | AUTOMATIC(1) | — | R-14 | новий |
| 269 | `workcenters/ASMLINE-1/alarm` | ASMLINE-1 | P-01 | ns=2;s=ASMLINE-1.State.Machine.Flags.Alarm (+ Error, Warning) | Boolean | — | — | False | True → заявка | R-15 збій (сценарій machine_fault) | новий |
| 270 | `workcenters/ASMLINE-1/pieces_out` | ASMLINE-1 | P-01 | ns=2;s=ASMLINE-1.State.Machine.Values.RelativePiecesOut | UInt64 | шт | — | 0 на початку зміни | — | R-16 лічильник деталей | новий |
| 271 | `workcenters/ASMLINE-1/job` | ASMLINE-1 | P-01 | ns=2;s=ASMLINE-1.JobManagement.JobOrderControl.JobOrderList[0].JobOrderID | String | — | — | `WO%05d` з id `mrp.workorder` (синтетичне — `SIM-%05d`, випуск `/jobs` — `cj-…`) | — | R-17 завдання | новий |
| 272 | `workcenters/SLIDE-1/state` | SLIDE-1 | P-02 | Modbus u80 fc2 pdu0 bool · ADAM-6050 DI0 00001 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 273 | `workcenters/SLIDE-1/alarm` | SLIDE-1 | P-02 | Modbus u80 fc2 pdu1 bool · ADAM-6050 DI1 00002 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 274 | `workcenters/SLIDE-1/pieces_out` | SLIDE-1 | P-02 | Modbus u80 fc3 pdu0+2 u32 little · ADAM-6050 40001–40002 лічильник DI0, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 275 | `workcenters/VSAW-1/state` | VSAW-1 | P-02 | Modbus u80 fc2 pdu2 bool · ADAM-6050 DI2 00003 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 276 | `workcenters/VSAW-1/alarm` | VSAW-1 | P-02 | Modbus u80 fc2 pdu3 bool · ADAM-6050 DI3 00004 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 277 | `workcenters/VSAW-1/pieces_out` | VSAW-1 | P-02 | Modbus u80 fc3 pdu4+2 u32 little · ADAM-6050 40005–40006 лічильник DI2, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 278 | `workcenters/SAND-1/state` | SAND-1 | P-02 | Modbus u80 fc2 pdu4 bool · ADAM-6050 DI4 00005 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 279 | `workcenters/SAND-1/alarm` | SAND-1 | P-02 | Modbus u80 fc2 pdu5 bool · ADAM-6050 DI5 00006 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 280 | `workcenters/SAND-1/pieces_out` | SAND-1 | P-02 | Modbus u80 fc3 pdu8+2 u32 little · ADAM-6050 40009–40010 лічильник DI4, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 281 | `workcenters/PRESS-1/state` | PRESS-1 | P-02 | Modbus u80 fc2 pdu6 bool · ADAM-6050 DI6 00007 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 282 | `workcenters/PRESS-1/alarm` | PRESS-1 | P-02 | Modbus u80 fc2 pdu7 bool · ADAM-6050 DI7 00008 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 283 | `workcenters/PRESS-1/pieces_out` | PRESS-1 | P-02 | Modbus u80 fc3 pdu12+2 u32 little · ADAM-6050 40013–40014 лічильник DI6, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 284 | `workcenters/GLUE-1/state` | GLUE-1 | P-02 | Modbus u80 fc2 pdu8 bool · ADAM-6050 DI8 00009 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 285 | `workcenters/GLUE-1/alarm` | GLUE-1 | P-02 | Modbus u80 fc2 pdu9 bool · ADAM-6050 DI9 00010 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 286 | `workcenters/GLUE-1/pieces_out` | GLUE-1 | P-02 | Modbus u80 fc3 pdu16+2 u32 little · ADAM-6050 40017–40018 лічильник DI8, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 287 | `workcenters/SPRAY-1/state` | SPRAY-1 | P-02 | Modbus u81 fc2 pdu0 bool · ADAM-6050 DI0 00001 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 288 | `workcenters/SPRAY-1/alarm` | SPRAY-1 | P-02 | Modbus u81 fc2 pdu1 bool · ADAM-6050 DI1 00002 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 289 | `workcenters/SPRAY-1/pieces_out` | SPRAY-1 | P-02 | Modbus u81 fc3 pdu0+2 u32 little · ADAM-6050 40001–40002 лічильник DI0, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 290 | `workcenters/AUTOSPRAY-1/state` | AUTOSPRAY-1 | P-02 | Modbus u81 fc2 pdu2 bool · ADAM-6050 DI2 00003 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 291 | `workcenters/AUTOSPRAY-1/alarm` | AUTOSPRAY-1 | P-02 | Modbus u81 fc2 pdu3 bool · ADAM-6050 DI3 00004 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 292 | `workcenters/AUTOSPRAY-1/pieces_out` | AUTOSPRAY-1 | P-02 | Modbus u81 fc3 pdu4+2 u32 little · ADAM-6050 40005–40006 лічильник DI2, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 293 | `workcenters/DRY-1/state` | DRY-1 | P-02 | Modbus u81 fc2 pdu4 bool · ADAM-6050 DI4 00005 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 294 | `workcenters/DRY-1/alarm` | DRY-1 | P-02 | Modbus u81 fc2 pdu5 bool · ADAM-6050 DI5 00006 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 295 | `workcenters/DRY-1/pieces_out` | DRY-1 | P-02 | Modbus u81 fc3 pdu8+2 u32 little · ADAM-6050 40009–40010 лічильник DI4, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 296 | `workcenters/UV-1/state` | UV-1 | P-02 | Modbus u81 fc2 pdu6 bool · ADAM-6050 DI6 00007 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 297 | `workcenters/UV-1/alarm` | UV-1 | P-02 | Modbus u81 fc2 pdu7 bool · ADAM-6050 DI7 00008 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 298 | `workcenters/UV-1/pieces_out` | UV-1 | P-02 | Modbus u81 fc3 pdu12+2 u32 little · ADAM-6050 40013–40014 лічильник DI6, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 299 | `workcenters/HINGE-1/state` | HINGE-1 | P-02 | Modbus u81 fc2 pdu8 bool · ADAM-6050 DI8 00009 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 300 | `workcenters/HINGE-1/alarm` | HINGE-1 | P-02 | Modbus u81 fc2 pdu9 bool · ADAM-6050 DI9 00010 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 301 | `workcenters/HINGE-1/pieces_out` | HINGE-1 | P-02 | Modbus u81 fc3 pdu16+2 u32 little · ADAM-6050 40017–40018 лічильник DI8, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 302 | `workcenters/BOX-1/state` | BOX-1 | P-02 | Modbus u82 fc2 pdu0 bool · ADAM-6050 DI0 00001 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 303 | `workcenters/BOX-1/alarm` | BOX-1 | P-02 | Modbus u82 fc2 pdu1 bool · ADAM-6050 DI1 00002 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 304 | `workcenters/BOX-1/pieces_out` | BOX-1 | P-02 | Modbus u82 fc3 pdu0+2 u32 little · ADAM-6050 40001–40002 лічильник DI0, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 305 | `workcenters/PACK-1/state` | PACK-1 | P-02 | Modbus u82 fc2 pdu2 bool · ADAM-6050 DI2 00003 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 306 | `workcenters/PACK-1/alarm` | PACK-1 | P-02 | Modbus u82 fc2 pdu3 bool · ADAM-6050 DI3 00004 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 307 | `workcenters/PACK-1/pieces_out` | PACK-1 | P-02 | Modbus u82 fc3 pdu4+2 u32 little · ADAM-6050 40005–40006 лічильник DI2, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 308 | `workcenters/PACK-2/state` | PACK-2 | P-02 | Modbus u82 fc2 pdu4 bool · ADAM-6050 DI4 00005 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 309 | `workcenters/PACK-2/alarm` | PACK-2 | P-02 | Modbus u82 fc2 pdu5 bool · ADAM-6050 DI5 00006 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 310 | `workcenters/PACK-2/pieces_out` | PACK-2 | P-02 | Modbus u82 fc3 pdu8+2 u32 little · ADAM-6050 40009–40010 лічильник DI4, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 311 | `workcenters/PACKLINE-1/state` | PACKLINE-1 | P-02 | Modbus u82 fc2 pdu6 bool · ADAM-6050 DI6 00007 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 312 | `workcenters/PACKLINE-1/alarm` | PACKLINE-1 | P-02 | Modbus u82 fc2 pdu7 bool · ADAM-6050 DI7 00008 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 313 | `workcenters/PACKLINE-1/pieces_out` | PACKLINE-1 | P-02 | Modbus u82 fc3 pdu12+2 u32 little · ADAM-6050 40013–40014 лічильник DI6, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 314 | `workcenters/ASM-1/state` | ASM-1 | P-02 | Modbus u82 fc2 pdu8 bool · ADAM-6050 DI8 00009 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 315 | `workcenters/ASM-1/alarm` | ASM-1 | P-02 | Modbus u82 fc2 pdu9 bool · ADAM-6050 DI9 00010 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 316 | `workcenters/ASM-1/pieces_out` | ASM-1 | P-02 | Modbus u82 fc3 pdu16+2 u32 little · ADAM-6050 40017–40018 лічильник DI8, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 317 | `workcenters/ASM-2/state` | ASM-2 | P-02 | Modbus u83 fc2 pdu0 bool · ADAM-6050 DI0 00001 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 318 | `workcenters/ASM-2/alarm` | ASM-2 | P-02 | Modbus u83 fc2 pdu1 bool · ADAM-6050 DI1 00002 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 319 | `workcenters/ASM-2/pieces_out` | ASM-2 | P-02 | Modbus u83 fc3 pdu0+2 u32 little · ADAM-6050 40001–40002 лічильник DI0, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 320 | `workcenters/ASM-3/state` | ASM-3 | P-02 | Modbus u83 fc2 pdu2 bool · ADAM-6050 DI2 00003 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 321 | `workcenters/ASM-3/alarm` | ASM-3 | P-02 | Modbus u83 fc2 pdu3 bool · ADAM-6050 DI3 00004 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 322 | `workcenters/ASM-3/pieces_out` | ASM-3 | P-02 | Modbus u83 fc3 pdu4+2 u32 little · ADAM-6050 40005–40006 лічильник DI2, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 323 | `workcenters/ASM-4/state` | ASM-4 | P-02 | Modbus u83 fc2 pdu4 bool · ADAM-6050 DI4 00005 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 324 | `workcenters/ASM-4/alarm` | ASM-4 | P-02 | Modbus u83 fc2 pdu5 bool · ADAM-6050 DI5 00006 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 325 | `workcenters/ASM-4/pieces_out` | ASM-4 | P-02 | Modbus u83 fc3 pdu8+2 u32 little · ADAM-6050 40009–40010 лічильник DI4, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 326 | `workcenters/ASM-5/state` | ASM-5 | P-02 | Modbus u83 fc2 pdu6 bool · ADAM-6050 DI6 00007 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 327 | `workcenters/ASM-5/alarm` | ASM-5 | P-02 | Modbus u83 fc2 pdu7 bool · ADAM-6050 DI7 00008 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 328 | `workcenters/ASM-5/pieces_out` | ASM-5 | P-02 | Modbus u83 fc3 pdu12+2 u32 little · ADAM-6050 40013–40014 лічильник DI6, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 329 | `workcenters/ASM-6/state` | ASM-6 | P-02 | Modbus u83 fc2 pdu8 bool · ADAM-6050 DI8 00009 (в роботі) | bit | 0/1 | — | 1 коли завдання в роботі | — | R-14 (DI) | новий |
| 330 | `workcenters/ASM-6/alarm` | ASM-6 | P-02 | Modbus u83 fc2 pdu9 bool · ADAM-6050 DI9 00010 (аварія) | bit | 0/1 | — | 0 | 1 → заявка | R-15 | новий |
| 331 | `workcenters/ASM-6/pieces_out` | ASM-6 | P-02 | Modbus u83 fc3 pdu16+2 u32 little · ADAM-6050 40017–40018 лічильник DI8, 32 біт, молодше слово першим | U32 | шт | ×1 | накопич. | — | R-16 (цикл = деталь) | новий |
| 332 | `equipment/GANTRY-1/state` | GANTRY-1 | P-03 | GET /api/v1/status → $.state (+ OPC UA GANTRY-1.State.Machine.Overview.CurrentState) | enum | idle/moving/picking/placing/blocked/error | — | idle | error → заявка | R-18 портал | новий |
| 333 | `equipment/GANTRY-1/job` | GANTRY-1 | P-03 | GET /api/v1/jobs?state=active → $[0].id | String | — | — | — | — | R-18 | новий |
| 334 | `equipment/GANTRY-1/stacks` | GANTRY-1 | — | обчислює machine_connect з woodStore API-21 `GET /api/v1/stacks` (кількість стосів з `qty > 0`, `MC-DERIVED`) — без адреси (X-76); сирі дані стосів — лише через woodStore REST API-21/API-22 | int | шт | — | 23 | — | обчислює machine_connect | новий |
| 335 | `equipment/FL-1/state` | FL-1 | P-06 | MQTT f3d/mobile/FL-1/telemetry → $.state | enum | busy/idle/charging/offline | — | busy | offline > 5 хв → stale | R-05 | новий |
| 336 | `equipment/FL-1/x` | FL-1 | P-06 | MQTT f3d/mobile/FL-1/telemetry → $.x | number | м | — | координата сцени | — | R-19 рух по маршруту | новий |
| 337 | `equipment/FL-1/y` | FL-1 | P-06 | MQTT f3d/mobile/FL-1/telemetry → $.y | number | м | — | координата сцени | — | R-19 | новий |
| 338 | `equipment/FL-2/state` | FL-2 | P-06 | MQTT f3d/mobile/FL-2/telemetry → $.state | enum | busy/idle/charging/offline | — | busy | offline > 5 хв → stale | R-05 | новий |
| 339 | `equipment/FL-2/x` | FL-2 | P-06 | MQTT f3d/mobile/FL-2/telemetry → $.x | number | м | — | координата сцени | — | R-19 рух по маршруту | новий |
| 340 | `equipment/FL-2/y` | FL-2 | P-06 | MQTT f3d/mobile/FL-2/telemetry → $.y | number | м | — | координата сцени | — | R-19 | новий |
| 341 | `equipment/FL-3/state` | FL-3 | P-06 | MQTT f3d/mobile/FL-3/telemetry → $.state | enum | busy/idle/charging/offline | — | busy | offline > 5 хв → stale | R-05 | новий |
| 342 | `equipment/FL-3/x` | FL-3 | P-06 | MQTT f3d/mobile/FL-3/telemetry → $.x | number | м | — | координата сцени | — | R-19 рух по маршруту | новий |
| 343 | `equipment/FL-3/y` | FL-3 | P-06 | MQTT f3d/mobile/FL-3/telemetry → $.y | number | м | — | координата сцени | — | R-19 | новий |
| 344 | `equipment/FL-4/state` | FL-4 | P-06 | MQTT f3d/mobile/FL-4/telemetry → $.state | enum | busy/idle/charging/offline | — | busy | offline > 5 хв → stale | R-05 | новий |
| 345 | `equipment/FL-4/x` | FL-4 | P-06 | MQTT f3d/mobile/FL-4/telemetry → $.x | number | м | — | координата сцени | — | R-19 рух по маршруту | новий |
| 346 | `equipment/FL-4/y` | FL-4 | P-06 | MQTT f3d/mobile/FL-4/telemetry → $.y | number | м | — | координата сцени | — | R-19 | новий |
| 347 | `equipment/FL-5/state` | FL-5 | P-06 | MQTT f3d/mobile/FL-5/telemetry → $.state | enum | busy/idle/charging/offline | — | busy | offline > 5 хв → stale | R-05 | новий |
| 348 | `equipment/FL-5/x` | FL-5 | P-06 | MQTT f3d/mobile/FL-5/telemetry → $.x | number | м | — | координата сцени | — | R-19 рух по маршруту | новий |
| 349 | `equipment/FL-5/y` | FL-5 | P-06 | MQTT f3d/mobile/FL-5/telemetry → $.y | number | м | — | координата сцени | — | R-19 | новий |
| 350 | `equipment/FL-C1/state` | FL-C1 | P-06 | MQTT f3d/mobile/FL-C1/telemetry → $.state | enum | busy/idle/charging/offline | — | busy | offline > 5 хв → stale | R-05 | новий |
| 351 | `equipment/FL-C1/x` | FL-C1 | P-06 | MQTT f3d/mobile/FL-C1/telemetry → $.x | number | м | — | координата сцени | — | R-19 рух по маршруту | новий |
| 352 | `equipment/FL-C1/y` | FL-C1 | P-06 | MQTT f3d/mobile/FL-C1/telemetry → $.y | number | м | — | координата сцени | — | R-19 | новий |
| 353 | `equipment/FL-C2/state` | FL-C2 | P-06 | MQTT f3d/mobile/FL-C2/telemetry → $.state | enum | busy/idle/charging/offline | — | busy | offline > 5 хв → stale | R-05 | новий |
| 354 | `equipment/FL-C2/x` | FL-C2 | P-06 | MQTT f3d/mobile/FL-C2/telemetry → $.x | number | м | — | координата сцени | — | R-19 рух по маршруту | новий |
| 355 | `equipment/FL-C2/y` | FL-C2 | P-06 | MQTT f3d/mobile/FL-C2/telemetry → $.y | number | м | — | координата сцени | — | R-19 | новий |
| 356 | `equipment/TUGGER-1/state` | TUGGER-1 | P-06 | MQTT f3d/mobile/TUGGER-1/telemetry → $.state | enum | busy/idle/charging/offline | — | busy | offline > 5 хв → stale | R-05 | новий |
| 357 | `equipment/TUGGER-1/x` | TUGGER-1 | P-06 | MQTT f3d/mobile/TUGGER-1/telemetry → $.x | number | м | — | координата сцени | — | R-19 рух по маршруту | новий |
| 358 | `equipment/TUGGER-1/y` | TUGGER-1 | P-06 | MQTT f3d/mobile/TUGGER-1/telemetry → $.y | number | м | — | координата сцени | — | R-19 | новий |
| 359 | `equipment/COMPRESSOR/state` | COMPRESSOR | P-07 | Modbus u70 fc3 pdu3000 u16 · Elektronikon Mk5 3001 Machine status (ПРИПУЩЕННЯ) | U16 | 0 stop/1 load/2 unload/3 fault | — | 1 | 3 → заявка | R-08 | новий |
| 360 | `equipment/COMPRESSOR/temp_c` | COMPRESSOR | P-07 | Modbus u70 fc3 pdu3002 u16 · Elektronikon Mk5 3003 Element outlet temperature (ПРИПУЩЕННЯ) | U16 | °C | ×0,1 | 82 | > 110 → заявка | R-08 | новий |
| 361 | `equipment/DUST-1/state` | DUST-1 | P-07 | Modbus u84 fc2 pdu0+2 bool · ADAM-6050 DI0 00001 (вентилятори в роботі), DI1 00002 (аварія) — складений стан | bit | 0/1 | — | 1 | DI1=1 → заявка | R-09 | новий |
| 362 | `equipment/BOILER/return_c` | BOILER | P-08 | BACnet dev 140 AI:2 Present_Value (зворотка) | REAL | °C | ×1 | 58 | — | R-10 | новий |
| 363 | `equipment/BOILER/state` | BOILER | P-08 | BACnet dev 140 MSV:1 Present_Value | MSV | 1 standby/2 K1/3 K1+K2/4 fault | — | 1 (КГУ покриває тепло) | 4 → заявка | R-10 | новий |
| 364 | `infra/water/m3_total` | WATER | P-07 | Modbus u84 fc3 pdu16+2 u32 little · ADAM-6050 40017–40018 лічильник DI8, 1 імп = 10 л, Apator NK, молодше слово першим | U32 | імп→м³ | ×0,01 | 18 642 | — | R-21 вода | новий |
| 365 | `infra/water/flow_m3h` | WATER | P-07 | похідна m3_total за 5 хв | number | м³/год | — | 2,1 | — | R-21 | новий |
| 366 | `energy/cells/Q1/p_now` | Q1 | P-05 | Modbus u1 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | сума секції | — | R-01 | новий |
| 367 | `energy/cells/Q1/i_now` | Q1 | P-05 | Modbus u1 fc3 pdu3009+2 f32 · PM5560 3010–3011 Current Avg | F32 | А | ×1 | S/(√3·400) | > 1600 → заявка | R-01 | новий |
| 368 | `energy/cells/Q2/p_now` | Q2 | P-05 | Modbus u2 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | сума секції | — | R-01 | новий |
| 369 | `energy/cells/Q2/i_now` | Q2 | P-05 | Modbus u2 fc3 pdu3009+2 f32 · PM5560 3010–3011 Current Avg | F32 | А | ×1 | S/(√3·400) | > 1600 → заявка | R-01 | новий |
| 370 | `energy/lines/BW-1/p_now` | QF-1 | P-05 | Modbus u3 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | сума споживачів лінії | — | R-01 | новий |
| 371 | `energy/lines/BW-1/i_now` | QF-1 | P-05 | Modbus u3 fc3 pdu3009+2 f32 · PM5560 3010–3011 Current Avg | F32 | А | ×1 | — | > 0,9·номінал → warn | R-01 | новий |
| 372 | `energy/lines/BW-1/cos_phi` | QF-1 | P-05 | Modbus u3 fc3 pdu3083+2 f32 · PM5560 3084–3085 Power Factor Total | F32 | — | ×1 | 0,88–0,92 | < 0,85 → warn | R-01 | новий |
| 373 | `energy/lines/BW-2/p_now` | QF-2 | P-05 | Modbus u4 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | сума споживачів лінії | — | R-01 | новий |
| 374 | `energy/lines/BW-2/i_now` | QF-2 | P-05 | Modbus u4 fc3 pdu3009+2 f32 · PM5560 3010–3011 Current Avg | F32 | А | ×1 | — | > 0,9·номінал → warn | R-01 | новий |
| 375 | `energy/lines/BW-2/cos_phi` | QF-2 | P-05 | Modbus u4 fc3 pdu3083+2 f32 · PM5560 3084–3085 Power Factor Total | F32 | — | ×1 | 0,88–0,92 | < 0,85 → warn | R-01 | новий |
| 376 | `energy/lines/BW-3/p_now` | QF-3 | P-05 | Modbus u5 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | сума споживачів лінії | — | R-01 | новий |
| 377 | `energy/lines/BW-3/i_now` | QF-3 | P-05 | Modbus u5 fc3 pdu3009+2 f32 · PM5560 3010–3011 Current Avg | F32 | А | ×1 | — | > 0,9·номінал → warn | R-01 | новий |
| 378 | `energy/lines/BW-3/cos_phi` | QF-3 | P-05 | Modbus u5 fc3 pdu3083+2 f32 · PM5560 3084–3085 Power Factor Total | F32 | — | ×1 | 0,88–0,92 | < 0,85 → warn | R-01 | новий |
| 379 | `energy/lines/BW-4/p_now` | QF-4 | P-05 | Modbus u6 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | сума споживачів лінії | — | R-01 | новий |
| 380 | `energy/lines/BW-4/i_now` | QF-4 | P-05 | Modbus u6 fc3 pdu3009+2 f32 · PM5560 3010–3011 Current Avg | F32 | А | ×1 | — | > 0,9·номінал → warn | R-01 | новий |
| 381 | `energy/lines/BW-4/cos_phi` | QF-4 | P-05 | Modbus u6 fc3 pdu3083+2 f32 · PM5560 3084–3085 Power Factor Total | F32 | — | ×1 | 0,88–0,92 | < 0,85 → warn | R-01 | новий |
| 382 | `energy/lines/C1/p_now` | QF-C1 | P-05 | Modbus u7 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | сума споживачів лінії | — | R-01 | новий |
| 383 | `energy/lines/C1/i_now` | QF-C1 | P-05 | Modbus u7 fc3 pdu3009+2 f32 · PM5560 3010–3011 Current Avg | F32 | А | ×1 | — | > 0,9·номінал → warn | R-01 | новий |
| 384 | `energy/lines/C1/cos_phi` | QF-C1 | P-05 | Modbus u7 fc3 pdu3083+2 f32 · PM5560 3084–3085 Power Factor Total | F32 | — | ×1 | 0,88–0,92 | < 0,85 → warn | R-01 | новий |
| 385 | `energy/lines/C2/p_now` | QF-C2 | P-05 | Modbus u8 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | сума споживачів лінії | — | R-01 | новий |
| 386 | `energy/lines/C2/i_now` | QF-C2 | P-05 | Modbus u8 fc3 pdu3009+2 f32 · PM5560 3010–3011 Current Avg | F32 | А | ×1 | — | > 0,9·номінал → warn | R-01 | новий |
| 387 | `energy/lines/C2/cos_phi` | QF-C2 | P-05 | Modbus u8 fc3 pdu3083+2 f32 · PM5560 3084–3085 Power Factor Total | F32 | — | ×1 | 0,88–0,92 | < 0,85 → warn | R-01 | новий |
| 388 | `energy/transformers/T1/i_a` | T1 | P-05 | Modbus u1 fc3 pdu3009+2 f32 · PM5560 3010–3011 Current Avg | F32 | А | ×1 | 498 / 433 | — | R-04 | новий |
| 389 | `energy/transformers/T1/cos_phi` | T1 | P-05 | Modbus u1 fc3 pdu3083+2 f32 · PM5560 3084–3085 Power Factor Total | F32 | — | ×1 | 0,97 | — | R-04 | новий |
| 390 | `energy/transformers/T1/s_kva` | T1 | P-05 | Modbus u1 fc3 pdu3075+2 f32 · PM5560 3076–3077 Apparent Power Total | F32 | кВА | ×1 | 345 / 300 | > 1000 → заявка | R-04 | новий |
| 391 | `energy/transformers/T2/i_a` | T2 | P-05 | Modbus u2 fc3 pdu3009+2 f32 · PM5560 3010–3011 Current Avg | F32 | А | ×1 | 498 / 433 | — | R-04 | новий |
| 392 | `energy/transformers/T2/cos_phi` | T2 | P-05 | Modbus u2 fc3 pdu3083+2 f32 · PM5560 3084–3085 Power Factor Total | F32 | — | ×1 | 0,97 | — | R-04 | новий |
| 393 | `energy/transformers/T2/s_kva` | T2 | P-05 | Modbus u2 fc3 pdu3075+2 f32 · PM5560 3076–3077 Apparent Power Total | F32 | кВА | ×1 | 345 / 300 | > 1000 → заявка | R-04 | новий |
| 394 | `infra/pv/PV-INV-1/p_kw` | PV-INV | P-07 | Modbus u61 fc3 pdu32080+2 i32 · SUN2000 32080–32081 Active power | I32 | кВт | ×0,001 | до 115 | — | R-11 | новий |
| 395 | `infra/pv/PV-INV-1/status` | PV-INV | P-07 | Modbus u61 fc3 pdu32089 u16 · SUN2000 32089 Device status | U16 | enum Huawei | — | 0x0200 On-grid | 0x0300… → заявка | R-11 | новий |
| 396 | `infra/pv/PV-INV-1/kwh_today` | PV-INV | P-07 | Modbus u61 fc3 pdu32114+2 u32 · SUN2000 32114–32115 Daily energy yield | U32 | кВт·год | ×0,01 | — | — | R-11 | новий |
| 397 | `infra/pv/PV-INV-2/p_kw` | PV-INV | P-07 | Modbus u62 fc3 pdu32080+2 i32 · SUN2000 32080–32081 Active power | I32 | кВт | ×0,001 | до 115 | — | R-11 | новий |
| 398 | `infra/pv/PV-INV-2/status` | PV-INV | P-07 | Modbus u62 fc3 pdu32089 u16 · SUN2000 32089 Device status | U16 | enum Huawei | — | 0x0200 On-grid | 0x0300… → заявка | R-11 | новий |
| 399 | `infra/pv/PV-INV-2/kwh_today` | PV-INV | P-07 | Modbus u62 fc3 pdu32114+2 u32 · SUN2000 32114–32115 Daily energy yield | U32 | кВт·год | ×0,01 | — | — | R-11 | новий |
| 400 | `infra/pv/PV-INV-3/p_kw` | PV-INV | P-07 | Modbus u63 fc3 pdu32080+2 i32 · SUN2000 32080–32081 Active power | I32 | кВт | ×0,001 | до 115 | — | R-11 | новий |
| 401 | `infra/pv/PV-INV-3/status` | PV-INV | P-07 | Modbus u63 fc3 pdu32089 u16 · SUN2000 32089 Device status | U16 | enum Huawei | — | 0x0200 On-grid | 0x0300… → заявка | R-11 | новий |
| 402 | `infra/pv/PV-INV-3/kwh_today` | PV-INV | P-07 | Modbus u63 fc3 pdu32114+2 u32 · SUN2000 32114–32115 Daily energy yield | U32 | кВт·год | ×0,01 | — | — | R-11 | новий |
| 403 | `infra/pv/PV-INV-4/p_kw` | PV-INV | P-07 | Modbus u64 fc3 pdu32080+2 i32 · SUN2000 32080–32081 Active power | I32 | кВт | ×0,001 | до 115 | — | R-11 | новий |
| 404 | `infra/pv/PV-INV-4/status` | PV-INV | P-07 | Modbus u64 fc3 pdu32089 u16 · SUN2000 32089 Device status | U16 | enum Huawei | — | 0x0200 On-grid | 0x0300… → заявка | R-11 | новий |
| 405 | `infra/pv/PV-INV-4/kwh_today` | PV-INV | P-07 | Modbus u64 fc3 pdu32114+2 u32 · SUN2000 32114–32115 Daily energy yield | U32 | кВт·год | ×0,01 | — | — | R-11 | новий |
| 406 | `infra/pv/PV-INV-5/p_kw` | PV-INV | P-07 | Modbus u65 fc3 pdu32080+2 i32 · SUN2000 32080–32081 Active power | I32 | кВт | ×0,001 | до 115 | — | R-11 | новий |
| 407 | `infra/pv/PV-INV-5/status` | PV-INV | P-07 | Modbus u65 fc3 pdu32089 u16 · SUN2000 32089 Device status | U16 | enum Huawei | — | 0x0200 On-grid | 0x0300… → заявка | R-11 | новий |
| 408 | `infra/pv/PV-INV-5/kwh_today` | PV-INV | P-07 | Modbus u65 fc3 pdu32114+2 u32 · SUN2000 32114–32115 Daily energy yield | U32 | кВт·год | ×0,01 | — | — | R-11 | новий |
| 409 | `infra/pv/PV-INV-6/p_kw` | PV-INV | P-07 | Modbus u66 fc3 pdu32080+2 i32 · SUN2000 32080–32081 Active power | I32 | кВт | ×0,001 | до 115 | — | R-11 | новий |
| 410 | `infra/pv/PV-INV-6/status` | PV-INV | P-07 | Modbus u66 fc3 pdu32089 u16 · SUN2000 32089 Device status | U16 | enum Huawei | — | 0x0200 On-grid | 0x0300… → заявка | R-11 | новий |
| 411 | `infra/pv/PV-INV-6/kwh_today` | PV-INV | P-07 | Modbus u66 fc3 pdu32114+2 u32 · SUN2000 32114–32115 Daily energy yield | U32 | кВт·год | ×0,01 | — | — | R-11 | новий |
| 412 | `infra/pv/PV-INV-7/p_kw` | PV-INV | P-07 | Modbus u67 fc3 pdu32080+2 i32 · SUN2000 32080–32081 Active power | I32 | кВт | ×0,001 | до 115 | — | R-11 | новий |
| 413 | `infra/pv/PV-INV-7/status` | PV-INV | P-07 | Modbus u67 fc3 pdu32089 u16 · SUN2000 32089 Device status | U16 | enum Huawei | — | 0x0200 On-grid | 0x0300… → заявка | R-11 | новий |
| 414 | `infra/pv/PV-INV-7/kwh_today` | PV-INV | P-07 | Modbus u67 fc3 pdu32114+2 u32 · SUN2000 32114–32115 Daily energy yield | U32 | кВт·год | ×0,01 | — | — | R-11 | новий |
| 415 | `infra/pv/PV-INV-8/p_kw` | PV-INV | P-07 | Modbus u68 fc3 pdu32080+2 i32 · SUN2000 32080–32081 Active power | I32 | кВт | ×0,001 | до 115 | — | R-11 | новий |
| 416 | `infra/pv/PV-INV-8/status` | PV-INV | P-07 | Modbus u68 fc3 pdu32089 u16 · SUN2000 32089 Device status | U16 | enum Huawei | — | 0x0200 On-grid | 0x0300… → заявка | R-11 | новий |
| 417 | `infra/pv/PV-INV-8/kwh_today` | PV-INV | P-07 | Modbus u68 fc3 pdu32114+2 u32 · SUN2000 32114–32115 Daily energy yield | U32 | кВт·год | ×0,01 | — | — | R-11 | новий |
| 418 | `infra/totals/grid_kw` | EMS-1 | — | обчислює energy (R-06 (вводи u1/u2, СЕС, КГУ, BESS)) — без адреси (X-35) | number | кВт | — | 0 удень | — | обчислює energy (R-13 емулятора — баланс) | новий |
| 419 | `infra/totals/export_kw` | EMS-1 | — | обчислює energy (R-06 (вводи u1/u2, СЕС, КГУ, BESS)) — без адреси (X-35) | number | кВт | — | 42 | — | обчислює energy (R-13 емулятора — баланс) | новий |
| 420 | `infra/totals/bess_kw` | BESS | P-07 | Modbus u69 fc3 pdu37001+2 i32 · LUNA2000 37001–37002 Charge/Discharge power, + заряд | I32 | кВт | ×0,001 | 200 (заряд) | — | R-13 | новий |
| 421 | `infra/bess/state` | BESS | P-07 | Modbus u69 fc3 pdu37000 u16 · LUNA2000 37000 Running status | U16 | 0 offline/1 standby/2 running/3 fault/4 sleep | — | 2 | 3 → заявка | R-13 | новий |
| 422 | `infra/chp/hours` | CHP | P-07 | Modbus u72 fc3 pdu40010+2 u32 · TEDOM 40010–40011 Running hours (ПРИПУЩЕННЯ) | U32 | год | ×1 | 3 412 | ≥ 80 000 → капремонт | R-12 | новий |
| 423 | `infra/chp/heat_kw` | CHP | P-07 | Modbus u72 fc3 pdu40002 u16 · TEDOM 40002 Heat output (ПРИПУЩЕННЯ) | U16 | кВт | ×1 | 497 | — | R-12 | новий |
| 424 | `infra/chp/gas_m3h` | CHP | P-07 | Modbus u72 fc3 pdu40003 u16 · TEDOM 40003 Gas consumption (ПРИПУЩЕННЯ) | U16 | м³/год | ×0,1 | 109 | — | R-12 | новий |
| 425 | `infra/chp/state` | CHP | P-07 | Modbus u72 fc3 pdu40000 u16 · TEDOM 40000 State (ПРИПУЩЕННЯ) | U16 | 0 stop/1 start/2 run/3 fault | — | 2 | 3 → заявка | R-12 | новий |
| 426 | `infra/ats/position` | ATS-1 | P-07 | Modbus u71 fc3 pdu20483 u16 · ATyS p Annexe III 20483 Switch Position | U16 | 0 unknown/1 pos 0/2 pos I (мережа)/3 pos II (генератор) | — | 2 (I) | — | R-22 blackout | новий |
| 427 | `infra/ats/src1_ok` | ATS-1 | — | обчислює energy (R-14 з `infra/ats/src1_state`) — без адреси (X-35) | number | 0/1 | — | 1 | 0 → подія | обчислює energy (R-22 емулятора — стан джерела) | новий |
| 428 | `infra/ats/src2_ok` | ATS-1 | — | обчислює energy (R-14 з `infra/ats/src2_state`) — без адреси (X-35) | number | 0/1 | — | 0 (генератор зупинено) | — | обчислює energy (R-22 емулятора — стан джерела) | новий |
| 429 | `ventilation/units/RV-01/indoor_c` | RV-01 | P-08 | BACnet dev 101 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 430 | `ventilation/units/RV-01/heating_valve` | RV-01 | P-08 | BACnet dev 101 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 431 | `ventilation/units/RV-01/mode` | RV-01 | P-08 | BACnet dev 101 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 432 | `ventilation/units/RV-01/state` | RV-01 | P-08 | BACnet dev 101 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 433 | `ventilation/units/RV-02/indoor_c` | RV-02 | P-08 | BACnet dev 102 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 434 | `ventilation/units/RV-02/heating_valve` | RV-02 | P-08 | BACnet dev 102 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 435 | `ventilation/units/RV-02/mode` | RV-02 | P-08 | BACnet dev 102 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 436 | `ventilation/units/RV-02/state` | RV-02 | P-08 | BACnet dev 102 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 437 | `ventilation/units/RV-03/indoor_c` | RV-03 | P-08 | BACnet dev 103 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 438 | `ventilation/units/RV-03/heating_valve` | RV-03 | P-08 | BACnet dev 103 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 439 | `ventilation/units/RV-03/mode` | RV-03 | P-08 | BACnet dev 103 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 440 | `ventilation/units/RV-03/state` | RV-03 | P-08 | BACnet dev 103 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 441 | `ventilation/units/RV-04/indoor_c` | RV-04 | P-08 | BACnet dev 104 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 442 | `ventilation/units/RV-04/heating_valve` | RV-04 | P-08 | BACnet dev 104 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 443 | `ventilation/units/RV-04/mode` | RV-04 | P-08 | BACnet dev 104 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 444 | `ventilation/units/RV-04/state` | RV-04 | P-08 | BACnet dev 104 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 445 | `ventilation/units/RV-05/indoor_c` | RV-05 | P-08 | BACnet dev 105 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 446 | `ventilation/units/RV-05/heating_valve` | RV-05 | P-08 | BACnet dev 105 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 447 | `ventilation/units/RV-05/mode` | RV-05 | P-08 | BACnet dev 105 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 448 | `ventilation/units/RV-05/state` | RV-05 | P-08 | BACnet dev 105 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 449 | `ventilation/units/RV-06/indoor_c` | RV-06 | P-08 | BACnet dev 106 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 450 | `ventilation/units/RV-06/heating_valve` | RV-06 | P-08 | BACnet dev 106 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 451 | `ventilation/units/RV-06/mode` | RV-06 | P-08 | BACnet dev 106 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 452 | `ventilation/units/RV-06/state` | RV-06 | P-08 | BACnet dev 106 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 453 | `ventilation/units/RV-07/indoor_c` | RV-07 | P-08 | BACnet dev 107 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 454 | `ventilation/units/RV-07/heating_valve` | RV-07 | P-08 | BACnet dev 107 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 455 | `ventilation/units/RV-07/mode` | RV-07 | P-08 | BACnet dev 107 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 456 | `ventilation/units/RV-07/state` | RV-07 | P-08 | BACnet dev 107 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 457 | `ventilation/units/RV-08/indoor_c` | RV-08 | P-08 | BACnet dev 108 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 458 | `ventilation/units/RV-08/heating_valve` | RV-08 | P-08 | BACnet dev 108 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 459 | `ventilation/units/RV-08/mode` | RV-08 | P-08 | BACnet dev 108 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 460 | `ventilation/units/RV-08/state` | RV-08 | P-08 | BACnet dev 108 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 461 | `ventilation/units/RV-09/indoor_c` | RV-09 | P-08 | BACnet dev 109 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 462 | `ventilation/units/RV-09/heating_valve` | RV-09 | P-08 | BACnet dev 109 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 463 | `ventilation/units/RV-09/mode` | RV-09 | P-08 | BACnet dev 109 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 464 | `ventilation/units/RV-09/state` | RV-09 | P-08 | BACnet dev 109 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 465 | `ventilation/units/RV-10/indoor_c` | RV-10 | P-08 | BACnet dev 110 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 466 | `ventilation/units/RV-10/heating_valve` | RV-10 | P-08 | BACnet dev 110 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 467 | `ventilation/units/RV-10/mode` | RV-10 | P-08 | BACnet dev 110 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 468 | `ventilation/units/RV-10/state` | RV-10 | P-08 | BACnet dev 110 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 469 | `ventilation/units/RV-11/indoor_c` | RV-11 | P-08 | BACnet dev 111 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 470 | `ventilation/units/RV-11/heating_valve` | RV-11 | P-08 | BACnet dev 111 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 471 | `ventilation/units/RV-11/mode` | RV-11 | P-08 | BACnet dev 111 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 472 | `ventilation/units/RV-11/state` | RV-11 | P-08 | BACnet dev 111 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 473 | `ventilation/units/RV-12/indoor_c` | RV-12 | P-08 | BACnet dev 112 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 474 | `ventilation/units/RV-12/heating_valve` | RV-12 | P-08 | BACnet dev 112 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 475 | `ventilation/units/RV-12/mode` | RV-12 | P-08 | BACnet dev 112 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 476 | `ventilation/units/RV-12/state` | RV-12 | P-08 | BACnet dev 112 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 477 | `ventilation/units/RV-13/indoor_c` | RV-13 | P-08 | BACnet dev 113 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 478 | `ventilation/units/RV-13/heating_valve` | RV-13 | P-08 | BACnet dev 113 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 479 | `ventilation/units/RV-13/mode` | RV-13 | P-08 | BACnet dev 113 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 480 | `ventilation/units/RV-13/state` | RV-13 | P-08 | BACnet dev 113 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 481 | `ventilation/units/RV-14/indoor_c` | RV-14 | P-08 | BACnet dev 114 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 482 | `ventilation/units/RV-14/heating_valve` | RV-14 | P-08 | BACnet dev 114 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 483 | `ventilation/units/RV-14/mode` | RV-14 | P-08 | BACnet dev 114 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 484 | `ventilation/units/RV-14/state` | RV-14 | P-08 | BACnet dev 114 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 485 | `ventilation/units/RV-15/indoor_c` | RV-15 | P-08 | BACnet dev 115 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 486 | `ventilation/units/RV-15/heating_valve` | RV-15 | P-08 | BACnet dev 115 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 487 | `ventilation/units/RV-15/mode` | RV-15 | P-08 | BACnet dev 115 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 488 | `ventilation/units/RV-15/state` | RV-15 | P-08 | BACnet dev 115 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 489 | `ventilation/units/RV-16/indoor_c` | RV-16 | P-08 | BACnet dev 116 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 490 | `ventilation/units/RV-16/heating_valve` | RV-16 | P-08 | BACnet dev 116 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 491 | `ventilation/units/RV-16/mode` | RV-16 | P-08 | BACnet dev 116 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 492 | `ventilation/units/RV-16/state` | RV-16 | P-08 | BACnet dev 116 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 493 | `ventilation/units/RV-17/indoor_c` | RV-17 | P-08 | BACnet dev 117 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 494 | `ventilation/units/RV-17/heating_valve` | RV-17 | P-08 | BACnet dev 117 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 495 | `ventilation/units/RV-17/mode` | RV-17 | P-08 | BACnet dev 117 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 496 | `ventilation/units/RV-17/state` | RV-17 | P-08 | BACnet dev 117 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 497 | `ventilation/units/RV-18/indoor_c` | RV-18 | P-08 | BACnet dev 118 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 498 | `ventilation/units/RV-18/heating_valve` | RV-18 | P-08 | BACnet dev 118 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 499 | `ventilation/units/RV-18/mode` | RV-18 | P-08 | BACnet dev 118 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 500 | `ventilation/units/RV-18/state` | RV-18 | P-08 | BACnet dev 118 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 501 | `ventilation/units/RV-19/indoor_c` | RV-19 | P-08 | BACnet dev 119 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 502 | `ventilation/units/RV-19/heating_valve` | RV-19 | P-08 | BACnet dev 119 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 503 | `ventilation/units/RV-19/mode` | RV-19 | P-08 | BACnet dev 119 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 504 | `ventilation/units/RV-19/state` | RV-19 | P-08 | BACnet dev 119 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 505 | `ventilation/units/RV-20/indoor_c` | RV-20 | P-08 | BACnet dev 120 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 506 | `ventilation/units/RV-20/heating_valve` | RV-20 | P-08 | BACnet dev 120 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 507 | `ventilation/units/RV-20/mode` | RV-20 | P-08 | BACnet dev 120 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 508 | `ventilation/units/RV-20/state` | RV-20 | P-08 | BACnet dev 120 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 509 | `ventilation/units/RV-21/indoor_c` | RV-21 | P-08 | BACnet dev 121 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 510 | `ventilation/units/RV-21/heating_valve` | RV-21 | P-08 | BACnet dev 121 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 511 | `ventilation/units/RV-21/mode` | RV-21 | P-08 | BACnet dev 121 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 512 | `ventilation/units/RV-21/state` | RV-21 | P-08 | BACnet dev 121 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 513 | `ventilation/units/RV-22/indoor_c` | RV-22 | P-08 | BACnet dev 122 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 514 | `ventilation/units/RV-22/heating_valve` | RV-22 | P-08 | BACnet dev 122 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 515 | `ventilation/units/RV-22/mode` | RV-22 | P-08 | BACnet dev 122 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 516 | `ventilation/units/RV-22/state` | RV-22 | P-08 | BACnet dev 122 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 517 | `ventilation/units/RV-23/indoor_c` | RV-23 | P-08 | BACnet dev 123 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 518 | `ventilation/units/RV-23/heating_valve` | RV-23 | P-08 | BACnet dev 123 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 519 | `ventilation/units/RV-23/mode` | RV-23 | P-08 | BACnet dev 123 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 520 | `ventilation/units/RV-23/state` | RV-23 | P-08 | BACnet dev 123 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 521 | `ventilation/units/RV-24/indoor_c` | RV-24 | P-08 | BACnet dev 124 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 522 | `ventilation/units/RV-24/heating_valve` | RV-24 | P-08 | BACnet dev 124 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 523 | `ventilation/units/RV-24/mode` | RV-24 | P-08 | BACnet dev 124 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 524 | `ventilation/units/RV-24/state` | RV-24 | P-08 | BACnet dev 124 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 525 | `ventilation/units/RV-25/indoor_c` | RV-25 | P-08 | BACnet dev 125 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 526 | `ventilation/units/RV-25/heating_valve` | RV-25 | P-08 | BACnet dev 125 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 527 | `ventilation/units/RV-25/mode` | RV-25 | P-08 | BACnet dev 125 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 528 | `ventilation/units/RV-25/state` | RV-25 | P-08 | BACnet dev 125 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 529 | `ventilation/units/AHU-1/indoor_c` | AHU-1 | P-08 | BACnet dev 130 AI:2 (витяжка/кімната) | REAL | °C | ×1 | 17,5–19,5 | — | R-23 вентустановка | новий |
| 530 | `ventilation/units/AHU-1/heating_valve` | AHU-1 | P-08 | BACnet dev 130 AO:1 (клапан нагрівача) | REAL | % | ×1 | за тепловим балансом | — | R-23 | новий |
| 531 | `ventilation/units/AHU-1/mode` | AHU-1 | P-08 | BACnet dev 130 MSV:1 (1 VE/2 VEL/3 AQ/4 REC/5 EA/6 SA/7 ST/8 Off) | MSV | 1…8 | — | 1 VE / 4 REC | — | R-23 | новий |
| 532 | `ventilation/units/AHU-1/state` | AHU-1 | P-08 | BACnet dev 130 BI:1 (в роботі), BI:2 (несправність → fault), BI:5 (захист від замерзання → frost) — складений стан (bms B.1) | BI | running/stopped/fault/frost | — | BI:1=1 | fault/frost → заявка | R-23 | новий |
| 533 | `ventilation/units/EF-ELEC/state` | EF-ELEC | P-08 | BACnet dev 131 BI:1 (в роботі) | BI | 0 stopped/1 running | — | за термостатом | — | R-23 | новий |
| 534 | `ventilation/units/EF-CMP/state` | EF-CMP | P-08 | BACnet dev 132 BI:1 (в роботі) | BI | 0 stopped/1 running | — | за термостатом | — | R-23 | новий |
| 535 | `ventilation/units/EF-CHG/state` | EF-CHG | P-08 | BACnet dev 133 BI:1 (в роботі), BI:7 (заряджання активне) → складений стан running/stopped/stopped_charging (bms B.2) | BI | running/stopped/stopped_charging | — | running | stopped_charging ≥ 60 с → тривога (bms A-20) | R-23 | новий |
| 536 | `lighting/groups/LT-RCV-1/level` | LT-RCV-1 | P-08 | HelvarNet LP-1 (router @1.1) група G:1 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 537 | `lighting/groups/LT-RCV-1/p_now` | LT-RCV-1 | P-08 | HelvarNet LP-1 >V:2,C:161,G:1# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 538 | `lighting/groups/LT-RCV-2/level` | LT-RCV-2 | P-08 | HelvarNet LP-1 (router @1.1) група G:2 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 539 | `lighting/groups/LT-RCV-2/p_now` | LT-RCV-2 | P-08 | HelvarNet LP-1 >V:2,C:161,G:2# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 540 | `lighting/groups/LT-RCV-3/level` | LT-RCV-3 | P-08 | HelvarNet LP-1 (router @1.1) група G:3 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 541 | `lighting/groups/LT-RCV-3/p_now` | LT-RCV-3 | P-08 | HelvarNet LP-1 >V:2,C:161,G:3# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 542 | `lighting/groups/LT-RCV-4/level` | LT-RCV-4 | P-08 | HelvarNet LP-1 (router @1.1) група G:4 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 543 | `lighting/groups/LT-RCV-4/p_now` | LT-RCV-4 | P-08 | HelvarNet LP-1 >V:2,C:161,G:4# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 544 | `lighting/groups/LT-RCV-5/level` | LT-RCV-5 | P-08 | HelvarNet LP-1 (router @1.1) група G:5 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 545 | `lighting/groups/LT-RCV-5/p_now` | LT-RCV-5 | P-08 | HelvarNet LP-1 >V:2,C:161,G:5# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 546 | `lighting/groups/LT-RCV-6/level` | LT-RCV-6 | P-08 | HelvarNet LP-1 (router @1.1) група G:6 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 547 | `lighting/groups/LT-RCV-6/p_now` | LT-RCV-6 | P-08 | HelvarNet LP-1 >V:2,C:161,G:6# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 548 | `lighting/groups/LT-RCV-7/level` | LT-RCV-7 | P-08 | HelvarNet LP-1 (router @1.1) група G:7 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 549 | `lighting/groups/LT-RCV-7/p_now` | LT-RCV-7 | P-08 | HelvarNet LP-1 >V:2,C:161,G:7# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 550 | `lighting/groups/LT-SHEETS/level` | LT-SHEETS | P-08 | HelvarNet LP-1 (router @1.1) група G:8 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 551 | `lighting/groups/LT-SHEETS/p_now` | LT-SHEETS | P-08 | HelvarNet LP-1 >V:2,C:161,G:8# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 552 | `lighting/groups/LT-HW/level` | LT-HW | P-08 | HelvarNet LP-1 (router @1.1) група G:9 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 553 | `lighting/groups/LT-HW/p_now` | LT-HW | P-08 | HelvarNet LP-1 >V:2,C:161,G:9# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 554 | `lighting/groups/LT-EDGE/level` | LT-EDGE | P-08 | HelvarNet LP-1 (router @1.1) група G:10 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 555 | `lighting/groups/LT-EDGE/p_now` | LT-EDGE | P-08 | HelvarNet LP-1 >V:2,C:161,G:10# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 556 | `lighting/groups/LT-PKS/level` | LT-PKS | P-08 | HelvarNet LP-1 (router @1.1) група G:11 — відповідь на >V:2,C:152,@1.1.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 557 | `lighting/groups/LT-PKS/p_now` | LT-PKS | P-08 | HelvarNet LP-1 >V:2,C:161,G:11# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 558 | `lighting/groups/LT-CUT/level` | LT-CUT | P-08 | HelvarNet LP-2 (router @1.2) група G:12 — відповідь на >V:2,C:152,@1.2.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 559 | `lighting/groups/LT-CUT/p_now` | LT-CUT | P-08 | HelvarNet LP-2 >V:2,C:161,G:12# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 560 | `lighting/groups/LT-EB/level` | LT-EB | P-08 | HelvarNet LP-2 (router @1.2) група G:13 — відповідь на >V:2,C:152,@1.2.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 561 | `lighting/groups/LT-EB/p_now` | LT-EB | P-08 | HelvarNet LP-2 >V:2,C:161,G:13# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 562 | `lighting/groups/LT-CNC/level` | LT-CNC | P-08 | HelvarNet LP-2 (router @1.2) група G:14 — відповідь на >V:2,C:152,@1.2.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 563 | `lighting/groups/LT-CNC/p_now` | LT-CNC | P-08 | HelvarNet LP-2 >V:2,C:161,G:14# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 564 | `lighting/groups/LT-SORT/level` | LT-SORT | P-08 | HelvarNet LP-2 (router @1.2) група G:15 — відповідь на >V:2,C:152,@1.2.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 565 | `lighting/groups/LT-SORT/p_now` | LT-SORT | P-08 | HelvarNet LP-2 >V:2,C:161,G:15# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 566 | `lighting/groups/LT-FAC/level` | LT-FAC | P-08 | HelvarNet LP-2 (router @1.2) група G:16 — відповідь на >V:2,C:152,@1.2.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 567 | `lighting/groups/LT-FAC/p_now` | LT-FAC | P-08 | HelvarNet LP-2 >V:2,C:161,G:16# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 568 | `lighting/groups/LT-ASM/level` | LT-ASM | P-08 | HelvarNet LP-3 (router @1.3) група G:17 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 569 | `lighting/groups/LT-ASM/p_now` | LT-ASM | P-08 | HelvarNet LP-3 >V:2,C:161,G:17# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 570 | `lighting/groups/LT-PRE/level` | LT-PRE | P-08 | HelvarNet LP-3 (router @1.3) група G:18 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 571 | `lighting/groups/LT-PRE/p_now` | LT-PRE | P-08 | HelvarNet LP-3 >V:2,C:161,G:18# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 572 | `lighting/groups/LT-MAINT/level` | LT-MAINT | P-08 | HelvarNet LP-3 (router @1.3) група G:19 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 573 | `lighting/groups/LT-MAINT/p_now` | LT-MAINT | P-08 | HelvarNet LP-3 >V:2,C:161,G:19# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 574 | `lighting/groups/LT-PACK/level` | LT-PACK | P-08 | HelvarNet LP-3 (router @1.3) група G:20 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 575 | `lighting/groups/LT-PACK/p_now` | LT-PACK | P-08 | HelvarNet LP-3 >V:2,C:161,G:20# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 576 | `lighting/groups/LT-POST/level` | LT-POST | P-08 | HelvarNet LP-3 (router @1.3) група G:21 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 577 | `lighting/groups/LT-POST/p_now` | LT-POST | P-08 | HelvarNet LP-3 >V:2,C:161,G:21# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 578 | `lighting/groups/LT-CMP/level` | LT-CMP | P-08 | HelvarNet LP-3 (router @1.3) група G:22 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 579 | `lighting/groups/LT-CMP/p_now` | LT-CMP | P-08 | HelvarNet LP-3 >V:2,C:161,G:22# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 580 | `lighting/groups/LT-CHG/level` | LT-CHG | P-08 | HelvarNet LP-3 (router @1.3) група G:23 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 581 | `lighting/groups/LT-CHG/p_now` | LT-CHG | P-08 | HelvarNet LP-3 >V:2,C:161,G:23# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 582 | `lighting/groups/LT-FG/level` | LT-FG | P-08 | HelvarNet LP-3 (router @1.3) група G:24 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 583 | `lighting/groups/LT-FG/p_now` | LT-FG | P-08 | HelvarNet LP-3 >V:2,C:161,G:24# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 584 | `lighting/groups/LT-ELEC/level` | LT-ELEC | P-08 | HelvarNet LP-3 (router @1.3) група G:25 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 585 | `lighting/groups/LT-ELEC/p_now` | LT-ELEC | P-08 | HelvarNet LP-3 >V:2,C:161,G:25# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 586 | `lighting/groups/LT-OUT-1/level` | LT-OUT-1 | P-08 | HelvarNet LP-3 (router @1.3) група G:26 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 587 | `lighting/groups/LT-OUT-1/p_now` | LT-OUT-1 | P-08 | HelvarNet LP-3 >V:2,C:161,G:26# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 588 | `lighting/groups/LT-OUT-2/level` | LT-OUT-2 | P-08 | HelvarNet LP-3 (router @1.3) група G:27 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 589 | `lighting/groups/LT-OUT-2/p_now` | LT-OUT-2 | P-08 | HelvarNet LP-3 >V:2,C:161,G:27# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 590 | `lighting/groups/LT-OUT-3/level` | LT-OUT-3 | P-08 | HelvarNet LP-3 (router @1.3) група G:28 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 591 | `lighting/groups/LT-OUT-3/p_now` | LT-OUT-3 | P-08 | HelvarNet LP-3 >V:2,C:161,G:28# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 592 | `lighting/groups/LT-OUT-4/level` | LT-OUT-4 | P-08 | HelvarNet LP-3 (router @1.3) група G:29 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 593 | `lighting/groups/LT-OUT-4/p_now` | LT-OUT-4 | P-08 | HelvarNet LP-3 >V:2,C:161,G:29# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 594 | `lighting/groups/LT-OUT-5/level` | LT-OUT-5 | P-08 | HelvarNet LP-3 (router @1.3) група G:30 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 595 | `lighting/groups/LT-OUT-5/p_now` | LT-OUT-5 | P-08 | HelvarNet LP-3 >V:2,C:161,G:30# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 596 | `lighting/groups/LT-OUT-6/level` | LT-OUT-6 | P-08 | HelvarNet LP-3 (router @1.3) група G:31 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 597 | `lighting/groups/LT-OUT-6/p_now` | LT-OUT-6 | P-08 | HelvarNet LP-3 >V:2,C:161,G:31# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 598 | `lighting/groups/LT-OUT-7/level` | LT-OUT-7 | P-08 | HelvarNet LP-3 (router @1.3) група G:32 — відповідь на >V:2,C:152,@1.3.1.<n># / push C:13 | int | % | ×1 | за розкладом DALI R-24 | — | R-24 освітлення | новий |
| 599 | `lighting/groups/LT-OUT-7/p_now` | LT-OUT-7 | P-08 | HelvarNet LP-3 >V:2,C:161,G:32# (Query Group Power Consumption) | int | Вт→кВт | ×0,001 | n·126 Вт·level | — | R-24 | новий |
| 600 | `lighting/panels/LP-1/state` | LP-1 | P-08 | HelvarNet router `@1.1.0.0` — агрегат роутера (bms A-17/R-34): `>V:2,C:102,@1#` + C:110 пристроїв груп щита за маскою 0x0800000E | state | ok/fault/offline | — | ok | — (заявки — за групами `…/faults`) | R-24 | новий |
| 601 | `lighting/panels/LP-2/state` | LP-2 | P-08 | HelvarNet router `@1.2.0.0` — агрегат роутера (bms A-17/R-34): `>V:2,C:102,@1#` + C:110 пристроїв груп щита за маскою 0x0800000E | state | ok/fault/offline | — | ok | — (заявки — за групами `…/faults`) | R-24 | новий |
| 602 | `lighting/panels/LP-3/state` | LP-3 | P-08 | HelvarNet router `@1.3.0.0` — агрегат роутера (bms A-17/R-34): `>V:2,C:102,@1#` + C:110 пристроїв груп щита за маскою 0x0800000E | state | ok/fault/offline | — | ok | — (заявки — за групами `…/faults`) | R-24 | новий |
| 603 | `fire/groups/FA-RCV-1/state` | FA-RCV-1 | P-09 | BACnet dev 200 LSZ:1 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 604 | `fire/groups/FA-RCV-2/state` | FA-RCV-2 | P-09 | BACnet dev 200 LSZ:2 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 605 | `fire/groups/FA-RCV-3/state` | FA-RCV-3 | P-09 | BACnet dev 200 LSZ:3 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 606 | `fire/groups/FA-RCV-4/state` | FA-RCV-4 | P-09 | BACnet dev 200 LSZ:4 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 607 | `fire/groups/FA-RCV-5/state` | FA-RCV-5 | P-09 | BACnet dev 200 LSZ:5 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 608 | `fire/groups/FA-RCV-6/state` | FA-RCV-6 | P-09 | BACnet dev 200 LSZ:6 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 609 | `fire/groups/FA-RCV-7/state` | FA-RCV-7 | P-09 | BACnet dev 200 LSZ:7 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 610 | `fire/groups/FA-SHEETS/state` | FA-SHEETS | P-09 | BACnet dev 200 LSZ:8 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 611 | `fire/groups/FA-HW/state` | FA-HW | P-09 | BACnet dev 200 LSZ:9 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 612 | `fire/groups/FA-EDGE/state` | FA-EDGE | P-09 | BACnet dev 200 LSZ:10 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 613 | `fire/groups/FA-PKS/state` | FA-PKS | P-09 | BACnet dev 200 LSZ:11 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 614 | `fire/groups/FA-CUT/state` | FA-CUT | P-09 | BACnet dev 200 LSZ:12 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 615 | `fire/groups/FA-EB/state` | FA-EB | P-09 | BACnet dev 200 LSZ:13 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 616 | `fire/groups/FA-CNC/state` | FA-CNC | P-09 | BACnet dev 200 LSZ:14 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 617 | `fire/groups/FA-SORT/state` | FA-SORT | P-09 | BACnet dev 200 LSZ:15 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 618 | `fire/groups/FA-FAC/state` | FA-FAC | P-09 | BACnet dev 200 LSZ:16 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 619 | `fire/groups/FA-ASM/state` | FA-ASM | P-09 | BACnet dev 200 LSZ:17 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 620 | `fire/groups/FA-PRE/state` | FA-PRE | P-09 | BACnet dev 200 LSZ:18 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 621 | `fire/groups/FA-MAINT/state` | FA-MAINT | P-09 | BACnet dev 200 LSZ:19 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 622 | `fire/groups/FA-PACK/state` | FA-PACK | P-09 | BACnet dev 200 LSZ:20 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 623 | `fire/groups/FA-POST/state` | FA-POST | P-09 | BACnet dev 200 LSZ:21 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 624 | `fire/groups/FA-CMP/state` | FA-CMP | P-09 | BACnet dev 200 LSZ:22 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 625 | `fire/groups/FA-CHG/state` | FA-CHG | P-09 | BACnet dev 200 LSZ:23 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 626 | `fire/groups/FA-FG/state` | FA-FG | P-09 | BACnet dev 200 LSZ:24 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 627 | `fire/groups/FA-ELEC/state` | FA-ELEC | P-09 | BACnet dev 200 LSZ:25 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 628 | `fire/groups/FA-OUT-1/state` | FA-OUT-1 | P-09 | BACnet dev 200 LSZ:26 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 629 | `fire/groups/FA-OUT-2/state` | FA-OUT-2 | P-09 | BACnet dev 200 LSZ:27 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 630 | `fire/groups/FA-OUT-3/state` | FA-OUT-3 | P-09 | BACnet dev 200 LSZ:28 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 631 | `fire/groups/FA-OUT-4/state` | FA-OUT-4 | P-09 | BACnet dev 200 LSZ:29 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 632 | `fire/groups/FA-OUT-5/state` | FA-OUT-5 | P-09 | BACnet dev 200 LSZ:30 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 633 | `fire/groups/FA-OUT-6/state` | FA-OUT-6 | P-09 | BACnet dev 200 LSZ:31 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 634 | `fire/groups/FA-OUT-7/state` | FA-OUT-7 | P-09 | BACnet dev 200 LSZ:32 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 635 | `fire/groups/FA-BOILER/state` | FA-BOILER | P-09 | BACnet dev 200 LSZ:33 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 636 | `fire/loops/1/state` | FACP-1 | P-09 | BACnet dev 200 BV:1 Present_Value (FACP-1_Loop1_Fault; несправність лінії, `fault(reason=loop)`) | BV | 0/1 | — | 0 | 1 → заявка | R-25 | новий |
| 637 | `fire/loops/2/state` | FACP-1 | P-09 | BACnet dev 200 BV:2 Present_Value (FACP-1_Loop2_Fault; несправність лінії, `fault(reason=loop)`) | BV | 0/1 | — | 0 | 1 → заявка | R-25 | новий |
| 638 | `fire/loops/3/state` | FACP-1 | P-09 | BACnet dev 200 BV:3 Present_Value (FACP-1_Loop3_Fault; несправність лінії, `fault(reason=loop)`) | BV | 0/1 | — | 0 | 1 → заявка | R-25 | новий |
| 639 | `fire/loops/4/state` | FACP-1 | P-09 | BACnet dev 200 BV:4 Present_Value (FACP-1_Loop4_Fault; несправність лінії, `fault(reason=loop)`) | BV | 0/1 | — | 0 | 1 → заявка | R-25 | новий |
| 640 | `fire/totals/state` | FACP-1 | P-09 | BACnet dev 200 LSZ:0 Present_Value (панель, зведений стан) | enum | quiet/alarm/fault/test | — | quiet | — | R-25 | новий |
| 641 | `fire/totals/alarms` | FACP-1 | P-09 | BACnet dev 200 PIV:1 Present_Value (кількість активних тривог) | PIV | шт | — | 0 | > 0 → подія | R-25 | новий |
| 642 | `fire/totals/faults` | FACP-1 | P-09 | BACnet dev 200 PIV:2 Present_Value (кількість несправностей) | PIV | шт | — | 0 | > 0 → заявка | R-25 | новий |
| 643 | `fire/totals/disabled` | FACP-1 | P-09 | BACnet dev 200 PIV:3 Present_Value (вимкнених пристроїв) | PIV | шт | — | 0 | — | R-25 | новий |
| 644 | `fire/spark/SPARK-1/state` | SPARK-1 | P-09 | Modbus u85 fc2 pdu0 bool · ADAM-6050 DI0 00001 (іскра виявлена; DI1–DI3 — рядки 684–686) | bit | 0/1 | — | 0 | 1 → подія | R-26 іскрогасіння | новий |
| 645 | `fire/spark/SPARK-1/count_today` | SPARK-1 | P-09 | Modbus u85 fc3 pdu0+2 u32 little · ADAM-6050 40001–40002 лічильник DI0, молодше слово першим | U32 | шт | ×1 | 1 | — | R-26 | новий |
| 646 | `fire/smoke/SMOKE-VENTS/state` | SMOKE-CTRL | P-09 | Modbus u85 fc2 pdu4 bool · ADAM-6050 DI4 00005 (клапани відкриті; DI5/DI6 — рядки 687–688; DO0 — §8.11.3) | bit | 0/1 | — | 0 (закриті) | — | R-27 димовидалення | новий |
| 647 | `access/readers/ACR-IN/last_event` | ACR-IN | P-10 | POST /api/events/search (device_id.id = id зчитувача) → rows[0].event_type_id.code, user_id.user_id, datetime | event | код BioStar (4102 Verify success — card, 4867 Identify success — face, 6400 Access denied…) | — | — | 6400 Access denied → подія | R-28 відмітки за зміною | новий |
| 648 | `access/readers/ACR-ELEC/last_event` | ACR-ELEC | P-10 | POST /api/events/search (device_id.id = id зчитувача) → rows[0].event_type_id.code, user_id.user_id, datetime | event | код BioStar (4102 Verify success — card, 4867 Identify success — face, 6400 Access denied…) | — | — | 6400 Access denied → подія | R-28 відмітки за зміною | новий |
| 649 | `access/readers/ACR-CHG/last_event` | ACR-CHG | P-10 | POST /api/events/search (device_id.id = id зчитувача) → rows[0].event_type_id.code, user_id.user_id, datetime | event | код BioStar (4102 Verify success — card, 4867 Identify success — face, 6400 Access denied…) | — | — | 6400 Access denied → подія | R-28 відмітки за зміною | новий |
| 650 | `access/readers/ACR-PAINT/last_event` | ACR-PAINT | P-10 | POST /api/events/search (device_id.id = id зчитувача) → rows[0].event_type_id.code, user_id.user_id, datetime | event | код BioStar (4102 Verify success — card, 4867 Identify success — face, 6400 Access denied…) | — | — | 6400 Access denied → подія | R-28 відмітки за зміною | новий |
| 651 | `access/readers/ACR-SRV/last_event` | ACR-SRV | P-10 | POST /api/events/search (device_id.id = id зчитувача) → rows[0].event_type_id.code, user_id.user_id, datetime | event | код BioStar (4102 Verify success — card, 4867 Identify success — face, 6400 Access denied…) | — | — | 6400 Access denied → подія | R-28 відмітки за зміною | новий |
| 652 | `access/turnstiles/TURNSTILES/on_site` | TURNSTILES | P-10 | розрахунок із подій ACR-IN: входи − виходи за добу | int | осіб | — | 35 (зміна 1) | — | R-28 | новий |
| 653 | `access/events` | ACCESS | P-10 | POST /api/events/search (усі пристрої, datetime BETWEEN) | event[] | — | — | — | — | R-28 | новий |
| 654 | `yard/gates/GATE-W/state` | GATE-W | P-11 | Modbus u86 fc2 pdu0 bool · ADAM-6060 DI0 00001 (стріла відкрита; петля, фотоелемент, команди — рядки 689–693) | bit | 0/1 | — | 0 (закрито) | відкрито > 10 хв → warn | R-29 двір | новий |
| 655 | `yard/gates/GATE-W/passes_today` | GATE-W | P-11 | Modbus u86 fc3 pdu2+2 u32 little · ADAM-6060 40003–40004 лічильник DI1, молодше слово першим | U32 | шт | ×1 | 7 / 6 | — | R-29 | новий |
| 656 | `yard/gates/GATE-E/state` | GATE-E | P-11 | Modbus u86 fc2 pdu2 bool · ADAM-6060 DI2 00003 (стріла відкрита; петля, фотоелемент, команди — рядки 694–698) | bit | 0/1 | — | 0 (закрито) | відкрито > 10 хв → warn | R-29 двір | новий |
| 657 | `yard/gates/GATE-E/passes_today` | GATE-E | P-11 | Modbus u86 fc3 pdu6+2 u32 little · ADAM-6060 40007–40008 лічильник DI3, молодше слово першим | U32 | шт | ×1 | 7 / 6 | — | R-29 | новий |
| 658 | `yard/lpr/CAM-05/plate` | CAM-05 | P-11 | HTTP POST <collector>/f3d/lpr → plateText, plateCountry, carState; час — capture_timestamp (мс UTC) (камера GATE-W) | event | — | — | — | номер без броні → сценарій truck_no_booking | R-29 | новий |
| 659 | `yard/lpr/CAM-06/plate` | CAM-06 | P-11 | HTTP POST <collector>/f3d/lpr → plateText, plateCountry, carState; час — capture_timestamp (мс UTC) (камера GATE-E) | event | — | — | — | номер без броні → сценарій truck_no_booking | R-29 | новий |
| 660 | `yard/scale/TRUCK-SCALE/weight_kg` | TRUCK-SCALE | P-11 | SICS TCP :4001 «SI» → «S S  21380 kg» / «SIR» потік | number | кг | ×1 (дискретність 20 кг) | 0 без машини | > 60 000 → «S +» | R-30 автоваги | новий |
| 661 | `yard/scale/TRUCK-SCALE/stable` | TRUCK-SCALE | P-11 | SICS статус «S» (стабільно) / «D» (динамічно) | bit | 0/1 | — | 1 | — | R-30 | новий |
| 662 | `infra/genset/GENSET/state` | GENSET | P-12 | API ретранслятора SmartGen (td_genset relay_api.md), профіль D700 | — | — | — | резерв | — | td_genset | новий |
| 663 | `energy/consumers/OFFICE/p_now` | OFFICE | P-05 | Modbus u51 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 17.6 (cos φ 0.92) | — | noise (R-01) | новий |
| 664 | `energy/consumers/OFFICE/kwh_shift` | OFFICE | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 61.6 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | новий |
| 665 | `energy/consumers/LP-1/p_now` | LP-1 | P-05 | Modbus u52 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 5.6 (cos φ 0.95) | — | R-24 (Σ груп щита) | новий |
| 666 | `energy/consumers/LP-1/kwh_shift` | LP-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 19.6 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | новий |
| 667 | `energy/consumers/LP-2/p_now` | LP-2 | P-05 | Modbus u53 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 23.2 (cos φ 0.95) | — | R-24 (Σ груп щита) | новий |
| 668 | `energy/consumers/LP-2/kwh_shift` | LP-2 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 81.2 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | новий |
| 669 | `energy/consumers/LP-3/p_now` | LP-3 | P-05 | Modbus u54 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 9.5 (cos φ 0.95) | — | R-24 (Σ груп щита) | новий |
| 670 | `energy/consumers/LP-3/kwh_shift` | LP-3 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 33.2 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | новий |
| 671 | `energy/consumers/RV-ALL/p_now` | RV-ALL | P-05 | Modbus u55 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 82.9 (cos φ 0.95) | — | R-23 (Σ `p_now` RV-01…RV-25) | новий |
| 672 | `energy/consumers/RV-ALL/kwh_shift` | RV-ALL | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 290.1 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | новий |
| 673 | `energy/consumers/AHU-1/p_now` | AHU-1 | P-05 | Modbus u56 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 9.3 (cos φ 0.95) | — | R-23 | новий |
| 674 | `energy/consumers/AHU-1/kwh_shift` | AHU-1 | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 32.6 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | новий |
| 675 | `energy/consumers/EF-ELEC/p_now` | EF-ELEC | P-05 | Modbus u57 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.84 (cos φ 0.95) | — | R-23 | новий |
| 676 | `energy/consumers/EF-ELEC/kwh_shift` | EF-ELEC | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 2.9 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | новий |
| 677 | `energy/consumers/EF-CMP/p_now` | EF-CMP | P-05 | Modbus u58 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.0 (cos φ 0.95) | — | R-23 | новий |
| 678 | `energy/consumers/EF-CMP/kwh_shift` | EF-CMP | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 0.0 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | новий |
| 679 | `energy/consumers/EF-CHG/p_now` | EF-CHG | P-05 | Modbus u59 fc3 pdu3059+2 f32 · PM5560 3060–3061 Active Power Total | F32 | кВт | ×1 | 0.107 (cos φ 0.95) | — | R-23 | новий |
| 680 | `energy/consumers/EF-CHG/kwh_shift` | EF-CHG | — | обчислює energy (R-11, `EN-DERIVED`) — без адреси (X-35) | number | кВт·год | — | 0.4 | — | обчислює energy (R-03 емулятора — лише внутрішня величина) | новий |
| 681 | `fire/totals/system_state` | FACP-1 | P-09 | BACnet dev 200 MSV:1 Present_Value (FACP-1_SystemState) | MSV | 1 normal/2 alarm/3 fault/4 test/5 disabled | — | 1 | — | R-25 | новий |
| 682 | `fire/totals/sounders_active` | FACP-1 | P-09 | BACnet dev 200 BV:10 Present_Value (FACP-1_SoundersActive) | BV | 0/1 | — | 0 | — | R-25 | новий |
| 683 | `fire/totals/brigade` | FACP-1 | P-09 | BACnet dev 200 BV:11 Present_Value (FACP-1_FireBrigadeTransmitted) | BV | 0/1 | — | 0 | — | R-25 | новий |
| 684 | `fire/spark/SPARK-1/extinguishing` | SPARK-1 | P-09 | Modbus u85 fc2 pdu1 bool · ADAM-6050 DI1 00002 (гасіння активне) | bit | 0/1 | — | 0 | — | R-26 | новий |
| 685 | `fire/spark/SPARK-1/fault` | SPARK-1 | P-09 | Modbus u85 fc2 pdu2 bool · ADAM-6050 DI2 00003 (несправність іскрогасіння) | bit | 0/1 | — | 0 | 1 → заявка | R-26 | новий |
| 686 | `fire/spark/SPARK-1/water_ok` | SPARK-1 | P-09 | Modbus u85 fc2 pdu3 bool · ADAM-6050 DI3 00004 (тиск води гасіння в нормі) | bit | 0 low/1 ok | — | 1 | 0 → заявка | R-26 | новий |
| 687 | `fire/smoke/SMOKE-CTRL/fault` | SMOKE-CTRL | P-09 | Modbus u85 fc2 pdu5 bool · ADAM-6050 DI5 00006 (несправність щита D+H) | bit | 0 ok/1 fault | — | 0 | 1 → заявка | R-27 | новий |
| 688 | `fire/smoke/SMOKE-CTRL/battery` | SMOKE-CTRL | P-09 | Modbus u85 fc2 pdu6 bool · ADAM-6050 DI6 00007 (щит на живленні від АКБ) | bit | 0 mains/1 battery | — | 0 (1 під час `blackout`) | — | R-27 | новий |
| 689 | `yard/gates/GATE-W/loop` | GATE-W | P-11 | Modbus u86 fc2 pdu1 bool · ADAM-6060 DI1 00002 (індукційна петля) | bit | 0/1 | — | 0 | — | R-29 | новий |
| 690 | `yard/gates/GATE-W/photocell` | GATE-W | P-11 | Modbus u86 fc2 pdu4 bool · ADAM-6060 DI4 00005 (фотоелемент перешкоди) | bit | 0/1 | — | 0 | — | R-29 | новий |
| 691 | `yard/gates/GATE-W/cmd_open` | GATE-W | P-11 | Modbus u86 fc1 pdu16 bool, запис fc5 pdu16 · ADAM-6060 DO0 00017 «відкрити» (імпульс ≥ 1 с); лише `write_enabled` споживача | bit | 0/1 | — | 0 | — | R-29 | новий |
| 692 | `yard/gates/GATE-W/cmd_close` | GATE-W | P-11 | Modbus u86 fc1 pdu18 bool, запис fc5 pdu18 · ADAM-6060 DO2 00019 «закрити примусово»; лише `write_enabled` споживача | bit | 0/1 | — | 0 | — | R-29 | новий |
| 693 | `yard/gates/GATE-W/cmd_hold` | GATE-W | P-11 | Modbus u86 fc1 pdu20 bool, запис fc5 pdu20 · ADAM-6060 DO4 00021 «тримати відкритим» (окремий канал на ворота, X-47); лише `write_enabled` споживача | bit | 0/1 | — | 0 | — | R-25 / R-29 | новий |
| 694 | `yard/gates/GATE-E/loop` | GATE-E | P-11 | Modbus u86 fc2 pdu3 bool · ADAM-6060 DI3 00004 (індукційна петля) | bit | 0/1 | — | 0 | — | R-29 | новий |
| 695 | `yard/gates/GATE-E/photocell` | GATE-E | P-11 | Modbus u86 fc2 pdu5 bool · ADAM-6060 DI5 00006 (фотоелемент перешкоди) | bit | 0/1 | — | 0 | — | R-29 | новий |
| 696 | `yard/gates/GATE-E/cmd_open` | GATE-E | P-11 | Modbus u86 fc1 pdu17 bool, запис fc5 pdu17 · ADAM-6060 DO1 00018 «відкрити» (імпульс ≥ 1 с); лише `write_enabled` споживача | bit | 0/1 | — | 0 | — | R-29 | новий |
| 697 | `yard/gates/GATE-E/cmd_close` | GATE-E | P-11 | Modbus u86 fc1 pdu19 bool, запис fc5 pdu19 · ADAM-6060 DO3 00020 «закрити примусово»; лише `write_enabled` споживача | bit | 0/1 | — | 0 | — | R-29 | новий |
| 698 | `yard/gates/GATE-E/cmd_hold` | GATE-E | P-11 | Modbus u86 fc1 pdu21 bool, запис fc5 pdu21 · ADAM-6060 DO5 00022 «тримати відкритим» (окремий канал на ворота, X-47); лише `write_enabled` споживача | bit | 0/1 | — | 0 | — | R-25 / R-29 | новий |
| 699 | `energy/consumers/SAW-1/kwh_total` | SAW-1 | P-05 | Modbus u11 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 700 | `energy/consumers/SAW-2/kwh_total` | SAW-2 | P-05 | Modbus u12 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 701 | `energy/consumers/SAW-3/kwh_total` | SAW-3 | P-05 | Modbus u13 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 702 | `energy/consumers/SLIDE-1/kwh_total` | SLIDE-1 | P-05 | Modbus u14 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 703 | `energy/consumers/VSAW-1/kwh_total` | VSAW-1 | P-05 | Modbus u15 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 704 | `energy/consumers/NEST-1/kwh_total` | NEST-1 | P-05 | Modbus u16 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 705 | `energy/consumers/EDGE-1/kwh_total` | EDGE-1 | P-05 | Modbus u17 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 706 | `energy/consumers/EDGE-2/kwh_total` | EDGE-2 | P-05 | Modbus u18 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 707 | `energy/consumers/EDGE-3/kwh_total` | EDGE-3 | P-05 | Modbus u19 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 708 | `energy/consumers/CNC-3/kwh_total` | CNC-3 | P-05 | Modbus u20 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 709 | `energy/consumers/CNC-1/kwh_total` | CNC-1 | P-05 | Modbus u21 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 710 | `energy/consumers/CNC-2/kwh_total` | CNC-2 | P-05 | Modbus u22 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 711 | `energy/consumers/BORE-1/kwh_total` | BORE-1 | P-05 | Modbus u23 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 712 | `energy/consumers/CNC-4/kwh_total` | CNC-4 | P-05 | Modbus u24 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 713 | `energy/consumers/DOWEL-1/kwh_total` | DOWEL-1 | P-05 | Modbus u25 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 714 | `energy/consumers/SORT-1/kwh_total` | SORT-1 | P-05 | Modbus u26 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 715 | `energy/consumers/SAND-1/kwh_total` | SAND-1 | P-05 | Modbus u27 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 716 | `energy/consumers/AUTOSPRAY-1/kwh_total` | AUTOSPRAY-1 | P-05 | Modbus u28 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 717 | `energy/consumers/UV-1/kwh_total` | UV-1 | P-05 | Modbus u29 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 718 | `energy/consumers/HINGE-1/kwh_total` | HINGE-1 | P-05 | Modbus u30 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 719 | `energy/consumers/GLUE-1/kwh_total` | GLUE-1 | P-05 | Modbus u31 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 720 | `energy/consumers/PRESS-1/kwh_total` | PRESS-1 | P-05 | Modbus u32 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 721 | `energy/consumers/SPRAY-1/kwh_total` | SPRAY-1 | P-05 | Modbus u33 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 722 | `energy/consumers/DRY-1/kwh_total` | DRY-1 | P-05 | Modbus u34 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 723 | `energy/consumers/ASMLINE-1/kwh_total` | ASMLINE-1 | P-05 | Modbus u35 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 724 | `energy/consumers/ASM-1/kwh_total` | ASM-1 | P-05 | Modbus u36 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 725 | `energy/consumers/ASM-2/kwh_total` | ASM-2 | P-05 | Modbus u37 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 726 | `energy/consumers/ASM-3/kwh_total` | ASM-3 | P-05 | Modbus u38 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 727 | `energy/consumers/ASM-4/kwh_total` | ASM-4 | P-05 | Modbus u39 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 728 | `energy/consumers/ASM-5/kwh_total` | ASM-5 | P-05 | Modbus u40 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 729 | `energy/consumers/ASM-6/kwh_total` | ASM-6 | P-05 | Modbus u41 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 730 | `energy/consumers/PACK-1/kwh_total` | PACK-1 | P-05 | Modbus u42 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 731 | `energy/consumers/PACK-2/kwh_total` | PACK-2 | P-05 | Modbus u43 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 732 | `energy/consumers/BOX-1/kwh_total` | BOX-1 | P-05 | Modbus u44 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 733 | `energy/consumers/PACKLINE-1/kwh_total` | PACKLINE-1 | P-05 | Modbus u45 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 734 | `energy/consumers/GANTRY-1/kwh_total` | GANTRY-1 | P-05 | Modbus u46 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 735 | `energy/consumers/COMPRESSOR/kwh_total` | COMPRESSOR | P-05 | Modbus u47 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 736 | `energy/consumers/DUST-1/kwh_total` | DUST-1 | P-05 | Modbus u48 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 737 | `energy/consumers/BOILER/kwh_total` | BOILER | P-05 | Modbus u49 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 738 | `energy/consumers/CHARGING/kwh_total` | CHARGING | P-05 | Modbus u50 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 739 | `energy/consumers/OFFICE/kwh_total` | OFFICE | P-05 | Modbus u51 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 740 | `energy/consumers/LP-1/kwh_total` | LP-1 | P-05 | Modbus u52 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 741 | `energy/consumers/LP-2/kwh_total` | LP-2 | P-05 | Modbus u53 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 742 | `energy/consumers/LP-3/kwh_total` | LP-3 | P-05 | Modbus u54 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 743 | `energy/consumers/RV-ALL/kwh_total` | RV-ALL | P-05 | Modbus u55 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 744 | `energy/consumers/AHU-1/kwh_total` | AHU-1 | P-05 | Modbus u56 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 745 | `energy/consumers/EF-ELEC/kwh_total` | EF-ELEC | P-05 | Modbus u57 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 746 | `energy/consumers/EF-CMP/kwh_total` | EF-CMP | P-05 | Modbus u58 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 747 | `energy/consumers/EF-CHG/kwh_total` | EF-CHG | P-05 | Modbus u59 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | energy (R-03 інтеграл потужності) | новий |
| 748 | `energy/cells/Q1/i_a` | Q1 | P-05 | Modbus u1 fc3 pdu2999+2 f32 · PM5560 3000–3001 Current A | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 749 | `energy/cells/Q1/i_b` | Q1 | P-05 | Modbus u1 fc3 pdu3001+2 f32 · PM5560 3002–3003 Current B | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 750 | `energy/cells/Q1/i_c` | Q1 | P-05 | Modbus u1 fc3 pdu3003+2 f32 · PM5560 3004–3005 Current C | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 751 | `energy/cells/Q1/q_kvar` | Q1 | P-05 | Modbus u1 fc3 pdu3067+2 f32 · PM5560 3068–3069 Reactive Power Total | F32 | квар | ×1 | P·tan(acos cos φ) | — | R-01 | новий |
| 752 | `energy/cells/Q1/kwh_total` | Q1 | P-05 | Modbus u1 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | R-03 | новий |
| 753 | `energy/cells/Q1/kwh_export` | Q1 | P-05 | Modbus u1 fc3 pdu3207+4 i64 · PM5560 3208–3211 Active Energy Received (Out of Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | 0 (> 0 лише при експорті) | — | R-13 | новий |
| 754 | `energy/cells/Q1/state` | Q1 | P-05 | Modbus u1 fc3 pdu2017 u16 · PM5560 2018 Breaker state (ПРИПУЩЕННЯ, §8.7.1) | U16 | 0 open/1 closed/2 tripped | — | 1 | 2 tripped → заявка | R-15 / R-22 | новий |
| 755 | `energy/cells/Q2/i_a` | Q2 | P-05 | Modbus u2 fc3 pdu2999+2 f32 · PM5560 3000–3001 Current A | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 756 | `energy/cells/Q2/i_b` | Q2 | P-05 | Modbus u2 fc3 pdu3001+2 f32 · PM5560 3002–3003 Current B | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 757 | `energy/cells/Q2/i_c` | Q2 | P-05 | Modbus u2 fc3 pdu3003+2 f32 · PM5560 3004–3005 Current C | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 758 | `energy/cells/Q2/q_kvar` | Q2 | P-05 | Modbus u2 fc3 pdu3067+2 f32 · PM5560 3068–3069 Reactive Power Total | F32 | квар | ×1 | P·tan(acos cos φ) | — | R-01 | новий |
| 759 | `energy/cells/Q2/kwh_total` | Q2 | P-05 | Modbus u2 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | R-03 | новий |
| 760 | `energy/cells/Q2/kwh_export` | Q2 | P-05 | Modbus u2 fc3 pdu3207+4 i64 · PM5560 3208–3211 Active Energy Received (Out of Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | 0 (> 0 лише при експорті) | — | R-13 | новий |
| 761 | `energy/cells/Q2/state` | Q2 | P-05 | Modbus u2 fc3 pdu2017 u16 · PM5560 2018 Breaker state (ПРИПУЩЕННЯ, §8.7.1) | U16 | 0 open/1 closed/2 tripped | — | 1 | 2 tripped → заявка | R-15 / R-22 | новий |
| 762 | `energy/lines/BW-1/i_a` | QF-1 | P-05 | Modbus u3 fc3 pdu2999+2 f32 · PM5560 3000–3001 Current A | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 763 | `energy/lines/BW-1/i_b` | QF-1 | P-05 | Modbus u3 fc3 pdu3001+2 f32 · PM5560 3002–3003 Current B | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 764 | `energy/lines/BW-1/i_c` | QF-1 | P-05 | Modbus u3 fc3 pdu3003+2 f32 · PM5560 3004–3005 Current C | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 765 | `energy/lines/BW-1/kwh_total` | QF-1 | P-05 | Modbus u3 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | R-03 | новий |
| 766 | `energy/lines/BW-1/state` | QF-1 | P-05 | Modbus u3 fc3 pdu2017 u16 · PM5560 2018 Breaker state (ПРИПУЩЕННЯ, §8.7.1) | U16 | 0 open/1 closed/2 tripped | — | 1 | 2 tripped → заявка | R-15 / R-22 | новий |
| 767 | `energy/lines/BW-2/i_a` | QF-2 | P-05 | Modbus u4 fc3 pdu2999+2 f32 · PM5560 3000–3001 Current A | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 768 | `energy/lines/BW-2/i_b` | QF-2 | P-05 | Modbus u4 fc3 pdu3001+2 f32 · PM5560 3002–3003 Current B | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 769 | `energy/lines/BW-2/i_c` | QF-2 | P-05 | Modbus u4 fc3 pdu3003+2 f32 · PM5560 3004–3005 Current C | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 770 | `energy/lines/BW-2/kwh_total` | QF-2 | P-05 | Modbus u4 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | R-03 | новий |
| 771 | `energy/lines/BW-2/state` | QF-2 | P-05 | Modbus u4 fc3 pdu2017 u16 · PM5560 2018 Breaker state (ПРИПУЩЕННЯ, §8.7.1) | U16 | 0 open/1 closed/2 tripped | — | 1 | 2 tripped → заявка | R-15 / R-22 | новий |
| 772 | `energy/lines/BW-3/i_a` | QF-3 | P-05 | Modbus u5 fc3 pdu2999+2 f32 · PM5560 3000–3001 Current A | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 773 | `energy/lines/BW-3/i_b` | QF-3 | P-05 | Modbus u5 fc3 pdu3001+2 f32 · PM5560 3002–3003 Current B | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 774 | `energy/lines/BW-3/i_c` | QF-3 | P-05 | Modbus u5 fc3 pdu3003+2 f32 · PM5560 3004–3005 Current C | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 775 | `energy/lines/BW-3/kwh_total` | QF-3 | P-05 | Modbus u5 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | R-03 | новий |
| 776 | `energy/lines/BW-3/state` | QF-3 | P-05 | Modbus u5 fc3 pdu2017 u16 · PM5560 2018 Breaker state (ПРИПУЩЕННЯ, §8.7.1) | U16 | 0 open/1 closed/2 tripped | — | 1 | 2 tripped → заявка | R-15 / R-22 | новий |
| 777 | `energy/lines/BW-4/i_a` | QF-4 | P-05 | Modbus u6 fc3 pdu2999+2 f32 · PM5560 3000–3001 Current A | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 778 | `energy/lines/BW-4/i_b` | QF-4 | P-05 | Modbus u6 fc3 pdu3001+2 f32 · PM5560 3002–3003 Current B | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 779 | `energy/lines/BW-4/i_c` | QF-4 | P-05 | Modbus u6 fc3 pdu3003+2 f32 · PM5560 3004–3005 Current C | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 780 | `energy/lines/BW-4/kwh_total` | QF-4 | P-05 | Modbus u6 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | R-03 | новий |
| 781 | `energy/lines/BW-4/state` | QF-4 | P-05 | Modbus u6 fc3 pdu2017 u16 · PM5560 2018 Breaker state (ПРИПУЩЕННЯ, §8.7.1) | U16 | 0 open/1 closed/2 tripped | — | 1 | 2 tripped → заявка | R-15 / R-22 | новий |
| 782 | `energy/lines/C1/i_a` | QF-C1 | P-05 | Modbus u7 fc3 pdu2999+2 f32 · PM5560 3000–3001 Current A | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 783 | `energy/lines/C1/i_b` | QF-C1 | P-05 | Modbus u7 fc3 pdu3001+2 f32 · PM5560 3002–3003 Current B | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 784 | `energy/lines/C1/i_c` | QF-C1 | P-05 | Modbus u7 fc3 pdu3003+2 f32 · PM5560 3004–3005 Current C | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 785 | `energy/lines/C1/kwh_total` | QF-C1 | P-05 | Modbus u7 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | R-03 | новий |
| 786 | `energy/lines/C1/state` | QF-C1 | P-05 | Modbus u7 fc3 pdu2017 u16 · PM5560 2018 Breaker state (ПРИПУЩЕННЯ, §8.7.1) | U16 | 0 open/1 closed/2 tripped | — | 1 | 2 tripped → заявка | R-15 / R-22 | новий |
| 787 | `energy/lines/C2/i_a` | QF-C2 | P-05 | Modbus u8 fc3 pdu2999+2 f32 · PM5560 3000–3001 Current A | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 788 | `energy/lines/C2/i_b` | QF-C2 | P-05 | Modbus u8 fc3 pdu3001+2 f32 · PM5560 3002–3003 Current B | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 789 | `energy/lines/C2/i_c` | QF-C2 | P-05 | Modbus u8 fc3 pdu3003+2 f32 · PM5560 3004–3005 Current C | F32 | А | ×1 | ≈ `i_now` ± 3 % | — | R-01 | новий |
| 790 | `energy/lines/C2/kwh_total` | QF-C2 | P-05 | Modbus u8 fc3 pdu3203+4 i64 · PM5560 3204–3207 Active Energy Delivered (Into Load), Вт·год | I64 | Вт·год→кВт·год | ×0,001 | накопич. | — | R-03 | новий |
| 791 | `energy/lines/C2/state` | QF-C2 | P-05 | Modbus u8 fc3 pdu2017 u16 · PM5560 2018 Breaker state (ПРИПУЩЕННЯ, §8.7.1) | U16 | 0 open/1 closed/2 tripped | — | 1 | 2 tripped → заявка | R-15 / R-22 | новий |
| 792 | `infra/pv/PV-INV-1/kwh_total` | PV-INV | P-07 | Modbus u61 fc3 pdu32106+2 u32 · SUN2000 32106–32107 Accumulated energy yield | U32 | кВт·год | ×0,01 | накопич. | — | R-11 | новий |
| 793 | `infra/pv/PV-INV-2/kwh_total` | PV-INV | P-07 | Modbus u62 fc3 pdu32106+2 u32 · SUN2000 32106–32107 Accumulated energy yield | U32 | кВт·год | ×0,01 | накопич. | — | R-11 | новий |
| 794 | `infra/pv/PV-INV-3/kwh_total` | PV-INV | P-07 | Modbus u63 fc3 pdu32106+2 u32 · SUN2000 32106–32107 Accumulated energy yield | U32 | кВт·год | ×0,01 | накопич. | — | R-11 | новий |
| 795 | `infra/pv/PV-INV-4/kwh_total` | PV-INV | P-07 | Modbus u64 fc3 pdu32106+2 u32 · SUN2000 32106–32107 Accumulated energy yield | U32 | кВт·год | ×0,01 | накопич. | — | R-11 | новий |
| 796 | `infra/pv/PV-INV-5/kwh_total` | PV-INV | P-07 | Modbus u65 fc3 pdu32106+2 u32 · SUN2000 32106–32107 Accumulated energy yield | U32 | кВт·год | ×0,01 | накопич. | — | R-11 | новий |
| 797 | `infra/pv/PV-INV-6/kwh_total` | PV-INV | P-07 | Modbus u66 fc3 pdu32106+2 u32 · SUN2000 32106–32107 Accumulated energy yield | U32 | кВт·год | ×0,01 | накопич. | — | R-11 | новий |
| 798 | `infra/pv/PV-INV-7/kwh_total` | PV-INV | P-07 | Modbus u67 fc3 pdu32106+2 u32 · SUN2000 32106–32107 Accumulated energy yield | U32 | кВт·год | ×0,01 | накопич. | — | R-11 | новий |
| 799 | `infra/pv/PV-INV-8/kwh_total` | PV-INV | P-07 | Modbus u68 fc3 pdu32106+2 u32 · SUN2000 32106–32107 Accumulated energy yield | U32 | кВт·год | ×0,01 | накопич. | — | R-11 | новий |
| 800 | `infra/bess/kwh_charge_total` | BESS | P-07 | Modbus u69 fc3 pdu37014+2 u32 · LUNA2000 37014–37015 Total charge (ПРИПУЩЕННЯ, §8.9.2) | U32 | кВт·год | ×0,01 | накопич. | — | R-13 | новий |
| 801 | `infra/bess/kwh_discharge_total` | BESS | P-07 | Modbus u69 fc3 pdu37016+2 u32 · LUNA2000 37016–37017 Total discharge (ПРИПУЩЕННЯ, §8.9.2) | U32 | кВт·год | ×0,01 | накопич. | — | R-13 | новий |
| 802 | `infra/chp/kwh_total` | CHP | P-07 | Modbus u72 fc3 pdu40014+2 u32 · TEDOM 40014–40015 Energy produced total (ПРИПУЩЕННЯ) | U32 | кВт·год | ×1 | накопич. | — | R-12 | новий |
| 803 | `infra/ats/mode` | ATS-1 | P-07 | Modbus u71 fc3 pdu20482 u16 · ATyS p Annexe III 20482 Operating Mode | U16 | 0 manual/1 locked/16 auto/32 remote/64 inhibit | — | 32 remote (`amf_master=hgm`) / 16 auto (`ats`) | — | R-22 | новий |
| 804 | `infra/ats/gen_start` | ATS-1 | P-07 | Modbus u71 fc3 pdu20484 u16 · ATyS p Annexe III 20484 Source 2 Start Generator relay State | U16 | 0 off/1 on | — | 0 | — | R-22 | новий |
| 805 | `infra/ats/src1_state` | ATS-1 | P-07 | Modbus u71 fc3 pdu20486 u16 · ATyS p Annexe III 20486 Source 1 State | U16 | 0 under threshold/1 present/2 available | — | 2 | — | R-22 | новий |
| 806 | `infra/ats/src2_state` | ATS-1 | P-07 | Modbus u71 fc3 pdu20487 u16 · ATyS p Annexe III 20487 Source 2 State | U16 | 0 under threshold/1 present/2 available | — | 0 | — | R-22 | новий |
| 807 | `infra/ats/fail_start` | ATS-1 | — | обчислює energy (R-14 п. 5, FAIL START) — без адреси (X-35) | number | 0/1 | — | 0 | 1 → заявка (energy C.2) | обчислює energy (R-22 емулятора — подія «FAIL START») | новий |
| 808 | `workcenters/SAW-1/event` | SAW-1 | P-01 | ns=2;s=SAW-1.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 809 | `workcenters/SAW-1/job_cmd` | SAW-1 | P-01 | ns=2;s=SAW-1.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 810 | `workcenters/SAW-2/event` | SAW-2 | P-01 | ns=2;s=SAW-2.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 811 | `workcenters/SAW-2/job_cmd` | SAW-2 | P-01 | ns=2;s=SAW-2.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 812 | `workcenters/SAW-3/event` | SAW-3 | P-01 | ns=2;s=SAW-3.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 813 | `workcenters/SAW-3/job_cmd` | SAW-3 | P-01 | ns=2;s=SAW-3.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 814 | `workcenters/NEST-1/event` | NEST-1 | P-01 | ns=2;s=NEST-1.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 815 | `workcenters/NEST-1/job_cmd` | NEST-1 | P-01 | ns=2;s=NEST-1.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 816 | `workcenters/EDGE-1/event` | EDGE-1 | P-01 | ns=2;s=EDGE-1.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 817 | `workcenters/EDGE-1/job_cmd` | EDGE-1 | P-01 | ns=2;s=EDGE-1.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 818 | `workcenters/EDGE-2/event` | EDGE-2 | P-01 | ns=2;s=EDGE-2.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 819 | `workcenters/EDGE-2/job_cmd` | EDGE-2 | P-01 | ns=2;s=EDGE-2.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 820 | `workcenters/EDGE-3/event` | EDGE-3 | P-01 | ns=2;s=EDGE-3.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 821 | `workcenters/EDGE-3/job_cmd` | EDGE-3 | P-01 | ns=2;s=EDGE-3.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 822 | `workcenters/CNC-1/event` | CNC-1 | P-01 | ns=2;s=CNC-1.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 823 | `workcenters/CNC-1/job_cmd` | CNC-1 | P-01 | ns=2;s=CNC-1.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 824 | `workcenters/CNC-2/event` | CNC-2 | P-01 | ns=2;s=CNC-2.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 825 | `workcenters/CNC-2/job_cmd` | CNC-2 | P-01 | ns=2;s=CNC-2.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 826 | `workcenters/CNC-3/event` | CNC-3 | P-01 | ns=2;s=CNC-3.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 827 | `workcenters/CNC-3/job_cmd` | CNC-3 | P-01 | ns=2;s=CNC-3.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 828 | `workcenters/CNC-4/event` | CNC-4 | P-01 | ns=2;s=CNC-4.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 829 | `workcenters/CNC-4/job_cmd` | CNC-4 | P-01 | ns=2;s=CNC-4.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 830 | `workcenters/BORE-1/event` | BORE-1 | P-01 | ns=2;s=BORE-1.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 831 | `workcenters/BORE-1/job_cmd` | BORE-1 | P-01 | ns=2;s=BORE-1.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 832 | `workcenters/DOWEL-1/event` | DOWEL-1 | P-01 | ns=2;s=DOWEL-1.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 833 | `workcenters/DOWEL-1/job_cmd` | DOWEL-1 | P-01 | ns=2;s=DOWEL-1.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 834 | `workcenters/SORT-1/event` | SORT-1 | P-01 | ns=2;s=SORT-1.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 835 | `workcenters/SORT-1/job_cmd` | SORT-1 | P-01 | ns=2;s=SORT-1.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 836 | `workcenters/ASMLINE-1/event` | ASMLINE-1 | P-01 | ns=2;s=ASMLINE-1.Events (EventNotifier; WwBaseEventType / WwAlarmConditionType, §8.3.3) | event | — | — | — | — | R-15 (події §8.3.3) | новий |
| 837 | `workcenters/ASMLINE-1/job_cmd` | ASMLINE-1 | P-01 | ns=2;s=ASMLINE-1.JobManagement.JobOrderControl (методи Store/StoreAndStart/Stop/…, виклик із логіном; лише `write_enabled` споживача) | Method | — | — | — | — | R-17 | новий |
| 838 | `workcenters/SAW-1/machine_state` | SAW-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 839 | `workcenters/SAW-2/machine_state` | SAW-2 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 840 | `workcenters/SAW-3/machine_state` | SAW-3 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 841 | `workcenters/NEST-1/machine_state` | NEST-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 842 | `workcenters/EDGE-1/machine_state` | EDGE-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 843 | `workcenters/EDGE-2/machine_state` | EDGE-2 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 844 | `workcenters/EDGE-3/machine_state` | EDGE-3 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 845 | `workcenters/CNC-1/machine_state` | CNC-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 846 | `workcenters/CNC-2/machine_state` | CNC-2 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 847 | `workcenters/CNC-3/machine_state` | CNC-3 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 848 | `workcenters/CNC-4/machine_state` | CNC-4 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 849 | `workcenters/BORE-1/machine_state` | BORE-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 850 | `workcenters/DOWEL-1/machine_state` | DOWEL-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 851 | `workcenters/SORT-1/machine_state` | SORT-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 852 | `workcenters/ASMLINE-1/machine_state` | ASMLINE-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 853 | `workcenters/SLIDE-1/machine_state` | SLIDE-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 854 | `workcenters/VSAW-1/machine_state` | VSAW-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 855 | `workcenters/SAND-1/machine_state` | SAND-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 856 | `workcenters/PRESS-1/machine_state` | PRESS-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 857 | `workcenters/GLUE-1/machine_state` | GLUE-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 858 | `workcenters/SPRAY-1/machine_state` | SPRAY-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 859 | `workcenters/AUTOSPRAY-1/machine_state` | AUTOSPRAY-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 860 | `workcenters/DRY-1/machine_state` | DRY-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 861 | `workcenters/UV-1/machine_state` | UV-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 862 | `workcenters/HINGE-1/machine_state` | HINGE-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 863 | `workcenters/BOX-1/machine_state` | BOX-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 864 | `workcenters/PACK-1/machine_state` | PACK-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 865 | `workcenters/PACK-2/machine_state` | PACK-2 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 866 | `workcenters/PACKLINE-1/machine_state` | PACKLINE-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 867 | `workcenters/ASM-1/machine_state` | ASM-1 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 868 | `workcenters/ASM-2/machine_state` | ASM-2 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 869 | `workcenters/ASM-3/machine_state` | ASM-3 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 870 | `workcenters/ASM-4/machine_state` | ASM-4 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 871 | `workcenters/ASM-5/machine_state` | ASM-5 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 872 | `workcenters/ASM-6/machine_state` | ASM-6 | — | обчислює machine_connect (CM-02, `MC-DERIVED`) — без адреси (X-34) | state | working/setup/idle/fault/off/nodata | — | — | — | обчислює machine_connect | новий |
| 873 | `equipment/GANTRY-1/cmd` | GANTRY-1 | P-03 | POST /api/v1/jobs → $.id (API-25; лише `write_enabled` споживача) | String | — | — | — | — | R-18 | новий |
| 874 | `ventilation/units/RV-01/filter_extract_dp_pa` | RV-01 | P-08 | BACnet dev 101 AI:5 Present_Value (RV-01_ExtractAirFilterDp) | REAL | Па | ×1 | 168,1 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 875 | `ventilation/units/RV-01/heat_kw` | RV-01 | P-08 | BACnet dev 101 AI:7 Present_Value (RV-01_HeatOutput) | REAL | кВт | ×1 | 17,3 | — | R-23 | новий |
| 876 | `ventilation/units/RV-01/p_now` | RV-01 | P-08 | BACnet dev 101 AI:8 Present_Value (RV-01_FanPower) | REAL | кВт | ×1 | 2,8 | — | R-23 | новий |
| 877 | `ventilation/units/RV-01/setpoint_day_c` | RV-01 | P-08 | BACnet dev 101 AV:1 Present_Value (RV-01_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 878 | `ventilation/units/RV-01/setpoint_night_c` | RV-01 | P-08 | BACnet dev 101 AV:2 Present_Value (RV-01_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 879 | `ventilation/units/RV-01/check` | RV-01 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 880 | `ventilation/units/RV-02/filter_extract_dp_pa` | RV-02 | P-08 | BACnet dev 102 AI:5 Present_Value (RV-02_ExtractAirFilterDp) | REAL | Па | ×1 | 141,8 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 881 | `ventilation/units/RV-02/heat_kw` | RV-02 | P-08 | BACnet dev 102 AI:7 Present_Value (RV-02_HeatOutput) | REAL | кВт | ×1 | 17,1 | — | R-23 | новий |
| 882 | `ventilation/units/RV-02/p_now` | RV-02 | P-08 | BACnet dev 102 AI:8 Present_Value (RV-02_FanPower) | REAL | кВт | ×1 | 2,69 | — | R-23 | новий |
| 883 | `ventilation/units/RV-02/setpoint_day_c` | RV-02 | P-08 | BACnet dev 102 AV:1 Present_Value (RV-02_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 884 | `ventilation/units/RV-02/setpoint_night_c` | RV-02 | P-08 | BACnet dev 102 AV:2 Present_Value (RV-02_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 885 | `ventilation/units/RV-02/check` | RV-02 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 886 | `ventilation/units/RV-03/filter_extract_dp_pa` | RV-03 | P-08 | BACnet dev 103 AI:5 Present_Value (RV-03_ExtractAirFilterDp) | REAL | Па | ×1 | 115,6 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 887 | `ventilation/units/RV-03/heat_kw` | RV-03 | P-08 | BACnet dev 103 AI:7 Present_Value (RV-03_HeatOutput) | REAL | кВт | ×1 | 16,8 | — | R-23 | новий |
| 888 | `ventilation/units/RV-03/p_now` | RV-03 | P-08 | BACnet dev 103 AI:8 Present_Value (RV-03_FanPower) | REAL | кВт | ×1 | 2,57 | — | R-23 | новий |
| 889 | `ventilation/units/RV-03/setpoint_day_c` | RV-03 | P-08 | BACnet dev 103 AV:1 Present_Value (RV-03_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 890 | `ventilation/units/RV-03/setpoint_night_c` | RV-03 | P-08 | BACnet dev 103 AV:2 Present_Value (RV-03_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 891 | `ventilation/units/RV-03/check` | RV-03 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 892 | `ventilation/units/RV-04/filter_extract_dp_pa` | RV-04 | P-08 | BACnet dev 104 AI:5 Present_Value (RV-04_ExtractAirFilterDp) | REAL | Па | ×1 | 165,9 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 893 | `ventilation/units/RV-04/heat_kw` | RV-04 | P-08 | BACnet dev 104 AI:7 Present_Value (RV-04_HeatOutput) | REAL | кВт | ×1 | 7,0 | — | R-23 | новий |
| 894 | `ventilation/units/RV-04/p_now` | RV-04 | P-08 | BACnet dev 104 AI:8 Present_Value (RV-04_FanPower) | REAL | кВт | ×1 | 3,45 | — | R-23 | новий |
| 895 | `ventilation/units/RV-04/setpoint_day_c` | RV-04 | P-08 | BACnet dev 104 AV:1 Present_Value (RV-04_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 896 | `ventilation/units/RV-04/setpoint_night_c` | RV-04 | P-08 | BACnet dev 104 AV:2 Present_Value (RV-04_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 897 | `ventilation/units/RV-04/check` | RV-04 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 898 | `ventilation/units/RV-05/filter_extract_dp_pa` | RV-05 | P-08 | BACnet dev 105 AI:5 Present_Value (RV-05_ExtractAirFilterDp) | REAL | Па | ×1 | 229,8 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 899 | `ventilation/units/RV-05/heat_kw` | RV-05 | P-08 | BACnet dev 105 AI:7 Present_Value (RV-05_HeatOutput) | REAL | кВт | ×1 | 6,9 | — | R-23 | новий |
| 900 | `ventilation/units/RV-05/p_now` | RV-05 | P-08 | BACnet dev 105 AI:8 Present_Value (RV-05_FanPower) | REAL | кВт | ×1 | 3,31 | — | R-23 | новий |
| 901 | `ventilation/units/RV-05/setpoint_day_c` | RV-05 | P-08 | BACnet dev 105 AV:1 Present_Value (RV-05_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 902 | `ventilation/units/RV-05/setpoint_night_c` | RV-05 | P-08 | BACnet dev 105 AV:2 Present_Value (RV-05_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 903 | `ventilation/units/RV-05/check` | RV-05 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 904 | `ventilation/units/RV-06/filter_extract_dp_pa` | RV-06 | P-08 | BACnet dev 106 AI:5 Present_Value (RV-06_ExtractAirFilterDp) | REAL | Па | ×1 | 160,9 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 905 | `ventilation/units/RV-06/heat_kw` | RV-06 | P-08 | BACnet dev 106 AI:7 Present_Value (RV-06_HeatOutput) | REAL | кВт | ×1 | 6,8 | — | R-23 | новий |
| 906 | `ventilation/units/RV-06/p_now` | RV-06 | P-08 | BACnet dev 106 AI:8 Present_Value (RV-06_FanPower) | REAL | кВт | ×1 | 3,18 | — | R-23 | новий |
| 907 | `ventilation/units/RV-06/setpoint_day_c` | RV-06 | P-08 | BACnet dev 106 AV:1 Present_Value (RV-06_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 908 | `ventilation/units/RV-06/setpoint_night_c` | RV-06 | P-08 | BACnet dev 106 AV:2 Present_Value (RV-06_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 909 | `ventilation/units/RV-06/check` | RV-06 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 910 | `ventilation/units/RV-07/filter_extract_dp_pa` | RV-07 | P-08 | BACnet dev 107 AI:5 Present_Value (RV-07_ExtractAirFilterDp) | REAL | Па | ×1 | 101,0 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 911 | `ventilation/units/RV-07/heat_kw` | RV-07 | P-08 | BACnet dev 107 AI:7 Present_Value (RV-07_HeatOutput) | REAL | кВт | ×1 | 6,7 | — | R-23 | новий |
| 912 | `ventilation/units/RV-07/p_now` | RV-07 | P-08 | BACnet dev 107 AI:8 Present_Value (RV-07_FanPower) | REAL | кВт | ×1 | 3,05 | — | R-23 | новий |
| 913 | `ventilation/units/RV-07/setpoint_day_c` | RV-07 | P-08 | BACnet dev 107 AV:1 Present_Value (RV-07_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 914 | `ventilation/units/RV-07/setpoint_night_c` | RV-07 | P-08 | BACnet dev 107 AV:2 Present_Value (RV-07_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 915 | `ventilation/units/RV-07/check` | RV-07 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 916 | `ventilation/units/RV-08/filter_extract_dp_pa` | RV-08 | P-08 | BACnet dev 108 AI:5 Present_Value (RV-08_ExtractAirFilterDp) | REAL | Па | ×1 | 166,0 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 917 | `ventilation/units/RV-08/heat_kw` | RV-08 | P-08 | BACnet dev 108 AI:7 Present_Value (RV-08_HeatOutput) | REAL | кВт | ×1 | 7,2 | — | R-23 | новий |
| 918 | `ventilation/units/RV-08/p_now` | RV-08 | P-08 | BACnet dev 108 AI:8 Present_Value (RV-08_FanPower) | REAL | кВт | ×1 | 3,73 | — | R-23 | новий |
| 919 | `ventilation/units/RV-08/setpoint_day_c` | RV-08 | P-08 | BACnet dev 108 AV:1 Present_Value (RV-08_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 920 | `ventilation/units/RV-08/setpoint_night_c` | RV-08 | P-08 | BACnet dev 108 AV:2 Present_Value (RV-08_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 921 | `ventilation/units/RV-08/check` | RV-08 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 922 | `ventilation/units/RV-09/filter_extract_dp_pa` | RV-09 | P-08 | BACnet dev 109 AI:5 Present_Value (RV-09_ExtractAirFilterDp) | REAL | Па | ×1 | 110,6 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 923 | `ventilation/units/RV-09/heat_kw` | RV-09 | P-08 | BACnet dev 109 AI:7 Present_Value (RV-09_HeatOutput) | REAL | кВт | ×1 | 7,1 | — | R-23 | новий |
| 924 | `ventilation/units/RV-09/p_now` | RV-09 | P-08 | BACnet dev 109 AI:8 Present_Value (RV-09_FanPower) | REAL | кВт | ×1 | 3,58 | — | R-23 | новий |
| 925 | `ventilation/units/RV-09/setpoint_day_c` | RV-09 | P-08 | BACnet dev 109 AV:1 Present_Value (RV-09_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 926 | `ventilation/units/RV-09/setpoint_night_c` | RV-09 | P-08 | BACnet dev 109 AV:2 Present_Value (RV-09_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 927 | `ventilation/units/RV-09/check` | RV-09 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 928 | `ventilation/units/RV-10/filter_extract_dp_pa` | RV-10 | P-08 | BACnet dev 110 AI:5 Present_Value (RV-10_ExtractAirFilterDp) | REAL | Па | ×1 | 141,2 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 929 | `ventilation/units/RV-10/heat_kw` | RV-10 | P-08 | BACnet dev 110 AI:7 Present_Value (RV-10_HeatOutput) | REAL | кВт | ×1 | 7,8 | — | R-23 | новий |
| 930 | `ventilation/units/RV-10/p_now` | RV-10 | P-08 | BACnet dev 110 AI:8 Present_Value (RV-10_FanPower) | REAL | кВт | ×1 | 4,84 | — | R-23 | новий |
| 931 | `ventilation/units/RV-10/setpoint_day_c` | RV-10 | P-08 | BACnet dev 110 AV:1 Present_Value (RV-10_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 932 | `ventilation/units/RV-10/setpoint_night_c` | RV-10 | P-08 | BACnet dev 110 AV:2 Present_Value (RV-10_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 933 | `ventilation/units/RV-10/check` | RV-10 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 934 | `ventilation/units/RV-11/filter_extract_dp_pa` | RV-11 | P-08 | BACnet dev 111 AI:5 Present_Value (RV-11_ExtractAirFilterDp) | REAL | Па | ×1 | 167,4 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 935 | `ventilation/units/RV-11/heat_kw` | RV-11 | P-08 | BACnet dev 111 AI:7 Present_Value (RV-11_HeatOutput) | REAL | кВт | ×1 | 6,6 | — | R-23 | новий |
| 936 | `ventilation/units/RV-11/p_now` | RV-11 | P-08 | BACnet dev 111 AI:8 Present_Value (RV-11_FanPower) | REAL | кВт | ×1 | 2,93 | — | R-23 | новий |
| 937 | `ventilation/units/RV-11/setpoint_day_c` | RV-11 | P-08 | BACnet dev 111 AV:1 Present_Value (RV-11_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 938 | `ventilation/units/RV-11/setpoint_night_c` | RV-11 | P-08 | BACnet dev 111 AV:2 Present_Value (RV-11_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 939 | `ventilation/units/RV-11/check` | RV-11 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 940 | `ventilation/units/RV-12/filter_extract_dp_pa` | RV-12 | P-08 | BACnet dev 112 AI:5 Present_Value (RV-12_ExtractAirFilterDp) | REAL | Па | ×1 | 155,4 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 941 | `ventilation/units/RV-12/heat_kw` | RV-12 | P-08 | BACnet dev 112 AI:7 Present_Value (RV-12_HeatOutput) | REAL | кВт | ×1 | 6,7 | — | R-23 | новий |
| 942 | `ventilation/units/RV-12/p_now` | RV-12 | P-08 | BACnet dev 112 AI:8 Present_Value (RV-12_FanPower) | REAL | кВт | ×1 | 3,05 | — | R-23 | новий |
| 943 | `ventilation/units/RV-12/setpoint_day_c` | RV-12 | P-08 | BACnet dev 112 AV:1 Present_Value (RV-12_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 944 | `ventilation/units/RV-12/setpoint_night_c` | RV-12 | P-08 | BACnet dev 112 AV:2 Present_Value (RV-12_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 945 | `ventilation/units/RV-12/check` | RV-12 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 946 | `ventilation/units/RV-13/filter_extract_dp_pa` | RV-13 | P-08 | BACnet dev 113 AI:5 Present_Value (RV-13_ExtractAirFilterDp) | REAL | Па | ×1 | 164,3 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 947 | `ventilation/units/RV-13/heat_kw` | RV-13 | P-08 | BACnet dev 113 AI:7 Present_Value (RV-13_HeatOutput) | REAL | кВт | ×1 | 6,8 | — | R-23 | новий |
| 948 | `ventilation/units/RV-13/p_now` | RV-13 | P-08 | BACnet dev 113 AI:8 Present_Value (RV-13_FanPower) | REAL | кВт | ×1 | 3,18 | — | R-23 | новий |
| 949 | `ventilation/units/RV-13/setpoint_day_c` | RV-13 | P-08 | BACnet dev 113 AV:1 Present_Value (RV-13_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 950 | `ventilation/units/RV-13/setpoint_night_c` | RV-13 | P-08 | BACnet dev 113 AV:2 Present_Value (RV-13_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 951 | `ventilation/units/RV-13/check` | RV-13 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 952 | `ventilation/units/RV-14/filter_extract_dp_pa` | RV-14 | P-08 | BACnet dev 114 AI:5 Present_Value (RV-14_ExtractAirFilterDp) | REAL | Па | ×1 | 99,5 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 953 | `ventilation/units/RV-14/heat_kw` | RV-14 | P-08 | BACnet dev 114 AI:7 Present_Value (RV-14_HeatOutput) | REAL | кВт | ×1 | 6,9 | — | R-23 | новий |
| 954 | `ventilation/units/RV-14/p_now` | RV-14 | P-08 | BACnet dev 114 AI:8 Present_Value (RV-14_FanPower) | REAL | кВт | ×1 | 3,31 | — | R-23 | новий |
| 955 | `ventilation/units/RV-14/setpoint_day_c` | RV-14 | P-08 | BACnet dev 114 AV:1 Present_Value (RV-14_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 956 | `ventilation/units/RV-14/setpoint_night_c` | RV-14 | P-08 | BACnet dev 114 AV:2 Present_Value (RV-14_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 957 | `ventilation/units/RV-14/check` | RV-14 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 958 | `ventilation/units/RV-15/filter_extract_dp_pa` | RV-15 | P-08 | BACnet dev 115 AI:5 Present_Value (RV-15_ExtractAirFilterDp) | REAL | Па | ×1 | 167,4 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 959 | `ventilation/units/RV-15/heat_kw` | RV-15 | P-08 | BACnet dev 115 AI:7 Present_Value (RV-15_HeatOutput) | REAL | кВт | ×1 | 7,0 | — | R-23 | новий |
| 960 | `ventilation/units/RV-15/p_now` | RV-15 | P-08 | BACnet dev 115 AI:8 Present_Value (RV-15_FanPower) | REAL | кВт | ×1 | 3,45 | — | R-23 | новий |
| 961 | `ventilation/units/RV-15/setpoint_day_c` | RV-15 | P-08 | BACnet dev 115 AV:1 Present_Value (RV-15_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 962 | `ventilation/units/RV-15/setpoint_night_c` | RV-15 | P-08 | BACnet dev 115 AV:2 Present_Value (RV-15_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 963 | `ventilation/units/RV-15/check` | RV-15 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 964 | `ventilation/units/RV-16/filter_extract_dp_pa` | RV-16 | P-08 | BACnet dev 116 AI:5 Present_Value (RV-16_ExtractAirFilterDp) | REAL | Па | ×1 | 110,5 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 965 | `ventilation/units/RV-16/heat_kw` | RV-16 | P-08 | BACnet dev 116 AI:7 Present_Value (RV-16_HeatOutput) | REAL | кВт | ×1 | 7,1 | — | R-23 | новий |
| 966 | `ventilation/units/RV-16/p_now` | RV-16 | P-08 | BACnet dev 116 AI:8 Present_Value (RV-16_FanPower) | REAL | кВт | ×1 | 3,58 | — | R-23 | новий |
| 967 | `ventilation/units/RV-16/setpoint_day_c` | RV-16 | P-08 | BACnet dev 116 AV:1 Present_Value (RV-16_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 968 | `ventilation/units/RV-16/setpoint_night_c` | RV-16 | P-08 | BACnet dev 116 AV:2 Present_Value (RV-16_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 969 | `ventilation/units/RV-16/check` | RV-16 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 970 | `ventilation/units/RV-17/filter_extract_dp_pa` | RV-17 | P-08 | BACnet dev 117 AI:5 Present_Value (RV-17_ExtractAirFilterDp) | REAL | Па | ×1 | 119,5 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 971 | `ventilation/units/RV-17/heat_kw` | RV-17 | P-08 | BACnet dev 117 AI:7 Present_Value (RV-17_HeatOutput) | REAL | кВт | ×1 | 7,2 | — | R-23 | новий |
| 972 | `ventilation/units/RV-17/p_now` | RV-17 | P-08 | BACnet dev 117 AI:8 Present_Value (RV-17_FanPower) | REAL | кВт | ×1 | 3,73 | — | R-23 | новий |
| 973 | `ventilation/units/RV-17/setpoint_day_c` | RV-17 | P-08 | BACnet dev 117 AV:1 Present_Value (RV-17_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 974 | `ventilation/units/RV-17/setpoint_night_c` | RV-17 | P-08 | BACnet dev 117 AV:2 Present_Value (RV-17_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 975 | `ventilation/units/RV-17/check` | RV-17 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 976 | `ventilation/units/RV-18/filter_extract_dp_pa` | RV-18 | P-08 | BACnet dev 118 AI:5 Present_Value (RV-18_ExtractAirFilterDp) | REAL | Па | ×1 | 166,6 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 977 | `ventilation/units/RV-18/heat_kw` | RV-18 | P-08 | BACnet dev 118 AI:7 Present_Value (RV-18_HeatOutput) | REAL | кВт | ×1 | 7,1 | — | R-23 | новий |
| 978 | `ventilation/units/RV-18/p_now` | RV-18 | P-08 | BACnet dev 118 AI:8 Present_Value (RV-18_FanPower) | REAL | кВт | ×1 | 3,58 | — | R-23 | новий |
| 979 | `ventilation/units/RV-18/setpoint_day_c` | RV-18 | P-08 | BACnet dev 118 AV:1 Present_Value (RV-18_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 980 | `ventilation/units/RV-18/setpoint_night_c` | RV-18 | P-08 | BACnet dev 118 AV:2 Present_Value (RV-18_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 981 | `ventilation/units/RV-18/check` | RV-18 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 982 | `ventilation/units/RV-19/filter_extract_dp_pa` | RV-19 | P-08 | BACnet dev 119 AI:5 Present_Value (RV-19_ExtractAirFilterDp) | REAL | Па | ×1 | 121,0 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 983 | `ventilation/units/RV-19/heat_kw` | RV-19 | P-08 | BACnet dev 119 AI:7 Present_Value (RV-19_HeatOutput) | REAL | кВт | ×1 | 7,2 | — | R-23 | новий |
| 984 | `ventilation/units/RV-19/p_now` | RV-19 | P-08 | BACnet dev 119 AI:8 Present_Value (RV-19_FanPower) | REAL | кВт | ×1 | 3,73 | — | R-23 | новий |
| 985 | `ventilation/units/RV-19/setpoint_day_c` | RV-19 | P-08 | BACnet dev 119 AV:1 Present_Value (RV-19_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 986 | `ventilation/units/RV-19/setpoint_night_c` | RV-19 | P-08 | BACnet dev 119 AV:2 Present_Value (RV-19_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 987 | `ventilation/units/RV-19/check` | RV-19 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 988 | `ventilation/units/RV-20/filter_extract_dp_pa` | RV-20 | P-08 | BACnet dev 120 AI:5 Present_Value (RV-20_ExtractAirFilterDp) | REAL | Па | ×1 | 135,4 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 989 | `ventilation/units/RV-20/heat_kw` | RV-20 | P-08 | BACnet dev 120 AI:7 Present_Value (RV-20_HeatOutput) | REAL | кВт | ×1 | 7,7 | — | R-23 | новий |
| 990 | `ventilation/units/RV-20/p_now` | RV-20 | P-08 | BACnet dev 120 AI:8 Present_Value (RV-20_FanPower) | REAL | кВт | ×1 | 4,67 | — | R-23 | новий |
| 991 | `ventilation/units/RV-20/setpoint_day_c` | RV-20 | P-08 | BACnet dev 120 AV:1 Present_Value (RV-20_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 992 | `ventilation/units/RV-20/setpoint_night_c` | RV-20 | P-08 | BACnet dev 120 AV:2 Present_Value (RV-20_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 993 | `ventilation/units/RV-20/check` | RV-20 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 994 | `ventilation/units/RV-21/filter_extract_dp_pa` | RV-21 | P-08 | BACnet dev 121 AI:5 Present_Value (RV-21_ExtractAirFilterDp) | REAL | Па | ×1 | 120,3 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 995 | `ventilation/units/RV-21/heat_kw` | RV-21 | P-08 | BACnet dev 121 AI:7 Present_Value (RV-21_HeatOutput) | REAL | кВт | ×1 | 11,5 | — | R-23 | новий |
| 996 | `ventilation/units/RV-21/p_now` | RV-21 | P-08 | BACnet dev 121 AI:8 Present_Value (RV-21_FanPower) | REAL | кВт | ×1 | 0,88 | — | R-23 | новий |
| 997 | `ventilation/units/RV-21/setpoint_day_c` | RV-21 | P-08 | BACnet dev 121 AV:1 Present_Value (RV-21_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 998 | `ventilation/units/RV-21/setpoint_night_c` | RV-21 | P-08 | BACnet dev 121 AV:2 Present_Value (RV-21_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 999 | `ventilation/units/RV-21/check` | RV-21 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 1000 | `ventilation/units/RV-22/filter_extract_dp_pa` | RV-22 | P-08 | BACnet dev 122 AI:5 Present_Value (RV-22_ExtractAirFilterDp) | REAL | Па | ×1 | 133,8 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 1001 | `ventilation/units/RV-22/heat_kw` | RV-22 | P-08 | BACnet dev 122 AI:7 Present_Value (RV-22_HeatOutput) | REAL | кВт | ×1 | 11,5 | — | R-23 | новий |
| 1002 | `ventilation/units/RV-22/p_now` | RV-22 | P-08 | BACnet dev 122 AI:8 Present_Value (RV-22_FanPower) | REAL | кВт | ×1 | 0,88 | — | R-23 | новий |
| 1003 | `ventilation/units/RV-22/setpoint_day_c` | RV-22 | P-08 | BACnet dev 122 AV:1 Present_Value (RV-22_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 1004 | `ventilation/units/RV-22/setpoint_night_c` | RV-22 | P-08 | BACnet dev 122 AV:2 Present_Value (RV-22_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 1005 | `ventilation/units/RV-22/check` | RV-22 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 1006 | `ventilation/units/RV-23/filter_extract_dp_pa` | RV-23 | P-08 | BACnet dev 123 AI:5 Present_Value (RV-23_ExtractAirFilterDp) | REAL | Па | ×1 | 161,8 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 1007 | `ventilation/units/RV-23/heat_kw` | RV-23 | P-08 | BACnet dev 123 AI:7 Present_Value (RV-23_HeatOutput) | REAL | кВт | ×1 | 20,9 | — | R-23 | новий |
| 1008 | `ventilation/units/RV-23/p_now` | RV-23 | P-08 | BACnet dev 123 AI:8 Present_Value (RV-23_FanPower) | REAL | кВт | ×1 | 4,84 | — | R-23 | новий |
| 1009 | `ventilation/units/RV-23/setpoint_day_c` | RV-23 | P-08 | BACnet dev 123 AV:1 Present_Value (RV-23_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 1010 | `ventilation/units/RV-23/setpoint_night_c` | RV-23 | P-08 | BACnet dev 123 AV:2 Present_Value (RV-23_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 1011 | `ventilation/units/RV-23/check` | RV-23 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 1012 | `ventilation/units/RV-24/filter_extract_dp_pa` | RV-24 | P-08 | BACnet dev 124 AI:5 Present_Value (RV-24_ExtractAirFilterDp) | REAL | Па | ×1 | 108,2 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 1013 | `ventilation/units/RV-24/heat_kw` | RV-24 | P-08 | BACnet dev 124 AI:7 Present_Value (RV-24_HeatOutput) | REAL | кВт | ×1 | 19,6 | — | R-23 | новий |
| 1014 | `ventilation/units/RV-24/p_now` | RV-24 | P-08 | BACnet dev 124 AI:8 Present_Value (RV-24_FanPower) | REAL | кВт | ×1 | 4,03 | — | R-23 | новий |
| 1015 | `ventilation/units/RV-24/setpoint_day_c` | RV-24 | P-08 | BACnet dev 124 AV:1 Present_Value (RV-24_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 1016 | `ventilation/units/RV-24/setpoint_night_c` | RV-24 | P-08 | BACnet dev 124 AV:2 Present_Value (RV-24_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 1017 | `ventilation/units/RV-24/check` | RV-24 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 1018 | `ventilation/units/RV-25/filter_extract_dp_pa` | RV-25 | P-08 | BACnet dev 125 AI:5 Present_Value (RV-25_ExtractAirFilterDp) | REAL | Па | ×1 | 120,2 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 1019 | `ventilation/units/RV-25/heat_kw` | RV-25 | P-08 | BACnet dev 125 AI:7 Present_Value (RV-25_HeatOutput) | REAL | кВт | ×1 | 19,4 | — | R-23 | новий |
| 1020 | `ventilation/units/RV-25/p_now` | RV-25 | P-08 | BACnet dev 125 AI:8 Present_Value (RV-25_FanPower) | REAL | кВт | ×1 | 3,88 | — | R-23 | новий |
| 1021 | `ventilation/units/RV-25/setpoint_day_c` | RV-25 | P-08 | BACnet dev 125 AV:1 Present_Value (RV-25_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 1022 | `ventilation/units/RV-25/setpoint_night_c` | RV-25 | P-08 | BACnet dev 125 AV:2 Present_Value (RV-25_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 1023 | `ventilation/units/RV-25/check` | RV-25 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 1024 | `ventilation/units/AHU-1/filter_extract_dp_pa` | AHU-1 | P-08 | BACnet dev 130 AI:5 Present_Value (AHU-1_ExtractAirFilterDp) | REAL | Па | ×1 | 129,8 (0,8·AI:4) | > 350 → заявка | R-09 (0,8·AI:4) | новий |
| 1025 | `ventilation/units/AHU-1/heat_kw` | AHU-1 | P-08 | BACnet dev 130 AI:7 Present_Value (AHU-1_HeatOutput) | REAL | кВт | ×1 | 68,0 | — | R-23 | новий |
| 1026 | `ventilation/units/AHU-1/p_now` | AHU-1 | P-08 | BACnet dev 130 AI:8 Present_Value (AHU-1_FanPower) | REAL | кВт | ×1 | 9,3 | — | R-23 | новий |
| 1027 | `ventilation/units/AHU-1/setpoint_day_c` | AHU-1 | P-08 | BACnet dev 130 AV:1 Present_Value (AHU-1_RoomSetpointDay, RW) | REAL | °C | ×1 | 18,0 | — | R-23 | новий |
| 1028 | `ventilation/units/AHU-1/setpoint_night_c` | AHU-1 | P-08 | BACnet dev 130 AV:2 Present_Value (AHU-1_RoomSetpointNight, RW) | REAL | °C | ×1 | 14,0 | — | R-23 | новий |
| 1029 | `ventilation/units/AHU-1/check` | AHU-1 | — | обчислює bms (R-23, `BMS-DERIVED`) — без адреси (X-34) | state | 7 текстів bms R-23 | — | — | — | обчислює bms | новий |
| 1030 | `ventilation/units/AHU-1/room_pressure_pa` | AHU-1 | P-08 | BACnet dev 130 AI:9 Present_Value (AHU-1_RoomPressure) | REAL | Па | ×1 | −10 (−5…−15) | > 0 ≥ 300 с → заявка | R-23 | новий |
| 1031 | `ventilation/units/AHU-1/booth_interlock` | AHU-1 | P-08 | BACnet dev 130 BI:6 Present_Value (AHU-1_BoothExtractInterlock) | BI | 0 off/1 on | — | 1 | — | R-23 | новий |
| 1032 | `ventilation/units/EF-ELEC/indoor_c` | EF-ELEC | P-08 | BACnet dev 131 AI:2 Present_Value (EF-ELEC_RoomTemp) | REAL | °C | ×1 | 29,5 | > 35 ≥ 600 с → заявка | R-23 | новий |
| 1033 | `ventilation/units/EF-CMP/indoor_c` | EF-CMP | P-08 | BACnet dev 132 AI:2 Present_Value (EF-CMP_RoomTemp) | REAL | °C | ×1 | 24,0 | > 35 → warn | R-23 | новий |
| 1034 | `ventilation/units/EF-CHG/indoor_c` | EF-CHG | P-08 | BACnet dev 133 AI:2 Present_Value (EF-CHG_RoomTemp) | REAL | °C | ×1 | 22,0 | — | R-23 | новий |
| 1035 | `ventilation/totals/outdoor_c` | RV-01 | P-08 | BACnet dev 101 AI:6 Present_Value (RV-01_OutdoorTemp) | REAL | °C | ×1 | 9,0 (добовий хід ±3) | — | R-23 (`World.outdoor_c`) | новий |
| 1036 | `equipment/BOILER/heat_kw` | BOILER | P-08 | BACnet dev 140 AI:5 Present_Value (BOILER_HeatOutput) | REAL | кВт | ×1 | 0 (КГУ покриває тепло) | — | R-10 | новий |
| 1037 | `ventilation/heat_plant/check` | BOILER | — | обчислює bms (R-24, `BMS-DERIVED`) — без адреси (X-34) | state | норма/дефіцит тепла/немає даних | — | — | — | обчислює bms | новий |
| 1038 | `lighting/groups/LT-RCV-1/faults` | LT-RCV-1 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:1 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1039 | `lighting/groups/LT-RCV-1/faulty` | LT-RCV-1 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:1, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1040 | `lighting/groups/LT-RCV-1/scene` | LT-RCV-1 | P-08 | HelvarNet LP-1 >V:2,C:109,G:1# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1041 | `lighting/groups/LT-RCV-1/check` | LT-RCV-1 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1042 | `lighting/groups/LT-RCV-2/faults` | LT-RCV-2 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:2 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1043 | `lighting/groups/LT-RCV-2/faulty` | LT-RCV-2 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:2, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1044 | `lighting/groups/LT-RCV-2/scene` | LT-RCV-2 | P-08 | HelvarNet LP-1 >V:2,C:109,G:2# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1045 | `lighting/groups/LT-RCV-2/check` | LT-RCV-2 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1046 | `lighting/groups/LT-RCV-3/faults` | LT-RCV-3 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:3 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1047 | `lighting/groups/LT-RCV-3/faulty` | LT-RCV-3 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:3, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1048 | `lighting/groups/LT-RCV-3/scene` | LT-RCV-3 | P-08 | HelvarNet LP-1 >V:2,C:109,G:3# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1049 | `lighting/groups/LT-RCV-3/check` | LT-RCV-3 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1050 | `lighting/groups/LT-RCV-4/faults` | LT-RCV-4 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:4 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1051 | `lighting/groups/LT-RCV-4/faulty` | LT-RCV-4 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:4, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1052 | `lighting/groups/LT-RCV-4/scene` | LT-RCV-4 | P-08 | HelvarNet LP-1 >V:2,C:109,G:4# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1053 | `lighting/groups/LT-RCV-4/check` | LT-RCV-4 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1054 | `lighting/groups/LT-RCV-5/faults` | LT-RCV-5 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:5 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1055 | `lighting/groups/LT-RCV-5/faulty` | LT-RCV-5 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:5, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1056 | `lighting/groups/LT-RCV-5/scene` | LT-RCV-5 | P-08 | HelvarNet LP-1 >V:2,C:109,G:5# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1057 | `lighting/groups/LT-RCV-5/check` | LT-RCV-5 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1058 | `lighting/groups/LT-RCV-6/faults` | LT-RCV-6 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:6 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1059 | `lighting/groups/LT-RCV-6/faulty` | LT-RCV-6 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:6, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1060 | `lighting/groups/LT-RCV-6/scene` | LT-RCV-6 | P-08 | HelvarNet LP-1 >V:2,C:109,G:6# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1061 | `lighting/groups/LT-RCV-6/check` | LT-RCV-6 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1062 | `lighting/groups/LT-RCV-7/faults` | LT-RCV-7 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:7 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1063 | `lighting/groups/LT-RCV-7/faulty` | LT-RCV-7 | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:7, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1064 | `lighting/groups/LT-RCV-7/scene` | LT-RCV-7 | P-08 | HelvarNet LP-1 >V:2,C:109,G:7# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1065 | `lighting/groups/LT-RCV-7/check` | LT-RCV-7 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1066 | `lighting/groups/LT-SHEETS/faults` | LT-SHEETS | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:8 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1067 | `lighting/groups/LT-SHEETS/faulty` | LT-SHEETS | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:8, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1068 | `lighting/groups/LT-SHEETS/scene` | LT-SHEETS | P-08 | HelvarNet LP-1 >V:2,C:109,G:8# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1069 | `lighting/groups/LT-SHEETS/check` | LT-SHEETS | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1070 | `lighting/groups/LT-HW/faults` | LT-HW | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:9 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1071 | `lighting/groups/LT-HW/faulty` | LT-HW | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:9, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1072 | `lighting/groups/LT-HW/scene` | LT-HW | P-08 | HelvarNet LP-1 >V:2,C:109,G:9# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1073 | `lighting/groups/LT-HW/check` | LT-HW | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1074 | `lighting/groups/LT-EDGE/faults` | LT-EDGE | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:10 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1075 | `lighting/groups/LT-EDGE/faulty` | LT-EDGE | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:10, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1076 | `lighting/groups/LT-EDGE/scene` | LT-EDGE | P-08 | HelvarNet LP-1 >V:2,C:109,G:10# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1077 | `lighting/groups/LT-EDGE/check` | LT-EDGE | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1078 | `lighting/groups/LT-PKS/faults` | LT-PKS | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:11 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1079 | `lighting/groups/LT-PKS/faulty` | LT-PKS | P-08 | HelvarNet LP-1 (router @1.1) C:110 по пристроях групи G:11, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1080 | `lighting/groups/LT-PKS/scene` | LT-PKS | P-08 | HelvarNet LP-1 >V:2,C:109,G:11# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1081 | `lighting/groups/LT-PKS/check` | LT-PKS | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1082 | `lighting/groups/LT-CUT/faults` | LT-CUT | P-08 | HelvarNet LP-2 (router @1.2) C:110 по пристроях групи G:12 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1083 | `lighting/groups/LT-CUT/faulty` | LT-CUT | P-08 | HelvarNet LP-2 (router @1.2) C:110 по пристроях групи G:12, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1084 | `lighting/groups/LT-CUT/scene` | LT-CUT | P-08 | HelvarNet LP-2 >V:2,C:109,G:12# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1085 | `lighting/groups/LT-CUT/check` | LT-CUT | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1086 | `lighting/groups/LT-EB/faults` | LT-EB | P-08 | HelvarNet LP-2 (router @1.2) C:110 по пристроях групи G:13 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1087 | `lighting/groups/LT-EB/faulty` | LT-EB | P-08 | HelvarNet LP-2 (router @1.2) C:110 по пристроях групи G:13, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1088 | `lighting/groups/LT-EB/scene` | LT-EB | P-08 | HelvarNet LP-2 >V:2,C:109,G:13# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1089 | `lighting/groups/LT-EB/check` | LT-EB | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1090 | `lighting/groups/LT-CNC/faults` | LT-CNC | P-08 | HelvarNet LP-2 (router @1.2) C:110 по пристроях групи G:14 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1091 | `lighting/groups/LT-CNC/faulty` | LT-CNC | P-08 | HelvarNet LP-2 (router @1.2) C:110 по пристроях групи G:14, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1092 | `lighting/groups/LT-CNC/scene` | LT-CNC | P-08 | HelvarNet LP-2 >V:2,C:109,G:14# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1093 | `lighting/groups/LT-CNC/check` | LT-CNC | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1094 | `lighting/groups/LT-SORT/faults` | LT-SORT | P-08 | HelvarNet LP-2 (router @1.2) C:110 по пристроях групи G:15 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1095 | `lighting/groups/LT-SORT/faulty` | LT-SORT | P-08 | HelvarNet LP-2 (router @1.2) C:110 по пристроях групи G:15, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1096 | `lighting/groups/LT-SORT/scene` | LT-SORT | P-08 | HelvarNet LP-2 >V:2,C:109,G:15# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1097 | `lighting/groups/LT-SORT/check` | LT-SORT | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1098 | `lighting/groups/LT-FAC/faults` | LT-FAC | P-08 | HelvarNet LP-2 (router @1.2) C:110 по пристроях групи G:16 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1099 | `lighting/groups/LT-FAC/faulty` | LT-FAC | P-08 | HelvarNet LP-2 (router @1.2) C:110 по пристроях групи G:16, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1100 | `lighting/groups/LT-FAC/scene` | LT-FAC | P-08 | HelvarNet LP-2 >V:2,C:109,G:16# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1101 | `lighting/groups/LT-FAC/check` | LT-FAC | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1102 | `lighting/groups/LT-ASM/faults` | LT-ASM | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:17 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1103 | `lighting/groups/LT-ASM/faulty` | LT-ASM | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:17, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1104 | `lighting/groups/LT-ASM/scene` | LT-ASM | P-08 | HelvarNet LP-3 >V:2,C:109,G:17# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1105 | `lighting/groups/LT-ASM/check` | LT-ASM | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1106 | `lighting/groups/LT-PRE/faults` | LT-PRE | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:18 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1107 | `lighting/groups/LT-PRE/faulty` | LT-PRE | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:18, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1108 | `lighting/groups/LT-PRE/scene` | LT-PRE | P-08 | HelvarNet LP-3 >V:2,C:109,G:18# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1109 | `lighting/groups/LT-PRE/check` | LT-PRE | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1110 | `lighting/groups/LT-MAINT/faults` | LT-MAINT | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:19 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1111 | `lighting/groups/LT-MAINT/faulty` | LT-MAINT | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:19, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1112 | `lighting/groups/LT-MAINT/scene` | LT-MAINT | P-08 | HelvarNet LP-3 >V:2,C:109,G:19# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1113 | `lighting/groups/LT-MAINT/check` | LT-MAINT | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1114 | `lighting/groups/LT-PACK/faults` | LT-PACK | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:20 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1115 | `lighting/groups/LT-PACK/faulty` | LT-PACK | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:20, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1116 | `lighting/groups/LT-PACK/scene` | LT-PACK | P-08 | HelvarNet LP-3 >V:2,C:109,G:20# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1117 | `lighting/groups/LT-PACK/check` | LT-PACK | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1118 | `lighting/groups/LT-POST/faults` | LT-POST | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:21 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1119 | `lighting/groups/LT-POST/faulty` | LT-POST | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:21, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1120 | `lighting/groups/LT-POST/scene` | LT-POST | P-08 | HelvarNet LP-3 >V:2,C:109,G:21# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1121 | `lighting/groups/LT-POST/check` | LT-POST | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1122 | `lighting/groups/LT-CMP/faults` | LT-CMP | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:22 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1123 | `lighting/groups/LT-CMP/faulty` | LT-CMP | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:22, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1124 | `lighting/groups/LT-CMP/scene` | LT-CMP | P-08 | HelvarNet LP-3 >V:2,C:109,G:22# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1125 | `lighting/groups/LT-CMP/check` | LT-CMP | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1126 | `lighting/groups/LT-CHG/faults` | LT-CHG | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:23 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1127 | `lighting/groups/LT-CHG/faulty` | LT-CHG | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:23, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1128 | `lighting/groups/LT-CHG/scene` | LT-CHG | P-08 | HelvarNet LP-3 >V:2,C:109,G:23# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1129 | `lighting/groups/LT-CHG/check` | LT-CHG | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1130 | `lighting/groups/LT-FG/faults` | LT-FG | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:24 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1131 | `lighting/groups/LT-FG/faulty` | LT-FG | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:24, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1132 | `lighting/groups/LT-FG/scene` | LT-FG | P-08 | HelvarNet LP-3 >V:2,C:109,G:24# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1133 | `lighting/groups/LT-FG/check` | LT-FG | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1134 | `lighting/groups/LT-ELEC/faults` | LT-ELEC | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:25 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1135 | `lighting/groups/LT-ELEC/faulty` | LT-ELEC | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:25, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1136 | `lighting/groups/LT-ELEC/scene` | LT-ELEC | P-08 | HelvarNet LP-3 >V:2,C:109,G:25# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1137 | `lighting/groups/LT-ELEC/check` | LT-ELEC | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1138 | `lighting/groups/LT-OUT-1/faults` | LT-OUT-1 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:26 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1139 | `lighting/groups/LT-OUT-1/faulty` | LT-OUT-1 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:26, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1140 | `lighting/groups/LT-OUT-1/scene` | LT-OUT-1 | P-08 | HelvarNet LP-3 >V:2,C:109,G:26# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1141 | `lighting/groups/LT-OUT-1/check` | LT-OUT-1 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1142 | `lighting/groups/LT-OUT-2/faults` | LT-OUT-2 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:27 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1143 | `lighting/groups/LT-OUT-2/faulty` | LT-OUT-2 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:27, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1144 | `lighting/groups/LT-OUT-2/scene` | LT-OUT-2 | P-08 | HelvarNet LP-3 >V:2,C:109,G:27# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1145 | `lighting/groups/LT-OUT-2/check` | LT-OUT-2 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1146 | `lighting/groups/LT-OUT-3/faults` | LT-OUT-3 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:28 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1147 | `lighting/groups/LT-OUT-3/faulty` | LT-OUT-3 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:28, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1148 | `lighting/groups/LT-OUT-3/scene` | LT-OUT-3 | P-08 | HelvarNet LP-3 >V:2,C:109,G:28# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1149 | `lighting/groups/LT-OUT-3/check` | LT-OUT-3 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1150 | `lighting/groups/LT-OUT-4/faults` | LT-OUT-4 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:29 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1151 | `lighting/groups/LT-OUT-4/faulty` | LT-OUT-4 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:29, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1152 | `lighting/groups/LT-OUT-4/scene` | LT-OUT-4 | P-08 | HelvarNet LP-3 >V:2,C:109,G:29# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1153 | `lighting/groups/LT-OUT-4/check` | LT-OUT-4 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1154 | `lighting/groups/LT-OUT-5/faults` | LT-OUT-5 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:30 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1155 | `lighting/groups/LT-OUT-5/faulty` | LT-OUT-5 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:30, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1156 | `lighting/groups/LT-OUT-5/scene` | LT-OUT-5 | P-08 | HelvarNet LP-3 >V:2,C:109,G:30# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1157 | `lighting/groups/LT-OUT-5/check` | LT-OUT-5 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1158 | `lighting/groups/LT-OUT-6/faults` | LT-OUT-6 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:31 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1159 | `lighting/groups/LT-OUT-6/faulty` | LT-OUT-6 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:31, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1160 | `lighting/groups/LT-OUT-6/scene` | LT-OUT-6 | P-08 | HelvarNet LP-3 >V:2,C:109,G:31# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1161 | `lighting/groups/LT-OUT-6/check` | LT-OUT-6 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1162 | `lighting/groups/LT-OUT-7/faults` | LT-OUT-7 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:32 (склад — C:164), маска 0x0800000E → кількість | int | шт | ×1 | 0 | > 0 → заявка | R-24 (C:110) | новий |
| 1163 | `lighting/groups/LT-OUT-7/faulty` | LT-OUT-7 | P-08 | HelvarNet LP-3 (router @1.3) C:110 по пристроях групи G:32, маска 0x0800000E → адреси несправних | text | — | — | «—» | — | R-24 (C:110) | новий |
| 1164 | `lighting/groups/LT-OUT-7/scene` | LT-OUT-7 | P-08 | HelvarNet LP-3 >V:2,C:109,G:32# (Query LSIG) / push C:11 | int | 1…16 | — | 0 (сцену не викликали) | — | R-24 | новий |
| 1165 | `lighting/groups/LT-OUT-7/check` | LT-OUT-7 | — | обчислює bms (R-19, `BMS-DERIVED`) — без адреси (X-34) | state | 6 текстів bms R-19 | — | — | — | обчислює bms | новий |
| 1166 | `equipment/CUTOPT/cmd` | CUTOPT | — | команда rest_vendor cutopt, власник machine_connect (джерело `REST-CUTOPT` → `/jobs` API-30…API-34, §8.6; X-18, X-76) — без адреси | state | — | — | — | — | власник machine_connect (команда; емулятор не веде) | новий |
| 1167 | `fire/groups/FA-SOC/state` | FA-SOC | P-09 | BACnet dev 200 LSZ:34 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |
| 1168 | `fire/groups/FA-OFFICE/state` | FA-OFFICE | P-09 | BACnet dev 200 LSZ:35 Present_Value (BACnetLifeSafetyState) | enum | quiet(0)/pre-alarm(1)/alarm(2)/fault(3)/… | — | quiet | alarm/fault → подія + заявка | R-25 пожежна панель | новий |

*Кінець Додатка A.*
