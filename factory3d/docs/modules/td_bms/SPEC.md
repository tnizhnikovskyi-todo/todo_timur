# td_bms — специфікація

Версія 0.2 · 14.10.2026 (0.1 — 14.10.2026) · технічне рішення: `docs/modules/td_bms/ARCHITECTURE.md` (далі ARCH: FR-01…FR-26,
CH-01…CH-06, A-01…A-21, Q-01…Q-14). Спирається на: каркас §5 (імена, стоп-крани, права), §6.4, §6.5 (рішення менеджера
14.10: `bacnet_ip` — telemetry, `helvarnet` — bms), §6.6 P-08, §6.7, §6.8, D-08; `td_factory3d` CB-01, CB-03, CB-04,
CB-07…CB-10, CB-12, Додаток C (зони); `td_telemetry` M-02 `td.source`, M-03 `td.signal`, M-05
`td.reading.hour`, M-06 `td.command`, M-08 `maintenance.request`, CT-02 (інтерфейс плагіна, §8.3), CT-03 і Додаток
A (схеми `bacnet_ip`, `helvarnet`), CT-05 (R-04…R-06), CT-07, CT-09, CT-10 (`_td_ingest`), CT-12/R-26 (локальні
джерела), R-12, R-18, R-23, Додаток C.1 (`collector_main`, `BAC-140-BOILER`); `td_viewer3d` M-01, M-03, R-01,
R-14, Додаток A.13; `td_energy` CE-02, CE-03, CE-06, A-19; `td_fire_safety` A-20, CF-06, сигнал
`fire/totals/system_state`; `td_iot_sim` §8.10 (P-08), §9.1 R-22…R-24, §9.3 S-04, S-13, S-15, §7.2 API-12…API-16,
Додаток A.
Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-16 (M-13 без `selection_add` поля `origin` — значення `module` у базовому
selection telemetry M-03), X-19 (група `group_td_bms_operator` — у власному привілеї `privilege_td_bms` категорії
factory3d, §4.2, AC-62), X-58 (ТК-02 — параметр сценарію лише `value`), X-71 (§8.9: запис MSV:1 за зворотним `map`),
X-06 (§11 п. 4: COV допустимий, у v1 лишається опитування A-02), X-32 (§3: `menu_td_bms_config` під `menu_td_config`
з sequence резерву 80); закрито Q-09 (X-34, X-40, X-58) і Q-10 (X-06).
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-01, Q-02, Q-03, Q-04, Q-05, Q-06, Q-07, Q-08, Q-11, Q-12, Q-13, Q-14.

Позначення: **UT** — юніт-тест `odoo.tests`; **PT** — pytest плагіна з фейковим роутером Helvar; **TC** — стенд
(емулятор + колектор + Odoo); **MAN** — ручна перевірка. Odoo 19: SQL-обмеження — `models.Constraint`; хуки
`post_init_hook(env)` / `uninstall_hook(env)`; `fields.Json`; команди o2m/m2m — `odoo.fields.Command`. Рядки UI —
українською в коді (D-14). Усі імена остаточні.

## 0. Дерево файлів модуля

### 0.1 Odoo-модуль `odoo_addons/td_bms`

```
odoo_addons/td_bms/
├── __init__.py                      from . import models, wizard, tools; from .hooks import post_init_hook, uninstall_hook
├── __manifest__.py                  §1
├── hooks.py                         post_init_hook(env), uninstall_hook(env), run_install(env) — §5.3–§5.5 (R-29)
├── README.md                        установка, параметри, інструкції ARCH §4
├── CHANGELOG.md                     19.0.1.0.0 — перший випуск
├── models/
│   ├── __init__.py                  порядок: td_source, td_signal, td_bms_light_norm, td_bms_light_panel,
│   │                                td_bms_light_group, td_bms_light_scene, td_bms_hvac_unit, td_bms_heat_balance,
│   │                                td_bms_deviation, td_bms_check, td_bms_overview, viewer_provider,
│   │                                maintenance_request, maintenance_equipment, td_zone, res_config_settings
│   ├── td_source.py                M-12 (тип f3d_bms, _td_local_types)
│   ├── td_signal.py                M-13 (constraint запису, _td_ingest R-20)
│   ├── td_bms_light_norm.py        M-01
│   ├── td_bms_light_panel.py       M-02
│   ├── td_bms_light_group.py       M-03 (R-01…R-06, CH-03)
│   ├── td_bms_light_scene.py       M-04
│   ├── td_bms_hvac_unit.py         M-05 (R-10…R-13, CH-03)
│   ├── td_bms_heat_balance.py      M-06, M-07 (R-14…R-17)
│   ├── td_bms_deviation.py         M-08
│   ├── td_bms_check.py             AbstractModel td.bms.check: крон R-18…R-24, R-30
│   ├── td_bms_overview.py          M-10 (R-28)
│   ├── viewer_provider.py           M-11 (AbstractModel без _inherit, R-26, R-27)
│   ├── maintenance_request.py       M-14
│   ├── maintenance_equipment.py     M-16
│   ├── td_zone.py                  M-15
│   └── res_config_settings.py       M-17
├── wizard/
│   ├── __init__.py
│   ├── light_command_wizard.py      M-09a td.bms.light.command.wizard (R-25)
│   ├── hvac_command_wizard.py       M-09b td.bms.hvac.command.wizard (R-25)
│   └── command_wizard_views.xml     V-19, V-20
├── tools/
│   ├── __init__.py
│   ├── lighting.py                  чисті функції R-01…R-04, R-06 (без ORM): n_required, e_calc, pack_dali
│   ├── hvac.py                      R-10…R-13: MODE_LABELS, unit_state, fallback_heat, fallback_power
│   ├── heat.py                      R-14…R-17: design_balance(params, units), chp_heat(el_kw, …), live_balance(…)
│   ├── schedule.py                  R-18: work_interval_at(env, calendar, dt_utc) -> (start, end) | None
│   ├── rules.py                     R-19, R-21, R-23, R-24: чисті функції оцінки умов → (text, value, threshold)
│   ├── titles.py                    R-22: тексти заявок і журналу (uk, кома як десятковий роздільник)
│   ├── payload.py                   R-26, R-27: build_lighting(env, ctx, static), build_ventilation(env, ctx, static)
│   ├── signals.py                   читання last_* сигналів одним search_read: SignalCache(env, codes)
│   └── gen_data.py                  генератор data/*.xml і bms_signals.csv з макета (§5.2); Odoo його не вантажить
├── security/
│   ├── security.xml                 група «Будівля: оператор», implied, record rules (§4)
│   └── ir.model.access.csv          §4.1
├── data/
│   ├── ir_config_parameter.xml      §5.1 (noupdate="1")
│   ├── ir_cron.xml                  §6
│   ├── td_bms_light_norm_data.xml  13 норм (noupdate="1")
│   ├── td_bms_light_scene_data.xml 6 сцен (noupdate="1")
│   ├── td_bms_source_data.xml      32 джерела HelvarNet/BACnet (noupdate="1"), Додаток C
│   ├── td_bms_light_data.xml       3 щити, 32 групи (noupdate="1"), Додаток A.1/A.2
│   ├── td_bms_hvac_data.xml        29 установок, 1 тепловий баланс (noupdate="1"), Додаток A.3/A.4
│   ├── bms_signals.csv              549 сигналів (читає хук, не в `data` маніфесту), Додаток B
│   ├── td_bms_actions.xml          ir.actions.server «Повторити установку даних будівлі», клієнтська дія огляду
│   └── neutralize.sql               §5.6
├── views/
│   ├── menus.xml                    V-21
│   ├── td_bms_light_norm_views.xml V-01
│   ├── td_bms_light_panel_views.xml V-02, V-03
│   ├── td_bms_light_group_views.xml V-04…V-07
│   ├── td_bms_light_scene_views.xml V-08
│   ├── td_bms_hvac_unit_views.xml  V-09…V-12
│   ├── td_bms_heat_balance_views.xml V-13
│   ├── td_bms_deviation_views.xml  V-14…V-16
│   ├── td_zone_views.xml           V-17 (вкладка «Будівля» на зоні)
│   ├── maintenance_views.xml        V-18 (обладнання, заявка)
│   ├── res_config_settings_views.xml V-22
│   └── td_bms_overview_views.xml   V-23 (ir.actions.client)
├── static/
│   ├── description/icon.png         140×140
│   ├── src/overview/overview.js     OWL F3dBmsOverview (R-28)
│   ├── src/overview/overview.xml    шаблони
│   ├── src/overview/overview.scss   стилі
│   └── tests/overview.test.js       hoot-тест OWL (рендер плану з фіктивними даними)
└── tests/
    ├── __init__.py
    ├── common.py                    F3DBmsCase(TransactionCase): фікстури §13.0
    ├── test_lighting_calc.py        AC-01…AC-06
    ├── test_lighting_live.py        AC-07…AC-12
    ├── test_heat_balance.py         AC-13…AC-18
    ├── test_hvac_live.py            AC-19…AC-24
    ├── test_rules_lighting.py       AC-25…AC-30
    ├── test_rules_hvac.py           AC-31…AC-36
    ├── test_requests.py             AC-37…AC-41
    ├── test_viewer_provider.py      AC-42…AC-45
    ├── test_overview.py             AC-46, AC-47
    ├── test_hooks.py                AC-48…AC-56
    ├── test_commands.py             AC-57…AC-60
    ├── test_security.py             AC-61…AC-63
    └── test_data_sync.py            pytest поза Odoo: генератор ↔ макет (§13.1.3)
```

### 0.2 Плагін колектора `services/collector_plugins/f3d_collector_bms` (A-12)

```
services/collector_plugins/f3d_collector_bms/
├── README.md                        встановлення в образ колектора, params/address, обмеження
├── pyproject.toml                   name "f3d-collector-bms", version 0.1.0, requires-python ">=3.12", dependencies [] (лише stdlib +
│                                    пакет колектора f3d_collector з образу); [project.entry-points."factory3d_collector.plugins"]
│                                    helvarnet = "f3d_collector_bms.helvarnet:HelvarNetPlugin"
├── f3d_collector_bms/
│   ├── __init__.py                  __version__ = "0.1.0"
│   ├── protocol.py                  кадрування й розбір ASCII HelvarNet: build_query/build_command/parse_frame — R-31 (чисті функції)
│   ├── connection.py                HelvarConnection (asyncio TCP, черга запитів, читач, push-підписники), ConnectionPool — R-31, R-36
│   ├── helvarnet.py                 HelvarNetPlugin(SourcePlugin) — §8.3…§8.7, R-32…R-37
│   └── schemas/
│       ├── address.helvarnet.json   = SPEC §8.2.2 (розширення Додатка A.1 telemetry)
│       └── params.helvarnet.json    = SPEC §8.2.1
└── tests/
    ├── conftest.py                  fake_router (asyncio-сервер), plugin_ctx (фейковий PluginContext), freeze
    ├── fake_helvar_router.py        FakeHelvarRouter: стан груп/пристроїв, відповіді 101…191, push C:13/C:11, помилки, затримки
    ├── test_protocol.py             AC-64…AC-67
    └── test_plugin_helvarnet.py     AC-68…AC-78
```

Збирання образу колектора: `services/collector/requirements-extra.txt` містить рядок
`./../collector_plugins/f3d_collector_bms` (локальний шлях, `pip install --no-deps`); telemetry Dockerfile вже
встановлює `requirements-extra.txt` (telemetry §8.3.2).

## 1. Маніфест

```python
{
    "name": "Завод 3D: будівля (освітлення, вентиляція, опалення)",
    "summary": "Групи освітлення за нормами, DALI/HelvarNet, дахові установки й котельня (BACnet), тепловий баланс, відхилення → заявки ТО",
    "description": "td_bms: норми освітленості, щити й групи освітлення LT-* (Helvar Imagine 950), установки "
                   "RV-01…25, AHU-1, EF-*, котельня, тепловий баланс цеху, журнал відхилень, огляд будівлі, провайдери "
                   "3D-переглядача lighting/ventilation; плагін колектора helvarnet (services/collector_plugins/f3d_collector_bms).",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Maintenance",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_telemetry", "web"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/td_bms_light_norm_data.xml",
        "data/td_bms_light_scene_data.xml",
        "data/td_bms_source_data.xml",
        "data/td_bms_light_data.xml",
        "data/td_bms_hvac_data.xml",
        "data/ir_cron.xml",
        "data/td_bms_actions.xml",
        "wizard/command_wizard_views.xml",
        "views/td_bms_light_norm_views.xml",
        "views/td_bms_light_panel_views.xml",
        "views/td_bms_light_group_views.xml",
        "views/td_bms_light_scene_views.xml",
        "views/td_bms_hvac_unit_views.xml",
        "views/td_bms_heat_balance_views.xml",
        "views/td_bms_deviation_views.xml",
        "views/td_zone_views.xml",
        "views/maintenance_views.xml",
        "views/res_config_settings_views.xml",
        "views/td_bms_overview_views.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "td_bms/static/src/overview/overview.js",
            "td_bms/static/src/overview/overview.xml",
            "td_bms/static/src/overview/overview.scss",
        ],
        "web.assets_unit_tests": ["td_bms/static/tests/overview.test.js"],
    },
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
    "auto_install": False,
}
```

