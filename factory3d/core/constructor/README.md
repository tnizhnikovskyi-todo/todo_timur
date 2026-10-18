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
| `undo.js` | скасування/повтор (F09-01): знімок після кожної зміни (шари, місця, розміщення, правила S2 `S.site.rules`, адресація площадки); підпис кроку — `E.undoLabel(текст)`, `E.commit({label})` чи виведений із різниці; `E.undo/redo/undoReset/undoRebase`; відновлення — звичайний `E.commit`, тож адаптер сам ставить create/write/unlink; зміну `saveAddr` відновлює виклик адаптера |
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
