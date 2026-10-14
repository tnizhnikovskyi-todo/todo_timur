# factory3d_access — специфікація

Версія 0.1 · 14.10.2026 · автор: агент-архітектор модуля (хвиля 2, фаза 4) · статус: **чернетка на погодження**.
Технічне рішення: `docs/modules/factory3d_access/ARCHITECTURE.md` (далі ARCH; FR-01…FR-20, CA-01…CA-09,
A-01…A-27, Q-01…Q-14). Каркас: `docs/ARCHITECTURE.md` §5 (конвенції, стоп-крани), §6.1 (код сцени), §6.2 (зони),
§6.5 (рядок `biostar2` — опитування REST прямо з Odoo), §6.6 **P-10**, §6.7 (провайдер переглядача).

Контракти, на які спирається (посилання на ідентифікатори інших модулів):

| Модуль | Ідентифікатори |
|---|---|
| `factory3d_base` | CB-01 `f3d.scene.mixin` (`f3d_code`, `f3d_alias`, `search_f3d`, `action_f3d_show`), M-10 `hr.employee` + Додаток B (35 кодів `OP-*`, бейдж = код без дефісів), CB-03 `f3d.zone` (`zone_at`, xml-id `factory3d_base.zone_<slug>`), Додаток C/C.2 (`Z-KPP`, `Z-ASM`, `Z-FG`, `Z-ELEC`, `Z-POST`, `Z-CHG`, `Z-FAC`, `Z-MAINT`…), Додаток F (`TURNSTILES → Z-KPP`, `ACCESS` без зони), CB-09 (меню `factory3d_base.menu_f3d_root`, sequence 70 зарезервовано), CB-10 (групи `group_f3d_user/manager/admin`, параметр `factory3d.base.environment`), §5.1 (читання булевих параметрів) |
| `factory3d_viewer` | M-01 (хук `f3d.viewer.provider`: `_f3d_sequence`, `_f3d_sections`, `_f3d_group`, `_f3d_viewer_collect`, `_f3d_viewer_delta`; виклик за префіксом імені `f3d.viewer.provider.`), M-01f (провайдер `people` пише `employees[code].present` з `hr.attendance`), M-03 (`f3d.viewer.event._notify(model, codes, kind)`), R-02 (час «YYYY-MM-DD HH:MM» за Києвом), R-14 (delta копіює `_f3d_sections` провайдера цілком), Додаток A.11 (`employees[code]`, `zones[code]`) |
| `factory3d_iot_sim` | «документація вендора» P-10 §8.12: API-40 `POST /api/login`, API-41 `POST /api/logout`, API-42 `GET /api/users`, API-43 `GET /api/devices`, API-44 `GET /api/doors`, API-45 `POST /api/events/search`, API-46 `GET /api/event_types`; коди подій, `tna_key`; R-28 (розклад проходів), S-09 `access_event`, API-13 (запуск сценарію), API-14 (`POST /time`), Додаток A рядки 647–653 (7 сигналів `access/*`), §8.1.3 (порти 8443/8081) |
| `factory3d_telemetry` | CT-09 (`access/*` → `module='access'`, SPEC R-15), CT-10 / SPEC M-03 `f3d.signal._f3d_ingest(readings, src='module')` |
| `factory3d_fire_safety` | ARCH CF-02 (джерело проходів для навчальної тривоги), Q-10, Q-15 (прапор «навчання триває») — відповідь цього модуля: CA-03, CA-09 |

Odoo 19: SQL-обмеження — `models.Constraint`, індекси — `models.Index`, хуки — `post_init_hook(env)` /
`uninstall_hook(env)`, o2m/m2m — `odoo.fields.Command`. Факти стандарту перевірено на тестовому сервері
timur-o19demo, база `odoo` (лише читання, 14.10.2026) і в коді `odoo/odoo` гілки 19.0
(`addons/hr_attendance/models/hr_attendance.py`, `hr_employee.py`; `addons/hr/models/hr_employee.py`,
`hr_employee_public.py`): `hr.attendance.date` — `compute`, `store`, `required` (дата входу в tz працівника);
`in_mode`/`out_mode` — `readonly` Selection (`kiosk`, `systray`, `manual`, `technical`; `out_mode` ще `auto_check_out`);
`_check_validity` забороняє другу відкриту відмітку працівника і перетин інтервалів («Cannot create new attendance
record for …»); `hr.employee` вже має `last_check_in`, `last_check_out`, `last_attendance_id`, `attendance_state`;
користувач без `hr.group_hr_user` читає `hr.employee` лише через SQL-представлення `hr.employee.public`
(поля, яких там немає, дають `AccessError`).

