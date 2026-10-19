# td_energy_viewer3d — специфікація (міст «Енергетика в 3D»)

Версія 0.2 · 19.10.2026 (v0.1 — 18.10.2026, у складі W2) · стандарт `docs/DOC_STANDARD.md` · технічне рішення: [ARCHITECTURE.md](ARCHITECTURE.md) · статус: збудовано (гілка `claude/td-energy-w4`).
Міст `td_energy` ↔ `td_viewer3d` (`auto_install`): шар «Енергетика в 3D» — розфарбування вузлів схеми Пульту за станом, маркери тривог, блок «Енергетика» в картці об'єкта сцени, перехід «Відкрити в 3D» з підсвічуванням вузла. Модуль збудовано в хвилі W2 разом із `td_energy_control`, тому **нумерація ID продовжує W2 і єдина з [../td_energy_control/SPEC.md](../td_energy_control/SPEC.md)**: M-41, M-42, V-46, V-47, UI-23…UI-27, R-57, R-58, R-26 (VX-01…VX-05, розширення ядра `td_viewer3d`), AC-278…AC-293, ТК-28, ТП-11, A-52, A-53, X-93. Вимоги FR-62…FR-65, FR-70 і контракти C-44, C-45 — [../td_energy_control/ARCHITECTURE.md](../td_energy_control/ARCHITECTURE.md) §1.3 і §2.1. Відхилення від макета (D-37) — у `td_energy_control/SPEC.md`, «Відхилення від макета».
Спирається на: `td_viewer3d` (M-01 контракт провайдера, R-25 `registerViewerExtension`), `td_energy` (W1 R-26 стан вузлів схеми `sld_state`, клієнтські реєстри `td_energy.viewer_links`, `td_energy.node_card`), `td_constructor_viewer3d` (зразок моста), `docs/ARCHITECTURE.md` §6.7. Безпека: шар лише читає, нічого не керує.

## 0. Дерево файлів модуля

Власник — **D** (план збирання W2, ARCH §6.1). Файли без літери — менеджер (каркас). Окрім самого модуля, воркер D змінює лише зазначені файли `td_viewer3d` (VX-01…VX-05); `td_energy_control` і `td_energy` цим модулем не змінюються (клієнтські правки `td_energy` — власність B, `td_energy_control/SPEC.md` §3.4).

```
odoo_addons/td_energy_viewer3d/            D  міст 3D (розд. 8.4), auto_install
├── __manifest__.py, __init__.py          (менеджер)
├── models/{__init__.py, viewer_provider.py, td_energy_node.py, res_config_settings.py}   D  M-41, M-42
├── tools/{__init__.py, layer.py}                    D  R-57
├── static/src/layer/{energy_layer.js, markers.js, colors.js, links.js, energy_layer.scss}   D  UI-23…UI-27
├── static/tests/hoot/*.test.js                      D
├── views/{td_energy_viewer3d_views.xml}             D  V-46 (налаштування шару), V-47 (серверна дія й меню)
└── tests/{test_layer_payload.py, test_delta.py, test_kiosk.py, test_deeplink.py, test_hoot.py}   D

odoo_addons/td_viewer3d/                   D  лише зазначені файли (розд. 8.4: VX-01…VX-05)
├── static/src/viewer/core.js                        D  мінімальні адитивні вставки (≤ 90 рядків)
├── static/src/action/viewer_action.js               D  `opts.onOpenAction`
├── static/tests/hoot/extension_energy.test.js       D  AC-278…AC-281
└── tests/test_r26_extension.py                      D
```

## 1. Маніфест

- `name` «Енергетика — Переглядач 3D», `version` `19.0.1.0.0`, `license` LGPL-3, `application=False`, **`auto_install=True`**.
- `depends`: `td_energy`, `td_viewer3d`. Дані модуль не створює (`data`: лише `views/td_energy_viewer3d_views.xml`): видалення модуля прибирає шар і не залишає даних.
- `assets`: `web.assets_backend` і `td_viewer3d.assets_kiosk` — `td_energy_viewer3d/static/src/layer/**/*`; `web.assets_unit_tests` — `td_energy_viewer3d/static/tests/hoot/*`.
- `post_init_hook`/`uninstall_hook`/зовнішніх Python-залежностей немає.

