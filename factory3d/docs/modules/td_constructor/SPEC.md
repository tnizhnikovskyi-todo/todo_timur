# td_constructor — специфікація

Версія 0.2 · 19.10.2026 (v0.1 — 17.10.2026; зміни — «Журнал змін документа» в кінці) · технічне рішення: `docs/modules/td_constructor/ARCHITECTURE.md` (далі ARCH; рішення DEC-xx, питання Q-xx — там).
Вхідні документи: `build/constructor/DECISIONS.md` (рішення замовника CD-01…CD-24, 17.10.2026) і `build/constructor/PROTOTYPE.md`
(прототип-артефакт: його модель даних — чернетка моделей нижче, імена полів збережено).
Спирається на контракти каркаса: C-6.1 (код сцени), CB-01/CB-03/CB-05/CB-07 (`td_factory3d`: домішка, `td.zone.zone_at`, `stock.location`
вид і місткість, паспорт `td.equipment.passport`), CB-09 (меню), CB-10 (групи), CB-12 (габарит будівлі), конвенції §5. Нових протоколів P-xx немає.
Контракти, які модуль визначає сам: CC-01 (`td_site_id`), CC-02 (геометрія розкладки для переглядача, фаза 2) — ARCH §2.1.

**Злиття з «Конструктором складу» (CD-27, CD-29…CD-31).** v0.2 додає те, що зроблено в хвилях 0–2 слияння (модуль `19.0.1.4.0`, ядро `factory3d/core/constructor`):
моделі M-16…M-31, правила R-25…R-41, API-11…API-24 і додаткові маршрути (§7.1), представлення V-14…V-18, критерії AC-70…AC-137 (§12.1), тести (§13.6). Існуючі ID не
змінено. План слияння — `build/constructor/MERGE.md` (російською; F01…F19 — функції «Конструктора складу», N-xx — знайдене понад список), рішення замовника — `DECISIONS.md`
(CD-31: відповіді Q1…Q12; у цьому документі вони позначаються «CD-31 Q3» — на відміну від Q-xx ARCH/SPEC). Джерело істини — код і тести; розбіжності з MERGE.md описано в тексті.

Усі імена остаточні. Рядки інтерфейсу Odoo — українською в коді (`string="…"`); з v0.2 є `i18n/uk.po`, `i18n/en.po`, `i18n/td_constructor.pot` (574 терміни, CD-31 Q7: UK + EN; RU — за запитом). Odoo 19: SQL-обмеження — `models.Constraint`,
хуки — `post_init_hook(env)` / `uninstall_hook(env)`, команди — `odoo.fields.Command`, списки — `<list>`, видимість — `invisible="expr"`,
група користувача — `user.group_ids`, з імплікацією — `user.all_group_ids`, JSON-RPC — `type="jsonrpc"`.

Одиниці й система координат (DEC-15): шари, місця, розміщення — **метри**, система CB-04 (X вздовж будівлі, Y поперек, Z вгору; початок —
південно-західний кут будівлі площадки); кут повороту — **градуси проти годинникової стрілки** при погляді зверху; варіанти обладнання — **міліметри**.

## 0. Дерево файлів модуля

Позначка у квадратних дужках — воркер ARCH §6 (W1 бекенд, W2 клієнтська дія, W3 варіант: завантаження й віджет).

```
odoo_addons/td_constructor/
├── __init__.py                          [W1] from . import models, wizard, controllers, hooks; from .hooks import post_init_hook, uninstall_hook
├── __manifest__.py                      [W1] §1
├── README.md, CHANGELOG.md              [W1] 19.0.1.0.0 — перший випуск
├── hooks/
│   ├── __init__.py                      [W1] post_init_hook(env): params → seed → link (R-24); uninstall_hook(env)
│   ├── seed.py                          [W1] load_seed(env, data) — створення площадки з data/seed_site.json (§5.2)
│   └── link.py                          [W1] link_existing(env, site) — зв'язування з наявними stock.location / maintenance.equipment за кодом
├── models/
│   ├── __init__.py                      [W1]
│   ├── td_term.py                      [W1] M-11 довідник видів шарів і типів місць
│   ├── td_site.py                      [W1] M-01
│   ├── td_layer.py                     [W1] M-02
│   ├── td_slot.py                      [W1] M-03
│   ├── td_equipment_variant.py         [W1] M-04 (поля, обмеження, _f3d_set_model, _f3d_convert_model)
│   ├── td_placement.py                 [W1] M-05
│   ├── td_check_config.py              [W1] M-06
│   ├── td_layout_version.py            [W1] M-07
│   ├── td_equipment_passport.py        [W1] M-12 розширення паспорта
│   ├── stock_location.py                [W1] M-13
│   ├── maintenance_equipment.py         [W1] M-14
│   └── mrp_workcenter.py                [W1] M-15
├── services/                            [W1] чисті Python-модулі без ORM (їх тестують без бази)
│   ├── __init__.py
│   ├── geometry.py                      R-02, R-03: obb(), service_obb(), sat_penetration(), polygon_contains()
│   ├── cells.py                         R-01: SLOT_TEMPLATES, generate_cells(template, prefix, x, y, rot, params, overrides, elevation)
│   ├── checks.py                        R-04…R-10: run_checks(snapshot_dict, configs) -> list[issue]
│   ├── glb_meta.py                      R-19: glb_meta(bytes) -> dict (трикутники, bbox)
│   ├── convert.py                       R-20: CONVERTERS, available_converters()
│   ├── snapshot.py                      R-14: build_snapshot(site), apply_snapshot(site, data)
│   └── publish.py                       R-12, R-13: build_plan(site), apply_plan(site, plan, ticked, note)
├── wizard/
│   ├── __init__.py
│   ├── td_publish_wizard.py            [W1] M-08, M-09, M-10
│   └── td_publish_wizard_views.xml     [W1] V-08
├── controllers/
│   ├── __init__.py
│   ├── constructor.py                   [W1] API-01…API-08 (jsonrpc)
│   └── model.py                         [W1] API-09 (multipart), API-10 (GET GLB)
├── security/
│   ├── td_constructor_security.xml     [W1] привілей, 4 групи, record rules (§4)
│   └── ir.model.access.csv              [W1] §4.1
├── data/
│   ├── params.xml                       [W1] ir.config_parameter (noupdate=1)
│   ├── td_term_data.xml                [W1] 6 видів шарів + 6 типів місць (noupdate=0)
│   ├── td_generic_catalog.xml          [W1] 4 типові паспорти + 4 типові варіанти (noupdate=1)
│   ├── actions.xml                      [W1] ir.actions.client f3d_constructor + act_window довідників
│   └── seed_site.json                   [W1] копія вбудованого JSON прототипу (§5.2)
├── views/
│   ├── td_site_views.xml               [W1] V-01
│   ├── td_layer_views.xml              [W1] V-02
│   ├── td_slot_views.xml               [W1] V-03
│   ├── td_placement_views.xml          [W1] V-05
│   ├── td_check_config_views.xml       [W1] V-06
│   ├── td_layout_version_views.xml     [W1] V-07
│   ├── td_term_views.xml               [W1] V-09
│   ├── td_inherit_views.xml            [W1] V-10 (паспорт), V-11 (stock.location), V-12 (maintenance.equipment)
│   ├── td_equipment_variant_views.xml  [W3] V-04 (форма з віджетами f3d_model_upload / f3d_model_preview, список, канбан)
│   └── td_menus.xml                    [W1] V-13
├── static/
│   ├── description/icon.png             [W1]
│   ├── lib/dxf-parser/dxf-parser.min.js [W2] dxf-parser@1.1.2 (UMD, глобал DxfParser), LICENSE
│   ├── lib/f3d-loaders/f3d-loaders.esm.js [W3] OBJ, MTL, STL, FBX, Collada, 3MF, GLTFExporter + fflate (three r160 examples/jsm), LICENSE
│   ├── src/action/                      [W2] constructor_action.js/.xml/.scss — клієнтська дія f3d_constructor
│   ├── src/editor/                      [W0-A] core_loader.js, odoo_host.js (з CD-29 код редактора — у `factory3d/core/constructor/*`, див. нижче; раніше тут були store/geometry/cells/checks/dxf/scene/panels/dialogs/roles)
│   ├── src/model/                       [W3] formats.js, import.js, normalize.js, simplify.js, generic.js, three.js, upload.js
│   ├── src/widgets/                     [W3] model_preview.js/.xml/.scss, model_upload.js/.xml/.scss
│   └── tests/
│       ├── fixtures/cells_golden.json   [W1] еталон R-01 (Python → JS), створює W1 за годину від старту
│       ├── fixtures/checks_golden.json  [W1] еталон R-03…R-10
│       ├── editor/*.test.js             [W2] HOOT (suite @td_constructor/editor)
│       └── model/*.test.js              [W3] HOOT (suite @td_constructor/model)
├── tools/
│   ├── extract_seed.py                  [W1] витягує seed з index.html прототипу → data/seed_site.json
│   └── build_loaders.mjs                [W3] збірка f3d-loaders.esm.js (esbuild; запускається розробником, не сервером)
└── tests/
    ├── __init__.py                      [W1] імпортує всі файли нижче
    ├── common.py                        [W1] F3DConstructorCase: компанія, користувачі чотирьох ролей, площадка-фікстура
    ├── test_term_site_layer.py          [W1] AC-01, 04, 07…09, 17, 18
    ├── test_slot_cells.py               [W1] AC-11…16
    ├── test_variant.py                  [W1] AC-19…21
    ├── test_checks.py                   [W1] AC-22…32
    ├── test_variant_model_api.py        [W1] AC-33…36, 40
    ├── test_rights.py                   [W1] AC-43…47
    ├── test_api.py                      [W1] AC-48, 61, 62
    ├── test_publish.py                  [W1] AC-50…57
    ├── test_versions.py                 [W1] AC-58…60
    ├── test_seed_hook.py                [W1] AC-02, 03, 05, 06
    ├── test_hoot_editor.py              [W2] TestEditorHoot — запуск @td_constructor/editor
    └── test_hoot_model.py               [W3] TestModelHoot — запуск @td_constructor/model
```

### 0.1 Доповнення до дерева (хвилі 0–2 слияння, версія модуля 19.0.1.4.0)

Позначки: **W0-A** ядро й адаптер, **W0-B** скелет бекенду, **S1…S6** слайси (ARCH §6). Файли, що вже є в дереві вище й лише розширені, позначено `(+)`.

```
odoo_addons/td_constructor/
├── CHANGELOG.md (+)                     19.0.1.0.1 … 19.0.1.4.0 (по записах версій)
├── i18n/                                [S6] td_constructor.pot, uk.po, en.po (574 терміни; CD-31 Q7)
├── migrations/                          19.0.1.0.1 post (resync seed), 19.0.1.2.0 post (floor_spot у дозволені типи шарів), 19.0.1.3.0 pre (прив'язка довідників зони до xml-id)
├── models/
│   ├── td_slot_type.py                  [S1] M-16     td_slot_preset.py   [S1] M-17
│   ├── td_putaway_rule.py               [S2] M-18     td_replenish_rule.py [S2] M-19
│   ├── td_publish_op.py                 [S2] M-20     td_layout_variant.py [S6] M-21 (+ розширення td.layout.version: variant_id)
│   ├── td_comment.py                    [S6] M-22     td_zone_lock.py      [S6] M-23
│   ├── td_draft_mixin.py                [W0-B/S6] M-24 (аренда зони)
│   └── td_site.py, td_layer.py, td_slot.py, stock_location.py, td_layout_version.py, td_term.py, td_check_config.py (+)   M-25…M-30
├── services/                            чисті Python-модулі (ORM — лише state.py, snapshot.py, publish.py, capacity.py, putaway.py, metrics.py, odoo_sync.py)
│   ├── registry.py                      [W0-B] R-41: CHECKS, PLAN_BUILDERS, SNAPSHOT_SECTIONS, RENDERERS
│   ├── schemas.py, state.py             R-22 (схеми JSON), стан площадки для API-03/перевірок/плану
│   ├── addr.py [S1] R-25 · cells.py (+) [S1] R-26 · capacity.py [S2] R-28, R-29 · putaway.py [S2] R-30 · publish.py (+) [S2] R-31, R-32
│   ├── metrics.py [S3] R-33 · labels.py [S3] R-34 · odoo_sync.py [S4] R-35 · tabular.py [S4] R-36
│   └── building.py, checks_building.py [S5] R-37 · rack_spec.py, render_docs.py [S5] R-38 · snapshot.py (+) R-14/R-40
├── wizard/ (+)                          td_publish_wizard.py, td_publish_wizard_line.py, td_publish_wizard_views.xml: M-31, V-08
├── controllers/                         constructor.py (+) API-01…08 · library.py API-11, /site/addr · storage.py API-12 · stock.py API-13, 14 · putaway.py API-15 ·
│                                        odoo_import.py API-16, 20, /odoo/rules · plan.py API-17, 18 · render.py API-19 · wizard.py /site/wizard · collab.py API-21…24, /help · stub.py (not_implemented)
├── data/                                td_slot_type_data.xml [S1] (50 типів + `term_slot_type_floor_spot`), td_term_data.xml (+) (10 функцій і 4 атрибути зони), params.xml (+) (6 параметрів)
├── views/                               td_slot_type_views.xml (V-14), td_putaway_views.xml (V-15, V-16), td_collab_views.xml (V-17), td_help.xml (V-18: сторінка «Інструкція», розширення коментарів і варіантів)
├── static/
│   ├── lib/f3d-core/constructor.esm.js  [W0-A] збірка ядра (ESM, без three.js; коміт; `tools/build_core.mjs module`; хеш — `CORE_BUILD` у core_loader.js)
│   ├── src/tours/                       [S6] td_constructor_guide_tour.js, _variants_tour.js, _collab_tour.js (`web_tour.tours`, bundle `web.assets_tests`)
│   └── tests/{editor/s3…s6.test.js, fixtures/{addr_golden,cells_s1_golden,s2_fit_cases,s3_barcode_golden,s5_golden}.json, s4_python.xlsx, s4_roundtrip.xlsx}
└── tests/                               test_skeleton_*, test_registries, test_registry_hooks, test_new_fields_api, test_s1_* … test_s6_*, test_core_node, golden_*.py (§13.6)

factory3d/core/constructor/*             [W0-A, S1…S6] ядро редактора (JS + Three.js без Odoo), README.md; адаптери adapter.js, adapter_odoo.js, artifact/adapter_artifact.js
factory3d/tools/build_core.mjs, test_core.mjs, test_core_s1…s6.mjs     збірка й Node-тести ядра
factory3d/build/constructor/proto/*      прототип-артефакт (build.py, src/main.js, page.css, test_*.js Playwright)
```

## 1. Маніфест

```python
{
    "name": "Завод 3D: конструктор",
    "summary": "Конструктор розкладки заводу: площадки, шари, місця зі стелажів-шаблонів, каталог варіантів обладнання з 3D, перевірки, публікація в Odoo",
    "description": "3D-редактор розкладки (шари з відмітками, сітка, шаблони стелажів → комірки, розстановка обладнання з перевірками), "
                   "каталог варіантів на паспортах обладнання з 3D-моделлю, чернетка → публікація з підтвердженням і історією версій.",
    "version": "19.0.1.0.0",
    "category": "Manufacturing/Manufacturing",
    "author": "ToDo",
    "website": "https://todo.ltd",
    "license": "LGPL-3",
    "depends": ["td_factory3d", "td_viewer3d", "stock", "maintenance", "mrp"],
    "data": [
        "security/td_constructor_security.xml",
        "security/ir.model.access.csv",
        "data/params.xml",
        "data/td_term_data.xml",
        "data/td_generic_catalog.xml",
        "views/td_site_views.xml",
        "views/td_layer_views.xml",
        "views/td_slot_views.xml",
        "views/td_equipment_variant_views.xml",
        "views/td_placement_views.xml",
        "views/td_check_config_views.xml",
        "views/td_layout_version_views.xml",
        "views/td_term_views.xml",
        "views/td_inherit_views.xml",
        "wizard/td_publish_wizard_views.xml",
        "data/actions.xml",
        "views/td_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "td_constructor/static/src/action/**/*",
            "td_constructor/static/src/editor/**/*",
            "td_constructor/static/src/model/**/*",
            "td_constructor/static/src/widgets/**/*",
        ],
        "web.assets_unit_tests": [
            "td_constructor/static/tests/editor/**/*",
            "td_constructor/static/tests/model/**/*",
            "td_constructor/static/tests/fixtures/*.json",
        ],
    },
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
}
```

Порядок `data`: групи → доступи → параметри → довідник → типові паспорти → представлення (V-04 посилається на віджети з assets) → майстер →
дії (`actions.xml` посилається на представлення й майстер) → меню. `static/lib/**` **не** входить у bundle: `dxf-parser.min.js` вантажиться ліниво
`loadJS("/td_constructor/static/lib/dxf-parser/dxf-parser.min.js")`, `f3d-loaders.esm.js` — динамічним `import()` (DEC-06); обидва — лише коли потрібні.
Тестові `*.json` фікстури лежать у `web.assets_unit_tests` як статика й читаються HOOT через `fetch` (мок із `@odoo/hoot-mock` дозволяє лише `blob:`/`data:`,
тож читати нативним `fetch` з чистого iframe, як `static/tests/hoot/helpers.js` переглядача).
`external_dependencies.python` порожні навмисно: `cascadio`, `ifcopenshell`, `IfcConvert` — **необов'язкові** (R-20, DEC-04), їх відсутність не блокує встановлення.
`application: False` — пункти меню живуть під «Завод 3D» (`td_factory3d.menu_td_root`, DEC-01).

### 1.1 Доповнення до маніфесту (19.0.1.4.0)

Версія `19.0.1.4.0` (1.2.0 — S1, 1.3.0 — S2/довідники зони, 1.4.0 — S6: тури в `web.assets_tests`). `depends` і `external_dependencies` **не змінилися**: `mail` приходить транзитивно
через `stock`/`maintenance` (`td.comment` успадковує `mail.thread`, `mail.activity.mixin`, M-22); XLSX/PDF — `openpyxl`, `xlsxwriter`, `reportlab`, `qrcode` з залежностей Odoo
(CD-30: Community, без `stock_barcode`, `documents`, `knowledge`). Нові файли `data` у порядку підключення: після `data/td_generic_catalog.xml` — `data/td_slot_type_data.xml`;
після `views/td_inherit_views.xml` — `views/td_slot_type_views.xml`, `views/td_putaway_views.xml`, `views/td_collab_views.xml`, `views/td_help.xml` (QWeb-сторінка й розширення
коментарів/варіантів; посилається на `td_collab_views`); `wizard/td_publish_wizard_views.xml`, `data/actions.xml`, `views/td_menus.xml` — як раніше.

```python
"assets": {
    "web.assets_backend": [   # без змін: action/, editor/ (лише core_loader.js, odoo_host.js), model/, widgets/
        "td_constructor/static/src/action/**/*", "td_constructor/static/src/editor/**/*",
        "td_constructor/static/src/model/**/*", "td_constructor/static/src/widgets/**/*"],
    "web.assets_unit_tests": ["td_constructor/static/tests/editor/**/*", "td_constructor/static/tests/model/**/*",
        "td_constructor/static/tests/fixtures/*.json"],
    "web.assets_tests": ["td_constructor/static/src/tours/*.js"],   # 19.0.1.4.0: `start_tour` виконуються лише так (AC-130)
},
```

Збірка ядра `static/lib/f3d-core/constructor.esm.js` **не входить** у bundle: вантажиться динамічним `import()` (`core_loader.js`, `CORE_URL?v=CORE_BUILD`), як `f3d-loaders` (DEC-06).
Збирає розробник (`node tools/build_core.mjs module`), файл комітиться; на сервері нічого не збирається (ARCH §2.2a).

## 2. Моделі

Спільні правила для M-01…M-07: `company_id` — Many2one `res.company`, на площадці `required`, `default=lambda s: s.env.company`; у дочірніх сутностей —
`related="site_id.company_id"`, `store=True`, `index=True` (для record rule; DEC-12). `uid` — Char(32), `default=lambda s: uuid4().hex`, `copy=False`, `index`,
`readonly` у формах; ключ між знімком версії, клієнтом (тимчасові id) і відновленням (DEC-14); UNIQUE `(site_id, uid)` для layer/slot/placement.
Усі Float-метри — `digits=(10, 3)`, якщо не сказано інакше. `active` — Boolean `default=True`; архівація сутності не видаляє записи Odoo.
Кожне `create/write/unlink` layer/slot/placement/check.config викликає `site._f3d_touch(n)` (R-21): `draft_rev += 1`, `draft_changes += n`.

### M-01 `td.site` — площадка (CD-22)

`_name='td.site'`, `_description='Площадка'`, `_order='sequence, name'`, `_rec_name='name'`, `_rec_names_search=['name','code']`.

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | `required`, `string="Назва"` |
| `code` | Char(16) | `required`, `index`, `string="Код"`, `^[A-Z0-9]+$`; префікс площадки для сторонніх кодів (Q-07) |
| `sequence` | Integer | `default=10` |
| `company_id` | Many2one `res.company` | див. вище |
| `building_length_m`, `building_width_m`, `building_height_m` | Float | `required`, `default=60/30/8`, `>0`; `string="Довжина будівлі, м"` … (CB-12: для демо 150/72/9) |
| `column_step_x_m`, `column_step_y_m` | Float | `default=6.0`, `>0`; крок колон (`column_grid`) |
| `default_parent_location_id` | Many2one `stock.location` | `domain=[('usage','in',('internal','view'))]`, `check_company`; куди публікуються комірки, у яких не задано `parent_location_id` |
| `layer_ids` | One2many `td.layer` `site_id` | |
| `check_config_ids` | One2many `td.check.config` `site_id` | |
| `version_ids` | One2many `td.layout.version` `site_id` | |
| `active_version_id` | Many2one `td.layout.version` | `readonly`, `copy=False`; остання опублікована версія |
| `draft_base_version_id` | Many2one `td.layout.version` | `readonly`; версія, на якій ґрунтується чернетка (публікація → нова версія; відновлення → вибрана) |
| `draft_rev` | Integer | `default=0`, `readonly`, `copy=False`; лічильник правок (R-21) |
| `draft_changes` | Integer | `default=0`, `readonly`; «змінено N» від `active_version_id` (обнуляється публікацією) |
| `published_rev` | Integer | `readonly`; `draft_rev` на момент останньої публікації; `has_changes = draft_rev != published_rev` |
| `has_changes` | Boolean | `compute`, `string="Є непубліковані зміни"` |
| `seed_key` | Char(32) | `copy=False`, `readonly`; `'main_demo'` для площадки з seed |
| `slot_count`, `placement_count`, `layer_count`, `version_count` | Integer | `compute` (не stored), для кнопок-лічильників |
| `active` | Boolean | |

SQL: `_f3d_site_code_uniq = models.Constraint("UNIQUE(company_id, code)", "Код площадки має бути унікальним у компанії.")`;
`_f3d_site_seed_uniq = models.Constraint("UNIQUE(seed_key)", "Seed-площадка вже існує.")`.
`@api.constrains` розмірів: `"Розміри будівлі мають бути додатними."`.

Методи: `create` (після супер: `_f3d_init_checks()`; якщо `context.f3d_blank` — `_f3d_init_blank()`); `_f3d_init_checks()` — 7 рядків `td.check.config` за таблицею R-04
(ідемпотентно); `_f3d_init_blank()` — R-23 (5 базових шарів); `action_open_constructor()` → `{'type':'ir.actions.client','tag':'f3d_constructor','params':{'site_id':id}}`;
`action_publish_wizard()` → створює `td.publish.wizard` і повертає `act_window` (M-08; права — менеджер); `_f3d_touch(n=1)` (sudo, без `write_date` каскаду);
`_f3d_check_rights_manager()` → `AccessError("Лише менеджер конструктора…")`.

### M-02 `td.layer` — шар (CD-04, CD-05, CD-06, CD-09)

`_name='td.layer'`, `_description='Шар розкладки'`, `_order='site_id, sequence, elevation_m, id'`, `_rec_name='name'`.

| Поле | Тип | Параметри |
|---|---|---|
| `uid` | Char(32) | див. вище |
| `site_id` | Many2one `td.site` | `required`, `ondelete='cascade'`, `index` |
| `name` | Char | `required` |
| `kind` | Selection | `building`/`Будівля`, `storage`/`Склади`, `production`/`Виробництво`, `engineering`/`Інженерні мережі`, `yard`/`Двір`, `custom`/`Свій шар`; `required`, `default='custom'` |
| `sequence` | Integer | `default=10` |
| `elevation_m` | Float | `digits=(8,3)`, `default=0`; висотна відмітка (+3.6 для «Антресоль офісу») |
| `grid_step_m` | Float | `digits=(6,3)`, `default=0.5`, `>0`; крок сітки прив'язки |
| `aisle_width_m` | Float | `digits=(6,3)`, `default=3.0`, `≥0`; типова ширина проходу (для малювання проходів і перевірки `aisles_free` — розмір з `aisles`) |
| `max_floor_load_kn_m2` | Float | `digits=(8,2)`, `default=0`; `0` = перевірка `load` для шару вимкнена (Q-09) |
| `bounds` | Json | `False` або `[[x,y],…]` (≥3 точки, метри, простий багатокутник); `False` = габарит будівлі |
| `allowed_slot_type_ids` | Many2many `td.term` | `relation='td_layer_slot_type_rel'`, `domain=[('term_type','=','slot_type')]`; порожньо = усі типи |
| `edit_group_ids` | Many2many `res.groups` | `relation='td_layer_edit_group_rel'`; хто пише місця/розміщення шару (R-11); порожньо = лише менеджер |
| `color` | Char(7) | `default='#8d99ae'`, `^#[0-9a-fA-F]{6}$` |
| `opacity` | Float | `digits=(3,2)`, `default=1.0`, `0..1` |
| `style` | Selection | `solid`/`Суцільний`, `wire`/`Каркас`, `dashed`/`Пунктир`; `default='solid'` |
| `visible` | Boolean | `default=True`; видимість за замовчуванням у редакторі |
| `aisles` | Json | `default=[]`; список `{id: str, name: str, x0,y0,x1,y1: float}` (осьовий прямокутник, `x0<x1`, `y0<y1`) |
| `fire_paths` | Json | `default=[]`; `{id, kind: 'path'|'exit', name, x0,y0,x1,y1}` (шлях евакуації або майданчик перед виходом) |
| `utilities` | Json | `default=[]`; `{id, kind: 'electric'|'air'|'dust'|'panel', name, x, y, z}` (щити й магістралі) |
| `underlay_attachment_id` | Many2one `ir.attachment` | `ondelete='set null'`, `copy=False`; підкладка DXF/DWG (DEC-18) |
| `underlay_format` | Selection | `dxf`, `dwg`; `compute`/`store` з розширення файла вкладення; `False`, якщо немає |
| `underlay_status` | Selection | `none`, `ready` (DXF), `pending_conversion` (DWG, фаза 2); `compute`/`store` |
| `underlay_params` | Json | `default={}`; `{unit: 'mm'|'m', dx, dy, rot_deg, opacity, scale}`, за замовчуванням `{unit:'mm',dx:0,dy:0,rot_deg:0,opacity:0.5,scale:1}` |
| `company_id` | Many2one | related site, stored |
| `slot_count`, `placement_count` | Integer | `compute` |
| `is_manager` | Boolean | `compute` (не stored): `has_group` менеджера конструктора; для `readonly` у формі |
| `active` | Boolean | |

