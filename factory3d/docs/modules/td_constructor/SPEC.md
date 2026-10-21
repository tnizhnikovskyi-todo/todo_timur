# td_constructor — специфікація

Версія 0.3 · 19.10.2026 (v0.1 — 17.10.2026; v0.2 — злиття, 19.10.2026; зміни — «Журнал змін документа» в кінці) · технічне рішення: `docs/modules/td_constructor/ARCHITECTURE.md` (далі ARCH; рішення DEC-xx, питання Q-xx — там).
Вхідні документи: `build/constructor/DECISIONS.md` (рішення замовника CD-01…CD-24, 17.10.2026) і `build/constructor/PROTOTYPE.md`
(прототип-артефакт: його модель даних — чернетка моделей нижче, імена полів збережено).
Спирається на контракти каркаса: C-6.1 (код сцени), CB-01/CB-03/CB-05/CB-07 (`td_factory3d`: домішка, `td.zone.zone_at`, `stock.location`
вид і місткість, паспорт `td.equipment.passport`), CB-09 (меню), CB-10 (групи), CB-12 (габарит будівлі), конвенції §5. Нових протоколів P-xx немає.
Контракти, які модуль визначає сам: CC-01 (`td_site_id`), CC-02 (геометрія розкладки для переглядача, фаза 2) — ARCH §2.1.

**Злиття з «Конструктором складу» (CD-27, CD-29…CD-31).** v0.2 додає те, що зроблено в хвилях 0–2 злиття (модуль `19.0.1.4.0`, ядро `factory3d/core/constructor`):
моделі M-16…M-31, правила R-25…R-41, API-11…API-24 і додаткові маршрути (§7.1), представлення V-14…V-18, критерії AC-70…AC-138 (§12.1), тести (§13.6). Існуючі ID не
змінено. План злиття — `build/constructor/MERGE.md` (російською; F01…F19 — функції «Конструктора складу», N-xx — знайдене понад список), рішення замовника — `DECISIONS.md`
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
│   ├── td_equipment_variant.py         [W1] M-04 (поля, обмеження, _td_set_model, _td_convert_model)
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

