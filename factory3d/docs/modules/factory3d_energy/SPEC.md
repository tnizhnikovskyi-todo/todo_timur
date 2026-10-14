# factory3d_energy — специфікація

Версія 0.1 · 14.10.2026 · технічне рішення: `docs/modules/factory3d_energy/ARCHITECTURE.md` (далі ARCH: FR-01…FR-29,
CE-01…CE-09, A-01…A-22, Q-01…Q-20). Спирається на: каркас §5, §6.4–§6.8, D-04, D-06, D-11; `factory3d_base` CB-01,
CB-07…CB-10; `factory3d_telemetry` CT-01 (M-01…M-06), CT-03 (Додаток A.1 `modbus_tcp`), CT-05 (R-04…R-06), CT-10
(`_f3d_ingest`, R-17), CT-12 (R-26 локальні джерела), R-03 (зберігання), R-07 (stale), R-13 (шина); `factory3d_iot_sim`
§8.4.1, §8.7 (P-05), §8.9.1–§8.9.5 (P-07), Додаток A № 1–80, 190–196, 366–428, S-01, S-03, S-12, API-16;
`factory3d_viewer` M-01, M-03, R-01, R-07, R-14, A.5, A.12, A.13; `factory3d_machine_connect` CM-02, CM-03 (R-28);
`td_genset`/`factory3d_genset` R-04…R-06, AC-23, AC-30, AC-56, ТК-G04.

Позначення: UT — юніт-тест `odoo.tests` (`TransactionCase`), TC — стенд (емулятор + колектор + Odoo), MAN — ручна
перевірка на копії демо-бази. Odoo 19: `models.Constraint`, `post_init_hook(env)`/`uninstall_hook(env)`, `fields.Json`,
`Command`. Усі `Datetime` — UTC naive; «Київ» — `Europe/Kyiv` через `zoneinfo`. Рядки UI — українською в коді (D-14).
`req` = `required=True`; `idx` = `index=True`; `cost` у колонці «Параметри» = `groups="factory3d_energy.group_energy_cost"`.

## 0. Дерево файлів модуля

```
odoo_addons/factory3d_energy/
├── __init__.py                      from . import models, wizard, tools; from .hooks import post_init_hook, uninstall_hook
├── __manifest__.py                  §1
├── hooks.py                         post_init_hook(env), uninstall_hook(env), run_bind(env) — §5.3–§5.4
├── README.md                        установка, параметри, інструкції ARCH §4
├── CHANGELOG.md                     19.0.1.0.0 — перший випуск
├── models/
│   ├── __init__.py                  порядок: f3d_source, f3d_signal, f3d_energy_tariff, f3d_energy_node, f3d_energy_pool,
│   │                                f3d_energy_meter, f3d_energy_interval, f3d_energy_balance, f3d_energy_event,
│   │                                f3d_energy_outage, f3d_energy_alloc, mrp_workorder, mrp_production, mrp_workcenter,
│   │                                maintenance_equipment, maintenance_request, res_config_settings, viewer_provider
│   ├── f3d_energy_node.py           M-01
│   ├── f3d_energy_meter.py          M-02 (+ _f3d_kwh CE-06)
│   ├── f3d_energy_interval.py       M-03 (+ _cron_build R-04)
│   ├── f3d_energy_tariff.py         M-04, M-05 (R-05)
│   ├── f3d_energy_pool.py           M-06
│   ├── f3d_energy_alloc.py          M-07 (+ _cron_alloc R-08, R-09; _prepare_analytic_line_values A-11)
│   ├── f3d_energy_balance.py        M-08 (+ _cron_balance R-07)
│   ├── f3d_energy_event.py          M-09
│   ├── f3d_energy_outage.py         M-10 (R-14)
│   ├── mrp_workorder.py             M-11
│   ├── mrp_production.py           M-12 (_cal_price, _get_backorder_mo_vals — R-10)
│   ├── mrp_workcenter.py            M-13
│   ├── maintenance_equipment.py     M-14
│   ├── f3d_signal.py                M-15 (_f3d_ingest, origin += module, обмеження A-15)
│   ├── f3d_source.py                M-16 (type += f3d_energy, _f3d_local_types)
│   ├── maintenance_request.py       M-17
│   ├── res_config_settings.py       M-18
│   └── viewer_provider.py           M-20 (AbstractModel без _inherit, A-04)
├── wizard/
│   ├── __init__.py
│   ├── recompute_wizard.py          M-19
│   └── recompute_wizard_views.xml   V-19
├── tools/
│   ├── __init__.py
│   ├── counter.py                   CounterSeries: безперервний лічильник Ec(t) — R-03 (чисті функції)
│   ├── tariff.py                    zone_for(local_dt, zones) — R-05 (чисті функції)
│   ├── live.py                      section_values(...), site_totals(...) — R-06 (чисті функції)
│   ├── balance.py                   check(measured, expected, tol_pct, tol_kwh) — R-07
│   ├── alloc.py                     allocate_day(...) — R-08, R-09 (чисті функції, без ORM)
│   ├── ats.py                       ats_state(...), island(...) — R-14
│   ├── payload.py                   build_energy(env, ctx), build_infra(env, ctx, payload) — R-16, R-17
│   ├── dates.py                     to_local, day_bounds_utc, slot_floor, slots(day) — R-20
│   └── gen_energy_data.py           генератор data/energy_*.csv з макета й каталогу iot_sim (Odoo не вантажить)
├── security/
│   ├── f3d_energy_security.xml      групи, implied, record rules §4.2–§4.3
│   └── ir.model.access.csv          §4.1
├── data/
│   ├── ir_config_parameter.xml      §5.1 (noupdate="1")
│   ├── ir_cron.xml                  §6
│   ├── f3d_energy_tariff_data.xml   тариф демо (noupdate="1"), §5.2
│   ├── f3d_energy_actions.xml       ir.actions.server «Повторити прив'язку даних енергетики»
│   ├── energy_nodes.csv             123 рядки — Додаток B (читає хук, не в `data` маніфесту)
│   ├── energy_sources.csv           68 рядків — Додаток D.2
│   ├── energy_signals.csv           297 рядків — Додаток C
│   ├── energy_meters.csv            67 рядків — Додаток D.1
│   ├── energy_pools.csv             5 рядків — Додаток D.3
│   └── neutralize.sql               §5.6
├── views/
│   ├── menus.xml                    V-21
│   ├── f3d_energy_node_views.xml    V-01…V-04
│   ├── f3d_energy_meter_views.xml   V-05, V-06
│   ├── f3d_energy_interval_views.xml V-07, V-08
│   ├── f3d_energy_tariff_views.xml  V-09
│   ├── f3d_energy_pool_views.xml    V-10
│   ├── f3d_energy_alloc_views.xml   V-11
│   ├── f3d_energy_balance_views.xml V-12
│   ├── f3d_energy_event_views.xml   V-13
│   ├── f3d_energy_outage_views.xml  V-14
│   ├── mrp_production_views.xml     V-15
│   ├── mrp_workorder_views.xml      V-16
│   ├── mrp_workcenter_views.xml     V-17 (+ статбокс обладнання)
│   ├── res_config_settings_views.xml V-18
│   └── dashboard_views.xml          V-20 («Огляд»)
├── static/description/icon.png      іконка (блискавка над заводом, 140×140)
└── tests/
    ├── __init__.py
    ├── common.py                    F3DEnergyCase(TransactionCase): фікстури §13.0
    ├── test_node.py                 AC-01…AC-06
    ├── test_tariff.py               AC-07…AC-11
    ├── test_hooks.py                AC-12…AC-14, AC-70…AC-74
    ├── test_counter.py              AC-15…AC-20, AC-87
    ├── test_interval.py             AC-21…AC-25, AC-83, AC-84
    ├── test_live.py                 AC-26…AC-29, AC-86
    ├── test_balance.py              AC-30…AC-32
    ├── test_events.py               AC-33…AC-36
    ├── test_alloc.py                AC-37…AC-45, AC-85
    ├── test_costing.py              AC-46…AC-51
    ├── test_mo231.py                AC-52…AC-54
    ├── test_ats.py                  AC-55…AC-62
    ├── test_payload.py              AC-63…AC-69
    ├── test_security.py             AC-75…AC-82
    ├── test_data_sync.py            CSV ↔ макет (pytest поза Odoo)
    └── stand/                       ТК-01…ТК-12 (pytest -m stand)
```

## 1. Маніфест

```python
{
    "name": "Завод 3D: енергетика",
    "summary": "Схема електропостачання, лічильники PM5560, 15-хв профіль, баланс, кВт·год і вартість на завдання й МО, "
               "СЕС, накопичувач, КГУ, АВР, тарифи, ліміт потужності",
    "description": "Ієрархія ввід → трансформатор → ГРЩ → шинопровід → споживач; лічильники поверх factory3d_telemetry; "
                   "розподіл енергії на робочі завдання й собівартість МО; відключення мережі й АВР; провайдери 3D.",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["factory3d_telemetry", "mrp_account", "mrp_workorder", "analytic", "web_hierarchy"],
    "data": [
        "security/f3d_energy_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/ir_cron.xml",
        "data/f3d_energy_tariff_data.xml",
        "data/f3d_energy_actions.xml",
        "wizard/recompute_wizard_views.xml",
        "views/f3d_energy_node_views.xml",
        "views/f3d_energy_meter_views.xml",
        "views/f3d_energy_interval_views.xml",
        "views/f3d_energy_tariff_views.xml",
        "views/f3d_energy_pool_views.xml",
        "views/f3d_energy_alloc_views.xml",
        "views/f3d_energy_balance_views.xml",
        "views/f3d_energy_event_views.xml",
        "views/f3d_energy_outage_views.xml",
        "views/mrp_production_views.xml",
        "views/mrp_workorder_views.xml",
        "views/mrp_workcenter_views.xml",
        "views/res_config_settings_views.xml",
        "views/dashboard_views.xml",
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

Порядок `data`: групи → доступи → параметри → крони → тариф → дії → майстер → представлення → меню.
`energy_*.csv` у `data` не перелічені — їх читає хук через `odoo.tools.file_open` (як `scene_*.csv` у base). Зовнішніх
Python-залежностей немає (`zoneinfo` — стандартна бібліотека 3.12). `factory3d_viewer`, `factory3d_machine_connect`,
`factory3d_genset` — **не** в `depends` (A-04, A-05).

## 2. Моделі

### M-01 `f3d.energy.node` — вузол мережі (CE-05, FR-01)

```python
class F3dEnergyNode(models.Model):
    _name = "f3d.energy.node"
    _description = "Енергетика: вузол мережі"
    _inherit = ["mail.thread"]
    _parent_name = "parent_id"
    _parent_store = True
    _order = "sequence, code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,31}$")
    KINDS = [("input", "Ввід мережі"), ("substation", "РУ 10 кВ"), ("transformer", "Трансформатор"),
             ("switchboard", "ГРЩ"), ("section", "Секція шин"), ("cell", "Шафа ГРЩ"), ("line", "Лінія"),
             ("tapoff", "Відгалуження"), ("consumer", "Споживач"), ("generator", "Генерація"),
             ("storage", "Накопичувач"), ("ats", "АВР")]
```

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(32) | `req`, `idx`, `string="Код"`, `copy=False`, `tracking=True`; `CODE_RE` (= код сцени, де є: `SAW-1`, `QF-3`; синтетичні: `GRID-10KV`, `SEC-1`, `TAP-SAW-1`) |
| `name` | Char(128) | `req`, `string="Назва"` |
| `sequence` | Integer | `default=10` (шафи ГРЩ — 10…110 зліва направо, `SWB_CELLS` макета) |
| `active` | Boolean | `default=True` |
| `kind` | Selection `KINDS` | `req`, `idx`, `string="Вид"`, `tracking=True` |
| `cell_type` | Selection | `[('incomer','Ввідна'),('feeder','Фідер шинопроводу'),('cable','Кабельні фідери'),('coupler','Секційний вимикач'),('pfc','Компенсація')]`, `string="Тип шафи"` |
| `line_kind` | Selection | `[('busway','Шинопровід'),('cable','Кабелі')]`, `string="Тип лінії"` |
| `gen_kind` | Selection | `[('pv_inverters','СЕС: група інверторів'),('pv_inverter','Інвертор СЕС'),('pv_field','Поле модулів СЕС'),('chp','Когенерація'),('genset','Дизель-генератор')]`, `string="Тип генерації"` |
| `parent_id` | Many2one `f3d.energy.node` | `string="Живиться від"`, `ondelete="restrict"`, `idx` (A-16) |
| `parent_path` | Char | `idx` (стандарт `_parent_store`) |
| `child_ids` | One2many `f3d.energy.node` `parent_id` | `string="Живить"` |
| `cabinet_id` | Many2one `f3d.energy.node` | `string="Шафа (збірка)"`, `domain="[('kind','=','switchboard')]"`, `ondelete="set null"` (11 шаф → `SWB-1`) |
| `peer_id` | Many2one `f3d.energy.node` | `string="З'єднує з"`, `ondelete="set null"` (лише `QS` → `SEC-2`) |
| `section` | Integer | `string="Секція шин"`, `default=0` (0 — поза секціями; 1/2); для `cell`/`line`/`tapoff`/`consumer`/генерації — секція предка (заповнює хук) |
| `equipment_id` | Many2one `maintenance.equipment` | `string="Обладнання"`, `ondelete="set null"`, `idx` |
| `equipment_code` | Char | `related="equipment_id.f3d_code"` |
| `workcenter_id` | Many2one `mrp.workcenter` | `string="Робочий центр"`, `ondelete="set null"`, `idx` |
| `zone_id` | Many2one `f3d.zone` | `related="equipment_id.f3d_zone_id"`, `string="Зона"` |
| `rating_a` | Integer | `string="Номінал, А"` (шафи, лінії) |
| `rating_kva` | Integer | `string="Номінал, кВА"` (T1/T2 — 1000) |
| `rating_kvar` | Integer | `string="Номінал, квар"` (PFC — 350) |
| `voltage_kv` | Float | `digits=(5,2)`, `default=0.4`, `string="Напруга, кВ"` (ввід, RM6-1 — 10) |
| `p_inst_kw` | Float | `digits=(10,2)`, `string="Встановлена, кВт"` (споживачі — `consumers()[code].p_inst` макета) |
| `p_inst_source` | Selection | `[('passport','Паспорт'),('estimate','Оцінка'),('mixed','Паспорт + оцінка')]`, `string="Джерело потужності"` |
| `load_factor` | Float | `digits=(6,3)`, `string="Коефіцієнт завантаження в роботі"` (`PROFILE[type][0]` для РЦ; для решти — `p_now/p_inst` макета) |
| `idle_factor` | Float | `digits=(6,3)`, `string="Коефіцієнт простою"` (`IDLE_K` або `IDLE_DEFAULT=0.12` для РЦ) |
| `cos_phi_nominal` | Float | `digits=(4,2)`, `default=0.9`, `string="cos φ (номінал)"` |
| `is_critical` | Boolean | `string="Критичний (живлення від ДГУ)"`, `tracking=True` (CE-04) |
| `alloc_role` | Selection | `[('direct','Прямий (верстат)'),('shared','Спільний (пул)'),('overhead','Накладні'),('none','Не розподіляється')]`, `default='none'`, `req`, `string="Роль у розподілі"` |
| `pool_id` | Many2one `f3d.energy.pool` | `string="Пул"`, `ondelete="set null"` |
| `meter_ids` | One2many `f3d.energy.meter` `node_id` | `string="Лічильники"` |
| `meter_id` | Many2one `f3d.energy.meter` | `compute="_compute_meter_id"` (не зберігається): перший активний лічильник за `code` |
| `unit_id` | Integer | `string="Modbus unit (стенд)"` (довідково: iot_sim §8.4.1) |
| `note` | Text | `string="Примітка"` (`note` споживача з макета) |
| `group` | Selection | `[('light','Освітлення'),('vent','Вентиляція')]`, `string="Група"` (з макета `group`) |
| `company_id` | Many2one `res.company` | `req`, `default=lambda self: self.env.company`, `idx` |
| `p_now` | Float | `compute="_compute_live"` (не зберігається), `string="Зараз, кВт"`: `meter_id.p_signal_id.last_value` або 0 |
| `kwh_today` | Float | `compute="_compute_live"`, `string="Сьогодні, кВт·год"`: Σ `f3d.energy.interval.kwh` лічильника за сьогодні (Київ) |
| `pfc_q_now` | Integer | `readonly=True`, `string="Компенсація зараз, квар"` — лише шафи `pfc`, пише крон R-06 п. 2 |
| `live_status` | Selection | `compute="_compute_live"`: `meter_id.data_state` або `'none'` (`[('ok','Норма'),('stale','Немає даних'),('gap','Пропуск'),('reset','Скидання'),('no_data','Ще не було даних'),('none','Без лічильника')]`) |

```python
    _f3d_energy_node_code_uniq = models.Constraint("UNIQUE(code)", "Код вузла мережі має бути унікальним.")
    _f3d_energy_node_wc_uniq = models.Constraint("UNIQUE(workcenter_id)", "Робочий центр уже прив'язаний до іншого вузла.")