`@api.constrains`: `grid_step_m > 0` («Крок сітки має бути додатним.»); `bounds` — валідний багатокутник («Контур шару: щонайменше 3 точки.»); кожен елемент
`aisles`/`fire_paths`/`utilities` відповідає схемі (R-22: ключі, типи, `x0<x1`, `id` унікальні в межах поля; «Прохід N: некоректні координати.»);
`opacity` у `[0,1]`; `edit_group_ids` — лише групи привілею «Конструктор» (`privilege_td_constructor`) і `base.group_user`-похідні не дозволені («Лише ролі конструктора.»).
`write` (R-11): поля `layer_content = {aisles, fire_paths, utilities, underlay_attachment_id, underlay_params}` може писати користувач з `edit_group_ids` шару;
решту полів і `create/unlink` — лише менеджер. Видалення шару з місцями/розміщеннями — `UserError("Шар не порожній: архівуйте його або перенесіть об'єкти.")`.

### M-03 `td.slot` — місце за шаблоном (CD-07, CD-08)

`_name='td.slot'`, `_description='Місце (шаблон)'`, `_order='layer_id, code_prefix'`, `_rec_name='code_prefix'`.

| Поле | Тип | Параметри |
|---|---|---|
| `uid` | Char(32) | |
| `layer_id` | Many2one `td.layer` | `required`, `ondelete='cascade'`, `index` |
| `site_id` | Many2one `td.site` | `related='layer_id.site_id'`, `store=True`, `index=True` |
| `company_id` | Many2one | related site, stored |
| `template` | Selection | `pallet_rack`/`Паллетний стелаж`, `cantilever`/`Консольний стелаж`, `shelf`/`Полицевий стелаж / комірки фурнітури`, `floor_stack`/`Підлогове штабелювання`, `machine_spot`/`Місце під верстат`, `zone`/`Зона-контур`; `required`. Ворота/док — не входять (CD-08) |
| `code_prefix` | Char(22) | `required`, `^[A-Z0-9]+(-[A-Z0-9]+)*$` (`FG-R1`); ≤ 22, щоб код комірки (суфікс до 9 символів) вкладався у 32 (CB-01) |
| `x_m`, `y_m` | Float | центр габариту в метрах |
| `rotation` | Integer | `default=0`, `selection`-подібне обмеження `{0,90,180,270}` («Поворот місця кратний 90°.») |
| `params` | Json | параметри шаблону (R-01), `default={}` ; валідуються `services.cells.validate_params(template, params)` |
| `overrides` | Json | `default={}`; `{ "<код комірки>": {"disabled": bool, "max_load_kg": float, "capacity": float, "name": str≤64} }`; ключі, що не відповідають комірці, відкидаються при `write` («Комірки X немає в шаблоні.») |
| `parent_location_id` | Many2one `stock.location` | `domain=[('usage','in',('internal','view'))]`, `check_company`; куди публікувати комірки (R-12) |
| `cell_count` | Integer | `compute`, `store`, `depends=['template','params','overrides']`; кількість недисаблених комірок; 0 для `machine_spot`/`zone` |
| `footprint_l_m`, `footprint_w_m` | Float | `compute`, `store`: габарит у локальній системі (R-01) |
| `cells_html` | Html | `compute` (не stored), лише для форми: перші 50 комірок і підсумок «Усього N» |
| `note` | Text | |
| `active` | Boolean | |

SQL: `_f3d_slot_prefix_uniq = models.Constraint("UNIQUE(site_id, code_prefix)", "Префікс місця має бути унікальним на площадці.")`.
`@api.constrains('template','layer_id')`: шаблон дозволений шаром (`layer.allowed_slot_type_ids` порожнє або містить тип з `key == template`; «Шар «%s» не допускає тип «%s».»).
Метод `_f3d_cells(self)` → `list[dict]` — комірки на льоту (`services.cells.generate_cells`), **не зберігаються** (DEC-15); поля елемента — R-01. Метод
`_f3d_footprint_obb()` → OBB (R-02) для checks.

### M-04 `td.equipment.variant` — варіант обладнання (CD-10, CD-11, CD-12, CD-15…CD-19)

`_name='td.equipment.variant'`, `_description='Варіант обладнання'`, `_order='passport_id, sequence, id'`, `_rec_name='display_name'`; `display_name` = `"%s · %s" % (passport.name, name)`.
Каталог **глобальний** (спільний для площадок; DEC-02) — без `site_id`/`company_id`.

| Поле | Тип | Параметри |
|---|---|---|
| `passport_id` | Many2one `td.equipment.passport` | `required`, `ondelete='cascade'`, `index`, `string="Тип (паспорт)"` |
| `name` | Char | `required`, `string="Назва варіанта"` |
| `sequence` | Integer | `default=10` |
| `category` | Selection | `related='passport_id.td_category'`, `store=True`, `readonly=True` |
| `length_mm`, `width_mm`, `height_mm` | Integer | `string="Довжина/Ширина/Висота, мм"`; `>0` (constraint); у `create`, якщо не задані, беруться з `passport.dim_l_mm/dim_w_mm/dim_h_mm` |
| `service_front_mm`, `service_back_mm`, `service_left_mm`, `service_right_mm` | Integer | `default=0`, `≥0`; зона обслуговування: фронт/зад/ліворуч/праворуч (R-02) |
| `front_side` | Selection | `s`/`Південь (−Y)`, `n`/`Північ (+Y)`, `e`/`Схід (+X)`, `w`/`Захід (−X)`; `default='s'`; сторона фронту при повороті 0° |
| `anchor` | Selection | `center`/`Центр`, `front`/`Центр фронту`, `back`/`Центр тилу`, `corner`/`Лівий передній кут`; `default='center'`; точка, якою виріб прив'язаний до `(x_m,y_m)` розміщення |
| `rotation_mode` | Selection | `q`/`0/90/180/270°`, `h`/`0/180°`, `z`/`Лише 0°`, `any`/`Будь-який кут`; `default='q'` |
| `allowed_layer_kind_ids` | Many2many `td.term` | `relation='td_variant_layer_kind_rel'`, `domain=[('term_type','=','layer_kind')]`; порожньо = будь-який шар; за замовчуванням за категорією (R-23) |
| `allowed_slot_type_ids` | Many2many `td.term` | `relation='td_variant_slot_type_rel'`, `domain=[('term_type','=','slot_type')]`; порожньо = без обмежень |
| `utilities` | Json | `default=[]`; точки підключення `{kind: 'electric'|'air'|'dust', x_mm, y_mm, z_mm}` у локальній системі виробу (початок — центр габариту, X вздовж довжини, Y вздовж ширини; R-02) |
| `power_kw` | Float | `digits=(8,2)`, `≥0`; у `create` береться з `passport.power_kw`, якщо не задано |
| `panel` | Char(64) | щит живлення («ГРЩ-1», `string="Щит"`) |
| `weight_kg` | Float | `digits=(10,1)`, `≥0` |
| `floor_load_kn_m2` | Float | `digits=(8,2)`, `compute='_compute_floor_load'`, `store=True`, `readonly=False`; `weight_kg·9.80665/1000 / (L·W, м²)`, можна перевизначити вручну |
| `create_workcenter` | Boolean | `default=False`; `onchange`/default `True`, якщо `category=='machine'`; публікація створює `mrp.workcenter` (R-12) |
| `model_original_id` | Many2one `ir.attachment` | `ondelete='set null'`, `copy=False`; оригінал файла (до 20 МБ) |
| `model_glb_id` | Many2one `ir.attachment` | `ondelete='set null'`, `copy=False`; полегшений GLB для перегляду |
| `model_meta` | Json | `default={}`; `{format, file_name, size_bytes, glb_size_bytes, triangles, bbox_m: [x,y,z], size_mm: {x,y,z}, units: 'mm'|'cm'|'m'|'in', up_axis: 'y'|'z', status, warnings: [str], message: str, converted_by: 'browser'|'server'|None}` |
| `model_status` | Selection | `none`/`Немає`, `ok`/`Готово`, `pending_conversion`/`Очікує перетворення`, `error`/`Помилка`; `default='none'`, `readonly`, `index`; пише лише `_f3d_set_model` |
| `model_warning` | Char | `compute`: «N тис. трикутників при ліміті M тис.» якщо `meta.triangles > max_triangles` або `meta.warnings` |
| `image` | Image | `max_width=512`, `max_height=512`; мініатюра, яку знімає віджет W3 при завантаженні |
| `placement_count` | Integer | `compute` |
| `note` | Text | |
| `active` | Boolean | |

`@api.constrains`: розміри `>0` («Розміри варіанта мають бути додатними.»); сервіс `≥0`; `utilities` — масив об'єктів зі схемою (R-22; `kind` ∈ electric/air/dust, числа скінченні);
`model_meta.status` узгоджений з `model_status`; `model_status=='ok'` вимагає `model_glb_id`.
Методи: `_f3d_set_model(original, glb, meta, status, message)` (єдина точка запису полів моделі; перевірки R-18; повертає `dict(model_status, model_meta)`);
`_f3d_convert_model()` (R-20; нічого не кидає, повертає `{'ok': bool, 'status': str, 'message': str}`); `_f3d_effective_floor_load()`; `_f3d_local_geometry()` (R-02);
`action_clear_model()` (скидає вкладення й мета, `model_status='none'`; право — технолог/менеджер); `action_retry_convert()` (повторює `_f3d_convert_model()`); `unlink` — `UserError`, якщо є розміщення (архівуйте варіант).

### M-05 `td.placement` — розміщення обладнання (CD-10, CD-13)

`_name='td.placement'`, `_description='Розміщення обладнання'`, `_order='layer_id, code'`, `_rec_name='code'`.

| Поле | Тип | Параметри |
|---|---|---|
| `uid` | Char(32) | |
| `layer_id` | Many2one `td.layer` | `required`, `ondelete='cascade'`, `index` |
| `site_id`, `company_id` | Many2one | related, stored |
| `variant_id` | Many2one `td.equipment.variant` | `required`, `ondelete='restrict'`, `index` |
| `slot_id` | Many2one `td.slot` | `ondelete='set null'`, `domain=[('layer_id','=',layer_id)]`; місце під верстат / стелаж, в який поставлено |
| `cell_code` | Char(32) | необов'язково: комірка стелажа `slot_id` (R-04 fits/load); має бути серед `slot._f3d_cells()` |
| `code` | Char(32) | `required`, `^[A-Z0-9]+(-[A-Z0-9]+)*$`; майбутній `td_code` обладнання (CB-01) |
| `name` | Char | `required`; майбутня назва `maintenance.equipment` |
| `x_m`, `y_m` | Float | точка прив'язки (R-02) |
| `rotation` | Float | `digits=(6,2)`, `default=0`, `[0,360)`; нормалізується `%360`; допустимість — `variant.rotation_mode` (перевірка `fits`, не constraint, щоб редактор міг показати проблему) |
| `note` | Text | |
| `equipment_id` | Many2one `maintenance.equipment` | `readonly`, `copy=False`, `ondelete='set null'`; зв'язок після публікації/seed |
| `workcenter_id` | Many2one `mrp.workcenter` | те саме |
| `published_at` | Datetime | `readonly` |
| `active` | Boolean | |

SQL: `_f3d_placement_code_uniq = models.Constraint("UNIQUE(site_id, code)", "Код розміщення має бути унікальним на площадці.")`.
`@api.constrains('variant_id','layer_id')`: `variant.length_mm>0`. Методи: `_f3d_obb()`, `_f3d_service_obb()` (R-02); `action_show_in_3d()` → `equipment_id.action_f3d_show()` або
`UserError("Об'єкт ще не опубліковано в Odoo.")`.

### M-06 `td.check.config` — налаштування перевірки (CD-13, CD-14)

`_name='td.check.config'`, `_description='Перевірка розкладки'`, `_order='site_id, sequence'`.

| Поле | Тип | Параметри |
|---|---|---|
| `site_id` | Many2one `td.site` | `required`, `ondelete='cascade'` |
| `company_id` | Many2one | related, stored |
| `check_key` | Selection | `fits`/`Вміщується`, `collide`/`Перетини`, `service_free`/`Зона обслуговування вільна`, `aisles_free`/`Проходи вільні`, `load`/`Навантаження`, `utility_reach`/`Досяжність підключення`, `fire`/`Пожежні проходи й виходи`; `required` |
| `sequence` | Integer | порядок за списком вище (10…70) |
| `enabled` | Boolean | `default=True` |
| `mode` | Selection | `warn`/`Попередження`, `block`/`Заборона`; `required`, `default` — R-04 |
| `params` | Json | `default={}`; `utility_reach`: `{max_m: float}`; `collide`/`fits`/…: `{tolerance_mm: int}` (за замовчуванням `td.constructor.eps_mm`) |

SQL: `_f3d_check_uniq = models.Constraint("UNIQUE(site_id, check_key)", "Перевірка вже налаштована для площадки.")`.
`@api.constrains('params')`: `utility_reach.max_m > 0`, `tolerance_mm ≥ 0`.

### M-07 `td.layout.version` — версія планування (CD-21)

`_name='td.layout.version'`, `_description='Версія планування'`, `_order='site_id, n desc'`, `_rec_name='display_name'` (`"v%d · %s" % (n, site.name)`).

| Поле | Тип | Параметри |
|---|---|---|
| `site_id` | Many2one `td.site` | `required`, `ondelete='cascade'`, `index` |
| `company_id` | Many2one | related, stored |
| `n` | Integer | `required`, `readonly`; номер за площадкою: `max(n)+1`, UNIQUE `(site_id, n)` |
| `note` | Text | нотатка публікації |
| `published_by_id` | Many2one `res.users` | `readonly` |
| `published_at` | Datetime | `readonly`, `default=now` |
| `state` | Selection | `active`/`Діюча`, `superseded`/`Замінена`; `default='active'` (§10) |
| `snapshot_id` | Many2one `ir.attachment` | знімок (JSON, R-14), `res_model='td.layout.version'`, `res_id=id`, `type='binary'`, `mimetype='application/json'`; `ondelete='set null'` |
| `snapshot_sha1` | Char(40) | `readonly` |
| `draft_rev` | Integer | `site.draft_rev` на момент публікації |
| `slot_count`, `cell_count`, `placement_count`, `layer_count` | Integer | `readonly` |
| `created_count`, `updated_count`, `archived_count` | Integer | `readonly`; підсумок публікації |
| `report` | Json | `{created: [{model, code, id}], updated: [...], archived: [...], warnings: [issue,…]}` |
| `is_seed` | Boolean | `readonly`; v1 з seed (R-24) |

Права: створює лише `services.publish.apply_plan` і хук seed (через `sudo`); `write` дозволений тільки для `note` менеджеру; `unlink` — лише `group_td_admin` (історію не стираємо).
Методи: `action_restore_draft()` (R-14; менеджер); `action_download_snapshot()` → `ir.actions.act_url` на `/web/content/<snapshot_id>?download=true`.

### M-08 `td.publish.wizard` — майстер публікації (TransientModel; CD-20)

`_name='td.publish.wizard'`, `_description='Публікація розкладки'`.

