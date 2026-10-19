# td_yard — специфікація

Версія 0.2 · 14.10.2026 · автор: агент-архітектор модуля (хвиля 2, фаза 4) · технічне рішення:
`docs/modules/td_yard/ARCHITECTURE.md` (далі ARCH, версія 0.3: FR-01…FR-28, CY-01…CY-08, A-01…A-14, Q-01…Q-14).
Цей документ додає рішення A-15…A-28 (§15.2), правила R-01…R-24 (§9), моделі M-01…M-18, представлення V-01…V-34,
RPC/контракти API-01…API-06 (§7), критерії AC-01…AC-88 (§12), стендові сценарії ТК-01…ТК-08 (§13.2).
Зміни: 16.10.2026 — QA-фікс Y-1: AC-82 і ТК-02 — LPR доходить в Odoo через `POST /f3d/telemetry/event` з `route="lpr"`; без токена колектора — `401`; маршруту `/f3d/lpr` в Odoo немає (ingress колектора `POST /f3d/lpr` лишається).

Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-15 (M-07 `td_plate` — держномер, не код сцени), X-17 (джерела
`MB-U86-IO7`, `SICS-TRUCK-SCALE`: §5.3, M-03, M-06, §13, Додаток A), X-23 (R-20 п. 7 — `infra` лише через `deep_merge`; AC-87),
X-32 (§3: «Налаштування двору» під `td_factory3d.menu_td_config`, 60; AC-66), X-45 (§8.2 — спільна схема `sics`, власник
двір; AC-48), X-46 (Додаток A: `pulse_ms` 1500 на `cmd_open`/`cmd_close`, `cmd_hold` — рівень; R-15, API-04, AC-84, ТК-04),
X-47 (`GATE-E/cmd_hold` → DO5, PDU 21; AC-88), X-48 (R-07 п. 4 = telemetry R-22, `datetime` і `camera_tz` вилучено; API-03,
§5.1, V-32, §11.5), X-57 (ТК-01, ТК-03 — тіло `{"params": …}`), X-70 (`scale`/`offset` в `address.sics.json`, §8.5, AC-52),
X-73 (AC-23 за прикладом iot_sim: `plateList=f3d_bookings`, нове поле `plate_list_mode`, тести §13.1; ТК-02); закрито
Q-01 (X-53), Q-02 (X-49), Q-04 (X-46), Q-14 (X-04), рішення Q-13 (X-47); §15.3 — посилання на X-xx; Додаток A — рядки каталогу
iot_sim 689–698 (X-34).
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-05, Q-06, Q-07, Q-09, Q-11, Q-12, Q-13.
Зміни: 14.10.2026 — закрито рішеннями менеджера: Q-03, Q-08, Q-10.

Спирається на контракти (посилання — лише за ідентифікаторами):
- каркас `docs/ARCHITECTURE.md`: §5 (імена, стоп-крани, права, тести), §6.1–6.2 (код сцени, ворота = док),
  §6.4–6.5 (телеметрія, плагіни; `sics` належить цьому модулю), §6.6 рядок **P-11**, §6.7 (переглядач), D-02, D-03;
- `td_factory3d`: CB-01 (`td.scene.mixin`), CB-03 (`td.zone.zone_at`), CB-05 (ворота `stock.location`
  `td_kind='dock'`, `td_side`, `td_dock_no`, `td_accepts`, `td_x`, `td_y`; `stock.picking.type.dock_ids`),
  CB-06 (`stock.picking.batch.td_code` — єдиний код фури в 3D, `td_truck` — опис/назва з макета, не номер; X-15),
  CB-09 (меню, sequence 60), CB-10 (групи,
  `td.base.environment`), CB-12 (межі території), R-10/R-19 base, Додаток C.2 (надвірні зони), Додаток D (ворота),
  AC-25/AC-26 base (6 пакетів фур + 18 нових пакетів після міграції base);
- `td_viewer3d`: M-01 (`td.viewer.provider`, `_td_sequence=160` для yard), R-01 п. 3 (провайдери
  знаходяться за префіксом імені `td.viewer.provider.`), M-03 (`td.viewer.event._notify`), C-05 (дія
  `f3d_viewer.action`), Додаток A.0, A.8 (`pickings[].dock/truck`), A.11 (`docks`), A.13 (`infra.cards`), A.14 (`ship_chain`);
- `td_telemetry` SPEC: M-02 `td.source`, M-03 `td.signal` (`_td_ingest`), M-06 `td.command`,
  M-11 `td.push.handler`, M-13 `td.push.event`, API-05…API-07, R-17 (Ingester: `last_value` оновлюється SQL),
  R-18 (життєвий цикл команди), R-20 (Modbus: PDU, `wordorder`), R-22 (маршрутизація http_push), §8.3 (інтерфейс
  плагіна CT-02), §8.5 (`modbus_tcp`), §8.7 (`http_push`: `POST /f3d/{route}`); ARCH telemetry CT-01…CT-11, Q-13;
- `td_iot_sim` SPEC: §8.4.1 (unit id 86), §8.4.2 (лічильники ADAM: молодше слово першим), **§8.13 P-11**
  (§8.13.1 ADAM-6060, §8.13.2 Axis LPV JSON, §8.13.3 SICS), R-29, R-30, S-05 `truck_no_booking`, S-06 `truck_arrival`,
  API-01 `bookings[]`, Додаток A рядки 654–661 і 689–698;
- `td_access` ARCH: CA-07 (відвідувач з `origin='yard'`) — у v1 не викликається (межа ARCH §1.4).

Позначення типів перевірки: **UT** — `odoo.tests.TransactionCase`; **HT** — `HttpCase` (у т. ч. тур OWL);
**CT** — pytest плагіна колектора з фейковим сервером; **TC** — стенд (емулятор `iot_sim` + колектор + Odoo);
**MAN** — ручна перевірка на тестовому сервері timur-o19demo (база `odoo`). Odoo 19: SQL-обмеження —
`models.Constraint`; хуки `post_init_hook(env)` / `uninstall_hook(env)`; `fields.Json`; команди o2m/m2m —
`odoo.fields.Command`. Рядки UI — українською прямо в коді (D-14). Жодних `x_`-полів. Час у БД — UTC (naive);
«день», «сьогодні», години слотів у текстах — за `Europe/Kyiv` (R-23 і §11.5).

Часові приклади з макета: демо-годинник `dist/odoo_demo.json → meta.now = "2026-10-12 10:30"` (Київ, UTC+3,
літній час до 25.10.2026) = `2026-10-12 07:30 UTC`.

## 0. Дерево файлів модуля

### 0.1 Odoo-модуль `odoo_addons/td_yard`

```
odoo_addons/td_yard/
├── __init__.py                       from . import models, wizard, report, hooks; from .hooks import post_init_hook, uninstall_hook
├── __manifest__.py                   §1
├── README.md                         призначення, установка (порядок: base → telemetry → yard), параметри §5.1, стенд
├── CHANGELOG.md                      19.0.1.0.0 — перший випуск
├── hooks/
│   ├── __init__.py                   post_init_hook(env), uninstall_hook(env), run_all(env) — §5.4
│   └── migrate.py                    кроки 1–10 R-24: equipment_links, signals, product_weights, carrier_partners,
│                                     visits_from_batches, bookings_from_batches, weighing_from_card, params, report
├── tools/
│   ├── __init__.py
│   ├── plate.py                      normalize_plate(), display_plate(), is_valid_plate_input(), LOOKALIKE — R-08
│   ├── tz.py                         KYIV, to_local(dt), local_hm(dt), local_day(dt), day_bounds_utc(day), parse_axis_ts() (`capture_timestamp` епоха мс → UTC naive; R-07 п. 4) — §11.5
│   └── params.py                     PARAMS (ключ → умовчання), get_bool/get_int/get_float/get_str(env, name) — §5.1
├── models/
│   ├── __init__.py                   порядок: td_yard_gate, td_yard_scale, td_yard_visit, td_yard_booking,
│   │                                 td_yard_lpr_event, td_yard_weighing, stock_picking_batch, stock_picking,
│   │                                 res_partner, delivery_carrier, td_command, td_signal, td_push_handler,
│   │                                 td_viewer_provider, res_config_settings
│   ├── td_yard_visit.py             M-01 + kpp_data/kpp_action (API-01, API-02)
│   ├── td_yard_booking.py           M-02
│   ├── td_yard_gate.py              M-03
│   ├── td_yard_lpr_event.py         M-04 + _td_from_push (R-07, R-08)
│   ├── td_yard_weighing.py          M-05
│   ├── td_yard_scale.py             M-06
│   ├── stock_picking_batch.py        M-07
│   ├── stock_picking.py              M-08, M-08b (stock.move.line — R-09)
│   ├── res_partner.py                M-09
│   ├── delivery_carrier.py           M-10
│   ├── res_config_settings.py        M-11
│   ├── td_push_handler.py           M-12
│   ├── td_signal.py                 M-13
│   ├── td_viewer_provider.py        M-14
│   └── td_command.py                M-18
├── report/
│   ├── __init__.py
│   ├── td_yard_dock_report.py       M-15 (SQL-вид)
│   └── td_yard_report_views.xml     V-27, V-28
├── wizard/
│   ├── __init__.py
│   ├── td_yard_walkin_wizard.py     M-16
│   ├── td_yard_reject_wizard.py     M-17
│   └── td_yard_wizard_views.xml     V-29, V-30
├── security/
│   ├── td_yard_security.xml         привілей, 3 групи, implied, record rules (§4.2, §4.3)
│   └── ir.model.access.csv           §4.1
├── data/
│   ├── ir_config_parameter.xml       §5.1 (noupdate="1")
│   ├── ir_sequence.xml               §5.2
│   ├── td_yard_gate_data.xml        GATE-W, GATE-E, TRUCK-SCALE (§5.3; noupdate="1")
│   ├── td_yard_signals.csv          18 сигналів — читає хук (не в `data` маніфесту), Додаток A; джерела — константа hooks/migrate.py:SOURCES
│   ├── ir_cron.xml                   §6
│   ├── td_yard_actions.xml          ir.actions.server: «Повторити міграцію двору», «Диспетчеризація (стандарт)»
│   └── neutralize.sql                §5.6
├── views/
│   ├── td_yard_visit_views.xml      V-01…V-06
│   ├── td_yard_booking_views.xml    V-07…V-11
│   ├── td_yard_gate_views.xml       V-12, V-13
│   ├── td_yard_lpr_event_views.xml  V-14…V-16
│   ├── td_yard_weighing_views.xml   V-17…V-19
│   ├── td_yard_scale_views.xml      V-20
│   ├── stock_picking_batch_views.xml V-21, V-22
│   ├── stock_picking_views.xml       V-23, V-24
│   ├── res_partner_views.xml         V-25, V-26 (у т. ч. delivery.carrier)
│   ├── td_command_views.xml         V-31
│   ├── res_config_settings_views.xml V-32
│   ├── td_yard_kpp_action.xml       V-33 (ir.actions.client)
│   └── td_yard_menus.xml            V-34: меню й дії
├── static/src/kpp/
│   ├── kpp_action.js                 OWL-компонент F3dYardKpp (V-33, R-18)
│   ├── kpp_action.xml                шаблон
│   └── kpp_action.scss               стилі планшета
├── static/tests/tours/
│   ├── f3d_yard_dispatch_tour.js     тур AC-54
│   └── f3d_yard_kpp_tour.js          тур AC-58
└── tests/
    ├── __init__.py
    ├── common.py                     YardCase(TransactionCase): фікстури §13.1
    ├── test_visit.py                 AC-01…AC-03, AC-21, AC-22
    ├── test_booking.py               AC-04…AC-13
    ├── test_picking.py               AC-14…AC-20
    ├── test_lpr.py                   AC-23…AC-33 (+ TestInjection, ТБ-05)
    ├── test_commands.py              AC-34…AC-37, AC-88
    ├── test_gate.py                  AC-38…AC-40, AC-46, AC-47
    ├── test_scale.py                 AC-41…AC-45, AC-48
    ├── test_kpp.py                   AC-53…AC-58 (TestTours — HttpCase)
    ├── test_provider.py              AC-62…AC-65, AC-87
    ├── test_reports.py               AC-59…AC-61
    ├── test_migration.py             AC-72, AC-76, AC-77, AC-79
    ├── test_security.py              AC-66…AC-69, AC-73, AC-74
    ├── test_cron.py                  AC-70, AC-71, AC-80
    └── test_contracts.py             AC-78: поля/методи суміжних модулів і теги тестів (ризик ARCH §5.3)
```

### 0.2 Плагін колектора `services/collector_plugins/f3d_collector_yard`

```
services/collector_plugins/f3d_collector_yard/
├── pyproject.toml                    пакет f3d-collector-yard 0.1.0 (§8.1)
├── README.md                         установка в образ колектора, params/address, приклади
├── f3d_collector_yard/
│   ├── __init__.py                   __version__ = "0.1.0"
│   ├── sics.py                       SicsPlugin, Frame, parse_line(), to_kg() — §8.3–§8.6
│   └── schemas/
│       ├── params.sics.json          JSON Schema params джерела (§8.2, CY-05)
│       └── address.sics.json         JSON Schema адреси сигналу (§8.2, CY-05)
└── tests/
    ├── conftest.py                   фікстури: fake_sics (сервер на вільному порту), ctx (PluginContext-заглушка), event_loop
    ├── fake_sics_server.py           FakeSicsServer — §8.7
    ├── test_sics_parse.py            AC-49
    └── test_sics_plugin.py           AC-50…AC-52
```

## 1. Маніфест

```python
{
    "name": "Завод 3D: двір",
    "summary": "Рейси сторонніх фур, бронювання воріт, КПП із розпізнаванням номерів, шлагбауми й автоваги",
    "description": "Рейс фури від бронювання воріт до виїзду: черга, екран КПП, події Axis LPR через "
                   "td_telemetry, команди на шлагбауми CAME (ADAM-6060), автозважування (SICS), "
                   "нетто в документі приймання/відвантаження, звіти, розділ yard для 3D-переглядача.",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_factory3d", "td_telemetry", "stock_picking_batch", "stock_fleet",
                "delivery", "stock_delivery", "web_gantt", "mail", "bus"],
    "data": [
        "security/td_yard_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_sequence.xml",
        "data/td_yard_gate_data.xml",
        "data/ir_cron.xml",
        "data/td_yard_actions.xml",
        "views/td_yard_visit_views.xml",
        "views/td_yard_booking_views.xml",
        "views/td_yard_gate_views.xml",
        "views/td_yard_lpr_event_views.xml",
        "views/td_yard_weighing_views.xml",
        "views/td_yard_scale_views.xml",
        "views/stock_picking_batch_views.xml",
        "views/stock_picking_views.xml",
        "views/res_partner_views.xml",
        "views/td_command_views.xml",
        "views/res_config_settings_views.xml",
        "views/td_yard_kpp_action.xml",
        "wizard/td_yard_wizard_views.xml",
        "report/td_yard_report_views.xml",
        "views/td_yard_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "td_yard/static/src/kpp/kpp_action.js",
            "td_yard/static/src/kpp/kpp_action.xml",
            "td_yard/static/src/kpp/kpp_action.scss",
        ],
        "web.assets_tests": [
            "td_yard/static/tests/tours/*.js",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
```

Порядок `data`: групи → доступи → параметри → послідовності → ворота/ваги → крони → серверні дії → представлення
→ майстри → звіти → меню (посилаються на дії з усіх попередніх файлів). Джерела й сигнали telemetry створює хук
(`SOURCES` у `hooks/migrate.py`, `td_yard_signals.csv` через `odoo.tools.file_open("td_yard/data/td_yard_signals.csv")`)
без `ir.model.data` — A-19, §5.3.

Зміни щодо ARCH §2.1: додано `stock_delivery` (поле `stock.picking.carrier_id` оголошене в ньому — перевірено
`ir.model.fields.modules='stock_delivery'` у живій базі 14.10.2026) і `bus` (канал `f3d_yard` для екрана КПП).
`td_viewer3d` і `stock_fleet_enterprise` — не в `depends` (A-15, V-34). Python-залежностей поза stdlib немає
(`zoneinfo`, `base64`, `re`, `json`).

## 2. Моделі

Спільні позначення: `req` = `required=True`; `idx` = `index=True`; `ro` = `readonly=True`; типи — `fields.*`.
`GRP_SEC` = `"td_yard.group_td_yard_security"`, `GRP_DISP` = `"td_yard.group_td_yard_dispatcher"`,
`GRP_MGR` = `"td_yard.group_td_yard_manager"`. Параметри `P.<name>` = `ir.config_parameter`
`td.yard.<name>` через `tools/params.py` (§5.1). `now` = `fields.Datetime.now()` (UTC naive).

Хелпер прав (у `models/td_yard_visit.py`, використовують усі моделі модуля):

```python
def _td_yard_require(env, *xmlids):
    """Пропускає суперкористувача (env.su) і членів будь-якої з груп; інакше AccessError."""
    if env.su or any(env.user.has_group(x) for x in xmlids):
        return
    names = ", ".join(env.ref(x).name for x in xmlids)
    raise AccessError("Недостатньо прав: потрібна група «%s»." % names)
```

### M-01 `td.yard.visit` — рейс сторонньої фури (FR-01, CY-01)

```python
class F3dYardVisit(models.Model):
    _name = "td.yard.visit"
    _description = "Двір: рейс фури"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_start desc, arrived_at desc, id desc"
    _rec_name = "name"
    _rec_names_search = ["name", "plate", "plate_norm", "scene_code"]
    _check_company_auto = True
    STATES = [("draft", "Чернетка"), ("planned", "Заплановано"), ("arrived", "Прибула"), ("queued", "У черзі"),
              ("at_dock", "Біля воріт"), ("handling", "Операція"), ("weighed", "Зважена"), ("left", "Виїхала"),
              ("rejected", "Відхилена"), ("cancelled", "Скасована")]
    ACTIVE_STATES = ("arrived", "queued", "at_dock", "handling", "weighed")   # фура фізично на території
    TRANSITIONS = {  # §10.1
        "draft": {"planned", "arrived", "rejected", "cancelled"},
        "planned": {"draft", "arrived", "rejected", "cancelled"},
        "arrived": {"queued", "rejected"},
        "queued": {"at_dock", "handling", "left"},
        "at_dock": {"handling", "weighed", "left"},
        "handling": {"weighed", "left"},
        "weighed": {"left"},
        "left": set(), "rejected": set(), "cancelled": {"draft"},
    }
    TS_FIELD = {"planned": "planned_at", "arrived": "arrived_at", "queued": "admitted_at", "at_dock": "at_dock_at",
                "handling": "handling_start_at", "weighed": "weighed_out_at", "left": "left_at",
                "rejected": "rejected_at", "cancelled": "cancelled_at", "draft": None}
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char(32) | `req`, `ro`, `copy=False`, `idx`, `default="/"`, `string="Рейс"`; у `create` — `ir.sequence.next_by_code("td.yard.visit")` → `YV/2026/00001` (R-01) |
| `company_id` | Many2one `res.company` | `req`, `idx`, `default=lambda s: s.env.company`, `string="Компанія"` |
| `visit_type` | Selection | `[('incoming','Приймання'),('outgoing','Відвантаження'),('other','Інше')]`, `req`, `default='incoming'`, `tracking=True`, `string="Тип"` |
| `state` | Selection `STATES` | `req`, `default='draft'`, `idx`, `ro`, `tracking=True`, `copy=False`, `group_expand="_group_expand_states"`, `string="Стан"` |
| `priority` | Selection | `[('0','Звичайний'),('1','Терміново')]`, `default='0'`, `string="Пріоритет"` (R-05) |
| `is_walk_in` | Boolean | `default=False`, `ro`, `copy=False`, `string="Без броні"`, `help="Рейс створено на КПП для фури без бронювання (R-06)"` |
| `partner_id` | Many2one `res.partner` | `string="Постачальник / клієнт"`, `check_company=True`, `tracking=True`, `ondelete="restrict"` |
| `carrier_id` | Many2one `res.partner` | `string="Перевізник"`, `domain="[('is_company','=',True)]"`, `tracking=True`, `ondelete="restrict"`, `idx` (CY-01, A-04) |
| `delivery_carrier_id` | Many2one `delivery.carrier` | `string="Спосіб доставки"`, `ondelete="set null"`, `help="З документа відвантаження (stock.picking.carrier_id)"` |
| `driver_id` | Many2one `res.partner` | `string="Водій"`, `domain="[('is_company','=',False)]"`, `tracking=True`, `ondelete="restrict"` (CY-07) |
| `driver_phone` | Char(32) | `string="Телефон водія"`, `groups=GRP_SEC`, `copy=False` (PII, R-22) |
| `driver_doc` | Char(32) | `string="Документ водія"`, `groups=GRP_SEC`, `copy=False`, `help="Серія й номер посвідчення водія; без копій документа"` (PII, R-22) |
| `pii_cleared` | Boolean | `ro`, `default=False`, `copy=False`, `groups=GRP_SEC`, `string="Персональні дані очищено"` (R-22) |
| `plate` | Char(16) | `string="Держномер"`, `tracking=True`, `copy=False`; перевірка `_check_plate` (R-08) |
| `plate_norm` | Char(16) | `compute="_compute_plate_norm"`, `store=True`, `idx`, `string="Номер (нормалізований)"`: `tools.plate.normalize_plate(plate)` |
| `plate_display` | Char | `compute`, не зберігається: `tools.plate.display_plate(plate)` (`АА4512КТ` → `АА 4512 КТ`) |
| `batch_id` | Many2one `stock.picking.batch` | `string="Пакет (документи)"`, `idx`, `check_company=True`, `ondelete="set null"`, `tracking=True`, `domain="[('picking_type_code','in',('incoming','outgoing'))]"` |
| `picking_ids` | Many2many `stock.picking` | `compute="_compute_picking_ids"`, не зберігається: `batch_id.picking_ids`; `string="Документи"` |
| `picking_count` | Integer | `compute="_compute_picking_ids"` |
| `scene_code` | Char(32) | `related="batch_id.td_code"`, `store=True`, `idx`, `string="Код фури в 3D"` (CB-06) |
| `booking_ids` | One2many `td.yard.booking` `visit_id` | `string="Бронювання"` |
| `booking_id` | Many2one `td.yard.booking` | `compute="_compute_booking_id"`, `store=True`, `idx`, `string="Чинне бронювання"`: серед `booking_ids` зі `state='confirmed'` — з найпізнішим `slot_start`; немає → `False`. `@api.depends("booking_ids.state", "booking_ids.slot_start")` |
| `dock_id` | Many2one `stock.location` | `related="booking_id.dock_id"`, `store=True`, `idx`, `string="Ворота"` |
| `dock_code` | Char | `related="dock_id.td_code"`, `string="Код воріт"` |
| `planned_start` | Datetime | `related="booking_id.slot_start"`, `store=True`, `idx`, `string="План: початок"` |
| `planned_end` | Datetime | `related="booking_id.slot_end"`, `store=True`, `string="План: кінець"` |
| `side` | Selection | `[('west','Захід (приймання)'),('east','Схід (відвантаження)')]`, `compute="_compute_side"`, `store=True`, `idx`, `string="Сторона"`: `dock_id.td_side` або (`incoming`/`other` → `west`, `outgoing` → `east`) |
| `weighing_policy` | Selection | `[('none','Без зважування'),('in_out','На в\'їзді й виїзді')]`, `req`, `string="Зважування"`, `tracking=True`; умовчання в `create` за R-01 |
| `gate_in_id` | Many2one `td.yard.gate` | `ro`, `string="КПП в'їзду"`, `ondelete="set null"` — ворота події/дії «Прибула» |
| `gate_out_id` | Many2one `td.yard.gate` | `ro`, `string="КПП виїзду"`, `ondelete="set null"` |
| `planned_at` | Datetime | `ro`, `copy=False`, `string="Заплановано о"` |
| `arrived_at` | Datetime | `ro`, `copy=False`, `idx`, `string="Прибула о"` |
| `admitted_at` | Datetime | `ro`, `copy=False`, `string="Пропущено о"` (перехід у `queued`) |
| `at_dock_at` | Datetime | `ro`, `copy=False`, `string="Біля воріт з"` |
| `handling_start_at` | Datetime | `ro`, `copy=False`, `string="Операція з"` |
| `handling_end_at` | Datetime | `ro`, `copy=False`, `string="Операція до"` |
| `weighed_in_at` | Datetime | `ro`, `copy=False`, `string="Зважено на в'їзді"` |
| `weighed_out_at` | Datetime | `ro`, `copy=False`, `string="Зважено на виїзді"` |
| `left_at` | Datetime | `ro`, `copy=False`, `idx`, `string="Виїхала о"` |
| `rejected_at`, `cancelled_at` | Datetime | `ro`, `copy=False`, `string="Відхилено о"` / `"Скасовано о"` |
| `reject_reason` | Text | `ro`, `copy=False`, `string="Причина відхилення"` |
| `day` | Date | `compute="_compute_day"`, `store=True`, `idx`, `string="День"`: `tools.tz.local_day(planned_start or arrived_at or create_date)` (Київ) |
| `weighing_ids` | One2many `td.yard.weighing` `visit_id` | `string="Зважування"` |
| `gross_kg`, `tare_kg`, `net_kg` | Float | `digits=(12,1)`, `compute="_compute_weights"`, `store=True`, `string="Брутто, кг"` / `"Тара, кг"` / `"Нетто, кг"` (R-12) |
| `expected_kg` | Float | `digits=(12,1)`, `compute="_compute_weights"`, `store=True`, `string="Маса за документами, кг"` |
| `deviation_kg` | Float | `digits=(12,1)`, `compute="_compute_weights"`, `store=True`, `string="Відхилення, кг"` (`net − expected`) |
| `deviation_pct` | Float | `digits=(6,2)`, `compute="_compute_weights"`, `store=True`, `string="Відхилення, %"` |
| `weight_check` | Selection | `[('none','Не зважено'),('ok','У допуску'),('deviation','Відхилення'),('no_reference','Немає еталона')]`, `compute="_compute_weights"`, `store=True`, `string="Звірка ваги"` |
| `lpr_event_ids` | One2many `td.yard.lpr.event` `visit_id` | `string="Розпізнавання номерів"`, `groups=GRP_SEC` |
| `wait_min`, `dock_min`, `total_min`, `late_min` | Float | `digits=(8,1)`, `compute="_compute_durations"`, `store=True`, `group_operator="avg"`, `string="Очікування, хв"` / `"Біля воріт, хв"` / `"Загалом, хв"` / `"Запізнення, хв"` (R-19) |
| `is_no_show` | Boolean | `ro`, `default=False`, `copy=False`, `idx`, `string="Не приїхала"` (R-19) |
| `progress` | Float | `compute="_compute_progress"`, не зберігається, `string="Виконано"`: `Σ move.quantity / Σ move.product_uom_qty` (рухи документів пакета, `state != 'cancel'`; знаменник 0 → 0) — як viewer R-09 |
| `note` | Text | `string="Примітка"` |

SQL-обмеження:

```python
    _f3d_yard_visit_name_uniq = models.Constraint("UNIQUE(company_id, name)", "Номер рейсу має бути унікальним.")