## 2. Моделі

Власних таблиць немає (`AbstractModel` і розширення). Нижче — M-41 і M-42 (нумерація W2).

### M-41 `td.viewer.provider.energy_layer` — провайдер шару «Енергетика в 3D» (`td_energy_viewer3d`; FR-62, R-57)

`_name = "td.viewer.provider.energy_layer"` (`AbstractModel`, **без** `_inherit` моделей переглядача — duck typing, `docs/ARCHITECTURE.md` §6.7, `td_viewer3d` M-01), `_f3d_sequence = 101` (після `td.viewer.provider.energy` 100), `_f3d_sections = ("energy",)`, `_f3d_group = "td_factory3d.group_td_user"` (як у `td.viewer.provider.energy`; кіоск-користувач теж бачить розфарбовування; `card` — лише для `group_td_energy_user` і не в кіоску). Методи: `_f3d_viewer_collect(payload, ctx)` → `deep_merge(payload.setdefault("energy", {}), {"layer": tools.layer.build(env, ctx)})`; `_f3d_viewer_delta(patch, ctx)` → якщо `ctx["changes"]` містить `td.energy` або сигнали з префіксами W1 `ENERGY_PREFIXES` — `deep_merge(patch.setdefault("energy", {}), {"layer": layer})`, інакше нічого; `_f3d_viewer_bus_models()` → `["td.signal", "td.energy"]`. `from odoo.addons.td_viewer3d.tools.payload import deep_merge` — імпорт усередині методів (як `td_energy` R-18).

### M-42 `td.energy.node` і `res.config.settings` (міст 3D) — розширення (V-46, V-47, R-58)

`td.energy.node.action_td_open_3d(code=None)` (`api.model`; група `group_td_energy_user`): повертає `ir.actions.client` `tag="f3d_viewer.action"` з параметрами R-58 (шари, режим `td_energy`, `code`). Параметри `td.energy_viewer3d.layers` (JSON-список ключів шарів GLB для «Відкрити в 3D», default `["building","zones","line","facade","energy","backup","roofdeck"]`), `td.energy_viewer3d.marker_limit` (int, default 40), `td.energy_viewer3d.show_markers` (bool, default True).

## 3. Представлення й меню

| ID | XML-id (`td_energy_viewer3d.`) | Тип / модель | Структура |
|---|---|---|---|
| V-46 | `res_config_settings_view_form_td_energy_viewer3d` | `res.config.settings` (зміна, міст) | блок «Енергетика в 3D»: `td_energy_viewer3d_layers` (Text JSON), `…_marker_limit`, `…_show_markers` |
| V-47 | `action_td_energy_3d` | `ir.actions.server` (код: `action = env["td.energy.node"].action_td_open_3d()`) | меню «Енергетика в 3D» |

Меню (`views/td_energy_viewer3d_views.xml`):

| XML-id | Назва | Батько | seq | Групи | Дія |
|---|---|---|---|---|---|
| `td_energy_viewer3d.menu_td_energy_3d` | Енергетика в 3D | `td_energy.menu_td_energy` | 90 | `td_energy.group_td_energy_user` | `action_td_energy_3d` |

## 4. Права

`ir.model.access.csv` відсутній: моделей із таблицями немає. Провайдер `td.viewer.provider.energy_layer` працює з правами користувача переглядача (`_f3d_group = td_factory3d.group_td_user`); читання вузлів/подій — `sudo()` лише на читання з відсіканням полів (R-57); `card` — лише для `group_td_energy_user` і не в кіоску. Налаштування `td.energy_viewer3d.*` змінює адміністратор у формі налаштувань (V-46).

## 5. Дані

Немає. Параметри `td.energy_viewer3d.layers`, `td.energy_viewer3d.marker_limit`, `td.energy_viewer3d.show_markers` мають значення за замовчуванням у коді (`models/res_config_settings.py`, M-42); повторне `-u` кількостей не змінює.

