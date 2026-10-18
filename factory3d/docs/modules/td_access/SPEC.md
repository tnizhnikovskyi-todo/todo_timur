# factory3d_access — специфікація

Версія 0.2 · 14.10.2026 (0.1 — 14.10.2026) · автор: агент-архітектор модуля (хвиля 2, фаза 4) · статус: **чернетка на погодження**.
Зміни: 15.10.2026 — за рішенням модуля (build/modules/factory3d_access.md): DEC-10 (V-12 `action_f3d_access_settings` і AC-69: `target='current'` замість `inline`, недопустимого в Odoo 19).

Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-23 і X-87 (M-12, R-12 п. 7: дельта доповнює `patch` через `deep_merge` —
картки `infra` і ключі CA-05 `employees`/`zones`; AC-51, AC-67), X-33 (міст `factory3d_access_telemetry` створює 7 сигналів
`access/*`: §0, §1, M-17, §5.3, R-18, AC-53, AC-68), X-09 (A-21: `f3d_code` працівника тепер у `hr.employee.public`, base
M-10a), X-89 (правило X-32: пункт «Налаштування СКУД» `menu_f3d_access_settings` під `factory3d_base.menu_f3d_config`,
sequence 70, дія `action_f3d_access_settings`; §0, §3, AC-69); Q-10, Q-11 закрито.
Технічне рішення: `docs/modules/factory3d_access/ARCHITECTURE.md` (далі ARCH; FR-01…FR-20, CA-01…CA-09,
A-01…A-27, Q-01…Q-14). Каркас: `docs/ARCHITECTURE.md` §5 (конвенції, стоп-крани), §6.1 (код сцени), §6.2 (зони),
§6.5 (рядок `biostar2` — опитування REST прямо з Odoo), §6.6 **P-10**, §6.7 (провайдер переглядача).
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-01, Q-02, Q-04, Q-05, Q-14.
Зміни: 14.10.2026 — закрито рішеннями менеджера: Q-03, Q-09, Q-12, Q-13.
Зміни: 14.10.2026 — закрито відповідями замовника № 20–24: Q-06, Q-07, Q-08.

Контракти, на які спирається (посилання на ідентифікатори інших модулів):

| Модуль | Ідентифікатори |
|---|---|
| `factory3d_base` | CB-01 `f3d.scene.mixin` (`f3d_code`, `f3d_alias`, `search_f3d`, `action_f3d_show`), M-10 `hr.employee` + Додаток B (35 кодів `OP-*`, бейдж = код без дефісів), CB-03 `f3d.zone` (`zone_at`, xml-id `factory3d_base.zone_<slug>`), Додаток C/C.2 (`Z-KPP`, `Z-ASM`, `Z-FG`, `Z-ELEC`, `Z-POST`, `Z-CHG`, `Z-FAC`, `Z-MAINT`…), Додаток F (`TURNSTILES → Z-KPP`, `ACCESS` без зони), CB-09 (меню `factory3d_base.menu_f3d_root`, sequence 70 зарезервовано), CB-10 (групи `group_f3d_user/manager/admin`, параметр `factory3d.base.environment`), §5.1 (читання булевих параметрів) |
| `factory3d_viewer` | M-01 (хук `f3d.viewer.provider`: `_f3d_sequence`, `_f3d_sections`, `_f3d_group`, `_f3d_viewer_collect`, `_f3d_viewer_delta`; виклик за префіксом імені `f3d.viewer.provider.`), M-01f (провайдер `people` пише `employees[code].present` з `hr.attendance`), M-03 (`f3d.viewer.event._notify(model, codes, kind)`), R-02 (час «YYYY-MM-DD HH:MM» за Києвом), R-14 (дельта: власний розділ — цілком, спільні `infra`/`employees`/`zones` — лише через `deep_merge`, хелпер `factory3d_viewer/tools/payload.py`; X-23, X-82), Додаток A.11 (`employees[code]`, `zones[code]`) |
| `factory3d_iot_sim` | «документація вендора» P-10 §8.12: API-40 `POST /api/login`, API-41 `POST /api/logout`, API-42 `GET /api/users`, API-43 `GET /api/devices`, API-44 `GET /api/doors`, API-45 `POST /api/events/search`, API-46 `GET /api/event_types`; коди подій, `tna_key`; R-28 (розклад проходів), S-09 `access_event`, API-13 (запуск сценарію), API-14 (`POST /time`), Додаток A рядки 647–653 (7 сигналів `access/*`), §8.1.3 (порти 8443/8081) |
| `factory3d_telemetry` | CT-09 (`access/*` → `module='access'`, SPEC R-15), CT-10 / SPEC M-03 `f3d.signal._f3d_ingest(readings, src='module')`, M-03 `origin='module'` (X-16), R-07 (сигнали без джерела не стають `stale`); сигнали створює міст `factory3d_access_telemetry` (M-17, X-33) |
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
│   ├── res_config_settings_views.xml V-13 + дія `action_f3d_access_settings` (X-89)
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
    │   ├── events_shift.json         API-45: зміна 2026-10-12 за R-28 (§13.1, 140 + 12 рядків)
    │   └── gen_events_shift.py       генератор events_shift.json (Odoo не вантажить)
    ├── test_client.py                AC-04, AC-05, AC-56, AC-58
    ├── test_server.py                AC-01…AC-03, AC-06…AC-09, AC-14
    ├── test_sync.py                  AC-11…AC-13
    ├── test_events.py                AC-10, AC-24, AC-25, AC-31…AC-33, AC-34
    ├── test_attendance.py            AC-15…AC-23, AC-26
    ├── test_presence.py              AC-27…AC-30, AC-35…AC-38
    ├── test_cards.py                 AC-39…AC-43
    ├── test_visitors.py              AC-44…AC-48
    ├── test_viewer_provider.py       AC-49…AC-52, AC-67
    ├── test_settings.py              AC-53…AC-55, AC-57
    ├── test_hooks.py                 AC-59…AC-61
    ├── test_security.py              AC-62…AC-66, AC-69
    └── stand/                        pytest -m stand (не імпортується Odoo): conftest.py, test_tk_*.py (ТК-01…ТК-10)
```

Міст до телеметрії (X-33, каркас §3) — окремий модуль-місток, ставиться автоматично, коли встановлені обидва модулі:

```
odoo_addons/factory3d_access_telemetry/
├── __init__.py                       from . import models; from .hooks import post_init_hook
├── __manifest__.py                   §1 (міст)
├── hooks.py                          post_init_hook(env) → env['f3d.access.telemetry']._f3d_ensure_signals() (§5.3)
├── models/
│   ├── __init__.py                   f3d_access_telemetry
│   └── f3d_access_telemetry.py       M-17: f3d.access.telemetry (+ _f3d_ensure_signals), f3d.access.device (create/write)
└── tests/
    ├── __init__.py
    └── test_signals.py               AC-68
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
перевіряє `'<model>' in self.env` (A-19, A-24). Сигнали `access/*` у telemetry створює окремий міст
`factory3d_access_telemetry` (M-17, X-33) — маніфест моста:

```python
{
    "name": "Завод 3D: доступ — сигнали телеметрії",
    "summary": "7 сигналів СКУД access/* у factory3d_telemetry",
    "version": "19.0.1.0.0",
    "category": "Hidden",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["factory3d_access", "factory3d_telemetry"],
    "data": [],
    "post_init_hook": "post_init_hook",
    "auto_install": True,
    "installable": True,
    "application": False,
}
```

Міст не має власних моделей, прав, меню й даних XML: сигнали створює `post_init_hook` (§5.3), бо обладнання
`ACCESS`/`TURNSTILES` шукається за кодом сцени (base CB-01), а не за xml-id.

## 2. Моделі

Спільні позначення: `req` = `required=True`; `idx` = `index=True`; `ro` = `readonly=True`; типи — `fields.*`.
Усі `Datetime` — naive UTC (стандарт Odoo); перетворення — `tools/dates.py` (R-15). Параметри
`factory3d.access.*` читаються через `tools/params.py` (§5.1) з `sudo()`. Регулярні вирази (R-01):
`CODE_RE = ^[A-Z0-9]+(-[A-Z0-9]+)*$` (≤ 32, як base R-01), `BSID_RE = ^[0-9A-Za-z_\-]{1,64}$`,
`URL_RE = ^https?://[A-Za-z0-9.\-]+(:[0-9]{1,5})?/?$`, `CARD_RE = ^[0-9]{1,32}$`.
Групи скорочено: **S** = `factory3d_access.group_f3d_access_security`, **A** = `factory3d_access.group_f3d_access_admin`,
**F** = `factory3d_base.group_f3d_admin`, **U** = `factory3d_base.group_f3d_user`,
**H** = `hr_attendance.group_hr_attendance_user`.

### M-01 `f3d.access.server` — сервер BioStar 2 (FR-01, FR-05, FR-19)

```python
class F3dAccessServer(models.Model):
    _name = "f3d.access.server"
    _description = "СКУД: сервер BioStar 2"
    _order = "sequence, id"
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char(64) | `req`, `string="Назва"`, `default="BioStar 2"` |
| `sequence` | Integer | `default=10` |
| `url` | Char(255) | `req`, `string="URL сервера"`, `help="Напр. https://iot-sim:8443 (стенд) або https://biostar.local (прод)"`; при `create`/`write` кінцевий `/` обрізається |
| `verify_ssl` | Boolean | `string="Перевіряти сертифікат"`, `default=True` |
| `timeout_connect_s` | Integer | `string="Тайм-аут з'єднання, с"`, `default=5` |
| `timeout_read_s` | Integer | `string="Тайм-аут відповіді, с"`, `default=30` |
| `active` | Boolean | `default=True` |
| `company_id` | Many2one `res.company` | `req`, `idx`, `default=lambda s: s.env.company` |
| `session_id` | Char(128) | `string="Сесія (bs-session-id)"`, `ro`, `copy=False`, `groups="factory3d_base.group_f3d_admin"` |
| `state` | Selection | `[('offline','Не підключено'),('online','Онлайн'),('error','Помилка')]`, `req`, `default='offline'`, `ro`, `copy=False` |
| `stale` | Boolean | `compute="_compute_stale"` (не зберігається): `state == 'online'` і `last_contact < now − 3·poll_interval_s` |
| `last_contact` | Datetime | `ro`, `string="Останній контакт"` |
| `last_error` | Char(255) | `ro`, `string="Остання помилка"` — лише HTTP-код, `Response.code` і `Response.message` або клас винятку; без URL з параметрами, заголовків, тіл запитів |
| `last_error_ts` | Datetime | `ro` |
| `error_count` | Integer | `ro`, `default=0`, `string="Помилок поспіль"` |
| `next_try_at` | Datetime | `ro`, `string="Наступна спроба"` (R-16) |
| `last_event_ts` | Datetime | `ro`, `copy=False`, `string="Курсор: час останньої події"` (R-11) |
| `last_event_biostar_id` | Char(64) | `ro`, `copy=False`, `string="Курсор: id останньої події"` |
| `last_poll_at` | Datetime | `ro`, `string="Останнє опитування"` |
| `last_poll_rows` | Integer | `ro`, `string="Рядків в останньому опитуванні"` |
| `last_poll_new` | Integer | `ro`, `string="Нових подій в останньому опитуванні"` |
| `last_poll_more` | Boolean | `ro`, `string="Є ще сторінки"` (досягнуто `max_pages_per_run`) |
| `users_total` | Integer | `ro`, `string="Користувачів у BioStar"` (`UserCollection.total`) |
| `devices_total` | Integer | `ro`, `string="Пристроїв у BioStar"` |
| `users_synced_at`, `devices_synced_at` | Datetime | `ro` |
| `device_ids` | One2many `f3d.access.device` `server_id` | `string="Пристрої"` |
| `door_ids` | One2many `f3d.access.door` `server_id` | `string="Двері"` |
| `link_count`, `unlinked_count`, `event_count`, `error_event_count` | Integer | `compute` (не зберігаються): `search_count` зв'язків; зв'язків з `match='none'` і `in_biostar=True`; подій; подій з `process_state='error'` |
| `doors_without_zone` | Integer | `compute`: активних дверей без `zone_to_id` (ризик ARCH §5.2) |

Обмеження:

```python
    _f3d_access_server_timeouts = models.Constraint(
        "CHECK(timeout_connect_s BETWEEN 1 AND 60 AND timeout_read_s BETWEEN 1 AND 300)",
        "Тайм-аути: з'єднання 1–60 с, відповідь 1–300 с.")
```

`@api.constrains("url", "verify_ssl")` `_check_url`: (1) `URL_RE.match(url)` інакше
`ValidationError("URL сервера BioStar: очікується http(s)://хост[:порт], напр. https://iot-sim:8443")`;
(2) `verify_ssl=False` і `factory3d.base.environment != 'test'` →
`ValidationError("Вимкнути перевірку сертифіката можна лише в тестовому середовищі (factory3d.base.environment = test).")`;
(3) схема `http://` і `environment != 'test'` → `ValidationError("HTTP без TLS дозволено лише в тестовому середовищі.")`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `_get_client(self) -> BioStarClient` | `ensure_one()`; `BioStarClient(url, login=get_str('biostar_login','admin'), password=get_str('biostar_password',''), verify_ssl, timeout=(timeout_connect_s, timeout_read_s), session_id=self.sudo().session_id or None, write_enabled=get_flag('write_enabled'))`. Окремий метод — тести патчать його на `FakeBioStar` (`unittest.mock.patch.object`) |
| `_save_session(self, client)` | якщо `client.session_id != self.sudo().session_id` → `self.sudo().write({'session_id': client.session_id})` |
| `_mark_ok(self)` | `write({'state':'online','last_contact':now,'error_count':0,'next_try_at':False})` (sudo) |
| `_mark_error(self, exc)` | R-16: `n = error_count + 1`; `write({'state':'error','error_count':n,'last_error':str(exc)[:255],'last_error_ts':now,'next_try_at': now + min(60·2**(n−1), 600) с})`; `_logger.warning("BioStar %s: %s", name, exc)` (через `SecretFilter`) |
| `@api.model _cron_poll(self)` | якщо `not get_flag('read_enabled')` → `_logger.info` і вихід; для кожного `search([('active','=',True)])`: якщо `next_try_at and next_try_at > now` → пропустити; інакше `server._poll()`; кожен сервер — у `try/except Exception` (лише `_mark_error`, не перекидати) і `self.env.cr.commit()` після сервера (крон) — **лише** якщо `not self.env.context.get('f3d_no_commit')` і `not self.env.registry.in_test_mode()` |
| `_poll(self) -> dict` | R-11; повертає `{'rows': n, 'new': k, 'processed': p, 'more': bool}` |
| `_poll_window(self, since, until, max_pages=None) -> dict` | R-11 кроки 3–7 для заданого вікна без руху курсора (майстер M-13, перевірка 24 год R-20) |
| `action_poll_now(self)` | `groups=A`; `not read_enabled` → `UserError("Опитування BioStar вимкнено стоп-краном factory3d.access.read_enabled.")`; блокування рядка R-11 крок 1 не вдалося → `UserError("Опитування вже виконується. Спробуйте за хвилину.")`; `res = self._poll()`; повертає `display_notification` `type='success'`, `title="Опитування BioStar"`, `message="Рядків: %(rows)s, нових подій: %(new)s, оброблено: %(processed)s"` |
| `action_test_connection(self)` | `groups=F`; працює **незалежно** від `read_enabled` (A-18); окремий клієнт без збереженої сесії: `login()` → `users_total = list_users_total()` → `devices = list_devices()` → `logout()`; `write({users_total, devices_total: len(devices)})` + `_mark_ok()`; повідомлення `"З'єднання встановлено: користувачів %s, пристроїв %s"`; будь-який `BioStarError` → `_mark_error(e)` і `display_notification` `type='danger'` з `str(e)` (без секретів). Збережена `session_id` не змінюється |
| `action_sync_users(self)` / `action_sync_devices(self)` | `groups=A`; потребують `read_enabled` (той самий `UserError`); викликають `_sync_users()` / `_sync_devices()` (R-19), повідомлення з лічильниками |
| `@api.model _cron_sync_users(self)`, `_cron_sync_devices(self)` | як `_cron_poll`, але `_sync_users()` / `_sync_devices()` |
| `_sync_users(self) -> dict`, `_sync_devices(self) -> dict` | R-19 |
| `action_reset_cursor(self)` | `groups=F`; `write({'last_event_ts': False, 'last_event_biostar_id': False})` — наступне опитування за `initial_lookback_h` |
| `action_open_events/_links/_errors(self)` | `ir.actions.act_window` на `f3d.access.event` (`domain=[('server_id','=',id)]`, для `_errors` ще `('process_state','=','error')`), `f3d.access.user.link` |
| `_compute_stale` | `poll_interval_s = get_int('poll_interval_s', 60)` |

### M-02 `f3d.access.device` — зчитувач/контролер BioStar (FR-02)

```python
class F3dAccessDevice(models.Model):
    _name = "f3d.access.device"
    _description = "СКУД: пристрій BioStar"
    _order = "server_id, code"
    _rec_names_search = ["code", "name", "biostar_id"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char(128) | `req`, `string="Назва"` (з `GET /api/devices` `name` або data) |
| `code` | Char(32) | `req`, `idx`, `string="Код сцени"`, `help="ACR-IN, ACR-ELEC… (plant/infra.py:DOOR_READERS)"` |
| `server_id` | Many2one `f3d.access.server` | `req`, `idx`, `ondelete='cascade'` |
| `company_id` | Many2one | `related='server_id.company_id'`, `store=True`, `idx` |
| `biostar_id` | Char(64) | `string="ID у BioStar"`, `idx` (`5390001`…) |
| `device_type` | Char(64) | `ro`, `string="Тип"` (`device_type_id.name`, «BioEntry W3») |
| `ip` | Char(64) | `ro`, `string="IP"`, `groups=A` |
| `status` | Selection | `[('online','У мережі'),('offline','Не в мережі'),('unknown','Невідомо')]`, `default='unknown'`, `ro` |
| `status_ts` | Datetime | `ro` |
| `sync_fail_count` | Integer | `ro`, `default=0` |
| `direction` | Selection | `[('in','Вхід'),('out','Вихід'),('tna','За клавішею T&A')]`, `req`, `default='in'`, `string="Напрямок"`, `help="tna: вхід/вихід за tna_key події (1 — вхід, 2 — вихід)"` |
| `equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання"`, `ondelete='set null'`, `domain=[('f3d_code','!=',False)]` (`ACCESS`, `TURNSTILES`) |
| `x`, `y` | Float | `digits=(8,2)`, `string="X, м"` / `"Y, м"` (координати зчитувача з макета) |
| `zone_id` | Many2one `f3d.zone` | `string="Зона"`, `ondelete='set null'`, `help="Зона, звідки підходять до зчитувача (зона «з» дверей)"` (A-23) |
| `door_ids` | One2many `f3d.access.door` `entry_device_id` | `string="Двері (вхід)"` |
| `last_event_ts` | Datetime | `ro` |
| `last_event_code` | Integer | `ro` |
| `events_today` | Integer | `compute`: подій з `device_id=self` і `ts ≥ початок сьогоднішньої доби за Києвом` |
| `active` | Boolean | `default=True` |
| `note` | Text | `string="Примітка"` |

```python
    _f3d_access_device_code_uniq = models.Constraint("UNIQUE(code)", "Код пристрою має бути унікальним.")
    _f3d_access_device_bsid_uniq = models.Constraint("UNIQUE(server_id, biostar_id)",
                                                     "Пристрій із таким ID BioStar уже є на цьому сервері.")
```

`@api.constrains("code", "biostar_id")`: `CODE_RE` → `ValidationError("Код пристрою %s: лише великі латинські літери, цифри й дефіси (напр. ACR-IN).")`;
`biostar_id` і не `BSID_RE` → `ValidationError("ID BioStar %s: 1–64 символи [0-9A-Za-z_-].")`.

Методи: `action_f3d_show(self)` — `equipment_id.action_f3d_show()` якщо є обладнання з `f3d_code`; інакше
`zone_id.action_f3d_show()`; інакше `UserError("Пристрій не прив'язаний ні до обладнання, ні до зони.")`.
`action_open_events(self)` — події пристрою.

### M-03 `f3d.access.door` — двері/турнікет BioStar (FR-03, CA-04)

```python
class F3dAccessDoor(models.Model):
    _name = "f3d.access.door"
    _description = "СКУД: двері або турнікет"
    _order = "server_id, code"
    _rec_names_search = ["code", "name", "biostar_id"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char(128) | `req`, `string="Назва"` |
| `code` | Char(32) | `req`, `idx`, `string="Код"` (`TURN-1`, `DOOR-ELEC`, `DOOR-CHG`, `DOOR-PAINT`, `DOOR-SRV`) |
| `kind` | Selection | `[('door','Двері'),('turnstile','Турнікет')]`, `req`, `default='door'` |
| `server_id` | Many2one `f3d.access.server` | `req`, `idx`, `ondelete='cascade'` |
| `company_id` | Many2one | `related='server_id.company_id'`, `store=True`, `idx` |
| `biostar_id` | Char(64) | `string="ID у BioStar"`, `idx` |
| `entry_device_id` | Many2one `f3d.access.device` | `string="Зчитувач входу"`, `ondelete='set null'` |
| `exit_device_id` | Many2one `f3d.access.device` | `string="Зчитувач виходу"`, `ondelete='set null'` |
| `zone_from_id` | Many2one `f3d.zone` | `string="Із зони"`, `ondelete='set null'` |
| `zone_to_id` | Many2one `f3d.zone` | `string="У зону"`, `ondelete='set null'` |
| `is_perimeter` | Boolean | `string="Периметр (відмітки)"`, `default=False`, `help="Проходи через ці двері створюють і закривають відмітки Відвідування (A-04)"` |
| `dwell_min` | Integer | `string="Повернення в домашню зону, хв"`, `default=0`, `help="0 — зона лишається до наступного проходу"` |
| `open_duration_s` | Integer | `ro`, `string="Час відчинення, с"` (`open_duration` з API-44) |
| `state` | Selection | `[('unknown','Невідомо'),('locked','Зачинено на замок'),('unlocked','Розблоковано'),('open','Відчинено'),('closed','Зачинено'),('forced','Відчинено силоміць'),('held','Тримається відчиненим')]`, `req`, `default='unknown'`, `ro` |
| `state_ts` | Datetime | `ro` |
| `alarm` | Boolean | `ro`, `default=False`, `string="Тривога"` |
| `alarm_reason` | Selection | `[('forced','Відчинено силоміць'),('held','Тримається відчиненим'),('fire','Пожежна тривога')]`, `ro` |
| `passes_today` | Integer | `compute`: подій `event_type='pass'` цих дверей від початку доби за Києвом |
| `active` | Boolean | `default=True` |

```python
    _f3d_access_door_code_uniq = models.Constraint("UNIQUE(code)", "Код дверей має бути унікальним.")
    _f3d_access_door_bsid_uniq = models.Constraint("UNIQUE(server_id, biostar_id)",
                                                   "Двері з таким ID BioStar уже є на цьому сервері.")
    _f3d_access_door_dwell = models.Constraint("CHECK(dwell_min BETWEEN 0 AND 1440)",
                                               "Повернення в домашню зону: 0–1440 хв.")