```

`@api.constrains`:
- `plate` — `_check_plate`: непорожній `plate` після `strip().upper()` має відповідати
  `tools.plate.PLATE_INPUT_RE = ^[A-ZА-ЯІЇЄҐ0-9 \-]{2,16}$` і давати `normalize_plate()` довжиною 2…12 →
  інакше `ValidationError("Держномер «%s»: лише літери, цифри, пробіл і дефіс, 2–16 символів.")`. Значення
  зберігається як `plate.strip().upper()` (у `create`/`write`).
- `batch_id` — `_check_batch_unique`: інший рейс у станах ≠ {`left`,`rejected`,`cancelled`} з тим самим `batch_id`
  → `ValidationError("Пакет %s уже має активний рейс %s.")`.
- `batch_id`, `visit_type` — тип пакета (`batch_id.picking_type_code`) має відповідати `visit_type`
  (`incoming`↔`incoming`, `outgoing`↔`outgoing`; `other` — будь-який) → `ValidationError("Тип рейсу «%s» не
  збігається з типом операцій пакета %s.")`.

Обчислення:
- `_compute_weights` (`@api.depends("weighing_ids.weight_kg", "weighing_ids.kind", "weighing_ids.state",
  "weighing_ids.ts", "visit_type", "batch_id.picking_ids.move_ids.product_qty",
  "batch_id.picking_ids.move_ids.quantity", "batch_id.picking_ids.move_ids.product_id.weight",
  "batch_id.picking_ids.state")`) — R-12 кроки 1–4.
- `_compute_durations` (`@api.depends("arrived_at", "at_dock_at", "handling_end_at", "weighed_out_at",
  "left_at", "planned_start")`) — R-19.

Методи (CY-01; усі публічні дії — `ensure_one()` якщо не сказано інше; кожен перехід — через `_set_state`):

| Сигнатура | Права | Алгоритм |
|---|---|---|
| `create(vals_list)` | ACL | R-01: `name` з послідовності; `weighing_policy` (якщо не задано) = `P.weighing_policy_west` / `P.weighing_policy_east` за `side`, обчисленим з `visit_type` (`other` → west); `plate` → `strip().upper()`; після `super()` — `_td_yard_notify()` |
| `write(vals)` | ACL | `plate` → `strip().upper()`; заборонено змінювати `visit_type`, `batch_id` у станах ∉ {`draft`,`planned`,`arrived`} → `UserError("Тип і пакет змінюються лише до пропуску фури.")`; після `super()`: якщо змінено `plate`, `batch_id`, `priority` → `_td_yard_notify()` |
| `unlink()` | ACL | лише стани {`draft`,`planned`,`cancelled`}; інакше `UserError("Рейс у стані «%s» видаляти не можна — скасуйте або відхиліть його.")`; бронювання видаляються каскадно |
| `_set_state(new, ts=None, gate=None, note=None)` | — (внутрішній) | 0) `SELECT state FROM td_yard_visit WHERE id=%s FOR UPDATE` і `invalidate_recordset(['state'])` (§11.8); 1) `new ∈ TRANSITIONS[state]` інакше `UserError("Перехід «%s» → «%s» неможливий.")` (підписи станів); 2) `vals = {'state': new}`; `ts = ts or now`; якщо `TS_FIELD[new]` і поле порожнє — `vals[field] = ts` (повторний перехід не перезаписує); 3) `queued→handling`: також `at_dock_at = ts`, якщо порожній; 4) `new='arrived'` і `gate` → `gate_in_id`; 5) `self.sudo().write(vals)` (права перевірено викликачем); 6) чаттер `"Стан: %s → %s (%s)%s" % (old_label, new_label, local_hm(ts), note and " · " + note or "")`; 7) `_td_yard_notify()`; повертає `True` |
| `action_plan()` | `GRP_DISP` | `draft → planned`; потрібне `booking_id` (підтверджене) інакше `UserError("Спершу підтвердіть бронювання воріт.")` |
| `action_arrive(ts=None, gate=None, event=None)` | `GRP_SEC` | `draft\|planned → arrived`; `gate` = переданий або `td.yard.gate` з `direction in ('in','both')` і `side` рейсу (за замовчуванням `GATE-W`, iot_sim R-29: в'їзд через GATE-W); `event` → `event.visit_id = self`, `match_state='matched'`; повертає `True` |
| `action_admit(open_gate=True)` | `GRP_SEC` | `arrived → queued` (перехід виконується завжди, FR-28). Якщо `open_gate` і `gate_in_id`: якщо `P.write_enabled` і ворота мають сигнал `cmd_open` → `gate_in_id.action_command('open', visit=self, reason='manual')` у `try`; `UserError` R-15 (несвіжі дані, перешкода, попередня команда) → команда не створюється, `gate_in_id._td_yard_count_permit(self)`, чаттер «Команду не надіслано: <текст>. Відкрийте шлагбаум з пульта CAME»; без `write_enabled` — `_td_yard_count_permit(self)` і чаттер «Шлагбаум відкрийте з пульта CAME (команди вимкнено)». Повертає `display_notification`: `type='success'`, «Фуру %s пропущено» (команда надіслана) або `type='warning'` з текстом причини |
| `action_call_to_dock(dock=None)` | `GRP_SEC` | R-05 «виклик»: лише з `queued` (`UserError("Викликати на ворота можна лише фуру в черзі.")`); ворота: є `booking_id` → `booking_id.dock_id` (переданий `dock` інший → `UserError("Рейс заброньовано на %s.")`); немає → `dock` або `_td_yard_pick_dock()`; `None` → `UserError("Немає вільних воріт на стороні «%s».")`; ворота зайняті іншим рейсом (`_td_yard_dock_busy`) → `UserError("Ворота %s зайняті рейсом %s.")`; без броні — створити бронювання `source='walk_in'`, `[now, now + P.slot_default_min]` і `action_confirm()` (A-23; `ValidationError` конфлікту → `UserError("Ворота %s зайняті: %s")`); `_set_state('at_dock')` |
| `action_start_handling(auto=False)` | `GRP_SEC` або `stock.group_stock_user` | `queued\|at_dock → handling`; `auto=True` (R-09) — без перевірки прав, нотатка «автоматично: почато приймання/відвантаження в документі» |
| `action_end_handling(auto=False)` | `GRP_SEC` або `stock.group_stock_user` | лише стан `handling`; `handling_end_at = now`, якщо порожній; стан не змінюється; чаттер; якщо `P.auto_call_next` → `_td_yard_call_next(dock_id)` (R-05) |
| `action_weigh()` | `GRP_SEC` або `stock.group_stock_user` | лише стани {`queued`,`at_dock`,`handling`}; якщо ваги `TRUCK-SCALE` (`gate_out_id.scale_id` або перша `td.yard.scale`) мають свіже стабільне показання (R-10) → `scale.action_capture(visit=self)` і сповіщення «Записано %s кг»; інакше — дія `td.yard.weighing` форма `target='new'` з `context={'default_visit_id': id, 'default_scale_id': scale.id, 'default_kind': 'in' if not weighed_in_at else 'out', 'default_source': 'manual'}` |
| `action_leave(ts=None, note=None)` | `GRP_SEC` | `queued\|at_dock\|handling\|weighed → left`; `left_at = ts or now`; якщо `weighing_policy='in_out'` і немає зважування `out` → чаттер «Виїзд без зважування на виїзді»; якщо документи пакета не в `done/cancel` → чаттер «Документи не завершені: WH/IN/00128»; якщо `P.auto_call_next` і був `dock_id` → `_td_yard_call_next(dock_id)` |
| `action_reject_wizard()` | `GRP_SEC` | дія `td.yard.reject.wizard` (`target='new'`, `default_visit_id`) |
| `_do_reject(reason)` | — | з M-17: `draft\|planned\|arrived → rejected`, `reject_reason = reason`, `rejected_at`; бронювання `confirmed/requested` → `action_cancel()`; події LPR рейсу з `kpp_alert` → `kpp_alert=False`, `match_state='handled'` |
| `action_cancel()` | `GRP_DISP` | `draft\|planned → cancelled`; бронювання → `cancelled` |
| `action_draft()` | `GRP_DISP` | `cancelled → draft`; часові мітки не чистяться |
| `action_show_3d()` | read | `batch_id.action_f3d_show()` якщо `scene_code`; інакше `dock_id.action_f3d_show()` якщо `dock_id.td_code`; інакше `gate_in_id.action_f3d_show()`; інакше `UserError("Рейс не має об'єкта в 3D.")` (C-05 через CB-01) |
| `action_open_batch()` / `action_open_pickings()` | read | `act_window` на пакет / список документів (`domain=[('id','in',picking_ids.ids)]`) |
| `@api.model _find_by_plate(plate_norm, ts, direction='in')` | — | R-08 крок 6: повертає recordset кандидатів, упорядкований |
| `@api.model _td_yard_queue(side, dock=None)` | — | R-05: упорядкований recordset |
| `@api.model _td_yard_call_next(dock)` | — | R-05: перший з `_td_yard_queue(dock.td_side, dock)` → `action_call_to_dock(dock)` під `sudo()`; нікого → `False` |
| `_td_yard_pick_dock()` | — | R-05 вибір вільних воріт |
| `@api.model _td_yard_dock_busy(dock, start, end, exclude=None)` | — | R-05 → `self`-recordset рейсу-зайняття або порожній |
| `_compute_weights()`, `_td_yard_write_pickings()` | — | R-12 |
| `_td_yard_notify()` | — | R-21 |
| `@api.model _td_yard_viewer_event()` | — | `self.env['td.viewer.event'].sudo()` якщо `'td.viewer.event' in self.env`, інакше `None` (тести патчать, AC-64; так само на M-03, M-06) |
| `@api.model f3d_yard_run_migration()` | `td_factory3d.group_td_admin` | серверна дія V-34: `hooks.run_all(env)` → `display_notification` зі звітом |
| `@api.model kpp_data(gate_ids=None)` | `GRP_SEC` | API-01 (R-18) |
| `@api.model kpp_action(action, visit_id=None, event_id=None, gate_id=None, values=None)` | `GRP_SEC` | API-02 (R-18) |
| `@api.model _cron_queue()` | крон | R-05 (`auto_call_next`), R-16 (утримання, таймаути, стан воріт), R-19 («не приїхала»), R-07 (прострочені незбіги) |
| `@api.model _cron_gc()` | крон | R-22 |
| `@api.model _cron_day_reset()` | крон | R-23 |
| `_group_expand_states(states, domain)` | — | `['planned','arrived','queued','at_dock','handling','weighed','left']` |

### M-02 `td.yard.booking` — бронювання воріт (FR-02…FR-04, A-01)

```python
class F3dYardBooking(models.Model):
    _name = "td.yard.booking"
    _description = "Двір: бронювання воріт"
    _inherit = ["mail.thread"]
    _order = "slot_start, dock_id"
    _check_company_auto = True
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | `compute="_compute_name"`, `store=True`: `"%s · %s–%s" % (dock_id.td_code or dock_id.name, local "dd.mm HH:MM" slot_start, local "HH:MM" slot_end)` → `DOCK-W2 · 12.10 13:00–14:00` |
| `company_id` | Many2one `res.company` | `req`, `idx`, `default=lambda s: s.env.company` |
| `visit_id` | Many2one `td.yard.visit` | `idx`, `ondelete="cascade"`, `check_company=True`, `string="Рейс"`, `tracking=True` (не обов'язкове: запит постачальника без рейсу — Q-06) |
| `dock_id` | Many2one `stock.location` | `req`, `idx`, `check_company=True`, `domain="[('td_kind','=','dock')]"`, `tracking=True`, `string="Ворота"`, `ondelete="restrict"` |
| `dock_code` | Char | `related="dock_id.td_code"` |
| `side` | Selection | `related="dock_id.td_side"`, `store=True` |
| `slot_start` | Datetime | `req`, `idx`, `tracking=True`, `string="Початок"` |
| `slot_end` | Datetime | `req`, `idx`, `tracking=True`, `string="Кінець"`; `@api.onchange('slot_start')`: порожній або ≤ початку → `slot_start + P.slot_default_min` |
| `duration_min` | Integer | `compute`, не зберігається: `(slot_end − slot_start)` у хвилинах |
| `day` | Date | `compute`, `store=True`, `idx`, `string="День"`: `tools.tz.local_day(slot_start)` (Київ) |
| `source` | Selection | `[('dispatcher','Диспетчер'),('supplier','Постачальник'),('walk_in','Без броні (КПП)'),('migration','Міграція')]`, `req`, `default='dispatcher'`, `string="Джерело"` |
| `state` | Selection | `[('requested','Запит'),('confirmed','Підтверджено'),('cancelled','Скасовано')]`, `req`, `default='requested'`, `idx`, `tracking=True`, `copy=False` |
| `batch_id` | Many2one | `related="visit_id.batch_id"` |
| `partner_id` | Many2one | `related="visit_id.partner_id"` |
| `plate` | Char | `related="visit_id.plate"` |
| `visit_type` | Selection | `related="visit_id.visit_type"`, `store=True` |
| `visit_state` | Selection | `related="visit_id.state"` |
| `side_hint` | Selection `[('west','Захід'),('east','Схід')]` | `compute`, не зберігається: `visit_id.side` — для домену воріт у V-07 |
| `color` | Integer | `compute`, `store=True`: `incoming` → 4, `outgoing` → 2, `source='walk_in'` → 3, інакше 0 (Gantt) |
| `warning` | Char | `compute="_compute_warning"`, не зберігається: R-03 (буфер, календар) + R-04 (категорії), рядки через `"\n"`; порожньо → `False` |
| `note` | Text | `string="Примітка"` |

```python
    _f3d_yard_booking_slot = models.Constraint("CHECK(slot_end > slot_start)", "Кінець слоту має бути пізніше за початок.")
```

`@api.constrains("dock_id", "slot_start", "slot_end", "state")` `_check_overlap` — R-03 п. 1–3;
`@api.constrains("dock_id", "visit_id")` `_check_dock_side` — R-03 п. 4; `@api.constrains("slot_start", "slot_end")`
— тривалість ≤ 24 год (`"Слот довший за 24 год."`); `enforce_calendar=True` і слот поза зміною — R-03 п. 6.

| Сигнатура | Права | Алгоритм |
|---|---|---|
| `action_confirm()` | `GRP_DISP` (або `sudo` з R-05/R-24) | для кожного `requested`: `SELECT id FROM stock_location WHERE id=%s FOR UPDATE` (серіалізація підтверджень одних воріт); `state='confirmed'` (обмеження перевіряють конфлікт); `_sync_batch()` (R-02); `visit_id.state == 'draft'` → `visit_id._set_state('planned')`; чаттер рейсу «Заброньовано %s» |
| `action_cancel()` | `GRP_DISP` (з M-01 — `sudo`) | `requested\|confirmed → cancelled`; якщо рейс `planned` і в нього не лишилось `confirmed` → `visit._set_state('draft')` |
| `action_reset()` | `GRP_DISP` | `cancelled → requested` |
| `write(vals)` | ACL | після `super()`: для `confirmed`, якщо змінено `dock_id`/`slot_start`/`slot_end` і немає `context['f3d_yard_sync']` → `_sync_batch()`; `visit_id._td_yard_notify()` |
| `_sync_batch()` | — | R-02 (у `sudo()` і `with_context(f3d_yard_sync=True)`) |
| `@api.model _td_yard_overlaps(dock, start, end, exclude_ids=())` | — | `search([('dock_id','=',dock.id), ('state','=','confirmed'), ('slot_start','<',end), ('slot_end','>',start), ('id','not in',exclude_ids)])` |

### M-03 `td.yard.gate` — КПП / шлагбаум (FR-15, CY-03)

```python
class F3dYardGate(models.Model):
    _name = "td.yard.gate"
    _inherit = ["td.scene.mixin", "mail.thread"]
    _description = "Двір: КПП і шлагбаум"
    _order = "sequence, td_code"
    _rec_name = "name"
    _rec_names_search = ["name", "td_code", "camera_code"]
    _td_kind = "other"
    STATES = [("closed", "Закритий"), ("open", "Відкритий"), ("held", "Утримується відкритим"),
              ("error", "Помилка"), ("unknown", "Невідомо")]
```

| Поле | Тип | Параметри |
|---|---|---|
| `td_code` | Char(32) | перевизначення домішки: `req` (`GATE-W`, `GATE-E`; CB-01 R-01 формат) |
| `name` | Char(64) | `req`, `string="Назва"` |
| `sequence` | Integer | `default=10` |
| `active` | Boolean | `default=True` |
| `company_id` | Many2one `res.company` | `req`, `default=lambda s: s.env.company` |
| `direction` | Selection | `[('in','В\'їзд'),('out','Виїзд'),('both','В\'їзд і виїзд')]`, `req`, `string="Напрямок"` |
| `side` | Selection | `[('west','Захід'),('east','Схід')]`, `req`, `string="Сторона"` |
| `pos_x`, `pos_y` | Float | `digits=(8,2)`, `string="X, м"` / `"Y, м"` (CB-04; `plant/infra.py:GATES`, огорожа `y=−30`) |
| `equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання"`, `ondelete="set null"` (`GATE-W`) |
| `zone_id` | Many2one `td.zone` | `string="Зона"`, `ondelete="set null"` (`Z-GATE-W`) |
| `camera_code` | Char(32) | `idx`, `string="Камера LPR"`, `help="sensorProviderID камери Axis (CAM-05)"`; унікальний серед активних (`_check_camera`) |
| `camera_equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання камери"`, `ondelete="set null"` (`CCTV` — камери окремих одиниць не мають, base Додаток F) |
| `scale_id` | Many2one `td.yard.scale` | `string="Ваги"`, `ondelete="set null"` |
| `source_id` | Many2one `td.source` | `string="Модуль I/O"`, `ondelete="set null"` (`MB-U86-IO7`) |
| `state_signal_id`, `loop_signal_id`, `photocell_signal_id`, `passes_signal_id`, `cmd_open_signal_id`, `cmd_close_signal_id`, `cmd_hold_signal_id` | Many2one `td.signal` | `ondelete="set null"`, `string="Сигнал: стріла відкрита"` / `"…петля"` / `"…фотоелемент"` / `"…лічильник проїздів"` / `"Команда: відкрити"` / `"…закрити"` / `"…тримати"`; ставить хук (Додаток A) |
| `invert_di` | Boolean | `default=False`, `string="Інверсія входів"`, `help="Контакти NC: 0 = активний стан (ризик монтажу ARCH §5.3)"` |
| `mode` | Selection | `[('auto','Авто'),('manual','Ручний')]`, `req`, `default='manual'`, `tracking=True`, `string="Режим"` |
| `state` | Selection `STATES` | `req`, `default='unknown'`, `ro`, `idx`, `string="Стан"` (A-21; R-16) |
| `state_since` | Datetime | `ro` |
| `last_error` | Char(256) | `ro`, `string="Помилка"` |
| `responsible_id` | Many2one `res.users` | `string="Відповідальний (охорона)"`, `help="Кому ставиться активність при помилці воріт"` |
| `loop_occupied` | Boolean | `ro`, службове (R-17) |
| `photocell_blocked` | Boolean | `ro`, службове — останнє свіже значення фотоелемента |
| `counter_value` | Integer | `ro`, службове — останнє значення лічильника ADAM |
| `passes_day_start` | Integer | `ro`, службове — лічильник на початок доби (R-23) |
| `passes_today` | Integer | `ro`, `string="Проїздів сьогодні"` |
| `admitted_today` | Integer | `ro`, `string="Дозволів сьогодні"` |
| `tailgate_today` | Integer | `ro`, `string="Проїздів без дозволу"` |
| `last_tailgate_at` | Datetime | `ro` |
| `last_plate` | Char(16) | `ro`, `string="Останній номер"`, `groups=GRP_SEC` |
| `last_plate_at` | Datetime | `ro` |
| `pending_visit_id` | Many2one `td.yard.visit` | `ro`, `ondelete="set null"`, `string="Очікує проїзду"` (R-17) |
| `open_cmd_id` | Many2one `td.command` | `ro`, `ondelete="set null"` — остання команда «відкрити» під контролем таймауту (R-16) |
| `opened_at` | Datetime | `ro` — останній перехід DI «відкрито» 0→1 |
| `hold_until` | Datetime | `ro`, `string="Утримання до"` |
| `last_command_id` | Many2one `td.command` | `ro`, `ondelete="set null"` |
| `command_ids` | One2many `td.command` `td_yard_gate_id` | `string="Команди"` |
| `can_command` | Boolean | `compute="_compute_can_command"`, не зберігається |
| `command_block_reason` | Char | `compute="_compute_can_command"`: перша причина R-15 п. 2–6 (без конкретної команди — для `open`) або `False` |
| `note` | Text | |

`@api.constrains("camera_code", "active")` → дубль серед активних воріт → `ValidationError("Камера %s уже призначена воротам %s.")`.

| Сигнатура | Права | Алгоритм |
|---|---|---|
| `action_command(kind, visit=None, reason='manual')` | `GRP_SEC` при `reason='manual'` | R-15 → `td.command` |
| `action_open()`, `action_close()`, `action_hold()`, `action_release()` | `GRP_SEC` | `action_command('open'\|'close'\|'hold'\|'release')`; повертають `display_notification` «Команду надіслано» |
| `action_opened_manually()` | `GRP_SEC` | «Відкрито вручну»: `_td_yard_count_permit(pending_visit_id or None)`; `last_error=False`; `state` перераховується (R-16); чаттер «Відкрито з пульта CAME (%s)» з ім'ям користувача |
| `action_reset_error()` | `GRP_SEC` | `last_error=False`, `open_cmd_id=False`, `_td_yard_refresh_state()` |
| `_td_yard_count_permit(visit=None)` | — | `admitted_today += 1`; `visit` → `pending_visit_id = visit` |
| `_td_yard_on_readings(items)` | — | з M-13: `items = [(role, ts, value, q)]` за `ts` → R-17 (петля, лічильник) → `_td_yard_refresh_state()` |
| `_td_yard_refresh_state(now=None)` | — | R-16 |
| `_td_yard_auto_open(visit, event=None)` | — (внутрішній) | R-15 п. «авто»: перевірки умов авто-відкриття; виклик `action_command('open', visit, reason='auto_booking'\|'auto_exit')` у `try/except UserError` → у разі відмови `event.note = текст`, `event.kpp_alert = True` |
| `action_view_commands()` | read | `act_window` `td.command` `domain=[('td_yard_gate_id','=',id)]` |

### M-04 `td.yard.lpr.event` — подія розпізнавання номера (FR-07, FR-08)

```python
class F3dYardLprEvent(models.Model):
    _name = "td.yard.lpr.event"
    _description = "Двір: розпізнавання номера"
    _order = "ts desc, id desc"
    _log_access = False
    _rec_name = "plate_norm"
    MATCH = [("matched", "Зіставлено"), ("unmatched", "Без бронювання"), ("low_confidence", "Низька довіра"),
             ("unknown_camera", "Невідома камера"), ("ignored", "Ігноровано (читання вимкнено)"),
             ("handled", "Вирішено охороною"), ("expired", "Минув час")]
```

| Поле | Тип | Параметри |
|---|---|---|
| `ts` | Datetime | `req`, `idx`, `string="Час камери"` (UTC) |
| `received_at` | Datetime | `req`, `default=fields.Datetime.now`, `string="Отримано"` |
| `company_id` | Many2one `res.company` | `req`, `default=lambda s: s.env.company`, `idx` |
| `push_event_id` | Char(64) | `idx`, `string="Подія телеметрії"` (`event_id` M-13 telemetry) |
| `dedup_key` | Char(160) | `req`, `string="Ключ дубліката"` (R-07) |
| `camera_code` | Char(32) | `req`, `idx`, `string="Камера"` |
| `gate_id` | Many2one `td.yard.gate` | `idx`, `ondelete="set null"`, `string="КПП"` |
| `direction` | Selection | `[('in','В\'їзд'),('out','Виїзд'),('unknown','Невідомо')]`, `req`, `default='unknown'` |
| `car_state` | Selection | `[('new','Нова'),('update','Оновлення'),('lost','Зникла')]`, `req`, `default='new'` |
| `car_id` | Char(32) | `string="carID"` |
| `packet_counter` | Char(32) | |
| `plate_raw` | Char(32) | `string="Номер (plateText)"` |
| `plate_unicode` | Char(32) | `string="Номер (Unicode)"` |
| `plate_norm` | Char(16) | `idx`, `string="Номер"` |
| `plate_country` | Char(8) | |
| `confidence` | Float | `digits=(4,3)`, `string="Довіра"` (0…1) |
| `plate_list` | Char(32) | `string="Список камери"`, `help="Назва списку Axis LPV, у який потрапив номер (plateList), напр. f3d_bookings"` |
| `plate_list_mode` | Char(16) | `string="Режим списку"`, `help="plateListMode камери: allow / block / none"` (X-48, X-73) |
| `plate_list_description` | Char(256) | `string="Опис у списку камери"` |
| `image_attachment_id` | Many2one `ir.attachment` | `ondelete="set null"`, `string="Знімок"` |
| `image_url` | Char(512) | `string="Посилання на знімок"` |
| `image` | Binary | `related="image_attachment_id.datas"`, `string="Знімок"` (лише перегляд у формі) |
| `match_state` | Selection `MATCH` | `req`, `default='unmatched'`, `idx`, `string="Результат"` |
| `visit_id` | Many2one `td.yard.visit` | `idx`, `ondelete="set null"`, `string="Рейс"` |
| `kpp_alert` | Boolean | `idx`, `default=False`, `string="Потрібне рішення охорони"` |
| `lost_at` | Datetime | `string="Зникла з кадру"` |
| `handled_by` | Many2one `res.users` | `ondelete="set null"` |
| `handled_at` | Datetime | |
| `note` | Char(256) | `string="Пояснення"` |

```python
    _f3d_yard_lpr_dedup_uniq = models.Constraint("UNIQUE(dedup_key)", "Подія LPR з таким ключем уже є.")
```

`init()`: `tools.sql.create_index(cr, 'td_yard_lpr_event_plate_ts_idx', self._table, ['plate_norm', 'ts'])`.

| Сигнатура | Права | Алгоритм |
|---|---|---|
| `@api.model _td_from_push(event)` | — (з M-12, `sudo`) | R-07 → R-08 → дії після зіставлення; повертає запис або `False` |
| `_td_match()` | — | R-08 кроки 5–9 |
| `action_walk_in()` | `GRP_SEC` | дія `td.yard.walkin.wizard` (`target='new'`, `default_event_id`); лише для `match_state in ('unmatched','low_confidence')` і `direction != 'out'` |
| `action_link_visit(visit_id)` | `GRP_SEC` | ручна прив'язка: `visit_id` (у станах R-08 п. 6 за напрямком) → `visit_id`, `match_state='handled'`, `kpp_alert=False`, `handled_by/at`; порожній номер рейсу ← `plate_unicode or plate_raw`; для `in` і рейсу `planned\|draft` → `visit.action_arrive(ts, gate_id, self)` |
| `action_dismiss()` | `GRP_SEC` | `kpp_alert=False`, `match_state='handled'` (якщо було `unmatched/low_confidence`), `handled_by/at` |
| `action_reject()` | `GRP_SEC` | дія `td.yard.reject.wizard` з `default_event_id` (фура без рейсу: створює рейс `rejected` для журналу — M-17) |

### M-05 `td.yard.weighing` — зважування (FR-11, FR-12)

```python
class F3dYardWeighing(models.Model):
    _name = "td.yard.weighing"
    _description = "Двір: зважування"
    _inherit = ["mail.thread"]
    _order = "ts desc, id desc"
    _check_company_auto = True
```

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char(32) | `req`, `ro`, `copy=False`, `default="/"`; `create` → `ir.sequence` `td.yard.weighing` (`WG/2026/00001`) |
| `company_id` | Many2one `res.company` | `req`, `default=lambda s: s.env.company`, `idx` |
| `scale_id` | Many2one `td.yard.scale` | `req`, `idx`, `ondelete="restrict"`, `string="Ваги"` |
| `ts` | Datetime | `req`, `idx`, `default=fields.Datetime.now`, `string="Час"` |
| `kind` | Selection | `[('in','В\'їзд'),('out','Виїзд'),('check','Контрольне')]`, `req`, `string="Вид"` |
| `weight_kg` | Float | `req`, `digits=(12,1)`, `string="Вага, кг"`, `tracking=True` |
| `stable` | Boolean | `default=True`, `string="Стабільно"` |
| `source` | Selection | `[('auto','Автоматично'),('manual','Вручну'),('migration','Міграція')]`, `req`, `default='manual'` |
| `state` | Selection | `[('assigned','Призначено'),('unassigned','Непризначене'),('void','Анульовано')]`, `req`, `default='assigned'`, `idx`, `tracking=True` |
| `visit_id` | Many2one `td.yard.visit` | `idx`, `ondelete="set null"`, `check_company=True`, `tracking=True`, `string="Рейс"` |
| `role` | Selection | `[('gross','Брутто'),('tare','Тара'),('check','Контроль')]`, `compute="_compute_role"`, `store=True`, `string="Роль"` (R-12 п. 1) |
| `picking_id` | Many2one `stock.picking` | `ondelete="set null"`, `string="Документ"` — перший документ пакета рейсу за `name` (або з міграції) |
| `plate` | Char(16) | `string="Держномер"` — копія `visit_id.plate` при створенні/призначенні |
| `user_id` | Many2one `res.users` | `default=lambda s: s.env.user`, `ro`, `string="Хто записав"` |
| `note` | Char(256) | |

```python
    _f3d_yard_weighing_nonneg = models.Constraint("CHECK(weight_kg >= 0)", "Вага не може бути від'ємною.")
```

`@api.constrains("weight_kg", "scale_id", "source")`: для `source in ('manual','auto')`: `scale_id.min_kg ≤ weight_kg ≤
scale_id.max_kg` інакше `ValidationError("Вага %s кг поза межами ваг %s: %s…%s кг.")` (`400…60000`); `ts > now + 60 с`
→ `ValidationError("Час зважування в майбутньому.")`; `kind != 'check'` і `visit_id` вже має інше `assigned`
зважування того ж `kind` → `ValidationError("Рейс %s уже має зважування «%s» (%s кг). Анулюйте його спершу.")`.

| Сигнатура | Права | Алгоритм |
|---|---|---|
| `create(vals_list)` | ACL (`GRP_SEC`; `stock.group_stock_user` — через `visit.action_weigh` форму) | `name`; `state = 'assigned' if visit_id else 'unassigned'`; `plate` з рейсу; після `super()`: `_td_yard_apply()` |
| `_td_yard_apply()` | — | для `assigned` з рейсом: `kind='in'` → `visit.weighed_in_at = ts` (якщо порожній); `kind='out'` → якщо стан рейсу ∈ {`at_dock`,`handling`} і `weighing_policy='in_out'` → `visit._set_state('weighed', ts)`; `handling_end_at` порожній → `= ts`; далі `visit._td_yard_write_pickings()` (R-12) і `scale_id._td_yard_notify()` |
| `action_assign(visit_id, kind=None)` | `GRP_SEC` | лише `unassigned`: `visit_id`, `kind` (якщо задано), `state='assigned'`, `plate`; `_td_yard_apply()` |
| `action_assign_selected()` | `GRP_SEC` | кнопка форми: `action_assign(self.visit_id.id, self.kind)`; порожній `visit_id` → `UserError("Оберіть рейс.")` |
| `action_void()` | `GRP_SEC` | `state='void'`; рейс перераховує ваги (`_compute_weights`), `_td_yard_write_pickings()`; стан рейсу не відкочується (чаттер «Анульовано зважування %s») |

### M-06 `td.yard.scale` — автоваги (FR-15, A-09)

```python
class F3dYardScale(models.Model):
    _name = "td.yard.scale"
    _inherit = ["td.scene.mixin", "mail.thread"]
    _description = "Двір: автоваги"
    _order = "td_code"
    _rec_name = "name"
    _td_kind = "equipment"
```

| Поле | Тип | Параметри |
|---|---|---|
| `td_code` | Char(32) | `req` (`TRUCK-SCALE`) |
| `name` | Char(64) | `req` |
| `active` | Boolean | `default=True` |
| `company_id` | Many2one `res.company` | `req`, `default=lambda s: s.env.company` |
| `pos_x`, `pos_y` | Float | `digits=(8,2)` — `plant/infra.py:TRUCK_SCALE = (172.0, −14.0)` |
| `equipment_id` | Many2one `maintenance.equipment` | `ondelete="set null"` |
| `zone_id` | Many2one `td.zone` | `ondelete="set null"` (`Z-GATE-E`) |
| `source_id` | Many2one `td.source` | `ondelete="set null"` (`SICS-TRUCK-SCALE`) |
| `weight_signal_id`, `stable_signal_id` | Many2one `td.signal` | `ondelete="set null"` |
| `max_kg` | Float | `default=60000`, `string="НПВ, кг"` (`equipment_specs.json[role=truck_scale]`) |
| `min_kg` | Float | `default=400`, `string="НмПВ, кг"` |
| `division_kg` | Float | `default=20`, `string="Дискретність, кг"` |
| `auto_capture` | Boolean | `default=True`, `string="Автозахоплення"` |
| `capture_state` | Selection | `[('idle','Порожньо'),('settling','Стабілізація'),('captured','Зафіксовано'),('offline','Немає даних')]`, `req`, `default='idle'`, `ro` |
| `last_weight_kg` | Float | `ro`, `digits=(12,1)`, `string="Зараз, кг"` |
| `last_stable` | Boolean | `ro`, `string="Стабільно"` |
| `last_ts` | Datetime | `ro` |
| `candidate_kg` | Float | `ro`, службове (R-11) |
| `candidate_ts` | Datetime | `ro`, службове |
| `captured_kg` | Float | `ro`, службове — вага зафіксованого зважування |
| `last_weighing_id` | Many2one `td.yard.weighing` | `compute`, не зберігається: останнє `state != 'void'` за `ts` |
| `today_count` | Integer | `compute`, не зберігається: зважувань `state != 'void'` з `ts` у сьогоднішній добі (Київ) |

`@api.constrains("min_kg", "max_kg", "division_kg")`: `0 < min_kg < max_kg`, `division_kg > 0` →
`ValidationError("Межі ваг: 0 < НмПВ < НПВ, дискретність > 0.")`.

| Сигнатура | Права | Алгоритм |
|---|---|---|
| `_td_yard_on_readings(items)` | — | з M-13: `items = [(role, ts, value, q)]` → R-10, R-11 |
| `action_capture(visit=None)` | `GRP_SEC` або `stock.group_stock_user` | R-10 придатність поточного показання (`last_stable`, `now − last_ts ≤ P.weigh_max_age_s`, межі) інакше `UserError("Ваги не дають свіжого стабільного показання — введіть вагу вручну.")`; створює `td.yard.weighing` (`source='auto'`, `weight_kg = last_weight_kg`, `visit_id = visit` або R-11 п. 5) |
| `_td_yard_notify()` | — | R-21 |

### M-07 `stock.picking.batch` — розширення (FR-14, CY-02)

`_inherit = "stock.picking.batch"`.

| Поле | Тип | Параметри |
|---|---|---|
| `td_visit_ids` | One2many `td.yard.visit` `batch_id` | `string="Рейси"` |
| `td_visit_id` | Many2one `td.yard.visit` | `compute="_compute_f3d_visit"`, `store=True`, `idx`, `string="Активний рейс"`: рейс із `td_visit_ids`, стан ∉ {`left`,`rejected`,`cancelled`}, найбільший `id`; немає → останній `left` за `left_at`; немає → `False`. `@api.depends("td_visit_ids.state")` |
| `td_visit_state` | Selection | `related="td_visit_id.state"`, `string="Стан рейсу"` |
| `td_plate` | Char | `related="td_visit_id.plate"`, `string="Держномер (рейс)"`, `help="Держномер активного рейсу двору (td.yard.visit.plate). Код фури в 3D — td_code; td_truck — опис/назва фури з макета, не номер."` — єдине місце держномера на пакеті (X-15: код сцени — лише base `td_code` CB-06, `td_truck` — опис); читає емулятор (iot_sim API-01 `bookings[].plate`, X-49) |
| `td_visit_count` | Integer | `compute`, не зберігається |

| Сигнатура | Права | Алгоритм |
|---|---|---|
| `action_f3d_create_visit()` | `GRP_DISP` | `ensure_one()`; є активний рейс → відкрити його; `picking_type_code ∉ ('incoming','outgoing')` → `UserError("Рейс створюється лише для пакетів приймання або відвантаження.")`; `visit = create({'visit_type': picking_type_code, 'batch_id': id, 'partner_id': picking_ids[:1].partner_id.commercial_partner_id, 'delivery_carrier_id': picking_ids.carrier_id[:1], 'carrier_id': R-24 крок 4 правило, 'plate': False})`; якщо `dock_id` і `scheduled_date`: бронювання `requested` (`dock_id`, `slot_start=scheduled_date`, `slot_end=end_date or scheduled_date + P.slot_default_min`); відкрити форму рейсу |
| `action_f3d_open_visits()` | read | `act_window` рейсів пакета |
| `write(vals)` | ACL | R-02 зворотна синхронізація: після `super()`, якщо в `vals` є `dock_id`/`scheduled_date`/`end_date`, немає `context['f3d_yard_sync']` і `td_visit_id.booking_id.state == 'confirmed'` → `booking.with_context(f3d_yard_sync=True).sudo().write({'dock_id': dock_id.id, 'slot_start': scheduled_date, 'slot_end': end_date or scheduled_date + P.slot_default_min})` (конфлікт R-03 → `ValidationError` відкочує й запис пакета) |

### M-08 `stock.picking` — розширення (FR-12, FR-14, CY-02); M-08b `stock.move.line` (R-09)

`_inherit = "stock.picking"`.

| Поле | Тип | Параметри |
|---|---|---|
| `td_visit_id` | Many2one `td.yard.visit` | `related="batch_id.td_visit_id"`, `string="Рейс двору"` |
| `td_net_weight_kg` | Float | `digits=(12,1)`, `ro`, `copy=False`, `string="Нетто з автоваг, кг"` (R-12) |
| `td_expected_weight_kg` | Float | `digits=(12,1)`, `compute="_compute_f3d_expected"`, не зберігається, `string="Маса за документом, кг"` (R-12 п. 2) |
| `td_weight_check` | Selection | `[('none','Не зважено'),('ok','У допуску'),('deviation','Відхилення'),('no_reference','Немає еталона')]`, `ro`, `copy=False`, `default='none'`, `string="Звірка ваги"` |
| `td_weight_deviation_pct` | Float | `digits=(6,2)`, `ro`, `copy=False`, `string="Відхилення, %"` |
| `td_weighing_ids` | One2many `td.yard.weighing` `picking_id` | `string="Зважування"` |

| Сигнатура | Алгоритм |
|---|---|
| `_compute_f3d_expected()` | R-12 п. 2 для одного документа (`@api.depends("move_ids.product_qty", "move_ids.quantity", "move_ids.product_id.weight", "state")`) |
| `_td_expected_kg()` → `(float, bool)` | маса й ознака «є еталон» (усі рухи мають `product.weight > 0`) — R-12 п. 2 |
| `action_f3d_open_visit()` | форма `td_visit_id` |
| `_action_done()` | після `super()` (без `context['f3d_yard_no_auto']`): R-09 п. 2 для пакетів документів |

M-08b `_inherit = "stock.move.line"`: `create(vals_list)` / `write(vals)` — після `super()`, якщо `quantity` у
значеннях і > 0 і немає `context['f3d_yard_no_auto']` → R-09 п. 1 для `picking_id.batch_id.td_visit_id`.

### M-09 `res.partner` — розширення (FR-14, CY-07, A-04)

| Поле | Тип | Параметри |
|---|---|---|
| `td_is_carrier` | Boolean | `default=False`, `string="Перевізник"` |
| `td_is_driver` | Boolean | `default=False`, `string="Водій"` |
| `td_carrier_id` | Many2one `res.partner` | `domain="[('td_is_carrier','=',True)]"`, `ondelete="set null"`, `string="Перевізник водія"` |
| `td_driver_doc` | Char(32) | `groups=GRP_SEC`, `string="Документ водія"` (PII) |
| `td_default_plate` | Char(16) | `string="Типовий держномер"`; перевірка як `plate` M-01 |
| `td_visit_count` | Integer | `compute`, не зберігається: `search_count(['\|','\|',('partner_id','=',id),('carrier_id','=',id),('driver_id','=',id)])` у `td.yard.visit` (під `sudo()` лише для лічби) |

Метод `action_f3d_view_visits()` → `act_window` рейсів із тим самим доменом. `@api.onchange` на рейсі (M-01):
`driver_id` → `driver_phone = driver_id.phone`, `driver_doc = driver_id.td_driver_doc`, `carrier_id` (якщо
порожній) = `driver_id.td_carrier_id`, `plate` (якщо порожній) = `driver_id.td_default_plate`.

### M-10 `delivery.carrier` — розширення (FR-14)

`td_partner_id` Many2one `res.partner` (`domain="[('is_company','=',True)]"`, `ondelete="set null"`,
`string="Контрагент-перевізник"`). Використовується при створенні рейсу з пакета відвантаження (R-24 крок 4).

### M-11 `res.config.settings` — розширення (FR-25, §5.1)

Поля `f3d_yard_<name>` з `config_parameter="td.yard.<name>"` для кожного параметра §5.1, крім
`migration_state`, `migration_report`, `calendar_id`. Типи: Boolean / Integer / Float / Char / Selection
(`weighing_policy_*`: `[('none','Без зважування'),('in_out','На в\'їзді й виїзді')]`); `td_yard_calendar_id` —
Many2one `resource.calendar` з ручними `get_values`/`set_values` (`int(param or 0)`). Поля `read_enabled`,
`write_enabled` — `groups="td_factory3d.group_td_admin"`; решта — `GRP_MGR`. Кнопки: «Ворота й шлагбауми»
(`action_td_yard_gate`), «Повторити міграцію двору» (`action_td_yard_run_migration`, admin).

### M-12 `td.push.handler.yard` — обробник маршруту `lpr` (CT-08)

```python
class F3dPushHandlerYard(models.AbstractModel):
    _name = "td.push.handler.yard"
    _inherit = "td.push.handler"
    _description = "Двір: обробник подій LPR"
    _td_push_routes = ("lpr",)

    def _td_handle_push(self, route, event):
        if route != "lpr":
            return
        self.env["td.yard.lpr.event"].sudo()._td_from_push(event)
```

`event` — словник telemetry M-11: `{"event_id", "route", "ts" (datetime UTC), "remote", "headers", "payload"}`.
Виняток усередині — логується й записується telemetry у `td.push.event.error` (обробник працює в savepoint, M-11).

### M-13 `td.signal` — перевизначення `_td_ingest` (FR-13, A-17)

Telemetry R-17 оновлює `last_value` сирим SQL (`executemany UPDATE`) — перевизначення `write()` такі зміни не
бачить; тому гачок — на вхідному методі CT-10:

```python
class F3dSignal(models.Model):
    _inherit = "td.signal"

    @api.model
    def _td_ingest(self, readings, src="module", collector=None):
        res = super()._td_ingest(readings, src=src, collector=collector)
        bad = {x.get("i") for x in (res or {}).get("rejected", [])}
        yard = [r for i, r in enumerate(readings)
                if i not in bad and str(r.get("code") or "").startswith(("yard/gates/", "yard/scale/"))]
        if not yard or not tools.params.get_bool(self.env, "read_enabled"):
            return res
        try:
            with self.env.cr.savepoint():
                self.env["td.yard.gate"].sudo()._td_yard_dispatch(yard)
        except Exception:
            _logger.exception("td_yard: обробка показань двору")
        return res
```

`td.yard.gate._td_yard_dispatch(readings)` (`@api.model`): 1) мапа `code → (model, record_id, role)` з
`search_read` активних воріт (7 полів-сигналів) і ваг (2 поля) — 2 запити; 2) перетворення `ts` (рядок ISO з
зоною або `datetime`) → naive UTC; `value` → `float` або `None`; 3) групування за записом, сортування за `ts`;
4) `gate._td_yard_on_readings(items)` / `scale._td_yard_on_readings(items)`. Ролі воріт: `state`, `loop`,
`photocell`, `passes`, `cmd_open`, `cmd_close`, `cmd_hold`; ваг: `weight`, `stable`. Показання без ролі —
пропускаються. Нуль запитів, якщо в пакеті немає кодів `yard/gates/*` і `yard/scale/*` (AC-48).

### M-14 `td.viewer.provider.yard` — провайдер переглядача (FR-23, CY-06, A-15)

```python
class F3dViewerProviderYard(models.AbstractModel):
    _name = "td.viewer.provider.yard"          # без _inherit: viewer R-01 п. 3 шукає за префіксом імені
    _description = "3D: двір (фури, КПП, ваги)"
    _td_sequence = 160
    _td_sections = ("yard",)
    _td_group = "td_factory3d.group_td_user"

    def _td_viewer_collect(self, payload, ctx): ...      # R-20
    def _td_viewer_delta(self, patch, ctx): ...          # R-20 п. 7 (infra — лише deep_merge, X-23)
    def _td_viewer_bus_models(self):
        return ["td.yard.visit", "td.yard.gate", "td.yard.scale"]
```

Без встановленого `td_viewer3d` модель існує, але її ніхто не викликає (A-15).

### M-15 `td.yard.dock.report` — SQL-вид зайнятості воріт (FR-21)

`_name = "td.yard.dock.report"`, `_description = "Двір: зайнятість воріт"`, `_auto = False`, `_order = "day desc,
dock_id"`, `_rec_name = "dock_id"`.

| Поле | Тип | Опис |
|---|---|---|
| `day` | Date | день `at_dock_at` за Києвом |
| `dock_id` | Many2one `stock.location` | ворота |
| `side` | Selection `[('west','Захід'),('east','Схід')]` | `stock_location.td_side` |
| `company_id` | Many2one `res.company` | |
| `visit_count` | Integer | рейсів біля воріт |
| `busy_min` | Float | Σ (`t1 − t0`) хв, `t0 = at_dock_at`, `t1 = COALESCE(handling_end_at, weighed_out_at, left_at)` |
| `idle_min` | Float | `GREATEST(shift_min − busy_min, 0)` |
| `occupancy_pct` | Float | `busy_min / shift_min × 100`, 1 знак |
| `avg_dock_min` | Float | `busy_min / visit_count` |

SQL — R-19 п. 4. `init()`: `tools.drop_view_if_exists(cr, self._table)` + `CREATE OR REPLACE VIEW`.

### M-16 `td.yard.walkin.wizard` — рейс без броні (FR-06)

`TransientModel`, `_description = "Двір: рейс без бронювання"`.

| Поле | Тип | Параметри |
|---|---|---|
| `event_id` | Many2one `td.yard.lpr.event` | `ro` |
| `gate_id` | Many2one `td.yard.gate` | `req`, умовчання `event_id.gate_id` або перші ворота `direction in ('in','both')` |
| `plate` | Char(16) | `req`, умовчання `event_id.plate_unicode or event_id.plate_raw` |
| `visit_type` | Selection як M-01 | `req`, `default='incoming'` |
| `partner_id` | Many2one `res.partner` | `string="Постачальник / клієнт"` |
| `carrier_id` | Many2one `res.partner` | `domain="[('is_company','=',True)]"` |
| `driver_id` | Many2one `res.partner` | |
| `driver_phone`, `driver_doc` | Char(32) | `groups=GRP_SEC` |
| `batch_id` | Many2one `stock.picking.batch` | `domain="[('state','in',('draft','in_progress')),('td_visit_id','=',False),('picking_type_code','=',visit_type)]"`, `string="Пакет (якщо відомий)"` |
| `walk_in_left` | Integer | `compute`: `max(P.walk_in_limit_per_day − walk_in_today, 0)` (R-06) |
| `note` | Text | |

`action_create()`: R-06 перевірки; `visit = td.yard.visit.create({... 'is_walk_in': True, 'gate_in_id': gate_id})`;
`visit._set_state('arrived', ts=event_id.ts or now, gate=gate_id)`; `event_id` → `visit_id`, `match_state='handled'`,
`kpp_alert=False`, `handled_by/at`; повертає форму рейсу (`target='current'`) або `{'type': 'ir.actions.act_window_close'}`
у контексті `kpp=1`.

### M-17 `td.yard.reject.wizard` — відхилення (FR-06)

`TransientModel`: `visit_id` (Many2one, `ro`), `event_id` (Many2one `td.yard.lpr.event`, `ro`), `reason` (Text,
`req`, `string="Причина"`), `reason_code` (Selection `[('no_booking','Немає бронювання'),('wrong_docs','Документи не
збігаються'),('late','Запізнення поза вікном'),('safety','Безпека / стан машини'),('other','Інше')]`, `req`,
`default='no_booking'`). `action_confirm()`: `_td_yard_require(GRP_SEC)`; текст = `"%s: %s" % (label(reason_code),
reason)`; є `visit_id` → `visit_id._do_reject(text)`; лише `event_id` → створити рейс `{'visit_type': 'other',
'plate': event.plate_unicode or event.plate_raw, 'is_walk_in': True}` і `_set_state('rejected')` з тим самим текстом,
`event.visit_id = visit`, `match_state='handled'`, `kpp_alert=False`.

### M-18 `td.command` — розширення (FR-20, CY-08)

