# factory3d_fire_safety — специфікація

Версія 0.2 · 14.10.2026 (дописано §2 M-04…M-19, §3–§15, додатки A–D) · технічне рішення: `docs/modules/factory3d_fire_safety/ARCHITECTURE.md` (далі «ARCH»;
FR-xx, A-xx, Q-xx — звідти). Контракти, на які спирається документ: `factory3d_base` CB-01, CB-03, CB-04,
CB-07, CB-08, CB-09, CB-10, CB-12; `factory3d_viewer` M-01, M-03, API-03, Додаток A.13; `factory3d_telemetry`
CT-01, CT-03, CT-05, CT-06, CT-07, CT-08, CT-09, CT-10 (ARCH telemetry §2.1; SPEC telemetry M-02, M-03, M-06, M-08, M-11,
R-05, R-07, R-17, R-23 — Q-06/Q-07);
`factory3d_iot_sim` SPEC §8.11 (P-09), §8.4.1 (unit 85), §9.1 R-25…R-27, §9.3 S-07/S-08, API-13, Додаток A
(сигнали 189, 603–646); `factory3d_access` SPEC M-16, CA-03, CA-09 (джерело проходів, рішення менеджера 14.10);
каркас `docs/ARCHITECTURE.md` §5, §6.4, §6.7, §6.8, D-07. Контракти, що задає модуль, — CF-01…CF-06 (ARCH §2.1). Усі рядки інтерфейсу — українською в коді (D-14), без `.po`; жодних `x_`-полів.

Загальні правила моделей: `_description` українською; `Datetime` — UTC (стандарт Odoo), у payload — рядки за
Києвом через `factory3d_viewer.tools.dates` (viewer R-02); `_log_access=True` всюди, крім `f3d.fire.event`;
`company_id` лише на `f3d.fire.panel` і `f3d.fire.drill` (решта — довідники однієї будівлі, як `f3d.zone` без
компанії для надвірних). Координати — CB-04 (метри, X уздовж 0…150, Y поперек 0…72, Z угору).

## 0. Дерево файлів модуля

### 0.1 Основний модуль `odoo_addons/factory3d_fire_safety`

```
odoo_addons/factory3d_fire_safety/
├── __manifest__.py
├── __init__.py                          імпорт models, wizard, hooks; post_init_hook, uninstall_hook
├── hooks.py                             §5.4 (кроки 1–9), uninstall (§5.5)
├── README.md                            інструкції ARCH §4 (копія) + коротко про заборону запису
├── CHANGELOG.md
├── models/
│   ├── __init__.py
│   ├── f3d_fire_norm.py                 M-08 (імпортується першим — його читають compute інших)
│   ├── f3d_fire_panel.py                M-01
│   ├── f3d_fire_loop.py                 M-02
│   ├── f3d_fire_zone.py                 M-03
│   ├── f3d_fire_device.py               M-04
│   ├── f3d_fire_event.py                M-05
│   ├── f3d_fire_system.py               M-06
│   ├── f3d_fire_smoke_zone.py           M-07
│   ├── f3d_fire_exit.py                 M-09
│   ├── f3d_fire_route.py                M-10
│   ├── f3d_fire_drill.py                M-11, M-11a, M-11b, M-11c, M-11e
│   ├── passage_source.py                M-12, M-12a
│   ├── f3d_zone.py                      M-13
│   ├── maintenance_request.py           M-14
│   ├── f3d_source.py                    M-15 (частина: джерело)
│   ├── f3d_signal.py                    M-15 (частина: сигнал, слухач змін)
│   ├── f3d_command.py                   M-15 (частина: команда)
│   ├── res_config_settings.py           M-16
│   ├── push_handler.py                  M-18 (telemetry у depends — безумовно)
│   └── iot_sim_bridge.py                FR-23: методи запуску fire_drill (умовно, якщо 'f3d.sim.panel' in env)
├── tools/
│   ├── __init__.py
│   ├── states.py                        таблиці BACnetLifeSafetyState → стани (R-10, R-11), тексти
│   ├── geometry.py                      сітки R-02/R-03/R-04, точка в прямокутнику, відстані; чисті функції
│   ├── sync.py                          R-10…R-14, R-19: читання сигналів → стани → події → шина
│   ├── payload.py                       R-20, R-21: build_fire(env, ctx), build_evacuation(env, ctx) — без залежності від viewer
│   ├── dates.py                         local(dt) → "YYYY-MM-DD HH:MM" Europe/Kyiv (як viewer R-02)
│   ├── sanitize.py                      clean_text(s, n=500): прибирає керівні символи, обрізає (R-14 п. 4)
│   └── gen_data.py                      генератор data/*.csv|xml з макета (§5.2); запускається з кореня репозиторію
├── wizard/
│   ├── __init__.py
│   ├── drill_rollcall_wizard.py         M-11d, M-11f (TransientModel) перекличка
│   ├── drill_rollcall_views.xml         V-18
│   ├── bacnet_device_wizard.py          M-19 (TransientModel) зміна BACnet device instance
│   └── bacnet_device_views.xml          V-27
├── report/
│   ├── report_evac_compliance.xml       ir.actions.report «Перевірка евакуації та розстановки» (V-20)
│   ├── report_evac_compliance_templates.xml
│   ├── report_drill.xml                 ir.actions.report «Протокол навчальної тривоги» (V-21)
│   ├── report_drill_templates.xml
│   ├── report_events.xml                ir.actions.report «Журнал подій за період» (V-22)
│   └── report_events_templates.xml
├── views/
│   ├── menus.xml                        V-00 меню й дії
│   ├── f3d_fire_panel_views.xml         V-01, V-02 (огляд)
│   ├── f3d_fire_zone_views.xml          V-03…V-05
│   ├── f3d_fire_device_views.xml        V-06, V-07
│   ├── f3d_fire_event_views.xml         V-08, V-09
│   ├── f3d_fire_system_views.xml        V-10, V-11
│   ├── f3d_fire_exit_views.xml          V-12
│   ├── f3d_fire_route_views.xml         V-13
│   ├── f3d_fire_smoke_zone_views.xml    V-14
│   ├── f3d_fire_norm_views.xml          V-15
│   ├── f3d_fire_drill_views.xml         V-16, V-17, V-19
│   ├── f3d_zone_views.xml               V-23 (inherit base V-01)
│   ├── f3d_source_views.xml             V-24 (inherit telemetry форми джерела)
│   ├── maintenance_request_views.xml    V-25
│   └── res_config_settings_views.xml    V-26
├── security/
│   ├── security.xml                     група group_f3d_fire_drill, record rules §4.3
│   └── ir.model.access.csv              §4.1
├── data/                                порядок — як у маніфесті §1
│   ├── ir_config_parameter.xml          noupdate=1
│   ├── ir_sequence.xml
│   ├── ir_cron.xml
│   ├── f3d_fire_norm.csv                27 норм: 20 з макета + 7 авторських (noupdate=1; Додаток D)
│   ├── f3d_fire_panel.xml               1 прилад + 4 шлейфи (M-01, M-02)
│   ├── f3d_fire_zone.csv                33 зони
│   ├── f3d_fire_system.xml              3 системи
│   ├── f3d_fire_smoke_zone.csv          8 димових зон
│   ├── f3d_fire_device.csv              343 пристрої
│   ├── f3d_fire_exit.csv                12 виходів
│   ├── f3d_fire_route.xml               32 маршрути (`path` через eval — Json-поле, A-31)
│   ├── f3d_fire_drill_template.xml      1 шаблон, 8 кроків
│   ├── f3d_source_data.xml              2 джерела (noupdate=1)
│   ├── f3d_signal_data.xml              52 сигнали (noupdate=1) + прив'язки signal_* моделей (noupdate=0), A-31
│   ├── mail_activity_type.xml           тип активності «Пожежна тривога»
│   └── neutralize.sql
├── static/description/icon.png
└── tests/
    ├── __init__.py
    ├── common.py                        FireCase(TransactionCase): фікстури, фейкові показання, помічник push_text()
    ├── test_norms.py                    AC-05…AC-11, AC-70 (R-01…R-04, R-08, R-23)
    ├── test_event.py                    AC-12…AC-16, AC-68 (M-05, R-14, M-18)
    ├── test_sync.py                     AC-17…AC-27, AC-67 (R-10…R-13, R-19)
    ├── test_security_readonly.py        AC-28…AC-31, AC-66, ТБ-01…ТБ-04 (FR-18)
    ├── test_requests.py                 AC-32 (зв'язок заявок)
    ├── test_evacuation.py               AC-33…AC-40 (R-05…R-09, звіт)
    ├── test_drill.py                    AC-41…AC-52 (R-15…R-18)
    ├── test_passage_source.py           AC-53, AC-54, AC-75 (CF-02, CF-06; потребує test_factory3d_fire_safety)
    ├── test_viewer_provider.py          AC-55…AC-57, AC-59 (R-20, R-21 — функції tools/payload без viewer)
    ├── test_hooks.py                    AC-01…AC-04, AC-60…AC-62, AC-69 (§5.4, §5.5, перерахунок)
    ├── test_rights_ui.py                AC-63…AC-65 (меню, права, налаштування)
    ├── test_data_sync.py                AC-71 (pytest поза Odoo: генератор = data/*)
    └── stand/                           pytest -m stand (ТК-01…ТК-10) — поза odoo.tests
        ├── conftest.py
        ├── test_tk_facp.py
        ├── test_tk_drill.py
        └── test_tk_readonly.py
```

### 0.2 Міст-модуль `odoo_addons/factory3d_fire_safety_viewer` (A-35, M-17)

```
odoo_addons/factory3d_fire_safety_viewer/
├── __manifest__.py                     name «Завод 3D: Пожежна безпека — 3D», version 19.0.1.0.0, depends
│                                       [factory3d_fire_safety, factory3d_viewer], data [], auto_install True, LGPL-3
├── __init__.py
├── models/__init__.py
├── models/viewer_provider.py            f3d.viewer.provider.fire (130), f3d.viewer.provider.evacuation (140)
└── tests/test_provider.py              AC-58 (PayloadBuilder + DeltaBuilder viewer із провайдерами модуля)
```

### 0.3 Тестовий модуль `odoo_addons/test_factory3d_fire_safety` (лише для тестів, не ставиться на прод)

```
odoo_addons/test_factory3d_fire_safety/
├── __manifest__.py                     depends [factory3d_fire_safety], LGPL-3, installable True, auto_install False
├── __init__.py
└── models/passage_source_test.py       AbstractModel f3d.fire.passage.source.zz_test БЕЗ _inherit: _f3d_priority = 5,
                                        _f3d_available() → bool(env.context.get('f3d_test_passage_source')),
                                        _f3d_passages(start, end) → env.context.get('f3d_test_passages', []) (без _f3d_on_site і _f3d_key)
```

## 1. Маніфест

```python
{
    "name": "Завод 3D: Пожежна безпека",
    "summary": "Пожежна сигналізація (лише читання), іскрогасіння, димовидалення, евакуація за нормами, навчальні тривоги",
    "version": "19.0.1.0.0",
    "author": "ToDo",
    "license": "LGPL-3",
    "category": "Manufacturing/Maintenance",
    "website": "https://todo.ltd",
    "depends": ["factory3d_telemetry", "hr_attendance"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_sequence.xml",
        "data/mail_activity_type.xml",
        "data/f3d_fire_norm.csv",
        "data/f3d_fire_panel.xml",
        "data/f3d_fire_zone.csv",
        "data/f3d_fire_system.xml",
        "data/f3d_fire_smoke_zone.csv",
        "data/f3d_fire_device.csv",
        "data/f3d_fire_exit.csv",
        "data/f3d_fire_route.xml",
        "data/f3d_fire_drill_template.xml",
        "data/f3d_source_data.xml",
        "data/f3d_signal_data.xml",
        "data/ir_cron.xml",
        "views/f3d_fire_norm_views.xml",
        "views/f3d_fire_panel_views.xml",
        "views/f3d_fire_zone_views.xml",
        "views/f3d_fire_device_views.xml",
        "views/f3d_fire_event_views.xml",
        "views/f3d_fire_system_views.xml",
        "views/f3d_fire_exit_views.xml",
        "views/f3d_fire_route_views.xml",
        "views/f3d_fire_smoke_zone_views.xml",
        "views/f3d_fire_drill_views.xml",
        "wizard/drill_rollcall_views.xml",
        "wizard/bacnet_device_views.xml",
        "views/f3d_zone_views.xml",
        "views/f3d_source_views.xml",
        "views/maintenance_request_views.xml",
        "views/res_config_settings_views.xml",
        "report/report_evac_compliance.xml",
        "report/report_evac_compliance_templates.xml",
        "report/report_drill.xml",
        "report/report_drill_templates.xml",
        "report/report_events.xml",
        "report/report_events_templates.xml",
        "views/menus.xml",
    ],
    "demo": [],
    "assets": {},
    "external_dependencies": {"python": []},
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
```

Порядок `data` істотний: норми → прилад/шлейфи → зони (посилаються на шлейфи й `f3d.zone` base за xml-id
`factory3d_base.zone_<slug>`) → системи → димові зони → пристрої (посилаються на зони, шлейфи, системи, димові
зони) → виходи → маршрути (посилаються на виходи й `f3d.zone`) → шаблон → джерела → сигнали (посилаються на
джерела) → крони (після сигналів, щоб перший прогін не впав) → представлення → звіти → меню (останнім:
посилається на всі дії). Python-залежності поза Odoo — немає (`bacpypes3`/`pymodbus` живуть у колекторі
telemetry). `factory3d_viewer`, `factory3d_iot_sim`, `factory3d_access`, `factory3d_bms`,
`factory3d_machine_connect` — **не** в `depends`; інтеграція умовна (§2 M-17, M-18, FR-23, R-17).

## 2. Моделі

### M-08 `f3d.fire.norm` — довідник норм (FR-07, FR-08, A-11)

```python
class F3dFireNorm(models.Model):
    _name = "f3d.fire.norm"
    _description = "Пожежна безпека: норма"
    _order = "group, sequence, key"
    _rec_name = "name"
```

| Поле | Тип | Параметри |
|---|---|---|
| `key` | Char(48) | `required`, `index`, `string="Ключ"`, regex `^[a-z0-9_]+$` (constrains, `"Ключ норми — латиниця, цифри, підкреслення"`) |
| `name` | Char(128) | `required`, `string="Назва"` |
| `group` | Selection | `[('detection','Виявлення'),('alerting','Оповіщення'),('evacuation','Евакуація'),('smoke','Димовидалення'),('other','Інше')]`, `required`, `default='other'` |
| `sequence` | Integer | `default=10` |
| `value` | Float | `digits=(12,3)`, `string="Значення"` |
| `value_set` | Boolean | `string="Значення задано"`, `default=False` — бо `Float` не відрізняє 0 від «немає» (макет має `null`) |
| `unit` | Char(64) | `string="Одиниця"` |
| `ref` | Text | `required`, `string="Норма (пункт, таблиця)"` |
| `note` | Text | `string="Примітка"` |
| `sources` | Text | `string="Джерела (URL, по одному в рядку)"` |
| `active` | Boolean | `default=True` |

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `@api.model get(self, key, default=None) -> float or None` | `rec = search([('key','=',key),('active','=',True)], limit=1)`; `rec.value if rec and rec.value_set else default`; результат кешується на час транзакції (`self.env.cr.cache` не використовуємо — `tools.ormcache` за `key` з інвалідацією у `write/create/unlink`) |
| `@api.model get_ref(self, key) -> str` | `ref` або `""` |
| `write/create` | якщо змінюється `value` або `value_set` → `self.env['f3d.fire.panel']._schedule_compliance()` (ставить прапор `compliance_dirty=True` на всіх панелях; перерахунок — кнопкою або кроном `cron_f3d_fire_compliance`) |

Ключі (20, data `f3d_fire_norm.csv`, значення з `plant/fire_rules.json` і `plant/evac_rules.json`): `smoke_spacing_6_12m` 8,8 м
(detection), `smoke_wall_6_12m` 4,4 м, `smoke_area_6_12m` (не задано), `heat_spacing` 6,4 м, `heat_wall` 3,2 м
(з `note` fire_rules «6,4 м між сповіщувачами і 3,2 м до стіни»; доданий автором, `ref` той самий —
ДБН В.2.5-56 табл. 7.1), `heat_area` (не задано), `mcp_spacing` 30 м, `mcp_height` (не задано; `note` 1,2–1,6 м),
`sounder_level` 65 дБА (alerting), `sounder_bg_production` 85 дБА (ДБН п. 9.3.10 «механічні цехи»; author),
`sounder_bg_storage` 80 дБА («виробничі приміщення»), `sounder_bg_office` 55 дБА, `spark_detection_required`
(не задано), `flame_detector_note` (не задано), `evac_distance_prod_B` 240 м (evacuation), `evac_distance_polymer`
50 м (`norm_alt` макета, ДБН В.2.2-27 п. 8.2.11), `evac_exits_min` 2, `exit_width_min` 1,0 м, `door_width_min`
0,8 м, `smoke_zone_max_area` 1 600 м² (smoke), `smoke_vent_area` 1,5 м² Aa на 400 м², `smoke_vent_aa` 1,02 м²
(LAMILUX F100, паспорт `smoke_vent`), `exit_dispersal_k` 1,5 (ДБН В.1.1-7:2016 п. 7.2.6, `L = 1,5·√П` з `note`
`evac_exits_min`), а також ключі `evac_rules.json` `smoke_exhaust_required` 1 (smoke), `lightning_class` 2,
`eyewash_required`, `pv_roof_fire` (other, не задано); `cover_tol_m` **не** норма — параметр (§3 ARCH). Разом у CSV:
27 рядків (20 з JSON + 7 авторських з позначкою `note="Додано автором модуля: …"`, A-27; повний перелік — Додаток D); далі в документі «20 норм» означає
ключі з макета, «27 записів» — файл.

### M-01 `f3d.fire.panel` — прилад (FR-01, FR-11, FR-12)

```python
class F3dFirePanel(models.Model):
    _name = "f3d.fire.panel"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Пожежна сигналізація: прилад"
    _order = "name"
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char(128) | `required`, `string="Назва"`, default «Приймально-контрольний прилад» |
| `code` | Char(32) | `required`, `index`, `string="Код сцени"`, default `FACP-1`; SQL unique |
| `company_id` | Many2one `res.company` | `required`, `default=lambda self: self.env.company` |
| `equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання"`, `ondelete='set null'`, domain `[('f3d_code','!=',False)]` |
| `manufacturer`, `model` | Char | `related='equipment_id.f3d_manufacturer'` / `.f3d_model`, readonly |
| `zone_id` | Many2one `f3d.zone` | `string="Зона розміщення"` (демо `Z-OFFICE`), `ondelete='set null'` |
| `x`, `y` | Float | `digits=(8,2)`, `string="X, м"`/`"Y, м"` (97,2 / 58,25) |
| `source_id` | Many2one `f3d.source` | `string="Джерело BACnet"`, domain `[('type','=','bacnet_ip')]`, `ondelete='set null'` |
| `io_source_id` | Many2one `f3d.source` | `string="Джерело вводів (ADAM)"`, domain `[('type','=','modbus_tcp')]` |
| `signal_state_id` | Many2one `f3d.signal` | `string="Сигнал: стан приладу (LSZ:0)"` |
| `signal_system_id` | Many2one `f3d.signal` | `"Сигнал: системний стан (MSV:1)"` |
| `signal_alarms_id`, `signal_faults_id`, `signal_disabled_id` | Many2one `f3d.signal` | лічильники AV:1/2/3 |
| `signal_sounders_id`, `signal_brigade_id` | Many2one `f3d.signal` | BI:10 / BI:11 |
| `state` | Selection | `[('unknown','Невідомо'),('normal','Норма'),('prealarm','Передтривога'),('alarm','ТРИВОГА'),('fault','Несправність'),('disabled','Вимкнення'),('test','Тест')]`, `default='unknown'`, `readonly`, `index`, `tracking=True` |
| `raw_state` | Char(32) | `string="Стан LSZ:0"`, readonly (текст BACnet) |
| `system_state` | Integer | `string="MSV:1"`, readonly (1…5) |
| `state_text` | Char | `compute="_compute_state_text"` (R-10 п. 6), наприклад «Норма, 1 попередження» |
| `state_ts` | Datetime | `string="Стан з"` |
| `comm` | Selection | `[('online','Онлайн'),('stale','Дані застарілі'),('lost','Зв'язок втрачено'),('off','Обробка вимкнена')]`, `default='lost'`, `readonly`, `tracking=True` |
| `last_seen` | Datetime | `string="Останнє показання"`, readonly |
| `comm_since` | Datetime | `string="Стан зв'язку з"` |
| `comm_request_id` | Many2one `maintenance.request` | `string="Заявка про зв'язок"`, `ondelete='set null'` |
| `alarm_activity_id` | Many2one `mail.activity` | `ondelete='set null'` (FR-11) |
| `alarms_count`, `faults_count`, `disabled_count` | Integer | readonly, з AV:1/2/3 |
| `sounders_active`, `brigade_transmitted` | Boolean | readonly, з BI:10/11 |
| `loop_ids` | One2many `f3d.fire.loop` `panel_id` | |
| `zone_ids` | One2many `f3d.fire.zone` `panel_id` | |
| `zone_count`, `device_count`, `event_count`, `warn_count`, `alarm_zone_count` | Integer | `compute="_compute_counts"` (не зберігаються): `search_count` зон; пристроїв `[('panel_id','=',id)]`; подій за 7 діб; зон з `warn=True`; зон зі `state='alarm'` |
| `alarm_zone_ids` | Many2many `f3d.fire.zone` | compute: зони у `alarm`/`prealarm` |
| `compliance_mcp_max_m` | Float | `digits=(8,1)`, `string="Найбільша відстань до ручного сповіщувача, м"`, readonly (R-03) |
| `compliance_mcp_point` | Char(32) | «(60.0, 72.0)» |
| `compliance_mcp_ok` | Boolean | readonly |
| `compliance_sounder_max_m` | Float | `digits=(8,1)` (R-04, довідково) |
| `compliance_zones_ok`, `compliance_zones_total` | Integer | readonly |
| `compliance_missing_zones` | Char | `string="Зони цеху без сигналізації"` (R-08: «Z-OFFICE, Z-SOC») |
| `compliance_ts` | Datetime | `string="Перераховано"` |
| `compliance_routes_ok`, `compliance_routes_total` | Integer | readonly (R-05, R-07: маршрути, що відповідають / усього активних) |
| `compliance_exits_ok` | Boolean | readonly (R-06, R-07) |
| `compliance_exit_pair_m` | Float | `digits=(8,1)`, `string="Найбільша відстань між виходами, м"` (R-06: 145,1) |
| `compliance_exit_l_m` | Float | `digits=(8,1)`, `string="Потрібна розосередженість L, м"` (R-06: 31,6) |
| `compliance_smoke_ok`, `compliance_smoke_total` | Integer | readonly (R-09) |
| `evac_max_distance_m` | Float | `digits=(8,1)`, `string="Найдовший шлях до виходу (макет), м"` — з `evac_routes.json:max_distance` (45,3), дані |
| `evac_worst_x`, `evac_worst_y` | Float | `digits=(8,2)` — `worst_point` (32,25; 33,75), дані |
| `system_ids` | One2many `f3d.fire.system` `panel_id` | |
| `systems_text` | Char | `compute="_compute_systems_text"`: «Іскрогасіння: норма · Димовидалення: норма · Спринклери: очікування» — підписи `state` систем через « · » (для kanban V-02) |
| `compliance_dirty` | Boolean | `default=True` |
| `first_sync` | Boolean | `default=True` — службове (R-12 п. 5) |
| `read_enabled` | Boolean | `compute="_compute_read_enabled"` — значення параметра `factory3d.fire_safety.read_enabled` (для `invisible` у формі) |
| `viewer_available` | Boolean | compute: `'f3d.viewer.provider' in self.env` |
| `sim_available` | Boolean | compute: `'f3d.sim.panel' in self.env` |

Обмеження: `_f3d_fire_panel_code_uniq = models.Constraint("UNIQUE(code)", "Код приладу має бути унікальним.")`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `_compute_state_text(self)` | R-10 п. 6 |
| `_set_state(self, new_state, raw, ts, source='signal')` | `ensure_one()`; якщо `new_state == self.state` → лише `raw_state`; інакше `write({state, raw_state, state_ts: ts})`; `f3d.fire.event._log(...)` за таблицею R-14; `alarm` → `_notify_alarm()`; вихід з `alarm` (`reset`/`normal`) → `_close_alarm_activity()`; шина CF-04 `_notify('f3d.fire.panel', [code], 'state')` |
| `_set_comm(self, comm, ts)` | R-12 |
| `_notify_alarm(self, zone=None, device=None)` | якщо `alarm_activity_id` відкрита — нічого; інакше для кожного користувача групи з параметра `alert_group_xmlid` (активних, не `share`) — `activity_schedule('factory3d_fire_safety.mail_act_fire_alarm', user_id=…, summary="Пожежна тривога: <зона>, сповіщувач <адреса>", note=<текст події>)`; перша активність → `alarm_activity_id`; шина `_notify('f3d.fire.panel', [code], 'state')` |
| `_close_alarm_activity(self)` | усі відкриті активності типу `mail_act_fire_alarm` на записі → `action_feedback("Прилад скинуто")`; `alarm_activity_id=False` |
| `action_recompute_compliance(self)` | для кожного запису: R-03 (`compliance_mcp_*`), R-04 (`compliance_sounder_max_m`), R-08 (`compliance_missing_zones`), для всіх `zone_ids` — `zone._compute_required()`/`_compute_coverage()` (R-01, R-02), `compliance_zones_ok/total`, `f3d.fire.exit/route/smoke.zone` — `_recompute()` (R-05…R-09); `compliance_ts=now`, `compliance_dirty=False`; повертає `display_notification` «Перераховано: зони N/33, ручні max 26,9 м, маршрути N/32, димові зони N/8» |
| `@api.model _schedule_compliance(self)` | `search([]).write({'compliance_dirty': True})` |
| `action_f3d_show(self)` | `self.equipment_id.action_f3d_show()` якщо є, інакше `UserError("Прилад не прив'язаний до обладнання зі сцени.")` |
| `action_view_zones/_devices/_events/_requests(self)` | `act_window` на відповідну модель з доменом за `panel_id` (заявки: `[('equipment_id','in', усі equipment зон+панелі), ('stage_id.done','=',False)]`) |
| `action_view_3d_alarm(self)` | як `action_f3d_show`, але `params.code` = код першої тривожної зони (`alarm_zone_ids[:1].equipment_id.f3d_code`) |
| `action_set_bacnet_device(self)` | `groups=group_f3d_admin`; відкриває майстер M-19 з `default_panel_id=self.id`, `default_old_instance` = `address['device']` сигналу `signal_state_id` |
| `_compute_systems_text(self)` | для `system_ids` у порядку `code`: `"%s: %s" % (SYS_LABEL[system_type], state_label)`, де `SYS_LABEL = {'spark':'Іскрогасіння','smoke':'Димовидалення','sprinkler':'Спринклери'}`, `state_label` — R-13 таблиця «короткий підпис» |
| `@api.model _get_param(self, key, default)` | обгортка `ir.config_parameter.sudo().get_param('factory3d.fire_safety.'+key, default)` з приведенням типів (`'True'/'False'`, int, float) |

### M-02 `f3d.fire.loop` — шлейф (FR-02)

`_name = "f3d.fire.loop"`, `_description = "Пожежна сигналізація: шлейф"`, `_order = "panel_id, number"`, `_rec_name = "name"`.

| Поле | Тип | Параметри |
|---|---|---|
| `panel_id` | Many2one `f3d.fire.panel` | `required`, `ondelete='cascade'`, `index` |
| `number` | Integer | `required`, `string="Номер"` (1…4) |
| `name` | Char | `compute="_compute_name"`, `store=True`: «Шлейф 2» |
| `from_x_m`, `to_x_m` | Float | `digits=(8,1)`, `string="X від, м"`/`"X до, м"` (0/42, 42/92, 92/122, 122/151 — `plant/fire.py:LOOPS`) |
| `detectors_count`, `mcp_count`, `sounders_count`, `flame_count` | Integer | `compute="_compute_device_counts"`, `store=True`: `search_count` пристроїв шлейфу за типами (`detectors` = smoke+multi+heat) |
| `modules_count` | Integer | `string="Модулі вводу"`, з data (шлейф 2 — 4: 3 полум'я + 1 іскрогасіння; `fire.loops[2].modules`) |
| `device_count` | Integer | compute: усі пристрої шлейфу |
| `signal_id` | Many2one `f3d.signal` | `string="Сигнал несправності (BI)"` |
| `state` | Selection | `[('unknown','Невідомо'),('ok','Норма'),('fault','Несправність')]`, `default='unknown'`, readonly |
| `fault_since` | Datetime | readonly |
| `request_id` | Many2one `maintenance.request` | `related='signal_id.maintenance_request_id'`, readonly |
| `device_ids` | One2many `f3d.fire.device` `loop_id` | |

Обмеження: `UNIQUE(panel_id, number)` «Номер шлейфу має бути унікальним у межах приладу»; `@api.constrains('number')`: 1 ≤ number ≤ 8 («Cerberus PRO FC726-ZA: до 8 кілець з розширенням; у макеті 4»), текст «Номер шлейфу: 1…8».
Методи: `_set_state(new, ts)` — `ok`/`fault`, подія `loop_fault`/`loop_ok` (R-14), `fault_since`; `loop_of(x)` `@api.model` → шлейф, для якого `from_x_m ≤ x < to_x_m` (як `fire.loop_of`), інакше порожньо.

### M-03 `f3d.fire.zone` — зона виявлення (FR-03, FR-07)

```python
class F3dFireZone(models.Model):
    _name = "f3d.fire.zone"
    _description = "Пожежна сигналізація: зона виявлення"
    _order = "lsz_instance"
    _rec_name = "display"
    _rec_names_search = ["code", "name", "zone_id.name"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(16) | `required`, `index`, `string="Код групи"` (`FA-CUT`); SQL unique; regex `^FA-[A-Z0-9-]{2,10}$` (constrains, «Код групи: FA-<зона>») |
| `name` | Char(128) | `required`, `string="Назва"` (назва зони цеху з макета: «Розкрій»; для `FA-BOILER` — «Котельня») |
| `display` | Char | `compute="_compute_display"`, `store=True`: `"%s · %s" % (code, name)` |
| `panel_id` | Many2one `f3d.fire.panel` | `required`, `ondelete='cascade'`, `index` |
| `loop_id` | Many2one `f3d.fire.loop` | `required`, `ondelete='restrict'`, `string="Шлейф"` |
| `zone_id` | Many2one `f3d.zone` | `required`, `ondelete='restrict'`, `string="Зона цеху"`, `index` |
| `equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання (група сповіщувачів)"`, `ondelete='set null'` |
| `lsz_instance` | Integer | `required`, `string="BACnet LSZ instance"` (1…33 за Додатком A); SQL `UNIQUE(panel_id, lsz_instance)` |
| `ordinal` | Integer | `related='lsz_instance'` (для формули LSP id, R-23) |
| `kind` | Selection | `[('smoke','Димові оптичні'),('multi','Оптико-теплові (пил деревини)'),('heat','Теплові')]`, `required` |
| `kind_name` | Char | compute: підпис `kind` (= `KIND_NAME` макета) |
| `spacing_m` | Float | `digits=(6,1)`, `string="Крок, м"` (8,8 або 6,4 — з data; `compute` не робиться, щоб зберегти значення макета) |
| `wall_m` | Float | `digits=(6,1)`, `string="До стіни, м"` (4,4 / 3,2) |
| `x0`, `y0`, `x1`, `y1` | Float | `digits=(8,2)`, `string="Контур виявлення, м"` — прямокутник (для 32 зон = габарит `f3d.zone` base; для `FA-BOILER` — `fire.py:BOILER_HOUSE` (67,6, 75,0, 79,6, 81,0)) |
| `area_m2` | Float | `compute="_compute_area"`, `store=True`, `digits=(12,0)`: `(x1-x0)·(y1-y0)` округлено (макет `area`) |
| `z_m` | Float | `digits=(6,2)`, `string="Висота встановлення, м"` (8,85 / 4,35) |
| `device_ids` | One2many `f3d.fire.device` `zone_id` | |
| `detector_count` | Integer | `compute="_compute_detector_count"`, `store=True`: пристрої з `type in ('smoke','multi','heat')` і `active` |
| `n_required` | Integer | `string="Потрібно за ДБН"`, readonly (R-01) |
| `n_ok` | Boolean | readonly |
| `cover_max_gap_m` | Float | `digits=(6,2)`, `string="Найбільший розрив покриття, м"` (R-02) |
| `cover_point` | Char(32) | |
| `cover_ok` | Boolean | |
| `compliance` | Selection | `[('na','Не перевірено'),('ok','Відповідає'),('warn','Зауваження'),('fail','Не відповідає')]`, `default='na'`, readonly, `index` |
| `compliance_note` | Text | readonly (текст R-01/R-02) |
| `signal_id` | Many2one `f3d.signal` | `string="Сигнал стану (LSZ)"` |
| `dust_signal_id` | Many2one `f3d.signal` | `string="Сигнал запиленості зони"` (лише `FA-FAC` з макета — AV:21607 за кодом `fire/groups/FA-FAC/dust`) |
| `state` | Selection | як у M-01 `state`, `default='unknown'`, readonly, `index`, `tracking` не потрібен (журнал — події) |
| `raw_state` | Char(32) | readonly |
| `state_ts` | Datetime | readonly |
| `stale` | Boolean | readonly, `default=False` (A-17) |
| `warn` | Boolean | `compute="_compute_warn"`, `store=True`: будь-який пристрій зони з `dust_state in ('warn','alarm')` або `reliability` не `no-fault-detected`, або `state in ('fault','disabled')` |
| `warning` | Text | compute store (R-13 п. 4): текст найгіршого пристрою |
| `dust_max_pct` | Float | compute store: max `dust_pct` пристроїв |
| `maintenance_request_id` | Many2one `maintenance.request` | `compute="_compute_request"` (не зберігається): перша відкрита заявка (`stage_id.done=False`) з `f3d_fire_zone_id=self` або `f3d_signal_id in (signal_id, dust_signal_id, пристрої.*_signal_id)` |
| `maintenance_request_name` | Char | compute: `maintenance_request_id.name` → для payload `maintenance_request` (у макеті — `MR/00036`; у базі заявки мають лише `name`; береться `name`, A-15) |
| `color` | Integer | compute: `normal`→10 (зелений), `warn`→3, `fault`/`disabled`→2, `alarm`/`prealarm`→1, `test`→4, `unknown`→0 |
| `event_count` | Integer | compute: події зони за 30 діб |
| `active` | Boolean | `default=True` |

Обмеження: `_check_rect` (`@api.constrains('x0','y0','x1','y1')`): `x0 < x1`, `y0 < y1`, у межах CB-12
території; текст «Контур виявлення %s: некоректний прямокутник». `_check_spacing`: `spacing_m > 0`,
`wall_m > 0`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `_compute_required(self)` | R-01 → `n_required`, `n_ok` |
| `_compute_coverage(self)` | R-02 → `cover_max_gap_m`, `cover_point`, `cover_ok`; після обох — `compliance`: `fail` якщо `not n_ok` або `cover_max_gap_m > r + 2·tol`; `warn` якщо `not cover_ok` (у межах 2·tol); інакше `ok` (стан пристроїв і запиленість на відповідність не впливають — це `warn`); `compliance_note` (R-02) |
| `action_recompute(self)` | обидва + `display_notification` |
| `_set_state(self, new_state, raw, ts, device=None)` | як M-01 `_set_state` для зони: подія R-14 (`zone_id`, `device_id`), при `alarm` → `panel_id._notify_alarm(zone, device)`; при `test`/`alarm` → `f3d.fire.drill._match_test_alarm(self, device, ts, real=(new_state=='alarm'))` (R-18); шина `_notify('f3d.fire.zone', [code], 'state')`; `zone_id` отримує той самий `_notify('f3d.zone', [zone_id.f3d_code], 'state')` (viewer підсвічує зону цеху) |
| `action_f3d_show(self)` | `equipment_id.action_f3d_show()` (3D-об'єкт `FA-<зона>`); без обладнання — `zone_id.action_f3d_show()` |
| `action_view_devices/_events/_requests(self)` | `act_window` з доменом |
| `action_create_device_signals(self)` | для всіх пристроїв зони → `device.action_create_signals()` (A-02) |
| `point_inside(self, x, y) -> bool` | `x0 ≤ x ≤ x1 and y0 ≤ y ≤ y1` |

### M-04 `f3d.fire.device` — пристрій (FR-04)

```python
class F3dFireDevice(models.Model):
    _name = "f3d.fire.device"
    _description = "Пожежна сигналізація: пристрій"
    _order = "loop_id, zone_id, seq, address"
    _rec_name = "name"
    _rec_names_search = ["address", "name"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `address` | Char(16) | `required`, `index`, `string="Адреса"`; SQL unique; regex `^[0-4]\.[A-Z0-9-]{2,8}\.[0-9]{2}$` (constrains: «Адреса пристрою: <шлейф>.<ЗОНА>.<nn>, напр. 2.FAC.07»); шлейф `0` — пристрої не на C-NET (іскрогасіння, люки) |
| `name` | Char | `compute="_compute_name"`, `store=True`: `"%s %s" % (type_label, address)` → «Сповіщувач 2.FAC.07», «Ручний сповіщувач 1.MCP.03», «Оповіщувач 2.SND.05», «Сповіщувач полум'я 2.FLM.01», «Датчик іскор 0.SPK.01», «Форсунка гасіння 0.NOZ.02», «Люк димовидалення 0.SV.17» |
| `type` | Selection | `[('smoke','Димовий оптичний'),('multi','Оптико-тепловий'),('heat','Тепловий'),('mcp','Ручний'),('sounder','Оповіщувач'),('flame','Полум'я'),('spark_detector','Датчик іскор'),('spark_nozzle','Форсунка гасіння'),('smoke_vent','Люк димовидалення')]`, `required`, `index` |
| `is_detector` | Boolean | compute store: `type in ('smoke','multi','heat')` |
| `panel_id` | Many2one `f3d.fire.panel` | `ondelete='cascade'`, `index` (порожній для `spark_*`, `smoke_vent`) |
| `loop_id` | Many2one `f3d.fire.loop` | `ondelete='restrict'` (порожній для шлейфу 0) |
| `zone_id` | Many2one `f3d.fire.zone` | `ondelete='restrict'`, `index`, `string="Зона виявлення"` — лише для `is_detector` (constrains: детектор без зони / не-детектор із зоною → «Сповіщувач зони має належати зоні виявлення; інші пристрої — ні») |
| `plant_zone_id` | Many2one `f3d.zone` | `compute="_compute_plant_zone"`, `store=True`, `string="Зона цеху"`: для детекторів — `zone_id.zone_id`; для решти — `f3d.zone.zone_at(x, y)` (CB-03) або порожньо (стіни `x≈0`, `x≈150`, `y≈72` дають порожньо — очікувано для MCP/SND на стінах) |
| `system_id` | Many2one `f3d.fire.system` | `ondelete='restrict'` (для `spark_*`, `smoke_vent`) |
| `smoke_zone_id` | Many2one `f3d.fire.smoke.zone` | `ondelete='set null'` (для `smoke_vent`) |
| `equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання групи"`, `ondelete='set null'` (A-15: `FA-<зона>`, `FA-MCP`, `FA-SND`, `FA-FLAME`, `SPARK-1`, `SMOKE-VENTS`) |
| `model` | Char | `related='equipment_id.f3d_model'` |
| `lsp_instance` | Integer | `string="BACnet LSP instance"`, `index` (R-23; 0 для шлейфу 0) |
| `seq` | Integer | `string="№ у групі"` (`nn`) |
| `x`, `y`, `z` | Float | `digits=(8,2)`, `required` для `x`,`y`; `z` default 0 |
| `side` | Selection | `[('W','Захід'),('E','Схід'),('S','Південь'),('N','Північ'),('P','Стійка'),('X','Вісь X'),('Y','Вісь Y')]` — бік стіни для MCP/SND (`call_points()`/`sounders()`), вісь форсунки |
| `heading_deg` | Float | `digits=(6,1)` (полум'я: −90) |
| `state` | Selection | `[('unknown','Невідомо'),('normal','Норма'),('prealarm','Передтривога'),('alarm','Тривога'),('fault','Несправність'),('disabled','Вимкнено'),('test','Тест'),('active','Активний')]`, `default='unknown'`, readonly, `index` |
| `raw_state` | Char(32) | readonly |
| `reliability` | Char(32) | readonly (BACnet `reliability`; `no-fault-detected`, `unreliable-other`, …) |
| `state_ts` | Datetime | readonly |
| `dust_pct` | Float | `digits=(5,1)`, `string="Запиленість, %"`, readonly |
| `dust_ts` | Datetime | readonly |
| `dust_state` | Selection | `[('na','—'),('ok','Норма'),('warn','Попередження'),('alarm','Очистити')]`, `compute="_compute_dust_state"`, `store=True` (R-13 п. 3) |
| `monitor` | Boolean | `string="Окремі сигнали"`, `default=False`, `groups="factory3d_base.group_f3d_manager"` (A-02) |
| `state_signal_id` | Many2one `f3d.signal` | `string="Сигнал стану (LSP)"`, `ondelete='set null'` |
| `dust_signal_id` | Many2one `f3d.signal` | `string="Сигнал запиленості (AV)"`, `ondelete='set null'` |
| `maintenance_request_id` | Many2one `maintenance.request` | compute (не зберігається): відкрита заявка з `f3d_fire_device_id=self` або `f3d_signal_id in (state_signal_id, dust_signal_id)` |
| `event_count` | Integer | compute |
| `note` | Text | |
| `active` | Boolean | `default=True` |

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `_compute_name`, `_compute_plant_zone`, `_compute_dust_state` | за описом; `dust_state`: `na` якщо `dust_ts` порожній; `alarm` якщо `dust_pct ≥ dust_alarm_pct` (90); `warn` якщо `≥ dust_warn_pct` (80); інакше `ok` |
| `action_create_signals(self)` | `groups=manager`; для `is_detector`/`mcp`/`sounder`/`flame` з `panel_id.source_id`: якщо `state_signal_id` порожній → `f3d.signal.create({code: "fire/devices/%s/state" % address, name: "%s: стан" % name, kind: 'state', unit: '', equipment_id: equipment_id, source_id: panel_id.source_id, address: {"device": <device панелі, R-23>, "object":"LSP","instance": lsp_instance, "mode":"poll"}, period_s: 10, store_period_s: 3600, viewer_visible: False, module: 'fire_safety', origin: 'catalog', write_enabled: False, alarm_states: FAULT_STATES (R-11: `["fault","tamper","abnormal","emergency-power","supervisory"]`), alarm_title: "Несправність пристрою %s (%s): стан {text}" % (address, zone)})`; для `is_detector` додатково `dust_signal_id` → `{code: "fire/devices/%s/dust" % address, kind: 'gauge', unit: '%', address: {"device": <device панелі>, "object":"AV","instance": lsp_instance, "mode":"poll"}, period_s: 600, store_period_s: 3600, decimals: 1, hysteresis: 1.8, warn_high_on/alarm_high_on: True, warn_high: dust_warn_pct, alarm_high: dust_alarm_pct, alarm_title: "Очистити сповіщувач %s (%s): запиленість {value} % при нормі до {threshold}"}`; `monitor=True`; повторний виклик — нічого (ключ `code` унікальний у telemetry). Повертає `display_notification` з кількістю створених |
| `action_remove_signals(self)` | `groups=manager`; `monitor=False`; сигнали **не** видаляються (журнал показань), а `active=False` (поле telemetry M-03); `state_signal_id`/`dust_signal_id` лишаються (повторне `action_create_signals` знаходить сигнал за `code` з `active_test=False` і повертає `active=True`), крім `2.FAC.07` — його сигнал запиленості належить зоні й не архівується |
| `action_f3d_show(self)` | `equipment_id.action_f3d_show()` (груповий 3D-об'єкт, Q-09); без обладнання → `plant_zone_id.action_f3d_show()` |
| `_set_state(self, new_state, raw, ts, reliability=None)` | запис полів; подія R-14 рівня пристрою лише для `alarm`/`prealarm`/`fault`/`disabled`/`test` (перехід) і повернення; зона — через власний сигнал (не з пристрою) |
| `_set_dust(self, pct, ts, log=True)` | `dust_pct`, `dust_ts`; перехід `dust_state` → події `dust_warn`/`dust_alarm`/`dust_ok` (R-13 п. 3; `log=False` — без подій, лише хук §5.4 п. 3); зона `warn` перераховується через `@api.depends('device_ids.dust_state')` |
| `@api.model lsp_id(loop, ordinal, nn)` | R-23 |

Обмеження M-04:

```python
    _f3d_fire_device_address_uniq = models.Constraint("UNIQUE(address)", "Адреса пристрою має бути унікальною.")
    _f3d_fire_device_lsp_uniq = models.UniqueIndex("(lsp_instance) WHERE lsp_instance > 0",
                                                   "BACnet LSP instance має бути унікальним.")
```

`@api.constrains`:
- `address` — regex з таблиці; перша цифра адреси = `loop_id.number` для типів C-NET (`smoke`, `multi`, `heat`,
  `mcp`, `sounder`, `flame`) і `0` для `spark_detector`, `spark_nozzle`, `smoke_vent` → інакше
  `ValidationError("Адреса %s не відповідає шлейфу %s.")`;
- `type`, `zone_id` — текст у таблиці полів (детектор ↔ зона);
- `type`, `loop_id`, `panel_id`, `system_id` — типи C-NET вимагають `loop_id` і `panel_id`
  (`"Пристрій %s на шлейфі приладу: вкажіть шлейф і прилад."`); `spark_*`, `smoke_vent` вимагають `system_id`
  (`"Пристрій %s належить системі: вкажіть систему."`); `smoke_vent` вимагає `smoke_zone_id`;
- `x`, `y`, `z` — `site_x0_m ≤ x ≤ site_x1_m`, `site_y0_m ≤ y ≤ site_y1_m` (CB-12), `0 ≤ z ≤ 12`
  → `"Координати пристрою %s поза територією (CB-04/CB-12)."`.

Висоти `z` у data (A-32): сповіщувачі зон 8,85 (`fire.Z_DET`), котельня 4,35 (`Z_BOILER`), ручні 1,35, оповіщувачі
2,9 (`site.py:build_fire`), полум'я 5,0 (`FLAME`), датчики й форсунки іскор 7,98 (`DUCT_Z + 0,38` = `DUCT_TOP`),
люки 9,0 (`infra.ROOF_Z`). `note` у data лише в `2.FAC.07` — «біля шліфування» (текст попередження макета).

### M-05 `f3d.fire.event` — журнал подій (FR-05, FR-11, A-04, A-12, A-24, A-33)

```python
class F3dFireEvent(models.Model):
    _name = "f3d.fire.event"
    _description = "Пожежна безпека: подія журналу"
    _order = "ts desc, id desc"
    _rec_name = "text"
    _log_access = False
```

| Поле | Тип | Параметри |
|---|---|---|
| `ts` | Datetime | `required`, `index`, `default=fields.Datetime.now`, `string="Час"` (UTC; для подій із сигналів — `last_ts` сигналу) |
| `etype` | Selection `ETYPES` (40 значень, R-14) | `required`, `index`, `string="Тип"` |
| `kind` | Selection | `[('alarm','Тривога'),('prealarm','Передтривога'),('fault','Несправність'),('dust','Запиленість'),('disabled','Вимкнення'),('test','Тест'),('reset','Скидання'),('comm',"Зв'язок"),('spark','Іскрогасіння'),('smoke','Димовидалення'),('sprinkler','Спринклери'),('loop','Шлейф'),('drill','Навчання'),('manual','Коментар'),('info','Інформація')]`, `compute="_compute_kind"`, `store=True`, `index` — з таблиці R-14 (колонка «kind») |
| `level` | Selection | `[('info','Інформація'),('warn','Попередження'),('alarm','Тривога')]`, `required`, `index` |
| `object_code` | Char(32) | `required`, `index`, `string="Об'єкт"`: `FACP-1`, `FA-FAC`, `2.FAC.07`, `SPARK-1`, `SMOKE-CTRL`, `SPRINKLERS`, `MB-U85-IO6`, `DRILL/2026/0001` |
| `scene_code` | Char(32) | `string="Код у 3D"` — об'єкт для «Показати в 3D» і `fire.events[*].code`: зона → `code` зони; пристрій-детектор → `code` його зони; `mcp`/`sounder`/`flame` → `FA-MCP`/`FA-SND`/`FA-FLAME`; `spark_*` → `SPARK-1`; `smoke_vent` → `SMOKE-VENTS`; шлейф/прилад → `FACP-1`; система → її `code`; навчання → `code` зони навчання |
| `panel_id` | Many2one `f3d.fire.panel` | `ondelete='set null'`, `index` |
| `loop_id` | Many2one `f3d.fire.loop` | `ondelete='set null'` |
| `zone_id` | Many2one `f3d.fire.zone` | `ondelete='set null'`, `index` |
| `device_id` | Many2one `f3d.fire.device` | `ondelete='set null'`, `index` |
| `system_id` | Many2one `f3d.fire.system` | `ondelete='set null'` |
| `drill_id` | Many2one `f3d.fire.drill` | `ondelete='set null'`, `index` |
| `signal_id` | Many2one `f3d.signal` | `ondelete='set null'` |
| `request_id` | Many2one `maintenance.request` | `ondelete='set null'`, `string="Заявка ТО"` |
| `raw_from`, `raw_to` | Char(32) | `string="Було"`, `"Стало"` — тексти BACnet/станів |
| `text` | Char(500) | `required`, `string="Подія"` |
| `message_text` | Char(500) | `string="Текст приладу"` (BACnet `message-text`, M-18) |
| `source` | Selection | `[('signal','Сигнал'),('bacnet','Повідомлення BACnet'),('cron','Звірка'),('drill','Навчання'),('manual','Вручну'),('demo','Демо'),('system','Модуль')]`, `required`, `default='signal'` |
| `dedup_key` | Char(96) | `required`, `index`, `copy=False` (R-14 п. 2) |
| `in_drill` | Boolean | `string="Під час навчання"` — на момент `ts` було навчання `running` |
| `ack_required` | Boolean | `compute` (не зберігається): `level == 'alarm' and _get_param('event_ack_required', True)` |
| `ack` | Boolean | `default=False`, `string="Підтверджено"`, `index` |
| `ack_user_id` | Many2one `res.users` | `string="Підтвердив"`, `readonly` |
| `ack_ts` | Datetime | `string="Підтверджено о"`, `readonly` |
| `note` | Text | `string="Коментар"` |
| `user_id` | Many2one `res.users` | `string="Автор"`, `default=lambda self: self.env.user` (для `manual`; для автоматичних — `base.user_root`) |

```python
    _f3d_fire_event_dedup_uniq = models.Constraint("UNIQUE(dedup_key)", "Подія з таким ключем уже записана.")
    _f3d_fire_event_ts_kind_idx = models.Index("(ts, kind)")
    _f3d_fire_event_object_ts_idx = models.Index("(object_code, ts)")
```

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `@api.model _log(self, etype, object_code, ts, text, level=None, source='signal', key=None, **links) -> record` | 1) `level = level or ETYPE_TABLE[etype].level`; 2) `key = key or "%s:%s:%d" % (etype, object_code, int(ts.replace(tzinfo=UTC).timestamp()) // 2)` (кошик 2 с, A-04); 3) `existing = search([('dedup_key','=',key)], limit=1)` → якщо є: дописати порожні `message_text`/`request_id` з `links` і повернути його; 4) `text = sanitize(text)[:500]` (R-14 п. 4); 5) `in_drill = bool(env['f3d.fire.drill'].search_count([('state','=','running')]))`; 6) `scene_code` за правилом поля з `links`; 7) `with self.env.cr.savepoint(): create({...})` під `sudo()`; `IntegrityError` (паралельний воркер записав той самий ключ) → повернути `search([('dedup_key','=',key)])`; 8) повернути запис. Викликач не перевіряє права — метод службовий (з `sudo`) |
| `create(self, vals_list)` | якщо `not self.env.su`: кожен запис має `etype == 'manual'`, `level='info'`, `source='manual'`, `ts` ≤ `now + 60 с`, і користувач у `group_f3d_fire_drill` — інакше `AccessError("Користувач може додати лише коментар до журналу (тип «Коментар»).")`; для `manual` без `dedup_key` → `"manual:%s:%s" % (uuid4().hex, uid)`; `object_code` для `manual` — default `FACP-1` |
| `write(self, vals)` | якщо `not self.env.su` і `set(vals) - {'ack','ack_user_id','ack_ts','note'}` → `AccessError("Журнал подій змінювати не можна; дозволено лише підтвердження й коментар.")`; `ack=False` після `True` заборонено → `UserError("Підтвердження не знімається.")` |
| `unlink(self)` | завжди `UserError("Журнал подій не видаляється (A-12).")`, крім `self.env.context.get('f3d_fire_allow_unlink') and self.env.su` (лише тести й деінсталяція) |
| `action_ack(self)` | для записів `not ack`: `write({'ack': True, 'ack_user_id': uid, 'ack_ts': now})`; повертає `True` |
| `action_open_object(self)` | `ensure_one()`; перший непорожній із `device_id`, `zone_id`, `system_id`, `drill_id`, `loop_id`, `panel_id` → `act_window` форми цього запису |
| `action_f3d_show(self)` | `zone_id`/`device_id`/`system_id`/`panel_id` → їхній `action_f3d_show()`; інакше `UserError("Подія не прив'язана до об'єкта сцени.")` |
| `_payload_item(self) -> dict` | `{"time": local(ts), "level": {'info':'info','warn':'warn','alarm':'bad'}[level], "code": scene_code or object_code, "text": text}` (R-20) |

### M-06 `f3d.fire.system` — іскрогасіння, димовидалення, спринклери (FR-06)

`_name = "f3d.fire.system"`, `_inherit = ["mail.thread"]`, `_description = "Пожежна безпека: система"`,
`_order = "sequence, code"`, `_rec_name = "name"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(32) | `required`, `index`, SQL unique, `string="Код сцени"`: `SPARK-1`, `SMOKE-CTRL`, `SPRINKLERS` |
| `name` | Char(128) | `required`: «Іскрогасіння аспірації (GreCon BS 7)», «Димовидалення (D+H CPS-M1, люки LAMILUX F100)», «Спринклерна система» |
| `sequence` | Integer | `default=10` (10/20/30) |
| `system_type` | Selection | `[('spark','Іскрогасіння'),('smoke','Димовидалення'),('sprinkler','Спринклери')]`, `required` |
| `panel_id` | Many2one `f3d.fire.panel` | `required`, `ondelete='cascade'` (FACP-1) |
| `equipment_id` | Many2one `maintenance.equipment` | `ondelete='set null'` (хук: `SPARK-1`, `SMOKE-CTRL`, `SPRINKLERS`) |
| `vents_equipment_id` | Many2one `maintenance.equipment` | `ondelete='set null'`, `string="Обладнання люків"` (лише `smoke`: `SMOKE-VENTS`) |
| `source_id` | Many2one `f3d.source` | `ondelete='set null'` (`MB-U85-IO6`; спринклери — порожньо) |
| `signal_state_id` | Many2one `f3d.signal` | `string="Сигнал: стан"` — `spark`: DI0 «іскра»; `smoke`: DI4 «клапани відкриті» |
| `signal_active_id` | Many2one `f3d.signal` | `spark`: DI1 «гасіння» |
| `signal_fault_id` | Many2one `f3d.signal` | `spark`: DI2; `smoke`: DI5 |
| `signal_water_id` | Many2one `f3d.signal` | `spark`: DI3 «тиск води гасіння» |
| `signal_battery_id` | Many2one `f3d.signal` | `smoke`: DI6 «живлення від АКБ» |
| `signal_count_id` | Many2one `f3d.signal` | `spark`: HR 40001–40002 «іскор за добу» |
| `pressure_signal_id` | Many2one `f3d.signal` | `sprinkler`: `equipment/SPRINKLERS/pressure_bar` (власник telemetry; хук §5.4 п. 2 шукає за `code`) |
| `pressure_bar` | Float | `related='pressure_signal_id.last_value'`, `string="Тиск, бар"` |
| `pressure_min_bar` | Float | `related='pressure_signal_id.alarm_low'`, `string="Мінімум, бар"` (6,5) |
| `state` | Selection | `[('unknown','Невідомо'),('ok','Норма'),('active','Спрацювання'),('fault','Несправність'),('battery','Від акумуляторів'),('low_pressure','Низький тиск')]`, `default='unknown'`, `readonly`, `index`, `tracking=True` |
| `state_text` | Char | `compute="_compute_state_text"` (R-13 п. 5) |
| `state_ts` | Datetime | `readonly` |
| `stale` | Boolean | `readonly` — сигнали системи `status='stale'` (A-17) |
| `count_today` | Integer | `readonly`, `string="Іскор за добу"` |
| `count_ts` | Datetime | `readonly` |
| `device_ids` | One2many `f3d.fire.device` `system_id` | |
| `detector_count`, `nozzle_count`, `vent_count` | Integer | `compute="_compute_counts"`, `store=True`, `@api.depends('device_ids.type','device_ids.active')` (4 / 3 / 44) |
| `smoke_zone_ids` | One2many `f3d.fire.smoke.zone` `system_id` | |
| `drive_current_a` | Float | `default=7.5`, `string="Струм приводу, А"` (паспорт `smoke_vent`: соло-мотор 7,5 А) |
| `panel_current_a` | Float | `default=80.0`, `string="Струм щита, А"` (паспорт `smoke_control`: 80 А) |
| `panels_needed` | Integer | `compute`: `ceil(vent_count · drive_current_a / panel_current_a)` = `ceil(44·7,5/80)` = 5 (як `site2.build_smoke`) |
| `vent_area_m2` | Float | `compute`, `digits=(8,1)`: `vent_count · norm('smoke_vent_aa')` = 44,9 |
| `last_test_date` | Date | `string="Остання перевірка"` — data: `SPARK-1` 2026-10-11 (самотест, подія макета), `SMOKE-CTRL` 2026-09-30 (картка `SMOKE-VENTS`), `SPRINKLERS` 2026-09-30 (`equipment.SPRINKLERS.last_inspection`) |
| `note` | Text | |
| `active` | Boolean | `default=True` |

`_f3d_fire_system_code_uniq = models.Constraint("UNIQUE(code)", "Код системи має бути унікальним.")`.
`@api.constrains('system_type', 'pressure_signal_id', 'signal_state_id')`: `sprinkler` без `pressure_signal_id`
допускається (чиста база), але `spark`/`smoke` із `pressure_signal_id` → `"Сигнал тиску — лише для спринклерів."`.

Методи: `_set_state(self, new, ts, etype=None, text=None)` — запис, подія R-14 (якщо `etype`), шина
`_notify('f3d.fire.panel', ['FACP-1'], 'state')` (системи показуються в розділі `fire.systems`);
`action_f3d_show()` → `equipment_id.action_f3d_show()`; `action_view_devices()`, `action_view_events()`.

### M-07 `f3d.fire.smoke.zone` — димова зона (FR-09, A-10)

`_name = "f3d.fire.smoke.zone"`, `_description = "Димовидалення: димова зона"`, `_order = "code"`, `_rec_name = "code"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(8) | `required`, `index`, SQL unique, regex `^SZ-[0-9]{1,2}$` (`"Код димової зони: SZ-<n>"`) |
| `name` | Char(128) | `required`: «Димова зона SZ-1» |
| `system_id` | Many2one `f3d.fire.system` | `required`, `ondelete='cascade'`, domain `[('system_type','=','smoke')]` |
| `x0`, `y0`, `x1`, `y1` | Float | `digits=(8,2)`, `required` (`infra.SMOKE_ZONES`) |
| `area_m2` | Float | `compute`, `store=True`, `digits=(12,0)`: `(x1−x0)·(y1−y0)` (1440, 1584, 920, 1380, 1300, 1440, 1440, 1296) |
| `vent_ids` | One2many `f3d.fire.device` `smoke_zone_id` | |
| `vent_count` | Integer | `compute`, `store=True`, `@api.depends('vent_ids.active','vent_ids.type')`: активні `smoke_vent` |
| `vent_area_m2` | Float | `compute`, `digits=(8,2)`: `vent_count · norm('smoke_vent_aa')` |
| `need_vents` | Integer | `readonly`, `string="Потрібно люків"` (R-09) |
| `max_area_m2` | Float | `readonly`, `string="Найбільша площа за нормою, м²"` (R-09: 1600) |
| `area_ok`, `vents_ok` | Boolean | `readonly` |
| `compliance` | Selection | як у M-03, `default='na'`, `readonly` |
| `compliance_note` | Text | `readonly` |
| `active` | Boolean | `default=True` |

`_check_rect`: `x0 < x1`, `y0 < y1`, у межах будівлі (CB-12 `plant_length_m × plant_width_m`) → `"Контур димової зони %s поза будівлею."`.
Методи: `_recompute(self)` — R-09; `point_inside(x, y)`.

### M-09 `f3d.fire.exit` — евакуаційний вихід (FR-08)

`_name = "f3d.fire.exit"`, `_description = "Евакуація: вихід"`, `_order = "code"`, `_rec_name = "display"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(8) | `required`, `index`, SQL unique, regex `^EX-[A-Z0-9]{1,4}$` (`"Код виходу: EX-<бік><n>"`) |
| `name` | Char(128) | `required`: «Аварійний вихід EX-S1, південна стіна»; `EX-IN` — «Вхід персоналу EX-IN, південна стіна»; `EX-N5` — «Аварійний вихід EX-N5 з компресорної, північна стіна» |
| `display` | Char | `compute`, `store=True`: `"%s · %s" % (code, side label)` |
| `kind` | Selection | `[('emergency','Аварійний вихід'),('staff','Вхід персоналу')]`, `required`, `default='emergency'` (`EX-IN` → `staff`) |
| `x`, `y` | Float | `digits=(8,2)`, `required` (`evacuation.EXITS`) |
| `side` | Selection | `[('S','Південна стіна'),('N','Північна стіна'),('W','Західна стіна'),('E','Східна стіна')]`, `required` |
| `width_m` | Float | `digits=(4,2)`, `default=1.2`, `string="Ширина у просвіті, м"` (`evacuation.DOOR_W`; паспорт `exit_door` Hörmann STU) |
| `equipment_id` | Many2one `maintenance.equipment` | `ondelete='set null'` (хук: `EXITS`) |
| `route_ids` | One2many `f3d.fire.route` `exit_id` | |
| `route_count` | Integer | `compute` |
| `nearest_exit_m` | Float | `readonly`, `digits=(8,1)`, `string="До найближчого іншого виходу, м"` (R-06, довідково: EX-S4 і EX-IN — 7,4) |
| `width_ok` | Boolean | `readonly` (R-07) |
| `compliance` | Selection | як у M-03, `readonly` |
| `compliance_note` | Text | `readonly` |
| `note` | Text | |
| `active` | Boolean | `default=True` |

`@api.constrains('x','y')`: точка на зовнішній стіні: `|y| ≤ 0.5` або `|y − plant_width_m| ≤ 0.5` або `|x| ≤ 0.5`
або `|x − plant_length_m| ≤ 0.5`, і `0 ≤ x ≤ plant_length_m`, `0 ≤ y ≤ plant_width_m` → інакше
`ValidationError("Вихід %s має лежати на зовнішній стіні будівлі.")`. `@api.constrains('width_m')`: `> 0`.
Методи: `_recompute()` (R-06, R-07), `action_f3d_show()` → `equipment_id.action_f3d_show()` (3D-об'єкт `EXITS`).

### M-10 `f3d.fire.route` — маршрут евакуації (FR-08, A-05, A-25)

`_name = "f3d.fire.route"`, `_description = "Евакуація: маршрут"`, `_order = "zone_code"`, `_rec_name = "name"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(32) | `required`, `index`, SQL unique, `string="Код у 3D"`: `EVAC-<код зони без Z->` (`EVAC-CUT`, `EVAC-RCV-1`; `site2.build_evacuation`) |
| `name` | Char(128) | `required`: назва з `evac_routes.json` (`"Розкрій"`) |
| `zone_id` | Many2one `f3d.zone` | `required`, `ondelete='cascade'`, `index`; SQL unique (`UNIQUE(zone_id)`, «Для зони вже є маршрут») |
| `zone_code` | Char | `related='zone_id.f3d_code'`, `store=True` |
| `exit_id` | Many2one `f3d.fire.exit` | `required`, `ondelete='restrict'` |
| `length_m` | Float | `required`, `digits=(8,1)`, `string="Довжина шляху, м"` — `length` макета (Дейкстра; не довжина ламаної `path`) |
| `path` | Json | `required`, `string="Шлях"` — `[[x, y], …]`, 2…7 точок (усього 132 точки в 32 маршрутах) |
| `path_text` | Text | `compute`/`inverse` (як `f3d.zone.polygon_text` base) |
| `point_count` | Integer | `compute` |
| `width_min_m` | Float | `digits=(4,2)`, `string="Найвужче місце, м"` (A-25; у data 1,2 для всіх 32: прорізи 2,0/1,6/3,6 м ширші за двері) |
| `norm_m` | Float | `compute` (не зберігається): R-05 (240 або 50) |
| `length_ok`, `width_ok` | Boolean | `readonly` |
| `compliance` | Selection | як у M-03, `readonly`, `index` |
| `compliance_note` | Text | `readonly` |
| `active` | Boolean | `default=True` |

`@api.constrains('path', 'exit_id')`: список ≥ 2 точок; кожна — 2 числа (не `bool`); `0 ≤ x ≤ plant_length_m`,
`0 ≤ y ≤ plant_width_m`; остання точка не далі `exit_id.width_m / 2 + 0.5` м від `(exit.x, exit.y)` (у data
найбільше 0,89 м — `Z-PRE`) → `ValidationError("Шлях маршруту %s: %s")` з причиною; `length_m > 0`.
Методи: `_recompute()` (R-05, R-07); `action_f3d_show()` — `act = zone_id.action_f3d_show()`; якщо
`act['tag'] == 'f3d_viewer.action'` → `act['params']['code'] = self.code` (3D-об'єкт шляху); повернути `act`.

### M-11 `f3d.fire.drill` — навчальна тривога (FR-13, FR-14, FR-23, FR-24)

```python
class F3dFireDrill(models.Model):
    _name = "f3d.fire.drill"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Пожежна безпека: навчальна тривога"
    _order = "planned_ts desc, id desc"
    _rec_name = "name"
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char(32) | `required`, `readonly`, `copy=False`, `default='/'`, `index`; у `create` → `ir.sequence` `f3d.fire.drill` (`DRILL/2026/0001`) |
| `title` | Char(128) | `required`, `default="Навчальна пожежна тривога"`, `string="Назва"` |
| `company_id` | Many2one `res.company` | `required`, `default=lambda self: self.env.company`, `index` |
| `state` | Selection | `[('draft','Чернетка'),('planned','Заплановано'),('running','Триває'),('evaluating','Оцінювання'),('done','Завершено'),('cancelled','Скасовано')]`, `default='draft'`, `required`, `index`, `tracking=True` |
| `origin` | Selection | `[('manual','Вручну'),('panel','З приладу (тест)'),('demo','Демо')]`, `default='manual'`, `required`, `readonly` |
| `mode` | Selection | `[('sim','Емулятор'),('panel_test','Тест приладу'),('tabletop','Настільне')]`, `required`, `default='panel_test'`, `tracking=True` |
| `planned_ts` | Datetime | `string="Заплановано на"`, `tracking=True` (обов'язкове для `planned`) |
| `zone_id` | Many2one `f3d.fire.zone` | `required`, `ondelete='restrict'`, `string="Зона пожежі"`, `tracking=True` |
| `device_id` | Many2one `f3d.fire.device` | `ondelete='set null'`, `string="Сповіщувач"`, `domain="[('zone_id','=',zone_id),('is_detector','=',True)]"` |
| `template_id` | Many2one `f3d.fire.drill.template` | `ondelete='set null'`, `default` = шаблон з `is_default=True` |
| `responsible_id` | Many2one `res.users` | `default=lambda self: self.env.user`, `string="Відповідальний"` |
| `start_ts`, `end_ts` | Datetime | `readonly`, `string="Початок"`, `"Завершення"` |
| `duration_s` | Integer | `compute`, `store=True`: `end_ts − start_ts` у секундах (0, якщо немає) |
| `elapsed_s` | Integer | `compute` (не зберігається): `now − start_ts` для `running`, інакше `duration_s` |
| `sim_run_ref` | Char(32) | `readonly`, `string="Запуск емулятора"` (`f3d.sim.run.name`, FR-23) |
| `sim_available` | Boolean | `compute`: `'f3d.sim.run' in self.env` |
| `real_alarm` | Boolean | `readonly`, `string="Справжня тривога під час навчання"` (R-18 п. 4) |
| `step_ids` | One2many `f3d.fire.drill.step` `drill_id` | `copy=True` |
| `person_ids` | One2many `f3d.fire.drill.person` `drill_id` | `groups="factory3d_fire_safety.group_f3d_fire_drill,hr.group_hr_user"`, `copy=False` (FR-24) |
| `event_ids` | One2many `f3d.fire.event` `drill_id` | readonly |
| `steps_done`, `steps_total` | Integer | `compute`, `store=True`, `@api.depends('step_ids.done')` |
| `on_site_count`, `evacuated_count`, `present_count`, `missing_count` | Integer | `compute="_compute_people"`, `store=True`, `compute_sudo=True`, `@api.depends('person_ids.status')`: усього / `evacuated` / `present` (перекличка) / `missing` |
| `evac_time_s` | Integer | `readonly`, `string="Час евакуації, с"` (R-16 п. 4) |
| `evac_pct` | Float | `compute`, `store=True`, `digits=(5,1)`: `(evacuated + present) / on_site · 100`; `on_site = 0` → `100.0` |
| `time_limit_s` | Integer | `default` = параметр `drill_time_limit_s` (300), `string="Норматив часу, с"` (Q-03) |
| `data_quality` | Selection | `[('full','Повні'),('partial','Неповні')]`, `compute`, `store=True`: `partial`, якщо `present_count + missing_count > 0` або `on_site_count == 0` |
| `passage_source` | Char(32) | `readonly`, `string="Джерело проходів"` (`hr_attendance` / `access` / `demo`) |
| `result_suggested` | Selection | `[('ok','Пройдено'),('remarks','Пройдено із зауваженнями'),('failed','Не пройдено')]`, `compute`, `store=True` (R-16 п. 6) |
| `result` | Selection | ті самі значення, `tracking=True`, `string="Результат"` |
| `conclusions` | Text | `string="Висновки"` |
| `remarks` | Text | `string="Зауваження й заходи"` |
| `print_names` | Boolean | `default=False`, `string="Друкувати прізвища у протоколі"` (FR-24) |
| `last_tick_ts` | Datetime | службове |
| `color` | Integer | `compute`: `running`→1, `evaluating`→3, `done`+`ok`→10, `done`+`remarks`→2, `failed`→1, інше 0 |

Обмеження: `@api.constrains('state','planned_ts')` — `planned` без `planned_ts` → `"Вкажіть дату й час навчання."`;
`@api.constrains('device_id','zone_id')` — пристрій не з цієї зони → `"Сповіщувач %s не належить зоні %s."`;
`@api.constrains('state')` — `search_count([('state','=','running'),('company_id','=',company_id)]) > 1` →
`"Одночасно може тривати лише одне навчання."`.

Методи (переходи — §10.6):

| Сигнатура | Алгоритм |
|---|---|
| `create(self, vals_list)` | `name='/'` → `next_by_code('f3d.fire.drill')`; якщо `step_ids` не задані і є `template_id` (або default) → `_fill_steps()` |
| `_fill_steps(self)` | `step_ids = [Command.clear()] + [Command.create({sequence, t_plan_s, who, text: render(text), auto_key})]` для кроків шаблону; `render` — `str.format_map` з `{'detector': device_id.address or "—", 'zone': zone_id.name, 'sounders': кількість активних `sounder`}` (A-29); невідомий плейсхолдер → лишається як є |
| `action_plan(self)` | `draft → planned` |
| `action_start(self, ts=None, source='manual')` | `draft/planned → running`; R-15 |
| `action_start_sim(self)` | лише `mode='sim'` і `sim_available`, інакше `UserError("Модуль емулятора не встановлено.")`; `run = self._f3d_sim_start()` (iot_sim bridge, A-34); `sim_run_ref = run.name`; `run.state == 'failed'` → `UserError("Емулятор не запустив сценарій: %s" % run.message)`; далі `action_start(source='sim')` |
| `action_stop(self, ts=None)` | `running → evaluating`; R-16 п. 4–6; якщо `sim_run_ref` і `sim_available` → `_f3d_sim_stop()` (помилка емулятора — лише чаттер, не виняток) |
| `action_rollcall(self)` | лише `evaluating`; повертає дію майстра M-11d (`context={'default_drill_id': id}`) |
| `action_close(self)` | `evaluating → done`; без `result` → `UserError("Оберіть результат навчання.")`; без `conclusions` → `UserError("Заповніть висновки.")`; подія `drill_end` уже записана при `action_stop` |
| `action_cancel(self)` | `draft/planned/running → cancelled`; для `running` — як `action_stop` без розрахунків, `end_ts=now` |
| `action_reset_draft(self)` | `cancelled → draft`; `start_ts/end_ts/evac_time_s` очищаються, `person_ids` видаляються, кроки — `done=False` |
| `action_print(self)` | `report_f3d_fire_drill` (V-21) |
| `action_f3d_show(self)` | `zone_id.action_f3d_show()` |
| `_tick(self)` | для `running`: R-16 п. 2–3 (проходи), R-17 (кроки), R-16 п. 7 (авто-стоп), `last_tick_ts=now`, шина `_notify('f3d.fire.drill', [name], 'state')`, якщо щось змінилось |
| `@api.model _cron_tick(self)` | `drills = search([('state','=','running')])`; порожньо → вихід; інакше до `5` ітерацій: `drills._tick()`, `self.env.cr.commit()` (поза тестами: `not self.env.registry.in_test_mode()`), `time.sleep(10)`, `drills = drills.exists().filtered(lambda d: d.state == 'running')`; у тестовому режимі — одна ітерація без `sleep`/`commit` |
| `@api.model _f3d_is_active_at(self, ts) -> bool` | CF-06 (для `factory3d_access` CA-09): `ts` — UTC naive `datetime`; `True`, якщо `self.sudo().search_count([('start_ts','!=',False), ('start_ts','<=',ts), '|', ('end_ts','=',False), ('end_ts','>=',ts), ('state','in',('running','evaluating','done','cancelled'))]) > 0` (будь-яка компанія; навчання в `draft`/`planned` не рахуються). Приклад: навчання 10:00:00–10:05:30 → `ts` 10:03 → `True`; 10:06 → `False`; `running` без `end_ts`, старт 10:00 → будь-який `ts ≥ 10:00` → `True`; `ts` до старту → `False` |
| `@api.model _match_test_alarm(self, zone, device, ts, real=False)` | R-18 |
| `_f3d_sim_start(self) -> record` / `_f3d_sim_stop(self)` | iot_sim bridge (FR-23, A-34), `models/iot_sim_bridge.py` |
| `unlink(self)` | лише `draft`/`cancelled` → інакше `UserError("Видалити можна лише чернетку або скасоване навчання.")` |

### M-11a `f3d.fire.drill.step` — крок навчання

`_name = "f3d.fire.drill.step"`, `_description = "Навчальна тривога: крок"`, `_order = "drill_id, sequence, id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `drill_id` | Many2one `f3d.fire.drill` | `required`, `ondelete='cascade'`, `index` |
| `sequence` | Integer | `default=10` |
| `t_plan_s` | Integer | `required`, `default=0`, `string="План, с"` (0, 3, 3, 6, 9, 12, 15, 20) |
| `who` | Char(64) | `required`, `string="Хто"` |
| `text` | Char(256) | `required`, `string="Дія"` |
| `auto_key` | Selection `AUTO_KEYS` | `[('none','Вручну'),('detector','Тривога/тест зони на приладі'),('sounders','Оповіщувачі увімкнено'),('brigade','Передача на пульт'),('ventilation','Вентиляцію зупинено'),('smoke','Клапани димовидалення відкрито'),('doors','Двері розблоковано'),('evacuation','Перший вихід людей'),('machines','Верстати зони зупинено')]`, `required`, `default='none'` |
| `done` | Boolean | `default=False`, `string="Виконано"` |
| `done_ts` | Datetime | `string="Час виконання"` |
| `t_fact_s` | Integer | `string="Факт, с"` — `done_ts − drill.start_ts` у секундах, ≥ 0 |
| `delay_s` | Integer | `compute`, `store=True`: `t_fact_s − t_plan_s` (лише для `done`) |
| `done_by` | Selection | `[('auto','Автоматично'),('manual','Вручну')]` |
| `note` | Char(256) | |

`@api.constrains('t_plan_s')` ≥ 0. Методи: `action_done_now(self)` — лише `drill_id.state == 'running'` або
`evaluating`; `done=True`, `done_ts=now`, `t_fact_s=max(0, now − start_ts)`, `done_by='manual'`;
`action_undo(self)` — лише `done_by='manual'` і `drill.state in ('running','evaluating')`: скидає поля.

### M-11b `f3d.fire.drill.person` — людина на об'єкті (FR-13, FR-24)

`_name = "f3d.fire.drill.person"`, `_description = "Навчальна тривога: людина на об'єкті"`, `_order = "drill_id, seq"`.

| Поле | Тип | Параметри |
|---|---|---|
| `drill_id` | Many2one `f3d.fire.drill` | `required`, `ondelete='cascade'`, `index` |
| `seq` | Integer | `string="№"` — порядковий номер у списку (стабільний після знеособлення) |
| `employee_id` | Many2one `hr.employee` | `ondelete='set null'`, `index` (на тестовій копії `neutralize.sql` ставить NULL) |
| `since` | Datetime | `string="На об'єкті з"` |
| `source` | Selection | `[('attendance','Відмітки'),('access','СКУД'),('manual','Вручну'),('demo','Демо')]`, `required` |
| `exit_ts` | Datetime | `string="Вийшов о"` |
| `exit_point` | Char(64) | `string="Де вийшов"` (`TURN-1`, «Відмітка виходу», код дверей) |
| `exit_s` | Integer | `compute`, `store=True`: `exit_ts − drill.start_ts`, с (порожньо без виходу) |
| `rollcall` | Selection | `[('na','—'),('present','Присутній на місці збору'),('absent','Відсутній')]`, `default='na'` |
| `status` | Selection | `[('on_site','На об\'єкті'),('evacuated','Вийшов'),('present','Є на перекличці'),('missing','Не знайдено')]`, `compute`, `store=True`, `@api.depends('exit_ts','rollcall','drill_id.state')`: `exit_ts` → `evacuated`; `rollcall='present'` → `present`; `drill.state in ('draft','planned','running')` → `on_site`; інакше `missing` |

`_f3d_fire_person_uniq = models.Constraint("UNIQUE(drill_id, employee_id)", "Працівник уже є в списку навчання.")`.

### M-11c `f3d.fire.drill.template` і M-11e `f3d.fire.drill.template.step` — шаблон навчання

`f3d.fire.drill.template`: `_description = "Навчальна тривога: шаблон"`, `_order = "sequence, id"`. Поля: `name` Char
`required` («Евакуація цеху: сценарій макета»); `sequence` Integer; `is_default` Boolean (constrains: лише один
активний `is_default=True` → `"Шаблон за замовчуванням може бути лише один."`); `duration_s` Integer `default=300`
(для `fire_drill` емулятора); `default_zone_id` Many2one `f3d.fire.zone` (data: `FA-CNC`); `default_device_id`
Many2one `f3d.fire.device` (data: `2.CNC.05`) — для `evacuation.drill_origin/drill_detector` (R-21); `step_ids`
One2many M-11e; `note` Text; `active` Boolean.

`f3d.fire.drill.template.step`: `template_id` (required, cascade), `sequence`, `t_plan_s` Integer ≥ 0, `who`
Char(64), `text` Char(256) (з плейсхолдерами A-29), `auto_key` Selection `AUTO_KEYS`.

Data (`data/f3d_fire_drill_template.xml`, xml-id `drill_template_default`, кроки `drill_template_step_01…08`,
`odoo_demo.py:evacuation()`):

| № | t_plan_s | who | text | auto_key |
|---|---|---|---|---|
| 1 | 0 | Пожежна сигналізація | Сповіщувач {detector} ({zone}): дим і тепло — тривога на приладі. | `detector` |
| 2 | 3 | Пожежна сигналізація | Увімкнено {sounders} сирен-маяків по всьому цеху. | `sounders` |
| 3 | 3 | Пульт | Сигнал «Пожежа» передано на пульт ДСНС і черговому. | `brigade` |
| 4 | 6 | Вентиляція | Зупинено дахові установки й приплив фасадів, щоб не роздувати вогонь. | `ventilation` |
| 5 | 9 | Димовидалення | Відкрито клапани димовидалення на покрівлі. | `smoke` |
| 6 | 12 | Охорона й доступ | Розблоковано двері з контролем доступу й турнікети, шлагбауми — вгору. | `doors` |
| 7 | 15 | Евакуація | Люди йдуть зеленими маршрутами до найближчих виходів; збір — на паркуванні. | `evacuation` |
| 8 | 20 | Виробництво | Аварійна зупинка верстатів у зоні пожежі; аспірація — іскрогасіння в готовності. | `machines` |

### M-11d `f3d.fire.drill.rollcall.wizard` і M-11f `f3d.fire.drill.rollcall.line` — перекличка (TransientModel)

Майстер: `drill_id` (required), `line_ids` One2many M-11f. `default_get`: рядок на кожну людину навчання зі
статусом `missing` або `present` (`person_id`, `present = (rollcall == 'present')`). Рядок: `wizard_id`,
`person_id` (Many2one M-11b, required), `seq` (related), `employee_name` (related `person_id.employee_id.name`),
`present` Boolean. `action_apply()`: `drill_id.state == 'evaluating'`, інакше `UserError("Перекличка — після
завершення навчання.")`; для кожного рядка `person.rollcall = 'present' if present else 'absent'`; чаттер
навчання «Перекличка: присутні N, відсутні M»; повертає `act_window_close`.

### M-12 `f3d.fire.passage.source` — хук проходів людей (CF-02, A-08, A-19)

Контракт (узгоджено з `factory3d_access` SPEC M-16, CA-09, Q-13): **джерело — будь-яка модель реєстру, чиє `_name`
починається з `f3d.fire.passage.source.`** (з крапкою); `_inherit` від бази не вимагається, бо інші модулі (access) не
залежать від цього модуля. База `f3d.fire.passage.source` (AbstractModel) лише документує інтерфейс і дає реалізацію
пошуку; власне джерело модуля (M-12a) її успадковує.

```python
class F3dFirePassageSource(models.AbstractModel):
    _name = "f3d.fire.passage.source"
    _description = "Пожежна безпека: джерело даних про людей на об'єкті"
    _f3d_priority = 1000          # менше — пріоритетніше
    PREFIX = "f3d.fire.passage.source."
```

| Метод джерела | Вхід → вихід | Обов'язковий |
|---|---|---|
| `_f3d_passages(self, start, end) -> list[dict]` | UTC naive → `[{"employee_id": int, "ts": datetime, "point": str, "direction": "out"\|"in"}]` | так (за ним модель визнається джерелом) |
| `_f3d_on_site(self, at) -> list[dict]` | UTC naive → `[{"employee_id": int, "since": datetime, "point": str}]` | ні (немає — список людей на старті будується з `_f3d_passages(at − 24 год, at)`: останній прохід `in` без пізнішого `out`) |
| `_f3d_available(self) -> bool` | — | ні (немає — джерело доступне) |
| атрибути `_f3d_priority` (int, немає → 1000), `_f3d_key` (str, немає → суфікс імені після префікса: `access`) | — | ні |

Метод бази:

| Сигнатура | Алгоритм |
|---|---|
| `@api.model _f3d_source_names(self) -> list[str]` | `sorted(n for n in self.env.registry if n.startswith(PREFIX))` (як viewer M-01 знаходить провайдери); окремий метод — тести бачать реальний реєстр |
| `@api.model _f3d_get_source(self) -> model` | для `n` з `_f3d_source_names()`: `m = self.env[n].sudo()`; пропустити, якщо `not hasattr(m, '_f3d_passages')`; пропустити, якщо `hasattr(m, '_f3d_available') and not m._f3d_available()`; кандидати сортуються за `(getattr(m, '_f3d_priority', 1000), n)`; повернути першого; порожньо → `self.env['f3d.fire.passage.source.hr_attendance'].sudo()` |
| `@api.model _f3d_source_key(self, m) -> str` | `getattr(m, '_f3d_key', None) or m._name[len(PREFIX):]` |
| `@api.model _f3d_people_at(self, m, at) -> list[dict]` | `m._f3d_on_site(at)`, якщо метод є; інакше — з `m._f3d_passages(at − 24 год, at)` (останній `in` на людину без пізнішого `out`, `since` = його `ts`, `point` = його `point`) |

Відомі джерела: M-12a `hr_attendance` (пріоритет 100, цей модуль); `factory3d_access` M-16
`f3d.fire.passage.source.access` (пріоритет 10, без `_inherit`, без `_f3d_available`/`_f3d_key` → ключ `access`;
`_f3d_passages` повертає проходи периметра в обох напрямках, `point` = код дверей); тестове
`f3d.fire.passage.source.zz_test` (пріоритет 5, лише в тестовому модулі §0.3).

#### M-12a `f3d.fire.passage.source.hr_attendance` (пріоритет 100, `_f3d_key = "hr_attendance"`)

`_inherit = "f3d.fire.passage.source"`.
- `_f3d_available()` → `True`.
- `_f3d_on_site(at)`: `env['hr.attendance'].sudo().search([('check_in','<=',at), '|', ('check_out','=',False),
  ('check_out','>',at)], order='check_in, id')`; на кожного працівника — перший запис: `{"employee_id": att.employee_id.id,
  "since": att.check_in, "point": "Відмітка входу"}`. Демо 14.10: 35 записів (`check_in` 12.10 03:58–04:00 UTC,
  `check_out` порожній) → 35 людей для будь-якого `at` після 12.10 04:00 UTC.
- `_f3d_passages(start, end)`: `search([('check_out','>=',start), ('check_out','<=',end)], order='check_out')` →
  `{"employee_id", "ts": check_out, "point": "Відмітка виходу", "direction": "out"}`.

#### M-12b Джерело `factory3d_access` (зовнішній контракт, access M-16, CA-03, CA-09)

Модель `f3d.fire.passage.source.access` визначає **access**; цей модуль її не створює й не успадковує. Використання:
`_f3d_get_source()` знаходить її за префіксом, коли access встановлено (пріоритет 10 < 100); `passage_source='access'`;
у R-16 беруться лише записи `direction='out'`; відвідувачі в джерело access не входять. Зворотний контракт (CF-06):
access викликає `env['f3d.fire.drill']._f3d_is_active_at(ts)` (M-11), щоб вихід через турнікет під час навчання не
закривав відмітку відвідуваності (fire Q-15, access CA-09).

### M-13 `f3d.zone` — розширення (FR-22)

`_inherit = "f3d.zone"` (`models/f3d_zone.py`). Поля (усі не зберігаються, крім One2many):

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_fire_zone_ids` | One2many `f3d.fire.zone` `zone_id` | `string="Зони сигналізації"` |
| `f3d_fire_zone_count` | Integer | `compute` |
| `f3d_fire_kind` | Selection (значення M-03 `kind`) | `compute`: `kind` першої зони сигналізації (за `lsz_instance`) |
| `f3d_fire_state` | Selection (значення M-01 `state`) | `compute`: найгірший стан зон сигналізації за пріоритетом R-10; без зон — `False` |
| `f3d_evac_route_id` | Many2one `f3d.fire.route` | `compute`: `search([('zone_id','=',id)], limit=1)` |
| `f3d_evac_exit_code` | Char | `compute`: `f3d_evac_route_id.exit_id.code` |
| `f3d_evac_length_m` | Float | `compute`, `digits=(8,1)` |

Метод `action_view_fire_zones(self)` → `act_window` `f3d.fire.zone`, `domain=[('zone_id','=',id)]`.
Приклад: `Z-CNC` → `f3d_fire_kind='multi'`, `f3d_evac_exit_code='EX-S3'`, `f3d_evac_length_m=29.8`;
`Z-OFFICE` → `f3d_fire_zone_count=0`, `f3d_fire_state=False`, маршруту немає (`f3d_evac_route_id` порожній).

### M-14 `maintenance.request` — розширення (FR-10, A-16, R-22)

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_fire_event_id` | Many2one `f3d.fire.event` | `ondelete='set null'`, `string="Подія пожежної безпеки"` |
| `f3d_fire_zone_id` | Many2one `f3d.fire.zone` | `ondelete='set null'`, `index`, `string="Зона сигналізації"` |
| `f3d_fire_device_id` | Many2one `f3d.fire.device` | `ondelete='set null'`, `string="Пристрій"` |
| `f3d_origin` | Selection | `selection_add=[('fire_comm', "Немає зв'язку з пожежним приладом")]`, `ondelete={'fire_comm': 'set null'}` |

Методи:
- `create(self, vals_list)`: для `vals` з `f3d_signal_id`, де сигнал має `module == 'fire_safety'` або є
  `pressure_signal_id` системи: якщо параметр `team_id` задано і `maintenance_team_id` не передано явно викликачем,
  відмінним від telemetry — `vals['maintenance_team_id'] = team_id` (Q-02); `super()`; потім `_f3d_fire_link()`.
- `_f3d_fire_link(self)` — R-22.
- `action_f3d_fire_open_zone(self)` → форма `f3d_fire_zone_id`.

### M-15 `f3d.source`, `f3d.signal`, `f3d.command` — заборона запису й слухач змін (FR-18, A-03, A-22)

`f3d.source` (`models/f3d_source.py`, `_inherit = "f3d.source"`):

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_fire_readonly` | Boolean | `default=False`, `copy=False`, `string="Пожежна сигналізація: лише читання"`, `help="Рішення D-07: запис у прилад неможливий; прапор не знімається"` |
| `f3d_fire_consent_date` | Date | `string="Дозвіл монтажника: дата"`, `tracking=True` |
| `f3d_fire_consent_person` | Char(128) | `string="Дозвіл монтажника: особа, організація"`, `tracking=True` |
| `f3d_fire_consent_doc` | Char(128) | `string="Дозвіл монтажника: документ"` (номер листа/акта) |
| `f3d_fire_consent_attachment_id` | Many2one `ir.attachment` | `string="Скан дозволу"`, `ondelete='set null'` |

Перевірки (діють і під `sudo()` — `@api.constrains` не залежить від `env.su`):
1. `@api.constrains('write_enabled', 'f3d_fire_readonly')`: `f3d_fire_readonly and write_enabled` →
   `ValidationError("Джерело пожежної сигналізації працює лише на читання (рішення D-07). Увімкнути запис неможливо.")`;
2. `@api.constrains('type', 'params', 'f3d_fire_readonly')`: `f3d_fire_readonly and type == 'bacnet_ip' and not
   (params or {}).get('read_only')` → `ValidationError("Джерело %s: для пожежного приладу параметр read_only=true обов'язковий.")`;
3. `@api.constrains('read_enabled', 'f3d_fire_consent_date', 'f3d_fire_consent_person')`: `f3d_fire_readonly and
   read_enabled and environment == 'prod'` (параметр `factory3d.base.environment`) і не заповнені дата та особа →
   `ValidationError("Увімкнути читання приладу на проді можна лише з дозволом монтажника: заповніть дату й особу (вкладка «Пожежна сигналізація»).")`;
4. `write(vals)`: `'f3d_fire_readonly' in vals and not vals['f3d_fire_readonly'] and any(self.mapped('f3d_fire_readonly'))`
   → `ValidationError` з текстом п. 1 (до `super()`).

`f3d.signal` (`models/f3d_signal.py`, `_inherit = "f3d.signal"`):
1. `@api.constrains('write_enabled', 'module', 'source_id')`: `write_enabled and (module == 'fire_safety' or
   source_id.f3d_fire_readonly)` → `ValidationError("Сигнал пожежної безпеки %s працює лише на читання (D-07).")`;
2. `@api.model _f3d_ingest(self, readings, src="module", collector=None)` (A-22): `res = super()._f3d_ingest(...)`;
   `codes = [c for c in res.get('changed_codes') or [] if c.startswith('fire/') or c in self._f3d_fire_extra_codes()]`;
   якщо `codes` і параметр `read_enabled`: `with self.env.cr.savepoint(): env['f3d.fire.panel'].sudo()._f3d_fire_sync(codes=codes)`;
   будь-який виняток синхронізації логується `_logger.exception("fire sync after ingest")` і **не** впливає на `res`
   (push телеметрії не відкочується через пожежний модуль); повернути `res`;
3. `@api.model _f3d_fire_extra_codes(self) -> frozenset` — коди `pressure_signal_id` систем (`tools.ormcache()`,
   інвалідація в `f3d.fire.system.write/create`).

`f3d.command` (`models/f3d_command.py`, `_inherit = "f3d.command"`): `@api.model_create_multi create(vals_list)` — для
кожного `vals`: `sig = env['f3d.signal'].sudo().browse(vals['signal_id'])`; `sig.module == 'fire_safety' or
sig.source_id.f3d_fire_readonly` → `ValidationError("Команди на пристрої пожежної безпеки заборонені (D-07).")`
незалежно від `env.su`; далі `super()`.

### M-16 `res.config.settings` — розширення (FR-21)

Усі поля — `config_parameter='factory3d.fire_safety.<ключ>'`, крім позначених:

| Поле | Тип | Ключ / умовчання | Перевірка в `set_values` |
|---|---|---|---|
| `f3d_fire_read_enabled` | Boolean | `read_enabled` / CB-10 | `groups="factory3d_base.group_f3d_admin"` (поле); зміна → `_f3d_fire_sync(full=True)` після збереження |
| `f3d_fire_comm_stale_after_s` | Integer | `comm_stale_after_s` / 90 | ≥ 30 |
| `f3d_fire_comm_lost_after_s` | Integer | `comm_lost_after_s` / 180 | > `comm_stale_after_s` |
| `f3d_fire_dust_warn_pct` | Float | `dust_warn_pct` / 80 | 0 < warn < alarm ≤ 100; зміна → `warn_high` усіх сигналів `…/dust` модуля |
| `f3d_fire_dust_alarm_pct` | Float | `dust_alarm_pct` / 90 | те саме → `alarm_high` |
| `f3d_fire_polymer_panels` | Boolean | `polymer_panels` / False | зміна → `_schedule_compliance()` |
| `f3d_fire_cover_tol_m` | Float | `cover_tol_m` / 0.5 | 0 ≤ x ≤ 2; зміна → `_schedule_compliance()` |
| `f3d_fire_drill_time_limit_s` | Integer | `drill_time_limit_s` / 300 | ≥ 30 |
| `f3d_fire_drill_auto_create` | Boolean | `drill_auto_create` / True | — |
| `f3d_fire_drill_match_window_min` | Integer | `drill_match_window_min` / 30 | 1…720 |
| `f3d_fire_drill_auto_stop_s` | Integer | `drill_auto_stop_s` / 120 | ≥ 10 |
| `f3d_fire_drill_sim_duration_s` | Integer | `drill_sim_duration_s` / 300 | 30…3600 |
| `f3d_fire_alert_group_id` | Many2one `res.groups` | не `config_parameter`: `get_values` читає xml-id з `alert_group_xmlid` → id; `set_values` пише xml-id групи (`group.get_external_id()[id]`; група без xml-id → `UserError("Оберіть групу з зовнішнім ідентифікатором.")`) | — |
| `f3d_fire_team_id` | Many2one `maintenance.team` | `team_id` / id «Служба головного механіка» (хук) | — |
| `f3d_fire_viewer_devices` | Boolean | `viewer_devices` / False | — |
| `f3d_fire_event_ack_required` | Boolean | `event_ack_required` / True | — |

Порушення перевірки → `UserError` з назвою поля й межами («Поріг «Очистити» має бути більшим за поріг
«Попередження» і не більшим за 100 %.»). Поля `write_enabled` у налаштуваннях **немає** (FR-18, AC-65).

### M-17 Провайдери переглядача — міст-модуль `factory3d_fire_safety_viewer` (FR-15, CF-01, A-01, A-35)

Odoo імпортує Python-класи один раз на процес, тому `_inherit = "f3d.viewer.provider"` не можна зробити умовним
у самому модулі: провайдери живуть у міст-модулі `odoo_addons/factory3d_fire_safety_viewer` (`depends`:
`factory3d_fire_safety`, `factory3d_viewer`; `auto_install=True`; як telemetry A-20), §0.2.

| Модель | `_f3d_sequence` | `_f3d_sections` | `_f3d_group` | `_f3d_viewer_collect` | `_f3d_viewer_delta` | `_f3d_viewer_bus_models` |
|---|---|---|---|---|---|---|
| `f3d.viewer.provider.fire` | 130 | `("fire",)` | `factory3d_base.group_f3d_user` | `payload["fire"] = tools.payload.build_fire(env, ctx)` (R-20) | якщо `set(ctx["changes"]) ∩ BUS_MODELS` → `patch["fire"] = build_fire(...)`, інакше нічого | `BUS_MODELS = ["f3d.fire.panel", "f3d.fire.zone", "f3d.fire.system", "f3d.fire.event", "f3d.fire.device"]` |
| `f3d.viewer.provider.evacuation` | 140 | `("evacuation",)` | `factory3d_base.group_f3d_user` | `payload["evacuation"] = build_evacuation(env, ctx)` (R-21) | те саме для `["f3d.fire.drill", "f3d.fire.route", "f3d.fire.exit"]` | ці три |

`build_fire`/`build_evacuation` — у `factory3d_fire_safety/tools/payload.py` (основний модуль, без залежності від
viewer; дати — власна `tools/dates.local(dt)` = `Europe/Kyiv`, формат `"%Y-%m-%d %H:%M"`, як viewer R-02), щоб тести
основного модуля перевіряли структуру без переглядача (AC-55…AC-57). Читання — від імені користувача запиту (без
`sudo`); `f3d.fire.drill.person` у payload не потрапляє (лише кількості).

### M-18 `f3d.push.handler.fire` — повідомлення BACnet (A-04, API-01)

`_name = "f3d.push.handler.fire"`, `_inherit = "f3d.push.handler"` (telemetry M-11/CT-08 — telemetry є в `depends`),
`_f3d_push_routes = ("bacnet_event",)`. `_f3d_handle_push(self, route, event)`: R-14 п. 5 з `event["payload"]` за
схемою API-01; невалідний payload → `ValueError("bacnet_event: <поле>")` (telemetry записує в `f3d.push.event.error`).

### M-19 `f3d.fire.bacnet.device.wizard` — зміна BACnet device instance (TransientModel)

Поля: `panel_id` (required), `old_instance` Integer (readonly, з `default_old_instance`), `new_instance` Integer
`required` (0…4194302; constrains `"BACnet instance: 0…4194302"`), `signal_count` Integer (compute: сигнали
`source_id == panel_id.source_id`, `module == 'fire_safety'`, `address.device == old_instance`). `action_apply()`:
користувач без `factory3d_base.group_f3d_admin` → `AccessError`; для кожного такого сигналу
`address = dict(address, device=new_instance)` (через `write`, щоб telemetry скинула ETag колектора); чаттер панелі
«BACnet device змінено: 200 → <new>, сигналів <n>»; `display_notification`.

### iot_sim bridge (`models/iot_sim_bridge.py`, FR-23, A-34)

Методи `f3d.fire.drill` (без `_inherit` чужих моделей — лише виклики `self.env[...]` за наявності):
- `_f3d_sim_start(self) -> f3d.sim.run`: `ensure_one()`; користувач поза `group_f3d_fire_drill` → `AccessError`;
  `'f3d.sim.run' not in self.env` → `UserError("Модуль емулятора не встановлено.")`;
  `scenario = env['f3d.sim.scenario'].sudo().search([('code','=','fire_drill')], limit=1)` → немає →
  `UserError("У пульті емулятора немає сценарію fire_drill.")`; `params = {"zone": zone_id.code, "detector":
  device_id.address or zone_id.device_ids.filtered('is_detector')[:1].address, "real": False, "duration_s":
  _get_param('drill_sim_duration_s', 300)}`; `return self._f3d_sim_create_run(scenario, params)`, де
  `_f3d_sim_create_run(self, scenario, params)` = `env['f3d.sim.run'].sudo()._create_and_start(scenario, params)` (окремий
  метод — тести підміняють його; iot_sim M-05; стоп-кран `factory3d.iot_sim.write_enabled` перевіряє iot_sim — його
  `UserError` пробрасується). Для демо-зони: `{"zone": "FA-CNC", "detector": "2.CNC.05", "real": false, "duration_s": 300}`.
- `_f3d_sim_stop(self)`: `run = env['f3d.sim.run'].sudo().search([('name','=',sim_run_ref)], limit=1)`;
  `run.state in ('queued','running')` → `run.action_stop()`; виняток → `message_post("Емулятор: не вдалося зупинити
  сценарій: %s")`.

## 3. Представлення й меню

Спільне: рядки UI — українською в XML (D-14); Odoo 19: `<list>`, умови через `invisible`/`readonly`/`required`
(без `attrs`); стани — `widget="badge"` з декораціями `decoration-danger="state in ('alarm','prealarm')"`,
`decoration-warning="state in ('fault','disabled')"`, `decoration-info="state == 'test'"`,
`decoration-success="state == 'normal'"`, `decoration-muted="state == 'unknown'"` (для систем —
`active`→danger, `fault/battery/low_pressure`→warning, `ok`→success); відповідність — `widget="badge"`
`decoration-success="compliance == 'ok'"`, `decoration-warning="compliance == 'warn'"`,
`decoration-danger="compliance == 'fail'"`. Json-поля — через `*_text` з `widget="ace"` `options="{'mode': 'json'}"`.
Фільтри «Групувати за» в search-представленнях мають `name="group_<поле>"` (`group_state`, `group_type`, `group_group`) —
на них посилаються `search_default_*` дій.
Кнопка «Показати в 3D» — `icon="fa-cube"`, `invisible="not viewer_available"` (там, де поле є) — інакше CB-02
сам повідомляє про відсутній переглядач. Жодна кнопка, дія чи пункт меню модуля не створює `f3d.command` і не
викликає запис у пристрій (AC-31).

| ID | XML-id (модуль `factory3d_fire_safety`) | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `view_f3d_fire_panel_form` | form `f3d.fire.panel` | `<header>`: `action_recompute_compliance` («Перерахувати норми», `groups=group_f3d_manager`), `action_view_3d_alarm` («Тривога в 3D», `btn-danger`, `invisible="state not in ('alarm','prealarm') or not viewer_available"`), `action_f3d_show` («Показати в 3D»), `action_set_bacnet_device` («Змінити BACnet device», `groups=group_f3d_admin`), `action_add_comment` («Коментар у журнал», `groups=group_f3d_fire_drill`). Над `<sheet>`: `<div class="alert alert-danger" role="alert" invisible="state != 'alarm'">` з `state_text`; `alert-warning` `invisible="comm != 'lost'"` «Зв'язок із приладом втрачено з <last_seen>»; `alert-info` `invisible="read_enabled"` «Обробку сигналів вимкнено стоп-краном»; `alert-warning` `invisible="not compliance_dirty"` «Норми або пристрої змінено — перерахуйте відповідність». Статбокс: `action_view_zones` (`zone_count`, «Зони», `fa-th`), `action_view_devices` (`device_count`, «Пристрої»), `action_view_events` (`event_count`, «Події за 7 діб», `fa-list`), `warn_count` («Попередження», без дії, `invisible="not warn_count"`), `action_view_requests` («Заявки ТО», `fa-wrench`). `<sheet>`: `name` (title); група «Стан»: `state` (badge), `state_text`, `raw_state`, `system_state`, `state_ts`, `comm` (badge: `online` success, `stale` warning, `lost` danger, `off` muted), `last_seen`, `comm_since`, `alarms_count`, `faults_count`, `disabled_count`, `sounders_active`, `brigade_transmitted`, `alarm_zone_ids` (`many2many_tags`, `invisible="not alarm_zone_ids"`); група «Прилад»: `code`, `equipment_id`, `manufacturer`, `model`, `zone_id`, `x`, `y`, `company_id` (`groups="base.group_multi_company"`). `<notebook>`: «Шлейфи» (`loop_ids` list readonly: `number`, `from_x_m`, `to_x_m`, `detectors_count`, `mcp_count`, `sounders_count`, `flame_count`, `modules_count`, `state` badge, `request_id`); «Системи» (`system_ids` list readonly: `code`, `name`, `state` badge, `state_text`, `count_today`, `last_test_date`); «Відповідність нормам» (групи: «Розстановка» — `compliance_zones_ok`/`compliance_zones_total` («Зони відповідають»), `compliance_mcp_max_m`, `compliance_mcp_point`, `compliance_mcp_ok`, `compliance_sounder_max_m` з підказкою A-26, `compliance_missing_zones`; «Евакуація» — `compliance_routes_ok`/`compliance_routes_total`, `compliance_exits_ok`, `compliance_exit_pair_m`, `compliance_exit_l_m`, `evac_max_distance_m`, `evac_worst_x`, `evac_worst_y`; «Димовидалення» — `compliance_smoke_ok`/`compliance_smoke_total`; `compliance_ts`); «Сигнали» (`groups=group_f3d_manager`: `source_id`, `io_source_id`, `signal_state_id`, `signal_system_id`, `signal_alarms_id`, `signal_faults_id`, `signal_disabled_id`, `signal_sounders_id`, `signal_brigade_id`). Невидимі: `read_enabled`, `viewer_available`, `sim_available`, `compliance_dirty`. Чаттер (`mail.thread`, `mail.activity`) |
| V-02 | `view_f3d_fire_panel_kanban` | kanban `f3d.fire.panel` (Огляд) | `create="false"`, картка `t-name="card"` на всю ширину: велика плашка стану (клас за `state`: `text-bg-danger` alarm/prealarm, `text-bg-warning` fault/disabled, `text-bg-info` test, `text-bg-success` normal, `text-bg-secondary` unknown) з `state_text`; рядок «Зв'язок: `comm` · останнє показання `last_seen`»; лічильники «Зон `zone_count` · у тривозі `alarm_zone_count` · попереджень `warn_count`»; `systems_text`; «Ручні: найбільша відстань `compliance_mcp_max_m` м»; кнопки `action_view_zones` («Зони»), `action_view_events` («Журнал»), `action_f3d_show` («3D»), `action_recompute_compliance` (manager); клік — форма V-01 |
| V-01a | `view_f3d_fire_loop_list` / `_form` | `f3d.fire.loop` | list: `panel_id`, `number`, `name`, `from_x_m`, `to_x_m`, `device_count`, `detectors_count`, `mcp_count`, `sounders_count`, `flame_count`, `modules_count`, `state` (badge), `fault_since`, `request_id`; form: ті самі поля групами «Шлейф», «Пристрої», «Стан», вкладка `device_ids` (list readonly: `address`, `type`, `zone_id`, `state`) |
| V-03 | `view_f3d_fire_zone_kanban` | kanban `f3d.fire.zone` | `default_group_by="state"`, `records_draggable="false"`, `group_create="false"`, `quick_create="false"`, `create="false"`; картка: кольорова смуга `color` (`oe_kanban_color_<color>` через `kanban_color(record.color.raw_value)`), `code` (жирно), `name`, `kind_name`, «`detector_count` шт. · шлейф `loop_id`», плашка `state` (badge), `warn` → `<span class="text-warning">` з першими 120 символами `warning`, `dust_max_pct` % (`invisible="not dust_max_pct"`), `maintenance_request_name` (`text-danger`), плашка `compliance`, кнопка `action_f3d_show` («3D») |
| V-04 | `view_f3d_fire_zone_list`, `view_f3d_fire_zone_search` | list / search `f3d.fire.zone` | list (`create="false"`): `lsz_instance`, `code`, `name`, `zone_id`, `kind`, `loop_id`, `detector_count`, `n_required`, `state` (badge), `warn` (boolean), `dust_max_pct` (optional show), `compliance` (badge), `maintenance_request_name` (optional show), `stale` (optional hide), `area_m2` (optional hide), `spacing_m` (optional hide); декорації рядка: `decoration-danger="state in ('alarm','prealarm')"`, `decoration-warning="warn or state in ('fault','disabled')"`, `decoration-muted="state == 'unknown'"`. search: поля `code`, `name`, `zone_id`; фільтри `filter_alarm` «Тривога» (`state in (alarm,prealarm)`), `filter_fault` «Несправність» (`state = fault`), `filter_warn` «Попередження» (`warn = True`), `filter_disabled` «Вимкнено», `filter_test` «Тест», `filter_unknown` «Немає даних» (`state = unknown` або `stale`), `filter_noncompliant` «Не відповідає нормам» (`compliance in (warn,fail)`), «Архівні»; group by `group_state` (`state`), `kind`, `loop_id`, `compliance` |
| V-05 | `view_f3d_fire_zone_form` | form `f3d.fire.zone` | `<header>`: `action_recompute` («Перерахувати», manager), `action_create_device_signals` («Окремі сигнали пристроїв», manager, confirm «Створити сигнали стану й запиленості для всіх сповіщувачів зони?»), `action_f3d_show` («Показати в 3D»). Статбокс: `action_view_devices` (`detector_count`, «Сповіщувачі»), `action_view_events` (`event_count`, «Події 30 діб»), `action_view_requests` («Заявка», `invisible="not maintenance_request_id"`). `<sheet>`: `display` (title); група «Зона»: `code`, `name`, `zone_id`, `equipment_id`, `panel_id`, `loop_id`, `lsz_instance`, `kind`, `active`; група «Стан»: `state` (badge), `raw_state`, `state_ts`, `stale`, `warn`, `dust_max_pct`, `maintenance_request_id`; `warning` (full width, `invisible="not warning"`, клас `alert alert-warning`); група «Розстановка за ДБН»: `spacing_m`, `wall_m`, `x0`, `y0`, `x1`, `y1` (одна лінія «Контур, м»), `area_m2`, `z_m`, `detector_count`, `n_required`, `n_ok`, `cover_max_gap_m`, `cover_point`, `cover_ok`, `compliance` (badge); `compliance_note` (full width); `<div class="text-muted">` з довідкою README: «Цех понад 8 м: ДБН п. 7.2.10 рекомендує аспіраційні сповіщувачі; точкові під покрівлею — за табл. 7.2 до 12 м. Покриття — похідна перевірка A-06, не текст норми.» Вкладки: «Пристрої» (`device_ids` list readonly: `address`, `type`, `state`, `dust_pct`, `dust_state`, `monitor` (manager)), «Сигнали» (manager: `signal_id`, `dust_signal_id`) |
| V-06 | `view_f3d_fire_device_list`, `view_f3d_fire_device_search` | list / search `f3d.fire.device` | list (`create="false"`): `address`, `name`, `type`, `loop_id`, `zone_id`, `plant_zone_id` (optional show), `system_id` (optional hide), `lsp_instance` (optional hide), `x`, `y`, `z` (optional hide), `state` (badge), `reliability` (optional hide), `dust_pct`, `dust_state` (badge: `alarm` danger, `warn` warning, `ok` success), `monitor` (manager, optional show), `maintenance_request_id` (optional hide); search: поля `address`, `name`, `zone_id`, `plant_zone_id`; фільтри «Сповіщувачі» (`is_detector`), «Ручні» (`type=mcp`), «Оповіщувачі», «Полум'я», «Іскрогасіння» (`type in (spark_detector,spark_nozzle)`), «Люки» (`type=smoke_vent`), «Запиленість» (`dust_state in (warn,alarm)`), «Несправні» (`state in (fault,disabled)`), «Окремі сигнали» (`monitor`); group by `type`, `loop_id`, `zone_id`, `system_id` |
| V-07 | `view_f3d_fire_device_form` | form `f3d.fire.device` | `<header>`: `action_create_signals` («Окремі сигнали», manager, `invisible="monitor or not panel_id"`), `action_remove_signals` («Вимкнути окремі сигнали», manager, `invisible="not monitor"`), `action_f3d_show`. `<sheet>`: `name` (title); група «Пристрій»: `address`, `type`, `panel_id`, `loop_id`, `zone_id`, `plant_zone_id`, `system_id`, `smoke_zone_id`, `equipment_id`, `model`, `lsp_instance`, `seq`, `active`; група «Розміщення»: `x`, `y`, `z`, `side`, `heading_deg`, `note`; група «Стан»: `state` (badge), `raw_state`, `reliability`, `state_ts`, `dust_pct`, `dust_ts`, `dust_state`, `maintenance_request_id`; група «Сигнали» (manager): `monitor`, `state_signal_id`, `dust_signal_id` |
| V-08 | `view_f3d_fire_event_list`, `view_f3d_fire_event_search`, `view_f3d_fire_event_graph` | list / search / graph `f3d.fire.event` | list: `create="false"`, `edit="false"`, `delete="false"`, `default_order="ts desc"`; `<header>`: кнопка `action_ack` («Підтвердити», для вибраних); поля `ts`, `level` (badge: `alarm` danger, `warn` warning, `info` info), `kind`, `etype` (optional hide), `object_code`, `text`, `in_drill` (optional hide), `ack` (`widget="boolean"`), `ack_user_id` (optional hide), `request_id` (optional hide), `source` (optional hide); `decoration-bf="level == 'alarm' and not ack"`. search: поля `text`, `object_code`, `zone_id`, `drill_id`; фільтри `filter_alarm` «Тривоги» (`level=alarm`), `filter_warn` «Попередження», `filter_unack` «Непідтверджені тривоги» (`level=alarm`, `ack=False`), `filter_drill` «Під час навчань» (`in_drill`), `filter_today` «Сьогодні» (`ts >= context_today()` за часовим поясом користувача), `filter_7d` «7 діб»; group by `kind`, `level`, `object_code`, `ts:day`. graph: `type="bar"`, `ts` interval `day`, `kind`, міра `__count` |
| V-09 | `view_f3d_fire_event_form` | form `f3d.fire.event` | `create="false"`, `delete="false"`; `<header>`: `action_ack` («Підтвердити», `btn-primary`, `invisible="ack or level != 'alarm'"`), `action_open_object` («Відкрити об'єкт»), `action_f3d_show`; усі поля `readonly="1"`, крім `note`; групи «Подія» (`ts`, `level`, `kind`, `etype`, `object_code`, `text`, `message_text`, `raw_from`, `raw_to`, `source`, `in_drill`), «Зв'язки» (`panel_id`, `loop_id`, `zone_id`, `device_id`, `system_id`, `drill_id`, `signal_id`, `request_id`), «Підтвердження» (`ack`, `ack_user_id`, `ack_ts`, `note`). Окремий варіант `view_f3d_fire_event_form_manual` (для `action_add_comment`): `etype` прихований, `object_code`, `text`, `note`; кнопка «Зберегти» |
| V-10 | `view_f3d_fire_system_list` | list `f3d.fire.system` | `code`, `name`, `system_type`, `state` (badge), `state_text`, `count_today`, `detector_count` (optional show), `vent_count` (optional show), `pressure_bar` (optional show), `last_test_date`, `stale` (optional hide) |
| V-11 | `view_f3d_fire_system_form` | form `f3d.fire.system` | `<header>`: `action_f3d_show`, `action_view_events`. `<sheet>`: `name` (title); група «Стан»: `state` (badge), `state_text`, `state_ts`, `stale`, `count_today` (`invisible="system_type != 'spark'"`), `pressure_bar`, `pressure_min_bar` (`invisible="system_type != 'sprinkler'"`); група «Склад»: `code`, `system_type`, `equipment_id`, `vents_equipment_id` (smoke), `detector_count`, `nozzle_count` (spark), `vent_count`, `vent_area_m2`, `panels_needed`, `drive_current_a`, `panel_current_a` (smoke), `last_test_date`; група «Сигнали» (manager): `source_id`, `signal_state_id`, `signal_active_id`, `signal_fault_id`, `signal_water_id`, `signal_battery_id`, `signal_count_id`, `pressure_signal_id`; вкладки «Пристрої» (`device_ids`), «Димові зони» (`smoke_zone_ids`, `invisible="system_type != 'smoke'"`), «Примітка»; чаттер |
| V-12 | `view_f3d_fire_exit_list` / `_form` | `f3d.fire.exit` | list: `code`, `name`, `kind`, `side`, `x`, `y`, `width_m`, `route_count`, `nearest_exit_m`, `compliance` (badge); form: групи «Вихід» (`code`, `name`, `kind`, `side`, `x`, `y`, `width_m`, `equipment_id`, `active`), «Перевірка» (`width_ok`, `nearest_exit_m`, `compliance`, `compliance_note`); вкладка `route_ids` (list readonly: `zone_code`, `name`, `length_m`); кнопка «Показати в 3D». Редагування — `group_f3d_manager` (ACL) |
| V-13 | `view_f3d_fire_route_list` / `_form` / `_search` | `f3d.fire.route` | list: `zone_code`, `name`, `exit_id`, `length_m`, `norm_m`, `width_min_m`, `point_count` (optional hide), `compliance` (badge); `default_order="length_m desc"`; `decoration-danger="compliance == 'fail'"`; form: групи «Маршрут» (`code`, `name`, `zone_id`, `exit_id`, `length_m`, `width_min_m`, `active`), «Перевірка» (`norm_m`, `length_ok`, `width_ok`, `compliance`, `compliance_note`), `path_text` (ace json; редагування — лише з правом запису ACL, тобто `group_f3d_manager`); кнопка «Показати в 3D»; search: поля `zone_id`, `exit_id`; фільтр «Не відповідає»; group by `exit_id` |
| V-14 | `view_f3d_fire_smoke_zone_list` / `_form` | `f3d.fire.smoke.zone` | list: `code`, `name`, `area_m2`, `max_area_m2`, `vent_count`, `need_vents`, `vent_area_m2`, `compliance` (badge); form: групи «Зона» (`code`, `name`, `system_id`, `x0`…`y1`, `area_m2`, `active`), «Перевірка R-09» (`max_area_m2`, `area_ok`, `need_vents`, `vent_count`, `vent_area_m2`, `vents_ok`, `compliance`, `compliance_note`); вкладка `vent_ids` (list: `address`, `x`, `y`, `state`) |
| V-15 | `view_f3d_fire_norm_list` / `_form` / `_search` | `f3d.fire.norm` | list (`editable="bottom"` лише для manager через `edit` ACL; користувач — readonly): `group`, `key`, `name`, `value`, `value_set`, `unit`, `ref`; form: `name` (title), групи «Значення» (`key` — `readonly="id"`, `group`, `sequence`, `value`, `value_set`, `unit`, `active`), «Підстава» (`ref`, `note`, `sources` — текст з URL по рядку); search: поля `key`, `name`, `ref`; group by `group`; фільтр «Не задано» (`value_set=False`) |
| V-16 | `view_f3d_fire_drill_list`, `view_f3d_fire_drill_calendar`, `view_f3d_fire_drill_search` | `f3d.fire.drill` | list: `name`, `title`, `planned_ts`, `start_ts`, `zone_id`, `mode`, `origin` (optional show), `state` (badge: running danger, evaluating warning, done success, cancelled muted), `evac_time_s`, `evac_pct`, `result` (badge), `responsible_id` (optional hide); calendar: `date_start="planned_ts"`, `color="state"`, `mode="month"`, поля `zone_id`, `state`; search: поля `name`, `title`, `zone_id`; фільтри «Заплановані», «Тривають», «Оцінювання», «Завершені», «Мої» (`responsible_id = uid`), «Автоматичні» (`origin=panel`); group by `state`, `zone_id`, `planned_ts:month` |
| V-17 | `view_f3d_fire_drill_form` | form `f3d.fire.drill` | `<header>`: `action_plan` («Запланувати», `invisible="state != 'draft'"`), `action_start` («Почати», `btn-primary`, `invisible="state not in ('draft','planned') or mode == 'sim'"`), `action_start_sim` («Запустити на емуляторі», `btn-primary`, `invisible="state not in ('draft','planned') or mode != 'sim' or not sim_available"`), `action_stop` («Завершити», `btn-danger`, `invisible="state != 'running'"`), `action_rollcall` («Перекличка», `invisible="state != 'evaluating'"`), `action_close` («Закрити», `btn-primary`, `invisible="state != 'evaluating'"`), `action_cancel` («Скасувати», `invisible="state not in ('draft','planned','running')"`, confirm), `action_reset_draft` («У чернетку», `invisible="state != 'cancelled'"`), `action_print` («Протокол», `invisible="state not in ('evaluating','done')"`), `action_f3d_show` («Показати в 3D»); `statusbar_visible="draft,planned,running,evaluating,done"`. Над `<sheet>`: `alert-danger` `invisible="not real_alarm"` «Під час навчання прилад показав справжню тривогу»; `alert-info` `invisible="state != 'running'"` «Триває: <elapsed_s> с · кроки <steps_done>/<steps_total> · вийшли <evacuated_count>/<on_site_count>». `<sheet>`: `name` (title), `title`; група «План»: `mode`, `planned_ts`, `zone_id`, `device_id`, `template_id` (`readonly="state != 'draft'"`), `responsible_id`, `origin`, `company_id` (multi-company), `sim_run_ref` (`invisible="not sim_run_ref"`); група «Результат»: `start_ts`, `end_ts`, `duration_s`, `evac_time_s`, `time_limit_s`, `on_site_count`, `evacuated_count`, `present_count`, `missing_count`, `evac_pct`, `data_quality`, `passage_source`, `result_suggested`, `result` (обов'язковість перевіряє `action_close`, не атрибут поля); `<notebook>`: «Кроки» (`step_ids` list editable при `state in (draft, planned)`: `sequence` handle, `t_plan_s`, `who`, `text`, `auto_key` (optional hide), `done`, `t_fact_s`, `delay_s`, `done_by`, кнопки рядка `action_done_now` («Виконано», `invisible="done or parent.state not in ('running','evaluating')"`), `action_undo` («Скасувати відмітку», `invisible="done_by != 'manual'"`), `note`); «Люди» (`groups="factory3d_fire_safety.group_f3d_fire_drill,hr.group_hr_user"`; `person_ids` list readonly: `seq`, `employee_id`, `since`, `source`, `exit_ts`, `exit_s`, `exit_point`, `rollcall`, `status` (badge: evacuated success, present info, missing danger)); «Висновки» (`conclusions`, `remarks`, `print_names`); «Журнал» (`event_ids` list readonly: `ts`, `level`, `text`). Невидимі: `sim_available`, `real_alarm`. Чаттер з вкладеннями |
| V-18 | `view_f3d_fire_drill_rollcall_wizard_form` | form `f3d.fire.drill.rollcall.wizard` | `drill_id` (readonly); `line_ids` list editable (`create="false"`, `delete="false"`): `seq`, `employee_name` (`groups=group_f3d_fire_drill,hr.group_hr_user`), `present` (`widget="boolean_toggle"`); footer: `action_apply` («Зберегти перекличку», `btn-primary`), «Скасувати» (`special="cancel"`); дія `action_f3d_fire_drill_rollcall` (`target="new"`) |
| V-19 | `view_f3d_fire_drill_template_list` / `_form` | `f3d.fire.drill.template` | list: `sequence` (handle), `name`, `is_default`, `duration_s`, `default_zone_id`; form: `name`, `is_default`, `duration_s`, `default_zone_id`, `default_device_id`, `note`, `active`; `step_ids` list editable: `sequence` (handle), `t_plan_s`, `who`, `text`, `auto_key`; підказка «Плейсхолдери: {detector}, {zone}, {sounders}» |
| V-20 | `report_f3d_fire_evac_compliance` (`ir.actions.report`, `report_type="qweb-pdf"`, `model="f3d.fire.panel"`, `print_report_name="'Перевірка евакуації та розстановки — %s' % object.code"`) + шаблон `report_f3d_fire_evac_compliance_document` | QWeb | `web.html_container` + `web.external_layout`; розділи: 1) шапка — прилад, дата `compliance_ts` за Києвом, позначка «перераховано» або «потребує перерахунку» (`compliance_dirty`); 2) «Маршрути евакуації» — таблиця 32 рядків (`zone_code`, `name`, `exit_id.code`, `length_m`, `norm_m`, `width_min_m`, статус), найдовший шлях макета `evac_max_distance_m` у точці (`evac_worst_x`, `evac_worst_y`), норми з `ref` (`evac_distance_prod_B`, `evac_distance_polymer`); 3) «Виходи» — 12 рядків (`code`, `side`, `width_m`, `nearest_exit_m`, статус), `compliance_exit_pair_m` ≥ `compliance_exit_l_m`, підстава `evac_exits_min.ref`; 4) «Димові зони» — 8 рядків (`code`, `area_m2`, `max_area_m2`, `need_vents`, `vent_count`, статус) + `smoke_vent_area.note` (орієнтир, не норма); 5) «Розстановка сповіщувачів» — 33 рядки (`code`, `name`, `kind`, `detector_count`, `n_required`, `cover_max_gap_m`, `cover_point`, `compliance`) + «Зони цеху без сигналізації: Z-OFFICE, Z-SOC» (R-08); 6) «Ручні сповіщувачі» — `compliance_mcp_max_m` ≤ `mcp_spacing` у точці `compliance_mcp_point`; 7) «Оповіщувачі» — довідково `compliance_sounder_max_m` з текстом A-26; 8) перелік норм (`f3d.fire.norm`: `key`, `value unit`, `ref`). Дія друку — кнопка на V-01 і пункт меню `menu_f3d_fire_evac_report` (`ir.actions.server` `action_f3d_fire_evac_report`: `action = env['f3d.fire.panel'].search([], limit=1)._f3d_print_evac_report()`) |
| V-21 | `report_f3d_fire_drill` (`model="f3d.fire.drill"`, qweb-pdf, `print_report_name="'Протокол навчальної тривоги %s' % object.name"`) + `report_f3d_fire_drill_document` | QWeb | 1) реквізити (`name`, `title`, `mode`, `zone_id`, `device_id`, `planned_ts`, `start_ts`, `end_ts` — за Києвом, `responsible_id`); 2) таблиця кроків (`t_plan_s`, `who`, `text`, `t_fact_s`, `delay_s`, `done_by`); 3) евакуація: `on_site_count`, `evacuated_count`, `present_count`, `missing_count`, `evac_time_s` проти `time_limit_s`, `evac_pct`, `data_quality`, `passage_source`; 4) список людей — **лише** якщо `print_names` (номер, ПІБ, вийшов о, де, перекличка; FR-24), інакше рядок «Персональний список не друкується»; 5) `real_alarm`; 6) `result`, `conclusions`, `remarks`; 7) підписи «Відповідальний», «Інженер з пожежної безпеки» |
| V-22 | `report_f3d_fire_events` (`model="f3d.fire.event"`, qweb-pdf, друк вибраних записів зі списку V-08) + `report_f3d_fire_events_document` | QWeb | таблиця: час (Київ), рівень, категорія, об'єкт, подія, підтвердив/коли, коментар; шапка «Журнал подій пожежної безпеки з <min ts> по <max ts>, записів N» (Q-13) |
| V-23 | `view_f3d_zone_form_fire` | form inherit `factory3d_base.view_f3d_zone_form` | `//div[@name='button_box']` inside: статкнопка `action_view_fire_zones` (`f3d_fire_zone_count`, «Сигналізація», `fa-fire`); `//notebook` inside: `<page name="f3d_fire" string="Пожежна безпека">`: `f3d_fire_kind`, `f3d_fire_state` (badge), `f3d_evac_route_id`, `f3d_evac_exit_code`, `f3d_evac_length_m` |
| V-24 | `view_f3d_source_form_fire` | form inherit `factory3d_telemetry.view_f3d_source_form` | `//sheet` inside (останнім): `<div class="alert alert-danger" invisible="not f3d_fire_readonly">Джерело пожежної сигналізації: лише читання (D-07). Запис у прилад неможливий.</div>`; `//notebook` inside: `<page name="f3d_fire" string="Пожежна сигналізація" invisible="not f3d_fire_readonly">`: `f3d_fire_readonly` (readonly), `f3d_fire_consent_date`, `f3d_fire_consent_person`, `f3d_fire_consent_doc`, `f3d_fire_consent_attachment_id` (many2one з `domain="[('res_model','=','f3d.source'),('res_id','=',id)]"` — скан спершу додається вкладенням у чаттер джерела, потім обирається тут); поле `write_enabled` отримує `readonly="f3d_fire_readonly"` (`xpath //field[@name='write_enabled']` `position="attributes"`) |
| V-25 | `view_maintenance_request_form_fire` | form inherit `factory3d_telemetry.view_maintenance_request_form_f3d` | після `//field[@name='f3d_signal_id']`: `f3d_fire_zone_id`, `f3d_fire_device_id`, `f3d_fire_event_id` (усі `invisible="not f3d_fire_zone_id and not f3d_fire_device_id and not f3d_fire_event_id"`), кнопка `action_f3d_fire_open_zone` у `button_box` («Зона сигналізації», `invisible="not f3d_fire_zone_id"`) |
| V-26 | `res_config_settings_view_form_f3d_fire` | inherit `base.res_config_settings_view_form` | `//form` inside: `<app data-string="Пожежна безпека" string="Пожежна безпека" name="factory3d_fire_safety" groups="factory3d_base.group_f3d_manager">`; блоки: «Обробка сигналів» (`f3d_fire_read_enabled` — `groups=group_f3d_admin`, `f3d_fire_comm_stale_after_s`, `f3d_fire_comm_lost_after_s`, текст «Запис у прилад не налаштовується — рішення D-07»), «Запиленість сповіщувачів» (`f3d_fire_dust_warn_pct`, `f3d_fire_dust_alarm_pct`), «Норми» (`f3d_fire_polymer_panels` з підказкою п. 8.2.11, `f3d_fire_cover_tol_m`), «Навчальні тривоги» (`f3d_fire_drill_time_limit_s`, `f3d_fire_drill_auto_create`, `f3d_fire_drill_match_window_min`, `f3d_fire_drill_auto_stop_s`, `f3d_fire_drill_sim_duration_s`), «Сповіщення й заявки» (`f3d_fire_alert_group_id`, `f3d_fire_event_ack_required`, `f3d_fire_team_id`), «3D» (`f3d_fire_viewer_devices`) |
| V-27 | `view_f3d_fire_bacnet_device_wizard_form` | form `f3d.fire.bacnet.device.wizard` | `panel_id` (readonly), `old_instance`, `new_instance`, `signal_count`; `alert-warning` «Змінюються лише адреси сигналів; запис у прилад не виконується»; footer `action_apply` («Змінити», `btn-primary`, confirm), «Скасувати» |

Меню й дії (`views/menus.xml`; CB-09: батько `factory3d_base.menu_f3d_root`, sequence 85). Дії `ir.actions.act_window`
мають `context`/`domain`, як у таблиці; xml-id дій — `action_f3d_fire_<що>`.

| XML-id меню | Назва | Батько | seq | Групи | Дія (модель, `view_mode`, контекст) |
|---|---|---|---|---|---|
| `menu_f3d_fire_root` | Пожежна безпека | `factory3d_base.menu_f3d_root` | 85 | `group_f3d_user` | — |
| `menu_f3d_fire_overview` | Огляд | `menu_f3d_fire_root` | 10 | `group_f3d_user` | `action_f3d_fire_overview` (`f3d.fire.panel`, `kanban,form`) |
| `menu_f3d_fire_zone` | Зони сигналізації | `menu_f3d_fire_root` | 20 | `group_f3d_user` | `action_f3d_fire_zone` (`f3d.fire.zone`, `kanban,list,form`; `{'search_default_group_state': 1}`) |
| `menu_f3d_fire_device` | Пристрої | `menu_f3d_fire_root` | 30 | `group_f3d_user` | `action_f3d_fire_device` (`list,form`; `{'search_default_group_type': 1}`) |
| `menu_f3d_fire_event` | Журнал подій | `menu_f3d_fire_root` | 40 | `group_f3d_user` | `action_f3d_fire_event` (`list,form,graph`; `{'search_default_filter_7d': 1}`) |
| `menu_f3d_fire_system` | Системи | `menu_f3d_fire_root` | 50 | `group_f3d_user` | `action_f3d_fire_system` (`list,form`) |
| `menu_f3d_fire_evac` | Евакуація | `menu_f3d_fire_root` | 60 | `group_f3d_user` | — |
| `menu_f3d_fire_exit` | Виходи | `menu_f3d_fire_evac` | 10 | `group_f3d_user` | `action_f3d_fire_exit` (`list,form`) |
| `menu_f3d_fire_route` | Маршрути | `menu_f3d_fire_evac` | 20 | `group_f3d_user` | `action_f3d_fire_route` (`list,form`) |
| `menu_f3d_fire_smoke_zone` | Димові зони | `menu_f3d_fire_evac` | 30 | `group_f3d_user` | `action_f3d_fire_smoke_zone` (`list,form`) |
| `menu_f3d_fire_evac_report` | Звіт перевірки | `menu_f3d_fire_evac` | 40 | `group_f3d_user` | `action_f3d_fire_evac_report` (`ir.actions.server`, V-20) |
| `menu_f3d_fire_drill` | Навчальні тривоги | `menu_f3d_fire_root` | 70 | `group_f3d_user` | `action_f3d_fire_drill` (`list,form,calendar`; без контексту) |
| `menu_f3d_fire_norm` | Норми | `menu_f3d_fire_root` | 80 | `group_f3d_user` | `action_f3d_fire_norm` (`list,form`; `{'search_default_group_group': 1}`) |
| `menu_f3d_fire_config` | Налаштування | `menu_f3d_fire_root` | 90 | `group_f3d_manager` | — |
| `menu_f3d_fire_template` | Шаблони навчань | `menu_f3d_fire_config` | 10 | `group_f3d_manager` | `action_f3d_fire_drill_template` (`list,form`) |
| `menu_f3d_fire_loop` | Шлейфи | `menu_f3d_fire_config` | 20 | `group_f3d_manager` | `action_f3d_fire_loop` (`list,form`) |
| `menu_f3d_fire_settings` | Параметри | `menu_f3d_fire_config` | 30 | `group_f3d_manager` | `action_f3d_fire_settings` (`res.config.settings`, `form`, `target='inline'`, `{'module': 'factory3d_fire_safety'}`) |

Додатково: `menu_f3d_fire_maint_requests` «Заявки пожежної безпеки» під `maintenance.menu_m_request` (seq 50,
`group_f3d_user`): `maintenance.request`, `list,form`, `domain=['|', ('f3d_fire_zone_id','!=',False), ('f3d_signal_id.module','=','fire_safety')]`.
Методи дій на панелі: `action_add_comment(self)` → `act_window` `f3d.fire.event`, `view_id=view_f3d_fire_event_form_manual`,
`target='new'`, `context={'default_etype': 'manual', 'default_level': 'info', 'default_source': 'manual',
'default_object_code': code, 'default_panel_id': id}`; `_f3d_print_evac_report(self)` → якщо `compliance_dirty` —
спершу `action_recompute_compliance()`, потім `env.ref('factory3d_fire_safety.report_f3d_fire_evac_compliance').report_action(self)`.

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

Позначення груп: `U` = `factory3d_base.group_f3d_user`, `D` = `factory3d_fire_safety.group_f3d_fire_drill`,
`M` = `factory3d_base.group_f3d_manager`, `A` = `factory3d_base.group_f3d_admin`, `H` = `hr.group_hr_user`.

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_f3d_fire_norm_user,f3d.fire.norm user,model_f3d_fire_norm,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_norm_manager,f3d.fire.norm manager,model_f3d_fire_norm,factory3d_base.group_f3d_manager,1,1,1,0
access_f3d_fire_norm_admin,f3d.fire.norm admin,model_f3d_fire_norm,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_fire_panel_user,f3d.fire.panel user,model_f3d_fire_panel,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_panel_manager,f3d.fire.panel manager,model_f3d_fire_panel,factory3d_base.group_f3d_manager,1,1,0,0
access_f3d_fire_panel_admin,f3d.fire.panel admin,model_f3d_fire_panel,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_fire_loop_user,f3d.fire.loop user,model_f3d_fire_loop,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_loop_manager,f3d.fire.loop manager,model_f3d_fire_loop,factory3d_base.group_f3d_manager,1,1,0,0
access_f3d_fire_loop_admin,f3d.fire.loop admin,model_f3d_fire_loop,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_fire_zone_user,f3d.fire.zone user,model_f3d_fire_zone,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_zone_manager,f3d.fire.zone manager,model_f3d_fire_zone,factory3d_base.group_f3d_manager,1,1,0,0
access_f3d_fire_zone_admin,f3d.fire.zone admin,model_f3d_fire_zone,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_fire_device_user,f3d.fire.device user,model_f3d_fire_device,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_device_manager,f3d.fire.device manager,model_f3d_fire_device,factory3d_base.group_f3d_manager,1,1,0,0
access_f3d_fire_device_admin,f3d.fire.device admin,model_f3d_fire_device,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_fire_event_user,f3d.fire.event user,model_f3d_fire_event,factory3d_base.group_f3d_user,1,1,0,0
access_f3d_fire_event_drill,f3d.fire.event drill,model_f3d_fire_event,factory3d_fire_safety.group_f3d_fire_drill,1,1,1,0
access_f3d_fire_system_user,f3d.fire.system user,model_f3d_fire_system,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_system_manager,f3d.fire.system manager,model_f3d_fire_system,factory3d_base.group_f3d_manager,1,1,0,0
access_f3d_fire_system_admin,f3d.fire.system admin,model_f3d_fire_system,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_fire_smoke_zone_user,f3d.fire.smoke.zone user,model_f3d_fire_smoke_zone,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_smoke_zone_manager,f3d.fire.smoke.zone manager,model_f3d_fire_smoke_zone,factory3d_base.group_f3d_manager,1,1,1,0
access_f3d_fire_smoke_zone_admin,f3d.fire.smoke.zone admin,model_f3d_fire_smoke_zone,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_fire_exit_user,f3d.fire.exit user,model_f3d_fire_exit,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_exit_manager,f3d.fire.exit manager,model_f3d_fire_exit,factory3d_base.group_f3d_manager,1,1,1,0
access_f3d_fire_exit_admin,f3d.fire.exit admin,model_f3d_fire_exit,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_fire_route_user,f3d.fire.route user,model_f3d_fire_route,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_route_manager,f3d.fire.route manager,model_f3d_fire_route,factory3d_base.group_f3d_manager,1,1,1,0
access_f3d_fire_route_admin,f3d.fire.route admin,model_f3d_fire_route,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_fire_drill_user,f3d.fire.drill user,model_f3d_fire_drill,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_drill_drill,f3d.fire.drill drill,model_f3d_fire_drill,factory3d_fire_safety.group_f3d_fire_drill,1,1,1,1
access_f3d_fire_drill_step_user,f3d.fire.drill.step user,model_f3d_fire_drill_step,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_drill_step_drill,f3d.fire.drill.step drill,model_f3d_fire_drill_step,factory3d_fire_safety.group_f3d_fire_drill,1,1,1,1
access_f3d_fire_drill_person_drill,f3d.fire.drill.person drill,model_f3d_fire_drill_person,factory3d_fire_safety.group_f3d_fire_drill,1,1,1,1
access_f3d_fire_drill_person_hr,f3d.fire.drill.person hr,model_f3d_fire_drill_person,hr.group_hr_user,1,0,0,0
access_f3d_fire_drill_template_user,f3d.fire.drill.template user,model_f3d_fire_drill_template,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_drill_template_manager,f3d.fire.drill.template manager,model_f3d_fire_drill_template,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_fire_drill_template_step_user,f3d.fire.drill.template.step user,model_f3d_fire_drill_template_step,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_fire_drill_template_step_manager,f3d.fire.drill.template.step manager,model_f3d_fire_drill_template_step,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_fire_drill_rollcall_wizard_drill,f3d.fire.drill.rollcall.wizard drill,model_f3d_fire_drill_rollcall_wizard,factory3d_fire_safety.group_f3d_fire_drill,1,1,1,1
access_f3d_fire_drill_rollcall_line_drill,f3d.fire.drill.rollcall.line drill,model_f3d_fire_drill_rollcall_line,factory3d_fire_safety.group_f3d_fire_drill,1,1,1,1
access_f3d_fire_bacnet_device_wizard_admin,f3d.fire.bacnet.device.wizard admin,model_f3d_fire_bacnet_device_wizard,factory3d_base.group_f3d_admin,1,1,1,1
```

42 рядки. `f3d.fire.event`: `perm_unlink=0` для всіх (A-12); `write` користувача обмежений кодом (M-05, A-33);
`create` — лише `D` і лише `etype='manual'` (M-05). `f3d.fire.drill.person` — немає рядка для `U` (FR-24): читання
лише `D` і `H`. Абстрактні `f3d.fire.passage.source*` і провайдери міст-модуля рядків не потребують. Нові ACL на
`f3d.source`, `f3d.signal`, `f3d.command`, `maintenance.request`, `f3d.zone` не додаються (власники — telemetry, base,
maintenance).

### 4.2 Групи (`security/security.xml`)

```xml
<record id="privilege_f3d_fire" model="res.groups.privilege">
    <field name="name">Завод 3D: пожежна безпека</field>
    <field name="category_id" ref="factory3d_base.module_category_factory3d"/>
    <field name="sequence">85</field>
</record>
<record id="group_f3d_fire_drill" model="res.groups">
    <field name="name">Ведення навчальних тривог</field>
    <field name="privilege_id" ref="privilege_f3d_fire"/>
    <field name="sequence">10</field>
    <field name="implied_ids" eval="[Command.link(ref('factory3d_base.group_f3d_user'))]"/>
    <field name="comment">Інженер з пожежної безпеки: навчання, перекличка, коментарі в журналі, персональні дані навчань.</field>
</record>
<record id="factory3d_base.group_f3d_manager" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_f3d_fire_drill'))]"/>
</record>
```

Ланцюжок: `U ⊂ D ⊂ M ⊂ A ⊂ base.group_system` (CB-10). Група охорони для активностей — параметр `alert_group_xmlid`
(на тесті `U`; на проді — група access `factory3d_access.group_f3d_access_security`, якщо встановлено, CA-08).

### 4.3 Record rules (`security/security.xml`, глобальні)

| XML-id | Модель | Домен |
|---|---|---|
| `f3d_fire_panel_rule_company` | `f3d.fire.panel` | `[('company_id','in',company_ids)]` |
| `f3d_fire_drill_rule_company` | `f3d.fire.drill` | `[('company_id','in',company_ids)]` |
| `f3d_fire_drill_person_rule_company` | `f3d.fire.drill.person` | `[('drill_id.company_id','in',company_ids)]` |

Довідники (зони, пристрої, норми, маршрути) — без компанії (одна будівля, як надвірні зони base).

### 4.4 Захист полів і стоп-крани

- `f3d.fire.device.monitor` — `groups="factory3d_base.group_f3d_manager"`; `action_create_signals`/`action_remove_signals`
  перевіряють групу в коді (`AccessError("Окремі сигнали пристроїв вмикає менеджер «Завод 3D».")`).
- `f3d.fire.drill.person_ids` — `groups="…group_f3d_fire_drill,hr.group_hr_user"`; провайдери й звіт без
  `print_names` бачать лише кількості.
- `f3d_fire_read_enabled` у налаштуваннях — `groups=group_f3d_admin`; `action_set_bacnet_device` і M-19 — лише `A`.
- Стоп-кран читання `factory3d.fire_safety.read_enabled` (§5.1). Стоп-крана запису немає і він не читається (A-03);
  заборона запису — M-15 (діє під `sudo`). Токенів модуль не має (усі ендпоінти — telemetry/viewer зі своїми токенами).

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)

| key (`factory3d.fire_safety.*`) | value | XML-id | Примітка |
|---|---|---|---|
| `read_enabled` | `True` | `param_read_enabled` | хук §5.4 п. 1 перезаписує за CB-10: `environment == 'test'` → `True`, інакше `False` |
| `comm_stale_after_s` | `90` | `param_comm_stale_after_s` | R-12 |
| `comm_lost_after_s` | `180` | `param_comm_lost_after_s` | R-12 |
| `dust_warn_pct` | `80` | `param_dust_warn_pct` | R-13 |
| `dust_alarm_pct` | `90` | `param_dust_alarm_pct` | R-13 |
| `polymer_panels` | `False` | `param_polymer_panels` | R-05, Q-04 |
| `cover_tol_m` | `0.5` | `param_cover_tol_m` | R-02, A-06 |
| `drill_time_limit_s` | `300` | `param_drill_time_limit_s` | R-16, Q-03 |
| `drill_auto_create` | `True` | `param_drill_auto_create` | R-18 |
| `drill_match_window_min` | `30` | `param_drill_match_window_min` | R-18 |
| `drill_auto_stop_s` | `120` | `param_drill_auto_stop_s` | R-16 п. 7 |
| `drill_sim_duration_s` | `300` | `param_drill_sim_duration_s` | FR-23 |
| `alert_group_xmlid` | `factory3d_base.group_f3d_user` | `param_alert_group_xmlid` | FR-11 |
| `team_id` | `` (порожньо) | `param_team_id` | хук: id «Служба головного механіка» (демо 2), інакше порожньо (Q-02) |
| `viewer_devices` | `False` | `param_viewer_devices` | R-20 |
| `event_ack_required` | `True` | `param_event_ack_required` | M-05 |
| `migration_report` | `{}` | `param_migration_report` | §5.4 п. 9 |

Параметра `factory3d.fire_safety.write_enabled` немає (A-03); тест AC-31 перевіряє, що модуль не створює й не
читає його (`grep -rn "fire_safety.write_enabled" odoo_addons/factory3d_fire_safety` — лише в тестах і `neutralize.sql`).

### 5.2 Генератор `tools/gen_data.py` і data-файли з макета

Запуск (розробник, з кореня репозиторію): `python3 odoo_addons/factory3d_fire_safety/tools/gen_data.py --root .`
Читає (import/JSON): `plant/fire.py` (`detectors()`, `call_points()`, `sounders()`, `FLAME`, `SPARK_DETECTORS`,
`SPARK_EXTINGUISH`, `DUCT_TOP`, `LOOPS`, `BOILER_HOUSE`, `Z_DET`, `Z_BOILER`, `FACP_POS`, `load_rules()`),
`plant/infra.py` (`smoke_zone_vents()`, `ROOF_Z`), `plant/evacuation.py` (`EXITS`, `WALLS`, `DOOR_W`),
`plant/evac_routes.json`, `plant/fire_rules.json`, `plant/evac_rules.json`, `plant/layout.py` (`ZONES`),
`dist/odoo_demo.json` (`fire.groups` — порядок і назви, `fire.loops` — модулі, `evacuation.drill_steps`).
Пише детерміновано (сортування, без часових міток, `\n`, числа — `round(v, 2)` без зайвих нулів). Самоперевірки
(виняток `SystemExit(2)` з текстом): кількості 33 зон / 212 сповіщувачів (128 `smoke`, 82 `multi`, 2 `heat`) / 36 ручних
/ 41 оповіщувач / 3 полум'я / 4 датчики іскор / 3 форсунки / 44 люки / 8 димових зон / 12 виходів / 32 маршрути / 8
кроків; суми `fire.loops` макета (64/68/34/46 сповіщувачів; 10/10/7/9 ручних; 11/13/7/10 оповіщувачів) збігаються з
підрахунком за `loop_of`; унікальність адрес і LSP; невідомий ключ у JSON норм → помилка; кожен маршрут перетинає
`WALLS` лише в прорізах (A-25).

| Файл | Рядків | XML-id (slug = `plant/odoo_rpc.key(...)`) | Зміст і джерело |
|---|---|---|---|
| `data/f3d_fire_norm.csv` | 27 | `norm_<key>` | `id,key,name,group,sequence,value,value_set,unit,ref,note,sources` — Додаток D; `sources` — URL через `\n` |
| `data/f3d_fire_panel.xml` | 1 + 4 | `panel_facp_1`; `loop_1`…`loop_4` | прилад: `name` «Приймально-контрольний прилад», `code` `FACP-1`, `zone_id` ref `factory3d_base.zone_z_office`, `x` 97.2, `y` 58.25 (`FACP_POS`), `evac_max_distance_m` 45.3, `evac_worst_x` 32.25, `evac_worst_y` 33.75 (`evac_routes.json`); шлейфи: `number`, `from_x_m`/`to_x_m` з `LOOPS` (0/42, 42/92, 92/122, 122/151), `modules_count` 0/4/0/0 (`fire.loops[n].modules`) |
| `data/f3d_fire_zone.csv` | 33 | `fire_zone_<slug(code)>` (`fire_zone_fa_cut`) | `id,code,name,panel_id:id,loop_id:id,zone_id:id,lsz_instance,kind,spacing_m,wall_m,x0,y0,x1,y1,z_m`; порядок і `lsz_instance` = порядок `fire.groups` (Додаток A.1); `zone_id:id` = `factory3d_base.zone_<slug(Z-…)>` (`FA-BOILER` → `factory3d_base.zone_z_boiler`); `wall_m` 4.4 (smoke/multi), 3.2 (heat); контур — `layout.ZONES`, для котельні — `BOILER_HOUSE` |
| `data/f3d_fire_system.xml` | 3 | `system_spark_1`, `system_smoke_ctrl`, `system_sprinklers` | `code`, `name`, `sequence`, `system_type`, `panel_id`, `last_test_date`, `drive_current_a`/`panel_current_a`; `source_id` і `signal_*` тут **не** задаються — їх ставить блок прив'язок у кінці `f3d_signal_data.xml` (джерела й сигнали завантажуються пізніше за маніфестом §1) |
| `data/f3d_fire_smoke_zone.csv` | 8 | `smoke_zone_<slug>` (`smoke_zone_sz_1`) | `id,code,name,system_id:id,x0,y0,x1,y1` з `infra.SMOKE_ZONES` |
| `data/f3d_fire_device.csv` | 343 | `dev_<slug(address)>` (`dev_2_fac_07`) | `id,address,type,panel_id:id,loop_id:id,zone_id:id,system_id:id,smoke_zone_id:id,lsp_instance,seq,x,y,z,side,heading_deg,note`; порядок: сповіщувачі за `lsz_instance`, `nn`; ручні в порядку `call_points()`; оповіщувачі — `sounders()`; полум'я; датчики іскор; форсунки; люки (`SV-01…44` у порядку `smoke_zone_vents()`); адреси й LSP — R-23, Додаток A |
| `data/f3d_fire_exit.csv` | 12 | `exit_<slug>` (`exit_ex_s1`) | `id,code,name,kind,x,y,side,width_m,note` з `evacuation.EXITS`, `DOOR_W` |
| `data/f3d_fire_route.xml` | 32 | `route_<slug(zone)>` (`route_z_cut`) | `code` `EVAC-<zone[2:]>`, `name`, `zone_id` ref base, `exit_id` ref, `length_m`, `path` (`eval="[[49.75, 22.25], [50.25, 0.25]]"`), `width_min_m` (A-25: 1.2 для всіх) |
| `data/f3d_fire_drill_template.xml` | 1 + 8 | `drill_template_default`, `drill_template_step_01…08` | §2 M-11c; `default_zone_id` ref `fire_zone_fa_cnc`, `default_device_id` ref `dev_2_cnc_05` |
| `data/f3d_source_data.xml` (`noupdate="1"`) | 2 | `source_bacnet_facp_1`, `source_mb_u85_io6` | §5.3 |
| `data/f3d_signal_data.xml` | 52 + прив'язки | `sig_<slug(code)>` (`sig_fire_groups_fa_cut_state`) | `<data noupdate="1">`: 52 записи `f3d.signal` за Додатком B (`address`, `states`, `alarm_states` — через `eval`); `<data>` (оновлюються): `signal_*` на `panel_facp_1`, `loop_<n>.signal_id`, `fire_zone_*.signal_id`, `system_*.signal_*`/`source_id`, `panel_facp_1.source_id/io_source_id` |
| `data/mail_activity_type.xml` | 1 | `mail_act_fire_alarm` | `name` «Пожежна тривога», `icon` `fa-fire`, `res_model` `f3d.fire.panel`, `delay_count` 0, `decoration_type` `danger`, `category` `default` |
| `data/ir_sequence.xml` | 1 | `seq_f3d_fire_drill` | `code` `f3d.fire.drill`, `prefix` `DRILL/%(year)s/`, `padding` 4, `company_id` False |
| `data/ir_cron.xml` | 3 | §6 | |

Кількості після установки на чистій базі (без
`factory3d_base`-міграції обладнання): `f3d.fire.norm` 27, `.panel` 1, `.loop` 4, `.zone` 33, `.device` 343
(128 smoke, 82 multi, 2 heat, 36 mcp, 41 sounder, 3 flame, 4 spark_detector, 3 spark_nozzle, 44 smoke_vent),
`.system` 3, `.smoke.zone` 8, `.exit` 12, `.route` 32, `.drill.template` 1 (кроків 8), `f3d.source` модуля 2,
`f3d.signal` модуля 52 (+1 запиленість від хука).

### 5.3 `data/f3d_source_data.xml` (`noupdate="1"`)

| XML-id | `code` | `name` | `type` | `params` | Інше |
|---|---|---|---|---|---|
| `source_bacnet_facp_1` | `BACNET-FACP-1` | «Cerberus PRO FACP-1 (BACnet, лише читання)» | `bacnet_ip` | `{"host": "iot-sim", "port": 47808, "read_only": true, "timeout_s": 5, "rpm": true, "rpm_max": 50}` | `collector_id` ref `factory3d_telemetry.collector_main`; `module='fire_safety'`; `read_enabled=True` (хук → CB-10); `write_enabled=False`; `f3d_fire_readonly=True`; `period_s_default=10` |
| `source_mb_u85_io6` | `MB-U85-IO6` | «ADAM-6050 IO-6: GreCon BS 7 і D+H (лише читання)» | `modbus_tcp` | `{"host": "iot-sim", "port": 502, "unit": 85, "timeout_s": 3, "retries": 1}` | те саме; `period_s_default=2` |

На проді (інструкція ARCH 4.1) змінюються лише `params.host`/`port` (і device instance — M-19); код не змінюється.

### 5.4 `post_init_hook(env)` — кроки, ідемпотентність, очікувані кількості

`hooks.run_all(env) -> dict` виконує кроки; `post_init_hook = run_all + запис звіту`; усе в транзакції установки;
виняток на кроках 1–6 відкочує установку; кроки 7–8 — у `savepoint` (помилка → `partial` і WARNING). Логер
`odoo.addons.factory3d_fire_safety.hooks`, INFO на крок з лічильниками. Повторний запуск — лише через «Оновити
модуль» (окремої дії немає).

| # | Функція | Що робить | Ідемпотентність | Копія демо (14.10) | Чиста база |
|---|---|---|---|---|---|
| 1 | `params(env)` | лише якщо `migration_report == '{}'` (перша установка): `read_enabled = (factory3d.base.environment == 'test')`; `team_id` = id `maintenance.team` з `name='Служба головного механіка'` або порожньо | повтор — нічого | `read_enabled=True`, `team_id=2` | `True`, порожньо |
| 2 | `equipment.link(env)` | `E = env['maintenance.equipment'].search_f3d`; прилад ← `FACP-1`; кожна зона ← `E(code)`; пристрої: детектори ← обладнання своєї зони, `mcp` ← `FA-MCP`, `sounder` ← `FA-SND`, `flame` ← `FA-FLAME`, `spark_*` ← `SPARK-1`, `smoke_vent` ← `SMOKE-VENTS`; системи ← `SPARK-1`, `SMOKE-CTRL` (+ `vents_equipment_id` ← `SMOKE-VENTS`), `SPRINKLERS`; виходи ← `EXITS`; джерела: `BACNET-FACP-1.equipment_id` ← `FACP-1`, `MB-U85-IO6` ← `SPARK-1`; сигнали — R-24 (правило коду → обладнання); `pressure_signal_id` спринклерів ← `f3d.signal` з `code='equipment/SPRINKLERS/pressure_bar'` (якщо є). `LPS` не чіпається | перезапис тими ж значеннями | `linked: 42` (різних одиниць), `missing: 0`, `devices_linked: 343`, `signals_linked: 52`, `pressure_signal: True` | `linked: 0`, `missing: 42` (WARNING зі списком кодів), `pressure_signal: False` |
| 3 | `signals.dust(env)` | `sig = f3d.signal.search([('code','=','fire/groups/FA-FAC/dust')], active_test=False)`; є (telemetry, `origin='sim_data'`) → `write({source_id: BACNET-FACP-1, address: {"device":200,"object":"AV","instance":21607,"mode":"poll"}, period_s: 600, store_period_s: 3600, module: 'fire_safety', kind: 'gauge', unit: '%', warn_high: 80, warn_high_on: True, alarm_high: 90, alarm_high_on: True, hysteresis: 1.8, decimals: 1, alarm_title: "Очистити сповіщувач 2.FAC.07 (Дільниця фасадів МДФ): запиленість {value} % при нормі до {threshold}", write_enabled: False, equipment_id: FA-FAC})` без зміни `last_*`; немає → `create` з тими самими полями, `code`, `name` «Запиленість сповіщувача 2.FAC.07», `origin='catalog'` (**без** xml-id — сигнал переживає деінсталяцію); далі `fire_zone_fa_fac.dust_signal_id = dev_2_fac_07.dust_signal_id = sig`, `dev_2_fac_07.monitor = True`, `dev_2_fac_07._set_dust(sig.last_value, sig.last_ts)` якщо `last_ts` | за `code` | `dust_signal: reused`, `dust_pct: 86.1` (стан `warn`) | `dust_signal: created`, `dust_pct: None` |
| 4 | `requests.link(env)` | заявки з `f3d_signal_id` ∈ сигналів модуля і порожнім `f3d_fire_zone_id` → R-22 | за порожнім полем | `requests_linked: 1` (id 5 → `FA-FAC`, `2.FAC.07`) | 0 |
| 5 | `events.demo(env)` | 4 події макета (`fire.events`) — таблиця нижче — через `f3d.fire.event._log(..., source='demo', key='demo:<n>')` | за `dedup_key` | `events_demo: 4` (повторно 0) | 4 |
| 6 | `drills.demo(env)` | якщо немає навчання з `origin='demo'`: `create({title: "Навчальна тривога — демо (Присадка)", origin: 'demo', mode: 'tabletop', zone_id: FA-CNC, device_id: 2.CNC.05, planned_ts = start_ts: 2026-09-30 07:00:00 UTC (10:00 Київ), end_ts: +300 с, state: 'done', result: 'ok', conclusions: "Демо-запис: показує структуру протоколу навчання.", passage_source: 'demo', evac_time_s: 240})`; кроки з шаблону з `done=True`, `t_fact_s=t_plan_s`, `done_by='auto'`; люди (A-30): працівники з `f3d_code` (сортування за `f3d_code`), `k`-й (1…N) — `since = start − 3 год`, `exit_ts = start + round(240·k/N)` с, `exit_point="Демо"`, `source='demo'` | за `origin='demo'` | `drills_demo: 1`, людей 35, `evac_time_s 240`, `evac_pct 100.0` | `drills_demo: 1`, людей 0 (`evac_pct 100.0`, `data_quality='partial'`) |
| 7 | `sync.first(env)` | `env['f3d.fire.panel']._f3d_fire_sync(full=True)` (R-19); панель без показань → `comm='lost'` без події й заявки (`first_sync=True`, R-12 п. 5) | — | зони 33 `unknown`, крім `FA-FAC.warn=True` (запиленість); `comm='lost'` | так само без запиленості |
| 8 | `compliance(env)` | `panel.action_recompute_compliance()` (R-01…R-09) | — | `zones_ok: 33`, `mcp_max_m: 26.9`, `routes_ok: 32`, `exits_ok: True`, `smoke_ok: 8`, `missing_zones: "Z-OFFICE, Z-SOC"` | `routes_ok: 32` (маршрути посилаються на зони base з data), решта так само |
| 9 | `report.write(env, report)` | `migration_report = json.dumps({state, ts, ...лічильники кроків}, ensure_ascii=False)`; `state = 'done'` якщо `missing == 0`, інакше `partial` | перезапис | `state: done` | `state: partial` |

Демо-події (крок 5; час макета за Києвом → UTC):

| key | `ts` UTC | `etype` | `level` | `object_code` | зв'язки | `text` (дослівно з `fire.events`) |
|---|---|---|---|---|---|---|
| `demo:1` | 2026-10-12 05:47:00 | `spark` | warn | `SPARK-1` | `system_spark_1` | Іскрогасіння: іскру виявлено на магістралі аспірації над лінією A, гасіння 0,6 с, лінію не зупиняли. |
| `demo:2` | 2026-10-12 06:58:00 | `dust_warn` | warn | `2.FAC.07` | `fire_zone_fa_fac`, `dev_2_fac_07` | Попередження про запиленість: сповіщувач 2.FAC.07 (дільниця фасадів, шліфування). |
| `demo:3` | 2026-10-12 04:00:00 | `info` | info | `FACP-1` | `panel_facp_1` | Щотижнева перевірка оповіщувачів: усі 4 шлейфи — норма. |
| `demo:4` | 2026-10-11 20:10:00 | `info` | info | `SPARK-1` | `system_spark_1` | Самотест іскрогасіння: датчики й клапан гасіння — норма. |

`scene_code` демо-подій: `SPARK-1`, `FA-FAC`, `FACP-1`, `SPARK-1` — як `fire.events[*].code` макета.

### 5.5 `uninstall_hook(env)`

1. `_logger.warning("Видаляються журнал подій (%d) і навчання (%d) пожежної безпеки; експортуйте протоколи (інструкція 4.6)")`.
2. Сигнал запиленості (крок 3; на демо — xml-id telemetry, на чистій базі — без xml-id): `write({'source_id': False,
   'address': {}})` — переживає деінсталяцію (джерело `BACNET-FACP-1` видаляється з даними модуля), `module` лишається
   `fire_safety` (класифікатор telemetry CT-09); 52 сигнали з xml-id модуля Odoo видаляє як data (показання — каскадом
   telemetry).
3. `ir.config_parameter` `factory3d.fire_safety.*` → `unlink`.
4. `maintenance.request` лишаються; поля `f3d_fire_*` зникають з модулем; `f3d_origin='fire_comm'` → NULL
   (`ondelete` selection_add).
5. Моделі модуля (зони, пристрої, журнал, навчання) — стандартна деінсталяція; `f3d.zone`, обладнання, працівники,
   `hr.attendance` не змінюються.

### 5.6 `data/neutralize.sql`

```sql
-- factory3d_fire_safety: нейтралізація копії проду (CB-10, FR-19, FR-24)
UPDATE ir_config_parameter SET value = 'False' WHERE key = 'factory3d.fire_safety.read_enabled';
DELETE FROM ir_config_parameter WHERE key = 'factory3d.fire_safety.write_enabled';   -- не існує; захист від ручного створення
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'factory3d_fire_safety';
UPDATE f3d_source SET read_enabled = false, write_enabled = false WHERE f3d_fire_readonly IS TRUE;
UPDATE f3d_fire_drill SET sim_run_ref = NULL;
UPDATE f3d_fire_drill_person SET employee_id = NULL;
DELETE FROM mail_activity a USING ir_model_data d
  WHERE d.module = 'factory3d_fire_safety' AND d.name = 'mail_act_fire_alarm' AND d.model = 'mail.activity.type'
    AND a.activity_type_id = d.res_id;
UPDATE f3d_fire_panel SET comm = 'off';
```

## 6. Крони й фонові процеси (`data/ir_cron.xml`)

Odoo 19: `ir.cron` з `model_id`, `state='code'`, `code`, `interval_number`, `interval_type`, `active`, `priority`;
виконуються від `base.user_root`.

| XML-id | Назва | Інтервал | Код | Один прогін | Ліміти |
|---|---|---|---|---|---|
| `cron_f3d_fire_sync` | Пожежна безпека: звірка станів і зв'язку | 1 хв, `active=True`, `priority=5` | `model._cron_sync()` (`f3d.fire.panel`) | `read_enabled=False` → `comm='off'` усіх панелей, вихід; інакше `_f3d_fire_sync(full=True)` — R-19 (усі 53 сигнали одним `search_read`), R-12 (зв'язок), лічильник іскор (R-13 п. 5, доба за Києвом) | ≤ 2 с; виняток → `_logger.exception`, наступний прогін повторює (ідемпотентно) |
| `cron_f3d_fire_drill_tick` | Пожежна безпека: хід навчальної тривоги | 1 хв, `active=True`, `priority=5` | `model._cron_tick()` (`f3d.fire.drill`) | немає `running` → вихід за 1 запит; інакше до 5 ітерацій `_tick()` з паузою 10 с (R-15…R-17, авто-стоп) | ≤ 55 с; `commit` після ітерації |
| `cron_f3d_fire_compliance` | Пожежна безпека: перерахунок відповідності нормам | 1 доба, `nextcall` — найближче 03:10 Europe/Kyiv (ставить хук через `pytz`), `active=True` | `model._cron_compliance()` (`f3d.fire.panel`) | для всіх панелей `action_recompute_compliance()` без сповіщення (R-01…R-09) | ≤ 5 с |

## 7. HTTP/JSON API

Власних контролерів модуль не має (токенів теж). Нижче — два контракти даних, які модуль задає поверх ендпоінтів
інших модулів; тести перевіряють їх напряму (виклик обробника/функції), стенд — через ендпоінти.

### API-01 `POST /f3d/telemetry/event`, маршрут `bacnet_event` (вхід, telemetry API-05 → M-18)

Колектор (плагін `bacnet_ip`, вимога 7 ARCH §2.4, Q-07 б) ретранслює `UnconfirmedEventNotification` dev 200.
Елемент `events[]` telemetry: `route="bacnet_event"`, `payload`:

```json
{"device": 200, "object": "LSZ", "instance": 14, "event_type": "change-of-life-safety",
 "from_state": "quiet", "to_state": "test-alarm", "mode": "on",
 "message_text": "Тест: сповіщувач 2.CNC.05, Присадка", "ts": "2026-10-14T07:10:02Z",
 "notification_class": 1, "priority": 1}
```

Схема: `device*` int; `object*` ∈ {`LSZ`, `LSP`, `BI`, `BV`, `AV`, `MSV`, `PIV`} (повні назви ASHRAE теж приймаються —
нормалізація як telemetry R-23); `instance*` int ≥ 0; `event_type*` str ≤ 64; `from_state`, `to_state` str ≤ 32
(текст `BACnetLifeSafetyState` або `normal/offnormal/fault`); `message_text` str ≤ 500 (обрізається); `ts*` ISO з зоною;
інші ключі ігноруються. Обробка: R-14 п. 5. Помилки: відсутнє обов'язкове поле / невідомий `object` →
`ValueError("bacnet_event: <поле>")` (telemetry пише в `f3d.push.event.error`, відповідь API-05 лишається 200);
`device` ≠ device панелі (адреса `signal_state_id`) → подія ігнорується з DEBUG. Ідемпотентність — `event_id`
telemetry + `dedup_key` журналу. Ліміти — API-05 telemetry (≤ 100 подій, ≤ 1 МБ).

### API-02 Розділи `fire` і `evacuation` payload переглядача (вихід, viewer API-02/API-03, CF-01)

`GET /f3d/viewer/data?sections=fire,evacuation` і `GET /f3d/viewer/delta?since=…` повертають розділи, зібрані
M-17 за R-20/R-21. Повна схема з прикладом — Додаток C. Ліміт розміру: `fire` ≤ 60 КБ (без `devices`), ≤ 150 КБ з
`devices` (343 записи); `evacuation` ≤ 25 КБ. Коди помилок — viewer (розділ `error` у `meta.sections`, якщо
провайдер упав). Права — `group_f3d_user` (кіоск — `user_kiosk` viewer, теж `group_f3d_user`).

## 8. Сервісна частина

Власного сервісу немає: показання приладу й модуля вводу читає колектор `factory3d_telemetry` плагінами `bacnet_ip`
і `modbus_tcp` (каркас §6.5, рішення менеджера 14.10). Модуль постачає дані для колектора (джерела §5.3, сигнали
Додаток B) і вимоги до плагіна:

| # | Вимога до `bacnet_ip` (telemetry §8.8) | Як перевіряється |
|---|---|---|
| 1 | Типи об'єктів `LSZ`, `LSP`, `AV`, `BI`, `BV`, `MSV`, `PIV` (Q-16: реальний прилад — BV/PIV замість BI/AV) | ТК-01 на емуляторі; на проді — звірка за EPICS (Q-01) |
| 2 | `present-value` LSZ/LSP → `text` = назва переліку `BACnetLifeSafetyState` (`quiet`, `test-alarm`, …; R-11 таблиця), `value` = індекс; BI/BV → `map` адреси; MSV → `map` (1-based) | ТК-01, ТК-04 |
| 3 | Лише опитування `ReadPropertyMultiple` блоками ≤ `rpm_max` (A-20); жодних `SubscribeCOV` для джерел із `read_only` | ТБ-05 (перехоплення) |
| 4 | `params.read_only=true` → `write()` кидає `NotSupported` до будь-якого мережевого виклику; заборонені й інші сервіси зміни стану: `WriteProperty`, `WritePropertyMultiple`, `AcknowledgeAlarm`, `LifeSafetyOperation`, `DeviceCommunicationControl`, `ReinitializeDevice`, `CreateObject`, `DeleteObject` | ТБ-05; юніт-тести telemetry |
| 5 | Маршрутизована мережа (роутер емулятора, мережа 2) і прямий IP | ТК-01 (стенд), DEPLOY_TEST п. 6 (прод) |
| 6 | Опційно: `UnconfirmedEventNotification` → API-01 | ТК-04 (подія `bacnet` з `message_text`, якщо плагін реалізує) |

Таймінги контуру (для ТК і ТП):

| Ланка | Значення | Джерело |
|---|---|---|
| Опитування LSZ/LSP/BI/MSV/AV лічильників | 10 с | Додаток B `period_s` (A-20) |
| Опитування AV запиленості | 600 с | Додаток B |
| Опитування ADAM DI0–DI6 / HR 40001 | 2 с / 10 с | Додаток B |
| Відправка колектора | ≤ 5 с | telemetry `F3D_PUSH_INTERVAL_S` |
| Затримка тривоги до події в Odoo (хук A-22) | ≤ 15 с; без хука — ≤ 75 с (крон 1 хв) | R-19 |
| `stale` сигналу (telemetry R-07) | `max(3·10, 60)` = 60 с; ADAM 60 с; запиленість 1 800 с | telemetry §5.1 |
| Панель `comm='stale'` / `'lost'` | 90 с / 180 с | §5.1 |
| Імпульс іскри DI0 | 0,6 с — опитуванням не ловиться, події з лічильника HR 40001 (A-13) | iot_sim R-26 |

Емулятор (iot_sim §8.11) ↔ сигнали модуля: LSZ:1…33 — порядок `fire.groups` (Додаток A.1); LSP:<id> — R-23
(`2.FAC.07` → 21607); AV:21607 — запиленість `2.FAC.07`; BI:1…4, BI:10, BI:11, AV:1…3, MSV:1 — Додаток B; ADAM u85 —
DI0…DI6 (fc 2, PDU 0…6), HR 40001–40002 (fc 3, PDU 0, `count=2`, `u32`, `wordorder="little"` — «низьке слово перше,
за ADAM», iot_sim §8.4.2). Логування модуля: `odoo.addons.factory3d_fire_safety.sync` (INFO — переходи станів зон/
панелі/зв'язку, DEBUG — пакети кодів), `.hooks`, `.drill`; тексти без персональних даних (у логах — `employee_id`, не ПІБ).

## 9. Алгоритми й правила

Позначення: `N(key)` = `f3d.fire.norm.get(key)` (M-08; `None`, якщо `value_set=False`); `P(key)` =
`f3d.fire.panel._get_param(key)` (§5.1); `B(key)` = параметри CB-12 base (`plant_length_m` 150, `plant_width_m` 72);
`dist` — евклідова відстань у плані (м). Усі геометричні функції — чисті, у `tools/geometry.py`
(`required_count(rect, s)`, `coverage(rect, points, step=0.5)`, `max_distance(grid_w, grid_d, points, step=2.0)`,
`point_in_rect`). Округлення результатів — як у макеті: відстані до 0,1 м (`round(x, 1)`), розриви покриття до 0,01.
Числа в текстах — з комою (`f"{x:.1f}".replace(".", ",")`).

### R-01 Потрібна кількість сповіщувачів у зоні (FR-07; ДБН В.2.5-56:2014 зі Зм. № 2, табл. 7.1, 7.2)

1. Крок `s`: для `kind ∈ {smoke, multi}` — `s = min(N('smoke_spacing_6_12m'), 2·N('smoke_wall_6_12m'))`, якщо задано
   `N('smoke_area_6_12m')` — `s = min(s, √area)`; для `heat` — `s = min(N('heat_spacing'), 2·N('heat_wall'))`, з
   `N('heat_area')` так само. Будь-яка з двох основних норм не задана → `n_required = 0`, `n_ok = False`,
   `compliance = 'na'`, нотатка «Норма <key> не задана».
2. `nx = max(1, ceil((x1 − x0)/s − 1e−9))`, `ny = max(1, ceil((y1 − y0)/s − 1e−9))`, `n_required = nx·ny` (як
   `fire.detectors()`); `n_ok = detector_count ≥ n_required`.
3. Приклади (макет, `s = min(8,8; 2·4,4) = 8,8`): `FA-SHEETS` 26,8 × 44,8 → 4 × 6 = 24 (є 24); `FA-FAC` 49,4 × 25,0 →
   6 × 3 = 18; `FA-EDGE` 6,6 × 25,4 → 1 × 3 = 3; `FA-BOILER` (heat, `s = min(6,4; 6,4)`) 12,0 × 6,0 → 2 × 1 = 2;
   повна таблиця — Додаток A.1, усі 33 `n_ok`. Норму `smoke_spacing_6_12m` змінено на 6,0 → `FA-CUT` 13,6 × 44,8 →
   3 × 8 = 24 > 12 → `n_ok=False`, `compliance='fail'`.

### R-02 Покриття зони (похідна перевірка, A-06)

1. `r = s/√2` (s з R-01): 6,22 м для 8,8; 4,53 м для 6,4. `tol = P('cover_tol_m')` (0,5).
2. Сітка: `x = x0 + 0,5·i`, `i = 0…floor((x1 − x0)/0,5 + 1e−9)`; `y` так само; цикл `i` зовнішній, `j` внутрішній.
3. Для кожної точки `d = min dist(точка, (x, y) активних детекторів зони)`; `cover_max_gap_m = round(max d, 2)`,
   `cover_point` — перша точка з максимумом (строге `>`), формат `f"({round(x, 2)}, {round(y, 2)})"` (`"(122.0, 54.1)"`, `"(0.6, 10.15)"`); зона без детекторів → `gap = ∞`,
   `compliance='fail'`.
4. `cover_ok = gap ≤ r + tol`. `compliance`: `fail`, якщо `not n_ok` або `gap > r + 2·tol`; `warn`, якщо
   `not cover_ok`; інакше `ok`.
5. `compliance_note` = «Потрібно {n_required} ({nx}×{ny} при кроці {s} м), є {detector_count}. Покриття: найбільший
   розрив {gap} м у точці {cover_point} при радіусі {r} м + допуск {tol} м.»
6. Приклади: `FA-FG` → 6,26 у (122.0, 54.1), `r` 6,22 → `cover_ok` (≤ 6,72), `ok`; `FA-SHEETS` 5,02 у (14.6, 0.6);
   `FA-FAC` 5,86 у (42.2, 71.4); `FA-BOILER` 4,24 у (67.6, 75.0) при `r` 4,53. `cover_tol_m = 0,03` → `FA-FG`
   `cover_ok=False` (6,26 > 6,25), але 6,26 ≤ 6,28 → `compliance='warn'`; решта 32 зони — `ok` (наступний за величиною
   запас — `FA-PRE` 5,81). Повна таблиця розривів — Додаток A.1.

### R-03 Найбільша відстань до ручного сповіщувача (ДБН п. 7.2.11.3, ДСТУ-Н CEN/TS 54-14 6.5.4)

Сітка 2 м по будівлі: `x = 2i`, `i = 0…floor(B('plant_length_m')/2)` (0…75), `y = 2j`, `j = 0…floor(B('plant_width_m')/2)`
(0…36) — 2 812 точок; `d = min dist(точка, активні type='mcp')`; `compliance_mcp_max_m = round(max d, 1)`, точка — перша з
максимумом (формат R-02: `"(60.0, 72.0)"`); `compliance_mcp_ok = max ≤ N('mcp_spacing')`. Відстань по прямій без перешкод (як `fire.max_mcp_distance()`;
ДБН міряє шлях — зауваження у звіті). Макет: **26,9 м у (60.0, 72.0)** ≤ 30 → `ok`. Архівувати `1.MCP.08` (36, 59.75) →
32,0 м у (32.0, 72.0) → `compliance_mcp_ok=False`. Архівувати `2.MCP.09` (60, 0.6) → без змін (26,9).

### R-04 Найбільша відстань до оповіщувача (довідково, A-26)

Та сама сітка R-03 для `type='sounder'`: `compliance_sounder_max_m = 45,2` у (54.0, 0.0) (південна стіна без
оповіщувачів). Висновку «відповідає/ні» немає; у звіті — текст: «Рівень звуку ≥ {N('sounder_level')} дБА або на 5 дБА
вище фону (виробничі {N('sounder_bg_production')}, склади {N('sounder_bg_storage')}, офіс {N('sounder_bg_office')} дБА)
визначає акустичний розрахунок; паспорт FDS226-RW 75…99 дБА, покриття маяка W-3.2-10.»

### R-05 Довжина шляху евакуації (ДБН В.2.2-27:2025 п. 8.2.2, табл. 8.2; п. 8.2.11)

`norm = N('evac_distance_polymer')` (50), якщо `P('polymer_panels')`, інакше `N('evac_distance_prod_B')` (240).
Для кожного активного маршруту: `length_ok = length_m ≤ norm`; `compliance = 'ok'` якщо `length_ok and width_ok`
(R-07), інакше `fail`; нотатка «{length_m} м до {exit} при нормі ≤ {norm} м ({ref норми})». Панель:
`compliance_routes_ok/total`. Макет: 32/32 при 240 і при 50 (найдовший `Z-PRE` 38,6 м; найдальша точка цеху
`evac_max_distance_m` 45,3 м ≤ 50). Норму `evac_distance_prod_B` змінено на 30 → 6 маршрутів `fail`: `Z-RCV-4` 37,7,
`Z-SHEETS` 33,1, `Z-PRE` 38,6, `Z-MAINT` 30,6, `Z-FG` 32,6, `Z-OUT-4` 37,6 → 26/32. Тупики ≤ 25 м (п. 8.2.9) не
перевіряються (у макеті немає графа шляхів) — рядок у звіті «не перевіряється».

### R-06 Кількість і розосередженість виходів (ДБН В.1.1-7:2016 п. 7.2.4, 7.2.6; ДБН В.2.2-27 п. 8.2.9)

1. `E` — активні виходи; `n_ok = |E| ≥ N('evac_exits_min')` (2).
2. `П = 2·(B('plant_length_m') + B('plant_width_m'))` = 444 м (периметр зали, як `note` `evac_exits_min`);
   `L = N('exit_dispersal_k')·√П` = 1,5·√444 = **31,6 м** → `compliance_exit_l_m`.
3. `compliance_exit_pair_m = round(max dist(e1, e2), 1)` по всіх парах = **145,1** (`EX-S1`–`EX-N4`).
4. `nearest_exit_m` кожного виходу — до найближчого іншого (довідково): EX-S1 37,0; EX-S2 17,5; EX-S3 17,5; EX-S4 7,4;
   EX-S5 12,4; EX-S6 24,6; EX-N1 36,0; EX-N2 25,0; EX-N3 25,0; EX-N5 29,0; EX-N4 29,0; EX-IN 7,4.
5. `compliance_exits_ok = n_ok and pair ≥ L and всі width_ok` (R-07). Макет — `True`. Архівувати всі, крім EX-S4 і
   EX-IN → `n=2`, пара 7,4 < 31,6 → `False`. Ворота доків виходами не вважаються (дані містять лише двері).

### R-07 Ширина дверей і шляхів (ДБН В.1.1-7 п. 7.2.7, 7.3.6; ДБН В.2.2-27 п. 8.2.13–8.2.15)

`exit.width_ok = width_m ≥ N('door_width_min')` (0,8); `route.width_ok = min(width_min_m, exit_id.width_m) ≥
N('exit_width_min')` (1,0). Макет: виходи 1,2 м, найвужче місце шляхів 1,2 м (прорізи перегородок 1,6…4,0 м, A-25) →
усе `ok`. `EX-S1.width_m = 0,7` → вихід `fail`, маршрути до EX-S1 (`Z-RCV-1…4`, `Z-SHEETS`) `width_ok=False` → `fail`.

### R-08 Зони цеху без пожежної сигналізації (Q-05)

`compliance_missing_zones = ", ".join(sorted(code для f3d.zone активних, zone_type != 'outdoor', без активної f3d.fire.zone))`
→ **«Z-OFFICE, Z-SOC»** (34 цехові зони base − 32 із сигналізацією). Порожньо → `False`. У звіті — зауваження, не «fail».

### R-09 Димові зони й люки (ДБН В.2.5-56 п. 10.4.2; орієнтир MIndBauRL 5.7)

`area = (x1 − x0)·(y1 − y0)`; `max_area_m2 = N('smoke_zone_max_area')` (1600); `area_ok = area ≤ max`;
`need_vents = ceil(area/400 · N('smoke_vent_area') / N('smoke_vent_aa') − 1e−9)`; `vents_ok = vent_count ≥ need`;
`compliance`: `fail`, якщо `not area_ok`; `warn`, якщо `not vents_ok` (кількість люків — орієнтир, не норма); інакше `ok`.

| Зона | Контур | Площа | Потреба (1,5/1,02 на 400 м²) | Люків | Результат |
|---|---|---|---|---|---|
| SZ-1 | 0–20 × 0–72 | 1440 | 5,29 → 6 | 6 | ok |
| SZ-2 | 20–42 × 0–72 | 1584 | 5,82 → 6 | 6 | ok |
| SZ-3 | 42–62 × 0–46 | 920 | 3,38 → 4 | 4 | ok |
| SZ-4 | 62–92 × 0–46 | 1380 | 5,07 → 6 | 6 | ok |
| SZ-5 | 42–92 × 46–72 | 1300 | 4,78 → 5 | 5 | ok |
| SZ-6 | 92–112 × 0–72 | 1440 | 5,29 → 6 | 6 | ok |
| SZ-7 | 112–132 × 0–72 | 1440 | 5,29 → 6 | 6 | ok |
| SZ-8 | 132–150 × 0–72 | 1296 | 4,76 → 5 | 5 | ok |
| **Разом** | | 10 800 | 44 | 44 (Aa 44,9 м²) | 8/8 |

Архівувати `0.SV.01` → SZ-1 5 < 6 → `warn`; `SZ-1.x1 = 25` → площа 1800 > 1600 → `fail`.

### R-10 Стан приладу (FR-01)

1. `t0 = signal_state_id.last_text` (LSZ:0), `s0 = ZONE_MAP[t0]` (R-11); `v = signal_system_id` (MSV:1: `last_text`
   за `map` або `int(last_value)`), `s1 = {1:'normal', 2:'alarm', 3:'fault', 4:'test', 5:'disabled'}.get(v)`.
2. `PRIORITY = {alarm: 6, prealarm: 5, fault: 4, disabled: 3, test: 2, normal: 1, unknown: 0}`;
   `state = max((s0, s1), key=PRIORITY)` серед відомих; обидва невідомі → `unknown`.
3. `raw_state = t0`, `system_state = v`; лічильники `alarms_count/faults_count/disabled_count = int(round(AV:1/2/3))`;
   `sounders_active = (BI:10 text == 'on')`, `brigade_transmitted = (BI:11 text == 'on')`.
4. Зміна `state` → `_set_state` (події R-14, активність FR-11 при вході в `alarm`/`prealarm` без тривожних зон,
   закриття активності при виході в `normal`).
5. Сигнал зі `status='stale'` — значення не змінюється (A-17), панель стає `comm='stale'` за R-12.
6. `state_text`: `comm='off'` → «Обробка вимкнена»; `comm='lost'` → «Зв'язок із приладом втрачено»; інакше основа:
   `normal` «Норма», `alarm` «ТРИВОГА: <назви зон у тривозі, до 3, далі " та ще N">», `prealarm` «Передтривога: <зони>»,
   `fault` «Несправність» (+ «: <зони у fault>», якщо є), `disabled` «Вимкнення: N зон», `test` «Тест», `unknown` «Немає
   даних»; для `normal`/`test` + `warn_count > 0` → «, N попередження» (`N % 10 ∈ {1,2,3,4}` і `N % 100 ∉ {11…14}` →
   «попередження», інакше «попереджень»); `comm='stale'` → + « (дані застарілі)». Макет: `normal` + `FA-FAC.warn` →
   **«Норма, 1 попередження»**; 5 зон із попередженням → «Норма, 5 попереджень».

### R-11 Стани зон, пристроїв і шлейфів з `BACnetLifeSafetyState` (`tools/states.py`)

Перелік — ASHRAE 135 `BACnetLifeSafetyState` (номери підтверджено довідниками драйверів: Elipse BACnet
https://docs.elipse.com.br/documents/en-us/driver/bacnet/latest/generated_enum_bacnetlifesafetystate.html, CODESYS
`IEC_BACNET_LIFE_SAFETY_STATE` https://content.helpme-codesys.com/en/libs/CmpBACnet/3.5.17.0/BACnetEnums/IEC_BACNET_LIFE_SAFETY_STATE.html;
переглянуто 14.10.2026). Текст приходить від telemetry (R-23 telemetry), числовий рядок (`"9"`) переводиться за номером.

| № | Текст | Зона/прилад (`ZONE_MAP`) | Пристрій (`DEVICE_MAP`) | `FAULT_STATES` (заявка ТО) |
|---|---|---|---|---|
| 0 | quiet | normal | normal | |
| 1 | pre-alarm | prealarm | prealarm | |
| 2 | alarm | alarm | alarm | |
| 3 | fault | fault | fault | так |
| 4 | fault-pre-alarm | prealarm | prealarm | |
| 5 | fault-alarm | alarm | alarm | |
| 6 | not-ready | disabled | disabled | |
| 7 | active | alarm | active | |
| 8 | tamper | fault | fault | так |
| 9 | test-alarm | test | test | |
| 10 | test-active | test | test | |
| 11 | test-fault | test | test | |
| 12 | test-fault-alarm | test | test | |
| 13 | holdup | alarm | alarm | |
| 14 | duress | alarm | alarm | |
| 15 | tamper-alarm | alarm | alarm | |
| 16 | abnormal | fault | fault | так |
| 17 | emergency-power | fault | fault | так |
| 18 | delayed | prealarm | prealarm | |
| 19 | blocked | disabled | disabled | |
| 20 | local-alarm | prealarm | prealarm | |
| 21 | general-alarm | alarm | alarm | |
| 22 | supervisory | fault | fault | так |
| 23 | test-supervisory | test | test | |
| — | інший текст / порожньо | unknown (WARNING у лог, раз на код) | unknown | |

Справжня тривога (`alarm`) заявки не створює (A-07). Алгоритм для зони (`signal_id`): `status == 'stale'` → `stale=True`,
стан не змінюється; інакше `stale=False`; `t = last_text`; `t == raw_state` → нічого; інакше
`_set_state(ZONE_MAP[t], t, last_ts, device)`, де `device` — детектор зони з окремим сигналом у тому ж класі стану
(`DEVICE_MAP` збігається), інакше пристрій, знайдений у `message_text` BACnet (R-14 п. 5), інакше `None`. Пристрій
(`state_signal_id`) — те саме з `DEVICE_MAP`. Шлейф (`signal_id`, BI/BV з `map {"0":"off","1":"on"}`): `on` → `fault`,
`off` → `ok`. `warn` зони (M-03) — перерахунок через `@api.depends`.

### R-12 Зв'язок із приладом (FR-12, A-16)

1. `P('read_enabled') == False` або `source_id.read_enabled == False` → `comm='off'`, вихід (подій немає).
2. `last_seen = max(last_ts)` сигналів панелі (LSZ:0, MSV:1, AV:1…3, BI:1…4, BI:10, BI:11, LSZ:1…33) з `status ≠ 'unknown'`
   і `last_quality ≠ 'bad'`.
3. Немає `last_seen` → `new = 'lost'`; інакше `age = now − last_seen`: `age ≤ P('comm_stale_after_s')` (90) →
   `online`; `≤ P('comm_lost_after_s')` (180) → `stale`; інакше `lost`.
4. Перехід: `→ online` з `stale/lost/off` → подія `comm_restored`, закрити активність «Втрата зв'язку» (`action_feedback`
   «Зв'язок відновлено»), `first_sync=False`; `online → stale` → `comm_stale`; `online/stale → lost` → `comm_lost`
   (рівень `alarm`), активність типу `mail_act_fire_alarm` групі `alert_group_xmlid` з summary «Втрата зв'язку з
   приладом FACP-1», заявка R-22 п. 3.
5. `first_sync=True` (після установки, ще жодного показання): перехід у `lost` — без подій, активності й заявки;
   перше `online` — подія `comm_restored` і `first_sync=False` (інструкція ARCH 4.1 п. 5).
6. `comm_since = now` на кожній зміні; `zone.stale = comm in ('stale','lost')` для всіх зон панелі.
7. Модуль вводу ADAM (системи `spark`/`smoke`): усі сигнали системи `status='stale'` → `state='unknown'`, `stale=True`,
   подія `comm_lost` рівня `warn` з `object_code` = код системи («Немає даних від модуля вводу MB-U85-IO6: SPARK-1»);
   перше свіже показання → `comm_restored` (info) і перерахунок стану. Заявки немає (ARCH §2.4).
8. Приклад (ARCH 2.5, приклад 3): `last_seen` 10:31:00, крон о 10:32:40 → `stale` + `comm_stale`; о 10:34:05 → `lost`,
   `comm_lost` «Зв'язок із приладом FACP-1 втрачено: немає даних з 10:31 (3 хв)», заявка з тим самим заголовком; нове
   показання 10:40 → `online`, `comm_restored`, заявка лишається відкритою (закриває механік).

### R-13 Запиленість і системи (FR-06, FR-10)

1. Сигнал запиленості пристрою (`dust_signal_id`, `status ≠ 'unknown'`, `last_ts > dust_ts`) → `device._set_dust(last_value, last_ts)`.
2. Пороги — `P('dust_warn_pct')` (80) і `P('dust_alarm_pct')` (90); ті самі значення стоять у `warn_high/alarm_high`
   сигналів (M-16), тож заявку telemetry створює на тому ж порозі.
3. `dust_state`: `na` → без даних; `alarm`, якщо `pct ≥ 90`; `warn`, якщо `pct ≥ 80`; інакше `ok`. Події (при `log=True`):
   `na/ok → warn` — `dust_warn`; `→ alarm` — `dust_alarm`; `warn/alarm → ok` — `dust_ok`; `na → ok` — без події.
   Макет: 82 → `warn`; 90,1 → `alarm`; 79 → `ok` + `dust_ok`.
4. `zone.warning` — найгірший пристрій зони за порядком `alarm`-запиленість > `warn`-запиленість > `fault` > `disabled` >
   `reliability ∉ {порожньо, no-fault-detected}`; `loc = " " + note`, якщо `note`; тексти:
   `warn` — «Сповіщувач {address}{loc}: запиленість камери {floor(pct)} % — очистити до кінця зміни, інакше прилад
   переведе його в несправність.» (макет: **«Сповіщувач 2.FAC.07 біля шліфування: запиленість камери 82 % — очистити до
   кінця зміни, інакше прилад переведе його в несправність.»**); `alarm` — «Сповіщувач {address}{loc}: запиленість камери
   {floor(pct)} % понад {alarm} % — потрібне очищення (заявка ТО).»; `fault` — «Пристрій {address}{loc}: несправність
   ({raw_state або reliability}).»; `disabled` — «Пристрій {address}{loc}: вимкнено на приладі.»; немає — `False`.
5. Іскрогасіння: `DI0` іскра, `DI1` гасіння, `DI2` несправність, `DI3` тиск води (`map {"0":"low","1":"ok"}`), лічильник
   `c = int(round(HR))`. `state`: `unknown` (усі сигнали `stale`/`unknown`); `fault`, якщо `DI2 = on` або `DI3 = low`;
   `active`, якщо `DI0 = on` або `DI1 = on`; інакше `ok`. Лічильник: `c > count_today` → подія `spark` «Іскрогасіння:
   іскру виявлено на магістралі аспірації ({c − count_today} шт.), гасіння спрацювало; за добу — {c}.»; `c < count_today`
   (новий день/скидання модуля) — без події; потім `count_today = c`, `count_ts = last_ts`. `DI2 off→on` `spark_fault`,
   `on→off` `spark_fault_ok`; `DI3 ok→low` `spark_water_low`, `low→ok` `spark_water_ok`.
6. Димовидалення: `DI4` (`map {"0":"closed","1":"open"}`), `DI5` (`{"0":"ok","1":"fault"}`), `DI6` (`{"0":"mains","1":"battery"}`).
   `state`: `unknown`; `fault` (DI5); `battery` (DI6); `active` (DI4 open); `ok`. Події: `smoke_open`/`smoke_closed`,
   `smoke_fault`/`smoke_fault_ok`, `smoke_battery`/`smoke_mains`.
7. Спринклери: `pressure_signal_id.status`: `alarm` → `low_pressure`; `stale`/`unknown`/немає сигналу → `unknown`;
   інакше `ok`. Події `sprinkler_low` (`ok → low_pressure`), `sprinkler_ok` (`low_pressure → ok`).
8. `state_text` і короткий підпис (`systems_text`):

| Система | `ok` | `active` | `fault` | `battery` | `low_pressure` | `unknown` |
|---|---|---|---|---|---|---|
| spark | «Норма, іскор за добу — {count_today}» / «норма» | «Спрацювання: іскру гасять» / «спрацювання» | «Несправність» (+ « — немає тиску води», якщо DI3 low) / «несправність» | — | — | «Немає даних» / «немає даних» |
| smoke | «Клапани закриті, живлення від мережі» / «норма» | «Клапани відкриті» / «спрацювання» | «Несправність щита D+H» / «несправність» | «Живлення від акумуляторів (резерв 72 год)» / «від АКБ» | — | «Немає даних» |
| sprinkler | **«Спринклерна система в режимі очікування»** (дослівно `fire.totals.sprinkler`) / «очікування» | — | — | — | «Спринклерна система: тиск {p} бар нижче норми {min} бар» / «низький тиск» | «Спринклерна система: немає даних тиску» / «немає даних» |

### R-14 Журнал подій: типи, тексти, дедуплікація, BACnet (FR-05, A-04, A-24)

1. Таблиця `ETYPES` (`tools/states.py`; 41 значення; `{z}` = «{code} ({name})» зони, `{d}` = адреса пристрою,
   `{dd}` = «, сповіщувач {d}», якщо пристрій відомий):

| etype | kind | level | Об'єкт / тригер | Текст |
|---|---|---|---|---|
| `alarm` | alarm | alarm | зона/пристрій → `alarm` | «ТРИВОГА: зона {z}{dd}» |
| `prealarm` | prealarm | warn | → `prealarm` | «Передтривога: зона {z}{dd}» |
| `fault` | fault | warn | зона/пристрій → `fault`; прилад → `fault` без зон у `fault` | «Несправність зони {z}: стан {raw}» / «Несправність приладу FACP-1: стан {raw}» |
| `fault_ok` | fault | info | `fault → normal` | «Зона {z}: несправність усунено» |
| `disabled` | disabled | warn | → `disabled` | «Зону {z} вимкнено на приладі» |
| `enabled` | disabled | info | `disabled → normal` | «Зону {z} увімкнено» |
| `test` | test | info | → `test` | «Тест: зона {z}{dd}» |
| `test_end` | test | info | `test → normal` | «Тест завершено: зона {z}» |
| `reset` | reset | info | `alarm/prealarm → normal` (зона); прилад `≠ normal/unknown → normal` | «Зона {z}: тривогу скинуто» / «Прилад FACP-1: стан «Норма»» |
| `dust_warn` | dust | warn | R-13 п. 3 | «Попередження про запиленість: сповіщувач {d} ({zone name}{, note}) — {floor(pct)} %» |
| `dust_alarm` | dust | warn | R-13 п. 3 | «Запиленість сповіщувача {d} ({zone name}) {floor(pct)} % понад {alarm} %» |
| `dust_ok` | dust | info | R-13 п. 3 | «Сповіщувач {d}: запиленість {floor(pct)} % — у нормі» |
| `loop_fault` | loop | warn | BI шлейфу `off → on` (і `unknown → on`) | «Несправність шлейфу {n} приладу FACP-1» |
| `loop_ok` | loop | info | `on → off` | «Шлейф {n}: несправність усунено» |
| `sounders_on` | alarm | warn | BI:10 `off → on` | «Оповіщувачі увімкнено ({sounders} шт.)» |
| `sounders_off` | alarm | info | `on → off` | «Оповіщувачі вимкнено» |
| `brigade_on` | alarm | alarm | BI:11 `off → on` | «Сигнал «Пожежа» передано на пульт ДСНС» |
| `brigade_off` | alarm | info | `on → off` | «Передачу на пульт завершено» |
| `comm_stale` | comm | warn | R-12 | «Дані приладу FACP-1 застарілі: немає показань {age} с» |
| `comm_lost` | comm | alarm (системи — warn) | R-12 | «Зв'язок із приладом FACP-1 втрачено: немає даних з {HH:MM} ({m} хв)» / «Немає даних від модуля вводу {source}: {system}» |
| `comm_restored` | comm | info | R-12 | «Зв'язок із приладом FACP-1 відновлено» / «Дані модуля вводу {source} відновлено: {system}» |
| `spark` | spark | warn | R-13 п. 5 | див. R-13 п. 5 |
| `spark_fault` / `spark_fault_ok` | spark | warn / info | DI2 | «Несправність іскрогасіння SPARK-1» / «Іскрогасіння SPARK-1: несправність усунено» |
| `spark_water_low` / `spark_water_ok` | spark | warn / info | DI3 | «Іскрогасіння SPARK-1: немає тиску води гасіння» / «Іскрогасіння SPARK-1: тиск води в нормі» |
| `smoke_open` / `smoke_closed` | smoke | warn / info | DI4 | «Димовидалення: клапани відкрито ({vent_count} шт.)» / «Димовидалення: клапани закрито» |
| `smoke_fault` / `smoke_fault_ok` | smoke | warn / info | DI5 | «Несправність щита димовидалення SMOKE-CTRL» / «Щит димовидалення: несправність усунено» |
| `smoke_battery` / `smoke_mains` | smoke | warn / info | DI6 | «Щит димовидалення SMOKE-CTRL працює від акумуляторів» / «Щит димовидалення: живлення від мережі відновлено» |
| `sprinkler_low` / `sprinkler_ok` | sprinkler | warn / info | R-13 п. 7 | «Спринклерна система: тиск {p} бар нижче норми {min} бар» / «Спринклерна система: тиск у нормі ({p} бар)» |
| `drill_start` | drill | info | R-15 | «Навчальна тривога {name} розпочата: зона {z}, сповіщувач {d або «—»}, на об'єкті {n} осіб» |
| `drill_end` | drill | info | R-16 п. 4 | «Навчальна тривога {name} завершена: вийшли {e} з {n} за {t} с» |
| `drill_auto` | drill | info | R-18 п. 3 | «Навчання {name} створено автоматично: тест приладу в зоні {z}» |
| `drill_real_alarm` | drill | alarm | R-18 п. 4 | «Під час навчання {name} прилад показав справжню тривогу: зона {z}» |
| `bacnet` | info | info | R-14 п. 5 | «BACnet: {message_text}» або «BACnet: {object}:{instance} {from} → {to}» |
| `manual` | manual | info | користувач (M-05) | текст користувача |
| `info` | info | info | демо, службові | текст викликача |

2. Ключ дедуплікації — M-05 `_log` п. 2 (`etype:object:кошик 2 с`); для навчань — `drill_start:<name>`,
   `drill_end:<name>`, `drill_auto:<name>`, `drill_real_alarm:<name>`; демо — `demo:<n>`. Повторна звірка (крон після
   хука) не дублює подій, бо переходи рахуються від збережених `raw_state`, а не від сигналів.
3. Зв'язок із заявкою — R-22 п. 1.
4. Тексти: `tools/sanitize.clean_text(s, 500)` — видалити символи `\x00–\x1f`, `\x7f` (крім пробілу), стиснути пробіли,
   обрізати до 500; HTML не формується (представлення й переглядач екранують самі).
5. BACnet-повідомлення (M-18, API-01): `object` нормалізується (`life-safety-zone` → `LSZ`…); `LSZ:0` → прилад,
   `LSZ:n` → зона з `lsz_instance = n`, `LSP:id` → пристрій з `lsp_instance = id`, інше → прилад. `etype = ZONE_MAP` →
   тип переходу за таблицею п. 1 (`to_state = test-alarm` → `test`; `quiet` після `alarm` → `reset`). Шукається подія
   того ж `etype` і `object_code` з `|ts − event.ts| ≤ 5 с` → дописати `message_text` (і `device_id`, якщо в
   `message_text` знайдено адресу regex `\b[0-4]\.[A-Z0-9-]{2,8}\.[0-9]{2}\b` і пристрій існує); не знайдено → нова
   подія `bacnet` (info) з `message_text`. Стани моделей повідомлення **не** змінюють (лише сигнали, A-04).

### R-15 Початок навчання

1. Перевірки: `state ∈ {draft, planned}`; `zone_id` заданий; немає іншого `running` у компанії (`UserError("Уже триває
   навчання %s.")`).
2. `start_ts = ts or now`; `state='running'`; `steps` порожні → `_fill_steps()`; усі кроки `done=False`, `t_fact_s=0`.
3. `base = env['f3d.fire.passage.source']`; `src = base._f3d_get_source()`; `passage_source = base._f3d_source_key(src)`;
   люди = `base._f3d_people_at(src, start_ts)`, сортування `(since, employee_id)`; `person_ids` = рядки `seq` 1…n, `source`
   (`attendance` для `hr_attendance`, `access` для `access`, інакше `manual`), `since`.
4. Подія `drill_start`; чаттер «Почато о {HH:MM:SS}, на об'єкті {n}»; шина `_notify('f3d.fire.drill', [name], 'state')`.
5. Приклад (юніт-тест): відмітки `hr.attendance` — 3 відкриті з `check_in` до старту, 1 закрита до старту, 1 з
   `check_in` після старту → `on_site_count = 3`. Демо-копія: 35.

### R-16 Проходи, завершення, результат

1. Виконується в `_tick()` і в `action_stop()`.
2. `src` — та сама модель, що на старті (за `passage_source`: `PREFIX + passage_source`, якщо є в реєстрі, інакше
   `_f3d_get_source()`); `passages = src._f3d_passages(start_ts, min(now, end_ts or now))`, лише `direction='out'`, за зростанням `ts`; для
   людини навчання без `exit_ts` → `exit_ts = ts`, `exit_point = point`; працівники поза списком ігноруються.
3. Лічильники `on_site/evacuated/present/missing` і `evac_pct` — збережені compute (M-11).
4. `action_stop(ts)`: `end_ts = ts or now`; п. 2 до `end_ts`; `evac_time_s = max(exit_s)` серед тих, хто вийшов
   (немає — 0); `state='evaluating'`; подія `drill_end`.
5. `evac_pct = (evacuated + present)/on_site·100`, `on_site = 0` → 100,0.
6. `result_suggested` (для `evaluating`/`done`): `failed`, якщо `missing_count > 0`; `remarks`, якщо
   `evac_time_s > time_limit_s` або `data_quality='partial'` або `real_alarm` або `steps_done < steps_total`; інакше `ok`.
   Приклад: 3 людини, 2 вийшли через турнікет за 95 і 140 с, третій — на перекличці → `evac_time_s 140`,
   `evac_pct 100,0`, `partial` → `remarks`; без переклички → `missing 1` → `failed`.
7. Авто-стоп (у `_tick`, крім `mode='tabletop'`): була подія `test`/`alarm`/`prealarm` зони навчання з
   `ts ≥ start_ts − 60 с`, зараз усі зони панелі в `normal`/`unknown` і панель `normal`, і від останньої події
   `test_end`/`reset` цієї зони минуло ≥ `P('drill_auto_stop_s')` (120 с) → `action_stop(ts = час тієї події)`.
   Емулятор S-07 (`duration_s` 300): тест 0…300 с, повернення до 330 с → авто-стоп після 450 с, `end_ts` ≈ 330 с.

### R-17 Автовідмітка кроків

Для кроків `done=False` з `auto_key ≠ none` (у `_tick` і `action_stop`); `done_ts` → `t_fact_s = max(0, done_ts −
start_ts)`, `done_by='auto'`:

| auto_key | Умова (події журналу — `ts ≥ start_ts − 60 с`) | `done_ts` |
|---|---|---|
| `detector` | подія `test`/`alarm`/`prealarm` з `zone_id = drill.zone_id` | її `ts` |
| `sounders` | подія `sounders_on` | її `ts` |
| `brigade` | подія `brigade_on` (у навчанні S-07 `BI:11=0` → лишається вручну) | її `ts` |
| `smoke` | подія `smoke_open` | її `ts` |
| `evacuation` | є людина з `exit_ts` | `min(exit_ts)` |
| `ventilation` | є активні `f3d.signal` з `code =like 'ventilation/units/%/mode'` і `source_id`; усі мають `last_text ∈ {ST, Off}` і `last_ts ≥ start_ts` | `max(last_ts)` |
| `doors` | `'f3d.access.door' in env`; двері (лише `is_perimeter`, якщо поле є) усі в `state ∈ {unlocked, open}` | `now` |
| `machines` | для `wc ∈ drill.zone_id.zone_id.workcenter_ids` є сигнали `workcenters/<wc.code>/state` із джерелом; усі `last_text ∈ {ERROR, error, stopped}` і `last_ts ≥ start_ts` | `max(last_ts)` |

Без потрібних модулів/сигналів крок лишається для ручної відмітки (`action_done_now`). Емулятор S-07 (iot_sim R-25):
`detector` 0…5 с, `sounders` ≈ 3 с, `smoke` ≈ 9 с (+ затримка опитування ≤ 10 с і push ≤ 5 с), `ventilation` ≈ 6 с і
`doors` ≈ 12 с — лише з bms/access, `machines` ≈ 20 с — з machine_connect.

### R-18 Зіставлення тесту приладу з навчанням (FR-14, A-14)

Викликається з `zone._set_state` при новому стані `test` (параметр `real=False`) або `alarm` (`real=True`):
1. Є `running` навчання компанії: `test` → якщо в навчання немає `device_id`, а пристрій відомий — записати; повернути його.
2. `test` і немає `running`: шукати `planned` з `|planned_ts − ts| ≤ P('drill_match_window_min')` хв, спершу з тією ж зоною,
   далі найближче за часом; знайдено → якщо зона інша — `zone_id` = зона тесту + чаттер «Тест прийшов із зони {z},
   заплановано {z0}»; `device_id` = відомий пристрій; `action_start(ts, source='panel')`.
3. `test`, нічого не знайдено, `P('drill_auto_create')` → `create({title: "Тест приладу: {zone.name}", origin: 'panel',
   mode: 'panel_test', zone_id, device_id, planned_ts: ts})` → `action_start(ts)`; подія `drill_auto`. Параметр `False`
   → нічого.
4. `alarm` (справжня тривога): є `running` → `real_alarm=True`, подія `drill_real_alarm`, чаттер; немає → нічого
   (тривога — не навчання; активність охороні — FR-11).

### R-19 Синхронізація станів із сигналами (`tools/sync.FireSync`, A-22)

`FireSync(env).run(codes=None, full=False) -> dict`, викликається з `f3d.signal._f3d_ingest` (коди змін) і крона
(`full=True`):
1. `read_enabled=False` → R-12 п. 1, повернути `{"skipped": "read_disabled"}`.
2. Індекс `signal_id → [(роль, запис)]` з `panel.signal_*`, `loop.signal_id`, `zone.signal_id/dust_signal_id`,
   `device.state_signal_id/dust_signal_id`, `system.signal_*`/`pressure_signal_id` (один сигнал може мати дві ролі:
   запиленість `2.FAC.07` — зони й пристрою). `codes` задано → лише сигнали з цими кодами.
3. `rows = env['f3d.signal'].sudo().search_read([('id','in',ids)], ['code','last_value','last_text','last_ts','status','last_quality'])`;
   `last_quality = 'bad'` → рядок пропускається.
4. Порядок застосування: пристрої (стан, запиленість) → зони (R-11) → шлейфи → прилад (R-10) → системи (R-13) → зв'язок
   (R-12; при `full` або якщо серед кодів є сигнали приладу) → шина: `_notify('f3d.fire.zone', [змінені коди зон],
   'state')`, `_notify('f3d.fire.panel', ['FACP-1'], 'state')` за будь-якої зміни приладу/систем/зв'язку (лише якщо
   `'f3d.viewer.event' in env`).
5. Повернути `{"signals": n, "changed": m, "events": k}`. Ідемпотентно: повтор із тими самими сигналами → `changed: 0`,
   `events: 0`.

### R-20 Розділ `fire` payload (`tools/payload.build_fire`, CF-01, A-21)

Порядок ключів: `rules`, `loops`, `groups`, `totals`, `events`, `panel`, `systems`, (`devices`).
- `rules` — 10 ключів `fire_rules.json` у порядку файлу (`smoke_area_6_12m`, `smoke_spacing_6_12m`, `smoke_wall_6_12m`,
  `heat_area`, `heat_spacing`, `mcp_spacing`, `mcp_height`, `sounder_level`, `spark_detection_required`,
  `flame_detector_note`): `value` (ціле, якщо ціле: 30, 65) або `null`.
- `loops` — `{"1": {"detectors": 64, "mcp": 10, "sounders": 11, "flame": 0, "modules": 0, "state": "ok"}, "2": {68, 10, 13, 3, 4}, "3": {34, 7, 7, 0, 0}, "4": {46, 9, 10, 0, 0}}`; `state` = стан шлейфу (`unknown`→`"ok"`).
- `groups` — 33 записи за `lsz_instance`: `zone` (`zone_id.f3d_code`; для `FA-BOILER` — `"BOILER"`, як у макеті),
  `zone_name`, `kind`, `kind_name`, `n` (`detector_count`), `spacing`, `area` (int), `loop`, `state`, opt `warning`,
  opt `maintenance_request` (`name` заявки), opt `dust` (`round(max dust_pct/100, 3)`), `alarm_state` (стан моделі),
  `compliance`, `stale`. `state`: `alarm/prealarm/fault/disabled` → як є; `test` → `"test"`; інакше `warn` → `"warn"`;
  інакше `"ok"` (зокрема `unknown`, A-21).
- `totals` — `detectors` (Σ `n`), `mcp`, `sounders`, `flame` (активні пристрої типу), `spark_detectors`, `mcp_max_m`
  (`compliance_mcp_max_m`), `state` (`state_text`), `sprinkler` (`state_text` системи `SPRINKLERS`).
- `events` — 20 останніх (`ts desc`), `_payload_item()`.
- `panel` — `{code, state, state_text, comm, last_seen (local або null), alarms, faults, disabled, sounders, brigade}`.
- `systems` — `{"SPARK-1": {state, text, count_today}, "SMOKE-CTRL": {state, text, vents_open}, "SPRINKLERS": {state, text, pressure_bar}}`.
- `devices` — лише `P('viewer_devices')`: `{address: {type, x, y, z, zone (код зони або null), state, dust}}` (343).
Копія демо після установки (без колектора): `totals = {detectors: 212, mcp: 36, sounders: 41, mcp_max_m: 26.9,
flame: 3, spark_detectors: 4, state: "Зв'язок із приладом втрачено", sprinkler: "Спринклерна система в режимі
очікування"}`; `groups["FA-FAC"]`: `state "warn"`, `dust 0.861`, `warning` «Сповіщувач 2.FAC.07 біля шліфування:
запиленість камери 86 % — …», `maintenance_request` = «Очистити сповіщувач 2.FAC.07 (запиленість 82 %)»; `events` —
4 демо-події в порядку `demo:2`, `demo:1`, `demo:3`, `demo:4`.

### R-21 Розділ `evacuation` payload (`tools/payload.build_evacuation`)

Порядок ключів — як viewer A.13 + `drill_active`, `compliance`:
- `exits` — 12 у порядку `id` (= порядок макета): `{code, x, y, side, width, ok}`;
- `routes` — 32 за `zone_id.sequence`: `{zone_code: {name, exit, length, path, ok, norm}}`;
- `max_distance` = `evac_max_distance_m` (45.3), `worst_point` = `[evac_worst_x, evac_worst_y]` ([32.25, 33.75]);
- навчання для 3D: активне `running` навчання компанії, інакше шаблон за замовчуванням: `drill_origin` = код зони
  (`"FA-CNC"`), `drill_zone` = назва (`"Присадка"`), `drill_detector` = адреса (`"2.CNC.05"`);
- `norm_distance` = `N('evac_distance_prod_B')` (240), `norm_ref` = її `ref`; `norm_alt` = `N('evac_distance_polymer')`
  (50), `norm_alt_ref` = її `ref` (дослівно `norm_alt_ref` макета);
- `drill_steps` — кроки активного навчання (`t` = `t_plan_s`, `who`, `text`) або відрендерені кроки шаблону (8);
- `drill_active` — `null` або `{name, zone, zone_code, detector, started (local), elapsed_s, steps_done, steps_total,
  on_site, evacuated}`;
- `compliance` — `{routes_ok: 32, routes_total: 32, worst: 38.6, norm: 240, exits_ok: true, smoke_ok: 8, smoke_total: 8}`.

### R-22 Заявки ТО (FR-10, FR-12, A-16, A-28)

1. `maintenance.request.create` з `f3d_signal_id` сигналу модуля (M-14): сигнал — `dust_signal_id`/`state_signal_id`
   пристрою → `f3d_fire_device_id` = пристрій, `f3d_fire_zone_id` = його зона (пристрій має пріоритет над зоною для
   спільного сигналу запиленості); `zone.signal_id`/`dust_signal_id` → лише зона; шлейф/прилад/системи — без зони.
   `f3d_fire_event_id` = остання подія (≤ 10 хв) з `signal_id` = сигнал або з тим самим пристроєм/зоною й
   `kind ∈ {fault, dust, spark, smoke, sprinkler, loop}`; цій події `request_id` = заявка. До `description` додається
   рядок «Пожежна безпека: зона {z}{, пристрій {d}{ note}, BACnet LSP {lsp}}.».
2. Заголовки заявок telemetry (з `alarm_title` сигналів, Додаток B): зона — «Несправність зони FA-CUT (Розкрій): стан
   «fault»»; шлейф — «Несправність шлейфу 2 приладу FACP-1»; запиленість — «Очистити сповіщувач 2.FAC.07 (Дільниця
   фасадів МДФ): запиленість 90,1 % при нормі до 90»; іскрогасіння — «Несправність іскрогасіння SPARK-1 (пульт GreCon BS
   7)», «Іскрогасіння SPARK-1: немає тиску води гасіння»; щит — «Несправність щита димовидалення SMOKE-CTRL (D+H
   CPS-M1): АКБ або живлення». Емулятор при несправності сповіщувача дає дві заявки — зони й шлейфу (A-28).
3. Втрата зв'язку (R-12 п. 4): якщо `comm_request_id` відкрита (`stage_id.done=False`) — нічого; без `equipment_id`
   приладу — WARNING і без заявки; інакше `create({name: «Втрата зв'язку з приладом FACP-1: немає даних з {HH:MM} ({m}
   хв)», equipment_id, maintenance_type: 'corrective', maintenance_team_id: P('team_id') або команда обладнання або
   `factory3d.telemetry.default_team_id`, priority: '3', f3d_origin: 'fire_comm', request_date: today, schedule_date: now,
   description: «Автоматично: немає показань приладу FACP-1 (джерело BACNET-FACP-1) з {дата час Київ}; поріг
   {comm_lost_after_s} с.»})` → `comm_request_id`; подія `comm_lost.request_id`.

### R-23 Адреси пристроїв і BACnet LSP (A-09)

| Тип | Адреса | `lsp_instance` | Приклад |
|---|---|---|---|
| детектор зони | `<loop>.<code[3:]>.<nn>` (`nn` — порядок у `fire.detectors()[zone].points`, з 1) | `loop·10000 + lsz·100 + nn` | `2.FAC.07` → 21607; `2.CNC.05` → 21405; `1.RCV-1.01` → 10101; `2.BOILER.02` → 23302 |
| ручний | `<loop>.MCP.<nn>` (`nn` — порядок у `call_points()` у межах шлейфу `loop_of(x)`) | `loop·10000 + 90·100 + nn` | `1.MCP.01` → 19001; `4.MCP.09` → 49009 |
| оповіщувач | `<loop>.SND.<nn>` | `… + 91·100 + nn` | `2.SND.13` → 29113 |
| полум'я | `2.FLM.<nn>` | `… + 92·100 + nn` | `2.FLM.01` → 29201 |
| датчик іскор / форсунка / люк | `0.SPK.<nn>` / `0.NOZ.<nn>` / `0.SV.<nn>` | 0 | `0.SV.44` |

`@api.model lsp_id(loop, ordinal, nn)`: `1 ≤ loop ≤ 8`, `1 ≤ ordinal ≤ 99`, `1 ≤ nn ≤ 99`, інакше
`ValueError("LSP: шлейф 1…8, номер групи 1…99, номер 1…99")`; повертає `loop·10000 + ordinal·100 + nn`.
`device` в адресах сигналів = 200 (емулятор; прод — M-19).

### R-24 Обладнання сигналу за кодом (хук §5.4 п. 2)

`fire/groups/<FA>/…` → `<FA>`; `fire/loops/…`, `fire/totals/…` → `FACP-1`; `fire/spark/SPARK-1/…` → `SPARK-1`;
`fire/smoke/SMOKE-VENTS/…` → `SMOKE-VENTS`; `fire/smoke/SMOKE-CTRL/…` → `SMOKE-CTRL`; `fire/devices/<addr>/…` →
`equipment_id` пристрою. Немає обладнання в базі → `equipment_id` порожній, лічильник `missing` (заявки для такого
сигналу telemetry не створює — R-05 telemetry вимагає `equipment_id`).

## 10. Стани й переходи

### 10.1 Прилад `f3d.fire.panel.state` і зона `f3d.fire.zone.state`

Стани: `unknown` → (перше показання) → будь-який із `normal`, `prealarm`, `alarm`, `fault`, `disabled`, `test`; переходи
між будь-якими двома — за сигналом (R-10/R-11), без проміжних. Хто: `FireSync` (хук ingest або крон). Побічні ефекти:

| Перехід | Подія (R-14) | Інше |
|---|---|---|
| `* → alarm` (зона) | `alarm` | активність «Пожежна тривога: <зона>, сповіщувач <адреса>» групі охорони (FR-11, один раз на тривогу приладу — `alarm_activity_id`); R-18 п. 4; шина зони й `f3d.zone`; **без** заявки ТО |
| `* → prealarm` (зона) | `prealarm` | активність, як для `alarm`, summary «Передтривога: …» |
| `* → test` (зона) | `test` | R-18 п. 1–3 |
| `* → fault` (зона) | `fault` | заявку створює telemetry (`FAULT_STATES`) |
| `* → disabled` (зона) | `disabled` | — |
| `alarm/prealarm → normal` (зона) | `reset` | — |
| прилад `≠ normal → normal` | `reset` (прилад) | `_close_alarm_activity()` («Прилад скинуто») |
| `* → unknown` | — | не відбувається (немає показань → стан лишається, `stale=True`, A-17) |

### 10.2 Зв'язок `comm`

`lost` (умовчання, `first_sync`) → `online` (перше показання; `comm_restored`); `online → stale` (вік > 90 с;
`comm_stale`); `stale → lost` / `online → lost` (вік > 180 с; `comm_lost`, активність, заявка); `stale/lost → online`
(`comm_restored`, активність закрито); будь-який → `off` (стоп-кран або джерело `read_enabled=False`; без подій);
`off → online/stale/lost` за R-12 при наступній звірці.

### 10.3 Пристрій, запиленість, шлейф, система

- Пристрій `state` — лише для пристроїв з `monitor=True` (інші лишаються `unknown`); переходи — `DEVICE_MAP`.
- `dust_state`: `na → ok/warn/alarm` (перше показання; подія лише `na → warn/alarm`), `ok ↔ warn ↔ alarm` (R-13 п. 3).
- Шлейф: `unknown → ok/fault`, `ok ↔ fault` (`loop_fault`/`loop_ok`; `fault_since`).
- Система: `unknown/ok/active/fault/battery/low_pressure` за R-13; `→ unknown` лише через `stale` усіх сигналів (R-12 п. 7).

### 10.4 Навчальна тривога `f3d.fire.drill.state`

| З | У | Хто / що | Умови | Побічні ефекти |
|---|---|---|---|---|
| `draft` | `planned` | `action_plan` (D) | `planned_ts`, `zone_id` | чаттер |
| `draft`/`planned` | `running` | `action_start`/`action_start_sim` (D), R-18 (прилад, `sudo`) | немає іншого `running` | R-15; для `sim` — `f3d.sim.run` |
| `running` | `evaluating` | `action_stop` (D), авто-стоп R-16 п. 7 (крон) | — | R-16 п. 4; зупинка `f3d.sim.run` |
| `evaluating` | `done` | `action_close` (D) | `result`, `conclusions` | — |
| `draft`/`planned`/`running` | `cancelled` | `action_cancel` (D) | — | для `running`: `end_ts=now`, зупинка `sim` |
| `cancelled` | `draft` | `action_reset_draft` (D) | — | очищення полів, видалення людей |
| `done` | — | — | кінцевий; редагуються лише `conclusions`, `remarks`, `print_names` (`readonly` інших полів у V-17 при `state == 'done'`) | — |

Крок: `done=False → True` (авто R-17 або `action_done_now`); `True → False` лише для `done_by='manual'` (`action_undo`).
Людина: `on_site → evacuated` (прохід) або після `action_stop` → `missing`; `missing → present` (перекличка);
`missing ↔ absent` — `rollcall='absent'` лишає `missing`.

### 10.5 Подія журналу

`ack=False → True` (`action_ack`, будь-який `U`), назад — ні. Інших станів немає; запис незмінний (A-33).

## 11. Обробка помилок

| Ситуація | Поведінка |
|---|---|
| Прилад не відповідає (Who-Is/RPM таймаут) | telemetry: джерело `error`, сигнали `stale` (R-07 telemetry); модуль: R-12 (`stale` → `lost` → подія, активність, заявка); стани зон — останні відомі з `stale=True` (A-17); payload — `totals.state` «Зв'язок із приладом втрачено», `groups[*].stale=true` |
| ADAM u85 недоступний | системи `spark`/`smoke` → `unknown`, подія `comm_lost` (warn), заявки немає (R-12 п. 7) |
| Невідомий текст стану LSZ/LSP | стан `unknown`, `raw_state` = текст, WARNING один раз на `(code, текст)` за процес (`functools.lru_cache`); подія не пишеться |
| Показання `q='bad'` | ігнорується моделями (R-19 п. 3) |
| Дублікати показань/подій | telemetry `ON CONFLICT`; журнал — унікальний `dedup_key` + `savepoint` (M-05 `_log` п. 7); звірка порівнює зі збереженим `raw_state` |
| Паралельні воркери (push і крон одночасно) | `FireSync` пише стани ORM-ом; конфлікт серіалізації PostgreSQL → повтор транзакції Odoo (стандарт); ключ дедуплікації не дає подвійних подій |
| Виняток у синхронізації після push | `savepoint` + `_logger.exception`; push telemetry успішний; крон наздожене за ≤ 60 с (A-22) |
| Немає обладнання base (чиста база) | хук `missing: 42` (WARNING); заявки telemetry не створюються (немає `equipment_id`); заявка зв'язку — WARNING і пропуск (R-22 п. 3); модуль працює |
| Немає сигналу тиску спринклерів | система `SPRINKLERS` `unknown`, `totals.sprinkler` «Спринклерна система: немає даних тиску» |
| Немає `factory3d_viewer` | `_notify` не викликається (`'f3d.viewer.event' in env`); провайдерів немає (міст не встановлено); `action_f3d_show` — повідомлення CB-02 |
| Немає `factory3d_iot_sim` | `sim_available=False`, кнопка прихована; виклик методу → `UserError("Модуль емулятора не встановлено.")` |
| Емулятор відхилив сценарій | `f3d.sim.run.state='failed'` → `UserError` з `message`; навчання лишається `draft/planned` |
| Немає `factory3d_access` | M-12a (`hr.attendance`); кроки `doors` — вручну; `_f3d_is_active_at` лишається доступним (його ніхто не викликає) |
| Джерело проходів кидає виняток | `_tick` логує `_logger.exception`, проходи цієї ітерації пропускаються, навчання триває; на старті — `UserError("Джерело проходів <ключ> недоступне: …")` |
| Норма не задана (`value_set=False`) | правило → `compliance='na'` з нотаткою; звіт показує «норма не задана» |
| Невалідний payload `bacnet_event` | `ValueError` → telemetry `f3d.push.event.error`; модель не змінюється |
| Невалідний `path`/контур/адреса | `ValidationError` з текстом (§2) — і в UI, і в data (установка падає — захист від зіпсованого генератора) |
| Часові пояси | усе в БД — UTC naive; відображення й тексти — Europe/Kyiv (`tools/dates.local`); «за добу» лічильника іскор — доба приладу (скидання лічильника ADAM), модуль лише фіксує зменшення без події; `planned_ts` вводиться в поясі користувача (стандарт Odoo); демо-події макета («2026-10-12 09:58» Київ) → UTC −3 год (EEST) |
| Прискорення емулятора (`factor > 1`, iot_sim §9.4) | `ts` показань — час читання колектора (реальний), тож кроки навчання стискаються пропорційно; ТК виконуються з `factor=1` |
| Друге `running` навчання | `ValidationError` (M-11) або `UserError` (R-15 п. 1) |
| Видалення події/навчання не в `draft` | `UserError` (M-05, M-11) |
| Спроба запису в прилад будь-яким шляхом Odoo | `ValidationError` (M-15) — незалежно від групи й `sudo`; на рівні колектора — `NotSupported` (§8 п. 4) |

## 12. Acceptance Criteria

Тип перевірки: UT — юніт-тест Odoo (§13.1), TC — стенд на емуляторі (§13.2), MAN — ручна перевірка в протоколі.
«Чиста база» — база з `factory3d_base`, `factory3d_telemetry`, `hr_attendance` без демо-даних обладнання; «копія демо» —
копія бази `odoo` тестового сервера (14.10.2026).

| AC | FR / правило | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-20, §5.2 | Given чиста база; When модуль встановлено; Then `f3d.fire.norm` 27; `panel` 1; `loop` 4; `zone` 33 (`kind`: smoke 23, multi 9, heat 1); `device` 343 (smoke 128, multi 82, heat 2, mcp 36, sounder 41, flame 3, spark_detector 4, spark_nozzle 3, smoke_vent 44); `system` 3; `smoke.zone` 8; `exit` 12; `route` 32 (Σ точок `path` = 132); шаблон 1 з 8 кроками; джерел модуля 2 (`f3d_fire_readonly=True`, `write_enabled=False`, `params.read_only` у BACnet); сигналів із `module='fire_safety'` 53 (52 data + запиленість), усі `write_enabled=False` | UT |
| AC-02 | FR-20, §5.4 | Given копія демо; When установка; Then `migration_report`: `state=done`, `linked=42`, `missing=0`, `devices_linked=343`, `signals_linked=52`, `dust_signal=reused` (id = `factory3d_telemetry.sig_fire_groups_fa_fac_dust`), `requests_linked=1` (заявка id 5: `f3d_fire_zone_id=FA-FAC`, `f3d_fire_device_id=2.FAC.07`), `events_demo=4`, `drills_demo=1` (людей 35, `evac_time_s=240`); `2.FAC.07.dust_pct=86.1`, `dust_state='warn'`, `FA-FAC.warn=True`; `comm='lost'` без подій `comm_*` | TC |
| AC-03 | FR-20 | Given модуль встановлено; When `hooks.run_all(env)` ще двічі; Then кількості всіх моделей AC-01 незмінні, подій демо 4, демо-навчань 1, сигналів модуля 53, нових `maintenance.request` 0 | UT |
| AC-04 | FR-20 | Given чиста база; Then `state=partial`, `missing=42`, `dust_signal=created` (сигнал без запису `ir.model.data`), `pressure_signal=False`, `SPRINKLERS.state='unknown'` | UT |
| AC-05 | FR-07, R-01 | Given data; When `action_recompute_compliance`; Then `n_required` 33 зон = Додаток A.1 (`FA-SHEETS` 24, `FA-FAC` 18, `FA-EDGE` 3, `FA-BOILER` 2), усі `n_ok=True` | UT |
| AC-06 | FR-07, R-01, M-08 | When `norm_smoke_spacing_6_12m.value = 6.0`; Then `panel.compliance_dirty=True`; після перерахунку `FA-CUT.n_required=24`, `compliance='fail'`; повернути 8,8 → `ok` | UT |
| AC-07 | FR-07, R-02 | Then `FA-FG.cover_max_gap_m=6.26`, `cover_point="(122.0, 54.1)"`, `compliance='ok'`; `FA-SHEETS` 5.02 у "(14.6, 0.6)"; `cover_tol_m=0.03` → `FA-FG` `warn`, інші 32 `ok`; усі детектори `FA-RCV-1` архівовано → `fail` | UT |
| AC-08 | FR-07, R-03 | Then `compliance_mcp_max_m=26.9`, `compliance_mcp_point="(60.0, 72.0)"`, `compliance_mcp_ok=True`; `1.MCP.08.active=False` → 32.0, "(32.0, 72.0)", `False` | UT |
| AC-09 | FR-07, R-04 | Then `compliance_sounder_max_m=45.2`; `compliance` зон і `compliance_mcp_ok` від нього не залежать | UT |
| AC-10 | FR-07, R-08 | Then `compliance_missing_zones == "Z-OFFICE, Z-SOC"`; створити зону сигналізації для `Z-SOC` → `"Z-OFFICE"` | UT |
| AC-11 | FR-07, M-08 | Then `get('smoke_spacing_6_12m')=8.8`, `get('smoke_area_6_12m') is None`, `get('mcp_spacing')=30.0`, `get('exit_dispersal_k')=1.5`; 20 ключів JSON макета присутні; `key='Bad-Key'` → `ValidationError` | UT |
| AC-12 | FR-05, R-14 | When `_log('fault','FA-CUT',T,…)` двічі з `T` і `T+1 с` (той самий 2-с кошик) → 1 запис; `T+3 с` → 2 записи | UT |
| AC-13 | FR-05, A-33 | Given подія; When `U` пише `text` → `AccessError`; `U` пише `note`/`ack` → успіх; `unlink` від `A` і `sudo()` → `UserError` | UT |
| AC-14 | FR-05 | `U` створює подію → `AccessError`; `D` створює `etype='manual'` → успіх (`level='info'`, `dedup_key` починається з `manual:`); `D` створює `etype='alarm'` → `AccessError` | UT |
| AC-15 | FR-11 | `action_ack` → `ack=True`, `ack_user_id=uid`, `ack_ts` заповнено; `write({'ack': False})` → `UserError`; `ack_required=True` для `level='alarm'` | UT |
| AC-16 | FR-05, R-14 п. 4 | текст 600 символів з `\x00\x07` → збережено ≤ 500 без керівних символів; `_payload_item()` для `alarm` → `level='bad'`, `time` у форматі `YYYY-MM-DD HH:MM` за Києвом | UT |
| AC-17 | FR-03, FR-11, R-11 | When `push_text('fire/groups/FA-CUT/state','alarm')`; Then `FA-CUT.state='alarm'`, подія `alarm` «ТРИВОГА: зона FA-CUT (Розкрій)», на `FACP-1` по одній активності типу `mail_act_fire_alarm` кожному активному користувачу групи `alert_group_xmlid`; `maintenance.request` для сигналу зони **не** створено; When LSZ:0 і зона → `quiet`; Then події `reset` (зона, прилад), відкритих активностей цього типу 0 | UT |
| AC-18 | R-11 | `tools.states`: 24 тексти дають `ZONE_MAP`/`DEVICE_MAP`/`FAULT_STATES` за таблицею R-11; `"9"` → `test`; `"xyz"` → `unknown` | UT |
| AC-19 | FR-01, R-10 | LSZ:0 `quiet` + MSV:1 `1` → `normal`; LSZ:0 `quiet` + MSV:1 `3` → `fault`; `test-alarm` + `4` → `test`; `state_text`: `normal` + 1 зона `warn` → «Норма, 1 попередження»; 5 зон → «Норма, 5 попереджень»; `comm='lost'` → «Зв'язок із приладом втрачено» | UT |
| AC-20 | FR-10, R-13 | `push_value(dust, 82)` → `2.FAC.07.dust_state='warn'`, `FA-FAC.warn=True`, `warning` дорівнює тексту R-13 п. 4 з «82 %», подія `dust_warn`; `90.1` → `alarm`, подія `dust_alarm`, telemetry створила заявку з `f3d_fire_device_id=2.FAC.07` і командою з `team_id`; `79` → `ok`, `dust_ok`, `warning=False` | UT |
| AC-21 | FR-12, R-12 | (freezegun) Given `first_sync`; без показань → `comm='lost'`, подій 0; показання → `online`, `comm_restored`; +100 с → `stale`, `comm_stale`; +185 с → `lost`, `comm_lost`, активність, заявка «Втрата зв'язку з приладом FACP-1: немає даних з HH:MM (3 хв)» з `f3d_origin='fire_comm'`; ще цикл `online→lost` при відкритій заявці → нових заявок 0; показання → `online`, активність закрита, заявка відкрита | UT |
| AC-22 | FR-19 | `read_enabled=False` → після крона `comm='off'`; `push_text` зони → стан зони не змінився, подій 0; `build_fire()['totals']['state'] == "Обробка вимкнена"` | UT |
| AC-23 | FR-02, R-11 | `push_text('fire/loops/2/state','on')` → `loop_2.state='fault'`, `fault_since`, подія «Несправність шлейфу 2 приладу FACP-1»; `'off'` → `ok`, `loop_ok` | UT |
| AC-24 | FR-06, R-13 п. 5 | `count_today` 0 → 2 → подія `spark` «…(2 шт.), гасіння спрацювало; за добу — 2.»; 2 → 0 → подій 0; DI2 `on` → `fault`, `spark_fault`; DI3 `low` → `fault`, `state_text` містить «немає тиску води»; усі сигнали `stale` → `unknown`, `comm_lost` (warn) | UT |
| AC-25 | FR-06, R-13 п. 6–7 | DI4 `open` → `SMOKE-CTRL.state='active'`, `smoke_open` «(44 шт.)»; DI6 `battery` → `battery`; DI5 `fault` → `fault`; тиск спринклерів 6,2 (`alarm_low` 6,5) → `low_pressure`, текст «тиск 6,2 бар нижче норми 6,5 бар»; 7,2 → `ok`, `sprinkler_ok` | UT |
| AC-26 | R-19, A-22 | `env['f3d.signal']._f3d_ingest([{code:'fire/groups/FA-EB/state', ts, text:'fault'}], src='module')` → у тій самій транзакції `FA-EB.state='fault'`, подія `fault`; ingest коду `equipment/COMPRESSOR/pressure_bar` → `FireSync.run` не викликано (mock); `FireSync.run` кидає виняток → `_f3d_ingest` повертає результат без винятку | UT |
| AC-27 | R-19, A-17 | `run(full=True)` двічі → другий раз `changed=0`, `events=0`; сигнал зони `status='stale'` → `stale=True`, `state` незмінний | UT |
| AC-28 | FR-18, M-15 | `BACNET-FACP-1.sudo().write({'write_enabled': True})` → `ValidationError`; `write({'f3d_fire_readonly': False})` → `ValidationError`; `params` без `read_only` → `ValidationError`; `create` джерела з `f3d_fire_readonly` і `write_enabled` → `ValidationError` | UT |
| AC-29 | FR-18 | сигнал `module='fire_safety'` `sudo().write({'write_enabled': True})` → `ValidationError`; сигнал іншого модуля з джерелом `f3d_fire_readonly` → `ValidationError` | UT |
| AC-30 | FR-18 | `f3d.command.sudo().create({'signal_id': <сигнал fire>})` → `ValidationError`; команда для сигналу не пожежного джерела не блокується цим модулем | UT |
| AC-31 | FR-18, A-03 | параметра `factory3d.fire_safety.write_enabled` немає; жодне `ir.ui.view`, `ir.actions.server`, `ir.cron` модуля (за `ir.model.data` `module='factory3d_fire_safety'`) не містить `f3d.command`, `action_request_write`, `write_enabled` у значенні `True`; у `res.config.settings` немає поля з `write` у назві з префіксом `f3d_fire_` | UT |
| AC-32 | FR-10, R-22 | telemetry (через `_f3d_ingest` `fault`) створила заявку для `fire/groups/FA-CUT/state` → `f3d_fire_zone_id=FA-CUT`, `f3d_fire_event_id` = подія `fault`, `maintenance_team_id` = `team_id`, в `description` рядок «Пожежна безпека: зона FA-CUT (Розкрій).»; повтор `fault` поки заявка відкрита → нових заявок 0 | UT |
| AC-33 | FR-08, R-05 | 32 маршрути `ok`; найдовший `Z-PRE` 38,6; `polymer_panels=True` → `norm_m=50`, 32 `ok`; `evac_distance_prod_B=30` → `compliance_routes_ok=26`, `fail` = {Z-RCV-4, Z-SHEETS, Z-PRE, Z-MAINT, Z-FG, Z-OUT-4} | UT |
| AC-34 | FR-08, R-06 | `compliance_exit_l_m=31.6`, `compliance_exit_pair_m=145.1`, `nearest_exit_m` EX-S4 = 7,4, EX-S1 = 37,0; архівувати всі, крім EX-S4 і EX-IN → `compliance_exits_ok=False` | UT |
| AC-35 | FR-08, R-07 | `EX-S1.width_m=0.7` → `EX-S1.compliance='fail'`, маршрути Z-RCV-1…4 і Z-SHEETS `width_ok=False`, `fail` | UT |
| AC-36 | FR-09, R-09 | 8 димових зон: `need_vents` = таблиця R-09, Σ 44, усі `ok`; `0.SV.01.active=False` → SZ-1 `warn`; `SZ-1.x1=25` → `fail`; `x1=200` → `ValidationError` | UT |
| AC-37 | FR-08, M-09/M-10 | `EX-S3` (68.5, 0.0, S, 1.2); маршрут `Z-CNC` → EX-S3, 29,8 м, 3 точки; `panel.evac_max_distance_m=45.3`, `evac_worst_x/y=32.25/33.75`; `path` з точкою x=200 → `ValidationError`; кінець шляху за 5 м від виходу → `ValidationError` | UT |
| AC-38 | FR-08 | HTML звіту V-20 (`_render_qweb_html`) містить 32 рядки маршрутів, «38,6», «31,6», «145,1», «26,9», «Z-OFFICE, Z-SOC», 8 рядків димових зон | UT |
| AC-39 | FR-22 | `Z-CNC`: `f3d_fire_kind='multi'`, `f3d_evac_exit_code='EX-S3'`, `f3d_evac_length_m=29.8`; `FA-CNC.state='alarm'` → `Z-CNC.f3d_fire_state='alarm'`; `Z-OFFICE`: `f3d_fire_zone_count=0`, `f3d_fire_state=False` | UT |
| AC-40 | FR-08 | вихід (75, 30) → `ValidationError` «…на зовнішній стіні»; другий маршрут для `Z-CUT` → `IntegrityError`; `route.action_f3d_show()` при встановленому viewer (патч CB-02) → `params.code == 'EVAC-CNC'` | UT |
| AC-41 | FR-13, M-11 | новий навчання → `name` відповідає `^DRILL/\d{4}/\d{4}$`; 8 кроків; крок 1 «Сповіщувач 2.CNC.05 (Присадка): дим і тепло — тривога на приладі.», крок 2 «Увімкнено 41 сирен-маяків по всьому цеху.» | UT |
| AC-42 | FR-13, §10.4 | переходи таблиці §10.4; `action_close` без `result` → `UserError` «Оберіть результат навчання.»; без `conclusions` → `UserError`; `planned` без `planned_ts` → `ValidationError`; друге `running` → помилка; `unlink` `running` → `UserError` | UT |
| AC-43 | FR-13, R-15 | 3 відкриті відмітки до старту, 1 закрита до старту, 1 після старту → `on_site_count=3`, `passage_source='hr_attendance'`, подія `drill_start` | UT |
| AC-44 | FR-13, R-16 | 2 з 3 відмітили вихід на +95 і +140 с → після `_tick` `exit_ts`; `action_stop` → `evac_time_s=140`, `missing_count=1`, `result_suggested='failed'`; перекличка (присутній) → `present_count=1`, `evac_pct=100.0`, `data_quality='partial'`, `result_suggested='remarks'`; `action_close` з результатом → `done` | UT |
| AC-45 | FR-13, R-17 | події зони `test` +2 с, `sounders_on` +4 с, `smoke_open` +11 с → кроки 1, 2, 5 `done`, `t_fact_s` 2/4/11, `done_by='auto'`; крок 3 (`brigade`) не відмічено; `action_done_now` у `draft` → `UserError` | UT |
| AC-46 | FR-14, R-18 | заплановане навчання FA-CNC на T+10 хв; `test-alarm` FA-CNC у T → воно `running`, `start_ts` = `last_ts` сигналу; без плану → створено `origin='panel'`, `title="Тест приладу: Присадка"`, подія `drill_auto`; `drill_auto_create=False` → навчань 0 | UT |
| AC-47 | FR-14, R-18 п. 4 | навчання `running`; `alarm` у FA-CUT → `real_alarm=True`, подія `drill_real_alarm`, активність охороні; без `running` справжня тривога навчання не створює | UT |
| AC-48 | FR-13, R-16 п. 7 | події зони навчання `test` (T0) і `test_end` (T0+300); `_tick` о T0+450, `drill_auto_stop_s=120` → `evaluating`, `end_ts=T0+300`; `mode='tabletop'` → лишається `running` | UT |
| AC-49 | FR-23 | без iot_sim: `sim_available=False`, `action_start_sim` → `UserError`; з підміною `_f3d_sim_create_run` (повертає запуск `RUN/2026/0007`, `state='running'`) → параметри виклику `{"zone":"FA-CNC","detector":"2.CNC.05","real":false,"duration_s":300}`, `sim_run_ref='RUN/2026/0007'`, `state='running'`; підміна з `state='failed'` → `UserError` | UT |
| AC-50 | FR-24 | `U` (без `D`/`H`) `f3d.fire.drill.person.search([])` → `AccessError`; `H` — читає; HTML протоколу без `print_names` не містить жодного `employee_id.name`, з `print_names` — містить | UT |
| AC-51 | FR-13 | HTML звіту V-21 містить `name`, 8 рядків кроків, «Персональний список не друкується» | UT |
| AC-52 | FR-13 | `_cron_tick()` без `running` нічого не змінює; з `running` у тестовому режимі виконує рівно одну ітерацію `_tick` | UT |
| AC-53 | CF-02, M-12, M-12a | `_f3d_on_site`/`_f3d_passages` над синтетичними відмітками; без access і без контексту тестового джерела `_f3d_get_source()` → `hr_attendance` (`_f3d_source_key` = `hr_attendance`); моделі `f3d.fire.passage.source.access` цей модуль не створює (`'f3d.fire.passage.source.access' not in env`, якщо access не встановлено) | UT |
| AC-54 | A-19, M-12 | (тестовий модуль §0.3) модель `f3d.fire.passage.source.zz_test` **без** `_inherit` (пріоритет 5, без `_f3d_on_site` і `_f3d_key`): з контекстом `f3d_test_passage_source=True` `_f3d_get_source()` повертає її, ключ `zz_test`; `_f3d_people_at` будує людей із проходів (останній `in` без `out`); навчання з нею: `passage_source='zz_test'`, виходи `direction='out'` дають `exit_ts`, `in` ігноруються; без контексту (`_f3d_available()` → `False`) → `hr_attendance`; якщо в базі встановлено access — `'f3d.fire.passage.source.access'` знайдено за префіксом із пріоритетом 10 (`skipUnless`) | UT |
| AC-55 | FR-15, R-20 | `build_fire()` (чиста база): порядок ключів, `rules` 10 ключів (`smoke_spacing_6_12m` 8.8, `mcp_spacing` 30, `smoke_area_6_12m` null), `loops` = R-20, 33 `groups` з ключами A.13, `totals` 212/36/41/26.9/3/4; `json.dumps` без помилок | UT |
| AC-56 | FR-15, A-21 | `FA-CUT` `unknown` → `state="ok"`, `alarm_state="unknown"`, `stale`; `alarm` → `"alarm"`; запиленість 86,1 → `FA-FAC.state="warn"`, `dust=0.861`; відкрита заявка → `maintenance_request` = її `name` | UT |
| AC-57 | FR-15, R-21 | `build_evacuation()`: 12 `exits`, 32 `routes` (`Z-CNC.exit="EX-S3"`), `norm_distance=240`, `norm_alt=50`, 8 `drill_steps`, `drill_active=null`, `drill_origin="FA-CNC"`; при `running` навчанні FA-CUT → `drill_active.zone_code="FA-CUT"`, `drill_origin="FA-CUT"` | UT |
| AC-58 | FR-15, CF-04 | (міст-модуль, viewer встановлено) провайдери 130/140 у реєстрі; `PayloadBuilder` → `meta.sections.fire/evacuation='live'`; зміна стану `FA-CUT` → `f3d.viewer.event` з `model='f3d.fire.zone'`, `codes=['FA-CUT']`; `DeltaBuilder(since=до зміни)` → `patch.fire` присутній | UT |
| AC-59 | FR-15, FR-19 | `viewer_devices=True` → `fire.devices` 343 ключі, `devices["2.FAC.07"].dust=0.861`; `read_enabled=False` → `totals.state="Обробка вимкнена"` | UT |
| AC-60 | §5.5 | `uninstall_hook(env)` → сигнал запиленості існує з `source_id=False`, `address={}`; параметрів `factory3d.fire_safety.*` 0 | UT |
| AC-61 | FR-19, FR-24 | `neutralize.sql` виконується без помилки; `read_enabled='False'`, крони модуля `active=False`, джерела модуля `read_enabled=False`, `employee_id` людей навчань NULL, `sim_run_ref` NULL, активностей «Пожежна тривога» 0, `comm='off'` | UT |
| AC-62 | FR-07, §5.4 п. 8 | після установки: `compliance_zones_ok=33`, `compliance_mcp_max_m=26.9`, `compliance_routes_ok=32`, `compliance_exits_ok=True`, `compliance_smoke_ok=8`, `compliance_missing_zones="Z-OFFICE, Z-SOC"`, `compliance_dirty=False` | UT |
| AC-63 | FR-16 | меню §3: `menu_f3d_fire_root` (батько `factory3d_base.menu_f3d_root`, `sequence=85`, група `U`) і 16 дочірніх із sequence/групами таблиці; дії відкривають вказані моделі | UT |
| AC-64 | FR-17 | матриця §4.1: `U` читає зони, `write` → `AccessError`; `U` `create` навчання → `AccessError`; `D` створює навчання й читає людей; `M` пише норму, `unlink` норми → `AccessError`; `A` — успіх; `H` читає людей; `unlink` події будь-ким → помилка; `M` має групу `D` через `implied_ids` | UT |
| AC-65 | FR-21 | `res.config.settings`: збереження/читання 16 параметрів; `dust_warn ≥ dust_alarm` → `UserError`; зміна порогів запиленості → `warn_high/alarm_high` сигналів `…/dust`; група сповіщення зберігається як xml-id; полів із `write` у назві немає | UT |
| AC-66 | FR-04, A-02 | `M`: `2.CUT.01.action_create_signals()` → 2 сигнали `fire/devices/2.CUT.01/state` і `/dust` з адресами `{"device":200,"object":"LSP","instance":21201,"mode":"poll"}` / `AV`, `write_enabled=False`, `module='fire_safety'`; повтор → створено 0; `U` → `AccessError`; `action_remove_signals` → сигнали `active=False`, `monitor=False` | UT |
| AC-67 | FR-11 | 2 користувачі групи сповіщення → по одній активності на тривогу; друга зона в тривозі при відкритій активності → нових активностей 0; скидання приладу → усі закриті (`action_feedback` «Прилад скинуто») | UT |
| AC-68 | M-18, R-14 п. 5 | payload API-01 (LSZ 14, `test-alarm`, «Тест: сповіщувач 2.CNC.05, Присадка») за 3 с від події `test` FA-CNC → `message_text` дописано, `device_id=2.CNC.05`; без події → нова подія `bacnet`; без `instance` → `ValueError`; керівні символи в `message_text` видалено | UT |
| AC-69 | FR-07 | `action_recompute_compliance()` повертає `display_notification` з текстом «Перераховано: зони 33/33, ручні max 26,9 м, маршрути 32/32, димові зони 8/8»; `compliance_ts` заповнено; `_cron_compliance()` дає ті самі значення | UT |
| AC-70 | FR-04, R-23 | `lsp_id(2,16,7)=21607`, `lsp_id(1,90,1)=19001`, `lsp_id(9,1,1)` → `ValueError`; у data 292 пристрої C-NET з унікальним `lsp_instance > 0`, 51 — з 0; адреса `3.FAC.01` для пристрою шлейфу 2 → `ValidationError` | UT |
| AC-71 | FR-20 | `tools/gen_data.py` у тимчасову теку → файли побайтово дорівнюють `data/*` репозиторію | UT (pytest) |
| AC-72 | FR-01, P-09 | стенд (ТК-01): колектор читає dev 200 і u85; за ≤ 2 хв `comm='online'`, 33 зони `normal`, `FA-FAC.warn` за запиленістю емулятора, подія `comm_restored` | TC |
| AC-73 | FR-13, FR-23 | стенд (ТК-04): навчання «Запустити на емуляторі» → крок 1 `t_fact_s ≤ 15`, крок 2 ≤ 18, крок 5 ≤ 24; авто-стоп; протокол PDF | TC |
| AC-74 | FR-18 | стенд (ТБ-05): за весь прогін ТК-01…ТК-10 у перехопленні UDP 47808 немає жодного `WriteProperty`, `WritePropertyMultiple`, `SubscribeCOV`, `AcknowledgeAlarm`, `LifeSafetyOperation`, `DeviceCommunicationControl`, `ReinitializeDevice` від колектора; на TCP 502 unit 85 — жодної функції 05/06/15/16 | TC |
| AC-75 | CF-06 (access CA-09) | навчання `done` 10:00:00–10:05:30 → `_f3d_is_active_at(10:03)` = `True`, `(10:06)` = `False`, `(09:59)` = `False`; `running` зі стартом 10:00 → `(11:00)` = `True`; `planned` на 10:00 → `False`; виклик від користувача без прав на навчання (через `sudo` у методі) не кидає `AccessError` | UT |

## 13. План тестування (для Opus)

### 13.1 Юніт-тести (`odoo.tests`, теги `post_install`, `-at_install`, `f3d`, `f3d_fire`)

Запуск: `odoo-bin -d f3d_fire_test -i factory3d_fire_safety,test_factory3d_fire_safety --test-tags /factory3d_fire_safety
--stop-after-init --without-demo=all` (чиста база); міст-модуль — `-i factory3d_fire_safety_viewer --test-tags
/factory3d_fire_safety_viewer`; `test_data_sync.py` — `pytest odoo_addons/factory3d_fire_safety/tests/test_data_sync.py`
з кореня репозиторію. Час — `freezegun.freeze_time` (залежність тестів Odoo).

`tests/common.py` — `class FireCase(TransactionCase)`, `setUpClass`:
- записи data: `cls.panel = env.ref('factory3d_fire_safety.panel_facp_1')`, `cls.z_cut/z_eb/z_cnc/z_fac/z_fg/z_rcv1`
  (`fire_zone_fa_*`), `cls.dev_fac07 = …dev_2_fac_07`, `cls.dev_cnc05`, `cls.loop2`, `cls.src_bac`, `cls.src_io`,
  `cls.sys_spark`, `cls.sys_smoke`, `cls.sys_spr`, `cls.tpl = …drill_template_default`;
- обладнання (чиста база не має демо): `maintenance.team` «Тестова команда ПБ» → `cls.team`; `maintenance.equipment`
  з `f3d_code` `FACP-1`, `FA-CUT`, `FA-EB`, `FA-CNC`, `FA-FAC`, `SPARK-1`, `SMOKE-CTRL`, `SPRINKLERS` (команда
  `cls.team`); потім `hooks.equipment.link(env)` — сигнали й моделі отримують `equipment_id`;
- сигнал тиску спринклерів (якщо немає): `f3d.signal` `equipment/SPRINKLERS/pressure_bar`, `kind='gauge'`,
  `alarm_low=6.5`, `alarm_low_on=True`, `module='telemetry'`, `equipment_id=SPRINKLERS`; знову `hooks.equipment.link`;
- параметри: `read_enabled=True`, `team_id=cls.team.id`, `alert_group_xmlid` = тестова група `cls.g_alert`
  (`res.groups` + `ir.model.data` `test_fire.group_alert`) з 2 користувачами `cls.guard1`, `cls.guard2`;
- користувачі: `cls.u` (`base.group_user` + `group_f3d_user`), `cls.d` (+ `group_f3d_fire_drill`), `cls.m`
  (`group_f3d_manager`), `cls.a` (`group_f3d_admin`), `cls.hr` (`hr.group_hr_user` + `group_f3d_user`);
- хелпери: `T0 = datetime(2026, 10, 14, 7, 0, 0)` (UTC naive); `at(s)` = `T0 + timedelta(seconds=s)`;
  `push_text(code, text, ts)` / `push_value(code, value, ts)` → `env['f3d.signal']._f3d_ingest([...], src='module')`
  (з `freeze_time(ts + 1 с)`, щоб не спрацював `ts_future`); `sync()` → `panel._f3d_fire_sync(full=True)`;
  `ev(etype, **dom)` → `search` подій; `make_employee(name, code=None)`; `make_att(emp, check_in, check_out=None)`;
  `new_drill(**vals)` (від `cls.d`); `viewer_installed(flag)` (патч CB-02, як base `common.py`).

| Файл / клас | Тести | AC | Фікстури | Що assert |
|---|---|---|---|---|
| `test_hooks.py::TestInstallData` | `test_counts`, `test_kinds`, `test_sources_readonly`, `test_signals_readonly`, `test_dust_created_clean` | AC-01, AC-04 | data | точні кількості §5.2; `f3d_fire_readonly`, `params['read_only']`; 53 сигнали `module='fire_safety'` з `write_enabled=False`; `ir.model.data` для сигналу запиленості відсутній; `migration_report.state == 'partial'`, `missing == 42` (до створення фікстур обладнання — тест читає звіт установки) |
| `::TestRerun` | `test_run_all_idempotent` | AC-03 | — | `search_count` усіх моделей до/після двох `run_all`; подій `demo:*` 4 |
| `::TestUninstallNeutralize` | `test_uninstall_hook`, `test_neutralize_sql` | AC-60, AC-61 | навчання `done` з людиною; активність тривоги | після `uninstall_hook(env)` — сигнал запиленості `source_id=False`, `address == {}`; параметрів 0; `cr.execute(open(neutralize.sql).read())` → значення AC-61 (через SQL `SELECT`) |
| `::TestCompliance` | `test_after_install`, `test_notification` | AC-62, AC-69 | — | значення AC-62; рядок повідомлення AC-69 дослівно |
| `test_norms.py::TestRequired` | `test_table`, `test_change_spacing` | AC-05, AC-06 | Додаток A.1 як Python-словник | `n_required`, `n_ok`; `compliance_dirty`; `FA-CUT` 24 / `fail` |
| `::TestCoverage` | `test_gaps`, `test_tolerance_warn`, `test_no_detectors` | AC-07 | `set_param('cover_tol_m','0.03')`; архівація | `assertAlmostEqual(…, 6.26, 2)`, рядок точки; `compliance` |
| `::TestMcpSounder` | `test_mcp`, `test_mcp_archived`, `test_sounder_informative` | AC-08, AC-09 | архівація `1.MCP.08` | 26.9/"(60.0, 72.0)"; 32.0/"(32.0, 72.0)"; 45.2 |
| `::TestMissingZones`, `::TestNormModel` | `test_missing`, `test_get`, `test_key_regex`, `test_json_keys_present` | AC-10, AC-11 | зона для `Z-SOC` | рядки; значення; `ValidationError` |
| `::TestAddresses` | `test_lsp_id`, `test_unique_lsp`, `test_address_loop_mismatch` | AC-70 | — | формули R-23; 292 / 51; `ValidationError` |
| `test_event.py::TestEventLog` | `test_dedup_bucket`, `test_write_restricted`, `test_unlink_forbidden`, `test_manual_create`, `test_ack`, `test_sanitize_payload` | AC-12…AC-16 | `with_user(u/d/a)` | кількість записів; `AccessError`/`UserError`; поля підтвердження; довжина ≤ 500, `level='bad'` |
| `::TestBacnetPush` | `test_attach_message`, `test_new_bacnet_event`, `test_invalid_payload`, `test_control_chars` | AC-68 | `env['f3d.push.handler.fire']._f3d_handle_push('bacnet_event', {...})` | `message_text`, `device_id`; нова подія `etype='bacnet'`; `ValueError` |
| `test_sync.py::TestZones` | `test_alarm_cycle`, `test_states_table`, `test_loop_fault`, `test_stale_keeps_state`, `test_idempotent` | AC-17, AC-18, AC-23, AC-27 | `push_text` | стани, тексти подій, активності (`mail.activity` з `activity_type_id = mail_act_fire_alarm`, `user_id ∈ {guard1, guard2}`), 0 заявок для `alarm`; `changed == 0` |
| `::TestPanel` | `test_priority`, `test_state_text_plural`, `test_read_disabled` | AC-19, AC-22 | — | стани/тексти R-10; `comm='off'` |
| `::TestDust` | `test_dust_cycle` | AC-20 | `push_value` 82 → 90.1 → 79 | `dust_state`, `warning` (точний рядок), події, заявка (telemetry) з `f3d_fire_device_id`, `maintenance_team_id == team` |
| `::TestComm` | `test_comm_sequence` | AC-21 | `freeze_time` по кроках | переходи, події, активність, одна заявка, назва з «(3 хв)» |
| `::TestSystems` | `test_spark`, `test_smoke_sprinkler` | AC-24, AC-25 | коди Додатка B | стани, тексти, події |
| `::TestIngestHook`, `::TestAlarmActivity` | `test_immediate_sync`, `test_non_fire_code_skipped`, `test_sync_exception_isolated`, `test_activity_per_guard`, `test_reset_closes` | AC-26, AC-67 | `patch('…tools.sync.FireSync.run')` | виклики/відсутність виклику; результат ingest; кількість активностей |
| `test_security_readonly.py::TestReadonly` | `test_source_write_enabled_sudo`, `test_readonly_flag_sticky`, `test_params_read_only`, `test_signal_write_enabled_sudo`, `test_command_blocked_sudo`, `test_no_write_param_no_actions`, `test_device_signals_monitor` | AC-28…AC-31, AC-66 | `sudo()`, `with_user(m/u)` | `ValidationError`/`AccessError`; пошук `ir.ui.view.arch_db`/`ir.actions.server.code` модуля без `f3d.command`; сигнали M-04 |
| `test_requests.py::TestRequests` | `test_zone_fault_request_linked`, `test_no_duplicate` | AC-32 | `push_text(FA-CUT, 'fault')` | поля заявки M-14, `description`, одна заявка |
| `test_evacuation.py::TestRoutes` | `test_routes_ok`, `test_polymer`, `test_short_norm` | AC-33 | норми | 32/32; 26/32 і множина 6 зон |
| `::TestExits` | `test_dispersal`, `test_two_close_exits`, `test_door_width`, `test_exit_on_wall` | AC-34, AC-35, AC-40 | архівація, `width_m=0.7` | значення R-06/R-07; `ValidationError` |
| `::TestSmokeZones`, `::TestData`, `::TestReport`, `::TestPlantZone` | `test_need_table`, `test_vent_archived`, `test_area_fail`, `test_exit_route_data`, `test_path_validation`, `test_report_html`, `test_zone_fields`, `test_route_show_3d` | AC-36…AC-40 | `report._render_qweb_html(...)` | таблиця R-09; підрядки HTML; поля M-13; `params.code` |
| `test_drill.py::TestDrill` | `test_name_and_steps`, `test_transitions`, `test_start_people`, `test_passages_rollcall_result`, `test_auto_steps`, `test_match_planned`, `test_auto_create`, `test_no_auto_create`, `test_real_alarm`, `test_auto_stop`, `test_tabletop_no_auto_stop`, `test_sim_bridge`, `test_privacy`, `test_report_drill`, `test_cron_tick` | AC-41…AC-52 | `make_att`, `freeze_time`, події через `_log` (для R-17), `patch.object(type(env['f3d.fire.drill']), '_f3d_sim_create_run')` | значення AC; `result_suggested`; `t_fact_s`; параметри виклику емулятора |
| `test_passage_source.py::TestSources` | `test_hr_attendance`, `test_prefix_source_without_inherit`, `test_people_from_passages`, `test_unavailable_falls_back`, `test_access_if_installed` (`skipUnless('f3d.fire.passage.source.access' in env)`), `test_is_active_at` | AC-53, AC-54, AC-75 | тестовий модуль §0.3; `with_context(f3d_test_passage_source=True, f3d_test_passages=[…])` | ключ джерела; люди; `exit_ts`; булеві значення CF-06 |
| `test_viewer_provider.py::TestPayload` | `test_fire_structure`, `test_group_states`, `test_evacuation_structure`, `test_devices_and_disabled` | AC-55…AC-57, AC-59 | `tools.payload.build_fire/build_evacuation(env, ctx)` (`ctx = {"now": T0}`) | ключі, порядок, значення; `json.dumps` |
| `test_rights_ui.py::TestMenusRights` | `test_menus`, `test_acl_matrix`, `test_settings` | AC-63…AC-65 | `with_user(...)`; `env['res.config.settings'].create({...}).execute()` | меню/дії; `AccessError`; параметри й пороги сигналів |
| `factory3d_fire_safety_viewer/tests/test_provider.py::TestProvider` | `test_registered_and_live`, `test_bus_and_delta` | AC-58 | viewer `PayloadBuilder`, `DeltaBuilder` | `meta.sections`, `f3d.viewer.event`, `patch.fire` |
| `tests/test_data_sync.py` (pytest) | `test_generated_equals_repo` | AC-71 | `tools/gen_data.py --out <tmp>` | побайтова рівність |

### 13.2 Стендові сценарії ТК-01…ТК-10 (`tests/stand/`, `pytest -m stand`)

Передумови: compose `docker-compose.sim.yml` (iot_sim) + `docker-compose.collector.yml` (telemetry) + Odoo з
`factory3d_base`, `factory3d_telemetry`, `factory3d_iot_sim`, `factory3d_viewer`, `factory3d_fire_safety`(+ міст) на
копії демо; токен колектора видано; емулятор `factor=1`, режим `scenario`; `conftest.py` дає клієнти: XML-RPC Odoo
(лише читання моделей + виклик кнопок як користувач `d`) і REST `/sim/v1` (токен з `.env`). Очікування з таймаутами
опитування Odoo кожні 2 с.

| ТК | Кроки | Очікуваний результат | Де дивитися | AC |
|---|---|---|---|---|
| ТК-01 Підключення | колектор стартує з джерелами `BACNET-FACP-1`, `MB-U85-IO6` | ≤ 120 с: `f3d.source` обидва `online`; `panel.comm='online'`, `state='normal'`; 33 зони `normal`; `FA-FAC.dust_max_pct` = значення емулятора (82…90), `warn=True`; подія `comm_restored`; `fire.totals.state` = «Норма, 1 попередження» | Пожежна безпека → Огляд; Журнал | AC-72 |
| ТК-02 Запиленість | `PUT /sim/v1/signals/fire/groups/FA-FAC/dust {"value": 91, "hold_s": 600}` | ≤ 620 с (опитування 600 с): `2.FAC.07.dust_state='alarm'`, подія `dust_alarm`, заявка «Очистити сповіщувач 2.FAC.07 (Дільниця фасадів МДФ): запиленість 91 % при нормі до 90» з `f3d_fire_device_id`; закрити заявку (стадія Repaired) → емулятор скидає (R-25 iot_sim) → `dust_ok` | Обслуговування → Заявки | AC-20 |
| ТК-03 Несправність зони | `POST /sim/v1/device/FA-CUT/fault {"reason": "sensor"}`; через 60 с `POST /device/FA-CUT/clear` | ≤ 20 с: `FA-CUT.state='fault'`, `loop_2.state='fault'`, події `fault` і `loop_fault`, 2 заявки (зона, шлейф — A-28); `clear` → `fault_ok`, `loop_ok`; заявки відкриті | Зони; Шлейфи; Заявки | AC-23, AC-32 |
| ТК-04 Навчання на емуляторі | `d` створює навчання (FA-CNC, 2.CNC.05, `mode='sim'`) → «Запустити на емуляторі» | `sim_run_ref` заповнено; кроки: 1 ≤ 15 с, 2 ≤ 18 с, 5 ≤ 24 с (`done_by='auto'`); `evacuation.drill_active` у `/f3d/viewer/data`; після `duration_s` 300 + повернення ≤ 30 с + `drill_auto_stop_s` 120 → `evaluating`; перекличка → «Закрити» → PDF протоколу | Навчальні тривоги; 3D | AC-73, AC-44, AC-45 |
| ТК-05 Тест без плану | з пульту iot_sim `fire_drill` (`zone=FA-EB`) без навчання в Odoo | ≤ 20 с: навчання `origin='panel'`, «Тест приладу: Крайкооблицювання», `running`; подія `drill_auto`; авто-стоп після завершення сценарію | Навчальні тривоги | AC-46 |
| ТК-06 Справжня тривога | `POST /sim/v1/scenario/fire_drill/start {"params": {"zone": "FA-CUT", "real": true, "duration_s": 120}}` | ≤ 15 с: `FA-CUT.state='alarm'`, `panel.state='alarm'`, активності охороні, подія `brigade_on` (BI:11=1), **жодної** заявки ТО за тривогу; після завершення — `reset`, активності закриті | Огляд (червона плашка); дзвіночок активностей | AC-17, AC-67 |
| ТК-07 Іскрогасіння | `POST /sim/v1/scenario/spark/start {"params": {"count": 2, "interval_s": 30}}`; потім `{"fault": true}` | `count_today` +2, події `spark` (1–2 залежно від кошика опитування 10 с); `fault` → `SPARK-1.state='fault'`, `spark_fault`, заявка «Несправність іскрогасіння SPARK-1 (пульт GreCon BS 7)» | Системи; Журнал | AC-24 |
| ТК-08 Втрата зв'язку | `POST /sim/v1/device/FACP-1/fault {"reason": "comm"}`; через 5 хв `POST /device/FACP-1/clear` | 90–100 с: `comm='stale'`; 180–190 с: `lost`, подія, активність, заявка «Втрата зв'язку з приладом FACP-1: …»; `fire.totals.state` = «Зв'язок із приладом втрачено»; `clear` → `comm_restored` ≤ 20 с, активність закрита, заявка відкрита | Огляд; Заявки | AC-21 |
| ТК-09 Живлення щита D+H | `POST /sim/v1/scenario/blackout/start {"params": {"duration_s": 120, "genset": true}}` | `SMOKE-CTRL.state='battery'`, подія `smoke_battery`; після відновлення `smoke_mains` | Системи | AC-25 |
| ТК-10 3D | при ТК-04 і ТК-06 відкрити Завод 3D | шар «Пожежна безпека»: картки груп, «Потребує уваги» з FA-FAC; під час навчання — `drill_active` (автозапуск сценарію — після Q-09, інакше кнопка «Сценарій пожежної тривоги»); `/f3d/viewer/delta` містить `fire` після зміни стану | 3D-переглядач | AC-58 (MAN-частина) |

### 13.3 Тести безпеки

| ТБ | Що | Як | AC |
|---|---|---|---|
| ТБ-01 | джерело пожежної сигналізації не вмикає запис навіть під `sudo` | UT `test_source_write_enabled_sudo`, `test_readonly_flag_sticky`, `test_params_read_only` | AC-28 |
| ТБ-02 | сигнал `fire/*` не вмикає запис | UT `test_signal_write_enabled_sudo` | AC-29 |
| ТБ-03 | команда на сигнал `fire/*` неможлива | UT `test_command_blocked_sudo`; стенд: `GET /f3d/telemetry/commands` колектора ніколи не містить кодів `fire/*` | AC-30 |
| ТБ-04 | у модулі немає параметра/кнопки запису; емулятор відхиляє запис | UT `test_no_write_param_no_actions`; стенд: тестовий BACnet-клієнт (bacpypes3, поза колектором) `WriteProperty LSZ:14 present-value` → `write-access-denied` (iot_sim §8.11.2) | AC-31 |
| ТБ-05 | колектор не надсилає жодного пакета зміни стану | стенд: `tcpdump -i any -w fire.pcap 'udp port 47808 or tcp port 502'` у мережі `f3d_sim` під час ТК-01…ТК-10; `tshark -r fire.pcap -Y 'bacapp.confirmed_service && !(bacapp.confirmed_service == 12 \|\| bacapp.confirmed_service == 14)' \| wc -l` = 0 (дозволені лише ReadProperty 12 і ReadPropertyMultiple 14; заборонені, зокрема, subscribeCOV 5, writeProperty 15, writePropertyMultiple 16, deviceCommunicationControl 17, reinitializeDevice 20, acknowledgeAlarm 0, lifeSafetyOperation 27); `tshark -Y 'mbtcp.unit_id == 85 && (modbus.func_code == 5 \|\| modbus.func_code == 6 \|\| modbus.func_code == 15 \|\| modbus.func_code == 16)'` = 0 | AC-74 |
| ТБ-06 | доступи й ін'єкції | користувач без `group_f3d_user` → `AccessError` на всіх моделях модуля; `U` не читає людей навчань (AC-50); адреса `1.FAC.01'; DROP TABLE x;--` → `ValidationError`; `path` `[{"__class__": 1}]` → `ValidationError`; `message_text` `<script>alert(1)</script>` зберігається текстом і в HTML V-09/V-22 екранований (`&lt;script&gt;`) | AC-50, AC-64, AC-68 |

### 13.4 Тести продуктивності

| ТП | Обсяг | Межа | Як |
|---|---|---|---|
| ТП-01 | `build_fire` (33 зони, 20 подій) і `build_evacuation` | ≤ 100 мс кожен; JSON ≤ 60 КБ / ≤ 25 КБ; з `devices` ≤ 150 КБ | UT `test_payload_perf` (`time.perf_counter`, медіана з 5) |
| ТП-02 | `action_recompute_compliance` (R-02 ≈ 43 000 точок, R-03 2 812 × 36) | ≤ 2 с | UT `test_compliance_perf` |
| ТП-03 | `FireSync.run(full=True)` (53 сигнали) | ≤ 200 мс, ≤ 30 SQL-запитів без змін (`assertQueryCount`-подібний лічильник `cr.sql_log_count`) | UT `test_sync_perf` |
| ТП-04 | журнал 10 000 подій | `search_read` 80 рядків `ts desc` ≤ 200 мс (індекси M-05); відкриття списку V-08 ≤ 1 с | UT генерує 10 000 подій через `_log` (`sudo`) + MAN |

### 13.5 Чек-лист DEPLOY_TEST (`docs/modules/factory3d_fire_safety/DEPLOY_TEST.md`, здає W6)

1. Дамп бази `odoo` тестового сервера → `odoo_f3d_test`; знімки: `SELECT id, name, stage_id FROM maintenance_request
   ORDER BY id`, `SELECT count(*) FROM hr_attendance`, `SELECT id, code, last_value, module FROM f3d_signal WHERE code LIKE 'fire/%'`.
2. Установити `factory3d_base`, `factory3d_telemetry` (якщо ще ні), потім `factory3d_fire_safety` (+ міст за наявності
   viewer); лог INFO хука — лічильники AC-02; `migration_report.state = 'done'`.
3. Перевірити Огляд (прилад, 33 зони, `comm='lost'` до запуску колектора), звіт «Перевірка евакуації» (AC-38), демо-навчання.
4. Юніт-тести `--test-tags /factory3d_fire_safety` на `odoo_f3d_test` → 0 падінь.
5. Стенд ТК-01…ТК-10, ТБ-05 — протокол із фактичними часами.
6. Перехід «на прод» на копії: `environment='prod'` → `BACNET-FACP-1.read_enabled=False`; спроба увімкнути без дозволу
   → помилка (M-15 п. 3); заповнити дозвіл → увімкнути; змінити `params.host` на IP без мережі 2 — колектор знаходить
   пристрій прямим Who-Is (на стенді — IP контейнера iot-sim).
7. Повторне оновлення модуля (`-u factory3d_fire_safety`) → AC-03 (без дублікатів).
8. Деінсталяція на копії → `maintenance_request` (знімок п. 1) незмінні, сигнал запиленості існує, `hr_attendance` незмінна;
   повторна установка → п. 2 знову зелений.
9. `neutralize.sql` на копії → AC-61.
10. Записати фактичні кількості й часи в `CHANGELOG.md` (розділ «Установка на копію демо 14.10.2026»).

## 14. Definition of Done

- Юніт-тести §13.1 зелені на чистій базі й на копії демо (`--test-tags /factory3d_fire_safety`,
  `/factory3d_fire_safety_viewer`); `test_data_sync.py` зелений (генератор = data).
- ТК-01…ТК-10, ТБ-01…ТБ-06, ТП-01…ТП-04 пройдені; протокол із фактичними кількостями й часами — у `DEPLOY_TEST.md`.
- Кожен AC-01…AC-75 має зелений тест або відмітку ТК/MAN у протоколі; кожен FR-01…FR-24 покритий AC (§12).
- `ruff check` (конфіг проєкту; без нього — умовчання, довжина рядка 120) без помилок; XML валідний (`xmllint --noout`).
- Жодного `x_`-поля; жодного параметра чи поля `write_enabled` модуля:
  `grep -rn "x_\w*\s*=\s*fields\.\|fire_safety.write_enabled" odoo_addons/factory3d_fire_safety --include=*.py --include=*.xml`
  — збіги лише в тестах і `neutralize.sql`.
- `neutralize.sql` виконується без помилки (AC-61); стоп-кран `read_enabled` працює (AC-22).
- Перегляд безпеки: §13.3 пройдено; SQL лише параметризований (сирий SQL — тільки в `neutralize.sql`); жодного виклику
  `f3d.command`/`write()` плагіна з коду модуля; персональні дані навчань — лише групам `D`/`H` (AC-50).
- `README.md` модуля (установка, параметри §5.1, інструкції ARCH §4.1–4.6, заборона запису), `CHANGELOG.md` (`19.0.1.0.0`).
- Контракти CF-01…CF-06 реалізовані з точними іменами; зміна імен — лише через оновлення SPEC і повідомлення авторів
  viewer, access, telemetry, iot_sim.

## 15. Відкриті питання

Ті самі Q-01…Q-17, що в ARCH §5.1 (нумерація спільна); тут — що робить код, поки відповіді немає:

| ID | Поки немає відповіді |
|---|---|
| Q-01 | адреси й склад об'єктів — за емулятором (Додаток B); на проді `read_enabled=False` до дозволу монтажника (M-15 п. 3) |
| Q-02 | `team_id` = «Служба головного механіка»; M-14 підставляє команду в заявки сигналів модуля |
| Q-03 | `drill_time_limit_s=300`; перевищення дає `remarks`, не `failed` (R-16 п. 6) |
| Q-04 | `polymer_panels=False` (норма 240 м); у звіті й payload — обидві норми |
| Q-05 | 33 зони як у макеті; R-08 показує «Z-OFFICE, Z-SOC» як зауваження |
| Q-06 | перевизначення `_f3d_ingest` (A-22) + крон 1 хв; без підтвердження telemetry затримка ≤ 75 с |
| Q-07 | адреси за R-23 telemetry, `params.read_only`; без маршруту `bacnet_event` — події лише з переходів сигналів |
| Q-08 | A-09 (адреси MCP/SND/FLM), A-23 (8 нових кодів), ТК-03 очікує дві заявки |
| Q-09 | payload уже має `drill_active`, `alarm_state`, `devices`; без змін клієнта — «Попередження» замість «Тривога» в картці, сценарій 3D — кнопкою |
| Q-10 | закрито (A-19): джерело access знаходиться за префіксом; на місці збору — перекличка (M-11d) |
| Q-11 | у data 212 сповіщувачів (макет), README не правимо |
| Q-12 | крани/вогнегасники/насосна не моделюються |
| Q-13 | журнал без ротації (A-12); звіт V-22 — журнал за період |
| Q-14 | ADAM u85 DI0–DI6 за iot_sim §8.11.3; зміна розкладки — лише дані сигналів |
| Q-15 | закрито (CF-06 `_f3d_is_active_at`); модуль у `hr.attendance` не пише |
| Q-16 | код приймає BI/BV і AV/PIV однаково; на проді адреси змінюються даними; сигнал запиленості архівується, якщо прилад її не віддає |
| Q-17 | dev 200 лише опитуванням 10 с (A-20) |

## Додаток A. Адреси пристроїв і зони виявлення (генерує `tools/gen_data.py` з `plant/fire.py`, `plant/infra.py`)

### A.1 Зони виявлення (`data/f3d_fire_zone.csv`) і очікувані значення R-01/R-02

`lsz` = BACnet LSZ instance (= порядок `fire.groups` макета, iot_sim §8.11.1); контур — `layout.ZONES` (котельня —
`fire.BOILER_HOUSE`); `s` — крок R-01; `gap` / точка — R-02 (сітка 0,5 м, `r` = 6,22 м; котельня — 4,53 м).

| lsz | code | f3d.zone | name | kind | loop | n | nx×ny | x0, y0, x1, y1 | area | z | адреси | LSP | gap, м | точка |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | FA-RCV-1 | Z-RCV-1 | Приймання плит · ворота 1 | smoke | 1 | 4 | 2×2 | 0.6, 0.6, 13.4, 9.85 | 118 | 8.85 | `1.RCV-1.01`…`1.RCV-1.04` | 10101…10104 | 3.95 | (0.6, 0.6) |
| 2 | FA-RCV-2 | Z-RCV-2 | Приймання плит · ворота 2 | smoke | 1 | 4 | 2×2 | 0.6, 10.15, 13.4, 19.85 | 124 | 8.85 | `1.RCV-2.01`…`1.RCV-2.04` | 10201…10204 | 4.02 | (0.6, 10.15) |
| 3 | FA-RCV-3 | Z-RCV-3 | Приймання плит · ворота 3 | smoke | 1 | 4 | 2×2 | 0.6, 20.15, 13.4, 29.85 | 124 | 8.85 | `1.RCV-3.01`…`1.RCV-3.04` | 10301…10304 | 4.02 | (0.6, 20.15) |
| 4 | FA-RCV-4 | Z-RCV-4 | Приймання фурнітури, контроль і карантин · ворота 4 | smoke | 1 | 4 | 2×2 | 0.6, 30.15, 13.4, 39.85 | 124 | 8.85 | `1.RCV-4.01`…`1.RCV-4.04` | 10401…10404 | 4.02 | (0.6, 30.15) |
| 5 | FA-RCV-5 | Z-RCV-5 | Приймання крайки · ворота 5 | smoke | 1 | 4 | 2×2 | 0.6, 40.15, 13.4, 49.85 | 124 | 8.85 | `1.RCV-5.01`…`1.RCV-5.04` | 10501…10504 | 4.02 | (0.6, 40.15) |
| 6 | FA-RCV-6 | Z-RCV-6 | Приймання ЛФМ · ворота 6 | smoke | 1 | 4 | 2×2 | 0.6, 50.15, 13.4, 59.85 | 124 | 8.85 | `1.RCV-6.01`…`1.RCV-6.04` | 10601…10604 | 4.02 | (0.6, 50.15) |
| 7 | FA-RCV-7 | Z-RCV-7 | Приймання пакматеріалів · ворота 7 | smoke | 1 | 4 | 2×2 | 0.6, 60.15, 13.4, 71.4 | 144 | 8.85 | `1.RCV-7.01`…`1.RCV-7.04` | 10701…10704 | 4.26 | (0.6, 60.15) |
| 8 | FA-SHEETS | Z-SHEETS | Склад плит | smoke | 1 | 24 | 4×6 | 14.6, 0.6, 41.4, 45.4 | 1201 | 8.85 | `1.SHEETS.01`…`1.SHEETS.24` | 10801…10824 | 5.02 | (14.6, 0.6) |
| 9 | FA-HW | Z-HW | Склад фурнітури | smoke | 1 | 6 | 2×3 | 14.6, 46, 28.4, 71.4 | 351 | 8.85 | `1.HW.01`…`1.HW.06` | 10901…10906 | 5.46 | (14.6, 46.0) |
| 10 | FA-EDGE | Z-EDGE | Склад крайки | smoke | 1 | 3 | 1×3 | 28.8, 46, 35.4, 71.4 | 168 | 8.85 | `1.EDGE.01`…`1.EDGE.03` | 11001…11003 | 5.37 | (28.8, 46.0) |
| 11 | FA-PKS | Z-PKS | Пакувальні матеріали | smoke | 1 | 3 | 1×3 | 35.8, 46, 41.4, 71.4 | 142 | 8.85 | `1.PKS.01`…`1.PKS.03` | 11101…11103 | 5.08 | (35.8, 46.0) |
| 12 | FA-CUT | Z-CUT | Розкрій | multi | 2 | 12 | 2×6 | 41.8, 0.6, 55.4, 45.4 | 609 | 8.85 | `2.CUT.01`…`2.CUT.12` | 21201…21212 | 5.05 | (41.8, 0.6) |
| 13 | FA-EB | Z-EB | Крайкооблицювання | multi | 2 | 12 | 2×6 | 55.8, 0.6, 68.4, 45.4 | 564 | 8.85 | `2.EB.01`…`2.EB.12` | 21301…21312 | 4.88 | (55.8, 0.6) |
| 14 | FA-CNC | Z-CNC | Присадка | multi | 2 | 12 | 2×6 | 68.8, 0.6, 81.4, 45.4 | 564 | 8.85 | `2.CNC.01`…`2.CNC.12` | 21401…21412 | 5.44 | (68.8, 0.6) |
| 15 | FA-SORT | Z-SORT | Сортування деталей | multi | 2 | 12 | 2×6 | 81.8, 0.6, 91.6, 45.4 | 439 | 8.85 | `2.SORT.01`…`2.SORT.12` | 21501…21512 | 4.95 | (81.8, 0.6) |
| 16 | FA-FAC | Z-FAC | Дільниця фасадів МДФ | multi | 2 | 18 | 6×3 | 42.2, 46.4, 91.6, 71.4 | 1235 | 8.85 | `2.FAC.01`…`2.FAC.18` | 21601…21618 | 5.86 | (42.2, 71.4) |
| 17 | FA-ASM | Z-ASM | Збирання | multi | 3 | 8 | 2×4 | 92.4, 0.6, 109.6, 29.6 | 499 | 8.85 | `3.ASM.01`…`3.ASM.08` | 31701…31708 | 5.62 | (92.4, 15.1) |
| 18 | FA-PRE | Z-PRE | Буфер комплектів | smoke | 3 | 4 | 2×2 | 92.4, 30, 109.6, 45.6 | 268 | 8.85 | `3.PRE.01`…`3.PRE.04` | 31801…31804 | 5.81 | (92.4, 30.0) |
| 19 | FA-MAINT | Z-MAINT | Ремонтна дільниця | multi | 3 | 4 | 2×2 | 92.4, 46.4, 103.6, 57.6 | 125 | 8.85 | `3.MAINT.01`…`3.MAINT.04` | 31901…31904 | 3.96 | (92.4, 46.4) |
| 20 | FA-PACK | Z-PACK | Пакування | smoke | 3 | 8 | 2×4 | 110, 0.6, 121.6, 33.6 | 383 | 8.85 | `3.PACK.01`…`3.PACK.08` | 32001…32008 | 5.04 | (110.0, 0.6) |
| 21 | FA-POST | Z-POST | Вихід з пакування | smoke | 3 | 6 | 2×3 | 110, 34, 121.6, 59.6 | 297 | 8.85 | `3.POST.01`…`3.POST.06` | 32101…32106 | 5.16 | (110.0, 34.0) |
| 22 | FA-CMP | Z-CMP | Компресорна | multi | 3 | 2 | 1×2 | 110, 60, 115.6, 71.4 | 64 | 8.85 | `3.CMP.01`…`3.CMP.02` | 32201…32202 | 4.0 | (110.0, 60.0) |
| 23 | FA-CHG | Z-CHG | Зарядна станція | multi | 3 | 2 | 1×2 | 116, 60, 121.6, 71.4 | 64 | 8.85 | `3.CHG.01`…`3.CHG.02` | 32301…32302 | 4.0 | (116.0, 60.0) |
| 24 | FA-FG | Z-FG | Склад готової продукції | smoke | 4 | 14 | 2×7 | 122, 0.6, 135.6, 62 | 835 | 8.85 | `4.FG.01`…`4.FG.14` | 42401…42414 | 6.26 | (122.0, 54.1) |
| 25 | FA-ELEC | Z-ELEC | Електрощитова | smoke | 4 | 4 | 2×2 | 122.4, 62.4, 135.6, 71.4 | 119 | 8.85 | `4.ELEC.01`…`4.ELEC.04` | 42501…42504 | 4.33 | (129.4, 62.4) |
| 26 | FA-OUT-1 | Z-OUT-1 | Відвантаження · ворота 1 | smoke | 4 | 4 | 2×2 | 136, 0.6, 149.4, 9.85 | 124 | 8.85 | `4.OUT-1.01`…`4.OUT-1.04` | 42601…42604 | 4.07 | (136.0, 0.6) |
| 27 | FA-OUT-2 | Z-OUT-2 | Відвантаження · ворота 2 | smoke | 4 | 4 | 2×2 | 136, 10.15, 149.4, 19.85 | 130 | 8.85 | `4.OUT-2.01`…`4.OUT-2.04` | 42701…42704 | 4.14 | (136.0, 10.15) |
| 28 | FA-OUT-3 | Z-OUT-3 | Відвантаження · ворота 3 | smoke | 4 | 4 | 2×2 | 136, 20.15, 149.4, 29.85 | 130 | 8.85 | `4.OUT-3.01`…`4.OUT-3.04` | 42801…42804 | 4.14 | (136.0, 20.15) |
| 29 | FA-OUT-4 | Z-OUT-4 | Відвантаження · ворота 4 | smoke | 4 | 4 | 2×2 | 136, 30.15, 149.4, 39.85 | 130 | 8.85 | `4.OUT-4.01`…`4.OUT-4.04` | 42901…42904 | 4.14 | (136.0, 30.15) |
| 30 | FA-OUT-5 | Z-OUT-5 | Відвантаження · ворота 5 | smoke | 4 | 4 | 2×2 | 136, 40.15, 149.4, 49.85 | 130 | 8.85 | `4.OUT-5.01`…`4.OUT-5.04` | 43001…43004 | 4.14 | (136.0, 40.15) |
| 31 | FA-OUT-6 | Z-OUT-6 | Відвантаження · ворота 6 | smoke | 4 | 4 | 2×2 | 136, 50.15, 149.4, 59.85 | 130 | 8.85 | `4.OUT-6.01`…`4.OUT-6.04` | 43101…43104 | 4.14 | (136.0, 50.15) |
| 32 | FA-OUT-7 | Z-OUT-7 | Відвантаження · ворота 7 | smoke | 4 | 4 | 2×2 | 136, 60.15, 149.4, 71.4 | 151 | 8.85 | `4.OUT-7.01`…`4.OUT-7.04` | 43201…43204 | 4.37 | (136.0, 60.15) |
| 33 | FA-BOILER | Z-BOILER | Котельня | heat | 2 | 2 | 2×1 | 67.6, 75, 79.6, 81 | 72 | 4.35 | `2.BOILER.01`…`2.BOILER.02` | 23301…23302 | 4.24 | (67.6, 75.0) |

Координати 212 сповіщувачів — `fire.detectors()[zone].points` у порядку `nn` (округлення до 0,01 м); контрольні:
`2.FAC.07` → (62.78, 50.57, 8.85);
`2.CNC.05` → (72.75, 34.2, 8.85);
`1.SHEETS.01` → (17.95, 4.33, 8.85);
`2.BOILER.02` → (76.6, 78.0, 4.35);

### A.2 Ручні сповіщувачі (`type='mcp'`, z = 1,35, обладнання `FA-MCP`; порядок `call_points()`)

| # | address | LSP | x | y | side |
|---|---|---|---|---|---|
| 1 | `1.MCP.01` | 19001 | 0.04 | 7.3 | W |
| 2 | `4.MCP.01` | 49001 | 149.96 | 7.3 | E |
| 3 | `1.MCP.02` | 19002 | 0.04 | 17.3 | W |
| 4 | `4.MCP.02` | 49002 | 149.96 | 17.3 | E |
| 5 | `1.MCP.03` | 19003 | 0.04 | 27.3 | W |
| 6 | `4.MCP.03` | 49003 | 149.96 | 27.3 | E |
| 7 | `1.MCP.04` | 19004 | 0.04 | 37.3 | W |
| 8 | `4.MCP.04` | 49004 | 149.96 | 37.3 | E |
| 9 | `1.MCP.05` | 19005 | 0.04 | 47.3 | W |
| 10 | `4.MCP.05` | 49005 | 149.96 | 47.3 | E |
| 11 | `1.MCP.06` | 19006 | 0.04 | 57.3 | W |
| 12 | `4.MCP.06` | 49006 | 149.96 | 57.3 | E |
| 13 | `1.MCP.07` | 19007 | 0.04 | 67.3 | W |
| 14 | `4.MCP.07` | 49007 | 149.96 | 67.3 | E |
| 15 | `2.MCP.01` | 29001 | 50.5 | 45.88 | S |
| 16 | `2.MCP.02` | 29002 | 68 | 45.88 | S |
| 17 | `2.MCP.03` | 29003 | 91 | 45.88 | S |
| 18 | `3.MCP.01` | 39001 | 98.6 | 58.37 | S |
| 19 | `4.MCP.08` | 49008 | 131.3 | 62.37 | S |
| 20 | `3.MCP.02` | 39002 | 114.5 | 59.88 | S |
| 21 | `2.MCP.04` | 29004 | 48 | 29.75 | S |
| 22 | `2.MCP.05` | 29005 | 60 | 29.75 | S |
| 23 | `2.MCP.06` | 29006 | 84 | 29.75 | S |
| 24 | `3.MCP.03` | 39003 | 96 | 29.75 | S |
| 25 | `3.MCP.04` | 39004 | 108 | 29.75 | S |
| 26 | `3.MCP.05` | 39005 | 120 | 14.75 | S |
| 27 | `3.MCP.06` | 39006 | 120 | 44.75 | S |
| 28 | `1.MCP.08` | 19008 | 36 | 59.75 | S |
| 29 | `2.MCP.07` | 29007 | 84 | 59.75 | S |
| 30 | `4.MCP.09` | 49009 | 132 | 59.75 | S |
| 31 | `1.MCP.09` | 19009 | 28.22 | 9.5 | E |
| 32 | `2.MCP.08` | 29008 | 44.48 | 9.5 | W |
| 33 | `1.MCP.10` | 19010 | 30 | 0.6 | P |
| 34 | `2.MCP.09` | 29009 | 60 | 0.6 | P |
| 35 | `2.MCP.10` | 29010 | 90 | 0.6 | P |
| 36 | `3.MCP.07` | 39007 | 118 | 0.6 | P |

### A.3 Оповіщувачі (`type='sounder'`, z = 2,9, обладнання `FA-SND`; порядок `sounders()`)

| # | address | LSP | x | y | side |
|---|---|---|---|---|---|
| 1 | `2.SND.01` | 29101 | 48 | 44.75 | S |
| 2 | `2.SND.02` | 29102 | 60 | 44.75 | S |
| 3 | `2.SND.03` | 29103 | 72 | 44.75 | S |
| 4 | `2.SND.04` | 29104 | 84 | 44.75 | S |
| 5 | `3.SND.01` | 39101 | 96 | 44.75 | S |
| 6 | `3.SND.02` | 39102 | 108 | 44.75 | S |
| 7 | `3.SND.03` | 39103 | 120 | 14.75 | S |
| 8 | `3.SND.04` | 39104 | 120 | 59.75 | S |
| 9 | `1.SND.01` | 19101 | 5 | 71.96 | N |
| 10 | `1.SND.02` | 19102 | 15 | 71.96 | N |
| 11 | `1.SND.03` | 19103 | 25 | 71.96 | N |
| 12 | `1.SND.04` | 19104 | 35 | 71.96 | N |
| 13 | `2.SND.05` | 29105 | 45 | 71.96 | N |
| 14 | `2.SND.06` | 29106 | 55 | 71.96 | N |
| 15 | `2.SND.07` | 29107 | 65 | 71.96 | N |
| 16 | `2.SND.08` | 29108 | 75 | 71.96 | N |
| 17 | `2.SND.09` | 29109 | 85 | 71.96 | N |
| 18 | `3.SND.05` | 39105 | 95 | 71.96 | N |
| 19 | `3.SND.06` | 39106 | 105 | 71.96 | N |
| 20 | `3.SND.07` | 39107 | 115 | 71.96 | N |
| 21 | `4.SND.01` | 49101 | 125 | 71.96 | N |
| 22 | `4.SND.02` | 49102 | 135 | 71.96 | N |
| 23 | `4.SND.03` | 49103 | 145 | 71.96 | N |
| 24 | `1.SND.05` | 19105 | 0.04 | 10 | W |
| 25 | `1.SND.06` | 19106 | 0.04 | 20 | W |
| 26 | `1.SND.07` | 19107 | 0.04 | 30 | W |
| 27 | `1.SND.08` | 19108 | 0.04 | 40 | W |
| 28 | `1.SND.09` | 19109 | 0.04 | 50 | W |
| 29 | `1.SND.10` | 19110 | 0.04 | 60 | W |
| 30 | `1.SND.11` | 19111 | 0.04 | 70 | W |
| 31 | `4.SND.04` | 49104 | 149.96 | 10 | E |
| 32 | `4.SND.05` | 49105 | 149.96 | 20 | E |
| 33 | `4.SND.06` | 49106 | 149.96 | 30 | E |
| 34 | `4.SND.07` | 49107 | 149.96 | 40 | E |
| 35 | `4.SND.08` | 49108 | 149.96 | 50 | E |
| 36 | `4.SND.09` | 49109 | 149.96 | 60 | E |
| 37 | `4.SND.10` | 49110 | 149.96 | 70 | E |
| 38 | `2.SND.10` | 29110 | 45 | 45.88 | S |
| 39 | `2.SND.11` | 29111 | 55 | 45.88 | S |
| 40 | `2.SND.12` | 29112 | 75 | 45.88 | S |
| 41 | `2.SND.13` | 29113 | 85 | 45.88 | S |

### A.4 Полум'я та іскрогасіння

| address | type | LSP | x | y | z | side / heading | система / обладнання |
|---|---|---|---|---|---|---|---|
| `2.FLM.01` | flame | 29201 | 46 | 71.8 | 5 | heading -90 | панель / `FA-FLAME` |
| `2.FLM.02` | flame | 29202 | 64 | 71.8 | 5 | heading -90 | панель / `FA-FLAME` |
| `2.FLM.03` | flame | 29203 | 76 | 71.8 | 5 | heading -90 | панель / `FA-FLAME` |
| `0.SPK.01` | spark_detector | 0 | 47 | 18.5 | 7.98 | — | `SPARK-1` |
| `0.SPK.02` | spark_detector | 0 | 66 | 18.5 | 7.98 | — | `SPARK-1` |
| `0.SPK.03` | spark_detector | 0 | 79 | 18.5 | 7.98 | — | `SPARK-1` |
| `0.SPK.04` | spark_detector | 0 | 55.6 | 60.5 | 7.98 | — | `SPARK-1` |
| `0.NOZ.01` | spark_nozzle | 0 | 52.5 | 18.5 | 7.98 | X | `SPARK-1` |
| `0.NOZ.02` | spark_nozzle | 0 | 60.5 | 18.5 | 7.98 | X | `SPARK-1` |
| `0.NOZ.03` | spark_nozzle | 0 | 55.6 | 66 | 7.98 | Y | `SPARK-1` |

### A.5 Люки димовидалення (`type='smoke_vent'`, z = 9,0, система `SMOKE-CTRL`, обладнання `SMOKE-VENTS`; 3D-об'єкти `SV-nn`)

| address | 3D | smoke zone | x | y |
|---|---|---|---|---|
| `0.SV.01` | SV-01 | SZ-1 | 13.8 | 6 |
| `0.SV.02` | SV-02 | SZ-1 | 13.8 | 18 |
| `0.SV.03` | SV-03 | SZ-1 | 13.8 | 31.5 |
| `0.SV.04` | SV-04 | SZ-1 | 13.8 | 42 |
| `0.SV.05` | SV-05 | SZ-1 | 13.8 | 54 |
| `0.SV.06` | SV-06 | SZ-1 | 13.8 | 66 |
| `0.SV.07` | SV-07 | SZ-2 | 25.8 | 6 |
| `0.SV.08` | SV-08 | SZ-2 | 25.8 | 18 |
| `0.SV.09` | SV-09 | SZ-2 | 25.8 | 31.5 |
| `0.SV.10` | SV-10 | SZ-2 | 25.8 | 42 |
| `0.SV.11` | SV-11 | SZ-2 | 25.8 | 54 |
| `0.SV.12` | SV-12 | SZ-2 | 25.8 | 66 |
| `0.SV.13` | SV-13 | SZ-3 | 49.8 | 5.75 |
| `0.SV.14` | SV-14 | SZ-3 | 49.8 | 17.25 |
| `0.SV.15` | SV-15 | SZ-3 | 49.8 | 28.75 |
| `0.SV.16` | SV-16 | SZ-3 | 49.8 | 40.25 |
| `0.SV.17` | SV-17 | SZ-4 | 73.8 | 3.83 |
| `0.SV.18` | SV-18 | SZ-4 | 73.8 | 11.5 |
| `0.SV.19` | SV-19 | SZ-4 | 73.8 | 19.17 |
| `0.SV.20` | SV-20 | SZ-4 | 73.8 | 26.83 |
| `0.SV.21` | SV-21 | SZ-4 | 73.8 | 34.5 |
| `0.SV.22` | SV-22 | SZ-4 | 73.8 | 42.17 |
| `0.SV.23` | SV-23 | SZ-5 | 49.8 | 50.33 |
| `0.SV.24` | SV-24 | SZ-5 | 49.8 | 59 |
| `0.SV.25` | SV-25 | SZ-5 | 49.8 | 67.67 |
| `0.SV.26` | SV-26 | SZ-5 | 73.8 | 52.5 |
| `0.SV.27` | SV-27 | SZ-5 | 73.8 | 65.5 |
| `0.SV.28` | SV-28 | SZ-6 | 97.8 | 6 |
| `0.SV.29` | SV-29 | SZ-6 | 97.8 | 18 |
| `0.SV.30` | SV-30 | SZ-6 | 97.8 | 31.5 |
| `0.SV.31` | SV-31 | SZ-6 | 97.8 | 42 |
| `0.SV.32` | SV-32 | SZ-6 | 97.8 | 54 |
| `0.SV.33` | SV-33 | SZ-6 | 97.8 | 66 |
| `0.SV.34` | SV-34 | SZ-7 | 121.8 | 6 |
| `0.SV.35` | SV-35 | SZ-7 | 121.8 | 18 |
| `0.SV.36` | SV-36 | SZ-7 | 121.8 | 31.5 |
| `0.SV.37` | SV-37 | SZ-7 | 121.8 | 42 |
| `0.SV.38` | SV-38 | SZ-7 | 121.8 | 54 |
| `0.SV.39` | SV-39 | SZ-7 | 121.8 | 66 |
| `0.SV.40` | SV-40 | SZ-8 | 145.8 | 7.2 |
| `0.SV.41` | SV-41 | SZ-8 | 145.8 | 21.6 |
| `0.SV.42` | SV-42 | SZ-8 | 145.8 | 36 |
| `0.SV.43` | SV-43 | SZ-8 | 145.8 | 50.4 |
| `0.SV.44` | SV-44 | SZ-8 | 145.8 | 64.8 |

## Додаток B. Сигнали модуля (`data/f3d_signal_data.xml`, 52 + запиленість від хука; CF-03, A-23)

Спільне для всіх 52: `module='fire_safety'`, `origin='catalog'`, `write_enabled=False`, `viewer_visible=False` (розділ
`fire` будує M-17), `create_request` — `True` лише там, де є `alarm_states`/пороги, `alarm_priority='2'`, `decimals=0`,
`store_period_s=3600` (крім позначених), `hysteresis=0`, `min_duration_s=0`. Напрямок — **R** (лише читання) для всіх;
об'єкти dev 200 — iot_sim §8.11.1 (еталон ASHRAE 135 LSZ/LSP; склад об'єктів приладу — ПРИПУЩЕННЯ, Q-01/Q-16), u85 —
iot_sim §8.11.3 (ПРИПУЩЕННЯ, Q-14). Джерела: `B` = `source_bacnet_facp_1`, `M` = `source_mb_u85_io6`. Обладнання —
за R-24 (хук). Колонка «iot_sim №» — рядок Додатка A iot_sim (новий = A-23).

| # | code | name | kind / unit | джерело / `address` | `period_s` | `states` / `map` | `alarm_states` · `alarm_title` | iot_sim № |
|---|---|---|---|---|---|---|---|---|
| 1–33 | `fire/groups/<FA>/state` (33 зони, Додаток A.1) | «Стан зони <FA> (<назва>)» | state / — | B · `{"device": 200, "object": "LSZ", "instance": <lsz>, "mode": "poll"}` | 10 | текст `BACnetLifeSafetyState` (R-11), `states` порожньо | `["fault", "tamper", "abnormal", "emergency-power", "supervisory"]` · «Несправність зони <FA> (<назва>): стан «{text}»» | 603–635 |
| 34 | `fire/totals/state` | «Прилад FACP-1: стан (LSZ:0)» | state / — | B · `{"device": 200, "object": "LSZ", "instance": 0, "mode": "poll"}` | 10 | — | `[]`, `create_request=False` | 640 |
| 35 | `fire/totals/system_state` | «Прилад FACP-1: системний стан (MSV:1)» | state / — | B · `{"device": 200, "object": "MSV", "instance": 1, "mode": "poll", "map": {"1": "normal", "2": "alarm", "3": "fault", "4": "test", "5": "disabled"}}` | 10 | `["normal", "alarm", "fault", "test", "disabled"]` | `[]`, `False` | новий |
| 36 | `fire/totals/alarms` | «Прилад FACP-1: активні тривоги» | gauge / шт | B · `{"device": 200, "object": "AV", "instance": 1, "mode": "poll"}` | 10 | — | без порогів, `False` | 641 |
| 37 | `fire/totals/faults` | «Прилад FACP-1: несправності» | gauge / шт | B · `AV` 2 | 10 | — | без порогів, `False` (заявки — від зон і шлейфів) | 642 |
| 38 | `fire/totals/disabled` | «Прилад FACP-1: вимкнення» | gauge / шт | B · `AV` 3 | 10 | — | без порогів, `False` | 643 |
| 39–42 | `fire/loops/<n>/state`, n = 1…4 | «Шлейф <n>: несправність» | state / — | B · `{"device": 200, "object": "BI", "instance": <n>, "mode": "poll", "map": {"0": "off", "1": "on"}}` | 10 | `["off", "on"]` | `["on"]` · «Несправність шлейфу <n> приладу FACP-1» | 636–639 |
| 43 | `fire/totals/sounders_active` | «Оповіщувачі увімкнено (BI:10)» | state / — | B · `BI` 10, `map` off/on | 10 | `["off", "on"]` | `[]`, `False` | новий |
| 44 | `fire/totals/brigade` | «Передано на пульт ДСНС (BI:11)» | state / — | B · `BI` 11, `map` off/on | 10 | `["off", "on"]` | `[]`, `False` | новий |
| 45 | `fire/spark/SPARK-1/state` | «Іскрогасіння: іскра (DI0)» | state / — | M · `{"fc": 2, "addr": 0, "type": "bool", "unit": 85, "map": {"0": "off", "1": "on"}}` | 2 | `["off", "on"]` | `[]`, `False` (події — з лічильника, A-13) | 644 (звужено до DI0) |
| 46 | `fire/spark/SPARK-1/extinguishing` | «Іскрогасіння: гасіння (DI1)» | state / — | M · `fc 2`, `addr 1`, `map` off/on | 2 | `["off", "on"]` | `[]`, `False` | новий |
| 47 | `fire/spark/SPARK-1/fault` | «Іскрогасіння: несправність (DI2)» | state / — | M · `fc 2`, `addr 2`, `map` off/on | 2 | `["off", "on"]` | `["on"]` · «Несправність іскрогасіння SPARK-1 (пульт GreCon BS 7)» | новий |
| 48 | `fire/spark/SPARK-1/water_ok` | «Іскрогасіння: тиск води (DI3)» | state / — | M · `fc 2`, `addr 3`, `map {"0": "low", "1": "ok"}` | 2 | `["low", "ok"]` | `["low"]` · «Іскрогасіння SPARK-1: немає тиску води гасіння» | новий |
| 49 | `fire/spark/SPARK-1/count_today` | «Іскрогасіння: іскор за добу» | gauge / шт | M · `{"fc": 3, "addr": 0, "count": 2, "type": "u32", "wordorder": "little", "unit": 85}` | 10 | — | без порогів, `False`; `store_period_s=300` | 645 |
| 50 | `fire/smoke/SMOKE-VENTS/state` | «Люки димовидалення відкриті (DI4)» | state / — | M · `fc 2`, `addr 4`, `map {"0": "closed", "1": "open"}` | 2 | `["closed", "open"]` | `[]`, `False` | 646 (звужено до DI4) |
| 51 | `fire/smoke/SMOKE-CTRL/fault` | «Щит D+H: несправність (DI5)» | state / — | M · `fc 2`, `addr 5`, `map {"0": "ok", "1": "fault"}` | 2 | `["ok", "fault"]` | `["fault"]` · «Несправність щита димовидалення SMOKE-CTRL (D+H CPS-M1): АКБ або живлення» | новий |
| 52 | `fire/smoke/SMOKE-CTRL/battery` | «Щит D+H: живлення від АКБ (DI6)» | state / — | M · `fc 2`, `addr 6`, `map {"0": "mains", "1": "battery"}` | 2 | `["mains", "battery"]` | `[]`, `False` | новий |
| 53 | `fire/groups/FA-FAC/dust` (хук §5.4 п. 3, не в XML) | «Запиленість сповіщувача 2.FAC.07» | gauge / % | B · `{"device": 200, "object": "AV", "instance": 21607, "mode": "poll"}` | 600 | — | `warn_high` 80, `alarm_high` 90, `hysteresis` 1,8, `decimals` 1 · «Очистити сповіщувач 2.FAC.07 (Дільниця фасадів МДФ): запиленість {value} % при нормі до {threshold}» | 189 (рівень 0) |

Сигнали пристроїв за `monitor` (A-02, M-04 `action_create_signals`): `fire/devices/<address>/state` (LSP, 10 с) і
`fire/devices/<address>/dust` (AV, 600 с) — не в data.

## Додаток C. Приклад розділів payload (API-02, CF-01; копія демо після ТК-01: прилад онлайн, запиленість `2.FAC.07` = 82,5 % як у макеті)

```json
{
 "fire": {
  "rules": {"smoke_area_6_12m": null, "smoke_spacing_6_12m": 8.8, "smoke_wall_6_12m": 4.4, "heat_area": null,
            "heat_spacing": 6.4, "mcp_spacing": 30, "mcp_height": null, "sounder_level": 65,
            "spark_detection_required": null, "flame_detector_note": null},
  "loops": {"1": {"detectors": 64, "mcp": 10, "sounders": 11, "flame": 0, "modules": 0, "state": "ok"},
            "2": {"detectors": 68, "mcp": 10, "sounders": 13, "flame": 3, "modules": 4, "state": "ok"},
            "3": {"detectors": 34, "mcp": 7, "sounders": 7, "flame": 0, "modules": 0, "state": "ok"},
            "4": {"detectors": 46, "mcp": 9, "sounders": 10, "flame": 0, "modules": 0, "state": "ok"}},
  "groups": {
   "FA-RCV-1": {"zone": "Z-RCV-1", "zone_name": "Приймання плит · ворота 1", "kind": "smoke", "kind_name": "димові оптичні",
                "n": 4, "spacing": 8.8, "area": 118, "loop": 1, "state": "ok", "alarm_state": "normal", "compliance": "ok", "stale": false},
   "FA-FAC": {"zone": "Z-FAC", "zone_name": "Дільниця фасадів МДФ", "kind": "multi", "kind_name": "оптико-теплові (пил деревини)",
              "n": 18, "spacing": 8.8, "area": 1235, "loop": 2, "state": "warn",
              "warning": "Сповіщувач 2.FAC.07 біля шліфування: запиленість камери 82 % — очистити до кінця зміни, інакше прилад переведе його в несправність.",
              "maintenance_request": "Очистити сповіщувач 2.FAC.07 (запиленість 82 %)", "dust": 0.825,
              "alarm_state": "normal", "compliance": "ok", "stale": false},
   "FA-BOILER": {"zone": "BOILER", "zone_name": "Котельня", "kind": "heat", "kind_name": "теплові", "n": 2, "spacing": 6.4,
                 "area": 72, "loop": 2, "state": "ok", "alarm_state": "normal", "compliance": "ok", "stale": false}
  },
  "totals": {"detectors": 212, "mcp": 36, "sounders": 41, "mcp_max_m": 26.9, "flame": 3, "spark_detectors": 4,
             "state": "Норма, 1 попередження", "sprinkler": "Спринклерна система в режимі очікування"},
  "events": [
   {"time": "2026-10-12 09:58", "level": "warn", "code": "FA-FAC", "text": "Попередження про запиленість: сповіщувач 2.FAC.07 (дільниця фасадів, шліфування)."},
   {"time": "2026-10-12 08:47", "level": "warn", "code": "SPARK-1", "text": "Іскрогасіння: іскру виявлено на магістралі аспірації над лінією A, гасіння 0,6 с, лінію не зупиняли."},
   {"time": "2026-10-12 07:00", "level": "info", "code": "FACP-1", "text": "Щотижнева перевірка оповіщувачів: усі 4 шлейфи — норма."},
   {"time": "2026-10-11 23:10", "level": "info", "code": "SPARK-1", "text": "Самотест іскрогасіння: датчики й клапан гасіння — норма."}
  ],
  "panel": {"code": "FACP-1", "state": "normal", "state_text": "Норма, 1 попередження", "comm": "online",
            "last_seen": "2026-10-14 10:15", "alarms": 0, "faults": 0, "disabled": 0, "sounders": false, "brigade": false},
  "systems": {"SPARK-1": {"state": "ok", "text": "Норма, іскор за добу — 1", "count_today": 1},
              "SMOKE-CTRL": {"state": "ok", "text": "Клапани закриті, живлення від мережі", "vents_open": false},
              "SPRINKLERS": {"state": "ok", "text": "Спринклерна система в режимі очікування", "pressure_bar": 7.25}}
 },
 "evacuation": {
  "exits": [{"code": "EX-S1", "x": 14.0, "y": 0.0, "side": "S", "width": 1.2, "ok": true}, "… 11 ще …"],
  "routes": {"Z-CUT": {"name": "Розкрій", "exit": "EX-S2", "length": 22.5, "path": [[49.75, 22.25], [50.25, 0.25]], "ok": true, "norm": 240},
             "…": "31 ще"},
  "max_distance": 45.3, "worst_point": [32.25, 33.75],
  "drill_origin": "FA-CNC", "drill_zone": "Присадка", "drill_detector": "2.CNC.05",
  "norm_distance": 240, "norm_ref": "ДБН В.2.2-27:2025 «Промислові будівлі», п. 8.2.2, табл. 8.2 (…) + прим. 5",
  "norm_alt": 50, "norm_alt_ref": "ДБН В.2.2-27:2025 п. 8.2.11 — якщо стінові й покрівельні панелі з полімерним утеплювачем; тупики — не довше 25 м (п. 8.2.9); ворота не рахуються виходами (п. 8.2.6).",
  "drill_steps": [{"t": 0, "who": "Пожежна сигналізація", "text": "Сповіщувач 2.CNC.05 (Присадка): дим і тепло — тривога на приладі."},
                  {"t": 3, "who": "Пожежна сигналізація", "text": "Увімкнено 41 сирен-маяків по всьому цеху."}, "… 6 ще …"],
  "drill_active": null,
  "compliance": {"routes_ok": 32, "routes_total": 32, "worst": 38.6, "norm": 240, "exits_ok": true, "smoke_ok": 8, "smoke_total": 8}
 }
}
```

Під час навчання `drill_active` = `{"name": "DRILL/2026/0003", "zone": "Присадка", "zone_code": "FA-CNC", "detector":
"2.CNC.05", "started": "2026-10-14 10:20", "elapsed_s": 42, "steps_done": 4, "steps_total": 8, "on_site": 35,
"evacuated": 3}`. Рядки `"… N ще …"` у прикладі — скорочення документа, не частина контракту.

## Додаток D. Довідник норм (`data/f3d_fire_norm.csv`, 27 записів; A-27)

`value_set = (value is not None)`; `note` і `sources` — дослівно з JSON макета (для авторських — колонка «ref» і `note`
«Додано автором модуля: …», `sources` порожньо); `sequence` = 10·№ у межах групи; `unit` — коротка одиниця з таблиці
(повний текст одиниці JSON дописується на початок `note` у дужках, бо `unit` — Char(64)). Ключі 1–27:

| # | group | key | name | value | unit | ref |
|---|---|---|---|---|---|---|
| 1 | detection | `smoke_spacing_6_12m` | Відстань між димовими сповіщувачами (висота до 12 м) | 8,8 | м | ДБН В.2.5-56:2014 зі Зміною № 2, табл. 7.2 (висота приміщення до 12,0 м, квадратна схема) |
| 2 | detection | `smoke_wall_6_12m` | Відстань від димового сповіщувача до стіни (висота до 12 м) | 4,4 | м | ДБН В.2.5-56:2014 зі Зміною № 2, табл. 7.2; мінімальна відстань — ДСТУ-Н CEN/TS 54-14:2009, А.6.5.1 c) |
| 3 | detection | `smoke_area_6_12m` | Площа на один димовий сповіщувач (висота 6–12 м) | — | м² | ДБН В.2.5-56:2014 зі Зміною № 2, п. 7.2.11, табл. 7.2; ДСТУ-Н CEN/TS 54-14:2009, дод. А.6.5.1, табл. А.1 |
| 4 | detection | `heat_spacing` | Відстань між тепловими сповіщувачами | 6,4 | м | ДБН В.2.5-56:2014 зі Зміною № 2, табл. 7.1 (квадратна схема) |
| 5 | detection | `heat_wall` | Відстань від теплового сповіщувача до стіни | 3,2 | м | = `ref` `heat_spacing` |
| 6 | detection | `heat_area` | Площа на один тепловий сповіщувач | — | м² | ДБН В.2.5-56:2014 зі Зміною № 2, табл. 7.1; ДСТУ-Н CEN/TS 54-14:2009, табл. А.1 |
| 7 | detection | `mcp_spacing` | Найбільший шлях до ручного сповіщувача | 30 | м | ДБН В.2.5-56:2014 зі Зміною № 2, п. 7.2.11.3 (посилання на 6.5.1, 6.5.4 ДСТУ CEN/TS 54-14); ДСТУ-Н CEN/TS 54-14:2009, 6.5.4 та А.6.5.4; ДБН п. 7.2.21 |
| 8 | detection | `mcp_height` | Висота встановлення ручного сповіщувача | — | м | ДСТУ-Н CEN/TS 54-14:2009, А.6.5.4 |
| 9 | detection | `flame_detector_note` | Розміщення сповіщувачів полум'я | — | — | ДБН В.2.5-56:2014 зі Зміною № 2, п. 7.2.11.2, 7.2.25, 7.2.28, табл. А.2 п. 7.28–7.30; ДСТУ-Н CEN/TS 54-14:2009, 6.5.3, А.6.5.3 |
| 10 | detection | `spark_detection_required` | Система виявлення й гасіння іскор | — | — | ДБН В.2.5-56:2014 зі Зміною № 2, дод. А, табл. А.2, п. 7.6–7.8; VdS 3845:2026-05; VdS 2106 |
| 11 | alerting | `sounder_level` | Рівень звуку оповіщення, мінімум | 65 | дБА | ДБН В.2.5-56:2014 зі Зміною № 2, п. 9.3.1, 9.3.5, 9.3.8, 9.3.10; ДСТУ-Н CEN/TS 54-14:2009, А.6.6.2 a) |
| 12 | alerting | `sounder_bg_production` | Фоновий шум: механічні цехи | 85 | дБА | ДБН В.2.5-56:2014 зі Зміною № 2, п. 9.3.10 |
| 13 | alerting | `sounder_bg_storage` | Фоновий шум: виробничі приміщення | 80 | дБА | ДБН В.2.5-56:2014 зі Зміною № 2, п. 9.3.10 |
| 14 | alerting | `sounder_bg_office` | Фоновий шум: офіси | 55 | дБА | ДБН В.2.5-56:2014 зі Зміною № 2, п. 9.3.10 |
| 15 | evacuation | `evac_distance_prod_B` | Найбільша відстань до евакуаційного виходу (кат. В, ≥ 80 тис. м³) | 240 | м | ДБН В.2.2-27:2025 «Промислові будівлі», п. 8.2.2, табл. 8.2 (об'єм ≥80 тис. м³, кат. В, ступінь I, II, III, IIIа, щільність потоку до 1 ос/м²) + прим. 5 |
| 16 | evacuation | `evac_distance_polymer` | Найбільша відстань до виходу при полімерному утеплювачі панелей | 50 | м | ДБН В.2.2-27:2025 п. 8.2.11 — якщо стінові й покрівельні панелі з полімерним утеплювачем; тупики — не довше 25 м (п. 8.2.9); ворота не рахуються виходами (п. 8.2.6). |
| 17 | evacuation | `evac_exits_min` | Мінімальна кількість евакуаційних виходів | 2 | шт. | ДБН В.1.1-7:2016 п. 7.2.4; ДБН В.2.2-27:2025 п. 8.2.9 (приміщення кат. В площею >1000 м² — щонайменше два виходи (двері)) |
| 18 | evacuation | `exit_width_min` | Мінімальна ширина шляху евакуації | 1,0 | м | ДБН В.1.1-7:2016 п. 7.3.6 (ширина шляхів евакуації ≥1,0 м, висота ≥2,0 м); ДБН В.2.2-27:2025 п. 8.2.13, табл. 8.4; п. 8.2.15 |
| 19 | evacuation | `door_width_min` | Мінімальна ширина евакуаційних дверей у просвіті | 0,8 | м | ДБН В.1.1-7:2016 п. 7.2.7; ДБН В.2.2-27:2025 п. 8.2.14 |
| 20 | evacuation | `exit_dispersal_k` | Коефіцієнт розосередженості виходів (L = k·√П) | 1,5 | — | ДБН В.1.1-7:2016 п. 7.2.6 |
| 21 | smoke | `smoke_exhaust_required` | Обов'язковість димовидалення | 1 | так/ні | ДБН В.2.5-56:2014 (зі Змінами № 1, 2) п. 10.2.4 г); п. 10.5.1; ДБН В.2.2-27:2025 п. 8.1.20, п. 6.3.2 |
| 22 | smoke | `smoke_zone_max_area` | Найбільша площа димової зони | 1600 | м² | ДБН В.2.5-56:2014 (зі Змінами № 1, 2) п. 10.4.2 |
| 23 | smoke | `smoke_vent_area` | Аеродинамічна площа люків на 400 м² підлоги (орієнтир) | 1,5 | м² Aa | Muster-Industriebaurichtlinie (Німеччина) п. 5.7 — орієнтир; в Україні площу визначають розрахунком (ДСТУ CEN/TR 12101-5, ДСТУ EN 12101-2), нормованого відсотка не знайдено |
| 24 | smoke | `smoke_vent_aa` | Аеродинамічна площа одного люка LAMILUX F100 | 1,02 | м² | Паспорт `smoke_vent` (`plant/equipment_specs.json`): LAMILUX Smoke Lift Glass Skylight F100 1200×1200, EN 12101-2 |
| 25 | other | `lightning_class` | Клас (рівень) блискавкозахисту | 2 | клас | ДБН В.2.2-27:2025 п. 8.1.23 (→ ДСТУ EN 62305-1, ДСТУ IEC 62305-2, ДСТУ EN 62305-3, -4); ДСТУ Б В.2.5-38:2008 дод. А, пп. 2, 4 |
| 26 | other | `eyewash_required` | Фонтан для промивання очей | — | так/ні | НПАОП 40.1-1.21-98 (ПБЕЕС) п. 6.6.5; ПТЕЕС (наказ Мінпаливенерго № 258) розд. 10 |
| 27 | other | `pv_roof_fire` | Відстані для дахової ФЕС | — | м | Українських норм із відстанями для дахових ФЕС не знайдено (ДБН В.1.1-7:2016, ДБН В.2.5-56:2014, ДБН В.2.2-27:2025 — не містять). Орієнтир: Merkblatt Fachkommission Bauaufsicht «Hinweise zur Errichtung von PV-Anlagen» (08.05.2026); VdS 2098 (дод. S1) |