## 6. Крони й фонові процеси

Немає. Живі оновлення — канал `f3d_viewer` переглядача (`_f3d_viewer_bus_models()` → `td.signal`, `td.energy`) і `/f3d/viewer/delta` (R-57).

## 7. HTTP/JSON API

Власних маршрутів немає. Дані шару — ключ `energy.layer` у відповідях `/f3d/viewer/data` і `/f3d/viewer/delta` (структура — розд. 8.4.2, `meta.schema` лишається `"1.1"`); перехід у 3D — ORM-RPC `td.energy.node.action_td_open_3d(code=None)` (M-42, розд. 8.4.4).

## 8. Клієнтська та сервісна частина

Нумерація підрозділів збережена зі SPEC W2 (посилання «розд. 8.4.x» у кодових коментарях і тестах лишаються чинними).

### 8.4 «Енергетика в 3D»: міст `td_energy_viewer3d` і розширення `td_viewer3d` (власник D; FR-62…FR-65, FR-70, C-44, C-45)

**Рішення (A-52).** Шар — **окремий міст-модуль** `td_energy_viewer3d` (`depends`: `td_energy`, `td_viewer3d`; `auto_install: True`; LGPL-3), за зразком `td_constructor_viewer3d`: Python-провайдер (duck typing, контракт `td_viewer3d` M-01) віддає **адитивний** ключ `energy.layer` у payload (`meta.schema` лишається `"1.1"`: ключ вкладений у розділ `energy`, клієнт без моста його ігнорує), JS-розширення малює шар у ядрі переглядача. Обґрунтування: `td_energy` не залежить від `td_viewer3d`, а JS-імпорт `@td_viewer3d/viewer/core` у `td_energy` зламав би бандл без переглядача; наявний провайдер `td.viewer.provider.energy` (seq 100) не змінюється. Ядро переглядача для цього отримує мінімальні адитивні точки розширення (**VX-01…VX-05**, `td_viewer3d` R-26); без розширень поведінка ядра не змінюється.

#### 8.4.1 `td_viewer3d` R-26: розширення ядра (VX-01…VX-05; FR-70; AC-278…AC-281)

Розширює R-25 (`registerViewerExtension(ext)`): в `ext` з'являються **необов'язкові** члени (відсутній — нічого не робить; виключення розширення логується й не ламає ядро та інші розширення):

| ID | Член `ext` | Контракт |
|---|---|---|
| VX-01 | `colorModes: [{key, label, legend, hidden?}]` | ядро додає радіокнопки в групу «Розфарбування» (`name="cmode"`, значення `key`, підпис `label`), зберігає `colorMode`; необов'язковий прапор `hidden` ховає пункт (розширення без даних неактивне; розширення виставляє його в `applyData`, коли в payload немає свого розділу); `getState().mode` повертає `key`; `applyParams({mode})` приймає ключі розширень |
| VX-02 | `modeColor(mode, root, D) → THREE.Color \| null` | викликається з `modeColor(root)` ядра, коли `colorMode` — ключ розширення; `null` — без підсвічування; результат змішується як у вбудованих режимів (`paint`, коефіцієнт 0,45) |
| VX-03 | `applyData(api, D, info)` | `api` — як у R-25; `info = {reason: "load"\|"patch"\|"snapshot"\|"now", keys: Set<string>}`; викликається після `setData`, після кожного `applyPatch` із непорожнім патчем і після повернення «Зараз»/знімка; ядро після виклику запускає `repaintAll()`, якщо `colorMode` — режим розширення |
| VX-04 | `cardBlocks(code, D, api) → string[]` | список HTML-фрагментів, які ядро додає в кінець картки вибраного об'єкта (після `energyHtml`); екранування — відповідальність розширення (`esc`); порожній масив — нічого |
| VX-05 | `onAction(api, action, arg, el)` і `api.openAction(action) → boolean` | елементи з `data-ext="<id>:<action>:<arg>"` у картці/панелі делегуються розширенню з `id`; `api.openAction(act)` викликає `opts.onOpenAction(act)` (`viewer_action.js`: `this.action.doAction(act)`); у режимі кіоска `opts.onOpenAction` не задано → `false`; геттер `api.canOpenAction` (`!!opts.onOpenAction`) дозволяє розширенню не показувати кнопки дій, коли їх неможливо виконати |

