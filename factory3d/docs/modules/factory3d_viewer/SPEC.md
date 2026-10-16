# factory3d_viewer — специфікація

Версія 0.2 · 14.10.2026 (0.1 — 13.10.2026) · технічне рішення: `docs/modules/factory3d_viewer/ARCHITECTURE.md` (FR-01…FR-44,
A-01…A-17, Q-01…Q-08). Контракти, на які спирається: C-01 (`f3d.scene.mixin`, `factory3d_base` CB-01/CB-02),
C-08 (зони й ворота, `factory3d_base`), C-09 (паспорт, `factory3d_base`); контракти, які задає: C-02
(хук провайдера), C-03 (шина `f3d_viewer`), C-04 (HTTP API), C-05 (клієнтська дія), C-06 (знімки й
події), C-07 (шляхи сигналів). Формат даних — `dist/odoo_demo.json` + ключі модулів, `meta.schema = "1.1"` (Додаток A).
Зміни: 15.10.2026 — за рішеннями модуля (build/modules/factory3d_viewer.md): DEC-5 (§0: вбудовані провайдери по файлу `models/viewer_provider_<key>.py`), DEC-12 (§0, §8.2: панель, шар замовлень, потік, тривога й енергія — у `core.js`, без окремих `panel/overlay/flow/drill/energy.js`; вкладені шаблонні літерали заборонені — `rjsmin` їх псує; §8.4: поріг lite `deviceMemory <= 4`), DEC-15 (§0, §5.1: `neutralize.sql` у `data/`; додатково `bus_enabled=False`).

Зміни: 14.10.2026 — правки за CONSISTENCY.md: X-08 (кнопки «Показати в 3D» на формах носіїв домішки — у base CB-02;
V-02…V-07 вилучено, M-09, AC-22), X-09 (M-01f читає `hr.employee.public` без `sudo`, §4.4), X-14 (`f3d_loc_kind`,
`f3d_capacity` з base, R-04, Q-09 закрито), X-15 (код фури — `stock.picking.batch.f3d_code`, R-05, R-16, M-07),
X-19 (власний привілей групи кіоска, M-10, §4.3), X-22 (duck-typing контракт провайдера, M-01, R-01, R-14), X-23 і X-82
(глибоке злиття дельти, хелпер `deep_merge` у `tools/payload.py`, M-01, R-14), X-24 (схема 1.1, Додаток A.0, A.15),
X-25 (`energy_cost` лише з групою вартості energy, §4.4, R-07), X-26 (A.12 `cable`), X-27 (sequence 75 і 155, M-01),
X-28 (клієнт: навчальна тривога, стани й пристрої fire, рядки СКУД, x/y — фаза 4; §8.1–8.2), X-29 (45 зон, контури
надвірних з `f3d.zone`, M-01g, R-13), X-30 (меню 10/12/14/16, налаштування під `menu_f3d_config`, V-01); нові AC-56…AC-67;
§15 — закрито Q-09.
Зміни: 14.10.2026 — закрито відповідями замовника (CONSISTENCY, «Відповіді на питання до замовника»): Q-06, Q-08.
Зміни: 14.10.2026 — закрито рішеннями менеджера: Q-10, Q-11.
Зміни: 14.10.2026 — закрито відповідями замовника № 25–36 (прийнято рекомендації): Q-02, Q-05.
Зміни: 14.10.2026 — у макеті додано групи FA-SOC (LSZ 34) і FA-OFFICE (LSZ 35), відповідь № 12г: A.13 `fire.groups` 33 → 35, `fire.totals.detectors` 212 → 222; `passports` 205 → 207 (A.0, A.14); обладнання демо-бази 208 → 210 (M-04 крок 29, §5.4 крок 2: `FA-SOC`, `FA-OFFICE` з `manifest.parts[].codes` резолвляться в нове обладнання).

Позначення: UT — юніт-тест (`odoo.tests`), HT — HttpCase/тур, JT — HOOT-тест клієнта, MAN — ручна
перевірка на тестовому сервері timur-o19demo (база `odoo`).

## 0. Дерево файлів модуля

```
odoo_addons/factory3d_viewer/
├── __init__.py                      імпорт models, controllers, wizard, tools; post_init_hook, uninstall_hook
├── __manifest__.py                  §1
├── hooks.py                         post_init(env), uninstall(env) — ARCHITECTURE §2.8
├── README.md                        коротко: що це, URL кіоска, як оновити асети
├── CHANGELOG.md
├── models/
│   ├── __init__.py
│   ├── viewer_provider.py           M-01 абстрактний провайдер
│   ├── viewer_provider_<key>.py     M-01a…M-01h вбудовані: по файлу на провайдер (stock, production, logistics, quality, maintenance, people, chains, signals)
│   ├── viewer_event.py              M-03 f3d.viewer.event (+ _notify, крон сигналів)
│   ├── viewer_snapshot.py           M-02 f3d.viewer.snapshot (+ крони знімків і ротації)
│   ├── bus_emitters.py              M-07 перевизначення write/create/unlink 9 стандартних моделей
│   ├── mrp_production.py            M-08 action_f3d_show
│   ├── stock_picking.py             M-08
│   └── res_config_settings.py       M-06
├── controllers/
│   ├── __init__.py
│   ├── viewer.py                    API-01…API-07, API-10, API-11, API-12
│   └── kiosk.py                     API-08, API-09
├── wizard/
│   ├── __init__.py
│   ├── demo_wizard.py               M-04 f3d.demo.wizard
│   ├── demo_wizard_views.xml        V-10
│   ├── orm_proxy.py                 адаптер OrmProxy (A-08)
│   ├── demo_steps.py                порт plant/odoo_push.py Push + plant/odoo_flows.py FlowSteps (35 кроків)
│   ├── cycle_check_wizard.py        M-05 f3d.viewer.cycle.check
│   └── cycle_check_views.xml        V-11
├── tools/
│   ├── __init__.py
│   ├── payload.py                   PayloadBuilder (R-01), DeltaBuilder (R-14), resolver (R-16), deep_merge (M-01, X-82)
│   ├── cycle_check.py               копія plant/cycle_check.py (функція check(d) без змін)
│   ├── dates.py                     local(dt)/utc(s)/now(env) за Europe/Kyiv (R-02)
│   └── static_data.py               завантаження й кеш model_static.json, demo_payload.json, manifest
├── security/
│   ├── ir.model.access.csv          §4
│   ├── security.xml                 group_f3d_kiosk, record rules
│   └── kiosk_user.xml               user_kiosk (noupdate)
├── data/
│   ├── params.xml                   ir.config_parameter (noupdate)
│   ├── cron.xml                     4 крони §6
│   ├── neutralize.sql               demo_enabled=False, kiosk_enabled=False, bus_enabled=False, новий kiosk_token, крони вимкнути (Odoo читає лише `data/neutralize.sql`)
│   └── actions.xml                  ir.actions.client action_f3d_viewer, server action «Новий токен кіоска»
├── views/
│   ├── menus.xml                    V-01
│   ├── show_in_3d_views.xml         V-08a, V-08b кнопки на формах МО й переміщення (V-02…V-07 вилучено, X-08)
│   ├── viewer_snapshot_views.xml    V-12, V-13
│   ├── viewer_event_views.xml       V-14
│   ├── res_config_settings_views.xml V-15
│   └── templates_kiosk.xml          QWeb factory3d_viewer.kiosk_page
├── static/
│   ├── description/icon.png, index.html
│   ├── lib/three/
│   │   ├── three-bundle.esm.js      зібраний esbuild (A-01), експорт {THREE, OrbitControls, GLTFLoader, CSS2DRenderer, CSS2DObject, RoomEnvironment}
│   │   ├── three-bundle.esm.js.map
│   │   └── LICENSE                  MIT three.js
│   ├── model/parts/
│   │   ├── manifest.json            копія dist/parts/manifest.json + поле hash у кожній частині (§8.5)
│   │   ├── core.glb  engineering.glb  fire.glb  it.glb  site.glb
│   ├── data/
│   │   ├── model_static.json        Додаток B (генерується plant/export_viewer_assets.py)
│   │   ├── demo_payload.json        = Demo().build() (A-08), 1,07 МБ
│   │   └── BUILD.json               {"built_at", "git": sha, "three": "0.160.0", "schema": "1.1"}
│   ├── src/
│   │   ├── action/
│   │   │   ├── viewer_action.js     OWL F3dViewerAction (§8.1)
│   │   │   └── viewer_action.xml    шаблон factory3d_viewer.ViewerAction
│   │   ├── viewer/
│   │   │   ├── core.js              клас F3dViewer (§8.2) — сцена, частини, шари, види, вибір, підсвічування; у тому ж файлі (спільне замикання): вкладки й картки (R10–R19), шар «Замовлення в роботі» (R7), «Потік зміни» + програвання (R3, R4), пожежна тривога (R21), «Енергія» (R17, R18)
│   │   │   ├── data_client.js       DataClient: /static, /data, /delta, шина, дебаунс, патчі (§8.3)
│   │   │   ├── lite.js              визначення й застосування lite (§8.4)
│   │   │   ├── format.js            nf, pct, esc, plural, dayHm, KIND, *_STATE словники
│   │   │   └── viewer.scss          стилі макета (рядки 5–312 index.html) з префіксом .o_f3d
│   │   └── kiosk/
│   │       ├── kiosk.js             точка входу сторінки кіоска (§8.6)
│   │       └── kiosk.scss
│   └── tests/
│       ├── tours/show_in_3d_tour.js      §13.1 тури
│       ├── tours/click_open_record_tour.js
│       ├── tours/kiosk_tour.js
│       └── hoot/*.test.js                JT-тести панелі на demo_payload.json
├── tests/
│   ├── __init__.py
│   ├── common.py                    F3dViewerCase(TransactionCase): фікстури (§13.0)
│   ├── test_install.py
│   ├── test_payload_static.py  test_payload_stock.py  test_payload_production.py
│   ├── test_payload_logistics.py  test_payload_chains.py  test_payload_signals.py
│   ├── test_providers.py            хук, порядок, помилка провайдера
│   ├── test_access.py               права, sudo-lint
│   ├── test_resolver.py
│   ├── test_bus.py  test_snapshot.py  test_delta.py (+ TestDeepMerge, X-82)
│   ├── test_show_in_3d.py
│   ├── test_kiosk.py
│   ├── test_demo_wizard.py
│   ├── test_cycle_check.py
│   ├── test_controllers.py          HttpCase для API-01…API-10
│   ├── test_tours.py                HttpCase start_tour
│   └── test_perf.py
└── i18n/uk_UA.po                    рядки інтерфейсу (інтерфейс первинно українською, en — технічний)

Міст-модуль (A-17), ставиться автоматично разом із sale:
odoo_addons/factory3d_viewer_sale/
├── __manifest__.py                  depends factory3d_viewer, sale; auto_install True
├── __init__.py
├── models/__init__.py, models/sale_order.py     M-08: action_f3d_show, f3d_has_3d
├── views/sale_order_views.xml       V-09 кнопка «Показати в 3D»
└── tests/__init__.py, tests/test_sale_show.py

Допоміжний тестовий модуль (лише CI/тестовий сервер, не для проду; §13.0):
odoo_addons/test_factory3d_viewer/
├── __manifest__.py                  depends factory3d_viewer; installable True; application False
├── __init__.py, models/__init__.py
└── models/providers.py              f3d.viewer.provider.zz_test (seq 5, пише zones["Z-TEST"]), f3d.viewer.provider.zz_fail (seq 6, ValueError("boom"), sections fire),
                                     f3d.viewer.provider.zz_duck (AbstractModel за префіксом без _inherit, seq 152, sections ("infra", "zz_duck"),
                                     без _f3d_viewer_delta і _f3d_viewer_bus_models, пише infra.cards["ZZ-DUCK"] і zz_duck = {"ok": true};
                                     AC-57…AC-59)

Поза модулем (репозиторій):
plant/export_viewer_assets.py        збирає static/data/*, static/model/*, static/lib/three/* (§8.5)
viewer/index.html                    статична сторінка: після W2 — тонка обгортка, що імпортує те саме ядро
```

## 1. Маніфест

```python
{
    "name": "Завод 3D: переглядач",
    "summary": "3D-переглядач заводу всередині Odoo: живі дані з ORM, «Показати в 3D», журнал станів, кіоск",
    "version": "19.0.1.0.0",
    "author": "ToDo",
    "license": "LGPL-3",
    "category": "Manufacturing/Manufacturing",
    "website": "https://todo.ltd",
    "depends": ["factory3d_base", "bus", "web"],
    "data": [
        "security/security.xml",
        "security/kiosk_user.xml",
        "security/ir.model.access.csv",
        "data/params.xml",
        "data/actions.xml",
        "data/cron.xml",
        "views/menus.xml",
        "views/show_in_3d_views.xml",
        "views/viewer_snapshot_views.xml",
        "views/viewer_event_views.xml",
        "views/res_config_settings_views.xml",
        "views/templates_kiosk.xml",
        "wizard/demo_wizard_views.xml",
        "wizard/cycle_check_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "factory3d_viewer/static/src/viewer/viewer.scss",
            "factory3d_viewer/static/src/viewer/*.js",
            "factory3d_viewer/static/src/action/*",
        ],
        "factory3d_viewer.assets_kiosk": [
            ("include", "web._assets_helpers"),
            ("include", "web._assets_backend_helpers"),
            "web/static/src/scss/pre_variables.scss",
            "web/static/lib/bootstrap/scss/_variables.scss",
            ("include", "web._assets_bootstrap_backend"),
            ("include", "web._assets_core"),
            "web/static/src/libs/fontawesome/css/font-awesome.css",
            "factory3d_viewer/static/src/viewer/viewer.scss",
            "factory3d_viewer/static/src/kiosk/kiosk.scss",
            "factory3d_viewer/static/src/viewer/*.js",
            "factory3d_viewer/static/src/kiosk/*.js",
        ],
        "web.assets_tests": [
            "factory3d_viewer/static/tests/tours/*.js",
        ],
        "web.assets_unit_tests": [
            "factory3d_viewer/static/tests/hoot/*.test.js",
        ],
    },
    "post_init_hook": "post_init",
    "uninstall_hook": "uninstall",
    "external_dependencies": {},
    "installable": True,
    "application": False,
}
```

Порядок `data` обов'язковий: групи → користувач кіоска → доступи → параметри → дії (меню посилаються
на `action_f3d_viewer`) → крони (посилаються на моделі) → меню → решта. `static/lib/three/*` і
`static/model/*` **не** входять у бандли (A-01, A-07): вони віддаються статикою за URL
`/factory3d_viewer/static/...`. `factory3d_viewer.assets_kiosk` повторює склад
`hr_attendance.assets_public_attendance` Odoo 19 (мінімальний веб-клієнт без навігації).

## 2. Моделі

Спільні правила: `_description` українською; усі `Datetime` зберігаються в UTC (стандарт Odoo), у payload
віддаються рядками за Києвом (`tools/dates.py`, R-02); `_log_access=True` всюди, крім `f3d.viewer.event`
(`_log_access=False` — обсяг).

### M-01 `f3d.viewer.provider` — хук постачальника даних (C-02)

`_name = "f3d.viewer.provider"`, `AbstractModel`, `_description = "3D: постачальник даних переглядача"`.
Полів немає.

**Контракт провайдера — duck-typing (X-22, каркас §6.7, D-18).** Провайдер — будь-яка модель реєстру з іменем
`f3d.viewer.provider.<key>`. Дозволені два способи реєстрації: (а) `_inherit = "f3d.viewer.provider"` — вбудовані
провайдери нижче й містки auto_install, що залежать від viewer (`factory3d_telemetry_viewer` — telemetry A-20,
`factory3d_fire_safety_viewer` — fire_safety A-35); (б) `AbstractModel` за префіксом імені **без** `_inherit` моделей viewer — модулі, для
яких viewer необов'язковий (energy, machine_connect, bms, yard, access, міст `factory3d_genset`). Провайдер способу (б)
**обов'язково** визначає сам: `_f3d_sequence`, `_f3d_sections`, `_f3d_group`, `_f3d_viewer_collect`, `_f3d_viewer_delta`;
`_f3d_viewer_bus_models` — необов'язковий. Збирач (R-01) і дельта (R-14) читають кожен атрибут через
`getattr(provider, name, <умовчання з таблиці>)`, тож відсутній атрибут не ламає збирання; для способу (а) умовчання дає
успадкування від цієї моделі. Атрибути класу й методи:

| Атрибут/метод | Тип | Обов'язковий для (б) | Умовчання (`getattr` / успадкування) | Призначення |
|---|---|---|---|---|
| `_f3d_sequence` | int | так | `1000` | порядок виклику (менше — раніше): вбудовані 20…70 (`stock` 20, `production` 30, `logistics` 40, `quality` 45, `maintenance` 50, `people` 60, `chains` 70), machine_connect `machines` 75, вбудований `signals` 90, telemetry 95, energy 100, lighting 110, ventilation 120, fire 130, evacuation 140, infra 150, genset 155, yard 160, access 170 (X-27; 75 — після `chains` 70, бо доповнює `supply`/`sheet_chain`) |
| `_f3d_sections` | tuple[str] | так | `()` | ключі верхнього рівня payload, які провайдер записує; для `meta.sections` і для дельти за замовчуванням |
| `_f3d_group` | str | так | `"factory3d_base.group_f3d_user"` | xml-id групи; якщо користувач не в групі або групи немає в базі — провайдер пропускається, розділи `denied` |
| `_f3d_viewer_collect(self, payload: dict, ctx: dict) -> None` | метод | так | нічого не робить; відсутній у (б) → провайдер пропускається з WARNING у лог | заповнює/доповнює `payload` на місці; чужі й спільні розділи (`infra`, `workcenters`, `employees`, `zones`) лише доповнює (`setdefault`/`deep_merge`), не присвоює цілком |
| `_f3d_viewer_delta(self, patch: dict, ctx: dict) -> None` | метод | так | `tools.payload.default_delta(provider, patch, ctx)`: `tmp = {}`; `provider._f3d_viewer_collect(tmp, ctx)`; `deep_merge(patch, {k: tmp[k] for k in _f3d_sections if k in tmp})` (R-14 крок 5) | заповнює `patch` лише для `ctx["changes"]`; спільні розділи — лише через `deep_merge` (X-23), присвоєння `patch["infra"] = …` заборонене |
| `_f3d_viewer_bus_models(self) -> list[str]` | метод | ні | `[]` | моделі, зміни яких провайдер хоче бачити в `ctx["changes"]` (інформативно для тестів) |

**Хелпер `deep_merge` (X-23, X-82).** Розміщення — рівно `factory3d_viewer/tools/payload.py`; інші модулі імпортують
його всередині свого методу дельти: `from odoo.addons.factory3d_viewer.tools.payload import deep_merge` (yard R-20 п. 7,
td_genset R-13, energy R-18 п. 3, access M-12).

```python
def deep_merge(dst: dict, src: dict) -> dict:
    """Зливає src у dst на місці й повертає dst (той самий об'єкт)."""
    if not isinstance(dst, dict) or not isinstance(src, dict):
        raise TypeError("deep_merge: очікуються dict")
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            deep_merge(dst[key], value)          # dict + dict — рекурсивно
        else:
            dst[key] = copy.deepcopy(value)      # list, скаляр, None або dict поверх не-dict — заміна
    return dst
```

Семантика: dict зливається рекурсивно за ключами; list і скаляр (включно з `None`) замінюють значення цілком (списки
**не** конкатенуються); ключі `dst`, яких немає в `src`, лишаються; значення з `src` копіюються (`copy.deepcopy`), тож
`dst` не ділить змінних об'єктів із `src`; `dst` або `src` не `dict` → `TypeError`. Приклад:
`deep_merge({"cards": {"PV-INV": {"rows": [1]}}, "totals": {"pv_now": 468}}, {"cards": {"GENSET": {"rows": [2]}},
"totals": {"island": False}})` → `{"cards": {"PV-INV": {"rows": [1]}, "GENSET": {"rows": [2]}}, "totals": {"pv_now":
468, "island": False}}`; `deep_merge({"a": [1, 2]}, {"a": [3]})` → `{"a": [3]}`. Тести — AC-56 (`TestDeepMerge`).

`ctx` (dict, лише читання для провайдера):

