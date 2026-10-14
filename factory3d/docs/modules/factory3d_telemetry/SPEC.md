# factory3d_telemetry — специфікація

Версія 0.1 · 14.10.2026 · технічне рішення: `docs/modules/factory3d_telemetry/ARCHITECTURE.md` (далі ARCH:
FR-01…FR-30, CT-01…CT-11, A-01…A-20, Q-01…Q-13). Спирається на: каркас §5 (імена, стоп-крани, права), §6.4
(контракт телеметрії), §6.5 (плагіни; рішення менеджера 14.10 — `bacnet_ip` тут), §6.8 (заявки ТО), D-02,
D-04, D-07, D-11; `factory3d_base` CB-01, CB-07, CB-08, CB-09, CB-10, CB-11; `factory3d_viewer` M-01 (хук
провайдера), M-03 (`_notify`), API-03 (`patch.signals`), Додаток C (196 шляхів); `factory3d_iot_sim` §8.4
(Modbus, unit id), §8.8 (P-06), §8.9.3/§8.9.6 (P-07), §8.10.3 (BOILER BACnet), §8.11 (FACP read-only),
§8.13.2 (Axis LPV JSON), M-03 `f3d.sim.signal`, Додаток A (каталог 662 сигналів), API-01 `GET /f3d/sim/devices`.

Позначення: UT — юніт-тест `odoo.tests`; HT — `HttpCase`; CT — pytest колектора з фейковими серверами;
TC — стенд (емулятор + колектор + Odoo); MAN — ручна перевірка на тестовому сервері timur-o19demo
(база `odoo`). Odoo 19: SQL-обмеження — `models.Constraint`; хуки `post_init_hook(env)` /
`uninstall_hook(env)`; `fields.Json`; `request.make_json_response`. Рядки UI — українською в коді (D-14).

## 0. Дерево файлів модуля

### 0.1 Odoo-модуль `odoo_addons/factory3d_telemetry`

```
odoo_addons/factory3d_telemetry/
├── __init__.py                      from . import models, wizard, controllers, tools; from .hooks import post_init_hook, uninstall_hook
├── __manifest__.py                  §1
├── hooks.py                         post_init_hook(env), uninstall_hook(env), run_migration(env) — §5.3–§5.5
├── README.md                        установка, параметри, інструкції ARCH §4
├── CHANGELOG.md                     19.0.1.0.0 — перший випуск
├── models/
│   ├── __init__.py                  порядок: f3d_collector, f3d_source, f3d_signal, f3d_reading, f3d_reading_hour, f3d_command,
│   │                                f3d_push_event, push_handler, maintenance_equipment, maintenance_request, res_config_settings
│   ├── f3d_collector.py             M-01
│   ├── f3d_source.py                M-02
│   ├── f3d_signal.py                M-03 (+ _f3d_ingest CT-10, _f3d_import_sim_catalog CT-11)
│   ├── f3d_reading.py               M-04
│   ├── f3d_reading_hour.py          M-05
│   ├── f3d_command.py               M-06
│   ├── f3d_push_event.py            M-13
│   ├── push_handler.py              M-11 (AbstractModel f3d.push.handler, CT-08)
│   ├── maintenance_equipment.py     M-07
│   ├── maintenance_request.py       M-08
│   └── res_config_settings.py       M-09
├── wizard/
│   ├── __init__.py
│   ├── collector_token_wizard.py    M-12
│   └── collector_token_wizard_views.xml  V-03
├── controllers/
│   ├── __init__.py
│   └── telemetry.py                 API-01…API-07
├── tools/
│   ├── __init__.py
│   ├── address.py                   validate_address(type, address) / validate_params(type, params) — Додаток A (чисті функції)
│   ├── thresholds.py                eval_status(signal_state, value, text, ts) — R-04 (чиста функція, без ORM)
│   ├── ingest.py                    Ingester: валідація пакета, SQL-вставка показань, оновлення last_*, пороги, шина — R-17
│   ├── sim_catalog.py               parse_sim_address(protocol, text) → dict — R-24
│   ├── titles.py                    render_title(signal, value, rel, threshold) — R-05, таблиця шаблонів R-15
│   └── gen_signal_data.py           генератор data/signal_catalog.csv з Додатка A iot_sim (Odoo його не вантажить)
├── security/
│   ├── security.xml                 record rules §4.3
│   └── ir.model.access.csv          §4.1
├── data/
│   ├── ir_config_parameter.xml      §5.1 (noupdate="1")
│   ├── ir_cron.xml                  §6
│   ├── f3d_source_data.xml          7 джерел стенда (noupdate="1"), Додаток C
│   ├── signal_catalog.csv           56 рядків: 29 нових сигналів + 27 прив'язок мігрованих (читає хук, не в `data` маніфесту), Додаток C
│   ├── f3d_actions.xml              ir.actions.server «Повторити міграцію рівня 0»
│   └── neutralize.sql               §5.6
├── views/
│   ├── menus.xml                    V-22
│   ├── f3d_collector_views.xml      V-01, V-02
│   ├── f3d_source_views.xml         V-04…V-07
│   ├── f3d_signal_views.xml         V-08…V-12
│   ├── f3d_reading_views.xml        V-13…V-15
│   ├── f3d_reading_hour_views.xml   V-16
│   ├── f3d_command_views.xml        V-17
│   ├── f3d_push_event_views.xml     V-23
│   ├── maintenance_equipment_views.xml  V-18, V-19
│   ├── maintenance_request_views.xml    V-20
│   └── res_config_settings_views.xml    V-21
├── static/description/icon.png      іконка (антена над заводом; 140×140)
└── tests/
    ├── __init__.py
    ├── common.py                    F3DTelemetryCase(TransactionCase), F3DTelemetryHttpCase(HttpCase): фікстури §13.0
    ├── test_collector.py            AC-01…AC-03
    ├── test_source.py               AC-04…AC-06
    ├── test_signal.py               AC-07…AC-12
    ├── test_readings.py             AC-13…AC-18
    ├── test_thresholds.py           AC-19…AC-23
    ├── test_requests.py             AC-24…AC-27
    ├── test_meter.py                AC-28…AC-30
    ├── test_api.py                  AC-31…AC-39 (HttpCase)
    ├── test_commands.py             AC-40…AC-42
    ├── test_push_handler.py         AC-43, AC-44
    ├── test_migration.py            AC-45…AC-50
    ├── test_sim_catalog.py          AC-51, AC-52
    ├── test_security.py             AC-53…AC-56
    └── test_hooks.py                AC-57, AC-58
```

### 0.2 Міст-модуль `odoo_addons/factory3d_telemetry_viewer` (A-20)

```
odoo_addons/factory3d_telemetry_viewer/
├── __init__.py                      from . import models
├── __manifest__.py                  name "Завод 3D: телеметрія у переглядачі", depends ["factory3d_telemetry", "factory3d_viewer"],
│                                    auto_install True, version 19.0.1.0.0, author ToDo, license LGPL-3, data []
├── models/
│   ├── __init__.py
│   └── viewer_provider.py           M-10 f3d.viewer.provider.telemetry
└── tests/
    ├── __init__.py
    └── test_viewer_provider.py      AC-59…AC-61
```

### 0.3 Сервіс `services/collector`

```
services/collector/
├── README.md                        запуск, env, порти (коротко; повно — §8)
├── pyproject.toml                   пакет f3d_collector 0.1.0, Python 3.12; console_scripts f3d-collector = collector.__main__:main;
│                                    entry points [project.entry-points."factory3d_collector.plugins"]:
│                                    modbus_tcp = "collector.plugins.modbus_tcp:ModbusTcpPlugin", mqtt = "collector.plugins.mqtt:MqttPlugin",
│                                    http_push = "collector.plugins.http_push:HttpPushPlugin", bacnet_ip = "collector.plugins.bacnet_ip:BacnetIpPlugin"
├── requirements.txt                 §8.1.2
├── Dockerfile                       python:3.12-slim, user 10002 `collector`, HEALTHCHECK → GET http://127.0.0.1:9108/health
├── docker-compose.collector.yml     §8.1.4
├── .env.example                     усі F3D_* без секретів
├── collector/
│   ├── __init__.py                  __version__ = "0.1.0"
│   ├── __main__.py                  CLI: run | check-config | dump-config | test-source <code> | drain-buffer
│   ├── core/
│   │   ├── config.py                Settings (pydantic-settings), префікс F3D_ — §8.2
│   │   ├── types.py                 SourceCfg, SignalCfg, Reading, Health, Command, CommandResult, PushEvent — §8.3.1 (CT-02)
│   │   ├── registry.py              завантаження API-01, diff конфігурації за ETag, створення/зупинка плагінів
│   │   ├── scheduler.py             групи опитування за (source, period_s), джиттер, бекоф — R-19
│   │   ├── buffer.py                SQLite WAL: readings, events, results; ліміт F3D_BUFFER_MAX_MB — R-19
│   │   ├── odoo_client.py           aiohttp.ClientSession: config/push/status/event/commands/commands_result — §8.4
│   │   ├── commands.py              цикл команд (GET → plugin.write → POST result) — R-18
│   │   ├── allowlist.py             F3D_ALLOW_HOSTS: перевірка hostname/IP перед connect
│   │   ├── metrics.py               prometheus_client, HTTP :9108 (/metrics, /health)
│   │   ├── logging_conf.py          JSON-логи, SecretFilter
│   │   └── app.py                   збирання компонентів, graceful shutdown (SIGTERM → flush буфера ≤ 10 с)
│   ├── plugins/
│   │   ├── base.py                  SourcePlugin (ABC), PluginContext, load_plugins() — §8.3
│   │   ├── modbus_tcp.py            §8.5
│   │   ├── mqtt.py                  §8.6
│   │   ├── http_push.py             §8.7
│   │   ├── bacnet_ip.py             §8.8
│   │   └── schemas/                 address.<type>.json, params.<type>.json для 8 типів (= Додаток A; копія для jsonschema)
│   └── util/
│       ├── jsonpath.py              get(path, obj) для підмножини JSONPath: `$.a.b[0].c` — §8.6.2
│       ├── codec.py                 decode_registers(regs, type, wordorder, byteorder) / encode — R-20
│       └── timeutil.py              utcnow(), parse_iso(), to_iso_z()
├── state/                           buffer.sqlite (volume)
└── tests/
    ├── conftest.py                  фікстури: fake_odoo (aiohttp test server з API-01…API-07), modbus_server (pymodbus),
    │                                fake_mqtt (патч paho.Client), bacnet_device (bacpypes3 тестовий пристрій), tmp buffer
    ├── unit/
    │   ├── test_config.py, test_scheduler.py, test_buffer.py, test_odoo_client.py, test_commands.py, test_registry.py
    │   ├── test_codec.py, test_jsonpath.py, test_allowlist.py, test_logging.py
    │   └── test_plugin_modbus.py, test_plugin_mqtt.py, test_plugin_http_push.py, test_plugin_bacnet.py
    └── stand/                       ТК-01…ТК-12 (pytest -m stand проти compose iot_sim + collector + Odoo)
```

## 1. Маніфест

```python
{
    "name": "Завод 3D: телеметрія",
    "summary": "Джерела, сигнали, показання з обладнання; пороги → заявки ТО; ТО за лічильником; API колектора",
    "description": "Спільний хребет збору даних factory3d: f3d.collector, f3d.source, f3d.signal, f3d.reading, "
                   "f3d.reading.hour, f3d.command; ендпоінти /f3d/telemetry/*; плагіни колектора modbus_tcp, mqtt, "
                   "http_push, bacnet_ip (services/collector); міграція рівня 0 factory3d_iot_sim.",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["factory3d_base", "maintenance", "mail", "web"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",
        "data/f3d_source_data.xml",
        "data/f3d_actions.xml",
        "wizard/collector_token_wizard_views.xml",
        "views/f3d_collector_views.xml",
        "views/f3d_source_views.xml",
        "views/f3d_signal_views.xml",
        "views/f3d_reading_views.xml",
        "views/f3d_reading_hour_views.xml",
        "views/f3d_command_views.xml",
        "views/f3d_push_event_views.xml",
        "views/maintenance_equipment_views.xml",
        "views/maintenance_request_views.xml",
        "views/res_config_settings_views.xml",
        "views/menus.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
```

Порядок `data`: групи/правила → доступи → параметри → крони → джерела (посилаються на колектор
`collector_main` у тому ж файлі) → дії → майстер → представлення (дії вікон усередині) → меню.
`signal_catalog.csv` у `data` не перелічений — його читає хук через `odoo.tools.file_open` (як
`scene_*.csv` у base). Зовнішніх Python-залежностей в Odoo-модулі немає (валідація схем — власні
функції `tools/address.py`, без `jsonschema`). `maintenance` дає `maintenance.request/equipment/team/stage`;
`mail` — чаттер на колекторах, джерелах, сигналах.

## 2. Моделі

Спільні позначення: `req` = `required=True`; `idx` = `index=True`; усі `Datetime` — UTC naive (стандарт
Odoo); `Json` — `fields.Json`. Усі `_description` українською. Дані-Json у формах редагуються через парні
поля `*_text` (`compute`/`inverse`, widget `ace` з `mode: json`), помилка розбору — `ValidationError`.

### M-01 `f3d.collector` — колектор (CT-01)

```python
class F3dCollector(models.Model):
    _name = "f3d.collector"
    _description = "Телеметрія: колектор"
    _inherit = ["mail.thread"]
    _order = "code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,31}$")
```

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(32) | `req`, `idx`, `string="Код"`, `copy=False`, `tracking=True`; формат `CODE_RE` |
| `name` | Char(128) | `req`, `string="Назва"` |
| `active` | Boolean | `default=True` |
| `token_hash` | Char(64) | `string="Хеш токена"`, `groups="factory3d_base.group_f3d_admin"`, `copy=False`, `readonly=True`; sha256 hex |
| `token_hint` | Char(4) | `string="Останні символи токена"`, `groups=…group_f3d_admin`, `readonly=True` |
| `token_set_at` | Datetime | `string="Токен видано"`, `readonly=True` |
| `version` | Char(32) | `string="Версія"`, `readonly=True` (з API-03) |
| `last_seen` | Datetime | `string="Останній контакт"`, `readonly=True`, `idx` |
| `last_push_at` | Datetime | `string="Останній пакет"`, `readonly=True` |
| `last_ip` | Char(45) | `string="IP"`, `readonly=True` |
| `state` | Selection | `[('never','Ще не підключався'),('online','Онлайн'),('offline','Офлайн')]`, `default='never'`, `idx`, `tracking=True`, `readonly=True` (пише API-03 і крон R-25) |
| `status_interval_s` | Integer | `default=60`, `string="Період звіту стану, с"`; ≥ 10 |
| `push_interval_s` | Integer | `default=5`, `string="Період відправки, с"`; 1…60 |
| `push_max` | Integer | `default=1000`, `string="Показань у пакеті"`; 1…2000 |
| `config_poll_s` | Integer | `default=60`, `string="Період перечитування конфігурації, с"`; ≥ 10 |
| `uptime_s` | Integer | `readonly=True` |
| `buffer_rows` | Integer | `string="У буфері"`, `readonly=True` |
| `buffer_dropped` | Integer | `string="Втрачено з буфера"`, `readonly=True` |
| `plugins` | Json | `readonly=True` — `[{"type":"modbus_tcp","version":"0.1.0","sources":4}, …]` з API-03 |
| `config_etag` | Char(64) | `readonly=True` — останній виданий ETag |
| `rate_window_start` | Datetime | службове (R-17 ліміт частоти) |
| `rate_count` | Integer | службове |
| `source_ids` | One2many `f3d.source` `collector_id` | `string="Джерела"` |
| `source_count` | Integer | `compute="_compute_counts"` |
| `signal_count` | Integer | `compute="_compute_counts"` = `search_count([('source_id.collector_id','=',id)])` |
| `note` | Text | |

```python
    _f3d_collector_code_uniq = models.Constraint("UNIQUE(code)", "Код колектора має бути унікальним.")
    _f3d_collector_intervals = models.Constraint(
        "CHECK(status_interval_s >= 10 AND push_interval_s BETWEEN 1 AND 60 AND push_max BETWEEN 1 AND 2000 AND config_poll_s >= 10)",
        "Періоди колектора поза межами (статус ≥ 10 с, відправка 1…60 с, пакет 1…2000, конфігурація ≥ 10 с).")
```

`@api.constrains("code")`: `CODE_RE` → `ValidationError("Код колектора: великі латинські літери, цифри, дефіс (напр. COL-MAIN).")`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `action_generate_token(self)` | `ensure_one()`; перевірка `has_group('factory3d_base.group_f3d_admin')` інакше `AccessError`; `token = secrets.token_urlsafe(32)`; `write({'token_hash': hashlib.sha256(token.encode()).hexdigest(), 'token_hint': token[-4:], 'token_set_at': now})`; повідомлення в чаттер «Видано новий токен (…hint)»; повертає `act_window` на `f3d.collector.token.wizard` (`target='new'`, `context={'default_collector_id': id, 'default_token': token}`) |
| `action_revoke_token(self)` | `token_hash=False`, `token_hint=False`; чаттер «Токен відкликано» |
| `@api.model _authenticate(self, raw_token: str)` → recordset (0/1) | порожній/`len > 256` → порожньо; `h = sha256(raw).hexdigest()`; `cands = self.sudo().search([('active','=',True),('token_hash','!=',False)])`; повертає перший, для якого `hmac.compare_digest(c.token_hash, h)` (перебір усіх, без раннього виходу за `token_hash`) |
| `_touch(self, ip, version=None)` | `last_seen=now`, `last_ip=ip`, `version` якщо передано, `state='online'` якщо було інакше (без tracking-шуму: `with_context(mail_notrack=True)`) |
| `_config_payload(self)` → dict | API-01 (R-16) |
| `_etag(self)` → str | R-16 |
| `_rate_check(self)` → bool | R-17 п. 2 |
| `action_view_sources(self)` | `act_window` `f3d.source` `domain=[('collector_id','=',id)]`, `context={'default_collector_id': id}` |
| `_cron_offline(self)` | викликається з `cron_f3d_telemetry_stale`: `online` з `last_seen < now − 3·status_interval_s` → `offline`, усі його джерела `online/error` → `offline`, сигнали → R-07 |

### M-02 `f3d.source` — джерело даних (CT-01)

```python
class F3dSource(models.Model):
    _name = "f3d.source"
    _description = "Телеметрія: джерело даних"
    _inherit = ["mail.thread"]
    _order = "collector_id, code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-\.]{0,31}$")
    TYPES = [("modbus_tcp", "Modbus TCP"), ("mqtt", "MQTT"), ("http_push", "HTTP push (приймач)"),
             ("opcua", "OPC UA"), ("bacnet_ip", "BACnet/IP"), ("helvarnet", "HelvarNet"),
             ("sics", "SICS (ваги)"), ("rest_vendor", "REST вендора")]
    MODULES = [("telemetry", "Телеметрія"), ("machine_connect", "Верстати"), ("energy", "Енергетика"),
               ("genset", "Генератор"), ("bms", "Інженерні системи"), ("fire_safety", "Пожежна безпека"),
               ("yard", "Двір"), ("access", "СКУД"), ("other", "Інше")]
```

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(32) | `req`, `idx`, `string="Код"`, `copy=False`, `tracking=True`; `CODE_RE` |
| `name` | Char(128) | `req`, `string="Назва"` |
| `active` | Boolean | `default=True` |
| `type` | Selection `TYPES` | `req`, `string="Тип"`, `tracking=True` |
| `collector_id` | Many2one `f3d.collector` | `req`, `ondelete="restrict"`, `idx`, `string="Колектор"`, `tracking=True` |
| `equipment_id` | Many2one `maintenance.equipment` | `ondelete="set null"`, `string="Обладнання"`, `help="Головна одиниця обладнання (для дашборда)"` |
| `module` | Selection `MODULES` | `default="telemetry"`, `string="Модуль-власник"` |
| `params` | Json | `string="Параметри"`, `default=dict`; схема за типом — Додаток A.2 |
| `params_text` | Text | `compute="_compute_params_text"`, `inverse="_inverse_params_text"`, `string="Параметри (JSON)"` |
| `read_enabled` | Boolean | `default=True`, `string="Читати"`, `tracking=True` |
| `write_enabled` | Boolean | `default=False`, `string="Дозволити запис"`, `tracking=True` |
| `period_s_default` | Integer | `default=10`, `string="Період опитування за замовчуванням, с"`; ≥ 1 |
| `state` | Selection | `[('unknown','Невідомо'),('online','Онлайн'),('offline','Офлайн'),('error','Помилка'),('disabled','Вимкнено')]`, `default='unknown'`, `idx`, `readonly=True`, `tracking=True` |
| `last_ok` | Datetime | `readonly=True` |
| `last_error` | Char(512) | `readonly=True` |
| `error_count` | Integer | `readonly=True`, `default=0` |
| `stats` | Json | `readonly=True` — `{"polls": n, "errors": n, "latency_ms": x, "readings": n}` з API-03 |
| `signal_ids` | One2many `f3d.signal` `source_id` | |
| `signal_count` | Integer | `compute="_compute_counts"` |
| `alarm_count` | Integer | `compute="_compute_counts"` — сигнали `status='alarm'` |
| `stale_count` | Integer | `compute="_compute_counts"` — `status='stale'` |
| `note` | Text | |