Порядок `data`: групи/правила → доступи → параметри → норми → сцени → джерела (посилаються на
`td_telemetry.collector_main`) → щити й групи (посилаються на норми, джерела, зони base
`td_factory3d.zone_<slug>` і паспорти `td_factory3d.passport_<role>`) → установки й баланс → крон (після даних, щоб
перший прогін мав об'єкти) → дії → майстри → представлення → меню. `bms_signals.csv` у `data` не перелічений — його
читає хук через `odoo.tools.file_open` (Json-колонки розбираються `json.loads`; CSV-імпорт Odoo писав би Json рядком).
Python-залежностей в Odoo-модулі немає; `bacpypes3` — у колекторі telemetry; плагін `helvarnet` — лише stdlib
(`asyncio`).

## 2. Моделі

Спільні позначення: `req` = `required=True`; `idx` = `index=True`; `Datetime` — UTC naive; `Json` — `fields.Json`.
Усі `_description` українською. «Живі» поля — `compute` без `store`, читають `last_*` сигналів через
`tools.signals.SignalCache` (один `search_read` на набір записів: поля `code`, `last_value`, `last_text`, `last_ts`,
`status`, `last_quality`, `maintenance_request_id`). Сигнал «живий», якщо `status ∈ {ok, warn, alarm}`; `stale`/`unknown`
або відсутній — значення беруться з фолбеку (R-05, R-12, A-18), а `stale=True`.

### M-01 `td.bms.light.norm` — норма освітленості (FR-01)

```python
class F3dBmsLightNorm(models.Model):
    _name = "td.bms.light.norm"
    _description = "Будівля: норма освітленості"
    _order = "sequence, key"
    _rec_name = "name"
    _rec_names_search = ["name", "key"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `key` | Char(48) | `req`, `idx`, `string="Ключ"`, `help="Вид робіт з plant/lux_norms.json: woodworking_machine, spraying…"` |
| `name` | Char(128) | `req`, `string="Вид робіт"` |
| `sequence` | Integer | `default=10` |
| `lux` | Integer | `req`, `string="Норма, лк"` (Ēm на робочій поверхні) |
| `ugr` | Integer | `string="UGR, не більше"` |
| `ra` | Integer | `string="Ra, не менше"` |
| `ref_en` | Char(256) | `string="EN 12464-1"` (з `ref` json) |
| `ref_dbn` | Char(256) | `string="ДБН В.2.5-28"`, `default="ДБН В.2.5-28:2018 (зі Зміною № 1) — звірити розряд зорових робіт (Q-03)"` |
| `note` | Text | `string="Примітка"` |
| `sources` | Text | `string="Джерела"`, URL по рядку |
| `group_ids` | One2many `td.bms.light.group` `norm_id` | `string="Групи"` |
| `group_count` | Integer | `compute="_compute_group_count"` |
| `active` | Boolean | `default=True` |

```python
    _f3d_bms_norm_key_uniq = models.Constraint("UNIQUE(key)", "Ключ норми має бути унікальним.")
    _f3d_bms_norm_lux_pos = models.Constraint("CHECK(lux > 0)", "Норма освітленості має бути більшою за 0 лк.")
```

`@api.constrains("key")`: `^[a-z][a-z0-9_]{0,47}$` → `ValidationError("Ключ норми: латиниця, цифри, підкреслення.")`.
`write`: зміна `lux` → чаттер не потрібен (модель без `mail.thread`); залежні `e_norm`/`design_ok` груп
перераховуються через `depends` (M-03).

### M-02 `td.bms.light.panel` — щит освітлення (FR-02)

```python
class F3dBmsLightPanel(models.Model):
    _name = "td.bms.light.panel"
    _description = "Будівля: щит освітлення"
    _order = "code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(16) | `req`, `idx`, `string="Код"` (`LP-1`) |
| `name` | Char(128) | `req`, `string="Назва"` («Щит освітлення ЩО-1 · склади сировини, приймання») |
| `equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання"`, `ondelete="set null"` |
| `source_id` | Many2one `td.source` | `string="Джерело HelvarNet"`, `domain="[('type','=','helvarnet')]"`, `ondelete="set null"` |
| `cluster` | Integer | `req`, `default=1`, `string="Кластер"` (1…253) |
| `router` | Integer | `req`, `string="Роутер"` (1…254; `LP-1` → 1) |
| `x`, `y` | Float | `digits=(8,2)`, `string="X, м"`/`"Y, м"` (північна стіна: y = 71,0) |
| `zone_id` | Many2one `td.zone` | `string="Зона розміщення"`, `ondelete="set null"` |
| `group_ids` | One2many `td.bms.light.group` `panel_id` | `string="Групи"` |
| `group_count` | Integer | `compute="_compute_totals"`, `store=True` |
| `n_fixtures` | Integer | `compute="_compute_totals"`, `store=True`, `string="Світильників"` = Σ `group_ids.n_fixtures` |
| `p_inst_kw` | Float | `compute="_compute_totals"`, `store=True`, `digits=(8,1)`, `string="Встановлена потужність, кВт"` = `round(Σ group.p_inst_kw, 1)` |
| `state_signal_id` | Many2one `td.signal` | `string="Сигнал: стан щита"`, `ondelete="set null"` |
| `meter_code` | Char(64) | `compute`: `"energy/consumers/%s/p_now" % code` (A-16) |
| `p_now_kw` | Float | живе (R-05 п. 6), `digits=(8,1)`, `string="Потужність зараз, кВт"` |
| `p_source` | Selection | живе: `[('meter','Лічильник energy'),('dali','Сума груп (DALI)'),('design','Проєктна')]` |
| `state` | Selection | живе: `[('ok','Норма'),('fault','Є несправні світильники'),('offline','Немає зв'язку'),('unknown','Невідомо')]` — `state_signal_id.last_text` (`ok`/`fault`), `offline` якщо `source_id.state ∈ {offline, error, disabled}` або сигнал `stale`, `unknown` без сигналу |
| `active` | Boolean | `default=True` |
| `note` | Text | |

```python
    _f3d_bms_panel_code_uniq = models.Constraint("UNIQUE(code)", "Код щита має бути унікальним.")
    _f3d_bms_panel_router_uniq = models.Constraint("UNIQUE(cluster, router)", "Роутер з такою адресою вже призначено іншому щиту.")
    _f3d_bms_panel_addr = models.Constraint("CHECK(cluster BETWEEN 1 AND 253 AND router BETWEEN 1 AND 254)",
                                            "Адреса роутера: кластер 1…253, роутер 1…254.")
```

`@api.constrains("code")`: `^LP-\d{1,3}$` → `"Код щита — LP-<номер>."`.

Методи: `action_f3d_show(self)` — `ensure_one()`; `equipment_id.action_f3d_show()` якщо є, інакше `UserError("Щит %s
не прив'язаний до обладнання з кодом сцени.")`; `action_view_groups(self)` — `act_window` груп
(`domain=[('panel_id','=',id)]`).

### M-03 `td.bms.light.group` — група освітлення (FR-03…FR-06, CH-03)

```python
class F3dBmsLightGroup(models.Model):
    _name = "td.bms.light.group"
    _description = "Будівля: група освітлення"
    _inherit = ["mail.thread"]
    _order = "sequence, code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^LT-[A-Z0-9]+(-[A-Z0-9]+)*$")
```

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(32) | `req`, `idx`, `string="Код"`, `tracking=True` (`LT-CUT`) |
| `name` | Char(128) | `req`, `string="Назва"` («Освітлення: Розкрій») |
| `sequence` | Integer | `default=10` (порядок каталогу: № групи × 10) |
| `active` | Boolean | `default=True` |
| `zone_id` | Many2one `td.zone` | `req`, `ondelete="restrict"`, `idx`, `string="Зона"` |
| `zone_code` | Char | `related="zone_id.td_code"` |
| `zone_name` | Char | `related="zone_id.name"` |
| `area_m2` | Float | `related="zone_id.area_m2"`, `string="Площа, м²"` |
| `norm_id` | Many2one `td.bms.light.norm` | `req`, `ondelete="restrict"`, `string="Вид робіт"`, `tracking=True` |
| `e_norm` | Integer | `related="norm_id.lux"`, `string="Норма, лк"` |
| `panel_id` | Many2one `td.bms.light.panel` | `req`, `ondelete="restrict"`, `idx`, `string="Щит"` |
| `equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання"`, `ondelete="set null"` |
| `passport_id` | Many2one `td.equipment.passport` | `string="Паспорт світильника"`, `ondelete="set null"` |
| `fixture_kind` | Selection | `[('highbay','Широка оптика (WB)'),('highbay_rack','Вузька оптика над проходами (NB)')]`, `req`, `string="Тип світильника"` |
| `lumen` | Integer | `compute="_compute_fixture"`, `store=True`, `readonly=False`, `string="Світловий потік, лм"`: `passport_id.get_num('lumen')` або умовчання R-02 |
| `watt` | Integer | `compute="_compute_fixture"`, `store=True`, `readonly=False`, `string="Потужність світильника, Вт"`: `passport_id.get_num('watt')` або умовчання |
| `n_fixtures` | Integer | `req`, `string="Світильників встановлено"`, `tracking=True` |
| `uf` | Float | `req`, `digits=(3,2)`, `default=lambda s: float(param('td.bms.light_uf','0.7'))`, `string="Коефіцієнт використання UF"` |
| `mf` | Float | `req`, `digits=(3,2)`, `default=lambda s: float(param('td.bms.light_mf','0.8'))`, `string="Коефіцієнт експлуатації MF"` |
| `n_required` | Integer | `compute="_compute_design"`, `store=True`, `string="Світильників потрібно"` (R-03) |
| `e_calc_raw` | Float | `compute="_compute_design"`, `store=True`, `digits=(10,3)` |
| `e_calc` | Integer | `compute="_compute_design"`, `store=True`, `string="Розрахункова освітленість, лк"` (R-04) |
| `design_ok` | Boolean | `compute="_compute_design"`, `store=True`, `string="Норму виконано"` |
| `p_inst_kw` | Float | `compute="_compute_design"`, `store=True`, `digits=(8,2)`, `string="Встановлена потужність, кВт"` |
| `level_design` | Float | `req`, `digits=(3,2)`, `string="Рівень за проєктом"` (частка 0…1; макет `level`) |
| `control_mode` | Selection | `[('shift','DALI: зміна, 100 %'),('presence','DALI: присутність і денне світло')]`, `req`, `string="Керування"` |
| `check_off` | Boolean | `default=True`, `string="Перевіряти «вимкнено в робочий час»"` |
| `check_norm` | Boolean | `compute="_compute_check_norm"`, `store=True`, `readonly=False`, `string="Перевіряти норму"`: `control_mode == 'shift'` (A-07) |
| `calendar_id` | Many2one `resource.calendar` | `string="Робочий час"`, `help="Порожньо — параметр td.bms.calendar_id або календар компанії"` |
| `dali_group` | Integer | `req`, `string="DALI-група (G)"` (1…16383) |
| `dali_devices` | Char(256) | `string="Пристрої DALI"`, формат `@c.r.s.d1-d2[;@c.r.s.d1-d2…]` (R-06), напр. `@1.2.1.1-27` |
| `level_signal_id`, `power_signal_id`, `scene_signal_id`, `faults_signal_id`, `faulty_signal_id`, `check_signal_id` | Many2one `td.signal` | `ondelete="set null"`, `string="Сигнал: рівень"` / `"…: потужність"` / `"…: сцена"` / `"…: несправних"` / `"…: адреси несправних"` / `"…: перевірка"` |
| `level_pct` | Float | живе, `digits=(5,1)`, `string="Рівень зараз, %"` (R-05) |
| `level_source` | Selection | живе: `[('live','З DALI'),('design','Проєктний')]` |
| `e_now` | Integer | живе, `string="Освітленість зараз, лк"` (R-05) |
| `p_now_kw` | Float | живе, `digits=(8,2)`, `string="Потужність зараз, кВт"` |
| `scene` | Integer | живе, `string="Остання сцена"` (0 — невідомо) |
| `faults` | Integer | живе, `string="Несправних світильників"` |
| `faulty` | Char | живе, `string="Адреси несправних"` |
| `live_ts` | Datetime | живе: `max(last_ts)` рівня й потужності |
| `stale` | Boolean | живе: рівень не «живий» |
| `deviation` | Selection | живе: `[('none','Норма'),('off_hours','Поза робочим часом'),('off_in_work','Вимкнено в робочий час'),('below_norm','Нижче норми'),('no_data','Немає даних'),('no_mains','Немає мережі')]` — з `check_signal_id.last_text` за таблицею R-19 |
| `deviation_text` | Char | живе: `check_signal_id.last_text` |
| `plan_state` | Selection | живе, для огляду: `[('ok','Норма'),('low','Нижче норми'),('off','Вимкнено'),('fault','Є несправні'),('alarm','Відхилення'),('nodata','Немає даних')]` (R-28 п. 3) |
| `off_since` | Datetime | `readonly=True`, `copy=False` — з якого часу рівень < 1 % (R-20) |
| `low_since` | Datetime | `readonly=True`, `copy=False` — з якого часу `e_now < e_norm·(1 − tol)` при рівні ≥ 1 % (R-20) |
| `request_ids` | Many2many `maintenance.request` | `compute="_compute_requests"`: заявки з `td_signal_id ∈ {6 сигналів}` і `stage_id.done=False` |
| `request_count` | Integer | `compute="_compute_requests"` |
| `deviation_count` | Integer | `compute`: відкриті `td.bms.deviation` з `object_code == code` |
| `note` | Text | |

```python
    _f3d_bms_group_code_uniq = models.Constraint("UNIQUE(code)", "Код групи освітлення має бути унікальним.")
    _f3d_bms_group_dali_uniq = models.Constraint("UNIQUE(dali_group)", "DALI-група вже використана іншою групою.")
    _f3d_bms_group_checks = models.Constraint(
        "CHECK(n_fixtures >= 1 AND level_design >= 0 AND level_design <= 1 AND uf > 0 AND uf <= 1 AND mf > 0 AND mf <= 1 "
        "AND dali_group BETWEEN 1 AND 16383)",
        "Група освітлення: світильників ≥ 1, рівень 0…1, UF і MF у (0; 1], DALI-група 1…16383.")
```

`@api.constrains`:
- `code` — `CODE_RE` → `"Код групи: LT-<зона>, великі латинські літери, цифри, дефіси."`;
- `dali_devices` — `tools.lighting.parse_devices(text)` кидає `ValueError` → `ValidationError("Пристрої DALI: %s")`;
  кількість пристроїв (якщо задано) ≠ `n_fixtures` → `ValidationError("Пристроїв DALI %s, а світильників %s.")`;
  кластер/роутер кожної адреси ≠ `panel_id.cluster/router` → `"Адреса %s не належить щиту %s."`;
- `zone_id` — `zone_id.area_m2 <= 0` → `"Зона %s без контуру: площа 0 м², розрахунок неможливий."`.

Обчислення:
- `_compute_fixture` (`@api.depends("passport_id", "fixture_kind")`): `lm = passport_id.get_num('lumen')`, `w =
  passport_id.get_num('watt')`; `None` → `DEFAULT_FIX[fixture_kind]` = `{'highbay': (24000, 160), 'highbay_rack':
  (19000, 130)}` (`plant/lighting.py:DEFAULT_FIX`); `lumen = int(round(lm))`, `watt = int(round(w))`.
- `_compute_design` (`@api.depends("zone_id.area_m2", "norm_id.lux", "lumen", "watt", "n_fixtures", "uf", "mf")`):
  R-03/R-04 через `tools.lighting`.
- живі — `_compute_live` (`@api.depends_context("uid")`, без `store`): R-05 і таблиця R-19.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `action_f3d_show(self)` | `ensure_one()`; `equipment_id.action_f3d_show()` якщо `equipment_id.td_code`; інакше `zone_id.action_f3d_show()` |
| `action_open_command(self)` | `act_window` `td.bms.light.command.wizard` (`target='new'`, `context={'default_group_ids': ids}`); перед цим `_td_bms_check_operator()` (R-25 п. 1) |
| `action_view_readings(self)` | `act_window` `td.reading` (`graph,list`), `domain=[('signal_id','in',[level, power])]`, `context={'search_default_last_48h': 1}` |
| `action_view_deviations(self)` | `act_window` `td.bms.deviation`, `domain=[('object_code','=',code)]` |
| `action_view_requests(self)` | `act_window` `maintenance.request`, `domain=[('id','in',request_ids.ids)]` |
| `@api.model _td_bms_light_power(self)` → dict | CH-03: для всіх активних груп `{code: {"zone": zone_code, "panel": panel_id.code, "p_now_kw": p_now_kw, "p_inst_kw": p_inst_kw, "level_pct": level_pct}}` |
| `@api.model _td_bms_kwh(self, date_from, date_to)` → dict | CH-03: `read_group` `td.reading.hour` за `signal_id ∈ power_signal_id`, `hour ∈ [date_from, date_to)`, сума `v_avg` (кВт × 1 год) → `{code: round(kwh, 2)}`; групи без годин — `0.0` |

### M-04 `td.bms.light.scene` — сцена DALI (FR-18)

`_name = "td.bms.light.scene"`, `_description = "Будівля: сцена освітлення"`, `_order = "number"`.

| Поле | Тип | Параметри |
|---|---|---|
| `number` | Integer | `req`, `string="Номер"` (1…16) |
| `name` | Char(64) | `req`, `string="Назва"` |
| `level_pct` | Integer | `string="Рівень, %"` (0…100; для довідки й перевірки запису R-37) |
| `block` | Integer | `default=1`, `string="Блок сцен"` (1…8) |
| `note` | Char(256) | |

`_f3d_bms_scene_uniq = models.Constraint("UNIQUE(block, number)", "Сцена з таким номером уже є в блоці.")`;
`CHECK(number BETWEEN 1 AND 16 AND block BETWEEN 1 AND 8 AND (level_pct IS NULL OR level_pct BETWEEN 0 AND 100))`.
Дані (iot_sim R-24 / §8.10.4, ПРИПУЩЕННЯ — сцени програмуються в Helvar Designer, Q-05): 1 «Зміна» 100; 2 «Прибирання»
75; 3 «Половина» 50; 4 «Чергове освітлення» 25; 5 «Ніч» 10; 6 «Вимкнено» 0.

### M-05 `td.bms.hvac.unit` — установка вентиляції (FR-07…FR-09, CH-03)

```python
class F3dBmsHvacUnit(models.Model):
    _name = "td.bms.hvac.unit"
    _description = "Будівля: установка вентиляції"
    _inherit = ["mail.thread"]
    _order = "sequence, code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^(RV-\d{2}|AHU-\d{1,2}|EF-[A-Z]{2,8})$")
```

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(16) | `req`, `idx`, `string="Код"`, `tracking=True` |
| `name` | Char(128) | `req`, `string="Назва"` |
| `sequence` | Integer | `default=10` |
| `active` | Boolean | `default=True` |
| `kind` | Selection | `[('roofvent','Дахова установка'),('ahu','Припливна установка'),('fan','Витяжний вентилятор'),('exfan','Витяжний вентилятор (Ex)')]`, `req`, `string="Вид"` |
| `zone_id` | Many2one `td.zone` | `req`, `ondelete="restrict"`, `idx`, `string="Зона"` |
| `zone_name` | Char | `related="zone_id.name"` |
| `x`, `y` | Float | `digits=(8,2)`, `string="X, м"`/`"Y, м"` (план; Додаток A.3) |
| `equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання"`, `ondelete="set null"` |
| `passport_id` | Many2one `td.equipment.passport` | `string="Паспорт"`, `ondelete="set null"` |
| `source_id` | Many2one `td.source` | `string="Джерело BACnet"`, `domain="[('type','=','bacnet_ip')]"`, `ondelete="set null"` |
| `bacnet_device` | Integer | `string="BACnet device"` (101…133) |
| `fan_count` | Integer | `default=1`, `string="Вентиляторів"` (EF-ELEC — 2) |
| `airflow_nom` | Float | `compute="_compute_nominals"`, `store=True`, `readonly=False`, `digits=(10,0)`, `string="Номінальна витрата, м³/год"` (R-10 п. 1) |
| `heat_nom_kw` | Float | `compute="_compute_nominals"`, `store=True`, `readonly=False`, `digits=(8,1)`, `string="Теплова потужність нагрівача, кВт"` |
| `p_inst_kw` | Float | `compute="_compute_nominals"`, `store=True`, `readonly=False`, `digits=(8,3)`, `string="Потужність вентиляторів, кВт"` |
| `required_m3h` | Float | `digits=(8,1)`, `string="Потрібна витрата, м³/год"` (EF-CHG 158,4) |
| `mode_design` | Selection | `[('VE','VE — приплив і витяжка'),('VEL','VEL — знижена вентиляція'),('AQ','AQ — рекуперація за якістю повітря'),('REC','REC — рециркуляція'),('EA','EA — витяжка'),('SA','SA — приплив'),('ST','ST — очікування'),('Off','Вимкнено'),('thermostat','За термостатом'),('charging','Під час заряджання')]`, `req`, `string="Режим за проєктом"` |
| `required_in_work` | Boolean | `default=True`, `string="Має працювати в робочий час"` (EF — `False`) |
| `t_supply_design` | Float | `digits=(4,1)`, `string="Приплив за проєктом, °C"` (AHU-1 — 21,0) |
| `calendar_id` | Many2one `resource.calendar` | як у M-03 |
| `note` | Text | `string="Примітка"` (з макета для AHU-1 і вентиляторів) |
| `airflow_signal_id`, `supply_signal_id`, `indoor_signal_id`, `filter_signal_id`, `filter_extract_signal_id`, `valve_signal_id`, `heat_signal_id`, `power_signal_id`, `mode_signal_id`, `state_signal_id`, `sp_day_signal_id`, `sp_night_signal_id`, `pressure_signal_id`, `interlock_signal_id`, `check_signal_id` | Many2one `td.signal` | `ondelete="set null"`, `string="Сигнал: витрата"`, `"…: приплив"`, `"…: у зоні"`, `"…: фільтр припливу"`, `"…: фільтр витяжки"`, `"…: клапан нагріву"`, `"…: тепло"`, `"…: потужність"`, `"…: режим"`, `"…: стан"`, `"…: уставка день"`, `"…: уставка ніч"`, `"…: тиск у дільниці"`, `"…: блокування з камерами"`, `"…: перевірка"` |
| `airflow_m3h` | Float | живе, `digits=(10,1)`, `string="Витрата, м³/год"` |
| `k` | Float | живе, `digits=(4,3)`, `string="Частка номінальної витрати"` = `airflow_m3h / airflow_nom` (0, якщо `airflow_nom = 0`) |
| `supply_c`, `indoor_c` | Float | живе, `digits=(5,1)`, `string="Приплив, °C"` / `"У зоні, °C"` |
| `filter_dp_pa`, `filter_extract_dp_pa` | Float | живе, `digits=(6,1)`, `string="Фільтр припливу, Па"` / `"Фільтр витяжки, Па"` |
| `heating_valve` | Float | живе, `digits=(4,2)`, `string="Клапан нагріву"` (частка 0…1) |
| `heat_kw` | Float | живе, `digits=(8,1)`, `string="Тепло, кВт"` |
| `p_now_kw` | Float | живе, `digits=(8,3)`, `string="Потужність зараз, кВт"` |
| `mode_code` | Char | живе: `mode_signal_id.last_text` (`VE`…`Off`) або `False` |
| `mode_label` | Char | живе: R-10 п. 3 |
| `state` | Selection | живе: `[('on','Працює'),('standby','Очікування'),('off','Вимкнено'),('fault','Аварія')]` (R-11) |
| `setpoint_day_c`, `setpoint_night_c`, `room_pressure_pa` | Float | живе, `digits=(5,1)` |
| `live_ts` | Datetime | живе |
| `stale` | Boolean | живе: сигнал витрати (EF — стану) не «живий» |
| `deviation` | Selection | живе: `[('none','Норма'),('off_hours','Поза робочим часом'),('not_running','Не працює в робочий час'),('cold','Холодно в зоні'),('no_data','Немає даних'),('fire','Зупинено пожежною сигналізацією'),('no_mains','Немає мережі')]` з `check_signal_id.last_text` (R-23) |
| `deviation_text` | Char | живе |
| `alarm_count` | Integer | живе: кількість сигналів установки зі `status='alarm'` |
| `plan_state` | Selection | живе: `[('on','Працює'),('standby','Очікування'),('alarm','Відхилення'),('nodata','Немає даних')]` |
| `off_since` | Datetime | `readonly=True`, `copy=False` (R-20) — з якого часу не працює |
| `cold_since` | Datetime | `readonly=True`, `copy=False` (R-20) — з якого часу в зоні нижче `indoor_min_work_c` |
| `cold_off_since` | Datetime | `readonly=True`, `copy=False` (R-20) — з якого часу нижче `indoor_min_off_c` |
| `request_ids`, `request_count`, `deviation_count` | | як у M-03 (сигнали установки) |

```python
    _f3d_bms_unit_code_uniq = models.Constraint("UNIQUE(code)", "Код установки має бути унікальним.")
    _f3d_bms_unit_checks = models.Constraint(
        "CHECK(fan_count >= 1 AND (airflow_nom IS NULL OR airflow_nom >= 0) AND (p_inst_kw IS NULL OR p_inst_kw >= 0))",
        "Установка: вентиляторів ≥ 1, номінали ≥ 0.")
```

`@api.constrains`: `code` — `CODE_RE` → `"Код установки: RV-NN, AHU-N або EF-<назва>."`; `source_id` і `bacnet_device` —
якщо обидва задані і `source_id.params.get('device') != bacnet_device` → `"BACnet device %s не збігається з джерелом %s
(device %s)."`; `kind in (roofvent, ahu)` і `mode_design in (thermostat, charging)` → `"Режим «%s» — лише для
вентиляторів."`.

Методи: `action_f3d_show(self)` (як M-03: обладнання, інакше зона); `action_open_command(self)` →
`td.bms.hvac.command.wizard` (лише `kind in (roofvent, ahu)`, інакше `UserError("Керування вентиляторами EF не
передбачено (ARCH §1.4).")`); `action_view_readings`, `action_view_deviations`, `action_view_requests` — як M-03;
`@api.model _td_bms_heat_now(self)` → `{code: heat_kw}` для `kind in (roofvent, ahu)` (CH-03).

### M-06 `td.bms.heat.balance` — тепловий баланс цеху (FR-10, FR-11)

```python
class F3dBmsHeatBalance(models.Model):
    _name = "td.bms.heat.balance"
    _description = "Будівля: тепловий баланс"
    _inherit = ["mail.thread"]
    _order = "company_id"
```

| Поле | Тип | Параметри (умовчання = макет `plant/ventilation.py`) |
|---|---|---|
| `name` | Char(128) | `req`, `default="Тепловий баланс цеху"` |
| `company_id` | Many2one `res.company` | `req`, `default=lambda s: s.env.company`, `idx` |
| `t_out_design` | Float | `digits=(4,1)`, `default=-15.0`, `string="Розрахункова зовнішня, °C"`, `tracking=True` (`T_OUT_DESIGN`) |
| `t_in_set` | Float | `digits=(4,1)`, `default=18.0`, `string="Уставка в цеху, °C"` (`INDOOR_SET_C`) |
| `length_m`, `width_m`, `height_m` | Float | `digits=(6,2)`, `default` з `td.base.plant_length_m/width_m/height_m` (150 / 72 / 9; CB-12) |
| `u_wall`, `u_roof`, `u_floor` | Float | `digits=(5,3)`, `default` 0,35 / 0,25 / 0,15, `string="U стін/покрівлі/підлоги, Вт/(м²·К)"`, `tracking=True` |
| `infiltration_ach` | Float | `digits=(5,3)`, `default=0.1`, `string="Інфільтрація, обмінів/год"` |
| `winter_oa_share` | Float | `digits=(4,2)`, `default=0.5`, `string="Частка зовнішнього повітря в установках узимку"` |
| `heat_recovery` | Float | `digits=(4,2)`, `default=0.78`, `string="Ефективність рекуперації"` (паспорт RoofVent: 78 % суха) |
| `air_wh_m3k` | Float | `digits=(5,3)`, `default=0.34`, `string="Теплоємність повітря, Вт·год/(м³·К)"` (1,2 кг/м³ · 1,005 кДж/(кг·К) / 3,6) |
| `ahu_design_share` | Float | `digits=(4,2)`, `default=0.85`, `string="Частка номінальної витрати AHU-1 у розрахунку"` |
| `ahu_supply_c` | Float | `digits=(4,1)`, `default=21.0`, `string="Приплив AHU-1, °C"` |
| `internal_gains_kw` | Float | `digits=(8,1)`, `default=0.0`, `string="Внутрішні теплонадходження, кВт"`, `help="0 — як у макеті: не враховуються, це запас (Q-11)"` |
| `boilers` | Integer | `default=2`, `string="Котлів"` (`BOILERS`) |
| `boiler_kw` | Float | `digits=(8,1)`, `default=495.0`, `string="Потужність котла, кВт"` (`BOILER_KW`; паспорт `biomass_boiler` «Теплова потужність 495 кВт») |
| `boiler_stage_share` | Float | `digits=(4,2)`, `default=0.85`, `string="Поріг вмикання другого котла (частка К1)"` |
| `chp_el_kw` | Float | `default` = `passport_chp.power_kw` або 800, `string="КГУ: електрична, кВт"` |
| `chp_heat_kw`, `chp_heat_75_kw`, `chp_heat_50_kw` | Float | `default` = `get_num('heat_kw')` / `'heat_kw_75'` / `'heat_kw_50'` паспорта `chp` або 856 / 676 / 497 |
| `chp_min_load` | Float | `digits=(4,2)`, `default=0.5` (паспорт `min_load`) |
| `line_ids` | One2many `td.bms.heat.balance.line` `balance_id` | `string="Складові"` |
| `total_raw` | Float | `digits=(10,2)`, `readonly=True` |
| `total_kw` | Integer | `readonly=True`, `string="Навантаження при розрахунковій, кВт"` |
| `capacity_kw` | Integer | `readonly=True`, `string="Котли, кВт"` = `round(boilers·boiler_kw)` |
| `reserve` | Float | `digits=(6,2)`, `readonly=True`, `string="Запас із КГУ"` (частка) |
| `reserve_boilers` | Float | `digits=(6,2)`, `readonly=True`, `string="Запас котлів"` |
| `note` | Char(512) | `readonly=True` (R-14 п. 9) |
| `computed_at` | Datetime | `readonly=True` |
| `boiler_equipment_id`, `chp_equipment_id` | Many2one `maintenance.equipment` | `ondelete="set null"` (`BOILER`, `CHP`) |
| `outdoor_signal_id`, `boiler_state_signal_id`, `boiler_supply_signal_id`, `boiler_return_signal_id`, `boiler_heat_signal_id`, `silo_signal_id`, `chp_heat_signal_id`, `chp_el_signal_id`, `mains_signal_id`, `fire_signal_id`, `check_signal_id` | Many2one `td.signal` | `ondelete="set null"`; коди — §5.3 крок 5 |
| `outdoor_c` | Float | живе, `digits=(4,1)` |
| `heat_need_kw` | Float | живе, `digits=(8,1)`, `string="Потреба зараз, кВт"` (R-16) |
| `chp_heat_now_kw` | Float | живе, `digits=(8,1)`, `string="Тепло КГУ зараз, кВт"` (R-15) |
| `chp_source` | Selection | живе: `[('signal','Сигнал КГУ'),('calc','За електричною потужністю'),('design','Проєктне (50 %)')]` |
| `boilers_on_calc` | Integer | живе, `string="Котлів потрібно"` |
| `boilers_on` | Integer | живе, `string="Котлів працює"` (з MSV:1; `False` — немає даних) |
| `boiler_state` | Char | живе: `standby`/`K1`/`K1+K2`/`fault` |
| `boiler_load` | Float | живе, `digits=(4,2)` |
| `boiler_heat_kw`, `supply_c`, `return_c`, `silo_fill` | Float | живе |
| `deficit_kw` | Float | живе, `digits=(8,1)`, `string="Дефіцит тепла, кВт"` |
| `deviation`, `deviation_text` | Selection / Char | живе: `[('none','Норма'),('deficit','Дефіцит тепла'),('no_data','Немає даних')]` |
| `deficit_since` | Datetime | `readonly=True` (R-24) |

`_f3d_bms_balance_company_uniq = models.Constraint("UNIQUE(company_id)", "Тепловий баланс для компанії вже є.")`;
`@api.constrains` на параметри: `u_* > 0`, `0 ≤ infiltration_ach ≤ 5`, `0 ≤ winter_oa_share ≤ 1`, `0 ≤ heat_recovery
< 1`, `t_in_set > t_out_design`, `boilers ≥ 0`, `boiler_kw > 0`, `0 < boiler_stage_share ≤ 1`, `chp_heat_50_kw ≤
chp_heat_75_kw ≤ chp_heat_kw` → `ValidationError("Тепловий баланс: <параметр> поза межами.")`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `action_recompute(self)` | для кожного: `res = tools.heat.design_balance(params(self), units)` (R-14), де `units` — активні `td.bms.hvac.unit` (`kind`, `airflow_nom`); `line_ids = [Command.clear()] + [Command.create(l) for l in res['lines']]`; `write({total_raw, total_kw, capacity_kw, reserve, reserve_boilers, note, computed_at: now})`; чаттер «Перераховано: N кВт, запас X %» |
| `write(self, vals)` | після `super()`: якщо змінено будь-яке поле параметрів (список `DESIGN_FIELDS`) → `action_recompute()` |
| `action_reset_macro(self)` | `write(<умовчання таблиці вище>)` (менеджер) → перерахунок |
| `@api.model _td_bms_get(self)` | запис компанії `env.company`; немає → створює з умовчаннями й `action_recompute()` (sudo) |
| `_td_bms_live(self)` → dict | `tools.heat.live_balance(...)` (R-15, R-16) — словник для огляду, провайдера й крона |

### M-07 `td.bms.heat.balance.line` — складова балансу

`_name = "td.bms.heat.balance.line"`, `_description = "Будівля: складова теплового балансу"`, `_order = "balance_id,
sequence"`.

| Поле | Тип | Параметри |
|---|---|---|
| `balance_id` | Many2one `td.bms.heat.balance` | `req`, `ondelete="cascade"`, `idx` |
| `sequence` | Integer | `default=10` |
| `key` | Selection | `[('trans','Огородження'),('infil','Інфільтрація'),('vent_rv','Дахові установки'),('vent_ahu','Приплив фасадів'),('internal','Внутрішні надходження')]`, `req` |
| `name` | Char(256) | `req` (текст макета, R-14) |
| `kw` | Float | `digits=(10,2)` (без округлення) |
| `kw_round` | Integer | `string="кВт"` = `round(kw)` |
| `formula` | Char(512) | розшифровка з числами (R-14) |

### M-08 `td.bms.deviation` — журнал відхилень (FR-12, A-14)

```python
class F3dBmsDeviation(models.Model):
    _name = "td.bms.deviation"
    _description = "Будівля: відхилення"
    _order = "started desc, id desc"
    _rec_name = "name"
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char(256) | `req`, `string="Відхилення"` (текст R-22) |
| `signal_id` | Many2one `td.signal` | `req`, `ondelete="cascade"`, `idx` |
| `code` | Char | `related="signal_id.code"` |
| `rule` | Selection | `[('light_off','Світло вимкнено в робочий час'),('light_low','Освітленість нижче норми'),('light_fault','Аварія світильників'),('filter_supply','Фільтр припливу'),('filter_extract','Фільтр витяжки'),('unit_fault','Аварія установки'),('unit_off','Установка не працює в робочий час'),('cold','Холодно в зоні'),('overheat','Перегрів приміщення'),('charging_vent','Витяжка зарядної не працює під час заряджання'),('pressure','Тиск у дільниці фасадів'),('boiler_fault','Аварія котельні'),('heat_deficit','Дефіцит тепла'),('other','Інше')]`, `req`, `idx` |
| `object_kind` | Selection | `[('group','Група освітлення'),('panel','Щит'),('unit','Установка'),('boiler','Котельня')]` |
| `object_code` | Char(32) | `idx` (`LT-CUT`, `RV-05`, `BOILER`) |
| `equipment_id` | Many2one `maintenance.equipment` | `related="signal_id.equipment_id"`, `store=True` |
| `zone_id` | Many2one `td.zone` | `ondelete="set null"` |
| `started` | Datetime | `req`, `idx` |
| `ended` | Datetime | |
| `duration_min` | Float | `compute="_compute_duration"`, `store=True`, `digits=(10,1)` = `(ended − started)` у хв (відкриті — `False`; у списку показується живе через `now`) |
| `state` | Selection | `[('open','Триває'),('closed','Завершено')]`, `req`, `default='open'`, `idx` |
| `value` | Float | `digits=(12,2)`, `string="Показник"` (у момент відкриття; оновлюється максимальним/мінімальним у бік порушення) |
| `threshold` | Float | `digits=(12,2)`, `string="Поріг"` |
| `unit` | Char(16) | |
| `request_id` | Many2one `maintenance.request` | `ondelete="set null"` |
| `note` | Text | |

Індекси: `init()` → `CREATE INDEX IF NOT EXISTS td_bms_deviation_state_started_idx ON td_bms_deviation (state,
started)`, `…_signal_state_idx ON td_bms_deviation (signal_id, state)`. Створення/закриття — лише крон (R-22,
`sudo`); у формах `create="false"`; `write` дозволено полю `note` для `group_td_bms_operator`; `unlink` — лише
`group_td_admin`.

### M-09 Майстри керування (Transient, FR-18, R-25)

**M-09a `td.bms.light.command.wizard`**

| Поле | Тип | Параметри |
|---|---|---|
| `group_ids` | Many2many `td.bms.light.group` | `req`, `string="Групи"` |
| `action` | Selection | `[('scene','Викликати сцену'),('level','Встановити рівень')]`, `req`, `default='scene'` |
| `scene_id` | Many2one `td.bms.light.scene` | `string="Сцена"` (обов'язкове при `scene`) |
| `level_pct` | Integer | `string="Рівень, %"` (0…100, обов'язкове при `level`) |
| `fade_s` | Float | `digits=(6,1)`, `default=2.0`, `string="Час переходу, с"` (0…90 — максимум DALI за документом Helvar) |
| `expires_min` | Integer | `default=10`, `string="Дійсна, хв"` (1…60) |
| `note` | Char(256) | |

`action_apply(self)` — R-25; повертає `act_window` списку створених `td.command`.

**M-09b `td.bms.hvac.command.wizard`**

| Поле | Тип | Параметри |
|---|---|---|
| `unit_ids` | Many2many `td.bms.hvac.unit` | `req`, `domain="[('kind','in',('roofvent','ahu'))]"` |
| `action` | Selection | `[('mode','Режим'),('setpoint_day','Уставка день'),('setpoint_night','Уставка ніч')]`, `req` |
| `mode` | Selection | `[('VE','VE'),('VEL','VEL'),('AQ','AQ'),('REC','REC'),('EA','EA'),('SA','SA'),('ST','ST'),('Off','Off')]` з українськими підписами R-10 |
| `value_c` | Float | `digits=(4,1)`, `string="Уставка, °C"` (5,0…30,0) |
| `expires_min`, `note` | | як M-09a |

### M-10 `td.bms.overview` — дані огляду (FR-14)

`AbstractModel`, `_name = "td.bms.overview"`, `_description = "Будівля: огляд"`. Метод `@api.model
get_overview_data(self) -> dict` — R-28 (виконується від користувача, без `sudo`; моделі без доступу → порожні
розділи). Метод `@api.model action_open(self, model, res_id, what)` → `what ∈ {'form','show3d'}`: `form` →
`act_window` форми запису; `show3d` → `env[model].browse(res_id).action_f3d_show()`; `model ∉ {td.bms.light.group,
td.bms.light.panel, td.bms.hvac.unit, td.zone}` → `AccessError`.

### M-11 Провайдери переглядача — `AbstractModel` без `_inherit` (FR-20, A-06)

```python
class F3dViewerProviderLighting(models.AbstractModel):
    _name = "td.viewer.provider.lighting"
    _description = "3D: освітлення"
    _td_sequence = 110
    _td_sections = ("lighting",)
    _td_group = "td_factory3d.group_td_user"

class F3dViewerProviderVentilation(models.AbstractModel):
    _name = "td.viewer.provider.ventilation"
    _description = "3D: вентиляція й опалення"
    _td_sequence = 120
    _td_sections = ("ventilation",)
    _td_group = "td_factory3d.group_td_user"
```

| Метод | `.lighting` | `.ventilation` |
|---|---|---|
| `_td_viewer_collect(self, payload, ctx)` | `payload["lighting"] = tools.payload.build_lighting(self.env, ctx, payload.get("lighting") or ctx["static"].get("lighting") or {})` (R-26) | `payload["ventilation"] = tools.payload.build_ventilation(self.env, ctx, payload.get("ventilation") or ctx["static"].get("ventilation") or {})` (R-27) |
| `_td_viewer_delta(self, patch, ctx)` | якщо в `ctx["changes"]` є модель `td.bms` або коди `td.signal` з префіксом `lighting/` чи `energy/consumers/LP-` → `tmp = {}`; `self._td_viewer_collect(tmp, ctx)`; `patch["lighting"] = tmp["lighting"]`; інакше нічого | те саме для префіксів `ventilation/`, `equipment/BOILER/`, `infra/chp/`, `infra/totals/chp_kw`, `fire/totals/system_state`, `infra/ats/src1_ok` → `patch["ventilation"]` |
| `_td_viewer_bus_models(self)` | `["td.signal", "td.bms"]` | `["td.signal", "td.bms"]` |

Провайдер telemetry (95) уже записав `last_value` у вузли `lighting.groups[*]`/`ventilation.units[*]` (R-12
telemetry); провайдери модуля замінюють розділи повністю тими самими значеннями (те саме округлення R-12) плюс
обчисленими. Права: читання від користувача запиту; без доступу до моделей модуля — розділ лишається статичним.
Без `td_viewer3d` моделі не викликаються.

### M-12 `td.source` — локальний тип `f3d_bms` (CT-12, A-01)

`_inherit = "td.source"`; `type` — `selection_add=[('f3d_bms', 'Будівля (обчислені)')]`, `ondelete={'f3d_bms':
'cascade'}`; `@api.model _td_local_types(self)` → `super()._td_local_types() + ['f3d_bms']`. Джерело `BMS-DERIVED`
(xml-id `td_bms.source_bms_derived`, створює хук §5.3 крок 2): `name="Будівля: обчислені перевірки"`,
`type='f3d_bms'`, `collector_id=False`, `params={}`, `module='bms'`, `read_enabled` = параметр
`td.bms.read_enabled`, `period_s_default=60`. `state` веде модуль: крон R-18 ставить `online` після успішного
прогону, `error` + `last_error` при винятку (`sudo().write`).

### M-13 `td.signal` — розширення (A-01, R-20)

`_inherit = "td.signal"`:
1. `origin` **не** розширюється (X-16): значення `('module', 'Дані модуля')` є в базовому selection telemetry M-03;
   292 власні сигнали модуля (Додаток B) створюються з `origin='module'`, 176 рядків каталогу iot_sim — `catalog`.
2. `@api.constrains("write_enabled")`: для `module == 'bms'` і `write_enabled=True`: код не закінчується на
   `/level`, `/scene`, `/mode`, `/setpoint_day_c`, `/setpoint_night_c` або належить `EF-*`/`BOILER` →
   `ValidationError("Сигнал %s модуля «Будівля» не керується (ARCH §1.4).")`.
3. `@api.model _td_ingest(self, readings, src="module", collector=None)` (R-20): `res = super()._td_ingest(readings,
   src=src, collector=collector)`; якщо `self.env.context.get('f3d_bms_internal')` → повернути `res`; `codes = [c for c
   in res.get('changed_codes') or [] if c.startswith(('lighting/groups/', 'ventilation/units/'))]`; якщо `codes` і
   параметр `td.bms.read_enabled`: `with self.env.cr.savepoint(): self.env['td.bms.check'].sudo()._td_bms_on_ingest(codes)`;
   будь-який виняток → `_logger.exception("bms after ingest")`, `res` не змінюється; повернути `res`.

### M-14 `maintenance.request` — розширення (FR-13, A-14)

`_inherit = "maintenance.request"`:

| Поле | Тип | Параметри |
|---|---|---|
| `td_bms_rule` | Selection | ті самі значення, що `td.bms.deviation.rule`; `compute="_compute_f3d_bms_rule"`, `store=True`, `string="Правило «Будівля»"`: R-22 п. 1 за `td_signal_id.code` і `td_signal_id.module == 'bms'`, інакше `False` |
| `td_bms_deviation_ids` | One2many `td.bms.deviation` `request_id` | `string="Відхилення"` |
| `td_bms_enriched` | Boolean | `default=False`, `copy=False`, `readonly=True` — назву/значення вже доповнено (R-22 п. 3) |

`_compute_f3d_bms_rule` (`@api.depends("td_signal_id")`): `tools.rules.rule_of(code, last_text)` (R-22 п. 1); для
`…/check` — за `td_value`-незалежним текстом сигналу в момент обчислення.

### M-15 `td.zone` — розширення

`_inherit = "td.zone"`: `td_light_group_ids` (One2many `td.bms.light.group` `zone_id`, `string="Освітлення"`),
`td_hvac_unit_ids` (One2many `td.bms.hvac.unit` `zone_id`, `string="Вентиляція"`). Base не змінюється.

### M-16 `maintenance.equipment` — розширення

`_inherit = "maintenance.equipment"`: `td_bms_object` (Char, `compute`, не зберігається: `"group:<id>"`,
`"panel:<id>"`, `"unit:<id>"`, `"balance:<id>"` — перший об'єкт модуля з `equipment_id = self` (для `BOILER` —
баланс) або `False`); метод `action_f3d_bms_open(self)` → форма відповідного об'єкта.

### M-17 `res.config.settings` — розширення (FR-19)

| Поле | Тип | `config_parameter` |
|---|---|---|
| `td_bms_read_enabled` | Boolean | `td.bms.read_enabled` |
| `td_bms_write_enabled` | Boolean | `td.bms.write_enabled` (лише `group_td_admin`; `set_values` → R-30) |
| `td_bms_calendar_id` | Many2one `resource.calendar` | `td.bms.calendar_id` (id рядком) |
| `td_bms_light_check_delay_min` | Integer | `td.bms.light_check_delay_min` |
| `td_bms_light_norm_tolerance_pct` | Float | `td.bms.light_norm_tolerance_pct` |
| `td_bms_hvac_check_delay_min` | Integer | `td.bms.hvac_check_delay_min` |
| `td_bms_cold_delay_min` | Integer | `td.bms.cold_delay_min` |
| `td_bms_indoor_min_work_c` | Float | `td.bms.indoor_min_work_c` |
| `td_bms_indoor_min_off_c` | Float | `td.bms.indoor_min_off_c` |
| `td_bms_heat_deficit_kw` | Float | `td.bms.heat_deficit_kw` |
| `td_bms_heat_deficit_delay_min` | Integer | `td.bms.heat_deficit_delay_min` |
| `td_bms_check_heartbeat_min` | Integer | `td.bms.check_heartbeat_min` |
| `td_bms_light_uf`, `td_bms_light_mf` | Float | `td.bms.light_uf`, `td.bms.light_mf` |
| `td_bms_install_state` | Char | `compute`: `json.loads(param('install_report','{}')).get('state','—')` |

`set_values`: `read_enabled` змінився → R-29 п. 8 (прапори читання джерел модуля); `write_enabled` змінився → R-30.
Межі: затримки 1…240 хв, допуск 0…50 %, температури −30…40, дефіцит 0…2 000; поза межами — `ValidationError`.

## 3. Представлення й меню

Спільне: рядки UI — українською в XML; кнопка «Показати в 3D» (`action_f3d_show`, `type="object"`, `icon="fa-cube"`,
клас `btn-secondary`) — у `<header>` форм груп, щитів, установок; стани — `widget="badge"` з `decoration-success`
(`ok`/`on`/`none`), `decoration-warning` (`low`/`below_norm`/`standby`/`cold`), `decoration-danger`
(`alarm`/`fault`/`off_in_work`/`not_running`/`deficit`), `decoration-muted` (`nodata`/`no_data`/`off_hours`/`off`).
Живі поля — `readonly="1"`. Поля налаштувань (`zone_id`, `norm_id`, `n_fixtures`, `uf`, `mf`, `dali_*`, сигнали,
номінали) — `readonly="not td_is_manager"` (поле `td_is_manager` — `compute` `user.has_group('td_factory3d.group_td_manager')`
на M-02, M-03, M-05, M-06; присутнє у формах невидимим).

| ID | XML-id (`td_bms.`) | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `view_td_bms_light_norm_list`, `_form` | list (editable=bottom для менеджера), form `td.bms.light.norm` | list: `sequence` (handle), `key`, `name`, `lux`, `ugr`, `ra`, `ref_en`, `ref_dbn` (optional show), `group_count`; form: `name` (title), група «Норма»: `key`, `lux`, `ugr`, `ra`; група «Підстави»: `ref_en`, `ref_dbn`, `sources` (widget `text`); `note`; вкладка «Групи» (`group_ids` readonly: `code`, `zone_name`, `e_calc`, `design_ok`) |
| V-02 | `view_td_bms_light_panel_list` | list | `code`, `name`, `router`, `group_count`, `n_fixtures`, `p_inst_kw`, `p_now_kw`, `p_source` (optional hide), `state` (badge), `source_id` (optional show) |
| V-03 | `view_td_bms_light_panel_form` | form | `<header>`: «Показати в 3D». Статбокс: `action_view_groups` (`group_count`, «Групи», `fa-lightbulb-o`). `name` (title), `code`; група «Роутер Helvar Imagine 950»: `source_id`, `cluster`, `router`, `equipment_id`; група «Розташування»: `zone_id`, `x`, `y`; група «Зараз» (readonly): `state`, `p_now_kw`, `p_source`, `n_fixtures`, `p_inst_kw`; вкладка «Групи» (`group_ids` readonly list: `code`, `zone_name`, `n_fixtures`, `level_pct`, `e_now`, `e_norm`, `deviation` badge); «Примітка» |
| V-04 | `view_td_bms_light_group_list` | list | `sequence` (handle, лише менеджер), `code`, `zone_name`, `norm_id`, `e_norm`, `n_fixtures`, `n_required` (optional show), `e_calc` (`decoration-danger="not design_ok"`), `level_pct`, `e_now`, `p_now_kw`, `faults` (`decoration-danger="faults > 0"`), `deviation` (badge), `panel_id` (optional show), `dali_group` (optional hide), `control_mode` (optional hide), `request_count` (optional show) |
| V-05 | `view_td_bms_light_group_form` | form | `<header>`: «Показати в 3D», «Керування» (`action_open_command`, `groups="td_bms.group_td_bms_operator"`, `invisible="not td_bms_write_enabled"` — поле `compute` з параметра). Статбокс: `action_view_requests` (`request_count`, «Заявки», `fa-wrench`), `action_view_deviations` (`deviation_count`, «Відхилення», `fa-exclamation-triangle`), `action_view_readings` («Графік рівня», `fa-line-chart`). `name` (title), `code`; група «Зона й норма»: `zone_id`, `area_m2`, `norm_id`, `e_norm`, `control_mode`, `level_design`, `check_off`, `check_norm`, `calendar_id`; група «Світильники»: `passport_id`, `fixture_kind`, `lumen`, `watt`, `n_fixtures`, `panel_id`, `equipment_id`. Вкладка «Розрахунок»: `uf`, `mf`, `n_required`, `e_calc`, `design_ok` (badge «Норму виконано»/«Нижче норми»), `p_inst_kw`, статичний `<div class="text-muted">` «E = N · Φ · UF · MF / A; N потрібно = ⌈Eн · A / (Φ · UF · MF)⌉ (метод коефіцієнта використання, plant/lighting.py)». Вкладка «Зараз» (readonly): `level_pct`, `level_source`, `e_now`, `p_now_kw`, `scene`, `faults`, `faulty`, `deviation` (badge), `deviation_text`, `live_ts`, `stale`, `off_since`, `low_since`. Вкладка «DALI»: `dali_group`, `dali_devices`, `level_signal_id`, `power_signal_id`, `scene_signal_id`, `faults_signal_id`, `faulty_signal_id`, `check_signal_id`. «Примітка». Чаттер |
| V-06 | `view_td_bms_light_group_kanban` | kanban | `default_group_by="panel_id"`, `quick_create="false"`; картка: смуга кольору за `plan_state` (ok — зелена, low — жовта, off/nodata — сіра, fault/alarm — червона), `code`, `zone_name`, «`e_now` / `e_norm` лк», «`level_pct` %», `n_fixtures` світильн., `faults` (якщо > 0 — червоний бейдж), кнопка «3D» (`action_f3d_show`) |
| V-07 | `view_td_bms_light_group_search` | search | поля `code`, `name`, `zone_id`, `panel_id`, `norm_id`; фільтри «Відхилення» (`deviation in ('off_in_work','below_norm')` — пошук через `_search_deviation`), «Нижче норми за проєктом» (`design_ok = False`), «Є несправні» (`faults_signal_id.last_value > 0`), «Керування: зміна» / «присутність» (`control_mode`), «Архівні»; group by `panel_id`, `norm_id`, `control_mode` |
| V-08 | `view_td_bms_light_scene_list` | list editable (менеджер) | `block`, `number`, `name`, `level_pct`, `note` |
| V-09 | `view_td_bms_hvac_unit_list` | list | `code`, `name` (optional hide), `kind`, `zone_name`, `mode_label`, `state` (badge), `airflow_m3h`, `airflow_nom` (optional hide), `supply_c`, `indoor_c`, `heating_valve` (widget `percentage`), `heat_kw`, `filter_dp_pa` (`decoration-danger="filter_dp_pa > 250"`), `filter_extract_dp_pa` (optional hide), `p_now_kw`, `deviation` (badge), `request_count` (optional show) |
| V-10 | `view_td_bms_hvac_unit_form` | form | `<header>`: «Показати в 3D», «Керування» (`action_open_command`, оператор, `invisible="not td_bms_write_enabled or kind not in ('roofvent','ahu')"`). Статбокс: заявки, відхилення, «Графіки» (`action_view_readings`: витрата, фільтр, приплив, тепло). `name` (title), `code`; група «Установка»: `kind`, `zone_id`, `x`, `y`, `equipment_id`, `passport_id`, `source_id`, `bacnet_device`; група «Номінали»: `airflow_nom`, `heat_nom_kw`, `p_inst_kw`, `fan_count`, `required_m3h` (`invisible="kind != 'exfan'"`), `t_supply_design` (`invisible="kind != 'ahu'"`), `mode_design`, `required_in_work`, `calendar_id`. Вкладка «Зараз» (readonly): `mode_label`, `mode_code`, `state`, `airflow_m3h`, `k` (widget `percentage`), `supply_c`, `indoor_c`, `heating_valve` (percentage), `heat_kw`, `p_now_kw`, `filter_dp_pa`, `filter_extract_dp_pa`, `setpoint_day_c`, `setpoint_night_c`, `room_pressure_pa` (`invisible="kind != 'ahu'"`), `deviation` (badge), `deviation_text`, `live_ts`, `stale`. Вкладка «BACnet» — 15 полів сигналів. «Примітка» (`note`). Чаттер |
| V-11 | `view_td_bms_hvac_unit_kanban` | kanban | `default_group_by="kind"`; картка: смуга за `plan_state`, `code`, `zone_name`, `mode_label`, «`airflow_m3h` м³/год», фільтр «`filter_dp_pa` Па» (червоний > 250), «`heat_kw` кВт», кнопка «3D» |
| V-12 | `view_td_bms_hvac_unit_search` | search | поля `code`, `zone_id`, `kind`; фільтри «Відхилення» (`_search_deviation`), «Фільтр понад норму» (`filter_signal_id.status = 'alarm'`), «Дахові установки» (`kind='roofvent'`), «Вентилятори» (`kind in (fan, exfan)`); group by `kind`, `zone_id`, `mode_design` |
| V-13 | `view_td_bms_heat_balance_form` | form `td.bms.heat.balance` | `<header>`: «Перерахувати» (`action_recompute`, менеджер), «Повернути значення макета» (`action_reset_macro`, менеджер, `confirm="Повернути параметри макета?"`). Заголовок `name`; група «Зараз» (readonly): `outdoor_c`, `heat_need_kw`, `chp_heat_now_kw`, `chp_source`, `boilers_on_calc`, `boilers_on`, `boiler_state`, `boiler_load` (percentage), `boiler_heat_kw`, `supply_c`, `return_c`, `silo_fill` (percentage), `deficit_kw`, `deviation` (badge), `deviation_text`; група «Зима, розрахунок» (readonly): `total_kw`, `capacity_kw`, `chp_heat_kw`, `reserve` (percentage, «Запас із КГУ»), `reserve_boilers` (percentage), `computed_at`; `line_ids` (list readonly: `name`, `kw_round`, `formula`); `note`. Вкладка «Параметри» (менеджер редагує): `t_out_design`, `t_in_set`, `length_m`, `width_m`, `height_m`, `u_wall`, `u_roof`, `u_floor`, `infiltration_ach`, `winter_oa_share`, `heat_recovery`, `air_wh_m3k`, `ahu_design_share`, `ahu_supply_c`, `internal_gains_kw`, `boilers`, `boiler_kw`, `boiler_stage_share`, `chp_el_kw`, `chp_heat_kw`, `chp_heat_75_kw`, `chp_heat_50_kw`, `chp_min_load`. Вкладка «Сигнали» — 11 сигналів, `boiler_equipment_id`, `chp_equipment_id`. Чаттер. Кнопки «Показати в 3D» котельні (`boiler_equipment_id.action_f3d_show` через метод `action_show_boiler`) |
| V-14 | `view_td_bms_deviation_list` | list `td.bms.deviation` (`create="false"`) | `started`, `object_code`, `rule`, `name`, `value`, `threshold`, `unit`, `duration_min`, `state` (badge: open → danger, closed → muted), `request_id`, `ended` (optional hide); `decoration-danger="state == 'open'"` |
| V-15 | `view_td_bms_deviation_graph`, `_pivot` | graph (bar, `rule`, `__count`), pivot (рядки `rule`, стовпці `started:week`, міри `__count`, `duration_min`) | |
| V-16 | `view_td_bms_deviation_search`, `_form` | search: поля `object_code`, `rule`, `equipment_id`, `zone_id`; фільтри «Відкриті» (`state='open'`), «Сьогодні», «7 днів», «Освітлення» (`object_kind in (group, panel)`), «Вентиляція» (`unit`), «Котельня» (`boiler`); group by `rule`, `object_code`, `started:day`. form readonly, крім `note` | |
| V-17 | `view_td_zone_form_bms` | form inherit `td_factory3d.view_td_zone_form` | `//notebook` inside: `<page name="f3d_bms" string="Будівля" invisible="not td_light_group_ids and not td_hvac_unit_ids">`: `td_light_group_ids` (readonly: `code`, `e_norm`, `e_calc`, `level_pct`, `e_now`, `deviation`), `td_hvac_unit_ids` (readonly: `code`, `mode_label`, `airflow_m3h`, `filter_dp_pa`, `deviation`) |
| V-18 | `view_maintenance_equipment_form_bms`, `view_maintenance_request_form_bms` | inherit `maintenance.hr_equipment_view_form`, `maintenance.hr_equipment_request_view_form` | обладнання: `//div[@name='button_box']` inside — кнопка `action_f3d_bms_open` («Будівля», `fa-building`, `invisible="not td_bms_object"`); заявка: у групі «Телеметрія» telemetry (V-20 telemetry, `//group[@name='f3d_telemetry']`) після `td_threshold` — `td_bms_rule` (`invisible="not td_bms_rule"`), `td_bms_deviation_ids` (readonly list: `started`, `ended`, `value`, `state`) ; список заявок: `td_bms_rule` (optional hide); пошук: group by `td_bms_rule` |
| V-19 | `view_td_bms_light_command_wizard_form` | form M-09a | `<div class="alert alert-warning">` «Команда виконається, лише якщо керування дозволено в модулі «Будівля», телеметрії, джерелі, сигналі й колекторі»; `group_ids` (tags), `action` (radio), `scene_id` (`invisible="action != 'scene'"`, `required="action == 'scene'"`), `level_pct` (`invisible="action != 'level'"`), `fade_s`, `expires_min`, `note`; footer «Надіслати» (`action_apply`, `btn-primary`), «Скасувати» |
| V-20 | `view_td_bms_hvac_command_wizard_form` | form M-09b | те саме попередження; `unit_ids`, `action`, `mode` (`invisible="action != 'mode'"`), `value_c` (`invisible="action == 'mode'"`), `expires_min`, `note` |
| V-21 | меню (`views/menus.xml`) | `ir.ui.menu`, дії | таблиця нижче |
| V-22 | `res_config_settings_view_form_td_bms` | inherit `base.res_config_settings_view_form` | блок «Завод 3D» (як telemetry V-21: `//block[@name='td_base_settings']` або власний `name="td_bms_settings"`): «Будівля»: `td_bms_read_enabled` («Читати освітлення й вентиляцію»), `td_bms_write_enabled` («Дозволити керування», `groups="td_factory3d.group_td_admin"`); «Перевірки»: `td_bms_calendar_id`, `light_check_delay_min`, `light_norm_tolerance_pct`, `hvac_check_delay_min`, `cold_delay_min`, `indoor_min_work_c`, `indoor_min_off_c`, `heat_deficit_kw`, `heat_deficit_delay_min`, `check_heartbeat_min`; «Розрахунок освітлення»: `light_uf`, `light_mf`; «Дані»: `td_bms_install_state`, кнопка «Повторити установку даних» (admin) |
| V-23 | `action_td_bms_overview` | `ir.actions.client`, `tag="td_bms.overview"`, `name="Будівля"`, `target="current"` | OWL-компонент R-28 |

Меню (CB-09, sequence 80 під `td_factory3d.menu_td_root`):

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_td_bms` | Будівля | `td_factory3d.menu_td_root` | 80 | `group_td_user` | — |
| `menu_td_bms_overview` | Огляд | `menu_td_bms` | 10 | `group_td_user` | `action_td_bms_overview` |
| `menu_td_bms_lighting` | Освітлення | `menu_td_bms` | 20 | `group_td_user` | — |
| `menu_td_bms_light_group` | Групи | `menu_td_bms_lighting` | 10 | `group_td_user` | `action_td_bms_light_group` (kanban,list,form) |
| `menu_td_bms_light_panel` | Щити | `menu_td_bms_lighting` | 20 | `group_td_user` | `action_td_bms_light_panel` (list,form) |
| `menu_td_bms_light_norm` | Норми освітленості | `menu_td_bms_lighting` | 30 | `group_td_user` | `action_td_bms_light_norm` (list,form) |
| `menu_td_bms_hvac` | Вентиляція й опалення | `menu_td_bms` | 30 | `group_td_user` | — |
| `menu_td_bms_hvac_unit` | Установки | `menu_td_bms_hvac` | 10 | `group_td_user` | `action_td_bms_hvac_unit` (list,kanban,form) |
| `menu_td_bms_heat_balance` | Тепловий баланс | `menu_td_bms_hvac` | 20 | `group_td_user` | `action_td_bms_heat_balance_open` (`ir.actions.server`, `code="action = env['td.bms.heat.balance']._td_bms_get().get_formview_action()"`) |
| `menu_td_bms_deviation` | Відхилення | `menu_td_bms` | 40 | `group_td_user` | `action_td_bms_deviation` (list,graph,pivot,form; `context={'search_default_open': 1}`) |
| `menu_td_bms_config` | Будівля | `td_factory3d.menu_td_config` | 80 | `group_td_manager` | — |
| `menu_td_bms_config_scene` | Сцени DALI | `menu_td_bms_config` | 10 | `group_td_manager` | `action_td_bms_light_scene` |
| `menu_td_bms_config_settings` | Налаштування будівлі | `menu_td_bms_config` | 20 | `group_td_admin` | `action_td_bms_settings` (`res.config.settings`, `context={'module': 'td_bms'}`) |
| `menu_td_bms_config_reinstall` | Повторити установку даних будівлі | `menu_td_bms_config` | 90 | `group_td_admin` | `ir.actions.server` `action_td_bms_reinstall`: `code="action = env['td.bms.check'].f3d_bms_reinstall_data()"` |

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_bms_light_norm_user,td.bms.light.norm user,model_td_bms_light_norm,td_factory3d.group_td_user,1,0,0,0
access_td_bms_light_norm_manager,td.bms.light.norm manager,model_td_bms_light_norm,td_factory3d.group_td_manager,1,1,1,1
access_td_bms_light_panel_user,td.bms.light.panel user,model_td_bms_light_panel,td_factory3d.group_td_user,1,0,0,0
access_td_bms_light_panel_manager,td.bms.light.panel manager,model_td_bms_light_panel,td_factory3d.group_td_manager,1,1,1,1
access_td_bms_light_group_user,td.bms.light.group user,model_td_bms_light_group,td_factory3d.group_td_user,1,0,0,0
access_td_bms_light_group_manager,td.bms.light.group manager,model_td_bms_light_group,td_factory3d.group_td_manager,1,1,1,1
access_td_bms_light_scene_user,td.bms.light.scene user,model_td_bms_light_scene,td_factory3d.group_td_user,1,0,0,0
access_td_bms_light_scene_manager,td.bms.light.scene manager,model_td_bms_light_scene,td_factory3d.group_td_manager,1,1,1,1
access_td_bms_hvac_unit_user,td.bms.hvac.unit user,model_td_bms_hvac_unit,td_factory3d.group_td_user,1,0,0,0
access_td_bms_hvac_unit_manager,td.bms.hvac.unit manager,model_td_bms_hvac_unit,td_factory3d.group_td_manager,1,1,1,1
access_td_bms_heat_balance_user,td.bms.heat.balance user,model_td_bms_heat_balance,td_factory3d.group_td_user,1,0,0,0
access_td_bms_heat_balance_manager,td.bms.heat.balance manager,model_td_bms_heat_balance,td_factory3d.group_td_manager,1,1,1,0
access_td_bms_heat_balance_line_user,td.bms.heat.balance.line user,model_td_bms_heat_balance_line,td_factory3d.group_td_user,1,0,0,0
access_td_bms_heat_balance_line_manager,td.bms.heat.balance.line manager,model_td_bms_heat_balance_line,td_factory3d.group_td_manager,1,1,1,1
access_td_bms_deviation_user,td.bms.deviation user,model_td_bms_deviation,td_factory3d.group_td_user,1,0,0,0
access_td_bms_deviation_operator,td.bms.deviation operator,model_td_bms_deviation,td_bms.group_td_bms_operator,1,1,0,0
access_td_bms_deviation_admin,td.bms.deviation admin,model_td_bms_deviation,td_factory3d.group_td_admin,1,1,1,1
access_td_bms_light_command_wizard_operator,td.bms.light.command.wizard operator,model_td_bms_light_command_wizard,td_bms.group_td_bms_operator,1,1,1,1
access_td_bms_hvac_command_wizard_operator,td.bms.hvac.command.wizard operator,model_td_bms_hvac_command_wizard,td_bms.group_td_bms_operator,1,1,1,1
```

Абстрактні `td.bms.overview`, `td.bms.check`, `td.viewer.provider.lighting/.ventilation` рядків не потребують.
`td.bms.deviation.write` для оператора обмежено кодом: `write(vals)` → якщо `set(vals) - {'note'}` і не `env.su` →
`AccessError("Журнал відхилень веде система; можна змінювати лише примітку.")`.

### 4.2 Групи (`security/security.xml`)

```xml
<record id="privilege_td_bms" model="res.groups.privilege">
    <field name="name">Завод 3D: будівля</field>
    <field name="category_id" ref="td_factory3d.module_category_factory3d"/>
    <field name="sequence">80</field>
</record>
<record id="group_td_bms_operator" model="res.groups">
    <field name="name">Будівля: оператор</field>
    <field name="privilege_id" ref="privilege_td_bms"/>
    <field name="sequence">10</field>
    <field name="comment">Енергетик, головний механік: керування освітленням і вентиляцією (якщо дозволено), журнал відхилень.</field>
    <field name="implied_ids" eval="[Command.link(ref('td_factory3d.group_td_user'))]"/>
</record>
<record id="td_factory3d.group_td_manager" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_td_bms_operator'))]"/>
</record>
```

Ланцюжок: `group_td_user` ⊂ `group_td_bms_operator` ⊂ `group_td_manager` ⊂ `group_td_admin` ⊂ `base.group_system`.
Група — у власному привілеї `privilege_td_bms` (sequence 80 = резерв меню bms) категорії
`td_factory3d.module_category_factory3d` (X-19); драбина base `privilege_td` (Користувач/Менеджер/Адміністратор, CB-10)
не змінюється — base лише отримує implied-зв'язок `group_td_manager` → `group_td_bms_operator`.

### 4.3 Record rules

| XML-id | Модель | Домен | Групи |
|---|---|---|---|
| `td_bms_heat_balance_rule_company` | `td.bms.heat.balance` | `[('company_id','in',company_ids)]` | глобальне |

Решта моделей — без компанії (одна будівля; як зони base без компанії в мультикомпанійному режимі — CB-03 має
`company_id`, групи успадковують видимість зони через `zone_id`: record rule base на `td.zone` → недоступна зона робить
групу нечитабельною лише для `zone_id`; окреме правило не потрібне).

### 4.4 Захист полів і дій

- Поля налаштувань груп/установок/балансу — запис лише `group_td_manager` (ACL); оператор має читання + майстри.
- `td.bms.light.group.action_open_command`, майстри M-09 — `_td_bms_check_operator()`: `has_group('td_bms.group_td_bms_operator')`
  інакше `AccessError("Керування доступне енергетику й головному механіку (група «Будівля: оператор»).")`.
- `res.config.settings.td_bms_write_enabled` — `groups="td_factory3d.group_td_admin"`; `set_values` перевіряє групу
  ще раз (поле може прийти з RPC) → `AccessError`.
- `f3d_bms_reinstall_data` — лише `group_td_admin` → інакше `AccessError`.
- Сигнали модуля пишуться в `td.signal` лише хуком (`sudo`) і кроном через CT-10; ACL telemetry (менеджер) діє для
  ручних правок порогів у формі сигналу.

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)