| Поле | Тип | Параметри |
|---|---|---|
| `td_yard_gate_id` | Many2one `td.yard.gate` | `idx`, `ondelete="set null"`, `ro`, `string="КПП"` |
| `td_yard_visit_id` | Many2one `td.yard.visit` | `idx`, `ondelete="set null"`, `ro`, `string="Рейс"` |
| `td_yard_kind` | Selection | `[('open','Відкрити'),('close','Закрити'),('hold','Тримати відкритим'),('release','Зняти утримання')]`, `ro`, `string="Команда шлагбаума"` |
| `td_yard_reason` | Selection | `[('manual','Вручну'),('auto_booking','Авто: бронювання'),('auto_exit','Авто: виїзд'),('auto_hold_max','Авто: ліміт утримання')]`, `ro` |

`write(vals)`: після `super()`, якщо `state` змінився і `td_yard_gate_id` → `td_yard_gate_id._td_yard_refresh_state()`
(R-16: `failed`/`expired` → помилка воріт).

## 3. Представлення й меню

Спільне: усі рядки — українською в XML; стани — `widget="badge"` з декораціями
`decoration-success="state in ('left','confirmed','open')"`, `decoration-info="state in ('planned','queued','at_dock','handling','weighed')"`,
`decoration-warning="state in ('arrived','requested','held')"`, `decoration-danger="state in ('error','rejected')"`,
`decoration-muted="state in ('cancelled','draft','unknown')"`. Дати — стандартний віджет (клієнт показує за
часовим поясом користувача `Europe/Kyiv`). Кнопки з `groups` — точно як у таблицях; методи додатково перевіряють
права на сервері (§4.4).

| ID | XML-id (`td_yard.`) | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `view_td_yard_visit_form` | form `td.yard.visit` | `<header>` (кнопки `type="object"`): `action_plan` «Запланувати» (`invisible="state != 'draft' or not booking_id"`, groups `GRP_DISP`); `action_arrive` «Прибула» (`invisible="state not in ('draft','planned')"`, `GRP_SEC`); `action_admit` «Пропустити» (`btn-primary`, `invisible="state != 'arrived'"`, `GRP_SEC`); `action_call_to_dock` «На ворота» (`btn-primary`, `invisible="state != 'queued'"`, `GRP_SEC`); `action_start_handling` «Початок операції» (`invisible="state not in ('queued','at_dock')"`, groups `GRP_SEC,stock.group_stock_user`); `action_end_handling` «Кінець операції» (`invisible="state != 'handling' or handling_end_at"`, ті самі групи); `action_weigh` «Зважити» (`invisible="state not in ('queued','at_dock','handling')"`, ті самі групи); `action_leave` «Виїхала» (`invisible="state not in ('queued','at_dock','handling','weighed')"`, `GRP_SEC`); `action_reject_wizard` «Відхилити» (`invisible="state not in ('draft','planned','arrived')"`, `GRP_SEC`); `action_cancel` «Скасувати» (`invisible="state not in ('draft','planned')"`, `GRP_DISP`, `confirm="Скасувати рейс і бронювання?"`); `action_draft` «У чернетку» (`invisible="state != 'cancelled'"`, `GRP_DISP`); `action_show_3d` «Показати в 3D» (`icon="fa-cube"`, `invisible="not scene_code and not dock_code"`); статусбар `state` (`statusbar_visible="planned,arrived,queued,at_dock,handling,weighed,left"`). `<sheet>`: `div[@name='button_box']`: `action_open_pickings` (`picking_count`, «Документи», `fa-file-text-o`), `action_open_batch` («Пакет», `fa-cubes`, `invisible="not batch_id"`); стрічки `widget="web_ribbon"`: «Без броні» (`invisible="not is_walk_in"`, `bg_color="text-bg-warning"`), «Не приїхала» (`invisible="not is_no_show"`, `text-bg-danger`); `<div class="alert alert-warning" invisible="weight_check != 'deviation'">Відхилення нетто: <field name="deviation_kg"/> кг (<field name="deviation_pct"/> %)</div>`; заголовок `name`; група «Рейс»: `visit_type`, `priority` (widget `priority`), `partner_id`, `carrier_id`, `delivery_carrier_id`, `batch_id`, `scene_code`, `weighing_policy` (`readonly="state not in ('draft','planned','arrived')"`); група «Фура й водій»: `plate`, `driver_id`, `driver_phone`, `driver_doc`, `gate_in_id`, `gate_out_id`. Вкладки: «План і факт» (група «План»: `booking_id`, `dock_id`, `planned_start`, `planned_end`; група «Факт» (readonly): `planned_at`, `arrived_at`, `admitted_at`, `at_dock_at`, `handling_start_at`, `handling_end_at`, `weighed_in_at`, `weighed_out_at`, `left_at`, `rejected_at`, `cancelled_at`; група «Тривалості»: `wait_min`, `dock_min`, `total_min`, `late_min`, `progress` widget `progressbar`), «Бронювання» (`booking_ids` list `editable="bottom"` для `GRP_DISP`: `dock_id`, `slot_start`, `slot_end`, `source`, `state` badge, кнопки рядка `action_confirm` «Підтвердити» (`invisible="state != 'requested'"`), `action_cancel` «Скасувати» (`invisible="state == 'cancelled'"`)), «Зважування» (група readonly: `gross_kg`, `tare_kg`, `net_kg`, `expected_kg`, `deviation_kg`, `deviation_pct`, `weight_check` badge; `weighing_ids` list readonly: `name`, `ts`, `kind`, `role`, `weight_kg`, `source`, `state` badge), «Документи» (`picking_ids` readonly: `name`, `partner_id`, `scheduled_date`, `state`, `td_net_weight_kg`, `td_weight_check`), «Розпізнавання» (`groups=GRP_SEC`; `lpr_event_ids` readonly: `ts`, `camera_code`, `direction`, `car_state`, `plate_norm`, `confidence`, `match_state`), «Примітка» (`note`, `reject_reason` readonly). Чаттер (`chatter`) |
| V-02 | `view_td_yard_visit_list` | list | `name`, `day`, `visit_type`, `state` (badge), `plate`, `partner_id`, `carrier_id`, `dock_id`, `planned_start`, `arrived_at`, `left_at` (optional show), `wait_min` (optional hide), `dock_min` (optional hide), `net_kg` (optional hide), `weight_check` (badge, optional hide), `is_walk_in` (optional hide); `decoration-muted="state in ('left','cancelled','rejected')"`, `decoration-warning="is_walk_in and state in ('arrived','queued')"`, `decoration-danger="weight_check == 'deviation'"` |
| V-03 | `view_td_yard_visit_kanban` | kanban (диспетчерська) | `default_group_by="state"`, `records_draggable="0"`, `group_create="0"`, `quick_create="0"`, `default_order="priority desc, planned_start, arrived_at"`; картка: `name` (жирно), `plate_display`, `partner_id`, рядок `dock_code` · `planned_start` (локальний час `HH:MM`) – `planned_end`; бейджі: «Без броні» (`is_walk_in`), «Терміново» (`priority == '1'`), «Відхилення ваги» (`weight_check == 'deviation'`); `progress` (widget `progressbar`, `invisible="state not in ('at_dock','handling')"`); кнопки картки (`type="object"`, `class="btn btn-sm btn-primary"`): «Пропустити» (`action_admit`, `state == 'arrived'`), «На ворота» (`action_call_to_dock`, `state == 'queued'`), «Виїхала» (`action_leave`, `state == 'weighed'`) — групи як у V-01 |
| V-04 | `view_td_yard_visit_search` | search | поля `name`, `plate` (`filter_domain="['\|', ('plate','ilike',self), ('plate_norm','ilike',self)]"`), `partner_id`, `carrier_id`, `driver_id`, `dock_id`, `batch_id`; фільтри: `today` «Сьогодні» (`[('day','=', context_today().strftime('%Y-%m-%d'))]`), `on_site` «На території» (`[('state','in',('arrived','queued','at_dock','handling','weighed'))]`), `at_kpp` «Очікують на КПП» (`state = arrived`), `queued` «У черзі», `at_dock` «Біля воріт» (`state in (at_dock, handling)`), `walk_in` «Без броні», `no_show` «Не приїхала», `deviation` «Відхилення ваги», `done` «Виїхали» (`state = left`), `incoming` «Приймання», `outgoing` «Відвантаження»; group by `state`, `visit_type`, `dock_id`, `carrier_id`, `partner_id`, `day` |
| V-05 | `view_td_yard_visit_pivot` | pivot | рядки `carrier_id`, стовпці `visit_type`; міри `__count`, `wait_min`, `dock_min`, `total_min`, `late_min`, `net_kg` |
| V-06 | `view_td_yard_visit_graph` | graph | `type="bar"`, `stacked="1"`: `day` (row, `interval="day"`), `visit_type` (col), міра `__count` |
| V-07 | `view_td_yard_booking_form` | form `td.yard.booking` | `<header>`: `action_confirm` «Підтвердити» (`btn-primary`, `invisible="state != 'requested'"`, `GRP_DISP`), `action_cancel` «Скасувати» (`invisible="state == 'cancelled'"`, `GRP_DISP`), `action_reset` «Повернути в запит» (`invisible="state != 'cancelled'"`, `GRP_DISP`), статусбар `state`. `<div class="alert alert-warning" role="alert" invisible="not warning"><field name="warning" nolabel="1"/></div>`; група: `visit_id` (`context="{'default_visit_type': 'incoming'}"`), `dock_id` (`domain="[('td_kind','=','dock')] + ([('td_side','=', side_hint)] if side_hint else [])"` — `side_hint` = невидиме не збережене поле `compute` = `visit_id.side`), `slot_start`, `slot_end`, `duration_min`, `source`, `day`; група «Рейс» (readonly): `partner_id`, `plate`, `batch_id`, `visit_state`; `note`; чаттер |
| V-08 | `view_td_yard_booking_list` | list | `name`, `day`, `dock_id`, `slot_start`, `slot_end`, `visit_id`, `partner_id`, `plate`, `source`, `state` (badge); `decoration-muted="state == 'cancelled'"`, `decoration-warning="state == 'requested'"` |
| V-09 | `view_td_yard_booking_gantt` | gantt | `<gantt string="Бронювання воріт" date_start="slot_start" date_stop="slot_end" default_group_by="dock_id" default_scale="day" scales="day,week" color="color" pill_label="True" decoration-warning="state == 'requested'" decoration-muted="state == 'cancelled'" precision="{'day': 'hour:quarter', 'week': 'day:half'}" display_unavailability="0" sample="0">`; поля `state`, `visit_id`, `plate`, `partner_id`, `source`; шаблон `gantt-popover`: рейс, номер, партнер, джерело, `warning` (якщо є). Перетягування змінює `slot_start/slot_end/dock_id` → R-03 перевірка → R-02 синхронізація |
| V-10 | `view_td_yard_booking_calendar` | calendar | `date_start="slot_start" date_stop="slot_end" color="dock_id" mode="day" quick_create="0" event_open_popup="1"`; поля `visit_id`, `plate`, `state` |
| V-11 | `view_td_yard_booking_search` | search | поля `dock_id`, `visit_id`, `partner_id`; фільтри `confirmed` «Підтверджені» (за замовчуванням у дії), `requested` «Запити», `today` «Сьогодні» (`day = context_today()`), `west` «Захід», `east` «Схід»; group by `dock_id`, `side`, `source`, `state`, `day` |
| V-12 | `view_td_yard_gate_form` | form `td.yard.gate` | `<header>` (`GRP_SEC`): `action_open` «Відкрити», `action_close` «Закрити», `action_hold` «Тримати відкритим» (`confirm="Тримати шлагбаум відкритим до 30 хв?"`), `action_release` «Зняти утримання» (`invisible="state != 'held' and not hold_until"`), `action_opened_manually` «Відкрито вручну», `action_reset_error` «Скинути помилку» (`invisible="not last_error"`); поле `state` badge у заголовку. `<div class="alert alert-warning" invisible="not command_block_reason">Команди недоступні: <field name="command_block_reason" nolabel="1"/></div>`; `<div class="alert alert-danger" invisible="not last_error"><field name="last_error" nolabel="1"/></div>`; button_box: `action_view_commands` («Команди», `fa-terminal`), «Показати в 3D» (домішка CB-01); `name` (title); група «КПП»: `td_code`, `direction`, `side`, `mode` (widget `radio`, `readonly` для не-`GRP_MGR` через `groups` дублем поля), `camera_code`, `scale_id`, `responsible_id`; група «Зараз» (readonly): `state_since`, `last_plate`, `last_plate_at`, `passes_today`, `admitted_today`, `tailgate_today`, `last_tailgate_at`, `hold_until`, `pending_visit_id`; вкладки «Обладнання й сигнали» (`groups=GRP_MGR`): `equipment_id`, `zone_id`, `camera_equipment_id`, `source_id`, `pos_x`, `pos_y`, `invert_di`, 7 полів сигналів; «Команди» (`command_ids` readonly: `requested_at`, `td_yard_kind`, `state`, `requested_by`, `done_at`, `error`); чаттер |
| V-13 | `view_td_yard_gate_list` | list | `sequence` (handle), `td_code`, `name`, `direction`, `mode`, `state` (badge), `passes_today`, `admitted_today`, `tailgate_today` (optional hide), `last_plate` (groups `GRP_SEC`) |
| V-14 | `view_td_yard_lpr_event_list` | list `td.yard.lpr.event` | `create="0"`, `edit="0"`, `delete="0"`; `ts`, `camera_code`, `gate_id`, `direction`, `car_state`, `plate_norm`, `confidence` (widget `percentage`), `match_state` (badge), `visit_id`, `kpp_alert` (widget `boolean`), `lost_at` (optional hide), `note` (optional hide); `decoration-warning="kpp_alert"`, `decoration-muted="match_state in ('ignored','expired','handled')"` |
| V-15 | `view_td_yard_lpr_event_form` | form | readonly; `<header>`: `action_walk_in` «Створити рейс» (`invisible="match_state not in ('unmatched','low_confidence') or direction == 'out'"`), `action_reject` «Відхилити» (те саме), `action_dismiss` «Вирішено» (`invisible="not kpp_alert"`); групи: «Подія» (`ts`, `received_at`, `camera_code`, `gate_id`, `direction`, `car_state`, `car_id`, `packet_counter`, `push_event_id`), «Номер» (`plate_raw`, `plate_unicode`, `plate_norm`, `plate_country`, `confidence`, `plate_list`, `plate_list_mode`, `plate_list_description`), «Результат» (`match_state`, `visit_id`, `kpp_alert`, `note`, `lost_at`, `handled_by`, `handled_at`); `image` (widget `image`, `options="{'size': [640, 0]}"`), `image_url` (widget `url`) |
| V-16 | `view_td_yard_lpr_event_search` | search | поля `plate_norm`, `camera_code`, `visit_id`; фільтри `alert` «Потрібне рішення» (`kpp_alert = True`), `unmatched` «Без бронювання», `low` «Низька довіра», `today` «Сьогодні» (`ts >= (context_today()).strftime('%Y-%m-%d 00:00:00')`), `in` «В'їзд», `out` «Виїзд»; group by `gate_id`, `match_state`, `ts:day` |
| V-17 | `view_td_yard_weighing_list` | list | `name`, `ts`, `scale_id`, `kind`, `role`, `weight_kg`, `plate`, `visit_id`, `picking_id`, `source`, `state` (badge); `decoration-warning="state == 'unassigned'"`, `decoration-muted="state == 'void'"` |
| V-18 | `view_td_yard_weighing_form` | form | `<header>`: `action_assign_selected` «Призначити рейсу» (`invisible="state != 'unassigned'"`, `GRP_SEC`), `action_void` «Анулювати» (`invisible="state == 'void'"`, `GRP_SEC`, `confirm="Анулювати зважування?"`), статусбар `state`; група: `scale_id`, `ts`, `kind`, `weight_kg`, `stable`, `source` (readonly, якщо не новий запис), `visit_id` (`readonly="state not in ('unassigned',) and id"`), `role`, `picking_id`, `plate`, `user_id`, `note`; чаттер. Відкривається також як діалог із V-01 «Зважити» (`target='new'`, кнопки футера «Записати» (`special="save"`) і «Скасувати») |
| V-19 | `view_td_yard_weighing_search` | search | поля `name`, `plate`, `visit_id`, `picking_id`; фільтри `unassigned` «Непризначені», `today` «Сьогодні», `auto` «Автоматичні», `manual` «Ручні», `void` «Анульовані»; group by `scale_id`, `kind`, `source`, `ts:day` |
| V-20 | `view_td_yard_scale_form` / `_list` | form/list `td.yard.scale` | form: `<header>` `action_capture` «Зафіксувати зараз» (`GRP_SEC`); `name`; група: `td_code`, `equipment_id`, `zone_id`, `source_id`, `weight_signal_id`, `stable_signal_id`, `pos_x`, `pos_y` (менеджер); група «Межі»: `max_kg`, `min_kg`, `division_kg`, `auto_capture`; група «Зараз» (readonly): `capture_state`, `last_weight_kg`, `last_stable`, `last_ts`, `today_count`, `last_weighing_id`; list: `td_code`, `name`, `capture_state`, `last_weight_kg`, `last_stable`, `last_ts`, `today_count` |
| V-21 | `view_stock_picking_batch_form_td_yard` | form inherit `stock_picking_batch.stock_picking_batch_form` | `//header/field[@name='state']` `position="before"`: кнопка `action_f3d_create_visit` «Створити рейс» (`invisible="td_visit_id or picking_type_code not in ('incoming','outgoing')"`, `GRP_DISP`); `//div[@name='button_box']` `inside`: stat `action_f3d_open_visits` (`td_visit_count`, «Рейси», `fa-truck`, `invisible="not td_visit_count"`); `//notebook` `position="before"`: `<group name="f3d_yard" string="Двір" invisible="not td_visit_id">` з `td_visit_id`, `td_visit_state` (badge), `td_plate` |
| V-22 | `view_stock_picking_batch_list_td_yard` | list inherit `stock_fleet.stock_picking_batch_tree` | після `dock_id`: `td_visit_state` (badge, optional show), `td_plate` (optional hide) |
| V-23 | `view_picking_form_td_yard` | form inherit `stock.view_picking_form` | `//div[@name='button_box']` `inside`: stat `action_f3d_open_visit` («Рейс», `fa-truck`, `invisible="not td_visit_id"`); `//page[@name='extra']` `position="after"`: `<page name="f3d_yard" string="Двір" invisible="not td_visit_id and not td_net_weight_kg">`: `<div class="alert alert-warning" invisible="td_weight_check != 'deviation'">Нетто відрізняється від маси за документом більше за допуск.</div>`, група: `td_visit_id`, `td_net_weight_kg`, `td_expected_weight_kg`, `td_weight_check` (badge), `td_weight_deviation_pct`; `td_weighing_ids` (readonly list: `name`, `ts`, `kind`, `weight_kg`, `state`) |
| V-24 | `view_picking_list_td_yard` | list inherit `stock.vpicktree` | після `origin`: `td_weight_check` (badge, optional hide), `td_net_weight_kg` (optional hide) |
| V-25 | `view_partner_form_td_yard` | form inherit `base.view_partner_form` | `//div[@name='button_box']` `inside`: stat `action_f3d_view_visits` (`td_visit_count`, «Рейси», `fa-truck`, `invisible="not td_visit_count"`); `//notebook` `inside`: `<page name="f3d_yard" string="Двір">`: `td_is_carrier`, `td_is_driver`, `td_carrier_id` (`invisible="not td_is_driver"`), `td_driver_doc` (`invisible="not td_is_driver"`), `td_default_plate` |
| V-26 | `view_delivery_carrier_form_td_yard` | form inherit `delivery.view_delivery_carrier_form` | після `//field[@name='delivery_type']`: `td_partner_id` |
| V-27 | `view_td_yard_dock_report_pivot` / `_graph` / `_list` | `td.yard.dock.report` | pivot: рядки `dock_id`, стовпці `day:day`, міри `occupancy_pct`, `busy_min`, `idle_min`, `visit_count`; graph `type="bar"`: `dock_id`, міра `occupancy_pct`; list: `day`, `dock_id`, `side`, `visit_count`, `busy_min`, `idle_min`, `occupancy_pct`, `avg_dock_min` |
| V-28 | дії звітів (`report/td_yard_report_views.xml`) | `ir.actions.act_window` | `action_td_yard_visit_analysis` (`td.yard.visit`, `view_mode="pivot,graph,list"`, `context={'search_default_done': 1}`); `action_td_yard_dock_report` (`td.yard.dock.report`, `pivot,graph,list`) |
| V-29 | `view_td_yard_walkin_wizard_form` | form `td.yard.walkin.wizard` | `<div class="alert alert-info">Залишилось рейсів без броні на сьогодні: <field name="walk_in_left" nolabel="1"/></div>`; група: `plate`, `gate_id`, `visit_type`, `partner_id`, `carrier_id`, `batch_id`, `driver_id`, `driver_phone`, `driver_doc`, `note`; футер: `action_create` «Створити рейс» (`btn-primary`), «Скасувати» (`special="cancel"`) |
| V-30 | `view_td_yard_reject_wizard_form` | form `td.yard.reject.wizard` | `reason_code` (widget `radio`), `reason`; футер: `action_confirm` «Відхилити» (`btn-danger`), «Скасувати» |
| V-31 | `view_f3d_command_list_f3d_yard` | list inherit `td_telemetry.view_td_command_list` | після `signal_id`: `td_yard_gate_id` (optional show), `td_yard_kind` (optional show), `td_yard_visit_id` (optional show), `td_yard_reason` (optional hide); дія `action_td_yard_command` (`td.command`, list,form, `domain=[('td_yard_gate_id','!=',False)]`, `context={'create': 0}`) |
| V-32 | `res_config_settings_view_form_td_yard` | form inherit `base.res_config_settings_view_form` | `//form` `inside`: `<app data-string="Двір" string="Двір" name="td_yard" groups="td_yard.group_td_yard_manager">` з блоками (`<block title="…">` + `<setting>`): «Стоп-крани» (`td_yard_read_enabled` «Обробляти показання й події двору», `td_yard_write_enabled` «Дозволяти команди на шлагбауми», `td_yard_antipassback` — перші два `groups=td_factory3d.group_td_admin`); «КПП і розпізнавання» (`walk_in_allowed`, `walk_in_limit_per_day`, `lpr_min_confidence`, `lpr_match_window_h`, `lpr_store_images`, `lpr_image_max_kb`, `kpp_refresh_s`); «Бронювання й черга» (`slot_default_min`, `dock_turnaround_min`, `enforce_calendar`, `calendar_id`, `early_min`, `late_min`, `auto_call_next`, `queue_slot_window_min`, `arrival_timeout_min`, `no_show_min`, `dock_shift_min`); «Шлагбауми» (`open_timeout_s`, `cmd_cooldown_s`, `cmd_expire_s`, `hold_max_min`, `signal_max_age_s`); «Зважування» (`net_tolerance_pct`, `net_tolerance_kg`, `weigh_max_age_s`, `scale_auto_capture`, `scale_dwell_s`, `weighing_policy_west`, `weighing_policy_east`); «Зберігання даних» (`lpr_keep_days`, `visit_pii_keep_days`, `weighing_unassigned_keep_days`); «Міграція» (`seed_product_weights`, кнопка `td_yard.action_td_yard_run_migration` для admin). Мітки — як у лапках §5.1 |
| V-33 | `action_td_yard_kpp` (`views/td_yard_kpp_action.xml`) | `ir.actions.client` | `name="Екран КПП"`, `tag="f3d_yard.kpp"`, `target="current"`, `params="{}"`; клієнт — R-18 |
| V-34 | меню й дії (`views/td_yard_menus.xml`, `data/td_yard_actions.xml`) | `ir.ui.menu`, `ir.actions.*` | таблиця нижче |

Дії вікон — у файлі представлень своєї моделі (`views/f3d_yard_<model>_views.xml`; `action_td_yard_settings` — у
`views/res_config_settings_views.xml`), щоб вони існували до файлів налаштувань і меню (порядок `data` §1):

| XML-id | Модель | `view_mode` | `domain` / `context` |
|---|---|---|---|
| `action_td_yard_dispatch` | `td.yard.visit` | `kanban,list,form,pivot,graph` | `context={'search_default_today': 1}`; домен `[('state','not in',('cancelled',))]`; `help` «Немає рейсів на сьогодні. Створіть рейс або бронювання.» |
| `action_td_yard_visit` | `td.yard.visit` | `list,form,kanban,pivot,graph` | — |
| `action_td_yard_booking` | `td.yard.booking` | `gantt,calendar,list,form` | `context={'search_default_confirmed': 1, 'search_default_requested': 1}` |
| `action_td_yard_lpr_event` | `td.yard.lpr.event` | `list,form` | `context={'search_default_today': 1}` |
| `action_td_yard_weighing` | `td.yard.weighing` | `list,form` | `context={'search_default_today': 1}` |
| `action_td_yard_gate` | `td.yard.gate` | `list,form` | — |
| `action_td_yard_scale` | `td.yard.scale` | `list,form` | — |
| `action_td_yard_settings` | `res.config.settings` | `form` | `target='inline'`, `context={'module': 'td_yard', 'bin_size': False}` |

Серверні дії (`data/td_yard_actions.xml`):
- `action_td_yard_run_migration` («Повторити міграцію двору»): `model_id=model_td_yard_visit`, `state='code'`,
  `code="action = env['td.yard.visit'].f3d_yard_run_migration()"`; метод `@api.model f3d_yard_run_migration()`:
  без `group_td_admin` → `AccessError("Повторити міграцію може лише адміністратор «Завод 3D».")`; інакше
  `hooks.run_all(self.env)` і `display_notification` зі звітом (`sticky=True`).
- `action_td_yard_dispatch_std` («Диспетчеризація (стандарт)»): `model_id=stock_picking_batch.model_stock_picking_batch`,
  `code`: `view = env.ref('stock_fleet_enterprise.view_stock_picking_batch_gantt', raise_if_not_found=False)`;
  `action = env['ir.actions.act_window']._for_xml_id('stock_picking_batch.stock_picking_batch_action')`; якщо `view` →
  `action.update({'view_mode': 'gantt,list,form', 'views': [(view.id, 'gantt'), (False, 'list'), (False, 'form')]})`;
  `action['domain'] = [('dock_id', '!=', False)]`; `action['context'] = {'search_default_in_progress': 1}`.
  Без `stock_fleet_enterprise` — список пакетів із доками (Gantt відсутній, без помилки).

Меню (CB-09; батько `td_factory3d.menu_td_root`, sequence 60). Пункт параметрів модуля (`res.config.settings`) — під
`td_factory3d.menu_td_config` із sequence 60 (= резерв двору в CB-09; правило X-32); довідники воріт і ваг та
«Повторити міграцію двору» лишаються в корені двору:

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_td_yard` | Двір | `td_factory3d.menu_td_root` | 60 | `td_factory3d.group_td_user` | — |
| `menu_td_yard_dispatch` | Диспетчерська | `menu_td_yard` | 10 | `group_td_user` | `action_td_yard_dispatch` |
| `menu_td_yard_kpp` | Екран КПП | `menu_td_yard` | 20 | `group_td_yard_security` | `action_td_yard_kpp` |
| `menu_td_yard_booking` | Бронювання воріт | `menu_td_yard` | 30 | `group_td_user` | `action_td_yard_booking` |
| `menu_td_yard_visit` | Рейси | `menu_td_yard` | 40 | `group_td_user` | `action_td_yard_visit` |
| `menu_td_yard_dispatch_std` | Диспетчеризація (стандарт) | `menu_td_yard` | 45 | `group_td_yard_dispatcher` | `action_td_yard_dispatch_std` |
| `menu_td_yard_journals` | Журнали | `menu_td_yard` | 50 | `group_td_user` | — |
| `menu_td_yard_lpr` | Розпізнавання номерів | `menu_td_yard_journals` | 10 | `group_td_yard_security` | `action_td_yard_lpr_event` |
| `menu_td_yard_weighing` | Зважування | `menu_td_yard_journals` | 20 | `group_td_user` | `action_td_yard_weighing` |
| `menu_td_yard_commands` | Команди на шлагбауми | `menu_td_yard_journals` | 30 | `group_td_yard_security` | `action_td_yard_command` |
| `menu_td_yard_reports` | Звіти | `menu_td_yard` | 60 | `group_td_yard_dispatcher` | — |
| `menu_td_yard_report_visits` | Рейси (аналіз) | `menu_td_yard_reports` | 10 | `group_td_yard_dispatcher` | `action_td_yard_visit_analysis` |
| `menu_td_yard_report_docks` | Зайнятість воріт | `menu_td_yard_reports` | 20 | `group_td_yard_dispatcher` | `action_td_yard_dock_report` |
| `menu_td_yard_config` | Налаштування | `menu_td_yard` | 90 | `group_td_yard_manager` | — |
| `menu_td_yard_config_gate` | КПП і шлагбауми | `menu_td_yard_config` | 10 | `group_td_yard_manager` | `action_td_yard_gate` |
| `menu_td_yard_config_scale` | Автоваги | `menu_td_yard_config` | 20 | `group_td_yard_manager` | `action_td_yard_scale` |
| `menu_td_yard_config_settings` | Налаштування двору | `td_factory3d.menu_td_config` | 60 | `group_td_yard_manager` | `action_td_yard_settings` |
| `menu_td_yard_config_migration` | Повторити міграцію двору | `menu_td_yard_config` | 90 | `td_factory3d.group_td_admin` | `action_td_yard_run_migration` |

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_yard_visit_user,td.yard.visit user,model_td_yard_visit,td_factory3d.group_td_user,1,0,0,0
access_td_yard_visit_security,td.yard.visit security,model_td_yard_visit,group_td_yard_security,1,1,1,0
access_td_yard_visit_dispatcher,td.yard.visit dispatcher,model_td_yard_visit,group_td_yard_dispatcher,1,1,1,1
access_td_yard_booking_user,td.yard.booking user,model_td_yard_booking,td_factory3d.group_td_user,1,0,0,0
access_td_yard_booking_dispatcher,td.yard.booking dispatcher,model_td_yard_booking,group_td_yard_dispatcher,1,1,1,1
access_td_yard_gate_user,td.yard.gate user,model_td_yard_gate,td_factory3d.group_td_user,1,0,0,0
access_td_yard_gate_manager,td.yard.gate manager,model_td_yard_gate,group_td_yard_manager,1,1,1,1
access_td_yard_lpr_event_security,td.yard.lpr.event security,model_td_yard_lpr_event,group_td_yard_security,1,1,0,0
access_td_yard_lpr_event_manager,td.yard.lpr.event manager,model_td_yard_lpr_event,group_td_yard_manager,1,1,1,1
access_td_yard_weighing_user,td.yard.weighing user,model_td_yard_weighing,td_factory3d.group_td_user,1,0,0,0
access_td_yard_weighing_stock,td.yard.weighing stock,model_td_yard_weighing,stock.group_stock_user,1,1,1,0
access_td_yard_weighing_security,td.yard.weighing security,model_td_yard_weighing,group_td_yard_security,1,1,1,0
access_td_yard_weighing_manager,td.yard.weighing manager,model_td_yard_weighing,group_td_yard_manager,1,1,1,1
access_td_yard_scale_user,td.yard.scale user,model_td_yard_scale,td_factory3d.group_td_user,1,0,0,0
access_td_yard_scale_manager,td.yard.scale manager,model_td_yard_scale,group_td_yard_manager,1,1,1,1
access_td_yard_dock_report_user,td.yard.dock.report user,model_td_yard_dock_report,td_factory3d.group_td_user,1,0,0,0
access_td_yard_walkin_wizard_security,td.yard.walkin.wizard security,model_td_yard_walkin_wizard,group_td_yard_security,1,1,1,1
access_td_yard_reject_wizard_security,td.yard.reject.wizard security,model_td_yard_reject_wizard,group_td_yard_security,1,1,1,1
```

Абстрактні `td.push.handler.yard`, `td.viewer.provider.yard` рядків не потребують. `td.command` — права
telemetry (читання `group_td_user`, створення `group_td_manager`); двір створює команди через `sudo()` після
власних перевірок (A-20). Подій LPR звичайний `group_td_user` не читає (знімки, номери), створює їх лише
обробник під `sudo()`.

### 4.2 Групи (`security/td_yard_security.xml`, Odoo 19 `res.groups.privilege`)

```xml
<record id="privilege_td_yard" model="res.groups.privilege">
    <field name="name">Двір</field>
    <field name="category_id" ref="td_factory3d.module_category_factory3d"/>
    <field name="sequence">60</field>
</record>
<record id="group_td_yard_security" model="res.groups">
    <field name="name">Охорона КПП</field><field name="privilege_id" ref="privilege_td_yard"/><field name="sequence">10</field>
    <field name="implied_ids" eval="[Command.link(ref('td_factory3d.group_td_user'))]"/>
</record>
<record id="group_td_yard_dispatcher" model="res.groups">
    <field name="name">Диспетчер двору</field><field name="privilege_id" ref="privilege_td_yard"/><field name="sequence">20</field>
    <field name="implied_ids" eval="[Command.link(ref('group_td_yard_security')), Command.link(ref('stock.group_stock_user'))]"/>
</record>
<record id="group_td_yard_manager" model="res.groups">
    <field name="name">Менеджер двору</field><field name="privilege_id" ref="privilege_td_yard"/><field name="sequence">30</field>
    <field name="implied_ids" eval="[Command.link(ref('group_td_yard_dispatcher')), Command.link(ref('td_factory3d.group_td_manager'))]"/>
</record>
<record id="td_factory3d.group_td_admin" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_td_yard_manager'))]"/>
</record>
```

Ланцюжок: `group_td_yard_security` ⊂ `group_td_yard_dispatcher` ⊂ `group_td_yard_manager` ⊂
`td_factory3d.group_td_admin` ⊂ `base.group_system`. Комірник (`stock.group_stock_user` ⊃ `group_td_user`,
base §4.2) читає рейси, ворота, ваги, зважування; може «Початок/Кінець операції» і «Зважити» (M-01) та
створювати зважування (ACL `access_td_yard_weighing_stock`). Технічний користувач планшета `f3d_yard_kpp`
створює адміністратор уручну (не в data): групи `base.group_user` + `group_td_yard_security`.

### 4.3 Record rules

| XML-id | Модель | Домен | Групи |
|---|---|---|---|
| `td_yard_visit_rule_company` | `td.yard.visit` | `['\|', ('company_id','=',False), ('company_id','in',company_ids)]` | глобальне |
| `td_yard_booking_rule_company` | `td.yard.booking` | те саме | глобальне |
| `td_yard_gate_rule_company` | `td.yard.gate` | те саме | глобальне |
| `td_yard_scale_rule_company` | `td.yard.scale` | те саме | глобальне |
| `td_yard_weighing_rule_company` | `td.yard.weighing` | те саме | глобальне |
| `td_yard_lpr_event_rule_company` | `td.yard.lpr.event` | те саме | глобальне |

### 4.4 Серверні перевірки й персональні дані

- Кожна дія M-01…M-06 перевіряє групу хелпером `_td_yard_require` (таблиці §2) до будь-яких змін; кнопки з
  `groups` у представленнях — лише зручність. `sudo()` дозволено тільки в місцях, названих у §2/§9: запис
  стану рейсу після перевірки (`_set_state`), створення `td.command` (R-15), синхронізація пакета (R-02),
  обробник LPR (M-12), гачок показань (M-13), запис нетто в документи (R-12), автостарт операції (R-09), крони.
- Поля з `groups=GRP_SEC`: `td.yard.visit.driver_phone`, `driver_doc`, `pii_cleared`, `lpr_event_ids`;
  `res.partner.td_driver_doc`; `td.yard.gate.last_plate`; `td.yard.walkin.wizard.driver_phone/driver_doc`.
  Інші користувачі не читають їх ні через форму, ні через `read`/`search_read`/експорт (Odoo кидає `AccessError`).
- Журнали Python (`_logger`) не містять `driver_phone`, `driver_doc`, base64 знімків; номер фури — лише в
  DEBUG (AC-74).