### 0.1 Доповнення до дерева (хвилі 0–2 злиття, версія модуля 19.0.1.4.0)

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
├── services/                            чисті Python-модулі; ORM використовують лише state.py, snapshot.py, publish.py, capacity.py, putaway.py, metrics.py, odoo_sync.py, а також render_docs.py (режим `{site_id}`) і labels.py (параметр `labels_max`)
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
`application: False` — пункти меню живуть під «3D Завод» (`td_factory3d.menu_td_root`, DEC-01).

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
    "web.assets_tests": ["td_constructor/static/src/tours/*.js"],   # 19.0.1.4.0: `start_tour` виконуються лише так (AC-131)
},
```

Збірка ядра `static/lib/f3d-core/constructor.esm.js` **не входить** у bundle: вантажиться динамічним `import()` (`core_loader.js`, `CORE_URL?v=CORE_BUILD`), як `f3d-loaders` (DEC-06).
Збирає розробник (`node tools/build_core.mjs module`), файл комітиться; на сервері нічого не збирається (ARCH §2.2a).

## 2. Моделі

Спільні правила для M-01…M-07: `company_id` — Many2one `res.company`, на площадці `required`, `default=lambda s: s.env.company`; у дочірніх сутностей —
`related="site_id.company_id"`, `store=True`, `index=True` (для record rule; DEC-12). `uid` — Char(32), `default=lambda s: uuid4().hex`, `copy=False`, `index`,
`readonly` у формах; ключ між знімком версії, клієнтом (тимчасові id) і відновленням (DEC-14); UNIQUE `(site_id, uid)` для layer/slot/placement.
Усі Float-метри — `digits=(10, 3)`, якщо не сказано інакше. `active` — Boolean `default=True`; архівація сутності не видаляє записи Odoo.
Кожне `create/write/unlink` layer/slot/placement/check.config викликає `site._td_touch(n)` (R-21): `draft_rev += 1`, `draft_changes += n`.

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

Методи: `create` (після супер: `_td_init_checks()`; якщо `context.f3d_blank` — `_td_init_blank()`); `_td_init_checks()` — 7 рядків `td.check.config` за таблицею R-04
(ідемпотентно); `_td_init_blank()` — R-23 (5 базових шарів); `action_open_constructor()` → `{'type':'ir.actions.client','tag':'f3d_constructor','params':{'site_id':id}}`;
`action_publish_wizard()` → створює `td.publish.wizard` і повертає `act_window` (M-08; права — менеджер); `_td_touch(n=1)` (sudo, без `write_date` каскаду);
`_td_check_rights_manager()` → `AccessError("Лише менеджер конструктора…")`.

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
Метод `_td_cells(self)` → `list[dict]` — комірки на льоту (`services.cells.generate_cells`), **не зберігаються** (DEC-15); поля елемента — R-01. Метод
`_td_footprint_obb()` → OBB (R-02) для checks.

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
| `model_status` | Selection | `none`/`Немає`, `ok`/`Готово`, `pending_conversion`/`Очікує перетворення`, `error`/`Помилка`; `default='none'`, `readonly`, `index`; пише лише `_td_set_model` |
| `model_warning` | Char | `compute`: «N тис. трикутників при ліміті M тис.» якщо `meta.triangles > max_triangles` або `meta.warnings` |
| `image` | Image | `max_width=512`, `max_height=512`; мініатюра, яку знімає віджет W3 при завантаженні |
| `placement_count` | Integer | `compute` |
| `note` | Text | |
| `active` | Boolean | |

`@api.constrains`: розміри `>0` («Розміри варіанта мають бути додатними.»); сервіс `≥0`; `utilities` — масив об'єктів зі схемою (R-22; `kind` ∈ electric/air/dust, числа скінченні);
`model_meta.status` узгоджений з `model_status`; `model_status=='ok'` вимагає `model_glb_id`.
Методи: `_td_set_model(original, glb, meta, status, message)` (єдина точка запису полів моделі; перевірки R-18; повертає `dict(model_status, model_meta)`);
`_td_convert_model()` (R-20; нічого не кидає, повертає `{'ok': bool, 'status': str, 'message': str}`); `_td_effective_floor_load()`; `_td_local_geometry()` (R-02);
`action_clear_model()` (скидає вкладення й мета, `model_status='none'`; право — технолог/менеджер); `action_retry_convert()` (повторює `_td_convert_model()`); `unlink` — `UserError`, якщо є розміщення (архівуйте варіант).

### M-05 `td.placement` — розміщення обладнання (CD-10, CD-13)

`_name='td.placement'`, `_description='Розміщення обладнання'`, `_order='layer_id, code'`, `_rec_name='code'`.

| Поле | Тип | Параметри |
|---|---|---|
| `uid` | Char(32) | |
| `layer_id` | Many2one `td.layer` | `required`, `ondelete='cascade'`, `index` |
| `site_id`, `company_id` | Many2one | related, stored |
| `variant_id` | Many2one `td.equipment.variant` | `required`, `ondelete='restrict'`, `index` |
| `slot_id` | Many2one `td.slot` | `ondelete='set null'`, `domain=[('layer_id','=',layer_id)]`; місце під верстат / стелаж, в який поставлено |
| `cell_code` | Char(32) | необов'язково: комірка стелажа `slot_id` (R-04 fits/load); має бути серед `slot._td_cells()` |
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
`@api.constrains('variant_id','layer_id')`: `variant.length_mm>0`. Методи: `_td_obb()`, `_td_service_obb()` (R-02); `action_show_in_3d()` → `equipment_id.action_f3d_show()` або
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
- Типи, пресети, варіанти, коментарі, оренди — не чернетка площадки: `site._td_touch` вони не викликають (крім правок, що змінюють розкладку: `/site/addr`, `/odoo/rules`, перемикання варіанта).
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

`data` зберігається **нормалізованим** (`_td_normalize_data`, R-22): `template` ∈ (`pallet_rack`, `cantilever`, `shelf`, `floor_stack`, `floor_spot`, `machine_spot`), `params` — за `cells.normalize_params`, `rotation` — ціле 0…359, `prefix` ≤ 32,
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
«Виконавець не має доступу до конструктора»), `f3d_set_text`, `f3d_resolve(resolved)`, `f3d_remove` — **змінює, вирішує й видаляє автор або «Проєктування»** (технолог, комірник, інженер, менеджер); `_td_sync_activity` — відкрита задача з виконавцем має
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
`_td_normalized` (R-22) → `_td_check_*` (R-11; перевизначають моделі) → `_td_lease_*` (R-39; лише `td.slot`, `td.placement`) → `super()` → `_td_touch_sites` (R-21; контекст `f3d_no_touch` вимикає). Допоміжні: `_td_is_manager`, `_td_can_edit_layer(layer)`,
`_td_assert_layers` («Шар «%s» редагує: …»), `_td_assert_manager(what)`, `_td_etag()` (`write_date` у форматі `%Y-%m-%d %H:%M:%S.%f`).

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

`_check_addr`; `create/write` нормалізують `addr` (`_td_normalize_addr_vals`, помилка — `ValidationError("Адресація площадки: …")`); зміна `addr`/`depth_mode`/`loc_tree` через `_td_apply_addr(vals, renumber='new'|'all')` (R-25).

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

`overrides[code]` розширено ключами `usage` (`internal`/`view`) і `replenish_location` (R-28; `OVERRIDE_KEYS = disabled, max_load_kg, capacity, name, usage, replenish_location`). Службові методи адресації (`_td_addr_contexts`,
`_td_codes_map`, `_td_renumber`, `_td_recompute_counts`, контекст `f3d_no_renumber`) — R-25. Зміна `template`/`params`/`addr` перераховує `cell_count`, `footprint_*` і (якщо потрібно) переносить правки комірок на нові коди.

### M-28 `stock.location` — адресні номери (доповнює M-13)

`td_row`, `td_bay`, `td_level`, `td_pos` — Integer, `copy=False`, `readonly`, `td_row` з `index`; `0` — не задано; заміна `posx/posy/posz` Odoo 18 (їх у Odoo 19 немає). `@api.constrains` — від'ємні значення заборонені. Метод
`_td_address_vals(code, parts, addr, loc_tree)` лише **рахує** `{name, barcode, td_row, td_bay, td_level, td_pos}` (`addr.location_vals`, R-25); записує їх публікація (R-31).

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
| `menu_td_constructor` | Конструктор | `menu_td_constructor_plan` | 1 | `action_td_constructor` (`ir.actions.client`, `tag='f3d_constructor'`, `name='Конструктор'`, `target='current'`, `params={}`) |
| `menu_td_constructor_plan` | Планування | `td_factory3d.menu_td_root` | 70 | — (папка) |
| `menu_td_site` | Площадки | `menu_td_constructor_plan` | 10 | `action_td_site` (`list,form`) |
| `menu_td_layer` | Шари | `menu_td_constructor_plan` | 20 | `action_td_layer` (`list,form`; контекст `search_default_group_site`) |
| `menu_td_variant` | Каталог варіантів | `menu_td_constructor_plan` | 30 | `action_td_equipment_variant` (`kanban,list,form`) |
| `menu_td_version` | Версії планування | `menu_td_constructor_plan` | 40 | `action_td_layout_version` (`list,form`) |
| `menu_td_constructor_terms` | Довідники конструктора | `td_factory3d.menu_td_config` | 14 | `action_td_term` (`groups=group_td_constructor_manager`) |

Дія майстра `action_f3d_publish_wizard` — `target='new'`, створюється з `site.action_publish_wizard()`.

### 3.1 Представлення й меню злиття (V-14…V-18; хвилі 1–2)

Усі нові форми — без `attrs`; списки — `<list>`; редактор (`f3d_constructor`) лишається основним інтерфейсом, ці форми — службові (CD-03: точні числа правляться й тут). Файли: `views/td_slot_type_views.xml` (V-14), `td_putaway_views.xml` (V-15…V-16),
`td_collab_views.xml` і `td_help.xml` (V-17…V-18); `wizard/td_publish_wizard_views.xml` і `views/td_layout_version_views.xml` розширено (V-08, V-07). Представлення **площадки, шару, місця, паспорта, варіанта** не змінювалися: нові поля M-25…M-27 редагуються
в редакторі й у формах-JSON, а в формах V-01…V-03 не виводяться.

| V | XML-id (суфікси `view_td_…`) | Тип / модель | Структура |
|---|---|---|---|
| V-14 | `slot_type_list`, `slot_type_form`, `slot_type_search`, `slot_preset_list`, `slot_preset_form` | `td.slot.type`, `td.slot.preset` | Список типів (`sequence` handle, `ref`, `name`, `code`, `group`, `template`, `relevance`, `loc_kind` hide, `is_custom`, `company_id` у мультикомпанії); форма — групи «Основне» (`name`, `code`, `ref`, `group`, `template`, `shape`) і «Каталог» (`relevance`, `loc_kind`, `is_custom`, `company_id`, `sequence`, `active`) + `description`; пошук: `name/code/ref`, фільтри «Власні», «Є на фабриці» (`relevance >= 1`), «Архівні», групування за групою й генератором. Пресети: список `name`, `kind`, `type_id`; форма — ті самі + `active`. Дані `params`/`data` у формах не виводяться (редагуються в редакторі, R-22) |
| V-15 | `putaway_rule_list`, `putaway_rule_form` | `td.putaway.rule` | Список: `site_id`, `sequence` (handle), `product_id`, `category_id`, `in_location_id`, `out_code`, `out_location_id`, `storage_category_id` (hide), `deleted`; форма: «Умова» (`site_id`, `product_id`, `category_id`, `package_type_ids` tags, `storage_category_id`) і «Призначення» (`in_location_id`, `out_code`, `out_location_id`, `sublocation`, `sequence`, `deleted`, `odoo_rule_id`, `active`) |
| V-16 | `replenish_rule_list/_form`, `publish_op_list/_form` | `td.replenish.rule`, `td.publish.op` | Правила: `site_id`, `cell_code`, `location_id`, `product_id`, `min_qty`, `max_qty`, `deleted`, `odoo_orderpoint_id`. Журнал публікацій — **лише читання**: `version_id`, `seq`, `op`, `res_model`, `code`, `res_id`, `rolled_back` (та `before`/`after` у формі) |
| V-17 | `layout_variant_list/_form` (+ `_s6`), `comment_list/_form/_search` (+ `_s6`), `zone_lock_list` | `td.layout.variant`, `td.comment`, `td.zone.lock` | Варіанти: `site_id`, `sequence`, `name`, `base_version_id`, `is_training`, `is_current`, `origin_id`, `snapshot_id`. Коментарі: список `site_id`, `kind`, `state`, `target_kind`, `target_label`, `text`, `author_id`, `assignee_id`, `activity_ids` (`list_activity`); форма — + `chatter` (обговорення `mail.thread`); пошук: фільтри «Відкриті», «Вирішені», «Задачі», «Коментарі», «Мої задачі», групування за площадкою/видом/станом. Блокування — список `site_id`, `zone_uid`, `user_id`, `expires_at` |
| V-18 | `td_help_page` (QWeb), `action_td_help` | сторінка `/f3d/constructor/help` | `ir.actions.act_url` (`target='new'`) → GET `/f3d/constructor/help?lang=uk|en` (API: §7.1). 36 тем UK/EN — **той самий текст, що `core/constructor/help_topics.js`**; зіставлення тем перевіряє `tests/test_s6_help.py` (AC-130) |
| V-08+ | `publish_wizard_form` (розширення) | `td.publish.wizard` | Вкладки «Створення», «Перенесення», «Перейменування», «Атрибути, правила, обладнання» (за `kind`) замість однієї «Буде створено / оновлено»; лічильники «Перенесено · Перейменовано · Атрибути й обладнання · Без змін · Застосувати не можна»; поле «Зона або ряд» (`scope_slot_id`) і кнопки «Лише обране», «Вибрати все», «Зняти все»; нагадування про копію БД (`copy_reminder`, `copy_ack`); кнопка «Журнал публікацій» (`action_open_log`) |
| V-07+ | `layout_version_form_ops` | inherit `td.layout.version` форма | Кнопка «Відкотити публікацію» (`action_rollback`, `invisible` без `can_rollback`), банер «Публікацію відкочено …» / «Відкат недоступний: `rollback_reason`», вкладка «Операції в Odoo» (`op_ids`: `seq`, `op`, `res_model`, `code`, `before`, `after`, `rolled_back`) |

Меню (`views/td_menus.xml`; `groups=td_factory3d.group_td_user`, якщо не сказано; батько — `menu_td_constructor_plan`, якщо не сказано):

| XML-id | Назва | sequence | Дія |
|---|---|---|---|
| `menu_td_slot_type` | Типи місць | 50 | `action_td_slot_type` (`list,form`) |
| `menu_td_slot_preset` | Пресети місць | 55 | `action_td_slot_preset` |
| `menu_td_putaway_rule` | Правила розміщення | 60 | `action_td_putaway_rule` |
| `menu_td_replenish_rule` | Правила поповнення | 65 | `action_td_replenish_rule` |
| `menu_td_publish_op` | Журнал публікацій | 70 | `action_td_publish_op` |
| `menu_td_layout_variant` | Варіанти планування | 80 | `action_td_layout_variant` |
| `menu_td_comment` | Коментарі | 85 | `action_td_comment` («Коментарі конструктора») |
| `menu_td_zone_lock` | Блокування зон | 15 | `action_td_zone_lock` (`list`), батько `td_factory3d.menu_td_config`, `groups=group_td_constructor_manager` |
| `menu_td_constructor_help` | Інструкція конструктора | 2 | `action_td_help` (`ir.actions.act_url`) |

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

Правила ORM — перший бар'єр; другий — `_td_check_edit()` у `create/write/unlink` slot/placement/layer (пропускається при `env.su`; тексти уніфіковані): `AccessError("Шар «%s» редагує %s.")`. Публікація, відновлення версії, створення площадки, зміна `edit_group_ids`, `check.config` — лише `has_group('group_td_constructor_manager')`.
Сервіс публікації працює під `sudo()` + `with_company(site.company_id)` лише всередині `services.publish.apply_plan` **після** явної перевірки групи менеджера й стоп-крана `publish_enabled` (DEC-11, DEC-17); збереження чернетки (API-04) виконується від імені користувача **без** `sudo`.

### 4.5 Доповнення: права моделей злиття (хвилі 1–2)

Нові рядки `security/ir.model.access.csv` (скорочення груп — як у §4.1; `U` = `td_factory3d.group_td_user`; `PT`, `PS`, `PE`, `PM` — `group_td_constructor_technologist/storekeeper/engineer/manager`; `A` = `td_factory3d.group_td_admin`; колонки `read,write,create,unlink`):

| Модель | U | PT / PS / PE | PM | A | Примітка |
|---|---|---|---|---|---|
| `td.slot.type` | 1,0,0,0 | 1,1,1,0 | 1,1,1,1 | — | проєктувальники створюють лише власні типи (M-16); id `access_td_slot_type_{u,t,s,e,m}` |
| `td.slot.preset` | 1,0,0,0 | 1,1,1,0 | 1,1,1,1 | — | видаляє лише менеджер (перевірка в `unlink`); `access_td_slot_preset_{u,t,s,e,m}` |
| `td.putaway.rule`, `td.replenish.rule` | 1,0,0,0 | 1,1,1,1 | 1,1,1,1 | — | `access_td_putaway_rule_*`, `access_td_replenish_rule_*` |
| `td.publish.op` | 1,0,0,0 | — | — | 1,1,0,1 | пише лише сервіс публікації (`sudo`); `access_td_publish_op_{u,a}` |
| `td.layout.variant` | 1,0,0,0 | — | 1,1,1,1 | — | керує менеджер (R-40); `access_td_layout_variant_{u,m}` |
| `td.comment` | 1,0,0,0 | 1,1,1,1 | 1,1,1,1 | — | додає й вирішує через API-22 (`f3d_add` під `sudo` після перевірки групи `U`); `access_td_comment_{u,t,s,e,m}` |
| `td.zone.lock` | 1,0,0,0 | 1,1,1,1 | 1,1,1,1 | — | пише API-23 (під `sudo` з перевіркою ролі); `access_td_zone_lock_{u,t,s,e,m}` |

Record rules (глобальні, `perm_*` усі): `rule_td_slot_type_company`, `rule_td_slot_preset_company`, `rule_td_putaway_rule_company`, `rule_td_replenish_rule_company`, `rule_td_layout_variant_company`, `rule_td_comment_company`, `rule_td_zone_lock_company` —
`['|', ('company_id','=',False), ('company_id','in',company_ids)]`; `rule_td_publish_op_company` — `[('version_id.company_id','in',company_ids)]`. Права на шар (R-11) на правила, коментарі, варіанти й оренди **не поширюються** (шару в них немає); їхні обмеження — у M-18…M-23.
Серверні бар'єри понад ACL: типи/пресети (`AccessError` у `create/write/unlink`), варіанти (`_td_assert_manager`), коментарі (автор або «Проєктування»), оренди (R-39), `td.layer.items` (лише вміст шару — M-26).

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

### 5.4 Дані хвиль 1–2

- `data/td_slot_type_data.xml` (`noupdate="0"`): `term_slot_type_floor_spot` (`td.term` `slot_type`, `sequence=55`) і **50** `td.slot.type` з xml-id `slot_type_<code>` (`r01`, …): за групами 20 `rack`, 5 `floor`, 8 `special`, 12 `zone`, 5 `mobile`; за важливістю 16 × «●»
  (`relevance=2`), 19 × «○» (`1`), 15 × «—» (`0`). Файл **генерується** з `core/constructor/types_data.js` (Q9 CD-31: засіяти всі 50, показувати ●/○); його відповідність ядру перевіряє `tools/test_core_s1.mjs` (AC-79).
- `data/td_term_data.xml`: додано 10 `zone_function` і 4 `zone_attr` (M-30) у блоці `noupdate="1"` (назви й кольори, змінені користувачем, оновлення модуля не перезаписує); xml-id — `term_zone_function_<key>`, `term_zone_attr_<key>`.
- `data/params.xml` (`noupdate="1"`) — додано: `td.constructor.lock_ttl_s=300`, `lock_heartbeat_s=60`, `variants_max=12`, `versions_keep=50`, `stock_days=90` (період залишків/ABC, CD-31 Q8), `labels_max=5000` (макс. етикеток у PDF, F05). Таблиця налаштувань — ARCH §3.
- Міграції (`migrations/`, ідемпотентні): `19.0.1.0.1/post-migrate.py` (`seed.resync_site`: порожній план незміненого сіда), `19.0.1.2.0/post-migrate.py` (тип `floor_spot` додається в `allowed_slot_type_ids` наявних шарів «Склади»; чернетка не позначається зміненою),
  `19.0.1.3.0/pre-migrate.py` (прив'язка наявних термінів зони до xml-id до завантаження даних; самі терміни не змінюються). Міграція `post_migration` MERGE §3.6 (`type_id` за `template`, `addr=legacy`, `loc_tree='flat'`, `warehouse_id`) **не потрібна**: усі нові поля мають
  безпечні значення за замовчуванням (порожній `addr` = `legacy`, `loc_tree='flat'`), а `warehouse_id` порожній, доки його не вкаже користувач (AC-137).
- `uninstall_hook` — без змін: бізнес-записи Odoo не видаляються (§5.3); нові моделі видаляються разом із модулем (ORM).

## 6. Крони й фонові процеси

Немає. Конвертація STEP/IGES/IFC (R-20) — синхронна при завантаженні (API-09) із таймаутом `convert_timeout_s=60`; довші — статус `pending_conversion` і ручний запуск кнопкою «Спробувати перетворити» (`variant.action_retry_convert()`, технолог/менеджер). Окремий cron не створюється (Q-02). Хвилі 1–2 кронів теж не додають: прострочені оренди зон прибирає `td.zone.lock.f3d_purge` при кожному зверненні до API-23 (M-23), контрольні точки понад `versions_keep` — при створенні нової (API-24); публікації не видаляються ніколи.

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
**API-09** — перевірки: розмір `original`/`glb` ≤ `max_model_mb` (R-18), розширення з переліку R-15 (`.skp` відхиляється), права `T`/`M`; `glb` проходить `glb_meta` (R-19); `meta` від клієнта — довідково, трикутники й bbox перераховуються сервером; запис — `variant._td_set_model(...)`; для `step/stp/iges/igs/ifc` — `status='pending_conversion'` і виклик `_td_convert_model()`. Ліміти: 1 завантаження на варіант за раз (блокування рядка варіанта `FOR UPDATE NOWAIT`).

### 7.1 API-11…API-24 і додаткові маршрути (хвилі 1–2)

Правила — як у API-01…10 (префікс `/f3d/constructor`, `auth="user"`, `type="jsonrpc"`, `{ok: true, …}` або `{ok: false, code, message, …}` з HTTP 200, права від імені користувача, дані Odoo — під `sudo` лише в межах відповіді після перевірки групи).
Коди помилок, спільні для всіх: `not_found` (площадка/запис недоступні за `ir.rule` чи відсутні), `rights`, `validation`; решта — у таблиці. **Усі 14 API реалізовано** (на відміну від скелета W0-B, де вони повертали `not_implemented` з `controllers/stub.py`; зараз `stub.py` лишився як відповідь `/render/<kind>`,
якщо рендерер не зареєстровано, R-41). «Проєктування» = технолог, комірник, інженер або менеджер; «перегляд» = `td_factory3d.group_td_user`.

| API | Маршрут(и) | Тіло | Відповідь (`ok: true`) | Права; коди помилок |
|---|---|---|---|---|
| API-11 | `/library` | `{op: list|save|delete, kind?: type|preset, id?, vals?}` | `list` → `{types, presets}`; `save` → `{kind, record}`; `delete` → `{kind, id}` | list — перегляд; save — «Проєктування» (тип каталогу, `is_custom=False`, — лише менеджер); delete — менеджер, лише власні типи без місць. `vals` типу: `code` (лише при створенні), `name`, `description`, `group`, `template`, `shape`, `params`, `loc_kind`, `relevance`; пресету: `name`, `type_id`, `kind`, `data`. Зайві поля → `validation`; `IntegrityError` → `validation` |
| (F01) | `/site/addr` | `{site_id, addr?, loc_tree?, depth_mode?, renumber: 'new'|'all'}` | `{pinned, rev, draft_changes, has_changes, addr, loc_tree, depth_mode}` | менеджер або проєктувальник із правом на шар площадки; опублікованій площадці `renumber='all'` чи зміну `loc_tree` — лише менеджер (CD-31 Q2). `validation` (схема R-22) |
| API-12 | `/storage_categories` | `{op: list|save|delete, id?, vals?, confirm?}` | `list` → `{categories, strategies, functions, attrs}`; `save` → `{category}`; `delete` → `{id}` | list — перегляд; save/delete — менеджер **і** `confirm: true` (CD-20: прямий виклик Odoo); `vals = {name, max_weight ≥ 0, allow_new_product: empty|same|mixed, capacity?}`; категорія, що вже використовується, не видаляється |
| API-12 | `/removal_strategies` | `{}` | `{strategies}` | перегляд |
| API-12 | `/storage/loads` | `{site_id, codes?}` (≤ 5000) | `{loads: {код: {qty, weight_kg}}, limits}` — залишки й вага запасу за кодами комірок і ліміти ваги комірки | перегляд; `validation` |
| API-13 | `/stock/state` | `{site_id, codes?, days?, detail?, offset?, limit?}` | `{at, days, truncated, next, codes: {код: {qty, reserved, fill, in_date, age_days, moves, min, max, capacity, top_product, location_id, detail?}}}`; ≤ 2 МБ і ≤ 2000 локацій за відповідь; `detail` (рядки, рух, правила, категорія, запис) — лише для ≤ 20 кодів | перегляд; `days` 1…3650 (за замовч. `td.constructor.stock_days`); `codes` ≤ 5000 |
| API-14 | `/stock/find` | `{site_id, q, mode: any|product|lot|package}` | `{hits: [{code, items: [{product, ref, qty, lot, package}]}]}` (усі слова запиту — в одному залишку; ≤ 500) | перегляд; `q` ≤ 200 символів, непорожній |
| API-15 | `/putaway/where` | `{site_id, product_id, quantity?, location_id? | location_code?, package_type_id?}` | `{estimate: false, location: {id, code, name}, moved}` — «Куди покладе Odoo» (метод стратегії розміщення локації, лише застосовані правила) | перегляд; `validation` (товар), `not_found` (локація приймання чужої компанії) |
| API-15 | `/putaway/fit` | без `product_id`/`codes`: `{site_id}`; інакше `{site_id, product_id?, package_type_id?, codes}` (≤ 500) | `{rules: {uid: [{code, reason}]}}` — правила чернетки з проблемами; або `{items: {код: [причини]}}` — «Чи вміститься» | перегляд; `validation` (потрібен товар чи упаковка) |
| API-15 | `/putaway/lookup` | `{site_id, kind: product|category|package_type|location, term?, ids?, limit?}` | `{rows: [{id, name, code?}]}` (≤ 40, записи інших компаній не віддаються) | перегляд (лише читання, довідник для форм правил) |
| API-16 | `/odoo/locations` | `{site_id, op: feed|sync|baseline, warehouse_id?, offset?, limit?}` | `feed` → `{feed: {root, warehouse, locations: [{id, code, name, parent, parent_id, usage, barcode, qty, active}], total, truncated, next}}` (пачки до 20 000, стеля 50 000); `sync` → `{feed (без locations), diff: {appeared, disappeared, renamed, moved}, baseline: created|existing|missing}`; `baseline` → `{}` | перегляд; `baseline` і збереження бази при `sync` — менеджер чи проєктувальник шару |
| API-17 | `/codes/check` | `{site_id, codes: [str]}` | `{codes: {код: {state: free|own|match|busy, reason}}}` | перегляд; > 5000 кодів → `too_many` |
| API-18 | `/publish/log` | `{site_id, version_id?, limit?}` (≤ 100, 20) | `{versions: [{…, can_rollback, ops за видами}], can_rollback, ops?}` (з `version_id` — операції версії) | перегляд |
| API-18 | `/publish/rollback` | `{site_id, version_id, confirm: true}` | `{version: {id, n}, reverted, versions}` | менеджер; без `confirm` — `validation`; відмова відкату — `rollback_blocked` з `issues: [{code, reason}]` (R-32), збій у транзакції — `rollback` |
| API-19 | `/render/labels_pdf`, `/render/table_xlsx`, `/render/plan_pdf`, `/render/spec_pdf` | JSON-RPC-параметри = payload рендерера (R-34, R-36, R-38) | `{filename, mimetype, content}` (`content` — base64) | перегляд; `validation` (ліміти й схема payload), `rights`; рендерер не зареєстровано — `not_implemented` |
| API-20 | `/parse/table` | `{site_id?, filename, content (base64), sheet?}` | `{format: xlsx|csv, encoding?, delimiter?, sheets?, sheet?, rows, truncated}` | перегляд; файл > 25 МБ, > 200 000 рядків чи > 200 колонок — `validation` |
| (F10) | `/odoo/rules` | `{site_id, parse_rules}` | `{rev, draft_changes, has_changes}` | менеджер чи проєктувальник шару; `validation` (схема R-22); збільшує лічильник чернетки |
| API-21 | `/variants` | `{site_id, op: list|create|activate|rename|delete|end_training, id?, name?, metrics?, training?, activate?, keep?}` | `{variants: [{id, name, is_training, active, origin_id, base_version, metrics {cells, places, area, volume, max_weight, ops}, by, at}], active_id, training_id, max, can_edit, id, reload, draft: {rev, changes}}` | list — перегляд; решта — менеджер; `validation` (назва, ліміт 12, дубль, «активний/єдиний не видаляється», навчальна копія вже є) |
| API-22 | `/comments` | `{site_id, op: list|create|update|resolve|delete|assignees, id?, vals?, text?, resolved?}` | `{comments: [{id, target_kind, target_uid, target_label, kind, state, text, author, author_id, mine, assignee, assignee_id, at, resolved_by, resolved_at, can_resolve, can_delete}], at, id?}` (≤ 2000); `assignees` → `{users: [{id, name}], me}` | перегляд додає; `update`/`resolve`/`delete` — автор або «Проєктування» (M-22) |
| API-23 | `/locks` | `{site_id, op: list|acquire|release, zone_uid?}` | `{locks: [{zone_uid, user_id, user, mine, expires_at}], ttl, heartbeat, now, lock?, released?}`; `acquire` чужої зони → `{ok: false, code: 'locked', message («хто й до котрої»), lock, locks, ttl, heartbeat, now}` | list — перегляд; acquire/release — «Проєктування»; `zone_uid` рядок ≤ 32 |
| API-24 | `/version/view` | `{site_id}` або `{version_id}` | `{versions: [{id, n, kind, state, published_at, by, note, is_active, has_snapshot, counts}], keep}` або `{version, view: {site, layers, slots, placements, counts}}` (знімок R-14 у форматі API-03, лише читання) | перегляд |
| API-24 | `/version/checkpoint` | `{site_id, op: create, note?}` або `{op: note, version_id, note}` | `{version}` | create — «Проєктування» (знімок чернетки без публікації; старі точки понад `versions_keep` прибираються, публікації — ніколи, R-40); note — менеджер |
| (F16) | `/site/wizard` | `{site_id}` (читання) або `{site_id, state}` | `{wizard_state}` | менеджер чи проєктувальник шару; `state` — об'єкт ≤ 256 КБ, вкладеність ≤ 8; лічильник чернетки **не** змінюється |
| (F19) | `GET /help?lang=uk|en` (`type="http"`, `auth="user"`) | — | HTML-сторінка «Інструкція конструктора» (QWeb `td_constructor.td_help_page`, 36 тем) | будь-який користувач, мова за замовч. українська |

**Зміни API-03…API-07 (сумісні).** `load` додатково віддає: `site.{warehouse, addr, loc_tree, depth_mode, sprinkler_height, aisle_tech, parse_rules, wizard_state, active_variant, odoo_baseline_id, publish_copy_ack}`; `layers[].items`;
`slots[].{type_id, storage_category_id, removal_strategy_id, function_id, attr_ids, temp_min_c, temp_max_c, tech, addr, depth_mode}`; корінь `types`, `presets` (бібліотека, `ir.rule` компанії) і `rules: {putaway: […], replenish: […]}` (чернетки правил з `etag`, разом із позначеними `deleted`).
`save` приймає також `td.putaway.rule`, `td.replenish.rule` (поля M-18, M-19; посилання на `product.product`, `product.category`, `stock.location`, `stock.package.type`, `stock.storage.category`, `product.removal`, `td.term` перевіряються на існування й тип довідника: `function_id` →
`zone_function`, `attr_ids` → `zone_attr`), а в `td.layer` — `items`, у `td.slot` — нові поля M-27; невідомі ключі → `validation`. `publish` приймає `scope: [uid]` (застосувати лише рядки зон/рядів, батьки додаються самі) і `excluded: [[res_model, code]]` / `[[res_model, code, kind]]`
(рядки, що пропускаються), повертає ще `counts`, `ops` (кількість записів журналу), `skipped`. `publish/preview` і `validate` без змін контракту; `validate` тепер виконує й перевірки з реєстру `CHECKS` (R-41), якщо їхні налаштування увімкнено.

**Помилки й ідемпотентність нових API.** `locked` (API-23) — єдиний новий код очікуваної помилки, окрім `too_many` (API-17). Повторний `acquire` власної оренди продовжує її. `variants.create` з існуючою назвою — `validation`.
Вимкнений стоп-кран `publish_enabled` блокує публікацію (API-06/07, код `disabled`); відкат (API-18), читання API-12…API-17 і запис правил чернетки від нього не залежать.

## 8. Клієнтська й сервісна частини

Колектора й емулятора немає. Нижче — склад клієнтського коду й контракти між воркерами (ARCH §6). Кожен файл — ES-модуль `/** @odoo-module */`, імпорти `@td_constructor/<шлях>`; Odoo-сервіси: `orm`, `rpc`, `notification`, `action`, `dialog`.

### 8.1 Бібліотеки (DEC-06)

- **three.js — не вендориться ще раз.** Усе, що потребує `THREE`, імпортує `/td_viewer3d/static/lib/three/three-bundle.esm.js` (r160; експорти `THREE`, `GLTFLoader`, `OrbitControls`, `CSS2DObject`, `CSS2DRenderer`, `RoomEnvironment`). Єдиний спосіб — `loadThree()` у `static/src/{editor,model}/three.js` (динамічний `import()` за URL, як `core.js` переглядача; по одному невеликому файлу на воркера, без спільного коду).
- **Завантажувачі й експортер** (`OBJLoader`, `MTLLoader`, `STLLoader`, `FBXLoader`, `ColladaLoader`, `ThreeMFLoader`, `GLTFExporter`, `fflate`) відсутні в бандлі переглядача → W3 збирає `static/lib/f3d-loaders/f3d-loaders.esm.js` з `three@0.160.0/examples/jsm` скриптом `tools/build_loaders.mjs` (esbuild; `three` замінюється shim-модулем, що читає `globalThis.__F3D_THREE__`; `loadThree()` кладе туди `THREE` перед динамічним імпортом бандла). Файл комітиться, на сервері нічого не збирається. Заборонено: CDN, `<script src="http…">`, `fetch` на зовнішні адреси (DoD-перевірка — grep, AC-05).
- **dxf-parser@1.1.2** (UMD, глобал `DxfParser`) — `static/lib/dxf-parser/dxf-parser.min.js`, лінивий `loadJS` (W2).

### 8.2 W2: клієнтська дія `f3d_constructor` (DEC-08)

> **Оновлено в v0.2 (CD-29, W0-A).** Код редактора, описаний нижче, тепер у `factory3d/core/constructor/*` (один на модуль і прототип), `OdooStore` став `OdooAdapter` (`adapter_odoo.js`, ті самі виклики API-01…API-08 плюс API-11…API-24), у `static/src/editor/` лишилися `core_loader.js` і `odoo_host.js`; див. §8.4. Нижче — початкове рішення W2, поведінка якого збережена.

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

### 8.4 Ядро + адаптер (CD-29, W0-A): що змінилося в §8.2–8.3

**Заміна W2.** Редактор більше не складається з `static/src/editor/{store,cells,checks,scene,…}.js`. Один код `factory3d/core/constructor/*` (JS + Three.js, **без** `@web`, `@odoo`, `@td_constructor`, `window.claude`, `fetch`; лише відносні імпорти — перевіряє `node tools/test_core.mjs`) обслуговує і модуль, і прототип-артефакт.
Нижче «Odoo» і «артефакт» — два **адаптери** одного контракту (`core/constructor/adapter.js`); решта ядра нічого про Odoo не знає (`stock.*` знає лише `adapter_odoo.js`, CD-30).

| Частина | Файли | Роль |
|---|---|---|
| Точка входу | `index.js` | `mountEditor(host, adapter)`, `unmountEditor`, реєстри, простори імен для тестів і мостів («Переглядач» бере з ядра геометрію й генерацію комірок, не копіюючи їх) |
| Контракт адаптера | `adapter.js` | `BaseAdapter`, `assertAdapter`, `newUid`, `StoreError`; методи: `load(siteId)`, `save(state, {now})`, `flush()`, `check(layerId?)`, `publish({onClose, state})`, `uploadModel`, `restoreVersion`, `listSites`, `createSite`, `saveSite`, `saveCheck`, `loadModel`, `attachUnderlay/detachUnderlay/loadUnderlay`, `ensureGroupIds`, `capabilities`; зворотні виклики `onStatus/onSaved/onConflict/onReject/onReload`; методи можливостей — `library`, `saveAddr`, `categories`, `stockLoads`, `stock`, `find`, `putawayWhere/putawayFit`, `lookup`, `codesCheck`, `locations`/`sync`, `saveParseRules`, `parseTable`, `planLog/planOps/rollback`, `render`, `saveWizard`, `warehouses`, `variants`, `comments`, `locks`, `versions` |
| Адаптер Odoo | `adapter_odoo.js` | `OdooAdapter`: API `/f3d/constructor/*` (§7, §7.1), `rpc`, `orm`, `action`, `uploadModel` передає хост; перетворення API↔стан, черга `save` з `etag`/`id_map`, повтори 2/5/15 с |
| Адаптер артефакта | `artifact/adapter_artifact.js`, `artifact/odoo_sim.js`, `artifact/{storage,sample,sample_locations,demo_stock,collab_artifact,checks_extra,dialogs,preview}.js` | `ArtifactAdapter`: база артефакта (`window.claude.use("db")` → `localStorage` → пам'ять, IndexedDB; **один документ на вариант**, бюджет 256 КіБ, `storage.js`); `odoo_sim.js` імітує «Odoo» прототипа (план, журнал, відкат, категорії, «чи вміститься», «куди покладе» як «оцінка», демо-залишки з позначкою «демо») |
| Хост | модуль: `static/src/action/constructor_action.js` (Owl, `registry.category("actions")` `f3d_constructor`) + `static/src/editor/odoo_host.js` (three.js з бандла переглядача, `buildGenericModel`, завантаження моделей API-09, діалоги форм Odoo `variantForm`/`passportForm`/`record`) + `core_loader.js` (динамічний `import()` ядра); прототип: `build/constructor/proto/src/main.js` + `page.css` |

**Можливості (`capabilities`).** Адаптер оголошує, що вміє; ядро ховає функції, яких немає (`can(name)`):

| Можливість | Що вмикає | Odoo | Артефакт |
|---|---|---|---|
| `publish` | публікація/план | так (API-06/07) | так (імітація) |
| `check` | «Перевірити на сервері» | так (API-05) | ні (локальні перевірки) |
| `library` | типи й пресети | так (API-11) | так (`db`) |
| `storage` | категорії зберігання, стратегії | так (API-12) | імітація |
| `stock` | залишки, пошук «де лежить», теплові карти | так (API-13/14) | демо-синтетика з позначкою «демо» |
| `putaway` | «Куди покладе Odoo», «Чи вміститься» | так (API-15) | «оцінка» ядра |
| `odoo_import` | структура з Odoo, розбіжності | так (API-16, `/odoo/rules`) | демо-стрічка |
| `rollback` | журнал і відкат | так (API-18) | імітація |
| `render` | PDF/XLSX на сервері | так (API-19) | ні («PDF формує сервер»); ZPL, CSV, PNG — локально |
| `files` | розбір XLSX на сервері | так (API-20) | ні (XLSX/CSV читає ядро) |
| `variants` | варіанти планування | так (API-21) | так (`db`) |
| `comments` | коментарі й задачі | так (API-22) | так (`db`, без виконавців і завдань) |
| `locks` | оренда зон | так (API-23) | **ні** (блокування не емулюються) |

**Збірка.** `node tools/build_core.mjs module [--check]` → `odoo_addons/td_constructor/static/lib/f3d-core/constructor.esm.js` (esbuild, ESM, без three.js; ≈ 1 МБ; **коміт**; на сервері не збирається) і оновлює `CORE_BUILD` (хеш) у `static/src/editor/core_loader.js` (скидання кешу браузера: `import(CORE_URL?v=CORE_BUILD)`);
`--check` — лише перевірити свіжість (код 1, якщо ні). `node tools/build_core.mjs proto --out <файл.js>` збирає IIFE прототипа з `build/constructor/proto/src/main.js` + `core/constructor/artifact/*`; його викликає `build/constructor/proto/build.py` (склеює в один `index.html`; `F3D_PROTO_MINIFY=1` — мінімізований; **бюджет 900 КБ**, після S6 — 833 КБ).
Каталог `ESBUILD_DIR` (з `node_modules/esbuild`) — змінна середовища, інакше збірка робить `npm install esbuild` у тимчасовий каталог. Після правки `core/` треба **перезібрати модуль і закомітити** збірку (конфлікт у ній розв'язується перезбіркою). Умовні 3D-моделі й завантажувачі (`static/src/model/*`, W3) лишаються в модулі: хост передає `buildGenericModel`/`loadLoaders`.

### 8.5 Правила ядра без дзеркала в Python (F09, F16, F17, N-01, N-02, F19)

Це алгоритми редактора: вони пишуть у БД лише звичайними правками (API-04) або через уже описані API; серверних дублів немає. Тести — `tools/test_core_s*.mjs`, HOOT `static/tests/editor/s*.test.js`, Playwright `build/constructor/proto/test_s*.js` (§13.6).

- **Скасування й повтор (F09-01, `undo.js`):** знімок стану після кожної зміни (шари, місця, розміщення, правила `S.site.rules`, поля площадки: адресація, габарит, крок колон, висоти, техніка); ≤ 100 кроків і ≤ 30 млн символів знімків; підпис кроку `E.undoLabel`/`E.commit({label})`;
  Ctrl+Z, Ctrl+Shift+Z / Ctrl+Y, кнопки ↶ ↷; відновлення — звичайний `E.commit`, тож адаптер сам ставить `create/write/unlink`; зміну адресації відновлює `saveAddr`, габарит і крок колон — `E.saveSiteProps`, висоту спринклерів і техніку — `adapter.saveSite`.
- **Мультивиділення й інструменти (F09-02…05, 08…10):** `S.multi`; Ctrl+клік, рамка Shift у «Плані»; групове перетягування зі збереженням взаємного положення; `R` повертає ряди; Ctrl+D дублює (ярус — зверху, стелаж — у кінці ряду, ряд — зі наступним номером `R3→R7`, місце на підлозі — зі наступним кодом, зона — «копія»);
  Ctrl+C/V — у виділений об'єкт, якщо підходить, інакше в найближчий придатний рівень, інакше поруч (копія тієї самої конструкції, місця нові й порожні); масив N×M, масове створення в зоні; вирівнювання (лівий/правий/верх/низ/центр X/Y), розподіл (≥ 3), групування в нову зону й розгрупування (коди не змінюються).
- **Автораскладка (F17, `autolayout.js`):** `autoLayoutZone(id)` — ряди вглиб у межах зони (її розмір фіксований); `autoLayoutSite({layerId})` — зони полицями по горизонталі в контурі, ряди вглиб у зонах (зона без `fixed` отримує розмір за вмістом); чисті `layoutLines`, `packRects`, `layoutPlan` стану не чіпають; застосування — **один** `E.commit`;
  номери рядів і коди зон перед рухом закріплюються (коди комірок не залежать від геометрії, R-25). Не вміщається — **нічого не змінюється**, повідомлення називає потрібний розмір. *Перешкоди* (`layerObstacles`): проходи й пожежні шляхи шару, `layer.items` (R-37), розміщення шару, місця під верстати, об'єкти будівлі (`obstacleRects`: колони, стіни, офіс, зарядка шарів `building` **і** колони сітки `site.column_grid`
  0.4×0.4 м у вузлах; ворота, док, двері — прорізи); стіни не під кратним 90° кутом перевіряються за справжньою формою (SAT). *Контур* (`regionOf`): `bounds` шару (многокутник ≥ 3 точок) → контур шару `building` → габарит площадки; зона має лежати цілком усередині (`obbInsidePolygon`, відступ 0.5 м); зони з `locked` не рухаються.
  **Колони сітки обходяться, поки це можливо:** якщо з ними зони не вміщаються, а без них вміщаються (крок сітки менший за зону), розкладка йде **без колон сітки** (`layoutAroundBuilding` → `gridIgnored: true`, у повідомленні названо крок); стіни, офіс, зарядка й явні колони `items` дотримуються завжди. Після такої розкладки блоки можуть стояти «в колонах» сітки,
  і це **показує перевірка `inside`**: вона бачить ті самі колони сітки (R-37 п. 2, 4; Q-19 закрито у `19.0.1.4.1`), тож у режимі `block` такий план не публікується. Так само розкладає `structure.js` (імпорт структури з Odoo).
- **Майстер «З нуля» (F16, `wizard.js`):** кроки Будівля → Зони → Ряди → Адресація → Перевірки → План змін; склад Odoo вибирається (`warehouses()`), **склад не створюється**; кожен крок — звичайна зміна (Ctrl+Z); повторне «Застосувати» кроку замінює створене ним; значення форм і створене зберігаються в `site.wizard_state` (`/site/wizard`, без зміни лічильника чернетки);
  результат — «Застосувати в Odoo…» (план R-31) або «Файл для імпорту…».
- **Рівні й мініатюра (N-01, `levels.js`, `minimap.js`):** рівні WH › зона › ряд › стелаж › ярус; вибраний рівень ховає решту (хук кадру), камера наїжджає, «↑» (U) — рівень вище, «⟲» — скинути; «Клік виділяє: Місце / Стелаж / Ряд / Зона», повторний клік піднімає вибір; мініатюра — контур, зони, місця й обладнання з рамкою поточного виду (проєкція кутів екрана на підлогу), клік/перетягування переносить камеру.
  `scene.js` не змінюється: видимість — хук `pre` кадру, значки — шар накладок (`collab_ui.js`).
- **Ролі в UI (N-02, `draft.js`):** `E.access()` → «Перегляд» (`group_td_user`), «Проєктування» (ролі конструктора), «Застосування» (`canPublish()`: менеджер і `publish_enabled`; не на телефоні); недоступні кнопки неактивні з підказкою `E.accessHint`; сервер права все одно перевіряє (R-11). Статуси об'єктів (N-05, N-08): «не збережено», «нове · лише в моделі», «з Odoo».
- **Мобільний режим (F06-04, CD-31 Q11, `s3_chrome.js`):** до 768 px — згорнута панель (☰), пошук зверху, картка на весь екран, жести; **лише перегляд і пошук**, без правки й без переміщень товару; редагування вимкнене. Тури на телефоні недоступні.
- **Тури, інструкція, мови (F19, `tours.js`, `tour_defs.js`, `help_topics.js`, `i18n.js`):** тур новачка (13 кроків; пропозиція при першому вході) і 11 тематичних (`basic`, `rack`, `import`, `scratch`, `address`, `putaway`, `apply`, `find`, `labels`, `docs`, `team`); кроки `read` і `do` («Показати мені»); запуск зі списку чи `#tour-<id>`; ←/→/Esc; «пройдено» — у браузері. Тур, що змінює дані, йде в навчальній копії (R-40 п. 3).
  «Інструкція» — 36 тем UK/EN, **ті самі тексти** на сторінці Odoo `/f3d/constructor/help` (V-18). Мова: перемикач UK/EN, вибір у браузері (`f3d_constructor_lang`), без вибору — `host.lang`, інакше UK; українська — ключ: `t("Українська фраза")`. `t()` застосовано лише у файлах S6 (7 файлів); решту ядра перекладає **DOM-перекладач** `i18n.js` (точні фрази й шаблони, атрибути `title`/`placeholder`/`aria-label`) — див. Q-15.
  Окремі тури Odoo (`web_tour`) — `static/src/tours/*` у `web.assets_tests` (AC-131).

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

`_td_convert_model()` (не кидає винятків): (1) якщо `convert_server_enabled=False` → `pending_conversion`, «Серверне перетворення вимкнено»; (2) конвертер за `meta.format`: `step/stp` → `cascadio` (`import cascadio`, `cascadio.step_to_glb(in, out)` — **ПРИПУЩЕННЯ** щодо API), `ifc` → виконуваний `IfcConvert` (IfcOpenShell; `shutil.which`; `IfcConvert in.ifc out.glb`), `iges/igs` — конвертера немає; (3) немає конвертера/бібліотеки → статус лишається `pending_conversion`, `meta.message = "Перетворення STEP/IFC на сервері недоступне: бібліотеку не встановлено (cascadio / IfcConvert). Оригінал збережено; експортуйте модель у GLB або OBJ."`; (4) є → тимчасовий каталог, запуск із таймаутом 60 с, читання GLB, `glb_meta` (R-19), `_td_set_model(glb=…, status='ok', converted_by='server')` (**ПРИПУЩЕННЯ**: вихід у метрах); помилка/таймаут → `error`, `meta.message` з причиною. Реєстр `services.convert.CONVERTERS = {ext: (probe(), run(in_path, out_path, timeout))}` розширюється без змін ядра (тест підміняє його).

### R-21 Лічильник чернетки й `etag`

`etag = write_date.strftime('%Y-%m-%d %H:%M:%S.%f')`. `_td_touch(n)`: SQL `UPDATE td_site SET draft_rev = draft_rev + 1, draft_changes = draft_changes + n WHERE id=%s` (без зміни `write_date` площадки). `has_changes = draft_rev != published_rev`. API-04: для `write/unlink` порівнюється `etag` запису з поточним `write_date`; розбіжність → `conflict` без змін. `draft_changes` = кількість змінених сутностей з моменту діючої версії (збільшується на число операцій; обнуляється публікацією/відновленням діючої).

### R-22 Схеми JSON-полів

`aisles[]`: `{id: str 1…32, name: str ≤64, x0<x1, y0<y1: finite float}`; `fire_paths[]` — те саме + `kind ∈ {path, exit}`; `utilities[]`: `{id, kind ∈ {electric, air, dust, panel}, name, x, y, z=0}`; `bounds`: `[[x,y],…]` ≥3, не самоперетинний; `underlay_params`: `unit ∈ {mm,m}`, `dx,dy,rot_deg,scale>0,opacity∈[0,1]`; `variant.utilities[]`: `{kind ∈ {electric, air, dust}, x_mm, y_mm, z_mm}`; `slot.overrides[code]`: ключі `disabled|max_load_kg|capacity|name`; `check.params`: R-04. Невідомі ключі відкидаються при `write` (не помилка), типи/діапазони — `ValidationError` із вказанням індексу елемента.

### R-23 Порожня площадка й типові значення

`_td_init_blank()`: будівля 60×30×8, крок колон 6×6; шари (`sequence` 10…50): «Будівля» (`building`, 0.0, `edit_group_ids` порожні, типи `zone`), «Склади» (`storage`, 0.0, комірник, типи `pallet_rack, cantilever, shelf, floor_stack`), «Виробництво» (`production`, 0.0, технолог, `machine_spot, zone`), «Інженерні мережі» (`engineering`, +6.0, інженер, `zone`), «Двір» (`yard`, 0.0, порожні, `zone`); `grid_step_m=0.5`, `aisle_width_m=3.0`; кольори `#9aa5b1`, `#e8a33d`, `#5b7c99`, `#c0392b`, `#6aa84f`. Каталог — 4 типові варіанти з §5.1. Для нового варіанта `allowed_layer_kind_ids` за категорією: `machine`→production; `rack`→storage; `forklift`→storage, production, yard; `conveyor`→production; `panel`→production, engineering; `robot`→production; `other`→усі.

### R-24 Порядок хука й ідемпотентність

Описано в §5.2 (кроки 1–6). Критерій ідемпотентності: два запуски `post_init_hook` поспіль → однакова кількість записів у всіх моделях конструктора, `seed_report` однаковий, жоден `stock.location`/`maintenance.equipment` не створений і не змінений, крім полів `td_site_id`, `td_slot_uid`, `td_placement_uid`, `equipment_id`, `workcenter_id`.

### 9.1 Правила злиття (R-25…R-41)

Джерело — `services/*.py` (чисті функції з дзеркалами в `core/constructor/*.js`; «золоті» фікстури: `static/tests/fixtures/{addr_golden,cells_s1_golden,s2_fit_cases,s3_barcode_golden,s5_golden}.json`, `tests/golden_*.py`). Контекст рішень — `build/constructor/MERGE.md` §2; «CD-31 Qn» — відповіді замовника.
Зеркала Python↔JS ведуться **лише** там, де потрібні запис в Odoo чи блокування публікації: адресація й генерація комірок (R-25, R-26), перевірки (R-29, R-37), «чи вміститься» (R-30), розбір таблиць (R-36), Code128 (R-34), специфікація стелажів (R-38), розбір правил (R-35). Решта алгоритмів — лише в ядрі (§8.5).

### R-25 Адресація: шаблон коду, сегменти, напрями (F01; `services/addr.py` ↔ `core/constructor/addr_core.js`)

`addr` (JSON площадки, зони-контуру чи місця; R-22) — або порожній `{}` (пресет **`legacy`**: коди як у R-01, жодних змін у seed і золотих фікстурах), або повний вигляд (є `tpl`):
`{tpl, sep, seg: {zone|row|bay|level|pos: {kind: num|alpha, width 1…8, start 0…999 (alpha: 1…999)}}, row_from: up|down|left|right, row_mode: seq|snake, bay_dir: ltr|rtl|odd_even, level_dir: up|down, zone_code?, row_no?, legacy?}`.

1. **Шаблон** `tpl` (≤ 64 символи): слова через пробіл; слово = літери/цифри/`._/#:-` + `{сегмент}`; сегменти `{zone} {row} {bay} {level} {pos}` і `{prefix}` (= `code_prefix` місця); синоніми UK `{зона} {ряд} {секція} {ярус} {позиція} {префікс}` і EN `{aisle} {section} {tier} {position}`;
   сегмент — не більше разу; слово, у якому немає значення сегмента, **пропускається цілком**; слова з'єднує `sep` (≤ 3 символи, за замовч. `-`). Код ≤ 32 символи (`CB-01`). Шаблон за замовч. `{zone} {row} {bay} {level} {pos}`.
2. **Пресети** (`PRESETS`): `legacy`, `zone_row_bay_level`, `prefix_bay_level` (`{prefix} B{bay} L{level} {pos}`), `prefix_bay_letter` (`{prefix} {bay}{level} {pos}`, ярус літерою), `row_odd_even` (непарні/парні секції по сторонах проходу).
3. **Область дії:** діють найближчі власні налаштування — місце → зона-контур, що його містить → площадка (`effective_addr`). Власні налаштування = є `tpl` або `legacy: true`; часткові вигляди `{row_no}` (закріплений номер ряду), `{zone_code}` (код зони замість номера, ≤ 8 символів) успадковують шаблон.
4. **Номер ряду:** ряди (`pallet_rack`, `cantilever`, `shelf`, `floor_stack`) зони чи шару нумеруються за геометрією відносно `row_from` (`up`/`down` — за Y, `left`/`right` — за X); закріплені `row_no` лишаються, нові беруть вільні номери; `row_mode=snake` змінює напрям у парних рядах.
   Напрям секцій: `ltr` — зліва направо (у повернутих на 90°/270° — зверху вниз), `rtl`, `odd_even` — непарні/парні по сторонах проходу; двосторонні ряди продовжують нумерацію; `level_dir=down` — ярус 1 вгорі.
5. **Місця на підлозі** (`floor_spot`, R-26) нумеруються **першим доступним сегментом** шаблону в порядку `pos`, `row`, `bay`, `level` за геометрією в зоні (F01-08).
6. **Що йде в Odoo** (`location_vals(code, parts, addr, loc_tree)` → `{name, barcode, td_row, td_bay, td_level, td_pos}`): `barcode = td_code` = повний код; `name` — повний код при `loc_tree='flat'` і **коротке ім'я** (останнє слово шаблону) при `row`/`section`; `td_*` — логічні номери
   сегментів (0 — немає). Ієрархія при `row`/`section`: батьківська віртуальна локація на ряд (створює публікація, R-31; секції локаціями не стають — CD-31 Q1).
7. **Глибина** `depth_mode`: `level` — останній рівень-локація = ярус; `cell` — ярус ділиться на `cells_per_level` (1…12) локацій `<код ярусу>-1…N` вздовж X (F01-10; генератор — R-26).
8. **Застосування** (`/site/addr`, `td.site._td_apply_addr(vals, renumber)`): `renumber='new'` (за замовч., CD-31 Q2) — місця з уже опублікованими локаціями й без власних налаштувань **закріплюють** поточну адресацію й номер ряду (коди не змінюються), нові беруть нову;
   `'all'` — зняти закріплення й перенумерувати все за геометрією (опублікованій площадці — лише менеджер: змінюються імена й штрихкоди, потрібні нові етикетки). Ручні правки комірок (`overrides`) і розміщення (`cell_code`) переносяться на нові коди за порядком комірок (`_td_renumber`); якщо число комірок змінилося (глибина «комірка»), ключі `overrides` без пари відкидаються, а розміщення лишаються без змін.
   Результат — звичайна правка чернетки (`_td_touch`).
9. **Колізії:** попередній перегляд у ядрі (перші 10 кодів і останній, скільки кодів зміниться, чи є повтори); унікальність — R-29 (`code_conflict`) і `conflict_codes` публікації (R-31).

Приклад: `{tpl: "{zone} {row} {bay} {level}"}` з умовчаннями сегментів (зона — літера, ряд і секція — 2 цифри, ярус — 1), зона 1, ряд 2, секція 3, ярус 4 → `A-02-03-4` (штрихкод і `td_code`); при `loc_tree='row'|'section'` ім'я локації — останнє слово (`4`), повний код лишається в штрихкоді. Еталонні значення — `addr_golden.json`.

### R-26 Генератори комірок v2 (F08, F01-08/10; `services/cells.py` ↔ `cells.js`)

Доповнює R-01; без явно заданих нових параметрів результат **байт-в-байт** як у R-01 (золоті `cells_golden.json`, `cells_s1_golden.json`).

- Нове значення `template`: **`floor_spot`** («Місце на підлозі (одна локація)») — прямокутник на підлозі = ОДНА комірка з кодом `code_prefix` (або кодом за адресацією, R-25 п. 5); параметри `length` 0.1…200 (1.2), `width` 0.1…200 (0.8), `height` 0…30 (1.5), `max_load_kg` ≥ 0 (0), `capacity` ≥ 0 (0);
  вибір `loc_kind` (за замовч. `area`) і `shape` (за замовч. `zone`). Для буферних, технологічних зон, мобільних носіїв, воріт. Вхід у `PRESET_TEMPLATES`, `SPOT_TEMPLATES`, дозволений тип шару «Склади» (міграція 19.0.1.2.0).
- Необов'язкові параметри стелажів (потрапляють у нормалізований словник **лише коли задані**): `bottom_on_floor` (за замовч. `True`; `False` — нижній ярус на `BOTTOM_LIFT = 0.15` м), `double_sided` (двосторонній ряд: `sides = 2`), `gap_x`, `gap_y` (0…2), `beam_th` (0…0.3), `slope` (0…20),
  `cells_per_level` (1…12), `level_heights` (список висот ярусів, 0.1…3), для `pallet_rack` — `deep` (1…6, глибина складування в паллетах); вибір `code_style` (`default`, `bay_letter`, `exact`), `loc_kind`, `shape` (з `SHAPE_KEYS`, M-16). `floor_stack` приймає `gap_x`, `gap_y`.
- `index_digits` (1…4, за замовч. 2) — ширина індексу; `exact`-стиль розширює межі `cell_l`, `cell_w` (0.1…200), `max_height` (0.05…30).
- `overrides[code]` — ключі `disabled`, `max_load_kg`, `capacity`, `name`, `usage` (`internal`/`view`), `replenish_location` (булеве); невідомі ключі відкидаються.
- Глибина `cell` (R-25 п. 7) застосовується до шаблонів з ярусами; контекст адресації `ctx = {addr, zone, row, spot, depth_mode}` передається у `generate_cells`, без `ctx` — legacy-коди.

### R-27 Тип місця, пресет, каталог 50 (F08, F09-06/07; `models/td_slot_type.py`, `td_slot_preset.py`, `types_data.js`)

1. **Каталог:** 50 типів у 5 групах (20/5/8/12/5) на **семи генераторах** (`pallet_rack`, `cantilever`, `shelf`, `floor_stack`, `floor_spot`, `machine_spot`, `zone`; для типів-ворота/док — без генератора), `relevance` 2/1/0 (●/○/—); за замовч. UI показує ● і ○ (CD-31 Q9).
   Єдине джерело — `types_data.js`; XML і прототип його дзеркалять.
2. **Місце з типу:** нове `td.slot` отримує `type_id`, `template` і `params` типу; `_check_type` вимагає `type.template == slot.template`. Параметри місця — його власні («Конструкція ряду» перевизначає тип, «Як у типу» повертає); зміна розміру типу в проєкті пересобирає параметри всіх місць цього типу
   (бібліотека при цьому **не** змінюється, F08-05).
3. **Бібліотека** (F09-07): типи й пресети — на компанію (`company_id`); власні типи позначені `is_custom`. Пресет — `row`, `section` чи `group` (R-22: `data` нормалізується сервером). Вставка пресету — у ядрі: зона → ряд ×N, ряд → секція(ї), група — у зону чи точку; нові місця отримують вільні коди.
4. Каталог змінює лише менеджер; тип, що використовується місцями, не видаляється; ключ `code` не змінюється.

### R-28 Категорія зберігання, стратегія списання, функція й атрибути зони, прапорці (F03; `services/capacity.py`, `publish.py`)

1. **Наслідування вниз** (`publish.zone_chain`, `inherited`): для `storage_category_id` і `removal_strategy_id` діє значення місця, інакше найближчої зони з непорожнім значенням (ланцюжок зон, що містять **центр комірки**, від найменшої площі до найбільшої; вкладена зона перекриває далеку). «Без категорії» на місці — порожнє значення, що наслідується.
2. **Категорії зберігання** (`stock.storage.category` + ємності) створює/змінює/видаляє менеджер прямим викликом API-12 з `confirm: true` (CD-20; у план публікації вони не входять): `name` (обов'язкова), `max_weight ≥ 0`, `allow_new_product` ∈ (`empty`, `same`, `mixed`), `capacity` ≤ 200 рядків
   (товар/упаковка → кількість). Використовувану категорію видалити не можна.
3. **Функція зони** (10 значень `td.term` `zone_function`, колір рамки й підпису) і **атрибути зони** (4 `zone_attr`; температурний режим `temp_min_c…temp_max_c`, обидві 0 — не задано) наслідуються вниз і живуть лише в проєкті (в Odoo не пишуться).
4. **Прапорці локації** (`overrides[code].usage`, `.replenish_location`; `publish.flag_vals/flag_problem`): рядок плану `attrs` змінює `usage`/`replenish_location`; **заборонено** (`blocked`, мітка `stock` / `replenish_usage` / `replenish_nested`) — зробити `view` локацію із залишком, поставити «місце поповнення»
   не внутрішній локації чи вкладене в батька/нащадка, що вже є місцем поповнення.
5. **Ємність і заповнення:** межа ваги комірки = `max_load_kg` (перевизначення/шаблон), інакше `max_weight` категорії (`capacity.site_cell_limits`); заповнення `fill` (R-33) = частка ємності за кількістю товару категорії, інакше вага запасу проти межі; `None` — ємність не задано.
   Зведення ємності зони/площадки (місць, палетомісць, площа, об'єм, ємність у кг) — у ядрі (`capacity_core.js`, F03-08); ті самі цифри (`cells`, `places`, `area`, `volume`, `max_weight`) порівнюють варіанти (R-40).

### R-29 Перевірки даних Odoo: `cell_load`, `putaway_fit`, `code_conflict` (F03, F04, F01-07; реєстр `CHECKS`, R-41)

Перевірки чисті (без ORM): дані з БД кладе в `scene.extra` будівник плану (`capacity.plan_check_scene`), тому **«живі» перевірки в редакторі й на сервері працюють лише з даними, що їх подав адаптер**; без даних — порожньо. `severity = config.mode` (`warn`/`block`), рядок
`td.check.config` створюється при першому вмиканні (M-30).

| Ключ | `sequence` у реєстрі | Умова зауваження | Повідомлення |
|---|---|---|---|
| `cell_load` | 80 | `extra.loads[код].weight_kg > межа + eps`, межа = `extra.limits[код]`, інакше `max_load_kg` комірки; межа 0 — не перевіряється | «{код}: вага запасу {x} кг перевищує допустимі {y} кг» |
| `putaway_fit` | 90 | для кожного правила чернетки (`extra.putaway`, без `deleted`) з ціллю-коміркою чернетки: `fit_problems` (R-30) непорожні | «Правило «{мітка}»: не вміститься в {код} — {причина}» |
| `code_conflict` | 95 | `extra.code_states[код].state == 'busy'` (R-31: код зайнятий іншою площадкою/компанією, архівною, не внутрішньою локацією, локацією іншого складу чи збігається з кількома) | «{код}: {причина}» |

Без налаштування `code_conflict` план публікації дає такі зауваження як `warn` (`publish._code_mode`); з налаштуванням (навіть вимкненим) — тільки перевірка.

### R-30 Правила розміщення й поповнення (F04, F03-07; `services/putaway.py`, `capacity.py`)

1. **Чернетка → Odoo лише публікацією** (CD-31 Q4): `td.putaway.rule` → `stock.putaway.rule`, `td.replenish.rule` → `stock.warehouse.orderpoint`; рядки плану `res_model` = `stock.putaway.rule` / `stock.warehouse.orderpoint` (`PLAN_BUILDERS` `putaway`, `capacity`; застосовувачі `publish.APPLIERS`).
   Збіг із наявним правилом Odoo за тими самими умовами — прив'язка (`odoo_rule_id`/`odoo_orderpoint_id`), не дублікат. Правило, що веде в комірку, ще не опубліковану (`out_code`), залежить від рядка її створення (`depends_code`). **Неповне** правило (немає цілі чи умови) і правило з невідомою ціллю — `blocked`, не публікується.
   Видалення в чернетці (`deleted=True` або `active=False`) → рядок `archive` (`explicit`, не пропозиція) → у Odoo `active=False` із записом у журнал; відкат повертає (R-32).
2. **«Куди покладе Odoo»** (`putaway.where`, API-15): товар, кількість, упаковка, локація приймання (за замовч. `default_location_in(site)`) → метод стратегії розміщення локації `_get_putaway_strategy`, **лише застосовані** правила (чернетка не враховується); `{location: {id, code, name}, moved}`;
   режим `closest_location` зберігає категорію зберігання. В артефакті — «оцінка» ядра (`estimate: true`).
3. **«Чи вміститься»** (`fit_problems(item, cell, limit_kg, eps=1e-6)`): причини (українською), коли: вага товару > межі ваги комірки; об'єм товару > об'єму комірки; вага упаковки (`max_weight`) > межі; відсортовані габарити упаковки (`packaging_length`, `width`, `height`) не вміщуються у відсортовані `l×w×h` комірки.
   Невідомі (нульові) величини пропускаються. Одиниці — до метрів/кг/м³ за конфігурацією Odoo (`capacity.unit_factors`). Спільні випадки — `static/tests/fixtures/s2_fit_cases.json` (Python і JS читають один файл).
4. **Правила в картці місця** (F04-07) і підсвічування цілі (F04-04) — ядро; список «Правила розміщення сюди» береться з `rules.putaway` (API-03) за `out_code`/`out_location_id`/категорією зберігання.
5. **Мін/макс** (`td.replenish.rule`): `min_qty ≥ 0`, `max_qty ≥ min_qty`; `cell_code` або `location_id`; при публікації для комірки чернетки — залежність від рядка її створення; місце поповнення не вкладається (R-28 п. 4).

### R-31 План змін v2 (F02, F02-10/11; `services/publish.py`)

Розширює R-12/R-13. **Види рядка** (`kind`): `create` (з батьками: `depends_code`), `move` (інший батько), `rename` (ім'я/код), `attrs` (штрихкод, вид, місткість, категорія зберігання, стратегія списання, прапорці, відновлення з архіву), `update` (обладнання й робочі центри), `archive`.
Збіг із наявними записами — за `td_code`, потім `barcode` (комірки) / `serial_no` (обладнання) / `td_alias`: дублікатів не створюємо, нічого не видаляємо; зайве — лише пропозиція архівації для записів із `td_site_id` площадки (`selected=False`).

1. **Порядок застосування (одна транзакція):** створення (батьки раніше) → перенесення → перейменування → атрибути → обладнання й робочі центри → архів → правила поповнення → правила розміщення; помилка — відкат усього (`rollback`); два одночасні застосування — `FOR UPDATE NOWAIT` (`conflict`).
   Категорії зберігання в план не входять (R-28 п. 2).
2. **Область** (F02-03, `select_lines`): `scope` — uid зон/рядів; застосовуються лише їхні рядки (`scope_uid`, `zone_uid`); потрібні батьки (`depends_code`) **додаються самі**, навіть коли зняті; `excluded` — рядки `(res_model, code[, kind])`, що пропускаються; `blocked` рядки не беруть участі взагалі;
   рядок, чий батько заблокований, не застосовується й потрапляє в `skipped` («Залежність {код} заблокована»). Архівація — лише коди з `archive_codes` (явне видалення правила — не пропозиція, діє без нього).
3. **Блокування рядка** (`blocked`, `blocked_reason`, `flags`): архівація — лише порожніх (`stock.quant`) і без незавершених переміщень; перенесення локації із залишком — попередження (`stock`); штрихкод зайнятий (R-29 `code_states`) — `barcode_busy`; прапорці — R-28 п. 4. Помилки перевірок режиму `block` забороняють застосування.
4. **Адреса комірки:** `create`/`rename` несуть `td_row/td_bay/td_level/td_pos` і ім'я за `loc_tree` (R-25 п. 6); при `loc_tree='row'` перед комірками створюється батьківська віртуальна локація ряду (рядок `create` із `depends_code`); зміна адресації площадки дає `rename` замість `create`.
5. **Нагадування про копію БД** (F02-10): перше застосування площадки (журнал порожній, `publish_copy_ack=False`) — банер у майстрі; «Більше не нагадувати» (`copy_ack`) ставить `site.publish_copy_ack`.
6. **База порівняння:** успішна публікація оновлює `site.odoo_baseline_id` (`odoo_sync.save_baseline`; збій читання стрічки публікацію не скасовує), тож створене публікацією не з'являється як розбіжність (R-35).
7. **Ідемпотентність:** повторна публікація без змін — `no_changes`; розкладка без правок після повернення версії — порожній план.

### R-32 Журнал і відкат публікації (F02-08, CD-31 Q5; `publish.make_op`, `rollback_version`)

Кожна операція застосування пише `td.publish.op` (`seq`, `op`, `res_model`, `res_id`, `code`, `before`, `after`) — до коміту версії. **Відкат** (`/publish/rollback`, `action_rollback`; менеджер, `confirm`) виконує обернені операції **лише в Odoo** (чернетка не змінюється),
у зворотному порядку (за `seq`): створене → `active=False` (і скидання зв'язку з чернеткою правила), `move/rename/attrs` → попередні значення (`before`), архівоване → `active=True`; запис, якого вже немає, пропускається. `rollback_problems(version)` забороняє відкат, коли: це контрольна точка («Контрольна точка не змінює Odoo»);
версію вже відкочено; немає операцій; є **пізніша** непереглянута публікація з тими самими `(res_model, code)` («відкотіть її першою»); запис Odoo видалено; створене вже використано (локація чи її нащадки мають залишки `stock.quant` ≠ 0 або рухи `stock.move.line`; обладнання має заявки ТО `maintenance.request`; робочий центр — завдання `mrp.workorder`); `archive`-операцію скасовано вручну або запис змінено після публікації
(поточні значення ≠ `after`). Відкат атомарний (savepoint): або все, або нічого (`rollback`); успішний — `rolled_back=True` на операціях, `rolled_back_at/by_id` на версії; повторний — заборонено.

### R-33 Залишки, показники, пошук (F06, F07, CD-31 Q8; `services/metrics.py`, `heat.js`)

1. **Залишки за кодами** (`stock_state`, API-13): код комірки = `stock.location.td_code`, площадка = `td_site_id`; читання від імені сервера лише по локаціях площадки. Агрегати: `qty`, `reserved`, `fill` (R-28 п. 5), `in_date`/`age_days` (найстаріша партія із залишком), `moves` (`stock.move.line` за `days`, за замовч. `td.constructor.stock_days=90`), `min`/`max`
   (`stock.warehouse.orderpoint` локації), `capacity`, `top_product`, `location_id`. Відповідь ріжеться пачками (≤ 2 МБ, ≤ 2000 локацій), клієнт повторює з `offset: next`, поки `truncated`. Без синтетики (в артефакті — «демо»).
2. **Класи показників** (ядро, `registries.metrics`): `fill` — порожньо / до 25 % / 25–50 % / 50–75 % / понад 75 % / без ємності; `below_min` — запасу немає / нижче мінімуму / не нижче / без правила; `empty` — порожнє / зайняте; `abc` — A (80 % руху), B (наступні 15 %), C (останні 5 %), без руху — за числом переміщень за період;
   `age` — до 30 / 31–90 / 91–180 / 181–365 / понад 365 днів (за найстарішою партією). Нові (ще не збережені) комірки лишають власний колір; вибір запам'ятовується; легенда показує число комірок у класах.
3. **Пошук** (`stock_find`, API-14): `mode` ∈ (`any`, `product`, `lot`, `package`); запит розбивається на слова, **усі слова мають збігтися в одному залишку** (назва/артикул товару, партія, упаковка); ≤ 500 збігів; «Перейти до місця» (код без регістру й роздільників, `plt01a → PLT-01A`) — у ядрі (`search.js`).

### R-34 Етикетки (F05, API-19 `labels_pdf`; `services/labels.py` ↔ `labels.js`, `barcode.js`)

Ядро вибирає комірки (виділене, зона, ряд, ярус, усе; фільтри «лише нові й перенумеровані», «лише застосовані в Odoo»), будує вміст і сітку; сервер **лише малює**. Payload: `{format: pdf|png, font: cyr|latin, kind: code128|qr, page: {w, h}, grid: {cols, rows, x0, y0, w, h, gx?, gy?}, skip?, labels: [{code (≤ 64), lines?: ≤ 4 × ≤ 80 символів, arrow?: up|down}]}`
(розміри в мм; `page` 20…1000, `grid.cols/rows` 1…100). Ліміти: `len(labels) ≤ td.constructor.labels_max` (5000), PNG ≤ **12 аркушів** (кілька → ZIP), інакше лише PDF. PDF: `reportlab`, шрифт NotoSans зі вбудованою кирилицею (`font=latin` — Helvetica); Code128 — власний кодувальник, **той самий алгоритм, що `barcode.js`** (золоті
`s3_barcode_golden.json`); QR — `qrcode` (byte). ZPL (203/300 dpi, `^BC`/`^BQ`) будується лише в ядрі. Помилки payload — `validation`.

### R-35 Структура з Odoo, розбіжності, правила розбору (F10, F02-09/12, CD-31 Q3; `services/odoo_sync.py` ↔ `parse_codes.js`, `structure.js`)

1. **Стрічка** (`locations_feed`): нейтральний список локацій складу площадки з вкладеними (`usage` internal і view) — `{id, code, name, parent, parent_id, usage, barcode, qty, active}`, пачки до 20 000, стеля 50 000 (`truncated`, `next`); склад — `warehouse_id` площадки чи параметр. Імена `stock.*` ядро не знає (CD-30).
2. **Розбір кодів** (ядро): правила `site.parse_rules = {v: 1, rules: [{id, mode: mask|regex, mask|regex, type, enabled}] (≤ 30), tray: [{code, name, parent, usage, reason}] (≤ 5000), tray_more}`; маска з частин `{ряд} {секція} {ярус} {префікс}` (+EN), `{x:a}` літери, `{x:A-D}`/`{x:1-5}` діапазони,
   `*` — будь-який текст; regex з групами `row/bay/level/zone/pos/prefix`; далі шаблон адресації (R-25) і «як зараз». Результат: ряд+секція+ярус → ряд/стелаж/ярус; секція+ярус → ряд із зони-батька; ряд+ярус → ряд зі стосами; без частин — місце на підлозі.
   Нерозібране без зони-батька потрапляє в лоток «Не розміщено» (`parse_rules.tray`); розміщення з лотка й імпорт структури — **одна** звичайна зміна (Ctrl+Z).
3. **База порівняння** — вкладення `site.odoo_baseline_id` (стрічка на момент останнього «Оновити з Odoo» чи успішної публікації); `diff_feeds` → `appeared`, `disappeared`, `renamed`, `moved` (дзеркало `diffFeeds` у `artifact/sample_locations.js`); «Прийняти з Odoo» / «Залишити моє» — одна зміна, далі база оновлюється.
   Збереження бази — менеджер чи проєктувальник шару; читач бачить `diff`, але `baseline` не змінює.
4. **Запис правил** (`/odoo/rules`): `normalize_parse_rules` (R-22), лічильник чернетки збільшується (правила входять до розкладки).

### R-36 Таблиці XLSX/CSV (F11; `services/tabular.py` ↔ `tabular_core.js`)

`parse_table(filename, content, sheet=0)`: XLSX — `openpyxl` (read-only, `data_only`: значення формул як у Excel), CSV — UTF-8 (з BOM чи без) або Windows-1251, роздільник кома / крапка з комою / табуляція за першим рядком; рядки — списки (`str|int|float|bool`, порожня клітинка — `""`). `table_xlsx(rows, sheet)` → XLSX (`xlsxwriter`):
рядки лишаються рядками (нулі на початку), числа — числами. Ліміти: файл ≤ 25 МБ, ≤ 200 000 рядків, ≤ 200 колонок — інакше `validation`. Формат збігається з тим, що читає/пише ядро без сервера (CSV), тож «туди-назад» без втрат (золоті `s4_python.xlsx`, `s4_roundtrip.xlsx`).
Формат імпорту `stock.location`: заголовки EN/UK/RU (Full Location Name, Location Type, Barcode, Parent Location, + Corridor/Shelves/Height, + Product/Quantity/Lot); код = штрихкод, інакше ім'я; нескладські типи пропускаються. Експорт: усі місця або «нові й змінені» (з недостаючими батьками), XLSX чи CSV.
**Не зроблено:** `.whproj.json` (F11-05) і «Місця в Excel» (F15-03) — Q-16, Q-17.

### R-37 Будівля, проходи, техніка, перевірки `inside`, `aisle_width`, `height` (F18, N-06, N-07; `services/building.py`, `checks_building.py` ↔ `building_core.js`)

1. **Об'єкти** шару `kind=building` — `layer.items` (R-22, ≤ 5000): `{id, kind: column|wall|gate|dock|door|office|charger, name, x, y, w, d, rot (°), th? (стіна), h?, location_uid? (лише gate/dock)}`; усі — прямокутники OBB: центр `(x, y)`, довжина `w` уздовж осі `rot`, глибина `d`; стіна — відрізок довжиною `w` і товщиною `th` під довільним кутом (CD-31 Q10:
   проходи — по осях, стіни — будь-який відрізок). Типові розміри `(w, d)`: колона 0.4×0.4, стіна 5×0.2, ворота 3.5×0.3, док 3×0.5, двері 1×0.2, офіс 6×4, зарядка 1.2×0.8. Перешкоди (`OBSTACLE_KINDS`): `column`, `wall`, `office`, `charger`; ворота, док і двері — прорізи.
2. **Контур** — `bounds` шару `building` (многокутник ≥ 3 точок), інакше прямокутник `building.length × width`. **Колони сітки** `site.column_grid` (`step_x`, `step_y`) — це **не** об'єкти `items`: сцена малює їх 0.4×0.4 м у вузлах сітки, а вузли дає **єдина функція** `grid_nodes` (Python, `building.py`) ↔ `gridNodes` (JS, `building_core.js`): `x = step_x, 2·step_x, …` (`x < length − 0.01`), `y` так само за `width`; сітки немає, якщо будь-який крок ≤ 1 м, немає габариту чи вузлів ≥ 2000; вузол ближче 5 см до явної колони `items` пропускається (колона не дублюється).
   Вузли бачать авторозкладка (§8.5, `obstacleRects`) і перевірка `inside` (п. 4) — Q-19 закрито у `19.0.1.4.1`. Стан перевірок (`checks_state` / `toCheckState`) передає `site.column_grid = {step_x, step_y}`; без нього (старі фікстури) колон сітки немає.
3. **Техніка складу** (N-06): `site.aisle_tech` / `slot.tech` = `ключ` або `ключ:мін_м`; ключі й типові мінімуми ширини проїзду, м: `hand` 1.2, `stacker` 2.0, `reach` 2.8, `vna` 1.8, `forklift` 3.5, `custom` (свій мінімум), `none` («не перевіряти»); порожнє значення зони — «як у складу», порожнє значення складу — «не перевіряти».
   Діє найменша зона з власною технікою, що містить точку.
4. **`inside`** (`CHECKS` `inside`, sequence 100): місця й обладнання шарів `storage`, `production`, `custom` (`INSIDE_KINDS`) мають лежати **усередині контуру** («{код}: поза контуром будівлі») і не перетинати перешкоди з `layer.items` («{код}: перетинає колону/стіну/офіс/зарядку техніки «{ім'я}»») **та колони сітки** `site.column_grid` («{код}: перетинає колону сітки (x; y)», координати вузла `%.2f`), SAT-проникнення > `eps` (той самий допуск і та сама геометрія 0.4×0.4 м, що в авторозкладки).
   Серйозність зауваження **не залежить від джерела колони**: `severity = config.mode` (R-04) — явна колона й колона сітки однаково `block` (зупиняє публікацію, API-07 `blocked`) чи `warn` (потрапляє в `report.warnings`). Вузол під явною колоною вдруге не рахується; об'єкт, що перетинає дві колони, дає два зауваження.
5. **`aisle_width`** (110): мінімальна ширина за технікою: проходи шарів (`aisles`, ширина = менша сторона) і проїзди між лицьовими сторонами рядів (`pallet_rack`, `cantilever`, `shelf`; паралельні в межах 1°, спільна довжина лицьових сторін ≥ 1 м, пари далі 12 м не розглядаються); **зазор до 0.6 м — «спина до спини», не проїзд**;
   якщо між рядами щось стоїть — не проїзд.
6. **`height`** (120): верх складування (`building.slot_height` = сума ярусів (+0.15 м, якщо нижній ярус не на підлозі) + 0.25 м для палетного/консольного чи 0.1 м для полицевого) не вище стелі будівлі й не ближче **0.5 м** до спринклерів (`site.sprinkler_height_m`, 0 — немає).
7. Режим «Будівля» (ядро): контур числами чи многокутником, колони (клік чи «Колони сіткою»), стіни, ворота, док, двері, офіс, зарядка, проходи як графи, прив'язка 0.1/0.5/1 м (Alt — без), лінійка й рулетка; ворота й док прив'язуються до локації Odoo (`location_uid`).

### R-38 Документи: специфікація стелажів і план (F15; `services/rack_spec.py`, `render_docs.py` ↔ `spec.js`, `plan_doc.js`)

Формули **відновлено за інструкцією «Документи»** (CD-31 Q12: еталонних файлів «Конструктора складу» немає). Рахуються за **нормалізованими** параметрами місця; `sides = 2` для `double_sided` — кожен бік окремо:
`pallet_rack` (B прольотів, N ярусів): рам `(B+1)·sides` розміру В×Г (Г = `depth·deep`), балок `B·N·2·sides` довжиною `bay_width`, зв'язок `2·B·sides`; `shelf` (S секцій, K полиць): стійок `(S+1)·2·sides`, полиць `S·K·sides` (`cell_w × cell_d`, м²), зв'язок `S·sides`;
`cantilever` (A секцій, N ярусів): стійок `(A+1)·sides`, консолей `(A+1)·N·sides` довжиною `arm_length`, зв'язок `A·sides`; стяжки двосторонніх рядів: `секцій+1` штук довжиною `gap_y` (≥ 0.05 м) на двосторонній стелаж чи на пару «спина до спини» (зазор < 0.6 м, паралельні, спільна довжина ≥ 90 %).
Висота рами/стійки = `slot_height` (R-37 п. 6). Підсумки — за типорозмірами. **`plan_pdf`**: `{title, page: {w, h}, ops: [...]}`, примітиви в мм (початок — лівий верх, y вниз): `poly`, `rect`, `line`, `text` (`anchor`, `rot` проти годинникової), `clipBegin`/`clipEnd` — той самий список малює SVG ядра; ≤ 200 000 примітивів.
**`spec_pdf`**: `{format: pdf|xlsx, title, tables: [{name, columns, rows}]}` (`MAX_TABLES=10`, `MAX_COLUMNS=30`, `MAX_ROWS=100000`; назви аркушів XLSX унікалізуються) або `{site_id}` — сервер рахує специфікацію за чернеткою (`rack_spec.build_spec(spec_slots(checks_state(site)))` → `tables`). Шрифт NotoSans з кирилицею; читання — «перегляд», без запису в БД.

### R-39 Оренда зони (F14, CD-31 Q6; `td.zone.lock`, `td.draft.mixin`)

1. **Зона об'єкта** — найменша зона-контур (`td.slot` `template='zone'`), що містить його центр, інакше сам об'єкт (його `uid`): `zone_uid`. Дзеркало в ядрі: `locks.js`.
2. **Оренда** `lock_ttl_s` = 300 с, продовження раз на `lock_heartbeat_s` = 60 с, зняття при виході з режиму правки чи закритті; опитування списку раз на 15 с. `acquire` власної чи простроченої оренди успішний; діюча чужа → код `locked` з повідомленням «хто й до котрої години (HH:MM, часовий пояс користувача)».
3. **Перевірка при записі** (`td.draft.mixin.create/write/unlink` для `td.slot` і `td.placement`, до `super()`; `f3d_assert_write/create`): для кожної позиції об'єкта (старої й нової, якщо вона змінюється) береться ключ зони — найменша зона-контур, що містить точку, а також `uid` самого об'єкта (для самої зони — лише її `uid`); якщо за цим ключем є **діюча оренда іншого користувача** → `AccessError` «Зону … редагує … до HH:MM» (API-04 повертає `rights`).
   Поза орендою правка проходить — діє лише `etag` (R-21). Дивитися, виділяти й коментувати чужу зону можна. Перевірка пропускається при `env.su` і контексті `f3d_no_lock_check`; менеджер оренду чужого **не** обходить, але може зняти її записом (`unlink` у списку «Блокування зон»).
4. Прострочені оренди прибираються при кожному зверненні (`f3d_purge`); крону немає. В артефакті оренди **не емулюються** (`capabilities.locks=false`).

### R-40 Варіанти, контрольні точки, знімок схеми 2 (F12, N-03, F19-04; розширює R-14)

1. **Знімок** `schema: 2` (читає й `1`): до R-14 додано `site.{addr, loc_tree, depth_mode, sprinkler_height_m, aisle_tech, parse_rules, wizard_state, warehouse{id, code}}` (лише відмінні від типових — знімок незміненої чернетки лишається таким, як був), `layers[].items`, `slots[].{type, storage_category, removal_strategy, function, attrs, temp_min_c, temp_max_c, tech, addr, depth_mode}`
   і `sections` — розділи реєстру `SNAPSHOT_SECTIONS` (`replenish_rules`, `putaway_rules`; R-41). Відновлення старого знімка скидає нові поля до типових; посилання на видалені записи Odoo ігноруються. `count_differences` враховує розділи.
2. **Варіанти** (M-21): перемикання = знімок поточної гілки → `apply_snapshot` вибраної (savepoint), `draft_base_version_id` = базова версія варіанта, `draft_changes` = відмінності від діючої версії. Публікація й «застосування» стосуються **лише активного** варіанта (F12-04). Ліміт `variants_max` (12) на робочі; «Як є» створюється автоматично.
   Цифри порівняння (`cells`, `places`, `area`, `volume`, `max_weight` + `ops`) рахує ядро.
3. **Навчальна копія** (F19-04): тур, що змінює дані, створює тимчасовий варіант `is_training`; «Залишити зміни» робить його робочим, «Скасувати» повертає `origin_id` і видаляє копію; публікація навчальної копії забороняється (`UserError`).
4. **Контрольні точки** (N-03, `/version/checkpoint`): знімок чернетки як `td.layout.version` з `kind='checkpoint'`, `state='superseded'`, нотатка за замовч. «Контрольна точка»; діюча версія й база чернетки не змінюються; точок понад `versions_keep` (50) прибирають найстаріші — **публікації не видаляються ніколи**.
   «Відновити» (клієнт) спершу зберігає поточну чернетку окремою контрольною точкою, потім викликає API-08.

### R-41 Реєстри точок розширення (`services/registry.py`; ядро — `core/constructor/registry.js`)

**Python** (`class Registry`: `register(key, value, sequence=100, replace=False)` або декоратор, `unregister`, `get`, `keys`, `items`; повторний ключ без `replace` — `RegistryError`; порядок обходу — за `sequence`, далі за порядком реєстрації). Слайс реєструється **зі свого файлу** (його імпортує `services/__init__.py`):

| Реєстр | Контракт значення | Споживач | Ключі (sequence) |
|---|---|---|---|
| `CHECKS` | `fn(scene, config, eps) -> [issue]`, `issue = {check, severity, layer_id, codes, message}`; ключ = `td.check.config.check_key`; запускається, лише якщо є **увімкнений** рядок налаштувань; вбудовані 7 перевірок (`checks.CHECKERS`) реєстром не перекриваються | `checks.run_checks` (API-05, публікація) | `cell_load` (80), `putaway_fit` (90), `code_conflict` (95), `inside` (100), `aisle_width` (110), `height` (120) |
| `PLAN_BUILDERS` | `fn(site, env, lines, issues) -> int` — дописує рядки плану й зауваження на місці, повертає число рядків «без змін» | `publish.build_plan` | `capacity` (60), `putaway` (70) |
| `SNAPSHOT_SECTIONS` | `SnapshotSection(build, apply)`: `build(site) -> JSON` (порожнє — розділ не пишеться), `apply(site, data)` викликається для **кожного** зареєстрованого розділу (`data=None`, якщо в знімку його немає) | `snapshot.build_snapshot/apply_snapshot/count_differences` | `replenish_rules` (60), `putaway_rules` (70) |
| `RENDERERS` | `fn(env, payload) -> (filename, mimetype, bytes)`; помилки — `UserError`/`ValidationError`/`AccessError` (`validation`/`rights`) | `controllers/render.py` (API-19) | `labels_pdf` (10), `plan_pdf` (30), `spec_pdf` (31), `table_xlsx` |
| `publish.APPLIERS` (звичайний `dict`) | `res_model -> fn(site, lines, records, ops) -> [entry]` | `publish._apply` | `stock.warehouse.orderpoint` (`capacity`), `stock.putaway.rule` (`putaway`) |

**Ядро** (`REGISTRY_NAMES`): `panels` (вкладки лівої панелі `area:"left"`, блоки правої `right|site|slot|placement`), `dialogs`, `checks` (`{run, config?}`), `shapes` (каркаси форм типів), `metrics` (колір комірки за показником), `menu` (`top`/`more`), `hotkeys`, `capabilities`; `registries.X.add(key, value, {sequence, force})` — повторний ключ без `force` помилка.
`CAPABILITY_NAMES`: `publish`, `check`, `library`, `storage`, `stock`, `putaway`, `odoo_import`, `rollback`, `render`, `files`, `variants`, `comments`, `locks`; можливість, якої адаптер не оголосив, ховає відповідну функцію (`can(name)`).

## 10. Стани й переходи

| Об'єкт | Стани | Переходи (хто/що) | Побічні ефекти |
|---|---|---|---|
| Чернетка площадки | `clean` (`draft_rev == published_rev`) ↔ `dirty` | будь-яка правка layer/slot/placement/check.config (UI, форма, API-04) → `dirty`; публікація або відновлення діючої версії → `clean` | `draft_changes` змінюється за R-21 |
| `td.layout.version.state` | `active` → `superseded` | нова публікація робить попередню `superseded`; `active` — завжди рівно одна на площадку | `site.active_version_id`, `published_rev = draft_rev` |
| `td.equipment.variant.model_status` | `none` → `ok` / `pending_conversion` / `error`; `pending_conversion` → `ok`/`error` (`_td_convert_model`, `action_retry_convert`); будь-який → `none` (`action_clear_model`); `ok`/`error` → `ok` (нове завантаження) | API-09, віджет W3 | вкладення замінюються, старі видаляються (`unlink` вкладення) |
| `td.publish.wizard.state` | `preview` → `done` | `action_confirm` | створює версію; повторне натискання неможливе |
| `td.layer.underlay_status` | `none` → `ready` (DXF) / `pending_conversion` (DWG) | завантаження файла (`write` `underlay_attachment_id`) | — |

### 10.1 Доповнення: стани хвиль 1–2

| Об'єкт | Стани | Переходи (хто/що) | Побічні ефекти |
|---|---|---|---|
| `td.layout.variant` | робочий / навчальний (`is_training`); активний (`site.active_variant_id`) / неактивний | `f3d_make` (менеджер) → новий; `f3d_activate` → знімок поточної гілки, `apply_snapshot` вибраної; `f3d_end_training(keep)` → робочий або видалення; видалення активного й єдиного — заборонене в API-21 | `draft_base_version_id`, `draft_changes`, `draft_rev += 1` при перемиканні; публікація навчального — `UserError` (R-40) |
| `td.layout.version.kind` | `publish` (за замовч.) / `checkpoint` | публікація → `publish`, `state='active'`; API-24 `checkpoint` → `checkpoint`, `state='superseded'` | контрольна точка не змінює Odoo, діючу версію й базу чернетки; точки понад `versions_keep` видаляються |
| `td.layout.version` (відкат) | не відкочена → відкочена (`rolled_back_at` ≠ порожнє) | `action_rollback` / `/publish/rollback` (менеджер, `confirm`), лише якщо `rollback_problems` порожні (R-32); необоротно | операції `td.publish.op.rolled_back = True`; записи Odoo: створене → архів, значення назад; чернетка не змінюється |
| `td.comment.state` | `open` ↔ `resolved` | `f3d_resolve(resolved)` — автор чи «Проєктування»; `kind`/`assignee_id` міняються лише в `open` | `resolved_by_id`, `resolved_at`; `_td_sync_activity`: відкрита задача з виконавцем має одне `mail.activity`, вирішена — жодного |
| `td.zone.lock` | вільна → орендована → (продовжена) → прострочена / знята | `f3d_acquire` (до `now + lock_ttl_s`), heartbeat раз на `lock_heartbeat_s`, `f3d_release`; прострочена не блокує й прибирається `f3d_purge` | чужа діюча оренда → відмова правки (R-39) |
| Правила `td.putaway.rule`, `td.replenish.rule` | нове (`odoo_*_id` порожнє) → опубліковане (зв'язане) → `deleted` → архівоване в Odoo | правка (проєктувальник); публікація (R-30, R-31); `deleted=True` / `active=False` + публікація | відкат повертає попередній стан (R-32); знімок версії містить правила (R-40) |
| `td.site.wizard_state` | порожній → заповнений (кроки майстра) → завершений | `/site/wizard` | не змінює лічильник чернетки |

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

### 11.1 Доповнення: помилки й граничні випадки хвиль 1–2

| Ситуація | Поведінка |
|---|---|
| Редагування в чужій орендованій зоні | `AccessError` «Зону … редагує … до HH:MM»; API-04 → `rights`; клієнт повертає об'єкт у попередній стан; сама оренда `acquire` → `{ok: false, code: 'locked'}` зі списком оренд (R-39) |
| Відкат неможливий (створене використано, пізніша публікація, запис змінено) | `rollback_blocked` з `issues: [{code, reason}]`; кнопка «Відкотити» неактивна з причиною (`rollback_reason`) |
| Стрічка локацій Odoo більша за пачку | `truncated: true`, `next` — клієнт повторює з `offset` (пачка до 20 000, стеля 50 000); `stock/state` — пачки ≤ 2 МБ і ≤ 2000 локацій |
| Помилка читання стрічки після публікації | публікація **не** скасовується; база порівняння створюється при наступному «Оновити з Odoo» (`odoo_sync.save_baseline` у `try`) |
| Файл XLSX/CSV пошкоджений, > 25 МБ, > 200 000 рядків, > 200 колонок | `validation` (API-20); клієнт для CSV/XLSX без сервера (`files=false`) показує помилку розбору в діалозі імпорту |
| Невідомі ключі в JSON (`addr`, `items`, `parse_rules`, `params`) | відкидаються без помилки; хибні типи й діапазони — `SchemaError`/`AddrError`/`ValidationError` із номером елемента (R-22) |
| Рендерер (`labels_pdf`, `table_xlsx`, `plan_pdf`, `spec_pdf`) не зареєстровано | `{ok: false, code: 'not_implemented'}`; зареєстровано, але payload хибний — `validation` |
| Код комірки зайнятий в Odoo іншою площадкою/компанією/архівною/не внутрішньою локацією | `code_states.state='busy'` → зауваження `code_conflict` (R-29), у плані — `blocked` із міткою `barcode_busy`; чужі назви компаній не розкриваються |
| Перше застосування площадки | банер «зробіть копію бази» (`copy_reminder`); не блокує, `copy_ack` вимикає нагадування |
| Часові пояси | `expires_at`, `at`, `resolved_at`, `now` — UTC `YYYY-MM-DD HH:MM:SS`; клієнт показує HH:MM у часовому поясі браузера |
| Артефакт без сервера | `locks` вимкнено, задачі без виконавців, PDF/«Куди покладе» — «на сервері»/«оцінка», дані — у `db` артефакта (бюджет 256 КіБ: один документ на варіант) |

## 12. Acceptance Criteria

Тип: **UT** — юніт-тест `odoo.tests` (`post_install`, `-at_install`, `f3d`, `f3d_constructor`); **JS** — HOOT (`web.assets_unit_tests`); **MAN** — ручна перевірка на `serve.sh` за ТК (§13.2). Тести W1 (UT) не залежать від браузера.

| AC | CD / FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-01 | FR-01 | Given чиста база з base+viewer; When встановлено модуль; Then є 4 групи й привілей, 12 `td.term`, 8 ключів `td.constructor.*`, меню `menu_td_constructor_plan` (sequence 70) під `td_factory3d.menu_td_root` і `menu_td_constructor` (1) під ним, дія `tag='f3d_constructor'` | UT |
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

### 12.1 Acceptance Criteria злиття (AC-70…AC-138; функції F01…F19 і N-xx з `build/constructor/MERGE.md` §1)

Типи — як у §12, плюс **PW** — сценарій Playwright на прототипі (`build/constructor/proto/test_s*.js`, потрібні каталоги `vendor/` і `fixtures/` поза репозиторієм); **JS** охоплює Node-тести ядра (`tools/test_core_s*.mjs`, запускає `node tools/test_core.mjs`) і HOOT (`static/tests/editor/s*.test.js`,
запускає `tests/test_hoot_editor.py`). Файли Python-тестів — у `odoo_addons/td_constructor/tests/`. Кожен AC зі статусом «Не зроблено» або «Відоме обмеження» має відповідне відкрите питання (§15).

| AC | F / CD | Given / When / Then; тести | Тип |
|---|---|---|---|
| AC-70 | W0-B, CD-31 | Given чиста база; When встановлено `19.0.1.4.0` (і при `-u`); Then існують M-16…M-23 з полями §2.1, ACL §4.5 і 8 глобальних правил компанії, 6 параметрів (`lock_ttl_s`, `lock_heartbeat_s`, `variants_max`, `versions_keep`, `stock_days`, `labels_max`), меню V-14…V-18, 50 типів, довідники зони (10+4); деінсталяція не видаляє бізнес-записів Odoo. Тести: `test_skeleton_models.py` `TestSkeletonModels`, `test_skeleton_rights.py` `TestSkeletonRights`, `test_install.py` `TestInstall` | UT |
| AC-71 | R-41 | Given реєстри `CHECKS`, `PLAN_BUILDERS`, `SNAPSHOT_SECTIONS`, `RENDERERS`; When реєстрація, дубль, `replace`, `unregister`, порядок за `sequence`; Then вони незалежні, повторний ключ без `replace` — `RegistryError`; зареєстрована перевірка запускається в API-05 (лише при увімкненому `td.check.config`), розділ знімка входить у R-14, рендерер — у API-19. Тести: `test_registries.py` `TestRegistries`, `test_registry_hooks.py` `TestRegistryHooks`, `TestRegistryHooksApi` | UT |
| AC-72 | CD-29 | Given `factory3d/core/constructor/*`; When `node tools/test_core.mjs` (з `ESBUILD_DIR` — і перевірка свіжості збірки модуля); Then у ядрі лише відносні імпорти (жодних `@web`/`@odoo`/`@td_constructor`/`window.claude`/`fetch`), `assertAdapter` приймає `OdooAdapter` і `ArtifactAdapter`, `CAPABILITY_NAMES` повні, `constructor.esm.js` збігається з `build_core.mjs module --check`, `CORE_BUILD` оновлено. Тести: `tools/test_core.mjs` (+ `test_core_s1…s6.mjs`); з Odoo — `tests/test_core_node.py` `TestCoreNode` | JS |
| AC-73 | CD-29 | Given прототип; When `python3 build/constructor/proto/build.py` (мінімізований `F3D_PROTO_MINIFY=1`); Then він збирається з тих самих файлів ядра, **< 900 КБ**, містить усі 31 шар і 1078 об'єктів сцени. Тести: Playwright `build/constructor/proto/test_scene.js`, `smoke.js`, `test_ac.js`, `test_upgrade.js` (потрібні каталоги `vendor/`, `fixtures/` поза репозиторієм) | PW |
| AC-74 | F01-01…04 | Given `addr` (шаблон, сегменти цифрами/літерами, пропуск слів без значення, синоніми UK/EN, напрями `ltr/rtl/odd_even`, `snake`, `level_dir=down`, зворотний розбір); When `addr.render_code`/`parse_code`/`normalize_addr`; Then коди збігаються з еталоном `addr_golden.json` в Python і JS, `legacy` не змінює жодного коду. Тести: `test_s1_addr.py` `TestAddrEngine`, `test_s1_golden.py` `TestS1Golden`, `tools/test_core_s1.mjs` | UT+JS |
| AC-75 | F01-03/06, CD-31 Q2 | Given площадка з опублікованими місцями; When `/site/addr` (`renumber='new'|'all'`, власна адресація зони/місця, `depth_mode`); Then `new` закріплює коди опублікованих і нумерує нові, `all` — усе; `overrides` і `cell_code` розміщень переносяться; проєктувальник не може `all`/зміну `loc_tree` опублікованої площадки; хибна схема — `validation`. Тести: `TestAddrModels`, `TestSiteAddrApi` (`test_s1_addr.py`), `TestChecksWithAddressing` (`test_s1_checks.py`) | UT |
| AC-76 | F01-05/10/11 | Given `loc_tree` ∈ (`flat`, `row`, `section`), `depth_mode='cell'`; When `location_vals`, `_td_address_vals`, генерація комірок; Then `name` — повний код при `flat` і останнє слово при `row`/`section`, `td_row/td_bay/td_level/td_pos` — логічні номери, ярус ділиться на `cells_per_level` локацій `<код>-1…N`. Тести: `TestAddrEngine.test_depth_cell_splits_levels`, `test_location_vals_flat_and_row`; `TestAddrModels.test_stock_location_address_helpers` | UT |
| AC-77 | F01-07, F02-11 | Given код комірки чернетки; When `/codes/check`, `code_states`, перевірка `code_conflict`, план; Then стани `free/own/match/busy` з причинами (інша площадка, компанія, архівна, не внутрішня, інший склад), зауваження `code_conflict` за режимом, рядок плану `blocked` із міткою `barcode_busy`; > 5000 кодів — `too_many`. Тести: `TestS2Plan.test_code_states`, `test_barcode_held_by_non_internal_location_is_blocked`; `TestS2Putaway.test_code_conflict_check_with_data`; `TestS2PlanApi.test_codes_check_and_log_and_rollback` | UT |
| AC-78 | F01-08, F08 | Given місце `floor_spot`; When генерація й нумерація; Then одна комірка з `code_prefix` (або код за адресацією першим доступним сегментом `pos/row/bay/level`), параметри `length/width/height/max_load_kg/capacity` у межах R-26. Тести: `TestAddrEngine.test_floor_spot_numbering_by_first_available_segment`, `TestCatalog.test_floor_spot_generator`, `TestMigrationFloorSpot` | UT |
| AC-79 | F08-01/02, CD-31 Q9 | Given модуль; When завантажено `td_slot_type_data.xml`; Then 50 типів (20/5/8/12/5 за групами; ● 16, ○ 19, — 15), семи генераторів, нові параметри стелажів проходять валідацію й дають геометрію, `data/td_slot_type_data.xml` ≡ `types_data.js`. Тести: `test_s1_catalog.py` `TestCatalog` (`fifty_types_seeded`, `seven_generators_build_geometry`, `new_params_validation_and_geometry`, `type_validation`, `slot_from_type_and_consistency`), `tools/test_core_s1.mjs` | UT+JS |
| AC-80 | F08-03…06 | Given діалог каталогу в редакторі; When «Додати в проєкт», «Додати на план», зміна розміру типу, «Конструкція ряду» / «Як у типу»; Then каталог не змінюється, місця з'являються з параметрами типу, зміна розміру типу пересобирає всі його місця, 9 форм 3D/2D зареєстровано в `shapes`. Тести: `tools/test_core_s1.mjs`; Playwright `test_s1.js` | JS+PW |
| AC-81 | F08, F09-07 | Given ролі; When API-11 `save`/`delete`, ORM; Then читач не пише; проєктувальник створює лише власні типи (`is_custom`) і пресети й не видаляє; тип каталогу змінює лише менеджер; тип із місцями не видаляється; ізоляція компаній. Тести: `TestLibraryApi` (`test_s1_library.py`), `TestCatalog.test_rights_catalog_and_custom`, `TestSkeletonRights.test_designer_edits_library_but_cannot_delete` | UT |
| AC-82 | F09-06/07 | Given пресет `row`/`section`/`group`; When API-11 `save`, вставка; Then `data` зберігається нормалізованим (R-22), секцією — лише стелаж чи штабель, група 1…200 місць; вставка: зона → ряд ×N, ряд → секція. Тести: `TestLibraryApi.test_presets_lifecycle_and_validation`; `tools/test_core_s1.mjs` | UT+JS |
| AC-83 | F02-01/02/04 | Given чернетка й Odoo; When `build_plan`/`apply_plan`; Then рядки `create/move/rename/attrs/update/archive` у порядку R-31 п. 1 в одній транзакції, `td_row…td_pos` у `create`, `loc_tree='row'` — батьківська локація раніше, зміна адресації = `rename`, архів — лише порожніх без незавершених переміщень, перенесення із залишком — `warn`, повтор без змін — `no_changes`. Тести: `test_s2_plan.py` `TestS2Plan` (`create_line_carries_address_parts_and_scope`, `update_is_split_into_move_rename_attrs`, `row_tree_*`, `renumber_becomes_rename_when_the_addressing_changes`, `archive_blocked_by_unfinished_moves`, `move_of_location_with_stock_warns`, `idempotent_publish_has_no_changes`) | UT |
| AC-84 | F02-03 | Given план із зонами й рядами; When `scope`/`excluded` (API-07, майстер); Then застосовуються лише вибрані рядки, батьки додаються самі, `blocked` не застосовуються, залежні від заблокованого батька — `skipped`. Тести: `TestS2Plan.test_scope_applies_one_row_only`, `test_wizard_pages_scope_select_all_and_apply`, `test_wizard_blocked_line_is_not_applicable`; `TestS2PlanApi.test_publish_api_scope_and_excluded` | UT |
| AC-85 | F02-08 | Given публікація; When застосовано; Then `td.publish.op` має `before`/`after` для кожної операції, `/publish/log` і форма версії показують операції за видами й `can_rollback`. Тести: `TestS2Plan.test_journal_records_ops_with_before_after`, `test_publish_log_and_version_form`; `TestS2PlanApi.test_codes_check_and_log_and_rollback` | UT |
| AC-86 | F02-08, CD-31 Q5 | Given версія з операціями; When `/publish/rollback` (`confirm`, менеджер); Then створене → архів, `move/rename/attrs` і архівоване повертаються, чернетка не змінюється; відкат забороняється, якщо створене використано, є пізніша публікація з тими ж кодами чи запис змінено (`rollback_blocked` + причини); атомарно; не-менеджеру — `rights`. Тести: `TestS2Plan.test_rollback_restores_odoo`, `test_rollback_reverts_move_rename_attrs_and_archive`, `test_rollback_blocked_when_used_or_changed_or_later`, `test_rollback_needs_manager`, `test_rollback_is_atomic`; `TestS2PlanApi.test_rollback_rights` | UT |
| AC-87 | F02-10 | Given площадка без журналу; When відкрито майстер; Then `copy_reminder=True`, `copy_ack` пише `publish_copy_ack`, повторно нагадування немає. Тест: `TestS2Plan.test_wizard_first_application_reminds_about_database_copy` | UT |
| AC-88 | F02-09/12 | Given база порівняння `odoo_baseline_id`; When `/odoo/locations` `op=sync|baseline`, публікація; Then `diff` має `appeared/disappeared/renamed/moved`, без бази — `baseline: created`, публікація оновлює базу (створене нею не є розбіжністю) і не падає при збої стрічки; читач не змінює базу. Тести: `test_s4_sync.py` (`TestS4Schema.test_diff_feeds`, `TestS4Feed.test_sync_baseline_and_diff`, `TestS4PublishBaseline`, `TestS4Api.test_sync_and_baseline_route`), HOOT `s4.test.js`, Playwright `test_s4.js` (`розбіжності`) | UT+JS |
| AC-89 | F02-06 | Given план; When «Файл для імпорту…»; Then таблиця «нові й змінені» у форматі імпорту `stock.location` (XLSX/CSV, з недостаючими батьками). Тести: `tools/test_core_s2.mjs` (`plan_core.js`), `tools/test_core_s4.mjs` | JS |
| AC-90 | F03-02/06 | Given менеджер; When API-12 `save`/`delete` (`confirm: true`), публікація; Then категорії створюються/змінюються/видаляються (використану видалити не можна), `storage_category_id` і `removal_strategy_id` наслідуються вниз по ланцюжку зон (найменша зона перекриває), без `confirm` — `validation`, не-менеджеру — `rights`. Тести: `TestS2Capacity.test_category_crud_and_validation`, `test_category_in_use_is_not_deleted`; `TestS2StorageApi.test_list_save_delete_and_rights`; `TestS2Plan.test_storage_category_and_removal_strategy_inherit_from_zone`, `test_nested_zones_inherit_from_the_nearest_zone` | UT |
| AC-91 | F03-03/04 | Given модуль; Then 10 функцій і 4 атрибути зони — `td.term` із xml-id (`noupdate`), міграція `19.0.1.3.0` прив'язує наявні терміни без зміни. Тести: `TestS2Capacity.test_zone_terms_come_from_module_data`, `test_pre_migrate_binds_existing_zone_terms_to_xmlids` | UT |
| AC-92 | F03-05 | Given `overrides[код].usage/replenish_location`; When план; Then `attrs` змінює прапорці, `view` для локації із залишком і вкладене/неінтернальне «місце поповнення» — `blocked`. Тести: `TestS2Plan.test_flags_from_cell_overrides_are_published`, `test_flag_rules_stock_view_and_nested_replenish` | UT |
| AC-93 | F03-07 | Given `td.replenish.rule`; When публікація/відкат/знімок; Then `stock.warehouse.orderpoint` створюється (з батьківською коміркою), оновлюється, архівується, зв'язується з наявним; `max < min` і від'ємні — `ValidationError`; правила входять до знімка й відновлюються. Тести: `TestS2Capacity` (`orderpoint_*`, `replenish_rule_validation`, `replenish_rules_are_part_of_snapshot_and_restore`, `linked_rule_missing_in_snapshot_is_marked_deleted`) | UT |
| AC-94 | F03-08 | Given залишки з вагою; When `/storage/loads`, перевірка `cell_load`; Then `loads` і `limits` за кодами, зауваження «вага запасу … перевищує допустимі …» за режимом; зведення ємності (місць, палетомісць, площа, об'єм, кг) збігається в ядрі. Тести: `TestS2Capacity.test_cell_load_check_in_plan_and_pure`, `TestS2StorageApi.test_loads_route`, `tools/test_core_s2.mjs` | UT+JS |
| AC-95 | F04-01…03 | Given `td.putaway.rule`; When публікація; Then `stock.putaway.rule` створюється/оновлюється/архівується, ідентичне наявне правило прив'язується, правило до неопублікованої комірки залежить від її створення, неповне — `blocked`, правила входять до знімка. Тести: `TestS2Putaway` (`rule_to_unpublished_cell_depends_on_its_creation`, `rule_update_package_types_and_delete`, `rule_links_identical_existing_odoo_rule`, `incomplete_rules_are_blocked_not_published`, `putaway_rules_are_part_of_snapshot_and_restore`) | UT |
| AC-96 | F04-05 | Given правила Odoo; When `/putaway/where`; Then відповідь — місце за `_get_putaway_strategy` лише застосованих правил (`estimate: false`), `closest_location` зберігає категорію; невідомий товар — `validation`. Тести: `TestS2Putaway.test_where_uses_only_applied_rules`, `test_closest_location_keeps_storage_category`; `TestS2PutawayApi.test_where_and_fit_routes` | UT |
| AC-97 | F04-06 | Given товар/упаковка й комірка; When `/putaway/fit`, перевірка `putaway_fit`; Then причини за вагою, об'ємом, вагою й габаритами упаковки (R-30 п. 3), невідоме пропускається; Python і JS дають однаково на `s2_fit_cases.json`; одиниці — за конфігурацією Odoo. Тести: `TestS2Putaway.test_fit_problems_pure`, `test_fit_problems_match_shared_cases`, `test_rule_fit_inputs_check_and_plan_issue`, `test_item_units_follow_odoo_configuration`; `tools/test_core_s2.mjs` | UT+JS |
| AC-98 | F04-04/07 | Given форма правила; When `/putaway/lookup`, вибір правила; Then довідник (≤ 40, лише своєї компанії, лише читання), підсвічування цілі й «Правила розміщення сюди» в картці місця. Тести: `TestS2PutawayApi.test_lookup_route`; `tools/test_core_s2.mjs`; Playwright `test_s2.js` | UT+PW |
| AC-99 | F05 | Given вибір комірок; When `/render/labels_pdf` (`format: pdf|png`); Then PDF (A4, сітка, `skip`) із кирилицею, Code128 або QR, стрілка ярусу; PNG — один аркуш чи ZIP; помилки payload — `validation`. Тести: `test_s3_labels.py` `TestS3Labels` (`pdf_pages_and_text`, `pdf_latin_font_and_qr`, `png_single_and_multi_page`, `payload_validation`, `paginate_skip_first`, `renderer_registered_and_rights`), `TestS3LabelsApi` | UT |
| AC-100 | F05-03/04 | Given Code128; When Python (`labels.py`) і JS (`barcode.js`); Then однаковий результат на `s3_barcode_golden.json`; ліміти: `labels_max` (5000) і PNG ≤ 12 аркушів; ZPL (203/300 dpi) будує ядро. Тести: `TestS3Labels.test_golden_barcodes_match_core`, `test_code128_rules`, `test_png_page_limit`, `test_labels_max_parameter`; `tools/test_core_s3.mjs`; Playwright `test_s3.js` (`labels`) | UT+JS+PW |
| AC-101 | F06-03, F07 | Given залишки площадки; When `/stock/state`; Then `qty`, `reserved`, `fill` (за ємністю товару категорії чи вагою проти межі), `age_days`, `moves` за `stock_days`, `min/max`, пачки з `truncated/next`, `detail` для ≤ 20 кодів; без групи «Перегляд» — `rights`; `days` поза 1…3650 — `validation`. Тести: `test_s3_stock.py` `TestS3StockState`, `TestS3StockApi` (`state_route`, `state_validation_and_rights`) | UT |
| AC-102 | F06-01/02 | Given запит; When `/stock/find` (`any|product|lot|package`) і «Перейти до місця»; Then усі слова збігаються в одному залишку, пошук за партією й упаковкою, код без регістру й роздільників. Тести: `TestS3StockState.test_find_all_words_in_one_quant`, `test_find_by_lot_and_package_modes`; `TestS3StockApi.test_find_route`; HOOT `s3.test.js`; Playwright `test_s3.js` (`search`) | UT+JS |
| AC-103 | F07-01…08 | Given показник; When перемикач «Показник»; Then класи `fill` (6), `below_min` (4), `empty` (2), `abc` (A/B/C/без руху), `age` (5) із легендою й числом комірок, вибір запам'ятовується, нові комірки лишають свій колір; в артефакті — позначка «демо». Тести: `tools/test_core_s3.mjs`; HOOT `s3.test.js`; Playwright `test_s3.js` (`heat`) | JS+PW |
| AC-104 | F06-04/05, CD-31 Q11 | Given екран ≤ 768 px; When мобільний режим; Then панель згорнута, пошук зверху, картка на весь екран, **редагування вимкнене**; підказка при наведенні (код, товар, заповнення). Тести: Playwright `test_s3.js` (`mobile`, `card`); MAN на телефоні | PW+MAN |
| AC-105 | F09-01 | Given зміни в редакторі; When Ctrl+Z / Ctrl+Shift+Z (Ctrl+Y) / ↶ ↷; Then скасовується крок над чергою адаптера (включно з правилами, адресацією, габаритом, кроком колон, висотами, технікою), ≤ 100 кроків; підписи кроків. Тести: HOOT `s3.test.js`; `tools/test_core_s3.mjs`; Playwright `test_s3.js` (`undo`) | JS+PW |
| AC-106 | F09-02…05, 08…10 | Given виділення; When Ctrl+клік, рамка Shift, Ctrl+D, Ctrl+C/V, масив, вирівнювання; Then взаємне положення зберігається, дублювання дає наступний код/номер ряду, вставка — у придатний рівень; коди при вирівнюванні/групуванні не змінюються. Тести: HOOT `s3.test.js`; Playwright `test_s3.js` (`multi`, `tools`, `align`) | JS+PW |
| AC-107 | N-02, N-05, N-08 | Given ролі; When `E.access()`; Then «Перегляд/Проєктування/Застосування», недоступні кнопки неактивні з підказкою, статуси «не збережено», «нове · лише в моделі», «з Odoo», «Зберегти все», «Скинути до даних Odoo». Тести: `tools/test_core_s3.mjs`; Playwright `test_s3.js` (`save`) | JS+PW |
| AC-108 | F10-01…03 | Given правила розбору; When `normalize_parse_rules`, `parse_codes.js`; Then маска й regex дають ряд/секцію/ярус/зону/префікс, невалідні правила — `validation` (≤ 30 правил, ≤ 5000 у лотку), дзеркало Python↔JS. Тести: `TestS4Schema.test_normalize_parse_rules(_errors)`; `tools/test_core_s4.mjs`; Playwright `test_s4.js` (`правила`) | UT+JS |
| AC-109 | F10-04 | Given нерозібрані коди; When імпорт структури; Then вони в лотку «Не розміщено», розміщення з лотка й імпорт — одна зміна (Ctrl+Z). Тести: `tools/test_core_s4.mjs`; HOOT `s4.test.js`; Playwright `test_s4.js` (`лоток`) | JS+PW |
| AC-110 | F10-05 | Given склад Odoo; When `/odoo/locations` `op=feed`; Then нейтральна стрічка (internal і view, `qty`, пачки ≤ 20 000, стеля 50 000), `td_code` важливіший за штрихкод, склад — `warehouse_id` площадки чи параметр, невідомий склад — `validation`; ядро будує зони, ряди, місця з адресацією S1. Тести: `TestS4Feed` (`feed_content_and_filters`, `feed_td_code_wins_and_batches`, `other_warehouse_and_missing_warehouse`, `structure_imports_into_project_with_addressing_s1`), `TestS4Api`; HOOT `s4.test.js`; Playwright `test_s4.js` (`імпорт`) | UT+JS |
| AC-111 | F11-01/02/04 | Given XLSX/CSV; When `/parse/table`, `/render/table_xlsx`; Then розбір (UTF-8/Windows-1251, роздільники), ліміти 25 МБ/200 000 рядків/200 колонок, «туди-назад» без втрат на золотих `s4_python.xlsx`/`s4_roundtrip.xlsx`; без групи «Перегляд» — `rights`. Тести: `test_s4_tabular.py` `TestS4Tabular`, `TestS4TabularApi`; HOOT `s4.test.js`; Playwright `test_s4.js` (`файли`) | UT+JS |
| AC-112 | F11-03/05 | **Не зроблено.** Імпорт/експорт `.whproj.json` і одноразове перенесення проєктів «Конструктора складу» (CD-31 Q3) очікують зразків файлів (CD-31 Q12) — Q-16 | — |
| AC-113 | F17 | Given зони або склад; When «Розкласти автоматично»; Then зони полицями в контурі, ряди вглиб, перешкоди (проходи, `items`, розміщення, колони сітки) обходяться, **колони сітки ігноруються лише якщо з ними не вміщається** (`gridIgnored`), не вміщається — нічого не змінюється й названо потрібний розмір; одна зміна (Ctrl+Z). Тести: `tools/test_core_s4.mjs`; Playwright `test_s4.js` (`розкладка`) | JS+PW |
| AC-114 | F18-01…06 | Given шар `building`; When API-04 `td.layer.items`; Then об'єкти нормалізуються (R-22; ≤ 5000, види, розміри, `location_uid` лише gate/dock), проєктувальник шару пише `items`, але не налаштування шару; контур — `bounds` ≥ 3 точок. Тести: `test_s5_checks.py` `TestS5Building` (`items_normalization_and_errors`, `layer_items_validation_and_load`, `layer_items_rights`), `TestNewFieldsApi.test_designer_writes_layer_items_but_not_layer_settings`; HOOT `s5.test.js`; Playwright `test_s5.js` | UT+JS |
| AC-115 | F18-08, N-07 | Given сцена; When `inside`, `aisle_width`, `height`; Then зауваження за R-37 п. 4…6 (поза контуром, перетин колони (явної чи сітки)/стіни/офісу/зарядки, вузький прохід і проїзд між рядами, вище стелі чи ближче 0.5 м до спринклерів); Python і JS збігаються на `s5_golden.json`. Тести: `TestS5Building` (`fixtures_match_code`, `inside_with_contour_and_items`, `aisle_width_by_site_and_zone_tech`, `height_against_ceiling_and_sprinklers`); HOOT `s5.test.js`; `tools/test_core_s5.mjs` | UT+JS |
| AC-116 | F18, F17 | Given колони `site.column_grid` (крок 6×6) і авторозкладка, що обійшла їх (`gridIgnored`) та поставила ряд на вузол сітки; When `inside` (`block`); Then зауваження «{код}: перетинає колону сітки (x; y)» тієї ж серйозності, що й для явної колони; вузол під явною колоною не дублюється; повернутий ряд і розміщення теж перевіряються; крок сітки 0 — колон немає; `block` зупиняє публікацію (R-04), `warn` — ні. Python і JS збігаються на `s5_golden.json` (сцени `inside_grid`, `inside_grid_off`). Тести: `TestS5Building.test_inside_column_grid`; `tools/test_core_s5.mjs`; Playwright `test_s5.js` (`t_grid_check`: авторозкладка з `gridIgnored` → `inside` показує колону) | UT+JS+PW |
| AC-117 | N-06 | Given `site.aisle_tech` і `slot.tech` зони; When `aisle_width`; Then діє найменша зона з власною технікою, `ключ:мін_м` задає свій мінімум, «не перевіряти» вимикає, «як у складу» наслідує. Тести: `TestS5Building.test_tech_catalog_and_zone_resolution`, `test_aisle_width_by_site_and_zone_tech`; HOOT `s5.test.js` | UT+JS |
| AC-118 | F15-01/04 | Given стелажі різних типів; When `rack_spec.build_spec`, `/render/spec_pdf`; Then кількості рам/балок/полиць/стійок/консолей/зв'язок/стяжок за R-38, підсумки за типорозмірами, XLSX/PDF з кирилицею; payload `{site_id}` рахується на сервері; Python і JS збігаються. Тести: `TestS5Building.test_spec_from_db_state`, `TestS5Docs` (`spec_xlsx_from_tables`, `spec_pdf_from_tables_has_cyrillic_text`, `spec_computed_by_server_for_site`, `spec_validation`, `spec_xlsx_sheet_names_unique_and_empty_tables`); `tools/test_core_s5.mjs` | UT+JS |
| AC-119 | F15-02 | Given план; When `/render/plan_pdf`; Then PDF вектором потрібного розміру з текстом кирилицею, валідація `ops`/`page`; без групи «Перегляд» — `rights`. Тести: `TestS5Docs` (`plan_pdf_page_size_and_text`, `plan_pdf_validation`, `rights_without_viewer_group`, `routes_return_base64_files_and_errors`); HOOT `s5.test.js` | UT+JS |
| AC-120 | F15-03 | **Не зроблено.** Експорт «Місця в Excel» (код, штрихкод, зона, ряд, секція, ярус, позиція, тип, габарити, ємність, макс. вага, категорія, залишок, статус existing/new/changed, id Odoo) — Q-17 | — |
| AC-121 | F16 | Given порожня площадка; When майстер «З нуля» (6 кроків); Then кожен крок — звичайна зміна з Ctrl+Z, повторне «Застосувати» замінює створене кроком, склад не створюється, `/site/wizard` пише `wizard_state` ≤ 256 КБ без зміни лічильника чернетки; проєктувальник без права на шар — `rights`. Тести: `test_s5_wizard.py` `TestS5Wizard`; `tools/test_core_s5.mjs`; Playwright `test_s5.js` | UT+JS+PW |
| AC-122 | F12-01/02 | Given менеджер; When API-21 `create/activate/rename/delete`; Then «Як є» створюється автоматично, переключення зберігає чернетку в знімку, до 12 робочих варіантів, дубль назви без урахування регістру й видалення активного/єдиного — `validation`, не-менеджеру — `rights`. Тести: `test_s6_collab.py` `TestVariants` (`ensure_creates_as_is`, `create_switch_back_keeps_draft`, `delete_rules_and_limit`, `rights_manager_only`), `TestCollabApi.test_variants_api_flow`; HOOT `s6.test.js` | UT+JS |
| AC-123 | F12-03/04 | Given два варіанти; When порівняння, публікація; Then цифри `cells/places/area/volume/max_weight/ops` порівнюються, публікація й застосування лише активного варіанта (`version.variant_id`). Тести: `TestVariants.test_publish_version_gets_variant`; `tools/test_core_s6.mjs`; Playwright `test_s6.js` (`варіанти`) | UT+JS+PW |
| AC-124 | F12-05, F19-04 | Given тур, що змінює дані; When запуск; Then створюється навчальна копія, «Залишити зміни» робить її робочим, «Скасувати» повертає варіант-джерело й видаляє копію, публікація копії заборонена; копія одна. Тести: `TestVariants.test_training_copy_cancel_and_keep`, `TestCollabApi.test_training_via_api`; Playwright `test_s6.js` (`тури`) | UT+PW |
| AC-125 | F13-01/04 | Given користувачі; When API-22; Then будь-хто з «Перегляд» додає й читає, змінює/вирішує/видаляє автор або «Проєктування», чужий читач — `rights`; текст ≤ 4000, вид/об'єкт перевіряються. Тести: `TestComments` (`viewer_adds_designer_resolves`, `other_viewer_cannot_resolve_or_delete`, `validation`, `update_only_author_or_designer`) | UT |
| AC-126 | F13 | Given задача з виконавцем; When створення, вирішення, зміна виконавця; Then рівно одне `mail.activity` у виконавця, вирішення/нотатка його закривають; виконавець без доступу — `validation`; виконавця має лише задача. Тести: `TestComments.test_task_creates_activity_and_resolve_closes_it`, `test_assignee_rules` | UT |
| AC-127 | F13-02/03 | Given коментарі; When редактор; Then значки з числом (синій — нотатка, помаранчевий — відкрита задача, сірий — усе вирішено), блок у правій панелі, фільтри статус/вид/текст/«лише цей об'єкт», опитування раз на 15 с не стирає набраного. Тести: HOOT `s6.test.js`; `tools/test_core_s6.mjs`; Playwright `test_s6.js` (`коментарі`) | JS+PW |
| AC-128 | F14-01/03, CD-31 Q6 | Given дві сесії; When API-23 `acquire/release`; Then оренда на `lock_ttl_s`, чужа діюча — `locked`, правка в чужій зоні — `AccessError`/`rights`, прострочена не блокує, об'єкт поза зонами блокує себе, проєктувальник без ролі не бере оренду; `su` обходить. Тести: `TestZoneLocks` (7 тестів), `test_s6_collab.py` | UT |
| AC-129 | F14-02 | Given оренди; When редактор; Then значки з іменем (червоний — чужа, зелений — моя), список раз на 15 с, банер оновлюється на місці; в артефакті блокувань і значків немає (`locks=false`). Тести: HOOT `s6.test.js`; Playwright `test_s6.js` (`блокування`) | JS+PW |
| AC-130 | F19-01 | Given користувач; When GET `/f3d/constructor/help?lang=uk|en`; Then QWeb-сторінка з 36 темами, ті самі тексти, що `help_topics.js` (id збігаються), без входу — редирект; перелік id турів у `tour_defs.js` (`welcome`, `basic`, `rack`, `import`, `scratch`, `address`, `putaway`, `apply`, `find`, `labels`, `docs`, `team`) зафіксовано. Тести: `test_s6_help.py` `TestHelp` (`topics_in_sync`, `tour_catalogue`, `help_route_renders_both_languages`, `help_requires_login`) | UT |
| AC-131 | F19-02/03 | Given `web.assets_tests`; When `start_tour` (`td_constructor_guide_tour`, `_variants_tour`, `_collab_tour`); Then тури виконуються в браузері Odoo (реєстрація в `web_tour.tours`; у `web.assets_backend` вони не працювали). Тести: `test_s6_tours.py` `TestS6Tours` | UT |
| AC-132 | F19-05, CD-31 Q7 | Given перемикач UK/EN; When вибір мови; Then шапка, вкладки, меню, діалоги S6 перекладені (`t()`), решта ядра — DOM-перекладачем; вибір запам'ятовується; `en.po` покриває всі msgid `.pot` (> 500) і не лишає українських термінів без перекладу, `uk.po` не змінює джерел. Тести: `TestHelp.test_po_files_uk_and_en`; HOOT `s6.test.js`; `tools/test_core_s6.mjs`; Playwright `test_s6.js` (`мова`). Повне покриття `t()` — Q-15 | UT+JS |
| AC-133 | N-01 | Given рівні WH › зона › ряд › стелаж › ярус; When вибір рівня, «↑», «⟲», мініатюра; Then решта ховається, камера наїжджає, клік по сцені піднімає вибір, мініатюра переносить камеру. Тести: `tools/test_core_s6.mjs`; Playwright `test_s6.js` (`рівні`) | JS+PW |
| AC-134 | N-03 | Given версії; When `/version/view`, `/version/checkpoint`; Then останні 50 із видом (`publish`/`checkpoint`), перегляд знімка (лише читання), контрольна точка без змін в Odoo, точки понад `versions_keep` прибираються, публікації — ніколи; нотатку версії міняє менеджер. Тести: `TestCollabApi.test_checkpoint_and_view`, `test_checkpoints_pruned_publications_kept`; HOOT `s6.test.js`; Playwright `test_s6.js` (`історія`) | UT+JS |
| AC-135 | R-22, R-40 | Given нові поля M-25…M-27; When API-03/04, знімок; Then `load` без даних дає порожні розширення, `save`↔`load` без втрат, невідомі посилання — `validation`; знімок `schema: 2` не змінюється для незміненої чернетки, містить і відновлює нові поля, знімок `1` скидає їх до типових, видалені посилання ігноруються. Тести: `test_new_fields_api.py` `TestNewFieldsApi`, `TestNewFieldsSnapshot` | UT |
| AC-136 | API-11…24 | Given контролери; When маршрути; Then кожен маршрут §7.1 зареєстровано рівно один раз, заглушок `not_implemented` не лишилося. Тест: `test_skeleton_api.py` `TestSkeletonApi` | UT |
| AC-137 | §5.4 | Given стара база `19.0.1.0.x`…`1.3.0`; When `-u td_constructor`; Then міграції ідемпотентні: `floor_spot` додається в дозволені типи шарів «Склади» (порожній список лишається порожнім; неактивні шари й змінена чернетка не чіпаються), довідники зони прив'язуються до xml-id. Тести: `test_s1_migration.py` `TestMigrationFloorSpot`, `TestS2Capacity.test_pre_migrate_binds_existing_zone_terms_to_xmlids` | UT |
| AC-138 | R-11, §13.3 | Given ролі «без групи», «перегляд», «проєктування», менеджер; When кожен API-11…24 і `/site/*`; Then читання — лише «перегляд», запис — за таблицею §7.1, публікація/відкат/варіанти/категорії — менеджер; `ok: false` з `rights` без побічних ефектів. Тести: `TestSkeletonRights`, `TestS2PlanApi.test_rollback_rights`, `TestS2StorageApi`, `TestS4Api.test_rules_route_rights`, `TestS4TabularApi.test_parse_table_requires_view_group`, `TestS5Docs.test_rights_without_viewer_group`, `TestS3StockApi.test_state_validation_and_rights` | UT |

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
| ТК-01 | Меню «3D Завод → Планування → Конструктор» | відкривається редактор площадки «Меблеве підприємство»: будівля 150×72, шари, стелажі ГП із комірками, станки |
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

### 13.6 Тести хвиль 0–2 (злиття): файли, класи, запуск

**Python (Odoo, `odoo_addons/td_constructor/tests/`, теги `post_install`, `-at_install`, `f3d`, `f3d_constructor` і тег слайса `f3d_s1`…`f3d_s6` (`TestCoreNode` — `f3d_core`); ≈ 300 тестів у файлах нижче).** Базові класи — `common.py` (`F3DConstructorCase`, `F3DConstructorHttpCase`); еталони й «золоті» дані — `golden_s1.py`, `golden_s3.py`, `golden_s4.py`, `golden_s5.py`, `golden_scenes.py`.

| Файл | Класи | AC |
|---|---|---|
| `test_skeleton_models.py`, `test_skeleton_rights.py`, `test_skeleton_api.py`, `test_install.py` | `TestSkeletonModels`, `TestSkeletonRights`, `TestSkeletonApi`, `TestInstall` | 70, 136, 138 |
| `test_registries.py`, `test_registry_hooks.py` | `TestRegistries`, `TestRegistryHooks`, `TestRegistryHooksApi` | 71 |
| `test_new_fields_api.py` | `TestNewFieldsApi`, `TestNewFieldsSnapshot` | 114, 135 |
| `test_s1_addr.py`, `test_s1_catalog.py`, `test_s1_checks.py`, `test_s1_library.py`, `test_s1_golden.py`, `test_s1_migration.py`, `test_s1_core_node.py` | `TestAddrEngine`, `TestAddrModels`, `TestSiteAddrApi`, `TestCatalog`, `TestChecksWithAddressing`, `TestLibraryApi`, `TestS1Golden`, `TestMigrationFloorSpot`, `TestS1CoreNode` | 74…82, 137 |
| `test_s2_plan.py`, `test_s2_capacity.py`, `test_s2_putaway.py`, `test_s2_core_node.py` | `TestS2Plan`, `TestS2PlanApi`, `TestS2Capacity`, `TestS2StorageApi`, `TestS2Putaway`, `TestS2PutawayApi`, `TestS2CoreNode` | 77, 83…98 |
| `test_s3_labels.py`, `test_s3_stock.py`, `test_s3_core_node.py` | `TestS3Labels`, `TestS3LabelsApi`, `TestS3StockState`, `TestS3StockApi`, `TestS3CoreNode` | 99…102 |
| `test_s4_sync.py`, `test_s4_tabular.py`, `test_s4_core_node.py` | `TestS4Schema`, `TestS4Feed`, `TestS4PublishBaseline`, `TestS4Api`, `TestS4Tabular`, `TestS4TabularApi`, `TestS4CoreNode` | 88, 108…111 |
| `test_s5_checks.py`, `test_s5_docs.py`, `test_s5_wizard.py`, `test_s5_core_node.py` | `TestS5Building`, `TestS5Docs`, `TestS5Wizard`, `TestS5CoreNode` | 114…119, 121 |
| `test_s6_collab.py`, `test_s6_help.py`, `test_s6_tours.py` | `TestVariants`, `TestCollabApi`, `TestComments`, `TestZoneLocks`, `TestHelp`, `TestS6Tours` | 122…126, 128, 130…132, 134 |
| `test_core_node.py`, `test_hoot_editor.py`, `test_hoot_model.py` | `TestCoreNode` (запускає `node tools/test_core.mjs`), `TestEditorHoot`, `TestModelHoot` | 72, JS-частини |

Запуск (за конвенцією проєкту, `T=factory3d/tools/odoo`): `F3D_TEST_INSTALL=td_constructor $T/run_tests.sh <db> /td_constructor` (усе), `…/td_constructor:TestS2Plan` (клас), `…/td_constructor:TestS6Tours` (тури; браузер Chrome потрібен `start_tour`).
**Нестабільність:** тести S3 (`test_s3`) бувають нестабільними під навантаженням (кілька агентів на одному сервері) — Q-18; при падінні перезапустити окремо й порівняти.

**Node (ядро без Odoo):** `node tools/test_core.mjs` — відносні імпорти, контракт адаптера, збірка свіжа (з `ESBUILD_DIR`), реєстр слайсів + `tools/test_core_s1.mjs` (адреси, каталог 50 типів ≡ XML, пресети), `_s2.mjs` (план, ємність, правила, «чи вміститься»), `_s3.mjs` (скасування, виділення, етикети, ZPL, теплові карти, пошук, доступ), `_s4.mjs` (розбір кодів, лоток, CSV/XLSX, авторозкладка, розбіжності),
`_s5.mjs` (будівля, перевірки, специфікація, документи, майстер), `_s6.mjs` (варіанти, коментарі, оренди, тури, мови, рівні, мініатюра, історія). Кожен файл запускається й окремо. Збірка: `node tools/build_core.mjs module --check`.

**HOOT** (`static/tests/editor/`, suite `@td_constructor/editor`, запускає `TestEditorHoot`): `engine.test.js`, `editor.test.js`, `store.test.js`, `dxf.test.js` (W2), `s3.test.js` (4 тести), `s4.test.js` (4), `s5.test.js` (5), `s6.test.js` (7); хелпери `core.js` (`setupCore`), `helpers.js`, `fixtures.js`; модельні тести W3 — `static/tests/model/*`.

**Playwright (прототип, `build/constructor/proto/`):** `PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node build/constructor/proto/test_s<N>.js [набір]` після `python3 build/constructor/proto/build.py`; набори — S3: `undo, multi, tools, align, labels, heat, search, card, mobile, save`; S4: `імпорт, файли, лоток, розкладка, розбіжності, правила`; S6: `chrome, варіанти, коментарі, рівні, мова, тури, запрошення, історія, блокування`;
S1, S2, S5 — власні набори (`test_s1.js`, `test_s2.js`, `test_s5.js`); загальні — `smoke.js`, `test_ac.js`, `test_cell.js`, `test_idb.js`, `test_misc.js`, `test_nostorage.js`, `test_reload.js`, `test_scene.js`, `test_upgrade.js`. Потрібні каталоги `vendor/` і `fixtures/` **поза репозиторієм** (як у PROTOTYPE.md).

**Додатково до §13.3 (безпека):** кожен API §7.1 має перевірки за ролями (AC-138); ін'єкції — `addr` (`tpl` лише `[A-Za-z0-9._/#:-]`, ≤ 64), `parse_rules.mask/regex`, `code` типу (регулярка), `zone_uid` ≤ 32, JSON ≤ 256 КБ / 8 рівнів (R-22); `confirm: true` для API-12 save/delete, API-18 rollback, API-07 publish; нічого не видаляється в Odoo (відкат архівує, публікація архівує лише з `archive_codes`).
**Додатково до §13.4 (продуктивність):** `stock/state` — пачки ≤ 2000 локацій і ≤ 2 МБ (`TestS3StockState.test_batches`); стрічка локацій — пачки ≤ 20 000; бюджет прототипу 900 КБ (`test_scene.js`). **Навантажувального тесту на 5–50 тис. комірок немає** — Q-21.

## 14. Definition of Done

- [ ] Усі UT (W1) і HOOT (W2, W3) зелені: `run_tests.sh` повертає `OK`; AC-01…AC-68 покриті (UT/JS) або пройдені за ТК (MAN) зі скриншотами.
- [ ] `ruff check` (конфіг base `ruff.toml`) без зауважень; нема `x_`-полів; у bundle немає зовнішніх URL (AC-05).
- [ ] Модуль ставиться на чисту базу й на копію демо-бази; `post_init_hook` ідемпотентний (AC-02, AC-03).
- [ ] Права: AC-43…AC-47, AC-56 і §13.3 пройдені; перегляд безпеки (rules, `sudo` лише в `publish`).
- [ ] `neutralize.sql` не потрібен (немає кронів, джерел, токенів) — зафіксовано в README модуля.
- [ ] `README.md`, `CHANGELOG.md`, `DEPLOY_TEST.md`; інструкції ARCH §4 перенесені в README.
- [ ] Відхилення від CD-16 (DEC-03) підтверджене замовником або позначене в README як «очікує підтвердження» (Q-01).

- [ ] Злиття (хвилі 0–2): AC-70…AC-138 покриті або мають відкрите питання (AC-112, AC-120 — Q-16, Q-17; AC-116 і Q-19 закрито у `19.0.1.4.1`); `node tools/test_core.mjs` і `node tools/build_core.mjs module --check` зелені; Playwright `test_s1…s6.js` пройдені перед публікацією прототипа; `i18n/*.po` без розбіжностей з `.pot` (AC-132).
- [x] `CHANGELOG.md` модуля має запис кожної версії до `19.0.1.4.1`; `core/constructor/README.md` описує S1…S6; `README.md` модуля оновлено під хвилі 1–2 (моделі, API-11…24, меню, ролі, параметри, «Як перевірити на тестовому сервері»).
- [ ] `DEPLOY_TEST.md` модуля (§13.5) **ще не створено**: файла немає, чек-лист §13.5 здає інтеграція (ARCH §5.3).

## 15. Відкриті питання

Ті самі номери, що в ARCH §5.1: Q-01 (відхилення від CD-16), Q-02 (серверні конвертери), Q-03 (шаблон «зона» → `td.zone`), Q-04 (хто публікує), Q-05 (архівація при залишках), Q-06 (DWG на сервері), Q-07 (префікси кодів між площадками), Q-08 (фаза 2: переглядач з розкладки), Q-09 (ліміти навантаження), Q-10 (досяжність підключення), Q-11 (типові габарити), Q-12 (коди й види комірок консольних/підлогових шаблонів), Q-13 (`mrp_maintenance`), Q-14 (шлях Hoot-suite).


Нові питання злиття (повний опис — ARCH §5.1; відповіді CD-31 Q1…Q11 прийнято, див. `build/constructor/DECISIONS.md`):

| ID | Питання | Що робимо тим часом |
|---|---|---|
| Q-15 | Англійська через `t()`: зараз EN покриває DOM-перекладач `i18n.js` (точні фрази й шаблони), `t()` є лише в 7 файлах S6; потрібні виклики `t()` у ≈ 20 файлах ядра (панелі, діалоги, `app.js`, `addr.js`, `types_ui.js`, `capacity_ui.js`, `rules_dialog.js`, `plan_dialog.js`, `files_ui.js`, `sync_ui.js`, `docs_ui.js`, `building_ui.js`, `wizard.js` …) | режим EN працює через DOM-перекладач; нові рядки реєструються `addEn()` у своєму файлі (AC-132) |
| Q-16 | F11-05 `.whproj.json` (експорт/імпорт проєкту) і CD-31 Q3 (одноразовий імпорт проєктів «Конструктора складу» в площадки й варіанти, відключення `wh_constructor`) — чекають зразків файлів від замовника (CD-31 Q12) | не реалізовано (AC-112); `wh_constructor` не відключається |
| Q-17 | F15-03 «Місця в Excel» (код, штрихкод, зона, ряд, секція, ярус, позиція, тип, габарити, ємність, макс. вага, категорія, залишок, статус, id Odoo) не зроблено | не реалізовано (AC-120); сервер уже вміє `table_xlsx` (R-36) |
| Q-18 | `test_s3` нестабільний під навантаженням | перезапуск окремо (§13.6) |
| Q-19 | Колони `column_grid` при нестачі місця ігноруються авторозкладкою (`gridIgnored`), але `inside` їх не бачив (R-37 п. 2) — зауваження не було | **Закрито у `19.0.1.4.1`:** `inside` (Python і JS) бачить вузли `site.column_grid` так само, як `obstacleRects` (`grid_nodes` ↔ `gridNodes`), серйозність = режим перевірки, як в явної колони (R-37 п. 2, 4; AC-116). Авторозкладка без змін: колони сітки обходяться, поки це можливо; якщо ні — ряд може стояти на колоні, але це видно в `inside`, а в `block` план не публікується |
| Q-20 | Еталонні файли «Конструктора складу» (CD-31 Q12): формули специфікації стелажів (R-38), авторозкладки (§8.5), ZPL відновлено за інструкцією | реалізовано за інструкцією; зразки — звірити |
| Q-21 | Склад 5–50 тис. комірок: навантажувальний тест (пачки `stock/state`, `InstancedMesh`) не виконано (MERGE §5.4) | пачки й ліміти (§13.4); тест на копії бази замовника перед продом |
| Q-22 | Міст `td_constructor_viewer3d` (`19.0.1.0.0`) не оновлювався: власна копія малювання каркаса (`slot_view.js`), немає `floor_spot`, `double_sided`, форм типів, об'єктів будівлі | міст малює те, що вміє; перехід на бандл ядра (ARCH CC-05) |

## Журнал змін документа

| Версія | Дата | Зміни |
|---|---|---|
| 0.1 | 17.10.2026 | перший випуск: M-01…M-15, V-01…V-13, API-01…API-10, R-01…R-24, AC-01…AC-68, Q-01…Q-14 |
| 0.2 | 19.10.2026 | злиття з «Конструктором складу» (хвилі 0–2, модуль `19.0.1.4.0`): §0.1 і §1.1 (файли, маніфест); §2.1 і M-16…M-31; §3.1 V-14…V-18 і меню; §4.5 права; §5.4 дані й міграції; §6 (кронів немає); §7.1 API-11…API-24 і маршрути `/site/addr`, `/odoo/rules`, `/site/wizard`, `/help`, `/storage/loads`, `/putaway/lookup`, `/removal_strategies`; §8.4 ядро + адаптер, §8.5 правила ядра; §9.1 R-25…R-41 (реєстри — R-41); §10.1, §11.1; §12.1 AC-70…AC-138; §13.6 тести; §14, §15 (Q-15…Q-22). Існуючі ID не змінено; `static/src/editor/*` у §0 замінено ядром (CD-29), `.po` тепер ведуться (CD-31 Q7) |
| 0.3 | 19.10.2026 | дефект `inside` і колони сітки (модуль `19.0.1.4.1`): R-37 п. 2 і 4, §8.5, AC-115, AC-116, чек-лист, Q-19 закрито; лише код перевірки й тести, дані й схема без змін |
