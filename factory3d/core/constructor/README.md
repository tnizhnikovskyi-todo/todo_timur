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
| `types_catalog.js` … `i18n.js` | заглушки слайсів S1…S6 (див. «Волни») |

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