| key | value | XML-id | Примітка |
|---|---|---|---|
| `td.bms.read_enabled` | `True` | `param_read_enabled` | хук перезаписує за CB-10 |
| `td.bms.write_enabled` | `False` | `param_write_enabled` | |
| `td.bms.calendar_id` | `` | `param_calendar_id` | порожньо — календар компанії |
| `td.bms.light_check_delay_min` | `10` | `param_light_check_delay` | |
| `td.bms.light_norm_tolerance_pct` | `5` | `param_light_norm_tol` | |
| `td.bms.hvac_check_delay_min` | `10` | `param_hvac_check_delay` | |
| `td.bms.cold_delay_min` | `30` | `param_cold_delay` | |
| `td.bms.indoor_min_work_c` | `16.0` | `param_indoor_min_work` | |
| `td.bms.indoor_min_off_c` | `10.0` | `param_indoor_min_off` | |
| `td.bms.heat_deficit_kw` | `20` | `param_heat_deficit_kw` | |
| `td.bms.heat_deficit_delay_min` | `30` | `param_heat_deficit_delay` | |
| `td.bms.check_heartbeat_min` | `10` | `param_check_heartbeat` | |
| `td.bms.light_uf` | `0.7` | `param_light_uf` | `plant/lighting.py:UF` |
| `td.bms.light_mf` | `0.8` | `param_light_mf` | `MF` |
| `td.bms.install_report` | `{}` | `param_install_report` | звіт хука |

Читання булевих: `get_param(key, 'False') in ('True', 'true', '1')`; чисел — `float(get_param(key) or default)` з
умовчанням таблиці при помилці розбору (WARNING у лог).

### 5.2 Data-файли з макета і генератор `tools/gen_data.py`

Запуск (розробник, з кореня репозиторію): `python3 odoo_addons/td_bms/tools/gen_data.py --root .`. Імпортує
`plant.lighting`, `plant.ventilation`, `plant.layout`, читає `plant/lux_norms.json`, `plant/equipment_specs.json`;
пише детерміновано (сортування, без часових міток):

- **`data/td_bms_light_norm_data.xml`** — 13 `td.bms.light.norm` (xml-id `norm_<key>`; `sequence` = порядок у
  json × 10; `name` — `plant/lighting.py:NORM_NAMES`, для `sanding` — «шліфування, оздоблення фасадів», для
  `quality_control` — «контроль якості»; `lux`, `ugr`, `ra`, `ref_en` = `ref`, `note`, `sources` = `"\n".join(sources)`).
  Ефективні значення лк — Додаток A.0.
- **`data/td_bms_light_scene_data.xml`** — 6 сцен M-04 (xml-id `scene_1…scene_6`).
- **`data/td_bms_source_data.xml`** — 32 `td.source` (Додаток C): xml-id `source_hn_lp_<n>` і `source_bac_<device>`;
  `collector_id` → `td_telemetry.collector_main`; `module='bms'`; `read_enabled` у XML `True` (хук виправляє за
  параметром); `write_enabled=False`; `params` — `eval` Python-словника.
- **`data/td_bms_light_data.xml`** — 3 щити (xml-id `panel_lp_<n>`) і 32 групи (xml-id `group_<slug>`, slug = код
  у нижньому регістрі з `-`→`_`: `group_lt_cut`): `code`, `name` (= назва обладнання в демо «Освітлення: <назва зони>»),
  `sequence`, `zone_id` → `td_factory3d.zone_<slug зони>`, `norm_id` → `norm_<task>`, `panel_id`, `passport_id` →
  `td_factory3d.passport_highbay` / `passport_highbay_rack`, `fixture_kind`, `n_fixtures`, `level_design`,
  `control_mode` (`shift`, якщо `level == 1.0`, інакше `presence`), `dali_group` (= № у каталозі 1…32), `dali_devices`
  (R-06). Повний зміст — Додаток A.1, A.2.
- **`data/td_bms_hvac_data.xml`** — 29 установок (xml-id `unit_<slug>`: `unit_rv_05`, `unit_ahu_1`, `unit_ef_elec`)
  і баланс `heat_balance_main` (умовчання M-06, `company_id` → `base.main_company`). Додаток A.3.