```python
    _f3d_source_code_uniq = models.Constraint("UNIQUE(code)", "Код джерела має бути унікальним.")
    _f3d_source_period = models.Constraint("CHECK(period_s_default >= 1)", "Період опитування має бути ≥ 1 с.")
```

Перевірки (`@api.constrains("type", "params")`): `errors = tools.address.validate_params(type, params)`
→ непорожньо → `ValidationError("Параметри джерела %s: %s" % (code, "; ".join(errors)))`.
`@api.constrains("code")`: `CODE_RE` → `"Код джерела: великі латинські літери, цифри, дефіс, крапка."`.
`@api.constrains("type", "write_enabled")`: `type == 'bacnet_ip' and params.get('read_only') and write_enabled`
→ `"Джерело лише для читання (пожежна панель): запис заборонено."`. Зміна `type` при наявних сигналах
→ `ValidationError("Тип джерела з сигналами змінити не можна — створіть нове джерело.")`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `write(self, vals)` | якщо `'read_enabled' in vals and not vals['read_enabled']` → після `super()`: `state='disabled'`, сигнали → `_mark_stale('disabled')` (R-07); якщо `read_enabled` стає `True` → `state='unknown'`; будь-яка зміна `params/read_enabled/write_enabled/active/type` → `collector_id.config_etag=False` (змусити перевидати ETag) |
| `_apply_status(self, item: dict)` | з API-03: `state` ∈ {online, offline, error} (при `read_enabled=False` — лишається `disabled`), `last_ok`, `last_error[:512]`, `error_count`, `stats`; перехід у `offline/error` → `signal_ids._mark_stale(state)`; у `online` — нічого (сигнали оживуть від показань) |
| `action_view_signals(self)` | `act_window` `f3d.signal`, `domain=[('source_id','=',id)]`, `context={'default_source_id': id}` |
| `action_test_params(self)` | валідатор → `display_notification` «Параметри коректні» / помилки |
| `_default_address(self)` → dict | заготовка адреси для нового сигналу за типом (Додаток A.1, поле «приклад») |

### M-03 `f3d.signal` — сигнал (CT-01, §6.4 каркаса)

```python
class F3dSignal(models.Model):
    _name = "f3d.signal"
    _description = "Телеметрія: сигнал"
    _inherit = ["mail.thread"]
    _order = "sequence, code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^[a-z_]+(/[A-Za-z0-9_\-\.]+)+$")       # = iot_sim M-03
    KINDS = [("gauge", "Величина"), ("counter", "Лічильник"), ("state", "Стан"), ("event", "Подія")]
    STATUSES = [("unknown", "Невідомо"), ("ok", "Норма"), ("warn", "Увага"), ("alarm", "Тривога"), ("stale", "Немає даних")]
```

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(128) | `req`, `idx`, `string="Код (шлях)"`, `copy=False`, `tracking=True`; `CODE_RE`, ≤ 128 |
| `name` | Char(256) | `req`, `string="Назва"` |
| `sequence` | Integer | `default=10` |
| `active` | Boolean | `default=True` |
| `quantity` | Char(64) | `string="Величина"` (мок `x_kind`: «Потужність», «Тиск») |
| `kind` | Selection `KINDS` | `req`, `default="gauge"`, `string="Вид"`, `tracking=True` |
| `unit` | Char(32) | `string="Одиниця"` |
| `states` | Json | `string="Допустимі стани"`, список рядків; для `kind='state'` (порожньо = будь-який текст) |
| `equipment_id` | Many2one `maintenance.equipment` | `ondelete="set null"`, `idx`, `string="Обладнання"`, `tracking=True` |
| `equipment_code` | Char | `related="equipment_id.f3d_code"`, `string="Код обладнання"` |
| `workcenter_id` | Many2one `mrp.workcenter` | `ondelete="set null"`, `string="Робочий центр"` |
| `source_id` | Many2one `f3d.source` | `ondelete="set null"`, `idx`, `string="Джерело"`, `tracking=True` |
| `source_type` | Selection | `related="source_id.type"` |
| `collector_id` | Many2one `f3d.collector` | `related="source_id.collector_id"`, `store=True`, `idx` |
| `address` | Json | `string="Адреса в джерелі"`, `default=dict`; схема за `source_id.type` — Додаток A.1 |
| `address_text` | Text | `compute`/`inverse`, `string="Адреса (JSON)"` |
| `period_s` | Integer | `default=10`, `string="Період, с"`; ≥ 1 (для push-протоколів — очікуваний період, для `stale`) |
| `store_period_s` | Integer | `default=lambda self: int(self.env['ir.config_parameter'].sudo().get_param('factory3d.telemetry.default_store_period_s', '300'))`, `string="Зберігати не частіше, с"`; 0 = кожне показання |
| `scale` | Float | `digits=(16,6)`, `default=1.0`, `string="Множник"` — застосовує колектор після перетворення адреси (R-02) |
| `decimals` | Integer | `default=2`, `string="Знаків після коми"` |
| `nominal` | Float | `string="Номінал"` |
| `warn_low`, `warn_high`, `alarm_low`, `alarm_high` | Float | `string="Увага, нижче"`, `"Увага, вище"`, `"Тривога, нижче"`, `"Тривога, вище"`, `tracking=True` |
| `warn_low_on`, `warn_high_on`, `alarm_low_on`, `alarm_high_on` | Boolean | `default=False` — поріг задано (A-03: Float не відрізняє 0 від «немає») |
| `hysteresis` | Float | `default=0.0`, `string="Гістерезис"`, ≥ 0 |
| `min_duration_s` | Integer | `default=0`, `string="Мінімальна тривалість, с"`, ≥ 0 |
| `alarm_states` | Json | `string="Стани-тривоги"`, список рядків (для `kind='state'`) |
| `alarm_title` | Char(256) | `string="Заголовок заявки"`, шаблон з `{name} {equipment} {code} {value} {unit} {threshold} {rel} {text}` (R-05) |
| `alarm_priority` | Selection | `[('0','Дуже низький'),('1','Низький'),('2','Звичайний'),('3','Високий')]`, `default='2'` |
| `create_request` | Boolean | `default=True`, `string="Створювати заявку ТО"` |
| `write_enabled` | Boolean | `default=False`, `string="Дозволити запис"`, `tracking=True` |
| `viewer_visible` | Boolean | `default=True`, `string="Показувати в 3D"` (A-19) |
| `last_value` | Float | `string="Останнє значення"`, `readonly=True` |
| `last_text` | Char(64) | `string="Останній стан"`, `readonly=True` |
| `last_ts` | Datetime | `string="Час останнього"`, `readonly=True`, `idx` |
| `last_quality` | Selection | `[('good','Добра'),('uncertain','Непевна'),('bad','Погана')]`, `readonly=True` |
| `last_stored_ts` | Datetime | службове (R-03) |
| `status` | Selection `STATUSES` | `default="unknown"`, `idx`, `readonly=True`, `tracking=True` |
| `status_since` | Datetime | `readonly=True` |
| `breach_since` | Datetime | службове (R-04 мін. тривалість) |
| `maintenance_request_id` | Many2one `maintenance.request` | `ondelete="set null"`, `string="Відкрита заявка"`, `readonly=True`, `copy=False` |
| `request_closed_at` | Datetime | службове (R-06 cooldown) |
| `last_notified_ts` | Datetime | службове (R-13) |
| `origin` | Selection | `[('sim_data','Рівень 0 (макет)'),('catalog','Каталог емулятора'),('manual','Вручну')]`, `default='manual'`, `string="Походження"` |
| `module` | Selection `f3d.source.MODULES` | `default='telemetry'`, `string="Модуль-власник"`, `idx` |
| `derived_from_id` | Many2one `f3d.signal` | `ondelete="set null"`, `string="Похідний від"` |
| `derive_rule` | Selection | `[('none','—'),('rate_h','Швидкість за годину (Δ/Δt)')]`, `default='none'` (R-08) |
| `sim_mode` | Char(16) | `string="Режим макета"` (A-11) |
| `sim_params` | Json | `string="Параметри макета"` — `{"nominal", "noise", "rate", "limit", "alarm", "threshold", "seed"}` |
| `note` | Text | |
| `reading_count` | Integer | `compute="_compute_reading_count"` (не зберігається): `read_group` за 48 год |
| `meter_equipment_ids` | One2many `maintenance.equipment` `f3d_meter_signal_id` | `string="ТО за лічильником"` |

```python
    _f3d_signal_code_uniq = models.Constraint("UNIQUE(code)", "Код сигналу має бути унікальним.")
    _f3d_signal_periods = models.Constraint("CHECK(period_s >= 1 AND store_period_s >= 0 AND min_duration_s >= 0 AND hysteresis >= 0)",
                                            "Період ≥ 1 с, інтервал зберігання ≥ 0, тривалість і гістерезис ≥ 0.")
```

`@api.constrains`:
- `code` — `CODE_RE` → `ValidationError("Код сигналу %s: шлях виду energy/consumers/SAW-1/p_now (малі літери групи, далі сегменти через /).")`;
- `source_id`, `address` — якщо `source_id`: `errors = validate_address(source_id.type, address)` → `"Адреса сигналу %s: %s"`; без джерела адреса не перевіряється;
- пороги — `alarm_low_on and warn_low_on and alarm_low > warn_low` → `"«Тривога, нижче» має бути ≤ «Увага, нижче»."`; симетрично для `high` (`alarm_high < warn_high` заборонено); `alarm_low_on and alarm_high_on and alarm_low >= alarm_high` → `"«Тривога, нижче» має бути < «Тривога, вище»."`;
- `kind` — `kind='state'` з увімкненими числовими порогами → `"Для стану задайте «Стани-тривоги», а не числові пороги."`; `derive_rule='rate_h'` без `derived_from_id` або `derived_from_id.kind != 'counter'` → `"Похідна «за годину» потребує лічильника-джерела."`;
- `write_enabled` — `True` при `source_id.type == 'bacnet_ip' and source_id.params.get('read_only')` → `"Запис у пожежну панель заборонено (D-07)."`.

Методи (повні сигнатури; алгоритми — у §9):