```

`@api.constrains("code","biostar_id","zone_from_id","zone_to_id","is_perimeter","entry_device_id","exit_device_id")`:
`CODE_RE`/`BSID_RE` як M-02; рівно одна із зон задана → `ValidationError("Задайте обидві зони дверей («Із зони» і «У зону») або жодної.")`;
`is_perimeter` без `zone_to_id` → `ValidationError("Двері периметра потребують зони «У зону».")`;
пристрій іншого сервера → `ValidationError("Зчитувач має належати тому самому серверу BioStar.")`.

Методи: `_f3d_set_state(self, state, ts, alarm=None, reason=None)` — R-10; `action_f3d_show(self)` —
`entry_device_id.action_f3d_show()`; `action_open_events(self)`; `action_ack_alarm(self)` (`groups=S`) —
`alarm=False`, `alarm_reason=False`, шина (R-10 крок 4).

### M-04 `f3d.access.user.link` — користувач BioStar ↔ людина (FR-04)

```python
class F3dAccessUserLink(models.Model):
    _name = "f3d.access.user.link"
    _description = "СКУД: користувач BioStar"
    _order = "server_id, biostar_user_id"
    _rec_name = "biostar_user_id"
    _rec_names_search = ["biostar_user_id", "biostar_name"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `server_id` | Many2one `f3d.access.server` | `req`, `idx`, `ondelete='cascade'` |
| `company_id` | Many2one | `related='server_id.company_id'`, `store=True`, `idx` |
| `biostar_user_id` | Char(64) | `req`, `idx`, `string="Користувач BioStar (user_id)"` |
| `biostar_name` | Char(128) | `ro`, `string="Ім'я в BioStar"` (для ручного зв'язування; не для збігу, A-03) |
| `employee_id` | Many2one `hr.employee` | `idx`, `ondelete='set null'`, `string="Працівник"` |
| `visitor_id` | Many2one `f3d.access.visitor` | `idx`, `ondelete='set null'`, `string="Відвідувач"` |
| `match` | Selection | `[('barcode','За бейджем'),('alias','За другим кодом сцени'),('code','За кодом сцени без дефісів'),('manual','Вручну'),('visitor','Відвідувач'),('none','Не зв\'язано')]`, `req`, `default='none'`, `ro` (крім `manual` — ставиться `write`, R-03 крок 6) |
| `user_group` | Char(64) | `ro`, `string="Група BioStar"` |
| `disabled` | Boolean | `ro`, `string="Вимкнено в BioStar"` |
| `start_dt`, `expiry_dt` | Datetime | `ro`, `string="Діє з"` / `"Діє до"` |
| `card_count` | Integer | `ro`, `string="Карток у BioStar"` |
| `has_face` | Boolean | `ro`, `string="Є шаблон обличчя"` (`face_count > 0`; сам шаблон не читається, A-09) |
| `has_finger` | Boolean | `ro`, `string="Є відбиток"` (`fingerprint_template_count`/`finger_count > 0`, якщо ключ є) |
| `in_biostar` | Boolean | `ro`, `default=True`, `string="Є в BioStar"` (False — не повернувся в останній повній синхронізації) |
| `synced` | Boolean | `ro`, `default=False`; `last_sync` Datetime `ro` |
| `event_count` | Integer | `compute` |
| `active` | Boolean | `default=True` |

```python
    _f3d_access_link_uniq = models.Constraint("UNIQUE(server_id, biostar_user_id)",
                                              "Користувач BioStar уже зв'язаний на цьому сервері.")
    _f3d_access_link_employee_uniq = models.Constraint("UNIQUE(server_id, employee_id)",
                                                       "Працівник уже має користувача BioStar на цьому сервері.")
    _f3d_access_link_one_holder = models.Constraint("CHECK(employee_id IS NULL OR visitor_id IS NULL)",
                                                    "Користувач BioStar належить або працівнику, або відвідувачу.")
```

`@api.constrains("biostar_user_id")`: не `BSID_RE` → `ValidationError("Користувач BioStar %s: 1–64 символи [0-9A-Za-z_-].")`.
`display_name` (`_compute_display_name`): `"OPSAW1 · Олег Мельник"` — `biostar_user_id` + `employee_id.name` або
`visitor_id.name` або `biostar_name` або «не зв'язано».

`write(vals)`: якщо у `vals` є `employee_id` або `visitor_id` і немає `match` → `vals['match'] = 'manual'` (працівник)
/ `'visitor'` (відвідувач) / `'none'` (обидва порожні). Методи: `@api.model _f3d_match_employee(self, biostar_user_id)` —
R-03; `action_rematch(self)` (`groups=A`) — R-03 для записів з `match in ('none','barcode','alias','code')`;
`action_open_events(self)`.

### M-05 `f3d.access.event` — подія BioStar (FR-05…FR-09, FR-20, CA-03)

```python
class F3dAccessEvent(models.Model):
    _name = "f3d.access.event"
    _description = "СКУД: подія BioStar"
    _order = "ts desc, id desc"
    _log_access = False
```

| Поле | Тип | Параметри |
|---|---|---|
| `server_id` | Many2one `f3d.access.server` | `req`, `idx`, `ondelete='cascade'` |
| `company_id` | Many2one | `related='server_id.company_id'`, `store=True`, `idx` |
| `biostar_id` | Char(64) | `req`, `string="ID події BioStar"` (`rows[].id`) |
| `ts` | Datetime | `req`, `idx`, `string="Час"` (`datetime`, UTC) |
| `server_ts` | Datetime | `string="Час сервера"` (`server_datetime`) |
| `received_at` | Datetime | `req`, `default=fields.Datetime.now`, `string="Отримано"` |
| `code` | Integer | `req`, `idx`, `string="Код події"` (`event_type_id.code`) |
| `code_name` | Char | `compute` (не зберігається): `event_codes.classify(code)['name']` («Успішна перевірка (картка)») |
| `event_type` | Selection | `[('pass','Прохід'),('fail','Невдала ідентифікація'),('denied','Відмова'),('door','Двері'),('alarm','Тривога'),('system','Система'),('other','Інше')]`, `req`, `idx`, `string="Тип"` (R-09) |
| `credential` | Selection | `[('card','Картка'),('face','Обличчя'),('finger','Відбиток'),('id_face','ID + обличчя'),('id_finger','ID + відбиток'),('pin','ID + PIN'),('other','Інше')]`, `string="Спосіб"` |
| `deny_reason` | Selection | `[('access_group','Немає в групі доступу'),('disabled','Користувач вимкнений'),('expired','Строк дії минув'),('blacklist','Чорний список'),('apb','Антипрохід'),('timed_apb','Антипрохід за часом'),('scheduled_lock','Заблоковано розкладом'),('other','Інше')]`, `string="Причина відмови"` |
| `tna_key` | Char(4) | `string="Клавіша T&A"` (`""`, `"1"`, `"2"`) |
| `direction` | Selection | `[('in','Вхід'),('out','Вихід'),('none','—')]`, `req`, `default='none'`, `string="Напрямок"` (R-02) |
| `raw_device_id` | Char(64) | `string="ID пристрою BioStar"` |
| `raw_door_id` | Char(64) | `string="ID дверей BioStar"` |
| `raw_user_id` | Char(64) | `idx`, `string="Користувач BioStar"`, `groups="factory3d_access.group_f3d_access_security,hr_attendance.group_hr_attendance_user"` |
| `device_id` | Many2one `f3d.access.device` | `idx`, `ondelete='set null'`, `string="Пристрій"` |
| `door_id` | Many2one `f3d.access.door` | `idx`, `ondelete='set null'`, `string="Двері"` |
| `is_perimeter` | Boolean | `idx`, `string="Периметр"` — копія `door_id.is_perimeter` на момент обробки |
| `zone_from_id`, `zone_to_id` | Many2one `f3d.zone` | `ondelete='set null'` — копії зон дверей на момент обробки |
| `link_id` | Many2one `f3d.access.user.link` | `ondelete='set null'` |
| `employee_id` | Many2one `hr.employee` | `idx`, `ondelete='set null'`, `string="Працівник"` |
| `visitor_id` | Many2one `f3d.access.visitor` | `idx`, `ondelete='set null'`, `string="Відвідувач"` |
| `unknown_user` | Boolean | `idx`, `string="Нерозпізнаний"` — є `raw_user_id`, але немає ні працівника, ні відвідувача |
| `process_state` | Selection | `[('new','Нова'),('done','Оброблена'),('error','Помилка')]`, `req`, `default='new'`, `idx` |
| `attendance_action` | Selection | `[('none','—'),('checked_in','Вхід: нова відмітка'),('attached','Прив\'язано до відкритої відмітки'),('checked_out','Вихід: відмітку закрито'),('merged','Злито з попередньою відміткою'),('duplicate','Повторний вхід'),('no_open','Вихід без відкритої відмітки'),('drill','Навчальна тривога'),('late','Запізніла подія'),('future','Відкладено: час у майбутньому'),('not_employee','Не працівник')]`, `req`, `default='none'`, `string="Дія з відміткою"` |
| `attendance_id` | Many2one `hr.attendance` | `ondelete='set null'`, `string="Відмітка"` |
| `presence_changed` | Boolean | `string="Змінено присутність/зону"` |
| `apb_suspect` | Boolean | `idx`, `string="Підозра на антипрохід"` (A-08) |
| `zone_violation` | Boolean | `idx`, `string="Порушення дозволених зон"` (відвідувач, R-14) |
| `error_message` | Char(255) | `string="Помилка обробки"` |
| `raw` | Json | `groups="factory3d_base.group_f3d_admin"`, лише при `keep_raw=True`, без ключа `user_id.name` (A-09) |

```python
    _f3d_access_event_uniq = models.Constraint("UNIQUE(server_id, biostar_id)",
                                               "Подія BioStar уже збережена (дублікат).")
    _f3d_access_event_emp_ts_idx = models.Index("(employee_id, ts)")
    _f3d_access_event_door_ts_idx = models.Index("(door_id, ts)")
    _f3d_access_event_visitor_ts_idx = models.Index("(visitor_id, ts)")
```

`display_name`: `"%s · %s · %s" % (to_local_str(ts), door_id.code or device_id.code or raw_device_id, code_name)`.

Методи:

| Сигнатура | Вхід → вихід | Алгоритм |
|---|---|---|
| `@api.model _f3d_ingest_rows(self, server, rows)` | `rows: list[dict]` (API-06) → `dict(created, duplicates, invalid)` | R-11 крок 5: для кожного рядка `_f3d_parse_row(server, row)`; невалідний (немає `id`/`datetime`/`event_type_id.code`, `BSID_RE` не пройшов, `int(code)` → `ValueError`) → `invalid += 1`, WARNING з `id`; дублікати в межах пакета й у БД (`search_read([('server_id','=',server.id),('biostar_id','in',ids)], ['biostar_id'])`) → `duplicates`; решта — `create(vals_list)` пакетами по 500 (sudo); повертає лічильники і `recordset` створених у ключі `records` |
| `@api.model _f3d_parse_row(self, server, row) -> dict` | рядок API-06 → `vals` | `biostar_id=str(row['id'])`; `ts=parse_bs_dt(row['datetime'])`; `server_ts=parse_bs_dt(row.get('server_datetime'))` або `False`; `code=int(row['event_type_id']['code'])`; `cls=classify(code)` → `event_type`, `credential`, `deny_reason`; `tna_key=str(row.get('tna_key') or '')`; `raw_device_id=str((row.get('device_id') or {}).get('id') or '')`; `door = row.get('door_id')`: якщо `list` → перший елемент, якщо `dict` → він; `raw_door_id=str(door.get('id') or '')`; `raw_user_id=str((row.get('user_id') or {}).get('user_id') or '')` (порожній для подій дверей/системи); `device_id` = пристрій сервера з `biostar_id=raw_device_id`; `door_id` = двері з `biostar_id=raw_door_id`, а якщо немає — перші двері з `entry_device_id` або `exit_device_id` = `device_id`; `raw` — лише якщо `keep_raw`: `deepcopy(row)` без `user_id.name`, `user_id.photo_exists`, `hint` |
| `_f3d_process(self, force=False)` | recordset → `None` | сортує `self` за `(ts, id)`; для кожної події з `process_state='new'` (або будь-якої при `force=True`): `with self.env.cr.savepoint():` R-02…R-10 (порядок — R-04 «Конвеєр обробки»); виняток → `process_state='error'`, `error_message=str(e)[:255]`, ERROR у лог; успіх → `process_state='done'` (крім `future`); після циклу — шина й телеметрія (R-12 крок 6, R-18) |
| `action_reprocess(self)` | кнопка (`groups=A`) | `self.sudo()._f3d_process(force=True)` для подій з `process_state in ('new','error')`; для `done` — лише крок класифікації й зв'язку (R-03), без повторних дій з відміткою, якщо `attendance_id` уже задано (ідемпотентність) |
| `@api.model f3d_on_site_at(self, ts, company=None) -> dict` | CA-03 | R-21 |
| `@api.model f3d_passes_between(self, t0, t1, door_codes=None, direction=None) -> recordset` | CA-03 | R-21 |
| `@api.model _f3d_drill_active(self, ts) -> bool` | CA-09 | R-21 крок 3 |
| `@api.model _gc(self, keep_days)` | → кількість видалених | R-20 крок 1 |
| `@api.model _f3d_last_events(self, limit=20) -> list[dict]` | для провайдера (R-12) | останні `limit` подій `event_type in ('pass','denied','fail','door','alarm')` за спаданням `ts` |
| `@api.model _f3d_bus(self, model, codes)` | `model: str`, `codes: set[str]` → `None` | R-12 крок 6: порожні `codes` або `'f3d.viewer.event' not in self.env` → вихід; інакше `self.env['f3d.viewer.event'].sudo()._notify(model, codes, 'state')`. Окремий метод — тести патчать його |
| `@api.model _cron_zone_dwell(self)` | крон (§6) | R-17 |
| `@api.model _cron_housekeeping(self)` | крон (§6) | R-20 кроки 1–6; кожен крок у `savepoint`, помилка кроку → ERROR у лог, решта кроків виконується |

Фільтри журналу (V-05, FR-09): «Відмови» `[('event_type','in',('denied','fail'))]`, «Антипрохід»
`['|',('deny_reason','in',('apb','timed_apb')),('apb_suspect','=',True)]`, «Нерозпізнані користувачі»
`[('unknown_user','=',True)]`, «Порушення зон» `[('zone_violation','=',True)]`, «Помилки обробки»
`[('process_state','=','error')]`, «Периметр» `[('is_perimeter','=',True)]`, «Сьогодні» (`ts` ≥ початок доби).

### M-06 `f3d.access.card` — картка доступу (FR-10)

```python
class F3dAccessCard(models.Model):
    _name = "f3d.access.card"
    _description = "СКУД: картка доступу"
    _inherit = ["mail.thread"]
    _order = "state, number"
    _rec_name = "number"
```

| Поле | Тип | Параметри |
|---|---|---|
| `number` | Char(32) | `req`, `idx`, `tracking=True`, `string="Номер картки (CSN)"` |
| `card_type` | Selection | `[('csn','CSN'),('wiegand','Wiegand'),('secure','Secure Credential'),('mobile','Mobile CSN')]`, `req`, `default='csn'`; `card_type_id` BioStar: `csn`→0, `wiegand`→1, `secure`→2, `mobile`→4 (стаття Suprema 24000091098) |
| `server_id` | Many2one `f3d.access.server` | `req`, `ondelete='restrict'`, `default` = перший активний сервер компанії |
| `company_id` | Many2one | `related='server_id.company_id'`, `store=True`, `idx` |
| `holder_type` | Selection | `[('employee','Працівник'),('visitor','Відвідувач'),('pool','Пул відвідувачів')]`, `req`, `default='employee'`, `tracking=True` |
| `employee_id` | Many2one `hr.employee` | `idx`, `ondelete='set null'`, `tracking=True` |
| `visitor_id` | Many2one `f3d.access.visitor` | `idx`, `ondelete='set null'`, `tracking=True` |
| `state` | Selection | `[('draft','Чернетка'),('active','Видана'),('blocked','Заблокована'),('returned','Повернута'),('lost','Втрачена')]`, `req`, `default='draft'`, `tracking=True` |
| `block_reason` | Char(128) | `tracking=True`, `string="Причина блокування"` |
| `issued_at`, `blocked_at`, `returned_at` | Datetime | `ro` |
| `biostar_card_id` | Char(64) | `ro`, `string="ID картки в BioStar"` (відповідь API-07) |
| `sync_state` | Selection | `[('local','Лише в Odoo'),('pending','Очікує запису'),('synced','Синхронізовано'),('error','Помилка')]`, `req`, `default='local'`, `tracking=True`, `ro` |
| `pending_op` | Selection | `[('issue','Видати'),('block','Заблокувати'),('unblock','Розблокувати'),('return','Повернути')]`, `ro` |
| `sync_error` | Char(255) | `ro` |
| `sync_ts` | Datetime | `ro` |
| `sync_attempts` | Integer | `ro`, `default=0` |
| `holder_name` | Char | `compute`: ім'я працівника/відвідувача або «Пул» |
| `active` | Boolean | `default=True` |

```python
    _f3d_access_card_uniq = models.Constraint("UNIQUE(server_id, number)", "Картка з таким номером уже є.")
```

`@api.constrains("number","holder_type","employee_id","visitor_id","state","block_reason")`:
`CARD_RE` → `ValidationError("Номер картки: лише цифри, до 32 знаків (CSN з BioStar).")`;
`holder_type='employee'` без `employee_id` або з `visitor_id` → `ValidationError("Картка працівника: вкажіть працівника.")`;
`holder_type='visitor'` без `visitor_id` → `ValidationError("Картка відвідувача: вкажіть відвідувача.")`;
`holder_type='pool'` з `employee_id`/`visitor_id` → `ValidationError("Картка пулу не прив'язується до людини.")`;
`state='blocked'` без `block_reason` → `ValidationError("Вкажіть причину блокування.")`;
дві картки зі `state='active'` в одного відвідувача → `ValidationError("У відвідувача вже є видана картка.")`.

Методи (переходи — §10.3; запис — R-13):

| Сигнатура | Групи | Алгоритм |
|---|---|---|
| `action_issue(self)` | S (лише `holder_type in ('visitor','pool')`), A | `state in ('draft','returned')` інакше `UserError("Видати можна лише чернетку або повернуту картку.")`; `holder_type='pool'` → `UserError("Спершу оберіть, кому видається картка.")`; `write({'state':'active','issued_at':now,'returned_at':False})`; `_f3d_queue('issue')` |
| `action_block(self)` | A | `state='active'` інакше `UserError`; без `block_reason` → `UserError("Вкажіть причину блокування.")`; `write({'state':'blocked','blocked_at':now})`; `_f3d_queue('block')` |
| `action_unblock(self)` | A | `state='blocked'` → `active`, `block_reason=False`; `_f3d_queue('unblock')` |
| `action_return(self)` | S, A | `state in ('active','blocked')` → `returned`, `returned_at=now`; картка відвідувача → `holder_type='pool'`, `visitor_id` лишається до R-20 крок 5 (історія); `_f3d_queue('return')` |
| `action_mark_lost(self)` | A | `state='lost'`, `block_reason='Втрачена'`; `_f3d_queue('block')` |
| `_f3d_queue(self, op)` | — | якщо `get_flag('write_enabled')`: `write({'pending_op': op, 'sync_state': 'pending', 'sync_attempts': 0, 'sync_error': False})` і одразу `_f3d_push()`; інакше `write({'pending_op': op, 'sync_state': 'local'})` і `message_post` «Запис у BioStar вимкнено стоп-краном. Виконайте операцію «%s» у BioStar вручну і натисніть «Позначити синхронізованим».» |
| `_f3d_push(self)` | — | R-13 крок 2–5 (sudo) |
| `action_retry_sync(self)` | A | `sync_state in ('error','local')` і `write_enabled` → `sync_state='pending'`, `_f3d_push()`; без `write_enabled` → `UserError("Запис у BioStar вимкнено стоп-краном factory3d.access.write_enabled.")` |
| `action_mark_synced(self)` | A | `sync_state in ('local','error')` → `write({'sync_state':'synced','sync_ts':now,'pending_op':False,'sync_error':False})`, `message_post` «Позначено синхронізованим вручну» |
| `@api.model _cron_card_sync(self)` | — | якщо `not write_enabled` → вихід; `search([('sync_state','in',('pending','error')),('sync_attempts','<',card_sync_max_attempts)], limit=100)._f3d_push()` |

### M-07 `f3d.access.visitor` — відвідувач (FR-11, CA-07)

```python
class F3dAccessVisitor(models.Model):
    _name = "f3d.access.visitor"
    _description = "СКУД: відвідувач"
    _inherit = ["mail.thread"]
    _order = "date_from desc, id desc"
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char(128) | `req`, `tracking=True`, `string="ПІБ"` |
| `visitor_company` | Char(128) | `string="Компанія"` |
| `host_employee_id` | Many2one `hr.employee` | `req`, `ondelete='restrict'`, `tracking=True`, `string="Хто приймає"` |
| `purpose` | Char(255) | `string="Мета візиту"` |
| `date_from` | Datetime | `req`, `default=fields.Datetime.now`, `tracking=True`, `string="З"` |
| `date_to` | Datetime | `req`, `default=lambda s: now + visitor_default_hours`, `tracking=True`, `string="До"` |
| `allowed_zone_ids` | Many2many `f3d.zone` | `relation='f3d_access_visitor_zone_rel'`, `string="Дозволені зони"`, `help="Порожньо — без перевірки"` |
| `card_id` | Many2one `f3d.access.card` | `ondelete='set null'`, `tracking=True`, `domain="[('holder_type','in',('pool','visitor')),('state','in',('draft','returned')),('server_id','=',server_id)]"` |
| `server_id` | Many2one `f3d.access.server` | `req`, `default` = перший активний сервер компанії |
| `company_id` | Many2one `res.company` | `req`, `idx`, `default=lambda s: s.env.company` |
| `biostar_user_id` | Char(64) | `tracking=True`, `string="Користувач BioStar"`, `help="Під стоп-краном запису модуль створює V-<id> сам; інакше введіть user_id, створений у BioStar"` |
| `link_id` | Many2one `f3d.access.user.link` | `ro`, `ondelete='set null'` |
| `state` | Selection | `[('draft','Чернетка'),('expected','Очікується'),('on_site','На території'),('left','Вийшов'),('closed','Закрито'),('cancelled','Скасовано')]`, `req`, `default='draft'`, `tracking=True` |
| `arrived_at`, `left_at` | Datetime | `ro`, `string="Прийшов"` / `"Вийшов"` |
| `present` | Boolean | `ro`, `idx` |
| `zone_id` | Many2one `f3d.zone` | `ro`, `idx`, `string="Зона"` |
| `zone_since` | Datetime | `ro` |
| `zone_door_id` | Many2one `f3d.access.door` | `ro` (для R-17) |
| `last_event_id` | Many2one `f3d.access.event` | `ro` |
| `document_checked` | Boolean | `string="Документ перевірено"` (документ не зберігається, Q-06) |
| `overdue` | Boolean | `ro`, `string="Прострочено"` |
| `origin` | Selection | `[('manual','Вручну'),('yard','Двір'),('portal','Портал')]`, `req`, `default='manual'` |
| `origin_ref` | Char(64) | `string="Джерело (посилання)"` (напр. `YV/2026/0012` з `factory3d_yard`) |
| `sync_state` | Selection | як M-06 (`local/pending/synced/error`), `default='local'`, `ro` — створення користувача BioStar |
| `sync_error` | Char(255) | `ro` |
| `event_ids` | One2many `f3d.access.event` `visitor_id` | `ro` |
| `violation_count` | Integer | `compute`: подій із `zone_violation=True` |

`@api.constrains("date_from","date_to","biostar_user_id")`: `date_to <= date_from` →
`ValidationError("Час «До» має бути пізніше за «З».")`; `date_to − date_from > 7 діб` →
`ValidationError("Візит довший за 7 діб оформіть як окремі візити.")`; `biostar_user_id` і не `BSID_RE` → як M-04.

Методи (переходи — §10.4; правила — R-14):

| Сигнатура | Групи | Алгоритм |
|---|---|---|
| `action_expect(self)` | S | `draft` → `expected`; якщо `card_id` порожня — бере першу картку пулу (`holder_type='pool'`, `state in ('draft','returned')`, той самий сервер, `order='number'`); картка: `holder_type='visitor'`, `visitor_id=self`, `action_issue()`; немає вільної — `message_post` «Вільних карток у пулі немає»; користувач BioStar — R-14 крок 2 |
| `action_arrive(self)` | S | вручну: `expected` → `on_site`, `arrived_at=now`, `present=True`, `zone_id` = `zone_to_id` дверей периметра (перші `is_perimeter`), `zone_since=now` |
| `action_leave(self)` | S | `on_site` → `left`, `left_at=now`, `present=False`, `zone_id=False`, `zone_since=False` |
| `action_close(self)` | S | `left`/`expected`/`on_site` → `closed`; `present=False`; картка `action_return()`; користувач BioStar — `link_id.active=False` (запис у BioStar не потрібен: `expiry_datetime` минає сам) |
| `action_cancel(self)` | S | `draft`/`expected` → `cancelled`; картка повертається |
| `unlink(self)` | — | лише `state in ('draft','cancelled')`, інакше `UserError("Видалити можна лише чернетку або скасований візит.")` |
| `@api.model f3d_visitor_register(self, vals) -> record` | CA-07, sudo-безпечний для викликів з інших модулів | `vals` (`name`, `host_employee_id`, `date_from`, `date_to`, `visitor_company`, `purpose`, `origin`, `origin_ref`, `allowed_zone_ids`) → `create(vals)` → `action_expect()` → запис |
| `_f3d_push_user(self)` | — | R-14 крок 2 |
| `@api.model _cron_user_sync(self)` | — | якщо `write_enabled`: відвідувачі `sync_state in ('pending','error')`, `state in ('expected','on_site')`, `limit=100` → `_f3d_push_user()` |
| `_compute_display_name` | — | `"%s (%s)" % (name, visitor_company)` або `name` |

### M-08 `hr.employee` — розширення (CA-01, FR-08)

`_inherit = "hr.employee"`. Поля зберігаються в `hr_employee` (не в `hr.version`). Відмінність від стандарту:
`last_check_in`/`last_check_out`/`attendance_state` описують **відмітку** (може бути ручною, кіоском, авто-виходом),
поля нижче — **фізичний прохід** через СКУД (зокрема внутрішні двері й проходи без відмітки, R-04/R-05).

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_access_present` | Boolean | `ro`, `idx`, `default=False`, `string="На території"` |
| `f3d_access_zone_id` | Many2one `f3d.zone` | `ro`, `idx`, `ondelete='set null'`, `string="Зона зараз"` (ефективна, R-08) |
| `f3d_access_zone_since` | Datetime | `ro`, `string="У зоні з"` |
| `f3d_access_last_in` | Datetime | `ro`, `string="Останній вхід (СКУД)"` |
| `f3d_access_last_out` | Datetime | `ro`, `string="Останній вихід (СКУД)"` |
| `f3d_home_zone_id` | Many2one `f3d.zone` | `ondelete='set null'`, `tracking=True`, `string="Домашня зона"`, `help="Зона робочого місця: сюди людину ставить вхід через периметр і повернення з технічних приміщень (A-15)"` |
| `f3d_access_zone_door_id` | Many2one `f3d.access.door` | `ro`, `ondelete='set null'`, `groups="hr.group_hr_user"` — двері, через які увійшов у поточну зону (R-17) |
| `f3d_access_last_event_id` | Many2one `f3d.access.event` | `ro`, `ondelete='set null'`, `groups="factory3d_access.group_f3d_access_security"` |
| `f3d_access_card_ids` | One2many `f3d.access.card` `employee_id` | `groups="factory3d_access.group_f3d_access_security"`, `string="Картки"` |
| `f3d_access_link_ids` | One2many `f3d.access.user.link` `employee_id` | `groups="factory3d_access.group_f3d_access_security"`, `string="Користувачі BioStar"` |

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `_f3d_access_set(self, vals, event=None)` | sudo `write(vals)`; якщо змінилися `f3d_access_present`/`f3d_access_zone_id` → `_f3d_bus('hr.employee', self.mapped('f3d_code'))` (R-12 крок 6) |
| `@api.model _f3d_access_public_presence(self, codes=None) -> dict` | для провайдера (A-21): `self.sudo().search_read([('f3d_code','!=',False),('active','=',True)] + ([('f3d_code','in',list(codes))] if codes else []), ['f3d_code','f3d_access_present','f3d_access_zone_id','f3d_access_zone_since','f3d_access_last_event_id'])` і `sudo().read` подій → `{code: {'present': bool, 'zone': 'Z-CUT'\|None, 'zone_since': datetime\|None, 'last_event': {'ts', 'door', 'direction', 'type'}\|None}}` (без `raw_user_id`, імен і карток) |
| `action_f3d_access_events(self)` | `groups=S`: журнал подій працівника |

Вкладка «Доступ» (V-10) — лише для тих, хто читає `hr.employee` (`hr.group_hr_user`); охорона бачить людей у
M-14.

#### M-08a `hr.employee.public` — дзеркало (A-17)

`_inherit = "hr.employee.public"`; поля з тими самими іменами, `readonly=True`, без `compute`
(SQL-представлення стандарту бере колонки `e.<name>` з `hr_employee`, `hr/models/hr_employee_public.py:_get_fields`):
`f3d_access_present` (Boolean), `f3d_access_zone_id` (Many2one `f3d.zone`), `f3d_access_zone_since`,
`f3d_access_last_in`, `f3d_access_last_out` (Datetime), `f3d_home_zone_id` (Many2one `f3d.zone`). Інші поля M-08
у публічний профіль не потрапляють. У `models/hr_employee.py` клас розширення `hr.employee` оголошується **перед**
класом `hr.employee.public`: `Registry.init_models` виконує `_auto_init()` і `init()` по моделях у порядку оголошення,
тож колонки `hr_employee.f3d_access_*` мають існувати до перебудови представлення `hr_employee_public`.

### M-09 `hr.attendance` — розширення (CA-06, FR-07)

```python
class HrAttendance(models.Model):
    _inherit = "hr.attendance"
    in_mode = fields.Selection(selection_add=[("biostar", "СКУД BioStar 2")], ondelete={"biostar": "set default"})
    out_mode = fields.Selection(selection_add=[("biostar", "СКУД BioStar 2")], ondelete={"biostar": "set default"})
```

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_in_event_id` | Many2one `f3d.access.event` | `ro`, `ondelete='set null'`, `string="Подія входу"`, `groups="factory3d_access.group_f3d_access_security,hr_attendance.group_hr_attendance_user"` |
| `f3d_out_event_id` | Many2one `f3d.access.event` | те саме, `string="Подія виходу"` |
| `f3d_in_device_id` | Many2one `f3d.access.device` | `ro`, `ondelete='set null'`, `string="Пристрій входу"`, ті самі `groups` |
| `f3d_out_device_id` | Many2one `f3d.access.device` | те саме, `string="Пристрій виходу"` |
| `f3d_closed_by_rule` | Boolean | `ro`, `default=False`, `idx`, `string="Закрито правилом (без виходу)"` (R-07) |

Стандартні методи не перевизначаються; відмітки створює/змінює лише обробка подій (sudo), тож стандартні
обмеження `_check_validity` і `_check_validity_check_in_check_out` діють і для СКУД (їхні `ValidationError` →
`process_state='error'` події, §11).

### M-10 `f3d.zone` — розширення (CA-02)

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_people_now` | Integer | `compute="_compute_f3d_people"` (не зберігається), `string="Людей зараз"`: `read_group` (sudo) `hr.employee` `[('f3d_access_present','=',True),('f3d_access_zone_id','in',ids)]` за `f3d_access_zone_id` + `f3d.access.visitor` `[('present','=',True),('zone_id','in',ids)]` за `zone_id` |
| `f3d_people_employee_ids` | Many2many `hr.employee` | `compute` (sudo), не зберігається — для API інших модулів (fire_safety); у представленнях не виводиться |
| `f3d_people_visitor_ids` | Many2many `f3d.access.visitor` | `compute` (sudo), не зберігається |

Метод `action_view_people(self)` → `ir.actions.act_window` на `f3d.access.presence` (`views` kanban, list;
`domain=[('zone_id','=',self.id)]`, `name="Люди: %s" % name`).

### M-11 `res.config.settings` — розширення (FR-16)

Усі поля — `groups="factory3d_base.group_f3d_admin"`, `config_parameter` = ключ §5.1. Булеві зберігаються
стандартом як `True`/відсутній параметр; читання — `get_flag` (відсутній = `False`).

| Поле | Тип | `config_parameter` | Обмеження |
|---|---|---|---|
| `f3d_access_read_enabled` | Boolean | `factory3d.access.read_enabled` | — |
| `f3d_access_write_enabled` | Boolean | `factory3d.access.write_enabled` | — |
| `f3d_access_biostar_login` | Char | `factory3d.access.biostar_login` | — |
| `f3d_access_biostar_password` | Char | `factory3d.access.biostar_password` | у формі `password="True"` |
| `f3d_access_page_size` | Integer | `factory3d.access.page_size` | 1–2000 |
| `f3d_access_max_pages_per_run` | Integer | `factory3d.access.max_pages_per_run` | 1–100 |
| `f3d_access_overlap_s` | Integer | `factory3d.access.overlap_s` | 0–3600 |
| `f3d_access_initial_lookback_h` | Integer | `factory3d.access.initial_lookback_h` | 1–168 |
| `f3d_access_paging_mode` | Selection `[('offset','offset'),('hint','hint (BioStar 2.8+)')]` | `factory3d.access.paging_mode` | — |
| `f3d_access_dup_window_min` | Integer | `factory3d.access.dup_window_min` | 0–120 |
| `f3d_access_merge_gap_min` | Integer | `factory3d.access.merge_gap_min` | 0–240 |
| `f3d_access_max_shift_h` | Integer | `factory3d.access.max_shift_h` | 1–24 |
| `f3d_access_stale_close_enabled` | Boolean | `factory3d.access.stale_close_enabled` | — |
| `f3d_access_stale_close_fallback_min` | Integer | `factory3d.access.stale_close_fallback_min` | 1–720 |
| `f3d_access_keep_days` | Integer | `factory3d.access.keep_days` | 1–3650 |
| `f3d_access_keep_raw` | Boolean | `factory3d.access.keep_raw` | — |
| `f3d_access_publish_signals` | Boolean | `factory3d.access.publish_signals` | — |
| `f3d_access_visitor_default_hours` | Integer | `factory3d.access.visitor_default_hours` | 1–72 |
| `f3d_access_visitor_user_prefix` | Char | `factory3d.access.visitor_user_prefix` | `^[A-Za-z0-9_\-]{1,8}$` |
| `f3d_access_visitor_user_group_id` | Char | `factory3d.access.visitor_user_group_id` | `^[0-9]{1,9}$` |
| `f3d_access_server_count` | Integer | — | `compute`: кількість серверів (кнопка «Сервери BioStar») |

Перевірка діапазонів — у `set_values` до `super()`: порушення → `ValidationError("%(label)s: допустимо %(lo)s–%(hi)s.")`.
Кнопки блоку: «Сервери BioStar» (`action_f3d_access_server`), «Перевірити з'єднання» (`action_f3d_access_test` →
`server.action_test_connection()` першого активного сервера).

### M-12 `f3d.viewer.provider.access` — провайдер переглядача (CA-05, FR-14, A-19)

```python
class F3dViewerProviderAccess(models.AbstractModel):
    _name = "f3d.viewer.provider.access"       # БЕЗ _inherit: factory3d_viewer не є залежністю (A-19)
    _description = "3D: СКУД — люди, двері, зчитувачі"
    _f3d_sequence = 170
    _f3d_sections = ("access",)
    _f3d_group = "factory3d_base.group_f3d_user"
```

Переглядач (viewer R-01 крок 3) знаходить провайдери за префіксом імені в реєстрі й викликає атрибути й методи
нижче (duck typing, той самий інтерфейс, що viewer M-01). Без `factory3d_viewer` модель просто ніхто не викликає.

| Метод | Алгоритм |
|---|---|
| `_f3d_viewer_collect(self, payload, ctx)` | R-12 кроки 1–5 |
| `_f3d_viewer_delta(self, patch, ctx)` | R-12 п. 7 (X-23, X-87): немає змін моделей `_f3d_viewer_bus_models()` у `ctx["changes"]` → нічого; інакше `tmp` із заготовками ключів CA-05 (змінені коди `hr.employee`, усі активні зони, картки `infra.cards.TURNSTILES`/`ACCESS`) → `self._f3d_viewer_collect(tmp, ctx)`; `patch["access"] = tmp["access"]` (власний розділ — цілком); `employees`, `zones`, `infra` — лише `deep_merge(patch.setdefault(k, {}), tmp[k])` (хелпер viewer M-01, імпорт усередині методу); присвоєння `patch["infra"]`/`patch["employees"]`/`patch["zones"] = …` заборонене |
| `_f3d_viewer_bus_models(self)` | `["hr.employee", "f3d.access.door", "f3d.access.visitor"]` |

### M-13 `f3d.access.event.reprocess.wizard` — повторна обробка й опитування періоду (FR-19)

`TransientModel`, `_description = "СКУД: повторна обробка подій"`.

| Поле | Тип | Параметри |
|---|---|---|
| `mode` | Selection | `[('reprocess','Обробити події повторно'),('repoll','Опитати BioStar за період')]`, `req`, `default='reprocess'` |
| `server_id` | Many2one `f3d.access.server` | `req`, `default` — перший активний |
| `date_from`, `date_to` | Datetime | `req`; `default` `now − 24 год`, `now` |
| `only_errors` | Boolean | `default=True`, `string="Лише нові й з помилками"` |
| `result` | Text | `ro` |

`@api.constrains`: `date_to <= date_from` → `ValidationError("Кінець періоду має бути пізніше за початок.")`;
`date_to − date_from > 7 діб` → `ValidationError("Період — не довше 7 діб.")`.
`action_run(self)` (`groups=A`): `reprocess` → події сервера у `[date_from, date_to]` (з `only_errors` —
`process_state in ('new','error')`) → `action_reprocess()`; `repoll` → потрібен `read_enabled` (інакше
`UserError` як M-01), `server._poll_window(date_from, date_to, max_pages=100)`; `result` = лічильники; повертає
ту саму форму (`target='new'`).

### M-14 `f3d.access.presence` — люди по зонах, SQL-представлення (FR-08, FR-12, A-17)

```python
class F3dAccessPresence(models.Model):
    _name = "f3d.access.presence"
    _description = "СКУД: люди на території"
    _auto = False
    _order = "zone_id, name"
```

| Поле | Тип | Джерело |
|---|---|---|
| `id` | — | працівник: `e.id * 2`; відвідувач: `v.id * 2 + 1` |
| `person_type` | Selection `[('employee','Працівник'),('visitor','Відвідувач')]` | константа гілки |
| `employee_id` | Many2one `hr.employee` | `e.id` / `NULL` |
| `visitor_id` | Many2one `f3d.access.visitor` | `NULL` / `v.id` |
| `name` | Char | `e.name` / `v.name` |
| `code` | Char | `e.f3d_code` / `'V-' \|\| v.id` |
| `zone_id` | Many2one `f3d.zone` | `e.f3d_access_zone_id` / `v.zone_id` |
| `zone_since` | Datetime | `e.f3d_access_zone_since` / `v.zone_since` |
| `last_in` | Datetime | `e.f3d_access_last_in` / `v.arrived_at` |
| `home_zone_id` | Many2one `f3d.zone` | `e.f3d_home_zone_id` / `NULL` |
| `host_employee_id` | Many2one `hr.employee` | `NULL` / `v.host_employee_id` |
| `company_id` | Many2one `res.company` | `e.company_id` / `v.company_id` |

```sql
CREATE OR REPLACE VIEW f3d_access_presence AS (
  SELECT e.id * 2 AS id, 'employee' AS person_type, e.id AS employee_id, NULL::int AS visitor_id,
         e.name AS name, e.f3d_code AS code, e.f3d_access_zone_id AS zone_id,
         e.f3d_access_zone_since AS zone_since, e.f3d_access_last_in AS last_in,
         e.f3d_home_zone_id AS home_zone_id, NULL::int AS host_employee_id, e.company_id AS company_id
    FROM hr_employee e WHERE e.active AND e.f3d_access_present
  UNION ALL
  SELECT v.id * 2 + 1, 'visitor', NULL::int, v.id, v.name, 'V-' || v.id, v.zone_id, v.zone_since, v.arrived_at,
         NULL::int, v.host_employee_id, v.company_id
    FROM f3d_access_visitor v WHERE v.present AND v.state = 'on_site'
)
```

`init()` — `tools.drop_view_if_exists` + `CREATE OR REPLACE VIEW` (як стандартні звіти); `models/__init__.py` імпортує
`f3d_access_presence` після `f3d_access_visitor` і `hr_employee` (колонки мають існувати). Методи:
`action_f3d_show(self)` — працівник з кодом: `employee_id.sudo().action_f3d_show()` (дія містить лише код);
відвідувач або без коду — `zone_id.action_f3d_show()`; `action_open_person(self)` — форма відвідувача (S) або
працівника (`hr.employee`, лише якщо `self.env['hr.employee'].has_access('read')`, інакше `hr.employee.public`).

### M-15 `f3d.access.telemetry` — міст до `factory3d_telemetry` (FR-15)

`AbstractModel`, `_description = "СКУД: публікація сигналів телеметрії"`. Методи:
`@api.model _f3d_signal_model(self)` → `self.env['f3d.signal'].sudo()`, якщо `'f3d.signal' in self.env`, інакше `None`
(окремий метод — тести підставляють фейкову модель); `@api.model _f3d_publish(self, server, events) -> dict | None` —
R-18; `_f3d_signal_model()` повертає `None` → `None`. Сигнали, у які пише R-18, створює міст `factory3d_access_telemetry`
(M-17, X-33); сам `factory3d_access` від telemetry не залежить.

### M-16 `f3d.fire.passage.source.access` — джерело проходів для навчальної тривоги (CA-09, A-24)

```python
class F3dFirePassageSourceAccess(models.AbstractModel):
    _name = "f3d.fire.passage.source.access"   # БЕЗ _inherit: factory3d_fire_safety не є залежністю
    _description = "СКУД: проходи для навчальної тривоги"
    _f3d_priority = 10
```

| Метод | Вихід | Алгоритм |
|---|---|---|
| `_f3d_on_site(self, at)` | `list[dict(employee_id: int, since: datetime, point: str)]` | `res = env['f3d.access.event'].f3d_on_site_at(at)`; для кожного працівника: `since` = його останній вхід периметра ≤ `at`, `point` = `door_id.code` цього входу |
| `_f3d_passages(self, start, end)` | `list[dict(employee_id, ts, point, direction)]` | `f3d_passes_between(start, end, door_codes=None)` з `is_perimeter=True`, лише `employee_id`; `point = door_id.code` |
| `_f3d_drill_active(self, ts)` | `bool` | делегує `f3d.access.event._f3d_drill_active(ts)` |

`factory3d_fire_safety` (CF-02) обирає джерело з найменшим `_f3d_priority` серед моделей реєстру з префіксом
`f3d.fire.passage.source.` (Q-13).

### M-17 Міст `factory3d_access_telemetry` — 7 сигналів СКУД (FR-15, X-33)

Модуль-місток (§0, §1: `auto_install=True`, `depends=["factory3d_access", "factory3d_telemetry"]`) за зразком
`factory3d_telemetry_viewer` (каркас §3). Нових моделей немає; файл `models/f3d_access_telemetry.py` розширює дві моделі:

```python
class F3dAccessTelemetry(models.AbstractModel):
    _inherit = "f3d.access.telemetry"

class F3dAccessDevice(models.Model):
    _inherit = "f3d.access.device"
```

Сигнали (коди = iot_sim Додаток A 647–653; на демо — 7):

| Код | `name` | `kind` | `unit` | `equipment_id` |
|---|---|---|---|---|
| `access/readers/<код пристрою>/last_event` — по одному на кожен `f3d.access.device` з кодом за R-01 (демо: `ACR-IN`, `ACR-ELEC`, `ACR-CHG`, `ACR-PAINT`, `ACR-SRV` — рядки 647–651) | `СКУД: остання подія <код>` | `event` | — | `device.equipment_id` (`TURNSTILES` для `ACR-IN`, `ACCESS` для решти — §5.3 крок 3) |
| `access/turnstiles/TURNSTILES/on_site` (652) | `СКУД: на території зараз` | `gauge` | `осіб` | `maintenance.equipment.search_f3d('TURNSTILES')` (порожньо → без обладнання) |
| `access/events` (653) | `СКУД: нові події за опитування` | `event` | — | `maintenance.equipment.search_f3d('ACCESS')` |

Спільні значення всіх сигналів моста: `module='access'` (telemetry CT-09), `origin='module'` (сигнал модуля з власних
даних, не імпорт каталогу — telemetry M-03, X-16), `source_id=False` і `address={}` (без джерела: не потрапляє в
API-01 колектора, крон `stale` telemetry R-07 його не чіпає — показання лише через CT-10 `_f3d_ingest(src='module')`),
`period_s=60` (крон опитування), `store_period_s=0` (кожне показання; ≤ 1 на опитування), `create_request=False`
(порогів немає), `viewer_visible=False` (розділ `access` переглядача — власний розділ провайдера M-12, провайдер
telemetry R-12 його не дублює), `active=True`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `@api.model _f3d_ensure_signals(self, devices=None) -> dict` | `S = env['f3d.signal'].sudo().with_context(active_test=False)`; `devices = devices or env['f3d.access.device'].sudo().search([])`; рядки = по пристрою з кодом, що проходить `CODE_RE` (R-01), + 2 фіксовані (таблиця вище); для кожного: `S.search([('code','=',code)], limit=1)` знайдено → пропуск (наявний сигнал — архівний або створений інакше, напр. імпортом каталогу telemetry CT-11 — не змінюється); інакше `S.create(vals)`; INFO «Сигнали СКУД: створено %d, наявних %d»; повертає `{'created': n, 'existing': m}` |
| `f3d.access.device.create(self, vals_list)` (`@api.model_create_multi`) | `records = super().create(vals_list)`; `env['f3d.access.telemetry']._f3d_ensure_signals(records)` (новий пристрій із R-19 `BS-<id>` отримує свій сигнал); повертає `records` |
| `f3d.access.device.write(self, vals)` | `res = super().write(vals)`; `'code' in vals` → `_f3d_ensure_signals(self)` (сигнал старого коду лишається з історією показань); повертає `res` |

Деінсталяція моста: `uninstall_hook` немає — сигнали й показання лишаються як історія telemetry (вони не дані
модуля, стандартна деінсталяція їх не видаляє); R-18 без моста продовжує публікувати в наявні сигнали.

## 3. Представлення й меню

Спільне: усі дії — `ir.actions.act_window` з XML-id `factory3d_access.action_<…>`, оголошені у файлі представлень
своєї моделі; кнопки об'єктів — `type="object"`; кнопки з `groups` приховані для інших. Кнопка «Показати в 3D» —
`icon="fa-cube"`, `class="btn-secondary"`.

| ID | XML-id | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `view_f3d_access_server_form`, `view_f3d_access_server_list` | form/list `f3d.access.server` | form `<header>`: `action_test_connection` «Перевірити з'єднання» (F), `action_poll_now` «Опитати зараз» (A), `action_sync_users` «Синхронізувати користувачів» (A), `action_sync_devices` «Синхронізувати пристрої й двері» (A), `action_reset_cursor` «Скинути курсор» (F, `confirm="Наступне опитування почнеться за initial_lookback_h. Продовжити?"`); `state` widget `statusbar` (`statusbar_visible="offline,online,error"`). Статбокс: `action_open_events` (`event_count`, «Події»), `action_open_errors` (`error_event_count`, «Помилки»), `action_open_links` (`link_count`, «Користувачі»; під ним `unlinked_count` «не зв'язано»). Попередження `<div class="alert alert-warning" invisible="not stale">Немає контакту з BioStar довше трьох інтервалів опитування.</div>`, `<div class="alert alert-danger" invisible="state != 'error'"><field name="last_error"/></div>`, `<div class="alert alert-info" invisible="not doors_without_zone">Двері без зон: <field name="doors_without_zone"/> — проходи через них не змінюють зону людей.</div>`. Група «Підключення»: `name`, `url`, `verify_ssl`, `timeout_connect_s`, `timeout_read_s`, `company_id` (multi-company), `active`. Група «Стан» (readonly): `last_contact`, `error_count`, `next_try_at`, `last_error_ts`, `users_total`, `devices_total`, `users_synced_at`, `devices_synced_at`. Група «Опитування»: `last_event_ts`, `last_event_biostar_id`, `last_poll_at`, `last_poll_rows`, `last_poll_new`, `last_poll_more`. Вкладки «Пристрої» (`device_ids` list readonly: `code`, `name`, `biostar_id`, `status`, `zone_id`), «Двері» (`door_ids`: `code`, `name`, `state`, `is_perimeter`). Поле `session_id` не виводиться. List: `name`, `url`, `state` (badge: `decoration-success="state=='online'"`, `decoration-danger="state=='error'"`), `last_contact`, `last_poll_new`, `error_count` |
| V-02 | `view_f3d_access_device_list`, `_form`, `_search` | `f3d.access.device` | list (editable для A): `code`, `name`, `biostar_id`, `device_type`, `direction`, `zone_id`, `equipment_id`, `status` (badge), `last_event_ts`, `events_today`; form: заголовок `name`; кнопки «Показати в 3D» (`action_f3d_show`), «Події» (`action_open_events`); групи «Ідентифікація» (`code`, `biostar_id`, `server_id`, `device_type`, `ip`), «Сцена» (`equipment_id`, `zone_id`, `x`, `y`, `direction`), «Стан» (`status`, `status_ts`, `sync_fail_count`, `last_event_ts`, `last_event_code`); `note`. Search: `code`, `name`, `biostar_id`; фільтри «Не в мережі» (`status='offline'`), «Без зони» (`zone_id=False`); group by `status`, `zone_id` |
| V-03 | `view_f3d_access_door_list`, `_form`, `_search`, `_kanban` | `f3d.access.door` | list: `code`, `name`, `kind`, `zone_from_id`, `zone_to_id`, `is_perimeter`, `dwell_min`, `state` (badge, `decoration-danger="alarm"`), `state_ts`, `passes_today`; `decoration-danger="alarm"`. Kanban (вид за замовчуванням для S): картка — `code`, `name`, стан кольором (`open/unlocked` жовтий, `forced/held` червоний, решта сірий), `passes_today`. Form: кнопки «Показати в 3D», «Події», «Зняти тривогу» (`action_ack_alarm`, S, `invisible="not alarm"`); групи «Двері» (`code`, `name`, `kind`, `biostar_id`, `server_id`, `open_duration_s`), «Граф зон» (`zone_from_id`, `zone_to_id`, `is_perimeter`, `dwell_min`), «Зчитувачі» (`entry_device_id`, `exit_device_id`), «Стан» (`state`, `state_ts`, `alarm`, `alarm_reason`). Search: фільтри «Тривога» (`alarm=True`), «Периметр», «Без зон» (`zone_to_id=False`) |
| V-04 | `view_f3d_access_user_link_list`, `_form`, `_search` | `f3d.access.user.link` | list: `biostar_user_id`, `biostar_name`, `employee_id`, `visitor_id`, `match` (badge, `decoration-warning="match=='none'"`), `user_group`, `disabled`, `card_count`, `has_face`, `in_biostar`, `last_sync`; `decoration-muted="not in_biostar"`. Form: кнопки «Підібрати працівника» (`action_rematch`, A), «Події»; поля як у списку, `employee_id`/`visitor_id` редагуються (A). Search: фільтри «Не зв'язано» (`match='none'`, за замовчуванням у меню), «Немає в BioStar» (`in_biostar=False`), «Вимкнено» (`disabled=True`), «Відвідувачі» (`visitor_id!=False`); group by `match` |
| V-05 | `view_f3d_access_event_list`, `_form`, `_search`, `_pivot`, `_graph` | `f3d.access.event` (журнал, без `create`/`edit`/`delete` у UI: `create="0" edit="0" delete="0"`) | list: `ts`, `door_id`, `device_id`, `direction`, `event_type` (badge: `pass` зелений, `denied/fail` червоний, `door` сірий, `alarm` помаранчевий), `code`, `code_name` (optional show), `credential` (optional hide), `employee_id`, `visitor_id`, `raw_user_id` (optional hide), `deny_reason` (optional show), `attendance_action` (optional show), `apb_suspect` (widget boolean, optional show), `process_state` (optional hide); `decoration-danger="event_type in ('denied','fail') or process_state=='error'"`, `decoration-warning="apb_suspect or zone_violation"`. Form (readonly): кнопка «Обробити повторно» (`action_reprocess`, A); групи «Подія» (`ts`, `server_ts`, `received_at`, `biostar_id`, `code`, `code_name`, `event_type`, `credential`, `deny_reason`, `tna_key`, `direction`), «Де» (`device_id`, `door_id`, `is_perimeter`, `zone_from_id`, `zone_to_id`), «Хто» (`raw_user_id`, `link_id`, `employee_id`, `visitor_id`, `unknown_user`), «Результат» (`process_state`, `attendance_action`, `attendance_id`, `presence_changed`, `apb_suspect`, `zone_violation`, `error_message`), `raw` (F, widget `ace` json, `invisible="not raw"`). Search: поля `employee_id`, `visitor_id`, `raw_user_id`, `door_id`, `device_id`, `code`; фільтри §2 M-05 + «Проходи» (`event_type='pass'`), «Вхід», «Вихід»; дата `ts`; group by `door_id`, `event_type`, `employee_id`, `ts:day`. Pivot: рядки `employee_id`, колонки `ts:day`, міра `__count`. Graph: bar `ts:hour` × `event_type` |
| V-06 | `action_f3d_access_event_report` | дія «Проходи СКУД» на `f3d.access.event` | `views` list, pivot, graph; `domain=[('event_type','=','pass'),('is_perimeter','=',True)]`, `context={'search_default_today': 1, 'search_default_group_employee': 1}` |
| V-07 | `view_f3d_access_card_list`, `_form`, `_search` | `f3d.access.card` | list: `number`, `card_type`, `holder_type`, `holder_name`, `state` (badge), `sync_state` (badge: `synced` зелений, `pending` синій, `error` червоний, `local` сірий), `issued_at`; form `<header>`: `action_issue` «Видати» (`invisible="state not in ('draft','returned')"`), `action_block` «Заблокувати» (A, `invisible="state != 'active'"`), `action_unblock` «Розблокувати» (A), `action_return` «Повернути», `action_mark_lost` «Втрачена» (A), `action_retry_sync` «Повторити запис у BioStar» (A, `invisible="sync_state not in ('error','local') or not pending_op"`), `action_mark_synced` «Позначити синхронізованим» (A, `invisible="sync_state not in ('local','error') or not pending_op"`); `state` statusbar (`draft,active,blocked,returned`). Попередження `<div class="alert alert-warning" invisible="sync_state != 'local' or not pending_op">Запис у BioStar вимкнено стоп-краном. Виконайте операцію в BioStar вручну і натисніть «Позначити синхронізованим».</div>`, `<div class="alert alert-danger" invisible="sync_state != 'error'"><field name="sync_error"/></div>`. Групи: `number`, `card_type`, `server_id`, `holder_type`, `employee_id` (`invisible="holder_type != 'employee'"`), `visitor_id` (`invisible="holder_type != 'visitor'"`), `block_reason`, `issued_at`, `blocked_at`, `returned_at`, `biostar_card_id`, `pending_op`, `sync_ts`, `sync_attempts`; чаттер. Search: фільтри за `state`, «Пул вільних» (`holder_type='pool'` і `state in (draft, returned)`), «Помилки запису» (`sync_state='error'`), «Не записано в BioStar» (`sync_state='local'` і `pending_op != False`) |
| V-08 | `view_f3d_access_visitor_list`, `_form`, `_search`, `_calendar` | `f3d.access.visitor` | list: `name`, `visitor_company`, `host_employee_id`, `date_from`, `date_to`, `state` (badge), `card_id`, `zone_id`, `overdue` (boolean), `violation_count`; `decoration-danger="overdue or violation_count"`. Form `<header>`: «Очікується» (`action_expect`, draft), «Прийшов» (`action_arrive`, expected), «Вийшов» (`action_leave`, on_site), «Закрити» (`action_close`), «Скасувати» (`action_cancel`); statusbar `draft,expected,on_site,left,closed`. Групи «Візит» (`name`, `visitor_company`, `host_employee_id`, `purpose`, `date_from`, `date_to`, `allowed_zone_ids` tags, `document_checked`, `origin`, `origin_ref`), «Доступ» (`card_id`, `server_id`, `biostar_user_id`, `link_id`, `sync_state`, `sync_error`), «Зараз» (readonly: `present`, `zone_id`, `zone_since`, `arrived_at`, `left_at`, `overdue`); вкладка «Події» (`event_ids` list readonly: `ts`, `door_id`, `direction`, `event_type`, `zone_violation`); чаттер. Calendar: `date_start="date_from"`, `date_stop="date_to"`, колір `state`. Search: фільтри «Сьогодні», «На території», «Очікуються», «Прострочені», «Порушення зон» |
| V-09 | `view_f3d_access_presence_kanban`, `_list`, `_search` | `f3d.access.presence` (`create="0" edit="0" delete="0"`) | kanban `default_group_by="zone_id"`, `group_create="0"`, `group_delete="0"`, `group_edit="0"`, `records_draggable="0"`; лічильник у заголовку колонки — стандартний `count`; картка: `name`, `code`, бейдж «Відвідувач» (`person_type=='visitor'`), «У зоні з» `zone_since` (формат часу), «Вхід» `last_in`, домашня зона (якщо ≠ `zone_id`, сірим); кнопки «Показати в 3D» (`action_f3d_show`), «Відкрити» (`action_open_person`). List: `name`, `code`, `person_type`, `zone_id`, `zone_since`, `last_in`, `home_zone_id`, `host_employee_id`. Search: `name`, `code`, `zone_id`; фільтри «Працівники», «Відвідувачі», «Без домашньої зони» (`person_type='employee'` і `home_zone_id=False`); group by `zone_id`, `person_type` |
| V-10 | `view_hr_employee_form_f3d_access`, `view_hr_employee_list_f3d_access`, `view_hr_employee_search_f3d_access` | inherit `hr.view_employee_form`, `hr.view_employee_tree`, `hr.view_employee_filter` | form: `xpath //notebook position="inside"` → `<page name="f3d_access" string="Доступ">`: група «Зараз» (`f3d_access_present`, `f3d_access_zone_id`, `f3d_access_zone_since`, `f3d_home_zone_id` — редагує `hr.group_hr_user`), група «Проходи» (`f3d_access_last_in`, `f3d_access_last_out`, `f3d_access_last_event_id` (S)), `f3d_access_link_ids` (S, list readonly: `biostar_user_id`, `match`, `card_count`, `has_face`), `f3d_access_card_ids` (S, list: `number`, `state`, `sync_state`); кнопка в `div[@name='button_box']` «Проходи» (`action_f3d_access_events`, S, icon `fa-id-card-o`). list: після `name` `f3d_access_present` (optional hide, widget `boolean`), `f3d_access_zone_id` (optional hide). search: фільтри «На території» (`f3d_access_present=True`), «Без домашньої зони» (`f3d_home_zone_id=False`); group by `f3d_access_zone_id` |
| V-11 | `view_hr_attendance_form_f3d`, `view_hr_attendance_list_f3d`, `view_hr_attendance_search_f3d` | inherit `hr_attendance.hr_attendance_view_form`, `view_attendance_tree`, `hr_attendance_view_filter` | form: після `//field[@name='check_out']` група «СКУД» (`invisible="in_mode != 'biostar' and out_mode != 'biostar' and not f3d_closed_by_rule"`): `f3d_in_event_id`, `f3d_in_device_id`, `f3d_out_event_id`, `f3d_out_device_id`, `f3d_closed_by_rule`; list: після `out_mode` `f3d_in_device_id` (optional hide), `f3d_closed_by_rule` (optional show); search: фільтри «СКУД BioStar 2» (`in_mode='biostar'`), «Закриті за правилом» (`f3d_closed_by_rule=True`); `in_mode` уже є в групуванні «Method» стандарту |
| V-12 | `view_f3d_zone_form_f3d_access`, `view_f3d_zone_kanban_f3d_access` | inherit `factory3d_base.view_f3d_zone_form`, `view_f3d_zone_kanban` | form: stat-кнопка `action_view_people` (`f3d_people_now`, «Людей зараз», icon `fa-users`, groups S) у `div[@name='button_box']`; kanban: рядок «Людей зараз: N» (`f3d_people_now`), якщо N > 0 |
| V-13 | `res_config_settings_view_form_f3d_access` | inherit `hr_attendance.res_config_settings_view_form` | `xpath //app[@name='hr_attendance'] position="inside"` → `<block title="СКУД Suprema BioStar 2" name="f3d_access_block" groups="factory3d_base.group_f3d_admin">`: settings «Приймати події» (`f3d_access_read_enabled`, help «Стоп-кран: опитування BioStar кронами й кнопками»), «Запис у BioStar» (`f3d_access_write_enabled`, help «Стоп-кран: картки й користувачі-відвідувачі»), «Обліковий запис» (`f3d_access_biostar_login`, `f3d_access_biostar_password` `password="True"`), «Опитування» (`page_size`, `max_pages_per_run`, `overlap_s`, `initial_lookback_h`, `paging_mode`), «Правила відміток» (`dup_window_min`, `merge_gap_min`, `max_shift_h`, `stale_close_enabled`, `stale_close_fallback_min`), «Дані» (`keep_days`, `keep_raw`, `publish_signals`), «Відвідувачі» (`visitor_default_hours`, `visitor_user_prefix`, `visitor_user_group_id`); кнопки «Сервери BioStar», «Перевірити з'єднання» |
| V-14 | `view_f3d_access_event_reprocess_wizard_form` | form `f3d.access.event.reprocess.wizard` | `mode` (radio), `server_id`, `date_from`, `date_to`, `only_errors` (`invisible="mode != 'reprocess'"`), `result` (readonly, `invisible="not result"`); footer: «Виконати» (`action_run`, `btn-primary`), «Закрити» (`special="cancel"`). Дія `action_f3d_access_reprocess_wizard` (`target='new'`) |
| V-15 | `views/menus.xml` | `ir.ui.menu` | таблиця нижче |