- **`data/bms_signals.csv`** (549 рядків, Додаток B): `code,name,quantity,kind,unit,object,role,equipment,source,
  address,period_s,store_period_s,scale,decimals,states,alarm_low,alarm_high,warn_high,alarm_states,alarm_title,
  hysteresis,min_duration_s,viewer_visible,create_request,origin,writable,new`; JSON-колонки — компактний JSON;
  `writable=1` — 142 керовані сигнали (A-21); `new=0` — 81 сигнал макета (оновлення прив'язки), `new=1` — 468.

Невідомий ключ макета (нова зона в `LIGHT_ZONES`, нова установка в `ROOFVENTS`) → генератор падає з повідомленням
(щоб зміна макета не пройшла непоміченою); `tests/test_data_sync.py` порівнює згенероване з репозиторієм побайтово.

### 5.3 `post_init_hook(env)` — кроки, джерела, ідемпотентність, очікувані кількості (R-29)

`hooks.run_install(env) -> dict`; `post_init_hook = run_install + звіт`. Усе в транзакції установки; виняток на
будь-якому кроці відкочує установку. Логер `odoo.addons.td_bms.hooks`, INFO з лічильниками.

| # | Функція | Що робить | Ідемпотентність | Очікувано (копія демо з base + telemetry) | Чиста база (base + telemetry) |
|---|---|---|---|---|---|
| 1 | `params(env)` | `read_enabled = (td.base.environment == 'test')`; `write_enabled = 'False'` | перезапис | `read_enabled=True` | те саме |
| 2 | `derived_source(env)` | `td.source` `BMS-DERIVED` (M-12) з xml-id `td_bms.source_bms_derived` (через `ir.model.data` `_update_xmlids`) | upsert за `code` | `created: 1` | те саме |
| 3 | `link_equipment(env)` | для щитів, груп, установок: `env['maintenance.equipment'].search_f3d(code)` → `equipment_id` (лише порожні); баланс: `boiler_equipment_id = search_f3d('BOILER')`, `chp_equipment_id = search_f3d('CHP')`; джерела модуля: `equipment_id` = обладнання з кодом у `code` джерела (`BAC-105-RV-05` → `RV-05`, `HN-LP-2` → `LP-2`) | лише порожні | `panels: 3`, `groups: 32`, `units: 29`, `balance: 2`, `sources: 32`, `not_found: 0` | `not_found: 66` (WARNING на кожен) |
| 4 | `signals(env)` | `bms_signals.csv`: `sig = search([('code','=',code)], active_test=False)`; `new=0` і є → `write` полів прив'язки (`source_id`, `address`, `period_s`, `store_period_s`, `scale`, `decimals`, `viewer_visible`, `module='bms'`, `active=True`, `equipment_id` якщо порожнє; пороги/`alarm_title`/`hysteresis` — лише з непорожніх колонок); `new=0` і немає (чиста база) або `new=1` і немає → `create` (усі колонки; `origin` з CSV; `equipment_id` = `search_f3d(equipment)`; `source_id` за кодом джерела; `write_enabled=False`); `new=1` і є → `write` визначення без `last_*`/`status`/`origin`; xml-id `td_bms.sig_<slug>` для створених (`slug` — правило telemetry Додаток D) | upsert за `code` | `created: 468`, `updated: 81`, `no_equipment: 0` | `created: 549`, `updated: 0` |
| 5 | `link_signals(env)` | поля сигналів M-02/M-03/M-05/M-06 за кодами Додатка B (колонки `object`, `role`); баланс: `outdoor` = `ventilation/totals/outdoor_c`, `boiler_state` = `equipment/BOILER/state`, `boiler_supply` = `…/supply_c` (telemetry), `boiler_return` = `…/return_c`, `boiler_heat` = `…/heat_kw`, `silo` = `…/silo_fill` (telemetry), `chp_heat` = `infra/chp/heat_kw` (energy, якщо існує), `chp_el` = `infra/totals/chp_kw` (energy/рівень 0, якщо існує), `mains` = `infra/ats/src1_ok` (energy, якщо існує), `fire` = `fire/totals/system_state` (fire_safety, якщо існує), `check` = `ventilation/heat_plant/check` | перезапис | `links: 549 − 0` (усі ролі), `optional_missing: ['infra/chp/heat_kw', 'infra/ats/src1_ok', 'fire/totals/system_state']` (на демо без energy/fire_safety; `infra/totals/chp_kw` є з рівня 0) | ті самі `optional_missing` + `infra/totals/chp_kw` |
| 6 | `read_flags(env)` | джерела модуля (32 + `BMS-DERIVED`): `read_enabled` = параметр п. 1 | перезапис | `sources_read: 33` | те саме |
| 7 | `write_flags(env)` | R-30 з `write_enabled=False` | перезапис | `signals_write: 0` | те саме |
| 8 | `recompute(env)` | `td.bms.heat.balance._td_bms_get().action_recompute()`; групи — stored compute уже пораховані | — | `total_kw: 753` | `753` |
| 9 | `demo_request(env)` | для відкритих заявок із `td_signal_id.module == 'bms'` і статусом сигналу `alarm` — епізод журналу `state='open'`, `started = request.create_date`, `value = td_value`, `threshold = td_threshold`, `request_id` | за `(signal_id, state='open')` | `deviations: 1` (заявка id 6, RV-05) | 0 |
| 10 | `report(env, report)` | `td.bms.install_report = json.dumps({state, ts, ...})`; `state='partial'`, якщо `not_found > 0` або сигналів створено/оновлено менше за 549, інакше `done` | перезапис | `done` | `partial` (немає обладнання) |

Метод `td.bms.check.f3d_bms_reinstall_data()` (`@api.model`, лише `group_td_admin`) → `hooks.run_install(env)`,
повертає `display_notification` зі звітом (`sticky=True`). Повторний запуск: кроки 2–9 нічого не дублюють (лічильники
`created: 0`).

### 5.4 `uninstall_hook(env)`

1. `env['ir.config_parameter'].search([('key','=like','td.bms.%')]).unlink()`.
2. Сигнали `module='bms'` з `origin ∈ {catalog, module}` → `write({'active': False, 'source_id': False, 'write_enabled': False})`;
   81 сигнал макета (`origin='sim_data'`) → `write({'source_id': False, 'address': {}, 'write_enabled': False})`.
3. Відкриті `td.command` на сигналах модуля у `queued` → `cancelled` (через `action_cancel`).
4. `maintenance.request`, `td.reading`, `td.reading.hour` — не чіпаються; моделі модуля, джерела з даних модуля і
   тип `f3d_bms` (`ondelete='cascade'` → `BMS-DERIVED`) видаляються стандартно.

### 5.5 Повторна установка

Після деінсталяції й нової установки: сигнали з п. 2 §5.4 знаходяться за `code` з `active_test=False` (крок 4 §5.3) і
повертаються `active=True` із джерелами; історія показань зберігається.

### 5.6 `data/neutralize.sql`

```sql
-- td_bms: нейтралізація копії проду (CB-10, каркас §5)
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('td.bms.read_enabled', 'td.bms.write_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_bms';
UPDATE td_source SET read_enabled = false, write_enabled = false, state = 'disabled' WHERE module = 'bms';
UPDATE td_signal SET write_enabled = false WHERE module = 'bms';
```

## 6. Крони й фонові процеси (`data/ir_cron.xml`)

| XML-id | Назва | Інтервал | Модель / метод | Один прогін | Ліміти |
|---|---|---|---|---|---|
| `cron_td_bms_check` | Будівля: перевірка відхилень | 1 хв, `active=True` | `td.bms.check._cron_check` | якщо `read_enabled=False` → вихід; інакше: (1) `SignalCache` усіх сигналів модуля (один `search_read`, 549); (2) робочий час (R-18) для календарів груп/установок; (3) придушення (R-21); (4) правила груп (R-19), установок (R-23), котельні (R-24) → список показань стан-сигналів, що змінили текст або чекають heartbeat; (5) один `env['td.signal'].with_context(f3d_bms_internal=True).sudo()._td_ingest(readings, src='module')`; (6) доповнення нових заявок і журнал (R-22); (7) `BMS-DERIVED.state='online'`, `last_ok=now`; (8) шина CH-06 для об'єктів зі зміненим відхиленням | ≤ 2 с на 61 об'єкт; виняток → `BMS-DERIVED.state='error'`, `last_error` (≤ 512), лог `exception`, транзакція крона відкочується (наступний прогін повторить) |

Крон від `base.user_root`; заявок напряму не створює (лише через telemetry CT-05 у п. 5).

## 7. HTTP/JSON API

Власних HTTP-маршрутів немає. Показання надходять через telemetry API-02 (колектор) і CT-10 (крон). Клієнт OWL
викликає ORM: `orm.call('td.bms.overview', 'get_overview_data', [])` і `orm.call('td.bms.overview', 'action_open',
[model, res_id, what])` — стандартний `/web/dataset/call_kw` із сесією користувача (права ORM). Контракт відповіді
`get_overview_data` — R-28.

## 8. Сервісна частина — плагін колектора `helvarnet` (CT-02, FR-23)

### 8.1 Пакет, встановлення, залежності

- Пакет `f3d-collector-bms` 0.1.0 (§0.2), Python 3.12, **лише stdlib** (`asyncio`, `statistics`, `re`, `time`) і
  ядро колектора telemetry (`collector.plugins.base.SourcePlugin`, `collector.core.types`, `collector.core.errors`).
- Entry point: `[project.entry-points."factory3d_collector.plugins"] helvarnet = "f3d_collector_bms.helvarnet:HelvarNetPlugin"`;
  ядро знаходить його через `load_plugins()` (telemetry §8.3.2). Без пакета джерела `helvarnet` отримують
  `Health(state='error', error='plugin helvarnet not installed')`, решта колектора працює.
- Тести: `pytest services/collector_plugins/f3d_collector_bms` (у середовищі, де встановлено пакет колектора
  `services/collector` у режимі `pip install -e`); `pytest-asyncio` — з `requirements.txt` колектора.
- Еталон протоколу: Helvar «HelvarNet Overview» (Designer 4.2.18 Help File, с. 409–503;
  https://aca.im/driver_docs/Helvar/HelvarNet-Overview.pdf, переглянуто 14.10.2026): TCP-порт роутера **50000**, UDP
  50001; ASCII `>`…`#`, відповідь `?…=…#`, частковий кадр `$`, помилка `!…=<код>#`; ≤ 1 500 байт; параметри `V`, `C`,
  `G`, `B`, `S`, `L`, `F` (сотні секунди: `F:9000` = 90 с), `A` (підтвердження), адреса `@кластер.роутер.підмережа.пристрій`;
  запити до будь-якого роутера маршрутизуються в систему; «Push Messages» (ввімкнення в Designer). Розбіжності з
  iot_sim §8.10.4 — Q-04/Q-09.

### 8.2 Схеми (CH-05; розширення telemetry Додатка A.1/A.2 без зміни обов'язкових ключів)

#### 8.2.1 `params` джерела (`schemas/params.helvarnet.json`; Odoo — `tools.address` telemetry + перевірка в M-02)

| Ключ | Тип | Обов. | За замовч. | Обмеження |
|---|---|---|---|---|
| `host` | str | так | — | ім'я/IP (telemetry A.0) |
| `port` | int | ні | 50000 | 1…65535 |
| `protocol` | str | ні | `tcp` | `tcp`, `udp` (`udp` у v1 → `ConnectError("udp not supported")`) |
| `timeout_s` | number | ні | 3 | 0,5…30 — очікування відповіді на запит |
| `cluster` | int | так (bms) | 1 | 1…253 |
| `router` | int | так (bms) | — | 1…254; роутер щита (`LP-1` → 1) |
| `version` | int | ні | 2 | 1, 2 — значення `V` |
| `rate_per_s` | int | ні | 20 | 1…100 — запитів/с на TCP-сеанс (спільний для всіх джерел `host:port`) |
| `push` | bool | ні | `true` | обробляти push-повідомлення роутера (R-36) |
| `membership_ttl_s` | int | ні | 3600 | 60…86 400 — кеш складу груп (C:164) |

#### 8.2.2 `address` сигналу (`schemas/address.helvarnet.json`)

| Ключ | Тип | Обов. | За замовч. | Обмеження / зміст |
|---|---|---|---|---|
| `group` | int | так для `query` ∈ {`level`, `power`, `scene`, `faults`, `faulty`} | — | 1…16383 (= `dali_group`) |
| `device` | str | так для `query='router'` | — | `^@\d{1,3}\.\d{1,3}\.\d{1,4}\.\d{1,3}$`; для `router` — `@<cluster>.<router>.0.0` |
| `query` | str | ні | `level` | `level` (C:152, %), `power` (C:161, Вт), `scene` (C:109), `faults` (C:110, кількість), `faulty` (C:110, текст адрес), `router` (C:102 + агрегат, стан) |
| `devices` | list[str] | ні | — | фолбек складу групи: елементи `@c.r.s.d` або `@c.r.s.d1-d2` (≤ 64 елементи) |
| `sample` | int | ні | 3 | 1…16 — пристроїв для рівня (R-32) |
| `mask` | int | ні | 134217742 (`0x0800000E`) | біти C:110, що вважаються несправністю: LampFailure 0x2, Missing 0x4, Faulty 0x8, CommsError 0x08000000 |
| `scale` | number | ні | 1 | множник значення (для `power` — 0,001: Вт → кВт) |
| `fade_s` | number | ні | 2,0 | 0…90 — час переходу при записі (`F = round(fade_s·100)`) |
| `block` | int | ні | 1 | 1…8 — блок сцен для `scene` |
| `map` | object | ні | — | для `router`: `{"ok": "ok", "fault": "fault"}` (довідково) |

В Odoo адресу перевіряє валідатор telemetry (A.1: обов'язкові `group` або `device`, `query`, `map`; додаткові ключі
дозволені A.0) — модуль його не перевизначає; повну схему (діапазони `sample`, `mask`, формат `devices`) перевіряють
плагін (`validate()` до `connect()`, помилка → джерело `error: "schema: …"`) і тест `test_data_sync.py` для даних модуля.

### 8.3 Класи й інтерфейс

```python
class HelvarNetPlugin(SourcePlugin):
    type = "helvarnet"
    version = "0.1.0"
    address_schema = load_schema("address.helvarnet.json")
    params_schema = load_schema("params.helvarnet.json")
    push_mode = False          # ядро планує poll(); push-кадри роутера плагін емітує сам через ctx.emit (R-36)

    def __init__(self, source: SourceCfg, ctx: PluginContext): ...
    async def connect(self) -> None            # R-31: ctx.allowlist(host); ConnectionPool.acquire(host, port, protocol)
    async def disconnect(self) -> None         # ConnectionPool.release(...): закриває сеанс, коли не лишилось джерел
    async def poll(self, signals) -> list[Reading]   # R-32…R-35
    async def subscribe(self) -> None          # не використовується (push_mode=False) → NotSupported
    async def write(self, signal, value, text) -> str  # R-37
    def health(self) -> Health                 # §8.6
```

`protocol.py` (чисті функції, без мережі):

| Функція | Вхід → вихід |
|---|---|
| `build_query(version, cmd, group=None, address=None, extra=None) -> str` | `>V:{v},C:{cmd}[,G:{g}][,{k}:{x}…][,{address}]#`; `address` — рядок `@c.r.s.d` або `@c` (для C:102); порядок параметрів — `V`, `C`, `G`, `B`, `S`, `L`, `F`, `A`, далі адреса |
| `build_command(version, cmd, group, level=None, scene=None, block=1, fade_cs=200, ack=True) -> str` | C:13 → `>V:2,C:13,G:12,L:60,F:200,A:1#`; C:11 → `>V:2,C:11,G:12,B:1,S:3,F:200,A:1#` |
| `parse_frame(text) -> Frame` | `Frame(kind ∈ {'reply','error','push','partial'}, version, cmd, params: dict, address: str|None, answer: str|None)`; `?…=…#` → `reply`; `!…=<n>#` → `error`, `answer` = код; `>…#` → `push`; закінчення `$` → `partial`; інше → `ProtocolError` |
| `split_stream(buffer: bytes) -> (frames: list[str], rest: bytes)` | ділить потік на кадри за `#` і `$` (ASCII, `latin-1` декодування), відкидає байти до першого `?`/`!`/`>`; кадр > 1 500 байт → `ProtocolError` |
| `decode_level(answer: str) -> int` | `n = int(answer)`; `n & 0x80000000` → 0 (вимкнено, R-32); інакше `min(100, n & 0x7F)` |
| `expand_devices(items) -> list[str]` | `["@1.2.1.1-3"]` → `["@1.2.1.1", "@1.2.1.2", "@1.2.1.3"]`; > 255 пристроїв або `d1 > d2` → `ValueError` |
| `key_of(frame) -> tuple` | ключ кореляції `(cmd, G або адреса)` |

`connection.py`:
- `HelvarConnection(host, port, timeout_s, rate_per_s)` — один `asyncio.open_connection`; читач-корутина
  розбирає потік (`split_stream`), збирає часткові кадри (`partial` до `reply`), відповіді віддає очікуючим запитам за
  `key_of`, push-кадри — підписникам (`add_push_listener(fn)`); запити серіалізуються (`asyncio.Lock`, одна відповідь
  очікується одночасно) з токен-бакетом `rate_per_s`; `request(text, key, timeout)` → `Frame` або `TimeoutError`.
- `ConnectionPool` — `{(host, port): HelvarConnection}` з лічильником джерел; з'єднання спільне для `HN-LP-1…3` (A-03).

### 8.4 Опитування (R-32…R-35)

`poll(signals)` групує сигнали за `query` і виконує запити в порядку `router`, `level`, `scene`, `power`, `faults`/
`faulty`; кожне `Reading.ts` = UTC час отримання відповіді; помилка одного сигналу → `Reading(q='bad', value=None)` для
нього (а не виняток), втрата з'єднання → `PollError` для всієї групи (ядро — бекоф telemetry R-19).

### 8.5 Push (R-36)

При `params.push=true` плагін реєструє слухача на `HelvarConnection`; push `C:13` (рівень групи) і `C:11` (сцена)
перетворює на показання сигналів `level`/`scene` своїх джерел із тим самим `group` і одразу кладе в буфер через
`ctx.emit(Reading)`; push інших команд ігнорується (лічильник `collector_helvarnet_push_ignored_total`).

### 8.6 Health, метрики, логування

- `health()`: `online`, якщо останній запит до свого роутера успішний ≤ 2 найбільших `period_s` сигналів тому і роутер
  є у відповіді C:102; `error` — 3 поспіль `PollError`/`TimeoutError` або роутера немає в C:102 (`error="router @1.2
  not in cluster"`); `offline` — немає TCP-сеансу. `stats`: `queries`, `errors`, `timeouts`, `push`, `latency_ms`
  (EWMA), `devices_faulty`, `version` (фактична `V`).
- Метрики (`ctx.metrics`): `collector_helvarnet_queries_total{source,cmd}`, `…_errors_total{source,code}`,
  `…_push_total{source,cmd}`, `…_push_ignored_total`, `…_latency_seconds` (histogram), `…_faulty_devices{source}`.
- Логи: `collector.plugin.helvarnet.<source>`; кадри — лише на DEBUG; помилки протоколу — WARNING раз на хвилину на
  тип; секретів немає.

### 8.7 Що заборонено в плагіні

- Будь-які команди, крім запитів 102, 104 (діагностика `test-source`), 109, 110, 152, 161, 164, 191 і записів C:11,
  C:13; конфігураційні команди та тести аварійного освітлення (19…24) — `NotSupported`.
- Запис у групу `G:40` (EMERGENCY) або групу, якої немає серед сигналів джерела, — `NotSupported`.
- З'єднання з хостом поза `F3D_ALLOW_HOSTS` (`AllowlistDenied` від ядра).

### 8.8 Фейковий роутер для тестів (`tests/fake_helvar_router.py`)

`FakeHelvarRouter(routers={1: {...}, 2: {...}, 3: {...}}, version=2, push=True, latency_ms=0)` — asyncio TCP-сервер на
вільному порту: зберігає групи `{G: [адреси]}`, рівні пристроїв, сцени, стани C:110, потужність `n·W·level`;
відповідає за документом Helvar (§8.1) на 101, 102, 103, 104, 109, 110, 152, 161, 164, 165, 191; на C:11/C:13 змінює
рівні учасників, відповідає `!V:2,C:13,G:<g>,…=0#` при `A:1` (або мовчить, якщо `ack=False`), шле push усім клієнтам;
режими: `error_code` для конкретного запиту, `drop_after=n` (розірвати з'єднання після n кадрів), `partial=True`
(ділити відповіді 164 на `$`-частини), `version=1` (на `V:2` → `!…=18#`), `delay_s` (таймаути). Склад — з Додатка A.1
(LP-2: G:12 `@1.2.1.1-27` …).

### 8.9 Використання плагіна `bacnet_ip` telemetry (FR-24, A-02, A-03)

- Джерело на пристрій: `BAC-<device>-<code>` (`params` — Додаток C; `network=2`, `rpm=true`, `rpm_max=50`, без
  `read_only`).
- Адреси — Додаток B (telemetry A.1): `{"object": "AI", "instance": 4, "property": "present-value", "mode": "poll",
  "doc": "AI:4 RV-05_FreshAirFilterDp"}`; складені стани — `states[]` (перший збіг); MSV — `map`/`states`.
- Періоди: вимірювання й стани — 30 с, уставки — 300 с; ядро telemetry групує сигнали джерела з однаковим `period_s`
  в один RPM (≤ 50 пар; з `status-flags` — ≤ 25 сигналів на RPM, тож RV-05 з 13 сигналами 30 с — 1 RPM).
- Запис (лише з п'ятьма запобіжниками, R-25): MSV:1 (`text` → значення за зворотним `map` адреси: `"VEL"` → 2;
  telemetry R-23, X-66, X-71), AV:1, AV:2 — `WriteProperty`
  `priority=8` (telemetry R-23); AO:1, AO:2, BV:1 і котельня — без `write_enabled` (constraint M-13).

## 9. Алгоритми й правила

Числа — з макета (`plant/lighting.py`, `plant/ventilation.py`, `dist/odoo_demo.json` 14.10.2026); округлення — Python
`round` (банківське лише для .5 точно — у прикладах не трапляється). Функції `tools/*.py` — чисті (без ORM), тести
викликають їх напряму.

### 9.1 Освітлення

| ID | Правило | Алгоритм / формула | Приклад (вхід → вихід) |
|---|---|---|---|
| R-01 | **Ефективна норма** | `lux(task) = lux_norms.json[task].lux`, якщо є; інакше `plant/lighting.py:NORMS[task]`; у даних — 13 норм (Додаток A.0). `lux_norms.json` перекриває `NORMS` для `storage_racks` (200 → 150) і `battery_charging` (150 → 200) | `storage_racks` → 150; `battery_charging` → 200; `woodworking_machine` → 500 |
| R-02 | **Параметри світильника** | `lumen = passport.get_num('lumen')`, `watt = passport.get_num('watt')` (CB-08); `None` → `DEFAULT_FIX` (`highbay` 24 000 лм / 160 Вт, `highbay_rack` 19 000 / 130); ціле `round` | паспорти демо `highbay`, `highbay_rack` → 20 500 / 126; паспорт без `lumen` → 24 000 / 160 |
| R-03 | **Потрібна кількість** (метод коефіцієнта використання) | `n_required = max(1, ⌈E_н · A / (Φ · UF · MF)⌉)`, `A = zone.area_m2` (м², 0,1), `UF = 0,7`, `MF = 0,8` | LT-CUT: `500 · 609,3 / (20 500 · 0,56) = 304 650 / 11 480 = 26,54` → **27**; LT-FAC: `750 · 1 235,0 / 11 480 = 80,69` → **81** (встановлено 91); LT-EB: 24,59 → **25** (27); LT-SHEETS: `100 · 1 200,6 / 11 480 = 10,46` → **11** (12); зона 1 м², 100 лк → **1** |
| R-04 | **Розрахункова освітленість, потужність, виконання норми** | `e_calc_raw = n · Φ · UF · MF / A`; `e_calc = round(e_calc_raw)`; `p_inst_kw = round(n · W / 1000, 2)`; `design_ok = n ≥ n_required ∧ e_calc_raw ≥ E_н` | LT-CUT: `27 · 11 480 / 609,3 = 508,73` → **509**, 3,40 кВт, `design_ok`; LT-FAC: `91 · 11 480 / 1 235 = 845,89` → **846**, 11,47 кВт; LT-RCV-7: `4 · 11 480 / 144 = 318,9` → **319**; LT-HW: 163,77 → **164**, 0,63 кВт; LT-CUT з `n=26` → 489,9 → `design_ok=False`. Для 32 груп результати = `lighting.groups[*].e_calc`, `area`, `p_inst` макета (Додаток A.1) |
| R-05 | **Живі значення групи й щита** | 1) `level_pct` = `level_signal.last_value` (обмежити 0…100), якщо сигнал «живий» (`status ∈ {ok,warn,alarm}`), `level_source='live'`; інакше `level_design·100`, `'design'`. 2) `e_now = round(e_calc_raw · level_pct / 100)`. 3) `p_now_kw` = `power_signal.last_value` (кВт), якщо живий; інакше `round(n · W · level_pct / 100 / 1000, 2)`. 4) `scene` = `int(scene.last_value)` (живий) інакше 0; `faults` = `int(faults.last_value)` інакше 0; `faulty` = `faulty.last_text` або `""`. 5) `stale = not live(level)`. 6) Щит: якщо сигнал `meter_code` існує й живий → `p_now_kw = last_value`, `p_source='meter'` (A-16); інакше, якщо хоч одна група щита має живу потужність → `round(Σ p_now_kw груп, 1)`, `'dali'`; інакше `round(Σ проєктних p_now, 1)`, `'design'`. 7) `plan_state`: `faults > 0` → `fault`; `deviation ∈ {off_in_work, below_norm}` → `alarm`; `stale` → `nodata`; `level_pct < 1` → `off`; `check_norm ∧ e_now < E_н·(1 − tol)` → `low`; інакше `ok` | LT-SHEETS без сигналу: `level=80`, `e_now = round(114,74 · 0,8) = 92`, `p_now = round(12·126·0,8/1000, 2) = 1,21` (= макет); LT-CUT рівень 60 (живий): `e_now = round(508,73 · 0,6) = 305`; щит LP-1 без даних: 5,6 (`design`); LP-2 з лічильником energy 21,9 → 21,9 (`meter`) |
| R-06 | **DALI-адресація групи** | Формат `dali_devices`: елементи `@c.r.s.d1-d2` або `@c.r.s.d` через `;`. Розклад (генератор, правило емулятора iot_sim §8.10.4): для груп щита в порядку каталогу (`sequence`): якщо `used > 0` і `n > 64 − used` → нова лінія (`line += 1`, `used = 0`); далі `n` пристроїв поспіль `used+1…`, переходячи на наступну лінію при 64; `G` = № групи в каталозі (1…32), `G:40` — EMERGENCY (не група модуля). Склад групи в роботі — з роутера (C:164, R-35); `dali_devices` — фолбек і перевірка | LP-2: LT-CUT `@1.2.1.1-27`, LT-EB `@1.2.1.28-54`, LT-CNC `@1.2.2.1-27`, LT-SORT `@1.2.2.28-39`, LT-FAC `@1.2.3.1-64;@1.2.4.1-27`; LP-3: LT-OUT-1 `@1.3.1.59-62`, LT-OUT-2 `@1.3.2.1-4` (4 > 64 − 62) |

### 9.2 Вентиляція й опалення

| ID | Правило | Алгоритм / формула | Приклад (вхід → вихід) |
|---|---|---|---|
| R-10 | **Номінали, частка витрати, підписи режимів** | 1) `airflow_nom`: `roofvent` — `get_num('airflow_m3h') or 8000`; `ahu` — `get_num('airflow_m3h') or 20000`; `fan` — `(get_num('airflow_m3h') or 6000) · fan_count`; `exfan` — `get_num('airflow_m3h') or 644`. `heat_nom_kw`: `roofvent` — `get_num('heat_kw') or 60.0`, інші — 0. `p_inst_kw`: `roofvent` — `power_kw or 4.0`; `ahu` — `power_kw or 15.0`; `fan` — `(power_kw or 0.6)·fan_count`; `exfan` — `power_kw or 0.18`. `required_m3h` (exfan) — `get_num('required_m3h') or 160`. 2) `k = airflow_m3h / airflow_nom` (0 при `airflow_nom = 0`). 3) `MODE_LABELS = {VE: "Приплив і витяжка", VEL: "Знижена вентиляція", AQ: "Рекуперація", REC: "Рециркуляція", EA: "Витяжка", SA: "Приплив", ST: "Очікування", Off: "Вимкнено"}`; `mode_label`: RV — `MODE_LABELS[mode_code]`; AHU-1 при `VE` — «Приплив під витяжку фарбувальних камер», інакше `MODE_LABELS`; `fan` — працює: «Увімкнено N з N (термостат)» (N = `fan_count`), не працює: «Чекає (термостат)»; `exfan` — працює: «Безперервно під час заряджання, не менше {round(required_m3h)} м³/год», інакше «Зупинено»; без живого режиму — підпис `mode_design` (VE/AQ/REC — як у макеті) | RV: 8 000 / 116,8 / 8,6; AHU-1: 20 000 / 0 / 15,0; EF-ELEC: 14 120 / 0,84; EF-CMP: 7 060 / 0,42; EF-CHG: 644 / 0,178, 158,4; RV-05 `airflow 5 760` → `k = 0,72`; `AQ` → «Рекуперація»; EF-CHG працює → «…не менше 158 м³/год» |
| R-11 | **Стан установки (payload `state`)** | RV/AHU: `state` сигнал `fault`/`frost` → `fault`; `running` → `on`; `stopped` → `standby`, якщо `mode_code == 'ST'`, інакше `off`. `fan`: `running` → `on`, `stopped` → `standby`, `fault` → `fault`. `exfan`: `running` → `on`, `stopped_charging` → `fault`, `stopped` → `standby`. Немає живого стану → значення статики (`on`/`standby` макета), `stale=True` | RV-05 `stopped` + `ST` → `standby`; `stopped` + `Off` → `off`; EF-CMP `stopped` → `standby` (= макет) |
| R-12 | **Живі значення установки** | Для кожного поля: живий сигнал → `last_value` (клапан `%` → частка `/100`); інакше значення статики `ventilation.units[code]` (макет); інакше формула R-13. Виняток: якщо витрата жива, а тепло/клапан/потужність — ні, береться R-13 від живої витрати (свіжіше за статику). Округлення для payload — telemetry R-12 (`|v| < 20` → 2 знаки, інакше 1) | RV-05 без даних: витрата 5 912,6, приплив 19,32, тепло 6,9 (статика); витрата жива 6 000, тепло без сигналу → R-13: 7,2 |
| R-13 | **Формули макета (фолбек)** | `t_out` = живий `ventilation/totals/outdoor_c`, інакше 9,0 (`OUTDOOR_C`); `t_set = balance.t_in_set` (18). RV: `heat = heat_nom · k · (t_set − t_out) / (t_set + 15) · f`, `f = 0,3` для `AQ`, `0,8` для `VE`, `VEL`, `REC`, `EA`, `SA`, `heat = 0` для `ST`/`Off`; `heating_valve = round(min(1, heat / heat_nom), 2)`; `p_now = round(p_inst · k³ + 0,1, 2)`. AHU-1: `heat = airflow · 1,2 / 3600 · (t_supply_design − t_out)`; `p_now = round(p_inst · k³ + 0,1, 2)`; клапан — лише статика (0,46). Вентилятори: `p_now = p_inst` (працює) або 0 | RV-05 `k=0,72`, AQ: `116,8·0,72·9/33·0,3 = 6,88` → **6,9**, клапан **0,06**, `p_now = 8,6·0,373 + 0,1 = ` **3,31**; RV-01 `k=0,68`, VE: `116,8·0,68·9/33·0,8 = 17,33` → **17,3**, клапан 0,15; RV-21 `k=0,45`, REC: **11,5**, `p_now` **0,88**; AHU-1 17 000 м³/год, 21 °C: `17 000·1,2/3600·12 = ` **68,0**; при `t_out = −10`: RV-05 → `116,8·0,72·28/33·0,3 = 21,4` |
| R-14 | **Тепловий баланс при розрахунковій температурі** (`tools.heat.design_balance`) | `Δt = t_in_set − t_out_design`; `S_стін = 2·(L + W)·H`; `S_покр = S_підл = L·W`; `Q_огор = (S_стін·U_стін + S_покр·U_покр + S_підл·U_підл)·Δt / 1000`; `Q_інф = L·W·H·n_інф·c·Δt / 1000`; `Q_RV = Σ airflow_nom(roofvent) · частка_ЗП · c · Δt · (1 − η_рек) / 1000`; `Q_AHU = airflow_nom(ahu) · ahu_design_share · c · (ahu_supply_c − t_out_design) / 1000`; `Q_вн = −internal_gains_kw` (рядок лише якщо > 0); `total_raw = Σ`; `total_kw = round(total_raw)`; `capacity_kw = round(boilers · boiler_kw)`; `reserve = round((capacity + chp_heat_kw) / total_raw − 1, 2)`; `reserve_boilers = round(capacity / total_raw − 1, 2)`; `note` — текст макета з U (кома). Назви рядків: «Тепловтрати через стіни, покрівлю й підлогу»; «Інфільтрація крізь ворота ({n_інф} обміну/год)»; «Дахові установки: {частка·100} % зовнішнього повітря, рекуперація {η·100} %»; «Приплив дільниці фасадів (без рекуперації — витяжка з фарбування)»; «Внутрішні теплонадходження (зменшують навантаження)». `formula` рядка — підстановка чисел, напр. «(3 996·0,35 + 10 800·0,25 + 10 800·0,15)·33/1000» | Макет: `Δt = 33`; `S_стін = 3 996`; `Q_огор = 5 718,6·33/1000 = 188,71` → **189**; `Q_інф = 97 200·0,1·0,34·33/1000 = 109,06` → **109**; `Q_RV = 200 000·0,5·0,34·33·0,22/1000 = 246,84` → **247**; `Q_AHU = 20 000·0,85·0,34·36/1000 = 208,08` → **208**; `total_raw = 752,69` → **753**; `capacity` **990**; `reserve = (990 + 856)/752,69 − 1 = ` **1,45**; `reserve_boilers` = **0,32**. `U_стін = 0,5` → `Q_огор = 208,49`, total **772**. `internal_gains_kw = 100` → рядок −100, total **653** |
| R-15 | **Тепло КГУ зараз** (`tools.heat.chp_heat`) | 1) сигнал `infra/chp/heat_kw` живий → значення, `chp_source='signal'`; 2) інакше сигнал `infra/totals/chp_kw` живий: `load = el / chp_el_kw`; `load < 0,05` → 0; `load ≤ chp_min_load` → `chp_heat_50_kw`; `≤ 0,75` → лінійно від `heat_50` до `heat_75` між 0,5 і 0,75; інакше лінійно від `heat_75` до `heat_kw` між 0,75 і 1,0 (вище 1 — `heat_kw`); `'calc'`; 3) інакше `chp_heat_50_kw`, `'design'` (макет удень — 50 %) | `el = 397,3` → 0,497 → **497**; `500` → 0,625 → `497 + 0,5·179 = ` **586,5**; `700` → 0,875 → `676 + 0,5·180 = ` **766**; `800` → **856**; `0` → **0**; без сигналів → **497** |
| R-16 | **Живий баланс** (`tools.heat.live_balance`) | `need = Σ heat_kw` RV й AHU (R-12/R-13); `chp = R-15`; `boil = max(0, need − chp)`; `boilers_on_calc = 0`, якщо `boil ≤ 0`; `1`, якщо `boil ≤ boiler_stage_share · boiler_kw`; інакше `2` (не більше `boilers`); `boiler_load = round(boil / boiler_kw, 2)`; фактичні котли — `equipment/BOILER/state`: `standby` → 0, `K1` → 1, `K1+K2` → 2, `fault` → 0 (немає сигналу → `boilers_on = boilers_on_calc`, `boiler_state = False`); `available = chp + boilers_on · boiler_kw`; `deficit = round(max(0, need − available), 1)` | Макет: `need = 322`, `chp = 497` → `boil 0`, `calc 0`, `load 0,0`, `deficit 0`; `need 600`, `chp 497`, стан `K1` → `calc 1`, `load 0,21`, `deficit 0`; те саме, стан `fault` → **103**; `need 2 000`, `chp 856`, `K1+K2` → `available 1 846`, **154**; поріг другого котла: `boil 420,75` → 1, `421` → 2 |
| R-17 | **Підсумки `ventilation.totals`** | `units = 29`; `airflow_m3h = round(Σ airflow, −2)`; `heat_kw = round(Σ heat_kw)`; `p_now = round(Σ p_now, 1)`; `p_inst = round(Σ p_inst, 1)`; `outdoor_c` — живий або статика (9,0); `indoor_set_c = t_in_set`; `boilers`, `boiler_kw`; `boilers_on` (фактичні, R-16); `boiler_load`; `design_heat_kw = total_kw`; `chp_heat_kw = round(min(chp, need))`; `chp_heat_now = round(chp)`; `chp_heat_rated = round(chp_heat_kw параметр)`; додатково `heat_need_kw = round(need, 1)`, `boilers_on_calc`, `deficit_kw`, `chp_source` | Статика макета: 173 400 м³/год, 322 кВт, 93,2 / 231,4 кВт, 9,0 / 18,0, 2 × 495, 0 / 0,0, 753, 322, 497, 856 (= `dist/odoo_demo.json` `ventilation.totals`) |

### 9.3 Робочий час, правила відхилень, заявки

| ID | Правило | Алгоритм | Приклад |
|---|---|---|---|
| R-18 | **Робочий час** (`tools.schedule.work_interval_at`) | Календар: `calendar_id` групи/установки → параметр `td.bms.calendar_id` → `company.resource_calendar_id`. `dt` (UTC naive) → aware UTC; `intervals = cal._work_intervals_batch(dt − 12 год, dt + 12 год, compute_leaves=True)[False]`; повернути `(start, stop)` інтервалу з `start ≤ dt < stop` (UTC naive) або `None`. Кеш на прогін крона за `(calendar_id, хвилина)` | «Зміна 1» (Europe/Kyiv): вт 14.10.2026 10:00 Київ (07:00 UTC) → `(04:00, 08:30)` UTC; 11:45 Київ (обід) → `None`; 15:31 → `None`; сб 18.10 10:00 → `None`; день із `resource.calendar.leaves` компанії → `None` |
| R-19 | **Перевірка групи освітлення** (`tools.rules.light_check`) | Вхід: `live(level)`, `level_pct`, `e_now_raw`, `E_н`, `tol = light_norm_tolerance_pct/100`, `interval` (R-18), `mains_lost` (R-21), `off_since`, `low_since`, `delay = light_check_delay_min`, `now`. 1) `not live` → «немає даних»; 2) `interval is None` → «поза робочим часом»; 3) `mains_lost` → «немає мережі (живлення від резерву)»; 4) `start = interval[0]`; `check_off ∧ level_pct < 1 ∧ off_since ∧ now − max(off_since, start) ≥ delay` → «вимкнено в робочий час»; 5) `check_norm ∧ level_pct ≥ 1 ∧ e_now_raw < E_н·(1 − tol) ∧ low_since ∧ now − max(low_since, start) ≥ delay` → «нижче норми»; 6) інакше «норма». Тексти `states` сигналу `…/check` і ключі `deviation`: «норма» `none`, «поза робочим часом» `off_hours`, «вимкнено в робочий час» `off_in_work`, «нижче норми» `below_norm`, «немає даних» `no_data`, «немає мережі (живлення від резерву)» `no_mains`; `alarm_states = ["вимкнено в робочий час", "нижче норми"]` | LT-CUT, вт, рівень 0 з 09:55: о 10:04 «норма», о 10:05 «вимкнено в робочий час»; рівень 60 з 10:00: `305,2 < 475` → о 10:10 «нижче норми»; рівень 95: `483,3 ≥ 475` → «норма»; LT-SHEETS (`check_norm=False`) рівень 50 → «норма»; рівень 0 з учора 18:00 → о 07:09 «норма», о 07:10 «вимкнено…»; 11:40 → «поза робочим часом» |
| R-20 | **Умови «з якого часу»** (`td.bms.check._td_bms_on_ingest(codes)` і крок крона) | Для коду `lighting/groups/<G>/level`: `v = last_value`, `ts = last_ts`; `v < 1` і `off_since` порожнє → `off_since = ts`; `v ≥ 1` → `off_since = False`; `e = e_calc_raw · v / 100`; `v ≥ 1 ∧ e < E_н·(1 − tol)` і `low_since` порожнє → `low_since = ts`; інакше (`v < 1` або `e ≥ …`) → `low_since = False`. Для `ventilation/units/<U>/state` або `/mode`: `not_running = state == 'stopped' ∨ mode ∈ {ST, Off}` (не `fault`/`frost`) → `off_since` як вище; для `/indoor_c`: `< indoor_min_work_c` → `cold_since`, `< indoor_min_off_c` → `cold_off_since`. Крон (п. 4 §6) робить те саме з поточних значень, якщо поле не відповідає поточній умові (час = `now`). Під час придушення (R-21) `off_since = False` | `level` 0 з `ts=09:55:12` → `off_since = 09:55:12`; наступне 0 о 10:00 — без змін; 60 о 10:00 → `off_since=False`, `low_since=10:00` |
| R-21 | **Придушення** (`tools.rules.suppression`) | `mains_lost` = сигнал `infra/ats/src1_ok` (CE-02) живий і `last_value == 0`; `fire_active` = сигнал `fire/totals/system_state` живий і `last_text ∈ {alarm, test}`, або `'td.fire.drill' in env` і `env['td.fire.drill'].sudo()._td_is_active_at(now)` (CF-06). Освітлення: `mains_lost` → «немає мережі…». Установки RV/AHU: `mains_lost` → «немає мережі…»; `fire_active ∧ not_running` → «зупинено пожежною сигналізацією»; після зняття — звичайна перевірка з новою затримкою (бо `off_since` скинуто) | навчання S-07 о 10:00: усі RV `ST` → «зупинено пожежною сигналізацією», заявок 0; відбій 10:05, RV-07 не запустилась → о 10:15 «не працює в робочий час» |
| R-22 | **Правило заявки, журнал, доповнення назв** (`tools.rules.rule_of`, `tools.titles`) | 1) `rule_of(code, text)`: `…/filter_dp_pa` → `filter_supply`; `…/filter_extract_dp_pa` → `filter_extract`; `ventilation/units/EF-CHG/state` → `charging_vent`; інші `ventilation/units/*/state` → `unit_fault`; `ventilation/units/EF-ELEC/indoor_c` → `overheat`; `…/room_pressure_pa` → `pressure`; `lighting/groups/*/faults` → `light_fault`; `lighting/groups/*/check`: «вимкнено в робочий час» → `light_off`, «нижче норми» → `light_low`; `ventilation/units/*/check`: «не працює в робочий час» → `unit_off`, «холодно в зоні» → `cold`; `equipment/BOILER/state` → `boiler_fault`; `ventilation/heat_plant/check` → `heat_deficit`; інше → `other`. 2) **Журнал** (кожен прогін після CT-10): сигнали модуля зі `status='alarm'` без відкритого епізоду → `create` (`started = status_since or now`, `value`, `threshold` — спрацьований поріг (`alarm_high`/`alarm_low`) або значення R-22 п. 3, `unit`, `object_*`, `zone_id`, `request_id = maintenance_request_id`, `name` — назва заявки або текст п. 3); відкриті епізоди сигналів зі `status ≠ alarm` → `state='closed'`, `ended = status_since or now`; відкриті без `request_id` → підставити, коли з'явилась; `value` оновлюється найгіршим (більшим для верхнього порогу, меншим для нижнього). 3) **Доповнення назв** заявок на сигналах `…/check` з `td_bms_enriched=False`: `name`, `td_value`, `td_threshold` за таблицею R-22a; `description += "\n" + рядок деталей`; `td_bms_enriched=True`. Для `light_fault` — лише `description += "Несправні світильники: <faulty>; щит <LP>, DALI-група G:<g>."`. Числа: лк, %, кВт — цілі; °C — 1 знак, кома | див. R-22a |
| R-23 | **Перевірка установки** (`tools.rules.unit_check`, лише `kind ∈ {roofvent, ahu}`) | 1) витрата й стан не живі → «немає даних»; 2) `mains_lost` → «немає мережі (живлення від резерву)»; 3) `fire_active ∧ not_running` → «зупинено пожежною сигналізацією»; 4) `interval is None`: `indoor` живий `< indoor_min_off_c` і `now − cold_off_since ≥ cold_delay` → «холодно в зоні»; інакше «поза робочим часом»; 5) у робочий час: `required_in_work ∧ not_running ∧ now − max(off_since, start) ≥ hvac_check_delay` → «не працює в робочий час»; `indoor < indoor_min_work_c ∧ now − max(cold_since, start) ≥ cold_delay` → «холодно в зоні»; інакше «норма». `VEL` у робочий час — не відхилення. Тексти/ключі: «норма» `none`, «поза робочим часом» `off_hours`, «не працює в робочий час» `not_running`, «холодно в зоні» `cold`, «немає даних» `no_data`, «зупинено пожежною сигналізацією» `fire`, «немає мережі (живлення від резерву)» `no_mains`; `alarm_states = ["не працює в робочий час", "холодно в зоні"]`. Пороги сигналів (CT-05, у даних): фільтр припливу `alarm_high=250`, `hysteresis=5`; витяжки `350`/`10`; `state` `alarm_states=["fault","frost"]`; EF-CHG `["stopped_charging"]`; EF-ELEC `indoor_c` `alarm_high=35`, `hysteresis=1`, `min_duration_s=600`; AHU-1 `room_pressure_pa` `alarm_high=0`, `hysteresis=1`, `min_duration_s=300` | RV-05 вт 10:00, `ST` з 09:50 → о 10:00 «не працює в робочий час»; 23:00, `ST`, 15 °C → «поза робочим часом»; 23:00, 9 °C з 22:20 → о 22:50 «холодно в зоні»; 10:00, 15,5 °C з 09:30 → «холодно в зоні»; RV-05 `VEL` о 10:00 → «норма»; `fault` → заявка лише за `state` (CT-05), перевірка — «норма» |
| R-24 | **Перевірка котельні / дефіцит тепла** | `need`, `deficit` — R-16; немає живих `heat_kw` у ≥ 50 % RV/AHU або стану котельні → «немає даних»; `deficit > heat_deficit_kw` → `deficit_since` (якщо порожнє — `now`); `deficit ≤ поріг` → `deficit_since = False`; `deficit_since ∧ now − deficit_since ≥ heat_deficit_delay` → «дефіцит тепла»; інакше «норма». Сигнал `ventilation/heat_plant/check` (обладнання `BOILER`), `states = ["норма", "дефіцит тепла", "немає даних"]`, `alarm_states = ["дефіцит тепла"]`. Аварія котельні — окремо за `equipment/BOILER/state` (`alarm_states=["fault"]`, CT-05) | `deficit 103` з 10:00 → о 10:30 «дефіцит тепла»; `deficit 15` → «норма» |

