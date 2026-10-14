# factory3d_base — специфікація

Версія 0.2 · 14.10.2026 (0.1 — 13.10.2026) · технічне рішення: `docs/modules/factory3d_base/ARCHITECTURE.md` (далі ARCH).
Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-09 (дзеркало `f3d_code`, `f3d_alias`, `f3d_kind` у `hr.employee.public`, M-10a, FR-14, AC-55),
X-15 (`f3d_truck` — опис/назва фури, не держномер і не код; код фури в 3D — лише `f3d_code`), X-32 і сторона base у X-69 (§3: резерв
55 genset, правило пункту «Налаштування <модуля>» під `menu_f3d_config`, власні пункти base поза резервом), сторона base у X-19
(§4.2: у `privilege_f3d` лише групи base).
Спирається на контракти каркаса `docs/ARCHITECTURE.md`: C-6.1 (код сцени), C-6.2 (зони й ворота),
C-6.3 (паспорт), C-6.7 (кнопка «Показати в 3D»), рішення D-03 (ворота = `stock.location`-док),
конвенції §5. Визначає власні контракти CB-01…CB-12 (ARCH §2.1). Протоколи P-xx не задіяні.

Усі імена остаточні. Рядки інтерфейсу — українською в коді (A-08). Odoo 19: SQL-обмеження —
`models.Constraint`, хуки — `post_init_hook(env)` / `uninstall_hook(env)`, команди o2m/m2m —
`odoo.fields.Command`.

## 0. Дерево файлів модуля

```
odoo_addons/factory3d_base/
├── __init__.py                      from . import models, hooks; from .hooks import post_init_hook, uninstall_hook
├── __manifest__.py                  §1
├── README.md                        що робить модуль, установка, параметри (з ARCH §3–4)
├── CHANGELOG.md                     19.0.1.0.0 — перший випуск
├── hooks/
│   ├── __init__.py                  post_init_hook(env), uninstall_hook(env), run_all(env) — оркестратор §5.3
│   ├── docks.py                     крок 1: ворота в типах операцій (R-10)
│   ├── codes.py                     кроки 2–5: коди локацій/РЦ/працівників/обладнання (R-05…R-07)
│   ├── passports.py                 крок 6: прив'язка паспортів і складових (R-17)
│   ├── zones.py                     крок 7: корені зон і прив'язки (R-08)
│   ├── batches.py                   крок 8–9: x_* → пакети, звірка (R-11…R-13)
│   ├── x_fields.py                  CB-11: read_manual_field / drop_manual_fields / restore_manual_fields (R-14…R-16)
│   └── report.py                    звіт міграції → ir.config_parameter (R-16)
├── models/
│   ├── __init__.py                  порядок: f3d_scene_mixin, f3d_zone, f3d_equipment_passport, stock_location,
│   │                                stock_picking_batch, stock_picking, mrp_workcenter, maintenance_equipment, hr_employee
│   ├── f3d_scene_mixin.py           M-01
│   ├── f3d_zone.py                  M-02 + поля f3d_zone_id на stock.location/mrp.workcenter/maintenance.equipment
│   ├── f3d_equipment_passport.py    M-05, M-06, M-07
│   ├── stock_location.py            M-03
│   ├── stock_picking_batch.py       M-04
│   ├── stock_picking.py             M-11
│   ├── mrp_workcenter.py            M-09
│   ├── maintenance_equipment.py     M-08
│   └── hr_employee.py               M-10, M-10a (дзеркало в hr.employee.public; клас hr.employee — першим)
├── security/
│   ├── f3d_security.xml             категорія, привілей, групи, implied, record rule (§4)
│   └── ir.model.access.csv          §4.1
├── data/
│   ├── ir_config_parameter.xml      §5.1 (noupdate="1")
│   ├── f3d_zone_data.xml            34 зони (noupdate="1"), додаток C
│   ├── f3d.equipment.passport.csv   93 паспорти (noupdate="0")
│   ├── f3d.equipment.spec.csv       999 специфікацій
│   ├── f3d.equipment.source.csv     252 джерела
│   ├── scene_docks.csv              14 воріт — таблиця для хука (не модель), додаток D
│   ├── scene_locations.csv          689 рядків code,kind,capacity — вид і місткість місць (FR-13)
│   ├── scene_zone_links.csv         211 прив'язок зона→(prefix|code|workcenter|equipment|root)
│   ├── scene_employee_codes.csv     35 рядків barcode→f3d_code, додаток B
│   ├── scene_equipment_codes.csv    208 рядків code, xmlid, legacy_serial, name, role, components, zone
│   ├── f3d_actions.xml              ir.actions.server «Повторити міграцію демо-даних»
│   └── neutralize.sql               §5.5
├── views/
│   ├── f3d_menus.xml                V-17: кореневе меню, підменю, дії
│   ├── f3d_zone_views.xml           V-01…V-04
│   ├── stock_location_views.xml     V-05…V-07
│   ├── stock_picking_batch_views.xml V-08, V-09
│   ├── stock_picking_views.xml      V-10
│   ├── mrp_workcenter_views.xml     V-11
│   ├── maintenance_equipment_views.xml V-12, V-13
│   ├── hr_employee_views.xml        V-14
│   └── f3d_equipment_passport_views.xml V-15, V-16
├── static/description/icon.png      іконка застосунку (куб із заводом; 140×140)
├── tools/
│   └── gen_data.py                  генератор data/*.csv і f3d_zone_data.xml з макета (§5.2); Odoo його не вантажить
└── tests/
    ├── __init__.py
    ├── common.py                    F3DCase(TransactionCase): фікстури §13.1
    ├── test_scene_mixin.py          AC-01…AC-09
    ├── test_employee.py             AC-13, AC-39, AC-40, AC-55
    ├── test_zone.py                 AC-15…AC-19
    ├── test_dock.py                 AC-11, AC-20…AC-24
    ├── test_batch.py                AC-22, AC-51, AC-52
    ├── test_migration.py            AC-10, AC-12, AC-14, AC-25…AC-31
    ├── test_passport.py             AC-32…AC-38
    ├── test_security.py             AC-41…AC-45, AC-50
    ├── test_hooks.py                AC-46…AC-49
    └── test_data_sync.py            CSV ↔ макет (поза Odoo, pytest; §13.1)
```

## 1. Маніфест

```python
{
    "name": "Завод 3D: база",
    "summary": "Коди сцени, зони цеху, ворота-доки, паспорти обладнання, групи прав для factory3d",
    "description": "Ядро factory3d: домішка f3d.scene.mixin, f3d.zone, ворота як доки Odoo 19, "
                   "паспорти обладнання з макета, міграція демо-полів x_dock/x_truck/x_vehicle.",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["stock", "stock_picking_batch", "stock_fleet", "fleet", "mrp", "maintenance",
                "mrp_maintenance", "hr", "web"],
    "data": [
        "security/f3d_security.xml",
        "security/ir.model.access.csv",
        "data/ir_config_parameter.xml",
        "data/f3d.equipment.passport.csv",
        "data/f3d.equipment.spec.csv",
        "data/f3d.equipment.source.csv",
        "data/f3d_zone_data.xml",
        "data/f3d_actions.xml",
        "views/f3d_zone_views.xml",
        "views/f3d_equipment_passport_views.xml",
        "views/stock_location_views.xml",
        "views/stock_picking_batch_views.xml",
        "views/stock_picking_views.xml",
        "views/mrp_workcenter_views.xml",
        "views/maintenance_equipment_views.xml",
        "views/hr_employee_views.xml",
        "views/f3d_menus.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": True,
}
```

Порядок `data` важливий: групи → доступи → параметри → паспорти (CSV: спершу `passport`, потім
`spec`/`source`, що посилаються на `passport_id:id`) → зони → дії → представлення → меню (посилаються
на дії). `scene_*.csv` у `data` не перелічені — їх читає хук через `odoo.tools.file_open`.
`application: True` — щоб «Завод 3D» був застосунком із власною іконкою в меню.

## 2. Моделі

Спільні позначення: `req` = `required=True`; `idx` = `index=True`; типи — Odoo `fields.*`.

### M-01 `f3d.scene.mixin` — домішка «код сцени» (CB-01)

```python
class F3dSceneMixin(models.AbstractModel):
    _name = "f3d.scene.mixin"
    _description = "Код сцени 3D"
    _f3d_kind = "other"                       # носій перевизначає
    _f3d_resolve_order = ["f3d.zone", "stock.location", "mrp.workcenter",
                          "maintenance.equipment", "hr.employee", "stock.picking.batch"]
    F3D_CODE_RE = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)*$")
```

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_code` | Char(32) | `string="Код сцени"`, `idx`, `copy=False`, `help="Код об'єкта в 3D-моделі (glTF extras code), напр. SAW-1, FG-R1-B01-L1, DOCK-W1"` |
| `f3d_alias` | Char(32) | `string="Другий код сцени"`, `idx`, `copy=False`, `help="Ще один код того самого запису в 3D, якщо модель малює його двома об'єктами (ворота DOCK-W1 і майданчик UNLOAD-1)"` |
| `f3d_kind` | Selection | `[('location','Місце зберігання'),('workcenter','Робочий центр'),('equipment','Обладнання'),('employee','Працівник'),('dock','Ворота'),('zone','Зона'),('vehicle','Транспорт'),('other','Інше')]` — константа модуля `F3D_KIND_SELECTION` у `models/f3d_scene_mixin.py` (її ж бере дзеркало M-10a), `string="Вид у сцені"`, `req`, `idx`, `default=lambda self: self._f3d_kind` |
| `f3d_viewer_available` | Boolean | `compute="_compute_f3d_viewer_available"`, не зберігається: `True`, якщо `_f3d_viewer_installed()` |
| `is_f3d_manager` | Boolean | `compute="_compute_is_f3d_manager"`, не зберігається: `self.env.user.has_group('factory3d_base.group_f3d_manager')` — для `readonly` полів домішки у формах (§3) |

SQL-обмеження (застосовуються до кожного носія окремо — Odoo копіює обмеження домішки в
конкретну модель):

```python
    _f3d_code_uniq = models.Constraint("UNIQUE(f3d_code)", "Код сцени має бути унікальним у межах моделі.")
    _f3d_alias_uniq = models.Constraint("UNIQUE(f3d_alias)", "Другий код сцени має бути унікальним у межах моделі.")
```

`NULL` не конфліктують: записи без коду — скільки завгодно.

`@api.constrains("f3d_code", "f3d_alias")` `_check_f3d_codes` — для кожного запису:
1. якщо `f3d_code` і не `F3D_CODE_RE.match(f3d_code)` → `ValidationError("Код сцени %s: лише великі латинські літери, цифри й дефіси між групами (напр. FG-R1-B01-L1).")`;
2. те саме для `f3d_alias`;
3. `f3d_alias` без `f3d_code` → `ValidationError("Другий код сцени можна задати лише разом з основним.")`;
4. `f3d_alias == f3d_code` → `ValidationError("Другий код сцени збігається з основним.")`;
5. `f3d_alias` дорівнює `f3d_code` або `f3d_alias` іншого запису цієї ж моделі (`search_count` з `active_test=False`) → `ValidationError("Код %s уже використаний записом %s.")`; симетрично `f3d_code` ≠ чужий `f3d_alias`.

Методи:

| Сигнатура | Вхід → вихід | Алгоритм |
|---|---|---|
| `@api.model search_f3d(self, code)` | `code: str` → recordset цієї моделі (0 або 1 запис) | порожній/`None` → порожній recordset; `self.with_context(active_test=False).search(['|', ('f3d_code','=',code), ('f3d_alias','=',code)], limit=1)` |
| `@api.model f3d_resolve(self, code)` | → recordset першої моделі з `_f3d_resolve_order`, де знайдено, інакше `None` | для `m in _f3d_resolve_order`: `if m in self.env` (модель є в реєстрі) і `self.env[m].search_f3d(code)` → повернути |
| `@api.model f3d_resolve_all(self, code)` | → `dict[str, recordset]` лише непорожні | те саме для всіх моделей реєстру, що успадковують домішку: `self.env.registry.descendants(['f3d.scene.mixin'], '_inherit')` мінус абстрактні |
| `f3d_codes(self)` | → `list[str]` | `[c for c in (self.f3d_code, self.f3d_alias) if c]` (ensure_one) |
| `@api.model _f3d_viewer_installed(self)` | → `bool` | `self.env['ir.module.module'].sudo().search_count([('name','=','factory3d_viewer'),('state','=','installed')]) > 0` (рішення менеджера: перевірка стану модуля; окремий метод — щоб тести патчили його через `unittest.mock.patch.object`) |
| `action_f3d_show(self)` | → dict дії (CB-02) | `ensure_one()`; без `f3d_code` → `UserError("Запис не має коду сцени. Заповніть «Код сцени» на вкладці «Завод 3D».")`; якщо `self._f3d_viewer_installed()`: `{'type':'ir.actions.client','tag':'f3d_viewer.action','name':'Завод 3D','target':'current','params':{'code':self.f3d_code,'alias':self.f3d_alias or False,'model':self._name,'res_id':self.id,'kind':self.f3d_kind}}` (тег і ключ `code` — контракт менеджера; решта ключів — довідкові, A-18); інакше `{'type':'ir.actions.client','tag':'display_notification','params':{'title':'Модуль 3D-переглядача не встановлено','message':'Установіть factory3d_viewer, щоб показати %s у 3D.' % self.f3d_code,'type':'warning','sticky':False}}` |
| `@api.model f3d_run_migration(self)` | → dict `display_notification` зі звітом | `if not self.env.user.has_group('factory3d_base.group_f3d_admin'): raise AccessError(...)`; `report = hooks.run_all(self.env)`; повідомлення `"Міграцію виконано: %s" % json.dumps(report, ensure_ascii=False)`, `type='success'`, `sticky=True` |
| `write(self, vals)` / `create(self, vals_list)` | — | R-04: якщо у `vals` є `f3d_code`/`f3d_alias`/`f3d_kind` і `not self.env.su` і користувач без `group_f3d_manager` → `AccessError("Змінювати код сцени може лише менеджер «Завод 3D».")`; далі `super()` |

Домішку одержують (через `_inherit = [<model>, "f3d.scene.mixin"]`): `stock.location`
(`_f3d_kind="location"`), `mrp.workcenter` (`"workcenter"`), `maintenance.equipment`
(`"equipment"`), `hr.employee` (`"employee"`), `f3d.zone` (`"zone"`), `stock.picking.batch`
(`"vehicle"`). Кожен носій розширює `_rec_names_search` своєю `f3d_code` (див. M-03, M-08…).

### M-02 `f3d.zone` — зона цеху (CB-03)

```python
class F3dZone(models.Model):
    _name = "f3d.zone"
    _inherit = ["f3d.scene.mixin"]
    _description = "Зона цеху"
    _order = "sequence, f3d_code"
    _rec_name = "name"
    _rec_names_search = ["name", "f3d_code"]
    _f3d_kind = "zone"
```

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_code` | Char(32) | перевизначення: `required=True` (код зони = код сцени: `Z-RCV-1`, `Z-SHEETS`) |
| `name` | Char(128) | `req`, `string="Назва"` |
| `sequence` | Integer | `default=10` |
| `zone_type` | Selection | `[('receiving','Приймання'),('storage','Склад'),('production','Виробництво'),('assembly','Збирання'),('packing','Пакування'),('shipping','Відвантаження'),('technical','Технічна'),('office','Офіс і побут'),('outdoor','Двір')]`, `req`, `string="Тип"` |
| `is_roof` | Boolean | `default=False`, `string="Дах"`, `help="Контур лежить на рівні покрівлі (z = 9 м), а не на підлозі; лише для типу «Двір»"` — `Z-ROOF` (рішення менеджера, Q-06) |
| `polygon` | Json | `string="Контур, м"`, список точок `[[x, y], …]`, ≥ 3; зберігається як JSON |
| `polygon_text` | Text | `compute="_compute_polygon_text"`, `inverse="_inverse_polygon_text"`: `json.dumps(polygon)` ↔ `json.loads` (помилка розбору → `ValidationError("Контур: очікується JSON-список точок [[x, y], …]")`) |
| `area_m2` | Float | `compute="_compute_geometry"`, `store=True`, `digits=(12,1)`, `string="Площа, м²"` |
| `x_min`, `y_min`, `x_max`, `y_max` | Float | `compute="_compute_geometry"`, `store=True`, `digits=(8,2)` — габаритний прямокутник |
| `color` | Char(7) | `string="Колір"`, `default="#d5d8dc"`, формат `#rrggbb` |
| `description` | Text | `string="Опис"` |
| `root_location_id` | Many2one `stock.location` | `string="Місце в Odoo"`, `ondelete="set null"`, `help="Групова локація, що відповідає зоні (напр. WH/Stock/Сировина/Плити)"` |
| `company_id` | Many2one `res.company` | `req`, `default=lambda self: self.env.company`, `idx` |
| `active` | Boolean | `default=True` |
| `location_ids` | One2many `stock.location` `f3d_zone_id` | `string="Місця зберігання"` |
| `workcenter_ids` | One2many `mrp.workcenter` `f3d_zone_id` | `string="Робочі центри"` |
| `equipment_ids` | One2many `maintenance.equipment` `f3d_zone_id` | `string="Обладнання"` |
| `dock_location_ids` | Many2many `stock.location` | `compute="_compute_docks"` (не зберігається): `location_ids.filtered(lambda l: l.f3d_kind == 'dock')` |
| `location_count`, `workcenter_count`, `equipment_count`, `dock_count` | Integer | `compute="_compute_counts"`, не зберігаються; `search_count` по `f3d_zone_id` (активні) |

Обмеження:

```python
    _f3d_zone_color = models.Constraint("CHECK(color ~ '^#[0-9a-fA-F]{6}$')", "Колір зони — у форматі #rrggbb.")
```

`@api.constrains("polygon")` `_check_polygon` (R-09): `polygon` порожній — дозволено (зона без
контуру); інакше: список довжиною ≥ 3; кожна точка — список/кортеж із 2 чисел (`int`/`float`, не
`bool`); усі `site_x0_m ≤ x ≤ site_x1_m` і `site_y0_m ≤ y ≤ site_y1_m` (параметри CB-12: територія
`plant/infra.py:SITE` = −32…182 × −30…100; надвірні зони виходять за будівлю); площа > 0; `is_roof`
лише при `zone_type='outdoor'` (`"Позначка «Дах» — лише для зон типу «Двір»."`). Текст помилки:
`"Контур зони %s: %s"` із причиною.

Обчислення `_compute_geometry` (`@api.depends("polygon")`): якщо `polygon` порожній → усі нулі;
інакше `area_m2 = |Σ (x_i·y_{i+1} − x_{i+1}·y_i)| / 2` (формула Гаусса), `x_min = min(x)` тощо.
Приклад: `Z-CMP` `[[110,60],[115.6,60],[115.6,71.4],[110,71.4]]` → `area_m2 = 63.8`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `@api.model zone_at(self, x, y, company=None, roof=False)` | кандидати: `search([('active','=',True),('is_roof','=',roof),('x_min','<=',x),('x_max','>=',x),('y_min','<=',y),('y_max','>=',y)], order='sequence')` (дах шукається лише при `roof=True`); для кожного — тест «промінь» (парність перетинів ребер полігона); повернути першу зону, що містить точку; інакше порожній recordset. Точка на ребрі вважається всередині. Приклад: `zone_at(45.5, 5.0)` → `Z-CUT`; `zone_at(0.3, 5.0)` → порожньо (стіна) |
| `action_view_locations/_workcenters/_equipment(self)` | `ir.actions.act_window` на відповідну модель із `domain=[('f3d_zone_id','=',self.id)]`, `context={'default_f3d_zone_id': self.id}` |
| `action_f3d_show(self)` | успадковано (M-01) |

### M-03 `stock.location` — розширення: домішка, зона, ворота (CB-05)

```python
class StockLocation(models.Model):
    _name = "stock.location"
    _inherit = ["stock.location", "f3d.scene.mixin"]
    _f3d_kind = "location"
    _rec_names_search = ["complete_name", "barcode", "f3d_code", "f3d_alias"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_zone_id` | Many2one `f3d.zone` | `string="Зона"`, `ondelete="set null"`, `idx` (оголошується у `models/f3d_zone.py`, W2) |