| Ключ | Тип | Значення |
|---|---|---|
| `user` | `res.users` | користувач запиту (для кіоска — `user_kiosk`) |
| `now` | `datetime` (UTC, naive) | `meta.now` у UTC (R-02) |
| `now_local` | str | `"YYYY-MM-DD HH:MM"` за Києвом |
| `today` | str | `"YYYY-MM-DD"` за Києвом |
| `static` | dict | завантажений `model_static.json` (лише читання) |
| `lite` | bool | кіоск/планшет: провайдер може пропускати важкі поля (у вбудованих — `passports` і так у статиці; `lite` не змінює контракт) |
| `kiosk` | bool | запит від кіоска: приховати `sale_orders[].amount`, `productions[].energy_cost` |
| `energy_cost` | bool | користувач бачить вартість енергії: група `factory3d_energy.group_f3d_energy_cost` існує в базі, користувач у ній і не `kiosk` (X-25, X-19); інакше `productions[].energy_cost` не віддається |
| `codes` | set[str] або `None` | для delta: коди/назви, що змінились (об'єднання за всіма моделями) |
| `changes` | dict[str, set[str]] | для delta: `{model: {codes}}` з `f3d.viewer.event` після `since` |
| `sections` | dict[str, str] | `payload["meta"]["sections"]` — провайдер **не** пише сюди (пише збирач) |

Порядок виклику й обробка помилок — R-01. Усі вбудовані провайдери нижче — спосіб (а): `_inherit = "f3d.viewer.provider"`
і `_name = "f3d.viewer.provider.<key>"`; спільна база для ORM-читання — `tools/payload.py`
(функції `read(env, model, domain, fields, order)` = `env[model].search_read(domain, fields, order=order)`
без `sudo`, `access_ok(env, model) -> bool` = `model in env and env[model].has_access("read")`).

#### M-01a `f3d.viewer.provider.stock` (20) — `products`, `locations`

Група `stock.group_stock_user`. Алгоритм (R-03):

1. `products`: `product.product` з `default_code != False`, `active_test=False` у контексті (як `LiveDemo.__init__`):
   поля `default_code`, `name`, `uom_id`, `categ_id`, `seller_ids` → `{default_code: {default_code, name,
   uom: uom_id.name, categ: categ_id.name, seller: seller_ids[0].partner_id.name або відсутній}}`.
   Включаються лише товари, що є в `stock.quant` непорожніх або в компонентах/виробах МО (щоб не роздувати
   розділ на проді: обмеження 5 000 товарів, далі — лише з залишками).
2. `locations`: `stock.location` з `f3d_code != False` і `usage in ('internal','transit')`, поля
   `f3d_code`, `complete_name`, `f3d_loc_kind` і `f3d_capacity` (base M-03, CB-05; X-14): `kind` = `f3d_loc_kind`
   (`stack|bin|shelf|pallet_cell|kit|area`), порожнє — запасне `static.layout.locations[code].kind`; `capacity` — R-04.
   Для кожного: `quants` = `stock.quant` з `location_id` у множині й `quantity != 0`:
   `{product: default_code, qty: round(quantity, 2), reserved: round(reserved_quantity, 2) якщо > 0,
   lot: lot_id.name, package: package_id.name}`; ключ `reserved_for` = назва відвантаження, якщо резерв
   походить з `stock.move.line` зі `state in ('assigned','partially_available')` і `picking_id.picking_type_code='outgoing'`
   (один запит `stock.move.line` по `location_id in ids`); `picking` = назва приймання для квантів у
   `UNLOAD-*` (рядки `stock.move.line` `state='done'` сьогодні з `location_dest_id` = ця локація);
   `quality` = `quality.check.name` зі `quality_state='fail'` і тим самим лотом (якщо модель є).
   Сортування квантів: `(product, package або "", lot або "")`.
3. `fill`, `state`, `orderpoint` — R-04.
4. Локації без квантів теж віддаються (порожні комірки малюють `fill=0`).

#### M-01b `f3d.viewer.provider.production` (30) — `workcenters`, `productions`, `workorders`

Група `mrp.group_mrp_user`. Алгоритм — R-06 (робочі центри, OEE, втрати), R-07 (МО і завдання, прогрес,
демо-годинник, `energy_kwh`; `energy_cost` — лише при `ctx["energy_cost"]`, X-25), R-08 (компоненти МО). Читає `mrp.workcenter` (`f3d_code`, `name`, `working_state`,
`capacity_ids`, `time_efficiency`, `note`; поля `default_capacity` в Odoo 19 немає — X-92), `mrp.production` (`name`, `state`, `reservation_state`,
`product_id`, `product_qty`, `product_uom_id`, `origin`, `date_start`, `date_deadline`, `bom_id.code`,
`workorder_ids`, `move_raw_ids`, `mrp_production_source_count`, `procurement_group_id`), `mrp.workorder`
(`id`, `name`, `production_id`, `workcenter_id`, `state`, `sequence`, `duration_expected`, `date_start`,
`date_finished`, `working_state`, `is_user_working`; планове завершення = `date_start + duration_expected`,
коли `date_finished` порожнє — Q-10), `mrp.workcenter.productivity` (`workcenter_id`, `workorder_id`,
`loss_id.name`, `loss_id.loss_type`, `date_start`, `date_end`, `duration`), `maintenance.request` відкриті
по `equipment_id.workcenter_id`.

#### M-01c `f3d.viewer.provider.logistics` (40) — `pickings`, `docks`, `sale_orders`, `purchase_orders`

Група `stock.group_stock_user`; `sale_orders` лише якщо `access_ok('sale.order')`, `purchase_orders`
— `access_ok('purchase.order')`. Алгоритм R-05 (док, фура, техніка, тип), R-09 (рядки, прогрес,
`source_locations`, `location_dest`, `note`).

#### M-01d `f3d.viewer.provider.quality` (45) — `quality_checks`

Лише якщо `access_ok('quality.check')`. `quality.check` з `quality_state` будь-який, `create_date` ≥
сьогодні − 7 днів або `quality_state='fail'`: `{name, title: point_id.title або test_type_id.name,
product: product_id.default_code, lot: lot_id.name, state: quality_state ('none'|'pass'|'fail'),
location: f3d_code локації `picking_id.location_dest_id` для приймань або `QC-1` для карантину
(квант з цим лотом у локації з `f3d_code='QC-1'`), picking: picking_id.name, production:
production_id.name, note: additional_note або note (HTML → текст, ≤ 300 символів)}`.

#### M-01e `f3d.viewer.provider.maintenance` (50) — `equipment`, `maintenance_requests`

Група `base.group_user`. `maintenance.equipment` з `f3d_code != False`: `{name, category:
category_id.name, serial: serial_no якщо ≠ f3d_code, manufacturer: f3d_manufacturer, model: f3d_model,
next_maintenance: next_action_date, maintenance_request: назва першої відкритої заявки
(`stage_id.done=False`), current_task: назва батча/переміщення, де `f3d_vehicle_id` = це обладнання
і `state in ('in_progress','draft')` (для навантажувачів)}`. Живі показники (`battery`, `hours`,
`pressure_bar`, …) кладе провайдер `signals` (M-01h) за шляхами `equipment/<code>/<field>`; без
сигналів цих ключів немає, і картка (R19) просто не показує рядки. Поля `state` (`busy|charging`),
`busy/total` (`CHARGING`), `boilers`, `last_inspection`, `leak_check` — зі статики `static.equipment`
(Додаток B), якщо є. `maintenance_requests`: усі заявки з `equipment_id.f3d_code != False` і
(`stage_id.done=False` або `close_date ≥ сьогодні − 7 днів`): `{id: name, name: name (тема),
equipment: f3d_code, maintenance_type, stage: stage_id.name, priority, request_date (date → "YYYY-MM-DD 00:00"),
schedule_date, technician: user_id.name}`; ключ `id` — це `name` заявки (`MR/00031`), як у файлі.

#### M-01f `f3d.viewer.provider.people` (60) — `employees`

Група `base.group_user`. Читання — модель `hr.employee.public` від користувача запиту **без** `sudo()` (X-09):
`f3d_code`, `f3d_alias`, `f3d_kind` — дзеркальні поля base M-10a; `name`, `job_title`, `job_id`, `department_id`,
`resource_calendar_id` — стандартні публічні поля. `hr.employee.public` з `f3d_code != False` і `active=True`: `{name, job: job_title
або job_id.name, department: department_id.name, workcenter: f3d_code робочого центру, якщо
співробітник — оператор поточного завдання (`mrp.workorder` зі `state='progress'` і
`employee_ids`/`employee_id` містить його; `id` працівника в `hr.employee.public` той самий, що в `hr.employee`) або
`f3d_code` = `OP-<wc>` (правило макета), shift: назва `resource_calendar_id`, current_workorder: `WO<id:05d>` цього
завдання}`. Відмітка `hr.attendance` сьогодні без `check_out` (лише якщо `access_ok('hr.attendance')`) → `present: true`
(необов'язковий ключ; з `factory3d_access` його перекриває провайдер `access` 170, CA-05). Модель `hr.employee` провайдер
не читає: для користувача без `hr.group_hr_user` Odoo 19 вимагає, щоб кожне поле було в `hr.employee.public`.

#### M-01g `f3d.viewer.provider.chains` (70) — `sheet_chain`, `ship_chain`, `material_paths`, `full_cycle_mo`, `productions[].supply/delivery/components[].path`, `zones` (живі поля), `docks`

Група `mrp.group_mrp_user` і `stock.group_stock_user` (обидві). Алгоритми R-10 (шлях плити),
R-11 (шляхи компонентів), R-12 (шлях до клієнта, фасади, `full_cycle_mo`), R-13 (ланцюжки й
`material_paths`, живі поля зон і воріт). Працює поверх результатів M-01a…M-01c: якщо якогось розділу
немає (denied/error), пропускає відповідні частини й пише `meta.sections.chains = "partial"`.
`zones` (X-29): **усі** активні `f3d.zone` base (`search_read` як користувач, `[('active','=',True)]`, порядок
`sequence, f3d_code`) — 45 на демо-базі: 34 зони цеху + 11 надвірних (base Додаток C.2); живі поля кожної зони — R-13
(`name`, `zone_type`, `polygon`, `is_roof`, `odoo_location`, `locations`, `workcenters`, `pickings`). Геометрія надвірних
зон береться лише з `f3d.zone.polygon` (у статиці `layout.zones` їх немає); `is_roof=true` — лише `Z-ROOF`.

#### M-01h `f3d.viewer.provider.signals` (90) — значення сигналів за шляхами

Група `group_f3d_user`. Якщо `"x_f3d_signal" in env` і доступ є: `search_read([('x_active','=',True),
('x_code','!=',False)], ['x_code','x_value','x_unit','x_mode','x_charging','x_updated','x_state'])`; далі
як `LiveDemo.sync_signals`: для кожного `x_code = a/b/c/leaf` знайти вузол `payload[a][b][c]`
(якщо шлях не існує — пропустити), `node[leaf] = round(v/100, 3)` якщо `x_unit == '%'`, інакше
`round(v, 2)` при `|v| < 20`, інакше `round(v, 1)`; якщо `x_mode == 'drain'` і в вузлі є `state`:
`state = 'charging' якщо x_charging інакше 'busy'`. `energy.totals.pv_kw = infra.totals.pv_now`,
`energy.totals.chp_kw = infra.totals.chp_kw`. `meta.iot = {source: "імітація датчиків (модуль
factory3d_iot_sim)", signals: n, alarms: кількість x_state == "тривога", updated: local(max x_updated)}`.
Якщо моделі немає — нічого (у фазі 2 `factory3d_telemetry` додає `f3d.viewer.provider.telemetry` з
sequence 95 і тим самим алгоритмом над `f3d.signal.code/last_value/unit/status/last_ts`).

### M-02 `f3d.viewer.snapshot` — знімок стану (C-06)

`_name = "f3d.viewer.snapshot"`, `_description = "3D: знімок стану заводу"`, `_order = "ts desc"`,
`_rec_name = "display_name"`.

| Поле | Тип | Параметри |
|---|---|---|
| `ts` | Datetime | string «Момент», required, index, default `fields.Datetime.now` |
| `shift_date` | Date | string «Дата зміни», required, index, compute з `ts` за Києвом, store |
| `kind` | Selection | string «Тип»; `[('periodic','Плановий'), ('event','Подія'), ('install','Установка'), ('manual','Вручну')]`, required, default `periodic`, index |
| `payload_file` | Binary | string «Дані (gzip JSON)», `attachment=True`, required |
| `payload_name` | Char | string «Файл», default `snapshot.json.gz` |
| `size_kb` | Integer | string «Розмір, КБ», readonly, compute з `len(payload_file)` при створенні, store |
| `schema` | Char | string «Версія схеми», default `"1.1"` (X-24), required; = `meta.schema` payload знімка; клієнт читає будь-яку `1.x` (R-19) |
| `note` | Char | string «Примітка» (для `event`: «Зупинка CNC-2 · MR/00031») |
| `event_count` | Integer | string «Подій з попереднього», readonly |
| `user_id` | Many2one `res.users` | string «Від імені», default `user_kiosk` для крону |
| `company_id` | Many2one `res.company` | string «Компанія», required, default `env.company`, index; record rule §4 |
| `display_name` | Char | compute: `"{ts за Києвом} · {kind label}"` |

SQL-constraint: `CHECK (size_kb >= 0)`. Методи:

- `_take(self, kind="periodic", note=None, user=None) -> record` — `PayloadBuilder(env.with_user(user або
  user_kiosk), full=True).build()` → `json.dumps(ensure_ascii=False, separators=(",",":"))` → `gzip
  level 6` → `create`. Перед серіалізацією в `payload.meta.events` кладуться події `f3d.viewer.event` з часу
  попереднього знімка (≤ 500 останніх, R-17), `event_count` = їх кількість. Якщо попередній знімок за < 60 с —
  повертає його (ідемпотентність крону).
- `_cron_snapshot(self)` — якщо зараз (Київ) у вікні `snapshot_hours` (формат `HH:MM-HH:MM`; порожньо —
  завжди) — `_take("periodic")`; інакше нічого. Крон — §6.
- `_cron_rotate(self)` — `unlink` знімків з `ts < now − snapshot_keep_days` (крім `kind='install'`),
  `f3d.viewer.event` з `ts < now − snapshot_keep_days`; лог «ротація: знімків N, подій M».
- `action_open_viewer(self)` — повертає `action_f3d_viewer` з `params={"snapshot": id}`.
- `read_payload(self) -> dict` — розпаковує; доступ — `group_f3d_user` (права §4).

### M-03 `f3d.viewer.event` — подія шини (C-03, C-06)

`_name = "f3d.viewer.event"`, `_description = "3D: подія зміни стану"`, `_order = "ts desc, id desc"`,
`_log_access = False`.

| Поле | Тип | Параметри |
|---|---|---|
| `ts` | Datetime | required, index, default now |
| `model` | Char | string «Модель», required, index, size 64 |
| `codes` | Json | string «Коди», required — список рядків (коди сцени або назви документів), ≤ 500 елементів |
| `kind` | Selection | `[('state','Стан'), ('stock','Залишки'), ('doc','Документ'), ('signal','Сигнал'), ('maintenance','ТО')]`, required, index |
| `user_id` | Many2one `res.users` | хто спричинив (`env.uid`), ondelete `set null` |
| `n` | Integer | кількість кодів, compute store |

Індекс SQL: `(ts, model)`. Методи:

- `_notify(self, model: str, codes: Iterable[str], kind: str) -> None` (класовий вхід C-03):
  1. подія `f3d.viewer.event` пишеться завжди; повідомлення в шину — лише якщо `bus_enabled=True`;
  2. `codes = {c for c in codes if c}`; якщо порожньо — вихід;
  3. `data = self.env.cr.precommit.data.setdefault("f3d_viewer.notify", {})`;
     `data.setdefault((model, kind), set()).update(codes)`; при першому виклику в транзакції —
     `self.env.cr.precommit.add(partial(self._flush_notify, self.env))` (один обробник на транзакцію);
  4. `_flush_notify(env)`: для кожного `(model, kind), codes` — `create({ts, model, codes: sorted(codes)[:500],
     kind, user_id})`; якщо `bus_enabled` — `env["bus.bus"]._sendone("f3d_viewer", "f3d_viewer",
     {"model": model, "codes": sorted(codes)[:500], "kind": kind, "ts": ts_iso_utc})`; очистити `data`.
- `_since(self, since: datetime, limit=2000) -> dict[str, set[str]] | None` — події з `ts > since`;
  якщо `since < now − event_keep_hours` або рядків > `limit` → `None` (означає «повний»); інакше
  `{model: set(codes)}`.
- `_cron_signal_bus(self)` — якщо `"x_f3d_signal" in env`: `search_read([('x_active','=',True),
  ('x_updated','>', останній_ts_параметр `factory3d.viewer.signal_bus_ts`)], ['x_code'])` →
  `_notify("x_f3d_signal", [x_code...], "signal")`, оновити параметр. Крон щохвилини.

### M-04 `f3d.demo.wizard` — майстер демо-даних (FR-34, FR-35)

`_name = "f3d.demo.wizard"`, `TransientModel`, `_description = "3D: заливка демо-даних"`.

| Поле | Тип | Параметри |
|---|---|---|
| `step_ids` | One2many `f3d.demo.wizard.step` (inverse `wizard_id`) | кроки |
| `state` | Selection | `[('draft','Готово до запуску'), ('queued','У черзі'), ('running','Виконується'), ('done','Виконано'), ('error','Помилка')]`, default `draft`, readonly |
| `enabled` | Boolean | compute: параметр `demo_enabled` |
| `progress` | Integer | 0…100, readonly |
| `current_step` | Char | readonly |
| `log` | Text | readonly, останні 500 рядків |
| `demo_clock` | Char | default з параметра `demo_clock` або `"2026-10-12 10:30"`, help «Демо-годинник: дата й час, до яких прив'язані документи» |
| `cron_id` | Many2one `ir.cron` | readonly, крон «3D: заливка демо» |
| `new_records` | Integer | readonly, лічильник `Push.n_new` |

`f3d.demo.wizard.step` (TransientModel): `wizard_id`, `name` (Char, ключ кроку з `STEPS`),
`label` (Char, українська назва з таблиці нижче), `sequence` (Integer), `selected` (Boolean, default True),
`state` (`todo|running|done|skipped|error`), `duration_s` (Float), `message` (Char).

Кроки (`demo_steps.STEPS`, порядок і ключі = `plant/odoo_push.py:STEPS`):

| # | Ключ | Назва в майстрі | Що робить (порт з `odoo_push.py` / `odoo_flows.py`) | Ідемпотентність |
|---|---|---|---|---|
| 1 | `modules` | Модулі | `ir.module.module.button_immediate_install` для `iot`, `hr_attendance`, `stock_delivery`, `stock_picking_batch`, `stock_fleet` (пропуск, якщо встановлені) | стан модуля |
| 2 | `settings` | Налаштування складу/виробництва | `res.config.settings` з `SETTINGS` (6 груп) + `execute()` | повторне виконання не змінює |
| 3 | `base` | Компанія, валюта, товари, партнери, одиниці | `Push.step_base` | `ensure(xid)` через `ir.model.data` модуль `factory3d` |
| 4 | `views` | Поля ворота/фура на формі переміщення | `FlowSteps.step_views` — **пропускається** в модулі (поля `x_*` у проді заборонені; батчі — крок `docks`) | завжди `skipped` з повідомленням |
| 5 | `calendar` | Графік «Зміна 1 (07:00–15:30)» | `step_calendar` | ensure |
| 6 | `locations` | 689 місць зі штрихкодом = код сцени | `step_locations` | ensure за xid `loc_<code>` |
| 7 | `workcenters` | 35 робочих центрів | `step_workcenters` | ensure |
| 8 | `people` | 35 співробітників | `step_people` | ensure |
| 9 | `purchase` | 13 закупівель і приймання | `step_purchase` | ensure |
| 10 | `sale` | 8 замовлень клієнтів і відвантаження | `step_sale` | ensure |
| 11 | `internal` | Внутрішні переміщення (INT, PC, SFP) | `step_internal` | ensure |
| 12 | `production` | 32 МО | `step_production` | ensure |
| 13 | `boms` | 27 специфікацій, 171 операція | `step_boms` | ensure |
| 14 | `layout` | Групи локацій, маршрути складу | `step_layout` | ensure |
| 15 | `lots` | 131 партія | `step_lots` | ensure |
| 16 | `stock` | Залишки (інвентаризація за квантами) | `step_stock` | квант = ціль, повтор нічого не змінює |
| 17 | `routes` | Маршрути 2/3 кроки | `step_routes` | ensure |
| 18 | `orderpoints` | 167 правил поповнення | `step_orderpoints` | ensure |
| 19 | `children` | Дочірні МО фасадів | `step_children` | ensure |
| 20 | `fronts` | Етажерки фасадів | `step_fronts` | ensure |
| 21 | `mo_locations` | Місця компонентів МО | `step_mo_locations` | ensure |
| 22 | `consumption` | Спожиті компоненти виконаних операцій | `step_consumption` | за станом move |
| 23 | `po_links` | Рядки закупівель ↔ правила | `step_po_links` | ensure |
| 24 | `docks` | 14 воріт і 6 батчів із доком і фурою | `step_docks`, плюс (A-08 доповнення) батч на **кожне** переміщення з доком; `f3d_code` = код фури в 3D (`TRUCK-IN-1`), `f3d_truck` = опис/назва фури з макета (base CB-06, X-15) | ensure `batch_<name>` |
| 25 | `wc_tags` | Дільниці робочих центрів | `step_wc_tags` | ensure |
| 26 | `losses` | 73 простої за зміну | `step_losses` | ensure |
| 27 | `quality` | Точки й перевірки контролю | `step_quality` | ensure |
| 28 | `maintenance` | Команда, 6 заявок | `step_maintenance` | ensure |
| 29 | `equipment` | 210 одиниць обладнання з паспортами | `step_equipment` (поля `f3d_*` з C-09, а не `note`) | ensure |
| 30 | `preventive` | Планове ТО | `step_preventive` | ensure |
| 31 | `iot_module` | Імпорт data-модуля імітації IoT | `base.import.module` з zip `odoo_addons/factory3d_iot_sim` — у майстрі **пропускається**, якщо модуль уже встановлено; інакше повідомлення «встановіть `factory3d_iot_sim` з Застосунків» (`skipped`) | стан модуля |
| 32 | `signals` | 196 сигналів імітації | `step_signals` (лише якщо `x_f3d_signal` є) | ensure `sig_<code>` |
| 33 | `attendance` | Відмітки 35 людей | `step_attendance` | ensure |
| 34 | `carriers` | Перевізники | `step_carriers` | ensure |
| 35 | `finish` | Резерви, зупинка CNC-2, зсув нумерації | `Push.step_finish` | резерв повторно — без змін; `number_next` ставиться лише якщо менший |

Методи:

- `default_get` — створює 35 рядків `step_ids` (усі `selected`), `enabled` з параметра.
- `action_run(self)` — якщо `not enabled` → `UserError("Заливка демо вимкнена на цій базі
  (factory3d.viewer.demo_enabled). Увімкніть у Завод 3D → Налаштування → Налаштування переглядача лише на тестовому сервері.")`;
  якщо крон уже `active` з `state='running'` → `UserError("Заливка вже виконується")`; записує
  `demo_clock` у параметр; `state='queued'`, зберігає обрані кроки в параметр
  `factory3d.viewer.demo_queue` (JSON: `{wizard_id, steps:[...]}`), вмикає крон «3D: заливка демо»
  з `nextcall=now`; повертає `{"type":"ir.actions.act_window", "res_model": self._name, "res_id": self.id, "view_mode":"form", "target":"new"}`.
- `_cron_run(self)` (викликає крон): читає чергу, `state='running'`; для кожного кроку —
  `demo_steps.Runner(env, payload=static_data.demo_payload(), log=cb).run(step)` у `savepoint`;
  після кожного кроку `commit` (крон-транзакція; `self.env.cr.commit()` дозволено в кроні), оновлює
  `progress = k/n*100`, `current_step`, лог; виняток → `state='error'`, крок `error`, повідомлення =
  клас + текст без traceback; у кінці `state='done'`, вимкнути крон, очистити чергу, записати в лог
  `cycle_check` результат (M-05) по payload користувача кіоска.
- `action_refresh(self)` — перечитати `state/progress/log` з параметрів (майстер transient; стан
  зберігається в `factory3d.viewer.demo_state` JSON) і повернути ту саму форму.
- `action_select_all/none`.

`wizard/orm_proxy.py` — клас `OrmProxy(env)` з `__call__(self, model, method, *args, **kw)`:
`search_read/search/search_count/read/fields_get/name_search/create/write/unlink` → відповідні методи
`env[model].with_context(ctx)`; будь-який інший `method` → `env[model].browse(args[0]).method(*args[1:],
**kw)` (кнопки `action_confirm`, `button_mark_done`, `action_assign`, `button_immediate_install`…);
`kw["context"]` зливається з `ctx` (`lang=uk_UA`, `tz=Europe/Kyiv`, `tracking_disable=True`,
`mail_create_nolog=True`, `mail_notrack=True`); `has(model)`, `installed(*names)`, `install(*names)`
як у `plant/odoo_rpc.Odoo`; `version` = `{"server_serie": "19.0"}`; `uid` = `env.uid`.
`demo_steps.py` — файл `odoo_push.py` + `odoo_flows.py` з мінімальними правками: `from .orm_proxy import
key, utc` (функції `key`, `utc` перенесені), без `argparse/main`, крок `views` → `skipped`, крок
`iot_module` → перевірка встановлення, крок `docks` — батч на кожне переміщення з доком, крок
`equipment` пише `f3d_role/f3d_manufacturer/f3d_model/f3d_power_kw/f3d_connected_kw/f3d_dimensions` і
`f3d_spec_ids` (C-09) замість злиття в `note`. Тест порівняння з оригіналом — §13.1 `test_demo_steps_diff`
(diff ≤ 80 рядків).

### M-05 `f3d.viewer.cycle.check` — перевірка циклу (FR-36)

`_name = "f3d.viewer.cycle.check"`, `TransientModel`. Поля: `result_html` (Html, readonly), `issue_count`
(Integer, readonly), `state` (`[('draft','—'),('ok','Цикл замкнений'),('issues','Є проблеми')]`),
`payload_user_id` (Many2one `res.users`, default поточний; для адміністратора можна обрати `user_kiosk`),
`ran_at` (Datetime). Метод `action_run(self)`: `payload = PayloadBuilder(env.with_user(payload_user_id),
full=True).build()`; `issues = tools.cycle_check.check(payload)`; `result_html` = список `<li>` з
посиланнями: рядок виду `"{name}: …"` де `name` збігається з `pickings[].name` / `productions[].name` /
`quality_checks[].name` → `<a href="#" data-f3d-open="{name}">`, інакше код об'єкта → `data-f3d-code`;
кнопка «Показати в 3D» відкриває переглядач із першим проблемним об'єктом. Повертає ту саму форму.

### M-06 `res.config.settings` — розширення

Поля (`config_parameter=…`): `f3d_snapshot_minutes` (Integer, `factory3d.viewer.snapshot_minutes`),
`f3d_snapshot_hours` (Char), `f3d_snapshot_keep_days` (Integer), `f3d_event_keep_hours` (Integer),
`f3d_delta_debounce_ms` (Integer), `f3d_kiosk_enabled` (Boolean), `f3d_kiosk_refresh_s` (Integer),
`f3d_bus_enabled` (Boolean), `f3d_demo_enabled` (Boolean), `f3d_demo_clock` (Char), `f3d_lite_default`
(Selection `0|1|auto`), `f3d_kiosk_url` (Char, compute, readonly: `{base_url}/f3d/kiosk/{token}` —
лише для `group_f3d_admin`, інакше порожньо). Метод `action_f3d_new_kiosk_token(self)` — `group_f3d_admin`:
`set_param("factory3d.viewer.kiosk_token", secrets.token_hex(16))`, повертає перезавантаження форми.
`set_values` валідує: `snapshot_minutes` 5…60, `kiosk_refresh_s` 5…120, `snapshot_hours` відповідає
`^\d\d:\d\d-\d\d:\d\d$` або порожній, `demo_clock` — `^\d{4}-\d\d-\d\d \d\d:\d\d$` або порожній; інакше
`ValidationError` з текстом «Невірне значення <поле>: очікується …».

### M-07 Емітери шини — перевизначення стандартних моделей (FR-18)

Файл `models/bus_emitters.py`. Для кожної моделі `_inherit` з перевизначенням `create` (після `super`),
`write` (після `super`), `unlink` (до `super`): обчислити коди й викликати
`self.env["f3d.viewer.event"]._notify(model, codes, kind)`. Поля-тригери (зміна інших полів не
публікується): 

| Модель | Поля-тригери (`write`) | Коди | `kind` |
|---|---|---|---|
| `stock.quant` | `quantity`, `reserved_quantity`, `lot_id`, `package_id`, `location_id` | `location_id.f3d_code` (+ старе місце при зміні) | `stock` |
| `stock.move.line` | `quantity`, `picked`, `state`, `location_id`, `location_dest_id` | `location_id.f3d_code`, `location_dest_id.f3d_code`, `picking_id.name` | `stock` |
| `stock.picking` | `state`, `scheduled_date`, `date_done`, `batch_id`, `partner_id` | `name`, `batch_id.dock_id.f3d_code` | `doc` |
| `stock.picking.batch` | `state`, `dock_id`, `f3d_code`, `f3d_vehicle_id`, `picking_ids`, `scheduled_date` | `picking_ids.name`, `dock_id.f3d_code`, `f3d_code` (код фури, X-15), `f3d_vehicle_id.f3d_code` | `doc` |
| `mrp.workorder` | `state`, `date_start`, `date_finished`, `working_state`, `workcenter_id`, `duration` | `WO<id:05d>`, `production_id.name`, `workcenter_id.f3d_code` | `state` |
| `mrp.production` | `state`, `reservation_state`, `product_qty`, `date_start`, `date_deadline`, `move_raw_ids` | `name` | `doc` |
| `mrp.workcenter` | `working_state`, `active` | `f3d_code` | `state` |
| `mrp.workcenter.productivity` | `date_start`, `date_end`, `loss_id`, `workcenter_id` | `workcenter_id.f3d_code`, `workorder_id` → `WO…` | `state` |
| `maintenance.request` | `stage_id`, `equipment_id`, `schedule_date`, `user_id`, `priority` | `name`, `equipment_id.f3d_code`, `equipment_id.workcenter_id.f3d_code` | `maintenance` |

`create` публікує завжди (ті самі коди), `unlink` — коди до видалення. Якщо `f3d_code` порожній у всіх
пов'язаних записах — не публікувати. Реалізація через спільний міксин `f3d.viewer.bus.mixin`
(AbstractModel у тому ж файлі) з атрибутами `_f3d_bus_fields: tuple`, `_f3d_bus_kind: str` і методом
`_f3d_bus_codes(self) -> set[str]`, який кожна модель перевизначає.

### M-08 `action_f3d_show()` для документів (FR-22, A-11)

- `mrp.production.action_f3d_show(self)` → `{"type": "ir.actions.client", "tag": "f3d_viewer.action",
  "name": "3D: " + name, "params": {"mo": self.name, "tab": "production"}}`; для кількох записів —
  перший.
- `stock.picking.action_f3d_show(self)` → `params: {"picking": name, "tab": "logistics"}`.
- `sale.order.action_f3d_show(self)` → якщо є МО (`mrp.production` з `origin = name` або через
  `procurement_group_id`) → `params: {"mo": перше МО за `date_start`, "so": name}`; інакше якщо є
  відвантаження (`picking_ids` зі `state != 'cancel'`) → `params: {"picking": name, "so": name}`;
  інакше `UserError("Для замовлення ще немає виробничих замовлень чи відвантажень")`. Оскільки
  `sale` не входить у `depends` (A-04), а `_inherit = "sale.order"` без залежності неможливий, метод
  і кнопка живуть у міст-модулі `factory3d_viewer_sale` (A-17): `odoo_addons/factory3d_viewer_sale/`
  з `__manifest__.py` (`depends: ["factory3d_viewer", "sale"]`, `auto_install: True`,
  `version 19.0.1.0.0`, `author ToDo`, `license LGPL-3`), `models/sale_order.py`,
  `views/sale_order_views.xml` (V-09), `tests/test_sale_show.py`. Для `purchase` міст не потрібен
  (кнопки на закупівлі немає).
- Поле `f3d_has_3d` (Boolean, compute, не store) на `mrp.production`, `stock.picking` (цей модуль)
  і `sale.order` (міст-модуль):
  чи є що показати (`True`, якщо є хоч одне робоче завдання з `workcenter_id.f3d_code` / є
  `batch_id.dock_id.f3d_code` або рядок з локацією з `f3d_code` / є МО чи відвантаження) — для
  `invisible` кнопки.

### M-09 «Показати в 3D» на моделях домішки — дія і кнопки `factory3d_base` (CB-02, X-08)

Viewer нічого не додає до моделей і форм носіїв домішки (`stock.location`, `mrp.workcenter`, `maintenance.equipment`,
`hr.employee`, `f3d.zone`, `stock.picking.batch`). Діє `factory3d_base` CB-02 / M-01 `action_f3d_show()`: якщо модуль
`factory3d_viewer` встановлений — `{"type": "ir.actions.client", "tag": "f3d_viewer.action", "name": "Завод 3D",
"target": "current", "params": {"code": f3d_code, "alias": f3d_alias або False, "model": _name, "res_id": id,
"kind": f3d_kind}}`; інакше `ir.actions.client` `display_notification` «Модуль 3D-переглядача не встановлено». Кнопки —
у формах base (V-01 `f3d.zone`, V-05 `stock.location`, V-08 `stock.picking.batch` на `stock_fleet.stock_picking_batch_form`,
V-11 `mrp.workcenter`, V-12 `maintenance.equipment`, V-14 `hr.employee`; видимість — `f3d_viewer_available`). Viewer
читає `params.code` (§8.1 `applyParams`); `alias`, `model`, `res_id`, `kind` — довідкові, клієнт їх не використовує.
Власні кнопки viewer — лише для документів (M-08: V-08a `mrp.production`, V-08b `stock.picking`, V-09 `sale.order` у
містку `factory3d_viewer_sale`).

### M-10 Технічний користувач і група кіоска (дані, не модель)

`security/security.xml`: власний привілей `res.groups.privilege` `privilege_f3d_viewer` «Завод 3D: переглядач»
(категорія `factory3d_base.module_category_factory3d`, sequence 10 = резерв viewer CB-09; X-19) і `res.groups`
`group_f3d_kiosk` «Завод 3D: кіоск» (`privilege_id` = `privilege_f3d_viewer`, sequence 10), `implied_ids`:
`base.group_user`, `factory3d_base.group_f3d_user`, `stock.group_stock_user`, `mrp.group_mrp_user` (§4.3).
`security/kiosk_user.xml` (`noupdate=1`):
`res.users` `user_kiosk`: `login="f3d_kiosk"`, `name="Екран цеху (3D)"`, `group_ids=[group_f3d_kiosk]`,
`password` не задається, `notification_type="inbox"`, `action_id` — `action_f3d_viewer`, `active=True`,
`share=False`. Користувач не може входити інтерактивно (немає пароля; `test_kiosk_user_cannot_login`).

## 3. Представлення й меню

### V-01 Меню (`views/menus.xml`)

| XML-id | Назва | Батько | sequence | Дія | Групи |
|---|---|---|---|---|---|
| `menu_f3d_viewer` | Переглядач | `factory3d_base.menu_f3d_root` | 10 | `action_f3d_viewer` (client) | `factory3d_base.group_f3d_user` |
| `menu_f3d_journal` | Журнал станів | `factory3d_base.menu_f3d_root` | 12 | — (контейнер) | `factory3d_base.group_f3d_manager` |
| `menu_f3d_snapshots` | Знімки | `menu_f3d_journal` | 1 | `action_f3d_viewer_snapshot` (list, form) | `group_f3d_manager` |
| `menu_f3d_events` | Події | `menu_f3d_journal` | 2 | `action_f3d_viewer_event` (list) | `group_f3d_manager` |
| `menu_f3d_cycle_check` | Перевірка циклу | `factory3d_base.menu_f3d_root` | 14 | `action_f3d_cycle_check` (form wizard, target new) | `group_f3d_manager` |
| `menu_f3d_demo` | Демо-дані | `factory3d_base.menu_f3d_root` | 16 | `action_f3d_demo_wizard` (form wizard, target new) | `factory3d_base.group_f3d_admin` |
| `menu_f3d_settings` | Налаштування переглядача | `factory3d_base.menu_f3d_config` | 10 | `action_f3d_config_settings` (`res.config.settings`, context `{"module": "factory3d_viewer"}`) | `group_f3d_admin` |

Sequence (X-30, base CB-09): пункти viewer у корені `factory3d_base.menu_f3d_root` займають лише діапазон 10–19
(резерв viewer; 20 — `menu_f3d_plant` base); пункт налаштувань — під `factory3d_base.menu_f3d_config` з sequence 10
(= резерв viewer, правило X-32), а не другим пунктом «Налаштування» в корені.

`data/actions.xml`: `action_f3d_viewer` — `ir.actions.client`, `name="Завод 3D"`, `tag="f3d_viewer.action"`,
`target="current"`, `params` порожні (параметри підставляє `action_f3d_show`).

### V-08a, V-08b, V-09 Кнопка «Показати в 3D» на документах (`views/show_in_3d_views.xml`; V-09 — міст `factory3d_viewer_sale`)

V-02…V-07 — **вилучено (X-08)**: кнопки на формах носіїв домішки (`stock.location`, `mrp.workcenter`,
`maintenance.equipment`, `hr.employee`, `f3d.zone`, `stock.picking.batch`) дає `factory3d_base` (CB-02; base V-01, V-05,
V-08, V-11, V-12, V-14) — viewer другої кнопки в ті самі форми не додає (M-09). Viewer додає кнопку лише в шапку форм
документів, однакову в усіх трьох:

```xml
<button name="action_f3d_show" type="object" string="Показати в 3D" icon="fa-cube"
        class="btn-secondary" groups="factory3d_base.group_f3d_user" invisible="not f3d_has_3d"/>
```

(поле `f3d_has_3d` (M-08) додається у форму невидимим).

| ID | Модель | Успадкована форма (xml-id) | Куди вставити |
|---|---|---|---|
| V-02…V-07 | — | — | вилучено (X-08): кнопки носіїв домішки — у `factory3d_base` (CB-02) |
| V-08a | `mrp.production` | `mrp.mrp_production_form_view` | `//header` position `inside`, після `button_mark_done` |
| V-08b | `stock.picking` | `stock.view_picking_form` | `//header` position `inside`, після `button_validate` |
| V-09 | `sale.order` (міст-модуль) | `sale.view_order_form` | `//header` position `inside`, після `action_confirm` |

Гарячих клавіш (`data-hotkey`) кнопці не призначаємо — конфлікт зі стандартними. Для турів кнопка має
`name="action_f3d_show"` — селектор `button[name='action_f3d_show']`.

### V-10 Майстер демо (`wizard/demo_wizard_views.xml`)

`view_f3d_demo_wizard_form`, модель `f3d.demo.wizard`, form:
- шапка: `state` statusbar (`draft,queued,running,done,error`); кнопки «Запустити» (`action_run`,
  `invisible="state in ('queued','running') or not enabled"`, `class="btn-primary"`), «Оновити»
  (`action_refresh`), «Усі кроки»/«Жодного» (`action_select_all`/`action_select_none`, `invisible="state != 'draft'"`);
- `alert` (`role="alert"`, клас `alert-danger`, `invisible="enabled"`): «Заливка демо вимкнена на цій
  базі. Увімкніть «Заливка демо дозволена» у Завод 3D → Налаштування → Налаштування переглядача лише на тестовому сервері.»;
- група: `demo_clock`, `progress` (widget `progressbar`), `current_step`, `new_records`;
- `step_ids` list editable bottom: `sequence` (handle), `selected` (boolean_toggle), `label`, `name`
  (readonly), `state` (badge: `todo` сірий, `running` синій, `done` зелений, `skipped` жовтий, `error`
  червоний — `decoration-*`), `duration_s`, `message`;
- вкладка «Лог»: `log` (readonly, `widget="text"`).
`action_f3d_demo_wizard`: `ir.actions.act_window`, `view_mode="form"`, `target="new"`.

### V-11 Перевірка циклу (`wizard/cycle_check_views.xml`)

`view_f3d_cycle_check_form`: кнопки «Запустити» (`action_run`), «Показати в 3D» (`action_show_first`,
`invisible="state != 'issues'"`), «Закрити»; поля `payload_user_id` (`groups="factory3d_base.group_f3d_admin"`),
`ran_at`, `issue_count`, `state` (widget `badge`: `ok` зелений, `issues` червоний), `result_html` (widget `html`,
readonly). `action_f3d_cycle_check`: form, `target="new"`.

### V-12 Знімки — список (`views/viewer_snapshot_views.xml`)

`view_f3d_viewer_snapshot_list`: `ts` (widget `datetime`), `shift_date`, `kind` (badge), `size_kb`,
`event_count`, `note`, `user_id`; кнопка в рядку «Відкрити в переглядачі» (`action_open_viewer`, icon
`fa-cube`); `default_order="ts desc"`; search: фільтри «Сьогодні», «Цей тиждень», групування за `shift_date`,
`kind`. `action_f3d_viewer_snapshot`: list, form; context `{"search_default_today": 1}`.

### V-13 Знімок — форма

`view_f3d_viewer_snapshot_form`: шапка з «Відкрити в переглядачі»; поля readonly: `ts`, `shift_date`,
`kind`, `size_kb`, `schema`, `note`, `event_count`, `user_id`, `company_id`, `payload_file`
(widget `binary`, `filename="payload_name"` — завантажити gzip).

### V-14 Події — список (`views/viewer_event_views.xml`)

`view_f3d_viewer_event_list`: `ts`, `model`, `kind` (badge), `n`, `codes` (widget `json`? у 19 — показувати
як текст через `field widget="char"` compute `codes_text`), `user_id`; readonly (`create="0" edit="0"`),
пошук по `model`, `kind`, діапазону `ts`. Поле `codes_text` (Char, compute, не store: `", ".join(codes)[:200]`)
додається в M-03.

### V-15 Налаштування (`views/res_config_settings_views.xml`)

Успадкування `base.res_config_settings_view_form`, блок `app` з `data-string="Завод 3D"`,
`name="factory3d_viewer"`, `groups="factory3d_base.group_f3d_admin"`; секції:
«Журнал станів» (`f3d_snapshot_minutes`, `f3d_snapshot_hours`, `f3d_snapshot_keep_days`,
`f3d_event_keep_hours`), «Живі оновлення» (`f3d_bus_enabled`, `f3d_delta_debounce_ms`),
«Кіоск» (`f3d_kiosk_enabled`, `f3d_kiosk_refresh_s`, `f3d_kiosk_url` readonly з кнопкою «Копіювати»
(widget `CopyClipboardChar`), кнопка «Новий токен кіоска» `action_f3d_new_kiosk_token` з `confirm="Старі
адреси кіосків перестануть працювати. Продовжити?"`), «Планшети» (`f3d_lite_default`), «Демо» (`f3d_demo_enabled`,
`f3d_demo_clock`, попередження «Лише для тестового сервера»).

## 4. Права

### 4.1 `security/ir.model.access.csv` (повністю)

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_f3d_viewer_snapshot_user,f3d.viewer.snapshot user,model_f3d_viewer_snapshot,factory3d_base.group_f3d_user,1,0,0,0
access_f3d_viewer_snapshot_kiosk,f3d.viewer.snapshot kiosk,model_f3d_viewer_snapshot,factory3d_viewer.group_f3d_kiosk,1,0,1,0
access_f3d_viewer_snapshot_manager,f3d.viewer.snapshot manager,model_f3d_viewer_snapshot,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_viewer_event_user,f3d.viewer.event user,model_f3d_viewer_event,base.group_user,1,0,1,0
access_f3d_viewer_event_manager,f3d.viewer.event manager,model_f3d_viewer_event,factory3d_base.group_f3d_manager,1,1,1,1
access_f3d_demo_wizard_admin,f3d.demo.wizard admin,model_f3d_demo_wizard,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_demo_wizard_step_admin,f3d.demo.wizard.step admin,model_f3d_demo_wizard_step,factory3d_base.group_f3d_admin,1,1,1,1
access_f3d_viewer_cycle_check_manager,f3d.viewer.cycle.check manager,model_f3d_viewer_cycle_check,factory3d_base.group_f3d_manager,1,1,1,1
```

Абстрактні моделі (`f3d.viewer.provider*`, `f3d.viewer.bus.mixin`) доступів не потребують. Запис подій
(`perm_create` для `base.group_user`) потрібен, бо подію створює транзакція будь-якого користувача, який
змінив документ; `_notify` викликається з `write` стандартних моделей без `sudo`.

### 4.2 Record rules (`security/security.xml`)

| XML-id | Модель | Домен | Групи |
|---|---|---|---|
| `rule_f3d_viewer_snapshot_company` | `f3d.viewer.snapshot` | `[('company_id', 'in', company_ids)]` | усі (global) |
| `rule_f3d_viewer_event_read_all` | `f3d.viewer.event` | `[(1, '=', 1)]` | `base.group_user` (події не містять даних, лише коди) |

### 4.3 Групи модуля

```xml
<record id="privilege_f3d_viewer" model="res.groups.privilege">
    <field name="name">Завод 3D: переглядач</field>
    <field name="category_id" ref="factory3d_base.module_category_factory3d"/>
    <field name="sequence">10</field>
</record>
<record id="group_f3d_kiosk" model="res.groups">
    <field name="name">Завод 3D: кіоск</field><field name="privilege_id" ref="privilege_f3d_viewer"/><field name="sequence">10</field>
    <field name="implied_ids" eval="[Command.link(ref('base.group_user')), Command.link(ref('factory3d_base.group_f3d_user')),
                                     Command.link(ref('stock.group_stock_user')), Command.link(ref('mrp.group_mrp_user'))]"/>
</record>
```

| XML-id | Назва | Привілей | implied_ids | Призначення |
|---|---|---|---|---|
| `factory3d_viewer.group_f3d_kiosk` | Завод 3D: кіоск | `factory3d_viewer.privilege_f3d_viewer` (категорія `factory3d_base.module_category_factory3d`, sequence 10; X-19 — власний привілей модуля, не категорія `base.module_category_manufacturing_manufacturing` і не привілей base `privilege_f3d`) | `base.group_user`, `factory3d_base.group_f3d_user`, `stock.group_stock_user`, `mrp.group_mrp_user` | технічний користувач екранів; **не** входить у `sales_team.*`, `purchase.*`, `hr.group_hr_user`, `factory3d_energy.group_f3d_energy_cost`; драбину base `group_f3d_user ⊂ manager ⊂ admin` (CB-10) не змінює |

### 4.4 Розділи payload за групами (перевіряє `tools/payload.access_ok` і `_f3d_group`)

| Розділ(и) | Модель ORM | Умова включення (користувач запиту) | Якщо ні |
|---|---|---|---|
| `meta`, `zones` (статика), `docks` (статика), `energy`, `lighting`, `ventilation`, `fire`, `infra`, `evacuation`, `passports`, `layout`, `path_templates` | файл | `group_f3d_user` | `/static` → 403 |
| `products`, `locations` | `product.product`, `stock.location`, `stock.quant`, `stock.move.line` | `has_access('read')` на всіх чотирьох (фактично `stock.group_stock_user`) | `{}` + `sections.locations="denied"` |
| `workcenters`, `productions`, `workorders` | `mrp.workcenter`, `mrp.production`, `mrp.workorder`, `mrp.workcenter.productivity` | `mrp.group_mrp_user` | `{}`/`[]` + `denied` |
| `pickings`, `docks` (живі) | `stock.picking`, `stock.picking.batch`, `stock.move` | `stock.group_stock_user` | `[]` + `denied` |
| `sale_orders` | `sale.order` | модель є і `has_access` (`sales_team.group_sale_salesman`); ключ `amount` — лише `sales_team.group_sale_salesman_all_leads` і не кіоск | `[]` + `denied`/`missing` |
| `purchase_orders` | `purchase.order` | модель є і `purchase.group_purchase_user` | `[]` |
| `quality_checks` | `quality.check` | модель є і `has_access` | `[]` |
| `equipment`, `maintenance_requests` | `maintenance.equipment`, `maintenance.request` | `base.group_user` (стандартні права maintenance: читання всім внутрішнім) | `denied` |
| `employees` | `hr.employee.public` (без `sudo`; `f3d_code`, `f3d_alias`, `f3d_kind` — дзеркало base M-10a, X-09) | `base.group_user` — лише публічні поля (M-01f) | `denied` |
| `sheet_chain`, `ship_chain`, `material_paths`, `full_cycle_mo`, `productions[].supply/delivery/components[].path` | обчислення | обидві групи `mrp` і `stock` | `chains="partial"`: ланцюжки порожні, у МО — без `supply`/`delivery` |
| значення сигналів, `meta.iot` | `x_f3d_signal` / `f3d.signal` | модель є і `has_access` | значення зі статики |

`productions[].energy_kwh/energy_cost` — обчислення зі статичних паспортів (`static.energy.consumers[].p_inst`,
`PROFILE`). `energy_kwh` віддається всім, хто бачить `productions`. `energy_cost` (вартість) — **лише** якщо
`ctx.energy_cost` (M-01): група `factory3d_energy.group_f3d_energy_cost` існує в базі (`env.ref(…, raise_if_not_found=False)`),
користувач у ній і запит не з кіоска; інакше ключа немає — статичну вартість viewer без групи вартості energy не віддає
(X-25). Без `factory3d_energy` групи немає → `energy_cost` не віддається нікому; з energy провайдер `energy` (100)
перераховує обидва ключі й сам видаляє `energy_cost` без групи (energy R-16).

## 5. Дані

### 5.1 `data/params.xml` (`noupdate="1"`)

| Ключ | Значення при встановленні | Хто змінює |
|---|---|---|
| `factory3d.viewer.snapshot_minutes` | `10` | налаштування |
| `factory3d.viewer.snapshot_hours` | `06:30-16:00` | налаштування |
| `factory3d.viewer.snapshot_keep_days` | `14` | налаштування |
| `factory3d.viewer.event_keep_hours` | `48` | налаштування |
| `factory3d.viewer.delta_debounce_ms` | `1500` | налаштування |
| `factory3d.viewer.kiosk_enabled` | `True` | налаштування, `neutralize.sql` |
| `factory3d.viewer.kiosk_refresh_s` | `15` | налаштування |
| `factory3d.viewer.bus_enabled` | `True` | налаштування, `neutralize.sql` |
| `factory3d.viewer.lite_default` | `auto` | налаштування |
| `factory3d.viewer.kiosk_token` | **не в XML** — `post_init` генерує `secrets.token_hex(16)` | кнопка «Новий токен», `neutralize.sql` |
| `factory3d.viewer.demo_enabled` | **не в XML** — `post_init` за ознакою демо-бази (ARCHITECTURE §2.8) | налаштування, `neutralize.sql` |
| `factory3d.viewer.demo_clock` | **не в XML** — `post_init`: `2026-10-12 10:30` на демо-базі, інакше порожньо | налаштування |
| `factory3d.viewer.signal_bus_ts` | порожньо | крон сигналів (службовий) |
| `factory3d.viewer.demo_queue`, `factory3d.viewer.demo_state` | порожньо | майстер демо (службові) |

### 5.2 `security/kiosk_user.xml`, `security/security.xml` — M-10, §4.3.

### 5.3 Статичні файли (`static/data`, `static/model`, `static/lib`) — генеруються `plant/export_viewer_assets.py` (§8.5), у git зберігаються (бінарні GLB — через git LFS, якщо репозиторій ним користується; інакше як є — 13,7 МБ).

### 5.4 `post_init` — кроки й очікувані кількості на копії демо-бази

| Крок | Дія | Очікувано на демо-базі |
|---|---|---|
| 1 | параметри `kiosk_token`, `demo_enabled`, `demo_clock` | `demo_enabled=True`, `demo_clock="2026-10-12 10:30"` (бо `factory3d_iot_sim` встановлений і компанія «Меблева фабрика (демо)») |
| 2 | перевірка кодів: для кожного коду з `manifest.parts[].codes` (усі унікальні коди; 1 078 після перебудови 14.10 — +`FA-SOC`, `FA-OFFICE`) — резолвер R-16 | знайдено: локації 697 (зі штрихкодом; після міграції base `f3d_code` = штрихкод), робочі центри 35, обладнання до 210, співробітники 35, зони 34 (коди з `manifest.parts[].codes`; payload `zones` віддає всі 45 активних `f3d.zone`, зокрема 11 надвірних base C.2 — X-29), батчі 6; у лог одна стрічка підсумку |
| 3 | знімок `kind=install` | 1 запис, `size_kb` 100…160 |
| 4 | якщо `x_f3d_signal` є — увімкнути крон «3D: сигнали імітації в шину» | крон `active=True` |

Кроки не створюють і не змінюють бізнес-записів.

## 6. Крони й фонові процеси (`data/cron.xml`)

| XML-id | Назва | Інтервал | Модель / метод | Один прогін | Ліміти |
|---|---|---|---|---|---|
| `cron_f3d_snapshot` | 3D: знімок стану | 10 хв (`interval_number=10`, `interval_type=minutes`), `active=True` | `f3d.viewer.snapshot._cron_snapshot` | 1 знімок, якщо у вікні `snapshot_hours`; ≤ 2 с на демо | пропуск, якщо попередній < 60 с тому |
| `cron_f3d_rotate` | 3D: ротація журналу станів | щодня 02:30 (Київ; у XML `nextcall` в UTC) | `f3d.viewer.snapshot._cron_rotate` | видаляє знімки й події старші `snapshot_keep_days`, батчами по 1 000 подій | ≤ 60 с, решта — наступного разу |
| `cron_f3d_signal_bus` | 3D: сигнали імітації в шину | 1 хв, `active=False` (вмикає `post_init`, якщо є `x_f3d_signal`) | `f3d.viewer.event._cron_signal_bus` | одна подія `kind=signal` з усіма зміненими шляхами | ≤ 500 кодів у повідомленні |
| `cron_f3d_demo` | 3D: заливка демо | `active=False`; майстер ставить `nextcall=now`, `numbercall=1` | `f3d.demo.wizard._cron_run` | усі обрані кроки, commit після кожного | ≤ 30 хв; `interval` 1 день, після прогону `active=False` |

Крони виконуються від `user_kiosk`? Ні: `user_id` крону = `base.user_root` (стандарт), а знімок береться
`with_user(user_kiosk)` всередині (`_take(user=user_kiosk)`), щоб payload знімка мав права кіоска, а не
суперкористувача.

## 7. HTTP/JSON API (C-04)

Спільне: усі маршрути `type="http"` повертають `Response` з `Content-Type: application/json; charset=utf-8`
і `Cache-Control: no-store` (крім API-01, API-07). Помилки — JSON `{"error": {"code": "<snake>", "message":
"<укр.>"}}` з HTTP-статусом. Параметри валідуються до звернення до ORM: `code`/`codes` —
`^[A-Za-z0-9_\-][A-Za-z0-9_.\-]*(/[A-Za-z0-9_\-][A-Za-z0-9_.\-]*)*$`, ≤ 64 символи, кожен (сегменти через `/` — назви документів, `WH/MO/00231`; сегмент не починається з `.`, тож `..` і `../x` — `400`), ≤ 200 кодів; `<snapshot_id>` — лише цифри, інакше `404 not_found`; `<code>` маршруту API-12 — той самий `CODE_RE` (невалідний — `400`, немає в базі — `404 not_found`); `since` — ISO-8601 UTC (`2026-10-12T07:30:12Z` або без `Z`);
`date` — `^\d{4}-\d\d-\d\d$`; `sections` — ключі з контракту через кому; `full`, `lite`, `kiosk` — `0|1`.
Невалідний параметр → `400 {"code": "bad_request"}`. `auth="user"` → без сесії Odoo віддає стандартний
редирект на `/web/login` (для `type=http`), тести перевіряють `401/303`.

### API-01 `GET /f3d/viewer/static`

`auth="user"`, група `group_f3d_user` (інакше `403 forbidden`). Відповідь: вміст
`model_static.json` + `{"meta": {"schema": "1.1", "built_at": …, "static_etag": "<sha1[:16]>"}}`.
Заголовки: `ETag: "<sha1 файлу>"`, `Cache-Control: private, max-age=3600`, `Content-Encoding: gzip` (якщо
клієнт приймає). `If-None-Match` збіг → `304`. Розмір ≈ 600 КБ / ≈ 80 КБ gzip. Кеш у пам'яті воркера:
`tools/static_data.load()` читає файл один раз і перечитує, коли змінився `mtime`.

### API-02 `GET /f3d/viewer/data`

`auth="user"`, `group_f3d_user`. Параметри: `sections` (csv, за замовчуванням усі живі), `full` (`1` —
злити зі статикою в один документ за контрактом), `lite` (`1` — `ctx.lite`), `codes` (csv — обмежити
`locations`/`workcenters`/`equipment` цими кодами; документи — ті, що посилаються на коди; для
«Показати в 3D» не використовується, повний payload завжди). Відповідь — R-01. Приклад (скорочено):

```json
{"meta": {"source": "Odoo 19.0 · timur-o19demo", "database": "odoo", "company": "Меблева фабрика (демо)",
          "warehouse": "WH", "now": "2026-10-12 10:30", "live": true, "pulled_at": "2026-10-13 23:06",
          "schema": "1.1", "user": "Адміністратор", "lite": false, "kiosk": false,
          "sections": {"products": "live", "locations": "live", "workcenters": "live", "productions": "live",
                       "workorders": "live", "sale_orders": "live", "purchase_orders": "live", "pickings": "live",
                       "quality_checks": "live", "maintenance_requests": "live", "equipment": "live",
                       "employees": "live", "docks": "live", "zones": "live", "chains": "live", "signals": "live",
                       "energy": "static", "lighting": "static", "ventilation": "static", "fire": "static",
                       "infra": "static", "evacuation": "static", "passports": "static"},
          "errors": [], "iot": {"source": "імітація датчиків (модуль factory3d_iot_sim)", "signals": 196,
          "alarms": 1, "updated": "2026-10-13 23:05"},
          "note": "Живі дані з бази: 42 переміщень, 32 виробничих замовлень, 804 залишків. Демо-годинник зупинено на 2026-10-12 10:30 — від нього рахуються таймери робочих завдань."},
 "products": {"DSP16-SON": {"default_code": "DSP16-SON", "name": "ДСП 16 мм Дуб Сонома 2800×2070", "uom": "арк", "categ": "Плитні матеріали", "seller": "Плитсервіс (демо)"}},
 "locations": {"PLT-04C": {"complete_name": "WH/Сировина/Плити/Портал/PLT-04C", "kind": "stack", "capacity": 60, "fill": 0.25,
               "quants": [{"product": "DSP16-SON", "qty": 15.0, "lot": "DSP16-SON-2609-131", "reserved": 15.0}]}},
 "workcenters": {"CNC-2": {"name": "Присадка ЧПК B", "code": "CNC-2", "status": "stop", "working_state": "blocked", "oee": 0.31, "capacity": 1,
                 "time_efficiency": 1.0, "productive_minutes": 65, "losses": [{"reason": "Поломка", "minutes": 48}],
                 "current_workorder": "WO00051", "queue": ["WO00045", "WO00039"], "maintenance_request": "MR/00031",
                 "manufacturer": "HOMAG", "model": "CENTATEQ P-110 /31", "energy": {"p_now": 0.7, "line": "BW-1"}}},
 "productions": [], "workorders": {}, "sale_orders": [], "purchase_orders": [], "pickings": [], "quality_checks": [],
 "maintenance_requests": [], "equipment": {}, "employees": {}, "docks": {"DOCK-W1": "WH/IN/00128"}, "zones": {},
 "sheet_chain": {}, "ship_chain": {}, "material_paths": [], "full_cycle_mo": "WH/MO/00237",
 "energy": {"consumers": {"SAW-1": {"p_now": 12.8}}, "totals": {"pv_kw": 0.0, "chp_kw": 397.3}}}
```

У живій відповіді статичні розділи присутні **лише** тими вузлами, куди записано сигнали (`energy.consumers.<code>.p_now`,
`equipment.<code>.battery`, `ventilation.units.<code>.filter_dp_pa`, `fire.groups.FA-FAC.dust`,
`energy.transformers.<code>.*`, `infra.totals.*`, `energy.totals.pv_kw/chp_kw`); значення сигналів обладнання
(`battery`, `hours`, …) лежать у `equipment.<code>` поруч із базовими полями M-01e; клієнт зливає все глибоко
(R-19). Коди: `200`; `403` без групи;
`500 {"code": "payload_failed"}` лише якщо впав сам збирач (не провайдер).

### API-03 `GET /f3d/viewer/delta`

`auth="user"`, `group_f3d_user`. Параметри: `since` (обов'язковий), `codes` (csv, підказка — об'єднується з
кодами подій), `lite`. Алгоритм R-14. Відповідь:

```json
{"ts": "2026-10-12T07:30:14Z", "full": false, "events": 3,
 "patch": {"workorders": {"WO00013": {…повний запис…}}, "workcenters": {"SAW-1": {…}},
           "productions": [{…повний запис МО WH/MO/00231…}], "pickings": [], "locations": {"PLT-04C": {…}},
           "equipment": {}, "maintenance_requests": [], "docks": {"DOCK-W1": "WH/IN/00128"},
           "zones": {"Z-CUT": {"pickings": []}}, "sheet_chain": {…}, "full_cycle_mo": "WH/MO/00237",
           "signals": [{"path": "energy/consumers/SAW-1/p_now", "value": 13.1}],
           "meta": {"now": "2026-10-12 10:31", "iot": {…}}},
 "removed": {"productions": ["WH/MO/00240"], "pickings": [], "locations": [], "workorders": []}}
```

Правила: записи вбудованих розділів у `patch` — **повні** записи власника (зниклий opt-ключ — зі значенням `null`),
доповнені ключами модулів; клієнт зливає `patch` у `D` глибоко (R-14 п. 7, X-23), розділ цілком не замінює; списки
`productions`/`pickings`/`maintenance_requests`/`quality_checks` — елементи з ключем `name`/`id` для злиття за ключем; `removed` —
ключі, яких більше немає (скасовані/видалені документи, локації без коду). `{"full": true, "ts": …}` —
клієнт перечитує API-02. Коди: `200`, `400` (без `since`), `403`.

### API-04 `GET /f3d/viewer/resolve`

`auth="user"`, `group_f3d_user`. Параметри: `code` **або** `name` (назва документа), рівно один.
Відповідь `{"model": "mrp.workcenter", "res_id": 12, "display_name": "Розкрій 1", "kind": "workcenter"}`
або `{"model": null, "res_id": null, "reason": "not_found"}` (`200`, не помилка). Алгоритм R-16.

Необов'язковий `codes` (лише з `code`; через кому, кожен за `CODE_RE`, ≤ 200, інакше `400`): коди дочірніх об'єктів сцени
(комірки стелажа). Якщо власного запису `code` немає, відповідь — список записів дочірніх кодів:
`{"model": "stock.location", "res_id": null, "res_ids": [11, 12, …], "display_name": null, "kind": "group", "count": 72}`
(R-16 п. 5). Власний запис має перевагу: відповідь тоді без `res_ids`.

### API-05 `GET /f3d/viewer/snapshots`

`auth="user"`, `group_f3d_user`. Параметри: `date` (`YYYY-MM-DD`, за замовчуванням сьогодні за Києвом).
Відповідь `{"date": "2026-10-12", "snapshots": [{"id": 17, "ts": "2026-10-12 07:00", "kind": "periodic",
"size_kb": 128, "note": null}], "mode": "snapshots"|"plan"}` — `mode="snapshots"`, якщо знімків ≥ 3.
Record rule компанії застосовується ORM.

### API-06 `GET /f3d/viewer/snapshot/<int:snapshot_id>`

`auth="user"`, `group_f3d_user`. Відповідь — payload знімка (повний документ контракту, `meta.snapshot = {id, ts, kind}`),
`Content-Encoding: gzip` напряму з вкладення (без розпакування на сервері, якщо клієнт приймає gzip).
`404`, якщо немає або не видно за правилом компанії.

### API-07 `GET /f3d/viewer/parts/manifest.json`

`auth="user"`, `group_f3d_user`. Відповідь — `static/model/parts/manifest.json`, у якому `parts[].file`
переписано на `/factory3d_viewer/static/model/parts/<key>.glb?v=<hash>`; `ETag`, `max-age=3600`.
Самі `.glb` — статика Odoo (`/factory3d_viewer/static/model/parts/core.glb`), стандартні `ETag`/`Last-Modified`,
`Cache-Control: public, max-age=604800` (Odoo `STATIC_CACHE`), а `?v=` гарантує оновлення.

### API-08 `GET /f3d/kiosk/<token>`

`auth="public"`, `website=False`, `sitemap=False`, `csrf=False`. Перевірки: `kiosk_enabled`,
`hmac.compare_digest(token, kiosk_token)`; інакше `404` (однакова відповідь для вимкненого й невірного).
Рендер QWeb `factory3d_viewer.kiosk_page` (§8.6) з `session_info` мінімальним (`{"db", "lang": "uk_UA",
"user_context": {"tz": "Europe/Kyiv"}}`), бандл `factory3d_viewer.assets_kiosk`, параметрами URL
(`tab`, `mode`, `code`, `layers`, `lite`, `refresh`) і `data-token`. Жодних даних Odoo у HTML.

### API-09 `GET /f3d/kiosk/<token>/static`, `/data`, `/delta`, `/parts/manifest.json`, `/snapshots`, `/snapshot/<id>`

`auth="public"`. Ті самі перевірки токена; далі `request.update_env(user=user_kiosk)` (Odoo 19 API:
`request.env = request.env(user=user_kiosk.id)`), `ctx.kiosk=True`, і виклик тієї самої логіки, що в
API-01…API-07. Rate-limit: ≤ 10 запитів/с на IP — лічильник у пам'яті воркера (`collections.deque` міток часу за IP,
вікно 1 с; публічна сесія для цього не придатна) → `429`. Відповіді без `Set-Cookie`.

### API-10 `POST /f3d/viewer/cycle_check`

`type="jsonrpc"`, `auth="user"`, `group_f3d_manager`. Параметри: `{"as_user": <id> | null}` (лише admin може
вказати іншого). Відповідь `{"ok": true, "issues": []}` або `{"ok": false, "issues": ["WH/IN/00134: приймання без
західних воріт", …], "count": 1}`. Той самий код, що M-05.

### API-11 `POST /f3d/viewer/maintenance/plan`

`type="jsonrpc"` (тіло JSON, CSRF-токен не потрібен), `auth="user"`, `group_f3d_user`; кіоск (`group_f3d_kiosk`,
`ctx.kiosk`) — завжди відмова. Параметри: рівно один із `{"code": "<f3d_code>"}` (regex §7) або `{"equipment_id": <int>}`.
Відповідь — завжди `result`; JSON-RPC не дає змінити HTTP-статус, тому статус помилки лежить у тілі:
`{"ok": false, "status": 400|403|404, "error": {"code": "bad_request|forbidden|kiosk|not_found|no_team", "message": "<укр.>"}}`.
Успіх: `{"ok": true, "created": bool, "request": <запис maintenance_requests[] (A.9)>, "equipment": {"<code>": {"maintenance_request",
"maintenance_request_id", "maintenance_due": null, "next_maintenance"}}}` — клієнт зливає це як delta-патч.
Алгоритм — R-22. ORM — з правами користувача запиту, без `sudo`.

### API-12 `GET /f3d/viewer/loc/<code>`

Історія однієї комірки для її картки (R-24); окремо від `/data`, щоб не роздувати періодичний payload.
`auth="user"`, `group_f3d_user` **і** `stock.group_stock_user` (як провайдер `stock`; інакше `403 forbidden`); запит
виконується з правами користувача (без `sudo`). `<code>` — `f3d_code` або `f3d_alias` локації: невалідний за `CODE_RE` —
`400 bad_request`, немає в базі — `404 not_found`. `Cache-Control: no-store`, gzip. Кіоск (API-09) маршруту не має.
Відповідь: `{"code", "complete_name", "truncated", "products": [{"product" (default_code), "name", "uom", "qty",
"reserved", "lots": [{"lot", "qty", "reserved", "arrived": [{"doc", "date", "qty", "from"}], "reserve": [{"doc", "qty",
"pending", "to"}]}], "out": [{"doc", "qty", "to", "date"}], "incoming": [{"doc", "qty", "from", "date"}]}]}`;
`doc` = `{"name", "model", "id", "kind": "picking|production|scrap|inventory|move", "state"}` (`model`/`id` порожні для
«Інвентаризації» й довільних рухів), `from`/`to` = `{"code" (f3d_code або null), "name" (complete_name)}`, `date` — київський
час `YYYY-MM-DD HH:MM`.

## 8. Клієнтська частина

### 8.1 OWL-дія `F3dViewerAction` (`static/src/action/viewer_action.js`)

```js
/** @odoo-module */
import { registry } from "@web/core/registry";
import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { F3dViewer } from "@factory3d_viewer/viewer/core";
import { DataClient } from "@factory3d_viewer/viewer/data_client";

export class F3dViewerAction extends Component {
    static template = "factory3d_viewer.ViewerAction";
    static props = { ...standardActionServiceProps };
    setup() {
        this.root = useRef("root");
        this.action = useService("action");
        this.bus = useService("bus_service");
        this.orm = useService("orm");
        this.notification = useService("notification");
        const p = this.props.action.params || {};
        onMounted(async () => {
            this.client = new DataClient({ bus: this.bus, base: "/f3d/viewer", kiosk: false });
            this.viewer = new F3dViewer(this.root.el, {
                client: this.client, lite: p.lite ?? "auto", testMode: !!p.f3d_test,
                onOpenRecord: (model, resId) => this.action.doAction({ type: "ir.actions.act_window", res_model: model, res_id: resId, views: [[false, "form"]], target: "current" }),
                onNotify: (msg, type) => this.notification.add(msg, { type }),
            });
            await this.viewer.mount();           // маніфест → core.glb → решта у фоні
            await this.viewer.load();            // /static → /data → підписка на шину
            this.viewer.applyParams(p);          // code | mo | picking | so | tab | mode | layers | snapshot
        });
        onWillUnmount(() => this.viewer?.destroy());   // відписка від шини, зупинка циклу рендера, dispose GLB
    }
}
registry.category("actions").add("f3d_viewer.action", F3dViewerAction);
```

Шаблон `factory3d_viewer.ViewerAction`: `<div class="o_f3d_viewer h-100" t-ref="root"/>` — ядро саме
створює розмітку макета (`#stage`, `#labels`, `header.bar`, `#side`, `#card`, `#flow`, `#help`) усередині
кореня з класами з префіксом `o_f3d_` (стилі в `viewer.scss` — рядки 5–312 макета з перейменуванням
селекторів `#id → .o_f3d_<id>`), щоб не конфліктувати з DOM Odoo. Заголовок дії (`breadcrumb`) —
`props.action.name` («Завод 3D» або «3D: WH/MO/00231»).

`applyParams(p)` (порядок): `layers` (`prod` → увімкнути шар «Замовлення в роботі»; інакше список ключів
шарів, решта вимкнути) → `mode` (`setMode`) → `tab` (`openTab`) → `snapshot` (R-17) → один із `mo`
(`showMO(name)`), `picking` (`showPicking(name)`), `code` (`select(await ensureCode(code))`, `focusOn`),
`so` (лише для підпису в картці: «Замовлення S00087»). Невідомий `code`/`mo`/`picking` → `onNotify("Об'єкта
… немає в моделі/даних", "warning")`, дія лишається відкритою на «Огляді». Дія з кнопки носія домішки (base CB-02, X-08)
приходить з `params = {code, alias, model, res_id, kind}`: переглядач бере лише `code`; `alias`, `model`, `res_id`, `kind`
довідкові й ігноруються, як і будь-які інші невідомі ключі (FR-02).

### 8.2 Ядро `F3dViewer` (`static/src/viewer/core.js`; панель, шар замовлень, потік, тривога й енергія — у тому ж файлі)

Вкладені шаблонні літерали (шаблон усередині `${…}` шаблону) у файлах переглядача заборонені: їх псує `rjsmin`.

Публічний API (використовують дія, кіоск, тури, HOOT):

| Метод / поле | Опис |
|---|---|
| `new F3dViewer(el, opts)` | `opts`: `client` (DataClient), `lite` (`0|1|"auto"`), `testMode` (bool — нульовий рендерер §8.7), `partsUrl` (за замовчуванням `/f3d/viewer/parts/manifest.json` через `client.manifestUrl`), `onOpenRecord(model, id)`, `onNotify(msg, type)`, `storage` (`localStorage` або `null`) |
| `mount()` | будує DOM, рендерер, завантажує маніфест, `core`; повертає `Promise` після `core`; решта частин у фоні (як `loadPart` макета, рядки 554–593) |
| `load()` | `client.loadStatic()` → `client.loadData()` → `this.D = merge(static, live)` (R-19) → `indexData()` → `openTab("overview")` → `client.subscribe(patch => this.applyPatch(patch))` |
| `applyPatch(patch)` | R-14 крок 7: глибоке злиття `patch` у `D` (`deepMerge`, X-23), елементи списків за `name`/`id`, `removed`, сигнали за шляхами, `updateLive()`, `paint` змінених кодів, перебудова overlay лише для змінених МО, автостарт/автостоп навчання (п. 10 нижче), `renderPanel(true)` якщо відкритий об'єкт/документ у `patch` |
| `select(obj \| code \| null, {keepHighlight})`, `ensureCode(code)`, `focusOn(obj)` | як у макеті (рядки 577–579, 1229–1243, 666) |
| `openTab(tab)`, `showMO(name)`, `showPicking(name)`, `showProduct(code)`, `showLine(code)`, `showChain(v)`, `showMatPath(i)`, `startDrill()`, `stopDrill()` | як у макеті (`openTab` 1390, `showMO` 1538, `showPicking` 1706, `showProduct` 1646, `showLine` 2060, `showChain` 1755, `showMatPath` 1748, `startDrill` 2561) |
| `setMode(mode)`, `setLayer(key, on)`, `setProdOverlay(on)`, `goView(nameOrIndex)` | режими кольору (794–835), шари (670–741), шар замовлень (1190–1213), види (634–646) |
| `setSimTime(min \| null)`, `playShift()`, `stopShift()`, `setPlaybackMode("plan" \| "snapshots")` | R3/R4 (2316–2537) + R-17 |
| `setLite(on)` | §8.4 |
| `getState()` | `{tab, panel, selected, mode, layers:{}, simMinutes, lite, live, playbackMode}` — для турів і тестів |
| `destroy()` | відписка, `renderer.setAnimationLoop(null)`, `dispose()` геометрій/матеріалів, зняття слухачів `resize/keydown` |
| `D`, `idx`, `items`, `layers` | дані, індекси (`indexData` 1287–1303), об'єкти сцени, шари — лише читання |

`window.odoo.f3d = viewer` виставляється в `testMode` або при `?debug=` (для турів: `odoo.f3d.getState()`).

Відмінності від `viewer/index.html` (решта — перенесення 1:1, зі збереженням імен функцій і рядків DOM):

1. Дані: `ODOO_URL`/`loadOdoo` замінено на `DataClient` (§8.3); `Promise.all([loadOdoo(), modelLoaded])`
   → `load()` після `mount()`.
2. R20: `setInterval(tick, 3000)` виконує лише `energyTick()` + `updateLive()` **якщо `!D.meta.live`**
   (демо-файл у статичній сторінці); при `meta.live` прогрес не імітується — лише патчі.
3. FR-07: `buildLabels`, маячки (2664–2668), `renderObject` читають `status` з `D.workcenters[code]?.status ??
   u.status` і `state` з `D.locations[code]?.state ?? u.state`; `applyPatch` перемальовує підпис верстата при
   зміні `status`.
4. Картка об'єкта: кнопка «Відкрити в Odoo» (`id="c-open"`), видима якщо `opts.onOpenRecord`; клік →
   `client.resolve({code})` → `onOpenRecord(model, res_id)` або `onNotify("У базі немає запису з кодом " + code, "info")`.
   У картках МО/переміщення/замовлення/заявки — посилання «Відкрити в Odoo» → `client.resolve({name})`.
5. `three` — `const { THREE, OrbitControls, GLTFLoader, CSS2DRenderer, CSS2DObject, RoomEnvironment } =
   await import(opts.threeUrl ?? "/factory3d_viewer/static/lib/three/three-bundle.esm.js")` у `mount()`;
   у статичній сторінці `dist/` той самий файл лежить поруч (`three-bundle.esm.js`).
6. `localStorage` (ключі `f3d.lite`, `f3d.layers`, `f3d.tab`) — лише зручності, усі читання в `try/catch`.
7. Теми: `viewer.scss` визначає `--f3d-*` токени від змінних Odoo (`--o-view-background-color`, `$o-brand-primary`)
   і темний варіант під селектором темної теми Odoo 19 Enterprise (клас на `body`; розробник бере його з
   `web_enterprise/static/src/webclient/*.scss`; тест AC-09 перевіряє через `data-theme="dark"` на `html`);
   ядро слухає `MutationObserver` на `document.documentElement` (`data-theme`), `prefers-color-scheme`, як у
   макеті (480–483), і зміну класу `body`.
8. Клавіші 1–9, 0, Esc обробляються лише коли фокус у переглядачі (`el.contains(document.activeElement) ||
   document.activeElement === document.body`), щоб не ламати гарячі клавіші Odoo.
9. Розділ «Енергія» та інші статичні розділи рендеряться лише якщо розділ є в `D` (макет уже так робить:
   `if (!e) …`), тому відсутність модулів фаз 2–5 не ламає панель.
10. Пожежна безпека за `factory3d_fire_safety` CF-01 (X-28, fire Q-09; FR-39):
    а) **автостарт/автостоп навчання**: після `load()` і кожного `applyPatch` ядро порівнює `D.evacuation.drill_active`
       з попереднім значенням: `null → {…}` (або змінилось `drill_active.name`) → `startDrill()` з `drill_origin`,
       `drill_zone`, `drill_detector`, `drill_steps` payload і зсувом таймлайна на `drill_active.elapsed_s` с; `{…} → null`
       → `stopDrill()`. Ручна кнопка «Сценарій пожежної тривоги» лишається; ручна зупинка під час активного навчання не
       перезапускає його до зміни `drill_active.name`. Без ключа `drill_active` (fire не встановлено) — як у макеті;
    б) **кольори станів**: `fire.groups[*].state` ∈ {`alarm`, `fault`} → червоний (`--bad`) і чип «Тривога» /
       «Несправність»; `prealarm`, `warn`, `disabled`, `test` → жовтий (`--warn`) з текстом «Передтривога»,
       «Попередження», «Вимкнено», «Тестування»; `ok` — зелений. У «Огляд → Потребує уваги» рядки `alarm`/`fault` — першими;
       `fire.panel.state` ∈ {`alarm`, `fault`} так само фарбує картку `FACP-1`;
    в) **маркери пристроїв**: якщо є `fire.devices` (`{address: {type, x, y, z, zone, state, dust}}`, лише за параметром
       fire `viewer_devices`), шар «Пожежна сигналізація» малює маркер кожного пристрою в точці (`x`, `y`, `z`) з кольором
       стану за п. б) замість підсвічування групи `FA-<зона>`; клік по маркеру → картка: адреса, `type`, зона, стан,
       `dust` (частка → %). Без `fire.devices` — підсвічування групи, як у макеті.