**R-22a. Тексти й значення заявок відхилень** (`tools.titles`; `{zone}` = `zone_id.name`):

| Правило | `name` | `td_value` / `td_threshold` | Рядок `description` | Приклад |
|---|---|---|---|---|
| `light_off` | «Освітлення {code} ({zone}): вимкнено в робочий час — рівень {level} % при нормі {e_norm} лк» | `e_now` / `E_н` | «Група DALI G:{g}, щит {panel}; вимкнено з {off_since Київ}.» | «Освітлення LT-CUT (Розкрій): вимкнено в робочий час — рівень 0 % при нормі 500 лк» |
| `light_low` | «Освітлення {code} ({zone}): ≈ {e_now} лк при нормі {e_norm} лк (рівень {level} %)» | `e_now` / `E_н` | «Розрахунок: {e_calc} лк при 100 %, допуск {tol} %; з {low_since Київ}.» | «Освітлення LT-CUT (Розкрій): ≈ 305 лк при нормі 500 лк (рівень 60 %)» |
| `unit_off` | «Установка {code} ({zone}): не працює в робочий час — режим «{mode_label}»» | `airflow_m3h` / 0 | «Стан {state}; з {off_since Київ}.» | «Установка RV-05 (Склад плит): не працює в робочий час — режим «Очікування»» |
| `cold` | «Установка {code} ({zone}): у зоні {indoor} °C при нормі від {t_min} °C» | `indoor_c` / `t_min` | «Уставка {setpoint_day_c} °C; з {cold_since Київ}.» | «Установка RV-05 (Склад плит): у зоні 15,5 °C при нормі від 16,0 °C» |
| `heat_deficit` | «Котельня: дефіцит тепла {deficit} кВт (потреба {need} кВт, джерела {available} кВт)» | `deficit` / `heat_deficit_kw` | «КГУ {chp} кВт ({chp_source}), котлів у роботі {boilers_on} з {boilers}, стан «{boiler_state}».» | «Котельня: дефіцит тепла 103 кВт (потреба 600 кВт, джерела 497 кВт)» |
| інші (пороги CT-05) | назва від telemetry за `alarm_title` (Додаток B) | telemetry | — | «Заміна фільтрів: перепад тиску 285 Па при нормі до 250»; «Аварія світильників LT-CUT: несправних 1 шт. при нормі 0» |

### 9.4 Керування й дані