Дії (`res_model`, `view_mode`, `domain`, `context`):

| XML-id | Модель | `view_mode` | `domain` / `context` |
|---|---|---|---|
| `action_f3d_access_presence` | `f3d.access.presence` | kanban,list | `context={'search_default_group_zone': 1}` (kanban і так групує за `zone_id`) |
| `action_f3d_access_event` | `f3d.access.event` | list,form,pivot,graph | `context={'search_default_today': 1}` |
| `action_f3d_access_event_report` | V-06 | list,pivot,graph | V-06 |
| `action_f3d_access_visitor` | `f3d.access.visitor` | list,calendar,form | `context={'search_default_today': 1}` |
| `action_f3d_access_door` | `f3d.access.door` | kanban,list,form | — |
| `action_f3d_access_device` | `f3d.access.device` | list,form | — |
| `action_f3d_access_card` | `f3d.access.card` | list,form | — |
| `action_f3d_access_user_link` | `f3d.access.user.link` | list,form | `context={'search_default_unlinked': 1}` |
| `action_f3d_access_server` | `f3d.access.server` | list,form | — |
| `action_f3d_access_reprocess_wizard` | M-13 | form | `target='new'` |
| `action_f3d_access_settings` | `res.config.settings` | form | `target='current'` (`inline` недопустимий в Odoo 19), `context={'module': 'hr_attendance'}` — відкриває налаштування застосунку «Відвідування», де блок V-13 `f3d_access_block` (X-89; шаблон td_genset `action_f3d_genset_settings`); визначена у `views/res_config_settings_views.xml` |

Меню (CB-09: sequence 70 під `factory3d_base.menu_f3d_root` зарезервовано):

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_f3d_access` | Доступ | `factory3d_base.menu_f3d_root` | 70 | S | — |
| `menu_f3d_access_presence` | Люди по зонах | `menu_f3d_access` | 10 | S | `action_f3d_access_presence` |
| `menu_f3d_access_event` | Журнал подій | `menu_f3d_access` | 20 | S | `action_f3d_access_event` |
| `menu_f3d_access_visitor` | Відвідувачі | `menu_f3d_access` | 30 | S | `action_f3d_access_visitor` |
| `menu_f3d_access_door` | Двері | `menu_f3d_access` | 40 | S | `action_f3d_access_door` |
| `menu_f3d_access_device` | Пристрої | `menu_f3d_access` | 50 | S | `action_f3d_access_device` |
| `menu_f3d_access_card` | Картки | `menu_f3d_access` | 60 | S | `action_f3d_access_card` |
| `menu_f3d_access_user_link` | Користувачі BioStar | `menu_f3d_access` | 70 | A | `action_f3d_access_user_link` |
| `menu_f3d_access_reprocess` | Повторна обробка | `menu_f3d_access` | 80 | A | `action_f3d_access_reprocess_wizard` |
| `menu_f3d_access_server` | Сервери BioStar | `menu_f3d_access` | 90 | F | `action_f3d_access_server` |
| `menu_f3d_access_att_report` | Проходи СКУД | `hr_attendance.menu_hr_attendance_reporting` | 20 | H, S | `action_f3d_access_event_report` |
| `menu_f3d_access_att_server` | Сервери BioStar | `hr_attendance.menu_hr_attendance_configuration` | 50 | F | `action_f3d_access_server` |
| `menu_f3d_access_settings` | Налаштування СКУД | `factory3d_base.menu_f3d_config` | 70 (резерв access CB-09; X-32, X-89) | F | `action_f3d_access_settings` |

Блок налаштувань — V-13 (у застосунку «Відвідування», A-16); пункт `menu_f3d_access_settings` лише веде до нього (X-89).

Імена фільтрів пошуку (`<filter name=…>`, на них посилаються дії й тести): V-04 — `unlinked`, `missing`, `disabled`,
`visitors`, `group_match`; V-05 — `today`, `filter_pass`, `filter_in`, `filter_out`, `filter_denied`, `filter_apb`,
`filter_unknown`, `filter_zone_violation`, `filter_errors`, `filter_perimeter`, `group_door`, `group_type`,
`group_employee`, `group_day`; V-07 — `pool_free`, `sync_error`, `sync_local`; V-08 — `today`, `on_site`, `expected`,
`overdue`, `violations`; V-09 — `employees`, `visitors`, `no_home_zone`, `group_zone`, `group_type`; V-10 —
`f3d_present`, `f3d_no_home_zone`, `group_f3d_zone`; V-11 — `f3d_biostar`, `f3d_closed_by_rule`.

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_f3d_access_server_admin,f3d.access.server access admin,model_f3d_access_server,group_f3d_access_admin,1,0,0,0
access_f3d_access_server_f3d_admin,f3d.access.server f3d admin,model_f3d_access_server,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_access_device_user,f3d.access.device user,model_f3d_access_device,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_access_device_admin,f3d.access.device admin,model_f3d_access_device,group_f3d_access_admin,1,1,1,1
access_f3d_access_door_user,f3d.access.door user,model_f3d_access_door,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_access_door_security,f3d.access.door security,model_f3d_access_door,group_f3d_access_security,1,1,0,0
access_f3d_access_door_admin,f3d.access.door admin,model_f3d_access_door,group_f3d_access_admin,1,1,1,1
access_f3d_access_user_link_security,f3d.access.user.link security,model_f3d_access_user_link,group_f3d_access_security,1,0,0,0
access_f3d_access_user_link_hr,f3d.access.user.link hr,model_f3d_access_user_link,hr_attendance.group_hr_attendance_user,1,0,0,0
access_f3d_access_user_link_admin,f3d.access.user.link admin,model_f3d_access_user_link,group_f3d_access_admin,1,1,1,1
access_f3d_access_event_security,f3d.access.event security,model_f3d_access_event,group_f3d_access_security,1,0,0,0
access_f3d_access_event_hr,f3d.access.event hr,model_f3d_access_event,hr_attendance.group_hr_attendance_user,1,0,0,0
access_f3d_access_event_f3d_admin,f3d.access.event f3d admin,model_f3d_access_event,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_access_card_security,f3d.access.card security,model_f3d_access_card,group_f3d_access_security,1,1,1,0
access_f3d_access_card_admin,f3d.access.card admin,model_f3d_access_card,group_f3d_access_admin,1,1,1,1
access_f3d_access_visitor_security,f3d.access.visitor security,model_f3d_access_visitor,group_f3d_access_security,1,1,1,1
access_f3d_access_visitor_hr,f3d.access.visitor hr,model_f3d_access_visitor,hr_attendance.group_hr_attendance_user,1,0,0,0
access_f3d_access_presence_security,f3d.access.presence security,model_f3d_access_presence,group_f3d_access_security,1,0,0,0
access_f3d_access_presence_hr,f3d.access.presence hr,model_f3d_access_presence,hr_attendance.group_hr_attendance_user,1,0,0,0
access_f3d_access_reprocess_wizard_admin,f3d.access.event.reprocess.wizard admin,model_f3d_access_event_reprocess_wizard,group_f3d_access_admin,1,1,1,1
```