Також `api` розширюється полями `select(code)`, `focusOn(obj)`, `codeRoot(code)` (існують) і `labelsRoot` (контейнер міток) — без змін поведінки. Файли: `td_viewer3d/static/src/viewer/core.js` (вставки ≤ 90 рядків), `static/src/action/viewer_action.js` (`onOpenAction`), тести `static/tests/hoot/extension_energy.test.js`, `tests/test_r26_extension.py`. Обмеження: `rjsmin` — без вкладених шаблонних літералів у змінюваних місцях; `dist/viewer` не оновлюється.

#### 8.4.2 Payload `energy.layer` (R-57; M-41)

```json
{"layer":{"schema":1,"thresholds":{"warn_pct":80,"alarm_pct":100},
  "nodes":[{"code":"BW-2","scene":"BW-2","kind":"line","name":"ШР-2","state":"ok","load":0.30,"i_a":192,"p_kw":124.0,"rating_a":630,
            "card":true,"alarms":0,"worst":null,"title":null},
           {"code":"C2","scene":"CABLES","kind":"line","name":"C2","state":"alarm","load":null,"i_a":null,"p_kw":128.0,"rating_a":null,
            "card":true,"alarms":1,"worst":"bad","title":"Лічильник PM-QF-C2 не на зв'язку"}],
  "alarms":[{"id":212,"node":"C2","scene":"CABLES","level":"bad","title":"Лічильник PM-QF-C2 не на зв'язку","time":"13:47","state":"active"}],
  "summary":{"alarm":1,"warn":2,"gen":1,"off":3}}}
```

Правила: `nodes` — вузли `sld_show=True` (W1 R-26; ≈ 21) видів `line`, `transformer`, `cell` (feeder/cable/incomer/coupler/pfc), `generator`, `storage`, `ats`, `section`; `state` = `td.energy.node.sld_state` (`ok|warn|alarm|off|gen`, **та сама логіка й пороги `td.energy.load_warn_pct/_alarm_pct`, що в Пульті**); `load` — частка 0…∞ (`p_now / номінал`, W1 R-26) або `null`; `scene` — код об'єкта сцени: `equipment_id.td_code`, інакше `node.code`; для кабельних ліній `C1`, `C2` — `CABLES` (єдиний об'єкт сцени; стан об'єкта = найгірший серед вузлів з тим самим `scene`); `scene=null`, якщо коду немає серед відомих кодів сцени (множина з `ctx["static"]` — `model_static.json` `td_viewer3d`: `energy.lines|transformers|cells`, `equipment`, `zones`; воркер D бере наявний завантажувач статики `td_viewer3d.tools.payload`; якщо множину отримати неможливо — `scene = equipment.td_code or node.code` без перевірки, A-53) — вузол лишається в списку (картка доступна), але не розфарбовується й не має маркера; `alarms[]` — відкриті `td.energy.event` (`state in ('active','acked')`, `level in ('warn','bad')`, `node_id`), ≤ `marker_limit` (40), сортування `bad` → `warn`, далі за часом; `title` ≤ 80 символів; `time` — Київ `HH:MM`; `card` — `false` у кіоску й без групи; ключі вартості та імена користувачів (`acked_by`, `assigned_user_id`) **не віддаються**; для `ctx["kiosk"]` — `title` без технічних деталей діагностики. Розмір `layer` ≤ 12 КБ, побудова ≤ 150 мс (ТП-11). Дельта (`_f3d_viewer_delta`) — **повна заміна** `layer` (списки замінюються цілком за `deep_merge`).

#### 8.4.3 Клієнт моста (UI-23…UI-27)

`registerViewerExtension({colorModes, modeColor, applyData, cardBlocks, onAction})` у `static/src/layer/energy_layer.js`:

