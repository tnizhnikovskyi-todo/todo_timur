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
│   ├── viewer_provider.py               M-17 (реєструється лише якщо 'f3d.viewer.provider' in env — через
│   │                                    умовний _inherit у __init__ моделей, як telemetry M-10)
│   ├── push_handler.py                  M-18 (умовно, якщо 'f3d.push.handler' in env)
│   └── iot_sim_bridge.py                FR-23: методи запуску fire_drill (умовно, якщо 'f3d.sim.panel' in env)
├── tools/
│   ├── __init__.py
│   ├── states.py                        таблиці BACnetLifeSafetyState → стани (R-10, R-11), тексти
│   ├── geometry.py                      сітки R-02/R-03/R-04, точка в прямокутнику, відстані; чисті функції
│   ├── sync.py                          R-10…R-14, R-19: читання сигналів → стани → події → шина
│   └── gen_data.py                      генератор data/*.csv|xml з макета (§5.2); запускається з кореня репозиторію
├── wizard/
│   ├── __init__.py
│   ├── drill_rollcall_wizard.py         M-11d (TransientModel) перекличка
│   └── drill_rollcall_views.xml         V-18
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
│   ├── f3d_fire_norm.csv                20 норм (noupdate=1)
│   ├── f3d_fire_panel.xml               1 прилад + 4 шлейфи (M-01, M-02)
│   ├── f3d_fire_zone.csv                33 зони
│   ├── f3d_fire_system.xml              3 системи
│   ├── f3d_fire_smoke_zone.csv          8 димових зон
│   ├── f3d_fire_device.csv              343 пристрої
│   ├── f3d_fire_exit.csv                12 виходів
│   ├── f3d_fire_route.csv               32 маршрути (path у JSON-колонці)
│   ├── f3d_fire_drill_template.xml      1 шаблон, 8 кроків
│   ├── f3d_source_data.xml              2 джерела (noupdate=1)
│   ├── f3d_signal_data.csv              52 сигнали (noupdate=1)
│   ├── mail_activity_type.xml           тип активності «Пожежна тривога»
│   └── neutralize.sql
├── static/description/icon.png
└── tests/
    ├── __init__.py
    ├── common.py                        FireCase(TransactionCase): фікстури, фейкові показання, помічник push_text()
    ├── test_norms.py                    AC-05…AC-11 (R-01…R-04, R-08)
    ├── test_event.py                    AC-12…AC-16 (M-05, R-14)
    ├── test_sync.py                     AC-17…AC-27 (R-10…R-13, R-19)
    ├── test_security_readonly.py        AC-28…AC-31, ТБ-01…ТБ-04 (FR-18)
    ├── test_requests.py                 AC-32 (зв'язок заявок)
    ├── test_evacuation.py               AC-33…AC-40 (R-05…R-09, звіт)
    ├── test_drill.py                    AC-41…AC-52 (R-15…R-18)
    ├── test_passage_source.py           AC-53, AC-54 (CF-02)
    ├── test_viewer_provider.py          AC-55…AC-59 (R-20, R-21)
    ├── test_hooks.py                    AC-01…AC-04, AC-60…AC-62 (§5.4, §5.5)
    └── stand/                           pytest -m stand (ТК-01…ТК-10) — поза odoo.tests
        ├── conftest.py
        ├── test_tk_facp.py
        ├── test_tk_drill.py
        └── test_tk_readonly.py
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
        "data/f3d_fire_route.csv",
        "data/f3d_fire_drill_template.xml",
        "data/f3d_source_data.xml",
        "data/f3d_signal_data.csv",
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
(LAMILUX F100, паспорт `smoke_vent`), `cover_tol_m` **не** норма — параметр (§3 ARCH). Разом у CSV: 23 рядки
(20 з JSON + 3 авторських з позначкою `note="Додано автором модуля: …"`); далі в документі «20 норм» означає
ключі з макета, «23 записи» — файл.

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
| `action_create_signals(self)` | `groups=manager`; для `is_detector`/`mcp`/`sounder`/`flame` з `panel_id.source_id`: якщо `state_signal_id` порожній → `f3d.signal.create({code: "fire/devices/%s/state" % address, name: "%s: стан" % name, kind: 'state', unit: '', equipment_id: equipment_id, source_id: panel_id.source_id, address: {"object":"life-safety-point","instance": lsp_instance,"property":"present-value"}, period_s: 30, store_period_s: 3600, module: 'fire_safety', origin: 'catalog', write_enabled: False, alarm_states: ['fault','fault-pre-alarm','fault-alarm','test-fault','test-fault-alarm'], alarm_title: "Несправність пристрою %s (%s): стан {text}" % (address, zone)})`; для `is_detector` додатково `dust_signal_id` → `{code: "fire/devices/%s/dust" % address, kind: 'gauge', unit: '%', address: {"object":"analog-value","instance": lsp_instance}, period_s: 600, warn_high: dust_warn_pct, alarm_high: dust_alarm_pct, alarm_title: "Очистити сповіщувач %s (%s): запиленість {value} % при нормі до {threshold}"}`; `monitor=True`; повторний виклик — нічого (ключ `code` унікальний у telemetry). Повертає `display_notification` з кількістю створених |
| `action_remove_signals(self)` | `monitor=False`; сигнали **не** видаляються (журнал показань), а `active=False` (якщо telemetry має `active`; інакше `source_id=False`) — Q-06 |
| `action_f3d_show(self)` | `equipment_id.action_f3d_show()` (груповий 3D-об'єкт, Q-09); без обладнання → `plant_zone_id.action_f3d_show()` |
| `_set_state(self, new_state, raw, ts, reliability=None)` | запис полів; подія R-14 рівня пристрою лише для `alarm`/`prealarm`/`fault`/`disabled`/`test` (перехід) і повернення; зона — через власний сигнал (не з пристрою) |
| `_set_dust(self, pct, ts)` | `dust_pct`, `dust_ts`; перехід `dust_state` → події `dust_warn`/`dust_alarm`/`dust_ok` (R-13 п. 3); зона `warn` перераховується через `@api.depends('device_ids.dust_state')` |
| `@api.model lsp_id(loop, ordinal, nn)` | R-23 |