| ID | Правило | Алгоритм | Приклад |
|---|---|---|---|
| R-25 | **Команди з майстрів** (FR-18, A-09) | 1) `_td_bms_check_operator()`; 2) параметр `td.bms.write_enabled` → інакше `UserError("Керування вимкнено: модуль «Будівля» (td.bms.write_enabled).")`; 3) `td.telemetry.write_enabled` → інакше `UserError("Керування вимкнено: телеметрія (td.telemetry.write_enabled).")`; 4) для кожної групи/установки: сигнал (`level_signal_id` / `scene_signal_id` / `mode_signal_id` / `sp_day_signal_id` / `sp_night_signal_id`) має `write_enabled` і `source_id.write_enabled` — інакше список у `UserError("Запис вимкнено на: LT-CUT (джерело HN-LP-2), …")`; 5) валідація: рівень 0…100, сцена — запис M-04, режим — 8 кодів, уставка 5,0…30,0; 6) `cmd = env['td.command'].with_user(SUPERUSER_ID).create({'signal_id', 'value', 'text', 'expires_at': now + expires_min, 'origin': 'bms', 'requested_by': env.uid, 'note': note})`: рівень → `value=level_pct`, `text="fade=<fade_s>"`; сцена → `value=scene.number`, `text="fade=<fade_s>"`; режим → `value=False`, `text=<код>`; уставка → `value=value_c`, `text=False`; 7) чаттер об'єкта «Надіслано команду: <дія> (<користувач>), команда #<id>»; 8) повернути `act_window` `td.command` (`domain=[('id','in',ids)]`) | оператор, усе дозволено: LT-MAINT, сцена 3 → команда `value=3`, `text="fade=2.0"`, `requested_by=оператор`; без `write_enabled` модуля → `UserError` п. 2; RV-05 режим `VEL` → `text="VEL"` |
| R-29 | **Установка даних** | §5.3; сигнали з CSV — правило оновлення `new=0` (лише прив'язка) і `new=1` (визначення без `last_*`); посилання моделей на сигнали за `(object, role)` CSV | — |
| R-30 | **Прапори запису** (A-21) | `write_enabled=True` → `td.source` `HN-LP-1…3`, `BAC-101…125`, `BAC-130-AHU-1`: `write_enabled=True`; 142 сигнали з `writable=1` (CSV): `write_enabled=True`; чаттер джерел; `False` → те саме `False` для всіх джерел/сигналів модуля; відкриті `td.command` модуля в `queued` → `cancelled` | `True` → 29 джерел, 142 сигнали; `False` → 0 і 0 |

### 9.5 Переглядач і огляд

| ID | Правило | Алгоритм | Приклад |
|---|---|---|---|
| R-26 | **Розділ `lighting`** (`tools.payload.build_lighting(env, ctx, static)`) | `groups = {}`: для активних груп за `sequence`: `rec = dict(static.get('groups', {}).get(code, {}))`; `rec.update({zone: zone_code, zone_name, task: norm.key, task_name: norm.name, kind: fixture_kind, panel: panel.code, n: n_fixtures, lumen, watt, area: round(area_m2), e_norm, e_calc, level: round(level_pct/100, 3), e_now, p_inst: p_inst_kw, p_now: round(p_now_kw, 2), control: label(control_mode)})` + `dali_group`, `faults`, `faulty`, `scene`, `deviation`, `deviation_text`, `stale`, `level_source`; групи статики без запису ORM — як є. `panels`: `{code: {name, groups: [коди за sequence], n, p_inst: round(Σ, 1), p_now: round(p_now_kw, 1), state, p_source}}`. `uf`/`mf` — параметри (0,7 / 0,8); `norms_ref = {key: ref_en}` для активних норм. Ключі верхнього рівня — `groups`, `panels`, `uf`, `mf`, `norms_ref` (A.13) | без живих даних: `groups["LT-CUT"]` = `{"zone": "Z-CUT", "zone_name": "Розкрій", "task": "woodworking_machine", "task_name": "верстатна обробка деревини", "kind": "highbay", "panel": "LP-2", "n": 27, "lumen": 20500, "watt": 126, "area": 609, "e_norm": 500, "e_calc": 509, "level": 1.0, "e_now": 509, "p_inst": 3.4, "p_now": 3.4, "control": "DALI: зміна, 100 %", …}`; `panels["LP-1"]` = `{"n": 50, "p_inst": 6.3, "p_now": 5.6, …}` |
| R-27 | **Розділ `ventilation`** (`build_ventilation`) | `units`: для активних установок: база — статика `units[code]`; оновлення: `name`, `kind` (`roofvent`/`ahu`/`fan`/`exfan`), `zone` (код), `mode` (`mode_label`), `airflow_m3h`, `airflow_nom` (ціле), `supply_c`, `indoor_c`, `heating_valve`, `heat_kw` (лише RV/AHU), `p_inst`, `p_now`, `filter_dp_pa` (RV/AHU), `state` (R-11), `maintenance_request` (назва найстарішої відкритої заявки на сигналах установки, інакше ключ видаляється) і `maintenance_request_id` (id тієї ж заявки: назви заявок не унікальні, клієнт шукає заявку за id — viewer R-22; у delta, `ctx['delta']`, обидва ключі при відсутності заявки пишуться як `null`), `note` + `mode_code`, `filter_extract_dp_pa`, `setpoint_day_c`, `setpoint_night_c`, `deviation`, `deviation_text`, `stale`; значення — R-12 з округленням telemetry R-12. `totals` — R-17. `heat_balance` = `{t_out: t_out_design, items: [{name, kw: kw_round}], total: total_kw, capacity: capacity_kw, chp_kw: round(chp_heat_kw), reserve, note}`. `boiler` = `{state, supply_c, return_c, silo_fill (частка), heat_kw}` | без живих даних: `units`, `totals`, `heat_balance` = `dist/odoo_demo.json.ventilation` (крім ключів `maintenance_request` і `maintenance_request_id`, що беруться з живих заявок: «MR/…» заявки id 6 для RV-05) |
| R-28 | **Огляд будівлі** (`td.bms.overview.get_overview_data`) | Відповідь: `{"ts": ISO UTC "Z", "work_time": bool (R-18 для календаря компанії), "plan": {"width": plant_length_m, "depth": plant_width_m}, "zones": [{"id", "code", "name", "polygon", "group": код|null, "state": plan_state|null}] (зони `zone_type != 'outdoor'`), "groups": [{"id", "code", "zone", "e_now", "e_norm", "level", "faults", "state", "deviation_text"}], "panels": [{"id", "code", "x", "y", "state", "p_now"}], "units": [{"id", "code", "kind", "x", "y", "zone", "mode_label", "state", "plan_state", "airflow", "filter_dp", "deviation_text"}], "kpi": {"groups_ok", "groups_total", "lighting_kw", "units_on", "units_total", "airflow", "heat_need", "chp_heat", "boilers_on", "deficit", "open_deviations", "open_requests"}, "heat": {<R-16 поля>, "design": {"total", "capacity", "chp", "reserve", "lines": [{"name", "kw"}]}}, "deviations": [≤ 50 відкритих: {"id", "started" (Київ "YYYY-MM-DD HH:MM"), "object_code", "rule", "name", "request"}]}`. `plan_state` установки: `alarm_count > 0` або `deviation ∈ {not_running, cold}` → `alarm`; `stale` → `nodata`; `state ∈ {on}` → `on`; інакше `standby`. `groups_ok` — групи з `plan_state ∈ {ok}` | на демо без живих даних: 34 зони, 32 групи (`groups_ok` 32: 22 групи «зміни» з рівнем 100 % і 10 груп «присутності» без перевірки норми), 3 щити, 29 установок, `heat_need 322`, `chp_heat 497`, `boilers_on 0`, `deficit 0`, `open_deviations 1` і `open_requests 1` (RV-05, заявка id 6) |

### 9.6 Плагін `helvarnet`

| ID | Правило | Алгоритм | Приклад |
|---|---|---|---|
| R-31 | **Сеанс, кадри, кореляція, частота** | Один TCP-сеанс на `host:port` (пул); `connect`: `ctx.allowlist(host)`, `open_connection` з таймаутом `timeout_s`, запит `C:191` (версія HelvarNet) — відповідь фіксує `version` (`=2` → 2; помилка 18 при `V:2` → `version=1`, повтор); потік ділиться на кадри `#`/`$` (≤ 1 500 байт); `partial` накопичується до `reply` з тим самим ключем; кореляція — `key_of` = `(C, G | адреса)` + FIFO; один запит у польоті (`Lock`); токен-бакет `rate_per_s` (місткість 1 с); таймаут → `TimeoutError` → сигнал `q='bad'`; 3 таймаути поспіль або закритий сокет → `PollError`, сеанс закривається, наступний `poll` перепідключається (бекоф ядра) | `>V:2,C:152,@1.2.1.5#` → `?V:2,C:152,@1.2.1.5=75#` → 75; `!V:2,C:152,@1.2.1.99=11#` → `HelvarError(11, "Device does not exist")` |
| R-32 | **Рівень групи** (`query='level'`) | склад групи (R-35) без пристроїв, що в останньому опитуванні несправностей мали біт Missing або помилку 11; вибірка `sample` позицій `[0, len//2, len−1]` (унікальні, по порядку); для кожного `C:152` → `decode_level`; помилки 11/12 — пропуск; `value = statistics.median_low(рівні)`; жодної відповіді → `q='bad'` | LT-CUT `@1.2.1.1…27`: пристрої 1, 14, 27 → 60, 60, 60 → **60**; `2147483649` (`0x80000001`) → **0**; 1 → 100, 14 → 0x8000…, 27 → 100 → `median_low([0,100,100]) = 100` |
| R-33 | **Потужність і сцена** | `query='power'`: `>V:{v},C:161,G:{g}#` → Вт · `address.scale` (0,001) → кВт; відповідь 0 → `0.0` (документ Helvar: «невідомо» теж 0). `query='scene'`: `>V:{v},C:109,G:{g}#` → ціле 1…16 (0, якщо не викликалась) | G:12 → `=3402` → **3,402** кВт; `C:109` → `=3` → **3** |
| R-34 | **Несправності, адреси, стан щита** | `query ∈ {faults, faulty}` (один обхід на групу за період, результат кешується для обох сигналів): для кожного пристрою складу `C:110` → `int(answer) & mask ≠ 0` → несправний; помилка 11 → несправний (відсутній); `faults` = кількість; `faulty` = адреси без `@` через `,`, обрізані до 64 символів із суфіксом `+N` (`"1.2.1.5,1.2.1.9"`; порожньо → `"—"`). `query='router'`: `>V:{v},C:102,@{cluster}#` → список роутерів; свого немає → `text="offline"`, `q='bad'`; є → `"fault"`, якщо в будь-якій групі джерела `faults > 0` (останній обхід), інакше `"ok"`. Якщо задано `address.devices`, пристрої з нього, яких немає у складі з роутера (C:164), теж рахуються несправними (відсутні) | LT-CUT, `@1.2.1.5` стан `2` (LampFailure) → `faults=1`, `faulty="1.2.1.5"`; LP-2 → `fault`; 12 несправних → `"1.2.1.1,…,1.2.1.10+2"` |
| R-35 | **Склад групи** | `>V:{v},C:164,G:{g}#` → адреси через `,` (частини `$` об'єднуються); кеш на `membership_ttl_s`; помилка/порожньо → `expand_devices(address.devices)`; немає і того → сигнали групи `q='bad'`, WARNING «склад групи G:<g> невідомий» | G:16 → 91 адреса `@1.2.3.1…64, @1.2.4.1…27` (у двох частинах `$`) |
| R-36 | **Push** | слухач розбирає `>V:x,C:13,G:g,L:l…#` → `Reading(code сигналу level з group=g, value=l (decode_level не застосовується), ts=now)`; `C:11,G:g,…,S:s` → `scene=s`; `ctx.emit`; лічильник | push `>V:2,C:13,G:12,L:0,F:100#` → `lighting/groups/LT-CUT/level = 0` за ≤ 1 с |
| R-37 | **Запис** (`write(signal, value, text)`) | дозволено лише `query ∈ {level, scene}`, `group ≠ 40`; `fade_s` = `text` `fade=<x>` або `address.fade_s`; `level`: `value` 0…100 → `build_command(C:13, L=round(value), F=round(fade·100), A:1)`; `scene`: `value` 1…16 → `C:11, B=block, S=round(value)`; надіслати; очікувати до `timeout_s` кадр `error` з `=0` (успіх), `=n` (`WriteError("HelvarNet error n: <текст>")`) або push тієї ж команди; нічого не отримано → через `fade_s + 1` с перевірка: `level` — `C:152` на першому пристрої групи (±2 %), `scene` — `C:109` == `S`; збіг → `"verified"`, інакше `WriteError("no ack, level now X")`. Результат: `"C13 G12 L60 F200 ack"` / `"… verified"` | LT-MAINT G:19 рівень 50 → `>V:2,C:13,G:19,L:50,F:200,A:1#`, відповідь `!V:2,C:13,G:19,L:50,F:200,A:1=0#` → `"C13 G19 L50 F200 ack"`; G:40 → `NotSupported` |

## 10. Стани й переходи

### 10.1 Стан-сигнал перевірки групи (`lighting/groups/<G>/check`, R-19)

```
немає даних ◄──(рівень не живий)── будь-який
поза робочим часом ──(почався робочий інтервал)──► норма
норма ──(рівень < 1 % ≥ delay)──► вимкнено в робочий час ──(рівень ≥ 1 %)──► норма / нижче норми
норма ──(E_now < E_н·(1−tol) ≥ delay, check_norm)──► нижче норми ──(E_now ≥ …)──► норма
будь-який робочий ──(src1_ok = 0)──► немає мережі ──(мережа є)──► норма (затримка заново)
будь-який ──(кінець робочого інтервалу)──► поза робочим часом
```

Побічні ефекти: запис показання (CT-10) при зміні тексту і кожні `check_heartbeat_min`; перехід у
`alarm_states` → telemetry R-05 (заявка, якщо немає відкритої і минув cooldown) → R-22 (доповнення, журнал);
вихід з `alarm_states` → епізод журналу `closed`; заявка лишається до закриття механіком; шина CH-06.

### 10.2 Стан-сигнал перевірки установки (`ventilation/units/<U>/check`, R-23) і котельні (R-24)

```
немає даних | поза робочим часом | норма | не працює в робочий час | холодно в зоні |
зупинено пожежною сигналізацією | немає мережі
```

Переходи аналогічні 10.1: «не працює…» і «холодно…» — після затримок; «зупинено пожежною…»/«немає мережі» мають
пріоритет і скидають `off_since`. Котельня: `норма ⇄ дефіцит тепла` (після `heat_deficit_delay`), `немає даних`.

### 10.3 Епізод журналу (`td.bms.deviation.state`)

`open` (сигнал модуля перейшов у `status='alarm'`) → `closed` (сигнал вийшов з `alarm`: `ok`, `warn`, `stale`,
`unknown`). `stale` закриває епізод з `note` «закрито: немає даних». Повторна тривога → новий епізод. Видалення —
лише адміністратор.

### 10.4 Стан щита (`td.bms.light.panel.state`)

`unknown` (немає сигналу) → `ok` / `fault` (плагін R-34) → `offline` (джерело `offline/error/disabled` або сигнал
`stale`) → назад за першим живим показанням.

### 10.5 Стан установки (`state`, R-11) і котельні

`on ⇄ standby ⇄ off`, будь-який → `fault` (стан `fault`/`frost`, EF-CHG `stopped_charging`) → за станом сигналу.
Котельня (iot_sim §10): `standby(1) ⇄ K1(2) ⇄ K1+K2(3)`, будь-який → `fault(4)` → `standby`.

### 10.6 Команда (`td.command.state`, telemetry §10.4)

`queued` (майстер R-25) → `sent` → `done`/`failed` (плагін R-37 / `bacnet_ip`) | `expired` | `cancelled` (R-30 при
вимкненні `write_enabled`).

### 10.7 Звіт установки (`td.bms.install_report.state`)

`{}` → `done` | `partial` (немає обладнання/сигналів); `partial` → `done` після появи обладнання й
`f3d_bms_reinstall_data`.

## 11. Обробка помилок

1. **HelvarNet недоступний** (роутер вимкнено, порт закрито, мережа): плагін — `ConnectError`/`PollError`, бекоф
   telemetry R-19; джерело `error`/`offline` (telemetry R-25) → сигнали `stale` (R-07 telemetry, `stale_after = max(3·60,
   60) = 180 с` для рівня); перевірки груп → «немає даних», щит → `offline`; заявок немає (Q-13); огляд і переглядач —
   `stale`. Відновлення автоматичне: перше показання → R-04 telemetry, перевірка → «норма» (затримки рахуються заново).
2. **Роутер відповідає помилкою** (`!…=n#`): 1/9/10 (група/кластер/роутер не існує) → сигнал `q='bad'`, WARNING раз на
   годину; 11 (пристрою немає) — для рівня пропуск пристрою, для несправностей — пристрій несправний; 12 (властивості
   немає) — пропуск; 18 — пониження версії (R-31); інші — `q='bad'`.
3. **Push без опитування / втрачений push** — опитування кожні `period_s` (60 с) відновлює рівень; дубль push і
   опитування з тим самим значенням → R-03 telemetry зберігає не частіше `store_period_s`.
4. **BACnet: пристрій не відповідає** (Who-Is/RPM таймаут) → джерело `error`, сигнали `stale` через `max(3·30, 60) =
   90 с`; `reliability`/`status-flags` `fault` → `q='uncertain'`/`bad` (telemetry R-23) — значення не оновлюють
   `last_value`; перевірки установки → «немає даних». **COV у v1 не використовується** (A-02): втрата підписки
   неможлива. Зміна `mode` на `cov` в адресі допустима без коду: telemetry рахує `stale_after` для COV від інтервалу
   контрольного читання `max(period_s·10, 300)` с (telemetry R-07, X-06), хибних `stale` у спокої немає.
5. **Сигналу немає** (energy/fire_safety не встановлені, сигнал видалено) — поле `*_signal_id` порожнє → фолбек R-05,
   R-12, R-15, придушення R-21 вимкнене; WARNING лише в хуку.
6. **Календар без робочих інтервалів / не заданий** — `work_interval_at` → `None` → «поза робочим часом» (заявок «у
   робочий час» немає); у звіті хука `calendar_missing=True`, якщо в компанії немає календаря.
7. **Часові пояси** — БД UTC naive; R-18 перетворює в aware UTC, календар — у своєму `tz` (Europe/Kyiv); тексти
   заявок і журналу — Київ (`pytz`/`zoneinfo`, як telemetry R-14); плагін — `ts` UTC tz-aware.
8. **Виняток у крону** — транзакція відкочується, `BMS-DERIVED.state='error'`, `last_error`; наступний прогін через
   1 хв. Виняток у `_td_ingest`-перевизначенні — лог, push telemetry не відкочується (savepoint).
9. **Дублікати** — стан-сигнал пишеться лише при зміні тексту/heartbeat; `(signal_id, ts)` унікальні (telemetry); епізод
   журналу — один відкритий на сигнал (перевірка перед `create`); доповнення назви — один раз (`td_bms_enriched`).
10. **Заявку закрито, а відхилення триває** — telemetry R-06 (нова не раніше `realarm_cooldown_s`); епізод журналу
    лишається `open` з `request_id` закритої заявки, при новій заявці — `request_id` оновлюється.
11. **Команда не виконана** (`failed`, `expired`) — статус і текст помилки в `td.command` (telemetry); чаттер
    групи/установки отримує «Команда #<id>: <стан> — <помилка>» (крон R-22 при наступному прогоні для команд з
    `origin='bms'` і зміненим станом).
12. **Невідповідність кількості пристроїв DALI** (`dali_devices` ≠ `n_fixtures`) — `ValidationError` у формі; з роутера
    (C:164) інша кількість → WARNING у колекторі (`membership mismatch G:<g>: router 26, expected 27`) і `faults`
    рахує відсутні з `dali_devices` як несправні.
13. **Зона без контуру** (`area_m2 = 0`) — `ValidationError` на групі (M-03); дані макета завжди мають контур (base AC-15).

## 12. Acceptance Criteria

Формат: Given / When / Then; тип перевірки: **UT**, **PT**, **TC**, **MAN**. «Демо» — копія бази `odoo` з установленими
`td_factory3d`, `td_telemetry`, `td_bms`; «чиста» — база з `--without-demo=all` і тими самими модулями.

| ID | FR / R | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01, R-01 | Given установку; Then 13 `td.bms.light.norm` з `lux`: `woodworking_machine` 500, `woodworking_bench` 300, `spraying` 750, `sanding` 750, `quality_control` 1000, `storage_racks` **150**, `storage_floor` 100, `packing_dispatch` 300, `loading_ramps` 150, `switchgear_room` 200, `compressor_room` 200, `battery_charging` **200**, `corridors_traffic` 150; `ref_en` `storage_racks` = «EN 12464-1:2021, табл. 13, реф. 13.2 (ред. 2011 — 5.5.2)»; `ref_dbn` непорожній. When норма з `lux=0` / дубль `key` → `IntegrityError`; `key='Woodworking'` → `ValidationError` | UT |
| AC-02 | FR-03, FR-04, R-03, R-04 | Given установку (зони base з даних); Then 32 групи; для кожної рядка Додатка A.1: `zone_code`, `norm_id.key`, `fixture_kind`, `panel_id.code`, `n_fixtures`, `round(area_m2)`, `e_norm`, `n_required`, `e_calc`, `p_inst_kw` (до 0,01), `level_design`, `control_mode`, `dali_group`, `dali_devices` збігаються; `design_ok=True` для всіх 32; Σ `n_fixtures` = 320, Σ `p_inst_kw` = 40,32 | UT |
| AC-03 | FR-04, R-03, R-04 | Given зона 100 м², норма 300 лк, Φ 20 500, UF 0,7, MF 0,8; When `n_fixtures=3`; Then `n_required = ⌈300·100/11 480⌉ = 3`, `e_calc = round(3·11 480/100) = 344`, `design_ok=True`, `p_inst_kw=0.38`. When `n_fixtures=2` → `e_calc=230`, `design_ok=False`. When зона 1 м², 100 лк → `n_required=1`. When зона без контуру → `ValidationError` | UT |
| AC-04 | FR-03, R-02 | Given паспорт без `lumen`/`watt`; When група `fixture_kind='highbay'` → `lumen=24000`, `watt=160`; `highbay_rack` → 19 000 / 130; With паспорт `td_factory3d.passport_highbay` → 20 500 / 126; ручна зміна `lumen` (менеджер) зберігається, `e_calc` перераховано | UT |
| AC-05 | FR-03, R-06 | Given дані; Then `dali_devices` 32 груп = Додаток A.1 (LT-FAC `@1.2.3.1-64;@1.2.4.1-27`, LT-OUT-2 `@1.3.2.1-4`); `tools.lighting.pack_dali([(code, n) …])` для LP-1/2/3 повертає ті самі рядки; When `dali_devices='@1.2.1.1-26'` при `n_fixtures=27` → `ValidationError` «Пристроїв DALI 26, а світильників 27.»; `@1.3.1.1-27` на LT-CUT (щит LP-2) → «Адреса @1.3.1.1 не належить щиту LP-2.»; `'@1.2.1.1-27#'` → `ValidationError` | UT |
| AC-06 | FR-03 | When друга група з `dali_group=12` → `IntegrityError`; `code='lt-cut'` → `ValidationError`; `level_design=1.2` / `uf=0` → `IntegrityError` (CHECK) | UT |
| AC-07 | FR-05, R-05 | Given LT-CUT, сигнали без показань; Then `level_pct=100`, `level_source='design'`, `e_now=509`, `p_now_kw=3.4`, `stale=True`, `scene=0`, `faults=0`. When `_td_ingest` `level=60`, `p_now=2.04`, `scene=3`, `faults=1`, `faulty` текст `1.2.1.5` (ts=now) → `level_pct=60`, `'live'`, `e_now=305`, `p_now_kw=2.04`, `scene=3`, `faults=1`, `faulty='1.2.1.5'`, `stale=False`, `plan_state='fault'`. LT-SHEETS без даних → `e_now=92`, `p_now_kw=1.21` | UT |
| AC-08 | FR-02, R-05 п. 6, A-16 | Given щити без живих даних; Then LP-1 `p_now_kw=5.6`, `p_source='design'`, `n_fixtures=50`, `p_inst_kw=6.3`; LP-2 23,2 / 184 / 23,2; LP-3 9,5 / 86 / 10,8. When жива потужність LT-CUT 2,0 → LP-2 `p_source='dali'`, `p_now_kw = round(2.0 + 3.4 + 3.4 + 1.51 + 11.47, 1) = 21.8`. When сигнал `energy/consumers/LP-2/p_now` (створений тестом, `module='energy'`) живий 22,7 → `22.7`, `'meter'` | UT |
| AC-09 | FR-02 | Given `lighting/panels/LP-2/state` `fault` (живий) → `state='fault'`; джерело `HN-LP-2` `state='error'` → `offline`; сигнал без показань → `unknown` | UT |
| AC-10 | R-05 п. 7 | Таблиця: (faults 1) → `fault`; (check «вимкнено…») → `alarm`; (рівень не живий) → `nodata`; (рівень 0, живий) → `off`; (LT-CUT 60 %, `check_norm`) → `low`; (LT-SHEETS 50 %, `check_norm=False`) → `ok`; (LT-CUT 100 %) → `ok` | UT |
| AC-11 | CH-03 | Given LT-CUT `p_now=3.4` живий; Then `_td_bms_light_power()['LT-CUT'] == {'zone': 'Z-CUT', 'panel': 'LP-2', 'p_now_kw': 3.4, 'p_inst_kw': 3.4, 'level_pct': 100.0}` (рівень живий 100). Given 3 агрегати `td.reading.hour` сигналу потужності LT-CUT з `v_avg` 3,4 / 3,4 / 1,7 у вікні; When `_td_bms_kwh(d0, d1)`; Then `{'LT-CUT': 8.5, …інші 0.0}` | UT |
| AC-12 | V-07 | When `search([('deviation','in',['off_in_work','below_norm'])])` при LT-CUT check «нижче норми», LT-EB «норма»; Then лише LT-CUT; `('deviation','=','none')` → без LT-CUT | UT |
| AC-13 | FR-10, R-14 | Given установку; Then баланс компанії: 4 рядки `kw_round` 189 / 109 / 247 / 208, назви як макет (`Інфільтрація крізь ворота (0,1 обміну/год)`, `Дахові установки: 50 % зовнішнього повітря, рекуперація 78 %`), `total_kw=753`, `total_raw` ≈ 752,69 (±0,01), `capacity_kw=990`, `chp_heat_kw=856`, `reserve=1.45`, `reserve_boilers=0.32`, `note` = «Оцінка, не проєкт: U стін 0,35, покрівлі 0,25, підлоги 0,15 Вт/(м²·К); внутрішні теплонадходження від верстатів (сотні кВт у зміну) не враховано — це запас.» | UT |
| AC-14 | FR-10, R-14 | When `u_wall=0.5` (менеджер) → перерахунок автоматично: огородження 208, `total_kw=772`; `internal_gains_kw=100` → 5-й рядок −100, `total_kw=672` (при `u_wall=0.5`); `action_reset_macro()` → 753, 4 рядки; користувач без менеджера `write` → `AccessError` | UT |
| AC-15 | R-15 | `tools.heat.chp_heat(el, params)` для `el` ∈ {None (немає сигналу), 0, 397.3, 500, 700, 800, 900} → {(497, 'design'), (0, 'calc'), (497, 'calc'), (586.5, 'calc'), (766, 'calc'), (856, 'calc'), (856, 'calc')}; з сигналом `infra/chp/heat_kw` 512 → (512, 'signal') | UT |
| AC-16 | R-16 | `live_balance`: (need 322, chp 497, стан немає) → `boil 0`, `calc 0`, `boilers_on 0`, `load 0.0`, `deficit 0`; (600, 497, `K1`) → `calc 1`, `boilers_on 1`, `load 0.21`, `deficit 0`; (600, 497, `fault`) → `boilers_on 0`, `deficit 103.0`; (2000, 856, `K1+K2`) → `deficit 154.0`; (917.75, 497, —) → `boil 420.75`, `calc 1`; (918, 497) → `calc 2` | UT |
| AC-17 | R-17, R-27 | Given дані без живих показань і статика = `tests/data/static_bms.json`; When `build_ventilation`; Then `totals` == `{"units": 29, "airflow_m3h": 173400.0, "heat_kw": 322, "p_now": 93.2, "p_inst": 231.4, "outdoor_c": 9.0, "indoor_set_c": 18.0, "boilers": 2, "boiler_kw": 495, "boilers_on": 0, "boiler_load": 0.0, "design_heat_kw": 753, "chp_heat_kw": 322, "chp_heat_now": 497, "chp_heat_rated": 856}` + додаткові ключі CH-02 | UT |
| AC-18 | FR-10 | `heat_recovery=1.0` / `t_in_set=-20` / `boiler_stage_share=0` / `chp_heat_50_kw=900` (> 75 %) → `ValidationError`; другий баланс тієї ж компанії → `IntegrityError` | UT |
| AC-19 | FR-07, R-10 | Given установку; Then RV-01…25: `airflow_nom=8000`, `heat_nom_kw=116.8`, `p_inst_kw=8.6`; AHU-1: 20 000 / 0 / 15,0, `t_supply_design=21.0`; EF-ELEC: `fan_count=2`, 14 120 / 0,84; EF-CMP 7 060 / 0,42; EF-CHG 644 / 0,178, `required_m3h=158.4`; `mode_design` і `required_in_work` — Додаток A.3; координати RV-05 (21,5; 33,5), AHU-1 (66,0; 56,5) | UT |
| AC-20 | R-10, R-11 | Таблиця `mode_label`/`state`: RV (`running`, `AQ`) → «Рекуперація», `on`; (`stopped`, `ST`) → «Очікування», `standby`; (`stopped`, `Off`) → «Вимкнено», `off`; (`frost`, `VE`) → `fault`; AHU-1 (`running`, `VE`) → «Приплив під витяжку фарбувальних камер»; EF-ELEC `running` → «Увімкнено 2 з 2 (термостат)», `on`; EF-CMP `stopped` → «Чекає (термостат)», `standby`; EF-CHG `running` → «Безперервно під час заряджання, не менше 158 м³/год»; `stopped_charging` → `fault` | UT |
| AC-21 | R-13 | `tools.hvac.fallback_heat`: RV `k=0.72`, `AQ`, `t_out=9` → 6,88 (у payload 6,9), клапан 0,06, `p_now` 3,31; RV `0.68`, `VE` → 17,33 / 0,15; RV `0.45`, `REC` → 11,47; RV `ST` → 0; AHU-1 17 000 м³/год, 21 °C → 68,0; RV `0.72`, `AQ`, `t_out=-10` → 21,4 | UT |
| AC-22 | R-12, A-18 | Given RV-05 без живих даних і статика; Then `airflow_m3h=5912.6`, `heat_kw=6.9`, `filter_dp_pa=287.2` (статика), `stale=True`. When жива витрата 6 000, без живого тепла → `heat_kw = round(116.8·0.75·9/33·0.3, 1) = 7.2`; When живе тепло 8,1 → 8,1; клапан живий 12 % → `heating_valve=0.12` | UT |
| AC-23 | CH-03 | `_td_bms_heat_now()` повертає 26 ключів (RV + AHU-1) без EF; сума при статиці = 322 (±0,5) | UT |
| AC-24 | FR-07 | `code='RV-5'` → `ValidationError`; `bacnet_device=106` при джерелі `device=105` → `ValidationError`; `kind='roofvent'`, `mode_design='thermostat'` → `ValidationError` | UT |
| AC-25 | R-18 | `freeze_time` і календар «Зміна 1» (тест створює ідентичний: пн–пт 07:00–11:30, 12:00–15:30, `tz=Europe/Kyiv`): вт 14.10.2026 07:00 UTC → `(04:00, 08:30)`; 08:45 UTC (11:45 Київ) → `None`; 12:31 UTC → `None`; сб 18.10 07:00 UTC → `None`; leave компанії на 15.10 → 15.10 07:00 UTC → `None` | UT |
| AC-26 | FR-06, R-19, R-20 | Given LT-CUT, `delay=10`, вт: When `level=0` о 09:55 (Київ) через `_td_ingest`; Then `off_since` = 09:55; крон о 10:04 → `check.last_text='норма'`; о 10:05 → «вимкнено в робочий час», `status='alarm'`, заявка створена telemetry; о 10:06 → нового показання немає (текст той самий, heartbeat 10 хв); `level=100` о 10:20 → `off_since=False`, крон → «норма»; рівень 0 з учора 18:00 → о 07:09 «норма», 07:10 «вимкнено…»; 11:40 → «поза робочим часом»; група `check_off=False` → «норма» | UT |
| AC-27 | FR-06, R-19 | LT-CUT `level=60` з 10:00 → о 10:10 «нижче норми» (305 < 475); `level=95` → «норма» (483,3 ≥ 475); `tol=0` і `level=98` → 498,6 < 500 → «нижче норми»; LT-SHEETS `level=50` → «норма» (`check_norm=False`); `check_norm=True` вручну на LT-SHEETS, `level=50` → `e=57,4 < 95` → «нижче норми» | UT |
| AC-28 | R-19, R-21 | рівень без показань (сигнал `unknown`) → «немає даних», заявки немає; `infra/ats/src1_ok`=0 (живий, сигнал тесту) → «немає мережі (живлення від резерву)», `off_since=False`; мережа повернулась о 10:30, рівень 0 → «вимкнено…» не раніше 10:40 | UT |
| AC-29 | R-20, M-13 | `_td_ingest` з кодом `lighting/groups/LT-CUT/level` → `off_since` = `ts` показання (не `now`); виклик із контекстом `f3d_bms_internal` → `_td_bms_on_ingest` не викликано (mock); `_td_bms_on_ingest` кидає виняток → `_td_ingest` повертає результат `super()` без винятку, показання збережено; `read_enabled=False` → не викликано | UT |
| AC-30 | A-01, CT-12 | `BMS-DERIVED`: `type='f3d_bms'`, `is_local=True`, без колектора; сигнали `…/check` на ньому; telemetry `_cron_stale()` не робить їх `stale` (через 2 год без показань); у `collector._config_payload()` джерела немає; push колектора на `…/check` → `rejected: foreign_signal`; крон пише показання лише при зміні тексту або через `check_heartbeat_min` (10 хв: о 10:05 і 10:15, не о 10:06) | UT |
| AC-31 | FR-09, R-23 | RV-05, вт: `mode=ST` з 09:50 → о 09:59 «норма», о 10:00 «не працює в робочий час» → заявка; `mode=VEL` → «норма»; `state=fault` і `ST` → перевірка «норма» (аварія — окремо за `state`); EF-ELEC `stopped` у робочий час → перевірки немає (сигналу `check` немає) | UT |
| AC-32 | FR-09, R-23 | RV-05 `indoor=15.5` з 09:30 → о 10:00 «холодно в зоні»; 23:00, `indoor=15` → «поза робочим часом»; 23:00 `indoor=9` з 22:20 → о 22:50 «холодно в зоні» (заявка «… у зоні 9,0 °C при нормі від 10,0 °C») | UT |
| AC-33 | FR-25, R-21 | сигнал `fire/totals/system_state` (створений тестом) `test`, RV-07 `stopped` → «зупинено пожежною сигналізацією», заявки немає; `normal` о 10:05 → о 10:15 «не працює…»; без сигналу, з моделлю-заглушкою `td.fire.drill` (`_td_is_active_at` → True через `patch`) — те саме; `src1_ok=0` → «немає мережі…» | UT |
| AC-34 | FR-09, CT-05 | `_td_ingest` `ventilation/units/RV-05/filter_dp_pa = 285.2` → одна заявка «Заміна фільтрів: перепад тиску 285 Па при нормі до 250» на `RV-05`, `td_bms_rule='filter_supply'`; 248 → `alarm` триває (гістерезис 5); 244 → `ok`; `…/filter_extract_dp_pa = 360` → «Заміна фільтрів витяжки: перепад тиску 360 Па при нормі до 350», `td_bms_rule='filter_extract'` | UT |
| AC-35 | FR-09 | `RV-07/state` `fault` → «Дахова установка RV-07: аварія установки (стан «fault»)», правило `unit_fault`; `frost` — те саме; `EF-CHG/state` `stopped_charging` → «Витяжка зарядної станції (Ex): не працює під час заряджання — водень!», `charging_vent`; `EF-ELEC/indoor_c` 36,2 протягом 600 с (`decimals=0`) → «Електрощитова: температура 36 °C при нормі до 35», `overheat` (599 с — ще ні); `AHU-1/room_pressure_pa` 2,0 протягом 300 с (`decimals=0`) → «Дільниця фасадів: тиск 2 Па при нормі до 0 (має бути розрідження)», `pressure`. Назви з `alarm_title` формує telemetry R-05 (числа — за `decimals`, кома) | UT |
| AC-36 | FR-10, FR-11, R-24 | живі `heat_kw` 26 установок Σ 600, `infra/totals/chp_kw` 397,3 (сигнал тесту), `equipment/BOILER/state` `fault` → `deficit 103`; о T+29 хв «норма», T+30 хв «дефіцит тепла» → заявка «Котельня: дефіцит тепла 103 кВт (потреба 600 кВт, джерела 497 кВт)» на `BOILER`; стан `fault` окремо → заявка «Котельня на відходах (2 × Kalvis K-500M): аварія котельні (стан «fault»)», `boiler_fault`; < 13 живих `heat_kw` → «немає даних» | UT |
| AC-37 | FR-13, R-22 | після AC-26 заявка: `name` «Освітлення LT-CUT (Розкрій): вимкнено в робочий час — рівень 0 % при нормі 500 лк», `td_value=0`, `td_threshold=500`, `description` містить «Група DALI G:12, щит LP-2; вимкнено з 14.10.2026 09:55.», `td_bms_rule='light_off'`, `td_bms_enriched=True`, `maintenance_type='corrective'`, команда — «Служба головного механіка»; повторні прогони — `name` незмінний, заявок 1 | UT |
| AC-38 | R-22a | `light_low` (LT-CUT 60 %) → «Освітлення LT-CUT (Розкрій): ≈ 305 лк при нормі 500 лк (рівень 60 %)», 305 / 500; `unit_off` RV-05 → «Установка RV-05 (Склад плит): не працює в робочий час — режим «Очікування»»; `cold` → «Установка RV-05 (Склад плит): у зоні 15,5 °C при нормі від 16,0 °C»; `heat_deficit` → AC-36 | UT |
| AC-39 | FR-06, R-22, R-34 | `lighting/groups/LT-CUT/faults = 1` → заявка «Аварія світильників LT-CUT: несправних 1 шт. при нормі 0», `light_fault`; `faulty='1.2.1.5'` → `description` містить «Несправні світильники: 1.2.1.5; щит LP-2, DALI-група G:12.»; `faults=0` → `status='ok'`, заявка відкрита до закриття | UT |
| AC-40 | FR-12, R-22 | після AC-34 і крону: епізод `rule='filter_supply'`, `object_code='RV-05'`, `object_kind='unit'`, `value=285.2`, `threshold=250`, `unit='Па'`, `request_id` = заявка, `state='open'`, `zone_id=Z-SHEETS`; значення 300 → `value=300`; 244 → крон → `closed`, `ended` = `status_since`, `duration_min` > 0; повторна тривога → новий епізод (2 записи) | UT |
| AC-41 | R-22, telemetry R-06 | заявку з AC-26 переведено в `Repaired`, група лишається вимкненою; Then нової заявки немає (cooldown 3 600 с); епізод `open`; через 3 601 с (freeze_time) наступний heartbeat → нова заявка, епізод `request_id` = нова, доповнена | UT |
| AC-42 | FR-20, R-26, CH-02 | Given дані без живих показань, статика `tests/data/static_bms.json`; When `env['td.viewer.provider.lighting']._td_viewer_collect(payload, ctx)`; Then для кожної з 32 груп ключі A.13 (`zone`, `zone_name`, `task`, `task_name`, `kind`, `panel`, `n`, `lumen`, `watt`, `area`, `e_norm`, `e_calc`, `level`, `e_now`, `p_inst`, `p_now`, `control`) == `dist/odoo_demo.json.lighting.groups[code]`; `panels` (`name`, `groups`, `n`, `p_inst`, `p_now`) == макет; `uf=0.7`, `mf=0.8`; `norms_ref` == макет (13 ключів); додаткові ключі CH-02 присутні | UT |
| AC-43 | FR-20, R-27 | те саме для `ventilation`: 29 `units` (ключі A.13 крім `maintenance_request`) == `dist/odoo_demo.json.ventilation.units` (числа — до округлення telemetry R-12 значень статики, тобто рівні), `totals` (AC-17), `heat_balance` == макет (`t_out -15.0`, 4 items, `total 753`, `capacity 990`, `chp_kw 856`, `reserve 1.45`, `note`); на демо `units["RV-05"].maintenance_request` = назва заявки id 6, `maintenance_request_id` = 6; дві однойменні заявки на різних установках → у кожної свій id (`test_maintenance_request_id_same_name`) | UT + TC |
| AC-44 | R-26, R-27 | живі: LT-CUT `level=60` → `level 0.6`, `e_now 305`; RV-05 `mode=ST`, `state=stopped` → `mode «Очікування»`, `mode_code «ST»`, `state «standby»`; `heating_valve` 12 % → 0.12; `supply_c` 19,337 → 19.34; `airflow_m3h` 5 852,544 → 5852.5; `faults` 1 → ключ `faults: 1`, `faulty: "1.2.1.5"` | UT |
| AC-45 | M-11, A-06 | `_td_viewer_delta(patch, ctx)` з `changes={'td.signal': {'equipment/COMPRESSOR/pressure_bar'}}` → `patch` порожній; з `{'td.signal': {'lighting/groups/LT-CUT/level'}}` → `patch['lighting']` повний розділ, `ventilation` немає; `{'td.bms': {'RV-05'}}` → обидва провайдери пишуть свої розділи; моделі мають `_name` з префіксом `td.viewer.provider.` і **не** успадковують `td.viewer.provider` (`_inherit` порожній); користувач без `group_td_user` → розділ не змінюється; без `td_viewer3d` установка й тести модуля проходять | UT |
| AC-46 | FR-14, R-28 | `get_overview_data()` на установленій базі: `zones` — 34 (без `outdoor`), кожна з `polygon` ≥ 3 точок; `groups` 32, `panels` 3 (LP-1 x=40,0), `units` 29 (RV-05 x=21,5, y=33,5); `kpi.groups_total=32`, `units_total=29`; `heat.design.total=753`; `deviations` — список відкритих ≤ 50; користувач без доступу до `td.bms.hvac.unit` → `units=[]` без винятку | UT |
| AC-47 | FR-14 | `action_open('td.bms.light.group', id, 'form')` → `act_window` форми; `'show3d'` → дія `action_f3d_show` обладнання LT-CUT; `model='res.users'` → `AccessError`. Hoot-тест `overview.test.js`: монтування `F3dBmsOverview` з фіктивними даними (2 зони, 1 установка) рендерить 2 `polygon` з класами `o_f3d_bms_ok`/`o_f3d_bms_alarm`, 1 `circle`, KPI «32 / 32»; клік по зоні викликає `orm.call(..., 'action_open', [...,'form'])` | UT (JS) |
| AC-48 | FR-21, §5.3 | чиста база (base + telemetry без демо-обладнання): Then 13 норм, 6 сцен, 3 щити, 32 групи, 29 установок, 1 баланс (4 рядки, 753), 33 джерела модуля (32 + `BMS-DERIVED`), 549 сигналів `module='bms'` (`created: 549`), `install_report.state='partial'`, `not_found: 66`; установка без винятків | UT |
| AC-49 | FR-21, A-04 | демо: `install_report` `created: 468`, `updated: 81`; 81 сигнал `ventilation/*` має `origin='sim_data'`, `last_value` і `status` як до установки (знімок), `source_id` = `BAC-<dev>-<code>`, адреса за Додатком B; сигнал RV-05 `filter_dp_pa` має `maintenance_request_id` = заявка id 6; 176 нових — `origin='catalog'`, 292 — `origin='module'` | TC |
| AC-50 | §5.3 крок 3 | демо: `equipment_id` у 32 груп (`LT-CUT` → «Освітлення: Розкрій»), 3 щитів, 29 установок (RV-05 → «Припливно-витяжна установка RV-05»), баланс → `BOILER`, `CHP`; 32 джерела з обладнанням | TC |
| AC-51 | Додаток B | Then `ventilation/units/RV-05/filter_dp_pa`: `source_id.code='BAC-105-RV-05'`, `address={"object":"AI","instance":4,"property":"present-value","mode":"poll","doc":"AI:4 RV-05_FreshAirFilterDp"}`, `period_s=30`, `store_period_s=600`, `alarm_high=250`, `hysteresis=5`; `lighting/groups/LT-CUT/level`: `HN-LP-2`, `{"group":12,"query":"level","devices":["@1.2.1.1-27"],"sample":3}`, `unit='%'`, `period_s=60`, `store_period_s=900`; `lighting/groups/LT-CUT/check`: `BMS-DERIVED`, `kind='state'`, `states` 6, `alarm_states` 2, `viewer_visible=False`; `ventilation/units/RV-05/mode`: `states` = 8 кодів, `map` 1…8; усі 549 — `write_enabled=False`; усі адреси BACnet проходять `tools.address.validate_address('bacnet_ip', …)` telemetry | UT |
| AC-52 | §5.3 крок 9 | демо: 1 епізод журналу `open`, `rule='filter_supply'`, `object_code='RV-05'`, `request_id` = id 6, `started` = `create_date` заявки | TC |
| AC-53 | §5.3 | `f3d_bms_reinstall_data()` адміністратором вдруге → `created: 0`, кількості моделей і сигналів незмінні, епізодів журналу 1 | UT + TC |
| AC-54 | FR-19 | `td.base.environment='prod'` до установки → `td.bms.read_enabled='False'`, 33 джерела `read_enabled=False` (`state='disabled'`); `test` → `True`; усі 15 параметрів §5.1 існують | UT |
| AC-55 | FR-21, §5.4 | `uninstall_hook(env)` на тестовій базі: параметри `td.bms.*` відсутні; 468 сигналів — `active=False`, без джерела; 81 — `source_id=False`, `address={}`; заявки й показання на місці | UT |
| AC-56 | FR-19 | `cr.execute(neutralize.sql)` → `read_enabled/write_enabled='False'`, крон модуля `active=False`, джерела модуля `read_enabled=False`, `state='disabled'`, сигнали `write_enabled=False`; файл виконується без помилки | UT |
| AC-57 | FR-18, R-30, A-21 | адміністратор `td_bms_write_enabled=True` → 29 джерел `write_enabled=True` (не `BAC-131…133`, не `BAC-140-BOILER`), 142 сигнали (`level`, `scene` ×32; `mode`, `setpoint_day_c`, `setpoint_night_c` ×26); `False` → 0 і 0, команди модуля в `queued` → `cancelled`; менеджер (не адмін) через RPC → `AccessError` | UT |
| AC-58 | FR-18, R-25 | оператор, усі прапори ввімкнені (telemetry `write_enabled=True` параметр): майстер LT-MAINT сцена 3, `fade_s=2` → 1 `td.command` `signal=lighting/groups/LT-MAINT/scene`, `value=3`, `text='fade=2.0'`, `origin='bms'`, `requested_by`=оператор, `state='queued'`, `expires_at` = now + 10 хв; рівень 50 на LT-CUT і LT-EB → 2 команди; чаттер групи «Надіслано команду…» | UT |
| AC-59 | R-25 | користувач `group_td_user` → `AccessError`; `td.bms.write_enabled=False` → `UserError` «Керування вимкнено: модуль «Будівля» (td.bms.write_enabled).»; telemetry вимкнено → відповідний текст; `HN-LP-3.write_enabled=False` → «Запис вимкнено на: LT-MAINT (джерело HN-LP-3)»; рівень 120 → `ValidationError` | UT |
| AC-60 | FR-18, M-13 | майстер установок: RV-05 режим `VEL` → команда `text='VEL'`; уставка ніч 12,0 → `value=12.0` на `…/setpoint_night_c`; EF-ELEC у майстрі → домен виключає; `write_enabled=True` на `ventilation/units/EF-ELEC/state`, `equipment/BOILER/return_c` або `ventilation/units/RV-05/heating_valve` → `ValidationError` «…не керується» | UT |
| AC-61 | FR-17 | `user` (лише `group_td_user`): читає всі моделі, `write` групи → `AccessError`; оператор: `write({'note'})` епізоду — ок, `write({'state'})` → `AccessError`; менеджер: редагує групи/установки/баланс/норми; `unlink` епізоду — лише адмін | UT |
| AC-62 | FR-16, FR-17 | групи: `group_td_bms_operator.implied_ids ∋ group_td_user`, `group_td_manager.implied_ids ∋ group_td_bms_operator`; меню §3 з xml-id, `sequence` (`menu_td_bms` = 80 під `menu_td_root`, `menu_td_bms_config` = 80 під `menu_td_config` — X-32), групами; `group_td_bms_operator.privilege_id` = `td_bms.privilege_td_bms`, його `category_id` = `td_factory3d.module_category_factory3d`; `group_td_bms_operator` не входить у групи `td_factory3d.privilege_td` (X-19) | UT |
| AC-63 | §4.4, §13.3 | `f3d_bms_reinstall_data()` менеджером → `AccessError`; `action_open('res.partner', …)` → `AccessError`; `dali_devices="@1.2.1.1-27;DROP"` → `ValidationError` | UT |
| AC-64 | R-31 | `build_query(2, 152, address='@1.2.1.5')` == `">V:2,C:152,@1.2.1.5#"`; `build_query(2, 161, group=12)` == `">V:2,C:161,G:12#"`; `build_query(2, 102, address='@1')` == `">V:2,C:102,@1#"`; `build_command(2, 13, 12, level=60, fade_cs=100)` == `">V:2,C:13,G:12,L:60,F:100,A:1#"`; `build_command(2, 11, 12, scene=3, block=1, fade_cs=200)` == `">V:2,C:11,G:12,B:1,S:3,F:200,A:1#"`; `group=0`/`level=101`/адреса `@1.2.1` → `ValueError` | PT |
| AC-65 | R-31 | `parse_frame("?V:2,C:152,@1.2.1.5=75#")` → `reply`, `cmd=152`, `address='@1.2.1.5'`, `answer='75'`; `"!V:2,C:104,@2.2.1.1=11#"` → `error`, `answer='11'`; `">V:2,C:13,G:12,L:60,F:100#"` → `push`, `params={'G':'12','L':'60','F':'100'}`; `"?V:2,C:164,G:16=@1.2.3.1,@1.2.3.2$"` → `partial`; `"hello#"` → `ProtocolError`; `split_stream(b'xx?V:2,C:191=2#>V:2,C:13,G:1,L:5#?V:2')` → 2 кадри, залишок `b'?V:2'`; кадр 1 600 байт → `ProtocolError` | PT |
| AC-66 | R-32 | `decode_level` для `"75"` → 75, `"2147483649"` → 0, `"100"` → 100, `"127"` → 100, `"0"` → 0 | PT |
| AC-67 | CH-05 | схеми: адреса `{"group":12,"query":"level"}` валідна; `{"query":"router","device":"@1.2.0.0"}` валідна; `{"query":"level"}` (без `group`) → помилка; `{"group":12,"query":"bogus"}` → помилка; `sample=0`, `fade_s=100` → помилки; params без `router` → помилка; `protocol='udp'` проходить схему, `connect` → `ConnectError("udp not supported")`; ті самі 5 адрес (крім розширень) проходять валідатор telemetry `validate_address('helvarnet', …)` | PT |
| AC-68 | R-32, R-35 | фейковий роутер, G:12 = `@1.2.1.1…27`, рівні 60: `poll([level])` → `Reading(value=60, q='good')`, запитів C:152 — 3 (пристрої 1, 14, 27), C:164 — 1; повторний `poll` у межах TTL — C:164 не повторюється; роутер на C:164 відповідає `!…=15#` → склад з `address.devices`; пристрій 14 → `!…=11#` → медіана з двох; усі помилки → `q='bad'` | PT |
| AC-69 | R-33 | G:12, 27 × 126 Вт × 100 % → `poll([power])` → 3,402 (scale 0,001); `scene` після C:11 S:3 → 3; без сцен → 0 | PT |
| AC-70 | R-34 | пристрій `@1.2.1.5` стан `0x02` → `faults=1`, `faulty='1.2.1.5'`; стан `0x100` (EM_Resting) → не несправний; `@1.2.1.9` `!…=11#` → несправний (2, `'1.2.1.5,1.2.1.9'`); 12 несправних → текст ≤ 64 символів із `+N`; `router` (C:102 `=1,2,3`) → `ok`/`fault`; роутера 2 немає у відповіді → `q='bad'`, `text='offline'`; C:110 виконується один раз на обидва сигнали `faults`/`faulty` за період | PT |
| AC-71 | R-36 | `params.push=true`: фейк шле push `>V:2,C:13,G:12,L:0,F:100#` → `ctx.emit` отримав `Reading(code=…/LT-CUT/level, value=0)` ≤ 1 с; push `C:11,G:12,…,S:5` → `scene=5`; push `C:23` → ігнор, лічильник +1; `push=false` → нічого | PT |
| AC-72 | R-37 | `write(level LT-MAINT, 50, "fade=1.0")` → роутер отримав `">V:2,C:13,G:19,L:50,F:100,A:1#"`, повернуто `"C13 G19 L50 F100 ack"`; фейк без ack, рівень змінено → `"… verified"`; фейк без ack і рівень не змінено → `WriteError("no ack, level now 100")`; `!…=1#` → `WriteError("HelvarNet error 1: …")`; сцена 3 → `C:11,…,S:3` і `C:109` = 3 | PT |
| AC-73 | R-37, §8.7 | `write` для `query='power'`/`faults`/`router` → `NotSupported`; `group=40` → `NotSupported`; спроба надіслати C:19 через публічний API плагіна неможлива (функцій немає; тест перевіряє, що `protocol.ALLOWED_COMMANDS == {11, 13, 102, 104, 109, 110, 152, 161, 164, 191}`) | PT |
| AC-74 | R-31 | фейк `version=1`: `connect` → C:191 з `V:2` → `!…=18#` → повтор `V:1` → `health().stats.version == 1`; подальші запити з `V:1` | PT |
| AC-75 | R-31, §8.6 | фейк закриває сокет після 5 кадрів → `poll` → `PollError`; наступний `poll` → нове з'єднання й дані; фейк зупинено → `connect` → `ConnectError`, `health().state='offline'`; `ctx.allowlist` кидає `AllowlistDenied` → жодного з'єднання (лічильник фейка 0) | PT |
| AC-76 | R-31 | `rate_per_s=10`, 40 запитів → тривалість ≥ 3,0 с; фейк `delay_s=5`, `timeout_s=0.5` → відповідний сигнал `q='bad'`, 3 таймаути поспіль → `PollError` | PT |
| AC-77 | A-03, R-31 | 3 джерела `HN-LP-1…3` на одному `host:port` → фейк бачить 1 TCP-з'єднання; `disconnect` двох — з'єднання живе; третього — закрито | PT |
| AC-78 | FR-23 | `importlib.metadata.entry_points(group="factory3d_collector.plugins")` містить `helvarnet`; `load_plugins()["helvarnet"] is HelvarNetPlugin`; `HelvarNetPlugin.validate(source)` на даних Додатка C/B → `[]` | PT |

Покриття FR: FR-01 AC-01; FR-02 AC-08, AC-09; FR-03 AC-02, AC-04…AC-06; FR-04 AC-02, AC-03; FR-05 AC-07, AC-10;
FR-06 AC-26, AC-27, AC-39; FR-07 AC-19, AC-24; FR-08 AC-20…AC-22; FR-09 AC-31, AC-32, AC-34, AC-35; FR-10 AC-13…AC-18,
AC-36; FR-11 AC-36; FR-12 AC-40; FR-13 AC-37, AC-38; FR-14 AC-46, AC-47; FR-15 MAN (ТК-10) + AC-12; FR-16 AC-62;
FR-17 AC-61, AC-62; FR-18 AC-57…AC-60; FR-19 AC-54, AC-56; FR-20 AC-42…AC-45; FR-21 AC-48…AC-55; FR-22 AC-26, AC-30;
FR-23 AC-64…AC-78; FR-24 AC-51, ТК-02; FR-25 AC-28, AC-33; FR-26 AC-08, AC-11, AC-15, AC-23, AC-33.

## 13. План тестування (для Opus)

### 13.0 Фікстури й вимоги до тестованості

**Odoo `tests/common.py`** — `class F3DBmsCase(TransactionCase)` (теги `post_install`, `-at_install`, `f3d`, `f3d_bms`),
`setUpClass`:
- `cls.zone_cut = env.ref('td_factory3d.zone_z_cut')`, `cls.zone_sheets = env.ref('td_factory3d.zone_z_sheets')`;
  `cls.group_cut = env.ref('td_bms.group_lt_cut')`, `cls.group_sheets`, `cls.group_eb`, `cls.group_maint`;
  `cls.panel2 = env.ref('td_bms.panel_lp_2')`; `cls.rv05 = env.ref('td_bms.unit_rv_05')`, `cls.rv07`,
  `cls.ahu`, `cls.ef_elec`, `cls.ef_chg`; `cls.balance = env['td.bms.heat.balance']._td_bms_get()`;
- обладнання для заявок: якщо `search_f3d('LT-CUT')` порожньо (чиста база) — тест створює `maintenance.equipment`
  `name="Освітлення: Розкрій"`, `serial_no` і `td_code` `LT-CUT`, команду `cls.team = maintenance.team «Служба головного
  механіка (тест)»` і прив'язує `group_cut.equipment_id`, сигнали (`equipment_id`); те саме для `RV-05`, `RV-07`,
  `EF-ELEC`, `EF-CHG`, `AHU-1`, `BOILER`;
- користувачі: `cls.user_reader` (`base.group_user` + `group_td_user`), `cls.user_operator` (+ `group_td_bms_operator`),
  `cls.user_manager` (+ `group_td_manager`), `cls.user_admin` (+ `group_td_admin`);
- календар `cls.cal_shift` — копія «Зміна 1» (пн–пт 07:00–11:30, 12:00–15:30, `tz='Europe/Kyiv'`), параметр
  `td.bms.calendar_id = cal_shift.id`; `cls.cal_24` (7 × 00:00–24:00) для ТК-подібних тестів;
- хелпери: `ingest(code, value=None, text=None, ts=None)` → `env['td.signal'].sudo()._td_ingest([{...}], src='module')`
  (`ts` за замовчуванням — `fields.Datetime.now()`, у тестах — `freezegun`/`odoo.tests.freeze_time`); `run_check(at)` —
  `with freeze_time(at): env['td.bms.check']._cron_check()`; `set_sql(signal, **vals)` — пряме `UPDATE td_signal`
  (`last_value`, `last_text`, `last_ts`, `status`) + `invalidate_model`; `kyiv(y, m, d, hh, mm)` → UTC naive; `make_signal(code,
  **vals)` (для сигналів energy/fire_safety у тестах: `infra/ats/src1_ok`, `infra/chp/heat_kw`, `infra/totals/chp_kw`,
  `energy/consumers/LP-2/p_now`, `fire/totals/system_state`, без джерела);
- `cls.static = json.load(file_open('td_bms/tests/data/static_bms.json'))` — розділи `lighting` і
  `ventilation` з `dist/odoo_demo.json` (генерує `tools/gen_data.py`, файл у репозиторії);
- `ctx(static=None, changes=None)` → словник `ctx` viewer M-01 (`user`, `now`, `static={'lighting':…, 'ventilation':…}`,
  `changes`).

**Плагін `tests/conftest.py`** (`pytest-asyncio`, `asyncio_mode=auto`):
- `fake_router` → `FakeHelvarRouter` на `127.0.0.1:<вільний порт>` зі складом груп LP-1…3 (Додаток A.1), рівні 100,
  вати 126, без несправностей; параметри фікстури: `version`, `push`, `ack`, `delay_s`, `drop_after`, `partial`;
- `plugin_ctx` → фейковий `PluginContext`: `allowlist` (дозволяє `127.0.0.1`, може кидати), `emit` (список), `metrics`
  (заглушка з лічильниками), `log`;
- `source_cfg(router=2, signals=[...])` → `SourceCfg` з `params={"host":"127.0.0.1","port":<порт>,"cluster":1,"router":2,
  "version":2,"rate_per_s":100,"push":true,"timeout_s":0.5}` і сигналами з Додатка B (`SignalCfg`).

### 13.1 Юніт-тести

#### 13.1.1 Odoo (`odoo-bin -d f3d_test -i td_factory3d,td_telemetry,td_bms --test-tags /td_bms --stop-after-init`)

| Файл / клас | Тести | AC | Фікстури | Що саме assert |
|---|---|---|---|---|
| `test_lighting_calc.py::TestNorms` | `test_13_norms_effective_lux`, `test_norm_constraints` | AC-01 | дані | значення `lux` (dict 13), `ref_en`; `IntegrityError` у `mute_logger` + `cr.savepoint()`; `ValidationError` |
| `::TestGroupDesign` | `test_32_groups_match_macro` (параметризований рядками Додатка A.1, жорстко вписаними в тест як таблиця), `test_totals_320_fixtures`, `test_formula_synthetic`, `test_min_one`, `test_zone_without_polygon` | AC-02, AC-03 | дані; синтетична зона `Z-T1` 10×10 м | рівність полів; `assertAlmostEqual(p_inst_kw, …, 2)`; `ValidationError` |
| `::TestFixture` | `test_passport_values`, `test_defaults_without_passport`, `test_manual_override` | AC-04 | паспорт-заглушка без специфікацій | `lumen`/`watt` |
| `::TestDali` | `test_devices_match_appendix`, `test_pack_dali_function`, `test_count_mismatch`, `test_wrong_router`, `test_injection_rejected`, `test_unique_dali_group`, `test_code_and_checks` | AC-05, AC-06, AC-63 | дані | рядки `dali_devices`; тексти `ValidationError` |
| `test_lighting_live.py::TestLive` | `test_design_fallback`, `test_live_values`, `test_sheets_design`, `test_plan_state_table` | AC-07, AC-10 | `ingest` | поля M-03 |
| `::TestPanel` | `test_design_sums`, `test_dali_sum`, `test_meter_priority`, `test_state` | AC-08, AC-09 | `make_signal('energy/consumers/LP-2/p_now')`, `set_sql` джерела `HN-LP-2.state='error'` | `p_now_kw`, `p_source`, `state` |
| `::TestContracts` | `test_light_power`, `test_kwh_from_hours`, `test_search_deviation` | AC-11, AC-12 | `td.reading.hour` створюються ORM у тесті | dict рівність; `search` |
| `test_heat_balance.py::TestDesign` | `test_macro_753`, `test_param_change_recompute`, `test_internal_gains`, `test_reset_macro`, `test_constraints`, `test_rights` | AC-13, AC-14, AC-18 | `cls.balance` | `kw_round` рядків, `total_kw`, `reserve`, `note`; `AccessError` для `user_reader` |
| `::TestLive` | `test_chp_heat_table`, `test_live_balance_table`, `test_totals_static` | AC-15…AC-17 | чисті функції `tools.heat`; `build_ventilation` | таблиці значень |
| `test_hvac_live.py::TestNominals` | `test_nominals`, `test_coordinates`, `test_constraints` | AC-19, AC-24 | дані | значення |
| `::TestState` | `test_mode_labels_states` (таблиця AC-20), `test_fallback_formulas`, `test_live_precedence`, `test_heat_now_contract` | AC-20…AC-23 | `ingest`, статика | значення, `stale` |
| `test_rules_lighting.py::TestSchedule` | `test_work_interval` | AC-25 | `cal_shift`, leave | кортежі/`None` |
| `::TestLightRules` | `test_off_in_work_delay`, `test_off_since_yesterday`, `test_lunch_and_after_shift`, `test_check_off_false`, `test_below_norm`, `test_tolerance_zero`, `test_presence_not_checked`, `test_no_data`, `test_mains_suppression` | AC-26…AC-28 | `run_check`, `ingest`, `make_signal('infra/ats/src1_ok')` | `check_signal_id.last_text`, `status`, кількість `maintenance.request` з `td_signal_id` |
| `::TestIngestHook` | `test_since_from_reading_ts`, `test_internal_context_skips`, `test_exception_isolated`, `test_read_disabled_skips` | AC-29 | `unittest.mock.patch.object(type(env['td.bms.check']), '_td_bms_on_ingest')` | виклики mock; `res` `_td_ingest`; `off_since` |
| `::TestDerivedSource` | `test_local_source`, `test_not_stale_by_telemetry`, `test_foreign_push_rejected`, `test_heartbeat` | AC-30 | `env['td.signal']._cron_stale()`, `td.collector` тесту з токеном і `_config_payload()` | стани, кількість `td.reading` сигналу `check` |
| `test_rules_hvac.py::TestUnitRules` | `test_not_running`, `test_vel_ok`, `test_fault_separate`, `test_fans_no_check`, `test_cold_work`, `test_cold_off_hours`, `test_fire_suppression_signal`, `test_fire_suppression_drill_mock`, `test_mains` | AC-31…AC-33 | `run_check`, `ingest`, `make_signal('fire/totals/system_state')` | тексти, заявки |
| `::TestThresholds` | `test_filter_supply_rv05`, `test_filter_extract`, `test_unit_fault_frost`, `test_ef_chg_charging`, `test_ef_elec_overheat`, `test_ahu_pressure`, `test_boiler_fault`, `test_heat_deficit` | AC-34…AC-36 | `ingest` | `name`, `td_bms_rule`, кількість заявок |
| `test_requests.py::TestEnrichment` | `test_light_off_title`, `test_titles_table`, `test_faults_description`, `test_idempotent` | AC-37…AC-39 | після правил | `name`, `td_value`, `td_threshold`, `description`, `td_bms_enriched` |
| `::TestJournal` | `test_open_update_close`, `test_new_episode`, `test_cooldown_new_request` | AC-40, AC-41 | `freeze_time` | поля епізодів, кількості |
| `test_viewer_provider.py::TestLightingSection` | `test_static_equals_macro`, `test_live_values` | AC-42, AC-44 | `cls.static`, `ctx()` | порівняння словників A.13 з `cls.static` (точна рівність) |
| `::TestVentilationSection` | `test_static_equals_macro`, `test_maintenance_request_key`, `test_maintenance_request_id_same_name`, `test_maintenance_request_id_cleared`, `test_live_values` | AC-43, AC-44 | ті самі | порівняння |
| `::TestProviderContract` | `test_names_without_inherit`, `test_delta_relevance`, `test_access_denied_keeps_static` | AC-45 | `ctx(changes=…)` | `_inherit`, вміст `patch` |
| `test_overview.py::TestOverview` | `test_structure_counts`, `test_access_partial`, `test_action_open` | AC-46, AC-47, AC-63 | користувачі | ключі, кількості, `AccessError` |
| `test_hooks.py::TestInstall` | `test_counts_clean`, `test_signal_definitions`, `test_reinstall_idempotent`, `test_params_environment`, `test_uninstall_hook`, `test_neutralize` | AC-48, AC-51, AC-53…AC-56 | `hooks.run_install(env)`, `uninstall_hook(env)` у транзакції тесту | кількості, `install_report`, поля сигналів, `validate_address` |
| `test_commands.py::TestWriteFlags` | `test_enable_disable`, `test_manager_rpc_denied` | AC-57 | `res.config.settings` | кількості прапорів |
| `::TestWizards` | `test_light_scene`, `test_light_level_multi`, `test_refusals`, `test_hvac_mode_setpoint`, `test_forbidden_write_flags` | AC-58…AC-60 | `user_operator`, `set_param('td.telemetry.write_enabled','True')` | поля `td.command`, тексти `UserError`/`ValidationError` |
| `test_security.py::TestRights` | `test_acl_matrix`, `test_groups_chain`, `test_own_privilege`, `test_menus`, `test_reinstall_admin_only` | AC-61…AC-63 | користувачі | `AccessError`; `env.ref(menu).sequence`; `privilege_id`/`category_id` групи оператора, група оператора поза `td_factory3d.privilege_td` (X-19) |
| `static/tests/overview.test.js` (hoot, `--test-tags /td_bms` через `HttpCase.start_tour`-незалежний `web.assets_unit_tests`) | `F3dBmsOverview renders plan`, `click opens form` | AC-47 | `mockService("orm", …)` з фіктивною відповіддю R-28 | кількість `polygon`/`circle`, класи, виклик `orm.call` |

#### 13.1.2 Плагін (`pytest services/collector_plugins/f3d_collector_bms -q`)

| Файл | Тести | AC | Що assert |
|---|---|---|---|
| `test_protocol.py` | `test_build_query`, `test_build_command`, `test_build_invalid`, `test_parse_reply_error_push_partial`, `test_split_stream`, `test_frame_too_long`, `test_decode_level`, `test_expand_devices`, `test_schemas`, `test_allowed_commands` | AC-64…AC-67, AC-73 | точні рядки; `Frame`; винятки; `jsonschema.validate` (бібліотека є в колекторі) |
| `test_plugin_helvarnet.py` | `test_level_sample_median`, `test_membership_cache_fallback`, `test_power_scene`, `test_faults_faulty_router`, `test_push_emit`, `test_write_ack_verify_fail`, `test_write_not_supported`, `test_version_fallback`, `test_reconnect_offline_allowlist`, `test_rate_limit_timeouts`, `test_shared_connection`, `test_entry_point` | AC-68…AC-72, AC-74…AC-78 | `Reading`; лічильники кадрів фейка; час виконання (`time.monotonic`); `health()` |

#### 13.1.3 Синхронізація даних з макетом (`pytest odoo_addons/td_bms/tests/test_data_sync.py`, поза Odoo)

`test_generated_files_match`: `gen_data.py --out <tmp>` → файли побайтово = `data/*` і `tests/data/static_bms.json`;
`test_groups_vs_macro`: для 32 груп `plant.lighting.layout(...)` → `n`, `e_calc`, `p_inst`, `area` = Додаток A.1;
`test_balance_vs_macro`: `plant.ventilation.heat_balance(...)` = `tools.heat.design_balance(...)` (4 рядки, 753);
`test_signal_count`: CSV 549 рядків, коди унікальні, 142 `writable=1`, 81 `new=0`.

### 13.2 Стендові сценарії ТК-01…ТК-12 (емулятор + колектор + Odoo)

Передумови (усі ТК): `docker compose -f docker-compose.sim.yml --profile dev up -d` (iot_sim, mosquitto); образ колектора
з `f3d-collector-bms` (`requirements-extra.txt`), `F3D_ALLOW_HOSTS=iot-sim,mosquitto`, `F3D_WRITE_ENABLED=0`; Odoo 19 з
копією демо (`odoo_f3d_bms`), установлені `td_factory3d`, `td_telemetry`, `td_bms` (і `td_viewer3d`
для ТК-10); токен колектора; змінна `SIM=http://127.0.0.1:8090/sim/v1`, `AUTH="Authorization: Bearer $SIM_API_TOKEN"`.
Для ТК з перевірками робочого часу менеджер створює календар «Цілодобово (ТК)» (7 × 00:00–24:00) і ставить його в
`td.bms.calendar_id`, затримки `light_check_delay_min=1`, `hvac_check_delay_min=1`, `cold_delay_min=1`,
`heat_deficit_delay_min=1`; telemetry `realarm_cooldown_s=60`. Час очікування — з запасом на опитування 30/60 с, push 5 с
і крон 60 с.

| ТК | Кроки | Очікуваний результат | Де дивитися |
|---|---|---|---|
| ТК-01 Підключення | запустити колектор; 3 хв | Завод 3D → Телеметрія → Огляд: 32 джерела bms `online`, `BMS-DERIVED` `online`; Будівля → Огляд: 32 групи з `level_source=live`, 29 установок без `stale`; сигнали `module=bms`: `ok` усі, крім `ventilation/units/RV-05/filter_dp_pa` (`alarm`, емулятор стартує з 285) | Огляд, список сигналів (фільтр «Мій модуль» = bms) |
| ТК-02 `filter_clogged` RV-05 | 1) заявку id 6 перевести в «Repaired»; `curl -X POST $SIM/reset -H "$AUTH" -d '{"keep_time":true}'` → RV-05 120 Па, сигнал `ok` ≤ 2 хв; 2) `curl -X POST $SIM/scenario/filter_clogged/start -H "$AUTH" -H 'Content-Type: application/json' -d '{"run_ref":"RUN/TK02","params":{"device":"RV-05","value":285,"ramp_min":2}}'` (лише `value` — iot_sim S-04, X-58); 3) чекати 4 хв; 4) закрити нову заявку, `POST $SIM/scenario/filter_clogged/stop` | 3) сигнал `filter_dp_pa` 285 ± 5, `alarm`; нова заявка «Заміна фільтрів: перепад тиску 285 Па при нормі до 250» на RV-05, команда «Служба головного механіка», `td_bms_rule=filter_supply`; епізод журналу `open`; картка RV-05 у переглядачі «Фільтр 285 Па · замінити»; огляд — RV-05 червоний; 4) ≤ 3 хв сигнал `ok`, епізод `closed` | Обслуговування → Заявки; Будівля → Відхилення; 3D |
| ТК-03 Освітлення вимкнене / нижче норми | календар «Цілодобово (ТК)»; 1) `POST $SIM/scenario/lighting_scene/start` `{"run_ref":"RUN/TK03A","params":{"group":"LT-CUT","level":0,"duration_s":900}}`; 2) `…/start` `{"run_ref":"RUN/TK03B","params":{"group":"LT-EB","level":60,"duration_s":900}}`; чекати 3 хв | 1) `lighting/groups/LT-CUT/level=0` ≤ 10 с (push); ≤ 2,5 хв заявка «Освітлення LT-CUT (Розкрій): вимкнено в робочий час — рівень 0 % при нормі 500 лк»; 2) LT-EB `e_now = 329` → заявка «Освітлення LT-EB (Крайкооблицювання): ≈ 329 лк при нормі 500 лк (рівень 60 %)»; огляд: Z-CUT сірий/червоний, Z-EB червоний; після `stop` — «норма», епізоди `closed` | Заявки, Відхилення, Огляд |
| ТК-04 Аварія світильника | менеджер ставить сигналам `lighting/groups/LT-CUT/faults` і `/faulty` `period_s=60`; `POST $SIM/scenario/lighting_scene/start` `{"run_ref":"RUN/TK04","params":{"group":"LT-CUT","scene":1,"fault_device":"@1.2.1.5","duration_s":900}}`; 3 хв | `faults=1`, `faulty='1.2.1.5'`; заявка «Аварія світильників LT-CUT: несправних 1 шт. при нормі 0», в описі «Несправні світильники: 1.2.1.5; щит LP-2, DALI-група G:12.»; щит LP-2 `state=fault`; після `stop` — `faults=0` | форма групи, щита; заявка |
| ТК-05 Нічне зниження | менеджер створює календар «Без робочого часу (ТК)» (без інтервалів) і ставить його в параметр; `POST $SIM/time` `{"set":"<сьогодні>T23:00:00+03:00"}`; 3 хв | RV/AHU: `mode=ST`, `state=stopped` → `state=standby`, `mode_label` «Очікування»; `heat_kw` → 0, `heat_need_kw` падає до 0; `setpoint_night_c=14.0`; перевірки «поза робочим часом»; **жодної** нової заявки й епізоду; потім календар «Цілодобово (ТК)» → ≤ 3 хв заявки «Установка RV-xx (…): не працює в робочий час — режим «Очікування»» (перевірка контрасту, 26 заявок) — закрити масово; повернути `POST $SIM/time {"set":"<сьогодні>T10:00:00+03:00"}` | Установки (kanban), Тепловий баланс, Заявки |
| ТК-06 Аварія котельні | `POST $SIM/device/BOILER/fault` `{"reason":"generic"}`; 2 хв; `POST $SIM/device/BOILER/clear` | `equipment/BOILER/state=fault`; заявка «Котельня на відходах (2 × Kalvis K-500M): аварія котельні (стан «fault»)», `boiler_fault`; баланс: `boilers_on=0`, `boiler_state=fault`; дефіциту немає (потреба < КГУ); `clear` → `standby`, епізод `closed` | Тепловий баланс, Заявки |
| ТК-07 HelvarNet недоступний | менеджер: `HN-LP-2.params.port = 50999`; 4 хв; повернути 50000 | ≤ 2 хв `HN-LP-2.state=error` («Connection refused»); ≤ 3 хв 5 груп LP-2 `stale`, перевірки «немає даних», щит LP-2 `offline`; нових заявок 0; огляд — Z-CUT…Z-FAC заштриховані; після повернення ≤ 2 хв `online`, значення живі, «норма» | Телеметрія → Огляд; Будівля → Огляд |
| ТК-08 BACnet-пристрій мовчить | `POST $SIM/device/RV-07/fault` `{"reason":"comm"}`; 3 хв; `clear` | `BAC-107-RV-07` `error`, сигнали RV-07 `stale` ≤ 90 с після помилки; перевірка RV-07 «немає даних»; заявок немає; `clear` → `online`, «норма» | Телеметрія → Джерела |
| ТК-09 Керування | адміністратор: Будівля «Дозволити керування», Телеметрія «Дозволяти команди», колектор `F3D_WRITE_ENABLED=1` (перезапуск); оператор: LT-MAINT → «Керування» → сцена 3; RV-05 → режим `VEL`; потім адміністратор вимикає керування | команда LT-MAINT `done` ≤ 15 с (`result` містить `ack` або `verified`), рівень групи 50 % ≤ 60 с; RV-05 команда `done`, `mode=VEL` ≤ 60 с; після вимкнення — майстер не відкривається (`UserError`), прапори `write_enabled` 0/0 | Телеметрія → Команди; форми |
| ТК-10 Інтерфейс і 3D | з `td_viewer3d`: Будівля → Огляд — план, KPI, вкладки; група LT-CUT → «Показати в 3D»; переглядач: картка LT-CUT, RV-05, «Теплова мережа» | картки показують ті самі числа, що форми (`e_now`, режим, витрата, фільтр, «Зима −15 °C ≈ 753 кВт з 990 кВт двох котлів і 856 кВт КГУ»); живе оновлення ≤ 15 с після зміни рівня (ТК-03) | UI, 3D |
| ТК-11 Пожежне навчання (з `td_fire_safety`, інакше MAN-пропуск) | календар «Цілодобово (ТК)»; `POST $SIM/scenario/fire_drill/start` `{"run_ref":"RUN/TK11","params":{"zone":"FA-CNC","duration_s":300}}`; 8 хв | ≤ 1 хв RV/AHU `ST`; `fire/totals/system_state=test`; перевірки «зупинено пожежною сигналізацією»; заявок «не працює…» 0; після завершення установки запускаються, перевірки «норма» | Установки, Заявки |
| ТК-12 Звірка з пристроєм | `curl -s "$SIM/signals?device=RV-08" -H "$AUTH"`; `printf '>V:2,C:152,@1.2.1.1#' \| nc -q1 iot-sim 50000` (з контейнера колектора) | значення в Odoo (форма RV-08, LT-CUT) збігаються з емулятором (± шум за 30 с; рівень — точно) | термінал, форми |