20 рядків. Охорона має `write` на двері лише для `action_ack_alarm` (поля дверей, крім `alarm`/`alarm_reason`,
у формі readonly для S; `write` інших полів охороною блокує `F3dAccessDoor.write`: якщо користувач не A і
`set(vals) - {'alarm','alarm_reason'}` → `AccessError("Змінювати двері може лише адміністратор СКУД.")`).
Абстрактні M-12, M-15, M-16 рядків не потребують; міст M-17 (`factory3d_access_telemetry`) нових моделей не має — без `ir.model.access.csv`. Обробка подій, кронів і хуків іде від `sudo()` (крон —
`base.user_root`); кнопки перевіряють групу до `sudo()`. Стандартні моделі (`hr.attendance`, `hr.employee`) — права
`hr_attendance`/`hr`; модуль у них пише лише через `sudo()` обробки.

### 4.2 Групи (`security/f3d_access_security.xml`), Odoo 19 (`res.groups.privilege`)

```xml
<record id="privilege_f3d_access" model="res.groups.privilege">
    <field name="name">Завод 3D: доступ (СКУД)</field>
    <field name="category_id" ref="factory3d_base.module_category_factory3d"/>
    <field name="sequence">70</field>
</record>
<record id="group_f3d_access_security" model="res.groups">
    <field name="name">Охорона</field><field name="privilege_id" ref="privilege_f3d_access"/><field name="sequence">10</field>
    <field name="implied_ids" eval="[Command.link(ref('factory3d_base.group_f3d_user'))]"/>
</record>
<record id="group_f3d_access_admin" model="res.groups">
    <field name="name">Адміністратор СКУД</field><field name="privilege_id" ref="privilege_f3d_access"/><field name="sequence">20</field>
    <field name="implied_ids" eval="[Command.link(ref('group_f3d_access_security')), Command.link(ref('factory3d_base.group_f3d_manager'))]"/>
</record>
<record id="factory3d_base.group_f3d_admin" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_f3d_access_admin'))]"/>
</record>
```

Ланцюг CA-08: `base.group_system` ⊃ `group_f3d_admin` ⊃ `group_f3d_access_admin` ⊃ `group_f3d_access_security`
⊃ `group_f3d_user`. HR-офіцер (`hr_attendance.group_hr_attendance_user`) не отримує груп модуля автоматично.

### 4.3 Record rules

| XML-id | Модель | Домен | Групи | Операції |
|---|---|---|---|---|
| `rule_f3d_access_server_company` | `f3d.access.server` | `[('company_id','in',company_ids)]` | глобальне | усі |
| `rule_f3d_access_device_company` | `f3d.access.device` | `[('company_id','in',company_ids)]` | глобальне | усі |
| `rule_f3d_access_door_company` | `f3d.access.door` | те саме | глобальне | усі |
| `rule_f3d_access_user_link_company` | `f3d.access.user.link` | те саме | глобальне | усі |
| `rule_f3d_access_event_company` | `f3d.access.event` | те саме | глобальне | усі |
| `rule_f3d_access_card_company` | `f3d.access.card` | те саме | глобальне | усі |
| `rule_f3d_access_visitor_company` | `f3d.access.visitor` | те саме | глобальне | усі |
| `rule_f3d_access_presence_company` | `f3d.access.presence` | `['\|',('company_id','=',False),('company_id','in',company_ids)]` | глобальне | read |
| `rule_f3d_access_card_security_visitors` | `f3d.access.card` | `[('holder_type','in',('visitor','pool'))]` | S | write, create (`perm_read=False`, `perm_unlink=False`) |
| `rule_f3d_access_card_admin_all` | `f3d.access.card` | `[(1,'=',1)]` | A | write, create, unlink |

Охорона читає всі картки (номери потрібні на посту), але змінює й створює лише картки відвідувачів і пулу.

### 4.4 Видимість персональних даних

| Дані | Хто бачить | Механізм |
|---|---|---|
| Присутність, зона, «у зоні з», домашня зона працівника | усі внутрішні (`hr.employee.public`, M-08a), переглядач (U) | поля M-08a; провайдер R-12 |
| Журнал подій (хто, коли, які двері), `raw_user_id` | S, H, F | ACL M-05, `groups` поля |
| Номери карток, `biostar_card_id` | S, A | ACL M-06 |
| Відвідувачі (ПІБ, компанія, приймаючий) | S, H | ACL M-07; у переглядачі — лише лічильники; ім'я — тільки S (R-12) |
| `raw` JSON події | F | `groups` поля; без `user_id.name` |
| Біометрія, фото, документи | ніхто — не зберігаються | A-09; AC-64 |
| `session_id`, пароль BioStar | F | `groups` поля, `ir.config_parameter` |

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`) і `tools/params.py`

`tools/params.py`: `PREFIX = "factory3d.access."`; `get_str(env, key, default='')` =
`env['ir.config_parameter'].sudo().get_param(PREFIX + key, default)`; `get_flag(env, key)` =
`get_str(env, key, 'False') in ('True', 'true', '1')`; `get_int(env, key, default, lo, hi)` — `int()`; помилка
перетворення або вихід за `[lo, hi]` → `default` і WARNING «Параметр factory3d.access.%s=%r поза межами, взято %s»;
`set_param(env, key, value)` — `sudo().set_param`.

| key | value (data) | XML-id | Межі `get_int` | Коментар |
|---|---|---|---|---|
| `factory3d.access.write_enabled` | `False` | `param_write_enabled` | — | стоп-кран запису |
| `factory3d.access.biostar_login` | `admin` | `param_biostar_login` | — | емулятор: `SIM_BIOSTAR_USER` |
| `factory3d.access.poll_interval_s` | `60` | `param_poll_interval` | 10–3600 | для `stale` (інтервал крону — в `ir.cron`) |
| `factory3d.access.page_size` | `500` | `param_page_size` | 1–2000 | `Query.limit` |
| `factory3d.access.max_pages_per_run` | `20` | `param_max_pages` | 1–100 | |
| `factory3d.access.overlap_s` | `120` | `param_overlap` | 0–3600 | |
| `factory3d.access.future_tolerance_s` | `300` | `param_future_tolerance` | 0–3600 | верхня межа вікна `now + N` (R-11, R-15) |
| `factory3d.access.initial_lookback_h` | `24` | `param_initial_lookback` | 1–168 | |
| `factory3d.access.recheck_hours` | `24` | `param_recheck_hours` | 1–168 | добова перевірка вікна (R-20) |
| `factory3d.access.paging_mode` | `offset` | `param_paging_mode` | `offset`/`hint` | інше значення → `offset` + WARNING |
| `factory3d.access.dup_window_min` | `20` | `param_dup_window` | 0–120 | R-04 |
| `factory3d.access.merge_gap_min` | `0` | `param_merge_gap` | 0–240 | R-06 |
| `factory3d.access.max_shift_h` | `16` | `param_max_shift` | 1–24 | R-05 (A-20) |
| `factory3d.access.stale_close_enabled` | `True` | `param_stale_close` | — | R-07 |
| `factory3d.access.stale_close_fallback_min` | `60` | `param_stale_fallback` | 1–720 | R-07 |
| `factory3d.access.keep_days` | `90` | `param_keep_days` | 1–3650 | R-20 (Q-08) |
| `factory3d.access.keep_raw` | `False` | `param_keep_raw` | — | |
| `factory3d.access.publish_signals` | `True` | `param_publish_signals` | — | R-18 |
| `factory3d.access.last_events_limit` | `20` | `param_last_events_limit` | 0–100 | R-12 |
| `factory3d.access.card_sync_max_attempts` | `10` | `param_card_sync_max` | 1–100 | R-13 |
| `factory3d.access.visitor_default_hours` | `8` | `param_visitor_hours` | 1–72 | |
| `factory3d.access.visitor_user_prefix` | `V-` | `param_visitor_prefix` | — | BioStar `user_id` відвідувача = префікс + `id` |
| `factory3d.access.visitor_user_group_id` | `1` | `param_visitor_group` | — | `user_group_id.id` для `POST /api/users` (ПРИПУЩЕННЯ: окремої групи «Відвідувачі» в P-10 немає, Q-06) |
| `factory3d.access.migration_state` | `pending` | `param_migration_state` | — | хук пише `done`/`partial`/`skipped` |
| `factory3d.access.migration_report` | `{}` | `param_migration_report` | — | JSON лічильників хука |

`factory3d.access.read_enabled` у data **немає**: його ставить хук (§5.3 крок 1) за `factory3d.base.environment`.
`factory3d.access.biostar_password` у data **немає** (вводить адміністратор, V-13); на тестовому сервері —
значення `SIM_BIOSTAR_PASS` стенду.

### 5.2 Data-файли з макета

**`data/f3d_access_server_data.xml`** (`noupdate="1"`): `server_biostar_sim` — `name="BioStar 2 (емулятор)"`,
`url="https://iot-sim:8443"` (iot_sim §8.1.3), `verify_ssl=True` у XML (на тесті хук ставить `False`, див. нижче),
`timeout_connect_s=5`, `timeout_read_s=30`, `state='offline'`. Обмеження `_check_url` пропускає `verify_ssl=False` лише при `environment='test'`; на
проді (`environment='prod'` до установки) — запис падав би, тому XML-запис створюється з `verify_ssl=True`, а хук
(§5.3 крок 2) ставить `False`, якщо `environment == 'test'`.

**`data/f3d_access_device_data.xml`** (`noupdate="1"`), пристрої (джерело: `plant/infra.py:DOOR_READERS`,
iot_sim API-43). `server_id` = `server_biostar_sim`; `zone_id` — зона «з» дверей (A-23; `zone_at` для зчитувачів на
стінах повертає порожньо: `ACR-IN (99.3, 0.12)` між `Z-KPP` (y ≤ 0) і `Z-ASM` (y ≥ 0.6), `ACR-ELEC (129.0, 62.25)`
між `Z-FG` (y ≤ 62.0) і `Z-ELEC` (y ≥ 62.4), `ACR-CHG (117.0, 59.88)` між `Z-POST` і `Z-CHG`):

| XML-id | `code` | `name` | `biostar_id` | `direction` | `x` | `y` | `zone_id` (ref) |
|---|---|---|---|---|---|---|---|
| `device_acr_in` | ACR-IN | Вхід персоналу (прохідна) | 5390001 | `tna` | 99.3 | 0.12 | `factory3d_base.zone_z_kpp` |
| `device_acr_elec` | ACR-ELEC | Електрощитова | 5390002 | `in` | 129.0 | 62.25 | `factory3d_base.zone_z_fg` |
| `device_acr_chg` | ACR-CHG | Зарядна | 5390003 | `in` | 117.0 | 59.88 | `factory3d_base.zone_z_post` |
| `device_acr_paint` | ACR-PAINT | Склад ЛФМ | 5390004 | `in` | 61.0 | 65.88 | `factory3d_base.zone_z_fac` |
| `device_acr_srv` | ACR-SRV | Серверна | 5390005 | `in` | 99.6 | 48.6 | `factory3d_base.zone_z_maint` |

Двері (джерело: iot_sim API-44, граф ARCH §2.3, A-05):

| XML-id | `code` | `name` | `kind` | `biostar_id` | `entry_device_id` | `zone_from_id` | `zone_to_id` | `is_perimeter` | `dwell_min` |
|---|---|---|---|---|---|---|---|---|---|
| `door_turn_1` | TURN-1 | Турнікет прохідної | `turnstile` | 1 | `device_acr_in` | `zone_z_kpp` | `zone_z_asm` | True | 0 |
| `door_elec` | DOOR-ELEC | Електрощитова | `door` | 2 | `device_acr_elec` | `zone_z_fg` | `zone_z_elec` | False | 30 |
| `door_chg` | DOOR-CHG | Зарядна | `door` | 3 | `device_acr_chg` | `zone_z_post` | `zone_z_chg` | False | 30 |
| `door_paint` | DOOR-PAINT | Склад ЛФМ | `door` | 4 | `device_acr_paint` | `zone_z_fac` | `zone_z_fac` | False | 30 |
| `door_srv` | DOOR-SRV | Серверна | `door` | 5 | `device_acr_srv` | `zone_z_maint` | `zone_z_maint` | False | 30 |

`equipment_id` у data не задається (обладнання створює демо-база, не модуль) — прив'язує хук (§5.3 крок 3).

**`data/scene_home_zones.csv`** (джерело: `plant/site.py:1341–1373` `build_people`, координати → base `zone_at`):

```csv
code,zone
OP-W1,Z-HW
OP-W2,Z-HW
OP-W3,Z-RCV-2
OP-W4,Z-RCV-4
OP-W5,Z-SHEETS
OP-W6,Z-POST
OP-W7,Z-OUT-3
```

### 5.3 `post_init_hook(env)` — кроки, джерела, ідемпотентність, очікувані кількості

`hooks.run_all(env) -> dict` виконує кроки по черзі (усе `sudo`), кожен повертає лічильники; `post_init_hook(env)` =
`run_all(env)` + крок 8. Логер `odoo.addons.factory3d_access.hooks`, INFO на кожен крок. Виняток на будь-якому
кроці відкочує установку (кроки не мають зовнішніх викликів — BioStar хук не чіпає). Повторний виклик — кнопка
не передбачена; `run_all` ідемпотентний (тест AC-60).

| # | Що робить | Джерело | Ідемпотентність | Очікувано (копія демо) | Чиста база |
|---|---|---|---|---|---|
| 1 | параметри: якщо `factory3d.access.read_enabled` відсутній → `'True'` при `factory3d.base.environment == 'test'`, інакше `'False'` | base §5.1 | лише відсутній | `read_enabled: True` | `True` (base ставить `test`) |
| 2 | сервер `server_biostar_sim`: якщо `environment == 'test'` → `verify_ssl=False` | data | перезапис тим самим | `servers: 1` | 1 |
| 3 | пристрої → обладнання: `ACR-IN` → `maintenance.equipment.search_f3d('TURNSTILES')`, решта 4 → `search_f3d('ACCESS')`; не знайдено → WARNING, пропуск | base Додаток F, `plant/infra.py:233` | лише порожнє `equipment_id` | `devices: 5`, `doors: 5`, `equipment_bound: 5` (2 різні одиниці) | `equipment_bound: 0` |
| 4 | зв'язки: для кожного `hr.employee` (активного) з `barcode` (BSID_RE) без зв'язку на сервері → `f3d.access.user.link.create({server_id, biostar_user_id: barcode, employee_id, match: 'barcode', synced: False})` | `hr.employee.barcode` (Додаток B) | пропуск, якщо `(server, barcode)` або `(server, employee)` уже є | `links: 35` | 0 |
| 5 | домашні зони (лише порожні `f3d_home_zone_id`): (а) `f3d_code` вигляду `OP-<wc>` і `mrp.workcenter.search_f3d(wc).f3d_zone_id` → ця зона; (б) інакше перший РЦ, де `employee in wc.employee_ids`, з `f3d_zone_id`; (в) інакше рядок `scene_home_zones.csv` (`f3d.zone.search_f3d(zone)`); (г) інакше без зони + `home_zone_missing += 1` | base Додатки B, C; CSV | лише порожні | `home_zones: 35` (`from_workcenter: 28`: `Z-CUT` 4, `Z-EB` 3, `Z-CNC` 5, `Z-FAC` 6, `Z-ASM` 6, `Z-PACK` 4; `from_csv: 7`), `home_zone_missing: 0` | 0 |
| 6 | початкова присутність (A-22): для працівників з відкритою відміткою (`check_out=False`) і `f3d_access_present=False` → `f3d_access_present=True`, `f3d_access_zone_id = f3d_home_zone_id`, `f3d_access_zone_since = f3d_access_last_in = attendance.check_in`; самі відмітки **не змінюються** | `hr.attendance` (крок `attendance` макета) | лише `present=False` | `presence_seeded: 35`, `attendances_touched: 0` | 0 |
| 7 | перевірка: `hr.attendance` з `in_mode='biostar'` = 0, кількість `hr.attendance` до й після кроку 1…6 однакова | — | — | `attendances_total: 35` | 0 |
| 8 | звіт: `migration_state` (перевірки в цьому порядку) = `skipped` (немає жодного працівника з бейджем) / `partial` (`equipment_bound < 5` або `home_zone_missing > 0`) / `done`; `migration_report` = JSON лічильників + `ts` | — | перезапис | `done` | `skipped` |

Демо-відмітки 35 × `in_mode='manual'` за 2026-10-12 (`plant/odoo_flows.py:469–479`, xml-id `factory3d.att_op_*`)
лишаються як є; дублювання з подіями емулятора виключає R-04 крок 3б (прив'язка в межах `dup_window_min`), а
відкриті відмітки минулих днів закриває R-07 (крон господарства, §6).

**Міст `factory3d_access_telemetry` (X-33, M-17).** Його `post_init_hook(env)` =
`env['f3d.access.telemetry']._f3d_ensure_signals()` (усе `sudo`, без зовнішніх викликів). Ставиться автоматично після
`factory3d_access`, коли встановлено `factory3d_telemetry` (або навпаки). Очікувано — на копії демо й на чистій базі
однаково (5 пристроїв — data access, §5.2): `created: 7` (5 `access/readers/<ACR-*>/last_event`,
`access/turnstiles/TURNSTILES/on_site`, `access/events`), `existing: 0`; повторний виклик — `created: 0`,
`existing: 7`; на копії демо `equipment_id` заповнено у 7 сигналів (`TURNSTILES` — 2, `ACCESS` — 5), на чистій базі
— у 0 (обладнання з кодами немає). Пристрої, що з'являться пізніше (R-19), отримують сигнал у `create` (M-17).

### 5.4 `uninstall_hook(env)`

1. `env['ir.config_parameter'].sudo().search([('key','=like','factory3d.access.%')]).unlink()`.
2. Крони, дії, меню, моделі модуля, поля `f3d_*` на `hr.employee`/`hr.attendance`/`f3d.zone` видаляє стандартна
   деінсталяція; значення `in_mode`/`out_mode = 'biostar'` стандарт переводить у `manual` (`ondelete='set default'`).
3. Події, картки, відвідувачі, зв'язки, пристрої, двері видаляються з таблицями (A-12). `hr.attendance`,
   `hr.employee`, `f3d.zone` не видаляються. Очікувано на демо: `hr.attendance` — та сама кількість, що перед
   деінсталяцією.

### 5.5 `data/neutralize.sql`

```sql
-- factory3d_access: нейтралізована копія проду (FR-16).
UPDATE ir_cron SET active = false
 WHERE id IN (SELECT res_id FROM ir_model_data WHERE module = 'factory3d_access' AND model = 'ir.cron');
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('factory3d.access.read_enabled', 'factory3d.access.write_enabled');
DELETE FROM ir_config_parameter WHERE key = 'factory3d.access.biostar_password';
UPDATE f3d_access_server SET session_id = NULL, state = 'offline', next_try_at = NULL, error_count = 0;
UPDATE f3d_access_card SET sync_state = 'local' WHERE sync_state = 'pending';
UPDATE f3d_access_visitor SET sync_state = 'local' WHERE sync_state = 'pending';
```

## 6. Крони й фонові процеси (`data/ir_cron.xml`, `noupdate="1"`)

Усі: `user_id = base.user_root`, `state='code'`, `active=True` (на тесті; `neutralize.sql` вимикає), без
`numbercall` (Odoo 19). Крони, що ходять у мережу (опитування, синхронізації, запис карток), спочатку перевіряють свій стоп-кран
(`read_enabled` або `write_enabled`); крон dwell і кроки господарства без мережі працюють завжди.

| XML-id | Назва | Інтервал | `code` | Що робить за прогін | Ліміти |
|---|---|---|---|---|---|
| `cron_f3d_access_poll` | СКУД: опитування подій BioStar | 1 хв | `model._cron_poll()` (`f3d.access.server`) | R-11 для кожного активного сервера, де `next_try_at` минув; обробка нових подій R-02…R-10; телеметрія R-18; шина R-12 | ≤ `max_pages_per_run × page_size` рядків (20 × 500 = 10 000); один сервер — один `FOR UPDATE NOWAIT` |
| `cron_f3d_access_sync_users` | СКУД: синхронізація користувачів | 1 год | `model._cron_sync_users()` | R-19 крок 1 | усі сторінки `GET /api/users` по 100 |
| `cron_f3d_access_sync_devices` | СКУД: синхронізація пристроїв і дверей | 1 день, `nextcall` 00:10 UTC (03:10 EEST / 02:10 EET) | `model._cron_sync_devices()` | R-19 кроки 2–3 | — |
| `cron_f3d_access_zone_dwell` | СКУД: повернення з технічних приміщень | 5 хв | `model._cron_zone_dwell()` (`f3d.access.event`) | R-17 | — (обсяг — десятки людей) |
| `cron_f3d_access_card_sync` | СКУД: запис карток і відвідувачів у BioStar | 10 хв | `model._cron_card_sync()` (`f3d.access.card`), далі `env['f3d.access.visitor']._cron_user_sync()` | R-13 крок 6, R-14 крок 2 | 100 карток + 100 відвідувачів за прогін; лише `write_enabled` |
| `cron_f3d_access_housekeeping` | СКУД: ротація і закриття відміток | 1 день, `nextcall` 23:30 UTC (02:30 EEST / 01:30 EET) | `model._cron_housekeeping()` (`f3d.access.event`) | R-20 кроки 1–6 | видалення пакетами по 5 000 з `cr.commit()` між пакетами (поза тестами) |

`_cron_housekeeping` крок 4 (перевірка вікна 24 год) виконується лише при `read_enabled`; решта кроків — завжди.

## 7. HTTP/JSON API

Власних HTTP-контролерів модуль **не має** (усе ініціює Odoo; ARCH §2.2). Нижче — клієнтська сторона P-10
(`tools/biostar_client.py`). Ідентифікатори `factory3d_access API-01…API-09`; відповідність «документації вендора»
`factory3d_iot_sim` API-40…API-46 і статтям Suprema (переглянуто 14.10.2026):
«How to login» https://support.supremainc.com/en/support/solutions/articles/24000072553,
«How To Retrieve Events Logs» …/24000072557, «How to implement pagination for event search» …/24000106474,
«How to enroll a card and assign it to a user» …/24000091098, «How to create a user» …/24000072555,
документація API https://bs2api.biostar2.com/.

### 7.1 Клієнт `BioStarClient`

```python
class BioStarError(Exception):          # .http_status: int|None, .bs_code: str|None, .message: str
class BioStarAuthError(BioStarError):   # 401 або Response.code "101"/"10" після повторного входу
class BioStarWriteDisabled(BioStarError):  # запис при write_enabled=False (до будь-якого з'єднання)

class BioStarClient:
    def __init__(self, url, login, password, verify_ssl=True, timeout=(5, 30), session_id=None,
                 write_enabled=False, http=None): ...   # http: requests.Session (тести підставляють мок)
    session_id: str | None
    def login(self) -> str
    def logout(self) -> None
    def request(self, method, path, json=None, params=None, write=False, _retry=True) -> dict
    def list_users(self, limit=100) -> Iterator[dict]
    def list_users_total(self) -> int
    def list_devices(self) -> list[dict]
    def list_doors(self) -> list[dict]
    def search_events(self, since, until, limit, offset=None, hint=None) -> tuple[list[dict], int | None]
    def create_card(self, card_id: str, card_type_id: int) -> str
    def update_user_cards(self, user_id: str, cards: list[dict]) -> None
    def create_user(self, user_id, name, start_dt, expiry_dt, user_group_id) -> None
