# factory3d_fire_safety — специфікація

Версія 0.1 · 14.10.2026 · технічне рішення: `docs/modules/factory3d_fire_safety/ARCHITECTURE.md` (далі «ARCH»;
FR-xx, A-xx, Q-xx — звідти). Контракти, на які спирається документ: `factory3d_base` CB-01, CB-03, CB-04,
CB-07, CB-08, CB-09, CB-10, CB-12; `factory3d_viewer` M-01, M-03, API-03, Додаток A.13; `factory3d_telemetry`
CT-01, CT-03, CT-05, CT-06, CT-07, CT-09 (ARCH telemetry §2.1; SPEC telemetry — паралельно, Q-06/Q-07);
`factory3d_iot_sim` SPEC §8.11 (P-09), §8.4.1 (unit 85), §9.1 R-25…R-27, §9.3 S-07/S-08, API-13, Додаток A
(сигнали 189, 603–646); каркас `docs/ARCHITECTURE.md` §5, §6.4, §6.7, §6.8, D-07. Контракти, що задає модуль, —
CF-01…CF-05 (ARCH §2.1). Усі рядки інтерфейсу — українською в коді (D-14), без `.po`; жодних `x_`-полів.

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
│   ├── f3d_fire_drill.py                M-11, M-11a, M-11b, M-11c
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
    ├── test_norms.py                    AC-05…AC-11, AC-69, AC-70 (R-01…R-04, R-08, R-23)
    ├── test_event.py                    AC-12…AC-16, AC-68 (M-05, R-14, M-18)
    ├── test_sync.py                     AC-17…AC-27, AC-67 (R-10…R-13, R-19)
    ├── test_security_readonly.py        AC-28…AC-31, AC-66, ТБ-01…ТБ-04 (FR-18)
    ├── test_requests.py                 AC-32 (зв'язок заявок)
    ├── test_evacuation.py               AC-33…AC-40 (R-05…R-09, звіт)
    ├── test_drill.py                    AC-41…AC-52 (R-15…R-18)
    ├── test_passage_source.py           AC-53, AC-54 (CF-02)
    ├── test_viewer_provider.py          AC-55…AC-57, AC-59 (R-20, R-21 — функції tools/payload без viewer)
    ├── test_hooks.py                    AC-01…AC-04, AC-60…AC-62 (§5.4, §5.5)
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
| `x_from`, `x_to` | Float | `digits=(8,1)`, `string="X від, м"`/`"X до, м"` (0/42, 42/92, 92/122, 122/151 — `plant/fire.py:LOOPS`) |
| `detectors_count`, `mcp_count`, `sounders_count`, `flame_count` | Integer | `compute="_compute_device_counts"`, `store=True`: `search_count` пристроїв шлейфу за типами (`detectors` = smoke+multi+heat) |
| `modules_count` | Integer | `string="Модулі вводу"`, з data (шлейф 2 — 4: 3 полум'я + 1 іскрогасіння; `fire.loops[2].modules`) |
| `device_count` | Integer | compute: усі пристрої шлейфу |
| `signal_id` | Many2one `f3d.signal` | `string="Сигнал несправності (BI)"` |
| `state` | Selection | `[('unknown','Невідомо'),('ok','Норма'),('fault','Несправність')]`, `default='unknown'`, readonly |
| `fault_since` | Datetime | readonly |
| `request_id` | Many2one `maintenance.request` | `related='signal_id.maintenance_request_id'`, readonly |
| `device_ids` | One2many `f3d.fire.device` `loop_id` | |

Обмеження: `UNIQUE(panel_id, number)` «Номер шлейфу має бути унікальним у межах приладу»; `@api.constrains('number')`: 1 ≤ number ≤ 8 («Cerberus PRO FC726-ZA: до 8 кілець з розширенням; у макеті 4»), текст «Номер шлейфу: 1…8».
Методи: `_set_state(new, ts)` — `ok`/`fault`, подія `loop_fault`/`loop_ok` (R-14), `fault_since`; `loop_of(x)` `@api.model` → шлейф, для якого `x_from ≤ x < x_to` (як `fire.loop_of`), інакше порожньо.

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
| `_compute_coverage(self)` | R-02 → `cover_max_gap_m`, `cover_point`, `cover_ok`; після обох — `compliance`: `fail` якщо `not n_ok` або `cover_max_gap_m > r + 2·tol`; `warn` якщо `not cover_ok` (у межах 2·tol) або `warn`-пристрої; інакше `ok`; `compliance_note` |
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
| `_set_dust(self, pct, ts)` | `dust_pct`, `dust_ts`; перехід `dust_state` → події `dust_warn`/`dust_alarm`/`dust_ok` (R-13 п. 3); зона `warn` перераховується через `@api.depends('device_ids.dust_state')` |
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

```python
class F3dFirePassageSource(models.AbstractModel):
    _name = "f3d.fire.passage.source"
    _description = "Пожежна безпека: джерело даних про людей на об'єкті"
    _f3d_priority = 1000          # менше — пріоритетніше
    _f3d_key = "none"             # пишеться в f3d.fire.drill.passage_source
```

| Метод | Вхід → вихід | Поведінка бази |
|---|---|---|
| `_f3d_available(self) -> bool` | — | `False` |
| `_f3d_on_site(self, at: datetime) -> list[dict]` | UTC naive → `[{"employee_id": int, "since": datetime, "point": str}]` | `[]` |
| `_f3d_passages(self, start, end) -> list[dict]` | UTC → `[{"employee_id": int, "ts": datetime, "point": str, "direction": "out"\|"in"}]` | `[]` |
| `@api.model _f3d_get_source(self) -> model` | → модель-реалізація | кандидати: `self.env.registry.descendants(['f3d.fire.passage.source'], '_inherit')` мінус сама база; лишити ті, де `_f3d_available()`; повернути з найменшим `(_f3d_priority, _name)`; якщо жодної — `env['f3d.fire.passage.source.hr_attendance']` |

#### M-12a `f3d.fire.passage.source.hr_attendance` (пріоритет 100, `_f3d_key = "hr_attendance"`)

- `_f3d_available()` → `True`.
- `_f3d_on_site(at)`: `env['hr.attendance'].sudo().search([('check_in','<=',at), '|', ('check_out','=',False),
  ('check_out','>',at)], order='check_in, id')`; на кожного працівника — перший запис: `{"employee_id": att.employee_id.id,
  "since": att.check_in, "point": "Відмітка входу"}`. Демо 14.10: 35 записів (`check_in` 12.10 03:58–04:00 UTC,
  `check_out` порожній) → 35 людей для будь-якого `at` після 12.10 04:00 UTC.
- `_f3d_passages(start, end)`: `search([('check_out','>=',start), ('check_out','<=',end)], order='check_out')` →
  `{"employee_id", "ts": check_out, "point": "Відмітка виходу", "direction": "out"}`.

#### M-12b `f3d.fire.passage.source.access` (пріоритет 10, `_f3d_key = "access"`, A-19)

- `_f3d_available()` → `'f3d.access.event' in self.env`.
- `_f3d_access_model(self)` → `self.env['f3d.access.event'].sudo()` (окремий метод — тести підміняють його фейком).
- `_f3d_on_site(at)`: `res = _f3d_access_model().f3d_on_site_at(at)` (access CA-03); для `emp in res['employees']`:
  `{"employee_id": emp.id, "since": emp.f3d_access_last_in or at, "point": "СКУД"}`; відвідувачі
  (`res['visitors']`) у список людей навчання не входять — їх кількість пишеться в чаттер навчання при старті
  («На об'єкті також N відвідувачів (СКУД)»).
- `_f3d_passages(start, end)`: `events = _f3d_access_model().f3d_passes_between(start, end, direction='out')`;
  для подій з `employee_id` і (`door_id.is_perimeter`, якщо поле є, інакше всі): `{"employee_id",
  "ts": ev.ts, "point": ev.door_id.code, "direction": "out"}`.

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
  _get_param('drill_sim_duration_s', 300)}`; `return env['f3d.sim.run'].sudo()._create_and_start(scenario, params)`
  (iot_sim M-05; стоп-кран `factory3d.iot_sim.write_enabled` перевіряє iot_sim — його `UserError` пробрасується).
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
Кнопка «Показати в 3D» — `icon="fa-cube"`, `invisible="not viewer_available"` (там, де поле є) — інакше CB-02
сам повідомляє про відсутній переглядач. Жодна кнопка, дія чи пункт меню модуля не створює `f3d.command` і не
викликає запис у пристрій (AC-31).

| ID | XML-id (модуль `factory3d_fire_safety`) | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `view_f3d_fire_panel_form` | form `f3d.fire.panel` | `<header>`: `action_recompute_compliance` («Перерахувати норми», `groups=group_f3d_manager`), `action_view_3d_alarm` («Тривога в 3D», `btn-danger`, `invisible="state not in ('alarm','prealarm') or not viewer_available"`), `action_f3d_show` («Показати в 3D»), `action_set_bacnet_device` («Змінити BACnet device», `groups=group_f3d_admin`), `action_add_comment` («Коментар у журнал», `groups=group_f3d_fire_drill`). Над `<sheet>`: `<div class="alert alert-danger" role="alert" invisible="state != 'alarm'">` з `state_text`; `alert-warning` `invisible="comm != 'lost'"` «Зв'язок із приладом втрачено з <last_seen>»; `alert-info` `invisible="read_enabled"` «Обробку сигналів вимкнено стоп-краном»; `alert-warning` `invisible="not compliance_dirty"` «Норми або пристрої змінено — перерахуйте відповідність». Статбокс: `action_view_zones` (`zone_count`, «Зони», `fa-th`), `action_view_devices` (`device_count`, «Пристрої»), `action_view_events` (`event_count`, «Події за 7 діб», `fa-list`), `warn_count` («Попередження», без дії, `invisible="not warn_count"`), `action_view_requests` («Заявки ТО», `fa-wrench`). `<sheet>`: `name` (title); група «Стан»: `state` (badge), `state_text`, `raw_state`, `system_state`, `state_ts`, `comm` (badge: `online` success, `stale` warning, `lost` danger, `off` muted), `last_seen`, `comm_since`, `alarms_count`, `faults_count`, `disabled_count`, `sounders_active`, `brigade_transmitted`, `alarm_zone_ids` (`many2many_tags`, `invisible="not alarm_zone_ids"`); група «Прилад»: `code`, `equipment_id`, `manufacturer`, `model`, `zone_id`, `x`, `y`, `company_id` (`groups="base.group_multi_company"`). `<notebook>`: «Шлейфи» (`loop_ids` list readonly: `number`, `x_from`, `x_to`, `detectors_count`, `mcp_count`, `sounders_count`, `flame_count`, `modules_count`, `state` badge, `request_id`); «Системи» (`system_ids` list readonly: `code`, `name`, `state` badge, `state_text`, `count_today`, `last_test_date`); «Відповідність нормам» (групи: «Розстановка» — `compliance_zones_ok`/`compliance_zones_total` («Зони відповідають»), `compliance_mcp_max_m`, `compliance_mcp_point`, `compliance_mcp_ok`, `compliance_sounder_max_m` з підказкою A-26, `compliance_missing_zones`; «Евакуація» — `compliance_routes_ok`/`compliance_routes_total`, `compliance_exits_ok`, `compliance_exit_pair_m`, `compliance_exit_l_m`, `evac_max_distance_m`, `evac_worst_x`, `evac_worst_y`; «Димовидалення» — `compliance_smoke_ok`/`compliance_smoke_total`; `compliance_ts`); «Сигнали» (`groups=group_f3d_manager`: `source_id`, `io_source_id`, `signal_state_id`, `signal_system_id`, `signal_alarms_id`, `signal_faults_id`, `signal_disabled_id`, `signal_sounders_id`, `signal_brigade_id`). Невидимі: `read_enabled`, `viewer_available`, `sim_available`, `compliance_dirty`. Чаттер (`mail.thread`, `mail.activity`) |
| V-02 | `view_f3d_fire_panel_kanban` | kanban `f3d.fire.panel` (Огляд) | `create="false"`, картка `t-name="card"` на всю ширину: велика плашка стану (клас за `state`: `text-bg-danger` alarm/prealarm, `text-bg-warning` fault/disabled, `text-bg-info` test, `text-bg-success` normal, `text-bg-secondary` unknown) з `state_text`; рядок «Зв'язок: `comm` · останнє показання `last_seen`»; лічильники «Зон `zone_count` · у тривозі `alarm_zone_count` · попереджень `warn_count`»; `systems_text`; «Ручні: найбільша відстань `compliance_mcp_max_m` м»; кнопки `action_view_zones` («Зони»), `action_view_events` («Журнал»), `action_f3d_show` («3D»), `action_recompute_compliance` (manager); клік — форма V-01 |
| V-01a | `view_f3d_fire_loop_list` / `_form` | `f3d.fire.loop` | list: `panel_id`, `number`, `name`, `x_from`, `x_to`, `device_count`, `detectors_count`, `mcp_count`, `sounders_count`, `flame_count`, `modules_count`, `state` (badge), `fault_since`, `request_id`; form: ті самі поля групами «Шлейф», «Пристрої», «Стан», вкладка `device_ids` (list readonly: `address`, `type`, `zone_id`, `state`) |
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
| `data/f3d_fire_panel.xml` | 1 + 4 | `panel_facp_1`; `loop_1`…`loop_4` | прилад: `name` «Приймально-контрольний прилад», `code` `FACP-1`, `zone_id` ref `factory3d_base.zone_z_office`, `x` 97.2, `y` 58.25 (`FACP_POS`), `evac_max_distance_m` 45.3, `evac_worst_x` 32.25, `evac_worst_y` 33.75 (`evac_routes.json`); шлейфи: `number`, `x_from`/`x_to` з `LOOPS` (0/42, 42/92, 92/122, 122/151), `modules_count` 0/4/0/0 (`fire.loops[n].modules`) |
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