- Команди на шлагбаум: `reason='manual'` — лише `GRP_SEC`; автоматичні (`auto_*`) — лише з внутрішніх методів
  (`_td_yard_auto_open`, `_cron_queue`), від імені `base.user_root` у полі `requested_by` (A-20).

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`) і `tools/params.py`

XML-id параметра — `param_<name>`; ключ — `td.yard.<name>`. `tools/params.py` містить словник
`PARAMS = {name: (type, default)}` з тими самими значеннями; `get_bool(env, name)` = `get_param(key, default) in
('True','true','1')`; `get_int`/`get_float` — `int(float(v))`/`float(v)` з поверненням умовчання при помилці розбору
(WARNING раз на ключ); читання — `env['ir.config_parameter'].sudo()`. Значення для тестового сервера — колонка
«Умовчання» (= ARCH §3).

| name | Умовчання | Тип | Мітка в налаштуваннях | Де використовується |
|---|---|---|---|---|
| `read_enabled` | `True` (хук: `td.base.environment == 'test'` → `True`, інакше `False`) | bool | Обробляти показання й події двору | M-12, M-13, R-07, R-16 |
| `write_enabled` | `False` | bool | Дозволяти команди на шлагбауми | R-15 |
| `antipassback` | `True` | bool | Контроль проїзду без дозволу | R-17 |
| `walk_in_allowed` | `True` | bool | Охорона створює рейси без броні | R-06 |
| `walk_in_limit_per_day` | `5` | int | Ліміт рейсів без броні на добу | R-06 |
| `lpr_min_confidence` | `0.80` | float | Мінімальна довіра розпізнавання | R-08 |
| `lpr_match_window_h` | `4` | int | Вікно пошуку рейсу за номером, год | R-08 |
| `lpr_store_images` | `True` | bool | Зберігати знімки номерів | R-07 |
| `lpr_image_max_kb` | `1024` | int | Макс. розмір знімка, КБ | R-07 |
| `lpr_keep_days` | `30` | int | Зберігати події LPR, діб | R-22 |
| `kpp_refresh_s` | `10` | int | Оновлення екрана КПП, с | R-18 |
| `slot_default_min` | `60` | int | Тривалість слоту за замовчуванням, хв | R-02, R-05 |
| `dock_turnaround_min` | `15` | int | Буфер між слотами, хв | R-03 |
| `enforce_calendar` | `False` | bool | Забороняти слоти поза зміною | R-03 |
| `calendar_id` | `` (хук: id `resource.calendar` «Зміна 1 (07:00–15:30)», на демо `2`) | int | Календар роботи воріт | R-03 |
| `early_min` | `60` | int | Авто-пропуск: раніше за слот, хв | R-15 |
| `late_min` | `120` | int | Авто-пропуск: пізніше за початок слоту, хв | R-15 |
| `auto_call_next` | `False` | bool | Викликати наступну фуру автоматично | R-05 |
| `queue_slot_window_min` | `30` | int | Слот «починається» протягом, хв | R-05 |
| `arrival_timeout_min` | `30` | int | Незбіг LPR без рішення гасне через, хв | R-07 |
| `no_show_min` | `120` | int | «Не приїхала» через, хв після початку слоту | R-19 |
| `dock_shift_min` | `480` | int | Робочий час воріт на добу, хв | R-19 («Зміна 1»: 07:00–11:30 + 12:00–15:30 = 480) |
| `open_timeout_s` | `10` | int | Таймаут підтвердження відкриття, с | R-16 (CAME 4–6 с, емулятор 5 с) |
| `cmd_cooldown_s` | `30` | int | Інтервал між командами, с | R-15 |
| `cmd_expire_s` | `30` | int | Строк дії команди, с | R-15 (`td.command.expires_at`) |
| `hold_max_min` | `30` | int | Макс. утримання відкритим, хв | R-16 |
| `signal_max_age_s` | `15` | int | Свіжість сигналів воріт, с | R-15, R-16 |
| `net_tolerance_pct` | `2.0` | float | Допуск нетто, % | R-12 |
| `net_tolerance_kg` | `100` | float | Допуск нетто, кг (мінімум) | R-12 |
| `weigh_max_age_s` | `15` | int | Свіжість показання ваг, с | R-10 |
| `scale_auto_capture` | `True` | bool | Автозахоплення зважування | R-11 |
| `scale_dwell_s` | `120` | int | Фура «на вагах» у 3D після зважування, с | R-20 |
| `weighing_policy_west` | `in_out` | `none`/`in_out` | Зважування рейсів приймання | R-01 |
| `weighing_policy_east` | `in_out` | `none`/`in_out` | Зважування рейсів відвантаження | R-01 |
| `visit_pii_keep_days` | `90` | int | Зберігати персональні дані водіїв, діб | R-22 |
| `weighing_unassigned_keep_days` | `7` | int | Зберігати непризначені зважування, діб | R-22 |
| `seed_product_weights` | `True` | bool | Заповнити маси плит із моделі (лише нульові) | R-24 крок 3 |
| `migration_state` | `pending` | str | — | R-24 (`pending`/`skipped`/`partial`/`done`) |
| `migration_report` | `{}` | str (JSON) | — | R-24 |

Жодного токена, пароля чи URL з секретом серед параметрів немає (FR-25): токени маршруту `lpr` і колектора —
у telemetry (`F3D_HTTP_PUSH_TOKEN_LPR`, `F3D_HTTP_PUSH_SECRET_LPR`, хеш токена колектора).
Параметр `camera_tz` вилучено (X-48): час події LPR — лише `capture_timestamp` або час прийому (R-07 п. 4).

### 5.2 `data/ir_sequence.xml` (`noupdate="1"`)

| XML-id | `code` | `prefix` | `padding` | Приклад |
|---|---|---|---|---|
| `seq_td_yard_visit` | `td.yard.visit` | `YV/%(year)s/` | 5 | `YV/2026/00001` |
| `seq_td_yard_weighing` | `td.yard.weighing` | `WG/%(year)s/` | 5 | `WG/2026/00001` |

`company_id` порожній (спільні), `implementation='standard'`.

### 5.3 `data/td_yard_gate_data.xml` (`noupdate="1"`) і `data/td_yard_signals.csv`

Записи моделей модуля (видаляються разом із модулем):

| XML-id | Модель | Значення (джерело) |
|---|---|---|
| `scale_truck` | `td.yard.scale` | `td_code='TRUCK-SCALE'`, `name='Автомобільні ваги АКСІС 60 т'`, `pos_x=172.0`, `pos_y=-14.0` (`plant/infra.py:TRUCK_SCALE`), `max_kg=60000`, `min_kg=400`, `division_kg=20` (`equipment_specs.json[role=truck_scale]`: НПВ 60 000, НмПВ 400, дискретність 20 кг), `auto_capture=True` |
| `gate_w` | `td.yard.gate` | `td_code='GATE-W'`, `name="КПП приймання (в'їзд)"`, `sequence=10`, `direction='in'`, `side='west'`, `pos_x=-20.0`, `pos_y=-30.0` (`infra.py:GATES[0]`, огорожа `y0=−30`), `camera_code='CAM-05'` (`infra.py:CAMERAS`, iot_sim §8.13.2), `mode='manual'` |
| `gate_e` | `td.yard.gate` | `td_code='GATE-E'`, `name='КПП відвантаження (виїзд)'`, `sequence=20`, `direction='out'`, `side='east'`, `pos_x=168.0`, `pos_y=-30.0`, `camera_code='CAM-06'`, `scale_id=ref('scale_truck')`, `mode='manual'` |

`equipment_id`, `zone_id`, `camera_equipment_id`, `source_id` і поля сигналів ставить хук (R-24 кроки 1–2), бо
відповідні записи належать base/telemetry і можуть бути відсутні на чистій базі.

Джерела й сигнали — записи моделей telemetry; хук створює/оновлює їх за `code` **без** `ir.model.data`
(A-19), тож деінсталяція двору їх не видаляє (ARCH §2.8). Коди джерел — за єдиною схемою telemetry C.1/C.3
(`MB-U<unit>-<NAME>` для Modbus, `SICS-<NAME>` для SICS; ключі `source_map` CT-11 `u86` → `MB-U86-IO7`, `sics` →
`SICS-TRUCK-SCALE`; X-17). Джерела (константа `hooks/migrate.py:SOURCES`):

| code | name | type | params (стенд) | Інше |
|---|---|---|---|---|
| `MB-U86-IO7` | ADAM-6060 IO-7 (шлагбауми двору) | `modbus_tcp` | `{"host": "iot-sim", "port": 502, "unit": 86, "timeout_s": 2, "retries": 1, "max_block": 32}` | `collector_id` = `td_telemetry.collector_main` (немає → перший активний `td.collector`; немає жодного → крок `skipped` з WARNING), `module='yard'`, `read_enabled=True`, `write_enabled=False`, `period_s_default=1`, `equipment_id` = `GATE-W` |
| `SICS-TRUCK-SCALE` | Автоваги АКСІС (SICS) | `sics` | `{"host": "iot-sim", "port": 4001, "mode": "stream", "period_s": 1, "timeout_s": 5, "unit": "kg", "dialect": "mt_sics", "reset_on_connect": true}` | те саме, `equipment_id` = `TRUCK-SCALE` |

Події LPR надходять через джерело telemetry `td_telemetry.source_http_push` (`HTTP-PUSH`, `params.routes =
["lpr"]`, telemetry §5.2/API-01); двір свого `http_push`-джерела не створює (A-18). Якщо `HTTP-PUSH` на маршрут
`lpr` немає — крок 2 пише WARNING і прив'язує сигнали LPR без джерела.

`data/td_yard_signals.csv` — 18 рядків, повний зміст — Додаток A. Колонки: `code,name,kind,unit,equipment,source,
address,period_s,store_period_s,write_enabled,warn_high,min_duration_s,create_request,viewer_visible,owner,role`
(`source` — код джерела; `owner` — `gate_w`/`gate_e`/`scale_truck`/порожньо; `role` — назва поля на власнику
без `_signal_id`: `state`, `loop`, `photocell`, `passes`, `cmd_open`, `cmd_close`, `cmd_hold`, `weight`, `stable`).

### 5.4 `post_init_hook(env)` — кроки, джерела, ідемпотентність, очікувані кількості (R-24)

`hooks/__init__.py:run_all(env) -> dict` виконує кроки по черзі в контексті
`{'f3d_yard_no_auto': True, 'tracking_disable': True, 'mail_create_nolog': True}` під `sudo()`; кожен крок повертає
словник лічильників; виняток кроку → лог ERROR, `report['errors'].append("<крок>: <текст>")`, наступні кроки
виконуються (крок обгорнуто `with env.cr.savepoint()`); `post_init_hook = run_all + report`. Логер
`odoo.addons.td_yard.hooks`, INFO з лічильниками на кожен крок.

| # | Функція | Джерело | Що робить | Ідемпотентність | Очікувано (копія демо після base і telemetry) | Чиста база |
|---|---|---|---|---|---|---|
| 0 | `params(env)` | CB-10, `resource.calendar` | лише якщо `migration_state == 'pending'`: `read_enabled = 'True' if environment == 'test' else 'False'`; `calendar_id` (порожній) = id календаря з `name = 'Зміна 1 (07:00–15:30)'`, інакше `company.resource_calendar_id` | лише при `pending` / порожньому | `read_enabled=True`, `calendar_id=2` | `True`, календар компанії |
| 1 | `gates_and_scale(env)` | `maintenance.equipment.search_f3d` (CB-01), `td.zone.search_f3d` | порожні поля: `gate_w.equipment_id=GATE-W`, `gate_e.equipment_id=GATE-E`, `scale_truck.equipment_id=TRUCK-SCALE`; `zone_id`: `Z-GATE-W`, `Z-GATE-E`, `Z-GATE-E` (base C.2); `camera_equipment_id = CCTV` для обох воріт | лише порожні | `gates: 2`, `scales: 1`, `linked_equipment: 3`, `cameras: 2`, `zones: 3` | `linked_equipment: 0` (WARNING на кожен код), `zones: 3` |
| 2 | `signals_and_sources(env)` | `SOURCES`, `td_yard_signals.csv` | джерела: `search([('code','=',code)])` → `write(params, module, collector_id, equipment_id)` або `create`; сигнали: `search([('code','=',code)], active_test=False)` → `write` полів визначення (`name`, `kind`, `unit`, `equipment_id`, `source_id`, `address`, `period_s`, `store_period_s`, `write_enabled`, пороги, `create_request`, `viewer_visible`, `module='yard'`) або `create` (+ `origin='catalog'`); `last_*` не чіпаються; далі `owner.<role>_signal_id = signal`, `owner.source_id = source` | upsert за `code` | `sources_created: 2`, `http_push_reused: 1`, `signals_created: 18`, `signals_updated: 0`, `linked: 16` (14 воріт + 2 ваг; 2 сигнали LPR без власника) | те саме |
| 3 | `product_weights(env)` | маси iot_sim R-30 (A-11): `DSP16-SON`, `DSP16-WHT`, `DSP16-ANT`, `DSP16-WNG` — 56 кг; `DSP18-CON` — 63 кг (ПРИПУЩЕННЯ: 56 × 18/16, Q-09); `MDF18-RAW` — 70; `HDF3-WHT` — 12 | лише якщо `seed_product_weights` і `product.product.weight == 0` (за `default_code`) | лише нульові | `products_weighted: 7` | `0` |
| 4 | `carrier_partners(env)` | `delivery.carrier`, `res.partner` | для перевізника з порожнім `td_partner_id`: `name == 'Власний транспорт'` → `company.partner_id`; інакше `res.partner` з тим самим `name` і `is_company=True` (1 збіг); знайдений партнер → `td_is_carrier=True` | лише порожні | `carriers_linked: 2` («Власний транспорт» → «Меблева фабрика (демо)», «Нова Пошта Вантаж (демо)» → партнер id 11), `unmatched: 1` («Standard delivery») | `0` |
| 5 | `visits_from_batches(env)` | `stock.picking.batch` з `td_code =like 'TRUCK-%'` (base CB-06, AC-25 base); якщо таких 0 — пакети з `description` за `^(TRUCK-[A-Z0-9-]+) · (DOCK-[EW]\d)$` (формат `odoo_flows.step_docks`) | для пакета без рейсів: `create` рейсу R-24 п. «рейс» у стані `handling` з мітками часу | пакети з рейсом пропускаються | `visits: 6` (`incoming: 3`, `outgoing: 3`), `with_plate: 1`, `by_description: 0` | `skipped` (0 пакетів) |
| 6 | `bookings_from_batches(env)` | `dock_id`, `scheduled_date`, `end_date` пакетів рейсів кроку 5 | рейс без бронювань: `create({'visit_id', 'dock_id', 'slot_start': scheduled_date, 'slot_end': end_date or +slot_default_min, 'source': 'migration', 'state': 'confirmed'})` у контексті `f3d_yard_sync=True` (без запису в пакет); `ValidationError` конфлікту → створити `requested`, `conflicts += 1` | рейси з бронюванням пропускаються | `bookings: 6`, `conflicts: 0` (6 різних воріт) | `0` |
| 7 | `weighing_from_card(env)` | `plant/infra.py:368` «АА 4512 КТ · брутто 21 380 кг · WH/OUT/00413» | рейс пакета `TRUCK-OUT-1` без зважування `source='migration'`: `create({'scale_id': scale_truck, 'kind': 'check', 'weight_kg': 21380, 'source': 'migration', 'visit_id', 'picking_id': WH/OUT/00413, 'ts': batch.scheduled_date, 'plate': 'АА4512КТ'})`; стан рейсу не змінюється | за `source='migration'` | `weighings: 1` | `0` |
| 8 | `report(env, report)` | — | `migration_state` = `skipped` (крок 5 skipped), `partial` (є `errors` або `conflicts`), інакше `done`; `migration_report = json.dumps(report, ensure_ascii=False, default=str)` з `ts` | перезапис | `done` | `skipped` |

Рейс із пакета (крок 5, R-24): `picks = batch.picking_ids.sorted('name')`; `visit_type = batch.picking_type_code`;
`partner_id = picks[:1].partner_id.commercial_partner_id`; `delivery_carrier_id = picks.carrier_id[:1]`;
`carrier_id` = `partner_id` для `incoming`, `delivery_carrier_id.td_partner_id` для `outgoing`; `plate =
'АА4512КТ'` лише для `td_code == 'TRUCK-OUT-1'` (картка ваг макета), решта порожні; `weighing_policy` за R-01;
`gate_in_id = gate_w`; `state='handling'`; `arrived_at = scheduled_date − 20 хв`, `admitted_at = scheduled_date −
15 хв`, `at_dock_at = handling_start_at = scheduled_date` (iot_sim R-29: прибуття за 20 хв до слоту); `planned_at`
порожній (у демо немає даних). Очікувані 6 рейсів (`YV/2026/…` у порядку `batch.id`; час — Київ, 12.10.2026):

| Рейс | Пакет | Код 3D | Тип | Партнер | Перевізник | Ворота | Слот | Номер | Документ | Маса за документом |
|---|---|---|---|---|---|---|---|---|---|---|
| YV/2026/00001 | BATCH/IN/00001 | TRUCK-IN-1 | incoming | Плитсервіс (демо) | Плитсервіс (демо) | DOCK-W1 | 09:30–10:30 | — | WH/IN/00128 | (120 + 80) × 56 = 11 200 кг |
| YV/2026/00002 | BATCH/IN/00002 | TRUCK-IN-2 | incoming | Плитсервіс (демо) | Плитсервіс (демо) | DOCK-W3 | 10:15–11:15 | — | WH/IN/00129 | 60 × 70 + 200 × 12 = 6 600 кг |
| YV/2026/00003 | BATCH/IN/00003 | TRUCK-IN-3 | incoming | Фурнітура-Трейд (демо) | Фурнітура-Трейд (демо) | DOCK-W4 | 10:40–11:40 | — | WH/IN/00130 | немає еталона (фурнітура, вага 0) |
| YV/2026/00004 | BATCH/OUT/00004 | TRUCK-OUT-1 | outgoing | Меблі Дім (демо) | Меблева фабрика (демо) | DOCK-E2 | 12:00–13:00 | АА4512КТ | WH/OUT/00413 | немає еталона |
| YV/2026/00005 | BATCH/OUT/00005 | TRUCK-OUT-2 | outgoing | Студія «Інтер'єр» (демо) | Нова Пошта Вантаж (демо) | DOCK-E5 | 12:00–13:00 | — | WH/OUT/00416 | немає еталона |
| YV/2026/00006 | BATCH/OUT/00006 | TRUCK-OUT-3 | outgoing | Меблі Дім (демо) | Нова Пошта Вантаж (демо) | DOCK-E7 | 11:00–12:00 | — | WH/OUT/00418 | немає еталона |

(Пакети й вікна — жива база 14.10.2026: `scheduled_date…end_date` UTC 06:30–07:30, 07:15–08:15, 07:40–08:40,
09:00–10:00, 09:00–10:00, 08:00–09:00.) Для YV/2026/00001: `arrived_at` 09:10, `admitted_at` 09:15, `at_dock_at`
09:30 → `wait_min = 20.0`, `late_min = −20.0`. Решта 18 пакетів base (без `td_code`, AC-26 base) рейсів не
отримують — їх рейси створює диспетчер кнопкою «Створити рейс» (V-21).

### 5.5 `uninstall_hook(env)`

1. `env['ir.config_parameter'].search([('key','=like','td.yard.%')]).unlink()`.
2. Крони, послідовності, ворота/ваги (data), рейси, бронювання, події LPR, зважування — видаляє стандартна
   деінсталяція моделей модуля (вкладення знімків — разом із подіями через `res_model`; хук додатково
   `env['ir.attachment'].search([('res_model','=','td.yard.lpr.event')]).unlink()`).
3. Не чіпаються: `stock.picking.batch.dock_id/scheduled_date/end_date`, `product.product.weight`, партнери,
   `delivery.carrier`, `td.source`/`td.signal` двору (без xml-id, A-19; лишаються з `module='yard'`),
   `td.command` (поля `td_yard_*` зникають разом із модулем).

### 5.6 `data/neutralize.sql`

```sql
-- td_yard: нейтралізація копії проду (каркас §5, FR-25)
UPDATE ir_config_parameter SET value = 'False' WHERE key IN ('td.yard.write_enabled', 'td.yard.read_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
  WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'td_yard';
UPDATE td_yard_gate SET mode = 'manual', hold_until = NULL, open_cmd_id = NULL;
UPDATE td_source SET read_enabled = false, write_enabled = false WHERE module = 'yard';
```

## 6. Крони й фонові процеси (`data/ir_cron.xml`)

Усі — `user_id = base.user_root`, `active=True`, модель `td.yard.visit`, `state='code'`.

| XML-id | Назва | Інтервал | Метод | Один прогін | Ліміти |
|---|---|---|---|---|---|
| `cron_td_yard_queue` | Двір: черга, ворота, «не приїхала» | 1 хв | `_cron_queue()` | 1) R-16: для кожних активних воріт `_td_yard_refresh_state()` (stale → `unknown`, таймаут відкриття, `failed/expired` команди, зняття утримання після `hold_until`); 2) R-07: події `kpp_alert=True`, `match_state in ('unmatched','low_confidence')`, `received_at < now − arrival_timeout_min` → `match_state='expired'`, `kpp_alert=False`; 3) R-19: рейси `planned` з `planned_start < now − no_show_min` і `is_no_show=False` → `is_no_show=True` + чаттер «Не приїхала»; 4) R-05: якщо `auto_call_next` — для кожних воріт без рейсу в `at_dock/handling` → `_td_yard_call_next(dock)` | ≤ 5 с; ≤ 200 рейсів за прогін |
| `cron_td_yard_gc` | Двір: ротація й персональні дані | 1 доба, `nextcall` найближче 03:00 Київ (ставить хук через `zoneinfo`) | `_cron_gc()` | R-22 | батчі по 1 000; ≤ 60 с |
| `cron_td_yard_day_reset` | Двір: добові лічильники воріт | 1 доба, `nextcall` найближче 00:05 Київ | `_cron_day_reset()` | R-23 | — |

Прострочене (сервер стояв) — Odoo виконує крон один раз (`numbercall` у 19 відсутній — стандартна поведінка);
методи ідемпотентні.

## 7. HTTP/JSON API

Власних HTTP-контролерів модуль не має (A-10): пристрої говорять із колектором telemetry, клієнт — через
стандартний JSON-RPC Odoo (`/web/dataset/call_kw`) із сесією користувача. Нижче — контракти, які тестувальник
перевіряє без коду розробника.

### API-01 `td.yard.visit.kpp_data(gate_ids=None)` — дані екрана КПП (RPC, FR-19)

Виклик: `orm.call("td.yard.visit", "kpp_data", [], {"gate_ids": [1, 2]})`. Права: `GRP_SEC` (інакше
`AccessError`). `gate_ids` — `None` = усі активні ворота компанії. Відповідь (R-18; час — Київ, `"HH:MM"` або
`"YYYY-MM-DD HH:MM"`):

```json
{"now": "2026-10-12 10:30", "refresh_s": 10, "read_enabled": true, "write_enabled": false,
 "can": {"walk_in": true, "walk_in_left": 5, "dispatcher": false, "command": false,
         "command_reason": "Команди на шлагбаум вимкнено (td.yard.write_enabled)."},
 "gates": [{"id": 1, "code": "GATE-W", "name": "КПП приймання (в'їзд)", "direction": "in", "mode": "manual",
            "state": "closed", "state_label": "Закритий", "error": null, "loop": false, "photocell": false,
            "last_plate": "АА4512КТ", "last_plate_at": "09:10", "passes_today": 7, "admitted_today": 7,
            "tailgate_today": 0, "hold_until": null, "command_block": "Команди на шлагбаум вимкнено (td.yard.write_enabled)."}],
 "scale": {"id": 1, "code": "TRUCK-SCALE", "weight_kg": 0.0, "stable": true, "state": "idle", "age_s": 3, "offline": false,
           "today_count": 1, "last": {"plate": "АА 4512 КТ", "weight_kg": 21380.0, "kind": "check", "picking": "WH/OUT/00413", "ts": "09:00"}},
 "at_gate": [{"visit_id": 7, "name": "YV/2026/00007", "plate": "АА 1234 КТ", "partner": "Плитсервіс (демо)", "carrier": "Плитсервіс (демо)",
              "type": "incoming", "state": "arrived", "state_label": "Прибула", "dock": "DOCK-W2", "slot": "13:00–14:00",
              "since": "10:28", "walk_in": false, "color": "green", "weights": {"gross": 0.0, "tare": 0.0, "net": 0.0},
              "actions": ["admit", "reject"]}],
 "in_yard": [{"visit_id": 1, "name": "YV/2026/00001", "plate": "", "state": "handling", "state_label": "Операція", "dock": "DOCK-W1",
              "slot": "09:30–10:30", "since": "09:30", "color": "blue", "progress": 0.6, "actions": ["weigh", "leave"]}],
 "events": [{"id": 3, "ts": "10:27", "camera": "CAM-05", "gate": "GATE-W", "direction": "in", "plate": "АА1234КТ", "confidence": 0.91,
             "match_state": "unmatched", "match_label": "Без бронювання", "visit": null, "kpp_alert": true, "color": "yellow",
             "image_url": "/web/content/512", "actions": ["walk_in", "reject", "link", "dismiss"]}]}
```

Склад: `at_gate` — рейси `arrived` (сортування `arrived_at`); `in_yard` — рейси `queued`, `at_dock`, `handling`,
`weighed` (сортування за станом у цьому порядку, далі `admitted_at`); `events` — 20 останніх подій LPR з
`received_at` сьогодні + усі з `kpp_alert=True` (без дублікатів, `ts desc`); `image_url` = `/web/content/<attachment
id>` або `image_url` події. Обмеження: ≤ 50 рейсів у кожному списку; виконання ≤ 50 мс на копії демо (AC-58,
§13.4). Порожні значення — `null`/`""` (не відсутні ключі).

### API-02 `td.yard.visit.kpp_action(action, visit_id=None, event_id=None, gate_id=None, values=None)` (RPC, FR-19)

Права: `GRP_SEC`; далі права конкретного методу. Відповідь: `{"ok": true, "message": "<текст для сповіщення>",
"action": <dict дії або null>}`; помилки — `UserError`/`AccessError`/`ValidationError` (клієнт показує текст).

| `action` | Обов'язково | Виклик | `action` у відповіді |
|---|---|---|---|
| `admit` | `visit_id` | `visit.action_admit()` | — |
| `reject` | `visit_id` або `event_id` | — | дія майстра M-17 (`target='new'`, `context={'kpp': 1}`) |
| `walk_in` | `event_id` (або `values.plate` + `gate_id`) | — | дія майстра M-16 |
| `call` | `visit_id` | `visit.action_call_to_dock()` | — |
| `weigh` | `visit_id`; `values.weight_kg` (необов'язково) | є `weight_kg` → `td.yard.weighing.create({'visit_id', 'scale_id', 'kind': 'in' if not weighed_in_at else 'out', 'weight_kg', 'source': 'manual'})`; інакше `visit.action_weigh()` | дія форми зважування, якщо показання ваг непридатне |
| `leave` | `visit_id` | `visit.action_leave()` | — |
| `open` / `close` / `hold` / `release` | `gate_id` | `gate.action_command(kind)` | — |
| `opened_manually` | `gate_id` | `gate.action_opened_manually()` | — |
| `link` | `event_id`, `visit_id` | `event.action_link_visit(visit_id)` | — |
| `dismiss` | `event_id` | `event.action_dismiss()` | — |
| `assign_weighing` | `values.weighing_id`, `visit_id` | `weighing.action_assign(visit_id)` | — |

Невідома дія → `UserError("Невідома дія КПП: %s")`. Після кожної дії — сповіщення шини `f3d_yard` (API-05).

### API-03 Вхідна подія LPR (через telemetry API-05 → M-11 → M-12)

Двір не приймає HTTP: камера/емулятор → колектор `POST http://collector:8080/f3d/lpr` (telemetry §8.7) →
`POST /f3d/telemetry/event` (API-05 telemetry) → `td.push.handler.yard._td_handle_push('lpr', event)`.
`event`: `{"event_id": "<64 hex>", "route": "lpr", "ts": datetime UTC, "remote": "10.90.2.5", "headers": {...},
"payload": {...}}`. Ключі `payload`, які читає двір (Axis «License plate verifier API», developer.axis.com,
переглянуто 14.10.2026; формат емулятора — iot_sim §8.13.2); решта ігнорується:

| Ключ | Тип у JSON | Використання | Перевірка |
|---|---|---|---|
| `sensorProviderID` | str | `camera_code` → `td.yard.gate.camera_code` | `^[A-Za-z0-9_.-]{1,32}$`, інакше подія `unknown_camera` з `camera_code='?'` |
| `carState` | str `new`/`update`/`lost` | `car_state` | інше → `new` |
| `carID` | str/int | `car_id`, ключ дубліката | `str(...)[:32]` |
| `packetCounter` | str/int | `packet_counter`, ключ дубліката | `str(...)[:32]` |
| `capture_timestamp` | str/int, UNIX мс UTC | `ts` (R-07 п. 4 = telemetry R-22, X-48) | немає / не число / > `now + 60 с` / < `now − td.telemetry.keep_days` → час прийому, `note` |
| `datetime` | str `YYYYMMDD HHMMSSmmm` | не використовується (X-48: час — лише `capture_timestamp` або час прийому) | — |
| `plateText` | str (латиниця) | `plate_raw` | `[:32]` |
| `plateUnicode` / `plateUTF8` | str | `plate_unicode` (перше непорожнє) | `[:32]` |
| `plateCountry` | str | `plate_country` | `[:8]` |
| `plateConfidence` | str/float 0…1 | `confidence` | нечислове → 0.0; обрізання до [0, 1] |
| `plateList`, `plateListMode`, `plateListDescription` | str | `plate_list` (назва списку камери, напр. `f3d_bookings`), `plate_list_mode` (режим списку: `allow`/`block`/`none`…), `plate_list_description` (X-48, X-73) | `[:32]`, `[:16]`, `[:256]` |
| `carMoveDirection` | str `in`/`out`/`unknown` | `direction` | інше → за `gate.direction` |
| `GEOtarget` | str | лише контроль: ≠ `gate.td_code` → `note` «GEOtarget %s ≠ %s» (не блокує) | — |
| `imageArray` | list/dict/str base64 | знімок (R-07 п. 7) | розмір ≤ `lpr_image_max_kb`; JPEG/PNG сигнатура |
| `imagesURI` | list[str] | `image_url = imagesURI[0]` | `http(s)://…`, ≤ 512 символів |
| `imageFile`, `imageFile2` | str (шлях на камері) | не використовуються (за документом Axis — шлях, не base64) | — |

Ідемпотентність — R-07 (ключ дубліката); telemetry додатково відкидає повтор `event_id`. Ліміти тіла — telemetry
(≤ 256 КБ `payload`, ≤ 1 МБ запит).

### API-04 Вихідні команди на шлагбаум (`td.command`, telemetry M-06, R-18; CY-08)

Двір створює `td.command` (під `sudo()`) з полями: `signal_id` = `cmd_open/close/hold_signal_id` воріт, `value`
= `1.0` (`open`, `close`, `hold`) або `0.0` (`release`), `origin='yard'`, `expires_at = now + P.cmd_expire_s`,
`note = "%s %s · %s" % (kind, gate.td_code, visit.name or "")`, `requested_by` = користувач (`reason='manual'`)
або `base.user_root` (`auto_*`), `td_yard_gate_id`, `td_yard_visit_id`, `td_yard_kind`, `td_yard_reason`.
Колектор забирає її (API-06 telemetry) і пише coil (`modbus_tcp`, fc 5, `address.write.addr`: 16/18/20 для
GATE-W, 17/19/21 для GATE-E — Додаток A, X-47); для `open`/`close` плагін сам повертає coil у 0 через
`address.write.pulse_ms` = 1 500 мс (X-46), `hold`/`release` — рівень без імпульсу. Результат (`done`/`failed`/`expired`) повертається через API-07 telemetry
і `td.command.write` (M-18 → R-16).

### API-05 Шина `f3d_yard` (екран КПП)

`env['bus.bus']._sendone("f3d_yard", "f3d_yard/update", {"model": "<model>", "ids": [..], "ts": "<UTC ISO>"})` —
після кожної зміни стану рейсу, воріт, нової події LPR, зважування (R-21). Клієнт КПП підписується
`busService.addChannel("f3d_yard")` і перечитує API-01 (не частіше 1 разу на 2 с — дебаунс у клієнті).

### API-06 Розділ `yard` для переглядача (CY-06)

Схема — Додаток C; збирає M-14 (R-20); доставка — viewer API-02/API-03 (`/f3d/viewer/data`, `/f3d/viewer/delta`).

## 8. Сервісна частина — плагін колектора `sics` (FR-17, CY-05)

### 8.1 Пакет, залежності, установка

`services/collector_plugins/f3d_collector_yard/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "f3d-collector-yard"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["f3d_collector>=0.1.0"]          # ядро колектора telemetry (collector.*)

[project.optional-dependencies]
test = ["pytest==8.3.3", "pytest-asyncio==0.24.0", "jsonschema==4.23.0"]

[project.entry-points."factory3d_collector.plugins"]
sics = "f3d_collector_yard.sics:SicsPlugin"

[tool.setuptools.package-data]
f3d_collector_yard = ["schemas/*.json"]
```

Лише stdlib (`asyncio`, `json`, `re`, `datetime`, `importlib.resources`) + `collector.plugins.base`,
`collector.core.types`, `collector.core.errors` (telemetry §8.3). Установка в образ колектора: рядок
`f3d-collector-yard @ file:///opt/plugins/f3d_collector_yard` у `services/collector/requirements-extra.txt`
(файл telemetry; Dockerfile колектора копіює `services/collector_plugins/` у `/opt/plugins`). Без пакета джерело
`sics` отримує `Health(state='error', error='plugin sics not installed')` (telemetry §8.3.2).

### 8.2 Конфігурація: `params` джерела і `address` сигналу (CY-05; копії схем — у telemetry `plugins/schemas/`)

**Спільна схема `sics` — власник цей модуль** (каркас §6.5, X-45). telemetry Додаток A.1 `sics`, A.2 `sics` і файли
`plugins/schemas/params.sics.json`, `address.sics.json` — дослівні копії двох схем нижче: адреса — `field*` ∈
{`weight`, `stable`}, `cmd` ∈ {`SI`} з умовчанням `SI`, `write.cmd` ∈ {`Z`, `T`, `TAC`}, спільні ключі telemetry A.0
`scale` (≠ 0, умовч. 1) і `offset` (умовч. 0; X-70), `doc`; `params` — `host*`,
`port` (4001), `mode` (`stream`), `period_s` (1), `timeout_s` (**5** — єдине умовчання для валідатора telemetry M-02/M-03
і плагіна), `unit` (`kg`), `dialect` (`mt_sics`), `reset_on_connect` (`true`); `additionalProperties: false` в обох.
Валідація telemetry за цими схемами пропускає джерело `SICS-TRUCK-SCALE` (§5.3) і сигнали № 17–18 Додатка A
(№ 18 — `field: "stable"`); зміни схеми вносяться тут, telemetry їх копіює.

`schemas/params.sics.json`:

```json
{"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "params.sics", "type": "object",
 "required": ["host"], "additionalProperties": false,
 "properties": {
   "host": {"type": "string", "minLength": 1, "maxLength": 253},
   "port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 4001},
   "mode": {"enum": ["stream", "poll"], "default": "stream"},
   "period_s": {"type": "number", "minimum": 0.2, "maximum": 60, "default": 1},
   "timeout_s": {"type": "number", "minimum": 0.5, "maximum": 30, "default": 5},
   "unit": {"enum": ["kg", "t", "lb", "g"], "default": "kg"},
   "dialect": {"enum": ["mt_sics"], "default": "mt_sics"},
   "reset_on_connect": {"type": "boolean", "default": true}}}
```

`schemas/address.sics.json`:

```json
{"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "address.sics", "type": "object",
 "required": ["field"], "additionalProperties": false,
 "properties": {
   "cmd": {"enum": ["SI"], "default": "SI"},
   "field": {"enum": ["weight", "stable"]},
   "write": {"type": "object", "required": ["cmd"], "additionalProperties": false,
             "properties": {"cmd": {"enum": ["Z", "T", "TAC"]}}},
   "scale": {"type": "number", "not": {"const": 0}, "default": 1},
   "offset": {"type": "number", "default": 0},
   "doc": {"type": "string", "maxLength": 128}}}
```

`unit` — одиниця за замовчуванням, якщо відповідь не містить одиниці; фактична одиниця завжди береться з кадру.
`dialect` зарезервовано під інший протокол індикатора АКСІС (Q-05); у v1 — лише `mt_sics`. Запис `TA` (тара) у v1
заборонений (ARCH §2.6) — схема його не допускає. `SicsPlugin.validate(source)` повертає помилки обох схем
(`jsonschema.Draft202012Validator`, якщо пакет є; інакше ручна перевірка обов'язкових ключів і enum).

### 8.3 Клас `SicsPlugin(SourcePlugin)` (`f3d_collector_yard/sics.py`)

```python
class SicsPlugin(SourcePlugin):
    type = "sics"
    version = "0.1.0"
    push_mode = False                 # ядро планує poll(); у режимі stream poll() віддає останній кадр потоку
    address_schema = _load("address.sics.json")
    params_schema = _load("params.sics.json")
```

Стан екземпляра: `_reader`, `_writer` (`asyncio.StreamReader/Writer`), `_lock` (`asyncio.Lock` — одна команда
на з'єднання), `_stream_task`, `_latest: Frame | None`, `_latest_ts: datetime | None` (UTC, час прийому кадру),
`_returned_ts` (час останнього кадру, вже відданого в `poll`), `_pending: dict[str, asyncio.Future]` (відповіді
на команди в режимі stream), `_device: str | None` (серійний номер з `I4`), лічильники `frames`, `errors`,
`reconnects`, `consecutive_errors`.

| Метод | Алгоритм |
|---|---|
| `connect()` | 1) `ctx.allowlist(host)` (`AllowlistDenied` пробрасується); 2) `asyncio.wait_for(asyncio.open_connection(host, port), timeout_s)` → інакше `ConnectError("SICS %s:%s: немає з'єднання")`; 3) якщо `reset_on_connect`: надіслати `@`, читати рядки до `I4 …` (серійний номер → `_device`) або `ES` (діалект без `@` — не помилка) не довше `timeout_s`; 4) `mode == 'stream'`: надіслати `SIR`, запустити `_stream_task = asyncio.create_task(self._stream_loop())`; 5) `reconnects += 1` (крім першого) |
| `_stream_loop()` | нескінченно: `line = await asyncio.wait_for(reader.readline(), timeout_s)`; `TimeoutError`/EOF → `_stream_error = "немає кадрів %s с"`, закрити з'єднання й вийти (наступний `poll` кидає `PollError`, ядро робить бекоф і `connect`); `frame = parse_line(line)`; `frame.id == 'S'` → `_latest`, `_latest_ts = utcnow()`, `frames += 1`; інша відповідь (`Z`, `T`, `TAC`, `ES`, `EL`, `ET`) → `_pending[...]` future, якщо є (див. `write`) |
| `poll(signals)` | `mode='poll'`: під `_lock` надіслати `SI`, читати рядки до кадру з `id == 'S'` (≤ 3 рядки, решта — несподівані `I4` — пропуск) за `timeout_s` → інакше `PollError("SICS: немає відповіді на SI за %s с")`; `ES/ET/EL` → `PollError("SICS: помилка %s на SI")`. `mode='stream'`: є `_stream_error` → `PollError`; `_latest_ts` порожній або старіший за `timeout_s` → `PollError("SICS: немає кадрів %s с")`; `_latest_ts == _returned_ts` → `[]` (нового немає); інакше `_returned_ts = _latest_ts` і кадр → показання. Перетворення кадру — R-13 (§9). Кожен сигнал отримує `Reading(code, ts=frame_ts, value, q)` за `address.field` |
| `write(signal, value, text)` | 1) `address.write.cmd` ∉ {`Z`,`T`,`TAC`} або відсутній → `NotSupported("SICS: запис дозволено лише Z/T/TAC")`; 2) повторна перевірка `ctx.settings.write_enabled` (ядро вже перевірило, захист у глибину) → інакше `WriteError("запис вимкнено")`; 3) під `_lock`: надіслати команду; `poll`-режим — читати відповідь до рядка з `id == cmd` (`TAC` для `TAC`); `stream`-режим — `_pending[cmd] = future`, команда скасовує `SIR` (MT-SICS §4.9), дочекатися future за `timeout_s`, потім знову надіслати `SIR`; 4) успіх: `Z A`, `T S <w> <u>`, `TAC A` → повернути рядок відповіді; `I`/`+`/`-`/`L` → `WriteError("SICS %s %s: команду не виконано")`; таймаут → `WriteError("SICS: немає відповіді на %s за %s с")` |
| `disconnect()` | скасувати `_stream_task`; якщо з'єднання живе і `mode='stream'` — надіслати `S` не потрібно (закриття сокета зупиняє потік); `writer.close(); await writer.wait_closed()` (ігнорувати помилки) |
| `health()` | `online`: з'єднання є і (`mode='poll'` і останній `poll` успішний ≤ `max(3·period_s, timeout_s)` тому) або (`mode='stream'` і `_latest_ts` не старший за `max(3·period_s, timeout_s)`); `error`: `consecutive_errors ≥ 3`; інакше `offline`. `stats = {"frames", "errors", "reconnects", "mode", "device": _device, "last_frame_age_s"}` |

