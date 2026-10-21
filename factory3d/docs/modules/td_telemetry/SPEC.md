# td_telemetry — специфікація

Версія 0.3 · 14.10.2026 (0.2 — 14.10.2026) · технічне рішення: `docs/modules/td_telemetry/ARCHITECTURE.md` (далі ARCH:
FR-01…FR-31, CT-01…CT-12, A-01…A-25, Q-01…Q-17). Спирається на: каркас §5 (імена, стоп-крани, права), §6.4
(контракт телеметрії), §6.5 (плагіни; D-16 — `bacnet_ip` тут), §6.8 (заявки ТО), D-02,
D-04, D-07, D-11, D-17, D-19, D-20; `td_factory3d` CB-01, CB-07, CB-08, CB-09, CB-10, CB-11; `td_viewer3d` M-01 (хук
провайдера), M-03 (`_notify`), API-03 (`patch.signals`), Додаток C (196 шляхів); `td_iot_sim` §8.4
(Modbus, unit id), §8.8 (P-06), §8.9.3/§8.9.6 (P-07), §8.10.3 (BOILER BACnet), §8.11 (FACP read-only),
§8.13.2 (Axis LPV JSON), M-03 `td.sim.signal`, Додаток A (каталог сигналів — джерело істини для кодів; кількість
рядків веде iot_sim, з доповненнями модулів за X-34), API-01 `GET /f3d/sim/devices`; контракти інших модулів, з якими
звірено сторону telemetry: `td_fire_safety` API-01 (`bacnet_event`), M-18; `td_yard` §8.2 (схеми `sics`),
M-12, Додаток A; `td_machine_connect` §8.3–§8.4 (ключі-розширення `opcua`/`rest_vendor`), M-20; `td_bms`
§8.2 (`helvarnet`), R-25, R-33, Додаток B.

Зміни: 16.10.2026 — QA-фікси (DEC-19, T-2/T-3): ліміт частоти push (R-17 п. 2, `_rate_check`) веде журнал пакетів — `INSERT` у службову таблицю `td_collector_push` (створює `init()`, без FK), `COUNT` за 60 с; поля колектора `rate_window_start`/`rate_count` вилучено; рядки старші 10 хв прибирає `_cron_offline`; зміна IP сама по собі більше не викликає запис `_touch` (`last_ip` пишеться разом із тротлінговим записом або зміною стану). Оновлено M-01, R-17 п. 2, AC-41.

Зміни: 15.10.2026 — за рішенням модуля (build/modules/td_telemetry.md): DEC-10 (AC-78: для одного блоку 3000…3020 джерело з `params.gap_max=10`; `gap_max` за замовчуванням лишається 8 за R-20 і Додатком A.2).

Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-83 («час прийому» = нове поле M-04 `td.reading.received_at`, `fields.Datetime.now()`
у `_td_ingest`, контекст `f3d_received_at`; `event.ts`/`capture_timestamp` — час пристрою лише для відображення й дедуплікації;
R-17 п. 6, R-22 і приклад, API-05, §8.7, хук крок 5 і Додаток D (`create_date` → `received_at`), V-14, AC-49, нова AC-104), X-81
(`write.pulse_ms` лише для імпульсних команд, рівневі записи без нього — A.1, §8.5, AC-09, AC-100), X-86 (порядок провайдерів
з вбудованим `signals` 90 — M-10; ARCH CT-07) (v0.3).

Зміни (v0.2): 14.10.2026 — правки за `docs/CONSISTENCY.md` v0.3: X-02 (API-02/API-05 = `_td_ingest`, R-17 п. 0, точка
розширення M-03), X-03 (CR-01: `td.command.payload`/`result_data`, API-06 `payload`, API-07 `data`, `SourcePlugin.call`;
маніфест 19.0.1.1.0), X-04 (R-18 п. 1 і §4.4: під `env.su` перевірка групи пропускається), X-05 (`bacnet_ip`: маршрут
`bacnet_event`, для `read_only` — лише Who-Is/ReadProperty/ReadPropertyMultiple; перелік маршрутів API-05), X-06 (`stale`
для `mode=cov` — від інтервалу контрольного читання), X-07 (`delta` агрегату — від `v_last` попередньої години), X-16
(`origin='module'`), X-34 (без жорсткої кількості рядків каталогу), X-37 (`positive-integer-value`/`PIV`), X-42 (R-24: PDU
за вендором, без загального «номер − 1»), X-45 (схеми `sics` = yard §8.2), X-46 (`write.pulse_ms`), X-52 (ключі-розширення
`opcua`/`rest_vendor`/`helvarnet` — довідково), X-53 (приклади R-22/API-05/API-06), X-58 (ТК — лише `value`; тіло сценаріїв ТК — `{"params": …}` за загальним рішенням X-57), X-63 (масштаб:
адреса — плагін, `signal.scale` — ядро), X-66 (запис MSV за зворотним `map`); закрито Q-04, Q-08, Q-12, Q-14, Q-15.
Нові ID: AC-93…AC-103, A-23…A-25 (ARCH).
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-05, Q-06, Q-07, Q-10, Q-11, Q-13.
Зміни: 14.10.2026 — закрито рішеннями менеджера: Q-01, Q-02, Q-09, Q-16, Q-17.
Зміни: 14.10.2026 — рівень 0: поріг тривоги температури трансформаторів T1/T2 140 °C (відповідь № 24), демо-базу оновлено.

Позначення: UT — юніт-тест `odoo.tests`; HT — `HttpCase`; CT — pytest колектора з фейковими серверами;
TC — стенд (емулятор + колектор + Odoo); MAN — ручна перевірка на тестовому сервері timur-o19demo
(база `odoo`). Odoo 19: SQL-обмеження — `models.Constraint`; хуки `post_init_hook(env)` /
`uninstall_hook(env)`; `fields.Json`; `request.make_json_response`. Рядки UI — українською в коді (D-14).

## 0. Дерево файлів модуля

### 0.1 Odoo-модуль `odoo_addons/td_telemetry`

```
odoo_addons/td_telemetry/
├── __init__.py                      from . import models, wizard, controllers, tools; from .hooks import post_init_hook, uninstall_hook
├── __manifest__.py                  §1
├── hooks.py                         post_init_hook(env), uninstall_hook(env), run_migration(env) — §5.3–§5.5
├── README.md                        установка, параметри, інструкції ARCH §4
├── CHANGELOG.md                     19.0.1.0.0 — перший випуск; 19.0.1.1.0 — CR-01 корисне навантаження команд (X-03) і правки X-xx
├── models/
│   ├── __init__.py                  порядок: td_collector, td_source, td_signal, td_reading, td_reading_hour, td_command,
│   │                                td_push_event, push_handler, maintenance_equipment, maintenance_request, res_config_settings
│   ├── td_collector.py             M-01
│   ├── td_source.py                M-02
│   ├── td_signal.py                M-03 (+ _td_ingest CT-10, _td_import_sim_catalog CT-11)
│   ├── td_reading.py               M-04
│   ├── td_reading_hour.py          M-05
│   ├── td_command.py               M-06
│   ├── td_push_event.py            M-13
│   ├── push_handler.py              M-11 (AbstractModel td.push.handler, CT-08)
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
│   ├── address.py                   validate_address(type, address, local_types=()) / validate_params(type, params, local_types=()) — Додаток A, R-26 (чисті функції)
│   ├── thresholds.py                eval_status(state, value, text, ts, cfg) -> (status, breach_since) — R-04, §13.0.1; cov_check_s(period_s) — R-07 (чисті функції)
│   ├── ingest.py                    Ingester: валідація пакета, SQL-вставка показань, оновлення last_*, пороги, шина — R-17
│   ├── sim_catalog.py               parse_sim_address(protocol, text) → dict — R-24
│   ├── titles.py                    render_title(signal, value, rel, threshold), fmt_num(x, decimals) — R-05, A-21, шаблони R-15
│   └── gen_signal_data.py           генератор data/signal_catalog.csv з Додатка A iot_sim (Odoo його не вантажить)
├── security/
│   ├── security.xml                 record rules §4.3
│   └── ir.model.access.csv          §4.1
├── data/
│   ├── ir_config_parameter.xml      §5.1 (noupdate="1")
│   ├── ir_cron.xml                  §6
│   ├── td_source_data.xml          7 джерел стенда (noupdate="1"), Додаток C
│   ├── signal_catalog.csv           56 рядків: 29 нових сигналів + 27 прив'язок мігрованих (читає хук, не в `data` маніфесту), Додаток C
│   ├── td_actions.xml              ir.actions.server «Повторити міграцію рівня 0»
│   └── neutralize.sql               §5.6
├── views/
│   ├── menus.xml                    V-22
│   ├── td_collector_views.xml      V-01, V-02
│   ├── td_source_views.xml         V-04…V-07
│   ├── td_signal_views.xml         V-08…V-12
│   ├── td_reading_views.xml        V-13…V-15
│   ├── td_reading_hour_views.xml   V-16
│   ├── td_command_views.xml        V-17
│   ├── td_push_event_views.xml     V-23
│   ├── maintenance_equipment_views.xml  V-18, V-19
│   ├── maintenance_request_views.xml    V-20
│   └── res_config_settings_views.xml    V-21
├── static/description/icon.png      іконка (антена над заводом; 140×140)
└── tests/
    ├── __init__.py
    ├── common.py                    F3DTelemetryMixin, F3DTelemetryCase(TransactionCase), F3DTelemetryHttpCase(HttpCase): фікстури §13.0.1
    ├── test_collector.py            AC-01…AC-03
    ├── test_source.py               AC-04…AC-07, AC-91, AC-92
    ├── test_signal.py               AC-08…AC-12, AC-99, AC-103
    ├── test_readings.py             AC-13…AC-21
    ├── test_thresholds.py           AC-22…AC-26, AC-98
    ├── test_requests.py             AC-27…AC-31
    ├── test_meter.py                AC-32…AC-34
    ├── test_api.py                  AC-35…AC-46, AC-93, AC-94 (HttpCase)
    ├── test_commands.py             AC-47, AC-48, AC-96
    ├── test_push_handler.py         AC-49, AC-50, AC-102
    ├── test_sim_catalog.py          AC-51, AC-52
    ├── test_migration.py            AC-53…AC-57 (AC-58 — ТК-01)
    ├── test_security.py             AC-59…AC-62
    ├── test_views.py                AC-63…AC-65
    └── test_hooks.py                AC-66, AC-67
```

### 0.2 Міст-модуль `odoo_addons/td_telemetry_viewer3d` (A-20)

```
odoo_addons/td_telemetry_viewer3d/
├── __init__.py                      from . import models
├── __manifest__.py                  name "Завод 3D: телеметрія у переглядачі", depends ["td_telemetry", "td_viewer3d"],
│                                    auto_install True, version 19.0.1.0.0, author ToDo, license LGPL-3, data []
├── models/
│   ├── __init__.py
│   └── viewer_provider.py           M-10 td.viewer.provider.telemetry
└── tests/
    ├── __init__.py
    └── test_viewer_provider.py      AC-68…AC-70
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
│   │   ├── commands.py              цикл команд (GET → plugin.write або plugin.call для `payload` → POST result) — R-18, X-03
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
│   │   └── schemas/                 address.<type>.json, params.<type>.json для 8 типів (= Додаток A; копія для jsonschema); `*.sics.json` — копія схем yard §8.2 (X-45)
│   └── util/
│       ├── jsonpath.py              get(path, obj) для підмножини JSONPath: `$.a.b[0].c` — §8.6.2
│       ├── codec.py                 decode_registers(regs, type, wordorder, byteorder) / encode — R-20
│       └── timeutil.py              utcnow(), parse_iso(), to_iso_z()
├── state/                           buffer.sqlite (volume)
└── tests/
    ├── conftest.py                  фікстури: fake_odoo (aiohttp test server з API-01…API-07), modbus_server (pymodbus),
    │                                fake_mqtt (патч paho.Client), mqtt_broker (mosquitto, маркер broker), bacnet_device (bacpypes3), vclock, buffer — §13.0.2
    ├── unit/
    │   ├── test_config.py, test_scheduler.py, test_buffer.py, test_odoo_client.py, test_commands.py, test_registry.py
    │   ├── test_codec.py, test_jsonpath.py, test_allowlist.py, test_logging.py, test_cli.py, test_metrics.py
    │   └── test_plugin_modbus.py, test_plugin_mqtt.py, test_plugin_http_push.py, test_plugin_bacnet.py
    └── stand/                       ТК-01…ТК-16 (pytest -m stand проти compose iot_sim + collector + Odoo)
```

## 1. Маніфест

```python
{
    "name": "Завод 3D: телеметрія",
    "summary": "Джерела, сигнали, показання з обладнання; пороги → заявки ТО; ТО за лічильником; API колектора",
    "description": "Спільний хребет збору даних factory3d: td.collector, td.source, td.signal, td.reading, "
                   "td.reading.hour, td.command; ендпоінти /f3d/telemetry/*; плагіни колектора modbus_tcp, mqtt, "
                   "http_push, bacnet_ip (services/collector); міграція рівня 0 td_iot_sim.",
    "version": "19.0.1.1.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_factory3d", "maintenance", "mail", "web"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",
        "data/td_source_data.xml",
        "data/td_actions.xml",
        "wizard/collector_token_wizard_views.xml",
        "views/td_collector_views.xml",
        "views/td_source_views.xml",
        "views/td_signal_views.xml",
        "views/td_reading_views.xml",
        "views/td_reading_hour_views.xml",
        "views/td_command_views.xml",
        "views/td_push_event_views.xml",
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

Версія `19.0.1.1.0` (X-03, CR-01; відхилення від `19.0.1.0.0` каркаса §5 — затверджене рішення реєстру): додано
`td.command.payload`/`result_data` (M-06), ключ `payload` в API-06 і `data` в API-07, метод плагіна `call()` (§8.3.2).
Поля нові й nullable — скрипт міграції не потрібен. Колектор і Odoo-модуль оновлюються разом (один реліз): команду з
`payload` виконує лише `CommandLoop` з гілкою `call()` (§8.4); `write()` для неї не викликається ніколи.

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

### M-01 `td.collector` — колектор (CT-01)

```python
class F3dCollector(models.Model):
    _name = "td.collector"
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
| `token_hash` | Char(64) | `string="Хеш токена"`, `groups="td_factory3d.group_td_admin"`, `copy=False`, `readonly=True`; sha256 hex |
| `token_hint` | Char(4) | `string="Останні символи токена"`, `groups=…group_td_admin`, `readonly=True` |
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
| `source_ids` | One2many `td.source` `collector_id` | `string="Джерела"` |
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
| `action_generate_token(self)` | `ensure_one()`; перевірка `has_group('td_factory3d.group_td_admin')` інакше `AccessError`; `token = secrets.token_urlsafe(32)`; `write({'token_hash': hashlib.sha256(token.encode()).hexdigest(), 'token_hint': token[-4:], 'token_set_at': now})`; повідомлення в чаттер «Видано новий токен (…hint)»; повертає `act_window` на `td.collector.token.wizard` (`target='new'`, `context={'default_collector_id': id, 'default_token': token}`) |
| `action_revoke_token(self)` | `token_hash=False`, `token_hint=False`; чаттер «Токен відкликано» |
| `@api.model _authenticate(self, raw_token: str)` → recordset (0/1) | порожній/`len > 256` → порожньо; `h = sha256(raw).hexdigest()`; `cands = self.sudo().search([('active','=',True),('token_hash','!=',False)])`; повертає перший, для якого `hmac.compare_digest(c.token_hash, h)` (перебір усіх, без раннього виходу за `token_hash`) |
| `_touch(self, ip, version=None, pushed=False)` | `last_seen=now`, `last_ip=ip`, `version` якщо передано, `last_push_at=now` якщо `pushed`, `state='online'` якщо було інакше (без tracking-шуму: `with_context(mail_notrack=True)`). DEC-19: не частіше за раз на `min(td.telemetry.touch_interval_s = 30, status_interval_s)` с; зміна `state` або версії — одразу; сама зміна IP запису не викликає (T-3: за CDN/проксі IP різний у кожного запиту), `last_ip` пишеться разом із тротлінговим записом або зміною стану. Зміни: 15.10.2026, 16.10.2026 |
| `_config_payload(self)` → dict | API-01 (R-16) |
| `_etag(self)` → str | R-16 |
| `init(self)` | DEC-19 (T-2): `CREATE TABLE IF NOT EXISTS td_collector_push (collector_id integer NOT NULL, ts timestamp NOT NULL)` і `CREATE INDEX IF NOT EXISTS td_collector_push_collector_ts_idx ON td_collector_push (collector_id, ts)`; без FK на `td_collector`. Зміни: 16.10.2026 |
| `_rate_check(self)` → bool | R-17 п. 2: `INSERT (collector_id, now)` у `td_collector_push`, далі `SELECT COUNT(*)` рядків цього колектора з `ts > now − 60 с`; `count <= push_rate_per_min` → `True`, інакше `False` (контролер → `429`). Відхилені пакети теж рахуються. Лічильник не лежить у рядку колектора, тому паралельні push не блокують один одного. Зміни: 16.10.2026 |
| `action_view_sources(self)` | `act_window` `td.source` `domain=[('collector_id','=',id)]`, `context={'default_collector_id': id}` |
| `_cron_offline(self)` | викликається з `cron_td_telemetry_stale`: спершу `DELETE FROM td_collector_push WHERE ts < now − 600 с` (T-2, `RATE_KEEP_S`); далі `online` з `last_seen < now − 3·status_interval_s` → `offline`, усі його джерела `online/error` → `offline`, сигнали → R-07 |

### M-02 `td.source` — джерело даних (CT-01)

```python
class F3dSource(models.Model):
    _name = "td.source"
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
| `collector_id` | Many2one `td.collector` | `ondelete="restrict"`, `idx`, `string="Колектор"`, `tracking=True`; обов'язковий для всіх типів, крім локальних — constraint `_check_f3d_collector_required` (R-26) |
| `is_local` | Boolean | `compute` (не зберігається): `type in self._td_local_types()`; у формі `collector_id` має `required="not is_local"` |
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
| `signal_ids` | One2many `td.signal` `source_id` | |
| `signal_count` | Integer | `compute="_compute_counts"` |
| `alarm_count` | Integer | `compute="_compute_counts"` — сигнали `status='alarm'` |
| `stale_count` | Integer | `compute="_compute_counts"` — `status='stale'` |
| `note` | Text | |

```python
    _f3d_source_code_uniq = models.Constraint("UNIQUE(code)", "Код джерела має бути унікальним.")
    _f3d_source_period = models.Constraint("CHECK(period_s_default >= 1)", "Період опитування має бути ≥ 1 с.")
```

Перевірки (`@api.constrains("type", "params")`): `errors = tools.address.validate_params(type, params, self._td_local_types())`
→ непорожньо → `ValidationError("Параметри джерела %s: %s" % (code, "; ".join(errors)))`.
`@api.constrains("code")`: `CODE_RE` → `"Код джерела: великі латинські літери, цифри, дефіс, крапка."`.
`@api.constrains("type", "write_enabled")`: `type == 'bacnet_ip' and params.get('read_only') and write_enabled`
→ `"Джерело лише для читання (пожежна панель): запис заборонено."`. Зміна `type` при наявних сигналах
→ `ValidationError("Тип джерела з сигналами змінити не можна — створіть нове джерело.")`.
`@api.constrains("type", "collector_id")` `_check_f3d_collector_required`: `not collector_id and type not in
self._td_local_types()` → `ValidationError("Джерело %s: вкажіть колектор." % code)` (R-26).

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `write(self, vals)` | якщо `'read_enabled' in vals and not vals['read_enabled']` → після `super()`: `state='disabled'`, сигнали → `_mark_stale('disabled')` (R-07); якщо `read_enabled` стає `True` → `state='unknown'`; будь-яка зміна `params/read_enabled/write_enabled/active/type` → `collector_id.config_etag=False` (змусити перевидати ETag) |
| `_apply_status(self, item: dict)` | з API-03: `state` ∈ {online, offline, error} (при `read_enabled=False` — лишається `disabled`), `last_ok`, `last_error` (маскування R-25, ≤ 512), `error_count` (= `stats.errors`, якщо є), `stats`; перехід у `offline/error` → `signal_ids._mark_stale(state)`; у `online` — нічого (сигнали оживуть від показань) |
| `action_view_signals(self)` | `act_window` `td.signal`, `domain=[('source_id','=',id)]`, `context={'default_source_id': id}` |
| `action_test_params(self)` | валідатор → `display_notification` «Параметри коректні» / помилки |
| `_default_address(self)` → dict | заготовка адреси для нового сигналу за типом (Додаток A.1, поле «приклад») |
| `@api.model _td_local_types(self) -> list[str]` | CT-12, R-26: типи локальних джерел (без колектора); базово `[]`; модуль, що додає тип через `selection_add` поля `type`, розширює: `return super()._td_local_types() + ['td_genset']` |

**Примітка (енергетика W2, Q-30).** Типи джерел, яких немає в `td_telemetry` (наприклад `energy_ctl` модуля `td_energy_control`), реєструють свої валідатори **під час імпорту модуля**: `tools/address.py` `PARAMS_VALIDATORS[<тип>]` і `ADDRESS_VALIDATORS[<тип>]` — звичайні словники модуля, `td_telemetry` не змінюється. Офіційний хук розширення (`_td_param_validators`) — окремою дрібною зміною пізніше. Ключі додаються лише поряд із `selection_add` поля `type` (`ondelete={"<тип>": "cascade"}`) і не перезаписують чужі.

### M-03 `td.signal` — сигнал (CT-01, §6.4 каркаса)

```python
class F3dSignal(models.Model):
    _name = "td.signal"
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
| `kind` | Selection `KINDS` | `req`, `default="gauge"`, `string="Вид"`, `tracking=True`; `state` — текстовий стан (`text`), числові коди станів пристроїв моделюються як `gauge` |
| `unit` | Char(32) | `string="Одиниця"` |
| `states` | Json | `string="Допустимі стани"`, список рядків; для `kind='state'` (порожньо = будь-який текст) |
| `equipment_id` | Many2one `maintenance.equipment` | `ondelete="set null"`, `idx`, `string="Обладнання"`, `tracking=True` |
| `equipment_code` | Char | `related="equipment_id.td_code"`, `string="Код обладнання"` |
| `workcenter_id` | Many2one `mrp.workcenter` | `ondelete="set null"`, `string="Робочий центр"` |
| `source_id` | Many2one `td.source` | `ondelete="set null"`, `idx`, `string="Джерело"`, `tracking=True` |
| `source_type` | Selection | `related="source_id.type"` |
| `collector_id` | Many2one `td.collector` | `related="source_id.collector_id"`, `store=True`, `idx` |
| `address` | Json | `string="Адреса в джерелі"`, `default=dict`; схема за `source_id.type` — Додаток A.1 |
| `address_text` | Text | `compute`/`inverse`, `string="Адреса (JSON)"` |
| `period_s` | Integer | `default=10`, `string="Період, с"`; ≥ 1 (для push-протоколів — очікуваний період, для `stale`) |
| `store_period_s` | Integer | `default=lambda self: int(self.env['ir.config_parameter'].sudo().get_param('td.telemetry.default_store_period_s', '300'))`, `string="Зберігати не частіше, с"`; 0 = кожне показання |
| `scale` | Float | `digits=(16,6)`, `default=1.0`, `string="Множник"`, `help="Множник сигналу: ядро колектора один раз множить на нього інженерне значення, яке повернув плагін (масштаб і зсув адреси плагін уже застосував). R-02."` — X-63: ключі адреси (`address.scale`, `offset`, `map`, `agg`) застосовує плагін, `signal.scale` — лише ядро колектора (§8.3.3) або R-22 для `http_push`; плагіни `SignalCfg.scale` не застосовують |
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
| `origin` | Selection | `[('sim_data','Рівень 0 (макет)'),('catalog','Каталог емулятора'),('manual','Вручну'),('module','Дані модуля')]`, `default='manual'`, `string="Походження"` (X-16): `sim_data` — мігровані з рівня 0 (§5.3 крок 2); `catalog` — **лише** рядки каталогу iot_sim Додаток A (C.2 `new=1`, CT-11); `module` — сигнали, які модуль створює з власних даних (не з рядка каталогу), напр. energy/bms/machine_connect/fire_safety; `manual` — створені користувачем. Модулі значення не додають через `selection_add` |
| `module` | Selection `td.source.MODULES` | `default='telemetry'`, `string="Модуль-власник"`, `idx` |
| `derived_from_id` | Many2one `td.signal` | `ondelete="set null"`, `string="Похідний від"` |
| `derive_rule` | Selection | `[('none','—'),('rate_h','Швидкість за годину (Δ/Δt)')]`, `default='none'` (R-08) |
| `sim_mode` | Char(16) | `string="Режим макета"` (A-11) |
| `sim_params` | Json | `string="Параметри макета"` — `{"nominal", "noise", "rate", "limit", "alarm", "threshold", "seed"}` |
| `note` | Text | |
| `reading_count` | Integer | `compute="_compute_reading_count"` (не зберігається): `read_group` за 48 год |
| `meter_equipment_ids` | One2many `maintenance.equipment` `td_meter_signal_id` | `string="ТО за лічильником"` |
| `td_is_manager` | Boolean | `compute` (не зберігається): `self.env.user.has_group('td_factory3d.group_td_manager')` — для `readonly` у формі |
| `states_text`, `alarm_states_text` | Char | `compute`/`inverse`: список `states`/`alarm_states` через кому (пробіли обрізаються, порожні відкидаються) |
| `sim_params_text` | Text | `compute` (readonly): `json.dumps(sim_params, ensure_ascii=False, indent=2)` |

```python
    _f3d_signal_code_uniq = models.Constraint("UNIQUE(code)", "Код сигналу має бути унікальним.")
    _f3d_signal_periods = models.Constraint("CHECK(period_s >= 1 AND store_period_s >= 0 AND min_duration_s >= 0 AND hysteresis >= 0)",
                                            "Період ≥ 1 с, інтервал зберігання ≥ 0, тривалість і гістерезис ≥ 0.")
```

`@api.constrains`:
- `code` — `CODE_RE` → `ValidationError("Код сигналу %s: шлях виду energy/consumers/SAW-1/p_now (малі літери групи, далі сегменти через /).")`;
- `source_id`, `address` — якщо `source_id` і `address` непорожня: `errors = validate_address(source_id.type, address, self.env['td.source']._td_local_types())` → `"Адреса сигналу %s: %s"`; без джерела, з `{}` або на локальному джерелі (R-26) адреса не перевіряється;
- пороги — `alarm_low_on and warn_low_on and alarm_low > warn_low` → `"«Тривога, нижче» має бути ≤ «Увага, нижче»."`; симетрично для `high` (`alarm_high < warn_high` заборонено); `alarm_low_on and alarm_high_on and alarm_low >= alarm_high` → `"«Тривога, нижче» має бути < «Тривога, вище»."`;
- `kind` — `kind='state'` з увімкненими числовими порогами → `"Для стану задайте «Стани-тривоги», а не числові пороги."`; `derive_rule='rate_h'` без `derived_from_id` або `derived_from_id.kind != 'counter'` → `"Похідна «за годину» потребує лічильника-джерела."`;
- `write_enabled` — `True` при `source_id.type == 'bacnet_ip' and source_id.params.get('read_only')` → `"Запис у пожежну панель заборонено (D-07)."`.

Методи (повні сигнатури; алгоритми — у §9):

| Сигнатура | Призначення |
|---|---|
| `@api.model _td_ingest(self, readings: list[dict], src: str = "module", collector=None) -> dict` | CT-10 / API-02: `readings = [{"code", "ts": datetime\|str, "value": float\|None, "text": str\|None, "q": "good"}]`; повертає `{"accepted", "stored", "duplicates", "rejected": [{"i", "code", "reason"}], "changed_codes": [...], "alarms_opened"}`; `ts` — рядок ISO із зоною або `datetime` (naive = UTC); алгоритм R-17 (`tools/ingest.Ingester`); кожне збережене показання отримує `received_at` — час прийому в Odoo, одне значення на виклик: `self.env.context.get("f3d_received_at") or fields.Datetime.now()` (R-17 п. 6, X-83). **Точка розширення** (D-19, X-02): єдиний вхід усіх показань — API-02 і API-05 викликають саме `env['td.signal'].sudo()._td_ingest(readings, src='collector', collector=c)`, модулі (CT-10) — з `src='module'`; `Ingester` напряму ніхто, крім цього методу, не викликає. Перевизначення в модулях (`_inherit = "td.signal"`) зберігає сигнатуру `(self, readings, src="module", collector=None)`, викликає `super()._td_ingest(readings, src=src, collector=collector)` з незміненими аргументами першою дією, що змінює дані (лише читання до виклику допускається), і повертає результат `super()` без змін; власні дії після `super()` — у `self.env.cr.savepoint()`, їхній виняток логується і не відкочує показання (як fire M-15, bms M-13, energy M-15) |
| `_apply_reading(self, ts, value, text, quality) -> dict` | службово з Ingester (у пам'яті, без ORM-write): повертає нові значення полів `last_*`, `status*`, `breach_since` за R-03/R-04 |
| `_open_request(self, value, text, ts) -> maintenance.request` | R-05 |
| `_on_request_closed(self, request)` | R-06 (викликається з M-08) |
| `_td_stale_after(self) -> int` | R-07, X-06: вікно `stale` сигналу в секундах — `max(stale_periods · p, stale_min_s)`, де `p = cov_check_s(period_s) = max(period_s · 10, 300)` для сигналів з ефективним режимом `cov` (джерело `bacnet_ip` без `params.read_only`, `address.mode == 'cov'` або `mode` відсутній і об'єкт за умовчанням `cov` — A.1), інакше `p = period_s`; `cov_check_s` — одна формула у двох пакетах: Odoo `tools/thresholds.cov_check_s(period_s)`, колектор `collector/plugins/bacnet_ip.cov_check_s(period_s)` (§8.8) |
| `_mark_stale(self, reason: str)` | R-07: `status='stale'` (крім `unknown`), `status_since=now`, чаттер «Немає даних: <reason>» (один раз на перехід) |
| `_notify_viewer(self, codes: list[str])` | R-13: якщо `'td.viewer.event' in self.env` → `self.env['td.viewer.event']._notify('td.signal', codes, 'signal')` |
| `@api.model _td_import_sim_catalog(self, codes=None, module=None, source_map=None, defaults=None) -> dict` | CT-11, R-24: `{"created", "updated", "unparsed": [code], "skipped": [code]}`; без моделі `td.sim.signal` — ті самі ключі з нулями й `"state": "skipped"` |
| `@api.model _td_import_sim_rows(self, rows: list[dict], source_map: dict, defaults: dict) -> dict` | ядро CT-11 над рядками з полями iot_sim M-03 (`code`, `name`, `protocol`, `address`, `dtype`, `unit`, `scale`, `nominal`, `thresholds`, `kind`); ключ джерела — Додаток C.3; `_td_import_sim_catalog` читає `td.sim.signal` і викликає його |
| `action_test_address(self)` | валідатор адреси → `display_notification` |
| `action_view_readings(self)` | `act_window` `td.reading` `domain=[('signal_id','=',id)]`, `context={'search_default_last_48h':1}`, `view_mode='graph,list'` |
| `action_open_request(self)` | відкрити `maintenance_request_id` |
| `action_request_write(self)` | відкрити форму нової `td.command` з `default_signal_id` (лише якщо `write_enabled`) |
| `name_get`-подібне `_compute_display_name` | `"%s (%s)" % (name, code)` |
| `write(self, vals)` | зміна `address`/`period_s`/`scale`/`source_id`/`active`/`write_enabled`/`states` → `collector_id.config_etag=False`; зміна порогів → `status` перераховується з `last_value` (R-04, без мін. тривалості); далі `super()` |
| `unlink(self)` | заборонено, якщо є `meter_equipment_ids` (`UserError("Сигнал використовується для ТО за лічильником на %s.")`); показання видаляються каскадно |

### M-04 `td.reading` — показання (CT-01)

```python
class F3dReading(models.Model):
    _name = "td.reading"
    _description = "Телеметрія: показання"
    _order = "ts desc, id desc"
    _log_access = False
    _rec_name = "ts"
```

| Поле | Тип | Параметри |
|---|---|---|
| `signal_id` | Many2one `td.signal` | `req`, `ondelete="cascade"`, `idx` |
| `equipment_id` | Many2one `maintenance.equipment` | `related="signal_id.equipment_id"`, `store=True`, `idx` |
| `ts` | Datetime | `req`, `string="Час"` |
| `value` | Float | `string="Значення"` (для `state` — **0-based** індекс у `states`, −1 якщо текст поза списком; для `event` — 1); не плутати з 1-based номером стану BACnet MSV (R-23, X-66) |
| `text` | Char(64) | `string="Текст"` (стан/подія) |
| `quality` | Selection | `[('good','Добра'),('uncertain','Непевна'),('bad','Погана')]`, `default='good'`, `req` |
| `src` | Selection | `[('collector','Колектор'),('sim_data','Рівень 0'),('module','Модуль'),('manual','Вручну')]`, `default='collector'`, `req` |
| `received_at` | Datetime | `req`, `default=fields.Datetime.now`, `string="Отримано"`, `help="Час прийому показання в Odoo"` — «час прийому» (X-83): ставить `_td_ingest` (R-17 п. 6), не індексується |
| `unit` | Char | `related="signal_id.unit"` |
| `code` | Char | `related="signal_id.code"` |

```python
    _f3d_reading_uniq = models.Constraint("UNIQUE(signal_id, ts)", "Показання для цього сигналу і часу вже є.")
```

«Час прийому» (X-83) — `received_at`: `fields.Datetime.now()` в Odoo в момент `_td_ingest` (одне значення на виклик, R-17 п. 6); `ts` — час пристрою або джерела (`event.ts` колектора, `capture_timestamp` камери, `ts` пакета API-02), він лише для відображення й дедуплікації (`UNIQUE(signal_id, ts)`); вікна `ts_future`/`ts_too_old` (API-02, R-22) рахуються від часу прийому.

`init(self)`: `CREATE INDEX IF NOT EXISTS td_reading_ts_idx ON td_reading (ts)` (ротація) — через
`tools.sql.create_index`. Індекс `(signal_id, ts)` створює унікальне обмеження. Створення — лише через
`Ingester` (SQL `INSERT … ON CONFLICT (signal_id, ts) DO NOTHING`) або ORM у тестах/хуку; у формах
`create="false"`. `write` заборонено (`UserError("Показання не редагуються.")`), крім `quality`
адміністратором.

### M-05 `td.reading.hour` — годинний агрегат (CT-01)

`_name = "td.reading.hour"`, `_description = "Телеметрія: годинний агрегат"`, `_order = "hour desc"`,
`_log_access = False`.

| Поле | Тип | Параметри |
|---|---|---|
| `signal_id` | Many2one `td.signal` | `req`, `ondelete="cascade"`, `idx` |
| `equipment_id` | Many2one | `related="signal_id.equipment_id"`, `store=True`, `idx` |
| `hour` | Datetime | `req`, `string="Година (UTC)"` — початок години |
| `v_min`, `v_avg`, `v_max`, `v_sum` | Float | |
| `v_count` | Integer | |
| `v_first`, `v_last` | Float | перше/останнє за `ts` |
| `delta` | Float | для `kind='counter'`: `v_last(h) − v_prev`, де `v_prev` — `v_last` найближчого попереднього агрегату цього сигналу (`hour < h`; за безперервного ряду — година `h − 1`); для першої години ряду (попереднього агрегату немає) — `v_last(h) − v_first(h)`; якщо `v_last(h) < v_prev` (скидання/ролловер, R-08) — `v_last(h) − v_first(h)`; інакше (не лічильник) 0. X-07, R-09, A-25 |

`_f3d_reading_hour_uniq = models.Constraint("UNIQUE(signal_id, hour)", "Агрегат за цю годину вже є.")`.
Заповнюється кроном R-09 через `INSERT … ON CONFLICT DO UPDATE`; у формах `create="false"`, `edit="false"`.

### M-06 `td.command` — команда на запис у пристрій (A-08, FR-21)

`_name = "td.command"`, `_description = "Телеметрія: команда на пристрій"`, `_order = "requested_at desc"`,
`_inherit = ["mail.thread"]`.

| Поле | Тип | Параметри |
|---|---|---|
| `signal_id` | Many2one `td.signal` | `req`, `ondelete="cascade"`, `idx`, `domain="[('write_enabled','=',True)]"` |
| `source_id` | Many2one `td.source` | `related="signal_id.source_id"`, `store=True`, `idx` |
| `collector_id` | Many2one `td.collector` | `related="signal_id.collector_id"`, `store=True`, `idx` |
| `signal_kind` | Selection | `related="signal_id.kind"` (для `invisible` у формі V-17) |
| `value` | Float | `string="Значення"` |
| `text` | Char(64) | `string="Текст/стан"` (для `kind='state'`) |
| `payload` | Json | `string="Дані команди"`, `copy=False`; CR-01 (X-03): `None` (звичайна команда — `value`/`text`, плагін `write()`) або об'єкт JSON ≤ 64 КБ (`len(json.dumps(payload, ensure_ascii=False).encode()) ≤ 65 536`) — команда-виклик, колектор передає його `call(signal, payload)` плагіна (§8.3.2, §8.4); `value`/`text` такої команди плагін не використовує. Зміст задає модуль-власник плагіна (machine_connect CM-08) |
| `payload_text` | Text | `compute`/`inverse` (`ace`, `mode: json`), `string="Дані команди (JSON)"`; порожньо → `payload=None` |
| `result_data` | Json | `string="Дані результату"`, `readonly=True`, `copy=False` — `data` з API-07 (об'єкт, який повернув `call()`; для `write()` — порожньо) |
| `state` | Selection | `[('queued','У черзі'),('sent','Передано колектору'),('done','Виконано'),('failed','Помилка'),('expired','Прострочено'),('cancelled','Скасовано')]`, `default='queued'`, `idx`, `tracking=True` |
| `requested_by` | Many2one `res.users` | `default=lambda self: self.env.user`, `readonly=True` |
| `requested_at` | Datetime | `default=fields.Datetime.now`, `readonly=True` |
| `expires_at` | Datetime | `default=lambda self: now + 10 хв`, `string="Дійсна до"` |
| `sent_at`, `done_at` | Datetime | `readonly=True` |
| `result` | Char(256) | `readonly=True` |
| `error` | Char(512) | `readonly=True` |
| `origin` | Char(32) | `string="Ініціатор"` (`manual`, ключ модуля) |
| `note` | Char(256) | |

`@api.constrains("payload")`: не `None` і не `dict` або > 64 КБ → `ValidationError("Дані команди мають бути об'єктом
JSON ≤ 64 КБ.")`.

Методи: `create(vals_list)` — для кожного: `sig = signal_id`; перевірки R-18 п. 1 (усі чотири прапори крім
колекторного; `AccessError`/`UserError` з текстами R-18); перевірка групи `group_td_manager` виконується лише коли
`not self.env.su` — під `sudo()` і `with_user(SUPERUSER_ID)` (модулі: yard A-20, bms R-25, machine_connect M-20) її
пропущено, решта запобіжників R-18 п. 1 діє (X-04, як base R-04); `requested_by` — `self.env.user` (під `sudo()` —
той самий користувач), модуль може передати явно; `action_cancel()` — лише `queued` → `cancelled`;
`_cron_expire()` — `queued/sent` з `expires_at < now` → `expired`. Для `kind='state'` з `text` поле `value`
обчислюється як **0-based** індекс `text` у `states` (−1 поза списком; та сама база, що `td.reading.value`, M-04) — лише
довідково (список, графік); плагіни для запису стану його **не** використовують: Modbus і BACnet беруть ключ
зворотного `address.map` (`"VEL"` → 2), BACnet MSV/MSI без `map` — 1-based індекс у `states` (R-23, §8.8, X-66).

### M-13 `td.push.event` — журнал подій http_push (FR-22)

`_name = "td.push.event"`, `_description = "Телеметрія: подія HTTP push"`, `_order = "ts desc"`,
`_log_access = False`.

| Поле | Тип | Параметри |
|---|---|---|
| `event_id` | Char(64) | `req`, `idx` — унікальний ідентифікатор від колектора |
| `route` | Char(32) | `req`, `idx` |
| `ts` | Datetime | `req`, `idx` |
| `collector_id` | Many2one `td.collector` | `ondelete="set null"` |
| `remote` | Char(64) | IP/хост відправника |
| `payload` | Json | тіло події |
| `handled_by` | Char(256) | імена моделей-обробників через кому |
| `error` | Char(512) | |
| `signal_count` | Integer | скільки показань породжено |

`_f3d_push_event_uniq = models.Constraint("UNIQUE(event_id)", "Подія з таким ідентифікатором уже є.")`.
Ротація — крон R-10 (`keep_days` ті самі). Метод `@api.model _td_receive(self, events: list[dict], collector) -> dict` —
R-22 для пакета API-05 (контролер лише автентифікує й розбирає JSON); повертає тіло відповіді API-05.

### M-07 `maintenance.equipment` — розширення: сигнали, ТО за лічильником (CT-06)

```python
class MaintenanceEquipment(models.Model):
    _inherit = "maintenance.equipment"
```

| Поле | Тип | Параметри |
|---|---|---|
| `td_signal_ids` | One2many `td.signal` `equipment_id` | `string="Сигнали"` |
| `td_signal_count` | Integer | `compute="_compute_f3d_signal_counts"` — активні сигнали |
| `td_alarm_count` | Integer | `compute` — `status='alarm'` |
| `td_stale_count` | Integer | `compute` — `status='stale'` |
| `td_meter_signal_id` | Many2one `td.signal` | `string="Лічильник для ТО"`, `ondelete="set null"`, `domain="[('kind','=','counter'), '\|', ('equipment_id','=',id), ('equipment_id','=',False)]"`, `tracking=True` |
| `td_meter_unit` | Char | `related="td_meter_signal_id.unit"` |
| `td_meter_interval` | Float | `digits=(12,1)`, `string="Інтервал ТО"`, `help="У одиницях лічильника: мотогодини, цикли, м³"` |
| `td_meter_last_value` | Float | `digits=(12,1)`, `string="Останнє ТО при показнику"` |
| `td_meter_last_date` | Date | `string="Дата останнього ТО"` |
| `td_meter_lead_pct` | Float | `default=lambda self: float(param('td.telemetry.meter_lead_pct', '5'))`, `string="Планувати за, % інтервалу"` |
| `td_meter_next_value` | Float | `compute="_compute_f3d_meter"`, `store=True`: `last_value + interval` (0, якщо не задано) |
| `td_meter_current` | Float | `compute` (не зберігається): `td_meter_signal_id.last_value` |
| `td_meter_remaining` | Float | `compute` (не зберігається): `next_value − current` |
| `td_meter_request_id` | Many2one `maintenance.request` | `string="Планова заявка"`, `ondelete="set null"`, `readonly=True` |

`@api.constrains("td_meter_signal_id", "td_meter_interval")`: сигнал без інтервалу або інтервал ≤ 0 →
`ValidationError("Задайте інтервал ТО за лічильником (> 0).")`; сигнал іншого обладнання (не порожнього і не
цього) → `"Лічильник належить іншому обладнанню."`.

Методи: `_td_meter_check(self)` — R-11 (викликається з Ingester для обладнання, чий лічильник оновився);
`action_f3d_view_signals(self)` — `act_window` `td.signal` `domain=[('equipment_id','=',id)]`,
`context={'default_equipment_id': id, 'search_default_active': 1}`; `action_f3d_view_readings(self)` —
`td.reading` графік за 48 год, `domain=[('equipment_id','=',id)]`.

### M-08 `maintenance.request` — розширення (§6.8 каркаса, CT-05, CT-06)

```python
class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"
```

| Поле | Тип | Параметри |
|---|---|---|
| `td_signal_id` | Many2one `td.signal` | `string="Сигнал"`, `ondelete="set null"`, `idx` |
| `td_equipment_code` | Char | `related="equipment_id.td_code"`, `store=True`, `string="Код обладнання"` |
| `td_origin` | Selection | `[('threshold','Поріг сигналу'),('meter','ТО за лічильником'),('stale','Немає даних'),('manual','Вручну')]`, `string="Джерело заявки"` |
| `td_value` | Float | `string="Показник при створенні"` |
| `td_threshold` | Float | `string="Поріг"` |
| `td_signal_status` | Selection | `related="td_signal_id.status"` |

`write(self, vals)`: `super()`; якщо `'stage_id' in vals`: для заявок, де `stage_id.done` стало `True`
(порівняння зі станом до запису) — `td_signal_id._on_request_closed(self)` (R-06) і, якщо
`td_origin == 'meter'`, `equipment_id._td_meter_closed(self)` (R-11 п. 5). Повторне відкриття
(`done → not done`) → сигнал знову отримує `maintenance_request_id = self` (R-06 п. 4).
`unlink(self)`: перед `super()` — сигнали з `maintenance_request_id in self` → `maintenance_request_id=False`,
`request_closed_at=now` (R-06).
Для `td_origin='threshold'` стандартна поведінка `maintenance_type='corrective'`; для `meter` —
`'preventive'`; `recurring_maintenance=False` завжди (повторність веде лічильник, не календар).

### M-09 `res.config.settings` — розширення

| Поле | Тип | `config_parameter` |
|---|---|---|
| `td_telemetry_read_enabled` | Boolean | `td.telemetry.read_enabled` |
| `td_telemetry_write_enabled` | Boolean | `td.telemetry.write_enabled` |
| `td_telemetry_keep_days` | Integer | `td.telemetry.keep_days` |
| `td_telemetry_keep_hours_days` | Integer | `td.telemetry.keep_hours_days` |
| `td_telemetry_default_store_period_s` | Integer | `td.telemetry.default_store_period_s` |
| `td_telemetry_stale_periods` | Integer | `td.telemetry.stale_periods` |
| `td_telemetry_stale_min_s` | Integer | `td.telemetry.stale_min_s` |
| `td_telemetry_bus_min_interval_s` | Integer | `td.telemetry.bus_min_interval_s` |
| `td_telemetry_realarm_cooldown_s` | Integer | `td.telemetry.realarm_cooldown_s` |
| `td_telemetry_push_max_readings` | Integer | `td.telemetry.push_max_readings` |
| `td_telemetry_push_rate_per_min` | Integer | `td.telemetry.push_rate_per_min` |
| `td_telemetry_meter_lead_pct` | Float | `td.telemetry.meter_lead_pct` |
| `td_telemetry_default_team_id` | Many2one `maintenance.team` | `td.telemetry.default_team_id` (id як рядок; `get_values` читає `int(...)`) |
| `td_telemetry_drop_level0` | Boolean | `td.telemetry.drop_level0` |
| `td_telemetry_level0_state` | Char | `compute`: `json.loads(param('level0_migrated','{}')).get('state','—')` (readonly) |
| `td_telemetry_collector_count` | Integer | `compute`: `search_count` активних колекторів |

Булеві параметри читаються `get_param(key, 'False') in ('True','true','1')` (як у base §5.1). Кнопки:
«Колектори» (`action_td_collector`), «Повторити міграцію рівня 0» (`action_td_run_migration`, лише
`group_td_admin`).

### M-10 `td.viewer.provider.telemetry` — провайдер переглядача (CT-07, міст-модуль A-20)

```python
class F3dViewerProviderTelemetry(models.AbstractModel):
    _name = "td.viewer.provider.telemetry"
    _inherit = "td.viewer.provider"
    _description = "3D: значення сигналів телеметрії"
    _td_sequence = 95
    _td_sections = ()
    _td_group = "td_factory3d.group_td_user"
```

- `_td_viewer_collect(self, payload, ctx)`: R-12 над усіма `td.signal` з `active=True`,
  `viewer_visible=True`, `status != 'unknown'` (поля `code`, `last_value`, `last_text`, `unit`, `kind`,
  `status`, `last_ts`); пише `meta.iot`.
- `_td_viewer_delta(self, patch, ctx)`: `codes = ctx['changes'].get('td.signal', set())`; якщо порожньо —
  нічого; інакше `patch['signals'] = [{"path": code, "value": <R-12 значення>} …]` для сигналів із `codes`
  (видимих), `patch.setdefault('meta', {})['iot'] = <R-12 meta.iot>`.
- `_td_viewer_bus_models(self)` → `['td.signal']`.

Провайдер M-01h viewer (над `x_f3d_signal`) після міграції не знаходить активних `x_`-записів
(`x_active=False`, §5.3 крок 6) — конфлікту немає; якщо міграцію не виконано (`partial`), обидва пишуть ті
самі шляхи, останнім — цей (95 > 90: порядок каркаса §6.7 — machine_connect 75, вбудований `signals` 90, telemetry 95; X-86).

### M-11 `td.push.handler` — хук обробника подій http_push (CT-08)

```python
class F3dPushHandler(models.AbstractModel):
    _name = "td.push.handler"
    _description = "Телеметрія: обробник подій HTTP push"
    _td_push_routes = ()                      # напр. ("lpr",)

    def _td_handle_push(self, route: str, event: dict) -> None:
        """event = {"event_id", "route", "ts": datetime (UTC), "remote", "headers": {...}, "payload": {...}}"""
```

Реєстр обробників — скануванням `self.env.registry.descendants(['td.push.handler'], '_inherit')` мінус
абстрактна база (як viewer A-05); порядок — за `_name`. Реалізація — `@api.model _td_handler_models(self, route: str)
-> list[str]` (імена моделей, у яких `route in _td_push_routes`; тести її підміняють). Виняток в обробнику логується
(`logger.exception`) і записується в `td.push.event.error`, інші обробники виконуються, транзакція не
відкочується (обробник працює в `savepoint`).

### M-12 `td.collector.token.wizard` — показ токена (Transient)

| Поле | Тип | Параметри |
|---|---|---|
| `collector_id` | Many2one `td.collector` | `req`, `readonly=True` |
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
| V-01 | `view_td_collector_list` | list `td.collector` | `code`, `name`, `state` (badge), `last_seen`, `version`, `source_count`, `signal_count`, `buffer_rows` (optional hide), `token_hint` (groups admin, optional hide); `decoration-success="state == 'online'"`, `decoration-danger="state == 'offline'"` |
| V-02 | `view_td_collector_form` | form | `<header>`: кнопки `action_generate_token` («Згенерувати токен», `btn-primary`, groups admin), `action_revoke_token` («Відкликати токен», groups admin, `invisible="not token_hash"`), статусбар `state`. Статбокс: `action_view_sources` (`source_count`, «Джерела»), `signal_count` («Сигнали», без дії). Заголовок: `name`; група «Ідентифікація»: `code`, `active` (toggle), `token_hint` (groups admin), `token_set_at`, `version`, `last_seen`, `last_push_at`, `last_ip`; група «Періоди»: `status_interval_s`, `push_interval_s`, `push_max`, `config_poll_s`; група «Стан сервісу» (readonly): `uptime_s`, `buffer_rows`, `buffer_dropped`, `config_etag`; вкладка «Плагіни» (`plugins` через `widget="json"` readonly), «Джерела» (`source_ids` readonly list: `code`, `name`, `type`, `state`, `signal_count`), «Примітка» (`note`); чаттер |
| V-03 | `view_td_collector_token_wizard_form` | form `td.collector.token.wizard` | `<div class="alert alert-warning">Токен показується один раз. Збережіть його в .env колектора.</div>`, `token` (widget `CopyClipboardChar`), `env_line` (widget `CopyClipboardText`), footer: «Закрити» (`special="cancel"`) |
| V-04 | `view_td_source_list` | list `td.source` | `code`, `name`, `type`, `collector_id`, `state` (badge), `read_enabled` (toggle, groups manager), `write_enabled` (toggle, groups manager), `signal_count`, `alarm_count`, `stale_count`, `last_ok`, `last_error` (optional hide), `module` (optional hide); декорації за `state` |
| V-05 | `view_td_source_form` | form | `<header>`: `action_test_params` («Перевірити параметри»), `action_view_signals` («Сигнали»), статусбар `state`. Статбокс: `signal_count`, `alarm_count` («Тривог», `decoration-danger`), `stale_count`. `name`; група «Джерело»: `code`, `type`, `collector_id` (`required="not is_local"`), `equipment_id`, `module`, `active`; група «Прапори»: `read_enabled`, `write_enabled` (`invisible="type == 'http_push'"`), `period_s_default`; група «Стан» (readonly): `last_ok`, `last_error`, `error_count`; вкладки: «Параметри» (`params_text` ace; під ним `<div class="text-muted">` з прикладом для типу — статичний текст у XML на кожен тип через `invisible="type != 'modbus_tcp'"` тощо, Додаток A.2), «Сигнали» (`signal_ids` list editable=bottom для менеджера: `code`, `name`, `kind`, `unit`, `period_s`, `status`, `last_value`, `last_ts`), «Статистика» (`stats` json readonly), «Примітка»; чаттер |
| V-06 | `view_td_source_kanban` | kanban (дашборд «Огляд») | `default_group_by="state"`, картка: `name`, `code`, `type`, `collector_id.code`, `signal_count`, кольорова мітка `alarm_count > 0` (червона), `stale_count > 0` (сіра), `last_ok`; клік — форма; `quick_create="false"` |
| V-07 | `view_td_source_search` | search | поля `name`, `code`, `collector_id`, `equipment_id`; фільтри: «Онлайн» (`state=online`), «Офлайн/помилка» (`state in (offline,error)`), «З тривогами» (`alarm_count > 0` — через `signal_ids.status = alarm`), «Вимкнені» (`read_enabled=False`), «Архівні»; group by `type`, `collector_id`, `module`, `state` |
| V-08 | `view_td_signal_list` | list `td.signal` | `default_order="sequence, code"`; `equipment_id`, `name`, `quantity` (optional hide), `last_value`, `unit`, `last_text` (optional hide), `status` (badge), `last_ts`, `maintenance_request_id` (optional show), `source_id` (optional show), `code` (optional hide), `kind` (optional hide), `module` (optional hide), `period_s` (optional hide), `origin` (optional hide), `active` (optional hide); декорації; multi-edit для менеджера |
| V-09 | `view_td_signal_form` | form | `<header>`: `action_view_readings` («Показання»), `action_test_address` («Перевірити адресу»), `action_open_request` («Заявка», `invisible="not maintenance_request_id"`), `action_request_write` («Записати в пристрій», `invisible="not write_enabled"`, groups manager), статусбар `status` (`statusbar_visible="ok,warn,alarm,stale"`). Статбокс: `reading_count` («Показань за 2 доби»). `name` (title); група «Зараз» (readonly): `last_value`, `unit`, `last_text`, `last_ts`, `last_quality`, `status_since`, `maintenance_request_id`; група «Звідки»: `code`, `equipment_id`, `workcenter_id`, `source_id`, `source_type` (readonly), `collector_id` (readonly), `kind`, `quantity`, `states_text` (список через кому), `active`, `viewer_visible`, `module`, `origin` (readonly), `sequence`; група «Опитування»: `period_s`, `store_period_s`, `scale`, `decimals`, `nominal`, `write_enabled`; група «Пороги»: рядками `warn_low_on` + `warn_low` (`invisible="not warn_low_on"` на числі — обидва в одному `<div class="o_row">`), так само `warn_high`, `alarm_low`, `alarm_high`; `hysteresis`, `min_duration_s`, `alarm_states_text` (Char compute/inverse, через кому; `invisible="kind != 'state'"`), `alarm_title`, `alarm_priority`, `create_request`; вкладки: «Адреса» (`address_text` ace + статична підказка за `source_type`), «Похідна» (`derived_from_id`, `derive_rule`), «Макет» (`sim_mode`, `sim_params_text` readonly), «ТО за лічильником» (`meter_equipment_ids` readonly: `name`, `td_meter_interval`, `td_meter_next_value`), «Примітка»; чаттер. Поля порогів/адреси/джерела — `readonly="not td_is_manager"` (поле `td_is_manager` — M-03) |
| V-10 | `view_td_signal_graph` | graph `td.signal` | `type="bar"`, `last_value` measure, рядок `equipment_id` — для швидкого огляду «що зараз» |
| V-11 | `view_td_signal_pivot` | pivot | рядки `equipment_id`, стовпці `status`, міра `__count` |
| V-12 | `view_td_signal_search` | search | поля `name`, `code`, `equipment_id`, `source_id`; фільтри «Тривога» (`status=alarm`), «Увага», «Немає даних» (`stale`), «Без джерела» (`source_id=False`), «Увімкнені» (`active=True`, default), «Мій модуль» відсутній; group by `equipment_id`, `source_id`, `module`, `kind`, `status` |
| V-13 | `view_td_reading_graph` | graph `td.reading` | `type="line"`, `<field name="ts" interval="hour"/>`, `<field name="signal_id"/>`, `<field name="value" type="measure"/>`; `stacked="0"` (як мок `view_reading_graph`) |
| V-14 | `view_td_reading_list` | list | `create="false"`, `edit="false"`, `default_order="ts desc"`: `ts`, `equipment_id`, `signal_id`, `value`, `text`, `unit`, `quality` (optional hide), `src` (optional hide), `received_at` (optional hide; X-83) |
| V-15 | `view_td_reading_search` | search | поля `signal_id`, `equipment_id`, `code`; фільтри «Останні 2 доби» (`last_48h`: `ts >= now − 48h`, default через контекст дії), «Сьогодні», «7 днів», «Непевні/погані» (`quality != good`); group by `signal_id`, `equipment_id`, `ts:day` |
| V-16 | `view_td_reading_hour_pivot` / `_graph` / `_list` | `td.reading.hour` | pivot: рядки `signal_id`, стовпці `hour:day`, міри `v_avg`, `v_min`, `v_max`, `delta`; graph line `hour`/`v_avg`; list readonly |
| V-17 | `view_td_command_list` / `_form` | `td.command` | list: `requested_at`, `signal_id`, `value`, `text`, `state` (badge), `requested_by`, `sent_at`, `done_at`, `error`; form: `signal_id`, `value`, `text` (`invisible="signal_kind != 'state'"` — related `signal_kind`), `payload_text` (`widget="ace"` `mode: json`, підказка «Лише для команд-викликів модулів; порожньо — звичайний запис значення»), `expires_at`, `note`, група readonly результату (`result`, `error`, `result_data` через `widget="json"`); кнопка `action_cancel` (`invisible="state != 'queued'"`); `<div class="alert alert-info">` «Команда виконається, лише якщо запис дозволено на модулі, джерелі, сигналі й у колекторі» |
| V-18 | `view_maintenance_equipment_form_td_signals` | form inherit `maintenance.hr_equipment_view_form` | `//div[@name='button_box']` inside: статкнопки `action_f3d_view_signals` (`td_signal_count`, «Сигнали», `fa-rss`), `td_alarm_count` («Тривоги», `fa-bell`, `invisible="not td_alarm_count"`, клас `text-danger`); `//notebook` inside: `<page name="f3d_signals" string="Сигнали" invisible="not td_signal_count and not td_meter_signal_id">`: список `td_signal_ids` readonly (`quantity`, `name`, `last_value`, `unit`, `last_text`, `status` badge, `last_ts`, `maintenance_request_id`; `decoration-danger="status == 'alarm'"`), кнопка `action_f3d_view_readings` («Графік за 2 доби»); група «ТО за лічильником»: `td_meter_signal_id`, `td_meter_unit`, `td_meter_interval`, `td_meter_last_value`, `td_meter_last_date`, `td_meter_lead_pct`, `td_meter_current` (readonly), `td_meter_next_value` (readonly), `td_meter_remaining` (readonly, `decoration-danger="td_meter_remaining <= 0"`), `td_meter_request_id` (readonly). Це заміна `td_iot_sim.view_equipment_form_signals` (та ж назва сторінки `f3d_signals`; мок-представлення деактивується хуком) |
| V-19 | `view_maintenance_equipment_list_td_signals` / `_search` | inherit `maintenance.hr_equipment_view_tree` / `hr_equipment_view_search` | list: `td_alarm_count` (optional show), `td_signal_count` (optional hide); search: фільтри «З тривогами» (`td_signal_ids.status = alarm`), «Є сигнали» (`td_signal_ids != False`), «ТО за лічильником» (`td_meter_signal_id != False`) |
| V-20 | `view_maintenance_request_form_td` / `_list_f3d` / `_search_f3d` | inherit `maintenance.hr_equipment_request_view_form` / `hr_equipment_request_view_tree` / `hr_equipment_request_view_search` | form: після `equipment_id` група «Телеметрія» (`invisible="not td_signal_id"`): `td_signal_id`, `td_signal_status`, `td_origin`, `td_value`, `td_threshold`; list: `td_origin` (optional hide), `td_equipment_code` (optional hide); search: фільтр «З телеметрії» (`td_signal_id != False`), group by `td_origin` |
| V-21 | `res_config_settings_view_form_td_telemetry` | inherit `base.res_config_settings_view_form` | блок `app_settings_block` `data-string="Завод 3D"` (спільний блок base, якщо є — `xpath //block[@name='td_base_settings']`, інакше власний `name="td_telemetry_settings"`): «Телеметрія»: `td_telemetry_read_enabled` («Приймати показання»), `td_telemetry_write_enabled` («Дозволяти команди на пристрої»), `td_telemetry_collector_count` + кнопка «Колектори»; «Зберігання»: `keep_days`, `keep_hours_days`, `default_store_period_s`; «Пороги й заявки»: `stale_periods`, `stale_min_s`, `realarm_cooldown_s`, `meter_lead_pct`, `default_team_id`; «API»: `push_max_readings`, `push_rate_per_min`, `bus_min_interval_s`; «Рівень 0»: `td_telemetry_level0_state` (readonly), `td_telemetry_drop_level0`, кнопка «Повторити міграцію рівня 0» (groups admin) |
| V-22 | меню та дії (`views/menus.xml`) | `ir.ui.menu`, `ir.actions.act_window` | таблиця нижче |
| V-23 | `view_td_push_event_list` / `_form` | `td.push.event` | list readonly: `ts`, `route`, `remote`, `handled_by`, `signal_count`, `error`; form readonly з `payload` (json) |

Меню (розділ «Телеметрія» — під `td_factory3d.menu_td_data` «Дані», sequence 20; пункт налаштувань — під `menu_td_config`, sequence 30, CB-09):

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_td_telemetry` | Телеметрія | `td_factory3d.menu_td_data` | 20 | `group_td_user` | — |
| `menu_td_telemetry_overview` | Огляд | `menu_td_telemetry` | 10 | `group_td_user` | `action_td_source_overview` (`td.source`, kanban,list,form; `context={'search_default_group_state': 1}`) |
| `menu_td_telemetry_signal` | Сигнали | `menu_td_telemetry` | 20 | `group_td_user` | `action_td_signal` (list,form,graph,pivot; `context={'search_default_active': 1, 'search_default_group_equipment': 1}`) |
| `menu_td_telemetry_reading` | Показання | `menu_td_telemetry` | 30 | `group_td_user` | `action_td_reading` (graph,list; `context={'search_default_last_48h': 1}`; `domain=[]`) |
| `menu_td_telemetry_reading_hour` | Годинні агрегати | `menu_td_telemetry` | 35 | `group_td_user` | `action_td_reading_hour` (pivot,graph,list) |
| `menu_td_telemetry_source` | Джерела | `menu_td_telemetry` | 40 | `group_td_manager` | `action_td_source` (list,form,kanban) |
| `menu_td_telemetry_collector` | Колектори | `menu_td_telemetry` | 50 | `group_td_admin` | `action_td_collector` (list,form) |
| `menu_td_telemetry_command` | Команди | `menu_td_telemetry` | 60 | `group_td_manager` | `action_td_command` (list,form) |
| `menu_td_telemetry_push_event` | Події HTTP push | `menu_td_telemetry` | 70 | `group_td_manager` | `action_td_push_event` (list,form) |
| `menu_td_telemetry_config` | Налаштування телеметрії | `td_factory3d.menu_td_config` | 30 | `group_td_admin` | `action_td_telemetry_settings` (`res.config.settings`, `context={'module': 'td_telemetry'}`) |

Додатково для механіка: `menu_td_telemetry_maint` «Телеметрія» під `maintenance.menu_maintenance_title`
(`sequence=6`, групи `group_td_user`, дія `action_td_signal` з `context={'search_default_alarm': 1}`) —
на місце мок-меню «Імітація IoT» (`sequence=5`, деактивується хуком).

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_collector_user,td.collector user,model_td_collector,td_factory3d.group_td_user,1,0,0,0
access_td_collector_admin,td.collector admin,model_td_collector,td_factory3d.group_td_admin,1,1,1,1
access_td_source_user,td.source user,model_td_source,td_factory3d.group_td_user,1,0,0,0
access_td_source_manager,td.source manager,model_td_source,td_factory3d.group_td_manager,1,1,1,1
access_td_signal_user,td.signal user,model_td_signal,td_factory3d.group_td_user,1,0,0,0
access_td_signal_manager,td.signal manager,model_td_signal,td_factory3d.group_td_manager,1,1,1,1
access_td_reading_user,td.reading user,model_td_reading,td_factory3d.group_td_user,1,0,0,0
access_td_reading_manager,td.reading manager,model_td_reading,td_factory3d.group_td_manager,1,0,1,0
access_td_reading_admin,td.reading admin,model_td_reading,td_factory3d.group_td_admin,1,1,1,1
access_td_reading_hour_user,td.reading.hour user,model_td_reading_hour,td_factory3d.group_td_user,1,0,0,0
access_td_reading_hour_admin,td.reading.hour admin,model_td_reading_hour,td_factory3d.group_td_admin,1,1,1,1
access_td_command_user,td.command user,model_td_command,td_factory3d.group_td_user,1,0,0,0
access_td_command_manager,td.command manager,model_td_command,td_factory3d.group_td_manager,1,1,1,0
access_td_command_admin,td.command admin,model_td_command,td_factory3d.group_td_admin,1,1,1,1
access_td_push_event_user,td.push.event user,model_td_push_event,td_factory3d.group_td_user,1,0,0,0
access_td_push_event_admin,td.push.event admin,model_td_push_event,td_factory3d.group_td_admin,1,1,1,1
access_td_collector_token_wizard_admin,td.collector.token.wizard admin,model_td_collector_token_wizard,td_factory3d.group_td_admin,1,1,1,1
```

Абстрактні `td.push.handler`, `td.viewer.provider.telemetry` рядків не потребують. Контролери
працюють `sudo()` після перевірки токена. Поля `td_*` на `maintenance.equipment`/`maintenance.request` —
за правами цих моделей (`maintenance.group_equipment_manager` редагує ТО за лічильником; поля
`td_signal_id`, `td_origin`, `td_value`, `td_threshold` на заявці — `readonly` у формі, пише модуль).

### 4.2 Групи

Нових груп немає — CB-10 (`group_td_user/manager/admin`). У `security/security.xml` — лише правила.

### 4.3 Record rules (`security/security.xml`)

| XML-id | Модель | Домен | Групи |
|---|---|---|---|
| `td_reading_rule_all` | `td.reading` | `[(1,'=',1)]` | глобальне (без компанії: показання не мультикомпанійні) |
| `td_command_rule_own_or_manager` | `td.command` | `['\|', ('requested_by','=',user.id), ('signal_id.module','!=',False)]` — фактично всім; правило-заготовка для майбутнього обмеження за модулем | `group_td_user` |

Компанії: моделі модуля без `company_id` (завод один; CB-10 base теж без компанії для паспортів).

### 4.4 Захист полів

- `td.collector.token_hash/token_hint` — `groups=group_td_admin` (невидимі й не читаються іншими навіть
  через `read`); `_authenticate` — `sudo()`.
- `td.signal.write`: зміна `write_enabled`, `source_id`, `address`, порогів — лише `group_td_manager`
  (через ACL — user має лише читання); `status`, `last_*`, `maintenance_request_id` — `readonly=True` у
  полі, пише лише код (`sudo` в Ingester).
- `td.command.create` — `group_td_manager` + R-18 п. 1; під `env.su` (`sudo()`, `with_user(SUPERUSER_ID)`) перевірка
  групи пропускається (як base R-04), а прапори модуля, джерела, сигналу, `read_only` і локальний тип перевіряються
  завжди (X-04, AC-96); модулі створюють команди лише після власних перевірок ролі (yard R-15/A-20, bms R-25,
  machine_connect M-20); `unlink` — лише admin.

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)

| key | value | XML-id | Примітка |
|---|---|---|---|
| `td.telemetry.read_enabled` | `True` | `param_read_enabled` | хук перезаписує за CB-10: `environment == 'test'` → `True`, інакше `False` |
| `td.telemetry.write_enabled` | `False` | `param_write_enabled` | |
| `td.telemetry.keep_days` | `30` | `param_keep_days` | |
| `td.telemetry.keep_hours_days` | `400` | `param_keep_hours_days` | |
| `td.telemetry.default_store_period_s` | `300` | `param_default_store_period` | |
| `td.telemetry.stale_periods` | `3` | `param_stale_periods` | |
| `td.telemetry.stale_min_s` | `60` | `param_stale_min_s` | |
| `td.telemetry.bus_min_interval_s` | `10` | `param_bus_min_interval` | |
| `td.telemetry.realarm_cooldown_s` | `3600` | `param_realarm_cooldown` | |
| `td.telemetry.push_max_readings` | `2000` | `param_push_max` | |
| `td.telemetry.push_rate_per_min` | `60` | `param_push_rate` | |
| `td.telemetry.meter_lead_pct` | `5` | `param_meter_lead_pct` | |
| `td.telemetry.default_team_id` | `` (порожньо) | `param_default_team` | хук: id команди «Служба головного механіка», якщо є, інакше перша `maintenance.team` |
| `td.telemetry.drop_level0` | `False` | `param_drop_level0` | |
| `td.telemetry.level0_migrated` | `{}` | `param_level0_migrated` | звіт хука |
| `td.telemetry.stale_notify_min` | `0` | `param_stale_notify_min` | зарезервовано (Q-11), 0 = вимкнено |

### 5.2 `data/td_source_data.xml` (`noupdate="1"`) і `data/signal_catalog.csv`

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
Логер `odoo.addons.td_telemetry.hooks`, INFO з лічильниками на кожен крок.

| # | Функція | Джерело | Що робить | Ідемпотентність | Очікувано (копія демо 14.10.2026, 14 112 показань на ≈07:30 UTC) | Чиста база |
|---|---|---|---|---|---|---|
| 1 | `params(env)` | CB-10 | `read_enabled = (environment == 'test')`; `default_team_id` = id `maintenance.team` з `name='Служба головного механіка'` або перший | перезапис лише порожніх/дефолтних | `read_enabled=True`, `team=2` | `True`/перша команда |
| 2 | `signals_level0(env)` | `x_f3d_signal` (ORM, `sudo`, `active_test=False`) | якщо `'x_f3d_signal' not in env` → `skipped`; інакше для кожного запису (порядок `x_sequence, id`, щоб джерела `x_source_id` створювались раніше): `vals` за Додатком D; `search([('code','=',x_code)])` → `write` (лише поля визначення, не `last_*`, якщо запис уже `origin='sim_data'`) або `create`; xml-id `td_telemetry.sig_<slug>` (`slug` = `plant/odoo_rpc.key(x_code)`); другий прохід — `derived_from_id` за `x_source_id` | upsert за `code` | `signals_migrated: 196`, `created: 196`, `alarm: 1`, `with_request: 2`, `by_module: {energy: 87, bms: 81, fire_safety: 1, telemetry: 27}` (energy = 84 `energy/*` + 3 `infra/totals/*`, Додаток B) | `skipped` |
| 3 | `signals_catalog(env)` | `data/signal_catalog.csv` | `new=1` → `create` (`origin='catalog'`), якщо коду ще немає; усі рядки — `write` непорожніх колонок прив'язки; `source` → `search([('code','=',source)])`; `equipment` → `env['maintenance.equipment'].search_f3d(code)` (CB-01), немає → WARNING і без обладнання; рядок `new=0` з кодом, якого немає в базі, → `bind_missing`; джерелам Додатка C.1 без `equipment_id` — `search_f3d` за кодом обладнання | upsert | звіт `signals_catalog`: `created: 29`, `bound: 55`, `bind_missing: 0`, `no_equipment: 0` (усі коди є в демо: FL-*, TUGGER-1, COMPRESSOR, DUST-1, T1, T2, WATER, SPRINKLERS, AIR-RING, BOILER) | `created: 29`, `bound: 28`, `bind_missing: 27`, `no_equipment: 29` (WARNING на кожен) |
| 3а | `meters(env)` | Додаток C.4 (`hooks.METERS`) | ТО за лічильником на обладнанні з порожнім `td_meter_signal_id`; прив'язка наявної відкритої `preventive` заявки (A-22) | лише порожні | `meters: 9`, `meter_requests_linked: 9` | `meters: 0` |
| 4 | `sim_catalog(env)` | `td.sim.signal` (iot_sim 19.0.2.0.0) | якщо моделі немає → `skipped`; інакше `_td_import_sim_catalog(codes=<225 кодів моєї зони>, source_map=Додаток C.3, defaults={'origin': keep})` — заповнює `address`, якщо порожня, `sim_params`, `nominal`; не змінює `source_id`, якщо вже є | upsert | на демо з data-модулем 19.0.1.0.0 — `skipped` | `skipped` |
| 5 | `readings_level0(env)` | `x_f3d_reading` | батчами по 5 000: `SELECT r.id, r.x_signal_id, r.x_value, r.x_time, r.create_date FROM x_f3d_reading r ORDER BY id` → `execute_values("INSERT INTO td_reading (signal_id, equipment_id, ts, value, quality, src, received_at) VALUES %s ON CONFLICT (signal_id, ts) DO NOTHING")` із `signal_id` за мапою крок 2, `received_at` = `create_date` запису рівня 0 (коли показання потрапило в Odoo; X-83); `x_time` NULL → пропуск | `ON CONFLICT` | `readings_migrated: N` — кількість `x_f3d_reading` з `x_time` на момент установки (14 112 на 14.10.2026 ≈07:30 UTC; ≤ 56 448 за 2 доби), `skipped_null_ts: 0` | `skipped` |
| 6 | `requests_level0(env)` | `maintenance.request` із `x_request_id` | для сигналів з `maintenance_request_id`: `request.write({'td_signal_id', 'td_origin': 'threshold', 'td_value': last_value, 'td_threshold': alarm_*})`; якщо `request.stage_id.done` → сигнал `maintenance_request_id=False`, `request_closed_at=request.write_date` | перезапис | `requests_linked: 2` (id 6 RV-05, id 5 FA-FAC — обидві відкриті) | `skipped` |
| 7 | `hours_rebuild(env)` | `td.reading` | R-09 за всіма годинами, де є показання, але немає агрегату | upsert | `hours: ≈ 1 400` (196 × 7 год) | 0 |
| 8 | `verify(env)` | кроки 2, 5 | `count(td.signal, origin=sim_data) == count(x_f3d_signal)`; для кожного — `abs(last_value − x_value) < 1e-6` і `status` відповідає `x_state`; `count(td.reading, src=sim_data) == count(x_f3d_reading з x_time)`; рядки розбіжностей `"<code>: last_value 304.241 != x_value 304.000"` | — | `mismatches: []` | `[]` |
| 9 | `level0_off(env)` | `ir.cron`, `ir.ui.menu`, `ir.ui.view`, `x_f3d_signal`, `ir.config_parameter` | лише якщо `mismatches == []`: `cron_iot_sim.active=False` (`env.ref('td_iot_sim.cron_iot_sim', raise_if_not_found=False)`); `cr.execute("UPDATE x_f3d_signal SET x_active = false")`; меню `td_iot_sim.menu_iot_root` → `active=False` (діти ховаються з батьком); представлення `td_iot_sim.view_equipment_form_signals` → `active=False`; параметр `td.iot_sim.level0_enabled` (якщо існує) → `False` | повторно — без змін | `cron_off: True`, `x_inactive: 196`, `menu_off: 1`, `view_off: 1`, `iot_sim_param: True/False` | `skipped` |
| 10 | `drop_level0(env)` | параметр `drop_level0` | лише якщо `True` і `mismatches == []`: `ir.ui.view` рівня 0 (7 за xml-id `td_iot_sim.view_*`) `unlink`; `drop_manual_fields(env, 'maintenance.equipment', ['x_f3d_signal_ids'])` (CB-11); `env['ir.model'].search([('model','in',['x_f3d_reading','x_f3d_signal'])]).unlink()` (спершу reading — FK); меню рівня 0 `unlink` | повторно — нічого | за замовчуванням `skipped` | `skipped` |
| 11 | `report(env, report)` | — | `level0_migrated = json.dumps(report)`, `report` — плоский dict: `state`, `ts`, `mismatches`, лічильники кроків 2 (`signals_migrated`, `by_module`, `alarm`, `with_request`), 3а (`meters`, `meter_requests_linked`), 5 (`readings_migrated`, `skipped_null_ts`), 6 (`requests_linked`), 7 (`hours`), 9 (`cron_off`, `x_inactive`, `menu_off`, `view_off`) і вкладені `signals_catalog` (крок 3), `sim_catalog` (крок 4); `state` = `skipped` (крок 2 skipped) / `partial` (`mismatches`) / `done` | перезапис | `done` | `skipped` |

Загалом після установки на копії демо: `td.signal` **225** (196 `sim_data` + 29 `catalog`), з них із
`source_id` **55**, без джерела 170 (169 чужих + `infra/water/flow_m3h` похідна), `status`: `alarm` 1
(`ventilation/units/RV-05/filter_dp_pa`), `ok` 195, `unknown` 29 (нові — до першого показання); `td.source` 7;
`td.collector` 1; `td.reading` = кількість `x_f3d_reading`; `maintenance.request` з `td_signal_id` — 11 (2 `threshold` + 9 `meter`, крок 3а).

`action_td_run_migration` (`data/td_actions.xml`, `ir.actions.server` на `td.signal`,
`code="action = env['td.signal'].f3d_run_migration()"`): метод `@api.model f3d_run_migration(self)` —
`AccessError` без `group_td_admin`; інакше `hooks.run_migration(self.env)` і `display_notification` зі
звітом (`sticky=True`).

### 5.4 `uninstall_hook(env)`

1. Крони модуля — видаляються з модулем; тут: `td.command` у `queued/sent` → нічого (таблиця зникне).
2. Якщо `'x_f3d_signal' in env`: `cr.execute("UPDATE x_f3d_signal SET x_active = true")`; меню
   `td_iot_sim.menu_iot_root`, представлення `view_equipment_form_signals` → `active=True`; крон
   `cron_iot_sim` **не** вмикається (лог WARNING «рівень 0 вимкнено; увімкніть вручну або через пульт»).
3. `ir.config_parameter` `td.telemetry.*` → `unlink`; `td.iot_sim.level0_enabled` не чіпається.
4. `maintenance.request` лишаються (поля `td_*` зникають з модулем); `td.reading`, `td.reading.hour`,
   `td.push.event` — видаляються з моделями (технічні журнали, як iot_sim A-11); `td.signal`,
   `td.source`, `td.collector` — теж (визначення відтворюються з data/міграції при повторній установці).

### 5.5 Повторна установка

`post_init_hook` на базі, де рівень 0 уже архівовано (`x_active=False`): крок 2 читає з
`active_test=False` → 196 знову; `last_value` беруться з `x_value` (застарілі) **лише** якщо сигнал
створюється; крок 9 повторно вимикає рівень 0; показання `ON CONFLICT` — без дублікатів.

### 5.6 `data/neutralize.sql`

```sql
-- td_telemetry: нейтралізація копії проду (CB-10, каркас §5)
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('td.telemetry.read_enabled', 'td.telemetry.write_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_telemetry';
UPDATE td_source SET read_enabled = false, write_enabled = false, state = 'disabled';
UPDATE td_collector SET token_hash = NULL, token_hint = NULL, state = 'never';
UPDATE td_command SET state = 'expired' WHERE state IN ('queued', 'sent');
UPDATE td_signal SET write_enabled = false;
```

## 6. Крони й фонові процеси (`data/ir_cron.xml`)

| XML-id | Назва | Інтервал | Модель / метод | Один прогін | Ліміти |
|---|---|---|---|---|---|
| `cron_td_telemetry_stale` | Телеметрія: застарілі сигнали й офлайн-колектори | 1 хв, `active=True` | `td.signal._cron_stale` | R-07: один `search` кандидатів з `status in (ok,warn,alarm)`, джерелом нелокального типу (R-26) і `last_ts < now − stale_min_s`; відбір у Python `last_ts < now − s._td_stale_after()` (вікно на сигнал, для COV — X-06); `_mark_stale('timeout')` батчем; потім `td.collector._cron_offline()` (R-25) | ≤ 5 с; не більше 2 000 сигналів за прогін |
| `cron_td_telemetry_hour` | Телеметрія: годинні агрегати | 10 хв, `active=True` | `td.reading.hour._cron_aggregate` | R-09: для закритих годин від `max(hour) − 1 год` (або найстарішого показання) до `date_trunc('hour', now) − 1 год` — один SQL upsert | ≤ 30 с; вікно ≤ 48 год за прогін (решта — наступним) |
| `cron_td_telemetry_rotate` | Телеметрія: ротація показань | 1 доба, `nextcall` = найближче 02:40 Europe/Kyiv (ставить хук через `pytz`), `active=True` | `td.reading._cron_rotate` | R-10: `DELETE FROM td_reading WHERE ts < now − keep_days` батчами по 50 000 (`ctid`/`id` підзапит); те саме для `td_reading_hour` (`keep_hours_days`) і `td_push_event` (`keep_days`) | ≤ 60 с; решта — наступного дня |
| `cron_td_telemetry_commands_gc` | Телеметрія: прострочені команди | 10 хв, `active=True` | `td.command._cron_expire` | `queued/sent` з `expires_at < now` → `expired` | — |
| `td_iot_sim.cron_iot_sim` | Емулятор IoT: рівень 0 | — | — | **вимикається** хуком §5.3 крок 9; модуль його не створює і не видаляє | — |

Крони виконуються від `base.user_root`; методи працюють `sudo()` на власних моделях, не торкаються
`maintenance.request` (заявки створює лише Ingester у транзакції push або R-07 ніколи — `stale` заявок не
створює).

## 7. HTTP/JSON API (CT-04)

Спільне: `controllers/telemetry.py`, усі маршрути `type="http"`, `auth="public"`, `csrf=False`,
`methods` як у таблиці; відповідь `request.make_json_response(data, status)` з `Content-Type:
application/json; charset=utf-8`, `Cache-Control: no-store` (крім API-01 — `private, max-age=0`).
Автентифікація: заголовок `Authorization: Bearer <token>` → `td.collector._authenticate(token)`; порожній
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
Віддаються лише активні джерела цього колектора (джерела локальних типів R-26 — ніколи) й активні сигнали з непорожньою адресою; джерела з
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

Обробка (R-17 п. 0, X-02, D-19): контролер автентифікує колектор, перевіряє стоп-кран (`423`), розмір і схему тіла
(`400`/`413`), `collector` (`403`) і ліміт частоти (`429`, R-17 п. 2), після чого **один раз** викликає
`env['td.signal'].sudo()._td_ingest(body["readings"], src='collector', collector=c)` (`c` — автентифікований
`td.collector`) і будує відповідь з її результату (`changed` = `changed_codes`; `config_etag`, `read_enabled`,
`server_time` додає контролер). Прямий виклик `tools/ingest.Ingester` з контролера заборонено — інакше перевизначення
`_td_ingest` модулів (fire, energy, machine_connect, yard, bms) не спрацюють для пакетів колектора.
Відповідь `200`:

```json
{"accepted": 4, "stored": 2, "duplicates": 0, "rejected": [{"i": 7, "code": "equipment/XX/y", "reason": "unknown_code"}],
 "changed": ["equipment/FL-C1/battery", "equipment/FL-C1/state"], "alarms_opened": 0,
 "config_etag": "a3f9…", "read_enabled": true, "server_time": "2026-10-14T06:10:06Z"}
```

`accepted` — елементи, що оновили `last_*` (або були старіші за `last_ts`, але валідні); `stored` — записані
в `td.reading` (R-03); `duplicates` — `(signal, ts)` уже були; `rejected[].reason` ∈ {`unknown_code`,
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
"server_time": "…", "rejected": ["<невідомі або чужі коди>"]}`; `sources` не список → `400 bad_schema`. Ліміти: ≤ 500 джерел у звіті, ≤ 256 КБ (більше → `413`). Коди: `200`, `400`, `401`, `403`.
`state` ∈ {`online`, `offline`, `error`}; `error` ≤ 512 символів; секрети у `error` колектор маскує сам
(`SecretFilter`), Odoo додатково обрізає все після `password=`/`token=` (R-25).

### API-04 `GET /f3d/telemetry/health`

Без токена: `200 {"ok": true, "module": "td_telemetry", "version": "19.0.1.1.0", "server_time": "…"}`.
З валідним токеном — додатково `"collector": {"code", "state", "last_seen"}, "counts": {"signals": 225,
"alarms": 1, "stale": 0, "sources_online": 6}`. Невалідний токен — як без токена (`200` без лічильників). Жодних інших даних без токена (безпека §13.3). `ok=false`
(`503`) лише якщо реєстр моделей недоступний (теоретично ніколи — слугує для `HEALTHCHECK`).

### API-05 `POST /f3d/telemetry/event` (ретрансляція `http_push`, CT-08)

```json
{"collector": "COL-MAIN",
 "events": [{"event_id": "9f1c…(sha256 hex, 64)", "route": "lpr", "ts": "2026-10-14T05:15:05.507Z", "remote": "10.90.2.5",
             "headers": {"content-type": "application/json", "user-agent": "AXIS LPV"},
             "payload": {"plateText": "AA4512KT", "plateUnicode": "АА4512КТ", "carState": "new", "carMoveDirection": "in",
                         "GEOtarget": "GATE-W", "sensorProviderID": "CAM-05", "capture_timestamp": "1791954905507", "…": "…"}}]}
```

≤ 100 подій, ≤ 1 МБ; `event_id*` (64 hex: sha256 від маршруту + тіла + `remote`), `route*`
(`^[a-z][a-z0-9_]{0,31}$`), `ts*` ISO з зоною, `remote`, `headers` (лише `content-type`, `user-agent`,
`x-f3d-token-ok`), `payload*` (JSON object ≤ 256 КБ). Невалідна подія (немає обов'язкового ключа, `route` не за регексом, `payload` не
об'єкт) → `400 bad_schema` для всього пакета. Дія (R-22): для кожної події — `td.push.event`
(дублікат `event_id` → `rejected: duplicate`); диспетчеризація обробникам M-11 з `_td_push_routes ∋ route`;
сигнали джерел `http_push` цього колектора з `address.route == route` і `match ⊆ payload` → показання через
`env['td.signal'].sudo()._td_ingest(readings, src='collector', collector=c)` (X-02; той самий вхід, що API-02) з контекстом
`f3d_received_at` — «час прийому» пакета в Odoo (`td.reading.received_at`, R-22, X-83); `events[].ts` — час події від колектора
(пристрою), лише для відображення в журналі й дедуплікації.
Відповідь `200 {"accepted": n, "rejected": [...], "handled": {"lpr": ["td.push.handler.yard"]}}` (`handled` —
`_name` моделей-обробників M-11 за маршрутом). Коди: `200`, `400`, `401`, `403`, `413`, `423` (`read_disabled`).

Маршрути подій (X-05; маршрут без обробника приймається — `td.push.event` з порожнім `handled_by`, без помилки):

| `route` | Хто породжує (плагін колектора) | Обробник (M-11) | Схема `payload` |
|---|---|---|---|
| `lpr` | `http_push` (Axis LPV, `POST /f3d/lpr[/<secret>]`, §8.7) | `td.push.handler.yard` (yard M-12) | Axis LPV JSON (iot_sim §8.13.2) |
| `mc_opcua`, `mc_woodstore`, `mc_cutopt` | `opcua`, `rest_vendor` (machine_connect §8.3–§8.4) | `td.push.handler.machine_connect` (machine_connect M-21) | machine_connect EV-01…EV-03 |
| `bacnet_event` | `bacnet_ip` — ретрансляція `UnconfirmedEventNotification` (§8.8, R-23) | `td.push.handler.fire` (fire_safety M-18) | fire_safety API-01: `device*`, `object*`, `instance*`, `event_type*`, `from_state`, `to_state`, `mode`, `message_text`, `ts*`, `notification_class`, `priority`, `ack_required` |

### API-06 `GET /f3d/telemetry/commands`

Параметри: `limit` (≤ 100, default 50). Дія (R-18): якщо глобальний `write_enabled=False` → `200
{"commands": [], "write_enabled": false}`; інакше `queued` команди сигналів джерел цього колектора з
`expires_at > now`, упорядковані `requested_at` → `state='sent'`, `sent_at=now`; відповідь:

```json
{"write_enabled": true, "server_time": "…",
 "commands": [{"id": 17, "code": "ventilation/units/RV-05/mode", "source": "BAC-105-RV-05",
               "value": 1.0, "text": "VEL", "payload": null, "requested_at": "…", "expires_at": "…",
               "address": {"object": "MSV", "instance": 1, "map": {"1": "VE", "2": "VEL", "3": "AQ", "4": "REC", "5": "EA", "6": "SA", "7": "ST", "8": "Off"}}},
              {"id": 18, "code": "workcenters/SAW-1/job_cmd", "source": "UA-SAW-1",
               "value": 0.0, "text": null, "payload": {"method": "StoreAndStart", "job": "WO00013", "qty": 14, "ref": "WH/MO/00233", "priority": 5},
               "requested_at": "…", "expires_at": "…", "address": {"nodeid": "ns=2;s=SAW-1.JobManagement.JobOrderControl", "io": "write", "call": "job"}}]}
```

Приклад 1 — режим установки RV-05 (bms R-25, дозволений запис MSV:1; X-53): `value` — довідковий 0-based індекс M-06,
плагін пише `2` за зворотним `map` (R-23, X-66). Приклад 2 — команда-виклик CR-01 (X-03; зміст `payload` — machine_connect
CM-08, тут ілюстративно). Схема елемента: `id*` int, `code*`, `source*`, `value` number|null, `text` str|null, `payload`
object|null (CR-01), `requested_at*`, `expires_at*`, `address*` (Додаток A.1). Коди `200`, `401`, `403`. Колектор опитує
кожні `F3D_COMMANDS_POLL_S` (5 с) лише коли `write_enabled` (з відповіді API-01/API-02).

### API-07 `POST /f3d/telemetry/commands/result`

```json
{"collector": "COL-MAIN", "results": [{"id": 17, "state": "done", "ts": "…", "result": "written 2 @prio 8", "error": null, "data": null},
                                      {"id": 18, "state": "done", "ts": "…", "result": "{\"ReturnStatus\": 0}", "error": null, "data": {"ReturnStatus": 0}},
                                      {"id": 19, "state": "failed", "ts": "…", "result": null, "error": "WriteAccessDenied", "data": null}]}
```

Дія: `sent` → `done`/`failed` з `done_at`, `result`, `error` і `result_data = data` (CR-01, X-03; `data` — об'єкт, який
повернув `call()`, або `null`/відсутній); інші стани → `rejected: already_done|not_sent`; неіснуючий id або команда іншого колектора → `not_found`;
`results` не список, `data` не об'єкт/`null` або `data` > 64 КБ → `400 bad_schema` для всього запиту.
Чаттер команди: «Виконано: …» / «Помилка: …». Відповідь `200 {"accepted": n, "rejected": [...]}`.

### 7.1 Контрольний приклад curl (стенд)

```bash
TOKEN=…   # з майстра M-12
curl -sS -H "Authorization: Bearer $TOKEN" http://odoo19:8069/f3d/telemetry/config | jq .etag
curl -sS -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"collector":"COL-MAIN","readings":[{"code":"equipment/COMPRESSOR/pressure_bar","ts":"2026-10-14T06:10:00Z","value":5.9}]}' \
  http://odoo19:8069/f3d/telemetry/push
# → {"accepted":1,"stored":1,...,"alarms_opened":0}  (min_duration_s=30); те саме з ts +30 с → "alarms_opened":1
# і заявка «Компресорна станція: тиск 5,9 бар при нормі від 6»
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
| `F3D_COLLECTOR_CODE` | str / **обов'язково** | = `td.collector.code` |
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
    code: str; kind: str; unit: str; period_s: int
    scale: float                         # signal.scale — застосовує лише ядро (§8.3.3, R-02, X-63); плагін НЕ множить
    write_enabled: bool
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
    payload: dict | None = None          # CR-01 (X-03): не None → ядро викликає plugin.call(), а не write()

@dataclass(frozen=True)
class CommandResult:
    id: int; state: str; ts: datetime; result: str | None = None; error: str | None = None
    data: dict | None = None             # CR-01: dict, який повернув call(); → API-07 data → td.command.result_data

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
    emit: Callable[[Reading], None]         # для push-протоколів: ядро множить value на signal.scale (R-02) і кладе в буфер
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
        settings.write_enabled and source.write_enabled and signal.write_enabled (ядро перевіряє до виклику).
        Стан (`text`): ключ зворотного address.map; BACnet MSV/MSI без map — 1-based індекс у states (X-66)."""
    async def call(self, signal: SignalCfg, payload: dict) -> dict:
        """CR-01 (X-03): виконати команду-виклик з корисним навантаженням (метод OPC UA, завдання порталу тощо);
        повертає JSON-серіалізований dict ≤ 64 КБ (→ CommandResult.data). За замовчуванням raise NotSupported.
        Ті самі передумови, що write(); ядро викликає call() лише для Command.payload is not None."""
    def health(self) -> Health: ...
```

Реєстрація: `pyproject.toml` `[project.entry-points."factory3d_collector.plugins"] modbus_tcp = "collector.plugins.modbus_tcp:ModbusTcpPlugin"`.
`load_plugins()` → `importlib.metadata.entry_points(group="factory3d_collector.plugins")` → `{type: cls}`;
джерело з типом без плагіна → `Health(state='error', error='plugin <type> not installed')` і WARNING, решта
працює. Плагіни інших модулів — окремі pip-пакети з тим самим entry point (напр. `f3d_collector_opcua`),
встановлюються в образ через `requirements-extra.txt`.

Винятки ядра: `ConnectError`, `PollError`, `WriteError`, `NotSupported`, `AllowlistDenied` — усі з
`collector.core.errors`; текст без секретів.

Масштаб (R-02, X-63): `poll()`/`emit()` повертають **інженерне** значення `eng` — плагін уже застосував усі ключі адреси
свого типу (`scale`, `offset` — спільні A.0; `map`, `agg`, `range` тощо); `SignalCfg.scale` плагін не застосовує. Плагіни
`call()` у цьому модулі (`modbus_tcp`, `mqtt`, `http_push`, `bacnet_ip`) не реалізують → `NotSupported`; реалізують
`opcua`, `rest_vendor` (machine_connect).

#### 8.3.3 Планувальник (`core/scheduler.py`) — R-19

- Для кожного джерела з `read_enabled` і плагіном не-push: групи = `{period_s: [signals]}`; на групу —
  таска `loop_poll(source, period, signals)`: `await plugin.poll(signals)` → `apply_signal_scale(readings)` →
  `buffer.put_many(readings)`. `apply_signal_scale` (`core/scheduler.py`, також обгортка `ctx.emit` для push-плагінів;
  X-63, R-02): для показань сигналів `kind ∈ {gauge, counter}` з `value is not None` — `value = value · signal.scale`
  рівно один раз; `text`, `value=None`, `state`/`event` — без змін; невідомий код — без змін (WARNING);
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
  `expires_at > now`; якщо `cmd.payload is None` — `await plugin.write(signal, value, text)` → `CommandResult(done,
  result)`; інакше (CR-01, X-03) — `data = await plugin.call(signal, cmd.payload)`: `data` не `dict`, не серіалізується в
  JSON або > 64 КБ → `failed` «call returned invalid data»; інакше `CommandResult(done, result=json.dumps(data,
  ensure_ascii=False, sort_keys=True)[:256], data=data)`; `NotSupported` → `failed` «call not supported by <type>».
  Таймаут виклику — 10 с (для адреси з `write.pulse_ms` — `10 + pulse_ms/1000` с, X-46); таймаут → `failed` «timeout»,
  інший виняток → `failed` з його текстом → `POST commands/result` (через буфер `results`, щоб не загубити).

### 8.5 Плагін `modbus_tcp` (`plugins/modbus_tcp.py`) — R-20

- `pymodbus.client.AsyncModbusTcpClient(host, port, timeout=params.timeout_s, retries=params.retries)`;
  **пул**: один клієнт на `(host, port)` спільний для всіх джерел (кілька unit за одним шлюзом) — клас
  `ConnectionPool` у модулі плагіна; `connect()` → `await client.connect()`; `connected` перевіряється перед
  кожним `poll`.
- `poll(signals)`: групування (R-20 п. 3) → для кожного блоку `read_coils` (fc 1) / `read_discrete_inputs`
  (2) / `read_holding_registers` (3) / `read_input_registers` (4) з `slave=unit` (`unit` сигналу або
  джерела); `rr.isError()` → `PollError(str(rr))` (виняток Modbus 0x02/0x0B — у тексті); декодування
  `util/codec.decode_registers(regs, type, wordorder, byteorder)`; `value = raw·address.scale + address.offset` (масштаб
  адреси, X-63; `signal.scale` застосовує ядро, §8.3.3); `range`
  порушено → `q='bad'`; `kind='state'`: `map[str(int(raw))]` → `text` (немає в `map` → `text=str(raw)`,
  `q='uncertain'`); `states[]`-адреси (складений стан) → перший збіг за порядком.
- `write(signal, value, text)`: `fc` 5 (coil, `value != 0`) / 6 (один регістр) / 16 (кілька: типи 32/64/f32)
  на `address.write.addr` або `address.addr`; `kind='state'` з `text` → `value = int(key)` за зворотним
  `map`; результат `"fc16 addr 3100 = [7000]"`. Без `write.pulse_ms` запис **рівневий** (X-81): плагін пише значення команди
  (fc 5: `value != 0` → `True`) і більше нічого — вихід лишається в записаному стані до наступної команди (yard `cmd_hold`:
  «тримати відкритим» = 1, зняття утримання — команда зі значенням 0); результат `"fc5 addr 20 = True"`.
- **Імпульс** (`address.write.pulse_ms`, 100…10 000, лише з `write.fc` 5 або 6; лише для імпульсних команд — yard
  `cmd_open`/`cmd_close`; X-46, X-81, yard Q-04 — CAME ≥ 1 с):
  значення команди ігнорується; плагін пише `1` (fc 5 — `True`, fc 6 — `1`), чекає `pulse_ms` (`clock.sleep`, з'єднання
  між записами не блокується — опитування інших сигналів тривають), пише `0`; скидання (`0`) виконується в `finally` і
  захищене від скасування (`asyncio.shield`), тож таймаут команди не лишає вихід увімкненим; невдале скидання —
  до 3 спроб з інтервалом 0,5 с, далі `WriteError("pulse reset failed: <текст>")` і метрика
  `collector_modbus_pulse_reset_failed_total{source}`; невдалий перший запис → скидання все одно виконується (стан
  виходу невідомий), команда `failed` з текстом першої помилки. Результат `"fc5 addr 16 pulse 1→0 1500 ms"`.
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
  obj)`; `ts` = `jsonpath.get(ts_path)` (ISO або epoch мс) або час отримання колектором; `kind='gauge'/'counter'` → число
  (`bool` → 0/1) → `eng = val·address.scale + address.offset` (спільні ключі A.0, умовчання 1/0; X-63); `kind='state'` → `map.get(str(val), str(val))` → `text`; відсутній шлях → пропуск
  (`collector_mqtt_missing_path_total`).
- `retain`-повідомлення при підключенні → приймаються, але `ts` = час отримання колектором і `q='uncertain'` (стале
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
  `address.ts_path` сигналів маршруту (перший, що є) → epoch мс/с або ISO; інакше час отримання колектором
  (`event.ts` — час пристрою/колектора для журналу й дедуплікації; «час прийому» показання — `td.reading.received_at`
  в Odoo, R-22, X-83);
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
  `ReadProperty`); для кожного сигналу: `present-value` → число (`Real`/`Unsigned` (у т.ч. `positive-integer-value`,
  X-37)/`Enumerated`/`Boolean` → float; для `gauge`/`counter` далі `eng = raw·address.scale + address.offset` — A.0,
  X-63; `MultiState` → 1-based індекс → `map[str(idx)]` або `states[idx−1]` → `text`); `status-flags` читається тим самим RPM
  (`fault` або `in-alarm` → `q='uncertain'`; `out-of-service` → `q='bad'`); `reliability`, якщо є в адресі
  (`check_reliability=true`) ≠ `no-fault-detected` → `q='bad'`; `priority-array` — лише для AO/AV/BV при
  `address.read_priority_array=true` (у `Reading` не передається; потрібно для `write` release — кешується).
- `mode='cov'`: після `connect` — `SubscribeCOV(subscriber_process_id=<hash сигналу>, object, confirmed=False,
  lifetime=cov_lifetime_s)`; `UnconfirmedCOVNotification` → показання (`ts` = час отримання колектором; `present-value` і
  `status-flags` з повідомлення); поновлення підписки на 2/3 `lifetime`; відмова (`Error`/таймаут) → сигнал
  переводиться в `poll` з `period_s` до наступного `connect`; метрика `collector_bacnet_cov_active`.
  Сигнали `mode='poll'` опитуються планувальником як звичайно; у `cov` планувальник також виконує
  контрольне читання раз на `cov_check_s(period_s) = max(period_s·10, 300)` с (виявлення «мовчазної» підписки).
  Результат контрольного читання — звичайне показання (`Reading`, `ts` = час читання), навіть якщо значення не змінилось,
  тож `last_ts` COV-сигналу в спокої оновлюється не рідше `cov_check_s`; Odoo рахує для таких сигналів `stale` від цього
  інтервалу (R-07, `td.signal._td_stale_after`, X-06). Ефективний режим: `address.mode`, інакше умовчання A.1 за
  об'єктом; для джерела з `params.read_only=true` — завжди `poll` (нижче).
- **`read_only`** (`params.read_only=true`, пожежна панель FACP-1; D-07, X-05, fire_safety ARCH Q-07): плагін **ініціює**
  до такого пристрою лише сервіси `Who-Is`, `ReadProperty`, `ReadPropertyMultiple`. Усі вихідні запити йдуть через
  `BacnetApp._request(source, service, …)` з білим списком `RO_SERVICES = {"who-is", "read-property",
  "read-property-multiple"}`; будь-який інший сервіс (`SubscribeCOV`, `SubscribeCOVProperty`, `AcknowledgeAlarm`,
  `LifeSafetyOperation`, `WriteProperty`, `WritePropertyMultiple`, `DeviceCommunicationControl`,
  `ReinitializeDevice`, `AtomicWriteFile`, `CreateObject`, `DeleteObject` тощо) → `NotSupported("read-only device:
  <service>")` **до** формування пакета, метрика `collector_bacnet_ro_blocked_total{source,service}`; не залежить від
  `F3D_WRITE_ENABLED` і прапорів запису. Сигнали з `mode='cov'` на такому джерелі опитуються як `poll` з `period_s`
  (INFO раз на `connect`). Прийом вхідних `UnconfirmedEventNotification` (нижче) — не запит до пристрою й дозволений.
- **Події `bacnet_event`** (X-05, fire_safety API-01, M-18): вхідне `UnconfirmedEventNotification` від пристрою, для
  якого є джерело `bacnet_ip` цього колектора з `read_enabled` і `params.events` (умовчання = значення `params.read_only`,
  A-23), ретранслюється в Odoo: `ctx.emit_event(PushEvent(event_id, route="bacnet_event", ts=<час отримання колектором, UTC>,
  remote=<код джерела>, headers={}, payload))` → буфер `events` → API-05. `payload`: `device` (instance
  `initiatingDeviceIdentifier`), `object` (тип `eventObjectIdentifier` у короткій формі `AI/AO/AV/BI/BO/BV/MSI/MSV/LSZ/
  LSP/PIV`, інші — повна назва ASHRAE), `instance`, `event_type` (назва `eventType`: `change-of-life-safety`,
  `change-of-state`, `out-of-range` …), `from_state`/`to_state` — для `change-of-life-safety`: `to_state` = `new-state`
  (`BACnetLifeSafetyState`: `quiet`, `alarm`, `fault`, `test-alarm` …), `mode` = `new-mode`, `from_state` = попередній
  `to_state` цього об'єкта з кешу плагіна (подія або останнє опитане значення `present-value`), інакше `fromState`; для
  решти типів — `fromState`/`toState` (`normal`, `offnormal`, `fault`, `high-limit`, `low-limit`); `message_text` (≤ 500,
  обрізається), `notification_class`, `priority`, `ack_required` (bool), `ts` — час отримання колектором ISO `…Z` (часова мітка
  пристрою не використовується: годинник панелі не синхронізований із колектором). `event_id = sha256("bacnet_event\n" +
  <код джерела> + "\n" + canonical_json(payload))`. Подія від пристрою без джерела або з `events=false` → відкидається,
  `collector_bacnet_events_ignored_total{reason="unknown_device"|"disabled"}`; прийняті —
  `collector_bacnet_events_total{source}`. `ConfirmedEventNotification` плагін не обробляє (панель налаштовує
  монтажник на unconfirmed-сповіщення колектору).
- `write(signal, value, text)`: заборонено, якщо `params.read_only` (`NotSupported("read-only device")`) —
  перевірка в коді, не лише в даних (D-07); інакше `WriteProperty(object, 'present-value', pv,
  priority=address.priority or 8)`, де `pv` за порядком: (1) `text == "null"` або (`value is None` і `text` порожній) →
  `Null` (release пріоритету); (2) `text` задано — стан (X-66, як у Modbus): є `address.map` → ключ зворотного `map`
  (`text="VEL"`, `map {"1":"VE","2":"VEL",…}` → `2`); `map` немає, об'єкт MSV/MSI → 1-based індекс
  `states.index(text) + 1` (та сама база, що читання); BV/BO без `map` → `inactive`=0 / `active`=1; `text` не знайдено →
  `WriteError("text «…» немає в map/states")` без відправки; `value` команди тут не використовується; (3) інакше —
  число `value`. Результат `"written <pv> @prio <p>"` (`"written 2 @prio 8"`); `Error: write-access-denied` → `WriteError`.
- `health()`: `online`, якщо останній RPM/COV без помилки ≤ 2 періоди; `stats`: `polls`, `cov_notifications`,
  `events`, `ro_blocked`, `errors`, `latency_ms`.
- Тести: `bacpypes3` тестовий пристрій (`tests/conftest.py: bacnet_device`) з об'єктами AI:1, AI:2, AI:3, AO:1,
  MSV:1, BI:1, LSZ:12, PIV:1 на вільному UDP-порту (без роутера), журналом отриманих сервісів і генератором подій
  (§13.0.2); стенд — емулятор (роутер + мережа 2).

### 8.9 Метрики (`core/metrics.py`, `/metrics`)

`collector_up`, `collector_config_etag_info{etag}`, `collector_readings_total{source}`,
`collector_readings_rejected_total{reason}`, `collector_push_total{status}` (`ok|retry|rejected|locked`),
`collector_push_latency_seconds` (histogram), `collector_buffer_rows`, `collector_buffer_dropped_total`,
`collector_source_up{source,type}` (0/1), `collector_poll_seconds{source}` (histogram),
`collector_poll_errors_total{source}`, `collector_poll_overrun_total{source}`,
`collector_mqtt_messages_total{source}`, `collector_mqtt_missing_path_total{source}`,
`collector_http_push_requests_total{route,status}`, `collector_bacnet_cov_active{source}`,
`collector_bacnet_events_total{source}`, `collector_bacnet_events_ignored_total{reason}`,
`collector_bacnet_ro_blocked_total{source,service}` (X-05), `collector_modbus_pulse_reset_failed_total{source}` (X-46),
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
- Запис у пристрої: чотири запобіжники (ARCH §2.6); плагін отримує `write()`/`call()` лише після перевірок ядра;
  `bacnet_ip` для `read_only` ініціює лише Who-Is/ReadProperty/ReadPropertyMultiple (§8.8, X-05).
- Конфігурація з Odoo валідується схемами до створення плагінів; невалідне джерело → `error` у статусі, не
  падіння процесу.
- Образ: non-root, `read_only`, без shell-утиліт, `pip install --no-cache-dir`, `HEALTHCHECK`.

## 9. Алгоритми й правила

| ID | Правило | Алгоритм / формула | Приклад (вхід → вихід) |
|---|---|---|---|
| R-01 | **Формат коду сигналу** | `^[a-z_]+(/[A-Za-z0-9_\-\.]+)+$`, ≤ 128 (= iot_sim M-03). Перший сегмент — розділ payload переглядача (`energy`, `equipment`, `ventilation`, `fire`, `infra`, `workcenters`, `lighting`, `yard`, `access`), останній — ключ у вузлі | `equipment/FL-C1/battery` ✓; `ventilation/units/RV-05/filter_dp_pa` ✓; `Equipment/FL-1` ✗ (великі), `equipment` ✗ (один сегмент), `energy//x` ✗ |
| R-02 | **Перетворення значення** (X-63) | Два кроки, кожен рівно один раз. (1) **Плагін** повертає інженерне значення `eng = f_addr(raw)`, застосувавши всі ключі адреси свого типу: спільні `scale`, `offset` (A.0, умовчання 1/0, дозволені для будь-якого типу: `eng = raw·address.scale + address.offset`), а також специфічні (`agg`, `wordorder`, `bit` — Modbus; `map`/`states` — стани; `query`/`scale` — `helvarnet`, bms R-33 тощо). (2) **Ядро колектора** множить на `signal.scale` (default 1) перед буфером (§8.3.3 `apply_signal_scale`, лише `gauge`/`counter` з числовим `value`): `value = eng · signal.scale`. Плагіни `SignalCfg.scale` не застосовують. Для `http_push` обидва кроки виконує Odoo в R-22 (значення витягується з події в Odoo). В Odoo значення більше не перетворюється (окрім округлення в представленнях за `decimals`). Переглядач — R-12 | ADAM-6017 AI0 raw 60 950, адреса `scale=32000/65535=0.48829`, `offset=0` → 29 761,2 м³/год; RTD raw 35 716, `scale=200/65535=0.0030519`, `offset=−50` → 59,0 °C; Elektronikon HR 3002 = 6772, `scale=0.001` → 6,772 бар (`signal.scale=1` → 6,772); bms `lighting/groups/LT-CUT/p_now`: HelvarNet C:161 → 3 402 Вт, адреса `scale=0.001` (плагін) → 3,402, `signal.scale=1` → **3,402 кВт** (не 3 402 і не 0,003402) |
| R-03 | **Політика зберігання** | Показання з `q != 'bad'` і `ts > last_ts` завжди оновлює `last_value/last_text/last_ts/last_quality`. У `td.reading` пишеться, якщо: (а) `store_period_s == 0`; або (б) `last_stored_ts` порожній або `ts − last_stored_ts ≥ store_period_s`; або (в) змінився `status` (R-04) або `last_text` (стан); або (г) `q == 'bad'` (діагностика, не частіше ніж раз на `store_period_s` від останнього збереженого `bad`). Показання старіше `last_ts` (повтор з буфера) — пишеться за (б) відносно найближчого збереженого, але `last_*` не чіпає. Після запису `last_stored_ts = ts` | `store_period_s=300`, показання кожні 10 с: за годину зберігається 12, `last_value` оновлюється 360 разів; стан техніки `busy→charging` — записується одразу |
| R-04 | **Статус за порогами** (чиста функція `tools/thresholds.eval_status(state, value, text, ts, cfg)`) | `kind ∈ {gauge, counter}`: `breach = alarm_low_on ∧ v < alarm_low` або `alarm_high_on ∧ v > alarm_high` → рівень `alarm`; інакше `warn_low_on ∧ v < warn_low` або `warn_high_on ∧ v > warn_high` → `warn`; інакше `ok`. **Гістерезис**: якщо поточний `status` уже `alarm` (`warn`), вихід у нижчий рівень лише коли `v ≥ alarm_low + h` (для нижнього) / `v ≤ alarm_high − h` (для верхнього), `h = hysteresis`. **Мінімальна тривалість**: перехід у вищий рівень (`ok→warn`, `ok→alarm`, `warn→alarm`) набуває чинності, коли умова тримається ≥ `min_duration_s` (`breach_since` = перший `ts` порушення; `ts − breach_since ≥ min_duration_s`); зниження — негайно. `kind='state'`: `text ∈ alarm_states` → `alarm`, інакше `ok`. `kind='event'`: завжди `ok`. `q='bad'` → статус не змінюється. Зміна статусу → `status_since = ts`, чаттер «Стан: норма → тривога (304,2 Па)». `stale` → при першому показанні повертається до обчисленого | RV-05 `alarm_high=250`, `h=10`: 285 → `alarm`; 248 → лишається `alarm` (≥ 240); 239 → `ok`. FL-C1 `warn_low=25`, `alarm_low=15`: 23,6 → `warn`; 14,2 → `alarm`; 26 → `ok`. COMPRESSOR `alarm_low=6.0`, `h=0.1`, `min_duration_s=30`: 5,9 о 10:00:00 → `breach_since`; 5,95 о 10:00:30 → `alarm`; 6,05 → лишається; 6,11 → `ok`. `equipment/COMPRESSOR/state` `alarm_states=["fault"]`: `fault` → `alarm`, `loaded` → `ok` |
| R-05 | **Тривога → заявка ТО** (§6.8, CT-05) | Умови створення: `status` став `alarm` (перехід) ∧ `create_request` ∧ `equipment_id` ∧ `maintenance_request_id` порожнє (або його `stage_id.done`) ∧ (`request_closed_at` порожнє або `now − request_closed_at ≥ realarm_cooldown_s`). Поля: `name = render_title`, `equipment_id`, `maintenance_type='corrective'`, `maintenance_team_id = equipment.maintenance_team_id or param default_team_id`, `priority = alarm_priority`, `td_signal_id`, `td_equipment_code`, `td_origin='threshold'`, `td_value=v` (або `text`), `td_threshold` (поріг, що спрацював), `description` = «Автоматично з телеметрії: сигнал <code>, показник <v> <unit> <rel> порогу <thr> <unit>, джерело <source.code>, час <ts Київ>.», `request_date=today`, `schedule_date=now`. Сигнал: `maintenance_request_id=request`; чаттер сигналу «Створено заявку <name>». **Шаблон заголовка**: `alarm_title` з плейсхолдерами `{name}` (назва сигналу), `{equipment}` (`equipment_id.name`), `{code}` (`td_code` обладнання), `{quantity}`, `{value}` (`tools/titles.fmt_num(v, decimals)`, A-21: округлення до `decimals`, десяткова кома, зайві нулі дробової частини відкидаються, групи тисяч через пробіл, якщо модуль ≥ 1 000), `{unit}`, `{threshold}` (`fmt_num` з тим самим `decimals`), `{rel}` («до» для верхнього порогу, «від» для нижнього), `{text}`; порожній `alarm_title` → умовчання `"{name}: {value} {unit} при нормі {rel} {threshold} {unit}"`; для `state` — `"{name}: стан «{text}»"`. Довжина ≤ 256. Кілька сигналів одного обладнання → кілька заявок (дедуплікація — на сигнал, не на обладнання) | RV-05 (`alarm_title="Заміна фільтрів: перепад тиску {value} Па при нормі до {threshold}"`, `decimals=0`): 285,2 → «Заміна фільтрів: перепад тиску 285 Па при нормі до 250». FL-C1 battery (`alarm_title="Зарядити АКБ: заряд {value} % при нормі від {threshold}"`, `decimals=1`): 14,2 → «Зарядити АКБ: заряд 14,2 % при нормі від 15». COMPRESSOR pressure (міграція R-15: `alarm_title="{equipment}: тиск {value} бар при нормі від {threshold}"`, обладнання «Компресорна станція», `decimals=2`): 5,9 → «Компресорна станція: тиск 5,9 бар при нормі від 6»; без `alarm_title`, `name="Тиск на виході"` → «Тиск на виході: 5,9 бар при нормі від 6 бар». FA-FAC dust → «Очистити сповіщувач: запиленість 92 % при нормі до 90». COMPRESSOR state `fault` → «Компресор: стан «fault»» |
| R-06 | **Закриття заявки** | `maintenance.request.write` з переходом у `stage_id.done`: для `td_signal_id`: якщо це його `maintenance_request_id` — `maintenance_request_id=False`, `request_closed_at=now`; в усіх випадках (і для заявок, створених іншими модулями з `td_signal_id`, напр. міст генератора) `status` перераховується з `last_value` за R-04 **без** мін. тривалості й без створення заявки; чаттер сигналу «Заявку <name> закрито; стан: <status>»; якщо `status` лишився `alarm` — додатково «Тривога триває, нова заявка не раніше <now + cooldown Київ>». Повторне відкриття заявки (`done → not done`): якщо сигнал без відкритої заявки — `maintenance_request_id = request` знову. Видалення заявки — `ondelete set null` → сигнал без заявки, `request_closed_at=now` | RV-05: заявка закрита, емулятор скинув 120 Па → `ok`; закрита без ремонту при 300 Па → `alarm` лишається, нова заявка — через 1 год при наступному показанні > 250 (перехід не потрібен: при `status=alarm` і порожній заявці після cooldown Ingester створює заявку за «утриманням» — умова R-05 перевіряється на кожному показанні в `alarm`, не лише на переході) |
| R-07 | **Stale** | `stale_after = max(stale_periods · p, stale_min_s)` (`td.signal._td_stale_after()`), де `p = period_s`, а для сигналів з ефективним режимом `cov` (джерело `bacnet_ip` без `params.read_only`; `address.mode == 'cov'` або `mode` не задано й об'єкт за умовчанням `cov` — A.1) `p = cov_check_s(period_s) = max(period_s · 10, 300)` — інтервал контрольного читання колектора (§8.8), бо в спокої COV-сигнал отримує показання лише з нього (X-06). Крон щохвилини: сигнали з `status ∈ {ok,warn,alarm}` ∧ `source_id` нелокального типу (R-26: `source_id.type not in _td_local_types()`) ∧ `last_ts < now − stale_after` → `_mark_stale('timeout')`. Джерело `offline/error/disabled` (API-03 або крон колектора) → усі його сигнали зі `status ≠ unknown` → `stale` одразу. Сигнали **без** `source_id` (`sim_data` до прив'язки) — ніколи не `stale` (п. 4 ARCH §1.4). `stale` не змінює `maintenance_request_id` і не створює заявок (Q-11). Перше валідне показання → R-04 | `equipment/COMPRESSOR/pressure_bar` `period_s=10` → `stale_after = max(30, 60) = 60 с`; `equipment/FL-1/battery` `period_s=5` → 60 с; `infra/water/m3_total` `period_s=60` → 180 с; `equipment/BOILER/supply_c` (`BAC-140-BOILER`, `mode='cov'`, `period_s=30`) → `p = max(300, 300) = 300`, `stale_after = 900 с`; той самий сигнал з `mode='poll'` → 90 с; AI на джерелі з `read_only=true` (`mode` не задано) → `poll`, `period_s=30` → 90 с; `energy/consumers/SAW-1/p_now` без джерела → лишається `ok` зі значенням рівня 0 |
| R-08 | **Лічильники й похідні** | `kind='counter'`: значення монотонні; показання `v < last_value − 1 %·last_value` (крім лічильників із `sim_params.reset='daily'`, напр. `cycles_today` о 00:00, — у них зменшення штатне, `q='good'`) → `q='uncertain'`, приймається (можливий ролловер/заміна лічильника), чаттер раз на добу. `derive_rule='rate_h'` (`infra/water/flow_m3h`): при кожному показанні джерела `m3_total` Ingester бере найстаріше збережене показання джерела у вікні `[ts − 300 с, ts − 60 с]` (або `last_stored` старше 60 с) і пише похідне показання `value = (v − v_prev) / ((ts − ts_prev)/3600)` з `ts` джерела, `src` як у джерела; немає попереднього → пропуск. `cycles_today` (`equipment/GANTRY-1/cycles_today`) — лічильник з добовим скиданням: `sim_params.reset='daily'` | вода: 18 642,00 о 10:00, 18 642,35 о 10:10 → `flow_m3h = 0,35/(600/3600) = 2,1 м³/год`; `hours` 17 846,6 → 17 846,8 (+0,2 за 12 хв) ✓; 17 846,8 → 17 000 → `uncertain` |
| R-09 | **Годинні агрегати** | Крон: `INSERT INTO td_reading_hour (signal_id, equipment_id, hour, v_min, v_avg, v_max, v_sum, v_count, v_first, v_last, delta) SELECT signal_id, max(equipment_id), date_trunc('hour', ts), min(value), avg(value), max(value), sum(value), count(*), (array_agg(value ORDER BY ts))[1], (array_agg(value ORDER BY ts DESC))[1], delta FROM td_reading r JOIN td_signal s … WHERE r.quality <> 'bad' AND ts >= %s AND ts < %s GROUP BY signal_id, date_trunc('hour', ts) ON CONFLICT (signal_id, hour) DO UPDATE SET …`. **`delta`** (X-07, A-25): для `kind='counter'` `delta(h) = v_last(h) − v_prev(h)`, де `v_prev(h)` = `v_last` попередньої години того ж сигналу у вікні (`LAG(v_last) OVER (PARTITION BY signal_id ORDER BY hour)`), а для першої години вікна — `v_last` найсвіжішого наявного агрегату `td_reading_hour` з `hour <` початку вікна (за безперервного ряду це `h − 1`; при пропуску годин — остання година з даними, тож приріст за пропуск не губиться); немає попереднього (перша година ряду) → `v_last(h) − v_first(h)`; `v_last(h) < v_prev(h)` (добове скидання/ролловер, R-08) → `v_last(h) − v_first(h)`; не лічильник → 0. Сума `delta` за добу = приріст лічильника від останнього показання попередньої доби до останнього показання цієї (без скидань). Вікно: від `max(hour) − 1 год` (повторний перерахунок останньої години — для показань, що прийшли з буфера пізніше) до останньої закритої години включно (`ts < date_trunc('hour', now)`, остання `hour = date_trunc('hour', now) − 1 год`); `stale`/`state` сигнали агрегуються за `value` (індексом) — для станів `v_avg` сенсу не має, UI показує `v_last`. Рядки `text` без `value` (події) — `v_count` тільки | RV-05 за 10:00–11:00 при 12 збережених показаннях 280…290 → `v_min=280`, `v_max=290`, `v_count=12`; `hours` компресора (перша година ряду) `v_first=17 846,6`, `v_last=17 847,6`, `delta=1,0`; наступна година 17 847,9 … 17 848,4 → `delta = 17 848,4 − 17 847,6 = 0,8` (а не `v_last − v_first = 0,5`: 0,3 між годинами не губиться); година без показань, потім 17 849,0 → `delta = 17 849,0 − 17 848,4 = 0,6` |
| R-10 | **Ротація** | Щодня: `DELETE FROM td_reading WHERE id IN (SELECT id FROM td_reading WHERE ts < %s ORDER BY ts LIMIT 50000)` у циклі ≤ 60 с (`now − keep_days`); `td_reading_hour` — `hour < now − keep_hours_days`; `td_push_event` — `ts < now − keep_days`. Агрегати за видалені години лишаються. Лог INFO з кількостями; `VACUUM` не викликається (autovacuum) | `keep_days=30` на 14.11: усе до 15.10 видаляється; агрегати з 13.10 лишаються до 400 днів |
| R-11 | **ТО за лічильником** | Перевірка `_td_meter_check` при кожному оновленні `td_meter_signal_id.last_value` (Ingester, після `last_*`): `next = td_meter_last_value + td_meter_interval`; `lead = interval · lead_pct/100`; якщо `current ≥ next − lead` ∧ `td_meter_request_id` порожнє (або `done`) → `maintenance.request`: `name = "ТО за лічильником: {td_code} — {next:n} {unit} (зараз {current:n})"`, `maintenance_type='preventive'`, `maintenance_team_id` як R-05, `priority='1'` (`'3'`, якщо `current ≥ next`), `td_signal_id = meter`, `td_origin='meter'`, `td_value=current`, `td_threshold=next`, `schedule_date = now + max(0, (next − current)/rate)` де `rate` = `delta` за останні 7 діб з `td.reading.hour`/168 год (невідомо → `now`); `equipment.td_meter_request_id = request`; чаттер обладнання. Закриття (`_td_meter_closed`): `td_meter_last_value = meter.last_value` на момент закриття, `td_meter_last_date = today`, `td_meter_request_id=False` → `next` перераховується. Зміна `td_meter_last_value/interval` вручну → перевірка повторюється при наступному показанні. Сигнал без показань (`unknown`) — нічого | COMPRESSOR: `last=16 000`, `interval=2 000`, `lead 5 %` → `next=18 000`, заявка при `current ≥ 17 900`: на демо `hours=17 846,6` → заявки ще немає, `remaining=153,4`; при 17 900,2 → «ТО за лічильником: COMPRESSOR — 18 000 год (зараз 17 900)», `schedule_date` ≈ через `99,8/ (8,5/24)` ≈ 11,7 доби (з `delta` 8,5 год/добу, iot_sim R-06). FL-2: `last=3 000`, `interval=1 000`, `hours=3 216,5` → `next=4 000`, `remaining=783,5` |
| R-12 | **Значення для переглядача** (CT-07; порт `odoo_pull.sync_signals`) | Для кожного сигналу (`active`, `viewer_visible`, `status ≠ unknown`): `*path, leaf = code.split('/')`; `node = payload[path[0]]…[path[-1]]` — якщо будь-який крок не `dict`/відсутній → пропуск (без створення вузлів). `kind ∈ {gauge, counter}`: `v = last_value`; `unit == '%'` → `node[leaf] = round(v/100, 3)`; інакше `round(v, 2)` при `abs(v) < 20`, інакше `round(v, 1)`. `kind='state'`: `node[leaf] = last_text` (для техніки `equipment/<code>/state` — значення `busy\|charging\|idle\|to_charge\|offline\|fault`; `to_charge` → `busy` робить адреса `map`, тож тут без перетворень). Після циклу: якщо є обидва `infra.totals.pv_now` і `energy.totals` → `energy.totals.pv_kw = infra.totals.pv_now`; так само `chp_kw`. `meta.iot = {"source": "телеметрія (td_telemetry)", "signals": n_видимих, "alarms": count(status=alarm), "stale": count(stale), "updated": local(max(last_ts)) "YYYY-MM-DD HH:MM" Київ}`. `ctx.lite`/`ctx.kiosk` — без відмінностей | `equipment/FL-C1/battery` 23,6 % → `equipment["FL-C1"].battery = 0.236`; `equipment/COMPRESSOR/hours` 17 846,6 → `17846.6`; `pressure_bar` 6,772 → `6.77`; `equipment/FL-C1/state` `charging` → `equipment["FL-C1"].state = "charging"`; `infra/water/m3_total` → вузол `infra.water` відсутній у payload → пропуск (поки energy/infra-провайдер його не створить); `equipment/FL-1/x` — `viewer_visible=False` → пропуск |
| R-13 | **Шина (дебаунс)** | Після обробки пакета: `codes = {сигнали, у яких змінився last_value/last_text/status}`; для кожного — якщо `last_notified_ts` порожній або `now − last_notified_ts ≥ bus_min_interval_s` або змінився `status` чи `last_text` → у список повідомлення і `last_notified_ts=now` (SQL batch); далі один виклик `_notify_viewer(codes)` → viewer M-03 коалесує в одне повідомлення на транзакцію. Без viewer — лише оновлення `last_notified_ts` не робиться | 8 навантажувачів шлють кожні 5 с → переглядач отримує код не частіше 1 разу на 10 с на сигнал; зміна стану `busy→charging` — негайно |
| R-14 | **Часові пояси** | База: UTC naive. API вхід: ISO 8601 з `Z`/зсувом → `datetime.fromisoformat` (Python 3.12 розуміє `Z`) → `astimezone(UTC)` → naive; рядок без зони → `ts_no_tz`; `datetime` без tzinfo (виклики CT-10 з Python) — UTC. API вихід: `…Z`. Тексти заявок/чаттера/`meta.iot.updated`: `Europe/Kyiv` через `pytz`/`zoneinfo` (`fields.Datetime.context_timestamp` з `tz='Europe/Kyiv'` — не з користувача, бо контролер працює від суперкористувача). Рівень 0: `x_time`/`x_updated` — UTC naive (сервер Odoo у UTC), переносяться як є. Колектор: усі `Reading.ts` tz-aware UTC; MQTT `ts` `+03:00` → UTC; Axis `capture_timestamp` epoch мс → UTC | `"2026-10-14T06:10:03.250+03:00"` → `2026-10-14 03:10:03.250` UTC; у заявці «час 14.10.2026 06:10» (Київ) |
| R-15 | **Виведення `module`, `kind`, порогів і заголовків при міграції** | `module` за префіксом коду (CT-09): `energy/*`, `infra/*` → `energy`, крім `infra/water/*` → `telemetry`, `infra/genset/*` → `genset`; `ventilation/*`, `lighting/*` → `bms`; `fire/*` → `fire_safety`; `equipment/*` → `telemetry`; `workcenters/*` → `machine_connect`; `yard/*` → `yard`; `access/*` → `access`; інше → `other`. `kind` за `x_mode`: `hours`, `energy`, `counter` → `counter`; решта (`noise`, `machine`, `drain`, `drift`, `level`, `solar`) → `gauge`. Пороги: `x_alarm='above'` → `alarm_high=x_threshold`, `alarm_high_on=True`; `'below'` → `alarm_low`; інакше вимкнені; `hysteresis` = 2 % від `\|threshold\|` для `drift` (RV: 5 Па; DUST 0,036 кПа; FA-FAC 1,8 %), 0 для решти. `alarm_title` за `quantity` + `x_alarm`: «Перепад» above → «Заміна фільтрів: перепад тиску {value} {unit} при нормі до {threshold}»; «Запиленість» above → «Очистити сповіщувач: запиленість {value} % при нормі до {threshold}»; «Тиск» below → «{equipment}: тиск {value} бар при нормі від {threshold}»; «Температура» above → «{equipment}: температура {value} °C при нормі до {threshold}»; «Вакуум» above → «Портал: вакуум {value} кПа при нормі нижче {threshold}»; інакше порожньо (умовчання R-05). `decimals`: `unit ∈ {Па, %, шт}` → 0; `кВт·год, год` → 1; інакше 2. `quantity = x_kind`; `name = x_name`; `sequence = x_sequence`; `status`: `'тривога'` → `alarm`, інакше `ok`; `status_since = x_updated` | `ventilation/units/RV-05/filter_dp_pa`: `module=bms`, `kind=gauge`, `alarm_high=250`, `h=5`, заголовок «Заміна фільтрів…»; `energy/consumers/SAW-1/kwh_shift`: `module=energy`, `kind=counter`, `derived_from=…/p_now`; `equipment/FL-1/hours`: `telemetry`, `counter` |
| R-16 | **ETag конфігурації** | `etag = sha256(json.dumps(payload без ключів etag/generated_at/server_time, sort_keys=True))` — обчислюється при кожному запиті (≤ 50 мс на 1 000 сигналів); `collector.config_etag = etag` (без `write` якщо не змінився). `If-None-Match` збіг → `304`. Будь-який `write` у `td.source`/`td.signal` з полями конфігурації чи глобальних параметрів змінює payload → інший etag автоматично | зміна `period_s` сигналу → наступний `push` повертає новий `config_etag` → колектор перечитує |
| R-17 | **Валідація, ідемпотентність і паралельність push** (`tools/ingest.Ingester`) | 0) **Вхід** (X-02, D-19): `Ingester` викликається лише з `td.signal._td_ingest`; API-02 і API-05 викликають `env['td.signal'].sudo()._td_ingest(readings, src='collector', collector=c)`, модулі (CT-10) — `_td_ingest(readings, src='module')`; перевизначення модулів (M-03, «точка розширення») отримують усі показання — і колектора, і модулів; 1) розбір і валідація елементів (reason-коди API-02); 2) ліміт частоти — виконує **контролер API-02 до** виклику п. 0 (не `_td_ingest`): `INSERT` у `td_collector_push` і `COUNT` рядків колектора за останні 60 с (DEC-19; поля `rate_window_start`/`rate_count` вилучено), count > `push_rate_per_min` → `429`; 3) `signals = search_read([('code','in',codes)], fields…)` одним запитом; чужі/неактивні → reject; 4) сортування показань за `(code, ts)`; 5) для кожного сигналу — послідовно `_apply_reading` у пам'яті (R-03/R-04/R-08) → списки: `to_store`, `last_updates`, `status_changes`, `requests_to_open`, `meter_checks`, `derived_readings`; 6) `execute_values("INSERT INTO td_reading (signal_id, equipment_id, ts, value, text, quality, src, received_at) VALUES %s ON CONFLICT (signal_id, ts) DO NOTHING RETURNING signal_id")` → `stored`; `received_at` — «час прийому» (X-83): одне значення на виклик `_td_ingest`, `self.env.context.get('f3d_received_at') or fields.Datetime.now()` (R-22 передає його в контексті, щоб час прийому показання й заміна `ts` збігалися); `duplicates` — показання пакета, чия пара `(signal_id, ts)` уже є в `td.reading` (конфлікти `ON CONFLICT` + один `SELECT` пар для показань з `ts ≤ last_ts`, що не стали кандидатами); 7) `executemany("UPDATE td_signal SET last_value=%s, last_text=%s, last_ts=%s, last_quality=%s, last_stored_ts=%s WHERE id=%s AND (last_ts IS NULL OR last_ts < %s)")` — старіше показання з іншого воркера не перезапише новіше; 8) `invalidate_model(['last_value','last_text','last_ts','last_quality','last_stored_ts'])`; 9) ORM `write` для `status/status_since/breach_since` (лише змінені), `_open_request` (R-05), `_td_meter_check` (R-11), чаттер; 10) R-13 шина; 11) відповідь. Усе в одній транзакції запиту; виняток → `500` і повний відкат (колектор повторить пакет; дублікати відсіє `ON CONFLICT`). Для CT-10 (`src='module'`) — ті самі кроки без перевірки колектора (`foreign_signal`); API-05 — без п. 2 | пакет 1 000 показань × 55 сигналів → 1 `search_read`, 1 `execute_values`, 1 `executemany`, ≤ 55 ORM-записів; повтор того самого пакета → `duplicates=1000`, `stored=0`, `changed=[]` |
| R-18 | **Життєвий цикл команди** | 1) створення (`td.command.create`): `signal.write_enabled` ∧ `signal.source_id.write_enabled` ∧ параметр `write_enabled` — інакше `UserError("Запис у пристрій вимкнено: <що саме>")`; якщо `not env.su` і користувач без `group_td_manager` → `AccessError`; під `env.su` (`sudo()`, `with_user(SUPERUSER_ID)` — модулі yard A-20, bms R-25, machine_connect M-20) перевірку групи пропущено (X-04, як base R-04), усі інші перевірки цього пункту діють так само; `source_id.params.read_only` → `UserError("Джерело лише для читання.")`; джерело локального типу (R-26) → `UserError("Джерело %s без колектора: запис у пристрій неможливий.")`; 2) `queued` → API-06 віддає → `sent`; 3) колектор: четвертий запобіжник `F3D_WRITE_ENABLED`; `plugin.write` (або `plugin.call(signal, payload)` для команди з `payload` — CR-01, X-03, §8.4) → API-07 (з `data` для `call`) → `done`/`failed`; 4) `expires_at` минув у `queued/sent` → `expired` (крон); 5) `done` → через ≤ `period_s` сигнал покаже нове значення (окремо, читанням); команда не змінює `last_value` сама | оператор bms ставить режим RV-05 `VEL` (bms R-25: `td.command` `ventilation/units/RV-05/mode`, `text="VEL"` під `with_user(SUPERUSER_ID)`) → колектор `WriteProperty MSV:1 = 2 prio 8` (зворотний `map`, R-23) → `done`; при `F3D_WRITE_ENABLED=0` колектор не опитує API-06 → команда `expired` через 10 хв з чаттером «Колектор не забрав команду» |
| R-19 | **Планувальник, пакети, бекоф, буфер** | §8.3.3–§8.3.4. Формули: джиттер старту `U(0, period)`; бекоф `min(30, 2^n)` с для `poll`, `min(60, 2^n)` для `connect` і Odoo; пакет відправляється при `len(buffer) ≥ push_max` або за таймером `push_interval_s`; буфер FIFO, ліміт за розміром файлу (`PRAGMA page_count·page_size`), перевірка раз на 60 с | Odoo недоступний 1 год при 15 показаннях/с → 54 000 рядків ≈ 5 МБ у буфері; після відновлення — 54 пакети по 1 000 з інтервалом ≥ 1 с (без очікування `push_interval_s`, якщо буфер ≥ `push_max`) |
| R-20 | **Modbus: декодування і групування** | Типи: `bool` (coil/DI або біт `bit` регістра), `u16`, `i16` (1 регістр), `u32`, `i32`, `f32` (2), `u64`, `i64`, `f64` (4); `wordorder` `big` (старше слово в першому регістрі — PM5560, Huawei, Elektronikon за iot_sim) або `little` (ADAM лічильники: низьке слово першим — iot_sim §8.4.2); `byteorder` `big` (Modbus-стандарт) — `little` лише для екзотики. Групування: сигнали одного `unit` і `fc` сортуються за `addr`; сусідні об'єднуються в блок, якщо `addr_next − (addr_last + count_last) ≤ params.gap_max` (default 8) і довжина блоку ≤ `params.max_block` (125 регістрів / 2000 бітів); один запит на блок; `agg` (`max\|min\|sum\|avg\|first`) — над `count` однотипних значень. Адреси у `address.addr` — **PDU** (A-01); `doc` ігнорується | u70: `pressure` addr 3001, `load` 3009, `hours` 3019 (u32) → один блок `3000…3020` (21 регістр); u96 T1 `addr 0, count 3, agg max` + T2 `addr 3, count 3` → блок 0…5; ADAM лічильник води `addr 16, u32, little`: регістри `[0x2E2A, 0x001C]` → `0x001C2E2A = 1 846 826` імп × 0,01 = 18 468,26 м³ |
| R-21 | **MQTT: відображення** | §8.6; `path` — підмножина JSONPath: `$`, `.key`, `[n]`; значення `bool` → 0/1; `null` → пропуск; рядок-число → `float` (для gauge/counter); `map` застосовується до `str(val)`; `ts_path` → ISO або epoch (с/мс за величиною > 10¹¹ → мс); `retain` → `q='uncertain'` | `{"battery_pct": 57.1, "state": "to_charge", "ts": "2026-10-14T08:15:03+03:00"}` → `equipment/FL-1/battery = 57.1`, `state` з `map {"to_charge":"busy"}` → `busy`, `ts` 05:15:03Z |
| R-22 | **HTTP push: маршрутизація в Odoo** (API-05) | Для події `route`: (1) `td.push.event` (дублікат → reject); (2) обробники M-11 у порядку `_name`, кожен у `savepoint`; (3) сигнали: `search([('source_id.type','=','http_push'), ('source_id.collector_id','=',collector), ('active','=',True)])` з `address.route == route` і `all(payload.get(k) == v for k, v in address.match.items())` → `val = jsonpath(address.path, payload)`; для `gauge`/`counter` — число (`bool` → 0/1, рядок-число → `float`, інше → пропуск) і масштаб R-02 обидва кроки тут: `value = (val·address.scale + address.offset) · signal.scale` (X-63) → `env['td.signal'].sudo().with_context(f3d_received_at=received_at)._td_ingest([{code, ts, value\|text}], src='collector', collector=c)` (X-02), де `received_at = fields.Datetime.now()` — «час прийому», один на пакет `_td_receive`; показання отримують `td.reading.received_at = received_at` (X-83); `ts` показання — час пристрою з `address.ts_path` (лише для відображення й дедуплікації); без `ts_path` — `ts = received_at`; якщо `ts_path` дає `ts_future`/`ts_too_old`/`ts_invalid` (вікно рахується від `received_at`) — `ts = received_at` з `q='uncertain'` (Q-15, закрито X-48); `event.ts` колектора (`td.push.event.ts`, §8.7) і `capture_timestamp` — час пристрою, лише для відображення й дедуплікації, «часом прийому» не є (X-83); `kind='event'` → `value=1`, `text = str(val)[:64]`; `signal_count` у журналі | подія CAM-05 `plateText=AA4512KT`: обробник yard (`td.push.handler.yard`, yard M-12; X-53) знаходить бронювання; сигнал `yard/lpr/CAM-05/plate` (`address={"route":"lpr","match":{"sensorProviderID":"CAM-05"},"path":"$.plateText","ts_path":"$.capture_timestamp"}`) → показання `text="AA4512KT"`, `ts = 2026-10-14 05:15:05.507` (`capture_timestamp` `1791954905507` — час камери), `received_at = 2026-10-14 05:15:10` (час прийому в Odoo, X-83); `capture_timestamp` на 2 хв у майбутньому (`ts_future`) → `ts = received_at = 05:15:10`, `q='uncertain'` |
| R-23 | **BACnet: адресація, COV, запис** | §8.8. `object` приймає канонічні назви ASHRAE (`analog-input`, `analog-output`, `analog-value`, `binary-input`, `binary-output`, `binary-value`, `multi-state-value`, `multi-state-input`, `life-safety-zone`, `life-safety-point`, `positive-integer-value`, `device`) і короткі `AI/AO/AV/BI/BO/BV/MSV/MSI/LSZ/LSP/PIV` (нормалізуються валідатором; `PIV` — X-37, Cerberus FC726: лічильники, запиленість за PICS); `property` default `present-value`; `index` — для масивів (`priority-array[8]`); `mode` default `cov` для AI/BI/MSI/MSV/LSZ/LSP, `poll` для решти (у т.ч. PIV), для джерела з `params.read_only` — завжди `poll` (§8.8, X-05); `cov_lifetime_s` default 300; `priority` 1…16 default 8 (запис). `Enumerated`/`MultiState` → `map` або `states` (1-based індекс MSV → `states[idx−1]`); `Unsigned` (PIV) → число; **запис стану** (X-66, як Modbus): є `map` → ключ зворотного `map`; без `map` для MSV/MSI → 1-based `states.index(text)+1`; `value` команди для стану не використовується; **події** `UnconfirmedEventNotification` → маршрут `bacnet_event` (§8.8, API-05, X-05); `BinaryPV` → `inactive/active` → `map` (default `{"0":"off","1":"on"}` для state, 0/1 для gauge); `LifeSafetyState` → назва enum (`quiet`, `alarm`, `fault`, `test-alarm`…) → `text`. Складений стан — `states[]` з `object/instance/eq/text` (перший збіг) | `equipment/BOILER/supply_c`: `{"device":140,"object":"AI","instance":1,"mode":"cov"}`; `ventilation/units/RV-05/mode` (bms): `{"device":105,"object":"MSV","instance":1,"map":{"1":"VE","2":"VEL","3":"AQ","4":"REC","5":"EA","6":"SA","7":"ST","8":"Off"}}`; `fire/groups/FA-CUT/state` (fire_safety): `{"device":200,"object":"LSZ","instance":12}` → `text="alarm"`; PIV `{"object":"PIV","instance":3}` → `positive-integer-value` 3, `Unsigned` 17 → 17.0; запис режиму RV-05 `text="VEL"` (адреса з `map` вище) → `WriteProperty dev105 MSV:1 PV 2 prio 8` (не 1 = `VE`); MSV без `map`, `states=["standby","K1","K1+K2","fault"]`, `text="K1"` → PV 2 |
| R-24 | **Парсер адрес каталогу емулятора** (`tools/sim_catalog.parse_sim_address(protocol, text) -> dict\|None`, CT-11, A-18) | Регулярні вирази над колонкою «Адреса в джерелі» Додатка A iot_sim; результат — `address` за Додатком A.1 цього документа. **Адреса Modbus — PDU за документом вендора, без загального «номер − 1»** (D-20, X-42, як energy R-01): (а) PDU-нотація каталогу `u<unit> fc<n> pdu<addr>[+<count>]` (колонка PDU iot_sim за X-42 / Q-04) — береться як є; (б) якщо PDU-нотації в рядку немає — вендорська нотація за unit iot_sim §8.4.1: Huawei SUN2000/LUNA2000 (u61…u69), Socomec ATyS p (u71), TEDOM (u72) — номер у документі вендора вже PDU → `addr = N`; ADAM (u80…u96): `N ≥ 40001 → N − 40001`, `30001 ≤ N < 40000 → fc 4, N − 30001`, coil/DI `00001… → N − 1`; PM5560 (u1…u59) і Elektronikon Mk5 (u70, ПРИПУЩЕННЯ — як C.2) — 1-based у документі → `N − 1`; unit поза переліком → `None` (`unparsed`). Шаблони: (0) `Modbus u(\d+)(?: \([^)]*\))? fc([1-4]) pdu(\d+)(?:\+(\d+))?` → `{"unit":u,"fc":n,"addr":pdu,"count"?}` (тип/масштаб — з колонок, як у (1)); (1) `Modbus u(\d+)(?: \([^)]*\))? HR (\d+)(?:[–-](\d+))?` → `{"fc":3,"addr":pdu(u, a),"count":b−a+1 або за type,"unit":u}` (`pdu(u, N)` — правило (б)); `type` з колонки «Тип» (`U16/I16/U32/I32/I64/F32` → нижній регістр), `wordorder: "little"` якщо в тексті `ADAM` і `лічильник`; `scale` з колонки «Масштаб» (`×0,001` → 0.001; `R-20` → лінійні коефіцієнти з діапазону в дужках `4–20 мА = 0…32 000` → `scale=(hi−lo)/65535`, `offset=lo`; `0–65535 → −50…+150` → `scale=200/65535, offset=−50`); (2) `Modbus u(\d+)(?: \([^)]*\))? DI(\d+) coil 0*(\d+)` (і кілька через кому для складеного стану) → `{"fc":2,"addr":n−1,"type":"bool"}` або `states[]`; `DO(\d+) coil` → `write`; (3) `MQTT (\S+) → \$\.(\S+)` → `{"topic","path":"$.…"}`; (4) `BACnet dev (\d+) (AI\|AO\|AV\|BI\|BO\|BV\|MSV\|LSZ\|LSP\|PIV):(\d+)` (PIV — X-37) (кілька — `states[]`), `Present_Value` → `present-value`; (5) `OPC UA\|ns=2;s=…` → `{"nodeid"}`; (6) `GET (/\S+) → \$\.(\S+)` → `{"method":"GET","path":…,"json_path":"$.…"}`; (7) `HTTP POST <collector>/f3d/(\w+) → (.+)` → `{"route","path":"$.<перше поле>"}`; (8) `SICS … «(\w+)»` → `{"cmd": "SI", "field": "weight"}` (`field="stable"`, якщо в тексті є `stable` або `стабіл`; X-45 — схема yard §8.2, `field` обов'язковий, `cmd` лише `SI`; інша команда в лапках → `None`); (9) `Σ Modbus u61…u68`, `похідна`, `GET /api/v1/jobs?…` і все інше → `None` (→ `unparsed`). `map` для enum з колонки «Одиниця» виду `0 stop/1 load/2 unload/3 fault` → `{"0":"stop",…}`. Позначка `[notation?]` (Q-04) більше не ставиться — Q-04 закрито X-42 | `Modbus u70 (Elektronikon Mk5, ПРИПУЩЕННЯ) HR 3002 (Outlet pressure)` + `U16`, `×0,001` → `{"unit":70,"fc":3,"addr":3001,"type":"u16","scale":0.001,"doc":"HR 3002 (Outlet pressure)"}`; `Modbus u90 (ADAM-6017) HR 40001 (AI0, 4–20 мА = 0…32 000 м³/год)` → `{"unit":90,"fc":3,"addr":0,"type":"u16","scale":0.48829,"offset":0,"range":[0,32000]}`; `Modbus u84 (ADAM-6050) HR 40017–40018 (лічильник DI8, …)` + `U32`, `×0,01` → `{"unit":84,"fc":3,"addr":16,"count":2,"type":"u32","wordorder":"little","scale":0.01}`; `MQTT f3d/mobile/FL-1/telemetry → $.battery_pct` → `{"topic":"f3d/mobile/FL-1/telemetry","path":"$.battery_pct"}`; `BACnet dev 140 AI:1 Present_Value (подача)` → `{"device":140,"object":"analog-input","instance":1,"property":"present-value"}`; `Modbus u84 (ADAM-6050) DI0 coil 00001 (вентилятори в роботі), DI1 coil 00002 (аварія)` → `{"unit":84,"fc":2,"states":[{"addr":1,"eq":1,"text":"fault"},{"addr":0,"eq":1,"text":"running"},{"addr":0,"eq":0,"text":"stopped"}]}` |
| R-25 | **Стан джерела й колектора** | Джерело: API-03 `state` як прислав колектор (`online/offline/error`), `last_ok`, `last_error`, `error_count`; `read_enabled=False` → `disabled` незалежно від звіту; відсутнє у звіті джерело (плагіна немає) → `error: "plugin not installed"` (колектор надсилає його з таким текстом). Колектор: `online` при будь-якому API-02/03/05/06; крон: `last_seen < now − 3·status_interval_s` → `offline` + усі його джерела `online/error` → `offline` → сигнали `stale`. Текст `last_error`: маскування `re.sub(r'(?i)(password=\|token=\|bearer\s+)\S+', r'\1***', text)`, далі ≤ 512 | колектор мовчить 3 хв → `offline`, 55 сигналів `stale`, дашборд «Огляд» показує 7 джерел у колонці «Офлайн» |
| R-26 | **Локальні джерела без колектора** (рішення менеджера 14.10.2026 за td_genset Q-20; FR-31, CT-12) | Типи з `td.source._td_local_types()` (базово `[]`; модуль-власник додає значення в `type` через `selection_add` і розширює метод через `super()`; міст `td_genset_factory3d` — `td_genset`) описують дані, які вже є в Odoo. Для них: `collector_id` не обов'язковий (`_check_f3d_collector_required`); `validate_params(type, params, local_types)` перевіряє лише, що `params` — об'єкт JSON без ключів-секретів (A.0); `validate_address` не перевіряє нічого (адреса — будь-яке JSON-значення, напр. рядок-ключ моста); API-01 таких джерел не віддає; крон R-07 і крон R-25 їхніх сигналів не чіпають — `stale` ставить власник через `_mark_stale(reason)`; `_apply_status` не викликається (немає колектора), `state` веде власник; `read_enabled=False` → `disabled` і сигнали `stale` (як для всіх); показання — лише CT-10 `_td_ingest(…, src='module')` (push колектора на такий сигнал → `foreign_signal`); пороги, заявки R-05/R-06, шина R-13, агрегати R-09, ротація R-10 — як для всіх; команди `td.command` — заборонені (R-18) | джерело `GENSET-RELAY` (`type='td_genset'`, без колектора, `params={}`, `module='genset'`) зберігається; сигнал `infra/genset/GENSET/state` на ньому (`period_s=100`, `last_ts` 2 год тому, `ok`) — крон R-07 лишає `ok`; `_td_ingest([{"code": …, "ts": now, "value": 1, "q": "good"}], src='module')` → `accepted=1`; той самий код у `POST push` колектора → `rejected: foreign_signal` |

## 10. Стани й переходи

### 10.1 Сигнал (`td.signal.status`)

```
unknown ──(перше показання q≠bad)──► ok / warn / alarm   (R-04)
ok ◄──► warn ◄──► alarm              (R-04; вгору — з min_duration_s, вниз — з hysteresis)
{ok,warn,alarm} ──(без показань > stale_after | джерело offline/error/disabled)──► stale   (R-07)
stale ──(показання q≠bad)──► ok / warn / alarm
alarm ──(status став alarm ∧ умови R-05)──► заявка створена (maintenance_request_id)
заявка done (R-06) ──► maintenance_request_id = ∅, request_closed_at = now, status перераховано
```

Побічні ефекти: чаттер при кожній зміні `status`; шина при зміні (R-13); `status_since`.

### 10.2 Джерело (`td.source.state`)

`unknown` (створено) → `online` | `offline` | `error` (API-03) → `disabled` (`read_enabled=False`, `write`)
→ `unknown` (`read_enabled=True`); `offline` також із крону колектора (R-25). Перехід у `offline/error/
disabled` → сигнали `stale`. Локальні джерела (R-26): `state` веде модуль-власник (`write` від `sudo`); telemetry змінює
лише `disabled`/`unknown` за `read_enabled`.

### 10.3 Колектор (`td.collector.state`)

`never` → `online` (перший API-виклик) → `offline` (крон) → `online`. Токен відкликано → колектор отримує
`401` і переходить у режим очікування (буфер росте) — в Odoo `offline` через 3 інтервали.

### 10.4 Команда (`td.command.state`)

`queued` → `sent` (API-06) → `done` | `failed` (API-07); `queued|sent` → `expired` (крон); `queued` →
`cancelled` (кнопка). Кінцеві: `done`, `failed`, `expired`, `cancelled`.

### 10.5 Заявка ТО (стандартні стадії `maintenance.stage`)

Створюється на першій стадії (`New Request`); `stage_id.done` → R-06/R-11. Стадії `Repaired`, `Scrap` у
демо — `done=True`.

### 10.6 Міграція рівня 0 (`td.telemetry.level0_migrated.state`)

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
5. **Часові пояси** — R-14; `ts` з майбутнього > 60 с → `ts_future` (годинник пристрою/колектора); «час прийому» (X-83) — лише
   `td.reading.received_at` (Odoo, `_td_ingest`); колектор, якщо пристрій не дав часу, ставить у `ts` час отримання колектором;
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
14. **MQTT без `ts`** або `ts` невалідний — час отримання колектором, `q='uncertain'` лише для `retain`.
15. **BACnet `WriteAccessDenied`/`read_only`** — команда `failed` з текстом; сигнал без змін.
16. **Переглядач без вузла для шляху** — сигнал пропускається (R-12), без помилок у `meta.errors`.

## 12. Acceptance Criteria

Формат: Given / When / Then; тип перевірки: **UT** — `odoo.tests.TransactionCase`; **HT** — `odoo.tests.HttpCase`
(запити через `url_open` до того самого процесу); **CT** — pytest колектора з фейковими серверами; **TC** — стенд
§13.2 (емулятор + колектор + Odoo); **MAN** — ручна перевірка. Фікстури, коди й константи (`T0`, `COL-T`,
`MB-T-U70`, `sig_press`…) — §13.0. У UT/HT коди обладнання в шляхах мають суфікс `-T` (`equipment/FL-C1-T/battery`),
щоб тести проходили й на копії демо, де мігровані сигнали з кодами макета вже є; числа — з макета (джерело — у
правилі R-xx). Час у UT заморожується (`freezegun.freeze_time`), `T0 = 2026-10-14 06:00:00` UTC (= 09:00 Київ).

| ID | FR / правило | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-02, A-02 | Given колектор `COL-T`, користувач `user_admin`; When `action_generate_token()`; Then дія `ir.actions.act_window` на `td.collector.token.wizard` з `target='new'` і `context['default_token']` довжиною ≥ 43; `token_hash == sha256(token).hexdigest()`, `token_hint == token[-4:]`, `token_set_at` заповнено; у чаттері «Видано новий токен (…<hint>)» і **немає** повного токена; `_authenticate(token) == COL-T`; `_authenticate(token + 'x')`, `_authenticate('')`, `_authenticate('a' * 257)` — порожньо. When `active=False` → порожньо. When повторна генерація → старий токен порожньо, новий — `COL-T`. When `action_revoke_token()` → `token_hash=False`, `token_hint=False`, `_authenticate(новий)` порожньо, чаттер «Токен відкликано» | UT |
| AC-02 | FR-02 | Given новий колектор; When `code` ∈ {`COL-MAIN-T`, `C1`, `COL-2-YARD`}; Then збережено зі `state='never'`, `push_interval_s=5`, `push_max=1000`, `status_interval_s=60`, `config_poll_s=60`. When `code` ∈ {`col-main`, `COL_MAIN`, `-COL`, `COL MAIN`, 33 символи}; Then `ValidationError` «Код колектора: великі латинські літери, цифри, дефіс (напр. COL-MAIN).». When другий `COL-MAIN-T` → `IntegrityError`. When `push_max=2001`, `push_interval_s=0`, `push_interval_s=61`, `status_interval_s=9`, `config_poll_s=9` (кожен окремо) → `IntegrityError` (CHECK) | UT |
| AC-03 | FR-02, R-25 | Given `COL-T` `state='online'`, `status_interval_s=60`; його джерела `MB-T-U70` `online`, `MQTT-T` `error`; `sig_press` `status='ok'`; `COL-T2` `online`, `last_seen=now`; When `COL-T.last_seen = now − 181 с` і `td.signal._cron_stale()`; Then `COL-T.state='offline'`, обидва джерела `offline`, `sig_press.status='stale'`; `COL-T2` і `MB-T2` без змін. When `last_seen = now − 179 с`; Then `COL-T` лишається `online` | UT |
| AC-04 | FR-01, CT-03 | Given `user_manager`; When створює по джерелу кожного з 8 типів із параметрами-прикладами Додатка A.2; Then збережено, `state='unknown'`, `read_enabled=True`, `write_enabled=False`. When параметри: `modbus_tcp` без `host`; `port` 0 і 65536; `unit` 0 і 248; `mqtt` `topics=[]`; `mqtt` топік `f3d/#/x`; `mqtt` з ключем `password`; `http_push` `routes=["Lpr"]`; `bacnet_ip` `device=4194303`; `opcua` `endpoint="http://x"`; `rest_vendor` `base_url="ftp://x"`; `params=[1]` (кожен окремо); Then `ValidationError`, текст починається «Параметри джерела <code>:» і містить ім'я ключа (для `password` — «секрети не зберігаються в Odoo — використайте password_ref»). When `code` ∈ {`MB-U70.A`, `HTTP-PUSH-T`} → збережено; `mb-u70` → `ValidationError` «Код джерела: великі латинські літери, цифри, дефіс, крапка.» | UT |
| AC-05 | FR-01, R-07 | Given `MB-T-U70` `state='online'`, `sig_press` `status='ok'`, `COL-T.config_etag='x'`; When `user_manager` пише `read_enabled=False`; Then `state='disabled'`, `sig_press.status='stale'`, чаттер сигналу «Немає даних: disabled», `COL-T.config_etag=False`; `_apply_status({"code": "MB-T-U70", "state": "online"})` лишає `disabled`. When `read_enabled=True`; Then `state='unknown'`, сигнал лишається `stale` до першого показання | UT |
| AC-06 | FR-01, FR-29, D-07 | Given `BAC-T-200` (`params.read_only=true`) і `sig_fire` на ньому; When `write_enabled=True` на джерелі; Then `ValidationError` «Джерело лише для читання (пожежна панель): запис заборонено.». When `sig_fire.write_enabled=True`; Then `ValidationError` «Запис у пожежну панель заборонено (D-07).». When `MB-T-U70.type='mqtt'` (є сигнали); Then `ValidationError` «Тип джерела з сигналами змінити не можна — створіть нове джерело.»; джерело без сигналів змінює тип разом із валідними `params` нового типу | UT |
| AC-07 | FR-08, R-25 | Given `BAC-T-105` `online`, `sig_rv` `ok`; When `_apply_status({"code": "BAC-T-105", "state": "error", "last_ok": "2026-10-14T05:50:10Z", "error": "Who-Is: device 105 not found; url=http://u:password=Secr3t@x token=abc Bearer xyz", "stats": {"polls": 120, "errors": 60}})`; Then `state='error'`, `last_ok=2026-10-14 05:50:10`, `last_error` не містить `Secr3t`, `abc`, `xyz` і містить `password=***`, `token=***`, `Bearer ***`; `error_count=60`, `stats` збережено як є; `sig_rv.status='stale'`. When `error` довжиною 600; Then `len(last_error) == 512` | UT |
| AC-08 | FR-03, R-01 | Given `user_manager`; When `code` ∈ {`equipment/FL-C1-T/battery`, `ventilation/units/RV-05-T/filter_dp_pa`, `infra/WATER-T/m3_total`, `energy/consumers/SAW-T/p_now`} (нові); Then збережено. When `code` ∈ {`Equipment/FL-T/x`, `equipment`, `energy//x`, `equipment/FL T/x`, `equipment/FL-T/`, `equipment/FL-T/x;DROP TABLE td_signal`, `equipment/FL-T/x'--`, 129 символів}; Then `ValidationError`, текст починається «Код сигналу»; таблиця `td_signal` існує й кількість рядків не змінилась. When дубль коду → `IntegrityError` | UT |
| AC-09 | FR-03, CT-03, A-01 | Given сигнал на `MB-T-U70`; When `address={"fc": 3, "addr": 3001, "type": "u16", "scale": 0.001}`; Then збережено. When `fc=7`; `addr=-1`; `addr=65536`; `type="u128"`; `wordorder="middle"`; `count=0`; `agg="median"`; `states=[{"addr": 0, "eq": 1}]` (без `text`); `write={"fc": 5, "addr": 16, "pulse_ms": 99}` і `pulse_ms: 10001`; `write={"fc": 16, "addr": 16, "pulse_ms": 1500}` — кожен окремо; Then `ValidationError` «Адреса сигналу <code>: <ключ>: …». When `write={"fc": 5, "addr": 16, "pulse_ms": 1500}` (X-46) → збережено; `write={"fc": 5, "addr": 20}` без `pulse_ms` (рівневий запис, X-81) → збережено. Given сигнал на `MQTT-T`: `path="$.battery_pct"` → ок; `path` ∈ {`$.a;drop`, `battery_pct`, `$..x`} або `topic="f3d/mobile/+/telemetry"` → помилка. Given `BAC-T-105`: `{"object": "AI", "instance": 4}`, `{"object": "analog-input", "instance": 4}`, `{"object": "PIV", "instance": 1}` і `{"object": "positive-integer-value", "instance": 1}` (X-37) → ок; `object="XX"`, `instance=4194303`, `priority=0`, `priority=17` → помилка. Given `HTTP-T`: `route="Lpr"`, `match=[1]` → помилка. When сигнал без `source_id` з `address={"any": 1}` → збережено без перевірки. When `address=[1, 2]` → «адреса має бути об'єктом JSON». When `address_text="{bad"` → `ValidationError` | UT |
| AC-10 | FR-03 | Given новий сигнал `gauge`; When `warn_low_on=alarm_low_on=True`, `warn_low=15`, `alarm_low=20`; Then `ValidationError` з текстом M-03 `«Тривога, нижче» має бути ≤ «Увага, нижче».`. When `warn_high=245`, `alarm_high=240` (обидва `_on`) → помилка; `alarm_low=10`, `alarm_high=10` → помилка; `kind='state'` з `alarm_high_on=True` → «Для стану задайте «Стани-тривоги», а не числові пороги.»; `derive_rule='rate_h'` без `derived_from_id` або з `derived_from_id=sig_press` (gauge) → «Похідна «за годину» потребує лічильника-джерела.». When `period_s=0` або `hysteresis=-1` → `IntegrityError`. When параметр `default_store_period_s='120'` і новий сигнал → `store_period_s == 120` | UT |
| AC-11 | FR-03, R-04, R-16 | Given `sig_rv` `last_value=285`, `status='alarm'`, `alarm_high=250`, відкрита заявка; When `user_manager` пише `alarm_high=300`; Then `status='ok'` одразу (без `min_duration_s`), `status_since=now`, повідомлення в чаттері сигналу з «Стан:», заявка лишається відкритою. When `period_s=20`; Then `COL-T.config_etag=False`. When змінено лише `name`; Then `config_etag` незмінний | UT |
| AC-12 | FR-03, FR-13 | Given `sig_hours` — лічильник ТО на `eq_comp`; When `sig_hours.unlink()`; Then `UserError` «Сигнал використовується для ТО за лічильником на Компресорна станція.». Given сигнал без ТО з 3 показаннями і 1 агрегатом; When `unlink()`; Then показання й агрегати видалені (каскад) | UT |
| AC-13 | FR-04, R-03, A-04 | Given `sig_press` (`store_period_s=300`, `min_duration_s=0`, `alarm_low=6.0`); When одним `_td_ingest` 360 показань `6.80` з кроком 10 с від `T0`; Then `last_value=6.80`, `last_ts=T0+3590 с`, у `td.reading` сигналу рівно 12 рядків із `ts = T0 + k·300 с` (k = 0…11), `last_stored_ts=T0+3300 с`. When далі `5.9` о `T0+3600 с` → записано (зміна статусу на `alarm`); `5.85` о `T0+3610 с` → не записано, `last_value=5.85`. When `q='bad'` `7.5` о `T0+3620 с` → `last_value` лишається 5.85, рядок `quality='bad'` записано; другий `bad` о `T0+3630 с` → не записано (правило (г) рахується від останнього збереженого `bad`). When `store_period_s=0` і 10 показань → 10 рядків | UT |
| AC-14 | FR-04, FR-07, R-17 | Given 4 показання різних сигналів з `ts=T0`: `sig_press` 6.772, `sig_bat` 23.6, `sig_flstate` `busy`, `sig_water` 18642.37; When `_td_ingest` двічі тим самим списком; Then 1-й: `accepted=4`, `stored=4`, `duplicates=0`, `changed_codes` — 4 коди; 2-й: `accepted=4`, `stored=0`, `duplicates=4`, `changed_codes=[]`, у `td.reading` 4 рядки, `last_*` незмінні, нових повідомлень чаттера немає. When далі `sig_press` `ts=T0−600 с` `6.5`; Then рядок у `td.reading` є, `last_value=6.772`, `last_ts=T0` | UT |
| AC-15 | R-17 п. 7 | Given `sig_press` `last_ts=T0+100 с`, `last_value=6.9`, `status='ok'` (встановлено SQL, як після push іншого воркера); When `_td_ingest([{code, ts: T0+50 с, value: 5.0}])`; Then `last_value=6.9`, `last_ts=T0+100 с`, `status='ok'` (пороги не переоцінено, заявки немає), рядок `ts=T0+50 с` записано | UT |
| AC-16 | FR-04 | Given показання `sig_press`; When `user_manager` пише `value`; Then `UserError` «Показання не редагуються.»; When `user_admin` пише `quality='bad'` → дозволено. When ORM `create` показання з тим самим `(signal_id, ts)` → `IntegrityError` | UT |
| AC-17 | FR-05, R-09 | Given `freeze_time('2026-10-14 11:20')`; показання створені `td.reading.create` (не через Ingester): `sig_rv` 12 показань у 10:00…10:55 (крок 5 хв) зі значеннями 280, 282, 284, 286, 288, 290, 290, 288, 286, 284, 282, 280 і одне `quality='bad'` 999 о 10:57; `sig_hours` 17846.6 о 10:05 і 17847.6 о 10:55; When `td.reading.hour._cron_aggregate()`; Then для `sig_rv` один рядок `hour=2026-10-14 10:00`: `v_min=280`, `v_max=290`, `v_avg=285`, `v_count=12`, `v_first=280`, `v_last=280`, `delta=0`; для `sig_hours` `v_first=17846.6`, `v_last=17847.6`, `delta=1.0` (±1e-6). When повторний прогін → рядків стільки ж, значення ті самі. When о 11:30 створено показання `sig_rv` 295 з `ts` 10:58 і прогін → `v_max=295`, `v_count=13`. Година 11:00 (незакрита) не агрегується. When (X-07) `freeze_time('2026-10-14 14:20')`, `sig_hours` 17847.9 о 11:05 і 17848.4 о 11:50, о 12:xx показань немає, 17849.0 о 13:30, і прогін; Then `sig_hours` 11:00: `v_first=17847.9`, `v_last=17848.4`, `delta=0.8` (= 17848.4 − 17847.6, не 0.5); 12:00 — рядка немає; 13:00: `delta=0.6` (від `v_last` 11:00); сума `delta` 10:00…13:00 = 2.4 = 17849.0 − 17846.6. Given новий сигнал `equipment/GANTRY-T/cycles_today` (`counter`, `src_mb`, `{"fc": 3, "addr": 2}`, `sim_params={"reset": "daily"}`) з показаннями 370 о 2026-10-13 23:50, 2 о 2026-10-14 00:10 і 5 о 00:40; When прогін; Then година 2026-10-13 23:00 — `delta=0` (перша година ряду, одне показання), година 2026-10-14 00:00 — `delta=3` (`v_last < v_prev` → `v_last − v_first`) | UT |
| AC-18 | FR-04, FR-05, R-10 | Given `freeze_time('2026-11-14 02:40')`, `keep_days=30`, `keep_hours_days=400`; показання `sig_press` з `ts` 2026-10-14 01:00 (31 доба) і 2026-10-16 01:00 (29 діб); агрегати з `hour` = now − 401 доба і now − 399 діб; `td.push.event` з `ts` now − 31 доба; When `td.reading._cron_rotate()`; Then старі показання, агрегат і подія видалені, молодші — лишились. When константа батча `ROTATE_BATCH` підмінена на 2 і старих показань 5; Then видалено всі 5 за один прогін (цикл батчів) | UT |
| AC-19 | R-08 | Given `sig_hours` (`counter`) `last_value=17846.6`; When 17846.8 → `last_quality='good'`; When 17000.0 → `last_value=17000.0`, `last_quality='uncertain'`, чаттер сигналу містить «Лічильник зменшився» (не частіше 1 разу за добу: друге зменшення того ж дня — без нового повідомлення). Given лічильник з `sim_params={"reset": "daily"}` 373 → 2 → `good`. Given `sig_water` і `sig_flow` (`rate_h`); When `sig_water` 18642.00 о `T0` і 18642.35 о `T0+600 с`; Then для `sig_flow` одне показання `ts=T0+600 с`, `value=2.1` (±1e-6), `src='collector'`, `sig_flow.last_value=2.1`; на першому показанні похідного немає | UT |
| AC-20 | R-14 | Given `freeze_time('2026-10-14 06:10:10')`; When `_td_ingest` з `ts` ∈ {`2026-10-14T06:10:03.250+03:00`, `2026-10-14T06:10:03`, `2026-10-14T06:11:30Z`, `2026-10-14T06:11:00Z`, `2026-09-13T06:00:00Z`, `2026-13-01T00:00:00Z`}; Then 1-ше прийнято з `ts = 2026-10-14 03:10:03.250` UTC; 2-ге — `rejected` `ts_no_tz`; 3-тє — `ts_future`; 4-те прийнято; 5-те — `ts_too_old`; 6-те — `ts_invalid` (поле `i` — індекс у пакеті). Заявка, створена показанням `sig_rv` 285 з `ts` `2026-10-14T06:10:00Z`, має в `description` «14.10.2026 09:10» (Київ) | UT |
| AC-21 | CT-10, FR-07 | Given `sig_free` (без джерела) і `sig_press`; When `env['td.signal']._td_ingest([...], src='module')` 100 разів поспіль; Then без `429`/ліміту частоти, показання з `src='module'`, `foreign_signal` не перевіряється; `unknown_code` відхиляється так само; поріг `sig_press` 5.9 створює заявку | UT |
| AC-22 | FR-09, R-04 | Given `sig_rv` `alarm_high=250`, `hysteresis=10`, `min_duration_s=0`, інші пороги вимкнені; When послідовно 250, 285, 248, 240.5, 239; Then `ok`, `alarm`, `alarm`, `alarm`, `ok`. Чиста функція `tools.thresholds.eval_status` на тих самих входах дає ті самі статуси | UT |
| AC-23 | FR-09, R-04 | Given `sig_bat` `warn_low=25`, `alarm_low=15`, `hysteresis=0`; When 26, 23.6, 14.2, 16, 26; Then `ok`, `warn`, `alarm`, `warn`, `ok` | UT |
| AC-24 | FR-09, R-04 | Given `freeze_time('2026-10-14 10:02')`, `sig_press` `alarm_low=6.0`, `hysteresis=0.1`, `min_duration_s=30`, часи — UTC того ж дня; When 5.9 о 10:00:00; Then `status='ok'`, `breach_since=10:00:00`, заявки немає. When 5.95 о 10:00:30; Then `alarm`, заявка створена. When 6.05 о 10:00:40 → `alarm`; 6.11 о 10:00:50 → `ok`, `breach_since=False`. When 5.9 о 10:01:00, 6.2 о 10:01:10, 5.9 о 10:01:20, 5.9 о 10:01:45; Then `ok` на всіх (порушення переривалось, `breach_since=10:01:20`, 25 с < 30) | UT |
| AC-25 | FR-09, R-04 | Given `sig_cstate` (`kind='state'`, `alarm_states=["fault"]`); When `text` `fault`; Then `alarm`, заявка «Компресор: стан «fault»»; When `loaded` → `ok`. Given сигнал `kind='event'` → після будь-якого показання `ok`. When показання `q='bad'` → `status` не змінюється. When `text="boost"` поза `states` → прийнято, `last_quality='bad'`, `value=-1`, `rejected[].reason='unknown_state'` | UT |
| AC-26 | FR-12, R-07 | Given `freeze_time`, `stale_periods=3`, `stale_min_s=60`; `sig_press` (`period_s=10`, `last_ts=now−61 с`, `ok`), `sig_bat` (`period_s=5`, `last_ts=now−59 с`), `sig_water` (`period_s=60`, `last_ts=now−179 с`), `sig_free` (без джерела, `last_ts=now−1 доба`), `sig_rv` (`alarm` з відкритою заявкою, `last_ts=now−61 с`, `period_s=10`); When `_cron_stale()`; Then `sig_press`, `sig_rv` — `stale` (чаттер «Немає даних: timeout», `sig_rv.maintenance_request_id` не змінено, нових заявок 0); `sig_bat`, `sig_water`, `sig_free` — без змін. When `sig_press` отримує 6.8; Then `ok`. When `stale_min_s=30`, `stale_periods=5` → для `period_s=10` межа 50 с | UT |
| AC-27 | FR-10, R-05, §6.8 каркаса | Given `sig_rv` (обладнання `eq_rv` з командою `team_mech`, `alarm_high=250`, `decimals=0`, `alarm_title="Заміна фільтрів: перепад тиску {value} Па при нормі до {threshold}"`); When показання 285.2 о `T0`; Then одна `maintenance.request`: `name` «Заміна фільтрів: перепад тиску 285 Па при нормі до 250», `equipment_id=eq_rv`, `maintenance_type='corrective'`, `maintenance_team_id=team_mech`, `priority='2'`, `stage_id` — перша стадія (`done=False`, найменший `sequence`), `td_signal_id=sig_rv`, `td_equipment_code='RV-05-T'`, `td_origin='threshold'`, `td_value=285.2`, `td_threshold=250`, `request_date` = сьогодні; `description` містить `ventilation/units/RV-05-T/filter_dp_pa`, `BAC-T-105`, «14.10.2026 09:00»; `sig_rv.maintenance_request_id` = заявка; `_td_ingest` повертає `alarms_opened=1`. Given обладнання `eq_other` без команди → `maintenance_team_id` = параметр `default_team_id` | UT |
| AC-28 | R-05, A-21 | Given `render_title`/`fmt_num` (`tools/titles.py`); Then `sig_bat` 14.2 (`decimals=1`, `alarm_title="Зарядити АКБ: заряд {value} % при нормі від {threshold}"`) → «Зарядити АКБ: заряд 14,2 % при нормі від 15»; `sig_press` 5.9 (`decimals=2`, `alarm_title="{equipment}: тиск {value} бар при нормі від {threshold}"`, обладнання «Компресорна станція») → «Компресорна станція: тиск 5,9 бар при нормі від 6»; FA-FAC 92 (`decimals=0`, `alarm_title="Очистити сповіщувач: запиленість {value} % при нормі до {threshold}"`) → «Очистити сповіщувач: запиленість 92 % при нормі до 90»; порожній `alarm_title`, `name="Тиск на виході"`, 5.9 бар, поріг 6.0 нижній → «Тиск на виході: 5,9 бар при нормі від 6 бар»; `kind='state'`, `name="Компресор"`, порожній шаблон, `fault` → «Компресор: стан «fault»»; шаблон із `{foo}` → `{foo}` лишається буквально; результат > 256 символів обрізається до 256. `fmt_num`: (17900.2, 0) → «17 900», (18000, 0) → «18 000», (29761.2, 1) → «29 761,2», (-71.9, 1) → «-71,9», (6.0, 2) → «6», (0.0005, 2) → «0» | UT |
| AC-29 | FR-10, R-05 | Given `sig_rv` з відкритою заявкою; When 300, 260, 300 (утримання `alarm`), потім 239 (`ok`) і знову 285 (перехід у `alarm`); Then заявок на `sig_rv` усього 1. Given сигнал з порогом без `equipment_id`; When тривога → заявки немає, чаттер «Тривога без обладнання — заявку не створено». Given `create_request=False` → `status='alarm'`, заявки немає | UT |
| AC-30 | FR-11, R-06 | Given `sig_rv` з відкритою заявкою, останнє показання 120 (`status='ok'`); When заявку переведено в стадію з `done=True`; Then `maintenance_request_id=False`, `request_closed_at=now`, `status='ok'`, чаттер сигналу «Заявку <name> закрито; стан: Норма». Given останнє 300 (`alarm`); When закрито о `T0`; Then `status='alarm'`, чаттер містить «Тривога триває, нова заявка не раніше 14.10.2026 10:00»; показання 300 о `T0+1800 с` → нової заявки немає; о `T0+3601 с` → створено 2-гу заявку (без переходу статусу) | UT |
| AC-31 | FR-11, R-06 | Given закрита заявка `sig_rv`, сигнал без відкритої; When заявку повернуто на стадію з `done=False`; Then `sig_rv.maintenance_request_id` = ця заявка. When відкриту заявку видалено (`user_admin`, `unlink`); Then `maintenance_request_id=False`, `request_closed_at=now` | UT |
| AC-32 | FR-13, R-11 | Given `eq_comp`: `td_meter_signal_id=sig_hours`, `td_meter_interval=2000`, `td_meter_last_value=16000`, `td_meter_lead_pct=5`; `sig_hours.last_value=17846.6`; Then `td_meter_next_value=18000`, `td_meter_remaining=153.4`, заявки немає. When показання 17900.2; Then заявка: `name` «ТО за лічильником: COMPRESSOR-T — 18 000 год (зараз 17 900)», `maintenance_type='preventive'`, `priority='1'`, `td_origin='meter'`, `td_signal_id=sig_hours`, `td_value=17900.2`, `td_threshold=18000`, `maintenance_team_id=team_mech`; `eq_comp.td_meter_request_id` = заявка. When 17901 → другої немає. Given `eq_fl2` (`interval=1000`, `last=3000`) і показання 4000.5 → заявка з `priority='3'` | UT |
| AC-33 | FR-13, R-11 | Given заявка AC-32 відкрита, `sig_hours.last_value=17905.0`; When заявку закрито; Then `td_meter_last_value=17905.0`, `td_meter_last_date` = сьогодні (Київ), `td_meter_request_id=False`, `td_meter_next_value=19905.0`, чаттер обладнання містить «ТО за лічильником виконано при 17 905» | UT |
| AC-34 | FR-13, R-11 | When `eq_comp.td_meter_signal_id=sig_hours` без інтервалу або `td_meter_interval=0`; Then `ValidationError` «Задайте інтервал ТО за лічильником (> 0).». When лічильник `eq_fl2` призначено на `eq_comp` → «Лічильник належить іншому обладнанню.». Given агрегати `sig_hours` за 7 діб із сумарною `delta=59.5`; When заявка R-11 при 17900.2; Then `schedule_date = now + 11.74 доби` (±0.05 доби). Без агрегатів → `schedule_date = now` (±1 хв). Given `eq_fl2` `last=3000`, `interval=1000`, `sig_fl2_hours.last_value=3216.5` → `td_meter_remaining=783.5` | UT |
| AC-35 | FR-06, API-01 | Given `COL-T` з токеном, джерела `MB-T-U70`, `MQTT-T`, `BAC-T-105`, `BAC-T-200`, `HTTP-T`, `MB-T-U84` (`COL-T`), архівне `MB-T-OLD` (`COL-T`) і `MB-T2` (`COL-T2`); When `GET /f3d/telemetry/config` з `Authorization: Bearer <token>`; Then `200`, `Content-Type: application/json`, `Cache-Control: private, max-age=0`; ключі верхнього рівня — точно схема §7 API-01; у `sources` — 6 активних джерел `COL-T` (без `MB-T-OLD` і `MB-T2`); `sig_flow` (без джерела) і сигнал з порожньою адресою відсутні; `MQTT-T.params` містить `password_ref`, а ключів `password`/`token` немає ніде в тілі; заголовок `ETag` == `"` + `body.etag` + `"`. When `MB-T-U70.read_enabled=False` → джерело в списку з `read_enabled: false`. When параметр `read_enabled=False` → `body.read_enabled=false` і в усіх джерел `read_enabled: false` | HT |
| AC-36 | FR-06, R-16 | Given попередній `etag`; When два поспіль `GET config`; Then `etag` однакові. When `If-None-Match: "<etag>"`; Then `304`, тіло порожнє. When `sig_press.period_s=20`; Then `GET` → `200` з новим `etag`; `POST push` (будь-яке валідне показання) повертає `config_etag` == новий `etag` | HT |
| AC-37 | FR-20, API-01…API-07 | Given 7 ендпоінтів; When без `Authorization`, з `Bearer wrong`, з відкликаним токеном; Then `401 {"error": {"code": "unauthorized", "message": "Невірний токен колектора"}}` для config/push/status/event/commands/commands_result; тіло відповіді не містить надісланого токена. When `COL-T.active=False` → `403 forbidden`. `GET /f3d/telemetry/health` у всіх трьох випадках → `200` з мінімальним тілом (AC-42) | HT |
| AC-38 | FR-07, API-02 | Given свіжі `ts` (now − 5 с); When `POST /f3d/telemetry/push` з 4 показаннями (`sig_press` 6.772 `q=good`, `sig_bat` 23.6 з `+03:00`, `sig_flstate` `text=busy`, `sig_water` 18642.37); Then `200`: `accepted=4`, `rejected=[]`, `stored=4`, `duplicates=0`, `changed` — 4 коди, `alarms_opened=0`, `config_etag` — 64 hex, `read_enabled=true`, `server_time` закінчується на `Z`; `sig_press.last_value=6.772`, `sig_bat.status='warn'`, `sig_flstate.last_text='busy'`; `COL-T.last_push_at`, `last_seen` оновлені, `state='online'` | HT |
| AC-39 | FR-07, API-02 | When тіло не JSON → `400 bad_json`; `readings` не список → `400 bad_schema`; 2 001 показання → `413 too_many_readings`; тіло > 1 МБ → `413 payload_too_large`; `"collector": "COL-T2"` з токеном `COL-T` → `403 collector_mismatch`. When пакет з 12 елементів, де по одному: невідомий код, сигнал `COL-T2`, архівний сигнал, `Equipment/X`, `ts` без зони, `ts="abc"`, `ts` +5 хв, `ts` −31 доба, `value="abc"`, `value=NaN`, `text` 65 символів, без `value` і `text`; Then `200`, `accepted=0`, `rejected[].reason` відповідно: `unknown_code`, `foreign_signal`, `inactive`, `bad_code_format`, `ts_no_tz`, `ts_invalid`, `ts_future`, `ts_too_old`, `value_invalid`, `value_invalid`, `text_too_long`, `missing_value`, `rejected[].i` = 0…11 | HT |
| AC-40 | FR-07, R-17 | Given пакет AC-38 прийнято; When той самий пакет удруге; Then `200`, `stored=0`, `duplicates=4`, `changed=[]`, `last_*` незмінні, кількість `td.reading` незмінна | HT |
| AC-41 | FR-07, FR-19, R-17 | When параметр `td.telemetry.read_enabled='False'`; Then `POST push` → `423 {"error": {"code": "read_disabled", …}}`, жодного показання й зміни `last_*`; `POST event` → `423`. Given `push_rate_per_min='3'`; When 4 push за < 60 с; Then 4-й → `429 rate_limited` із заголовком `Retry-After: 10`; When рядки `td_collector_push` колектора `COL-T` старші 60 с (SQL: `UPDATE td_collector_push SET ts = ts − interval '61 seconds' WHERE collector_id = COL-T.id`) → наступний `200` | HT |
| AC-42 | FR-08, API-03, API-04 | When `POST /f3d/telemetry/status` з тілом-прикладом §7 API-03 (коди `MB-T-U70` `online`, `MQTT-T` `online`, `BAC-T-105` `error`, плюс `NOPE` і `MB-T2`); Then `200 {"ok": true, "config_etag", "read_enabled", "write_enabled", "server_time", "rejected": ["NOPE", "MB-T2"]}`; `COL-T.version='0.1.0'`, `uptime_s=86412`, `buffer_rows=0`, `buffer_dropped=0`, `plugins` збережено; `BAC-T-105.state='error'`, `last_error` маскований (R-25). When `sources` не список → `400 bad_schema`. When `GET /f3d/telemetry/health` без токена або з невірним; Then `200`, ключі рівно {`ok`, `module`, `version`, `server_time`}, `version='19.0.1.1.0'`. With валідним токеном → додатково `collector` {`code`, `state`, `last_seen`} і `counts` {`signals`, `alarms`, `stale`, `sources_online`}, значення дорівнюють `search_count` у базі | HT |
| AC-43 | FR-22, API-05 | Given `HTTP-T` (`routes=["lpr"]`), `sig_plate` (`address={"route": "lpr", "match": {"sensorProviderID": "CAM-05"}, "path": "$.plateText", "ts_path": "$.capture_timestamp"}`); When `POST /f3d/telemetry/event` з однією подією (тіло Axis з §7 API-05, `capture_timestamp` = now − 2 с у мс); Then `200 {"accepted": 1, "rejected": [], "handled": {}}`; `td.push.event` з `route='lpr'`, `remote`, `payload`, `signal_count=1`; `sig_plate.last_text='AA4512KT'`. When та сама подія вдруге → `accepted=0`, `rejected=[{"event_id": …, "reason": "duplicate"}]`. When `route="Lpr"` або `payload` — список → `400 bad_schema`; 101 подія → `413`; параметр `read_enabled=False` → `423` | HT |
| AC-44 | FR-21, API-06 | Given `sig_valve` (`write_enabled=True`) на `BAC-T-105` (`write_enabled=True`); команди: A (`queued`, `COL-T`), B (`queued`, сигнал на `MB-T2` — `COL-T2`), C (`queued`, `expires_at` у минулому); When параметр `write_enabled=False` і `GET /f3d/telemetry/commands`; Then `{"commands": [], "write_enabled": false}`, A лишається `queued`. When `write_enabled=True`; Then повертається лише A з `address` сигналу, A → `sent`, `sent_at` заповнено; повторний `GET` → `[]`; `?limit=1` обмежує | HT |
| AC-45 | FR-21, API-07 | Given A `sent`, D `sent`; When `POST /f3d/telemetry/commands/result` з `[{id: A, state: done, result: "written 80.0 @prio 8"}, {id: D, state: failed, error: "WriteAccessDenied"}]`; Then `200 {"accepted": 2, "rejected": []}`, A `done` з `done_at`, `result`, чаттер «Виконано: written 80.0 @prio 8»; D `failed`, `error`. When той самий запит удруге → `accepted=0`, `rejected` з `reason='already_done'` для обох. When результат для `queued` → `not_sent`; для неіснуючого id або команди `COL-T2` → `not_found`. When `results` не список → `400 bad_schema` | HT |
| AC-46 | FR-07, API-02 | Given 1 000 показань для 55 сигналів (`ts` різні); When `POST push`; Then відповідь ≤ 1 с (середнє з 5 прогонів на тестовій базі). Кількість SQL-запитів обробки (лічильник `cr.sql_log_count`) для 1 000 і для 100 показань тих самих 55 сигналів при незмінних статусах відрізняється ≤ 5 (немає N+1) | HT |
| AC-47 | FR-21, R-18 | Given `sig_valve`, `BAC-T-105`, параметр `write_enabled`; When `user_manager` створює `td.command(value=80)` при: параметр `False` → `UserError` «Запис у пристрій вимкнено: параметр модуля.»; джерело `write_enabled=False` → «… джерело BAC-T-105.»; сигнал `write_enabled=False` → «… сигнал ventilation/units/RV-05-T/heating_valve.» (перевірки саме в цьому порядку); усі `True` → `state='queued'`, `requested_by=user_manager`, `expires_at = requested_at + 10 хв`. When `user_reader` → `AccessError`. Given `sig_fire` і `BAC-T-200` з `write_enabled=True`, виставленими SQL в обхід перевірок; When команда → `UserError` «Джерело лише для читання.» | UT |
| AC-48 | FR-21, R-18 | Given команда `queued`; When `action_cancel()` → `cancelled`; для `sent` → `UserError` «Скасувати можна лише команду в черзі.». Given `queued` і `sent` з `expires_at = now − 1 с`; When `_cron_expire()`; Then обидві `expired`, чаттер «Колектор не забрав команду». Given сигнал `kind='state'`, `states=["VE", "VEL", "AQ", "REC", "EA", "SA", "ST", "Off"]`; When команда `text='VEL'`; Then `value=1.0` | UT |
| AC-49 | FR-22, CT-08, R-22 | Given `freeze_time('2026-10-14 05:15:10')`, `F3dPushHandler._td_handler_models` підмінено на `['td.push.handler']`, `_td_handle_push` — `Mock`; When `env['td.push.event']._td_receive([подія lpr з CAM-05], COL-T)`; Then обробник викликано 1 раз з `route='lpr'` і `event` з ключами `event_id`, `route`, `ts` (datetime UTC naive), `remote`, `headers`, `payload`; `handled_by='td.push.handler'`; `sig_plate` отримав показання `text='AA4512KT'` з `ts` = `capture_timestamp` (епоха мс → UTC: `1791954905507` → `2026-10-14 05:15:05.507`) і `received_at = 2026-10-14 05:15:10` (час прийому в Odoo, X-83). When подія з `sensorProviderID='CAM-06'` → показання немає, `signal_count=0` | UT |
| AC-50 | R-22 | Given `_td_handler_models` → `['td.push.handler', 'td.push.handler']`, `_td_handle_push` з `side_effect=[ValueError('boom'), None]`; When `_td_receive`; Then другий виклик відбувся; `td.push.event.error` містить `ValueError: boom`; подія і показання `sig_plate` збережені (транзакція не відкочена) | UT |
| AC-51 | FR-30, R-24 | Given `tools.sim_catalog.parse_sim_address`; Then шість прикладів R-24 дають рівно наведені `dict`; `("modbus", "Modbus u61 HR 32080–32081")` з типом `I32`, масштабом `×0,001` → `{"unit": 61, "fc": 3, "addr": 32080, "count": 2, "type": "i32", "scale": 0.001, "doc": "HR 32080–32081"}` (Huawei — PDU як у документі, X-42); `"Modbus u72 (TEDOM) HR 40000"` + `U16` → `"addr": 40000`; `"Modbus u1 (PM5560) HR 3060–3061"` + `F32` → `"addr": 3059`; PDU-нотація `"Modbus u61 fc3 pdu32080+2"` + `I32` → `{"unit": 61, "fc": 3, "addr": 32080, "count": 2, "type": "i32", …}`; `"Modbus u99 HR 100"` → `None`; `"BACnet dev 200 PIV:3 Present_Value (запиленість)"` → `{"device": 200, "object": "positive-integer-value", "instance": 3, "property": "present-value"}` (X-37); `("opcua", "ns=2;s=SAW-1.State.Machine.Flags.Alarm (+ Error, Warning)")` → `{"nodeid": "ns=2;s=SAW-1.State.Machine.Flags.Alarm"}`; `"HTTP POST <collector>/f3d/lpr → plateText, plateCountry, carState, datetime (камера GATE-W)"` → `{"route": "lpr", "path": "$.plateText"}`; `"SICS TCP :4001 «SI» → «S S  21380 kg» / «SIR» потік"` → `{"cmd": "SI", "field": "weight"}`; `"SICS TCP :4001 «SI» → stable (S S / S D)"` → `{"cmd": "SI", "field": "stable"}` (X-45); `"GET /api/v1/status → $.vacuum_kpa"` → `{"method": "GET", "path": "/api/v1/status", "json_path": "$.vacuum_kpa"}`; `"Σ Modbus u61…u68 HR 32080–32081"`, `"похідна m3_total за 5 хв"` → `None` | UT |
| AC-52 | FR-30, CT-11 | Given рядки каталогу (dict з полями iot_sim M-03): новий `equipment/COMPRESSOR-T/temp_c` (`Modbus u70 HR 3003`, `U16`, `×0,1`), наявний `sig_press` з `source_id` і `last_value=6.8`, рядок `Σ Modbus …`, рядок з кодом `Bad/Code`; When `_td_import_sim_rows(rows, source_map={"u70": "MB-T-U70"}, defaults={})`; Then `{"created": 1, "updated": 1, "unparsed": ["…Σ…"], "skipped": ["Bad/Code"]}`; новий сигнал: `origin='catalog'`, `source_id=MB-T-U70`, `address={"unit": 70, "fc": 3, "addr": 3002, "type": "u16", "scale": 0.1, …}`; у `sig_press` `source_id` і `last_value` не змінилися. When `_td_import_sim_catalog()` без моделі `td.sim.signal` → `{"created": 0, "updated": 0, "unparsed": [], "skipped": [], "state": "skipped"}` | UT |
| AC-53 | FR-18, R-15, Додаток D | Given `make_level0` (§13.0): 7 сигналів рівня 0 — `ventilation/units/RV-05-T/filter_dp_pa` (`drift`, `above` 250, «тривога», 320.594, заявка A), `fire/groups/FA-T/dust` (`drift`, `above` 90, 89.304, заявка B), `equipment/FL-T/battery` (`drain`, 49.556, `x_charging=True`), `equipment/FL-T/hours` (`hours`), `equipment/COMPRESSOR-T/pressure_bar` (`noise`, `below` 6.0, `x_kind="Тиск"`), `energy/consumers/SAW-T/p_now` (`machine`), `energy/consumers/SAW-T/kwh_shift` (`energy`, `x_source_id` → p_now); 30 показань + 1 з `x_time=NULL`; крон/меню/представлення з xml-id `td_iot_sim.*`; `with_catalog_rows` з рядком `equipment/FL-T/state` (`new=1`); When `hooks.run_migration(env)`; Then звіт: `signals_migrated=7`, `readings_migrated=30`, `skipped_null_ts=1`, `requests_linked=2`, `mismatches=[]`, `state='done'`, `by_module={"bms": 1, "fire_safety": 1, "telemetry": 3, "energy": 2}`; RV-05-T: `module='bms'`, `kind='gauge'`, `alarm_high=250`, `alarm_high_on=True`, `hysteresis=5`, `decimals=0`, `alarm_title` «Заміна фільтрів: перепад тиску {value} {unit} при нормі до {threshold}», `status='alarm'`, `last_value=320.594`, `maintenance_request_id=A`, `origin='sim_data'`, `sim_mode='drift'`; FA-T: `hysteresis=1.8`; FL-T/hours: `kind='counter'`, `decimals=1`; COMPRESSOR-T: `alarm_low=6.0`, `decimals=2`; kwh_shift: `module='energy'`, `kind='counter'`, `derived_from_id` = p_now; `equipment/FL-T/state.last_text='charging'`; xml-id `td_telemetry.sig_ventilation_units_rv_05_t_filter_dp_pa` існує; показання `src='sim_data'`, `quality='good'`, `received_at` = `create_date` записів `x_f3d_reading` (X-83); заявки A, B мають `td_signal_id`, `td_origin='threshold'`; крон `active=False`, усі 7 `x_active=False`, меню `menu_iot_root` і представлення `view_equipment_form_signals` `active=False` | UT |
| AC-54 | FR-18 | Given міграцію AC-53 виконано; When `run_migration` удруге; Then `created=0`, кількість `td.signal`/`td.reading` незмінна, `mismatches=[]`, `state='done'`. Given свіжий рівень 0 і `hooks.readings_level0` підмінено так, що пропускає 1 рядок; When `run_migration`; Then `state='partial'`, `mismatches` містить рядок про кількість показань, крон рівня 0 лишається `active=True`, `x_active=True` | UT |
| AC-55 | FR-18 | Given рівень 0 (AC-53) і поле `maintenance.equipment.x_f3d_signal_ids` (manual); When `drop_level0='True'` і `run_migration`; Then `ir.model` `x_f3d_signal`, `x_f3d_reading` видалені, `'x_f3d_signal' not in env`, поле `x_f3d_signal_ids` видалене, 7 представлень `td_iot_sim.view_*` видалені. When `drop_level0='True'`, але `mismatches ≠ []` → нічого не видалено | UT |
| AC-56 | FR-18, FR-28 | Given чиста база без рівня 0 і без обладнання макета; When `post_init_hook`; Then `level0_migrated.state='skipped'`; `td.collector` 1 (`COL-MAIN`, `token_hash=False`); `td.source` 7 з кодами й параметрами Додатка C.1; `td.signal` 29 з `origin='catalog'` (без `equipment_id`, WARNING у лозі на кожен відсутній код), звіт `signals_catalog`: `created=29`, `bound=28`, `bind_missing=27`, `no_equipment=29`; `meters=0` | UT |
| AC-57 | FR-18 | Given міграцію AC-53 виконано; When `uninstall_hook(env)`; Then усі `x_active=True`, меню й представлення рівня 0 `active=True`, крон `cron_iot_sim` лишається `active=False`, у лозі WARNING «рівень 0 вимкнено; увімкніть вручну або через пульт»; параметрів `td.telemetry.*` немає | UT |
| AC-58 | FR-18, FR-28, FR-13 | Given копія демо-бази з установленими `td_factory3d` і `td_iot_sim` 19.0.1.0.0, знято `N = SELECT count(*) FROM x_f3d_reading WHERE x_time IS NOT NULL` (14 112 на 14.10.2026 ≈07:30 UTC); When `-i td_telemetry`; Then звіт: `signals_migrated=196`, `by_module={"energy": 87, "bms": 81, "fire_safety": 1, "telemetry": 27}`, `alarm=1`, `with_request=2`, `readings_migrated=N`, `skipped_null_ts=0`, `requests_linked=2`, `signals_catalog.created=29`, `bound=55`, `no_equipment=0`, `meters=9`, `meter_requests_linked=9`, `mismatches=[]`, `state='done'`; `td.signal` 225 (196 `sim_data` + 29 `catalog`), з `source_id` 55; `status`: `alarm` 1 (`ventilation/units/RV-05/filter_dp_pa`), `ok` 195, `unknown` 29; `td.source` 7; `td.collector` 1; `maintenance.request` з `td_signal_id` — 11 (2 `threshold` + 9 `meter`); `x_f3d_signal` з `x_active=False` — 196; `cron_iot_sim.active=False` | TC |
| AC-59 | FR-20 | Given користувачі §13.0; Then матриця §13.3 ТБ-03 виконується: `user_reader` читає всі 8 моделей модуля, будь-який `create/write/unlink` → `AccessError`; `user_manager` створює/пише `td.source`, `td.signal`, створює `td.command`, але `create` `td.collector` і `unlink` `td.command` → `AccessError`; `user_admin` — усе; `user_plain` (без груп f3d) `search` на `td.signal` → `AccessError`; `user_mech` (`maintenance.group_equipment_manager` + `group_td_user`) пише `td_meter_interval` на обладнанні | UT |
| AC-60 | FR-20, A-02 | Given токен `COL-T`; When `user_manager` читає `token_hash`/`token_hint` (`read`, `search_read`, `fields_get`); Then `AccessError` або поля відсутні у `fields_get`. When логи рівня DEBUG перехоплено (`assertLogs('odoo', 'DEBUG')`) під час `action_generate_token` і `_td_ingest`; Then жоден запис не містить сирого токена; `mail.message` колектора містить лише `token_hint` | UT |
| AC-61 | FR-19, CB-10 | Given `td.base.environment='test'`; When `hooks.params(env)`; Then `td.telemetry.read_enabled='True'`. Given `environment='prod'` і `read_enabled` — значення з data; When `hooks.params(env)`; Then `'False'`. `write_enabled='False'` в обох випадках. `res.config.settings` показує ті самі значення в `td_telemetry_read_enabled`/`_write_enabled` | UT |
| AC-62 | FR-19 | Given колектор із токеном, джерела `online`, сигнал `write_enabled=True` (на не-`read_only` джерелі), команди `queued` і `sent`, параметри `True`; When `cr.execute(file_open('td_telemetry/data/neutralize.sql').read())`; Then обидва параметри `'False'`; усі крони модуля `active=False`; усі `td.source` `read_enabled=False`, `write_enabled=False`, `state='disabled'`; `td.collector.token_hash IS NULL`, `state='never'`; команди `expired`; `td.signal.write_enabled=False` у всіх | UT |
| AC-63 | FR-14 | Given `eq_comp` з 3 сигналами (`sig_press`, `sig_hours`, `sig_cstate`); Then `td_signal_count=3`, `td_alarm_count=0`; після тривоги `sig_press` → `td_alarm_count=1`; форма `maintenance.equipment` (`get_views`) містить `page[@name='f3d_signals']` з полем `td_signal_ids` і кнопки `action_f3d_view_signals`, `action_f3d_view_readings`; `action_f3d_view_signals()` має `domain=[('equipment_id','=',eq_comp.id)]`. Після AC-53 представлення `td_iot_sim.view_equipment_form_signals` неактивне | UT |
| AC-64 | FR-15 | Given модуль установлено; When `get_views` для кожної моделі з типами §3 (V-01…V-23); Then без винятків. When `Form(env['td.signal'].with_user(user_manager))`: `code`, `name`, `source_id=MB-T-U70`, `address_text='{"fc": 3, "addr": 3001, "type": "u16"}'` → збережено, `address` — dict. When `Form(td.source)` з `params_text` невалідним → `ValidationError`. Дія `action_td_reading` має `context.search_default_last_48h=1` і `view_mode` починається з `graph` | UT |
| AC-65 | FR-16 | Then `menu_td_telemetry`: батько `td_factory3d.menu_td_data`, `sequence=20`, група `group_td_user`; діти й `sequence`: Огляд 10, Сигнали 20, Показання 30, Годинні агрегати 35, Джерела 40, Колектори 50, Команди 60, Події HTTP push 70 з групами таблиці §3; `menu_td_telemetry_maint` під `maintenance.menu_maintenance_title`, `sequence=6`. When `user_reader` (`load_menus`); Then бачить Огляд, Сигнали, Показання, Годинні агрегати і не бачить Джерела, Колектори, Команди, Події | UT |
| AC-66 | FR-19, FR-28, §5–§6 | Then 16 параметрів §5.1 з указаними значеннями (`default_team_id` — id першої команди, якщо «Служба головного механіка» немає); 4 крони §6 з інтервалами 1 хв, 10 хв, 1 доба, 10 хв і `active=True`; `cron_td_telemetry_rotate.nextcall` у Києві має час 02:40; колектор `collector_main` (`COL-MAIN`) і 7 джерел Додатка C.1 з `collector_id=collector_main` | UT |
| AC-67 | FR-18, FR-20 | When `env['td.signal'].with_user(user_manager).f3d_run_migration()`; Then `AccessError`. When `user_admin`; Then дія `display_notification` з `sticky=True` і текстом звіту; повтор — `created=0` | UT |
| AC-68 | FR-17, R-12, CT-07 | Given міст-модуль, payload `{"equipment": {"FL-C1-T": {"battery": 0.5, "state": "idle", "hours": 0}, "COMPRESSOR-T": {"pressure_bar": 0, "hours": 0}, "GANTRY-T": {"vacuum_kpa": 0}}, "infra": {"totals": {"pv_now": 12.5, "chp_kw": 397.3}}, "energy": {"totals": {}}, "meta": {}}`; сигнали: `sig_bat` 23.6 %, `sig_flstate` `charging`, `sig_hours` 17846.6, `sig_press` 6.772, `equipment/GANTRY-T/vacuum_kpa` −71.9, `sig_water` (вузла `infra.WATER-T` немає), `equipment/FL-C1-T/x` (`viewer_visible=False`), сигнал `status='unknown'`; останній `last_ts` = `2026-10-14 06:10:00`; When `_td_viewer_collect(payload, ctx)`; Then `battery=0.236`, `state='charging'`, `hours=17846.6`, `pressure_bar=6.77`, `vacuum_kpa=-71.9`; `infra` не отримав ключа `WATER-T`; `x` не з'явився; `energy.totals.pv_kw=12.5`, `chp_kw=397.3`; `meta.iot == {"source": "телеметрія (td_telemetry)", "signals": <видимих не unknown>, "alarms": 0, "stale": 0, "updated": "2026-10-14 09:10"}`; `_td_sequence == 95` | UT |
| AC-69 | FR-17, CT-07 | Given ctx `changes={'td.signal': {'equipment/FL-C1-T/battery', 'equipment/FL-C1-T/x'}}`; When `_td_viewer_delta(patch, ctx)`; Then `patch['signals'] == [{"path": "equipment/FL-C1-T/battery", "value": 0.236}]`, `patch['meta']['iot']` присутній. When `changes={}` → `patch` порожній. `_td_viewer_bus_models() == ['td.signal']` | UT |
| AC-70 | FR-17, R-13 | Given міст-модуль, `bus_min_interval_s=10`, `td.viewer.event._notify` підмінено `Mock`; When `sig_bat` 50 о `T0`, 49 о `T0+5 с`, 48 о `T0+10 с` (кожне окремим `_td_ingest`); Then `_notify` отримав код `sig_bat` на `T0` і `T0+10 с`, не на `T0+5 с`. When `sig_flstate` `busy` о `T0`, `charging` о `T0+3 с` → обидва повідомлені (зміна стану негайно). Без міст-модуля (`'td.viewer.event' not in env`) — `_td_ingest` без помилок | UT |
| AC-71 | FR-23, R-19 | Given `Scheduler` з інжектованими `sleep`/`rand`/`now` (§13.0.2), джерело з сигналами `period_s` 10, 10, 60 і фейковий плагін; Then 2 групи опитування; перша затримка групи = `rand()·period`; після 3 поспіль `PollError` — `health().state='error'`, затримки бекофу 1, 2, 4 … 30 с; успіх скидає бекоф і стан `online`; `poll` довший за період → `collector_poll_overrun_total{source}` +1 | CT |
| AC-72 | FR-23, R-19 | Given буфер у `tmp_path`; When `put_many` 10 показань, `take(4)`; Then 4 найстаріші (FIFO); `ack(ids)` видаляє; повторне відкриття файлу зберігає неакнуті 6. When `F3D_BUFFER_MAX_MB=1` і вставлено 30 000 рядків з `text` 64 символи; Then розмір файлу ≤ 1 МБ після перевірки ліміту, найстаріші видалено партіями по 10 000, `dropped_total` ≥ 10 000; `events`/`results` лімітом не видаляються | CT |
| AC-73 | FR-23, API-02 | Given `fake_odoo` і `Pusher`; When відповідь `200` → рядки акнуті; `423` → лишились, опитування призупинено; `429` з `Retry-After: 10` → повтор не раніше 10 с; `400` → пакет видалено, ERROR, `collector_push_rejected_total` +1; `503` тричі → лишились, бекоф 1/2/4 с; `config_etag` ≠ поточного → викликано `Registry.refresh()`; `server_time` відрізняється на 45 с → WARNING і `collector_clock_skew_seconds=45` | CT |
| AC-74 | FR-23, FR-06 | Given `fake_odoo` з конфігурацією 2 джерел; When `Registry.load()`; Then 2 плагіни створені й `connect`; наступне опитування з `If-None-Match` → `304` → жодного перезапуску; зміна `params` одного джерела → `disconnect`/`connect` лише його. When Odoo недоступний на старті, `state/config.json` віком 6 діб → використано; 8 діб → очікування з бекофом. When адреса сигналу невалідна за схемою → джерело `error` «schema: …», інше працює | CT |
| AC-75 | FR-21, FR-27, R-18 | Given `fake_odoo` з командою для сигналу з `write_enabled`; When `F3D_WRITE_ENABLED=0`; Then `GET commands` не викликається жодного разу за 30 с віртуального часу. When `=1` і Odoo `write_enabled=true`; Then `plugin.write` викликано, `POST commands/result` зі `state=done`; сигнал у конфігурації з `write_enabled=false` → `failed` «signal write disabled» без `plugin.write`; `expires_at` у минулому → `failed` «expired»; `WriteError('WriteAccessDenied')` → `failed` з цим текстом; `write` довше 10 с → `failed` «timeout»; при недоступному Odoo результат лежить у буфері `results` і доходить після відновлення | CT |
| AC-76 | FR-24, CT-02 | Given установлений пакет; When `load_plugins()`; Then рівно `{"modbus_tcp", "mqtt", "http_push", "bacnet_ip"}` із класами CT-02. When джерело типу `opcua` без плагіна; Then `Health(state='error', error='plugin opcua not installed')`, інші джерела працюють. Підклас `SourcePlugin` без абстрактних методів → `TypeError` при створенні. `validate()` повертає помилки схеми до `connect()` (`connect` не викликано) | CT |
| AC-77 | FR-25, R-20 | Given `util.codec.decode_registers`; Then `[6772]` `u16` × 0.001 → 6.772; `[0xFFFF]` `i16` → −1; `[0x0000, 0x45B0]` `u32` big → 17840; `[0x2E2A, 0x001C]` `u32` little → 1 846 826 (× 0.01 → 18 468.26); `[0x40C8, 0xF5C3]` `f32` → 6.28 (±1e-6); `[0, 0, 0, 0xC544]` `i64` → 50 500; біт 3 у `[0x0008]` → 1; `encode` ∘ `decode` — тотожність для `u16`, `u32` (обидва порядки), `f32`. Лінійне масштабування ADAM: raw 60 963 × 0.4882887 → 29 767.5 (±0.1); RTD raw 35 749 × 0.0030518 − 50 → 59.10 (±0.01) | CT |
| AC-78 | FR-25, R-20 | Given `modbus_server` (pymodbus) з unit 70: HR 3000…3020 = `[1, 6772, 828, 30, 240, 0, 0, 0, 0, 64, 1630, 0, 0, 0, 0, 0, 0, 0, 0, 0, 17840]` (розрив 3010→3019 = 9 > `gap_max` за замовчуванням 8, Додаток A.2, тож для одного блоку джерело має `params.gap_max=10`), unit 96: HR 0…5 = `[35000, 35749, 34000, 33000, 33500, 33200]`, unit 84: DI0=1, DI1=0, HR 16…17 = `[0x2E2A, 0x001C]`; When `poll` сигналів unit 70 (тиск 3001, стан 3000, температура 3002, завантаження 3009, мотогодини 3019 `u32`); Then **один** запит `read_holding_registers(3000, 21)` (лічильник запитів сервера), значення 6.772, `loaded`, 82.8, 64, 17840. T1 (`addr 0, count 3, agg max`) → 59.10. DUST-1 стан → `running`; DI1=1 → `fault`. Вода → 18 468.26. Адреса 5000 → `PollError` з кодом винятку 2; unit 99 → `PollError` (0x0B або таймаут). `range=[0, 10]` при значенні 16 → `q='bad'`. Два джерела `iot-sim:502` (unit 70, 84) → один клієнт у пулі. `write` (fc 6, addr 3099, 7.2 бар × 1000) → HR 3099 = 7200 | CT |
| AC-79 | FR-26, R-21 | Given фейковий paho-клієнт; When повідомлення `f3d/mobile/FL-1/telemetry` з тілом-прикладом iot_sim §8.8.1 (`state="to_charge"`); Then показання `battery=57.1`, `hours=2069.8`, `x=112.4`, `state` з `text='busy'` (map), `ts=2026-10-14T05:15:03Z`. When `retain=True` → `q='uncertain'`, `ts` = час отримання колектором. When тіло не JSON → показання з `q='bad'`, `value=None` для сигналів топіка. When шляху `$.battery_pct` немає → показання немає, `collector_mqtt_missing_path_total` +1. When `status` `{"online": false}` → `stats.offline_devices` містить `FL-1`, `health().state='online'`. `on_disconnect` → `offline`; `on_connect` з `reason_code≠0` → `error`. **broker**: з mosquitto 2.0.20 — публікація → показання ≤ 2 с; брокер зупинено → `offline`; запущено → перепідключення ≤ 60 с | CT |
| AC-80 | FR-22, R-22 | Given `HttpPushServer` (aiohttp test client), джерело `routes=["lpr"]`, `allow_ips=["127.0.0.1"]`; When `POST /f3d/lpr` з тілом Axis; Then `200 {"received": true}`, у буфері `events` 1 рядок з `event_id == sha256("lpr\n127.0.0.1\n" + canonical_json(payload))`; повтор того самого тіла → у буфері 1 рядок. When IP не в списку → `403`; заданий `secret_ref` і неправильний суфікс → `404`; заданий `token_ref` без заголовка → `401`, з правильним `X-F3D-Token` → `200`; тіло 1 МБ + 1 байт → `413`; `text/plain` → `415`; JSON-масив → `400`; `/f3d/unknown` → `404`; `multipart/form-data` з частиною `application/json` і JPEG → подія з JSON-частини | CT |
| AC-81 | FR-29, R-23, D-07 | Given `bacnet_device` (AI:1=77.4, AI:3=61.1, AO:1 з `priority-array`, MSV:1=2, BI:1=1, LSZ:12=`quiet`); When `poll`; Then `supply_c=77.4`, MSV:1 з `states=["standby", "K1", "K1+K2", "fault"]` → `text='K1'`, LSZ:12 → `text='quiet'`; `status-flags` `fault` на AI:1 → `q='uncertain'`; `out-of-service` → `q='bad'`. When `mode='cov'` і PV AI:1 → 78.0; Then показання ≤ 1 с. When пристрій відхиляє `SubscribeCOV` → сигнал опитується з `period_s`. When `write(AO:1, 80)` при дозволах; Then PV=80, `priority-array[8]=80`, результат `written 80.0 @prio 8`. When `params.read_only=true` → `NotSupported('read-only device')`, лічильник `WriteProperty` на пристрої = 0. When запис у AI:1 → `WriteError` (`write-access-denied`). When `device=999` без відповіді → `ConnectError('Who-Is: device 999 not found')`. **X-66** — Given MSV:1 з `map={"1": "standby", "2": "K1", "3": "K1+K2", "4": "fault"}`; When `write(MSV:1, value=1.0, text='K1')`; Then PV=2 (не 1), результат `written 2 @prio 8`; без `map`, `states=["standby", "K1", "K1+K2", "fault"]`, `text='K1+K2'` → PV=3; `text='boost'` → `WriteError`, `WriteProperty` не надіслано. **X-05** — Given джерело `read_only=true` на тому ж пристрої з AI:1 (`mode` не задано, умовч. `cov`), MSV:1, LSZ:12; When `connect`, 3 цикли `poll`, спроба `write`, спроба явного `SubscribeCOV` через `BacnetApp._request`; Then журнал `bacnet_device.services` містить лише `who-is`, `read-property-multiple` (і `read-property`, якщо `rpm=false`), жодного `subscribe-cov`, `write-property`, `acknowledge-alarm`, `life-safety-operation`, `device-communication-control`, `reinitialize-device`; спроба `SubscribeCOV` → `NotSupported('read-only device: subscribe-cov')`, `collector_bacnet_ro_blocked_total{service="subscribe-cov"}` +1; AI:1 опитується з `period_s`. **X-06** — Given не-`read_only` AI:1 `mode='cov'`, `period_s=30`, PV незмінне; When `vclock` +300 с; Then рівно одне контрольне RPM і одне показання AI:1 з `ts` = час читання (значення те саме). **X-37** — PIV:1 (`Unsigned` 17) → показання 17.0 | CT |
| AC-82 | FR-27 | When `allowlist("10.0.0.9")` при `F3D_ALLOW_HOSTS=iot-sim,10.0.3.0/24`; Then `AllowlistDenied`, `asyncio.open_connection`/`socket.create_connection` (шпигуни) не викликані, `collector_allowlist_denied_total` +1; `10.0.3.21` дозволено. `SecretFilter`: запис з `Authorization: Bearer abc123…`, `password=Secr3t`, значенням `F3D_COLLECTOR_TOKEN` → у виводі `***`, секретів немає. `F3D_COLLECTOR_TOKEN` 20 символів → `f3d-collector run` код виходу 2. Відсутня `F3D_MQTT_PASSWORD` → джерело `error` «secret F3D_MQTT_PASSWORD not set», інші працюють. `/metrics` не містить значень токенів і паролів | CT |
| AC-83 | FR-23 | Then `/metrics` містить усі імена §8.9; `GET /health` → ключі `status`, `odoo`, `buffer_rows`, `sources`; Odoo недоступний > 5 хв віртуального часу → `status='degraded'`. `f3d-collector check-config` → код 0 при `fake_odoo` health з валідним токеном, 1 при `401`; `dump-config` друкує JSON без ключів `password`/`token` | CT |
| AC-84 | FR-28, FR-23 | Given стенд §13.2 (ТК-02, ТК-03); Then ≤ 2 хв після старту колектора 7 джерел `online`; 55 прив'язаних сигналів мають `last_ts ≥ now − 2·period_s` і жодного `stale`; значення збігаються з `GET /sim/v1/signals/{code}` у межах допусків ТК-03 | TC |
| AC-85 | FR-10, FR-11 | Given стенд (ТК-05); When сценарій `filter_clogged` DUST-1 `value=1.9`; Then ≤ 5 хв `equipment/DUST-1/filter_dp_kpa` `alarm`, заявка «Заміна фільтрів: перепад тиску 1,9 кПа при нормі до 1,8»; закриття заявки → емулятор повертає номінал → `ok` | TC |
| AC-86 | FR-12, FR-23 | Given стенд (ТК-08); When `POST /sim/v1/device/COMPRESSOR/fault {"reason": "comm"}`; Then ≤ 70 с `MB-U70-COMPRESSOR` `error`, 5 сигналів компресора `stale`, заявок не створено; `clear` → `ok` ≤ 30 с | TC |
| AC-87 | FR-23 | Given стенд (ТК-12); When Odoo зупинено на 10 хв; Then `buffer_rows` росте; після старту Odoo буфер спорожнів ≤ 2 хв; для кожного прив'язаного сигналу в `td.reading` за вікно простою немає дірок, більших за `store_period_s + period_s`; `duplicates` у логах колектора = 0 помилок | TC |
| AC-88 | FR-21, FR-27 | Given стенд (ТК-15), тимчасовий сигнал уставки компресора; Then команда виконується лише коли увімкнено всі чотири запобіжники; HR 3100 емулятора = 7200 після `done`; з будь-яким вимкненим — команда `expired` або не створена | TC |
| AC-89 | FR-17 | Given стенд із `td_viewer3d` і міст-модулем (ТК-14); Then картка COMPRESSOR у 3D показує тиск = `round(last_value, 2)`; зміна значення в емуляторі видно в 3D ≤ 15 с; `meta.iot.source` = «телеметрія (td_telemetry)» | TC |
| AC-90 | FR-22 | Given стенд (ТК-16); When сценарій `truck_no_booking`; Then ≤ 15 с у «Події HTTP push» подія `lpr` з `payload.plateListMode='none'` (X-48, X-74) і `remote` = IP емулятора | TC |
| AC-91 | FR-31, R-26, CT-12 | Given базовий модуль; Then `env['td.source']._td_local_types() == []`; `tools.address.validate_params('td_genset', {})` → `["type: невідомий тип джерела «td_genset»"]`, `validate_params('td_genset', {}, local_types=('td_genset',))` → `[]`, `validate_params('td_genset', {"password": "x"}, local_types=('td_genset',))` → помилка про секрет. Given `_td_local_types` підмінено на `['rest_vendor']` (у базі тестів моста немає; механізм перевіряється на наявному типі); When `user_manager` створює `LOCAL-T` (`type='rest_vendor'`, без `collector_id`, `params={}`, `module='genset'`, `period_s_default=60`); Then збережено, `is_local=True`; сигнал на ньому з `address="fuel_pct"` (рядок) збережено. When без підміни те саме → `ValidationError` з «Джерело LOCAL-T: вкажіть колектор.» (і помилкою `base_url` параметрів) | UT |
| AC-92 | FR-31, R-26, CT-10 | Given підміну AC-91, `LOCAL-T`, сигнал `sig_local` (`period_s=100`, через `set_sql`: `status='ok'`, `last_ts=now − 2 год`); When `_cron_stale()`; Then `sig_local.status='ok'`; `col._config_payload()` не містить `LOCAL-T`. When `_td_ingest([rd(sig_local, 75)], src='module')`; Then `accepted=1`, `last_value=75`, рядок у `td.reading` з `src='module'`. When `push([rd(sig_local, 76)])` від колектора `COL-T` → `rejected[0].reason='foreign_signal'`. When `sig_local._mark_stale('td_genset: немає свіжих даних')` двічі → `stale`, одне повідомлення чаттера. When `td.command` на `sig_local` (прапори запису ввімкнені через `set_sql`) → `UserError` «Джерело LOCAL-T без колектора: запис у пристрій неможливий.». When `read_enabled=False` на `LOCAL-T` → `state='disabled'` | UT |
| AC-93 | FR-07, FR-22, CT-10, R-17 п. 0 (X-02) | Given `_td_ingest` моделі `td.signal` обгорнуто шпигуном (`patch.object(type(env['td.signal']), '_td_ingest', autospec=True, side_effect=<оригінал>)`); When `POST /f3d/telemetry/push` з 1 показанням `sig_press`; Then шпигун викликано рівно 1 раз з `src='collector'` і `collector` = `COL-T`, `readings` — список з тіла; `changed` відповіді == `changed_codes` результату. When `POST /f3d/telemetry/event` з подією для `sig_plate`; Then шпигун викликано 1 раз з `src='collector'`, `collector=COL-T`. When `push` відхилено `429` (ліміт частоти) або `423` → шпигун не викликано | HT |
| AC-94 | FR-21, API-06, API-07, M-06 (X-03, CR-01) | Given `sig_valve` і `BAC-T-105` з `write_enabled=True`, параметр `write_enabled='True'`; When `user_manager` створює `td.command(signal_id=sig_valve, payload={"method": "StoreAndStart", "job": "WO00013", "qty": 14})`; Then `state='queued'`, `payload` — той самий dict, `payload_text` — JSON; When `payload=[1]`, `payload="x"` або dict > 64 КБ (кожен окремо) → `ValidationError` «Дані команди мають бути об'єктом JSON ≤ 64 КБ.»; When `GET /f3d/telemetry/commands`; Then елемент команди має `"payload": {"method": "StoreAndStart", "job": "WO00013", "qty": 14}`, елемент звичайної команди — `"payload": null`. When `POST /f3d/telemetry/commands/result` `[{"id": <id>, "state": "done", "result": "{\"ReturnStatus\": 0}", "data": {"ReturnStatus": 0}}]`; Then `state='done'`, `result_data == {"ReturnStatus": 0}`. When `data="x"` або `data` > 64 КБ → `400 bad_schema`, стан команди не змінено. Маніфест `version == '19.0.1.1.0'` | HT |
| AC-95 | FR-21, FR-24, CT-02 (X-03, CR-01) | Given `fake_odoo` з командою `{"payload": {"method": "Stop", "job": "WO00013"}}` для сигналу з `write_enabled`, `F3D_WRITE_ENABLED=1`, фейковий плагін з `call` → `{"ReturnStatus": 0}`; Then `call(signal, {"method": "Stop", "job": "WO00013"})` викликано 1 раз, `write` — 0 разів; `POST commands/result`: `state='done'`, `data={"ReturnStatus": 0}`, `result='{"ReturnStatus": 0}'`. When плагін без `call` (`modbus_tcp`) → `failed`, `error='call not supported by modbus_tcp'`, `write` не викликано. When `call` повертає список або dict > 64 КБ → `failed` «call returned invalid data». When `call` довше 10 с → `failed` «timeout». Команда без `payload` → `write` (як AC-75) | CT |
| AC-96 | FR-21, R-18 п. 1, §4.4 (X-04) | Given `sig_valve`, `BAC-T-105` і параметр — усі `write_enabled=True`; When `env['td.command'].with_user(user_reader).sudo().create({'signal_id': sig_valve.id, 'value': 1})`; Then команда `queued`, `requested_by == user_reader`. When `env['td.command'].with_user(SUPERUSER_ID).create(...)` → `queued`. When `with_user(user_reader).create(...)` без `sudo()` → `AccessError`. When під `sudo()`: джерело `write_enabled=False` → `UserError` «Запис у пристрій вимкнено: … джерело BAC-T-105.»; параметр `False` → «… параметр модуля.»; `sig_fire` (прапори через `set_sql`) → `UserError` «Джерело лише для читання.» — запобіжники під `env.su` діють | UT |
| AC-97 | FR-29, R-23, API-05 (X-05) | Given `bacnet_device` (device 140) і джерело `BAC-T-140` (`params={"host": "127.0.0.1", "port": <порт>, "device": 140, "read_only": true}`; `events` не задано → `true`), LSZ:12 опитано зі станом `quiet`; When пристрій надсилає `UnconfirmedEventNotification` (`eventObjectIdentifier` LSZ:12, `eventType` `change-of-life-safety`, `new-state` `test-alarm`, `new-mode` `on`, `messageText` «Тест: сповіщувач 2.CNC.05, Присадка», `notificationClass` 1, `priority` 1, `ackRequired` false); Then `ctx.emit_event` 1 раз: `route='bacnet_event'`, `remote='BAC-T-140'`, `headers={}`, `payload == {"device": 140, "object": "LSZ", "instance": 12, "event_type": "change-of-life-safety", "from_state": "quiet", "to_state": "test-alarm", "mode": "on", "message_text": "Тест: сповіщувач 2.CNC.05, Присадка", "notification_class": 1, "priority": 1, "ack_required": false, "ts": <vclock now ISO Z>}`, `event_id == sha256("bacnet_event\nBAC-T-140\n" + canonical_json(payload))`; пакетів до пристрою у відповідь — 0. When `eventType` `out-of-range` на AI:1 (`fromState` `normal`, `toState` `high-limit`) → `from_state='normal'`, `to_state='high-limit'`, без `mode`. When `messageText` 600 символів → `message_text` 500. When джерело з `"events": false` або подія від device 999 → подій немає, `collector_bacnet_events_ignored_total{reason="disabled"}` / `{reason="unknown_device"}` +1 | CT |
| AC-98 | FR-12, R-07 (X-06) | Given `freeze_time`, `stale_periods=3`, `stale_min_s=60`; сигнали на `src_bac` (не `read_only`): `sig_cov` `{"object": "analog-input", "instance": 1}` (`mode` умовч. `cov`) і `sig_cov2` `{"object": "AI", "instance": 2, "mode": "cov"}`, обидва `period_s=30`; `sig_poll` `{"object": "AI", "instance": 3, "mode": "poll"}`, `period_s=30`; на `src_bac_ro` (`read_only`): `sig_ro_ai` `{"object": "AI", "instance": 5}`, `period_s=30`; Then `_td_stale_after()` = 900, 900, 90, 90; `sig_rv` (`"mode": "poll"`, `period_s=10`) → 60. When усі `status='ok'`, `last_ts = now − 301 с` і `_cron_stale()`; Then `sig_cov`, `sig_cov2` — `ok`, `sig_poll`, `sig_ro_ai` — `stale`. When `sig_cov.last_ts = now − 901 с` → `stale`. `tools.thresholds.cov_check_s(10) == 300`, `cov_check_s(60) == 600` | UT |
| AC-99 | FR-03, M-03 (X-16) | Then `env['td.signal'].fields_get(['origin'])['origin']['selection'] == [('sim_data', 'Рівень 0 (макет)'), ('catalog', 'Каталог емулятора'), ('manual', 'Вручну'), ('module', 'Дані модуля')]`; новий сигнал без `origin` → `'manual'`; `create({..., 'origin': 'module'})` → збережено; `_td_import_sim_rows` створює `origin='catalog'` (AC-52), міграція — `sim_data` (AC-53) | UT |
| AC-100 | FR-25, R-20 (X-46, X-81) | Given `modbus_server` з unit 86 (coils 16…21 = 0) і журналом записів `modbus_server.writes` `[(t, fc, addr, value)]` за `vclock`; сигнал `{"fc": 1, "addr": 16, "type": "bool", "write": {"fc": 5, "addr": 16, "pulse_ms": 1500}}`; When `write(signal, value=0.0, text=None)`; Then `writes == [(T, 5, 16, True), (T + 1.5 с, 5, 16, False)]` (значення команди ігнорується), результат `"fc5 addr 16 pulse 1→0 1500 ms"`; під час імпульсу `poll` іншого сигналу того самого unit виконується. When скидання падає 2 рази й проходить утретє → успіх, 3 спроби скидання. When скидання падає 3 рази → `WriteError('pulse reset failed: …')`, `collector_modbus_pulse_reset_failed_total` +1. When таймаут команди під час імпульсу (`CommandLoop`, ліміт `10 + 1.5` с підмінено на 0,5 с) → coil 16 = 0 після скасування (скидання захищене). Given рівневий сигнал `{"fc": 1, "addr": 20, "type": "bool", "write": {"fc": 5, "addr": 20}}` (без `pulse_ms`, X-81); When `write(signal, value=1.0)`; Then `writes == [(T, 5, 20, True)]`, через 10 с coil 20 = 1 (скидання немає), результат `"fc5 addr 20 = True"`; When `write(signal, value=0.0)`; Then coil 20 = 0 | CT |
| AC-101 | R-02, §8.3.3 (X-63) | Given фейковий плагін, що повертає `Reading(value=3.402)` для `SignalCfg(scale=1.0)` і `SignalCfg(scale=2.0)`, `Reading(text='busy')` для стану, `Reading(value=None, q='bad')`; When цикл `loop_poll` і push-шлях `ctx.emit`; Then у буфері 3.402, 6.804, `busy`, `None` (множення рівно один раз, лише `gauge`/`counter`). Given `mqtt` з адресою `{"topic": …, "path": "$.p_w", "scale": 0.001, "offset": 0}` і повідомленням `{"p_w": 3402}`, `SignalCfg.scale=1000` → `Reading.value` плагіна = 3.402 (плагін `signal.scale` не застосовує), у буфері 3402.0. Given BACnet AI:3 з адресою `{"object": "AI", "instance": 3, "mode": "poll", "scale": 0.1, "offset": -5}` і `bacnet_device.set_pv('AI:3', 611)` → `Reading.value=56.1` | CT |
| AC-102 | R-22, R-02 (X-63) | Given сигнал `yard/lpr/CAM-T/conf` (`gauge`, `src_http`, `address={"route": "lpr", "match": {"sensorProviderID": "CAM-05"}, "path": "$.confidence", "scale": 0.01}`, `scale=2.0`); When `_td_receive` події `lpr` з `payload.confidence=87`; Then `last_value=1.74` (`87·0.01·2`); з `address.offset=0.1` → `(0.87+0.1)·2 = 1.94`; `payload.confidence="abc"` → показання немає, `signal_count` не враховує | UT |
| AC-103 | FR-01, FR-03, CT-03, Додаток A (X-45) | Given джерело `SICS-T` (`sics`); When `params` = `{"host": "iot-sim", "port": 4001, "mode": "stream", "period_s": 1, "timeout_s": 5, "unit": "kg", "dialect": "mt_sics", "reset_on_connect": true}` → збережено; `{"host": "iot-sim"}` → збережено; `mode="push"`, `timeout_s=31`, `unit="oz"`, `{"host": "x", "foo": 1}` (кожен окремо) → `ValidationError` з «Параметри джерела SICS-T:» і ключем (`foo: невідомий ключ (схема sics не допускає додаткових)`). Сигнал на `SICS-T`: `{"field": "weight"}`, `{"field": "stable", "cmd": "SI"}`, `{"field": "weight", "write": {"cmd": "Z"}}`, `{"field": "weight", "scale": 0.001}` → збережено; `{"cmd": "SI"}` (без `field`), `{"field": "unit"}`, `{"field": "weight", "cmd": "SIR"}`, `{"field": "weight", "write": {"cmd": "TA"}}`, `{"field": "weight", "x": 1}` → `ValidationError` | UT |
| AC-104 | M-04, R-17 п. 6, R-22 (X-83) | Given `freeze_time('2026-10-14 05:15:10')`; When `_td_ingest([{code: sig_press, ts: '2026-10-14T05:14:00Z', value: 6.4}], src='module')`; Then рядок `td.reading`: `ts=2026-10-14 05:14:00`, `received_at=2026-10-14 05:15:10`; When те саме з контекстом `f3d_received_at=2026-10-14 05:15:00`; Then `received_at=05:15:00`. When `_td_receive` події `lpr` CAM-05 з `capture_timestamp='1791954905507'`; Then показання `sig_plate`: `ts=2026-10-14 05:15:05.507`, `received_at=05:15:10`, `quality='good'`; When `capture_timestamp` = now + 120 с; Then `ts = received_at = 05:15:10`, `quality='uncertain'`; When сигнал маршруту без `ts_path`; Then `ts = received_at`, `quality='good'`; `td.push.event.ts` = `ts` події від колектора (не замінюється) | UT |

Покриття FR → AC: FR-01 AC-04…06, AC-103; FR-02 AC-01…03; FR-03 AC-08…12, AC-99, AC-103; FR-04 AC-13…16, AC-18; FR-05
AC-17, AC-18; FR-06 AC-35, AC-36, AC-74; FR-07 AC-14, AC-21, AC-38…41, AC-46, AC-93; FR-08 AC-07, AC-42; FR-09 AC-22…25;
FR-10 AC-27, AC-29, AC-85; FR-11 AC-30, AC-31, AC-85; FR-12 AC-26, AC-86, AC-98; FR-13 AC-12, AC-32…34, AC-58; FR-14 AC-63;
FR-15 AC-64; FR-16 AC-65; FR-17 AC-68…70, AC-89; FR-18 AC-53…58, AC-67; FR-19 AC-41, AC-61, AC-62, AC-66; FR-20 AC-37,
AC-59, AC-60, AC-67; FR-21 AC-44, AC-45, AC-47, AC-48, AC-75, AC-88, AC-94…96; FR-22 AC-43, AC-49, AC-50, AC-80, AC-90,
AC-93, AC-104; FR-23 AC-71…75, AC-83, AC-84, AC-87; FR-24 AC-76, AC-95; FR-25 AC-77, AC-78, AC-100; FR-26 AC-79; FR-27 AC-75,
AC-82, AC-88; FR-28 AC-56, AC-58, AC-66, AC-84; FR-29 AC-06, AC-81, AC-97; FR-30 AC-51, AC-52; FR-31 AC-91, AC-92.
Правила: R-01 AC-08; R-02 AC-77, AC-78, AC-101, AC-102; R-03 AC-13; R-04 AC-11, AC-22…25; R-05 AC-27…29; R-06 AC-30,
AC-31; R-07 AC-05, AC-26, AC-98; R-08 AC-19; R-09 AC-17; R-10 AC-18; R-11 AC-32…34; R-12 AC-68; R-13 AC-70; R-14 AC-20;
R-15 AC-53; R-16 AC-36; R-17 AC-14, AC-15, AC-40, AC-93, AC-104; R-18 AC-47, AC-48, AC-75, AC-96; R-19 AC-71, AC-72; R-20 AC-77,
AC-78, AC-100; R-21 AC-79; R-22 AC-49, AC-50, AC-80, AC-102, AC-104; R-23 AC-81, AC-97; R-24 AC-51; R-25 AC-03, AC-07; R-26 AC-91,
AC-92. API: API-01 AC-35…37; API-02 AC-37…41, AC-46, AC-93; API-03 AC-37, AC-42; API-04 AC-37, AC-42; API-05 AC-37, AC-43,
AC-93, AC-97; API-06 AC-37, AC-44, AC-94; API-07 AC-37, AC-45, AC-94. Рядки реєстру → AC: X-02 AC-93; X-03 AC-94, AC-95;
X-04 AC-96; X-05 AC-81, AC-97, ТБ-06; X-06 AC-81, AC-98; X-07 AC-17; X-16 AC-99; X-37 AC-09, AC-51, AC-81; X-42 AC-51;
X-45 AC-51, AC-103; X-46 AC-09, AC-100; X-63 AC-101, AC-102; X-66 AC-81; X-81 AC-09, AC-100; X-83 AC-49, AC-53, AC-104.

## 13. План тестування (для Opus)

### 13.0 Фікстури й вимоги до тестованості

#### 13.0.1 Odoo: `tests/common.py`

Теги всіх класів: `@tagged('post_install', '-at_install', 'f3d', 'f3d_telemetry')`. Запуск на чистій базі:
`odoo-bin -d f3d_tel_test -i td_telemetry --test-tags /td_telemetry --without-demo=all --stop-after-init`;
міст-модуль — `-i td_viewer3d,td_telemetry_viewer3d --test-tags /td_telemetry_viewer3d`.

Вимоги до коду модуля (інакше тести не написати без читання коду): «зараз» — лише `fields.Datetime.now()` /
`datetime.now(UTC)` у Python, ніде SQL `now()` (працює `freezegun.freeze_time`); константа `ROTATE_BATCH = 50000`
у `models/td_reading.py`; хук читає `signal_catalog.csv` лише через `hooks._catalog_rows(env) -> list[dict]`;
`tools/thresholds.eval_status(state: dict, value, text, ts, cfg: dict) -> tuple[str, datetime | None]`
(`state = {"status", "breach_since"}`, `cfg` — поля порогів сигналу; повертає новий `status` і `breach_since`);
`_td_ingest` приймає `ts` як рядок ISO із зоною або `datetime` (naive = UTC).

`class F3DTelemetryMixin` (спільний `setUpClass` для `F3DTelemetryCase(TransactionCase)` і
`F3DTelemetryHttpCase(HttpCase)`), усе створюється від суперкористувача:

| Фікстура | Що створює |
|---|---|
| константи | `T0 = datetime(2026, 10, 14, 6, 0, 0)` (UTC naive); `KYIV = ZoneInfo('Europe/Kyiv')` |
| параметри | `td.telemetry.read_enabled='True'`, `write_enabled='False'`, `keep_days='30'`, `keep_hours_days='400'`, `default_store_period_s='300'`, `stale_periods='3'`, `stale_min_s='60'`, `bus_min_interval_s='10'`, `realarm_cooldown_s='3600'`, `push_max_readings='2000'`, `push_rate_per_min='60'`, `meter_lead_pct='5'`, `default_team_id=str(team_default.id)` |
| користувачі (`odoo.tests.new_test_user`) | `user_plain` (`base.group_user`); `user_reader` (+ `td_factory3d.group_td_user`); `user_mech` (+ `group_td_user`, `maintenance.group_equipment_manager`); `user_manager` (+ `group_td_manager`); `user_admin` (+ `group_td_admin`) |
| команди й стадії | `team_mech` «Служба головного механіка (тест)», `team_default` «Команда за замовчуванням (тест)»; `stage_new` = перша `maintenance.stage` з `done=False` за `sequence`; `stage_done` = перша з `done=True` |
| обладнання (`maintenance.equipment`, `td_code`) | `eq_comp` «Компресорна станція» `COMPRESSOR-T`; `eq_rv` «Припливно-витяжна установка RV-05 (тест)» `RV-05-T`; `eq_flc1` «Навантажувач (резерв) (тест)» `FL-C1-T`; `eq_fl2` «Навантажувач приймання (тест)» `FL-2-T`; `eq_water` «Водомірний вузол (тест)» `WATER-T` — усі з `maintenance_team_id=team_mech`; `eq_other` «Обладнання без команди» `OTHER-T` без команди |
| колектори | `col` `COL-T` «Тестовий колектор», `col2` `COL-T2`; `cls.token`, `cls.token2` — з `action_generate_token()` від `user_admin` (`['context']['default_token']`) |
| джерела | `src_mb` `MB-T-U70` (`modbus_tcp`, `{"host": "iot-sim", "port": 502, "unit": 70}`, `equipment_id=eq_comp`); `src_mb84` `MB-T-U84` (`unit` 84); `src_mqtt` `MQTT-T` (`mqtt`, `{"host": "mosquitto", "port": 1883, "username": "collector", "password_ref": "F3D_MQTT_PASSWORD", "client_id": "f3d-test", "topics": ["f3d/mobile/+/telemetry"]}`); `src_bac` `BAC-T-105` (`bacnet_ip`, `{"host": "iot-sim", "device": 105}`); `src_bac_ro` `BAC-T-200` (`{"host": "iot-sim", "device": 200, "read_only": true}`); `src_http` `HTTP-T` (`http_push`, `{"routes": ["lpr"], "allow_ips": ["iot-sim"]}`); `src_old` `MB-T-OLD` (`active=False`); усі на `col`; `src_other` `MB-T2` на `col2` |
| сигнали | таблиця нижче |
| `push(readings, collector=None, src='collector')` | `env['td.signal'].sudo()._td_ingest(readings, src=src, collector=collector or col)` |
| `rd(sig, value=None, text=None, at=0, q='good')` | `{"code": sig.code, "ts": T0 + timedelta(seconds=at), "value": value, "text": text, "q": q}` (ключі `None` не передаються) |
| `set_sql(rec, **vals)` | `UPDATE <table> SET … WHERE id=%s` (параметризовано) + `rec.invalidate_recordset()` — для `readonly`/службових полів (`last_ts`, `status`, `ts` у `td_collector_push`, прапорів в обхід перевірок) |
| `close(req)` / `reopen(req)` | `req.write({'stage_id': stage_done.id})` / `stage_new.id` |
| `make_level0(signals, readings)` | створює manual-моделі `x_f3d_signal` і `x_f3d_reading` (`ir.model` `state='manual'`, поля й типи — Додаток D, як у живій базі), manual-поле `maintenance.equipment.x_f3d_signal_ids` (one2many), записи; `ir.cron` «IoT tick» `active=True` з `ir.model.data` `td_iot_sim.cron_iot_sim`; меню `td_iot_sim.menu_iot_root` (батько `maintenance.menu_maintenance_title`) з дочірнім `menu_iot_signals`; представлення `td_iot_sim.view_equipment_form_signals` (inherit форми обладнання з `x_f3d_signal_ids`) і ще 6 `td_iot_sim.view_*` на `x_f3d_signal`/`x_f3d_reading`; параметр `td.iot_sim.level0_enabled='True'`. Повертає dict записів. Класи з `make_level0` мають `@skipIf('x_f3d_signal' вже в реєстрі)` — на копії демо їх замінює AC-58 |
| `with_catalog_rows(rows)` | контекстний менеджер: `unittest.mock.patch('odoo.addons.td_telemetry.hooks._catalog_rows', return_value=rows)` |
| `api(method, path, body=None, token=…, headers=None, raw=None)` (лише HttpCase) | `url_open(path, data=raw or json.dumps(body), headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', **headers}, method=method)` → `(status, json або None, headers)`; `token=None` — без заголовка |

Сигнали фікстур (усі `active=True`, `origin='manual'`, `store_period_s=300`, якщо не сказано інакше):

| Змінна | `code` | `kind`, `unit` | Джерело, `address` | Інше |
|---|---|---|---|---|
| `sig_press` | `equipment/COMPRESSOR-T/pressure_bar` | gauge, бар | `src_mb`, `{"fc": 3, "addr": 3001, "type": "u16", "scale": 0.001}` | `eq_comp`, `name` «Компресор: тиск», `period_s=10`, `alarm_low=6.0` (`_on`), `hysteresis=0.1`, `min_duration_s=30`, `decimals=2`, `alarm_title="{equipment}: тиск {value} бар при нормі від {threshold}"` |
| `sig_hours` | `equipment/COMPRESSOR-T/hours` | counter, год | `src_mb`, `{"fc": 3, "addr": 3019, "type": "u32"}` | `eq_comp`, `period_s=60`, `decimals=1` |
| `sig_cstate` | `equipment/COMPRESSOR-T/state` | state | `src_mb`, `{"fc": 3, "addr": 3000, "type": "u16", "map": {"0": "stopped", "1": "loaded", "2": "unloaded", "3": "fault", "4": "standby"}}` | `eq_comp`, `name` «Компресор», `states` = 5 значень `map`, `alarm_states=["fault"]`, `alarm_title` порожній |
| `sig_rv` | `ventilation/units/RV-05-T/filter_dp_pa` | gauge, Па | `src_bac`, `{"object": "analog-input", "instance": 4, "mode": "poll"}` (як bms Додаток B; без `mode` AI був би `cov` і `stale` рахувався б від 300 с — X-06) | `eq_rv`, `period_s=10`, `alarm_high=250` (`_on`), `hysteresis=10`, `decimals=0`, `alarm_title="Заміна фільтрів: перепад тиску {value} Па при нормі до {threshold}"` |
| `sig_valve` | `ventilation/units/RV-05-T/heating_valve` | gauge, % | `src_bac`, `{"object": "analog-output", "instance": 1, "priority": 8}` | `eq_rv`, `write_enabled=False` |
| `sig_bat` | `equipment/FL-C1-T/battery` | gauge, % | `src_mqtt`, `{"topic": "f3d/mobile/FL-C1-T/telemetry", "path": "$.battery_pct"}` | `eq_flc1`, `period_s=5`, `warn_low=25`, `alarm_low=15` (`_on`), `hysteresis=0`, `decimals=1`, `alarm_title="Зарядити АКБ: заряд {value} % при нормі від {threshold}"` |
| `sig_flstate` | `equipment/FL-C1-T/state` | state | `src_mqtt`, `{…, "path": "$.state", "map": {"to_charge": "busy"}}` | `eq_flc1`, `period_s=5`, `states=["idle", "busy", "charging", "offline", "fault"]` |
| `sig_flx` | `equipment/FL-C1-T/x` | gauge, м | `src_mqtt`, `path` `$.x` | `viewer_visible=False`, `store_period_s=60` |
| `sig_fl2_hours` | `equipment/FL-2-T/hours` | counter, год | `src_mqtt`, `path` `$.hours` | `eq_fl2`, `decimals=1` |
| `sig_water` | `infra/WATER-T/m3_total` | counter, м³ | `src_mb84`, `{"fc": 3, "addr": 16, "count": 2, "type": "u32", "wordorder": "little", "scale": 0.01}` | `eq_water`, `period_s=60`, `decimals=2` |
| `sig_flow` | `infra/WATER-T/flow_m3h` | gauge, м³/год | — (без джерела) | `eq_water`, `derived_from_id=sig_water`, `derive_rule='rate_h'`, `period_s=60` |
| `sig_fire` | `fire/groups/FA-T/state` | state | `src_bac_ro`, `{"object": "life-safety-zone", "instance": 12}` | — |
| `sig_plate` | `yard/lpr/CAM-T/plate` | event | `src_http`, `{"route": "lpr", "match": {"sensorProviderID": "CAM-05"}, "path": "$.plateText", "ts_path": "$.capture_timestamp"}` | — |
| `sig_free` | `energy/consumers/SAW-T/p_now` | gauge, кВт | — | `origin='sim_data'`; через `set_sql`: `last_value=12.18`, `status='ok'`, `last_ts=T0 − 1 доба` |
| `sig_foreign` | `equipment/OTHER-T/x` | gauge | `src_other`, `{"fc": 3, "addr": 0}` | колектор `COL-T2` |
| `sig_old` | `equipment/OTHER-T/old` | gauge | `src_mb`, `{"fc": 3, "addr": 1}` | `active=False` |
| `sig_noaddr` | `equipment/OTHER-T/noaddr` | gauge | `src_mb`, `{}` (не налаштовано) | у конфігурацію API-01 не потрапляє |

#### 13.0.2 Колектор: `services/collector/tests/conftest.py`

Вимоги до коду сервісу: класи `Scheduler`, `Pusher`, `StatusReporter`, `CommandLoop`, `Buffer`, плагіни отримують
годинник через параметр `clock: Clock = SystemClock()` (`now() -> datetime` UTC, `monotonic()`, `async sleep(s)`)
і генератор `rand: Callable[[], float] = random.random`; HTTP-клієнт Odoo — через `OdooClient(base_url, token,
session=None)`; `HttpPushServer.app` — властивість з `aiohttp.web.Application`.

| Фікстура | Що робить |
|---|---|
| `settings(tmp_path, monkeypatch)` | env: `F3D_ODOO_URL=<fake_odoo.url>`, `F3D_COLLECTOR_CODE=COL-T`, `F3D_COLLECTOR_TOKEN='t'·43`, `F3D_ALLOW_HOSTS=127.0.0.1,localhost`, `F3D_BUFFER_DIR=tmp_path`, `F3D_WRITE_ENABLED=0`; повертає `Settings()` |
| `vclock` | віртуальний годинник: `now()` від `2026-10-14T06:00:00Z`, `sleep(s)` просуває час і віддає керування циклу; `advance(s)` |
| `fake_odoo` | `aiohttp.test_utils.TestServer` з API-01…API-07: програмовані `config` (dict), `etag`, `push_status` (черга кодів), `write_enabled`, `commands`; журнал викликів `calls[(method, path, json)]`; перевіряє `Authorization` |
| `modbus_server` | `pymodbus==3.9.2` `ModbusTcpServer` на `127.0.0.1:<вільний порт>`, `ModbusServerContext(slaves={70: …, 84: …, 86: …, 90: …, 96: …}, single=False)` з `zero_mode=True` (індекс блоку = PDU-адреса); дані — AC-78 (unit 86 — coils 16…21 = 0, AC-100); `CountingBlock` (підклас `ModbusSequentialDataBlock`) рахує виклики `getValues` → `modbus_server.requests` і журналює `setValues` → `modbus_server.writes = [(vclock.now(), fc, addr, value)]`; `fail_writes(n)` — наступні `n` записів відповідають винятком 0x04 |
| `fake_mqtt` | підміна `paho.mqtt.client.Client` класом `FakeClient` (методи `username_pw_set`, `tls_set`, `reconnect_delay_set`, `connect_async`, `loop_start`, `loop_stop`, `subscribe`, `publish`, `disconnect`); помічники `deliver(topic, payload: bytes, retain=False)`, `drop(rc=7)`, `connect_ok(rc=0)` синхронно викликають колбеки |
| `mqtt_broker` (маркер `broker`) | `F3D_TEST_MQTT=host:port` з env, інакше `docker run -d --rm -p 127.0.0.1::1883 eclipse-mosquitto:2.0.20 mosquitto -c /mosquitto-no-auth.conf`; без Docker — `pytest.skip` (Q-16) |
| `bacnet_device` | `bacpypes3==0.0.102` застосунок-пристрій `device 140` на `127.0.0.1:<вільний UDP-порт>`, об'єкти AI:1 (77.4), AI:2 (20.0), AI:3 (61.1), AO:1 (commandable, `priority-array`), MSV:1 (2, 4 стани, commandable), BI:1 (1), LSZ:12 (`quiet`), PIV:1 (17); лічильник `write_count` (перевизначений `do_WritePropertyRequest`); журнал отриманих сервісів `services: list[str]` (`who-is`, `read-property`, `read-property-multiple`, `subscribe-cov`, `write-property` …; X-05); помічники `set_pv(obj, v)`, `set_flags(obj, fault=False, oos=False)`, `reject_cov=True`, `send_event(obj, event_type, from_state, to_state, new_state=None, new_mode=None, message_text='', notification_class=1, priority=1, ack_required=False)` — `UnconfirmedEventNotification` колектору (AC-97) |
| `http_push_client` | `aiohttp.test_utils.TestClient(TestServer(HttpPushServer(…).app))`; `remote` тестового клієнта — `127.0.0.1` |
| `buffer(tmp_path)` | `Buffer(tmp_path / 'buffer.sqlite', max_mb=200)` |

### 13.1 Юніт-тести

#### 13.1.1 Odoo (`odoo_addons/td_telemetry/tests/`, міст — `td_telemetry_viewer3d/tests/`)

Помилки цілісності — у `with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.cr.savepoint():`.
Кожен під-випадок AC зі списком значень — `self.subTest(case=…)`.

| Файл::клас | Тести | AC | Фікстури | Що саме assert |
|---|---|---|---|---|
| `test_collector.py::TestToken` | `test_generate_token`, `test_authenticate_cases`, `test_revoke`, `test_regenerate_invalidates`, `test_inactive_collector` | AC-01 | `col`, `user_admin` | `hashlib.sha256(token).hexdigest()`; `token_hint`; тип і `target` дії; `assertNotIn(token, body)` для всіх `mail.message` колектора; рівність recordset `_authenticate` |
| `::TestCollectorConstraints` | `test_code_valid`, `test_code_invalid`, `test_code_unique`, `test_interval_checks`, `test_defaults` | AC-02 | — | текст `ValidationError`; `IntegrityError` для кожного CHECK; значення за замовчуванням |
| `::TestCollectorOffline` | `test_offline_after_3_intervals`, `test_online_within_window` | AC-03 | `col`, `col2`, `src_mb`, `src_mqtt`, `sig_press`, `freeze_time` | `state` колекторів/джерел; `status` сигналу; `col2` незмінний |
| `test_source.py::TestParams` | `test_valid_examples` (8 підтестів), `test_invalid_params` (11 підтестів), `test_code_format` | AC-04 | `user_manager`, Додаток A.2 | `ValidationError` і підрядки «Параметри джерела», ім'я ключа |
| `::TestSourceToggle` | `test_disable_marks_stale`, `test_status_keeps_disabled`, `test_reenable_unknown` | AC-05 | `src_mb`, `sig_press`, `col` | `state`, `status`, `config_etag`, тіло останнього `mail.message` сигналу |
| `::TestReadOnly` | `test_source_write_forbidden`, `test_signal_write_forbidden`, `test_type_change_with_signals`, `test_type_change_empty` | AC-06 | `src_bac_ro`, `sig_fire`, `src_mb` | тексти `ValidationError` |
| `::TestApplyStatus` | `test_error_masked`, `test_truncated_512`, `test_signals_stale` | AC-07 | `src_bac`, `sig_rv` | `assertNotIn('Secr3t', last_error)`, `assertIn('password=***', …)`, `error_count == 60`, `len == 512` |
| `::TestLocalSource` | `test_default_no_local_types`, `test_validate_params_local`, `test_local_without_collector`, `test_non_local_requires_collector`, `test_local_excluded_from_config_and_stale`, `test_local_ingest_module_only`, `test_local_mark_stale_once`, `test_local_no_commands`, `test_local_read_disabled` | AC-91, AC-92 | `patch.object(type(env['td.source']), '_td_local_types', lambda self: ['rest_vendor'])`, `set_sql` | `ValidationError` тексти; `is_local`; `_config_payload()['sources']` коди; `status`; відповіді `_td_ingest`; кількість `mail.message` |
| `test_signal.py::TestOrigin` | `test_origin_selection`, `test_origin_module_saved` | AC-99 | `user_manager` | `fields_get` selection (4 значення в порядку M-03); умовчання `manual` |
| `::TestSicsSchema` | `test_sics_params_valid`, `test_sics_params_invalid`, `test_sics_address_valid`, `test_sics_address_invalid` | AC-103 | джерело `SICS-T` (створюється в тесті) | `ValidationError` і підрядки ключів |
| `::TestCode` | `test_valid_codes`, `test_invalid_codes`, `test_unique_code` | AC-08 | `user_manager` | `ValidationError` з «Код сигналу»; `SELECT count(*) FROM td_signal` до/після однаковий |
| `::TestAddress` | `test_modbus`, `test_mqtt`, `test_bacnet`, `test_http_push`, `test_no_source_not_validated`, `test_not_object`, `test_address_text` | AC-09 | `src_mb`, `src_mqtt`, `src_bac`, `src_http` | `ValidationError` із «Адреса сигналу» і ключем; збережений `address` |
| `::TestThresholdConstraints` | `test_low_order`, `test_high_order`, `test_low_lt_high`, `test_state_numeric`, `test_derive_requires_counter`, `test_checks`, `test_store_period_default` | AC-10 | — | тексти; `IntegrityError`; `store_period_s == 120` |
| `::TestWrite` | `test_threshold_change_recomputes`, `test_config_change_resets_etag`, `test_name_change_keeps_etag` | AC-11 | `sig_rv`, `sig_press`, `col` | `status`, `status_since`, `config_etag` |
| `::TestUnlink` | `test_meter_signal_protected`, `test_cascade_readings` | AC-12 | `eq_comp`, `sig_hours` | `UserError` текст; `search_count` показань/агрегатів = 0 |
| `test_readings.py::TestStorePolicy` | `test_store_every_300s`, `test_status_change_stored`, `test_bad_quality`, `test_store_period_zero` | AC-13 | `sig_press`, `push`, `rd` | список `ts` збережених рядків дорівнює очікуваному; `last_*` |
| `::TestIdempotency` | `test_repeat_batch`, `test_older_reading_stored_not_last` | AC-14 | 4 сигнали | повні dict відповідей `_td_ingest`; кількість рядків; `last_*`; кількість `mail.message` |
| `::TestRace` | `test_older_does_not_override` | AC-15 | `sig_press`, `set_sql` | `last_value`, `last_ts`, `status`, кількість заявок 0 |
| `::TestReadingModel` | `test_no_edit`, `test_admin_quality`, `test_unique` | AC-16 | `user_manager`, `user_admin` | `UserError`; `IntegrityError` |
| `::TestHourly` | `test_aggregate_values`, `test_rerun_upsert`, `test_late_reading`, `test_open_hour_skipped`, `test_counter_delta_from_prev_hour`, `test_counter_delta_gap`, `test_counter_delta_daily_reset` | AC-17 | `sig_rv`, `sig_hours`, `freeze_time` | поля агрегату з `assertAlmostEqual(places=6)`; кількість рядків 1 |
| `::TestRotate` | `test_rotate_keep_days`, `test_rotate_batches` | AC-18 | `patch.object(td_reading, 'ROTATE_BATCH', 2)` | наявність/відсутність id |
| `::TestCounters` | `test_decrease_uncertain`, `test_daily_reset_good`, `test_rate_h_derived`, `test_first_no_derived` | AC-19 | `sig_hours`, `sig_water`, `sig_flow` | `last_quality`; похідне показання 2.1 (`places=6`) |
| `::TestTimezones` | `test_ts_variants`, `test_request_time_kyiv` | AC-20 | `freeze_time('2026-10-14 06:10:10')`, `sig_rv` | `rejected` з `i`/`reason`; `ts` у базі; підрядок у `description` |
| `::TestModuleIngest` | `test_ct10_no_rate_limit_and_rules` | AC-21 | `sig_free`, `sig_press` | `src='module'`; немає `rate_limited`; заявка створена |
| `test_thresholds.py::TestEvalStatusPure` (`unittest.TestCase`) | `test_high_hysteresis`, `test_low_warn_alarm`, `test_min_duration`, `test_state`, `test_event`, `test_bad_quality` | AC-22…AC-25 | — | кортежі `(status, breach_since)` |
| `::TestHighHysteresis`, `::TestLowWarnAlarm`, `::TestMinDuration`, `::TestStateEvent` | по одному тесту на послідовність AC | AC-22…AC-25 | `sig_rv`, `sig_bat`, `sig_press`, `sig_cstate` | `status` після кожного показання; кількість заявок |
| `::TestStale` | `test_cron_stale_windows`, `test_no_source_never_stale`, `test_request_kept`, `test_recover`, `test_params` | AC-26 | 5 сигналів, `freeze_time` | `status`; `maintenance_request_id`; заявок 0 |
| `::TestStaleCov` | `test_stale_after_cov_poll_ro`, `test_cron_cov_not_stale_301s`, `test_cron_cov_stale_901s`, `test_cov_check_s` | AC-98 | `src_bac`, `src_bac_ro`, 4 сигнали в тесті, `freeze_time` | `_td_stale_after()`; `status` |
| `test_requests.py::TestOpenRequest` | `test_request_fields`, `test_default_team` | AC-27 | `sig_rv`, `eq_other` | усі поля заявки; `alarms_opened == 1` |
| `::TestTitles` | `test_titles`, `test_fmt_num`, `test_unknown_placeholder`, `test_truncate_256` | AC-28 | чисті функції + `sig_bat`, `sig_press` | рівність рядків |
| `::TestDedup` | `test_one_open_request`, `test_no_equipment`, `test_create_request_off` | AC-29 | `sig_rv` | `search_count` заявок; текст чаттера |
| `::TestClose` | `test_close_back_to_ok`, `test_close_still_alarm_cooldown` | AC-30 | `sig_rv`, `close`, `freeze_time` | `request_closed_at`, `status`, тексти чаттера, кількість заявок 1 → 1 → 2 |
| `::TestReopenDelete` | `test_reopen_relinks`, `test_delete_sets_closed_at` | AC-31 | `reopen`, `user_admin` | `maintenance_request_id`, `request_closed_at` |
| `test_meter.py::TestMeterCreate` | `test_no_request_before_lead`, `test_request_at_lead`, `test_no_duplicate`, `test_overdue_priority` | AC-32 | `eq_comp`, `sig_hours`, `eq_fl2`, `sig_fl2_hours` | `td_meter_next_value`, `td_meter_remaining`, поля заявки |
| `::TestMeterClose` | `test_close_updates_last` | AC-33 | — | `td_meter_last_value/date`, `next`, чаттер |
| `::TestMeterRules` | `test_interval_required`, `test_foreign_meter`, `test_schedule_date_rate`, `test_schedule_date_no_rate`, `test_remaining_fl2` | AC-34 | агрегати `td.reading.hour` за 7 діб (17 рядків по `delta=3.5`) | `ValidationError`; `assertAlmostEqual(schedule_date − now, 11.74 доби, delta=0.05 доби)` |
| `test_api.py::TestConfig` (HttpCase) | `test_config_schema`, `test_filters`, `test_no_secrets`, `test_source_disabled`, `test_global_disabled`, `test_etag_304`, `test_etag_changes` | AC-35, AC-36 | `api`, усі джерела | статус, ключі, `ETag`, `Cache-Control`, `assertNotIn('"password"', raw)` |
| `::TestAuth` | `test_401_all_endpoints` (7 × 3 підтести), `test_403_inactive`, `test_health_never_401` | AC-37 | `api(token=None/'wrong'/revoked)` | статус і `error.code`; токен не в тілі |
| `::TestPush` | `test_push_ok`, `test_push_bad_body`, `test_push_element_rejects`, `test_push_repeat`, `test_push_read_disabled_423`, `test_push_rate_limited_429` | AC-38…AC-41 | `api`, `set_sql` | тіла відповідей; `last_*`; лічильники `td.reading`; `Retry-After` |
| `::TestStatusHealth` | `test_status_ok`, `test_status_bad_schema`, `test_health_variants` | AC-42 | `api` | поля колектора/джерел; ключі health |
| `::TestEvent` | `test_event_ok`, `test_event_duplicate`, `test_event_bad`, `test_event_413_423` | AC-43 | `api`, `sig_plate` | `td.push.event`; `sig_plate.last_text` |
| `::TestCommandsApi` | `test_commands_write_disabled`, `test_commands_handout`, `test_results`, `test_results_repeat_and_errors` | AC-44, AC-45 | `sig_valve`, `sig_foreign`, `set_sql` | стани команд; тіла |
| `::TestIngestEntryPoint` | `test_push_goes_through_f3d_ingest`, `test_event_goes_through_f3d_ingest`, `test_rejected_push_no_ingest` | AC-93 | `api`, шпигун `patch.object(type(env['td.signal']), '_td_ingest', autospec=True, side_effect=…)` | `call_args` (`src`, `collector`); `changed` |
| `::TestCommandPayload` | `test_payload_create_and_validate`, `test_commands_payload_key`, `test_result_data_saved`, `test_result_data_bad_schema` | AC-94 | `sig_valve`, `set_sql`, `api` | `payload`, `result_data`; тіла API-06/07 |
| `::TestPushPerf` (тег `f3d_perf`) | `test_push_1000_under_1s`, `test_no_n_plus_one` | AC-46 | 55 сигналів (`setUpClass` створює 38 додаткових на `src_mb`) | `time.perf_counter`; `self.cr.sql_log_count` до/після |
| `test_commands.py::TestCommandCreate` | `test_flags_order`, `test_all_flags_ok`, `test_reader_denied`, `test_read_only_source` | AC-47 | `sig_valve`, `src_bac`, `sig_fire`, `set_sql` | тексти `UserError`, `AccessError`, поля команди |
| `::TestCommandLifecycle` | `test_cancel`, `test_expire_cron`, `test_state_text_to_index` | AC-48 | `freeze_time` | `state`; чаттер; `value == 1.0` |
| `::TestCommandSudo` | `test_sudo_skips_group`, `test_superuser_create`, `test_no_sudo_denied`, `test_sudo_flags_still_checked` | AC-96 | `user_reader`, `sig_valve`, `sig_fire`, `set_sql` | `state`, `requested_by`; `AccessError`/`UserError` тексти |
| `test_push_handler.py::TestDispatch` | `test_handler_called`, `test_signal_reading_from_event`, `test_match_mismatch`, `test_handler_exception_isolated`, `test_numeric_scale_address_and_signal`, `test_received_at_and_ts_fallback` | AC-49, AC-50, AC-102, AC-104 | `patch.object(F3dPushHandler, '_td_handler_models')`, `patch.object(F3dPushHandler, '_td_handle_push')` | аргументи `Mock.call_args`; `handled_by`, `error`, `signal_count`; показання; `received_at` = заморожений час, заміна `ts` на `received_at` для `ts_future` і без `ts_path`, контекст `f3d_received_at` (X-83) |
| `test_sim_catalog.py::TestParse` (`unittest.TestCase`) | `test_r24_examples`, `test_vendor_pdu_rule` (Huawei/TEDOM/PM5560/ADAM, X-42), `test_pdu_notation`, `test_opcua_http_sics` (`field`, X-45), `test_piv` (X-37), `test_unparsed` | AC-51 | — | рівність dict |
| `::TestImportRows` | `test_import_rows`, `test_no_sim_model` | AC-52 | `sig_press`, `src_mb` | звіт; поля нового сигналу; незмінність `sig_press` |
| `test_migration.py::TestLevel0` | `test_full_migration` | AC-53 | `make_level0` (7 сигналів, 31 показання, заявки A/B на `eq_rv`/`eq_other`), `with_catalog_rows` | звіт `run_migration`; поля кожного сигналу; xml-id; показання; рівень 0 вимкнено |
| `::TestRerunPartial` | `test_rerun_idempotent`, `test_partial_keeps_level0` | AC-54 | `patch('…hooks.readings_level0', side_effect=…)` | `state`, `mismatches`, `cron.active`, `x_active` (SQL) |
| `::TestDrop` | `test_drop_level0`, `test_no_drop_on_mismatch` | AC-55 | `drop_level0='True'` | `ir.model`, `ir.model.fields`, `ir.ui.view` за xml-id |
| `::TestCleanDb` | `test_clean_install_state` (`@skipIf` копія демо: `level0_migrated.state != 'skipped'`) | AC-56 | — | кількості за `origin='catalog'`, коди 29; джерела 7; звіт |
| `::TestUninstall` | `test_uninstall_restores_level0` | AC-57 | `make_level0`, `run_migration`, `uninstall_hook` | `x_active`, `active` меню/представлень/крону; `assertLogs(level='WARNING')`; параметри відсутні |
| `test_security.py::TestAcl` | `test_matrix` (§13.3 ТБ-03, підтест на клітинку), `test_plain_user_denied`, `test_mech_meter_fields` | AC-59 | користувачі | `AccessError` / успіх |
| `::TestSecrets` | `test_token_fields_hidden`, `test_token_not_logged`, `test_token_not_in_messages` | AC-60 | `col`, `assertLogs('odoo', 'DEBUG')` | відсутність підрядка токена в усіх `record.getMessage()` |
| `::TestStopCranes` | `test_test_env_defaults`, `test_prod_env_defaults`, `test_settings_fields` | AC-61 | `hooks.params(env)` | значення параметрів |
| `::TestNeutralize` | `test_neutralize_sql` | AC-62 | `file_open('td_telemetry/data/neutralize.sql')` | стан після `cr.execute` |
| `test_views.py::TestEquipmentTab` | `test_counts`, `test_page_present`, `test_actions` | AC-63 | `eq_comp` | `get_views(…)['views']['form']['arch']` містить `name="f3d_signals"`; домен дії |
| `::TestViewsLoad` | `test_all_views_load`, `test_signal_form_create`, `test_source_bad_params_text`, `test_reading_action_context` | AC-64 | `Form` | без винятків; `address` dict |
| `::TestMenus` | `test_menu_tree`, `test_reader_menus` | AC-65 | `user_reader` | `parent_id`, `sequence`, `group_ids`; `load_menus` |
| `test_hooks.py::TestData` | `test_params`, `test_crons`, `test_rotate_nextcall_kyiv`, `test_sources_data` | AC-66 | — | 16 параметрів; 4 крони; `nextcall.astimezone(KYIV).strftime('%H:%M') == '02:40'`; 7 джерел (Додаток C.1) |
| `::TestRunMigrationAction` | `test_manager_denied`, `test_admin_notification` | AC-67 | `user_manager`, `user_admin` | `AccessError`; `tag == 'display_notification'`, `params.sticky` |
| `td_telemetry_viewer3d/tests/test_viewer_provider.py::TestCollect` | `test_values_and_meta`, `test_missing_node_skipped`, `test_invisible_and_unknown_skipped`, `test_sequence` | AC-68 | сигнали фікстур (міст-модуль імпортує `F3DTelemetryCase`) | рівність фрагментів payload; `meta.iot` |
| `::TestDelta` | `test_delta_signals`, `test_delta_empty`, `test_bus_models` | AC-69 | ctx-словник | `patch` |
| `::TestBus` | `test_debounce_10s`, `test_state_change_immediate` | AC-70 | `patch.object(type(env['td.viewer.event']), '_notify')`, `freeze_time` | `call_args_list` |

#### 13.1.2 Колектор (`services/collector/tests/unit/`, `pytest -m "not stand"`)

Запуск: `cd services/collector && pip install -e . -r requirements.txt && pytest -m "not stand and not broker"` (CI) і
`pytest -m broker` (з mosquitto). `pytest-asyncio` у режимі `asyncio_mode = "auto"`, `pytest-timeout` 30 с на тест.

| Файл | Тести | AC | Фікстури | Що саме assert |
|---|---|---|---|---|
| `test_scheduler.py` | `test_groups_by_period`, `test_initial_jitter`, `test_backoff_and_error_state`, `test_success_resets`, `test_overrun_metric`, `test_core_applies_signal_scale_once`, `test_emit_applies_signal_scale` | AC-71, AC-101 | `vclock`, фейковий плагін (`poll` з програмованими винятками) | кількість груп; моменти викликів `poll` за `vclock`; `health().state`; значення метрики |
| `test_buffer.py` | `test_fifo_take_ack`, `test_persist_after_reopen`, `test_size_limit_drops_oldest`, `test_events_results_not_dropped` | AC-72 | `buffer`, `tmp_path` | порядок id; розмір файлу; `dropped_total` |
| `test_odoo_client.py` | `test_push_200_ack`, `test_push_423_keep_pause`, `test_push_429_retry_after`, `test_push_400_drop`, `test_push_503_backoff`, `test_config_etag_refresh`, `test_clock_skew_warning` | AC-73 | `fake_odoo`, `vclock`, `caplog` | рядки буфера; виклики `Registry.refresh`; записи логу; метрики |
| `test_registry.py` | `test_load_and_connect`, `test_304_no_restart`, `test_changed_source_restart_only`, `test_cached_config_age`, `test_invalid_schema_source_error`, `test_load_plugins`, `test_missing_plugin`, `test_abstract_plugin`, `test_validate_before_connect` | AC-74, AC-76 | `fake_odoo`, `tmp_path/state/config.json` | `connect`/`disconnect` лічильники; `Health` |
| `test_commands.py` | `test_write_disabled_no_poll`, `test_write_done`, `test_signal_write_disabled`, `test_expired`, `test_write_error`, `test_write_timeout`, `test_results_buffered`, `test_payload_calls_call_not_write`, `test_call_not_supported`, `test_call_invalid_data`, `test_call_timeout` | AC-75, AC-95 | `fake_odoo`, `vclock`, фейковий плагін | `fake_odoo.calls`; тіла `commands/result` |
| `test_codec.py` | `test_decode_cases` (параметризований), `test_roundtrip`, `test_linear_scale_adam` | AC-77 | — | значення з допуском |
| `test_jsonpath.py` | `test_get_paths`, `test_invalid_paths` | AC-79 | — | `$.a.b[0].c` → значення; `$..x`, `a.b` → `ValueError` |
| `test_plugin_modbus.py` | `test_block_grouping_one_request`, `test_decode_values`, `test_agg_max_rtd`, `test_di_states`, `test_water_little_endian`, `test_illegal_address`, `test_unknown_unit`, `test_range_bad`, `test_pool_shared`, `test_write_fc6`, `test_pulse_write_1_then_0`, `test_pulse_reset_retry`, `test_pulse_reset_failed`, `test_pulse_reset_on_cancel`, `test_level_write_no_reset` | AC-78, AC-100 | `modbus_server` | `modbus_server.requests == 1` для блоку; `Reading` поля; HR 3099 |
| `test_plugin_mqtt.py` | `test_telemetry_mapping`, `test_retain_uncertain`, `test_bad_json`, `test_missing_path_metric`, `test_status_offline_device`, `test_disconnect_states`, `test_address_scale_not_signal_scale` (AC-101); `@pytest.mark.broker`: `test_broker_roundtrip`, `test_broker_reconnect` | AC-79 | `fake_mqtt`, `mqtt_broker` | `Reading` поля; `stats`; `health()` |
| `test_plugin_http_push.py` | `test_accept_event`, `test_event_id_dedup`, `test_ip_denied`, `test_secret_path`, `test_token_header`, `test_413_415_400`, `test_unknown_route`, `test_multipart_json_part` | AC-80 | `http_push_client`, `buffer` | статуси; рядки `events` у буфері; `event_id` |
| `test_plugin_bacnet.py` | `test_rpm_poll_values`, `test_status_flags_quality`, `test_cov_notification`, `test_cov_rejected_fallback_poll`, `test_write_priority`, `test_read_only_no_packet`, `test_write_ro_object_error`, `test_whois_not_found`, `test_msv_write_reverse_map`, `test_msv_write_states_1_based`, `test_read_only_services_whitelist`, `test_cov_control_read_emits`, `test_piv_value`, `test_address_scale_offset`, `test_event_relay_life_safety`, `test_event_out_of_range`, `test_event_ignored_unknown_or_disabled` | AC-81, AC-97, AC-101 | `bacnet_device`, `vclock` | значення; `q`; `write_count == 0`; тексти винятків |
| `test_allowlist.py` | `test_allowlist_blocks_connect`, `test_cidr_allowed`, `test_odoo_host_auto` | AC-82 | `monkeypatch` шпигуни `asyncio.open_connection`, `socket.create_connection` | `AllowlistDenied`; кількість викликів шпигунів 0 |
| `test_logging.py` | `test_secret_filter_masks`, `test_metrics_no_secrets` | AC-82 | `caplog`, `/metrics` | відсутність секретів |
| `test_config.py` | `test_token_too_short_exit2`, `test_missing_secret_ref`, `test_required_env` | AC-74, AC-82 | `subprocess.run([sys.executable, '-m', 'collector', 'run'])` з env | код виходу; `Health` |
| `test_cli.py` | `test_check_config_ok`, `test_check_config_401`, `test_dump_config_no_secrets` | AC-83 | `fake_odoo` | коди виходу; stdout |
| `test_metrics.py` | `test_metric_names`, `test_health_degraded` | AC-83 | `vclock` | імена §8.9; `status` |

### 13.2 Стендові сценарії (ТК) — емулятор `td_iot_sim` + колектор + Odoo

Стенд (Q-17): хост із Docker; `docker compose -f docker-compose.sim.yml --profile dev up -d` (iot_sim, mosquitto;
режим `scenario`, `factor=1`, `SIM_LPR_PUSH_URL=http://collector:8080/f3d/lpr`); Odoo 19 у контейнері `odoo19`
(мережа `odoo_default`) з **копією** демо-бази після DEPLOY_TEST кроків 1–4 (§13.5); колектор
`docker compose -f docker-compose.collector.yml up -d` з `.env` за ARCH §3. Пульт емулятора — iot_sim §7.2
(`curl -H "Authorization: Bearer $SIM_API_TOKEN" http://127.0.0.1:8090/sim/v1/…`); перед кожним ТК —
`POST /sim/v1/reset {"keep_time": true}`. Сценарії S-xx запускаються `POST /sim/v1/scenario/<name>/start` з тілом
`{"params": {…}}` (iot_sim API-13; формат обов'язковий — рішення X-57); у таблиці після назви сценарію наведено **вміст
`params`** (для `filter_clogged` — лише ключ `value`, X-58), напр. ТК-05: `{"params": {"device": "DUST-1", "value": 1.9,
"ramp_min": 2}}`; `POST /sim/v1/device/<code>/fault` (API-12) і `PUT /sim/v1/signals/<code>` (API-16) — тіла як у
таблиці, без `params`. Автоматизовані перевірки — `pytest services/collector/tests/stand -m stand`
з env `F3D_STAND_ODOO_URL`, `F3D_STAND_ODOO_DB`, `F3D_STAND_ODOO_LOGIN`, `F3D_STAND_ODOO_PASSWORD` (XML-RPC до копії),
`F3D_STAND_SIM_URL`, `SIM_API_TOKEN`, `F3D_STAND_COLLECTOR_METRICS=http://collector:9108`. Результати — у
`docs/modules/td_telemetry/TEST_REPORT.md` (таблиця ТК: дата, фактичні значення, статус).

| ТК | Назва | Передумови (сценарій емулятора) | Кроки | Очікуваний результат (AC) | Де дивитися |
|---|---|---|---|---|---|
| ТК-01 | Установка й міграція рівня 0 | копія демо з `td_factory3d` (§13.5 п. 1–2); емулятор не потрібен | 1) знімки S0–S3 §13.5; 2) `odoo-bin -d <copy> -i td_telemetry --stop-after-init --log-level=info`; 3) SQL-перевірки AC-58 | AC-58; у лозі рядки кроків 1–11 §5.3 з кількостями, без ERROR; хук ≤ 120 с | лог; Налаштування → Технічні → Параметри `td.telemetry.level0_migrated`; 3D Завод → Дані → Телеметрія → Сигнали, фільтр «Тривога» — 1 рядок (RV-05); меню «Імітація IoT» зникло |
| ТК-02 | Реєстрація колектора й перший обмін | ТК-01; емулятор `reset`, без запусків | 1) Колектори → COL-MAIN → «Згенерувати токен», скопіювати; 2) `.env` колектора (ARCH §3); `up -d collector`; 3) чекати 2 хв; 4) `curl -H "Authorization: Bearer $T" http://odoo19:8069/f3d/telemetry/health` з контейнера колектора | AC-84: колектор `online`, версія `0.1.0`; 7 джерел `online`; `counts.stale = 0`; 55 сигналів зі свіжим `last_ts`; `collector_source_up` = 1 для 7 джерел; у `docker logs collector` немає ERROR | 3D Завод → Дані → Телеметрія → Огляд (kanban: 7 у «Онлайн»), Колектори; `/metrics` |
| ТК-03 | Звірка значень з емулятором (нотація PDU за вендором, X-42) | ТК-02, 5 хв роботи | для кожного з 55 сигналів: `GET /sim/v1/signals/{code}` і `last_value`/`last_text` (XML-RPC), час знімків ≤ 2·`period_s` | Допуски: тиск Elektronikon ±0,01 бар; завантаження ±1 %; мотогодини ±0,1 год; температура компресора ±0,1 °C; RTD T1/T2 ±0,2 °C; ADAM AI ±0,05 % діапазону (витрата ±16 м³/год, перепад ±0,002 кПа, тиск ±0,008 бар); BACnet ±0,01; MQTT і стани — точний збіг; вода ±0,01 м³; жодного `last_quality='bad'` | таблиця різниць у `TEST_REPORT.md`; `/sim/v1/signals?device=COMPRESSOR` |
| ТК-04 | Техніка MQTT (P-06) | ТК-02 | 1) S-10 `battery_low` `{"device": "FL-C1", "level_pct": 14.2}`; 2) 10 хв спостереження; 3) закрити заявку | ≤ 15 с `equipment/FL-C1/battery` `alarm`, заявка «Зарядити АКБ: заряд 14,2 % при нормі від 15» (значення в заголовку — перше показання < 15: 14,0…14,2); `equipment/FL-C1/state` `busy` → `charging`; після заряду > 25 % — `ok`; `equipment/FL-C1/x`, `/y` змінюються, у 3D ключів `x/y` немає (A-19) | Обслуговування → Заявки; FL-C1 → вкладка «Сигнали»; Показання (графік) |
| ТК-05 | Фільтр аспірації → заявка → закриття | ТК-02 | 1) S-04 `filter_clogged` `{"device": "DUST-1", "value": 1.9, "ramp_min": 2}`; 2) чекати заявку; 3) `POST /sim/v1/scenario/filter_clogged/stop`, закрити заявку (стадія Repaired) | AC-85: `equipment/DUST-1/filter_dp_kpa` `alarm` ≤ 30 с після перевищення 1,8; заявка «Заміна фільтрів: перепад тиску 1,9 кПа при нормі до 1,8», команда «Служба головного механіка»; після кроку 3 — `ok` (≤ 1,764 з гістерезисом 0,036), у чаттері сигналу «Заявку … закрито» | Обслуговування → Заявки; Сигнали → DUST-1 |
| ТК-06 | RV-05 через CT-11 (прив'язка за bms) | ТК-02; для варіанта A — iot_sim 19.0.2.0.0 з `td.sim.signal` | 1) створити джерело `BAC-105-RV-05` (`bacnet_ip`, `{"host": "iot-sim", "device": 105}`, COL-MAIN); 2) A: `odoo shell`: `env['td.signal']._td_import_sim_catalog(codes=['ventilation/units/RV-05/filter_dp_pa'], source_map={'dev105': 'BAC-105-RV-05'})`; B: вручну адреса `{"object": "analog-input", "instance": 4, "mode": "cov"}`; 3) `realarm_cooldown_s=60`; закрити заявку id 6; 4) S-04 `{"device": "RV-05", "value": 285}`; 5) `stop`, закрити заявку | після 2 — сигнал отримує значення ≤ 30 с; після 3 — `alarm` лишається (285…320 > 250), чаттер «Тривога триває…»; ≤ 2 хв після cooldown — нова заявка «Заміна фільтрів: перепад тиску 285 Па при нормі до 250»; після 5 — `ok` (≤ 245 з гістерезисом 5) | Заявки; Сигнали → RV-05 (чаттер) |
| ТК-07 | Компресор: падіння тиску й перегрів | ТК-02 | 1) S-11 `compressor_fault` `{"kind": "pressure_drop", "duration_s": 900}`; 2) після завершення — S-11 `{"kind": "overtemp", "duration_s": 300}`; 3) закрити заявки | крок 1: `equipment/COMPRESSOR/pressure_bar` `alarm` не раніше ніж через 30 с після першого значення < 6,0 (`min_duration_s`), заявка «Компресорна станція: тиск 5,5 бар при нормі від 6» (значення фактичне); `equipment/AIR-RING/pressure_bar` → 5,6 → окрема заявка «Пневмомагістраль: тиск 5,6 бар при нормі від 6»; після завершення — `ok`; крок 2: `equipment/COMPRESSOR/temp_c` > 110 → заявка «Компресорна станція: температура 115 °C при нормі до 110», `equipment/COMPRESSOR/state` `fault` → заявка «Компресор: стан «fault»» | Сигнали, фільтр «Тривога»; Заявки |
| ТК-08 | Недоступний пристрій (stale без заявок) | ТК-02 | 1) `POST /sim/v1/device/COMPRESSOR/fault {"reason": "comm"}`; 2) 3 хв; 3) `POST /sim/v1/device/COMPRESSOR/clear` | AC-86: ≤ 2 хв `MB-U70-COMPRESSOR` `error` з `last_error` (без секретів), 5 сигналів компресора `stale`, нових заявок 0; після `clear` ≤ 60 с — `online`, сигнали з актуальним статусом | Огляд (колонка «Помилка»); форма джерела; `collector_poll_errors_total` |
| ТК-09 | Котельня BACnet: COV і резервне опитування | ТК-02 | 1) S-13 `boiler_refill` `{"level_pct": 95}`; 2) `PUT /sim/v1/signals/equipment/BOILER/silo_fill {"value": 40, "hold_s": 120}`; 3) `docker exec collector f3d-collector dump-config` | `silo_fill` = 95 ≤ 10 с після кроку 1; = 40 ≤ 5 с після кроку 2 (COV, `cov-increment` 1 %); `collector_bacnet_cov_active{source="BAC-140-BOILER"}` = 2; у `dump-config` `mode: cov` | Сигнали BOILER; `/metrics` |
| ТК-10 | Лічильник води й похідна витрата | ТК-02, ≥ 15 хв роботи | 1) зняти `infra/water/m3_total` двічі з інтервалом 10 хв (Odoo й `GET /sim/v1/signals/infra/water/m3_total`); 2) `infra/water/flow_m3h` | `m3_total` монотонний, збіг з емулятором ±0,01 м³; `flow_m3h` = Δ/Δt за R-08 ±0,05 м³/год; середня за годину ≈ 2,1 м³/год (модель iot_sim R-21, допуск ±50 %) | Показання (графік за 2 доби); Годинні агрегати (`delta`) |
| ТК-11 | Звірка джерела перед увімкненням (Q-05, ризик ARCH §5.2) | ТК-02 | 1) `MB-U90-AI1.read_enabled=False`; 2) `docker exec collector f3d-collector test-source MB-U90-AI1`; 3) порівняти з `/sim/v1/signals?device=DUST-1` і паспортом `equipment_specs.json[role=dust_extraction]` (32 000 м³/год); 4) `read_enabled=True`; 5) тимчасово `range: [0, 5]` в адресі `equipment/SPRINKLERS/pressure_bar`, через ≤ 60 с повернути `[0, 16]` | крок 1: джерело `disabled`, 4 сигнали `stale`; крок 2 друкує 4 значення в допусках ТК-03 і нічого не пише в Odoo (кількість `td.reading` незмінна); крок 4 — `online` ≤ 60 с; крок 5 — показання `quality='bad'`, `last_value` не оновлюється, після повернення — `good` | термінал; Показання, фільтр «Непевні/погані» |
| ТК-12 | Відмова Odoo й буфер | ТК-02 | 1) `docker compose stop odoo19` на 10 хв; 2) `start`; 3) 5 хв | AC-87: `collector_buffer_rows` росте ≈ 12…15/с; `/health` `degraded` після 5 хв; після старту буфер спорожнів ≤ 2 хв; у `td.reading` за вікно простою для кожного прив'язаного сигналу немає проміжку > `store_period_s + period_s`; `collector_push_total{status="rejected"}` = 0 | `/metrics`; Показання (графік без розриву) |
| ТК-13 | ТО за лічильником COMPRESSOR | ТК-02 | 1) закрити заявку «ТО на 18 000 мотогодин» (прив'язана хуком, Додаток C.4) при мотогодинах H; 2) менеджер ставить `td_meter_last_value = H − 1 950`; 3) ≤ 60 с | крок 1: `td_meter_last_value = H`, `td_meter_next_value = H + 2 000`, чаттер; крок 3: заявка «ТО за лічильником: COMPRESSOR — <H+50> год (зараз <H>)», `preventive`, `priority='1'`, `td_meter_request_id` заповнено | COMPRESSOR → вкладка «Сигнали» → «ТО за лічильником»; Заявки |
| ТК-14 | 3D-переглядач | ТК-02; `td_viewer3d` установлено (міст `td_telemetry_viewer3d` — auto_install) | 1) 3D Завод → Переглядач; 2) картка COMPRESSOR; 3) `PUT /sim/v1/signals/equipment/COMPRESSOR/pressure_bar {"value": 6.55, "hold_s": 300}`; 4) картка FL-C1 | AC-89: тиск 6,55 на картці ≤ 15 с без перезавантаження; `meta.iot.source` «телеметрія (td_telemetry)», `alarms` = кількість `alarm`; стан FL-C1 = `last_text` сигналу | 3D-переглядач; DevTools → `/f3d/viewer/delta` |
| ТК-15 | Команди й чотири запобіжники | ТК-02; запис у HR 3100 емулятора дозволено (iot_sim §8.9.3) | 1) менеджер створює сигнал `equipment/COMPRESSOR/setpoint_bar` (`MB-U70-COMPRESSOR`, `{"fc": 3, "addr": 3099, "type": "u16", "scale": 0.001, "write": {"fc": 6, "addr": 3099}}`, `period_s=10`); 2) команда 7,2 при всіх прапорах `False`; 3) по черзі ввімкнути параметр, джерело, сигнал → команда; колектор з `F3D_WRITE_ENABLED=0`; 4) `F3D_WRITE_ENABLED=1`, перезапуск колектора, нова команда; 5) усі прапори `False`, сигнал архівувати | AC-88: крок 2 — `UserError` «Запис у пристрій вимкнено: параметр модуля.»; крок 3 — `queued` → `expired` через 10 хв, чаттер «Колектор не забрав команду»; крок 4 — `done` ≤ 10 с, `result` «fc6 addr 3099 = [7200]», сигнал показує 7,2 ≤ 20 с; для `fire/*` сигналів команду створити неможливо | 3D Завод → Дані → Телеметрія → Команди; `docker logs collector` |
| ТК-16 | HTTP push LPR і стоп-кран прийому | ТК-02 | 1) S-05 `truck_no_booking` `{"gate": "GATE-W"}`; 2) Налаштування → «Приймати показання» вимкнути на 3 хв; 3) увімкнути | AC-90: подія `lpr` з `payload.plateList='none'` у «Події HTTP push» ≤ 15 с; крок 2 — колектор отримує `423` (`collector_push_total{status="locked"}` росте), `last_*` в Odoo не змінюються, опитування призупинені ≤ 60 с; крок 3 — опитування відновились ≤ 60 с, рядки буфера доставлено | 3D Завод → Дані → Телеметрія → Події HTTP push; `/metrics` |

### 13.3 Тести безпеки (ТБ)

| ТБ | Перевірка | Як | Очікувано |
|---|---|---|---|
| ТБ-01 | Токени API | AC-37 + стенд: 100 запитів з випадковими токенами до `config`/`push` | усі `401`; час відповіді не залежить від префікса токена (перебір усіх кандидатів, `compare_digest`); відкликаний/архівний колектор — `401`/`403` |
| ТБ-02 | Секрети не виходять за межі | AC-60, AC-82; стенд: `docker logs collector`, лог Odoo, `GET config` — пошук сирого токена, `F3D_MQTT_PASSWORD`, `F3D_HTTP_PUSH_TOKEN_LPR` | 0 збігів; у `params` лише `*_ref`; `neutralize.sql` стирає хеші (AC-62); токен у майстрі не зберігається в базі (`SELECT * FROM td_collector_token_wizard` — `token` порожній після закриття або рядків немає після GC Transient) |
| ТБ-03 | Доступ без групи і матриця прав | AC-59 за таблицею нижче; UI: `user_plain` не бачить меню «3D Завод → Дані → Телеметрія», URL `/odoo/action-td_telemetry.action_td_signal` → помилка доступу | як у таблиці |
| ТБ-04 | Ін'єкції в коди, адреси, маршрути | AC-08, AC-09, AC-39; push з `code="'; DELETE FROM td_reading; --"` → `bad_code_format`; адреса `{"addr": "3001; DROP"}` → помилка типу; MQTT `path="$.a\"]; drop"` → помилка формату; колектор: `POST /f3d/lpr/../admin`, `/f3d/LPR` → `404`; огляд коду: `grep -rnE "execute\(f\"\|execute\(.*%[^s]\|execute\(.*\.format\(" models tools hooks.py controllers` — 0 збігів | жодних змін у таблицях; помилки валідації |
| ТБ-05 | Запис при `write_enabled=False` (чотири запобіжники) | AC-44, AC-47, AC-75; ТК-15 | параметр/джерело/сигнал `False` → команда не створюється або не видається; `F3D_WRITE_ENABLED=0` → `GET commands` не викликається, `plugin.write` не викликається |
| ТБ-06 | Пожежна панель (dev 200) — жодного запису й лише Who-Is/ReadProperty/ReadPropertyMultiple (D-07, X-05, fire_safety ARCH Q-07) | Odoo: AC-06, AC-47; колектор: AC-81 (`write_count == 0`, журнал сервісів `read_only`); стенд: прив'язати `fire/groups/FA-CUT/state` (LSZ:12, без `mode` — умовч. `cov`) і `fire/groups/FA-FAC/dust` до тимчасового джерела `BAC-200-FACP` (`read_only: true`), решта BACnet-джерел колектора `read_enabled=False` на час тесту (у мережі — лише трафік до dev 200), SQL в обхід перевірок: `write_enabled=true` на джерелі й сигналі, `F3D_WRITE_ENABLED=1`, команда через SQL `INSERT` у `td_command` (`queued`); `tcpdump -i any udp port 47808 -w facp.pcap` на 5 хв; сценарій `fire_drill` емулятора — для подій | команда `failed` «read-only device»; у `facp.pcap` від колектора: `tshark -r facp.pcap -Y "ip.src == <collector> && bacapp.type == 0 && !(bacapp.confirmed_service in {12 14})"` — 0 пакетів (жодних `WriteProperty` 15, `SubscribeCOV` 5, `AcknowledgeAlarm` 0, `LifeSafetyOperation` 27, `DeviceCommunicationControl` 17, `ReinitializeDevice` 20); `-Y "ip.src == <collector> && bacapp.type == 1 && !(bacapp.unconfirmed_service in {0 8})"` — 0 (лише `Who-Is` і `I-Am` власного device-об'єкта колектора); `collector_bacnet_ro_blocked_total` ≥ 0 без помилок процесу; події `UnconfirmedEventNotification` панелі → «Події HTTP push» з `route='bacnet_event'` (AC-97); `GET /sim/v1/events?device=FACP-1` без записів про запис |
| ТБ-07 | Приймач http_push | AC-80; стенд: POST з контейнера поза `allow_ips` → `403`; без секретного суфікса (якщо `F3D_HTTP_PUSH_SECRET_LPR` задано) → `404`; 1 000 запитів за 10 с | відмови; колектор `healthy`, RSS росте < 50 МБ; подій у буфері — лише унікальні |
| ТБ-08 | Контейнер і allow-list колектора | `docker inspect collector`: `User=10002`, `ReadonlyRootfs=true`, `CapDrop=[ALL]`; `docker port collector` порожньо; `F3D_ALLOW_HOSTS=mosquitto` (без `iot-sim`) + `tcpdump host iot-sim` 2 хв | Modbus/BACnet-джерела `error` «хост не в allow-list», 0 пакетів до `iot-sim` |
| ТБ-09 | Health і метрики без даних | AC-42, AC-82, AC-83 | `/f3d/telemetry/health` без токена — 4 ключі; `/metrics` без секретів |
| ТБ-10 | Ліміти | AC-39, AC-41, AC-43; API-03 з 501 джерелом → `413`; API-05 з 101 подією → `413` | коди відмов; Odoo не падає |

Матриця прав (ТБ-03, AC-59): R — читання, W — запис, C — створення, D — видалення; «—» — `AccessError`.

| Модель | `user_plain` | `user_reader` | `user_manager` | `user_admin` |
|---|---|---|---|---|
| `td.collector` | — | R | R | RWCD |
| `td.source` | — | R | RWCD | RWCD |
| `td.signal` | — | R | RWCD | RWCD |
| `td.reading` | — | R | RC (W — `UserError`) | RWCD |
| `td.reading.hour` | — | R | R | RWCD |
| `td.command` | — | R | RWC | RWCD |
| `td.push.event` | — | R | R | RWCD |
| `td.collector.token.wizard` | — | — | — | RWCD |
| `maintenance.equipment.td_meter_*` | — | за правами `maintenance` | за правами `maintenance` | так |

### 13.4 Тести продуктивності (ТП)

Середовище: копія демо на тестовому сервері timur-o19demo (2 воркери Odoo), або локальний Odoo з
PostgreSQL 16; дані генеруються SQL `generate_series` у тестовій базі (не в живій).

| ТП | Що | Обсяг | Межа |
|---|---|---|---|
| ТП-01 | `POST push` (AC-46) | 50 пакетів × 1 000 показань для 55 сигналів; окремо 10 × 2 000 | p95 ≤ 1 с (1 000), ≤ 2 с (2 000); без помилок `500` |
| ТП-02 | `GET config` | 1 000 сигналів на одному колекторі | ≤ 0,5 с; обчислення ETag ≤ 50 мс (лог DEBUG); тіло ≈ 500 КБ; `304` ≤ 0,2 с |
| ТП-03 | Ротація R-10 | 2,4 М показань за 30 діб + 81 000 старших за `keep_days` | `_cron_rotate` ≤ 60 с, видалено 81 000; з 3 М застарілих — зупинка за 60 с, решта наступним прогоном; `EXPLAIN` підзапиту — Index Scan `td_reading_ts_idx` |
| ТП-04 | Розмір таблиць | після ТП-03 | `pg_total_relation_size('td_reading')` ≤ 350 МБ (оцінка ARCH §2.7 — 310 МБ); `td_reading_hour` 2,2 М рядків ≤ 260 МБ |
| ТП-05 | Агрегати R-09 | 225 сигналів, вікно 48 год (≈ 130 000 показань) | `_cron_aggregate` ≤ 30 с |
| ТП-06 | Колектор під навантаженням стенда | 1 год, ≈ 15 показань/с | CPU ≤ 20 % одного ядра, RSS ≤ 150 МБ, `collector_push_latency_seconds` p95 ≤ 0,5 с; після 10 хв простою Odoo (ТК-12) 54 000 рядків доставлено ≤ 2 хв |
| ТП-07 | Графік «Показання» | 2,4 М рядків, один сигнал, 48 год | дія `action_td_reading` з фільтром `last_48h` відкривається ≤ 2 с (`read_group` за `signal_id`, `ts:hour`) |

### 13.5 Чек-лист DEPLOY_TEST (`docs/modules/td_telemetry/DEPLOY_TEST.md`, здає W7)

1. Дамп бази `odoo` тестового сервера timur-o19demo (`pg_dump -Fc`), відновити як `odoo_f3d_tel`; на копії
   встановити `td_factory3d` за його DEPLOY_TEST (коди `FL-1`…, `COMPRESSOR`, `WATER` у `td_code`).
2. Знімки: S0 `SELECT count(*) FROM x_f3d_reading WHERE x_time IS NOT NULL`; S1 `SELECT x_code, x_value, x_state,
   x_request_id FROM x_f3d_signal ORDER BY x_code`; S2 `SELECT id, name, stage_id, maintenance_type FROM
   maintenance_request ORDER BY id`; S3 `SELECT c.active FROM ir_cron c JOIN ir_model_data d ON d.res_id = c.id AND
   d.model = 'ir.cron' WHERE d.module = 'td_iot_sim' AND d.name = 'cron_iot_sim'`.
3. Установка (ТК-01): `-i td_telemetry --log-level=info`; зафіксувати час і звіт `level0_migrated`;
   `readings_migrated == S0`; S2 — ті самі id/назви (додались лише поля `td_*`).
4. Юніт-тести на копії: `--test-tags /td_telemetry` → 0 падінь (класи синтетичного рівня 0 пропущені за
   `skipIf`, AC-58 — у ТК-01).
5. Стенд: ТК-02…ТК-16 з колектором і емулятором, протокол у `TEST_REPORT.md`.
6. Повтор міграції (Налаштування → «Повторити міграцію рівня 0») → `created: 0`, кількості незмінні.
7. Деінсталяція: `x_f3d_signal.x_active = true` для 196, меню «Імітація IoT» видно, `cron_iot_sim` лишається
   вимкненим (S3 не відновлюється автоматично — рішення адміністратора), S2 — ті самі заявки; таблиць `td_*` немає.
   Повторна установка → ТК-01 зелений, `readings_migrated` = поточний S0.
8. Нейтралізація: `psql -d odoo_f3d_tel -f data/neutralize.sql` (разом із base/viewer/iot_sim) → колектор отримує
   `401`, параметри `False`, крони модуля вимкнені, джерела `disabled`.
9. Відкат: видалити `odoo_f3d_tel`; жива база `odoo` не змінювалась. На живій базі відкат = деінсталяція (п. 7) +
   ручне ввімкнення `cron_iot_sim` (A-07: рівень 0 вимикається, а не видаляється).
10. Фактичні кількості, час хука й результати ТК/ТП — у `CHANGELOG.md` (розділ «Міграція демо») і `TEST_REPORT.md`.

## 14. Definition of Done

- Усі юніт-тести §13.1.1 зелені на чистій базі (`--without-demo=all`) і на копії демо (`--test-tags
  /td_telemetry,/td_telemetry_viewer3d`); тести колектора §13.1.2 зелені (`pytest -m "not stand"`,
  `-m broker` — де є Docker, Q-16).
- Кожен AC-01…AC-104 має зелений тест (UT/HT/CT) або відмітку ТК/MAN з датою в `TEST_REPORT.md`; ТК-01…ТК-16,
  ТБ-01…ТБ-10, ТП-01…ТП-07 пройдені на стенді з фактичними значеннями.
- `ruff check` (Odoo-модуль і `services/collector`, довжина рядка 120) і `ruff format --check` без помилок;
  `pylint-odoo` (якщо є в репозиторії) без помилок рівня error; `mypy services/collector/collector` без помилок.
- Жодного `x_`-поля в коді модуля: `grep -rn "x_f3d\|x_code\|x_value" odoo_addons/td_telemetry --include=*.py
  --include=*.xml` знаходить лише `hooks.py` і `tests/` (міграція); жодного `TODO`/`TBD`.
- `data/neutralize.sql` виконується без помилки (AC-62); `uninstall_hook` перевірено (AC-57, §13.5 п. 7).
- Перегляд безпеки §13.3 пройдено: токени (хеш, `compare_digest`, не в логах), SQL лише параметризований, адреси й
  параметри валідуються до збереження, секрети — лише `*_ref`, пожежна панель — жодного запису (ТБ-06).
- `services/collector`: образ збирається (`docker build`), `HEALTHCHECK` зелений, контейнер non-root і `read_only`,
  версії залежностей закріплені `==` у `requirements.txt` (§8.1.2).
- Документація: `README.md` модуля (установка, параметри §5.1, інструкції ARCH §4.1–§4.6), `services/collector/README.md`
  (env §8.2, порти, CLI), `CHANGELOG.md` (`19.0.1.0.0`; `19.0.1.1.0` — CR-01 і правки за CONSISTENCY.md X-xx; розділ «Міграція демо» з фактичними кількостями),
  `DEPLOY_TEST.md`, `TEST_REPORT.md`.
- Контракти CT-01…CT-12 реалізовано з точними іменами цього документа; будь-яка зміна імен — лише через оновлення
  SPEC і повідомлення авторів energy/bms/fire_safety/machine_connect/yard/access/td_genset.

## 15. Відкриті питання

Ті самі Q-01…Q-17, що в ARCH §5.1 (нумерація спільна); тут — що робить код, поки відповіді немає.

| ID | Поки немає відповіді |
|---|---|
| Q-01 | **Закрито 14.10 (рішення менеджера):** після: TimescaleDB — коли `td_reading` > 20 М рядків або потрібні ряди 1 с. TimescaleDB немає; `Sink` зарезервовано (§8.3.6); сирі ряди 1 с у `td.reading` не пишуться |
| Q-02 | **Закрито 14.10 (рішення менеджера):** ні — емулятор говорить лише протоколами (D-01). емулятор у `td.reading` напряму не пише; рівень 0 вимикається лише хуком цього модуля |
| Q-03 | закрито: `BAC-140-BOILER` і адреси котельні — у Додатку C; `return_c`, `state` котельні створює bms через CT-11 |
| Q-04 | **закрито X-42** (D-20): адреси — PDU за документом вендора, без загального «номер − 1»; каталог iot_sim отримує явну PDU-нотацію `u<unit> fc<n> pdu<addr>`; парсер R-24 бере її як є, інакше застосовує правило за вендором; позначки `[notation?]` немає; звірка — ТК-03 |
| Q-05 | **Закрито 14.10 (відповідь № 8, CONSISTENCY):** ТО за лічильником: компресор 2 000 мотогодин, навантажувачі й тягач 1 000. адреси Elektronikon — з iot_sim §8.9.3 (ПРИПУЩЕННЯ), лише в даних (Додаток C.2); перед увімкненням заліза — ТК-11 |
| Q-06 | **Закрито 14.10 (відповідь № 8, CONSISTENCY):** пороги заряду техніки 25 % / 15 %. інтервали ТО — Додаток C.4 (COMPRESSOR 2 000 год, техніка 1 000 год); наявні відкриті планові заявки прив'язуються до ТО за лічильником (A-22) |
| Q-07 | **Закрито 14.10 (відповідь № 8, CONSISTENCY):** прийнято рекомендовану відповідь. техніка: `warn_low=25` без заявки, `alarm_low=15` із заявкою (Додаток C.2) |
| Q-08 | **закрито X-28**: координати техніки в 3D — фаза 4; до того `equipment/<код>/x`, `/y` зберігаються з `viewer_visible=False`, провайдер їх не віддає |
| Q-09 | **Закрито 14.10 (рішення менеджера):** джерело істини — лічильник PM5560 (energy). сигнали `energy/*` лишаються `sim_data` без джерела до прив'язки energy |
| Q-10 | **Закрито 14.10 (відповідь № 15, CONSISTENCY):** сирі показання — 30 діб, агрегати — 400 діб. `keep_days=30`, `keep_hours_days=400`, лічильники — `period_s` 60 с (Додаток C.2) |
| Q-11 | **Закрито 14.10 (відповідь № 8, CONSISTENCY):** «мовчання» пристроїв — лише на дашборді, без сповіщень і заявок. `stale` — лише стан і дашборд; `stale_notify_min=0` (вимкнено) |
| Q-12 | **закрито X-21**: каркас v0.2 містить D-13 (рівень 0), D-14 (рядки UI в коді), D-16 (`bacnet_ip` у telemetry, §6.5) — діємо за ними |
| Q-13 | **Закрито 14.10 (відповідь № 17, CONSISTENCY):** приймач LPR — allow-list IP + секретний шлях. на стенді — allow-list `iot-sim`; секретний суфікс підтримується (`F3D_HTTP_PUSH_SECRET_LPR`, порожньо = вимкнено) |
| Q-14 | **закрито X-58**: параметр сценарію `filter_clogged` — лише `value` (iot_sim §9.3; приклад §7.2 виправляє iot_sim); ТК-05/ТК-06 передають тільки `value` |
| Q-15 | **закрито X-48** (рішення збігається з поточним кодом): час події http_push — з `address.ts_path` (`$.capture_timestamp`, епоха мс UTC); значення, що дає `ts_future`/`ts_too_old`, замінюється часом прийому (`td.reading.received_at`, X-83) з `q='uncertain'` (R-22); приклад iot_sim §8.13.2 виправляє iot_sim |
| Q-16 | **Закрито 14.10 (рішення менеджера):** так — CI-раннер із Docker, `pytest -m broker`. тести `-m broker` пропускаються без `F3D_TEST_MQTT`/Docker; MQTT покрито фейковим клієнтом (AC-79) і ТК-04 |
| Q-17 | **Закрито 14.10 (рішення менеджера):** стенд — на timur-o19demo, compose-профіль `dev`, окрема база-копія `odoo_f3d_tel`. ТК виконуються локально: compose iot_sim (профіль `dev`) + колектор + контейнер Odoo 19 з дампом копії демо |

## Додаток A. Схеми `address` і `params` за типом джерела (CT-03, A-01)

Реалізація: Odoo — чисті функції `tools/address.py` (`validate_address(type, address) -> list[str]`,
`validate_params(type, params) -> list[str]`, без `jsonschema`); колектор — `plugins/schemas/address.<type>.json`,
`params.<type>.json` (JSON Schema draft 2020-12, той самий зміст). Модуль-власник плагіна може додавати ключі, але не
змінювати обов'язкові (CT-03).

### A.0 Спільні правила

- `address` і `params` — JSON-об'єкти; інше → «адреса має бути об'єктом JSON» / «параметри мають бути об'єктом JSON».
- `address == {}` — «не налаштовано»: зберігається без перевірки, сигнал не потрапляє в API-01. Сигнал без
  `source_id` — адреса не перевіряється.
- Невідомі ключі дозволені (розширення модулів; довідковий перелік ключів-розширень власників — нижче в A.1/A.2,
  X-52); ключі, що починаються з `_`, — заборонені. Виняток: тип, схема власника якого забороняє додаткові ключі
  (`sics` — yard §8.2, `additionalProperties: false`, X-45): невідомий ключ → «<ключ>: невідомий ключ (схема sics не
  допускає додаткових)».
- **Спільні ключі `address` для всіх типів** (X-63): `scale` (number, ≠ 0, умовч. 1) і `offset` (number, умовч. 0) —
  лінійне перетворення, яке застосовує **плагін** (`eng = raw·scale + offset`, R-02); для `sics` вони теж дозволені
  (виняток із `additionalProperties: false`). `signal.scale` (M-03) — окремий множник, його застосовує ядро колектора
  (§8.3.3) або R-22.
- `type` поза 8 типами CT-03: якщо він у `local_types` (R-26, `td.source._td_local_types()`) — `params` лише
  перевіряється як об'єкт JSON без ключів-секретів, `address` не перевіряється зовсім; інакше → «type: невідомий тип
  джерела «<type>»».
- Секрети в Odoo не зберігаються: ключі `password`, `token`, `secret`, `api_key`, `key` у `params` → помилка
  «<ключ>: секрети не зберігаються в Odoo — використайте <ключ>_ref»; `*_ref` — ім'я змінної середовища колектора,
  `^F3D_[A-Z0-9_]{1,60}$`.
- Тексти помилок (кожна — один рядок `"<ключ>: <проблема>"`): «обов'язковий»; «має бути ціле число|число|рядок|
  булеве|список|об'єкт»; «поза межами <lo>…<hi>»; «недопустиме значення «<v>»; дозволено: <a, b, c>»; «не відповідає
  формату <опис>». `ValidationError` моделі об'єднує їх через «; » (§2 M-02, M-03).
- Рядки ≤ 1 024 символи, весь JSON ≤ 8 КБ; числа скінченні (не NaN/inf).
- `host` — ім'я DNS (`^[A-Za-z0-9]([A-Za-z0-9\-\.]{0,251}[A-Za-z0-9])?$`) або IPv4/IPv6; JSONPath (`path`, `ts_path`,
  `json_path`, `status_online_path`) — `^\$(\.[A-Za-z_][A-Za-z0-9_\-]*|\[[0-9]+\])+$`.

### A.1 `address` сигналу

**`modbus_tcp`** (приклад: `{"fc": 3, "addr": 3001, "type": "u16", "scale": 0.001, "range": [0, 16], "doc": "HR 3002 Outlet pressure"}`)

| Ключ | Тип | Обов. | За замовч. | Обмеження |
|---|---|---|---|---|
| `fc` | int | так | — | 1, 2, 3, 4 |
| `addr` | int | так, якщо немає `states` | — | 0…65535, **PDU** (A-01) |
| `unit` | int | ні | `params.unit` | 1…247 |
| `type` | str | ні | `u16` (fc 3/4), `bool` (fc 1/2) | `bool, u16, i16, u32, i32, f32, u64, i64, f64`; для fc 1/2 — лише `bool` |
| `count` | int | ні | ширина типу (1/2/4; `bool` — 1) | 1…125; кратне ширині; більше ширини — лише з `agg` |
| `agg` | str | ні | — | `max, min, sum, avg, first` |
| `wordorder`, `byteorder` | str | ні | `big` | `big, little` |
| `bit` | int | ні | — | 0…15; лише з `type=bool` і fc 3/4 |
| `scale`, `offset` | number | ні | 1 / 0 | `scale ≠ 0`; спільні ключі A.0 (застосовує плагін, X-63) |
| `range` | [number, number] | ні | — | `lo < hi`; поза межами → `q='bad'` |
| `map` | object | ні | — | ключі — цілі як рядки, значення — рядки ≤ 64 |
| `states` | list | ні | — | 1…16 елементів `{"addr": 0…65535, "eq": int, "text": str ≤ 64, "fc"?: 1…4}`; перший збіг |
| `write` | object | ні | — | `{"fc": 5, 6 або 16, "addr": 0…65535, "pulse_ms"?: 100…10 000}`; `pulse_ms` (X-46) — необов'язковий, лише з `fc` 5 або 6 і лише для імпульсних команд: плагін пише 1, через `pulse_ms` — 0, значення команди ігнорується (§8.5); yard ставить `1500` на `cmd_open`/`cmd_close` (CAME ≥ 1 с); рівневі записи — без `pulse_ms`: пишеться значення команди, вихід тримається до скидання наступною командою (yard `cmd_hold`, X-81) |
| `doc` | str | ні | — | ≤ 256, вендорська нотація (довідково) |

**`mqtt`** (приклад: `{"topic": "f3d/mobile/FL-1/telemetry", "path": "$.battery_pct", "ts_path": "$.ts", "device": "FL-1"}`)

| Ключ | Тип | Обов. | За замовч. | Обмеження |
|---|---|---|---|---|
| `topic` | str | так | — | ≤ 256, без `+`/`#`, рівні непорожні, без `\x00` |
| `path` | str | так | — | JSONPath A.0 |
| `ts_path` | str | ні | час отримання колектором | JSONPath A.0; значення ISO 8601 або епоха с/мс |
| `device` | str | ні | — | ≤ 32 |
| `map` | object | ні | — | рядок → рядок ≤ 64 |
| `write` | object | ні | — | `{"topic": str без wildcard, "template": str ≤ 1024 з {value} або {text}}` |

**`http_push`** (приклад — `sig_plate`, §13.0): `route*` (`^[a-z][a-z0-9_]{0,31}$`), `path*` (JSONPath), `match`
(об'єкт: ключ → рядок/число/булеве; усі мають збігтися з `payload`), `ts_path` (JSONPath; час пристрою — для відображення й
дедуплікації; без нього або поза вікном — `ts = received_at`, час прийому в Odoo, R-22, X-83).

**`bacnet_ip`** (приклад: `{"object": "analog-input", "instance": 1, "property": "present-value", "mode": "cov", "cov_increment": 0.2}`)

| Ключ | Тип | Обов. | За замовч. | Обмеження |
|---|---|---|---|---|
| `object` | str | так | — | `analog-input, analog-output, analog-value, binary-input, binary-output, binary-value, multi-state-input, multi-state-value, life-safety-zone, life-safety-point, positive-integer-value, device` або `AI, AO, AV, BI, BO, BV, MSI, MSV, LSZ, LSP, PIV` (нормалізує плагін; PIV — X-37, Cerberus FC726) |
| `instance` | int | так | — | 0…4194302 |
| `property` | str | ні | `present-value` | `^[a-z][a-z0-9\-]{0,63}$` |
| `index` | int | ні | — | ≥ 0 |
| `device` | int | ні | `params.device` | має дорівнювати `params.device` |
| `mode` | str | ні | `cov` для AI/BI/MSI/MSV/LSZ/LSP, `poll` для решти (у т.ч. PIV) | `cov, poll`; на джерелі з `params.read_only=true` діє як `poll` завжди (X-05); `cov` → `stale` від `cov_check_s(period_s)` (R-07, X-06) |
| `cov_increment` | number | ні | — | > 0 (довідково) |
| `priority` | int | ні | 8 | 1…16 (лише запис) |
| `map` | object | ні | — | рядок → рядок; ключ — номер стану (MSV 1-based); при записі стану — зворотний `map` (X-66) |
| `states` | list | ні | — | складений стан: `{"object", "instance", "eq", "text"}`, 1…16 |
| `scale`, `offset` | number | ні | 1 / 0 | спільні ключі A.0 (X-63) |
| `check_reliability`, `read_priority_array` | bool | ні | `false` | — |

**`opcua`** (власник плагіна — machine_connect): `nodeid*` (`^ns=\d+;[sigb]=.{1,240}$`), `mode` (`subscribe` |
`poll`, умовч. `subscribe`), `sampling_ms` (0…60000), `map`. Ключі-розширення (X-52; **довідково** — власник і
перевірка повної схеми — machine_connect SPEC §8.3, A-16, CM-06; валідатор telemetry їх лише пропускає за A.0):
`ns_uri` (URI простору екземплярів; перекриває `params.ns_uri`), `events` (bool, лише з `mode="subscribe"`), `io`
(`read` — умовч. | `write` — сигнал лише для команд, не підписується), `call` (`"job"` — команда CMD-01), `job_select`
(`"running_or_first"` — для `JobOrderList`), `ww_uri` (умовч. `http://opcfoundation.org/UA/Woodworking/`), `isa_uri`
(умовч. `http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/`).
**`helvarnet`** (bms): один із `group` (1…16383) або `device` (`^@\d+\.\d+\.\d+\.\d+$`) обов'язковий; `query`
(рядок, умовч. `level`), `map`. Ключі-розширення (X-52; довідково — власник bms SPEC §8.2.2, CH-05): `query` ∈ {`level`,
`power`, `scene`, `faults`, `faulty`, `router`}, `devices` (список `@c.r.s.d` / `@c.r.s.d1-d2`, ≤ 64), `sample` (1…16,
умовч. 3), `mask` (ціле, умовч. 134217742), `scale` (спільний ключ A.0; для `power` — 0,001: Вт → кВт, застосовує плагін,
R-02/X-63), `fade_s` (умовч. 2,0), `block` (1…8, умовч. 1).
**`sics`** (власник — yard; копія схеми yard SPEC §8.2 `address.sics.json`, X-45; `additionalProperties: false`, крім
спільних `scale`/`offset` A.0): `field*` ∈ {`weight`, `stable`}; `cmd` ∈ {`SI`} (умовч. `SI`); `write` — об'єкт
`{"cmd"*: "Z" | "T" | "TAC"}` без інших ключів (запис `TA` заборонено); `doc` (рядок ≤ 128). Приклад:
`{"field": "weight", "doc": "SI вага брутто"}`.
**`rest_vendor`** (machine_connect, access): `method` (`GET` | `POST`, умовч. `GET`), `path*` (`^/\S{0,255}$`),
`json_path*` (JSONPath), `query` (об'єкт рядок → рядок/число), `map`. Ключі-розширення (X-52; довідково — machine_connect
SPEC §8.4, CM-06): `cmd` (`gantry` | `cutopt` — сигнал команд, не опитується), `default` (значення, якщо `json_path`
нічого не знайшов; умовч. — пропуск показання), `io` (`read` | `write`).

### A.2 `params` джерела (приклади — валідні значення для AC-04)

| Тип | Ключі (`*` — обов'язкові; умовчання) | Приклад |
|---|---|---|
| `modbus_tcp` | `host*`; `port` 1…65535 (502); `unit` 1…247 (1); `timeout_s` 0,5…60 (3); `retries` 0…5 (2); `max_block` 1…125 (125); `gap_max` 0…32 (8) | `{"host": "iot-sim", "port": 502, "unit": 70, "timeout_s": 3, "retries": 2, "max_block": 100}` |
| `mqtt` | `host*`; `port` (1883); `username`; `password_ref`; `client_id*` (`^[A-Za-z0-9_\-]{1,64}$`); `topics*` (1…32 фільтри; `#` лише останнім рівнем, `+` — цілий рівень); `status_topic` (з `{device}`); `status_online_path` (`$.online`); `keepalive_s` 5…600 (30); `tls` (false); `qos` 0…1 (1) | як у §7 API-01 |
| `http_push` | `routes*` (1…16 значень `^[a-z][a-z0-9_]{0,31}$`); `allow_ips` (список хостів/IP/CIDR); `token_ref`; `secret_ref`; `max_body_kb` 1…1024 (1024) | `{"routes": ["lpr"], "allow_ips": ["iot-sim"], "token_ref": "F3D_HTTP_PUSH_TOKEN_LPR", "secret_ref": "F3D_HTTP_PUSH_SECRET_LPR"}` |
| `bacnet_ip` | `host*`; `port` (47808); `device*` 0…4194302; `address` (BACnet-адреса ≤ 64, напр. `2:0x0a000005bac0`); `network` 1…65534; `timeout_s` 1…60 (5); `rpm` (true); `rpm_max` 1…200 (50); `cov_lifetime_s` 60…3600 (300); `read_only` (false) — пристрій лише для читання (D-07, X-05): плагін ініціює лише `Who-Is`, `ReadProperty`, `ReadPropertyMultiple`, інші сервіси (у т.ч. `SubscribeCOV`, `AcknowledgeAlarm`, `LifeSafetyOperation`, `WriteProperty*`, `DeviceCommunicationControl`, `ReinitializeDevice`) блокуються в коді до відправки, `mode=cov` діє як `poll`; запис і `write_enabled` заборонені (M-02, M-03); `events` (bool; умовч. = значення `read_only`, A-23) — ретранслювати `UnconfirmedEventNotification` пристрою в API-05 з `route="bacnet_event"` (§8.8, fire_safety API-01) | `{"host": "iot-sim", "port": 47808, "device": 140, "network": 2, "timeout_s": 5, "rpm": true, "rpm_max": 50, "cov_lifetime_s": 300}` |
| `opcua` | `endpoint*` (`^opc\.tcp://`); `security_mode` (`None` \| `Sign` \| `SignAndEncrypt`; `None`); `security_policy` (`None` \| `Basic256Sha256` \| `Aes128_Sha256_RsaOaep` \| `Aes256_Sha256_RsaPss`); `username`; `password_ref`; `cert_ref`; `key_ref`; `timeout_s` (5); `publishing_interval_ms` 50…60000 (1000). Ключі-розширення (X-52, довідково — machine_connect SPEC §8.3, A-16): `ns_uri` (URI простору екземплярів; на стенді `http://todo.ltd/f3d/iot_sim/instances/`), `app_uri` (`urn:todo.ltd:f3d:collector`), `server_cert_ref`, `heartbeat_s` 10…600 (60) | `{"endpoint": "opc.tcp://iot-sim:4840/f3d/", "security_mode": "None"}` |
| `helvarnet` | `host*`; `port` (50000); `protocol` (`tcp` \| `udp`; `tcp`); `timeout_s` (3). Ключі-розширення (X-52, довідково — bms SPEC §8.2.1, CH-05): `cluster` 1…253 (1), `router` 1…254, `version` 1 \| 2 (2), `rate_per_s` 1…100 (20), `push` (true), `membership_ttl_s` 60…86 400 (3600) | `{"host": "iot-sim", "port": 50000, "protocol": "tcp"}` |
| `sics` | копія схеми yard SPEC §8.2 `params.sics.json` (X-45; `additionalProperties: false`): `host*` (рядок 1…253); `port` 1…65535 (4001); `mode` (`stream` \| `poll`; `stream`); `period_s` 0,2…60 (1); `timeout_s` 0,5…30 (**5** — одне умовчання з yard); `unit` (`kg` \| `t` \| `lb` \| `g`; `kg`); `dialect` (`mt_sics`; `mt_sics`); `reset_on_connect` (true) | `{"host": "iot-sim", "port": 4001}` |
| `rest_vendor` | `base_url*` (`^https?://`); `auth` (`none` \| `api_key` \| `bearer` \| `basic`; `none`); `header` (`X-Api-Key`); `key_ref`; `user`; `password_ref`; `verify_tls` (true); `timeout_s` 1…60 (5). Ключі-розширення (X-52, довідково — machine_connect SPEC §8.4, CM-06): `vendor` (`woodstore` \| `cutopt` \| `generic`; `generic`), `events_period_s` 1…60 (2), `stacks_period_s` 5…600 (30), `jobs_period_s` 2…600 (10) | `{"base_url": "http://iot-sim:8082", "auth": "api_key", "key_ref": "F3D_WOODSTORE_KEY"}` |

## Додаток B. Сигнали рівня 0: власник, пороги, хто прив'язує джерело

Джерело — жива база timur-o19demo (база `odoo`, 14.10.2026, лише читання), `plant/odoo_flows.py:signal_specs`.
`module` — за R-15; пороги — з `x_alarm`/`x_threshold` (R-15); «прив'язує» — хто ставить `source_id`/`address`.

| Група коду | Кількість | `x_mode` | `module` | Пороги рівня 0 | Прив'язує |
|---|---|---|---|---|---|
| `energy/consumers/<РЦ>/p_now` | 35 | `machine` | energy | — | energy (PM5560, P-05) |
| `energy/consumers/<інженерні>/p_now` (GANTRY-1, COMPRESSOR, DUST-1, BOILER, CHARGING) | 5 | `noise` | energy | — | energy |
| `energy/consumers/*/kwh_shift` | 40 | `energy` | energy | — (`derived_from` = `p_now`) | energy |
| `energy/transformers/T1/p_kw`, `…/T2/p_kw` | 2 | `noise` | energy | — | energy |
| `energy/transformers/T1/temp_c`, `…/T2/temp_c` | 2 | `noise` | energy | `above` 140 (відповідь № 24; попередження 130 додає хук energy) | **telemetry** (ADAM-6015 u96, Додаток C.2) |
| `infra/totals/pv_now`, `chp_kw`, `bess_soc` | 3 | `solar`, `noise` | energy | — | energy |
| `equipment/<техніка>/battery` (8) | 8 | `drain` | telemetry | — (дані: 25/15, Q-07) | **telemetry** (MQTT) |
| `equipment/<техніка>/hours` (8) | 8 | `hours` | telemetry | — | **telemetry** (MQTT) |
| `equipment/GANTRY-1/cycles_today`, `vacuum_kpa` | 2 | `counter`, `noise` | telemetry | `vacuum_kpa` `above` −60 | machine_connect (woodStore P-03) |
| `equipment/COMPRESSOR/pressure_bar`, `load`, `hours` | 3 | `noise`, `hours` | telemetry | `pressure_bar` `below` 6,0 | **telemetry** (u70) |
| `equipment/DUST-1/airflow_m3h`, `filter_dp_kpa` | 2 | `noise`, `drift` | telemetry | `filter_dp_kpa` `above` 1,8 | **telemetry** (u90) |
| `equipment/BOILER/supply_c`, `silo_fill` | 2 | `noise`, `level` | telemetry | — | **telemetry** (BACnet dev 140) |
| `equipment/SPRINKLERS/pressure_bar` | 1 | `noise` | telemetry | `below` 6,5 | **telemetry** (u90) |
| `equipment/AIR-RING/pressure_bar` | 1 | `noise` | telemetry | `below` 6,0 | **telemetry** (u90) |
| `ventilation/units/<RV-01…25, AHU-1>/filter_dp_pa` | 26 | `drift` | bms | `above` 250 | bms (BACnet dev 101–130) |
| `ventilation/units/*/supply_c` | 26 | `noise` | bms | — | bms |
| `ventilation/units/*/airflow_m3h` | 29 | `noise` | bms | — | bms |
| `fire/groups/FA-FAC/dust` | 1 | `drift` | fire_safety | `above` 90 | fire_safety (BACnet dev 200, лише читання) |
| **Разом** | **196** | | energy 87, bms 81, telemetry 27, fire_safety 1 | 34 з порогами | telemetry — 27 |

## Додаток C. Дані стенда

### C.1 Джерела (`data/td_source_data.xml`, усі `collector_id=collector_main`, `module='telemetry'`, `read_enabled=True`, `write_enabled=False`)

| xml-id | `code` | `type` | `name` | `params` | `equipment_id` |
|---|---|---|---|---|---|
| `source_mqtt_mobile` | `MQTT-MOBILE` | `mqtt` | Телематика техніки (MQTT) | `{"host": "mosquitto", "port": 1883, "username": "collector", "password_ref": "F3D_MQTT_PASSWORD", "client_id": "f3d-collector", "topics": ["f3d/mobile/+/telemetry", "f3d/mobile/+/status"], "status_topic": "f3d/mobile/{device}/status", "status_online_path": "$.online", "keepalive_s": 30, "tls": false}` | — |
| `source_mb_u70_compressor` | `MB-U70-COMPRESSOR` | `modbus_tcp` | Компресор Elektronikon Mk5 (u70) | `{"host": "iot-sim", "port": 502, "unit": 70, "timeout_s": 3, "retries": 2, "max_block": 100}` | COMPRESSOR |
| `source_mb_u84_io5` | `MB-U84-IO5` | `modbus_tcp` | ADAM-6050 IO-5: аспірація, вода (u84) | `{"host": "iot-sim", "port": 502, "unit": 84, "timeout_s": 3, "retries": 2}` | — |
| `source_mb_u90_ai1` | `MB-U90-AI1` | `modbus_tcp` | ADAM-6017 AI-1: аспірація, спринклери, пневмокільце (u90) | `{"host": "iot-sim", "port": 502, "unit": 90, "timeout_s": 3, "retries": 2}` | — |
| `source_mb_u96_rtd1` | `MB-U96-RTD1` | `modbus_tcp` | ADAM-6015 RTD-1: трансформатори (u96) | `{"host": "iot-sim", "port": 502, "unit": 96, "timeout_s": 3, "retries": 2}` | — |
| `source_bac_140_boiler` | `BAC-140-BOILER` | `bacnet_ip` | Котельня Kalvis (BACnet dev 140) | `{"host": "iot-sim", "port": 47808, "device": 140, "network": 2, "timeout_s": 5, "rpm": true, "rpm_max": 50, "cov_lifetime_s": 300}` | BOILER |
| `source_http_push` | `HTTP-PUSH` | `http_push` | Приймач HTTP push (Axis LPV) | `{"routes": ["lpr"], "allow_ips": ["iot-sim"], "token_ref": "F3D_HTTP_PUSH_TOKEN_LPR", "secret_ref": "F3D_HTTP_PUSH_SECRET_LPR"}` | — |

`equipment_id` у XML не ставиться (обладнання з кодами з'являється після міграції base); хук крок 3 ставить його за
`search_f3d(code)`, якщо порожнє.

### C.2 `data/signal_catalog.csv` (56 рядків)

`<C>` ∈ {`FL-1`, `FL-2`, `FL-3`, `FL-4`, `FL-5`, `FL-C1`, `FL-C2`, `TUGGER-1`} — генератор розгортає рядок у 8.
Пороги: `alarm_low=15` означає `alarm_low=15`, `alarm_low_on=True`. Порожня клітинка = «не змінювати» (`new=0`) або
умовчання поля (`new=1`). Для `new=1`: `origin='catalog'`, `module` за R-15, `equipment` = сегмент коду (крім
`infra/water/*` → `WATER`).

| № | `code` | `new` | `name` / `quantity`; `kind`, `unit` | `source`; `address` | `period_s` / `store_period_s`; `decimals` | Пороги, `hysteresis`, `min_duration_s`; `states` / `alarm_states`; `alarm_title`; інше |
|---|---|---|---|---|---|---|
| 1–8 | `equipment/<C>/battery` | 0 | — | `MQTT-MOBILE`; `{"topic": "f3d/mobile/<C>/telemetry", "path": "$.battery_pct", "ts_path": "$.ts", "device": "<C>"}` | 5 / 300; 1 | `warn_low=25`, `alarm_low=15`, `hysteresis=1`; «Зарядити АКБ: заряд {value} % при нормі від {threshold}» |
| 9–16 | `equipment/<C>/hours` | 0 | — | `MQTT-MOBILE`; `{…, "path": "$.hours", …}` | 5 / 300; 1 | — |
| 17 | `equipment/COMPRESSOR/pressure_bar` | 0 | — | `MB-U70-COMPRESSOR`; `{"fc": 3, "addr": 3001, "type": "u16", "scale": 0.001, "range": [0, 16], "doc": "HR 3002 Outlet pressure"}` | 10 / 300; 2 | `hysteresis=0.1`, `min_duration_s=30` (поріг 6,0 — з міграції) |
| 18 | `equipment/COMPRESSOR/load` | 0 | — | `MB-U70-COMPRESSOR`; `{"fc": 3, "addr": 3009, "type": "u16", "range": [0, 100], "doc": "HR 3010 Load (VSD output)"}` | 10 / 300; 0 | — |
| 19 | `equipment/COMPRESSOR/hours` | 0 | — | `MB-U70-COMPRESSOR`; `{"fc": 3, "addr": 3019, "type": "u32", "doc": "HR 3020–3021 Running hours"}` | 60 / 300; 1 | — |
| 20 | `equipment/DUST-1/airflow_m3h` | 0 | — | `MB-U90-AI1`; `{"fc": 3, "addr": 0, "type": "u16", "scale": 0.4882887, "offset": 0, "range": [0, 32000], "doc": "HR 40001 AI0 4–20 мА = 0…32 000 м³/год"}` | 10 / 300; 0 | — |
| 21 | `equipment/DUST-1/filter_dp_kpa` | 0 | — | `MB-U90-AI1`; `{"fc": 3, "addr": 1, "type": "u16", "scale": 0.0000610361, "range": [0, 4], "doc": "HR 40002 AI1 4–20 мА = 0…4 кПа"}` | 10 / 300; 2 | (поріг 1,8 і `hysteresis` 0,036 — з міграції) |
| 22 | `equipment/SPRINKLERS/pressure_bar` | 0 | — | `MB-U90-AI1`; `{"fc": 3, "addr": 2, "type": "u16", "scale": 0.0002441444, "range": [0, 16], "doc": "HR 40003 AI2 4–20 мА = 0…16 бар"}` | 10 / 300; 2 | — |
| 23 | `equipment/AIR-RING/pressure_bar` | 0 | — | `MB-U90-AI1`; `{"fc": 3, "addr": 3, …той самий масштаб…, "doc": "HR 40004 AI3 4–20 мА = 0…16 бар"}` | 10 / 300; 2 | — |
| 24 | `energy/transformers/T1/temp_c` | 0 | — | `MB-U96-RTD1`; `{"fc": 3, "addr": 0, "count": 3, "agg": "max", "type": "u16", "scale": 0.0030518044, "offset": -50, "range": [-50, 150], "doc": "HR 40001–40003 RTD0–2, макс."}` | 30 / 300; 1 | — |
| 25 | `energy/transformers/T2/temp_c` | 0 | — | `MB-U96-RTD1`; `{"fc": 3, "addr": 3, …, "doc": "HR 40004–40006 RTD3–5, макс."}` | 30 / 300; 1 | — |
| 26 | `equipment/BOILER/supply_c` | 0 | — | `BAC-140-BOILER`; `{"object": "analog-input", "instance": 1, "property": "present-value", "mode": "cov", "cov_increment": 0.2, "doc": "AI:1 BOILER_SupplyTemp"}` | 30 / 300; 1 | — |
| 27 | `equipment/BOILER/silo_fill` | 0 | — | `BAC-140-BOILER`; `{"object": "analog-input", "instance": 3, "mode": "cov", "cov_increment": 1, "doc": "AI:3 BOILER_SiloLevel"}` | 30 / 300; 0 | — |
| 28–35 | `equipment/<C>/state` | 1 | «<C>: стан» / «Стан»; state, — | `MQTT-MOBILE`; `{…, "path": "$.state", …, "map": {"to_charge": "busy"}}` | 5 / 300; 0 | `states=["idle", "busy", "charging", "offline", "fault"]`, `alarm_states=["fault"]`; «{equipment}: несправність (стан «{text}»)» |
| 36–43 | `equipment/<C>/x` | 1 | «<C>: координата X» / «Координата»; gauge, м | `MQTT-MOBILE`; `{…, "path": "$.x", …}` | 5 / 60; 1 | `viewer_visible=False` (Q-08) |
| 44–51 | `equipment/<C>/y` | 1 | «<C>: координата Y» / «Координата»; gauge, м | `MQTT-MOBILE`; `{…, "path": "$.y", …}` | 5 / 60; 1 | `viewer_visible=False` |
| 52 | `equipment/COMPRESSOR/state` | 1 | «Компресор: стан» / «Стан»; state, — | `MB-U70-COMPRESSOR`; `{"fc": 3, "addr": 3000, "type": "u16", "map": {"0": "stopped", "1": "loaded", "2": "unloaded", "3": "fault", "4": "standby"}, "doc": "HR 3001 Machine status"}` | 10 / 300; 0 | `states=["stopped", "loaded", "unloaded", "fault", "standby"]`, `alarm_states=["fault"]`; «Компресор: стан «{text}»» |
| 53 | `equipment/COMPRESSOR/temp_c` | 1 | «Компресор: температура гвинтового блока» / «Температура»; gauge, °C | `MB-U70-COMPRESSOR`; `{"fc": 3, "addr": 3002, "type": "u16", "scale": 0.1, "range": [0, 150], "doc": "HR 3003 Element outlet temperature"}` | 10 / 300; 1 | `alarm_high=110`, `hysteresis=2`; «{equipment}: температура {value} °C при нормі до {threshold}» |
| 54 | `equipment/DUST-1/state` | 1 | «Аспірація: стан» / «Стан»; state, — | `MB-U84-IO5`; `{"fc": 2, "states": [{"addr": 1, "eq": 1, "text": "fault"}, {"addr": 0, "eq": 1, "text": "running"}, {"addr": 0, "eq": 0, "text": "stopped"}], "doc": "DI0 вентилятори в роботі, DI1 аварія"}` | 10 / 300; 0 | `states=["running", "stopped", "fault"]`, `alarm_states=["fault"]`; «Аспірація: аварія вентиляторів (стан «{text}»)» |
| 55 | `infra/water/m3_total` | 1 | «Водомірний вузол: показник лічильника» / «Об'єм»; counter, м³ | `MB-U84-IO5`; `{"fc": 3, "addr": 16, "count": 2, "type": "u32", "wordorder": "little", "scale": 0.01, "doc": "HR 40017–40018 лічильник DI8, 1 імп = 10 л"}` | 60 / 300; 2 | — |
| 56 | `infra/water/flow_m3h` | 1 | «Водомірний вузол: витрата» / «Витрата»; gauge, м³/год | — (похідна) | 60 / 300; 2 | `derived_from=infra/water/m3_total`, `derive_rule=rate_h` |

Підсумок: `new=1` — 29 (8 + 8 + 8 + 5), `new=0` — 27; з джерелом — 55 (усі, крім № 56).

### C.3 `source_map` для CT-11 (хук крок 4) і ключ джерела з розібраної адреси

Ключ: Modbus → `u<unit>`; MQTT → `mqtt`; BACnet → `dev<device>`; HTTP POST → `http:<route>`; OPC UA → `opcua`;
REST → `rest`; SICS → `sics`. Карта цього модуля: `{"mqtt": "MQTT-MOBILE", "u70": "MB-U70-COMPRESSOR", "u84":
"MB-U84-IO5", "u90": "MB-U90-AI1", "u96": "MB-U96-RTD1", "dev140": "BAC-140-BOILER", "http:lpr": "HTTP-PUSH"}`;
ключі без відповідності — `source_id` не ставиться (сигнал чекає модуля-власника).

### C.4 ТО за лічильником (`hooks.METERS`, хук крок 3а, A-22)

| Обладнання | `td_meter_signal_id` | `td_meter_interval` | `td_meter_last_value` | Прив'язка наявної заявки |
|---|---|---|---|---|
| COMPRESSOR | `equipment/COMPRESSOR/hours` | 2 000 | 16 000 (MR «ТО на 18 000 мотогодин») | відкрита `preventive` заявка обладнання (у демо id 3) |
| FL-1…FL-5, FL-C1, FL-C2, TUGGER-1 | `equipment/<C>/hours` | 1 000 | `floor(last_value / 1000) · 1000` на момент установки (FL-2 3 222,1 → 3 000) | остання відкрита `preventive` заявка обладнання (у демо id 7–14 «Планове ТО») |

Правило кроку 3а: лише якщо `td_meter_signal_id` порожній; `td_meter_lead_pct` — з параметра; прив'язана заявка
отримує `td_signal_id`, `td_origin='meter'`, `td_threshold = next`, обладнання — `td_meter_request_id`; нових
заявок хук не створює. Очікувано на копії демо: `meters: 9`, `meter_requests_linked: 9`; на чистій базі — 0.

## Додаток D. Карта полів рівня 0 → `td.*` (хук кроки 2, 5)

Типи `x_`-полів — як у живій базі (`fields_get`, 14.10.2026).

| `x_f3d_signal` (тип) | `td.signal` | Правило |
|---|---|---|
| `x_code` (char) | `code` | ключ upsert; xml-id `td_telemetry.sig_<slug>`, `slug` = `re.sub(r'[^0-9A-Za-z]+', '_', code).strip('_').lower()` (= `plant/odoo_rpc.key`; коди ASCII) |
| `x_name` (char) | `name` | як є |
| `x_sequence` (integer) | `sequence` | як є |
| `x_active` (boolean) | — | `td.signal.active=True` завжди |
| `x_equipment_id` (m2o `maintenance.equipment`) | `equipment_id` | той самий id |
| `x_workcenter_id` (m2o `mrp.workcenter`) | `workcenter_id` | той самий id |
| `x_source_id` (m2o `x_f3d_signal`) | `derived_from_id` | другий прохід за `x_code` джерела; `derive_rule='none'` |
| `x_kind` (char) | `quantity` | як є; також вибір `alarm_title` (R-15) |
| `x_unit` (char) | `unit` | як є; `decimals` за R-15 |
| `x_mode` (char) | `sim_mode`, `kind` | `kind` за R-15 |
| `x_value` (float) | `last_value` | лише при створенні |
| `x_nominal` (float) | `nominal`, `sim_params.nominal` | |
| `x_noise`, `x_rate`, `x_limit`, `x_seed` (float/integer) | `sim_params.noise/rate/limit/seed` | |
| `x_alarm` (char), `x_threshold` (float) | `alarm_high`/`alarm_low` + `_on`, `hysteresis`, `alarm_title`; `sim_params.alarm/threshold` | R-15 |
| `x_state` (char) | `status` | «тривога» → `alarm`, інакше `ok` |
| `x_charging` (boolean) | `sim_params.charging`; `last_text` сигналу `equipment/<код>/state` | `charging` / `busy` (для `drain`) |
| `x_updated` (datetime) | `last_ts`, `status_since`, `last_stored_ts` | UTC naive як є |
| `x_request_id` (m2o `maintenance.request`) | `maintenance_request_id` | крок 6 (`requests_level0`) |
| — | `origin='sim_data'`, `module` (R-15), `period_s=60`, `store_period_s=300`, `last_quality='good'`, `viewer_visible=True`, `create_request=True` | умовчання міграції |

| `x_f3d_reading` (тип) | `td.reading` | Правило |
|---|---|---|
| `x_signal_id` (m2o `x_f3d_signal`) | `signal_id` | мапа `x_f3d_signal.id → td.signal.id` з кроку 2 |
| `x_equipment_id` (m2o) | `equipment_id` | з сигналу (`td.signal.equipment_id`) |
| `x_value` (float) | `value` | як є |
| `x_time` (datetime) | `ts` | UTC naive; `NULL` → пропуск (`skipped_null_ts`) |
| `create_date` (datetime, службове) | `received_at` | час прийому в Odoo (X-83), UTC naive як є |
| `x_name`, `x_unit` (char) | — | не переносяться (`code`, `unit` — related) |
| — | `quality='good'`, `src='sim_data'`, `text=NULL` | |