| `f3d_loc_kind` | Selection | `[('stack','Стос плит'),('bin','Комірка фурнітури'),('shelf','Полиця крайки'),('pallet_cell','Комірка палет ГП'),('kit','Візок / етажерка комплекту'),('area','Майданчик')]`, `string="Вид місця"`, `idx`; значення = `locations[*].kind` макета (A-16); порожньо — не з макета (групові локації, `WH/Stock`, східні ворота) |
| `f3d_capacity` | Float | `digits=(12,2)`, `string="Місткість"`, `default=0`, `help="В одиницях, якими рахується заповненість: аркуші (стос), шт (комірка фурнітури), м (полиця крайки), палети (комірка ГП, PAL-*); 0 — не задано"` (R-21) |
| `f3d_side` | Selection | `[('west','Захід (приймання)'),('east','Схід (відвантаження)')]`, `string="Сторона воріт"` |
| `f3d_dock_no` | Integer | `string="№ воріт"` (1…7 за макетом; обмеження — лише ≥ 1) |
| `f3d_accepts` | Many2many `product.category` | `relation="f3d_dock_product_categ_rel"`, `column1="location_id"`, `column2="categ_id"`, `string="Приймає категорії"`, `help="Порожньо — без обмежень"` |
| `f3d_x`, `f3d_y` | Float | `digits=(8,2)`, `string="X, м"` / `"Y, м"` — центр воріт у системі CB-04 |
| `f3d_dock_width_m` | Float | `digits=(5,2)`, `default=3.4`, `string="Ширина, м"` (`plant/layout.py:DOORS`) |
| `f3d_dock_height_m` | Float | `digits=(5,2)`, `default=4.5`, `string="Висота, м"` (`DOOR_H`) |
| `f3d_dock_picking_type_ids` | Many2many `stock.picking.type` | `compute="_compute_f3d_dock_picking_types"`, не зберігається: `search([('dock_ids','in',self.id)])` |

```python
    _f3d_capacity_nonneg = models.Constraint("CHECK(f3d_capacity >= 0)", "Місткість місця не може бути від'ємною.")
```

`@api.constrains("f3d_kind", "f3d_side", "f3d_dock_no", "usage", "f3d_x", "f3d_y")` `_check_f3d_dock`:
- `f3d_kind` ∉ {`location`, `dock`} → `ValidationError("Місце зберігання може бути лише «Місце зберігання» або «Ворота».")`;
- `f3d_kind == 'dock'`: потрібні `f3d_side` і `f3d_dock_no ≥ 1` (`"Для воріт задайте сторону й номер."`); `usage == 'internal'` (`"Ворота мають бути внутрішньою локацією."`); пара `(company_id, f3d_side, f3d_dock_no)` унікальна серед активних воріт (`"Ворота %s %s уже існують: %s"`); `0 ≤ f3d_x ≤ plant_length_m`, `0 ≤ f3d_y ≤ plant_width_m`;
- `f3d_kind != 'dock'` і задано `f3d_side` або `f3d_dock_no` → `"Сторона й номер воріт задаються лише для виду «Ворота»."`.

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `f3d_register_dock(self)` | для кожних воріт (`f3d_kind=='dock'`): `wh = self.warehouse_id`; `ptype = wh.in_type_id if f3d_side=='west' else wh.out_type_id`; `ptype.dispatch_management = True`; якщо `self not in ptype.dock_ids` → `ptype.dock_ids = [Command.link(self.id)]`; повертає `ptype`. Викликається хуком (R-10) і кнопкою «Зареєструвати як док» (менеджер) |
| `write(self, vals)` | якщо `vals.get('f3d_kind') == 'dock'` або (`'f3d_side' in vals` для воріт) → після `super()` викликати `f3d_register_dock()` (ідемпотентно) |

### M-04 `stock.picking.batch` — розширення: фура, техніка (CB-06)

```python
class StockPickingBatch(models.Model):
    _name = "stock.picking.batch"
    _inherit = ["stock.picking.batch", "f3d.scene.mixin"]
    _f3d_kind = "vehicle"
    _rec_names_search = ["name", "f3d_code", "f3d_truck"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_truck` | Char(64) | `string="Фура"`, `help="Опис або назва фури з макета (не держномер і не код сцени). Код фури в 3D — «Код фури в 3D» (f3d_code); держномер веде модуль двору (рейс, f3d_plate)."`. Після міграції демо дорівнює `x_truck` (R-12). Переглядач і резолвер код фури беруть лише з `f3d_code` (CB-06, X-15); держномер — `factory3d_yard` `f3d.yard.visit.plate` (на пакеті related `f3d_plate`, yard M-07) |
| `f3d_vehicle_id` | Many2one `maintenance.equipment` | `string="Техніка"`, `domain="[('f3d_code','!=',False)]"`, `ondelete="set null"`, `help="Навантажувач або тягач, що виконує пакет (FL-2, FL-6, TUGGER-1)"` |
| `f3d_dock_code` | Char | `related="dock_id.f3d_code"`, `string="Код воріт"`, readonly |
| `f3d_dock_warning` | Char | `compute="_compute_f3d_dock_warning"`, не зберігається (R-19) |

`_compute_f3d_dock_warning` (`@api.depends("dock_id", "dock_id.f3d_accepts", "picking_ids.move_ids.product_id")`):
якщо `dock_id.f3d_accepts` порожні → `False`; інакше `bad = {move.product_id.categ_id для move in picking_ids.move_ids якщо жодна з дозволених категорій не є предком-або-самою (`categ.parent_path` починається з `allowed.parent_path`)}`; `bad` порожня → `False`; інакше
`"Ворота %s приймають: %s. У пакеті є: %s." % (dock_id.f3d_code, ', '.join(allowed.mapped('name')), ', '.join(bad.mapped('name')))`.
Не блокує (`UserError` не кидається).

### M-11 `stock.picking` — довідкові поля з пакета (A-14)