| ID | Компонент | Поведінка |
|---|---|---|
| UI-23 | `EnergyLayerExtension` | Тримає `state = {byScene: Map, alarms, version}` з `D.energy.layer`; `applyData` оновлює карту й маркери (лише якщо `info.keys` містить `energy`); без `D.energy.layer` (старий сервер) — розширення неактивне, режим не показується (`colorModes[].hidden = !layer`, VX-01) |
| UI-24 | `StateColors` | Режим `td_energy` «Електромережа: стан вузлів» (легенда: «норма», «увага ≥ {warn_pct} %», «тривога ≥ {alarm_pct} % / немає даних», «генерує/працює», «вимкнено/резерв»); `modeColor`: `ok` → `C_OK` (`#27ae60`), `warn` → `C_WARN` (`#f39c12`), `alarm` → `C_BAD` (`#e74c3c`), `gen` → бурштиновий (`#b45309`), `off` → сірий (`#9ca3af`); кодування не лише кольором: у картці — текстовий чип стану |
| UI-25 | `AlarmMarkers` | Для кожного запису `alarms[]` зі `scene` — спрайт (канва 64 × 64: коло `--bad`/`--warn`, знак «!») над найвищою точкою `codeRoot(scene)` (`Box3`), `renderOrder` вищий за сцену, масштаб сталий у пікселях; пульсація (`reduceMotion` вимикає); клік по маркеру — `api.select(scene)`; підказка `title` + час зберігається в `userData.tooltip` спрайта, але **підказку при наведенні в збірці не реалізовано** (ядро не показує tooltip; див. «Журнал змін документа»); ≤ `marker_limit`; зняття/перебудова при `applyData`; `dispose` геометрії/текстур; прихований, коли `show_markers=false` або шар `energy` вимкнений |
| UI-26 | `NodeBlock` | `cardBlocks(code)`: блок «Енергетика»: чип стану («Норма», «Увага», «Тривога», «Генерує», «Вимкнено»), `P {p_kw} кВт`, `{i_a} А · {load%}` (якщо є), перелік тривог вузла (≤ 3) і кнопка «Відкрити картку вузла» (`data-ext="td_energy:open_card:<node code>"`) — лише якщо `card=true` і дозволено `openAction` (`api.canOpenAction`, не кіоск); `onAction` → `api.openAction({type:"ir.actions.client",tag:"td_energy.node_card",name:<code>,params:{code}})` (V-23 W1) |
| UI-27 | `ViewerLinks` | Реєструє `registry.category("td_energy.viewer_links").add("default", {open})`, де `open({code})` викликає `orm.call("td.energy.node","action_td_open_3d",[code\|\|null])` і `action.doAction(result)`; без модуля `td_viewer3d` запис не реєструється (міст `auto_install` не встановлюється) |

#### 8.4.4 «Відкрити в 3D» і підсвічування вузла (R-58; FR-64)

`td.energy.node.action_td_open_3d(code=None)` повертає `{"type":"ir.actions.client","tag":"f3d_viewer.action","name":"Завод 3D","target":"current","params":{"layers":<td.energy_viewer3d.layers>,"mode":"td_energy","tab":"energy","code":<scene|null>,"td_energy_node":<code|null>}}`: `code` вузла перетворюється на `scene` за правилами 8.4.2; невідомий `code` → `UserError("Вузол %s не знайдено.")`; вузол без `scene` → `params.code = null` і повідомлення-попередження в клієнті «Для вузла {code} немає об'єкта в 3D; відкрито шар «Енергетика»». Переглядач (`applyParams`): `layers` → `mode` → `tab` → `code` (`select(ensureCode(code))` + `focusOn`); вибраний вузол отримує жовту обвідку ядра (`C_SEL`) і блок UI-26; маркер вибраного вузла пульсує. Точки входу в Odoo: (1) Пульт, «Відкрити в 3D» (UI-01 W1) → `viewerLinks.default.open({})`; (2) панель вузла схеми й картка вузла, «Показати в 3D» → `open({code})`; (3) мобільний «Де це в 3D» → `open({code})`; (4) меню «Енергетика в 3D» (V-47). Назад: у картці переглядача (UI-26) — «Відкрити картку вузла»; з картки — крихти W1.