```

`request()` (усі виклики): `url = base + path`; заголовки `Content-Type: application/json`, `Accept: application/json`,
`bs-session-id: <session_id>` (крім `login`); `timeout=(connect, read)`, `verify=verify_ssl`. Якщо `write=True` і
`not write_enabled` → `BioStarWriteDisabled("Запис у BioStar вимкнено стоп-краном factory3d.access.write_enabled")`
**до** з'єднання. Обробка відповіді:

| Ситуація | Дія |
|---|---|
| `requests.ConnectionError`, `Timeout`, `SSLError` | `BioStarError(None, None, "<Клас>: <текст без URL-параметрів>")` |
| HTTP 401 або тіло `Response.code ∈ {"10","11"}` (сесія відсутня/прострочена; емулятор AC-41: `code="10"`) і `_retry` | `self.login()`; повтор того самого запиту з `_retry=False` |
| HTTP 401 повторно, або `Response.code == "101"` | `BioStarAuthError(401, code, message)` |
| HTTP 405 | `BioStarError(405, None, "Метод не підтримується сервером BioStar (405)")` (емулятор на запис незмінних ресурсів, iot_sim §11) |
| інший HTTP ≥ 400 | `BioStarError(status, Response.code, Response.message або перші 200 символів тексту)` |
| HTTP 200, тіло не JSON | `BioStarError(200, None, "Невалідна відповідь JSON")` |
| HTTP 200, `Response.code` є і ≠ `"0"` | `BioStarError(200, code, message)` |
| HTTP 200, `Response` відсутній (емулятор API-45) | успіх |

Логування: логер `odoo.addons.factory3d_access.tools.biostar_client`, рівень DEBUG — `"%s %s → %s (%d мс)"`
(метод, шлях без query, статус, час); тіла й заголовки не логуються ніколи. `SecretFilter(logging.Filter)` додається
до цього логера і замінює в `record.getMessage()` збіги `(?i)("password"\s*:\s*")[^"]*(")`, `(?i)(bs-session-id\W+)[0-9a-f\-]{8,}`
на `\1***\2` / `\1***`.

### 7.2 Виклики

| ID | iot_sim | Метод і шлях | Тіло запиту | Відповідь 200 (що читаємо) | `write` |
|---|---|---|---|---|---|
| API-01 | API-40 | `POST /api/login` | `{"User": {"login_id": "<biostar_login>", "password": "<biostar_password>"}}` | заголовок `bs-session-id` → `session_id`; тіло `User.user_id` не використовується | ні |
| API-02 | API-41 | `POST /api/logout` | `{}` + `bs-session-id` | `Response.code == "0"` | ні |
| API-03 | API-42 | `GET /api/users?limit=100&offset=<n>` | — | `UserCollection.total` (рядок → int), `rows[]`: `user_id`, `name`, `user_group_id.name`, `start_datetime`, `expiry_datetime`, `disabled` (`"true"/"false"`), `card_count`, `face_count`, `fingerprint_template_count` (якщо є); **ігнорується**: `photo`, `photo_exists`, шаблони, `pin`, `email`, `phone` | ні |
| API-04 | API-43 | `GET /api/devices` | — | `DeviceCollection.rows[]`: `id`, `name`, `device_type_id.name`, `status` (`"1"` у мережі, `"0"` ні, інше — невідомо), `ip` | ні |
| API-05 | API-44 | `GET /api/doors` | — | `DoorCollection.rows[]`: `id`, `name`, `entry_device_id.id`, `exit_device_id.id` (якщо є), `open_duration` | ні |
| API-06 | API-45 | `POST /api/events/search` | див. нижче | `EventCollection.total`, `rows[]`: `id`, `datetime`, `server_datetime`, `event_type_id.code`, `user_id.user_id`, `device_id.id`, `door_id` (список або об'єкт), `tna_key`, `hint` | ні |
| API-07 | — (емулятор: 405) | `POST /api/cards` | `{"CardCollection": {"rows": [{"card_id": "<number>", "card_type": {"id": "<0\|1\|2\|4>", "type": "1"}}]}}` (ПРИПУЩЕННЯ за полями статті 24000091098: `card_type:id`, `card_type:type`, `card_id`) | `CardCollection.rows[0].id` → `biostar_card_id` | так |
| API-08 | — (емулятор: 405) | `PUT /api/users/<user_id>` | `{"User": {"cards": [{"id": "<biostar_card_id>", "is_blocked": "true\|false"}, …]}}` — **повний** список карток користувача (ПРИПУЩЕННЯ: `is_blocked` — за статтею про мобільний доступ, ARCH §5.2) | `Response.code == "0"` | так |
| API-09 | — (емулятор: 405, Q-12) | `POST /api/users` | `{"User": {"user_id": "V-12", "name": "<ПІБ>", "user_group_id": {"id": "<visitor_user_group_id>"}, "start_datetime": "2026-10-12T05:00:00.00Z", "expiry_datetime": "2026-10-12T13:00:00.00Z", "disabled": "false"}}` (стаття 24000072555) | `Response.code == "0"` | так |

Тіло API-06 (R-11), приклад першої сторінки опитування о 2026-10-12 07:00:30 UTC з курсором 06:59:10:

```json
{"Query": {"limit": 500, "offset": 0,
  "conditions": [{"column": "datetime", "operator": 3,
                  "values": ["2026-10-12T06:57:10.000Z", "2026-10-12T07:05:30.000Z"]}],
  "orders": [{"column": "datetime", "descending": false}]}}
```

Наступна сторінка: `offset` += кількість отриманих рядків (`paging_mode='offset'`); при `paging_mode='hint'` —
`offset` відсутній, додається `"hint": "<rows[-1].hint>"` (стаття 24000106474: `hint` працює лише разом із `limit`).
Відповідь (емулятор, один рядок):

```json
{"EventCollection": {"total": "4", "rows": [{"id": "133", "server_datetime": "2026-10-12T03:52:11.00Z",
  "datetime": "2026-10-12T03:52:10.00Z", "index": "346",
  "user_id": {"user_id": "OPSAW1", "name": "Олег Мельник", "photo_exists": "false"},
  "user_group_id": {"id": "1", "name": "Виробництво"},
  "device_id": {"id": "5390001", "name": "ACR-IN BioEntry W3 (прохідна)"},
  "door_id": [{"id": "1", "name": "Турнікет TURN-1"}], "event_type_id": {"code": "4102"},
  "tna_key": "1", "is_dst": "0", "timezone": {"half": "0", "hour": "3", "negative": "0"}, "hint": "…"}]}}
```

Ідемпотентність: читання — природно; події — `UNIQUE(server_id, biostar_id)`; API-07 не ідемпотентний (повтор
створить другу картку в BioStar) — тому `biostar_card_id`, отриманий раз, більше не перезаписується, а повтор після
помилки API-08 не викликає API-07 удруге (R-13 крок 3); API-08 ідемпотентний (повний список); API-09 — повтор
після успіху дасть помилку «user exists» → R-14 крок 2 трактує `Response.code` з текстом `exist` як успіх.
Ліміти: `limit ≤ 2000` (емулятор, Suprema), ≤ 10 сесій одночасно (емулятор), сесія — 30 хв бездіяльності (емулятор).

## 8. Сервісна частина

Немає: колектор і плагін `collector/plugins/biostar2.py` не пишуться (каркас §6.5, A-02). Емулятор — модуль
`factory3d_iot_sim` (P-10); стендові тести (§13.2) лише керують ним через `/sim/v1` (iot_sim API-13, API-14).

## 9. Алгоритми й правила

Часи в прикладах: «06:52» — Київ, «03:52Z» — UTC. 2026-10-12 — понеділок, Київ = UTC+3 (EEST); з 2026-10-25
01:00Z — UTC+2 (EET). Графік «Зміна 1 (07:00–15:30)» (`resource.calendar` id 2 демо, `tz=Europe/Kyiv`): пн–пт
07:00–11:30 і 12:00–15:30, рядків `day_period='lunch'` немає (тому стандартний `worked_hours` не віднімає обід).
Розклад емулятора R-28: вхід `06:40 + det(code, mod=20)` хв (OP-SAW-1 → 06:52, OP-CNC-4 → 06:40, OP-PACK-2 → 06:59;
та сама формула, що в `plant/odoo_flows.py:step_attendance`), вихід `15:30 + det mod 20`, OP-W1 → ACR-ELEC 09:51,
OP-W2 → ACR-PAINT 10:20, ACR-SRV — Administrator (`user_id "1"`).

### R-01 Валідація кодів і адрес

`code` пристрою/дверей — `CODE_RE` (як base R-01): `ACR-IN`, `TURN-1`, `DOOR-ELEC`, `BS-5390006` — так; `acr-in`,
`ACR_IN`, `ACR--1`, `Турнікет` — ні. `biostar_id`/`biostar_user_id` — `BSID_RE`: `5390001`, `OPSAW1`, `V-12` — так;
`OP SAW`, `'; DROP`, рядок 65 символів — ні. URL — `URL_RE`: `https://iot-sim:8443`, `http://iot-sim:8081` (лише
`environment='test'`) — так; `ftp://x`, `https://iot-sim:8443/api?x=1`, `javascript:alert(1)` — ні. Номер картки —
`CARD_RE`. Невалідні значення з BioStar (рядки API-03/04/05/06) не створюють записів: WARNING
`"BioStar: пропущено рядок %s з невалідним id"` і лічильник `invalid`.

### R-02 Напрямок проходу

Для подій `event_type in ('pass','denied','fail')` з `door_id` і `device_id`:
1. `device_id == door_id.exit_device_id` → `out`;
2. інакше `device_id.direction == 'tna'` → `tna_key == "1"` → `in`; `"2"` → `out`; інше → `none` і
   `error_message = "Невідомий напрямок: tna_key порожній"` (подія лише в журналі);
3. інакше `device_id.direction` (`in`/`out`).
Без `door_id` або `device_id` → `none`. Інші типи → `none`.
Приклади: ACR-IN, `tna_key "1"` → `in`; ACR-IN `"2"` → `out`; ACR-IN `""` → `none`; ACR-ELEC (`in`) → `in`.

### R-03 Зв'язок користувача BioStar з людиною

`_f3d_match_employee(u)` для `u = raw_user_id`/`row.user_id` у межах компанії сервера (`active=True`):
1. зв'язок `(server, u)` уже має `match in ('manual','visitor')` → не змінюється;
2. `hr.employee.search([('barcode','=',u)])` — рівно один → `match='barcode'`;
3. інакше `search([('f3d_alias','=',u)])` — рівно один → `'alias'`;
4. інакше серед `search([('f3d_code','!=',False)])` ті, у кого `f3d_code.replace('-','') == u` — рівно один → `'code'`;
5. інакше `f3d.access.visitor.search([('biostar_user_id','=',u),('server_id','=',server)])` — один → `visitor_id`, `'visitor'`;
6. інакше `'none'`. Збіг за ім'ям заборонено (A-03; імена в демо повторюються, base Додаток B: «Олег Мельник» —
   і OPSAW1, і OPW3). Кілька кандидатів на кроці 2–4 → `'none'` + WARNING «Неоднозначний збіг».
   Знайдений працівник уже має інший зв'язок на сервері (`UNIQUE(server_id, employee_id)`) → `'none'` + WARNING.
Подія з `raw_user_id`, для якого зв'язку немає, створює зв'язок `(server, u)` одразу з результатом кроків 2–6 (не чекає
години до R-19). Приклади: `OPSAW1` → Олег Мельник (`OP-SAW-1`), `barcode`; працівник без бейджа з
`f3d_code='OP-NEST-2'` і користувач `OPNEST2` → `code`; `"1"` (Administrator BioStar) → `none`, подія
`unknown_user=True`.

### R-04 Конвеєр обробки події і вхід через периметр

**Конвеєр** `_f3d_process` для однієї події `ev` (`now = fields.Datetime.now()`):
1. R-03: `link` → `employee_id`/`visitor_id`; `unknown_user = bool(raw_user_id) and not (employee or visitor)`;
2. копії з дверей: `is_perimeter`, `zone_from_id`, `zone_to_id`; R-02 `direction`;
3. `device_id.last_event_ts/code` — якщо `ev.ts ≥ last_event_ts`;
4. `event_type in ('door','alarm')` → R-10; `event_type ≠ 'pass'` → кінець (`attendance_action='none'`; відмови —
   лише журнал, FR-09);
5. `pass` без людини → кінець; відвідувач → R-14 крок 3–4 (`attendance_action='not_employee'`), кінець;
6. працівник `E`: `ev.ts > now` → `attendance_action='future'`, `process_state` лишається `new`, кінець (R-15);
7. `E.f3d_access_last_event_id.ts > ev.ts` → `attendance_action='late'` (запізніла подія; ні відмітка, ні зона не
   змінюються, A-26), кінець;
8. лише для периметра: відкрита відмітка `open = hr.attendance.search([('employee_id','=',E.id),('check_out','=',False)], order='check_in desc', limit=1)`;
   якщо `open` і `ev.ts − open.check_in > max_shift_h` і `stale_close_enabled` → R-07 для `open` (з
   оновленням присутності), `open = None`;
9. `was_present = E.f3d_access_present`; `same_day = E.f3d_access_last_in and local_date(E.f3d_access_last_in) == local_date(ev.ts)`;
10. периметр: `in` → кроки «Вхід» нижче; `out` → R-05; `none` → нічого; не периметр → `attendance_action='none'`;
11. R-08 (присутність і зона); `E.f3d_access_last_event_id = ev`;
12. `process_state='done'`.

**Вхід** (периметр, `direction='in'`), `dup = dup_window_min`:
- `_f3d_drill_active(ev.ts)` → `attendance_action='drill'` (відмітка не змінюється; людина повертається після
  евакуації — CA-09, fire Q-15);
- 3а: є `open` і `open.f3d_in_event_id` порожнє і `|ev.ts − open.check_in| ≤ dup` хв → `open.write({'f3d_in_event_id': ev, 'f3d_in_device_id': device})`
  (`check_in`, `in_mode` не змінюються), `attendance_action='attached'`;
- 3б: є `open` і `was_present and same_day` → `attendance_action='duplicate'`, `apb_suspect=True`;
- 3в: є `open` (інакше) → `attendance_action='attached'` (людина повертається до ще відкритої відмітки, напр.
  ручна відмітка кіоском раніше; `f3d_in_event_id` пишеться, лише якщо порожнє);
- 4а: `open` немає і R-06 повернув відмітку → `attendance_action='merged'`;
- 4б: `open` немає → `create({'employee_id': E, 'check_in': ev.ts, 'in_mode': 'biostar', 'f3d_in_event_id': ev, 'f3d_in_device_id': device})`
  → `attendance_action='checked_in'`; `was_present and same_day` → ще й `apb_suspect=True`.
`ev.attendance_id` = відповідна відмітка.

Приклади (копія демо, 2026-10-12): Олег Мельник має відкриту `manual` відмітку `check_in=03:52:00Z`; подія 4102
ACR-IN `tna_key "1"` о 03:52:10Z → 3а (`|10 с| ≤ 20 хв`) → `attached`, нова відмітка **не** створюється
(35 демо-відміток + 35 подій входу = 35 відміток). Чиста база: та сама подія → 4б, відмітка `check_in=2026-10-12 03:52:10`,
`in_mode='biostar'`, `date=2026-10-12`. Повторна подія входу о 03:55:00Z (людина вже `present`) → 3б,
`duplicate`, `apb_suspect=True`, відміток усе одно одна.

### R-05 Вихід через периметр

(`direction='out'`, після кроків 1–9 конвеєра):
1. `_f3d_drill_active(ev.ts)` → `attendance_action='drill'`, відмітка не закривається;
2. `open` немає → `attendance_action='no_open'`;
3. `ev.ts ≤ open.check_in` → `attendance_action='no_open'`, `error_message="Вихід раніше за вхід відмітки"`;
4. інакше `open.write({'check_out': ev.ts, 'out_mode': 'biostar', 'f3d_out_event_id': ev, 'f3d_out_device_id': device})`
   → `attendance_action='checked_out'`.
`max_shift_h` (16 год, A-20) дозволяє закрити відмітку через північ (нічна робота): вхід 2026-10-12 19:00Z, вихід
2026-10-13 03:00Z (8 год) → закрито подією; вхід 2026-10-12 03:52Z без виходу, наступний «вихід» 2026-10-13 12:40Z
(32 год) → крок 8 конвеєра закрив стару відмітку R-07 о 12:30Z 12.10, подія → `no_open`.
Приклад: Олег Мельник, вихід 15:42 (12:42:05Z, `tna_key "2"`) → `check_out=2026-10-12 12:42:05`,
`out_mode='biostar'`; `worked_hours` рахує стандарт (≈ 8,83 год від 03:52:10Z).

### R-06 Злиття коротких виходів (обід)

Лише при `merge_gap_min > 0` і вході без відкритої відмітки: `last = hr.attendance.search([('employee_id','=',E),('check_out','!=',False),('out_mode','=','biostar'),('check_out','>=',ev.ts − merge_gap_min),('check_out','<=',ev.ts)], order='check_out desc', limit=1)`;
`local_date(last.check_in) == local_date(ev.ts)` → `last.write({'check_out': False, 'out_mode': 'manual', 'f3d_out_event_id': False, 'f3d_out_device_id': False})`
(стандарт не має «порожнього» `out_mode`; `manual` — значення за замовчуванням), `ev.attendance_id = last`.
Приклад: OP-SAW-1 вийшов на обід 11:31 (08:31Z), повернувся 11:58 (08:58Z), вийшов 15:42 (12:42Z).
`merge_gap_min=0` (за замовчуванням, A-06) → 2 відмітки: 03:52–08:31 (4,65 год) і 08:58–12:42 (3,73 год), сума 8,38 год;
`merge_gap_min=45` → 1 відмітка 03:52–12:42 (8,83 год; обід увійшов у відпрацьоване — графік без рядка `lunch`).

### R-07 Закриття відкритої відмітки без виходу

Умова: `stale_close_enabled`; відмітка `A` відкрита; викликається (а) кроком 8 конвеєра, (б) R-20 крок 2 для
відміток працівників, що мають активний зв'язок BioStar, з `local_date(A.check_in) < local_date(now)` і
`now − A.check_in > max_shift_h`.
1. `tz = E._get_tz()` (календар → працівник → компанія → UTC; у демо `Europe/Kyiv`); `d = local_date(A.check_in, tz)`;
2. `cal = E.resource_calendar_id`; рядки `cal.attendance_ids` з `dayofweek == str(d.weekday())`,
   `display_type != 'line_section'`, `day_period != 'lunch'`, і при `cal.two_weeks_calendar` —
   `week_type == str(env['resource.calendar.attendance'].get_week_type(d))`;
3. рядки є → `end = tz.localize(datetime.combine(d, time()) + timedelta(hours=max(hour_to)))` → UTC naive
   (`tools/dates.schedule_end_utc`); `end > A.check_in` → `check_out = end`;
4. інакше (вихідний, немає календаря або вхід після кінця графіка) → `check_out = A.check_in + stale_close_fallback_min`;
5. `A.write({'check_out': check_out, 'out_mode': 'technical', 'f3d_closed_by_rule': True})`;
   `A.message_post(body="Закрито правилом СКУД: немає проходу на вихід; вихід = %s." % ("кінець графіка %s" % HH:MM | "вхід + %s хв" % N))`;
6. якщо `E.f3d_access_present` і (`not E.f3d_access_last_in` або `E.f3d_access_last_in ≤ check_out`) →
   `present=False`, `zone=False`, `zone_since=False`, `zone_door=False`, шина.
Відмітки, закриті стандартним авто-виходом (`out_mode='auto_check_out'`), R-07 не чіпає (вони вже закриті).

| Вхід (`check_in`) | Кінець графіка | `check_out` |
|---|---|---|
| 2026-10-12 03:52:00Z (пн, 06:52 EEST) | 15:30 EEST | 2026-10-12 12:30:00Z |
| 2026-10-26 05:01:00Z (пн, 07:01 EET) | 15:30 EET | 2026-10-26 13:30:00Z |
| 2026-10-12 13:10:00Z (пн, 16:10 — після кінця) | 15:30 < входу | 2026-10-12 14:10:00Z (+60 хв) |
| 2026-10-17 06:00:00Z (сб) | рядків немає | 2026-10-17 07:00:00Z |

Демо: 35 відміток 2026-10-12 03:40…03:59Z → R-20 крок 2 першого ж прогону господарства на тестовому сервері
(реальна дата 14.10) закриває всі 35 о 12:30:00Z з `f3d_closed_by_rule=True`.

### R-08 Присутність і зона людини (граф дверей)

Для події `pass` з людиною (працівник після кроку 10 конвеєра; відвідувач — R-14), `home` = `E.f3d_home_zone_id`
(відвідувач — порожньо), `D` = двері, `t = ev.ts`. Оновлення пишуться лише якщо змінюються (інакше
`presence_changed=False`):

| Випадок | `present` | `zone` | `zone_since` | `zone_door` | Інше |
|---|---|---|---|---|---|
| периметр, `in` | True | `home` або `D.zone_to_id` | `t` | — | `last_in = t`; `was_present and same_day` → `apb_suspect=True` |
| периметр, `out` | False | — | — | — | `last_out = t`; `not was_present` → `apb_suspect=True` |
| периметр, `drill`/`none` | як для `in`/`out` за `direction`; `none` — без змін | | | | |
| внутрішні, `in`, є `D.zone_to_id` | True (якщо було False → ще й `apb_suspect=True`) | `D.zone_to_id` | `t`, якщо зона змінилась, інакше без змін | `D`, якщо `D.dwell_min > 0` | відвідувач: `allowed_zone_ids` непорожні і `D.zone_to_id ∉` → `zone_violation=True` |
| внутрішні, `out` (зчитувач виходу) | True | `home` або `D.zone_from_id` | `t` | — | |
| двері без зон | без змін | без змін | — | — | лише журнал |

Приклади (2026-10-12): OP-SAW-1 вхід 06:52 → `present`, зона `Z-CUT` (домашня з РЦ SAW-1), з 06:52; без домашньої
зони → `Z-ASM` (`TURN-1.zone_to_id`). OP-W1 о 09:51 через ACR-ELEC → `Z-ELEC` з 09:51, `zone_door=DOOR-ELEC`
(`dwell_min=30`) → R-17 о 10:21 повертає в `Z-HW`. OP-W2 о 10:20 через ACR-PAINT → `Z-FAC` (контейнер комори
`PAINT-STORE`), о 10:50 → `Z-HW`. Стан на 10:30 демо-годинника при відтворенні дня емулятором: `Z-CUT` 4,
`Z-EB` 3, `Z-CNC` 5, `Z-FAC` 7 (6 операторів + OP-W2), `Z-ASM` 6, `Z-PACK` 4, `Z-HW` 1, `Z-RCV-2` 1, `Z-RCV-4` 1,
`Z-SHEETS` 1, `Z-POST` 1, `Z-OUT-3` 1 — разом 35. Вихід 15:42 → `present=False`, зона порожня.

### R-09 Класифікація кодів подій (`tools/event_codes.classify`)

`code = mainCode·256 + subCode` (BioStar 2 Device SDK «Log Management API»,
https://kb.supremainc.com/bs2sdk/doku.php?id=en:log_management_api, iot_sim §8.12). Класифікація — за
`main = code >> 8`, `sub = code & 0xFF` (A-27: стійко до розбіжності iot_sim ARCH Q-13 / Додаток A «4096», де sub = 0).

| `main` (hex) | Коди | `event_type` | `credential` / `deny_reason` за `sub` | Назва (`code_name`) |
|---|---|---|---|---|
| 0x10 | 4096–4351 | `pass` | 0x01 `pin`; 0x02–0x03 `id_finger`; 0x04–0x05 `id_face` (**4100**); 0x06–0x0B `card` (**4102**); інше `other` | Успішна перевірка |
| 0x11 | 4352–4607 | `fail` | — | Невдала перевірка |
| 0x12, 0x15 | 4608…, 5376… | `alarm` | — | Прохід під примусом (duress) |
| 0x13 | 4864–5119 | `pass` | 0x01–0x02 `finger` (**4865**); 0x03–0x04 `face` (**4867**); інше `other` | Успішна ідентифікація |
| 0x14, 0x17, 0x18 | **5120**… | `fail` | — | Невдала ідентифікація / автентифікація |
| 0x16 | 5632… | `pass` | `other` | Подвійна автентифікація |
| 0x19 | **6400**–6655 | `denied` | 0x01 `access_group` (6401); 0x02 `disabled` (6402); 0x03 `expired` (6403); 0x04 `blacklist` (6404); 0x05 `apb` (**6405**); 0x06 `timed_apb` (6406); 0x07 `scheduled_lock` (6407); 0x00 та інше `other` (6400) | Відмову в доступі |
| 0x20–0x2F | 8192–12287 | `system` | — | Керування користувачами/пристроєм |
| 0x30–0x3F | **12544** (0x3100), **15104** (0x3B00) | `system` | — | Пристрій: запуск, мережа |
| 0x50 | **20480** | `door` | стан `unlocked` | Двері розблоковано |
| 0x51 | 20736 | `door` | `locked` | Двері зачинено на замок |
| 0x52 | **20992** | `door` | `open` | Двері відчинено |
| 0x53 | **21248** | `door` | `closed` | Двері зачинено |
| 0x54 | 21504 | `door` | `forced` (тривога) | Двері відчинено силоміць |
| 0x55 | 21760 | `door` | `held` (тривога) | Двері тримаються відчиненими |
| 0x56–0x5F | | `door` | без зміни стану | Подія дверей |
| 0x60–0x6F | **26368** (0x6700) | `alarm` | 0x6700 → пожежна тривога (`fire`) | Тривога зони |
| інше | | `other` | — | Подія %s |

`classify(code)` → `{'event_type', 'credential', 'deny_reason', 'door_state', 'alarm_reason', 'name'}`; `code ≤ 0`
→ `other`. Відмови й підозри фіксуються лише в журналі (A-08): у Odoo нічого не блокується.

### R-10 Стан дверей (FR-03, CA-04)

Для подій `door`/`alarm` з `door_id` (а для 26368 без дверей — усі активні двері сервера): якщо
`door.state_ts` порожній або `ev.ts ≥ door.state_ts`:
1. `door_state` з R-09 → `state`, `state_ts = ev.ts`;
2. `forced`/`held` → `alarm=True`, `alarm_reason` відповідно; 26368 → `alarm=True`, `alarm_reason='fire'` (стан не змінюється);
3. `closed`/`locked` знімають тривогу з причиною `forced`/`held` (не `fire`; пожежну знімає охорона `action_ack_alarm`);
4. зміна `state`/`alarm` → шина `('f3d.access.door', [code], 'state')` (R-12 крок 6).
Приклад: 20480 03:52:10Z → `unlocked`; 20992 03:52:11Z → `open`; 21248 03:52:16Z → `closed`. Запізніла 20992 з
03:52:11Z після 21248 → ігнорується (стан `closed`). `fire_drill` емулятора: 20480 на дверях 1–5 + 26368 → усі 5
`unlocked`, `alarm=True`, `alarm_reason='fire'`.

### R-11 Опитування `events/search` (FR-05)

`server._poll()`:
1. `cr.execute("SELECT id FROM f3d_access_server WHERE id = %s FOR UPDATE NOWAIT", [id])`; `psycopg2.errors.LockNotAvailable`
   → `{'skipped': True}` (крон) або `UserError` (кнопка);
2. `now`; `since = last_event_ts − overlap_s` (курсор є) або `now − initial_lookback_h`; `until = now + future_tolerance_s`;
3. `client = _get_client()`; без `session_id` перший запит робить `login()` (API-01);
4. сторінки: `rows_all = []`; `page = 0`; цикл: `rows, total = client.search_events(since, until, limit=page_size, offset=len(rows_all))`
   (`paging_mode='hint'`: `offset=None`, `hint=rows_all[-1]['hint']` для сторінок ≥ 2); `rows_all += rows`; `page += 1`;
   вихід, якщо `len(rows) < page_size` або `page == max_pages_per_run`; `more = (page == max_pages_per_run and len(rows) == page_size)`;
5. `res = env['f3d.access.event']._f3d_ingest_rows(server, rows_all)` (лише після всіх сторінок: помилка мережі на
   будь-якій сторінці → нічого не збережено, курсор не рухається, R-16);
6. обробка: `env['f3d.access.event'].search([('server_id','=',id),('process_state','=','new'),('ts','<=',now)], order='ts, id', limit=10000)._f3d_process()`
   (включно з раніше відкладеними `future`);
7. курсор: `max_ts = max(parse_bs_dt(r['datetime']) for r in rows_all)`; `new = min(max_ts, now)`; якщо
   `not last_event_ts or new > last_event_ts` → `last_event_ts = new`, `last_event_biostar_id` = `id` рядка з `max_ts`;
   майбутні події курсор за `now` не переносять (інакше між `now` і курсором губилися б події);
8. `_save_session(client)`, `_mark_ok()`, `last_poll_at=now`, `last_poll_rows=len(rows_all)`, `last_poll_new=res['created']`, `last_poll_more=more`;
9. R-18 (якщо `created > 0`).
Перекриття `overlap_s=120` дає повторні рядки щохвилини — вони відсіюються `UNIQUE(server_id, biostar_id)`
(`duplicates`). Приклад: ранок 06:40–07:00 емулятор дає 35 × (4102|4867) + 35 × 3 події дверей = 140 рядків
(Додаток §13.1 `events_shift.json`); опитування щохвилини бере ≈ 7 нових і ≈ 14 повторних. Після простою 3 год
(≈ 160 подій) перше опитування бере все однією сторінкою. Обмеження: > `page_size·max_pages_per_run` подій з одним і
тим самим `datetime` не пройдуть (на макеті неможливо: ≤ 1 400 подій/добу).

### R-12 Схема даних переглядача (CA-05)

`_f3d_viewer_collect(payload, ctx)`; `is_sec = env.user.has_group('factory3d_access.group_f3d_access_security')`;
усі часи — `to_local_str` (viewer R-02), «сьогодні» — доба `ctx['today']` за Києвом:
1. `pres = env['hr.employee']._f3d_access_public_presence()` (sudo, лише непублічно-нечутливі поля, A-21);
2. для кожного `code` у `payload.get('employees', {})`, що є в `pres` (інші записи не змінюються): `rec['present'] = bool(pres[code].present)` (перекриває
   значення провайдера `people` з `hr.attendance`), `rec['zone']` = код зони або `None`, `rec['zone_since']` або
   `None`, `rec['last_event'] = {"ts", "door", "direction", "type"}` або `None` (двері — код, без осіб);
3. для кожного `code` у `payload.get('zones', {})`: `["people_now"] = n` (0, якщо нікого);
4. `payload["access"]`:

```json
{"updated": "2026-10-12 10:30",
 "server": {"name": "BioStar 2 (емулятор)", "state": "online", "stale": false, "last_contact": "2026-10-12 10:29"},
 "on_site": {"employees": 35, "visitors": 1, "total": 36},
 "today": {"events": 152, "passes": 38, "entries": 35, "exits": 0, "denied": 1},
 "zones": {"Z-CUT": 4, "Z-EB": 3, "Z-CNC": 5, "Z-FAC": 7, "Z-ASM": 6, "Z-PACK": 4, "Z-HW": 1, "Z-OFFICE": 1},
 "people": {"OP-SAW-1": {"present": true, "zone": "Z-CUT", "zone_since": "2026-10-12 06:52",
            "last_event": {"ts": "2026-10-12 06:52", "door": "TURN-1", "direction": "in", "type": "pass"}}},
 "visitors": [{"code": "V-12", "zone": "Z-OFFICE", "since": "2026-10-12 09:10", "name": "Іван Петренко"}],
 "readers": {"ACR-IN": {"name": "Вхід персоналу (прохідна)", "zone": "Z-KPP", "x": 99.3, "y": 0.12,
             "status": "online", "last_event": {"ts": "2026-10-12 06:59", "code": 4102, "type": "pass"}}},
 "doors": {"TURN-1": {"name": "Турнікет прохідної", "kind": "turnstile", "state": "closed", "alarm": false,
           "alarm_reason": null, "is_perimeter": true, "zone_from": "Z-KPP", "zone_to": "Z-ASM", "passes_today": 35}},
 "cards": {"TURNSTILES": {"rows": [["На території зараз", "35 працівників · 1 відвідувач"], ["Сьогодні проходів", "38"],
                                    ["Odoo Attendances", "відмітки входу й виходу щохвилини · опитування 10:29"]]},
           "ACCESS": {"rows": [["Дверей з рідерами", "5"], ["Останній доступ", "склад ЛФМ, 10:20 — Інна Карпенко"]]}},
 "last_events": [{"ts": "2026-10-12 10:20", "door": "DOOR-PAINT", "device": "ACR-PAINT", "direction": "in",
                  "type": "pass", "code": 4102, "person": "OP-W2"}]}
```

   Правила полів: `people` — усі працівники з `f3d_code` (і для дельти, Q-10); `zones` — лише ненульові;
   `visitors[].name` і `last_events` (останні `last_events_limit` подій, `person` = `f3d_code` або `V-<id>` або
   `null`) — **лише** `is_sec`, інакше ключа `name` немає, а `last_events = []`; «Останній доступ» — остання подія
   `pass` на дверях `is_perimeter=False`: `"%s, %s" % (назва дверей з малої літери, HH:MM)` + `" — " + ім'я` лише для
   `is_sec`; «Сьогодні проходів» = `today.passes`; рядок «… відвідувач/відвідувачі/відвідувачів» — українська форма
   множини (1 / 2–4 / 5+);
5. якщо `payload.get('infra', {}).get('cards')` має ключі `TURNSTILES`/`ACCESS` (повний payload зі статикою) →
   їхні `rows` замінюються рядками з `access.cards` (A-14: живі лічильники замість «146 працівників · 3 відвідувачі»,
   «312»);
6. (обробка подій, не провайдер) після `_f3d_process` пакета: `'f3d.viewer.event' in env` → по одному виклику
   `_notify('hr.employee', коди працівників з presence_changed, 'state')`, `_notify('f3d.access.door', коди дверей зі
   зміною R-10, 'state')`, `_notify('f3d.access.visitor', ['V-<id>', …], 'state')`; без viewer — нічого.
7. `_f3d_viewer_delta(patch, ctx)` (X-23, X-87; viewer R-14 п. 5, 7):
   1) умова: `set(ctx.get('changes') or {}) & {'hr.employee', 'f3d.access.door', 'f3d.access.visitor'}` порожня →
      `patch` не змінюється;
   2) `tmp = {'employees': {c: {} for c in ctx['changes'].get('hr.employee', ())}, 'zones': {z: {} for z in
      env['f3d.zone'].search([]).mapped('f3d_code')}, 'infra': {'cards': {'TURNSTILES': {}, 'ACCESS': {}}}}`;
      `self._f3d_viewer_collect(tmp, ctx)` — кроки 1–5 заповнюють `employees[code]` (`present`, `zone`, `zone_since`,
      `last_event`), `zones[code].people_now` (0 для зон без людей — так клієнт обнуляє зону, яку покинули), розділ
      `access` і `infra.cards.TURNSTILES/ACCESS.rows`;
   3) `from odoo.addons.factory3d_viewer.tools.payload import deep_merge` (імпорт усередині методу: метод викликає лише
      встановлений viewer, A-19); `patch['access'] = tmp['access']` (власний розділ провайдера — цілком); для
      `k in ('employees', 'zones', 'infra')` з непорожнім `tmp[k]` — `deep_merge(patch.setdefault(k, {}), tmp[k])`:
      лише доповнення, ключі інших провайдерів (`employees[code].name/workcenter` від `people`, інші ключі
      `zones[code]`, картки `infra.cards.PV-INV`/`GENSET`/`TRUCK-SCALE` energy/genset/yard) не змінюються;
      присвоєння `patch['infra'] = …`, `patch['employees'] = …`, `patch['zones'] = …` заборонене;
   4) клієнт viewer зливає дельту глибоко (viewer R-14 п. 7): рядки карток СКУД, присутність і «Людей зараз» у 3D
      оновлюються без повного перечитування.
   Приклад: `patch = {'infra': {'cards': {'PV-INV': {'rows': [['Зараз', '468 кВт']]}}}, 'employees': {'OP-SAW-1':
   {'name': 'Олег Мельник', 'workcenter': 'SAW-1'}}}` (від energy і `people`), `ctx.changes = {'hr.employee':
   {'OP-SAW-1'}, 'f3d.access.door': {'TURN-1'}}` → `patch.infra.cards` — `PV-INV`, `TURNSTILES`, `ACCESS`;
   `patch.employees['OP-SAW-1']` — `name`, `workcenter`, `present: true`, `zone: 'Z-CUT'`, `zone_since`, `last_event`;
   `patch.zones['Z-CUT'].people_now = 4`, зони без людей — 0; `patch.access` — повний розділ (AC-51, AC-67).