```python
class StockPicking(models.Model):
    _inherit = "stock.picking"
```

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_dock_id` | Many2one `stock.location` | `related="batch_id.dock_id"`, `string="Ворота"`, readonly, не зберігається |
| `f3d_dock_code` | Char | `related="batch_id.dock_id.f3d_code"`, `string="Код воріт"` |
| `f3d_truck` | Char | `related="batch_id.f3d_truck"`, `string="Фура"` |
| `f3d_truck_code` | Char | `related="batch_id.f3d_code"`, `string="Код фури в 3D"` |
| `f3d_vehicle_id` | Many2one `maintenance.equipment` | `related="batch_id.f3d_vehicle_id"`, `string="Техніка"` |

Усі `readonly=True`; редагування — лише через пакет.

### M-05 `f3d.equipment.passport` — паспорт ролі обладнання (CB-07, A-02)

```python
class F3dEquipmentPassport(models.Model):
    _name = "f3d.equipment.passport"
    _description = "Паспорт обладнання"
    _order = "manufacturer, model"
    _rec_name = "name"
    _rec_names_search = ["name", "role", "manufacturer", "model"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `role` | Char(64) | `req`, `idx`, `string="Роль"`, `help="Ключ ролі з equipment_specs.json: beam_saw, compressor, facp…"` |
| `name` | Char | `compute="_compute_name"`, `store=True`: `"%s %s" % (manufacturer, model)` |
| `manufacturer` | Char(128) | `req`, `string="Виробник"` |
| `model` | Char(255) | `req`, `string="Модель"` |
| `reason` | Text | `string="Чому обрано"` |
| `dim_l_mm`, `dim_w_mm`, `dim_h_mm` | Integer | `string="Довжина, мм"` / `"Ширина, мм"` / `"Висота, мм"`; `0` = не опубліковано |
| `dimensions` | Char | `compute="_compute_dimensions"`, `store=True`, `string="Д×Ш×В, мм"`: `" × ".join(str(v) if v else "—" for v in (L, W, H))`; усі нулі → `False` |
| `power_kw` | Float | `digits=(8,2)`, `string="Потужність, кВт"`, `0` = не опубліковано (R-18) |
| `connected_kw` | Float | `digits=(8,2)`, `string="Потужність підключення, кВт"`, `0` = не опубліковано |
| `connected_note` | Text | `string="Про потужність підключення"` |
| `note` | Text | `string="Примітка"` |
| `spec_ids` | One2many `f3d.equipment.spec` `passport_id` | `string="Параметри"` |
| `source_ids` | One2many `f3d.equipment.source` `passport_id` | `string="Джерела"` |
| `equipment_ids` | One2many `maintenance.equipment` `f3d_passport_id` | `string="Одиниці"` |
| `component_of_ids` | Many2many `maintenance.equipment` | `relation="f3d_equipment_component_passport_rel"`, `column1="passport_id"`, `column2="equipment_id"`, `string="У складі одиниць"` |
| `unit_count` | Integer | `compute="_compute_counts"`, `string="Одиниць під паспортом"` = `len(equipment_ids)` |
| `component_count` | Integer | `compute="_compute_counts"` = `len(component_of_ids)` |
| `active` | Boolean | `default=True` |

```python
    _f3d_passport_role_uniq = models.Constraint("UNIQUE(role)", "Роль паспорта має бути унікальною.")
```

`@api.constrains("role")`: `role` відповідає `^[a-z][a-z0-9_]*$` (`"Роль: латиниця, цифри, підкреслення."`).

Методи:

| Сигнатура | Алгоритм |
|---|---|
| `get_num(self, key)` → `float \| None` | `ensure_one()`; `key == 'power_kw'` → `power_kw or None`; `key == 'connected_kw'` → `connected_kw or None`; інакше `spec = spec_ids.filtered(lambda s: s.key == key)[:1]`; `spec.value_num if spec and spec.value_num is not False else None`. Приклад: паспорт `highbay`.`get_num('lumen')` → `20500.0`; `beam_saw`.`get_num('connected_kw')` → `None` |
| `action_view_equipment(self)` | `act_window` `maintenance.equipment`, `domain=[('f3d_passport_id','=',self.id)]` |

### M-06 `f3d.equipment.spec` — параметр паспорта

```python
class F3dEquipmentSpec(models.Model):
    _name = "f3d.equipment.spec"
    _description = "Параметр паспорта обладнання"
    _order = "passport_id, sequence, id"
    _rec_name = "name"
```

| Поле | Тип | Параметри |
|---|---|---|
| `passport_id` | Many2one `f3d.equipment.passport` | `req`, `ondelete="cascade"`, `idx` |
| `sequence` | Integer | `default=10` |
| `key` | Char(64) | `idx`, `string="Ключ"`, `help="Машинний ключ для розрахунків (lumen, airflow_m3h, kva); порожній — лише для показу"` |
| `name` | Char(128) | `req`, `string="Параметр"` (напр. «Довжина різу») |
| `value_text` | Char(512) | `string="Значення"` (як опубліковано: «4300 мм (ряд 3200 / 3800 / 4300 / 5600)») |
| `value_num` | Float | `digits=(16,4)`, `string="Число"` |
| `uom` | Char(32) | `string="Одиниця"` |
| `kind` | Selection | `[('published','Опубліковано виробником'),('estimate','Оцінка'),('derived','Розрахунок')]`, `default='published'`, `req` |

```python
    _f3d_spec_key_uniq = models.Constraint("UNIQUE(passport_id, key)", "Ключ параметра повторюється в паспорті.")
```
(`key` `NULL` — без обмеження). `@api.constrains("value_text","value_num")`: хоча б одне задане
(`value_text` непорожній або `value_num` ≠ `False`) → інакше `"Параметр %s: задайте значення."`.

### M-07 `f3d.equipment.source` — джерело паспорта

| Поле | Тип | Параметри |
|---|---|---|
| `passport_id` | Many2one `f3d.equipment.passport` | `req`, `ondelete="cascade"`, `idx` |
| `sequence` | Integer | `default=10` |
| `url` | Char(1024) | `req`, `string="Посилання"` |
| `name` | Char(128) | `string="Назва"`, `compute="_compute_name"`, `store=True`, `readonly=False`: хост з URL (`urllib.parse.urlparse(url).netloc`), якщо порожнє |
| `kind` | Selection | `[('main','Паспорт'),('connected','Потужність підключення')]`, `default='main'`, `req` |
| `attachment_id` | Many2one `ir.attachment` | `string="PDF"`, `ondelete="set null"` (Q-04: заповнюється вручну) |

`_order = "passport_id, kind, sequence, id"`; `_description = "Джерело паспорта обладнання"`.
`@api.constrains("url")`: починається з `http://` або `https://` (`"Посилання має починатися з http(s)://"`).

### M-08 `maintenance.equipment` — розширення: код, зона, паспорт (C-6.3, CB-07)

```python
class MaintenanceEquipment(models.Model):
    _name = "maintenance.equipment"
    _inherit = ["maintenance.equipment", "f3d.scene.mixin"]
    _f3d_kind = "equipment"
    _rec_names_search = ["name", "serial_no", "f3d_code"]
```

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_zone_id` | Many2one `f3d.zone` | `string="Зона"`, `ondelete="set null"`, `idx` (у `models/f3d_zone.py`) |
| `f3d_passport_id` | Many2one `f3d.equipment.passport` | `string="Паспорт"`, `ondelete="set null"`, `idx` |
| `f3d_component_passport_ids` | Many2many `f3d.equipment.passport` | `relation="f3d_equipment_component_passport_rel"`, `column1="equipment_id"`, `column2="passport_id"`, `string="У складі"` |
| `f3d_role` | Char | `related="f3d_passport_id.role"` |
| `f3d_manufacturer` | Char | `related="f3d_passport_id.manufacturer"` |
| `f3d_model` | Char | `related="f3d_passport_id.model"` |
| `f3d_reason` | Text | `related="f3d_passport_id.reason"` |
| `f3d_power_kw` | Float | `related="f3d_passport_id.power_kw"` |
| `f3d_connected_kw` | Float | `related="f3d_passport_id.connected_kw"` |
| `f3d_dimensions` | Char | `related="f3d_passport_id.dimensions"` |
| `f3d_spec_ids` | One2many | `related="f3d_passport_id.spec_ids"` |
| `f3d_source_ids` | One2many | `related="f3d_passport_id.source_ids"` |
| `f3d_units` | Integer | `related="f3d_passport_id.unit_count"`, `string="Одиниць під паспортом"` |

Усі related — `readonly=True`, не зберігаються. `note` не змінюється модулем (C-6.3).

Метод `f3d_get_num(self, key)` → `self.f3d_passport_id.get_num(key) if self.f3d_passport_id else None` (CB-08).

### M-09 `mrp.workcenter` — розширення

`_inherit = ["mrp.workcenter", "f3d.scene.mixin"]`, `_f3d_kind = "workcenter"`,
`_rec_names_search = ["name", "code", "f3d_code"]`; поле `f3d_zone_id` Many2one `f3d.zone`
(`ondelete="set null"`, `idx`, у `models/f3d_zone.py`). Інших полів немає.

### M-10 `hr.employee` — розширення

`_inherit = ["hr.employee", "f3d.scene.mixin"]`, `_f3d_kind = "employee"`,
`_rec_names_search = ["name", "f3d_code"]`.

Метод `@api.model _f3d_code_from_barcode(self, barcode, workcenter=None)` → `str | False` (R-06):
1. `barcode` порожній → `False`;
2. рядок у таблиці `scene_employee_codes.csv` (`hooks.codes.employee_table(env)`: dict barcode→code) → код;
3. `workcenter` (запис `mrp.workcenter` з `f3d_code`) → `"OP-" + workcenter.f3d_code`;
4. `re.fullmatch(r"OPW(\d+)", barcode)` → `"OP-W%s"`;
5. інакше `False`.

Приклади: `OPSAW1` → `OP-SAW-1` (таблиця); `OPASMLINE1` → `OP-ASMLINE-1`; `OPW3` → `OP-W3`;
новий бейдж `OPNEST2` без таблиці і без РЦ → `False`; з РЦ `NEST-1` → `OP-NEST-1`.

### M-10a `hr.employee.public` — дзеркало коду сцени (X-09)

```python
class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"
```

| Поле | Тип | Параметри |
|---|---|---|
| `f3d_code` | Char(32) | `readonly=True`, `string="Код сцени"` |
| `f3d_alias` | Char(32) | `readonly=True`, `string="Другий код сцени"` |
| `f3d_kind` | Selection | `selection=F3D_KIND_SELECTION` (той самий список, що M-01), `readonly=True`, `string="Вид у сцені"` |

Без `compute`, `default`, `index`, обмежень і методів: `hr.employee.public` — SQL-представлення (`_auto = False`),
стандарт будує його з колонок `hr_employee` за збереженими полями моделі (`hr/models/hr_employee_public.py:_get_fields`,
`init`: `FROM hr_employee e JOIN hr_version v ON v.id = e.current_version_id`; колонки, яких немає в `hr.version`,
беруться з `e.`). Домішку `f3d.scene.mixin` дзеркало **не** успадковує: її `UNIQUE`-обмеження, `_check_f3d_codes` і R-04
`write`/`create` до представлення не застосовні. Не дзеркаляться не збережені `f3d_viewer_available`, `is_f3d_manager`
і кнопка `action_f3d_show` (вона лише у формі `hr.employee`, V-14).

Навіщо (Odoo 19, `hr/models/hr_employee.py`): для користувача без `hr.group_hr_user` `hr.employee.fetch()` і
`search_fetch()` читають значення з `hr.employee.public` і викликають `_check_private_fields(field_names)`; поле, якого
немає в публічній моделі, дає `AccessError`. Збережені поля домішки без `groups` потрапляють у prefetch, тож без
дзеркала будь-яке читання працівника користувачем без прав HR (навіть `name`, `name_search` за `_rec_names_search`
з `f3d_code`) падало б. Із дзеркалом провайдер переглядача `people` (viewer M-01f) і кіоск читають `f3d_code`,
`f3d_alias`, `f3d_kind` працівника без `sudo()`.

Порядок оголошення: у `models/hr_employee.py` клас M-10 (`hr.employee`) — **перед** класом M-10a: `Registry.init_models`
виконує `_auto_init()` і `init()` у порядку оголошення, тож колонки `hr_employee.f3d_*` мають існувати до перебудови
представлення `hr_employee_public` (той самий прийом — `factory3d_access` M-08a, A-17; access додає свої поля
`f3d_access_*` до того самого представлення, імена не перетинаються).

## 3. Представлення й меню

Усі вкладки домішки називаються **«Завод 3D»** і містять групу `group_f3d_scene`: `f3d_code`,
`f3d_alias`, `f3d_kind` (поля з `groups="factory3d_base.group_f3d_manager"` на редагування — для
решти `readonly="1"` через `attrs`: `readonly="not is_f3d_manager"`, де `is_f3d_manager` —
не збережене `Boolean compute` на домішці = `user.has_group(...)`; додати до M-01), і кнопка
`action_f3d_show` (`string="Показати в 3D"`, `type="object"`, `icon="fa-cube"`,
`invisible="not f3d_code"`, клас `btn-secondary`). У заголовку (`<header>`) форм кнопка дублюється
як `btn-primary` з `invisible="not f3d_code or not f3d_viewer_available"`. Поля `is_f3d_manager` і
`f3d_viewer_available` присутні у формі невидимими (`invisible="1"`), бо на них посилаються атрибути.

| ID | XML-id | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `factory3d_base.view_f3d_zone_form` | form `f3d.zone` | `<header>`: «Показати в 3D». Статбокс: `action_view_locations` (`location_count`, «Місця»), `action_view_workcenters` («Робочі центри»), `action_view_equipment` («Обладнання»), `dock_count` («Ворота», без дії). `<sheet>`: `name` (title), група «Зона»: `f3d_code`, `zone_type`, `sequence`, `color` (widget `color`), `root_location_id`, `company_id` (groups `base.group_multi_company`), `active` (widget `boolean_toggle`); група «Геометрія»: `polygon_text` (widget `ace`, options `{'mode':'json'}`), `area_m2` (readonly), `x_min/y_min/x_max/y_max` (readonly, одна лінія «Габарит, м»). Вкладки: «Опис» (`description`), «Місця» (`location_ids` list: `complete_name`, `f3d_code`, `f3d_kind`, `barcode`; readonly), «Робочі центри» (`workcenter_ids`: `code`, `name`, `f3d_code`), «Обладнання» (`equipment_ids`: `f3d_code`, `name`, `category_id`), «Ворота» (`dock_location_ids`: `f3d_code`, `complete_name`, `f3d_side`, `f3d_dock_no`) |
| V-02 | `factory3d_base.view_f3d_zone_list` | list `f3d.zone` | `sequence` (handle), `f3d_code`, `name`, `zone_type`, `area_m2`, `location_count`, `workcenter_count`, `equipment_count`, `root_location_id`, `color` (widget `color`, optional hide); `decoration-muted="not active"`; `default_order` за моделлю |
| V-03 | `factory3d_base.view_f3d_zone_search` | search | поля `name`, `f3d_code`, `root_location_id`; фільтри за `zone_type` (9 — по одному на тип), «Архівні» (`active=False`); group by `zone_type` |
| V-04 | `factory3d_base.view_f3d_zone_kanban` | kanban | картка: кольорова смуга `color`, `name`, `f3d_code`, тип, `area_m2` м², лічильники; клік — форма |
| V-05 | `factory3d_base.view_stock_location_form_f3d` | form inherit `stock.view_location_form` | базова форма локації в 19.0 не має `<notebook>` (поля: `name`, `location_id`, `usage`, групи `additional_info`, «Cyclic Counting», «Logistics»; `barcode` додає `stock_barcode.view_location_form_inherit`), тому `xpath expr="//sheet" position="inside"` → `<notebook><page name="f3d" string="Завод 3D">…</page></notebook>`: група «Код сцени» (стандарт домішки) + `f3d_zone_id`, `f3d_loc_kind`, `f3d_capacity`; група «Ворота» (`invisible="f3d_kind != 'dock'"`): `f3d_side`, `f3d_dock_no`, `f3d_accepts` (widget `many2many_tags`), `f3d_x`, `f3d_y`, `f3d_dock_width_m`, `f3d_dock_height_m`, `f3d_dock_picking_type_ids` (readonly, tags), кнопка `f3d_register_dock` («Зареєструвати як док», `groups=group_f3d_manager`). Кнопка «Показати в 3D» — у `div[@name='button_box']` як stat-кнопка з іконкою `fa-cube` |
| V-06 | `factory3d_base.view_stock_location_list_f3d` | list inherit `stock.view_location_tree2` | після `usage` (у базовому списку 19.0 поля `barcode` немає): `f3d_code` (optional show), `f3d_kind` (optional hide), `f3d_loc_kind` (optional hide), `f3d_capacity` (optional hide), `f3d_zone_id` (optional hide) |
| V-07 | `factory3d_base.view_stock_location_search_f3d` | search inherit `stock.view_location_search` | поле `f3d_code`; фільтри «Ворота» (`f3d_kind='dock'`), «З кодом сцени» (`f3d_code != False`), «Без коду» (`f3d_code = False`); group by `f3d_zone_id` |
| V-08 | `factory3d_base.view_stock_picking_batch_form_f3d` | form inherit **`stock_fleet.stock_picking_batch_form`** (саме це успадковане представлення додає `dock_id`, `vehicle_id`, `vehicle_category_id`, `driver_id`; базове `stock_picking_batch.stock_picking_batch_form` їх не має) | після `dock_id` (xpath `//field[@name='dock_id']`, `position="after"`): `f3d_truck`, `f3d_vehicle_id`; на початку `<sheet>` (`xpath expr="//sheet" position="inside"`... ні — `position="before"` відносно першого елемента `//sheet/*[1]`): `<div class="alert alert-warning" role="alert" invisible="not f3d_dock_warning"><field name="f3d_dock_warning" readonly="1" nolabel="1"/></div>`; вкладка «Завод 3D» після `//page[@name='page_transfers']` (`position="after"`) з полями домішки (`f3d_code` з підписом «Код фури в 3D») |
| V-09 | `factory3d_base.view_stock_picking_batch_list_f3d` | list inherit **`stock_fleet.stock_picking_batch_tree`** (додає `dock_id`, `vehicle_id`, `vehicle_category_id`) | після `dock_id`: `f3d_truck` (optional show), `f3d_vehicle_id` (optional hide), `f3d_code` (optional hide) |
| V-10 | `factory3d_base.view_picking_form_f3d` / `view_picking_list_f3d` | form/list inherit `stock.view_picking_form`, `stock.vpicktree` | form: після `origin` група readonly `f3d_dock_id` (`invisible="not f3d_dock_id"`), `f3d_truck` (`invisible="not f3d_truck"`), `f3d_vehicle_id` (`invisible="not f3d_vehicle_id"`); list: після `origin` `f3d_dock_id` (optional show), `f3d_truck` (optional hide), `f3d_vehicle_id` (optional hide). Це заміна демо-представлень `factory3d.view_picking_form_dock` / `view_picking_list_dock` |
| V-11 | `factory3d_base.view_mrp_workcenter_form_f3d` / `_list_f3d` | inherit `mrp.mrp_workcenter_view` (form), `mrp.mrp_workcenter_tree_view` (list) | form: вкладка «Завод 3D» (домішка + `f3d_zone_id`); list: `f3d_code` (optional show), `f3d_zone_id` (optional hide) |
| V-12 | `factory3d_base.view_maintenance_equipment_form_f3d` | form inherit `maintenance.hr_equipment_view_form` | вкладка «Завод 3D»: домішка + `f3d_zone_id`; вкладка «Паспорт»: `f3d_passport_id`, `f3d_units`, група readonly: `f3d_manufacturer`, `f3d_model`, `f3d_role`, `f3d_dimensions`, `f3d_power_kw`, `f3d_connected_kw`; `f3d_reason` (readonly, full width); `f3d_spec_ids` (list readonly: `name`, `value_text`, `value_num`, `uom`, `kind`); `f3d_source_ids` (list readonly: `kind`, `name`, `url` widget `url`); `f3d_component_passport_ids` (list editable для менеджера: `name`, `manufacturer`, `model`). Заголовок: кнопка «Показати в 3D» |
| V-13 | `factory3d_base.view_maintenance_equipment_list_f3d` / `_search_f3d` | inherit `maintenance.hr_equipment_view_tree` / `hr_equipment_view_search` | list: `f3d_code` (optional show), `f3d_passport_id` (optional hide), `f3d_zone_id` (optional hide); search: поле `f3d_code`, фільтр «З кодом сцени», «Без паспорта» (`f3d_passport_id = False`), group by `f3d_zone_id`, `f3d_passport_id` |
| V-14 | `factory3d_base.view_hr_employee_form_f3d` | form inherit `hr.view_employee_form` | вкладка «Завод 3D» (домішка); `f3d_code` з help «Код людини в сцені (OP-SAW-1); бейдж `barcode` — без дефісів» |
| V-15 | `factory3d_base.view_f3d_equipment_passport_form` / `_list` / `_search` | `f3d.equipment.passport` | form: `name` (title readonly), статбокс `action_view_equipment` (`unit_count`), група: `role`, `manufacturer`, `model`, `active`; група «Габарити й потужність»: `dim_l_mm`, `dim_w_mm`, `dim_h_mm`, `dimensions` (readonly), `power_kw`, `connected_kw`; `reason` (full width); вкладки «Параметри» (`spec_ids` editable list: `sequence` handle, `name`, `value_text`, `value_num`, `uom`, `key`, `kind`), «Джерела» (`source_ids` editable: `kind`, `name`, `url` widget `url`, `attachment_id`), «Потужність підключення» (`connected_note`), «Примітка» (`note`), «Одиниці» (`equipment_ids` readonly: `f3d_code`, `name`), «У складі одиниць» (`component_of_ids` readonly). list: `manufacturer`, `model`, `role`, `unit_count`, `power_kw`, `connected_kw`; search: `name`, `role`, `manufacturer`; group by `manufacturer` |
| V-16 | `factory3d_base.view_f3d_equipment_spec_list`, `view_f3d_equipment_source_list` | list (самостійні, для меню «Параметри паспортів») | spec: `passport_id`, `name`, `value_text`, `value_num`, `uom`, `key`, `kind`; source: `passport_id`, `kind`, `name`, `url` |
| V-17 | меню та дії (`views/f3d_menus.xml`) | `ir.ui.menu`, `ir.actions.act_window`, `ir.actions.server` | див. таблицю нижче |

Меню (CB-09). `web_icon="factory3d_base,static/description/icon.png"` на кореневому:

| XML-id | Назва | Батько | sequence | Групи | Дія |
|---|---|---|---|---|---|
| `menu_f3d_root` | Завод 3D | — | 75 | `group_f3d_user` | — |
| `menu_f3d_plant` | Завод | `menu_f3d_root` | 20 | `group_f3d_user` | — |
| `menu_f3d_zone` | Зони | `menu_f3d_plant` | 10 | `group_f3d_user` | `action_f3d_zone` (`f3d.zone`, views kanban,list,form; `context={'search_default_group_zone_type':1}`) |
| `menu_f3d_dock` | Ворота | `menu_f3d_plant` | 20 | `group_f3d_user` | `action_f3d_dock` (`stock.location`, list,form; `domain=[('f3d_kind','=','dock')]`, `context={'default_f3d_kind':'dock','default_usage':'internal'}`) |
| `menu_f3d_equipment` | Обладнання зі сцени | `menu_f3d_plant` | 30 | `group_f3d_user` | `action_f3d_equipment` (`maintenance.equipment`, list,form; `domain=[('f3d_code','!=',False)]`, `context={'search_default_group_f3d_zone':1}`) |
| `menu_f3d_passport` | Паспорти обладнання | `menu_f3d_plant` | 40 | `group_f3d_user` | `action_f3d_equipment_passport` (list,form) |
| `menu_f3d_config` | Налаштування | `menu_f3d_root` | 99 | `group_f3d_manager` | — |
| `menu_f3d_config_spec` | Параметри паспортів | `menu_f3d_config` | 20 | `group_f3d_manager` | `action_f3d_equipment_spec` (list) |
| `menu_f3d_config_source` | Джерела паспортів | `menu_f3d_config` | 21 | `group_f3d_manager` | `action_f3d_equipment_source` (list) |
| `menu_f3d_config_params` | Параметри системи | `menu_f3d_config` | 95 | `group_f3d_admin` | `action_f3d_config_parameter` (`ir.config_parameter`, list,form; `domain=[('key','=like','factory3d.%')]`) |
| `menu_f3d_config_migration` | Повторити міграцію демо-даних | `menu_f3d_config` | 96 | `group_f3d_admin` | `ir.actions.server` `action_f3d_run_migration`: `model_id=model_f3d_scene_mixin`, `state='code'`, `code="action = env['f3d.scene.mixin'].f3d_run_migration()"` (у `data/f3d_actions.xml`) |

Зарезервовані sequence під `menu_f3d_root` для інших модулів: 10 viewer, 30 telemetry,
40 machine_connect, 50 energy, 55 genset (міст `factory3d_genset`, `td_genset`), 60 yard, 70 access, 80 bms,
85 fire_safety, 90 iot_sim (X-32). Base займає 20 (`menu_f3d_plant`) і 99 (`menu_f3d_config`).

Правило налаштувань модулів (X-32): пункт «Налаштування <модуля>» (дія `res.config.settings` модуля або підменю
його параметрів) ставиться під `factory3d_base.menu_f3d_config` з `sequence` = резерв модуля з переліку вище
(viewer 10, telemetry 30, machine_connect 40, energy 50, genset 55, yard 60, access 70, bms 80, fire_safety 85,
iot_sim 90); довідники модуля (типи, правила, пристрої) можуть лишатися в його власному корені під `menu_f3d_root`.
Власні пункти base під `menu_f3d_config` — поза чужим резервом: 20, 21 (довідники паспортів, резерв base) і 95, 96
(системні, після всіх модулів).

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_f3d_zone_user,f3d.zone user,model_f3d_zone,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_zone_manager,f3d.zone manager,model_f3d_zone,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_equipment_passport_user,f3d.equipment.passport user,model_f3d_equipment_passport,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_equipment_passport_manager,f3d.equipment.passport manager,model_f3d_equipment_passport,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_equipment_spec_user,f3d.equipment.spec user,model_f3d_equipment_spec,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_equipment_spec_manager,f3d.equipment.spec manager,model_f3d_equipment_spec,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_equipment_source_user,f3d.equipment.source user,model_f3d_equipment_source,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_equipment_source_manager,f3d.equipment.source manager,model_f3d_equipment_source,factory3d_base.group_f3d_manager,1,1,1,1
```

Абстрактна `f3d.scene.mixin` рядків не потребує. Доступ до стандартних моделей — їхні групи;
поля `f3d_*` на них читає кожен, хто читає запис; запис — R-04. `hr.employee` без `hr.group_hr_user` читається
через `hr.employee.public` (стандарт): `f3d_code`, `f3d_alias`, `f3d_kind` там є завдяки дзеркалу M-10a (X-09);
`hr.employee.public` рядків у CSV не потребує (права стандарту — `base.group_user`).

### 4.2 Групи (`security/f3d_security.xml`), Odoo 19 (`res.groups.privilege`)

```xml
<record id="module_category_factory3d" model="ir.module.category">
    <field name="name">Завод 3D</field><field name="sequence">60</field>
</record>
<record id="privilege_f3d" model="res.groups.privilege">
    <field name="name">Завод 3D</field><field name="category_id" ref="module_category_factory3d"/>
    <field name="sequence">10</field>
</record>
<record id="group_f3d_user" model="res.groups">
    <field name="name">Користувач</field><field name="privilege_id" ref="privilege_f3d"/><field name="sequence">10</field>
</record>
<record id="group_f3d_manager" model="res.groups">
    <field name="name">Менеджер</field><field name="privilege_id" ref="privilege_f3d"/><field name="sequence">20</field>
    <field name="implied_ids" eval="[Command.link(ref('group_f3d_user'))]"/>
</record>
<record id="group_f3d_admin" model="res.groups">
    <field name="name">Адміністратор</field><field name="privilege_id" ref="privilege_f3d"/><field name="sequence">30</field>
    <field name="implied_ids" eval="[Command.link(ref('group_f3d_manager'))]"/>
</record>
<record id="base.group_system" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_f3d_admin'))]"/>
</record>
<record id="stock.group_stock_user" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_f3d_user'))]"/>
</record>
<record id="mrp.group_mrp_user" model="res.groups">
    <field name="implied_ids" eval="[Command.link(ref('group_f3d_user'))]"/>
</record>
```

Привілей `privilege_f3d` містить лише три групи base (драбина CB-10). Інші модулі додають групи
`group_f3d_<модуль>_<роль>` у власний `res.groups.privilege` з `category_id=factory3d_base.module_category_factory3d`,
не в `privilege_f3d` (X-19).

### 4.3 Record rules

| XML-id | Модель | Домен | Групи |
|---|---|---|---|
| `f3d_zone_rule_company` | `f3d.zone` | `['|', ('company_id','=',False), ('company_id','in',company_ids)]` | глобальне (без груп) |

Паспорти/специфікації/джерела — без компанії (довідник вендорів спільний).

### 4.4 Правило R-04 (захист полів домішки)

`write`/`create` з `f3d_code`, `f3d_alias`, `f3d_kind` дозволені суперкористувачу (`env.su`, хуки)
і членам `group_f3d_manager`; іншим — `AccessError`. Поля воріт (`f3d_side`, `f3d_dock_no`,
`f3d_accepts`, `f3d_x`, `f3d_y`, `f3d_dock_*`) і `f3d_zone_id` — за стандартними правами
на модель (комірник зі `stock.group_stock_manager` може перенести локацію в іншу зону).

## 5. Дані

### 5.1 `data/ir_config_parameter.xml` (`noupdate="1"`)

| key | value | XML-id |
|---|---|---|
| `factory3d.base.environment` | `test` | `param_environment` |
| `factory3d.base.plant_length_m` | `150` | `param_plant_length` |
| `factory3d.base.plant_width_m` | `72` | `param_plant_width` |
| `factory3d.base.plant_height_m` | `9` | `param_plant_height` |
| `factory3d.base.site_x0_m` | `-32` | `param_site_x0` (`plant/infra.py:SITE`) |
| `factory3d.base.site_y0_m` | `-30` | `param_site_y0` |
| `factory3d.base.site_x1_m` | `182` | `param_site_x1` |
| `factory3d.base.site_y1_m` | `100` | `param_site_y1` |
| `factory3d.base.keep_x_fields` | `False` | `param_keep_x_fields` |
| `factory3d.base.uninstall_restore_x_fields` | `True` | `param_uninstall_restore` |
| `factory3d.base.migration_state` | `pending` | `param_migration_state` (хук пише `skipped`/`partial`/`done`) |
| `factory3d.base.migration_report` | `{}` | `param_migration_report` |

Читання булевих: `get_param(key, 'False') in ('True', 'true', '1')`.

### 5.2 Data-файли з макета і генератор `tools/gen_data.py`

Запуск (розробник, з кореня репозиторію): `python3 -m odoo_addons.factory3d_base.tools.gen_data`
(або `python3 odoo_addons/factory3d_base/tools/gen_data.py --root .`). Читає
`dist/odoo_demo.json`, `plant/layout.py` (import), `plant/equipment_specs.json`,
`plant/equipment.py`, `plant/odoo_flows.py:NAMES`, `README.md` не читає (список A-06 зашитий у
генераторі). Пише файли нижче детерміновано (сортування, без часових міток), щоб `git diff` показував
лише справжні зміни макета.

**`data/f3d.equipment.passport.csv`** (93 рядки; xml-id `passport_<role>`):
`id,role,manufacturer,model,reason,dim_l_mm,dim_w_mm,dim_h_mm,power_kw,connected_kw,connected_note,note`.
`dimensions_mm.L/W/H` → цілі, `null` → `0`; `power_kw null` → `0`; `connected_kw null` → `0`;
`note` → `note` (3 ролі: `chp`, `board_rack`, `board_forklift`).

**`data/f3d.equipment.spec.csv`** (999 рядків; xml-id `spec_<role>_<nnn>`):
`id,passport_id:id,sequence,key,name,value_text,value_num,uom,kind`.
1. Рядки `specs` (951): `sequence = 10·n`, `key` порожній, `name` = ключ словника (uk), `value_text` =
   значення як рядок, `value_num` порожньо, `uom` порожньо, `kind = published`.
2. Рядки додаткових числових ключів (48 непорожніх значень; `null`/`[]` пропускаються):
   `sequence = 1000 + 10·n`, `key` = ключ JSON, `name`/`uom` з таблиці нижче; скаляр-число →
   `value_num` і `value_text` = те саме число; рядок (`controller`, `drive`) → `value_text`;
   список (`beam_levels_mm_*`, `exhaust_module_mm`, `silencer_mm`) → `value_text = json.dumps(v, ensure_ascii=False)`;
   `kind = published`.

| key | name | uom |
|---|---|---|
| `lumen` | Світловий потік | лм |
| `watt` | Споживана потужність | Вт |
| `airflow_m3h` | Витрата повітря | м³/год |
| `required_m3h` | Потрібна витрата (розрахунок) | м³/год |
| `heat_kw` | Теплова потужність | кВт |
| `heat_kw_75` / `heat_kw_50` | Теплова потужність при 75 % / 50 % | кВт |
| `kva` / `kva_standby` | Потужність PRP / ESP | кВА |
| `fuel_lph_75` | Витрата палива при 75 % | л/год |
| `tank_l` | Бак | л |
| `controller` | Контролер | — |
| `kwh` | Ємність | кВт·год |
| `wp` | Потужність модуля | Вт |
| `kw_ac` | Потужність AC | кВт |
| `gas_m3h` / `gas_m3h_75` / `gas_m3h_50` | Витрата газу при 100 / 75 / 50 % | м³/год |
| `eta_el` / `eta_th` | ККД електричний / тепловий | % |
| `min_load` | Мінімальне тривале навантаження | % |
| `current_a` | Струм | А |
| `exhaust_module_mm` / `silencer_mm` | Модуль вихлопу / глушник | мм |
| `beam_clear_mm` | Просвіт балки | мм |
| `frame_depth_mm` | Глибина рами | мм |
| `level_capacity_kg` | Навантаження на ярус | кг |
| `upright_mm` | Стійка | мм |
| `design_stack_max_kg` | Макс. маса стосу (проєкт) | кг |
| `bay_pitch_mm` | Крок прольоту | мм |
| `beam_height_mm` | Висота балки | мм |
| `beam_levels_mm_full_stack` / `beam_levels_mm_075_stack` | Рівні балок (повний стос / 0,75 стосу) | мм |
| `capacity_kg` | Вантажопідйомність | кг |
| `load_centre_mm` | Центр ваги | мм |
| `capacity_at_1035mm_kg` | Вантажопідйомність при c = 1035 мм | кг |
| `aisle_mm` | Робочий прохід | мм |
| `lift_mm` | Висота підйому | мм |
| `truck_w_mm` / `truck_l_mm` | Ширина / довжина навантажувача | мм |
| `drive` | Привод | — |

Невідомий ключ → генератор падає з помилкою (щоб новий ключ у макеті не пройшов непоміченим).

**`data/f3d.equipment.source.csv`** (252 рядки; xml-id `source_<role>_<kind>_<n>`):
`id,passport_id:id,sequence,kind,url,name` — `sources` (215, `kind=main`), `connected_sources`
(37, `kind=connected`); `name` = хост URL.

**`data/f3d_zone_data.xml`** (45 записів, `noupdate="1"`, xml-id `zone_<slug>`, slug = код у нижньому
регістрі з `-`→`_`: `zone_z_rcv_1`, `zone_z_sheets`): `f3d_code`, `name`, `zone_type` (додаток C),
`polygon` (`eval="[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]"` з `plant/layout.py:ZONES` — 34 цехових; для 11
надвірних — прямокутники додатка C.2, які генератор рахує з констант `plant/infra.py` і координат
`plant/site.py:881–919` за правилом A-19), `color`, `description`, `sequence` (порядок у `ZONES`:
10, 20, …; надвірні — 400…500), `is_roof` (лише `Z-ROOF`). `root_location_id` не в XML — ставить хук
(шляхи залежать від бази).

**`data/scene_docks.csv`** (14 рядків): `code,side,no,barcode,alias,x,y,width,height,accepts,zone`:
`DOCK-W1,west,1,UNLOAD-1,UNLOAD-1,0.0,5.0,3.4,4.5,Плитні матеріали,Z-RCV-1` … `DOCK-E7,east,7,DOCK-E7,,150.0,65.0,3.4,4.5,,Z-OUT-7`
(`accepts` — назви `product.category` через `;`; повний перелік — додаток D).

**`data/scene_locations.csv`** (689 рядків, усі ключі `locations` макета): `code,kind,capacity` —
`kind` ∈ {`stack` 123, `bin` 144, `shelf` 24, `pallet_cell` 360, `kit` 20, `area` 18}; `capacity` —
число або порожньо (`null` у макеті: 20 `kit` + 15 `area`); разом із місткістю 654 (`stack` 60 під
порталом / 55 у стелажі, `bin` 6…1666, `shelf` 2200, `pallet_cell` 2, `PAL-1…3` 14). Приклад:
`PLT-01A,stack,60`; `FUR-R1-S01-L1,bin,66`; `UNLOAD-1,area,`; `KIT-01,kit,`.

**`data/scene_zone_links.csv`** (225 рядків): `zone,kind,value` з `kind ∈ {prefix, code, workcenter, equipment, root}`:
- `prefix` (7): `Z-SHEETS:PLT-`, `Z-SHEETS:RCK-`, `Z-HW:FUR-`, `Z-EDGE:EB-`, `Z-PKS:PAL-`, `Z-FG:FG-R`, `Z-PRE:KIT-`;
- `code` (29): `Z-RCV-k:UNLOAD-k` (7), `Z-RCV-1..3:QC-PLT-1..3` (3), `Z-RCV-4:QC-1`, `Z-PKS:PACK-STORE`, `Z-FAC:PAINT-STORE`, `Z-POST:POST-STAGE`, `Z-PRE:FRONTS-1,2,3,7,8` (5), `Z-FAC:FRONTS-4,5,6` (3), `Z-OUT-k:DOCK-Ek` (7); примітка: для `UNLOAD-k` хук знаходить локацію за `f3d_alias` (після кроку 2 її `f3d_code` = `DOCK-Wk`);
- `workcenter` (35): з `zones[*].workcenters`;
- `equipment` (133): 29 `ventilation.units[*].zone`, 33 `fire.groups` (`FA-BOILER` → `Z-BOILER`), 32 `lighting.groups`, 26 за A-06 і 13 за A-19 (додаток F: `GATE-W`→`Z-GATE-W`; `GATE-E`, `TRUCK-SCALE`→`Z-GATE-E`; `TURNSTILES`→`Z-KPP`; `GENSET`, `BESS`, `CHP`, `PV-INV`→`Z-ENERGY`; `BOILER`→`Z-BOILER`; `PV-ROOF`, `SMOKE-VENTS`, `LPS`→`Z-ROOF`; `ATS-1`→`Z-ELEC`);
- `root` (21): `Z-RCV-k:WH/Вхід/Ворота k`, `Z-SHEETS:WH/Stock/Сировина/Плити`, `Z-HW:WH/Stock/Сировина/Фурнітура`, `Z-EDGE:WH/Stock/Сировина/Крайка`, `Z-PKS:WH/Stock/Сировина/Пакування`, `Z-PRE:WH/Stock/Передвиробництво`, `Z-POST:WH/Пост-виробництво`, `Z-FG:WH/Stock/Готова продукція`, `Z-OUT-k:WH/Відвантаження/Ворота k`.

**`data/scene_employee_codes.csv`** (35 рядків): `barcode,f3d_code,name` — додаток B.

**`data/scene_equipment_codes.csv`** (208 рядків): `code,xmlid,legacy_serial,name,role,components,zone`:
`code` — код сцени; `xmlid` — `eq_<slug>` (демо-xml-id у модулі `factory3d`, slug як у `plant/odoo_rpc.key`:
`eq_fl_c1`, `eq_qf_c1`, `eq_lt_rcv_1`); `legacy_serial` — лише для 7 навантажувачів; `role` — порожньо
для `CHARGING`, `SPRINKLERS`, `AIR-RING`; `components` — ролі через `;` (`acb;power_meter`);
`zone` — код зони або порожньо (лише для 119 рядків `equipment` вище; РЦ-обладнання зону бере з РЦ).

### 5.3 `post_init_hook(env)` — кроки, джерела, ідемпотентність, очікувані кількості

`hooks/__init__.py:run_all(env) -> dict` виконує кроки по черзі, кожен повертає словник
лічильників; `post_init_hook(env)` = `run_all(env)` + запис звіту. Усе в транзакції установки; виняток
на будь-якому кроці відкочує установку (крім кроку 10, що виконується лише після успішної звірки).
Логер `odoo.addons.factory3d_base.hooks`, рівень INFO на кожен крок із кількостями.

| # | Функція | Джерело | Що робить | Ідемпотентність | Очікувано (копія демо) | Чиста база |
|---|---|---|---|---|---|---|
| 1 | `docks.register(env)` | `scene_docks.csv`, `stock.location.barcode` | для кожного рядка: `loc = search([('barcode','=',barcode)], limit=1)`; немає → пропуск із WARNING; `loc.write({f3d_code, f3d_alias, f3d_kind:'dock', f3d_side, f3d_dock_no, f3d_x, f3d_y, f3d_dock_width_m, f3d_dock_height_m, f3d_accepts: [Command.set(ids категорій за назвою)]})`; `loc.f3d_register_dock()`; після циклу: `in_type.dock_ids = Command.set(west)`, `out_type.dock_ids = Command.set(east)` (A-10) | повторний `write` тими ж значеннями | `docks: 14`, `in_type.dock_ids: 7`, `out_type.dock_ids: 7` | `docks: 0` (WARNING) |
| 2 | `codes.locations(env)` | `stock.location` з `barcode`, `usage='internal'`, під `warehouse_id.view_location_id`, крім `warehouse.lot_stock_id`; `scene_locations.csv` | (а) `f3d_code = barcode` якщо `f3d_code` порожній і `barcode` відповідає R-01 і не зайнятий; ворота з кроку 1 уже мають код — пропуск; (б) для кожного рядка `scene_locations.csv`: `loc = env['stock.location'].search_f3d(code)` (для `UNLOAD-k` знаходить ворота за псевдонімом); `loc.write({'f3d_loc_kind': kind, 'f3d_capacity': capacity or 0})` (R-21) | (а) лише порожні `f3d_code`; (б) перезапис тими ж значеннями | `locations: 682` нових (696 усього з 14 воріт), `kinds: 689`, `capacities: 654` | 0 |
| 3 | `codes.workcenters(env)` | `mrp.workcenter.code` | `f3d_code = code` якщо порожній і валідний | так само | `workcenters: 35` | 0 |
| 4 | `codes.employees(env)` | `hr.employee.barcode`, `scene_employee_codes.csv`, `mrp.workcenter.employee_ids` | `f3d_code = _f3d_code_from_barcode(barcode, wc)` для працівників без коду; `wc` = перший РЦ, де `employee in wc.employee_ids` | так само | `employees: 35` | 0 |
| 5 | `codes.equipment(env)` | `maintenance.equipment.serial_no`, `scene_equipment_codes.csv`, `ir.model.data` (`module='factory3d'`) | R-07: код за `serial_no` ∈ `code` (201) → за `xmlid` (`ir.model.data` `module='factory3d', name=xmlid, model='maintenance.equipment'`) → за `legacy_serial` (7); пишеться лише порожнім | так само | `equipment: 208`, `by_serial: 201`, `by_xmlid_or_legacy: 7`, `unmatched: 0` | 0 |
| 6 | `passports.link(env)` | `scene_equipment_codes.csv`, паспорти з data | для рядків із `role`: `eq = env['maintenance.equipment'].search_f3d(code)`; `eq.f3d_passport_id = ref('factory3d_base.passport_'+role)`; `eq.f3d_component_passport_ids = Command.set([...])` | перезапис тими ж значеннями | `linked: 205`, `components: 63`, `no_passport: 3` | 0 |
| 7 | `zones.bind(env)` | `scene_zone_links.csv` | `root` → `root_location_id = search([('complete_name','=',value)])`; `prefix` → `stock.location.search([('f3d_code','=like', value+'%')]).f3d_zone_id = zone`; `code` → `search_f3d(value)`; `workcenter` → `mrp.workcenter.search_f3d`; `equipment` → `maintenance.equipment.search_f3d`; потім для обладнання з `workcenter_id` і без зони: `f3d_zone_id = workcenter_id.f3d_zone_id` | перезапис | `roots: 21`, `locations: 695`, `workcenters: 35`, `equipment: 168` | `zones: 45` (з data), прив'язок 0 |
| 8 | `batches.migrate(env)` | `x_fields.read_manual_field` для `x_dock`, `x_truck`, `x_vehicle` на `stock.picking` | R-11…R-13 | за `batch_id` і `description` | `batches_updated: 6`, `batches_created: 18`, `pickings_attached: 18`, `pickings_total_in_batches: 24` | `skipped` (полів немає) |
| 9 | `batches.verify(env)` | ті самі | R-13; повертає `mismatches: list[str]` | — | `mismatches: 0`, `moves_changed: 0` | — |
| 10 | `x_fields.drop_demo(env)` | `ir.ui.view` (xml-id `factory3d.view_picking_form_dock`, `factory3d.view_picking_list_dock`), `ir.model.fields` `x_dock/x_truck/x_vehicle` (`state='manual'`) | лише якщо `mismatches == 0` і `keep_x_fields` False: `unlink` представлень (через `ir.model.data` → `res_id`), далі `drop_manual_fields(env, 'stock.picking', ['x_dock','x_truck','x_vehicle'])` | повторно — нічого | `views_dropped: 2`, `fields_dropped: 3` | 0 |
| 11 | `report.write(env, report)` | — | `migration_state` = `skipped` (крок 8 skipped) / `partial` (`mismatches` > 0 або `keep_x_fields`) / `done`; `migration_report` = JSON усіх лічильників + `ts` | перезапис | `done` | `skipped` |

Порядок читання `x_*`: `read_manual_field(env, 'stock.picking', 'x_dock')` → `dict[picking_id, value]`
через `cr.execute("SELECT id, x_dock FROM stock_picking WHERE x_dock IS NOT NULL")` лише якщо поле існує
в `ir.model.fields` (інакше `{}`); ORM поля `x_*` не використовує (після видалення реєстр їх не знає).

### 5.4 `uninstall_hook(env)`

1. Якщо `factory3d.base.uninstall_restore_x_fields` ≠ True → лише крок 4.
2. `restore_manual_fields(env, 'stock.picking', [('x_dock','Ворота (док)'), ('x_truck','Фура'), ('x_vehicle','Техніка')])`:
   створює відсутні `ir.model.fields` (`ttype='char'`, `state='manual'`) — колонки з'являються.
3. `cr.execute("UPDATE stock_picking p SET x_dock = l.f3d_code FROM stock_picking_batch b JOIN stock_location l ON l.id = b.dock_id WHERE p.batch_id = b.id")`;
   `UPDATE … SET x_truck = COALESCE(b.f3d_code, b.f3d_truck) … WHERE p.batch_id = b.id AND (b.f3d_code IS NOT NULL OR b.f3d_truck IS NOT NULL)`;
   `UPDATE … SET x_vehicle = e.f3d_code FROM stock_picking_batch b JOIN maintenance_equipment e ON e.id = b.f3d_vehicle_id WHERE p.batch_id = b.id`.
   Очікувано на демо: 21 / 6 / 3 заповнених значень.
4. `env['ir.config_parameter'].search([('key','=like','factory3d.base.%')]).unlink()`.
5. Пакети, зони (дані модуля), паспорти — видаляє стандартна деінсталяція; переміщення, локації,
   обладнання, працівники, РЦ — не чіпаються (колонки `f3d_*` зникають разом із полями).

### 5.5 `data/neutralize.sql`

```sql
-- factory3d_base: нейтралізована копія проду — тестове середовище (CB-10).
UPDATE ir_config_parameter SET value = 'test' WHERE key = 'factory3d.base.environment';
```

## 6. Крони й фонові процеси

Немає.

## 7. HTTP/JSON API

Немає. Усі дані — через ORM/XML-RPC стандартно (`search_read`). Для `plant/odoo_pull.py` заміна полів —
§11.4.

## 8. Сервісна частина

Немає (ні колектора, ні емулятора).

## 9. Алгоритми й правила

| ID | Правило |
|---|---|
| R-01 | **Формат коду сцени**: `^[A-Z0-9]+(-[A-Z0-9]+)*$`, ≤ 32 символів. Таксономія з макета (додаток A): локації `PLT-01A`, `RCK-R2-1C`, `FUR-R1-S02-L3`, `EB-U1-S1-L1`, `FG-R1-B01-L1`, `KIT-01`, `FRONTS-1`, `UNLOAD-1`, `QC-PLT-1`, `QC-1`, `PAL-1`, `PACK-STORE`, `PAINT-STORE`, `POST-STAGE`, `OUT-STAGE`; РЦ `SAW-1`…`PACKLINE-1`; обладнання `FL-1`, `COMPRESSOR`, `RV-05`, `QF-C1`, `LT-RCV-1`, `FA-FAC`; люди `OP-SAW-1`, `OP-W1`; ворота `DOCK-W1`…`DOCK-E7`; зони `Z-RCV-1`, `Z-SHEETS`; фури `TRUCK-IN-1`, `TRUCK-OUT-3`. Невалідні: `saw-1`, `SAW_1`, `SAW-`, `-SAW`, `SAW--1`, `Ворота 1` |
| R-02 | **Унікальність**: `f3d_code` і `f3d_alias` унікальні в межах моделі (SQL); псевдонім не збігається з жодним кодом/псевдонімом тієї ж моделі (Python). Між моделями збіги дозволені (A-15): РЦ `SAW-1` і обладнання `SAW-1` |
| R-03 | **Резолвер**: `f3d_resolve(code)` перебирає `_f3d_resolve_order` = зона → локація → РЦ → обладнання → працівник → пакет; повертає перший знайдений. `SAW-1` → `mrp.workcenter`; `UNLOAD-1` → `stock.location` (за псевдонімом); `Z-CUT` → `f3d.zone`; `XYZ-9` → `None` |
| R-04 | **Права на коди**: див. §4.4 |
| R-05 | **Код локації з штрихкоду**: кандидати — внутрішні локації під `view_location_id` складу з `barcode`, крім `lot_stock_id`; `barcode` валідний за R-01 → `f3d_code`. На демо `WHSTOCK` виключається як `lot_stock_id`. `f3d_kind` лишається `location` (ворота обробляє крок 1 раніше й мають `dock`) |
| R-06 | **Код працівника** — M-10 `_f3d_code_from_barcode`; застосовується лише до порожнього `f3d_code`; зміна бейджа код не змінює |
| R-07 | **Код обладнання**: `serial_no ∈ scene_equipment_codes.code` → код; інакше `ir.model.data(module='factory3d', model='maintenance.equipment', res_id=id).name ∈ xmlid` → код; інакше `serial_no ∈ legacy_serial` → код; інакше без коду + WARNING. 7 навантажувачів: `FL-4369→FL-1`, `FL-4912→FL-2`, `FL-4731→FL-3`, `FL-4374→FL-4`, `FL-4193→FL-5`, `FL-4606→FL-C1`, `FL-4787→FL-C2` |
| R-08 | **Зона локації/РЦ/обладнання** — за `scene_zone_links.csv` (§5.2): `prefix` через `=like`, `code` точно, обладнання РЦ — зона РЦ. Нові локації користувача зони не отримують автоматично (ставить технолог або `zone_at` у майбутніх модулях) |
| R-09 | **Контур зони**: ≥ 3 точок, числа, у межах території `[site_x0_m, site_x1_m] × [site_y0_m, site_y1_m]` = `[−32, 182] × [−30, 100]` (`plant/infra.py:SITE`), площа > 0 (M-02). Площа — формула Гаусса. Приклади: `Z-SHEETS` (14.6,0.6)–(41.4,45.4) → 1200.6 м²; `Z-FAC` → 1235.0; `Z-RCV-7` (0.6,60.15)–(13.4,71.4) → 144.0; `Z-YARD-W` (−32,0)–(0,72) → 2304.0; `Z-ROOF` (0,0)–(150,72) → 10800.0. Надвірні контури виведено за A-19 (габарит об'єктів моделі + 1 м) |
| R-10 | **Реєстрація доку**: ворота `west` → `warehouse.in_type_id.dock_ids`, `east` → `warehouse.out_type_id.dock_ids`; `dispatch_management=True` на типі. Після хука `in_type.dock_ids` = {`WH/Вхід/Ворота 1…7`}, `out_type.dock_ids` = {`WH/Відвантаження/Ворота 1…7`} (батьківська `WH/Відвантаження` прибирається, A-10). Стандарт Odoo 19 (`stock_fleet`): `batch.dock_id` обмежено `child_of allowed_dock_ids`; при записі `dock_id` або `batch_id` стандарт переписує `location_dest_id` (incoming/internal) чи `location_id` (outgoing) рухів на док — це очікувана поведінка |
| R-11 | **Групування переміщень у пакети** (крок 8): для кожного `stock.picking` з непорожнім `x_dock`, `x_truck` або `x_vehicle`, упорядкованих за `id`: (а) `x_truck` непорожній → пакет = існуючий за xml-id `factory3d.batch_<slug(x_truck)>` або `search([('description','=like', x_truck+' %')], limit=1)` або `picking.batch_id`; якщо не знайдено — створити як у (б) з `f3d_code=f3d_truck=x_truck`; (б) інакше, якщо `picking.batch_id` порожній → створити пакет: `picking_type_id=picking.picking_type_id`, `dock_id = env['stock.location'].search_f3d(x_dock)` (якщо `x_dock`; не знайдено → mismatch), `vehicle_category_id = ref('factory3d.vehcat_truck')` (через `ir.model.data`, якщо є) при `x_dock`, `f3d_vehicle_id = env['maintenance.equipment'].search_f3d(x_vehicle)` при `x_vehicle`, `scheduled_date=picking.scheduled_date`, `user_id=picking.user_id`, `description = ' · '.join(filter(None, [x_truck, x_dock, x_vehicle]))`. Один пакет на документ (Q-02). Створення — ORM без `picking_ids` (тоді `stock_fleet` не чіпає рухів) |
| R-12 | **Прив'язка документа до пакета** (A-09): `cr.execute("UPDATE stock_picking SET batch_id = %s WHERE id = %s AND batch_id IS NULL", (bid, pid))`; після всіх — `env['stock.picking'].invalidate_model(['batch_id'])`, `env['stock.picking.batch'].invalidate_model(['picking_ids','state','scheduled_date'])`; для створених пакетів: усі документи `done`/`cancel` → `batch._compute_state()` (стандарт дає `done`); інакше `batch.action_confirm()` (стандарт: `_sanity_check` + `in_progress`; документи вже `assigned`). Існуючі 6 пакетів: `write({'f3d_code': x_truck, 'f3d_truck': x_truck})` без `dock_id` у `vals` |
| R-13 | **Звірка** (крок 9): для кожного документа з `x_*`: `x_dock` → `picking.batch_id.dock_id.f3d_code == x_dock`; `x_truck` → `batch_id.f3d_code == x_truck`; `x_vehicle` → `batch_id.f3d_vehicle_id.f3d_code == x_vehicle`; знімок `{move.id: (location_id, location_dest_id, state)}` усіх рухів цих документів до кроку 8 дорівнює знімку після; кожна розбіжність — рядок `"WH/IN/00123: x_dock=DOCK-W5, batch.dock=None"` |
| R-14 | **Читання manual-поля** (CB-11): `read_manual_field(env, model, name) -> dict[int, str]`: якщо `ir.model.fields.search_count([('model','=',model),('name','=',name)]) == 0` → `{}`; інакше SQL `SELECT id, "<name>" FROM <table> WHERE "<name>" IS NOT NULL AND "<name>" <> ''` (`name` перевіряється регулярним виразом `^x_[a-z0-9_]+$` перед підстановкою) |
| R-15 | **Видалення manual-полів**: `drop_manual_fields(env, model, names)`: `env['ir.model.fields'].search([('model','=',model),('name','in',names),('state','=','manual')]).unlink()` — Odoo сам прибирає колонки; перед цим викликач має видалити представлення, що посилаються на поля (крок 10 робить це для двох демо-представлень; інші представлення з `x_dock` шукати `ir.ui.view.search([('arch_db','ilike','x_dock')])` і при наявності — не видаляти поля, а записати `mismatch`) |
| R-16 | **Відновлення manual-полів**: `restore_manual_fields(env, model, spec: list[tuple[name, label]])` → створює відсутні `ir.model.fields` (`model_id`, `name`, `field_description=label`, `ttype='char'`, `state='manual'`); повертає кількість створених |
| R-17 | **Роздача паспорта на одиниці**: паспорт прив'язаний до ролі; одиниця отримує `f3d_passport_id` за `scene_equipment_codes.role`; складові «у складі» — `components` того ж рядка (на код, не на роль). `unit_count` = кількість одиниць із цим паспортом: `forklift` → 6 (`FL-1,3,4,5,C1,C2`), `roofvent` → 25, `highbay` → 29, `main_switchboard` → 7, `beam_saw` → 2, `compressor` → 1. Паспорти без одиниць (14 ролей: `robot_return`, `uv_oven`, `paint_pump`, `strapping`, `briquetting_press`, `busbar_main`, `tapoff`, `fabric_duct`, `network_switch`, `nvr`, `panic_bar`, `earthing`, `wastewater`, `fire_hydrant_cabinet`) — лише складові або довідкові (`fire_hydrant_cabinet` — ні те, ні інше; лишається довідником) |
| R-18 | **Семантика нулів у паспорті**: `power_kw = 0`, `connected_kw = 0`, `dim_* = 0` означають «не опубліковано» (у макеті `null`; значень 0 немає: 46 паспортів без `power_kw`, 76 без `connected_kw`, 32 без `H`). `get_num` повертає `None` для нуля полів `power_kw`/`connected_kw`; для `spec.value_num` нуль — справжній нуль |
| R-19 | **Попередження про категорію на воротах** (M-04): категорія товару «підходить», якщо дорівнює дозволеній або є її нащадком (`parent_path`). На демо: пакет на `DOCK-W4` з `FUR-*` → без попередження; пакет на `DOCK-W1` з `EB2-ANT` (Крайка) → `"Ворота DOCK-W1 приймають: Плитні матеріали. У пакеті є: Крайка."` |
| R-20 | **`zone_at`** — M-02; точка на межі двох зон → зона з меншим `sequence` (зони макета не перетинаються, зазори 0.3–0.4 м) |
| R-21 | **Вид і місткість місця** (FR-13): `f3d_loc_kind` і `f3d_capacity` беруться з `locations[*].kind` / `capacity` макета через `scene_locations.csv`; `capacity null` → `0` («не задано»). Заповненість, яку рахує переглядач: `fill = Σ quant.quantity / f3d_capacity` при `f3d_capacity > 0`, інакше не визначена (`kit`, `area` без `PAL-*`). Одиниця місткості — та, якою макет рахує заповненість цього виду: `stack` — аркуші (`арк`), `bin` — `шт`, `shelf` — `м`, `pallet_cell` і `PAL-*` — палети/упаковки `PACK…`. Приклад: `PLT-02A` (стос під порталом) `capacity=60`, залишок 45 арк → `fill=0.75`; `FG-R1-B01-L1` `capacity=2`, 1 палета → `0.5`; `KIT-01` → `fill=None`. Нові локації користувача: вид/місткість ставить технолог (вкладка «Завод 3D») |

## 10. Стани й переходи

Власних машин станів немає. `factory3d.base.migration_state`: `pending` (після data) →
`skipped` | `partial` | `done` (хук); `partial` → `done` після усунення причини та
`f3d_run_migration` (адміністратор). Стани пакетів — стандартні (`draft → in_progress → done/cancel`);
міграція створює пакети в `done` (усі документи `done`) або `in_progress`.

## 11. Обробка помилок

1. **Немає переглядача** — `action_f3d_show` повертає повідомлення, не виняток (AC-09).
2. **Код не знайдено в базі** (`f3d_resolve`) — `None`; виклики з інших модулів мають це обробляти.
3. **Міграція — розбіжність** (R-13): поля `x_*` не видаляються, стан `partial`, список у
   `migration_report.mismatches`; установка модуля не падає. Адміністратор правит дані й запускає
   `f3d_run_migration`.
4. **Заміна полів для `plant/odoo_pull.py` і переглядача** (Q-09): `x_dock` → `batch_id.dock_id.f3d_code`
   (або `f3d_dock_code` на `stock.picking`), `x_truck` → `batch_id.f3d_code` (`f3d_truck_code`),
   `x_vehicle` → `batch_id.f3d_vehicle_id.f3d_code`; `search_read` `stock.picking` з
   `fields=['f3d_dock_code','f3d_truck_code','f3d_truck','f3d_vehicle_id']` працює без join.
5. **Локацію-ворота переназначили** (`f3d_kind` з `dock` на `location`): `write` не чистить
   `dock_ids` типів операцій автоматично — лише попередження в логах; менеджер прибирає вручну
   (операція рідкісна; не автоматизуємо, щоб не ламати відкриті пакети).
6. **Часові пояси**: модуль не працює з датами, крім `scheduled_date` пакета (копія з документа, UTC).
7. **Дублікат коду при імпорті** (крок 2/5 натрапив на зайнятий код) — пропуск + WARNING,
   лічильник `conflicts`; не виняток.
8. **Відсутні довідники на чистій базі** (категорії товарів «Плитні матеріали» тощо) —
   `f3d_accepts` лишаються порожніми; WARNING.

## 12. Acceptance Criteria

Формат: Given / When / Then; тип перевірки: **UT** (юніт-тест у модулі), **TC** (сценарій на копії
демо-бази, §13.2), **MAN** (ручна перевірка в інтерфейсі).

| ID | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given `f3d.zone`; When створюємо з `f3d_code` ∈ {`Z-TEST-1`, `A1`, `FG-R1-B01-L1`}; Then збережено. When `f3d_code` ∈ {`z-test`, `Z_TEST`, `Z-`, `-Z`, `Z--1`, 33 символи}; Then `ValidationError` | UT |
| AC-02 | FR-01 | Given зона `Z-T1`; When друга зона `Z-T1`; Then `IntegrityError`/`ValidationError` (SQL unique) | UT |
| AC-03 | FR-01 | Given РЦ з `f3d_code='T-1'`; When обладнання з `f3d_code='T-1'`; Then збережено (різні моделі) | UT |
| AC-04 | FR-01 | Given локація A `f3d_code='D-1'`, `f3d_alias='U-1'`; When локація B з `f3d_code='U-1'` або `f3d_alias='D-1'`; Then `ValidationError`. When A `f3d_alias='D-1'`; Then `ValidationError`. When `f3d_alias` без `f3d_code`; Then `ValidationError` | UT |
| AC-05 | FR-02 | Given локація з кодом `D-1`, псевдонім `U-1`; When `search_f3d('D-1')`, `search_f3d('U-1')`; Then той самий запис; `search_f3d('')` → порожньо; архівований запис теж знаходиться | UT |
| AC-06 | FR-02 | Given зона `X-1`, локація `X-1`, РЦ `X-1`; When `f3d_resolve('X-1')`; Then зона. When зону архівовано/видалено; Then локація. When `f3d_resolve('NOPE-0')`; Then `None` | UT |
| AC-07 | FR-02 | When `f3d_resolve_all('X-1')`; Then dict із ключами `f3d.zone`, `stock.location`, `mrp.workcenter`, без порожніх | UT |
| AC-08 | FR-03 | Given `_f3d_viewer_installed()` повертає `True` (патч `unittest.mock.patch.object`); When `action_f3d_show()` на РЦ `SAW-1`; Then результат дорівнює `{'type':'ir.actions.client','tag':'f3d_viewer.action','name':'Завод 3D','target':'current','params':{'code':'SAW-1','alias':False,'model':'mrp.workcenter','res_id':<id>,'kind':'workcenter'}}`; `f3d_viewer_available` = True. Окремо без патча на базі без `factory3d_viewer`: `_f3d_viewer_installed()` = False | UT |
| AC-09 | FR-03 | Given модуль `factory3d_viewer` не встановлений; When `action_f3d_show()`; Then `tag=='display_notification'`, `params.title=='Модуль 3D-переглядача не встановлено'`, `params.type=='warning'`, `params.message` містить код; без коду — `UserError`; `f3d_viewer_available` = False | UT |
| AC-10 | FR-04 | Given чиста база з локаціями `WH/Stock/A` (`barcode='A-1'`), `WH/Stock/B` (`barcode='b-1'`), `WH/Stock` (`barcode='WHSTOCK'`); When `codes.locations(env)`; Then `A-1` отримав код, `b-1` ні (невалідний), `WH/Stock` ні; повтор — без змін. TC: на копії демо 696 локацій із кодом | UT + TC |
| AC-11 | FR-04/06 | Given копія демо; When установка; Then 14 локацій `f3d_kind='dock'`: `DOCK-W1…W7` з `f3d_alias='UNLOAD-1…7'`, `barcode` незмінний `UNLOAD-k`, `f3d_side='west'`, `f3d_x=0`, `f3d_y ∈ {5,15,…,65}`; `DOCK-E1…E7` `east`, `f3d_x=150`, без псевдоніма. UT: `docks.register` на синтетичних локаціях з барком `UNLOAD-1`/`DOCK-E1` | UT + TC |
| AC-12 | FR-04 | Given РЦ `code='T-9'` без `f3d_code`; When `codes.workcenters`; Then `f3d_code='T-9'`. TC: 35 | UT + TC |
| AC-13 | FR-04/09 | Given працівники з бейджами `OPSAW1`, `OPW3`, `OPNEW7` (останній у `employee_ids` РЦ `NEW-7`), `ZZ` (без РЦ); When `codes.employees`; Then `OP-SAW-1`, `OP-W3`, `OP-NEW-7`, без коду. TC: 35 кодів, Administrator без коду | UT + TC |
| AC-14 | FR-04 | Given обладнання `serial_no='SAW-1'`, `serial_no='FL-4369'` з xml-id `factory3d.eq_fl_1`, `serial_no='FL-4912'` без xml-id, `serial_no='ZZ-1'` (не в таблиці); When `codes.equipment`; Then `SAW-1`, `FL-1`, `FL-2` (legacy), без коду + `unmatched=1`. TC: 208, `unmatched=0`, кількість `maintenance.equipment` незмінна (208) | UT + TC |
| AC-15 | FR-05 | Given установка; When читаємо `f3d.zone`; Then 45 записів з кодами додатка C, типи: 7 `receiving`, 7 `storage`, 5 `production`, 1 `assembly`, 1 `packing`, 7 `shipping`, 4 `technical`, 2 `office`, 11 `outdoor`; `is_roof` = True лише у `Z-ROOF`; контури надвірних — додаток C.2 | UT |
| AC-16 | FR-05 | Given зона `Z-CMP` з контуром `[[110,60],[115.6,60],[115.6,71.4],[110,71.4]]`; Then `area_m2=63.8`, `x_min=110`, `y_max=71.4`. When контур із 2 точок / точка `[200, 0]` / `[[1,1],[2,2],[3,3]]` (площа 0) / не-JSON у `polygon_text`; Then `ValidationError` | UT |
| AC-17 | FR-05 | When `zone_at(45.5, 5.0)`; Then `Z-CUT`; `zone_at(0.3, 5.0)` → порожньо; `zone_at(14.6, 0.6)` (кут `Z-SHEETS`) → `Z-SHEETS`; `zone_at(140, 65)` → `Z-OUT-7`; `zone_at(-7.3, 5.0)` (фура `TRUCK-IN-1`) → `Z-YARD-W`; `zone_at(172, -14)` (автоваги) → `Z-GATE-E`; `zone_at(128.5, 76.2)` (генератор) → `Z-ENERGY`; `zone_at(75, 36)` з виключенням `is_roof` (`zone_at(x, y, roof=False)`) → `Z-CNC`, а не `Z-ROOF` (дах не бере участі в пошуку на підлозі: параметр `roof=False` за замовчуванням) | UT |
| AC-18 | FR-05 | Given зона з 2 локаціями (одна `dock`), 1 РЦ, 1 обладнанням; Then `location_count=2`, `dock_count=1`, `dock_location_ids` = ворота, `workcenter_count=1`, `equipment_count=1`; архівована локація не рахується | UT |
| AC-19 | FR-05 | Given копія демо; Then `root_location_id` у 21 зоні (`Z-SHEETS` → `WH/Stock/Сировина/Плити`, `Z-RCV-1` → `WH/Вхід/Ворота 1`, `Z-OUT-7` → `WH/Відвантаження/Ворота 7`); `Z-SHEETS.location_count=123`, `Z-HW=144`, `Z-EDGE=24`, `Z-PKS=4`, `Z-FG=360`, `Z-PRE=17`, `Z-FAC=4`, `Z-POST=1`, `Z-RCV-1=2`, `Z-RCV-4=2`, `Z-RCV-5=1`, `Z-OUT-k=1`; `Z-CUT.workcenter_count=6`, `Z-ASM=7`; `Z-ELEC.equipment_count = 20` (16 + `ATS-1` + `LT-ELEC`, `FA-ELEC`, `EF-ELEC`); `Z-ENERGY.equipment_count=4`, `Z-BOILER=2` (`BOILER`, `FA-BOILER`), `Z-ROOF=3`, `Z-GATE-E=2`, `Z-GATE-W=1`, `Z-KPP=1`; `Z-YARD-W/E`, `Z-PARKING`, `Z-FIREWATER`, `Z-WASTE` — 0 | TC |
| AC-20 | FR-06 | Given внутрішня локація; When `f3d_kind='dock'` без сторони/номера → `ValidationError`; з `west`/1 → ок; друга `west`/1 → `ValidationError`; `f3d_kind='location'` з `f3d_dock_no=2` → `ValidationError`; `f3d_kind='zone'` на локації → `ValidationError` | UT |
| AC-21 | FR-06 | Given ворота `west`/1 у складі `WH`; When `f3d_register_dock()`; Then `WH.in_type_id.dispatch_management=True`, ворота ∈ `in_type_id.dock_ids`; повтор — без дублювання; `east` → `out_type_id`. TC: `in_type.dock_ids` = 7 західних, `out_type.dock_ids` = 7 східних, `WH/Відвантаження` не в списку | UT + TC |
| AC-22 | FR-06 | Given ворота з `f3d_accepts=[Плитні матеріали]`, пакет із документом, де товар категорії «Крайка»; Then `f3d_dock_warning` містить `Крайка`; товар дочірньої категорії «Плитні матеріали/ХДФ» → без попередження; ворота без категорій → `False`; збереження пакета не блокується | UT |
| AC-23 | FR-06 | When ворота з `f3d_x=151` або `f3d_y=-1`; Then `ValidationError` | UT |
| AC-24 | FR-06 | Given копія демо; When відкриваємо `BATCH/IN/00001`; Then `allowed_dock_ids` = 7 західних воріт; `dock_id` = `WH/Вхід/Ворота 1`, `f3d_dock_code='DOCK-W1'` | TC |
| AC-25 | FR-07 | Given копія демо; Then `BATCH/IN/00001…3`, `BATCH/OUT/00004…6` мають `f3d_code` і `f3d_truck` = `TRUCK-IN-1/2/3`, `TRUCK-OUT-1/2/3`, `dock_id` незмінний | TC |
| AC-26 | FR-07 | Then усього 24 пакети: 18 нових; 15 із `dock_id` і без `f3d_code` (по одному на `WH/IN/00123…00127, 00131…00135`, `WH/OUT/00412, 00414, 00415, 00417, 00419`), 3 внутрішні з `f3d_vehicle_id` (`WH/INT/00061→FL-2`, `00071→FL-6`, `00072→FL-6`) без `dock_id`; `picking_type_id` пакета = тип документа; `vehicle_category_id`=«Фура» на пакетах із доком | TC |
| AC-27 | FR-07 | Then пакети документів `WH/IN/00123…00127`, `WH/INT/00071` у стані `done`; решта нових — `in_progress`; знімок `stock.move (location_id, location_dest_id, state)` 42 документів до і після установки збігається; `stock.quant` не змінилися | TC |
| AC-28 | FR-07 | Then `migration_state='done'`, `migration_report.mismatches=[]`, `ir.model.fields` без `x_dock/x_truck/x_vehicle` для `stock.picking`, `ir.ui.view` `factory3d.view_picking_form_dock`/`_list_dock` відсутні, форма переміщення відкривається без помилки | TC |
| AC-29 | FR-07 | Given `keep_x_fields='True'` до установки; Then пакети створені, поля `x_*` лишилися зі значеннями, `migration_state='partial'` | TC |
| AC-30 | FR-07 | Given установку виконано; When `f3d_run_migration()` адміністратором; Then кількості пакетів/кодів/зв'язків не змінилися, звіт `batches_created=0` | TC |
| AC-31 | FR-07 | Given установку виконано; When деінсталяція; Then `x_dock/x_truck/x_vehicle` існують, значення на 21/6/3 документах дорівнюють початковим (знімок перед установкою); 24 пакети лишаються (бізнес-дані); видалено лише зони, паспорти/специфікації/джерела, параметри `factory3d.base.*`; локації/обладнання/РЦ/працівники на місці | TC |
| AC-32 | FR-08 | Given установка на чисту базу; Then 93 `f3d.equipment.passport`, ролі з `equipment_specs.json` (`beam_saw` → `HOMAG`, `SAWTEQ S-310 з підйомним столом (S-310/43/22)`, `dim_l_mm=9957`, `dim_w_mm=6514`, `dim_h_mm=0`, `power_kw=11`, `connected_kw=0`, `connected_note` непорожній) | UT |
| AC-33 | FR-08 | Then 999 `f3d.equipment.spec` (`beam_saw`: 14 рядків, перший `name='Довжина різу'`, `value_text='4300 мм (ряд 3200 / 3800 / 4300 / 5600)'`; `highbay`: рядок `key='lumen'`, `value_num=20500`, `uom='лм'`), 252 `f3d.equipment.source` (`beam_saw`: 2 `main` + 2 `connected`) | UT |
| AC-34 | FR-08 | Given копія демо; Then 205 одиниць із `f3d_passport_id`, 3 без (`CHARGING`, `SPRINKLERS`, `AIR-RING`); `passport_forklift.unit_count=6`, `passport_roofvent=25`, `passport_highbay=29`, `passport_main_switchboard=7`; `maintenance.equipment` і далі 208 | TC |
| AC-35 | FR-08 | Then `EDGE-1.f3d_component_passport_ids` = {`robot_return`}; `SWB-1` = {`acb`, `power_meter`}; `WATER` = {`eyewash`, `wastewater`}; `LT-RCV-1` = {`lighting_control`}; усього 63 зв'язки, 61 одиниця зі складовими | TC |
| AC-36 | FR-08 | Given `SAW-1`; Then `f3d_role='beam_saw'`, `f3d_manufacturer='HOMAG'`, `f3d_power_kw=11`, `f3d_dimensions='9957 × 6514 × —'`, `len(f3d_spec_ids)=14`, `len(f3d_source_ids)=4`, `f3d_units=2` | TC |
| AC-37 | FR-08 | When `passport_highbay.get_num('lumen')` → 20500.0; `get_num('watt')` → 126.0; `passport_beam_saw.get_num('connected_kw')` → `None`; `get_num('power_kw')` → 11.0; `get_num('nope')` → `None`; `SAW-1.f3d_get_num('power_kw')` → 11.0 | UT |
| AC-38 | FR-08 | Given копія демо; Then `maintenance.equipment.note` усіх 208 записів побайтово дорівнює знімку до установки | TC |
| AC-39 | FR-09 | Given копія демо; Then `hr.employee.f3d_code` для 35 бейджів = додаток B (повна перевірка таблицею) | TC |
| AC-40 | FR-09 | When `_f3d_code_from_barcode` з прикладами M-10; Then очікувані значення | UT |
| AC-41 | FR-10 | Then групи `group_f3d_user/manager/admin` існують, `manager.implied_ids ∋ user`, `admin ∋ manager`, `base.group_system.implied_ids ∋ admin`, `stock.group_stock_user ∋ user`, `mrp.group_mrp_user ∋ user`; привілей «Завод 3D» | UT |
| AC-42 | FR-10 | Given користувач лише з `group_f3d_user`; Then читає `f3d.zone`/паспорти, `write`/`create`/`unlink` → `AccessError`; з `group_f3d_manager` — усе дозволено | UT |
| AC-43 | FR-10 | Given користувач `stock.group_stock_manager` без `group_f3d_manager`; When `location.write({'f3d_code':'X-1'})`; Then `AccessError`; `write({'name':'Нова'})` — ок; з `group_f3d_manager` — ок | UT |
| AC-44 | FR-10 | Then існують меню з xml-id таблиці §3 із указаними `sequence`, `parent_id`, групами; `menu_f3d_root.sequence=75` | UT |
| AC-45 | FR-10 | Given 2 компанії, зона компанії B; When користувач компанії A шукає зони; Then зона B не видна; зона без компанії видна обом | UT |
| AC-46 | FR-11 | Then усі 12 параметрів §5.1 існують зі значеннями за замовчуванням (крім `migration_state`, що після хука ≠ `pending`) | UT |
| AC-47 | FR-11 | Given чиста база (без `x_*`); Then `migration_state='skipped'`, звіт без помилок, установка успішна | UT |
| AC-48 | FR-11 | Given чиста база з установленим модулем і 1 зоною, 1 локацією з кодом; When `uninstall_hook(env)`; Then параметри `factory3d.base.*` відсутні, локація існує; `restore_manual_fields` створив `x_dock/x_truck/x_vehicle` | UT |
| AC-49 | FR-11 | When виконати `data/neutralize.sql` (через `cr.execute(file content)`); Then `environment='test'`; файл виконується без помилки | UT |
| AC-50 | FR-11 | Given користувач `group_f3d_manager` без `admin`; When `f3d_run_migration()`; Then `AccessError`; адміністратор → dict `display_notification` | UT |
| AC-51 | FR-12 | Given пакет із `dock_id` (ворота `D-1`), `f3d_code='TRUCK-T-1'`, `f3d_truck='Фура плит (тест)'` (опис, не держномер — X-15), `f3d_vehicle_id` (обладнання `FL-T`), документ у пакеті; Then на документі `f3d_dock_code='D-1'`, `f3d_truck_code='TRUCK-T-1'`, `f3d_truck='Фура плит (тест)'`, `f3d_vehicle_id.f3d_code='FL-T'`; `search_read` з цими полями повертає значення; документ без пакета → `False` | UT |
| AC-52 | FR-12 | Given копія демо; When `search_read('stock.picking', [], fields=['name','f3d_dock_code','f3d_truck_code','f3d_vehicle_id'])`; Then 21 документ із `f3d_dock_code` (= колишній `x_dock`), 6 із `f3d_truck_code`, 3 з `f3d_vehicle_id` | TC |
| AC-53 | FR-13 | Given локації з кодами `PLT-T1`, `FUR-T1`, `UNLOAD-T1` (ворота з псевдонімом) і файл `scene_locations.csv`, підмінений тестом на 3 рядки (`PLT-T1,stack,60`; `FUR-T1,bin,66`; `UNLOAD-T1,area,`); When `codes.locations(env)`; Then `PLT-T1.f3d_loc_kind='stack'`, `f3d_capacity=60`; `FUR-T1` → `bin`/66; ворота → `area`/0 (знайдено за псевдонімом); повтор — без змін; `f3d_capacity=-1` → `IntegrityError`; `f3d_loc_kind='rack'` → `ValueError` селекції | UT |
| AC-54 | FR-13 | Given копія демо; Then `f3d_loc_kind` заповнено на 689 локаціях (`pallet_cell` 360, `bin` 144, `stack` 123, `shelf` 24, `kit` 20, `area` 18), `f3d_capacity > 0` на 654; `PLT-01A`=60, `RCK-R1-1A`=55, `EB-U1-S1-L1`=2200, `FG-R1-B01-L1`=2, `PAL-1`=14, `FUR-R1-S01-L1`=66; `KIT-01` і `UNLOAD-1` = 0; `DOCK-E1`, `WH/Stock` — вид порожній | TC |
| AC-55 | FR-14 | Given працівник `OP-SAW-T` (`f3d_code` записано `sudo()`), користувач `u` лише з `base.group_user` (без `hr.group_hr_user`); When `env['hr.employee.public'].with_user(u).search_read([('f3d_code','=','OP-SAW-T')], ['name','f3d_code','f3d_alias','f3d_kind'])`; Then 1 рядок, `f3d_code='OP-SAW-T'`, `f3d_alias=False`, `f3d_kind='employee'`. When `env['hr.employee'].with_user(u).browse(emp.id)` читає `name` і `f3d_code`; Then без `AccessError` (prefetch полів домішки проходить `_check_private_fields`), `f3d_code='OP-SAW-T'`; `env['hr.employee'].with_user(u).search([('f3d_code','=','OP-SAW-T')])` → цей працівник; `name_search('OP-SAW-T')` знаходить його. Then поля M-10a `readonly`, модель `hr.employee.public` не має обмеження `_f3d_code_uniq` | UT |

## 13. План тестування

### 13.1 Юніт-тести (`odoo.tests`, теги `post_install`, `-at_install`, `f3d`, `f3d_base`)

Запуск: `odoo-bin -d f3d_test -i factory3d_base --test-tags /factory3d_base --stop-after-init`
(чиста база з демо-даними Odoo вимкненими: `--without-demo=all`).

`tests/common.py` — `class F3DCase(TransactionCase)` з `setUpClass`:
- `cls.company = env.company`; `cls.wh = env['stock.warehouse'].search([('company_id','=',company.id)], limit=1)`;
- користувачі: `cls.user_reader` (groups `base.group_user` + `group_f3d_user`), `cls.user_manager`
  (+ `group_f3d_manager`), `cls.user_stock_mgr` (`base.group_user` + `stock.group_stock_manager`, без `f3d_manager` — увага: `stock.group_stock_user` неявно дає `f3d_user`), `cls.user_admin` (`group_f3d_admin`);
- `cls.categ_boards = product.category «Плитні матеріали»`, `cls.categ_hdf` (дочірня «ХДФ»), `cls.categ_edge` («Крайка»);
- `cls.loc_in = stock.location` `WH/Вхід-Т` (internal, під `wh.view_location_id`), `cls.dock_w1` (`barcode='UNLOAD-T1'`), `cls.dock_e1` (`barcode='DOCK-TE1'`) — не ворота до виклику хелперів;
- `cls.wc = mrp.workcenter` `code='SAW-T'`; `cls.eq = maintenance.equipment` `serial_no='SAW-T'`; `cls.emp = hr.employee` `barcode='OPSAWT'`;
- хелпери: `make_zone(code, polygon=None, **vals)`, `make_dock(loc, side, no, x, y)`, `make_batch(pickings, dock=None, **vals)`, `make_picking(ptype, products, state)`, `viewer_installed(flag)` (контекстний менеджер: `unittest.mock.patch.object(F3dSceneMixin, '_f3d_viewer_installed', return_value=flag)`), `with_data_file(name, rows)` (контекстний менеджер, що підміняє читання `data/scene_*.csv` у `hooks` на задані рядки), `snapshot_moves(pickings)`.

| Файл / клас | Тест | AC | Фікстури | Що саме assert |
|---|---|---|---|---|
| `test_scene_mixin.py::TestCodeFormat` | `test_valid_codes`, `test_invalid_codes` | AC-01 | `make_zone` | `ValidationError` для кожного невалідного; збережений `f3d_code` для валідних |
| `::TestUniqueness` | `test_unique_in_model`, `test_cross_model_allowed`, `test_alias_rules` | AC-02…04 | зона, локація, РЦ, обладнання | `IntegrityError` в `mute_logger` + `cr.savepoint`; успішне створення крос-модельне; 4 випадки псевдоніма |
| `::TestSearch` | `test_search_f3d_code_alias`, `test_search_empty`, `test_search_archived`, `test_resolve_order`, `test_resolve_all` | AC-05…07 | зона `X-1`, локація `X-1`, РЦ `X-1` | рівність recordset; `None`; порядок |
| `::TestShow` | `test_show_with_viewer`, `test_show_without_viewer`, `test_show_no_code`, `test_viewer_detection_real` | AC-08, AC-09 | `viewer_installed(True/False)` | точна рівність усього dict дії (`assertEqual`); `tag`, `params.title`; `UserError`; без патча `_f3d_viewer_installed()` дорівнює `ir.module.module` `factory3d_viewer` `state=='installed'` |
| `test_employee.py::TestEmployeeCode` | `test_from_table`, `test_from_workcenter`, `test_opw_rule`, `test_unknown`, `test_hook_employees` | AC-13, AC-40 | працівники 4 шт., РЦ `NEW-7` з `employee_ids` | значення M-10; після `codes.employees(env)` коди на місці; повтор не змінює |
| `::TestEmployeePublic` | `test_public_mirror_read`, `test_private_read_without_hr_rights`, `test_search_by_code_without_hr_rights`, `test_mirror_readonly_no_constraint` | AC-55 | `cls.emp` з `f3d_code='OP-SAW-T'` (через `sudo()`), користувач `base.group_user` без `hr.group_hr_user` (`new_test_user(..., groups='base.group_user')`) | значення `search_read` з `hr.employee.public`; `with_user(u)` читання `name`/`f3d_code` на `hr.employee` без `AccessError`; `search`/`name_search` за кодом; `_fields['f3d_code'].readonly`; `'_f3d_code_uniq'` відсутнє серед обмежень `hr.employee.public` |
| `test_zone.py::TestZoneData` | `test_45_zones_loaded`, `test_types_distribution`, `test_polygons_inside_site`, `test_indoor_inside_building`, `test_roof_flag` | AC-15 | data | кількості; усі зони в межах `[−32,182]×[−30,100]`; 34 цехових у межах `[0,150]×[0,72]`; `is_roof` лише `Z-ROOF`; `is_roof` на зоні типу `storage` → `ValidationError` |
| `::TestGeometry` | `test_area_bbox`, `test_polygon_validation`, `test_polygon_text_inverse`, `test_zone_at` | AC-16, AC-17 | `make_zone` | `area_m2 == 63.8` (assertAlmostEqual, 1 знак); `ValidationError` 4 випадки; `zone_at` 4 точки |
| `::TestCounters` | `test_counts_and_docks`, `test_archived_not_counted` | AC-18 | зона + 2 локації (`make_dock` одна) + РЦ + обладнання | лічильники; `dock_location_ids` |
| `test_dock.py::TestDockConstraints` | `test_requires_side_no`, `test_unique_side_no`, `test_kind_mismatch`, `test_kind_zone_forbidden`, `test_coords_bounds` | AC-20, AC-23 | `make_dock` | `ValidationError` тексти починаються з очікуваних фраз |
| `::TestRegister` | `test_register_west_east`, `test_register_idempotent`, `test_hook_docks_on_synthetic` | AC-11, AC-21 | локації з barcode `UNLOAD-1`, `DOCK-E1`; `scene_docks.csv` | `dock_ids`, `dispatch_management`; після `docks.register(env)`: `f3d_code='DOCK-W1'`, `f3d_alias='UNLOAD-1'`, `barcode` незмінний |
| `test_batch.py::TestDockWarning` | `test_warning_text`, `test_child_category_ok`, `test_no_categories` | AC-22 | ворота з категоріями, `make_picking` з товарами категорій, `make_batch` | рівність рядка попередження; `False` |
| `::TestPickingRelated` | `test_related_fields`, `test_search_read` | AC-51 | пакет із `dock_id`, кодами, технікою | значення; `search_read` через `env['stock.picking'].search_read(...)` |
| `test_migration.py::TestCodesHooks` | `test_locations`, `test_workcenters`, `test_equipment_resolution` | AC-10, AC-12, AC-14 | локації `A-1`/`b-1`/`WHSTOCK`; РЦ; обладнання 4 шт. + `ir.model.data` `factory3d.eq_fl_1` | коди; `unmatched` |
| `::TestLocationKinds` | `test_kind_capacity_from_table`, `test_kind_via_alias`, `test_rerun`, `test_capacity_nonneg`, `test_kind_selection` | AC-53 | локації `PLT-T1`, `FUR-T1`, ворота з псевдонімом `UNLOAD-T1`; `with_data_file('scene_locations.csv', …)` | `f3d_loc_kind`/`f3d_capacity`; `IntegrityError` у `mute_logger`; `ValueError` при невідомому значенні селекції |
| `::TestBatchMigration` | `test_full_cycle_synthetic`, `test_done_pickings_attached`, `test_moves_untouched`, `test_rerun_idempotent`, `test_keep_x_fields`, `test_mismatch_blocks_drop` | AC-25…AC-30 (синтетично) | тест сам створює manual-поля `x_dock/x_truck/x_vehicle` через `ir.model.fields`, 4 документи (2 `done` із `x_dock`, 1 `assigned` із `x_truck`+`x_dock`, 1 internal `done` із `x_vehicle`), ворота `DOCK-T1`, обладнання `FL-T`, демо-представлення `factory3d.view_picking_form_dock` (створене тестом із `x_dock` в arch) | після `batches.migrate`: 3 пакети (1 з `f3d_code`), `batch_id` на 4 документах, стани `done`/`in_progress`; `snapshot_moves` рівний; після `verify`: `mismatches == []`; після `drop_demo`: поля й представлення відсутні; повтор: `batches_created == 0`; з `keep_x_fields` поля лишаються; якщо підмінити `x_dock` на неіснуючий код → `mismatches` ≠ [] і поля не видалені |
| `::TestUninstall` | `test_restore_x_fields` | AC-48 | те саме + `uninstall_hook(env)` | `ir.model.fields` 3 шт. створено, значення `x_dock`/`x_truck`/`x_vehicle` відновлені (через `cr.execute SELECT`), параметри відсутні |
| `test_passport.py::TestPassportData` | `test_93_passports`, `test_beam_saw_fields`, `test_spec_counts`, `test_sources`, `test_extra_numeric_keys` | AC-32, AC-33 | data | кількості 93/999/252; значення `beam_saw`; `highbay lumen` |
| `::TestPassportApi` | `test_get_num`, `test_equipment_related`, `test_unit_count`, `test_role_unique`, `test_spec_key_unique`, `test_source_url_check` | AC-36, AC-37 (синтетично) | обладнання з `f3d_passport_id=passport_beam_saw` | значення; `IntegrityError`; `ValidationError` |
| `::TestPassportLink` | `test_link_from_table_synthetic` | AC-34, AC-35 (синтетично) | обладнання `EDGE-1`, `SWB-1`, `CHARGING` з кодами | після `passports.link(env)`: паспорт і складові; `CHARGING` без паспорта |
| `test_security.py::TestGroups` | `test_groups_chain`, `test_menus`, `test_access_reader_manager`, `test_code_write_rights`, `test_zone_company_rule`, `test_run_migration_rights` | AC-41…AC-45, AC-50 | користувачі з `common.py` | `implied_ids`; `AccessError` через `with_user()`; меню `env.ref(...)` з `sequence` |
| `test_hooks.py::TestParams` | `test_params_defaults`, `test_clean_db_skipped`, `test_neutralize_sql`, `test_report_json` | AC-46, AC-47, AC-49 | — | значення; `json.loads(migration_report)` без помилки; `cr.execute(sql)` |
| `test_data_sync.py` (pytest, поза Odoo) | `test_csv_matches_macro` | — | `tools/gen_data.py` у тимчасову теку | згенеровані файли побайтово дорівнюють `data/*` у репозиторії (захист від розходження з макетом) |

### 13.2 Сценарії на копії демо-бази ТК-01…ТК-06

Передумови: копія бази `odoo` тестового сервера (`createdb -T` або дамп/відновлення), модуль у
`addons_path`, знімки перед установкою (SQL, зберегти у файл):
`S1 = SELECT id,name,x_dock,x_truck,x_vehicle,batch_id FROM stock_picking ORDER BY id`;
`S2 = SELECT id,location_id,location_dest_id,state FROM stock_move ORDER BY id`;
`S3 = SELECT id,serial_no,md5(coalesce(note,'')) FROM maintenance_equipment ORDER BY id`;
`S4 = SELECT count(*) FROM stock_quant WHERE quantity<>0`; `S5 = SELECT id,barcode,complete_name FROM stock_location ORDER BY id`.

| ТК | Кроки | Очікуваний результат | Де дивитися |
|---|---|---|---|
| ТК-01 Установка | `odoo-bin -d <copy> -i factory3d_base --stop-after-init`; лог рівня INFO | без ERROR/WARNING (крім відомих Odoo); у лозі рядки кроків 1–11 із кількостями §5.3; `migration_state='done'` | лог; Налаштування → Технічні → Параметри системи → `factory3d.base.*` |
| ТК-02 Коди й зони | SQL/UI: `SELECT f3d_kind,count(*) FROM stock_location WHERE f3d_code IS NOT NULL GROUP BY 1` → `location 682`, `dock 14`; `mrp_workcenter` 35; `hr_employee` 35; `maintenance_equipment` 208 (серійники навантажувачів `FL-4369`… мають код `FL-1`…); `f3d_zone` 45 (11 `outdoor`, kanban показує їх окремою групою); `SELECT f3d_loc_kind,count(*) FROM stock_location WHERE f3d_loc_kind IS NOT NULL GROUP BY 1` → `pallet_cell 360, bin 144, stack 123, shelf 24, kit 20, area 18`; `f3d_capacity > 0` → 654 (AC-54); `f3d_zone` 34; лічильники зон за AC-19 | кількості точні; Завод 3D → Завод → Зони: kanban 34 карток із площами; `Z-SHEETS` → 123 місця, 0 РЦ; `Z-CUT` → 6 РЦ | меню «Завод 3D», форми зон |
| ТК-03 Пакети й поля x_* | порівняти `S1` з новим станом: кожен рядок із `x_dock` → `batch_id` непорожній і `batch.dock_id.f3d_code == x_dock`; `S2` == поточний знімок рухів; `S4` незмінний; `stock_picking_batch` 24 рядки; `ir_model_fields` без `x_dock/x_truck/x_vehicle` для `stock.picking`; `ir_ui_view` без `view_picking_form_dock` | 0 розбіжностей; пакети `BATCH/IN/00001…3`, `BATCH/OUT/00004…6` з `f3d_code`; 15 нових пакетів із доком, 3 з технікою; стани `done` для 6 пакетів | Склад → Операції → Пакетні переміщення (список із колонками «Фура», «Техніка»); форма `WH/IN/00128`: «Ворота WH/Вхід/Ворота 1», «Фура TRUCK-IN-1» |
| ТК-04 Інтерфейс | (1) Обслуговування → Обладнання → `SAW-1` → вкладка «Паспорт»: HOMAG, SAWTEQ S-310…, 14 параметрів, 4 джерела, «Одиниць під паспортом» 2; «Показати в 3D» → жовте повідомлення (viewer не встановлений). (2) Склад → Конфігурація → Місця зберігання → `WH/Вхід/Ворота 4` → «Завод 3D»: Ворота, Захід, № 4, «Фурнітура», X 0, Y 35; «Типи операцій» = Receipts. (3) Новий пакет типу Receipts: поле «Док» пропонує 7 західних воріт; вибрати `Ворота 1`, додати документ із крайкою → попередження «Ворота DOCK-W1 приймають: Плитні матеріали…». (4) Працівники → Олег Мельник (OPSAW1) → «Завод 3D»: `OP-SAW-1`. (5) Комірник (користувач лише `stock.group_stock_user`) бачить меню «Завод 3D», вкладки, але поле «Код сцени» readonly | усе як описано, без traceback | UI |
| ТК-05 Повтор і деінсталяція | (1) Завод 3D → Налаштування → «Повторити міграцію демо-даних» (адміністратор) → звіт `batches_created: 0`, кількості незмінні. (2) Деінсталювати модуль → `SELECT x_dock,x_truck,x_vehicle FROM stock_picking` дорівнює `S1`; `stock_picking_batch` 24 (лишаються); `f3d_zone`, `f3d_equipment_passport` таблиць немає; `S3`, `S5` незмінні. (3) Повторна установка → ТК-01…ТК-03 знову зелені (пакети вже є → `batches_created: 0`, звірка 0) | як описано | SQL, Застосунки |
| ТК-06 Переглядач-макет (після правки `plant/odoo_pull.py` за §11.4, Q-09) | `python3 -m plant.odoo_pull dist/odoo_demo_live.json` проти копії → `cycle_check` зелений; `pickings[*].dock/truck/vehicle` збігаються з `dist/odoo_demo.json` | 0 помилок `cycle_check` | термінал |

### 13.3 Тести безпеки

- Без групи: користувач `base.group_user` без `f3d_user` → `f3d.zone.search` → `AccessError`
  (`test_security.py::test_no_group_denied`).
- Запис кодів без `f3d_manager` → `AccessError` (AC-43), включно з `create` локації з `f3d_code`.
- `f3d_run_migration` без `f3d_admin` → `AccessError` (AC-50); пункт меню невидимий (група на меню).
- Ін'єкції: `f3d_code` з `'; DROP TABLE --` → `ValidationError` R-01 (`test_code_injection_rejected`);
  `read_manual_field(env, 'stock.picking', 'x_dock; DROP')` → `ValueError` до будь-якого SQL
  (`test_manual_field_name_validated`); `polygon_text` з `{"__class__":…}` → `ValidationError`.
- Публічний профіль працівника: користувач без `hr.group_hr_user` читає лише поля M-10a, а не `barcode` (стандартне
  приватне поле) — `with_user(u).read(['barcode'])` → `AccessError` (`test_employee.py::TestEmployeePublic`, AC-55).
- Record rule компанії (AC-45).
- Токенів/стоп-кранів у base немає — `neutralize.sql` перевіряється AC-49.

### 13.4 Тести продуктивності

- `test_perf_resolve`: 1 000 викликів `f3d_resolve` на базі з 700 локаціями — ≤ 3 с сумарно
  (індекс на `f3d_code`); `EXPLAIN` показує Index Scan (`test_index_exists`: `pg_indexes` містить
  `stock_location_f3d_code_index`).
- `test_perf_zone_at`: 10 000 точок випадково по плану — ≤ 5 с.
- ТК-01: хук на копії демо — ≤ 60 с (вимірюється за логом).
- Лічильники зон: відкриття списку 34 зон — ≤ 1 с (ручна перевірка в ТК-02).

### 13.5 Чек-лист DEPLOY_TEST (файл `docs/modules/factory3d_base/DEPLOY_TEST.md`, здає W5)

1. Зняти дамп бази `odoo` тестового сервера; відновити як `odoo_f3d_test`; зберегти знімки S1–S5.
2. Установити модуль (ТК-01); перевірити `migration_state`, звіт, лог.
3. ТК-02, ТК-03, ТК-04.
4. Прогнати юніт-тести на `odoo_f3d_test`: `--test-tags /factory3d_base` → 0 падінь.
5. ТК-05 (повтор, деінсталяція, повторна установка).
6. Відкат: видалити `odoo_f3d_test`; робоча база `odoo` не змінювалася (установка на неї — лише
   після погодження і правки `odoo_pull`, Q-09; перед цим `keep_x_fields=True`).
7. Записати фактичні кількості у CHANGELOG (розділ «Міграція демо 13.10.2026»).

## 14. Definition of Done

- Усі юніт-тести §13.1 зелені на чистій базі й на копії демо (`--test-tags /factory3d_base`);
  `test_data_sync.py` зелений.
- ТК-01…ТК-05 пройдені, протокол у `DEPLOY_TEST.md` з фактичними кількостями.
- Кожен AC-01…AC-55 має зелений тест або відмітку ТК/MAN у протоколі.
- `ruff`/`flake8` без помилок (конфіг проєкту; якщо немає — `ruff check` з умовчаннями, довжина рядка 120).
- Жодного `x_`-поля в коді модуля (крім рядкових імен у `hooks/batches.py`, `hooks/x_fields.py`,
  `hooks/__init__.py` для міграції) — `grep -rn "x_dock\|x_truck\|x_vehicle" models/ views/ data/` порожній.
- `neutralize.sql` виконується без помилки; AC-49.
- `README.md` модуля (установка, параметри, 4 інструкції ARCH §4), `CHANGELOG.md` (`19.0.1.0.0`).
- Перегляд безпеки: §13.3 пройдено; SQL лише параметризований; імена manual-полів валідуються.
- Контракти CB-01…CB-12 реалізовані з точними іменами з цього документа; зміни імен — лише через
  оновлення SPEC і повідомлення авторів viewer/telemetry/yard.

## 15. Відкриті питання

Ті самі Q-01…Q-10, що в ARCH §5.1 (нумерація спільна); тут — що робить код, поки відповіді немає:

| ID | Поки немає відповіді |
|---|---|
| Q-01 | A-01: одна локація, псевдонім `UNLOAD-k` |
| Q-02 | один пакет на документ (R-11) |
| Q-03 | закрито менеджером 13.10: `f3d_loc_kind`/`f3d_capacity` імпортуються (FR-13, R-21, A-16) |
| Q-04 | `attachment_id` порожнє; PDF не завантажуються |
| Q-05 | A-06: 26 одиниць прив'язано за README (додаток F) |
| Q-06 | вирішено менеджером 13.10: 11 надвірних зон у base (додаток C.2, A-19, `is_roof` для `Z-ROOF`) |
| Q-07 | `OUT-STAGE` без зони |
| Q-08 | рядки українською в коді |
| Q-09 | `plant/odoo_pull.py` не правимо в цьому модулі; до правки — `keep_x_fields=True` на живій базі |
| Q-10 | `f3d_code` фури на пакеті необов'язковий |

## Додаток A. Таксономія кодів сцени (з `dist/odoo_demo.json`, 13.10.2026)

| Модель | Префікс / шаблон | Кількість | Приклади | Джерело в базі |
|---|---|---|---|---|
| `stock.location` | `FG-R<1-5>-B<01-18>-L<1-4>` (комірка ГП) | 360 | `FG-R1-B01-L1`, `FG-R5-B18-L4` | `barcode` |
| | `FUR-R<1-6>-S<01-06>-L<1-4>` (комірка фурнітури) | 144 | `FUR-R1-S01-L1` | `barcode` |
| | `RCK-R<1-8>-<1-3><A-D>` (стос у стелажі плит) | 96 | `RCK-R1-1A`, `RCK-R8-3D` | `barcode` |
| | `PLT-<01-09><A-C>` (стос під порталом) | 27 | `PLT-01A`, `PLT-09C` | `barcode` |
| | `EB-U<1-2>-S<1-4>-L<1-3>` (полиця крайки) | 24 | `EB-U1-S1-L1` | `barcode` |
| | `KIT-<01-12>` (візок комплекту) | 12 | `KIT-01` | `barcode` |
| | `FRONTS-<1-8>` (етажерка фасадів) | 8 | `FRONTS-1` | `barcode` |
| | `UNLOAD-<1-7>` (майданчик вивантаження; після міграції — `f3d_alias` воріт `DOCK-W<k>`) | 7 | `UNLOAD-1` | `barcode` |
| | `QC-PLT-<1-3>`, `QC-1` (контроль, карантин) | 4 | `QC-PLT-1`, `QC-1` | `barcode` |
| | `PAL-<1-3>`, `PACK-STORE`, `PAINT-STORE`, `POST-STAGE`, `OUT-STAGE` | 7 | | `barcode` |
| | `DOCK-W<1-7>` (ворота приймання, `f3d_kind=dock`) | 7 | `DOCK-W1` | `scene_docks.csv` (локація за `barcode=UNLOAD-k`) |
| | `DOCK-E<1-7>` (ворота відвантаження) | 7 | `DOCK-E1` | `barcode` |
| `mrp.workcenter` | `SAW-<1-3>`, `SLIDE-1`, `VSAW-1`, `NEST-1`, `EDGE-<1-3>`, `CNC-<1-4>`, `BORE-1`, `DOWEL-1`, `SORT-1`, `SAND-1`, `AUTOSPRAY-1`, `UV-1`, `HINGE-1`, `GLUE-1`, `PRESS-1`, `SPRAY-1`, `DRY-1`, `ASMLINE-1`, `ASM-<1-6>`, `PACK-<1-2>`, `BOX-1`, `PACKLINE-1` | 35 | | `code` |
| `maintenance.equipment` | 35 кодів РЦ (та сама назва) | 35 | `SAW-1` | `serial_no` |
| | `FL-<1-5>`, `FL-C<1-2>`, `FL-6`, `TUGGER-1`, `GANTRY-1`, `BOARD-RACKS`, `COMPRESSOR`, `DUST-1`, `BOILER`, `CHARGING`, `SPRINKLERS`, `AIR-RING` | 19 | | `serial_no` (крім 7 навантажувачів — R-07) |
| | енергетика: `RM6-1`, `T1`, `T2`, `SWB-1`, `Q1`, `Q2`, `QS`, `QF-<1-4>`, `QF-C<1-2>`, `PFC-<1-2>`, `EMS-1`, `BW-<1-4>`, `GENSET`, `ATS-1`, `BESS`, `PV-ROOF`, `PV-INV`, `CHP` | 26 | | `serial_no` |
| | освітлення: `LT-<зона>` (32: `LT-RCV-<1-7>`, `LT-SHEETS`, `LT-HW`, `LT-EDGE`, `LT-PKS`, `LT-CUT`, `LT-EB`, `LT-CNC`, `LT-SORT`, `LT-FAC`, `LT-ASM`, `LT-PRE`, `LT-MAINT`, `LT-PACK`, `LT-POST`, `LT-CMP`, `LT-CHG`, `LT-FG`, `LT-ELEC`, `LT-OUT-<1-7>`), `LP-<1-3>`, `EMERGENCY` | 36 | | `serial_no` |
| | вентиляція: `RV-<01-25>`, `AHU-1`, `EF-ELEC`, `EF-CMP`, `EF-CHG` | 29 | | `serial_no` |
| | пожежна: `FACP-1`, `FA-MCP`, `FA-SND`, `FA-FLAME`, `SPARK-1`, `FA-<зона>` (32), `FA-BOILER`, `SMOKE-VENTS`, `SMOKE-CTRL`, `EXITS` | 41 | | `serial_no` |
| | інше: `LPS`, `WATER`, `ODOO-TABLETS`, `ODOO-SCANNERS`, `WIFI`, `SERVER`, `TURNSTILES`, `ACCESS`, `CCTV`, `TRUCK-SCALE`, `GATE-W`, `GATE-E`, `PRN-RCV`, `PRN-PACK1`, `PRN-PACK2`, `PRN-OUT`, `SCALE-OUT1`, `SCALE-OUT2`, `SCALE-RCV`, `IOT-RCV`, `IOT-PACK`, `IOT-OUT`, `EYE-CHG`, `EYE-PAINT` | 22 | | `serial_no` |
| `hr.employee` | `OP-<код РЦ>` (28), `OP-W<1-7>` (7) | 35 | `OP-SAW-1`, `OP-W1` | `barcode` без дефісів |
| `f3d.zone` | цех: `Z-RCV-<1-7>`, `Z-OUT-<1-7>`, `Z-<назва>` (20); територія: `Z-GATE-W`, `Z-GATE-E`, `Z-YARD-W`, `Z-YARD-E`, `Z-KPP`, `Z-PARKING`, `Z-BOILER`, `Z-FIREWATER`, `Z-ENERGY`, `Z-WASTE`, `Z-ROOF` | 45 | `Z-SHEETS`, `Z-ENERGY` | data-файл |
| `stock.picking.batch` | `TRUCK-IN-<1-3>`, `TRUCK-OUT-<1-3>` | 6 | `TRUCK-IN-1` | `x_truck` |

Разом обладнання: 35 + 19 + 26 + 36 + 29 + 41 + 22 = 208.

Види місць (`locations[*].kind`, FR-13) і місткість (`capacity`):

| `f3d_loc_kind` | Коди | Кількість | `f3d_capacity` | Одиниця |
|---|---|---|---|---|
| `stack` | `PLT-*` (27), `RCK-*` (96) | 123 | 60 / 55 | аркуші |
| `bin` | `FUR-*` | 144 | 6, 10, 13, 20, 25, 33, 50, 66, 83, 133, 333, 500, 666, 833, 1333, 1666 | шт |
| `shelf` | `EB-*` | 24 | 2200 | м |
| `pallet_cell` | `FG-*` | 360 | 2 | палети (упаковки `PACK…`) |
| `kit` | `KIT-*` (12), `FRONTS-*` (8) | 20 | — (0) | — |
| `area` | `UNLOAD-*` (7, через псевдонім воріт), `QC-PLT-*` (3), `QC-1`, `PAL-*` (3), `PACK-STORE`, `PAINT-STORE`, `POST-STAGE`, `OUT-STAGE` | 18 | лише `PAL-*` = 14 | палети |

## Додаток B. Коди працівників (`data/scene_employee_codes.csv`, 35 рядків)

| barcode | f3d_code | Ім'я (демо) | Посада | РЦ |
|---|---|---|---|---|
| OPSAW1 | OP-SAW-1 | Олег Мельник | Оператор | SAW-1 |
| OPSAW2 | OP-SAW-2 | Ірина Коваль | Оператор | SAW-2 |
| OPSLIDE1 | OP-SLIDE-1 | Андрій Бондар | Оператор | SLIDE-1 |
| OPNEST1 | OP-NEST-1 | Наталія Ткачук | Оператор | NEST-1 |
| OPEDGE1 | OP-EDGE-1 | Сергій Кравець | Оператор | EDGE-1 |
| OPEDGE2 | OP-EDGE-2 | Оксана Шевчук | Оператор | EDGE-2 |
| OPCNC3 | OP-CNC-3 | Віктор Поліщук | Оператор | CNC-3 |
| OPCNC1 | OP-CNC-1 | Марина Литвин | Оператор | CNC-1 |
| OPCNC2 | OP-CNC-2 | Дмитро Савчук | Налагоджувальник | CNC-2 |
| OPBORE1 | OP-BORE-1 | Юлія Марченко | Оператор | BORE-1 |
| OPCNC4 | OP-CNC-4 | Петро Онищенко | Оператор | CNC-4 |
| OPDOWEL1 | OP-DOWEL-1 | Тетяна Руденко | Оператор | DOWEL-1 |
| OPSAND1 | OP-SAND-1 | Роман Гнатюк | Оператор | SAND-1 |
| OPAUTOSPRAY1 | OP-AUTOSPRAY-1 | Галина Мороз | Оператор | AUTOSPRAY-1 |
| OPHINGE1 | OP-HINGE-1 | Василь Лисенко | Оператор | HINGE-1 |
| OPGLUE1 | OP-GLUE-1 | Олена Кузьменко | Оператор | GLUE-1 |
| OPPRESS1 | OP-PRESS-1 | Ігор Павленко | Оператор | PRESS-1 |
| OPSPRAY1 | OP-SPRAY-1 | Світлана Зінченко | Оператор | SPRAY-1 |
| OPASMLINE1 | OP-ASMLINE-1 | Максим Остапенко | Оператор | ASMLINE-1 |
| OPASM1 | OP-ASM-1 | Людмила Гончар | Оператор | ASM-1 |
| OPASM2 | OP-ASM-2 | Богдан Ярошенко | Оператор | ASM-2 |
| OPASM3 | OP-ASM-3 | Катерина Бойко | Оператор | ASM-3 |
| OPASM4 | OP-ASM-4 | Євген Тимошенко | Оператор | ASM-4 |
| OPASM6 | OP-ASM-6 | Алла Демченко | Оператор | ASM-6 |
| OPPACK1 | OP-PACK-1 | Степан Кушнір | Оператор | PACK-1 |
| OPPACK2 | OP-PACK-2 | Валентина Чорна | Оператор | PACK-2 |
| OPBOX1 | OP-BOX-1 | Артем Литвиненко | Оператор | BOX-1 |
| OPPACKLINE1 | OP-PACKLINE-1 | Надія Сидоренко | Оператор | PACKLINE-1 |
| OPW1 | OP-W1 | Олександр Федоренко | Комірник | — |
| OPW2 | OP-W2 | Інна Карпенко | Комірник | — |
| OPW3 | OP-W3 | Олег Мельник | Приймальник | — |
| OPW4 | OP-W4 | Ірина Коваль | Контролер ВТК | — |
| OPW5 | OP-W5 | Андрій Бондар | Оператор порталу | — |
| OPW6 | OP-W6 | Наталія Ткачук | Комірник ГП | — |
| OPW7 | OP-W7 | Сергій Кравець | Комплектувальник | — |

Імена повторюються (генератор `NAMES` циклічний) — збіг за ім'ям не використовувати, лише `barcode`.
Без коду: `Administrator` (без бейджа). РЦ без оператора в демо: `SAW-3`, `VSAW-1`, `EDGE-3`,
`SORT-1`, `UV-1`, `DRY-1`, `ASM-5` (простій або без людини).

## Додаток C. Зони (`data/f3d_zone_data.xml`, координати з `plant/layout.py`)

Контур — прямокутник `(x0, y0, x1, y1)` → `[[x0,y0],[x1,y0],[x1,y1],[x0,y1]]`; `sequence` = порядок у таблиці × 10.

| f3d_code | name | zone_type | x0 | y0 | x1 | y1 | area_m2 | color | root (хук) |
|---|---|---|---|---|---|---|---|---|---|
| Z-RCV-1 | Приймання плит · ворота 1 | receiving | 0.6 | 0.6 | 13.4 | 9.85 | 118.4 | #8fb9d6 | WH/Вхід/Ворота 1 |
| Z-RCV-2 | Приймання плит · ворота 2 | receiving | 0.6 | 10.15 | 13.4 | 19.85 | 124.2 | #a9cbe2 | WH/Вхід/Ворота 2 |
| Z-RCV-3 | Приймання плит · ворота 3 | receiving | 0.6 | 20.15 | 13.4 | 29.85 | 124.2 | #8fb9d6 | WH/Вхід/Ворота 3 |
| Z-RCV-4 | Приймання фурнітури, контроль і карантин · ворота 4 | receiving | 0.6 | 30.15 | 13.4 | 39.85 | 124.2 | #a9cbe2 | WH/Вхід/Ворота 4 |
| Z-RCV-5 | Приймання крайки · ворота 5 | receiving | 0.6 | 40.15 | 13.4 | 49.85 | 124.2 | #8fb9d6 | WH/Вхід/Ворота 5 |
| Z-RCV-6 | Приймання ЛФМ · ворота 6 | receiving | 0.6 | 50.15 | 13.4 | 59.85 | 124.2 | #a9cbe2 | WH/Вхід/Ворота 6 |
| Z-RCV-7 | Приймання пакматеріалів · ворота 7 | receiving | 0.6 | 60.15 | 13.4 | 71.4 | 144.0 | #8fb9d6 | WH/Вхід/Ворота 7 |
| Z-SHEETS | Склад плит | storage | 14.6 | 0.6 | 41.4 | 45.4 | 1200.6 | #d2c0dc | WH/Stock/Сировина/Плити |
| Z-HW | Склад фурнітури | storage | 14.6 | 46.0 | 28.4 | 71.4 | 350.5 | #b1d8bf | WH/Stock/Сировина/Фурнітура |
| Z-EDGE | Склад крайки | storage | 28.8 | 46.0 | 35.4 | 71.4 | 167.6 | #efcfae | WH/Stock/Сировина/Крайка |
| Z-PKS | Пакувальні матеріали | storage | 35.8 | 46.0 | 41.4 | 71.4 | 142.2 | #e3d3b4 | WH/Stock/Сировина/Пакування |
| Z-CUT | Розкрій | production | 41.8 | 0.6 | 55.4 | 45.4 | 609.3 | #b9d3e6 | — |
| Z-EB | Крайкооблицювання | production | 55.8 | 0.6 | 68.4 | 45.4 | 564.5 | #b9d3e6 | — |
| Z-CNC | Присадка | production | 68.8 | 0.6 | 81.4 | 45.4 | 564.5 | #b9d3e6 | — |
| Z-SORT | Сортування деталей | production | 81.8 | 0.6 | 91.6 | 45.4 | 439.0 | #c9cfe6 | — |
| Z-FAC | Дільниця фасадів МДФ | production | 42.2 | 46.4 | 91.6 | 71.4 | 1235.0 | #d9c7e8 | — |
| Z-ASM | Збирання | assembly | 92.4 | 0.6 | 109.6 | 29.6 | 498.8 | #c6dcc0 | — |
| Z-PRE | Буфер комплектів | storage | 92.4 | 30.0 | 109.6 | 45.6 | 268.3 | #eadf9f | WH/Stock/Передвиробництво |
| Z-MAINT | Ремонтна дільниця | technical | 92.4 | 46.4 | 103.6 | 57.6 | 125.4 | #d5d8dc | — |
| Z-SOC | Побутові приміщення | office | 104.0 | 46.4 | 109.6 | 57.6 | 62.7 | #d5d8dc | — |
| Z-OFFICE | Офіс | office | 92.4 | 58.0 | 109.6 | 71.4 | 230.5 | #d5d8dc | — |
| Z-PACK | Пакування | packing | 110.0 | 0.6 | 121.6 | 33.6 | 382.8 | #e3d3b4 | — |
| Z-POST | Вихід з пакування | storage | 110.0 | 34.0 | 121.6 | 59.6 | 297.0 | #eadf9f | WH/Пост-виробництво |
| Z-CMP | Компресорна | technical | 110.0 | 60.0 | 115.6 | 71.4 | 63.8 | #d5d8dc | — |
| Z-CHG | Зарядна станція | technical | 116.0 | 60.0 | 121.6 | 71.4 | 63.8 | #d5d8dc | — |
| Z-FG | Склад готової продукції | storage | 122.0 | 0.6 | 135.6 | 62.0 | 835.0 | #b4dfc1 | WH/Stock/Готова продукція |
| Z-ELEC | Електрощитова | technical | 122.4 | 62.4 | 135.6 | 71.4 | 118.8 | #e6d27a | — |
| Z-OUT-1 | Відвантаження · ворота 1 | shipping | 136.0 | 0.6 | 149.4 | 9.85 | 124.0 | #ecbdb7 | WH/Відвантаження/Ворота 1 |
| Z-OUT-2 | Відвантаження · ворота 2 | shipping | 136.0 | 10.15 | 149.4 | 19.85 | 130.0 | #f3d0cb | WH/Відвантаження/Ворота 2 |
| Z-OUT-3 | Відвантаження · ворота 3 | shipping | 136.0 | 20.15 | 149.4 | 29.85 | 130.0 | #ecbdb7 | WH/Відвантаження/Ворота 3 |
| Z-OUT-4 | Відвантаження · ворота 4 | shipping | 136.0 | 30.15 | 149.4 | 39.85 | 130.0 | #f3d0cb | WH/Відвантаження/Ворота 4 |
| Z-OUT-5 | Відвантаження · ворота 5 | shipping | 136.0 | 40.15 | 149.4 | 49.85 | 130.0 | #ecbdb7 | WH/Відвантаження/Ворота 5 |
| Z-OUT-6 | Відвантаження · ворота 6 | shipping | 136.0 | 50.15 | 149.4 | 59.85 | 130.0 | #f3d0cb | WH/Відвантаження/Ворота 6 |
| Z-OUT-7 | Відвантаження · ворота 7 | shipping | 136.0 | 60.15 | 149.4 | 71.4 | 150.8 | #ecbdb7 | WH/Відвантаження/Ворота 7 |

### C.2 Надвірні зони (`zone_type='outdoor'`, 11; контури за A-19 з `plant/infra.py`, `site.py:881–919`, `site2.py`)

| f3d_code | name | x0 | y0 | x1 | y1 | area_m2 | Об'єкти моделі, з яких виведено контур | Обладнання (f3d_zone_id) |
|---|---|---|---|---|---|---|---|---|
| Z-GATE-W | КПП приймання (в'їзд, шлагбаум) | −25.0 | −30.0 | −15.0 | 0.0 | 300.0 | `GATES[0]`: `GATE-W` x=−20 на огорожі y=−30, ширина 8 м; `CAM-05` (−20,−28.5); смуга до двору | GATE-W |
| Z-GATE-E | КПП відвантаження (виїзд, шлагбаум, автоваги) | 163.0 | −30.0 | 175.0 | 0.0 | 360.0 | `GATE-E` x=168; `TRUCK_SCALE=(172,−14)` 3×18 м + табло при x=169.4; `CAM-06` | GATE-E, TRUCK-SCALE |
| Z-YARD-W | Двір приймання (фури біля західних воріт) | −32.0 | 0.0 | 0.0 | 72.0 | 2304.0 | `SITE` x0=−32 … стіна x=0; `TRUCK-IN-1…3` при x=−7.3; `CAM-08` | — |
| Z-YARD-E | Двір відвантаження (фури біля східних воріт) | 150.0 | 0.0 | 182.0 | 72.0 | 2304.0 | стіна x=150 … `SITE` x1=182; `TRUCK-OUT-1…3` при x=157.3; `CAM-09` | — |
| Z-KPP | Прохідна персоналу (турнікети, пішохідна доріжка) | 95.0 | −30.0 | 104.0 | 0.0 | 270.0 | `KPP=(98.4,−27)`: будівля 3×4 при (101.4,−27), навіс 4×4.4, турнікети x=97.5/98.8, доріжка x=98.4 до входу `EX-IN`; `CAM-07` | TURNSTILES |
| Z-PARKING | Паркування персоналу | 106.0 | −27.0 | 150.0 | −6.0 | 924.0 | `PARKING` як є | — |
| Z-BOILER | Майданчик котельні (котельня, силос стружки, брикетувальний прес) | 59.4 | 74.0 | 80.6 | 83.6 | 203.5 | силос r=2 при (62.6,78) + стійки ±1.4; котельня 12×6 при (73.6,78), димарі; прес 2.4×1.1 при (61.6,82) + 3 палети брикетів до x=67.4 | BOILER, FA-BOILER |
| Z-FIREWATER | Пожежні резервуари й насосна | 3.5 | 74.5 | 28.0 | 83.6 | 223.0 | два резервуари r=3.5 при (8,79) і (17,79) з драбинами (x+3.55); насосна 4×3 при (25,77.5); трубопровід до стіни | — (резервуари — частина об'єкта `BOILER`, окремого коду немає) |
| Z-ENERGY | Майданчик енергетики за північною стіною (генератор, КГУ, накопичувач, ГРП, охолоджувач, інвертори СЕС) | 93.5 | 72.0 | 145.3 | 83.8 | 611.2 | `GENSET_POS=(128.5,76.2)` плита 5.4×2; `BESS_POS=(140,75.4)` плита 5.8×1.6 до x=144.3; `CHP_POS=(118.6,76.6)` 8×3.2; `CHP_EXH_POS=(117.6,78.6)`; `CHP_COOLER_POS=(118.6,81.6)` 6×2.3; `CHP_GRP_POS=(112.5,81)`; `PV_INVERTERS_X` 95…106.2 на стіні y=72.5 | GENSET, BESS, CHP, PV-INV (`ATS-1` — усередині будівлі → `Z-ELEC`) |
| Z-WASTE | Майданчик відходів | 158.0 | 78.0 | 176.0 | 92.0 | 252.0 | `WASTE` як є; `CAM-12` (167,85) | — |
| Z-ROOF | Дах і сонячна станція (`is_roof`) | 0.0 | 0.0 | 150.0 | 72.0 | 10800.0 | контур будівлі `W×D`; `PV-ROOF`, клапани димовидалення, блискавкозахист на покрівлі `ROOF_Z=9` | PV-ROOF, SMOKE-VENTS, LPS |

`color` надвірних — службовий `#d5d8dc` (як технічні зони), дах — `#c9cfe6`; `description` — з `desc`
відповідних об'єктів `site2.py:build_territory` (`TERRITORY`, `KPP`, `WASTE`, шлагбауми, ваги) і
`site.py:916–919` (`BOILER`), `site2.py:135–236` (генератор, накопичувач, КГУ, ГРП, інвертори),
`site2.py:179–182` (СЕС). `root_location_id` у надвірних зон порожній. `sequence`: 400 … 500 з кроком 10
у порядку таблиці. Поза зонами лишаються: шлагбаумна смуга між КПП і паркуванням, газопровід до межі
майданчика (y=100), естакада теплотраси — це лінійні об'єкти без площі.

`description` — з п'ятого елемента кортежу `ZONES`/`RCV_DESC` (`plant/layout.py`). Прив'язки РЦ:
`Z-CUT`: SAW-1, SAW-2, SAW-3, SLIDE-1, VSAW-1, NEST-1; `Z-EB`: EDGE-1, EDGE-2, EDGE-3, CNC-3;
`Z-CNC`: CNC-1, CNC-2, BORE-1, CNC-4, DOWEL-1; `Z-SORT`: SORT-1; `Z-FAC`: SAND-1, AUTOSPRAY-1, UV-1,
HINGE-1, GLUE-1, PRESS-1, SPRAY-1, DRY-1; `Z-ASM`: ASMLINE-1, ASM-1…ASM-6; `Z-PACK`: PACK-1, PACK-2,
BOX-1, PACKLINE-1.

## Додаток D. Ворота (`data/scene_docks.csv`)

| code | side | no | barcode (локація) | alias | x | y | accepts | zone |
|---|---|---|---|---|---|---|---|---|
| DOCK-W1 | west | 1 | UNLOAD-1 | UNLOAD-1 | 0.0 | 5.0 | Плитні матеріали | Z-RCV-1 |
| DOCK-W2 | west | 2 | UNLOAD-2 | UNLOAD-2 | 0.0 | 15.0 | Плитні матеріали | Z-RCV-2 |
| DOCK-W3 | west | 3 | UNLOAD-3 | UNLOAD-3 | 0.0 | 25.0 | Плитні матеріали | Z-RCV-3 |
| DOCK-W4 | west | 4 | UNLOAD-4 | UNLOAD-4 | 0.0 | 35.0 | Фурнітура | Z-RCV-4 |
| DOCK-W5 | west | 5 | UNLOAD-5 | UNLOAD-5 | 0.0 | 45.0 | Крайка | Z-RCV-5 |
| DOCK-W6 | west | 6 | UNLOAD-6 | UNLOAD-6 | 0.0 | 55.0 | ЛФМ | Z-RCV-6 |
| DOCK-W7 | west | 7 | UNLOAD-7 | UNLOAD-7 | 0.0 | 65.0 | Пакування | Z-RCV-7 |
| DOCK-E1…E7 | east | 1…7 | DOCK-E1…E7 | — | 150.0 | 5…65 | — | Z-OUT-1…7 |

`width=3.4`, `height=4.5` для всіх (`plant/layout.py:DOORS`, `DOOR_H`). Категорії — назви
`product.category` демо (`Плитні матеріали` 7 товарів, `Фурнітура` 24, `Крайка` 6, `ЛФМ` 6
(включно з плівкою `PVC-WG`), `Пакування` 4); відповідність воротам — з ліній документів приймання
`odoo_demo.json` (`DOCK-W1…3` → лише плити, …) і `RCV_GOODS`.

## Додаток E. Паспорти: роль → виробник, модель → коди одиниць → складові (`scene_equipment_codes.csv`)

| role | manufacturer | model (скорочено) | одиниці (f3d_code) | складові (components) |
|---|---|---|---|---|
| beam_saw | HOMAG | SAWTEQ S-310 (S-310/43/22) | SAW-1, SAW-2 | — |
| beam_saw_book | HOMAG | SAWTEQ S-510 (S-510/43/22) | SAW-3 | — |
| sliding_table_saw | Altendorf | F 45 | SLIDE-1 | — |
| vertical_panel_saw | Striebig | EVOLUTION 4224 | VSAW-1 | — |
| nesting_cnc | HOMAG | CENTATEQ N-510 /32/22 | NEST-1 | — |
| board_storage | HOMAG | STORETEQ P-500, ST71 X | GANTRY-1 | — |
| edgebander_laser | HOMAG | EDGETEQ S-500 airTec | EDGE-1 | robot_return |
| edgebander | HOMAG | EDGETEQ S-380 1660 HF | EDGE-2, EDGE-3 | — |
| ptp_cnc | HOMAG | CENTATEQ P-110 /31 | CNC-1, CNC-2, CNC-3, CNC-4 | — |
| throughfeed_drilling | HOMAG | DRILLTEQ H-600 | BORE-1 | — |
| dowel_inserting | HOMAG | DRILLTEQ D-510 | DOWEL-1 | — |
| hinge_insertion | Blum | MINIPRESS P | HINGE-1 | — |
| sorting_cell | HOMAG | SORTBOT R-300 | SORT-1 | — |
| wide_belt_sander | SCM (DMC) | dmc sd 60 135 | SAND-1 | — |
| membrane_press | Orma | AIR SYSTEM ECO 30/14 | PRESS-1 | — |
| glue_spray_booth | Ardesia | AMBER 3 | GLUE-1 | — |
| manual_spray_booth | Ardesia | DOUBLE 4 | SPRAY-1 | paint_pump |
| automatic_spraying | Cefla Finishing | EASY 2000 DUO D | AUTOSPRAY-1 | — |
| drying | Cefla Finishing | вертикальна двозонна сушка | DRY-1 | — |
| uv_line | Cefla Finishing (Sorbini) | Smartcoater MF-EVO + UV-R/3 | UV-1 | uv_oven |
| case_clamp_auto | HOMAG | CABTEQ T-200 | ASMLINE-1 | — |
| case_clamp_manual | HOMAG | CABTEQ S-250 | ASM-1…ASM-6 | — |
| box_machine | Panotec | Nextmode 2.5 | BOX-1 | — |
| stretch_wrapper | Robopac | Rotoplat 508 PDS | PACK-1, PACK-2 | — |
| shrink_line | Smipack | FP8000CS + T652 | PACKLINE-1 | strapping |
| compressor | Atlas Copco | GA 37 VSD+ FF ×2 + LV911 | COMPRESSOR | — |
| dust_extraction | NESTRO Lufttechnik | NKJ 32 000 м³/год | DUST-1 | — |
| biomass_boiler | Kalvis | K-500M | BOILER | briquetting_press |
| forklift | Jungheinrich | EFG 216 | FL-1, FL-3, FL-4, FL-5, FL-C1, FL-C2 | — |
| board_forklift | Linde Material Handling | X50/600 | FL-2, FL-6 | — |
| tugger | Jungheinrich | EZS 350 | TUGGER-1 | — |
| board_rack | SSI Schäfer | PR 600 | BOARD-RACKS | — |
| substation | Schneider Electric | RM6 NE-QIQI 24 кВ | RM6-1 | — |
| transformer | Schneider Electric | Trihal 1000 кВА | T1, T2 | busbar_main |
| main_switchboard | Schneider Electric | PrismaSeT P | SWB-1, QF-1, QF-2, QF-3, QF-4, QF-C1, QF-C2 | SWB-1: acb; power_meter · QF-*: power_meter |
| acb | Schneider Electric | MasterPact MTZ2 16 H1 | Q1, Q2, QS | Q1, Q2: power_meter · QS: — |
| busbar_dist | Schneider Electric | Canalis KSA 630 А | BW-1, BW-2, BW-3, BW-4 | tapoff |
| power_meter | Schneider Electric | PowerLogic PM5560 | EMS-1 | — |
| pfc | Schneider Electric | VarSet 350 квар | PFC-1, PFC-2 | — |
| highbay | Signify (Philips) | CoreLine Highbay Gen5 WB | LT-* (29: усі крім LT-HW, LT-EDGE, LT-FG) | lighting_control |
| highbay_rack | Signify (Philips) | CoreLine Highbay Gen5 NB | LT-HW, LT-EDGE, LT-FG | lighting_control |
| emergency | Zemper | Spazio High Bay LUE4700LX | EMERGENCY | — |
| lighting_control | Helvar | Imagine 950 DALI-2 Router | LP-1, LP-2, LP-3 | — |
| roofvent | Hoval | RoofVent RH-9C | RV-01…RV-25 | — |
| make_up_ahu | VTS Group | VENTUS VVS180 | AHU-1 | fabric_duct |
| wall_fan | VENTS | OV 4E 500 | EF-ELEC, EF-CMP | — |
| ex_fan | Systemair | EX 140A-4 | EF-CHG | — |
| facp | Siemens | Cerberus PRO FC726-ZA | FACP-1 | — |
| multi_detector | Siemens | OOH740 | FA-CUT, FA-EB, FA-CNC, FA-SORT, FA-FAC, FA-ASM, FA-MAINT, FA-CMP, FA-CHG | — |
| smoke_detector | Siemens | OP720 | FA-SHEETS, FA-HW, FA-EDGE, FA-PKS, FA-PRE, FA-PACK, FA-POST, FA-FG, FA-ELEC, FA-RCV-1…7, FA-OUT-1…7 (23) | — |
| heat_detector | Siemens | HI720 | FA-BOILER | — |
| flame_detector | Spectrex (Emerson) | SharpEye 40/40C-I | FA-FLAME | — |
| mcp | Siemens | FDM225-RP | FA-MCP | — |
| sounder_beacon | Siemens | FDS226-RW | FA-SND | — |
| spark_detection | Fagus-GreCon | GreCon BS 7 | SPARK-1 | — |
| genset | KOHLER-SDMO | D700 | GENSET | — |
| ats | Socomec | ATyS p 1600 A | ATS-1 | — |
| bess | Huawei | LUNA2000-200KWH-2H1 | BESS | — |
| pv_module | LONGi | Hi-MO 6 LR5-72HTH-580M | PV-ROOF | pv_inverter |
| pv_inverter | Huawei | SUN2000-115KTL-M2 | PV-INV | — |
| chp | TEDOM | Quanto D800 NG | CHP | — |
| smoke_vent | LAMILUX | F100 | SMOKE-VENTS | — |
| smoke_control | D+H | CPS-M1-080-1010-B | SMOKE-CTRL | — |
| exit_door | Hörmann | STU | EXITS | panic_bar |
| lightning_air | DEHN | стрижень 103 231 + RD 8 | LPS | earthing |
| water_meter | Apator Powogaz | MWN50-G NK | WATER | eyewash; wastewater |
| eyewash | Haws | 8300-8309 | EYE-CHG, EYE-PAINT | — |
| iot_box | Odoo S.A. | IoT Box | IOT-RCV, IOT-PACK, IOT-OUT | — |
| shopfloor_tablet | Samsung | Galaxy Tab Active5 Pro | ODOO-TABLETS | — |
| handheld_scanner | Zebra | TC22 | ODOO-SCANNERS | — |
| label_printer | Zebra | ZT411 | PRN-RCV, PRN-PACK1, PRN-PACK2, PRN-OUT | — |
| scale | METTLER TOLEDO | PFA584 | SCALE-OUT1, SCALE-OUT2, SCALE-RCV | — |
| wifi_ap | Cisco | CW9166D1 | WIFI | — |
| server_rack | APC | NetShelter SX AR3100B2 + SRT10K | SERVER | network_switch; nvr |
| turnstile | Gunnebo | SlimStile EV | TURNSTILES | access_reader |
| access_reader | Suprema | BioEntry W3 | ACCESS | — |
| cctv_camera | Axis | P1488-LE | CCTV | nvr |
| truck_scale | Аксіс | 60-18-К-Е | TRUCK-SCALE | — |
| barrier | CAME | GARD LS6 | GATE-W, GATE-E | — |
| robot_return, uv_oven, paint_pump, strapping, briquetting_press, busbar_main, tapoff, fabric_duct, network_switch, nvr, panic_bar, earthing, wastewater, fire_hydrant_cabinet | (14 ролей лише як складові / довідник) | | — | — |

Разом одиниць із паспортом: 205; зв'язків «у складі»: 63 (61 одиниця). Без паспорта: `CHARGING`
(Зарядна станція), `SPRINKLERS` (Спринклерна система), `AIR-RING` (Пневмомагістраль).

## Додаток F. Зони обладнання за README (A-06, 26 одиниць) і навантажувачі (R-07)

| f3d_code | zone | Підстава (README) |
|---|---|---|
| RM6-1, T1, T2, SWB-1, Q1, Q2, QS, QF-1, QF-2, QF-3, QF-4, QF-C1, QF-C2, PFC-1, PFC-2, EMS-1 | Z-ELEC | «Електрощитова — у куті складу ГП біля північної стіни (зона Z-ELEC)»; «комірки 10 кВ, 2 сухі трансформатори, ГРЩ з 11 шаф» |
| COMPRESSOR | Z-CMP | «Компресорна й зарядна біля складу ГП»; зона «Компресорна» |
| CHARGING, EYE-CHG | Z-CHG | зона «Зарядна станція»; «аварійних душів Haws (зарядна й фарбування)» |
| GANTRY-1, BOARD-RACKS | Z-SHEETS | «портал із вакуумним захопленням», «8 ліній стелажів» у складі плит |
| FACP-1 | Z-OFFICE | «Прилад FC726-ZA … біля входу в офіс (пост охорони)» |
| EYE-PAINT | Z-FAC | «аварійних душів Haws (… фарбування)» |
| PRN-PACK1, PRN-PACK2, IOT-PACK | Z-PACK | «етикетка SSCC на пакуванні», принтери пакування 1/2 |

Надвірні зони за моделлю території (A-19, 13 одиниць): GATE-W → Z-GATE-W; GATE-E, TRUCK-SCALE → Z-GATE-E;
TURNSTILES → Z-KPP; GENSET, BESS, CHP, PV-INV → Z-ENERGY; BOILER → Z-BOILER (разом із FA-BOILER з
`fire.groups`, зона якого в макеті вже `Z-BOILER`); PV-ROOF, SMOKE-VENTS, LPS → Z-ROOF; ATS-1 → Z-ELEC
(`ATS_POS=(135.1, 68.5)` — усередині електрощитової). Силос, брикетувальний прес, резервуари, насосна,
КПП, шлагбаумні тумби, камери `CAM-*` окремих одиниць обладнання в базі не мають (частина об'єктів
`BOILER`, `KPP`, `CCTV`).

Без зони (розподілені по всьому заводу або без координат у моделі): DUST-1 (фільтр — об'єкт у шарі
аспірації всередині цеху), WATER, SMOKE-CTRL, EXITS, LP-1…3, EMERGENCY, FA-MCP, FA-SND, FA-FLAME,
SPARK-1, SERVER, WIFI, ACCESS, CCTV, ODOO-TABLETS, ODOO-SCANNERS, PRN-RCV, PRN-OUT, SCALE-*, IOT-RCV,
IOT-OUT, AIR-RING, SPRINKLERS, FL-*, TUGGER-1 (Q-05).

Навантажувачі в базі (`serial_no` ≠ код): FL-4369 → FL-1 «Навантажувач ГП 1»; FL-4912 → FL-2
«Навантажувач приймання» (Linde X50); FL-4731 → FL-3 «Навантажувач відвантаження»; FL-4374 → FL-4
«Навантажувач ГП 2»; FL-4193 → FL-5 «Навантажувач пакування»; FL-4606 → FL-C1 «Навантажувач (резерв)»;
FL-4787 → FL-C2 «Навантажувач (резерв)». `FL-6` має `serial_no='FL-6'`.