| Сигнатура | Призначення |
|---|---|
| `@api.model _f3d_ingest(self, readings: list[dict], src: str = "module", collector=None) -> dict` | CT-10 / API-02: `readings = [{"code", "ts": datetime|str, "value": float|None, "text": str|None, "q": "good"}]`; повертає `{"accepted", "stored", "duplicates", "rejected": [{"i", "code", "reason"}], "changed_codes": [...]}`; алгоритм R-17 (`tools/ingest.Ingester`) |
| `_apply_reading(self, ts, value, text, quality) -> dict` | службово з Ingester (у пам'яті, без ORM-write): повертає нові значення полів `last_*`, `status*`, `breach_since` за R-03/R-04 |
| `_open_request(self, value, text, ts) -> maintenance.request` | R-05 |
| `_on_request_closed(self, request)` | R-06 (викликається з M-08) |
| `_mark_stale(self, reason: str)` | R-07: `status='stale'` (крім `unknown`), `status_since=now`, чаттер «Немає даних: <reason>» (один раз на перехід) |
| `_notify_viewer(self, codes: list[str])` | R-13: якщо `'f3d.viewer.event' in self.env` → `self.env['f3d.viewer.event']._notify('f3d.signal', codes, 'signal')` |
| `@api.model _f3d_import_sim_catalog(self, codes=None, module=None, source_map=None, defaults=None) -> dict` | CT-11, R-24: `{"created", "updated", "unparsed": [code], "skipped": [code]}` |
| `action_test_address(self)` | валідатор адреси → `display_notification` |
| `action_view_readings(self)` | `act_window` `f3d.reading` `domain=[('signal_id','=',id)]`, `context={'search_default_last_48h':1}`, `view_mode='graph,list'` |
| `action_open_request(self)` | відкрити `maintenance_request_id` |
| `action_request_write(self)` | відкрити форму нової `f3d.command` з `default_signal_id` (лише якщо `write_enabled`) |
| `name_get`-подібне `_compute_display_name` | `"%s (%s)" % (name, code)` |
| `write(self, vals)` | зміна `address`/`period_s`/`scale`/`source_id`/`active`/`write_enabled`/`states` → `collector_id.config_etag=False`; зміна порогів → `status` перераховується з `last_value` (R-04, без мін. тривалості); далі `super()` |
| `unlink(self)` | заборонено, якщо є `meter_equipment_ids` (`UserError("Сигнал використовується для ТО за лічильником на %s.")`); показання видаляються каскадно |

### M-04 `f3d.reading` — показання (CT-01)

```python
class F3dReading(models.Model):
    _name = "f3d.reading"
    _description = "Телеметрія: показання"
    _order = "ts desc, id desc"
    _log_access = False
    _rec_name = "ts"
```

| Поле | Тип | Параметри |
|---|---|---|
| `signal_id` | Many2one `f3d.signal` | `req`, `ondelete="cascade"`, `idx` |
| `equipment_id` | Many2one `maintenance.equipment` | `related="signal_id.equipment_id"`, `store=True`, `idx` |
| `ts` | Datetime | `req`, `string="Час"` |
| `value` | Float | `string="Значення"` (для `state` — індекс у `states`, −1 якщо текст поза списком; для `event` — 1) |
| `text` | Char(64) | `string="Текст"` (стан/подія) |
| `quality` | Selection | `[('good','Добра'),('uncertain','Непевна'),('bad','Погана')]`, `default='good'`, `req` |
| `src` | Selection | `[('collector','Колектор'),('sim_data','Рівень 0'),('module','Модуль'),('manual','Вручну')]`, `default='collector'`, `req` |
| `unit` | Char | `related="signal_id.unit"` |
| `code` | Char | `related="signal_id.code"` |

```python
    _f3d_reading_uniq = models.Constraint("UNIQUE(signal_id, ts)", "Показання для цього сигналу і часу вже є.")
```

`init(self)`: `CREATE INDEX IF NOT EXISTS f3d_reading_ts_idx ON f3d_reading (ts)` (ротація) — через
`tools.sql.create_index`. Індекс `(signal_id, ts)` створює унікальне обмеження. Створення — лише через
`Ingester` (SQL `INSERT … ON CONFLICT (signal_id, ts) DO NOTHING`) або ORM у тестах/хуку; у формах
`create="false"`. `write` заборонено (`UserError("Показання не редагуються.")`), крім `quality`
адміністратором.

### M-05 `f3d.reading.hour` — годинний агрегат (CT-01)

`_name = "f3d.reading.hour"`, `_description = "Телеметрія: годинний агрегат"`, `_order = "hour desc"`,
`_log_access = False`.

| Поле | Тип | Параметри |
|---|---|---|
| `signal_id` | Many2one `f3d.signal` | `req`, `ondelete="cascade"`, `idx` |
| `equipment_id` | Many2one | `related="signal_id.equipment_id"`, `store=True`, `idx` |
| `hour` | Datetime | `req`, `string="Година (UTC)"` — початок години |
| `v_min`, `v_avg`, `v_max`, `v_sum` | Float | |
| `v_count` | Integer | |
| `v_first`, `v_last` | Float | перше/останнє за `ts` |
| `delta` | Float | `v_last − v_first` для `kind='counter'`, інакше 0 (R-09) |

`_f3d_reading_hour_uniq = models.Constraint("UNIQUE(signal_id, hour)", "Агрегат за цю годину вже є.")`.
Заповнюється кроном R-09 через `INSERT … ON CONFLICT DO UPDATE`; у формах `create="false"`, `edit="false"`.

### M-06 `f3d.command` — команда на запис у пристрій (A-08, FR-21)

`_name = "f3d.command"`, `_description = "Телеметрія: команда на пристрій"`, `_order = "requested_at desc"`,
`_inherit = ["mail.thread"]`.

| Поле | Тип | Параметри |
|---|---|---|
| `signal_id` | Many2one `f3d.signal` | `req`, `ondelete="cascade"`, `idx`, `domain="[('write_enabled','=',True)]"` |
| `source_id` | Many2one `f3d.source` | `related="signal_id.source_id"`, `store=True`, `idx` |
| `collector_id` | Many2one `f3d.collector` | `related="signal_id.collector_id"`, `store=True`, `idx` |
| `value` | Float | `string="Значення"` |
| `text` | Char(64) | `string="Текст/стан"` (для `kind='state'`) |
| `state` | Selection | `[('queued','У черзі'),('sent','Передано колектору'),('done','Виконано'),('failed','Помилка'),('expired','Прострочено'),('cancelled','Скасовано')]`, `default='queued'`, `idx`, `tracking=True` |
| `requested_by` | Many2one `res.users` | `default=lambda self: self.env.user`, `readonly=True` |
| `requested_at` | Datetime | `default=fields.Datetime.now`, `readonly=True` |
| `expires_at` | Datetime | `default=lambda self: now + 10 хв`, `string="Дійсна до"` |
| `sent_at`, `done_at` | Datetime | `readonly=True` |
| `result` | Char(256) | `readonly=True` |
| `error` | Char(512) | `readonly=True` |
| `origin` | Char(32) | `string="Ініціатор"` (`manual`, ключ модуля) |
| `note` | Char(256) | |

Методи: `create(vals_list)` — для кожного: `sig = signal_id`; перевірки R-18 п. 1 (усі чотири прапори крім
колекторного; `AccessError`/`UserError` з текстами R-18); `action_cancel()` — лише `queued` → `cancelled`;
`_cron_expire()` — `queued/sent` з `expires_at < now` → `expired`. Запис `value` для `kind='state'`
обчислюється з `text` за `states` (індекс) — для плагінів, що пишуть числа (BACnet MSV).

### M-13 `f3d.push.event` — журнал подій http_push (FR-22)

`_name = "f3d.push.event"`, `_description = "Телеметрія: подія HTTP push"`, `_order = "ts desc"`,
`_log_access = False`.

| Поле | Тип | Параметри |
|---|---|---|
| `event_id` | Char(64) | `req`, `idx` — унікальний ідентифікатор від колектора |
| `route` | Char(32) | `req`, `idx` |
| `ts` | Datetime | `req`, `idx` |
| `collector_id` | Many2one `f3d.collector` | `ondelete="set null"` |
| `remote` | Char(64) | IP/хост відправника |
| `payload` | Json | тіло події |
| `handled_by` | Char(256) | імена моделей-обробників через кому |
| `error` | Char(512) | |
| `signal_count` | Integer | скільки показань породжено |

`_f3d_push_event_uniq = models.Constraint("UNIQUE(event_id)", "Подія з таким ідентифікатором уже є.")`.
Ротація — крон R-10 (`keep_days` ті самі).

### M-07 `maintenance.equipment` — розширення: сигнали, ТО за лічильником (CT-06)

```python
class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"
```

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_signal_ids` | One2many `f3d.signal` `equipment_id` | `string="Сигнали"` |
| `f3d_signal_count` | Integer | `compute="_compute_f3d_signal_counts"` — активні сигнали |
| `f3d_alarm_count` | Integer | `compute` — `status='alarm'` |
| `f3d_stale_count` | Integer | `compute` — `status='stale'` |
| `f3d_meter_signal_id` | Many2one `f3d.signal` | `string="Лічильник для ТО"`, `ondelete="set null"`, `domain="[('kind','=','counter'), '|', ('equipment_id','=',id), ('equipment_id','=',False)]"`, `tracking=True` |
| `f3d_meter_unit` | Char | `related="f3d_meter_signal_id.unit"` |
| `f3d_meter_interval` | Float | `digits=(12,1)`, `string="Інтервал ТО"`, `help="У одиницях лічильника: мотогодини, цикли, м³"` |
| `f3d_meter_last_value` | Float | `digits=(12,1)`, `string="Останнє ТО при показнику"` |
| `f3d_meter_last_date` | Date | `string="Дата останнього ТО"` |
| `f3d_meter_lead_pct` | Float | `default=lambda self: float(param('factory3d.telemetry.meter_lead_pct', '5'))`, `string="Планувати за, % інтервалу"` |
| `f3d_meter_next_value` | Float | `compute="_compute_f3d_meter"`, `store=True`: `last_value + interval` (0, якщо не задано) |
| `f3d_meter_current` | Float | `compute` (не зберігається): `f3d_meter_signal_id.last_value` |
| `f3d_meter_remaining` | Float | `compute` (не зберігається): `next_value − current` |
| `f3d_meter_request_id` | Many2one `maintenance.request` | `string="Планова заявка"`, `ondelete="set null"`, `readonly=True` |

`@api.constrains("f3d_meter_signal_id", "f3d_meter_interval")`: сигнал без інтервалу або інтервал ≤ 0 →
`ValidationError("Задайте інтервал ТО за лічильником (> 0).")`; сигнал іншого обладнання (не порожнього і не
цього) → `"Лічильник належить іншому обладнанню."`.

Методи: `_f3d_meter_check(self)` — R-11 (викликається з Ingester для обладнання, чий лічильник оновився);
`action_f3d_view_signals(self)` — `act_window` `f3d.signal` `domain=[('equipment_id','=',id)]`,
`context={'default_equipment_id': id, 'search_default_active': 1}`; `action_f3d_view_readings(self)` —
`f3d.reading` графік за 48 год, `domain=[('equipment_id','=',id)]`.

### M-08 `maintenance.request` — розширення (§6.8 каркаса, CT-05, CT-06)

```python
class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"
```

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_signal_id` | Many2one `f3d.signal` | `string="Сигнал"`, `ondelete="set null"`, `idx` |
| `f3d_equipment_code` | Char | `related="equipment_id.f3d_code"`, `store=True`, `string="Код обладнання"` |
| `f3d_origin` | Selection | `[('threshold','Поріг сигналу'),('meter','ТО за лічильником'),('stale','Немає даних'),('manual','Вручну')]`, `string="Джерело заявки"` |
| `f3d_value` | Float | `string="Показник при створенні"` |
| `f3d_threshold` | Float | `string="Поріг"` |
| `f3d_signal_status` | Selection | `related="f3d_signal_id.status"` |

`write(self, vals)`: `super()`; якщо `'stage_id' in vals`: для заявок, де `stage_id.done` стало `True`
(порівняння зі станом до запису) — `f3d_signal_id._on_request_closed(self)` (R-06) і, якщо
`f3d_origin == 'meter'`, `equipment_id._f3d_meter_closed(self)` (R-11 п. 5). Повторне відкриття
(`done → not done`) → сигнал знову отримує `maintenance_request_id = self` (R-06 п. 4).
Для `f3d_origin='threshold'` стандартна поведінка `maintenance_type='corrective'`; для `meter` —
`'preventive'`; `recurring_maintenance=False` завжди (повторність веде лічильник, не календар).

### M-09 `res.config.settings` — розширення

| Поле | Тип | `config_parameter` |
|---|---|---|
| `f3d_telemetry_read_enabled` | Boolean | `factory3d.telemetry.read_enabled` |
| `f3d_telemetry_write_enabled` | Boolean | `factory3d.telemetry.write_enabled` |
| `f3d_telemetry_keep_days` | Integer | `factory3d.telemetry.keep_days` |
| `f3d_telemetry_keep_hours_days` | Integer | `factory3d.telemetry.keep_hours_days` |
| `f3d_telemetry_default_store_period_s` | Integer | `factory3d.telemetry.default_store_period_s` |
| `f3d_telemetry_stale_periods` | Integer | `factory3d.telemetry.stale_periods` |
| `f3d_telemetry_stale_min_s` | Integer | `factory3d.telemetry.stale_min_s` |
| `f3d_telemetry_bus_min_interval_s` | Integer | `factory3d.telemetry.bus_min_interval_s` |
| `f3d_telemetry_realarm_cooldown_s` | Integer | `factory3d.telemetry.realarm_cooldown_s` |
| `f3d_telemetry_push_max_readings` | Integer | `factory3d.telemetry.push_max_readings` |
| `f3d_telemetry_push_rate_per_min` | Integer | `factory3d.telemetry.push_rate_per_min` |
| `f3d_telemetry_meter_lead_pct` | Float | `factory3d.telemetry.meter_lead_pct` |
| `f3d_telemetry_default_team_id` | Many2one `maintenance.team` | `factory3d.telemetry.default_team_id` (id як рядок; `get_values` читає `int(...)`) |
| `f3d_telemetry_drop_level0` | Boolean | `factory3d.telemetry.drop_level0` |
| `f3d_telemetry_level0_state` | Char | `compute`: `json.loads(param('level0_migrated','{}')).get('state','—')` (readonly) |
| `f3d_telemetry_collector_count` | Integer | `compute`: `search_count` активних колекторів |

Булеві параметри читаються `get_param(key, 'False') in ('True','true','1')` (як у base §5.1). Кнопки:
«Колектори» (`action_f3d_collector`), «Повторити міграцію рівня 0» (`action_f3d_run_migration`, лише
`group_f3d_admin`).

### M-10 `f3d.viewer.provider.telemetry` — провайдер переглядача (CT-07, міст-модуль A-20)

```python
class F3dViewerProviderTelemetry(models.AbstractModel):
    _name = "f3d.viewer.provider.telemetry"
    _inherit = "f3d.viewer.provider"
    _description = "3D: значення сигналів телеметрії"
    _f3d_sequence = 95
    _f3d_sections = ()
    _f3d_group = "factory3d_base.group_f3d_user"
```

- `_f3d_viewer_collect(self, payload, ctx)`: R-12 над усіма `f3d.signal` з `active=True`,
  `viewer_visible=True`, `status != 'unknown'` (поля `code`, `last_value`, `last_text`, `unit`, `kind`,
  `status`, `last_ts`); пише `meta.iot`.
- `_f3d_viewer_delta(self, patch, ctx)`: `codes = ctx['changes'].get('f3d.signal', set())`; якщо порожньо —
  нічого; інакше `patch['signals'] = [{"path": code, "value": <R-12 значення>} …]` для сигналів із `codes`
  (видимих), `patch.setdefault('meta', {})['iot'] = <R-12 meta.iot>`.
- `_f3d_viewer_bus_models(self)` → `['f3d.signal']`.

Провайдер M-01h viewer (над `x_f3d_signal`) після міграції не знаходить активних `x_`-записів
(`x_active=False`, §5.3 крок 6) — конфлікту немає; якщо міграцію не виконано (`partial`), обидва пишуть ті
самі шляхи, останнім — цей (95 > 90).

### M-11 `f3d.push.handler` — хук обробника подій http_push (CT-08)

```python
class F3dPushHandler(models.AbstractModel):
    _name = "f3d.push.handler"
    _description = "Телеметрія: обробник подій HTTP push"
    _f3d_push_routes = ()                      # напр. ("lpr",)

    def _f3d_handle_push(self, route: str, event: dict) -> None:
        """event = {"event_id", "route", "ts": datetime (UTC), "remote", "headers": {...}, "payload": {...}}"""
```

Реєстр обробників — скануванням `self.env.registry.descendants(['f3d.push.handler'], '_inherit')` мінус
абстрактна база (як viewer A-05); порядок — за `_name`. Виняток в обробнику логується
(`logger.exception`) і записується в `f3d.push.event.error`, інші обробники виконуються, транзакція не
відкочується (обробник працює в `savepoint`).

### M-12 `f3d.collector.token.wizard` — показ токена (Transient)

| Поле | Тип | Параметри |
|---|---|---|
| `collector_id` | Many2one `f3d.collector` | `req`, `readonly=True` |
| `token` | Char | `readonly=True`, `string="Токен (скопіюйте зараз — більше не показується)"` |
| `env_line` | Char | `compute`: `"F3D_COLLECTOR_CODE=%s\nF3D_COLLECTOR_TOKEN=%s" % (code, token)` |

Без збереження; форма `target='new'` з кнопкою «Закрити». Токен у `context` живе лише в межах одного
запиту (не логувати; `log_access` у Transient не містить `token` — поле не `tracking`).

## 3. Представлення й меню

Спільне: декорації сигналів у всіх списках — `decoration-danger="status == 'alarm'"`,
`decoration-warning="status == 'warn'"`, `decoration-muted="status in ('stale','unknown')"`; поле `status`
з `widget="badge"`. Рядки UI — українською в XML. Усі `Json`-поля — через `*_text` з `widget="ace"`
`options="{'mode': 'json'}"`.

| ID | XML-id | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `view_f3d_collector_list` | list `f3d.collector` | `code`, `name`, `state` (badge), `last_seen`, `version`, `source_count`, `signal_count`, `buffer_rows` (optional hide), `token_hint` (groups admin, optional hide); `decoration-success="state == 'online'"`, `decoration-danger="state == 'offline'"` |
| V-02 | `view_f3d_collector_form` | form | `<header>`: кнопки `action_generate_token` («Згенерувати токен», `btn-primary`, groups admin), `action_revoke_token` («Відкликати токен», groups admin, `invisible="not token_hash"`), статусбар `state`. Статбокс: `action_view_sources` (`source_count`, «Джерела»), `signal_count` («Сигнали», без дії). Заголовок: `name`; група «Ідентифікація»: `code`, `active` (toggle), `token_hint` (groups admin), `token_set_at`, `version`, `last_seen`, `last_push_at`, `last_ip`; група «Періоди»: `status_interval_s`, `push_interval_s`, `push_max`, `config_poll_s`; група «Стан сервісу» (readonly): `uptime_s`, `buffer_rows`, `buffer_dropped`, `config_etag`; вкладка «Плагіни» (`plugins` через `widget="json"` readonly), «Джерела» (`source_ids` readonly list: `code`, `name`, `type`, `state`, `signal_count`), «Примітка» (`note`); чаттер |
| V-03 | `view_f3d_collector_token_wizard_form` | form `f3d.collector.token.wizard` | `<div class="alert alert-warning">Токен показується один раз. Збережіть його в .env колектора.</div>`, `token` (widget `CopyClipboardChar`), `env_line` (widget `CopyClipboardText`), footer: «Закрити» (`special="cancel"`) |
| V-04 | `view_f3d_source_list` | list `f3d.source` | `code`, `name`, `type`, `collector_id`, `state` (badge), `read_enabled` (toggle, groups manager), `write_enabled` (toggle, groups manager), `signal_count`, `alarm_count`, `stale_count`, `last_ok`, `last_error` (optional hide), `module` (optional hide); декорації за `state` |
| V-05 | `view_f3d_source_form` | form | `<header>`: `action_test_params` («Перевірити параметри»), `action_view_signals` («Сигнали»), статусбар `state`. Статбокс: `signal_count`, `alarm_count` («Тривог», `decoration-danger`), `stale_count`. `name`; група «Джерело»: `code`, `type`, `collector_id`, `equipment_id`, `module`, `active`; група «Прапори»: `read_enabled`, `write_enabled` (`invisible="type == 'http_push'"`), `period_s_default`; група «Стан» (readonly): `last_ok`, `last_error`, `error_count`; вкладки: «Параметри» (`params_text` ace; під ним `<div class="text-muted">` з прикладом для типу — статичний текст у XML на кожен тип через `invisible="type != 'modbus_tcp'"` тощо, Додаток A.2), «Сигнали» (`signal_ids` list editable=bottom для менеджера: `code`, `name`, `kind`, `unit`, `period_s`, `status`, `last_value`, `last_ts`), «Статистика» (`stats` json readonly), «Примітка»; чаттер |
| V-06 | `view_f3d_source_kanban` | kanban (дашборд «Огляд») | `default_group_by="state"`, картка: `name`, `code`, `type`, `collector_id.code`, `signal_count`, кольорова мітка `alarm_count > 0` (червона), `stale_count > 0` (сіра), `last_ok`; клік — форма; `quick_create="false"` |
| V-07 | `view_f3d_source_search` | search | поля `name`, `code`, `collector_id`, `equipment_id`; фільтри: «Онлайн» (`state=online`), «Офлайн/помилка» (`state in (offline,error)`), «З тривогами» (`alarm_count > 0` — через `signal_ids.status = alarm`), «Вимкнені» (`read_enabled=False`), «Архівні»; group by `type`, `collector_id`, `module`, `state` |
| V-08 | `view_f3d_signal_list` | list `f3d.signal` | `default_order="sequence, code"`; `equipment_id`, `name`, `quantity` (optional hide), `last_value`, `unit`, `last_text` (optional hide), `status` (badge), `last_ts`, `maintenance_request_id` (optional show), `source_id` (optional show), `code` (optional hide), `kind` (optional hide), `module` (optional hide), `period_s` (optional hide), `origin` (optional hide), `active` (optional hide); декорації; multi-edit для менеджера |
| V-09 | `view_f3d_signal_form` | form | `<header>`: `action_view_readings` («Показання»), `action_test_address` («Перевірити адресу»), `action_open_request` («Заявка», `invisible="not maintenance_request_id"`), `action_request_write` («Записати в пристрій», `invisible="not write_enabled"`, groups manager), статусбар `status` (`statusbar_visible="ok,warn,alarm,stale"`). Статбокс: `reading_count` («Показань за 2 доби»). `name` (title); група «Зараз» (readonly): `last_value`, `unit`, `last_text`, `last_ts`, `last_quality`, `status_since`, `maintenance_request_id`; група «Звідки»: `code`, `equipment_id`, `workcenter_id`, `source_id`, `source_type` (readonly), `collector_id` (readonly), `kind`, `quantity`, `states_text`? — ні: `states` через `widget="json"`? — рішення: `states_text` (Char, compute/inverse, список через кому), `active`, `viewer_visible`, `module`, `origin` (readonly), `sequence`; група «Опитування»: `period_s`, `store_period_s`, `scale`, `decimals`, `nominal`, `write_enabled`; група «Пороги»: рядками `warn_low_on` + `warn_low` (`invisible="not warn_low_on"` на числі — обидва в одному `<div class="o_row">`), так само `warn_high`, `alarm_low`, `alarm_high`; `hysteresis`, `min_duration_s`, `alarm_states_text` (Char compute/inverse, через кому; `invisible="kind != 'state'"`), `alarm_title`, `alarm_priority`, `create_request`; вкладки: «Адреса» (`address_text` ace + статична підказка за `source_type`), «Похідна» (`derived_from_id`, `derive_rule`), «Макет» (`sim_mode`, `sim_params_text` readonly), «ТО за лічильником» (`meter_equipment_ids` readonly: `name`, `f3d_meter_interval`, `f3d_meter_next_value`), «Примітка»; чаттер. Поля порогів/адреси/джерела — `readonly="not is_f3d_manager"` (поле `is_f3d_manager` Boolean compute додати в M-03 як у base M-01) |
| V-10 | `view_f3d_signal_graph` | graph `f3d.signal` | `type="bar"`, `last_value` measure, рядок `equipment_id` — для швидкого огляду «що зараз» |
| V-11 | `view_f3d_signal_pivot` | pivot | рядки `equipment_id`, стовпці `status`, міра `__count` |
| V-12 | `view_f3d_signal_search` | search | поля `name`, `code`, `equipment_id`, `source_id`; фільтри «Тривога» (`status=alarm`), «Увага», «Немає даних» (`stale`), «Без джерела» (`source_id=False`), «Увімкнені» (`active=True`, default), «Мій модуль» відсутній; group by `equipment_id`, `source_id`, `module`, `kind`, `status` |
| V-13 | `view_f3d_reading_graph` | graph `f3d.reading` | `type="line"`, `<field name="ts" interval="hour"/>`, `<field name="signal_id"/>`, `<field name="value" type="measure"/>`; `stacked="0"` (як мок `view_reading_graph`) |
| V-14 | `view_f3d_reading_list` | list | `create="false"`, `edit="false"`, `default_order="ts desc"`: `ts`, `equipment_id`, `signal_id`, `value`, `text`, `unit`, `quality` (optional hide), `src` (optional hide) |
| V-15 | `view_f3d_reading_search` | search | поля `signal_id`, `equipment_id`, `code`; фільтри «Останні 2 доби» (`last_48h`: `ts >= now − 48h`, default через контекст дії), «Сьогодні», «7 днів», «Непевні/погані» (`quality != good`); group by `signal_id`, `equipment_id`, `ts:day` |
| V-16 | `view_f3d_reading_hour_pivot` / `_graph` / `_list` | `f3d.reading.hour` | pivot: рядки `signal_id`, стовпці `hour:day`, міри `v_avg`, `v_min`, `v_max`, `delta`; graph line `hour`/`v_avg`; list readonly |
| V-17 | `view_f3d_command_list` / `_form` | `f3d.command` | list: `requested_at`, `signal_id`, `value`, `text`, `state` (badge), `requested_by`, `sent_at`, `done_at`, `error`; form: `signal_id`, `value`, `text` (`invisible="signal_kind != 'state'"` — related `signal_kind`), `expires_at`, `note`, група readonly результату; кнопка `action_cancel` (`invisible="state != 'queued'"`); `<div class="alert alert-info">` «Команда виконається, лише якщо запис дозволено на модулі, джерелі, сигналі й у колекторі» |
| V-18 | `view_maintenance_equipment_form_f3d_signals` | form inherit `maintenance.hr_equipment_view_form` | `//div[@name='button_box']` inside: статкнопки `action_f3d_view_signals` (`f3d_signal_count`, «Сигнали», `fa-rss`), `f3d_alarm_count` («Тривоги», `fa-bell`, `invisible="not f3d_alarm_count"`, клас `text-danger`); `//notebook` inside: `<page name="f3d_signals" string="Сигнали" invisible="not f3d_signal_count and not f3d_meter_signal_id">`: список `f3d_signal_ids` readonly (`quantity`, `name`, `last_value`, `unit`, `last_text`, `status` badge, `last_ts`, `maintenance_request_id`; `decoration-danger="status == 'alarm'"`), кнопка `action_f3d_view_readings` («Графік за 2 доби»); група «ТО за лічильником»: `f3d_meter_signal_id`, `f3d_meter_unit`, `f3d_meter_interval`, `f3d_meter_last_value`, `f3d_meter_last_date`, `f3d_meter_lead_pct`, `f3d_meter_current` (readonly), `f3d_meter_next_value` (readonly), `f3d_meter_remaining` (readonly, `decoration-danger="f3d_meter_remaining <= 0"`), `f3d_meter_request_id` (readonly). Це заміна `factory3d_iot_sim.view_equipment_form_signals` (та ж назва сторінки `f3d_signals`; мок-представлення деактивується хуком) |
| V-19 | `view_maintenance_equipment_list_f3d_signals` / `_search` | inherit `maintenance.hr_equipment_view_tree` / `hr_equipment_view_search` | list: `f3d_alarm_count` (optional show), `f3d_signal_count` (optional hide); search: фільтри «З тривогами» (`f3d_signal_ids.status = alarm`), «Є сигнали» (`f3d_signal_ids != False`), «ТО за лічильником» (`f3d_meter_signal_id != False`) |
| V-20 | `view_maintenance_request_form_f3d` / `_list_f3d` / `_search_f3d` | inherit `maintenance.hr_equipment_request_view_form` / `hr_equipment_request_view_tree` / `hr_equipment_request_view_search` | form: після `equipment_id` група «Телеметрія» (`invisible="not f3d_signal_id"`): `f3d_signal_id`, `f3d_signal_status`, `f3d_origin`, `f3d_value`, `f3d_threshold`; list: `f3d_origin` (optional hide), `f3d_equipment_code` (optional hide); search: фільтр «З телеметрії» (`f3d_signal_id != False`), group by `f3d_origin` |
| V-21 | `res_config_settings_view_form_f3d_telemetry` | inherit `base.res_config_settings_view_form` | блок `app_settings_block` `data-string="Завод 3D"` (спільний блок base, якщо є — `xpath //block[@name='factory3d_base_settings']`, інакше власний `name="factory3d_telemetry_settings"`): «Телеметрія»: `f3d_telemetry_read_enabled` («Приймати показання»), `f3d_telemetry_write_enabled` («Дозволяти команди на пристрої»), `f3d_telemetry_collector_count` + кнопка «Колектори»; «Зберігання»: `keep_days`, `keep_hours_days`, `default_store_period_s`; «Пороги й заявки»: `stale_periods`, `stale_min_s`, `realarm_cooldown_s`, `meter_lead_pct`, `default_team_id`; «API»: `push_max_readings`, `push_rate_per_min`, `bus_min_interval_s`; «Рівень 0»: `f3d_telemetry_level0_state` (readonly), `f3d_telemetry_drop_level0`, кнопка «Повторити міграцію рівня 0» (groups admin) |
| V-22 | меню та дії (`views/menus.xml`) | `ir.ui.menu`, `ir.actions.act_window` | таблиця нижче |
| V-23 | `view_f3d_push_event_list` / `_form` | `f3d.push.event` | list readonly: `ts`, `route`, `remote`, `handled_by`, `signal_count`, `error`; form readonly з `payload` (json) |

Меню (CB-09, sequence 30 під `factory3d_base.menu_f3d_root`):

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_f3d_telemetry` | Телеметрія | `factory3d_base.menu_f3d_root` | 30 | `group_f3d_user` | — |
| `menu_f3d_telemetry_overview` | Огляд | `menu_f3d_telemetry` | 10 | `group_f3d_user` | `action_f3d_source_overview` (`f3d.source`, kanban,list,form; `context={'search_default_group_state': 1}`) |
| `menu_f3d_telemetry_signal` | Сигнали | `menu_f3d_telemetry` | 20 | `group_f3d_user` | `action_f3d_signal` (list,form,graph,pivot; `context={'search_default_active': 1, 'search_default_group_equipment': 1}`) |
| `menu_f3d_telemetry_reading` | Показання | `menu_f3d_telemetry` | 30 | `group_f3d_user` | `action_f3d_reading` (graph,list; `context={'search_default_last_48h': 1}`; `domain=[]`) |
| `menu_f3d_telemetry_reading_hour` | Годинні агрегати | `menu_f3d_telemetry` | 35 | `group_f3d_user` | `action_f3d_reading_hour` (pivot,graph,list) |
| `menu_f3d_telemetry_source` | Джерела | `menu_f3d_telemetry` | 40 | `group_f3d_manager` | `action_f3d_source` (list,form,kanban) |
| `menu_f3d_telemetry_collector` | Колектори | `menu_f3d_telemetry` | 50 | `group_f3d_admin` | `action_f3d_collector` (list,form) |
| `menu_f3d_telemetry_command` | Команди | `menu_f3d_telemetry` | 60 | `group_f3d_manager` | `action_f3d_command` (list,form) |
| `menu_f3d_telemetry_push_event` | Події HTTP push | `menu_f3d_telemetry` | 70 | `group_f3d_manager` | `action_f3d_push_event` (list,form) |
| `menu_f3d_telemetry_config` | Налаштування телеметрії | `factory3d_base.menu_f3d_config` | 30 | `group_f3d_admin` | `action_f3d_telemetry_settings` (`res.config.settings`, `context={'module': 'factory3d_telemetry'}`) |

Додатково для механіка: `menu_f3d_telemetry_maint` «Телеметрія» під `maintenance.menu_maintenance_title`
(`sequence=6`, групи `group_f3d_user`, дія `action_f3d_signal` з `context={'search_default_alarm': 1}`) —
на місце мок-меню «Імітація IoT» (`sequence=5`, деактивується хуком).

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_f3d_collector_user,f3d.collector user,model_f3d_collector,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_collector_admin,f3d.collector admin,model_f3d_collector,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_source_user,f3d.source user,model_f3d_source,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_source_manager,f3d.source manager,model_f3d_source,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_signal_user,f3d.signal user,model_f3d_signal,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_signal_manager,f3d.signal manager,model_f3d_signal,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_reading_user,f3d.reading user,model_f3d_reading,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_reading_manager,f3d.reading manager,model_f3d_reading,factory3d_base.group_f3d_manager,1,0,1,0
access_f3d_reading_admin,f3d.reading admin,model_f3d_reading,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_reading_hour_user,f3d.reading.hour user,model_f3d_reading_hour,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_reading_hour_admin,f3d.reading.hour admin,model_f3d_reading_hour,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_command_user,f3d.command user,model_f3d_command,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_command_manager,f3d.command manager,model_f3d_command,factory3d_base.group_f3d_manager,1,1,1,0
access_f3d_command_admin,f3d.command admin,model_f3d_command,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_push_event_user,f3d.push.event user,model_f3d_push_event,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_push_event_admin,f3d.push.event admin,model_f3d_push_event,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_collector_token_wizard_admin,f3d.collector.token.wizard admin,model_f3d_collector_token_wizard,factory3d_base.group_f3d_admin,1,1,1,1
```

Абстрактні `f3d.push.handler`, `f3d.viewer.provider.telemetry` рядків не потребують. Контролери
працюють `sudo()` після перевірки токена. Поля `f3d_*` на `maintenance.equipment`/`maintenance.request` —
за правами цих моделей (`maintenance.group_equipment_manager` редагує ТО за лічильником; поля
`f3d_signal_id`, `f3d_origin`, `f3d_value`, `f3d_threshold` на заявці — `readonly` у формі, пише модуль).

### 4.2 Групи

Нових груп немає — CB-10 (`group_f3d_user/manager/admin`). У `security/security.xml` — лише правила.

### 4.3 Record rules (`security/security.xml`)

| XML-id | Модель | Домен | Групи |
|---|---|---|---|
| `f3d_reading_rule_all` | `f3d.reading` | `[(1,'=',1)]` | глобальне (без компанії: показання не мультикомпанійні) |
| `f3d_command_rule_own_or_manager` | `f3d.command` | `['|', ('requested_by','=',user.id), ('signal_id.module','!=',False)]` — фактично всім; правило-заготовка для майбутнього обмеження за модулем | `group_f3d_user` |

Компанії: моделі модуля без `company_id` (завод один; CB-10 base теж без компанії для паспортів).

### 4.4 Захист полів

- `f3d.collector.token_hash/token_hint` — `groups=group_f3d_admin` (невидимі й не читаються іншими навіть
  через `read`); `_authenticate` — `sudo()`.
- `f3d.signal.write`: зміна `write_enabled`, `source_id`, `address`, порогів — лише `group_f3d_manager`
  (через ACL — user має лише читання); `status`, `last_*`, `maintenance_request_id` — `readonly=True` у
  полі, пише лише код (`sudo` в Ingester).
- `f3d.command.create` — `group_f3d_manager` + R-18 п. 1; `unlink` — лише admin.

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)