11. Рядки СКУД за `factory3d_access` CA-05 (X-28; FR-40), лише якщо ключі є в `D`: картка людини (`empHtml`) — «На
    території» (`employees[code].present`: «так»/«ні»), «Зона» (`zones[zone].name` або код `zone`, «з HH:MM» за
    `zone_since`), «Останній прохід» (`last_event`: `HH:MM · door · вхід|вихід` за `direction`; `type` ≠ `pass` →
    «відмова»); картка зони (`zoneHtml`) — «Людей зараз» (`zones[code].people_now`). Без `factory3d_access` рядків немає.
12. Зони (X-29; FR-41): `D.zones` містить усі 45 зон; контур зони, якої немає в `D.static.layout.zones` (11 надвірних),
    будується з `zones[code].polygon` (`[[x, y], …]`, м, система координат CB-04) — підпис і підсвічування як у зон цеху;
    зона з `is_roof: true` (`Z-ROOF`) малюється на висоті покрівлі 9 м і лише коли ввімкнено шар `roofdeck` (вид «Дах і
    СЕС»). Клік по надвірній зоні → `zoneHtml`, як для зон цеху (порожні `locations`/`workcenters` не показуються).
13. Координати техніки (`equipment/<code>/x`, `/y`) переглядач не показує — фаза 4; telemetry зберігає ці сигнали з
    `viewer_visible=False`, у payload їх немає (X-28, telemetry Q-08); рухома техніка лишається в позиціях моделі.

