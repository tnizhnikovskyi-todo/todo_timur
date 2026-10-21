# td_machine_connect — специфікація

Версія 0.2 · 14.10.2026 (0.1 — 14.10.2026) · технічне рішення: `docs/modules/td_machine_connect/ARCHITECTURE.md` (далі ARCH:
FR-01…FR-36, CM-01…CM-09, A-01…A-30, Q-01…Q-17). Спирається на: каркас §5 (імена, стоп-крани, права), §6.4, §6.5,
§6.6 P-01…P-04, §6.7, §6.8, D-05, D-11; `td_factory3d` CB-01, CB-03, CB-05, CB-09, CB-10, Додаток B (коди
працівників); `td_telemetry` 19.0.1.1.0: CT-01 (M-01…M-06, M-11, M-13; M-06 `td.command.payload`/`result_data` —
CR-01, X-03), CT-02 (§8.3 інтерфейс плагіна, у т. ч. `SourcePlugin.call`), CT-03 (Додаток A:
`opcua`, `rest_vendor`, `modbus_tcp`), CT-04 (API-01…API-07; API-06 `payload`, API-07 `data`), CT-05 (R-05/R-06 заявки), CT-08 (`td.push.handler`),
CT-10 (`_td_ingest`), CT-12 (R-26 локальні типи), R-17 (Ingester), R-18 (команди); `td_viewer3d` M-01, M-03,
API-03, Додаток A.4/A.5/A.10/A.14; `td_iot_sim` §7.2 API-13 (тіло запуску `{"params": {…}}`), §8.3 (P-01), §8.4.2 (P-02), §8.5 (P-03, API-20…27), §8.6
(P-04, API-30…34), §9.1 R-14…R-18, §9.3 S-01, S-02, Додаток A (рядки 97, 98, 197–334).

Зміни: 14.10.2026 — правки за `docs/CONSISTENCY.md` v0.3: X-03 (команди — `td.command.payload` telemetry 19.0.1.1.0,
CR-01: схеми CMD-01…03 і результати `call()` — R-21, створення команд — M-20, §7.2, плагіни §8.3–§8.4, R-15…R-24;
текстова граматика R-21 лишається запасною; AC-50, 53, 54, 57, 58, 62, 63, 65, 74, 77…79, 101, нові AC-102, AC-103;
ТК-04, ТК-06, ТК-07, ТК-10; фікстура `cmd_done`),
X-16 (сигнали модуля — `origin='module'`, Додаток C.2, AC-83), X-18 (код команд оптимізатора `equipment/CUTOPT/cmd`
замість `mc/cutopt/cmd`), X-27 (`mc_state` — `viewer_visible=False`, AC-83), X-32 (пункт «Налаштування верстатів» під
`td_factory3d.menu_td_config`, sequence 40; AC-89), X-57 (ТК-02, ТК-08, ТК-12, ТК-14 — тіло запуску сценарію
`{"params": {…}}`), X-63 (плагін `opcua` не множить на `signal.scale` — R-22 п. 3), X-76 (`equipment/CUTOPT/cmd` і
`equipment/GANTRY-1/stacks` — у каталозі iot_sim `protocol=none`, Додаток C.2); §15 — закрито Q-09 (X-03), Q-16 (X-52),
Q-17 (X-38; ТК-15), Q-15 (X-34, X-38, X-43; X-92 — менеджер). X-93: створення команд (`_td_mc_create_command`,
`_td_mc_payload_supported`) винесено з `tools/commands.py` у `models/td_command.py` (M-20) — `tools/commands.py`
без імпортів Odoo, побайтово = `cmdtext.py` (§0, M-13, M-20, §7.2, §13.0.1 п. 9, AC-58, AC-80, AC-102, AC-103, §13.1, DoD).
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-01, Q-02, Q-03, Q-12, Q-14.
Зміни: 14.10.2026 — закрито відповідями замовника № 25–36 (прийнято рекомендації): Q-04…Q-08, Q-10, Q-11, Q-13.
Зміни: 15.10.2026 — DEC-19 (ТП-01): `_cron_tick` — id-порядок, пачки по 10 з commit, `FOR UPDATE SKIP LOCKED`; push блокує верстати за id; `raw_ts`/`pieces_ts` без інших змін — не частіше за раз на 30 с (§6 `cron_td_mc_tick`, R-04).
Зміни: 15.10.2026 — DEC-20 (ТБ-03): одноразовий токен API-01 — у заголовку `X-F3D-Token`, не в query `t` (§7 API-01, §8 `cutopt`, AC-66, AC-67, ТБ-03).
Зміни: 16.10.2026 — QA-фікси: API-01 п. 1 (M-1, AC-67) — Bearer приймається лише від колектора-власника джерела команд оптимізатора `equipment/CUTOPT/cmd` (REST-CUTOPT), токен іншого колектора → `401`; Додаток C.2 — `store_period_s = 300` для `io_state`, `io_alarm`, `ua_state`, `ua_mode`, `ua_alarm`, `ua_job`, `g_state`, `g_job` (зміни стану пишуться негайно, прорідження лише незмінних повторів).
Зміни: 20.10.2026 — вау-функція №19 «Портальний склад плит у 3D наживо» (R-31, AC-120…AC-126; 19.0.1.3.0): вузли `equipment.GANTRY-1.portal` і `locations[PLT-*].portal`, плитка «Портал», демо-історія порталу, міст 19.0.1.2.0; емулятор — авто-`feed` за РЦ у WORKING (td_iot_sim R-18).

Позначення: UT — `odoo.tests.TransactionCase`; HT — `HttpCase`; CT — pytest пакета плагінів із фейковими серверами;
TC — стенд (емулятор + колектор + Odoo); MAN — ручна перевірка на тестовому сервері timur-o19demo (база `odoo`).
Odoo 19: SQL-обмеження — `models.Constraint`, індекси — `models.Index`/`tools.sql.create_index`, хуки —
`post_init_hook(env)`/`uninstall_hook(env)`, `fields.Json`, `request.make_json_response`, команди —
`odoo.fields.Command`. Рядки UI — українською в коді (D-14). Усі `Datetime` — UTC naive; тексти для людей —
`Europe/Kyiv`. Усі імена в цьому документі остаточні.

## 0. Дерево файлів модуля

### 0.1 Odoo-модуль `odoo_addons/td_machine_connect`

```
odoo_addons/td_machine_connect/
├── __init__.py                      from . import models, wizard, controllers, tools; from .hooks import post_init_hook, uninstall_hook
├── __manifest__.py                  §1
├── hooks.py                         post_init_hook(env), uninstall_hook(env), run_migration(env) -> dict — §5.3, §5.4;
│                                    _csv_rows(env, name) -> list[dict], _signal_rows(code, protocol, io_unit, io_slot) -> list[dict] (§13.0.1)
├── README.md                        призначення, установка, параметри, інструкції ARCH §4
├── CHANGELOG.md                     19.0.1.0.0 — перший випуск
├── models/
│   ├── __init__.py                  порядок: td_machine, td_machine_downtime, td_machine_wo, td_machine_state_log, td_downtime,
│   │                                td_machine_event, td_machine_message, td_oee_shift, td_gantry_stack, td_gantry_job,
│   │                                td_cut_part, td_cut_map, mrp_workcenter, mrp_workorder, mrp_production,
│   │                                mrp_workcenter_productivity, product_template, td_signal, td_source, td_command,
│   │                                push_handler, viewer_provider, res_config_settings, stock_picking, maintenance_request
│   ├── td_machine.py               M-01: поля, R-01…R-04 (нормалізація, фіксація стану, журнал), диспетчер _td_dispatch
│   ├── td_machine_downtime.py      M-01 (_inherit = "td.machine"): R-05…R-08 простої, підказки, заявки (гачки _td_after_commit, _td_tick_extra)
│   ├── td_machine_wo.py            M-01 (_inherit = "td.machine"): R-09…R-12 автостарт/пауза/лічильник/завершення (ті самі гачки)
│   ├── td_machine_state_log.py     M-02
│   ├── td_downtime.py              M-03
│   ├── td_machine_event.py         M-04
│   ├── td_machine_message.py       M-05
│   ├── td_oee_shift.py             M-06 (+ R-14 крон)
│   ├── td_gantry_stack.py          M-07 (R-15, R-18)
│   ├── td_gantry_job.py            M-08 (R-16, R-17; _td_notify_portal — R-31 п. 8)
│   ├── td_portal.py                R-31: td.portal (AbstractModel) — вузли payload порталу й стосів, плитка «Портал»
│   ├── td_cut_part.py              M-09
│   ├── td_cut_map.py               M-10, M-11 (R-19, R-20)
│   ├── mrp_workcenter.py            M-12
│   ├── mrp_workorder.py             M-13
│   ├── mrp_production.py            M-14
│   ├── mrp_workcenter_productivity.py  M-15, M-16 (R-06 злиття)
│   ├── product_template.py          M-17
│   ├── td_signal.py                M-18 (_td_ingest, _mark_stale)
│   ├── td_source.py                M-19 (selection_add td_machine, _td_local_types)
│   ├── td_command.py               M-20: _td_mc_create_command, _td_mc_payload_supported (X-93), реакція на done/failed
│   ├── push_handler.py              M-21 td.push.handler.machine_connect (EV-01…EV-03)
│   ├── viewer_provider.py           M-22 td.viewer.provider.machines (R-25)
│   ├── res_config_settings.py       M-23
│   ├── stock_picking.py             M-27
│   └── maintenance_request.py       M-28 (R-08)
├── wizard/
│   ├── __init__.py
│   ├── downtime_reason_wizard.py    M-24
│   ├── downtime_reason_wizard_views.xml  V-09
│   ├── cut_plan_import_wizard.py    M-25
│   ├── cut_part_import_wizard.py    M-26
│   └── cut_wizard_views.xml         V-27, V-28
├── controllers/
│   ├── __init__.py
│   └── cutmap.py                    API-01
├── tools/
│   ├── __init__.py
│   ├── states.py                    normalize(protocol, raw: dict) -> str — R-01 (чиста функція)
│   ├── ppt.py                       ppt_intervals(env, workcenter, dt_from, dt_to) / clip / union — R-26
│   ├── oee.py                       compute_oee(inputs: dict) -> dict — R-13 (чиста функція)
│   ├── commands.py                  build_payload / check_payload / cmd_label / result_text / build_cmd / parse_cmd — R-21 (payload CR-01 і запасна текстова граматика; чисті функції без `env` і без імпортів Odoo; той самий модуль копіюється в пакет плагінів, AC-80)
│   ├── cutcsv.py                    build_parts_csv(lines) -> str / parse_plan(json) -> dict — R-19, R-20, Додаток D
│   ├── payload.py                   build_machines(env, ctx) -> dict — фрагмент payload переглядача (M-22, R-25; R-31 вузли порталу)
│   ├── portal.py                    day_start / to_sec / waste_weighted — R-31 (чисті функції)
│   ├── demo_portal.py               demo_gantry(env) — R-31 п. 8: демо-історія порталу (завдання, карти розкрою, показання стосів)
│   └── gen_mc_data.py               генератор data/mc_machines.csv і data/mc_signals.csv з Додатка A iot_sim (Odoo його не вантажить)
├── security/
│   ├── security.xml                 record rules §4.3
│   └── ir.model.access.csv          §4.1
├── data/
│   ├── ir_config_parameter.xml      §5.1 (noupdate="1")
│   ├── ir_sequence.xml              послідовності «ПОРТ/», «КР/» (noupdate="1")
│   ├── ir_cron.xml                  §6
│   ├── res_users.xml                технічний користувач user_td_machine (noupdate="1")
│   ├── mrp_loss_data.xml            loss_unknown «Не вказано» (noupdate="1")
│   ├── mc_sources.xml               22 джерела (noupdate="1"), Додаток C.1
│   ├── mc_machine_messages.xml      10 повідомлень OPC UA → причини (noupdate="1"), Додаток B
│   ├── mc_machines.csv              35 рядків (читає хук), Додаток A
│   ├── mc_signals.csv               шаблони 207 сигналів (читає хук), Додаток C.2
│   ├── td_actions.xml              ir.actions.server: «Повторити міграцію», «Підтвердити простої», «Перерахувати OEE»
│   └── neutralize.sql               §5.6
├── views/
│   ├── menus.xml                    V-30
│   ├── td_machine_views.xml        V-01…V-04
│   ├── td_machine_state_log_views.xml  V-05, V-06
│   ├── td_downtime_views.xml       V-07, V-08
│   ├── td_machine_event_views.xml  V-10, V-11, V-24
│   ├── td_oee_views.xml            V-12…V-14
│   ├── td_gantry_views.xml         V-15…V-19
│   ├── td_cut_views.xml            V-20…V-26
│   ├── mrp_workcenter_views.xml     V-29: форма РЦ, список журналу часу, форма причини втрат
│   ├── mrp_workorder_views.xml      V-26
│   ├── mrp_production_views.xml     V-25
│   ├── product_views.xml            V-29: розміри листа на формі товару
│   └── res_config_settings_views.xml  V-31
├── static/description/icon.png     іконка (верстат із шестернею; 140×140)
└── tests/
    ├── __init__.py
    ├── common.py                    F3DMachineCase(F3DTelemetryCase), F3DMachineHttpCase — фікстури §13.0
    ├── test_normalize.py            AC-01…AC-03
    ├── test_state_log.py            AC-04…AC-08
    ├── test_ppt.py                  AC-09, AC-10
    ├── test_downtime.py             AC-11…AC-16
    ├── test_merge_operator.py       AC-17…AC-20
    ├── test_hints.py                AC-21…AC-24
    ├── test_autostart.py            AC-25…AC-32, AC-101
    ├── test_counter_finish.py       AC-33…AC-38
    ├── test_oee.py                  AC-39…AC-44
    ├── test_energy_contract.py      AC-45, AC-46
    ├── test_gantry_stack.py         AC-47…AC-51
    ├── test_gantry_job.py           AC-52…AC-56
    ├── test_commands.py             AC-57, AC-58, AC-102
    ├── test_cutmap.py               AC-59…AC-65
    ├── test_api_export.py           AC-66…AC-68 (HttpCase)
    ├── test_migration.py            AC-81…AC-85
    ├── test_viewer_provider.py      AC-86…AC-88
    ├── test_security.py             AC-89…AC-91
    ├── test_hooks.py                AC-92
    ├── test_portal.py               AC-120…AC-124 (R-31)
    └── stand/                       ТК-01…ТК-16, ТП-01…ТП-04 (pytest -m stand; Odoo цей пакет не імпортує):
                                     conftest.py, helpers.py, test_tk01_install.py … test_tk16_shift_end.py,
                                     load_machines.py (ТП-01), data/parts_BR-K4.csv (Q-04)
```

### 0.2 Пакет плагінів колектора `services/collector_plugins/machine_connect`

```
services/collector_plugins/machine_connect/
├── README.md                        установка в образ колектора, env, адреси
├── pyproject.toml                   пакет f3d_collector_mc 0.1.0, Python 3.12; залежність f3d_collector (telemetry) >=0.1.0;
│                                    [project.entry-points."factory3d_collector.plugins"]
│                                    opcua = "f3d_collector_mc.opcua:OpcUaPlugin"
│                                    rest_vendor = "f3d_collector_mc.rest_vendor:RestVendorPlugin"
│                                    [project.entry-points."factory3d_collector.rest_vendors"]
│                                    woodstore = "f3d_collector_mc.woodstore:WoodStoreAdapter"
│                                    cutopt = "f3d_collector_mc.cutopt:CutOptAdapter"
│                                    generic = "f3d_collector_mc.generic:GenericAdapter"
├── requirements.txt                 asyncua==1.1.6, aiohttp==3.11.18 (як telemetry), cryptography==44.0.3
├── f3d_collector_mc/
│   ├── __init__.py                  __version__ = "0.1.0"
│   ├── opcua.py                     OpcUaPlugin (§8.3) — R-22
│   ├── ua_session.py                SessionPool: одна asyncua.Client на endpoint+безпеку; переп'єднання; NamespaceArray
│   ├── nodeids.py                   resolve(nodeid, ns_uri, ns_array) -> ua.NodeId; validate(nodeid)
│   ├── ua_values.py                 to_reading(signal, variant, ts) / jobs(JobOrderList) / event_payload(event)
│   ├── rest_vendor.py               RestVendorPlugin (§8.4) — адаптер за params.vendor
│   ├── woodstore.py                 WoodStoreAdapter (§8.5) — R-23
│   ├── cutopt.py                    CutOptAdapter (§8.6) — R-24
│   ├── generic.py                   GenericAdapter: GET path → json_path
│   ├── cmdtext.py                   копія odoo_addons/td_machine_connect/tools/commands.py (R-21; перевіряється тестом на ідентичність)
│   ├── events.py                    make_event(route, source_code, payload) -> PushEvent (event_id = sha256)
│   └── schemas/                     address.opcua.ext.json, params.opcua.ext.json, address.rest_vendor.ext.json, params.rest_vendor.ext.json
└── tests/
    ├── conftest.py                  фікстури §13.0.2: ua_server (asyncua Server у процесі), woodstore_app, cutopt_app (aiohttp), ctx (PluginContext-заглушка)
    ├── fakes/
    │   ├── opcua_server.py          мінімальний сервер: Machines/<C> з State/Machine/Overview, Flags, Values, JobManagement, Events
    │   ├── woodstore_app.py         aiohttp-застосунок API-20…27 у пам'яті
    │   └── cutopt_app.py            aiohttp-застосунок API-30…34 у пам'яті
    └── unit/
        ├── test_nodeids.py          AC-69
        ├── test_opcua_subscribe.py  AC-70, AC-71
        ├── test_opcua_events.py     AC-72
        ├── test_opcua_reconnect.py  AC-73
        ├── test_opcua_call.py       AC-74, AC-103
        ├── test_woodstore.py        AC-75…AC-77, AC-103
        ├── test_cutopt.py           AC-78, AC-79
        └── test_cmdtext.py          AC-80
```

## 1. Маніфест

```python
{
    "name": "Завод 3D: верстати",
    "summary": "Стани верстатів → журнал часу, автостарт завдань, простої з причинами, OEE; портал STORETEQ; карти розкрою",
    "description": "Підключення верстатів HOMAG (OPC UA, OPC 40550-1) і верстатів без інтерфейсу (I/O ADAM): нормалізовані "
                   "стани, журнал станів і простоїв, автостарт/пауза/завершення робочих завдань, OEE за фактом; портальний "
                   "склад плит HOMAG STORETEQ P-500 (стоси ↔ залишки, завдання порталу з МО); карти розкрою й програми "
                   "ЧПК з МО. Плагіни колектора opcua і rest_vendor — services/collector_plugins/machine_connect.",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_telemetry", "mrp_workorder"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_sequence.xml",
        "data/res_users.xml",
        "data/mrp_loss_data.xml",
        "data/mc_sources.xml",
        "data/mc_machine_messages.xml",
        "data/ir_cron.xml",
        "data/td_actions.xml",
        "wizard/downtime_reason_wizard_views.xml",
        "wizard/cut_wizard_views.xml",
        "views/td_machine_views.xml",
        "views/td_machine_state_log_views.xml",
        "views/td_downtime_views.xml",
        "views/td_machine_event_views.xml",
        "views/td_oee_views.xml",
        "views/td_gantry_views.xml",
        "views/td_cut_views.xml",
        "views/mrp_workcenter_views.xml",
        "views/mrp_workorder_views.xml",
        "views/mrp_production_views.xml",
        "views/product_views.xml",
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

Порядок `data`: групи/правила → доступи → параметри → послідовності → технічний користувач (посилається на групи) →
причина «Не вказано» → джерела (посилаються на `td_telemetry.collector_main`) → довідник повідомлень (посилається
на причини) → крони (посилаються на технічні методи) → дії → майстри → представлення → меню. `mc_machines.csv` і
`mc_signals.csv` у `data` не перелічені — їх читає хук через `odoo.tools.file_open` (як `scene_*.csv` у base).
Зовнішніх Python-залежностей в Odoo-модулі немає: OPC UA і HTTP до пристроїв — лише в колекторі.
`mrp_workorder` дає `start_employee`/`stop_employee`, `employee_ids`, планшет «Цех»; `td_telemetry` — усе
інше (через нього `td_factory3d`, `maintenance`, `mail`, `mrp`, `stock`, `hr`).
Модуль розрахований на `td_telemetry` 19.0.1.1.0 (CR-01, X-03: `td.command.payload`/`result_data`, API-06
`payload`, API-07 `data`, `SourcePlugin.call`); з telemetry без поля `payload` команди йдуть запасною текстовою
граматикою R-21 (M-20 `_td_mc_payload_supported`). Власна версія модуля — `19.0.1.0.0` (перший випуск).

## 2. Моделі

Спільні позначення: `req` = `required=True`; `idx` = `index=True`; `ro` = `readonly=True`; усі `_description`
українською. Спільні константи — у `models/td_machine.py` (імпортують інші файли):

```python
STATES = [("working", "В роботі"), ("setup", "Налагодження"), ("idle", "Очікування"),
          ("fault", "Аварія"), ("off", "Вимкнено"), ("nodata", "Немає даних")]
DOWN_STATES = ("setup", "idle", "fault", "off")             # стани, що дають простій
PROTOCOLS = [("opcua", "OPC UA (OPC 40550-1)"), ("io", "Модуль вводу (ADAM, Modbus TCP)"), ("manual", "Без підключення")]
AUTO_MODES = [("off", "Вимкнено"), ("job", "Лише за завданням верстата"), ("job_or_single", "За завданням або єдиним у черзі")]
SIG_ROLES = ("state", "mode", "alarm", "pieces", "job", "event")
P = "td.machine_connect."                              # префікс параметрів
def param(env, key, default): return env["ir.config_parameter"].sudo().get_param(P + key, default)
def param_bool(env, key, default="False"): return param(env, key, default) in ("True", "true", "1")
```

Умовчання стоп-кранів при відсутньому параметрі: `read_enabled` = (`td.base.environment` == `test`),
`auto_start_enabled` = `False`, `write_enabled` = `False` (CB-10).

### M-01 `td.machine` — верстат (підключення й живий стан) (CM-01, A-01)

```python
class F3dMachine(models.Model):
    _name = "td.machine"
    _description = "Верстати: підключення верстата"
    _inherit = ["mail.thread"]
    _order = "code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `workcenter_id` | Many2one `mrp.workcenter` | `req`, `idx`, `ondelete="cascade"`, `string="Робочий центр"`, `tracking=True` |
| `name` | Char | `related="workcenter_id.name"`, `store=True`, `string="Назва"` |
| `code` | Char | `related="workcenter_id.td_code"`, `store=True`, `idx`, `string="Код"` |
| `zone_id` | Many2one `td.zone` | `related="workcenter_id.td_zone_id"`, `store=True`, `string="Зона"` |
| `company_id` | Many2one `res.company` | `related="workcenter_id.company_id"`, `store=True`, `idx` |
| `equipment_id` | Many2one `maintenance.equipment` | `ondelete="set null"`, `string="Обладнання"` (за `td_code` = `code`; заявки ТО, паспорт) |
| `active` | Boolean | `default=True` |
| `protocol` | Selection `PROTOCOLS` | `req`, `default="opcua"`, `string="Підключення"`, `tracking=True` |
| `source_id` | Many2one `td.source` | `ondelete="set null"`, `string="Джерело"` (`UA-<код>` або `MB-U8x-IOy`) |
| `io_slot` | Integer | `string="Позиція в модулі I/O"`, `help="m = 0…4: DI(2m) — в роботі, DI(2m+1) — аварія, лічильник DI(2m)"`; лише для `io` |
| `sig_state_id` | Many2one `td.signal` | `ondelete="set null"`, `string="Сигнал стану"` (`workcenters/<код>/state`) |
| `sig_mode_id` | Many2one `td.signal` | `string="Сигнал режиму"` (`…/mode`, лише OPC UA) |
| `sig_alarm_id` | Many2one `td.signal` | `string="Сигнал тривоги"` (`…/alarm`) |
| `sig_pieces_id` | Many2one `td.signal` | `string="Лічильник деталей"` (`…/pieces_out`) |
| `sig_job_id` | Many2one `td.signal` | `string="Сигнал завдання"` (`…/job`, лише OPC UA) |
| `sig_event_id` | Many2one `td.signal` | `string="Сигнал подій"` (`…/event`, лише OPC UA) |
| `sig_machine_state_id` | Many2one `td.signal` | `string="Обчислений стан"` (`…/machine_state`, джерело `MC-DERIVED`) |
| `sig_job_cmd_id` | Many2one `td.signal` | `string="Команди завдань"` (`…/job_cmd`, лише OPC UA) |
| `read_enabled` | Boolean | `default=True`, `string="Читати"`, `tracking=True` |
| `auto_start_mode` | Selection `AUTO_MODES` | `req`, `default="job_or_single"`, `string="Автостарт"`, `tracking=True` |
| `auto_finish` | Boolean | `default=True`, `string="Автозавершення"`, `tracking=True` |
| `auto_pause` | Boolean | `default=True`, `string="Автопауза"`, `tracking=True` |
| `micro_stop_s` | Integer | `default=lambda s: int(param(s.env, "micro_stop_s", "120"))`, `string="Мікрозупинка до, с"` |
| `pause_after_min` | Integer | `default=lambda s: int(param(s.env, "pause_after_min", "10"))`, `string="Пауза завдання після, хв"` |
| `finish_idle_s` | Integer | `default=lambda s: int(param(s.env, "finish_idle_s", "60"))`, `string="Завершення після зупинки, с"` |
| `employee_id` | Many2one `hr.employee` | `ondelete="set null"`, `string="Працівник для автостарту"`, `help="Якщо немає поточного й оператора OP-<код>"` |
| `state` | Selection `STATES` | `default="nodata"`, `req`, `idx`, `ro`, `string="Стан"` (без `tracking` — журнал змін веде M-02) |
| `state_since` | Datetime | `ro`, `string="Стан з"` |
| `raw_state` | Char(16) | `ro`, `string="Стан верстата (сирий)"` — `WORKING`, `READY`… або `run`/`stop` (I/O) |
| `raw_mode` | Char(16) | `ro`, `string="Режим (сирий)"` — `AUTOMATIC`, `SETUP`… |
| `raw_alarm` | Boolean | `ro`, `string="Тривога"` |
| `raw_job` | Char(64) | `ro`, `string="Завдання на верстаті"` — `JobOrderID` |
| `raw_ts` | Datetime | `ro`, `string="Останнє показання"` |
| `pending_state` | Selection `STATES` | службове (R-02) |
| `pending_since` | Datetime | службове (R-02) |
| `pieces_last` | Float | `ro`, `string="Лічильник (останнє)"` |
| `pieces_ts` | Datetime | `ro` |
| `current_log_id` | Many2one `td.machine.state.log` | `ro`, `ondelete="set null"` |
| `current_downtime_id` | Many2one `td.downtime` | `ro`, `ondelete="set null"`, `string="Поточний простій"` |
| `active_workorder_id` | Many2one `mrp.workorder` | `ro`, `ondelete="set null"`, `string="Активне завдання"` |
| `wo_paused` | Boolean | службове: таймер `active_workorder_id` закрив верстат (R-10) |
| `last_autostart_key` | Char(64) | службове (R-09 п. 7) |
| `no_job_since` | Datetime | службове: верстат працює без завдання з (R-09 п. 9) |
| `no_job_notified` | Boolean | службове |
| `oee_shift_id` | Many2one `td.oee.shift` | `ro`, `ondelete="set null"`, `string="OEE поточної зміни"` |
| `oee_today` | Float | `related="oee_shift_id.oee"`, `string="OEE зміни"` |
| `availability_today`, `performance_today`, `quality_today` | Float | `related="oee_shift_id.availability/performance/quality"` |
| `downtime_open_min` | Float | `compute="_compute_live"` (не зберігається): `(now − current_downtime_id.date_start)/60`, 0 якщо немає |
| `queue_ready_count` | Integer | `compute="_compute_live"`: `mrp.workorder.search_count([('workcenter_id','=',wc),('state','=','ready')])` |
| `color` | Integer | `compute="_compute_live"`: `working` 10, `setup` 4, `idle` 3, `fault` 1, `off` 0, `nodata` 0 (kanban) |
| `note` | Text | `string="Примітка"` |

```python
    _f3d_machine_wc_uniq = models.Constraint("UNIQUE(workcenter_id)", "Для робочого центру вже є запис підключення.")
    _f3d_machine_thresholds = models.Constraint(
        "CHECK(micro_stop_s >= 0 AND pause_after_min >= 1 AND finish_idle_s >= 0)",
        "Пороги верстата: мікрозупинка ≥ 0 с, пауза ≥ 1 хв, завершення ≥ 0 с.")
```

`@api.constrains("protocol", "sig_state_id", "sig_job_id", "auto_start_mode", "sig_mode_id", "sig_alarm_id",
"sig_pieces_id", "sig_event_id", "sig_machine_state_id", "sig_job_cmd_id")` `_check_f3d_signals`:
1. `protocol != 'manual'` і немає `sig_state_id` → `ValidationError("Для підключеного верстата задайте сигнал стану.")`;
2. кожен заданий `sig_*` (крім `sig_machine_state_id`) має `code` з префіксом `f"workcenters/{code}/"` →
   інакше `"Сигнал %s не належить верстату %s."`;
3. `sig_machine_state_id` — джерело типу `td_machine` → інакше `"Обчислений стан має бути на джерелі MC-DERIVED."`;
4. `auto_start_mode == 'job'` і (`protocol != 'opcua'` або немає `sig_job_id`) → `"Режим «Лише за завданням» потребує сигналу завдання (OPC UA)."`;
5. `protocol == 'io'` і `io_slot` поза 0…4 → `"Позиція в модулі I/O: 0…4."`.

`create`/`write`/`unlink`: після `super()` — `self.env.registry.clear_cache()` (скидає `_td_code_map`), якщо в `vals`
є будь-яке `sig_*`, `active`, `read_enabled`; зміна `auto_start_mode`/`read_enabled` — повідомлення в чатер (tracking).

Методи (алгоритми — §9):

| Сигнатура | Призначення |
|---|---|
| `@api.model @tools.ormcache() _td_code_map(self) -> dict` | `{signal_code: (machine_id, role)}` для активних верстатів: ролі `state`, `mode`, `alarm`, `pieces`, `job`, `event` з полів `sig_*` (один `search_read`) |
| `@api.model _td_dispatch(self, readings: list[dict], src: str) -> dict` | вхід із M-18 після `super()._td_ingest`: R-04 п. 0; повертає `{"machines": n, "transitions": n, "autostarts": n, "finished": n, "errors": [..]}` |
| `_td_lock(self)` | `self.env.cr.execute("SELECT id FROM td_machine WHERE id IN %s FOR UPDATE", (tuple(self.ids),))` — до будь-якої зміни стану (R-09 п. 7) |
| `_td_apply(self, items: list[dict])` | `ensure_one()`; R-01, R-02, R-11 для показань одного верстата (відсортовані за `ts`) |
| `_td_on_raw_state(self, new: str, ts: datetime)` | R-02 (мікрозупинка, відкладений перехід) |
| `_td_commit_state(self, new: str, ts: datetime, cause: str = "machine")` | R-04: закрити інтервал, відкрити новий, R-05 (простій), R-10 (пауза/відновлення), R-09 (автостарт), сигнал `machine_state`, шина |
| `_td_mark_nodata(self, ts: datetime, reason: str)` | R-03 |
| `_td_emit_state(self, ts: datetime)` | `self.env["td.signal"].with_context(f3d_mc_internal=True)._td_ingest([{"code": sig_machine_state_id.code, "ts": ts, "text": state, "q": "good"}], src="module")` (CT-10) |
| `_td_notify(self, kinds=("state",))` | якщо `'td.viewer.event' in self.env`: `self.env['td.viewer.event']._notify('mrp.workcenter', self.mapped('code'), 'state')` |
| `@api.model _cron_tick(self)` | тут — R-02 п. 4 (відкладені переходи), R-03 п. 3, стан `MC-DERIVED`; далі для кожного верстата `_td_tick_extra(now)`: R-10 п. 2 (пауза за часом), R-12 п. 3 (завершення I/O), R-05 п. 6 (межа планового часу), R-06 п. 3/5, R-09 п. 9 (без завдання); ≤ 35 верстатів, ≤ 10 с |
| `@api.model _td_wo_intervals(self, workorders, date_from=None, date_to=None) -> dict` | CM-03, R-28 |
| `@api.model _td_wc_intervals(self, workcenter, date_from, date_to) -> list` | CM-03, R-28 |
| `_td_oee(self, date_from, date_to) -> dict` | CM-04, R-13 |
| `action_test_connection(self)` | `display_notification`: «Джерело <код>: <стан>; стан <raw_state>/<raw_mode>, тривога <так/ні>, лічильник <n>, завдання <raw_job>; останнє показання <час Київ>» |
| `action_view_logs(self)` / `action_view_downtimes(self)` / `action_view_oee(self)` | `act_window` на M-02 / M-03 / M-06 з `domain=[('machine_id','=',id)]` |
| `action_open_workcenter(self)` | форма `mrp.workcenter` |
| `action_f3d_show(self)` | `self.workcenter_id.action_f3d_show()` (CB-02) |
| `action_reset_state(self)` | лише `group_td_admin` (`AccessError`): `_td_lock()`, закрити `current_log_id`/`current_downtime_id` о `now`, `state='nodata'`, чатер «Стан скинуто адміністратором» |

Гачки між файлами (кожне перевизначення викликає `super()` першим): `_td_after_commit(self, old: str, new: str, ts:
datetime)` — після фіксації переходу (R-04 п. 4; у `td_machine.py` порожній); `_td_tick_extra(self, now: datetime)` —
частина `_cron_tick` для кожного верстата з `read_enabled`; `_td_on_count(self, delta: float, ts: datetime)` — після
R-11 п. 1–3; `_td_on_job(self, text: str, ts: datetime)` — зміна `raw_job`; `_td_apply_event(self, payload: dict)`
(`@api.model`, EV-01 з M-21). Базові реалізації в `models/td_machine.py`: `_td_count(value, ts)` — R-11 п. 1–3, потім
`_td_on_count(delta, ts)`; `_td_on_job` — пише `raw_job`; `_td_apply_event` — знаходить верстат за `machine`
(немає → `ValueError`), решта — у файлах нижче.

У `models/td_machine_downtime.py` (`_inherit = "td.machine"`): `_td_open_downtime(kind, ts)`, `_td_close_downtime(ts)`
(R-05), `_td_hint(kind, ts) -> tuple[loss, str, event]` (R-07), `_td_apply_event` (R-07 п. 1, R-08 п. 3); гачки:
`_td_after_commit` — R-05 п. 1–4, R-08 п. 2; `_td_tick_extra` — R-05 п. 6, R-06 п. 3 і 5.
У `models/td_machine_wo.py` (`_inherit = "td.machine"`): `_td_match_job(text) -> mrp.workorder` (R-09 п. 1),
`_td_candidate(ts) -> mrp.workorder` (R-09 п. 2), `_td_pick_employee(wo) -> hr.employee` (R-09 п. 4),
`_td_autostart(ts)` (R-09), `_td_autopause(ts, reason)`, `_td_resume(ts)` (R-10), `_td_try_finish(ts, trigger)`
(R-12); гачки: `_td_on_count` — R-11 п. 4–5; `_td_on_job` — R-09 п. 8, R-12 п. 1;
`_td_after_commit` — R-10, R-09, R-12 п. 2; `_td_tick_extra` — R-10 п. 2, R-12 п. 3, R-09 п. 9; `_td_apply_event` —
R-12 п. 1 (`I0002`). У `models/td_machine.py`: `_td_tech_env()` →
`self.env(user=self.env.ref("td_machine_connect.user_td_machine").id, su=False)` з `context={"tz": "Europe/Kyiv",
"f3d_mc_auto": True}`.

### M-02 `td.machine.state.log` — інтервал стану (журнал часу верстата) (CM-01, CM-03)

```python
class F3dMachineStateLog(models.Model):
    _name = "td.machine.state.log"
    _description = "Верстати: інтервал стану"
    _order = "date_start desc, id desc"
```

| Поле | Тип | Параметри |
|---|---|---|
| `machine_id` | Many2one `td.machine` | `req`, `idx`, `ondelete="cascade"`, `string="Верстат"` |
| `workcenter_id` | Many2one `mrp.workcenter` | `related="machine_id.workcenter_id"`, `store=True`, `idx` |
| `code` | Char | `related="machine_id.code"`, `store=True` |
| `state` | Selection `STATES` | `req`, `idx`, `string="Стан"` |
| `date_start` | Datetime | `req`, `idx`, `string="Початок"` |
| `date_end` | Datetime | `idx`, `string="Кінець"` (порожньо — триває) |
| `duration_min` | Float | `compute="_compute_duration"`, `store=True`, `digits=(12, 2)`, `string="Хв"`: `(date_end − date_start).total_seconds()/60`, відкритий — 0 |
| `workorder_id` | Many2one `mrp.workorder` | `ondelete="set null"`, `idx`, `string="Завдання"` (активне на момент відкриття або старту) |
| `production_id` | Many2one `mrp.production` | `related="workorder_id.production_id"`, `store=True` |
| `employee_id` | Many2one `hr.employee` | `ondelete="set null"`, `string="Працівник"` |
| `downtime_id` | Many2one `td.downtime` | `ondelete="set null"`, `string="Простій"` |
| `source` | Selection | `[('machine','Верстат'),('operator','Оператор'),('system','Система')]`, `default='machine'`, `req` |
| `raw` | Char(64) | `string="Сирий стан"` — `"WORKING/AUTOMATIC"`, `"run/alarm=0"` |
| `pieces_start` | Float | `string="Лічильник на початку"` |
| `pieces` | Float | `default=0`, `string="Деталей"` — приріст лічильника за інтервал (R-11) |
| `in_ppt_min` | Float | `digits=(12, 2)`, `string="У плановому часі, хв"` — ставиться при закритті (R-04 п. 3) |

```python
    _f3d_log_dates = models.Constraint("CHECK(date_end IS NULL OR date_end >= date_start)", "Кінець інтервалу раніше за початок.")
    _f3d_log_machine_start_idx = models.Index("(machine_id, date_start)")

    def init(self):
        self.env.cr.execute("CREATE UNIQUE INDEX IF NOT EXISTS td_machine_state_log_open_uniq "
                            "ON td_machine_state_log (machine_id) WHERE date_end IS NULL")
```

Методи: `_td_close(self, ts)` — `date_end = max(ts, date_start)`, `in_ppt_min` (R-04 п. 3), повторний виклик на закритому —
нічого; `_compute_display_name` — `"%s · %s · %s–%s" % (code, label(state), local(date_start, '%H:%M'), local(date_end,
'%H:%M') або '…')`; `unlink` — лише `group_td_admin` (`AccessError("Журнал станів видаляє лише адміністратор.")`);
`write` полів `state`, `date_start`, `machine_id` — лише `env.su` або адміністратор (`AccessError`). Форми — лише читання.

### M-03 `td.downtime` — простій (CM-01, A-06)

```python
class F3dDowntime(models.Model):
    _name = "td.downtime"
    _description = "Верстати: простій"
    _inherit = ["mail.thread"]
    _order = "date_start desc, id desc"
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | `compute="_compute_name"`, `store=True`: `"%s · %s" % (code, local(date_start, "%d.%m %H:%M"))` |
| `machine_id` | Many2one `td.machine` | `req`, `idx`, `ondelete="cascade"`, `string="Верстат"` |
| `workcenter_id` | Many2one `mrp.workcenter` | `related="machine_id.workcenter_id"`, `store=True`, `idx` |
| `code` | Char | `related="machine_id.code"`, `store=True` |
| `company_id` | Many2one `res.company` | `related="machine_id.company_id"`, `store=True`, `idx` |
| `date_start` | Datetime | `req`, `idx`, `string="Початок"`, `tracking=True` |
| `date_end` | Datetime | `idx`, `string="Кінець"`, `tracking=True` |
| `is_open` | Boolean | `compute="_compute_open"`, `store=True`, `idx`, `string="Триває"` = `not date_end` |
| `duration_min` | Float | `compute="_compute_duration"`, `store=True`, `digits=(12,1)`, `string="Тривалість, хв"` (відкритий — 0) |
| `duration_live` | Float | `compute="_compute_live"` (не зберігається): відкритий — `(now − date_start)/60`, інакше `duration_min` |
| `ppt_min` | Float | `digits=(12,1)`, `string="У плановому часі, хв"` (R-05 п. 5) |
| `state_kind` | Selection | `[('fault','Аварія'),('setup','Налагодження'),('idle','Очікування'),('off','Вимкнено')]`, `req`, `string="Стан верстата"` |
| `loss_id` | Many2one `mrp.workcenter.productivity.loss` | `req`, `ondelete="restrict"`, `string="Причина"`, `tracking=True`, `domain="[('loss_type','in',('availability','quality'))]"`, `default=lambda s: s.env.ref("td_machine_connect.loss_unknown")` |
| `loss_type` | Selection | `related="loss_id.loss_type"` |
| `planned` | Boolean | `related="loss_id.td_planned"`, `string="Плановий"` |
| `reason_source` | Selection | `[('auto','Автоматично'),('hint','Підказка верстата'),('operator','Оператор'),('master','Майстер'),('demo','Демо-дані')]`, `req`, `default='auto'`, `string="Хто вказав"`, `tracking=True` |
| `reason_state` | Selection | `[('to_classify','Потребує причини'),('to_confirm','Потребує підтвердження'),('confirmed','Підтверджено')]`, `req`, `idx`, `default='to_classify'`, `string="Класифікація"`, `tracking=True` |
| `hint_loss_id` | Many2one `mrp.workcenter.productivity.loss` | `ondelete="set null"`, `string="Підказка"` |
| `hint_text` | Char(256) | `string="Звідки підказка"` (`"E0421 Помилка шпинделя осі Z"`, `"Режим SETUP"`, `"WH/MO/00245: чекає компонентів"`) |
| `event_id` | Many2one `td.machine.event` | `ondelete="set null"`, `string="Подія верстата"` |
| `workorder_id` | Many2one `mrp.workorder` | `ondelete="set null"`, `string="Завдання"` |
| `production_id` | Many2one `mrp.production` | `related="workorder_id.production_id"`, `store=True` |
| `employee_id` | Many2one `hr.employee` | `ondelete="set null"`, `string="Працівник (причина)"` |
| `reason_user_id` | Many2one `res.users` | `ro`, `string="Причину вказав"` |
| `reason_at` | Datetime | `ro` |
| `confirmed_by` | Many2one `res.users` | `ro`, `string="Підтвердив"` |
| `confirmed_at` | Datetime | `ro` |
| `productivity_ids` | One2many `mrp.workcenter.productivity` `td_downtime_id` | `string="Записи журналу часу"` |
| `maintenance_request_id` | Many2one `maintenance.request` | `ondelete="set null"`, `string="Заявка ТО"` |
| `note` | Text | `string="Примітка"` |
| `has_loss_tool` | Boolean | `compute` (не зберігається): `bool(self.env.ref('factory3d.loss_tool', raise_if_not_found=False))` — для кнопки kanban «Заміна інструменту» |

```python
    _f3d_downtime_dates = models.Constraint("CHECK(date_end IS NULL OR date_end >= date_start)", "Кінець простою раніше за початок.")
    def init(self):
        self.env.cr.execute("CREATE UNIQUE INDEX IF NOT EXISTS td_downtime_open_uniq ON td_downtime (machine_id) "
                            "WHERE date_end IS NULL")
```

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `action_set_reason(self, loss_id: int, employee_id: int = None, source: str = None)` | права: `mrp.group_mrp_user` (`AccessError`); `confirmed` і користувач без `mrp.group_mrp_manager` → `UserError("Простій підтверджено — змінити причину може майстер.")`; `loss` не availability/quality → `UserError("Причина має бути втратою доступності або якості.")`; `src = source or ('master' if has_group('mrp.group_mrp_manager') else 'operator')`; `_td_apply_reason(loss, src, employee)`; `reason_state = 'confirmed' if src == 'master' else 'to_confirm'` |
| `action_confirm(self)` | права `mrp.group_mrp_manager`; для кожного: `loss_id == loss_unknown` → `UserError("Спершу вкажіть причину простою %s.")`; `reason_state='confirmed'`, `confirmed_by`, `confirmed_at=now`; повертає `True` (серверна дія «Підтвердити простої» викликає для виділених) |
| `action_open_reason_wizard(self)` | `act_window` M-24 `target='new'`, `context={'default_downtime_id': id}` |
| `_td_apply_reason(self, loss, source, employee=None)` | `write({'loss_id': loss.id, 'reason_source': source, 'employee_id': employee.id or False, 'reason_user_id': env.uid, 'reason_at': now})`; усім `productivity_ids` із `td_auto=True` → `loss_id = loss.id` (через `sudo()`; записи оператора не змінюються); чатер «Причина: <назва> (<хто>)» |
| `_td_close(self, ts)` | R-05 п. 4 |
| `write(self, vals)` | `loss_id` у `vals` без контексту `f3d_mc_internal` → перевірки `action_set_reason` (права, `confirmed`); далі `super()` |
| `unlink(self)` | лише `group_td_admin` (`AccessError("Простій видаляє лише адміністратор.")`) |

### M-04 `td.machine.event` — подія верстата OPC UA (CM-01, A-27)

`_name = "td.machine.event"`, `_description = "Верстати: подія верстата"`, `_order = "ts desc, id desc"`.

| Поле | Тип | Параметри |
|---|---|---|
| `machine_id` | Many2one `td.machine` | `req`, `idx`, `ondelete="cascade"` |
| `workcenter_id` | Many2one | `related="machine_id.workcenter_id"`, `store=True` |
| `ts` | Datetime | `req`, `idx`, `string="Час"` (`Time` події, UTC) |
| `kind` | Selection | `[('event','Подія'),('alarm','Тривога')]`, `req` (`WwBaseEventType` / `WwAlarmConditionType`) |
| `message_id` | Char(16) | `idx`, `string="Код"` (`E0421`) |
| `message_name` | Char(64) | `string="Назва"` (`SpindleOverload`) |
| `category` | Selection | `[('0','Інше'),('1','Діагностика'),('2','Інформація'),('3','Попередження'),('4','Тривога'),('5','Помилка')]`, `req`, `string="Категорія"` (`WwEventCategoryEnumeration`) |
| `severity` | Integer | `string="Важливість"` (1…1000) |
| `text` | Char(256) | `string="Текст"` (перше з `LocalizedMessages` з `locale` `uk`, інакше перше) |
| `path` | Char(256) | `string="Вузол"` (`PathParts` через « / ») |
| `active` | Boolean | `default=True`, `string="Активна"` (`ActiveState` для тривоги; для події — `True`) |
| `acked` | Boolean | `string="Квитовано"` |
| `ext_event_id` | Char(64) | `req`, `idx`, `string="Ідентифікатор події"` (= `event_id` telemetry M-13) |
| `payload` | Json | `string="Дані"` (EV-01 цілком) |
| `message_rec_id` | Many2one `td.machine.message` | `compute="_compute_message_rec"`, `store=True` — `td.machine.message._td_match(message_id)` |
| `downtime_id` | Many2one `td.downtime` | `ondelete="set null"` |

`_f3d_machine_event_uniq = models.Constraint("UNIQUE(ext_event_id)", "Подія вже записана.")`. Ротація — крон R-14 п. 6
(`keep_event_days`). У формах — лише читання.

### M-05 `td.machine.message` — довідник повідомлень верстата → причина (CM-01)

`_name = "td.machine.message"`, `_description = "Верстати: повідомлення верстата"`, `_order = "sequence, message_id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `message_id` | Char(16) | `req`, `idx`, `string="Код"`; точний (`E0421`) або префікс із `*` у кінці (`E04*`); `^[A-Z0-9]{1,15}\*?$` |
| `name` | Char(128) | `req`, `string="Текст"` |
| `category` | Selection | як M-04, `string="Категорія"` (довідково) |
| `loss_id` | Many2one `mrp.workcenter.productivity.loss` | `req`, `ondelete="restrict"`, `string="Причина"`, `domain="[('loss_type','in',('availability','quality'))]"` |
| `auto_apply` | Boolean | `default=True`, `string="Ставити причиною автоматично"` |
| `sequence` | Integer | `default=10` |
| `active` | Boolean | `default=True` |

`_f3d_message_uniq = models.Constraint("UNIQUE(message_id)", "Код повідомлення повторюється.")`; `@api.constrains("message_id")`
— регекс → `"Код повідомлення: латиниця й цифри, ≤ 15, необов'язкова * у кінці."`. Метод `@api.model _td_match(self,
message_id) -> record`: порожній → порожньо; точний збіг активного; інакше записи з `*`, для яких `message_id.startswith(
pattern[:-1])`, — найдовший префікс; інакше порожньо. Дані — Додаток B.

### M-06 `td.oee.shift` — OEE верстата за зміну (CM-04, A-07, A-08)

`_name = "td.oee.shift"`, `_description = "Верстати: OEE за зміну"`, `_order = "date desc, code"`.

| Поле | Тип | Параметри |
|---|---|---|
| `machine_id` | Many2one `td.machine` | `req`, `idx`, `ondelete="cascade"` |
| `workcenter_id` | Many2one | `related="machine_id.workcenter_id"`, `store=True`, `idx` |
| `code` | Char | `related="machine_id.code"`, `store=True` |
| `zone_id` | Many2one | `related="machine_id.zone_id"`, `store=True` |
| `company_id` | Many2one | `related="machine_id.company_id"`, `store=True` |
| `date` | Date | `req`, `idx`, `string="Дата зміни"` (за Києвом) |
| `date_start`, `date_end` | Datetime | `string="Початок/кінець зміни"` (перший початок і останній кінець інтервалів календаря дати, UTC) |
| `state` | Selection | `[('open','Поточна'),('closed','Закрита')]`, `req`, `default='open'` |
| `source` | Selection | `[('machine','Журнал станів'),('timelog','Журнал часу Odoo')]`, `req` (R-13 п. 2) |
| `ppt_min` | Float | `digits=(12,1)`, `string="Плановий час, хв"` (уже без планових простоїв і «немає даних») |
| `planned_stop_min`, `nodata_min` | Float | `digits=(12,1)` |
| `run_min`, `run_wo_min`, `setup_min`, `fault_min`, `idle_min`, `off_min`, `unexplained_min`, `down_min` | Float | `digits=(12,1)`; `down_min = setup + fault + idle + off` у межах планового часу |
| `ideal_min` | Float | `digits=(12,1)`, `string="Ідеальний час, хв"` = Σ ідеальний цикл × к-сть |
| `qty_total`, `qty_bad`, `qty_good` | Float | `digits=(12,1)` |
| `availability`, `performance`, `performance_raw`, `quality`, `oee` | Float | `digits=(6,4)`; `has_data=False` → 0 і не показуються |
| `has_data` | Boolean | `string="Є дані"` (`ppt_min > 0`) |
| `coverage` | Float | `digits=(6,4)`, `string="Повнота даних"` = `1 − nodata/(ppt + nodata)` |
| `incomplete` | Boolean | `string="Неповні дані"` (`coverage < coverage_min`) |
| `losses` | Json | `string="Втрати"` — `[{"loss_id": int, "name": str, "minutes": float}]` за спаданням |
| `computed_at` | Datetime | `ro` |
| `oee_color` | Selection | `compute` (не зберігається): `good` (≥ `oee_good`), `warn` (≥ `oee_warn`), `bad` |

`_f3d_oee_uniq = models.Constraint("UNIQUE(machine_id, date)", "OEE за цю зміну вже є.")`. Методи:
`@api.model _td_compute(self, machine, day: date, close: bool = False) -> record` (R-14), `@api.model _cron_oee(self)`
(R-14), `action_recompute(self)` (кнопка; права `group_td_manager`). Записи змінює лише крон/кнопка (`sudo`); форми
— лише читання.

### M-07 `td.gantry.stack` — стос під порталом (CM-01, A-11)

```python
class F3dGantryStack(models.Model):
    _name = "td.gantry.stack"
    _description = "Портал: стос плит"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "code"
    _rec_name = "code"
    GANTRY_TARGETS = ("SAW-1", "SAW-2", "SAW-3", "NEST-1")    # iot_sim API-25 target
```

| Поле | Тип | Параметри |
|---|---|---|
| `location_id` | Many2one `stock.location` | `req`, `idx`, `ondelete="cascade"`, `string="Місце"`, `domain="[('td_loc_kind','=','stack')]"` |
| `code` | Char | `related="location_id.td_code"`, `store=True`, `idx`, `string="Стос"` (`PLT-04C`) |
| `capacity` | Float | `related="location_id.td_capacity"`, `string="Місткість, арк."` (60, CB-05) |
| `row` | Integer | `compute="_compute_rowcol"`, `store=True`, `string="Ряд"` — з коду `PLT-(\d{2})([A-C])` |
| `col` | Char(1) | `compute="_compute_rowcol"`, `store=True`, `string="Колонка"` |
| `orderpoint_id` | Many2one `stock.warehouse.orderpoint` | `ondelete="set null"`, `string="Правило поповнення"` |
| `min_qty`, `max_qty` | Float | `related="orderpoint_id.product_min_qty/product_max_qty"` |
| `ws_qty` | Integer | `string="Портал, арк."`, `tracking=True` |
| `ws_product` | Char(32) | `string="Товар у порталі"` (`default_code`) |
| `ws_product_id` | Many2one `product.product` | `compute="_compute_ws_product"`, `store=True` — `search([('default_code','=',ws_product)], limit=1)` |
| `ws_lot` | Char(64) | `string="Партія в порталі"` |
| `ws_reserved` | Integer | `string="Зарезервовано порталом"` |
| `ws_locked` | Boolean | `string="Заблоковано в порталі"` |
| `ws_updated` | Datetime | `string="Оновлено в порталі"` (`updated` API-21) |
| `ws_seen` | Datetime | `string="Отримано"` (час обробки EV-02) |
| `odoo_qty` | Float | `digits=(12,1)`, `string="Odoo, арк."` — Σ `stock.quant.quantity` у `location_id` (пише `_td_refresh`) |
| `odoo_product_id` | Many2one `product.product` | `string="Товар в Odoo"` (кванти з найбільшою к-стю) |
| `odoo_lot_id` | Many2one `stock.lot` | `string="Партія в Odoo"` |
| `fed_unconsumed` | Float | `digits=(12,1)`, `string="Подано, не списано"` (R-15 п. 2) |
| `expected_qty` | Float | `digits=(12,1)`, `string="Має бути в порталі"` = `odoo_qty − fed_unconsumed` |
| `diff` | Float | `digits=(12,1)`, `string="Розбіжність, арк."` = `ws_qty − expected_qty` |
| `state` | Selection | `[('ok','Збігається'),('pending','Перевіряється'),('diff','Розбіжність'),('unknown','Немає даних')]`, `default='unknown'`, `idx`, `tracking=True` |
| `diff_since` | Datetime | службове (R-15 п. 4) |
| `fill` | Float | `compute` (не зберігається): `ws_qty / capacity` при `capacity > 0` |
| `job_ids` | One2many `td.gantry.job` `stack_id` | `string="Завдання"` |
| `note` | Text | |

`_f3d_stack_loc_uniq = models.Constraint("UNIQUE(location_id)", "Для місця вже є стос.")`; `CHECK(ws_qty >= 0)`
(`"Кількість у порталі не може бути від'ємною."`).

Методи: `_td_refresh(self)` — R-15 п. 1–5 (без `write`, якщо нічого не змінилось); `@api.model _td_apply_ws(self,
items: list[dict], ts)` — EV-02 `stacks` (R-23 п. 3); `action_accept_portal(self)` — R-15 п. 6а (права
`stock.group_stock_manager`); `action_fix_portal(self)` — R-15 п. 6б (CMD-02 `stack`); `action_replenish(self)` — R-18
п. 2; `action_view_quants(self)`, `action_view_jobs(self)`; `action_f3d_show(self)` → `location_id.action_f3d_show()`.

### M-08 `td.gantry.job` — завдання порталу (CM-01)

```python
class F3dGantryJob(models.Model):
    _name = "td.gantry.job"
    _description = "Портал: завдання"
    _inherit = ["mail.thread"]
    _order = "id desc"
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | `req`, `copy=False`, `default=lambda s: s.env["ir.sequence"].next_by_code("td.gantry.job")`, `string="Номер"` (`ПОРТ/00007`) |
| `ws_id` | Char(32) | `idx`, `copy=False`, `string="Номер у woodStore"` (`wj-00412`) |
| `type` | Selection | `[('feed','Подача на верстат'),('restack','Перекладання'),('return','Повернення в стос'),('count','Перерахунок')]`, `req`, `default='feed'` |
| `origin` | Selection | `[('odoo','Odoo'),('machine','Портал')]`, `req`, `default='odoo'`, `string="Створено в"` |
| `stack_id` | Many2one `td.gantry.stack` | `ondelete="set null"`, `string="Стос"` (порожньо — портал обирає за товаром/партією) |
| `target_workcenter_id` | Many2one `mrp.workcenter` | `ondelete="set null"`, `string="На верстат"`, `domain="[('td_code','in',('SAW-1','SAW-2','SAW-3','NEST-1'))]"` |
| `target_code` | Char | `related="target_workcenter_id.td_code"` |
| `sheets` | Integer | `req`, `default=1`, `string="Листів"` |
| `done` | Integer | `default=0`, `string="Подано"`, `tracking=True` |
| `product_id` | Many2one `product.product` | `string="Плита"` |
| `lot_id` | Many2one `stock.lot` | `string="Партія"` |
| `priority` | Integer | `default=5`, `string="Пріоритет"` (1…9) |
| `external_ref` | Char(64) | `string="Документ"` (назва МО) |
| `production_id` | Many2one `mrp.production` | `ondelete="set null"`, `idx` |
| `workorder_id` | Many2one `mrp.workorder` | `ondelete="set null"` |
| `cut_map_id` | Many2one `td.cut.map` | `ondelete="set null"` |
| `state` | Selection | `[('draft','Чернетка'),('to_send','До відправки'),('sent','Надіслано'),('queued','У черзі порталу'),('active','Виконується'),('done','Виконано'),('cancelled','Скасовано'),('error','Помилка')]`, `req`, `idx`, `default='draft'`, `tracking=True` |
| `command_id` | Many2one `td.command` | `ondelete="set null"`, `string="Команда"` |
| `cancel_command_id` | Many2one `td.command` | `ondelete="set null"` |
| `error` | Char(512) | `ro` |
| `ws_created`, `started`, `finished` | Datetime | `ro` |
| `sheet_log` | Json | `default=list`, `string="Листи"` — `[{"ts": iso, "stack": "PLT-03C", "lot": "…"}]`, ≤ 200 |
| `consumed_qty` | Float | `ro`, `string="Списано в МО"` (R-17) |
| `company_id` | Many2one `res.company` | `req`, `default=lambda s: s.env.company` |

```python
    _f3d_gjob_ws_uniq = models.Constraint("UNIQUE(ws_id)", "Завдання woodStore вже прив'язане.")
    _f3d_gjob_numbers = models.Constraint("CHECK(sheets >= 1 AND done >= 0 AND priority BETWEEN 1 AND 9)",
                                          "Листів ≥ 1, подано ≥ 0, пріоритет 1…9.")
```

`@api.constrains("type", "product_id", "target_workcenter_id", "state")`: `type='feed'` і стан ≠ `draft`/`cancelled`
без `product_id` або `target_workcenter_id` → `"Для подачі задайте плиту і верстат."`; `target_code` поза
`GANTRY_TARGETS` → `"Портал подає лише на SAW-1, SAW-2, SAW-3, NEST-1."`; `origin='odoo'` і `stack_id.product`
відрізняється від `product_id` (за квантами Odoo) → `"У стосі %s інша плита: %s."`.

Методи: `action_send(self)` — `draft/error` → `to_send` (права `mrp.group_mrp_user`); `action_cancel(self)` — R-16 п. 6
(права `mrp.group_mrp_manager` для `queued/active`, інакше `mrp.group_mrp_user`); `action_retry(self)` — `error` →
`to_send`; `@api.model _td_from_production(self, production, workorder=None, cut_map=None, sheets=None) -> record` —
R-16 п. 1; `_td_send(self)` — R-16 п. 2; `@api.model _td_apply_ws(self, items: list[dict], ts)` — EV-02 `jobs`;
`@api.model _td_apply_events(self, items: list[dict])` — EV-02 `events` (R-23 п. 4); `_td_consume(self)` — R-17;
`@api.model _cron_gantry(self)` — R-15, R-16, R-18 (§6).

### M-09 `td.cut.part` — деталь виробу для розкрою (CM-01, A-13)

`_name = "td.cut.part"`, `_description = "Розкрій: деталь виробу"`, `_order = "bom_id, sequence, part_code"`,
`_rec_name = "name"`.

| Поле | Тип | Параметри |
|---|---|---|
| `bom_id` | Many2one `mrp.bom` | `req`, `idx`, `ondelete="cascade"`, `string="Специфікація"` |
| `product_tmpl_id` | Many2one `product.template` | `related="bom_id.product_tmpl_id"`, `store=True` |
| `sequence` | Integer | `default=10` |
| `part_code` | Char(16) | `req`, `string="Код деталі"` (`P001`; `^[A-Za-z0-9_\-]{1,16}$`) |
| `name` | Char(64) | `req`, `string="Назва"` (без `;` і переносів) |
| `length_mm` | Integer | `req`, `string="Довжина, мм"` (1…5600) |
| `width_mm` | Integer | `req`, `string="Ширина, мм"` (1…2200) |
| `qty` | Float | `req`, `default=1.0`, `digits=(8,2)`, `string="На виріб, шт"` (> 0) |
| `material_role` | Selection | `[('main','Основна плита (≥ 8 мм)'),('back','Тонка плита (< 8 мм)'),('product','Вказаний товар')]`, `req`, `default='main'`, `string="Матеріал"` |
| `material_product_id` | Many2one `product.product` | `string="Плита"`, `domain="[('td_sheet_length_mm','>',0)]"` — обов'язкова для `product` |
| `grain` | Selection | `[('0','Без текстури'),('1','Уздовж'),('2','Поперек')]`, `default='0'`, `req`, `string="Текстура"` |
| `edge_top`, `edge_bottom`, `edge_left`, `edge_right` | Char(32) | `string="Крайка верх/низ/ліво/право"` — `default_code` крайки (`EB2-SON`) або порожньо; `^[A-Z0-9][A-Z0-9\-]{0,31}$` |
| `program` | Char(64) | `string="Програма ЧПК (MPR)"` (`^[A-Za-z0-9_\-\.]{1,64}$` або порожньо) |
| `note` | Char(256) | |
| `active` | Boolean | `default=True` |

`_f3d_part_uniq = models.Constraint("UNIQUE(bom_id, part_code)", "Код деталі повторюється в специфікації.")`;
`CHECK(length_mm BETWEEN 1 AND 5600 AND width_mm BETWEEN 1 AND 2200 AND qty > 0)` («Розміри деталі поза межами
або кількість ≤ 0.»); `@api.constrains`: регекси полів → `"Деталь %s: %s"`; `material_role='product'` без
`material_product_id` → `"Для матеріалу «Вказаний товар» оберіть плиту."`.

### M-10 `td.cut.map` — карта розкрою (CM-01)

```python
class F3dCutMap(models.Model):
    _name = "td.cut.map"
    _description = "Розкрій: карта розкрою"
    _inherit = ["mail.thread"]
    _order = "id desc"
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | `req`, `copy=False`, `default=lambda s: s.env["ir.sequence"].next_by_code("td.cut.map")`, `string="Номер"` (`КР/00012`) |
| `production_id` | Many2one `mrp.production` | `req`, `idx`, `ondelete="restrict"`, `string="Виробниче замовлення"` |
| `product_id` | Many2one | `related="production_id.product_id"` |
| `workorder_id` | Many2one `mrp.workorder` | `ondelete="set null"`, `string="Завдання розкрою"`, `domain="[('production_id','=',production_id)]"` |
| `workcenter_id` | Many2one `mrp.workcenter` | `related="workorder_id.workcenter_id"`, `store=True` |
| `machine_code` | Char | `related="workcenter_id.td_code"` |
| `material_role` | Selection | як M-09, `req`, `default='main'` |
| `material_product_id` | Many2one `product.product` | `req`, `string="Плита"`, `domain="[('td_sheet_length_mm','>',0)]"` |
| `sheet_length_mm`, `sheet_width_mm`, `thickness_mm` | Integer | `string="Лист: довжина/ширина/товщина, мм"` — копія з товару при створенні |
| `qty` | Float | `req`, `digits=(12,2)`, `string="Виробів"` (`production.product_qty` − уже вироблене) |
| `line_ids` | One2many `td.cut.map.line` `map_id` | `string="Деталі"` |
| `parts_count` | Integer | `compute="_compute_parts"`, `store=True`, `string="Деталей"` = Σ `line.qty` |
| `mode` | Selection | `[('collector','Через колектор'),('manual','Вручну')]`, `req`, `default=lambda s: param(s.env, "cutting_mode", "manual")` |
| `state` | Selection | `[('draft','Чернетка'),('exported','Експортовано'),('optimizing','Оптимізується'),('planned','Сплановано'),('released','Випущено'),('running','Ріжеться'),('done','Виконано'),('error','Помилка'),('cancel','Скасовано')]`, `req`, `idx`, `default='draft'`, `tracking=True` |
| `ext_job_id` | Char(32) | `idx`, `copy=False`, `string="Номер в оптимізаторі"` (`cj-00077`) |
| `job_order_id` | Char(64) | `copy=False`, `string="JobOrder верстата"` |
| `plan_sheets` | Integer | `string="Аркушів за планом"`, `tracking=True` |
| `plan_waste_pct` | Float | `digits=(5,1)`, `string="Відхід, %"` |
| `plan_cut_length_m` | Float | `digits=(10,1)`, `string="Довжина різу, м"` |
| `plan_est_min` | Float | `digits=(8,1)`, `string="Оцінка часу, хв"` |
| `plan_json` | Json | `copy=False`, `string="План"` (API-32) |
| `sheets_need` | Float | `compute="_compute_need"` (не зберігається), `string="Потреба МО, арк."` — Σ `product_uom_qty` сировинних рухів МО з `material_product_id`, `state not in ('done','cancel')` |
| `sheets_warning` | Char | `compute="_compute_need"`: `plan_sheets > sheets_need` → `"За планом %d арк., у МО %g — оновіть потребу або візьміть із запасу."`, інакше порожньо |
| `csv_attachment_id` | Many2one `ir.attachment` | `ondelete="set null"`, `copy=False`, `string="Список деталей (CSV)"` |
| `plan_attachment_id` | Many2one `ir.attachment` | `ondelete="set null"`, `copy=False`, `string="План (JSON)"` |
| `mpr_attachment_ids` | Many2many `ir.attachment` | `relation="td_cut_map_mpr_rel"`, `column1="map_id"`, `column2="attachment_id"`, `copy=False`, `string="Програми ЧПК"` |
| `export_token_hash` | Char(64) | `copy=False`, `groups="td_factory3d.group_td_admin"` — sha256 одноразового токена API-01 |
| `export_token_expires` | Datetime | `copy=False`, `groups="td_factory3d.group_td_admin"` |
| `command_ids` | One2many `td.command` `td_cut_map_id` | `string="Команди"` |
| `gantry_job_id` | Many2one `td.gantry.job` | `ondelete="set null"`, `copy=False` |
| `error` | Char(512) | `ro` |
| `released_at`, `done_at` | Datetime | `ro` |
| `company_id` | Many2one | `related="production_id.company_id"`, `store=True` |

`@api.constrains("sheet_length_mm", "sheet_width_mm", "thickness_mm", "material_product_id")`: розміри листа > 0
(`"Задайте розміри листа плити %s."`); `@api.constrains("line_ids")` — кожна деталь вміщується в лист з урахуванням
текстури (R-19 п. 4) → `"Деталь %s (%d × %d) не вміщується в лист %d × %d."`.

Методи (R-19, R-20):

| Сигнатура | Дія |
|---|---|
| `@api.model _td_create_for(self, production, material_role='main') -> record` | R-19 п. 1–3 (кнопка МО «Створити карту розкрою» викликає для `main` і, якщо є, `back`) |
| `action_build_lines(self)` | R-19 п. 3 (у `draft`, перебудова) |
| `action_export(self)` | `draft` → `exported`: CSV R-19 п. 5 → `ir.attachment` (`res_model='td.cut.map'`, `name="<номер>_parts.csv"`, `mimetype='text/csv'`); режим `collector` → `action_send_optimizer()` |
| `action_send_optimizer(self)` | R-20 п. 1 (CMD-03 `upload`) |
| `action_download_csv(self)` | `ir.actions.act_url` `/web/content/<csv_attachment_id>?download=true` |
| `action_open_plan_import(self)` | M-25 `target='new'` |
| `action_update_mo_need(self)` | R-20 п. 4 (права `mrp.group_mrp_manager`) |
| `action_release(self)` | R-20 п. 5 |
| `action_cancel(self)` / `action_reset_draft(self)` | `cancel` з будь-якого, крім `done`; `draft` з `error`/`cancel` (очищає `ext_job_id`, план, команди не чіпає) |
| `_td_new_export_token(self) -> str` | `t = secrets.token_hex(8)`; `export_token_hash = sha256(t)`, `export_token_expires = now + export_token_ttl_s`; повертає `t` |
| `@api.model _td_check_export_token(self, map_id, t) -> record` | API-01 п. 3 |
| `_td_apply_job(self, job: dict)` / `_td_apply_plan(self, plan: dict)` / `_td_apply_mpr(self, part: str, text: str)` | R-20 п. 2–3 (з EV-03) |
| `@api.model _cron_cutmap(self)` | R-20 п. 6 |

### M-11 `td.cut.map.line` — деталь у карті розкрою

`_name = "td.cut.map.line"`, `_description = "Розкрій: деталь у карті"`, `_order = "map_id, sequence, id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `map_id` | Many2one `td.cut.map` | `req`, `idx`, `ondelete="cascade"` |
| `sequence` | Integer | `default=10` |
| `part_id` | Many2one `td.cut.part` | `ondelete="set null"` |
| `part_code` | Char(16) | `req` |
| `name` | Char(64) | `req` |
| `length_mm`, `width_mm` | Integer | `req` |
| `qty` | Integer | `req` (≥ 1) |
| `grain` | Selection | як M-09 |
| `edge_top`, `edge_bottom`, `edge_left`, `edge_right` | Char(32) | |
| `program` | Char(64) | |
| `mpr_attachment_id` | Many2one `ir.attachment` | `ondelete="set null"` |

`CHECK(qty >= 1 AND length_mm > 0 AND width_mm > 0)`. Редагується лише в `draft` (`write` в інших станах →
`UserError("Карта %s уже експортована — поверніть у чернетку.")`).

### M-12 `mrp.workcenter` — розширення

`_inherit = "mrp.workcenter"`. Поля: `td_machine_ids` One2many `td.machine` `workcenter_id`; `td_machine_id`
Many2one `td.machine` `compute="_compute_f3d_machine"` (не зберігається; перший з `td_machine_ids`);
`td_machine_state` Selection `STATES` `compute` (= `td_machine_id.state`, порожньо без верстата), `string="Стан
верстата"`; `td_oee_today` Float `compute` (= `td_machine_id.oee_today`). Метод `action_f3d_machine(self)` — форма
`td.machine` (створення з `default_workcenter_id`, якщо немає; права `group_td_manager`). Стандартні поля й
методи РЦ не перевизначаються.

### M-13 `mrp.workorder` — розширення

`_inherit = "mrp.workorder"`.

| Поле | Тип | Параметри |
|---|---|---|
| `td_qty_counted` | Float | `digits="Product Unit"`, `ro`, `copy=False`, `string="Порахував верстат"` (R-11) |
| `td_qty_synced_at` | Datetime | службове (режим `live`, R-11 п. 5) |
| `td_auto_started` | Boolean | `ro`, `copy=False`, `string="Стартував верстат"` |
| `td_partial_hold` | Boolean | `copy=False`, `string="Неповна партія"` (R-12 п. 4) |
| `td_run_min` | Float | `digits=(12,1)`, `ro`, `copy=False`, `string="Робота верстата, хв"` (R-28) |
| `td_setup_min` | Float | `digits=(12,1)`, `ro`, `copy=False`, `string="Налагодження, хв"` (R-28) |
| `td_machine_state` | Selection `STATES` | `related="workcenter_id.td_machine_state"`, `string="Стан верстата"` |
| `td_cut_map_ids` | One2many `td.cut.map` `workorder_id` | `string="Карти розкрою"` |
| `td_can_send` | Boolean | `compute` (не зберігається): верстат РЦ має `protocol='opcua'` і `sig_job_cmd_id` |
| `td_gantry_job_ids` | One2many `td.gantry.job` `workorder_id` | `string="Завдання порталу"` |

Методи: `action_f3d_finish_partial(self)` — права `mrp.group_mrp_manager`; `ensure_one()`; `qty_produced =
td_qty_counted` (якщо > 0), `td_partial_hold=False`, `button_finish()` (стандарт; `qty_production` не змінюється,
backorder — рішення МО при закритті); чатер МО «Завдання <назва> завершено неповною партією: <n> з <m>».
`action_f3d_clear_hold(self)` — `td_partial_hold=False` (дозапуск).
`action_f3d_send_to_machine(self)` (FR-27, CMD-01 `Store`; права `mrp.group_mrp_user`): `ensure_one()`; немає
`td_can_send` → `UserError("Робочий центр %s не приймає завдань з Odoo (немає OPC UA JobManagement).")`; стан ∉
{`ready`, `blocked`} → `UserError("Завдання %s уже в роботі або завершене.")`; команда CMD-01 `Store`:
`env["td.command"]._td_mc_create_command(machine.sig_job_cmd_id, "Store", {"job": f"WO{id:05d}", "qty": max(1,
ceil(qty_remaining)), "ref": production_id.name, "priority": 5}, {"td_machine_id": machine.id})` (payload R-21, X-03; поле не за R-21 →
`UserError` з M-20; п'ять запобіжників, M-20); чатер МО «Завдання <назва> поставлено в чергу верстата <код>: <`text`
команди>». Старт — з пульта верстата, далі R-09.
Стандартні `button_start`, `button_finish`, `button_pending` **не перевизначаються**.

### M-14 `mrp.production` — розширення

`_inherit = "mrp.production"`. Поля: `td_cut_map_ids` One2many `td.cut.map` `production_id`, `td_cut_map_count`
Integer `compute`, `td_gantry_job_ids` One2many `td.gantry.job` `production_id`, `td_gantry_job_count` Integer
`compute`. Методи: `action_f3d_create_cut_maps(self)` — права `group_td_manager`; для ролей `main` і `back` (якщо
у МО є сировинний рух плити відповідної товщини, R-19 п. 1) — `td.cut.map._td_create_for(self, role)`; повертає
дію на створені карти; МО у стані `done`/`cancel` → `UserError("МО %s завершено або скасовано.")`.
`action_f3d_view_cut_maps(self)`, `action_f3d_feed_gantry(self)` — `td.gantry.job._td_from_production(self)`
(R-16 п. 1), повертає форму завдання; `action_f3d_view_gantry_jobs(self)`.

### M-15 `mrp.workcenter.productivity` — розширення (CM-09, R-06)

`_inherit = "mrp.workcenter.productivity"`.

| Поле | Тип | Параметри |
|---|---|---|
| `td_downtime_id` | Many2one `td.downtime` | `ondelete="set null"`, `idx`, `string="Простій верстата"` |
| `td_source` | Selection | `[('operator','Оператор'),('machine','Верстат'),('master','Майстер'),('demo','Демо-дані')]`, `default='operator'`, `string="Звідки запис"` |
| `td_auto` | Boolean | `default=False`, `string="Створено верстатом"` |

`create(self, vals_list)` (`@api.model_create_multi`): `records = super().create(vals_list)`; якщо контекст має
`f3d_mc_auto` — записам `td_source='machine'`, `td_auto=True` (якщо не задано у `vals`) і повернути; інакше для
кожного запису з `loss_type in ('availability', 'quality')` і `workorder_id` порожнім — R-06 (злиття з відкритим
простоєм верстата цього РЦ); повертає `records` (жоден створений запис не видаляється). `write`/`unlink` — стандарт.

### M-16 `mrp.workcenter.productivity.loss` — розширення (CM-09)

`_inherit = "mrp.workcenter.productivity.loss"`; поле `td_planned` Boolean `default=False`, `string="Плановий
простій"`, `help="Не входить у плановий час виробництва при розрахунку OEE (обід, регламентна перерва)"`.

### M-17 `product.template` — розміри листа (A-25)

`_inherit = "product.template"`; поля `td_sheet_length_mm`, `td_sheet_width_mm`, `td_thickness_mm` — Integer,
`default=0`, `string="Лист: довжина/ширина/товщина, мм"`; `CHECK(td_sheet_length_mm >= 0 AND td_sheet_width_mm >= 0
AND td_thickness_mm >= 0)`; `@api.constrains`: довжина > 0 ⇔ ширина > 0 ⇔ товщина > 0 (`"Задайте всі три розміри
листа або жодного."`). Заповнення з назви — хук §5.3 крок 2 (R-27 п. 2).

### M-18 `td.signal` — вхід показань (A-22)

`_inherit = "td.signal"`. Перевизначення (обидва викликають `super()` **першим** і не змінюють його результату):

```python
    @api.model
    def _td_ingest(self, readings, src="module", collector=None):
        res = super()._td_ingest(readings, src=src, collector=collector)
        if self.env.context.get("f3d_mc_internal") or not param_bool(self.env, "read_enabled", _env_default(self.env)):
            return res
        # unknown_state telemetry приймає (q='bad') і лише повідомляє — такі показання модуль обробляє сам (R-01)
        rejected = {r["i"] for r in res.get("rejected", ()) if r.get("reason") != "unknown_state"}
        code_map = self.env["td.machine"]._td_code_map()
        mine = [dict(r, i=i) for i, r in enumerate(readings) if i not in rejected and r.get("code") in code_map]
        if mine:
            self.env["td.machine"].sudo()._td_dispatch(mine, src)
        return res

    def _mark_stale(self, reason):
        res = super()._mark_stale(reason)
        code_map = self.env["td.machine"]._td_code_map()
        for sig in self.filtered(lambda s: code_map.get(s.code, (0, ""))[1] == "state"):
            self.env["td.machine"].sudo().browse(code_map[sig.code][0])._td_mark_nodata(fields.Datetime.now(), reason)
        return res
```

`_td_dispatch` ловить винятки на рівні верстата (`savepoint` на верстат, `logger.exception`, лічильник
`errors`), тож помилка диспетчера не відкочує показань telemetry і не дає `5xx` колектору.

### M-19 `td.source` — локальний тип (A-17, CT-12)

```python
class F3dSource(models.Model):
    _inherit = "td.source"
    type = fields.Selection(selection_add=[("f3d_machine", "Верстати: обчислені стани")], ondelete={"f3d_machine": "cascade"})

    @api.model
    def _td_local_types(self):
        return super()._td_local_types() + ["f3d_machine"]
```

Джерело `MC-DERIVED` (`type='f3d_machine'`, без колектора, `params={}`, `module='machine_connect'`); його `state`
веде модуль: `online`, коли `read_enabled` модуля `True`, інакше `disabled` (крон R-02 п. 4 щохвилини, лише при зміні).

### M-20 `td.command` — розширення (A-14, CM-08, X-03)

`_inherit = "td.command"` (поля telemetry 19.0.1.1.0 `payload`, `result_data` — CR-01, telemetry M-06). Поля:
`td_machine_id` Many2one `td.machine`, `td_gantry_job_id` Many2one
`td.gantry.job`, `td_cut_map_id` Many2one `td.cut.map` — усі `ondelete="set null"`, `idx`. `write(self, vals)`:
`super()`; якщо `'state' in vals` і новий стан ∈ {`done`, `failed`, `expired`, `cancelled`} і `origin ==
'machine_connect'` → `self._td_mc_on_result()`: для `td_gantry_job_id` — R-16 п. 3; для `td_cut_map_id` — R-20 п. 2;
для `td_machine_id` — чатер верстата «Команда <текст>: <стан> <result/error>». Результат команди модуль бере з
`result_data` (об'єкт, який повернув `call()` плагіна, колонка «Результат» R-21); у запасному режимі (`result_data`
порожнє) — з рядка `result` (колонка «Запасний `result`» R-21). Те саме виконують крони R-16/R-20
для команд, стан яких змінено не через ORM (A-14).

Створення команд модулем — лише методом цього розширення (X-93: не в `tools/commands.py`, бо той модуль копіюється в
пакет колектора й не імпортує Odoo) `@api.model _td_mc_create_command(self, signal, op, fields: dict, links: dict | None
= None) -> td.command` (виклик — `env["td.command"]._td_mc_create_command(...)`; чисті функції R-21 — з
`..tools.commands`):
1. `param_bool("write_enabled")` — інакше `UserError("Запис на пристрої вимкнено: td.machine_connect.write_enabled.")`.
2. Вид команди — з адреси сигналу: `address.call == "job"` → `job`; `address.cmd` ∈ {`gantry`, `cutopt`} → той самий;
   інакше `UserError("Сигнал %s не є сигналом команд верстатів.")`.
3. `payload = build_payload(kind, op, **fields)` (R-21); `ValueError` → `UserError("Команда «%s» не відповідає формату: %s")`.
4. `self._td_mc_payload_supported()` (`@api.model`, = `'payload' in self._fields`, telemetry 19.0.1.1.0) → `vals = {'payload':
   payload, 'text': cmd_label(kind, payload)}` (`text` довідковий — для списку команд telemetry V-17 і чатера; плагін
   для команди з `payload` його не читає, telemetry M-06); інакше — запасний режим: `vals = {'text': build_cmd(kind, op,
   **fields)}` (> 64 символи → той самий `UserError`, що в п. 3).
5. `self.sudo().create({'signal_id': signal.id, **vals, 'origin': 'machine_connect', 'expires_at': now +
   10 хв, **(links or {})})` — решту запобіжників (telemetry `write_enabled`, джерело, сигнал) перевіряє telemetry R-18
   у `create`.

### M-21 `td.push.handler.machine_connect` — події колектора (CM-07)

```python
class F3dPushHandlerMachineConnect(models.AbstractModel):
    _name = "td.push.handler.machine_connect"
    _inherit = "td.push.handler"
    _description = "Верстати: обробник подій колектора"
    _td_push_routes = ("mc_opcua", "mc_woodstore", "mc_cutopt")
```

`_td_handle_push(self, route, event)`: `payload = event["payload"]`; невідомий `payload["kind"]` або відсутнє
обов'язкове поле → `ValueError("<route>: <поле>")` (telemetry пише в `td.push.event.error`). Маршрути:
`mc_opcua` → `td.machine._td_apply_event(payload)` (R-07 п. 1, R-12 п. 1; EV-01); `mc_woodstore` → `kind='status'` R-23 п. 2, `'stacks'` → `td.gantry.stack._td_apply_ws`,
`'jobs'` → `td.gantry.job._td_apply_ws`, `'events'` → `_td_apply_events` (EV-02); `mc_cutopt` → `kind='job'`
`_td_apply_job`, `'plan'` `_td_apply_plan`, `'mpr'` `_td_apply_mpr` (EV-03). Обробник працює `sudo()`.

### M-22 `td.viewer.provider.machines` — провайдер переглядача (CM-05, A-18)

```python
class F3dViewerProviderMachines(models.AbstractModel):
    _name = "td.viewer.provider.machines"
    _description = "3D: живі стани верстатів, OEE, портал, карти розкрою"
    _td_sequence = 75
    _td_sections = ()
    _td_group = "td_factory3d.group_td_user"
```

Без `_inherit`: viewer M-01 R-01 п. 3 збирає моделі з префіксом `td.viewer.provider.` і читає атрибути
`_td_sequence`, `_td_sections`, `_td_group`. Методи: `_td_viewer_collect(self, payload, ctx)` — R-25;
`_td_viewer_delta(self, patch, ctx)` — R-25 п. 7; `_td_viewer_bus_models(self)` → `["mrp.workcenter",
"stock.location", "maintenance.equipment", "mrp.production"]`. Побудова — функції `tools/payload.py` цього модуля
(`build_machines(env, ctx)`), щоб юніт-тести перевіряли без встановленого viewer.

### M-23 `res.config.settings` — розширення

| Поле | Тип | `config_parameter` (`td.machine_connect.` + …) | Групи у формі |
|---|---|---|---|
| `td_mc_read_enabled` | Boolean | `read_enabled` | `group_td_admin` |
| `td_mc_auto_start_enabled` | Boolean | `auto_start_enabled` | `group_td_admin` |
| `td_mc_write_enabled` | Boolean | `write_enabled` | `group_td_admin` |
| `td_mc_micro_stop_s` | Integer | `micro_stop_s` | `group_td_manager` |
| `td_mc_pause_after_min` | Integer | `pause_after_min` | `group_td_manager` |
| `td_mc_finish_idle_s` | Integer | `finish_idle_s` | `group_td_manager` |
| `td_mc_qty_sync_mode` | Selection `[('finish','При завершенні'),('live','Наживо')]` | `qty_sync_mode` | `group_td_manager` |
| `td_mc_qty_sync_s` | Integer | `qty_sync_s` | `group_td_manager` |
| `td_mc_coverage_min` | Float | `coverage_min` | `group_td_manager` |
| `td_mc_oee_good`, `td_mc_oee_warn` | Float | `oee_good`, `oee_warn` | `group_td_manager` |
| `td_mc_no_job_activity_min` | Integer | `no_job_activity_min` | `group_td_manager` |
| `td_mc_stack_diff_tolerance` | Integer | `stack_diff_tolerance` | `group_td_manager` |
| `td_mc_stack_diff_confirm_min` | Integer | `stack_diff_confirm_min` | `group_td_manager` |
| `td_mc_gantry_auto_replenish` | Boolean | `gantry_auto_replenish` | `group_td_manager` |
| `td_mc_gantry_auto_feed` | Boolean | `gantry_auto_feed` | `group_td_manager` |
| `td_mc_cutting_mode` | Selection `[('collector','Через колектор'),('manual','Вручну')]` | `cutting_mode` | `group_td_admin` |
| `td_mc_export_token_ttl_s` | Integer | `export_token_ttl_s` | `group_td_admin` |
| `td_mc_keep_log_days`, `td_mc_keep_event_days` | Integer | `keep_log_days`, `keep_event_days` | `group_td_admin` |
| `td_mc_migration_state` | Char | `compute`: `json.loads(param('migration_report','{}')).get('state','—')` | — |

`set_values(self)`: якщо змінюється будь-який із полів групи `group_td_admin`, а користувач без неї →
`AccessError("Стоп-крани змінює лише адміністратор «Завод 3D».")`; межі: `micro_stop_s` 0…3600, `pause_after_min`
1…240, `finish_idle_s` 0…3600, `qty_sync_s` 30…3600, `coverage_min` 0…1, `oee_warn < oee_good` (обидва 0…1),
`stack_diff_tolerance` 0…60, `stack_diff_confirm_min` 1…240, `export_token_ttl_s` 60…3600, `keep_log_days` ≥ 30,
`keep_event_days` ≥ 7 — інакше `ValidationError("<назва>: поза межами <lo>…<hi>.")`. Кнопка «Повторити міграцію
демо-даних» (`action_td_mc_run_migration`, `group_td_admin`).

### M-24 `td.downtime.reason.wizard` — причина простою (TransientModel)

| Поле | Тип | Параметри |
|---|---|---|
| `downtime_id` | Many2one `td.downtime` | `req`, `ro` |
| `hint_text` | Char | `related="downtime_id.hint_text"` |
| `loss_id` | Many2one `mrp.workcenter.productivity.loss` | `req`, `domain="[('manual','=',True),('loss_type','in',('availability','quality'))]"`, `default` = `downtime_id.hint_loss_id` або поточна причина, якщо не «Не вказано» |
| `employee_id` | Many2one `hr.employee` | `default=lambda s: s.env.user.employee_id` |
| `note` | Char(256) | |

`action_apply(self)` → `downtime_id.action_set_reason(loss_id.id, employee_id.id)`; `note` → `downtime_id.note` (дописати
рядком «<час> <ім'я>: <note>»); `{'type': 'ir.actions.act_window_close'}`. На простої — метод
`action_quick_reason(self)` для кнопок kanban: `self.env.ref(self.env.context['f3d_loss_xmlid'])` → `action_set_reason`.

### M-25 `td.cut.plan.import.wizard` — імпорт плану (ручний режим)

Поля: `map_id` (req, ro), `file` Binary (req), `filename` Char. `action_import(self)`: `base64` → UTF-8 → `json.loads`
(помилка → `UserError("Файл плану: невалідний JSON (%s).")`) → `tools.cutcsv.parse_plan(data)` (схема API-32; помилки →
`UserError("Файл плану: %s")`) → `map_id._td_apply_plan(plan)`; карта має бути в `exported`/`optimizing`/`planned`
(`UserError("Карта %s не очікує плану (стан «%s»).")`).

### M-26 `td.cut.part.import.wizard` — імпорт деталей

Поля: `bom_id` (req), `file` Binary (req), `filename`, `replace` Boolean (`default=False` — «Замінити наявні»).
`action_import(self)`: CSV за Додатком E (`;`, UTF-8, заголовок обов'язковий); рядок з помилкою → список помилок
`"рядок N: <поле>: <проблема>"`; якщо помилок > 0 — `UserError` з усіма (до 50) і нічого не пишеться; інакше
`replace` → `unlink` наявних деталей специфікації; upsert за `(bom_id, part_code)`; повідомлення «Імпортовано N
деталей».

### M-27 `stock.picking` — поповнення під портал (R-18)

`_inherit = "stock.picking"`; `_action_done(self)`: `res = super()._action_done()`; `stacks =
td.gantry.stack.search([('location_id','in', move_line_ids.location_dest_id.ids + move_line_ids.location_id.ids)])`
для виконаних документів; якщо є — `stacks._td_refresh()` і R-18 п. 3 для стосів, у які **прийшли** листи; повертає `res`.

### M-28 `maintenance.request` — заявка з тривоги верстата (R-08)

`_inherit = "maintenance.request"`; `create(self, vals_list)`: `records = super().create(vals_list)`; для записів з
`td_signal_id`, код якого є в `td.machine._td_code_map()` з роллю `alarm` — R-08 п. 1; повертає `records`.

## 3. Представлення й меню

Спільне: стани верстата — `widget="badge"` з `decoration-success="state == 'working'"`, `decoration-info="state ==
'setup'"`, `decoration-warning="state == 'idle'"`, `decoration-danger="state == 'fault'"`, `decoration-muted="state in
('off','nodata')"`; частки OEE (0…1) — `widget="percentage"`; тексти — українською в XML; час — у tz користувача
(стандарт). Усі XML-id нижче — з префіксом `td_machine_connect.`.

| ID | XML-id | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `view_td_machine_kanban` | kanban `td.machine` («Огляд верстатів») | `default_group_by="zone_id"`, `class="o_kanban_small_column"`, `records_draggable="0"`; поле `color` — кольорова смуга; картка: заголовок `code` · `name`; бейдж `state` + «з `state_since`» (widget `remaining_days` не підходить — `t-esc` локального часу з `luxon`); рядок «Завдання: `active_workorder_id`» + «`active_workorder_id.td_qty_counted` / `active_workorder_id.qty_production`»; якщо `current_downtime_id`: «Простій: `current_downtime_id.loss_id` · `downtime_open_min` хв» червоним для `fault`; рядок «OEE `oee_today`» з кольором за `oee_shift_id.oee_color`; іконки `fa-plug` (OPC UA) / `fa-microchip` (I/O); кнопки: «Причина» (`action_open_reason_wizard` на `current_downtime_id`, `invisible="not current_downtime_id"`), «3D» (`action_f3d_show`); групи `group_td_user` |
| V-02 | `view_td_machine_list` | list `td.machine` | `code`, `name`, `zone_id`, `protocol`, `source_id`, `state` (badge), `state_since`, `active_workorder_id`, `oee_today` (`widget="percentage"`), `auto_start_mode`, `read_enabled` (toggle, `readonly` для не-менеджерів), `micro_stop_s` (optional hide) |
| V-03 | `view_td_machine_form` | form `td.machine` | `<header>`: «Перевірити підключення» (`action_test_connection`), «Показати в 3D» (`action_f3d_show`), «Скинути стан» (`action_reset_state`, `groups="td_factory3d.group_td_admin"`, `confirm="Закрити поточний інтервал і простій?"`), статусбар `state` (readonly). Статбокс: «Журнал станів» (`action_view_logs`), «Простої» (`action_view_downtimes`), «OEE» (`action_view_oee`), «Робочий центр» (`action_open_workcenter`). `<sheet>`: `name` (title, readonly), група «Підключення»: `workcenter_id`, `equipment_id`, `protocol`, `source_id`, `io_slot` (`invisible="protocol != 'io'"`), `active`; вкладка «Сигнали»: `sig_state_id`, `sig_mode_id` / `sig_job_id` / `sig_event_id` / `sig_job_cmd_id` (`invisible="protocol != 'opcua'"`), `sig_alarm_id`, `sig_pieces_id`, `sig_machine_state_id`; вкладка «Автоматика»: `read_enabled`, `auto_start_mode`, `auto_finish`, `auto_pause`, `micro_stop_s`, `pause_after_min`, `finish_idle_s`, `employee_id`; вкладка «Живий стан» (усе readonly): `state`, `state_since`, `raw_state`, `raw_mode`, `raw_alarm`, `raw_job`, `raw_ts`, `pieces_last`, `active_workorder_id`, `current_log_id`, `current_downtime_id`, `oee_today`, `availability_today`, `performance_today`, `quality_today`; вкладка «Примітка»: `note`; чатер. Редагування — `group_td_manager` (`ir.model.access`) |
| V-04 | `view_td_machine_search` | search | поля `code`, `name`, `workcenter_id`; фільтри «В роботі», «Налагодження», «Очікування», «Аварія», «Вимкнено», «Немає даних», «OPC UA», «I/O», «Автостарт увімкнено» (`auto_start_mode != 'off'`), «Є простій» (`current_downtime_id != False`); group by `zone_id`, `protocol`, `state` |
| V-05 | `view_td_machine_state_log_list`, `_graph`, `_pivot` | list / graph / pivot `td.machine.state.log` | list (readonly, `create="0"`): `code`, `state` (badge), `date_start`, `date_end`, `duration_min` (sum), `workorder_id`, `production_id`, `employee_id`, `pieces` (sum), `downtime_id`, `source`, `raw` (optional hide); graph `type="bar"` `stacked="1"`: `code` (row), `state` (col), `duration_min` (measure); pivot: рядки `code`, колонки `state`, міра `duration_min`, `pieces` |
| V-06 | `view_td_machine_state_log_search` | search | `code`, `workorder_id`, `production_id`; фільтри «Сьогодні» (`date_start >= context_today()` у UTC межах дня Києва — `[('date_start','>=', (context_today()).strftime('%Y-%m-%d 00:00:00'))]`), «Відкриті» (`date_end = False`), за станами (6); group by `machine_id`, `state`, `date_start:day` |
| V-07 | `view_td_downtime_list`, `_graph`, `_pivot` | list / graph / pivot `td.downtime` | list: `code`, `date_start`, `date_end`, `duration_live` (sum), `state_kind`, `loss_id` (`options="{'no_create': True}"`, редагується `mrp.group_mrp_user` через `action_set_reason` — у списку readonly), `hint_loss_id`, `hint_text` (optional show), `reason_source`, `reason_state` (badge: `to_classify` danger, `to_confirm` warning, `confirmed` success), `workorder_id`, `maintenance_request_id` (optional), `employee_id` (optional hide); дія у списку «Підтвердити» (`action_confirm`, `groups="mrp.group_mrp_manager"`); graph `type="bar"` «Парето втрат»: `loss_id` (row), `duration_min` (measure), `order="desc"`; pivot: `workcenter_id` × `loss_id`, `duration_min` |
| V-08 | `view_td_downtime_kanban`, `_form`, `_search` | kanban / form / search `td.downtime` | kanban «Без причини» (для планшета, великі кнопки): фільтр за замовчуванням `reason_state in ('to_classify','to_confirm')` і `date_start` сьогодні; картка: `code`, `state_kind`, «з `date_start` · `duration_live` хв», `hint_text`; кнопки причин (`type="object" name="action_quick_reason"`) з `context="{'f3d_loss_xmlid': …}"`: «Очікування матеріалу» (`mrp.block_reason0`), «Поломка» (`mrp.block_reason1`), «Налагодження» (`mrp.block_reason2`), «Заміна інструменту» (`factory3d.loss_tool` — лише якщо є, `invisible` через поле `has_loss_tool` compute), «Інше…» (`action_open_reason_wizard`); form: заголовок `name`; `<header>`: «Вказати причину» (`action_open_reason_wizard`), «Підтвердити» (`action_confirm`, `groups="mrp.group_mrp_manager"`, `invisible="reason_state == 'confirmed'"`), статусбар `reason_state`; групи «Простій»: `machine_id`, `state_kind`, `date_start`, `date_end`, `duration_live`, `ppt_min`; «Причина»: `loss_id` (readonly, змінюється кнопками), `reason_source`, `employee_id`, `reason_user_id`, `reason_at`, `confirmed_by`, `confirmed_at`; «Підказка»: `hint_loss_id`, `hint_text`, `event_id`; «Звʼязки»: `workorder_id`, `production_id`, `maintenance_request_id`; вкладка «Журнал часу» (`productivity_ids` readonly: `loss_id`, `date_start`, `date_end`, `duration`, `td_source`, `employee_id`); `note`; чатер. search: `code`, `loss_id`, `workorder_id`; фільтри «Сьогодні», «Триває» (`is_open`), «Без причини» (`reason_state='to_classify'`), «Не підтверджено» (`reason_state != 'confirmed'`), «Аварії» (`state_kind='fault'`), «Демо» (`reason_source='demo'`); group by `workcenter_id`, `loss_id`, `state_kind`, `date_start:day` |
| V-09 | `view_td_downtime_reason_wizard_form` | form M-24 | `downtime_id` (readonly), `hint_text` (readonly, `invisible="not hint_text"`), `loss_id` (`widget="radio"`), `employee_id`, `note`; footer «Зберегти» (`action_apply`, `btn-primary`), «Скасувати» |
| V-10 | `view_td_machine_event_list`, `_form` | list / form `td.machine.event` | list (readonly): `ts`, `code` (related `machine_id.code`), `kind`, `message_id`, `text`, `category` (badge: 4–5 danger, 3 warning), `active`, `downtime_id`; form readonly + `payload` (`widget="ace"` `mode: json`) |
| V-11 | `view_td_machine_event_search` | search | `message_id`, `machine_id`; фільтри «Тривоги» (`kind='alarm'`), «Активні», «Помилки» (`category in ('4','5')`), «Сьогодні»; group by `machine_id`, `message_id` |
| V-12 | `view_td_oee_shift_list`, `_pivot`, `_graph` | list / pivot / graph `td.oee.shift` | list (readonly): `date`, `code`, `zone_id`, `availability`, `performance`, `quality`, `oee` (усі `widget="percentage"`; `decoration-success="oee_color == 'good'"`, `-warning`, `-danger`), `ppt_min`, `run_min`, `down_min`, `qty_total`, `qty_bad`, `coverage` (percentage, optional show), `incomplete` (optional), `state`, `source` (optional hide); pivot: рядки `zone_id` → `code`, колонки `date:week`, міри `run_min`, `ppt_min`, `ideal_min`, `qty_total`, `qty_bad` (сумарний OEE у pivot не рахується — див. дію «OEE за період», V-14); graph `line` `oee` за `date` по `code` |
| V-13 | `view_td_oee_shift_search` | search | `code`, `zone_id`; фільтри «Сьогодні», «Цей тиждень», «Цей місяць», «Неповні дані», «OEE < порогу» (`oee < 0.5` — значення порогу з параметра не підставляється, фіксоване 0,5 у фільтрі), «Закриті»; group by `zone_id`, `code`, `date:week` |
| V-14 | `view_td_oee_shift_form`, дія `action_td_oee_period` | form (readonly) + client action | form: усі поля M-06 групами «Час», «Кількість», «Показники», «Втрати» (`losses` як таблиця через віджет `json` readonly); серверна дія «OEE за період» на виділених записах: `display_notification` з агрегатом R-13 п. 8 («SAW-1, 01.10–14.10: A 0,83 · P 0,97 · Q 0,99 · OEE 0,80») |
| V-15 | `view_td_gantry_stack_kanban` | kanban `td.gantry.stack` («Портал: стоси») | `default_group_by="row"`, `default_order="col"`; картка: `code`, `ws_product` / `odoo_product_id`, «портал `ws_qty` · Odoo `odoo_qty` · подано `fed_unconsumed`», шкала `fill`, бейдж `state` (ok success, pending info, diff danger, unknown muted), `min_qty`/`max_qty`; кнопки «Поповнити» (`action_replenish`), «3D» |
| V-16 | `view_td_gantry_stack_list`, `_form` | list / form | list: `code`, `ws_product`, `ws_lot`, `ws_qty`, `odoo_qty`, `fed_unconsumed`, `expected_qty`, `diff` (`decoration-danger="state == 'diff'"`), `state`, `min_qty`, `ws_updated`; form: `<header>` «Прийняти з порталу» (`action_accept_portal`, `groups="stock.group_stock_manager"`, `invisible="state != 'diff'"`, `confirm="Створити інвентаризацію стосу на %s арк.?"`), «Виправити портал» (`action_fix_portal`, `groups="stock.group_stock_manager"`, `invisible="state != 'diff'"`), «Поповнити» (`action_replenish`), статусбар `state`; групи «Портал» (`ws_*`), «Odoo» (`odoo_qty`, `odoo_product_id`, `odoo_lot_id`, `fed_unconsumed`, `expected_qty`, `diff`, `diff_since`), «Правило поповнення» (`orderpoint_id`, `min_qty`, `max_qty`); вкладка «Завдання» (`job_ids`); чатер і діяльності |
| V-17 | `view_td_gantry_stack_search` | search | `code`, `ws_product`; фільтри «Розбіжність», «Перевіряється», «Немає даних», «Нижче мінімуму» (`ws_qty < min_qty`); group by `row`, `state`, `ws_product` |
| V-18 | `view_td_gantry_job_list`, `_form`, `_kanban` | list / form / kanban `td.gantry.job` | list: `name`, `ws_id`, `type`, `stack_id`, `target_workcenter_id`, `product_id`, `sheets`, `done`, `external_ref`, `state` (badge), `origin`, `started`, `finished`; form: `<header>` «Надіслати» (`action_send`, `invisible="state not in ('draft','error')"`), «Повторити» (`action_retry`, `invisible="state != 'error'"`), «Скасувати» (`action_cancel`, `invisible="state in ('done','cancelled')"`), статусбар `draft,to_send,sent,queued,active,done`; групи «Що» (`type`, `product_id`, `lot_id`, `sheets`, `done`, `priority`), «Звідки/куди» (`stack_id`, `target_workcenter_id`), «Документ» (`external_ref`, `production_id`, `workorder_id`, `cut_map_id`), «Портал» (`ws_id`, `origin`, `command_id`, `error`, `ws_created`, `started`, `finished`, `consumed_qty`); вкладка «Листи» (`sheet_log` json readonly); чатер; kanban `default_group_by="state"` |
| V-19 | `view_td_gantry_job_search` | search | `name`, `ws_id`, `external_ref`, `product_id`; фільтри «Активні» (`state in ('to_send','sent','queued','active')`), «Помилки», «Сьогодні», «З порталу» (`origin='machine'`); group by `state`, `target_workcenter_id` |
| V-20 | `view_td_cut_part_list`, `_form`, `_search` | list (editable bottom) / form / search `td.cut.part` | list: `bom_id` (у вкладенні — invisible), `sequence` (handle), `part_code`, `name`, `length_mm`, `width_mm`, `qty`, `material_role`, `material_product_id` (optional), `grain`, `edge_top`, `edge_bottom`, `edge_left`, `edge_right`, `program`; search: `bom_id`, `product_tmpl_id`, `part_code`, `name`; group by `bom_id`; дія «Імпорт CSV» (M-26) у меню списку |
| V-21 | `view_td_cut_map_list` | list `td.cut.map` | `name`, `production_id`, `workcenter_id`, `material_product_id`, `qty`, `parts_count`, `plan_sheets`, `plan_waste_pct`, `state` (badge), `mode`, `ext_job_id` (optional) |
| V-22 | `view_td_cut_map_form` | form `td.cut.map` | `<header>`: «Зібрати деталі» (`action_build_lines`, `invisible="state != 'draft'"`), «Експортувати» (`action_export`, `invisible="state != 'draft'"`, `btn-primary`), «Завантажити CSV» (`action_download_csv`, `invisible="not csv_attachment_id"`), «На оптимізацію» (`action_send_optimizer`, `invisible="state not in ('exported','error') or mode != 'collector'"`), «Імпорт плану» (`action_open_plan_import`, `invisible="state not in ('exported','optimizing','planned') or mode != 'manual'"`), «Оновити потребу МО» (`action_update_mo_need`, `invisible="not sheets_warning"`, `groups="mrp.group_mrp_manager"`), «Випустити на верстат» (`action_release`, `invisible="state != 'planned'"`, `btn-primary`), «Скасувати», «У чернетку» (`invisible="state not in ('error','cancel')"`), статусбар `draft,exported,optimizing,planned,released,running,done`. Попередження `sheets_warning` (`alert-warning`), `error` (`alert-danger`). Групи: «Замовлення» (`production_id`, `product_id`, `qty`, `workorder_id`, `workcenter_id`), «Матеріал» (`material_role`, `material_product_id`, `sheet_length_mm`, `sheet_width_mm`, `thickness_mm`), «План» (`plan_sheets`, `plan_waste_pct`, `plan_cut_length_m`, `plan_est_min`, `ext_job_id`, `job_order_id`, `gantry_job_id`), «Файли» (`csv_attachment_id`, `plan_attachment_id`, `mpr_attachment_ids` many2many_binary readonly); вкладки «Деталі» (`line_ids` editable у `draft`: `part_code`, `name`, `length_mm`, `width_mm`, `qty`, `grain`, крайки, `program`, `mpr_attachment_id`), «Команди» (`command_ids` readonly: `text`, `state`, `result`, `error`, `requested_at`); чатер |
| V-23 | `view_td_cut_map_search` | search | `name`, `production_id`, `ext_job_id`; фільтри за станами, «Помилки»; group by `state`, `workcenter_id` |
| V-24 | `view_td_machine_message_list` | list (editable) `td.machine.message` | `sequence` (handle), `message_id`, `name`, `category`, `loss_id`, `auto_apply`, `active` |
| V-25 | `view_mrp_production_form_td` | form inherit `mrp.mrp_production_form_view` | статбокс (`div[@name='button_box']`): «Карти розкрою» (`action_f3d_view_cut_maps`, `td_cut_map_count`), «Портал» (`action_f3d_view_gantry_jobs`, `td_gantry_job_count`); `<header>`: «Створити карту розкрою» (`action_f3d_create_cut_maps`, `groups="td_factory3d.group_td_manager"`, `invisible="state in ('draft','done','cancel')"`), «Подати плити порталом» (`action_f3d_feed_gantry`, `invisible="state in ('draft','done','cancel')"`) |
| V-26 | `view_mrp_workorder_form_td`, `view_mrp_workorder_list_td` | inherit `mrp.mrp_production_workorder_form_view_inherit` (form), `mrp.mrp_production_workorder_tree_editable_view` (list) | form: після `qty_produced` — `td_qty_counted`, `td_machine_state` (badge), `td_auto_started`, `td_partial_hold` (+ кнопки «Завершити неповною партією» `action_f3d_finish_partial` / «Зняти позначку» `action_f3d_clear_hold`, `groups="mrp.group_mrp_manager"`, `invisible="not td_partial_hold"`), кнопка «Надіслати на верстат» (`action_f3d_send_to_machine`, `groups="mrp.group_mrp_user"`, `invisible="not td_can_send or state not in ('ready', 'blocked')"`), сторінка «Верстат»: `td_run_min`, `td_setup_min`, `td_cut_map_ids`, `td_gantry_job_ids`; list: `td_qty_counted` (optional show), `td_machine_state` (optional show), `td_partial_hold` (optional hide) |
| V-27 | `view_td_cut_plan_import_wizard_form` | form M-25 | `map_id`, `file` (`filename="filename"`), footer «Імпортувати» / «Скасувати» |
| V-28 | `view_td_cut_part_import_wizard_form` | form M-26 | `bom_id`, `file`, `replace`, підказка формату (Додаток E), footer |
| V-29 | `view_mrp_workcenter_form_td`, `view_mrp_workcenter_productivity_list_td`, `view_mrp_workcenter_productivity_loss_form_td`, `view_product_template_form_td` | inherit `mrp.mrp_workcenter_view`, `mrp.oee_tree_view`, `mrp.oee_loss_form_view`, `product.product_template_form_view` | РЦ: статкнопка «Верстат» (`action_f3d_machine`, поле `td_machine_state` бейджем) у `button_box`; журнал часу (list): `td_source` (optional show), `td_downtime_id` (optional hide), `td_auto` (optional hide); причина втрати (form): `td_planned`; товар: група «Лист плити» (`td_sheet_length_mm`, `td_sheet_width_mm`, `td_thickness_mm`) на вкладці «Загальна інформація» (`//page[@name='general_information']`, `position="inside"`), видима `group_td_user` |
| V-30 | меню (`views/menus.xml`) | `ir.ui.menu`, `ir.actions.act_window` | таблиця нижче |
| V-31 | `res_config_settings_view_form_td_mc` | form inherit `base.res_config_settings_view_form` | відкривається пунктом `menu_td_mc_settings` (дія `action_td_mc_settings`, X-32); блок `<app string="Верстати" name="td_machine_connect">` (або `<block>` у застосунку «Завод 3D», якщо base дає застосунок): «Стоп-крани» (`td_mc_read_enabled`, `td_mc_auto_start_enabled`, `td_mc_write_enabled` — `groups="td_factory3d.group_td_admin"`), «Пороги» (мікрозупинка, пауза, завершення), «Лічильник» (`qty_sync_mode`, `qty_sync_s`), «OEE» (`coverage_min`, `oee_good`, `oee_warn`), «Портал» (допуск, підтвердження, авто-поповнення, авто-подача), «Карти розкрою» (`cutting_mode`, TTL), «Зберігання», кнопка міграції, `td_mc_migration_state` |

Меню (CB-09; `parent="td_factory3d.menu_td_root"`). Пункт параметрів модуля (`res.config.settings`, V-31) — під
`td_factory3d.menu_td_config` із sequence 40 (= резерв верстатів у CB-09; правило X-32); довідники підключення
верстатів, повідомлень і причин лишаються в корені модуля («Верстати → Налаштування»):

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_td_mc_root` | Верстати | `td_factory3d.menu_td_root` | 40 | `group_td_user` | — |
| `menu_td_mc_dashboard` | Огляд верстатів | `menu_td_mc_root` | 10 | `group_td_user` | `action_td_machine_dashboard` (`td.machine`, kanban,list,form) |
| `menu_td_mc_downtime` | Простої | `menu_td_mc_root` | 20 | `group_td_user` | `action_td_downtime` (list,kanban,form,graph,pivot; `context={'search_default_today': 1}`) |
| `menu_td_mc_downtime_tablet` | Простої без причини | `menu_td_mc_root` | 21 | `mrp.group_mrp_user` | `action_td_downtime_tablet` (kanban,form; `context={'search_default_not_confirmed': 1, 'search_default_today': 1}`) |
| `menu_td_mc_oee` | OEE | `menu_td_mc_root` | 30 | `group_td_user` | `action_td_oee_shift` (list,pivot,graph,form; `search_default_this_week`) |
| `menu_td_mc_log` | Журнал станів | `menu_td_mc_root` | 40 | `group_td_user` | `action_td_machine_state_log` (list,graph,pivot) |
| `menu_td_mc_event` | Події верстатів | `menu_td_mc_root` | 45 | `group_td_user` | `action_td_machine_event` (list,form) |
| `menu_td_mc_gantry` | Портал | `menu_td_mc_root` | 50 | `group_td_user` | — |
| `menu_td_mc_gantry_stack` | Стоси під порталом | `menu_td_mc_gantry` | 10 | `group_td_user` | `action_td_gantry_stack` (kanban,list,form) |
| `menu_td_mc_gantry_job` | Завдання порталу | `menu_td_mc_gantry` | 20 | `group_td_user` | `action_td_gantry_job` (list,kanban,form) |
| `menu_td_mc_cut` | Розкрій | `menu_td_mc_root` | 60 | `group_td_user` | — |
| `menu_td_mc_cut_map` | Карти розкрою | `menu_td_mc_cut` | 10 | `group_td_user` | `action_td_cut_map` (list,form) |
| `menu_td_mc_cut_part` | Деталі виробів | `menu_td_mc_cut` | 20 | `group_td_manager` | `action_td_cut_part` (list,form; `context={'search_default_group_bom': 1}`) |
| `menu_td_mc_config` | Налаштування | `menu_td_mc_root` | 90 | `group_td_manager` | — |
| `menu_td_mc_config_machine` | Верстати (підключення) | `menu_td_mc_config` | 10 | `group_td_manager` | `action_td_machine_config` (list,form) |
| `menu_td_mc_config_message` | Повідомлення верстатів | `menu_td_mc_config` | 20 | `group_td_manager` | `action_td_machine_message` (list) |
| `menu_td_mc_config_loss` | Причини простоїв | `menu_td_mc_config` | 30 | `group_td_manager` | `action_td_productivity_loss` (`mrp.workcenter.productivity.loss`, list,form — стандартні представлення `mrp.oee_loss_tree_view`/`oee_loss_form_view`; власної дії для причин у `mrp` 19 немає) |
| `menu_td_mc_settings` | Налаштування верстатів | `td_factory3d.menu_td_config` | 40 (резерв модуля CB-09; X-32) | `group_td_manager` | `action_td_mc_settings` (`res.config.settings`, `form`, `target='inline'`, `context={'module': 'td_machine_connect'}`) — V-31 |

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_machine_user,td.machine user,model_td_machine,td_factory3d.group_td_user,1,0,0,0
access_td_machine_manager,td.machine manager,model_td_machine,td_factory3d.group_td_manager,1,1,1,1
access_td_machine_state_log_user,td.machine.state.log user,model_td_machine_state_log,td_factory3d.group_td_user,1,0,0,0
access_td_machine_state_log_admin,td.machine.state.log admin,model_td_machine_state_log,td_factory3d.group_td_admin,1,1,1,1
access_td_downtime_user,td.downtime user,model_td_downtime,td_factory3d.group_td_user,1,0,0,0
access_td_downtime_mrp_user,td.downtime mrp user,model_td_downtime,mrp.group_mrp_user,1,1,0,0
access_td_downtime_mrp_manager,td.downtime mrp manager,model_td_downtime,mrp.group_mrp_manager,1,1,1,0
access_td_downtime_admin,td.downtime admin,model_td_downtime,td_factory3d.group_td_admin,1,1,1,1
access_td_machine_event_user,td.machine.event user,model_td_machine_event,td_factory3d.group_td_user,1,0,0,0
access_td_machine_event_admin,td.machine.event admin,model_td_machine_event,td_factory3d.group_td_admin,1,1,1,1
access_td_machine_message_user,td.machine.message user,model_td_machine_message,td_factory3d.group_td_user,1,0,0,0
access_td_machine_message_manager,td.machine.message manager,model_td_machine_message,td_factory3d.group_td_manager,1,1,1,1
access_td_oee_shift_user,td.oee.shift user,model_td_oee_shift,td_factory3d.group_td_user,1,0,0,0
access_td_oee_shift_admin,td.oee.shift admin,model_td_oee_shift,td_factory3d.group_td_admin,1,1,1,1
access_td_gantry_stack_user,td.gantry.stack user,model_td_gantry_stack,td_factory3d.group_td_user,1,0,0,0
access_td_gantry_stack_stock_manager,td.gantry.stack stock manager,model_td_gantry_stack,stock.group_stock_manager,1,1,0,0
access_td_gantry_stack_manager,td.gantry.stack manager,model_td_gantry_stack,td_factory3d.group_td_manager,1,1,1,1
access_td_gantry_job_user,td.gantry.job user,model_td_gantry_job,td_factory3d.group_td_user,1,0,0,0
access_td_gantry_job_mrp_user,td.gantry.job mrp user,model_td_gantry_job,mrp.group_mrp_user,1,1,1,0
access_td_gantry_job_manager,td.gantry.job manager,model_td_gantry_job,td_factory3d.group_td_manager,1,1,1,1
access_td_cut_part_user,td.cut.part user,model_td_cut_part,td_factory3d.group_td_user,1,0,0,0
access_td_cut_part_manager,td.cut.part manager,model_td_cut_part,td_factory3d.group_td_manager,1,1,1,1
access_td_cut_map_user,td.cut.map user,model_td_cut_map,td_factory3d.group_td_user,1,0,0,0
access_td_cut_map_manager,td.cut.map manager,model_td_cut_map,td_factory3d.group_td_manager,1,1,1,1
access_td_cut_map_line_user,td.cut.map.line user,model_td_cut_map_line,td_factory3d.group_td_user,1,0,0,0
access_td_cut_map_line_manager,td.cut.map.line manager,model_td_cut_map_line,td_factory3d.group_td_manager,1,1,1,1
access_td_downtime_reason_wizard,td.downtime.reason.wizard,model_td_downtime_reason_wizard,mrp.group_mrp_user,1,1,1,0
access_td_cut_plan_import_wizard,td.cut.plan.import.wizard,model_td_cut_plan_import_wizard,td_factory3d.group_td_manager,1,1,1,0
access_td_cut_part_import_wizard,td.cut.part.import.wizard,model_td_cut_part_import_wizard,td_factory3d.group_td_manager,1,1,1,0
```

AbstractModel `td.push.handler.machine_connect` і `td.viewer.provider.machines` рядків не потребують. Стандартні моделі
(`mrp.workorder`, `mrp.workcenter.productivity`, `stock.quant`, `maintenance.request`) — права їхніх модулів; модуль
змінює їх або від користувача (дії), або від технічного користувача (автодії), або `sudo()` (диспетчер, крони).

### 4.2 Групи

Власних груп немає (CB-10): `group_td_user` ⊂ `group_td_manager` ⊂ `group_td_admin`; `mrp.group_mrp_user` і
`stock.group_stock_user` вже мають `group_td_user` (base §4.2). Технічний користувач
`td_machine_connect.user_td_machine` (`data/res_users.xml`, `noupdate="1"`): `login="f3d_machine_bot"`,
`name="Верстати (автоматично)"`, `active=False`, `share=False`, `group_ids` = `base.group_user`,
`mrp.group_mrp_user`, `stock.group_stock_user`, `maintenance.group_equipment_manager` (читання заявок для R-08),
`td_factory3d.group_td_user`; `tz="Europe/Kyiv"`, `lang="uk_UA"` (якщо мова активна, інакше `en_US`); пароля немає
(вхід неможливий).

### 4.3 Record rules (`security/security.xml`)

| XML-id | Модель | Домен | Групи |
|---|---|---|---|
| `rule_td_machine_company` | `td.machine` | `[('company_id','in',company_ids)]` | глобальне |
| `rule_td_downtime_company` | `td.downtime` | `[('company_id','in',company_ids)]` | глобальне |
| `rule_td_oee_shift_company` | `td.oee.shift` | `[('company_id','in',company_ids)]` | глобальне |
| `rule_td_gantry_job_company` | `td.gantry.job` | `[('company_id','in',company_ids)]` | глобальне |
| `rule_td_cut_map_company` | `td.cut.map` | `[('company_id','in',company_ids)]` | глобальне |

Журнал станів, події, стоси — через верстат/локацію (одна компанія в демо); окремі правила не потрібні.

### 4.4 Захист полів і дій

- `td.machine`: поля стану (`state*`, `raw_*`, `pending_*`, `pieces_*`, `current_*`, `active_workorder_id`,
  `last_autostart_key`, `no_job_*`, `oee_shift_id`) — `readonly=True` у моделі; змінює лише диспетчер (`sudo`).
- `td.downtime.loss_id` — лише через `action_set_reason` (перевірки M-03); `reason_state='confirmed'` знімає
  лише `mrp.group_mrp_manager`.
- `td.cut.map.export_token_hash`, `export_token_expires` — `groups="td_factory3d.group_td_admin"`; у логах і чатері
  токен не друкується.
- Стоп-крани в `res.config.settings` — `group_td_admin` (M-23 `set_values`).
- Дії розбіжності стосу — `stock.group_stock_manager` (перевірка `has_group` у методах, `AccessError("Розбіжність
  стосу виправляє начальник складу.")`).

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)

| key (`td.machine_connect.` + …) | value | XML-id |
|---|---|---|
| `read_enabled` | не створюється в XML — ставить хук §5.3 крок 0 за `td.base.environment` (`test` → `True`, `prod` → `False`) | — |
| `auto_start_enabled` | `False` | `param_auto_start_enabled` |
| `write_enabled` | `False` | `param_write_enabled` |
| `micro_stop_s` | `120` | `param_micro_stop_s` |
| `pause_after_min` | `10` | `param_pause_after_min` |
| `finish_idle_s` | `60` | `param_finish_idle_s` |
| `qty_sync_mode` | `finish` | `param_qty_sync_mode` |
| `qty_sync_s` | `300` | `param_qty_sync_s` |
| `coverage_min` | `0.95` | `param_coverage_min` |
| `oee_good` | `0.75` | `param_oee_good` |
| `oee_warn` | `0.5` | `param_oee_warn` |
| `no_job_activity_min` | `15` | `param_no_job_activity_min` |
| `stack_diff_tolerance` | `0` | `param_stack_diff_tolerance` |
| `stack_diff_confirm_min` | `10` | `param_stack_diff_confirm_min` |
| `gantry_auto_replenish` | `False` | `param_gantry_auto_replenish` |
| `gantry_auto_feed` | `False` | `param_gantry_auto_feed` |
| `cutting_mode` | не в XML — хук крок 0: `test` → `collector`, `prod` → `manual` | — |
| `export_token_ttl_s` | `600` | `param_export_token_ttl_s` |
| `keep_log_days` | `400` | `param_keep_log_days` |
| `keep_event_days` | `90` | `param_keep_event_days` |
| `migration_report` | `{}` | `param_migration_report` |
| `gantry_status` | `{}` | `param_gantry_status` — службовий: останній статус порталу (R-23 п. 2), JSON ≤ 4 КБ |

Читання булевих — `param_bool` (§2). Відсутній `read_enabled` → умовчання CB-10.

### 5.2 Data-файли

| Файл | Записи | Зміст / джерело |
|---|---|---|
| `ir_sequence.xml` | 2 | `seq_td_gantry_job` (`code="td.gantry.job"`, `prefix="ПОРТ/"`, `padding=5`), `seq_td_cut_map` (`code="td.cut.map"`, `prefix="КР/"`, `padding=5`), `company_id=False` |
| `res_users.xml` | 1 | `user_td_machine` (§4.2) |
| `mrp_loss_data.xml` | 1 | `loss_unknown`: `name="Не вказано"`, `loss_id=mrp.category_availability`, `manual=True`, `sequence=99` |
| `mc_sources.xml` | 22 | Додаток C.1: 15 `opcua`, 4 `modbus_tcp`, 2 `rest_vendor`, 1 `td_machine`; `module='machine_connect'`, `collector_id=td_telemetry.collector_main` (крім `MC-DERIVED`), `read_enabled=True`, `write_enabled=False`; `equipment_id` не в XML (хук крок 3) |
| `mc_machine_messages.xml` | 10 | Додаток B.1 (`message_E0421` …), `loss_id` — `ref` на `mrp.block_reason*`/`loss_unknown` |
| `ir_cron.xml` | 5 | §6 |
| `td_actions.xml` | 3 | `action_td_mc_run_migration` (`td.machine`, `code`: `action = env['td.machine']._td_run_migration()`, `group_td_admin`), `action_td_downtime_confirm` (`td.downtime`, `binding_model_id`, `code`: `records.action_confirm()`, `mrp.group_mrp_manager`), `action_td_oee_period` (`td.oee.shift`, `binding_model_id`, R-13 п. 8) |
| `mc_machines.csv` | 35 | Додаток A: `code,protocol,source,io_unit,io_slot,auto_start_mode,operator_code` |
| `mc_signals.csv` | 18 шаблонів → 207 сигналів | Додаток C.2 (колонки `template,protocol,code,name,kind,…`); розгортає `hooks._signal_rows` для кодів Додатка A і GANTRY-1 |

### 5.3 `post_init_hook(env)` — кроки, ідемпотентність, очікувані кількості

`hooks.run_migration(env) -> dict` виконує кроки по черзі (кожен повертає лічильники); `post_init_hook(env)` =
`run_migration(env)` + запис звіту. Усе — у транзакції установки (`sudo`); виняток кроку 1–5 відкочує установку; крок 6
при помилці пише `state='partial'` і не відкочує. Логер `odoo.addons.td_machine_connect.hooks`, INFO на крок.

| # | Функція | Джерело | Що робить | Ідемпотентність | Копія демо | Чиста база |
|---|---|---|---|---|---|---|
| 0 | `params(env)` | `td.base.environment` | `read_enabled`, `cutting_mode`, якщо відсутні (§5.1) | лише відсутні | `read_enabled=True`, `cutting_mode=collector` | те саме |
| 1 | `losses(env)` | `mrp.block_reason0…7`, `ir.model.data` `factory3d.loss_tool/loss_break` | R-27 п. 1: переклади uk (якщо мова `uk_UA` активна і uk-назва = en), категорія «Доступність» демо-причинам без `loss_id`, `td_planned=True` для «Перерва» | лише порожні/неперекладені | `loss_translated: 7`, `loss_category_fixed: 2`, `loss_planned: 1` | `loss_translated: 7` (або 0 без uk), решта 0 |
| 2 | `sheets(env)` | `product.template` категорії «Плитні матеріали» з нульовими `td_sheet_*` | R-27 п. 2: регекс назви | лише нульові | `sheets_sized: 7` | 0 |
| 3 | `machines(env)` | `mc_machines.csv`, `mrp.workcenter.search_f3d(code)`, `maintenance.equipment.search_f3d(code)`, `hr.employee.search_f3d('OP-'+code)`, джерела з кроку data | upsert `td.machine` за `workcenter_id`; `source_id`, `protocol`, `io_slot`, `auto_start_mode` з CSV; `equipment_id`, `employee_id` (оператор, якщо є); `td.source.equipment_id` джерел `UA-<C>` = обладнання | upsert, `sig_*` — у кроці 4 | `machines: 35`, `with_operator: 28`, `with_equipment: 35` | `machines: 0` (РЦ без кодів — WARNING з кодами) |
| 4 | `signals(env)` | `mc_signals.csv`, наявні `td.signal` за `code` | R-27 п. 3: upsert 207 сигналів; наявним (2 — `equipment/GANTRY-1/cycles_today`, `vacuum_kpa`) — лише `source_id`, `address`, `period_s`, `store_period_s`, `module` не змінюється; `sig_*` верстатів | upsert за `code` | `signals_created: 205`, `signals_bound: 2`, `machines_wired: 35` | `signals_created: 207`, `machines_wired: 0` |
| 5 | `stacks(env)` | `stock.location` з `td_loc_kind='stack'` і `td_code =like 'PLT-%'`; `stock.warehouse.orderpoint` цих локацій | upsert `td.gantry.stack` за `location_id`, `orderpoint_id`; `_td_refresh()` (Odoo-частина) | upsert | `stacks: 27`, `orderpoints_linked: 23` | 0 |
| 6 | `demo_journal(env)` | `mrp.workcenter.productivity` (усі), `maintenance.request` | R-27 п. 4: `td_source='demo'` усім, де `td_source` = умовчання і `create_date` < установки модуля; 73 закритих простої без завдання → 73 `td.downtime` (`closed`), 1 відкритий → 1 `td.downtime` (`is_open`, CNC-2, `maintenance_request_id`=MR/00031), верстат CNC-2 `state='fault'`, `current_downtime_id`; **нових записів журналу часу — 0** | за `td_downtime_id` (повторно — пропуск) | `timelog_marked: 184`, `downtimes_created: 74`, `downtimes_open: 1`, `requests_linked: 1`, `timelog_created: 0` | `skipped` |
| 7 | `report(env, rep)` | — | `migration_report` = JSON усіх лічильників + `ts` + `state` (`done` / `partial` / `skipped`) | перезапис | `done` | `done` (кроки 3–6 нульові) |

`hooks._td_run_migration` (серверна дія) — лише `group_td_admin` (`AccessError`), повторює кроки 0–7, повертає
`display_notification` зі звітом.

### 5.4 `uninstall_hook(env)`

1. Крони модуля `active=False` (вони видаляються з модулем, крок — на випадок збою деінсталяції).
2. `ir.config_parameter` з ключами `td.machine_connect.%` — `unlink`.
3. Сигнали й джерела, створені хуком/data, **не** видаляються (дані telemetry, історія показань); джерела
   `td_machine` видаляються каскадом `selection_add` (`MC-DERIVED`), їхні сигнали лишаються з `source_id=False`.
4. Записи `mrp.workcenter.productivity` лишаються (стандартний журнал); поля `td_*` зникають; моделі `td.machine*`,
   `td.downtime`, `td.oee.shift`, `td.gantry.*`, `td.cut.*` видаляє Odoo разом із модулем (у README —
   попередження: «перед деінсталяцією вивантажте простої й OEE»).

### 5.5 Повторна установка

Хук ідемпотентний. Після деінсталяції поля `td_*` і моделі модуля зникають, тому повторна установка на тій самій
базі знову позначає записи журналу часу, створені до установки, як `demo` і знову створює простої (74 на копії
демо); записи, створені модулем під час попередньої установки (`td_auto`), після деінсталяції стають звичайними
записами журналу часу й позначаються як `demo` разом з іншими (відомо, прийнятно — деінсталяцію на проді не
планують).

### 5.6 `data/neutralize.sql`

```sql
-- td_machine_connect: нейтралізована копія проду.
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('td.machine_connect.read_enabled', 'td.machine_connect.auto_start_enabled',
               'td.machine_connect.write_enabled', 'td.machine_connect.gantry_auto_replenish',
               'td.machine_connect.gantry_auto_feed');
UPDATE ir_config_parameter SET value = 'manual' WHERE key = 'td.machine_connect.cutting_mode';
UPDATE td_cut_map SET export_token_hash = NULL, export_token_expires = NULL;
UPDATE td_machine SET read_enabled = false, auto_start_mode = 'off';
UPDATE ir_cron SET active = false
 WHERE id IN (SELECT res_id FROM ir_model_data WHERE module = 'td_machine_connect' AND model = 'ir.cron');
```

## 6. Крони й фонові процеси (`data/ir_cron.xml`)

Усі — від `base.user_root`, методи працюють `sudo()`; кожен верстат/стос/карта обробляється в `savepoint` (помилка
одного не зупиняє інших, `logger.exception`).

| XML-id | Назва | Інтервал | Модель / метод | Один прогін | Ліміти |
|---|---|---|---|---|---|
| `cron_td_mc_tick` | Верстати: такт | 1 хв, `active=True` | `td.machine._cron_tick` (DEC-19: за id, пачки по 10 з commit, `SKIP LOCKED` — верстат, зайнятий push, пропускається до наступного такту) | лише якщо `read_enabled`: R-02 п. 4, R-03 п. 3, R-05 п. 6, R-10 п. 2, R-12 п. 3, R-09 п. 9; стан джерела `MC-DERIVED` (M-19) | ≤ 35 верстатів, ≤ 10 с |
| `cron_td_mc_oee` | Верстати: OEE змін | 5 хв | `td.oee.shift._cron_oee` | R-14 | ≤ 35 × 2 записи, ≤ 20 с |
| `cron_td_mc_gantry` | Портал: звірка й завдання | 1 хв | `td.gantry.job._cron_gantry` | R-15 п. 1–5 (усі стоси), R-16 п. 2 (відправка `to_send`), п. 5 (тайм-аути), R-18 п. 1 (поповнення) | ≤ 27 стосів, ≤ 20 завдань, ≤ 10 с |
| `cron_td_mc_cutmap` | Розкрій: стан оптимізації | 1 хв | `td.cut.map._cron_cutmap` | R-20 п. 6 | ≤ 20 карт |
| `cron_td_mc_rotate` | Верстати: ротація журналів | 1 доба, `nextcall` = найближчі 03:10 Europe/Kyiv (ставить хук через `zoneinfo`) | `td.machine.state.log._cron_rotate` | `DELETE` журналу станів `date_end < now − keep_log_days` і подій `ts < now − keep_event_days` батчами по 20 000 | ≤ 60 с |

## 7. HTTP/JSON API, події, команди

### API-01 `GET /f3d/machine/cutmap/<int:map_id>/export` (FR-35)

`controllers/cutmap.py`, `type="http"`, `auth="public"`, `csrf=False`, `methods=["GET"]`. Порядок перевірок:
1. `Authorization: Bearer <токен колектора>` → `request.env['td.collector'].sudo()._authenticate(token)` (telemetry M-01), далі колектор має бути власником джерела сигналу команд оптимізатора `equipment/CUTOPT/cmd` (CMD-03, `cut_cmd`, джерело `REST-CUTOPT`; `td.cut.map._td_export_collector()`, M-1, AC-67);
   порожньо/невірний/токен іншого колектора → `401 {"error": {"code": "unauthorized", "message": "Невірний токен колектора"}}`.
2. Заголовок `X-F3D-Token` (16 hex, `^[0-9a-f]{16}$`; query-параметр `t` не приймається — URL потрапляє в access-log) → інакше `400 bad_token`.
3. `td.cut.map._td_check_export_token(map_id, t)`: карти немає → `404 not_found`; `sha256(t) != export_token_hash` →
   `403 forbidden`; `export_token_expires < now` → `410 expired`; стан ≠ `exported` → `409 bad_state`.
4. Відповідь `200`, `Content-Type: application/json; charset=utf-8`, `Cache-Control: no-store`:

```json
{"map": "КР/00012", "external_ref": "WH/MO/00233", "machine": "SAW-1", "material": "DSP16-ANT",
 "sheet": "2800x2070x16", "priority": 5, "parts": 48,
 "parts_csv": "PartId;Description;Material;Length;Width;Quantity;Grain;EdgeTop;EdgeBottom;EdgeLeft;EdgeRight;Program\r\nP001;Боковина;DSP16-ANT;720;560;2;1;EB2-ANT;;EB2-ANT;;\r\n…"}
```

5. Після формування відповіді — `export_token_hash = NULL` (одноразовий), чатер карти «Список деталей забрав колектор
   <код>». Розмір ≤ 1 МБ (≈ 5 000 деталей); більше → `413 too_large` (карта → `error` «Забагато деталей для однієї
   карти»). Ідемпотентність: повтор з тим самим `t` → `403`.

### 7.1 Події колектора → Odoo (telemetry API-05, CM-07)

Обгортка `PushEvent` telemetry (`event_id` = sha256 hex від `route + "\n" + source + "\n" + canonical_json(payload)`,
`route`, `ts` UTC, `remote` = код джерела, `headers={}`, `payload`). Схеми `payload`:

**EV-01 `mc_opcua`** (подія або тривога OPC UA, плагін `opcua`):

```json
{"kind": "alarm", "source": "UA-CNC-2", "machine": "CNC-2", "time": "2026-10-12T06:42:00.000Z",
 "message_id": "E0421", "message_name": "SpindleOverload", "category": 5, "severity": 1000,
 "text": "Помилка шпинделя осі Z", "texts": {"uk": "Помилка шпинделя осі Z", "en": "Spindle error axis Z"},
 "path": ["CNC-2", "Spindle", "Z"], "group": "Drive", "active": true, "acked": false, "args": {}}
```

Обов'язкові: `kind` (`event`|`alarm`), `source`, `machine` (код сцени), `time` (ISO з `Z`), `category` (0…5), `text`
(≤ 256). `message_id` ≤ 16, `severity` 1…1000.

**EV-02 `mc_woodstore`** (адаптер `woodstore`): `{"kind": "status", "source": "REST-WOODSTORE", "status": {…API-20…}}`;
`{"kind": "stacks", "source": …, "hash": "<sha256 списку>", "items": [ {…API-21…} ×27 ]}`; `{"kind": "jobs", "source": …,
"items": [ {…API-24…} ]}` (лише змінені з останнього разу); `{"kind": "events", "source": …, "items": [ {…API-27…} ]}`.

**EV-03 `mc_cutopt`** (адаптер `cutopt`): `{"kind": "job", "source": "REST-CUTOPT", "map": "КР/00012", "job": {…API-31…}}`;
`{"kind": "plan", "source": …, "map": "КР/00012", "job_id": "cj-00077", "plan": {…API-32…}}`; `{"kind": "mpr", "source":
…, "map": "КР/00012", "job_id": "cj-00077", "part": "P001", "text": "<MPR ≤ 200 КБ>"}`.

Усі події ≤ 256 КБ (telemetry API-05); більше — адаптер ділить (`stacks` — по 50, `jobs`/`events` — по 200 елементів).

### 7.2 Команди Odoo → пристрої (telemetry M-06/API-06/07, CR-01, CM-08)

Створюються лише `td.command._td_mc_create_command` (M-20, X-93). Основний канал (X-03): `td.command.payload` — об'єкт R-21
(telemetry 19.0.1.1.0), колектор виконує `call(signal, payload)` плагіна, повернений об'єкт → API-07 `data` →
`td.command.result_data`; `text` команди — довідковий підпис `cmd_label` (R-21). Запасний канал — текст граматики
R-21 без `payload` (`write()` плагіна; запасний `result` — R-21). Сигнали-адресати:

| ID | Сигнал | Джерело | `payload` (приклад) | Плагін робить | `result_data` |
|---|---|---|---|---|---|
| CMD-01 | `workcenters/<C>/job_cmd` | `UA-<C>` | `{"method": "StoreAndStart", "job": "WO00013", "qty": 14, "ref": "WH/MO/00233", "priority": 5}`, `{"method": "Stop", "job": "WO00013"}` | виклик `<C>.JobManagement.JobOrderControl.<method>` (R-22 п. 6) | `{"ReturnStatus": 0}` |
| CMD-02 | `equipment/GANTRY-1/cmd` | `REST-WOODSTORE` | `{"op": "feed", "stack": "PLT-03C", "target": "SAW-1", "sheets": 4, "product": "DSP16-ANT", "priority": 5, "ref": "WH/MO/00233"}`, `{"op": "cancel", "id": "wj-00412"}`, `{"op": "stack", "stack": "PLT-07C", "qty": 55, "product": "DSP16-SON", "lot": "DSP16-SON-2610-321"}` | API-25 / API-26 / API-23 (R-23 п. 5) | `{"id": "wj-00412", "state": "queued"}` / `{"id": "wj-00412", "state": "cancelled"}` / `{"id": "PLT-07C", "qty": 55}` |
| CMD-03 | `equipment/CUTOPT/cmd` | `REST-CUTOPT` | `{"op": "upload", "map": 12, "token": "9f2c41aa07b3e5d1"}`, `{"op": "status", "job": "cj-00077"}`, `{"op": "release", "job": "cj-00077", "machine": "SAW-1", "priority": 5}`, `{"op": "mpr", "job": "cj-00077", "part": "P001"}` | API-01 цього модуля → API-30; API-31/32; API-33; API-34 (R-24) | `{"job_id": "cj-00077", "state": "optimizing", "eta_s": 5}` / `{"job_id": "cj-00077", "state": "planned", "sheets": 7, "waste_pct": 11.4}` / `{"job_id": "cj-00077", "state": "released", "job_order_id": "cj-00077"}` / `{"part": "P001", "size_kb": 4}` |

## 8. Сервісна частина — пакет плагінів `f3d_collector_mc` (CM-06)

### 8.1 Пакет, залежності, установка

- Python 3.12; `requirements.txt`: `asyncua==1.1.6` (та сама версія, що в емуляторі iot_sim §8.1.2, A-20),
  `aiohttp==3.11.18` (як ядро telemetry §8.1.2), `cryptography==44.0.3` (сертифікати OPC UA); тести —
  `pytest`, `pytest-asyncio`, `pytest-timeout` тих самих версій, що в telemetry. Жодних серверів протоколів у коді
  пакета — лише в `tests/fakes/`.
- Установка в образ колектора: рядок `./services/collector_plugins/machine_connect` у
  `services/collector/requirements-extra.txt` (telemetry §8.3.2); entry points §0.2. Ядро telemetry
  (`load_plugins()`) знаходить `opcua` і `rest_vendor` без змін ядра; адаптери REST — група
  `factory3d_collector.rest_vendors` (`importlib.metadata.entry_points(group=…)`), завантажує `RestVendorPlugin`.
- Імпорти з ядра: `collector.plugins.base.SourcePlugin`, `PluginContext`; `collector.core.types.SourceCfg`,
  `SignalCfg`, `Reading`, `Health`, `PushEvent`; `collector.core.errors.ConnectError`, `PollError`, `WriteError`,
  `NotSupported`, `AllowlistDenied`.
- Схеми розширень (`schemas/*.ext.json`, JSON Schema 2020-12) перевіряються **додатково** до схем telemetry у
  `validate()` плагіна (CT-03: обов'язкові ключі не змінюються).

### 8.2 Конфігурація (змінні середовища колектора)

| Змінна | Тип / default | Призначення |
|---|---|---|
| `F3D_OPCUA_PASSWORD` | str / порожньо | пароль користувача OPC UA (`params.password_ref`); на стенді = `SIM_OPCUA_PASS` |
| `F3D_OPCUA_CERT` | path / порожньо | сертифікат клієнта DER (`params.cert_ref`), лише при `security_mode != "None"` |
| `F3D_OPCUA_KEY` | path / порожньо | приватний ключ PEM (`params.key_ref`) |
| `F3D_OPCUA_SERVER_CERT` | path / порожньо | очікуваний сертифікат сервера (`params.server_cert_ref`, розширення) — закріплення; порожньо на проді при `SignAndEncrypt` → `ConnectError("server certificate not pinned")` |
| `F3D_WOODSTORE_KEY` | str / **обов'язково для `REST-WOODSTORE`** | `X-Api-Key` (= `SIM_WOODSTORE_APIKEY`) |
| `F3D_CUTOPT_KEY` | str / **обов'язково для `REST-CUTOPT`** | `X-Api-Key` (= `SIM_JOBS_APIKEY`) |
| `F3D_MC_STATE_DIR` | path / `F3D_BUFFER_DIR` | курсори адаптерів (`woodstore_<source>.json`: `last_event_id`, `jobs_since`, `stacks_hash`) |
| `F3D_ALLOW_HOSTS` | — | (telemetry) має містити хост `iot-sim` (стенд) або IP верстатів/woodStore/оптимізатора (прод) |

Секрети — лише через `ctx.secrets(name)`; відсутня змінна → джерело `error: "secret F3D_… not set"` (telemetry §8.2).

### 8.3 Плагін `opcua` (`opcua.py`, `ua_session.py`, `nodeids.py`, `ua_values.py`) — R-22

```python
class OpcUaPlugin(SourcePlugin):
    type = "opcua"; version = "0.1.0"; push_mode = True
    address_schema = TELEMETRY_SCHEMA["opcua"] + EXT["address.opcua"]
    params_schema = TELEMETRY_SCHEMA["opcua"] + EXT["params.opcua"]
```

Ключі-розширення (A-16): `params.ns_uri` (URI простору екземплярів; на стенді `http://todo.ltd/f3d/iot_sim/instances/`),
`params.server_cert_ref`, `params.app_uri` (default `urn:todo.ltd:f3d:collector`); `address.ns_uri` (перекриває
параметр), `address.events` (bool, лише з `mode="subscribe"`), `address.io` (`"read"` default | `"write"` — сигнал
лише для команд, не підписується), `address.call` (`"job"` — команда CMD-01), `address.job_select` (`"running_or_first"`
— для сигналу `JobOrderList`), `address.ww_uri` (default `http://opcfoundation.org/UA/Woodworking/`), `address.isa_uri`
(default `http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/`).

1. **Сесії.** `SessionPool` (на процес) — одна `asyncua.Client` на ключ `(endpoint, security_mode, security_policy,
   username)`; джерела `UA-<C>` того самого endpoint ділять сесію (15 джерел стенда → 1 сесія); лічильник посилань,
   закриття при `disconnect()` останнього джерела.
2. **`connect()`**: `ctx.allowlist(urlparse(endpoint).hostname)`; `client = Client(url=endpoint, timeout=timeout_s)`;
   `client.application_uri = params.app_uri`; `client.name = "f3d-collector"`; безпека: `security_mode != "None"` →
   `await client.set_security(<клас політики з asyncua.crypto.security_policies за security_policy>, certificate=
   secrets(cert_ref), private_key=secrets(key_ref), server_certificate=secrets(server_cert_ref) або None, mode=
   ua.MessageSecurityMode.<security_mode>)`; `username` → `client.set_user(username)`, `client.set_password(
   secrets(password_ref))`; `await client.connect()`; `ns_array = await client.get_namespace_array()`; `await
   client.load_data_type_definitions()` (помилка → WARNING один раз; сигнали `job` → `q='bad'`, команди `call` →
   `WriteError("data types not loaded")`). Помилки → `ConnectError` без секретів.
3. **`subscribe()`** (для сигналів джерела з `io != "write"`): резолв `nodeid` (R-22 п. 1); групи: (а) `DataChange` —
   `sub = await client.create_subscription(params.publishing_interval_ms, DataHandler(self))`,
   `await sub.subscribe_data_change(nodes, sampling_interval=address.sampling_ms або 0)`; (б) події — `evsub =
   await client.create_subscription(publishing_interval_ms, EventHandler(self))`, `await evsub.subscribe_events(
   sourcenode=<C>.Events, evtypes=[WwBaseEventType, WwAlarmConditionType])` (типи резолвляться browse-шляхом у
   просторі `ww_uri`; не знайдено → `ua.ObjectIds.BaseEventType` з WARNING); (в) `mode="poll"` — власна задача,
   `client.read_values(nodes)` кожні `period_s`.
4. **Сповіщення.** `DataHandler.datachange_notification(node, val, data)` → `ua_values.to_reading(signal, data.
   monitored_item.Value, now)` (R-22 п. 2–4) → `ctx.emit(reading)`; `EventHandler.event_notification(event)` →
   `ua_values.event_payload(source, machine_code, event)` (EV-01, R-22 п. 5) → `ctx.emit_event(events.make_event(
   "mc_opcua", source.code, payload))`.
5. **Нагляд і переп'єднання.** Задача `watchdog` на сесію: кожні 5 с `await client.check_connection()`; виняток або
   `status_change_notification` з `Bad*` → усім джерелам сесії `Health(state='offline', error=…)`, для всіх
   сигналів — показання `q='bad'` (`text="bad"` для `state/mode/alarm/job`, лічильники — пропуск), `client.disconnect()`
   (тихо), бекоф 1, 2, 4 … 60 с, повтор п. 2, потім п. 3 для всіх зареєстрованих джерел; метрика
   `collector_mc_opcua_reconnects_total{endpoint}`.
6. **`call(signal, payload)`** (CR-01, X-03; основний шлях команд) — лише сигнали з `address.call == "job"` (інакше
   `NotSupported`); ядро вже перевірило 4 запобіжники; плагін додатково: `ctx.settings.write_enabled` (інакше
   `WriteError("write disabled")`); `cmdtext.check_payload("job", payload)` (R-21; помилка → `WriteError("bad_command: …")`);
   виклик R-22 п. 6; таймаут 10 с; повертає `{"ReturnStatus": 0}`. **`write(signal, value, text)`** — запасна текстова
   граматика: ті самі перевірки, `cmdtext.parse_cmd("job", text)` (помилка → `WriteError("bad_command: …")`) → той самий
   виклик → рядок `cmdtext.result_text(...)` (`"ok ReturnStatus=0"`).
7. **`health()`**: `online`, якщо сесія підключена і < 100 % елементів джерела мають `Bad*`; `error` — усі погані
   (текст «усі вузли Bad_…»); `offline` — сесії немає; `stats = {"items": n, "notifications": n, "events": n,
   "reconnects": n, "last_notification": iso}`.

### 8.4 Плагін `rest_vendor` (`rest_vendor.py`, `generic.py`) — R-23, R-24

```python
class RestVendorPlugin(SourcePlugin):
    type = "rest_vendor"; version = "0.1.0"; push_mode = False
```

Ключі-розширення: `params.vendor` (`woodstore` | `cutopt` | `generic`, default `generic`), `params.events_period_s`
(1…60, default 2), `params.stacks_period_s` (5…600, default 30), `params.jobs_period_s` (2…600, default 10);
`address.cmd` (`gantry` | `cutopt` — сигнал команд, не опитується), `address.default` (значення, якщо `json_path`
нічого не знайшов; default — пропуск показання), `address.io` (`read` | `write`).

1. `connect()`: `ctx.allowlist(urlparse(base_url).hostname)`; `aiohttp.ClientSession(base_url=params.base_url,
   timeout=ClientTimeout(total=timeout_s), headers=<за auth>)`: `api_key` → `{params.header or "X-Api-Key":
   secrets(key_ref)}`; `bearer` → `Authorization: Bearer secrets(key_ref)`; `basic` → `BasicAuth(user,
   secrets(password_ref))`; `verify_tls=false` дозволено лише для `http://` (для `https://` → `ConnectError("verify_tls
   false is not allowed for https")`); адаптер = entry point `params.vendor`; `await adapter.start(self)` (фонові задачі).
2. `poll(signals)` → `await adapter.poll(signals)` (сигнали з `io != "write"` і без `cmd`); `disconnect()` → `adapter.stop()`,
   закриття сесії.
3. `call(signal, payload)` (CR-01, X-03; основний шлях команд) → `await adapter.command(signal,
   cmdtext.check_payload(address.cmd, payload))` → об'єкт результату R-21 (≤ 64 КБ); `write(signal, value, text)` —
   запасна текстова граматика: `cmdtext.parse_cmd(address.cmd, text)` → той самий `adapter.command` → рядок
   `cmdtext.result_text(...)` (≤ 256); помилка схеми/граматики → `WriteError("bad_command: …")` без HTTP-запитів;
   сигнал без `address.cmd` або адаптер `generic` → `NotSupported`.
4. `GenericAdapter.poll`: групує сигнали за `(method, path, query)`; один запит на групу; `jsonpath.get(json_path, body)`
   (утиліта telemetry `collector.util.jsonpath`); число → `value`, рядок → `text` (≤ 64), `bool` → 0/1, `None`/немає →
   `address.default` або пропуск; `map` до тексту; HTTP ≥ 400 → `PollError("HTTP <code> <path>")`.

### 8.5 Адаптер `woodstore` (`woodstore.py`) — P-03, R-23

`WoodStoreAdapter(GenericAdapter)`: `poll` — як generic (статус `/api/v1/status`, активне завдання
`/api/v1/jobs?state=active`); додатково після кожного успішного `GET /api/v1/status` — подія `mc_woodstore` `kind='status'`,
якщо хеш `{state, current_job, aisles, alarms}` змінився. Фонові задачі (`start`):

| Задача | Період | Запит | Подія |
|---|---|---|---|
| `events_loop` | `events_period_s` (2 с) | `GET /api/v1/events?since=<last_event_id>` (перший запуск — без `since`) | `kind='events'`, `items` (≤ 200 на подію), курсор `last_event_id` = id останнього; `410`/невідомий курсор → скинути курсор |
| `stacks_loop` | `stacks_period_s` (30 с) | `GET /api/v1/stacks` | `kind='stacks'` (усі 27, по 50), якщо хеш змінився або минуло ≥ 15 хв від останньої відправки |
| `jobs_loop` | `jobs_period_s` (10 с) | `GET /api/v1/jobs?since=<jobs_since>` | `kind='jobs'`, лише елементи, чиї `(state, done)` змінились порівняно з пам'яттю; `jobs_since` = max `created/started/finished` |

Курсори зберігаються в `F3D_MC_STATE_DIR/woodstore_<source>.json` після кожної успішно поставленої в буфер події.
Команди (`address.cmd == "gantry"`, CMD-02): R-23 п. 5. Помилки HTTP: `401/403` → `Health.error="auth"`; `409` на
POST → `WriteError("CONFLICT: <message>")`; `5xx`/мережа → `PollError`/`WriteError`.

### 8.6 Адаптер `cutopt` (`cutopt.py`) — P-04, R-24

`CutOptAdapter`: `poll` — нічого (сигналів читання немає); команди (`address.cmd == "cutopt"`, CMD-03) — R-24. Для
`upload` адаптер робить **читання** з Odoo: `GET {F3D_ODOO_URL}/f3d/machine/cutmap/<map_id>/export` з заголовком `X-F3D-Token: <t>` (не в URL) окремою
`aiohttp.ClientSession` з `Authorization: Bearer <F3D_COLLECTOR_TOKEN>` (`ctx.settings`), TLS-перевірка як ядро
(`F3D_ODOO_CA`), таймаут 15 с; інших звернень до Odoo плагін не робить (A-14).

### 8.7 Протокольні карти

**P-01 (OPC UA, iot_sim §8.3.2; `<C>` — код верстата; простір `ns_uri`, на стенді індекс 2):**

| Сигнал | `nodeid` (до резолву) | Тип UA | Перетворення в `Reading` | `kind` | Напрям |
|---|---|---|---|---|---|
| `workcenters/<C>/state` | `ns=2;s=<C>.State.Machine.Overview.CurrentState` | `WwUnitStateEnumeration` (Int32) | `value=int`, `text=map[str(v)]` (`0 OFFLINE`, `1 STANDBY`, `2 READY`, `3 WORKING`, `4 ERROR`) | state | R |
| `workcenters/<C>/mode` | `ns=2;s=<C>.State.Machine.Overview.CurrentMode` | `WwUnitModeEnumeration` | `0 OTHER`, `1 AUTOMATIC`, `2 SEMIAUTOMATIC`, `3 MANUAL`, `4 SETUP`, `5 SLEEP` | state | R |
| `workcenters/<C>/alarm` | `ns=2;s=<C>.State.Machine.Flags.Alarm` | Boolean | `value=1/0`, `text` `on`/`off` | state | R |
| `workcenters/<C>/pieces_out` | `ns=2;s=<C>.State.Machine.Values.RelativePiecesOut` | UInt64 | `value=float(v)` | counter | R |
| `workcenters/<C>/job` | `ns=2;s=<C>.JobManagement.JobOrderControl.JobOrderList` + `job_select="running_or_first"` | `ISA95JobOrderAndStateDataType[]` | `text` = `JobOrderID` обраного елемента (≤ 64) або `"-"` (порожній список) | state | R |
| `workcenters/<C>/event` | `ns=2;s=<C>.Events` + `events: true` | події `WwBaseEventType`, `WwAlarmConditionType` | **не** показання: подія EV-01 (показання пише Odoo, A-27) | event | R |
| `workcenters/<C>/job_cmd` | `ns=2;s=<C>.JobManagement.JobOrderControl` + `io: "write"`, `call: "job"` | Methods `Store, StoreAndStart, Start, Stop, Pause, Resume, Cancel, Abort, Clear` | CMD-01 | state | W |

Еталони: OPC 40550-1 v1.02.0 (nodeset `Opc.Ua.Woodworking.NodeSet2.xml`, ModelVersion 1.2.0, 2025-06-01:
`WwUnitStateEnumeration` OFFLINE=0, STANDBY=1, READY=2, WORKING=3, ERROR=4; `WwUnitModeEnumeration` OTHER=0, AUTOMATIC=1,
SEMIAUTOMATIC=2, MANUAL=3, SETUP=4, SLEEP=5; `WwEventCategoryEnumeration` OTHER=0, DIAGNOSTIC=1, INFORMATION=2, WARNING=3,
ALARM=4, ERROR=5 — звірено 14.10.2026, https://reference.opcfoundation.org/Woodworking/v100/docs/ і
https://github.com/OPCFoundation/UA-Nodeset/tree/latest/Woodworking); OPC 40001-3 Job Management / OPC 10031-4 ISA-95 Job
Control — методи й структури `JobOrderControl` за iot_sim §8.3.2 (**ПРИПУЩЕННЯ** iot_sim, Q-01).

**P-02 (Modbus TCP, ADAM-6050, iot_sim §8.4.2; плагін telemetry `modbus_tcp`, адреси PDU, A-01 telemetry):** для верстата
з модулем `unit` і позицією `m`:

| Сигнал | `address` | `kind` | Період |
|---|---|---|---|
| `workcenters/<C>/state` | `{"fc": 2, "addr": 2m, "type": "bool", "map": {"0": "stop", "1": "run"}, "doc": "DI<2m> coil 0000<2m+1> в роботі"}` | state | 1 с |
| `workcenters/<C>/alarm` | `{"fc": 2, "addr": 2m+1, "type": "bool", "map": {"0": "off", "1": "on"}, "doc": "DI<2m+1> аварія"}` | state | 1 с |
| `workcenters/<C>/pieces_out` | `{"fc": 3, "addr": 4m, "count": 2, "type": "u32", "wordorder": "little", "doc": "HR 4000<4m+1>–… лічильник DI<2m>"}` | counter | 5 с |

`unit` — у `params` джерела (`MB-U80-IO1` … `MB-U83-IO4`, unit 80…83). Повна розкладка — Додаток A.

**P-03 (REST woodStore, iot_sim §8.5):** `base_url` `http://iot-sim:8082`, шляхи з префіксом `/api/v1`:

| Сигнал / задача | Метод, шлях, `json_path` | Тип | Період |
|---|---|---|---|
| `equipment/GANTRY-1/state` | `GET /api/v1/status` → `$.state` (`idle\|moving\|picking\|placing\|blocked\|error`) | state | 5 с |
| `equipment/GANTRY-1/cycles_today` | `GET /api/v1/status` → `$.cycles_today` | counter | 5 с |
| `equipment/GANTRY-1/vacuum_kpa` | `GET /api/v1/status` → `$.vacuum_kpa` | gauge | 5 с |
| `equipment/GANTRY-1/job` | `GET /api/v1/jobs` `query={"state": "active"}` → `$[0].id`, `default="-"` | state | 5 с |
| `equipment/GANTRY-1/stacks` | без адреси на колекторі — обчислює Odoo (кількість стосів з `ws_qty > 0`) на джерелі `MC-DERIVED` | gauge | — |
| `equipment/GANTRY-1/cmd` | `POST /api/v1/jobs` (`cmd: "gantry"`, `io: "write"`) | state | — |
| події / стоси / завдання | `GET /api/v1/events`, `/stacks`, `/jobs` (§8.5) | — | 2 / 30 / 10 с |

**P-04 (REST оптимізатор, iot_sim §8.6):** `base_url` `http://iot-sim:8083`; `POST /jobs` (multipart: `parts` — файл
`parts.csv` `text/csv; charset=utf-8`, `material`, `sheet`, `external_ref`, `machine`), `GET /jobs/{id}`, `GET
/jobs/{id}/plan`, `POST /jobs/{id}/release` (`{"machine", "priority"}`), `GET /jobs/{id}/mpr?part=`; сигнал команд
`equipment/CUTOPT/cmd` (X-18; `{"method": "POST", "path": "/jobs", "json_path": "$.job_id", "cmd": "cutopt", "io": "write"}`).

### 8.8 Логування й метрики

Логер `collector.plugin.<type>.<source>` (ядро); рівні: INFO — підключення/переп'єднання, виконані команди; WARNING —
`Bad*`-статуси (раз на хвилину на джерело), невідомі події, `4xx`; ERROR — винятки. Секрети маскує `SecretFilter`
ядра; тексти MPR і CSV у логи не пишуться (лише розмір). Метрики (через `ctx.metrics`):
`collector_mc_opcua_notifications_total{source}`, `collector_mc_opcua_events_total{source,kind}`,
`collector_mc_opcua_reconnects_total{endpoint}`, `collector_mc_rest_requests_total{source,path,code}`,
`collector_mc_commands_total{source,cmd,result}`.

## 9. Алгоритми й правила

Позначення: `ts` — час показання (UTC naive після `tools.states.parse_ts`: рядок ISO з зоною → UTC; aware `datetime` →
UTC; naive — як є); `now` — `fields.Datetime.now()`; «хв» — хвилини з двома знаками; приклади часу — за Києвом
(12.10.2026 — понеділок, EEST = UTC+3).

### R-01 Нормалізація стану (`tools/states.normalize(protocol, raw) -> str`, FR-01, CM-02)

`raw = {"state": str|None, "mode": str|None, "alarm": bool, "bad": bool}` (`state`, `mode` — тексти після `map`
сигналу; `bad` — останнє показання стану мало `q='bad'`). Перший рядок, що збігся:

| Протокол | Умова | Стан |
|---|---|---|
| будь-який | `bad` або `state is None` | `nodata` |
| `opcua` | `state == "ERROR"` | `fault` |
| `opcua` | `state == "WORKING"` | `working` (тривога при роботі не зупиняє — заявку дає telemetry, A-19) |
| `opcua` | `alarm` і `state in ("READY", "STANDBY", "OFFLINE")` | `fault` (аварійна кнопка / огородження без `Error`) |
| `opcua` | `state in ("READY", "STANDBY")` і `mode == "SETUP"` | `setup` |
| `opcua` | `state in ("READY", "STANDBY")` | `idle` |
| `opcua` | `state == "OFFLINE"` | `off` |
| `io` | `alarm` | `fault` |
| `io` | `state == "run"` | `working` |
| `io` | `state == "stop"` | `idle` |
| будь-який | інше (невідомий текст) | `nodata` + WARNING «невідомий стан <state>» (раз на годину на верстат) |
| `manual` | — | стан не обчислюється (лишається `nodata`) |

Приклади: `("opcua", WORKING, AUTOMATIC, False)` → `working`; `(READY, SETUP)` → `setup`; `(READY, AUTOMATIC)` → `idle`;
`(ERROR, AUTOMATIC, True)` → `fault`; `(OFFLINE, SLEEP)` → `off`; `(READY, AUTOMATIC, alarm=True)` → `fault`;
`(STANDBY, SLEEP)` → `idle`; `("io", run, alarm=False)` → `working`; `("io", run, alarm=True)` → `fault`;
`("io", stop)` → `idle`; `bad=True` → `nodata`. Стан емулятора (iot_sim R-14) демо 10:30: 29 РЦ `WORKING` → `working`,
SAW-3/VSAW-1/EDGE-3/UV-1/ASM-5 `READY` → `idle`, CNC-2 `ERROR` → `fault`.

### R-02 Мікрозупинки й момент фіксації стану (`_td_on_raw_state`, FR-02, A-05)

1. Показання з `ts < state_since` (пізнє, з буфера після новішого переходу) стан не змінює — лише `raw_*` не
   оновлюються, лічильник обробляється (R-11); лог DEBUG `late`.
2. `new == state`: якщо є `pending_state` — скасувати (`pending_state=False`, `pending_since=False`): мікрозупинка
   поглинута інтервалом `working`. Інакше нічого.
3. `new in ("working", "fault", "off", "nodata")` → `_td_commit_state(new, ts)` одразу, `pending_*` очищено.
4. `new in ("idle", "setup")`: якщо `state == "working"` і `micro_stop_s > 0` → якщо `pending_state` порожнє —
   `pending_since = ts`; `pending_state = new` (початок мікрозупинки — найраніший неробочий `ts`); фіксація — коли
   показання з `ts' ≥ pending_since + micro_stop_s` або крон (`now ≥ pending_since + micro_stop_s + 30 с`, 30 с — запас
   на доставку з буфера) → `_td_commit_state(pending_state, pending_since)` (заднім числом). Інакше (`state` не
   `working` або поріг 0) → `_td_commit_state(new, ts)` одразу.

Приклад (SAW-1, поріг 120 с): `working`; `READY` 10:02:00, `WORKING` 10:03:10 (70 с) → переходу немає, 70 с — у роботі;
`READY` 10:05:00 і далі без змін → крон о 10:07:30 фіксує `idle` з 10:05:00 (інтервал `working` закрито о 10:05:00).
`ERROR` 10:20:00 → `fault` одразу о 10:20:00.

### R-03 Немає даних (`_td_mark_nodata`, A-02)

1. telemetry позначила сигнал стану `stale` (M-18 `_mark_stale`) → `_td_commit_state("nodata", now, cause="system")`.
2. Показання стану з `q='bad'` (OPC UA `Bad_*`, плагін R-22 п. 2; Modbus — `quality` плагіна telemetry) →
   `normalize` дає `nodata` → R-02 п. 3.
3. На `nodata`: поточний простій закривається о `ts` (R-05 п. 4); автостарт/пауза/завершення не виконуються; таймери
   завдань не чіпаються; перше добре показання → звичайна обробка (з `nodata` перехід фіксується одразу).
4. Для P-01 плагін повторює останні значення кожні `heartbeat_s` (60 с, R-22 п. 4), `period_s` сигналів P-01 = 60 →
   `stale` через `max(3·60, 60) = 180 с` після обриву; P-02 опитується кожну 1 с → `stale` через 60 с (telemetry R-07).

### R-04 Фіксація стану й журнал (`_td_dispatch`, `_td_apply`, `_td_commit_state`, FR-03)

0. `_td_dispatch(readings, src)`: `code_map` (M-01); групування за верстатом; верстати з `active=False` або
   `read_enabled=False` пропускаються; для кожного (за `code`) у `savepoint`: `_td_lock()`, `_td_apply(items)`; виняток →
   `logger.exception`, `errors.append(code)`, наступний верстат.
1. `_td_apply(items)`: сортування за `(ts, порядок ролей state < mode < alarm < job < pieces)`; для ролі `state` —
   `raw_state = text` (або `None` при `q='bad'`, `raw["bad"]=True`), `mode` — `raw_mode`, `alarm` — `raw_alarm = (text ==
   "on" or value == 1)`; після кожного з цих трьох — `new = normalize(...)`, `_td_on_raw_state(new, ts)`; `job` —
   `_td_on_job(text, ts)` (R-09 п. 8, R-12); `pieces` — `_td_count(value, ts)` (R-11); `event` — ігнорується (A-27).
   Після циклу — один `write` полів `raw_*`, `raw_ts = max(ts)`.
2. `_td_commit_state(new, ts, cause)`: `new == state` → нічого; інакше закрити `current_log_id._td_close(ts)`;
   створити інтервал `{machine_id, state: new, date_start: ts, workorder_id: active_workorder_id, employee_id: останній
   працівник активного завдання, source: cause, raw: "<raw_state>/<raw_mode або alarm=0|1>", pieces_start: pieces_last}`;
   `state = new`, `state_since = ts`, `current_log_id`, `pending_*` очищено.
3. Закриття інтервалу: `date_end = max(ts, date_start)`; `in_ppt_min = |[date_start, date_end) ∩ PPT|` (R-26); для
   `working`/`setup` із завданням — `workorder_id.td_run_min` / `td_setup_min += duration_min` (R-28: усі хвилини
   інтервалу, не лише планові).
4. Простій: R-05 (закрити поточний; відкрити новий, якщо `new in DOWN_STATES`).
5. Завдання: `new == "working"` → `_td_resume(ts)` або `_td_autostart(ts)` (R-09, R-10); `new == "fault"` →
   `_td_autopause(ts, "fault")` (R-10 п. 1); `new == "nodata"` → нічого.
6. `_td_emit_state(ts)`, `_td_notify()`.

Приклад: SAW-1 `idle` з 09:50 → `WORKING` о 09:55:00 → інтервал `idle` 09:50–09:55 (5 хв ≥ 120 с —
простій лишається), новий `working` з 09:55, сигнал `workcenters/SAW-1/machine_state = "working"` (`ts` 06:55:00Z).

### R-05 Простій і записи журналу часу (`_td_open_downtime`, `_td_close_downtime`, FR-04, FR-05, A-04)

1. Відкриття (`new in DOWN_STATES`): `td.downtime {machine_id, date_start: ts, state_kind: new, workorder_id:
   active_workorder_id, loss_id: loss_unknown, reason_source: 'auto', reason_state: 'to_classify'}`; підказка R-07;
   якщо на РЦ уже є **відкритий** запис втрати оператора (`td_auto=False`, `loss_type in (availability, quality)`,
   без завдання) — він прив'язується (`td_downtime_id`) і його причина стає причиною простою (`reason_source='operator'`,
   `reason_state='to_confirm'`); `current_downtime_id`; R-08 п. 2.
2. Аварія (`fault`): одразу — `_td_close_timers(ts)` (R-10 п. 1, якщо дозволено автопаузу) і відкритий запис
   `mrp.workcenter.productivity {workcenter_id, loss_id: причина простою (за R-07 — «Поломка» `mrp.block_reason1`, якщо
   підказки немає), date_start: ts, description: hint_text або "Аварія верстата", td_downtime_id, td_source: 'machine',
   td_auto: True}` у технічному середовищі з контекстом `f3d_mc_auto` → РЦ `working_state='blocked'` (стандартне
   обчислення з відкритого запису втрати). `button_block()` не викликається (він закриває таймери часом `now`, а не `ts`).
3. Очікування / налагодження / вимкнення: поки простій триває, записів журналу часу немає (РЦ не блокується, оператор
   може стартувати завдання).
4. Закриття (`_td_close_downtime(ts)` на переході зі стану простою): `date_end = ts`; `ppt_min = |[start, ts) ∩ PPT|`;
   якщо `state_kind != 'fault'` і `ppt_min·60 < micro_stop_s` → простій видаляється (`unlink` `sudo`), записів не пишеться;
   інакше: відкриті записи втрат, прив'язані до простою (машинні й операторські), закриваються `date_end = ts`; для
   `idle/setup/off` — закриті машинні записи `{loss_id: причина, date_start, date_end, workorder_id: (лише setup) завдання
   простою, description: "<стан>: <причина>[; <hint_text>]", employee_id, td_downtime_id, td_source: 'machine',
   td_auto: True}` на інтервали `[start, ts)` **мінус** інтервали прив'язаних записів оператора, кожен ≥ 1 хв (без
   перекриття записів); `current_downtime_id=False`.
5. Тривалість у стандарті: для втрат доступності з календарем РЦ Odoo рахує `duration` лише робочими годинами
   (`mrp.workcenter.productivity.loss._convert_to_duration`) — обід і ніч не входять.
6. Межа робочого дня: крон о кінці **останнього** інтервалу планового часу дня закриває відкриті прості
   `idle/setup/off` (п. 4, `ts` = кінець інтервалу) і, якщо стан не змінився, відкриває новий о початку першого
   інтервалу наступного робочого дня (коли той настане); аварії не діляться.

Приклад (SAW-1, 07:00–10:30): `idle` 07:16–07:32 (16 хв, оператор обрав «Очікування матеріалу» о 07:20) → закритий
машинний запис 07:16–07:20 «Очікування матеріалу» + запис оператора 07:20–07:32 (закрито о 07:32 переходом у `working`);
`setup` 08:40–08:50 → запис «Налагодження» з WO00013, оператор змінив на «Заміна інструменту» → запис «Заміна інструменту»
10 хв; `idle` 10:12:30–10:13:40 (70 с) → поглинуто (R-02).

### R-06 Злиття з відмітками оператора (M-15 `create`, FR-06, A-03)

Тригер — створення запису `mrp.workcenter.productivity` поза контекстом `f3d_mc_auto` з `loss_type in (availability,
quality)` і без завдання (стандартне «Заблокувати» в «Цеху»/на формі РЦ).
1. Верстат РЦ (`td_machine_id`, `read_enabled`); немає → стандарт без змін.
2. Є відкритий простій: запис `td_downtime_id = простій`, `td_source = 'operator'` (`'master'` для
   `mrp.group_mrp_manager`); `простій._td_apply_reason(loss, source, employee)`; `reason_state = 'confirmed'` для
   майстра, інакше `'to_confirm'`; відкриті машинні записи простою (аварія) закриваються `date_end = запис.date_start`
   і отримують ту саму причину — записи не перекриваються.
3. Простою немає, верстат `working`: запис лишається (оператор знає наперед); коли верстат зупиниться — R-05 п. 1
   підхопить його причиною; якщо верстат працює ще `micro_stop_s` після створення запису, крон закриває запис
   (`date_end = now`, до `description` додається « (закрито: верстат працює)») — верстат — джерело істини про роботу.
4. Повернення верстата в `working` закриває всі записи простою (R-05 п. 4) → РЦ розблоковано.
5. Оператор натиснув «Розблокувати» (стандарт `unblock()` закриває всі відкриті записи) під час аварії: на наступному
   такті, якщо `state == 'fault'` і в простою немає відкритого машинного запису — відкривається новий (`now`, опис
   «Аварія триває»).

### R-07 Підказки причини (FR-07)

1. Подія EV-01 (`mc_opcua`): `td.machine.event` (дублікат `ext_event_id` → пропуск); `ingest` показання
   `workcenters/<C>/event` (`text = f"{message_id} {text}"[:64]`, `value=1`, контекст `f3d_mc_internal`); тривога з
   `active=False` → знайти активну подію того самого `message_id` верстата → `active=False`. Якщо відкритий простій
   почався не раніше `ts − 120 с` і категорія ≥ 3 і `reason_source in ('auto', 'hint')`: `event_id`, `hint_loss_id =
   message.loss_id` (немає повідомлення і категорія ≥ 4 → `mrp.block_reason1`), `hint_text = f"{message_id} {text}"`;
   `auto_apply` (або немає повідомлення і категорія ≥ 4) і `reason_source == 'auto'` → `_td_apply_reason(hint, 'hint')`,
   `reason_state='to_confirm'`; R-08 п. 3.
2. Відкриття простою (R-05 п. 1) шукає події верстата з `ts ≥ start − 120 с`, категорія ≥ 3 — найвища категорія,
   потім найпізніша → як п. 1.
3. `setup` → підказка `mrp.block_reason2` «Налагодження», `hint_text = "Режим верстата SETUP"`, застосовується
   (`hint`, `to_confirm`).
4. `fault` без події → `mrp.block_reason1` «Поломка», `hint_text = "Стан верстата ERROR"` (I/O: «Вхід аварії»),
   застосовується.
5. `idle`: на РЦ немає `ready`, але є завдання `blocked` (чекає попередньої операції) або `ready` з МО
   `reservation_state != 'assigned'` → `hint_loss_id = mrp.block_reason0` «Очікування матеріалу», `hint_text =
   "<МО>: чекає компонентів/попередньої операції"`, **не** застосовується (оператор підтверджує кнопкою).
6. `off` у плановому часі — без підказки (`to_classify`).

Приклад: CNC-2 о 09:42 `ERROR` + EV-01 `E0421` (категорія 5) → простій «Поломка» (`hint`, `to_confirm`),
`hint_text = "E0421 Помилка шпинделя осі Z"`; SAW-3 `idle` з 07:14, на РЦ WO00094 `blocked`… (у демо — `ready` з МО
`reservation_state='confirmed'`) → підказка «Очікування матеріалу», причина «Не вказано» до вибору оператора.

### R-08 Заявка ТО з тривоги (M-28, FR-08, A-19)

1. `maintenance.request.create` з `td_signal_id` ролі `alarm` (заявку створила telemetry R-05 при `alarm_states=["on"]`):
   якщо в верстата відкритий простій без заявки — `maintenance_request_id = заявка`; якщо в простою є `hint_text` —
   `заявка.message_post(body="Подія верстата: <hint_text> (<час Київ>)")`.
2. Відкриття простою `fault`: відкрита заявка (`stage_id.done=False`) з `td_signal_id = sig_alarm_id`, створена
   ≥ `start − 10 хв`, без простою → прив'язати (порядок telemetry → модуль не гарантований — обидві сторони шукають).
3. Подія після прив'язки (R-07 п. 1) → той самий `message_post` у заявку.
4. Закриття/підтвердження простою заявку не змінює; закриття заявки простій не змінює.

### R-09 Автостарт завдання (`_td_autostart`, `_td_match_job`, `_td_candidate`, FR-09…FR-11, A-09)

Передумови: `auto_start_enabled` (параметр) ∧ `auto_start_mode != 'off'` ∧ стан щойно став `working` (або змінилось
завдання верстата при `working`) ∧ контекст без `f3d_mc_internal`.
1. **Збіг завдання** (`_td_match_job(raw_job)`): `"-"`/порожньо → немає; `^WO0*(\d{1,9})$` або `^(\d{1,9})$` → `mrp.workorder`
   з цим id; `^cj-\d+$` → `td.cut.map` з `ext_job_id` → `workorder_id`; інше → немає. Придатне: існує,
   `workcenter_id == верстат.workcenter_id`, стан ∈ {`ready`, `progress`, `blocked`}. Текст непорожній, але не
   придатний → автостарту немає, діяльність майстру «Завдання верстата «<текст>» не знайдено в Odoo» (раз на текст).
2. **Одне в черзі** (`_td_candidate`, лише `job_or_single` і порожній текст завдання): завдань РЦ `progress` рівно 1 →
   воно; `progress` 0 і `ready` рівно 1 → воно; інакше немає.
3. Завдання вже активне (`active_workorder_id == wo`) і має відкритий таймер (будь-якого користувача) → нічого.
4. **Працівник** (`_td_pick_employee(wo)`), «дозволений» = `wc.employee_ids` порожні або містять його: (а) якщо
   `wo.employee_ids` непорожні — старт не потрібен (оператор уже працює), лише `active_workorder_id = wo`; (б) працівник
   останнього продуктивного запису цього РЦ від початку першого інтервалу планового часу сьогодні; (в)
   `hr.employee.search_f3d("OP-" + code)` (Додаток B base); (г) `верстат.employee_id`; (ґ) перший з `wc.employee_ids`;
   (д) без працівника.
5. Якщо РЦ `working_state == 'blocked'` — закрити його відкриті записи втрат `date_end = ts` (верстат працює — A-03).
6. Старт у технічному середовищі (`_td_tech_env()`): з працівником — `wo.start_employee(emp.id)`, без — `wo.button_start()`;
   новий відкритий запис журналу часу цього завдання → `date_start = ts`, якщо `ts < now`; `wo.td_auto_started = True`;
   `active_workorder_id = wo`, `wo_paused = False`, `no_job_since = False`; поточний інтервал стану `workorder_id = wo`,
   `employee_id`; `last_autostart_key = f"wo:{wo.id}@{ts.isoformat()}"`; чатер МО «Завдання <назва> стартував верстат
   <код> о <ЧЧ:ММ> (працівник <ім'я>)».
7. **Ідемпотентність**: рядок верстата заблоковано (`FOR UPDATE`, R-04 п. 0); той самий ключ → пропуск; відкритий таймер
   завдання → п. 3; Odoo-обмеження «cannot be started twice» не досягається. `UserError`/`ValidationError` від стандарту
   ловиться: діяльність на МО «Автостарт <код> не вдався: <текст>», чатер верстата, стан верстата не змінюється.
8. **Зміна завдання при роботі** (`_td_on_job`): `raw_job` змінився → для попереднього активного — R-12 (тригер
   `job_changed`); якщо стан `working` — п. 1…6 для нового тексту з `ts` показання.
9. **Робота без завдання**: після спроби немає активного → `no_job_since = ts` (якщо порожнє); крон: `now − no_job_since ≥
   no_job_activity_min` і не `no_job_notified` → діяльність `mail.mail_activity_data_todo` на верстаті для
   `workcenter_id.technician_user_id` (немає → `base.user_admin`) «<код> працює без завдання з <ЧЧ:ММ> — оберіть завдання в
   «Цеху»», `no_job_notified=True`; активне завдання з'явилось → діяльність `action_feedback("Завдання <назва>")`,
   прапори скинуто.

Приклади: SAW-1 `JobOrderID="WO00013"` → WO 13 (`ready`, SAW-1) → `start_employee(Олег Мельник)`; SLIDE-1 (I/O,
`job_or_single`): `ready` лише WO00101 → старт; EDGE-1 з двома `ready` (WO00014, WO00020) → автостарту немає, «працює без
завдання»; `JobOrderID="cj-00077"` → карта КР/00012 → WO розкрою.

### R-10 Автопауза й відновлення (`_td_autopause`, `_td_resume`, `_td_close_timers`, FR-12)

Передумови: `auto_start_enabled` ∧ `auto_pause` ∧ `active_workorder_id` у стані `progress`.
1. `fault` → одразу `_td_close_timers(ts)`: відкриті продуктивні записи (`loss_type in (productive, performance)`) завдань
   цього РЦ закриваються стандартним `_close()` у технічному середовищі, потім запис з найпізнішим `date_end` цього
   завдання отримує `date_end = max(ts, date_start)`, якщо `now − ts > 5 с`; `wo_paused = True`.
2. `idle`/`off` тривалістю ≥ `pause_after_min` (крон або показання) → те саме з `ts = state_since` (таймер закривається
   заднім числом на початок простою); `setup` таймер не зупиняє.
3. `working` і `wo_paused` і завдання ще `progress` → відновлення: працівник останнього продуктивного запису завдання
   (якщо дозволений) → `start_employee`, інакше `button_start`; `date_start = ts`; `wo_paused = False`. Завдання вже
   `done/cancel` → R-09.
4. `nodata` — нічого.

Приклад: CNC-2 WO00051 працює з 09:29; `ERROR` о 09:42 → таймер 09:29–09:42 (13 хв), простій «Поломка»; `clear`, `WORKING`
о 10:30 → простій закрито о 10:30 (48 хв), таймер WO00051 з 10:30.

### R-11 Лічильник деталей (`_td_count`, FR-13)

1. Перше значення (`pieces_last` порожнє) → `pieces_last = value`, приросту немає.
2. `delta = value − pieces_last`; `delta < 0` → скидання лічильника (початок зміни для `Relative*`, `Clear counter` ADAM):
   `delta = value` якщо `value ≤ 1000`, інакше 0 + WARNING; `delta > 1000` за одне показання → 0 + WARNING (обрив/перехід
   на `Absolute*`).
3. `pieces_last = value`, `pieces_ts = ts`; `current_log_id.pieces += delta`.
4. Стан `working`/`setup` і є `active_workorder_id` у `progress` → `wo.td_qty_counted += delta` (`sudo`).
5. `qty_sync_mode == 'live'` і `now − td_qty_synced_at ≥ qty_sync_s` → `wo.write({'qty_produced': min(td_qty_counted,
   qty_production)})` (технічне середовище; стандарт може зробити наступне завдання частково готовим — тому умовчання
   `finish`, A-10); `td_qty_synced_at = now`.

Приклад: SAW-1 `RelativePiecesOut` 0 (09:55) … 14 (10:25:48) → `td_qty_counted = 14`; о 07:00 наступної зміни
`Relative*` = 0 → `delta = 0`; ADAM SLIDE-1 `40001` 1 846 → 1 851 → `+5`.

### R-12 Автозавершення й неповна партія (`_td_try_finish`, FR-14, A-10)

Передумови: `auto_start_enabled` ∧ `auto_finish` ∧ `active_workorder_id` у `progress`; `remaining = wo.qty_remaining`,
`counted = wo.td_qty_counted`.
1. Тригер `job_changed` (є `sig_job_id`; `raw_job` змінився з id цього завдання на інший або `"-"`) або подія EV-01
   `I0002` з `{job}` цього завдання: `counted ≥ remaining` → завершити (п. 4); інакше — неповна (п. 5).
2. Без сигналу завдання (I/O, або OPC UA без `JobManagement`): `counted ≥ remaining` ∧ стан не `working` уже
   `finish_idle_s` (показання або крон) → завершити; `counted < remaining` → нічого (оператор продовжить або завершить сам).
3. Крон перевіряє п. 2 щохвилини.
4. Завершення (технічне середовище): `qty_produced = qty_production` (якщо `counted > qty_production` — чатер МО «Верстат
   порахував <counted>, план <qty>»); `stop_employee(wo.employee_ids.ids)`, якщо є; `button_finish()`; закриті таймери —
   `date_end = ts` (як R-10 п. 1); `active_workorder_id = False`, `wo_paused = False`; чатер МО «Завдання <назва>
   завершив верстат <код>: <counted> шт».
5. Неповна партія: `wo.td_partial_hold = True`; таймери закриваються (R-10 п. 1); діяльність на МО для
   `mrp.group_mrp_manager` (`user_id` = відповідальний МО або `base.user_admin`) «Неповна партія на <код>: <counted> з
   <qty>. Завершіть як є або дозапустіть»; МО не розбивається, `qty_production` не змінюється, `button_mark_done` не
   викликається. Майстер: `action_f3d_finish_partial` або `action_f3d_clear_hold` (M-13).

Приклади: SAW-1 WO00013 `qty 14`, `counted 14`, `JobOrderList` порожній о 10:25:48 → завершено; SLIDE-1 WO00101 `qty 8`,
`counted 8`, `stop` з 10:40:00 → о 10:41:00 завершено; SAW-2 `counted 12` з 14, завдання зняте → неповна партія.

### R-13 OEE за фактом (`tools/oee.compute_oee`, `td.machine._td_oee`, FR-16, A-07)

Вхід для верстата й вікна `[t0, t1)`: інтервали планового часу (R-26), інтервали станів (M-02, відкритий — до `t1`),
прості з `td_planned`, кількості й цикли завдань, брак.
1. `PPT_raw = Σ|PPT ∩ [t0, t1)|`; `planned_stop = Σ|прості з td_planned ∩ PPT|`; `nodata = Σ|інтервали nodata ∩ PPT \ planned|`.
2. `PPT = PPT_raw − planned_stop − nodata` (≥ 0); `PPT = 0` → `has_data = False`, показники 0.
3. `run = Σ|working ∩ PPT'|`, де `PPT' = PPT \ planned \ nodata`; `run_wo` — частина `run` з `workorder_id`;
   `setup/fault/idle/off` — так само; `down = setup + fault + idle + off`; `unexplained = max(0, PPT − run − down)`.
4. **A** = `run / PPT`.
5. Ідеальний цикл завдання, хв/шт: `cycle = operation_id.time_cycle_manual / capacity × 100 / wc.time_efficiency`, де
   `capacity = wc._get_capacity(wo.product_id, wo.product_uom_id)` (стандарт, умовчання 1); без операції — `wo.duration_expected
   / qty_production`. `ideal = Σ_wo pieces_wo × cycle_wo` (`pieces_wo` — Σ `pieces` інтервалів з цим завданням у вікні).
6. **P** = `min(1, ideal / run_wo)`; `performance_raw = ideal / run_wo`; `run_wo = 0` → `P = 1` (`performance_raw = 0`).
7. **Q** = `(total − bad) / total`, `total = Σ pieces_wo`, `bad = Σ stock.scrap.scrap_qty` (стан `done`, `workorder_id` —
   завдання цього РЦ, `date_done ∈ [t0, t1)`, товар = виріб МО) + Σ к-сть записів журналу часу категорії «Якість» не
   рахується (лише хвилини в Парето); `total = 0` → `Q = 1`.
8. **OEE** = `A × P × Q`. За період — суми хвилин, `ideal`, `total`, `bad` по змінах → A, P, Q з сум (не середнє
   відношень). `coverage = 1 − nodata / (PPT + nodata)`; `incomplete = coverage < coverage_min`.
9. Джерело `timelog` (у вікні немає інтервалів станів — РЦ без підключення або до установки): `run` = об'єднання
   продуктивних записів журналу часу ∩ PPT, прості — записи втрат за категоріями ∩ PPT (`setup` — причини «Налагодження»,
   «Заміна інструменту»; `fault` — «Поломка»; решта — `idle`), кількості — `qty_produced` завдань, завершених у вікні.
10. Втрати (`losses`) — Σ хвилин простоїв ∩ PPT за причиною (`loss_id`), за спаданням.

Приклади (зміна 12.10, вікно 07:00–10:30, `PPT = 210`):

| Верстат | Вхід | A | P | Q | OEE | Колір |
|---|---|---|---|---|---|---|
| SAW-1 (макет `oee=0.84`, `productive_minutes=176`) | `working` 176; прості 16 «Очікування матеріалу», 10 «Заміна інструменту», 8 «Не вказано»; емулятор: 80 шт × 2,2 хв = 176 (iot_sim R-16); брак 0 | 176/210 = **0,838** | 176/176 = **1,00** | **1,00** | **0,84** = переглядач | зелений (≥ 0,75) |
| SAW-1 (реальний варіант) | ті самі хвилини; 76 шт; брак 1 | 0,838 | 76·2,2/176 = **0,950** | 75/76 = **0,987** | 0,838·0,950·0,987 = **0,786** | зелений |
| CNC-2 (макет `oee=0.31`, 65 хв) | `working` 65 (32 шт × 2,0 = 64); прості 11 «Налагодження», 5 «Очікування матеріалу», 23 «Заміна інструменту», 48 «Поломка», 58 «Не вказано» | 65/210 = **0,310** | 64/65 = **0,985** | 1,00 | **0,305** | червоний (< 0,5) |
| SAW-3 (макет `oee=0.49`, 103 хв) | `working` 103 (114 шт × 0,9 = 102,6); прості 14 «Налагодження», 81 «Очікування матеріалу», 12 «Не вказано» | **0,490** | **0,996** | 1,00 | **0,488** | червоний |
| SAW-1, дві зміни (період) | зміна 1: PPT 480, run 400, ideal 396, 180 шт, брак 2; зміна 2: PPT 480, run 360, ideal 350, 159 шт, брак 0 | 760/960 = **0,792** | 746/760 = **0,982** | 337/339 = **0,994** | **0,773** | зелений |

### R-14 Записи OEE за зміну й крон (`_td_compute`, `_cron_oee`, FR-17, A-08)

1. Дата зміни `d` — дата за Києвом; вікно — від початку першого до кінця останнього інтервалу планового часу РЦ на `d`;
   інтервалів немає (вихідний) → запису немає.
2. `_cron_oee` (5 хв): для кожного активного верстата з `read_enabled`: запис за сьогодні (upsert за `(machine_id, date)`):
   `t1 = min(now, кінець вікна)`, стан `open`; якщо `now ≥ кінець вікна` → `closed`; запис за вчора у стані `open` →
   перерахунок на повне вікно і `closed`; `machine.oee_shift_id` = сьогоднішній.
3. Перерахунок: `machine._td_oee(t0, t1)` → усі поля M-06, `source`, `computed_at = now`.
4. Закритий запис крон не змінює; кнопка «Перерахувати» (`group_td_manager`) — так.
5. Без верстата (`td.machine` немає) OEE не рахується (вбудований провайдер переглядача лишає своє значення).
6. Ротація (`cron_td_mc_rotate`): журнал станів `date_end < now − keep_log_days`, події `ts < now − keep_event_days`;
   `td.oee.shift` і `td.downtime` не ротуються.

### R-15 Звірка стосу порталу (`td.gantry.stack._td_refresh`, FR-18, A-11)

1. `odoo_qty = Σ stock.quant.quantity` у `location_id`; `odoo_product_id` — товар з найбільшою к-стю; `odoo_lot_id` — його
   партія з найбільшою к-стю.
2. `fed_unconsumed = Σ done` завдань порталу `type='feed'`, `stack_id = цей`, стан ∈ {`active`, `done`}, МО яких не в
   `done/cancel` (листи вже в порталі «зникли», а в Odoo кванти зменшаться лише при закритті МО); завдання без МО
   (`origin='machine'`, без `external_ref` МО) не враховуються — це справжня розбіжність.
3. `expected_qty = odoo_qty − fed_unconsumed`; `diff = ws_qty − expected_qty`.
4. Стан: немає даних порталу (`ws_seen` порожнє або старше 10 хв) → `unknown`; `ws_product` і `odoo_product_id.default_code`
   обидва задані й різні → `diff` одразу (діяльність «у порталі <A>, в Odoo <B>»); `|diff| ≤ stack_diff_tolerance` →
   `ok`, `diff_since=False`; інакше `diff_since` порожнє → `diff_since = now`, `pending`; `now − diff_since ≥
   stack_diff_confirm_min` → `diff` + діяльність (одна відкрита на стос) для першого активного користувача
   `stock.group_stock_manager` (не `base.user_root`), інакше `base.user_admin`: «Стос <код>: портал <ws>, має бути
   <expected> (Odoo <odoo> − подано <fed>)». Повернення в `ok` → діяльність `action_feedback("Збігається")`.
5. Виклики: крон 1 хв (усі 27), EV-02 `stacks`, M-27 (поповнення), закриття МО (перерахунок стосів, з яких брали плиту —
   через крон).
6. Дії (`stock.group_stock_manager`): (а) «Прийняти з порталу»: цільовий залишок кванта `(odoo_product_id, location,
   odoo_lot_id)` = `ws_qty + fed_unconsumed` − (Σ інших квантів локації); `stock.quant` з `inventory_mode=True`:
   `inventory_quantity = ціль`, `action_apply_inventory()`; чатер; (б) «Виправити портал»: CMD-02 `stack` (`stack` —
   код, `qty` — `int(expected_qty)`, `product` — `default_code`, `lot` — партія або `null`; M-20; потребує запису).

Приклад: `PLT-01B` Odoo 45 арк. DSP16-WNG (партія DSP16-WNG-2610-114); завдання ПОРТ/00003 подало 7 для МО у роботі →
`fed=7`, `expected=38`; портал 38 → `ok`; портал 36 → `diff=−2`, `pending` → через 10 хв `diff`; «Прийняти з порталу» →
квант 36 + 7 = 43 → `expected=36` → `ok`.

### R-16 Завдання порталу (`td.gantry.job`, FR-19)

1. `_td_from_production(mo, workorder=None, cut_map=None, sheets=None)`: завдання розкрою = `workorder` або перше
   завдання МО не в `done/cancel` на РЦ з кодом ∈ `GANTRY_TARGETS` (немає → `UserError("У МО %s немає завдання розкрою на
   SAW-1…3 або NEST-1.")`); плита = `cut_map.material_product_id` або товар сировинного руху МО з
   `td_thickness_mm ≥ 8` і найбільшою к-стю; к-сть = `sheets` або `cut_map.plan_sheets` або `product_uom_qty` руху −
   Σ `sheets` наявних непоскасованих завдань цього МО й товару (≤ 0 → `UserError("Плити для %s уже подано.")`);
   стос — локація зарезервованого рядка руху, якщо це стос `PLT-*` (найбільша к-сть), інакше порожньо (портал обере);
   партія — з того рядка. Наявне завдання цього МО й товару у стані `draft…active` → повертається воно (без дубля).
   Автоподача (`gantry_auto_feed`): крон для кожного РЦ з `GANTRY_TARGETS` бере перше завдання черги (`progress`, інакше
   `ready` з найменшим `production_id.name`) МО без завдання порталу → створює в стані `to_send`.
2. `_td_send` (крон, `to_send`): CMD-02 `feed` (R-21: `stack` — код стосу або `null`, `target`, `sheets`, `product` —
   `default_code`, `priority`, `ref` — назва МО) — команда на `equipment/GANTRY-1/cmd` (M-20) → `sent`, `command_id`. Запис вимкнено → лишається `to_send`, `error =
   "Запис вимкнено: <що>"` (оновлюється лише при зміні тексту).
3. Результат команди: `done` → `ws_id = result_data["id"]` (запасний режим — `result`), стан `queued` (якщо події ще не
   дали пізнішого); `failed` → `error`,
   стан `error`; `expired` → `error = "Колектор не забрав команду"`.
4. Події EV-02 (`jobs`, `events`): за `ws_id`; невідомий `ws_id` → нове завдання `origin='machine'`: `external_ref` = назва
   МО → `production_id`; `product`/`stack`/`target` за кодами; стани woodStore → Odoo: `queued`→`queued`, `active`→`active`,
   `done`→`done`, `cancelled`→`cancelled`, `error`→`error`; `done` = поле `done`; `sheet_placed` → `sheet_log` (дублікат
   за id події пропускається), `done = max(done, len(sheet_log))`; `job_finished` → `done`; `stack_empty` → `stack._td_refresh()`,
   чатер; `alarm` → чатер обладнання GANTRY-1. Карта розкрою у стані `released` з тим самим МО → `gantry_job_id`.
5. Таймаути (крон): `active` без змін > 30 хв → чатер «Завдання порталу без руху 30 хв».
6. Скасування: `draft/to_send` → `cancelled` локально; `sent/queued/active` → CMD-02 `cancel` (`id` = `ws_id`; потребує запису,
   інакше `UserError("Скасування в порталі потребує дозволу запису.")`) → `done` команди → `cancelled`.
7. Перехід у `done` → R-17.

Приклад: WH/MO/00233 → ПОРТ/00007: `feed`, `PLT-03C`, SAW-1, 4 арк. DSP16-ANT, партія DSP16-ANT-2613-130, `payload`
`{"op": "feed", "stack": "PLT-03C", "target": "SAW-1", "sheets": 4, "product": "DSP16-ANT", "priority": 5, "ref":
"WH/MO/00233"}` (`text` — `feed;PLT-03C;SAW-1;4;DSP16-ANT;5;WH/MO/00233`) → `result_data.id = wj-00412` → `queued` →
`active` → 4 × `sheet_placed` → `done`.

### R-17 Списання плити в МО (`_td_consume`, FR-20, A-12)

1. Лише `type='feed'` з МО у `confirmed/progress/to_close` і товаром; `n = done − consumed_qty` ≤ 0 → нічого.
2. Рух — перший сировинний рух МО з цим товаром не в `done/cancel`.
3. Розподіл листів за (стос, партія): з `sheet_log` (стос кожного листа), партія — `odoo_lot_id` стосу або `lot_id` завдання.
4. Для кожної групи `(location, lot, k)`: незібрані (`picked=False`) рядки руху в інших локаціях зменшуються на `k`
   (від найбільшого); рядок `(location, lot)` руху збільшується на `k` або створюється, `picked=True`; рух
   `picked=True`, коли Σ зібраного ≥ `product_uom_qty`. Стандарт перераховує резерв квантів; `UserError` (недостатньо в
   кванті) → чатер завдання «Не вдалося списати: <текст>», `consumed_qty` не змінюється.
5. `consumed_qty += k`.

Приклад: WH/MO/00233, рух 128 (4 арк. DSP16-ANT, резерв `PLT-03C`) → портал подав 4 з `PLT-03C` → рядок `PLT-03C`,
партія DSP16-ANT-2613-130, 4, `picked=True`; `consumed_qty=4`; при закритті МО квант `PLT-03C` зменшиться на 4.

### R-18 Поповнення під портал (FR-21)

1. Крон: стоси з правилом, у яких `ws_qty` (або `expected_qty`, якщо `unknown`) < `min_qty` (10), без відкритого
   переміщення з `location_dest_id = стос`; `gantry_auto_replenish` → `orderpoint_id.action_replenish()` (стандарт —
   WH/INT за правилом «Стелажі → портал»), не частіше 1 разу на годину на стос; інакше нічого (кнопка).
2. Кнопка «Поповнити» → те саме без умови параметра; немає правила → `UserError("Для стосу %s немає правила поповнення.")`.
3. Виконане переміщення в стос (M-27) → `_td_refresh()`; CMD-02 `stack` (`qty` — `int(expected_qty)`, `product` —
   `default_code`, `lot` — партія або `null`; якщо дозволено), інакше діяльність для відповідального переміщення «Оновіть стос <код> у woodStore:
   <n> арк. <товар>».

Приклад: `PLT-08A` портал 9 < 10 → WH/INT із `RCK-R3-3C` (як WH/INT/00073) → виконано (стос 9 + 45) → команда
`{"op": "stack", "stack": "PLT-08A", "qty": 54, "product": "DSP16-WHT", "lot": null}` (якщо партія не відстежується в
стосі; `text` — `stack;PLT-08A;54;DSP16-WHT;-`).

### R-19 Карта розкрою з МО (`_td_create_for`, `action_build_lines`, CSV, FR-23, FR-24)

1. Плити МО — сировинні рухи (не `done/cancel`) з `td_sheet_length_mm > 0`; роль `main` — товщина ≥ 8 (найбільша к-сть),
   `back` — < 8; немає → `UserError("У МО %s немає плити для ролі «%s».")`.
2. Специфікація — `production.bom_id` (немає → `UserError("У МО %s немає специфікації.")`); деталі — активні `td.cut.part`
   цієї специфікації з `material_role = роль` або `role='product'` і `material_product_id = плита`; немає → `UserError(
   "Для специфікації «%s» немає деталей ролі «%s» — заповніть «Деталі виробів».")`.
3. Рядок: `qty = ceil(part.qty × map.qty)`, розміри, текстура, крайки, програма, `part_code`, `sequence`.
4. Вміщення: текстура `0` — `(L ≤ SL ∧ W ≤ SW) ∨ (L ≤ SW ∧ W ≤ SL)`; `1`/`2` — лише `L ≤ SL ∧ W ≤ SW` (обертати не можна);
   `SL × SW` — лист карти (2800 × 2070).
5. CSV (`tools/cutcsv.build_parts_csv`): UTF-8 без BOM, CRLF, роздільник `;`, заголовок
   `PartId;Description;Material;Length;Width;Quantity;Grain;EdgeTop;EdgeBottom;EdgeLeft;EdgeRight;Program` (iot_sim §8.6.1);
   `Description` — назва з `;` → `,`, переносами → пробіл, без початкових `=`, `+`, `-`, `@` (захист від формул у
   таблицях), ≤ 64; `Material` — `default_code` плити.
6. Завдання розкрою карти — перше завдання МО не в `done/cancel` на РЦ з кодом ∈ {`SAW-1`, `SAW-2`, `SAW-3`, `NEST-1`,
   `SLIDE-1`, `VSAW-1`}.

Приклад (тестові деталі `tests/data/parts_BR-K4.csv`, не дані модуля — Q-04): WH/MO/00233 «Комод 4 шухляди» × 14,
деталь `P001` «Боковина» 720 × 560, 2 шт/виріб, текстура 1, крайка EB2-ANT зверху й зліва → рядок
`P001;Боковина;DSP16-ANT;720;560;28;1;EB2-ANT;;EB2-ANT;;`.

### R-20 Оптимізація, план, випуск (FR-25, FR-26)

1. «На оптимізацію» (`collector`, стан `exported`/`error`): `t = _td_new_export_token()`; CMD-03 `upload` (`map` — `map.id`,
   `token` — `t`; M-20, `td_cut_map_id`); стан `optimizing`. Запис вимкнено → `UserError` з текстом M-20.
2. Результат `upload`: `done` → `ext_job_id = result_data["job_id"]` (`cj-00077`; запасний режим — перше слово
   `result`); `failed/expired` → `error`, стан `error`.
   EV-03 `job` → `_td_apply_job` (карта за `job.job_id` = `ext_job_id`, інакше за `map`): `optimizing` → `optimizing`;
   `planned` → підсумок плану з `job.plan` (`sheets`, `waste_pct`, `cut_length_m`, `est_min`); `released` → `released`,
   `job_order_id = job.job_id`; `running` → `running`; `done` → `done`; `error` → `error`, `error = job.error`.
3. EV-03 `plan` → `_td_apply_plan(plan)` (`cutcsv.parse_plan`: `total_sheets` ціле ≥ 1, `waste_pct` 0…100, `sheets` —
   список з `no`, `parts[]`); `plan_json`, `plan_sheets = total_sheets`, `plan_waste_pct`; вкладення `<номер>_plan.json`;
   стан `planned`; для рядків із `program` і РЦ ЧПК (`NEST-1`) — CMD-03 `mpr` (`job` — `ext_job_id`, `part` —
   `part_code`; по одному); EV-03 `mpr` →
   вкладення `<part_code>.mpr` (`text/plain`), `line.mpr_attachment_id`, `mpr_attachment_ids`.
4. «Оновити потребу МО» (`mrp.group_mrp_manager`): `product_uom_qty` руху плити = `plan_sheets`; чатер МО «Потреба в <товар>
   за картою <номер>: <було> → <стало> арк.».
5. «Випустити на верстат» (`planned`): `collector` → CMD-03 `release` (`job` — `ext_job_id`, `machine` — код РЦ,
   `priority` 5); результат `done` → `released`,
   `released_at`, `job_order_id`; Odoo **не** створює завдання порталу — оптимізатор при випуску сам ставить у woodStore
   `feed` на `total_sheets` (iot_sim API-33), дзеркало R-16 п. 4 прив'язує його до МО й карти. `manual` → кнопка ставить
   `released` (випуск — в intelliDivide вручну).
6. Крон: карти `optimizing` з `ext_job_id` і без команди `queued/sent` молодшої за 60 с → CMD-03 `status` (`job` —
   `ext_job_id`); `optimizing`
   > 30 хв → `error` «Оптимізатор не відповів 30 хв»; `released` → `running`, коли завдання розкрою стартувало
   (`progress`), → `done`, коли воно `done`; прострочені токени експорту (`export_token_expires < now`) → очистити.

Приклад: КР/00012 (WH/MO/00231, 48 деталей) → `cj-00077` → план 7 арк., відхід 11,4 %, різ 182,6 м, 31 хв (iot_sim API-31);
у МО 8 арк. → попередження немає; «Випустити» → `JobOrderList` SAW-1 отримує `cj-00077` → автостарт (R-09 п. 1) → портал
подає 7 листів.

### R-21 Корисне навантаження команд і запасна текстова граматика (`tools/commands.py` = `f3d_collector_mc/cmdtext.py`, CM-08, X-03)

Основний канал — `td.command.payload` (telemetry M-06, CR-01, 19.0.1.1.0): JSON-об'єкт ≤ 64 КБ; колектор передає його
`call(signal, payload)` плагіна (telemetry §8.3.2), повернений об'єкт — API-07 `data` → `td.command.result_data`.
Текстова граматика (поля через `;`, весь текст ≤ 64 символи) лишається **запасною**: Odoo створює текстову команду лише
коли в `td.command` немає поля `payload` (M-20 п. 4); плагіни приймають її в `write(signal, value, text)` і виконують так
само, як `call()` (так працюють і команди, які інженер створив вручну у формі telemetry V-17 лише з текстом). Вид
команди — з адреси сигналу: `address.call == "job"` (`opcua`) → `job`; `address.cmd` ∈ {`gantry`, `cutopt`}
(`rest_vendor`) → той самий вид.

Значення полів (і в `payload`, і в тексті): `CODE` `^[A-Z0-9][A-Z0-9\-]{0,31}$`; `REF` `^[A-Za-z0-9/_\-\.]{1,32}$`;
`JOB` `^[A-Za-z0-9_\-\.]{1,32}$`; `INT` ціле 1…9999 (текст `^\d{1,4}$`); `PRIO` ціле 1…9 (текст `^[1-9]$`); `LOT`
`^[A-Za-z0-9_\-\.]{1,40}$` або `null` (текст `-`); `ID` ціле 1…999 999 999 (текст `^\d{1,9}$`); `TOKEN`
`^[0-9a-f]{16}$`; `METHOD` ∈ {`Store`, `StoreAndStart`, `Start`, `Stop`, `Pause`, `Resume`, `Cancel`, `Abort`, `Clear`};
у `payload` числа — JSON-цілі (не рядки й не `bool`), ключі — точно за таблицею (відсутній або зайвий ключ — помилка;
порядок перевірки: `method`/`op`, далі ключі в порядку таблиці, далі зайві).

| Вид | Операція | `payload` | Результат `call()` → `result_data` | Запасний текст | Запасний `result` |
|---|---|---|---|---|---|
| `job` (CMD-01) | `Store`, `StoreAndStart` | `{"method": METHOD, "job": JOB, "qty": INT, "ref": REF, "priority": PRIO}` | `{"ReturnStatus": 0}` | `METHOD;JOB;INT;REF;PRIO` | `ok ReturnStatus=0` |
| `job` (CMD-01) | `Start`, `Stop`, `Pause`, `Resume`, `Cancel`, `Abort`, `Clear` | `{"method": METHOD, "job": JOB}` | `{"ReturnStatus": 0}` | `METHOD;JOB` | `ok ReturnStatus=0` |
| `gantry` (CMD-02) | `feed` | `{"op": "feed", "stack": CODE або null (портал обирає), "target": CODE, "sheets": INT, "product": CODE, "priority": PRIO, "ref": REF}` | `{"id": "wj-00412", "state": "queued"}` (API-25) | `feed;STACK;CODE;INT;CODE;PRIO;REF` (`STACK` — `CODE` або `*` = `null`) | `wj-00412` |
| `gantry` (CMD-02) | `cancel` | `{"op": "cancel", "id": JOB}` | `{"id": "wj-00412", "state": "cancelled"}` (API-26) | `cancel;JOB` | `cancelled` |
| `gantry` (CMD-02) | `stack` | `{"op": "stack", "stack": CODE, "qty": INT, "product": CODE, "lot": LOT}` | `{"id": "PLT-07C", "qty": 55}` (API-23) | `stack;CODE;INT;CODE;LOT` | `stack PLT-07C=55` |
| `cutopt` (CMD-03) | `upload` | `{"op": "upload", "map": ID, "token": TOKEN}` | `{"job_id": "cj-00077", "state": "optimizing", "eta_s": 5}` (API-30) | `upload;ID;TOKEN` | `cj-00077 optimizing` |
| `cutopt` (CMD-03) | `status` | `{"op": "status", "job": JOB}` | `{"job_id": "cj-00077", "state": "planned", "sheets": 7, "waste_pct": 11.4}` (API-31; `sheets`/`waste_pct` — з `plan`, інакше `null`) | `status;JOB` | `planned 7 11.4` або `<state>` |
| `cutopt` (CMD-03) | `release` | `{"op": "release", "job": JOB, "machine": CODE, "priority": PRIO}` | `{"job_id": "cj-00077", "state": "released", "job_order_id": "cj-00077"}` (API-33) | `release;JOB;CODE;PRIO` | `released cj-00077` |
| `cutopt` (CMD-03) | `mpr` | `{"op": "mpr", "job": JOB, "part": JOB}` | `{"part": "P001", "size_kb": 4}`; MPR немає (`404`) → `{"part": "P001", "size_kb": null}` | `mpr;JOB;JOB` | `mpr P001 4 КБ` / `no mpr` |

Функції (чисті, без Odoo-імпортів; `ValueError("<поле>: …")` при помилці):
- `build_payload(kind, op, **fields) -> dict` — об'єкт за таблицею; `check_payload(kind, payload) -> dict` — перевірка
  готового об'єкта (плагін, перед будь-яким мережевим викликом), повертає копію;
- `build_cmd(kind, op, **fields) -> str` — запасний текст (додатково: `;` у значеннях і довжина ≤ 64);
  `parse_cmd(kind, text) -> dict` — повертає **той самий** об'єкт, що `build_payload`
  (`parse_cmd(k, build_cmd(k, op, **f)) == build_payload(k, op, **f)` для кожного рядка таблиці);
- `cmd_label(kind, payload) -> str` — текст запасної граматики, якщо ≤ 64 символи, інакше перші 63 символи + `…`
  (довідкове `td.command.text`, M-20);
- `result_text(kind, payload, data) -> str` — запасний `result` з об'єкта результату (колонка «Запасний `result`»).

Приклади: `build_payload("gantry", "feed", stack="PLT-03C", target="SAW-1", sheets=4, product="DSP16-ANT", priority=5,
ref="WH/MO/00233")` → `{"op": "feed", "stack": "PLT-03C", "target": "SAW-1", "sheets": 4, "product": "DSP16-ANT",
"priority": 5, "ref": "WH/MO/00233"}`; `build_cmd` з тими самими полями → `feed;PLT-03C;SAW-1;4;DSP16-ANT;5;WH/MO/00233`;
товар `DSP16 ANT` → `ValueError("product: …")`; `check_payload("gantry", {"op": "feed", "sheets": 4})` →
`ValueError("stack: відсутнє")`; `parse_cmd("gantry", "stack;PLT-07C;55;DSP16-SON;L1;x")` → `ValueError("fields:
очікується 5")`; `build_cmd("gantry", "feed", stack="PLT-T1", target="SAW-T", sheets=4, product="B" * 32, priority=5,
ref="WH/MO/T0001")` → `ValueError("length: 66 > 64")`, а `build_payload` з тими самими полями — об'єкт (довжина тексту
його не обмежує), `cmd_label` для нього — 63 символи + `…`; `parse_cmd("job", "Stop;WO00013")` → `{"method": "Stop",
"job": "WO00013"}`; `result_text("gantry", {"op": "stack", …}, {"id": "PLT-07C", "qty": 55})` → `stack PLT-07C=55`.

### R-22 Плагін `opcua`: адреси, значення, події, виклики (FR-27)

1. Резолв `nodeid`: `^ns=(\d+);([sigb])=(.{1,240})$` (CT-03); `ns_uri` (адреса, інакше параметри) → індекс =
   позиція URI в `NamespaceArray` (немає → джерело `error: "namespace <uri> not found"`); `s` — рядок, `i` — ціле, `g` —
   GUID, `b` — base64. Приклад: `ns=2;s=SAW-1.State.Machine.Overview.CurrentState` + `ns_uri=http://todo.ltd/f3d/iot_sim/instances/`
   на сервері з цим URI на позиції 5 → `NodeId("SAW-1.State.Machine.Overview.CurrentState", 5)`.
2. Якість: `StatusCode.is_good()` → `good`; `is_uncertain()` → `uncertain`; інше → `bad` (для `state/mode/alarm/job` —
   показання `text="bad"`, `q='bad'`; лічильники — пропуск).
3. Значення: перерахування (Int32) → `value = int`, `text = map[str(v)]` (немає в `map` → `str(v)`); `Boolean` → `value 1/0`,
   `text = map["1"/"0"]`; числа → `value = float(v)` (`signal.scale` множить ядро колектора, плагін його не застосовує —
   telemetry R-02, X-63); `String`/`LocalizedText` → `text[:64]`;
   `JobOrderList` (`job_select="running_or_first"`) → елемент, у якого будь-який `State[].StateText.Text == "Running"`,
   інакше перший незавершений (жоден `StateText.Text` ∉ {`Ended`, `Completed`, `Aborted`, `Cancelled`}); `text =
   JobOrder.JobOrderID[:64]`; порожній список або всі завершені → `"-"` (завершене завдання, що лишилось у списку,
   не тримає старий текст — інакше R-12 п. 1 не побачить зміни). Час — `SourceTimestamp`, інакше
   `ServerTimestamp`, інакше час прийому; > 60 с у майбутньому → час прийому + WARNING.
4. Серцебиття: кожні `heartbeat_s` (розширення параметрів, 60 с, 10…600) останні добрі значення підписаних сигналів
   надсилаються з `ts = now` (якщо сесія `online`), щоб telemetry R-07 бачила живий зв'язок.
5. Події (`event_payload`): `Time`, `Severity`, `Message`, поля `IWwEventMessageType` (`MessageId`, `MessageName`,
   `EventCategory`, `PathParts`, `Group`, `LocalizedMessages`, `Arguments`), для тривог `ActiveState/Id`, `AckedState/Id`;
   `kind = "alarm"` для підтипу `WwAlarmConditionType`, інакше `"event"`; `machine` = код зі `SourceName` або `source.code`
   без `UA-`; `text = LocalizedMessages[locale="uk"]` або `Message.Text`; EV-01.
6. Виклик `JobOrderControl` (CMD-01; `call()` з `payload` R-21, запасний `write()` — через `parse_cmd`): об'єкт
   `<C>.JobManagement.JobOrderControl`, метод — дочірній вузол `<isa_idx>:<method>`;
   `Store`/`StoreAndStart` — аргумент `ua.ISA95JobOrderDataType(JobOrderID=job, Description=[ua.LocalizedText(f"{ref} {job}",
   "uk")], WorkMasterID=[], Priority=priority, JobOrderParameters=[ISA95ParameterDataType(ID="PlannedOrderQuantity",
   Value=Variant(float(qty))), ISA95ParameterDataType(ID="OrderNumbers", Value=Variant([ref]))])`; інші — `(job, [])`
   (`JobOrderID: String`, `Comment: LocalizedText[]`); вихід `ReturnStatus` (UInt64): `0` → `{"ReturnStatus": 0}`
   (запасний `result` — `"ok ReturnStatus=0"`), інакше `WriteError("ReturnStatus=<n>")`. Сигнатури — **ПРИПУЩЕННЯ** iot_sim §8.3.2 (OPC 10031-4), Q-01.

### R-23 Адаптер `woodstore` і обробка в Odoo (FR-22)

1. Опитування — §8.5; `GET /api/v1/jobs?state=active` порожній → `default "-"`.
2. Подія `status` → параметр `td.machine_connect.gantry_status` = `{"state", "position", "vacuum_kpa", "cycles_today",
   "current_job", "aisles_open": [номери з gate_open], "alarms": [...], "ts"}` (лише при зміні); нова тривога → чатер
   обладнання GANTRY-1 «Тривога порталу: <текст>»; шина `('maintenance.equipment', ['GANTRY-1'], 'state')`.
3. Подія `stacks` → `_td_apply_ws(items, ts)`: за `id` = код стосу (невідомий → WARNING, пропуск); оновити `ws_*` лише при
   зміні, `ws_seen = now`; `_td_refresh()`; сигнал `equipment/GANTRY-1/stacks` = кількість стосів з `ws_qty > 0` (CT-10,
   джерело `MC-DERIVED`); шина `('stock.location', [коди], 'stock')`.
4. Подія `events` → `td.gantry.job._td_apply_events` (R-16 п. 4); `aisle_opened`/`aisle_closed` → `gantry_status.aisles_open`.
5. Команди CMD-02 (`payload` R-21, X-03) → HTTP: `feed` → `POST /api/v1/jobs {"type": "feed", "source": stack (null —
   портал обирає), "target", "sheets", "product", "lot": null, "priority", "external_ref": ref}` → `201` → результат
   `{"id", "state"}` з відповіді; `409` → `WriteError("CONFLICT: <message>")`; `cancel` → `DELETE /api/v1/jobs/{id}` →
   `{"id", "state": "cancelled"}`; `stack` → `PATCH /api/v1/stacks/{stack} {"qty", "product", "lot", "reason":
   "odoo_inventory"}` → `{"id": stack, "qty"}`. Запасні рядки `result` для `write()` — R-21.

Приклад: стос `PLT-04C` API-21 `{"qty": 38, "product": "DSP16-SON", "lot": "DSP16-SON-2610-114", "reserved": 10}` →
`ws_qty=38`; 23 стоси з `qty > 0` → `equipment/GANTRY-1/stacks = 23` (= `equipment.GANTRY-1.stacks` макета).

### R-24 Адаптер `cutopt` (P-04)

Команди CMD-03 (`payload` R-21, X-03): `upload` (`map`, `token`) → API-01 (§7) → `200` JSON → `POST /jobs` multipart
(`parts` = файл `parts.csv` з `parts_csv`, `material`, `sheet`, `external_ref`, `machine`) → `202 {"job_id", "state",
"eta_s"}` → подія EV-03 `job` (`map` з відповіді API-01) → результат `{"job_id", "state", "eta_s"}`; API-01 ≠ `200` →
`WriteError("export <code>")`; `422` → `WriteError("422: <detail[0]>")`. `status` (`job`) → `GET /jobs/{id}` → EV-03 `job`;
`state == "planned"` → `GET /jobs/{id}/plan` → EV-03 `plan`; результат `{"job_id", "state", "sheets", "waste_pct"}` (з
`job.plan`, інакше `null`). `release` (`job`, `machine`, `priority`) → `POST /jobs/{id}/release {"machine", "priority"}` →
EV-03 `job` (`state="released"`) → результат `{"job_id", "state", "job_order_id"}`. `mpr` (`job`, `part`) → `GET
/jobs/{id}/mpr?part=` → `200` → EV-03 `mpr` (текст ≤ 200 КБ, більше → `WriteError("mpr too large")`) → `{"part",
"size_kb"}`; `404` → `{"part", "size_kb": null}` (команда `done`). Запасні рядки `result` для `write()` — R-21.

### R-25 Провайдер переглядача (`td.viewer.provider.machines`, FR-33, CM-05)

`_td_viewer_collect(payload, ctx)` (читання від користувача запиту; вузли, яких немає, пропускаються без помилок):
1. `workcenters[код]` для верстатів з кодом у `payload["workcenters"]`: `machine_state` (str), `state_since` (`"YYYY-MM-DD
   HH:MM"` Київ), `link` (`opcua`|`io`|`manual`), `online` (`state != 'nodata'`); якщо є запис OEE поточної зміни з
   `has_data` — `oee` (перекриття), `availability`, `performance`, `quality` (round 2); `downtime` (якщо відкритий):
   `{"reason": loss_id.name, "since": "HH:MM", "minutes": int(duration_live), "kind": state_kind, "state": reason_state,
   "hint": hint_text}` (`hint` лише непорожній); `pieces_shift` — Σ `pieces` інтервалів поточної зміни (int); `counted` —
   `td_qty_counted` активного завдання; `status`: `fault` → `"stop"`, `working` → `"work"`, інакше як дав провайдер
   production.
2. `equipment["GANTRY-1"]` (якщо є): `gantry = {"state", "job": {"id": ws_id, "target", "sheets", "done", "ref"} | null,
   "stacks": int, "aisles_open": [int], "alarms": [str]}` з `gantry_status` і активного завдання.
3. `locations["PLT-*"]`: `gantry = {"qty": ws_qty, "expected": expected_qty, "diff": diff, "state": state}` для стосів з
   даними порталу.
4. `productions[]` (за `name`): `cut_map = {"name", "state", "sheets": plan_sheets, "waste_pct"}` (остання не скасована
   карта); `supply.gantry = {"job": name, "sheets", "done", "state"}` (останнє не скасоване завдання), лише якщо `supply` є.
5. `sheet_chain.steps[4]` (крок 5 «Виробництво») — якщо є активні (`queued/active`) завдання порталу:
   `stock = "портал: <n> завд. · <Σ(sheets − done)> арк."`.
6. Нічого з вбудованих полів, крім `oee` і `status` п. 1, не перезаписується (`losses`, `productive_minutes`, `queue`,
   `current_workorder` — провайдера production).
7. `_td_viewer_delta(patch, ctx)`: ті самі п. 1–5 лише для вузлів, що є в `patch` (провайдери `production`, `stock`,
   `maintenance`, `chains` уже поклали повні записи змінених кодів; модуль шле `_notify` саме за моделями, які вони
   обробляють: `mrp.workcenter` (`state`), `stock.location` (`stock`), `maintenance.equipment` (`state`), `mrp.production`
   (`doc`)).

Приклад фрагмента: `"SAW-1": {…, "status": "work", "oee": 0.84, "machine_state": "working", "state_since": "2026-10-12 09:55",
"link": "opcua", "online": true, "availability": 0.84, "performance": 1.0, "quality": 1.0, "pieces_shift": 80, "counted": 14}`;
`"CNC-2": {…, "status": "stop", "machine_state": "fault", "downtime": {"reason": "Поломка", "since": "09:42", "minutes": 48,
"kind": "fault", "state": "to_confirm", "hint": "E0421 Помилка шпинделя осі Z"}}`.

### R-26 Плановий час і часові пояси (`tools/ppt.py`, A-23)

1. `ppt_intervals(env, wc, dt_from, dt_to)`: календар `wc.resource_calendar_id` (інакше компанії); `calendar.
   _work_intervals_batch(aware(dt_from), aware(dt_to), resources=wc.resource_id)[wc.resource_id.id]` → інтервали з tz →
   UTC naive; стандарт віднімає відсутності ресурсу `time_type='leave'`, слоти завдань (`time_type='other'`) — ні.
2. Демо: 12.10.2026 → `[04:00, 08:30)`, `[09:00, 12:30)` UTC (07:00–11:30, 12:00–15:30 Київ, EEST) = 480 хв; 26.10.2026
   (після переходу на EET UTC+2) → `[05:00, 09:30)`, `[10:00, 13:30)` UTC = 480 хв; субота — порожньо.
3. Допоміжні: `clip(intervals, a, b)`, `union(intervals)`, `minus(a, b)`, `total_min(intervals)` (чисті функції).
4. Дата зміни — дата за Києвом початку першого інтервалу. Тексти (чатер, діяльності, payload) — Київ
   (`zoneinfo.ZoneInfo("Europe/Kyiv")`), не tz користувача (крони працюють від суперкористувача).
5. Колектор: усі `ts` — UTC (OPC UA `SourceTimestamp` — UTC за стандартом; woodStore — ISO з офсетом → UTC).

### R-27 Міграція демо (`hooks.py`, FR-29, FR-30, A-24)

1. Причини: переклади uk (`with_context(lang='uk_UA').write({'name': …})`, лише якщо `uk_UA` активна і uk-назва = en):
   `block_reason0` «Очікування матеріалу», `block_reason1` «Поломка», `block_reason2` «Налагодження», `block_reason4`
   «Знижена швидкість», `block_reason5` «Дефект процесу», `block_reason6` «Знижений вихід», `block_reason7` «Повністю
   продуктивний час»; `factory3d.loss_tool`, `factory3d.loss_break` з порожньою категорією → `mrp.category_availability`;
   `factory3d.loss_break.td_planned = True`.
2. Розміри листа: товари категорії «Плитні матеріали» (і дочірніх) з нульовими полями; назва `(\d{3,4})\s*[×xX]\s*(\d{3,4})`
   → довжина, ширина; `(\d+(?:[.,]\d+)?)\s*мм` (перше) → товщина (округлення); приклад «ДСП 16 мм Дуб Сонома 2800×2070» →
   2800 / 2070 / 16; «ХДФ 3 мм білий 2800×2070» → 3; без збігу — пропуск + WARNING.
3. Сигнали: `mc_signals.csv` розгортається для 35 верстатів (Додаток A) і GANTRY-1 → 207 рядків; upsert за `code`:
   новим — усі поля Додатка C.2 і xml-id `td_machine_connect.sig_<slug>` (`noupdate=True`); наявним — лише
   `source_id`, `address`, `period_s`, `store_period_s`, `viewer_visible` (пороги, `last_*`, `module` не чіпаються).
4. Журнал демо: `install_ts` = час початку хука; записи `mrp.workcenter.productivity` з `create_date < install_ts` і
   `td_downtime_id IS NULL` → `td_source='demo'` (SQL `UPDATE`); з них втрати (`loss_type in availability/quality`,
   без завдання) РЦ, що мають верстат → `td.downtime` (`date_start/date_end` = запису; `state_kind`: «Equipment
   Failure» → `fault`, «Setup and Adjustments»/«Заміна інструменту» → `setup`, інше → `idle`; `loss_id` = запису;
   `reason_source='demo'`, `reason_state='confirmed'`; `ppt_min = duration` запису), запис отримує `td_downtime_id`.
   Відкритий (CNC-2 з 09:42) → простій відкритий, `maintenance_request_id` = відкрита `corrective` заявка обладнання (MR/00031),
   верстат `state='fault'`, `state_since = date_start`, `current_downtime_id`; інтервали станів не створюються.
5. Звіт (`migration_report`): `{"loss_translated", "loss_category_fixed", "loss_planned", "sheets_sized", "machines",
   "with_operator", "signals_created", "signals_bound", "machines_wired", "stacks", "orderpoints_linked", "timelog_marked",
   "downtimes_created", "downtimes_open", "requests_linked", "timelog_created": 0, "ts", "state"}`.

### R-28 Інтервали для енергії (`_td_wo_intervals`, `_td_wc_intervals`, CM-03, FR-34)

1. `_td_wo_intervals(workorders, date_from=None, date_to=None)`: інтервали M-02 зі станом ∈ {`working`, `setup`} і
   `workorder_id in workorders.ids`, що перетинають вікно (відкритий — до `now`), обрізані вікном → `{wo_id: [(start, end,
   state), …]}` за часом, UTC naive.
2. `_td_wc_intervals(workcenter, date_from, date_to)` → `[(start, end, state, wo_id | False), …]` усіх станів.
3. `mrp.workorder.td_run_min` / `td_setup_min` += `duration_min` інтервалу при його закритті (R-04 п. 3).
4. Energy (`td_energy`) рахує кВт·год завдання як ∫ `energy/consumers/<код>/p_now` (або різниці лічильника PM5560)
   по інтервалах п. 1, а `idle/off/fault` — як непрямі витрати РЦ.

Приклад: WO00013 → `[(06:55:00, 07:25:48, "working")]` UTC → `td_run_min = 30,8`; при `p_now ≈ 12,18 кВт` (iot_sim R-02)
energy отримає ≈ 6,25 кВт·год.

### R-29 Простої в гривнях (DT-1…DT-5, FR-37; вау-функція №17; версія 19.0.1.1.0)

1. **Вартість (DT-1).** `td.downtime.cost` — `Monetary`, `store=True`, `compute` залежить від `duration_min`, `workcenter_id.costs_hour`, `currency_id`:
   `cost = duration_min / 60 × workcenter_id.costs_hour`, у валюті компанії верстата (`currency_id` = `company_id.currency_id`), округлення валютою.
   Зміна `costs_hour` РЦ перераховує вартість усіх його простоїв (стандартний перерахунок збережених полів, без крону). Відкритий простій має `cost = 0`
   до закриття; `cost_live` (не зберігається) рахує його наживо. `shift_date` (`Date`, `store`, індекс) — київська доба `date_start` = `td.oee.shift.date`
   («зміна» в модулі — одна доба на верстат, R-14); служить зрізом аналітики.
2. **Аналітика «Простої в ₴» (DT-2, V-32).** Дія `action_td_downtime_cost` (`td.downtime`; `graph,pivot,list`; контекст `search_default_this_month`,
   `search_default_group_loss`), меню `menu_td_mc_downtime_cost` («Простої в ₴», `menu_td_mc_root`, seq 22 — поруч із «Простої», `group_td_manager`).
   Графік — Парето за `loss_id`: `type="bar" order="DESC"` за мірою `cost` (сума за спаданням); зведена — рядки `workcenter_id` (верстат), стовпці `shift_date:day`
   (зміна); у пошуку: «Цей місяць», групування «Робочий центр» і «Зміна». У списку простоїв `cost` — `optional="hide"`, `group_td_manager`.
3. **Плитка «Огляд верстатів» (DT-2, V-33).** kanban V-01 має `js_class="td_machine_kanban"`: `MachineKanbanRenderer` додає над картками `DowntimeCostTile`
   — «Простої за місяць: N ₴, з них без причини: M ₴» (символ і розташування — за валютою компанії); дані — `td.downtime.td_cost_tile()` (`@api.model`): сума за поточний
   місяць за київським часом (закриті за `cost` + відкриті наживо); «без причини» — `reason_state = 'to_classify'`; без `group_td_manager` повертає `False` (плитки немає).
   Клік відкриває V-32. Файли: `static/src/views/machine_kanban/*`, тур `td_machine_connect_cost_tile`.
4. **Payload (DT-3).** `workcenters[code].downtime_cost` (float, сума за місяць у валюті компанії) додає R-25 `_machine_node` лише якщо запит не з кіоска і користувач — менеджер
   «Завод 3D» (за аналогією з `energy_cost`, X-25); інакше ключа немає. Значення оновлюється разом із вузлом верстата (повний payload і дельта вузла).
5. **Демо-ставки (DT-4).** `hooks.demo_rates(env)` (крок `run_migration` після `demo_journal`, лічильник звіту `rates_set`; `migrations/19.0.1.1.0/post-migrate.py` для вже
   встановлених демо-баз): для РЦ верстатів з `mc_machines.csv`, у яких `costs_hour = 0`, задає ставку за префіксом коду (`RATES`, умовчання `RATE_DEFAULT`); ненульові ставки не чіпає;
   працює лише в демо-базі (є простої `reason_source = 'demo'` або записи журналу `td_source = 'demo'`); ідемпотентний.
6. **3D (DT-5).** Міст `td_machine_connect_viewer3d` (`depends: td_machine_connect, td_viewer3d`, `auto_install`): JS-розширення `registerViewerExtension` (td_viewer3d R-26, VX-01…VX-03)
   додає режим розфарбування «Простої, ₴» (`td_downtime_cost`) після «OEE верстатів»: колір верстата за часткою від найбільшої суми (від 60 % — червоний, 25–60 % — жовтий,
   менше — зелений); без `downtime_cost` у payload (кіоск, не менеджер) пункт схований. Ядро `core.js` не змінювалось.

AC: **AC-104** вартість = тривалість × ставка, валюта компанії, `shift_date` київський (`test_cost_is_duration_times_rate`, `test_shift_date_is_kyiv_local`); **AC-105** зміна ставки перераховує
`cost` (`test_recompute_on_rate_change`); **AC-106** Парето за сумою спадає, графік `order="DESC"`, зрізи за верстатом і зміною (`test_pareto_sorted_by_sum`); **AC-107** плитка: місяць, «без причини»,
відкриті наживо, лише менеджер (`test_tile_*`) і тур `td_machine_connect_cost_tile`; **AC-108** `downtime_cost` у payload лише менеджеру і не в кіоску (`test_payload_downtime_cost`; міст —
`td_machine_connect_viewer3d/tests/test_payload.py`); **AC-109** демо-ставки лише для порожніх, ідемпотентно (`TestDemoRates`); **AC-110** режим «Простої, ₴»: радіо, колір, легенда, дельта
(HOOT `td_machine_connect_viewer3d/static/tests/hoot/downtime_cost.test.js`).

### R-30 Вузьке місце заводу (BN-1…BN-8, FR-38; вау-функція №16; версія 19.0.1.2.1)

Система сама знаходить ділянку, що обмежує випуск (логіка теорії обмежень), і показує її в аналітиці, плитці «Огляду верстатів» і в 3D.
Розрахунок — чисті функції `tools/bottleneck.py` (без ORM, юніт-тести `tests/test_bottleneck.py`); збір даних — `td.bottleneck` (`AbstractModel`, `models/td_bottleneck.py`).

1. **Вікно, ділянки (BN-1).** `period`: `shift` — київська доба до «зараз» (як «зміна» в R-14), `day` — останні 24 год, `week` — останні 7 діб (`period_window`).
   «Зараз» — демо-годинник «Переглядача» `td.viewer.demo_clock` (час за Києвом), якщо він заданий і валідний (лише демо-бази), інакше реальний час.
   Ділянка (`group_by=area`, умовчання) — перша мітка РЦ (`mrp.workcenter.tag`, «дільниця»; демо-крок `wc_tags`), РЦ без мітки — окрема ділянка;
   `group_by=workcenter` — кожен РЦ окремо. Станції без даних (немає ні доступного часу, ні завдань) у рейтинг не потрапляють.
2. **Показники ділянки (BN-2).**
   - *Завантаження* = Σ `run_min` / Σ `ppt_min` верстатів ділянки за вікно (`td.machine._td_oee`: журнал станів `td.machine.state.log`, а без нього — журнал часу, як в OEE R-13);
     `ppt_min` — доступний час (плановий час мінус планові зупинки й «немає даних»); без доступного часу завантаження невідоме (`None`).
   - *Черга* — завдання (`mrp.workorder`), у яких попередня операція завершена (`ready_at <= t`), а ця ще не почата (`start_at > t` або немає): на кінець вікна і на його початок;
     `queue_delta` — зміна за вікно. Попередня операція — `blocked_by_workorder_ids`, а без залежностей у МО — попереднє завдання за `sequence`; для першої операції `ready_at` — початок МО.
     `start_at` — найраніший факт роботи (журнал станів `working`/`setup`, журнал часу, інакше `date_start` завдання в роботі), `finish_at` — для виконаного завдання останнє завершення журналів, інакше `date_finished`.
     Скасовані завдання й МО в чернетці/скасовані не враховуються.
   - *Очікування* — середнє `start_at − ready_at` (хв, не менше 0) завдань, що стартували у вікні, і `t1 − ready_at` завдань, що ще чекають.
   - *Випуск* — Σ `qty_produced` завдань ділянки, завершених у вікні (одиниці виробу МО); `capacity` = випуск / завантаження — випуск при 100 % завантаженні.
3. **Вузьке місце (BN-3).** `find_bottleneck`: серед ділянок із завантаженням `>= 50 %` (`LOAD_MIN`) — `growing`: найбільш завантажена з чергою, що зросла за вікно; інакше `queue`: з чергою, що не росте;
   інакше `load`: найбільш завантажена без черги (не виражене). Якщо жодна ділянка не досягає 50 %, але черга десь є, — `low`: найбільш завантажена з чергою як імовірний кандидат; інакше вузького місця немає.
   Рівність — більша черга, потім ключ. Рейтинг: вузьке місце першим, далі за завантаженням і чергою.
4. **«Що якщо» (BN-4).** Модель пропускної здатності лінії за маршрутами МО (`build_routes`: послідовність ділянок завдань МО, сусідні однакові зливаються). Кожен маршрут бере частку потужності ділянки
   пропорційно своїм замовленням (`capacity × n_маршруту / Σ n маршрутів через ділянку`); маршрут обмежує найменша частка, пропускна здатність лінії — сума маршрутів (`line_capacity`).
   Ділянки без потужності (немає даних) не обмежують. `what_if(+X %)` підвищує потужність вузького місця на X % (умовчання 20, у звіті змінюється, 0…500) і дає приріст лінії та наступне обмеження на найбільшому
   маршруті через нього; підказка: «+20 % потужності на Розкрій → +14 % випуску, далі обмежує Присадка». Спрощення: спільні ділянки між маршрутами ділять потужність за поточним складом замовлень, черги й перепланування не моделюються.
5. **Аналітика й плитка (BN-5).** Клієнтська дія `action_td_bottleneck` (`static/src/bottleneck/*`, V-34), меню `menu_td_mc_bottleneck` («Вузьке місце», `menu_td_mc_root`, seq 25, `group_td_user`): кнопки періоду, вибір «Ділянки / Робочі центри»,
   поле «Що якщо, +%», виділене вузьке місце (смуга з показниками й вердиктом), підказка, рейтинг (завантаження, черга зі стрілкою зміни, очікування, випуск). Дані — `td.bottleneck.td_report(period, group_by, boost_pct)` (лише `group_td_user`, інакше `AccessError`).
   Плитка «Вузьке місце: <ділянка>, черга N» (+ «(імовірне)» для `load`/`low`) над картками «Огляду верстатів» поруч із плиткою простоїв: `td.bottleneck.td_tile()` (період `day`; без вузького місця або без `group_td_user` — `False`, плитки немає); клік відкриває аналітику.
6. **Payload (BN-6).** `workcenters[code].flow` (`tools/payload.apply_flow`, викликає провайдер R-25 після `apply_machines`) для верстатів ділянок із рейтингу: `station`, `key`, `load`, `queue`, `queue_delta`, `wait_min`, `output`, `rank`, `bottleneck`, `period`;
   для верстатів ділянки-вузького місця ще `verdict`, `hint`, `codes` (верстати ділянки), `prev` (верстати найчастішої попередньої ділянки за маршрутами). Показники не фінансові — є й у кіоску. Збій розрахунку лише логується, payload віддається без `flow`.
   Дельта (R-25 п. 7) несе зведення `flow` усіх верстатів ділянок із рейтингу, а не лише вузлів патча (воно мале): зміна вузького місця чи черги торкається й вузлів, яких у патчі немає,
   тож клієнт знімає стару стопку й ставить нову; вузол без патча створюється з одним ключем `flow` (клієнт зливає дельту глибоко).
7. **3D (BN-7).** Міст `td_machine_connect_viewer3d` (19.0.1.1.0): розширення `registerViewerExtension` (R-26, VX-03, VX-04) `static/src/layer/bottleneck_layer.js`: червона стопка коробок на підлозі **біля входу верстата ділянки** (верстат, найближчий до попередньої ділянки `prev`, без неї — найзахідніший; сторона, що дивиться на `prev`, інакше −X; по центру сторони, на 0,9 м від краю — а не посеред проходу), висота за чергою (не більше 12 коробок),
   бейдж із числом просто над стопкою і підпис поруч у стилі підписів верстатів: «Вузьке місце · черга N», а при вердикті `load`/`low` — «Ймовірне вузьке місце · черга N» (19.0.1.2.2); наведення на підпис показує метрики (ділянка, завантаження, черга, очікування, «Що якщо»), клік відкриває картку верстата-входу з блоком «Вузьке місце»; блок «Вузьке місце · <ділянка>» у картці верстата (вердикт, завантаження, черга, очікування, випуск, рейтинг; у вузького місця — підказка «Що якщо»). Шар «Замовлення в роботі» й `core.js` не змінювались; без `flow` розширення неактивне.
8. **Кеш (BN-8).** `td.bottleneck._td_analyze` без явної дати кешується (`tools.ormcache`): ключ — компанія, період, групування, відсоток, 60-секундна корзина реального часу (`CACHE_S`) і демо-годинник; payload, дельти,
   плитка й звіт з однаковими параметрами рахують розрахунок не частіше за раз на 60 с (≈0,3 с на демо). Кеш скидається лише часом: скидання за змінами завдань і журналу станів — це скидання всього кешу `default` реєстру з сигналом
   усім воркерам, воно дорожче за розрахунок. Результат кешу — лише для читання.
9. **Демо-перевірка.** На демо-даних (МО WH/MO/00231–00262, демо-годинник 12.10.2026 10:30) завантаження ділянок 11–37 %, черга лише в «Розкрій» (2 непочаті перші операції МО 00246, 00254, +2 за вікно): вердикт `low`, кандидат — «Розкрій»
   (завантаження 37 %, очікування 4 хв). Демо вироджене для ТОС: кожне МО має лише одне завдання «в роботі», решта «заблоковані» попередньою операцією, а журнал часу демо охоплює лише ранок 12.10 (частина ще до початку календарної зміни).
   Результат не підганяється: вузького місця з вердиктом `growing` демо не дає.

AC: **AC-111** завантаження = робота / доступний час, з журналу станів і з журналу часу, ділянки за мітками РЦ (`test_load_is_work_over_available_time`, `test_timelog_fallback_without_state_log`, `test_area_grouping_by_workcenter_tag`, `test_load_and_empty_station_skipped`);
**AC-112** черга = попередня операція завершена, ця не почата, на кінець і початок вікна (`test_queue_is_finished_predecessor_and_not_started`, `test_orders_queue_wait_output`, `test_first_operation_not_started_waits_since_mo_start`);
**AC-113** очікування й випуск (`test_wait_average`, `test_output_is_quantity_finished_in_window`); **AC-114** вибір вузького місця: найбільш завантажена з чергою, що росте; `queue`/`load`/`low`/немає (`test_growing_queue_beats_higher_load`, `test_bottleneck_is_busiest_station_with_growing_queue`,
`test_low_load_with_queue_is_low_verdict_candidate`, `test_no_data_no_bottleneck`); **AC-115** «що якщо»: приріст, обмеження наступною ділянкою, спільні ділянки, підказка з X за умовчанням 20 (`test_what_if_*`, `test_line_capacity_shares_station_between_routes`, `test_what_if_hint_on_scenario`);
**AC-116** аналітика, плитка, права, демо-годинник і тур `td_machine_connect_bottleneck` (`test_report_and_tile`, `test_report_and_tile_need_factory_user`, `test_demo_clock_is_now`, `TestBottleneckTour`); **AC-117** `workcenters[code].flow` у payload, кіоск, дельта, `prev`
(`test_flow_nodes_in_payload`, `test_flow_delta_carries_full_summary`, `test_flow_delta_without_queue_has_no_bottleneck_marks`, `test_flow_prev_is_main_upstream_station`; міст — `td_machine_connect_viewer3d/tests/test_payload.py`, `TestBottleneckFlowPayload`); **AC-118** 3D: стопка (висота, бік `prev`, ліміт, дельта), блок картки
(HOOT `td_machine_connect_viewer3d/static/tests/hoot/bottleneck.test.js`, BN1…BN7, зокрема BN7: вузьке місце переїхало з А на Б — у А стопки немає; BN8 — підпис за вердиктом, BN9 — стопка біля входу верстата ділянки на підлозі, BN10 — підказка з метриками й клік по підпису);
**AC-119** кеш розрахунку: два виклики поспіль — один розрахунок, нова 60-секундна корзина, компанія й демо-годинник у ключі, явна дата без кешу
(`test_analysis_is_cached_for_a_minute`, `test_cache_key_has_company_and_demo_clock`).

### R-31 Портальний склад плит у 3D наживо (PT-1…PT-8, FR-39; вау-функція №19; версія 19.0.1.3.0)

Висота стосів під порталом береться з даних, портал рухається за часом завдань, у картках видно ланцюжок лист → завдання → карта розкрою → МО.
Збір даних — `td.portal` (`AbstractModel`, `models/td_portal.py`), чисті функції — `tools/portal.py`; 3D — міст `td_machine_connect_viewer3d` (`static/src/layer/portal_model.js`, `portal_layer.js`; хуки часу й кадру — td_viewer3d VX-08).

1. **Звідки дані (PT-1).** Портал STORETEQ P-500 — це REST «woodStore API v1» (P-03, §8.5; інтерфейс закритий, Q-02, ПРИПУЩЕННЯ), а не OPC UA: `GET /stacks` (`qty`, `product`, `lot`, `updated`) →
   `td.gantry.stack` (R-15, R-23 п. 3), `GET /jobs` і `GET /events` (`job_started`, `sheet_placed` зі стосом, `job_finished`; `external_ref` = назва МО) → `td.gantry.job` з `sheet_log` (R-16 п. 4, R-23 п. 4).
   Ланцюжок існує в даних: лист (запис `sheet_log`: час, стос, партія) → завдання (`stack_id`, `target_workcenter_id`) → карта розкрою (`cut_map_id`, інакше остання не скасована карта МО; відходи `plan_waste_pct`)
   → МО (`production_id`, `external_ref`). Без стенда (демо-база) його будує демо-крок п. 8, на стенді — емулятор (п. 9).
2. **Вузол `equipment["GANTRY-1"].portal` (PT-2).** `{"day": "РРРР-ММ-ДД", "now": секунди київської доби, "cycle_s": 27, "jobs": [...], "today": {"jobs", "sheets", "waste_pct"}}`. «Зараз» — демо-годинник
   `td.viewer.demo_clock` (як R-30), інакше реальний час. `jobs` — завдання подачі (`type='feed'`) за київську добу: відкриті (`sent/queued/active`) і завершені з початку доби, не пізніші за «зараз», ≤ 60 (`JOBS_MAX`), за початком.
   Вузол завдання: `id` (номер `ПОРТ/…`), `ws`, `state`, `stack` (код стосу; порожній — перший зі `log`), `target` (код верстата), `sheets`, `done`, `product`, `name`, `lot`, `ref`, `mo`, `mo_product`, `origin` (документ-джерело МО),
   `s`/`e` (старт/фініш, секунди доби або `null`), `log` — `[[секунди, код стосу], …]` листів доби до «зараз» (≤ 30 останніх), `cut` — `{name, state, sheets, waste_pct}` (`waste_pct` лише для карт у станах
   `planned/released/running/done` з планом; для чернетки й без плану — `null`, а не 0). Завдання, яке за даними закінчилось після «зараз» (демо-годинник), віддається активним з `done` за журналом. `today.waste_pct` —
   середньозважене за листами завдань відходів їхніх карт (`tools/portal.waste_weighted`); немає жодної карти з планом — `null` («—»).
3. **Вузол `locations[PLT-*].portal` (PT-3).** Для кожного стосу (повний payload — усі `td.gantry.stack`, дельта — лише вузли патча): `{"qty", "upd", "src", "capacity", "thickness", "product", "name", "lot", "next"}`. `qty` — листів за показанням порталу
   (`ws_qty`, `src="portal"`), а без даних порталу — залишок Odoo (`odoo_qty`, `src="odoo"`); `upd` — час показання (`ws_updated`, секунди доби, не пізніше за «зараз») або `null` («зараз»); `thickness` — `td_thickness_mm`
   плити стосу; `next` — активне, інакше найпріоритетніше відкрите завдання стосу (`job`, `state`, `target`, `sheets`, `done`, `ref`). Збій розрахунку лише логується (savepoint), payload віддається без вузлів порталу.
   Існуючі ключі R-25 п. 2–3 (`gantry`) не змінюються. Вузли є і в кіоску: це не фінансові дані; провайдер, як і раніше, лише для `group_td_user`.
4. **Залишок на момент t і рух (PT-4, клієнт).** Залишок стосу на `t` = показання `qty` на момент `upd` (немає — «зараз») мінус листи зі `log` усіх завдань у `(upd, t]` плюс листи в `(t, upd]` (`stackQtyAt`) — тож у «Потоці зміни» стоси
   худнуть за часом, а запізнення показання (портал віддає стоси раз на 30 с) не дає зайвого листа. Вікно руху листа — останні `cycle_s` (27) с перед його кладенням (або від попереднього кладення, якщо проміжок коротший); у ньому
   портал виконує фази в частках 0,37 / 0,15 / 0,37 / 0,11: їде до стосу, бере лист (вакуум), везе до верстата, кладе (td_iot_sim R-18); після кладення порожня рама їде на парковку (початкове положення візка, `RETURN_S` = 10 с) і стоїть запарковано до наступного вікна, яке рушає звідти (`from = {target, k}` — положення між верстатом і парковкою, без стрибків). Для активного завдання додається вікно наступного листа
   (очікуване кладення = останнє + типовий період за журналом, 27…300 с). Лист у «руках» — із стосу вже знятий (на 1 нижче). Поза порталу — чиста функція `poseAt(P, t)`; у «живому» режимі `t` = `portal.now` + час, що минув;
   у «Потоці зміни» — `api.simMinutes()` ядра (td_viewer3d VX-08), зміну часу ловить підписка `api.onSimTime(cb)` (швидкість програвання — з кроку між змінами), DOM повзунка міст не читає. При швидкому програванні (понад 8× реального часу) вікна по секундах миготіли б, тому цикл «верстат → стос → верстат»
   активного завдання йде з власним темпом (6 с, `poseLapse`). Без телепортів: положення візка наближається до цілі зі згладжуванням і межею швидкості 18 м/с.
5. **3D (PT-5).** Міст `td_machine_connect_viewer3d` 19.0.1.2.2, розширення `registerViewerExtension` (R-26, VX-03, VX-04, VX-05), група сцени `td_portal_layer`: на кожен стос — паралелепіпед з висотою `листи × товщина`
   (смуга на бічних гранях — один лист на тайл) кольору декору плити, табличка «матеріал · N арк.»; запечені плити стосу (`stack_*_1/2`) і запечений візок порталу (`GANTRY-1_5…10`) ховаються — замість них рухомий міст, візок, щогла,
   вакуумна рама (тією ж геометрією, що й запечені) і лист кольору плити. Запечена `GANTRY-1_6` містить і балку моста, і траверсу (плиту над присосками): геометрію розділено за висотою, балка їде з мостом, траверса — з візком і рамою (раніше траверса лишалась у повітрі й виглядала плитою, що висить сама). **Лист має лише два положення:** висить під вакуумною рамою (верх листа = низ рами, по центру) або лежить на опорі — верх стосу чи приймальний стіл пили (верх опори — медіана 9 променів зверху вниз у точці кладення: стіл разом із запеченою пачкою на ньому). Фази: порожня рама їде до стосу на безпечній висоті (вища за найвищий можливий стос і стіл + 0,5 м) → опускається до верху стосу → захоплення → підйом → переїзд → опускання на стіл → відпускання; лист лежить на столі до моменту, коли пила його забирає (`HOLD_S` = 100 с після кладення або за секунду до відпускання наступного листа на цей стіл; у швидкому програванні — до наступного захоплення), потім порожня рама повертається на парковку. Лист і висота стосу, стола й рами узгоджені (товщина листа — `td_thickness_mm` стосу, габарит 2800 × 2070 як у плит). Клік по плитах проходить до запеченого піддона: вибирається стос. Без вузла `portal` (старий сервер, портала немає) розширення неактивне, а запечені
   деталі повертаються. Кадр за потребою міст просить `api.invalidate()` (VX-08) після зміни положень; для листа в «руках» додатково стоїть прапорець `userData.f3dAnimated`. Потребує `td_viewer3d` ≥ 19.0.1.1.1 (VX-08: `simMinutes`, `onSimTime`, `invalidate` — додано до `core.js` аддитивно; без них міст бачить лише живий режим).
6. **Картки (PT-6, VX-04, VX-05).** Стос: матеріал і код, залишок і висота на `t` («15 арк. з 60 · висота 240 мм»), джерело (показання порталу / Odoo), партія, наступне завдання. Портал: стан («Везе лист до верстата»), «Завдань N · листів M»,
   «Відходи розкрою X %», активне завдання і ще до 4 завдань; кожне завдання — три рядки: **Лист** (`лист k з n · стос → верстат · матеріал`), **Карта розкрою** (`КР/… · відходи X %`), **Замовлення** (`WH/MO/… · виріб`);
   стос і верстат у рядку — посилання (`data-ext="td_machine_connect_portal:select:<код>"`) вибирають об'єкт у 3D. Верстат-ціль (SAW-1…3, NEST-1): блок «Портал · подача на <код>» із завданням (активне або останнє).
7. **Плитка «Портал: N завдань сьогодні, відходи розкрою X %» (PT-7).** `td.portal.td_tile()` (`@api.model`, лише `group_td_user`, інакше `False`; `False` також, якщо немає ні стосів, ні завдань порталу) → `{jobs, sheets, waste_pct}`;
   OWL-компонент `GantryTile` у `td_machine_kanban` поруч із плитками простоїв і вузького місця (V-33); «завдання/завдань» за українським множинним; відходи `—`, якщо немає карт з планом; клік відкриває «Завдання порталу».
8. **Шина й демо (PT-8).** Хід завдання оновлює 3D дельтою: `_td_apply_events` (`job_started`, `sheet_placed`, `job_finished`) і `_td_apply_ws` шлють `maintenance.equipment`/`GANTRY-1` і `stock.location` для стосів, з яких брали лист
   (`td.gantry.job._td_notify_portal`; коалесценція — td_viewer3d R-15). Демо: `tools/demo_portal.demo_gantry(env)` (крок `run_migration` після `demo_rates`, лічильники звіту `gantry_jobs`, `cut_maps`; `migrations/19.0.1.3.0/post-migrate.py`;
   лише демо-база без жодного завдання порталу, ідемпотентний) для кожного завдання розкрою МО в роботі (SAW-1…3, NEST-1) створює завдання подачі по кожному стосу й партії резерву сировини (`origin='odoo'`, МО, карта), завдання йдуть по черзі
   (портал один; початок за 5 хв до операції, 70…109 с на лист за назвою МО), останнє завдання МО в роботі — активне на «зараз» (останній лист 25 с тому), МО «готове» — у черзі; карта розкрою на МО — `released` з відходами 6,0…14,9 %
   (детерміновано за назвою МО); показання кожного стосу з залишком: `ws_qty` = Odoo − подане в МО, що не закриті (R-15 п. 2), `ws_updated` = час останнього листа зі стосу.
9. **Емулятор (td_iot_sim R-18).** REST woodStore стенда раніше віддавав лише завдання, створені Odoo (`POST /jobs`, `/jobs` API-33), а модель порталу `models/gantry.py` ставила `feed` у пам'ять, не показуючи їх по REST, тож без ручної команди
   в Odoo завдань порталу не було. `protocols/woodstore_auto.py` (`AutoFeed`) додає: кожен РЦ розкрою (SAW-1…3, NEST-1) у WORKING без завдання порталу в черзі отримує `feed` на 2…5 листів із `external_ref` = `order` активного завдання РЦ
   (назва МО), плита — з наявних стосів (детерміновано за МО), пріоритет 3 (команда Odoo з 5 обганяє), не більше 12 листів на МО; `GET /status` віддає фази `moving/picking/placing` (цикл 27 с наприкінці періоду листа, 10:4:10:3).
   `SIM_WOODSTORE_AUTOFEED=0` вимикає. Подія `sheet_placed` несе стос — звідси `sheet_log` і залишок стосу.

AC: **AC-120** вузол порталу: ланцюжок лист → завдання → карта розкрою (відходи) → МО, секунди доби, зведення «сьогодні», майбутнє за демо-годинником приховано, `waste_pct` лише для запланованих карт (`TestPortalNodes.test_equipment_node_chain_and_today`,
`test_node_hides_future_and_clips_log_to_now`, `test_cut_waste_only_for_planned_maps`, `test_job_without_mo_has_no_cut`, `TestPortalPure`); **AC-121** вузол стосу: показання/Odoo, товщина, наступне завдання (`test_stack_nodes_portal_and_odoo_sources`,
`test_next_job_prefers_active_then_priority`); **AC-122** payload: повний, дельта лише для вузлів патча, кіоск, збій не ламає (`test_payload_collect_and_delta_carry_portal`, `test_portal_failure_does_not_break_payload`; міст —
`td_machine_connect_viewer3d/tests/test_payload.py`, `TestPortalPayload`); **AC-123** плитка: підрахунок, відходи, права, порожній портал (`test_tile_*`), `jobsWord` і тур; **AC-124** демо-історія й шина: завдання по черзі без накладання, карти, показання
стосів `ok`, ідемпотентність, `_notify` при ході завдання (`TestDemoGantry`, `test_events_notify_equipment_and_stacks`); **AC-125** 3D: залишок на `t`, вікна й фази руху, без телепортів, висота стосу, запечені деталі ховаються й повертаються,
картки, дельта (HOOT `td_machine_connect_viewer3d/static/tests/hoot/portal.test.js`, PT1…PT11, зокрема PT8/PT8b — час за `simMinutes`/`onSimTime`, кадр через `invalidate`; PT4b — листи на столах; PT11 — інваріант: кожен видимий лист висить під рамою або лежить на опорі ± 1 см для серії моментів у живому режимі й у «Потоці зміни»); **AC-126** емулятор: авто-завдання за РЦ у WORKING з МО, фази `status`, обмеження на МО, вимкнення (`services/iot_sim/tests/protocols/test_woodstore_auto.py`).

## 10. Стани й переходи

### 10.1 Верстат (`td.machine.state`, CM-02)

```
nodata ──(перше добре показання)──► working | setup | idle | fault | off          (R-01, фіксація одразу)
working ──(idle/setup ≥ micro_stop_s, заднім числом)──► idle | setup               (R-02 п. 4)
working ──(ERROR / alarm при зупинці)──► fault ;  working ──(OFFLINE)──► off       (одразу)
idle | setup | off | fault ──(WORKING)──► working                                  (простій закрито; R-09/R-10)
fault ──(READY)──► idle ;  idle ──(SETUP)──► setup ; …                              (простій закрито, новий відкрито)
будь-який ──(stale / q=bad)──► nodata                                               (R-03)
```

Побічні ефекти переходу: закриття/відкриття інтервалу M-02, простою M-03 (R-05), автостарт/пауза/завершення (R-09…R-12),
сигнал `machine_state`, шина.

### 10.2 Простій (`td.downtime`)

`відкритий (is_open)` → `закритий` (перехід верстата, межа дня R-05 п. 6, `nodata`); `закритий` з `ppt_min·60 <
micro_stop_s` (не аварія) → видалено. Класифікація: `to_classify` → (`hint` з `auto_apply`, оператор) → `to_confirm` →
(майстер «Підтвердити») → `confirmed`; майстер, що вказує причину, → одразу `confirmed`; `confirmed` змінює лише майстер.

### 10.3 Завдання Odoo (стандартні стани `mrp.workorder`) під дією модуля

`ready/blocked` ──(R-09)──► `progress` (таймер відкрито) ──(R-10 пауза)──► `progress` (таймер закрито, `wo_paused`) ──(R-10
відновлення)──► `progress` (таймер) ──(R-12)──► `done`; `progress` ──(R-12 п. 5)──► `progress` + `td_partial_hold` ──(майстер)──►
`done` / `progress`. Модуль не переводить у `cancel` і не змінює МО.

### 10.4 Завдання порталу (`td.gantry.job.state`)

`draft` → `to_send` (кнопка/автоподача) → `sent` (команда створена) → `queued` (результат `wj-…` або подія) → `active` → `done`
(R-17); `draft/to_send` → `cancelled`; `sent/queued/active` → `cancelled` (CMD-02 `cancel`); `sent` → `error` (команда
`failed/expired`), `queued/active` → `error` (подія); `error` → `to_send` («Повторити»). Кінцеві: `done`, `cancelled`.

### 10.5 Стос (`td.gantry.stack.state`)

`unknown` → `ok` | `pending` (дані порталу); `ok` ⇄ `pending` (розбіжність з'явилась/зникла); `pending` → `diff` (≥
`stack_diff_confirm_min`); `diff` → `ok` (дія або самоусунення); будь-який → `unknown` (немає даних 10 хв).

### 10.6 Карта розкрою (`td.cut.map.state`)

`draft` → `exported` → (`collector`) `optimizing` → `planned` → `released` → `running` → `done`; (`manual`) `exported` →
`planned` (імпорт) → `released` (кнопка); `optimizing/planned/released` → `error` (команда/подія/30 хв); будь-який, крім
`done`, → `cancel`; `error/cancel` → `draft`.

### 10.7 Запис OEE (`td.oee.shift.state`)

`open` (поточна зміна, оновлення 5 хв) → `closed` (після кінця вікна; змінюється лише кнопкою «Перерахувати»).

## 11. Обробка помилок

1. **Верстат недоступний / обрив OPC UA** — плагін: бекоф 1…60 с, відновлення підписок (R-22, §8.3 п. 5), `q='bad'` →
   `nodata`; telemetry `stale` → `nodata` (R-03); автодії не виконуються; простій, що тривав, закривається.
2. **Odoo недоступний** — колектор буферизує (telemetry R-19); після відновлення пакети приходять зі старими `ts`:
   R-02 п. 1 (пізні не переписують журнал), переходи фіксуються за `ts` показань (журнал станів точний), автостарт
   ставить `date_start` таймера = `ts` переходу.
3. **Дублікати** — показання (telemetry унікальність `(signal, ts)`), події (`ext_event_id`, `td.push.event`), події
   woodStore (`sheet_log` за id), команди (ключ автостарту, `ws_id` унікальний).
4. **Стандарт Odoo відмовив** (`UserError` у `start_employee`/`button_finish`/`stock.move.line`) — дія не виконується,
   діяльність/чатер з текстом, стан верстата й журнал не відкочуються (окремий `savepoint` на автодію).
5. **Гонка двох воркерів** — `SELECT … FOR UPDATE` рядка верстата (R-04 п. 0); частковий унікальний індекс відкритого
   інтервалу/простою на верстат — друга вставка падає → `savepoint` відкат, лог WARNING.
6. **Невідомі коди** — стос/РЦ/товар у подіях woodStore, завдання верстата → WARNING, пропуск або діяльність (R-09 п. 1);
   подія з невідомим `machine` → `ValueError` (telemetry пише в `td.push.event.error`).
7. **Запис вимкнено** — команди не створюються (`UserError` для кнопок; `to_send` + текст для крону), п'ять запобіжників.
8. **Невалідні дані плану/CSV** — `UserError` з номером рядка/полем, нічого не пишеться (M-25, M-26).
9. **Часові пояси й DST** — R-26; плановий час 26.10.2026 (зміна EEST → EET) обчислює календар; лічильники OPC UA
   `Relative*` скидаються емулятором о початку зміни за Києвом — R-11 п. 2.
10. **Розбіжність лічильника** — скидання, стрибки > 1000 → R-11 п. 2.
11. **Зв'язок є, а завдання верстата не з Odoo** (оператор запустив програму вручну) — «працює без завдання» (R-09 п. 9).
12. **Портал заблоковано (прохід відчинено)** — завдання лишаються `queued`, стан порталу `blocked` видно в картці; Odoo
    нічого не робить автоматично.
13. **Демо-журнал** — міграція не будує історію (A-24); OEE з дня установки.

## 12. Acceptance Criteria

Тип перевірки: **UT** (`TransactionCase`), **HT** (`HttpCase`), **CT** (pytest пакета плагінів), **TC** (стенд), **MAN**.
Фікстури — §13.0.

| ID | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given `tools.states.normalize`; Then кожен рядок таблиці прикладів R-01 дає вказаний стан (11 випадків) | UT |
| AC-02 | FR-01 | When `normalize("opcua", {"state": "FOO", …})`; Then `nodata` і WARNING один раз за годину для того самого верстата (`assertLogs`) | UT |
| AC-03 | FR-01 | Given верстат `io` `M-IO`; When `_td_ingest` показань `workcenters/IO-T/state` `text="run"` і `/alarm` `text="on"` з однаковим `ts`; Then `state='fault'` (тривога важливіша) | UT |
| AC-04 | FR-03 | Given `M-UA` (`idle` з 09:50); When `_td_ingest([state WORKING @09:55:00, mode AUTOMATIC])`; Then інтервал `idle` закрито `09:55:00`, відкрито `working` з `09:55:00`, `machine.state='working'`, `state_since=09:55:00`; один відкритий інтервал (`search_count(date_end=False)==1`) | UT |
| AC-05 | FR-02 | Given `working`, `micro_stop_s=120`; When READY @10:02:00, WORKING @10:03:10; Then переходів немає, `pending_state=False`, кількість інтервалів не змінилась | UT |
| AC-06 | FR-02, FR-36 | Given `working`; When READY @10:05:00 і `_cron_tick()` з `freeze_time(10:07:31)`; Then `idle` зафіксовано з `10:05:00`, інтервал `working` закрито `10:05:00`; крон о `10:06:50` — ще ні | UT |
| AC-07 | FR-03 | Given `working` з 10:00:00; When показання стану `READY @09:59:00` (пізнє); Then стан не змінився; лічильник у тому самому пакеті оброблено | UT |
| AC-08 | FR-03, CM-02 | When перехід у `working`; Then `td.signal` `workcenters/UA-T/machine_state` має `last_text='working'`, показання в `td.reading` з `src='module'`; `_td_ingest` від колектора на цей код → `rejected: foreign_signal` (CT-12) | UT |
| AC-09 | FR-16 | Given РЦ з календарем «Зміна 1»; Then `ppt_intervals(12.10.2026 00:00–24:00 Київ)` = `[04:00–08:30, 09:00–12:30]` UTC, 480 хв; `26.10.2026` = `[05:00–09:30, 10:00–13:30]`; `17.10.2026` (субота) = `[]`; відсутність ресурсу `time_type='leave'` 10:00–11:00 віднімається, слот завдання `time_type='other'` — ні | UT |
| AC-10 | FR-01 | Given `working`; When `sig_state._mark_stale('timeout')`; Then `state='nodata'`, відкритий простій закрито, таймери завдання не змінено; When показання стану `q='bad'` → `nodata` | UT |
| AC-11 | FR-04 | Given `working` з WO у `progress` (таймер оператора відкритий), `auto_start_enabled=True`; When ERROR @09:42:00 (`now` 09:42:03); Then простій `fault`, відкритий запис журналу часу `loss_id=mrp.block_reason1`, `td_auto=True`, `date_start=09:42:00`; таймер завдання закритий `date_end=09:42:00`; `workcenter.working_state='blocked'` | UT |
| AC-12 | FR-05 | Given `working`; When READY @10:05 (зафіксовано), WORKING @10:21; Then поки простій тривав — записів журналу часу з `td_downtime_id` 0, `working_state != 'blocked'`; після — один закритий запис 10:05–10:21 `loss_unknown`, `td_auto=True`, простій закрито, `ppt_min=16` | UT |
| AC-13 | FR-05 | Given `idle` зафіксовано о 11:29 (до обіду), WORKING о 12:00:30; Then `ppt_min=1,0` (лише 11:29–11:30 + 12:00–12:00:30 = 1,5 хв) — простій лишається; Given `idle` 15:31–15:45 (поза зміною) → простій видалено, записів немає | UT |
| AC-14 | FR-05 | Given `idle` з 15:00; When крон о 15:30:30; Then простій закрито `15:30`, новий не відкрито до 07:00 наступного робочого дня; крон о 07:00:30 вівторка (стан ще `idle`) → новий простій з 07:00 | UT |
| AC-15 | FR-06 | Given відкритий простій `loss_unknown`; When `user_mrp` `action_set_reason(block_reason0)`; Then `loss_id`, `reason_source='operator'`, `reason_state='to_confirm'`, машинні записи простою мають ту саму причину; When `user_f3d` (без mrp) → `AccessError` | UT |
| AC-16 | FR-06 | When `user_mrp_manager` `action_confirm()` на простої з `loss_unknown` → `UserError`; з причиною → `confirmed`, `confirmed_by`; When `user_mrp` змінює причину `confirmed` → `UserError` | UT |
| AC-17 | FR-06 | Given відкритий простій `fault` з машинним записом; When `user_mrp` створює запис журналу часу (блок) «Equipment Failure» без завдання; Then запис `td_downtime_id = простій`, `td_source='operator'`; машинний запис закрито `date_end = запис.date_start`; перекриттів немає | UT |
| AC-18 | FR-06 | Given `working`, оператор заблокував РЦ з «Material Availability»; When READY (зафіксовано); Then простій отримав причину оператора (`operator`, `to_confirm`), запис прив'язано | UT |
| AC-19 | FR-06 | Given простій `idle` з прив'язаним відкритим записом оператора; When WORKING; Then запис оператора закрито `date_end = ts`, `working_state != 'blocked'` | UT |
| AC-20 | FR-06 | Given `fault`, оператор `workcenter.unblock()`; When `_cron_tick()`; Then відкрито новий машинний запис «Аварія триває» | UT |
| AC-21 | FR-07 | Given повідомлення `E0421 → block_reason1 (auto_apply)`; When ERROR @09:42:00 і EV-01 `E0421` @09:42:01; Then простій `loss_id=block_reason1`, `reason_source='hint'`, `hint_text='E0421 Помилка шпинделя осі Z'`, `event_id`; і в зворотному порядку (подія раніше за стан на ≤ 120 с) — те саме | UT |
| AC-22 | FR-07 | When READY + mode SETUP; Then простій `setup`, причина `block_reason2` (`hint`); закриття → запис журналу часу з `workorder_id` активного завдання | UT |
| AC-23 | FR-07 | Given на РЦ лише завдання `blocked`; When `idle`; Then `hint_loss_id=block_reason0`, `loss_id=loss_unknown`, `reason_state='to_classify'` | UT |
| AC-24 | FR-08 | Given сигнал `alarm` з `alarm_states=["on"]`, `create_request=True`; When показання `on` разом зі ERROR; Then одна заявка ТО (не дві — сигнал `state` `create_request=False`), `downtime.maintenance_request_id` = заявка, у чатері заявки «Подія верстата: E0421…» після EV-01 | UT |
| AC-25 | FR-09, FR-10 | Given `auto_start_enabled=True`, `M-UA` `job_or_single`, WO `ready` id N на РЦ, оператор `OP-UA-T` дозволений; When WORKING @t + `job="WO%05d" % N`; Then WO `progress`, відкритий таймер з `employee_id = OP-UA-T`, `user_id = user_td_machine`, `date_start = t`; `td_auto_started=True`; `active_workorder_id = WO` | UT |
| AC-26 | FR-09 | Given `M-IO` (без сигналу завдання), `ready` рівно одне; When `run`; Then старт; Given два `ready` → старту немає, `no_job_since=t`; `_cron_tick` о `t+15 хв` → одна діяльність «працює без завдання», повторний крон — не дублює | UT |
| AC-27 | FR-09 | Given режим `job`; When WORKING з `job="-"`; Then старту немає навіть за одного `ready` | UT |
| AC-28 | FR-09 | When `job="WO99999"` (немає) або завдання іншого РЦ; Then старту немає; діяльність «Завдання верстата «WO99999» не знайдено в Odoo» (одна на текст) | UT |
| AC-29 | FR-11 | When той самий пакет (WORKING + job) надіслано двічі і ще раз із новим `ts`; Then рівно один відкритий таймер, рівно один виклик `start_employee` (`mock.patch.object` з `wraps`) | UT |
| AC-30 | FR-11 | Given РЦ `blocked` відкритим записом оператора; When WORKING + job; Then запис закрито `ts`, завдання стартувало (без `UserError` «unblock») | UT |
| AC-31 | FR-10 | Then порядок вибору R-09 п. 4: (б) працівник сьогоднішнього запису > (в) `OP-<код>` > (г) `employee_id` верстата > (ґ) перший дозволений; недозволений `OP-<код>` (є `wc.employee_ids` без нього) пропускається; (д) без працівника → `button_start` | UT |
| AC-32 | FR-15 | Given `auto_start_enabled=False`; When WORKING + job; Then стан і журнал оновлено, завдання не стартувало, таймери не змінювались; Given `read_enabled=False` (параметр) → `td.machine.state` не змінився, показання telemetry записані | UT |
| AC-33 | FR-13 | Given активне WO; When `pieces_out` 0→1→5 і 5→0→2 (скидання), 2→1500 (стрибок); Then `td_qty_counted = 5 + 2 = 7`, стрибок ігнорується з WARNING, `log.pieces` сумується | UT |
| AC-34 | FR-13 | Given `qty_sync_mode='live'`, `qty_sync_s=300`; When лічильник +3 о `t`, +2 о `t+60`, +1 о `t+301`; Then `qty_produced` = 3 після першого, не змінився після другого, = 6 після третього; у режимі `finish` — 0 до завершення | UT |
| AC-35 | FR-14 | Given активне WO (`qty_production=14`, `counted=14`); When `job` → `"-"`; Then `qty_produced=14`, `state='done'`, `active_workorder_id=False`, чатер МО; Given `counted=12` → `td_partial_hold=True`, таймер закритий, діяльність на МО, `state='progress'`, `production.product_qty` не змінився | UT |
| AC-36 | FR-14 | Given `M-IO`, `counted ≥ remaining`, `stop` з `t`; When `_cron_tick` о `t+59` → ще ні; о `t+61` → `done` | UT |
| AC-37 | FR-14 | Given `td_partial_hold`; When `user_mrp_manager` `action_f3d_finish_partial()`; Then `qty_produced=counted`, `done`; `user_mrp` → `AccessError` | UT |
| AC-38 | FR-12 | Given `working` з таймером; When ERROR → таймер закритий одразу, `wo_paused=True`; When WORKING → новий таймер того самого працівника з `ts`; Given `idle` → таймер закривається кроном через `pause_after_min` з `date_end = state_since`; `setup` — не закривається | UT |
| AC-39 | FR-16 | Given синтетичний журнал SAW-1 R-13 (176 `working`, прості 16/10/8, 80 шт × 2,2, без браку); When `_td_oee(07:00, 10:30)`; Then `ppt=210`, `run=176`, `A=0.8381±0.0005`, `P=1.0`, `Q=1.0`, `oee=0.838`, `losses` у порядку 16, 10, 8 | UT |
| AC-40 | FR-16 | Same з 76 шт і `stock.scrap` 1 шт (`done`, `workorder_id`) → `P=0.95`, `Q=0.9868`, `oee=0.7857±0.0005`; CNC-2 R-13 → `oee=0.305±0.001`; SAW-3 → `0.488±0.001` | UT |
| AC-41 | FR-16 | Given дві закриті зміни R-13 (480/400/396/180/2 і 480/360/350/159/0); When дія «OEE за період»; Then повідомлення містить `A 0,79 · P 0,98 · Q 0,99 · OEE 0,77` | UT |
| AC-42 | FR-16 | Given 30 хв `nodata` у зміні; Then `ppt` зменшено на 30, `coverage=1−30/480=0.9375`, `incomplete=True` (`coverage_min=0.95`) | UT |
| AC-43 | FR-16 | Given РЦ без інтервалів станів, лише записи журналу часу (продуктивний 07:00–09:00, втрата «Поломка» 09:00–09:30); Then `source='timelog'`, `run=120`, `fault_min=30`, `unexplained = PPT − 150` | UT |
| AC-44 | FR-17, FR-36 | When `_cron_oee` о 10:30 → запис `open`, `machine.oee_shift_id`; о 15:35 → `closed`; повторний крон закритого не змінює; `_cron_rotate` видаляє інтервали старші `keep_log_days` і події старші `keep_event_days`, `td.oee.shift` — ні | UT |
| AC-45 | FR-34 | Given інтервали `setup` 09:40–09:55 і `working` 09:55–10:25:48 з WO, `idle` 10:25:48–10:30 без WO; Then `_td_wo_intervals(wo)` = два інтервали (setup, working); з вікном 10:00–10:10 — один обрізаний `working`; `_td_wc_intervals` — три | UT |
| AC-46 | FR-34 | Then після закриття інтервалів `wo.td_run_min=30.8`, `td_setup_min=15.0` | UT |
| AC-47 | FR-18 | Given стос `PLT-T1` (квант 45), завдання порталу `done=7` для МО в роботі, `ws_qty=38`; When `_td_refresh()`; Then `fed_unconsumed=7`, `expected=38`, `diff=0`, `state='ok'` | UT |
| AC-48 | FR-18 | When `ws_qty=36` → `pending`, `diff_since`; через 10 хв (`freeze_time`) → `diff`, одна діяльність для користувача `stock.group_stock_manager`; Given `ws_product='DSP16-SON'`, Odoo `DSP16-WNG` → `diff` одразу | UT |
| AC-49 | FR-22 | When подія `mc_woodstore` `status` з `gantry_status` новим (`aisles[2].gate_open=true`, `alarms=["Вакуум"]`); Then параметр `gantry_status.aisles_open=[2]`, чатер GANTRY-1 «Тривога порталу: Вакуум»; When `stacks` з 23 стосами `qty>0` → сигнал `equipment/GANTRY-1/stacks.last_value=23` | UT |
| AC-50 | FR-18 | Given `diff=−2` (AC-48); When `user_stock_manager` «Прийняти з порталу»; Then квант = 43, стан `ok`; `user_f3d` → `AccessError`; «Виправити портал» при `write_enabled=False` → `UserError`, при п'яти запобіжниках → команда з `payload` `{"op": "stack", "stack": "PLT-T1", "qty": 38, …}` (`text` `stack;PLT-T1;38;…`, X-03) | UT |
| AC-51 | FR-21 | Given правило `min 10`, `ws_qty=9`, `gantry_auto_replenish=True`; When `_cron_gantry`; Then `action_replenish` викликано 1 раз (повтор крону за годину — ні; є відкрите переміщення — ні); When переміщення в `PLT-T1` виконано і запис вимкнено → діяльність «Оновіть стос PLT-T1 у woodStore» | UT |
| AC-52 | FR-19 | Given МО з рухом плити (резерв у `PLT-T1`, партія L1) і завданням на SAW-T; When `action_f3d_feed_gantry()` двічі; Then одне завдання `feed`, `stack_id=PLT-T1`, `lot_id=L1`, `sheets` = к-сть руху; МО без завдання розкрою → `UserError` | UT |
| AC-53 | FR-19 | Given `to_send`, запобіжники ввімкнено; When `_cron_gantry`; Then `td.command` на `equipment/GANTRY-1/cmd` з `payload == {"op": "feed", "stack": "PLT-T1", "target": "SAW-T", "sheets": 4, "product": "BOARD-T", "priority": 5, "ref": "WH/MO/T0001"}` і `text="feed;PLT-T1;SAW-T;4;BOARD-T;5;WH/MO/T0001"` (X-03), стан `sent`; запис вимкнено → лишається `to_send`, `error` «Запис вимкнено…» | UT |
| AC-54 | FR-19 | When команда `done` з `result_data={"id": "wj-00412", "state": "queued"}` → `ws_id="wj-00412"`, `queued` (X-03); `failed` → `error` з текстом; `expired` → «Колектор не забрав команду» | UT |
| AC-55 | FR-19 | When EV-02 `jobs` з невідомим `wj-00500`, `external_ref="WH/MO/T0001"`; Then нове завдання `origin='machine'` з `production_id`; EV-02 `events` 3 × `sheet_placed` (одна повторно) → `done=2`... `len(sheet_log)=2`, `done=max(done, 2)` | UT |
| AC-56 | FR-20 | Given завдання `done=4` з `PLT-T2` (резерв руху був у `PLT-T1`); When `_td_consume()`; Then рядок руху `PLT-T2` 4 `picked=True`, незібраний рядок `PLT-T1` зменшено на 4, `consumed_qty=4`; повторний виклик — без змін | UT |
| AC-57 | CM-08 | Then приклади R-21 (`build_payload`, `check_payload`, `build_cmd`, `parse_cmd`, `cmd_label`, `result_text`) — рівно наведені об'єкти, тексти й помилки; для кожного рядка таблиці R-21 `parse_cmd(k, build_cmd(k, op, **f)) == build_payload(k, op, **f)` і `result_text` дає колонку «Запасний `result`» | UT, CT |
| AC-58 | FR-15 | Given будь-який із п'яти запобіжників вимкнено (`machine_connect.write_enabled`, `telemetry.write_enabled`, джерело, сигнал); When `env['td.command']._td_mc_create_command(...)` (M-20); Then `UserError` з назвою запобіжника, команди немає; поле не за R-21 (`product="DSP16 ANT"`) → `UserError` «… не відповідає формату …»; сигнал без `address.call`/`address.cmd` → `UserError` «… не є сигналом команд верстатів» | UT |
| AC-59 | FR-23 | Then `td.cut.part` з `length_mm=0` або `qty=0` → помилка БД; `material_role='product'` без плити → `ValidationError`; M-26 з CSV Додатка E (3 рядки, 1 з помилкою) → `UserError` з «рядок 3: width_mm…», деталей не додано; без помилок → 3 деталі, повторний імпорт без `replace` — upsert (3) | UT |
| AC-60 | FR-24 | Given МО ×14, деталь `P001` 2 шт/виріб 720×560 текстура 1; When `_td_create_for(mo, 'main')`; Then рядок `qty=28`; деталь 2100×1500 текстура 1 на листі 2800×2070 → вміщується; 2100×2100 текстура 0 → `ValidationError` «не вміщується»; без деталей → `UserError` | UT |
| AC-61 | FR-24 | When `action_export()`; Then вкладення `КР/…_parts.csv`, перший рядок — заголовок R-19 п. 5, рядок `P001;Боковина;BOARD-T;720;560;28;1;EB-T;;EB-T;;`, CRLF, без BOM; `;` у назві → `,` | UT |
| AC-62 | FR-25 | Given `collector`, запобіжники ввімкнено; When `action_send_optimizer()`; Then команда з `payload == {"op": "upload", "map": <id карти>, "token": t}` (`t` — 16 hex), `export_token_hash = sha256(t)`, `expires = now + 600`, стан `optimizing` | UT |
| AC-63 | FR-25 | When команда `done` (`result_data={"job_id": "cj-00077", "state": "optimizing", "eta_s": 5}`), EV-03 `plan` (`total_sheets=7`, `waste_pct=11.4`), EV-03 `mpr` для `P001`; Then `ext_job_id="cj-00077"`, `plan_sheets=7`, вкладення плану й `P001.mpr`, стан `planned`; невалідний план (`total_sheets=0`) → `ValueError` у журналі подій, стан не змінився; карта `optimizing` > 30 хв (крон) → `error` | UT |
| AC-64 | FR-25 | Given `plan_sheets=9`, рух МО 8; Then `sheets_warning` непорожній; `action_update_mo_need()` → рух 9, чатер МО; `user_f3d_manager` без `mrp_manager` → `AccessError` | UT |
| AC-65 | FR-26 | When «Випустити» → команда з `payload == {"op": "release", "job": "cj-00077", "machine": "SAW-T", "priority": 5}`; `done` → `released`; EV-02 `jobs` з `external_ref` цього МО → карта `gantry_job_id`; у режимі `manual` M-25 з JSON API-32 → `planned`, «Випустити» → `released` без команд; автостарт `job="cj-00077"` → WO карти (R-09 п. 1) | UT |
| AC-66 | FR-35 | Given карта `exported`, токен `t`; When `GET /f3d/machine/cutmap/<id>/export` з Bearer колектора і `X-F3D-Token: t`; Then `200`, JSON з `parts_csv` = CSV AC-61, `Cache-Control: no-store`; повтор → `403` (одноразовий) | HT |
| AC-67 | FR-35 | Then без Bearer → `401`; токен колектора іншого → `401`; невірний `t` → `403`; без `X-F3D-Token` (у т.ч. `?t=` у query) → `400`; прострочений → `410`; стан `draft` → `409`; неіснуюча карта → `404`; `t="xyz"` → `400` | HT |
| AC-68 | FR-35 | Given 6 000 деталей; Then `413`, карта `error` | HT |
| AC-69 | FR-27 | Given `NamespaceArray` з URI на позиції 5; Then `nodeids.resolve("ns=2;s=SAW-1.State…", ns_uri)` → `NodeId(…, 5)`; без URI → індекс 2; URI немає → `ConnectError` «namespace … not found»; `ns=2;x=1` → помилка валідації | CT |
| AC-70 | FR-27 | Given фейковий сервер (§13.0.2) з `SAW-T`; When плагін `connect`+`subscribe`; Then показання `state` `value=3, text="WORKING"`, `mode` `text="AUTOMATIC"`, `alarm` `text="off"`, `pieces_out` `value=0.0`; зміна на сервері `CurrentState=4` → `text="ERROR"` ≤ 2 с; `ts` = `SourceTimestamp` | CT |
| AC-71 | FR-27 | Given `JobOrderList` [перший `AllowedToStart` `WO00014`, другий `Running` `WO00013`]; Then `text="WO00013"`; [`Completed` `WO00012`, `AllowedToStart` `WO00014`] → `"WO00014"`; усі `Ended`/`Completed` або порожній → `"-"`; без змін 60 с → повторне показання з новим `ts` (серцебиття) | CT |
| AC-72 | FR-27 | When сервер генерує `WwAlarmConditionType` `E0421`; Then `ctx.emit_event` один раз з `route="mc_opcua"`, payload EV-01 (`kind="alarm"`, `category=5`, `active=true`, `text` uk), `event_id` = sha256 | CT |
| AC-73 | FR-27 | When сервер зупинено; Then ≤ 10 с показання `q="bad"` для `state` (`text="bad"`), `health().state="offline"`; сервер піднято → переп'єднання ≤ 60 с, підписки відновлено (нові зміни приходять), метрика `reconnects` +1 | CT |
| AC-74 | FR-27 | Given `settings.write_enabled=True`; When `call(job_cmd, {"method": "StoreAndStart", "job": "WO00013", "qty": 14, "ref": "WH/MO/00233", "priority": 5})`; Then фейковий метод отримав `ISA95JobOrderDataType(JobOrderID="WO00013", Priority=5)` і повернуто `{"ReturnStatus": 0}`; `ReturnStatus=3` → `WriteError`; `write_enabled=False` → `WriteError("write disabled")`; об'єкт не за R-21 → `WriteError("bad_command…")` | CT |
| AC-75 | FR-28 | Given фейковий woodStore (стан `moving`, `vacuum_kpa=-71.9`, `cycles_today=373`, активне `wj-1`); When `poll`; Then 4 показання (`state="moving"`, `vacuum_kpa=-71.9`, `cycles_today=373`, `job="wj-1"`), один GET `/api/v1/status`; без активних — `job="-"`; подія `status` лише при зміні хешу | CT |
| AC-76 | FR-28 | When `events_loop`: перший запит без `since`, наступні з `since=<останній id>`; 250 подій → 2 події `mc_woodstore` (200 + 50); курсор у `woodstore_<source>.json`; `stacks_loop` — подія лише при зміні хешу або через 15 хв; `jobs_loop` — лише змінені `(state, done)` | CT |
| AC-77 | FR-28 | When `call(g_cmd, {"op": "feed", "stack": "PLT-03C", "target": "SAW-1", "sheets": 4, "product": "DSP16-ANT", "priority": 5, "ref": "WH/MO/00233"})`; Then `POST /api/v1/jobs` з тілом R-23 п. 5, результат `{"id": "wj-…", "state": "queued"}`; `"stack": null` → `"source": null`; `409` → `WriteError("CONFLICT: …")`; `{"op": "cancel", "id": "wj-1"}` → `DELETE`; `{"op": "stack", "stack": "PLT-07C", "qty": 55, "product": "DSP16-SON", "lot": null}` → `PATCH` з `"lot": null` | CT |
| AC-78 | FR-28 | Given фейкові Odoo API-01 і оптимізатор; When `call(cut_cmd, {"op": "upload", "map": 12, "token": t})`; Then GET API-01 з Bearer колектора, `POST /jobs` multipart з `parts.csv`, подія EV-03 `job`, результат `{"job_id": "cj-1", "state": "optimizing", "eta_s": 5}`; API-01 `410` → `WriteError("export 410")`; `422` → `WriteError("422: …")` | CT |
| AC-79 | FR-28 | When `{"op": "status", "job": "cj-1"}` (стан `planned`) → дві події (`job`, `plan`), результат `{"job_id": "cj-1", "state": "planned", "sheets": 7, "waste_pct": 11.4}`; `{"op": "release", "job": "cj-1", "machine": "SAW-1", "priority": 5}` → `{"job_id": "cj-1", "state": "released", "job_order_id": "cj-1"}`; `{"op": "mpr", "job": "cj-1", "part": "P001"}` → подія `mpr`; `404` → `{"part": "P001", "size_kb": null}` | CT |
| AC-80 | CM-08 | Then `f3d_collector_mc/cmdtext.py` побайтово дорівнює `odoo_addons/td_machine_connect/tools/commands.py` (тест читає обидва файли); `ast` файлу — жодного `import odoo`/`from odoo…`/відносного імпорту з `..models`, `cmdtext` імпортується в середовищі пакета без встановленого `odoo` (X-93) | CT |
| AC-81 | FR-29 | Given копія демо; When хук; Then `block_reason0.with_context(lang='uk_UA').name == 'Очікування матеріалу'`; `factory3d.loss_tool.loss_type == 'availability'`; `loss_break.td_planned`; звіт `loss_translated=7`, `loss_category_fixed=2` | UT (на копії демо — TC) |
| AC-82 | FR-29 | Then 7 листових товарів мають `2800/2070/16`, `…/18`, `…/3` за назвою; повтор хука нічого не змінює | UT |
| AC-83 | FR-29 | Then 35 `td.machine` (15 `opcua`, 20 `io`), 28 з `employee_id`; 22 джерела; сигналів модуля 207 (`signals_created` 205 + `signals_bound` 2 на копії демо); кожен верстат має `sig_state_id`, `sig_machine_state_id`; створені сигнали — `origin='module'` (X-16), прив'язані 2 — `origin` без змін; `workcenters/<C>/machine_state` — `viewer_visible=False` (X-27); сигнал команд оптимізатора — `equipment/CUTOPT/cmd` (X-18), коду `mc/cutopt/cmd` немає | TC (копія демо), UT (фікстури) |
| AC-84 | FR-29 | Then 27 `td.gantry.stack`, 23 з `orderpoint_id` | TC, UT |
| AC-85 | FR-30 | Then `downtimes_created=74`, `downtimes_open=1` (CNC-2, `maintenance_request_id`=MR/00031), `timelog_marked=184`, кількість `mrp.workcenter.productivity` після хука = до хука (184); CNC-2 `state='fault'`; повторний хук — 0 нових | TC, UT |
| AC-86 | FR-33 | Given payload з `workcenters` (SAW-T, CNC-T), `equipment["GANTRY-1"]`, `locations["PLT-T1"]`, `productions`, `sheet_chain`; When `_td_viewer_collect`; Then ключі R-25 п. 1–5 з очікуваними значеннями, `losses`/`queue`/`current_workorder` не змінені | UT |
| AC-87 | FR-33 | Given немає запису OEE поточної зміни; Then `oee` лишився вхідним; `status` для `fault` → `"stop"`; вузол відсутній — без винятку | UT |
| AC-88 | FR-33 | When перехід стану; Then `td.viewer.event` (якщо модель є) з `model='mrp.workcenter'`, `codes=['SAW-T']`; `_td_viewer_delta` доповнює лише вузли `patch` | UT (умовно `skipUnless('td.viewer.event' in env)`) |
| AC-89 | FR-31, FR-32 | Then меню `menu_td_mc_root` під `td_factory3d.menu_td_root` з `sequence=40`; `menu_td_mc_settings` — батько `td_factory3d.menu_td_config`, `sequence=40`, група `group_td_manager`, дія `action_td_mc_settings` (`res.config.settings`, `context.module='td_machine_connect'`) (X-32); `user_f3d` читає всі моделі, не пише `td.machine`; `user_f3d_manager` створює верстат; `user_stock` не бачить дій розбіжності; record rule компанії приховує верстат іншої компанії | UT |
| AC-90 | FR-15, FR-32 | When `user_f3d_manager` вмикає `td_mc_write_enabled` у налаштуваннях → `AccessError`; `user_f3d_admin` — так; межі M-23 → `ValidationError` | UT |
| AC-91 | FR-32 | Then `user_td_machine.active=False`, пароля немає, вхід `/web/login` неможливий; має групи §4.2 | UT, HT |
| AC-92 | FR-15 | When `uninstall_hook`; Then параметри `td.machine_connect.%` видалено, крони неактивні, `td.signal` модуля лишились; `neutralize.sql` на копії → три стоп-крани `False`, `cutting_mode='manual'`, `td_machine.read_enabled=false` | UT, TC |
| AC-93 | FR-01, FR-03 | Given ТК-01 (`follow_odoo`, годинник емулятора = реальний, робочий час зміни); Then за ≤ 3 хв: 29 верстатів `working`, 5 `idle` (SAW-3, VSAW-1, EDGE-3, UV-1, ASM-5), CNC-2 `fault` (стан міграції), 34 відкриті інтервали; 21 джерело модуля й `MC-DERIVED` `online`; `mrp.workorder` не змінено, команд 0 | TC |
| AC-94 | FR-04, FR-07, FR-08 | Given ТК-02 (`scenario`); Then CNC-2 `fault` (міграція) → `idle` закриває простій міграції й розблоковує РЦ, MR/00031 без змін; When `machine_fault CNC-2 reason=spindle`; Then ≤ 10 с `fault`, простій «Поломка» (`hint`, `E0421`), відкритий машинний запис журналу часу, РЦ `blocked`, одна нова заявка «CNC-2: аварія верстата» з подією в чатері, у 3D `status=stop`; `stop` → `idle`, простій і запис закрито, РЦ розблоковано, заявка відкрита | TC |
| AC-95 | FR-09…FR-14, FR-34 | Given ТК-04 (`scenario`, `Store` з Odoo, `Start` з пульта); Then ≤ 15 с після `WORKING` WO `progress` з таймером OP-SAW-1 (`create_uid = user_td_machine`); після `Completed` — `qty_produced = qty_production`, `done`; Σ хвилин таймерів WO = Σ інтервалів `working` WO ±1 хв = `td_run_min`; повторний `Start` другого таймера не дає | TC |
| AC-96 | FR-19, FR-20 | Given ТК-06; Then завдання порталу з МО виконано, стос порталу зменшився на N, звірка `ok`, рух МО має зібраний рядок зі стосу | TC |
| AC-97 | FR-24…FR-26 | Given ТК-10; Then карта → `optimizing` → `planned` (аркушів > 0), `released`; `JobOrderList` SAW-1 містить `cj-…`; завдання розкрою стартувало автоматично | TC |
| AC-98 | FR-01 | Given ТК-12 (`machine_fault CNC-3 reason=comm`); Then ≤ 180 с CNC-3 `nodata`, автодій немає, `coverage` зміни < 1 | TC |
| AC-99 | FR-27, FR-01 | Given ТП-01 (35 верстатів, показання щосекунди, 30 хв) і ТП-02 (ланцюг емулятор → колектор → Odoo); Then API-02 p95 ≤ 1,2 с без `5xx` і блокувань БД; «подія емулятора → простій в Odoo» p95 ≤ 10 с; буфер колектора не росте | TC |
| AC-100 | FR-15 | Given ТК-03 і DEPLOY_TEST п. 6 «перший тиждень лише читання» (`auto_start_enabled=False`, `write_enabled=False`); Then за зміну журнал станів і прості є, `mrp.workorder`/`mrp.workcenter.productivity` автоматикою не змінені (`write_uid != user_td_machine`), команд модуля 0 | TC |
| AC-101 | FR-27, FR-15 | Given `enable_write()`, `make_mo(wc_ua, qty=14, name='WH/MO/T0002')` (WO id N `ready`); When `user_mrp` `action_f3d_send_to_machine()`; Then `td.command` на `sig_ua_cmd` з `payload == {"method": "Store", "job": "WO%05d" % N, "qty": 14, "ref": "WH/MO/T0002", "priority": 5}` і `text == "Store;WO%05d;14;WH/MO/T0002;5" % N` (X-03), `td_machine_id = m_ua`, `origin='machine_connect'`, чатер МО; `cmd_done(cmd, data={"ReturnStatus": 0})` → чатер верстата «Команда …: done {"ReturnStatus": 0}»; WO у `progress` → `UserError`; WO на `wc_io` → `UserError` «не приймає завдань з Odoo»; `write_enabled=False` → `UserError` з назвою запобіжника | UT |
| AC-102 | FR-15, FR-19, CM-08 | Given `enable_write()`; When `env['td.command']._td_mc_create_command(sig_g_cmd, "feed", {"stack": "PLT-T1", "target": "SAW-T", "sheets": 4, "product": "B" * 32, "priority": 5, "ref": "WH/MO/T0001"})`; Then команда з `payload` (усі поля без змін), `text` — перші 63 символи тексту R-21 + «…» (`len(text) == 64`). Given `td.command._td_mc_payload_supported` підмінено на `False` (telemetry без CR-01, X-93); When той самий виклик; Then `UserError` «… length: 66 > 64», команди немає; When завдання AC-53 → `_cron_gantry`; Then команда без `payload`, `text="feed;PLT-T1;SAW-T;4;BOARD-T;5;WH/MO/T0001"`; `cmd_done(cmd, "wj-00412")` (без `result_data`) → `ws_id="wj-00412"`, `queued` (X-03, запасна граматика) | UT |
| AC-103 | FR-27, FR-28, CM-08 | Given `settings.write_enabled=True`; When `write(job_cmd, None, "Stop;WO00013")`; Then фейковий метод `Stop("WO00013", [])` — той самий виклик, що `call(job_cmd, {"method": "Stop", "job": "WO00013"})`, — і `result="ok ReturnStatus=0"`; `write(g_cmd, None, "feed;PLT-03C;SAW-1;4;DSP16-ANT;5;WH/MO/00233")` → те саме тіло `POST /api/v1/jobs`, що в AC-77, `result="wj-…"`; `call(g_cmd, {"op": "feed", "sheets": 4})` → `WriteError("bad_command: stack: відсутнє")`, HTTP-запитів 0; `call` на сигналі без `address.call`/`address.cmd` → `NotSupported`; плагіни беруть граматику лише з `cmdtext` (без Odoo, X-93) (X-03, запасна граматика) | CT |

Покриття FR: FR-01 AC-01…03, 10, 93, 98, 99; FR-02 AC-05, 06; FR-03 AC-04, 07, 08, 93; FR-04 AC-11, 94; FR-05 AC-12…14;
FR-06 AC-15…20; FR-07 AC-21…23, 94; FR-08 AC-24, 94; FR-09 AC-25…28, 95; FR-10 AC-25, 31; FR-11 AC-29, 30; FR-12 AC-38;
FR-13 AC-33, 34; FR-14 AC-35…37; FR-15 AC-32, 58, 90, 92, 100…102; FR-16 AC-09, 39…43; FR-17 AC-44; FR-18 AC-47, 48, 50;
FR-19 AC-52…55, 96, 102; FR-20 AC-56, 96; FR-21 AC-51; FR-22 AC-49; FR-23 AC-59; FR-24 AC-60, 61, 97; FR-25 AC-62…64, 97;
FR-26 AC-65, 97; FR-27 AC-69…74, 99, 101, 103; FR-28 AC-75…79, 103; FR-29 AC-81…84; FR-30 AC-85; FR-31 AC-89; FR-32 AC-89…91;
FR-33 AC-86…88; FR-34 AC-45, 46, 95; FR-35 AC-66…68; FR-36 AC-06, 44, 51, 63. CM-08 — AC-57, 80, 102, 103.


## 13. План тестування (для Opus)

Тестувальник пише тести лише за цим розділом, §12 і контрактами (§2, §7, §9); код модуля не читає. Якщо тест
неможливо написати без читання коду — це дефект SPEC або коду (вимоги тестованості нижче), а не привід читати код.

### 13.0 Фікстури й вимоги до тестованості

#### 13.0.1 Odoo: `tests/common.py`

Теги всіх класів: `@tagged('post_install', '-at_install', 'f3d', 'f3d_machine_connect')`. Запуск на чистій базі:
`odoo-bin -d f3d_mc_test -i td_machine_connect --test-tags /td_machine_connect --without-demo=all
--stop-after-init`; на копії демо — `-u td_machine_connect --test-tags /td_machine_connect` (класи
`TestMigrationDemo` виконуються лише там: `skipUnless(env['mrp.workcenter'].search_f3d('SAW-1'))`).

Вимоги до коду модуля (обов'язкові, інакше тест не написати без читання коду):
1. «Зараз» — лише `fields.Datetime.now()` / `datetime.now(UTC)`; SQL `now()` і `CURRENT_TIMESTAMP` заборонені (`freezegun`).
2. `_td_dispatch` синхронний: після повернення `_td_ingest` стан, журнал, простої, таймери вже змінено (жодних черг,
   `ir.cron._trigger`, `postcommit`).
3. `GANTRY_TARGETS` читається лише як `self.env["td.gantry.stack"].GANTRY_TARGETS` (не імпортованою константою).
4. Хук читає CSV лише через `hooks._csv_rows(env, name: str) -> list[dict]` (`name` ∈ {`mc_machines`, `mc_signals`});
   шаблони сигналів розгортає `hooks._signal_rows(code: str, protocol: str, io_unit: int | None, io_slot: int | None)
   -> list[dict]` (значення для `td.signal.create` без `source_id`, `equipment_id`) — та сама функція створює сигнали
   фікстур.
5. Логер — `logging.getLogger(__name__)` у кожному файлі (`assertLogs('odoo.addons.td_machine_connect', 'WARNING')`).
6. Автоматичні зміни стандартних моделей — лише через `_td_tech_env()`; їхні `create_uid`/`write_uid` =
   `user_td_machine`.
7. Діяльності модуля: тип `mail.mail_activity_data_todo`, `summary` = перші 64 символи тексту, `note` = повний текст
   (тести шукають за `res_model`, `res_id`, `summary`).
8. `tools/payload.build_machines(env, ctx) -> dict` — без імпорту моделей viewer.
9. `tools/states`, `tools/oee`, `tools/ppt` (крім `ppt_intervals`), `tools/commands` (без імпортів Odoo, X-93), `tools/cutcsv` — чисті функції без `env`.

`class F3DMachineMixin(F3DTelemetryMixin)` (`from odoo.addons.td_telemetry.tests.common import
F3DTelemetryMixin`); `F3DMachineCase(F3DMachineMixin, TransactionCase)`, `F3DMachineHttpCase(F3DMachineMixin,
HttpCase)`. Від батьківського класу використовуються лише `col`, `token`, `push()`, `set_sql()`, `api()`,
`team_mech`, `user_plain`, параметри telemetry. Усе нижче створюється від суперкористувача в `setUpClass`.

| Фікстура | Що створює / робить |
|---|---|
| час | `D0 = date(2026, 10, 12)` (понеділок, EEST UTC+3); `kt("09:55[:ss]", day=D0) -> datetime` — naive UTC (`kt("09:55") == datetime(2026, 10, 12, 6, 55)`); у §12 час без дати = `kt(...)`; `at(t, day=D0)` — контекстний менеджер `freeze_time(kt(t, day))`; у `setUp` за замовчуванням `freeze_time(kt("10:30"))` (`self.startPatcher`-подібно: `start()` + `addCleanup(stop)`) |
| параметри (`td.machine_connect.` + …) | `read_enabled=True`, `auto_start_enabled=False`, `write_enabled=False`, `micro_stop_s=120`, `pause_after_min=10`, `finish_idle_s=60`, `qty_sync_mode=finish`, `qty_sync_s=300`, `coverage_min=0.95`, `oee_good=0.75`, `oee_warn=0.5`, `no_job_activity_min=15`, `stack_diff_tolerance=0`, `stack_diff_confirm_min=10`, `gantry_auto_replenish=False`, `gantry_auto_feed=False`, `cutting_mode=collector`, `export_token_ttl_s=600`, `keep_log_days=400`, `keep_event_days=90` |
| `enable_autostart()` | `auto_start_enabled=True` |
| `enable_write()` | чотири запобіжники Odoo: `td.machine_connect.write_enabled=True`, `td.telemetry.write_enabled=True`, `write_enabled=True` на `src_ua`, `src_saw`, `src_ws`, `src_cut` і сигналах `sig_ua_cmd`, `sig_saw_cmd`, `sig_g_cmd`, `sig_cut_cmd` (п'ятий — `F3D_WRITE_ENABLED` колектора — в Odoo-тестах не діє) |
| користувачі | `new_test_user(env, login=…, groups=…, tz='Europe/Kyiv')`: `user_f3d` (`base.group_user,td_factory3d.group_td_user`), `user_f3d_manager` (+`td_factory3d.group_td_manager`), `user_f3d_admin` (+`td_factory3d.group_td_admin`), `user_mrp` (`mrp.group_mrp_user`), `user_mrp_manager` (`mrp.group_mrp_manager`), `user_stock` (`stock.group_stock_user`), `user_stock_manager` (`stock.group_stock_manager`); працівники `emp_mrp`, `emp_master` з `user_id` = `user_mrp`, `user_mrp_manager` |
| календар | `cal` «Зміна 1 (тест)», `tz='Europe/Kyiv'`, `hours_per_day=8`, пн–пт `07:00–11:30` (`day_period='morning'`) і `12:00–15:30` (`'afternoon'`) |
| працівники | `emp_ua` «Оператор UA (тест)» (`barcode='OPUAT'`, `td_code='OP-UA-T'`), `emp_saw` (`OP-SAW-T`), `emp_io` (`OP-IO-T`), `emp_x` «Сторонній оператор» (`OP-X-T`) |
| обладнання | `eq_ua` `UA-T`, `eq_io` `IO-T`, `eq_saw` `SAW-T` (`maintenance_team_id=team_mech`); `eq_gantry` = `maintenance.equipment.search_f3d('GANTRY-1')` або створити «Портал (тест)» `GANTRY-1` |
| РЦ | `wc_ua` «Верстат OPC UA (тест)» `UA-T`, `wc_io` «Верстат I/O (тест)» `IO-T`, `wc_saw` «Розкрій (тест)» `SAW-T`, `wc_cnc` «Присадка (тест)» `CNC-T`: `resource_calendar_id=cal`, `time_efficiency=100`, `employee_ids` порожні |
| товари | `board` «ДСП 16 мм тест 2800×2070» `BOARD-T` (`is_storable=True`, `tracking='lot'`, 2800/2070/16); `board2` `BOARD-T2` (те саме, інший декор); `hdf` «ХДФ 3 мм тест 2800×2070» `HDF-T` (2800/2070/3); `edge` `EB-T` (`type='consu'`); `fg` «Тумба тест» `FG-T`; партії `lot_l1` «L1», `lot_l2` «L2» (`board`) |
| місця й стоси | `loc_t1`, `loc_t2` «PLT-T1», «PLT-T2» під `stock.warehouse` компанії `lot_stock_id` (`td_code`, `td_loc_kind='stack'`, `td_capacity=60`); `stack_t1`, `stack_t2` = `td.gantry.stack.create({'location_id': …})`; `put_stock(board, loc_t1, 45, lot_l1)` (`stock.quant._update_available_quantity`) |
| `make_mo(wc, qty=14, comps=((board, 0.5),), name=None, cycle=2.2)` | BOM `fg` з однією операцією «Операція <код>» на `wc` (`time_mode='manual'`, `time_cycle_manual=cycle`) і компонентами `comps` (к-сть на 1 виріб); МО `fg × qty` (`name` — якщо задано, напр. `WH/MO/T0001`), `action_confirm()`, `action_assign()`; повертає МО з одним завданням `ready` |
| джерела | `src_ua` `UA-UA-T`, `src_saw` `UA-SAW-T` (`opcua`, `{"endpoint": "opc.tcp://iot-sim:4840/f3d/", "security_mode": "None", "ns_uri": "http://todo.ltd/f3d/iot_sim/instances/"}`); `src_io` `MB-U80-T` (`modbus_tcp`, `{"host": "iot-sim", "port": 502, "unit": 80}`); `src_ws` `REST-WOODSTORE-T` (`rest_vendor`, `{"base_url": "http://iot-sim:8082", "auth": "api_key", "key_ref": "F3D_WOODSTORE_KEY", "vendor": "woodstore"}`); `src_cut` `REST-CUTOPT-T` (`{"base_url": "http://iot-sim:8083", "auth": "api_key", "key_ref": "F3D_CUTOPT_KEY", "vendor": "cutopt"}`) — усі `collector_id=col`, `module='machine_connect'`, `read_enabled=True`, `write_enabled=False`; `src_der = env.ref('td_machine_connect.source_mc_derived')` |
| сигнали | `hooks._signal_rows("UA-T", "opcua", None, None)` → `sig_ua_state`, `sig_ua_mode`, `sig_ua_alarm`, `sig_ua_pieces`, `sig_ua_job`, `sig_ua_event`, `sig_ua_cmd`, `sig_ua_mstate`; `("SAW-T", "opcua")` → `sig_saw_*` (ті самі ролі); `("IO-T", "io", 80, 0)` → `sig_io_state`, `sig_io_alarm`, `sig_io_pieces`, `sig_io_mstate`; `source_id` — `src_ua`/`src_saw`/`src_io`, `machine_state` — `src_der`; `equipment_id` — `eq_*`. GANTRY-1 і оптимізатор (`sig_g_state`, `sig_g_job`, `sig_g_cmd`, `sig_g_stacks`, `equipment/CUTOPT/cmd` → `sig_cut_cmd`): знайти за кодом (на копії демо їх створив хук) або створити за Додатком C.2, потім `write({'source_id': src_ws / src_cut / src_der})` |
| верстати | `m_ua` (`wc_ua`, `opcua`, `src_ua`, сигнали UA, `auto_start_mode='job_or_single'`); `m_saw` (`wc_saw`, `opcua`, `src_saw`, `auto_start_mode='job'`); `m_io` (`wc_io`, `io`, `src_io`, `io_slot=0`, `job_or_single`); `m_cnc` (`wc_cnc`, `manual`, без сигналів); `equipment_id` — `eq_*`; стан `nodata` |
| патч | `cls.startClassPatcher(patch.object(type(cls.env['td.gantry.stack']), 'GANTRY_TARGETS', ('SAW-1', 'SAW-2', 'SAW-3', 'NEST-1', 'SAW-T')))` |
| `rk(sig, text=None, value=None, t='10:00:00', q='good')` | показання `{"code": sig.code, "ts": kt(t), …}` (ключі `None` не передаються) |
| `ua(m, t, state=None, mode=None, alarm=None, pieces=None, job=None, q='good')` | показання OPC UA-верстата з одним `ts`: `state`/`mode` — текст (`"WORKING"` → `value=3`, `text="WORKING"` за картою P-01), `alarm` — `True/False` → `1/"on"`, `0/"off"`; `pieces` — число; `job` — текст |
| `io(m, t, run=None, alarm=None, pieces=None, q='good')` | те саме для I/O: `run` → `1/"run"`, `0/"stop"` |
| `feed(readings, src='collector')` | `push(readings, src=src)` + `env.invalidate_all()`; повертає результат `_td_ingest` |
| `tick(t)`, `oee_tick(t)`, `gantry_tick(t)`, `cutmap_tick(t)` | `with at(t):` відповідний крон (`_cron_tick`, `_cron_oee`, `_cron_gantry`, `_cron_cutmap`) |
| `push_event(route, payload, source)` | подія як від плагіна: `event_id = sha256(route + "\n" + source + "\n" + json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False))`, `ts = now`, `remote = source` → `env['td.push.event'].sudo()._td_receive([ev], col)` |
| `ev_ua(m, message_id, category, text, t, kind='alarm', active=True)` | EV-01 для `m` (`source = m.source_id.code`, `machine = m.code`, `time = kt(t)` ISO `Z`) → `push_event('mc_opcua', …)` |
| `make_log(m, state, start, end=None, wo=None, pieces=0)` | `td.machine.state.log` через `sudo().create` (для OEE і R-28; минає диспетчер) |
| `cmd_done(cmd, result=None, data=None)` / `cmd_fail(cmd, error)` / `cmd_expire(cmd)` | `cmd.sudo().write({'state': 'done', 'result': result або json.dumps(data, ensure_ascii=False, sort_keys=True)[:256], 'result_data': data, 'done_at': now})` (команда з `payload` — `data` = об'єкт результату R-21; запасний режим — лише `result`) / `'failed'`, `error` / `'expired'` — як telemetry API-07 (CR-01, X-03) |
| `acts(rec, summary=None)` | `mail.activity` на `rec` (з фільтром за `summary`, якщо задано) |

Помилки цілісності — у `with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError), self.cr.savepoint():`.
Підвипадки таблиць AC — `self.subTest(case=…)`. «SAW-1» у прикладах R-13/R-28, на які посилаються AC-39…AC-46,
у тестах = `m_saw` з календарем `cal` (той самий день `D0`).

#### 13.0.2 Колектор: `services/collector_plugins/machine_connect/tests/conftest.py`

Вимоги до коду пакета: плагіни отримують годинник `clock` (той самий `Clock` ядра telemetry, telemetry §13.0.2) і
`SessionPool` через конструктор (`OpcUaPlugin(ctx, clock=SystemClock(), pool=None)`); інтервали (`heartbeat_s`, бекоф,
нагляд 5 с) — лише через `clock.sleep`; HTTP-сесії адаптерів створює `RestVendorPlugin._session_factory` (підмінюється
в тестах); курсори — у `ctx.settings.mc_state_dir`.

| Фікстура | Що робить |
|---|---|
| `vclock` | віртуальний годинник ядра telemetry (від `2026-10-12T06:00:00Z`) |
| `ctx` | заглушка `PluginContext`: `emitted: list[Reading]`, `events: list[PushEvent]`, `emit()`, `emit_event()`, `secrets(name)` зі словника (`F3D_OPCUA_PASSWORD='pw'`, `F3D_WOODSTORE_KEY='ws-key'`, `F3D_CUTOPT_KEY='co-key'`; відсутній → `KeyError`), `allowlist(host)` (`127.0.0.1`, `localhost`; інакше `AllowlistDenied`), `settings` (`write_enabled=False`, `odoo_url`, `collector_token='t'*43`, `mc_state_dir=tmp_path`), `metrics` (лічильники в пам'яті) |
| `ua_server` | `fakes/opcua_server.FakeMachines(port=<вільний>)`: `asyncua.Server` у процесі, endpoint `opc.tcp://127.0.0.1:<port>/f3d/`, `NoSecurity`, анонімний доступ + користувач `collector`/`pw` (`user_manager`); простори: `0` UA, `1` `urn:test`, `2` `http://example.org/other/`, `3` `http://opcfoundation.org/UA/Woodworking/`, `4` `http://opcfoundation.org/UA/ISA95-JOBCONTROL_V2/`, `5` `http://todo.ltd/f3d/iot_sim/instances/` (екземпляри — на 5, щоб перевірити резолв за URI); структури `ISA95StateDataType` (`StateText: LocalizedText`, `StateNumber: UInt32`), `ISA95JobOrderDataType` (`JobOrderID`, `Description[]`, `WorkMasterID[]`, `Priority`, `JobOrderParameters[]`), `ISA95JobOrderAndStateDataType` (`JobOrder`, `State[]`) у просторі 4 (`new_struct`); типи подій `WwBaseEventType` (`MessageId`, `MessageName`, `EventCategory`, `PathParts`, `Group`, `LocalizedMessages`, `Arguments`) і `WwAlarmConditionType` (підтип `AlarmConditionType` з тими самими полями) у просторі 3; об'єкт `Objects/Machines/SAW-T` з вузлами `SAW-T.State.Machine.Overview.CurrentState` (Int32), `.CurrentMode` (Int32), `SAW-T.State.Machine.Flags.Alarm` (Boolean), `SAW-T.State.Machine.Values.RelativePiecesOut` (UInt64), `SAW-T.JobManagement.JobOrderControl.JobOrderList` (масив структур), `SAW-T.Events` (`EventNotifier=SubscribeToEvents`), методи `JobOrderControl.{Store, StoreAndStart, Start, Stop, Pause, Resume, Cancel, Abort, Clear}`; помічники `set(var, value)`, `set_jobs([(id, state_text)])`, `fire_event(kind, message_id, category, text_uk, text_en, active=True)`, `calls: list[(method, args)]`, `ret_status` (0), `stop()`, `start()` (той самий порт) |
| `woodstore_app` | `fakes/woodstore_app.py`: `aiohttp` API-20…27 у пам'яті (стан `status`, 27 стосів `PLT-01A…PLT-09C`, `jobs`, `events`), перевірка `X-Api-Key == 'ws-key'` (`401`), журнал `calls[(method, path, query, json)]`; помічники `add_events(n)`, `set_status(**kw)`, `conflict_next=True` (наступний `POST /jobs` → `409 {"error": "not enough sheets"}`) |
| `cutopt_app` | `fakes/cutopt_app.py`: API-30…34 (`jobs[id] = {state, plan, mpr}`), `X-Api-Key == 'co-key'`; `POST /jobs` зберігає multipart (`parts`, `material`, `sheet`, `external_ref`, `machine`) і віддає `202 {"job_id": "cj-1", "state": "optimizing", "eta_s": 5}`; `advance("cj-1", "planned", plan=…)` |
| `fake_odoo_export` | `aiohttp` сервер з `GET /f3d/machine/cutmap/<id>/export`: перевіряє `Authorization: Bearer <collector_token>`, програмовані відповіді (`200` з JSON API-01, `410`, `403`) |
| `opcua_plugin(ctx, ua_server, vclock)` / `rest_plugin(ctx, app, vendor)` | плагін з `SourceCfg` (`params` за Додатком C.1 з `endpoint`/`base_url` фейка, `ns_uri=http://todo.ltd/f3d/iot_sim/instances/`) і `SignalCfg` за шаблонами Додатка C.2 для коду `SAW-T` |

Маркери: `asyncio` (усі), `timeout(30)`; жодних зовнішніх мереж і Docker.

### 13.1 Юніт-тести

#### 13.1.1 Odoo (`odoo_addons/td_machine_connect/tests/`)

Кожен файл — один клас `F3DMachineCase` (крім `test_api_export.py` — `F3DMachineHttpCase`). Колонка «Перевірити
також» — що додати до Then з AC (стани, кількості, відсутність побічних ефектів).

| Файл::клас | Тести | AC | Особливі фікстури | Перевірити також |
|---|---|---|---|---|
| `test_normalize.py::TestNormalize` | `test_examples_r01` (11 `subTest`), `test_unknown_text_nodata_warns_once`, `test_io_alarm_wins` | AC-01…03 | — (чисті функції) + `m_io` для AC-03 | AC-02: другий виклик тієї ж години — без WARNING (`assertNoLogs`), о `+1 год` — знову WARNING |
| `test_state_log.py::TestStateLog` | `test_transition_closes_and_opens`, `test_micro_stop_absorbed`, `test_pending_committed_by_cron`, `test_late_reading_ignored`, `test_machine_state_signal`, `test_collector_cannot_feed_derived` | AC-04…08 | `make_log(m_ua, 'idle', kt('09:50'))` + `m_ua.current_log_id`, `state='idle'` через `set_sql` | `duration_min` закритого інтервалу = 5,0; `in_ppt_min` = 5,0; інтервали не перекриваються; `sig_ua_mstate.last_text` |
| `test_ppt.py::TestPpt` | `test_ppt_monday`, `test_ppt_dst`, `test_ppt_saturday`, `test_leave_subtracted`, `test_stale_to_nodata`, `test_bad_quality_nodata` | AC-09, AC-10 | `resource.calendar.leaves` на `wc_ua.resource_id` 10:00–11:00 (`time_type='leave'`) і слот `time_type='other'` | `ppt_intervals` повертає список пар naive UTC, відсортований; AC-10: `current_downtime_id` закрито `now`, таймери завдання не змінені |
| `test_downtime.py::TestDowntime` | `test_fault_blocks_wc`, `test_idle_no_timelog_until_close`, `test_idle_lunch_and_after_shift`, `test_day_boundary`, `test_set_reason_rights`, `test_confirm_rights` | AC-11…16 | `make_mo(wc_ua)`; WO стартує `start_employee(emp_ua)` від `user_mrp` о 09:29 | AC-11: `wo.time_ids` закритий запис має `date_end=09:42:00` (не `now`); AC-12: `mrp.workcenter.productivity.search_count([('td_downtime_id','=',d.id)])` 0 → 1; AC-14: крон 15:30:30 не відкриває нового до 07:00 вівторка (`at('07:00:30', day=D0+1)`) |
| `test_merge_operator.py::TestMerge` | `test_operator_block_during_fault`, `test_operator_block_before_stop`, `test_working_closes_operator_record`, `test_unblock_reopens_fault_record` | AC-17…20 | записи оператора — `mrp.workcenter.productivity.with_user(user_mrp).create({...})` без `workorder_id` | жоден запис оператора не видалено (`exists()`); `td_source` (`operator`/`master`) за групою творця |
| `test_hints.py::TestHints` | `test_event_after_state`, `test_event_before_state`, `test_setup_hint`, `test_idle_blocked_hint_not_applied`, `test_alarm_request_linked_once` | AC-21…24 | повідомлення `E0421` з Додатка B (data); `make_mo(wc_ua)` з другою операцією `blocked` для AC-23 | AC-21: `td.machine.event` один (повтор `ev_ua` з тим самим вмістом — дублікат, `td.push.event` один); AC-24: `maintenance.request.search_count([('equipment_id','=',eq_ua.id)]) == 1` |
| `test_autostart.py::TestAutostart` | `test_start_by_job`, `test_single_ready_io`, `test_two_ready_no_start_activity`, `test_job_mode_requires_job`, `test_unknown_job_activity`, `test_idempotent`, `test_blocked_wc_unblocked`, `test_employee_order`, `test_stop_crane`, `test_send_to_machine` | AC-25…32, AC-101 | `enable_autostart()`; WO id → текст `f"WO{wo.id:05d}"`; AC-31: `wc_ua.employee_ids = emp_saw + emp_x`, записи журналу часу сьогодні від `emp_saw` | AC-25: `create_uid` таймера = `user_td_machine`, чатер МО містить «стартував верстат UA-T»; AC-29: `mock.patch.object(type(env['mrp.workorder']), 'start_employee', autospec=True, side_effect=…wraps)` — `call_count == 1`; AC-32: `write_date` WO не змінився |
| `test_counter_finish.py::TestCounterFinish` | `test_counter_reset_and_jump`, `test_live_sync`, `test_finish_by_job_change`, `test_partial_hold`, `test_io_finish_after_idle`, `test_finish_partial_rights`, `test_autopause_resume` | AC-33…38 | `enable_autostart()`; `make_mo(wc_ua, qty=14)` стартоване автостартом о 09:55 | AC-33: WARNING `assertLogs`; AC-35: `production.qty_producing` не змінився автоматикою до завершення; AC-38: тривалості таймерів у хвилинах (`duration`) збігаються з інтервалами ±0,05 |
| `test_oee.py::TestOee` | `test_saw1_macket`, `test_saw1_real`, `test_cnc2`, `test_saw3`, `test_period_two_shifts`, `test_nodata_coverage`, `test_timelog_source`, `test_cron_open_close_rotate` | AC-39…44 | журнали — `make_log` (сума хвилин за таблицею R-13; прості — `td.downtime` з `loss_id`); брак — `stock.scrap` (`workorder_id`, `state='done'`, `date_done=kt('10:00')`); AC-41 — два записи `td.oee.shift` `closed` через `sudo().create` | `compute_oee` викликається напряму для AC-39/40 з вхідним словником (чиста функція) і через `_td_oee` — результати рівні; AC-44: ротація видаляє лише інтервали з `date_end < now − 400 діб` |
| `test_energy_contract.py::TestEnergyContract` | `test_wo_intervals_window`, `test_wc_intervals`, `test_run_setup_minutes` | AC-45, AC-46 | `make_log` з `wo`; закриття — через диспетчер (`ua(...)`) для AC-46 | повернення — `dict[int, list[tuple[datetime, datetime, str]]]`, naive UTC, відсортовано; відкритий інтервал обрізано `now` |
| `test_gantry_stack.py::TestGantryStack` | `test_fed_unconsumed`, `test_pending_then_diff`, `test_product_mismatch`, `test_status_event`, `test_accept_portal`, `test_fix_portal_needs_write`, `test_replenish_once_per_hour` | AC-47…51 | `put_stock(board, loc_t1, 45, lot_l1)`; завдання порталу `done=7` з МО `make_mo(wc_saw)` у `progress`; EV-02 через `push_event('mc_woodstore', {"kind": "stacks", …}, 'REST-WOODSTORE-T')`; правило поповнення `stock.warehouse.orderpoint` на `loc_t1` (min 10, max 60) | AC-48: діяльність одна навіть після 3 кронів; AC-50: `stock.quant` `quantity` 43, `stock.move` інвентаризації `done` |
| `test_gantry_job.py::TestGantryJob` | `test_from_production_no_dup`, `test_send_payload`, `test_command_results`, `test_mirror_and_sheets`, `test_consume_move_lines` | AC-52…56 | `make_mo(wc_saw, name='WH/MO/T0001', comps=((board, 4/14),))` (рух 4 арк., резерв у `PLT-T1`); `enable_write()` для AC-53/54 | AC-53: `td.command.payload` і `text`, `signal_id=sig_g_cmd`, `origin='machine_connect'`, `td_gantry_job_id`; AC-55: `sheet_log` без дубля за id події; AC-56: `stock.move.line` `PLT-T1` зменшено на 4, `PLT-T2` 4 `picked` |
| `test_commands.py::TestCommands` | `test_build_parse_examples`, `test_five_fuses`, `test_payload_and_label`, `test_fallback_text_mode` | AC-57, AC-58, AC-102 | `enable_write()`, потім вимикати по одному; AC-102 — `patch.object(type(env['td.command']), '_td_mc_payload_supported', return_value=False)` (X-93) | текст `UserError` містить ключ запобіжника (`td.machine_connect.write_enabled`, `td.telemetry.write_enabled`, код джерела, код сигналу) |
| `test_cutmap.py::TestCutMap` | `test_part_constraints_and_import`, `test_create_lines_and_fit`, `test_export_csv`, `test_send_optimizer_token`, `test_apply_job_plan_mpr`, `test_sheets_warning_and_update_need`, `test_release_and_manual_plan`, `test_csv_formula_prefix_stripped` | AC-59…65 | BOM з `td.cut.part` `P001` (720×560, 2 шт, текстура 1, `edge_top=edge_left='EB-T'`); МО `make_mo(wc_saw, qty=14, comps=((board, 8/14),))`; `enable_write()` | AC-61: байти вкладення `== expected.encode()` (CRLF, без BOM); AC-62: `export_token_hash` недоступний `user_f3d_manager` (`AccessError` на `read`); `test_csv_formula_prefix_stripped`: назва `=SUM(A1)` → `Description` `SUM(A1)` (R-19 п. 5) |
| `test_api_export.py::TestApiExport` (HttpCase) | `test_export_ok_once`, `test_errors`, `test_too_large` | AC-66…68 | карта в `exported` з токеном (`_td_new_export_token()` від `sudo`); 6 000 рядків — через `sudo().create` | порядок перевірок API-01 (без Bearer — `401` навіть з невірним `t`); тіло помилки `{"error": {"code", "message"}}` |
| `test_migration.py::TestMigrationClean`, `::TestMigrationDemo` | `test_clean_db_zero`, `test_losses`, `test_sheets`, `test_machines_signals`, `test_stacks`, `test_demo_journal`, `test_idempotent` | AC-81…85 | `TestMigrationDemo` — лише на копії демо (`skipUnless`); `TestMigrationClean` — `with patch('odoo.addons.td_machine_connect.hooks._csv_rows', side_effect=…)` на 2 РЦ фікстур | повтор `run_migration(env)` → `signals_created: 0`, `downtimes_created: 0`, кількості моделей незмінні; `migration_report.state == 'done'` |
| `test_viewer_provider.py::TestViewerProvider` | `test_collect_payload`, `test_no_oee_keeps_input`, `test_bus_and_delta` | AC-86…88 | payload-вхід — словник у тесті (без viewer); `td.oee.shift` для `m_saw` за `D0` | `tools.payload.build_machines` повертає ті самі ключі, що й `_td_viewer_collect` дописує; провайдер не кидає винятків для `m_cnc` (`manual`, без сигналів) |
| `test_security.py::TestSecurity` | `test_menu_and_access_matrix`, `test_settings_admin_only`, `test_tech_user` | AC-89…91 | користувачі фікстур; матриця §13.3 | `ir.ui.menu` `menu_td_mc_root` видиме `user_f3d` і невидиме `user_plain` (`_visible_menu_ids`); `menu_td_mc_settings` (під `td_factory3d.menu_td_config`, X-32) видиме `user_f3d_manager` і невидиме `user_f3d` |
| `test_hooks.py::TestHooks` | `test_uninstall_hook_params_crons`, `test_neutralize_sql` | AC-92 | `uninstall_hook(env)` у транзакції тесту (відкочується); SQL з `data/neutralize.sql` через `cr.execute` | після SQL: три стоп-крани `False`, `cutting_mode='manual'`, крони модуля `active=False`, `td.machine.read_enabled=False` усім |

#### 13.1.2 Колектор (`services/collector_plugins/machine_connect/tests/unit/`)

Запуск: `pytest services/collector_plugins/machine_connect -m "not stand"`.

| Файл | Тести | AC | Фікстури | Перевірити також |
|---|---|---|---|---|
| `test_nodeids.py` | `test_resolve_by_uri`, `test_fallback_index`, `test_missing_uri`, `test_validate_errors` | AC-69 | `ns_array` — список у тесті | `validate` відхиляє `ns=2;x=1`, `ns=;s=a`, рядок 241 символ |
| `test_opcua_subscribe.py` | `test_initial_values`, `test_change_emits`, `test_job_select_running_or_first`, `test_heartbeat_60s`, `test_session_shared` | AC-70, AC-71 | `ua_server`, `vclock`, 2 джерела `UA-SAW-T`, `UA-SAW-T2` на один endpoint | одна сесія (`pool.sessions == 1`); `ts` показань = `SourceTimestamp`; серцебиття не шлеться при `offline` |
| `test_opcua_events.py` | `test_alarm_event_payload`, `test_event_dedup_id`, `test_unknown_event_type_fallback` | AC-72 | `ua_server.fire_event('alarm', 'E0421', 5, 'Помилка шпинделя осі Z', 'Spindle error axis Z')` | `payload` відповідає EV-01 (усі обов'язкові ключі, `time` з `Z`), `event_id` стабільний для однакового вмісту |
| `test_opcua_reconnect.py` | `test_server_down_bad_quality`, `test_reconnect_resubscribe`, `test_backoff_sequence` | AC-73 | `ua_server.stop()/start()`, `vclock` | бекоф 1, 2, 4, …, 60 с (`vclock.sleeps`); після переп'єднання зміна змінної дає показання; `collector_mc_opcua_reconnects_total` = 1 |
| `test_opcua_call.py` | `test_store_and_start`, `test_stop`, `test_return_status_error`, `test_write_disabled`, `test_bad_command`, `test_not_job_signal`, `test_write_text_fallback` | AC-74, AC-103 | `ctx.settings.write_enabled=True`, `ua_server.ret_status` | `ua_server.calls[-1]` — аргументи (`JobOrderID`, `Priority`, параметри `PlannedOrderQuantity=14.0`, `OrderNumbers=["WH/MO/00233"]`); при `write_enabled=False` викликів 0 |
| `test_woodstore.py` | `test_poll_status`, `test_status_event_on_change`, `test_events_cursor`, `test_stacks_hash_and_resend`, `test_jobs_changed_only`, `test_commands`, `test_commands_text_fallback` | AC-75…77, AC-103 | `woodstore_app`, `tmp_path` курсорів | курсор переживає перезапуск плагіна (новий екземпляр читає файл); `401` → `health().error == "auth"` |
| `test_cutopt.py` | `test_upload_flow`, `test_upload_export_gone`, `test_status_planned`, `test_release`, `test_mpr` | AC-78, AC-79 | `cutopt_app`, `fake_odoo_export` | `parts.csv` у multipart побайтово = `parts_csv` з API-01; токен колектора не потрапляє в лог (`caplog`) |
| `test_cmdtext.py` | `test_identical_to_odoo_tool`, `test_no_odoo_imports`, `test_examples` | AC-80, AC-57 | шлях до `odoo_addons/td_machine_connect/tools/commands.py` відносно кореня репозиторію | `filecmp.cmp(..., shallow=False)`; `ast.walk` — немає `Import`/`ImportFrom` з `odoo` (X-93) |

### 13.2 Стендові сценарії (ТК) — емулятор `td_iot_sim` + колектор з пакетом + Odoo

Стенд — той самий, що в telemetry §13.2 (Q-17 telemetry): хост із Docker; `docker compose -f docker-compose.sim.yml
--profile dev up -d` (iot_sim); Odoo 19 у контейнері `odoo19` з **копією** демо-бази після DEPLOY_TEST п. 1–3 (§13.5);
колектор `docker compose -f docker-compose.collector.yml up -d` з пакетом `f3d_collector_mc` у
`requirements-extra.txt` і `.env`: `F3D_OPCUA_PASSWORD=$SIM_OPCUA_PASS`, `F3D_WOODSTORE_KEY=$SIM_WOODSTORE_APIKEY`,
`F3D_CUTOPT_KEY=$SIM_JOBS_APIKEY`, `F3D_ALLOW_HOSTS=iot-sim,odoo19`, `F3D_WRITE_ENABLED=0` (у ТК-04, 06, 07, 10, 15 —
`1`, перезапуск колектора). Параметри джерел `UA-*` на стенді — `username: "collector"`, `password_ref:
"F3D_OPCUA_PASSWORD"` (Додаток C.1).

Правила часу (обов'язкові для всіх ТК з Odoo): емулятор `factor=1`, годинник емулятора = реальний (`POST
/sim/v1/time {"set": "<зараз, ISO з +03:00>"}`), `|sim_now − real_now| ≤ 5 с` за `GET /status`. Причина: плагін
замінює час із майбутнього на час прийому, а серцебиття шле `ts = now` (R-22 п. 3–4) — sim-час, відмінний від
реального, робить наступні показання «пізніми» (R-02 п. 1). Плановий час Odoo — реальний календар (R-26), тому ТК-01…
ТК-15 виконуються в робочий час (пн–пт 07:30–15:00 за Києвом; поза зміною верстати без завдань — `off`, а не `idle`),
ТК-16 — з 15:00 до 15:40.

Перед кожним ТК: `POST /sim/v1/reset {"keep_time": true}`; режим емулятора — як у колонці «Передумови»; база —
свіжа копія з шаблону `odoo_f3d_mc_t0` (DEPLOY_TEST п. 3: `createdb -T odoo_f3d_mc_t0 odoo_f3d_mc_tk`), крім ТК, що
явно продовжують попередній. Автоматизація: `pytest odoo_addons/td_machine_connect/tests/stand -m stand` у
контейнері `stand-runner` у мережі `f3d_sim` (порти 4840/8082/8083 доступні лише там), env: `F3D_STAND_ODOO_URL`,
`F3D_STAND_ODOO_DB`, `F3D_STAND_ODOO_LOGIN`, `F3D_STAND_ODOO_PASSWORD` (XML-RPC до копії), `F3D_STAND_SIM_URL`
(`http://iot-sim:8090/sim/v1`), `SIM_API_TOKEN`, `F3D_STAND_OPCUA` (`opc.tcp://iot-sim:4840/f3d/`), `SIM_OPCUA_USER`,
`SIM_OPCUA_PASS`, `SIM_WOODSTORE_APIKEY`, `SIM_JOBS_APIKEY`. Помічники `tests/stand/helpers.py`: `odoo(model, method,
*args, **kw)`, `sim(method, path, body=None)`, `wait_until(fn, timeout_s, every_s=2)`, `ua_call(code, method, *args)`
(asyncua з користувачем `SIM_OPCUA_USER`), `ua_jobs(code)` (читання `JobOrderList`), `ws(method, path, body=None)`
(woodStore з ключем). Результати — `docs/modules/td_machine_connect/TEST_REPORT.md` (ТК, дата/час, фактичні
значення, статус). Позначки «MAN» — кроки в UI, які виконує людина (тестувальник фіксує скриншот у звіті).

| ТК | Назва | Передумови | Кроки | Очікуваний результат (AC) | Де дивитися |
|---|---|---|---|---|---|
| ТК-01 | Установка, міграція й читання 35 верстатів | копія після DEPLOY_TEST п. 1–2 (модуль ще не встановлено); емулятор `follow_odoo` на цю копію | 1) знімки S0–S5 (§13.5 п. 2); 2) `odoo-bin -d <копія> -i td_machine_connect --stop-after-init --log-level=info`; 3) звіт міграції; 4) `docker compose restart collector`; 5) 3 хв | AC-83…85; AC-93: 29 `working`, 5 `idle` (SAW-3, VSAW-1, EDGE-3, UV-1, ASM-5), CNC-2 `fault` (стан міграції, інтервалу немає), 34 відкриті інтервали; джерела `UA-*` (15), `MB-*` (4), `REST-*` (2) — `online`, `MC-DERIVED` — `online`; `mrp.workorder` і `mrp.workcenter.productivity` не змінювались (макс. `write_date` = S4); команд 0 | «Огляд верстатів», «Журнал станів», Телеметрія → Джерела |
| ТК-02 | Аварія CNC-2 (`machine_fault CNC-2`) | ТК-01 (та сама копія); `POST /mode {"mode": "scenario"}`, без `shift` | 1) 3 хв; 2) `POST /scenario/machine_fault/start {"params": {"device": "CNC-2", "reason": "spindle"}}` (тіло iot_sim API-13, X-57); 3) 10 с; 4) MAN: «Простої без причини» → картка CNC-2 → «Поломка» (оператор), «Підтвердити» (майстер); 5) `POST /scenario/machine_fault/stop`; 6) 2 хв | крок 1: CNC-2 `fault` → `idle` (READY без завдання): простій міграції закрито `ts` переходу, запис «Equipment Failure» закрито тим самим `ts`, РЦ CNC-2 `working_state != 'blocked'`, MR/00031 без змін (R-08 п. 4); AC-94: крок 3 — `fault`, новий простій `hint` «Поломка», `hint_text` «E0421 Помилка шпинделя осі Z», подія `E0421` у «Події верстатів», відкритий запис «Поломка» (`td_auto`), РЦ `blocked`, одна нова заявка «CNC-2: аварія верстата» з `td_signal_id` = `workcenters/CNC-2/alarm` і повідомленням «Подія верстата: E0421 …», `downtime.maintenance_request_id` = вона; крок 4 — `reason_state='confirmed'`; крок 6 — `idle`, простій `fault` закрито, запис закрито, РЦ розблоковано, заявка відкрита | Огляд, Простої, Обслуговування → Заявки, 3D (якщо є viewer) |
| ТК-03 | Зміна `shift` — лише читання | ТК-01; `scenario`; `auto_start_enabled=False`, `write_enabled=False` | 1) `POST /scenario/shift/start {"params": {"speed": 1, "trucks": false, "people": false}}`; 2) 60 хв; 3) `_cron_oee` (або 5 хв); 4) звіти | для кожного з 35: інтервали журналу без розривів і перекриттів (`date_start` наступного = `date_end` попереднього), сума тривалостей від першого переходу = минулому часу ±1 хв; інтервалів < 120 с у станах простою немає; прості < 120 с не записані; записів `mrp.workorder`/`mrp.workcenter.productivity` з `write_uid = user_td_machine` — 0; команд 0; `td.oee.shift` за сьогодні `open` для 35, `coverage ≥ 0,95`; події I0001/I0002 OPC UA-верстатів у «Подіях»; діяльностей «не знайдено в Odoo» — 0 (автостарт вимкнено) (AC-100 частково) | Журнал станів (pivot за `code`, `state`), OEE |
| ТК-04 | Автостарт і автозавершення за завданням верстата (SAW-1, OPC UA) | ТК-01; `scenario` без `shift`; `auto_start_enabled=True`; запис для `workcenters/SAW-1/job_cmd` (параметри модуля й telemetry, джерело `UA-SAW-1`, сигнал, `F3D_WRITE_ENABLED=1`); WO00013 завершено вручну (MAN, майстер у «Цеху»); нове МО «Комод 4 шухляди» × 2 підтверджено (WO «Розкрій» на SAW-1 `ready`, позначимо N) | 1) WO N → «Надіслати на верстат» (`action_f3d_send_to_machine`); 2) 30 с; 3) `ua_call("SAW-1", "Start", "WO%05d" % N, [])` (оператор на пульті); 4) чекати завершення завдання емулятором (≈ 15 + 2,2 × 2 хв); 5) повтор `Start` того ж `JobOrderID` | AC-101: команда CMD-01 `Store` (`payload` `{"method": "Store", "job": "WO000NN", "qty": 2, "ref": "WH/MO/…", "priority": 5}`) `done`, `result_data={"ReturnStatus": 0}`, `ua_jobs("SAW-1")` містить WO N `AllowedToStart`; AC-95: ≤ 15 с після `WORKING` — WO `progress`, таймер `employee_id` = Олег Мельник (OP-SAW-1), `create_uid = user_td_machine`, `td_auto_started`; `td_qty_counted` росте з `RelativePiecesOut`; після `Completed` — `qty_produced = 2`, `state='done'`, чатер МО «…завершив верстат SAW-1: 2 шт»; Σ хвилин таймерів WO = Σ інтервалів `working` з WO ±1 хв; `_td_wo_intervals(WO)` = ці інтервали, `td_run_min` = їх сума (контракт energy, AC-45/46 на стенді); крок 5 — другого таймера немає | WO (вкладка «Верстат»), МО (чатер), Журнал станів |
| ТК-05 | Автостарт «одне в черзі» й лічильник ADAM (SLIDE-1, I/O) | ТК-01; `scenario`; `auto_start_enabled=True`; SLIDE-1 має одне завдання `progress` WO00101 з таймером оператора (демо); `qty_remaining` = R | 1) `PUT /signals/workcenters/SLIDE-1/state {"value": 1, "hold_s": 1800}`; 2) `PUT …/pieces_out {"value": 65534}`, потім `65535`, `65537` (перехід через межу слова), далі +1 кожні 20 с до `65537 + R − 3`; 3) `PUT …/state {"value": 0, "hold_s": 600}`; 4) 70 с; 5) `PUT …/alarm {"value": 1, "hold_s": 120}` | крок 1: ≤ 5 с `working`, `active_workorder_id` = WO00101, другого таймера немає (R-09 п. 4а); крок 2: прирости 1, 2, 1, … — `td_qty_counted = R` (порядок слів `little`, A-28; при хибному порядку — WARNING «стрибок», тест падає); крок 4: WO00101 `done`, `qty_produced = qty_production`; крок 5: `fault`, простій «Поломка» з `hint_text` «Вхід аварії», заявка одна (`workcenters/SLIDE-1/alarm`) | WO00101, Журнал станів |
| ТК-06 | Портал: подача плити за МО і списання | ТК-01; `scenario`; запис для `equipment/GANTRY-1/cmd` (5 запобіжників) | 1) МО WH/MO/00233 → «Подати порталом»; 2) «Надіслати»; 3) 5 хв; 4) звірка `PLT-03C`; 5) MAN: закрити МО (майстер) і знову звірка | AC-96: ПОРТ/… `feed`, `PLT-03C`, SAW-1, 4 арк. DSP16-ANT, партія DSP16-ANT-2613-130; команда CMD-02 `feed` (`text` `feed;PLT-03C;SAW-1;4;DSP16-ANT;5;WH/MO/00233`) `done` → `ws_id = result_data.id = wj-…` → `queued` → `active` → `done`, `done=4`, `sheet_log` 4; рядок руху МО `PLT-03C` 4 `picked`, `consumed_qty=4`; стос `PLT-03C`: `ws_qty` −4, `fed_unconsumed=4`, `state='ok'`; після закриття МО квант −4, `fed_unconsumed=0`, `ok` | Портал → Завдання, Стоси; МО → Компоненти |
| ТК-07 | Розбіжність стосу, виправлення, поповнення | ТК-01; `scenario`; запис для `equipment/GANTRY-1/cmd`; користувач з `stock.group_stock_manager` | 1) `ws("PATCH", "/api/v1/stacks/PLT-01B", {"qty": q − 2, "reason": "test"})`; 2) 60 с; 3) 10 хв; 4) MAN «Прийняти з порталу»; 5) `PATCH … {"qty": q' + 3}`, через 10 хв «Виправити портал»; 6) `PATCH /stacks/PLT-08A {"qty": 9}`, `gantry_auto_replenish=True`; 7) 2 хв; 8) MAN: виконати WH/INT | крок 2: `pending`; крок 3: `diff`, одна діяльність начальнику складу «Стос PLT-01B: портал …, має бути …»; крок 4: квант = `ws_qty + fed`, `ok`, діяльність закрита «Збігається»; крок 5: команда CMD-02 `stack` (`stack` PLT-01B, `qty` = `<expected>`, `product` DSP16-WNG, `lot` — партія) `done`, портал = `expected`, `ok`; крок 7: WH/INT у `PLT-08A` за правилом «Поповнення під портал» (одне); крок 8: команда CMD-02 `stack` для `PLT-08A` (`qty` = `<n>`) (AC-47, 48, 50, 51 на стенді) | Стоси (kanban), Склад → Переміщення |
| ТК-08 | Події порталу: завдання з пульта woodStore і тривога | ТК-01; `scenario`; запис вимкнено | 1) `ws("POST", "/api/v1/jobs", {"type": "feed", "source": "PLT-04C", "target": "SAW-2", "sheets": 2, "product": "DSP16-SON", "external_ref": "WH/MO/00231"})`; 2) 2 хв; 3) `POST /scenario/machine_fault/start {"params": {"device": "GANTRY-1"}}` (X-57); 4) 30 с; 5) `stop` | AC-55: нове завдання `origin='machine'`, `production_id` = WH/MO/00231, `done=2`, `sheet_log` 2; стос PLT-04C −2, `fed_unconsumed` +2, `ok`; AC-49: `equipment/GANTRY-1/state` = `error`, параметр `gantry_status` з `alarms`, чатер GANTRY-1 «Тривога порталу: …», одна заявка «GANTRY-1: аварія порталу» (Додаток C.2 `g_state`); команд 0 | Портал → Завдання; GANTRY-1 (Обслуговування) |
| ТК-09 | Карта розкрою вручну (формат intelliDivide не підтверджено, Q-03) | ТК-01; `cutting_mode=manual`; деталі BOM «Комод 4 шухляди» з `tests/stand/data/parts_BR-K4.csv` (M-26, MAN) | 1) WH/MO/00233 → «Створити карти розкрою»; 2) карта `main` → «Зібрати деталі», «Експортувати»; 3) «Завантажити CSV»; 4) `POST http://iot-sim:8083/jobs` з цим CSV (оператор intelliDivide), `GET /jobs/{id}/plan` → файл; 5) MAN: «Імпортувати план» (M-25); 6) «Випустити» | CSV: заголовок R-19 п. 5, CRLF, без BOM, рядків = деталей карти, `Quantity` = `ceil(qty × 14)`; план → `planned`, `plan_sheets = total_sheets`, `plan_waste_pct`; «Випустити» → `released` без команд (0 `td.command`); вкладення `КР/…_parts.csv`, `КР/…_plan.json` | Розкрій → Карти |
| ТК-10 | Карта розкрою через колектор → верстат → портал | ТК-09 крок 1–2 на свіжій копії з `cutting_mode=collector`; запис для `equipment/CUTOPT/cmd`; `auto_start_enabled=True` | 1) «Експортувати» (→ `upload`); 2) 30 с; 3) «Випустити на верстат»; 4) `ua_jobs("SAW-1")`; якщо `cj-…` за 60 с не `Running` — `ua_call("SAW-1", "Start", "cj-…", [])`; 5) до завершення | AC-97: команда `upload` (`payload` `{"op": "upload", "map": <id>, "token": <16 hex>}`) `done` → `ext_job_id = result_data.job_id = cj-…` → `planned` (`plan_sheets > 0`) → `released`; API-01 викликано один раз (лог Odoo `200`, повтор `403`); у порталі `feed` на `total_sheets` з `external_ref` МО → дзеркало `origin='machine'`, `cut_map.gantry_job_id`; WO розкрою стартував автоматично за `cj-…` (R-09 п. 1), карта `running` → `done` | Карта (чатер, вкладення), WO, Портал |
| ТК-11 | Причини простоїв: планшет і злиття з оператором | ТК-01; `scenario`; користувачі: оператор (`mrp.group_mrp_user`, працівник OP-SAW-2), майстер (`mrp.group_mrp_manager`) | 1) `PUT /signals/workcenters/SAW-2/state {"value": 2, "hold_s": 900}` (READY); 2) 3 хв; 3) MAN оператор: «Простої без причини» → SAW-2 → «Очікування матеріалу»; 4) MAN оператор у «Цеху» на SAW-2: «Заблокувати» → «Заміна інструменту»; 5) MAN майстер: «Підтвердити простої»; 6) `PUT … {"release": true}` (повернення до моделі емулятора) | крок 2: простій `idle` з 120 с затримкою від `ts`; крок 3: `operator`, `to_confirm`; крок 4: запис оператора прив'язано (AC-17/18 на стенді), машинний запис закрито його `date_start`, перекриттів у журналі часу РЦ немає; крок 5: `confirmed`; крок 6: записи закрито, РЦ розблоковано (AC-19) | Простої (kanban), «Цех», Журнал часу РЦ |
| ТК-12 | Втрата зв'язку з верстатом | ТК-01; `scenario` + `shift` | 1) `POST /scenario/machine_fault/start {"params": {"device": "CNC-3", "reason": "comm"}}` (X-57); 2) 3 хв; 3) `stop`; 4) 2 хв | AC-98: ≤ 10 с показання `q='bad'` → CNC-3 `nodata` (не пізніше 180 с — через `stale`), інтервал `nodata`, простій (якщо був) закрито, таймери завдань CNC-3 не змінені, заявок нових 0; `coverage` CNC-3 < 1; крок 4: стан відновлено, новий інтервал | Журнал станів, OEE (`coverage`) |
| ТК-13 | Відмова Odoo й буфер колектора | ТК-01; `scenario` | 1) `PUT /signals/workcenters/SAW-1/state {"value": 3, "hold_s": 1800}`; 2) `docker compose stop odoo19`; 3) через 2 хв `PUT … {"value": 2, …}` (T1), через 5 хв — `{"value": 3}` (T2); 4) через 3 хв `start odoo19`; 5) 5 хв | інтервал SAW-1 `idle` `[T1, T2)` ±2 с (час показань, §11 п. 2), простій `idle` з `date_start = T1`, `ppt_min ≈ 5`; дублікатів інтервалів немає; буфер колектора спорожнів ≤ 2 хв | Журнал станів SAW-1; `/metrics` колектора |
| ТК-14 | 3D-переглядач | ТК-01; `td_viewer3d` установлено; `scenario` | 1) Завод 3D → 3D; 2) картки SAW-1, CNC-2, стос PLT-03C; 3) `POST /scenario/machine_fault/start {"params": {"device": "SAW-2"}}` (X-57); 4) 15 с | AC-86…88 на стенді: стан, OEE зміни з `td.oee.shift`, поточний простій і причина; крок 4 — SAW-2 `status=stop` без перезавантаження сторінки; стос: портал/Odoo/подано | 3D |
| ТК-15 | Стоп-крани в роботі | ТК-01; `scenario` + `shift`; `F3D_WRITE_ENABLED=1` | 1) 10 хв з `auto_start_enabled=False`; 2) увімкнути `auto_start_enabled` (адмін); 3) 10 хв; 4) `read_enabled=False` (параметр); 5) 3 хв; 6) повернути; 7) для `equipment/GANTRY-1/cmd` вимикати по одному: параметр модуля, параметр telemetry, джерело, сигнал, `F3D_WRITE_ENABLED=0` — щоразу «Надіслати» завдання порталу | крок 1: WO не змінені автоматикою; крок 3: I/O-верстат з єдиним завданням `ready`/`progress` у черзі Odoo при переході в `working` стартує/підхоплює його (R-09 п. 2, AC-32 на стенді); OPC UA-верстати: `JobOrderID` планувальника у форматі `WO%05d` (X-38, Q-17 закрито) стартує відповідне завдання Odoo, якщо воно в черзі РЦ, інакше — діяльність «не знайдено в Odoo», одна на текст; крок 5: стани верстатів не змінюються, `MC-DERIVED` `disabled`, показання telemetry пишуться; крок 7: перші чотири — `UserError`/`to_send` з назвою запобіжника, п'ятий — команда `queued` → `expired` «Колектор не забрав команду» (AC-58) | Огляд, Телеметрія → Команди |
| ТК-16 | Кінець зміни: прості й OEE | ТК-01; `scenario` + `shift`; старт о 15:00, кінець о 15:40 | 1) `PUT /signals/workcenters/EDGE-3/state {"value": 2, "hold_s": 3600}` (простій через межу зміни); 2) до 15:40; 3) «OEE за період» за сьогодні | о 15:30 простій EDGE-3 закрито `15:30:00` (R-05 п. 6), нового немає; о ≥ 15:35 `td.oee.shift` за сьогодні `closed`, повторний крон не змінює (AC-44 на стенді); для кожного запису `abs(oee − availability × performance × quality) ≤ 0,0001`, `run_min + down_min + unexplained_min = ppt_min ± 0,5` | OEE (list, pivot) |

### 13.3 Тести безпеки (ТБ)

| ТБ | Перевірка | Як | Очікувано |
|---|---|---|---|
| ТБ-01 | Матриця прав і меню | AC-89…91 за таблицею нижче (`with_user(u)`, `check_access`); UI: `user_plain` не бачить «Завод 3D → Верстати»; URL `/odoo/action-td_machine_connect.action_td_machine_dashboard` від `user_plain` → помилка доступу | як у таблиці |
| ТБ-02 | П'ять запобіжників запису | AC-58, ТК-15; огляд коду пакета: `grep -rnE "write_value\|set_value\|write_attribute\|write_params" services/collector_plugins/machine_connect/f3d_collector_mc` → 0 (плагін не пише змінні OPC UA, лише викликає методи `JobOrderControl`) | команди не створюються/не видаються при будь-якому вимкненому; змінні верстата не змінюються ніколи |
| ТБ-03 | Експорт API-01 | AC-66…68; стенд: 100 запитів з випадковими `t` (заголовок `X-F3D-Token`) → усі `403`; токен після першого `200` не діє; `t` і `export_token_hash` не трапляються в лозі Odoo, чатері карти, `td.command.result`; `Authorization` іншого колектора → `401` | порівняння хешів `hmac.compare_digest`; `Cache-Control: no-store` |
| ТБ-04 | Технічний користувач | AC-91; стенд: XML-RPC `authenticate(db, 'f3d_machine_bot', <будь-що>)` → `False`; `/web/login` → помилка | користувач неактивний, без пароля, без `base.group_system`/`group_td_manager` |
| ТБ-05 | Секрети | лог колектора (`docker logs collector`, `F3D_LOG_LEVEL=DEBUG` 15 хв, ТК-04/10), лог Odoo, telemetry `GET config` — пошук значень `F3D_OPCUA_PASSWORD`, `F3D_WOODSTORE_KEY`, `F3D_CUTOPT_KEY`, `F3D_COLLECTOR_TOKEN`, токенів `t` API-01 | 0 збігів; у `td.source.params` лише `*_ref` (Додаток C.1) |
| ТБ-06 | Ін'єкції й екранування | `job="WO00013'; DROP TABLE mrp_workorder; --"` (AC-28 — діяльність з текстом, без SQL); EV-01 `text="<img src=x onerror=alert(1)>"` → чатер/діяльність екрановані (`markupsafe.escape`); деталь `name="=HYPERLINK(\"http://x\")"` → у CSV без `=` (R-19 п. 5); поля команд з `;`/пробілом → `UserError` (R-21); огляд коду: `grep -rnE "execute\(f\"\|execute\(.*%[^s]\|execute\(.*\.format\(" odoo_addons/td_machine_connect` → 0 | відмови/екранування; жодних 5xx |
| ТБ-07 | Безпека OPC UA | стенд: джерело `UA-SAW-1` з `security_mode=SignAndEncrypt`, `security_policy=Basic256Sha256`, `cert_ref`/`key_ref` (сертифікат колектора), `server_cert_ref` = сертифікат емулятора → `online`; інший `F3D_OPCUA_SERVER_CERT` → `error` «server certificate …»; без `server_cert_ref` при `SignAndEncrypt` → `error` «server certificate not pinned»; виклик методу без користувача → `WriteError` (`BadUserAccessDenied`) | як описано; секрети не в `last_error` |
| ТБ-08 | REST woodStore/оптимізатор і allow-list | без `F3D_WOODSTORE_KEY` → джерело `error` «secret F3D_WOODSTORE_KEY not set»; хибний ключ → `401` → `error` «auth»; `base_url=https://…` з `verify_tls=false` → `error`; `F3D_ALLOW_HOSTS` без `iot-sim` → 0 пакетів до `iot-sim` (`tcpdump` 2 хв) | відмови; колектор `healthy` |
| ТБ-09 | Мультикомпанійність | друга компанія `C2` з РЦ і верстатом `M2`; користувач лише `C2` | не бачить верстатів, простоїв, OEE, завдань порталу, карт компанії 1 (record rules §4.3); `_cron_*` обробляють обидві компанії |
| ТБ-10 | Нейтралізація й деінсталяція | AC-92; на копії: `psql -f data/neutralize.sql` (разом з base/telemetry/viewer) → кнопки «Надіслати», «На оптимізацію», «Випустити» → `UserError`; крони вимкнені; токени експорту `NULL` | так |

Матриця прав (ТБ-01): R — читання, W — запис, C — створення, D — видалення; «—» — `AccessError`. Права на окремі дії
(причина простою, підтвердження, розбіжність стосу, стоп-крани) — AC-15, 16, 37, 50, 90.

| Модель | `user_plain` | `user_f3d` | `user_mrp` | `user_stock_manager` | `user_f3d_manager` | `user_f3d_admin` |
|---|---|---|---|---|---|---|
| `td.machine` | — | R | R | R | RWCD | RWCD |
| `td.machine.state.log` | — | R | R | R | R | RWCD |
| `td.downtime` | — | R | RW | R | R | RWCD |
| `td.machine.event`, `td.oee.shift` | — | R | R | R | R | RWCD |
| `td.machine.message` | — | R | R | R | RWCD | RWCD |
| `td.gantry.stack` | — | R | R | RW | RWCD | RWCD |
| `td.gantry.job` | — | R | RWC | R | RWCD | RWCD |
| `td.cut.part`, `td.cut.map`, `td.cut.map.line` | — | R | R | R | RWCD | RWCD |
| `td.downtime.reason.wizard` | — | — | RWC | — | — | — (лише з `mrp.group_mrp_user`) |
| `td.cut.plan.import.wizard`, `td.cut.part.import.wizard` | — | — | — | — | RWC | RWC |

### 13.4 Тести продуктивності (ТП)

Середовище: стенд §13.2 (Odoo 2 воркери, PostgreSQL 16); дані обсягу — SQL `generate_series` лише в тестовій копії.

| ТП | Що | Обсяг | Межа |
|---|---|---|---|
| ТП-01 | Вхід показань 35 верстатів щосекунди (AC-99) | колектор зупинено; генератор `tests/stand/load_machines.py` з токеном `COL-MAIN` (перегенерованим на копії) шле API-02 щосекунди: 35 верстатів × 3…5 показань (стан, режим, тривога, лічильник, завдання); кожен верстат перемикає `WORKING`↔`READY` раз на 10 с (зсув фаз), `micro_stop_s=0` на копії → ≈ 3,5 переходи/с; 30 хв | API-02 p95 ≤ 1,2 с, p99 ≤ 2 с; 0 відповідей `5xx`; у лозі Odoo 0 `deadlock detected`/`could not serialize`; CPU воркера Odoo ≤ 70 % ядра в середньому; `_cron_tick` ≤ 10 с; інтервалів ≈ 6 300 без перекриттів (SQL-перевірка `lag(date_end) = date_start`) |
| ТП-02 | Затримка ланцюга емулятор → колектор → Odoo | `scenario` + `shift`; щопів хвилини `machine_fault` start/stop по колу на CNC-1, CNC-3, EDGE-1, SAW-2, BORE-1; 30 хв (60 переходів) | `td.downtime.create_date − ts` події емулятора (`/sim/v1/events`) p95 ≤ 10 с; `collector_buffer_rows` ≤ 100 весь час; процес колектора CPU ≤ 15 % ядра, RSS ≤ 150 МБ; 1 сесія OPC UA на 15 джерел |
| ТП-03 | Звіти й крони на обсязі року | `generate_series`: 840 000 інтервалів (35 × 400 діб × 60), 140 000 простоїв, 9 800 записів OEE, 20 000 WO | `_cron_oee` ≤ 20 с; «OEE за період» за рік ≤ 5 с; pivot «Простої» за місяць ≤ 3 с; `_cron_rotate` видаляє 73 500 (35 × 35 діб × 60) ≤ 60 с; `_td_wo_intervals` для 100 WO ≤ 0,5 с (контракт energy); `EXPLAIN` — Index Scan за `(machine_id, date_start)` |
| ТП-04 | Портал і карти | 27 стосів, події woodStore кожні 2 с, `stacks` кожні 30 с, 20 активних завдань; карта на 5 000 деталей | `_cron_gantry` ≤ 10 с; обробка EV-02 `stacks` (27 елементів) ≤ 0,5 с; API-01 на 5 000 деталей ≤ 2 с, тіло ≤ 1 МБ |

### 13.5 Чек-лист DEPLOY_TEST (`docs/modules/td_machine_connect/DEPLOY_TEST.md`, здає W9) — «по одному верстату, перший тиждень лише читання»

1. Дамп бази `odoo` тестового сервера timur-o19demo (`pg_dump -Fc`), відновити як `odoo_f3d_mc`; встановити
   `td_factory3d`, `td_telemetry` (і за потреби `td_viewer3d`) за їхніми DEPLOY_TEST. Жива база не
   змінюється.
2. Знімки: S0 `SELECT count(*) FROM mrp_workcenter_productivity` (184); S1 `SELECT workcenter_id, count(*) FROM
   mrp_workcenter_productivity WHERE date_end IS NULL GROUP BY 1`; S2 `SELECT id, state, qty_produced FROM mrp_workorder
   ORDER BY id`; S3 `SELECT id, name, stage_id FROM maintenance_request ORDER BY id`; S4 `SELECT max(write_date) FROM
   mrp_workorder` і те саме для `mrp_workcenter_productivity`; S5 `SELECT location_id, product_id, lot_id, quantity
   FROM stock_quant q JOIN stock_location l ON l.id = q.location_id WHERE l.td_code LIKE 'PLT-%'`.
3. Установка (ТК-01 кроки 2–3): зафіксувати час хука й `migration_report`; S0 = 184, S2/S3/S5 незмінні, S1 —
   незмінні, крім позначки `td_source='demo'`. Одразу після установки — шаблон для ТК: `createdb -T odoo_f3d_mc
   odoo_f3d_mc_t0` (ТК самі вмикають потрібні прапори).
4. Стоп-крани після установки: `read_enabled=True` (параметр), `auto_start_enabled=False`, `write_enabled=False`,
   `cutting_mode=manual`; **по одному верстату**: `td.machine.read_enabled=False` для 34, `True` — лише SAW-1.
5. Юніт-тести на копії (`--test-tags /td_machine_connect`) → 0 падінь (`TestMigrationDemo` — на шаблоні
   `odoo_f3d_mc_t0`, бо п. 4 змінює прапори верстатів).
6. **Перший тиждень — лише читання** (емулятор `follow_odoo`, далі `scenario` + `shift`): день 1 — SAW-1 (журнал
   проти `/sim/v1/events` і пульта; поріг мікрозупинки); день 2 — + SAW-2, SAW-3, NEST-1, CNC-1…4 (OPC UA); день 3 —
   + модуль I/O `u80` (SLIDE-1, VSAW-1, SAND-1, PRESS-1, GLUE-1; перевірка проводки DI як у ТК-05 з `hold`); день 4 —
   + `u81…u83`; день 5 — усі 35, OEE за тиждень. Щодня: `SELECT count(*) FROM mrp_workorder WHERE write_uid = <id
   user_td_machine>` = 0; `td.command` модуля = 0; прості без причини старші доби — нагадування майстру; розбіжність
   OEE з оцінкою майстра — у звіт.
7. Тиждень 2 (ARCH §4.6): `auto_start_enabled=True`; `auto_start_mode='job_or_single'` лише SAW-1, решта `off`; щодня — подвійних таймерів 0
   (`SELECT workorder_id, count(*) FROM mrp_workcenter_productivity WHERE date_end IS NULL GROUP BY 1 HAVING count(*) >
   1` без завдань із кількома операторами), неповних партій — розбір з майстром; далі — по верстату за день.
8. Портал: `write_enabled` і запобіжники `equipment/GANTRY-1/cmd` — лише після зелених ТК-06…08 і відповіді на Q-02;
   спершу команди `stack` (виправлення), потім `feed`.
9. Карти розкрою: `cutting_mode=manual` до закриття Q-03; ТК-10 — лише на стенді.
10. Нейтралізація: `psql -d odoo_f3d_mc -f data/neutralize.sql` (разом із base/telemetry/viewer/iot_sim) → AC-92, ТБ-10.
11. Деінсталяція/повторна установка на копії: §5.4, §5.5 — після повторної установки 74 простої (якщо нових записів
    журналу часу не було), S0 не зменшився.
12. Відкат на живій базі = вимкнути три стоп-крани → деінсталяція (стандартний журнал часу лишається; простої й OEE
    модуля зникають — вивантажити до того). Фактичні кількості, час хука, результати ТК/ТБ/ТП — у `CHANGELOG.md`
    («Міграція демо») і `TEST_REPORT.md`.

## 14. Definition of Done

- Юніт-тести §13.1.1 зелені на чистій базі (`--without-demo=all`) і на шаблоні копії демо `odoo_f3d_mc_t0`
  (`TestMigrationDemo` — лише там); тести пакета §13.1.2 зелені (`pytest -m "not stand"`), без мережі й Docker.
- Кожен AC-01…AC-103 має зелений тест (UT/HT/CT) або відмітку ТК/MAN з датою й фактичними значеннями в
  `TEST_REPORT.md`; ТК-01…ТК-16, ТБ-01…ТБ-10, ТП-01…ТП-04 пройдені на стенді.
- `ruff check` і `ruff format --check` (довжина рядка 120) для модуля й пакета; `pylint-odoo` (якщо є в репозиторії)
  без помилок рівня error; жодного `TODO`/`TBD`/`print(`.
- Жодного `x_`-поля: `grep -rnE "(^|[^A-Za-z0-9_])x_[a-z]" odoo_addons/td_machine_connect
  services/collector_plugins/machine_connect` → 0 (модуль не читає рівень 0 — це робить telemetry).
- Рядки інтерфейсу українською в коді (D-14): `string=`, `help=`, назви меню/дій/кронів, тексти `UserError`/
  `ValidationError`/`AccessError`, чатера й діяльностей — українською; англійською лише технічні коди (`WORKING`,
  `E0421`, коди сигналів).
- Стандартні методи Odoo перевизначено лише ті, що названо в §2 (M-15 `create`, M-18 `_td_ingest`/`_mark_stale`,
  M-19 `_td_local_types`, M-20 `write`, M-27 `_action_done`, M-28 `create`):
  `grep -rnE "def (button_start|button_finish|button_pending|start_employee|stop_employee|_close|unblock|button_block)\("
  odoo_addons/td_machine_connect` → 0.
- `tools/commands.py` і `f3d_collector_mc/cmdtext.py` побайтово однакові й без імпортів Odoo (AC-80, X-93); `asyncua==1.1.6` закріплено; команди
  модуля — `td.command.payload` (telemetry 19.0.1.1.0, X-03), запасна текстова граматика R-21 перевірена (AC-102, AC-103).
- `data/neutralize.sql` виконується без помилки (AC-92); `uninstall_hook` і повторна установка перевірені (§13.5 п. 11).
- Перегляд безпеки §13.3 пройдено: запис на пристрої — лише через `td.command._td_mc_create_command` і п'ять запобіжників, плагін не
  пише змінних OPC UA, секрети — лише `*_ref`, токен API-01 одноразовий і хешований, SQL лише параметризований.
- Жива база `odoo` на timur-o19demo під час розробки й тестів не змінювалась (усі записи — на копіях).
- Документація: `README.md` модуля (установка, параметри §5.1, інструкції ARCH §4), `README.md` пакета (env §8.2,
  адреси, установка в образ колектора), `CHANGELOG.md` (`19.0.1.0.0`, «Міграція демо» з фактичними кількостями),
  `DEPLOY_TEST.md`, `TEST_REPORT.md`.
- Контракти CM-01…CM-09 (ARCH §2.1) реалізовано з точними іменами цього документа; зміна імен — лише через оновлення
  SPEC і повідомлення авторів `td_energy` (CM-03), `td_viewer3d` (CM-05), `td_telemetry` (CM-06…CM-08).

## 15. Відкриті питання

Ті самі Q-01…Q-17, що в ARCH §5.1 (нумерація спільна); тут — що робить код, поки відповіді немає.

| ID | Поки немає відповіді |
|---|---|
| Q-01 | **Закрито 14.10 (відповідь № 6, CONSISTENCY):** за OPC 40550-1 і `JobManagement`; nodeset і серійні номери — вхідні дані ПНР. адреси OPC 40550-1 і `JobManagement` — з iot_sim §8.3 (ПРИПУЩЕННЯ), лише в даних (Додаток C); верстат без `JobManagement` — сигнал `job` без адреси, `auto_start_mode='job_or_single'` (правило «одне в черзі») |
| Q-02 | **Закрито 14.10 (відповідь № 6, CONSISTENCY):** woodStore — контракт P-03, на проді — адаптер за описом HOMAG. адаптер `woodstore` за контрактом P-03 iot_sim; на проді `write_enabled=False`, команди порталу не надсилаються, звірка стосів працює лише на читання |
| Q-03 | **Закрито 14.10 (відповідь № 6, CONSISTENCY):** CSV P-04 з CAD; на проді `cutting_mode=manual` до звірки з intelliDivide; MPR — з woodWOP. прод — `cutting_mode=manual` (CSV R-19 п. 5 вручну, план JSON API-32 — M-25); стенд — `collector`; формат CSV ізольовано в `tools/cutcsv.py` |
| Q-04 | **Закрито 14.10 (відповідь № 27, CONSISTENCY):** імпорт CSV з CAD (imos/BAZIS тощо) у `td.cut.part` за форматом Додатка E; ручне введення — запасне; CAD-систему уточнює технолог на ПНР. деталі — ручне введення й імпорт CSV Додатка E; у макеті деталей немає, ТК беруть `tests/stand/data/parts_*.csv` (у модуль не потрапляють) |
| Q-05 | **Закрито 14.10 (відповідь № 28, CONSISTENCY):** причини простоїв макета + «Не вказано»; підтверджує майстер зміни; мікрозупинка 120 с, автопауза 10 хв. причини — Додаток B.2 + «Не вказано»; підтверджує `mrp.group_mrp_manager`; `micro_stop_s=120`, `pause_after_min=10` (§5.1) |
| Q-06 | **Закрито 14.10 (відповідь № 29, CONSISTENCY):** автостарт від працівника, відміченого сьогодні на РЦ, інакше — закріплений оператор `OP-<код>` (R-09); вхід на планшет — стандартний Shop Floor Odoo за бейджем працівника (`hr.employee.barcode`, та сама картка, що в СКУД), коду модуль не додає. порядок вибору працівника R-09 п. 4; 7 РЦ без оператора — без працівника (`button_start`) |
| Q-07 | **Закрито 14.10 (відповідь № 30, CONSISTENCY):** неповну партію вирішує майстер (A-10): прапор «неповна партія» + діяльність, МО автоматично не розбивається. неповна партія — прапор `td_partial_hold` + діяльність; МО не розбивається (A-10) |
| Q-08 | **Закрито 14.10 (відповідь № 31, CONSISTENCY):** `qty_produced` — при завершенні (`qty_sync_mode=finish`); наживо — лише `td_qty_counted`. `qty_sync_mode=finish`; наживо видно `td_qty_counted` |
| Q-09 | **закрито X-03** (CR-01: telemetry 19.0.1.1.0 — `td.command.payload`/`result_data`, API-06 `payload`, API-07 `data`, `SourcePlugin.call`): команди — `payload` R-21 (M-20, §7.2, плагіни `call()`); текстова граматика CMD-01…03 (≤ 64 символи) — запасна (`write()` плагінів; Odoo — лише без поля `payload`); GET API-01 з одноразовим токеном лишається (CSV карти до 1 МБ більший за 64 КБ `payload`, A-14) |
| Q-10 | **Закрито 14.10 (відповідь № 32, CONSISTENCY):** якість для OEE — `stock.scrap` з `workorder_id` + втрати категорії «Якість» (R-13). `Q` — `stock.scrap` з `workorder_id`; без браку `Q=1` |
| Q-11 | **Закрито 14.10 (відповідь № 33, CONSISTENCY):** DI «в роботі» — реле «цикл»; деталі — за лічильником (iot_sim R-16). DI «в роботі» = сигнал циклу; паузи між циклами поглинає `micro_stop_s`; лічильник = деталі |
| Q-12 | **Закрито 14.10 (відповідь № 6, CONSISTENCY):** `SignAndEncrypt`, `Basic256Sha256`, сертифікат колектора, окремі облікові записи на читання й на методи. стенд — `security_mode=None`; параметри безпеки (`cert_ref`, `key_ref`, `server_cert_ref`, `username`, `password_ref`) уже в схемі й Додатку C.1; ТБ-07 перевіряє `SignAndEncrypt` |
| Q-13 | **Закрито 14.10 (відповідь № 34, CONSISTENCY):** плановий час — календар РЦ + причини з `td_planned` («Перерва»). плановий час = календар РЦ мінус відсутності `leave` мінус прості з причиною `td_planned` («Перерва») |
| Q-14 | **Закрито 14.10 (відповідь № 7, CONSISTENCY):** плита списується при подачі порталом (R-17). списання — при подачі порталом (`picked` рядки руху, R-17), проведення — при закритті МО |
| Q-15 | **закрито**: ADAM — `wordorder=little` (**X-43**, D-20; A-28, ТК-05 перевіряє); заявку дає лише сигнал `alarm`, `state` — `create_request=False` (**X-38**); коди модуля (`workcenters/<C>/event`, `job_cmd`, `machine_state`, `equipment/GANTRY-1/cmd`, `equipment/CUTOPT/cmd`) каталог iot_sim доповнює з Додатка C.2 (**X-34**, X-76) — сигнал `workcenters/<C>/event` і далі створює хук. `default_capacity` у viewer замінено на `capacity_ids`/1 (**X-92**), `oee` перекриває провайдер цього модуля (R-25) |
| Q-16 | **закрито X-52**: ключі-розширення `opcua` (`ns_uri`, `events`, `io`, `call`, `job_select`; `params.ns_uri`, `app_uri`, `heartbeat_s`) і `rest_vendor` (`cmd`, `default`, `io`; `params.vendor`, `events_period_s`, `stacks_period_s`, `jobs_period_s`) внесено в telemetry Додаток A як довідкові (власник — цей модуль, CM-06); `validate()` плагіна перевіряє їх схемами `schemas/*.ext.json` |
| Q-17 | **закрито X-38**: емулятор формує `JobOrderID = "WO%05d"` (id `mrp.workorder`) у сценаріях і `follow_odoo`, завершені JobOrder лишаються в `JobOrderList` зі станом `Ended/Completed` — збігається з R-09 п. 1 і R-22 п. 3 без змін коду; ТК автостарту лишаються детермінованими (`Store` з Odoo, AC-101, + `Start` з пульта стенда — ТК-04, ТК-10) |

## Додаток A. Верстати (`data/mc_machines.csv`, 35 рядків)

Формат CSV: UTF-8, `,`, заголовок `code,protocol,source,io_unit,io_slot,auto_start_mode,operator_code`; порожні поля —
порожньо. Хук (§5.3 крок 3) шукає РЦ `mrp.workcenter.search_f3d(code)`, обладнання `maintenance.equipment.search_f3d(
code)`, працівника `hr.employee.search_f3d(operator_code)`; не знайдено — рядок пропускається (WARNING), лічильник
`machines` не збільшується. Назви — з демо (`dist/odoo_demo.json → workcenters`), у CSV не входять. Генератор
`tools/gen_mc_data.py` будує CSV з iot_sim Додатка A (рядки 197–334) і base Додатка B.

| № | `code` | Назва (демо) | `protocol` | `source` | `io_unit` | `io_slot` | `auto_start_mode` | `operator_code` |
|---|---|---|---|---|---|---|---|---|
| 1 | SAW-1 | Розкрій 1 | opcua | UA-SAW-1 | | | job_or_single | OP-SAW-1 |
| 2 | SAW-2 | Розкрій 2 | opcua | UA-SAW-2 | | | job_or_single | OP-SAW-2 |
| 3 | SAW-3 | Пакетний розкрій | opcua | UA-SAW-3 | | | job_or_single | |
| 4 | NEST-1 | Нестинг ЧПК | opcua | UA-NEST-1 | | | job_or_single | OP-NEST-1 |
| 5 | EDGE-1 | Крайкооблицювання A | opcua | UA-EDGE-1 | | | job_or_single | OP-EDGE-1 |
| 6 | EDGE-2 | Крайкооблицювання B | opcua | UA-EDGE-2 | | | job_or_single | OP-EDGE-2 |
| 7 | EDGE-3 | Крайкооблицювання C | opcua | UA-EDGE-3 | | | job_or_single | |
| 8 | CNC-1 | Присадка ЧПК A | opcua | UA-CNC-1 | | | job_or_single | OP-CNC-1 |
| 9 | CNC-2 | Присадка ЧПК B | opcua | UA-CNC-2 | | | job_or_single | OP-CNC-2 |
| 10 | CNC-3 | Присадка ЧПК D1 | opcua | UA-CNC-3 | | | job_or_single | OP-CNC-3 |
| 11 | CNC-4 | Присадка ЧПК D2 | opcua | UA-CNC-4 | | | job_or_single | OP-CNC-4 |
| 12 | BORE-1 | Прохідна присадка C | opcua | UA-BORE-1 | | | job_or_single | OP-BORE-1 |
| 13 | DOWEL-1 | Шкантування C | opcua | UA-DOWEL-1 | | | job_or_single | OP-DOWEL-1 |
| 14 | SORT-1 | Сортувальний робот | opcua | UA-SORT-1 | | | job_or_single | |
| 15 | ASMLINE-1 | Лінія збирання корпусів | opcua | UA-ASMLINE-1 | | | job_or_single | OP-ASMLINE-1 |
| 16 | SLIDE-1 | Форматно-розкрійний | io | MB-U80-IO1 | 80 | 0 | job_or_single | OP-SLIDE-1 |
| 17 | VSAW-1 | Вертикальна пила | io | MB-U80-IO1 | 80 | 1 | job_or_single | |
| 18 | SAND-1 | Шліфування фасадів | io | MB-U80-IO1 | 80 | 2 | job_or_single | OP-SAND-1 |
| 19 | PRESS-1 | Мембранно-вакуумний прес | io | MB-U80-IO1 | 80 | 3 | job_or_single | OP-PRESS-1 |
| 20 | GLUE-1 | Кабіна нанесення клею | io | MB-U80-IO1 | 80 | 4 | job_or_single | OP-GLUE-1 |
| 21 | SPRAY-1 | Фарбувальна камера | io | MB-U81-IO2 | 81 | 0 | job_or_single | OP-SPRAY-1 |
| 22 | AUTOSPRAY-1 | Автомат фарбування | io | MB-U81-IO2 | 81 | 1 | job_or_single | OP-AUTOSPRAY-1 |
| 23 | DRY-1 | Сушильна камера | io | MB-U81-IO2 | 81 | 2 | job_or_single | |
| 24 | UV-1 | УФ-лакування | io | MB-U81-IO2 | 81 | 3 | job_or_single | |
| 25 | HINGE-1 | Встановлення завіс | io | MB-U81-IO2 | 81 | 4 | job_or_single | OP-HINGE-1 |
| 26 | BOX-1 | Розкрій гофрокартону | io | MB-U82-IO3 | 82 | 0 | job_or_single | OP-BOX-1 |
| 27 | PACK-1 | Пакування 1 | io | MB-U82-IO3 | 82 | 1 | job_or_single | OP-PACK-1 |
| 28 | PACK-2 | Пакування 2 | io | MB-U82-IO3 | 82 | 2 | job_or_single | OP-PACK-2 |
| 29 | PACKLINE-1 | Термоусадка та обв'язка | io | MB-U82-IO3 | 82 | 3 | job_or_single | OP-PACKLINE-1 |
| 30 | ASM-1 | Збирання 1 | io | MB-U82-IO3 | 82 | 4 | job_or_single | OP-ASM-1 |
| 31 | ASM-2 | Збирання 2 | io | MB-U83-IO4 | 83 | 0 | job_or_single | OP-ASM-2 |
| 32 | ASM-3 | Збирання 3 | io | MB-U83-IO4 | 83 | 1 | job_or_single | OP-ASM-3 |
| 33 | ASM-4 | Збирання 4 | io | MB-U83-IO4 | 83 | 2 | job_or_single | OP-ASM-4 |
| 34 | ASM-5 | Збирання 5 | io | MB-U83-IO4 | 83 | 3 | job_or_single | |
| 35 | ASM-6 | Збирання 6 | io | MB-U83-IO4 | 83 | 4 | job_or_single | OP-ASM-6 |

Разом: 15 `opcua`, 20 `io` (4 модулі × 5 позицій), 28 з оператором (без: SAW-3, VSAW-1, EDGE-3, SORT-1, DRY-1, UV-1,
ASM-5 — base Додаток B). Розкладка I/O = iot_sim §8.4.2 (DI `2m` — в роботі, DI `2m+1` — аварія, HR `4m`…`4m+1` —
лічильник DI `2m`).

## Додаток B. Повідомлення верстатів і причини простоїв

### B.1 `data/mc_machine_messages.xml` (10 записів, `noupdate="1"`)

Каталог повідомлень емулятора (iot_sim §8.3.3); `category` — `WwEventCategoryEnumeration`. XML-id — `message_<код>`.
Інформаційні (`category` 2) підказок не дають (R-07 п. 1: категорія ≥ 3), записи потрібні для назв у журналі подій;
`I0002` — тригер завершення (R-12 п. 1) незалежно від `loss_id`.

| `sequence` | `message_id` | `name` | `category` | `loss_id` | `auto_apply` |
|---|---|---|---|---|---|
| 10 | I0001 | Завдання запущено | 2 | `loss_unknown` | False |
| 20 | I0002 | Завдання завершено | 2 | `loss_unknown` | False |
| 30 | I0003 | Зміна розпочата | 2 | `loss_unknown` | False |
| 40 | W0101 | Низький тиск повітря | 3 | `mrp.block_reason1` | False |
| 50 | W0102 | Потрібне ТО за мотогодинами | 3 | `mrp.block_reason1` | False |
| 60 | A0201 | Аварійна зупинка (кнопка) | 4 | `mrp.block_reason1` | False |
| 70 | A0202 | Втрата зв'язку з приводом осі | 4 | `mrp.block_reason1` | True |
| 80 | E0421 | Помилка шпинделя осі Z | 5 | `mrp.block_reason1` | True |
| 90 | E0430 | Втрата живлення | 5 | `loss_unknown` | False |
| 100 | E0440 | Відкрито огородження | 5 | `mrp.block_reason2` | False |

### B.2 Причини простоїв (`mrp.workcenter.productivity.loss`) після хука

| XML-id | Назва Odoo (en) | Назва uk (хук, R-27 п. 1) | Категорія (`loss_type`) | `td_planned` | `state_kind` при міграції демо | Де використовується |
|---|---|---|---|---|---|---|
| `mrp.block_reason0` | Material Availability | Очікування матеріалу | availability | False | `idle` | підказка R-07 п. 5, кнопка планшета |
| `mrp.block_reason1` | Equipment Failure | Поломка | availability | False | `fault` | аварія без події (R-05 п. 2, R-07 п. 4), B.1 |
| `mrp.block_reason2` | Setup and Adjustments | Налагодження | availability | False | `setup` | режим SETUP (R-07 п. 3) |
| `mrp.block_reason4` | Reduced Speed | Знижена швидкість | performance | False | — | не для простоїв (домен M-03 — лише availability/quality) |
| `mrp.block_reason5` | Process Defect | Дефект процесу | quality | False | `idle` | вибір оператора |
| `mrp.block_reason6` | Reduced Yield | Знижений вихід | quality | False | `idle` | вибір оператора |
| `mrp.block_reason7` | Fully Productive Time | Повністю продуктивний час | productive | False | — | стандартні таймери |
| `factory3d.loss_tool` | — | Заміна інструменту (демо) | availability (хук ставить категорію) | False | `setup` | кнопка kanban, вибір оператора |
| `factory3d.loss_break` | — | Перерва (демо) | availability (хук) | **True** | `idle` | плановий простій — поза PPT (R-13 п. 1) |
| `td_machine_connect.loss_unknown` | — | Не вказано | availability | False | — | умовчання простою (`to_classify`) |

## Додаток C. Джерела й сигнали

### C.1 Джерела (`data/mc_sources.xml`, 22 записи, `noupdate="1"`)

Спільне: `module='machine_connect'`, `read_enabled=True`, `write_enabled=False`, `collector_id=
td_telemetry.collector_main` (крім `MC-DERIVED`); `equipment_id` ставить хук (крок 3) за кодом. XML-id —
`source_<код>` у нижньому регістрі з `-` → `_` (`source_ua_saw_1`, `source_mb_u80_io1`, `source_rest_woodstore`,
`source_rest_cutopt`, `source_mc_derived`).

| Код | Назва | `type` | `params` (стенд) | Обладнання |
|---|---|---|---|---|
| `UA-<C>` × 15 (`<C>` — OPC UA-верстати Додатка A, № 1–15) | «OPC UA <C>» | `opcua` | `{"endpoint": "opc.tcp://iot-sim:4840/f3d/", "security_mode": "None", "security_policy": "None", "username": "collector", "password_ref": "F3D_OPCUA_PASSWORD", "timeout_s": 5, "publishing_interval_ms": 1000, "ns_uri": "http://todo.ltd/f3d/iot_sim/instances/", "app_uri": "urn:todo.ltd:f3d:collector", "heartbeat_s": 60}` | `<C>` |
| `MB-U80-IO1`, `MB-U81-IO2`, `MB-U82-IO3`, `MB-U83-IO4` | «Модуль I/O ADAM-6050 №1…4» | `modbus_tcp` | `{"host": "iot-sim", "port": 502, "unit": 80…83, "timeout_s": 3, "retries": 2, "max_block": 125, "gap_max": 8}` | — |
| `REST-WOODSTORE` | «Портал STORETEQ: woodStore» | `rest_vendor` | `{"base_url": "http://iot-sim:8082", "auth": "api_key", "header": "X-Api-Key", "key_ref": "F3D_WOODSTORE_KEY", "verify_tls": true, "timeout_s": 5, "vendor": "woodstore", "events_period_s": 2, "stacks_period_s": 30, "jobs_period_s": 10}` | GANTRY-1 |
| `REST-CUTOPT` | «Оптимізатор розкрою» | `rest_vendor` | `{"base_url": "http://iot-sim:8083", "auth": "api_key", "header": "X-Api-Key", "key_ref": "F3D_CUTOPT_KEY", "verify_tls": true, "timeout_s": 15, "vendor": "cutopt"}` | — |
| `MC-DERIVED` | «Верстати: обчислені стани» | `td_machine` | `{}` | — |

Прод (Q-12, після відповіді на Q-01): `endpoint` — IP верстата (`opc.tcp://<ip>:4840`), `security_mode=SignAndEncrypt`,
`security_policy=Basic256Sha256`, `cert_ref=F3D_OPCUA_CERT`, `key_ref=F3D_OPCUA_KEY`, `server_cert_ref` — окрема
змінна на верстат (`F3D_OPCUA_SERVER_CERT_<C>`, `-` → `_`); `MB-*` — IP модулів; REST — адреси woodStore/оптимізатора
і `verify_tls=true` для `https`. Змінює адміністратор у формі джерела (дані `noupdate`).

### C.2 Шаблони сигналів (`data/mc_signals.csv`, 18 шаблонів → 207 сигналів)

Формат CSV: UTF-8, `,`, лапки `"` для JSON; колонки `template,protocol,code,name,kind,unit,source,address,period_s,
store_period_s,decimals,states,alarm_states,create_request,alarm_title,viewer_visible,write_enabled`. Підстановки:
`{C}` — код, `{N}` — назва РЦ, `{SRC}` — `source` з Додатка A, `{DI_RUN}` = `2·io_slot`, `{DI_ALARM}` = `2·io_slot + 1`,
`{HR}` = `4·io_slot`. Спільне для всіх: `module='machine_connect'`, `origin='module'` (X-16: сигнали з власних даних модуля; `catalog` — лише
рядки каталогу iot_sim, `selection_add` модуль не робить; у двох прив'язаних наявних сигналах рівня 0 `origin` не
змінюється — R-27 п. 3), `equipment_id` — обладнання
`{C}` (GANTRY-1 для `g_*`), `workcenter_id` — РЦ `{C}`; XML-id `td_machine_connect.sig_<код>` (`/`, `-`, `.` →
`_`, нижній регістр). Розгортає `hooks._signal_rows` (§13.0.1 п. 4).

| `template` | Для | Код | Назва | `kind`, `unit` | Джерело | `address` | `period_s` / `store_period_s` | Інше |
|---|---|---|---|---|---|---|---|---|
| `ua_state` | 15 OPC UA | `workcenters/{C}/state` | «{N}: стан (OPC UA)» | state | `{SRC}` | `{"nodeid": "ns=2;s={C}.State.Machine.Overview.CurrentState", "mode": "subscribe", "sampling_ms": 500, "map": {"0": "OFFLINE", "1": "STANDBY", "2": "READY", "3": "WORKING", "4": "ERROR"}}` | 60 / 300 | `states` = 5 текстів + `bad`; `create_request=False`; `viewer_visible=False` |
| `ua_mode` | 15 | `workcenters/{C}/mode` | «{N}: режим» | state | `{SRC}` | `{"nodeid": "ns=2;s={C}.State.Machine.Overview.CurrentMode", "mode": "subscribe", "sampling_ms": 500, "map": {"0": "OTHER", "1": "AUTOMATIC", "2": "SEMIAUTOMATIC", "3": "MANUAL", "4": "SETUP", "5": "SLEEP"}}` | 60 / 300 | `states` = 6 + `bad`; `create_request=False`; `viewer_visible=False` |
| `ua_alarm` | 15 | `workcenters/{C}/alarm` | «{N}: тривога» | state | `{SRC}` | `{"nodeid": "ns=2;s={C}.State.Machine.Flags.Alarm", "mode": "subscribe", "map": {"0": "off", "1": "on"}}` | 60 / 300 | `states=["off","on","bad"]`, `alarm_states=["on"]`, `create_request=True`, `alarm_title="{code}: аварія верстата"`; `viewer_visible=False` |
| `ua_pieces` | 15 | `workcenters/{C}/pieces_out` | «{N}: деталей за зміну» | counter, шт | `{SRC}` | `{"nodeid": "ns=2;s={C}.State.Machine.Values.RelativePiecesOut", "mode": "subscribe"}` | 60 / 300 | `decimals=0` |
| `ua_job` | 15 | `workcenters/{C}/job` | «{N}: завдання на верстаті» | state | `{SRC}` | `{"nodeid": "ns=2;s={C}.JobManagement.JobOrderControl.JobOrderList", "mode": "subscribe", "job_select": "running_or_first"}` | 60 / 300 | `states=[]` (будь-який текст) |
| `ua_event` | 15 | `workcenters/{C}/event` | «{N}: події верстата» | event | `{SRC}` | `{"nodeid": "ns=2;s={C}.Events", "mode": "subscribe", "events": true}` | 86400 / 0 | показання пише Odoo (A-27); `viewer_visible=False` |
| `ua_job_cmd` | 15 | `workcenters/{C}/job_cmd` | «{N}: команди завдань» | state | `{SRC}` | `{"nodeid": "ns=2;s={C}.JobManagement.JobOrderControl", "mode": "subscribe", "io": "write", "call": "job"}` | 86400 / 0 | `write_enabled=False`; `viewer_visible=False` |
| `io_state` | 20 I/O | `workcenters/{C}/state` | «{N}: в роботі (DI)» | state | `{SRC}` | `{"fc": 2, "addr": {DI_RUN}, "type": "bool", "map": {"0": "stop", "1": "run"}}` | 1 / 300 | `states=["stop","run","bad"]`; `create_request=False`; `viewer_visible=False` |
| `io_alarm` | 20 | `workcenters/{C}/alarm` | «{N}: аварія (DI)» | state | `{SRC}` | `{"fc": 2, "addr": {DI_ALARM}, "type": "bool", "map": {"0": "off", "1": "on"}}` | 1 / 300 | як `ua_alarm` |
| `io_pieces` | 20 | `workcenters/{C}/pieces_out` | «{N}: лічильник деталей» | counter, шт | `{SRC}` | `{"fc": 3, "addr": {HR}, "count": 2, "type": "u32", "wordorder": "little"}` | 5 / 300 | `decimals=0` |
| `mc_state` | 35 | `workcenters/{C}/machine_state` | «{N}: стан верстата» | state | `MC-DERIVED` | `{}` | 86400 / 0 | `states=["working","setup","idle","fault","off","nodata"]`; пише модуль (CT-10); `viewer_visible=False` (X-27: `workcenters[код].machine_state` у payload ставить провайдер 75, R-25 п. 1; провайдер telemetry 95 його не перезаписує) |
| `g_state` | GANTRY-1 | `equipment/GANTRY-1/state` | «Портал: стан» | state | `REST-WOODSTORE` | `{"method": "GET", "path": "/api/v1/status", "json_path": "$.state"}` | 5 / 300 | `states=["idle","moving","picking","placing","blocked","error"]`, `alarm_states=["error"]`, `create_request=True`, `alarm_title="{code}: аварія порталу"` |
| `g_cycles` | GANTRY-1 | `equipment/GANTRY-1/cycles_today` | «Портал: циклів за добу» | counter, шт | `REST-WOODSTORE` | `{"method": "GET", "path": "/api/v1/status", "json_path": "$.cycles_today"}` | 5 / 300 | є в демо (рівень 0) — оновлюються лише джерело, адреса, періоди, `viewer_visible` |
| `g_vacuum` | GANTRY-1 | `equipment/GANTRY-1/vacuum_kpa` | «Портал: вакуум» | gauge, кПа | `REST-WOODSTORE` | `{"method": "GET", "path": "/api/v1/status", "json_path": "$.vacuum_kpa"}` | 5 / 60 | `decimals=1`; є в демо — як `g_cycles` |
| `g_job` | GANTRY-1 | `equipment/GANTRY-1/job` | «Портал: активне завдання» | state | `REST-WOODSTORE` | `{"method": "GET", "path": "/api/v1/jobs", "query": {"state": "active"}, "json_path": "$[0].id", "default": "-"}` | 5 / 300 | `states=[]` |
| `g_stacks` | GANTRY-1 | `equipment/GANTRY-1/stacks` | «Портал: непорожніх стосів» | gauge, шт | `MC-DERIVED` | `{}` | 86400 / 0 | пише модуль після EV-02 `stacks` (R-23 п. 3; сирі дані стосів — woodStore API-21), `decimals=0`; у каталозі iot_sim — рядок `protocol=none` (X-76: обчислює machine_connect з woodStore API-2x) |
| `g_cmd` | GANTRY-1 | `equipment/GANTRY-1/cmd` | «Портал: команди» | state | `REST-WOODSTORE` | `{"method": "POST", "path": "/api/v1/jobs", "json_path": "$.id", "cmd": "gantry", "io": "write"}` | 86400 / 0 | `write_enabled=False`; `viewer_visible=False` |
| `cut_cmd` | оптимізатор | `equipment/CUTOPT/cmd` (X-18) | «Оптимізатор розкрою: команди» | state | `REST-CUTOPT` | `{"method": "POST", "path": "/jobs", "json_path": "$.job_id", "cmd": "cutopt", "io": "write"}` | 86400 / 0 | без обладнання й РЦ (сегмент `CUTOPT` — оптимізатор розкрою, запису `maintenance.equipment` немає); `write_enabled=False`; `viewer_visible=False`; у каталозі iot_sim — рядок `protocol=none` (X-76: команда `rest_vendor` `cutopt`, власник machine_connect) |

**Період збереження сигналів стану.** Для `io_state`, `io_alarm`, `ua_state`, `ua_mode`, `ua_alarm`, `ua_job`, `g_state`, `g_job` — `store_period_s = 300` (раніше 0). Зміна стану пишеться в `td.reading` негайно (telemetry R-03/D-11: зміна `status` або `last_text`); прорідження торкається лише незмінних повторів — один запис на 300 с (`ts − last_stored_ts ≥ store_period_s`). `last_*` оновлюється з кожного показання.

Підсумок: 7 × 15 + 3 × 20 + 35 + 7 = **207**; на копії демо `g_cycles` і `g_vacuum` уже є → `signals_created=205`,
`signals_bound=2` (AC-83). Період 86 400 с — для сигналів без регулярних показань (події, команди, обчислені), щоб
telemetry не позначала їх `stale` (R-07 telemetry); стан зв'язку верстата визначає `ua_state`/`io_state`.

## Додаток D. План оптимізатора (API-32) для M-25 і EV-03 `plan`

`tools/cutcsv.parse_plan(data: dict) -> dict` приймає JSON iot_sim API-32 (той самий файл, що «оператор
intelliDivide» зберігає вручну). Обов'язкові: `total_sheets` (ціле ≥ 1), `waste_pct` (0…100), `sheets` (список 1…500;
кожен: `no` ціле ≥ 1, `product` рядок ≤ 32, `parts` список з `id` (= `part_code`), `x`, `y`, `w`, `h` (цілі ≥ 0),
`rot` ∈ {0, 90}). Необов'язкові: `cut_length_m`, `est_min` (якщо немає — з EV-03 `job.plan`), `sheets[].waste_pct`,
`sheets[].cuts`. Невідомі ключі ігноруються. Помилка → `ValueError("<шлях>: <проблема>")` (`sheets[2].parts[0].w:
очікується ціле ≥ 0`). Кількість розміщених деталей за `id` ≠ к-сті рядка карти → план приймається, чатер карти
«План не відповідає карті: P001 28 → 27».

```json
{"total_sheets": 7, "waste_pct": 11.4, "cut_length_m": 182.6, "est_min": 31,
 "sheets": [{"no": 1, "product": "DSP16-ANT", "waste_pct": 9.8,
             "parts": [{"id": "P001", "x": 0, "y": 0, "w": 720, "h": 560, "rot": 0}],
             "cuts": [{"dir": "x", "pos": 720, "from": 0, "to": 2070}]}]}
```

## Додаток E. CSV деталей виробу (M-26)

UTF-8 (BOM допускається й відкидається), роздільник `;`, перший рядок — заголовок (порядок колонок довільний, назви
точні): `part_code;name;length_mm;width_mm;qty;material_role;material;grain;edge_top;edge_bottom;edge_left;edge_right;
program;note`. Обов'язкові колонки й значення: `part_code`, `name`, `length_mm`, `width_mm`, `qty`. Умовчання:
`material_role=main`, `grain=0`, решта порожні. `qty` — крапка або кома; `material` — `default_code` плити (обов'язковий
для `product`); `edge_*` — `default_code` крайки. Перевірки — обмеження M-09 і R-19 п. 5; номер рядка N у помилці —
номер рядка файлу (заголовок — 1).

```
part_code;name;length_mm;width_mm;qty;material_role;material;grain;edge_top;edge_bottom;edge_left;edge_right;program;note
P001;Боковина;720;560;2;main;;1;EB-T;;EB-T;;;
P002;Дно;764;2300;1;main;;0;EB-T;;;;;
P003;Задня стінка;780;716;1;back;;0;;;;;;
```

Цей файл (AC-59) дає `UserError` «рядок 3: width_mm: 2300 поза межами 1…2200» і нічого не пише; з `width_mm=500` у
рядку 3 — 3 деталі.