## 9. Алгоритми й правила

### R-57 Шар «Енергетика в 3D»: правила payload

Описано в розд. 8.4.2 (структура `energy.layer`, стани, вибір `scene`, маркери, кіоск, розмір). Додатково: `thresholds` беруться з `td.energy.load_warn_pct/_alarm_pct` (W1 §5.1), тому колір вузла в 3D збігається з Пультом (AC-284); провайдер не пише в БД і працює з правами користувача (`_f3d_group`), читання вузлів/подій — `sudo()` лише на читання з відсіканням полів за описом.

### R-58 «Відкрити в 3D» і підсвічування вузла

Описано в розд. 8.4.4 (`action_td_open_3d`, параметри `f3d_viewer.action`, порядок `applyParams`, точки входу).

## 10. Стани й переходи

Станів немає. Стан вузла — `ok|warn|alarm|off|gen` (`td.energy.node.sld_state`, W1 R-26), маркер — `bad|warn`; режим розфарбування `td_energy` вмикається користувачем або параметром `mode` дії `f3d_viewer.action`.

## 11. Обробка помилок

- Старий сервер/немає `D.energy.layer` → розширення неактивне, режим розфарбування прихований (`colorModes[].hidden`), блоки картки порожні.
- Виключення розширення логується й не ламає ядро переглядача та інші розширення (R-26).
- `action_td_open_3d`: невідомий `code` → `UserError("Вузол %s не знайдено.")`; вузол без об'єкта в сцені → `params.code = null` і попередження в клієнті; без модуля `td_viewer3d` запис `td_energy.viewer_links` не реєструється.
- Шина недоступна — оновлення з резервного опитування переглядача; час — Київ `HH:MM` (R-63 `td_energy_control`).

## 12. Acceptance Criteria

Колонки як у `td_energy_control/SPEC.md` §12. AC-278…AC-281 — розширення ядра `td_viewer3d` (R-26), AC-282…AC-293 — міст.

### 12.1 Розширення ядра переглядача (R-26) — AC-278…AC-281

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-278 | FR-65, FR-70 | Given розширення з `colorModes`/`modeColor` (VX-01/02); Then радіо в групі «Розфарбування», `applyParams({mode})` вмикає режим, `modeColor` фарбує, `getState().mode` = ключ; виключення розширення логується, ядро й інші розширення працюють; без розширення режими не змінюються | UT-JS |
| AC-279 | FR-65, FR-70 | Given VX-03; Then `applyData(api, D, info)` після `load/patch/snapshot/now` з `info.keys`; для режиму розширення після виклику `repaintAll()` | UT-JS |
| AC-280 | FR-65, FR-70 | Given VX-04/05; Then `cardBlocks` додаються в картку; клік по `data-ext` → `onAction`; `api.openAction` → `opts.onOpenAction`; у кіоску → `false` (`api.canOpenAction` = `!!opts.onOpenAction`) | UT-JS |
| AC-281 | FR-65, FR-70 | Given регресія; Then `td_constructor_viewer3d` (`applyLayout`) і AC-01…AC-67 переглядача зелені; `registerViewerExtension` без нових членів працює як раніше | UT |

### 12.2 «Енергетика в 3D» — AC-282…AC-293