| Поле | Тип | Параметри |
|---|---|---|
| `site_id` | Many2one `td.site` | `required`, `readonly` |
| `note` | Text | `string="Нотатка до версії"` |
| `draft_rev` | Integer | `readonly`; `site.draft_rev` на момент побудови плану (захист від застарілого майстра) |
| `state` | Selection | `preview`/`Попередній перегляд`, `done`/`Опубліковано`; `default='preview'` |
| `line_ids` | One2many `td.publish.wizard.line` | `wizard_id` |
| `issue_ids` | One2many `td.publish.wizard.issue` | `wizard_id` |
| `n_create`, `n_update`, `n_archive`, `n_unchanged`, `n_warn`, `n_block` | Integer | `compute`; `n_archive` — лише відмічені |
| `can_publish` | Boolean | `compute`: `n_block == 0` і `site.has_changes` і `publish_enabled` |
| `version_id` | Many2one `td.layout.version` | після публікації |

Методи: `default_get` не використовується; майстер створює `site.action_publish_wizard()` → `services.publish.build_plan(site)` → рядки/зауваження (R-12). `action_confirm()`: перевірка
`draft_rev == site.draft_rev` (інакше `UserError("Чернетка змінилась. Закрийте вікно й відкрийте майстер знову.")`), перерахунок плану, `services.publish.apply_plan(...)`,
`state='done'`, `version_id`, повертає `act_window` версії. `action_cancel()` — закрити без змін.

### M-09 `td.publish.wizard.line` — рядок плану

`_name='td.publish.wizard.line'`, `_order='kind, model, code'`. Поля: `wizard_id` (Many2one, cascade); `kind` (Selection `create`/«Буде створено», `update`/«Буде оновлено»,
`archive`/«Пропонуємо архівувати»); `res_model` (Selection `stock.location`, `maintenance.equipment`, `mrp.workcenter`); `code` (Char); `name` (Char); `res_id` (Integer, 0 для create);
`source_uid` (Char; `uid` місця/розміщення, `''` для archive); `changes` (Text: «td_capacity: 0 → 4; parent: WH/Stock → WH/Stock/FG»; для create — коротка картка «місткість 4, вид pallet_cell»);
`selected` (Boolean; `default=True` для create/update, **`False` для archive**; для `blocked=True` змінювати не можна); `blocked` (Boolean); `blocked_reason` (Char: «Є залишки: 12.0 од.», «Код зайнятий записом поза площадкою»).

### M-10 `td.publish.wizard.issue` — зауваження перевірок

`_name='td.publish.wizard.issue'`, `_order='severity desc, check_key, id'`. Поля: `wizard_id`; `check_key` (Selection як у M-06 плюс `conflict`/«Конфлікт кодів», `data`/«Дані»); `severity` (`warn`/`block`);
`layer_id` (Many2one `td.layer`); `codes` (Char, через кому); `message` (Char).

### M-11 `td.term` — довідник конструктора (DEC-02)

`_name='td.term'`, `_description='Довідник конструктора'`, `_order='term_type, sequence'`, `_rec_name='name'`. Поля: `term_type` (Selection `layer_kind`/«Вид шару», `slot_type`/«Тип місця»; `required`),
`key` (Char(32), `required`; ключі — як значення `td.layer.kind` та `td.slot.template`), `name` (Char, `required`, `translate=False`), `sequence`, `active`.
SQL: `UNIQUE(term_type, key)`. Дані — `data/td_term_data.xml` (12 записів, §5.1), `noupdate="0"`; створення/зміна — менеджер, видалення — лише `group_td_admin`.

### M-12 `td.equipment.passport` — розширення (CB-07, CD-10)

`_inherit='td.equipment.passport'`. Додані поля: `td_category` (Selection `machine`/«Верстат», `rack`/«Стелаж», `forklift`/«Навантажувач», `conveyor`/«Конвеєр»,
`panel`/«Шафа/щит», `robot`/«Робот», `other`/«Інше»; `default='other'`, `index`, `string="Категорія (конструктор)"`; від неї залежить умовна модель, CD-18);
`variant_ids` (One2many `td.equipment.variant` `passport_id`); `variant_count` (Integer, `compute`). Метод `action_view_variants()` → `act_window` варіантів паспорта.
Існуючі 93 паспорти base отримують `td_category` у `post_init_hook` за таблицею ролі→категорії (§5.3; решта — `other`).

### M-13 `stock.location` — розширення

Поля: `td_site_id` (Many2one `td.site`, `index`, `copy=False`, `ondelete='set null'`, `readonly`, `string="Площадка конструктора"`) — запис керується конструктором (CC-01);
`td_slot_uid` (Char(32), `copy=False`, `readonly`) — `uid` місця, з якого створено/оновлено. Інших змін немає. Права на ці поля — як у base R-04 (пише лише `publish` під `sudo`).

### M-14 `maintenance.equipment` — розширення

Поля: `td_site_id` (як у M-13), `td_placement_uid` (Char(32)). Метод `action_f3d_show()` — з base (CB-02), не міняється.

### M-15 `mrp.workcenter` — розширення

Поля: `td_site_id` (як у M-13). Зв'язок `maintenance.equipment.workcenter_id` ставиться, лише якщо поле існує в реєстрі (`"workcenter_id" in env["maintenance.equipment"]._fields`; його додає `mrp_maintenance`, DEC-16).

### 2.1 Моделі злиття (M-16…M-31): загальні правила

Усе нижче — **факт коду** `19.0.1.4.0` (`models/*.py`); поля, які тут не названо, лишилися як у M-01…M-15. Правила, спільні для M-16…M-31:

- Мультикомпанія: нові моделі з `company_id` мають глобальне `ir.rule` `['|', ('company_id','=',False), ('company_id','in',company_ids)]` (§4.5); `td.publish.op` — за `version_id.company_id`.
- Чернетки (`td.putaway.rule`, `td.replenish.rule`) успадковують `td.draft.mixin` (M-24): `uid`, `etag`, лічильник R-21, права R-11, нормалізація JSON R-22, перевірка оренди зони R-39. У Odoo (`stock.putaway.rule`,
  `stock.warehouse.orderpoint`) вони потрапляють **лише публікацією** (CD-31 Q4).
- Типи, пресети, варіанти, коментарі, оренди — не чернетка площадки: `site._f3d_touch` вони не викликають (крім правок, що змінюють розкладку: `/site/addr`, `/odoo/rules`, перемикання варіанта).
- Тексти помилок — українською; помилки доступу — `AccessError`, помилки даних — `ValidationError`/`UserError`; API перетворює їх на `rights`/`validation` (§7.1).

### M-16 `td.slot.type` — тип місця (F08, CD-31 Q9)

`_description = "Тип місця"`, `_order = 'group, sequence, id'`, `_rec_names_search = ['name','code','ref']`. Запис каталогу: генератор (R-26) + параметри за замовчуванням + форма 3D + група. Каталог — **50 типів** у `data/td_slot_type_data.xml` (`noupdate="0"`),
який **генерується** з `core/constructor/types_data.js` (Node-тест `tools/test_core_s1.mjs` звіряє файл із ядром). Типи користувачів у файл не входять.

| Поле | Тип | Параметри |
|---|---|---|
| `code` | Char(32) | `required`, `index`; `^[A-Za-z0-9][A-Za-z0-9_]{0,31}$`; для каталогу — `ref` малими літерами; **не змінюється** після створення (API-11 `validation`) |
| `ref` | Char(16) | позначення в каталозі: `R01`, `FL2`, `SP3`… |
| `name` | Char | `required` |
| `description` | Text | |
| `group` | Selection | `required`, `default='rack'`, `index`: `rack` (20 типів), `floor` (5), `special` (8), `zone` (12), `mobile` (5) |
| `template` | Selection | значення M-03 `template` (R-26); порожньо — об'єкт будівлі (ворота/док), без комірок |
| `shape` | Char(32) | ключ форми з реєстру `shapes` ядра (`SHAPE_KEYS`: `rack`, `roll_rack`, `stack`, `zone`, `fence`, `cylinder`, `cabinet`, `mobile`, `gate`; порожньо — каркас генератора) |
| `params` | Json | `default=dict`; параметри за замовчуванням, нормалізуються `cells.normalize_params(template, params)` (R-22) |
| `relevance` | Integer | `default=0`; `CHECK (0..2)`: 0 — немає на фабриці («—»), 1 — буває («○»), 2 — є («●»); у UI за замовчуванням показуються 1 і 2 |
| `loc_kind` | Selection | `stack`, `bin`, `shelf`, `pallet_cell`, `kit`, `area` (значення `stock.location.td_loc_kind`, CB-05) |
| `is_custom` | Boolean | `default=False`; створений користувачем |
| `company_id` | Many2one `res.company` | порожньо — тип каталогу, спільний для всіх; власний тип — компанія автора |
| `sequence`, `active` | Integer(10), Boolean | |

Обмеження: UNIQUE-індекс `(code, COALESCE(company_id, 0))`; `CHECK (relevance BETWEEN 0 AND 2)`; `_check_code`, `_check_params` («невідома форма 3D», помилка параметрів, JSON-ліміти R-22), `_check_template_spot` (генератори `machine_spot` і `zone`
типом не стають: у них немає комірок). Права: менеджер створює/змінює типи каталогу й видаляє; проєктувальники (технолог, комірник, інженер) створюють **лише власні** (`is_custom=True`, компанія = поточна) і правлять їх; видалення — менеджер
(`AccessError`). Тип, який використовує хоч одне місце (`td.slot.type_id`, `ondelete='restrict'`), видалити не можна (API-11).

### M-17 `td.slot.preset` — пресет (F09-06/07)

`_order = 'name, id'`. Збережена настройка для вставки.

| Поле | Тип | Параметри |
|---|---|---|
| `name` | Char | `required` |
| `type_id` | Many2one `td.slot.type` | `ondelete='set null'`, `index` |
| `kind` | Selection | `required`, `default='row'`: `row` (ряд), `section` (секція), `group` (виділене) |
| `data` | Json | `default=dict`; для `row`/`section` — `{slot: Spec}`, для `group` — `{slots: [Spec…]}` (1…200); `Spec = {template, params, rotation, type_code?, prefix?, dx?, dy?, addr?}` |
| `company_id` | Many2one `res.company` | `required`, `index`, `default=env.company` |
| `active` | Boolean | |

`data` зберігається **нормалізованим** (`_f3d_normalize_data`, R-22): `template` ∈ (`pallet_rack`, `cantilever`, `shelf`, `floor_stack`, `floor_spot`, `machine_spot`), `params` — за `cells.normalize_params`, `rotation` — ціле 0…359, `prefix` ≤ 32,
`addr` — `addr.normalize_addr`; секцією може бути лише стелаж чи штабель (`pallet_rack`, `cantilever`, `shelf`, `floor_stack`). `_check_data` відхиляє ненормалізовані дані. Права — як у M-16 (видаляє лише менеджер).

### M-18 `td.putaway.rule` — правило розміщення, чернетка (F04, CD-31 Q4)

`_inherit = ['td.draft.mixin']`, `_order = 'site_id, sequence, id'`. UNIQUE `(site_id, uid)`.

| Поле | Тип | Параметри |
|---|---|---|
| `site_id` | Many2one `td.site` | `required`, `ondelete='cascade'`, `index` |
| `uid` | Char(32) | `default=uuid4().hex`, `copy=False`, `index`, `readonly` |
| `product_id` / `category_id` | Many2one `product.product` / `product.category` | `ondelete='cascade'`; умова «товар» або «категорія товару» |
| `package_type_ids` | Many2many `stock.package.type` | таблиця `td_putaway_rule_package_type_rel` |
| `in_location_id` | Many2one `stock.location` | «коли приходить у» (звідки) |
| `out_code` | Char(32) | код комірки **чернетки**, ще не опублікованої; після публікації правило залежить від рядка її створення (`depends_code`) |
| `out_location_id` | Many2one `stock.location` | «куди» (опублікована локація) |
| `sublocation` | Selection | `no` (за замовч.), `last_used`, `closest_location` |
| `storage_category_id` | Many2one `stock.storage.category` | |
| `sequence` | Integer | `default=10` (пріоритет) |
| `odoo_rule_id` | Many2one `stock.putaway.rule` | `readonly`, `copy=False`, `ondelete='set null'`, `index`; заповнює публікація |
| `deleted` | Boolean | «Видалено в чернетці»: публікація видалить правило в Odoo |
| `company_id` | related `site_id.company_id` | `store=True`, `index=True` |
| `active` | Boolean | |

Права: читає `group_td_user`; пишуть технолог, комірник, інженер, менеджер (в т.ч. видаляють). Поведінка — R-30, R-31.

### M-19 `td.replenish.rule` — правило поповнення min/max, чернетка (F03-07)

`_inherit = ['td.draft.mixin']`, `_order = 'site_id, cell_code, id'`. UNIQUE `(site_id, uid)`. Поля `site_id`, `uid`, `company_id`, `active`, `deleted` — як у M-18; решта:

| Поле | Тип | Параметри |
|---|---|---|
| `product_id` | Many2one `product.product` | `required`, `ondelete='cascade'` |
| `cell_code` | Char(32) | код комірки чернетки |
| `location_id` | Many2one `stock.location` | `ondelete='cascade'`; опублікована локація |
| `min_qty`, `max_qty` | Float | `digits='Product Unit'` |
| `odoo_orderpoint_id` | Many2one `stock.warehouse.orderpoint` | `readonly`, `copy=False`, `ondelete='set null'`, `index` |

`_check_min_max`: «Мінімум і максимум … не можуть бути від'ємними», «Максимум … не може бути меншим за мінімум». Права — як у M-18.

### M-20 `td.publish.op` — операція публікації, журнал (F02-08)

`_order = 'version_id, seq, id'`. Створює лише `publish.apply_plan` (під `sudo`); для всіх, крім адміна, — тільки читання. Відкат працює за цим журналом (R-32).

| Поле | Тип | Параметри |
|---|---|---|
| `version_id` | Many2one `td.layout.version` | `required`, `ondelete='cascade'`, `index`, `readonly` |
| `seq` | Integer | порядковий номер у версії |
| `op` | Selection | `create`, `move`, `rename`, `attrs`, `archive` |
| `res_model` | Selection | `stock.location`, `maintenance.equipment`, `mrp.workcenter`, `stock.warehouse.orderpoint`, `stock.putaway.rule` |
| `res_id` | Integer | id запису Odoo |
| `code` | Char | код (або ключ) запису |
| `before`, `after` | Json | значення полів до й після (для `create` `before` порожнє) |
| `rolled_back` | Boolean | `default=False`, ставить `rollback_version` |

### M-21 `td.layout.variant` — варіант планування (F12, N-03)

`_order = 'site_id, sequence, id'`. Гілка чернетки як **знімок** R-14; історія публікацій лишається в `td.layout.version`. Рівно один варіант на площадку активний (`site.active_variant_id`): чернетка площадки — його «живі» записи.

| Поле | Тип | Параметри |
|---|---|---|
| `site_id` | Many2one `td.site` | `required`, `ondelete='cascade'`, `index` |
| `name` | Char | `required`; унікальність серед робочих варіантів площадки — без урахування регістру (перевіряється в `f3d_make`/`rename`) |
| `sequence` | Integer | `default=10` |
| `snapshot_id` | Many2one `ir.attachment` | знімок R-14 (JSON), `ondelete='set null'`, `copy=False` |
| `base_version_id` | Many2one `td.layout.version` | версія, від якої гілка; `index` |
| `is_training` | Boolean | «Навчальний»: тимчасова копія для турів (F19-04), **не публікується** |
| `origin_id` | Many2one `td.layout.variant` | варіант, до якого повертає «Скасувати» навчальної копії |
| `metrics` | Json | цифри для порівняння: `cells`, `places`, `area`, `volume`, `max_weight` (рахує ядро, сервер лише зберігає числа, округлені до 3 знаків) |
| `company_id` | related `site_id.company_id` | `store=True` |
| `active` | Boolean | |
| `is_current` | Boolean | `compute`: `site.active_variant_id == self` |

Методи (права — менеджер, `AccessError` «Варіантами планування керує лише менеджер конструктора»): `f3d_ensure(site)` — перший варіант «Як є» зі знімком поточної чернетки; `f3d_make(site, name, training, activate, metrics)` — «Створити з поточного»
(ліміт `td.constructor.variants_max=12` на площадку для робочих; навчальна копія — одна); `f3d_activate(metrics)` — знімок поточної гілки → `apply_snapshot` вибраної, `draft_base_version_id`, `draft_changes` = відмінності від діючої версії
(чернетка не втрачається); `f3d_end_training(keep)` — «Залишити зміни» (стає робочим) або «Скасувати» (повернення до `origin_id` і видалення копії); `f3d_dict(ops)`. Розширення `td.layout.version.create`: публікація
(`kind='publish'`) пише `variant_id` активного варіанта, а для навчальної копії — `UserError("Навчальна копія не публікується в Odoo …")`. Видалення активного й єдиного варіанта заборонене в API-21 (форма Odoo це дозволяє: `ondelete='set null'`,
наступний `f3d_ensure` бере перший робочий).

### M-22 `td.comment` — коментар або задача (F13)

`_inherit = ['mail.thread', 'mail.activity.mixin']`, `_order = 'site_id, state, id desc'`. Об'єкт чернетки позначається `target_uid` (записів Odoo в чернетки немає). **Відхилення від MERGE §3.2** («`mail.activity` не беремо»): для задач із виконавцем
створюється завдання `mail.activity` (див. DEC-22 ARCH); сервіс `mail` — з Community.