### 8.4 Протокольна карта (P-11 §8.13.3; MT-SICS IND400 «SICS Commands», 30881805 A, 2024 — §2.1, §2.2.1–2.2.3, §4.5, §4.7–4.12, §5.6–5.8; mt.com, переглянуто 14.10.2026)

Кадр: ASCII, команда великими літерами + `CR LF`; відповідь: `ID␣статус␣вага(10 символів, праворуч)␣одиниця CR LF`;
помилки — 2 символи (`ES` синтаксис; `ET`, `EL` — передача/логіка в загальному MT-SICS; IND400 документує `ES`).

| Команда | Напрям | Відповідь | Значення | Що робить плагін |
|---|---|---|---|---|
| `@` | W (скидання) | `I4 A "AX2026-0001"` | скидання, серійний номер | при `connect`, `reset_on_connect` |
| `SI` | R | `S S      21380 kg` / `S D      21360 kg` / `S I` / `S +` / `S -` | вага негайно: стабільна / динамічна / не виконано / перевантаження / недовантаження | режим `poll`, раз на `period_s` |
| `SIR` | R (потік) | ті самі кадри безперервно (емулятор 2/с) до будь-якої іншої команди | | режим `stream` |
| `S` | R | `S S …` (чекає стабілізації) / `S I` / `S +` / `S -` | | не використовується (блокуюча) |
| `Z` | W | `Z A` / `Z I` / `Z +` / `Z -` | обнулення (тара скидається) | `write` (лише `write_enabled`) |
| `T` | W | `T S      14000 kg` / `T I` / `T +` / `T -` | тарування стабільної ваги | `write` |
| `TAC` | W | `TAC A` / `TAC I` | очищення тари | `write` |
| `TA` | R/W | `TA A      14000 kg` / `TA I` / `TA L` | запит / встановлення тари | **не підтримується** (v1) |
| `I2`, `I4` | R | `I2 A "AKSIS 60-18 (sim) 60000 kg"`, `I4 A "…"` | ідентифікація | лише `I4` при скиданні |

### 8.5 Розбір кадру й одиниці (R-13)

`parse_line(raw: bytes|str) -> Frame` (`Frame(kind, id, status, value, unit, text, raw)`, `kind ∈ {'weight',
'status', 'error', 'empty'}`): декодування `ascii` з `errors='replace'`; `strip("\r\n ")`; порожньо → `empty`;
`tokens = line.split()`; `tokens == [x]` і `x ∈ {'ES','ET','EL'}` → `error`; `len ≥ 4` і `tokens[1] ∈ {'S','D'}` і
`tokens[2]` відповідає `^-?\d+(\.\d+)?$` → `weight` (`value = float(tokens[2])`, `unit = tokens[3]`); `len == 3` і
`tokens[1] ∈ {'S','D'}` і число → `weight` з `unit = params.unit`; `len ≥ 2` і `tokens[1] ∈ {'A','I','+','-','–','L'}` →
`status` (`text = " ".join(tokens[2:]).strip('"')`); інакше → `error` з `id='?'` (лічильник `errors`, WARNING раз
на хвилину). Одиниці → кг: `kg` × 1; `g` × 0.001; `t` × 1000; `lb` × 0.45359237; інша → показання `q='bad'`.

Показання з кадру `S`:

| Кадр | `field='weight'` | `field='stable'` |
|---|---|---|
| `S S      21380 kg` | `value=21380.0`, `q='good'` | `1.0`, `good` |
| `S D      21360 kg` | `21360.0`, `good` | `0.0`, `good` |
| `S S       21.38 t` | `21380.0`, `good` | `1.0`, `good` |
| `S S        -20 kg` | `-20.0`, `good` (дрейф нуля; Odoo трактує < `min_kg` як «порожньо») | `1.0`, `good` |
| `S I` | `None`, `bad`, `text='busy'` | `None`, `bad` |
| `S +` | `None`, `bad`, `text='overload'` | `None`, `bad` |
| `S -` | `None`, `bad`, `text='underload'` | `None`, `bad` |
| `S S      21380 oz` | `None`, `bad`, `text='unit oz'` | `1.0`, `good` |

Ключі адреси `scale`/`offset` (X-70, telemetry A.0) застосовує плагін до значення поля після перетворення в кг:
`value = value_kg · address.scale + address.offset` (умовч. 1 і 0; `None` лишається `None`); `signal.scale` плагін не
застосовує — множить ядро колектора (telemetry R-02, X-63; у даних `scale=1.0`). `ts` показання — час прийому кадру
(UTC, `datetime.now(timezone.utc)`).

### 8.6 Таймінги й стан-машина (R-14)

`DISCONNECTED → CONNECTING → (RESET @) → READY (poll) | STREAMING (SIR) → помилка → DISCONNECTED` (бекоф і повторне
`connect` — ядро telemetry R-19: 1 → 30 с для `poll`, 1 → 60 с для `connect`).

| Параметр | Значення (стенд) | Поведінка |
|---|---|---|
| `period_s` | 1 | планувальник викликає `poll` кожну секунду (група сигналів `weight` + `stable`, однаковий `period_s=1`) |
| `timeout_s` | 5 | з'єднання; відповідь на `SI`/`@`/команду запису; тиша потоку `SIR` > 5 с → розрив і перепідключення |
| швидкість потоку | емулятор 2 кадри/с (iot_sim §8.13.3) | у `poll` віддається лише останній кадр: ≤ 1 показання/с на сигнал |
| повторне `SIR` | після кожної команди запису в режимі `stream` | MT-SICS: будь-яка команда скасовує `SIR` |
| `consecutive_errors` | скидається першим успішним `poll` | ≥ 3 → `health().state='error'` |

### 8.7 Фейковий сервер для тестів (`tests/fake_sics_server.py`)

`FakeSicsServer(weights: list[tuple[str, float, str]] | Callable, unit="kg", rate_hz=2.0, drop_after=None,
reply_delay_s=0.0, reset_reply='I4 A "FAKE-0001"', support_reset=True)` — `asyncio.start_server` на `127.0.0.1:0`
(порт у `server.port`). Поведінка: `SI` → наступний `(status, value, unit)` зі списку (`status` ∈ `S`/`D`/`I`/`+`/`-`;
для `I`/`+`/`-` — рядок `S <status>`), формат `f"S {status} {value:>10.0f} {unit}\r\n"` (як IND400 §2.2.1);
`SIR` → ті самі кадри з частотою `rate_hz` до наступної команди; `Z` → `Z A`; `T` → `T S <поточна вага> kg`; `TAC`
→ `TAC A`; `TA…` → `TA A …`; `@` → `reset_reply` (або `ES`, якщо `support_reset=False`); невідоме → `ES`;
`drop_after=N` — закрити з'єднання після N кадрів; `reply_delay_s` — затримка відповіді (для таймаутів). Лічильник
отриманих команд `server.received: list[str]`.

### 8.8 Логування й метрики

Логер ядра `collector.plugin.sics.<source>`: INFO — підключення/відключення, `device`; WARNING — помилки кадрів
(раз на хвилину на тип), таймаути; DEBUG — сирі рядки. Секретів у плагіні немає (параметри без `*_ref`).
Метрики через `ctx.metrics` з мітками `type="sics", source=<code>`: `collector_sics_frames_total`,
`collector_sics_errors_total{kind}`, `collector_sics_reconnects_total`, `collector_sics_last_weight_kg` (gauge).

### 8.9 Сумісність з емулятором і живим пристроєм

Емулятор (iot_sim §8.13.3) реалізує `S`, `SI`, `SIR`, `Z`/`ZI`, `T`/`TI`, `TA`, `I0…I4`, `@`, `ES/EL/ET` — плагін
використовує підмножину `@`, `SI`, `SIR`, `Z`, `T`, `TAC` (останню емулятор не перелічує — відповідь `ES` дає
`WriteError("SICS: помилка ES на TAC")`, AC-52). Живий індикатор АКСІС ME-01: RS-232 → TCP-шлюз (ПРИПУЩЕННЯ,
Q-05); перехід — зміна `params.host/port` джерела `SICS-TRUCK-SCALE` (каркас §1).

## 9. Алгоритми й правила

Час у прикладах — Київ (UTC+3) 12.10.2026, якщо не сказано інше. «Сьогодні» — доба за Києвом
(`tools.tz.day_bounds_utc(local_day(now))` → `[00:00, 24:00)` Київ у UTC).

### R-01 Номер і умовчання рейсу

1. `name = ir.sequence.next_by_code('td.yard.visit')` → `YV/2026/00001`; унікальність у межах компанії (SQL).
2. `side` (compute): `dock_id.td_side`, якщо є ворота; інакше `incoming`/`other` → `west`, `outgoing` → `east`.
3. `weighing_policy` при створенні (якщо не передано): `west` → `P.weighing_policy_west`, `east` →
   `P.weighing_policy_east` (обидва `in_out` на стенді). Змінюється диспетчером до пропуску (`readonly` у V-01).
4. `plate` зберігається як `strip().upper()`; `plate_norm` — R-08 п. 1.

Приклад: `create({'visit_type': 'outgoing', 'plate': ' аа 4512 кт '})` → `name='YV/2026/00007'`, `side='east'`,
`weighing_policy='in_out'`, `plate='АА 4512 КТ'`, `plate_norm='AA4512KT'`.

### R-02 Синхронізація бронювання ↔ пакет (A-01)

1. **Прямий напрям** (`booking._sync_batch`, викликається з `action_confirm` і `write` підтвердженого
   бронювання): якщо `visit_id.batch_id` і `batch.state ∉ ('done','cancel')`: `vals = {}`; `batch.dock_id != dock_id`
   → `vals['dock_id']`; `batch.scheduled_date != slot_start` → `vals['scheduled_date']`; `batch.end_date != slot_end`
   → `vals['end_date']`; непорожні `vals` → `batch.sudo().with_context(f3d_yard_sync=True).write(vals)`. Пишуться
   лише змінені поля, бо запис `dock_id` змушує `stock_fleet` переписати локації рухів на док (base R-10 —
   очікувана стандартна поведінка). `end_date` у `stock_fleet` — `readonly` лише в представленні; ORM-запис дозволений.
2. **Зворотний напрям** (M-07 `write`): зміна `dock_id`/`scheduled_date`/`end_date` пакета (стандартний Gantt
   диспетчеризації) без `context['f3d_yard_sync']` оновлює підтверджене бронювання активного рейсу
   (`slot_end = end_date or scheduled_date + P.slot_default_min`) з тим самим контекстом; R-03 конфлікт → `ValidationError`
   відкочує й запис пакета.
3. Бронювання `requested`/`cancelled` пакет не змінюють. Скасування підтвердженого бронювання поля пакета не очищає.

Приклад: пакет base для `WH/IN/00131` (`dock_id = WH/Вхід/Ворота 2`, `scheduled_date = 10:00 UTC`); диспетчер
«Створити рейс» → бронювання `requested` 13:00–14:00 → «Підтвердити» → `vals = {}` (усе збігається, пакет не
пишеться). Перетягування смуги в Gantt на 14:15–15:15 → `batch.scheduled_date = 11:15 UTC`, `end_date = 12:15 UTC`.

### R-03 Конфлікти слотів

1. Перетин підтверджених бронювань одних воріт: `[s1, e1) ∩ [s2, e2) ≠ ∅ ⇔ s1 < e2 ∧ s2 < e1` →
   `ValidationError("Ворота %s уже заброньовані: %s (%s–%s).")` (код воріт, `name` чужого бронювання, локальні години).
2. Дотик (`e1 == s2`) — дозволено. Бронювання `requested`/`cancelled` не блокують; перетин із `requested` → рядок
   `warning` «Перетин із запитом %s».
3. Підтвердження серіалізується блокуванням рядка воріт (`SELECT … FROM stock_location WHERE id=%s FOR UPDATE`) —
   два паралельні підтвердження одного проміжку дають одне `ValidationError` (AC-07).
4. Сторона: `visit_id.side != dock_id.td_side` → `ValidationError("Ворота %s на стороні «%s», а рейс — «%s».")`;
   `batch.picking_type_id.dock_ids` непорожні і `dock_id` не серед них → `ValidationError("Ворота %s не належать
   типу операцій %s.")`.
5. Буфер (попередження): найближче підтверджене бронювання тих самих воріт до/після слоту з проміжком
   `0 ≤ gap < P.dock_turnaround_min` → `warning` «Між слотами %s хв (буфер %s хв): %s».
6. Календар (попередження; при `P.enforce_calendar` — `ValidationError` з тим самим текстом): календар
   `P.calendar_id`; для локального дня тижня `slot_start` беруться `attendance_ids` з `dayofweek == str(weekday)`;
   немає → «День без зміни «%s».»; інакше вікно `[min(hour_from), max(hour_to)]`; слот (локальний) має лежати в
   одній добі всередині вікна → інакше «Слот поза зміною «%s» (%s–%s).». Обідня перерва не перевіряється.
7. Тривалість слоту ≤ 24 год; `slot_end > slot_start` (SQL).

Приклади (є підтверджене `DOCK-W2 · 12.10 13:00–14:00`; календар «Зміна 1 (07:00–15:30)»: Пн–Пт 07:00–11:30,
12:00–15:30): 13:30–14:30 на `DOCK-W2` → `ValidationError` «Ворота DOCK-W2 уже заброньовані: DOCK-W2 · 12.10
13:00–14:00 (13:00–14:00).»; 14:00–15:00 → підтверджено, `warning` «Між слотами 0 хв (буфер 15 хв): DOCK-W2 ·
12.10 13:00–14:00»; 14:15–15:15 → без попереджень; 15:00–16:00 → підтверджено з `warning` «Слот поза зміною
«Зміна 1 (07:00–15:30)» (07:00–15:30).», а при `enforce_calendar=True` — `ValidationError`; `DOCK-E1` для рейсу
`incoming` → `ValidationError` «Ворота DOCK-E1 на стороні «Схід (відвантаження)», а рейс — «Захід (приймання)».».

### R-04 Категорії воріт

Алгоритм base R-19 для пари (ворота бронювання, товари документів пакета рейсу): `allowed = dock_id.td_accepts`;
порожньо → без попередження; `bad` = категорії товарів рухів (`state != 'cancel'`), жодна з дозволених не є
предком-або-самою (`categ.parent_path` починається з `allowed.parent_path`); непорожня → рядок `warning`
«Ворота %s приймають: %s. У рейсі є: %s.» (назви через «, »). Не блокує ні підтвердження, ні виклик на ворота;
`_td_yard_pick_dock` ставить ворота з попередженням у кінець списку (R-05 п. 2).
Приклад: бронювання `DOCK-W1` під пакет `WH/IN/00132` (крайка `EB2-SON`, `EB2-WHT`) → «Ворота DOCK-W1 приймають:
Плитні матеріали. У рейсі є: Крайка.»; `DOCK-W5` → без попередження.

### R-05 Черга й виклик на ворота

1. **Зайнятість** `_td_yard_dock_busy(dock, start, end, exclude)`: рейс ≠ `exclude` у станах `at_dock`/`handling` з
   `dock_id == dock` (незалежно від часу) або підтверджене бронювання воріт, що перетинає `[start, end)`, рейс якого
   порожній або в стані ∉ {`left`,`rejected`,`cancelled`} і ≠ `exclude`. Повертає рейс-зайняття (або бронювання
   без рейсу — тоді повідомлення «запит постачальника»).
2. **Вибір воріт для рейсу без броні** `_td_yard_pick_dock()`: ворота `td_kind='dock'`, `td_side == side`, активні,
   компанія рейсу; якщо пакет має `picking_type_id.dock_ids` — перетин із ними; порядок: спершу без попередження
   R-04, далі за `td_dock_no`; перші не зайняті на `[now, now + P.slot_default_min)`.
3. **Порядок черги** `_td_yard_queue(side, dock=None)`: рейси `queued` цієї сторони; при `dock` — без тих, чиє
   бронювання на інших воротах. Ключ сортування: `(rank, k1, arrived_at, id)`: `rank = 0` — `priority='1'`; `rank =
   1` — є бронювання і `slot_start ≤ now + P.queue_slot_window_min` (`k1 = slot_start`); `rank = 2` — усі інші
   (`k1 = arrived_at`).
4. **Наступний на ворота** `_td_yard_call_next(dock)`: перший кандидат з п. 3, для якого
   `_td_yard_dock_busy(dock, now, now + slot_default_min, exclude=кандидат)` порожнє (для рейсу з бронюванням —
   його власне бронювання не заважає) → `action_call_to_dock(dock)`; інших пропустити. Викликається кнопкою
   «Наступний» не передбачено — лише авто: з `action_end_handling`/`action_leave` і крону при `P.auto_call_next`.
5. «На ворота» вручну — M-01 `action_call_to_dock`.

Приклад (зараз 12:50; захід, черга): V1 без броні, прибула 12:20; V2 бронювання `DOCK-W2` 13:00, прибула 12:40;
V3 бронювання `DOCK-W5` 14:00, прибула 12:30; V4 без броні, `priority='1'`, прибула 12:45. `_td_yard_queue('west')`
→ `[V4, V2, V1, V3]`; `_td_yard_queue('west', DOCK-W2)` → `[V4, V2, V1]`; `_td_yard_call_next(DOCK-W2)` → V4
пропущено (бронювання V2 13:00–14:00 перетинає `[12:50, 13:50)`), викликано V2 (`at_dock`).

### R-06 Фура без броні

1. Подія LPR на в'їзді без збігу (R-08) → `match_state='unmatched'`, `kpp_alert=True`; команда шлагбаума не
   створюється ніколи (R-15 авто вимагає підтвердженого бронювання).
2. `walk_in_today` = рейси `is_walk_in=True`, `state != 'rejected'`, `arrived_at` сьогодні.
3. Майстер M-16 `action_create`: користувач без `GRP_DISP`: `P.walk_in_allowed == False` →
   `UserError("Рейси без броні створює лише диспетчер.")`; `walk_in_today ≥ P.walk_in_limit_per_day` →
   `UserError("Ліміт рейсів без броні на сьогодні (%s) вичерпано — зверніться до диспетчера.")`. Диспетчер — без
   обох обмежень.
4. Рейс створюється в стані `arrived` (`is_walk_in=True`, без бронювання); пропуск — лише кнопкою «Пропустити»
   (у режимі `auto` теж), ворота — «На ворота» (R-05 п. 2, бронювання `source='walk_in'`, A-23).
5. «Відхилити» (M-17) без рейсу — створює рейс `other` у стані `rejected` для журналу; подія `handled`.

Приклад: сьогодні вже 5 рейсів без броні, охоронець → `UserError` з «(5)»; диспетчер → створено 6-й.

### R-07 Приймання подій LPR і дублікати (`td.yard.lpr.event._td_from_push`)

1. `payload` не `dict` → WARNING, `return False`.
2. Камера: `camera_code` з `sensorProviderID` (API-03); ворота — активні з `camera_code == camera_code`; немає →
   подія `match_state='unknown_camera'`, `kpp_alert=False`, без зіставлення (п. 9 не виконується).
3. Ключ дубліката: є `carID` і `packetCounter` → `"%s|%s|%s" % (camera, carID, packetCounter)`; інакше
   `"evt|" + event['event_id']`. Подія з таким ключем є → повернути її без змін (повтор камери/колектора).
4. Час `ts` — той самий порядок, що telemetry R-22 для показання `yard/lpr/<CAM>/plate` (X-48): `capture_timestamp`
   (епоха мс UTC, `tools.tz.parse_axis_ts`); якщо ключа немає або значення невалідне (`ts_invalid`), пізніше за
   `now + 60 с` (`ts_future`) чи раніше за `now − td.telemetry.keep_days` (`ts_too_old`) — `ts` = час прийому
   (`now` = `received_at`), `note` «Час камери відкинуто (<причина>) — узято час прийому». Поле `datetime` камери не
   використовується (параметр `camera_tz` вилучено, X-48).
5. `carState`: `lost` — шукати попередню подію `camera_code` + `car_id` за 2 год: є → `lost_at = ts`; якщо вона
   `kpp_alert` і `match_state ∈ (unmatched, low_confidence)` → `match_state='expired'`, `kpp_alert=False`, `note`
   «Фура поїхала без рішення»; якщо в неї рейс, напрям `out`, рейс ще не `left` і це `gate.pending_visit_id` →
   `visit.action_leave(ts, note="виїзд за камерою %s")` (sudo); новий запис не створюється. Попередньої немає →
   створити запис `car_state='lost'`, `match_state='ignored'`. `update` — попередня подія тієї ж машини за 30 хв:
   новий номер з більшою довірою → оновити поля номера/довіри; якщо вона `unmatched/low_confidence` — повторити
   R-08; новий запис не створюється; попередньої немає → як `new`. `new` → створити запис.
6. `P.read_enabled == False` → запис із `match_state='ignored'`, без знімка, без зіставлення й змін воріт.
7. Знімок (лише при створенні запису і `P.lpr_store_images`): `imageArray` — список → перший елемент; словник →
   значення `image`/`data`/перше рядкове; рядок → base64 (префікс `data:image/...;base64,` відкидається);
   `base64.b64decode(validate=True)`; розмір ≤ `P.lpr_image_max_kb × 1024`; сигнатура `FF D8 FF` (JPEG) або
   `89 50 4E 47` (PNG) → `ir.attachment` (`name = "lpr-<camera>-<YYYYMMDD-HHMMSS>.jpg|png"`, `res_model =
   'td.yard.lpr.event'`, `res_id`, `raw`, `mimetype`, `public=False`); інакше `note` «Знімок відхилено: <розмір|формат>».
   `imagesURI[0]` (`http(s)://`, ≤ 512) → `image_url`.
8. Ворота: `last_plate = plate_unicode or plate_raw`, `last_plate_at = ts` (лише для валідного номера).
9. Зіставлення й дії — R-08; далі R-21 (шина).
10. Крон: `kpp_alert=True`, `match_state ∈ (unmatched, low_confidence)`, `received_at < now − P.arrival_timeout_min`
    → `expired`, `kpp_alert=False`.

Приклад (S-05 `truck_no_booking`, `plate=АА1234КТ`): POST CAM-05 `carState=new`, `carID=501`, `packetCounter=9001`
→ запис `dedup_key='CAM-05|501|9001'`, `unmatched`, `kpp_alert=True`; повтор того самого тіла → той самий запис;
через 10 хв `carState=lost`, `carID=501` → `lost_at`, `match_state='expired'`, `kpp_alert=False`.

### R-08 Нормалізація номера й зіставлення

1. `normalize_plate(s)`: порожньо → `""`; `upper()`; видалити пробіли й `- . _ ·`; замінити кириличні двійники
   латиницею `LOOKALIKE = {А:A, В:B, Е:E, І:I, Ї:I, К:K, М:M, Н:H, О:O, Р:P, С:C, Т:T, Х:X, У:Y}`; результат валідний,
   якщо `^[A-Z0-9А-ЯІЇЄҐ]{2,12}$`. Приклади: `"АА 4512 КТ"` → `"AA4512KT"`; `"aa-4512-kt"` → `"AA4512KT"`;
   `"КА 0001 ВХ"` → `"KA0001BX"`; `"ВІ 7777 ЕН"` → `"BI7777EH"`; `"ЖЖ1234"` → `"ЖЖ1234"` (валідний); `"A"` → невалідний.
2. `display_plate(s)`: без пробілів, `upper()`; збіг `^([A-ZА-ЯІЇЄҐ]{2})(\d{4})([A-ZА-ЯІЇЄҐ]{2})$` → `"АА 4512 КТ"`;
   інакше як є.
3. Невалідний `plate_norm` → `match_state='low_confidence'`, `note` «Номер не розпізнано», `kpp_alert=True`.
4. `confidence < P.lpr_min_confidence` → `low_confidence`, `note` «Довіра 0.62 < 0.80», `kpp_alert=True`.
5. Напрям: `carMoveDirection ∈ (in, out)` → він; інакше `in` для воріт `in`/`both`, `out` для `out`.
6. Кандидати за номером (`_find_by_plate`): `in` — рейси зі станами `planned`, `arrived`, `queued` і
   `plate_norm == p`, для `planned` — `|planned_start − ts| ≤ P.lpr_match_window_h`; плюс `draft` з `day` = сьогодні;
   `out` — стани `queued`, `at_dock`, `handling`, `weighed` без вікна. Порядок: `|planned_start − ts|` (порожній —
   у кінець), далі `id`.
7. Документи з опису: `tokens = re.findall(r"[A-Z]{2,}/[A-Z]{2,}/\d{3,}", plate_list_description or "")`;
   `doc_visits` — рейси тих самих станів (п. 6, без вікна), у яких `batch_id.name ∈ tokens` або
   `batch_id.picking_ids.name ∩ tokens ≠ ∅`.
   - кандидатів за номером 1 → він;
   - більше 1 → перетин із `doc_visits`, якщо рівно 1 — він; інакше перший за порядком, `note` «Кілька рейсів з
     номером %s — обрано %s», `kpp_alert=True`;
   - 0 → `doc_visits` рівно 1 → він; якщо `visit.plate` порожній — `visit.plate = plate_unicode or plate_raw`
     (чаттер «Номер заповнено з камери %s»); якщо `visit.plate_norm != p` — `note` «Номер камери %s ≠ номер рейсу
     %s», `kpp_alert=True`;
   - інакше `unmatched`, `kpp_alert=True`, `note` «Номер не знайдено серед рейсів» (`in`) / «Фура виїжджає без
     рейсу» (`out`).
8. Збіг: `visit_id`, `match_state='matched'`. В'їзд: рейс `draft|planned` → `action_arrive(ts, gate, event)` (під
   `sudo`); `arrived|queued` — без зміни стану, `note` «Повторне розпізнавання»; якщо `kpp_alert=False` →
   `gate._td_yard_auto_open(visit, event)` (R-15 п. 10). Виїзд: `visit.gate_out_id = gate`; якщо `kpp_alert=False`
   → `gate._td_yard_auto_open(visit, event)` (R-15 п. 11).

Приклади: (а) рейс `YV/2026/00007` (`planned`, `DOCK-W2` 13:00–14:00, пакет документа `WH/IN/00131`, номер
порожній); подія CAM-05 12:40 `plateText="AA7310KT"`, `plateUnicode="АА7310КТ"`, `plateConfidence="0.912340"`,
`plateListDescription="WH/IN/00131 DOCK-W2 Плитсервіс (демо)"` → за номером 0 → за описом 1 → `matched`, номер
рейсу ← `АА7310КТ`, рейс `arrived` (`arrived_at` 12:40). (б) Та сама подія без опису → `unmatched`, `kpp_alert`.
(в) Номер `АА4512КТ` на CAM-06 (`out`) при рейсі `YV/2026/00004` у стані `handling` з `plate='АА4512КТ'` → `matched`
(виїзд), `gate_out_id = GATE-E`. (г) `plateConfidence="0.62"` → `low_confidence`, рейс не змінюється.

### R-09 Автостарт і кінець операції зі складу

1. `stock.move.line` з `quantity > 0` (create/write, без `f3d_yard_no_auto`) → для `picking_id.batch_id.td_visit_id`
   у стані `queued`/`at_dock` → `action_start_handling(auto=True)` (під `sudo`; з `queued` також `at_dock_at = now`).
2. `stock.picking._action_done` → для кожного пакета проведених документів: усі документи пакета в `done`/`cancel`
   → рейс у стані `handling` (або `at_dock` — спершу п. 1) отримує `handling_end_at = now` (якщо порожній),
   чаттер «Документи проведено»; далі як `action_end_handling(auto=True)`.

Приклад: комірник вносить 12 аркушів у рядок `WH/IN/00131` → `YV/2026/00007` `at_dock → handling`; проведення
`WH/IN/00131` → `handling_end_at`; стан лишається `handling` до зважування на виїзді.

### R-10 Придатність показання ваг

Показання придатне для захоплення, якщо `q == 'good'`, `value is not None`, `ts ≥ now − P.weigh_max_age_s`
(повтори з буфера колектора — лише оновлюють `last_*`, якщо новіші), `min_kg ≤ value ≤ max_kg`. `value < min_kg`
— «порожні ваги». `value > max_kg` або `q='bad'` — ігнорується (капча `capture_state` не змінюється). Ваги
`offline`, якщо сигнал ваги `stale`/`unknown` або `last_ts < now − 3 × weigh_max_age_s` (оновлює крон R-16 п. 6);
тоді автозахоплення не працює, «Зважити» відкриває ручне введення (FR-28).
Приклади: 25 200 кг, стабільно, 3 с тому → придатне; те саме 20 с тому → ні; 350 кг → порожньо; 61 000 → ігнор.

### R-11 Автозахоплення й призначення зважування

Працює, якщо `P.scale_auto_capture`, `scale.auto_capture` і `P.read_enabled`.
1. Показання групуються за `ts`: вага `w` і стабільність `s` (немає `s` у групі → `last_stable`); група без `w` —
   пропуск. `last_weight_kg/last_stable/last_ts` оновлюються, якщо `ts > last_ts`.
2. Непридатне (R-10) і `w < min_kg` → `capture_state='idle'`, кандидат очищено.
3. `idle`/`settling`: `s` і є кандидат і `|w − candidate_kg| ≤ 2 × division_kg` → **захоплення**:
   `weight = floor(mean(candidate_kg, w) / division_kg + 0.5) × division_kg`, `capture_state='captured'`,
   `captured_kg = weight`; `s` без кандидата або з більшою різницею → `candidate_kg = w`, `candidate_ts = ts`,
   `settling`; не `s` → кандидат очищено, `settling`.
4. `captured`: нові захоплення не створюються, доки `w ≥ min_kg` (та сама фура на вагах).
5. Призначення в момент захоплення `ts`: `A_in` = рейси `weighing_policy='in_out'`, `state='queued'`, без
   `assigned` зважування `in`, `admitted_at ≥ ts − 2 год`; `A_out_ready` = `in_out`, `state='handling'`,
   `handling_end_at` заповнено, є `in`, немає `out`; `A_out_any` = `in_out`, стан `at_dock`/`handling`, є `in`, немає
   `out`. `|A_in ∪ A_out_ready| == 1` → цей рейс (`kind='in'`, якщо з `A_in`, інакше `out`); `== 0` і `|A_out_any| == 1`
   → `out`; інакше — **непризначене** зважування (`state='unassigned'`, `kind='check'`, `note` «Кандидатів: N»,
   картка КПП червона). Охоронець призначає (`action_assign(visit, kind)`; `kind` за замовчуванням `in`, якщо
   рейс без `in`, інакше `out`).

Приклад (S-06, R-30 iot_sim: брутто 25 200 ± 20): кадри 12:44:00 `8 400 D`, :01 `17 600 D`, :02 `25 200 D`,
:03 `25 200 S` (кандидат), :04 `25 180 S` → `|−20| ≤ 40` → зважування `floor(25 190 / 20 + 0.5) × 20 = 25 200`;
єдиний кандидат `YV/2026/00007` (`queued`, пропущено 12:42) → `kind='in'`, роль `gross`, `weighed_in_at = 12:44:04`.
Далі `25 200 S` — без нових записів; `300 S` → `idle`.

### R-12 Нетто і звірка (FR-12)

1. Роль зважування: `incoming`/`other`: `in` → `gross`, `out` → `tare`; `outgoing`: `in` → `tare`, `out` →
   `gross`; `check` → `check`.
2. Маса документа: Σ по рухах `state != 'cancel'`: `qty × weight_kg`, де `qty` = `move.product_uom._compute_quantity(
   move.quantity, product.uom_id)` для проведеного документа, інакше `move.product_qty`; `weight_kg =
   weight_uom._compute_quantity(product.weight, uom.product_uom_kgm)` (`weight_uom` =
   `product.template._get_weight_uom_id_from_ir_config_parameter()`). Еталон є, якщо рухи є і в усіх `product.weight > 0`.
   Рейс: Σ по документах пакета `state != 'cancel'`; еталон — якщо він є в кожному.
3. Ваги рейсу: останнє `assigned` зважування `in` і `out` (за `ts`); `gross`, `tare` за ролями; `net = |gross − tare|`,
   якщо є обидва, інакше `0`; `incoming` з `gross < tare` → чаттер «Брутто менше тари (%s < %s кг)».
4. Звірка: немає обох зважувань → `none`; немає еталона або маса 0 → `no_reference`; `tol = max(expected ×
   P.net_tolerance_pct / 100, P.net_tolerance_kg)`; `dev = net − expected`; `|dev| ≤ tol` → `ok`, інакше
   `deviation`; `deviation_pct = round(dev / expected × 100, 2)` (expected > 0, інакше 0).
5. Документи (`_td_yard_write_pickings`, `sudo`): документи пакета `state != 'cancel'` за `name`; один → уся `net`;
   кілька → частки `expected_i / Σ expected` (Σ = 0 → порівну); на документі: `td_net_weight_kg`, `td_weight_check`
   (п. 4 для частки й маси документа), `td_weight_deviation_pct`; для `outgoing` також `shipping_weight` (у
   одиниці ваги компанії). `deviation` → активність `mail.mail_activity_data_warning` на документі для `user_id`
   документа або пакета (немає обох — без активності), `summary` «Відхилення нетто», `note` «Нетто %s кг, за
   документом %s кг, відхилення %+.0f кг (%+.2f %%) при допуску %s кг.»; повторно не створюється, поки відкрита.
   Документ не блокується.

Приклади (`WH/IN/00128`, маса 11 200 кг, `tol = max(224, 100) = 224`): брутто 25 200, тара 14 000 → нетто 11 200,
`ok`, 0,00 %; брутто 25 520 → нетто 11 520, `+320 > 224` → `deviation`, +2,86 %; брутто 25 300 → +100 → `ok`
(+0,89 %). `WH/IN/00129` (6 600 кг, `tol = max(132, 100) = 132`): нетто 6 700 → `ok`; 6 750 → `deviation` (+2,27 %).
`WH/IN/00130` (фурнітура, вага 0) → `no_reference`. `TRUCK-OUT-1`: `in` 14 000 (тара), `out` 21 380 (брутто) → нетто
7 380, `no_reference`, `WH/OUT/00413.shipping_weight = 7 380`.

### R-13 Розбір SICS і одиниці — §8.5 (плагін)

### R-14 Режими опитування SICS, таймаути, перепідключення — §8.3, §8.6 (плагін)

### R-15 Команди шлагбаума (FR-09)

`gate.action_command(kind, visit=None, reason='manual')`, перевірки строго в цьому порядку (перша невдала —
`UserError`/`AccessError`, нічого не створюється):
1. `kind ∈ {open, close, hold, release}` інакше `ValueError`.
2. `reason='manual'` → `_td_yard_require(GRP_SEC)`; `reason ∈ {auto_booking, auto_exit, auto_hold_max}` → лише
   при `env.su` (внутрішні виклики під `sudo()`, обробник LPR, крон від `base.user_root`), інакше
   `AccessError("Автоматичні команди створює лише система.")`. Далі — `SELECT id FROM td_yard_gate WHERE id=%s FOR UPDATE`.
3. `P.write_enabled` → інакше `UserError("Команди на шлагбаум вимкнено (td.yard.write_enabled). Відкрийте
   шлагбаум з пульта CAME і натисніть «Відкрито вручну».")`.
4. Сигнал команди (`release` → `cmd_hold_signal_id`): є, `active`, `write_enabled`, `source_id.write_enabled` →
   інакше `UserError("Сигнал команди «%s» для %s не налаштований або запис на сигналі/джерелі вимкнено.")`.
5. Для `open`/`close`: сигнал фотоелемента є, `status ∉ (stale, unknown)`, `last_ts ≥ now − P.signal_max_age_s` →
   інакше `UserError("Немає свіжих даних фотоелемента %s (останні: %s).")`; перекритий (`(last_value ≥ 0.5) xor
   invert_di`) → `UserError("Під стрілою перешкода (фотоелемент %s) — команда заборонена.")`.
6. Немає команди воріт у `queued`/`sent` з `requested_at > now − P.cmd_cooldown_s` → інакше `UserError("Попередня
   команда «%s» ще виконується (з %s).")`.
7. `reason` авто і `gate.state == 'error'` → `UserError("Ворота %s у стані помилки — авто-відкриття вимкнено.")`.
8. Створення `td.command` (API-04) під `sudo()`; виняток telemetry (R-18 telemetry) пробрасується як є. Значення:
   `open`/`close`/`hold` — `1.0`, `release` — `0.0`; імпульс ≥ 1 с для CAME дає адреса сигналу (`write.pulse_ms =
   1500` на `cmd_open`/`cmd_close`, Додаток A; плагін `modbus_tcp` пише 1, через `pulse_ms` — 0; X-46); `cmd_hold` —
   рівень без `pulse_ms`; кожні ворота мають власний `cmd_hold` (GATE-W PDU 20, GATE-E PDU 21; X-47).