### 8.3 `DataClient` (`static/src/viewer/data_client.js`)

| Метод | Поведінка |
|---|---|
| `constructor({bus, base, kiosk, token, refreshS, debounceMs, fetch})` | `base` = `/f3d/viewer` або `/f3d/kiosk/<token>`; `fetch` — інжекція для тестів |
| `loadStatic()` | `GET {base}/static` з `If-None-Match` із `localStorage["f3d.static.etag"]`; `304` → з `localStorage["f3d.static"]` (якщо є, ≤ 2 МБ); інакше зберегти. Перевірка `meta.schema` (R-19). |
| `loadData()` | `GET {base}/data`; зберігає `lastTs = meta.ts_utc` (додаткове поле `meta.ts_utc` ISO) |
| `subscribe(cb)` | бекенд: `bus.addChannel("f3d_viewer")`, `bus.subscribe("f3d_viewer", msg => this._queue(msg))`; кіоск або `bus_enabled=false` (`meta.bus=false`): `setInterval(() => this._delta(), refreshS*1000)` |
| `_queue(msg)` | `pending.codes ∪= msg.codes`; `clearTimeout(t); t = setTimeout(_delta, debounceMs)` |
| `_delta()` | якщо `inflight` — позначити `again=true` і вийти; `GET {base}/delta?since=lastTs&codes=…`; `full` → `loadData()` і `cb({full: payload})`; інакше `cb(patch)`, `lastTs = ts`; помилка → лічильник `errors++`, `backoff = min(60, 2^errors)` с; після 5 помилок у кіоску — `location.reload()`; у бекенді — індикатор «немає зв'язку» і опитування кожні 30 с |
| `resolve({code \| name, codes})` | `GET {base}/resolve`; `codes` — коди дочірніх об'єктів (API-04, R-16 п. 5) |
| `locHistory(code)` | `GET {base}/loc/<code>` (API-12, R-24); `404` → `null`; кіоск і `FileClient` — `null` |
| `snapshots(date)`, `snapshot(id)` | API-05/06, кеш `Map<id, payload>` ≤ 20 записів |
| `state` | `"loading" \| "live" \| "polling" \| "offline"`; подія `statechange` для індикатора (R2) |
| `bus` подія `disconnect`/`reconnect` (Odoo `bus_service` емітує `BUS:DISCONNECT`/`BUS:RECONNECT`) | → `polling`/`live`; після `reconnect` — негайний `_delta()` |

### 8.4 Lite-режим (`static/src/viewer/lite.js`)

`detectLite()` → `true`, якщо `navigator.deviceMemory !== undefined && navigator.deviceMemory <= 4` (Chrome віддає не більше 8, тож при `<= 8` lite вмикався б завжди) або
(`matchMedia("(pointer: coarse)").matches` і `innerWidth <= 1400`) або `opts.kiosk && !params.lite==="0"`.
`applyLite(viewer, on)`:

| Параметр | Повний | Lite |
|---|---|---|
| `renderer.setPixelRatio` | `min(devicePixelRatio, 2)` | `1` |
| `antialias` | `true` | `false` (рендерер створюється один раз — lite визначається до створення; перемикання в UI → перезавантаження дії з параметром `lite`) |
| тіні (`shadowMap.enabled`, `sun.castShadow`) | увімкнені, 4096² | вимкнені; перемикач «Тіні» прихований |
| оточення | `PMREMGenerator` + `RoomEnvironment` | немає; `HemisphereLight` 0.55 + `DirectionalLight` 1.2 |
| `envMapIntensity` матеріалів | 0.45 | 0 |
| частинки гілок (`branchParticles`) | 3 на гілку, 1…4 у шарі замовлень | 1 |
| підписи (`syncLabels`) | зони + верстати ≤ 70 м | зони + вибраний об'єкт |
| частини у фоні | усі по черзі | лише `engineering`; `fire`, `it`, `site` — при вмиканні шару |
| `controls.enableDamping` | `true` | `false` |
| `TubeGeometry` сегменти | `pts*24`, радіальних 8 | `pts*10`, радіальних 4 |
| ціль | 60 кадр/с ПК | ≥ 30 кадр/с Samsung Galaxy Tab Active5 Pro (10,1", 1920×1200), «Загальний вигляд» + шар замовлень; вимірюється `test_perf` MAN |

### 8.5 Збирання асетів — `plant/export_viewer_assets.py` (поза модулем, крок після `build_scene.py`)

```
python3 plant/export_viewer_assets.py odoo_addons/factory3d_viewer [--dist dist] [--no-three]
```

Кроки (усі детерміновані, без Blender; потрібен Node для esbuild):

1. `static/data/model_static.json` ← `Demo().build()` з фільтром Додатка B (видалити документи й живий стан),
   додати `layout` (із `plant/layout.py`: `W,D,H`, `ZONES` → `{code: {name, rect, color, desc}}`, `MACHINES` →
   `{code: {type, name, x, y, desc, zone}}`, `DOORS`, `RCV_GOODS`, `LAYERS`), `path_templates` (Додаток B),
   `door_goods` (`plant/cycle_check.DOOR_GOODS`), `meta.schema="1.1"`, `meta.built_at`, `meta.git`.
2. `static/data/demo_payload.json` ← `Demo().build()` як є (вхід майстра демо).
3. `static/model/parts/*.glb` ← копія `dist/parts/*.glb`; `manifest.json` ← `dist/parts/manifest.json` +
   `parts[].hash = sha1(file)[:12]`; `file` лишається `parts/<key>.glb` (контролер API-07 переписує URL).
4. `static/lib/three/three-bundle.esm.js` ← `npx --yes esbuild@0.21.5 plant/viewer_three_entry.js
   --bundle --format=esm --minify --sourcemap --outfile=…` де `plant/viewer_three_entry.js`:
   `export * as THREE from "three"; export { OrbitControls } from "three/addons/controls/OrbitControls.js"; …`
   з `node_modules/three@0.160.0` (`package.json` у корені репозиторію: `devDependencies: {"three": "0.160.0",
   "esbuild": "0.21.5", "@gltf-transform/cli": "4.1.1"}`); `--no-three` пропускає (бандл уже в git).
5. `static/data/BUILD.json`.
6. `dist/index.html` і `dist/factory_viewer.html` (`build_scene.py --embed`) збираються з того самого ядра:
   `viewer/index.html` після W2 містить лише розмітку-скелет і `<script type="module">import {F3dViewer}
   from "./viewer/core.js"; …</script>` з `DataClient` у режимі «файл» (`base: null` → читає `odoo_demo.json`
   поруч, без delta) — FR-38. Скрипт копіює `static/src/viewer/*.js` у `dist/viewer/` і бандл three поруч.

### 8.6 Сторінка кіоска (`views/templates_kiosk.xml`, `static/src/kiosk/kiosk.js`)

QWeb `factory3d_viewer.kiosk_page`: `<!DOCTYPE html><html lang="uk"><head>` `meta viewport`
(`width=device-width, initial-scale=1, viewport-fit=cover`), `<title>Завод 3D</title>`,
`t-call-assets="factory3d_viewer.assets_kiosk"`, `<body class="o_f3d_kiosk">` з
`<div id="f3d-kiosk" t-att-data-token="token" t-att-data-params="json.dumps(params)"/>` і `<script>odoo = {csrf_token, debug: "", session_info: {…}}</script>`.
`kiosk.js` (`/** @odoo-module */`): після `whenReady` — `new DataClient({base: "/f3d/kiosk/" + token, kiosk: true,
refreshS})`, `new F3dViewer(el, {client, lite: params.lite ?? "auto", kiosk: true})`, `mount()`, `load()`,
`applyParams(params)`; у кіоску ядро ховає кнопки «Відкрити в Odoo», меню видів лишається (сенсорне),
панель «Показ» без «Тіні»; `setInterval(reloadAt0400, 60000)` — FR-33; `navigator.onLine` події →
`client.state`. Без шини (A-03).

### 8.7 Тестовий режим (нульовий рендерер)

`opts.testMode` або `?f3d_test=1` або `new WebGLRenderer()` кинув виняток (headless Chrome без GPU): ядро
створює `NullRenderer` (`setSize/setPixelRatio/render/setAnimationLoop(fn)` — `fn` викликається `setInterval`
100 мс, `domElement` = `<canvas>` без контексту), `GLTFLoader` працює (парсинг — чистий JS), `CSS2DRenderer`
працює; `pick()` повертає `null`; вибір у турах — через `odoo.f3d.select("SAW-1")`. Панель, дані, патчі,
підсвічування (`paint` змінює матеріали — працює без GPU) тестуються повністю. У `getState()` → `renderer: "null"`.

### 8.8 Сумісність зі статичною сторінкою

`viewer/index.html` стає: розмітка (рядки 314–395 макета без змін) + `<script type="module">` на 30 рядків:
`import {F3dViewer} from "./viewer/core.js"; import {FileClient} from "./viewer/data_client.js"; const v = new
F3dViewer(document.getElementById("app"), {client: new FileClient("odoo_demo.json"), threeUrl:
"./viewer/three-bundle.esm.js"}); await v.mount(); await v.load();`. `FileClient` = `DataClient` з `base=null`:
`loadStatic()` → `{}` (у файлі все разом), `loadData()` → весь файл, `subscribe` → `tick` імітації (R20 для
`meta.live=false`). `build_scene.py --embed` вбудовує, як і раніше, `odoo-data`, `parts-manifest`, `part-*`.
Таким чином регресії макета (R-A) перевіряються одним HOOT-прогоном на `demo_payload.json`.

## 9. Алгоритми й правила

### R-01 Побудова payload (`tools/payload.PayloadBuilder`)

Вхід: `env` (користувача), `full: bool`, `lite`, `kiosk`, `sections: set|None`, `codes: set|None`.

1. `static = static_data.load()`; `ctx` за M-01 (`now`, `now_local`, `today` — R-02; `static`; `lite`; `kiosk`; `energy_cost`; `user`).
2. `payload = {"meta": {...}}`; якщо `full` — `payload.update(deepcopy(static без "layout","path_templates"))`
   (розділи `energy`, `lighting`, `ventilation`, `fire`, `infra`, `evacuation`, `passports`, `zones`, `docks`
   беруться статичні; `meta.sections[k]="static"`); інакше в `payload` лише живі розділи, а для сигналів
   створюються порожні вузли `energy.consumers/transformers/totals`, `equipment`, `ventilation.units`,
   `fire.groups`, `infra.totals` (щоб провайдер сигналів мав куди писати) — клієнт зливає глибоко.
3. Провайдери — duck-typing (M-01, X-22): усі моделі реєстру з префіксом імені, незалежно від `_inherit`:
   `providers = sorted([env[n] for n in env.registry if n.startswith("f3d.viewer.provider.")],
   key=lambda m: (getattr(m, "_f3d_sequence", 1000), m._name))`. Атрибути читаються лише через `getattr` з
   умовчаннями M-01: `seq = getattr(p, "_f3d_sequence", 1000)`, `secs = tuple(getattr(p, "_f3d_sections", ()))`,
   `grp = getattr(p, "_f3d_group", "factory3d_base.group_f3d_user")`, `collect = getattr(p, "_f3d_viewer_collect", None)`;
   `collect is None` → WARNING «провайдер <name> без _f3d_viewer_collect» і пропуск (розділи не позначаються).
4. Для кожного `p`: якщо `sections` задано і `set(secs) ∩ sections == ∅` — пропустити; якщо група `grp`
   відсутня в базі (`env.ref(grp, raise_if_not_found=False)` — `None`) або `not env.user.has_group(grp)` —
   `meta.sections[k]="denied"` для його розділів, пропустити;
   інакше `try: with env.cr.savepoint(): collect(payload, ctx)` → `meta.sections[k]="live"`
   для записаних розділів; `except Exception as e: _logger.exception(...)`; `meta.sections[k]="error"`;
   `meta.errors.append({"provider": p._name, "error": type(e).__name__})`; стан розділів — як до провайдера
   (savepoint відкочує лише БД; `payload` відновлюється з `deepcopy`, зробленої перед викликом, якщо
   розділи провайдера ≤ 1 МБ; інакше провайдер відповідає сам).
5. `meta`: `source = f"Odoo {serie} · {host}"` (`web.base.url` без схеми), `database = env.cr.dbname`,
   `company`, `warehouse` = код першого складу компанії (`stock.warehouse.code`), `now`, `live=True`,
   `pulled_at` (реальний час за Києвом), `schema="1.1"`, `ts_utc` (ISO, для `since`), `user`, `lite`, `kiosk`,
   `bus = bus_enabled`, `sections`, `errors`, `note` (як у `LiveDemo.build`: кількості переміщень, МО,
   залишків, демо-годинник, сигнали), `iot` (з M-01h).
6. Порядок ключів верхнього рівня (X-24, Додаток A.0): збирач перебудовує `payload` — спершу 26 базових ключів у
   порядку A.0 (ті, що є), далі ключі модулів (`yard`, `access`, A.15) у порядку першої появи, тобто за `_f3d_sequence`
   провайдера, що їх додав (`yard` 160, потім `access` 170); порядок вкладених ключів контрактом не фіксується.
7. Повернути `payload`. Гарантія: будь-який провайдер, що впав, не змінює інші розділи.

### R-02 Час і часовий пояс (`tools/dates.py`)

`TZ = Europe/Kyiv`. `local(dt_utc) -> "YYYY-MM-DD HH:MM"`; `utc(s_local) -> datetime`; `now(env)`: якщо
параметр `demo_clock` непорожній і валідний — `utc(demo_clock)`, інакше `datetime.utcnow()`; `today = local(now)[:10]`.
Поля `Date` (`request_date`, `next_action_date`) → `"YYYY-MM-DD 00:00"` → у payload як `"YYYY-MM-DD HH:MM"`
(`maintenance_requests[].request_date` у файлі має час — для `Date` беремо `create_date` заявки за Києвом).
`since` у `/delta` — UTC ISO; `ts_utc` у `meta` — UTC ISO.

### R-03 Товари й локації — M-01a.

### R-04 Заповненість і стан комірки

- `kind` = base `stock.location.f3d_loc_kind` (M-03, X-14); порожнє — запасне `static.layout.locations[code].kind`.
- `capacity` = base `stock.location.f3d_capacity`, якщо > 0 (у payload — `int`, якщо значення ціле, інакше
  `round(…, 2)`); `0` («не задано» за base) — запасне `static.layout.locations[code].capacity` (stack 60/55, bin —
  `orderpoint.max`, shelf 2200, pallet_cell 2, area `null`). Приклад: `PLT-04C` з `f3d_capacity=60` → `capacity: 60`;
  `f3d_capacity=0` → `capacity` зі статики (60).
- `fill`: `pallet_cell` → `min(1, len(quants)/2)`; `capacity` → `min(1, Σqty/capacity)`; інакше `null`
  (`LiveDemo.sync_stock`).
- `orderpoint`: `stock.warehouse.orderpoint` з `location_id` = локація: `{product: default_code, min:
  product_min_qty, max: product_max_qty, purchase: назва підтвердженої закупівлі, рядок якої має
  `orderpoint_id` = це правило (`purchase.order.line.orderpoint_id`, якщо модель є)}`; `purchase` відсутній, якщо
  немає.
- `state` (лише для локацій з `orderpoint`): `have = Σqty` того товару; `out` якщо `have ≤ 0`, `low` якщо
  `have < min`, інакше `ok`. Приклад: `FUR-R1-S02-L3`: 705 шт, min 250 → `ok`, `fill = 705/833 = 0,846`.

### R-05 Ворота, фура, техніка й тип переміщення

Для `stock.picking` (`state != 'cancel'`, `scheduled_date` у діапазоні `today − 7 … today + 7` або
`state in ('assigned','waiting','confirmed')`):

- `type`: `picking_type_code == 'incoming'` → `incoming`; `'outgoing'` → `outgoing`; `'internal'` → за
  назвою типу операції (`picking_type_id.name`, lang uk): «Розміщення плит у стелажі» → `putaway`,
  «Поповнення під портал» → `replenish`, «Комплектація компонентів» → `pick_components`, «Розміщення
  готової продукції» → `store_finished`; інші внутрішні — не включати (як `LiveDemo`: «нові внутрішні
  без місця в 3D не показуємо»). `picking_type` = назва типу.
- `dock`: 1) `batch_id.dock_id.f3d_code` якщо є; 2) інакше для `incoming` — `f3d_code` локації
  `location_dest_id` або будь-якого `move_line_ids.location_dest_id`, що має вигляд `UNLOAD-k` → `DOCK-Wk`;
  для `outgoing` — `f3d_code` локації `location_id`/`move_line_ids.location_id` виду `DOCK-Ek` або
  `OUT-STAGE` + `Z-OUT-k` → `DOCK-Ek`; 3) інакше ключ відсутній. Приклад: `WH/IN/00131` без батча, dest
  `WH/Вхід/Ворота 2` (`UNLOAD-2`) → `DOCK-W2`.
- `truck`: `batch_id.f3d_code` — єдиний код фури в 3D (base CB-06, C-08, X-15; `TRUCK-IN-1`…`TRUCK-OUT-3`), інакше
  `null`. `batch_id.f3d_truck` (опис/назва фури з макета) і держномер (yard `f3d_plate`) у `truck` не потрапляють.
- `vehicle`: `batch_id.f3d_vehicle_id.f3d_code` (`FL-2`), інакше відсутній.
- `docks` (живі): `{dock_code: назва переміщення}` — для кожних воріт перше за `scheduled_date` незавершене
  (`state != 'done'`) переміщення з цим `dock`; якщо таких немає — останнє завершене сьогодні; ворота без
  документа — відсутні в словнику.

### R-06 Робочі центри

Для кожного `mrp.workcenter` з `f3d_code`:

- `working_state` — як є (`normal|blocked|done`).
- `current_workorder` — `WO<id:05d>` завдання зі `state='progress'` на цьому центрі (перше за `date_start`);
  `queue` — до 8 завдань зі `state in ('ready','waiting','pending')`, сортування `(state != 'ready', production.name)`.
- `status`: `blocked` → `stop`; інакше `current_workorder` → `work`; інакше `idle`.
- `losses`: рядки `mrp.workcenter.productivity` за сьогодні (за Києвом) з `loss_id.loss_type != 'productive'`,
  згруповані за `loss_id.name` (uk): `[{reason, minutes: round(Σduration)}]`, відсортовано за `minutes` спаданням.
- `productive_minutes` = `round(Σ duration)` рядків `loss_type='productive'` за сьогодні (відкриті — до
  `ctx.now`).
- `oee` = `round(productive_minutes / max(1, shift_elapsed), 2)`, де `shift_elapsed` = хвилин від початку
  зміни (`resource_calendar_id` перший інтервал сьогодні, інакше 07:00) до `min(ctx.now, кінець зміни)`,
  обмежено `0…1`. Приклад (демо): SAW-1: `productive 176`, зміна 07:00, `now` 10:30 → `210` хв → `0.84`.
  CNC-2: `65/210 = 0.31`. (Стандартне поле `mrp.workcenter.oee` Odoo рахує за інший період, тому не
  використовується.)
- `capacity` = `capacity` першого рядка `capacity_ids` без продукту (`product_id = False`), інакше `1.0` — так само,
  як `mrp.workcenter._get_capacity()` Odoo 19 для загальної місткості (поля `default_capacity` немає; X-92);
  `time_efficiency` = `time_efficiency/100`.
- `idle_reason`: якщо `status='idle'` — перший рядок `note` робочого центру (HTML → текст) або, якщо є
  завдання `waiting` у черзі, «Чекає компонентів для {production}» ; якщо немає — відсутній.
- `maintenance_request`: назва першої відкритої заявки з `equipment_id.workcenter_id` = центр.
- `manufacturer`, `model`: з `maintenance.equipment` цього центру (`f3d_manufacturer`, `f3d_model`, C-09) або
  `static.passports[code]`.
- `energy`: `{p_now: static.energy.consumers[code].p_now (перекриється сигналом), line: …line}`.

### R-07 МО і робочі завдання

`mrp.production` зі `state != 'cancel'` і (`state in ('confirmed','progress','to_close')` або `date_finished ≥ today`):

- `state`: `to_close` → `progress`; `draft` → `confirmed`; інші як є. `reservation_state`: лише якщо
  `reservation_state == 'confirmed'` і `state == 'confirmed'` → `"waiting"`, інакше ключ відсутній.
- `product`, `product_name`, `qty = product_qty`, `uom = product_uom_id.name`, `origin` (назва SO або
  батьківського МО), `route` = `bom_id.code` (у демо «A», «B», «C», «D», «F1»…; якщо порожньо — `""`),
  `date_start = local(date_start)`, `date_deadline = local(date_deadline або date_finished)`, `child_productions` =
  назви МО з `origin` = це МО (лише якщо є).
- Завдання (`workorder_ids` за `sequence, id`): `id = f"WO{wo.id:05d}"`, `name`, `production`, `workcenter =
  f3d_code`, `sequence = k+1`, `duration_expected = round()`, `state`: `done`→`done`; `progress`→`progress`;
  `cancel` — пропустити; `waiting` → `waiting`; `ready`/`blocked`/`pending`: якщо `k == 0` і
  `reservation_state == 'waiting'` → `waiting`, інакше `ready` якщо попереднє `done|progress`, інакше `pending`
  (`LiveDemo.sync_production`, рядки 143–147).