Усі імена остаточні. Рядки інтерфейсу — українською в коді (D-14). Жодного `x_`-поля.

## 0. Дерево файлів модуля

```
odoo_addons/factory3d_access/
├── __init__.py                       from . import models, wizard; from .hooks import post_init_hook, uninstall_hook
├── __manifest__.py                   §1
├── README.md                         призначення, установка, параметри (ARCH §3), інструкції ARCH §4.1–4.6
├── CHANGELOG.md                      19.0.1.0.0 — перший випуск; розділ «Міграція демо» з фактичними кількостями
├── hooks.py                          post_init_hook(env), uninstall_hook(env), run_all(env) -> dict (§5.3, §5.4)
├── tools/
│   ├── __init__.py
│   ├── biostar_client.py             BioStarClient, BioStarError/AuthError/WriteDisabled, SecretFilter (§7, R-11, R-16)
│   ├── event_codes.py                classify(code) -> dict; таблиця кодів (R-09)
│   ├── dates.py                      parse_bs_dt, fmt_bs_dt, to_local_str, local_date, schedule_end_utc (R-07, R-15)
│   └── params.py                     get_flag/get_int/get_str/set_param для factory3d.access.* (§5.1)
├── models/
│   ├── __init__.py                   f3d_access_server, f3d_access_device, f3d_access_door, f3d_access_user_link,
│   │                                 f3d_access_visitor, f3d_access_card, f3d_access_event, hr_employee, hr_attendance,
│   │                                 f3d_zone, f3d_access_presence, res_config_settings, viewer_provider,
│   │                                 telemetry_bridge, fire_passage_source
│   ├── f3d_access_server.py          M-01 (опитування R-11, сесія R-16, синхронізація R-19)
│   ├── f3d_access_device.py          M-02
│   ├── f3d_access_door.py            M-03 (стан R-10)
│   ├── f3d_access_user_link.py       M-04 (зв'язок R-03)
│   ├── f3d_access_event.py           M-05 (обробка R-02…R-10, службові методи R-21)
│   ├── f3d_access_card.py            M-06 (R-13)
│   ├── f3d_access_visitor.py         M-07 (R-14)
│   ├── hr_employee.py                M-08 hr.employee, M-08a hr.employee.public
│   ├── hr_attendance.py              M-09
│   ├── f3d_zone.py                   M-10
│   ├── f3d_access_presence.py        M-14 (SQL-представлення «Люди по зонах», A-17)
│   ├── res_config_settings.py        M-11
│   ├── viewer_provider.py            M-12 f3d.viewer.provider.access (R-12, A-19)
│   ├── telemetry_bridge.py           M-15 f3d.access.telemetry (R-18)
│   └── fire_passage_source.py        M-16 f3d.fire.passage.source.access (CA-09, A-24)
├── wizard/
│   ├── __init__.py
│   ├── event_reprocess_wizard.py     M-13
│   └── event_reprocess_wizard_views.xml  V-14
├── security/
│   ├── f3d_access_security.xml       привілей, групи, implied, record rules (§4.2, §4.3)
│   └── ir.model.access.csv           §4.1
├── data/
│   ├── ir_config_parameter.xml       §5.1 (noupdate="1")
│   ├── ir_cron.xml                   §6 (6 кронів)
│   ├── f3d_access_server_data.xml    1 сервер «BioStar 2 (емулятор)» (noupdate="1")
│   ├── f3d_access_device_data.xml    5 пристроїв + 5 дверей P-10 (noupdate="1")
│   ├── scene_home_zones.csv          7 рядків code,zone для складських (читає хук, не модель)
│   └── neutralize.sql                §5.5
├── views/
│   ├── f3d_access_server_views.xml   V-01
│   ├── f3d_access_device_views.xml   V-02
│   ├── f3d_access_door_views.xml     V-03
│   ├── f3d_access_user_link_views.xml V-04
│   ├── f3d_access_event_views.xml    V-05, V-06 (журнал, «Проходи СКУД»)
│   ├── f3d_access_card_views.xml     V-07
│   ├── f3d_access_visitor_views.xml  V-08
│   ├── f3d_access_presence_views.xml V-09
│   ├── hr_employee_views.xml         V-10
│   ├── hr_attendance_views.xml       V-11
│   ├── f3d_zone_views.xml            V-12
│   ├── res_config_settings_views.xml V-13
│   └── menus.xml                     V-15 (дії й меню)
└── tests/
    ├── __init__.py                   імпортує test_* (крім stand/)
    ├── common.py                     AccessCase(TransactionCase), FakeBioStar, make_row(), фікстури §13.1
    ├── fixtures/
    │   ├── login_ok.json             відповідь API-40 (тіло)
    │   ├── login_fail.json           {"Response": {"code": "101", …}}
    │   ├── users.json                API-42: 36 рядків (35 бейджів + "1" Administrator)
    │   ├── devices.json              API-43: 5 рядків
    │   ├── doors.json                API-44: 5 рядків
    │   └── events_shift.json         API-45: зміна 2026-10-12 за R-28 (§13.1, 140 + 12 рядків)
    ├── test_client.py                AC-04, AC-05, AC-58
    ├── test_server.py                AC-01…AC-03, AC-06…AC-09, AC-14
    ├── test_sync.py                  AC-11…AC-13
    ├── test_events.py                AC-10, AC-24, AC-25, AC-31…AC-33, AC-34
    ├── test_attendance.py            AC-15…AC-23, AC-26
    ├── test_presence.py              AC-27…AC-30, AC-35…AC-38
    ├── test_cards.py                 AC-39…AC-43
    ├── test_visitors.py              AC-44…AC-48
    ├── test_viewer_provider.py       AC-49…AC-52
    ├── test_settings.py              AC-53…AC-57
    ├── test_hooks.py                 AC-59…AC-61
    ├── test_security.py              AC-62…AC-66
    └── stand/                        pytest -m stand (не імпортується Odoo): conftest.py, test_tk_*.py (ТК-01…ТК-10)
```