9. Наслідки: `open` → `open_cmd_id = cmd`, `_td_yard_count_permit(visit)`; `hold` → `hold_until = now +
   P.hold_max_min`; `release` → `hold_until = False`; усі → `last_command_id`, чаттер воріт і рейсу «Команда «%s»
   %s (#%s) · %s», R-21.
10. **Авто на в'їзді** (`_td_yard_auto_open`, ворота `in`/`both`, подія `in`): умови — `gate.mode == 'auto'`,
    `P.write_enabled`, `now − event.ts ≤ 60 с` (інакше `note` «Подія запізнилась на N с — авто-пропуск вимкнено»,
    `kpp_alert=True`; §11.2), рейс щойно `arrived`, не `is_walk_in`, `booking_id.state == 'confirmed'`, `ts ∈ [planned_start −
    P.early_min, planned_start + P.late_min]`; успіх → `action_command('open', visit, 'auto_booking')` і
    `visit._set_state('queued', note="пропущено автоматично")`. Невиконана умова → команди немає; `event.note` з
    причиною («Ворота в ручному режимі», «Команди вимкнено», «Поза вікном слоту 12:00–15:00», «Без броні»);
    `kpp_alert=True` лише для «поза вікном» і «без броні» (решта — звичайна робота охорони кнопкою «Пропустити»);
    `UserError` з п. 3–7 → `event.note` = текст, `kpp_alert=True`.
11. **Авто на виїзді** (ворота `out`/`both`, подія `out`): `gate.mode == 'auto'`, `P.write_enabled`, `now − event.ts ≤ 60 с`, рейс `weighed`
    або (`weighing_policy == 'none'`, стан `at_dock`/`handling`, усі документи `done`/`cancel`) → `action_command('open',
    visit, 'auto_exit')`; виїзд фіксує R-17.

Приклад: бронювання 13:00, `early_min=60`, `late_min=120` → вікно 12:00–15:00; прибуття 12:40 → команда `open`
на `yard/gates/GATE-W/cmd_open` (`value=1.0`, `expires_at = +30 с`), рейс `queued`; прибуття 11:50 → без команди,
`note` «Поза вікном слоту 12:00–15:00», `kpp_alert=True`; фотоелемент 1 → `UserError` п. 5 (для ручної команди) /
`note` з тим самим текстом (для авто).

### R-16 Стан воріт, таймаути, утримання (`_td_yard_refresh_state`)

Виклики: після обробки показань воріт (M-13), після зміни команди (M-18), крон щохвилини, дії M-03.
1. Контроль команди «відкрити» (`open_cmd_id`): `failed`/`expired` → `last_error = "Команду «Відкрити» не виконано:
   %s"` (`error` або підпис стану), `open_cmd_id = False`; `done`: DI «відкрито» спостерігалось з `done_at − 1 с`
   (`opened_at ≥ done_at − 1 с` або зараз відкрито) → `open_cmd_id = False`; інакше `now − done_at > P.open_timeout_s`
   → `last_error = "Немає підтвердження відкриття за %s с"`, `open_cmd_id = False`; `queued`/`sent` — чекати
   (telemetry прострочить через `cmd_expire_s`).
2. Утримання: `hold_until` і `now > hold_until` → якщо `P.write_enabled` — `action_command('release',
   reason='auto_hold_max')` під `sudo` (`UserError` → чаттер), `hold_until = False`, чаттер «Утримання знято за
   часом (%s хв)».
3. Стан: є `last_error` → `error`; інакше немає `P.read_enabled` або сигнал стану відсутній/`stale`/`unknown`/
   `last_ts < now − max(P.signal_max_age_s, 3 × period_s)` → `unknown`; інакше `open = (last_value ≥ 0.5) xor
   invert_di`; `held = open and (hold_until > now or свіжий cmd_hold ≥ 0.5)`; стан `held` / `open` / `closed`.
4. Зміна стану → `state_since = now`; перехід у `open` → `opened_at` = `ts` показання (з M-13) або `now`; R-21.
5. Нова помилка → чаттер, активність `mail.mail_activity_data_warning` для `responsible_id` (одна відкрита), червона
   плитка КПП. «Скинути помилку» / «Відкрито вручну» очищують.
6. Ваги (у тому ж кроні): сигнал ваги `stale`/`unknown` або `last_ts < now − 3 × weigh_max_age_s` →
   `capture_state='offline'`; свіже показання повертає `idle`.

Приклад: команда #17 `done` о 10:00:02, DI0 = 1 о 10:00:06 → `open`, помилки немає; DI0 лишається 0 до 10:00:13 →
`error` «Немає підтвердження відкриття за 10 с». ADAM вимкнено → сигнали `stale` (telemetry R-07) → ворота
`unknown`, кнопки команд КПП неактивні з поясненням.

### R-17 Антипрохід і виявлення виїзду (`_td_yard_on_readings`)

Для показань воріт за зростанням `ts`:
1. `loop`: `occ = (v ≥ 0.5) xor invert_di`; перехід `True → False` (машина проїхала) при `pending_visit_id`: ворота
   `out`/`both` і рейс у стані `queued`/`at_dock`/`handling`/`weighed` → `visit.action_leave(ts, note="виїзд за
   петлею %s")` (sudo); `pending_visit_id = False` для будь-якого напрямку; `loop_occupied = occ`.
2. `photocell`: `photocell_blocked = (v ≥ 0.5) xor invert_di`.
3. `passes`: `v = int(value)`; `v < passes_day_start` → `passes_day_start = 0` (лічильник ADAM скинуто);
   `prev = passes_today`; `passes_today = v − passes_day_start`; `counter_value = v`; якщо `P.antipassback`,
   `passes_today > admitted_today` і `passes_today > prev` → `tailgate_today += passes_today − max(prev,
   admitted_today)`, `last_tailgate_at = ts`, чаттер «Проїзд без дозволу: проїздів %s, дозволів %s», червоний банер
   КПП, R-21.
4. `state`: перехід 0 → 1 запам'ятовує `opened_at = ts`.
5. Після циклу — `_td_yard_refresh_state()`.

Дозвіл (`admitted_today += 1`) дають: команда `open` (будь-яка причина), «Пропустити» без команди (команди вимкнені),
«Відкрито вручну». Приклад: після добового скидання `passes_day_start = 7`, `admitted_today = 0`; «Пропустити» (1
дозвіл), лічильник 8 → проїздів 1 ≤ 1 — норма; лічильник 9 без нового дозволу → 2 > 1 → `tailgate_today = 1`.
Стенд з `SIM_YARD_AUTOGATE=1` (емулятор відкриває сам) дає хибні проїзди без дозволу — там `antipassback=False`.

### R-18 Екран КПП: дані, кольори, дії (API-01, API-02, V-33)

1. Колір картки рейсу: `green` — `arrived` з підтвердженим бронюванням у вікні R-15 п. 10 або рейс у дворі без
   проблем; `yellow` — `is_walk_in`, поза вікном, `arrived` без броні; `red` — `weight_check == 'deviation'` або
   незакрита помилка воріт рейсу; `blue` — `at_dock`/`handling`. Події: `yellow` — `kpp_alert`; `grey` — `handled`,
   `expired`, `ignored`; `green` — `matched`; `red` — `unknown_camera`.
2. Дії картки: `arrived` → `admit`, `reject`; `queued` → `call`, `weigh`, `leave`; `at_dock`/`handling` → `weigh`,
   `leave`; `weighed` → `leave`; подія `unmatched`/`low_confidence` (`in`) → `walk_in`, `reject`, `link`, `dismiss`;
   (`out`) → `link`, `dismiss`; ворота → `open`, `close`, `hold`, `release` (лише `can.command` і без
   `command_block`), `opened_manually`; непризначене зважування → `assign_weighing`.
3. `can.walk_in` = `P.walk_in_allowed` і `walk_in_left > 0`, або користувач — диспетчер; `can.command` =
   `P.write_enabled`; `gates[].command_block` = текст першої невдалої перевірки R-15 п. 3–6 для `open` або `null`.
4. Клієнт `F3dYardKpp` (OWL, `registry.category("actions").add("f3d_yard.kpp", F3dYardKpp)`): `setup()` —
   `useService("orm")`, `"action"`, `"notification"`, `"bus_service"`; `useState({data: null, busy: false})`;
   `onWillStart` → `load()`; `onMounted` → `setInterval(load, data.refresh_s × 1000)`,
   `bus_service.addChannel("f3d_yard")`, `subscribe("f3d_yard/update", debounce(load, 2000))`; `onWillUnmount` —
   очищення. `load()` → API-01 (помилка → сповіщення `danger`, попередні дані лишаються). `act(action, args)` →
   API-02; `res.action` → `action.doAction(res.action, {onClose: load})`; інакше сповіщення `res.message` і `load()`.
   Розмітка: верхня смуга — час, плитки воріт (стан кольором, останній номер, «проїздів/дозволів», кнопки команд
   `disabled` з `title = command_block`), плитка ваг (вага великими цифрами, «стабільно/динамічно/немає даних»,
   «сьогодні N»); три колонки «На КПП» (`at_gate` + події з `kpp_alert`), «У дворі» (`in_yard`, на картці — поле ваги
   і «Записати» для ручного зважування), «Події LPR» (`events` з мініатюрою `image_url`). Кнопки ≥ 56 px заввишки;
   усі підписи українською.

### R-19 Тривалості, «не приїхала», звіти

1. `wait_min = at_dock_at − arrived_at`; `dock_min = end − at_dock_at`, `end = handling_end_at or weighed_out_at or
   left_at`; `total_min = left_at − arrived_at`; `late_min = arrived_at − planned_start` (зі знаком: від'ємне —
   раніше). Хвилини, 1 знак; бракує мітки → `False` (NULL, не входить у середнє pivot).
2. «Не приїхала»: крон — `planned`, `planned_start < now − P.no_show_min`, `is_no_show=False` → `True` + чаттер.
3. Pivot V-05 — середні (`group_operator="avg"`) тривалостей і сума `net_kg` за перевізником/партнером/воротами/днем.
4. SQL-вид M-15:

```sql
CREATE OR REPLACE VIEW td_yard_dock_report AS (
  WITH p AS (
    SELECT COALESCE((SELECT NULLIF(value, '')::numeric FROM ir_config_parameter
                     WHERE key = 'td.yard.dock_shift_min'), 480) AS shift_min),
  v AS (
    SELECT v.dock_id, v.company_id,
           (v.at_dock_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kyiv')::date AS day,
           EXTRACT(EPOCH FROM (COALESCE(v.handling_end_at, v.weighed_out_at, v.left_at) - v.at_dock_at)) / 60.0 AS busy
    FROM td_yard_visit v
    WHERE v.dock_id IS NOT NULL AND v.at_dock_at IS NOT NULL
      AND COALESCE(v.handling_end_at, v.weighed_out_at, v.left_at) IS NOT NULL)
  SELECT row_number() OVER (ORDER BY v.day, v.dock_id) AS id, v.day, v.dock_id, l.td_side AS side, v.company_id,
         count(*) AS visit_count, round(sum(v.busy)::numeric, 1) AS busy_min,
         round(GREATEST(p.shift_min - sum(v.busy), 0)::numeric, 1) AS idle_min,
         round((sum(v.busy) / NULLIF(p.shift_min, 0) * 100)::numeric, 1) AS occupancy_pct,
         round((sum(v.busy) / count(*))::numeric, 1) AS avg_dock_min
  FROM v JOIN stock_location l ON l.id = v.dock_id CROSS JOIN p
  GROUP BY v.day, v.dock_id, l.td_side, v.company_id, p.shift_min)
```

Приклад: `YV/2026/00001` прибула 09:10, `at_dock` 09:30, кінець операції 10:50, зважена 11:00, виїхала 11:05 →
`wait_min = 20`, `dock_min = 80`, `total_min = 115`, `late_min = −20`; звіт `DOCK-W1` 12.10: `busy_min = 80`,
`idle_min = 400`, `occupancy_pct = 16.7`, `visit_count = 1`.

### R-20 Провайдер переглядача (FR-23, CY-06, A-13, A-16)

`_td_viewer_collect(payload, ctx)` (схема — Додаток C, координати — Додаток B):
1. `gates`: активні ворота → `{code: {name, state, mode, error, passes_today, admitted_today, tailgate_today,
   last_plate, last_plate_at, x, y}}`; `last_plate`/`last_plate_at` — лише якщо `ctx.user` у `GRP_SEC` і не
   `ctx.kiosk` (інакше ключі зі значенням `null`); читання полів з `groups` — тільки за цієї умови.
2. `scale`: `{code: {weight_kg, stable, state, today, last: {plate, weight_kg, kind, picking, ts}, x, y}}`.
3. `trucks`: рейси в станах `arrived`, `queued`, `at_dock`, `handling`, `weighed` (компанії користувача) з полями
   Додатка C; позиція — Додаток B; `zone = env['td.zone'].zone_at(x, y).td_code or null`; `plate = null` при
   `ctx.kiosk`.
4. `queue = {"west": [...], "east": [...]}` (назви рейсів `queued` за R-05 п. 3); `kpp = {"west": [...], "east":
   [...]}` (рейси `arrived` за `arrived_at`).
5. `stats`: `planned_today`, `arrived_today`, `on_site`, `at_dock`, `left_today`, `walk_in_today`, `unmatched`
   (`kpp_alert=True`, лише для `GRP_SEC`, інакше `null`), `avg_wait_min` (середнє `wait_min` рейсів з `at_dock_at`
   сьогодні або `null`), `weighings_today`; `updated` = `ctx.now_local`.
6. `infra.cards` (A-16): якщо `payload.get("infra", {}).get("cards")` — `dict`: для `GATE-W`/`GATE-E` (ключ є)
   `rows = [["Стан", <підпис стану з малої>], ["Сьогодні проїздів", str(passes_today)], ["Режим", "авто"|"ручний"]]`
   + `["Останній номер", "АА 4512 КТ · 09:10"]` (умова п. 1); для `TRUCK-SCALE` — `[["Остання машина",
   "<номер або —> · брутто <вага> кг · <документ>"], ["Сьогодні зважувань", str(today)], ["Зараз", "<вага> кг ·
   стабільно|динамічно|немає даних"]]`. Числа — цілі з пробілом-розділювачем тисяч (`21 380`). Картка макета
   `infra.py:368` після міграції: «АА 4512 КТ · брутто 21 380 кг · WH/OUT/00413», «Сьогодні зважувань» — за фактом.
7. `_td_viewer_delta(patch, ctx)`: якщо `ctx["changes"]` містить `td.yard.visit`/`td.yard.gate`/`td.yard.scale` →
   `patch["yard"]` = повний розділ (власний розділ провайдера); спільний розділ `infra` лише доповнюється через
   спільний хелпер viewer `deep_merge` (viewer M-01, X-23; рекурсивне злиття словників, списки — заміна):
   `deep_merge(patch.setdefault("infra", {}), {"cards": {code: {"rows": ...}} для трьох карток})` (без статичних
   полів); ключі `infra`, уже записані іншими провайдерами (energy 150, genset 155, access 170), і їхні картки не
   змінюються; присвоєння `patch["infra"] = …` заборонене. Хелпер імпортується всередині методу
   (`from odoo.addons.td_viewer3d.tools.payload import deep_merge` — модуль хелпера за viewer M-01, як у td_genset R-13; провайдер
   викликає лише встановлений viewer, A-15). Немає змін — нічого.
8. Помилка всередині провайдера — обробляє viewer R-01 (розділ `error`); провайдер не перехоплює винятки сам.

Приклад (копія демо після міграції): `trucks` — 6 записів у стані `handling` з координатами макета
(`plant/site.py:1425–1430`): `TRUCK-IN-1` (−7.3, 5.0, 0) `Z-YARD-W` `DOCK-W1` `WH/IN/00128` `progress=0.6`;
`TRUCK-IN-2` (−7.3, 25.0, 0) `DOCK-W3` 0.2; `TRUCK-IN-3` (−7.3, 35.0, 0) `DOCK-W4` 0.31; `TRUCK-OUT-1`
(157.3, 15.0, 180) `Z-YARD-E` `DOCK-E2` 0.7; `TRUCK-OUT-2` (157.3, 45.0, 180) `DOCK-E5` 0.28; `TRUCK-OUT-3`
(157.3, 65.0, 180) `DOCK-E7` 0.08.

### R-21 Сповіщення (шина viewer і `f3d_yard`)

1. Рейс (`_td_yard_notify`): після `create`, `_set_state`, зміни `plate`/`batch_id`/`priority`, підтвердження/
   скасування/перенесення бронювання, застосування зважування → `ev = self._td_yard_viewer_event()`; якщо `ev` —
   `ev._notify('td.yard.visit', [name, scene_code, dock_code], 'doc')` (порожні коди відкидає viewer M-03).
2. Ворота: зміна `state`, `passes_today`, `admitted_today`, `tailgate_today`, `last_plate`, `last_error` →
   `_notify('td.yard.gate', [td_code], 'state')`.
3. Ваги: зміна `capture_state` або нове зважування → `_notify('td.yard.scale', [td_code], 'state')`; поточна вага
   без зміни `capture_state` шину не будить (КПП опитує кожні 10 с).
4. Канал `f3d_yard` (API-05): моделі й id збираються в `env.cr.precommit.data['f3d_yard.bus']` і відправляються одним
   `_sendone` на модель у `precommit` (як viewer M-03) — пакет показань не породжує сотні повідомлень.

### R-22 Ротація й персональні дані (крон `cron_td_yard_gc`, FR-24)

1. Події LPR з `received_at < now − P.lpr_keep_days`: спершу `ir.attachment` (`res_model='td.yard.lpr.event'`,
   `res_id in ids`), потім події; батчі по 1 000.
2. Рейси з `COALESCE(left_at, rejected_at, cancelled_at) < now − P.visit_pii_keep_days`, `pii_cleared=False` →
   `driver_phone=False`, `driver_doc=False`, `pii_cleared=True`; `plate`, `driver_id` лишаються (операційні дані,
   ARCH §2.6).
3. Непризначені зважування з `ts < now − P.weighing_unassigned_keep_days` → `unlink`.
4. Звіт у лог INFO: `{"lpr_deleted": n, "images_deleted": n, "pii_cleared": n, "weighings_deleted": n}`.

Приклад (запуск 14.10.2026 03:00): подія від 10.09.2026 (34 доби) видаляється зі знімком; рейс, що виїхав
10.07.2026 (96 діб), — PII очищено; рейс від 20.07.2026 (86 діб) — ні.

### R-23 Добове скидання лічильників (крон `cron_td_yard_day_reset`, 00:05 Київ)

Для кожних воріт: `passes_day_start = counter_value`, `passes_today = 0`, `admitted_today = 0`, `tailgate_today = 0`;
R-21. Якщо пристрій сам обнуляє лічильник опівночі (iot_sim: сигнал «passes_today»), R-17 п. 3 обробляє `v <
passes_day_start`.

### R-24 Міграція з демо-бази — §5.4 (кроки 0–8, правило «рейс із пакета», очікувані кількості)

## 10. Стани й переходи

### 10.1 Рейс `td.yard.visit.state` (A-03)

```
draft ──бронювання підтверджено / action_plan──► planned ──LPR збіг / «Прибула»──► arrived ──«Пропустити» / авто R-15──► queued
  │  ▲                                              │                                 │                                   │
  │  └──────бронювання скасовано────────────────────┘                                 │                    «На ворота» / R-05│ автостарт R-09
  │                                                                                   │                                   ▼   ▼
  ├──«Прибула» (без броні) / M-16 walk-in──────────────────────────────────► arrived  │              at_dock ──R-09 / «Початок»──► handling
  │                                                                                   │                 │  │ зважування out          │ зважування out
  ├──M-17──► rejected ◄──M-17── planned, arrived ◄────────────────────────────────────┘                 │  └──────────► weighed ◄─────┘
  └──«Скасувати»──► cancelled ──«У чернетку»──► draft                         queued/at_dock/handling/weighed ──«Виїхала» / R-17 / R-07 lost──► left
```

| Стан | Вхід (хто/що) | Мітка часу | Побічні ефекти |
|---|---|---|---|
| `draft` | створення; скасування останнього бронювання з `planned`; `action_draft` з `cancelled` | — | — |
| `planned` | `booking.action_confirm` (диспетчер; R-24 — одразу `handling`) або `action_plan` | `planned_at` | шина R-21 |
| `arrived` | LPR-збіг на в'їзді (R-08 п. 8), «Прибула» (охорона), майстер M-16 | `arrived_at`, `gate_in_id` | КПП: картка «На КПП»; R-15 п. 10 (авто) |
| `queued` | «Пропустити» (охорона) або авто R-15 п. 10 | `admitted_at` | команда `open` (якщо можна) або +1 дозвіл (R-17); `pending_visit_id` воріт |
| `at_dock` | «На ворота» (охорона/диспетчер), авто R-05 | `at_dock_at` | без броні — бронювання `walk_in` (A-23) |
| `handling` | «Початок операції» (охорона/комірник), R-09 | `handling_start_at` (з `queued` — і `at_dock_at`) | `handling_end_at` — окремою дією/R-09 п. 2, стан не змінює |
| `weighed` | зважування `out` при `weighing_policy='in_out'` зі стану `at_dock`/`handling` | `weighed_out_at` | R-12: нетто → документи; авто-виїзд R-15 п. 11 |
| `left` | «Виїхала», петля виїзду після дозволу (R-17), `lost` камери виїзду (R-07) | `left_at` | R-05 `auto_call_next`; документи не змінюються |
| `rejected` | M-17 з `draft`/`planned`/`arrived` | `rejected_at`, `reject_reason` | бронювання → `cancelled`; події LPR рейсу → `handled` |
| `cancelled` | «Скасувати» з `draft`/`planned` | `cancelled_at` | бронювання → `cancelled` |

Будь-який інший перехід — `UserError` «Перехід «…» → «…» неможливий.». `_set_state` спершу блокує рядок рейсу
(`SELECT state FROM td_yard_visit WHERE id=%s FOR UPDATE`) і повторно перевіряє стан — два одночасні
«Пропустити» дають один перехід і одну команду (§11.8).

### 10.2 Бронювання `td.yard.booking.state`

`requested ──action_confirm (R-03)──► confirmed ──action_cancel──► cancelled ──action_reset──► requested`;
`requested ──action_cancel──► cancelled`. `confirmed` синхронізується з пакетом (R-02); перенесення в Gantt —
лише `write` слоту (R-03 → R-02).

### 10.3 Ворота `td.yard.gate.state` (R-16)

`unknown ⇄ closed ⇄ open ⇄ held`; будь-який → `error` (таймаут/невиконана команда); `error ──«Скинути помилку» /
«Відкрито вручну»──► перерахунок`. `unknown` — немає свіжих сигналів або `read_enabled=False`. Режим `mode`
(`auto`/`manual`) — окреме поле, змінює менеджер двору.

### 10.4 Подія LPR `match_state`

Створення → `matched` | `unmatched` | `low_confidence` | `unknown_camera` | `ignored`; `unmatched`/`low_confidence` →
`handled` (охорона: рейс без броні, відхилення, прив'язка, «Вирішено») | `expired` (крон через
`arrival_timeout_min` або `lost`); `update` камери може перевести `unmatched/low_confidence` → `matched`.

### 10.5 Зважування `state` і ваги `capture_state`

Зважування: `assigned` (є рейс) | `unassigned` (R-11 п. 5) → `assigned` (`action_assign`) | `void` (`action_void`, з
будь-якого). Ваги: `idle → settling → captured → idle` (R-11), будь-який → `offline` (R-16 п. 6) → `idle`.

### 10.6 Міграція `td.yard.migration_state`

`pending → skipped | partial | done`; `partial → done` після усунення конфліктів і «Повторити міграцію двору».

## 11. Обробка помилок

1. **Пристрої недоступні.** ADAM: сигнали `stale` (telemetry R-07) → ворота `unknown`, команди заблоковані
   (R-15 п. 5), охорона відкриває з пульта CAME і тисне «Відкрито вручну»; рейси ведуться вручну (FR-28). Камера:
   подій немає → охорона «Прибула» вручну з номером. Ваги: `offline` → ручне зважування (`source='manual'`).
2. **Колектор/Odoo недоступні.** Колектор буферизує показання й події (telemetry §8.3.4); події LPR приходять із
   затримкою з часом камери `ts`. Авто-пропуск (R-15 п. 10/11) виконується лише для подій з `now − ts ≤ 60 с`;
   старіші → `note` «Подія запізнилась на N с — авто-пропуск вимкнено», `kpp_alert=True`. Автозахоплення ваг —
   лише для показань не старших `weigh_max_age_s` (R-10).
3. **Дублікати.** LPR — ключ R-07 п. 3 + `event_id` telemetry; показання — `ON CONFLICT` telemetry; зважування —
   один `assigned` кожного виду на рейс (M-05); команди — `cmd_cooldown_s` і блокування рядка воріт
   (`SELECT … FOR UPDATE` у `action_command` перед п. 6 R-15).
4. **Застарілі дані.** Ворота/фотоелемент — `signal_max_age_s` (15 с); ваги — `weigh_max_age_s` (15 с); старіші
   показання оновлюють лише `last_*`, якщо новіші за збережені.
5. **Часові пояси.** БД — UTC naive; камера: `capture_timestamp` — UTC мс, поза вікном telemetry R-22 — час прийому;
   поле `datetime` камери не використовується (X-48); «сьогодні», добові лічильники, звіти, текст слотів — `Europe/Kyiv` (`zoneinfo`, перехід на
   зимовий час 25.10.2026 враховується автоматично; доба 25.10 має 25 год). Крони з фіксованим локальним часом
   — `nextcall` ставить хук у UTC з урахуванням поясу; після переходу DST час запуску зсувається на 1 год
   (прийнятно, Q не потрібне).
6. **Виняток у гачку показань (M-13)** — savepoint, `_logger.exception`, push telemetry не відкочується (показання
   збережені, двір пропускає пакет). Виняток в обробнику LPR (M-12) — telemetry пише в `td.push.event.error`
   (M-11 telemetry), подія повторно не надходить (дублікат `event_id`); охорона працює вручну.
7. **Невалідні вхідні дані.** Номер — R-08 п. 3; камера — `unknown_camera`; JSON без потрібних ключів — подія з
   порожніми полями й `low_confidence`; знімок — R-07 п. 7; текстові поля обрізаються до довжини поля; HTML/SQL у
   рядках зберігається як текст (ORM-параметризація, екранування QWeb/OWL).
8. **Паралельність.** Стан рейсу — блокування рядка в `_set_state`; підтвердження бронювань — блокування рядка воріт
   (R-03 п. 3); команди — блокування рядка воріт; автозахоплення — блокування рядка ваг
   (`SELECT … FROM td_yard_scale WHERE id=%s FOR UPDATE`) на час R-11; конфлікт серіалізації PostgreSQL у push
   telemetry повторює колектор.
9. **Зміна контрактів суміжних модулів** — `tests/test_contracts.py` (AC-78) падає на CI з назвою відсутнього поля
   чи методу.
10. **Видалені/відсутні записи.** Пакет видалено → `batch_id = NULL`, рейс працює без документів (`no_reference`);
    ворота без сигналів → `command_block_reason` «Сигнали не налаштовані»; немає `td.yard.scale` → «Зважити»
    відкриває ручне введення без ваг → `UserError("Немає автоваг у довіднику.")`.
11. **Одиниці.** `product.weight` в одиниці компанії (не кг) — перетворення R-12 п. 2; кадр SICS у `t`/`lb`/`g` —
    §8.5; невідома одиниця — `q='bad'`.
12. **Перевантаження ваг** (`S +`, > 60 000 кг) — показання `bad`, не захоплюється; КПП показує «Перевантаження»
    (`kpp_data.scale.state='offline'` не ставиться; `weight_kg = null`).
13. **Номери емулятора й макета.** iot_sim бере номер з `stock.picking.batch.td_plate` (M-07), а для рейсу без номера
    (`bookings[].plate = null`) генерує його сам (X-49) — тоді R-08 п. 7 (опис) дає збіг і заповнює номер рейсу.

## 12. Acceptance Criteria

Тип: UT — `TransactionCase`; HT — `HttpCase`/тур; CT — pytest плагіна; TC — стенд (ТК §13.2). Фікстури — §13.1.

| ID | FR / R | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01, R-01 | When `create({'visit_type': 'outgoing', 'plate': ' аа 4512 кт '})`; Then `name` відповідає `^YV/\d{4}/\d{5}$`, `side='east'`, `weighing_policy='in_out'`, `plate='АА 4512 КТ'`, `plate_norm='AA4512KT'`, `plate_display='АА 4512 КТ'`; `plate='A'` і `plate='AA#12'` → `ValidationError` | UT |
| AC-02 | FR-01, §10.1 | Given рейс із пакетом і бронюванням; When ланцюжок `confirm → arrive(t1) → admit(t2) → call_to_dock(t3) → start_handling(t4) → weighing out(t5) → leave(t6)` (час через `ts`/патч `fields.Datetime.now`); Then стани `planned…left`, кожна мітка = своєму `t`; повторний `action_arrive` → `UserError` «неможливий», `arrived_at` незмінний; `draft → left` → `UserError` | UT |
| AC-03 | FR-01, R-19 | Given мітки прикладу R-19 (09:10/09:30/10:50/11:00/11:05, план 09:30); Then `wait_min=20.0`, `dock_min=80.0`, `total_min=115.0`, `late_min=-20.0`; рейс без `left_at` → `total_min` порожній (`False`) | UT |
| AC-04 | FR-02, R-02 | Given пакет (`dock D1`, `scheduled 07:00`, `end 08:00` UTC) і бронювання `D2` 10:00–11:00; When `action_confirm`; Then пакет `dock_id=D2`, `scheduled_date=10:00`, `end_date=11:00`, рейс `planned`; при однакових значеннях `stock.picking.batch.write` не викликається (патч-лічильник); пакет `done` — не змінюється | UT |
| AC-05 | FR-02, R-02 | Given підтверджене бронювання; When `batch.write({'scheduled_date': +1 год})`; Then `booking.slot_start` = нове значення, `slot_end = end_date`; запис пакета, що створює перетин з іншим підтвердженим бронюванням воріт, → `ValidationError`, пакет і бронювання незмінні | UT |
| AC-06 | FR-02, §10.2 | When `action_cancel` єдиного підтвердженого бронювання рейсу `planned`; Then бронювання `cancelled`, рейс `draft`, поля пакета не змінені; `action_reset` → `requested` | UT |
| AC-07 | FR-03, R-03 | Given підтверджене `T1` 13:00–14:00; Then 13:30–14:30 на тих самих воротах `action_confirm` → `ValidationError`, текст починається з «Ворота DOCK-T1 уже заброньовані»; 14:00–15:00 → `confirmed`; `requested` 13:30–14:30 не блокує, `warning` містить «Перетин із запитом» | UT |
| AC-08 | FR-03, R-03 | Then 14:00–15:00 → `warning` містить «Між слотами 0 хв (буфер 15 хв)»; 14:15–15:15 → `warning == False` | UT |
| AC-09 | FR-03, R-03 | Given календар «Зміна 1» (07:00–11:30, 12:00–15:30, Пн–Пт); Then 15:00–16:00 → `warning` «Слот поза зміною «Зміна 1 (07:00–15:30)» (07:00–15:30).»; `enforce_calendar=True` → `ValidationError` тим самим текстом; субота → «День без зміни»; ворота східної сторони для `incoming` → `ValidationError` «на стороні»; ворота поза `picking_type_id.dock_ids` → `ValidationError` «не належать типу операцій» | UT |
| AC-10 | FR-04, R-04 | Given ворота `DOCK-T1` (`td_accepts=[Плитні матеріали]`) і пакет із товаром категорії «Крайка»; Then `booking.warning` містить «Ворота DOCK-T1 приймають: Плитні матеріали. У рейсі є: Крайка.»; товар «Плитні матеріали / ХДФ» → без цього рядка; `action_confirm` не блокується | UT |
| AC-11 | FR-05, R-05 | Given рейси V1…V4 прикладу R-05 (зараз 12:50); Then `_td_yard_queue('west')` = `[V4, V2, V1, V3]`; `_td_yard_queue('west', DOCK-W2)` = `[V4, V2, V1]` | UT |
| AC-12 | FR-05, R-05 | Then `action_call_to_dock` для V2 → `at_dock` на своїх воротах; для V1 (без броні) → перші вільні ворота без попередження R-04, нове бронювання `source='walk_in'`, `confirmed`, `[now, now+60 хв]`; усі ворота сторони зайняті → `UserError` «Немає вільних воріт»; передані ворота зайняті рейсом у `handling` → `UserError` «зайняті рейсом»; з `arrived` → `UserError` | UT |
| AC-13 | FR-05, R-05 | Then `_td_yard_call_next(DOCK-W2)` о 12:50 повертає/викликає V2 (V4 пропущено); `auto_call_next=True` і `action_leave` рейсу з `DOCK-W2` → наступний за чергою `at_dock`; `auto_call_next=False` → черга без змін | UT |
| AC-14 | FR-14, M-07 | Given пакет приймання з документом партнера-контакту компанії «Плитсервіс (демо)»; When `action_f3d_create_visit`; Then рейс `incoming`, `partner_id` = компанія (commercial), бронювання `requested` з `dock_id/scheduled_date/end_date` пакета, повертається дія форми рейсу; повторний виклик відкриває той самий рейс; пакет `internal` → `UserError`; `search_read('stock.picking.batch', fields=['td_visit_id','td_visit_state','td_plate'])` повертає значення | UT |
| AC-15 | FR-14, M-08, R-12 | Given документ із рухами 120 і 80 аркушів товарів з `weight=56`; Then `td_expected_weight_kg = 11200.0`; після проведення з `quantity` 72 і 48 → `6720.0`; `td_visit_id` = активний рейс пакета | UT |
| AC-16 | FR-14, M-09, M-10 | Then `res.partner.td_visit_count` рахує рейси, де партнер — постачальник, перевізник або водій (3 різні рейси → 3); onchange `driver_id` заповнює `driver_phone`, `driver_doc`, `carrier_id`, `plate` з картки водія; користувач лише з `group_td_user` → `read(['td_driver_doc'])` дає `AccessError` | UT |
| AC-17 | FR-12, R-12 | Given рейс `incoming` з документом на 11 200 кг; When зважування `in` 25 200 і `out` 14 000; Then рейс `gross_kg=25200`, `tare_kg=14000`, `net_kg=11200`, `weight_check='ok'`, `deviation_pct=0.0`; документ `td_net_weight_kg=11200`, `td_weight_check='ok'`; рейс `weighed` | UT |
| AC-18 | FR-12, R-12 | When брутто 25 520; Then `deviation`, `deviation_pct=2.86`, на документі одна активність «Відхилення нетто» (повторний перерахунок не додає другу); брутто 25 300 → `ok` (0.89); маса 6 600 і нетто 6 750 → `deviation` (2.27) | UT |
| AC-19 | FR-12, R-12 | Then товар з `weight=0` → `no_reference`; рейс `outgoing` (`in` 14 000, `out` 21 380) → `tare=14000`, `gross=21380`, `net=7380`, `shipping_weight` документа = 7380; два документи з масами 8 000 і 4 000 і нетто 12 300 → 8 200 і 4 100; `action_void` зважування `out` → рейс `net_kg=0`, `weight_check='none'` | UT |
| AC-20 | R-09 | Given рейс `at_dock` з документом; When `stock.move.line.write({'quantity': 12})`; Then рейс `handling`, `handling_start_at` заповнено; проведення всіх документів пакета → `handling_end_at`; з контекстом `f3d_yard_no_auto` — без змін | UT |
| AC-21 | FR-22, §10.1 | Then `user_reader.action_admit()` → `AccessError`; комірник: `action_start_handling` — так, `action_admit` — `AccessError`; охоронець: `action_admit`, `action_leave`, майстер відхилення — так, `action_cancel` — `AccessError`; диспетчер — `action_cancel` так | UT |
| AC-22 | FR-01, M-17 | Then `unlink` рейсу в `draft`/`planned`/`cancelled` — так, в `arrived` — `UserError`; майстер M-17 (`no_booking`, «немає документів») → `rejected`, `reject_reason="Немає бронювання: немає документів"`, бронювання `cancelled`; другий активний рейс на той самий пакет → `ValidationError`; `visit_type='outgoing'` з пакетом приймання → `ValidationError` | UT |
| AC-23 | FR-07, R-07 (X-48, X-73) | Given `freeze_time('2026-10-14 05:15:10')`; When `_td_handle_push('lpr', event)` з тілом iot_sim §8.13.2 (дослівно, `lpr_payload()`: `capture_timestamp='1791954905507'`); Then одна подія: `camera_code='CAM-05'`, `gate_id=GATE-W`, `direction='in'`, `car_state='new'`, `plate_raw='AA4512KT'`, `plate_unicode='АА4512КТ'`, `plate_norm='AA4512KT'`, `confidence=0.912`, `plate_list='f3d_bookings'`, `plate_list_mode='allow'`, `plate_list_description='BATCH/OUT/00004 DOCK-E2 Меблі Дім (демо)'`, `dedup_key='CAM-05\|12891\|2117397'`, `ts = 2026-10-14 05:15:05.507` (= `capture_timestamp`, той самий час, що показання `yard/lpr/CAM-05/plate` за telemetry R-22). When `capture_timestamp='1792391105507'` (19.10.2026, `ts_future`) → `ts = 2026-10-14 05:15:10` (час прийому), `note` містить «Час камери відкинуто»; без `capture_timestamp` (є `datetime`) → `ts` = час прийому, `datetime` ігнорується; `capture_timestamp` 31 добу тому (`ts_too_old` при `keep_days=30`) → час прийому | UT |
| AC-24 | FR-07, R-07 | Then повтор того самого тіла → подій 1; `carState=update` того ж `carID` з вищою довірою → рядків 1, `confidence` оновлено; тіло без `carID` → `dedup_key = 'evt\|' + event_id` | UT |
| AC-25 | FR-07, R-07 | Given `unmatched` подія з `kpp_alert`; When `carState=lost` того ж `carID`; Then `lost_at` заповнено, `match_state='expired'`, `kpp_alert=False`, нового рядка немає; `lost` без попередньої → рядок `ignored`; `_cron_queue` через 31 хв гасить інший `unmatched` → `expired` | UT |
| AC-26 | FR-07, R-07 | Then `imageArray=["<base64 JPEG 2 КБ>"]` → `ir.attachment` (`mimetype='image/jpeg'`, `res_model='td.yard.lpr.event'`); 1,5 МБ → без вкладення, `note` містить «Знімок відхилено»; base64 тексту → відхилено; `lpr_store_images=False` → без вкладення; `imagesURI=["https://10.90.2.5/a.jpg"]` → `image_url`; `imageFile` ігнорується | UT |
| AC-27 | FR-08, R-08 | `normalize_plate` / `display_plate`: усі приклади R-08 п. 1–2 (таблиця в тесті) | UT |
| AC-28 | FR-08, R-08 | Given `planned` рейс з номером `АА7310КТ`, слот 13:00; When подія CAM-05 12:40 з цим номером; Then `matched`, рейс `arrived`, `arrived_at` = час події, `gate_in_id=GATE-W`; слот на 5 год пізніше → `unmatched`; повторна подія для `arrived` → стан незмінний, `note` «Повторне розпізнавання»; CAM-06 для рейсу в `handling` → `matched`, `gate_out_id=GATE-E` | UT |
| AC-29 | FR-08, R-08 | Then опис `"WH/IN/00131 DOCK-W2 …"` і рейс без номера → `matched`, номер рейсу ← `АА7310КТ`; рейс з іншим номером → `matched`, `kpp_alert=True`, `note` «≠», команд немає; два рейси з однаковим номером → обрано той, чий пакет в описі | UT |
| AC-30 | FR-08, R-07, R-08 | Then довіра 0.62 → `low_confidence`, `kpp_alert`; `sensorProviderID='CAM-99'` → `unknown_camera`; `read_enabled=False` → `ignored`, `gate.last_plate` незмінний, рейс незмінний | UT |
| AC-31 | FR-06, R-06 | Given ворота `auto`, `write_enabled=True`, сигнали свіжі; When подія без збігу; Then `kpp_alert=True`, `td.command` не створено | UT |
| AC-32 | FR-06, R-06 | Then майстер M-16 охоронця → рейс `arrived`, `is_walk_in=True`, подія `handled`; при 5 рейсах без броні сьогодні — `UserError` з «(5)»; диспетчер → 6-й створено; `walk_in_allowed=False` → охоронець `UserError` «лише диспетчер» | UT |
| AC-33 | FR-06, M-17 | Then «Відхилити» подію без рейсу → рейс `other`, `rejected`, `is_walk_in=True`, подія `handled`; відхилення `planned` рейсу → бронювання `cancelled` | UT |
| AC-34 | FR-09, R-15 | Given `write_enabled=False`; When `gate.action_command('open')` охоронцем; Then `UserError` з «td.yard.write_enabled»; команд 0 | UT |
| AC-35 | FR-09, R-15 | Then `user_reader` → `AccessError`; охоронець (`write_enabled=True`, сигнали свіжі) → `td.command`: `signal_id` = `cmd_open`, `value=1.0`, `origin='yard'`, `expires_at = now + 30 с`, `requested_by` = охоронець, `td_yard_gate_id`, `td_yard_kind='open'`, `td_yard_reason='manual'`; `release` → сигнал `cmd_hold`, `value=0.0`; виклик з `reason='auto_booking'` без `sudo` → `AccessError` | UT |
| AC-36 | FR-09, R-15 | Then фотоелемент `1` → `UserError` «перешкода»; `last_ts` фотоелемента 60 с тому → `UserError` «Немає свіжих даних»; команда `queued` 10 с тому → `UserError` «ще виконується»; `cmd_open.write_enabled=False` → `UserError` «не налаштований» | UT |
| AC-37 | FR-09, R-15 | Given `mode='auto'`, бронювання 13:00; Then подія 12:40 → команда `auto_booking`, рейс `queued`; 11:50 → команди немає, `note` «Поза вікном слоту 12:00–15:00», `kpp_alert`; `mode='manual'` → команди немає, `kpp_alert=False`; подія з `ts` 5 хв тому → без команди, `note` «запізнилась»; CAM-06 для рейсу `weighed` → команда `auto_exit` | UT |
| AC-38 | FR-10, R-16 | Given команда `open` `done` о T; Then DI0=1 о T+4 → `state='open'`, без помилки; DI0=0 і `refresh` о T+11 → `state='error'`, `last_error` «Немає підтвердження відкриття за 10 с», активність для `responsible_id`; команда `expired` → `error` «не виконано»; «Скинути помилку» → перерахунок | UT |
| AC-39 | FR-10, R-16 | Then `hold` → `hold_until = now + 30 хв`, DI0=1 → `held`; `_cron_queue` після `hold_until` → команда `release` (`auto_hold_max`), `hold_until=False`; при `write_enabled=False` — лише очищення й чаттер «Утримання знято» | UT |
| AC-40 | FR-10, R-17 | Given `passes_day_start=7`, `admitted_today=0`; When «Пропустити» (+1), лічильник 8, потім 9; Then `passes_today=2`, `tailgate_today=1`, чаттер «Проїзд без дозволу»; `antipassback=False` → `tailgate_today=0`; петля 1→0 при `pending_visit_id` у стані `weighed` на GATE-E → рейс `left`; на GATE-W → `pending_visit_id` очищено, стан рейсу незмінний | UT |
| AC-41 | FR-11, R-10 | Then ручне зважування 300 кг і 61 000 кг → `ValidationError` «поза межами»; друге `assigned` зважування `in` для рейсу → `ValidationError`; `ts` через 5 хв у майбутньому → `ValidationError` | UT |
| AC-42 | FR-11, R-10, R-16 | Then показання ваг з `ts` 20 с тому → захоплення немає; `action_capture` при такому показанні → `UserError` «введіть вагу вручну»; сигнал ваги `stale` + `_cron_queue` → `capture_state='offline'` | UT |
| AC-43 | FR-13, R-11 | Given один рейс `queued` (`in_out`, без `in`); When `_td_ingest` з кадрами прикладу R-11 (через `td.signal._td_ingest`, `src='module'`); Then одне зважування `auto`, `weight_kg=25200`, `kind='in'`, `role='gross'`, рейс `weighed_in_at`; подальші `25 200 S` — без нових; `300 S` → `idle`; наступна фура 14 000 → нове захоплення | UT |
| AC-44 | FR-13, R-11 | Then лише кадри `D` → немає зважування; два `S` з різницею 60 кг → немає (кандидат замінено); `q='bad'` (перевантаження) → ігнор, `last_weight_kg` незмінний | UT |
| AC-45 | FR-13, R-11 | Then два кандидати `queued` → зважування `unassigned`, `kind='check'`; `action_assign(visit)` → `assigned`, `kind='in'`, `weighed_in_at`; рейс `handling` з `handling_end_at` і `in` → захоплення `out`, рейс `weighed` | UT |
| AC-46 | FR-15 | Then після установки: `GATE-W` (`direction='in'`, `side='west'`, `camera_code='CAM-05'`, `pos=(−20,−30)`, `mode='manual'`), `GATE-E` (`out`, `east`, `CAM-06`, `scale_id=TRUCK-SCALE`), `TRUCK-SCALE` (`max_kg=60000`, `min_kg=400`, `division_kg=20`, `pos=(172,−14)`); друга активна брама з `CAM-05` → `ValidationError` | UT |
| AC-47 | FR-15, R-16 | Then DI0 свіжий 1 → `open`; `invert_di=True` → `closed`; сигнал `stale` → `unknown`; `last_error` + свіжий DI → `error`; `read_enabled=False` → `unknown` | UT |
| AC-48 | FR-16, M-13, R-24 к. 2 | Then 18 `td.signal` з кодами й адресами Додатка A, `module='yard'`; 2 джерела з `params` §5.3 (`module='yard'`), валідація telemetry за схемою §8.2 без помилок (зокрема № 18 `field: "stable"`, X-45); сигнали LPR на `HTTP-PUSH`; 16 полів-сигналів воріт/ваг заповнено; повторний крок → `signals_created=0`, `signals_updated=18`, `last_value` незмінний; `_td_ingest` пакета без кодів `yard/gates\|scale` додає 0 SQL-запитів (`assertQueryCount` різниці з викликом `super`) | UT |
| AC-49 | FR-17, R-13 | `parse_line` і перетворення показань — усі рядки таблиці §8.5; `ES`/`ET`/`EL` → `error`; `g`/`t`/`lb` → кг | CT |
| AC-50 | FR-17, R-14 | Given `FakeSicsServer` (кадри `S S 21380 kg`); Then `poll` у режимі `poll` → 2 показання (`21380.0`, `1.0`, `good`); режим `stream` → `SIR` надіслано, `poll` віддає останній кадр, наступний `poll` без нових кадрів → `[]`; `@` → `health().stats.device='FAKE-0001'`; сервер без `@` (`ES`) — підключення успішне | CT |
| AC-51 | FR-17, R-14 | Then сервер не відповідає (`reply_delay_s=10`, `timeout_s=1`) → `PollError`; `drop_after=3` у `stream` → `PollError`, повторний `connect` відновлює кадри; 3 помилки поспіль → `health().state='error'`; `allowlist` відмовляє → `AllowlistDenied` до спроби з'єднання | CT |
| AC-52 | FR-17 | Then `write` з `address.write.cmd='Z'` у `stream` → результат `"Z A"`, у `server.received` після `Z` знову `SIR`; `T` → `"T S …"`; `TAC` на сервері, що відповідає `ES` → `WriteError`; `cmd='TA'` → `NotSupported`; `settings.write_enabled=False` → `WriteError`; схеми §8.2 приймають приклади §5.3/Додатка A і `{"field":"weight","scale":0.001,"offset":0}` (X-70), відхиляють `{"field":"weight","write":{"cmd":"TA"}}`, `"scale": 0` та невідомі ключі; кадр `S S 21380 kg` з `scale=0.001` → `21.38` | CT |
| AC-53 | FR-18 | Then `get_views` для `td.yard.visit` (kanban, list, form, pivot, graph, search) і `td.yard.booking` (gantt, calendar, list, form, search) без помилок; `read_group` kanban за `state` повертає 7 колонок `_group_expand_states` | UT |
| AC-54 | FR-18 | Тур `f3d_yard_dispatch_tour`: меню «Двір → Диспетчерська», картка рейсу `arrived` → «Пропустити» → картка в колонці «У черзі»; форма рейсу показує кнопки лише свого стану | HT |
| AC-55 | FR-18 | Then серверна дія «Диспетчеризація (стандарт)» на базі з `stock_fleet_enterprise` → `views[0]` = (`view_stock_picking_batch_gantt`, `gantt`), `domain=[('dock_id','!=',False)]`; без модуля (патч `env.ref` → `None`) → `view_mode` без `gantt` | UT |
| AC-56 | FR-19, API-01 | Given рейс `arrived` з броньованим слотом у вікні, рейс без броні, подія `unmatched`; When `kpp_data()` охоронцем; Then ключі API-01; картки `green`/`yellow`, дії `["admit","reject"]`; подія з діями `["walk_in","reject","link","dismiss"]`; `can.command=False` і `command_block` з «write_enabled»; `user_reader` → `AccessError` | UT |
| AC-57 | FR-19, API-02 | Then `kpp_action('admit', visit_id)` → рейс `queued`, `ok=True`; `'weigh'` з `values={'weight_kg': 25200}` → зважування `manual`; `'reject'` → `action` = дія M-17; `'walk_in'` → дія M-16; `'unknown'` → `UserError` | UT |
| AC-58 | FR-19 | Тур `f3d_yard_kpp_tour`: дія «Екран КПП» відкривається, картка з номером `АА 7310 КТ` у «На КПП», «Пропустити» → картка в «У дворі»; кнопка «Відкрити» `disabled` з `title`, що містить «вимкнено»; `kpp_data` на 50 рейсах і 20 подіях ≤ 50 мс (середнє 5 викликів) | HT |
| AC-59 | FR-20 | Then дії журналів відкриваються охоронцем; `user_reader` читає зважування, але `td.yard.lpr.event` → `AccessError`; `action_td_yard_command` показує лише команди з `td_yard_gate_id` | UT |
| AC-60 | FR-21 | Given два рейси одного перевізника з `wait_min` 20 і 40 і рейс без `at_dock_at`; Then `read_group(['carrier_id'], ['wait_min:avg'])` → 30.0 | UT |
| AC-61 | FR-21, R-19 | Given рейс прикладу R-19 на `DOCK-T1`; Then рядок звіту: `busy_min=80.0`, `idle_min=400.0`, `occupancy_pct=16.7`, `visit_count=1`; параметр `dock_shift_min=600` → `idle_min=520.0` без переустановки | UT |
| AC-62 | FR-23, R-20 | When `_td_viewer_collect(payload={}, ctx)`; Then `payload['yard']` має `gates`, `scale`, `trucks`, `queue`, `kpp`, `stats`, `updated`; рейс `handling` на західних воротах `td_x=0, td_y=5` → `x=-7.3, y=5.0, rz=0`; на східних `(150, 15)` → `(157.3, 15.0, 180)`; `arrived` на GATE-W → `(-20.0, -22.0, 90)`; другий `queued` заходу → `(-26.0, 25.0, 90)`; `weighed` 30 с тому → `(172.0, -14.0, 90)`; `ctx.kiosk` → `plate=None`; користувач без `GRP_SEC` → `gates[*].last_plate=None` | UT |
| AC-63 | FR-23, A-16 | Given `payload['infra']['cards']` з `GATE-W`, `TRUCK-SCALE`; Then рядки карток R-20 п. 6 («Стан», «Сьогодні проїздів», «Режим»; «Остання машина» = «АА 4512 КТ · брутто 21 380 кг · WH/OUT/00413»); payload без `infra` → ключ `infra` не створено | UT |
| AC-64 | FR-23, R-21 | Given патч `_td_yard_viewer_event()` → `Mock`; When `action_admit`; Then `_notify('td.yard.visit', [name, scene_code, dock_code], 'doc')`; зміна стану воріт → `_notify('td.yard.gate', ['GATE-W'], 'state')`; 10 переходів у транзакції → один `bus.bus._sendone` на модель (`precommit`) | UT |
| AC-65 | FR-23 | Then модель `td.viewer.provider.yard` є в реєстрі без `td_viewer3d`, `_td_sequence=160`, `_td_sections=('yard',)`; `_td_viewer_delta(patch, {'changes': {}})` → `patch` порожній; з `{'changes': {'td.yard.visit': {...}}}` → `patch['yard']` | UT |
| AC-66 | FR-22 | Then `menu_td_yard` (батько `td_factory3d.menu_td_root`, `sequence=60`) і 16 пунктів його дерева із групами й sequence §3; `menu_td_yard_config_settings` — батько `td_factory3d.menu_td_config`, `sequence=60` (X-32); ланцюжок `implied_ids` §4.2; `group_td_admin` ⊃ `group_td_yard_manager` | UT |
| AC-67 | FR-22, §4.1 | Then для кожного рядка CSV `check_access` (read/write/create/unlink) користувачів `reader`, `stock`, `guard`, `dispatcher`, `manager` відповідає матриці (параметризований тест) | UT |
| AC-68 | FR-24, §4.4 | Then `user_reader`: `visit.read(['driver_phone'])`, `gate.read(['last_plate'])` → `AccessError`; `search_read(fields=['name','plate'])` — так; охоронець читає `driver_doc` | UT |
| AC-69 | FR-22, §4.3 | Given рейс компанії B; Then користувач лише компанії A не бачить його (`search_count = 0`) | UT |
| AC-70 | FR-24, R-22 | Given рейс `left` 96 діб тому з телефоном і документом; Then `_cron_gc` → `driver_phone=False`, `driver_doc=False`, `pii_cleared=True`, `plate` збережено; рейс 86 діб — без змін | UT |
| AC-71 | FR-24, R-22 | Then подія LPR 31 добу тому зі знімком → видалена разом із `ir.attachment`; 29 діб — лишається; непризначене зважування 8 діб тому → видалене | UT |
| AC-72 | FR-25 | Then хук крок 0: `environment='test'` → `read_enabled='True'`; `'prod'` (свіжа установка) → `'False'`; при `read_enabled=False` подія LPR → `ignored`, `_td_ingest` воріт не змінює `passes_today`, ворота `unknown` | UT |
| AC-73 | FR-25 | When виконати `data/neutralize.sql` (`cr.execute`); Then `write_enabled='False'`, `read_enabled='False'`, крони модуля `active=False`, ворота `mode='manual'`, джерела `module='yard'` з `read_enabled=False` | UT |
| AC-74 | FR-25, §4.4 | Then жодного параметра `td.yard.*` з `token`/`secret`/`password` у ключі; обробка події зі знімком і рейсом із телефоном водія при рівні логів INFO не пише в журнал телефон, документ і base64 (`assertLogs` + пошук підрядків) | UT |
| AC-75 | FR-26, R-24 | Given копія демо-бази після base і telemetry; When установка; Then `migration_state='done'`, звіт §5.4 (`visits: 6`, `bookings: 6`, `conflicts: 0`, `weighings: 1`, `products_weighted: 7`, `carriers_linked: 2`, `signals_created: 18`, `sources_created: 2`, `linked_equipment: 3`); 6 рейсів таблиці §5.4 (тип, партнер, перевізник, ворота, слот, номер); `YV/2026/00001.wait_min=20.0` | TC |
| AC-76 | FR-26, R-24 | Then синтетично (пакети `TRUCK-T-1` incoming, `TRUCK-T-2` outgoing з доками, перевізник «Власний транспорт»): `run_all` → 2 рейси `handling`, 2 бронювання `migration`; повторний `run_all` → `visits: 0`, `bookings: 0`; база без пакетів → `migration_state='skipped'`; копія демо — повтор кнопкою меню нічого не дублює (TC) | UT+TC |
| AC-77 | FR-26, A-11 | Then крок 3: товари `DSP16-SON` (вага 0) → 56, `MDF18-RAW` → 70, товар з вагою 60 — незмінний; `seed_product_weights=False` → 0 змін | UT |
| AC-78 | FR-27 | Then `test_contracts`: `td.signal._td_ingest(readings, src, collector)`, `td.command` поля (`signal_id`, `value`, `state`, `origin`, `expires_at`, `requested_by`, `done_at`, `error`), `td.push.handler._td_push_routes`, `stock.picking.batch` (`dock_id`, `end_date`, `td_code`), `td.scene.mixin.search_f3d`, `td.zone.zone_at` існують; усі класи тестів мають теги `post_install`, `-at_install`, `f3d`, `f3d_yard` | UT |
| AC-79 | FR-28 | Given сигнали без значень (`unknown`), `write_enabled=False`; When повний ручний цикл: бронювання → «Прибула» → «Пропустити» → «На ворота» → ручне зважування `in`/`out` → «Виїхала»; Then кожна дія успішна, `admitted_today=1`, чаттер «відкрийте з пульта CAME», нетто пораховано; `kpp_data.can.command=False` з поясненням; ворота `unknown` | UT |
| AC-80 | §6, R-23, R-19 | Then `_cron_day_reset` → `passes_day_start = counter_value`, лічильники дня 0; `_cron_queue`: рейс `planned` зі слотом 3 год тому → `is_no_show=True`; ворота перераховують стан | UT |
| AC-81 | FR-07, FR-08, FR-09, FR-13 | ТК-01: `truck_arrival` повний цикл на стенді (§13.2) | TC |
| AC-82 | FR-07 | ТК-02: ручний POST LPR на колектор `POST /f3d/lpr` (маршрут `lpr`, токен у `X-F3D-Token`) → колектор шле в Odoo `POST /f3d/telemetry/event` з `route="lpr"` → подія в Odoo ≤ 10 с; без токена → колектор `401`, подій немає. Odoo маршруту `/f3d/lpr` не має: `POST /f3d/telemetry/event` без токена колектора → `401` | TC |
| AC-83 | FR-06 | ТК-03: `truck_no_booking` → картка «Без бронювання», DI0 = 0 весь `wait_min`, рейс без броні створено охоронцем | TC |
| AC-84 | FR-09, FR-10 | ТК-04: команда `open` → coil 16 = 1 і через 1,5 с — 0 (`pulse_ms`, X-46), DI0 = 1 ≤ 6 с, ворота `open`; `F3D_WRITE_ENABLED=0` → команда `expired`, ворота `error` | TC |
| AC-85 | FR-11, FR-13, FR-28 | ТК-05/ТК-06: автозважування з емулятора (брутто 25 200 ± 20) і перехід на ручне при зупиненому SICS | TC |
| AC-86 | FR-23 | ТК-08: `/f3d/viewer/data` містить `yard` з 6 фурами й `meta.sections.yard='live'`; картки `GATE-W`, `TRUCK-SCALE` з живими рядками | TC |
| AC-87 | FR-23, R-20 п. 7 (X-23) | Given `patch = {"infra": {"totals": {"genset_kw": 348}, "cards": {"GENSET": {"rows": [["Стан", "резерв"]]}, "GATE-W": {"title": "КПП приймання"}}}}` (дельта інших провайдерів); When `_td_viewer_delta(patch, {"changes": {"td.yard.gate": {...}}})`; Then `patch["infra"]["totals"] == {"genset_kw": 348}`, картка `GENSET` незмінна, `GATE-W` має і `title`, і `rows` R-20 п. 6, `GATE-E` і `TRUCK-SCALE` мають `rows`; об'єкт `patch["infra"]` той самий (`is`, злиття, не присвоєння); `patch["yard"]` — повний розділ | UT |
| AC-88 | FR-09, FR-15, R-15 (X-46, X-47) | Then сигнали хука: `cmd_open`/`cmd_close` — `address.write = {"fc": 5, "addr": 16/18 (GATE-W), 17/19 (GATE-E), "pulse_ms": 1500}`; `cmd_hold` — без `pulse_ms`, `GATE-W` `addr 20`, `GATE-E` `addr 21`; охоронець з `enable_writes()`: `gate_e.action_hold()` → `td.command.signal_id` = `yard/gates/GATE-E/cmd_hold`, `value=1.0`; `gate_w.action_hold()` → `yard/gates/GATE-W/cmd_hold` (різні сигнали й адреси) | UT |

## 13. План тестування (для Opus)

### 13.1 Юніт-тести (`odoo.tests`, теги `post_install`, `-at_install`, `f3d`, `f3d_yard`)

Запуск: `odoo-bin -d f3d_yard_test -i td_yard --test-tags /td_yard --stop-after-init --without-demo=all`
(чиста база; `td_factory3d` і `td_telemetry` ставляться як залежності). Час — `freezegun.freeze_time`
(входить у залежності тестів Odoo 19) у UTC: «12.10.2026 12:50 Київ» = `freeze_time("2026-10-12 09:50:00")`.

`tests/common.py` — `class YardCase(TransactionCase)`, `setUpClass`:
- `cls.company = env.company`; `cls.company_b` = нова компанія (AC-69); `cls.wh` — склад компанії; `cls.in_type`,
  `cls.out_type`, `cls.int_type`.
- Категорії: `categ_boards` «Плитні матеріали», `categ_hdf` («ХДФ», батько `categ_boards`), `categ_edge` «Крайка»,
  `categ_fur` «Фурнітура». Товари (`type='consu'`, `is_storable=True`, одиниця «Units»): `prod_dsp16` (`DSP16-T`,
  `weight=56`, плити), `prod_mdf18` (`MDF18-T`, 70), `prod_hdf` (`HDF3-T`, 12, ХДФ), `prod_edge` (`EB-T`, 0,
  крайка), `prod_fur` (`FUR-T`, 0), `prod_heavy` (`W60-T`, 60).
- Ворота (хелпер base-подібний `make_dock(code, side, no, x, y, accepts=())`: `stock.location` `usage='internal'`
  під `wh.view_location_id`, `write({'td_code', 'td_kind': 'dock', 'td_side', 'td_dock_no', 'td_x', 'td_y',
  'td_accepts'})`, `f3d_register_dock()`): `dock_w1` = `DOCK-T1` (west, 1, 0, 5, плити), `dock_w2` = `DOCK-T2` (west, 2,
  0, 15), `dock_w5` = `DOCK-T5` (west, 5, 0, 45, крайка), `dock_e1` = `DOCK-TE1` (east, 1, 150, 15).
- Календар `cal` «Зміна 1 (07:00–15:30)» (`tz='Europe/Kyiv'`, Пн–Пт 07:00–11:30 і 12:00–15:30); параметр
  `calendar_id = cal.id`.
- Користувачі (`new_test_user`): `user_reader` (`base.group_user`, `td_factory3d.group_td_user`), `user_stock`
  (`stock.group_stock_user`), `user_guard` (`group_td_yard_security`), `user_disp` (`group_td_yard_dispatcher`),
  `user_mgr` (`group_td_yard_manager`), `user_admin` (`td_factory3d.group_td_admin`), `user_b` (лише
  `company_b`, `group_td_yard_dispatcher`).
- Партнери: `supplier` «Плитсервіс (демо)» (компанія) з контактом `supplier_contact`; `client` «Меблі Дім (демо)»;
  `carrier` «Нова Пошта Вантаж (Т)» (`td_is_carrier`); `driver` (особа, `phone='+380501112233'`,
  `td_driver_doc='ВХК123456'`, `td_is_driver`, `td_carrier_id=carrier`, `td_default_plate='АА7310КТ'`).
- Дані модуля: `gate_w = env.ref('td_yard.gate_w')`, `gate_e`, `scale = env.ref('td_yard.scale_truck')`;
  сигнали за кодами Додатка A (створені хуком установки на чистій базі); `responsible_id` воріт = `user_guard`.
- Хелпери: `kyiv(hhmm, day='2026-10-12') -> datetime UTC`; `set_param(name, value)`; `set_signal(code, value,
  age_s=1, status='ok')` (запис `last_value`, `last_ts = now − age_s`, `status` під `sudo`); `fresh_gate(gate,
  open=0, loop=0, photocell=0)`; `enable_writes()` (параметри `td.yard.write_enabled`,
  `td.telemetry.write_enabled` = `True`, `write_enabled=True` на `MB-U86-IO7` і cmd-сигналах);
  `make_picking(ptype, lines, partner)` (підтверджений, `assigned`); `make_batch(pickings, dock=None, start=None,
  end=None, code=None)`; `make_visit(**vals)`; `make_booking(visit, dock, start, end, confirm=True)`;
  `lpr_payload(**over) -> dict` (тіло iot_sim §8.13.2 дослівно + перевизначення); `push_lpr(payload, ts=None,
  event_id=None)` → `env['td.push.handler.yard']._td_handle_push('lpr', {...})`; `ingest(rows)` →
  `env['td.signal']._td_ingest([{'code', 'ts', 'value', 'q'}], src='module')`; `viewer_mock()` — контекстний
  менеджер `patch.object(type(env['td.yard.visit']), '_td_yard_viewer_event', return_value=Mock())` і так само
  для воріт/ваг; `jpeg_b64(size_kb)` — валідний JPEG заданого розміру.

| Файл / клас | Тести | AC | Фікстури | Що саме assert |
|---|---|---|---|---|
| `test_visit.py::TestVisitBasics` | `test_create_defaults`, `test_plate_validation` | AC-01 | — | значення полів; `ValidationError` |
| `::TestTransitions` | `test_full_chain_timestamps`, `test_invalid_transition`, `test_repeat_arrive_keeps_ts` | AC-02 | пакет + бронювання, `freeze_time` по кроках | `state`, кожна `*_at`; текст «неможливий» |
| `::TestDurations` | `test_example_r19`, `test_missing_marks` | AC-03 | мітки через `write` під `sudo` | 20/80/115/−20; `False` |
| `::TestRights` | `test_reader_cannot_admit`, `test_stock_user_handling`, `test_guard_actions`, `test_dispatcher_cancel` | AC-21 | користувачі `common` | `AccessError` / успіх через `with_user` |
| `::TestUnlinkReject` | `test_unlink_states`, `test_reject_wizard`, `test_batch_unique`, `test_type_mismatch` | AC-22 | — | `UserError`/`ValidationError`; `reject_reason` |
| `test_booking.py::TestSync` | `test_confirm_writes_batch`, `test_no_write_when_equal`, `test_done_batch_untouched`, `test_reverse_sync`, `test_reverse_conflict`, `test_cancel_to_draft` | AC-04…AC-06 | `patch.object(type(env['stock.picking.batch']), 'write', autospec=True, side_effect=…)` для лічби | поля пакета/бронювання; кількість викликів |
| `::TestConflicts` | `test_overlap_error`, `test_touching_ok`, `test_requested_warning`, `test_buffer_warning`, `test_calendar_warning`, `test_enforce_calendar`, `test_weekend`, `test_side_and_type_docks`, `test_parallel_confirm_lock` | AC-07…AC-09 | `dock_w2`, `cal`; для блокування — другий курсор `self.registry.cursor()` | тексти починаються з фраз R-03; другий курсор чекає/отримує `ValidationError` |
| `::TestCategories` | `test_warning_text`, `test_child_ok`, `test_not_blocking` | AC-10 | `dock_w1`, `prod_edge`, `prod_hdf` | рядок `warning` |
| `::TestQueue` | `test_order`, `test_order_for_dock`, `test_call_booked`, `test_call_walk_in_picks_dock`, `test_no_free_dock`, `test_dock_busy`, `test_call_wrong_state`, `test_call_next_skips_walk_in`, `test_auto_call_next` | AC-11…AC-13 | V1…V4 (R-05) | порядок списку; нове бронювання `walk_in`; `UserError` тексти |
| `test_picking.py::TestBatchVisit` | `test_create_visit_button`, `test_reopen_existing`, `test_internal_batch`, `test_search_read_fields` | AC-14 | `make_batch` | значення, тип дії |
| `::TestExpected` | `test_expected_demand`, `test_expected_done_qty`, `test_related_visit` | AC-15 | 120/80 `prod_dsp16` | 11200.0 / 6720.0 |
| `::TestPartner` | `test_visit_count`, `test_driver_onchange`, `test_driver_doc_hidden` | AC-16 | `driver`, `carrier`, `Form(visit)` | лічильник; поля onchange; `AccessError` |
| `::TestNetCheck` | `test_ok`, `test_deviation_activity_once`, `test_ok_within_tolerance`, `test_small_doc`, `test_no_reference`, `test_outgoing_shipping_weight`, `test_allocation_two_pickings`, `test_void_recompute` | AC-17…AC-19 | зважування `manual` через ORM | поля рейсу/документа; `mail.activity` count == 1 |
| `::TestAutoHandling` | `test_move_line_starts`, `test_done_sets_end`, `test_no_auto_context` | AC-20 | рейс `at_dock` | стан, мітки |
| `test_lpr.py::TestIntake` | `test_iot_sim_example_fields`, `test_plate_list_mode`, `test_capture_ts_consistent`, `test_capture_ts_out_of_window`, `test_datetime_ignored`, `test_dedup_same_body`, `test_update_merges`, `test_no_carid_key`, `test_lost_expires`, `test_lost_without_prior`, `test_cron_expire` | AC-23…AC-25 | `lpr_payload`, `freeze_time` | поля події; кількість рядків |
| `::TestImages` | `test_jpeg_saved`, `test_too_big`, `test_not_image`, `test_store_disabled`, `test_images_uri`, `test_image_file_ignored` | AC-26 | `jpeg_b64` | `ir.attachment` count/mimetype; `note` |
| `::TestPlate` | `test_normalize_examples`, `test_display_examples` | AC-27 | — (чисті функції `tools/plate.py`) | рівність |
| `::TestMatching` | `test_plate_match_arrive`, `test_window`, `test_repeat_note`, `test_exit_match`, `test_description_fills_plate`, `test_description_plate_conflict`, `test_ambiguous_by_doc`, `test_low_confidence`, `test_unknown_camera`, `test_read_disabled_ignored` | AC-28…AC-30 | рейси з бронюваннями на `dock_w2` | `match_state`, стан рейсу, `kpp_alert`, `note` |
| `::TestWalkIn` | `test_unmatched_no_command`, `test_wizard_creates`, `test_limit_guard`, `test_dispatcher_over_limit`, `test_walk_in_disallowed`, `test_reject_event`, `test_reject_planned` | AC-31…AC-33 | `enable_writes`, `gate_w.mode='auto'` | `td.command` count == 0; стани |
| `test_commands.py::TestCommandChecks` | `test_write_disabled`, `test_reader_access`, `test_guard_creates_command`, `test_release_value`, `test_auto_reason_needs_su`, `test_photocell_blocked`, `test_photocell_stale`, `test_cooldown`, `test_signal_write_disabled` | AC-34…AC-36 | `enable_writes`, `fresh_gate` | поля `td.command`; тексти помилок |
| `::TestCommandAddresses` | `test_pulse_on_open_close`, `test_hold_level_separate_channels`, `test_hold_commands_per_gate` | AC-88 | сигнали хука (Додаток A), `enable_writes`, `fresh_gate` | `address.write` (`addr`, `pulse_ms`); `signal_id` команд `hold` |
| `::TestAutoOpen` | `test_auto_in_window`, `test_auto_outside_window`, `test_manual_mode`, `test_late_event`, `test_auto_exit` | AC-37 | бронювання 13:00, `freeze_time` 12:40/11:50 | команда `auto_booking`/`auto_exit`; `note` |
| `test_gate.py::TestTimeouts` | `test_open_confirmed`, `test_open_timeout_error`, `test_command_expired_error`, `test_reset_error`, `test_hold_and_release`, `test_hold_release_without_writes` | AC-38, AC-39 | команда з `state='done'`, `done_at` (запис під `sudo`) | `state`, `last_error`, `mail.activity` |
| `::TestPasses` | `test_tailgate_example`, `test_antipassback_off`, `test_leave_by_loop`, `test_entry_loop_clears_pending`, `test_counter_reset` | AC-40 | `ingest` з кодами `passes`/`loop` | лічильники; стан рейсу |
| `::TestGateData` | `test_gate_scale_records`, `test_camera_unique`, `test_state_from_signals` | AC-46, AC-47 | data | значення; `ValidationError`; стани `open/closed/unknown/error` |
| `test_scale.py::TestManual` | `test_limits`, `test_duplicate_kind`, `test_future_ts` | AC-41 | — | `ValidationError` |
| `::TestCapture` | `test_stale_not_captured`, `test_capture_action_stale`, `test_offline_cron`, `test_capture_example_r11`, `test_no_new_while_captured`, `test_next_truck`, `test_unstable`, `test_diff_too_big`, `test_overload_bad` | AC-42…AC-44 | `ingest` кадрами R-11 з `freeze_time` | зважування count/вага/роль; `capture_state` |
| `::TestAssign` | `test_two_candidates_unassigned`, `test_assign`, `test_out_ready` | AC-45 | 2 рейси `queued` | стани зважування й рейсу |
| `::TestSignalsData` | `test_18_signals`, `test_sources_params`, `test_http_push_reuse`, `test_links`, `test_rerun_upsert`, `test_ingest_no_yard_no_queries` | AC-48 | `hooks.migrate.signals_and_sources(env)`; `self.assertQueryCount` | коди/адреси = Додаток A (рядки в тесті як константа); кількість запитів |
| `test_kpp.py::TestKppData` | `test_structure`, `test_colors_actions`, `test_command_block`, `test_reader_denied` | AC-56 | рейси/події | ключі й значення API-01 |
| `::TestKppAction` | `test_admit`, `test_weigh_manual`, `test_reject_action`, `test_walk_in_action`, `test_unknown_action` | AC-57 | — | стани; dict дії |
| `::TestViews` | `test_get_views`, `test_kanban_columns`, `test_dispatch_std_action` | AC-53, AC-55 | — | без винятків; 7 колонок; `views[0][1]=='gantt'` |
| `::TestTours` (`HttpCase`) | `test_dispatch_tour`, `test_kpp_tour`, `test_kpp_data_perf` | AC-54, AC-58 | тури `static/tests/tours/*.js` (у `web.assets_tests`) | тур успішний; час |
| `test_reports.py::TestReports` | `test_journal_access`, `test_command_action_domain`, `test_pivot_avg_wait`, `test_dock_report_example`, `test_dock_shift_param` | AC-59…AC-61 | — | значення `read_group`/SQL-виду |
| `test_provider.py::TestProvider` | `test_sections_and_coords`, `test_kiosk_and_rights`, `test_infra_cards`, `test_no_infra`, `test_notify_calls`, `test_bus_coalesced`, `test_registry_without_viewer`, `test_delta`, `test_delta_deep_merge_infra` | AC-62…AC-65, AC-87 | рейси в різних станах, `viewer_mock`; для AC-87 — `patch` з чужими ключами `infra` (код `td_viewer3d` у `addons_path`, імпорт хелпера без установки модуля) | dict payload; виклики `Mock`; чужі ключі `infra` збережено |
| `test_security.py::TestSecurity` | `test_menus_groups`, `test_implied_chain`, `test_acl_matrix`, `test_pii_fields`, `test_company_rule`, `test_neutralize_sql`, `test_no_secret_params`, `test_logs_without_pii` | AC-66…AC-69, AC-73, AC-74 | — | `env.ref`; `check_access`; `cr.execute(sql)`; `assertLogs` |
| `test_cron.py::TestCron` | `test_gc_pii`, `test_gc_lpr_images`, `test_gc_weighings`, `test_day_reset`, `test_no_show`, `test_queue_refresh` | AC-70, AC-71, AC-80 | дати через `write` під `sudo` | поля після кронових методів |
| `test_migration.py::TestMigration` | `test_params_env_test_prod`, `test_read_disabled_effects`, `test_synthetic_run_all`, `test_rerun_idempotent`, `test_clean_skipped`, `test_product_weights`, `test_seed_disabled`, `test_manual_flow_no_telemetry` | AC-72, AC-76, AC-77, AC-79 | пакети `TRUCK-T-1/2` з `td_code` | звіт; стани; ваги товарів |
| `test_contracts.py::TestContracts` | `test_telemetry_contract`, `test_base_contract`, `test_tags` | AC-78 | — | `inspect.signature`, `_fields`; теги всіх класів модуля |
| `services/.../tests/test_sics_parse.py` | `test_frames_table`, `test_units`, `test_errors`, `test_garbage` | AC-49 | — | `Frame`, показання |
| `services/.../tests/test_sics_plugin.py` | `test_poll_mode`, `test_stream_mode`, `test_stream_no_new`, `test_reset_device`, `test_reset_unsupported`, `test_poll_timeout`, `test_stream_drop_reconnect`, `test_health_states`, `test_allowlist`, `test_write_z_resumes_sir`, `test_write_t`, `test_write_tac_es`, `test_write_ta_not_supported`, `test_write_disabled`, `test_address_scale_offset`, `test_schemas` | AC-50…AC-52 | `fake_sics` (pytest-asyncio), `ctx` з `settings.write_enabled` | результати й винятки; `server.received` |

Запуск плагіна: `cd services/collector_plugins/f3d_collector_yard && pip install -e ../../collector -e .[test] &&
pytest -q` (без мережі, лише `127.0.0.1`).

### 13.2 Стендові сценарії ТК-01…ТК-08 (емулятор + колектор + Odoo; `docker compose --profile dev`)

Передумови (усі ТК): копія демо-бази з `td_factory3d`, `td_telemetry`, `td_yard` (за потреби
`td_viewer3d`); колектор `COL-MAIN` з токеном; `iot_sim` env: `SIM_LPR_PUSH_URL=http://collector:8080/f3d/lpr`,
`SIM_YARD_AUTOGATE=0`, токен маршруту `lpr` за Q-03 (заголовок `X-F3D-Token`) або `allow_ips: ["iot-sim"]` на
`HTTP-PUSH`; параметри: `td.yard.read_enabled=True`, `td.yard.antipassback=False` для ТК-01/03 (емулятор
може рухати фури без наших дозволів). Новий документ для ТК-01: приймання від «Плитсервіс (демо)» — `DSP16-SON` 120
+ `DSP16-WHT` 80 аркушів (маса 11 200 кг, як `WH/IN/00128`), пакет із воротами `DOCK-W2` і `scheduled_date` = зараз
+ 10 хв, підтверджений.

| ТК | Передумови | Кроки | Очікуваний результат | Де дивитися | AC |
|---|---|---|---|---|---|
| ТК-01 `truck_arrival` | `GATE-W`, `GATE-E` `mode='auto'`; `write_enabled` на модулі, `td.telemetry.write_enabled`, джерелі `MB-U86-IO7`, cmd-сигналах; `F3D_WRITE_ENABLED=1`; рейс створено кнопкою «Створити рейс», бронювання підтверджено | 1) `POST /sim/v1/scenario/truck_arrival/start {"params": {"booking": "<пакет>", "unload_min": 2}}` (iot_sim API-13, X-57); 2) після «Біля воріт» комірник проводить документ; 3) чекати виїзду | ≤ 10 с: подія CAM-05 `matched` (рейс без номера → емулятор генерує номер, збіг за описом заповнює номер рейсу; X-49), рейс `arrived → queued`, команда `auto_booking` `done`, `GATE-W` `open` ≤ 6 с; зважування `in` `auto` 25 200 ± 20 кг; «На ворота» (вручну або `auto_call_next`) → `at_dock` → `handling` (R-09) → `handling_end_at`; CAM-06 `matched` (виїзд); зважування `out` 14 000 ± 20 → `weighed`, нетто 11 200 ± 40, `weight_check='ok'`, документ «Двір»; команда `auto_exit`; петля GATE-E → `left` | Двір → Диспетчерська, Екран КПП, Журнали (LPR, Зважування, Команди), документ → вкладка «Двір», 3D | AC-81, AC-75 (картина даних) |
| ТК-02 POST LPR | колектор з `F3D_HTTP_PUSH_TOKEN_LPR` | `curl -s -X POST http://collector:8080/f3d/lpr -H 'Content-Type: application/json' -H "X-F3D-Token: $TOK" -d @lpr_new.json` (тіло iot_sim §8.13.2 з `carID=777`, `packetCounter=1`, номер `АА5555КТ`, `capture_timestamp` = зараз у мс, `plateList=""`, `plateListMode="none"`, `plateListDescription=""` — як у фури без броні, X-48); повтор того самого; без заголовка | 200 `{"received": true}`; ≤ 10 с — одна подія `unmatched` (повтор не дублює); без токена — 401 (колектор), подій немає; `POST /f3d/telemetry/event` з `route="lpr"` без токена колектора — 401 | Двір → Журнали → Розпізнавання номерів; Телеметрія → Події HTTP push | AC-82 |
| ТК-03 `truck_no_booking` | `mode='auto'`, команди дозволені | `POST /sim/v1/scenario/truck_no_booking/start {"params": {"plate": "АА1234КТ", "gate": "GATE-W", "wait_min": 3}}` (iot_sim API-13, X-57); на КПП — «Створити рейс» (або нічого) | картка «Без бронювання» жовта; `td.command` для GATE-W не створено; DI0 = 0 весь час (сигнал `yard/gates/GATE-W/state` = 0); з «Створити рейс» — рейс `arrived`, `is_walk_in`; без дії — після `lost` подія `expired` | Екран КПП; Телеметрія → Сигнали | AC-83 |
| ТК-04 команда DO0 | як ТК-01, `mode='manual'` | охоронець «Відкрити» на GATE-W; потім `F3D_WRITE_ENABLED=0`, перезапуск колектора, «Відкрити» ще раз | 1-ша: команда `done` ≤ 10 с, coil 00017 (PDU 16) = 1 і через 1,5 с знову 0 (`pulse_ms`, X-46; журнал u86 емулятора), DI0 = 1 ≤ 6 с, ворота `open`, `admitted_today` +1; 2-га: команда `expired` через 30 с, ворота `error` «Команду «Відкрити» не виконано» | форма воріт; Журнали → Команди | AC-84 |
| ТК-05 SICS | джерело `SICS-TRUCK-SCALE` `mode=stream` | запустити ТК-01 (етап ваг) або сценарій емулятора з фурою; паралельно `mode=poll` (змінити `params`) і повторити | сигнали `weight_kg`/`stable` оновлюються кожні ≤ 5 с; зважування `auto` одне на заїзд; у `poll` — те саме | Телеметрія → Сигнали; Двір → Зважування | AC-85 |
| ТК-06 пристрої офлайн | — | змінити порт `SICS-TRUCK-SCALE` на 4999 і `MB-U86-IO7` на 503; через 2 хв — ручний цикл рейсу: «Прибула», «Пропустити», «Зважити» з введенням 25 200 / 14 000, «Виїхала»; повернути порти | ваги `offline`, ворота `unknown`, кнопки команд неактивні з поясненням; ручний цикл проходить, нетто пораховано; після повернення портів — `idle`/`closed` ≤ 2 хв | Екран КПП; форма рейсу | AC-85, AC-79 |
| ТК-07 міграція | свіжа копія демо-бази | установка base → telemetry → yard; «Повторити міграцію двору» | звіт і 6 рейсів §5.4; повтор нічого не дублює; журнал без ERROR | Налаштування → Параметри системи (`td.yard.migration_report`); Двір → Рейси | AC-75, AC-76 |
| ТК-08 переглядач | `td_viewer3d` встановлено | відкрити «Завод 3D» (3D) і `GET /f3d/viewer/data` | `yard.trucks` — 6 фур у координатах макета; `meta.sections.yard = "live"`; картки `GATE-W`/`TRUCK-SCALE` з живими рядками; після «Пропустити» в ТК-01 — фура з'являється в черзі двору (delta) | 3D, вкладка «Логістика», картки | AC-86 |