| key | value | XML-id | Примітка |
|---|---|---|---|
| `factory3d.telemetry.read_enabled` | `True` | `param_read_enabled` | хук перезаписує за CB-10: `environment == 'test'` → `True`, інакше `False` |
| `factory3d.telemetry.write_enabled` | `False` | `param_write_enabled` | |
| `factory3d.telemetry.keep_days` | `30` | `param_keep_days` | |
| `factory3d.telemetry.keep_hours_days` | `400` | `param_keep_hours_days` | |
| `factory3d.telemetry.default_store_period_s` | `300` | `param_default_store_period` | |
| `factory3d.telemetry.stale_periods` | `3` | `param_stale_periods` | |
| `factory3d.telemetry.stale_min_s` | `60` | `param_stale_min_s` | |
| `factory3d.telemetry.bus_min_interval_s` | `10` | `param_bus_min_interval` | |
| `factory3d.telemetry.realarm_cooldown_s` | `3600` | `param_realarm_cooldown` | |
| `factory3d.telemetry.push_max_readings` | `2000` | `param_push_max` | |
| `factory3d.telemetry.push_rate_per_min` | `60` | `param_push_rate` | |
| `factory3d.telemetry.meter_lead_pct` | `5` | `param_meter_lead_pct` | |
| `factory3d.telemetry.default_team_id` | `` (порожньо) | `param_default_team` | хук: id команди «Служба головного механіка», якщо є, інакше перша `maintenance.team` |
| `factory3d.telemetry.drop_level0` | `False` | `param_drop_level0` | |
| `factory3d.telemetry.level0_migrated` | `{}` | `param_level0_migrated` | звіт хука |
| `factory3d.telemetry.stale_notify_min` | `0` | `param_stale_notify_min` | зарезервовано (Q-11), 0 = вимкнено |

### 5.2 `data/f3d_source_data.xml` (`noupdate="1"`) і `data/signal_catalog.csv`

Колектор `collector_main`: `code=COL-MAIN`, `name="Основний колектор (стенд)"`, без токена (видає
адміністратор майстром). Джерела — Додаток C.1 (7 записів, xml-id `source_<slug>`: `source_mqtt_mobile`,
`source_mb_u70_compressor`, `source_mb_u84_io5`, `source_mb_u90_ai1`, `source_mb_u96_rtd1`,
`source_bac_140_boiler`, `source_http_push`), усі `collector_id=collector_main`, `read_enabled=True`,
`write_enabled=False`, `module='telemetry'`.

`data/signal_catalog.csv` (56 рядків; генерує `tools/gen_signal_data.py` з Додатка A iot_sim і Додатка C
цього документа; детерміновано): колонки `code,name,quantity,kind,unit,equipment,workcenter,source,address,
period_s,store_period_s,scale,decimals,nominal,warn_low,warn_high,alarm_low,alarm_high,alarm_states,alarm_title,
hysteresis,min_duration_s,states,viewer_visible,derived_from,derive_rule,origin,module,sim_mode,sim_params,
new`. `new=1` — 29 нових сигналів (створюються); `new=0` — 27 прив'язок мігрованих (оновлюються лише поля
`source`, `address`, `period_s`, `store_period_s`, пороги/`alarm_title`/`hysteresis`, якщо колонка непорожня;
`last_*` не чіпаються). Порожня колонка = «не змінювати». Повний зміст — Додаток C.2.

### 5.3 `post_init_hook(env)` — кроки, джерела, ідемпотентність, очікувані кількості

`hooks.run_migration(env) -> dict` виконує кроки; `post_init_hook = run_migration + звіт`. Усе в транзакції
установки; виняток на кроці 1–5, 8 відкочує установку; крок 6 виконується лише при `mismatches == []`.
Логер `odoo.addons.factory3d_telemetry.hooks`, INFO з лічильниками на кожен крок.

| # | Функція | Джерело | Що робить | Ідемпотентність | Очікувано (копія демо 14.10, 7 840 показань) | Чиста база |
|---|---|---|---|---|---|---|
| 1 | `params(env)` | CB-10 | `read_enabled = (environment == 'test')`; `default_team_id` = id `maintenance.team` з `name='Служба головного механіка'` або перший | перезапис лише порожніх/дефолтних | `read_enabled=True`, `team=2` | `True`/перша команда |
| 2 | `signals_level0(env)` | `x_f3d_signal` (ORM, `sudo`, `active_test=False`) | якщо `'x_f3d_signal' not in env` → `skipped`; інакше для кожного запису (порядок `x_sequence, id`, щоб джерела `x_source_id` створювались раніше): `vals` за Додатком D; `search([('code','=',x_code)])` → `write` (лише поля визначення, не `last_*`, якщо запис уже `origin='sim_data'`) або `create`; xml-id `factory3d_telemetry.sig_<slug>` (`slug` = `plant/odoo_rpc.key(x_code)`); другий прохід — `derived_from_id` за `x_source_id` | upsert за `code` | `signals_migrated: 196`, `created: 196`, `alarm: 1`, `with_request: 2`, `by_module: {energy: 84, bms: 81, fire_safety: 1, telemetry: 27, machine_connect: 0, genset: 0}`; `infra/*` 3 → energy | `skipped` |
| 3 | `signals_catalog(env)` | `data/signal_catalog.csv` | `new=1` → `create` (`origin='catalog'`), якщо коду ще немає; усі рядки — `write` непорожніх колонок прив'язки; `source` → `search([('code','=',source)])`; `equipment` → `env['maintenance.equipment'].search_f3d(code)` (CB-01), немає → WARNING і без обладнання | upsert | `created: 29`, `bound: 55`, `no_equipment: 0` (усі коди є в демо: FL-*, TUGGER-1, COMPRESSOR, DUST-1, T1, T2, WATER, SPRINKLERS, AIR-RING, BOILER) | `created: 29`, `bound: 55`, `no_equipment: 29…` (без обладнання — WARNING) |
| 4 | `sim_catalog(env)` | `f3d.sim.signal` (iot_sim 19.0.2.0.0) | якщо моделі немає → `skipped`; інакше `_f3d_import_sim_catalog(codes=<225 кодів моєї зони>, source_map=Додаток C.3, defaults={'origin': keep})` — заповнює `address`, якщо порожня, `sim_params`, `nominal`; не змінює `source_id`, якщо вже є | upsert | на демо з data-модулем 19.0.1.0.0 — `skipped` | `skipped` |
| 5 | `readings_level0(env)` | `x_f3d_reading` | батчами по 5 000: `SELECT r.id, r.x_signal_id, r.x_value, r.x_time FROM x_f3d_reading r ORDER BY id` → `execute_values("INSERT INTO f3d_reading (signal_id, equipment_id, ts, value, quality, src) VALUES %s ON CONFLICT (signal_id, ts) DO NOTHING")` із `signal_id` за мапою крок 2; `x_time` NULL → пропуск | `ON CONFLICT` | `readings_migrated: 7 840` (кількість на момент установки; ≤ 56 448 за 2 доби), `skipped_null_ts: 0` | `skipped` |
| 6 | `requests_level0(env)` | `maintenance.request` із `x_request_id` | для сигналів з `maintenance_request_id`: `request.write({'f3d_signal_id', 'f3d_origin': 'threshold', 'f3d_value': last_value, 'f3d_threshold': alarm_*})`; якщо `request.stage_id.done` → сигнал `maintenance_request_id=False`, `request_closed_at=request.write_date` | перезапис | `requests_linked: 2` (id 6 RV-05, id 5 FA-FAC — обидві відкриті) | `skipped` |
| 7 | `hours_rebuild(env)` | `f3d.reading` | R-09 за всіма годинами, де є показання, але немає агрегату | upsert | `hours: ≈ 1 400` (196 × 7 год) | 0 |
| 8 | `verify(env)` | кроки 2, 5 | `count(f3d.signal, origin=sim_data) == count(x_f3d_signal)`; для кожного — `abs(last_value − x_value) < 1e-6` і `status` відповідає `x_state`; `count(f3d.reading, src=sim_data) == count(x_f3d_reading з x_time)`; рядки розбіжностей `"<code>: last_value 304.241 != x_value 304.000"` | — | `mismatches: []` | `[]` |
| 9 | `level0_off(env)` | `ir.cron`, `ir.ui.menu`, `ir.ui.view`, `x_f3d_signal`, `ir.config_parameter` | лише якщо `mismatches == []`: `cron_iot_sim.active=False` (`env.ref('factory3d_iot_sim.cron_iot_sim', raise_if_not_found=False)`); `cr.execute("UPDATE x_f3d_signal SET x_active = false")`; меню `factory3d_iot_sim.menu_iot_root` → `active=False` (діти ховаються з батьком); представлення `factory3d_iot_sim.view_equipment_form_signals` → `active=False`; параметр `factory3d.iot_sim.level0_enabled` (якщо існує) → `False` | повторно — без змін | `cron_off: True`, `x_inactive: 196`, `menu_off: 1`, `view_off: 1`, `iot_sim_param: True/False` | `skipped` |
| 10 | `drop_level0(env)` | параметр `drop_level0` | лише якщо `True` і `mismatches == []`: `ir.ui.view` рівня 0 (7 за xml-id `factory3d_iot_sim.view_*`) `unlink`; `drop_manual_fields(env, 'maintenance.equipment', ['x_f3d_signal_ids'])` (CB-11); `env['ir.model'].search([('model','in',['x_f3d_reading','x_f3d_signal'])]).unlink()` (спершу reading — FK); меню рівня 0 `unlink` | повторно — нічого | за замовчуванням `skipped` | `skipped` |
| 11 | `report(env, report)` | — | `level0_migrated = json.dumps({state, ts, ...лічильники, mismatches})`; `state` = `skipped` (крок 2 skipped) / `partial` (`mismatches`) / `done` | перезапис | `done` | `skipped` |

Загалом після установки на копії демо: `f3d.signal` **225** (196 `sim_data` + 29 `catalog`), з них із
`source_id` **55**, без джерела 170 (169 чужих + `infra/water/flow_m3h` похідна), `status`: `alarm` 1
(`ventilation/units/RV-05/filter_dp_pa`), `ok` 195, `unknown` 29 (нові — до першого показання); `f3d.source` 7;
`f3d.collector` 1; `f3d.reading` = кількість `x_f3d_reading`; `maintenance.request` з `f3d_signal_id` — 2.

`action_f3d_run_migration` (`data/f3d_actions.xml`, `ir.actions.server` на `f3d.signal`,
`code="action = env['f3d.signal'].f3d_run_migration()"`): метод `@api.model f3d_run_migration(self)` —
`AccessError` без `group_f3d_admin`; інакше `hooks.run_migration(self.env)` і `display_notification` зі
звітом (`sticky=True`).

### 5.4 `uninstall_hook(env)`

1. Крони модуля — видаляються з модулем; тут: `f3d.command` у `queued/sent` → нічого (таблиця зникне).
2. Якщо `'x_f3d_signal' in env`: `cr.execute("UPDATE x_f3d_signal SET x_active = true")`; меню
   `factory3d_iot_sim.menu_iot_root`, представлення `view_equipment_form_signals` → `active=True`; крон
   `cron_iot_sim` **не** вмикається (лог WARNING «рівень 0 вимкнено; увімкніть вручну або через пульт»).
3. `ir.config_parameter` `factory3d.telemetry.*` → `unlink`; `factory3d.iot_sim.level0_enabled` не чіпається.
4. `maintenance.request` лишаються (поля `f3d_*` зникають з модулем); `f3d.reading`, `f3d.reading.hour`,
   `f3d.push.event` — видаляються з моделями (технічні журнали, як iot_sim A-11); `f3d.signal`,
   `f3d.source`, `f3d.collector` — теж (визначення відтворюються з data/міграції при повторній установці).

### 5.5 Повторна установка

`post_init_hook` на базі, де рівень 0 уже архівовано (`x_active=False`): крок 2 читає з
`active_test=False` → 196 знову; `last_value` беруться з `x_value` (застарілі) **лише** якщо сигнал
створюється; крок 9 повторно вимикає рівень 0; показання `ON CONFLICT` — без дублікатів.

### 5.6 `data/neutralize.sql`

```sql
-- factory3d_telemetry: нейтралізація копії проду (CB-10, каркас §5)
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('factory3d.telemetry.read_enabled', 'factory3d.telemetry.write_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'factory3d_telemetry';
UPDATE f3d_source SET read_enabled = false, write_enabled = false, state = 'disabled';
UPDATE f3d_collector SET token_hash = NULL, token_hint = NULL, state = 'never';
UPDATE f3d_command SET state = 'expired' WHERE state IN ('queued', 'sent');
UPDATE f3d_signal SET write_enabled = false;
```

## 6. Крони й фонові процеси (`data/ir_cron.xml`)

| XML-id | Назва | Інтервал | Модель / метод | Один прогін | Ліміти |
|---|---|---|---|---|---|
| `cron_f3d_telemetry_stale` | Телеметрія: застарілі сигнали й офлайн-колектори | 1 хв, `active=True` | `f3d.signal._cron_stale` | R-07: один `search` сигналів з `status in (ok,warn,alarm)` і `last_ts < now − stale_after`; `_mark_stale('timeout')` батчем; потім `f3d.collector._cron_offline()` (R-25) | ≤ 5 с; не більше 2 000 сигналів за прогін |
| `cron_f3d_telemetry_hour` | Телеметрія: годинні агрегати | 10 хв, `active=True` | `f3d.reading.hour._cron_aggregate` | R-09: для закритих годин від `max(hour) − 1 год` (або найстарішого показання) до `date_trunc('hour', now) − 1 год` — один SQL upsert | ≤ 30 с; вікно ≤ 48 год за прогін (решта — наступним) |
| `cron_f3d_telemetry_rotate` | Телеметрія: ротація показань | 1 доба, `nextcall` = найближче 02:40 Europe/Kyiv (ставить хук через `pytz`), `active=True` | `f3d.reading._cron_rotate` | R-10: `DELETE FROM f3d_reading WHERE ts < now − keep_days` батчами по 50 000 (`ctid`/`id` підзапит); те саме для `f3d_reading_hour` (`keep_hours_days`) і `f3d_push_event` (`keep_days`) | ≤ 60 с; решта — наступного дня |
| `cron_f3d_telemetry_commands_gc` | Телеметрія: прострочені команди | 10 хв, `active=True` | `f3d.command._cron_expire` | `queued/sent` з `expires_at < now` → `expired` | — |
| `factory3d_iot_sim.cron_iot_sim` | Емулятор IoT: рівень 0 | — | — | **вимикається** хуком §5.3 крок 9; модуль його не створює і не видаляє | — |