| AC | FR | Given / When / Then | Тип |
|---|---|---|---|
| AC-282 | FR-62 | Given демо-БД; When `td.viewer.provider.energy_layer._f3d_viewer_collect`; Then `energy.layer` за схемою 8.4.2 (≈ 21 вузол, `thresholds` 80/100, `alarms`); `meta.schema` лишається `"1.1"`; `_f3d_sequence=101`; користувач без `td_factory3d.group_td_user` — розділ `denied` | UT |
| AC-283 | FR-62 | Then `scene` = `equipment.td_code` або `node.code`; `C1`,`C2` → `CABLES`; невідомий код → `scene=null` (вузол у списку, без маркера); стан об'єкта сцени = найгірший серед вузлів з тим самим `scene` | UT |
| AC-284 | FR-62 | Given приклад 14:20 (W1 R-26); Then `state` збігається з `td.energy.node.sld_state` і Пультом: `C2` alarm, `PFC-2` warn, `PV-INV` gen, `CHP` off, `ATS-1` off, `QS` off, `T2` ok; пороги змінюються разом із `td.energy.load_*_pct` | UT |
| AC-285 | FR-62 | Then `alarms[]` — лише `active/acked`, `warn\|bad`, ≤ `marker_limit`, `bad` першими, `title ≤ 80`; немає `acked_by`/користувачів/вартості | UT |
| AC-286 | FR-62 | Given зміна `td.energy` або енергетичного `td.signal`; When `_f3d_viewer_delta`; Then `patch.energy.layer` — повна заміна (списки не конкатенуються); інші зміни — без `layer` | UT |
| AC-287 | FR-62 | Given `ctx.kiosk`; Then розфарбування й `alarms` є, `card=false`, `title` без технічних деталей діагностики; користувач без `group_td_energy_user` (не кіоск) — теж `card=false` | UT |
| AC-288 | FR-62 | Given `StateColors`; When `modeColor('td_energy', root)`; Then `ok`→зелений, `warn`→жовтий, `alarm`→червоний, `gen`→бурштиновий, `off`→сірий; невідомий `scene` → `null`; легенда містить пороги | UT-JS |
| AC-289 | FR-62 | Given `AlarmMarkers`; Then спрайти для `alarms[]` зі `scene` у `codeRoot`, ≤ ліміту; знімаються/`dispose` при оновленні й вимиканні шару; `reduceMotion` вимикає пульсацію; клік → `api.select(scene)` | UT-JS |
| AC-290 | FR-63 | Given `NodeBlock`; Then чип стану, `P`, струм/%, ≤ 3 тривоги, кнопка «Відкрити картку вузла» лише при `card` і наявності `openAction`; клік → `openAction` `td_energy.node_card` з `params.code` | UT-JS |
| AC-291 | FR-64 | When `action_td_open_3d('BW-2')`; Then `f3d_viewer.action` з `layers` (параметр), `mode='td_energy'`, `tab='energy'`, `code='BW-2'`; вузол без об'єкта в сцені (приклад у тесті: `BW-4` з `equipment_id.td_code`, якого немає в сцені; `PFC-2` **є** в сцені, тож `scene` не порожній) → `code=null`, `td_energy_node='BW-4'`; невідомий код → `UserError`; без `code` — лише шар | UT |
| AC-292 | FR-64 | Given td_energy client (§3.4 п.1); Then «Відкрити в 3D» і «Показати в 3D» (Пульт, панель вузла, картка, мобільний) використовують `viewerLinks.default`; без моста — шлях W1/сповіщення; ключ `layer` виправлено на `layers` | UT-JS |
| AC-293 | FR-62…FR-64 | Given стенд (ТК-28); When «Відкрити в 3D» → режим «Електромережа: стан вузлів», маркер на `C2`; клік по ШР-2 → блок «Енергетика» → «Відкрити картку вузла» відкриває `td_energy.node_card`; «Показати в 3D» для `BW-2` підсвічує вузол; зміна стану (сценарій емулятора) оновлює колір і маркери ≤ 10 с; скріншоти | TC/MAN |

## 13. План тестування

### 13.1 Юніт-тести

**Міст 3D і переглядач (D)**: `td_energy_viewer3d/tests/{test_layer_payload.py::TestLayerPayload (AC-282…AC-285), test_delta.py::TestDelta (AC-286), test_kiosk.py::TestKiosk (AC-287), test_deeplink.py::TestDeepLink (AC-291), test_hoot.py::TestEnergyLayerHoot (AC-288…AC-290)}`; `td_viewer3d/static/tests/hoot/extension_energy.test.js` (AC-278…AC-280); `td_viewer3d/tests/test_r26_extension.py` і повний прогін `/td_viewer3d` + `/td_constructor_viewer3d` (AC-281).