### 13.3 Тести безпеки (ТБ)

| ТБ | Перевірка | Як |
|---|---|---|
| ТБ-01 | користувач без `group_td_user` не читає моделі модуля, меню «Будівля» невидиме | UT `test_acl_matrix` |
| ТБ-02 | оператор не змінює налаштування груп/установок/балансу; не видаляє журнал | AC-61 |
| ТБ-03 | команда неможлива без будь-якого з п'яти запобіжників; з `F3D_WRITE_ENABLED=0` колектор не забирає команди → `expired` за 10 хв | AC-57…AC-59, ТК-09 (варіант з `F3D_WRITE_ENABLED=0`) |
| ТБ-04 | заборонені записи: EF-*, котельня, AO:1/AO:2/BV:1, G:40, інші команди HelvarNet | AC-60, AC-73 |
| ТБ-05 | ін'єкції: `dali_devices` з `#`, `;DROP`, адреси з `>`; JSON `address` з ключем `_x` (telemetry A.0) → `ValidationError`; плагін не формує кадр із нецілих значень | AC-05, AC-63, AC-64 |
| ТБ-06 | allow-list колектора блокує роутер поза списком | AC-75 |
| ТБ-07 | `neutralize.sql` вимикає читання, запис, крон | AC-56 |
| ТБ-08 | у `params` джерел модуля немає секретів (усі 32 проходять `validate_params` telemetry без помилок про секрети) | UT `test_signal_definitions` |
| ТБ-09 | `action_open` огляду приймає лише 4 моделі | AC-63 |
| ТБ-10 | логи колектора на INFO не містять кадрів HelvarNet; на DEBUG — лише кадри без секретів | PT `caplog` у `test_power_scene` |

### 13.4 Тести продуктивності (ТП)

| ТП | Обсяг | Норма | Як виміряти |
|---|---|---|---|
| ТП-01 | 29 BACnet-пристроїв + котельня telemetry, ≈ 380 об'єктів, `period_s=30` | цикл опитування пристрою p95 ≤ 2 с, `collector_poll_overrun_total` = 0 за 30 хв | метрики колектора `/metrics` |
| ТП-02 | 3 роутери, 32 групи, 320 пристроїв | обхід несправностей ≤ 30 с при `rate_per_s=20`; рівень/потужність/сцена 32 груп ≤ 10 с за хвилину | лог плагіна (`sweep done in …`), PT з фейком 320 пристроїв і `rate_per_s=100` ≤ 5 с |
| ТП-03 | ≈ 12 показань/с від bms у push | API-02 telemetry p95 ≤ 1 с на пакет 1 000 | метрика `collector_push_latency_seconds` |
| ТП-04 | крон перевірок 61 об'єкт + журнал 549 сигналів | ≤ 2 с на прогін; провайдери ≤ 300 мс; `get_overview_data` ≤ 500 мс | UT `test_perf_check` (`time.perf_counter`, демо-дані), лог крона |
| ТП-05 | доба роботи стенда | ≤ 60 000 нових рядків `td.reading` сигналів `module='bms'` | SQL `SELECT count(*) FROM td_reading r JOIN td_signal s ON s.id=r.signal_id WHERE s.module='bms' AND r.ts > now() - interval '1 day'` |

### 13.5 Чек-лист DEPLOY_TEST (`docs/modules/td_bms/DEPLOY_TEST.md`, здає W7) — «одна зона → усі»

1. Дамп бази `odoo` тестового сервера → `odoo_f3d_bms`; знімок `SELECT code, last_value, status, maintenance_request_id
   FROM td_signal WHERE code LIKE 'ventilation/%'` (після установки telemetry).
2. Установити `td_bms`; лог без ERROR; `install_report.state='done'`, лічильники §5.3 (468/81, 65 обладнання).
3. Прогнати `--test-tags /td_bms` на `odoo_f3d_bms` → 0 падінь; `pytest` плагіна й `test_data_sync.py` → 0 падінь.
4. **Одна зона:** параметр `read_enabled=True`, але всім джерелам модуля `read_enabled=False`, крім `BAC-108-RV-08`,
   `BAC-109-RV-09`, `HN-LP-2`; запустити колектор; ТК-12 для RV-08, RV-09, LT-CUT; переконатися, що інші джерела
   `disabled`, заявок по інших об'єктах немає; ТК-03 (лише LT-CUT).
5. **Усі:** увімкнути решту джерел (список джерел → «Читати» масово); ТК-01, ТК-02, ТК-04…ТК-08.
6. ТК-09 (керування) — лише на стенді з емулятором; на копії проду керування не вмикається.
7. Відкат: `neutralize.sql` → крон і джерела вимкнені; деінсталяція модуля → §5.4 (сигнали деактивовані, заявки на
   місці); база `odoo` не змінювалася.
8. Записати фактичні числа в `CHANGELOG.md` («Установка на копію демо 14.10.2026»).

## 14. Definition of Done

- Усі UT §13.1.1 зелені на чистій базі й копії демо; PT §13.1.2 і `test_data_sync.py` зелені; hoot-тест огляду зелений.
- ТК-01…ТК-10, ТК-12 пройдені на стенді (ТК-11 — за наявності fire_safety), протокол у `TEST_REPORT.md` з фактичними
  числами; ТБ-01…ТБ-10, ТП-01…ТП-05 виконані.
- Кожен AC-01…AC-78 має зелений тест або відмітку ТК/MAN у протоколі; покриття FR — таблиця під §12.
- `ruff check` (довжина рядка 120) без помилок для `odoo_addons/td_bms` і `services/collector_plugins/f3d_collector_bms`;
  `eslint`/`prettier` проєкту — для `static/src`.
- Жодного `x_`-поля; `grep -rn "x_f3d" odoo_addons/td_bms` порожній.
- `neutralize.sql` перевірений (AC-56); стоп-крани описані в README; `write_enabled` за замовчуванням `False`.
- README модуля (установка, параметри, 6 інструкцій ARCH §4), README плагіна (встановлення в образ, `params`/`address`,
  обмеження), `CHANGELOG.md` `19.0.1.0.0`.
- Перегляд безпеки §13.3 пройдено; SQL лише параметризований; плагін — whitelist команд.
- Контракти CH-01…CH-06 реалізовані з точними іменами; зміна імен — лише через SPEC і повідомлення авторів viewer,
  energy, fire_safety, telemetry.
- `DEPLOY_TEST.md` заповнений за §13.5.

## 15. Відкриті питання

Ті самі Q-01…Q-14, що в ARCH §5.1 (нумерація спільна); тут — що робить код, поки відповіді немає.

| ID | Поки немає відповіді |
|---|---|
| Q-01 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** напряму BACnet і HelvarNet; при появі BMS — лише `params` джерел. читаємо напряму: 29 джерел BACnet (dev 101…133) і 3 HelvarNet; перехід на BMS — лише `params`/`address` (Додатки B, C) |
| Q-02 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** BACnet-ПРИПУЩЕННЯ до переліку точок Hoval; при Modbus — ті самі коди. адреси BACnet за iot_sim §8.10.2 (ПРИПУЩЕННЯ); Modbus-шлюз Hoval — нові джерела `modbus_tcp` з тими самими кодами сигналів |
| Q-03 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** більша з норм EN 12464-1 і ДБН В.2.5-28 (зі Зміною № 1). норми — `lux_norms.json` (EN 12464-1:2021); `ref_dbn` — «звірити (Q-03)»; правка — менеджер у формі норми |
| Q-04 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** `V:2`, C:161/C:164; фолбек `V:1`. `version=2` з фолбеком на 1; склад групи — C:164 з фолбеком `devices`; підтвердження запису — ack/push/перевірка; маска несправностей `0x0800000E` за документом Helvar |
| Q-05 | **Закрито 14.10 (відповідь № 14, CONSISTENCY):** календар «Зміна 1 (07:00–15:30)». календар компанії «Зміна 1»; поле `calendar_id` на групі/установці для винятків |
| Q-06 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** поза v1; далі — щомісячний план ТО. аварійне освітлення не моніториться модулем |
| Q-07 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** v2. групи «присутність» — лише «вимкнено в робочий час» |
| Q-08 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** оператори — енергетик і головний механік; керування — наказом головного інженера. група «Будівля: оператор» без користувачів; керування вимкнено |
| Q-09 | **закрито X-34, X-40, X-58**: каталог iot_sim доповнюється з Додатка B (джерело — bms); стан щита — агрегат роутера (R-34), R-23 iot_sim `heat_nom = 116,8`, біти C:110 за документом Helvar, рівень EF-CHG — за A-20; ТК передають лише `value` |
| Q-10 | **закрито X-06**: telemetry R-07 рахує `stale_after` для COV від інтервалу контрольного читання; у v1 усі BACnet-сигнали лишаються `mode="poll"` (A-02), перехід на COV — даними |
| Q-11 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** `internal_gains_kw = 0`. `internal_gains_kw = 0` |
| Q-12 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** пороги §3 погоджено. пороги — §3 ARCH / §5.1 |
| Q-13 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** лише огляд і дашборд, без `mail.activity` (як telemetry Q-11, відповідь № 8). втрата зв'язку — лише огляд/переглядач/«немає даних» |
| Q-14 | **Закрито 14.10 (відповідь № 13, CONSISTENCY):** після відбою — звичайна перевірка з затримкою 10 хв. придушення R-21 за сигналами fire_safety/energy; після відбою — звичайні затримки |

## Додаток A. Дані з макета

### A.0 Норми освітленості (`data/td_bms_light_norm_data.xml`, з `plant/lux_norms.json`, R-01)

| key | name | lux | UGR | Ra | ref_en |
|---|---|---|---|---|---|
| `woodworking_machine` | верстатна обробка деревини | 500 | 19 | 80 | EN 12464-1:2021, табл. 33, реф. 33.6 (ред. 2011 — 5.25.6) |
| `woodworking_bench` | збирання, верстакові роботи | 300 | 25 | 80 | табл. 33, реф. 33.4 (5.25.4) |
| `spraying` | фарбування, оздоблення | 750 | 22 | 80 | табл. 33, реф. 33.5 (5.25.5) |
| `sanding` | шліфування, оздоблення фасадів | 750 | 22 | 80 | табл. 33, реф. 33.5 (5.25.5) |
| `quality_control` | контроль якості | 1000 | 19 | 90 | табл. 33, реф. 33.9 (5.25.9) |
| `storage_racks` | стелажні проходи з персоналом | **150** | 22 | 60 | табл. 13, реф. 13.2 (5.5.2) |
| `storage_floor` | складування | 100 | 25 | 60 | табл. 12, реф. 12.1 (5.4.1) |
| `packing_dispatch` | пакування й відвантаження | 300 | 25 | 60 | табл. 12, реф. 12.2 (5.4.2) |
| `loading_ramps` | рампи завантаження | 150 | 25 | 40 | табл. 9, реф. 9.4 (5.1.4) |
| `switchgear_room` | електрощитова | 200 | 25 | 60 | табл. 11, реф. 11.1 (5.3.1) |
| `compressor_room` | компресорна | 200 | 25 | 60 | табл. 11, реф. 11.1 (5.3.1) |
| `battery_charging` | заряджання акумуляторів | **200** | 25 | 60 | табл. 11, реф. 11.1 (5.3.1) — за аналогією |
| `corridors_traffic` | проходи й проїзди | 150 | 28 | 40 | табл. 9, реф. 9.1 (5.1.1) |

`ref_en` у даних — повний рядок `ref` json («EN 12464-1:2021, …»); `note`, `sources` — з json; `ref_dbn` — умовчання M-01.

### A.1 Групи освітлення (`data/td_bms_light_data.xml`; перевірка R-03/R-04/R-06; Φ = 20 500 лм, W = 126 Вт для всіх)

Колонки: № (= `dali_group`, `sequence` = № × 10) | `code` | зона | назва зони | `norm` (task) | `fixture_kind` | `panel` | `n_fixtures` | `area_m2` | `E_н` | `n_required` | `e_calc` | `level_design` | `control_mode` | G | `dali_devices` | `p_inst_kw`.