Без групи `group_f3d_user` провайдер не викликається (viewer `_f3d_group`).

### R-13 Картки: запис у BioStar (FR-10)

1. `_f3d_queue(op)` — M-06; без `write_enabled` жодного мережевого виклику (AC-40, AC-56).
2. `_f3d_push()` (sudo) для карток `sync_state='pending'`: `user = ` зв'язок `(server, employee)` → `biostar_user_id`
   (працівник) або `visitor.biostar_user_id`; немає → `error`, `"У власника картки немає користувача BioStar."`;
3. `issue`: якщо `biostar_card_id` порожній → API-07 (`card_id=number`, `card_type.id` за M-06) → одразу записати
   `biostar_card_id`; далі API-08 з повним списком карток власника на сервері, що мають `biostar_card_id` і
   `state in ('active','blocked')`: `[{"id": c.biostar_card_id, "is_blocked": "true" if c.state == 'blocked' else "false"}]`;
   `block`/`unblock` — лише API-08 (немає `biostar_card_id` → `error`, `"Картку не записано в BioStar: видайте її під
   стоп-краном або позначте синхронізованою вручну."`); `return` — API-08 зі списком **без** цієї картки;
4. успіх → `sync_state='synced'`, `sync_ts=now`, `pending_op=False`, `sync_error=False`, `message_post` «Записано в BioStar: %s»;
5. `BioStarWriteDisabled` → `sync_state='local'`; інший `BioStarError` → `sync_state='error'`, `sync_error=str(e)[:255]`,
   `sync_attempts += 1`, `message_post` «Помилка запису в BioStar: %s»; **локальний** `state` не відкочується;
6. крон 10 хв повторює `pending`/`error` з `sync_attempts < card_sync_max_attempts`.
Емулятор (ТК-08): API-07 → 405 → `error`, `sync_error="Метод не підтримується сервером BioStar (405)"`, `state='blocked'`.

### R-14 Відвідувачі (FR-11, CA-07)

1. Переходи — §10.4; `f3d_visitor_register(vals)` = `create` + `action_expect`.
2. Користувач BioStar (на `action_expect` і кроном): якщо `biostar_user_id` порожній і `write_enabled` →
   `biostar_user_id = visitor_user_prefix + str(id)` (`V-12`) і API-09 (`start = date_from`, `expiry = date_to + 1 год`,
   `user_group_id = visitor_user_group_id`); успіх або `Response.message` містить `exist` → `sync_state='synced'`;
   помилка → `error` + текст. Без `write_enabled` → `sync_state='local'`, охорона вводить `biostar_user_id` вручну.
   Будь-яка зміна `biostar_user_id` → зв'язок `(server, biostar_user_id)`: створити або оновити `visitor_id`,
   `match='visitor'`; зв'язок належить працівнику → `ValidationError("Користувач BioStar %s належить працівнику %s.")`.
3. Прохід периметра відвідувача: `in` і стан `expected` → `on_site`, `arrived_at=t`; `out` і `on_site` → `left`,
   `left_at=t`; присутність/зона — R-08; стани `draft`/`closed`/`cancelled`/`left` (вхід після виходу → знову
   `on_site`, якщо `t ≤ date_to + 1 год`, інакше лише журнал) → `error_message="Відвідувач у стані «%s»: прохід лише зафіксовано"`.
4. Внутрішні двері — R-08 (`zone_violation`). Відміток `hr.attendance` відвідувачі не мають (`not_employee`).
5. Прострочення — R-20 крок 3.

### R-15 Час і часові пояси

`parse_bs_dt(s)`: приймає `2026-10-12T03:52:10.00Z`, `…10.000Z`, `…10Z`, `…10+00:00`; повертає naive UTC; порожнє →
`None`; інше → `ValueError` (рядок `invalid`, R-01). `fmt_bs_dt(dt)` → `"2026-10-12T03:52:10.000Z"`.
Поля `timezone`/`is_dst` подій ігноруються: час завжди з `datetime` (UTC). Локальна доба людини —
`E._get_tz()` (у демо `Europe/Kyiv`), для журналу й переглядача — `Europe/Kyiv`. Приклади: `2026-10-12T21:30:00Z` →
13.10 00:30 (наступна доба); `2026-10-25T00:30:00Z` → 25.10 03:30 EEST; `2026-10-25T01:30:00Z` → 25.10 03:30 EET
(той самий локальний час двічі — порядок визначає UTC); `2026-10-26T05:00:00Z` → 07:00. Майбутні події: верхня межа
вікна `now + future_tolerance_s`; подія з `ts > now` зберігається (`attendance_action='future'`, `process_state='new'`)
і обробляється першим опитуванням, коли `ts ≤ now` (прискорений годинник емулятора `factor > 1`, iot_sim API-14).

### R-16 Сесія, повтори, пауза

`session_id` зберігається на сервері між прогонами; 401 / `Response.code ∈ {"10","11"}` → один повторний `login()`;
невдача → `BioStarAuthError`. Будь-який `BioStarError` у `_poll`/`_sync_*` → `_mark_error`: пауза
`min(60·2^(n−1), 600)` с, де `n = error_count` після збільшення: n=1 → 60 с, 2 → 120, 3 → 240, 4 → 480, ≥ 5 → 600.
Крон до `next_try_at` сервер пропускає. Успіх → `online`, `error_count=0`. Курсор при помилці не змінюється — після
відновлення вікно `last_event_ts − overlap_s … now` забирає все пропущене (FR-05); простій > `initial_lookback_h` не
обмежує (вікно від курсора), але > 10 000 подій забираються кількома прогонами (`last_poll_more`).

### R-17 Повернення з технічного приміщення і «людей зараз»

`_cron_zone_dwell` (5 хв): `hr.employee` і `f3d.access.visitor` з `zone_door_id.dwell_min > 0`, `present=True` і
`zone_since + dwell_min ≤ now` → `zone = home or zone_door_id.zone_from_id`, `zone_since = now`, `zone_door_id=False`,
шина. Приклад: OP-W1 `Z-ELEC` з 06:51Z (09:51) → прогін о 07:25Z (10:25) → `Z-HW`. `f3d.zone.f3d_people_now` — M-10,
рахує за збереженими полями (A-07).

### R-18 Сигнали телеметрії (FR-15)

Після опитування з `created > 0`, якщо `publish_signals` і `'f3d.signal' in env` (інакше нічого):
`readings` = для кожного пристрою з новими подіями типу `pass`/`denied`/`fail` — остання з них:
`{"code": "access/readers/%s/last_event" % device.code, "ts": ev.ts, "value": float(ev.code), "text": ("%s %s" % (ev.code, ev.door_id.code or '')).strip()[:64], "q": "good"}`
(без `user_id` — персональні дані в телеметрію не йдуть, A-28);
`{"code": "access/turnstiles/TURNSTILES/on_site", "ts": now, "value": float(on_site.total)}`;
`{"code": "access/events", "ts": now, "value": float(created), "text": "pass:%d denied:%d door:%d" % (…)}`.
`env['f3d.signal'].sudo()._f3d_ingest(readings, src='module')` у `savepoint`; виняток → WARNING, опитування не падає.
Сигнали створює міст `factory3d_access_telemetry` (M-17, X-33): 7 записів `f3d.signal` = iot_sim Додаток A 647–653
(`module='access'`, `origin='module'`, без джерела; по одному `…/last_event` на кожен пристрій). Міст ставиться
автоматично разом із telemetry, тож `rejected` (`unknown_code`) буває лише для архівного чи видаленого сигналу → DEBUG.

### R-19 Синхронізація довідників (FR-02, FR-03, FR-04)

1. **Користувачі** (`_sync_users`): усі сторінки API-03 (`limit=100`); для рядка: `u = str(user_id)`, не `BSID_RE` →
   пропуск; зв'язок `(server, u)` створити/оновити: `biostar_name=name`, `user_group=user_group_id.name`,
   `disabled = (disabled == "true")`, `start_dt`/`expiry_dt` (R-15), `card_count=int(card_count or 0)`,
   `has_face = int(face_count or 0) > 0`, `has_finger = int(fingerprint_template_count or finger_count or 0) > 0`,
   `in_biostar=True`, `synced=True`, `last_sync=now`; `match='none'` → R-03; зв'язки сервера, яких не було у відповіді →
   `in_biostar=False`. Повертає `{'total', 'created', 'updated', 'matched', 'unlinked', 'missing'}`; `users_total`,
   `users_synced_at`. Емулятор: `total=36`, зв'язків 36: 35 `barcode`, `"1"` — `none` (`unlinked=1`).
2. **Пристрої** (`_sync_devices` ч. 1): API-04; пристрій `(server, id)`: немає → `create({'code': 'BS-%s' % id, 'name', 'direction': 'in'})`
   + WARNING «Новий пристрій BioStar %s: задайте код сцени, зону й напрямок»; є → `device_type`, `ip`,
   `status` (`"1"` → `online`, `"0"` → `offline`, інше → `unknown`), `status_ts=now`, `sync_fail_count=0` (`name`
   існуючих не перезаписується). Пристрої сервера, яких немає у відповіді → `status='unknown'`. Помилка
   синхронізації → усім пристроям сервера `sync_fail_count += 1`; `≥ 2` → `status='unknown'`.
3. **Двері** (`_sync_devices` ч. 2): API-05; двері `(server, id)`: немає → `create({'code': 'BSD-%s' % id, 'name', 'kind': 'door'})`
   (без зон — лише журнал, ARCH §5.2); `entry_device_id`/`exit_device_id` — пристрої з `biostar_id` відповідних
   `id`; `open_duration_s`. Емулятор: 5 пристроїв і 5 дверей оновлено, створено 0; `devices_total=5`.

### R-20 Господарство (крон щодоби, FR-18)

1. Ротація: `f3d.access.event` з `ts < now − keep_days` — `unlink` пакетами по 5 000 (sudo);
2. R-07 для відкритих відміток працівників з активним зв'язком (умова R-07 (б));
3. відвідувачі `state in ('expected','on_site','left')` з `date_to + 1 год < now` → `state='closed'`, `overdue=True`
   для `expected`/`on_site`, `present=False`, зона порожня, картка `action_return()`, `message_post`
   «Закрито автоматично: строк візиту минув»;
4. при `read_enabled`: для кожного активного сервера `_poll_window(now − recheck_hours, now)` (події, що надійшли на
   сервер із запізненням, Q-02; дублікати відсіюються);
5. картки `returned`/`lost` з `returned_at < now − keep_days` → `visitor_id=False` (картка лишається в пулі);
6. відвідувачі `closed`/`cancelled` з `date_to < now − keep_days` → `unlink` (мінімізація ПД, Q-08).

### R-21 Службові методи для інших модулів (FR-20, CA-03, CA-09)

1. `f3d_on_site_at(ts, company=None)`: SQL
   `SELECT DISTINCT ON (employee_id) employee_id, direction, ts FROM f3d_access_event WHERE employee_id IS NOT NULL AND is_perimeter AND event_type = 'pass' AND direction IN ('in','out') AND ts <= %(ts)s AND ts >= %(ts)s - interval '%(h)s hours' AND company_id = ANY(%(cids)s) ORDER BY employee_id, ts DESC, id DESC`
   (`h = max_shift_h`, `cids` = `company.ids` або `env.companies.ids`) → на території, якщо `direction='in'`; плюс
   працівники з `f3d_access_present=True` без жодної події периметра (присутність із хука, A-22), якщо
   `f3d_access_last_in ≤ ts`; те саме для `visitor_id`. Повертає `{'employees': hr.employee, 'visitors': f3d.access.visitor, 'ts': ts}`.
   Приклад: дані ранку 2026-10-12, `ts = 07:30Z` → 35 працівників; `ts = 03:45Z` → лише ті, хто увійшов до 06:45
   (OP-CNC-4, OP-SPRAY-1, OP-PACKLINE-1, OP-W6 — 06:40; OP-CNC-3 — 06:41; OP-EDGE-1, OP-CNC-2, OP-ASM-1 — 06:42;
   OP-EDGE-2, OP-CNC-1, OP-ASM-2 — 06:43; OP-ASMLINE-1, OP-ASM-3 — 06:44; OP-SAND-1, OP-ASM-4 — 06:45) — 15.
2. `f3d_passes_between(t0, t1, door_codes=None, direction=None)` → `search([('event_type','=','pass'),('ts','>=',t0),('ts','<=',t1)] + ([('door_id.code','in',door_codes)] if door_codes else []) + ([('direction','=',direction)] if direction else []), order='ts, id')`.
   Для навчальної тривоги fire_safety: `f3d_passes_between(start, end, ['TURN-1'], 'out')` — хто й коли вийшов.
3. `_f3d_drill_active(ts)`: `'f3d.fire.drill' in env` і модель має метод `_f3d_is_active_at` →
   `bool(env['f3d.fire.drill'].sudo()._f3d_is_active_at(ts))`; інакше `False` (контракт CA-09 до `factory3d_fire_safety`, Q-13).

## 10. Стани й переходи

### 10.1 Сервер (`f3d.access.server.state`)