Також W5 здає `docs/modules/factory3d_access/DEPLOY_TEST.md` і `TEST_REPORT.md` (§13.5).

## 1. Маніфест

```python
{
    "name": "Завод 3D: доступ (СКУД BioStar 2)",
    "summary": "Suprema BioStar 2: відмітки в Відвідуванні, картки, турнікети, відвідувачі, люди по зонах",
    "description": "Опитування REST BioStar 2 з Odoo (P-10): журнал подій, відмітки hr.attendance за проходами "
                   "периметра, присутність і зона людей, стан дверей, картки й відвідувачі під стоп-краном запису.",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Attendances",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["factory3d_base", "hr_attendance", "mail"],
    "data": [
        "security/f3d_access_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/f3d_access_server_data.xml",
        "data/f3d_access_device_data.xml",
        "data/ir_cron.xml",
        "views/f3d_access_server_views.xml",
        "views/f3d_access_device_views.xml",
        "views/f3d_access_door_views.xml",
        "views/f3d_access_user_link_views.xml",
        "views/f3d_access_event_views.xml",
        "views/f3d_access_card_views.xml",
        "views/f3d_access_visitor_views.xml",
        "views/f3d_access_presence_views.xml",
        "views/hr_employee_views.xml",
        "views/hr_attendance_views.xml",
        "views/f3d_zone_views.xml",
        "views/res_config_settings_views.xml",
        "wizard/event_reprocess_wizard_views.xml",
        "views/menus.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": ["requests"]},
    "installable": True,
    "application": False,
}
```

Порядок `data`: групи й правила → доступи → параметри → сервер → пристрої/двері (посилаються на сервер і
зони `factory3d_base.zone_*`) → крони → представлення (дії оголошено у файлі представлень своєї моделі) →
майстер → меню (посилаються на дії). `scene_home_zones.csv` і `neutralize.sql` у `data` не перелічені: перший
читає хук (`odoo.tools.file_open`), другий виконує `odoo-bin neutralize`. Python-залежності: `requests` (входить
у вимоги Odoo 19, перевірено ≥ 2.31), `pytz` (ядро Odoo); тести — `freezegun` (вимоги Odoo). Опційні модулі
(`factory3d_viewer`, `factory3d_telemetry`, `factory3d_fire_safety`) у `depends` **не** входять: модуль
перевіряє `'<model>' in self.env` (A-19, A-24).