### 13.3 Тести безпеки (ТБ)

| ID | Перевірка | Очікування | AC |
|---|---|---|---|
| ТБ-01 | Доступ без групи: `user_reader` — дії рейсу, команди, події LPR, майстри | `AccessError` на кожну | AC-21, AC-35, AC-59, AC-67 |
| ТБ-02 | Персональні дані: читання/експорт `driver_phone`, `driver_doc`, `td_driver_doc`, `last_plate` не-охороною | `AccessError`; експорт не пропонує полів | AC-68 |
| ТБ-03 | Стоп-крани: `write_enabled=False` (команд 0), `read_enabled=False` (події `ignored`, показання не змінюють двір), `neutralize.sql` | як в AC | AC-34, AC-72, AC-73 |
| ТБ-04 | Токени: у параметрах модуля немає секретів; маршрут `lpr` без токена — 401 (telemetry) | як в AC | AC-74, AC-82 |
| ТБ-05 | Ін'єкції в подію: `sensorProviderID="CAM-05'; DROP TABLE td_yard_visit;--"`, `plateText="<script>alert(1)</script>"`, `plateListDescription` з SQL, `plateText` як список/об'єкт, рядки 10 КБ | `unknown_camera`/`low_confidence`, без винятків SQL, значення обрізані до довжини полів, у формі й КПП показуються як текст (QWeb/OWL екранують) | AC-30 (+ окремий `test_lpr.py::TestInjection`) |
| ТБ-06 | Знімки: 1,5 МБ base64, не-зображення, `data:`-URI з SVG | відхилено, `note` | AC-26 |
| ТБ-07 | RPC з чужими id: `kpp_action('admit', visit_id=<рейс company_b>)` | `AccessError`/`MissingError` (record rule) | AC-69 |
| ТБ-08 | Журнали без PII при INFO; `sudo()` лише в місцях §4.4 (перегляд коду: `grep -n "sudo()" odoo_addons/td_yard -r` зіставити зі списком) | як описано | AC-74, DoD |