Крони виконуються від `base.user_root`; методи працюють `sudo()` на власних моделях, не торкаються
`maintenance.request` (заявки створює лише Ingester у транзакції push або R-07 ніколи — `stale` заявок не
створює).

## 7. HTTP/JSON API (CT-04)

Спільне: `controllers/telemetry.py`, усі маршрути `type="http"`, `auth="public"`, `csrf=False`,
`methods` як у таблиці; відповідь `request.make_json_response(data, status)` з `Content-Type:
application/json; charset=utf-8`, `Cache-Control: no-store` (крім API-01 — `private, max-age=0`).
Автентифікація: заголовок `Authorization: Bearer <token>` → `f3d.collector._authenticate(token)`; порожній
або невірний → `401 {"error": {"code": "unauthorized", "message": "Невірний токен колектора"}}`; колектор
`active=False` → `403 forbidden`. Усі помилки — `{"error": {"code": "<snake>", "message": "<укр.>"}}`.
Після перевірки — `env = request.env(user=SUPERUSER_ID)` з `context={'f3d_collector_id': id, 'tz': 'UTC'}`.
Розмір тіла > 1 МБ → `413 payload_too_large`; невалідний JSON → `400 bad_json`. Часи у відповідях — ISO 8601
UTC із суфіксом `Z`. Усі ендпоінти ідемпотентні, крім API-07 (повторний результат для `done` команди
ігнорується з `reason="already_done"`).

### API-01 `GET /f3d/telemetry/config`

Заголовки: `If-None-Match: "<etag>"` → `304` без тіла, якщо `etag` збігається (R-16). Відповідь `200`:

```json
{"etag": "a3f9…(64 hex)", "generated_at": "2026-10-14T06:10:00Z", "server_time": "2026-10-14T06:10:00Z",
 "read_enabled": true, "write_enabled": false,
 "collector": {"code": "COL-MAIN", "push_interval_s": 5, "push_max": 1000, "status_interval_s": 60, "config_poll_s": 60},
 "params": {"stale_periods": 3, "stale_min_s": 60},
 "sources": [
   {"code": "MB-U70-COMPRESSOR", "type": "modbus_tcp", "read_enabled": true, "write_enabled": false,
    "params": {"host": "iot-sim", "port": 502, "unit": 70, "timeout_s": 3, "retries": 2, "max_block": 100},
    "signals": [
      {"code": "equipment/COMPRESSOR/pressure_bar", "kind": "gauge", "unit": "бар", "period_s": 10, "scale": 1.0,
       "write_enabled": false, "states": null, "decimals": 2,
       "address": {"fc": 3, "addr": 3001, "type": "u16", "scale": 0.001, "offset": 0, "range": [0, 16], "doc": "HR 3002 Outlet pressure"}},
      {"code": "equipment/COMPRESSOR/state", "kind": "state", "unit": "", "period_s": 10, "scale": 1.0, "write_enabled": false,
       "states": ["stopped", "loaded", "unloaded", "fault", "standby"],
       "address": {"fc": 3, "addr": 3000, "type": "u16", "map": {"0": "stopped", "1": "loaded", "2": "unloaded", "3": "fault", "4": "standby"}, "doc": "HR 3001 Machine status"}}
    ]},
   {"code": "MQTT-MOBILE", "type": "mqtt", "read_enabled": true, "write_enabled": false,
    "params": {"host": "mosquitto", "port": 1883, "username": "collector", "password_ref": "F3D_MQTT_PASSWORD",
               "client_id": "f3d-collector", "topics": ["f3d/mobile/+/telemetry", "f3d/mobile/+/status"],
               "status_topic": "f3d/mobile/{device}/status", "status_online_path": "$.online", "keepalive_s": 30, "tls": false},
    "signals": [{"code": "equipment/FL-1/battery", "kind": "gauge", "unit": "%", "period_s": 5, "scale": 1.0, "write_enabled": false,
                 "address": {"topic": "f3d/mobile/FL-1/telemetry", "path": "$.battery_pct", "ts_path": "$.ts", "device": "FL-1"}}]},
   {"code": "HTTP-PUSH", "type": "http_push", "read_enabled": true, "write_enabled": false,
    "params": {"routes": ["lpr"], "allow_ips": ["iot-sim"], "token_ref": "F3D_HTTP_PUSH_TOKEN_LPR", "secret_ref": "F3D_HTTP_PUSH_SECRET_LPR"},
    "signals": []}
 ]}
```