```

`@api.constrains` `_check_node`:
1. `code` не відповідає `CODE_RE` → `ValidationError("Код вузла %s: великі латинські літери, цифри, дефіс (напр. QF-3, TAP-SAW-1).")`;
2. `self._has_cycle()` → `"Вузол %s не може живитися сам від себе (цикл у схемі)."`;
3. `kind == 'cell'` без `cell_type` → `"Для шафи ГРЩ задайте тип шафи."`; `kind == 'line'` без `line_kind` → `"Для лінії задайте тип."`;
4. `kind in ('consumer','cell','line','tapoff','section','transformer','substation')` без `parent_id` → `"Вузол %s має живитися від іншого вузла."` (`input`, `switchboard` — корені; `ats` і генерація — з батьком за даними);
5. `alloc_role == 'direct'` без `workcenter_id` або `kind != 'consumer'` → `"Прямий споживач має бути вузлом-споживачем з робочим центром."`;
6. `alloc_role == 'shared'` без `pool_id` → `"Спільний споживач має належати пулу."`; `pool_id` при ролі ≠ `shared` → `"Пул задається лише спільним споживачам."`;
7. `workcenter_id` при `kind != 'consumer'` → `"Робочий центр прив'язується лише до споживача."`;
8. `section not in (0, 1, 2)` → `"Секція шин: 0, 1 або 2."`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `_compute_meter_id(self)` | `self.meter_id = self.meter_ids.filtered('active').sorted('code')[:1]` |
| `_compute_live(self)` | один `search_read` сигналів `meter_ids.p_signal_id`; один `read_group` `f3d.energy.interval` (`meter_id in`, `ts_start >= day_bounds_utc(today)[0]`) з `sum(kwh)` за `meter_id` |
| `@api.model _f3d_kwh_by_code(self, code, date_from, date_to) -> tuple[float, str]` | CE-06: `node = search([('code','=',code)], limit=1)`; немає або без лічильника → `(0.0, 'missing')`; інакше `node.meter_id._f3d_kwh(date_from, date_to)` |
| `_f3d_descendant_meters(self) -> f3d.energy.meter` | лічильники вузлів `child_of self` (без самого `self`), активні |
| `action_view_meters(self)` / `action_view_intervals(self)` / `action_view_balance(self)` | `act_window` на M-02 / M-03 (`domain=[('node_id','child_of',id)]`, графік за сьогодні) / M-08 |
| `action_f3d_show(self)` | `equipment_id.action_f3d_show()`, якщо є; інакше `UserError("Вузол %s не має об'єкта в 3D.")` |
| `_compute_display_name(self)` | `"%s · %s" % (code, name)` |

### M-02 `f3d.energy.meter` — лічильник (CE-05, CE-06, FR-02, FR-27)

```python
class F3dEnergyMeter(models.Model):
    _name = "f3d.energy.meter"
    _description = "Енергетика: лічильник"
    _inherit = ["mail.thread"]
    _order = "node_id, code"
    _rec_name = "code"
    _rec_names_search = ["code", "name"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(32) | `req`, `idx`, `copy=False`, `string="Код"` (`PM-Q1`, `PM-SAW-1`, `SUN-1`…`SUN-8`, `LUNA-1`, `TEDOM-1`); regex `CODE_RE` M-01 |
| `name` | Char(128) | `string="Назва"` |
| `active` | Boolean | `default=True` |
| `node_id` | Many2one `f3d.energy.node` | `req`, `ondelete="restrict"`, `idx`, `string="Вузол"` |
| `model` | Selection | `[('pm5560','Schneider PowerLogic PM5560'),('sun2000','Huawei SUN2000'),('luna2000','Huawei LUNA2000'),('tedom','TEDOM ProCon'),('other','Інший')]`, `req`, `default='pm5560'` |
| `role` | Selection | `[('incomer','Ввід'),('feeder','Фідер'),('consumer','Споживач'),('generation','Генерація'),('storage','Накопичувач')]`, `req`, `string="Роль"` |
| `source_id` | Many2one `f3d.source` | `string="Джерело"`, `ondelete="set null"` |
| `p_signal_id` | Many2one `f3d.signal` | `string="Сигнал потужності, кВт"`, `ondelete="set null"` |
| `e_import_signal_id` | Many2one `f3d.signal` | `string="Лічильник енергії (споживання / вироблення), кВт·год"`, `domain="[('kind','=','counter')]"`, `ondelete="set null"` |
| `e_export_signal_id` | Many2one `f3d.signal` | `string="Лічильник енергії (віддача), кВт·год"`, `domain` те саме, `ondelete="set null"` (Q1/Q2 — 3208; LUNA — розряд 37016) |
| `counter_offset` | Float | `digits=(16,3)`, `default=0`, `readonly=True`, `string="Поправка після скидань (імпорт)"` (R-03) |
| `counter_offset_export` | Float | те саме для експорту |
| `data_state` | Selection | `[('no_data','Ще не було даних'),('ok','Норма'),('stale','Немає даних'),('gap','Пропуск'),('reset','Скидання лічильника')]`, `default='no_data'`, `readonly=True`, `idx`, `tracking=True` |
| `data_state_since` | Datetime | `readonly=True` |
| `last_interval_start` | Datetime | `readonly=True`, `string="Останній побудований інтервал"` |
| `last_value` | Float | `related="e_import_signal_id.last_value"`, `string="Показник, кВт·год"` |
| `last_ts` | Datetime | `related="e_import_signal_id.last_ts"` |
| `p_now` | Float | `related="p_signal_id.last_value"`, `string="Потужність, кВт"` |
| `max_kw` | Float | `digits=(10,1)`, `req`, `default=10`, `string="Максимальна потужність, кВт"` — правдоподібність після скидання (R-03 п. 2), Додаток D.1 |
| `ct_ratio` | Char(16) | `string="Трансформатори струму"` (`1600/5`, `630/5`, `100/5` — iot_sim §8.7) |
| `unit_id` | Integer | `related="node_id.unit_id"` |
| `company_id` | Many2one | `related="node_id.company_id"`, `store=True` |
| `note` | Text | |

```python
    _f3d_energy_meter_code_uniq = models.Constraint("UNIQUE(code)", "Код лічильника має бути унікальним.")
```

`@api.constrains("e_import_signal_id", "e_export_signal_id", "p_signal_id")`: сигнал енергії не `kind='counter'` →
`ValidationError("Лічильник %s: сигнал енергії має бути накопичувальним (counter).")`; одиниця не `кВт·год` →
`"Лічильник %s: сигнал енергії має бути в кВт·год."`; `p_signal_id.unit` не `кВт` → `"…потужність має бути в кВт."`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `_f3d_counter_series(self, date_from, date_to, export=False) -> tools.counter.CounterSeries` | `ensure_one()`; R-03: показання `f3d.reading` сигналу (`quality != 'bad'`, `ts` між `date_from − 2 год` і `date_to + 2 год`, `ORDER BY ts`) + точка (`last_ts`, `last_value`) сигналу, якщо `last_ts > max(ts)`; якщо перших точок немає раніше `date_from` (ротація) — точки `(ts_start, e_start)` і `(ts_end, e_end)` з `f3d.energy.interval` за те саме вікно (запасний ряд, якість не краща за `interpolated`); повертає `CounterSeries(points, offset0=counter_offset)` |
| `_f3d_kwh(self, date_from, date_to) -> tuple[float, str]` | CE-06: `s = _f3d_counter_series(...)`; `s.delta(date_from, date_to)` (R-03) → `(round(kwh, 3), quality)`; немає сигналу енергії → `(0.0, 'missing')` |
| `_f3d_update_state(self, now)` | R-21 |
| `action_view_intervals(self)` | графік M-03 за останні 2 доби |

### M-03 `f3d.energy.interval` — 15-хв профіль лічильника (A-01, FR-04)

`_name = "f3d.energy.interval"`, `_description = "Енергетика: 15-хвилинний інтервал"`, `_order = "ts_start desc, meter_id"`,
`_log_access = False`, `_rec_name = "ts_start"`.

| Поле | Тип | Параметри |
|---|---|---|
| `meter_id` | Many2one `f3d.energy.meter` | `req`, `ondelete="cascade"`, `idx` |
| `node_id` | Many2one `f3d.energy.node` | `related="meter_id.node_id"`, `store=True`, `idx` |
| `role` | Selection | `related="meter_id.role"`, `store=True` |
| `ts_start` | Datetime | `req`, `idx`, `string="Початок (UTC)"` — кратний 15 хв |
| `ts_end` | Datetime | `req`, `string="Кінець (UTC)"` = `ts_start + 15 хв` |
| `day` | Date | `req`, `idx`, `string="Дата (Київ)"` = дата `ts_start` за Києвом |
| `hour_local` | Integer | `req`, `string="Година (Київ)"` 0…23 |
| `e_start`, `e_end` | Float | `digits=(16,3)` — безперервний лічильник `Ec` на межах (R-03) |
| `kwh` | Float | `digits=(12,3)`, `string="кВт·год"` = `e_end − e_start` (≥ 0) |
| `kwh_export` | Float | `digits=(12,3)`, `default=0`, `string="Віддано, кВт·год"` (лічильники з `e_export_signal_id`) |
| `kw_avg` | Float | `digits=(10,2)`, `string="Середня, кВт"` = `kwh × 4` |
| `zone_id` | Many2one `f3d.energy.tariff.zone` | `ondelete="set null"`, `string="Зона тарифу"` |
| `price` | Float | `digits=(10,4)`, `string="Ціна, грн/кВт·год"`, `cost` |
| `cost` | Float | `digits=(12,2)`, `string="Вартість, грн"`, `cost` — `kwh × price` лише для ролей `incomer`, `feeder`, `consumer`; для генерації/накопичувача 0 |
| `quality` | Selection | `[('measured','Виміряно'),('interpolated','Інтерпольовано'),('reset','Скидання лічильника'),('missing','Немає даних')]`, `req`, `default='measured'`, `idx` |
| `built_at` | Datetime | `req` |

```python
    _f3d_energy_interval_uniq = models.Constraint("UNIQUE(meter_id, ts_start)", "Інтервал для лічильника вже є.")
```
`init()`: `create_index(self.env.cr, "f3d_energy_interval_day_idx", self._table, ["day", "role"])`. Запис — лише
кроном/майстром (`INSERT … ON CONFLICT (meter_id, ts_start) DO UPDATE`, R-04); у формах `create="false" edit="false"`.
Методи: `@api.model _cron_build(self)` — R-04; `@api.model _f3d_rebuild(self, meters, date_from, date_to)` — R-04 для
вікна (майстер M-19, повтор `missing`).

### M-04 `f3d.energy.tariff` — тариф і договір (FR-05, A-17)

`_name = "f3d.energy.tariff"`, `_description = "Енергетика: тариф"`, `_inherit = ["mail.thread"]`, `_order = "date_from desc"`.

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char(128) | `req`, `string="Назва"` |
| `active` | Boolean | `default=True` |
| `company_id` | Many2one `res.company` | `req`, `default=lambda self: self.env.company`, `idx` |
| `currency_id` | Many2one `res.currency` | `req`, `default=lambda self: self.env.company.currency_id` |
| `date_from` | Date | `req`, `string="Діє з"`, `tracking=True` |
| `date_to` | Date | `string="Діє по"` (порожньо — безстроково), `tracking=True` |
| `zone_ids` | One2many `f3d.energy.tariff.zone` `tariff_id` | `string="Зони"`, `copy=True` |
| `export_price` | Float | `digits=(10,4)`, `default=0`, `string="Ціна віддачі в мережу, грн/кВт·год"`, `cost` |
| `contract_kw` | Float | `digits=(10,1)`, `req`, `default=800`, `string="Договірна потужність, кВт"`, `tracking=True` (Q-04) |
| `peak_warn_pct` | Float | `digits=(5,1)`, `default=90`, `string="Попередження від, % договірної"` |
| `note` | Text | |

`@api.constrains("date_from", "date_to", "active", "company_id")`: `date_to < date_from` → `"Дата «по» раніше дати «з»."`;
перетин періодів з іншим активним тарифом компанії (`date_to` порожня = +∞) → `"Період тарифу перетинається з «%s»."`.
`@api.constrains("zone_ids")` `_check_coverage` (R-05 п. 3): кожна 15-хв чверть тижня (7 × 96) покрита рівно однією
зоною → інакше `"Зони тарифу «%s»: %s о %s не покрито"` або `"… покрито двічі (%s, %s)"` (день — «пн»…«нд»).
`write`/`create` зі зміною `contract_kw`, `peak_warn_pct`, `date_*`, `active` → `_f3d_apply_contract_thresholds()` (R-12 п. 1).

Методи (`tools/tariff.py` — чисті функції; модель — обгортки):

| Сигнатура | Алгоритм |
|---|---|
| `@api.model _f3d_tariff_at(self, dt_utc, company=None)` | активний тариф компанії, де `date_from ≤ local_date(dt_utc) ≤ date_to` (або `date_to` порожня); немає → порожньо |
| `@api.model _f3d_price_at(self, dt_utc, company=None) -> tuple[zone, float]` | R-05 |
| `_f3d_apply_contract_thresholds(self)` | R-12 п. 1 для чинного сьогодні тарифу |

### M-05 `f3d.energy.tariff.zone` — зона тарифу

`_name = "f3d.energy.tariff.zone"`, `_description = "Енергетика: зона тарифу"`, `_order = "tariff_id, sequence, id"`.

| Поле | Тип | Параметри |
|---|---|---|
| `tariff_id` | Many2one `f3d.energy.tariff` | `req`, `ondelete="cascade"`, `idx` |
| `sequence` | Integer | `default=10` |
| `name` | Char(64) | `req`, `string="Зона"` («День», «Ніч», «Пік») |
| `code` | Selection | `[('flat','Цілодобова'),('day','День'),('night','Ніч'),('peak','Пік'),('half_peak','Напівпік')]`, `req`, `default='flat'` |
| `price` | Float | `digits=(10,4)`, `req`, `string="Ціна, грн/кВт·год"`, `cost` |
| `weekdays` | Char(7) | `req`, `default="0123456"`, `string="Дні тижня"` (0 — понеділок; `^[0-6]{1,7}$`, без повторів) |
| `hour_from` | Float | `req`, `default=0`, `string="З (год)"` (0…24, кратне 0,25; віджет `float_time`) |
| `hour_to` | Float | `req`, `default=24`, `string="До (год)"`; `hour_to < hour_from` — вікно через північ (23:00–07:00); `hour_from == hour_to` заборонено |
| `color` | Integer | для графіків |

`@api.constrains`: `weekdays` формат → `"Дні тижня: цифри 0…6 без повторів (0 — понеділок)."`; години поза 0…24 або не кратні
0,25 → `"Години зони — від 0 до 24 з кроком 15 хв."`; `hour_from == hour_to` → `"Зона «%s» має нульову тривалість."`;
`price < 0` → `"Ціна не може бути від'ємною."`.

### M-06 `f3d.energy.pool` — пул спільних споживачів (FR-09, Q-01)

`_name = "f3d.energy.pool"`, `_description = "Енергетика: пул спільних споживачів"`, `_inherit = ["mail.thread"]`, `_order = "sequence, code"`.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(32) | `req`, `copy=False`, regex M-01 (`POOL-AIR`) |
| `name` | Char(128) | `req` |
| `sequence` | Integer | `default=10` |
| `active` | Boolean | `default=True` |
| `node_ids` | One2many `f3d.energy.node` `pool_id` | `string="Споживачі пулу"` |
| `driver` | Selection | `[('kwh','Пропорційно прямим кВт·год'),('time','Пропорційно машинному часу')]`, `req`, `default='kwh'`, `tracking=True` |
| `workcenter_ids` | Many2many `mrp.workcenter` | `relation="f3d_energy_pool_workcenter_rel"`, `string="Обслуговує робочі центри"`, `help="Порожньо — усі робочі центри з прямим лічильником"` |
| `note` | Text | |
| `kwh_today` | Float | `compute` (не зберігається): Σ `kwh_today` вузлів |

`_f3d_energy_pool_code_uniq = models.Constraint("UNIQUE(code)", "Код пулу має бути унікальним.")`. Архівований пул не
розподіляється — його енергія йде в `unallocated` (R-09 п. 6).

### M-07 `f3d.energy.alloc` — розподіл енергії за добу (FR-08…FR-10, A-09, A-11)

`_name = "f3d.energy.alloc"`, `_description = "Енергетика: розподіл на виробництво"`, `_order = "day desc, production_id, workorder_id, kind"`.

| Поле | Тип | Параметри |
|---|---|---|
| `day` | Date | `req`, `idx`, `string="Дата (Київ)"` |
| `kind` | Selection | `[('direct','Пряма'),('shared','Спільна'),('idle','Простій РЦ'),('unallocated','Нерозподілена'),('overhead','Накладні')]`, `req`, `idx` |
| `workorder_id` | Many2one `mrp.workorder` | `ondelete="cascade"`, `idx` (порожньо для `idle`, `unallocated`, `overhead`) |
| `production_id` | Many2one `mrp.production` | `related="workorder_id.production_id"`, `store=True`, `idx` |
| `workcenter_id` | Many2one `mrp.workcenter` | `idx` (для `direct`, `shared`, `idle`) |
| `node_id` | Many2one `f3d.energy.node` | вузол-споживач (`direct`, `idle`, `overhead`) |
| `pool_id` | Many2one `f3d.energy.pool` | (`shared`, `unallocated`) |
| `kwh` | Float | `digits=(12,3)`, `string="кВт·год"` |
| `minutes` | Float | `digits=(10,1)`, `string="Хвилин роботи"` (для `direct`/`shared` — хвилини завдання в добі) |
| `cost` | Float | `digits=(12,2)`, `string="Вартість, грн"`, `cost` |
| `currency_id` | Many2one `res.currency` | `default=lambda self: self.env.company.currency_id` |
| `quality` | Selection | `[('measured','Виміряно'),('interpolated','Інтерпольовано'),('estimate','Оцінка'),('partial','Частково')]`, `req`, `default='measured'` |
| `locked` | Boolean | `default=False`, `idx`, `string="Зафіксовано"` (МО закрито, R-10) |
| `analytic_line_ids` | Many2many `account.analytic.line` | `relation="f3d_energy_alloc_analytic_rel"`, `copy=False` |
| `company_id` | Many2one `res.company` | `req`, `default=lambda self: self.env.company` |

Ключ запису (перевіряється кодом, не SQL — `NULL` у ключі): `(day, kind, workorder_id, workcenter_id, node_id, pool_id)`.
Методи: `@api.model _cron_alloc(self)` — R-08, R-09; `@api.model _f3d_alloc_days(self, days, now=None)` — повний
перерахунок діб; `_prepare_analytic_line_values(self, account_field_values, amount, unit_amount)` — A-11:
`{"name": "[EN] %s" % workorder_id.display_name, "amount": amount, **account_field_values, "unit_amount": unit_amount,
"product_id": workorder_id.product_id.id, "product_uom_id": env.ref("uom.product_uom_kwh").id, "company_id":
company_id.id, "ref": production_id.name, "category": "manufacturing_order"}`.

### M-08 `f3d.energy.balance` — погодинна перевірка балансу (FR-07)

`_name = "f3d.energy.balance"`, `_description = "Енергетика: баланс обліку"`, `_order = "hour desc, node_id"`, `_log_access = False`.

| Поле | Тип | Параметри |
|---|---|---|
| `node_id` | Many2one `f3d.energy.node` | `req`, `ondelete="cascade"`, `idx` (Q1, Q2, QF-1…4, QF-C1/C2) |
| `hour` | Datetime | `req`, `idx`, `string="Година (UTC)"` |
| `day` | Date | `req`, `string="Дата (Київ)"` |
| `measured_kwh` | Float | `digits=(12,3)` |
| `expected_kwh` | Float | `digits=(12,3)` |
| `diff_kwh` | Float | `digits=(12,3)` = `measured − expected` |
| `diff_pct` | Float | `digits=(8,2)` |
| `state` | Selection | `[('ok','Норма'),('deviation','Відхилення'),('skipped','Не перевірено')]`, `req`, `idx` |
| `reason` | Char(256) | причина `skipped` або перелік дочірніх без даних |

`_f3d_energy_balance_uniq = models.Constraint("UNIQUE(node_id, hour)", "Баланс за цю годину вже є.")`.

### M-09 `f3d.energy.event` — журнал подій енергетики (FR-13)

`_name = "f3d.energy.event"`, `_description = "Енергетика: подія"`, `_order = "ts desc, id desc"`, `_log_access = False`.

| Поле | Тип | Параметри |
|---|---|---|
| `ts` | Datetime | `req`, `idx` |
| `level` | Selection | `[('info','Інформація'),('warn','Увага'),('bad','Аварія')]`, `req`, `idx` |
| `kind` | Selection | `[('threshold','Поріг сигналу'),('peak','Пік потужності'),('balance','Баланс'),('meter','Лічильник'),('ats','АВР'),('outage','Відключення'),('pfc','Компенсація'),('manual','Вручну')]`, `req` |
| `code` | Char(32) | код об'єкта сцени (`CNC-2`, `SWB-1`, `PFC-2`, `ATS-1`) |
| `node_id` | Many2one `f3d.energy.node` | `ondelete="set null"` |
| `signal_id` | Many2one `f3d.signal` | `ondelete="set null"` |
| `outage_id` | Many2one `f3d.energy.outage` | `ondelete="set null"` |
| `text` | Char(256) | `req` (українською, з числами: «CNC-2: аварійна зупинка, споживання впало до 0,7 кВт.») |

Метод `@api.model _f3d_log(self, level, kind, code, text, ts=None, node=None, signal=None, outage=None, dedup_min=0)`:
`dedup_min > 0` і є подія з тими самими `kind`, `code`, `text` за останні `dedup_min` хв → не створювати; інакше
`create(...)`; потім `_notify_viewer('f3d.energy', [code])` (R-18).

### M-10 `f3d.energy.outage` — відключення мережі (FR-14, CE-03)

`_name = "f3d.energy.outage"`, `_description = "Енергетика: відключення мережі"`, `_inherit = ["mail.thread"]`, `_order = "ts_start desc"`.

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | `compute="_compute_name"`, `store=True`: `"Відключення %s" % local(ts_start).strftime("%d.%m.%Y %H:%M")` |
| `ts_start` | Datetime | `req`, `idx`, `string="Початок"` |
| `ts_end` | Datetime | `string="Кінець"` |
| `duration_min` | Float | `compute`, `store=True`, `digits=(10,1)`: `(ts_end − ts_start)/60` (відкрите — 0) |
| `state` | Selection | `[('open','Триває'),('closed','Завершено')]`, `req`, `default='open'`, `idx` |
| `source` | Selection | `[('ats','За АВР'),('incomers','За вводами')]`, `req` |
| `amf_master` | Selection | `[('hgm','HGM6120N (Remote control АВР)'),('ats','ATyS p (Auto)'),('unknown','Невідомо')]`, `default='unknown'` (режим АВР на початку, R-14 п. 6) |
| `transfer_s` | Float | `digits=(8,1)`, `string="Переключення на генератор, с"` (від `ts_start` до `position=3`) |
| `return_s` | Float | `string="Повернення на мережу, с"` (від появи мережі до `position=2`) |
| `gen_started` | Boolean | `string="Генератор запустився"` |
| `gen_start_at` | Datetime | `readonly=True` — момент `gen_start='on'` (R-14 п. 5) |
| `grid_back_at` | Datetime | `readonly=True` — момент повернення мережі (R-14 п. 7) |
| `fail_start` | Boolean | `string="FAIL START"` |
| `load_before_kw` | Float | `digits=(10,1)` — `energy/totals/p_now` перед подією |
| `critical_kw` | Float | `digits=(10,1)` — `critical_kw` на початку |
| `load_island_kw` | Float | `digits=(10,1)` — останнє споживання під час острова |
| `shed_kw` | Float | `digits=(10,1)` — max `load_before − load_island` |
| `event_ids` | One2many `f3d.energy.event` `outage_id` | |
| `note` | Text | |

Відкрите відключення одне: `@api.constrains("state")` друге `open` → `ValidationError("Уже триває відключення %s.")`.

### M-11 `mrp.workorder` — розширення: енергія завдання (CE-07, FR-08)

`_inherit = "mrp.workorder"`.

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_energy_alloc_ids` | One2many `f3d.energy.alloc` `workorder_id` | `string="Розподіл енергії"` |
| `f3d_energy_direct_kwh` | Float | `compute="_compute_f3d_energy"`, `store=True`, `digits=(12,3)`, `string="Енергія пряма, кВт·год"` |
| `f3d_energy_shared_kwh` | Float | те саме, `string="Енергія спільна, кВт·год"` |
| `f3d_energy_kwh` | Float | те саме, `string="Енергія, кВт·год"` = пряма + спільна |
| `f3d_energy_cost` | Float | те саме, `digits=(12,2)`, `string="Вартість енергії, грн"`, `cost` |
| `f3d_energy_minutes` | Float | те саме, `digits=(10,1)`, `string="Хвилин з енергією"` (Σ `minutes` рядків `direct`) |
| `f3d_energy_quality` | Selection | те саме, `[('none','Немає даних'),('measured','Виміряно'),('estimate','Оцінка'),('partial','Частково')]` |

`_compute_f3d_energy` (`@api.depends("f3d_energy_alloc_ids.kwh", "f3d_energy_alloc_ids.cost", "f3d_energy_alloc_ids.kind",
"f3d_energy_alloc_ids.quality")`): `direct = Σ kwh (kind='direct')`, `shared = Σ kwh (kind='shared')`, `cost = Σ cost
(direct+shared)`, `minutes = Σ minutes (direct)`; `quality`: немає рядків → `none`; усі `direct` `measured` (або
`interpolated`) → `measured`; усі `estimate` → `estimate`; інакше `partial`. Округлення: `kwh` 3 знаки, `cost` 2.

### M-12 `mrp.production` — розширення: енергія й собівартість МО (CE-07, FR-10, A-10)

`_inherit = "mrp.production"`.

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_energy_alloc_ids` | One2many `f3d.energy.alloc` `production_id` | `string="Розподіл енергії"` |
| `f3d_energy_direct_kwh` | Float | `compute="_compute_f3d_energy"`, `store=True`, `digits=(12,3)`, `string="Енергія пряма, кВт·год"` = Σ `workorder_ids.f3d_energy_direct_kwh` |
| `f3d_energy_shared_kwh` | Float | те саме = Σ `f3d_energy_shared_kwh` |
| `f3d_energy_kwh` | Float | те саме, `string="Енергія, кВт·год"` |
| `f3d_energy_cost` | Float | те саме, `digits=(12,2)`, `string="Вартість енергії, грн"`, `cost` |
| `f3d_energy_unit_cost` | Float | `compute` (не зберігається), `digits=(12,4)`, `string="Енергія на одиницю, грн"`, `cost` = `cost / qty`, де `qty = product_uom_id._compute_quantity(qty_producing or product_qty, product_id.uom_id)`; `qty == 0` → 0 |
| `f3d_energy_state` | Selection | `compute`, `store=True`: `[('none','Немає даних'),('estimate','Оцінка'),('partial','Частково виміряно'),('measured','Виміряно')]` — за `f3d_energy_quality` завдань з енергією (як M-11) |
| `f3d_energy_locked` | Boolean | `readonly=True`, `copy=False`, `string="Енергію зафіксовано"` |
| `f3d_energy_applied_unit` | Float | `readonly=True`, `copy=False`, `digits=(12,4)`, `string="Енергія в Extra Unit Cost, грн/од."`, `cost` |

`@api.depends("workorder_ids.f3d_energy_direct_kwh", "workorder_ids.f3d_energy_shared_kwh", "workorder_ids.f3d_energy_cost",
"workorder_ids.f3d_energy_quality")`.

Методи (R-10):

| Сигнатура | Алгоритм |
|---|---|
| `_cal_price(self, consumed_moves)` | перевизначення: **до** `super()`: якщо не `self.env.context.get('f3d_energy_skip')`: `self._f3d_energy_finalize()`; далі `self._f3d_energy_apply_extra_cost()`; потім `return super()._cal_price(consumed_moves)` |
| `_f3d_energy_finalize(self)` | `ensure_one()`; якщо `f3d_energy_locked` — нічого; `days` = місцеві дати з першої до останньої хвилини інтервалів завдань МО (R-08 п. 1) обмежені `now`; `env['f3d.energy.alloc']._f3d_alloc_days(days, now=now)` (перерахунок діб включно з поточною до `now`); `self.f3d_energy_alloc_ids.write({'locked': True})`; `f3d_energy_locked=True`; аналітика R-10 п. 5; чаттер «Енергію зафіксовано: N кВт·год (прямі X, спільні Y), вартість Z грн, якість <мітка>» (сума пишеться завжди — чаттер МО бачать користувачі з правами на МО; бухгалтерський зміст — у полях з `groups`) |
| `_f3d_energy_apply_extra_cost(self)` | R-10 п. 3–4 |
| `_get_backorder_mo_vals(self)` | `res = super()._get_backorder_mo_vals()`; `res['extra_cost'] = max(0.0, self.extra_cost - self.f3d_energy_applied_unit)`; `return res` (енергія не переходить у дозамовлення) |
| `action_f3d_energy_recompute(self)` | лише `group_energy_manager` (`AccessError`), лише незафіксовані: `_f3d_alloc_days(days)`; `display_notification` «Перераховано: N кВт·год» |
| `action_f3d_view_alloc(self)` | `act_window` `f3d.energy.alloc` (`domain=[('production_id','=',id)]`, вид list/pivot) |

### M-13 `mrp.workcenter` — розширення

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_energy_node_id` | Many2one `f3d.energy.node` | `compute="_compute_f3d_energy_node"` (не зберігається, `search="_search_f3d_energy_node"`): вузол з `workcenter_id = self` |
| `f3d_energy_p_now` | Float | `compute`: `f3d_energy_node_id.p_now`, `string="Потужність зараз, кВт"` |
| `f3d_kwh_today` | Float | `compute`: Σ інтервалів лічильника вузла за сьогодні, `string="Енергія сьогодні, кВт·год"` |
| `f3d_kwh_idle_today` | Float | `compute`: Σ `f3d.energy.alloc.kwh` (`kind='idle'`, `day=today`, `workcenter_id=self`), `string="Простій сьогодні, кВт·год"` |

Метод `action_f3d_energy_view(self)` — графік M-03 вузла за 2 доби.

### M-14 `maintenance.equipment` — розширення

`f3d_energy_node_ids` One2many `f3d.energy.node` `equipment_id` (`string="Вузли мережі"`), `f3d_energy_node_count`
Integer `compute`; `action_f3d_energy_nodes(self)` — `act_window` вузлів обладнання.

### M-15 `f3d.signal` — розширення: вхід показань, походження, заборона запису (A-15)

`_inherit = "f3d.signal"`.

- `origin` — `selection_add=[('module', 'Дані модуля')]`, `ondelete={'module': 'set default'}` (147 власних сигналів
  енергетики — Додаток C, колонка «Походження»).
- `@api.constrains("write_enabled", "module")` `_check_f3d_energy_write`: `module == 'energy' and write_enabled` →
  `ValidationError("Запис уставок у пристрої енергетики заборонено у v1 (factory3d.energy.write_enabled).")`.
- Перевизначення входу (`super()` **першим**, результат не змінюється; як machine_connect M-18):

```python
    ENERGY_PREFIXES = ("energy/", "infra/pv/", "infra/bess/", "infra/chp/", "infra/ats/", "infra/totals/")

    @api.model
    def _f3d_ingest(self, readings, src="module", collector=None):
        if self.env.context.get("f3d_energy_internal"):
            return super()._f3d_ingest(readings, src=src, collector=collector)
        codes = {r.get("code") for r in readings
                 if str(r.get("code", "")).startswith(self.ENERGY_PREFIXES)
                 or (str(r.get("code", "")).startswith("workcenters/") and str(r.get("code")).endswith("/machine_state"))}
        before = {}
        if codes:
            before = {s["code"]: (s["status"], s["last_text"], s["last_value"])
                      for s in self.sudo().search_read([("code", "in", list(codes))], ["code", "status", "last_text", "last_value"])}
        res = super()._f3d_ingest(readings, src=src, collector=collector)
        if before and param_bool(self.env, "factory3d.energy.read_enabled"):
            self.env["f3d.energy.event"].sudo()._f3d_on_ingest(before, readings)   # R-13, R-14
        return res
```

`f3d.energy.event._f3d_on_ingest(before, readings)` (метод M-09): `after = search_read` тих самих кодів; для кожного коду
зі зміненим `status` (R-13 п. 1) — подія; для `infra/ats/*` — R-14 (похідні `src1_ok/src2_ok`, відкриття/закриття
відключення, переключення, FAIL START). Виклики `_f3d_ingest` всередині — з контекстом `f3d_energy_internal=True`.
Винятки всередині обробника ловляться (`_logger.exception`) і не відкочують пакет (`with self.env.cr.savepoint()`).

### M-16 `f3d.source` — розширення: локальний тип `f3d_energy` (CT-12, A-08)

`_inherit = "f3d.source"`; `type` — `selection_add=[('f3d_energy', 'Енергетика (обчислені)')]`,
`ondelete={'f3d_energy': 'cascade'}`; `@api.model _f3d_local_types(self)` → `super()._f3d_local_types() + ['f3d_energy']`.
Джерело `EN-DERIVED` (xml-id `factory3d_energy.source_en_derived`, створює хук): `name="Енергетика: обчислені показники"`,
`collector_id` порожній, `params={}`, `module='energy'`, `read_enabled` = параметр `read_enabled`, `state` веде модуль
(`online`, поки крон `cron_f3d_energy_live` працює; R-21 п. 4).

### M-17 `maintenance.request` — розширення

`create(self, vals_list)`: `records = super().create(vals_list)`; для записів з `f3d_signal_id.module == 'energy'` —
`message_subscribe(partner_ids=users(group_energy_manager).partner_id.ids)` (енергетики отримують повідомлення про
заявки з енергетики, FR-12); `return records`.

### M-18 `res.config.settings` — розширення

| Поле | Тип | `config_parameter` / примітка |
|---|---|---|
| `f3d_energy_read_enabled` | Boolean | `factory3d.energy.read_enabled`; `set_values` → `write({'read_enabled': v})` на джерела `module='energy'` |
| `f3d_energy_write_enabled` | Boolean | `factory3d.energy.write_enabled`, `readonly=True` у формі (A-15) |
| `f3d_energy_costing_enabled` | Boolean | `factory3d.energy.costing_enabled` |
| `f3d_energy_analytic_enabled` | Boolean | `factory3d.energy.analytic_enabled` |
| `f3d_energy_balance_tol_pct` | Float | `factory3d.energy.balance_tol_pct` |
| `f3d_energy_balance_tol_kwh` | Float | `factory3d.energy.balance_tol_kwh` |
| `f3d_energy_gap_alarm_min` | Integer | `factory3d.energy.gap_alarm_min` |
| `f3d_energy_max_wait_h` | Integer | `factory3d.energy.max_wait_h` |
| `f3d_energy_keep_interval_days` | Integer | `factory3d.energy.keep_interval_days` |
| `f3d_energy_keep_event_days` | Integer | `factory3d.energy.keep_event_days` |
| `f3d_energy_shift_calendar_id` | Many2one `resource.calendar` | `factory3d.energy.shift_calendar_id` (id рядком) |
| `f3d_energy_typical_days` | Integer | `factory3d.energy.typical_days` |
| `f3d_energy_ats_fail_start_s` | Integer | `factory3d.energy.ats_fail_start_s` |
| `f3d_energy_peak_shave_kw` | Float | `factory3d.energy.peak_shave_kw` |
| `f3d_energy_install_state` | Char | `compute`: `json.loads(param install_report).get('state', '—')` |

Булеві читаються `get_param(key, 'False') in ('True', 'true', '1')` (як base §5.1). Помічник модуля
`tools.dates.param_bool(env, key)`, `param_float`, `param_int` — з умовчаннями §5.1.

### M-19 `f3d.energy.recompute.wizard` — перерахунок (Transient, FR-26)

| Поле | Тип | Параметри |
|---|---|---|
| `date_from` | Date | `req`, `default=today − 1` |
| `date_to` | Date | `req`, `default=today` |
| `what` | Selection | `[('intervals','Інтервали лічильників'),('alloc','Розподіл на виробництво'),('both','Усе')]`, `req`, `default='both'` |
| `meter_ids` | Many2many `f3d.energy.meter` | порожньо — усі |
| `result` | Text | readonly |

`action_run(self)`: користувач без `group_energy_manager` → `AccessError("Перерахунок енергії доступний енергетику.")`;
`date_to − date_from > 31 доба` → `UserError("Перерахунок — не більше 31 доби за раз.")`; `intervals` →
`f3d.energy.interval._f3d_rebuild(meters, d0, d1)`; `alloc` → `_f3d_alloc_days(days)` (зафіксовані рядки не змінюються,
R-23); `result` = «Інтервалів: N (нових M), діб розподілу: K, зафіксованих рядків пропущено: L».

### M-20 Провайдери переглядача — `AbstractModel` без `_inherit` (A-04, CE-08)

```python
class F3dViewerProviderEnergy(models.AbstractModel):
    _name = "f3d.viewer.provider.energy"
    _description = "3D: енергетика"
    _f3d_sequence = 100
    _f3d_sections = ("energy",)
    _f3d_group = "factory3d_base.group_f3d_user"      # кіоск і переглядач; гроші ховає R-16 п. 2, п. 8

class F3dViewerProviderInfra(models.AbstractModel):
    _name = "f3d.viewer.provider.infra"
    _description = "3D: власна генерація й резерв"
    _f3d_sequence = 150
    _f3d_sections = ("infra",)
    _f3d_group = "factory3d_base.group_f3d_user"
```

| Метод | `f3d.viewer.provider.energy` | `f3d.viewer.provider.infra` |
|---|---|---|
| `_f3d_viewer_collect(self, payload, ctx)` | `tools.payload.build_energy(self.env, ctx, payload)` (R-16): пише `payload["energy"]` (заміна вмісту ключів A.12, решта ключів статики лишається), `payload["workcenters"][wc]["energy"]` для наявних РЦ, `energy_kwh/energy_cost/energy_quality` у `payload["productions"]` | `tools.payload.build_infra(self.env, ctx, payload)` (R-17): `payload.setdefault("infra", {})`; оновлює `cards` лише `PV-ROOF`, `PV-INV`, `CHP`, `ATS-1`, `BESS`; `totals.update(<ключі CE-03>)` |
| `_f3d_viewer_delta(self, patch, ctx)` | R-18: якщо `ctx["changes"]` має `f3d.energy` або коди `f3d.signal` з префіксами `energy/`, `infra/` (крім `infra/genset/`, `infra/water/`) → `tmp = {}`; `build_energy(env, ctx, tmp)`; `patch["energy"] = tmp["energy"]`; для записів `patch.get("productions", [])` — ключі МО (R-16 п. 8) | те саме для `infra`, але **глибоке злиття** `deep_merge(patch.setdefault("infra", {}), tmp["infra"])` (A-22) |
| `_f3d_viewer_bus_models(self)` | `["f3d.signal", "f3d.energy", "mrp.production", "mrp.workorder"]` | `["f3d.signal", "f3d.energy"]` |

Виклики ORM — від імені користувача запиту (без `sudo`), крім читання параметрів. Відсутність прав на модель
(`has_access('read')` = False) → провайдер нічого не пише. Без `factory3d_viewer` моделі просто не викликаються.

## 3. Представлення й меню

Спільне: рядки UI українською; грошові поля — `groups="factory3d_energy.group_energy_cost"`; стани — `widget="badge"` з
`decoration-success` (`ok`/`measured`/`closed`), `decoration-warning` (`gap`/`interpolated`/`deviation`/`warn`),
`decoration-danger` (`stale`/`missing`/`bad`/`open`), `decoration-muted` (`no_data`/`skipped`/`none`).

| ID | XML-id (`factory3d_energy.`) | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `view_f3d_energy_node_hierarchy` | hierarchy `f3d.energy.node` | `parent_field="parent_id"`, `child_field="child_ids"`, `draggable="0"`, `icon="fa-bolt"`; картка: `name`, `code` (badge), `kind`, `p_now` («кВт зараз»), `rating_a`/`rating_kva`, `live_status` (badge), `is_critical` (іконка `fa-shield` якщо так); `<templates>` з `t-name="hierarchy-box"`; дія за замовчуванням меню «Схема мережі» з `context={'hierarchy_res_id': id GRID-10KV}` |
| V-02 | `view_f3d_energy_node_form` | form | `<header>`: «Показати в 3D» (`action_f3d_show`, `invisible="not equipment_id"`). Статбокс: `action_view_meters` (`fa-tachometer`, кількість), `action_view_intervals` («Профіль»), `action_view_balance` («Баланс», `invisible="kind not in ('cell')"`). `name` (title), `code`; група «Схема»: `kind`, `cell_type` (`invisible="kind != 'cell'"`), `line_kind` (`invisible="kind != 'line'"`), `gen_kind` (`invisible="kind != 'generator'"`), `parent_id`, `cabinet_id`, `peer_id` (`invisible="cell_type != 'coupler'"`), `section`, `sequence`, `active`; група «Прив'язка»: `equipment_id`, `workcenter_id` (`invisible="kind != 'consumer'"`), `zone_id`, `unit_id`; група «Номінали»: `voltage_kv`, `rating_a`, `rating_kva`, `rating_kvar`, `p_inst_kw`, `p_inst_source`, `load_factor`, `idle_factor`, `cos_phi_nominal`; група «Розподіл»: `alloc_role`, `pool_id` (`invisible="alloc_role != 'shared'"`), `is_critical`, `group`; група «Зараз» (readonly): `p_now`, `kwh_today`, `live_status`; вкладки «Живить» (`child_ids` list readonly: `code`, `name`, `kind`, `p_now`), «Лічильники» (`meter_ids`: `code`, `model`, `role`, `data_state`, `last_value`, `p_now`), «Примітка»; чаттер. Редагування — лише `group_energy_manager` (ACL) |
| V-03 | `view_f3d_energy_node_list` | list | `code`, `name`, `kind`, `cell_type` (optional hide), `parent_id`, `section`, `equipment_id` (optional show), `workcenter_id` (optional show), `p_inst_kw`, `p_now`, `kwh_today` (optional hide), `alloc_role` (optional hide), `pool_id` (optional hide), `is_critical` (optional hide), `live_status` (badge) |
| V-04 | `view_f3d_energy_node_search` | search | поля `code`, `name`, `equipment_id`, `workcenter_id`; фільтри за `kind` (12), «Критичні» (`is_critical`), «Прямі», «Спільні», «Накладні», «Без лічильника» (`meter_ids = False`), «Немає даних» (`meter_ids.data_state in (stale, gap, no_data)`); group by `kind`, `section`, `parent_id`, `pool_id` |
| V-05 | `view_f3d_energy_meter_list` / `_form` / `_search` | `f3d.energy.meter` | list: `code`, `node_id`, `model`, `role`, `p_now`, `last_value`, `last_ts`, `data_state` (badge), `data_state_since`, `last_interval_start` (optional hide), `source_id` (optional hide); form: `<header>` статусбар `data_state`; група: `code`, `name`, `node_id`, `model`, `role`, `ct_ratio`, `unit_id`, `active`; група «Сигнали»: `source_id`, `p_signal_id`, `e_import_signal_id`, `e_export_signal_id`; група «Стан» (readonly): `last_value`, `last_ts`, `p_now`, `counter_offset`, `counter_offset_export`, `data_state_since`, `last_interval_start`; кнопка `action_view_intervals`; чаттер; search: фільтри за `data_state`, `role`, `model`; group by `role`, `model` |
| V-06 | `view_f3d_energy_meter_kanban` | kanban (у «Огляд») | `default_group_by="role"`; картка: `code`, `node_id`, `p_now` кВт, `last_value` кВт·год, бейдж `data_state` |
| V-07 | `view_f3d_energy_interval_graph` / `_pivot` | graph / pivot `f3d.energy.interval` | graph: `type="bar"`, `<field name="ts_start" interval="hour"/>`, `<field name="kwh" type="measure"/>`, `stacked="1"` за `role`; pivot: рядки `node_id`, стовпці `day`, міри `kwh`, `cost`, `kw_avg` (avg) |
| V-08 | `view_f3d_energy_interval_list` / `_search` | list / search | list (`create="false" edit="false"`): `ts_start`, `meter_id`, `node_id`, `kwh`, `kwh_export` (optional hide), `kw_avg`, `zone_id`, `price`, `cost`, `quality` (badge); search: `meter_id`, `node_id`; фільтри «Сьогодні», «Вчора», «7 днів», «Не виміряно» (`quality != measured`), «Вводи», «Фідери», «Споживачі», «Генерація»; group by `day`, `hour_local`, `node_id`, `zone_id` |
| V-09 | `view_f3d_energy_tariff_list` / `_form` | `f3d.energy.tariff` | list: `name`, `date_from`, `date_to`, `contract_kw`, `active`; form: `name`; група «Договір»: `date_from`, `date_to`, `company_id` (multi-company), `currency_id`, `contract_kw`, `peak_warn_pct`, `export_price`, `active`; вкладка «Зони» (`zone_ids` editable list: `sequence` handle, `name`, `code`, `weekdays`, `hour_from` (`float_time`), `hour_to` (`float_time`), `price`); «Примітка»; чаттер. Доступ — `group_energy_cost` читання, `group_energy_manager` запис |
| V-10 | `view_f3d_energy_pool_list` / `_form` | `f3d.energy.pool` | list: `sequence` handle, `code`, `name`, `driver`, `kwh_today`, `active`; form: `code`, `name`, `driver`, `workcenter_ids` (`many2many_tags`), `node_ids` (list readonly: `code`, `name`, `p_now`), `note`; чаттер |
| V-11 | `view_f3d_energy_alloc_pivot` / `_list` / `_search` / `_graph` | `f3d.energy.alloc` | pivot: рядки `production_id`, стовпці `kind`, міри `kwh`, `cost`; list (readonly): `day`, `production_id`, `workorder_id`, `workcenter_id`, `kind`, `pool_id`, `kwh`, `minutes`, `cost`, `quality`, `locked`; search: фільтри за `kind`, «Зафіксовані», «Сьогодні», «Тиждень»; group by `day`, `production_id`, `workcenter_id`, `kind`, `pool_id`; graph bar `day`/`kwh` stacked `kind` |
| V-12 | `view_f3d_energy_balance_list` / `_search` | `f3d.energy.balance` | list (readonly): `hour`, `node_id`, `measured_kwh`, `expected_kwh`, `diff_kwh`, `diff_pct`, `state` (badge), `reason`; search: фільтри «Відхилення» (default у дії), «Сьогодні»; group by `node_id`, `day` |
| V-13 | `view_f3d_energy_event_list` / `_search` | `f3d.energy.event` | list (readonly): `ts`, `level` (badge: `info` — muted, `warn` — warning, `bad` — danger), `kind`, `code`, `text`; search: фільтри за `level`, `kind`; group by `kind`, `code` |
| V-14 | `view_f3d_energy_outage_list` / `_form` | `f3d.energy.outage` | list: `name`, `ts_start`, `ts_end`, `duration_min`, `state` (badge), `amf_master`, `transfer_s`, `shed_kw`, `fail_start`; form readonly (крім `note`): групи «Час», «Генератор і АВР», «Навантаження», вкладка «Події» (`event_ids`); чаттер |
| V-15 | `view_mrp_production_form_f3d_energy` | form inherit `mrp.mrp_production_form_view` | статкнопка в `//div[@name='button_box']`: `action_f3d_view_alloc` (`fa-bolt`, поле `f3d_energy_kwh` з підписом «кВт·год»); у `//notebook` нова `<page name="f3d_energy" string="Енергія">`: група «Енергія»: `f3d_energy_direct_kwh`, `f3d_energy_shared_kwh`, `f3d_energy_kwh`, `f3d_energy_state` (badge), `f3d_energy_locked`; група «Вартість» (`groups=cost`): `f3d_energy_cost`, `f3d_energy_unit_cost`, `f3d_energy_applied_unit`; кнопка `action_f3d_energy_recompute` («Перерахувати», `groups="factory3d_energy.group_energy_manager"`, `invisible="f3d_energy_locked"`); `f3d_energy_alloc_ids` (list readonly: `day`, `workorder_id`, `kind`, `pool_id`, `kwh`, `cost` (cost), `quality`) |
| V-16 | `view_mrp_workorder_form_f3d_energy` / `_list` | inherit `mrp.mrp_production_workorder_form_view_inherit` (form), `mrp.mrp_production_workorder_tree_editable_view` (list) | form: після `duration` — `f3d_energy_kwh`, `f3d_energy_cost` (cost), `f3d_energy_quality` (badge); list: `f3d_energy_kwh` (optional show, `sum="Разом"`), `f3d_energy_cost` (optional hide, cost) |
| V-17 | `view_mrp_workcenter_form_f3d_energy`, `view_maintenance_equipment_form_f3d_energy` | inherit `mrp.mrp_workcenter_view`, `maintenance.hr_equipment_view_form` | РЦ: статкнопка `action_f3d_energy_view` (`fa-bolt`, `f3d_kwh_today` «кВт·год сьогодні»), поля `f3d_energy_node_id`, `f3d_energy_p_now`, `f3d_kwh_idle_today` на вкладці «Завод 3D»; обладнання: статкнопка `action_f3d_energy_nodes` (`f3d_energy_node_count`, «Вузли мережі», `invisible="not f3d_energy_node_count"`) |
| V-18 | `res_config_settings_view_form_f3d_energy` | inherit `base.res_config_settings_view_form` | блок `<app string="Завод 3D: енергетика" name="factory3d_energy">`: «Стоп-крани» (`read_enabled`, `write_enabled` readonly з підказкою «заборонено у v1», `costing_enabled`, `analytic_enabled`), «Профіль і баланс» (`balance_tol_pct`, `balance_tol_kwh`, `gap_alarm_min`, `max_wait_h`, `typical_days`, `shift_calendar_id`), «Зберігання» (`keep_interval_days`, `keep_event_days`), «АВР і накопичувач» (`ats_fail_start_s`, `peak_shave_kw`), «Встановлення» (`install_state` readonly, кнопка «Повторити прив'язку даних» — `action_f3d_energy_rebind`, `groups="factory3d_base.group_f3d_admin"`) |
| V-19 | `view_f3d_energy_recompute_wizard_form` | form `f3d.energy.recompute.wizard` | `date_from`, `date_to`, `what`, `meter_ids` (`many2many_tags`), `result` (readonly, `invisible="not result"`); кнопки «Перерахувати» (`action_run`, `btn-primary`), «Закрити» |
| V-20 | `view_f3d_energy_dashboard` (дії «Огляд») | `ir.actions.act_window` `f3d.energy.node` kanban | дія `action_f3d_energy_overview`: kanban вузлів `kind in (transformer, line)` (`view_f3d_energy_node_kanban`: `name`, `code`, `p_now` кВт, `rating_a`/`rating_kva`, смуга завантаження `p_now`/номінал з кольорами viewer: < 60 % зелена, 60–80 % жовта, > 80 % червона, `kwh_today`); над kanban — `<div class="o_f3d_energy_kpi">` не робимо (A-12); поруч у меню: «Профіль доби» (`action_f3d_energy_profile`: graph M-03 `role='feeder'`, сьогодні, по годинах, stacked за `node_id`), «Енергія за МО» (`action_f3d_energy_alloc_pivot`), «Пік і вартість» (pivot M-03 `role='feeder'`, рядки `day`, міри `kwh`, `kw_avg` max, `cost`) |
| V-21 | меню та дії (`views/menus.xml`) | `ir.ui.menu` | таблиця нижче |

Меню (CB-09, `sequence=50` під `factory3d_base.menu_f3d_root`):

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_f3d_energy` | Енергетика | `factory3d_base.menu_f3d_root` | 50 | `group_energy_user` | — |
| `menu_f3d_energy_overview` | Огляд | `menu_f3d_energy` | 10 | `group_energy_user` | `action_f3d_energy_overview` |
| `menu_f3d_energy_scheme` | Схема мережі | `menu_f3d_energy` | 20 | `group_energy_user` | `action_f3d_energy_node_tree` (`f3d.energy.node`, views `hierarchy,list,form`) |
| `menu_f3d_energy_meter` | Лічильники | `menu_f3d_energy` | 30 | `group_energy_user` | `action_f3d_energy_meter` (list,kanban,form) |
| `menu_f3d_energy_profile` | Профіль доби | `menu_f3d_energy` | 40 | `group_energy_user` | `action_f3d_energy_profile` (graph,pivot,list; `context={'search_default_today': 1, 'search_default_role_feeder': 1}`) |
| `menu_f3d_energy_alloc` | Енергія на виробництво | `menu_f3d_energy` | 50 | `group_energy_user` | `action_f3d_energy_alloc_pivot` (pivot,graph,list) |
| `menu_f3d_energy_balance` | Баланс обліку | `menu_f3d_energy` | 60 | `group_energy_user` | `action_f3d_energy_balance` (`context={'search_default_deviation': 1}`) |
| `menu_f3d_energy_outage` | Відключення мережі | `menu_f3d_energy` | 70 | `group_energy_user` | `action_f3d_energy_outage` |
| `menu_f3d_energy_event` | Події | `menu_f3d_energy` | 80 | `group_energy_user` | `action_f3d_energy_event` |
| `menu_f3d_energy_config` | Налаштування | `menu_f3d_energy` | 90 | `group_energy_cost` | — |
| `menu_f3d_energy_tariff` | Тарифи й договір | `menu_f3d_energy_config` | 10 | `group_energy_cost` | `action_f3d_energy_tariff` |
| `menu_f3d_energy_pool` | Пули спільних споживачів | `menu_f3d_energy_config` | 20 | `group_energy_manager` | `action_f3d_energy_pool` |
| `menu_f3d_energy_recompute` | Перерахувати | `menu_f3d_energy_config` | 30 | `group_energy_manager` | `action_f3d_energy_recompute_wizard` (`target='new'`) |
| `menu_f3d_energy_settings` | Енергетика | `factory3d_base.menu_f3d_config` | 50 | `factory3d_base.group_f3d_admin` | `action_f3d_energy_settings` (`res.config.settings`, `context={'module': 'factory3d_energy'}`) |

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_f3d_energy_node_user,f3d.energy.node user,model_f3d_energy_node,factory3d_energy.group_energy_user,1,0,0,0
access_f3d_energy_node_manager,f3d.energy.node manager,model_f3d_energy_node,factory3d_energy.group_energy_manager,1,1,1,1
access_f3d_energy_node_f3d_user,f3d.energy.node f3d user,model_f3d_energy_node,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_energy_meter_user,f3d.energy.meter user,model_f3d_energy_meter,factory3d_energy.group_energy_user,1,0,0,0
access_f3d_energy_meter_manager,f3d.energy.meter manager,model_f3d_energy_meter,factory3d_energy.group_energy_manager,1,1,1,1
access_f3d_energy_meter_f3d_user,f3d.energy.meter f3d user,model_f3d_energy_meter,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_energy_interval_user,f3d.energy.interval user,model_f3d_energy_interval,factory3d_energy.group_energy_user,1,0,0,0
access_f3d_energy_interval_f3d_user,f3d.energy.interval f3d user,model_f3d_energy_interval,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_energy_interval_admin,f3d.energy.interval admin,model_f3d_energy_interval,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_energy_tariff_user,f3d.energy.tariff user,model_f3d_energy_tariff,factory3d_energy.group_energy_user,1,0,0,0
access_f3d_energy_tariff_manager,f3d.energy.tariff manager,model_f3d_energy_tariff,factory3d_energy.group_energy_manager,1,1,1,1
access_f3d_energy_tariff_zone_user,f3d.energy.tariff.zone user,model_f3d_energy_tariff_zone,factory3d_energy.group_energy_user,1,0,0,0
access_f3d_energy_tariff_zone_manager,f3d.energy.tariff.zone manager,model_f3d_energy_tariff_zone,factory3d_energy.group_energy_manager,1,1,1,1
access_f3d_energy_pool_user,f3d.energy.pool user,model_f3d_energy_pool,factory3d_energy.group_energy_user,1,0,0,0
access_f3d_energy_pool_manager,f3d.energy.pool manager,model_f3d_energy_pool,factory3d_energy.group_energy_manager,1,1,1,1
access_f3d_energy_alloc_user,f3d.energy.alloc user,model_f3d_energy_alloc,factory3d_energy.group_energy_user,1,0,0,0
access_f3d_energy_alloc_mrp,f3d.energy.alloc mrp user,model_f3d_energy_alloc,mrp.group_mrp_user,1,0,0,0
access_f3d_energy_alloc_admin,f3d.energy.alloc admin,model_f3d_energy_alloc,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_energy_balance_user,f3d.energy.balance user,model_f3d_energy_balance,factory3d_energy.group_energy_user,1,0,0,0
access_f3d_energy_balance_admin,f3d.energy.balance admin,model_f3d_energy_balance,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_energy_event_user,f3d.energy.event user,model_f3d_energy_event,factory3d_energy.group_energy_user,1,0,0,0
access_f3d_energy_event_f3d_user,f3d.energy.event f3d user,model_f3d_energy_event,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_energy_event_manager,f3d.energy.event manager,model_f3d_energy_event,factory3d_energy.group_energy_manager,1,1,1,0
access_f3d_energy_event_admin,f3d.energy.event admin,model_f3d_energy_event,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_energy_outage_user,f3d.energy.outage user,model_f3d_energy_outage,factory3d_energy.group_energy_user,1,0,0,0
access_f3d_energy_outage_f3d_user,f3d.energy.outage f3d user,model_f3d_energy_outage,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_energy_outage_manager,f3d.energy.outage manager,model_f3d_energy_outage,factory3d_energy.group_energy_manager,1,1,0,0
access_f3d_energy_outage_admin,f3d.energy.outage admin,model_f3d_energy_outage,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_energy_recompute_wizard_manager,f3d.energy.recompute.wizard manager,model_f3d_energy_recompute_wizard,factory3d_energy.group_energy_manager,1,1,1,1
```

Пояснення: `group_f3d_user` (переглядач, кіоск) читає вузли, лічильники, інтервали, події, відключення — провайдер
`infra` (група `group_f3d_user`) і картки. Провайдер `energy` вимагає `group_energy_user`. Тарифи читає
`group_energy_user`, але поля цін — `cost` (без групи вартості поля не видно). Абстрактні провайдери рядків не потребують.
Крони працюють від `base.user_root` (`sudo()` на власних моделях і `f3d.signal`/`f3d.reading` лише для читання й CT-10).

### 4.2 Групи (`security/f3d_energy_security.xml`)

```xml
<record id="privilege_f3d_energy" model="res.groups.privilege">
    <field name="name">Завод 3D: енергетика</field>
    <field name="category_id" ref="factory3d_base.module_category_factory3d"/>
    <field name="sequence">50</field>
</record>
<record id="group_energy_user" model="res.groups">
    <field name="name">Енергетика: перегляд</field><field name="privilege_id" ref="privilege_f3d_energy"/><field name="sequence">10</field>
    <field name="implied_ids" eval="[Command.link(ref('factory3d_base.group_f3d_user'))]"/>
</record>
<record id="group_energy_cost" model="res.groups">
    <field name="name">Енергетика: вартість</field><field name="privilege_id" ref="privilege_f3d_energy"/><field name="sequence">20</field>
    <field name="implied_ids" eval="[Command.link(ref('group_energy_user'))]"/>
</record>
<record id="group_energy_manager" model="res.groups">
    <field name="name">Енергетика: енергетик</field><field name="privilege_id" ref="privilege_f3d_energy"/><field name="sequence">30</field>
    <field name="implied_ids" eval="[Command.link(ref('group_energy_cost')), Command.link(ref('factory3d_base.group_f3d_manager'))]"/>
</record>
<record id="mrp.group_mrp_user" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_energy_user'))]"/>
</record>
<record id="mrp.group_mrp_manager" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_energy_cost'))]"/>
</record>
<record id="account.group_account_readonly" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_energy_cost'))]"/>
</record>
<record id="account.group_account_invoice" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_energy_cost'))]"/>
</record>
<record id="factory3d_base.group_f3d_admin" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_energy_manager'))]"/>
</record>
```

Наслідки: майстер (`mrp.group_mrp_user`) бачить кВт·год, не гроші; керівник виробництва й бухгалтер — гроші; енергетик
— усе й редагування; адміністратор `base.group_system` → `group_f3d_admin` → енергетик.

### 4.3 Record rules

| XML-id | Модель | Домен | Групи |
|---|---|---|---|
| `f3d_energy_node_rule_company` | `f3d.energy.node` | `['|', ('company_id','=',False), ('company_id','in',company_ids)]` | глобальне |
| `f3d_energy_tariff_rule_company` | `f3d.energy.tariff` | те саме | глобальне |
| `f3d_energy_alloc_rule_company` | `f3d.energy.alloc` | те саме | глобальне |
| `f3d_energy_meter_rule_company` | `f3d.energy.meter` | те саме (поле `company_id` related store) | глобальне |

Інтервали, баланс, події, відключення — без компанії (завод один; як `f3d.reading`).

### 4.4 Захист полів і дій

- Грошові поля (§2: позначка `cost`) — невидимі й не читаються без `group_energy_cost` (`groups=` на полі; `read` дає
  `AccessError` для явного запиту поля).
- `f3d.energy.alloc`, `f3d.energy.interval`, `f3d.energy.balance` — запис лише кроном/майстром (`sudo`), у формах
  `create/edit="false"`; ручне виправлення — адміністратор.
- `mrp.production.f3d_energy_locked`, `f3d_energy_applied_unit` — `readonly`, змінює лише `_f3d_energy_finalize`.
- Повтор хука (`action_f3d_energy_rebind`) і стоп-крани — `group_f3d_admin` (`AccessError` у методі).

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)

| key | value | XML-id | Примітка |
|---|---|---|---|
| `factory3d.energy.read_enabled` | `True` | `param_read_enabled` | хук перезаписує: `factory3d.base.environment == 'test'` → `True`, інакше `False` (CB-10) |
| `factory3d.energy.write_enabled` | `False` | `param_write_enabled` | A-15: значення не впливає — запис заборонено обмеженням |
| `factory3d.energy.costing_enabled` | `True` | `param_costing_enabled` | R-10 п. 3 |
| `factory3d.energy.analytic_enabled` | `True` | `param_analytic_enabled` | R-10 п. 5 |
| `factory3d.energy.balance_tol_pct` | `3` | `param_balance_tol_pct` | R-07 |
| `factory3d.energy.balance_tol_kwh` | `2.0` | `param_balance_tol_kwh` | R-07 |
| `factory3d.energy.gap_max_s` | `900` | `param_gap_max_s` | R-03: довший проміжок між точками → `interpolated` |
| `factory3d.energy.gap_alarm_min` | `60` | `param_gap_alarm_min` | R-21: подія «немає даних» |
| `factory3d.energy.max_wait_h` | `6` | `param_max_wait_h` | R-04: слот без точки після кінця стає `missing` |
| `factory3d.energy.settle_s` | `120` | `param_settle_s` | R-04: слот будується через 120 с після кінця |
| `factory3d.energy.reset_tol_kwh` | `1.0` | `param_reset_tol_kwh` | R-03: падіння лічильника більше цього — скидання |
| `factory3d.energy.keep_interval_days` | `400` | `param_keep_interval_days` | R-19 |
| `factory3d.energy.keep_event_days` | `90` | `param_keep_event_days` | R-19 |
| `factory3d.energy.shift_calendar_id` | `` | `param_shift_calendar` | хук: id `resource.calendar` з `name='Зміна 1 (07:00–15:30)'`, інакше `company.resource_calendar_id` |
| `factory3d.energy.typical_days` | `20` | `param_typical_days` | R-15 |
| `factory3d.energy.ats_fail_start_s` | `35` | `param_ats_fail_start_s` | R-14 п. 5 |
| `factory3d.energy.ats_fresh_factor` | `3` | `param_ats_fresh_factor` | R-14: свіжість сигналу АВР = `factor × period_s` |
| `factory3d.energy.peak_shave_kw` | `600` | `param_peak_shave_kw` | картка BESS (макет) |
| `factory3d.energy.alloc_close_h` | `2` | `param_alloc_close_h` | R-09: учорашня доба перераховується до 02:00 |
| `factory3d.energy.install_report` | `{}` | `param_install_report` | звіт хука |

### 5.2 Data-файли і генератор `tools/gen_energy_data.py`

Запуск (розробник, з кореня репозиторію): `python3 odoo_addons/factory3d_energy/tools/gen_energy_data.py --root .`.
Читає `plant/energy.py` (`energy_data`, `taps`, `PROFILE`, `IDLE_K`, `IDLE_DEFAULT`, `SWB_CELLS`, `SECTION`,
`BUSWAYS`, `CABLE_FEEDERS`), `plant/layout.py:MACHINES`, `plant/infra.py:CRITICAL`, `plant/equipment_specs.json`;
список unit id і адреси — зашиті таблиці Додатків A і D (з iot_sim §8.4.1, §8.7, §8.9 і виправлень A-06). Пише
детерміновано (сортування як у Додатках, без часових міток):

**`energy_nodes.csv`** (123 рядки, порядок Додатка B): `code,name,kind,cell_type,line_kind,gen_kind,parent,cabinet,peer,
section,sequence,equipment,workcenter,rating_a,rating_kva,rating_kvar,voltage_kv,p_inst_kw,p_inst_source,load_factor,
idle_factor,cos_phi,is_critical,alloc_role,pool,group,unit,note`. Порожня колонка = не задано. Шафи: `cabinet=SWB-1`,
`sequence` 10…110; `QS`: `parent=SEC-1`, `peer=SEC-2`; `ATS-1`: `parent=SWB-1`; `GENSET`: `parent=ATS-1`.

**`energy_sources.csv`** (68 рядків, Додаток D.2): `code,name,unit,equipment,host,port,timeout_s,retries,max_block,gap_max`
(`host=iot-sim`, `port=502`, `timeout_s=3`, `retries=2`, `max_block=125`, `gap_max=8`).

**`energy_signals.csv`** (297 рядків, Додаток C): `code,name,quantity,kind,unit,equipment,source,address,period_s,
store_period_s,decimals,states,warn_low,warn_high,alarm_low,alarm_high,alarm_states,alarm_title,hysteresis,
min_duration_s,viewer_visible,derived_from,origin,binding`; `address` — JSON (Додаток A); `states`, `alarm_states` —
JSON-списки; `binding` ∈ {`full` — створити або оновити визначення; `thresholds` — якщо сигнал існує, оновити лише
пороги/`alarm_title`/`hysteresis`/`min_duration_s`, якщо не існує — створити з усіма колонками (2 рядки
`energy/transformers/T*/temp_c`: джерело `MB-U96-RTD1` і адреса з telemetry Додаток C.2)}; `origin` ∈ {`catalog`,
`module`} — лише при створенні.

**`energy_meters.csv`** (67 рядків, Додаток D.1): `code,name,node,model,role,source,p_signal,e_import_signal,
e_export_signal,ct_ratio`.

**`energy_pools.csv`** (5 рядків, Додаток D.3): `code,name,sequence,driver,workcenters` (`workcenters` — коди через `;`,
порожньо — усі).

**`data/f3d_energy_tariff_data.xml`** (`noupdate="1"`): `tariff_demo` — `name="Умовний тариф (демо)"`,
`date_from="2026-01-01"`, `contract_kw=800`, `peak_warn_pct=90`, `export_price=0`, зона `tariff_demo_zone_flat`:
`name="Цілодобова"`, `code='flat'`, `weekdays="0123456"`, `hour_from=0`, `hour_to=24`, `price=8.4`
(`plant/energy.py:TARIFF`). Приклад двозонного тарифу — в інструкції ARCH §4.3, у даних не створюється.

**`data/f3d_energy_actions.xml`**: `action_f3d_energy_rebind` — `ir.actions.server`, `model_id=model_f3d_energy_node`,
`state='code'`, `code="action = env['f3d.energy.node'].action_f3d_energy_rebind()"`; метод `@api.model
action_f3d_energy_rebind(self)` M-01: без `group_f3d_admin` → `AccessError("Повтор прив'язки даних енергетики — лише
адміністратор.")`; `report = hooks.run_bind(self.env)`; `display_notification` «Прив'язку виконано: <JSON>», `sticky=True`.

### 5.3 `post_init_hook(env)` — кроки, ідемпотентність, очікувані кількості

`hooks.run_bind(env) -> dict` виконує кроки; `post_init_hook = run_bind + звіт`. Усе в транзакції установки; виняток на
кроці 1–7 відкочує установку. Логер `odoo.addons.factory3d_energy.hooks`, INFO на кожен крок.

| # | Функція | Джерело | Що робить | Ідемпотентність | Очікувано (копія демо 14.10) | Чиста база |
|---|---|---|---|---|---|---|
| 1 | `params(env)` | CB-10, `resource.calendar` | `read_enabled = (environment == 'test')`; `shift_calendar_id` | перезапис лише умовчань | `read_enabled=True`, `shift_calendar_id=2` | `True`, календар компанії |
| 2 | `derived_source(env)` | — | `f3d.source` `EN-DERIVED` (`type='f3d_energy'`, `module='energy'`, без колектора, `read_enabled` = п. 1), xml-id `factory3d_energy.source_en_derived` | upsert за `code` | `created: 1` | те саме |
| 3 | `pools(env)` | `energy_pools.csv` | `f3d.energy.pool` за `code` (без членів); `workcenter_ids` — `mrp.workcenter.search_f3d(code)`; немає РЦ → WARNING, лічильник `wc_missing` | upsert | `pools: 5`, `wc_missing: 0` | `pools: 5`, `wc_missing: 4` |
| 4 | `nodes(env)` | `energy_nodes.csv` | прохід 1: upsert за `code` усіх полів, крім `parent`, `cabinet`, `peer`; `equipment` → `maintenance.equipment.search_f3d(code)`; `workcenter` → `mrp.workcenter.search_f3d(code)`; `pool` → за `code`; прохід 2: `parent_id`, `cabinet_id`, `peer_id`; вузол з `alloc_role='direct'` без знайденого РЦ → `alloc_role='none'` + WARNING (`direct_without_wc`) | upsert | `nodes: 123`, `equipment_linked: 80`, `workcenter_linked: 35`, `critical: 10`, `unmatched_equipment: 0`, `direct_without_wc: 0` | `nodes: 123`, `equipment_linked: 0`, `unmatched_equipment: 80`, `direct_without_wc: 35` |
| 5 | `sources(env)` | `energy_sources.csv` | `f3d.source` `type='modbus_tcp'`, `collector_id = env.ref('factory3d_telemetry.collector_main')`, `params={host, port, unit, timeout_s, retries, max_block, gap_max}`, `module='energy'`, `equipment_id`, `read_enabled` = п. 1, `write_enabled=False`; xml-id `factory3d_energy.source_<slug>` (`slug` = код у нижньому регістрі з `-`→`_`) | upsert за `code` | `sources: 68` | `sources: 68` |
| 6 | `signals(env)` | `energy_signals.csv` | за `binding` (§5.2): `search([('code','=',code)], active_test=False)`; існує → `write` визначення (`kind`, `unit`, `equipment_id`, `source_id`, `address`, `period_s`, `store_period_s`, `decimals`, `states`, пороги з `*_on`, `alarm_states`, `alarm_title`, `hysteresis`, `min_duration_s`, `viewer_visible`, `module='energy'`, `active=True`; `last_*`, `status`, `origin` — не чіпаються); не існує → `create` з `origin` з CSV; другий прохід — `derived_from_id`; `energy/consumers/*/kwh_shift` → `source_id=EN-DERIVED`, `derived_from_id=…/kwh_total`, `derive_rule='none'` | upsert за `code` | `created: 210`, `updated: 87` (з них `thresholds: 2`), `module_energy: 297` | `created: 297`, `updated: 0` |
| 7 | `meters(env)` | `energy_meters.csv` | `f3d.energy.meter` за `code`: `node_id`, `source_id`, сигнали за кодами | upsert | `meters: 67` | `meters: 67` |
| 8 | `contract(env)` | тариф | `env['f3d.energy.tariff']._f3d_tariff_at(now)._f3d_apply_contract_thresholds()` (R-12 п. 1) | перезапис порогів | `grid15_kw`: `warn_high=720`, `alarm_high=800` | те саме |
| 9 | `report(env, report)` | — | `install_report = json.dumps({state, ts, …лічильники})`; `state='partial'`, якщо `unmatched_equipment > 0` або `direct_without_wc > 0`, інакше `done` | перезапис | `done` | `partial` |

Повторний запуск (`action_f3d_energy_rebind`) на тій самій базі: усі `created: 0`, кількості записів незмінні; інтервали,
розподіл, події — не чіпаються.

### 5.4 `uninstall_hook(env)`

1. Коди з `energy_signals.csv`: `f3d.signal` з цими кодами → `write({'source_id': False})`; з `origin in ('catalog',
   'module')` і створені хуком (xml-id `factory3d_energy.sig_<slug>`, ставиться при створенні) → `active=False`;
   мігровані рівня 0 (`origin='sim_data'`) лишаються активними. Значення `origin='module'` зникає з селекції —
   `ondelete='set default'` → `manual`.
2. `f3d.source` модуля (`module='energy'`) → `active=False`; `EN-DERIVED` видаляється з моделлю типу (`ondelete=cascade`
   на селекції — сигнали на ньому вже без джерела з п. 1).
3. `ir.config_parameter` `factory3d.energy.*` → `unlink`.
4. `mrp.production.extra_cost` закритих МО не змінюється; поля `f3d_energy_*` зникають з модулем; моделі `f3d.energy.*`
   видаляються стандартною деінсталяцією; аналітичні рядки (`account.analytic.line`) лишаються (бухгалтерські дані).

### 5.5 Повторна установка

Хук §5.3 на базі, де сигнали вже є з попередньої установки (`active=False`): `active_test=False` у пошуку → `updated`,
`active=True`; інтервали будуються заново з `f3d.reading` за `keep_days` telemetry (старші — втрачені разом із моделлю).

### 5.6 `data/neutralize.sql`

```sql
-- factory3d_energy: нейтралізація копії проду (каркас §5, CB-10)
UPDATE ir_config_parameter SET value = 'False'
 WHERE key IN ('factory3d.energy.read_enabled', 'factory3d.energy.write_enabled', 'factory3d.energy.costing_enabled');
UPDATE ir_cron c SET active = false FROM ir_model_data d
 WHERE d.model = 'ir.cron' AND d.res_id = c.id AND d.module = 'factory3d_energy';
UPDATE f3d_source SET read_enabled = false, state = 'disabled' WHERE module = 'energy';
```

## 6. Крони й фонові процеси (`data/ir_cron.xml`)

Усі крони: `user_id=base.user_root`, перевіряють `param_bool('factory3d.energy.read_enabled')` (крім ротації) і при
`False` завершуються без дій; кожен прогін — у `try/except` з `_logger.exception` і без підйому винятку (щоб не
блокувати планувальник), транзакційні межі — на рівні лічильника/доби (`self.env.cr.commit()` не викликається; ліміти
нижче тримають прогін коротким).

| XML-id | Назва | Інтервал | Модель / метод | Один прогін | Ліміти |
|---|---|---|---|---|---|
| `cron_f3d_energy_live` | Енергетика: живі показники | 1 хв | `f3d.energy.node._cron_live` | R-06 (тотали → 9 обчислених сигналів), R-12 п. 3–4 (асиметрія, cos φ), R-21 (стани лічильників), подія PFC (R-13 п. 4) | ≤ 5 с |
| `cron_f3d_energy_intervals` | Енергетика: 15-хвилинний профіль | 5 хв | `f3d.energy.interval._cron_build` | R-04 для 67 лічильників, потім R-11 (`kwh_shift`), R-15 (`load15_kw`, `grid15_kw`) | ≤ 2 доби слотів на лічильник за прогін; ≤ 30 с |
| `cron_f3d_energy_alloc` | Енергетика: розподіл на виробництво | 15 хв | `f3d.energy.alloc._cron_alloc` | R-08, R-09: доба сьогодні (до `now`); учора — якщо місцевий час < `alloc_close_h` або вчорашня доба ще не перерахована після 00:00 | ≤ 30 с |
| `cron_f3d_energy_balance` | Енергетика: баланс обліку | 1 год, `nextcall` — найближча хв 07 | `f3d.energy.balance._cron_balance` | R-07 для закритих годин за останні 48 год без запису або зі `skipped` молодше 6 год | ≤ 10 с |
| `cron_f3d_energy_rotate` | Енергетика: ротація | 1 доба, `nextcall` 03:10 Київ (хук через `zoneinfo`) | `f3d.energy.interval._cron_rotate` | R-19 | ≤ 60 с, батчі 50 000 |

## 7. HTTP/JSON API

HTTP-ендпоінтів модуль не має (усі показання — telemetry API-02 через колектор, обчислені — CT-10). Python-API для інших
модулів (CE-06, CE-08):

| ID | Сигнатура | Вхід → вихід | Помилки |
|---|---|---|---|
| API-01 | `env['f3d.energy.meter']._f3d_kwh(meter, date_from, date_to)` (метод запису: `meter._f3d_kwh(date_from, date_to)`) | `date_from < date_to` (UTC naive) → `(kwh: float, quality: str)` | `date_from ≥ date_to` → `ValueError("Порожній інтервал")`; без даних → `(0.0, 'missing')` |
| API-02 | `env['f3d.energy.node']._f3d_kwh_by_code(code, date_from, date_to)` | код вузла → те саме | невідомий код → `(0.0, 'missing')` |
| API-03 | `env['f3d.energy.event']._f3d_log(level, kind, code, text, ts=None, node=None, signal=None, outage=None, dedup_min=0)` | → запис або порожньо | `level`/`kind` поза селекцією → `ValueError` |
| API-04 | Провайдери `f3d.viewer.provider.energy`/`.infra` | контракт viewer M-01 | — |

## 8. Сервісна частина

Немає власного сервісу й плагінів. Колектор telemetry отримує 68 джерел енергетики з `GET /f3d/telemetry/config` (ETag):
після установки модуля колектор перечитує конфігурацію протягом `config_poll_s` (60 с) — перезапуск не потрібен.
Протокольні карти — Додаток A (PDU-адреси, типи, масштаб, джерело документа). Розмір конфігурації: 220 сигналів ≈ 110 КБ
(telemetry API-01: ≈ 500 КБ на 1 000 сигналів). Навантаження на стенд: PM5560 — 4 блоки на ввід, 3 на фідер, 2 на
споживача за цикл (групування telemetry R-20, `gap_max=8`): ≈ 160 запитів Modbus за 10 с на `iot-sim:502`.

## 9. Алгоритми й правила

### R-01 Адресація Modbus за вендором (A-06, CT-03)

Адреса сигналу — JSON telemetry Додаток A.1 (`fc`, `addr` — **PDU**, `type`, `scale`, `map`, `doc`); `unit` — у `params`
джерела. Правило перетворення номера з документа вендора в PDU:

| Пристрій | Документ | PDU | Порядок слів | Приклад |
|---|---|---|---|---|
| PM5560 (u1–8, u11–59) | Schneider «PM5560/PM5563 Modbus Register List», регістри 1-based | `N − 1` | `big` (старше слово першим) | P total 3060 → `{"fc":3,"addr":3059,"type":"f32","doc":"PM5560 3060 Active Power Total"}`; енергія 3204–3207 → `{"fc":3,"addr":3203,"type":"i64","scale":0.001,"doc":"PM5560 3204 Active Energy Delivered, Wh"}` |
| SUN2000 (u61–68) | Huawei «SUN2000MB Modbus Interface Definitions» — адреси вже PDU | `N` | `big` | 32080 → `{"fc":3,"addr":32080,"type":"i32","scale":0.001}` |
| LUNA2000 (u69) | iot_sim §8.9.2 (ПРИПУЩЕННЯ Huawei 37000-серії) | `N` | `big` | 37004 SOC → `{"fc":3,"addr":37004,"type":"u16","scale":0.1}` |
| ATyS p (u71) | Socomec «ATyS p Instruction manual 542 001 D», Annexe III (dec) | `N` | `big` | 20483 положення → `{"fc":3,"addr":20483,"type":"u16","map":{"0":"unknown","1":"pos_0","2":"pos_I","3":"pos_II"}}` |
| TEDOM (u72) | iot_sim §8.9.5 (ПРИПУЩЕННЯ) | `N` | `big` | 40001 P ел. → `{"fc":3,"addr":40001,"type":"u16"}` |

Декодування робить плагін telemetry (R-20 telemetry); приклади для тестів колектора й ТК-11: PM5560 3204–3207 =
`[0x0000, 0x0000, 0x0005, 0x5739]` → 350 009 Вт·год × 0,001 = **350,009 кВт·год**; 3060–3061 = `[0x4142, 0xE148]` →
**12,18 кВт**; SUN2000 32080–32081 = `[0x0000, 0x7EF4]` → 32 500 × 0,001 = **32,5 кВт**, `[0xFFFF, 0xFC18]` → **−1,0 кВт**;
LUNA 37001–37002 = `[0x0003, 0x0D40]` → 200 000 Вт × 0,001 = **200,0 кВт** (заряд); SUN2000 32106–32107 = `[0x0001, 0x86A0]`
→ 100 000 × 0,01 = **1 000,00 кВт·год**.

### R-02 Значення й знаки

1. Потужність PM5560 3060: знак за напрямком — на вводах `< 0` = віддача в мережу (iot_sim R-13); на фідерах і
   споживачах `< 0` не очікується (якщо прийшло — береться як є, у сумах споживачів — `max(0, P)`).
2. cos φ з PM5560 3084 (чотириквадрантний формат): `cos = |v|`, якщо `|v| ≤ 1`, інакше `2 − |v|` (`tools.live.pf_to_cos`);
   результат обмежено `[0, 1]`; `0` при `P ≈ 0` не використовується в розрахунках (береться `cos_phi_nominal`).
3. Енергія — кВт·год після `scale` адреси; у розрахунках округлення лише на виході: `kwh` 3 знаки, `cost` 2, `kw_avg` 2.
4. Сигнали `kind='state'`: `last_value` — індекс у `states` (telemetry A-06), `last_text` — текст. Для АВР `states`
   упорядковано так, що індекс = код Annexe III (A-07): `position` `["unknown","pos_0","pos_I","pos_II"]`,
   `src*_state` `["under","present","available"]`, `gen_start` `["off","on"]`; `mode` `["manual","locked","auto",
   "remote","inhibit"]` з `map {"0":"manual","1":"locked","16":"auto","32":"remote","64":"inhibit"}`.

### R-03 Безперервний лічильник `Ec(t)` (`tools/counter.py`, CE-06)

Вхід: точки `(t_i, v_i)` накопичувального сигналу (кВт·год), відсортовані за `t`, без `quality='bad'`;
`reset_tol` = параметр (1,0 кВт·год); `max_kw` = `f3d.energy.meter.max_kw` (поле M-02, з Додатка D.1: споживач
`ceil(2·p_inst_kw)` але ≥ 10; фідер 630 А → 437; C2 400 А → 278; ввід 1 600 А → 1 109; SUN2000 → 125; LUNA → 200;
TEDOM → 900); `gap_max_s` (900).

1. `c_0 = v_0 + base` (`base` = 0 для відносних рядів розподілу; = `counter_offset` лічильника для профілю R-04).
2. Для `i ≥ 1`: `d = v_i − v_{i−1}`; `dt_h = (t_i − t_{i−1})/3600`:
   - `d ≥ 0` → `c_i = c_{i−1} + d`, сегмент `ok`;
   - `−reset_tol ≤ d < 0` → `c_i = c_{i−1}` (шум/округлення), сегмент `ok`;
   - `d < −reset_tol` → **скидання**: якщо `0 ≤ v_i ≤ dt_h · max_kw` — лічильник почав з нуля, `c_i = c_{i−1} + v_i`;
     інакше (заміна лічильника з іншим показником) — `c_i = c_{i−1}`; сегмент `reset`; для профілю — нова поправка
     `counter_offset = c_i − v_i` записується на лічильник і подія R-13 «Лічильник <код>: скидання показника <v_{i−1}> →
     <v_i> кВт·год».
3. `Ec(t)`: `t = t_i` → `c_i`; `t_{i−1} < t < t_i` → лінійна інтерполяція; поза `[t_0, t_last]` → `None`. Якість точки:
   сегмент `reset` → `reset`; `t_i − t_{i−1} > gap_max_s` → `interpolated`; інакше `measured`.
4. `delta(a, b) = Ec(b) − Ec(a)` (≥ 0 за побудовою) з найгіршою якістю сегментів між `a` і `b` (порядок:
   `missing` > `reset` > `interpolated` > `measured`); будь-який `None` → `(None, 'missing')`.
5. Вибір ряду (M-02 `_f3d_counter_series`): показання `f3d.reading` у вікні `[a − 2 год, b + 2 год]` + (`last_ts`,
   `last_value`) сигналу; якщо перша точка пізніше `a` і вікно старше `keep_days` telemetry — ряд з інтервалів
   (`(ts_start, e_start)`, `(ts_end, e_end)`) лічильника (якість не краща за `interpolated`, якщо 15-хв межі не збігаються
   з `a`, `b`).

| Вхід | Вихід |
|---|---|
| точки (01:35:30, 999,890), (01:36:30, 1000,110), …, (02:54:30, 1017,270) з кроком 60 с і 13,2 кВт | `Ec(01:36:00) = 1000,000`, `Ec(02:54:00) = 1017,160`, `delta = 17,160`, `measured` |
| (10:00, 500,000), (10:40, 520,000) | `Ec(10:15) = 507,500` `interpolated`; `delta(10:00, 10:15) = 7,500` `interpolated` |
| `max_kw=48`: (10:00:00, 12 345,678), (10:01:00, 0,512) | скидання з нуля: `0,512 ≤ 48/60 = 0,8` → `c = 12 346,190`, `reset` |
| `max_kw=48`: (10:00:00, 12 345,678), (10:01:00, 2 000,000) | заміна: `c = 12 345,678` (0 кВт·год у сегменті), `reset` |
| (10:00, 100,000), (10:01, 99,600) | `−0,4 ≥ −1,0` → `c = 100,000`, `measured` |

### R-04 15-хвилинний профіль (`f3d.energy.interval._cron_build`, FR-04)

Для кожного активного лічильника `m` з `e_import_signal_id`:

1. Перший слот `s0` = `last_interval_start + 15 хв`; якщо інтервалів немає — `floor15(перша точка)`, але не раніше
   `now − 2 доби`. Останній слот `s1` — найпізніший з `ts_end ≤ now − settle_s`. Не більше 192 слотів за прогін.
2. Ряд R-03 з `base = counter_offset` на вікно `[s0 − 2 год, s1 + 15 хв]`.
3. Для кожного слоту `[a, b)`: `(e_a, q_a) = Ec(a)`, `(e_b, q_b) = Ec(b)`:
   - обидва визначені → `kwh = e_b − e_a`, `quality` = найгірша з R-03 п. 4;
   - `e_b` невизначений і `now − b < max_wait_h` → зупинитися (чекати даних), `last_interval_start` = попередній слот;
   - `e_b` невизначений і `now − b ≥ max_wait_h` → `kwh = 0`, `e_start = e_end = останнє відоме c`, `quality='missing'`.
4. Експорт: якщо `e_export_signal_id` — те саме з поправкою `counter_offset_export` → `kwh_export`.
5. `zone, price = tariff._f3d_price_at(a)` (R-05); `cost = round(kwh × price, 2)` для ролей `incomer` (лише імпорт),
   `feeder`, `consumer`; інші ролі — `cost = 0`; `kw_avg = round(kwh × 4, 2)`; `day`, `hour_local` — Київ (R-20).
6. Запис — `INSERT … ON CONFLICT (meter_id, ts_start) DO UPDATE SET e_start, e_end, kwh, kwh_export, kw_avg, zone_id,
   price, cost, quality, built_at`; `last_interval_start = a` останнього збудованого.
7. **Добудова пропусків**: після п. 6 — якщо в лічильника є слоти `missing` за останні 48 год, а в ряді з'явилась
   точка пізніше них — перебудувати вікно від першого такого слоту (п. 3 з новими точками: енергія пропуску
   розподіляється лінійно, `interpolated`).
8. Після всіх лічильників — R-11, R-15, `_notify('f3d.energy', ['energy'], 'signal')` (R-18).

Приклад (PM-SAW-1, тариф демо): `Ec(01:30) = 998,808`, `Ec(01:45) = 1001,980` → `kwh = 3,172`, `kw_avg = 12,69`, зона
«Цілодобова», `price = 8,40`, `cost = 26,64`, `measured`. Лічильник мовчав 10:00–10:40, далі є точка (10:40, 520,000):
слоти 10:00, 10:15 будуть `interpolated` з 7,5 кВт·год кожен, слот 10:30 — 5,0 (10:30–10:40) + частина після 10:40.

### R-05 Зона й ціна тарифу (`tools/tariff.py`, FR-05)

1. Тариф: активний тариф компанії з `date_from ≤ local_date(t) ≤ date_to` (`date_to` порожня = ∞); немає → `zone=None`,
   `price=0`, подія `warn` «Немає чинного тарифу на <дата>» (раз на добу, `dedup_min=1440`).
2. Зона: `local = to_local(t)`, `wd = local.weekday()` (0 — пн), `h = local.hour + local.minute/60`; зона `z`
   відповідає, якщо `str(wd) in z.weekdays` і (`z.hour_from ≤ h < z.hour_to`, коли `hour_from < hour_to`; або
   `h ≥ hour_from or h < hour_to`, коли `hour_to < hour_from`). Перша за `sequence`.
3. Перевірка покриття (`_check_coverage`): для `wd ∈ 0…6`, `k ∈ 0…95`, `h = k/4` — рівно одна зона.
4. Ціна слоту — за його початком.

| Тариф | Слот (Київ) | Зона / ціна |
|---|---|---|
| демо (одна зона 0–24, 8,40) | будь-який | «Цілодобова», 8,40 |
| «День» 07–23 9,60; «Ніч» 23–07 4,80 (усі дні) | 22:45 / 23:00 / 06:45 / 07:00 | День 9,60 / Ніч 4,80 / Ніч 4,80 / День 9,60 |
| той самий без зони на неділю (`weekdays="012345"`) | неділя 10:00 | `ValidationError` при збереженні: «Зони тарифу «…»: нд о 00:00 не покрито» |

### R-06 Живі показники (`tools/live.py`, `cron_f3d_energy_live`, FR-06, CE-03, CE-04)

Входи — `last_value` сигналів зі `status ∉ {'stale','unknown'}` і `last_quality != 'bad'` (далі «свіжі»).

1. Лінія `L`: `P_L = energy/lines/L/p_now`, `cos_L = pf_to_cos(energy/lines/L/cos_phi)` (несвіжий → `cos_phi_nominal`
   вузла, 0,9), `Q_L = P_L · tan(acos cos_L)`, `I_L = energy/lines/L/i_now`, `load_L = I_L / rating_a`.
2. Секція `s` (лінії, чиї шафи мають `section = s`): `P_s = Σ P_L`, `Q_s = Σ Q_L`, `cos_before_s = P_s / hypot(P_s, Q_s)`;
   компенсація: якщо свіжий `energy/cells/Q_s/q_kvar` — `q_pfc_s = clamp(Q_s − q_kvar_s, 0, rating_kvar)`; інакше
   теоретична `q_pfc_s = clamp(Q_s − P_s·tan(acos 0,97), 0, 350)`; `PFC q_now = min(350, round(q_pfc_s/50)·50)`;
   `S_s = hypot(P_s, Q_s − q_pfc_s)`, `cos_after_s = P_s / S_s`.
3. Тотали: `p_now = Σ P_s`; `s_now = hypot(Σ P_s, Σ (Q_s − q_pfc_s))`; `cos_before = Σ P / hypot(Σ P, Σ Q)`;
   `cos_after = Σ P / s_now`; `p_inst = Σ p_inst_kw` споживачів (1 201); `capacity_kva = Σ rating_kva` трансформаторів (2 000).
4. Трансформатор `T`: `p_kw`, `s_kva`, `i_a`, `temp_c`, `cos_phi = pf_to_cos(...)` — з сигналів `energy/transformers/T/*`;
   несвіжий `s_kva` → `S_s` п. 2; `load = s_kva / rating_kva`.
5. Генерація: `pv_now = Σ max(0, infra/pv/PV-INV-k/p_kw)` свіжих; `pv_today = Σ infra/pv/PV-INV-k/kwh_today`; `chp_kw`,
   `bess_kw` (+ заряд), `bess_soc` — сигнали; `bess_mode` = `charge` (> 1 кВт) / `discharge` (< −1) / `idle`.
6. Мережа: `grid_net = P_Q1 + P_Q2` (`energy/cells/Q*/p_now`); `grid_kw = max(0, grid_net)`, `export_kw = max(0, −grid_net)`;
   в острові (R-14) — обидва 0.
7. Критичні (CE-04): `critical_kw = Σ p_now` вузлів `is_critical` (споживачі — `energy/consumers/<код>/p_now`, лінія
   BW-1 — `energy/lines/BW-1/p_now`).
8. Запис обчислених (CT-10, `src='module'`, контекст `f3d_energy_internal`, `ts = floor_minute(now)`):
   `energy/totals/p_now`, `energy/totals/cos_phi` (= `cos_after`), `infra/totals/pv_now`, `infra/totals/grid_kw`,
   `infra/totals/export_kw`; поле вузла PFC `pfc_q_now` (Integer, readonly, M-01) — для подій R-13 п. 4. Якщо
   несвіжих фідерів > 2 або обидва вводи несвіжі — тотали не пишуться (R-21 п. 4).

Приклад (макет 12.10, 10:30; фідери з `plant/energy.py`): секція 1 — BW-3 70,1 / 0,92, BW-2 80,5 / 0,88, C1 184,1 / 0,90 →
`P_1 = 334,7`, `Q_1 = 162,5`, `cos_before_1 = 0,90`, `q_pfc_1 = 78,6` → **PFC-1 100 квар**, `S_1 = 345,1`, `cos_after_1 = 0,97`;
секція 2 — BW-1 106,9 / 0,89, BW-4 26,4 / 0,92, C2 158,0 / 0,95 → `P_2 = 291,3`, `Q_2 = 117,9`, `cos_before_2 = 0,93`,
`q_pfc_2 = 44,9` → **PFC-2 50 квар**, `S_2 = 300,3`; тотали `p_now = 626`, `s_now = 645`, `cos_before = 0,91`,
`cos_after = 0,97` (= `dist/odoo_demo.json:energy.totals`); `I_BW-1 = 173 А` (макет 174 — округлення cos лінії до 2 знаків).
Генерація: `pv_now = 468`, `chp_kw = 400`, `bess_kw = +200`; вводи: `P_Q1 = 334,7`, `P_Q2 = 291,3 − 468 − 400 + 200 =
−376,7` → `grid_net = −42,0` → **`grid_kw = 0`, `export_kw = 42`**; критичні **347,8 → 348**.

### R-07 Баланс обліку (`f3d.energy.balance._cron_balance`, FR-07)

Для кожної закритої години `H` (UTC, `[H, H + 1 год)`) і вузла:

| Вузол | Виміряно | Очікувано |
|---|---|---|
| лінія `L` (шафа QF-x) | Σ `kwh` лічильника шафи за 4 слоти | Σ `kwh` лічильників споживачів-нащадків лінії |
| `Q1` | Σ (`kwh − kwh_export`) PM-Q1 | Σ `kwh` фідерів секції 1 (QF-3, QF-2, QF-C1) |
| `Q2` | Σ (`kwh − kwh_export`) PM-Q2 | Σ `kwh` фідерів секції 2 (QF-1, QF-4, QF-C2) − Σ `kwh` SUN-1…8 − `kwh` TEDOM-1 + `kwh` LUNA-1 (заряд) − `kwh_export` LUNA-1 (розряд) |

1. `skipped`: будь-який вхідний слот `missing` (`reason` = «немає даних: PM-SAW-1 (2 інтервали)»); година перетинає
   відкрите або закрите відключення (`reason` = «відключення мережі»).
2. `diff = measured − expected`; `pct = |diff| / max(|measured|, |expected|) · 100` (обидва 0 → 0);
   `deviation`, якщо `pct > balance_tol_pct` **і** `|diff| > balance_tol_kwh`; інакше `ok`.
3. Запис `f3d.energy.balance` (upsert за `(node_id, hour)`); для не-`skipped` — показання обчисленого сигналу
   `<energy/lines/L|energy/cells/Q*>/imbalance_pct = pct` з `ts = H + 1 год` (пороги: `warn_high=3`, `alarm_high=5`,
   `min_duration_s=3600` → заявка «Небаланс обліку {code}: {value} % при допуску {threshold}» на другу годину поспіль).
4. `deviation` → подія `warn` «Небаланс обліку BW-1: 3,26 % (110,5 проти 106,9 кВт·год за 10:00–11:00)» (`dedup_min=60`).

| Вхід (за годину) | Вихід |
|---|---|
| Q1 334,7; фідери секції 1 70,1 + 80,5 + 184,1 | `diff 0`, `ok` |
| Q2 −376,7; секція 2 291,3, СЕС 468, КГУ 400, заряд 200 | `expected −376,7`, `ok` |
| BW-1 110,5; споживачі лінії 106,9 | `diff 3,6`, `pct 3,26`, **`deviation`** |
| BW-1 109,0; 106,9 | `pct 1,93`, `ok` |
| C1 вночі 1,5; 0,2 | `diff 1,3 ≤ 2,0` → `ok` |

### R-08 Пряма енергія завдання (`tools/alloc.py`, FR-08, A-05)

Для доби `D` (Київ): `d0, d1` = межі доби в UTC; `end = min(d1, now)`.

1. Кандидати: `mrp.workorder` з `time_ids` (журнал часу), що перетинають `[d0, end)`, або `state='progress'`, або
   `date_finished ≥ d0`.
2. Інтервали роботи: для РЦ з активним `f3d.machine` (`'f3d.machine' in env` і `search_count([('workcenter_id','=',wc),
   ('active','=',True)])`) — `env['f3d.machine']._f3d_wo_intervals(wos_rc, d0, end)` (CM-03: стани `working`, `setup`,
   UTC naive, відкритий — до `now`); для решти РЦ — `mrp.workcenter.productivity` з `workorder_id`, `[date_start,
   date_end or now] ∩ [d0, end)`, стан `working` для `loss_type in ('productive','performance')`, інакше `setup`.
3. Для кожного РЦ — елементарні сегменти між усіма межами інтервалів його завдань; у сегменті `[x, y)` з множиною
   активних завдань `A`: `(E, q) = series_rc.delta(x, y)` (R-03, ряд лічильника вузла РЦ); кожне `wo ∈ A` отримує
   `E / |A|` кВт·год і `(y − x)/60` хв (хвилини не діляться — це час роботи завдання).
4. Запасна оцінка: вузол РЦ без лічильника, без сигналу енергії або `E = None` → `E = p_inst_kw × load_factor ×
   (y − x)/3600` (формула `plant/odoo_demo.py:build_energy`), `q='estimate'`.
5. Простій РЦ: `idle = series_rc.delta(d0, end) − Σ прямих виміряних кВт·год РЦ за добу` (≥ 0) → рядок `idle`.
6. Якість рядка завдання за добу: усі сегменти `measured` → `measured`; є `interpolated`/`reset` → `interpolated`;
   усі `estimate` → `estimate`; суміш виміряного й оцінки → `partial`.
7. Вартість: для кожного сегмента — `E × price(зона початку сегмента)`; рядок — Σ, округлення 2.

Приклади: `WH/MO/00231` у режимі оцінки (лічильників ще немає, журнал часу макета): SAW-1 24 × 0,55 × 78/60 = **17,160**;
EDGE-1 67,5 × 0,65 × 63/60 = **46,069**; CNC-1 22 × 0,5 × 74/60 = **13,567**; SORT-1 20 × 0,45 × 29/60 = **4,350**;
ASMLINE-1 8 × 0,4 × 95/60 = **5,067**; разом **86,213 кВт·год**, вартість 144,14 + 386,98 + 113,96 + 36,54 + 42,56 =
**724,18 грн** (переглядач: 86,2 кВт·год, 724 грн). Виміряно: ряд PM-SAW-1 R-03 рядок 1 → WO00001 = 17,160 `measured`.
machine_connect: WO00013 → `[(06:55:00, 07:25:48, working)]`, `p_now ≈ 12,18` → ≈ **6,25 кВт·год** (R-28 machine_connect).
Два завдання на одному РЦ 10:00–10:20 одночасно, лічильник +4,0 → по **2,0** кВт·год і 20 хв кожному.

### R-09 Спільні пули, простій, накладні (`tools/alloc.py`, FR-09, Q-01)

Для доби `D`, для кожного слоту `w = [a, b)` 15-хв сітки ∩ `[d0, end)`:

1. `pool_kwh(p, w) = Σ` `delta(a, b)` лічильників вузлів-членів пулу `p` (член без даних пропускається; усі без даних —
   слот пулу пропускається).
2. Претенденти: завдання, активні в `w` (інтервал R-08 п. 2 перетинає `w`), на РЦ з `p.workcenter_ids` (порожньо —
   усі РЦ із прямим вузлом).
3. Драйвер: `kwh` → `D_wo` = прямі кВт·год завдання в `w` (з R-08 п. 3–4, включно з оцінкою); `time` → хвилини
   завдання в `w`.
4. `ΣD > 0` → частка `pool_kwh × D_wo / ΣD`; вартість `× price(a)`.
5. Агрегація за добу: рядки `shared` (`workorder_id`, `pool_id`), `minutes` — хвилини завдання в слотах пулу.
6. Нерозподілене: `unallocated(p, D) = Σ_w pool_kwh(p, w) − Σ shared(p, D)` (усі рядки пулу, включно зі
   зафіксованими) — рядок `unallocated`; архівований пул — уся його енергія в `unallocated`.
7. Накладні: вузли `alloc_role='overhead'` — рядок `overhead` з `delta(d0, end)` лічильника вузла за добу.
8. Перерахунок доби (`_f3d_alloc_days`): обчислити всі рядки доби в пам'яті; для кожного ключа (M-07): є незафіксований
   рядок → `write`, немає → `create`; незафіксовані рядки доби, яких немає в новому наборі, → `unlink`; зафіксовані
   (`locked`) — не змінюються й не видаляються, але їхні завдання беруть участь у знаменнику п. 4.

| Вхід | Вихід |
|---|---|
| слот 02:45–03:00 UTC, `POOL-DUST` (`kwh`): DUST-1 127,5 кВт → 31,875 кВт·год; SAW-1 (WO00001) 02:45–02:54 прямих 1,980; EDGE-1 (WO00002) 02:48–03:00 прямих 8,775 | SAW-1 **5,868** кВт·год / 49,29 грн; EDGE-1 **26,007** / 218,46 |
| той самий слот, `POOL-LIGHT` (`time`): LP-2 23,2 кВт → 5,800; хвилини 9 і 12 | SAW-1 **2,486**; EDGE-1 **3,314** |
| слот 00:00–00:15 UTC (ніч), DUST-1 2,0 кВт·год, завдань немає | `unallocated` +2,0 |
| BOILER за добу 240,0 кВт·год | `overhead` 240,0 |

### R-10 Енергія в собівартість МО (`mrp.production`, FR-10, A-10, A-11)

1. Поля МО/завдань (M-11, M-12) оновлюються з рядків розподілу (кроном R-09 і `_f3d_energy_finalize`).
2. **Фіксація** (`_cal_price` → `_f3d_energy_finalize`): перерахунок діб від першої хвилини інтервалів завдань МО до
   `now` (R-09 п. 8) → усі рядки `direct`/`shared` завдань МО `locked=True`, `f3d_energy_locked=True`, чаттер МО.
3. `_f3d_energy_apply_extra_cost`: якщо `costing_enabled` і `product_id.cost_method in ('fifo', 'average')` і
   `qty > 0` (кількість у одиниці товару: `product_uom_id._compute_quantity(qty_producing, product_id.uom_id)`) і
   `f3d_energy_applied_unit == 0`: `unit = round(f3d_energy_cost / qty, 4)`; `extra_cost += unit`;
   `f3d_energy_applied_unit = unit`; чаттер «До Extra Unit Cost додано енергію: 27,8531 грн/од. (724,18 грн / 26 шт).»
   Далі стандартний `_cal_price` Odoo 19 множить `extra_cost` на кількість і додає до `total_cost` готового руху.
4. Метод `standard`: `extra_cost` не змінюється (стандарт Odoo 19 бере `standard_price`), чаттер «Енергію не внесено у
   вартість: метод «Стандартна ціна» (Q-06). Енергія МО: 86,2 кВт·год, 724,18 грн.» `costing_enabled=False` → без змін
   і без повідомлення про вартість.
5. Аналітика: якщо `analytic_enabled` і `workcenter_id.analytic_distribution` — для кожного рядка `direct`/`shared`
   МО без `analytic_line_ids`: `vals = env['account.analytic.account']._perform_analytic_distribution(
   wc.analytic_distribution, -row.cost, row.kwh, row.analytic_line_ids, row)`; `row.analytic_line_ids += create(vals)`
   (назва «[EN] <завдання>», одиниця кВт·год, `category='manufacturing_order'`).
6. Дозамовлення: `_get_backorder_mo_vals` віднімає `f3d_energy_applied_unit` з `extra_cost` (енергія не переходить).
7. Повторне закриття (Odoo викликає `_cal_price` для кожного готового руху / backorder) — `f3d_energy_applied_unit ≠ 0`
   → крок 3 пропускається; `f3d_energy_locked` → крок 2 пропускається.

Приклад: `WH/MO/00231` (26 шт `KC-B600`), оцінка R-08: `f3d_energy_kwh = 86,213`, `f3d_energy_cost = 724,18`,
`f3d_energy_unit_cost = 27,8531`; для AVCO-категорії `extra_cost` 0 → 27,8531, у вартість готової продукції +724,18 грн;
на демо (`standard`) `extra_cost = 0`, чаттер про Q-06.

### R-11 `kwh_shift` (FR-11, A-20)

`shift_start(now)`: календар `shift_calendar_id`; для місцевої дати `now` — мінімальний `hour_from` атендансів дня
тижня; якщо `now_local` раніше нього або атендансів немає — попередній день з атендансами (≤ 7 діб назад; немає —
місцева північ). `kwh_shift = series.delta(shift_start, last_ts)` лічильника вузла (R-03, `base=0`), округлення 2;
показання `energy/consumers/<код>/kwh_shift` з `ts = last_ts` сигналу `kwh_total` (CT-10), кожен прогін R-04.
Приклад: зміна 07:00 Київ (04:00 UTC), `now` 10:30; PM-SAW-1 `Ec(04:00) = 1003,300`, `Ec(07:30) = 1053,800` → **50,50**
(макет `kwh_shift` SAW-1 = 50,5). О 06:30 Київ — від учорашніх 07:00.

### R-12 Обчислені сигнали з порогами (FR-12, A-13)

1. Договірна потужність: `grid15_kw` — `warn_high = contract_kw × peak_warn_pct/100`, `alarm_high = contract_kw`,
   `warn_high_on = alarm_high_on = True`, `min_duration_s = 0`, `alarm_title = "Перевищення договірної потужності: {value}
   кВт при ліміті {threshold} кВт"`, обладнання `SWB-1`. Приклад: 800 → 720 / 800; `grid15 = 812,4` → заявка
   «Перевищення договірної потужності: 812,4 кВт при ліміті 800 кВт».
2. Статичні пороги — з Додатка C (колонка «Пороги»): фідери `i_now` — 0,9·номінал / номінал (BW, C1: 567 / 630; C2:
   360 / 400), вводи 1 440 / 1 600 А, трансформатори `s_kva` 900 / 1 000 кВА, `temp_c` 100 / 110 °C (`hysteresis=2`,
   `min_duration_s=60`), cos φ ліній `warn_low=0,85`, cos φ на вводах `energy/totals/cos_phi` 0,95 / 0,90
   (`min_duration_s=900`), асиметрія 10 / 20 % (`min_duration_s=900`), небаланс 3 / 5 % (`min_duration_s=3600`), стани
   (`alarm_states`: `tripped`, `fault`), мотогодини КГУ 76 000 / 80 000, `fail_start` `alarm_high=0,5`.
3. Асиметрія струмів (`cron_f3d_energy_live`, кожні 5 хв — коли `minute % 5 == 0`): для 8 шаф з фазними струмами
   (Q1, Q2, QF-1…4, QF-C1/C2): `I_avg = (I_a + I_b + I_c)/3`; `I_avg < max(5 А, 0,02·rating_a)` → не рахувати;
   `unbal = max|I_k − I_avg| / I_avg × 100` → `…/i_unbal_pct`. Приклади: 171 / 180 / 168 → **4,05 %**; 140 / 180 / 150 →
   **14,89 %** (`warn`).
4. cos φ на вводах — R-06 п. 8.
5. Заголовки заявок: `alarm_title` з Додатка C; рендер і створення — telemetry R-05 (дедуплікація на сигнал).

### R-13 Журнал подій (`f3d.energy.event`, FR-13)

1. Зміна `status` сигналу `module='energy'` (порівняння `before`/`after` у M-15): `→ warn` — `warn`, `→ alarm` — `bad`,
   `→ ok` з `warn/alarm` — `info`; текст: для `alarm`/`warn` — рендер `alarm_title` (telemetry `tools.titles.render_title`)
   або «{name}: {value} {unit}»; для повернення — «{name}: повернувся в норму ({value} {unit})». `stale`/`unknown` — подій
   немає (їх веде R-21).
2. Стан верстата `workcenters/<РЦ>/machine_state` (machine_connect CM-02) став `fault` → `bad` «<РЦ>: аварійна зупинка,
   споживання впало до <p_now> кВт.» (`p_now` споживача, 1 знак, кома) — як подія макета `CNC-2`.
3. Пік доби: перший прогін R-04 після місцевої півночі пише подію за вчора: «Пік 15-хвилинної потужності за 12.10:
   654 кВт о 09:15; ліміт договірної потужності (800 кВт) не перевищено.» — `info`, якщо пік ≤ `warn_high`, `warn` — якщо
   вище, з «… перевищено на N кВт» якщо > `contract_kw`; `code='SWB-1'`.
4. Компенсація: `pfc_q_now` вузла PFC змінився (R-06 п. 8) → `info` «Компенсація секції 2: увімкнено ще один ступінь
   50 квар, cos φ 0,97.» / «вимкнено ступінь 50 квар» / «увімкнено 2 ступені (100 квар)», `dedup_min=10`.
5. Баланс (R-07 п. 4), лічильники (R-03, R-21), АВР і відключення (R-14).
6. Кожна подія → `_notify('f3d.energy', [code], 'signal')`.

### R-14 АВР, відключення, острів (`tools/ats.py`, FR-14, FR-15, CE-02, CE-03, A-07, A-14)

Свіжість сигналу АВР: `status ≠ stale` і `now − last_ts ≤ ats_fresh_factor × period_s` (3 × 5 = 15 с).

1. Похідні (у M-15 після `super()`): у пакеті є `infra/ats/src1_state` → `_f3d_ingest([{code: infra/ats/src1_ok, ts: ts
   пакета, value: 1 якщо text == 'available' інакше 0}])`; те саме для `src2`.
2. `grid_ok`: `src1_state` свіжий → `== 'available'`; інакше `position` свіжий → `== 2`; інакше за вводами: обидва
   `energy/cells/Q*/p_now` і `i_now` свіжі й `|P| < 1 кВт`, `I < 1 А` → `False`; інакше `True`.
3. `island` = `position` свіжий і `== 3`.
4. Відкриття (`grid_ok` став `False`, відкритого немає): `f3d.energy.outage` (`ts_start` = `ts` показання, `source` =
   `ats`/`incomers`, `amf_master` за `mode`: `remote` → `hgm`, `auto` → `ats`, інше → `unknown`; `load_before_kw` =
   `energy/totals/p_now.last_value`; `critical_kw` R-06 п. 7); подія `bad` «Зникла напруга мережі (ввід 10 кВ). Режим
   АВР: <мітка>.».
5. FAIL START (варіант B, `mode='auto'`): відкрите відключення, `gen_start='on'` (момент — `gen_start_at`, поле M-10)
   і `src2_state ≠ 'available'` довше `ats_fail_start_s` → `infra/ats/fail_start = 1` (заявка CT-05 на ATS-1 «АВР:
   генератор не запустився (FAIL START)»), `fail_start=True`, подія `bad` «АВР: генератор не запустився за 35 с (FAIL
   START).»; `src2` став `available` або `gen_start='off'` → `fail_start = 0`. У варіанті A (`mode='remote'`, пуск
   веде HGM6120N) реле 20484 не задіяне — FAIL START визначає `td_genset`.
6. Переключення: `position` став 3 при відкритому відключенні → `transfer_s = ts − ts_start`, `gen_started=True`,
   подія `info` «АВР: переключено на генератор за 14 с.».
7. Мережа повернулась (`grid_ok` став `True`) → `grid_back_at` (поле M-10); `position` став 2 (або АВР несвіжий і
   `grid_ok`) → закрити: `ts_end`, `return_s = ts − grid_back_at`, `state='closed'`, подія `info` «Мережу відновлено,
   АВР повернув живлення від мережі через 60 с; відключення тривало 10 хв.».
8. Під час відкритого — крон R-06 оновлює `load_island_kw = energy/totals/p_now`, `shed_kw = max(shed_kw, load_before −
   load_island)`.
9. Тотали в острові (провайдер `infra`, CE-03): `grid_kw=0`, `export_kw=0`, `pv_now`, `chp_kw`, `bess_kw` — виміряні (СЕС
   при блекауті дає `0x0303` → 0), `load_kw` = Σ фідерів, `shed_kw = max(0, load_before − load_kw)`, `bess_mode`.
   Ключі `island`, `grid_ok`, `genset_*` не пишуться (CE-01).
10. Узгодженість з мостом: параметр `factory3d.genset.amf_master` існує і не відповідає `mode` (`hgm`↔`remote`,
    `ats`↔`auto`) → подія `warn` раз на добу «Режим АВР «<мітка>» не відповідає налаштуванню моста генератора
    «<hgm|ats>».».

Приклад (S-03 `blackout`, варіант A): 10:05:00 `src1_state=under` → `src1_ok=0`, відключення відкрито, `load_before 626`,
`critical 348`; 10:05:14 `position=3` → `transfer_s 14`; критичні 348 кВт → `load_kw 348`, `shed_kw 278`, у момент
пуску `bess_kw −200` → `bess_mode='discharge'`; 10:15:00 `src1_state=available` → `grid_back_at`; 10:16:00 `position=2`
→ `return_s 60`, `duration_min 11,0`.

### R-15 Профіль доби, пік, типовий день (FR-28)

1. `profile[h]` (h — місцева година 0…23 сьогодні) = Σ `kwh` інтервалів лічильників ролі `feeder` з `hour_local = h`
   за сьогодні + для поточної години — Σ `delta(початок поточного слоту, now)` фідерів; ціле; години після поточної —
   `None`.
2. `kwh_today` = Σ закритих інтервалів фідерів сьогодні + частковий поточний слот; `cost_today` = Σ їхніх `cost` +
   частковий × поточна ціна; цілі.
3. `load15_kw(w) = Σ kwh фідерів у слоті × 4` → сигнал `energy/totals/load15_kw` (`ts` = кінець слоту); `peak_kw` =
   max за сьогодні (ціле), `peak_time` = місцевий початок слоту `"HH:MM"`.
4. `grid15_kw(w) = max(0, Σ (kwh − kwh_export) PM-Q1, PM-Q2 у слоті) × 4` → сигнал (R-12 п. 1).
5. `typical[h]` — середнє `profile` за останні `typical_days` робочих днів (пн–пт, ≥ 90 % слотів фідерів не `missing`);
   менше 3 таких днів → `typical` статики (`payload['energy']['typical']`) без змін.

Приклад (макет): `kwh_today = 2 867`, `cost_today = 24 083` (2 867 × 8,4), `peak_kw = 654`, `peak_time = "09:15"`.

### R-16 Розділ `energy` переглядача (`tools/payload.build_energy`, FR-16, CE-08)

Один `search_read` сигналів зони (`module='energy'`, свіжість R-06), вузлів, лічильників; один `read_group`
інтервалів доби. Структура — viewer A.12 (ключі й типи), значення:

1. `meta`: `source` «Лічильники PowerLogic PM5560 на вводах, фідерах і споживачах → Modbus TCP → колектор → Odoo
   (factory3d_energy)», `u_kv` «10 / 0,4», `tariff_uah` — ціна поточної зони (8.4), `note` — як макет + «Енергія на МО —
   за лічильниками; «оцінка» — за паспортом і журналом часу.».
2. `totals`: `p_inst`, `p_now` (ціле), `s_now`, `cos_before`, `cos_after` (R-06), `kwh_today`, `peak_kw`, `peak_time`,
   `cost_today` (лише `group_energy_cost` і не кіоск), `capacity_kva`, `pv_kw` (= `pv_now`), `grid_kw`, `pv_today`,
   `chp_kw`, `export_kw`, `bess_kw` (R-06), новий `contract_kw` (опційний ключ).
3. `transformers` T1/T2: `name`, `rating_kva`, `section`, `p_kw` (1 знак), `s_kva` (ціле), `load` (3 знаки), `i_a`
   (ціле), `temp_c` (1 знак), `cos_phi` (2 знаки), `incomer` (`Q1`/`Q2`).
4. `cells` — 11 шаф за `sequence`: `name`, `type` (= `cell_type`), `section` (`null` для QS), `feeds` (incomer — код
   трансформатора-батька; feeder/cable — код лінії; інакше `null`); incomer: `i_now`, `p_now`, `rating_a`, `state`
   (`closed`→`"on"`, `open`→`"off"`, `tripped`→`"tripped"`, немає сигналу → `"on"`); coupler: `rating_a`, `state` `"off"`,
   `note` «Розімкнений: секції живляться кожна від свого трансформатора. АВР замкне його, якщо зникне напруга на одному з
   вводів.»; pfc: `rating_kvar`, `q_now` (R-06), `steps` «50 + 3 × 100 квар», `cos_before`, `cos_after` секції;
   feeder/cable: `line`, `i_now`, `p_now`, `rating_a`, `state`.
5. `lines` — 6: `kind` (`busway`/`cable` — як макет), `name`, `cell`, `rating_a`, `consumers` (коди), `p_inst`, `p_now`,
   `cos_phi`, `i_now`, `load`.
6. `consumers` — 49: `name`, `feeder` (код шафи), `bus` (код шинопроводу або `null`), `p_inst`, `p_now` (округлення
   telemetry R-12: 2 знаки при `< 20`, інакше 1), `cos_phi` (номінал), `source`, `status`, `i_now = round(P·1000/(√3·400·cos))`,
   `line`, `kwh_shift` (сигнал), `note`, `group` (якщо задані). `status`: РЦ — `workcenters/<код>/machine_state`
   (`working|setup` → `work`, `fault` → `stop`, інше → `idle`), без machine_connect — `working_state == 'blocked'` →
   `stop`, є завдання `progress` → `work`, інакше `idle`; інші — `p_now ≥ 0,05·p_inst` → `work`, інакше `idle`.
7. `profile`, `typical` (R-15), `events` — 6 останніх `f3d.energy.event` (`time` місцевий `"YYYY-MM-DD HH:MM"`, `level`,
   `code`, `text`).
8. `workcenters[<код>].energy = {"p_now", "line"}` для РЦ, що є в payload; `productions[]`: за `name` МО з ORM
   (`search_read` полів `name`, `f3d_energy_kwh`, `f3d_energy_cost`, `f3d_energy_state`) — `energy_kwh = round(kwh, 1)`,
   `energy_cost = round(cost)` (лише з `group_energy_cost` і не кіоск — інакше ключ видаляється), `energy_quality` =
   `f3d_energy_state`.
9. Сигнали без свіжих даних — ключ лишається зі значенням статики (не `null`).

### R-17 Розділ `infra` (`tools/payload.build_infra`, FR-17, CE-01, CE-03)

`payload.setdefault("infra", {})`; `cards` — лише 5 кодів (рядки — як `plant/infra.py`, числа живі, формат `_fmt`:
пробіл тисяч, кома десяткова):

| Картка | Рядки |
|---|---|
| `PV-ROOF` | «Модулів» `"<n> × <wp> Вт"`, де `wp = equipment_id.f3d_get_num('wp')` (580), `n = round(p_inst_kw · 1000 / wp)` вузла `PV-ROOF` (900 000 / 580 → **1552**); «Потужність» `"900 кВт пік"` (`p_inst_kw`); «Зараз» `"<pv_now> кВт"`; «Сьогодні» `"<pv_today> кВт·год"`; «Частка СЕС зараз» `"<round(pv/load·100)> % споживання"`; `note` — текст макета |
| `PV-INV` | «Інверторів» `"8 × 115 кВт"`; «Навантаження» `"<round(pv_now/920·100)> %"`; «Стан» — `"усі в мережі"`, якщо всі 8 `status ∈ {on_grid, limited}`, інакше `"в мережі N з 8; PV-INV-3: аварія"` (перелік не-`on_grid` з текстом стану); `warn` — є `fault` |
| `CHP` | «Потужність» `"800 кВт ел. · 856 кВт тепла"`; «Зараз» `"<chp_kw> кВт ел. · <heat_kw> кВт тепла (<round(chp/800·100)> %)"`; «Тепло» — якщо в payload є `ventilation.totals.heat_kw`: `"мережі потрібно N кВт, надлишок M кВт — у сухий охолоджувач"`; «Газ» `"<gas_m3h> м³/год (при 100 % — 199)"`; «ККД» `"42,5 % ел. + 45,5 % тепл."` (паспорт); «Мотогодини» `"<hours> · до капремонту 80 000"`; `warn` — `state == 'fault'` |
| `ATS-1` | «Положення» (`pos_I` «Мережа (T1/T2)», `pos_II` «Генератор», `pos_0` «0 — обидва джерела вимкнені», інакше «невідомо»); «Режим» (`auto` «Авто», `remote` «Дистанційне (HGM6120N)», `manual` «Ручний», `locked` «Блоковано», `inhibit` «Заборонено»); «Номінал» `"1600 А"`; «Переключення» — `"<transfer_s> с при останньому відключенні"` або макет `"після пуску генератора, 10–15 с"`; «Останнє спрацювання» — останнє `f3d.energy.outage`: `"<dd.mm, HH:MM> — відключення мережі <тривалість>"` (тривалість `"2 год 11 хв"`), немає — макет «05.10, 18:42 — відключення мережі 2 год 11 хв»; `warn` — `fail_start` |
| `BESS` | «Ємність» `"387 кВт·год (2 шафи)"` (`2 × kwh` паспорта); «Потужність» `"200 кВт"`; «Заряд» `"<soc %> · <kWh> кВт·год"`; «Зараз» — `"заряджається N кВт (надлишок СЕС і КГУ)"` / `"віддає N кВт"` / `"очікування"`; «Режим» `"зрізання піків понад <peak_shave_kw> кВт + резерв на пуск генератора"`; «Тримає критичні» `"≈ <round(kwh·soc/critical·60)> хв"` (макет 51); `warn` — `state == 'fault'` |

`totals.update({...})` — ключі CE-03 з R-06/R-14 (`pv_kwp` = 900, `n_modules` = 1552, `chp_rated` = 800, `chp_heat` =
`heat_kw`, `chp_load` = `chp_kw/800` (3 знаки), `bess_kwh` = 387, `bess_soc` — частка (`%/100`, 3 знаки), `load_kw`,
`critical_kw` — цілі); `vents`, `vent_area`, `genset_kva` не чіпаються.

### R-18 Шина й дельти (FR-18, A-22)

1. Події шини: R-04 п. 8, R-13 п. 6, R-14 (кожна зміна відключення — `_notify('f3d.energy', ['ATS-1'], 'signal')`),
   R-09 (перерахунок МО — `_notify('mrp.production', [назви МО зі зміненим кВт·год ≥ 0,1], 'doc')` і
   `_notify('f3d.energy', ['energy'], 'signal')`). Без `factory3d_viewer` (`'f3d.viewer.event' not in env`) — нічого.
2. Дельта `energy`: умова — `ctx['changes']` має ключ `f3d.energy`, або `f3d.signal` з кодами з префіксами `energy/`,
   `infra/pv/`, `infra/bess/`, `infra/chp/`, `infra/ats/`, `infra/totals/`, або `mrp.production`/`mrp.workorder` → розділ
   будується цілком (≈ 30 КБ) і `patch['productions']` доповнюється R-16 п. 8.
3. Дельта `infra`: та сама умова (без `mrp.*`) → `deep_merge(patch.setdefault('infra', {}), tmp['infra'])` —
   рекурсивне злиття словників (списки — заміна).

### R-19 Ротація (`cron_f3d_energy_rotate`, FR-25)

`DELETE FROM f3d_energy_interval WHERE id IN (SELECT id FROM f3d_energy_interval WHERE ts_start < %s LIMIT 50000)` у
циклі ≤ 60 с (`now − keep_interval_days`); так само `f3d_energy_balance.hour`, `f3d_energy_event.ts` (`keep_event_days`).
`f3d.energy.alloc`, `f3d.energy.outage` не ротуються.

### R-20 Час і часові пояси

Зберігання — UTC naive; слоти 15 хв — `date_trunc` за UTC (зсув Києва цілий — межі збігаються з місцевими); доба,
`hour_local`, профіль, `kwh_shift`, тарифні вікна — `zoneinfo.ZoneInfo('Europe/Kyiv')`. Доба переходу на зимовий час
(25 год): повторена місцева година сумується в той самий індекс `profile`; доба переходу на літній (23 год): пропущена
година — 0. Тексти подій і заявок — Київ.

### R-21 Стан лічильника й обчислених (FR-27)

1. `data_state` (крон R-06, для кожного лічильника): немає `last_ts` → `no_data`; `status == 'stale'` або
   `now − last_ts > 3 × period_s` → `stale`; є інтервал `reset` за 24 год → `reset`; є `missing`/`interpolated` за 2 год →
   `gap`; інакше `ok`. Зміна → `data_state_since`, чаттер.
2. `stale` довше `gap_alarm_min` → подія `warn` «Лічильник PM-SAW-1: немає даних 60 хв (останнє показання 10:05).»
   (одна на епізод).
3. Енергія за пропуск не губиться (R-03, R-04 п. 7).
4. Обчислені: якщо крон не записав сигнал довше `3 × period_s` — провайдер не використовує значення (R-16 п. 9); джерело
   `EN-DERIVED` — `state='online'` при кожному успішному прогоні R-06, `error` з текстом винятку при збої.

### R-22 Прив'язка даних

Кроки, джерела й ідемпотентність — §5.3; правило відповідності кодів — CB-01 `search_f3d`.

### R-23 Перерахунок і фіксація

1. Рядки `locked` не змінюються ні кроном, ні майстром; МО з `f3d_energy_locked` не перераховується (кнопка
   прихована).
2. Майстер M-19 — до 31 доби; інтервали — `_f3d_rebuild` (upsert), розподіл — R-09 п. 8.
3. Зміна тарифу заднім числом → перерахунок інтервалів і незафіксованого розподілу майстром (не автоматично).

## 10. Стани й переходи

### 10.1 Лічильник (`f3d.energy.meter.data_state`, R-21)

```
no_data ──(перше показання)──► ok
ok ──(немає показань > 3·period | сигнал stale)──► stale ──(показання)──► ok | gap
ok ──(інтервал missing/interpolated за 2 год)──► gap ──(2 год без пропусків)──► ok
* ──(R-03 скидання)──► reset ──(24 год без скидань)──► ok
```
Побічні ефекти: `data_state_since`, чаттер лічильника; `stale` > `gap_alarm_min` → подія (R-21 п. 2).

### 10.2 Відключення (`f3d.energy.outage.state`, R-14)

`open` (втрата мережі) → [`transfer_s`, `gen_started` при `position=3`; `fail_start` у варіанті B] → [`grid_back_at`
при поверненні мережі] → `closed` (`position=2` або АВР несвіжий і `grid_ok`). Одночасно відкрите — лише одне.

### 10.3 Розподіл і МО

`f3d.energy.alloc`: створено/оновлено кроном (незафіксований) → `locked` (МО закрито, R-10 п. 2) — кінцевий.
`mrp.production.f3d_energy_state`: `none` → `estimate` | `partial` | `measured` (за якістю рядків); `f3d_energy_locked`:
`False` → `True` при `_cal_price` (зворотного переходу немає).

### 10.4 Інтервал і баланс

`f3d.energy.interval.quality`: `missing` → `interpolated` (R-04 п. 7, добудова) — інші переходи лише перебудовою
майстром. `f3d.energy.balance.state`: `skipped` → `ok` | `deviation` (повторна перевірка протягом 6 год).

### 10.5 Сигнали

Статуси — telemetry R-04/R-07 (CT-05). Модуль не змінює `status` напряму; обчислені сигнали отримують показання через
CT-10, і telemetry рахує статус і заявки.

## 11. Обробка помилок

1. **Лічильник недоступний** — колектор/telemetry: `stale`; модуль: інтервали чекають `max_wait_h`, далі `missing`;
   після повернення даних — добудова `interpolated` (R-04 п. 7); баланс годин з `missing` — `skipped`; розподіл: сегменти
   без даних РЦ — оцінка (`estimate`, R-08 п. 4); пул без даних — не розподіляється у цих слотах.
2. **Переповнення / скидання / заміна лічильника** — R-03 п. 2: енергія не губиться і не подвоюється; `reset` у
   інтервалі, подія, `counter_offset` оновлено.
3. **Пропуски інтервалів** — лінійна інтерполяція накопичувального лічильника (сумарна енергія через пропуск точна);
   «немає даних» (`missing`) лише коли після пропуску досі немає жодної точки довше `max_wait_h`.
4. **Показання з минулого (буфер колектора)** — telemetry зберігає (R-03 telemetry); профіль перебудовується, якщо слот
   ще не побудований або `missing`; побудовані `measured` слоти не перебудовуються автоматично (майстер).
5. **Немає тарифу** — `price=0`, подія раз на добу (R-05 п. 1).
6. **Немає РЦ/обладнання на чистій базі** — вузли без прив'язок, `alloc_role='none'` для прямих, звіт `partial` (§5.3).
7. **machine_connect встановлено, але РЦ не підключено** — журнал часу (R-08 п. 2).
8. **Виняток у кроні** — `_logger.exception`, прогін завершується, наступний повторює (ідемпотентні upsert); джерело
   `EN-DERIVED` → `state='error'`, `last_error` (R-21 п. 4).
9. **Виняток в обробнику `_f3d_ingest`** — `savepoint`, лог, пакет telemetry не відкочується (M-15).
10. **МО закривають до побудови останнього слоту** — розподіл фіксується з даними до `now` (лічильники РЦ — з показань,
    не зі слотів); залишок слоту — іншим завданням або `unallocated` (R-09 п. 6).
11. **Часові пояси** — R-20; `ts` з колектора — UTC; DST.
12. **Подвійне ввімкнення: машина в CM-03 і журнал часу одночасно** — береться лише CM-03 для підключених РЦ (без
    подвоєння).
13. **Запис уставок** — `ValidationError` (A-15); `f3d.command` на сигнали енергетики неможливі, бо `write_enabled`
    не може стати `True`.
14. **Нотація адрес на стенді не відповідає (Q-08)** — ТК-11 показує розбіжність (значення поза `range` → `q='bad'`,
    або `0x02` емулятора → джерело `error`); виправлення — у даних (`address`), не в коді.

## 12. Acceptance Criteria

Формат: Given / When / Then; тип: **UT**, **TC**, **MAN**. Фікстури — §13.0.

| ID | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given установка на чисту базу; Then 123 `f3d.energy.node`: `input` 1, `substation` 1, `transformer` 2, `switchboard` 1, `section` 2, `cell` 11, `line` 6, `tapoff` 36, `consumer` 49, `generator` 12, `storage` 1, `ats` 1; `QF-1.parent_id=SEC-2`, `BW-1.parent_id=QF-1`, `SAW-1.parent_id=TAP-SAW-1`, `TAP-SAW-1.parent_id=BW-1`, `COMPRESSOR.parent_id=C1`, `QS.peer_id=SEC-2`, усі 11 шаф `cabinet_id=SWB-1`; `section` SAW-1 = 2, SAND-1 = 1 | UT |
| AC-02 | FR-01 | Given вузол; When `code='saw-1'` / `parent_id` = власний нащадок / `alloc_role='direct'` без РЦ / `alloc_role='shared'` без пулу / пул при ролі `direct` / `cell` без `cell_type` / `section=3`; Then `ValidationError` з текстом §2 M-01; другий вузол з тим самим РЦ → `IntegrityError` | UT |
| AC-03 | FR-01 | Given мережа з даних; Then `search([('id','child_of',QF-1)])` містить BW-1, 7 відгалужень, 7 споживачів (SAW-1, SAW-2, EDGE-1, EDGE-2, CNC-1, CNC-2, SORT-1); Σ `p_inst_kw` споживачів = 1 201,0 ± 0,1; `QF-3._f3d_descendant_meters()` — рівно 8 лічильників споживачів BW-3 (SAND-1, AUTOSPRAY-1, UV-1, HINGE-1, GLUE-1, PRESS-1, SPRAY-1, DRY-1); власний PM-QF-3 не входить | UT |
| AC-04 | FR-01, CE-04 | Then `is_critical=True` рівно в 10 вузлах: LP-1, LP-2, LP-3, DUST-1, COMPRESSOR, BOILER, OFFICE, EF-ELEC, EF-CHG, BW-1 | UT |
| AC-05 | FR-02 | Then 67 `f3d.energy.meter`: `pm5560` 57 (`incomer` 2, `feeder` 6, `consumer` 49), `sun2000` 8, `luna2000` 1, `tedom` 1; `PM-Q1.e_export_signal_id.code='energy/cells/Q1/kwh_export'`; `PM-SAW-1.e_import_signal_id.code='energy/consumers/SAW-1/kwh_total'`, `p_signal_id.code='energy/consumers/SAW-1/p_now'`, `max_kw=48`; `LUNA-1.e_export_signal_id.code='infra/bess/kwh_discharge_total'` | UT |
| AC-06 | FR-02 | When лічильнику ставлять `e_import_signal_id` з `kind='gauge'` або одиницею `кВт`; Then `ValidationError` «…має бути накопичувальним (counter)» / «…в кВт·год» | UT |
| AC-07 | FR-05 | Given тариф «День» 07–23 9,60 / «Ніч» 23–07 4,80 (усі дні); When `_f3d_price_at` для місцевих 22:45, 23:00, 06:45, 07:00 (12.10.2026); Then 9,60 / 4,80 / 4,80 / 9,60, зони відповідні; демо-тариф → 8,40 «Цілодобова» для будь-якого часу | UT |
| AC-08 | FR-05 | When зберегти тариф із зонами без неділі; Then `ValidationError` «Зони тарифу «…»: нд о 00:00 не покрито»; дві зони на ту саму годину → «…покрито двічі (День, Пік)»; `hour_from=hour_to` → «…нульову тривалість»; `weekdays='0089'` → помилка формату | UT |
| AC-09 | FR-05 | Given активний тариф 2026-01-01…∞; When другий активний з 2026-06-01; Then `ValidationError` «Період тарифу перетинається…»; з `date_to=2026-05-31` у першого — дозволено, `_f3d_tariff_at(2026-07-01)` → другий | UT |
| AC-10 | FR-05, FR-12 | Given демо-тариф; When `contract_kw=900`, `peak_warn_pct=90`; Then сигнал `energy/totals/grid15_kw`: `warn_high=810`, `alarm_high=900`, обидва `*_on=True`, `alarm_title` за R-12 п. 1 | UT |
| AC-11 | FR-05 | Given тарифів немає; When R-04 будує слот; Then `price=0`, `cost=0`, `zone_id=False`, одна подія `warn` «Немає чинного тарифу на 12.10.2026» за добу (другий слот подій не додає) | UT |
| AC-12 | FR-24 | Given чиста база (telemetry встановлено, рівня 0 немає); When `post_init_hook`; Then звіт: `nodes: 123`, `sources: 68`, `meters: 67`, `pools: 5`, `signals.created: 297`, `signals.updated: 0`, `unmatched_equipment: 80`, `direct_without_wc: 35`, `state='partial'`; сигнали `energy/transformers/T1/temp_c` з джерелом `MB-U96-RTD1` і адресою telemetry | UT |
| AC-13 | FR-24 | Given копія демо 14.10; When установка; Then звіт `state='done'`, `equipment_linked: 80`, `workcenter_linked: 35`, `signals.created: 210`, `signals.updated: 87`, `unmatched_equipment: 0`; `last_value` сигналу `energy/consumers/SAW-1/p_now` дорівнює значенню до установки | TC |
| AC-14 | FR-24 | When `action_f3d_energy_rebind()` повторно (адміністратор); Then усі `created: 0`, кількості записів моделей незмінні; користувач `group_f3d_manager` → `AccessError` | UT |
| AC-15 | FR-04 | R-03 рядок 1: Given 80 точок з кроком 60 с від (01:35:30, 999,890) по 0,22; Then `Ec(01:36:00)=1000,000`, `Ec(02:54:00)=1017,160`, `delta=17,160`, `measured` (точність 1e-6) | UT |
| AC-16 | FR-04, FR-27 | R-03 рядок 2: (10:00, 500), (10:40, 520); Then `Ec(10:15)=507,5`, якість `interpolated`; з `gap_max_s=3600` — `measured` | UT |
| AC-17 | FR-27 | R-03 рядки 3–4: скидання з нуля → `c=12 346,190`, `reset`; заміна (2 000) → `c=12 345,678`; рядок 5 (−0,4) → без скидання | UT |
| AC-18 | FR-04 | Then `delta(a, b)` з будь-яким `None` → `(None, 'missing')`; порядок якостей `missing > reset > interpolated > measured` | UT |
| AC-19 | FR-04 | Given показань у `f3d.reading` за вікно немає, але є інтервали лічильника з `e_start/e_end`; When `_f3d_counter_series`; Then ряд з інтервалів, `delta` на межах 15 хв точний, усередині — `interpolated` | UT |
| AC-20 | FR-27 | Given профіль будується зі скиданням; Then `counter_offset` лічильника = `c − v` після скидання, одна подія `meter` `warn` «Лічильник PM-SAW-T: скидання показника 12 345,678 → 0,512 кВт·год» | UT |
| AC-21 | FR-04 | Given PM-SAW-T з рядом `Ec(01:30)=998,808`, `Ec(01:45)=1001,980` і демо-тариф; When `_cron_build`; Then інтервал `ts_start=01:30`: `kwh=3,172`, `kw_avg=12,69`, `price=8,40`, `cost=26,64`, `quality='measured'`, `day=2026-10-12`, `hour_local=4`; повторний прогін — той самий рядок (`ON CONFLICT`), кількість рядків незмінна | UT |
| AC-22 | FR-04 | Given остання точка 10:00, `now=10:30`; When прогін; Then слоти після 10:00 не будуються; `now=16:30` (`max_wait_h=6`) → слоти 10:00…16:00 `missing`, `kwh=0`; потім точка (16:40, +20 кВт·год) і прогін → ці слоти перебудовано `interpolated`, Σ `kwh` = 20,000 ± 0,001 | UT |
| AC-23 | FR-04 | Given ввід PM-Q-T з експортом; Then `kwh_export` заповнено; `cost` рахується з `kwh` (імпорт); лічильник ролі `generation` → `cost=0` | UT |
| AC-24 | FR-04, FR-23 | Given `read_enabled=False`; When `_cron_build`; Then 0 нових інтервалів | UT |
| AC-25 | FR-04 | Given 2 доби даних, перший прогін; Then ≤ 192 слоти на лічильник за прогін, `last_interval_start` = останній побудований | UT |
| AC-26 | FR-06 | Given свіжі сигнали ліній з числами R-06 прикладу; When `tools.live.site_totals(...)`; Then `P_1=334,7`, `cos_before_1=0,90`, PFC-1 `q_now=100`, `cos_after_1=0,97`, `S_1=345,1`; секція 2 — PFC-2 50, `cos_before_2=0,93`; тотали `p_now=626`, `s_now=645`, `cos_before=0,91`, `cos_after=0,97` | UT |
| AC-27 | FR-06 | Given `P_Q1=334,7`, `P_Q2=−376,7`; Then `grid_kw=0`, `export_kw=42`; `P_Q1=400`, `P_Q2=−100` → `grid_kw=300`, `export_kw=0`; острів → обидва 0 | UT |
| AC-28 | FR-06, CE-04 | Given `p_now` критичних як у макеті (LP-1 5,6; LP-2 23,2; LP-3 9,5; DUST-1 127,5; COMPRESSOR 46,6; BOILER 10,0; OFFICE 17,6; EF-ELEC 0,84; EF-CHG 0,107; BW-1 106,9); Then `critical_kw=347,847` → у payload `348` | UT |
| AC-29 | FR-06, FR-27 | When `_cron_live`; Then показання `energy/totals/p_now`, `energy/totals/cos_phi`, `infra/totals/pv_now`, `grid_kw`, `export_kw` з `src='module'`, `ts`=початок хвилини; Given 3 фідери `stale` → тотали не пишуться | UT |
| AC-30 | FR-07 | Given інтервали за годину за таблицею R-07; When `_cron_balance`; Then Q1 `ok` (diff 0), Q2 `ok` (expected −376,7), BW-1 110,5/106,9 → `deviation`, `diff_pct=3,26`; 109,0 → `ok` 1,93; C1 1,5/0,2 → `ok`; подія «Небаланс обліку BW-1: 3,26 % …» | UT |
| AC-31 | FR-07 | Given слот споживача лінії `missing` → `skipped`, `reason` містить код лічильника; година з відключенням → `skipped` «відключення мережі»; `imbalance_pct` для `skipped` не пишеться | UT |
| AC-32 | FR-07, FR-12 | Given BW-1 `deviation` 3,26 % і 5,4 % у дві години поспіль; Then сигнал `energy/lines/BW-1/imbalance_pct` `warn` після першої, `alarm` після другої (`min_duration_s=3600`), одна заявка з назвою, що починається з «Небаланс обліку QF-1: 5,4» (шаблон R-07 п. 3, `decimals=2`), на обладнанні QF-1 | UT |
| AC-33 | FR-12, FR-13 | Given сигнал `energy/transformers/T1/s_kva` (`warn_high=900`, `alarm_high=1000`); When показання 950, 1 020, 880 через `_f3d_ingest`; Then події `warn`, `bad`, `info` з текстами R-13 п. 1; заявка «Перевантаження трансформатора T1: 1020 кВА при номіналі 1000» (telemetry R-05) | UT |
| AC-34 | FR-12 | Given демо-тариф 800 кВт; When `grid15_kw` = 812,4; Then заявка «Перевищення договірної потужності: 812,4 кВт при ліміті 800 кВт» на SWB-1, енергетики (`group_energy_manager`) — підписники заявки (M-17) | UT |
| AC-35 | FR-12 | Given фазні струми 171/180/168 і 140/180/150 на QF-T; When `_cron_live` о хвилині, кратній 5; Then `i_unbal_pct` = 4,05 і 14,89 (`warn`); `I_avg=3` А → не пишеться | UT |
| AC-36 | FR-13 | Then: (а) `pfc_q_now` PFC-T 50 → 100 → подія «Компенсація секції 1: увімкнено ще один ступінь 50 квар, cos φ 0,97.»; повтор за 10 хв — без нової; (б) `workcenters/CNC-T/machine_state` → `fault`, `p_now` 0,7 → «CNC-T: аварійна зупинка, споживання впало до 0,7 кВт.»; (в) перший прогін після півночі → «Пік 15-хвилинної потужності за 12.10: 654 кВт о 09:15; ліміт договірної потужності (800 кВт) не перевищено.» | UT |
| AC-37 | FR-08 | Given WO SAW-T з журналом часу 01:36–02:54 і ряд AC-15; When `_f3d_alloc_days([12.10])`; Then рядок `direct` `kwh=17,160`, `minutes=78,0`, `cost=144,14`, `quality='measured'`; `wo.f3d_energy_direct_kwh=17,160` | UT |
| AC-38 | FR-08 | Given 5 WO МО-231-Т (SAW-T 78 хв, EDGE-T 63, CNC-T 74, SORT-T 29, ASMLINE-T 95; `p_inst`/`load_factor` = макет) без лічильників; Then прямі 17,160 / 46,069 / 13,567 / 4,350 / 5,067, `quality='estimate'`; МО `f3d_energy_kwh=86,213`, `f3d_energy_cost=724,18`, `f3d_energy_state='estimate'` | UT |
| AC-39 | FR-08 | Given два WO на одному РЦ 10:00–10:20, лічильник +4,0; Then по 2,000 кВт·год і 20,0 хв | UT |
| AC-40 | FR-08 | Given лічильник SAW-T за добу +30,0, прямі 17,160; Then рядок `idle` SAW-T 12,840 | UT |
| AC-41 | FR-08, A-05 | Given патч `_f3d_machine_intervals` повертає для WO `[(06:55:00, 07:25:48, 'working')]` і лічильник 12,18 кВт; Then `direct` 6,253 ± 0,005 кВт·год, `minutes=30,8`; журнал часу WO (інший) ігнорується для підключеного РЦ | UT |
| AC-42 | FR-09 | R-09 рядок 1 (слот 02:45–03:00, POOL-DUST-T `kwh`); Then `shared` SAW-T 5,868 / 49,29 грн, EDGE-T 26,007 / 218,46 | UT |
| AC-43 | FR-09 | R-09 рядок 2 (POOL-LIGHT-T `time`); Then 2,486 / 3,314 | UT |
| AC-44 | FR-09 | Given нічний слот без завдань (DUST 2,0) і BOILER-T за добу 240,0; Then `unallocated` POOL-DUST-T 2,0 (+ інші слоти), `overhead` BOILER-T 240,0; Σ `shared` + `unallocated` = Σ `delta` DUST-T за добу (± 0,003) | UT |
| AC-45 | FR-09, FR-10 | Given рядки МО А `locked`; When перерахунок доби з новими показаннями; Then рядки А незмінні (`kwh`, `cost`, `write_date`), рядки МО Б змінено, `unallocated` = залишок (може бути від'ємним до −0,5) | UT |
| AC-46 | FR-10 | Given МО-231-Т (26 шт), категорія товару `property_cost_method='average'`, енергія 724,18; When `button_mark_done`; Then `extra_cost=27,8531`, `f3d_energy_applied_unit=27,8531`, `f3d_energy_locked=True`, рух готової продукції має вартість, більшу на 724,18 ± 0,02 від того самого МО з `costing_enabled=False`; чаттер «До Extra Unit Cost додано енергію: 27,8531 грн/од. (724,18 грн / 26 шт).» | UT |
| AC-47 | FR-10, Q-06 | Given категорія `standard`; When закриття; Then `extra_cost=0`, `f3d_energy_applied_unit=0`, чаттер «Енергію не внесено у вартість: метод «Стандартна ціна»…», рядки `locked` | UT |
| AC-48 | FR-10, FR-23 | Given `costing_enabled=False`, AVCO; When закриття; Then `extra_cost` без змін, рядки `locked` | UT |
| AC-49 | FR-10 | Given AVCO, МО 26 шт, `qty_producing=10`, створення дозамовлення; Then дозамовлення `extra_cost` = `extra_cost` МО до закриття (без енергії); на закритому МО енергія = енергія його завдань | UT |
| AC-50 | FR-10 | Given РЦ SAW-T з `analytic_distribution={"<acc>": 100}`, `analytic_enabled=True`; When закриття; Then аналітичний рядок «[EN] <завдання>» з `amount=-144,14`, `unit_amount=17,16`, `product_uom_id=uom.product_uom_kwh`, `category='manufacturing_order'`, прив'язаний до `analytic_line_ids`; повторне закриття не дублює | UT |
| AC-51 | FR-10 | When `_cal_price` викликається двічі (два готові рухи); Then `extra_cost` збільшено один раз | UT |
| AC-52 | FR-10, FR-16 | Given AC-38; When провайдер `energy` на payload з `productions=[{"name": МО-231-Т…}]` для користувача з `group_energy_cost`; Then `energy_kwh=86.2`, `energy_cost=724`, `energy_quality='estimate'` | UT |
| AC-53 | FR-08 | Given копія демо; When крон розподілу за 12.10; Then `WH/MO/00231`: WO00001…WO00004 прямі 17,160 / 46,069 / 13,567 / 4,350 (`estimate`), WO00005 = 8 × 0,4 × хв/60 до `now` | TC |
| AC-54 | FR-22 | Given майстер (`mrp.group_mrp_user`, без `group_energy_cost`); When `read` МО полів `f3d_energy_kwh`, `f3d_energy_cost`; Then kWh повертається, `f3d_energy_cost` → `AccessError`; у формі вкладка «Енергія» без групи «Вартість» | UT |
| AC-55 | FR-14, CE-02 | When `_f3d_ingest([{infra/ats/src1_state, ts=T, text='available'}])`; Then `infra/ats/src1_ok` `last_value=1`, `last_ts=T`; `text='under'` → 0; `position` `pos_II` → `last_value=3`, `last_text='pos_II'` | UT |
| AC-56 | FR-14 | Given мережа, `mode='remote'`; When послідовно `src1_state=under` (T), `position=pos_II` (T+14 с), `src1_state=available` (T+600), `position=pos_I` (T+660); Then одне відключення: `amf_master='hgm'`, `transfer_s=14`, `return_s=60`, `duration_min=11,0`, `state='closed'`; події «Зникла напруга мережі…», «АВР: переключено на генератор за 14 с.», «Мережу відновлено… через 60 с; відключення тривало 11 хв.» | UT |
| AC-57 | FR-14 | Given `mode='auto'`, відключення відкрите, `gen_start=on` о T, `src2_state=under` до T+40 с, `ats_fail_start_s=35`; Then `infra/ats/fail_start=1` (заявка «АВР: генератор не запустився (FAIL START)» на ATS-1), `outage.fail_start=True`, подія `bad`; `src2_state=available` → `fail_start=0` | UT |
| AC-58 | FR-14 | Given `mode='remote'` (варіант A), `gen_start` не змінюється 60 с; Then `fail_start` не встановлюється; `amf_master='hgm'` | UT |
| AC-59 | FR-14, FR-15, CE-03 | Given відкрите відключення, `load_before=626`, фідери Σ 348, `bess_kw=−200`, `position=3`; When провайдер `infra`; Then `totals.grid_kw=0`, `export_kw=0`, `load_kw=348`, `shed_kw=278`, `bess_mode='discharge'`; ключів `island`, `grid_ok`, `genset_*` немає | UT |
| AC-60 | FR-14 | Given сигналів АВР немає (несвіжі), обидва вводи `P=0`, `I=0` свіжі; Then відключення `source='incomers'`; вводи ожили → закрите | UT |
| AC-61 | FR-15, CE-01 | Given payload з `infra.cards.GENSET` і `infra.totals.genset_kva=634` (статика); When провайдер `infra`; Then `GENSET` і `genset_kva` незмінні; змінено лише `PV-ROOF`, `PV-INV`, `CHP`, `ATS-1`, `BESS` | UT |
| AC-62 | FR-14 | Given параметр `factory3d.genset.amf_master='hgm'` і `mode='auto'`; Then одна подія `warn` на добу «Режим АВР «Авто» не відповідає налаштуванню моста генератора «hgm».» | UT |
| AC-63 | FR-16 | Given мережа з даних і свіжі сигнали за макетом; When `build_energy`; Then ключі A.12: `meta` (4), `totals` (16 + `contract_kw`), `transformers` (2 × 10 ключів), `cells` 11 у порядку `SWB_CELLS`, `lines` 6, `consumers` 49, `profile` 24, `typical` 24, `events` ≤ 6; `totals.p_now=626`, `cos_after=0.97`, `capacity_kva=2000`, `p_inst=1201` | UT |
| AC-64 | FR-16 | Then `cells['QS']` = `{type:'coupler', section: None, state:'off', rating_a:1600, note:…}`; `cells['PFC-2'].q_now=50`; `cells['Q1'].state='on'` (сигнал `closed`), `'tripped'` при `tripped`; `consumers['CNC-T'].status='stop'` при `machine_state='fault'`; `consumers['SAW-1'].i_now=22` при 12,18 кВт / 0,84 | UT |
| AC-65 | FR-16, FR-22 | Given `ctx.kiosk=True` або користувач без `group_energy_cost`; Then `totals.cost_today` і `productions[].energy_cost` відсутні, `energy_kwh` присутній | UT |
| AC-66 | FR-16 | Then `workcenters['SAW-1'].energy == {"p_now": 12.18, "line": "BW-1"}` | UT |
| AC-67 | FR-17 | Given макетні сигнали (pv 468 = 8 × 58,5, chp 400, bess +200, soc 76,1 %, Q1 334,7, Q2 −376,7); When `build_infra`; Then `totals.export_kw=42`, `grid_kw=0`, `bess_mode='charge'`, `critical_kw=348`, `n_modules=1552`; `cards['BESS'].rows` містить `["Зараз", "заряджається 200 кВт (надлишок СЕС і КГУ)"]` і `["Тримає критичні", "≈ 51 хв"]`; `cards['PV-INV'].rows` `["Стан", "усі в мережі"]`; картки `WATER`, `SERVER` незмінні | UT |
| AC-68 | FR-18, A-22 | Given `patch['infra']={'totals': {'genset_kw': 348}}` від іншого провайдера; When `_f3d_viewer_delta` провайдера `infra`; Then `patch['infra']['totals']` має і `genset_kw`, і `export_kw` | UT |
| AC-69 | FR-16, A-04 | Then моделі `f3d.viewer.provider.energy` (`_f3d_sequence=100`, `_f3d_sections=('energy',)`) і `.infra` (150, `('infra',)`) є в реєстрі без `factory3d_viewer`; `_inherit` порожній; виклик `_f3d_viewer_collect({}, ctx)` без viewer не падає | UT |
| AC-70 | FR-03, A-06 | Then адреси: `energy/consumers/SAW-1/p_now` = `{"fc":3,"addr":3059,"type":"f32",…}` на джерелі `MB-U11-PM-SAW-1` (`params.unit=11`); `…/kwh_total` = `addr 3203`, `i64`, `scale 0.001`; `infra/pv/PV-INV-3/p_kw` = `addr 32080`, `i32`, `0.001` на `MB-U63-SUN-3`; `infra/ats/position` = `addr 20483`, `kind='state'`, `states` 4; `infra/chp/state` `addr 40000`; усі 220 адрес проходять `tools.address.validate_address('modbus_tcp', …)` telemetry без помилок | UT |
| AC-71 | FR-03, FR-11 | Then 49 сигналів `…/kwh_shift`: `source_id=EN-DERIVED`, `derived_from_id` = `…/kwh_total` того самого споживача; `EN-DERIVED.type='f3d_energy'`, `collector_id` порожній, тип у `_f3d_local_types()` | UT |
| AC-72 | FR-03 | Given сигнал `energy/transformers/T1/temp_c` існує з адресою telemetry; When хук; Then адреса й джерело незмінні, `warn_high=100`, `alarm_high=110`, `hysteresis=2`, `min_duration_s=60` | UT |
| AC-73 | FR-03 | When telemetry API-01 `GET /f3d/telemetry/config` колектора `COL-MAIN`; Then у `sources` 68 джерел `MB-U*` енергетики з 220 сигналами, `EN-DERIVED` відсутнє | TC |
| AC-74 | FR-24 | When `uninstall_hook(env)`; Then параметрів `factory3d.energy.*` немає; сигнали з CSV без `source_id`; створені модулем — `active=False`; 87 мігрованих — активні; джерела `MB-U*` — `active=False` | UT |
| AC-75 | FR-21 | Then меню §3 з xml-id, `sequence`, батьками й групами (`menu_f3d_energy.sequence=50`, батько `factory3d_base.menu_f3d_root`) | UT |
| AC-76 | FR-19, FR-20 | Then усі представлення §3 завантажуються (`get_views` для кожної дії без помилок), вид `hierarchy` на `f3d.energy.node` існує; ручна перевірка: Енергетика → Схема мережі показує дерево GRID-10KV → RM6-1 → T1/T2 → Q1/Q2 → … | UT + MAN |
| AC-77 | FR-22 | Given користувачі: майстер, бухгалтер (`account.group_account_readonly`), енергетик, `group_f3d_user`; Then майстер має `group_energy_user`, не `group_energy_cost`; бухгалтер — `group_energy_cost`; енергетик — `group_f3d_manager`; `group_f3d_user` без енергетичних груп не бачить меню «Енергетика» | UT |
| AC-78 | FR-22 | Then ACL §4.1: майстер не може `write` вузол (`AccessError`), енергетик може; інтервали/розподіл — лише читання для всіх, крім адміністратора | UT |
| AC-79 | FR-22 | Given 2 компанії; Then вузли й тарифи компанії B не видно користувачу компанії A | UT |
| AC-80 | FR-23 | Given `read_enabled=True`; When `set_values` з `f3d_energy_read_enabled=False`; Then 68 джерел `read_enabled=False`, крони `_cron_live/_cron_build/_cron_alloc/_cron_balance` нічого не пишуть | UT |
| AC-81 | FR-23, A-15 | When `write({'write_enabled': True})` на будь-якому сигналі `module='energy'`; Then `ValidationError` «Запис уставок у пристрої енергетики заборонено у v1…»; сигнал іншого модуля — дозволено | UT |
| AC-82 | FR-23 | When виконати `neutralize.sql`; Then три параметри `False`, крони модуля неактивні, джерела `module='energy'` `read_enabled=false`, `state='disabled'` | UT |
| AC-83 | FR-11 | Given календар 07:00, `now` 10:30 Київ, ряд PM-SAW-T `Ec(04:00 UTC)=1003,3`, `Ec(07:30 UTC)=1053,8`; Then `kwh_shift=50,50`; о 06:30 Київ — від учорашніх 07:00 | UT |
| AC-84 | FR-25 | Given інтервали 401 доби тому і події 91 доби тому; When ротація; Then видалені; `f3d.energy.alloc` і відключення — ні | UT |
| AC-85 | FR-26 | Given майстер за 32 доби → `UserError`; майстер (енергетик) за 1 добу `both` → інтервали перебудовано, `result` містить кількості; користувач без групи → `AccessError` | UT |
| AC-86 | FR-28 | Given інтервали фідерів за 12.10 до 10:30; Then `profile` 24 елементи, години 11…23 — `None`, поточна година часткова; `peak_kw`/`peak_time` = максимум `load15` і його місцевий початок; < 3 робочих днів історії → `typical` статики | UT |
| AC-87 | FR-29 | Then `meter._f3d_kwh(01:36, 02:54)` = `(17.16, 'measured')`; `_f3d_kwh_by_code('NOPE', …)` = `(0.0, 'missing')`; `date_from ≥ date_to` → `ValueError` | UT |
| AC-88 | FR-08, FR-09 | ТК-03 `shift`: МО на SAW-1, NEST-1, EDGE-1 — після закриття `f3d_energy_direct_kwh` кожного WO = ∫ потужності емулятора за інтервалом ± 3 %, `quality='measured'`; спільні > 0 для `POOL-DUST`, `POOL-AIR`, `POOL-LIGHT` | TC |
| AC-89 | FR-14, FR-15 | ТК-05 `blackout` (варіант A): відключення з `transfer_s` 10…35 с, `shed_kw` 278 ± 30, `bess_mode='discharge'` під час пуску, у payload `infra.totals.grid_kw=0`, міст — `island=true` | TC |
| AC-90 | FR-06, FR-17 | ТК-07 експорт СЕС у полудень: `infra.totals.export_kw > 0`, `grid_kw=0`, `bess_kw ≤ 200`, `pv_now = Σ інверторів ± 1 кВт`, `kwh_export` PM-Q2 росте | TC |
| AC-91 | FR-03 | ТК-11 звірка адрес: для 5 лічильників PM5560 `kwh_total` vs `2700` Float32 (`GET /sim/v1/signals`) `|Δ| ≤ 1 кВт·год`; SUN2000 `p_kw` vs емулятор ± 0,5 кВт; ATyS `position` = 2 | TC |
| AC-92 | FR-07, FR-24 | DEPLOY_TEST етап 1 «один ввід і три фідери»: лише джерела PM-Q1, PM-QF-3, PM-QF-2, PM-QF-C1 і споживачі їх ліній `read_enabled=True` → баланс Q1 за 2 години `ok`; етап 2 — весь ГРЩ, баланс 8 вузлів `ok` або обґрунтоване `deviation` | TC |

## 13. План тестування (для Opus)

### 13.0 Фікстури й вимоги до тестованості

Запуск UT: `odoo-bin -d f3d_energy_test -i factory3d_energy --test-tags /factory3d_energy --stop-after-init
--without-demo=all` (чиста база з `factory3d_base`, `factory3d_telemetry`; `factory3d_viewer`, `factory3d_machine_connect`
не встановлені — їх поведінку імітують патчі). Теги класів: `post_install`, `-at_install`, `f3d`, `f3d_energy`. Час
заморожено: `odoo.tests.common.freeze_time('2026-10-12 08:00:00')` (UTC; Київ 11:00), бо telemetry відхиляє показання
старші `keep_days` і з майбутнього (R-17 telemetry).

`tests/common.py` — `class F3DEnergyCase(TransactionCase)`, `setUpClass`:
- `cls.collector = env.ref('factory3d_telemetry.collector_main')`; `cls.src_der = env.ref('factory3d_energy.source_en_derived')`;
- синтетична мережа (коди з суфіксом `-T`, щоб не конфліктувати з даними): `GRID-T` (input) → `T-T1` (transformer,
  `rating_kva=1000`) → `Q-T1` (cell incomer, `rating_a=1600`, `section=1`) → `SEC-T1` → `QF-T1` (cell feeder, 630 А) →
  `BW-T1` (line busway) → споживачі `SAW-T`, `EDGE-T`, `CNC-T`, `SORT-T`, `ASMLINE-T` (`direct`, РЦ з тими самими
  кодами, `p_inst_kw`/`load_factor` = 24/0,55, 67,5/0,65, 22/0,5, 20/0,45, 8/0,4), `DUST-T` (shared, `POOL-DUST-T`
  `kwh`), `LP-T` (shared, `POOL-LIGHT-T` `time`), `BOILER-T` (overhead); `PFC-T` (cell pfc, 350 квар);
- сигнали (через `env['f3d.signal'].create`, `module='energy'`, `source_id=False`, `store_period_s=0`, `kind='counter'`,
  `unit='кВт·год'` для енергії; `gauge` `кВт` для потужності) і лічильники `PM-<код>` з `max_kw` (SAW-T 48);
- тариф: демо з даних (8,40) або хелпер `make_tariff([(name, code, weekdays, h_from, h_to, price)], contract_kw=800)`;
- продукти й МО: `product_kc` (`KC-B600-T`, категорія `categ_avco` з `property_cost_method='average'` або
  `categ_std` `standard`), BOM з операціями на SAW-T, EDGE-T, CNC-T, SORT-T, ASMLINE-T; `make_mo(qty=26)` →
  `action_confirm()`; журнал часу — `env['mrp.workcenter.productivity'].create({'workcenter_id', 'workorder_id',
  'loss_id': env.ref('mrp.block_reason7').id, 'date_start', 'date_end'})` (продуктивна втрата демо — `block_reason7`;
  тест знаходить її як `search([('loss_type','=','productive')], limit=1)`);
- хелпери: `ingest(code, points)` → `env['f3d.signal']._f3d_ingest([{"code", "ts": t, "value": v} …], src='module')`;
  `ramp(code, t0, t1, kw, start=1000.0, step_s=60)` — точки накопичувального лічильника з постійною потужністю;
  `states(code, [(t, text)])`; `log(wo, start, end)`; `patch_machine(intervals)` — `unittest.mock.patch.object(
  type(env['f3d.energy.alloc']), '_f3d_machine_intervals', return_value=intervals)` (метод M-07, обгортка над CM-03);
  `patch_viewer()` — фейкова модель шини не потрібна: `_notify` викликається лише за наявності моделі;
  `users`: `u_master` (`mrp.group_mrp_user`), `u_account` (`account.group_account_readonly`), `u_energy`
  (`group_energy_manager`), `u_viewer` (`group_f3d_user`), `u_admin` (`group_f3d_admin`).

Тестованість: усі формули — чисті функції `tools/*.py` (без ORM) з тестами на числах §9; ORM-тести перевіряють
інтеграцію (поля, рядки, події, заявки).

### 13.1 Юніт-тести

| Файл / клас | Тест | AC | Фікстури | Що саме assert |
|---|---|---|---|---|
| `test_node.py::TestNodeData` | `test_123_nodes_by_kind`, `test_tree_links`, `test_descendants_qf3`, `test_critical_10` | AC-01, AC-03, AC-04 | дані модуля (CSV) | кількості за `kind`; `parent_id`/`cabinet_id`/`peer_id`/`section` прикладів; `search(child_of)`; Σ `p_inst_kw` 1 201 ± 0,1 |
| `::TestNodeConstraints` | `test_code_format`, `test_cycle`, `test_direct_needs_wc`, `test_shared_needs_pool`, `test_cell_type`, `test_section_range`, `test_wc_unique` | AC-02 | синтетичні вузли | `ValidationError` з текстом §2; `IntegrityError` у `mute_logger` + `cr.savepoint` |
| `::TestMeters` | `test_67_meters`, `test_meter_signal_checks` | AC-05, AC-06 | дані; синтетичний сигнал `gauge` | кількості за `model`/`role`; коди сигналів; `max_kw` |
| `test_tariff.py::TestZones` | `test_two_zone_prices`, `test_flat_demo`, `test_coverage_errors`, `test_overlap_periods`, `test_no_tariff_event` | AC-07…AC-09, AC-11 | `make_tariff` | ціни й зони; тексти помилок; одна подія за добу |
| `::TestContract` | `test_thresholds_from_contract` | AC-10 | демо-тариф | пороги сигналу `energy/totals/grid15_kw` |
| `test_hooks.py::TestInstall` | `test_clean_db_report`, `test_rebind_idempotent_and_rights`, `test_addresses`, `test_kwh_shift_rebind`, `test_temp_thresholds_only`, `test_uninstall_hook` | AC-12, AC-14, AC-70…AC-72, AC-74 | чиста база | звіт JSON; кількості; точні `address` для 4 прикладів AC-70 і `validate_address` для всіх 220; `uninstall_hook(env)` — параметри, `active`, `source_id` |
| `test_counter.py::TestCounterSeries` | `test_linear_ramp`, `test_gap_interpolated`, `test_reset_from_zero`, `test_replacement`, `test_small_negative`, `test_quality_order`, `test_fallback_intervals`, `test_api_kwh` | AC-15…AC-19, AC-87 | `tools.counter` (чисті) + `ramp` для AC-87 | числа R-03 з точністю 1e-6; якості |
| `::TestResetEvent` | `test_offset_and_event` | AC-20 | `PM-SAW-T`, `ingest` зі скиданням | `counter_offset`, текст події |
| `test_interval.py::TestBuild` | `test_slot_example`, `test_wait_then_missing_then_refill`, `test_export_and_cost_roles`, `test_read_disabled`, `test_limit_192`, `test_kwh_shift`, `test_rotation` | AC-21…AC-25, AC-83, AC-84 | `ramp`, `freeze_time` зсуви | значення полів інтервалу; кількість рядків; Σ кВт·год після добудови; `kwh_shift=50.5`; видалення старих |
| `test_live.py::TestLive` | `test_sections_pfc_totals`, `test_grid_export`, `test_critical`, `test_derived_ingest_and_stale_guard`, `test_profile_peak_typical` | AC-26…AC-29, AC-86 | `tools.live` (чисті) + сигнали | числа R-06/R-15; показання обчислених з `src='module'` |
| `test_balance.py::TestBalance` | `test_table_examples`, `test_skipped`, `test_imbalance_signal_alarm` | AC-30…AC-32 | інтервали, створені напряму (`sudo().create`) | стани, `diff_pct`, події, заявка |
| `test_events.py::TestEvents` | `test_status_transitions`, `test_contract_request_and_followers`, `test_unbalance`, `test_pfc_fault_peak_events` | AC-33…AC-36 | сигнали з порогами, обладнання з командою | тексти подій і заявок; `message_follower_ids` заявки містить партнера `u_energy` |
| `test_alloc.py::TestDirect` | `test_measured_saw`, `test_estimate_mo231`, `test_concurrent_split`, `test_idle_row`, `test_machine_connect_path` | AC-37…AC-41 | `make_mo`, `log`, `ramp`, `patch_machine` | `kwh`, `minutes`, `cost`, `quality` рядків і полів WO/МО |
| `::TestPools` | `test_dust_kwh_driver`, `test_light_time_driver`, `test_unallocated_overhead_conservation`, `test_locked_untouched`, `test_wizard` | AC-42…AC-45, AC-85 | слот 02:45–03:00, `ramp` DUST-T 127,5 кВт і LP-T 23,2 кВт | частки R-09; Σ збереження; незмінність `locked` |
| `test_costing.py::TestCosting` | `test_avco_extra_cost`, `test_standard_no_change`, `test_costing_disabled`, `test_backorder`, `test_analytic_lines`, `test_cal_price_twice` | AC-46…AC-51 | МО-231-Т з енергією 724,18; категорії AVCO/standard; аналітичний рахунок | `extra_cost`, `f3d_energy_applied_unit`, вартість руху ГП (`stock.move.value` ГП з/без енергії), аналітичні рядки, чаттер |
| `test_mo231.py::TestMo231` | `test_viewer_numbers`, `test_master_rights` | AC-52, AC-54 | AC-38 + провайдер | `energy_kwh 86.2`, `energy_cost 724`; `AccessError` на `f3d_energy_cost` |
| `test_ats.py::TestAts` | `test_src_ok_derived`, `test_outage_cycle_variant_a`, `test_fail_start_variant_b`, `test_no_fail_start_variant_a`, `test_island_totals`, `test_incomer_fallback`, `test_no_genset_keys`, `test_bridge_mismatch_event` | AC-55…AC-62 | сигнали АВР (`states` R-02 п. 4), `states(...)`, `freeze_time` кроки | поля відключення; події; `infra.totals` |
| `test_payload.py::TestPayload` | `test_energy_section_keys_and_numbers`, `test_cells_states_consumers`, `test_cost_hidden_kiosk`, `test_workcenter_energy`, `test_infra_cards_totals`, `test_delta_deep_merge`, `test_providers_registered` | AC-63…AC-69 | дані модуля + `last_value` сигналів, встановлені SQL (`UPDATE f3d_signal SET last_value=…, last_ts=…, status='ok'`) за числами макета | структура A.12/A.13; значення; відсутність ключів |
| `test_security.py::TestSecurity` | `test_menus`, `test_views_load`, `test_group_implications`, `test_acl`, `test_company_rules`, `test_read_disabled_crons`, `test_write_forbidden`, `test_neutralize_sql`, `test_injection_codes` | AC-75…AC-82 | користувачі §13.0 | меню, `get_views`, `AccessError`, `ValidationError`, SQL |
| `test_data_sync.py` (pytest поза Odoo) | `test_csv_match_macro` | — | `tools/gen_energy_data.py` у тимчасову теку | згенеровані `energy_*.csv` побайтово = `data/*` |

### 13.2 Стендові сценарії ТК-01…ТК-12

Передумови: `docker compose -f services/iot_sim/docker-compose.sim.yml --profile dev up -d iot_sim mosquitto
genset_relay` + колектор telemetry (`COL-MAIN`, токен) + копія демо `odoo_energy_test` з `factory3d_base`,
`factory3d_viewer`, `factory3d_iot_sim`, `factory3d_telemetry` (міграція `done`); для ТК-05/06 — `td_genset` 19.0 і
`factory3d_genset`; для ТК-05…ТК-08 — iot_sim з виправленням Q-08 (нотація Huawei/ATyS/TEDOM). Тести — `tests/stand/`
(`pytest -m stand`, клієнти: XML-RPC Odoo від користувача `u_energy`, REST емулятора з `SIM_API_TOKEN`).

| ТК | Назва | Кроки | Очікуваний результат | Де дивитися | AC |
|---|---|---|---|---|---|
| ТК-01 | Установка | `odoo-bin -d odoo_energy_test -i factory3d_energy --stop-after-init`; лог INFO | кроки хука 1–9 з кількостями §5.3, `install_report.state='done'`; колектор за ≤ 60 с отримує новий ETag, у `GET /f3d/telemetry/config` 68 джерел енергетики, 220 сигналів | лог; Налаштування → Завод 3D → Енергетика | AC-13, AC-73 |
| ТК-02 | Показання й профіль | `POST /sim/v1/mode {"mode":"follow_odoo"}`; 20 хв | 57 лічильників PM5560 `data_state='ok'`; ≥ 1 інтервал на кожен; `energy/totals/p_now` ≈ Σ фідерів емулятора ± 2 %; баланс годин `ok` | Енергетика → Лічильники, Профіль доби | AC-29 |
| ТК-03 | Зміна → кВт·год на МО | у Odoo: нове МО (BOM лінії A, 4 шт), запустити WO «Розкрій» на SAW-1 на 30 хв (кнопки Shop Floor), закрити; далі EDGE-1 20 хв | WO SAW-1 `f3d_energy_direct_kwh` = Σ `energy/consumers/SAW-1/p_now` × хв ± 3 % (`measured`), WO EDGE-1 так само; спільні `POOL-DUST`, `POOL-AIR`, `POOL-LIGHT` > 0 | МО → «Енергія», «Енергія на виробництво» | AC-88 |
| ТК-04 | Собівартість | категорію товару МО з ТК-03 перевести на AVCO (копія бази!), закрити МО | `extra_cost = f3d_energy_cost / qty`, `f3d_energy_locked`, чаттер; повторний `_cal_price` не змінює | форма МО | AC-46 |
| ТК-05 | Блекаут, варіант A | `factory3d.genset.amf_master=hgm`; `POST /sim/v1/scenario/blackout/start {"params":{"duration_s":600,"genset":true,"restore_delay_s":60}}` | ≤ 30 с: відключення відкрите (`amf_master` за режимом АВР), `transfer_s` 10…35; payload: `infra.totals.grid_kw=0`, `export_kw=0`, `shed_kw` 278 ± 30, `bess_mode='discharge'` під час пуску; міст — `island=true`; після 600 + 60 с — відключення закрите, `return_s` ≈ 60 | Енергетика → Відключення; 3D: картка ATS-1, вкладка «Енергія» | AC-56, AC-59, AC-89 |
| ТК-06 | Блекаут, варіант B: FAIL START | `amf_master=ats`; профіль `fake_relay` `d700_slow` (td_genset ТК-G04); `blackout {"duration_s":180,"amf_master":"ats"}`; якщо iot_sim без CI-01 — оркестратор td_genset: `PUT /sim/v1/signals/infra/ats/gen_start {"value":1,"hold_s":120}`, `src2_state=0` | через 35 ± 5 с після `gen_start=on` — `infra/ats/fail_start=1`, заявка «АВР: генератор не запустився (FAIL START)» на ATS-1, `outage.fail_start=True` | Заявки; Відключення | AC-57 |
| ТК-07 | Експорт СЕС у полудень | `POST /sim/v1/mode {"mode":"scenario"}`; `POST /time {"set":"2026-10-12T12:30:00+03:00"}`; 10 хв | `pv_now` = Σ інверторів ± 1 кВт > 600; `export_kw > 0`, `grid_kw = 0`; BESS `bess_kw` ≤ 200 і `bess_mode='charge'` (SOC < 100); `kwh_export` PM-Q2 росте; картка BESS «заряджається …» | 3D: «Власна генерація й резерв» | AC-90 |
| ТК-08 | Хмарно | `scenario/pv_cloudy/start {"params":{"cf":0.3,"duration_s":900}}` після ТК-07 | `pv_now` падає ≈ втричі, `bess_kw < 0` (розряд) або `grid_kw` росте; події немає (не поріг) | вкладка «Енергія» | — |
| ТК-09 | Договірна потужність | тариф демо: `contract_kw=300` (копія!) | за ≤ 20 хв `grid15_kw > 300` → заявка «Перевищення договірної потужності: … кВт при ліміті 300 кВт» на SWB-1, енергетик — підписник; повернути 800 → після наступного слоту `ok` | Заявки; Сигнали | AC-34 |
| ТК-10 | Лічильник недоступний | `POST /sim/v1/device/SAW-1-PM/fault {"reason":"comm"}`; 70 хв; `…/clear` | `PM-SAW-1` `stale`, подія «немає даних 60 хв»; інтервали чекають, далі `missing`; після `clear` — слоти пропуску `interpolated`, Σ `kwh` за пропуск = різниця показника лічильника ± 0,01 | Лічильники; Профіль | AC-22 |
| ТК-11 | Звірка адрес | `GET /sim/v1/signals?prefix=energy/consumers/` і `?device=PV-INV`; Odoo `last_value` | 5 PM5560: `kwh_total` vs Float32 2700 (`GET /signals/{code}` емулятора) `|Δ| ≤ 1`; SUN2000 `p_kw` ± 0,5 кВт; ATyS `position=pos_I` (2); TEDOM `chp_kw` ± 1 | Сигнали | AC-91 |
| ТК-12 | Переглядач | користувач `u_energy` відкриває 3D → «Енергія»; кіоск | KPI, трансформатори, профіль доби з годинами сьогодні, лінії, «Власна генерація й резерв», журнал подій — живі (`meta.sections.energy='live'`, `infra='live'`); у кіоску немає грн; зміна потужності SAW-1 (сценарій) — дельта ≤ 15 с | 3D | AC-63, AC-65 (MAN) |

### 13.3 Тести безпеки (ТБ)

- ТБ-01: користувач `base.group_user` без груп енергетики → `search` на `f3d.energy.node` → `AccessError`; меню
  «Енергетика» не видно (`test_menus`).
- ТБ-02: майстер читає `f3d_energy_cost`, `cost`, `price` → `AccessError` (AC-54); провайдер віддає payload без грн
  (AC-65).
- ТБ-03: запис уставок — `ValidationError` (AC-81); `f3d.command.create` на сигнал енергетики → `UserError` telemetry
  (бо `write_enabled=False`).
- ТБ-04: ін'єкції: код вузла `"SAW-1'; DROP TABLE f3d_energy_node;--"` → `ValidationError` (regex); `weekdays='0;1'` →
  `ValidationError`; адреса сигналу з ключем `_x` → помилка валідатора telemetry; усі SQL у `tools/` — параметризовані
  (`test_injection_codes` перевіряє, що `_cron_balance` з вузлом коду `X-1` не виконує зайвих запитів — `assertQueryCount`
  не вимагається; перевірка — `grep -rn "%s' %" tools/ models/` порожній у DoD).
- ТБ-05: `neutralize.sql` (AC-82); `action_f3d_energy_rebind` без `group_f3d_admin` (AC-14).
- ТБ-06: провайдери читають без `sudo`: користувач без доступу до `f3d.energy.node` → секція `denied` (viewer R-01), не
  виняток.

### 13.4 Тести продуктивності (ТП)

| ТП | Обсяг | Межа |
|---|---|---|
| ТП-01 | `_cron_build`: 67 лічильників × 2 доби (`f3d.reading` 57 × 2 880 + 10 × 576 точок) | ≤ 30 с, ≤ 200 SQL-запитів |
| ТП-02 | `_f3d_alloc_days` доби: 35 РЦ, 200 інтервалів завдань, 8 лічильників пулів | ≤ 5 с |
| ТП-03 | `build_energy` + `build_infra` на повних даних | ≤ 200 мс (UT, `time.perf_counter`) |
| ТП-04 | `_f3d_ingest` пакет 1 000 показань (500 енергетики) з перевизначенням M-15 vs без | приріст ≤ 15 % |
| ТП-05 | ротація 2,6 М рядків `f3d_energy_interval` (`generate_series`) | ≤ 60 с за прогін, `EXPLAIN` — Index Scan за `ts_start` |
| ТП-06 | `read_group` профілю за рік (pivot «Пік і вартість», 400 діб) | ≤ 3 с |

### 13.5 Чек-лист DEPLOY_TEST (`docs/modules/factory3d_energy/DEPLOY_TEST.md`, здає W6)

1. Дамп бази `odoo` тестового сервера → `odoo_energy_test`; переконатися, що telemetry `level0_migrated.state='done'`.
2. Установка (ТК-01), звіт хука, лог без ERROR.
3. **Етап 1 «один ввід і три фідери»**: адміністратор вимикає `read_enabled` усіх джерел енергетики, крім `MB-U01-PM-Q1`,
   `MB-U05-PM-QF-3`, `MB-U04-PM-QF-2`, `MB-U07-PM-QF-C1` і споживачів їхніх ліній (BW-3, BW-2, C1 — 21 джерело); через
   2 години: баланс Q1 і трьох фідерів `ok` (AC-92), профіль секції 1 і кВт·год завдань на РЦ BW-2/BW-3 — `measured`,
   решта РЦ — `estimate`.
4. **Етап 2 «весь ГРЩ»**: увімкнути решту джерел; через 2 години — баланс 8 вузлів `ok` (або `deviation` з причиною в
   протоколі), ТК-02.
5. ТК-03…ТК-12; UT на копії `--test-tags /factory3d_energy`.
6. Відкат: деінсталяція модуля на копії → сигнали без джерел, 87 мігрованих активні; повторна установка → ТК-01 зелений.
7. Видалити копію; робоча база `odoo` не змінювалась. Фактичні кількості — у CHANGELOG.

## 14. Definition of Done

- Усі UT §13.1 зелені на чистій базі й на копії демо (`--test-tags /factory3d_energy`); `test_data_sync.py` зелений.
- ТК-01…ТК-12 пройдені (ТК-05…ТК-08 — після виправлення iot_sim Q-08; до того — протокол з відміткою «блокер Q-08»
  за рішенням менеджера), протокол у `TEST_REPORT.md`; DEPLOY_TEST виконано.
- Кожен AC-01…AC-92 має зелений тест або відмітку ТК/MAN у протоколі.
- `ruff check` без помилок (довжина рядка 120); жодного `x_`-поля; рядки UI українською.
- `neutralize.sql` виконується (AC-82); стоп-крани перевірені (AC-80, AC-81).
- Перегляд безпеки: §13.3; SQL лише параметризований; грошові поля з `groups`.
- README (установка, параметри §3 ARCH, інструкції §4 ARCH), CHANGELOG `19.0.1.0.0`.
- Контракти CE-01…CE-09 реалізовані з точними іменами; зміни — через SPEC і повідомлення авторам td_genset/міст,
  viewer, machine_connect, iot_sim.

## 15. Відкриті питання

Ті самі Q-01…Q-20, що в ARCH §5.1; тут — що робить код, поки відповіді немає:

| ID | Поки немає відповіді |
|---|---|
| Q-01 | пули з драйверами (в): POOL-AIR/DUST/GANTRY — `kwh`, POOL-LIGHT/HVAC — `time`; котельня, зарядна, офіс, витяжки — `overhead` |
| Q-02 | TimescaleDB не використовується; `store_period_s` за Додатком C |
| Q-03 | тариф демо 8,40 цілодобово |
| Q-04 | `contract_kw=800` |
| Q-05 | ціна — тариф мережі (R-05) |
| Q-06 | `extra_cost` лише для FIFO/AVCO; для `standard` — чаттер |
| Q-07 | енергія простою — рядки `idle`, не на МО |
| Q-08 | адреси за документами вендорів (A-06); ТК-05…ТК-08 блоковані до виправлення iot_sim |
| Q-09 | стан вимикачів — регістр 2018 PM5560 (ПРИПУЩЕННЯ) |
| Q-10 | пороги температури трансформаторів 100/110 °C |
| Q-11 | допуск балансу 3 % / 2 кВт·год |
| Q-12 | асиметрія 10/20 %, cos φ 0,95/0,90 |
| Q-13 | генерація на секції 2, `ATS-1` — корінь під `SWB-1` |
| Q-14 | енергія від генератора — за тарифом |
| Q-15 | P 10 с, лічильники 60 с; сирі 30 діб, профіль 400 діб |
| Q-16 | «Огляд» — kanban/graph/pivot |
| Q-17 | `wordorder=big`; ТК-11 звіряє з Float32 2700 |
| Q-18 | портал → SAW-1…3, NEST-1; решта пулів — усі РЦ |
| Q-19 | календар «Зміна 1 (07:00–15:30)» |
| Q-20 | проводок немає; `extra_cost` + аналітика |

## Додаток A. Протокольні карти пристроїв енергетики (P-05, P-07)

Переглянуто 14.10.2026. Формат рядка Додатка C «Адреса»: `fc<n> <addr PDU> <type> [×scale] [map]` → JSON telemetry
A.1: `{"fc": n, "addr": addr, "type": type, "scale": scale?, "map": <карта A.2>?, "doc": "<вендор> <номер з документа> <назва>"}`;
`unit` — у `params` джерела (Додаток D.2). Порядок слів/байтів — `big` (умовчання telemetry).

### A.1 Регістри, які читає модуль

| Пристрій | Номер у документі | PDU | Тип | Масштаб | Одиниця | Сигнал(и) | Джерело документа |
|---|---|---|---|---|---|---|---|
| PM5560 | 3000–3001 / 3002–3003 / 3004–3005 | 2999 / 3001 / 3003 | f32 | 1 | А | `…/i_a`, `i_b`, `i_c` (вводи, фідери) | Schneider «PM5560/PM5563 Modbus Register List» (FAQ FA234017, https://www.se.com/ww/en/faqs/FA234017/); iot_sim §8.7.1 |
| PM5560 | 3010–3011 | 3009 | f32 | 1 | А | `…/i_now`, `energy/transformers/T*/i_a` | те саме |
| PM5560 | 3060–3061 | 3059 | f32 | 1 | кВт | `…/p_now`, `energy/transformers/T*/p_kw` | те саме |
| PM5560 | 3068–3069 | 3067 | f32 | 1 | квар | `energy/cells/Q*/q_kvar` | те саме |
| PM5560 | 3076–3077 | 3075 | f32 | 1 | кВА | `energy/transformers/T*/s_kva` | те саме |
| PM5560 | 3084–3085 | 3083 | f32 | 1 (R-02 п. 2) | — | `…/cos_phi` | те саме |
| PM5560 | 3204–3207 | 3203 | i64 | 0,001 | Вт·год → кВт·год | `…/kwh_total` | те саме; FAQ FA237865 «Formula to Calculate the Energy 64-bit INT in PM5000 Series» (https://www.se.com/ww/en/faqs/FA237865/, Q-17) |
| PM5560 | 3208–3211 | 3207 | i64 | 0,001 | Вт·год → кВт·год | `energy/cells/Q*/kwh_export` | те саме |
| PM5560 | 2018 (ПРИПУЩЕННЯ iot_sim) | 2017 | u16 | map `breaker` | — | `…/state` (вводи, фідери) | iot_sim §8.7.1 (Q-09) |
| SUN2000 | 32080–32081 | 32080 | i32 | 0,001 | кВт | `infra/pv/PV-INV-k/p_kw` | Huawei «SUN2000MB Modbus Interface Definitions» V200R023C10 Issue 02 (копія — https://community.jeedom.com/uploads/short-url/cEJpNRU5j3k0LvPW43eRU7nKzfr.pdf); iot_sim §8.9.1 |
| SUN2000 | 32089 | 32089 | u16 | map `pv_status` | — | `infra/pv/PV-INV-k/status` | те саме |
| SUN2000 | 32106–32107 | 32106 | u32 | 0,01 | кВт·год | `infra/pv/PV-INV-k/kwh_total` | те саме |
| SUN2000 | 32114–32115 | 32114 | u32 | 0,01 | кВт·год | `infra/pv/PV-INV-k/kwh_today` | те саме |
| LUNA2000 | 37000 | 37000 | u16 | map `bess_state` | — | `infra/bess/state` | iot_sim §8.9.2 (ПРИПУЩЕННЯ: https://support.huawei.com/enterprise/en/doc/EDOC1100311915) |
| LUNA2000 | 37001–37002 | 37001 | i32 | 0,001 | Вт → кВт (+ заряд) | `infra/totals/bess_kw` | те саме |
| LUNA2000 | 37004 | 37004 | u16 | 0,1 | % | `infra/totals/bess_soc` | те саме |
| LUNA2000 | 37014–37015 / 37016–37017 | 37014 / 37016 | u32 | 0,01 | кВт·год | `infra/bess/kwh_charge_total` / `kwh_discharge_total` | те саме |
| ATyS p | 20482 | 20482 | u16 | map `ats_mode` | — | `infra/ats/mode` | Socomec «ATyS p Instruction manual 542 001 D», Annexe III (https://www.nhp.com.au/public/assets/pim/Original/10043/Socomec-Transfer-Switch-ATyS-P-User-Manual.pdf); td_genset ARCH §1.1 |
| ATyS p | 20483 | 20483 | u16 | map `ats_position` | — | `infra/ats/position` | те саме |
| ATyS p | 20484 | 20484 | u16 | map `onoff` | — | `infra/ats/gen_start` | те саме |
| ATyS p | 20486 / 20487 | 20486 / 20487 | u16 | map `ats_source` | — | `infra/ats/src1_state` / `src2_state` | те саме |
| TEDOM | 40000 | 40000 | u16 | map `chp_state` | — | `infra/chp/state` | iot_sim §8.9.5 (ПРИПУЩЕННЯ, Q-08) |
| TEDOM | 40001 / 40002 | 40001 / 40002 | u16 | 1 | кВт | `infra/totals/chp_kw` / `infra/chp/heat_kw` | те саме |
| TEDOM | 40003 | 40003 | u16 | 0,1 | м³/год | `infra/chp/gas_m3h` | те саме |
| TEDOM | 40010–40011 | 40010 | u32 | 1 | год | `infra/chp/hours` | те саме |
| TEDOM | 40014–40015 | 40014 | u32 | 1 | кВт·год | `infra/chp/kwh_total` | те саме |
| ADAM-6015 u96 | 40001–40006 | 0…5 | u16 | R-20 telemetry | °C | `energy/transformers/T*/temp_c` | прив'язує telemetry (Додаток C.2) |

### A.2 Карти станів (`map`) і списки `states`

| Ім'я | `map` | `states` (індекс = `last_value`) | `alarm_states` |
|---|---|---|---|
| `breaker` | `{"0":"open","1":"closed","2":"tripped"}` | `["open","closed","tripped"]` | `["tripped"]` |
| `pv_status` | `{"0":"standby","1":"standby","2":"standby","3":"standby","256":"starting","512":"on_grid","513":"limited","768":"fault","769":"stopped","771":"no_grid","40960":"no_sun"}` | `["standby","starting","on_grid","limited","fault","stopped","no_grid","no_sun"]` | `["fault"]` |
| `bess_state` | `{"0":"offline","1":"standby","2":"running","3":"fault","4":"sleep"}` | `["offline","standby","running","fault","sleep"]` | `["fault"]` |
| `chp_state` | `{"0":"stop","1":"starting","2":"running","3":"fault","4":"cooling"}` | `["stop","starting","running","fault","cooling"]` | `["fault"]` |
| `ats_mode` | `{"0":"manual","1":"locked","16":"auto","32":"remote","64":"inhibit"}` | `["manual","locked","auto","remote","inhibit"]` | — |
| `ats_position` | `{"0":"unknown","1":"pos_0","2":"pos_I","3":"pos_II"}` | `["unknown","pos_0","pos_I","pos_II"]` | — |
| `onoff` | `{"0":"off","1":"on"}` | `["off","on"]` | — |
| `ats_source` | `{"0":"under","1":"present","2":"available"}` | `["under","present","available"]` | — |

## Додаток B. Вузли мережі (`data/energy_nodes.csv`, 123 рядки, з `plant/energy.py`, `plant/infra.py`)

Колонки: вид/тип шафи; батько (`parent`); обладнання (`equipment`, код `search_f3d`); РЦ; номінал; `p_inst_kw`;
`load_factor`; `idle_factor`; `cos_phi`; `p_inst_source`; роль у розподілі · пул; критичний; unit id стенда. Секції:
вузли під `SEC-1` (через предків) — `section=1`, під `SEC-2` — 2; `QS` — 0 (з'єднує, `peer=SEC-2`); шафи —
`cabinet=SWB-1`, `sequence` 10, 20 (`Q1`), …, 110 (`PFC-2`) у порядку `SWB_CELLS`; `RM6-1`, `GRID-10KV` —
`voltage_kv=10`; `note`, `group` — з макета (`consumers()[code].note/group`).

| № | Код | Вид | Живиться від | Обладнання | РЦ | Номінал | P вст., кВт | kf | idle | cos φ | Джерело | Роль · пул | Крит. | unit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `GRID-10KV` | input | — | — | — | — | — | — | — | — | — | — | — | — |
| 2 | `RM6-1` | substation | GRID-10KV | RM6-1 | — | — | — | — | — | — | — | — | — | — |
| 3 | `T1` | transformer | RM6-1 | T1 | — | 1000 кВА | — | — | — | — | — | — | — | — |
| 4 | `T2` | transformer | RM6-1 | T2 | — | 1000 кВА | — | — | — | — | — | — | — | — |
| 5 | `SWB-1` | switchboard | — | SWB-1 | — | — | — | — | — | — | — | — | — | — |
| 6 | `Q1` | cell/incomer | T1 | Q1 | — | 1600 А | — | — | — | — | — | — | — | — |
| 7 | `Q2` | cell/incomer | T2 | Q2 | — | 1600 А | — | — | — | — | — | — | — | — |
| 8 | `SEC-1` | section | Q1 | — | — | — | — | — | — | — | — | — | — | — |
| 9 | `SEC-2` | section | Q2 | — | — | — | — | — | — | — | — | — | — | — |
| 10 | `PFC-1` | cell/pfc | SEC-1 | PFC-1 | — | 350 квар | — | — | — | — | — | — | — | — |
| 11 | `QF-3` | cell/feeder | SEC-1 | QF-3 | — | 630 А | — | — | — | — | — | — | — | — |
| 12 | `QF-2` | cell/feeder | SEC-1 | QF-2 | — | 630 А | — | — | — | — | — | — | — | — |
| 13 | `QF-C1` | cell/cable | SEC-1 | QF-C1 | — | 630 А | — | — | — | — | — | — | — | — |
| 14 | `QS` | cell/coupler | SEC-1 | QS | — | 1600 А | — | — | — | — | — | — | — | — |
| 15 | `QF-1` | cell/feeder | SEC-2 | QF-1 | — | 630 А | — | — | — | — | — | — | — | — |
| 16 | `QF-4` | cell/feeder | SEC-2 | QF-4 | — | 630 А | — | — | — | — | — | — | — | — |
| 17 | `QF-C2` | cell/cable | SEC-2 | QF-C2 | — | 400 А | — | — | — | — | — | — | — | — |
| 18 | `PFC-2` | cell/pfc | SEC-2 | PFC-2 | — | 350 квар | — | — | — | — | — | — | — | — |
| 19 | `BW-1` | line/busway | QF-1 | BW-1 | — | 630 А | — | — | — | — | — | — | так | — |
| 20 | `BW-2` | line/busway | QF-2 | BW-2 | — | 630 А | — | — | — | — | — | — | — | — |
| 21 | `BW-3` | line/busway | QF-3 | BW-3 | — | 630 А | — | — | — | — | — | — | — | — |
| 22 | `BW-4` | line/busway | QF-4 | BW-4 | — | 630 А | — | — | — | — | — | — | — | — |
| 23 | `C1` | line/cable | QF-C1 | — | — | 630 А | — | — | — | — | — | — | — | — |
| 24 | `C2` | line/cable | QF-C2 | — | — | 400 А | — | — | — | — | — | — | — | — |
| 25 | `TAP-SAW-1` | tapoff | BW-1 | — | — | — | — | — | — | — | — | — | — | — |
| 26 | `TAP-SAW-2` | tapoff | BW-1 | — | — | — | — | — | — | — | — | — | — | — |
| 27 | `TAP-SAW-3` | tapoff | BW-2 | — | — | — | — | — | — | — | — | — | — | — |
| 28 | `TAP-SLIDE-1` | tapoff | BW-2 | — | — | — | — | — | — | — | — | — | — | — |
| 29 | `TAP-VSAW-1` | tapoff | BW-2 | — | — | — | — | — | — | — | — | — | — | — |
| 30 | `TAP-NEST-1` | tapoff | BW-2 | — | — | — | — | — | — | — | — | — | — | — |
| 31 | `TAP-EDGE-1` | tapoff | BW-1 | — | — | — | — | — | — | — | — | — | — | — |
| 32 | `TAP-EDGE-2` | tapoff | BW-1 | — | — | — | — | — | — | — | — | — | — | — |
| 33 | `TAP-EDGE-3` | tapoff | BW-2 | — | — | — | — | — | — | — | — | — | — | — |
| 34 | `TAP-CNC-3` | tapoff | BW-2 | — | — | — | — | — | — | — | — | — | — | — |
| 35 | `TAP-CNC-1` | tapoff | BW-1 | — | — | — | — | — | — | — | — | — | — | — |
| 36 | `TAP-CNC-2` | tapoff | BW-1 | — | — | — | — | — | — | — | — | — | — | — |
| 37 | `TAP-BORE-1` | tapoff | BW-2 | — | — | — | — | — | — | — | — | — | — | — |
| 38 | `TAP-CNC-4` | tapoff | BW-2 | — | — | — | — | — | — | — | — | — | — | — |
| 39 | `TAP-DOWEL-1` | tapoff | BW-2 | — | — | — | — | — | — | — | — | — | — | — |
| 40 | `TAP-SORT-1` | tapoff | BW-1 | — | — | — | — | — | — | — | — | — | — | — |
| 41 | `TAP-SAND-1` | tapoff | BW-3 | — | — | — | — | — | — | — | — | — | — | — |
| 42 | `TAP-AUTOSPRAY-1` | tapoff | BW-3 | — | — | — | — | — | — | — | — | — | — | — |
| 43 | `TAP-UV-1` | tapoff | BW-3 | — | — | — | — | — | — | — | — | — | — | — |
| 44 | `TAP-HINGE-1` | tapoff | BW-3 | — | — | — | — | — | — | — | — | — | — | — |
| 45 | `TAP-GLUE-1` | tapoff | BW-3 | — | — | — | — | — | — | — | — | — | — | — |
| 46 | `TAP-PRESS-1` | tapoff | BW-3 | — | — | — | — | — | — | — | — | — | — | — |
| 47 | `TAP-SPRAY-1` | tapoff | BW-3 | — | — | — | — | — | — | — | — | — | — | — |
| 48 | `TAP-DRY-1` | tapoff | BW-3 | — | — | — | — | — | — | — | — | — | — | — |
| 49 | `TAP-ASMLINE-1` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 50 | `TAP-ASM-1` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 51 | `TAP-ASM-2` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 52 | `TAP-ASM-3` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 53 | `TAP-ASM-4` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 54 | `TAP-ASM-5` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 55 | `TAP-ASM-6` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 56 | `TAP-PACK-1` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 57 | `TAP-PACK-2` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 58 | `TAP-BOX-1` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 59 | `TAP-PACKLINE-1` | tapoff | BW-4 | — | — | — | — | — | — | — | — | — | — | — |
| 60 | `TAP-GANTRY-1` | tapoff | BW-2 | — | — | — | — | — | — | — | — | — | — | — |
| 61 | `SAW-1` | consumer | TAP-SAW-1 | SAW-1 | SAW-1 | — | 24 | 0.55 | 0.12 | 0.84 | estimate | direct | — | 11 |
| 62 | `SAW-2` | consumer | TAP-SAW-2 | SAW-2 | SAW-2 | — | 24 | 0.55 | 0.12 | 0.84 | estimate | direct | — | 12 |
| 63 | `SAW-3` | consumer | TAP-SAW-3 | SAW-3 | SAW-3 | — | 45 | 0.6 | 0.12 | 0.84 | estimate | direct | — | 13 |
| 64 | `SLIDE-1` | consumer | TAP-SLIDE-1 | SLIDE-1 | SLIDE-1 | — | 7.5 | 0.45 | 0.12 | 0.82 | estimate | direct | — | 14 |
| 65 | `VSAW-1` | consumer | TAP-VSAW-1 | VSAW-1 | VSAW-1 | — | 7.3 | 0.4 | 0.12 | 0.82 | passport | direct | — | 15 |
| 66 | `NEST-1` | consumer | TAP-NEST-1 | NEST-1 | NEST-1 | — | 39 | 0.55 | 0.12 | 0.9 | passport | direct | — | 16 |
| 67 | `EDGE-1` | consumer | TAP-EDGE-1 | EDGE-1 | EDGE-1 | — | 67.5 | 0.65 | 0.3 | 0.9 | estimate | direct | — | 17 |
| 68 | `EDGE-2` | consumer | TAP-EDGE-2 | EDGE-2 | EDGE-2 | — | 28 | 0.65 | 0.3 | 0.9 | estimate | direct | — | 18 |
| 69 | `EDGE-3` | consumer | TAP-EDGE-3 | EDGE-3 | EDGE-3 | — | 28 | 0.65 | 0.3 | 0.9 | estimate | direct | — | 19 |
| 70 | `CNC-3` | consumer | TAP-CNC-3 | CNC-3 | CNC-3 | — | 22 | 0.5 | 0.12 | 0.9 | estimate | direct | — | 20 |
| 71 | `CNC-1` | consumer | TAP-CNC-1 | CNC-1 | CNC-1 | — | 22 | 0.5 | 0.12 | 0.9 | estimate | direct | — | 21 |
| 72 | `CNC-2` | consumer | TAP-CNC-2 | CNC-2 | CNC-2 | — | 22 | 0.5 | 0.12 | 0.9 | estimate | direct | — | 22 |
| 73 | `BORE-1` | consumer | TAP-BORE-1 | BORE-1 | BORE-1 | — | 19.5 | 0.5 | 0.12 | 0.88 | passport | direct | — | 23 |
| 74 | `CNC-4` | consumer | TAP-CNC-4 | CNC-4 | CNC-4 | — | 22 | 0.5 | 0.12 | 0.9 | estimate | direct | — | 24 |
| 75 | `DOWEL-1` | consumer | TAP-DOWEL-1 | DOWEL-1 | DOWEL-1 | — | 11 | 0.45 | 0.12 | 0.86 | passport | direct | — | 25 |
| 76 | `SORT-1` | consumer | TAP-SORT-1 | SORT-1 | SORT-1 | — | 20 | 0.45 | 0.12 | 0.9 | estimate | direct | — | 26 |
| 77 | `SAND-1` | consumer | TAP-SAND-1 | SAND-1 | SAND-1 | — | 30 | 0.7 | 0.12 | 0.85 | estimate | direct | — | 27 |
| 78 | `AUTOSPRAY-1` | consumer | TAP-AUTOSPRAY-1 | AUTOSPRAY-1 | AUTOSPRAY-1 | — | 18 | 0.6 | 0.12 | 0.88 | passport | direct | — | 28 |
| 79 | `UV-1` | consumer | TAP-UV-1 | UV-1 | UV-1 | — | 58.9 | 0.7 | 0.08 | 0.95 | passport | direct | — | 29 |
| 80 | `HINGE-1` | consumer | TAP-HINGE-1 | HINGE-1 | HINGE-1 | — | 1.1 | 0.3 | 0.12 | 0.85 | passport | direct | — | 30 |
| 81 | `GLUE-1` | consumer | TAP-GLUE-1 | GLUE-1 | GLUE-1 | — | 2.2 | 0.7 | 0.12 | 0.85 | passport | direct | — | 31 |
| 82 | `PRESS-1` | consumer | TAP-PRESS-1 | PRESS-1 | PRESS-1 | — | 28 | 0.6 | 0.35 | 0.97 | passport | direct | — | 32 |
| 83 | `SPRAY-1` | consumer | TAP-SPRAY-1 | SPRAY-1 | SPRAY-1 | — | 5.1 | 0.75 | 0.12 | 0.85 | passport | direct | — | 33 |
| 84 | `DRY-1` | consumer | TAP-DRY-1 | DRY-1 | DRY-1 | — | 17 | 0.75 | 0.6 | 0.95 | passport | direct | — | 34 |
| 85 | `ASMLINE-1` | consumer | TAP-ASMLINE-1 | ASMLINE-1 | ASMLINE-1 | — | 8 | 0.4 | 0.12 | 0.86 | estimate | direct | — | 35 |
| 86 | `ASM-1` | consumer | TAP-ASM-1 | ASM-1 | ASM-1 | — | 1.5 | 0.35 | 0.12 | 0.85 | estimate | direct | — | 36 |
| 87 | `ASM-2` | consumer | TAP-ASM-2 | ASM-2 | ASM-2 | — | 1.5 | 0.35 | 0.12 | 0.85 | estimate | direct | — | 37 |
| 88 | `ASM-3` | consumer | TAP-ASM-3 | ASM-3 | ASM-3 | — | 1.5 | 0.35 | 0.12 | 0.85 | estimate | direct | — | 38 |
| 89 | `ASM-4` | consumer | TAP-ASM-4 | ASM-4 | ASM-4 | — | 1.5 | 0.35 | 0.12 | 0.85 | estimate | direct | — | 39 |
| 90 | `ASM-5` | consumer | TAP-ASM-5 | ASM-5 | ASM-5 | — | 1.5 | 0.35 | 0.12 | 0.85 | estimate | direct | — | 40 |
| 91 | `ASM-6` | consumer | TAP-ASM-6 | ASM-6 | ASM-6 | — | 1.5 | 0.35 | 0.12 | 0.85 | estimate | direct | — | 41 |
| 92 | `PACK-1` | consumer | TAP-PACK-1 | PACK-1 | PACK-1 | — | 1.9 | 0.4 | 0.12 | 0.85 | passport | direct | — | 42 |
| 93 | `PACK-2` | consumer | TAP-PACK-2 | PACK-2 | PACK-2 | — | 1.9 | 0.4 | 0.12 | 0.85 | passport | direct | — | 43 |
| 94 | `BOX-1` | consumer | TAP-BOX-1 | BOX-1 | BOX-1 | — | 10 | 0.45 | 0.12 | 0.88 | passport | direct | — | 44 |
| 95 | `PACKLINE-1` | consumer | TAP-PACKLINE-1 | PACKLINE-1 | PACKLINE-1 | — | 19.9 | 0.65 | 0.12 | 0.97 | passport | direct | — | 45 |
| 96 | `GANTRY-1` | consumer | TAP-GANTRY-1 | GANTRY-1 | — | — | 15 | 0.347 | — | 0.86 | estimate | shared · POOL-GANTRY | — | 46 |
| 97 | `COMPRESSOR` | consumer | C1 | COMPRESSOR | — | — | 74 | 0.63 | — | 0.95 | passport | shared · POOL-AIR | так | 47 |
| 98 | `DUST-1` | consumer | C1 | DUST-1 | — | — | 150 | 0.85 | — | 0.88 | estimate | shared · POOL-DUST | так | 48 |
| 99 | `BOILER` | consumer | C1 | BOILER | — | — | 25 | 0.4 | — | 0.85 | estimate | overhead | так | 49 |
| 100 | `CHARGING` | consumer | C2 | CHARGING | — | — | 13.5 | 0.667 | — | 0.95 | estimate | overhead | — | 50 |
| 101 | `OFFICE` | consumer | C2 | — | — | — | 32.0 | 0.55 | — | 0.92 | estimate | overhead | так | 51 |
| 102 | `LP-1` | consumer | C2 | LP-1 | — | — | 6.3 | 0.889 | — | 0.95 | passport | shared · POOL-LIGHT | так | 52 |
| 103 | `LP-2` | consumer | C2 | LP-2 | — | — | 23.2 | 1.0 | — | 0.95 | passport | shared · POOL-LIGHT | так | 53 |
| 104 | `LP-3` | consumer | C2 | LP-3 | — | — | 10.8 | 0.88 | — | 0.95 | passport | shared · POOL-LIGHT | так | 54 |
| 105 | `RV-ALL` | consumer | C2 | — | — | — | 215.0 | 0.386 | — | 0.95 | passport | shared · POOL-HVAC | — | 55 |
| 106 | `AHU-1` | consumer | C2 | AHU-1 | — | — | 15.0 | 0.62 | — | 0.95 | estimate | shared · POOL-HVAC | — | 56 |
| 107 | `EF-ELEC` | consumer | C2 | EF-ELEC | — | — | 0.84 | 1.0 | — | 0.95 | passport | overhead | так | 57 |
| 108 | `EF-CMP` | consumer | C2 | EF-CMP | — | — | 0.42 | 0.0 | — | 0.95 | passport | overhead | — | 58 |
| 109 | `EF-CHG` | consumer | C2 | EF-CHG | — | — | 0.178 | 0.601 | — | 0.95 | passport | overhead | так | 59 |
| 110 | `PV-INV` | generator/pv_inverters | SEC-2 | PV-INV | — | — | 920 | — | — | — | — | — | — | — |
| 111 | `PV-INV-1` | generator/pv_inverter | PV-INV | PV-INV | — | — | 115 | — | — | — | — | — | — | 61 |
| 112 | `PV-INV-2` | generator/pv_inverter | PV-INV | PV-INV | — | — | 115 | — | — | — | — | — | — | 62 |
| 113 | `PV-INV-3` | generator/pv_inverter | PV-INV | PV-INV | — | — | 115 | — | — | — | — | — | — | 63 |
| 114 | `PV-INV-4` | generator/pv_inverter | PV-INV | PV-INV | — | — | 115 | — | — | — | — | — | — | 64 |
| 115 | `PV-INV-5` | generator/pv_inverter | PV-INV | PV-INV | — | — | 115 | — | — | — | — | — | — | 65 |
| 116 | `PV-INV-6` | generator/pv_inverter | PV-INV | PV-INV | — | — | 115 | — | — | — | — | — | — | 66 |
| 117 | `PV-INV-7` | generator/pv_inverter | PV-INV | PV-INV | — | — | 115 | — | — | — | — | — | — | 67 |
| 118 | `PV-INV-8` | generator/pv_inverter | PV-INV | PV-INV | — | — | 115 | — | — | — | — | — | — | 68 |
| 119 | `PV-ROOF` | generator/pv_field | PV-INV | PV-ROOF | — | — | 900 | — | — | — | — | — | — | — |
| 120 | `CHP` | generator/chp | SEC-2 | CHP | — | — | 800 | — | — | — | — | — | — | 72 |
| 121 | `BESS` | storage | SEC-2 | BESS | — | — | 200 | — | — | — | — | — | — | 69 |
| 122 | `ATS-1` | ats | SWB-1 | ATS-1 | — | — | — | — | — | — | — | — | — | 71 |
| 123 | `GENSET` | generator/genset | ATS-1 | GENSET | — | — | 507 | — | — | — | — | — | — | — |
## Додаток C. Сигнали зони енергетики (`data/energy_signals.csv`, 297 рядків)

### C.1 Правила колонок

- «Як»: **D** — з пристрою (колектор, джерело Modbus), **E** — обчислює модуль (CT-10 на `EN-DERIVED`), **T** — адресу
  ставить telemetry, модуль — лише пороги (`binding='thresholds'`).
- «Період/зберігання» — `period_s`/`store_period_s` (0 — кожне показання).
- «Походження» — при створенні: `sim_data` (існує з міграції рівня 0, не змінюється), `catalog` (рядок каталогу iot_sim,
  створюється з `origin='catalog'`), `energy` (власний, `origin='module'`).
- `name` при створенні: `<назва вузла>: <величина>` — `p_now` «потужність», `kwh_total` «лічильник енергії», `kwh_shift`
  «енергія за зміну», `kwh_export` «віддано в мережу», `i_now` «струм», `i_a/i_b/i_c` «струм фази A/B/C», `cos_phi`
  «cos φ», `q_kvar` «реактивна потужність», `s_kva` «повна потужність», `state` «стан автомата», `imbalance_pct`
  «небаланс обліку», `i_unbal_pct` «асиметрія струмів»; для `infra/*` — «СЕС PV-INV-k: потужність / стан / за добу /
  накопичено», «Накопичувач: …», «КГУ: …», «АВР: …»; `quantity` — «Потужність», «Енергія», «Струм», «cos φ», «Стан»…;
  у наявних (`sim_data`) `name` і `quantity` не змінюються.
- `decimals`: кВт 2; кВт·год 3 (`kwh_total`, `kwh_export`, лічильники BESS/КГУ/СЕС) і 2 (`kwh_shift`, `kwh_today`); А 0;
  квар 1; кВА 0; °C 1; % 2; cos φ 2; стани 0; год 0.
- `viewer_visible` — колонка «3D».

### C.2 Заголовки заявок (`alarm_title`) і параметри порогів

| Група сигналів | `alarm_title` | `hysteresis` | `min_duration_s` |
|---|---|---|---|
| `energy/lines/*/i_now`, `energy/cells/*/i_now` | «{equipment}: струм {value} А при номіналі {threshold} А» | 5 | 60 |
| `energy/transformers/*/s_kva` | «Перевантаження трансформатора {code}: {value} кВА при номіналі {threshold}» | 10 | 60 |
| `energy/transformers/*/temp_c` | «Перегрів трансформатора {code}: {value} °C при нормі до {threshold}» | 2 | 60 |
| `energy/lines/*/cos_phi` | — (лише `warn`) | 0,01 | 900 |
| `energy/totals/cos_phi` | «Низький cos φ на вводах: {value} при нормі від {threshold}» | 0,01 | 900 |
| `*/i_unbal_pct` | «Асиметрія струмів {code}: {value} % при нормі до {threshold}» | 1 | 900 |
| `*/imbalance_pct` | «Небаланс обліку {code}: {value} % при допуску {threshold}» | 0 | 3600 |
| `energy/totals/grid15_kw` | «Перевищення договірної потужності: {value} кВт при ліміті {threshold} кВт» | 0 | 0 |
| `*/state` (вимикачі) | «{equipment}: автомат вимкнувся аварійно» | — | 0 |
| `infra/pv/*/status` | «Інвертор СЕС {equipment}: аварійна зупинка ({text})» | — | 60 |
| `infra/bess/state`, `infra/chp/state` | «{equipment}: аварія ({text})» | — | 30 |
| `infra/chp/hours` | «КГУ: {value} мотогодин — капремонт при {threshold}» | 0 | 0 |
| `infra/ats/fail_start` | «АВР: генератор не запустився (FAIL START)» | 0 | 0 |

### C.3 Перелік

| № | Код | Як | Джерело | Адреса / правило | Вид | Од. | Період/зберіг. | Пороги | Походження | 3D | Обладнання |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `energy/consumers/SAW-1/p_now` | D | `MB-U11-PM-SAW-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | SAW-1 |
| 2 | `energy/consumers/SAW-1/kwh_total` | D | `MB-U11-PM-SAW-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | SAW-1 |
| 3 | `energy/consumers/SAW-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | SAW-1 |
| 4 | `energy/consumers/SAW-2/p_now` | D | `MB-U12-PM-SAW-2` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | SAW-2 |
| 5 | `energy/consumers/SAW-2/kwh_total` | D | `MB-U12-PM-SAW-2` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | SAW-2 |
| 6 | `energy/consumers/SAW-2/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | SAW-2 |
| 7 | `energy/consumers/SAW-3/p_now` | D | `MB-U13-PM-SAW-3` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | SAW-3 |
| 8 | `energy/consumers/SAW-3/kwh_total` | D | `MB-U13-PM-SAW-3` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | SAW-3 |
| 9 | `energy/consumers/SAW-3/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | SAW-3 |
| 10 | `energy/consumers/SLIDE-1/p_now` | D | `MB-U14-PM-SLIDE-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | SLIDE-1 |
| 11 | `energy/consumers/SLIDE-1/kwh_total` | D | `MB-U14-PM-SLIDE-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | SLIDE-1 |
| 12 | `energy/consumers/SLIDE-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | SLIDE-1 |
| 13 | `energy/consumers/VSAW-1/p_now` | D | `MB-U15-PM-VSAW-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | VSAW-1 |
| 14 | `energy/consumers/VSAW-1/kwh_total` | D | `MB-U15-PM-VSAW-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | VSAW-1 |
| 15 | `energy/consumers/VSAW-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | VSAW-1 |
| 16 | `energy/consumers/NEST-1/p_now` | D | `MB-U16-PM-NEST-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | NEST-1 |
| 17 | `energy/consumers/NEST-1/kwh_total` | D | `MB-U16-PM-NEST-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | NEST-1 |
| 18 | `energy/consumers/NEST-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | NEST-1 |
| 19 | `energy/consumers/EDGE-1/p_now` | D | `MB-U17-PM-EDGE-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | EDGE-1 |
| 20 | `energy/consumers/EDGE-1/kwh_total` | D | `MB-U17-PM-EDGE-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | EDGE-1 |
| 21 | `energy/consumers/EDGE-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | EDGE-1 |
| 22 | `energy/consumers/EDGE-2/p_now` | D | `MB-U18-PM-EDGE-2` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | EDGE-2 |
| 23 | `energy/consumers/EDGE-2/kwh_total` | D | `MB-U18-PM-EDGE-2` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | EDGE-2 |
| 24 | `energy/consumers/EDGE-2/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | EDGE-2 |
| 25 | `energy/consumers/EDGE-3/p_now` | D | `MB-U19-PM-EDGE-3` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | EDGE-3 |
| 26 | `energy/consumers/EDGE-3/kwh_total` | D | `MB-U19-PM-EDGE-3` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | EDGE-3 |
| 27 | `energy/consumers/EDGE-3/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | EDGE-3 |
| 28 | `energy/consumers/CNC-3/p_now` | D | `MB-U20-PM-CNC-3` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | CNC-3 |
| 29 | `energy/consumers/CNC-3/kwh_total` | D | `MB-U20-PM-CNC-3` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | CNC-3 |
| 30 | `energy/consumers/CNC-3/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | CNC-3 |
| 31 | `energy/consumers/CNC-1/p_now` | D | `MB-U21-PM-CNC-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | CNC-1 |
| 32 | `energy/consumers/CNC-1/kwh_total` | D | `MB-U21-PM-CNC-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | CNC-1 |
| 33 | `energy/consumers/CNC-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | CNC-1 |
| 34 | `energy/consumers/CNC-2/p_now` | D | `MB-U22-PM-CNC-2` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | CNC-2 |
| 35 | `energy/consumers/CNC-2/kwh_total` | D | `MB-U22-PM-CNC-2` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | CNC-2 |
| 36 | `energy/consumers/CNC-2/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | CNC-2 |
| 37 | `energy/consumers/BORE-1/p_now` | D | `MB-U23-PM-BORE-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | BORE-1 |
| 38 | `energy/consumers/BORE-1/kwh_total` | D | `MB-U23-PM-BORE-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | BORE-1 |
| 39 | `energy/consumers/BORE-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | BORE-1 |
| 40 | `energy/consumers/CNC-4/p_now` | D | `MB-U24-PM-CNC-4` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | CNC-4 |
| 41 | `energy/consumers/CNC-4/kwh_total` | D | `MB-U24-PM-CNC-4` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | CNC-4 |
| 42 | `energy/consumers/CNC-4/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | CNC-4 |
| 43 | `energy/consumers/DOWEL-1/p_now` | D | `MB-U25-PM-DOWEL-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | DOWEL-1 |
| 44 | `energy/consumers/DOWEL-1/kwh_total` | D | `MB-U25-PM-DOWEL-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | DOWEL-1 |
| 45 | `energy/consumers/DOWEL-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | DOWEL-1 |
| 46 | `energy/consumers/SORT-1/p_now` | D | `MB-U26-PM-SORT-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | SORT-1 |
| 47 | `energy/consumers/SORT-1/kwh_total` | D | `MB-U26-PM-SORT-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | SORT-1 |
| 48 | `energy/consumers/SORT-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | SORT-1 |
| 49 | `energy/consumers/SAND-1/p_now` | D | `MB-U27-PM-SAND-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | SAND-1 |
| 50 | `energy/consumers/SAND-1/kwh_total` | D | `MB-U27-PM-SAND-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | SAND-1 |
| 51 | `energy/consumers/SAND-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | SAND-1 |
| 52 | `energy/consumers/AUTOSPRAY-1/p_now` | D | `MB-U28-PM-AUTOSPRAY-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | AUTOSPRAY-1 |
| 53 | `energy/consumers/AUTOSPRAY-1/kwh_total` | D | `MB-U28-PM-AUTOSPRAY-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | AUTOSPRAY-1 |
| 54 | `energy/consumers/AUTOSPRAY-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | AUTOSPRAY-1 |
| 55 | `energy/consumers/UV-1/p_now` | D | `MB-U29-PM-UV-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | UV-1 |
| 56 | `energy/consumers/UV-1/kwh_total` | D | `MB-U29-PM-UV-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | UV-1 |
| 57 | `energy/consumers/UV-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | UV-1 |
| 58 | `energy/consumers/HINGE-1/p_now` | D | `MB-U30-PM-HINGE-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | HINGE-1 |
| 59 | `energy/consumers/HINGE-1/kwh_total` | D | `MB-U30-PM-HINGE-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | HINGE-1 |
| 60 | `energy/consumers/HINGE-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | HINGE-1 |
| 61 | `energy/consumers/GLUE-1/p_now` | D | `MB-U31-PM-GLUE-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | GLUE-1 |
| 62 | `energy/consumers/GLUE-1/kwh_total` | D | `MB-U31-PM-GLUE-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | GLUE-1 |
| 63 | `energy/consumers/GLUE-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | GLUE-1 |
| 64 | `energy/consumers/PRESS-1/p_now` | D | `MB-U32-PM-PRESS-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | PRESS-1 |
| 65 | `energy/consumers/PRESS-1/kwh_total` | D | `MB-U32-PM-PRESS-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | PRESS-1 |
| 66 | `energy/consumers/PRESS-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | PRESS-1 |
| 67 | `energy/consumers/SPRAY-1/p_now` | D | `MB-U33-PM-SPRAY-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | SPRAY-1 |
| 68 | `energy/consumers/SPRAY-1/kwh_total` | D | `MB-U33-PM-SPRAY-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | SPRAY-1 |
| 69 | `energy/consumers/SPRAY-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | SPRAY-1 |
| 70 | `energy/consumers/DRY-1/p_now` | D | `MB-U34-PM-DRY-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | DRY-1 |
| 71 | `energy/consumers/DRY-1/kwh_total` | D | `MB-U34-PM-DRY-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | DRY-1 |
| 72 | `energy/consumers/DRY-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | DRY-1 |
| 73 | `energy/consumers/ASMLINE-1/p_now` | D | `MB-U35-PM-ASMLINE-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | ASMLINE-1 |
| 74 | `energy/consumers/ASMLINE-1/kwh_total` | D | `MB-U35-PM-ASMLINE-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | ASMLINE-1 |
| 75 | `energy/consumers/ASMLINE-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | ASMLINE-1 |
| 76 | `energy/consumers/ASM-1/p_now` | D | `MB-U36-PM-ASM-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | ASM-1 |
| 77 | `energy/consumers/ASM-1/kwh_total` | D | `MB-U36-PM-ASM-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | ASM-1 |
| 78 | `energy/consumers/ASM-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | ASM-1 |
| 79 | `energy/consumers/ASM-2/p_now` | D | `MB-U37-PM-ASM-2` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | ASM-2 |
| 80 | `energy/consumers/ASM-2/kwh_total` | D | `MB-U37-PM-ASM-2` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | ASM-2 |
| 81 | `energy/consumers/ASM-2/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | ASM-2 |
| 82 | `energy/consumers/ASM-3/p_now` | D | `MB-U38-PM-ASM-3` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | ASM-3 |
| 83 | `energy/consumers/ASM-3/kwh_total` | D | `MB-U38-PM-ASM-3` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | ASM-3 |
| 84 | `energy/consumers/ASM-3/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | ASM-3 |
| 85 | `energy/consumers/ASM-4/p_now` | D | `MB-U39-PM-ASM-4` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | ASM-4 |
| 86 | `energy/consumers/ASM-4/kwh_total` | D | `MB-U39-PM-ASM-4` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | ASM-4 |
| 87 | `energy/consumers/ASM-4/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | ASM-4 |
| 88 | `energy/consumers/ASM-5/p_now` | D | `MB-U40-PM-ASM-5` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | ASM-5 |
| 89 | `energy/consumers/ASM-5/kwh_total` | D | `MB-U40-PM-ASM-5` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | ASM-5 |
| 90 | `energy/consumers/ASM-5/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | ASM-5 |
| 91 | `energy/consumers/ASM-6/p_now` | D | `MB-U41-PM-ASM-6` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | ASM-6 |
| 92 | `energy/consumers/ASM-6/kwh_total` | D | `MB-U41-PM-ASM-6` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | ASM-6 |
| 93 | `energy/consumers/ASM-6/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | ASM-6 |
| 94 | `energy/consumers/PACK-1/p_now` | D | `MB-U42-PM-PACK-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | PACK-1 |
| 95 | `energy/consumers/PACK-1/kwh_total` | D | `MB-U42-PM-PACK-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | PACK-1 |
| 96 | `energy/consumers/PACK-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | PACK-1 |
| 97 | `energy/consumers/PACK-2/p_now` | D | `MB-U43-PM-PACK-2` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | PACK-2 |
| 98 | `energy/consumers/PACK-2/kwh_total` | D | `MB-U43-PM-PACK-2` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | PACK-2 |
| 99 | `energy/consumers/PACK-2/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | PACK-2 |
| 100 | `energy/consumers/BOX-1/p_now` | D | `MB-U44-PM-BOX-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | BOX-1 |
| 101 | `energy/consumers/BOX-1/kwh_total` | D | `MB-U44-PM-BOX-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | BOX-1 |
| 102 | `energy/consumers/BOX-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | BOX-1 |
| 103 | `energy/consumers/PACKLINE-1/p_now` | D | `MB-U45-PM-PACKLINE-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | PACKLINE-1 |
| 104 | `energy/consumers/PACKLINE-1/kwh_total` | D | `MB-U45-PM-PACKLINE-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | PACKLINE-1 |
| 105 | `energy/consumers/PACKLINE-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | PACKLINE-1 |
| 106 | `energy/consumers/GANTRY-1/p_now` | D | `MB-U46-PM-GANTRY-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | GANTRY-1 |
| 107 | `energy/consumers/GANTRY-1/kwh_total` | D | `MB-U46-PM-GANTRY-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | GANTRY-1 |
| 108 | `energy/consumers/GANTRY-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | GANTRY-1 |
| 109 | `energy/consumers/COMPRESSOR/p_now` | D | `MB-U47-PM-COMPRESSOR` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | COMPRESSOR |
| 110 | `energy/consumers/COMPRESSOR/kwh_total` | D | `MB-U47-PM-COMPRESSOR` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | COMPRESSOR |
| 111 | `energy/consumers/COMPRESSOR/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | COMPRESSOR |
| 112 | `energy/consumers/DUST-1/p_now` | D | `MB-U48-PM-DUST-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | DUST-1 |
| 113 | `energy/consumers/DUST-1/kwh_total` | D | `MB-U48-PM-DUST-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | DUST-1 |
| 114 | `energy/consumers/DUST-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | DUST-1 |
| 115 | `energy/consumers/BOILER/p_now` | D | `MB-U49-PM-BOILER` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | BOILER |
| 116 | `energy/consumers/BOILER/kwh_total` | D | `MB-U49-PM-BOILER` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | BOILER |
| 117 | `energy/consumers/BOILER/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | BOILER |
| 118 | `energy/consumers/CHARGING/p_now` | D | `MB-U50-PM-CHARGING` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | CHARGING |
| 119 | `energy/consumers/CHARGING/kwh_total` | D | `MB-U50-PM-CHARGING` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | CHARGING |
| 120 | `energy/consumers/CHARGING/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | sim_data | так | CHARGING |
| 121 | `energy/consumers/OFFICE/p_now` | D | `MB-U51-PM-OFFICE` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | energy | так | — |
| 122 | `energy/consumers/OFFICE/kwh_total` | D | `MB-U51-PM-OFFICE` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | — |
| 123 | `energy/consumers/OFFICE/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | energy | так | — |
| 124 | `energy/consumers/LP-1/p_now` | D | `MB-U52-PM-LP-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | energy | так | LP-1 |
| 125 | `energy/consumers/LP-1/kwh_total` | D | `MB-U52-PM-LP-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | LP-1 |
| 126 | `energy/consumers/LP-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | energy | так | LP-1 |
| 127 | `energy/consumers/LP-2/p_now` | D | `MB-U53-PM-LP-2` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | energy | так | LP-2 |
| 128 | `energy/consumers/LP-2/kwh_total` | D | `MB-U53-PM-LP-2` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | LP-2 |
| 129 | `energy/consumers/LP-2/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | energy | так | LP-2 |
| 130 | `energy/consumers/LP-3/p_now` | D | `MB-U54-PM-LP-3` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | energy | так | LP-3 |
| 131 | `energy/consumers/LP-3/kwh_total` | D | `MB-U54-PM-LP-3` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | LP-3 |
| 132 | `energy/consumers/LP-3/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | energy | так | LP-3 |
| 133 | `energy/consumers/RV-ALL/p_now` | D | `MB-U55-PM-RV-ALL` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | energy | так | — |
| 134 | `energy/consumers/RV-ALL/kwh_total` | D | `MB-U55-PM-RV-ALL` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | — |
| 135 | `energy/consumers/RV-ALL/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | energy | так | — |
| 136 | `energy/consumers/AHU-1/p_now` | D | `MB-U56-PM-AHU-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | energy | так | AHU-1 |
| 137 | `energy/consumers/AHU-1/kwh_total` | D | `MB-U56-PM-AHU-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | AHU-1 |
| 138 | `energy/consumers/AHU-1/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | energy | так | AHU-1 |
| 139 | `energy/consumers/EF-ELEC/p_now` | D | `MB-U57-PM-EF-ELEC` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | energy | так | EF-ELEC |
| 140 | `energy/consumers/EF-ELEC/kwh_total` | D | `MB-U57-PM-EF-ELEC` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | EF-ELEC |
| 141 | `energy/consumers/EF-ELEC/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | energy | так | EF-ELEC |
| 142 | `energy/consumers/EF-CMP/p_now` | D | `MB-U58-PM-EF-CMP` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | energy | так | EF-CMP |
| 143 | `energy/consumers/EF-CMP/kwh_total` | D | `MB-U58-PM-EF-CMP` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | EF-CMP |
| 144 | `energy/consumers/EF-CMP/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | energy | так | EF-CMP |
| 145 | `energy/consumers/EF-CHG/p_now` | D | `MB-U59-PM-EF-CHG` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | energy | так | EF-CHG |
| 146 | `energy/consumers/EF-CHG/kwh_total` | D | `MB-U59-PM-EF-CHG` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | EF-CHG |
| 147 | `energy/consumers/EF-CHG/kwh_shift` | E | `EN-DERIVED` | R-11 | counter | кВт·год | 300/300 | — | energy | так | EF-CHG |
| 148 | `energy/cells/Q1/p_now` | D | `MB-U01-PM-Q1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | catalog | так | Q1 |
| 149 | `energy/cells/Q1/i_now` | D | `MB-U01-PM-Q1` | fc3 3009 f32 (3010) | gauge | А | 10/300 | warn > 1440, alarm > 1600 | catalog | так | Q1 |
| 150 | `energy/cells/Q1/i_a` | D | `MB-U01-PM-Q1` | fc3 2999 f32 (3000) | gauge | А | 30/300 | — | energy | ні | Q1 |
| 151 | `energy/cells/Q1/i_b` | D | `MB-U01-PM-Q1` | fc3 3001 f32 (3002) | gauge | А | 30/300 | — | energy | ні | Q1 |
| 152 | `energy/cells/Q1/i_c` | D | `MB-U01-PM-Q1` | fc3 3003 f32 (3004) | gauge | А | 30/300 | — | energy | ні | Q1 |
| 153 | `energy/cells/Q1/q_kvar` | D | `MB-U01-PM-Q1` | fc3 3067 f32 (3068) | gauge | квар | 10/300 | — | energy | ні | Q1 |
| 154 | `energy/cells/Q1/kwh_total` | D | `MB-U01-PM-Q1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | Q1 |
| 155 | `energy/cells/Q1/kwh_export` | D | `MB-U01-PM-Q1` | fc3 3207 i64 ×0.001 (3208 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | Q1 |
| 156 | `energy/cells/Q1/state` | D | `MB-U01-PM-Q1` | fc3 2017 u16 map (2018 ПРИПУЩЕННЯ) | state | — | 10/300 | alarm: tripped | energy | ні | Q1 |
| 157 | `energy/transformers/T1/p_kw` | D | `MB-U01-PM-Q1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | T1 |
| 158 | `energy/transformers/T1/i_a` | D | `MB-U01-PM-Q1` | fc3 3009 f32 (3010) | gauge | А | 10/300 | — | catalog | так | T1 |
| 159 | `energy/transformers/T1/cos_phi` | D | `MB-U01-PM-Q1` | fc3 3083 f32 (3084) | gauge | — | 10/300 | — | catalog | так | T1 |
| 160 | `energy/transformers/T1/s_kva` | D | `MB-U01-PM-Q1` | fc3 3075 f32 (3076) | gauge | кВА | 10/300 | warn > 900, alarm > 1000 | catalog | так | T1 |
| 161 | `energy/transformers/T1/temp_c` | T | `MB-U96-RTD1 (telemetry)` | telemetry Додаток C | gauge | °C | 30/300 | warn > 100, alarm > 110 | sim_data | так | T1 |
| 162 | `energy/cells/Q1/imbalance_pct` | E | `EN-DERIVED` | R-07 | gauge | % | 3600/0 | warn > 3, alarm > 5 (2 год) | energy | ні | Q1 |
| 163 | `energy/cells/Q1/i_unbal_pct` | E | `EN-DERIVED` | R-12 | gauge | % | 300/300 | warn > 10, alarm > 20 (15 хв) | energy | ні | Q1 |
| 164 | `energy/cells/Q2/p_now` | D | `MB-U02-PM-Q2` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | catalog | так | Q2 |
| 165 | `energy/cells/Q2/i_now` | D | `MB-U02-PM-Q2` | fc3 3009 f32 (3010) | gauge | А | 10/300 | warn > 1440, alarm > 1600 | catalog | так | Q2 |
| 166 | `energy/cells/Q2/i_a` | D | `MB-U02-PM-Q2` | fc3 2999 f32 (3000) | gauge | А | 30/300 | — | energy | ні | Q2 |
| 167 | `energy/cells/Q2/i_b` | D | `MB-U02-PM-Q2` | fc3 3001 f32 (3002) | gauge | А | 30/300 | — | energy | ні | Q2 |
| 168 | `energy/cells/Q2/i_c` | D | `MB-U02-PM-Q2` | fc3 3003 f32 (3004) | gauge | А | 30/300 | — | energy | ні | Q2 |
| 169 | `energy/cells/Q2/q_kvar` | D | `MB-U02-PM-Q2` | fc3 3067 f32 (3068) | gauge | квар | 10/300 | — | energy | ні | Q2 |
| 170 | `energy/cells/Q2/kwh_total` | D | `MB-U02-PM-Q2` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | Q2 |
| 171 | `energy/cells/Q2/kwh_export` | D | `MB-U02-PM-Q2` | fc3 3207 i64 ×0.001 (3208 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | Q2 |
| 172 | `energy/cells/Q2/state` | D | `MB-U02-PM-Q2` | fc3 2017 u16 map (2018 ПРИПУЩЕННЯ) | state | — | 10/300 | alarm: tripped | energy | ні | Q2 |
| 173 | `energy/transformers/T2/p_kw` | D | `MB-U02-PM-Q2` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | sim_data | так | T2 |
| 174 | `energy/transformers/T2/i_a` | D | `MB-U02-PM-Q2` | fc3 3009 f32 (3010) | gauge | А | 10/300 | — | catalog | так | T2 |
| 175 | `energy/transformers/T2/cos_phi` | D | `MB-U02-PM-Q2` | fc3 3083 f32 (3084) | gauge | — | 10/300 | — | catalog | так | T2 |
| 176 | `energy/transformers/T2/s_kva` | D | `MB-U02-PM-Q2` | fc3 3075 f32 (3076) | gauge | кВА | 10/300 | warn > 900, alarm > 1000 | catalog | так | T2 |
| 177 | `energy/transformers/T2/temp_c` | T | `MB-U96-RTD1 (telemetry)` | telemetry Додаток C | gauge | °C | 30/300 | warn > 100, alarm > 110 | sim_data | так | T2 |
| 178 | `energy/cells/Q2/imbalance_pct` | E | `EN-DERIVED` | R-07 | gauge | % | 3600/0 | warn > 3, alarm > 5 (2 год) | energy | ні | Q2 |
| 179 | `energy/cells/Q2/i_unbal_pct` | E | `EN-DERIVED` | R-12 | gauge | % | 300/300 | warn > 10, alarm > 20 (15 хв) | energy | ні | Q2 |
| 180 | `energy/lines/BW-1/p_now` | D | `MB-U03-PM-QF-1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | catalog | так | QF-1 |
| 181 | `energy/lines/BW-1/i_now` | D | `MB-U03-PM-QF-1` | fc3 3009 f32 (3010) | gauge | А | 10/300 | warn > 567, alarm > 630 | catalog | так | QF-1 |
| 182 | `energy/lines/BW-1/cos_phi` | D | `MB-U03-PM-QF-1` | fc3 3083 f32 (3084) | gauge | — | 10/300 | warn < 0,85 | catalog | так | QF-1 |
| 183 | `energy/lines/BW-1/i_a` | D | `MB-U03-PM-QF-1` | fc3 2999 f32 (3000) | gauge | А | 30/300 | — | energy | ні | QF-1 |
| 184 | `energy/lines/BW-1/i_b` | D | `MB-U03-PM-QF-1` | fc3 3001 f32 (3002) | gauge | А | 30/300 | — | energy | ні | QF-1 |
| 185 | `energy/lines/BW-1/i_c` | D | `MB-U03-PM-QF-1` | fc3 3003 f32 (3004) | gauge | А | 30/300 | — | energy | ні | QF-1 |
| 186 | `energy/lines/BW-1/kwh_total` | D | `MB-U03-PM-QF-1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | QF-1 |
| 187 | `energy/lines/BW-1/state` | D | `MB-U03-PM-QF-1` | fc3 2017 u16 map (2018 ПРИПУЩЕННЯ) | state | — | 10/300 | alarm: tripped | energy | ні | QF-1 |
| 188 | `energy/lines/BW-1/imbalance_pct` | E | `EN-DERIVED` | R-07 | gauge | % | 3600/0 | warn > 3, alarm > 5 (2 год) | energy | ні | QF-1 |
| 189 | `energy/lines/BW-1/i_unbal_pct` | E | `EN-DERIVED` | R-12 | gauge | % | 300/300 | warn > 10, alarm > 20 (15 хв) | energy | ні | QF-1 |
| 190 | `energy/lines/BW-2/p_now` | D | `MB-U04-PM-QF-2` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | catalog | так | QF-2 |
| 191 | `energy/lines/BW-2/i_now` | D | `MB-U04-PM-QF-2` | fc3 3009 f32 (3010) | gauge | А | 10/300 | warn > 567, alarm > 630 | catalog | так | QF-2 |
| 192 | `energy/lines/BW-2/cos_phi` | D | `MB-U04-PM-QF-2` | fc3 3083 f32 (3084) | gauge | — | 10/300 | warn < 0,85 | catalog | так | QF-2 |
| 193 | `energy/lines/BW-2/i_a` | D | `MB-U04-PM-QF-2` | fc3 2999 f32 (3000) | gauge | А | 30/300 | — | energy | ні | QF-2 |
| 194 | `energy/lines/BW-2/i_b` | D | `MB-U04-PM-QF-2` | fc3 3001 f32 (3002) | gauge | А | 30/300 | — | energy | ні | QF-2 |
| 195 | `energy/lines/BW-2/i_c` | D | `MB-U04-PM-QF-2` | fc3 3003 f32 (3004) | gauge | А | 30/300 | — | energy | ні | QF-2 |
| 196 | `energy/lines/BW-2/kwh_total` | D | `MB-U04-PM-QF-2` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | QF-2 |
| 197 | `energy/lines/BW-2/state` | D | `MB-U04-PM-QF-2` | fc3 2017 u16 map (2018 ПРИПУЩЕННЯ) | state | — | 10/300 | alarm: tripped | energy | ні | QF-2 |
| 198 | `energy/lines/BW-2/imbalance_pct` | E | `EN-DERIVED` | R-07 | gauge | % | 3600/0 | warn > 3, alarm > 5 (2 год) | energy | ні | QF-2 |
| 199 | `energy/lines/BW-2/i_unbal_pct` | E | `EN-DERIVED` | R-12 | gauge | % | 300/300 | warn > 10, alarm > 20 (15 хв) | energy | ні | QF-2 |
| 200 | `energy/lines/BW-3/p_now` | D | `MB-U05-PM-QF-3` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | catalog | так | QF-3 |
| 201 | `energy/lines/BW-3/i_now` | D | `MB-U05-PM-QF-3` | fc3 3009 f32 (3010) | gauge | А | 10/300 | warn > 567, alarm > 630 | catalog | так | QF-3 |
| 202 | `energy/lines/BW-3/cos_phi` | D | `MB-U05-PM-QF-3` | fc3 3083 f32 (3084) | gauge | — | 10/300 | warn < 0,85 | catalog | так | QF-3 |
| 203 | `energy/lines/BW-3/i_a` | D | `MB-U05-PM-QF-3` | fc3 2999 f32 (3000) | gauge | А | 30/300 | — | energy | ні | QF-3 |
| 204 | `energy/lines/BW-3/i_b` | D | `MB-U05-PM-QF-3` | fc3 3001 f32 (3002) | gauge | А | 30/300 | — | energy | ні | QF-3 |
| 205 | `energy/lines/BW-3/i_c` | D | `MB-U05-PM-QF-3` | fc3 3003 f32 (3004) | gauge | А | 30/300 | — | energy | ні | QF-3 |
| 206 | `energy/lines/BW-3/kwh_total` | D | `MB-U05-PM-QF-3` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | QF-3 |
| 207 | `energy/lines/BW-3/state` | D | `MB-U05-PM-QF-3` | fc3 2017 u16 map (2018 ПРИПУЩЕННЯ) | state | — | 10/300 | alarm: tripped | energy | ні | QF-3 |
| 208 | `energy/lines/BW-3/imbalance_pct` | E | `EN-DERIVED` | R-07 | gauge | % | 3600/0 | warn > 3, alarm > 5 (2 год) | energy | ні | QF-3 |
| 209 | `energy/lines/BW-3/i_unbal_pct` | E | `EN-DERIVED` | R-12 | gauge | % | 300/300 | warn > 10, alarm > 20 (15 хв) | energy | ні | QF-3 |
| 210 | `energy/lines/BW-4/p_now` | D | `MB-U06-PM-QF-4` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | catalog | так | QF-4 |
| 211 | `energy/lines/BW-4/i_now` | D | `MB-U06-PM-QF-4` | fc3 3009 f32 (3010) | gauge | А | 10/300 | warn > 567, alarm > 630 | catalog | так | QF-4 |
| 212 | `energy/lines/BW-4/cos_phi` | D | `MB-U06-PM-QF-4` | fc3 3083 f32 (3084) | gauge | — | 10/300 | warn < 0,85 | catalog | так | QF-4 |
| 213 | `energy/lines/BW-4/i_a` | D | `MB-U06-PM-QF-4` | fc3 2999 f32 (3000) | gauge | А | 30/300 | — | energy | ні | QF-4 |
| 214 | `energy/lines/BW-4/i_b` | D | `MB-U06-PM-QF-4` | fc3 3001 f32 (3002) | gauge | А | 30/300 | — | energy | ні | QF-4 |
| 215 | `energy/lines/BW-4/i_c` | D | `MB-U06-PM-QF-4` | fc3 3003 f32 (3004) | gauge | А | 30/300 | — | energy | ні | QF-4 |
| 216 | `energy/lines/BW-4/kwh_total` | D | `MB-U06-PM-QF-4` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | QF-4 |
| 217 | `energy/lines/BW-4/state` | D | `MB-U06-PM-QF-4` | fc3 2017 u16 map (2018 ПРИПУЩЕННЯ) | state | — | 10/300 | alarm: tripped | energy | ні | QF-4 |
| 218 | `energy/lines/BW-4/imbalance_pct` | E | `EN-DERIVED` | R-07 | gauge | % | 3600/0 | warn > 3, alarm > 5 (2 год) | energy | ні | QF-4 |
| 219 | `energy/lines/BW-4/i_unbal_pct` | E | `EN-DERIVED` | R-12 | gauge | % | 300/300 | warn > 10, alarm > 20 (15 хв) | energy | ні | QF-4 |
| 220 | `energy/lines/C1/p_now` | D | `MB-U07-PM-QF-C1` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | catalog | так | QF-C1 |
| 221 | `energy/lines/C1/i_now` | D | `MB-U07-PM-QF-C1` | fc3 3009 f32 (3010) | gauge | А | 10/300 | warn > 567, alarm > 630 | catalog | так | QF-C1 |
| 222 | `energy/lines/C1/cos_phi` | D | `MB-U07-PM-QF-C1` | fc3 3083 f32 (3084) | gauge | — | 10/300 | warn < 0,85 | catalog | так | QF-C1 |
| 223 | `energy/lines/C1/i_a` | D | `MB-U07-PM-QF-C1` | fc3 2999 f32 (3000) | gauge | А | 30/300 | — | energy | ні | QF-C1 |
| 224 | `energy/lines/C1/i_b` | D | `MB-U07-PM-QF-C1` | fc3 3001 f32 (3002) | gauge | А | 30/300 | — | energy | ні | QF-C1 |
| 225 | `energy/lines/C1/i_c` | D | `MB-U07-PM-QF-C1` | fc3 3003 f32 (3004) | gauge | А | 30/300 | — | energy | ні | QF-C1 |
| 226 | `energy/lines/C1/kwh_total` | D | `MB-U07-PM-QF-C1` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | QF-C1 |
| 227 | `energy/lines/C1/state` | D | `MB-U07-PM-QF-C1` | fc3 2017 u16 map (2018 ПРИПУЩЕННЯ) | state | — | 10/300 | alarm: tripped | energy | ні | QF-C1 |
| 228 | `energy/lines/C1/imbalance_pct` | E | `EN-DERIVED` | R-07 | gauge | % | 3600/0 | warn > 3, alarm > 5 (2 год) | energy | ні | QF-C1 |
| 229 | `energy/lines/C1/i_unbal_pct` | E | `EN-DERIVED` | R-12 | gauge | % | 300/300 | warn > 10, alarm > 20 (15 хв) | energy | ні | QF-C1 |
| 230 | `energy/lines/C2/p_now` | D | `MB-U08-PM-QF-C2` | fc3 3059 f32 (3060) | gauge | кВт | 10/300 | — | catalog | так | QF-C2 |
| 231 | `energy/lines/C2/i_now` | D | `MB-U08-PM-QF-C2` | fc3 3009 f32 (3010) | gauge | А | 10/300 | warn > 360, alarm > 400 | catalog | так | QF-C2 |
| 232 | `energy/lines/C2/cos_phi` | D | `MB-U08-PM-QF-C2` | fc3 3083 f32 (3084) | gauge | — | 10/300 | warn < 0,85 | catalog | так | QF-C2 |
| 233 | `energy/lines/C2/i_a` | D | `MB-U08-PM-QF-C2` | fc3 2999 f32 (3000) | gauge | А | 30/300 | — | energy | ні | QF-C2 |
| 234 | `energy/lines/C2/i_b` | D | `MB-U08-PM-QF-C2` | fc3 3001 f32 (3002) | gauge | А | 30/300 | — | energy | ні | QF-C2 |
| 235 | `energy/lines/C2/i_c` | D | `MB-U08-PM-QF-C2` | fc3 3003 f32 (3004) | gauge | А | 30/300 | — | energy | ні | QF-C2 |
| 236 | `energy/lines/C2/kwh_total` | D | `MB-U08-PM-QF-C2` | fc3 3203 i64 ×0.001 (3204 Вт·год) | counter | кВт·год | 60/60 | — | energy | ні | QF-C2 |
| 237 | `energy/lines/C2/state` | D | `MB-U08-PM-QF-C2` | fc3 2017 u16 map (2018 ПРИПУЩЕННЯ) | state | — | 10/300 | alarm: tripped | energy | ні | QF-C2 |
| 238 | `energy/lines/C2/imbalance_pct` | E | `EN-DERIVED` | R-07 | gauge | % | 3600/0 | warn > 3, alarm > 5 (2 год) | energy | ні | QF-C2 |
| 239 | `energy/lines/C2/i_unbal_pct` | E | `EN-DERIVED` | R-12 | gauge | % | 300/300 | warn > 10, alarm > 20 (15 хв) | energy | ні | QF-C2 |
| 240 | `infra/pv/PV-INV-1/p_kw` | D | `MB-U61-SUN-1` | fc3 32080 i32 ×0.001 | gauge | кВт | 10/300 | — | catalog | так | PV-INV |
| 241 | `infra/pv/PV-INV-1/status` | D | `MB-U61-SUN-1` | fc3 32089 u16 map | state | — | 30/300 | alarm: fault | catalog | так | PV-INV |
| 242 | `infra/pv/PV-INV-1/kwh_today` | D | `MB-U61-SUN-1` | fc3 32114 u32 ×0.01 | gauge | кВт·год | 60/300 | — | catalog | так | PV-INV |
| 243 | `infra/pv/PV-INV-1/kwh_total` | D | `MB-U61-SUN-1` | fc3 32106 u32 ×0.01 | counter | кВт·год | 60/300 | — | energy | ні | PV-INV |
| 244 | `infra/pv/PV-INV-2/p_kw` | D | `MB-U62-SUN-2` | fc3 32080 i32 ×0.001 | gauge | кВт | 10/300 | — | catalog | так | PV-INV |
| 245 | `infra/pv/PV-INV-2/status` | D | `MB-U62-SUN-2` | fc3 32089 u16 map | state | — | 30/300 | alarm: fault | catalog | так | PV-INV |
| 246 | `infra/pv/PV-INV-2/kwh_today` | D | `MB-U62-SUN-2` | fc3 32114 u32 ×0.01 | gauge | кВт·год | 60/300 | — | catalog | так | PV-INV |
| 247 | `infra/pv/PV-INV-2/kwh_total` | D | `MB-U62-SUN-2` | fc3 32106 u32 ×0.01 | counter | кВт·год | 60/300 | — | energy | ні | PV-INV |
| 248 | `infra/pv/PV-INV-3/p_kw` | D | `MB-U63-SUN-3` | fc3 32080 i32 ×0.001 | gauge | кВт | 10/300 | — | catalog | так | PV-INV |
| 249 | `infra/pv/PV-INV-3/status` | D | `MB-U63-SUN-3` | fc3 32089 u16 map | state | — | 30/300 | alarm: fault | catalog | так | PV-INV |
| 250 | `infra/pv/PV-INV-3/kwh_today` | D | `MB-U63-SUN-3` | fc3 32114 u32 ×0.01 | gauge | кВт·год | 60/300 | — | catalog | так | PV-INV |
| 251 | `infra/pv/PV-INV-3/kwh_total` | D | `MB-U63-SUN-3` | fc3 32106 u32 ×0.01 | counter | кВт·год | 60/300 | — | energy | ні | PV-INV |
| 252 | `infra/pv/PV-INV-4/p_kw` | D | `MB-U64-SUN-4` | fc3 32080 i32 ×0.001 | gauge | кВт | 10/300 | — | catalog | так | PV-INV |
| 253 | `infra/pv/PV-INV-4/status` | D | `MB-U64-SUN-4` | fc3 32089 u16 map | state | — | 30/300 | alarm: fault | catalog | так | PV-INV |
| 254 | `infra/pv/PV-INV-4/kwh_today` | D | `MB-U64-SUN-4` | fc3 32114 u32 ×0.01 | gauge | кВт·год | 60/300 | — | catalog | так | PV-INV |
| 255 | `infra/pv/PV-INV-4/kwh_total` | D | `MB-U64-SUN-4` | fc3 32106 u32 ×0.01 | counter | кВт·год | 60/300 | — | energy | ні | PV-INV |
| 256 | `infra/pv/PV-INV-5/p_kw` | D | `MB-U65-SUN-5` | fc3 32080 i32 ×0.001 | gauge | кВт | 10/300 | — | catalog | так | PV-INV |
| 257 | `infra/pv/PV-INV-5/status` | D | `MB-U65-SUN-5` | fc3 32089 u16 map | state | — | 30/300 | alarm: fault | catalog | так | PV-INV |
| 258 | `infra/pv/PV-INV-5/kwh_today` | D | `MB-U65-SUN-5` | fc3 32114 u32 ×0.01 | gauge | кВт·год | 60/300 | — | catalog | так | PV-INV |
| 259 | `infra/pv/PV-INV-5/kwh_total` | D | `MB-U65-SUN-5` | fc3 32106 u32 ×0.01 | counter | кВт·год | 60/300 | — | energy | ні | PV-INV |
| 260 | `infra/pv/PV-INV-6/p_kw` | D | `MB-U66-SUN-6` | fc3 32080 i32 ×0.001 | gauge | кВт | 10/300 | — | catalog | так | PV-INV |
| 261 | `infra/pv/PV-INV-6/status` | D | `MB-U66-SUN-6` | fc3 32089 u16 map | state | — | 30/300 | alarm: fault | catalog | так | PV-INV |
| 262 | `infra/pv/PV-INV-6/kwh_today` | D | `MB-U66-SUN-6` | fc3 32114 u32 ×0.01 | gauge | кВт·год | 60/300 | — | catalog | так | PV-INV |
| 263 | `infra/pv/PV-INV-6/kwh_total` | D | `MB-U66-SUN-6` | fc3 32106 u32 ×0.01 | counter | кВт·год | 60/300 | — | energy | ні | PV-INV |
| 264 | `infra/pv/PV-INV-7/p_kw` | D | `MB-U67-SUN-7` | fc3 32080 i32 ×0.001 | gauge | кВт | 10/300 | — | catalog | так | PV-INV |
| 265 | `infra/pv/PV-INV-7/status` | D | `MB-U67-SUN-7` | fc3 32089 u16 map | state | — | 30/300 | alarm: fault | catalog | так | PV-INV |
| 266 | `infra/pv/PV-INV-7/kwh_today` | D | `MB-U67-SUN-7` | fc3 32114 u32 ×0.01 | gauge | кВт·год | 60/300 | — | catalog | так | PV-INV |
| 267 | `infra/pv/PV-INV-7/kwh_total` | D | `MB-U67-SUN-7` | fc3 32106 u32 ×0.01 | counter | кВт·год | 60/300 | — | energy | ні | PV-INV |
| 268 | `infra/pv/PV-INV-8/p_kw` | D | `MB-U68-SUN-8` | fc3 32080 i32 ×0.001 | gauge | кВт | 10/300 | — | catalog | так | PV-INV |
| 269 | `infra/pv/PV-INV-8/status` | D | `MB-U68-SUN-8` | fc3 32089 u16 map | state | — | 30/300 | alarm: fault | catalog | так | PV-INV |
| 270 | `infra/pv/PV-INV-8/kwh_today` | D | `MB-U68-SUN-8` | fc3 32114 u32 ×0.01 | gauge | кВт·год | 60/300 | — | catalog | так | PV-INV |
| 271 | `infra/pv/PV-INV-8/kwh_total` | D | `MB-U68-SUN-8` | fc3 32106 u32 ×0.01 | counter | кВт·год | 60/300 | — | energy | ні | PV-INV |
| 272 | `infra/totals/bess_soc` | D | `MB-U69-BESS` | fc3 37004 u16 ×0.1 | gauge | % | 30/300 | — | sim_data | так | BESS |
| 273 | `infra/totals/bess_kw` | D | `MB-U69-BESS` | fc3 37001 i32 ×0.001 | gauge | кВт | 10/300 | — | catalog | так | BESS |
| 274 | `infra/bess/state` | D | `MB-U69-BESS` | fc3 37000 u16 map | state | — | 10/300 | alarm: fault | catalog | так | BESS |
| 275 | `infra/bess/kwh_charge_total` | D | `MB-U69-BESS` | fc3 37014 u32 ×0.01 | counter | кВт·год | 60/300 | — | energy | ні | BESS |
| 276 | `infra/bess/kwh_discharge_total` | D | `MB-U69-BESS` | fc3 37016 u32 ×0.01 | counter | кВт·год | 60/300 | — | energy | ні | BESS |
| 277 | `infra/totals/chp_kw` | D | `MB-U72-CHP` | fc3 40001 u16 | gauge | кВт | 10/300 | — | sim_data | так | CHP |
| 278 | `infra/chp/heat_kw` | D | `MB-U72-CHP` | fc3 40002 u16 | gauge | кВт | 30/300 | — | catalog | так | CHP |
| 279 | `infra/chp/gas_m3h` | D | `MB-U72-CHP` | fc3 40003 u16 ×0.1 | gauge | м³/год | 30/300 | — | catalog | так | CHP |
| 280 | `infra/chp/state` | D | `MB-U72-CHP` | fc3 40000 u16 map | state | — | 10/300 | alarm: fault | catalog | так | CHP |
| 281 | `infra/chp/hours` | D | `MB-U72-CHP` | fc3 40010 u32 | counter | год | 300/300 | warn > 76000, alarm > 80000 | catalog | так | CHP |
| 282 | `infra/chp/kwh_total` | D | `MB-U72-CHP` | fc3 40014 u32 | counter | кВт·год | 60/300 | — | energy | ні | CHP |
| 283 | `infra/ats/mode` | D | `MB-U71-ATS-1` | fc3 20482 u16 map | state | — | 10/300 | — | energy | ні | ATS-1 |
| 284 | `infra/ats/position` | D | `MB-U71-ATS-1` | fc3 20483 u16 map | state | — | 5/300 | — | catalog | так | ATS-1 |
| 285 | `infra/ats/gen_start` | D | `MB-U71-ATS-1` | fc3 20484 u16 map | state | — | 5/300 | — | energy | ні | ATS-1 |
| 286 | `infra/ats/src1_state` | D | `MB-U71-ATS-1` | fc3 20486 u16 map | state | — | 5/300 | — | energy | ні | ATS-1 |
| 287 | `infra/ats/src2_state` | D | `MB-U71-ATS-1` | fc3 20487 u16 map | state | — | 5/300 | — | energy | ні | ATS-1 |
| 288 | `infra/ats/src1_ok` | E | `EN-DERIVED` | R-14 | gauge | — | 10/300 | — | catalog | так | ATS-1 |
| 289 | `infra/ats/src2_ok` | E | `EN-DERIVED` | R-14 | gauge | — | 10/300 | — | catalog | так | ATS-1 |
| 290 | `infra/ats/fail_start` | E | `EN-DERIVED` | R-14 | gauge | — | 10/300 | alarm > 0,5 | energy | ні | ATS-1 |
| 291 | `infra/totals/pv_now` | E | `EN-DERIVED` | R-06 | gauge | кВт | 60/300 | — | sim_data | так | PV-INV |
| 292 | `infra/totals/grid_kw` | E | `EN-DERIVED` | R-06 | gauge | кВт | 60/300 | — | catalog | так | SWB-1 |
| 293 | `infra/totals/export_kw` | E | `EN-DERIVED` | R-06 | gauge | кВт | 60/300 | — | catalog | так | SWB-1 |
| 294 | `energy/totals/p_now` | E | `EN-DERIVED` | R-06 | gauge | кВт | 60/300 | — | energy | так | SWB-1 |
| 295 | `energy/totals/load15_kw` | E | `EN-DERIVED` | R-15 | gauge | кВт | 900/0 | — | energy | ні | SWB-1 |
| 296 | `energy/totals/grid15_kw` | E | `EN-DERIVED` | R-12 | gauge | кВт | 900/0 | warn > 0,9·contract, alarm > contract | energy | ні | SWB-1 |
| 297 | `energy/totals/cos_phi` | E | `EN-DERIVED` | R-06 | gauge | — | 60/300 | warn < 0,95, alarm < 0,90 (15 хв) | energy | ні | SWB-1 |
Разом: 297 (D 220, E 75, T 2; `sim_data` 87, `catalog` 63, власні 147).

## Додаток D. Лічильники, джерела, пули

### D.1 Лічильники (`data/energy_meters.csv`, 67)

| № | Код | Вузол | Модель | Роль | Джерело | Сигнал P | Енергія (імпорт / вироблення / заряд) | Енергія (віддача / розряд) | `max_kw` | ТС |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `PM-Q1` | `Q1` | pm5560 | incomer | `MB-U01-PM-Q1` | `energy/cells/Q1/p_now` | `energy/cells/Q1/kwh_total` | `energy/cells/Q1/kwh_export` | 1109 | 1600/5 |
| 2 | `PM-Q2` | `Q2` | pm5560 | incomer | `MB-U02-PM-Q2` | `energy/cells/Q2/p_now` | `energy/cells/Q2/kwh_total` | `energy/cells/Q2/kwh_export` | 1109 | 1600/5 |
| 3 | `PM-QF-1` | `QF-1` | pm5560 | feeder | `MB-U03-PM-QF-1` | `energy/lines/BW-1/p_now` | `energy/lines/BW-1/kwh_total` | — | 437 | 630/5 |
| 4 | `PM-QF-2` | `QF-2` | pm5560 | feeder | `MB-U04-PM-QF-2` | `energy/lines/BW-2/p_now` | `energy/lines/BW-2/kwh_total` | — | 437 | 630/5 |
| 5 | `PM-QF-3` | `QF-3` | pm5560 | feeder | `MB-U05-PM-QF-3` | `energy/lines/BW-3/p_now` | `energy/lines/BW-3/kwh_total` | — | 437 | 630/5 |
| 6 | `PM-QF-4` | `QF-4` | pm5560 | feeder | `MB-U06-PM-QF-4` | `energy/lines/BW-4/p_now` | `energy/lines/BW-4/kwh_total` | — | 437 | 630/5 |
| 7 | `PM-QF-C1` | `QF-C1` | pm5560 | feeder | `MB-U07-PM-QF-C1` | `energy/lines/C1/p_now` | `energy/lines/C1/kwh_total` | — | 437 | 630/5 |
| 8 | `PM-QF-C2` | `QF-C2` | pm5560 | feeder | `MB-U08-PM-QF-C2` | `energy/lines/C2/p_now` | `energy/lines/C2/kwh_total` | — | 278 | 400/5 |
| 9 | `PM-SAW-1` | `SAW-1` | pm5560 | consumer | `MB-U11-PM-SAW-1` | `energy/consumers/SAW-1/p_now` | `energy/consumers/SAW-1/kwh_total` | — | 48 | 100/5 |
| 10 | `PM-SAW-2` | `SAW-2` | pm5560 | consumer | `MB-U12-PM-SAW-2` | `energy/consumers/SAW-2/p_now` | `energy/consumers/SAW-2/kwh_total` | — | 48 | 100/5 |
| 11 | `PM-SAW-3` | `SAW-3` | pm5560 | consumer | `MB-U13-PM-SAW-3` | `energy/consumers/SAW-3/p_now` | `energy/consumers/SAW-3/kwh_total` | — | 90 | 100/5 |
| 12 | `PM-SLIDE-1` | `SLIDE-1` | pm5560 | consumer | `MB-U14-PM-SLIDE-1` | `energy/consumers/SLIDE-1/p_now` | `energy/consumers/SLIDE-1/kwh_total` | — | 15 | 100/5 |
| 13 | `PM-VSAW-1` | `VSAW-1` | pm5560 | consumer | `MB-U15-PM-VSAW-1` | `energy/consumers/VSAW-1/p_now` | `energy/consumers/VSAW-1/kwh_total` | — | 15 | 100/5 |
| 14 | `PM-NEST-1` | `NEST-1` | pm5560 | consumer | `MB-U16-PM-NEST-1` | `energy/consumers/NEST-1/p_now` | `energy/consumers/NEST-1/kwh_total` | — | 78 | 100/5 |
| 15 | `PM-EDGE-1` | `EDGE-1` | pm5560 | consumer | `MB-U17-PM-EDGE-1` | `energy/consumers/EDGE-1/p_now` | `energy/consumers/EDGE-1/kwh_total` | — | 135 | 100/5 |
| 16 | `PM-EDGE-2` | `EDGE-2` | pm5560 | consumer | `MB-U18-PM-EDGE-2` | `energy/consumers/EDGE-2/p_now` | `energy/consumers/EDGE-2/kwh_total` | — | 56 | 100/5 |
| 17 | `PM-EDGE-3` | `EDGE-3` | pm5560 | consumer | `MB-U19-PM-EDGE-3` | `energy/consumers/EDGE-3/p_now` | `energy/consumers/EDGE-3/kwh_total` | — | 56 | 100/5 |
| 18 | `PM-CNC-3` | `CNC-3` | pm5560 | consumer | `MB-U20-PM-CNC-3` | `energy/consumers/CNC-3/p_now` | `energy/consumers/CNC-3/kwh_total` | — | 44 | 100/5 |
| 19 | `PM-CNC-1` | `CNC-1` | pm5560 | consumer | `MB-U21-PM-CNC-1` | `energy/consumers/CNC-1/p_now` | `energy/consumers/CNC-1/kwh_total` | — | 44 | 100/5 |
| 20 | `PM-CNC-2` | `CNC-2` | pm5560 | consumer | `MB-U22-PM-CNC-2` | `energy/consumers/CNC-2/p_now` | `energy/consumers/CNC-2/kwh_total` | — | 44 | 100/5 |
| 21 | `PM-BORE-1` | `BORE-1` | pm5560 | consumer | `MB-U23-PM-BORE-1` | `energy/consumers/BORE-1/p_now` | `energy/consumers/BORE-1/kwh_total` | — | 39 | 100/5 |
| 22 | `PM-CNC-4` | `CNC-4` | pm5560 | consumer | `MB-U24-PM-CNC-4` | `energy/consumers/CNC-4/p_now` | `energy/consumers/CNC-4/kwh_total` | — | 44 | 100/5 |
| 23 | `PM-DOWEL-1` | `DOWEL-1` | pm5560 | consumer | `MB-U25-PM-DOWEL-1` | `energy/consumers/DOWEL-1/p_now` | `energy/consumers/DOWEL-1/kwh_total` | — | 22 | 100/5 |
| 24 | `PM-SORT-1` | `SORT-1` | pm5560 | consumer | `MB-U26-PM-SORT-1` | `energy/consumers/SORT-1/p_now` | `energy/consumers/SORT-1/kwh_total` | — | 40 | 100/5 |
| 25 | `PM-SAND-1` | `SAND-1` | pm5560 | consumer | `MB-U27-PM-SAND-1` | `energy/consumers/SAND-1/p_now` | `energy/consumers/SAND-1/kwh_total` | — | 60 | 100/5 |
| 26 | `PM-AUTOSPRAY-1` | `AUTOSPRAY-1` | pm5560 | consumer | `MB-U28-PM-AUTOSPRAY-1` | `energy/consumers/AUTOSPRAY-1/p_now` | `energy/consumers/AUTOSPRAY-1/kwh_total` | — | 36 | 100/5 |
| 27 | `PM-UV-1` | `UV-1` | pm5560 | consumer | `MB-U29-PM-UV-1` | `energy/consumers/UV-1/p_now` | `energy/consumers/UV-1/kwh_total` | — | 118 | 100/5 |
| 28 | `PM-HINGE-1` | `HINGE-1` | pm5560 | consumer | `MB-U30-PM-HINGE-1` | `energy/consumers/HINGE-1/p_now` | `energy/consumers/HINGE-1/kwh_total` | — | 10 | 100/5 |
| 29 | `PM-GLUE-1` | `GLUE-1` | pm5560 | consumer | `MB-U31-PM-GLUE-1` | `energy/consumers/GLUE-1/p_now` | `energy/consumers/GLUE-1/kwh_total` | — | 10 | 100/5 |
| 30 | `PM-PRESS-1` | `PRESS-1` | pm5560 | consumer | `MB-U32-PM-PRESS-1` | `energy/consumers/PRESS-1/p_now` | `energy/consumers/PRESS-1/kwh_total` | — | 56 | 100/5 |
| 31 | `PM-SPRAY-1` | `SPRAY-1` | pm5560 | consumer | `MB-U33-PM-SPRAY-1` | `energy/consumers/SPRAY-1/p_now` | `energy/consumers/SPRAY-1/kwh_total` | — | 11 | 100/5 |
| 32 | `PM-DRY-1` | `DRY-1` | pm5560 | consumer | `MB-U34-PM-DRY-1` | `energy/consumers/DRY-1/p_now` | `energy/consumers/DRY-1/kwh_total` | — | 34 | 100/5 |
| 33 | `PM-ASMLINE-1` | `ASMLINE-1` | pm5560 | consumer | `MB-U35-PM-ASMLINE-1` | `energy/consumers/ASMLINE-1/p_now` | `energy/consumers/ASMLINE-1/kwh_total` | — | 16 | 100/5 |
| 34 | `PM-ASM-1` | `ASM-1` | pm5560 | consumer | `MB-U36-PM-ASM-1` | `energy/consumers/ASM-1/p_now` | `energy/consumers/ASM-1/kwh_total` | — | 10 | 100/5 |
| 35 | `PM-ASM-2` | `ASM-2` | pm5560 | consumer | `MB-U37-PM-ASM-2` | `energy/consumers/ASM-2/p_now` | `energy/consumers/ASM-2/kwh_total` | — | 10 | 100/5 |
| 36 | `PM-ASM-3` | `ASM-3` | pm5560 | consumer | `MB-U38-PM-ASM-3` | `energy/consumers/ASM-3/p_now` | `energy/consumers/ASM-3/kwh_total` | — | 10 | 100/5 |
| 37 | `PM-ASM-4` | `ASM-4` | pm5560 | consumer | `MB-U39-PM-ASM-4` | `energy/consumers/ASM-4/p_now` | `energy/consumers/ASM-4/kwh_total` | — | 10 | 100/5 |
| 38 | `PM-ASM-5` | `ASM-5` | pm5560 | consumer | `MB-U40-PM-ASM-5` | `energy/consumers/ASM-5/p_now` | `energy/consumers/ASM-5/kwh_total` | — | 10 | 100/5 |
| 39 | `PM-ASM-6` | `ASM-6` | pm5560 | consumer | `MB-U41-PM-ASM-6` | `energy/consumers/ASM-6/p_now` | `energy/consumers/ASM-6/kwh_total` | — | 10 | 100/5 |
| 40 | `PM-PACK-1` | `PACK-1` | pm5560 | consumer | `MB-U42-PM-PACK-1` | `energy/consumers/PACK-1/p_now` | `energy/consumers/PACK-1/kwh_total` | — | 10 | 100/5 |
| 41 | `PM-PACK-2` | `PACK-2` | pm5560 | consumer | `MB-U43-PM-PACK-2` | `energy/consumers/PACK-2/p_now` | `energy/consumers/PACK-2/kwh_total` | — | 10 | 100/5 |
| 42 | `PM-BOX-1` | `BOX-1` | pm5560 | consumer | `MB-U44-PM-BOX-1` | `energy/consumers/BOX-1/p_now` | `energy/consumers/BOX-1/kwh_total` | — | 20 | 100/5 |
| 43 | `PM-PACKLINE-1` | `PACKLINE-1` | pm5560 | consumer | `MB-U45-PM-PACKLINE-1` | `energy/consumers/PACKLINE-1/p_now` | `energy/consumers/PACKLINE-1/kwh_total` | — | 40 | 100/5 |
| 44 | `PM-GANTRY-1` | `GANTRY-1` | pm5560 | consumer | `MB-U46-PM-GANTRY-1` | `energy/consumers/GANTRY-1/p_now` | `energy/consumers/GANTRY-1/kwh_total` | — | 30 | 100/5 |
| 45 | `PM-COMPRESSOR` | `COMPRESSOR` | pm5560 | consumer | `MB-U47-PM-COMPRESSOR` | `energy/consumers/COMPRESSOR/p_now` | `energy/consumers/COMPRESSOR/kwh_total` | — | 148 | 100/5 |
| 46 | `PM-DUST-1` | `DUST-1` | pm5560 | consumer | `MB-U48-PM-DUST-1` | `energy/consumers/DUST-1/p_now` | `energy/consumers/DUST-1/kwh_total` | — | 300 | 100/5 |
| 47 | `PM-BOILER` | `BOILER` | pm5560 | consumer | `MB-U49-PM-BOILER` | `energy/consumers/BOILER/p_now` | `energy/consumers/BOILER/kwh_total` | — | 50 | 100/5 |
| 48 | `PM-CHARGING` | `CHARGING` | pm5560 | consumer | `MB-U50-PM-CHARGING` | `energy/consumers/CHARGING/p_now` | `energy/consumers/CHARGING/kwh_total` | — | 27 | 100/5 |
| 49 | `PM-OFFICE` | `OFFICE` | pm5560 | consumer | `MB-U51-PM-OFFICE` | `energy/consumers/OFFICE/p_now` | `energy/consumers/OFFICE/kwh_total` | — | 64 | 100/5 |
| 50 | `PM-LP-1` | `LP-1` | pm5560 | consumer | `MB-U52-PM-LP-1` | `energy/consumers/LP-1/p_now` | `energy/consumers/LP-1/kwh_total` | — | 13 | 100/5 |
| 51 | `PM-LP-2` | `LP-2` | pm5560 | consumer | `MB-U53-PM-LP-2` | `energy/consumers/LP-2/p_now` | `energy/consumers/LP-2/kwh_total` | — | 47 | 100/5 |
| 52 | `PM-LP-3` | `LP-3` | pm5560 | consumer | `MB-U54-PM-LP-3` | `energy/consumers/LP-3/p_now` | `energy/consumers/LP-3/kwh_total` | — | 22 | 100/5 |
| 53 | `PM-RV-ALL` | `RV-ALL` | pm5560 | consumer | `MB-U55-PM-RV-ALL` | `energy/consumers/RV-ALL/p_now` | `energy/consumers/RV-ALL/kwh_total` | — | 430 | 100/5 |
| 54 | `PM-AHU-1` | `AHU-1` | pm5560 | consumer | `MB-U56-PM-AHU-1` | `energy/consumers/AHU-1/p_now` | `energy/consumers/AHU-1/kwh_total` | — | 30 | 100/5 |
| 55 | `PM-EF-ELEC` | `EF-ELEC` | pm5560 | consumer | `MB-U57-PM-EF-ELEC` | `energy/consumers/EF-ELEC/p_now` | `energy/consumers/EF-ELEC/kwh_total` | — | 10 | 100/5 |
| 56 | `PM-EF-CMP` | `EF-CMP` | pm5560 | consumer | `MB-U58-PM-EF-CMP` | `energy/consumers/EF-CMP/p_now` | `energy/consumers/EF-CMP/kwh_total` | — | 10 | 100/5 |
| 57 | `PM-EF-CHG` | `EF-CHG` | pm5560 | consumer | `MB-U59-PM-EF-CHG` | `energy/consumers/EF-CHG/p_now` | `energy/consumers/EF-CHG/kwh_total` | — | 10 | 100/5 |
| 58 | `SUN-1` | `PV-INV-1` | sun2000 | generation | `MB-U61-SUN-1` | `infra/pv/PV-INV-1/p_kw` | `infra/pv/PV-INV-1/kwh_total` | — | 125 | — |
| 59 | `SUN-2` | `PV-INV-2` | sun2000 | generation | `MB-U62-SUN-2` | `infra/pv/PV-INV-2/p_kw` | `infra/pv/PV-INV-2/kwh_total` | — | 125 | — |
| 60 | `SUN-3` | `PV-INV-3` | sun2000 | generation | `MB-U63-SUN-3` | `infra/pv/PV-INV-3/p_kw` | `infra/pv/PV-INV-3/kwh_total` | — | 125 | — |
| 61 | `SUN-4` | `PV-INV-4` | sun2000 | generation | `MB-U64-SUN-4` | `infra/pv/PV-INV-4/p_kw` | `infra/pv/PV-INV-4/kwh_total` | — | 125 | — |
| 62 | `SUN-5` | `PV-INV-5` | sun2000 | generation | `MB-U65-SUN-5` | `infra/pv/PV-INV-5/p_kw` | `infra/pv/PV-INV-5/kwh_total` | — | 125 | — |
| 63 | `SUN-6` | `PV-INV-6` | sun2000 | generation | `MB-U66-SUN-6` | `infra/pv/PV-INV-6/p_kw` | `infra/pv/PV-INV-6/kwh_total` | — | 125 | — |
| 64 | `SUN-7` | `PV-INV-7` | sun2000 | generation | `MB-U67-SUN-7` | `infra/pv/PV-INV-7/p_kw` | `infra/pv/PV-INV-7/kwh_total` | — | 125 | — |
| 65 | `SUN-8` | `PV-INV-8` | sun2000 | generation | `MB-U68-SUN-8` | `infra/pv/PV-INV-8/p_kw` | `infra/pv/PV-INV-8/kwh_total` | — | 125 | — |
| 66 | `LUNA-1` | `BESS` | luna2000 | storage | `MB-U69-BESS` | `infra/totals/bess_kw` | `infra/bess/kwh_charge_total` | `infra/bess/kwh_discharge_total` | 200 | — |
| 67 | `TEDOM-1` | `CHP` | tedom | generation | `MB-U72-CHP` | `infra/totals/chp_kw` | `infra/chp/kwh_total` | — | 900 | — |
### D.2 Джерела Modbus TCP (`data/energy_sources.csv`, 68; `type='modbus_tcp'`, колектор `COL-MAIN`, `module='energy'`)

`params = {"host": "iot-sim", "port": 502, "unit": <unit>, "timeout_s": 3, "retries": 2, "max_block": 125, "gap_max": 8}`;
`name` = опис; у проді — `host` лічильника (iot_sim Q-12), `unit` = адреса RS-485 за шлюзом або 1.

| № | Код | unit | Обладнання | Опис |
|---|---|---|---|---|
| 1 | `MB-U01-PM-Q1` | 1 | Q1 | PM5560 ввід Q1 |
| 2 | `MB-U02-PM-Q2` | 2 | Q2 | PM5560 ввід Q2 |
| 3 | `MB-U03-PM-QF-1` | 3 | QF-1 | PM5560 фідер QF-1 |
| 4 | `MB-U04-PM-QF-2` | 4 | QF-2 | PM5560 фідер QF-2 |
| 5 | `MB-U05-PM-QF-3` | 5 | QF-3 | PM5560 фідер QF-3 |
| 6 | `MB-U06-PM-QF-4` | 6 | QF-4 | PM5560 фідер QF-4 |
| 7 | `MB-U07-PM-QF-C1` | 7 | QF-C1 | PM5560 фідер QF-C1 |
| 8 | `MB-U08-PM-QF-C2` | 8 | QF-C2 | PM5560 фідер QF-C2 |
| 9 | `MB-U11-PM-SAW-1` | 11 | SAW-1 | PM5560 Розкрій 1 |
| 10 | `MB-U12-PM-SAW-2` | 12 | SAW-2 | PM5560 Розкрій 2 |
| 11 | `MB-U13-PM-SAW-3` | 13 | SAW-3 | PM5560 Пакетний розкрій |
| 12 | `MB-U14-PM-SLIDE-1` | 14 | SLIDE-1 | PM5560 Форматно-розкрійний |
| 13 | `MB-U15-PM-VSAW-1` | 15 | VSAW-1 | PM5560 Вертикальна пила |
| 14 | `MB-U16-PM-NEST-1` | 16 | NEST-1 | PM5560 Нестинг ЧПК |
| 15 | `MB-U17-PM-EDGE-1` | 17 | EDGE-1 | PM5560 Крайкооблицювання A |
| 16 | `MB-U18-PM-EDGE-2` | 18 | EDGE-2 | PM5560 Крайкооблицювання B |
| 17 | `MB-U19-PM-EDGE-3` | 19 | EDGE-3 | PM5560 Крайкооблицювання C |
| 18 | `MB-U20-PM-CNC-3` | 20 | CNC-3 | PM5560 Присадка ЧПК D1 |
| 19 | `MB-U21-PM-CNC-1` | 21 | CNC-1 | PM5560 Присадка ЧПК A |
| 20 | `MB-U22-PM-CNC-2` | 22 | CNC-2 | PM5560 Присадка ЧПК B |
| 21 | `MB-U23-PM-BORE-1` | 23 | BORE-1 | PM5560 Прохідна присадка C |
| 22 | `MB-U24-PM-CNC-4` | 24 | CNC-4 | PM5560 Присадка ЧПК D2 |
| 23 | `MB-U25-PM-DOWEL-1` | 25 | DOWEL-1 | PM5560 Шкантування C |
| 24 | `MB-U26-PM-SORT-1` | 26 | SORT-1 | PM5560 Сортувальний робот |
| 25 | `MB-U27-PM-SAND-1` | 27 | SAND-1 | PM5560 Шліфування фасадів |
| 26 | `MB-U28-PM-AUTOSPRAY-1` | 28 | AUTOSPRAY-1 | PM5560 Автомат фарбування |
| 27 | `MB-U29-PM-UV-1` | 29 | UV-1 | PM5560 УФ-лакування |
| 28 | `MB-U30-PM-HINGE-1` | 30 | HINGE-1 | PM5560 Встановлення завіс |
| 29 | `MB-U31-PM-GLUE-1` | 31 | GLUE-1 | PM5560 Кабіна нанесення клею |
| 30 | `MB-U32-PM-PRESS-1` | 32 | PRESS-1 | PM5560 Мембранно-вакуумний прес |
| 31 | `MB-U33-PM-SPRAY-1` | 33 | SPRAY-1 | PM5560 Фарбувальна камера |
| 32 | `MB-U34-PM-DRY-1` | 34 | DRY-1 | PM5560 Сушильна камера |
| 33 | `MB-U35-PM-ASMLINE-1` | 35 | ASMLINE-1 | PM5560 Лінія збирання корпусів |
| 34 | `MB-U36-PM-ASM-1` | 36 | ASM-1 | PM5560 Збирання 1 |
| 35 | `MB-U37-PM-ASM-2` | 37 | ASM-2 | PM5560 Збирання 2 |
| 36 | `MB-U38-PM-ASM-3` | 38 | ASM-3 | PM5560 Збирання 3 |
| 37 | `MB-U39-PM-ASM-4` | 39 | ASM-4 | PM5560 Збирання 4 |
| 38 | `MB-U40-PM-ASM-5` | 40 | ASM-5 | PM5560 Збирання 5 |
| 39 | `MB-U41-PM-ASM-6` | 41 | ASM-6 | PM5560 Збирання 6 |
| 40 | `MB-U42-PM-PACK-1` | 42 | PACK-1 | PM5560 Пакування 1 |
| 41 | `MB-U43-PM-PACK-2` | 43 | PACK-2 | PM5560 Пакування 2 |
| 42 | `MB-U44-PM-BOX-1` | 44 | BOX-1 | PM5560 Розкрій гофрокартону |
| 43 | `MB-U45-PM-PACKLINE-1` | 45 | PACKLINE-1 | PM5560 Термоусадка та обв'язка |
| 44 | `MB-U46-PM-GANTRY-1` | 46 | GANTRY-1 | PM5560 Портальний склад плит |
| 45 | `MB-U47-PM-COMPRESSOR` | 47 | COMPRESSOR | PM5560 Компресорна (2 × GA 37 VSD+, осушувач) |
| 46 | `MB-U48-PM-DUST-1` | 48 | DUST-1 | PM5560 Вентилятори аспірації |
| 47 | `MB-U49-PM-BOILER` | 49 | BOILER | PM5560 Котельня (2 котли), шнеки, брикетування |
| 48 | `MB-U50-PM-CHARGING` | 50 | CHARGING | PM5560 Зарядна станція (3 зарядні пристрої) |
| 49 | `MB-U51-PM-OFFICE` | 51 | — | PM5560 Офіс, побутові приміщення, серверна |
| 50 | `MB-U52-PM-LP-1` | 52 | LP-1 | PM5560 Щит освітлення ЩО-1 · склади сировини, приймання |
| 51 | `MB-U53-PM-LP-2` | 53 | LP-2 | PM5560 Щит освітлення ЩО-2 · лінії й дільниця фасадів |
| 52 | `MB-U54-PM-LP-3` | 54 | LP-3 | PM5560 Щит освітлення ЩО-3 · збирання, пакування, склад ГП, відвантаження |
| 53 | `MB-U55-PM-RV-ALL` | 55 | — | PM5560 Дахові установки вентиляції (25 шт.) |
| 54 | `MB-U56-PM-AHU-1` | 56 | AHU-1 | PM5560 Припливна установка дільниці фасадів |
| 55 | `MB-U57-PM-EF-ELEC` | 57 | EF-ELEC | PM5560 Витяжні вентилятори електрощитової |
| 56 | `MB-U58-PM-EF-CMP` | 58 | EF-CMP | PM5560 Витяжний вентилятор компресорної |
| 57 | `MB-U59-PM-EF-CHG` | 59 | EF-CHG | PM5560 Витяжка зарядної станції (Ex) |
| 58 | `MB-U61-SUN-1` | 61 | PV-INV | Huawei SUN2000 PV-INV-1 |
| 59 | `MB-U62-SUN-2` | 62 | PV-INV | Huawei SUN2000 PV-INV-2 |
| 60 | `MB-U63-SUN-3` | 63 | PV-INV | Huawei SUN2000 PV-INV-3 |
| 61 | `MB-U64-SUN-4` | 64 | PV-INV | Huawei SUN2000 PV-INV-4 |
| 62 | `MB-U65-SUN-5` | 65 | PV-INV | Huawei SUN2000 PV-INV-5 |
| 63 | `MB-U66-SUN-6` | 66 | PV-INV | Huawei SUN2000 PV-INV-6 |
| 64 | `MB-U67-SUN-7` | 67 | PV-INV | Huawei SUN2000 PV-INV-7 |
| 65 | `MB-U68-SUN-8` | 68 | PV-INV | Huawei SUN2000 PV-INV-8 |
| 66 | `MB-U69-BESS` | 69 | BESS | Huawei LUNA2000 |
| 67 | `MB-U71-ATS-1` | 71 | ATS-1 | Socomec ATyS p |
| 68 | `MB-U72-CHP` | 72 | CHP | TEDOM Quanto D800 |
### D.3 Пули (`data/energy_pools.csv`, 5; Q-01, Q-18)

| Код | Назва | `sequence` | Драйвер | Споживачі-члени (`pool` у Додатку B) | Обслуговує РЦ |
|---|---|---|---|---|---|
| `POOL-AIR` | Стиснене повітря | 10 | `kwh` | COMPRESSOR | усі |
| `POOL-DUST` | Аспірація | 20 | `kwh` | DUST-1 | усі |
| `POOL-GANTRY` | Подача плит (портал) | 30 | `kwh` | GANTRY-1 | SAW-1, SAW-2, SAW-3, NEST-1 |
| `POOL-LIGHT` | Освітлення цеху | 40 | `time` | LP-1, LP-2, LP-3 | усі |
| `POOL-HVAC` | Вентиляція | 50 | `time` | RV-ALL, AHU-1 | усі |

Накладні (`alloc_role='overhead'`): BOILER, CHARGING, OFFICE, EF-ELEC, EF-CMP, EF-CHG.