- Час з журналу `mrp.workcenter.productivity` по `workorder_id`: `worked = Σ minutes(date_start, date_end або
  ctx.now)`, `first = min(date_start)`, `last = max(date_end)`. `done`: `date_start = local(first або
  wo.date_start)`, `date_finished = local(last або wo.date_finished)`, `duration = round(worked)`, `progress = 1.0`.
  `progress`: `date_start`, `duration`, `progress = round(min(0.99, worked/max(1, duration_expected)), 2)`,
  `date_planned_finished = local(start + duration_expected)`, `blocked = True` якщо `working_state == 'blocked'`
  (ключ лише коли true). Інші: `progress = 0.0`, без дат.
- `progress` МО = `round((n_done + Σ progress(progress)) / n, 2)`; при `n == 0` — `0.0`.
- `energy_kwh`, `energy_cost`: `Σ p_inst(wc) × kf(type) × duration/60` по завданнях `done|progress`
  (`p_inst`, `kf` — `static.energy.consumers[code].p_inst`, `static.energy.profile_k[type]`, `tariff =
  static.energy.meta.tariff_uah`), як `Demo.build_energy`. Приклад: `WH/MO/00231` → 86,2 кВт·год, 724 грн.
  `energy_cost` записується лише при `ctx.energy_cost` (група `factory3d_energy.group_f3d_energy_cost`, не кіоск — §4.4,
  X-25); інакше ключа в записі МО немає. `energy_kwh` — завжди.
- Демо-годинник: усі «до зараз» — `ctx.now` (R-02).

### R-08 Компоненти МО

Для `move_raw_ids` зі `state != 'cancel'`, згруповано за товаром: `{product: default_code, qty:
round(Σ product_uom_qty), available: Σ quantity (зарезервовано) ≥ qty або state == 'done', locations:
коди локацій з ненульовим квантом цього товару (до 12, порядок — `static.layout` порядок)}` + поля R-11.
Компонент-фасад (товар дочірнього МО) включається так само; `child_productions` дає зв'язок.

### R-09 Рядки переміщення, прогрес, місця

- `lines`: по `move_ids` зі `state != 'cancel'`: `{product, qty: product_uom_qty, qty_done: round(quantity, 2)
  якщо picked або state == 'done', інакше 0}`.
- `progress = round(Σ min(qty_done, qty) / max(Σqty, 1), 2)`; `state` → `PICK_STATE` (`confirmed|waiting` →
  `waiting`, `assigned`, `done`, `draft`, інше як є); `scheduled_date = local(date_done якщо done інакше
  scheduled_date)`; `partner`, `origin`, `carrier = carrier_id.name` (якщо поле є — `stock_delivery`).
- `source_locations`: унікальні `f3d_code` з `move_line_ids.location_id` (для `outgoing`, `putaway`,
  `replenish`, `pick_components`); `location_dest`: для `pick_components`/`replenish`/`putaway` —
  `f3d_code` з `move_line_ids.location_dest_id` або `location_dest_id` (код `KIT-01`, `PLT-07C`); для
  `incoming`/`store_finished` — `complete_name` без префікса складу («Склад крайки») — як у файлі.
- `note`: для `outgoing` зі `state='waiting'` — «Чекає завершення МО»; для `incoming` з перевіркою якості
  `fail` — «{n} арк. пройшли контроль; {m} — у карантині ({QC})»; інакше `note` з `picking.note` (текст, ≤ 200).

### R-10 Шлях плити до пили (`productions[].supply`) — порт `Demo.mo_supply`

`prod` = перший компонент з категорії «Плитні матеріали» (`product.categ_id.name`) або `default_code`
з префіксом `DSP|MDF|HDF`. `pick` = перше `incoming` переміщення постачальника плит з цим товаром (за
`scheduled_date`); `door = int(dock[-1])` або `1 + sum(ord) % 3`. `gantry = first("PLT-", prod)`,
`rack = first("RCK-", prod)` (перша локація з префіксом і ненульовим квантом товару, порядок зі статики);
`lot` = лот кванта під порталом. Кроки — точно як рядки 756–778 макета (`GATE-W` → фура/ворота →
`UNLOAD-k` → `QC-PLT-k` (з `doc` = `quality_checks[].name` для цього приймання, якщо є) → `rack` → `gantry`),
`warn`, `note`. Етикетки — українською з того самого коду.

### R-11 Шляхи компонентів (`components[].door/receipt/expected/kind/to/path`) — порт `Demo.component_sources`

Префікс товару (`default_code`): `DSP|MDF|HDF` → «плита» → `to = wc("SAW","NEST","SLIDE","VSAW")`;
`FUR` → «фурнітура» → `wc("ASM","ASMLINE") або wc("HINGE")`; `EB` → «крайка» → `wc("EDGE")`; `LFM|PVC` →
«ЛФМ»/«плівка ПВХ» → `PRESS` для PVC, `GLUE` для `LFM-GLUE`, інакше `AUTOSPRAY|SPRAY|UV`, запасний
`GLUE|SPRAY|PRESS`; `PK` → «пакування» → `wc("BOX","PACK")`. `wc(*pre)` — перший робочий центр завдань МО
з таким префіксом коду. `door_of = {FUR:4, EB:5, LFM:6, PVC:6, PK:7}`; якщо є приймання з цим товаром —
`door` з його `dock`, `receipt` = останнє приймання з `progress > 0`, інакше `expected = "{name} о {HH:MM}"`
наступного. Кроки шляху — шаблон `static.path_templates[kind]` (Додаток B) з підстановкою `k`, фури
(`trucks[k]` — фура, що зараз стоїть у воротах k), першої локації з товаром (`first("RCK-"/"PLT-"/"FUR-"/"EB-")`),
візка `KIT-*` МО (локація з `production` = МО) або `Z-PRE`. Якщо префікс невідомий — `kind` відсутній,
`path = [GATE-W, DOCK-Wk, UNLOAD-k]`, `to = null` (клієнт не малює гілку). `product.categ_id.name` не
використовується для класифікації — лише префікс коду (контракт макета; Q до base не потрібен).

### R-12 Шлях до клієнта, фасади, `full_cycle_mo` — порт `Demo.mo_delivery`

`so = sale_orders[origin]`; `out = pickings[so.delivery]` (`delivery` = перше незавершене `outgoing` з `origin`
= SO або `sale_id`); `k = out.dock[-1]`; `cell` = перша комірка з `source_locations` з квантом виробу, інакше
перша `FG-R*` з виробом, інакше перша порожня `FG-R*`, інакше `FG-R1-B01-L1`; `last` = центр останнього
завдання; кроки — рядки 870–884 макета (`PRN-PACK1|2` → `POST-STAGE` (`doc` = `store_finished` для МО) →
`cell` → `SCALE-OUT1|2` (`k ≤ 4` → 1) → `Z-OUT-k` → `out.dock` → `out.truck` (якщо є) → `TRUCK-SCALE` → `GATE-E`),
`note` без фури. Фасади (МО з `origin` = інше МО): `buf` = локація `FRONTS-*` з `fronts_mo` = це МО (локації
`FRONTS-*` мають `fronts_mo`/`production` зі статики `static.layout.locations` + живих квантів: `fronts_mo`
= МО, виріб якого лежить у цій локації, або порядкове правило макета: k-те МО фасадів → `FRONTS-{k+1}`),
`asm` = центр `ASM*` батька, `delivery = {picking, partner, via: parent, steps: buf+asm+parent.steps, note}`.
`full_cycle_mo` = перше МО `progress` з `delivery.steps` ∋ `TRUCK-OUT*`, `supply.steps` ∋ `TRUCK-IN*` і
компонентом `FUR*` з `KIT-` у шляху; інакше перше МО.

### R-13 Ланцюжки, шляхи матеріалів, живі поля зон і воріт — порт `sheet_chain`, `ship_chain`, `material_paths`

- `sheet_chain.steps` (5 кроків, тексти з макета рядків 964–984): `docs` — живі назви: крок 1 — приймання
  плит сьогодні з фурою; крок 2 — `quality_checks` плит; крок 3 — `putaway` переміщення; крок 4 — `replenish`;
  крок 5 — МО з завданням `progress` на `SAW-1` (інакше перше МО). `codes`: крок 1 — фури й `UNLOAD-1..3`;
  2 — `QC-PLT-1..3`, `QC-1`; 3 — `BOARD-RACKS`, `location_dest` першого putaway, його `vehicle`; 4 —
  `GANTRY-1`, `location_dest` першого replenish, `vehicle`; 5 — `SAW-1..3`, `NEST-1`. `stock` — рядки
  «{n} стосів · {Σ} арк.» за квантами (функції `stacks`, `sheets`). `path` — 6 точок: фура першого приймання →
  `UNLOAD-k` → `QC-PLT-k` → `location_dest` putaway → `location_dest` replenish → `SAW-1`; якщо putaway/replenish
  немає — `RCK-R1-1A` / `PLT-01A`.
- `ship_chain.steps` — рядки 929–944: `stock` з живих кількостей (`store_finished` переміщень, зайнятих
  `FG-R*`, `outgoing` сьогодні, фур біля східних воріт).
- `material_paths` — для кожного `kind` перший компонент з `to`: `{kind, product, mo, steps: path + [{code: to,
  label: workcenters[to].name}]}`.
- `zones[code]` (X-29): записи для **всіх** активних `f3d.zone` base (45 = 34 зони цеху + 11 надвірних base C.2:
  `Z-GATE-W`, `Z-GATE-E`, `Z-YARD-W`, `Z-YARD-E`, `Z-KPP`, `Z-PARKING`, `Z-BOILER`, `Z-FIREWATER`, `Z-ENERGY`,
  `Z-WASTE`, `Z-ROOF`); статичний запис зони (якщо є) зливається глибоко з живими полями: `name` (`f3d.zone.name`),
  `zone_type` (`f3d.zone.zone_type`, напр. `production`, `outdoor`), `polygon` (`f3d.zone.polygon` — `[[x, y], …]`, м;
  ключ відсутній, якщо контур порожній; для надвірних зон — єдине джерело геометрії, у статиці їх немає), `is_roof`
  (`true` лише для `Z-ROOF`; ключ лише коли `true`), `locations` (коди локацій зони зі статики
  `static.zones[code].locations`, відфільтровані за наявністю в `locations`; для зон без статики — `f3d_code`
  локацій `f3d.zone.location_ids` або `[]`), `workcenters` (статика; для зон без статики — `f3d_code`
  `f3d.zone.workcenter_ids` або `[]`), `pickings` — назви переміщень з `dock` у цій зоні (`Z-RCV-k` ↔ `DOCK-Wk`,
  `Z-OUT-k` ↔ `DOCK-Ek`), `odoo_location` — `f3d.zone.root_location_id.complete_name` (C-08), інакше статика, інакше
  `null`. Приклад: `Z-YARD-W` → `{"name": "Двір приймання (фури біля західних воріт)", "zone_type": "outdoor",
  "polygon": [[-32.0, 0.0], …], "odoo_location": null, "locations": [], "workcenters": []}` (контур — як у base C.2,
  габарит −32…0 × 0…72 м); `Z-ROOF` → `zone_type: "outdoor"`, `is_roof: true`, габарит 0…150 × 0…72 м.

### R-14 Delta (`tools/payload.DeltaBuilder`)

1. `changes = f3d.viewer.event._since(since)`; `None` → `{"full": true, "ts": now}`.
2. `codes = ∪ changes.values() ∪ codes_param`; якщо `codes` порожні і подій немає → `{"ts": now, "patch": {}, "removed": {}, "events": 0}`.
3. `ctx.changes = changes`, `ctx.codes = codes`; `patch = {}`, `removed = {}`.
4. Провайдери — у тому самому порядку й з тими самими перевірками (`getattr`, група, `sections`, `savepoint`,
   `meta.errors`), що R-01 п. 3–4 (X-22); для кожного `delta = getattr(p, "_f3d_viewer_delta", None)`, `None` →
   п. 5. Вбудовані провайдери: `stock` — локації з кодів + локації з подій
   `stock.quant`/`stock.move.line` (повні записи за R-03/R-04); `production` — завдання `WO*` з кодів, їхні МО,
   МО з кодів, робочі центри з кодів **і** центри цих завдань (повні записи); `logistics` — переміщення з назв
   у кодах і з `dock` у кодах, `docks` цілком (малий); `maintenance` — заявки й обладнання з кодів; `people`
   — співробітники `OP-*` з кодів центрів; `quality` — цілком, якщо є події `quality.check`; `chains` —
   якщо змінилось хоч одне МО/переміщення — `sheet_chain`, `ship_chain`, `material_paths`, `full_cycle_mo`
   цілком і `supply/delivery/components` змінених МО (вони вже в повних записах МО); `signals` — при `kind=signal`
   — `patch.signals = [{path, value}]` для шляхів з `codes` + `meta.iot`. Запис вбудованого розділу в `patch` —
   повний запис власника; opt-ключ власника (Додаток A.3–A.11, напр. `blocked`, `reservation_state`, `idle_reason`,
   `maintenance_request`, `current_task`, `reserved_for`), якого в новому записі немає, DeltaBuilder дописує зі значенням
   `null` — так клієнт його прибирає (п. 7).
5. Провайдер без `_f3d_viewer_delta` (`getattr` → `None`; для способу (а) — успадкована реалізація M-01) — дельта за
   замовчуванням `tools.payload.default_delta(p, patch, ctx)`: `tmp = {}`; `collect(tmp, ctx)`;
   `deep_merge(patch, {k: tmp[k] for k in secs if k in tmp})` (M-01, X-23). Розділ понад 200 КБ пропускається з
   `meta.errors` (`"error": "DeltaTooLarge"`).
   **Злиття в `patch` (X-23).** Розділ цілком у `patch` присвоює лише його власник (вбудовані розділи; `yard`,
   `access`, `fire`, `evacuation`, `energy`, `lighting`, `ventilation` — модулі-власники). Будь-який провайдер, що пише в
   чужий або спільний розділ (`infra` — energy 150, genset 155, yard 160, access 170; `workcenters`, `productions`,
   `locations`, `equipment`, `employees`, `zones` — доповнення модулів, A.15), лише доповнює `patch` через
   `deep_merge(patch.setdefault(<розділ>, {}), <свої ключі>)`; присвоєння `patch["infra"] = …` заборонене. Порядок
   провайдерів для результату неважливий: різні провайдери пишуть різні листові ключі. Приклад: energy (150) поклала
   `patch.infra = {"cards": {"PV-INV": {…}}, "totals": {"pv_now": 468}}`, міст genset (155) зливає `{"cards": {"GENSET":
   {…}}, "totals": {"island": false}}` → `patch.infra.cards` має `PV-INV` і `GENSET`, `totals` — `pv_now` і `island`
   (AC-58).
6. `removed`: документи з подій, яких немає в результаті (скасовані/видалені) — за назвами з `codes`.
7. Клієнт (`applyPatch`) зливає дельту **глибоко** (X-23): `deepMerge(D, patch)` — та сама семантика, що `deep_merge`
   (dict — рекурсивно, list/скаляр — заміна), з трьома правилами клієнта: (а) списки записів `productions`, `pickings`,
   `maintenance_requests`, `quality_checks`, `sale_orders`, `purchase_orders` зливаються поелементно за ключем `name`
   (`maintenance_requests` — `id`): наявний елемент — `deepMerge`, новий — додається в кінець; (б) значення `null` у
   записі патча видаляє ключ у `D` (клієнт трактує відсутній ключ і `null` однаково); (в) `signals` — за шляхом, `removed`
   — видалення за ключем. Розділ у `D` цілком не замінюється ніколи: картки `infra.cards`, яких немає в патчі
   (статичні `WIFI`, `SERVER`…), і ключі інших провайдерів у записі (`workcenters[*].machine_state` machine_connect,
   `employees[*].zone` access) лишаються. `meta` — злиття; далі `indexData()` інкрементально (`idx.mo/pick/prodLocs/truck`
   перераховуються лише для змінених), `paint(items.get(code))` для всіх кодів, `updateLive()`, overlay для змінених МО,
   автостарт/автостоп навчання (§8.2 п. 10), `renderPanel(true)` якщо панель показує змінений об'єкт.

### R-15 Коалесценція шини — M-03 `_notify`. Приклад: `action_assign` 12 переміщень в одній транзакції → 3 події (`stock.picking`, `stock.move.line`, `stock.quant`) і 3 повідомлення, не 300.

### R-16 Резолвер (`tools/payload.resolve(env, code=None, name=None)`)

За `code`: по черзі моделі з `f3d.scene.mixin._f3d_resolve_order` base (M-01, R-03; X-85): `f3d.zone`,
`stock.location`, `mrp.workcenter`, `maintenance.equipment`, `hr.employee`, `stock.picking.batch` — список береться з
домішки, а не дублюється у viewer; `env[m].search_f3d(code)` домішки base (M-01: `f3d_code` або `f3d_alias`, 0 або 1 запис; без
`sudo`; модель пропускається, якщо `has_access('read')` хибне); код фури `TRUCK-*` знаходиться тим самим шляхом —
`stock.picking.batch.search_f3d(code)` за `f3d_code` (base CB-06, X-15; поле `f3d_truck` — опис, не код, у пошуку не
бере участі); спеціальні випадки до пошуку: `OP-<wc>` без запису → співробітник оператора
поточного завдання на центрі `<wc>`; `DOCK-W*`/`DOCK-E*` →
локація з цим кодом (ворота); `WO\d{5}` → `mrp.workorder` з `id = int`. За `name`: `mrp.production`,
`stock.picking`, `sale.order`, `purchase.order`, `maintenance.request`, `quality.check` — `search([('name','=',name)],
limit=1)`, моделі, яких немає в `env`, пропускаються. Результат `{model, res_id, display_name, kind}`; `kind` —
з `f3d_kind` домішки або `"document"`.