| № | code | zone | назва | task | kind | panel | n | A | E_н | n_req | e_calc | level | control | G | dali_devices | p_inst |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | LT-RCV-1 | Z-RCV-1 | Приймання плит · ворота 1 | packing_dispatch | highbay | LP-1 | 4 | 118.4 | 300 | 4 | 388 | 1.0 | shift | 1 | @1.1.1.1-4 | 0.5 |
| 2 | LT-RCV-2 | Z-RCV-2 | Приймання плит · ворота 2 | packing_dispatch | highbay | LP-1 | 4 | 124.2 | 300 | 4 | 370 | 1.0 | shift | 2 | @1.1.1.5-8 | 0.5 |
| 3 | LT-RCV-3 | Z-RCV-3 | Приймання плит · ворота 3 | packing_dispatch | highbay | LP-1 | 4 | 124.2 | 300 | 4 | 370 | 1.0 | shift | 3 | @1.1.1.9-12 | 0.5 |
| 4 | LT-RCV-4 | Z-RCV-4 | Приймання фурнітури, контроль і карантин · ворота 4 | packing_dispatch | highbay | LP-1 | 4 | 124.2 | 300 | 4 | 370 | 1.0 | shift | 4 | @1.1.1.13-16 | 0.5 |
| 5 | LT-RCV-5 | Z-RCV-5 | Приймання крайки · ворота 5 | packing_dispatch | highbay | LP-1 | 4 | 124.2 | 300 | 4 | 370 | 1.0 | shift | 5 | @1.1.1.17-20 | 0.5 |
| 6 | LT-RCV-6 | Z-RCV-6 | Приймання ЛФМ · ворота 6 | packing_dispatch | highbay | LP-1 | 4 | 124.2 | 300 | 4 | 370 | 1.0 | shift | 6 | @1.1.1.21-24 | 0.5 |
| 7 | LT-RCV-7 | Z-RCV-7 | Приймання пакматеріалів · ворота 7 | packing_dispatch | highbay | LP-1 | 4 | 144.0 | 300 | 4 | 319 | 1.0 | shift | 7 | @1.1.1.25-28 | 0.5 |
| 8 | LT-SHEETS | Z-SHEETS | Склад плит | storage_floor | highbay | LP-1 | 12 | 1200.6 | 100 | 11 | 115 | 0.8 | presence | 8 | @1.1.1.29-40 | 1.51 |
| 9 | LT-HW | Z-HW | Склад фурнітури | storage_racks | highbay_rack | LP-1 | 5 | 350.5 | 150 | 5 | 164 | 0.7 | presence | 9 | @1.1.1.41-45 | 0.63 |
| 10 | LT-EDGE | Z-EDGE | Склад крайки | storage_racks | highbay_rack | LP-1 | 3 | 167.6 | 150 | 3 | 205 | 0.7 | presence | 10 | @1.1.1.46-48 | 0.38 |
| 11 | LT-PKS | Z-PKS | Пакувальні матеріали | storage_floor | highbay | LP-1 | 2 | 142.2 | 100 | 2 | 161 | 0.6 | presence | 11 | @1.1.1.49-50 | 0.25 |
| 12 | LT-CUT | Z-CUT | Розкрій | woodworking_machine | highbay | LP-2 | 27 | 609.3 | 500 | 27 | 509 | 1.0 | shift | 12 | @1.2.1.1-27 | 3.4 |
| 13 | LT-EB | Z-EB | Крайкооблицювання | woodworking_machine | highbay | LP-2 | 27 | 564.5 | 500 | 25 | 549 | 1.0 | shift | 13 | @1.2.1.28-54 | 3.4 |
| 14 | LT-CNC | Z-CNC | Присадка | woodworking_machine | highbay | LP-2 | 27 | 564.5 | 500 | 25 | 549 | 1.0 | shift | 14 | @1.2.2.1-27 | 3.4 |
| 15 | LT-SORT | Z-SORT | Сортування деталей | woodworking_bench | highbay | LP-2 | 12 | 439.0 | 300 | 12 | 314 | 1.0 | shift | 15 | @1.2.2.28-39 | 1.51 |
| 16 | LT-FAC | Z-FAC | Дільниця фасадів МДФ | spraying | highbay | LP-2 | 91 | 1235.0 | 750 | 81 | 846 | 1.0 | shift | 16 | @1.2.3.1-64;@1.2.4.1-27 | 11.47 |
| 17 | LT-ASM | Z-ASM | Збирання | woodworking_bench | highbay | LP-3 | 15 | 498.8 | 300 | 14 | 345 | 1.0 | shift | 17 | @1.3.1.1-15 | 1.89 |
| 18 | LT-PRE | Z-PRE | Буфер комплектів | storage_racks | highbay | LP-3 | 4 | 268.3 | 150 | 4 | 171 | 0.8 | presence | 18 | @1.3.1.16-19 | 0.5 |
| 19 | LT-MAINT | Z-MAINT | Ремонтна дільниця | woodworking_bench | highbay | LP-3 | 4 | 125.4 | 300 | 4 | 366 | 1.0 | shift | 19 | @1.3.1.20-23 | 0.5 |
| 20 | LT-PACK | Z-PACK | Пакування | packing_dispatch | highbay | LP-3 | 12 | 382.8 | 300 | 11 | 360 | 1.0 | shift | 20 | @1.3.1.24-35 | 1.51 |
| 21 | LT-POST | Z-POST | Вихід з пакування | storage_floor | highbay | LP-3 | 3 | 297.0 | 100 | 3 | 116 | 0.8 | presence | 21 | @1.3.1.36-38 | 0.38 |
| 22 | LT-CMP | Z-CMP | Компресорна | compressor_room | highbay | LP-3 | 2 | 63.8 | 200 | 2 | 360 | 0.5 | presence | 22 | @1.3.1.39-40 | 0.25 |
| 23 | LT-CHG | Z-CHG | Зарядна станція | battery_charging | highbay | LP-3 | 2 | 63.8 | 200 | 2 | 360 | 0.5 | presence | 23 | @1.3.1.41-42 | 0.25 |
| 24 | LT-FG | Z-FG | Склад готової продукції | storage_racks | highbay_rack | LP-3 | 12 | 835.0 | 150 | 11 | 165 | 0.6 | presence | 24 | @1.3.1.43-54 | 1.51 |
| 25 | LT-ELEC | Z-ELEC | Електрощитова | switchgear_room | highbay | LP-3 | 4 | 118.8 | 200 | 3 | 387 | 0.5 | presence | 25 | @1.3.1.55-58 | 0.5 |
| 26 | LT-OUT-1 | Z-OUT-1 | Відвантаження · ворота 1 | packing_dispatch | highbay | LP-3 | 4 | 124.0 | 300 | 4 | 370 | 1.0 | shift | 26 | @1.3.1.59-62 | 0.5 |
| 27 | LT-OUT-2 | Z-OUT-2 | Відвантаження · ворота 2 | packing_dispatch | highbay | LP-3 | 4 | 130.0 | 300 | 4 | 353 | 1.0 | shift | 27 | @1.3.2.1-4 | 0.5 |
| 28 | LT-OUT-3 | Z-OUT-3 | Відвантаження · ворота 3 | packing_dispatch | highbay | LP-3 | 4 | 130.0 | 300 | 4 | 353 | 1.0 | shift | 28 | @1.3.2.5-8 | 0.5 |
| 29 | LT-OUT-4 | Z-OUT-4 | Відвантаження · ворота 4 | packing_dispatch | highbay | LP-3 | 4 | 130.0 | 300 | 4 | 353 | 1.0 | shift | 29 | @1.3.2.9-12 | 0.5 |
| 30 | LT-OUT-5 | Z-OUT-5 | Відвантаження · ворота 5 | packing_dispatch | highbay | LP-3 | 4 | 130.0 | 300 | 4 | 353 | 1.0 | shift | 30 | @1.3.2.13-16 | 0.5 |
| 31 | LT-OUT-6 | Z-OUT-6 | Відвантаження · ворота 6 | packing_dispatch | highbay | LP-3 | 4 | 130.0 | 300 | 4 | 353 | 1.0 | shift | 31 | @1.3.2.17-20 | 0.5 |
| 32 | LT-OUT-7 | Z-OUT-7 | Відвантаження · ворота 7 | packing_dispatch | highbay | LP-3 | 4 | 150.8 | 300 | 4 | 305 | 1.0 | shift | 32 | @1.3.2.21-24 | 0.5 |

Разом 320 світильників, `p_inst` 40,32 кВт; режим «зміна» — 22 групи, «присутність» — 10. `name` групи = «Освітлення:
<назва зони>» (як обладнання демо). `passport_id` = `td_factory3d.passport_highbay_rack` для `highbay_rack`, інакше
`passport_highbay`.

### A.2 Щити освітлення (`panel_lp_<n>`)

| code | name | router | x | y | zone | source | групи / n / p_inst / p_now (проєкт) |
|---|---|---|---|---|---|---|---|
| LP-1 | Щит освітлення ЩО-1 · склади сировини, приймання | 1 | 40,0 | 71,0 | Z-PKS | HN-LP-1 | 11 / 50 / 6,3 / 5,6 |
| LP-2 | Щит освітлення ЩО-2 · лінії й дільниця фасадів | 2 | 90,6 | 71,0 | Z-FAC | HN-LP-2 | 5 / 184 / 23,2 / 23,2 |
| LP-3 | Щит освітлення ЩО-3 · збирання, пакування, склад ГП, відвантаження | 3 | 135,0 | 71,0 | Z-ELEC | HN-LP-3 | 16 / 86 / 10,8 / 9,5 |

`x` — `plant/lighting.py:PANELS`; `y = 71,0` — біля північної стіни всередині зони (план); `cluster = 1`.

### A.3 Установки (`data/td_bms_hvac_data.xml`, `unit_<slug>`; з `plant/ventilation.py`, паспортів і `dist/odoo_demo.json`)

| code | name | kind | device | x | y | zone | mode_design | airflow_nom | heat_nom | p_inst | fan_count | required_in_work | статика макета (витрата / тепло / клапан / p_now / фільтр / стан) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RV-01 | Дахова установка RV-01 | roofvent | 101 | 7,0 | 12,0 | Z-RCV-2 | VE | 8 000 | 116,8 | 8,6 | 1 | так | 5467,5 / 17,3 / 0,15 / 2,8 / 210,1 / on |
| RV-02 | Дахова установка RV-02 | roofvent | 102 | 7,0 | 36,0 | Z-RCV-4 | VE | 8 000 | 116,8 | 8,6 | 1 | так | 5387,4 / 17,1 / 0,15 / 2,69 / 177,3 / on |
| RV-03 | Дахова установка RV-03 | roofvent | 103 | 7,0 | 62,5 | Z-RCV-7 | VE | 8 000 | 116,8 | 8,6 | 1 | так | 5205,5 / 16,8 / 0,14 / 2,57 / 144,5 / on |
| RV-04 | Дахова установка RV-04 | roofvent | 104 | 21,5 | 12,0 | Z-SHEETS | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5878,7 / 7,0 / 0,06 / 3,45 / 207,4 / on |
| RV-05 | Дахова установка RV-05 | roofvent | 105 | 21,5 | 33,5 | Z-SHEETS | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5912,6 / 6,9 / 0,06 / 3,31 / 287,2 / on |
| RV-06 | Дахова установка RV-06 | roofvent | 106 | 21,5 | 58,5 | Z-HW | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5713,8 / 6,8 / 0,06 / 3,18 / 201,1 / on |
| RV-07 | Дахова установка RV-07 | roofvent | 107 | 35,0 | 62,5 | Z-EDGE | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5407,6 / 6,7 / 0,06 / 3,05 / 126,2 / on |
| RV-08 | Дахова установка RV-08 | roofvent | 108 | 50,0 | 23,0 | Z-CUT | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 6047,7 / 7,2 / 0,06 / 3,73 / 207,5 / on |
| RV-09 | Дахова установка RV-09 | roofvent | 109 | 51,5 | 36,5 | Z-CUT | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 6000,0 / 7,1 / 0,06 / 3,58 / 138,3 / on |
| RV-10 | Дахова установка RV-10 | roofvent | 110 | 67,0 | 23,0 | Z-EB | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 6575,6 / 7,8 / 0,07 / 4,84 / 176,5 / on |
| RV-11 | Дахова установка RV-11 | roofvent | 111 | 66,5 | 36,5 | Z-EB | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5575,6 / 6,6 / 0,06 / 2,93 / 209,2 / on |
| RV-12 | Дахова установка RV-12 | roofvent | 112 | 77,0 | 23,0 | Z-CNC | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5667,1 / 6,7 / 0,06 / 3,05 / 194,3 / on |
| RV-13 | Дахова установка RV-13 | roofvent | 113 | 77,0 | 36,5 | Z-CNC | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5601,5 / 6,8 / 0,06 / 3,18 / 205,4 / on |
| RV-14 | Дахова установка RV-14 | roofvent | 114 | 87,0 | 8,0 | Z-SORT | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5615,6 / 6,9 / 0,06 / 3,31 / 124,4 / on |
| RV-15 | Дахова установка RV-15 | roofvent | 115 | 87,0 | 36,5 | Z-SORT | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5768,3 / 7,0 / 0,06 / 3,45 / 209,3 / on |
| RV-16 | Дахова установка RV-16 | roofvent | 116 | 101,0 | 8,0 | Z-ASM | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5879,3 / 7,1 / 0,06 / 3,58 / 138,1 / on |
| RV-17 | Дахова установка RV-17 | roofvent | 117 | 101,0 | 31,0 | Z-PRE | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5943,6 / 7,2 / 0,06 / 3,73 / 149,4 / on |
| RV-18 | Дахова установка RV-18 | roofvent | 118 | 114,0 | 8,0 | Z-PACK | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 5947,3 / 7,1 / 0,06 / 3,58 / 208,2 / on |
| RV-19 | Дахова установка RV-19 | roofvent | 119 | 114,0 | 31,0 | Z-PACK | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 6137,6 / 7,2 / 0,06 / 3,73 / 151,2 / on |
| RV-20 | Дахова установка RV-20 | roofvent | 120 | 114,0 | 52,0 | Z-POST | AQ | 8 000 | 116,8 | 8,6 | 1 | так | 6423,0 / 7,7 / 0,07 / 4,67 / 169,2 / on |
| RV-21 | Дахова установка RV-21 | roofvent | 121 | 125,4 | 57,0 | Z-FG | REC | 8 000 | 116,8 | 8,6 | 1 | так | 3650,6 / 11,5 / 0,1 / 0,88 / 150,4 / on |
| RV-22 | Дахова установка RV-22 | roofvent | 122 | 130,9 | 57,0 | Z-FG | REC | 8 000 | 116,8 | 8,6 | 1 | так | 3601,1 / 11,5 / 0,1 / 0,88 / 167,2 / on |
| RV-23 | Дахова установка RV-23 | roofvent | 123 | 142,5 | 12,0 | Z-OUT-2 | VE | 8 000 | 116,8 | 8,6 | 1 | так | 6393,1 / 20,9 / 0,18 / 4,84 / 202,2 / on |
| RV-24 | Дахова установка RV-24 | roofvent | 124 | 142,5 | 36,0 | Z-OUT-4 | VE | 8 000 | 116,8 | 8,6 | 1 | так | 6269,0 / 19,6 / 0,17 / 4,03 / 135,2 / on |
| RV-25 | Дахова установка RV-25 | roofvent | 125 | 142,5 | 62,5 | Z-OUT-7 | VE | 8 000 | 116,8 | 8,6 | 1 | так | 5937,4 / 19,4 / 0,17 / 3,88 / 150,2 / on |
| AHU-1 | Припливна установка дільниці фасадів | ahu | 130 | 66,0 | 56,5 | Z-FAC | VE | 20 000 | 0 | 15,0 | 1 | так | 16959,1 / 68,0 / 0,46 / 9,3 / 162,2 / on |
| EF-ELEC | Витяжні вентилятори електрощитової | fan | 131 | 124,9 | 71,4 | Z-ELEC | thermostat | 14 120 | 0 | 0,84 | 2 | ні | 14183,7 / — / — / 0,84 / — / on |
| EF-CMP | Витяжний вентилятор компресорної | fan | 132 | 111,0 | 71,4 | Z-CMP | thermostat | 7 060 | 0 | 0,42 | 1 | ні | 0,0 / — / — / 0,0 / — / standby |
| EF-CHG | Витяжка зарядної станції (Ex) | exfan | 133 | 119,0 | 70,5 | Z-CHG | charging | 644 | 0 | 0,178 | 1 | ні | 159,7 / — / — / 0,107 / — / on |

`t_supply_design` AHU-1 = 21,0; `required_m3h` EF-CHG = 158,4; `note` AHU-1, EF-ELEC, EF-CMP, EF-CHG — тексти `note`
макета (`plant/ventilation.py`). Координати вентиляторів EF-ELEC/EF-CMP — точки `(x, z)` на північній стіні
(`WALL_FANS`, `site.py:1233`), на плані `y = 71,4`; EF-CHG — `CHG_EXHAUST`; AHU-1 — `AHU_POS`. Статика — значення
`dist/odoo_demo.json` (база провайдера без живих даних, AC-43).

### A.4 Тепловий баланс (`heat_balance_main`, R-14)

| Параметр | Значення | Рядок | кВт | `formula` |
|---|---|---|---|---|
| `t_out_design` / `t_in_set` | −15,0 / 18,0 | Тепловтрати через стіни, покрівлю й підлогу | 189 (188,71) | (3 996·0,35 + 10 800·0,25 + 10 800·0,15)·33/1000 |
| `length_m` × `width_m` × `height_m` | 150 × 72 × 9 | Інфільтрація крізь ворота (0,1 обміну/год) | 109 (109,06) | 97 200·0,1·0,34·33/1000 |
| `u_wall` / `u_roof` / `u_floor` | 0,35 / 0,25 / 0,15 | Дахові установки: 50 % зовнішнього повітря, рекуперація 78 % | 247 (246,84) | 200 000·0,5·0,34·33·(1 − 0,78)/1000 |
| `infiltration_ach`, `winter_oa_share`, `heat_recovery`, `air_wh_m3k` | 0,1; 0,5; 0,78; 0,34 | Приплив дільниці фасадів (без рекуперації — витяжка з фарбування) | 208 (208,08) | 20 000·0,85·0,34·(21 − (−15))/1000 |
| `ahu_design_share`, `ahu_supply_c`, `internal_gains_kw` | 0,85; 21,0; 0 | **Разом** | **753** (752,69) | |
| `boilers` × `boiler_kw`, `boiler_stage_share` | 2 × 495; 0,85 | Котли | 990 | |
| `chp_el_kw`, `chp_heat_kw`/`_75`/`_50`, `chp_min_load` | 800; 856 / 676 / 497; 0,5 | Запас із КГУ / котлів | 1,45 / 0,32 | (990 + 856)/752,69 − 1; 990/752,69 − 1 |

## Додаток B. Сигнали модуля (`data/bms_signals.csv`, 549; CH-01)

Шаблони розгортає генератор; `<U>` — код установки, `<d>` — BACnet device (RV-NN → 100 + NN, AHU-1 → 130, EF-ELEC 131,
EF-CMP 132, EF-CHG 133), `<G>` — код групи, `<g>` — DALI-група (Додаток A.1), `<r>` — роутер щита групи, `<devs>` —
`dali_devices` групи як список елементів. Усі: `module='bms'`, `write_enabled=False`, `create_request=True` (крім
вказаних), `equipment` = `<U>`/`<G>`/`LP-<r>`/`BOILER` (для `outdoor_c` — `RV-01`), `scale=1` (крім вказаних).
Адреси BACnet мають `"property": "present-value"`, `"mode": "poll"` і `"doc": "<об'єкт> <U>_<object-name iot_sim>"`
(нижче скорочено). `new` 0 — сигнал рівня 0 (оновлення прив'язки), 1 — створення. `origin`: `sim_data` / `catalog` /
`module`.

### B.1 Дахові установки й AHU-1 (26 × 13 + 2 = 340), джерело `BAC-<d>-<U>`

| role | code | new / origin | name | quantity | kind / unit | address | period / store; decimals | пороги, стани, заголовок | vis. | writable |
|---|---|---|---|---|---|---|---|---|---|---|
| `airflow` | `ventilation/units/<U>/airflow_m3h` | 0 / sim_data | «<U>: витрата повітря» | Витрата | gauge / м³/год | `{"object":"AI","instance":3}` (SupplyAirFlow) | 30 / 600; 0 | — | так | 0 |
| `supply` | `…/supply_c` | 0 / sim_data | «<U>: температура припливу» | Температура | gauge / °C | AI:1 (SupplyAirTemp) | 30 / 600; 1 | — | так | 0 |
| `filter` | `…/filter_dp_pa` | 0 / sim_data | «<U>: перепад на фільтрі припливу» | Перепад | gauge / Па | AI:4 (FreshAirFilterDp) | 30 / 600; 0 | `alarm_high=250`, `hysteresis=5`; «Заміна фільтрів: перепад тиску {value} Па при нормі до {threshold}» | так | 0 |
| `indoor` | `…/indoor_c` | 1 / catalog | «<U>: температура в зоні» | Температура | gauge / °C | AI:2 (ExtractAirTemp) | 30 / 600; 1 | — | так | 0 |
| `valve` | `…/heating_valve` | 1 / catalog | «<U>: клапан нагрівача» | Положення | gauge / % | AO:1 (HeatingValve) | 30 / 600; 0 | — | так | 0 |
| `mode` | `…/mode` | 1 / catalog | «<U>: режим роботи» | Режим | state / — | `{"object":"MSV","instance":1,"map":{"1":"VE","2":"VEL","3":"AQ","4":"REC","5":"EA","6":"SA","7":"ST","8":"Off"}}` | 30 / 3600; 0 | `states=["VE","VEL","AQ","REC","EA","SA","ST","Off"]`, `alarm_states=[]`, `create_request=False` | ні | 1 |
| `state` | `…/state` | 1 / catalog | «<U>: стан установки» | Стан | state / — | `{"object":"BI","instance":1,"states":[{"object":"BI","instance":2,"eq":1,"text":"fault"},{"object":"BI","instance":5,"eq":1,"text":"frost"},{"object":"BI","instance":1,"eq":1,"text":"running"},{"object":"BI","instance":1,"eq":0,"text":"stopped"}]}` | 30 / 3600; 0 | `states=["running","stopped","fault","frost"]`, `alarm_states=["fault","frost"]`; «{equipment}: аварія установки (стан «{text}»)» | ні | 0 |
| `filter_extract` | `…/filter_extract_dp_pa` | 1 / module | «<U>: перепад на фільтрі витяжки» | Перепад | gauge / Па | AI:5 (ExtractAirFilterDp) | 30 / 600; 0 | `alarm_high=350`, `hysteresis=10`; «Заміна фільтрів витяжки: перепад тиску {value} Па при нормі до {threshold}» | так | 0 |
| `heat` | `…/heat_kw` | 1 / module | «<U>: теплова потужність» | Потужність | gauge / кВт | AI:7 (HeatOutput) | 30 / 600; 1 | — | так | 0 |
| `power` | `…/p_now` | 1 / module | «<U>: потужність вентиляторів» | Потужність | gauge / кВт | AI:8 (FanPower) | 30 / 600; 2 | — | так | 0 |
| `sp_day` | `…/setpoint_day_c` | 1 / module | «<U>: уставка день» | Температура | gauge / °C | AV:1 (RoomSetpointDay) | 300 / 3600; 1 | — | так | 1 |
| `sp_night` | `…/setpoint_night_c` | 1 / module | «<U>: уставка ніч» | Температура | gauge / °C | AV:2 (RoomSetpointNight) | 300 / 3600; 1 | — | так | 1 |
| `check` | `…/check` | 1 / module | «<U>: перевірка роботи» | Перевірка | state / — | джерело `BMS-DERIVED`, `address={}` | 60 / 3600; 0 | `states` = 7 текстів R-23, `alarm_states=["не працює в робочий час","холодно в зоні"]`; «{equipment}: {text}» | ні | 0 |
| `pressure` (лише AHU-1) | `ventilation/units/AHU-1/room_pressure_pa` | 1 / module | «AHU-1: тиск у дільниці фасадів» | Тиск | gauge / Па | AI:9 (RoomPressure) | 30 / 600; 0 | `alarm_high=0`, `hysteresis=1`, `min_duration_s=300`; «Дільниця фасадів: тиск {value} Па при нормі до {threshold} (має бути розрідження)» | так | 0 |
| `interlock` (лише AHU-1) | `ventilation/units/AHU-1/booth_interlock` | 1 / module | «AHU-1: витяжка фарбувальних камер працює» | Стан | state / — | `{"object":"BI","instance":6,"map":{"0":"off","1":"on"}}` | 30 / 3600; 0 | `states=["off","on"]`, `create_request=False` | ні | 0 |

### B.2 Вентилятори (3 × 3 = 9), джерело `BAC-<d>-<U>`

| role | code | new / origin | name | kind / unit | address | period / store; dec. | пороги, стани, заголовок | vis. |
|---|---|---|---|---|---|---|---|---|
| `airflow` | `ventilation/units/<U>/airflow_m3h` | 0 / sim_data | «<U>: витрата повітря» | gauge / м³/год | AI:3 (AirFlow) | 30 / 600; 0 | — | так |
| `state` (EF-ELEC, EF-CMP) | `…/state` | 1 / catalog | «<U>: стан вентилятора» | state / — | `{"object":"BI","instance":1,"map":{"0":"stopped","1":"running"}}` | 30 / 3600; 0 | `states=["running","stopped"]`, `create_request=False` | ні |
| `state` (EF-CHG) | `ventilation/units/EF-CHG/state` | 1 / catalog | «EF-CHG: стан витяжки» | state / — | `{"object":"BI","instance":1,"states":[{"object":"BI","instance":1,"eq":1,"text":"running"},{"object":"BI","instance":7,"eq":1,"text":"stopped_charging"},{"object":"BI","instance":1,"eq":0,"text":"stopped"}]}` | 30 / 3600; 0 | `states=["running","stopped","stopped_charging"]`, `alarm_states=["stopped_charging"]`, `min_duration_s=60`; «{equipment}: не працює під час заряджання — водень!» | ні |
| `indoor` | `…/indoor_c` | 1 / module | «<U>: температура приміщення» | gauge / °C | AI:2 (RoomTemp) | 30 / 600; 0 | EF-ELEC: `alarm_high=35`, `hysteresis=1`, `min_duration_s=600`, «Електрощитова: температура {value} °C при нормі до {threshold}»; EF-CMP: `warn_high=35`; EF-CHG: — | так |

### B.3 Зовнішня температура й котельня (5)

| code | new / origin | джерело | name | kind / unit | address | period / store; dec. | пороги, стани, заголовок | vis. |
|---|---|---|---|---|---|---|---|---|
| `ventilation/totals/outdoor_c` | 1 / module | `BAC-101-RV-01` | «Зовнішня температура (RV-01)» | gauge / °C | AI:6 (RV-01_OutdoorTemp) | 60 / 900; 1 | — | так |
| `equipment/BOILER/return_c` | 1 / catalog | `BAC-140-BOILER` (telemetry) | «Котельня: температура зворотної води» | gauge / °C | AI:2 (BOILER_ReturnTemp) | 30 / 600; 1 | — | так |
| `equipment/BOILER/state` | 1 / catalog | `BAC-140-BOILER` | «Котельня: стан» | state / — | `{"object":"MSV","instance":1,"map":{"1":"standby","2":"K1","3":"K1+K2","4":"fault"}}` | 30 / 3600; 0 | `states=["standby","K1","K1+K2","fault"]`, `alarm_states=["fault"]`; «{equipment}: аварія котельні (стан «{text}»)» | ні |
| `equipment/BOILER/heat_kw` | 1 / module | `BAC-140-BOILER` | «Котельня: теплова потужність» | gauge / кВт | AI:5 (BOILER_HeatOutput) | 30 / 600; 1 | — | так |
| `ventilation/heat_plant/check` | 1 / module | `BMS-DERIVED` | «Котельня: перевірка теплового балансу» | state / — | `{}` | 60 / 3600; 0 | `states=["норма","дефіцит тепла","немає даних"]`, `alarm_states=["дефіцит тепла"]`; «Котельня: {text}» | ні |

### B.4 Групи освітлення (32 × 6 = 192), джерело `HN-LP-<r>`

| role | code | new / origin | name | quantity | kind / unit | address | period / store; dec. | пороги, стани, заголовок | vis. | writable |
|---|---|---|---|---|---|---|---|---|---|---|
| `level` | `lighting/groups/<G>/level` | 1 / catalog | «<G>: рівень освітлення» | Рівень | gauge / % | `{"group":<g>,"query":"level","devices":<devs>,"sample":3,"fade_s":2.0}` | 60 / 900; 0 | — | так | 1 |
| `power` | `…/p_now` | 1 / catalog | «<G>: потужність» | Потужність | gauge / кВт | `{"group":<g>,"query":"power","scale":0.001}` | 60 / 900; 2 | — | так | 0 |
| `faults` | `…/faults` | 1 / module | «<G>: несправних світильників» | Кількість | gauge / шт | `{"group":<g>,"query":"faults","devices":<devs>,"mask":134217742}` | 300 / 3600; 0 | `alarm_high=0`; «Аварія світильників {code}: несправних {value} шт. при нормі {threshold}» | так | 0 |
| `faulty` | `…/faulty` | 1 / module | «<G>: адреси несправних світильників» | Адреси | state / — | `{"group":<g>,"query":"faulty","devices":<devs>,"mask":134217742}` | 300 / 3600; 0 | `states=[]` (будь-який текст), `create_request=False` | ні | 0 |
| `scene` | `…/scene` | 1 / module | «<G>: остання сцена» | Сцена | gauge / — | `{"group":<g>,"query":"scene","block":1,"fade_s":2.0}` | 60 / 3600; 0 | — | так | 1 |
| `check` | `…/check` | 1 / module | «<G>: перевірка освітлення» | Перевірка | state / — | джерело `BMS-DERIVED`, `{}` | 60 / 3600; 0 | `states` = 6 текстів R-19, `alarm_states=["вимкнено в робочий час","нижче норми"]`; «{equipment}: {text}» | ні | 0 |

### B.5 Щити (3), джерело `HN-LP-<r>`

| code | new / origin | name | kind | address | period / store | стани | vis. |
|---|---|---|---|---|---|---|---|
| `lighting/panels/LP-<r>/state` | 1 / catalog | «LP-<r>: стан щита (роутер Imagine 950)» | state | `{"device":"@1.<r>.0.0","query":"router"}` (A-17; каталог iot_sim — C:110 `@1.<r>.1.1`) | 60 / 3600 | `states=["ok","fault","offline"]`, `create_request=False` | ні |

Підсумок: 549 = B.1 340 + B.2 9 + B.3 5 + B.4 192 + B.5 3; `new=0` — 81 (`airflow` 29, `supply` 26, `filter` 26);
`origin='catalog'` — 176 (`indoor`, `valve`, `mode`, `state` × 26; `state` EF × 3; `level`, `power` × 32; щити 3;
`BOILER` `return_c`, `state`); `origin='module'` — 292; `writable=1` — 142; на `BMS-DERIVED` — 59; BACnet — 327;
HelvarNet — 163.

## Додаток C. Джерела модуля (`data/td_bms_source_data.xml`; `collector_id = td_telemetry.collector_main`, `module='bms'`, `write_enabled=False`)

| xml-id | `code` | `type` | `name` | `params` | `period_s_default` |
|---|---|---|---|---|---|
| `source_hn_lp_1` | `HN-LP-1` | `helvarnet` | Helvar Imagine 950 · щит LP-1 | `{"host": "iot-sim", "port": 50000, "protocol": "tcp", "timeout_s": 3, "cluster": 1, "router": 1, "version": 2, "rate_per_s": 20, "push": true, "membership_ttl_s": 3600}` | 60 |
| `source_hn_lp_2` | `HN-LP-2` | `helvarnet` | Helvar Imagine 950 · щит LP-2 | те саме, `"router": 2` | 60 |
| `source_hn_lp_3` | `HN-LP-3` | `helvarnet` | Helvar Imagine 950 · щит LP-3 | те саме, `"router": 3` | 60 |
| `source_bac_101` … `source_bac_125` | `BAC-101-RV-01` … `BAC-125-RV-25` | `bacnet_ip` | Hoval RoofVent RV-NN (BACnet dev 1NN) | `{"host": "iot-sim", "port": 47808, "device": <d>, "network": 2, "timeout_s": 5, "rpm": true, "rpm_max": 50, "cov_lifetime_s": 300}` | 30 |
| `source_bac_130` | `BAC-130-AHU-1` | `bacnet_ip` | VTS VENTUS AHU-1 (BACnet dev 130) | те саме, `"device": 130` | 30 |
| `source_bac_131` | `BAC-131-EF-ELEC` | `bacnet_ip` | Вентилятори електрощитової EF-ELEC (dev 131) | `"device": 131` | 30 |
| `source_bac_132` | `BAC-132-EF-CMP` | `bacnet_ip` | Вентилятор компресорної EF-CMP (dev 132) | `"device": 132` | 30 |
| `source_bac_133` | `BAC-133-EF-CHG` | `bacnet_ip` | Витяжка зарядної EF-CHG (dev 133) | `"device": 133` | 30 |
| `source_bms_derived` (хук) | `BMS-DERIVED` | `f3d_bms` | Будівля: обчислені перевірки | `{}`, без колектора | 60 |

На проді `host` — IP контролера RoofVent/роутера Helvar (`params.address` — BACnet-адреса, якщо пристрій за
маршрутизатором), `network` — номер мережі BACnet об'єкта (Q-01, Q-02). Котельня — джерело telemetry `BAC-140-BOILER`
(telemetry Додаток C.1), модуль його не змінює.