| Поле | Тип | Параметри |
|---|---|---|
| `site_id` | Many2one `td.site` | `required`, `ondelete='cascade'`, `index` |
| `target_kind` | Selection | `required`, `default='slot'`: `site`, `layer`, `slot`, `cell`, `placement`, `item` (об'єкт будівлі) |
| `target_uid` | Char(64) | `index`: uid шару/місця/розміщення/об'єкта або код комірки |
| `target_label` | Char | підпис об'єкта (≤ 200) |
| `kind` | Selection | `required`, `default='note'`, `tracking`: `note` (коментар), `task` (задача) |
| `state` | Selection | `required`, `default='open'`, `index`, `tracking`: `open`, `resolved` |
| `text` | Text | `required`; ≤ 4000 символів |
| `author_id` | Many2one `res.users` | `required`, `default=env.user`, `ondelete='restrict'` |
| `assignee_id` | Many2one `res.users` | `tracking`; лише для задачі; має мати доступ до конструктора |
| `resolved_by_id`, `resolved_at` | Many2one `res.users`, Datetime | `readonly`, `copy=False` |
| `company_id` | related `site_id.company_id` | `store=True` |
| `active` | Boolean | |

Методи: `f3d_add(site, vals)` (будь-хто з `group_td_user`; помилки «Введіть текст коментаря», «Текст довший за 4000 символів», «Вид: коментар або задача», «Невідомий вид об'єкта», «Виконавця можна призначити лише задачі»,
«Виконавець не має доступу до конструктора»), `f3d_set_text`, `f3d_resolve(resolved)`, `f3d_remove` — **змінює, вирішує й видаляє автор або «Проєктування»** (технолог, комірник, інженер, менеджер); `_f3d_sync_activity` — відкрита задача з виконавцем має
рівно одне `mail.activity` (`mail.mail_activity_data_todo`, `user_id = assignee_id`), вирішення/зміна виконавця/вид «нотатка» його закривають; `f3d_dict()`.

### M-23 `td.zone.lock` — блокування (оренда) зони (F14, CD-31 Q6)

`_order = 'site_id, zone_uid'`. UNIQUE `(site_id, zone_uid)` («Зона вже заблокована»). Оренда **необов'язкова** й діє поверх `etag` (R-21), а не замість нього: правку відхиляє лише чужа діюча оренда (R-39).

| Поле | Тип | Параметри |
|---|---|---|
| `site_id` | Many2one `td.site` | `required`, `ondelete='cascade'`, `index` |
| `zone_uid` | Char(32) | `required`, `index`: uid зони-контуру (`td.slot` з `template='zone'`) або, поза зонами, uid самого об'єкта |
| `user_id` | Many2one `res.users` | `required`, `default=env.user`, `ondelete='cascade'` |
| `expires_at` | Datetime | `required`, `index` |
| `company_id` | related `site_id.company_id` | `store=True` |

Методи: `f3d_ttl()` (`td.constructor.lock_ttl_s`, 300 с), `f3d_heartbeat()` (`lock_heartbeat_s`, 60 с), `f3d_acquire(site, zone_uid)` → `(ok, lock)` (продовжує свою, чужу діючу не перехоплює; гонку двох викликів вирішує savepoint + UNIQUE), `f3d_release(site, zone_uid=None)`,
`f3d_purge(site)` (прострочені — прибираються при кожному зверненні, **крону немає**), `f3d_active(site)`, `f3d_assert_write/create` (R-39), `f3d_label`, `f3d_dict`. Читає `group_td_user`; пишуть технолог, комірник, інженер, менеджер (через API-23).

### M-24 `td.draft.mixin` (AbstractModel) — спільна поведінка чернеток

`_description = "Чернетка площадки: лічильник правок і права"`. Успадковують: `td.layer`, `td.slot`, `td.placement`, `td.check.config` (M-02, M-03, M-05, M-06) і `td.putaway.rule`, `td.replenish.rule` (M-18, M-19). Реалізує `create/write/unlink` з єдиним порядком:
`_f3d_normalized` (R-22) → `_f3d_check_*` (R-11; перевизначають моделі) → `_f3d_lease_*` (R-39; лише `td.slot`, `td.placement`) → `super()` → `_f3d_touch_sites` (R-21; контекст `f3d_no_touch` вимикає). Допоміжні: `_f3d_is_manager`, `_f3d_can_edit_layer(layer)`,
`_f3d_assert_layers` («Шар «%s» редагує: …»), `_f3d_assert_manager(what)`, `_f3d_etag()` (`write_date` у форматі `%Y-%m-%d %H:%M:%S.%f`).

### M-25 `td.site` — розширення (MERGE §3.3; доповнює M-01)

| Поле | Тип | Параметри |
|---|---|---|
| `warehouse_id` | Many2one `stock.warehouse` | `check_company`, `index`, `copy=False`, `ondelete='set null'`; склад Odoo площадки (конструктор склад **не створює**, F16) |
| `addr` | Json | `default=dict`, `copy=False`; адресація (R-25, схема R-22); порожньо = пресет `legacy` |
| `loc_tree` | Selection | `required`, `default='flat'`: `flat` (ім'я локації = повний код), `row`, `section` (CD-31 Q1: існуючим — плоско; нові — «ряд»; секції локаціями не робимо) |
| `depth_mode` | Selection | `required`, `default='level'`: `level` (останній рівень-локація — ярус), `cell` (комірка) |
| `sprinkler_height_m` | Float(10,3) | `0` — спринклерів немає (R-37) |
| `aisle_tech` | Char(32) | ключ техніки складу: `ключ` або `ключ:мін_м` (N-06); порожньо — «не перевіряти» |
| `parse_rules` | Json | `default=dict`, `copy=False`; правила розбору кодів і лоток «Не розміщено» (R-35, R-22) |
| `active_variant_id` | Many2one `td.layout.variant` | `copy=False`, `ondelete='set null'`, `index` |
| `wizard_state` | Json | `default=dict`, `copy=False`; стан майстра «З нуля» (F16-04), ≤ 256 КБ, вкладеність ≤ 8 |
| `odoo_baseline_id` | Many2one `ir.attachment` | база порівняння «Оновити з Odoo» (R-35) |
| `publish_copy_ack` | Boolean | «Копію БД підтверджено» (нагадування F02-10, R-31) |

`_check_addr`; `create/write` нормалізують `addr` (`_f3d_normalize_addr_vals`, помилка — `ValidationError("Адресація площадки: …")`); зміна `addr`/`depth_mode`/`loc_tree` через `_f3d_apply_addr(vals, renumber='new'|'all')` (R-25).

### M-26 `td.layer` — розширення

`items` — Json, `default=list`: об'єкти будівлі (колона, стіна, ворота, док, двері, офіс, зарядка техніки; R-37, схема R-22 `building.normalize_items`, ≤ 5000). Входить у `LAYER_CONTENT_FIELDS` (разом з `aisles`, `fire_paths`, `utilities`,
`underlay_*`): **проєктувальник із правом на шар** пише лише вміст шару, налаштування шару — тільки менеджер (R-11). Нормалізація при `create/write` і `_check` (`@api.constrains` включає `items`).

### M-27 `td.slot` — розширення

| Поле | Тип | Параметри |
|---|---|---|
| `template` | Selection | додано `floor_spot` («Місце на підлозі (одна локація)», R-26) |
| `type_id` | Many2one `td.slot.type` | `index`, `ondelete='restrict'`; `_check_type`: тип — не об'єкт будівлі, `type.template == slot.template` |
| `storage_category_id` | Many2one `stock.storage.category` | `ondelete='set null'`; діє на вкладені рівні, якщо там не задано своєї (R-28) |
| `removal_strategy_id` | Many2one `product.removal` | `ondelete='set null'`; так само |
| `function_id` | Many2one `td.term` | домен `term_type='zone_function'`; функція зони (10 значень) |
| `attr_ids` | Many2many `td.term` | таблиця `td_slot_attr_rel`; домен `term_type='zone_attr'` (температурний режим, небезпечні вантажі, цінне, довгомірне) |
| `temp_min_c`, `temp_max_c` | Float(5,1) | обидві `0` — режим не задано |
| `tech` | Char(32) | техніка зони (N-06); порожньо — як у площадки |
| `addr` | Json | `default=dict`; власна адресація місця/зони (порожньо — успадкувати) |
| `depth_mode` | Selection | `level`/`cell`; порожньо — успадкувати |

`overrides[code]` розширено ключами `usage` (`internal`/`view`) і `replenish_location` (R-28; `OVERRIDE_KEYS = disabled, max_load_kg, capacity, name, usage, replenish_location`). Службові методи адресації (`_f3d_addr_contexts`,
`_f3d_codes_map`, `_f3d_renumber`, `_f3d_recompute_counts`, контекст `f3d_no_renumber`) — R-25. Зміна `template`/`params`/`addr` перераховує `cell_count`, `footprint_*` і (якщо потрібно) переносить правки комірок на нові коди.

### M-28 `stock.location` — адресні номери (доповнює M-13)

`td_row`, `td_bay`, `td_level`, `td_pos` — Integer, `copy=False`, `readonly`, `td_row` з `index`; `0` — не задано; заміна `posx/posy/posz` Odoo 18 (їх у Odoo 19 немає). `@api.constrains` — від'ємні значення заборонені. Метод
`_f3d_address_vals(code, parts, addr, loc_tree)` лише **рахує** `{name, barcode, td_row, td_bay, td_level, td_pos}` (`addr.location_vals`, R-25); записує їх публікація (R-31).

### M-29 `td.layout.version` — розширення (доповнює M-07)

| Поле | Тип | Параметри |
|---|---|---|
| `kind` | Selection | `required`, `default='publish'`, `index`: `publish`, `checkpoint` (контрольна точка: знімок чернетки без змін в Odoo, N-03) |
| `variant_id` | Many2one `td.layout.variant` | `readonly`, `copy=False`, `ondelete='set null'`, `index` |
| `rolled_back_at`, `rolled_back_by_id` | Datetime, Many2one `res.users` | `readonly`, `copy=False` |
| `op_ids` | One2many `td.publish.op` | `readonly` |
| `metrics` | Json | `readonly`, `copy=False` |
| `op_count`, `can_rollback`, `rollback_reason` | Integer, Boolean, Char | `compute` (`_compute_rollback`, R-32) |

`action_rollback()` — відкат публікації (менеджер, з підтвердженням у формі). Контрольні точки не мають операцій у журналі й не є «діючою версією»; публікація тільки `kind='publish'`.

### M-30 `td.term`, `td.check.config` — нові значення

`td.term.term_type` розширено: `zone_function` («Функція зони»: 10 записів `receiving`, `quality`, `quarantine`, `storage`, `picking`, `packing`, `shipping`, `scrap`, `returns`, `wip` з кольором `#rrggbb`) і `zone_attr` («Атрибут зони»: `temp`, `hazmat`,
`valuable`, `long`); додано `color` (Char(7), `#rrggbb`) і `value` (Char; для атрибута — значення за замовчуванням або підказка). Довідники сіються `data/td_term_data.xml` (xml-id; міграція `19.0.1.3.0/pre-migrate.py` прив'язує наявні терміни). `td.slot_type`-терміни
доповнено `floor_spot`.

`td.check.config.check_key` розширено: `inside`, `aisle_width`, `height`, `cell_load`, `putaway_fit`, `code_conflict` (R-27, R-29, R-37). Рядки налаштувань для нових перевірок **не створюються автоматично** при створенні площадки (її `CHECK_DEFAULTS` лишилися
7, R-04): ядро створює їх при першому вмиканні в панелях «Ємність» і «Будівля» (`td.check.config` `create` через API-04), і лише тоді `run_checks` виконує перевірку (R-41).

### M-31 `td.publish.wizard`, `td.publish.wizard.line` — розширення (доповнює M-08, M-09)

`td.publish.wizard.line`: `kind` + `move` («Буде переміщено»), `rename`, `attrs`; `res_model` + `stock.warehouse.orderpoint`, `stock.putaway.rule` (`ondelete='cascade'` для доданих значень); нові поля: `depends_code` (Char, код рядка,
який має бути застосований раніше), `scope_uid` (Char(32), uid місця/зони рядка), `zone_uid` (Char(32), зона, що містить комірку; для застосування частинами), `before` (Json, прежні значення), `flags` (Char: «stock» — є залишок, «barcode_busy» — штрихкод зайнятий та ін.).

`td.publish.wizard`: `scope_slot_id` (Many2one `td.slot`, область застосування: зона чи ряд, батьки додаються самі), `scope_slot_ids` (compute), `create_line_ids`/`move_line_ids`/`rename_line_ids`/`attrs_line_ids` (One2many з доменом за `kind`),
лічильники `n_move`, `n_rename`, `n_attrs`, `n_blocked` (`n_update` тепер рахує `update`+`move`+`rename`+`attrs`), `copy_reminder` (compute: перше застосування площадки — журнал порожній — і `publish_copy_ack=False`), `copy_ack` («Більше не нагадувати»).
Кнопки: `action_select_scope` («Лише обране»), `action_select_all`, `action_select_none`, `action_open_log` («Журнал публікацій»); `action_confirm` передає в `apply_plan` також `excluded` (кортежі `(res_model, code, kind)` невибраних рядків) і `scope`; після підтвердження записує `site.publish_copy_ack`.

## 3. Представлення й меню

Усі форми: `<form>` без `attrs`, кнопки з `invisible="…"`; списки — `<list>`; групи вказані в `groups=`. JSON-поля (`fields.Json`) показуються штатним віджетом `json`; точне редагування — у конструкторі.

| V | XML-id (суфікси `view_f3d_…`) | Тип / модель | Структура |
|---|---|---|---|
| V-01 | `site_form`, `site_list`, `site_search` | form/list/search `td.site` | Шапка: кнопки «Відкрити в конструкторі» (`action_open_constructor`), «Опублікувати…» (`action_publish_wizard`, `groups=group_td_constructor_manager`, `invisible="not has_changes"`). Поля: `name`, `code`, `company_id` (`groups=base.group_multi_company`), `building_*_m`, `column_step_*_m`, `default_parent_location_id`, `seed_key` (readonly). Кнопки-лічильники: шари, місця, розміщення, версії. Вкладки: «Шари» (list `layer_ids`: `name`, `kind`, `elevation_m`), «Перевірки» (editable list `check_config_ids`: `check_key` readonly, `enabled`, `mode`, `params`), «Версії» (readonly list). Рядок стану: «Чернетка · змінено N» (`draft_changes`), «Діюча: vN» |
| V-02 | `layer_form`, `layer_list` | form/list `td.layer` | Групи: «Основне» (`name`, `kind`, `site_id`, `elevation_m`, `grid_step_m`, `aisle_width_m`, `max_floor_load_kn_m2`), «Вигляд» (`color` віджет `color`, `opacity`, `style`, `visible`), «Права» (`edit_group_ids` `many2many_tags`, `domain=[('privilege_id','=',%(privilege_td_constructor)d)]`), «Типи місць» (`allowed_slot_type_ids` tags), вкладки «Контур» (`bounds`), «Проходи» (`aisles`), «Пожежні проходи» (`fire_paths`), «Мережі» (`utilities`), «Підкладка» (`underlay_attachment_id`, `underlay_format`, `underlay_status`, `underlay_params`). Поля, окрім `layer_content`, — `readonly="not is_manager"` (`is_manager` — `compute`, `has_group` менеджера) |
| V-03 | `slot_form`, `slot_list`, `slot_search` | `td.slot` | Форма: `template`, `code_prefix`, `layer_id`, `x_m`, `y_m`, `rotation`, `parent_location_id`, `params`, `overrides`, `cell_count`, вкладка «Комірки» (`cells_html`). Пошук: `code_prefix`, `layer_id`, групування за шаром/шаблоном. Редагування — рядок JSON (CD-03: точні числа; обидві правки пишуть ті самі записи) |
| V-04 | `equipment_variant_form`, `_list`, `_kanban`, `_search` | `td.equipment.variant` | **W3.** Форма: ліворуч `name`, `passport_id`, `category`, блок «Габарити й обслуговування» (`length_mm`, `width_mm`, `height_mm`, 4 поля `service_*_mm`), «Орієнтація» (`front_side`, `anchor`, `rotation_mode`), «Де можна ставити» (`allowed_layer_kind_ids`, `allowed_slot_type_ids` tags), «Підключення» (`utilities`, `power_kw`, `panel`), «Маса» (`weight_kg`, `floor_load_kn_m2`), `create_workcenter`; праворуч — віджет `<field name="model_glb_id" widget="f3d_model_preview"/>` і `<widget name="f3d_model_upload"/>` (статус, одиниці, вісь, кнопка «Підставити габарити з моделі», «Спростити», «Видалити модель»), `model_warning` (`alert`), `model_status` (`statusbar`-бейдж). Список: `name`, `passport_id`, `category`, `L×W×H`, `power_kw`, `model_status` (декорація `danger` для `error`, `warning` для `pending_conversion`). Канбан: `image`, `name`, габарит, статус. Діалог із конструктора відкривається `act_window` `target='new'` |
| V-05 | `placement_form`, `placement_list` | `td.placement` | `code`, `name`, `layer_id`, `variant_id`, `slot_id`, `cell_code`, `x_m`, `y_m`, `rotation`, `equipment_id` і `workcenter_id` (readonly), кнопка «Показати в 3D» (`action_show_in_3d`, `invisible="not equipment_id"`) |
| V-06 | `check_config_list` | editable list `td.check.config` | `check_key` (readonly), `enabled`, `mode`, `params` |
| V-07 | `layout_version_list`, `_form` | `td.layout.version` | Список: `n`, `published_at`, `published_by_id`, `note`, `state`, лічильники. Форма (readonly): шапка кнопки «Повернути чернетку до цієї версії» (`action_restore_draft`, `invisible="state == 'active' and site_id.draft_base_version_id == id"`, менеджер, з підтвердженням `confirm="…"`), «Завантажити знімок»; вкладка «Звіт» (`report`) |
| V-08 | `publish_wizard_form` | form `td.publish.wizard` | Рядок підсумку «Буде створено: N · Буде оновлено: M · Пропонуємо архівувати: K · Без змін: U»; `alert` червоний при `n_block>0` («Публікацію заборонено: …»), жовтий при `n_warn>0`. Вкладки: «Буде створено / оновлено» (list `line_ids` з `kind != 'archive'`: `res_model`, `code`, `name`, `changes`, `selected`), «Пропонуємо архівувати (лише пропозиція, нічого не видаляється)» (`kind == 'archive'`: `selected` редагований, за замовчуванням не відмічений, `blocked_reason`), «Зауваження перевірок» (`issue_ids`). Поле `note`. Кнопки: «Підтвердити й опублікувати» (`action_confirm`, `class="btn-primary"`, `invisible="not can_publish"`), «Скасувати» (`special="cancel"`) |
| V-09 | `term_list` | editable list `td.term` | `term_type`, `key`, `name`, `sequence` |
| V-10 | `passport_form_inherit` | inherit `td.equipment.passport` (base `view_td_equipment_passport_form`) | `td_category` після `role`; вкладка «Варіанти» (list `variant_ids`: `name`, `L×W×H`, `model_status`), кнопка-лічильник `variant_count` |
| V-11 | `stock_location_form_inherit` | inherit `stock.location` | readonly `td_site_id`, `td_slot_uid` у групі «Завод 3D» (після `td_code`) |
| V-12 | `maintenance_equipment_form_inherit` | inherit `maintenance.equipment` | readonly `td_site_id`, `td_placement_uid` у вкладці «Завод 3D» |
| V-13 | `td_menus.xml` | меню й дії | нижче |

Дії й меню (DEC-01, DEC-19; `groups=td_factory3d.group_td_user`, якщо не сказано):

| XML-id | Назва | Батько | sequence | Дія |
|---|---|---|---|---|
| `menu_td_constructor` | Конструктор | `td_factory3d.menu_td_root` | 12 | `action_td_constructor` (`ir.actions.client`, `tag='f3d_constructor'`, `name='Конструктор'`, `target='current'`, `params={}`) |
| `menu_td_constructor_plan` | Планування | `td_factory3d.menu_td_root` | 14 | — (папка) |
| `menu_td_site` | Площадки | `menu_td_constructor_plan` | 10 | `action_td_site` (`list,form`) |
| `menu_td_layer` | Шари | `menu_td_constructor_plan` | 20 | `action_td_layer` (`list,form`; контекст `search_default_group_site`) |
| `menu_td_variant` | Каталог варіантів | `menu_td_constructor_plan` | 30 | `action_td_equipment_variant` (`kanban,list,form`) |
| `menu_td_version` | Версії планування | `menu_td_constructor_plan` | 40 | `action_td_layout_version` (`list,form`) |
| `menu_td_constructor_terms` | Довідники конструктора | `td_factory3d.menu_td_config` | 14 | `action_td_term` (`groups=group_td_constructor_manager`) |

Дія майстра `action_f3d_publish_wizard` — `target='new'`, створюється з `site.action_publish_wizard()`.

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

Скорочення груп: `U`=`td_factory3d.group_td_user`, `M`=`group_td_constructor_manager`, `T`=`…_technologist`, `S`=`…_storekeeper`, `E`=`…_engineer`, `A`=`td_factory3d.group_td_admin` (у файлі — повні xml-id).

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_td_site_u,td.site user,model_td_site,U,1,0,0,0
access_td_site_m,td.site manager,model_td_site,M,1,1,1,1
access_td_layer_u,td.layer user,model_td_layer,U,1,0,0,0
access_td_layer_t,td.layer technologist,model_td_layer,T,1,1,0,0
access_td_layer_s,td.layer storekeeper,model_td_layer,S,1,1,0,0
access_td_layer_e,td.layer engineer,model_td_layer,E,1,1,0,0
access_td_layer_m,td.layer manager,model_td_layer,M,1,1,1,1
access_td_slot_u,td.slot user,model_td_slot,U,1,0,0,0
access_td_slot_t,td.slot technologist,model_td_slot,T,1,1,1,1
access_td_slot_s,td.slot storekeeper,model_td_slot,S,1,1,1,1
access_td_slot_e,td.slot engineer,model_td_slot,E,1,1,1,1
access_td_slot_m,td.slot manager,model_td_slot,M,1,1,1,1
access_td_placement_u,td.placement user,model_td_placement,U,1,0,0,0
access_td_placement_t,td.placement technologist,model_td_placement,T,1,1,1,1
access_td_placement_s,td.placement storekeeper,model_td_placement,S,1,1,1,1
access_td_placement_e,td.placement engineer,model_td_placement,E,1,1,1,1
access_td_placement_m,td.placement manager,model_td_placement,M,1,1,1,1
access_td_variant_u,td.equipment.variant user,model_td_equipment_variant,U,1,0,0,0
access_td_variant_t,td.equipment.variant technologist,model_td_equipment_variant,T,1,1,1,0
access_td_variant_m,td.equipment.variant manager,model_td_equipment_variant,M,1,1,1,1
access_td_check_config_u,td.check.config user,model_td_check_config,U,1,0,0,0
access_td_check_config_m,td.check.config manager,model_td_check_config,M,1,1,1,1
access_td_layout_version_u,td.layout.version user,model_td_layout_version,U,1,0,0,0
access_td_layout_version_m,td.layout.version manager,model_td_layout_version,M,1,1,0,0
access_td_layout_version_a,td.layout.version admin,model_td_layout_version,A,1,1,0,1
access_td_term_u,td.term user,model_td_term,U,1,0,0,0
access_td_term_m,td.term manager,model_td_term,M,1,1,1,0
access_td_term_a,td.term admin,model_td_term,A,1,1,1,1
access_td_publish_wizard_m,td.publish.wizard manager,model_td_publish_wizard,M,1,1,1,1
access_td_publish_wizard_line_m,td.publish.wizard.line manager,model_td_publish_wizard_line,M,1,1,1,1
access_td_publish_wizard_issue_m,td.publish.wizard.issue manager,model_td_publish_wizard_issue,M,1,1,1,1
```

### 4.2 Групи (`security/td_constructor_security.xml`)

Привілей `privilege_td_constructor` («Конструктор», категорія `td_factory3d.module_category_factory3d`, `sequence=20`) і групи (CB-10, X-19):

| XML-id | Назва | `implied_ids` | Призначення (CD-02) |
|---|---|---|---|
| `group_td_constructor_technologist` | Конструктор: технолог | `td_factory3d.group_td_user` | обладнання: розміщення на шарах, де він у `edit_group_ids`; варіанти каталогу |
| `group_td_constructor_storekeeper` | Конструктор: комірник | `td_factory3d.group_td_user`, `stock.group_stock_user` | стелажі й комірки на «своїх» шарах |
| `group_td_constructor_engineer` | Конструктор: інженер | `td_factory3d.group_td_user` | мережі: `aisles`, `fire_paths`, `utilities`, підкладка шару, розміщення щитів |
| `group_td_constructor_manager` | Конструктор: менеджер | `technologist`, `storekeeper`, `engineer`, `td_factory3d.group_td_manager` | усі шари, налаштування, публікація, версії |

`td_factory3d.group_td_admin` отримує `implied_ids += group_td_constructor_manager` (запис `<record id="td_factory3d.group_td_admin">`). Користувач із групою `td_factory3d.group_td_user` без ролей конструктора лише читає.

### 4.3 Record rules

| XML-id | Модель | Групи | Домен | perm |
|---|---|---|---|---|
| `rule_td_site_company`, `rule_td_layer_company`, `rule_td_slot_company`, `rule_td_placement_company`, `rule_td_check_config_company`, `rule_td_version_company` | `td.site`, `.layer`, `.slot`, `.placement`, `.check.config`, `.layout.version` | глобальне | `['|', ('company_id','=',False), ('company_id','in',company_ids)]` | усі |
| `rule_td_slot_manager`, `rule_td_placement_manager`, `rule_td_layer_manager` | slot, placement, layer | `M` | `[(1,'=',1)]` | write, create, unlink (read=0) |
| `rule_td_slot_role`, `rule_td_placement_role` | slot, placement | `T`, `S`, `E` | `[('layer_id.edit_group_ids','in',user.all_group_ids.ids)]` | write, create, unlink (read=0) |
| `rule_td_layer_role` | layer | `T`, `S`, `E` | `[('edit_group_ids','in',user.all_group_ids.ids)]` | write (read=0, create=0, unlink=0) |

Правило групи з `perm_read=0` не обмежує читання: читають усі з `group_td_user` (CD-02: чужі шари видно, не правляться). Менеджер імпліцитно входить у `T/S/E`, тож домен ролі для нього теж істинний, коли група в `edit_group_ids` є, а `rule_*_manager` покриває шари з порожнім `edit_group_ids` (R-11).

### 4.4 Серверна перевірка поверх правил (R-11)

Правила ORM — перший бар'єр; другий — `_f3d_check_edit()` у `create/write/unlink` slot/placement/layer (пропускається при `env.su`; тексти уніфіковані): `AccessError("Шар «%s» редагує %s.")`. Публікація, відновлення версії, створення площадки, зміна `edit_group_ids`, `check.config` — лише `has_group('group_td_constructor_manager')`.
Сервіс публікації працює під `sudo()` + `with_company(site.company_id)` лише всередині `services.publish.apply_plan` **після** явної перевірки групи менеджера й стоп-крана `publish_enabled` (DEC-11, DEC-17); збереження чернетки (API-04) виконується від імені користувача **без** `sudo`.

## 5. Дані

### 5.1 XML-дані й параметри

`data/td_term_data.xml` (`noupdate="0"`): 12 записів `td.term` з xml-id `term_layer_kind_<key>` (`building`, `storage`, `production`, `engineering`, `yard`, `custom`; назви — як у M-02) і `term_slot_type_<key>` (`pallet_rack`, `cantilever`, `shelf`, `floor_stack`, `machine_spot`, `zone`; назви — як у M-03).

`data/params.xml` (`noupdate="1"`) створює 6 ключів `ir.config_parameter` (`max_model_mb` … `convert_server_enabled`); `publish_enabled` і `seed_report` створює `post_init_hook` (кроки 1 і 6, §5.2) — разом 8 ключів `td.constructor.*`:

| Ключ | Значення | Призначення |
|---|---|---|
| `td.constructor.max_model_mb` | `20` | ліміт файла моделі (CD-17), R-18 |
| `td.constructor.max_triangles` | `50000` | поріг попередження (CD-17), R-18 |
| `td.constructor.autosave_ms` | `1500` | затримка автозбереження чернетки клієнтом |
| `td.constructor.eps_mm` | `1` | допуск геометрії, R-03 |
| `td.constructor.reach_default_m` | `15` | `utility_reach.max_m` за замовчуванням (Q-10) |
| `td.constructor.convert_server_enabled` | `True` | чи пробувати серверні конвертери (R-20) |
| `td.constructor.publish_enabled` | `True` на `test`, `False` на `prod` | стоп-кран публікації (DEC-17); значення за замовчуванням ставить хук з `td.base.environment` (CB-10) |
| `td.constructor.seed_report` | JSON | звіт хука seed (R-24) |

`data/td_generic_catalog.xml` (`noupdate="1"`; значення — **ПРИПУЩЕННЯ**: типові габарити, не з макета, Q-11): 4 паспорти base `role` ∈ {`generic_machine`, `generic_rack`, `generic_forklift`, `generic_panel`}, `manufacturer='Типовий'`, `model` = «Верстат (умовний)» / «Стелаж (умовний)» / «Навантажувач (умовний)» / «Шафа/щит (умовний)», `td_category` = `machine`/`rack`/`forklift`/`panel`, і по одному варіанту «Стандарт»: верстат 3000×1500×1800, сервіс 1000/500/500/500 (фронт/зад/ліво/право), 15 кВт, 3000 кг, `utilities=[{kind:'electric',x_mm:-1400,y_mm:0,z_mm:500}]`, `create_workcenter=True`; стелаж 2700×1100×6000, сервіс 0; навантажувач 2600×1200×2200, сервіс 1500/0/0/0, 4500 кг; шафа 800×400×2000, сервіс 1000/0/0/0. Ці паспорти потрібні порожній площадці (CD-24) і не належать 93 паспортам макета base.

### 5.2 Seed: `data/seed_site.json` і `post_init_hook` (DEC-13)

`seed_site.json` — копія вбудованого JSON прототипу (`build/constructor/PROTOTYPE.md` §«Дані»: з `td_viewer3d/static/data/model_static.json` ключ `layout` і з `plant/layout.py`, `plant/equipment_specs.json`). Цільова схема (якщо у прототипі інша — адаптер `hooks/seed.py:_normalize_seed`):

```
{ "meta": {"name": "Меблеве підприємство", "seed_key": "main_demo", "schema": 1,
           "counts": {"layers": n, "slots": n, "cells": n, "placements": n, "variants": n}},
  "site": {"building": {"length": 150, "width": 72, "height": 9}, "column_grid": {"step_x": 6, "step_y": 6}, "default_parent": "WH/Stock"},
  "layers": [{"uid","name","kind","elevation","grid_step","aisle_width","max_floor_load","bounds","slot_types":[..],"edit_roles":["storekeeper"],
              "color","opacity","aisles":[..],"fire_paths":[..],"utilities":[..]}],
  "slots": [{"uid","layer","template","code_prefix","x","y","rotation","params":{..},"overrides":{..},"parent":"<повне ім'я батьківської локації|null>"}],
  "variants": [{"key","passport_role","name","length","width","height","service":{"front","back","left","right"},"rotations","layer_kinds":[..],"slot_types":[..],
                "utilities":[..],"power_kw","panel","weight_kg","floor_load","anchor","front_side","create_workcenter"}],
  "placements": [{"uid","layer","variant":"<key>","slot":"<uid|null>","x","y","rotation","code","name"}] }
```
Відповідність полів прототипу: метри в `layers/slots/placements`, `variants.length/width/height` — мм (у прототипі «мм у формі, м у сцені» — хук ділить/множить, якщо значення у метрах: евристика `length < 50 → ×1000`). Очікувані кількості береться з `meta.counts`; відомі ключові факти макета: ряди FG-R1…FG-R5 по 72 комірки (18 пролітів × 4 яруси) = 360 локацій `FG-*` (base §1.1), 96 `RCK-*`, 144 `FUR-*` (`FUR-R1-S02-L3` → шаблон `shelf`), станки з `plant/layout.py:MACHINES` (кількість — з `meta.counts.placements`).

`post_init_hook(env)` — порядок, кожен крок ідемпотентний, усе в транзакції установки (R-24):
1. `params`: `publish_enabled` за `td.base.environment`.
2. `categories`: `td_category` у паспортів base за таблицею нижче (лише де `other`/порожньо — не перезаписуємо ручні значення).
3. `seed`: якщо `td.site` з `seed_key='main_demo'` немає — створити площадку, шари, варіанти (паспорт за `passport_role`; немає → пропуск і запис у звіт), місця, розміщення, `check.config` за R-04.
4. `link`: для кожної комірки місць seed знайти `stock.location` (R-12 збіг: `td_code`, потім `barcode`), виставити `td_site_id`/`td_slot_uid`; для кожного розміщення — `maintenance.equipment` за `td_code` → `equipment_id`, `td_site_id`, `td_placement_uid`; `mrp.workcenter` за `td_code`/`code`. **Нічого не створюється й не змінюється, крім цих службових полів.**
5. `baseline`: версія v1 «Імпорт із макета» (`is_seed=True`, `published_by`=OdooBot) зі знімком; `site.active_version_id`, `published_rev=draft_rev`, `draft_changes=0`. Непов'язані комірки/обладнання створить перша публікація.
6. `report`: JSON `{site_id, created: {layers, slots, cells, placements, variants}, linked: {locations, equipment, workcenters}, unlinked: {locations: [коди], equipment: [коди]}, skipped_variants: [role]}` у `td.constructor.seed_report`.
Повторний запуск: кроки 2, 4, 6 виконуються знову (звіряються зв'язки), кроки 3 і 5 пропускаються (`seed_key` існує) — дублікатів немає, правки користувача не перезаписуються.

Таблиця «роль паспорта → категорія» (джерело ролей — `td_factory3d/data/td.equipment.passport.csv`, 93 ролі; решта → `other`):
`machine`: beam_saw, beam_saw_book, sliding_table_saw, vertical_panel_saw, edgebander, edgebander_laser, nesting_cnc, ptp_cnc, throughfeed_drilling, dowel_inserting, hinge_insertion, wide_belt_sander, membrane_press, glue_spray_booth, manual_spray_booth, automatic_spraying, uv_line, uv_oven, drying, box_machine, case_clamp_auto, case_clamp_manual, shrink_line, strapping, stretch_wrapper, briquetting_press, compressor, dust_extraction;
`rack`: board_rack, board_storage, highbay_rack, server_rack; `forklift`: forklift, board_forklift, tugger; `panel`: main_switchboard, busbar_main, busbar_dist, substation, acb, tapoff, pfc, ats, lighting_control; `robot`: robot_return, sorting_cell; `conveyor`: — (немає в макеті).

### 5.3 `uninstall_hook(env)`

Видаляє лише власні `ir.config_parameter` `td.constructor.*`. Записи `stock.location`/`maintenance.equipment`/`mrp.workcenter`, створені публікацією, **не видаляються** (стовпці `td_site_id` зникають разом із моделлю); знімки версій (`ir.attachment`) лишаються.

## 6. Крони й фонові процеси

Немає. Конвертація STEP/IGES/IFC (R-20) — синхронна при завантаженні (API-09) із таймаутом `convert_timeout_s=60`; довші — статус `pending_conversion` і ручний запуск кнопкою «Спробувати перетворити» (`variant.action_retry_convert()`, технолог/менеджер). Окремий cron не створюється (Q-02).

## 7. HTTP/JSON API

Префікс `/f3d/constructor`. Усі маршрути `auth="user"`; JSON-RPC (`type="jsonrpc"`, `methods=["POST"]`) повертають `{ok: true, …}` або очікувану помилку `{ok: false, code, message, …}` (HTTP 200); неочікувані помилки — стандартний JSON-RPC error. Права — від імені користувача (без `sudo`), крім API-07. Усі повідомлення — українською. Кожен виклик, що змінює дані, — одна транзакція.

| API | Метод, маршрут | Тіло (JSON) | Відповідь (`ok: true`) | Коди помилок (`code`) |
|---|---|---|---|---|
| API-01 | POST `/f3d/constructor/sites` | `{}` | `{sites: [{id, name, code, company_id, seed: bool, active_version: {id, n}|null, draft_changes, has_changes, can_edit: bool}]}` — лише площадки компаній користувача | — |
| API-02 | POST `/f3d/constructor/site/create` | `{name, code, building?: {l,w,h}}` | `{site_id}`; створює порожню площадку (R-23) | `rights` (не менеджер), `validation` |
| API-03 | POST `/f3d/constructor/load` | `{site_id}` | див. нижче | `not_found`, `rights` |
| API-04 | POST `/f3d/constructor/save` | `{site_id, ops: [...]}` | `{rev, draft_changes, has_changes, id_map: {"<tmp>": id}, etags: {"<model>:<id>": "<write_date>"}}` | `conflict`, `rights`, `validation`, `not_found`, `too_many` |
| API-05 | POST `/f3d/constructor/validate` | `{site_id, layer_id?}` | `{issues: [issue], summary: {block, warn}}`; `issue = {check, severity, layer_id, codes: [..], message}` | `not_found` |
| API-06 | POST `/f3d/constructor/publish/preview` | `{site_id}` | `{action: <act_window майстра>, summary: {create, update, archive, unchanged, warn, block}}`; створює `td.publish.wizard` (нічого в Odoo не змінює) | `rights`, `no_changes`, `disabled` |
| API-07 | POST `/f3d/constructor/publish` | `{site_id, note?, archive_codes?: [..], confirm: true}` | `{version: {id, n}, created, updated, archived, warnings: [issue]}`; без `confirm: true` — `validation` | `rights`, `blocked` (з `issues`), `no_changes`, `disabled`, `conflict_codes`, `rollback` |
| API-08 | POST `/f3d/constructor/version/restore` | `{version_id}` | `{site_id, rev, draft_changes}` | `rights`, `not_found` |
| API-09 | POST (multipart) `/f3d/constructor/model/upload` | поля форми: `variant_id`, `csrf_token`, `original` (файл), `glb` (файл, необов'язково), `meta` (JSON-рядок) | `{status, meta, glb_url, original_url, message}` | `rights`, `too_large` (HTTP 413), `unsupported_format`, `bad_glb`, `not_found` |
| API-10 | GET `/f3d/constructor/model/<int:variant_id>/<string:kind>` (`kind` ∈ `glb`, `original`) | — | потік файла, `Content-Type: model/gltf-binary` або `application/octet-stream`, `ETag`, `Cache-Control: private, max-age=3600`; доступ — читання варіанта | `404`, `403` |

**API-03 `load`** — повний стан для редактора:
`{site: {id,name,code,building:{length,width,height},column_grid:{step_x,step_y},default_parent_location: {id,name}|null,active_version,draft_base_version,draft_rev,draft_changes,has_changes,settings:{autosave_ms,max_model_mb,max_triangles,eps_mm,reach_default_m,publish_enabled}},
layers: [{id,uid,name,kind,sequence,elevation,grid_step,aisle_width,max_floor_load,bounds,slot_types:[key],edit_groups:[{id,name,role}],color,opacity,style,visible,aisles,fire_paths,utilities,underlay:{url,format,status,params}|null,etag}],
slots: [{id,uid,layer_id,template,code_prefix,x,y,rotation,params,overrides,parent_location_id,cell_count,etag}],
placements: [{id,uid,layer_id,variant_id,slot_id,cell_code,x,y,rotation,code,name,equipment: {id,name}|null,etag}],
catalog: [{passport_id,name,role,manufacturer,model,category,variants:[{id,name,length,width,height,service:{front,back,left,right},rotations,layer_kinds:[key],slot_types:[key],utilities,power_kw,panel,weight_kg,floor_load,anchor,front_side,create_workcenter,model:{status,meta,glb_url}|null,etag}]}],
checks: [{check,enabled,mode,params}], versions: [{id,n,published_at,by,note,state,counts}] (останні 50),
rights: {is_manager, roles:[technologist|storekeeper|engineer|manager], editable_layer_ids:[id], can_publish, can_edit_catalog}}`. Одиниці: метри (шари/місця/розміщення), мм (варіанти). Розмір для seed ≈ 250 КБ JSON; ліміт відповіді — 2 МБ.

**API-04 `save`** — `ops[i] = {model, op, id?, tmp?, etag?, vals}`; `model` ∈ {`td.layer`, `td.slot`, `td.placement`, `td.check.config`}; `op` ∈ {`create` (з `tmp`), `write` (`id`, `etag`), `unlink` (`id`, `etag`)}. У `vals` посилання на нові записи — `"@<tmp>"`. Ліміт — 500 операцій і 1 МБ на запит. Виконується атомарно у порядку списку: перша помилка скасовує всі (`{ok:false, code, message, op_index, current?}`; для `conflict` — `current` = актуальні значення запису). Конфлікт: `etag` ≠ `write_date` запису (R-21). `layer`: `create`/`unlink` лише менеджер (інакше `rights`). Приклад:

```json
{"site_id": 1, "ops": [
 {"model": "td.slot", "op": "create", "tmp": "t1", "vals": {"uid": "a1f…", "layer_id": 5, "template": "pallet_rack", "code_prefix": "FG-R7",
   "x_m": 40.0, "y_m": 10.0, "rotation": 0, "params": {"bays": 18, "levels": 4, "bay_width": 2.7, "depth": 1.1, "level_height": 1.5, "positions_per_bay": 3, "max_load_kg": 1000}}},
 {"model": "td.placement", "op": "write", "id": 88, "etag": "2026-10-17 18:03:11.123456", "vals": {"x_m": 12.5, "rotation": 90}}]}
```
Відповідь: `{"ok": true, "rev": 14, "draft_changes": 3, "has_changes": true, "id_map": {"t1": 120}, "etags": {"td.slot:120": "…", "td.placement:88": "…"}}`.

**API-07 `publish`** — програмний еквівалент `action_confirm` майстра (тести, автоматизація): будує план (R-12), валідує (R-04…R-10), застосовує вибрані `archive_codes` (R-13), створює версію (R-14). Ідемпотентність: повторний виклик без змін → `no_changes`, нічого не створює. Коди: `disabled` (`publish_enabled=False`), `blocked` (є `block`-зауваження), `conflict_codes` (код зайнятий записом, що не належить площадці), `rollback` (непередбачена помилка; транзакція скасована, версії немає).
**API-09** — перевірки: розмір `original`/`glb` ≤ `max_model_mb` (R-18), розширення з переліку R-15 (`.skp` відхиляється), права `T`/`M`; `glb` проходить `glb_meta` (R-19); `meta` від клієнта — довідково, трикутники й bbox перераховуються сервером; запис — `variant._f3d_set_model(...)`; для `step/stp/iges/igs/ifc` — `status='pending_conversion'` і виклик `_f3d_convert_model()`. Ліміти: 1 завантаження на варіант за раз (блокування рядка варіанта `FOR UPDATE NOWAIT`).

## 8. Клієнтська й сервісна частини

Колектора й емулятора немає. Нижче — склад клієнтського коду й контракти між воркерами (ARCH §6). Кожен файл — ES-модуль `/** @odoo-module */`, імпорти `@td_constructor/<шлях>`; Odoo-сервіси: `orm`, `rpc`, `notification`, `action`, `dialog`.

### 8.1 Бібліотеки (DEC-06)

- **three.js — не вендориться ще раз.** Усе, що потребує `THREE`, імпортує `/td_viewer3d/static/lib/three/three-bundle.esm.js` (r160; експорти `THREE`, `GLTFLoader`, `OrbitControls`, `CSS2DObject`, `CSS2DRenderer`, `RoomEnvironment`). Єдиний спосіб — `loadThree()` у `static/src/{editor,model}/three.js` (динамічний `import()` за URL, як `core.js` переглядача; по одному невеликому файлу на воркера, без спільного коду).
- **Завантажувачі й експортер** (`OBJLoader`, `MTLLoader`, `STLLoader`, `FBXLoader`, `ColladaLoader`, `ThreeMFLoader`, `GLTFExporter`, `fflate`) відсутні в бандлі переглядача → W3 збирає `static/lib/f3d-loaders/f3d-loaders.esm.js` з `three@0.160.0/examples/jsm` скриптом `tools/build_loaders.mjs` (esbuild; `three` замінюється shim-модулем, що читає `globalThis.__F3D_THREE__`; `loadThree()` кладе туди `THREE` перед динамічним імпортом бандла). Файл комітиться, на сервері нічого не збирається. Заборонено: CDN, `<script src="http…">`, `fetch` на зовнішні адреси (DoD-перевірка — grep, AC-05).
- **dxf-parser@1.1.2** (UMD, глобал `DxfParser`) — `static/lib/dxf-parser/dxf-parser.min.js`, лінивий `loadJS` (W2).

### 8.2 W2: клієнтська дія `f3d_constructor` (DEC-08)

`static/src/action/constructor_action.js`: `registry.category("actions").add("f3d_constructor", F3dConstructorAction)`; `static template = "td_constructor.ConstructorAction"`; `props = {...standardActionServiceProps}`; монтує редактор у `t-ref="root"` (патерн `td_viewer3d/static/src/action/viewer_action.js`: `onMounted` → ініціалізація, `onWillUnmount` → `dispose()` всіх геометрій/матеріалів/рендерера, зупинка таймерів). `params.site_id` (необов'язково) вибирає площадку; інакше остання з `localStorage["f3d_constructor_site"]` або перша з API-01.

Редактор — **порт прототипу** (той самий JS: сцена, шари, шаблони, каталог, перетягування з прив'язкою до сітки, перевірки, підкладка, лінійка, діалоги), розрізаний на модулі `static/src/editor/`: `scene.js` (сцена, камера, рендер на вимогу, InstancedMesh для комірок), `cells.js` (дзеркало `services/cells.py`, R-01), `geometry.js` (дзеркало R-02/R-03), `checks.js` (R-04…R-10), `dxf.js`, `panels_layers.js`, `panels_slots.js`, `panels_catalog.js`, `panels_props.js`, `dialogs.js` (власні діалоги, **без** `alert/confirm/prompt`; публікація — майстер Odoo), `roles.js`, `store.js`. Правила порту: (1) UMD-глобали `THREE.*`, `DxfParser` замінюються імпортами з §8.1; (2) `window.claude.use("db"/"user")`, IndexedDB, localStorage-сховище і «пісочний» диспетчер ролей видаляються; (3) адаптер `store` — клас `OdooStore` нижче; (4) інтерфейс українською, ті ж тексти; (5) без CDN і Google Fonts (системні шрифти).

`OdooStore` (`store.js`) — єдине місце виклику API:

| Метод | Дія |
|---|---|
| `listSites()` / `createSite({name, code})` | API-01 / API-02 |
| `loadSite(id)` | API-03; повертає стан у структурі прототипу (`sites, layers, slots, placements, catalog, versions, settings`) + `rights`, `etags` |
| `queue(op)` | додає операцію API-04 (`create` з `tmp`, `write` — лише змінені поля, `unlink`); зливає операції над тим самим записом; автозбереження через `settings.autosave_ms` і при закритті сторінки; індикатор «Збережено / Зберігаємо… / Помилка» |
| `flush()` | API-04; застосовує `id_map` (заміна `tmp`→`id`) та `etags`; при `conflict` викликає `onConflict(current)` → діалог «Запис змінив інший користувач: [залишити моє] [взяти серверне]» |
| `validate(siteId, layerId?)` | API-05 — кнопка «Перевірити на сервері» (результат зливається з локальними зауваженнями) |
| `publishPreview(siteId)` | `flush()` → API-06 → `action.doAction(result.action, {onClose: reload})` (майстер V-08) |
| `restoreVersion(versionId)` | API-08 → `loadSite` |

Ролі (`roles.js`): права з `rights` (не з перемикача). Шар редагований, якщо `layer.id ∈ rights.editable_layer_ids`; інакше всі поля шару й об'єкти — `readonly`, підказка «редагує Комірник» (ім'я ролі з `edit_groups`). Менеджеру доступний режим «Переглянути як роль» (лише UI; сервер усе одно застосовує права). Каталог: кнопка «Змінити варіант» відкриває форму V-04 в діалозі `action.doAction({type:'ir.actions.act_window', res_model:'td.equipment.variant', res_id, views:[[false,'form']], target:'new'}, {onClose: reloadCatalog})`; нова модель/габарити з форми потрапляють у редактор після закриття діалогу. Підкладка: файл завантажується штатним `/web/binary/upload_attachment` (`model='td.layer'`, `id`), далі `queue({model:'td.layer', op:'write', vals:{underlay_attachment_id}})`; `.dwg` — повідомлення «Конвертуйте в DXF; DWG буде на сервері» (CD-09, DEC-18), статус `pending_conversion`.
Продуктивність: до ~600 комірок і ~250 об'єктів — спільні геометрії/InstancedMesh, рендер на вимогу (`requestRender()`), не безперервний цикл; один `WebGLRenderer`.

### 8.3 W3: віджети й конвеєр моделі (DEC-03…DEC-07)

- `model/formats.js`: `detectFormat(file)` → `{ext, kind: 'browser'|'server'|'rejected'}`: браузер — `glb, gltf, obj(+mtl), fbx, stl, 3mf, dae`; сервер — `step, stp, iges, igs, ifc`; відхилено — `skp` і все інше («Формат .skp не підтримується. Експортуйте в GLB, OBJ або STEP.»).
- `model/import.js`: `importModelFiles(files: File[], opts) → {glb: Blob, meta, warnings: [str]}` (R-15): вибір завантажувача за розширенням (для OBJ шукає `.mtl` і текстури серед `files`), нормалізація, підрахунок трикутників, експорт `GLTFExporter` (`binary:true`, `embedImages:true`, `maxTextureSize:1024`, `onlyVisible:true`), перевірка лімітів (R-18). `opts = {units: 'auto'|'mm'|'cm'|'m'|'in', upAxis: 'auto'|'y'|'z'}`.
- `model/simplify.js`: `simplifyToTriangles(object3d, target) → {object3d, triangles}` (R-16).
- `model/generic.js`: `buildGenericModel(category, {l, w, h}) → THREE.Group` (R-17, CD-18), `l,w,h` — метри; **W3 здає першим** (W2 використовує для об'єктів без моделі; до цього W2 ставить заглушку-паралелепіпед).
- `model/upload.js`: `uploadModel(variantId, {original, glb, meta}) → API-09` через `fetch` + `FormData` (`csrf_token: odoo.csrf_token`), прогрес `XMLHttpRequest.upload.onprogress`.
- `widgets/model_preview.js`: поле-віджет `f3d_model_preview` (`registry.category("fields").add("f3d_model_preview", {component, supportedTypes: ["many2one"], displayName: "3D-превью"})`), прив'язаний до `model_glb_id`; props — `record`, `readonly`. Поведінка: інтерактивний `OrbitControls` (обертання, масштаб, панорама), підлога-сітка 1 м, підписи габаритів, кнопка «Автообертання»; якщо `model_glb_id` порожнє або статус `pending_conversion`/`error` — умовна модель категорії з `record.data.length_mm/width_mm/height_mm` і підпис «Умовна модель (3D-файлу немає)» / «Очікує перетворення на сервері»; GLB — `GLTFLoader` за `/f3d/constructor/model/<id>/glb`; `onWillUnmount` → `dispose()` геометрій/матеріалів, `renderer.dispose()`, `forceContextLoss()`; рендер на вимогу (`controls.addEventListener('change')`), цикл `requestAnimationFrame` лише при автообертанні; висота 320 px, на вузькому екрані 240 px.
- `widgets/model_upload.js`: віджет форми `f3d_model_upload` (`registry.category("view_widgets")`): вибір файлів (`multiple`, `accept` за R-15), перемикачі «мм/см/м/дюйм» і «Вісь Z вгору», панель результату (формат, розмір МБ, трикутники, габарити мм, попередження), кнопки «Підставити габарити з моделі» (`record.update({length_mm, width_mm, height_mm})` за мапінгом x→довжина, z→ширина, y→висота), «Спростити» (з'являється при `triangles > max_triangles`), «Видалити модель» (`action_clear_model`). Якщо запис новий — спершу `record.save()`. Після успіху: `record.load()`; мініатюру (`image`) знімає `renderer.domElement.toBlob` 256×256, якщо `image` порожнє.
- `STEP/IGES/IFC` (R-15, R-20): віджет завантажує лише оригінал, показує «Збережено оригінал; перетворення на сервері очікує» або (після відповіді сервера) результат.

## 9. Алгоритми й правила

Python-реалізація — `services/*.py` (без ORM, приймає прості dict), JS-дзеркало — `static/src/editor/*.js`; еталон для обох — `static/tests/fixtures/{cells,checks}_golden.json` (генерує W1 з Python, AC-31). Допуск геометрії `eps = td.constructor.eps_mm / 1000` м (за замовчуванням 0,001 м).

### R-01 Генерація комірок (CD-07, CD-08)

Локальна система місця: початок — центр габариту, X уздовж довжини `L`, Y уздовж ширини `W`; світові координати комірки: `P + Rot(θ)·(lx, ly)`, де `P=(x_m,y_m)`, `θ=rotation`. `z0` — від відмітки шару. Номери: пролети/секції/колонки — зліва направо (+X), яруси/полиці — знизу вгору, ряди — з −Y. Індекс — `{:02d}` (ширина `max(2, цифр(N))`), ярус — без нулів. Код комірки ≤ 32 символи (інакше `ValidationError`), тому `code_prefix` ≤ 22.

| Шаблон | Параметри (діапазон; **ПРИПУЩЕННЯ** — умовчання для нового місця з UI, seed має власні значення) | `L × W` | Комірки: код, розмір, `z0` | Вид `td_loc_kind` / місткість |
|---|---|---|---|---|
| `pallet_rack` | `bays` 1…200 (6), `levels` 1…12 (4), `bay_width` 0.3…6 м (2.7), `depth` 0.2…3 (1.1), `level_height` 0.1…3 (1.5), `positions_per_bay` 1…8 (3), `max_load_kg` ≥0 (1000) | `bays·bay_width × depth` | `{p}-B{bb}-L{l}`; `bay_width × depth × level_height`; `(l−1)·level_height`; `lx=−L/2+(b−½)·bay_width`, `ly=0` | `pallet_cell` / `positions_per_bay` |
| `cantilever` | `arms` 1…100 (4; кількість секцій), `levels` 1…12 (3), `arm_length` 0.3…2 (1.0), `length` 0.5…60 (6), `level_height` (1.2), `max_load_kg` (500) | `length × arm_length` | `{p}-A{aa}-L{l}`; `length/arms × arm_length × level_height`; `(l−1)·level_height` | `shelf` (ПРИПУЩЕННЯ, Q-12) / не задається |
| `shelf` | `sections` 1…100 (4), `shelves` 1…20 (5), `cell_w` 0.1…3 (0.9), `cell_d` 0.1…2 (0.4), `cell_h` 0.05…2 (0.4) | `sections·cell_w × cell_d` | `{p}-S{ss}-L{l}`; `cell_w × cell_d × cell_h`; `(l−1)·cell_h` | `bin` / не задається |
| `floor_stack` | `rows` 1…50 (2), `cols` 1…26 (4), `cell_l` 0.3…6 (1.2), `cell_w` 0.3…4 (0.8), `max_height` 0.1…6 (1.5) | `cols·cell_l × rows·cell_w` | `{p}-{rr}{C}`, `C` = літера `A+col−1` (ПРИПУЩЕННЯ за зразком `PLT-04C`, Q-12); `cell_l × cell_w × max_height`; 0; `lx=−L/2+(c−½)·cell_l`, `ly=−W/2+(r−½)·cell_w` | `stack` / не задається |
| `machine_spot` | `length` 0.3…30, `width` 0.3…30, `service {front, back, left, right}` ≥0 м | `length × width` | комірок немає (`cell_count=0`) | — |
| `zone` | `polygon` `[[x,y],…]` ≥3 точки, світові координати; `x_m=y_m=0`, `rotation=0` | bbox полігона | комірок немає | — |

Елемент результату `generate_cells`: `{code, name, template, level, index, x, y, z0, l, w, h, rot, capacity, max_load_kg, kind}`. Перевизначення `overrides[code]`: `disabled=true` → комірка не повертається; `max_load_kg`, `capacity`, `name` замінюють значення. `cell_count = len(generate_cells(...))`.
Приклад: `pallet_rack`, `code_prefix='FG-R1'`, `bays=18`, `levels=4`, `bay_width=2.7`, `depth=1.1`, `level_height=1.5`, місце `(60, 5)`, `θ=0` → 72 комірки; `L=48.6`; `FG-R1-B01-L1` центр `(37.05, 5.0)`, `z0=0`; `FG-R1-B01-L4` — `z0=4.5`; `FG-R1-B18-L1` — центр `(82.95, 5.0)`. `levels=5` → 90 комірок. `θ=90` → `FG-R1-B01-L1` центр `(60, 5−22.95)=(60, −17.95)`.

### R-02 Геометрія: габарит, прив'язка, зона обслуговування, підключення

Вхід розміщення: варіант `L,W` (мм → `a=L/2000`, `b=W/2000`, м), `front_side`, `anchor`, `service_*`; розміщення `P=(x_m,y_m)`, `θ`. Одиничні вектори фронту `f`: `s=(0,−1)`, `n=(0,1)`, `e=(1,0)`, `w=(−1,0)`; праворуч (дивлячись на виріб з боку фронту) `r=(−f.y, f.x)`, ліворуч `−r`; `h_f` — півдовжина виробу вздовж `f` (`a` для `e/w`, `b` для `s/n`), `h_l` — вздовж `−r` (інша).
1. Центр у локальній системі виробу (повернутій на `θ` навколо `P`): `anchor=center` → `C=P`; `front` → `C=P−f·h_f`; `back` → `C=P+f·h_f`; `corner` (лівий передній кут; ліворуч = `−r`) → `C=P−f·h_f+r·h_l`. Зсув `o = C−P` обчислюється при `θ=0`; світовий центр `C_world = P + Rot(θ)·o`.
2. OBB габариту: центр `C_world`, піврозміри `(a, b)`, кут `θ`.
3. Видовження сервісу в локальних напрямках (при `θ=0`): `front→f`, `back→−f`, `right→r`, `left→−r`; `e_{+X}, e_{−X}, e_{+Y}, e_{−Y}` — значення (м) сервісу, спрямованого в ці боки. OBB сервісу: центр `C + Rot(θ)·((e_{+X}−e_{−X})/2, (e_{+Y}−e_{−Y})/2)`, піврозміри `(a+(e_{+X}+e_{−X})/2, b+(e_{+Y}+e_{−Y})/2)`, кут `θ`.
4. Точка підключення варіанта `(x_mm,y_mm,z_mm)` (початок — центр габариту) → світова: `C_world + Rot(θ)·(x_mm/1000, y_mm/1000)`.
Приклад: `L=4000`, `W=1200`, `front_side=s`, `anchor=front`, `P=(10,5)`, `θ=0` → `h_f=b=0.6`, `C=(10,5.6)`; фронт дивиться на південь (y=5.0). `service_front=1000` → сервіс-OBB центр `(10, 5.6−0.5)=(10,5.1)`, піврозміри `(2.0, 0.6+0.5=1.1)`.
Габарит місця (`slot`): OBB з центром `P`, піврозмірами `(L/2, W/2)` (R-01), кут `rotation`; для `machine_spot` — `length × width`.

### R-03 SAT для двох OBB

Для OBB `A,B` з осями `uA1,uA2,uB1,uB2` (одиничні), піврозмірами `(a1,a2)`, `(b1,b2)` і `d = cB−cA`: для кожної з 4 осей `u`: `rA = a1·|u·uA1| + a2·|u·uA2|`, `rB = b1·|u·uB1| + b2·|u·uB2|`, глибина `p_u = rA + rB − |d·u|`. `penetration = min_u p_u`. **Перетин, якщо `penetration > eps`** (дотик по краю — не перетин).
Приклад 1: `A` центр `(0,0)`, піврозміри `(1, 0.5)`, 0°; `B` центр `(1.5,0)`, `(1, 0.5)`, 0° → `p_x=0.5`, `p_y=1.0` → `0.5` — перетин. Центр `B=(2,0)` → `p_x=0` — немає перетину. Приклад 2: `A` `(0,0)`, `(1,1)`, 0°; `B` `(2.2,0)`, `(1,1)`, 45° → `p_x=0.214`, `p_y=2.414`, осі `B`: `0.858` → `0.214` — перетин.
`polygon_contains(poly, point)` — алгоритм променя з допуском `eps` на ребрах; `obb_inside_polygon(obb, poly)` — усі 4 кути всередині **і** жодне ребро OBB не перетинає ребро полігона (допуск `eps`).

### R-04 Перевірки: налаштування й `fits` (CD-13, CD-14)

Створюються при `create` площадки (ідемпотентно); порядок `sequence` 10…70:

| `check_key` | `enabled` | `mode` | `params` |
|---|---|---|---|
| `fits` | True | `block` | `{}` |
| `collide` | True | `block` | `{}` |
| `service_free` | True | `warn` | `{}` |
| `aisles_free` | True | `block` | `{}` |
| `load` | True | `warn` | `{}` |
| `utility_reach` | True | `warn` | `{max_m: 15}` |
| `fire` | True | `block` | `{}` |

`run_checks(state, configs)` повертає список `issue {check (= check_key), severity=config.mode, layer_id, codes, message}` лише для `enabled`. Об'єкти перевірки: розміщення (`placement`) і місця зі шаблонами, окрім `zone` (`slot`).
**fits** — для розміщення: (а) `variant.allowed_layer_kind_ids` непорожнє й не містить `layer.kind` → «{code}: варіант не допускається на шарі «{layer}»»; (б) `slot_id` задано, `allowed_slot_type_ids` непорожнє й не містить `slot.template` → «… не допускається в місці типу {template}»; (в) поворот не відповідає `rotation_mode` (`q`: `θ mod 90 = 0`; `h`: `mod 180`; `z`: `θ=0`; допуск 0,01°) → «{code}: поворот {θ}° недозволений»; (г) контейнер: якщо `cell_code` задано — OBB комірки (R-01), інакше якщо `slot_id` — OBB місця, інакше `layer.bounds` (R-03 `obb_inside_polygon`), інакше габарит будівлі `[0,Lb]×[0,Wb]` (`site.building_*`); габарит розміщення має бути всередині → «{code}: виходить за межі {місця|комірки|контуру шару|будівлі}». Для місць (`slot`): OBB всередині `layer.bounds`/будівлі.

### R-05 `collide`

Пари об'єктів одного шару серед `F` = розміщення ∪ місця (шаблони, крім `zone`); пара `(розміщення p, місце s)` ігнорується, якщо `p.slot_id == s.id`. Грубий відбір по AABB, далі R-03; `penetration > eps` → issue `codes=[a,b]`, «{a} перетинається з {b} на {depth:.2f} м». Об'єкти різних шарів не конфліктують (різні відмітки).

### R-06 `service_free`

Для розміщень із сумою `service_* > 0`: сервіс-OBB (R-02) проти габаритів **інших** об'єктів того самого шару (розміщення й місця з `F`, крім `p.slot_id`); `penetration > eps` → «Зона обслуговування {code} зачіпає {other}». Перетин сервісних зон між собою дозволено.

### R-07 `aisles_free`

Для кожного об'єкта з `F` (розміщення і місця): габарит-OBB проти прямокутників `layer.aisles` того самого шару (осьові OBB, кут 0); `penetration > eps` → «Прохід перекрито: {code} × {aisle.name}».

### R-08 `fire`

Той самий алгоритм, що R-07, проти `layer.fire_paths`; `penetration > eps` → «Пожежний прохід перекрито: {code} × {path.name}», для `kind='exit'` — «Вихід перекрито: {code} × {path.name}».

### R-09 `load`

Розміщення: `variant.floor_load_kn_m2` (R-04 field, ефективне) `> layer.max_floor_load_kn_m2` при `max>0` → «{code}: навантаження {x:.1f} кН/м² перевищує {max:.1f}». Якщо задано `cell_code`: `variant.weight_kg > max_load_kg комірки` (R-01 з перевизначенням) → «{code}: маса {w} кг перевищує {max} кг комірки {cell}». Шар без ліміту (0) не перевіряється.

### R-10 `utility_reach`

Для кожної точки підключення варіанта (R-02 п. 4) знайти найближчу точку `layer.utilities` **будь-якого шару площадки** того ж `kind` (`panel` вважається `electric`); 2D-відстань `d` (м) `> params.max_m` → «{code}: до найближчої точки «{kind}» {d:.1f} м (ліміт {max} м)»; точок потрібного виду немає — «{code}: на площадці немає точки «{kind}»». Варіант без `utilities` не перевіряється.

### R-11 Права на редагування (CD-02)

`can_edit_layer(user, layer)`: `user ∈ manager` → так; інакше `layer.edit_group_ids ∩ user.all_group_ids ≠ ∅`. `slot/placement`: `create/write/unlink` дозволені, якщо `can_edit_layer` істинне для шару до **і** після зміни (перенос між шарами — права на обидва). `layer.write`: поля зі списку `layer_content` — `can_edit_layer`; інші — лише менеджер; `edit_group_ids` — лише менеджер, лише групи привілею «Конструктор». Повідомлення: `«Шар «Склади» редагує: Конструктор: комірник.»`; для шару без груп — «…редагує: менеджер».

### R-12 План публікації

`build_plan(site)` → `{lines, issues, unchanged, draft_rev}`; кроки (усі читання — з `with_context(active_test=False)`, компанія `site.company_id` або без компанії):
1. `issues = run_checks(стан чернетки з БД)`; `block` — публікація недоступна.
2. Бажані локації: `generate_cells` для всіх активних місць; батько = `slot.parent_location_id`, інакше `site.default_parent_location_id` (немає ні того, ні того → issue `data` `block`: «Для місця {prefix} не задано батьківську локацію»).
3. Збіг локації з кодом: (а) `td_code == code`; (б) інакше `barcode == code`; кілька збігів → issue `conflict` `block` «Неоднозначний збіг для {code}»; збіг (б) при заповненому іншому `td_code` → `conflict`; знайдений запис з `td_site_id` іншої площадки → `conflict` «Код {code} зайнятий записом площадки {X}». Існуючі локації **не дублюються**.
4. Немає збігу → рядок `create`: `name=code` (або `overrides.name`), `barcode=code`, `td_code=code`, `usage='internal'`, `location_id=батько`, `td_loc_kind`, `td_capacity`, `td_site_id`, `td_slot_uid`, `company_id`. Є збіг → `update` лише з полів, що відрізняються: `td_code` (якщо порожній), `barcode` (якщо порожній), `td_loc_kind` (шаблон дає вид, відмінний), `td_capacity` (шаблон або перевизначення дає значення `≠0` і `≠` поточного), `location_id` (**лише** коли `slot.parent_location_id` задано явно й відмінний), `td_site_id`, `td_slot_uid`. Ім'я існуючого запису не змінюється. Архівований збіг → issue `warn` «Запис {code} архівований; не відновлюється автоматично»; рядок не створюється.
5. Обладнання: для кожного розміщення — `maintenance.equipment` за `td_code == code`, інакше за `serial_no == code` при порожньому `td_code`. `create`: `name`, `td_code`, `td_passport_id=variant.passport_id`, `td_zone_id=td.zone.zone_at(x,y,company)` (CB-03, якщо знайдено), `td_site_id`, `td_placement_uid`, `company_id`. `update` — `td_passport_id` (порожній → встановити; інакше розбіжність → рядок зі зміною), `td_zone_id`, `td_site_id`, `td_placement_uid`. Записи `mrp.workcenter` — коли `variant.create_workcenter`: збіг за `td_code`, інакше `code == code`; `create`: `name`, `code`, `td_code`, `td_site_id`, `company_id`; зв'язок `equipment.workcenter_id` (лише якщо поле існує, DEC-16) і `placement.workcenter_id`.
6. `apply_plan(site, plan, ticked_archive_codes, note)`: умови (група менеджера, `publish_enabled`, `plan.draft_rev == site.draft_rev`, `has_changes`, нема `block`); `SELECT … FROM td_site WHERE id=%s FOR UPDATE NOWAIT`; під `sudo()+with_company` створює/оновлює пачками (`create([...])`), ставить `placement.equipment_id/workcenter_id/published_at`, архівує позначені (R-13), будує версію (R-14); будь-який виняток — відкат усього. Незмінені записи не чіпаються (`write_date` не змінюється).

### R-13 Пропозиції архівації

Кандидати — записи з `td_site_id == site`, `active=True`, **код яких відсутній** у бажаних (комірки з `disabled`, видалені/архівовані місця й розміщення): `stock.location` (за `td_code`), `maintenance.equipment`, `mrp.workcenter`. Усі рядки `kind='archive'`, `selected=False`. `blocked=True` (змінити не можна): `stock.location` із залишком (`stock.quant` `quantity>0` у самій локації) — «Є залишки: {q}»; `maintenance.equipment` із відкритими заявками ТО (`maintenance.request` `stage_id.done=False`) — «Є відкриті заявки ТО»; `mrp.workcenter` з незавершеними завданнями (`mrp.workorder` `state not in ('done','cancel')`) — «Є незавершені завдання». Записи без `td_site_id` (створені не конструктором) **ніколи** не пропонуються. Архівація = `write({'active': False})`; видалення (`unlink`) не виконується ніколи.

### R-14 Знімок версії й відновлення чернетки (CD-21)

`build_snapshot(site)` → JSON `{schema:1, site:{name,code,building:{…},column_grid:{…},default_parent_location_id}, layers:[{uid,name,kind,sequence,elevation_m,grid_step_m,aisle_width_m,max_floor_load_kn_m2,bounds,allowed_slot_types:[key],edit_groups:[xml-id],color,opacity,style,visible,aisles,fire_paths,utilities,underlay_params}], slots:[{uid,layer_uid,template,code_prefix,x_m,y_m,rotation,params,overrides,parent_location:(повне ім'я|null)}], placements:[{uid,layer_uid,variant_id,variant_ref:{passport_role,name},slot_uid,cell_code,code,name,x_m,y_m,rotation}], check_configs:[{check,enabled,mode,params}], counts:{layers,slots,cells,placements}}` — **шаблони місць, не комірки**. Серіалізація: `sort_keys`, `ensure_ascii=False`; `snapshot_sha1 = sha1(bytes)`; зберігається `ir.attachment` (`mimetype='application/json'`, `name='f3d_layout_<site.code>_v<n>.json'`). Розмір для seed ≈ 150 КБ (ліміту 256 КіБ артефакта немає).
`apply_snapshot(site, data)` (відновлення): `layers/slots/placements` зіставляються за `uid` (оновлення, створення відсутніх; записи чернетки, яких немає у знімку, — `unlink`; `variant_id` береться за `id`, якщо існує, інакше за `variant_ref` → помилка `validation` із переліком), `check_configs` перезаписуються, поля площадки відновлюються. Записи Odoo (`stock.location` тощо) не чіпаються. Далі: `draft_base_version_id = version`; якщо `version == active_version` → `draft_rev = published_rev`, `draft_changes=0`; інакше `draft_rev += 1`, `draft_changes` = кількість сутностей (за `uid`), чий канонічний JSON відрізняється від знімка діючої версії (додані + змінені + видалені).

### R-15 Нормалізація моделі в браузері (CD-15, CD-16)

1. Розмір файлів ≤ `max_model_mb` (R-18), формат за `detectFormat` (§8.3). 2. Завантаження: `GLTFLoader`/`OBJLoader`(+`MTLLoader`)/`FBXLoader`/`STLLoader` (геометрія → `Mesh` із `MeshStandardMaterial`)/`ThreeMFLoader`/`ColladaLoader`. 3. Вісь вгору: `auto` → `z` для `stl`, `3mf`; `y` для інших; `z` → поворот сцени на −90° навколо X (у Y-up). 4. `bbox` вихідних одиниць; `units=auto`: для не-glTF `max(size) > 50 → 'mm'`, інакше `'m'`; для glTF — `'m'` (специфікація), але при `max(size) > 50` додається попередження «Схоже, одиниці — мм»; коефіцієнти `mm=0.001`, `cm=0.01`, `m=1`, `in=0.0254`. 5. Масштаб; зсув так, щоб центр bbox по X, Z = 0, `min.y = 0`. 6. `triangles` = Σ по мешах `(index ? index.count : position.count)/3`. 7. `meta = {format, file_name, size_bytes, glb_size_bytes, triangles, bbox_m:[x,y,z], size_mm:{x,y,z}, units, up_axis, status:'ok', warnings, converted_by:'browser'}`; `size_mm = round(bbox_m·1000)`. 8. Експорт GLB; розмір GLB ≤ ліміту. 9. Мапінг у варіант: `x→length_mm`, `z→width_mm`, `y→height_mm`.
Приклад: STL шафи, bbox у одиницях файла `(800, 400, 2000)`, `up=z` → `units='mm'`; після нормалізації `size_mm = {x:800, y:2000, z:400}` → `length_mm=800`, `width_mm=400`, `height_mm=2000`.

### R-16 Спрощення у браузері (CD-17)

`simplifyToTriangles(obj, target)`: кластеризація вершин на сітці: крок `h = diag(bbox)/N`; вершини в одній клітинці зливаються в середню, вироджені трикутники (дві однакові вершини) відкидаються, нормалі перераховуються, UV зливаються за першою вершиною. `N` підбирається бінарним пошуком у `[16, 1024]` за ≤12 ітерацій до `triangles ≤ target` (за замовчуванням `target = max_triangles`); результат — найбільше `N`, що задовольняє умову; якщо навіть `N=16` > target — повертає найкраще й попередження. Матеріали й кольори зберігаються. Пропозиція з'являється при `triangles > max_triangles`: «Модель має {n} тис. трикутників (ліміт {m} тис.). [Спростити] [Залишити як є]» (CD-17).

### R-17 Умовні моделі за категорією (CD-18)

`buildGenericModel(category, {l,w,h})` (метри, Y-up, центр X/Z у 0, низ Y=0, габарит групи = `l × h × w` з похибкою ≤1%): `machine` — корпус (`0.7h`), стіл (`0.1h`), шафа керування збоку (`0.9h`, `0.25l`), колір `#5b7c99`; `rack` — 4+ стійки по кутах і по 4 балки на ярус (`h/1.5` ярусів, ≥2), колір `#e8a33d`; `forklift` — шасі, щогла (`h`), вила, кабіна, колір `#f2c230`; `conveyor` — стрічка (`0.15h`), опорні ноги, ролики, колір `#7f8c8d`; `panel` — шафа з дверцятами й ручкою, колір `#c0392b`; `robot` — база, дві ланки, захват, колір `#2e86c1`; `other` — паралелепіпед `#95a5a6`. Спільні геометрії/матеріали кешуються за ключем `(category, l, w, h)`.

### R-18 Ліміти моделі (сервер, CD-17)

`size(original) ≤ max_model_mb·1 048 576` і `size(glb) ≤` те саме, інакше `too_large` (HTTP 413), нічого не зберігається. Дозволені розширення оригіналу: `glb, gltf, obj, mtl, fbx, stl, 3mf, dae, step, stp, iges, igs, ifc`; `.mtl`/текстури OBJ — поза оригіналом (їх вшиває GLB). `triangles` (R-19) `> max_triangles` → у `meta.warnings` додається `triangles_over_limit`, статус `ok`, `model_warning` показує попередження (не відмова). `glb` має починатися з `glTF` (версія 2) — інакше `bad_glb`.

### R-19 Метадані GLB (сервер)

`glb_meta(data: bytes) → {triangles, bbox_m, size_mm}` без сторонніх бібліотек: заголовок 12 байт (`magic=0x46546C67`, `version=2`, `length`), чанк 0 — JSON. Для кожного `mesh.primitive` (mode 4): `triangles += indices.count/3`, якщо немає `indices` — `POSITION.count/3`; mode 5/6 — `count−2`. `bbox` — об'єднання `POSITION.min/max` кожного примітива, перетворених афінною матрицею вузла (TRS або `matrix`, рекурсивно від `scene.nodes`). Помилки розбору → `bad_glb`. Значення клієнта (`meta.triangles`, `bbox_m`, `size_mm`) **перезаписуються** значеннями сервера.

### R-20 Серверне перетворення STEP/IGES/IFC (DEC-04)

`_f3d_convert_model()` (не кидає винятків): (1) якщо `convert_server_enabled=False` → `pending_conversion`, «Серверне перетворення вимкнено»; (2) конвертер за `meta.format`: `step/stp` → `cascadio` (`import cascadio`, `cascadio.step_to_glb(in, out)` — **ПРИПУЩЕННЯ** щодо API), `ifc` → виконуваний `IfcConvert` (IfcOpenShell; `shutil.which`; `IfcConvert in.ifc out.glb`), `iges/igs` — конвертера немає; (3) немає конвертера/бібліотеки → статус лишається `pending_conversion`, `meta.message = "Перетворення STEP/IFC на сервері недоступне: бібліотеку не встановлено (cascadio / IfcConvert). Оригінал збережено; експортуйте модель у GLB або OBJ."`; (4) є → тимчасовий каталог, запуск із таймаутом 60 с, читання GLB, `glb_meta` (R-19), `_f3d_set_model(glb=…, status='ok', converted_by='server')` (**ПРИПУЩЕННЯ**: вихід у метрах); помилка/таймаут → `error`, `meta.message` з причиною. Реєстр `services.convert.CONVERTERS = {ext: (probe(), run(in_path, out_path, timeout))}` розширюється без змін ядра (тест підміняє його).

### R-21 Лічильник чернетки й `etag`

`etag = write_date.strftime('%Y-%m-%d %H:%M:%S.%f')`. `_f3d_touch(n)`: SQL `UPDATE td_site SET draft_rev = draft_rev + 1, draft_changes = draft_changes + n WHERE id=%s` (без зміни `write_date` площадки). `has_changes = draft_rev != published_rev`. API-04: для `write/unlink` порівнюється `etag` запису з поточним `write_date`; розбіжність → `conflict` без змін. `draft_changes` = кількість змінених сутностей з моменту діючої версії (збільшується на число операцій; обнуляється публікацією/відновленням діючої).

### R-22 Схеми JSON-полів

`aisles[]`: `{id: str 1…32, name: str ≤64, x0<x1, y0<y1: finite float}`; `fire_paths[]` — те саме + `kind ∈ {path, exit}`; `utilities[]`: `{id, kind ∈ {electric, air, dust, panel}, name, x, y, z=0}`; `bounds`: `[[x,y],…]` ≥3, не самоперетинний; `underlay_params`: `unit ∈ {mm,m}`, `dx,dy,rot_deg,scale>0,opacity∈[0,1]`; `variant.utilities[]`: `{kind ∈ {electric, air, dust}, x_mm, y_mm, z_mm}`; `slot.overrides[code]`: ключі `disabled|max_load_kg|capacity|name`; `check.params`: R-04. Невідомі ключі відкидаються при `write` (не помилка), типи/діапазони — `ValidationError` із вказанням індексу елемента.

### R-23 Порожня площадка й типові значення

`_f3d_init_blank()`: будівля 60×30×8, крок колон 6×6; шари (`sequence` 10…50): «Будівля» (`building`, 0.0, `edit_group_ids` порожні, типи `zone`), «Склади» (`storage`, 0.0, комірник, типи `pallet_rack, cantilever, shelf, floor_stack`), «Виробництво» (`production`, 0.0, технолог, `machine_spot, zone`), «Інженерні мережі» (`engineering`, +6.0, інженер, `zone`), «Двір» (`yard`, 0.0, порожні, `zone`); `grid_step_m=0.5`, `aisle_width_m=3.0`; кольори `#9aa5b1`, `#e8a33d`, `#5b7c99`, `#c0392b`, `#6aa84f`. Каталог — 4 типові варіанти з §5.1. Для нового варіанта `allowed_layer_kind_ids` за категорією: `machine`→production; `rack`→storage; `forklift`→storage, production, yard; `conveyor`→production; `panel`→production, engineering; `robot`→production; `other`→усі.

### R-24 Порядок хука й ідемпотентність

Описано в §5.2 (кроки 1–6). Критерій ідемпотентності: два запуски `post_init_hook` поспіль → однакова кількість записів у всіх моделях конструктора, `seed_report` однаковий, жоден `stock.location`/`maintenance.equipment` не створений і не змінений, крім полів `td_site_id`, `td_slot_uid`, `td_placement_uid`, `equipment_id`, `workcenter_id`.

## 10. Стани й переходи

| Об'єкт | Стани | Переходи (хто/що) | Побічні ефекти |
|---|---|---|---|
| Чернетка площадки | `clean` (`draft_rev == published_rev`) ↔ `dirty` | будь-яка правка layer/slot/placement/check.config (UI, форма, API-04) → `dirty`; публікація або відновлення діючої версії → `clean` | `draft_changes` змінюється за R-21 |
| `td.layout.version.state` | `active` → `superseded` | нова публікація робить попередню `superseded`; `active` — завжди рівно одна на площадку | `site.active_version_id`, `published_rev = draft_rev` |
| `td.equipment.variant.model_status` | `none` → `ok` / `pending_conversion` / `error`; `pending_conversion` → `ok`/`error` (`_f3d_convert_model`, `action_retry_convert`); будь-який → `none` (`action_clear_model`); `ok`/`error` → `ok` (нове завантаження) | API-09, віджет W3 | вкладення замінюються, старі видаляються (`unlink` вкладення) |
| `td.publish.wizard.state` | `preview` → `done` | `action_confirm` | створює версію; повторне натискання неможливе |
| `td.layer.underlay_status` | `none` → `ready` (DXF) / `pending_conversion` (DWG) | завантаження файла (`write` `underlay_attachment_id`) | — |

## 11. Обробка помилок

| Ситуація | Поведінка |
|---|---|
| Два редактори правлять один запис | API-04 `conflict` з `current`; діалог у клієнті «залишити моє / взяти серверне»; інші записи запиту не застосовуються |
| Мережева помилка автозбереження | черга лишається в пам'яті; повтори через 2, 5, 15 с; індикатор «Помилка збереження»; `beforeunload` попереджає, поки черга непорожня |
| Втрата прав під час сесії | API-04 `rights` («Шар «X» редагує …»); клієнт повертає об'єкт у попередній стан і показує повідомлення |
| Публікація: код зайнятий чужим записом, неоднозначний збіг, немає батьківської локації | issue `conflict`/`data` `block`; кнопка публікації прихована |
| Два одночасні публікатори | `FOR UPDATE NOWAIT` → «Публікація вже виконується іншим користувачем» |
| Збій посеред публікації | відкат транзакції: нових записів, версії й змін `td_site_id` немає (`rollback`) |
| Завантаження моделі: >ліміту, невідомий формат, пошкоджений GLB | відповідні коди API-09; нічого не зберігається (вкладення створюються в тій самій транзакції) |
| WebGL недоступний | редактор і віджет показують «3D недоступне в цьому браузері»; форми Odoo працюють; HOOT-тести рендера використовують нульовий рендерер (патерн `testMode` переглядача) |
| Помилка розбору DXF | повідомлення з кількістю пропущених сутностей; файл >5 МБ або >200 тис. сутностей — попередження, імпорт обмежується першими 200 тис. |
| Часові пояси | усі `Datetime` — UTC у БД; клієнт показує в часовому поясі користувача; `etag` — UTC |
| Дублікати кодів | `models.Constraint`/`_check` із текстом українською; глобальна унікальність `td_code` (base) перевіряється при публікації (R-12) |
| Деінсталяція | §5.3: бізнес-записи Odoo не видаляються |

## 12. Acceptance Criteria

Тип: **UT** — юніт-тест `odoo.tests` (`post_install`, `-at_install`, `f3d`, `f3d_constructor`); **JS** — HOOT (`web.assets_unit_tests`); **MAN** — ручна перевірка на `serve.sh` за ТК (§13.2). Тести W1 (UT) не залежать від браузера.

| AC | CD / FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given чиста база з base+viewer; When встановлено модуль; Then є 4 групи й привілей, 12 `td.term`, 8 ключів `td.constructor.*`, меню `menu_td_constructor` (sequence 12) і `menu_td_constructor_plan` (14) під `td_factory3d.menu_td_root`, дія `tag='f3d_constructor'` | UT |
| AC-02 | CD-24, FR-02 | Given база без площадки; When виконано `post_init_hook`; Then є один `td.site` `seed_key='main_demo'` («Меблеве підприємство», 150×72×9) з кількостями `meta.counts` з `seed_site.json` (шарів, місць, комірок, розміщень, варіантів); повторний запуск не змінює кількостей ні в одній моделі | UT |
| AC-03 | CD-24 | Given існують `stock.location` `FG-R1-B01-L4` (barcode) і `maintenance.equipment` `SAW-1` (`td_code`); When виконано `link`; Then в них `td_site_id=site`, у відповідного розміщення `equipment_id` заповнено; нових `stock.location`/`maintenance.equipment` не створено; незнайдені коди — у `seed_report.unlinked` | UT |
| AC-04 | CD-24, CD-05 | Given менеджер; When API-02 `{name:'Склад 2', code:'S2'}`; Then площадка 60×30×8, 5 шарів із відмітками 0,0,0,+6.0,0, 7 `check.config` за R-04, 0 місць, 4 типові варіанти доступні; не-менеджер → `rights` | UT |
| AC-05 | CD-01, FR-21 | Given вихідники модуля; When тест сканує `*.py/*.js/*.xml` (крім `data/seed_site.json`, tests); Then немає жорстко заданих меблевих кодів (`FG-R`, `SAW-`, `RCK-`, `CNC-`) і зовнішніх URL (`http://`, `https://`, окрім `todo.ltd`, `odoo.com` у маніфесті/ліцензіях) | UT |
| AC-06 | CD-22 | Given дві площадки в одній компанії; When на обох створено місце `code_prefix='AA'`; Then створення дозволене (UNIQUE `(site_id, code_prefix)`), а публікація другої дає issue `conflict` `block` (код вже належить першій) | UT |
| AC-07 | CD-22 | Given площадки двох компаній і користувач першої; When API-01/API-03; Then бачить лише свою; `load` чужої → `not_found`; створення дочірніх записів до чужої площадки — `AccessError` | UT |
| AC-08 | CD-06 | Given шар; When задати `elevation_m=3.6`, `grid_step_m=0.25`, `aisle_width_m=3.5`, `color='#112233'`, `opacity=0.4`, `bounds` 4 точки, `edit_group_ids=[комірник]`, `allowed_slot_type_ids=[pallet_rack]`; Then збережено; `grid_step_m=0`, `color='red'`, `bounds` з 2 точок, група поза привілеєм → `ValidationError` | UT |
| AC-09 | CD-04, CD-05 | Given менеджер; When створено шар «Антресоль офісу» `kind='custom'`, `elevation_m=3.6` і місце `shelf` на ньому; Then `z0` комірок = `3.6 + (l−1)·cell_h`; шар видимий у `load` | UT |
| AC-10 | CD-04, FR-18 | Given завантажена площадка з шарами на різних відмітках; When відкрито редактор; Then сітка активного шару лежить на його відмітці з кроком `grid_step`, інші шари напівпрозорі, перемикач видимості ховає шар | JS |
| AC-11 | CD-07, CD-08 | Given місце `pallet_rack` `FG-R1` 18×4 (R-01); When `generate_cells`; Then 72 комірки, перша `FG-R1-B01-L1`, остання `FG-R1-B18-L4`, центр `FG-R1-B01-L1` у `(37.05, 5.0)` для місця в `(60,5)` | UT |
| AC-12 | CD-08, FR-05 | Given еталони `cells_golden.json` для 6 шаблонів; When Python і JS генерують комірки; Then коди, `x,y,z0,l,w,h`, місткість збігаються (допуск 1e-6); `SLOT_TEMPLATES` має рівно 6 ключів | UT+JS |
| AC-13 | CD-07 | Given місце 18×4 з `overrides={'FG-R1-B02-L1': {'disabled': true}, 'FG-R1-B03-L1': {'max_load_kg': 1500}}`; When перераховано; Then `cell_count=71`, комірки B02-L1 немає, B03-L1 має `max_load_kg=1500`; неіснуюча комірка в `overrides` → `ValidationError` | UT |
| AC-14 | CD-07 | Given місце 18×4; When `levels=5`; Then 90 комірок (UT: `cell_count`; JS: правка в панелі «Місця» перераховує комірки без перезавантаження) | UT+JS |
| AC-15 | CD-06, CD-08 | Given шар з `allowed_slot_type_ids=[pallet_rack]`; When створено місце `machine_spot`; Then `ValidationError` «Шар … не допускає тип …» | UT |
| AC-16 | CD-08 | Given модуль; When перелік шаблонів і `td.term` `slot_type`; Then немає ключів `gate`/`dock` | UT |
| AC-17 | CD-09, FR-04 | Given шар; When до шару прикріплено `plan.dxf`; Then `underlay_format='dxf'`, `underlay_status='ready'`, API-03 віддає `underlay.url`; JS: DXF з LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC → сегменти, масштаб мм→м, зсув і поворот з `underlay_params` застосовуються | UT+JS |
| AC-18 | CD-09 | Given файл `plan.dwg`; When завантажено в шар; Then `underlay_format='dwg'`, `underlay_status='pending_conversion'`; клієнт показує «Конвертуйте в DXF; DWG буде на сервері» і нічого не малює | UT+JS |
| AC-19 | CD-10, FR-06 | Given паспорт base; When створено варіант; Then `passport.variant_ids` містить його, `variant_count=1`, `td_category` за замовчуванням `other`; після хука `beam_saw.td_category='machine'`, `board_rack='rack'`, `forklift='forklift'` | UT |
| AC-20 | CD-11, CD-12 | Given варіант; When задано габарити, 4 сервіс-зони, `front_side`, `anchor`, `rotation_mode`, дозволені види шарів і типи місць, 2 точки підключення, `power_kw`, `panel`, `weight_kg`; Then збережено; `length_mm=0`, від'ємний сервіс, `utilities` з `kind='steam'` → `ValidationError` | UT |
| AC-21 | CD-11, CD-12 | Given паспорт `dim_l_mm=4000, dim_w_mm=1200, dim_h_mm=1600, power_kw=11`; When створено варіант без цих полів; Then вони наслідуються; `weight_kg=2400` при 4000×1200 → `floor_load_kn_m2 = 2400·9.80665/1000/4.8 = 4.90`; ручне значення зберігається | UT |
| AC-22 | CD-13 | Given еталони R-03 (приклади 1 і 2); When `sat_penetration`; Then 0.5 (перетин), 0 (дотик не є перетином), 0.214 (45°) з точністю 1e-3 | UT+JS |
| AC-23 | CD-13 | Given розміщення 4000×1200 поза `layer.bounds`; When `run_checks`; Then issue `fits`; у межах, але `rotation=45` при `rotation_mode='q'` → issue `fits` («поворот»); варіант не допускається на шарі → issue `fits` | UT |
| AC-24 | CD-13 | Given два розміщення, габарити перетинаються на 0.3 м; When `run_checks`; Then issue `collide` з обома кодами; на різних шарах — немає | UT |
| AC-25 | CD-13 | Given верстат із `service_front_mm=1000` і сусідній об'єкт у зоні 0.5 м перед фронтом; When `run_checks`; Then issue `service_free`; поворот на 90° змінює бік зони (R-02) | UT |
| AC-26 | CD-13 | Given прохід-прямокутник у шарі й розміщення, що його перекриває; Then issue `aisles_free` «Прохід перекрито» | UT |
| AC-27 | CD-13 | Given `max_floor_load_kn_m2=4` і варіант 4.90 кН/м²; Then issue `load`; для `cell_code` з `max_load_kg=1000` і `weight_kg=1200` — issue `load` | UT |
| AC-28 | CD-13 | Given `max_m=15`, найближча точка `electric` за 20 м; Then issue `utility_reach`; за 10 м — немає; без точок виду — issue «немає точки» | UT |
| AC-29 | CD-13 | Given `fire_paths` з `kind='exit'` перекритий об'єктом; Then issue `fire` | UT |
| AC-30 | CD-14, FR-11 | Given `collide` у режимі `warn`, потім `block`, потім `enabled=False`; When API-06/API-07 з перетином; Then `warn` — публікація дозволена, зауваження в `report.warnings`; `block` — `blocked` зі списком, версії немає; вимкнено — зауважень немає | UT |
| AC-31 | CD-13 | Given `checks_golden.json` (≥12 сцен, по кожній перевірці); When Python `run_checks` і JS `runChecks`; Then множини `(check, severity, codes)` збігаються | UT+JS |
| AC-32 | CD-13, CD-14 | Given нова площадка; Then 7 `check.config` за R-04 (`fits`, `collide`, `aisles_free`, `fire` — `block`; решта — `warn`); дубль `(site_id, check_key)` → `IntegrityError`/`ValidationError` | UT |
| AC-33 | CD-16 (DEC-03), CD-15 | Given варіант і GLB 200 КБ (24 трикутники); When API-09 (`original`+`glb`+`meta`) від технолога; Then створено два вкладення, `model_status='ok'`, `meta.triangles=24`, значення клієнта (`triangles=999`) перезаписано, `API-10 glb` повертає байти | UT |
| AC-34 | CD-17 | Given файл 21 МБ; When API-09 (UT) / вибір файла у віджеті (JS); Then відмова `too_large` (HTTP 413) з текстом «Файл більший за 20 МБ», вкладень не створено, `model_status` не змінився | UT+JS |
| AC-35 | CD-17 | Given GLB із 60 000 трикутників; When API-09; Then збережено, `model_warning` «60 тис. трикутників при ліміті 50 тис.», `meta.warnings=['triangles_over_limit']`; JS: `simplifyToTriangles(sphere100k, 50000)` → `triangles ≤ 50000` | UT+JS |
| AC-36 | CD-16 (DEC-04), CD-15 | Given файл `.step`; When API-09 без конвертера; Then `model_status='pending_conversion'`, оригінал збережено, `meta.message` з поясненням; з підміненим `CONVERTERS['step']` (повертає GLB) — `ok`, `converted_by='server'`; `.ifc`/`.iges` — аналогічно; `action_retry_convert` повторює | UT |
| AC-37 | CD-15, CD-16 | Given тестові файли (GLB, OBJ+MTL, STL генеруються в тесті; FBX, 3MF, DAE — малі фікстури); When `importModelFiles`; Then для кожного повертається GLB-Blob, `triangles>0`, `size_mm` відповідає еталону ±1 мм | JS |
| AC-38 | CD-15 | Given STL шафи (800,400,2000 у мм, Z-up); When `units:'auto'`, `upAxis:'auto'`; Then `units='mm'`, `size_mm={x:800,y:2000,z:400}`; з `units:'m'` — `size_mm.x=800000`; перемикач «Вісь Z вгору» міняє `y`/`z` | JS |
| AC-39 | CD-12 | Given варіант із моделлю `size_mm={x:800,y:2000,z:400}`; When «Підставити габарити з моделі»; Then `length_mm=800`, `width_mm=400`, `height_mm=2000` | JS |
| AC-40 | CD-15 | Given файл `.skp`; When вибрано у віджеті / API-09; Then відхилено з текстом «Формат .skp не підтримується…», `unsupported_format` | UT+JS |
| AC-41 | CD-18, FR-07 | Given категорії `machine, rack, forklift, conveyor, panel, robot, other`; When `buildGenericModel(cat, {l:3,w:1.5,h:1.8})`; Then габарит групи `3×1.8×1.5` ±1%, ≥2 дочірніх частини; редактор і віджет показують її, коли `model_status != 'ok'` | JS |
| AC-42 | CD-19, FR-09 | Given форма варіанта з GLB; When відкрито форму; Then віджет `f3d_model_preview` створює рендерер, `OrbitControls` реагують на перетягування (кут камери змінюється), при закритті форми `dispose()` викликано (нульовий рендерер у тесті); без файла — умовна модель + підпис | JS+MAN |
| AC-43 | CD-02 | Given шар «Склади» (`edit_group_ids=[комірник]`), «Виробництво» (`[технолог]`); When комірник пише місце на «Склади» і місце/розміщення на «Виробництво»; Then перше успішне, друге — `AccessError` «Шар «Виробництво» редагує: Конструктор: технолог.» | UT |
| AC-44 | CD-02 | Given технолог, інженер; When технолог створює розміщення на «Виробництво», правку варіанта; інженер пише `utilities`/`aisles` шару «Інженерні мережі» і спробу змінити `elevation_m` / `edit_group_ids`; Then перше й друге успішні, зміна `elevation_m`/`edit_group_ids` — `AccessError` | UT |
| AC-45 | CD-02 | Given шар з порожніми `edit_group_ids`; Then комірник/технолог/інженер — `AccessError`, менеджер — успіх | UT |
| AC-46 | CD-02 | Given комірник з правами на «Склади» і місце на ньому; When переносить місце на «Виробництво» (`layer_id`); Then `AccessError` (права на обидва шари) | UT |
| AC-47 | CD-02 | Given користувач лише з `group_td_user`; When API-04 `create` місця; Then `{ok:false, code:'rights'}`; прямий `write` через ORM — `AccessError` (ir.rule + ACL); читання API-03 дозволене | UT |
| AC-48 | CD-03 | Given місце; When `x_m` змінено у формі Odoo і через API-04 (як після перетягування в 3D); Then `load` повертає однакове значення; JS: поле в панелі властивостей двигає об'єкт, перетягування оновлює поле | UT+JS |
| AC-49 | CD-02 | Given `rights.editable_layer_ids=[1]`; When вибрано об'єкт шару 2; Then поля панелі readonly, перетягування вимкнено, підказка «редагує Комірник» | JS |
| AC-50 | CD-20 | Given чернетка з 1 новим рядом, 1 зміненим розміщенням і 1 видаленим місцем; When API-06; Then майстер містить рядки `create`/`update`/`archive` і підсумки `n_*`; у БД Odoo жодних змін (кількості `stock.location`, `maintenance.equipment` незмінні) | UT |
| AC-51 | CD-20 | Given порожня база локацій, місце 18×4 `FG-R1` з `parent_location_id=WH/Stock`; When `action_confirm`; Then створено 72 `stock.location`: `td_code=barcode=код`, `usage='internal'`, `td_loc_kind='pallet_cell'`, `td_capacity=positions_per_bay`, батько `WH/Stock`, `td_site_id=site`; рядок майстра `create` містить приклад коду | UT |
| AC-52 | CD-20 | Given вже існує `stock.location` з `barcode='FG-R1-B01-L4'` (без `td_code`); When публікація; Then запис **не дублюється**: оновлено `td_code`, `td_site_id`; кількість локацій = попередня + 71; повторна публікація без змін → `no_changes`, створено/оновлено 0 | UT |
| AC-53 | CD-20 | Given розміщення `SAW-9` варіантом із `create_workcenter=True`; When публікація; Then створено `maintenance.equipment` (`td_code`, `td_passport_id`, `td_zone_id` з `zone_at`) і `mrp.workcenter` (`code`, `td_code`); існуюче обладнання з тим самим `td_code` лише оновлюється; `placement.equipment_id/workcenter_id` заповнені | UT |
| AC-54 | CD-20, FR-16 | Given опубліковане місце, що видалене з чернетки; When майстер; Then рядок `archive` з `selected=False`; публікація без галочки лишає `stock.location` активним; з галочкою — `active=False`, запис не видалено; локація із залишком має `blocked=True`, галочку не поставити; записи без `td_site_id` ніколи не пропонуються | UT |
| AC-55 | CD-20, FR-22 | Given `td.constructor.publish_enabled='False'`; When API-07 / `action_confirm`; Then `disabled`, `can_publish=False`, нічого не створено | UT |
| AC-56 | CD-20, CD-02 | Given технолог/комірник/інженер; When API-06/07 і `action_confirm`; Then `rights`/`AccessError`; менеджер — успіх | UT |
| AC-57 | CD-20 | Given штучна помилка під час створення 40-ї локації (патч `create`); When API-07; Then `rollback`, жодної нової локації/версії, `td_site_id` не змінено | UT |
| AC-58 | CD-21, FR-17 | Given публікація; Then `td.layout.version` `n` = попередній+1, `state='active'`, попередня `superseded`, `snapshot_id` — JSON за R-14 з шаблонами місць (кількість `slots` збігається, комірок у знімку немає), `snapshot_sha1` збігається, `site.active_version_id` оновлено | UT |
| AC-59 | CD-21 | Given версії v1 і v2; When `action_restore_draft` на v1; Then чернетка = знімок v1 (за `uid`: зайві видалено, відсутні створено), `stock.location` не змінено, `draft_base_version_id=v1`, `has_changes=True`; відновлення діючої версії → `has_changes=False` | UT |
| AC-60 | CD-21 | Given чернетка без змін після публікації; When API-06/API-07; Then `no_changes` («Немає змін для публікації»), версія не створена | UT |
| AC-61 | CD-21, CD-03, FR-14 | Given два клієнти; When перший зберіг запис, другий шле `write` зі старим `etag`; Then `conflict` з `current`, нічого не застосовано; JS: `OdooStore.queue` зливає операції, автозбереження через `autosave_ms`, `id_map` підміняє `tmp`→`id`, при мережевій помилці — повтор | UT+JS |
| AC-62 | FR-19 | Given користувач менеджер; When API-01…API-10 з валідними й невалідними тілами; Then відповіді відповідають §7 (структура `load`, коди помилок, ліміти 500 ops / 1 МБ); неавтентифікований → редирект/401 | UT |
| AC-63 | CD-03, CD-13, CD-23 | Given режим «Редагування», шар зі станком і прохід, `aisles_free=block`; When станок перетягнуто в прохід; Then об'єкт повертається на місце з повідомленням «Прохід перекрито»; при `warn` лишається, підсвічується помаранчевим; позиція прив'язана до `grid_step` | JS |
| AC-64 | CD-23 | Given вибраний станок; When натиснуто `R` / кнопку повороту; Then `rotation += 90`, footprint перераховано (R-02), перетин із сусідом підсвічується | JS |
| AC-65 | CD-23 | Given редактор; When лінійка (2 кліки) і `Delete`; Then показано відстань у метрах; видалення просить підтвердження у власному діалозі (виклики `window.alert/confirm/prompt` відсутні — перевірка шпигуном) | JS |
| AC-66 | CD-22, CD-24 | Given дві площадки (seed і порожня); When перемикач площадки; Then редактор перезавантажує стан із API-03, зміни чернетки першої не потрапляють у другу; «Нова площадка» викликає API-02 | JS+MAN |
| AC-67 | CD-23, FR-20 | Given редактор і форма варіанта; When ширина 1440 і 400 px, світла/темна тема Odoo; Then інтерфейс українською, без горизонтальної прокрутки на 400 px, панелі складаються | MAN |
| AC-68 | CD-23, CD-01 | Given тестовий сервер із seed; When сценарій ТК-01…ТК-08 (шари, шаблон 18×4, каталог, моделі, перетягування з перевірками, DXF, публікація, версії); Then усі кроки виконуються без помилок консолі | MAN |

## 13. План тестування (для Opus)

### 13.1 Юніт-тести

Усі W1-тести — `TransactionCase`, теги `post_install`, `-at_install`, `f3d`, `f3d_constructor`; базовий клас `F3DConstructorCase` (`tests/common.py`): компанія, площадка-фікстура з 5 шарами (R-23), користувачі `u_manager`, `u_tech`, `u_store`, `u_eng`, `u_plain`, два `stock.location` (`WH/Stock`, `WH/Stock/FG`), паспорт із варіантом, генератор GLB (24 трикутники, будується в тесті з `struct`). Мінімальні GLB/STL/OBJ у JS-тестах також генеруються кодом.

| Файл / клас | AC | Ключові assert |
|---|---|---|
| `test_term_site_layer.py` `TestSiteLayer` | 01, 04, 07, 08, 09, 17, 18 | дані й групи; blank-площадка; ir.rule компанії; валідації шару; DXF/DWG статуси |
| `test_slot_cells.py` `TestSlotCells` | 11…16 | R-01 приклади з числами §9; `overrides`; `levels=5` → 90; перелік шаблонів |
| `test_variant.py` `TestVariant` | 19, 20, 21 | обмеження, наслідування з паспорта, `floor_load` |
| `test_checks.py` `TestChecks` | 22…32 | R-03 приклади; кожна перевірка; режими; `checks_golden.json` (золоті файли генерує той самий тест при `F3D_UPDATE_GOLDEN=1`, інакше звіряє) |
| `test_variant_model_api.py` `TestVariantModelApi` | 33…36, 40 | `HttpCase`/`url_open` multipart із `csrf_token`; ліміти; pending; підміна `CONVERTERS` |
| `test_rights.py` `TestRights` | 43…47 | рівні доступу за ролями; тексти помилок |
| `test_api.py` `TestApi` | 48, 61, 62 | `load`-структура; `save` атомарність, `conflict`, `id_map`, ліміти |
| `test_publish.py` `TestPublish` | 50…57 | R-12/R-13; відкат (`patch` `stock.location.create`); стоп-кран |
| `test_versions.py` `TestVersions` | 58…60 | знімок, `sha1`, відновлення, `no_changes` |
| `test_seed_hook.py` `TestSeedHook` | 02, 03, 05, 06 | запуск `post_init_hook(env)` двічі; лічильники; сканер джерел |
| `test_hoot_editor.py` `TestEditorHoot` (W2) | 10, 12, 14, 17…18, 22, 31, 48, 49, 61, 63…66 | запуск suite `@td_constructor/editor` (фільтр `&id=<hash>` як у `td_viewer3d/tests/test_hoot.py`) |
| `test_hoot_model.py` `TestModelHoot` (W3) | 34, 35, 37…42 | запуск suite `@td_constructor/model` |

### 13.2 Ручні сценарії на `serve.sh` (ТК-01…ТК-08, Playwright, `/opt/pw-browsers/chromium`)

Передумови: база з модулем і seed; користувач `admin`. Скриншоти — у `…/scratchpad/constructor/shots/`.

| ТК | Кроки | Очікування |
|---|---|---|
| ТК-01 | Меню «Завод 3D → Конструктор» | відкривається редактор площадки «Меблеве підприємство»: будівля 150×72, шари, стелажі ГП із комірками, станки |
| ТК-02 | Вкладка «Місця» → `pallet_rack` 18×4 → поставити; змінити ярус 4→5 | 72, потім 90 комірок із кодами `…-B01-L1`; ліч. у списку місць |
| ТК-03 | «Каталог»: перетягнути варіант на «Виробництво»; поставити на прохід | замічання «Прохід перекрито» (за режимом warn/block), при block — повернення |
| ТК-04 | «Змінити варіант»: завантажити GLB, OBJ+MTL, STL; STEP | превью обертається; габарити з моделі; STEP — «очікує перетворення» |
| ТК-05 | Підкладка DXF (тестовий файл) на шарі «Склади» | лінії на підлозі шару; масштаб/зсув/поворот працюють; DWG — повідомлення |
| ТК-06 | Роль: увійти комірником | правка «Виробництво» заборонена, підказка «редагує Технолог» |
| ТК-07 | «Опублікувати» | майстер зі списком «буде створено / оновлено / пропонуємо архівувати»; після підтвердження — нова версія, записи в «Склад → Локації» |
| ТК-08 | «Історія версій» → повернути чернетку до v1 | чернетка змінилась; записи Odoo без змін; перемикач площадки: seed ↔ порожня |

### 13.3 Тести безпеки

Доступ без групи (`u_plain`): лише читання; обхід `api-04` для чужого шару → `rights`; ін'єкції в `code`/`code_prefix` (`'; DROP`, пробіли, кирилиця, `../`) → `ValidationError` (регулярка CB-01); `name` у вкладеннях очищується (`os.path.basename`) в API-09; API-09 без `csrf_token` → 400; JSON у `params/overrides` із вкладеністю >8 рівнів або >256 КБ → відмова; `meta` не довіряється (AC-33); API-10 без права читання варіанта → 403; публікація не виконується без `publish_enabled`.

### 13.4 Продуктивність

API-03 для seed ≤ 1,5 с (≈ 250 КБ); API-04 зі 100 операціями ≤ 1 с; `run_checks` (Python) на 250 об'єктах ≤ 1 с, JS ≤ 300 мс; `build_plan` + `apply_plan` для 360 нових комірок ≤ 20 с; завантаження GLB 20 МБ (API-09) ≤ 10 с; рендер редактора на seed — одна відмальовка ≤ 50 мс (`requestRender`), пам'ять не росте після 10 перемикань площадки (перевірка `renderer.info.memory`).

### 13.5 Чек-лист DEPLOY_TEST (`docs/modules/td_constructor/DEPLOY_TEST.md`, здає інтеграція)

1. Копія демо-бази тестового сервера → встановлення модуля; 2. `seed_report`: `linked.locations` дорівнює числу локацій `FG-*`/`RCK-*`/`FUR-*` у базі, `unlinked` — перелічені; 3. «Опублікувати» на seed: `created` лише для кодів, яких бракувало; існуючі `FG-R1-B01-L4` не продубльовані; 4. відкат: деінсталяція — записи `stock.location`/`maintenance.equipment` на місці; 5. повторна установка — seed не дублюється (`seed_key`).

## 14. Definition of Done

- [ ] Усі UT (W1) і HOOT (W2, W3) зелені: `run_tests.sh` повертає `OK`; AC-01…AC-68 покриті (UT/JS) або пройдені за ТК (MAN) зі скриншотами.
- [ ] `ruff check` (конфіг base `ruff.toml`) без зауважень; нема `x_`-полів; у bundle немає зовнішніх URL (AC-05).
- [ ] Модуль ставиться на чисту базу й на копію демо-бази; `post_init_hook` ідемпотентний (AC-02, AC-03).
- [ ] Права: AC-43…AC-47, AC-56 і §13.3 пройдені; перегляд безпеки (rules, `sudo` лише в `publish`).
- [ ] `neutralize.sql` не потрібен (немає кронів, джерел, токенів) — зафіксовано в README модуля.
- [ ] `README.md`, `CHANGELOG.md`, `DEPLOY_TEST.md`; інструкції ARCH §4 перенесені в README.
- [ ] Відхилення від CD-16 (DEC-03) підтверджене замовником або позначене в README як «очікує підтвердження» (Q-01).

## 15. Відкриті питання

Ті самі номери, що в ARCH §5.1: Q-01 (відхилення від CD-16), Q-02 (серверні конвертери), Q-03 (шаблон «зона» → `td.zone`), Q-04 (хто публікує), Q-05 (архівація при залишках), Q-06 (DWG на сервері), Q-07 (префікси кодів між площадками), Q-08 (фаза 2: переглядач з розкладки), Q-09 (ліміти навантаження), Q-10 (досяжність підключення), Q-11 (типові габарити), Q-12 (коди й види комірок консольних/підлогових шаблонів), Q-13 (`mrp_maintenance`), Q-14 (шлях Hoot-suite).