| З | Подія | В | Хто | Побічні ефекти |
|---|---|---|---|---|
| `offline` | успішний запит (`_poll`, `_sync_*`, «Перевірити з'єднання») | `online` | крон, A, F | `last_contact`, `error_count=0` |
| будь-який | `BioStarError` | `error` | крон, кнопки | `error_count+1`, `last_error`, `next_try_at` (R-16) |
| `error` | успішний запит після `next_try_at` | `online` | крон | курсор продовжує з місця зупинки |
| будь-який | `neutralize.sql` | `offline` | адміністратор БД | `session_id=NULL` |

`stale` — не стан, а ознака (`online`, але без контакту > 3 інтервалів).

### 10.2 Подія (`process_state`, `attendance_action`)

`new` → `done` (конвеєр R-04, будь-який `attendance_action`, крім `future`); `new` → `new` (`future`, до `ts ≤ now`);
`new` → `error` (виняток у savepoint, напр. `ValidationError` стандарту відміток); `error` → `done`/`error`
(«Обробити повторно», M-13). `done` → `done` при повторній обробці без повторних дій з відміткою (M-05
`action_reprocess`). Подія ніколи не видаляється вручну (лише R-20 крок 1).

### 10.3 Картка (`state`, `sync_state`)

| З | Дія | В (`state`) | `sync_state` |
|---|---|---|---|
| `draft`, `returned` | «Видати» | `active` | `pending` → `synced`/`error` (`write_enabled`) або `local` |
| `active` | «Заблокувати» (причина) | `blocked` | те саме |
| `blocked` | «Розблокувати» | `active` | те саме |
| `active`, `blocked` | «Повернути» | `returned` (відвідувача → пул) | те саме |
| `active`, `blocked` | «Втрачена» | `lost` | `pending`/`local` (операція `block`) |
| будь-який | «Позначити синхронізованим» | без змін | `local`/`error` → `synced` |
| будь-який | «Повторити запис» | без змін | `local`/`error` → `pending` → … |

### 10.4 Відвідувач (`state`)

| З | Подія / дія | В | Ефекти |
|---|---|---|---|
| `draft` | «Очікується» / `f3d_visitor_register` | `expected` | картка з пулу, користувач BioStar (R-14 крок 2) |
| `expected` | прохід периметра `in` / «Прийшов» | `on_site` | `arrived_at`, `present`, зона |
| `on_site` | прохід периметра `out` / «Вийшов» | `left` | `left_at`, `present=False` |
| `left` | прохід `in` до `date_to + 1 год` | `on_site` | повторний вхід |
| `expected`, `on_site`, `left` | «Закрити» / R-20 крок 3 | `closed` | картка повертається; R-20 → `overdue` |
| `draft`, `expected` | «Скасувати» | `cancelled` | картка повертається |

### 10.5 Двері (`state`) — R-10; працівник (`f3d_access_present`, зона) — R-08, R-17, R-07 крок 6

## 11. Обробка помилок

1. **BioStar недоступний** (з'єднання, тайм-аут, TLS, 5xx): сервер `error`, пауза R-16, курсор не рухається, події
   за весь простій приходять після відновлення одним або кількома прогонами (AC-08, ТК-06). Кнопки показують
   текст помилки (`display_notification`, `danger`), крон не падає (інші сервери обробляються).
2. **Сесія прострочена / BioStar перезапущено**: 401 або `Response.code "10"/"11"` → повторний `login()`; невірні
   облікові дані (`"101"`) → `error` з текстом «Невірний логін або пароль BioStar (код 101)», без пароля в тексті
   й логах (AC-03, AC-58).
3. **Помилка на середині пагінації**: нічого з прогону не зберігається, курсор не рухається; наступний прогін
   повторює вікно (R-11 крок 5).
4. **Дублікати**: повторні рядки (перекриття, повтор вікна 24 год, майстер «Опитати період») — `UNIQUE(server_id,
   biostar_id)` і попередній `search_read`; лічильник `duplicates` (AC-07).
5. **Невалідні рядки** (немає `id`, `datetime`, нечисловий код, `biostar_id` поза `BSID_RE`): пропуск + WARNING,
   `invalid` (R-01).
6. **Застарілі (stale) дані**: `stale` на сервері після 3 інтервалів без контакту; пристрої — `status='unknown'`
   після 2 невдалих синхронізацій; переглядач отримує `access.server.stale`.
7. **Запізнілі події** (старіші за останню оброблену подію людини): `attendance_action='late'`, ні відміток, ні зони
   (A-26); виправлення — майстер M-13 «Обробити повторно» після ручної правки відміток HR.
8. **Стандартні обмеження відміток** (`_check_validity`: друга відкрита відмітка, перетин інтервалів;
   `check_out < check_in`): виняток у savepoint події → `process_state='error'`, `error_message` = текст Odoo
   («Cannot create new attendance record for …»); решта пакета обробляється (AC-34).
9. **Часові пояси**: збереження — UTC; локальна доба — tz працівника (R-15); перехід на зимовий час 25.10.2026 не
   змінює порядок подій (UTC), R-07 рахує кінець графіка в tz дня входу.
10. **Подвійні відмітки кіоск + СКУД** (компанія має `attendance_kiosk_mode='barcode_manual'`): R-04 крок 3а
    прив'язує прохід до відкритої відмітки будь-якого режиму в межах `dup_window_min`; рекомендація ARCH §3 —
    вимкнути кіоск для працівників зі СКУД.
11. **Запис у BioStar** (картки, відвідувачі): помилка → `sync_state='error'` з текстом відповіді, локальний стан
    лишається, крон повторює до `card_sync_max_attempts`; емулятор → 405 (AC-41, ТК-08).
12. **Немає опційних модулів**: без `factory3d_viewer` — немає шини й виклику провайдера; без `factory3d_telemetry`
    — немає сигналів; без `factory3d_fire_safety` — `_f3d_drill_active` = False. Жодного винятку (AC-52, AC-53).
13. **Невідомий користувач, пристрій, двері**: подія зберігається з `raw_*`; `unknown_user=True`; без дверей —
    напрямок `none`; адміністратор бачить фільтр «Нерозпізнані» і `unlinked_count` на сервері.
14. **Двері без зон** (нові з синхронізації): проходи лише в журналі; `doors_without_zone` на сервері.
15. **Конкурентне опитування** (крон + кнопка): `FOR UPDATE NOWAIT` — друге опитування пропускається / `UserError`.

## 12. Acceptance Criteria

Формат: Given / When / Then; тип: **UT** (юніт-тест, §13.1), **TC** (стенд на емуляторі, §13.2), **MAN** (вручну).
Фікстури (`emp_a`, `FakeBioStar`, `make_row`…) — §13.1. Час — `freeze_time` (UTC). Діапазони — за ARCH §6:
W1 AC-01…AC-14, W2 AC-15…AC-38, W3 AC-39…AC-48, W4 AC-49…AC-69.

| ID | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given `factory3d.base.environment='test'`; When створюємо сервер з `url` ∈ {`ftp://x`, `https://iot-sim:8443/api?x=1`, `javascript:alert(1)`} → `ValidationError`; `url='https://iot-sim:8443/'` → збережено `https://iot-sim:8443`; `timeout_connect_s=0` → помилка обмеження. Given `environment='prod'`; When `verify_ssl=False` або `url='http://iot-sim:8081'` → `ValidationError` з текстами M-01 | UT |
| AC-02 | FR-01, FR-19 | Given `read_enabled=False`, `FakeBioStar` з 36 користувачами й 5 пристроями; When `user_f3d_admin` → `action_test_connection()`; Then `state='online'`, `users_total=36`, `devices_total=5`, `[c[0] for c in fake.calls]` = `['login','list_users_total','list_devices','logout']`, `session_id` сервера не змінився, результат — `display_notification` `type='success'` з «користувачів 36, пристроїв 5». When `user_admin` (без F) → `AccessError` | UT + TC (ТК-02) |
| AC-03 | FR-01, FR-16 | Given `fake.login` кидає `BioStarAuthError(401,'101','Failed to login for invalid username or password')`, пароль `test-pass`; When `action_test_connection()`; Then повідомлення `type='danger'`, `state='error'`, `error_count=1`, `'101' in last_error`, `'test-pass' not in last_error`, жоден рядок логу (`assertLogs` рівня DEBUG логерів `odoo.addons.factory3d_access`) не містить `test-pass` | UT |
| AC-04 | FR-05 | Given `BioStarClient` з мок-`http` (`requests.Session`): `login` → 200 + `bs-session-id: s1`; When `list_devices()`; Then запит має заголовок `bs-session-id: s1`. Given відповідь `401 {"Response":{"code":"10"}}`, далі `login` → `s2`, далі 200; Then рівно 2 `POST /api/login`, повторний запит із `s2`, результат повернуто. Given дві 401 поспіль після повторного входу; Then `BioStarAuthError`, рівно 2 входи (без циклу) | UT |
| AC-05 | FR-05 | When `client.search_events(since=2026-10-12 06:57:10, until=07:05:30, limit=500, offset=0)`; Then тіло `POST /api/events/search` дорівнює JSON §7.2 (`assertEqual` dict). `hint="H1"`, `offset=None` → у `Query` є `"hint": "H1"`, немає `offset`. Given `page_size=2`, fake з 5 рядками; When `server._poll()`; Then `fake.search_calls` має `offset` 0, 2, 4, створено 5 подій | UT |
| AC-06 | FR-05 | Given `freeze_time('2026-10-12 07:00:30')`, курсор порожній, fake з рядками до 06:59:10Z; When `_poll()`; Then перший виклик `since=2026-10-11 07:00:30`, `until=2026-10-12 07:05:30`; `last_event_ts=06:59:10`; наступний `_poll()` (07:01:30) — `since=06:57:10`. Given рядок `datetime=07:03:00Z` (майбутній); Then подія збережена з `attendance_action='future'`, `process_state='new'`, `last_event_ts=07:00:30` (не 07:03) | UT |
| AC-07 | FR-05 | Given ті самі 4 рядки у fake; When `_poll()` двічі; Then 4 події `f3d.access.event`; другий прогін `last_poll_new=0`, `last_poll_rows=4`; `_f3d_ingest_rows` повертає `duplicates=4`; ручне `create` з тим самим `(server_id, biostar_id)` → `IntegrityError` | UT |
| AC-08 | FR-05, FR-16 | Given `fake.fail_always = BioStarError(None,None,'ConnectionError: refused')`, `freeze_time` T; When `_cron_poll()` у T, потім щоразу в `next_try_at + 1 с`; Then `error_count` 1…6, паузи `next_try_at − час прогону` = 60, 120, 240, 480, 600, 600 с; виклик `_cron_poll()` до `next_try_at` не звертається до fake; `last_event_ts` незмінний. When помилку знято і 12 рядків за час простою; Then `state='online'`, `error_count=0`, створено 12 подій, `since` = курсор − 120 с | UT + TC (ТК-06) |
| AC-09 | FR-05 | Given `page_size=2`, `max_pages_per_run=2`, 7 рядків; When `_poll()`; Then створено 4, `last_poll_more=True`, `last_event_ts` = `datetime` 4-го рядка; When `_poll()` ще раз; Then подій 7 (дублікати перекриття відсіяно) | UT |
| AC-10 | FR-06 | When `classify(c)` для c ∈ {4102, 4100, 4867, 4865, 4096, 5120, 4352, 6400, 6401, 6402, 6403, 6404, 6405, 6406, 6407, 20480, 20736, 20992, 21248, 21504, 21760, 26368, 12544, 15104, 0, 99999}; Then відповідно R-09 (`pass/card`, `pass/id_face`, `pass/face`, `pass/finger`, `pass/other`, `fail`, `fail`, `denied/other`, `access_group`, `disabled`, `expired`, `blacklist`, `apb`, `timed_apb`, `scheduled_lock`, `door/unlocked`, `locked`, `open`, `closed`, `forced`, `held`, `alarm/fire`, `system`, `system`, `other`, `other`) | UT |
| AC-11 | FR-02 | Given fake API-04: 5 рядків P-10 (`status "1"`, крім 5390005 `"0"`) + `5390006`; When `_sync_devices()`; Then 5 data-пристроїв оновлено (`ACR-SRV.status='offline'`, решта `online`, `device_type='BioEntry W3'`, `name` незмінні), створено `BS-5390006` (`direction='in'`, без зони); `devices_total=6`. Given `list_devices` кидає помилку двічі; Then `sync_fail_count=2`, `status='unknown'` | UT + TC (ТК-02) |
| AC-12 | FR-03 | Given fake API-05: двері 1–5 P-10 (`TURN-1 open_duration "5"`) + двері `6` з `entry_device_id 5390006`; When `_sync_devices()`; Then `TURN-1.open_duration_s=5`, зони дверей 1–5 незмінні, створено `BSD-6` з `entry_device_id=BS-5390006`, без зон; `server.doors_without_zone=1` | UT |
| AC-13 | FR-04 | Given fake API-03 (5 рядків): `TSTA1` (бейдж `emp_a`; `face_count "1"`, `photo "iVBOR…"`), `OPTSTC` (`emp_c.f3d_code='OP-TST-C'`, без бейджа), `ALIAS1` (`emp_d.f3d_alias`), `"1"` Administrator, `ZZZ9` з `name` = ім'я `emp_a`; наявний зв'язок `OLD9`; When `_sync_users()`; Then `TSTA1→emp_a` `barcode` з `has_face=True`, `OPTSTC→emp_c` `code`, `ALIAS1→emp_d` `alias`, `"1"` і `ZZZ9` — `none` (за ім'ям не зв'язано), `OLD9.in_biostar=False`; результат `{'total': 5, 'unlinked': 2, 'missing': 1, …}`; жодне поле зв'язку не містить `iVBOR` | UT + TC (ТК-02) |
| AC-14 | FR-02, FR-03 | When пристрій `code='acr-x'` / `biostar_id='53 9'` → `ValidationError`; другий пристрій `code='ACR-IN'` або той самий `biostar_id` на сервері → `IntegrityError`; двері лише з `zone_from_id` → `ValidationError`; `is_perimeter` без `zone_to_id` → `ValidationError`; `dwell_min=2000` → помилка; `entry_device_id` іншого сервера → `ValidationError` | UT |
| AC-15 | FR-07 | Given `emp_a` без відміток, `freeze_time('2026-10-12 03:53')`; When fake дає `make_row(1,'2026-10-12T03:52:00.00Z',4102,'TSTA1',tna='1')` і `_poll()`; Then одна `hr.attendance`: `check_in=2026-10-12 03:52:00`, `check_out=False`, `in_mode='biostar'`, `f3d_in_event_id`=подія, `f3d_in_device_id=device_acr_in`, `date=2026-10-12`; подія `attendance_action='checked_in'`, `process_state='done'`, `direction='in'`, `door_id=door_turn_1`, `is_perimeter=True` | UT + TC (ТК-03) |
| AC-16 | FR-07, FR-17 | Given `emp_a` з відкритою `manual` відміткою `check_in=03:52:00`, `present=False`; When вхід о 03:52:10; Then відміток 1, `attendance_action='attached'`, `f3d_in_event_id` заповнено, `in_mode='manual'`, `check_in=03:52:00`. Given `dup_window_min=20`, `emp_b` з `manual` 03:52, `present=True` з тієї ж доби, вхід о 04:20 → `duplicate`, `apb_suspect=True`, відміток 1 | UT + TC (ТК-03) |
| AC-17 | FR-07, FR-09 | Given AC-15 виконано; When вхід `TSTA1` о 03:55:00; Then відміток 1, подія `duplicate`, `apb_suspect=True`, `attendance_id` = відкрита | UT |
| AC-18 | FR-07 | Given AC-15; When `make_row(…,'2026-10-12T12:42:05.00Z',4102,'TSTA1',tna='2')`; Then `check_out=12:42:05`, `out_mode='biostar'`, `f3d_out_event_id`, `f3d_out_device_id=device_acr_in`; подія `checked_out`, `direction='out'` | UT + TC (ТК-04) |
| AC-19 | FR-07 | Given входи/виходи R-06 (03:52 in, 08:31 out, 08:58 in, 12:42 out); When `merge_gap_min=0`; Then 2 відмітки `(03:52, 08:31)`, `(08:58, 12:42)`. When `merge_gap_min=45` (окремий працівник, ті самі часи); Then 1 відмітка `(03:52, 12:42)`, `out_mode='biostar'`, подія 08:58 — `merged` | UT |
| AC-20 | FR-07, FR-18 | Given відкриті відмітки чотирьох працівників з календарем тесту і `check_in` з таблиці R-07; When `freeze_time('2026-10-28 02:00')`, `_cron_housekeeping()`; Then `check_out` = 12:30:00Z (12.10), 13:30:00Z (26.10), 14:10:00Z, 07:00:00Z (17.10); `out_mode='technical'`, `f3d_closed_by_rule=True`, у чаттері відмітки — текст R-07; у працівника `present=True` з `last_in=check_in` → `present=False`. Given `stale_close_enabled=False`; Then відмітки відкриті | UT |
| AC-21 | FR-07 | Given `emp_a` без відкритої відмітки; When вихід 12:42; Then `no_open`, відміток 0, `present=False`, `apb_suspect=True`. Given відкрита `check_in=10:00Z`; When вихід о 09:00Z (новіший за останню подію людини); Then `no_open`, `error_message="Вихід раніше за вхід відмітки"`, відмітка відкрита | UT |
| AC-22 | FR-07, FR-08 | Given AC-15; When `ACR-ELEC` 4102 `TSTA1` о 06:51Z; Then відмітка та сама й відкрита, подія `attendance_action='none'`, `employee.f3d_access_zone_id=Z-ELEC` | UT + TC (ТК-05) |
| AC-23 | FR-07 | Given вхід 2026-10-12 19:00Z, вихід 2026-10-13 03:00Z; Then відмітка закрита подією (`checked_out`, 8 год). Given вхід 03:52Z 12.10 без виходу, вихід 2026-10-13 12:40Z; Then стара відмітка `check_out=2026-10-12 12:30:00`, `f3d_closed_by_rule=True`, подія `no_open` | UT |
| AC-24 | FR-07 | Given оброблено вхід 03:52 і вихід 12:42; When наступне опитування приносить вхід 10:00Z (новий `biostar_id`); Then подія `late`, `process_state='done'`, відміток 1 закрита, `present=False` незмінно | UT |
| AC-25 | FR-07 | Given `freeze_time('2026-10-12 03:50')`, рядок 03:53:00Z (у межах `future_tolerance_s`); When `_poll()`; Then подія `future`, `process_state='new'`, відміток 0. When `freeze_time('2026-10-12 03:54')`, `_poll()`; Then подія `checked_in`, `check_in=03:53:00` | UT |
| AC-26 | FR-07 | When `parse_bs_dt` для `2026-10-12T03:52:10.00Z`, `…10.000Z`, `…10Z`, `…10+00:00` → `datetime(2026,10,12,3,52,10)`; `'x'` → `ValueError`; `local_date(2026-10-12 21:30)='2026-10-13'`; `to_local_str(2026-10-25 01:30)='2026-10-25 03:30'`; `schedule_end_utc(cal, 2026-10-12, tz)=12:30`, `(…, 2026-10-26)=13:30`, `(…, 2026-10-17)=None`; `fmt_bs_dt(2026-10-12 03:52:10)='2026-10-12T03:52:10.000Z'` | UT |
| AC-27 | FR-08 | Given `emp_a.f3d_home_zone_id=Z-CUT`, `emp_b` без домашньої; When вхід обох; Then `emp_a`: `present`, `Z-CUT`, `zone_since=ts`, `last_in=ts`; `emp_b`: `Z-ASM`; подія `presence_changed=True`. When вихід `emp_a`; Then `present=False`, зона порожня, `last_out=ts` | UT + TC (ТК-03) |
| AC-28 | FR-08 | Given `emp_a` у `Z-CUT`; When `ACR-ELEC` о 06:51Z; Then `Z-ELEC`, `f3d_access_zone_door_id=door_elec`; `_cron_zone_dwell()` о 07:20Z → `Z-ELEC`; о 07:21:01Z → `Z-CUT`, двері порожні. Given `door_elec.dwell_min=0`; Then о 09:00Z ще `Z-ELEC`. Given `emp_b` не на території; When `ACR-PAINT`; Then `present=True`, `Z-FAC`, `apb_suspect=True` | UT + TC (ТК-05) |
| AC-29 | FR-08 | Given 2 працівники й 1 відвідувач (`on_site`) у `Z-CUT`, 1 працівник поза територією з `Z-CUT` домашньою; Then `zone_z_cut.f3d_people_now=3`, `len(f3d_people_employee_ids)=2`, `len(f3d_people_visitor_ids)=1`; `action_view_people()` → `res_model='f3d.access.presence'`, `domain=[('zone_id','=',zone.id)]` | UT |
| AC-30 | FR-08, FR-12 | Given AC-29; When `user_security` → `f3d.access.presence.search_read([])`; Then 3 рядки: `id` працівників парні, відвідувача непарний, `code` відвідувача `V-<id>`, відсутній працівник відсутній у представленні; `user_f3d` → `AccessError` | UT |
| AC-31 | FR-09 | Given події `TSTA1`: 6405, 6401, 5120 і прохід з `apb_suspect=True`; When домени фільтрів з `view_f3d_access_event_search` (`filter_denied`, `filter_apb`); Then «Відмови» = 3, «Антипрохід» = 2 (6405 і `apb_suspect`); жодна з відмов не створила відмітку | UT + TC (ТК-05) |
| AC-32 | FR-09, FR-04 | Given подія `user "1"`, ACR-SRV; Then `unknown_user=True`, створено зв'язок `"1"` `match='none'`, фільтр «Нерозпізнані» = 1, відміток 0. Given подія `raw_user_id='OPTSTC'` без зв'язку, ACR-IN `tna "1"`; Then зв'язок `match='code'` → `emp_c`, `checked_in` | UT |
| AC-33 | FR-03 | Given `door_turn_1` `unknown`; When події 20480 (03:52:00), 20992 (03:52:01), 21248 (03:52:06), потім запізніла 20992 (03:52:01, новий id); Then стан `unlocked → open → closed`, запізніла ігнорується. When 21504 → `forced`, `alarm=True`; 21248 → `closed`, `alarm=False`. When 26368 без дверей; Then усі 5 дверей `alarm=True`, `alarm_reason='fire'`; `user_security.action_ack_alarm()` → `alarm=False`; `user_security` `write({'name': 'X'})` → `AccessError` | UT + TC (ТК-10) |
| AC-34 | FR-19 | Given `emp_a` з закритою ручною відміткою 03:00–05:00Z; When вхід о 04:00Z і в тому ж опитуванні вхід `emp_b`; Then подія `emp_a` `process_state='error'`, `error_message` містить `Cannot create new attendance record`, подія `emp_b` `done`. When ручну відмітку видалено і майстер `reprocess`, `only_errors=True`; Then подія `done`, `checked_in`. When майстер `repoll` при `read_enabled=False` → `UserError`; при `True` → `fake.search_calls[-1]` має `since=date_from`, `until=date_to` | UT |
| AC-35 | FR-20 | Given A вхід 03:40Z; B вхід 03:45Z; C вхід 03:50Z, вихід 04:30Z; D вхід 2026-10-09 03:40Z без виходу; When `f3d_on_site_at(ts)` для `ts` = 03:45Z, 04:00Z, 04:40Z; Then `{A,B}`, `{A,B,C}`, `{A,B}`; D — ніколи (старіше `max_shift_h`); повернуто ключі `employees`, `visitors`, `ts` | UT |
| AC-36 | FR-20 | Given проходи TURN-1 in/out і DOOR-ELEC in між t0 і t1; When `f3d_passes_between(t0, t1, ['TURN-1'], 'out')`; Then лише виходи TURN-1 за зростанням `ts`; без фільтрів — усі `pass` у вікні, включно з DOOR-ELEC | UT |
| AC-37 | FR-20 | Given `patch.object(F3dAccessEvent, '_f3d_drill_active', return_value=True)`, `emp_a` з відкритою відміткою і `present`; When вихід TURN-1; Then `attendance_action='drill'`, відмітка відкрита, `present=False`; When вхід; Then `drill`, відміток 1 відкрита, `present=True`. `env['f3d.fire.passage.source.access']._f3d_on_site(ts)` → `[{'employee_id': emp_a.id, 'since': …, 'point': 'TURN-1'}]`; `_f3d_passages(t0, t1)` — словники з ключами `employee_id, ts, point, direction` | UT |
| AC-38 | FR-18 | Given `keep_days=90`, події з `ts` = now − 91 і now − 89 діб; відвідувач `expected` з `date_to` = now − 2 год і карткою; картка `returned` з `returned_at` = now − 91 діб і `visitor_id`; відвідувач `closed` з `date_to` = now − 91 діб; `read_enabled=True`; When `_cron_housekeeping()`; Then перша подія видалена, друга є; відвідувач `closed`, `overdue=True`, картка `returned` у пулі; `fake.search_calls[-1].since` = now − 24 год; картка `visitor_id=False`; старий відвідувач видалений | UT |
| AC-39 | FR-10 | When картка `number='AB12'` → `ValidationError`; дубль номера на сервері → `IntegrityError`; `holder_type='employee'` без працівника, `pool` з відвідувачем, `blocked` без причини → `ValidationError` з текстами M-06 | UT |
| AC-40 | FR-10, FR-16 | Given `write_enabled=False`, картка `emp_a` `draft`; When `action_issue()`; Then `state='active'`, `sync_state='local'`, `pending_op='issue'`, у чаттері текст про стоп-кран, `fake.calls == []`. When `action_mark_synced()`; Then `synced`, `pending_op=False` | UT + TC (ТК-08) |
| AC-41 | FR-10 | Given `write_enabled=True`, картка `active` з `biostar_card_id='7'`; When `block_reason='Звільнення'`, `action_block()`; Then `fake.calls[-1] == ('update_user_cards', 'TSTA1', [{'id': '7', 'is_blocked': 'true'}])`, `sync_state='synced'`. Given `fake.write_status=405`; Then `sync_state='error'`, `sync_error='Метод не підтримується сервером BioStar (405)'`, `state='blocked'`, `sync_attempts=1` | UT + TC (ТК-08) |
| AC-42 | FR-10 | Given `write_enabled=True`, нова картка `12345678` (`csn`) `emp_a`; When `action_issue()`; Then виклики `('create_card','12345678',0)`, `('update_user_cards','TSTA1',[{'id':'9','is_blocked':'false'}])`, `biostar_card_id='9'`. Given `update_user_cards` падає; Then `biostar_card_id='9'` збережено, `error`; `action_retry_sync()` → `create_card` удруге не викликано | UT |
| AC-43 | FR-10 | Given `write_enabled=True`, картки `error` з `sync_attempts` 3 і 10 (`card_sync_max_attempts=10`); When `_cron_card_sync()`; Then повторено лише першу. Given `write_enabled=False`; Then `fake.calls == []` | UT |
| AC-44 | FR-11 | Given відвідувач `draft`, картка пулу `555` `draft`; When `action_expect()`; Then `expected`, картка `holder_type='visitor'`, `state='active'`; `biostar_user_id='V-T1'` вручну → зв'язок `match='visitor'`; When вхід `V-T1` TURN-1 `tna "1"`; Then `on_site`, `arrived_at`, `present`, `Z-ASM`; вихід → `left`; `action_close()` → `closed`, картка `returned`, `holder_type='pool'` | UT + TC (ТК-07) |
| AC-45 | FR-11 | Given AC-44 до виходу і `allowed_zone_ids=[Z-OFFICE]`; When прохід `V-T1` ACR-ELEC; Then `zone_violation=True`, `violation_count=1`, кількість `hr.attendance` не змінилась, `attendance_action='not_employee'`. Given відвідувач `closed`; When прохід; Then `error_message` «Відвідувач у стані «Закрито»…», стан не змінився | UT + TC (ТК-07) |
| AC-46 | FR-11 | Given `write_enabled=True`; When `action_expect()`; Then `biostar_user_id='V-%d' % id`, `fake.calls` містить `('create_user', 'V-%d', name, date_from, date_to + 1 год, '1')`, зв'язок `visitor`, `sync_state='synced'`. Given `fake.write_status=405`; Then `sync_state='error'`. Given `write_enabled=False`; Then `local`, викликів немає. When `biostar_user_id='TSTA1'` (зв'язок працівника) → `ValidationError` | UT + TC (ТК-07) |
| AC-47 | FR-11 | Given пул карток `600`, `555`; When `user_security` → `f3d_visitor_register({'name':'Водій','host_employee_id':…,'origin':'yard','origin_ref':'YV/2026/0012'})`; Then `expected`, `card_id.number='555'`, `origin='yard'`. Given пул порожній; Then `expected`, без картки, у чаттері «Вільних карток у пулі немає» | UT |
| AC-48 | FR-11 | When `date_to ≤ date_from` або тривалість 8 діб → `ValidationError`; новий відвідувач без `date_to` → `date_to = date_from + 8 год`; `unlink()` у стані `expected` → `UserError`, у `draft` — видалено | UT |
| AC-49 | FR-14 | Given `payload={'employees': {'OP-TST-A': {'name':'А','present':False}, 'OP-TST-B': {'name':'Б','present':True}}, 'zones': {'Z-CUT': {'name':'Розкрій'}}}`, `emp_a` у `Z-CUT` з 06:52, `emp_b` поза; When `env['f3d.viewer.provider.access']._f3d_viewer_collect(payload, ctx)` (`ctx` з `now`, `today`); Then `employees['OP-TST-A']` = `present=True`, `zone='Z-CUT'`, `zone_since='2026-10-12 06:52'`, `last_event` з ключами `ts, door, direction, type`; `OP-TST-B` → `present=False`, `zone=None`; `zones['Z-CUT']['people_now']=1`; нових ключів у `employees` немає | UT + TC (ТК-09) |
| AC-50 | FR-14, FR-13 | Given AC-49 + відвідувач на території + подія ACR-PAINT; When як `user_f3d`; Then `access` має ключі R-12 (`updated, server, on_site, today, zones, people, visitors, readers, doors, cards, last_events`), `last_events == []`, у `visitors[0]` немає `name`, рядок «Останній доступ» без « — »; When як `user_security`; Then `last_events` непорожній з `person`, «Останній доступ» = «склад ЛФМ, HH:MM — <ім'я>». Given `payload['infra']['cards']['TURNSTILES']` зі статикою «146 працівників · 3 відвідувачі»; Then замінено на живі рядки | UT |
| AC-51 | FR-14 | Given AC-49 (`emp_a` у `Z-CUT`, `emp_b` поза), `patch={}`, `ctx.changes={'hr.employee': {'OP-TST-A'}, 'f3d.access.door': {'TURN-1'}}`; When `_f3d_viewer_delta(patch, ctx)` (R-12 п. 7, X-87); Then `set(patch) == {'access', 'employees', 'zones', 'infra'}`, `patch['access']` — повний розділ R-12, `patch['employees'] == {'OP-TST-A': {'present': True, 'zone': 'Z-CUT', 'zone_since': …, 'last_event': …}}`, `patch['zones']` має всі активні зони (`Z-CUT.people_now=1`, решта 0), `set(patch['infra']['cards']) == {'TURNSTILES', 'ACCESS'}` з `rows` = `access.cards`; When `ctx.changes={'mrp.production': {'WH/MO/00231'}}`; Then `patch == {}`. Given `patch.object(F3dAccessEvent, '_f3d_bus')`; When опитування з 2 проходами TURN-1 (`emp_a`, `emp_b`); Then `_f3d_bus` викликано по разу з `('hr.employee', {'OP-TST-A','OP-TST-B'})` і `('f3d.access.door', {'TURN-1'})` | UT |
| AC-52 | FR-14 | Given база без `factory3d_viewer` (`'f3d.viewer.event' not in env`); When обробка подій; Then без винятків, `_f3d_bus` повертає `None`; модель `f3d.viewer.provider.access` у реєстрі з `_f3d_sequence=170`, `_f3d_sections=('access',)`, `_f3d_group='factory3d_base.group_f3d_user'` | UT |
| AC-53 | FR-15 | Given `patch.object(F3dAccessTelemetry, '_f3d_signal_model', return_value=fake_signal)`; When опитування з 3 новими подіями на ACR-IN і ACR-ELEC; Then `fake_signal.readings` коди = {`access/readers/ACR-IN/last_event`, `access/readers/ACR-ELEC/last_event`, `access/turnstiles/TURNSTILES/on_site`, `access/events`}, `src='module'`, жоден `text` не містить `TSTA1`. Given `publish_signals=False` або 0 нових подій або `_f3d_signal_model()` → `None`; Then не викликано. Реальні сигнали моста й прийом показань — AC-68 (X-33) | UT |
| AC-54 | FR-16 | Given `user_f3d_admin`; When `res.config.settings` з `f3d_access_page_size=300`, `f3d_access_write_enabled=True` → `execute()`; Then параметри `300`, `True`. `page_size=3000` → `ValidationError`. `fields_get` для `user_admin` (без F) не містить `f3d_access_biostar_password` | UT |
| AC-55 | FR-16 | Given `read_enabled=False`; When `_cron_poll()`, `_cron_sync_users()`, `_cron_sync_devices()`, `_cron_housekeeping()`; Then `fake.calls == []` (господарство без мережевого кроку 4 відпрацьовує). `action_poll_now()`, `action_sync_users()` → `UserError("Опитування BioStar вимкнено стоп-краном factory3d.access.read_enabled.")` | UT |
| AC-56 | FR-16 | Given `BioStarClient(write_enabled=False, http=mock)`; When `create_card`, `update_user_cards`, `create_user`; Then `BioStarWriteDisabled`, `mock.request.call_count == 0` | UT |
| AC-57 | FR-16 | Given сервер з `session_id='s1'`, `state='online'`, картка `pending`, параметри `read/write_enabled=True`, пароль; When `cr.execute(open('data/neutralize.sql').read())`; Then 6 кронів модуля `active=False`, `read_enabled='False'`, `write_enabled='False'`, пароля немає, `session_id` NULL, `state='offline'`, картка `local` | UT |
| AC-58 | FR-16 | Given пароль `S3cr3t!`, сесія `0123abcd-0000-1111-2222-333344445555`; When `login` і 3 запити з логуванням DEBUG; Then у `assertLogs` немає `S3cr3t!` і цієї сесії; `SecretFilter`: `'{"password": "x"}'` → `'{"password": "***"}'`, `'bs-session-id: 0123abcd-…'` → `'bs-session-id: ***'` | UT |
| AC-59 | FR-17 | Given фікстура «копія демо» (§13.1 `make_demo_like()`: 35 працівників Додатка B із бейджами й кодами, 28 РЦ із зонами Додатка C, обладнання `ACCESS`, `TURNSTILES`, 35 відкритих `manual` відміток 2026-10-12 03:40…03:59Z); When `hooks.run_all(env)`; Then звіт `servers=1, devices=5, doors=5, equipment_bound=5, links=35, home_zones=35, from_workcenter=28, from_csv=7, home_zone_missing=0, presence_seeded=35, attendances_touched=0, attendances_total=35`, `migration_state='done'`; `OP-W3.f3d_home_zone_id=Z-RCV-2`, `OP-SAW-1 → Z-CUT`; `device_acr_in.equipment_id.f3d_code='TURNSTILES'` | UT + TC (ТК-01) |
| AC-60 | FR-17 | When `run_all` удруге; Then `links=0, home_zones=0, presence_seeded=0` нових, кількості записів незмінні. Given чиста база (без працівників); Then `migration_state='skipped'`. Given `read_enabled` відсутній і `environment='test'` → `'True'`; наявне `'False'` не перезаписується | UT |
| AC-61 | FR-17 | Given установлений модуль, 2 відмітки `in_mode='biostar'`; When `uninstall_hook(env)`; Then параметрів `factory3d.access.%` немає, `hr.attendance` 2 записи на місці | UT |
| AC-62 | FR-13 | Матриця прав (§13.3 таблиця): для кожної пари (користувач, модель, операція) — дозволено/`AccessError` як у §4.1; `user_security` без `hr.group_hr_user` читає `hr.employee.public` поля `f3d_access_present`, `f3d_access_zone_id` | UT |
| AC-63 | FR-13 | `user_security`: `create` картки `holder_type='employee'` → `AccessError`; `pool` — ок; `write` картки працівника → `AccessError`; `user_admin` — ок. Сервер компанії B невидимий користувачу лише компанії A | UT |
| AC-64 | FR-13 | Поля моделей модуля (`fields_get`) не мають імен із `photo`, `image`, `template`, `document`, `fingerprint_data`; `keep_raw=False` → `raw=False`; `keep_raw=True` → `raw` без `user_id.name`, `user_id.photo_exists`, `hint` | UT |
| AC-65 | FR-12 | Меню з xml-id §3 існують з указаними батьками, `sequence` і групами; `menu_f3d_access.sequence=70`, батько `factory3d_base.menu_f3d_root`; `menu_f3d_access_att_report` під `hr_attendance.menu_hr_attendance_reporting` | UT |
| AC-66 | FR-12 | `get_view` (адміністратор): форма `hr.employee` містить `page[@name='f3d_access']`; форма `hr.attendance` — `f3d_in_event_id`; налаштування — `block[@name='f3d_access_block']`; форма `f3d.zone` — кнопку `action_view_people`; kanban `f3d.access.presence` має `default_group_by="zone_id"`. MAN: ТК-09 крок 1–3 у браузері | UT + MAN |
| AC-67 | FR-14 | Given `patch={'infra': {'cards': {'PV-INV': {'rows': [['Зараз', '468 кВт']]}}, 'totals': {'pv_now': 468}}, 'employees': {'OP-TST-A': {'name': 'А', 'workcenter': 'SAW-1'}}}` (як після energy 150 і `people`), `inf = patch['infra']`, `ctx.changes={'hr.employee': {'OP-TST-A'}}`; When `_f3d_viewer_delta(patch, ctx)` (X-23, X-87); Then `patch['infra'] is inf` (не присвоєно), `patch['infra']['cards']` має `PV-INV` (незмінна), `TURNSTILES`, `ACCESS`; `patch['infra']['totals'] == {'pv_now': 468}`; `patch['employees']['OP-TST-A']` має `name='А'`, `workcenter='SAW-1'` і `present`, `zone`, `zone_since`, `last_event`; `deep_merge` — з `factory3d_viewer.tools.payload` | UT |
| AC-68 | FR-15 | Given установлені `factory3d_access` і `factory3d_telemetry` (міст `factory3d_access_telemetry` установлено автоматично: `ir.module.module` `state='installed'`), 5 пристроїв data; Then є рівно 7 сигналів `access/%` (M-17): 5 `access/readers/<ACR-*>/last_event` (`kind='event'`), `access/turnstiles/TURNSTILES/on_site` (`gauge`, `unit='осіб'`), `access/events` (`event`); у всіх `module='access'`, `origin='module'`, `source_id=False`, `viewer_visible=False`, `create_request=False`, `period_s=60`. When `_f3d_ensure_signals()` удруге; Then `{'created': 0, 'existing': 7}`. When створено `f3d.access.device` з `code='ACR-T9'`; Then з'явився `access/readers/ACR-T9/last_event`. When `env['f3d.signal'].sudo()._f3d_ingest([{'code': 'access/turnstiles/TURNSTILES/on_site', 'ts': now, 'value': 35.0, 'q': 'good'}], src='module')`; Then `accepted=1`, `rejected=[]`, `last_value=35`. When `freeze_time(now + 1 доба)` і `env['f3d.signal']._cron_stale()`; Then статус сигналу не `stale` (без джерела, telemetry R-07) (X-33) | UT |
| AC-69 | FR-12, FR-16 | Given модуль установлено; Then `factory3d_access.menu_f3d_access_settings`: `parent_id` = `factory3d_base.menu_f3d_config`, `sequence=70`, `group_ids` = `factory3d_base.group_f3d_admin`, дія `action_f3d_access_settings` (`res_model='res.config.settings'`, `view_mode='form'`, `target='current'`, `context` з `module='hr_attendance'`); `get_views` форми `res.config.settings` для адміністратора містить `block[@name='f3d_access_block']`; користувач `user_security` (без `group_f3d_admin`) пункту не бачить (`ir.ui.menu` `_visible_menu_ids`) (X-89) | UT |

## 13. План тестування (для Opus)

### 13.1 Юніт-тести (`odoo.tests`, теги `post_install`, `-at_install`, `f3d`, `f3d_access`)

Запуск: `odoo-bin -d f3d_test -i factory3d_access --test-tags /factory3d_access --stop-after-init --without-demo=all`
(чиста база; `factory3d_base` встановлюється залежністю). Мережа в юніт-тестах заборонена: клієнт підмінено.

**`tests/common.py`** — `class AccessCase(TransactionCase)`, `setUpClass`:
- `cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, f3d_no_commit=True))`;
- параметри: `read_enabled='True'`, `write_enabled='False'`, `biostar_password='test-pass'`, `merge_gap_min='0'`,
  `dup_window_min='20'`, `keep_raw='False'`, `publish_signals='True'` (через `tools.params.set_param`);
- `cls.cal` = `resource.calendar` «Тест 07:00–15:30», `tz='Europe/Kyiv'`, рядки як `plant/odoo_flows.py:step_calendar`
  (пн–пт 7–11.5 `morning`, 12–15.5 `afternoon`);
- зони: `cls.z = {code: env.ref('factory3d_base.zone_' + code.lower().replace('-', '_'))}` для `Z-KPP, Z-ASM, Z-CUT,
  Z-FG, Z-ELEC, Z-POST, Z-CHG, Z-FAC, Z-MAINT, Z-HW, Z-OFFICE`;
- `cls.server = env.ref('factory3d_access.server_biostar_sim')`; пристрої/двері — `env.ref('factory3d_access.device_acr_in')`…
  `door_turn_1`, `door_elec`, `door_chg`, `door_paint`, `door_srv`;
- працівники (sudo, `resource_calendar_id=cls.cal`, `tz='Europe/Kyiv'`): `emp_a` («Тест А», `barcode='TSTA1'`,
  `f3d_code='OP-TST-A'`, `f3d_home_zone_id=Z-CUT`), `emp_b` («Тест Б», `TSTB2`, `OP-TST-B`, без домашньої),
  `emp_c` («Тест В», без бейджа, `OP-TST-C`), `emp_d` («Тест Г», без бейджа, `f3d_code='OP-TST-D'`, `f3d_alias='ALIAS1'`);
  зв'язки `TSTA1→emp_a`, `TSTB2→emp_b` (`match='barcode'`);
- користувачі (`mail.mail_notification`-незалежні, `new_test_user`): `user_plain` (`base.group_user`), `user_f3d`
  (+ `factory3d_base.group_f3d_user`), `user_security` (+ S), `user_admin` (+ A), `user_hr` (+ H), `user_f3d_admin` (+ F);
- `class FakeBioStar`: атрибути `users`, `devices`, `doors` (списки рядків API-03/04/05), `events` (рядки API-06),
  `calls` (список кортежів), `search_calls` (dict `since/until/limit/offset/hint`), `session_id`, `fail_always`
  (виняток або `None`), `fail_times` (скільки наступних викликів падають), `write_enabled`, `write_status`
  (`None`/405), `next_card_id` (`'9'`); методи з тими самими сигнатурами, що `BioStarClient` (§7.1);
  `search_events` фільтрує `events` за `since ≤ datetime ≤ until`, сортує за `datetime` зростанням і повертає
  `rows[offset:offset+limit]` (або після рядка з `hint`) і `total`; запис при `not write_enabled` →
  `BioStarWriteDisabled`, при `write_status=405` → `BioStarError(405, …)`;
- `patch_client(fake)` — контекстний менеджер `patch.object(type(env['f3d.access.server']), '_get_client', lambda self: fake)`;
- `make_row(id, dt, code, user=None, device='5390001', door='1', tna='')` → dict формату §7.2 (`door_id` — список);
- `poll(at)` — `with freeze_time(at): server._poll()`;
- `make_demo_like()` — 35 працівників з бейджами/кодами/іменами Додатка B base, 28 `mrp.workcenter` (`code`=`f3d_code`
  РЦ, `f3d_zone_id` за base Додатком C), 2 `maintenance.equipment` (`f3d_code` `ACCESS`, `TURNSTILES`), 35 відкритих
  `hr.attendance` (`in_mode='manual'`, `check_in = 2026-10-12 03:(40 + det(code, mod=20)):00`);
- `tests/fixtures/events_shift.json` — 152 рядки API-06 за 2026-10-12 (генерує `tests/fixtures/gen_events_shift.py`,
  Odoo його не вантажить): для 35 кодів Додатка B прохід ACR-IN о `03:(40+det(code,mod=20)):00Z`, код 4102, якщо
  `det(code) % 2 == 0`, інакше 4867 (ПРИПУЩЕННЯ: iot_sim R-28 «чергуються за det»), `tna_key "1"`, двері 1, плюс
  20480 (+0 с), 20992 (+1 с), 21248 (+6 с) дверей 1 → 140 рядків; OP-W1 ACR-ELEC 06:51:00Z, OP-W2 ACR-PAINT 07:20:00Z,
  `"1"` ACR-SRV 08:05:00Z, кожен + 3 події своїх дверей → 12 рядків; `id` "1"…"152" за зростанням `datetime`;
  `det` — FNV-1a 32 як `plant/odoo_demo.py:det`.

| Файл / клас | Тести | AC | Фікстури | Що саме assert |
|---|---|---|---|---|
| `test_client.py::TestClient` | `test_login_header`, `test_relogin_once`, `test_auth_error_no_loop`, `test_search_body_offset`, `test_search_body_hint`, `test_write_disabled_no_network`, `test_http_405`, `test_invalid_json`, `test_response_code_nonzero` | AC-04, AC-05, AC-56 | `unittest.mock.MagicMock(spec=requests.Session)` з чергою відповідей | заголовки, кількість `login`, тіло JSON (`assertEqual`), класи винятків, `call_count == 0` |
| `test_client.py::TestSecretFilter` | `test_password_masked`, `test_session_masked`, `test_logs_clean` | AC-58 | `assertLogs('odoo.addons.factory3d_access', 'DEBUG')` | відсутність секретів у `output` |
| `test_server.py::TestServerConstraints` | `test_url_rules`, `test_verify_ssl_env`, `test_timeouts` | AC-01 | `environment` `test`/`prod` | `ValidationError`/`IntegrityError` (`mute_logger('odoo.sql_db')` + `cr.savepoint()`) |
| `::TestConnection` | `test_ok_separate_session`, `test_auth_fail_no_secret`, `test_requires_f3d_admin` | AC-02, AC-03 | `FakeBioStar` | поля сервера, `fake.calls`, тип повідомлення, `AccessError` |
| `::TestPoll` | `test_window_first_and_next`, `test_future_row_cursor`, `test_dedup`, `test_backoff_sequence`, `test_recovery_after_outage`, `test_max_pages_more`, `test_pagination_offsets`, `test_lock_skip` | AC-05…AC-09 | `make_row`, `freeze_time` | `search_calls`, `last_event_ts`, лічильники, `next_try_at − now` |
| `::TestCodeValidation` | `test_device_codes`, `test_door_rules` | AC-14 | — | винятки |
| `test_sync.py::TestSync` | `test_sync_devices`, `test_device_fail_unknown`, `test_sync_doors_new`, `test_sync_users_matching`, `test_no_name_match`, `test_biometrics_not_stored`, `test_missing_users` | AC-11…AC-13 | fake з рядками API-03/04/05 (`fixtures/users.json`, `devices.json`, `doors.json` + додаткові рядки) | поля зв'язків/пристроїв/дверей, лічильники |
| `test_events.py::TestClassify` | `test_table` (параметризований `subTest`) | AC-10 | — | словник `classify` |
| `::TestJournal` | `test_late_event`, `test_future_then_processed`, `test_filters_denied_apb`, `test_unknown_user`, `test_immediate_match`, `test_door_states`, `test_fire_alarm_all_doors`, `test_ack_alarm_rights`, `test_validation_error_isolated`, `test_reprocess_wizard`, `test_repoll_wizard` | AC-24, AC-25, AC-31…AC-34 | `emp_a`, `emp_b`, двері data | `attendance_action`, `process_state`, стан дверей, `search_count` за доменами фільтрів (`safe_eval` домену з `env.ref('…view_f3d_access_event_search')` arch через `etree`) |
| `test_attendance.py::TestAttendance` | `test_check_in`, `test_attach_demo`, `test_duplicate_apb`, `test_check_out`, `test_lunch_merge_off_on`, `test_stale_close_table`, `test_stale_close_disabled`, `test_out_without_open`, `test_out_before_in`, `test_internal_door_no_attendance`, `test_night_and_long`, `test_dates_helpers` | AC-15…AC-23, AC-26 | `freeze_time`, `cls.cal` | поля `hr.attendance` (точні `datetime`), кількість відміток, `message_ids` (текст R-07) |
| `test_presence.py::TestPresence` | `test_home_zone_and_fallback`, `test_exit_clears`, `test_internal_zone_and_dwell`, `test_dwell_zero`, `test_internal_without_entry`, `test_people_now`, `test_presence_view_rows`, `test_on_site_at`, `test_passes_between`, `test_drill`, `test_fire_source_dicts`, `test_housekeeping` | AC-27…AC-30, AC-35…AC-38 | `emp_a…d`, відвідувач, `patch.object(F3dAccessEvent, '_f3d_drill_active')` | поля працівника, представлення, словники CA-03/CA-09 |
| `test_cards.py::TestCards` | `test_constraints`, `test_issue_local`, `test_mark_synced`, `test_block_synced`, `test_block_405`, `test_issue_creates_card_once`, `test_cron_retry_limits`, `test_cron_write_disabled` | AC-39…AC-43 | `FakeBioStar` (`write_enabled`), картки | `sync_state`, `fake.calls`, `biostar_card_id`, чаттер |
| `test_visitors.py::TestVisitors` | `test_lifecycle`, `test_no_attendance_and_violation`, `test_closed_pass_logged`, `test_biostar_user_create`, `test_biostar_user_405`, `test_manual_user_conflict`, `test_register_from_yard`, `test_register_no_card`, `test_dates_and_unlink` | AC-44…AC-48 | відвідувач, пул карток `555`, `600` | стани, `zone_violation`, `hr.attendance` кількість, `fake.calls` |
| `test_viewer_provider.py::TestProvider` | `test_employee_keys`, `test_zone_people_now`, `test_access_schema_user`, `test_access_schema_security`, `test_infra_cards_replaced`, `test_delta_deep_merge`, `test_delta_no_changes`, `test_delta_keeps_foreign_keys`, `test_bus_calls`, `test_no_viewer_ok`, `test_registry_attrs` | AC-49…AC-52, AC-67 | `payload` dict, `ctx={'now': datetime(2026,10,12,7,30), 'now_local': '2026-10-12 10:30', 'today': '2026-10-12', 'user': …}` (для дельти — ще `changes`), `with_user`; для AC-51, AC-67 — код `factory3d_viewer` в `addons_path` (імпорт хелпера `deep_merge` без установки модуля, як yard AC-87) | ключі й значення JSON R-12; для дельти — склад `patch`, збереження чужих ключів, `patch['infra'] is inf` |
| `test_settings.py::TestSettings` | `test_params_roundtrip`, `test_ranges`, `test_password_groups`, `test_read_disabled`, `test_neutralize_sql`, `test_telemetry_publish`, `test_telemetry_off` | AC-53…AC-55, AC-57 | `res.config.settings`, `patch.object(F3dAccessTelemetry, '_f3d_signal_model')` | параметри, `UserError` тексти, `fake.calls == []`, записи після SQL |
| `factory3d_access_telemetry/tests/test_signals.py::TestAccessSignals` (теги `post_install`, `-at_install`, `f3d`, `f3d_access`) | `test_bridge_installed_signals`, `test_ensure_idempotent`, `test_new_device_signal`, `test_ingest_accepted`, `test_no_stale_without_source` | AC-68 | 5 пристроїв data, `freeze_time`; потребує встановленого `factory3d_telemetry` | кількість і поля сигналів, лічильники `_f3d_ensure_signals`, результат `_f3d_ingest`, `status` |
| `test_hooks.py::TestHooks` | `test_demo_like_counts`, `test_idempotent`, `test_clean_db_skipped`, `test_read_enabled_default`, `test_uninstall_hook` | AC-59…AC-61 | `make_demo_like()` | звіт `json.loads(migration_report)`, поля |
| `test_security.py::TestSecurity` | `test_acl_matrix`, `test_public_presence_fields`, `test_card_rules`, `test_company_rules`, `test_no_biometric_fields`, `test_keep_raw`, `test_menus`, `test_views_arch`, `test_settings_menu` | AC-62…AC-66, AC-69 | користувачі `common.py` | `AccessError` через `with_user()`; `env.ref(menu).sequence/parent_id/group_ids`; `etree` arch |

### 13.2 Стендові сценарії ТК-01…ТК-10 (емулятор)

Передумови (усі ТК): тестовий сервер timur-o19demo, копія бази `odoo` → `odoo_f3d_test` (§13.5), установлені
`factory3d_base`, `factory3d_access` (для ТК-09 — ще `factory3d_viewer`); `docker compose -f docker-compose.sim.yml
--profile demo up -d` (iot_sim §8.1.4); Odoo і емулятор в одній мережі (`https://iot-sim:8443`); параметри:
`biostar_password` = `SIM_BIOSTAR_PASS`, `read_enabled=True`, `write_enabled=False`; емулятор у режимі `scenario`.
Автоматизація: `tests/stand/` (pytest -m stand; XML-RPC до Odoo, `/sim/v1` з `SIM_API_TOKEN`); змінні середовища
`F3D_ODOO_URL`, `F3D_ODOO_DB`, `F3D_ODOO_USER`, `F3D_ODOO_PASSWORD`, `SIM_API_URL`, `SIM_API_TOKEN` (секрети — у
середовищі стенду, не в репозиторії). «Опитати зараз» = виклик `action_poll_now` (XML-RPC).

| ТК | Кроки | Очікуваний результат | Де дивитися | AC |
|---|---|---|---|---|
| ТК-01 Установка на копію демо | `odoo-bin -d odoo_f3d_test -i factory3d_access --stop-after-init`; лог INFO | без ERROR/traceback; звіт хука: `servers 1, devices 5, doors 5, equipment_bound 5, links 35, home_zones 35, presence_seeded 35, attendances_touched 0`; `hr_attendance` 35 рядків, усі `in_mode='manual'`; «Люди по зонах» — 35 карток (`Z-CUT` 4, `Z-EB` 3, `Z-CNC` 5, `Z-FAC` 6, `Z-ASM` 6, `Z-PACK` 4, `Z-HW` 2, `Z-RCV-2` 1, `Z-RCV-4` 1, `Z-SHEETS` 1, `Z-POST` 1, `Z-OUT-3` 1) | лог; Завод 3D → Доступ → Люди по зонах; Параметри системи `factory3d.access.migration_report` | AC-59 |
| ТК-02 Підключення і довідники | «Перевірити з'єднання»; «Синхронізувати пристрої й двері»; «Синхронізувати користувачів» | `online`, `users_total=36`, `devices_total=5`; 5 пристроїв `online`, `device_type` «BioEntry W3»; 5 дверей з `open_duration_s`; Користувачі BioStar: 36, 35 `barcode`, `"1"` — «Не зв'язано» | Сервери BioStar; Пристрої; Користувачі BioStar | AC-02, AC-11, AC-13 |
| ТК-03 Ранковий вхід | `POST /sim/v1/time {"set": "<сьогодні>T06:30:00+03:00", "factor": 10}`; 3 хв реального часу (06:30–07:00 sim); «Опитати зараз» кожні 30 с або крон | Журнал: 35 проходів TURN-1 `in` (4102/4867) + 105 подій дверей; демо-відмітки 12.10 закриті R-07 (`f3d_closed_by_rule`, 12:30Z) при першому вході кожного; 35 нових відміток `in_mode='biostar'` з `check_in` 06:40–06:59 сьогодні; повторних відміток немає. Якщо `set` = `2026-10-12T06:30:00+03:00` — 35 подій `attached`, нових відміток 0 | Відвідування → Управління (фільтр «СКУД BioStar 2»); Журнал подій | AC-15, AC-16, AC-27 |
| ТК-04 Вихід | `POST /time {"set": "<сьогодні>T15:25:00+03:00", "factor": 10}`; 3 хв; опитування | 35 виходів `out`; 35 відміток закрито `out_mode='biostar'`, `check_out` 15:30–15:49; «Люди по зонах» порожньо; `TURN-1` `closed` | Відвідування; Люди по зонах; Двері | AC-18 |
| ТК-05 Внутрішні двері й відмова | після ТК-03: `POST /sim/v1/scenario/access_event/start {"params": {"device": "ACR-ELEC", "user": "OPW1", "code": 4102, "tna_key": "", "door_open": true}}`; потім `{"device": "ACR-ELEC", "user": "OPW2", "code": 6400}`; опитування; через 30 хв sim — `_cron_zone_dwell` | OP-W1 у `Z-ELEC`, потім `Z-HW`; відмітка OP-W1 не змінилась; подія 6400 OP-W2 у фільтрі «Відмови», двері 2 `DOOR-ELEC`; `DOOR-ELEC` `unlocked → open → closed` | Люди по зонах; Журнал (фільтр «Відмови»); форма Олександра Федоренка → «Доступ» | AC-22, AC-28, AC-31 |
| ТК-06 Недоступність і відновлення | `docker compose stop iot_sim` на 5 хв (sim продовжить після старту) — або невірний пароль; потім старт/виправлення | сервер `error`, `error_count` зростає, `next_try_at` за R-16; після відновлення — `online`, події за простій з'являються (порівняти кількість з `GET /api/events/search` за той самий інтервал напряму) | Сервери BioStar | AC-08 |
| ТК-07 Відвідувач | Відвідувачі → створити («Іван Петренко», «ТОВ Постачальник», приймає OP-W1, зони `Z-OFFICE`), картка пулу, «Очікується»; `biostar_user_id='V-<id>'` вручну (Q-12); `access_event {"device": "ACR-IN", "user": "V-<id>", "code": 4102, "tna_key": "1"}`; потім `{"device": "ACR-ELEC", "user": "V-<id>", "code": 4102, "tna_key": ""}`; потім `tna_key "2"` на ACR-IN | `on_site` → порушення зон (ACR-ELEC) → `left`; відміток відвідувача немає; «Люди по зонах» показує бейдж «Відвідувач» | Відвідувачі; Журнал (фільтр «Порушення зон») | AC-44, AC-45 |
| ТК-08 Блокування картки | Картка `12345678` працівнику OP-SAW-1 → «Видати» (`write_enabled=False`) → `local`, підказка; «Позначити синхронізованим». Увімкнути `write_enabled=True` → «Заблокувати» (причина «Тест») | 1) `local` і текст про стоп-кран; 2) `synced` вручну; 3) емулятор → 405: `sync_state='error'`, «Метод не підтримується сервером BioStar (405)», `state='blocked'`; у лозі емулятора WARNING 405. Повернути `write_enabled=False` | Картки | AC-40, AC-41 |
| ТК-09 Переглядач | (з `factory3d_viewer`) Завод 3D → Переглядач під час ТК-03; клік по людині й зоні `Z-CUT`; Люди по зонах → «Показати в 3D» | картка людини: «На території з», «Зона», «Останній прохід» (CA-05; рядки картки — автор viewer); зона: «Людей зараз: 4»; картка `TURNSTILES`: «35 працівників · 0 відвідувачів»; після проходу — оновлення без перезавантаження (шина) | 3D | AC-49, AC-66 (MAN) |
| ТК-10 Пожежне навчання | `POST /sim/v1/scenario/fire_drill/start {"params": {"zone": "FA-CNC"}}` | за ≤ 12 с sim: 20480 на дверях 1–5 і 26368 → двері `unlocked`, `alarm=True`, `alarm_reason='fire'` (червоні в канбані «Двері»); «Зняти тривогу» охороною; (з `factory3d_fire_safety` і `_f3d_is_active_at`) виходи TURN-1 під час навчання — `drill`, відмітки відкриті | Двері; Журнал | AC-33, AC-37 |