### 13.4 Тести продуктивності (ТП)

| ID | Обсяг | Вимір | Поріг |
|---|---|---|---|
| ТП-01 | 50 рейсів сьогодні, 20 подій LPR, 2 ворота | `kpp_data()` (середнє 5 викликів, тепла база) | ≤ 50 мс (CI-допуск ×4 — ≤ 200 мс) |
| ТП-02 | 40 фур на території | `_td_viewer_collect` | ≤ 30 мс; `json.dumps(payload['yard'])` ≤ 20 КБ |
| ТП-03 | пакет `_td_ingest` 1 000 показань без кодів двору | додаткові SQL-запити гачка M-13 | 0 (`assertQueryCount`) |
| ТП-04 | пакет 90 показань двору (5 с × 18 сигналів) | додаткові запити гачка | ≤ 15 |
| ТП-05 | 1 подія LPR без знімка | `_td_handle_push` | ≤ 100 мс |
| ТП-06 | 60 000 подій LPR старших 30 діб зі знімками 10 % | `_cron_gc` | ≤ 60 с, батчі по 1 000, без помилок пам'яті |
| ТП-07 | 15 000 рейсів (рік) | `search_read` V-05 pivot і SQL-вид M-15 за місяць | ≤ 1 с |

### 13.5 Чек-лист DEPLOY_TEST (`docs/modules/td_yard/DEPLOY_TEST.md`, здає W5)

1. Дамп бази тестового сервера (`pg_dump -Fc odoo > before_yard.dump`); копія `createdb -T`.
2. Модулі в `addons_path`; установка `-i td_yard` (base, telemetry уже стоять); журнал без `ERROR`/`Traceback`.
3. `td.yard.migration_state = done`; звіт = §5.4; 6 рейсів у диспетчерській (стан «Операція»).
4. `td.yard.read_enabled` = `True` (тест) / після `environment=prod` + нова установка — `False`.
5. Юніт-тести на копії: `--test-tags /td_yard` — зелені.
6. ТК-01…ТК-08 на стенді з емулятором — протокол із часом і скриншотами КПП.
7. `neutralize.sql` на копії → AC-73.
8. Деінсталяція на копії: параметри `td.yard.%` видалені; `td.signal`/`td.source` двору лишилися
   (`module='yard'`); пакети (`dock_id/scheduled_date/end_date`) і ваги товарів незмінні; повторна установка —
   міграція без дублікатів (`visits: 6` на чистій копії; повторно на тій самій — `visits: 0`, рейси видалені з модулем).
9. Відкат: `pg_restore` дампу п. 1; модуль прибрати з `addons_path`.

## 14. Definition of Done

- Усі AC-01…AC-88: UT/HT/CT — зелені в CI; TC — протокол ТК-01…ТК-08 з датою, стендом і результатом.
- `pylint-odoo` / `ruff` без помилок; XML валідний (`xmllint`); JS — `eslint` за конфігом Odoo; `prettier` для SCSS.
- Жодного `x_`-поля; рядки UI — українською; `README.md`, `CHANGELOG.md` (19.0.1.0.0), інструкції ARCH §4 перенесено
  в README.
- `neutralize.sql` перевірено (AC-73); стоп-крани описані в README; у параметрах немає секретів (AC-74).
- Перегляд безпеки: список `sudo()` збігається з §4.4; PII-поля з `groups`; ротація R-22 увімкнена кроном.
- Контракти з іншими модулями: `test_contracts` зелений; CY-01…CY-08 збігаються з полями цього SPEC.
- Плагін `sics`: `pytest` зелений, схеми §8.2 скопійовано в telemetry (`plugins/schemas/params.sics.json`,
  `address.sics.json` — побайтово однакові), рядок у `requirements-extra.txt` колектора.
- DEPLOY_TEST.md виконано на копії демо-бази; міграційний звіт додано до протоколу.

## 15. Відкриті питання, рішення автора, розбіжності

### 15.1 Відкриті питання (номери — як у ARCH §5.1; закриті рішеннями CONSISTENCY.md позначено X-xx)

| ID | Питання | Кому | Рекомендована відповідь | Що робимо тим часом (у коді) |
|---|---|---|---|---|
| Q-01 | Маршрут приймача LPR | автори telemetry, iot_sim | **закрито (X-53)**: колектор `POST /f3d/<route>[/<secret>]` → `/f3d/lpr` (telemetry SPEC §8.7, ARCH FR-22 вирівняно; = iot_sim Додаток A 658–659) | двір URL не знає; стенд — `SIM_LPR_PUSH_URL=http://collector:8080/f3d/lpr` |
| Q-02 | Номер фури для емулятора: iot_sim API-01 `bookings[].plate=null`, номер генерується, хоча картка макета `infra.py:368` прив'язує «АА 4512 КТ» до `WH/OUT/00413` (`TRUCK-OUT-1`) | автор iot_sim | **закрито (X-49)**: емулятор бере `stock.picking.batch.td_plate` (M-07), коли не `null`; інакше генерує і пише бронювання в `plateListDescription`; `АА4512КТ` — `TRUCK-OUT-1` | R-08 п. 7 (зіставлення за описом, заповнення номера); міграція ставить `АА4512КТ` лише `TRUCK-OUT-1` |
| Q-03 | **Закрито 14.10 (рішення менеджера):** `allow_ips` камер + секретний суфікс шляху (відповідь № 17е). Автентифікація маршруту `lpr` (емулятор шле без токена) | автори telemetry, iot_sim, адміністратор мережі | за telemetry Q-13: `allow_ips` камер + секретний суфікс шляху (`/f3d/lpr/<secret>`, `secret_ref`) — працює і з Axis, і з емулятором без зміни коду; `X-F3D-Token` — для вебхуків | стенд: `allow_ips: ["iot-sim"]`; ТК-02 перевіряє 401 без токена, якщо `token_ref` задано |
| Q-04 | Імпульс DO для CAME (≥ 1 с) | автор telemetry, монтажник | **закрито (X-46)**: `write.pulse_ms` у схемі `modbus_tcp` (telemetry A.1); `cmd_open`/`cmd_close` — `pulse_ms: 1500` (Додаток A); апаратний pulse-режим ADAM — додатково | — |
| Q-05 | **Закрито 14.10 (відповідь № 17, CONSISTENCY):** MT-SICS через шлюз до опису АКСІС; інший протокол — діалект `sics`. Протокол індикатора АКСІС ME-01 (RS-232), SICS-сумісність, шлюз | постачальник ваг | запросити опис; шлюз Moxa NPort/USR-TCP232; інший діалект — значення `params.dialect` | плагін лише `mt_sics` (§8.2) |
| Q-06 | **Закрито 14.10 (відповідь № 17, CONSISTENCY):** (а) лише диспетчер у v1; портал постачальника — v1.1. Хто бронює ворота для сторонніх фур | замовник | v1 — диспетчер; v1.1 — портал (`source='supplier'`, `requested`) | лише диспетчер |
| Q-07 | **Закрито 14.10 (відповідь № 17, CONSISTENCY):** після v1; рішення — в Odoo (R-08). Список дозволених номерів у камерах Axis (VAPIX) | замовник, інтегратор відео | після v1 | рішення лише в Odoo (R-08) |
| Q-08 | **Закрито 14.10 (рішення менеджера):** так — `yard.trucks[]` з `x/y/rz` → інстанс спільного меша `truck` (переглядач фази 2). Фури без коду сцени в 3D | автор viewer | спільний меш `truck` за `yard.trucks[].x/y/rz` | провайдер віддає координати (Додаток B) і `code` (якщо є) |
| Q-09 | **Закрито 14.10 (відповідь № 17, CONSISTENCY):** плити — за паспортом (iot_sim R-30), решта — з накладних постачальника. Маси товарів для звірки нетто (ДСП 18 мм — 63 кг ПРИПУЩЕННЯ) | замовник (технолог) | підтвердити маси аркушів/палет; інші — з накладних | плити — R-24 крок 3; решта — `no_reference` |
| Q-10 | **Закрито 14.10 (рішення менеджера):** апаратно контролером (DO4/DO5); Odoo лише показує `held`. Пожежа: «тримати відкритим» — контролер чи Odoo | менеджер, автор fire_safety | апаратно (без Odoo) | стан `held` лише за власною командою або свіжим coil DO4/DO5 (`cmd_hold` своїх воріт, R-16 п. 3) |
| Q-11 | **Закрито 14.10 (відповідь № 14, CONSISTENCY):** попередження (`enforce_calendar=False`). Друга зміна / графік КПП | замовник | попередження (`enforce_calendar=False`) | так |
| Q-12 | **Закрито 14.10 (відповідь № 17, CONSISTENCY):** ваги спільні, схему руху уточнити на ПНР. Розташування ваг для фур приймання | замовник | уточнити схему руху | стани не залежать від місця ваг; координата (172, −14) |
| Q-13 | **Закрито 14.10 (відповідь № 11, CONSISTENCY):** окремі DO4/DO5 (X-47). P-11 мав один DO4 «тримати відкритим» на обидва шлагбауми (iot_sim §8.13.1, coil 00021) — на проді окремі канали? | монтажник CAME, автор iot_sim | **рішення X-47**: окремі канали DO4 (PDU 20) → GATE-W, DO5 (PDU 21) → GATE-E (iot_sim §8.13.1 виправлено); лишається підтвердження монтажника (CONSISTENCY «Питання до замовника» № 11) | `cmd_hold` GATE-W → PDU 20, GATE-E → PDU 21 (Додаток A № 7, 14; AC-88); утримання одних воріт інші не зачіпає |
| Q-14 | telemetry R-18 / ACL: `td.command.create` лише для `group_td_manager`; чи пропускає перевірку групи при `env.su`? | автор telemetry | **закрито (X-04)**: так (як base R-04: `env.su` або група; решта запобіжників R-18 діють) | двір створює команди `sudo()` після власних перевірок R-15 (A-20); `test_contracts` перевіряє, що `sudo().create` охоронцем проходить |

### 15.2 Рішення автора SPEC (A-15…A-28; A-01…A-14 — ARCH §5.2)

| ID | Рішення | Чому |
|---|---|---|
| A-15 | Провайдер `td.viewer.provider.yard` — `AbstractModel` без `_inherit` (атрибути й методи контракту viewer M-01 реалізовані самостійно) | viewer R-01 п. 3 знаходить провайдери за префіксом імені; так `td_viewer3d` лишається необов'язковим без міст-модуля (у telemetry — A-20 міст) |
| A-16 | Провайдер оновлює рядки карток `infra.cards` `GATE-W`, `GATE-E`, `TRUCK-SCALE` (формат макета `infra.py:368–371`) | переглядач фази 1 уже показує ці картки; живі значення без зміни клієнта; статичні поля картки не чіпаються |
| A-17 | Гачок показань — перевизначення `td.signal._td_ingest` (CT-10), не `write()` (виправляє ARCH A-07) | telemetry R-17 п. 7 оновлює `last_value` сирим SQL; `write()` не викликається |
| A-18 | Події LPR — через джерело telemetry `HTTP-PUSH` (`source_http_push`, маршрут `lpr`); свого `http_push`-джерела двір не створює | джерело вже є в data telemetry (§5.2/API-01); два джерела на один маршрут конфліктували б у колекторі |
| A-19 | Джерела й сигнали двору створює хук (upsert за `code`) без `ir.model.data`; сигнали — з `data/td_yard_signals.csv` | сигнал з тим самим кодом може вже існувати (CT-11/рівень 0); деінсталяція двору не видаляє записи telemetry та їхні показання (ARCH §2.8) |
| A-20 | `td.command` створюється `sudo()` після перевірок R-15; `requested_by` — фактичний користувач або `base.user_root` для авто | охорона не в `group_td_manager` (telemetry ACL); журнал команд лишається правдивим |
| A-21 | `td.yard.gate.state` — збережене поле, перераховується гачком/кроном/діями | пошук і фільтри, kanban, шина при зміні; обчислення «на льоту» не дає подій зміни |
| A-22 | Нетто розподіляється між документами пакета пропорційно масам; для відвантажень пишеться й стандартний `shipping_weight` | один рейс — кілька документів; макет: «вага йде в документ відвантаження Odoo» (`site2.py:468`) |
| A-23 | Рейс без броні отримує бронювання (`source='walk_in'`) лише при виклику на ворота | Gantt показує фактичну зайнятість воріт; без воріт бронювання не має сенсу |
| A-24 | RPC екрана КПП — методи `td.yard.visit.kpp_data/kpp_action`, без окремої моделі | права й ACL уже визначені для рейсу; менше поверхні |
| A-25 | Авто-пропуск: вікно `[planned_start − early_min, planned_start + late_min]` (ARCH §2.5 п. 4 мав `planned_end + late_min` — виправлено на значення ARCH §3) і лише для подій не старших 60 с | параметр `late_min` описаний «після початку слоту»; стара подія з буфера не повинна відкривати шлагбаум |
| A-26 | Непризначене зважування має `kind='check'` до призначення; призначення визначає `in`/`out` | вид невідомий, доки не відомий рейс; `check` не впливає на нетто |
| A-27 | У `depends` додано `stock_delivery` (поле `stock.picking.carrier_id`) і `bus` (канал КПП) | перевірено в живій базі; ARCH §2.1 мав лише `delivery` |
| A-28 | `scene_code` рейсу = `related batch_id.td_code`; рейси без коду сцени мають лише координати (Додаток B) | код фури — власність base CB-06; координати для Q-08 |

### 15.3 Розбіжності з документами суміжних модулів (для менеджера)

Стан на 14.10.2026 — після CONSISTENCY.md v0.3 (X-01…X-80).

1. telemetry SPEC R-17 п. 7 (SQL-оновлення `last_value`) ↔ ARCH двору A-07 (`write()`) — виправлено в ARCH (A-17).
2. telemetry ARCH FR-22 `/f3d/push/<route>` ↔ telemetry SPEC §8.7 `/f3d/{route}` (Q-01) — вирішено X-53
   (`/f3d/<route>[/<secret>]`, правка в telemetry).
3. Схеми `sics`: telemetry A.1/A.2 розходились з §8.2 — вирішено X-45 (власник — двір, telemetry копіює) і X-70
   (`scale`/`offset` у `address.sics.json`).
4. telemetry R-18: створення команди — лише `group_td_manager` (Q-14, A-20) — вирішено X-04 (`env.su` пропускає групу).
5. iot_sim §8.4.1 («ADAM — старше слово першим») ↔ §8.4.2 — вирішено X-43 (молодше слово першим, `wordorder: "little"`).
6. iot_sim §8.13.1: один DO4 на обидва шлагбауми (Q-13) — вирішено X-47 (DO5 → GATE-E, PDU 21); каталог 654/656
   розділено, 10 сигналів двору — рядки каталогу 689–698 (X-34; адреси = Додаток A).
7. iot_sim §8.13.2 приклад: `capture_timestamp` ≠ `datetime` — вирішено X-48: R-07 п. 4 = telemetry R-22
   (`capture_timestamp`, поза вікном — час прийому), приклад iot_sim виправлено (AC-23 — X-73).
8. iot_sim `plateList="allow"` — вирішено X-48/X-73: `plateList` — назва списку (`f3d_bookings`), режим —
   `plateListMode` (поле `plate_list_mode`, M-04).
9. Axis `imageFile` — шлях на камері, не base64 (developer.axis.com) — ARCH A-14 виправлено (лише `imageArray`,
   `imagesURI`).
10. iot_sim §8.13.3 не перелічує `TAC` — плагін обробляє `ES` як `WriteError` (AC-52).
11. Номер `АА4512КТ`: iot_sim → `TRUCK-IN-1`, макет → `TRUCK-OUT-1` (Q-02) — вирішено X-49.

## Додаток A. Сигнали двору (`data/td_yard_signals.csv`, 18 рядків; CY-04)

Спільне: `module='yard'`, `viewer_visible=False`, `create_request=False`, `scale=1.0`, `decimals=0` (ваги — 0,
стабільність — 0), обладнання за кодом сцени (CB-01). Адреси Modbus — PDU 0-based (telemetry CT-03/R-20; unit 86 —
з `params` джерела). Колонка «Каталог» — рядок Додатка A iot_sim: 654–661 (8 «макетних») і 689–698 (10 сигналів, доданих
каталогом із цього додатка — X-34; адреси збігаються з iot_sim §8.13.1).

| № | `code` | `name` | `kind` | `unit` | Обладн. | Джерело | `address` | `period_s` / `store_period_s` | Запис / пороги | Власник.роль | Каталог |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `yard/gates/GATE-W/state` | GATE-W: стріла відкрита | gauge | — | GATE-W | MB-U86-IO7 | `{"fc":2,"addr":0,"type":"bool","doc":"DI0 00001 стріла відкрита"}` | 1 / 60 | — / `warn_high_on`, `warn_high=0.5`, `min_duration_s=600` (відкрито > 10 хв) | gate_w.state | 654 |
| 2 | `yard/gates/GATE-W/loop` | GATE-W: петля зайнята | gauge | — | GATE-W | MB-U86-IO7 | `{"fc":2,"addr":1,"type":"bool","doc":"DI1 00002 індукційна петля"}` | 1 / 60 | — | gate_w.loop | 689 |
| 3 | `yard/gates/GATE-W/photocell` | GATE-W: фотоелемент перекритий | gauge | — | GATE-W | MB-U86-IO7 | `{"fc":2,"addr":4,"type":"bool","doc":"DI4 00005 фотоелемент"}` | 1 / 60 | — | gate_w.photocell | 690 |
| 4 | `yard/gates/GATE-W/passes_today` | GATE-W: лічильник проїздів | counter | шт | GATE-W | MB-U86-IO7 | `{"fc":3,"addr":2,"count":2,"type":"u32","wordorder":"little","doc":"HR 40003–40004 лічильник DI1"}` | 10 / 300 | — | gate_w.passes | 655 |
| 5 | `yard/gates/GATE-W/cmd_open` | GATE-W: команда «відкрити» | gauge | — | GATE-W | MB-U86-IO7 | `{"fc":1,"addr":16,"type":"bool","write":{"fc":5,"addr":16,"pulse_ms":1500},"doc":"DO0 00017 відкрити (імпульс 1,5 с)"}` | 5 / 300 | `write_enabled=True` | gate_w.cmd_open | 691 |
| 6 | `yard/gates/GATE-W/cmd_close` | GATE-W: команда «закрити» | gauge | — | GATE-W | MB-U86-IO7 | `{"fc":1,"addr":18,"type":"bool","write":{"fc":5,"addr":18,"pulse_ms":1500},"doc":"DO2 00019 закрити примусово (імпульс 1,5 с)"}` | 5 / 300 | `write_enabled=True` | gate_w.cmd_close | 692 |
| 7 | `yard/gates/GATE-W/cmd_hold` | GATE-W: тримати відкритим | gauge | — | GATE-W | MB-U86-IO7 | `{"fc":1,"addr":20,"type":"bool","write":{"fc":5,"addr":20},"doc":"DO4 00021 тримати GATE-W (рівень)"}` | 5 / 300 | `write_enabled=True` | gate_w.cmd_hold | 693 |
| 8 | `yard/gates/GATE-E/state` | GATE-E: стріла відкрита | gauge | — | GATE-E | MB-U86-IO7 | `{"fc":2,"addr":2,"type":"bool","doc":"DI2 00003 стріла відкрита"}` | 1 / 60 | — / як № 1 | gate_e.state | 656 |
| 9 | `yard/gates/GATE-E/loop` | GATE-E: петля зайнята | gauge | — | GATE-E | MB-U86-IO7 | `{"fc":2,"addr":3,"type":"bool","doc":"DI3 00004 індукційна петля"}` | 1 / 60 | — | gate_e.loop | 694 |
| 10 | `yard/gates/GATE-E/photocell` | GATE-E: фотоелемент перекритий | gauge | — | GATE-E | MB-U86-IO7 | `{"fc":2,"addr":5,"type":"bool","doc":"DI5 00006 фотоелемент"}` | 1 / 60 | — | gate_e.photocell | 695 |
| 11 | `yard/gates/GATE-E/passes_today` | GATE-E: лічильник проїздів | counter | шт | GATE-E | MB-U86-IO7 | `{"fc":3,"addr":6,"count":2,"type":"u32","wordorder":"little","doc":"HR 40007–40008 лічильник DI3"}` | 10 / 300 | — | gate_e.passes | 657 |
| 12 | `yard/gates/GATE-E/cmd_open` | GATE-E: команда «відкрити» | gauge | — | GATE-E | MB-U86-IO7 | `{"fc":1,"addr":17,"type":"bool","write":{"fc":5,"addr":17,"pulse_ms":1500},"doc":"DO1 00018 відкрити (імпульс 1,5 с)"}` | 5 / 300 | `write_enabled=True` | gate_e.cmd_open | 696 |
| 13 | `yard/gates/GATE-E/cmd_close` | GATE-E: команда «закрити» | gauge | — | GATE-E | MB-U86-IO7 | `{"fc":1,"addr":19,"type":"bool","write":{"fc":5,"addr":19,"pulse_ms":1500},"doc":"DO3 00020 закрити примусово (імпульс 1,5 с)"}` | 5 / 300 | `write_enabled=True` | gate_e.cmd_close | 697 |
| 14 | `yard/gates/GATE-E/cmd_hold` | GATE-E: тримати відкритим | gauge | — | GATE-E | MB-U86-IO7 | `{"fc":1,"addr":21,"type":"bool","write":{"fc":5,"addr":21},"doc":"DO5 00022 тримати GATE-E (рівень)"}` | 5 / 300 | `write_enabled=True` | gate_e.cmd_hold | 698 |
| 15 | `yard/lpr/CAM-05/plate` | CAM-05: номер на в'їзді | event | — | CCTV | HTTP-PUSH (telemetry) | `{"route":"lpr","match":{"sensorProviderID":"CAM-05"},"path":"$.plateText","ts_path":"$.capture_timestamp"}` | 3600 / 0 | — | — | 658 |
| 16 | `yard/lpr/CAM-06/plate` | CAM-06: номер на виїзді | event | — | CCTV | HTTP-PUSH (telemetry) | `{"route":"lpr","match":{"sensorProviderID":"CAM-06"},"path":"$.plateText","ts_path":"$.capture_timestamp"}` | 3600 / 0 | — | — | 659 |
| 17 | `yard/scale/TRUCK-SCALE/weight_kg` | Автоваги: вага | gauge | кг | TRUCK-SCALE | SICS-TRUCK-SCALE | `{"cmd":"SI","field":"weight","doc":"SICS SI/SIR, дискретність 20 кг"}` | 1 / 60 | — | scale_truck.weight | 660 |
| 18 | `yard/scale/TRUCK-SCALE/stable` | Автоваги: стабільно | gauge | — | TRUCK-SCALE | SICS-TRUCK-SCALE | `{"cmd":"SI","field":"stable","doc":"SICS статус S/D"}` | 1 / 60 | — | scale_truck.stable | 661 |

Значення DI/DO — 0/1 (`gauge` без одиниці): у Odoo `last_value ≥ 0.5` = «так» (з урахуванням `invert_di` воріт).
Команди «відкрити»/«закрити» (№ 5, 6, 12, 13) — імпульс для CAME (≥ 1 с): `write.pulse_ms = 1500` (схема `modbus_tcp`
telemetry A.1, 100…10 000): плагін пише 1, через `pulse_ms` — 0 (X-46). «Тримати відкритим» (№ 7, 14) — рівень без
`pulse_ms`: `hold` пише 1, `release` — 0 (імпульс зняв би утримання через 1,5 с). Канали утримання окремі: DO4
(coil 00021, PDU 20) → GATE-W, DO5 (coil 00022, PDU 21) → GATE-E (X-47; підтвердження монтажника — Q-13).
CSV-рядок (приклад №1): `yard/gates/GATE-W/state,GATE-W: стріла відкрита,gauge,,GATE-W,MB-U86-IO7,"{""fc"":2,""addr"":0,
""type"":""bool"",""doc"":""DI0 00001 стріла відкрита""}",1,60,0,0.5,600,0,0,gate_w,state` (колонки §5.3; `warn_high`
порожній = порогу немає).

## Додаток B. Координати фур у 3D (R-20; система CB-04, метри, `rz` — градуси в плані)

Джерела: `plant/site.py:1425–1430` (фури біля воріт: захід `x = −7.3`, `rz = 0`; схід `x = W + 7.3 = 157.3`,
`rz = 180`; напівпричіп 13,6 м), `plant/layout.py:DOOR_Y` (5…65), `plant/infra.py` (`GATES`, `TRUCK_SCALE`), base
Додаток C.2 (зони).

| Стан рейсу / умова | Позиція | Приклад | Зона (`zone_at`) |
|---|---|---|---|
| `at_dock`, `handling` (захід) | `(dock.td_x − 7.3, dock.td_y, 0)` | `DOCK-W1 (0, 5)` → `(−7.3, 5.0, 0)` | `Z-YARD-W` |
| `at_dock`, `handling` (схід) | `(dock.td_x + 7.3, dock.td_y, 180)` | `DOCK-E2 (150, 15)` → `(157.3, 15.0, 180)` | `Z-YARD-E` |
| `arrived` — k-та за `arrived_at` на воротах в'їзду (`gate_in_id` або ворота `in` сторони) | `(gate.pos_x + [0, −3.5, +3.5][k], gate.pos_y + 8.0, 90)`, `k ≤ 2`; далі `x = y = null` | GATE-W `(−20, −30)`, k = 0 → `(−20.0, −22.0, 90)` | `Z-GATE-W` |
| `queued`, остання вага `in` не старша `scale_dwell_s` | `(scale.pos_x, scale.pos_y, 90)` | `(172.0, −14.0, 90)` | `Z-GATE-E` |
| `queued` — k-та в черзі сторони (R-05 п. 3) | захід `(−26.0, 9.0 + 16·k, 90)`, схід `(176.0, 9.0 + 16·k, 90)`, `k ≤ 3`; далі `null` | k = 1 захід → `(−26.0, 25.0, 90)` | `Z-YARD-W` / `Z-YARD-E` |
| `weighed`, `weighed_out_at` не старше `scale_dwell_s` | на вагах `(172.0, −14.0, 90)` | — | `Z-GATE-E` |
| `weighed`, пізніше | біля воріт виїзду `(gate_out.pos_x, gate_out.pos_y + 8.0, 270)` | GATE-E → `(168.0, −22.0, 270)` | `Z-GATE-E` |
| `draft`, `planned`, `left`, `rejected`, `cancelled` | у `trucks` не потрапляють | — | — |

## Додаток C. Розділ `yard` payload переглядача (CY-06, `meta.schema` viewer «1.1» за каркасом §6.7 + новий ключ верхнього рівня)

```json
{"yard": {
  "updated": "2026-10-12 10:30",
  "gates": {"GATE-W": {"name": "КПП приймання (в'їзд)", "state": "closed", "mode": "manual", "error": null,
                       "passes_today": 7, "admitted_today": 7, "tailgate_today": 0,
                       "last_plate": "АА4512КТ", "last_plate_at": "2026-10-12 09:10", "x": -20.0, "y": -30.0}},
  "scale": {"TRUCK-SCALE": {"weight_kg": 0.0, "stable": true, "state": "idle", "today": 1,
                            "last": {"plate": "АА 4512 КТ", "weight_kg": 21380.0, "kind": "check", "picking": "WH/OUT/00413",
                                     "ts": "2026-10-12 12:00"}, "x": 172.0, "y": -14.0}},
  "trucks": [{"visit": "YV/2026/00001", "code": "TRUCK-IN-1", "plate": null, "state": "handling", "type": "incoming",
              "dock": "DOCK-W1", "picking": "WH/IN/00128", "partner": "Плитсервіс (демо)", "carrier": "Плитсервіс (демо)",
              "walk_in": false, "progress": 0.6, "since": "2026-10-12 09:30", "weight_check": "none",
              "x": -7.3, "y": 5.0, "rz": 0, "zone": "Z-YARD-W"}],
  "queue": {"west": [], "east": []},
  "kpp": {"west": [], "east": []},
  "stats": {"planned_today": 6, "arrived_today": 6, "on_site": 6, "at_dock": 6, "left_today": 0, "walk_in_today": 0,
            "unmatched": 0, "avg_wait_min": 20.0, "weighings_today": 1}}}
```

| Ключ | Тип | req | Опис |
|---|---|---|---|
| `updated` | str `YYYY-MM-DD HH:MM` (Київ) | req | `ctx.now_local` |
| `gates[code]` | dict | req (може `{}`) | `name` str, `state` ∈ {`closed`,`open`,`held`,`error`,`unknown`}, `mode` ∈ {`auto`,`manual`}, `error` str/null, `passes_today`, `admitted_today`, `tailgate_today` int, `last_plate` str/null (R-20 п. 1), `last_plate_at` str/null, `x`, `y` float |
| `scale[code]` | dict | req (може `{}`) | `weight_kg` float/null, `stable` bool, `state` ∈ {`idle`,`settling`,`captured`,`offline`}, `today` int, `last` dict/null (`plate` str/null, `weight_kg` float, `kind` ∈ {`in`,`out`,`check`}, `picking` str/null, `ts` str), `x`, `y` |
| `trucks[]` | list[dict] | req | `visit` str, `code` str/null (CB-06), `plate` str/null, `state` (стани `ACTIVE_STATES`), `type` ∈ {`incoming`,`outgoing`,`other`}, `dock` str/null, `picking` str/null (перший документ), `partner`, `carrier` str/null, `walk_in` bool, `progress` float 0…1, `since` str (час входу в поточний стан), `weight_check` str, `x`, `y`, `rz` float/null, `zone` str/null |
| `queue.west/east` | list[str] | req | назви рейсів `queued` у порядку R-05 |
| `kpp.west/east` | list[str] | req | назви рейсів `arrived` за `arrived_at` |
| `stats` | dict | req | R-20 п. 5 |

Порядок ключів верхнього рівня payload: `yard` додається після ключів viewer A.0 (провайдер 160 — після `infra` 150);
`pickings[].dock/truck` і `docks` не змінюються (A-13). Розмір розділу для 40 фур ≤ 20 КБ (ТП-02).