Схема (обов'язкові позначено `*`): `etag*` str, `generated_at*`, `server_time*`, `read_enabled*` bool,
`write_enabled*` bool (глобальні стоп-крани), `collector*` {`code*`, `push_interval_s*`, `push_max*`,
`status_interval_s*`, `config_poll_s*`}, `params*`, `sources*` [] з `code*`, `type*` (один з 8),
`read_enabled*`, `write_enabled*`, `params*` (Додаток A.2; значення `*_ref` — **імена змінних середовища**
колектора, секрети в Odoo не зберігаються), `signals*` [] з `code*`, `kind*`, `unit*` (може бути `""`),
`period_s*`, `scale*`, `write_enabled*`, `states` (list|null), `decimals`, `address*` (Додаток A.1).
Віддаються лише активні джерела цього колектора й активні сигнали з непорожньою адресою; джерела з
`read_enabled=False` або при глобальному `read_enabled=False` — у списку з `read_enabled:false` (колектор не
опитує). Коди: `200`, `304`, `401`, `403`. Розмір на стенді ≈ 60 КБ (55 сигналів); 1 000 сигналів ≈ 500 КБ.

### API-02 `POST /f3d/telemetry/push`

Тіло (`application/json`, ≤ 1 МБ, ≤ `push_max_readings` = 2 000 елементів):

```json
{"collector": "COL-MAIN", "seq": 1842, "sent_at": "2026-10-14T06:10:05Z",
 "readings": [
   {"code": "equipment/COMPRESSOR/pressure_bar", "ts": "2026-10-14T06:10:00Z", "value": 6.772, "q": "good"},
   {"code": "equipment/FL-C1/battery", "ts": "2026-10-14T06:10:03.250+03:00", "value": 23.6},
   {"code": "equipment/FL-C1/state", "ts": "2026-10-14T06:10:03.250+03:00", "text": "busy"},
   {"code": "infra/water/m3_total", "ts": "2026-10-14T06:10:00Z", "value": 18642.37}
 ]}
```

Схема: `collector*` str (має дорівнювати коду автентифікованого колектора, інакше `403 collector_mismatch`),
`seq` int (монотонний лічильник пакетів; лише для логів/метрик), `sent_at` ISO, `readings*` [] з `code*`
(R-01), `ts*` (ISO 8601 **з зоною** `Z` або `±hh:mm`; без зони → відхилення елемента `ts_no_tz`), один з
`value` (number, скінченний) або `text` (str ≤ 64), `q` ∈ {`good`,`uncertain`,`bad`} (default `good`).
Відповідь `200`:

```json
{"accepted": 4, "stored": 2, "duplicates": 0, "rejected": [{"i": 7, "code": "equipment/XX/y", "reason": "unknown_code"}],
 "changed": ["equipment/FL-C1/battery", "equipment/FL-C1/state"], "alarms_opened": 0,
 "config_etag": "a3f9…", "read_enabled": true, "server_time": "2026-10-14T06:10:06Z"}
```

`accepted` — елементи, що оновили `last_*` (або були старіші за `last_ts`, але валідні); `stored` — записані
в `f3d.reading` (R-03); `duplicates` — `(signal, ts)` уже були; `rejected[].reason` ∈ {`unknown_code`,
`inactive`, `foreign_signal` (сигнал не на джерелі цього колектора), `ts_no_tz`, `ts_invalid`,
`ts_future` (> `now + 60 с`), `ts_too_old` (< `now − keep_days`), `value_invalid` (NaN/inf/не число),
`text_too_long`, `missing_value`, `unknown_state` (текст поза `states`, якщо список непорожній → приймається з
`q='bad'`, не відхиляється — reason лише інформує), `bad_code_format`}; `changed` — коди зі зміненим
`last_value/last_text/status` (для діагностики). Коди: `200`; `400 bad_json`/`bad_schema` (не список, >
ліміту — `413 too_many_readings`); `401`; `403`; `423 read_disabled` (глобальний стоп-кран; тіло не
обробляється — колектор лишає пакет у буфері); `429 rate_limited` (R-17 п. 2, заголовок `Retry-After: 10`).
Ідемпотентність: повторний той самий пакет → `duplicates = n`, `stored = 0`, `last_*` без змін (R-17).
Час обробки пакета 1 000 показань ≤ 1 с (§13.4).

### API-03 `POST /f3d/telemetry/status`

```json
{"collector": "COL-MAIN", "version": "0.1.0", "uptime_s": 86412, "ts": "2026-10-14T06:10:00Z",
 "buffer": {"rows": 0, "dropped_total": 0, "bytes": 24576},
 "plugins": [{"type": "modbus_tcp", "version": "0.1.0", "sources": 4}, {"type": "mqtt", "version": "0.1.0", "sources": 1},
             {"type": "http_push", "version": "0.1.0", "sources": 1}, {"type": "bacnet_ip", "version": "0.1.0", "sources": 1}],
 "sources": [
   {"code": "MB-U70-COMPRESSOR", "state": "online", "last_ok": "2026-10-14T06:09:58Z", "error": null,
    "stats": {"polls": 8640, "errors": 2, "latency_ms": 12, "readings": 43200}},
   {"code": "MQTT-MOBILE", "state": "online", "last_ok": "…", "error": null, "stats": {"messages": 17280, "readings": 69120}},
   {"code": "BAC-140-BOILER", "state": "error", "last_ok": "2026-10-14T05:50:10Z", "error": "Who-Is: device 140 not found (timeout 5 s)", "stats": {"polls": 120, "errors": 60}}
 ]}
```

Дія: `collector._touch(ip, version)`, `uptime_s`, `buffer_rows`, `buffer_dropped`, `plugins`; для кожного
`sources[]` з кодом джерела цього колектора — `source._apply_status(item)` (R-25); невідомі коди →
`rejected`. Відповідь `200 {"ok": true, "config_etag": "…", "read_enabled": true, "write_enabled": false,
"server_time": "…"}`. Ліміти: ≤ 500 джерел у звіті, ≤ 256 КБ. Коди: `200`, `400`, `401`, `403`.
`state` ∈ {`online`, `offline`, `error`}; `error` ≤ 512 символів; секрети у `error` колектор маскує сам
(`SecretFilter`), Odoo додатково обрізає все після `password=`/`token=` (R-25).

### API-04 `GET /f3d/telemetry/health`

Без токена: `200 {"ok": true, "module": "factory3d_telemetry", "version": "19.0.1.0.0", "server_time": "…"}`.
З валідним токеном — додатково `"collector": {"code", "state", "last_seen"}, "counts": {"signals": 225,
"alarms": 1, "stale": 0, "sources_online": 6}`. Жодних інших даних без токена (безпека §13.3). `ok=false`
(`503`) лише якщо реєстр моделей недоступний (теоретично ніколи — слугує для `HEALTHCHECK`).

### API-05 `POST /f3d/telemetry/event` (ретрансляція `http_push`, CT-08)

```json
{"collector": "COL-MAIN",
 "events": [{"event_id": "9f1c…(sha256 hex, 64)", "route": "lpr", "ts": "2026-10-14T05:15:05.507Z", "remote": "10.90.2.5",
             "headers": {"content-type": "application/json", "user-agent": "AXIS LPV"},
             "payload": {"plateText": "AA4512KT", "plateUnicode": "АА4512КТ", "carState": "new", "carMoveDirection": "in",
                         "GEOtarget": "GATE-W", "sensorProviderID": "CAM-05", "capture_timestamp": "1792391105507", "…": "…"}}]}
```

≤ 100 подій, ≤ 1 МБ; `event_id*` (64 hex: sha256 від маршруту + тіла + `remote`), `route*`
(`^[a-z][a-z0-9_]{0,31}$`), `ts*` ISO з зоною, `remote`, `headers` (лише `content-type`, `user-agent`,
`x-f3d-token-ok`), `payload*` (JSON object ≤ 256 КБ). Дія (R-22): для кожної події — `f3d.push.event`
(дублікат `event_id` → `rejected: duplicate`); диспетчеризація обробникам M-11 з `_f3d_push_routes ∋ route`;
сигнали джерел `http_push` цього колектора з `address.route == route` і `match ⊆ payload` → показання через
`_f3d_ingest` (`src='collector'`). Відповідь `200 {"accepted": n, "rejected": [...], "handled": {"lpr":
["f3d.push.handler.yard.lpr"]}}`. Коди: `200`, `400`, `401`, `403`, `413`, `423` (`read_disabled`).

### API-06 `GET /f3d/telemetry/commands`

Параметри: `limit` (≤ 100, default 50). Дія (R-18): якщо глобальний `write_enabled=False` → `200
{"commands": [], "write_enabled": false}`; інакше `queued` команди сигналів джерел цього колектора з
`expires_at > now`, упорядковані `requested_at` → `state='sent'`, `sent_at=now`; відповідь:

```json
{"write_enabled": true, "server_time": "…",
 "commands": [{"id": 17, "code": "ventilation/units/RV-05/heating_valve", "source": "BAC-105-RV-05",
               "value": 80.0, "text": null, "requested_at": "…", "expires_at": "…",
               "address": {"device": 105, "object": "analog-output", "instance": 1, "property": "present-value", "priority": 8}}]}
```

Коди `200`, `401`, `403`. Колектор опитує кожні `F3D_COMMANDS_POLL_S` (5 с) лише коли `write_enabled`
(з відповіді API-01/API-02).

### API-07 `POST /f3d/telemetry/commands/result`

```json
{"collector": "COL-MAIN", "results": [{"id": 17, "state": "done", "ts": "…", "result": "written 80.0 @prio 8", "error": null},
                                      {"id": 18, "state": "failed", "ts": "…", "result": null, "error": "WriteAccessDenied"}]}
```

Дія: `sent` → `done`/`failed` з `done_at`, `result`, `error`; інші стани → `rejected: already_done|not_sent`.
Чаттер команди: «Виконано: …» / «Помилка: …». Відповідь `200 {"accepted": n, "rejected": [...]}`.

### 7.1 Контрольний приклад curl (стенд)

```bash
TOKEN=…   # з майстра M-12
curl -sS -H "Authorization: Bearer $TOKEN" http://odoo19:8069/f3d/telemetry/config | jq .etag
curl -sS -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"collector":"COL-MAIN","readings":[{"code":"equipment/COMPRESSOR/pressure_bar","ts":"2026-10-14T06:10:00Z","value":5.9}]}' \
  http://odoo19:8069/f3d/telemetry/push
# → {"accepted":1,"stored":1,...,"alarms_opened":1}  і заявка «Компресор: тиск 5,9 бар при нормі від 6,0»
```

## 8. Сервісна частина `services/collector`

### 8.1 Пакет, залежності, порти, compose

#### 8.1.1 Запуск

`python -m collector run` (entry point `f3d-collector run`) — один процес asyncio: `Settings` з env →
`OdooClient` → `Registry.load()` (API-01; при недоступності Odoo — остання конфігурація з
`state/config.json`, якщо не старша за 7 діб, інакше очікування з бекофом) → створення плагінів через
entry points → `Scheduler` (опитування) + підписки + `HttpPushServer` → `Pusher` (буфер → API-02) →
`StatusReporter` (API-03) → `CommandLoop` (API-06/07, лише при `write_enabled`) → `/metrics`.
`f3d-collector check-config` — перевіряє env і доступність Odoo (`GET /f3d/telemetry/health` з токеном),
код виходу 0/1. `f3d-collector dump-config` — друкує конфігурацію з Odoo (без секретів).
`f3d-collector test-source <code>` — одноразове `connect` + `poll` усіх сигналів джерела, друкує значення.
`f3d-collector drain-buffer` — відправляє буфер і виходить.

#### 8.1.2 Залежності (`requirements.txt`, Python 3.12; закріпити `==` при першому збиранні)

| Пакет | Версія | Для чого |
|---|---|---|
| `aiohttp` | 3.11.18 | клієнт до Odoo (API-01…07) і сервер приймача `http_push` (A-13) |
| `pymodbus` | 3.9.2 | Modbus TCP клієнт (та сама версія, що в емуляторі; аргумент `slave=`; у 3.10+ — `device_id=`) |
| `paho-mqtt` | 2.1.0 | MQTT (`CallbackAPIVersion.VERSION2`) |
| `bacpypes3` | 0.0.102 | BACnet/IP клієнт (та сама версія, що в емуляторі) |
| `pydantic`, `pydantic-settings` | 2.11.x / 2.9.x | схеми, конфіг |
| `jsonschema` | 4.23.0 | валідація `address`/`params` за `plugins/schemas/*.json` (той самий зміст, що Додаток A) |
| `prometheus-client` | 0.21.x | `/metrics` |
| `aiosqlite` | 0.21.0 | буфер |
| `pytest`, `pytest-asyncio`, `pytest-timeout`, `aiohttp[speedups]`-тестові утиліти | 8.3.x / 0.25.x / 2.3.x | тести |

Жодних `requests`, `httpx`, `fastapi`; жодних **серверів** протоколів пристроїв (Modbus/BACnet/OPC UA) у
коді сервісу — лише в `tests/`.

#### 8.1.3 Порти й адреси

| Що | Порт | Примітка |
|---|---|---|
| приймач `http_push` | 8080 (`F3D_HTTP_PUSH_PORT`) | `POST /f3d/<route>[/<secret>]`, `GET /f3d/health`; лише в мережі `f3d_sim` |
| метрики/здоров'я | 9108 (`F3D_METRICS_PORT`) | `GET /metrics`, `GET /health` |
| BACnet/IP клієнт | UDP `F3D_BACNET_BIND` (`0.0.0.0:47808`) | власна IP у мережі `f3d_sim`; роутер емулятора на `iot-sim:47808` |
| вихідні з'єднання | Modbus 502, MQTT 1883, BACnet 47808/udp, Odoo 8069 | лише хости з `F3D_ALLOW_HOSTS` + Odoo |

#### 8.1.4 `docker-compose.collector.yml` (істотне)

```yaml
networks:
  f3d_sim: {external: true}        # мережа emulator compose (iot_sim, mosquitto)
  odoo_default: {external: true}   # мережа Odoo
services:
  collector:
    build: ./services/collector
    env_file: ./services/collector/.env
    networks: [f3d_sim, odoo_default]
    volumes: ["collector_state:/app/state"]
    read_only: true
    tmpfs: ["/tmp"]
    user: "10002:10002"
    cap_drop: [ALL]
    sysctls: {net.ipv4.ip_unprivileged_port_start: 0}   # не потрібно (8080/9108/47808 непривілейовані), лишено симетрично з iot_sim
    healthcheck: {test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:9108/health')"], interval: 30s, timeout: 5s, retries: 3}
    restart: unless-stopped
volumes: {collector_state: {}}
```

На хост порти не публікуються. Для проду (без емулятора) мережа `f3d_sim` замінюється на мережу з
маршрутом у VLAN цеху (`F3D_ALLOW_HOSTS` — реальні IP пристроїв).

### 8.2 Конфігурація (`core/config.py`, префікс `F3D_`)

| Змінна | Тип / default | Призначення |
|---|---|---|
| `F3D_ODOO_URL` | str / **обов'язково** | `http://odoo19:8069` або `https://…` |
| `F3D_ODOO_CA` | path / порожньо | CA для самопідписаного TLS |
| `F3D_COLLECTOR_CODE` | str / **обов'язково** | = `f3d.collector.code` |
| `F3D_COLLECTOR_TOKEN` | str / **обов'язково** (≥ 32 символи, інакше вихід код 2) | Bearer |
| `F3D_CONFIG_POLL_S` | int / 60 | період перечитування API-01 (перекривається `collector.config_poll_s` з Odoo) |
| `F3D_PUSH_INTERVAL_S` | int / 5 | період відправки (перекривається Odoo) |
| `F3D_PUSH_MAX` | int / 1000 | показань у пакеті (перекривається Odoo, не більше 2 000) |
| `F3D_STATUS_INTERVAL_S` | int / 60 | API-03 |
| `F3D_COMMANDS_POLL_S` | int / 5 | API-06 |
| `F3D_WRITE_ENABLED` | bool / 0 | стоп-кран запису в пристрої на стороні колектора |
| `F3D_ALLOW_HOSTS` | CSV / **обов'язково** | allow-list хостів/IP/CIDR пристроїв і брокера (`iot-sim,mosquitto` на стенді) |
| `F3D_BUFFER_DIR` | path / `./state` | SQLite |
| `F3D_BUFFER_MAX_MB` | int / 200 | ліміт буфера |
| `F3D_HTTP_PUSH_PORT` | int / 8080 | приймач |
| `F3D_HTTP_PUSH_TOKEN_<ROUTE>` | str / порожньо | токен маршруту (`X-F3D-Token` або Bearer); порожньо = без токена (лише allow-list IP) |
| `F3D_HTTP_PUSH_SECRET_<ROUTE>` | str / порожньо | секретний суфікс шляху `/f3d/<route>/<secret>` (Q-13) |
| `F3D_HTTP_PUSH_ALLOW_IPS` | CSV / порожньо | глобальний allow-list відправників (об'єднується з `params.allow_ips` джерела) |
| `F3D_MQTT_PASSWORD` та інші `*_ref` | str | секрети, на які посилаються `params.*_ref` |
| `F3D_BACNET_BIND` | str / `0.0.0.0:47808` | локальна адреса BACnet-застосунку |
| `F3D_BACNET_DEVICE_ID` | int / 3999 | instance власного device-об'єкта колектора |
| `F3D_METRICS_PORT` | int / 9108 | |
| `F3D_LOG_LEVEL`, `F3D_LOG_JSON` | `INFO`, `1` | |
| `F3D_TZ` | `Europe/Kyiv` | лише для логів; усі `ts` — UTC |
| `F3D_CLOCK_SKEW_WARN_S` | int / 30 | попередження при розходженні з `server_time` |

Усі `*_ref` у параметрах джерел розв'язуються **лише** через env (`os.environ[name]`); відсутня змінна →
джерело `error: "secret F3D_… not set"`, інші джерела працюють.

### 8.3 Ядро й інтерфейс плагіна (CT-02)

#### 8.3.1 Типи (`core/types.py`)

```python
@dataclass(frozen=True)
class SignalCfg:
    code: str; kind: str; unit: str; period_s: int; scale: float; write_enabled: bool
    states: list[str] | None; decimals: int; address: dict; source_code: str

@dataclass(frozen=True)
class SourceCfg:
    code: str; type: str; read_enabled: bool; write_enabled: bool; params: dict; signals: tuple[SignalCfg, ...]

@dataclass(frozen=True)
class Reading:
    code: str; ts: datetime              # tz-aware UTC
    value: float | None = None; text: str | None = None; q: str = "good"

@dataclass
class Health:
    state: str                           # "online" | "offline" | "error"
    error: str | None = None; last_ok: datetime | None = None; stats: dict = field(default_factory=dict)

@dataclass(frozen=True)
class Command:
    id: int; code: str; source: str; value: float | None; text: str | None; address: dict; expires_at: datetime

@dataclass(frozen=True)
class CommandResult:
    id: int; state: str; ts: datetime; result: str | None = None; error: str | None = None

@dataclass(frozen=True)
class PushEvent:
    event_id: str; route: str; ts: datetime; remote: str; headers: dict; payload: dict
```

#### 8.3.2 `plugins/base.py`

```python
class PluginContext:
    """Що плагін отримує від ядра."""
    settings: Settings                      # лише читання
    secrets: Callable[[str], str]           # resolve("F3D_MQTT_PASSWORD") → значення або KeyError
    allowlist: Callable[[str], None]        # allowlist("iot-sim") → None або AllowlistDenied
    emit: Callable[[Reading], None]         # для push-протоколів: покласти показання в буфер
    emit_event: Callable[[PushEvent], None] # для http_push
    metrics: Metrics                        # лічильники/гістограми з мітками type/source
    log: logging.Logger                     # дочірній логер "collector.plugin.<type>.<source>"

class SourcePlugin(ABC):
    type: ClassVar[str]                     # "modbus_tcp"
    version: ClassVar[str] = "0.1.0"
    address_schema: ClassVar[dict]          # JSON Schema (= Додаток A.1 для type)
    params_schema: ClassVar[dict]           # JSON Schema (= Додаток A.2)
    push_mode: ClassVar[bool] = False       # True → ядро викликає subscribe(), poll() не планується

    def __init__(self, source: SourceCfg, ctx: PluginContext): ...
    @classmethod
    def validate(cls, source: SourceCfg) -> list[str]:
        """Помилки схем params/address усіх сигналів; порожній список = ок. Викликається ядром до connect()."""
    async def connect(self) -> None:
        """Відкрити з'єднання/сесію. Перед будь-яким мережевим викликом — ctx.allowlist(host). Може кидати ConnectError."""
    async def disconnect(self) -> None: ...
    async def poll(self, signals: Sequence[SignalCfg]) -> list[Reading]:
        """Прочитати групу сигналів з однаковим period_s. Повертає показання (ts = час читання, UTC) або кидає PollError.
        Часткові помилки — Reading(q='bad') для відповідних сигналів."""
    async def subscribe(self) -> None:
        """Для push_mode: запустити підписки; показання віддаються через ctx.emit(). Повертається одразу."""
    async def write(self, signal: SignalCfg, value: float | None, text: str | None) -> str:
        """Записати значення; повертає рядок результату. За замовчуванням raise NotSupported. Викликається лише коли
        settings.write_enabled and source.write_enabled and signal.write_enabled (ядро перевіряє до виклику)."""
    def health(self) -> Health: ...
```

Реєстрація: `pyproject.toml` `[project.entry-points."factory3d_collector.plugins"] modbus_tcp = "collector.plugins.modbus_tcp:ModbusTcpPlugin"`.
`load_plugins()` → `importlib.metadata.entry_points(group="factory3d_collector.plugins")` → `{type: cls}`;
джерело з типом без плагіна → `Health(state='error', error='plugin <type> not installed')` і WARNING, решта
працює. Плагіни інших модулів — окремі pip-пакети з тим самим entry point (напр. `f3d_collector_opcua`),
встановлюються в образ через `requirements-extra.txt`.

Винятки ядра: `ConnectError`, `PollError`, `WriteError`, `NotSupported`, `AllowlistDenied` — усі з
`collector.core.errors`; текст без секретів.

#### 8.3.3 Планувальник (`core/scheduler.py`) — R-19

- Для кожного джерела з `read_enabled` і плагіном не-push: групи = `{period_s: [signals]}`; на групу —
  таска `loop_poll(source, period, signals)`: `await plugin.poll(signals)` → `buffer.put_many(readings)`;
  сон до наступного тіку `period − elapsed` з початковим джиттером `random(0, period)` (щоб 50 джерел не
  били одночасно); `elapsed > period` → метрика `collector_poll_overrun_total` + WARNING раз на хвилину.
- Помилка `poll` → бекоф на джерело: 1, 2, 4 … 30 с (max), стан `error` після 3 поспіль; будь-який успіх
  скидає. `connect` у бекофі 1 → 60 с.
- Push-плагіни: `subscribe()` один раз; плагін сам відновлює з'єднання (reconnect 1 → 60 с).
- Перечитування конфігурації: `Registry.refresh()` кожні `config_poll_s` і негайно, коли API-02/03 повернув
  інший `config_etag`; diff: нові/змінені джерела → `disconnect` старого плагіна, `connect` нового; незмінні —
  без перезапуску (порівняння `SourceCfg` як frozen dataclass).
- `read_enabled=False` глобально → усі опитування зупиняються (плагіни `disconnect`), статуси шлються далі.

#### 8.3.4 Буфер (`core/buffer.py`) — R-19

SQLite (`aiosqlite`, `journal_mode=WAL`, `synchronous=NORMAL`) у `F3D_BUFFER_DIR/buffer.sqlite`: таблиці
`readings(id INTEGER PK, code TEXT, ts TEXT, value REAL, text TEXT, q TEXT)`, `events(id, event_id TEXT UNIQUE,
route, ts, remote, headers TEXT, payload TEXT)`, `results(id, cmd_id INT, state, ts, result, error)`. `put_many`
— одна транзакція; `take(limit)` — найстаріші `limit` рядків (FIFO), видаляються після `200` від Odoo
(`ack(ids)`); при `423`/`5xx`/мережевій помилці — лишаються, бекоф 1 → 60 с; при `4xx` (крім 423/429) пакет
відкидається з ERROR (невалідний — повтор не допоможе) і лічильником `collector_push_rejected_total`.
Ліміт: `F3D_BUFFER_MAX_MB`; при перевищенні видаляються найстаріші `readings` партіями по 10 000 з лічильником
`collector_buffer_dropped_total` (повідомляється в API-03 `buffer.dropped_total`). `events`/`results` ніколи не
викидаються лімітом (вони малі), лише старші 7 діб.

#### 8.3.5 Клієнт Odoo (`core/odoo_client.py`)

`aiohttp.ClientSession(timeout=ClientTimeout(total=30), headers={"Authorization": f"Bearer {token}"})`;
методи `config(etag) → (304|dict)`, `push(readings) → dict`, `status(payload)`, `event(events)`,
`commands(limit)`, `commands_result(results)`. Ретраї: мережеві помилки/`502/503/504` — 3 спроби з 1/2/4 с,
далі виняток для циклу буфера. `server_time` з відповідей порівнюється з локальним UTC → `|skew| >
F3D_CLOCK_SKEW_WARN_S` → WARNING + `collector_clock_skew_seconds`.

#### 8.3.6 Зарезервовано: `Sink` для TimescaleDB (Q-01)

Інтерфейс `class Sink(ABC): async def write(self, readings: list[Reading])` з однією реалізацією
`OdooSink` (буфер → API-02). `TimescaleSink` не реалізується у фазі 2; місце — `core/sinks.py`.

### 8.4 Відправка, статус, команди

- `Pusher`: кожні `push_interval_s` або коли в буфері ≥ `push_max` → `take(push_max)` → `push` → `ack`;
  відповідь: `rejected[]` логуються WARNING (по одному рядку на `reason` з кількістю); `config_etag` ≠
  поточного → `Registry.refresh()`; `read_enabled=false` → пауза опитувань.
- `StatusReporter`: кожні `status_interval_s` — `Health` усіх плагінів + буфер + версії → API-03.
- `CommandLoop` (R-18): лише коли `settings.write_enabled` і Odoo `write_enabled`: `GET commands` →
  для кожної: знайти `SourceCfg`/`SignalCfg`; перевірки `source.write_enabled`, `signal.write_enabled`,
  `expires_at > now`; `await plugin.write(signal, value, text)` з таймаутом 10 с → `CommandResult(done,
  result)` або `failed` з текстом винятку → `POST commands/result` (через буфер `results`, щоб не загубити).

### 8.5 Плагін `modbus_tcp` (`plugins/modbus_tcp.py`) — R-20

- `pymodbus.client.AsyncModbusTcpClient(host, port, timeout=params.timeout_s, retries=params.retries)`;
  **пул**: один клієнт на `(host, port)` спільний для всіх джерел (кілька unit за одним шлюзом) — клас
  `ConnectionPool` у модулі плагіна; `connect()` → `await client.connect()`; `connected` перевіряється перед
  кожним `poll`.
- `poll(signals)`: групування (R-20 п. 3) → для кожного блоку `read_coils` (fc 1) / `read_discrete_inputs`
  (2) / `read_holding_registers` (3) / `read_input_registers` (4) з `slave=unit` (`unit` сигналу або
  джерела); `rr.isError()` → `PollError(str(rr))` (виняток Modbus 0x02/0x0B — у тексті); декодування
  `util/codec.decode_registers(regs, type, wordorder, byteorder)`; `value = raw·scale + offset`; `range`
  порушено → `q='bad'`; `kind='state'`: `map[str(int(raw))]` → `text` (немає в `map` → `text=str(raw)`,
  `q='uncertain'`); `states[]`-адреси (складений стан) → перший збіг за порядком.
- `write(signal, value, text)`: `fc` 5 (coil, `value != 0`) / 6 (один регістр) / 16 (кілька: типи 32/64/f32)
  на `address.write.addr` або `address.addr`; `kind='state'` з `text` → `value = int(key)` за зворотним
  `map`; результат `"fc16 addr 3100 = [7000]"`.
- `health()`: `online` якщо останній `poll` без помилки ≤ 2 періоди; `stats`: `polls`, `errors`,
  `latency_ms` (EWMA), `readings`.
- Сервер для тестів: `pymodbus.server.ModbusTcpServer` з `ModbusSlaveContext`/`ModbusSequentialDataBlock` на
  вільному порту (`tests/conftest.py: modbus_server`), unit 70/84/90/96 з регістрами з Додатка C.

### 8.6 Плагін `mqtt` (`plugins/mqtt.py`) — R-21

- `paho.mqtt.client.Client(CallbackAPIVersion.VERSION2, client_id=params.client_id + "-" + collector_code,
  protocol=MQTTv311, clean_session=False)`; `username_pw_set(params.username, secrets(params.password_ref))`;
  `tls_set()` при `params.tls`; `reconnect_delay_set(1, 60)`; `connect_async(host, port, keepalive_s)`;
  `loop_start()` (власний потік paho); `on_connect` → `subscribe([(t, qos) for t in params.topics])`;
  `on_message` → `loop.call_soon_threadsafe(queue.put_nowait, (topic, payload, retain))`; корутина
  `consumer` читає чергу й будує показання.
- Відповідність топік → сигнали: індекс `{topic_exact: [signals]}` + шаблони з `+`/`#` (функція
  `paho.mqtt.matcher`-подібна власна `topic_matches(sub, topic)`); для кожного сигналу з адресою на цей топік:
  `payload` → JSON (невалідний → `q='bad'`, `text=None`, WARNING раз на хвилину); `val = jsonpath.get(path,
  obj)`; `ts` = `jsonpath.get(ts_path)` (ISO або epoch мс) або час прийому; `kind='gauge'/'counter'` → число
  (`bool` → 0/1); `kind='state'` → `map.get(str(val), str(val))` → `text`; відсутній шлях → пропуск
  (`collector_mqtt_missing_path_total`).
- `retain`-повідомлення при підключенні → приймаються, але `ts` = час прийому і `q='uncertain'` (стале
  значення).
- Стан джерела: `status_topic` (шаблон з `{device}`) + `status_online_path`: `online=false` або LWT →
  пристрій у `stats.offline_devices`; джерело `offline` лише коли брокер недоступний; `health()` — за
  з'єднанням з брокером (`on_disconnect` → `offline`, `on_connect` з `reason_code != 0` → `error`).
- `write`: `address.write.topic` + `address.write.template` (JSON з `{value}`/`{text}`), `publish(qos=1)`;
  без `write` в адресі → `NotSupported`.
- Тести: фейковий `paho.Client` (клас у `tests/conftest.py`), який викликає `on_connect`/`on_message`
  синхронно; стенд — mosquitto емулятора.

### 8.7 Плагін `http_push` (`plugins/http_push.py`) — R-22

- `push_mode=True`; один `aiohttp.web.Application` на процес (`HttpPushServer`), маршрут
  `POST /f3d/{route}` і `POST /f3d/{route}/{secret}`, `GET /f3d/health`; порт `F3D_HTTP_PUSH_PORT`.
  Джерела типу `http_push` реєструють свої `params.routes`; маршрут без джерела → `404`.
- Перевірки запиту (у цьому порядку): розмір ≤ 1 МБ (`413`); `remote` ∈ `allow_ips` (джерела ∪ env;
  порожньо = будь-який) інакше `403`; якщо задано `secret_ref` — суфікс шляху збігається (`compare_digest`),
  інакше `404`; якщо задано `token_ref` — заголовок `X-F3D-Token` або `Authorization: Bearer` збігається,
  інакше `401`; `Content-Type` `application/json` або `multipart/form-data` (Axis може слати multipart: поле
  JSON береться з частини `application/json`, зображення відкидаються) інакше `415`; JSON object інакше
  `400`.
- Подія: `event_id = sha256(route + "\n" + remote + "\n" + canonical_json(payload))`; `ts`: з
  `address.ts_path` сигналів маршруту (перший, що є) → epoch мс/с або ISO; інакше час прийому;
  `ctx.emit_event(PushEvent(...))` → буфер `events` → API-05 пакетами ≤ 100. Відповідь пристрою — `200
  {"received": true}` одразу (не чекаючи Odoo). Сигнали з адресою на маршрут обробляє Odoo (API-05), не
  колектор — так показання й подія узгоджені в одній транзакції.
- `health()`: `online`, якщо сервер слухає; `stats`: `requests`, `rejected_ip`, `rejected_auth`, `events`.

### 8.8 Плагін `bacnet_ip` (`plugins/bacnet_ip.py`) — R-23, FR-29

- Один застосунок `bacpypes3.app.Application` на процес (`BacnetApp`), локальний device `F3D_BACNET_DEVICE_ID`
  («F3D Collector»), адреса `F3D_BACNET_BIND`; створюється при першому джерелі `bacnet_ip`.
- `connect()`: `ctx.allowlist(params.host)`; якщо `params.address` задано — використовується як BACnet-адреса
  (`"10.0.0.5"` або `"2:0x0a000005bac0"` для маршрутизованої мережі); інакше `Who-Is(device, device)` на
  `params.host:params.port` (unicast до роутера/пристрою) з таймаутом `timeout_s`; `I-Am` → адреса кешується
  (`core/state/bacnet_addr.json`); немає відповіді → `ConnectError("Who-Is: device 140 not found")`.
- `poll(signals)`: `ReadPropertyMultiple` блоками ≤ `params.rpm_max` (50) пар `(object, property)` на
  пристрій (якщо `params.rpm=false` або пристрій відповідає `unrecognized-service` → послідовний
  `ReadProperty`); для кожного сигналу: `present-value` → число (`Real`/`Unsigned`/`Enumerated`/`Boolean` →
  float; `MultiState` → індекс → `map`/`states` → `text`); `status-flags` читається тим самим RPM
  (`fault` або `in-alarm` → `q='uncertain'`; `out-of-service` → `q='bad'`); `reliability`, якщо є в адресі
  (`check_reliability=true`) ≠ `no-fault-detected` → `q='bad'`; `priority-array` — лише для AO/AV/BV при
  `address.read_priority_array=true` (у `Reading` не передається; потрібно для `write` release — кешується).
- `mode='cov'`: після `connect` — `SubscribeCOV(subscriber_process_id=<hash сигналу>, object, confirmed=False,
  lifetime=cov_lifetime_s)`; `UnconfirmedCOVNotification` → показання (`ts` = час прийому; `present-value` і
  `status-flags` з повідомлення); поновлення підписки на 2/3 `lifetime`; відмова (`Error`/таймаут) → сигнал
  переводиться в `poll` з `period_s` до наступного `connect`; метрика `collector_bacnet_cov_active`.
  Сигнали `mode='poll'` опитуються планувальником як звичайно; у `cov` планувальник також виконує
  контрольне читання раз на `max(period_s·10, 300)` с (виявлення «мовчазної» підписки).
- `write(signal, value, text)`: заборонено, якщо `params.read_only` (`NotSupported("read-only device")`) —
  перевірка в коді, не лише в даних (D-07); інакше `WriteProperty(object, 'present-value', value,
  priority=address.priority or 8)`; `MultiState` з `text` → індекс за `states`; `text == "null"` або
  `value is None` → `Null` (release пріоритету); результат `"written 80.0 @prio 8"`; `Error:
  write-access-denied` → `WriteError`.
- `health()`: `online`, якщо останній RPM/COV без помилки ≤ 2 періоди; `stats`: `polls`, `cov_notifications`,
  `errors`, `latency_ms`.
- Тести: `bacpypes3` тестовий пристрій (`tests/conftest.py: bacnet_device`) з об'єктами AI:1, AI:3, AO:1,
  MSV:1, BI:1 на вільному UDP-порту (без роутера); стенд — емулятор (роутер + мережа 2).

### 8.9 Метрики (`core/metrics.py`, `/metrics`)

`collector_up`, `collector_config_etag_info{etag}`, `collector_readings_total{source}`,
`collector_readings_rejected_total{reason}`, `collector_push_total{status}` (`ok|retry|rejected|locked`),
`collector_push_latency_seconds` (histogram), `collector_buffer_rows`, `collector_buffer_dropped_total`,
`collector_source_up{source,type}` (0/1), `collector_poll_seconds{source}` (histogram),
`collector_poll_errors_total{source}`, `collector_poll_overrun_total{source}`,
`collector_mqtt_messages_total{source}`, `collector_mqtt_missing_path_total{source}`,
`collector_http_push_requests_total{route,status}`, `collector_bacnet_cov_active{source}`,
`collector_commands_total{state}`, `collector_clock_skew_seconds`. `GET /health` → `{"status": "ok|degraded",
"odoo": "ok|unreachable", "buffer_rows": n, "sources": {"online": n, "error": n}}` — `degraded`, якщо Odoo
недоступний > 5 хв або будь-яке джерело в `error` > 10 хв; контейнер при `degraded` не перезапускається.

### 8.10 Логування й безпека

- JSON-логи (`F3D_LOG_JSON=1`): `{"ts","level","logger","msg","source","code","route","cmd"}`; `SecretFilter`
  замінює значення змінних `F3D_*TOKEN*`, `F3D_*PASSWORD*`, `F3D_*SECRET*`, заголовків `Authorization`,
  `X-F3D-Token`, параметрів `password=`/`token=` в URL на `***`. Рівень `INFO`; `pymodbus`, `paho`,
  `bacpypes3` — `WARNING`.
- `allowlist(host)`: резолв hostname → IP; IP ∈ множині (`F3D_ALLOW_HOSTS`: імена, IP, CIDR); Odoo-хост
  додається автоматично; відмова → `AllowlistDenied` + `collector_allowlist_denied_total` + WARNING; жодного
  з'єднання поза списком — тест `test_allowlist_blocks_connect`.
- Запис у пристрої: чотири запобіжники (ARCH §2.6); плагін отримує `write()` лише після перевірок ядра;
  `bacnet_ip` додатково відмовляє для `read_only`.
- Конфігурація з Odoo валідується схемами до створення плагінів; невалідне джерело → `error` у статусі, не
  падіння процесу.
- Образ: non-root, `read_only`, без shell-утиліт, `pip install --no-cache-dir`, `HEALTHCHECK`.

## 9. Алгоритми й правила

| ID | Правило | Алгоритм / формула | Приклад (вхід → вихід) |
|---|---|---|---|
| R-01 | **Формат коду сигналу** | `^[a-z_]+(/[A-Za-z0-9_\-\.]+)+$`, ≤ 128 (= iot_sim M-03). Перший сегмент — розділ payload переглядача (`energy`, `equipment`, `ventilation`, `fire`, `infra`, `workcenters`, `lighting`, `yard`, `access`), останній — ключ у вузлі | `equipment/FL-C1/battery` ✓; `ventilation/units/RV-05/filter_dp_pa` ✓; `Equipment/FL-1` ✗ (великі), `equipment` ✗ (один сегмент), `energy//x` ✗ |
| R-02 | **Перетворення значення** | У колекторі: `eng = f_addr(raw)` за адресою (Modbus: `raw·scale_addr + offset_addr`, агрегація `agg`; MQTT/BACnet/REST: число як є; `map` для станів), потім `value = eng · signal.scale` (default 1). В Odoo значення не перетворюється (окрім округлення в представленнях за `decimals`). Переглядач — R-12 | ADAM-6017 AI0 raw 60 950, адреса `scale=32000/65535=0.48829`, `offset=0` → 29 760 м³/год; RTD raw 35 716, `scale=200/65535=0.0030519`, `offset=−50` → 59,0 °C; Elektronikon HR 3002 = 6772, `scale=0.001` → 6,772 бар |
| R-03 | **Політика зберігання** | Показання з `q != 'bad'` і `ts > last_ts` завжди оновлює `last_value/last_text/last_ts/last_quality`. У `f3d.reading` пишеться, якщо: (а) `store_period_s == 0`; або (б) `last_stored_ts` порожній або `ts − last_stored_ts ≥ store_period_s`; або (в) змінився `status` (R-04) або `last_text` (стан); або (г) `q == 'bad'` (діагностика, не частіше ніж раз на `store_period_s`). Показання старіше `last_ts` (повтор з буфера) — пишеться за (б) відносно найближчого збереженого, але `last_*` не чіпає. Після запису `last_stored_ts = ts` | `store_period_s=300`, показання кожні 10 с: за годину зберігається 12, `last_value` оновлюється 360 разів; стан техніки `busy→charging` — записується одразу |
| R-04 | **Статус за порогами** (чиста функція `tools/thresholds.eval_status(state, value, text, ts, cfg)`) | `kind ∈ {gauge, counter}`: `breach = alarm_low_on ∧ v < alarm_low` або `alarm_high_on ∧ v > alarm_high` → рівень `alarm`; інакше `warn_low_on ∧ v < warn_low` або `warn_high_on ∧ v > warn_high` → `warn`; інакше `ok`. **Гістерезис**: якщо поточний `status` уже `alarm` (`warn`), вихід у нижчий рівень лише коли `v ≥ alarm_low + h` (для нижнього) / `v ≤ alarm_high − h` (для верхнього), `h = hysteresis`. **Мінімальна тривалість**: перехід у вищий рівень (`ok→warn`, `ok→alarm`, `warn→alarm`) набуває чинності, коли умова тримається ≥ `min_duration_s` (`breach_since` = перший `ts` порушення; `ts − breach_since ≥ min_duration_s`); зниження — негайно. `kind='state'`: `text ∈ alarm_states` → `alarm`, інакше `ok`. `kind='event'`: завжди `ok`. `q='bad'` → статус не змінюється. Зміна статусу → `status_since = ts`, чаттер «Стан: норма → тривога (304,2 Па)». `stale` → при першому показанні повертається до обчисленого | RV-05 `alarm_high=250`, `h=10`: 285 → `alarm`; 248 → лишається `alarm` (≥ 240); 239 → `ok`. FL-C1 `warn_low=25`, `alarm_low=15`: 23,6 → `warn`; 14,2 → `alarm`; 26 → `ok`. COMPRESSOR `alarm_low=6.0`, `h=0.1`, `min_duration_s=30`: 5,9 о 10:00:00 → `breach_since`; 5,95 о 10:00:30 → `alarm`; 6,05 → лишається; 6,11 → `ok`. `equipment/COMPRESSOR/state` `alarm_states=["fault"]`: `fault` → `alarm`, `loaded` → `ok` |
| R-05 | **Тривога → заявка ТО** (§6.8, CT-05) | Умови створення: `status` став `alarm` (перехід) ∧ `create_request` ∧ `equipment_id` ∧ `maintenance_request_id` порожнє (або його `stage_id.done`) ∧ (`request_closed_at` порожнє або `now − request_closed_at ≥ realarm_cooldown_s`). Поля: `name = render_title`, `equipment_id`, `maintenance_type='corrective'`, `maintenance_team_id = equipment.maintenance_team_id or param default_team_id`, `priority = alarm_priority`, `f3d_signal_id`, `f3d_equipment_code`, `f3d_origin='threshold'`, `f3d_value=v` (або `text`), `f3d_threshold` (поріг, що спрацював), `description` = «Автоматично з телеметрії: сигнал <code>, показник <v> <unit> <rel> порогу <thr> <unit>, джерело <source.code>, час <ts Київ>.», `request_date=today`, `schedule_date=now`. Сигнал: `maintenance_request_id=request`; чаттер сигналу «Створено заявку <name>». **Шаблон заголовка**: `alarm_title` з плейсхолдерами `{name}` (назва сигналу), `{equipment}` (`equipment_id.name`), `{code}` (`f3d_code` обладнання), `{quantity}`, `{value}` (округлено до `decimals`, кома як десятковий роздільник), `{unit}`, `{threshold}`, `{rel}` («до» для верхнього порогу, «від» для нижнього), `{text}`; порожній `alarm_title` → умовчання `"{name}: {value} {unit} при нормі {rel} {threshold} {unit}"`; для `state` — `"{name}: стан «{text}»"`. Довжина ≤ 256. Кілька сигналів одного обладнання → кілька заявок (дедуплікація — на сигнал, не на обладнання) | RV-05 (`alarm_title="Заміна фільтрів: перепад тиску {value} Па при нормі до {threshold}"`, `decimals=0`): 285,2 → «Заміна фільтрів: перепад тиску 285 Па при нормі до 250». FL-C1 battery (`alarm_title="Зарядити АКБ: заряд {value} % при нормі від {threshold}"`, `decimals=1`): 14,2 → «Зарядити АКБ: заряд 14,2 % при нормі від 15». COMPRESSOR pressure без `alarm_title`: 5,9 → «Компресор: тиск 5,9 бар при нормі від 6,0 бар». FA-FAC dust → «Очистити сповіщувач: запиленість 92 % при нормі до 90». COMPRESSOR state `fault` → «Компресор: стан «fault»» |
| R-06 | **Закриття заявки** | `maintenance.request.write` з переходом у `stage_id.done`: для `f3d_signal_id`: `maintenance_request_id=False`, `request_closed_at=now`; `status` перераховується з `last_value` за R-04 **без** мін. тривалості й без створення заявки; чаттер сигналу «Заявку <name> закрито; стан: <status>»; якщо `status` лишився `alarm` — додатково «Тривога триває, нова заявка не раніше <now + cooldown Київ>». Повторне відкриття заявки (`done → not done`): якщо сигнал без відкритої заявки — `maintenance_request_id = request` знову. Видалення заявки — `ondelete set null` → сигнал без заявки, `request_closed_at=now` | RV-05: заявка закрита, емулятор скинув 120 Па → `ok`; закрита без ремонту при 300 Па → `alarm` лишається, нова заявка — через 1 год при наступному показанні > 250 (перехід не потрібен: при `status=alarm` і порожній заявці після cooldown Ingester створює заявку за «утриманням» — умова R-05 перевіряється на кожному показанні в `alarm`, не лише на переході) |
| R-07 | **Stale** | `stale_after = max(stale_periods · period_s, stale_min_s)`. Крон щохвилини: сигнали з `status ∈ {ok,warn,alarm}` ∧ `source_id` ∧ `last_ts < now − stale_after` → `_mark_stale('timeout')`. Джерело `offline/error/disabled` (API-03 або крон колектора) → усі його сигнали зі `status ≠ unknown` → `stale` одразу. Сигнали **без** `source_id` (`sim_data` до прив'язки) — ніколи не `stale` (п. 4 ARCH §1.4). `stale` не змінює `maintenance_request_id` і не створює заявок (Q-11). Перше валідне показання → R-04 | `equipment/COMPRESSOR/pressure_bar` `period_s=10` → `stale_after = max(30, 60) = 60 с`; `equipment/FL-1/battery` `period_s=5` → 60 с; `infra/water/m3_total` `period_s=60` → 180 с; `energy/consumers/SAW-1/p_now` без джерела → лишається `ok` зі значенням рівня 0 |
| R-08 | **Лічильники й похідні** | `kind='counter'`: значення монотонні; показання `v < last_value − 1 %·last_value` (крім `v` близько 0 при скиданні лічильника, наприклад `cycles_today` о 00:00) → `q='uncertain'`, приймається (можливий ролловер/заміна лічильника), чаттер раз на добу. `derive_rule='rate_h'` (`infra/water/flow_m3h`): при кожному показанні джерела `m3_total` Ingester бере найстаріше збережене показання джерела у вікні `[ts − 300 с, ts − 60 с]` (або `last_stored` старше 60 с) і пише похідне показання `value = (v − v_prev) / ((ts − ts_prev)/3600)` з `ts` джерела, `src` як у джерела; немає попереднього → пропуск. `cycles_today` (`equipment/GANTRY-1/cycles_today`) — лічильник з добовим скиданням: `sim_params.reset='daily'` | вода: 18 642,00 о 10:00, 18 642,35 о 10:10 → `flow_m3h = 0,35/(600/3600) = 2,1 м³/год`; `hours` 17 846,6 → 17 846,8 (+0,2 за 12 хв) ✓; 17 846,8 → 17 000 → `uncertain` |
| R-09 | **Годинні агрегати** | Крон: `INSERT INTO f3d_reading_hour (signal_id, equipment_id, hour, v_min, v_avg, v_max, v_sum, v_count, v_first, v_last, delta) SELECT signal_id, max(equipment_id), date_trunc('hour', ts), min(value), avg(value), max(value), sum(value), count(*), (array_agg(value ORDER BY ts))[1], (array_agg(value ORDER BY ts DESC))[1], CASE WHEN s.kind='counter' THEN last−first ELSE 0 END FROM f3d_reading r JOIN f3d_signal s … WHERE r.quality <> 'bad' AND ts >= %s AND ts < %s GROUP BY signal_id, date_trunc('hour', ts) ON CONFLICT (signal_id, hour) DO UPDATE SET …`. Вікно: від `max(hour) − 1 год` (повторний перерахунок останньої години — для показань, що прийшли з буфера пізніше) до `date_trunc('hour', now) − 1 год`; `stale`/`state` сигнали агрегуються за `value` (індексом) — для станів `v_avg` сенсу не має, UI показує `v_last`. Рядки `text` без `value` (події) — `v_count` тільки | RV-05 за 10:00–11:00 при 12 збережених показаннях 280…290 → `v_min=280`, `v_max=290`, `v_count=12`; `hours` компресора `v_first=17 846,6`, `v_last=17 847,6`, `delta=1,0` |
| R-10 | **Ротація** | Щодня: `DELETE FROM f3d_reading WHERE id IN (SELECT id FROM f3d_reading WHERE ts < %s ORDER BY ts LIMIT 50000)` у циклі ≤ 60 с (`now − keep_days`); `f3d_reading_hour` — `hour < now − keep_hours_days`; `f3d_push_event` — `ts < now − keep_days`. Агрегати за видалені години лишаються. Лог INFO з кількостями; `VACUUM` не викликається (autovacuum) | `keep_days=30` на 14.11: усе до 15.10 видаляється; агрегати з 13.10 лишаються до 400 днів |
| R-11 | **ТО за лічильником** | Перевірка `_f3d_meter_check` при кожному оновленні `f3d_meter_signal_id.last_value` (Ingester, після `last_*`): `next = f3d_meter_last_value + f3d_meter_interval`; `lead = interval · lead_pct/100`; якщо `current ≥ next − lead` ∧ `f3d_meter_request_id` порожнє (або `done`) → `maintenance.request`: `name = "ТО за лічильником: {f3d_code} — {next:n} {unit} (зараз {current:n})"`, `maintenance_type='preventive'`, `maintenance_team_id` як R-05, `priority='1'` (`'3'`, якщо `current ≥ next`), `f3d_signal_id = meter`, `f3d_origin='meter'`, `f3d_value=current`, `f3d_threshold=next`, `schedule_date = now + max(0, (next − current)/rate)` де `rate` = `delta` за останні 7 діб з `f3d.reading.hour`/168 год (невідомо → `now`); `equipment.f3d_meter_request_id = request`; чаттер обладнання. Закриття (`_f3d_meter_closed`): `f3d_meter_last_value = meter.last_value` на момент закриття, `f3d_meter_last_date = today`, `f3d_meter_request_id=False` → `next` перераховується. Зміна `f3d_meter_last_value/interval` вручну → перевірка повторюється при наступному показанні. Сигнал без показань (`unknown`) — нічого | COMPRESSOR: `last=16 000`, `interval=2 000`, `lead 5 %` → `next=18 000`, заявка при `current ≥ 17 900`: на демо `hours=17 846,6` → заявки ще немає, `remaining=153,4`; при 17 900,2 → «ТО за лічильником: COMPRESSOR — 18 000 год (зараз 17 900)», `schedule_date` ≈ через `99,8/ (8,5/24)` ≈ 11,7 доби (з `delta` 8,5 год/добу, iot_sim R-06). FL-2: `last=3 000`, `interval=1 000`, `hours=3 216,5` → `next=4 000`, `remaining=783,5` |
| R-12 | **Значення для переглядача** (CT-07; порт `odoo_pull.sync_signals`) | Для кожного сигналу (`active`, `viewer_visible`, `status ≠ unknown`): `*path, leaf = code.split('/')`; `node = payload[path[0]]…[path[-1]]` — якщо будь-який крок не `dict`/відсутній → пропуск (без створення вузлів). `kind ∈ {gauge, counter}`: `v = last_value`; `unit == '%'` → `node[leaf] = round(v/100, 3)`; інакше `round(v, 2)` при `abs(v) < 20`, інакше `round(v, 1)`. `kind='state'`: `node[leaf] = last_text` (для техніки `equipment/<code>/state` — значення `busy|charging|idle|to_charge|offline|fault`; `to_charge` → `busy` робить адреса `map`, тож тут без перетворень). Після циклу: якщо є обидва `infra.totals.pv_now` і `energy.totals` → `energy.totals.pv_kw = infra.totals.pv_now`; так само `chp_kw`. `meta.iot = {"source": "телеметрія (factory3d_telemetry)", "signals": n_видимих, "alarms": count(status=alarm), "stale": count(stale), "updated": local(max(last_ts)) "YYYY-MM-DD HH:MM" Київ}`. `ctx.lite`/`ctx.kiosk` — без відмінностей | `equipment/FL-C1/battery` 23,6 % → `equipment["FL-C1"].battery = 0.236`; `equipment/COMPRESSOR/hours` 17 846,6 → `17846.6`; `pressure_bar` 6,772 → `6.77`; `equipment/FL-C1/state` `charging` → `equipment["FL-C1"].state = "charging"`; `infra/water/m3_total` → вузол `infra.water` відсутній у payload → пропуск (поки energy/infra-провайдер його не створить); `equipment/FL-1/x` — `viewer_visible=False` → пропуск |
| R-13 | **Шина (дебаунс)** | Після обробки пакета: `codes = {сигнали, у яких змінився last_value/last_text/status}`; для кожного — якщо `last_notified_ts` порожній або `now − last_notified_ts ≥ bus_min_interval_s` або змінився `status` → у список повідомлення і `last_notified_ts=now` (SQL batch); далі один виклик `_notify_viewer(codes)` → viewer M-03 коалесує в одне повідомлення на транзакцію. Без viewer — лише оновлення `last_notified_ts` не робиться | 8 навантажувачів шлють кожні 5 с → переглядач отримує код не частіше 1 разу на 10 с на сигнал; зміна стану `busy→charging` — негайно |
| R-14 | **Часові пояси** | База: UTC naive. API вхід: ISO 8601 з `Z`/зсувом → `datetime.fromisoformat` (Python 3.12 розуміє `Z`) → `astimezone(UTC)` → naive; без tzinfo → `ts_no_tz`. API вихід: `…Z`. Тексти заявок/чаттера/`meta.iot.updated`: `Europe/Kyiv` через `pytz`/`zoneinfo` (`fields.Datetime.context_timestamp` з `tz='Europe/Kyiv'` — не з користувача, бо контролер працює від суперкористувача). Рівень 0: `x_time`/`x_updated` — UTC naive (сервер Odoo у UTC), переносяться як є. Колектор: усі `Reading.ts` tz-aware UTC; MQTT `ts` `+03:00` → UTC; Axis `capture_timestamp` epoch мс → UTC | `"2026-10-14T06:10:03.250+03:00"` → `2026-10-14 03:10:03.250` UTC; у заявці «час 14.10.2026 06:10» (Київ) |
| R-15 | **Виведення `module`, `kind`, порогів і заголовків при міграції** | `module` за префіксом коду (CT-09): `energy/*`, `infra/*` → `energy`, крім `infra/water/*` → `telemetry`, `infra/genset/*` → `genset`; `ventilation/*`, `lighting/*` → `bms`; `fire/*` → `fire_safety`; `equipment/*` → `telemetry`; `workcenters/*` → `machine_connect`; `yard/*` → `yard`; `access/*` → `access`; інше → `other`. `kind` за `x_mode`: `hours`, `energy`, `counter` → `counter`; решта (`noise`, `machine`, `drain`, `drift`, `level`, `solar`) → `gauge`. Пороги: `x_alarm='above'` → `alarm_high=x_threshold`, `alarm_high_on=True`; `'below'` → `alarm_low`; інакше вимкнені; `hysteresis` = 2 % від `|threshold|` для `drift` (RV: 5 Па; DUST 0,036 кПа; FA-FAC 1,8 %), 0 для решти. `alarm_title` за `quantity` + `x_alarm`: «Перепад» above → «Заміна фільтрів: перепад тиску {value} {unit} при нормі до {threshold}»; «Запиленість» above → «Очистити сповіщувач: запиленість {value} % при нормі до {threshold}»; «Тиск» below → «{equipment}: тиск {value} бар при нормі від {threshold}»; «Температура» above → «{equipment}: температура {value} °C при нормі до {threshold}»; «Вакуум» above → «Портал: вакуум {value} кПа при нормі нижче {threshold}»; інакше порожньо (умовчання R-05). `decimals`: `unit ∈ {Па, %, шт}` → 0; `кВт·год, год` → 1; інакше 2. `quantity = x_kind`; `name = x_name`; `sequence = x_sequence`; `status`: `'тривога'` → `alarm`, інакше `ok`; `status_since = x_updated` | `ventilation/units/RV-05/filter_dp_pa`: `module=bms`, `kind=gauge`, `alarm_high=250`, `h=5`, заголовок «Заміна фільтрів…»; `energy/consumers/SAW-1/kwh_shift`: `module=energy`, `kind=counter`, `derived_from=…/p_now`; `equipment/FL-1/hours`: `telemetry`, `counter` |
| R-16 | **ETag конфігурації** | `etag = sha256(json.dumps(payload без ключів etag/generated_at/server_time, sort_keys=True))` — обчислюється при кожному запиті (≤ 50 мс на 1 000 сигналів); `collector.config_etag = etag` (без `write` якщо не змінився). `If-None-Match` збіг → `304`. Будь-який `write` у `f3d.source`/`f3d.signal` з полями конфігурації чи глобальних параметрів змінює payload → інший etag автоматично | зміна `period_s` сигналу → наступний `push` повертає новий `config_etag` → колектор перечитує |
| R-17 | **Валідація, ідемпотентність і паралельність push** (`tools/ingest.Ingester`) | 1) розбір і валідація елементів (reason-коди API-02); 2) ліміт частоти: `rate_window_start`/`rate_count` на колекторі — вікно 60 с, > `push_rate_per_min` → `429`; 3) `signals = search_read([('code','in',codes)], fields…)` одним запитом; чужі/неактивні → reject; 4) сортування показань за `(code, ts)`; 5) для кожного сигналу — послідовно `_apply_reading` у пам'яті (R-03/R-04/R-08) → списки: `to_store`, `last_updates`, `status_changes`, `requests_to_open`, `meter_checks`, `derived_readings`; 6) `execute_values("INSERT INTO f3d_reading (signal_id, equipment_id, ts, value, text, quality, src) VALUES %s ON CONFLICT (signal_id, ts) DO NOTHING RETURNING signal_id")` → `stored`; `duplicates = len(to_store) − stored`; 7) `executemany("UPDATE f3d_signal SET last_value=%s, last_text=%s, last_ts=%s, last_quality=%s, last_stored_ts=%s WHERE id=%s AND (last_ts IS NULL OR last_ts < %s)")` — старіше показання з іншого воркера не перезапише новіше; 8) `invalidate_model(['last_value','last_text','last_ts','last_quality','last_stored_ts'])`; 9) ORM `write` для `status/status_since/breach_since` (лише змінені), `_open_request` (R-05), `_f3d_meter_check` (R-11), чаттер; 10) R-13 шина; 11) відповідь. Усе в одній транзакції запиту; виняток → `500` і повний відкат (колектор повторить пакет; дублікати відсіє `ON CONFLICT`). Для CT-10 (`src='module'`) — ті самі кроки без п. 2 і без перевірки колектора | пакет 1 000 показань × 55 сигналів → 1 `search_read`, 1 `execute_values`, 1 `executemany`, ≤ 55 ORM-записів; повтор того самого пакета → `duplicates=1000`, `stored=0`, `changed=[]` |
| R-18 | **Життєвий цикл команди** | 1) створення (`f3d.command.create`): `signal.write_enabled` ∧ `signal.source_id.write_enabled` ∧ параметр `write_enabled` — інакше `UserError("Запис у пристрій вимкнено: <що саме>")`; користувач без `group_f3d_manager` → `AccessError`; `source_id.params.read_only` → `UserError("Джерело лише для читання.")`; 2) `queued` → API-06 віддає → `sent`; 3) колектор: четвертий запобіжник `F3D_WRITE_ENABLED`; `plugin.write` → API-07 → `done`/`failed`; 4) `expires_at` минув у `queued/sent` → `expired` (крон); 5) `done` → через ≤ `period_s` сигнал покаже нове значення (окремо, читанням); команда не змінює `last_value` сама | менеджер ставить `ventilation/units/RV-05/heating_valve = 80` → колектор `WriteProperty AO:1 = 80 prio 8` → `done`; при `F3D_WRITE_ENABLED=0` колектор не опитує API-06 → команда `expired` через 10 хв з чаттером «Колектор не забрав команду» |
| R-19 | **Планувальник, пакети, бекоф, буфер** | §8.3.3–§8.3.4. Формули: джиттер старту `U(0, period)`; бекоф `min(30, 2^n)` с для `poll`, `min(60, 2^n)` для `connect` і Odoo; пакет відправляється при `len(buffer) ≥ push_max` або за таймером `push_interval_s`; буфер FIFO, ліміт за розміром файлу (`PRAGMA page_count·page_size`), перевірка раз на 60 с | Odoo недоступний 1 год при 15 показаннях/с → 54 000 рядків ≈ 5 МБ у буфері; після відновлення — 54 пакети по 1 000 з інтервалом ≥ 1 с (без очікування `push_interval_s`, якщо буфер ≥ `push_max`) |
| R-20 | **Modbus: декодування і групування** | Типи: `bool` (coil/DI або біт `bit` регістра), `u16`, `i16` (1 регістр), `u32`, `i32`, `f32` (2), `u64`, `i64`, `f64` (4); `wordorder` `big` (старше слово в першому регістрі — PM5560, Huawei, Elektronikon за iot_sim) або `little` (ADAM лічильники: низьке слово першим — iot_sim §8.4.2); `byteorder` `big` (Modbus-стандарт) — `little` лише для екзотики. Групування: сигнали одного `unit` і `fc` сортуються за `addr`; сусідні об'єднуються в блок, якщо `addr_next − (addr_last + count_last) ≤ params.gap_max` (default 8) і довжина блоку ≤ `params.max_block` (125 регістрів / 2000 бітів); один запит на блок; `agg` (`max|min|sum|avg|first`) — над `count` однотипних значень. Адреси у `address.addr` — **PDU** (A-01); `doc` ігнорується | u70: `pressure` addr 3001, `load` 3009, `hours` 3019 (u32) → один блок `3000…3020` (21 регістр); u96 T1 `addr 0, count 3, agg max` + T2 `addr 3, count 3` → блок 0…5; ADAM лічильник води `addr 16, u32, little`: регістри `[0x2E2A, 0x001C]` → `0x001C2E2A = 1 846 826` імп × 0,01 = 18 468,26 м³ |
| R-21 | **MQTT: відображення** | §8.6; `path` — підмножина JSONPath: `$`, `.key`, `[n]`; значення `bool` → 0/1; `null` → пропуск; рядок-число → `float` (для gauge/counter); `map` застосовується до `str(val)`; `ts_path` → ISO або epoch (с/мс за величиною > 10¹¹ → мс); `retain` → `q='uncertain'` | `{"battery_pct": 57.1, "state": "to_charge", "ts": "2026-10-14T08:15:03+03:00"}` → `equipment/FL-1/battery = 57.1`, `state` з `map {"to_charge":"busy"}` → `busy`, `ts` 05:15:03Z |
| R-22 | **HTTP push: маршрутизація в Odoo** (API-05) | Для події `route`: (1) `f3d.push.event` (дублікат → reject); (2) обробники M-11 у порядку `_name`, кожен у `savepoint`; (3) сигнали: `search([('source_id.type','=','http_push'), ('source_id.collector_id','=',collector), ('active','=',True)])` з `address.route == route` і `all(payload.get(k) == v for k, v in address.match.items())` → `val = jsonpath(address.path, payload)` → `_f3d_ingest([{code, ts, value|text}])`; `kind='event'` → `value=1`, `text = str(val)[:64]`; `signal_count` у журналі | подія CAM-05 `plateText=AA4512KT`: обробник yard (`f3d.push.handler.yard.lpr`) знаходить бронювання; сигнал `yard/lpr/CAM-05/plate` (`address={"route":"lpr","match":{"sensorProviderID":"CAM-05"},"path":"$.plateText","ts_path":"$.capture_timestamp"}`) → показання `text="AA4512KT"`, `ts` з epoch мс |
| R-23 | **BACnet: адресація, COV, запис** | §8.8. `object` приймає канонічні назви ASHRAE (`analog-input`, `analog-output`, `analog-value`, `binary-input`, `binary-output`, `binary-value`, `multi-state-value`, `multi-state-input`, `life-safety-zone`, `life-safety-point`, `device`) і короткі `AI/AO/AV/BI/BO/BV/MSV/MSI/LSZ/LSP` (нормалізуються валідатором); `property` default `present-value`; `index` — для масивів (`priority-array[8]`); `mode` default `cov` для AI/BI/MSV/LSZ/LSP, `poll` для решти; `cov_lifetime_s` default 300; `priority` 1…16 default 8 (запис). `Enumerated`/`MultiState` → `map` або `states` (1-based індекс MSV → `states[idx−1]`); `BinaryPV` → `inactive/active` → `map` (default `{"0":"off","1":"on"}` для state, 0/1 для gauge); `LifeSafetyState` → назва enum (`quiet`, `alarm`, `fault`, `test-alarm`…) → `text`. Складений стан — `states[]` з `object/instance/eq/text` (перший збіг) | `equipment/BOILER/supply_c`: `{"device":140,"object":"AI","instance":1,"mode":"cov"}`; `ventilation/units/RV-05/mode` (bms): `{"device":105,"object":"MSV","instance":1,"map":{"1":"VE","2":"VEL","3":"AQ","4":"REC","5":"EA","6":"SA","7":"ST","8":"Off"}}`; `fire/groups/FA-CUT/state` (fire_safety): `{"device":200,"object":"LSZ","instance":12}` → `text="alarm"`; запис `heating_valve` 80 → `WriteProperty dev105 AO:1 PV 80.0 prio 8` |
| R-24 | **Парсер адрес каталогу емулятора** (`tools/sim_catalog.parse_sim_address(protocol, text) -> dict|None`, CT-11, A-18) | Регулярні вирази над колонкою «Адреса в джерелі» Додатка A iot_sim; результат — `address` за Додатком A.1 цього документа; правило PDU iot_sim §8.4.1: `N ≥ 40001 → N − 40001`, `30001 ≤ N < 40000 → fc 4, N − 30001`, `coil/DI 00001… → N − 1`, інакше `N − 1`. Шаблони: (1) `Modbus u(\d+)(?: \([^)]*\))? HR (\d+)(?:[–-](\d+))?` → `{"fc":3,"addr":pdu(a),"count":b−a+1 або за type,"unit":u}`; `type` з колонки «Тип» (`U16/I16/U32/I32/I64/F32` → нижній регістр), `wordorder: "little"` якщо в тексті `ADAM` і `лічильник`; `scale` з колонки «Масштаб» (`×0,001` → 0.001; `R-20` → лінійні коефіцієнти з діапазону в дужках `4–20 мА = 0…32 000` → `scale=(hi−lo)/65535`, `offset=lo`; `0–65535 → −50…+150` → `scale=200/65535, offset=−50`); (2) `Modbus u(\d+)(?: \([^)]*\))? DI(\d+) coil 0*(\d+)` (і кілька через кому для складеного стану) → `{"fc":2,"addr":n−1,"type":"bool"}` або `states[]`; `DO(\d+) coil` → `write`; (3) `MQTT (\S+) → \$\.(\S+)` → `{"topic","path":"$.…"}`; (4) `BACnet dev (\d+) (AI|AO|AV|BI|BO|BV|MSV|LSZ|LSP):(\d+)` (кілька — `states[]`), `Present_Value` → `present-value`; (5) `OPC UA|ns=2;s=…` → `{"nodeid"}`; (6) `GET (/\S+) → \$\.(\S+)` → `{"method":"GET","path":…,"json_path":"$.…"}`; (7) `HTTP POST <collector>/f3d/(\w+) → (.+)` → `{"route","path":"$.<перше поле>"}`; (8) `SICS … «(\w+)»` → `{"cmd"}`; (9) `Σ Modbus u61…u68`, `похідна`, `GET /api/v1/jobs?…` і все інше → `None` (→ `unparsed`). `map` для enum з колонки «Одиниця» виду `0 stop/1 load/2 unload/3 fault` → `{"0":"stop",…}`. Huawei-рядки (`u61…u69`) позначаються `address.doc += " [notation?]"` (Q-04) | `Modbus u70 (Elektronikon Mk5, ПРИПУЩЕННЯ) HR 3002 (Outlet pressure)` + `U16`, `×0,001` → `{"unit":70,"fc":3,"addr":3001,"type":"u16","scale":0.001,"doc":"HR 3002 (Outlet pressure)"}`; `Modbus u90 (ADAM-6017) HR 40001 (AI0, 4–20 мА = 0…32 000 м³/год)` → `{"unit":90,"fc":3,"addr":0,"type":"u16","scale":0.48829,"offset":0,"range":[0,32000]}`; `Modbus u84 (ADAM-6050) HR 40017–40018 (лічильник DI8, …)` + `U32`, `×0,01` → `{"unit":84,"fc":3,"addr":16,"count":2,"type":"u32","wordorder":"little","scale":0.01}`; `MQTT f3d/mobile/FL-1/telemetry → $.battery_pct` → `{"topic":"f3d/mobile/FL-1/telemetry","path":"$.battery_pct"}`; `BACnet dev 140 AI:1 Present_Value (подача)` → `{"device":140,"object":"analog-input","instance":1,"property":"present-value"}`; `Modbus u84 (ADAM-6050) DI0 coil 00001 (вентилятори в роботі), DI1 coil 00002 (аварія)` → `{"unit":84,"fc":2,"states":[{"addr":1,"eq":1,"text":"fault"},{"addr":0,"eq":1,"text":"running"},{"addr":0,"eq":0,"text":"stopped"}]}` |
| R-25 | **Стан джерела й колектора** | Джерело: API-03 `state` як прислав колектор (`online/offline/error`), `last_ok`, `last_error`, `error_count`; `read_enabled=False` → `disabled` незалежно від звіту; відсутнє у звіті джерело (плагіна немає) → `error: "plugin not installed"` (колектор надсилає його з таким текстом). Колектор: `online` при будь-якому API-02/03/05/06; крон: `last_seen < now − 3·status_interval_s` → `offline` + усі його джерела `online/error` → `offline` → сигнали `stale`. Текст `last_error`: обрізання після `password=`/`token=`/`Bearer ` (регекс), ≤ 512 | колектор мовчить 3 хв → `offline`, 55 сигналів `stale`, дашборд «Огляд» показує 6 джерел у колонці «Офлайн» |