П. 5 (`codes`, API-04): якщо за `code` нічого не знайдено, а передано `codes` — одним запитом на модель шукаються записи з
`f3d_code ∈ codes` або `f3d_alias ∈ codes` (порядок моделей домішки, ≤ 200, з правами користувача); перша модель, де щось є,
дає `{model, res_id: null, res_ids, kind: "group", count}`; нічого немає — `not_found`. Клієнт (`core.js`, картка 3D-об'єкта)
збирає `codes` так: нащадки об'єкта з кодом живих комірок (`D.locations[c].quants` — масив); якщо їх немає, а об'єкт —
стелаж (`kind = "rack"`), то комірки, чий центр лежить у габариті стелажа (+0,25 м; сцена плоска, ієрархії стелаж→комірка
у GLB немає); інакше комірки з префіксом `<code>-`. Більше 200 кодів — список не пропонується. Кнопка «Відкрити в Odoo»:
показується одразу, якщо дані підказують запис (`D.workcenters|employees|equipment|zones[code]`, жива комірка, фура,
ворота) або є живі комірки всередині; інакше — один `resolve({code})` на картку (результат кешується), кнопки немає, доки
запис не знайдено. Знайдено `res_ids` — `opts.onOpenRecords(model, ids, label)` (дія: список `stock.location` з доменом
`id in ids`); кіоск кнопки не має.

### R-17 Вибір режиму програвання на клієнті

При першому русі повзунка/▶: `client.snapshots(D.meta.now[:10])` → якщо `mode == "snapshots"` і користувач
не обрав `plan` вручну — `snapshots`: для хвилини `m` обирається знімок з найбільшим `ts ≤ day+m`, вантажиться
(кеш), застосовується як повний `D` (без `indexData` для статики), overlay перебудовується; між знімками
точки не інтерполюються (стрибок), стрічка «Потік зміни» будується з подій, записаних у знімок: при створенні знімка `_take`
додає `meta.events = [{ts, model, codes, kind}]` — події `f3d.viewer.event` з часу попереднього знімка, ≤ 500
останніх (M-02).
«Зараз» → останній живий `D` (зберігається окремо `Dlive`). `plan` — алгоритм макета (2301–2345).

### R-18 Lite — §8.4. R-19 Злиття статики й живих даних на клієнті

`merge(static, live)`: `D = structuredClone(static)` без `layout`/`path_templates` (лишаються в `D.static`);
для кожного ключа `live`: якщо значення — dict і в `D` є dict з тим самим ключем серед статичних розділів
(`energy`, `lighting`, `ventilation`, `fire`, `infra`, `evacuation`, `zones`, `docks`) — глибоке злиття
(об'єкти за ключами, скаляри перекривають); інакше — заміна. `meta` = `live.meta` + `static.meta.built_at/static_etag`.
Перевірка: `live.meta.schema.split(".")[0] === "1"` і `static.meta.schema` те саме; інакше `onNotify("Версія
даних … не підтримується переглядачем 1.x", "danger")` і зупинка. Мінорна версія (`1.0`, `1.1`) не перевіряється:
схема 1.x адитивна — ключі модулів (Додаток A.15) і невідомі ключі зберігаються в `D` як є, клієнт читає лише ті, що
знає (X-24).

Правило «вантаж комірок за живими залишками» (`stock_load.js`). Статичний вантаж у GLB (палети ГП, плити, лотки, рулони) —
формула сцени, не залишки. Коли `D.meta.live` і `D.locations[code].quants` — масив, вантаж малюється за ними (без живих
даних — як у GLB): (1) `pallet_cell`: статичний вантаж сховано, N процедурних палет з коробками, N = `min(capacity,
палети)`, палети = різні `package` серед рядків `qty > 0` + рядки без пакета (без пакетів — число рядків, як у `fill` R-04);
(2) `stack|shelf|bin|area|kit`: статичний вантаж видно, лише якщо `Σqty > 0`; якщо `qty > 0`, а статичного вантажу в сцені
нема, — узагальнений блок розміром із комірку, висота × `fill` (`fill = null` — повна); (3) прихований вантаж не ламає
вибір: на комірку ставиться невидимий об'єм (у режимах кольору й виборі він тонується); (4) картка комірки замість
статичного `desc` показує «За Odoo: N палет · товари» або «Порожньо»; (5) правило застосовується після кожного
`setData`, `applyPatch` (`locations`), знімка, «Зараз» і появи частини моделі; палети й блоки — спільна геометрія та
`InstancedMesh` по шарах моделі (вмикання шару ховає й процедурний вантаж).

### R-20 Кешування статики й частин

`ETag` статики = `sha1(вміст файлу)`; `manifest.parts[].hash` = `sha1(glb)[:12]`; URL `?v=hash`;
клієнт зберігає `etag` у `localStorage`; `BUILD.json.built_at` показується в «Огляд → Дані» («асети зібрано …»).

### R-21 Знімок — вибір часу

Крон о `HH:MM` у вікні → знімок; якщо `snapshot_hours` порожній — завжди. `shift_date` = дата `ts` за Києвом.

### R-22 Заявки ТО в картці: статус, посилання, «Запланувати ТО» (API-11)

- **Запис заявки** (`maintenance_requests[]`, провайдер M-01e) додатково має `res_id` (id запису; `id` = `name`, а назви
  в демо однакові — «Планове ТО», тож клієнт шукає заявку за `res_id`, а злиття delta — за `res_id`, якщо він є),
  `equipment_name`, `done` (стадія `done`) і `overdue_days` — лише для відкритої заявки з `schedule_date < ctx.now`:
  різниця календарних днів за Києвом (`0`, якщо прострочено сьогодні). Рядок обладнання й центру: `maintenance_request_id`.
  Так само `maintenance_request_id` (id тієї ж заявки, що й `maintenance_request`) віддають вентустановки
  (`ventilation.units[*]`, factory3d_bms R-27) і групи пожежної сигналізації (`fire.groups[*]`, factory3d_fire_safety R-20);
  клієнт знаходить їхню заявку за цим id (`mrOf`), за назвою — лише коли id немає. У delta ці провайдери (повний розділ у `patch`)
  самі дописують `maintenance_request` і `maintenance_request_id` зі значенням `null`, коли заявки більше немає.
- **Пілюля** у картках обладнання, робочого центру, вентустановки й групи пожежної сигналізації:
  `<тема> · <обладнання> · <стадія> · <ДД.ММ>[, прострочено N дн.]` (дата — `schedule_date`, інакше `request_date`), поруч —
  кнопка «Відкрити заявку в Odoo» (`onOpenRecord("maintenance.request", res_id)`; у кіоску й без `res_id` її немає).
- **«Запланувати ТО»**: `equipment[code].maintenance_due` ставиться, якщо відкритих заявок на обладнання немає й наступна
  планова дата (поле `next_action_date`, якщо воно є в базі, інакше остання закрита повторювана профілактична заявка +
  `repeat_interval × repeat_unit`, з урахуванням `repeat_until`) минула (`overdue`) або настане за ≤ 7 днів (`soon`). Кнопка є лише
  при `meta.live`, не в кіоску. Delta скидає `maintenance_request*`, `maintenance_due`, `next_maintenance`, `overdue_days` у `null`,
  коли їх більше немає.
- **API-11**: перевірки по порядку — кіоск → `403 kiosk`; немає групи переглядача або права `create` на `maintenance.request`
  → `403 forbidden`; невалідні параметри → `400`; обладнання з `f3d_code` немає або недоступне → `404`. Далі advisory-lock
  на обладнання; якщо є відкрита (стадія не `done`, не в архіві) профілактична заявка — повертається вона (`created=false`).
  Інакше створюється `maintenance.request`: `maintenance_type=preventive`, `name="Планове ТО · <обладнання>"`,
  `schedule_date` = наступна планова дата о 08:00 за Києвом (інакше поточний час), `maintenance_team_id` й `user_id` — з
  обладнання (команда — за замовчуванням Odoo, якщо в обладнання її немає; без жодної команди — `400 no_team`).

### R-23 Документи в картках: стан-бейдж і посилання на форму Odoo

Скрізь, де картка називає документ, поруч стоїть бейдж його стану (клас `o_f3d_pill`, як «Готово» у «Документ на воротах»),
а назва відкриває форму Odoo (`client.resolve({name})` → `onOpenRecord`; у кіоску — лише текст і бейдж). Назва документа —
`^(?:[A-Z][A-Z0-9]{0,5}/){1,3}\d{3,}$` (`WH/IN/00128`, `WH/INT/00061`, `QC/00413`); у вільному тексті (нотатки кроків,
`supply.note`, `delivery.note`, `loc.note`, `q.note`, `p.note`, `p.origin`, `c.expected`) такі назви знаходяться регулярним
виразом і розмічаються самі. Джерело стану (клієнт, `docInfo(name)`): `pickings[].state` → `quality_checks[].state` →
`productions[].state` → `productions[].supply|delivery.docs[name]`. Мітки (`format.js`): `stock.picking`
`draft/waiting/assigned/done/cancel` = Чернетка / Очікує / Готово / Виконано / Скасовано; `quality.check.quality_state`
`none/pass/fail` = Очікує / Пройдено / Брак; `mrp.production` `draft/confirmed/progress/done/cancel` = Чернетка /
Підтверджено / У роботі / Виконано / Скасовано; невідомий стан — сірий бейдж із сирим текстом. Провайдер `chains` для назв у
кроках `supply|delivery`, яких немає в payload (напр. внутрішнє переміщення `WH/INT/00061` у нотатці контролю плит), одним
запитом на модель (`stock.picking`, `mrp.production`, `quality.check`; з правами користувача) додає
`supply.docs` / `delivery.docs` = `{назва: {"kind": "picking|production|quality", "state"}}` (нормалізований стан: picking
`confirmed → waiting`, МО `to_close → progress`); у дельті — разом із `supply`/`delivery` змінених МО. Назва — `span[role=link]`
(не `button`: вона може стояти всередині рядка-кнопки, а вкладений `button` HTML не допускає), Enter = клік.
QC-посилання (`QC/…`) у рядку кванта («брак QC/00412»), червоному блоці комірки карантину, «Потребує уваги» і кроку «Контроль»
шляху плити відкривають `quality.check` і показують `quality_state`.

### R-24 Історія комірки (API-12)

Картка 3D-об'єкта, якому відповідає `D.locations[code]`, під таблицею залишків показує блок «Рух по комірці» з API-12
(кіоск його не показує). Клієнт: `DataClient.locHistory(code)` (`null` для `404`), кеш `locHist[code]`; запит іде при
відкритті картки; жива дельта, що зачепила `locations | pickings | productions | quality_checks` (або `full`), позначає
кеш застарілим, і відкрита картка перечитує його (запит не частіше одного одночасно; якщо дельта прийшла під час запиту —
повторно через 0,7 с); страховка — кеш старіший 60 с. `/data` і `/delta` не змінюються. Сервер
(`tools/loc_history.build`, одна вибірка на вид, ліміти `LIMIT_QUANTS = 50`, `LIMIT_DONE = 300`, `LIMIT_OPEN = 200`,
`truncated` — якщо хоч одна вперлась у ліміт; по ≤ 10 записів кожного виду на товар/партію):
1. Рядки = квант `stock.quant` комірки (товар, партія): залишок і резерв. Товар без залишку з'являється, якщо має відкритий рух
   із/у комірку.
2. `arrived` — останні (≤ 3, новіші першими) виконані `stock.move.line` з `location_dest_id = комірка` для цього товару й
   партії: документ (`picking`, інакше МО, утилізація, «Інвентаризація», інакше `reference`), дата, кількість (в од. виміру
   товару), звідки.
3. `reserve` — відкриті рядки `stock.move.line` з `location_id = комірка`, `quantity > 0`, стан не `done/cancel`: документ,
   кількість, куди.
4. `out` (на рівні товару: рух не прив'язаний до партії) — відкриті `stock.move` з `location_id = комірка`,
   `location_dest_id ≠ комірка`, стан `confirmed/waiting/partially_available`, ще не зарезервована частина
   (`product_qty − Σ рядків`); документ, що вже є в `reserve` того ж товару, зливається в той запис (`pending` = залишок) і в
   `out` не дублюється.
5. `incoming` (на рівні товару) — відкриті `stock.move` з `location_dest_id = комірка`, `location_id ≠ комірка`, стан не
   `done/cancel`: документ, кількість, звідки, планова дата.
Кожен `doc` з `model`/`id` на клієнті — посилання на форму (`data-rec="model:id"` → `onOpenRecord`) і бейдж стану (R-23).

## 10. Стани й переходи

| Об'єкт | Стани | Переходи / джерело |
|---|---|---|
| `pickings[].state` | `draft`, `waiting`, `assigned`, `done` (`cancel` не віддається) | `stock.picking.state`: `confirmed|waiting → waiting` (R-09) |
| `productions[].state` | `confirmed`, `progress`, `done` | `mrp.production.state`: `draft→confirmed`, `to_close→progress` |
| `workorders[].state` | `pending`, `ready`, `waiting`, `progress`, `done` + `blocked` | R-07: похідні від `mrp.workorder.state` і `working_state` |
| `workcenters[].status` | `work`, `idle`, `stop` | R-06: `blocked→stop`, є завдання `progress`→`work`, інакше `idle` |
| `locations[].state` | `ok`, `low`, `out` | R-04 |
| `equipment[].state` | `busy`, `charging` | сигнал `drain` (`x_charging`) або статика |
| `f3d.demo.wizard.state` | `draft → queued → running → done \| error`; `error → draft` (повторний запуск після виправлення) | `action_run`, `_cron_run` |
| `f3d.demo.wizard.step.state` | `todo → running → done \| skipped \| error` | `_cron_run` |
| `f3d.viewer.snapshot.kind` | `periodic`, `event`, `install`, `manual` | крон, `_notify` при `maintenance` з `kind=maintenance` і `stage` «В роботі» на робочому центрі (`event`: «Зупинка CNC-2 · MR/00031»), `post_init`, кнопка «Зробити знімок» у списку (`manual`) |
| `DataClient.state` | `loading → live`; `live ↔ polling` (шина впала/відновилась або `bus=false`); `* → offline` (мережі немає) → `loading` при відновленні | §8.3 |
| Клієнт: `panel.type` | `tab`, `object`, `mo`, `product`, `picking`, `line`, `drill` | як у макеті (1382–1410) |
| Клієнт: програвання | `live` (`simOverride=null`), `scrub` (повзунок), `play` (таймер 5 хв/250 мс) × режим `plan|snapshots` | R3, R-17 |

## 11. Обробка помилок

| Ситуація | Поведінка сервера | Поведінка клієнта |
|---|---|---|
| Провайдер кинув виняток | savepoint відкочується, розділ лишається попереднім, `meta.sections[k]="error"`, `meta.errors[]`, лог `factory3d_viewer` рівня ERROR з traceback | у «Огляд → Дані» банер «Розділ … недоступний (помилка модуля …)»; решта працює |
| Моделі `sale.order`/`purchase.order`/`quality.check`/`x_f3d_signal` немає | розділ порожній, `sections[k]="missing"` | вкладки працюють без цих даних (макет уже перевіряє наявність) |
| Немає прав на модель | `sections[k]="denied"` | те саме + підказка «Немає доступу до …» у картці |
| Провайдер за префіксом без `_f3d_viewer_collect` / без інших атрибутів (X-22) | `getattr` з умовчаннями M-01; без `collect` — пропуск і WARNING у лог; без `_f3d_viewer_delta` — дельта за замовчуванням R-14 п. 5 | — |
| `_f3d_group` провайдера — xml-id групи, якої немає в базі (модуль-власник групи не встановлено) | провайдер пропускається, розділи `denied` (R-01 п. 4) | як «немає прав» |
| `since` застарів / >2 000 подій | `{"full": true}` | повне перечитування `/data` |
| Шина недоступна (websocket) | — | `polling` кожні 30 с, індикатор червоний «немає зв'язку», після відновлення — негайний delta |
| `/delta` 5×× | лог | експоненційний відкат 2…60 с; у кіоску після 5 помилок — `location.reload()` |
| Мережа відсутня (`navigator.onLine=false`) | — | банер, дані лишаються, таймери зупинені |
| `code` невалідний | `400 bad_request` | не трапляється (клієнт валідує тим самим regex) |
| Запису немає для коду | `200 {model: null, reason: "not_found"}` | повідомлення «У базі немає запису з кодом …» |
| Токен кіоска невірний / кіоск вимкнений | `404` без тіла | — |
| Перевищено 10 req/s на IP (кіоск) | `429` | клієнт збільшує інтервал удвічі |
| GLB частина не завантажилась | — | як у макеті: `partState.delete`, повтор при наступному зверненні; `core` — повідомлення «Не вдалося завантажити модель» |
| WebGL недоступний | — | нульовий рендерер (§8.7) + банер «3D недоступне на цьому пристрої — показано лише дані» |
| Версія схеми не 1.x | — | зупинка з повідомленням (R-19) |
| `demo_clock` невалідний | `now()` ігнорує параметр, лог WARNING | — |
| Часові пояси | усі обчислення в UTC, рендер за Києвом; `since` — UTC; `today` — за Києвом (крон о 02:30 UTC+2/+3 — у XML `nextcall` ставиться в UTC, DST враховує `ir.cron` стандартно: інтервал 1 день від `nextcall`) | клієнт не конвертує (рядки як є), `Date.parse` лише для різниць у хвилинах |
| Дублікати кодів (два записи з одним `f3d_code` у різних моделях) | резолвер — перший за порядком R-16; payload — локація виграє у `locations`, центр у `workcenters` (різні розділи, конфлікту немає) | — |
| Два користувачі з різними правами на одному кіоску | неможливо: кіоск завжди `user_kiosk` | — |
| Демо-майстер на проді | `UserError` FR-35 | — |
| Майстер: крок упав | крок `error`, решта обраних **не** виконуються (порядок залежний), `state=error`, лог з класом винятку й текстом (без SQL) | — |

## 12. Acceptance Criteria

Формат: Given / When / Then; тип перевірки UT / HT / JT / MAN; посилання на FR.

| ID | FR | Given | When | Then | Тип |
|---|---|---|---|---|---|
| AC-01 | FR-01 | модуль встановлено, користувач у `group_f3d_user` | відкриває меню «Завод 3D → Переглядач» | виконується `ir.actions.client` з `tag="f3d_viewer.action"`, у DOM є `.o_f3d_viewer canvas` і `.o_f3d_card` | HT |
| AC-02 | FR-02 | дія з `params={"code":"SAW-1","tab":"production","mode":"oee"}` | `applyParams` | `getState()` = `{selected:"SAW-1", tab:"production", mode:"oee"}`; з `code:"NOPE"` — повідомлення `warning`, `selected=null`, дія відкрита | JT |
| AC-03 | FR-03 | бандл `static/lib/three/three-bundle.esm.js` у модулі | `mount()` | жодного запиту на хост поза `window.location.origin` (перехоплення `fetch`/`import` у HOOT); `THREE.REVISION === "160"` | JT |
| AC-04 | FR-04 | `GET /factory3d_viewer/static/model/parts/core.glb` | перший і повторний запит з `If-None-Match` | 200 з `ETag`, потім 304; `manifest.parts[0].file` містить `?v=` з 12 hex | HT |
| AC-05 | FR-05 | `mount()` | завершення | `items.has("SAW-1")` одразу після `core`; `items.has("RV-05")` лише після `loadPart("engineering")`; `setLayer("fire", true)` вантажить `fire` | JT |
| AC-06 | FR-06 | `demo_payload.json` як дані | 23 сценарії реєстру R1–R23 (по одному JT на рядок) | DOM/стан збігаються з очікуваними в тесті (деталі §13.1 JT-таблиця) | JT |
| AC-07 | FR-07 | GLB з `status=work` для `CNC-2`, payload з `workcenters["CNC-2"].status="stop"` | `buildLabels`, `renderObject("CNC-2")` | підпис з крапкою `--bad`, чип «Зупинено» | JT |
| AC-08 | FR-08, FR-23 | обрано `SAW-1` | клік «Відкрити в Odoo» | `onOpenRecord("mrp.workcenter", id)`; для коду без запису — `onNotify(..., "info")` | JT, HT |
| AC-09 | FR-09 | `document.documentElement.dataset.theme="dark"` | `applyTheme` | `scene.background` = значення `--f3d-scene` темної теми; при ширині 360 px `#side` прихований, `#card` внизу | JT |
| AC-10 | FR-10 | користувач `group_f3d_user` | `GET /f3d/viewer/static` двічі з `If-None-Match` | 200 з `ETag`, тіло має ключі `passports`, `energy`, `layout`, `path_templates`, `meta.schema="1.1"`; друга — 304 | HT |
| AC-11 | FR-11 | демо-база | `GET /f3d/viewer/data?full=1` | перші 26 ключів — базові ключі Додатка A.0 у тому ж порядку (без модулів-провайдерів інших ключів верхнього рівня немає), `meta.schema="1.1"`; `tools.cycle_check.check(payload) == []`; кожен запис відповідає типам Додатка A (валідатор у тесті) | HT |
| AC-12 | FR-12 | тестовий провайдер `f3d.viewer.provider.zz_test` з `_f3d_sequence=5` і `_f3d_sections=("zones",)` у тестовому модулі | `PayloadBuilder.build()` | порядок виклику: `zz_test` першим, далі `stock`(20)…`signals`(90); `meta.sections.zones="live"` | UT |
| AC-13 | FR-13 | тестовий провайдер, що кидає `ValueError` | `build()` | відповідь є, `meta.sections.<k>="error"`, `meta.errors[0].provider` = його `_name`, `error="ValueError"`, інші розділи заповнені; текст винятку в `meta` відсутній | UT |
| AC-14 | FR-14 | користувач без `mrp.group_mrp_user` | `/data` | `productions=[]`, `workorders={}`, `workcenters={}`, `sections.productions="denied"`; grep `sudo(` у `tools/` і `controllers/` дає лише `ir.config_parameter.sudo()` і `with_user` у `kiosk.py` | UT |
| AC-15 | FR-15 | `demo_clock="2026-10-12 10:30"`, завдання `progress` з відкритим рядком продуктивності від 09:58 | `/data` | `meta.now="2026-10-12 10:30"`, `workorders[...].duration=32`; з порожнім `demo_clock` — `meta.now` = зараз ±1 хв | UT |
| AC-16 | FR-16 | після `/data` змінити `stock.quant` у `PLT-04C` | `/delta?since=<ts>` | `patch.locations["PLT-04C"].quants` оновлені, інших локацій немає; `since` 3 доби тому → `{"full": true}` | UT, HT |
| AC-17 | FR-17 | `x_f3d_signal` `energy/consumers/SAW-1/p_now=13.1`, `equipment/FL-1/battery=57.1 (%)`, `x_mode=drain, x_charging=True` | `/data` | `energy.consumers["SAW-1"].p_now=13.1`, `equipment["FL-1"].battery=0.571`, `equipment["FL-1"].state="charging"`, `meta.iot.signals=196` | UT |
| AC-18 | FR-18, FR-26 | в одній транзакції `action_assign` на 12 переміщеннях | commit | у `f3d.viewer.event` ≤ 3 рядки (`stock.picking`, `stock.move.line`, `stock.quant`), `bus.bus` отримав ≤ 3 повідомлення каналу `f3d_viewer` з `kind`, `codes`, `ts` | UT |
| AC-19 | FR-19 | 5 повідомлень шини за 500 мс | `DataClient` | один `GET /delta` через 1,5 с з об'єднаними `codes`; друге повідомлення під час польоту → ще один запит після відповіді | JT |
| AC-20 | FR-20 | крон сигналів, `x_updated` змінився у 3 сигналів | `_cron_signal_bus` | одна подія `kind=signal`, `codes` = 3 шляхи; повторний запуск без змін — подій немає | UT |
| AC-21 | FR-21 | емуляція `BUS:DISCONNECT` | 30 с | `client.state="polling"`, індикатор `.off` з текстом «немає зв'язку», `GET /delta` раз на 30 с; `BUS:RECONNECT` → `live` і негайний delta | JT |
| AC-22 | FR-22 | 3 форми документів (V-08a `mrp.production`, V-08b `stock.picking`, V-09 `sale.order` у містку) і 6 форм носіїв домішки (`stock.location`, `mrp.workcenter`, `maintenance.equipment`, `hr.employee`, `f3d.zone`, `stock.picking.batch`) | відкрити форму запису | на формах документів кнопка `button[name=action_f3d_show]` (viewer) видима для `group_f3d_user`, невидима без групи і при `f3d_has_3d=False`; для 6 моделей носіїв модуль `factory3d_viewer` не має жодного успадкованого `ir.ui.view` (`ir.model.data` модуля з `model='ir.ui.view'` → `model` представлення ∉ 6 моделей) — кнопки там лише з base CB-02 (X-08); клік по кнопці base у шапці відкриває переглядач з `params.code` | HT (тур) |
| AC-23 | FR-22 | форма `WH/MO/00231` | клік «Показати в 3D» | дія `f3d_viewer.action` з `params.mo="WH/MO/00231"`; у переглядачі картка МО, `hl.markers.length ≥ 6` | HT (тур `show_in_3d_tour`) |
| AC-24 | FR-24 | коди `PLT-04C`, `SAW-1`, `FL-1`, `OP-SAW-1`, `Z-CUT`, `TRUCK-IN-1`, `DOCK-W1`, `WO00013`; назви `WH/MO/00231`, `WH/IN/00128`, `S00087`, `MR/00031` | `resolve` | відповідні `model`/`res_id`; `OP-W9` → `not_found`; без прав на `hr.employee` — `OP-SAW-1` → `not_found`; `TRUCK-IN-1` → `stock.picking.batch` через `search_f3d` за `f3d_code` (X-15) | UT |
| AC-25 | FR-25 | `snapshot_hours="06:30-16:00"`, час 10:00 Київ | `_cron_snapshot` | знімок `kind=periodic`, `size_kb` 80…200, payload розпаковується, `cycle_check` OK; о 20:00 — знімка немає; два виклики за 30 с — один знімок | UT |
| AC-26 | FR-27 | 5 знімків на 2026-10-12 | `API-05` | `mode="snapshots"`, 5 елементів; клієнт при `setSimTime(600)` застосовує знімок `ts ≤ 10:00`; 2 знімки → `mode="plan"` | UT, JT |
| AC-27 | FR-28 | знімки й події 15 днів тому | `_cron_rotate` | видалено, `kind=install` лишився; список «Знімки» показує `size_kb` | UT |
| AC-28 | FR-29 | правильний токен | `GET /f3d/kiosk/<token>?tab=production` без сесії | 200 HTML без `o_navbar`/`o_main_navbar`, є `#f3d-kiosk[data-token]`; невірний токен → 404; `kiosk_enabled=False` → 404 | HT |
| AC-29 | FR-30 | кіоск | `GET /f3d/kiosk/<token>/data` | `meta.user="Екран цеху (3D)"`, `meta.kiosk=true`, `sale_orders[].amount` відсутній, `productions[].energy_cost` відсутній; `employees` без `email`; жодного `sudo` | HT |
| AC-30 | FR-31 | `lite=1` | `mount()` | `renderer.shadowMap.enabled=false`, `pixelRatio=1`, `scene.environment=null`, `branchParticles` створює 1 частинку, після `load()` завантажено лише `core`+`engineering` | JT |
| AC-31 | FR-32 | `navigator.deviceMemory=4` (мок) | `detectLite()` | `true`; `localStorage.f3d.lite="0"` → `false` | JT |
| AC-32 | FR-33 | кіоск, `fetch` 5× відхиляє | `_delta` | `location.reload` викликано (мок) після 5-ї помилки; `onLine=false` → банер | JT |
| AC-33 | FR-34 | порожня база з `factory3d_base`, `demo_enabled=True` | майстер «усі кроки» | `state=done`, 35 кроків `done|skipped` (`views`, `iot_module` — `skipped`), `cycle_check` OK, повторний запуск → `new_records=0` | UT (довгий, тег `f3d_demo`) |
| AC-35 | FR-35 | `demo_enabled=False` | `action_run` | `UserError` з текстом «Заливка демо вимкнена на цій базі»; кнопка `invisible` | UT, HT |
| AC-36 | FR-36 | демо-база | «Перевірка циклу → Запустити» | `state=ok`, `issue_count=0`; після скасування `WH/OUT/00412` — `issues` містить «S00087: немає відвантаження» з посиланням | UT |
| AC-37 | FR-37 | `/static` з `meta.schema="2.0"` (мок) | `load()` | `onNotify(..., "danger")`, панель не рендериться | JT |
| AC-38 | FR-38 | `build_scene.py --embed dist` після W2 | відкрити `dist/index.html` через http.server | ті самі 23 сценарії R1–R23 проходять на `FileClient` (HOOT з `FileClient`) | JT, MAN |
| AC-39 | §2.6 | користувач `user_kiosk` | `POST /web/login` з будь-яким паролем | відмова (пароля немає); `share=False`, `has_group("group_f3d_kiosk")` | UT |
| AC-40 | §2.6 | `code="PLT-04C'; DROP"` | `/resolve` | 400 `bad_request`, жодного SQL з параметром | HT |
| AC-41 | R-05 | `WH/IN/00131` без батча, dest `UNLOAD-2` | `/data` | `pickings[name].dock="DOCK-W2"`, `truck` null; `WH/IN/00128` з батчем `dock_id=UNLOAD-1`, `f3d_code=TRUCK-IN-1`, `f3d_truck="Фура постачальника плит"` → `dock="DOCK-W1"`, `truck="TRUCK-IN-1"` (з `f3d_code`, не з `f3d_truck`, X-15) | UT |
| AC-42 | R-06 | SAW-1: продуктивних 176 хв, `now` 10:30 | `/data` | `oee=0.84`, `productive_minutes=176`, `status="work"`; CNC-2 `blocked` → `status="stop"`, `losses` містить «Поломка 48» | UT |
| AC-43 | R-07 | МО `confirmed` з `reservation_state=confirmed` | `/data` | `reservation_state="waiting"`, перше завдання `waiting`, друге `pending`; `progress=0.0` | UT |
| AC-44 | R-10…R-12 | `WH/MO/00231` | `/data` | `supply.steps[0].code="GATE-W"`, є `UNLOAD-1`, `QC-PLT-1`, стелаж `RCK-*`, стос `PLT-*`; `delivery.steps[-1].code="GATE-E"`; компонент `FUR-CF-750`: `kind="фурнітура"`, `to` ∈ `ASM*`, шлях містить `KIT-*` і `TUGGER-1` | UT |
| AC-45 | R-13 | демо-база | `/data` | `sheet_chain.steps` 5 кроків з непорожніми `codes`, `path` 6 точок; `material_paths` 6 видів; `full_cycle_mo` — МО з `TRUCK-IN*` і `TRUCK-OUT*` | UT |
| AC-46 | R-14 | завершити завдання `WO00013` | `/delta` | `patch.workorders.WO00013.state="done"`, `patch.workcenters["SAW-1"]`, `patch.productions[0].name="WH/MO/00231"`, `patch.sheet_chain` присутній | UT |
| AC-47 | R-19 | `static` з `energy.consumers.SAW-1.p_inst=24`, `live` з `energy.consumers.SAW-1.p_now=13.1` | `merge` | `D.energy.consumers["SAW-1"] = {…p_inst:24, p_now:13.1}` | JT |
| AC-48 | API-09 | 11 запитів за 1 с з одного IP до `/f3d/kiosk/<token>/delta` | — | 11-й → 429 | HT |
| AC-49 | M-07 | `maintenance.request` змінює стадію на «В роботі» для `CNC-2` | commit | подія `kind=maintenance`, `codes ⊇ {"MR/00031","CNC-2"}`; знімок `kind=event` з `note` «Зупинка CNC-2 · MR/00031» | UT |
| AC-50 | §4 | `group_f3d_manager` без `group_f3d_admin` | `/f3d/kiosk` URL у налаштуваннях | поле порожнє; `action_f3d_new_kiosk_token` → `AccessError` | UT |
| AC-51 | §8.7 | `testMode=true` | `mount()`+`load()` | `getState().renderer="null"`, панель «Огляд» має 4 `.o_f3d_kpi`, `select("SAW-1")` відкриває картку | JT, HT |
| AC-52 | §2.7 | демо-база | `/data` (жива частина) | ≤ 1,5 с і ≤ 80 запитів (`assertQueryCount`), gzip ≤ 200 КБ; `/static` ≤ 100 мс другий раз; `/delta` з 50 кодами ≤ 300 мс | UT (`test_perf`) |
| AC-53 | §5.4 | свіжа копія демо-бази | встановлення модуля | `post_init` лог містить «знайдено записів», параметри `demo_enabled=True`, `demo_clock` задано, знімок `install` 1, крон сигналів активний | UT |
| AC-54 | V-01 | користувач без `group_f3d_manager` | меню | «Журнал станів», «Перевірка циклу» відсутні; без `group_f3d_admin` — «Демо-дані», «Налаштування переглядача» відсутні | UT |
| AC-55 | A-17 | `sale` встановлено | список модулів | `factory3d_viewer_sale` `installed` автоматично; кнопка на `S00087` відкриває дію з `params.mo` | UT, HT |
| AC-56 | FR-42, M-01, R-14 (X-82) | `from odoo.addons.factory3d_viewer.tools.payload import deep_merge` | (1) `deep_merge({"cards": {"PV-INV": {"rows": [1]}}, "totals": {"pv_now": 468}}, {"cards": {"GENSET": {"rows": [2]}}, "totals": {"island": False}})`; (2) `deep_merge({"a": [1, 2]}, {"a": [3]})`; (3) `deep_merge({"a": {"x": 1}}, {"a": 5})`; (4) `deep_merge({"a": 1}, {"a": None})`; (5) `d = deep_merge({}, src)`, потім змінити `src["k"]["n"]`; (6) `deep_merge([], {})` | (1) результат має обидві картки й обидва ключі `totals`, повернуто той самий об'єкт `dst`; (2) `{"a": [3]}` (список замінено, не доповнено); (3) `{"a": 5}`; (4) `{"a": None}`; (5) `d` не змінився; (6) `TypeError` | UT |
| AC-57 | FR-43, M-01, R-01 (X-22, X-27) | тестовий модуль: `f3d.viewer.provider.zz_duck` — `AbstractModel` за префіксом **без** `_inherit`, `_f3d_sequence=152`, без `_f3d_viewer_delta` і `_f3d_viewer_bus_models` | `PayloadBuilder.build()` | `zz_duck` викликано: `infra.cards["ZZ-DUCK"]` і ключ `zz_duck` у payload, `meta.sections.infra="live"`; порядок виклику — `stock` 20, `production` 30, `logistics` 40, `quality` 45, `maintenance` 50, `people` 60, `chains` 70, `signals` 90, `zz_duck` 152; `"f3d.viewer.provider" not in type(env["f3d.viewer.provider.zz_duck"])._inherit`; провайдер з `_f3d_group` неіснуючої групи — пропущено, розділи `denied` | UT |
| AC-58 | FR-42, R-14 п. 5–7 (X-23) | `patch = {"infra": {"cards": {"PV-INV": {"rows": [["Зараз", "468 кВт"]]}}, "totals": {"pv_now": 468}}}` (як після energy 150); `ctx.changes` з будь-якою подією | `DeltaBuilder` викликає `zz_duck` (дельта за замовчуванням) | `patch.infra.cards` має `PV-INV` і `ZZ-DUCK`, `patch.infra.totals.pv_now=468` (не затерто). JT: `D.infra.cards` зі статичними `WIFI`, `SERVER`; `applyPatch` з цим `patch` → `WIFI`, `SERVER`, `PV-INV`, `ZZ-DUCK`; `D.workcenters["SAW-1"].machine_state="work"` лишається після патча `workcenters["SAW-1"]` без цього ключа; патч `{"workorders": {"WO00051": {"blocked": null}}}` прибирає `blocked`; патч `productions` з одним МО зливається за `name`, решта МО на місці | UT, JT |
| AC-59 | FR-11, FR-37, R-01 п. 6, Додаток A (X-24) | тестовий модуль `zz_duck` (додає ключ верхнього рівня `zz_duck`) | `/data?full=1` | `list(payload)[:26]` = порядок A.0, `list(payload)[26:] == ["zz_duck"]`; `meta.schema="1.1"`; `assertPayloadSchema` приймає payload з доданими ключами A.15 (`workcenters["SAW-1"].machine_state`, `infra.totals.island`, `fire.panel`) і відхиляє payload, де `zz_duck` стоїть перед `passports` | UT |
| AC-60 | FR-44, §4.4, R-07 (X-25) | `user_f3d` (stock + mrp), `factory3d_energy` не встановлено | `/data` | у `productions[*]` є `energy_kwh` (`WH/MO/00231` → 86.2), ключа `energy_cost` немає; мок: група `factory3d_energy.group_f3d_energy_cost` існує й користувач у ній → `energy_cost=724`; та сама група + `kiosk=True` → ключа немає | UT |
| AC-61 | FR-41, M-01g, R-13 (X-29) | демо-база з 45 активними `f3d.zone` (base Додаток C.1 + C.2) | `/data?full=1` | `len(zones)==45`; `zones["Z-YARD-W"]`: `zone_type="outdoor"`, `polygon` == `f3d.zone.polygon`, `locations=[]`, `workcenters=[]`; `zones["Z-ROOF"].is_roof=true`; у `zones["Z-CUT"]` ключа `is_roof` немає. JT: `D.static.layout.zones` без `Z-YARD-W`; після `load()` контур `Z-YARD-W` побудовано з `polygon`; `Z-ROOF` видимий лише з шаром `roofdeck` | UT, JT |
| AC-62 | FR-39, §8.2 п. 10 (X-28, fire Q-09) | `D.evacuation.drill_active=null`, `fire.groups["FA-CUT"].state="ok"` | `applyPatch({"evacuation": {"drill_active": {"name": "DRILL/2026/0003", "zone_code": "FA-CNC", "elapsed_s": 40}}, "fire": {"groups": {"FA-CUT": {"state": "alarm"}}, "devices": {"2.CNC.05": {"type": "smoke", "x": 75.0, "y": 20.0, "z": 8.6, "zone": "Z-CNC", "state": "alarm", "dust": 0.12}}}})`, далі `applyPatch({"evacuation": {"drill_active": null}})` | після першого: `startDrill` викликано, `getState().panel="drill"`, час сценарію ≥ 40 с; `FA-CUT` — клас `--bad`, чип «Тривога» (`fault` → «Несправність» червоним, `prealarm` → «Передтривога» жовтим); маркер `2.CNC.05` у шарі `fire`; після другого — `stopDrill` викликано; ручна зупинка при активному навчанні з тим самим `name` — повторного автостарту немає | JT |
| AC-63 | FR-40, §8.2 п. 11 (X-28, access CA-05) | `D.employees["OP-SAW-1"]` з `present: true`, `zone: "Z-CUT"`, `zone_since: "2026-10-12 07:02"`, `last_event: {"ts": "2026-10-12 06:58", "door": "KPP-IN", "direction": "in", "type": "pass"}`; `D.zones["Z-CUT"].people_now=6` | `select("OP-SAW-1")`, потім `select("Z-CUT")` | картка людини: «На території: так», «Зона: Розкрій з 07:02», «Останній прохід: 06:58 · KPP-IN · вхід»; картка зони: «Людей зараз: 6»; без цих ключів (access не встановлено) — рядків немає | JT |
| AC-64 | V-01 (X-30) | модуль встановлено | читання `ir.ui.menu` | `menu_f3d_viewer` (батько `factory3d_base.menu_f3d_root`) sequence 10, `menu_f3d_journal` 12, `menu_f3d_cycle_check` 14, `menu_f3d_demo` 16 — усі пункти viewer у корені в діапазоні 10–19; `menu_f3d_settings` — батько `factory3d_base.menu_f3d_config`, sequence 10, група `group_f3d_admin`; серед дітей `menu_f3d_root` рівно один пункт «Налаштування» (`factory3d_base.menu_f3d_config`) | UT |
| AC-65 | R-04, M-01a (X-14) | `PLT-04C` з `f3d_loc_kind='stack'`, `f3d_capacity=60`; `KIT-01` з порожнім `f3d_loc_kind` і `f3d_capacity=0` | `/data` | `locations["PLT-04C"]`: `kind="stack"`, `capacity=60`; після `f3d_capacity=80` → `capacity=80`, `fill` перераховано; `KIT-01`: `kind`, `capacity` — зі статики (`"kit"`, `null`); grep `f3d_kind_loc` у `models/`, `tools/` — 0 збігів | UT |
| AC-66 | M-01f, §4.4 (X-09) | `user_mrp_only` (без `hr.group_hr_user`), співробітник `OP-SAW-1` | `/data` | `employees["OP-SAW-1"]` = `{name, job, department, shift, workcenter, current_workorder}` без `AccessError`; `search_read` провайдера `people` викликано на `hr.employee.public` (`patch.object`), не на `hr.employee`; `sudo` не викликався (AC-14) | UT |
| AC-67 | M-10, §4.3 (X-19) | модуль встановлено | читання груп | `group_f3d_kiosk.privilege_id` = `factory3d_viewer.privilege_f3d_viewer`; його `category_id` = `factory3d_base.module_category_factory3d`, `sequence=10`; група кіоска не в `factory3d_base.privilege_f3d`; `implied_ids` = 4 групи §4.3 | UT |

(AC-34 навмисно немає — об'єднано з AC-33.)

## 13. План тестування (для Opus)

### 13.0 Фікстури (`tests/common.py`)

`F3dViewerCase(TransactionCase)`, теги `post_install`, `-at_install`, `f3d`, `f3d_viewer`. `setUpClass`:
- припускає базу з демо (CI: копія бази `odoo` тестового сервера з встановленими `factory3d_base`,
  `factory3d_iot_sim`; локально — `--test-tags` на цій копії); якщо `self.env.ref("factory3d_base.…")`
  немає — `skipTest`;
- користувачі: `user_f3d` (`group_f3d_user` + `stock`/`mrp` user), `user_stock_only`, `user_mrp_only`,
  `user_manager` (`group_f3d_manager`), `user_admin` (`group_f3d_admin`), `user_nobody` (лише `base.group_user`),
  `user_kiosk` = `env.ref("factory3d_viewer.user_kiosk")`;
- `self.payload(user, **kw) = PayloadBuilder(env.with_user(user), **kw).build()`;
- `self.set_param(key, val)`; `self.demo_clock("2026-10-12 10:30")` у `setUp`;
- `self.events_since(ts)`, `self.bus_messages()` — перехоплення `bus.bus._sendone` через `patch.object`;
- `self.assertPayloadSchema(payload)` — валідатор Додатка A схеми 1.1 (типи, обов'язкові ключі; верхній рівень — 26 ключів
  A.0 у порядку A.0 першими, ключі модулів — лише після них; вкладені ключі A.15 і невідомі вкладені ключі допускаються).

Тестові провайдери для AC-12/13 не можна оголосити у файлі тесту (моделі реєструються лише при
завантаженні модуля), тому вони живуть у допоміжному модулі `odoo_addons/test_factory3d_viewer/` (§0;
`depends: factory3d_viewer`, `installable: True`, не для проду) з трьома провайдерами: `zz_test` (sequence 5,
пише `zones["Z-TEST"]`), `zz_fail` (sequence 6, кидає `ValueError("boom")`, `_f3d_sections=("fire",)`) і `zz_duck`
(sequence 152, спосіб (б) M-01 — за префіксом без `_inherit`, без `_f3d_viewer_delta`/`_f3d_viewer_bus_models`; пише
`infra.cards["ZZ-DUCK"] = {"rows": [["Тест", "так"]]}` через `deep_merge` і ключ верхнього рівня `zz_duck = {"ok": true}`).
Модуль встановлюється лише в CI і на тестовому сервері; тести, що його потребують, роблять `skipTest`,
якщо `f3d.viewer.provider.zz_test` немає в реєстрі.

### 13.1 Юніт-тести (UT/JT) — на кожен AC типу UT/JT

| Файл | Клас | Тест | Фікстури | Що assert |
|---|---|---|---|---|
| `test_install.py` | `TestInstall` | `test_params_on_demo_db` (AC-53), `test_kiosk_user_cannot_login` (AC-39), `test_menus_by_group` (AC-54), `test_menu_sequences` (AC-64), `test_kiosk_privilege` (AC-67) | база демо | параметри; `res.users._check_credentials` кидає `AccessDenied`; `ir.ui.menu._visible_menu_ids`; `parent_id`/`sequence` пунктів V-01; `privilege_id` групи кіоска |
| `test_payload_static.py` | `TestStatic` | `test_static_keys`, `test_static_etag_stable`, `test_schema_version` | файл | ключі Додатка B, однаковий `sha1` при двох читаннях, `meta.schema=="1.1"` |
| `test_payload_stock.py` | `TestStock` | `test_locations_count_689`, `test_quants_plt_04c` (`qty 15, lot, reserved 15`), `test_fill_state_orderpoint` (AC-… R-04: `FUR-R1-S02-L3` ok/0.846), `test_reserved_for_outgoing`, `test_quality_quarantine_qc1`, `test_products_subset`, `test_loc_kind_capacity_from_base` (AC-65) | демо | значення як у `dist/odoo_demo.json` для тих самих ключів |
| `test_payload_production.py` | `TestProduction` | `test_workcenters_35`, `test_oee_saw1_084` (AC-42), `test_cnc2_stop_losses`, `test_workorder_states_derivation` (AC-43), `test_progress_demo_clock` (AC-15), `test_energy_kwh_mo231` (86.2), `test_energy_cost_requires_group` (AC-60: без групи вартості energy ключа немає; з групою 724; кіоск — немає), `test_queue_max_8` | демо, `demo_clock` | рівність із файлом ± 0,01 |
| `test_payload_logistics.py` | `TestLogistics` | `test_dock_from_batch` і `test_dock_from_location` (AC-41), `test_types_mapping` (6 типів, лічильники 13/12/8/4/3/2), `test_progress_lines`, `test_docks_dict_14`, `test_sale_purchase_optional` (мок `env` без `sale.order` → `[]`, `sections.sale_orders="missing"`), `test_note_waiting` | демо | — |
| `test_payload_chains.py` | `TestChains` | `test_supply_mo231` (AC-44), `test_components_paths_kinds` (200 компонентів, усі з `door`, `path[0]=GATE-W`), `test_delivery_fronts_via`, `test_full_cycle_mo` (AC-45), `test_sheet_chain_ship_chain_material_paths`, `test_cycle_check_ok` (AC-11), `test_zones_45_outdoor_polygon_roof` (AC-61) | демо | `tools.cycle_check.check(payload)==[]` |
| `test_payload_signals.py` | `TestSignals` | `test_paths_applied` (AC-17), `test_percent_to_fraction`, `test_drain_state`, `test_meta_iot`, `test_missing_model` | демо + `x_f3d_signal` | — |
| `test_providers.py` | `TestProviders` | `test_order_and_sections` (AC-12), `test_failed_provider_isolated` (AC-13), `test_group_denied` (`_f3d_group` невідомий xml-id → провайдер пропущено з `denied`), `test_sections_filter`, `test_duck_typed_provider_getattr` (AC-57: `zz_duck` без `_inherit` викликано, порядок 20…70, 90, 152), `test_top_level_order_schema_11` (AC-59) | `test_factory3d_viewer` | `meta.sections`, `meta.errors`, `list(payload)` |
| `test_access.py` | `TestAccess` | `test_mrp_denied` (AC-14), `test_stock_denied`, `test_nobody_gets_static_only`, `test_kiosk_user_sections` (AC-29 через `PayloadBuilder` з `kiosk=True`), `test_no_sudo_lint` (grep файлів `tools/*.py`, `controllers/*.py`, `models/viewer_provider.py`: кожне входження `.sudo(` має бути в рядку з `ir.config_parameter`), `test_amount_requires_all_leads`, `test_people_reads_public_without_sudo` (AC-66) | користувачі | — |
| `test_resolver.py` | `TestResolver` | `test_codes` (AC-24, параметризовано 8 кодів), `test_names` (4), `test_not_found`, `test_respects_access`, `test_bad_code_regex` | демо | `model`, `res_id` = `env.ref`/пошук |
| `test_bus.py` | `TestBus` | `test_coalesce_action_assign` (AC-18), `test_workorder_finish_codes`, `test_maintenance_event_snapshot` (AC-49), `test_bus_disabled_param` (події є, повідомлень немає), `test_signal_cron` (AC-20), `test_codes_cap_500` | `patch.object(BusBus, "_sendone")` | кількість і вміст |
| `test_snapshot.py` | `TestSnapshot` | `test_cron_window` (AC-25, `freezegun` недоступний → `patch("...dates.now")`), `test_idempotent_60s`, `test_rotate_keeps_install` (AC-27), `test_list_mode` (AC-26), `test_company_rule`, `test_read_payload_gzip` | — | — |
| `test_delta.py` | `TestDelta` | `test_quant_change_patch` (AC-16), `test_full_when_old_since`, `test_workorder_done_patch` (AC-46), `test_removed_cancelled_mo`, `test_default_delta_deep_merge` (AC-58: `zz_duck` без `_f3d_viewer_delta` → дельта за замовчуванням зливає `infra` через `deep_merge`, ключі energy в `patch.infra` не затерто), `test_opt_key_null` (зниклий `blocked` → `null` у патчі), `test_empty_delta` | демо | ключі `patch`, `removed`, `events` |
| `test_delta.py` | `TestDeepMerge` (`odoo.tests.BaseCase`, без бази) | `test_semantics` (AC-56: 6 випадків), `test_import_path` (`from odoo.addons.factory3d_viewer.tools.payload import deep_merge` — той самий об'єкт, що `tools.payload.deep_merge`) | — | результат і `id(dst)` |
| `test_show_in_3d.py` | `TestShowIn3D` | `test_base_action_opens_viewer` (дія base CB-02 для 6 моделей домішки при встановленому viewer → `tag="f3d_viewer.action"`, `params.code`; viewer метод не перевизначає, X-08), `test_mo_action`, `test_picking_action`, `test_has_3d_compute`, `test_button_in_views` (AC-22: парсинг `arch` — 2 форми документів мають кнопку viewer з `groups`; серед представлень модуля `factory3d_viewer` немає жодного для 6 моделей носіїв) | демо | — |
| `test_kiosk.py` | `TestKiosk` | `test_token_generated_32hex`, `test_new_token_admin_only` (AC-50), `test_kiosk_disabled_param`, `test_kiosk_ctx_hides_costs` | — | — |
| `test_demo_wizard.py` | `TestDemoWizard` (тег `f3d_demo`, повільний, окремий прогін) | `test_blocked_on_prod` (AC-35), `test_steps_default_35`, `test_run_all_on_empty_db` (AC-33: окрема порожня база з `factory3d_base`+`factory3d_viewer`+`factory3d_iot_sim`; перевірка кількостей: 689 локацій, 35 центрів, 32 МО, 199 завдань, 42 переміщення, 6 батчів, 196 сигналів), `test_idempotent_rerun`, `test_demo_steps_diff` (diff `wizard/demo_steps.py` проти `plant/odoo_push.py`+`odoo_flows.py` ≤ 80 рядків, крім шапки) | — | — |
| `test_cycle_check.py` | `TestCycleCheck` | `test_ok_on_demo` (AC-36), `test_issue_after_cancel_delivery`, `test_html_links` | демо | — |
| `test_perf.py` | `TestPerf` | `test_data_time_and_queries` (AC-52, `assertQueryCount(admin=80)` і `time < 1.5`), `test_static_cached`, `test_delta_50_codes`, `test_payload_gzip_size` | демо | пороги §2.7 |
| `static/tests/hoot/core.test.js` | — | `R1…R23` по одному `test()` на рядок реєстру (AC-06), `lite` (AC-30, AC-31), `theme` (AC-09), `params` (AC-02), `status_from_payload` (AC-07), `open_record` (AC-08), `schema_guard` (AC-37), `merge` (AC-47), `null_renderer` (AC-51), `file_client` (AC-38), `apply_patch_deep_merge` (AC-58), `outdoor_zones` (AC-61), `fire_drill_auto`, `fire_states_devices` (AC-62), `access_rows` (AC-63) | `demo_payload.json` + `model_static.json` через мок `fetch`; `testMode=true` | DOM-селектори `.o_f3d_*`, `getState()`, `hl.markers.length`, `prodOv.tracks.length` (30 МО в роботі) |
| `static/tests/hoot/data_client.test.js` | — | `debounce_single_delta` (AC-19), `inflight_again`, `bus_down_polling` (AC-21), `kiosk_reload_after_5` (AC-32), `etag_304_from_storage` | мок `fetch`, мок `bus_service` | кількість викликів `fetch`, `state` |

Приклад очікувань для R-тестів HOOT (витяг): `R10`: після `load()` у `.o_f3d_kpis` 4 елементи, перший
`29/35` (верстатів у роботі), другий — середній OEE `round(Σoee/35·100)%`; тест обчислює очікуване з
фікстури, не хардкодить. `R11`: `.o_f3d_rows li` = 32, перший — `WH/MO/00231` (сортування `progress`
перед `confirmed`, потім назва). `R12`: `showMO("WH/MO/00231")` → `hl.path` не null, маркери = `supply.steps
(6) + workorders (6) + delivery.steps (9)`. `R16`: `showPicking("WH/OUT/00412")` → маршрут `[cells..., Z-OUT-1,
DOCK-E1, TRUCK-OUT-1]`. `R21`: `startDrill()` → `drill.curves.length=32`, маркерів виходів 12.

### 13.2 Стендові сценарії ТК (емулятор `factory3d_iot_sim` + браузер)

| ТК | Передумови | Кроки | Очікуваний результат | Де дивитися |
|---|---|---|---|---|
| ТК-01 Живий прогрес | тестовий сервер, демо, `bus_enabled=True`, переглядач відкритий у двох вкладках | у третій вкладці: Виробництво → `WH/MO/00231` → завдання «Розкрій» → «Готово» | у обох вкладках ≤ 3 с: рядок МО 00231 оновив смугу, `SAW-1` маячок/підпис змінив стан, у шарі замовлень точка МО перемістилась до `EDGE-1` | 3D + вкладка «Виробництво» |
| ТК-02 Зупинка верстата | як ТК-01 | Виробництво → Робочі центри → `CNC-3` → «Заблокувати» з причиною «Поломка» | ≤ 3 с: `CNC-3` червоний, у «Огляд → Потребує уваги» рядок «Присадка ЧПК C — зупинено»; знімок `kind=event` НЕ створюється (без заявки ТО); створити заявку ТО на обладнання `CNC-3` і перевести в «В роботі» → знімок `event` з'явився в «Журнал станів» | 3D, «Огляд», «Знімки» |
| ТК-03 Сигнали IoT | `factory3d_iot_sim` увімкнена, «Оновити зараз» | «Обслуговування → Імітація IoT → Оновити зараз» | ≤ 70 с (крон щохвилини): картка `FL-1` показує новий заряд, `meta.iot.updated` оновився, індикатор «Odoo» показав час | картка `FL-1`, «Огляд → Дані» |
| ТК-04 Приймання на воротах | демо | Склад → Приймання `WH/IN/00131` → додати у батч із доком «Ворота 2» → підтвердити батч | ≤ 3 с: у «Логістика» рядок 00131 показує «Ворота 2», у 3D клік по `DOCK-W2` → «Документ на воротах» 00131 | «Логістика», картка воріт |
| ТК-05 Показати в 3D ×9 | демо | по черзі кнопка на 9 формах (локація `PLT-04C`, центр `SAW-1`, обладнання `FL-1`, співробітник оператор SAW-1, зона `Z-CUT`, батч `TRUCK-IN-1` — кнопки base CB-02; МО 00231, переміщення `WH/OUT/00412`, SO `S00087` — кнопки viewer) | кожна відкриває переглядач з потрібним об'єктом/маршрутом; на формах носіїв — лише кнопки base (шапка й вкладка «Завод 3D»), дубля від viewer немає (X-08); «← Назад» повертає на форму | переглядач |
| ТК-06 Зворотний перехід | переглядач | клік по `SAW-1` → «Відкрити в Odoo»; клік по `RV-05` → «Відкрити в Odoo» | форма робочого центру; для `RV-05` — форма обладнання (після міграції base) | форми |
| ТК-07 Кіоск на планшеті | Samsung Galaxy Tab Active5 Pro, Wi-Fi цеху, URL кіоска з `tab=production&lite=1` | відкрити, 10 хв спостереження; вимкнути Wi-Fi на 1 хв; увімкнути | ≥ 30 кадр/с (Chrome `chrome://` FPS-метр або `getState().fps` — ядро рахує середній FPS за 10 с), без навігації Odoo; банер «немає зв'язку» → зникає, дані оновились | планшет |
| ТК-08 Новий токен | адміністратор | «Новий токен кіоска» | стара адреса → 404 одразу; нова працює | браузер |
| ТК-09 Програвання зміни за знімками | ≥ 3 знімків сьогодні | ▶ у переглядачі | біля часу позначка «знімки», стани на 09:00 відповідають знімку 09:00 (звірити `WO` у «Знімки → відкрити» ) | переглядач, «Знімки» |
| ТК-10 Падіння провайдера | тестовий модуль `test_factory3d_viewer` встановлено (`zz_fail`) | відкрити переглядач | банер «Розділ fire недоступний (помилка модуля f3d.viewer.provider.zz_fail)», решта працює; у логах ERROR з traceback | «Огляд → Дані», лог |
| ТК-11 Демо на чистій базі | нова база, `factory3d_base`, `factory3d_viewer`, `factory3d_iot_sim`, `demo_enabled=True` | «Демо-дані → Запустити всі кроки», чекати | `done`, 33 `done` + 2 `skipped`, `cycle_check` OK, переглядач показує ту саму картину, що `dist/index.html` | майстер, переглядач |
| ТК-12 Прод-режим | `neutralize.sql` застосовано | «Демо-дані», URL кіоска | «Запустити» заблоковано; кіоск 404; крони вимкнені | меню, браузер |

### 13.3 Тести безпеки

- Без групи `group_f3d_user`: `/f3d/viewer/static|data|delta|resolve|snapshots` → 403 (HT `test_controllers.py::test_forbidden_without_group`).
- Без сесії: ті самі → редирект на `/web/login` (303) або 401 для JSON.
- Токен кіоска: невірний/порожній/зі спецсимволами → 404; `compare_digest` (перевірка, що порівняння не через `==` — grep у `kiosk.py`).
- `code`/`codes`/`since`/`date` з ін'єкціями (`' OR 1=1`, `../`, `%00`, 10 000 символів) → 400.
- `sudo`-lint (AC-14), `with_user` лише в `kiosk.py`.
- `sale_orders[].amount` відсутній для кіоска й користувачів без `group_sale_salesman_all_leads`; `productions[].energy_cost` відсутній для кіоска й користувачів без `factory3d_energy.group_f3d_energy_cost` (X-25, AC-60).
- Користувач без `hr.group_hr_user` отримує `employees` без `AccessError` і без `sudo` — читання `hr.employee.public` (X-09, AC-66).
- Шина: повідомлення не містять нічого, крім `model`, `codes`, `kind`, `ts` (UT `test_bus_payload_keys`).
- Стоп-крани: `demo_enabled=False` → `UserError`; `kiosk_enabled=False` → 404; `bus_enabled=False` → події без повідомлень; `neutralize.sql` виконується без помилок на копії бази й дає ці три стани + випадковий токен (UT `test_neutralize_sql`).
- Мультикомпанія: знімок компанії B невидимий користувачу компанії A (`test_company_rule`).

### 13.4 Тести продуктивності

| Тест | Порог | Як міряти |
|---|---|---|
| `/data` жива частина, демо-база (1 434 кванти, 199 завдань, 42 переміщення) | ≤ 1,5 с, ≤ 80 SQL | `test_perf.py`: `time.perf_counter()` навколо `PayloadBuilder.build()`, `self.assertQueryCount(admin=80)` |
| `/data?full=1` | ≤ 2,0 с; gzip ≤ 250 КБ | те саме + `gzip.compress` |
| `/static` | 1-й ≤ 300 мс, 2-й ≤ 100 мс | двічі через `url_open` |
| `/delta` 50 кодів | ≤ 300 мс, ≤ 30 SQL | — |
| ×10 обсяг (скрипт у тесті копіює кванти/завдання ×10 у savepoint) | `/data` ≤ 6 с | тег `f3d_perf_big`, лише вручну |
| Перше відкриття на ПК (Chrome, 20 Мбіт/с throttling) | ≤ 6 с до `modelReady` | MAN, DevTools |
| Планшет lite | ≥ 30 кадр/с, перше відкриття ≤ 12 с | ТК-07 |
| Ротація 300 000 подій | ≤ 60 с | `test_rotate_batches` з 20 000 синтетичних подій, екстраполяція |

### 13.5 Чек-лист DEPLOY_TEST (копія демо-бази)

1. `pg_dump` бази `odoo` тестового сервера → локальна копія; `odoo-bin -d copy -i factory3d_viewer --stop-after-init` без помилок.
2. Лог `post_init`: параметри, знайдені коди, знімок `install`.
3. `odoo-bin -d copy --test-tags /factory3d_viewer --stop-after-init` — усі UT/HT зелені; HOOT — `--test-tags /factory3d_viewer` з `web.assets_unit_tests` (або `odoo-bin … --test-enable --test-tags :TestHoot`).
4. Відкрити переглядач адміністратором: 5 вкладок, 13 видів, шар замовлень, програвання, тривога — ТК-05, ТК-01.
5. Кіоск з токеном — ТК-07, ТК-08.
6. `cycle_check` → OK.
7. `neutralize.sql` на копії → ТК-12; відкат: `pg_restore` копії.
8. Оновлення асетів: змінити `manifest.parts[0].hash` → переглядач вантажить новий URL (DevTools).
9. Деінсталяція: `uninstall_hook` — параметри `factory3d.viewer.*` видалені, `user_kiosk` архівований, бізнес-дані на місці (кількості з п. 2 незмінні).

## 14. Definition of Done

- Усі AC-01…AC-67 покриті тестами §13.1 (UT/JT/HT) або ТК §13.2; прогін зелений на копії демо-бази; `f3d_demo` і `f3d_perf_big` — окремим прогоном.
- `ruff` (конфіг репозиторію) і `eslint` (конфіг Odoo) без помилок; жодного `x_` поля, `TBD`, `print` у модулі; `sudo` лише в дозволених місцях (AC-14).
- `neutralize.sql` перевірений (ТК-12); `CHANGELOG.md` з версією `19.0.1.0.0`; `README.md` модуля; інструкції ARCHITECTURE §4 відтворені в `static/description/index.html`.
- Перегляд безпеки §13.3 підписаний менеджером; Q-01…Q-08 закриті або мають рішення «тим часом».
- `plant/export_viewer_assets.py` у репозиторії, `BUILD.json` збігається з git-ревізією асетів; `dist/index.html` зібраний з того самого ядра (AC-38).
- DEPLOY_TEST §13.5 пройдено, результат — у `docs/modules/factory3d_viewer/DEPLOY_TEST.md`.

## 15. Відкриті питання

Q-01…Q-08 — у ARCHITECTURE §5 (ті самі номери). Додатково виявлені під час написання SPEC:

| ID | Питання | Кому | Рекомендована відповідь | Тим часом |
|---|---|---|---|---|
| Q-09 | **Закрито (X-14):** поле типу локації для 3D (`stack|bin|shelf|pallet_cell|kit|area`) і місткість додає `factory3d_base` M-03 — `f3d_loc_kind`, `f3d_capacity` (CB-05) | автор SPEC base | так (рішення менеджера) | M-01a/R-04 читають `f3d_loc_kind`, `f3d_capacity` з base; статика — лише запасна (AC-65) |
| Q-10 | **Закрито 14.10 (рішення менеджера):** в Odoo 19 `mrp.workorder` має `date_start`/`date_finished`, поля `date_planned_finished` немає; ключ payload `date_planned_finished` обчислюється (`start + duration_expected`). `mrp.workorder.date_planned_finished` в Odoo 19 (у 17+ планові дати — `date_start`/`date_finished` до старту) | розробник (перевірити в коді 19) | рахувати `date_start + duration_expected` (R-07) | так і зроблено |
| Q-11 | **Закрито 14.10 (рішення менеджера):** без LFS — репозиторій не на LFS, частини GLB лишаються як є. Чи потрібен `git lfs` для 13,7 МБ GLB у `static/model/parts` | менеджер | так, якщо репозиторій уже на LFS; інакше — як є, оновлення частин ≤ 1 раз на тиждень | як є |

**Закрито 14.10 відповідями замовника** (CONSISTENCY, «Відповіді на питання до замовника»): Q-06 (№ 19), Q-08 (№ 19) — рішення в `ARCHITECTURE.md` §5. Рішеннями менеджера закрито Q-01, Q-03, Q-04, Q-07 — рішення в `ARCHITECTURE.md` §5. Відповідями № 35–36 закрито Q-02, Q-05.

## Додаток A. JSON-схема контракту даних (`meta.schema = "1.1"`)

Джерело: `dist/odoo_demo.json` (13.10.2026, живий знімок бази `odoo`) + генератор `plant/odoo_demo.py`.
Позначення: **req** — ключ обов'язковий у кожному записі; opt — може бути відсутнім (не `null`, а
відсутній); `N/M` — у скількох записах файлу ключ є. Типи: `str`, `int`, `float`, `num` (int або float),
`bool`, `list[T]`, `dict`, `null`. Дати — `str` `"YYYY-MM-DD HH:MM"` за Києвом, якщо не сказано інше.
Порядок ключів верхнього рівня — обов'язковий (клієнт не залежить, але тести порівнюють).

**Схема 1.1 (X-24, каркас §6.7).** `1.1` = 26 базових ключів `dist/odoo_demo.json` (A.0–A.14) + додаткові ключі
модулів, перелічені в A.15. Правила версії 1.x — адитивні: (1) додаткові ключі всередині базових розділів (у записах
`workcenters`, `productions`, `locations`, `equipment`, `employees`, `zones`, у `infra.cards.*`, `infra.totals`,
`fire`, `evacuation`, `lighting`, `ventilation`) дозволені й не змінюють тип і зміст базових ключів; (2) нові ключі
верхнього рівня (`yard`, `access`) стоять **лише після** 26 базових, у порядку `_f3d_sequence` провайдера (R-01 п. 6);
(3) базові ключі не прибираються й не перейменовуються; (4) клієнт ігнорує ключі, яких не знає. Мажорна версія `2.x` —
лише з новим клієнтом (FR-37).

### A.0 Верхній рівень (26 базових ключів + ключі модулів)

| Ключ | Тип | Записів у файлі | Хто дає в модулі | Опис |
|---|---|---|---|---|
| `meta` | dict | — | збирач | джерело, час, схема, розділи |
| `products` | dict[code→dict] | 57 | M-01a | товари за `default_code` |
| `locations` | dict[code→dict] | 689 | M-01a | місця зберігання за кодом сцени |
| `workcenters` | dict[code→dict] | 35 | M-01b | робочі центри |
| `productions` | list[dict] | 32 | M-01b, M-01g | МО |
| `workorders` | dict[id→dict] | 199 | M-01b | робочі завдання за `WO00001` |
| `sale_orders` | list[dict] | 8 | M-01c | замовлення клієнтів |
| `purchase_orders` | list[dict] | 3 | M-01c | закупівлі (лише з рядками до комірок/плит) |
| `pickings` | list[dict] | 42 | M-01c | переміщення 6 типів |
| `quality_checks` | list[dict] | 5 | M-01d | контроль якості |
| `maintenance_requests` | list[dict] | 6 | M-01e | заявки ТО |
| `equipment` | dict[code→dict] | 15 | M-01e, M-01h | обладнання з показниками |
| `employees` | dict[code→dict] | 35 | M-01f | люди (`OP-SAW-1`, `OP-W1`…) |
| `docks` | dict[code→str] | 14 | M-01c | ворота → назва переміщення |
| `zones` | dict[code→dict] | 45 (34 цеху + 11 надвірних, X-29) | статика + M-01g (усі активні `f3d.zone`) | зони |
| `energy` | dict | — | статика (+ `factory3d_energy`, сигнали) | електропостачання |
| `lighting` | dict | — | статика (+ `factory3d_bms`) | освітлення |
| `ventilation` | dict | — | статика (+ `factory3d_bms`, сигнали) | вентиляція й опалення |
| `fire` | dict | — | статика (+ `factory3d_fire_safety`, сигнал `FA-FAC/dust`) | пожежна сигналізація |
| `infra` | dict | — | статика (+ сигнали `totals`) | резерв, СЕС, ІТ, територія |
| `evacuation` | dict | — | статика (+ `factory3d_fire_safety`) | евакуація |
| `sheet_chain` | dict | — | M-01g | ланцюжок плит |
| `ship_chain` | dict | — | M-01g | ланцюжок відвантаження |
| `material_paths` | list[dict] | 6 | M-01g | типові шляхи матеріалів |
| `full_cycle_mo` | str | — | M-01g | назва МО для кнопки «Весь цикл» |
| `passports` | dict[code→dict] | 207 | статика | паспорти обладнання |
| `yard` | dict | — | `factory3d_yard` (160, CY-06) | лише з модулем; після 26 базових (A.15) |
| `access` | dict | — | `factory3d_access` (170, CA-05) | лише з модулем; після `yard` (A.15) |

### A.1 `meta`

| Ключ | Тип | req | Приклад |
|---|---|---|---|
| `source` | str | req | `"Odoo 19.0 · timur-o19demo"` |
| `database` | str | req | `"odoo"` |
| `company` | str | req | `"Меблева фабрика (демо)"` |
| `warehouse` | str | req | `"WH"` |
| `now` | str | req | `"2026-10-12 10:30"` — демо-годинник або зараз |
| `note` | str | req | текст для «Огляд → Дані» |
| `live` | bool | req | `true` з Odoo; `false` у згенерованому файлі |
| `pulled_at` | str | req при `live` | `"2026-10-13 23:06"` |
| `iot` | dict | opt | `{"source": str, "signals": int, "alarms": int, "updated": str}` |
| `schema` | str | req (нове) | `"1.1"` (X-24) |
| `ts_utc` | str | req (нове) | `"2026-10-13T20:06:12Z"` — для `since` |
| `user` | str | req (нове) | ім'я користувача запиту |
| `lite`, `kiosk`, `bus` | bool | req (нове) | — |
| `sections` | dict[str→str] | req (нове) | `"live"|"static"|"denied"|"missing"|"error"|"partial"` |
| `errors` | list[dict] | req (нове) | `[{"provider": str, "error": str}]` |
| `snapshot` | dict | opt | `{"id": int, "ts": str, "kind": str}` — лише у відповіді API-06 |
| `built_at`, `static_etag` | str | opt | зі статики |

### A.2 `products[code]`

| Ключ | Тип | req | Приклад |
|---|---|---|---|
| `default_code` | str | req | `"DSP16-SON"` |
| `name` | str | req | `"ДСП 16 мм Дуб Сонома 2800×2070"` |
| `uom` | str | req | `"арк"`, `"шт"`, `"компл"`, `"м"`, `"кг"`, `"рул"` |
| `categ` | str | req | `"Плитні матеріали"`, `"Фурнітура"`, `"Крайка"`, `"ЛФМ"`, `"Пакування"`, `"Готова продукція"`, `"Фасади"` |
| `seller` | str | opt (47/57) | `"Плитсервіс (демо)"` |

### A.3 `locations[code]`

| Ключ | Тип | req | Приклад / правило |
|---|---|---|---|
| `complete_name` | str | req | `"WH/Сировина/Плити/Портал/PLT-04C"` |
| `quants` | list[dict] | req (може бути `[]`) | A.3.1 |
| `capacity` | int (num, якщо base `f3d_capacity` дробове) або null | req | base `f3d_capacity` > 0, інакше статика (R-04, X-14): 60 (stack портал), 55 (стелаж), 833 (bin = max правила), 2200 (shelf), 2 (pallet_cell), 14 (`PAL-*`), null (area/kit) |
| `fill` | float або null | req | 0…1; null якщо `capacity` null |
| `kind` | str | req | base `f3d_loc_kind`, порожнє — статика (X-14): `"stack"` (123), `"bin"` (144), `"shelf"` (24), `"pallet_cell"` (360), `"kit"` (20), `"area"` (18) |
| `state` | str | opt (144 — лише bin) | `"ok"`, `"low"`, `"out"` |
| `orderpoint` | dict | opt (144) | `{"product": str, "min": int, "max": int, "purchase": str opt}` |
| `production` | str | opt (20 — kit) | `"WH/MO/00231"` — для якого МО візок/етажерка |
| `picking` | str | opt (12 — kit) | `"WH/PC/00311"` — комплектація |
| `fronts_mo` | str | opt (8 — `FRONTS-*`) | `"WH/MO/00255"` |
| `note` | str | opt (8) | `"Фасади з WH/MO/00255: готово 7 з 48"` |

A.3.1 `quants[]`: `product` str req; `qty` num req; `lot` str opt (131); `reserved` float opt (103; лише > 0);
`reserved_for` str opt (61; назва відвантаження); `package` str opt (470; `"PACK0030001"`); `picking` str opt
(15; приймання для `UNLOAD-*`); `quality` str opt (1; `"QC/00412"` карантин).

### A.4 `workcenters[code]`

| Ключ | Тип | req | Приклад |
|---|---|---|---|
| `name` | str | req | `"Розкрій 1"` |
| `code` | str | req | `"SAW-1"` |
| `status` | str | req | `"work"` (29), `"idle"` (5), `"stop"` (1) |
| `working_state` | str | req | `"done"`, `"normal"`, `"blocked"` (значення Odoo) |
| `oee` | float | req | 0…1, `0.84` |
| `capacity` | int | req | `1` |
| `time_efficiency` | float | req | `1.0` |
| `productive_minutes` | int | req | `176` |
| `losses` | list[{reason: str, minutes: int}] | req (може `[]`) | `[{"reason": "Очікування матеріалу", "minutes": 16}]` |
| `current_workorder` | str або null | req | `"WO00013"` |
| `queue` | list[str] | req | до 8 id завдань |
| `manufacturer`, `model` | str | req (35/35) | `"HOMAG"`, `"SAWTEQ S-310 …"` |
| `energy` | dict | req | `{"p_now": float, "line": str}` |
| `idle_reason` | str | opt (5) | текст |
| `maintenance_request` | str | opt (1) | `"MR/00031"` |

### A.5 `productions[]`

| Ключ | Тип | req | Приклад |
|---|---|---|---|
| `name` | str | req | `"WH/MO/00231"` |
| `product`, `product_name` | str | req | `"KC-B600"`, `"Шафа нижня 600"` |
| `qty` | num | req | `26.0` |
| `uom` | str | req | `"шт"` |
| `state` | str | req | `"progress"` (30), `"confirmed"` (2), `"done"` |
| `origin` | str | req | `"S00087"` або назва батьківського МО |
| `route` | str | req | `"A"`, `"B"`, `"C"`, `"D"`, `"F1"`, `"F2"`, `"F3"` (код специфікації) |
| `workorders` | list[str] | req | id завдань у порядку операцій |
| `date_start`, `date_deadline` | str | req | дати |
| `progress` | float | req | 0…1 |
| `components` | list[dict] | req | A.5.1 |
| `child_productions` | list[str] | opt (8) | МО фасадів |
| `supply` | dict | req (32/32; відсутній, якщо немає плити) | A.5.2 |
| `delivery` | dict | req (32/32; відсутній без SO) | A.5.3 |
| `energy_kwh` | float | req | `86.2` |
| `energy_cost` | int | opt — лише з групою `factory3d_energy.group_f3d_energy_cost` і не кіоск (§4.4, X-25) | `724` |
| `reservation_state` | str | opt (2) | `"waiting"` |

A.5.1 `components[]`: `product` str req; `qty` num req; `available` bool req; `locations` list[str] req (≤ 12);
`door` int req (1…7); `kind` str req (`"плита"`, `"фурнітура"`, `"крайка"`, `"ЛФМ"`, `"плівка ПВХ"`, `"пакування"`;
відсутній для невідомого префікса); `to` str req (код центру; `null` якщо не знайдено); `path` list[{code, label}] req;
`receipt` str opt (94/200); `expected` str opt (14/200, `"WH/IN/00132 о 14:00"`).

A.5.2 `supply`: `product` str; `steps` list[{code: str, label: str, note: str, doc: str|null opt}] (у файлі `note`
є в усіх 188 кроках, `doc` — у 54); `lot` str|null; `warn` str|null; `note` str|null; `docs` dict opt (R-23: назви документів із кроків і нотаток, яких немає в
`pickings`/`quality_checks`/`productions`: `{назва: {kind, state}}`).

A.5.3 `delivery`: `picking` str; `partner` str; `steps` list[{code, label, note, doc opt}] (284 кроки, `doc` у 64);
`note` str|null; `via` str opt (8 — МО фасадів: назва МО корпусу); `docs` dict opt (як у A.5.2).

### A.6 `workorders[id]`

| Ключ | Тип | req | Приклад |
|---|---|---|---|
| `id` | str | req | `"WO00001"` |
| `name` | str | req | `"Розкрій"` |
| `production` | str | req | `"WH/MO/00231"` |
| `workcenter` | str | req | `"SAW-1"` |
| `state` | str | req | `"done"` (80), `"pending"` (61), `"progress"` (30), `"ready"` (26), `"waiting"` (2) |
| `sequence` | int | req | від 1 |
| `duration_expected` | int | req | хвилини |
| `progress` | float | req | 0…1 |
| `date_start` | str | opt (110 — done/progress) | — |
| `date_finished` | str | opt (80 — done) | — |
| `duration` | int | opt (110) | фактичні хвилини |
| `date_planned_finished` | str | opt (30 — progress) | — |
| `blocked` | bool | opt (1; лише `true`) | — |

### A.7 `sale_orders[]`, `purchase_orders[]`

`sale_orders[]`: `name` str req (`"S00087"`); `partner` str req; `state` str req (`"sale"`); `date_order`,
`commitment_date` str req; `lines` list[{product: str, qty: num}] req; `productions` list[str] req; `amount`
float opt (права §4.4; у файлі req); `delivery` str req (назва відвантаження).
`purchase_orders[]`: `name` str req (`"P00412"`); `partner` str req; `state` str req (`"purchase"`); `date_order`,
`date_planned` str req; `lines` list[{product, qty}] req; `locations` list[str] req (комірки, для яких закупівля;
може бути `[]`).

### A.8 `pickings[]`

| Ключ | Тип | req | Приклад |
|---|---|---|---|
| `name` | str | req | `"WH/IN/00123"` |
| `picking_type` | str | req | `"Приймання"` |
| `type` | str | req | `"incoming"` (13), `"outgoing"` (8), `"putaway"` (2), `"replenish"` (3), `"pick_components"` (12), `"store_finished"` (4) |
| `partner` | str | req (може `""`) | — |
| `origin` | str | req | `"P00405"`, `"S00087"`, `"WH/MO/00231"`, `"QC/00413"`, текст |
| `state` | str | req | `"assigned"` (24), `"done"` (18), `"waiting"`, `"draft"` |
| `scheduled_date` | str | req | — |
| `progress` | float | req | 0…1 |
| `lines` | list[{product: str, qty: num, qty_done: num}] | req | — |
| `dock` | str | opt (21 — incoming/outgoing) | `"DOCK-W5"` |
| `truck` | str або null | opt (21) | `"TRUCK-IN-1"` |
| `location_dest` | str | opt (34) | `"Склад крайки"` або код `"KIT-01"`, `"PLT-07C"` |
| `source_locations` | list[str] | opt (25) | коди |
| `vehicle` | str або null | opt (5) | `"FL-2"` |
| `note` | str | opt (13) | — |
| `carrier` | str | opt (8 — outgoing) | `"Нова Пошта Вантаж (демо)"` |

### A.9 `quality_checks[]`, `maintenance_requests[]`

`quality_checks[]`: `name` str req; `title` str req; `product` str req; `lot` str opt (2); `state` str req
(`"none"`, `"pass"`, `"fail"`); `location` str req (код сцени: `"QC-1"`, `"QC-PLT-1"`, `"ASMLINE-1"`); `picking` str opt (4);
`production` str opt (1); `note` str req.
`maintenance_requests[]`: `id` str req (`"MR/00031"` = `name` заявки); (R-22, живі дані) `res_id` int opt, `equipment_name` str opt, `done` bool opt, `overdue_days` int opt; `name` str req (тема); `equipment` str req
(код сцени: `"CNC-2"`, `"DUST-1"`, `"FL-2"`, `"RV-05"`, `"FA-FAC"`); `maintenance_type` str req (`"corrective"`,
`"preventive"`); `stage` str req (`"Новий"`, `"В роботі"`, `"Відремонтовано"`, `"Брак"`); `priority` str req (`"0"`…`"3"`);
`request_date` str opt (4); `schedule_date` str opt (3); `technician` str opt (1).

### A.10 `equipment[code]`

Базові (M-01e): `name` str req; `category` str req; `serial` str opt (7); `manufacturer`, `model` str opt (12);
`next_maintenance` str opt (11); `current_task` str|null opt (8); `state` str opt (7: `"busy"`, `"charging"`);
`maintenance_request` str opt (1); `maintenance_request_id` int opt, `maintenance_due` `"overdue"|"soon"` opt (R-22). Показники (сигнали, C-07, усі opt, тип float якщо не сказано): `battery`
(0…1, 8), `hours` (9), `cycles_today` (1), `vacuum_kpa` (1, від'ємне), `pressure_bar` (3), `load` (0…1, 1),
`filter_dp_kpa` (1), `airflow_m3h` (1), `supply_c` (1), `silo_fill` (0…1, 1), `briquettes_today_kg` int (1),
`busy` int, `total` int (1 — `CHARGING`), `boilers` str (1), `last_inspection` str `"YYYY-MM-DD"` (1),
`leak_check` str (1). Коди у файлі: `FL-1…FL-5`, `FL-C1`, `FL-C2`, `TUGGER-1`, `GANTRY-1`, `COMPRESSOR`, `DUST-1`,
`BOILER`, `CHARGING`, `SPRINKLERS`, `AIR-RING`. Додаткові ключі модулів (`GANTRY-1.gantry`, `BOILER.heat_kw`/`return_c`) —
A.15. Координат техніки `x`, `y` у схемі 1.1 **немає** — фаза 4: сигнали `equipment/<code>/x`, `/y` telemetry зберігає з
`viewer_visible=False`, у payload вони не потрапляють (X-28, telemetry Q-08).

### A.11 `employees[code]`, `docks`, `zones[code]`

`employees[code]` (`OP-SAW-1`, `OP-W1`…): `name`, `job`, `department`, `shift` str req; `workcenter` str opt (28);
`current_workorder` str opt (28); `present` bool opt (нове; M-01f, з access — CA-05); з `factory3d_access` ще `zone`,
`zone_since`, `last_event` (A.15, X-28).
`docks`: `{"DOCK-W1": "WH/IN/00128", …, "DOCK-E7": "WH/OUT/00418"}` — ворота без документа відсутні.
`zones[code]` (усі активні `f3d.zone` base, 45; X-29): `name` str req; `odoo_location` str|null req; `locations` list[str]
req; `workcenters` list[str] req; `pickings` list[str] opt (14); `zone_type` str opt (нове: значення `f3d.zone.zone_type`,
`"outdoor"` для надвірних); `polygon` list[[x, y]] opt (нове: `f3d.zone.polygon`, м; для надвірних зон — єдина
геометрія); `is_roof` bool opt (нове; лише `true`, лише `Z-ROOF`); `people_now` int opt (access, A.15). Коди зон цеху (34):
`Z-RCV-1…7`, `Z-SHEETS`, `Z-HW`, `Z-EDGE`, `Z-PKS`, `Z-CUT`, `Z-EB`, `Z-CNC`, `Z-SORT`, `Z-FAC`, `Z-ASM`, `Z-PRE`,
`Z-MAINT`, `Z-SOC`, `Z-OFFICE`, `Z-PACK`, `Z-POST`, `Z-CMP`, `Z-CHG`, `Z-FG`, `Z-ELEC`, `Z-OUT-1…7`; надвірні (11, base
Додаток C.2): `Z-GATE-W`, `Z-GATE-E`, `Z-YARD-W`, `Z-YARD-E`, `Z-KPP`, `Z-PARKING`, `Z-BOILER`, `Z-FIREWATER`,
`Z-ENERGY`, `Z-WASTE`, `Z-ROOF`. Геометрія зон цеху (`rect`) — у `layout` статики; надвірних — лише `polygon` тут.

### A.12 `energy`

| Ключ | Тип | Опис |
|---|---|---|
| `meta` | dict | `source` str, `u_kv` str (`"10 / 0,4"`), `tariff_uah` float (8.4), `note` str |
| `totals` | dict | `p_inst` int, `p_now` num, `s_now` num, `cos_before` float, `cos_after` float, `kwh_today` int, `peak_kw` int, `peak_time` str `"09:15"`, `cost_today` int, `capacity_kva` int, `pv_kw` float, `grid_kw` num, `pv_today` int, `chp_kw` float, `export_kw` num, `bess_kw` num |
| `transformers` | dict[`T1`,`T2` → dict] | `name` str, `rating_kva` int, `section` int, `p_kw` float, `s_kva` int, `load` float, `i_a` int, `temp_c` float, `cos_phi` float, `incomer` str (`"Q1"`) |
| `cells` | dict[11 → dict] | `name` str, `type` str (`incomer`, `feeder`, `coupler`, `pfc`), `section` int\|null, `feeds` str\|null, `rating_a` int opt, `state` str opt (`"on"`), `line` str opt (`"BW-3"`), `i_now` int opt, `p_now` float opt, `rating_kvar` int opt, `q_now` int opt, `steps` str opt, `cos_before`/`cos_after` float opt, `note` str opt. Коди: `PFC-1`, `Q1`, `QF-3`, `QF-2`, `QF-C1`, `QS`, `QF-1`, `QF-4`, `QF-C2`, `Q2`, `PFC-2` |
| `lines` | dict[`BW-1…BW-4`,`C1`,`C2` → dict] | `kind` str (`busway`, `cable`; X-26, як energy R-16 п. 5), `name` str, `cell` str, `rating_a` int, `consumers` list[str], `p_inst` num, `p_now` float, `cos_phi` float, `i_now` int, `load` float |
| `consumers` | dict[49 → dict] | `name` str, `feeder` str, `bus` str\|null, `p_inst` num, `p_now` float, `cos_phi` float, `source` str (`passport`, `estimate`, `mixed`), `status` str (`work`/`idle`/`stop`), `i_now` int, `line` str, `kwh_shift` float, `note` str opt (9), `group` str opt (8, `"light"`) |
| `profile` | list[24 × int\|null] | кВт·год по годинах сьогодні (null — ще не настала) |
| `typical` | list[24 × int] | типовий день |
| `events` | list[{time: str, level: str (`info`/`warn`/`bad`), code: str, text: str}] | 6 |

### A.13 `lighting`, `ventilation`, `fire`, `infra`, `evacuation`

`lighting`: `groups` dict[32 `LT-*` → {zone, zone_name, task, task_name, kind, panel, n int, lumen int, watt int,
area int, e_norm int, e_calc int, level float, e_now int, p_inst float, p_now float, control str}]; `panels`
dict[`LP-1…3` → {name, groups list[str], n int, p_inst float, p_now float}]; `uf` 0.7; `mf` 0.8; `norms_ref` dict[task → str].
`ventilation`: `units` dict[29 (`RV-01…25`, `AHU-1`, `EF-ELEC`, `EF-CMP`, `EF-CHG`) → {name, kind, zone, mode,
airflow_m3h float, airflow_nom int, supply_c float opt (26), indoor_c float opt (28), heating_valve float opt (26),
heat_kw float opt (26), p_inst float, p_now float, filter_dp_pa float opt (26), state str (`on`/`off`),
maintenance_request str opt (1), maintenance_request_id int opt (R-22), note str opt (4)}]; `totals` {units int, airflow_m3h float, heat_kw int, p_now,
p_inst float, outdoor_c, indoor_set_c float, boilers int, boiler_kw int, boilers_on int, boiler_load float,
design_heat_kw int, chp_heat_kw int, chp_heat_now int, chp_heat_rated int}; `heat_balance` {t_out float, items
list[{name, kw int}], total int, capacity int, chp_kw int, reserve float, note str}.
`fire`: `rules` dict (10 ключів: `smoke_spacing_6_12m` 8.8, `smoke_wall_6_12m` 4.4, `heat_spacing` 6.4,
`mcp_spacing` 30, `sounder_level` 65, решта null); `loops` dict[`"1"…"4"` → {detectors, mcp, sounders, flame,
modules int}]; `groups` dict[35 `FA-*` → {zone, zone_name, kind (`smoke`/`multi`/`heat`), kind_name, n int,
spacing float, area int, loop int, state (`ok`/`warn`), warning str opt, maintenance_request str opt, maintenance_request_id int opt (R-22), dust float opt}];
`totals` {detectors 222, mcp 36, sounders 41, mcp_max_m 26.9, flame 3, spark_detectors 4, state str, sprinkler str};
`events` list[{time, level, code, text}] (4).
`infra`: `cards` dict[30 кодів → {rows list[[str, str]], note str opt, items list[str] opt, warn str opt}]
(`PV-ROOF`, `PV-INV`, `CHP`, `GENSET`, `ATS-1`, `BESS`, `WATER`, `ODOO-TABLETS`, `ODOO-SCANNERS`, `PRN-RCV`,
`PRN-PACK1`, `PRN-PACK2`, `PRN-OUT`, `SCALE-OUT1`, `SCALE-OUT2`, `SCALE-RCV`, `IOT-RCV`, `IOT-PACK`, `IOT-OUT`,
`WIFI`, `SERVER`, `TURNSTILES`, `ACCESS`, `CCTV`, `TRUCK-SCALE`, `GATE-W`, `GATE-E`, `SMOKE-VENTS`, `SMOKE-CTRL`,
`LPS`); `totals` {pv_kwp int, pv_now float, pv_today int, grid_kw, export_kw, bess_kw num, chp_kw float, chp_rated
int, chp_heat int, chp_load float, load_kw int, bess_kwh int, bess_soc float, genset_kva int, critical_kw int, vents
int, n_modules int, vent_area float}.
`evacuation`: `exits` list[12 × {code `EX-S1`…, x float, y float, side str}]; `routes` dict[32 зони → {name, exit,
length float, path list[[x, y]]}]; `max_distance` float; `worst_point` [x, y]; `drill_origin` str (`FA-CNC`);
`drill_zone` str; `drill_detector` str; `norm_distance` int (240); `norm_ref` str; `norm_alt` int (50);
`norm_alt_ref` str; `drill_steps` list[8 × {t int, who str, text str}].
Додаткові ключі модулів у цих розділах (bms CH-02, fire CF-01, energy CE-03, міст genset CG-02, yard/access картки
`infra.cards`) — A.15; зокрема `fire.groups[*].state` з `factory3d_fire_safety` приймає ще `alarm`, `prealarm`, `fault`,
`disabled`, `test` (клієнт — §8.2 п. 10).

### A.14 `sheet_chain`, `ship_chain`, `material_paths`, `full_cycle_mo`, `passports`

`sheet_chain`: `steps` list[5 × {n int, title str, docs list[str], codes list[str], stock str, desc str}]; `path`
list[6 × {code, label}] (`label` виду `"1 · фура"`).
`ship_chain`: `steps` list[5 × {n, title, codes, stock, desc}] (без `docs`).
`material_paths`: list[6 × {kind str, product str, mo str, steps list[{code, label}]}].
`full_cycle_mo`: str.
`passports[code]` (207 кодів, у т.ч. `LT-*`, `RV-*`, `FA-*`, `Q1`, `BW-1`…): `role` str req; `manufacturer`,
`model`, `reason` str req; `specs` dict[str → str] req; `dimensions_mm` {L, W, H: int|null} req; `power_kw`
num|null req; `sources` list[str] req; `units` list[dict тієї ж форми] req (може `[]`); `connected_kw` num|null opt (39);
`connected_note` str opt (39); `connected_sources` list[str] opt (39); решта числових ключів (`lumen`, `watt`,
`airflow_m3h`, `heat_kw`, `kva`, `tank_l`, `capacity_kg`…) — opt, специфічні для ролі, клієнт їх не читає
(показує лише `specs`).

### A.15 Додаткові ключі модулів (схема 1.1, X-24)

Перелік того, що модулі додають до базових розділів (адитивно, правила A.0) і які нові ключі верхнього рівня
приймає схема 1.1. Типи й значення — у SPEC модуля-власника за вказаним контрактом; viewer їх лише передає (клієнт
читає ті, що описані в §8.2). Порядок рядків — `_f3d_sequence` провайдера.

| Модуль, провайдер (sequence), контракт | Куди | Ключі |
|---|---|---|
| `factory3d_machine_connect`, `machines` (75), CM-05 | `workcenters[code]` | `machine_state`, `state_since`, `availability`, `performance`, `quality`, `downtime`, `pieces_shift`, `link`, `online`; перекриває `oee`, `status` (machine_connect R-25) |
| те саме | `equipment["GANTRY-1"]`, `locations["PLT-*"]` | `gantry` |
| те саме | `productions[]`, `sheet_chain` | `cut_map`, `supply.gantry`; перекриває `sheet_chain.steps[4].stock` |
| `factory3d_telemetry`, `telemetry` (95), CT-07 | вузли за шляхами сигналів (C-07) | значення в наявних вузлах (нових вузлів не створює); `meta.iot.stale` int |
| `factory3d_energy`, `energy` (100), CE-08 | `energy`, `workcenters[*].energy`, `productions[]` | розділ `energy` за A.12; `productions[]`: `energy_kwh`, `energy_cost` (лише з групою вартості, X-25), `energy_quality` |
| `factory3d_energy`, `infra` (150), CE-03 | `infra.totals`, `infra.cards` | `shed_kw`, `bess_mode` (`charge`/`discharge`/`idle`) + ключі CE-03 з A.13; `rows` карток `PV-ROOF`, `PV-INV`, `CHP`, `ATS-1`, `BESS` |
| `factory3d_bms`, `lighting` (110), CH-02 | `lighting.groups[*]`, `lighting.panels[*]` | groups: `dali_group`, `faults`, `faulty`, `scene`, `deviation`, `deviation_text`, `stale`, `level_source`; panels: `state`, `p_source` |
| `factory3d_bms`, `ventilation` (120), CH-02, bms Додаток B.1/B.3 | `ventilation.units[*]`, `ventilation.totals`, `ventilation.boiler`, `equipment["BOILER"]` | units: `mode_code`, `filter_extract_dp_pa`, `setpoint_day_c`, `setpoint_night_c`, `deviation`, `deviation_text`, `stale`, `room_pressure_pa` (`AHU-1`); totals: `heat_need_kw`, `boilers_on_calc`, `deficit_kw`, `chp_source`; `ventilation.boiler` {`state`, `supply_c`, `return_c`, `silo_fill`, `heat_kw`}; `equipment["BOILER"]`: `heat_kw`, `return_c` |
| `factory3d_fire_safety`, `fire` (130), CF-01 | `fire` | `panel` {`code`, `state`, `state_text`, `comm`, `last_seen`, `alarms`, `faults`, `disabled`, `sounders`, `brigade`}; `systems` {`SPARK-1`, `SMOKE-CTRL`, `SPRINKLERS` → {`state`, `text`, …}}; `devices` {адреса → {`type`, `x`, `y`, `z`, `zone`, `state`, `dust`}} (лише за параметром fire `viewer_devices`); `groups[*]`: `alarm_state`, `compliance` (`ok`/`warn`/`fail`), `stale`, значення `state` + `alarm`, `prealarm`, `fault`, `disabled`, `test`; `loops[*].state` |
| `factory3d_fire_safety`, `evacuation` (140), CF-01 | `evacuation` | `drill_active` (`null` або {`name`, `zone`, `zone_code`, `detector`, `started`, `elapsed_s`, `steps_done`, `steps_total`, `on_site`, `evacuated`}); `compliance` {`routes_ok`, `routes_total`, `worst`, `norm`, `exits_ok`, `smoke_ok`, `smoke_total`}; `exits[*]`: `width`, `ok`; `routes[*]`: `ok`, `norm` |
| міст `factory3d_genset`, `genset` (155), CG-02 | `infra.genset`, `infra.totals`, `infra.cards` | `infra.genset[<код>]` (вузол генератора: показники, `updated`, `state_label`, `mode_label`, `breaker_label`, `alarm_label`); totals: `genset_kw`, `genset_state`, `genset_fuel_pct`, `genset_autonomy_h`, `island`, `grid_ok`; `rows` картки `GENSET` |
| `factory3d_yard`, `yard` (160), CY-06 | **новий верхній ключ `yard`**; `infra.cards` | `yard` = yard Додаток C (`updated`, `gates`, `scale`, `trucks`, `queue`, `kpp`, `stats`); `rows` карток `GATE-W`, `GATE-E`, `TRUCK-SCALE` |
| `factory3d_access`, `access` (170), CA-05 | **новий верхній ключ `access`**; `employees[code]`, `zones[code]`, `infra.cards` | `access` = access R-12; employees: `present`, `zone`, `zone_since`, `last_event` {`ts`, `door`, `direction`, `type`}; zones: `people_now`; `rows` карток `TURNSTILES`, `ACCESS` |

## Додаток B. `static/data/model_static.json`

= `Demo().build()` **без** ключів `products`, `productions`, `workorders`, `sale_orders`, `purchase_orders`,
`pickings`, `quality_checks`, `maintenance_requests`, `employees`, `docks`, `sheet_chain`, `ship_chain`,
`material_paths`, `full_cycle_mo`; з `locations` лишаються лише `complete_name`, `kind`, `capacity` (без квантів,
`fill`, `state`, `orderpoint`, `production`, `picking`, `fronts_mo`, `note`); з `workcenters` — лише `name`,
`code`, `manufacturer`, `model`; з `equipment` — `name`, `category`, `manufacturer`, `model`, `boilers`, `busy`,
`total`, `last_inspection`, `leak_check` (без показників і `next_maintenance`, `current_task`, `maintenance_request`);
з `zones` — `name`, `odoo_location`, `locations`, `workcenters` (без `pickings`); `energy`, `lighting`, `ventilation`,
`fire`, `infra`, `evacuation`, `passports` — як є, але з розділів прибрано поля, що є в демо документами:
`fire.groups[*].maintenance_request`, `ventilation.units[*].maintenance_request`, `energy.events` → `[]`,
`fire.events` → `[]`, `energy.profile` → типовий (`typical`) до поточної години буде підставляти провайдер
`energy` фази 3 (до того клієнт малює `typical`). Додані ключі:

| Ключ | Вміст |
|---|---|
| `meta` | `{"schema": "1.1", "built_at": ISO, "git": sha, "source": "plant/odoo_demo.py Demo().build()", "live": false}` |
| `layout` | `dims` `{W:150, D:72, H:9}`; `zones` dict[code → {name, rect [x0,y0,x1,y1], color, desc}] (34 + `Z-RCV/OUT`; надвірних зон base C.2 тут немає — їх контур лише в живому `zones[code].polygon` з `f3d.zone`, X-29); `machines` dict[code → {type, name, x, y, desc, zone, rot opt}] (35); `doors` list[{side, y, w}] (14); `rcv_goods` dict[int → str]; `layers` list[{key, label, group}] (31); `locations` dict[code → {complete_name, kind, capacity, zone}] (689); `operators` dict[type → [x, y, rot]] |
| `path_templates` | `{"плита": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "QC-PLT-{k}", "{rack}", "{gantry}"], "фурнітура": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "QC-1", "SCALE-RCV", "PRN-RCV", "{bin}", "{kit_or_Z-PRE if to startswith ASM}", "TUGGER-1"], "крайка": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "{shelf}"], "ЛФМ": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "PAINT-STORE"], "плівка ПВХ": те саме, "пакування": ["GATE-W", "{truck_or_dock}", "UNLOAD-{k}", "PACK-STORE", "PAL-1", "{BOX-1 if to != BOX-1}"]}` з підписами `label` з макета (`"в'їзд"`, `"ворота {k}"`, `"вивантаження"`, `"контроль"`, `"зважування"`, `"етикетка партії"`, `"стелаж фурнітури"`, `"комплект WH/PC"`/`"буфер комплектів"`, `"тягач"`, `"склад крайки"`, `"склад ЛФМ"`, `"пакматеріали"`, `"піддони"`, `"коробки з гофрокартону"`, `"стелаж"`, `"під порталом"`) |
| `door_goods` | `{"1": ["DSP","MDF","HDF"], …, "7": ["PK"]}` (`plant/cycle_check.DOOR_GOODS`) |
| `supply_steps_text` | тексти `note` кроків `supply`/`delivery` з макета (рядки 757–778, 870–884), щоб провайдер `chains` не дублював рядки |
| `energy.profile_k` | `{type: kf}` з `plant/energy.PROFILE` і `idle_k` з `IDLE_K`/`IDLE_DEFAULT` — для R-07 `energy_kwh` |

Розмір: ≈ 650 КБ raw / ≈ 85 КБ gzip (passports 521 КБ). Файл детермінований: два запуски дають однаковий
`sha1` (`det()` без random) — тест `test_static_etag_stable`.

## Додаток C. Карта шляхів сигналів (C-07) — 196 шляхів `x_f3d_signal.x_code` (= майбутній `f3d.signal.code`)

| Група | Шаблон шляху | Кількість | Одиниця / режим імітації | Куди в payload |
|---|---|---|---|---|
| Потужність верстатів | `energy/consumers/<WC>/p_now` для 35 робочих центрів | 35 | кВт, `machine` (за `working_state`) | `energy.consumers[WC].p_now`; клієнт також пише в `workcenters[WC].energy.p_now` (R-19 клієнт: після патчу сигналу `energy/consumers/X/p_now` дублювати в `workcenters[X].energy.p_now`) |
| Енергія верстатів за зміну | `energy/consumers/<WC>/kwh_shift` | 35 | кВт·год, `energy` (інтеграл) | `energy.consumers[WC].kwh_shift` |
| Інженерні споживачі | `energy/consumers/{GANTRY-1,COMPRESSOR,DUST-1,BOILER,CHARGING}/p_now`, `/kwh_shift` | 10 | кВт / кВт·год, `noise`/`energy` | `energy.consumers[...]` |
| Рухома техніка | `equipment/{FL-1..FL-5,FL-C1,FL-C2,TUGGER-1}/battery`, `/hours` | 16 | `%` → частка, `drain`; год, `hours` | `equipment[code].battery/hours/state` |
| Портал | `equipment/GANTRY-1/cycles_today` (`counter`), `/vacuum_kpa` (`noise`, тривога `above -60`) | 2 | шт; кПа | `equipment["GANTRY-1"]` |
| Компресор | `equipment/COMPRESSOR/pressure_bar` (тривога `below 6.0`), `/load` (`%` → частка), `/hours` | 3 | бар; %; год | `equipment["COMPRESSOR"]` |
| Аспірація | `equipment/DUST-1/airflow_m3h`, `/filter_dp_kpa` (`drift`, тривога `above 1.8`) | 2 | м³/год; кПа | `equipment["DUST-1"]` |
| Котельня | `equipment/BOILER/supply_c`, `/silo_fill` (`%` → частка, `level`) | 2 | °C; % | `equipment["BOILER"]` |
| Спринклери, пневмокільце | `equipment/SPRINKLERS/pressure_bar` (тривога `below 6.5`), `equipment/AIR-RING/pressure_bar` (`below 6.0`) | 2 | бар | `equipment[...]` |
| Вентиляція | `ventilation/units/<U>/airflow_m3h` (29), `/supply_c` (26), `/filter_dp_pa` (26, `drift`, тривога `above 250`, заявка `MR/00035` для `RV-05`) | 81 | м³/год; °C; Па | `ventilation.units[U]` |
| Пожежна | `fire/groups/FA-FAC/dust` (`%` → частка, `drift`, тривога `above 90`, заявка `MR/00036`) | 1 | % | `fire.groups["FA-FAC"].dust` |
| Трансформатори | `energy/transformers/{T1,T2}/p_kw`, `/temp_c` (поріг energy: попередження 130, тривога 140 °C; відповідь № 24) | 4 | кВт; °C | `energy.transformers[T]` |
| Генерація | `infra/totals/pv_now` (`solar`), `infra/totals/chp_kw`, `infra/totals/bess_soc` (`%` → частка) | 3 | кВт; кВт; % | `infra.totals`; `energy.totals.pv_kw/chp_kw` дублюються (M-01h) |
| **Разом** | | **196** | | |

Правила застосування (M-01h): вузол шляху має існувати в payload (інакше сигнал ігнорується — так уникаємо
створення «порожніх» розділів без модуля-власника); у `/delta` сигнали приходять масивом `signals: [{path, value}]`
і клієнт застосовує їх тим самим правилом, плюс дублювання `p_now` у `workcenters[X].energy` і `pv_kw/chp_kw` у
`energy.totals`.
