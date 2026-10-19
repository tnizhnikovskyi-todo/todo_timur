# Ядро конструктора (CD-29): одне на модуль Odoo й прототип

JS + Three.js **без Odoo**: жодних імпортів `@web`, `@odoo`, `@td_constructor`, лише відносні (`./x.js`). Дані — через ОДИН впроваджений
адаптер; three.js, умовні моделі, тема й форми запису приходять від хоста. Перевіряє `node tools/test_core.mjs`.

## Розкладка

| Файл | Що |
|---|---|
| `index.js` | точка входу збірки: `mountEditor/unmountEditor`, реєстри, контракт, простори імен для тестів і мостів; **підключає заглушки волн 1–2** |
| `app.js` | монтування, завантаження площадки, автозбереження, події шапки, `hotkeys`, життєвий цикл |
| `state.js` · `util.js` · `data.js` | `S`/`V`/`E` (стан, сцена, функції між модулями), утиліти, довідники й описи шаблонів |
| `cells.js` · `geometry.js` · `checks.js` · `live.js` | R-01…R-10: комірки, OBB/SAT, перевірки (дзеркала Python, золоті фікстури), «живі» перевірки |
| `scene.js` · `panels_left.js` · `panels_right.js` · `dialogs.js` · `fields.js` · `dxf.js` · `roles.js` · `body.js` | 3D-сцена, панелі, діалоги, підкладка DXF, права, розмітка |
| `adapter.js` | **контракт адаптера**, `BaseAdapter`, `assertAdapter`, `newUid`, `StoreError` |
| `adapter_odoo.js` | `OdooAdapter` (API `/f3d/constructor/*`; `rpc`, `orm`, `action`, `uploadModel` передає хост) + перетворення API↔стан |
| `artifact/` | лише прототип: `ArtifactAdapter` (db → localStorage → пам'ять, IndexedDB), `sample.js` (+`seed/sample.json`, `fromProto`), діалоги каталогу й публікації, перевірки навантаження прототипу |
| `registry.js` | реєстри точок розширення |
| `host.js` · `three.js` | сервіси хоста й контейнер `THREE` |
| `types_catalog.js` … `i18n.js` | слайси S1…S6 (див. «Волни» і розділ S3 нижче); незаповнені — заглушки |

## Слайс S3 «Робота зі складом» (F05, F06, F07, F09-01…05/08…10, N-02, N-05, N-08)

| Файл | Що |
|---|---|
| `undo.js` | скасування/повтор (F09-01): знімок після кожної зміни (шари, місця, розміщення, правила S2 `S.site.rules`, поля площадки: адресація S1, габарит/крок колон/висоти/техніка складу S5); підпис кроку — `E.undoLabel(текст)`, `E.commit({label})` чи виведений із різниці; `E.undo/redo/undoReset/undoRebase`; відновлення — звичайний `E.commit`, тож адаптер сам ставить create/write/unlink; зміну адресації відновлює `saveAddr`, габарит і крок колон — `E.saveSiteProps`, висоту до спринклерів і техніку складу — `adapter.saveSite` |
| `selection.js` · `edit_tools.js` | мультивиділення `S.multi` (Ctrl+клік, рамка Shift у «Плані», групове перетягування, панель «Виділено N»), дублювання Ctrl+D, копіювати/вставити Ctrl+C/V, масив N×M, масове створення в зоні, вирівнювання/розподіл, групи в зону, властивості кількох |
| `labels.js` · `barcode.js` | етикетки (F05): вибір комірок, вміст, розкладка аркуша, SVG/PNG, ZPL, тіло запиту PDF; Code128 і QR без залежностей (еталон Python — `tests/golden_s3.py`) |
| `stock_state.js` · `heat.js` | залишки в `S.stock` (пачки API-13), теплові карти (F07): показники в реєстрі `metrics`, легенда з числом місць у класах, вибір запам'ятовується |
| `search.js` · `card.js` · `s3_chrome.js` | «Перейти до місця» й «Де лежить» (F06-01/02), картка місця й підказка при наведенні (F06-03/05), мобільний режим ≤ 768 px (F06-04; стилі вбудовано в `s3_chrome.js`), кнопки ↶ ↷, перемикач «Показник» |
| `draft.js` | рівні доступу `E.access()` (Перегляд / Проєктування / Застосування, N-02), статуси «не збережено» / «нове · лише в моделі» / «з Odoo» (N-05, N-08), «Зберегти все», «Скинути до даних Odoo», довідка гарячих клавіш |
| `artifact/demo_stock.js` | лише прототип: синтетичні залишки з позначкою «демо» (F07-08) |

Хуки: `E.lifecycle.mount/unmount` (множини функцій на монтування), `E.access()/accessHint(need)`, `E.objStatus(kind, rec)`, `E.recolorCells()`.
Ключ `S.ui.metric` ділиться з підсвіткою правил S2 (`rule_target`): чужий ключ у перемикачі «Показник» показується як «звичайний».

**Адаптер** (`capabilities.stock`, `capabilities.render`): `stock({codes?, days?, detail?, offset?})` → API-13 `/stock/state`
`{at, days, demo, truncated, next, codes: {код: {qty, reserved, fill, in_date, age_days, moves, min, max, capacity, top_product, location_id, detail?}}}`;
великий склад віддається пачками (≤ 2 МБ, 2000 локацій): поки `truncated`, ядро повторює виклик з `offset: next`. `detail` (до 20 кодів, для картки) —
`{rows, moves, rules, category, record: {model, id}}`; `record` ядро передає в `E.openRecord` («Відкрити в Odoo»), не знаючи імені моделі (CD-30).
`find({q, mode})` → API-14 `/stock/find` → `{hits: [{code, items: [{product, ref, qty, lot, package}]}]}` (усі слова — в одному залишку).
`render(kind, payload)` → API-19 `/render/<kind>` → `{filename, mimetype, content (base64)}`; `labels_pdf`: `payload.format` — `pdf` (за замовчуванням)
або `png` (один аркуш — PNG, кілька — ZIP; **не більше 12 аркушів**, ліміт PDF — параметр `td.constructor.labels_max`). Прототип: `stock/find` — демо,
`render` недоступний («PDF формує сервер»), ZPL і PNG будуються локально. `fill` на сервері: заповнення за ємністю товару категорії зберігання, інакше вага
запасу проти ліміту комірки від сервісу ємності S2 (`capacity.stock_loads`, `capacity.site_cell_limits`).

## Слайс S4 «Структура з Odoo, файли, авторозкладка» (F10, F11, F17, F02-09/12)

| Файл | Що |
|---|---|
| `parse_codes.js` | розбір кодів локацій (F10-01…03): правила `site.parse_rules` (маска `{ряд}-{секція}-{ярус}`, `{x:a}` літери, `{x:A-D}`/`{x:1-5}` діапазони, `*`; або regex із групами row/bay/level/zone/pos/prefix), далі шаблон адресації S1 і правило «як зараз»; діалог «Розбір кодів» |
| `structure.js` · `tray.js` | структура з локацій чи рядків файла → зони, ряди/яруси, місця на підлозі; нерозібране без зони-батька — лоток «Не розміщено» (`site.parse_rules.tray`, ≤ 5000); `commitStructure` і розміщення з лотка — ОДНА звичайна зміна (Ctrl+Z) |
| `tabular_core.js` · `tabular.js` · `files_ui.js` | CSV/XLSX без залежностей (власний zip/deflate), формат імпорту `stock.location` (заголовки EN/UK/RU), діалоги «Імпорт» і «Експорт» (усі місця або «нові й змінені» відносно Odoo з недостаючими батьками) |
| `sync_ui.js` | «Оновити з Odoo» (F02-12) і розбіжності (F02-09): з'явилося / зникло / перейменовано / інший батько; «Прийняти з Odoo» чи «Залишити моє» — одна зміна, далі база порівняння оновлюється |
| `autolayout.js` | авторозкладка (F17): зони по горизонталі полицями, ряди вглиб; панелі зони й площадки, пункт меню «Ще» |
| `artifact/sample_locations.js` | лише прототип: демо-стрічка локацій і `diffFeeds` (дзеркало `services/odoo_sync.diff_feeds`) |

**Адаптер** (`capabilities.odoo_import`): `locations({op})` → API-16 `POST /f3d/constructor/odoo/locations` (`op`: `feed` — стрічка `{root, warehouse, locations: [{id, code,
name, parent, parent_id, usage, barcode, qty, active}], truncated, next}` пачками `offset/limit`; `sync` — те саме без списку + `diff` і `baseline: created|existing|missing`;
`baseline` — база порівняння := нинішня стрічка). База — вкладення `site.odoo_baseline_id`; крім «Оновити з Odoo» її оновлює **успішна публікація** (`publish.apply_plan` →
`odoo_sync.save_baseline`), тож створене публікацією не показується як розбіжність. `saveParseRules(rules)` → `POST /f3d/constructor/odoo/rules` (`site.parse_rules`: правила + лоток;
окремий маршрут, бо ORM площадку проєктувальнику не пише; лічильник чернетки збільшується); `parseTable({filename, bytes, sheet})` → API-20 `POST /f3d/constructor/parse/table` (`{format, sheets?, rows}`, XLSX читає
openpyxl, CSV — UTF-8/Windows-1251). Прототип: усе локально (`ArtifactAdapter.locations` — демо-стрічка, база — у сховищі `<площадка>.baseline`).

**Авторозкладка.** `autoLayoutZone(id)` — ряди вглиб у межах зони (її розмір фіксований); `autoLayoutSite({layerId})` — зони полицями в контурі, ряди вглиб у зонах (зона без `fixed`
отримує розмір за вмістом). Чисті `layoutLines`, `packRects`, `layoutPlan` не торкаються стану; застосування — один `E.commit` з підписом, номери рядів і коди зон перед рухом
закріплюються (S1: коди комірок не залежать від геометрії). Не вміщається — нічого не змінюється, у повідомленні потрібний розмір.

*Перешкоди* (`layerObstacles(шар)`, прямокутники `[x0, y0, x1, y1]`): проходи й пожежні шляхи шару, `layer.items`, розміщення шару, місця під верстати, **об'єкти будівлі S5**
(`E.buildingObstacles()` = `obstacleRects(S.layers, S.site)` з `building_core.js`: колони, стіни, офіс, зарядка шарів `building` і колони `site.column_grid` — 0,4×0,4 м у вузлах сітки;
ворота, док і двері — прорізи, не перешкоди); стіни, повернуті не на кратний 90°, мають `.obb` і перевіряються за справжньою формою (SAT). Зони складних контурів (`locked`) не рухаються.
*Контур* (`regionOf(шар)` → `{x0, y0, x1, y1, poly?}`): `bounds` шару — масив точок `[[x, y], …]` (≥ 3), інакше контур шару `building` / габарит площадки (`contourOf`); для многокутника
зона має лежати цілком усередині (`obbInsidePolygon`, відступ 0,5 м), виріз обходиться. Колони `column_grid` обходяться, поки це можливо: якщо з ними зони не вміщаються,
а без них вміщаються (крок сітки менший за зону), розкладка йде без колон сітки (`layoutAroundBuilding` → `gridIgnored`, у повідомленні названо крок); стіни, офіс, зарядка й явні
колони дотримуються завжди. Не вміщається й без колон сітки — нічого не змінюється, причина називає перешкоди і крок сітки. Так само розкладає й `structure.js` (імпорт структури).

## Слайс S5 «Будівля, документи, майстер» (F15, F16, F18, N-06, N-07)

| Файл | Що |
|---|---|
| `building_core.js` | чисте ядро без DOM: об'єкти будівлі (`newItem`, `itemToApi`, `columnGrid`, `contourWalls`), контур (`contourOf`, `isSimplePolygon`, `nearestEdge`), проходи (вузли графа, `moveAisle`), прив'язка, техніка складу (`TECHS`, `parseTech`), перевірки `inside` / `aisle_width` / `height`, `obstacleRects`; дзеркало — `services/building.py`, `services/checks_building.py` (золота фікстура `fixtures/s5_golden.json`) |
| `building.js` · `building_ui.js` · `building_3d.js` | реєстрація перевірок і `E.buildingObstacles`; режим «Будівля» (контур, колони, стіни, ворота, док, двері, офіс, зарядка, проходи, лінійка й рулетка, техніка, висоти); 3D будівлі (instancing колон, лінія спринклерів) |
| `spec.js` · `plan_doc.js` · `docs_ui.js` | документи (F15): специфікація стелажів (рами, балки, полиці, стійки, консолі, зв'язки; CSV локально, XLSX/PDF — сервер) і план складу (SVG/PNG локально, PDF — вектором на сервері); область документа (зона/ряд) |
| `wizard.js` | майстер «З нуля» (F16): Будівля → Зони → Ряди → Адресація → Перевірки → План змін; вкладка лівої панелі, кожен крок — звичайна зміна; стан майстра — `site.wizard_state` |

*Формат `items`* (шар `building`, R-22; API-04 пише їх у `td.layer.items`, ≤ 5000): `{id, kind: column|wall|gate|dock|door|office|charger, name, x, y, w, d, rot (°), [th] (стіна), [h],
location_uid (лише gate/dock — «Пов'язати з локацією»)}`; усе — прямокутники (OBB): центр `(x, y)`, довжина `w` уздовж осі `rot`, глибина `d`. Контур — `layer.bounds` шару `building`;
проходи — осьові прямокутники `layer.aisles`. Поля площадки: `building {length, width, height}`, `column_grid {step_x, step_y}`, `sprinkler_height`, `aisle_tech`
(`ключ` або `ключ:мін_м`; зона має власне `tech`) — усе входить у знімок скасування (`undo.js`: Ctrl+Z відкочує габарит, висоти й техніку, відновлення викликає
`E.saveSiteProps` / `adapter.saveSite`).

**Адаптер** (`capabilities.render`, `capabilities.files`): `render(kind, payload)` → API-19 `POST /f3d/constructor/render/<kind>` → `{filename, mimetype, content (base64)}`; рендерери
реєструються в `services.registry.RENDERERS`: `labels_pdf` (S3), `table_xlsx` (S4/S5: `{rows, sheet}` → XLSX), `spec_pdf` (`format: pdf|xlsx`, таблиці специфікації), `plan_pdf` (`ops` —
той самий список примітивів у мм, що малює SVG ядра). `saveWizard(state)` → `POST /f3d/constructor/site/wizard` (state ≤ 256 КБ, вкладеність ≤ 8; без state — читання; права: менеджер
або проєктувальник із правом на шар; лічильник чернетки не змінюється). `warehouses()` — склади для вибору в майстрі. `saveSite({sprinkler_height, aisle_tech, building, column_grid})` — поля
площадки стандартним ORM.

## Контракт адаптера (`adapter.js`)

`load(siteId)` → стан · `save(state, {now})` (порівняння зі станом адаптера, черга, автозбереження) · `flush()` · `check(layerId?)` ·
`publish({onClose, state})` · `uploadModel(variantId, payload)` · `restoreVersion(id)` · `listSites()` · `createSite(o)` · `saveSite(vals)` ·
`saveCheck(key, vals)` · `loadModel(variant, THREE)` · `attachUnderlay/detachUnderlay/loadUnderlay` · `ensureGroupIds(roles)` · `capabilities` ·
зворотні виклики `onStatus/onSaved/onConflict/onReject/onReload`. Стан (`site`, `layers`, `slots`, `placements`, `catalog`, `settings`,
`versions`, `rights`) описано в шапці `adapter.js`. У ядрі — нейтральні терміни («місце зберігання», «категорія», «правило»): імена
`stock.*` знає лише `adapter_odoo.js` (CD-30). Нова можливість адаптера: додати ім'я в `CAPABILITY_NAMES` (registry.js), виставити в
`capabilities`, ховати функцію через `can(name)`.

## Реєстри (`registry.js`)

`panels` (вкладки лівої панелі `area:"left"`; блоки правої `area:"right"|"site"|"slot"|"placement"`) · `dialogs` (`newSite`, `history`,
`serverIssues`, `conflict`, `confirm` + від хоста `variantForm`, `passportForm`, `record`) · `checks` (`{run, config?}`; `runChecks`
ітерує реєстр) · `shapes` (каркаси шаблонів; нові форми типів) · `metrics` (колір комірки за `S.ui.metric`) · `menu` (`top`/`more`) ·
`hotkeys` (`{code|key|match, run, typing?}`) · `capabilities`. Запис: `registries.X.add(key, value, {sequence, force})`; повторний
ключ без `force` — помилка. Слайс реєструється **з свого файлу** (заглушка вже підключена в `index.js`).

## Збірка й тести

```
node tools/build_core.mjs module [--check]   # → odoo_addons/td_constructor/static/lib/f3d-core/constructor.esm.js (коміт; оновлює CORE_BUILD)
python3 build/constructor/proto/build.py     # → build/constructor/proto/index.html (esbuild IIFE + стилі модуля)
node tools/test_core.mjs                     # Node, без Odoo; з ESBUILD_DIR перевіряє свіжість збірки модуля
```

`ESBUILD_DIR` — каталог з `node_modules/esbuild` (без нього збірка робить `npm install esbuild` у тимчасовий каталог). Після правки `core/`
**перезберіть модуль** і закомітьте `constructor.esm.js` (при паралельних слайсах конфлікт у ньому розв'язується перезбіркою).

- Модуль: дія `static/src/action/constructor_action.js` → `static/src/editor/odoo_host.js` (хост, діалоги форм Odoo) → `core_loader.js`
  (динамічний import збірки). HOOT-тести редактора беруть ядро через `tests/editor/core.js` (`beforeEach(setupCore)`).
- Прототип: `build/constructor/proto/src/main.js` (хост артефакта) + `page.css`; стилі редактора — `constructor_action.scss` модуля.
  Playwright-тести — `build/constructor/proto/test_*.js` (потрібні каталоги `vendor/` і `fixtures/` поза репозиторієм).

## Що змінюється разом з ядром

Умовні 3D-моделі (`model/generic.js`) і завантажувачі моделей (`model/*`) лишаються в модулі (W3): хост передає `buildGenericModel` /
`loadLoaders`; прототип збирає `model/generic.js` тим самим esbuild. Імпорт моделей у прототипі (`artifact/adapter_artifact.js`
`parseModel`) — власний, на глобалах three r147; його об'єднання з `model/import.js` — окрема задача.