## 10. Стани й переходи

### 10.1 Сигнал (`f3d.signal.status`)

```
unknown ──(перше показання q≠bad)──► ok / warn / alarm   (R-04)
ok ◄──► warn ◄──► alarm              (R-04; вгору — з min_duration_s, вниз — з hysteresis)
{ok,warn,alarm} ──(без показань > stale_after | джерело offline/error/disabled)──► stale   (R-07)
stale ──(показання q≠bad)──► ok / warn / alarm
alarm ──(status став alarm ∧ умови R-05)──► заявка створена (maintenance_request_id)
заявка done (R-06) ──► maintenance_request_id = ∅, request_closed_at = now, status перераховано
```

Побічні ефекти: чаттер при кожній зміні `status`; шина при зміні (R-13); `status_since`.

### 10.2 Джерело (`f3d.source.state`)

`unknown` (створено) → `online` | `offline` | `error` (API-03) → `disabled` (`read_enabled=False`, `write`)
→ `unknown` (`read_enabled=True`); `offline` також із крону колектора (R-25). Перехід у `offline/error/
disabled` → сигнали `stale`.

### 10.3 Колектор (`f3d.collector.state`)

`never` → `online` (перший API-виклик) → `offline` (крон) → `online`. Токен відкликано → колектор отримує
`401` і переходить у режим очікування (буфер росте) — в Odoo `offline` через 3 інтервали.