### 13.3 Тести безпеки ТБ-01…ТБ-08

Матриця `test_acl_matrix` (R — read, W — write, C — create, D — unlink; «—» — `AccessError`):

| Модель | `user_plain` | `user_f3d` | `user_security` | `user_hr` | `user_admin` | `user_f3d_admin` |
|---|---|---|---|---|---|---|
| `f3d.access.server` | — | — | — | — | R | RWCD |
| `f3d.access.device` | — | R | R | — | RWCD | RWCD |
| `f3d.access.door` | — | R | RW (лише `alarm*`) | — | RWCD | RWCD |
| `f3d.access.user.link` | — | — | R | R | RWCD | RWCD |
| `f3d.access.event` | — | — | R | R | R | RWCD |
| `f3d.access.card` | — | — | RWC (відвідувачі/пул) | — | RWCD | RWCD |
| `f3d.access.visitor` | — | — | RWCD | R | RWCD | RWCD |
| `f3d.access.presence` | — | — | R | R | R | R |

| ТБ | Перевірка | Очікування |
|---|---|---|
| ТБ-01 | матриця вище (`test_acl_matrix`) + кнопки: `action_poll_now` для `user_security` → `AccessError`; `action_test_connection` для `user_admin` → `AccessError`; `action_reset_cursor` лише F | як у таблиці |
| ТБ-02 | секрети: `session_id` і `f3d_access_biostar_password` відсутні в `fields_get`/`read` для `user_admin`; пароль не в `last_error`, логах (AC-03, AC-58), чаттері карток/відвідувачів | відсутні |
| ТБ-03 | стоп-крани: AC-55, AC-56; `neutralize.sql` (AC-57); крони після нейтралізації не ходять у мережу (`fake.calls == []`) | так |
| ТБ-04 | ін'єкції: `biostar_user_id="'; DROP TABLE hr_employee; --"` у рядку API-03/06 → рядок пропущено (`invalid`), таблиця на місці; `code="ACR-IN'; --"` → `ValidationError`; `url="https://x/api?;rm"` → `ValidationError`; `event_type_id.code="4102; DROP"` → `invalid`; JSON з `__proto__`/вкладеними 1 000 рівнями → `invalid` без падіння крона | так |
| ТБ-05 | TLS: `verify_ssl=False` на `environment='prod'` неможливо (AC-01); `requests` викликається з `verify=True` за замовчуванням (`mock.call_args.kwargs['verify']`) | так |
| ТБ-06 | персональні дані: AC-64; `raw_user_id` невидимий `user_f3d`; переглядач без `last_events` і без імен для не-охорони (AC-50); телеметрія без `user_id` (AC-53) | так |
| ТБ-07 | `hr.employee`: охорона без `hr.group_hr_user` не читає `f3d_access_last_event_id`, `f3d_access_card_ids` через `hr.employee` (`AccessError`), але бачить людей через M-14 | так |
| ТБ-08 | емулятор (стенд): запис при `write_enabled=False` — у лозі емулятора немає жодного `POST /api/cards`, `PUT /api/users`, `POST /api/users` за весь прогін ТК-01…ТК-07 | 0 записів |

### 13.4 Тести продуктивності ТП-01…ТП-04

| ТП | Обсяг | Межа | Як |
|---|---|---|---|
| ТП-01 опитування з лавиною | 10 000 рядків (20 сторінок × 500) після «простою», 150 працівників | `_poll()` ≤ 60 с (створення + обробка), запитів до fake = 20 | `test_perf_poll` (тег `f3d_access_perf`, не в DoD-прогоні за замовчуванням), `time.perf_counter()` |
| ТП-02 добовий обсяг | 1 400 подій/добу (прод, ARCH §2.7) по 1 хв | одне опитування ≤ 2 с; 1 440 прогонів/добу; на стенді CPU Odoo-воркера < 5 % | ТК-03/04 з `factor=10`, лог тривалості крону (`ir.cron` `lastcall`), `pg_stat_statements` |
| ТП-03 провайдер і «люди зараз» | 150 працівників, 5 дверей, 130 000 подій у таблиці | `_f3d_viewer_collect` ≤ 200 мс; `f3d_people_now` для 45 зон ≤ 50 мс; `EXPLAIN` журналу «Сьогодні» — Index Scan по `ts` | `test_perf_provider` |
| ТП-04 ротація | 130 000 подій старших за `keep_days` | `_cron_housekeeping` ≤ 120 с, пакети по 5 000 | `test_perf_gc` (генерація `execute_values` у тесті) |

### 13.5 Чек-лист DEPLOY_TEST (`docs/modules/factory3d_access/DEPLOY_TEST.md`, здає W5)

1. Зняти дамп бази `odoo` тестового сервера; відновити як `odoo_f3d_test`; знімки: `SELECT id, employee_id, check_in, check_out, in_mode, out_mode FROM hr_attendance ORDER BY id` (S1), `SELECT id, barcode FROM hr_employee ORDER BY id` (S2).
2. Переконатися, що `factory3d_base` установлено (хвиля 1) і `factory3d.base.environment='test'`.
3. Установити модуль (ТК-01); `S1` після установки = до (відмітки не змінені); звіт хука. Якщо встановлено
   `factory3d_telemetry` — міст `factory3d_access_telemetry` установлюється автоматично, у лозі «Сигнали СКУД: створено 7»
   (AC-68, X-33); `--test-tags /factory3d_access_telemetry` → 0 падінь.
4. Підняти емулятор (iot_sim §8.1.4), ввести пароль BioStar, ТК-02…ТК-08; ТК-09 — якщо встановлено viewer; ТК-10.
5. Юніт-тести на копії: `--test-tags /factory3d_access` → 0 падінь; на чистій базі — те саме.
6. `odoo-bin neutralize -d odoo_f3d_test` → крони вимкнені, пароль стерто, `read_enabled='False'` (AC-57 на живій копії).
7. Деінсталяція модуля → `S1` за кількістю записів не менший, `in_mode`/`out_mode` `biostar` → `manual`; параметрів `factory3d.access.%` немає; повторна установка → ТК-01 зелений.
8. Відкат: видалити `odoo_f3d_test`; робоча база `odoo` не змінювалась.
9. Фактичні кількості й час опитування записати в CHANGELOG («Міграція демо») і `TEST_REPORT.md`.

## 14. Definition of Done

- Усі юніт-тести §13.1 зелені на чистій базі й на копії демо (`--test-tags /factory3d_access` і, з telemetry,
  `/factory3d_access_telemetry`), кожен AC-01…AC-69
  типу UT має тест із назвою з таблиці §13.1; тести не звертаються в мережу (перевірка: `requests.Session.request`
  запатчено в `AccessCase.setUpClass` на `AssertionError`).
- ТК-01…ТК-10 пройдені на стенді, протокол у `DEPLOY_TEST.md` з фактичними кількостями; ТБ-01…ТБ-08 зелені;
  ТП-01…ТП-04 у межах (результати в `TEST_REPORT.md`).
- `ruff check` (конфіг проєкту; без нього — умовчання, довжина рядка 120) без помилок; `xmllint --noout` для `views/`,
  `data/`, `security/`.
- `grep -rnE "\bx_[a-z]" models/ views/ data/ hooks.py tools/` порожній (жодного `x_`-поля); жодного `print(`;
  жодного `sudo()` у `controllers/` (їх немає) і в провайдері — лише в `_f3d_access_public_presence` (A-21).
- `neutralize.sql` виконується без помилки (AC-57) і перелічений у README.
- Секрети: пароль і `bs-session-id` не трапляються в логах тестового прогону (`grep -c "test-pass" odoo.log` = 0).
- Контракти CA-01…CA-09 реалізовані з точними іменами; зміна імен — лише через оновлення SPEC і повідомлення авторів
  `factory3d_viewer`, `factory3d_fire_safety`, `factory3d_yard`, `factory3d_telemetry`.
- `README.md` (установка, параметри §5.1, інструкції ARCH §4.1–4.6), `CHANGELOG.md` (`19.0.1.0.0`, «Міграція демо»).
- Перегляд безпеки (ТБ, §4.4) і перегляд коду PR (pr-review) — APPROVE; ARCH/SPEC оновлені за рішеннями менеджера щодо
  Q-01…Q-14.

## 15. Відкриті питання

Ті самі номери, що в ARCH §5.1 (Q-13, Q-14 додані разом із цим SPEC). Що робить код, поки відповіді немає:

| ID | Питання (коротко) | Рекомендація | Поки немає відповіді |
|---|---|---|---|
| Q-01 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** обидва режими `offset`/`hint`. пагінація `events/search` на проді: `offset` чи `hint` | підтримати обидва (`paging_mode`) | `offset` (емулятор); `hint` бере `hint` останнього рядка сторінки (ПРИПУЩЕННЯ за статтею 24000106474) |
| Q-02 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** запізнілі події — добовим переглядом (FR-18). `server_datetime` для запізнілих подій офлайн-пристроїв | так | вікно за `datetime` + добова перевірка `recheck_hours=24` (R-20 крок 4) |
| Q-03 | **Закрито 14.10 (рішення менеджера):** у v1.1 — синхронізація карток через `GET /api/cards`. імпорт карток працівників із BioStar (`GET /api/cards`) | v1.1, після підтримки емулятором | картки — вручну; `card_count` на зв'язку |
| Q-04 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** два турнікети × вхід/вихід, `tna_key` лишається; в емуляторі — даними у v1.1. один `ACR-IN` з `tna_key` чи два турнікети × два зчитувачі | два × два | `ACR-IN.direction='tna'`, один `TURN-1`; нові двері/пристрої — даними (R-19 + налаштування зон) |
| Q-05 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** стандарт Odoo: відмітка = факт, понаднормові — пороги 20/10 хв. правила робочого часу, нічні зміни | стандарт Odoo (факт + пороги понаднормових) | без обрізання відміток; вихід до `max_shift_h=16` год закриває відмітку через північ (A-20), довше — R-07 |
| Q-06 | **Закрито 14.10 (відповідь № 20, CONSISTENCY):** автоматично `POST /api/users` під стоп-краном `write_enabled`; документ не зберігаємо — лише прапорець «документ перевірено». відвідувачі в BioStar автоматично? документ? | автоматично під стоп-краном; документ не зберігати | обидва шляхи (R-14 крок 2); прапорець «Документ перевірено»; група BioStar `visitor_user_group_id=1` (ПРИПУЩЕННЯ) |
| Q-07 | **Закрито 14.10 (відповідь № 21, CONSISTENCY):** у v1 ні — лише читання стану; пожежне розблокування апаратно (FACP → BioStar); відкривання дверей з Odoo — v2. керування дверима з Odoo | ні у v1 | лише читання стану (R-10) |
| Q-08 | **Закрито 14.10 (відповідь № 22, CONSISTENCY):** `keep_days=90`; для розслідувань — експорт охороною. строк зберігання журналу | 90 днів | `keep_days=90`; відвідувачі видаляються через 90 днів після візиту (R-20 крок 6) |
| Q-09 | **Закрито 14.10 (рішення менеджера):** нові зони не створюємо; `zone_to` — зона-контейнер. побутовий блок між входом і цехом; зони комор | не створювати | граф ARCH §2.3, `zone_to` = зона-контейнер, `dwell_min=30` для DOOR-PAINT/DOOR-SRV |
| Q-10 | «людей зараз» у `zones[code]` чи лише в `access` | **закрито X-87 (X-23)**: обидва в повному payload і в дельті | R-12 п. 7: дельта — `access` цілком, `employees`/`zones`/`infra.cards` через `deep_merge`; рядки карток людини/зони — автор viewer за CA-05 |
| Q-11 | сигнатура `_f3d_ingest` і `module='access'` | закрито SPEC telemetry: M-03 `_f3d_ingest(readings, src='module', collector=None)`, R-15 `access/*` → `access`; хто створює сигнали — **закрито X-33**: міст `factory3d_access_telemetry` (M-17) | R-18 з `src='module'`; 7 сигналів створює міст; архівний/видалений сигнал — DEBUG |
| Q-12 | **Закрито 14.10 (рішення менеджера):** невідомий `user` → подія без `name`; `POST /api/users` — v1.1. емулятор: невідомий `user` у `access_event`, `POST /api/users` | невідомий → подія без `name`; `POST /api/users` у v1.1 | ТК-07 — ручне `biostar_user_id`; ТК-08 очікує 405 |
| Q-13 | **Закрито 14.10 (рішення менеджера):** так: fire_safety надає CF-02 (префікс `f3d.fire.passage.source.`) і CF-06 `_f3d_is_active_at`. **нове.** `factory3d_fire_safety`: знаходити джерела CF-02 за префіксом `f3d.fire.passage.source.` (не через `_inherit`, бо access не залежить від fire) і надати `f3d.fire.drill._f3d_is_active_at(ts) -> bool` (fire Q-15) | так (A-24); автор fire_safety — M-12/M-12a SPEC fire | M-16 і `_f3d_drill_active` готові; без методу у fire — `False` (виходи під час навчань закривають відмітки, як сьогодні) |
| Q-14 | **Закрито 14.10 (відповідь № 18, CONSISTENCY):** у v1 блокування лише в Odoo; запис у BioStar — після перевірки на тестовому сервері замовника. **нове.** Формат блокування картки в BioStar 2 (`PUT /api/users/{id}` з `cards[].is_blocked` чи окремий ендпоінт блокування/чорного списку) | перевірити на тестовому BioStar замовника до вмикання `write_enabled` (Suprema, замовник) | API-08 за ПРИПУЩЕННЯМ; ручний шлях «Позначити синхронізованим»; на стенді — 405 |

## Додаток A. Рішення автора, ухвалені в SPEC (продовження ARCH §7)

| ID | Рішення | Обґрунтування |
|---|---|---|
| A-17 | «Люди по зонах» — SQL-представлення `f3d.access.presence` (працівники + відвідувачі); поля присутності продубльовано в `hr.employee.public` (M-08a) | охорона без `hr.group_hr_user` не читає `hr.employee` (Odoo 19 `_check_private_fields`); один kanban для працівників і відвідувачів |
| A-18 | «Перевірити з'єднання» (лише F) працює і при `read_enabled=False`, з окремою сесією | адміністратор має перевірити доступ до вмикання опитування на проді |
| A-19 | Провайдер переглядача — `AbstractModel` без `_inherit` (duck typing інтерфейсу viewer M-01) | `factory3d_viewer` не є залежністю (каркас §3); `_inherit` на відсутню модель зламав би установку |
| A-20 | `max_shift_h=16`: вихід протягом 16 год після входу закриває відмітку навіть через північ; довше — R-07 | нічна робота без втрати відмітки; 16 год — поріг «Errors» стандартного фільтра `hr_attendance` |
| A-21 | Провайдер читає присутність через `sudo()` лише нечутливих полів (`_f3d_access_public_presence`), особи — тільки для охорони | `f3d_access_last_event_id` (група охорони) не входить у `hr.employee.public`; `f3d_code`, `f3d_alias`, `f3d_kind` там є з base M-10a (X-09), поля присутності — з M-08a; присутність/зона за ARCH §2.6 доступні всім внутрішнім |
| A-22 | Хук засіває присутність із відкритих відміток (35 на демо), відмітки не змінює | інакше після установки провайдер (170) перекрив би `present` провайдера `people` на `False` і 3D-картина демо зникла б |
| A-23 | Зона пристрою — з data (зона «з» дверей), не `zone_at` | 3 з 5 зчитувачів стоять на стінах у зазорах між зонами (`ACR-IN y=0.12`, `ACR-ELEC y=62.25`, `ACR-CHG y=59.88`) — `zone_at` повертає порожньо |
| A-24 | Джерело проходів для fire_safety — `AbstractModel` `f3d.fire.passage.source.access` (`_f3d_priority=10`) і прапор навчання через `_f3d_is_active_at` (CA-09) | обидва модулі не залежать один від одного; fire Q-10, Q-15 |
| A-25 | `dwell_min=30` для всіх внутрішніх дверей (і DOOR-PAINT/DOOR-SRV, де `zone_to` = контейнер) | з `dwell_min=0` комірник після складу ЛФМ лишався б у `Z-FAC` до кінця зміни |
| A-26 | Події, старші за останню оброблену подію людини, — `late`: ні відмітки, ні зони | порядок доставки не гарантований (офлайн-пристрої, Q-02); стандарт `_check_validity` відхилив би перетин інтервалів; виправлення — майстер M-13 |
| A-27 | Класифікація за `code >> 8` | iot_sim ARCH Q-13 і Додаток A кажуть «4096/4864», SPEC iot_sim §8.12 — «4102/4867»; обидва варіанти дають правильний тип |
| A-28 | Сигнали телеметрії без `user_id`: `text` = «код двері» | `f3d.signal` читає кожен `group_f3d_user`; персональні дані — лише в журналі з правами охорони |