Команда: `F3D_TEST_INSTALL=td_energy,td_viewer3d,td_energy_viewer3d factory3d/tools/odoo/run_tests.sh <db> /td_energy_viewer3d` (Python + hoot `TestEnergyLayerHoot`); регресія переглядача — `F3D_TEST_INSTALL=td_factory3d,td_viewer3d,test_td_viewer3d,td_constructor,td_constructor_viewer3d factory3d/tools/odoo/run_tests.sh <db> /td_viewer3d` і `/td_constructor_viewer3d`.

### 13.2 Стендовий сценарій

| ТК | Назва | Кроки | Очікується |
|---|---|---|---|
| ТК-28 | 3D (AC-293) | Пульт → «Відкрити в 3D»; клік по ШР-2; «Відкрити картку вузла»; Пульт → вузол `BW-2` → «Показати в 3D»; змінити стан (`pfc_step_fault`/відключення лічильника) | режим «Електромережа: стан вузлів», маркери за тривогами, блок «Енергетика», перехід у картку, підсвічування вузла; колір/маркер оновлюються ≤ 10 с; кіоск без картки |

### 13.3 Тести безпеки

Кіоск (`ctx.kiosk`) і користувач без `group_td_energy_user`: `card=false`, немає імен користувачів/вартості (AC-285, AC-287); користувач без `td_factory3d.group_td_user` — розділ `denied` (AC-282).

### 13.4 Тести продуктивності

- ТП-11: `energy.layer` ≤ 12 КБ, побудова ≤ 150 мс на 123 вузлах; дельта ≤ 100 мс; клієнт — ≤ 40 маркерів без падіння нижче 30 кадр/с на планшеті (MAN).

## 14. Definition of Done

- Усі AC-278…AC-292 (UT/UT-JS) зелені; AC-293 (ТК-28, скріншоти) прийнято.
- Регресія переглядача зелена: `td_viewer3d` (AC-01…AC-67), `td_constructor_viewer3d`, `td_energy`.
- `ruff` без помилок; JS — перевірка `rjsmin` (без вкладених шаблонних літералів у змінюваних місцях `core.js`); README модуля.

## 15. Відкриті питання й рішення автора

Відкритих питань немає. Рішення автора (нумерація W2):

| ID | Рішення | Обґрунтування |
|---|---|---|
| A-52 | Шар 3D — міст `td_energy_viewer3d` + адитивні VX-01…VX-05 у `td_viewer3d`; ключ `energy.layer` не змінює `meta.schema` | `td_energy` не залежить від `td_viewer3d`; зразок `td_constructor_viewer3d` |
| A-53 | `scene` вузла = `equipment.td_code` або `node.code`; `C1`/`C2` → `CABLES` (найгірший стан); маркери малює клієнт | Модель сцени має один об'єкт кабелів |
| X-93 | (`td_viewer3d`) VX-01…VX-05 адитивні; ядро не залежить від `td_energy`; без розширень поведінка не змінюється | Сумісність із `td_constructor_viewer3d` |

## Журнал змін документа

| Дата | Версія | Зміна |
|---|---|---|
| 18.10.2026 | 0.1 | Розділ 8.4 і пов'язані ID у складі `W2_SPEC.md` (хвиля W2, воркер D) |
| 19.10.2026 | 0.2 | Виокремлено в окремий SPEC моста; переклад українською; додано рішення збірки: ключ `show_markers` (параметр `td.energy_viewer3d.show_markers`, `layer.show_markers`), прапор `colorModes[].hidden` (VX-01), геттер `api.canOpenAction` (VX-05); виправлено очікування AC-291 (`PFC-2` є в сцені, тест — вузол `BW-4` з `equipment_id.td_code` поза сценою); **не реалізовано:** підказка маркера при наведенні (`userData.tooltip` готовий, ядро tooltip не показує); слоти «тест ДГУ» в розкладі — у `td_energy_control` (R-54 п.7, A-66) |