### 10.4 Команда (`f3d.command.state`)

`queued` → `sent` (API-06) → `done` | `failed` (API-07); `queued|sent` → `expired` (крон); `queued` →
`cancelled` (кнопка). Кінцеві: `done`, `failed`, `expired`, `cancelled`.

### 10.5 Заявка ТО (стандартні стадії `maintenance.stage`)

Створюється на першій стадії (`New Request`); `stage_id.done` → R-06/R-11. Стадії `Repaired`, `Scrap` у
демо — `done=True`.

### 10.6 Міграція рівня 0 (`factory3d.telemetry.level0_migrated.state`)

`{}`/`pending` → `skipped` | `partial` | `done`; `partial` → `done` після усунення розбіжностей і
`f3d_run_migration`.

## 11. Обробка помилок

1. **Пристрій недоступний** — плагін: бекоф R-19, `Health.error`; Odoo: джерело `error` після звіту, сигнали
   `stale` через `stale_after`; відновлення — автоматичне. Жодних заявок ТО через `stale` (Q-11).
2. **Odoo недоступний / `423`** — буфер SQLite до 200 МБ; `423` (стоп-кран) — пакет лишається, опитування
   зупиняються лише коли `read_enabled=false` у відповіді API-01 (перечитується кожні `config_poll_s`);
   при `5xx` — повтор з бекофом; `4xx` (крім 423/429) — пакет відкидається з ERROR (невалідний).
3. **Повтори/дублікати** — `(signal_id, ts)` унікальні; `last_*` не відкочуються назад (R-17 п. 7);
   події `http_push` — за `event_id`; результати команд — `already_done`.
4. **Застарілі дані з буфера** (прийшли після новіших) — зберігаються за R-03, `last_*` не змінюються,
   пороги не переоцінюються, агрегат за годину перерахується наступним кроном (вікно −1 год).
5. **Часові пояси** — R-14; `ts` з майбутнього > 60 с → `ts_future` (годинник пристрою/колектора);
   колектор попереджає про skew; показання з `ts` старіше `keep_days` → `ts_too_old`.
6. **Невалідна адреса/параметри** — `ValidationError` при збереженні в Odoo (валідатор); якщо все ж
   потрапило (data) — колектор відкидає джерело зі `error: "schema: …"`, інші працюють.
7. **Сигнал без обладнання** — пороги працюють, заявка не створюється (`create_request` ігнорується, чаттер
   «Тривога без обладнання — заявку не створено»).
8. **Заявку видалили** — `ondelete set null`; сигнал продовжує як після закриття (R-06).
9. **Команда без `write_enabled`** — не створюється (UserError); якщо прапор вимкнули після `queued` —
   API-06 її не віддає (перевірка при видачі), крон → `expired`.
10. **Гонка двох воркерів Odoo** — `UPDATE … WHERE last_ts < new_ts` + унікальний індекс; транзакція
    push не блокує інші (немає `SELECT … FOR UPDATE` на сигналах; `status` пишеться ORM — конфлікт
    оновлень одного рядка вирішує PostgreSQL серіалізацією за рядком).
11. **Обсяг пакета** — > 2 000 або > 1 МБ → `413`; колектор ділить пакети за `push_max` ≤ 2 000.
12. **Рівень 0 після міграції** — `x_active=False` → провайдер viewer M-01h і `odoo_pull.sync_signals`
    бачать 0 активних; якщо хтось увімкне крон рівня 0 вручну — він оновить лише `x_`-записи (неактивні
    `search` крону за `x_active=True` не знайде → нічого не робить). Повторне ввімкнення `x_active` без
    вимкнення телеметрії створює два джерела значень — заборонено інструкцією ARCH §4.5.
13. **Міграція з розбіжностями** — стан `partial`, рівень 0 не вимикається, адміністратор бачить список у
    налаштуваннях (`level0_state`) і запускає повтор.
14. **MQTT без `ts`** або `ts` невалідний — час прийому, `q='uncertain'` лише для `retain`.
15. **BACnet `WriteAccessDenied`/`read_only`** — команда `failed` з текстом; сигнал без змін.
16. **Переглядач без вузла для шляху** — сигнал пропускається (R-12), без помилок у `meta.errors`.
