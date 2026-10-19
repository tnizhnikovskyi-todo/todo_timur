# Ядро конструктора (CD-29): одне на модуль Odoo й прототип

JS + Three.js **без Odoo**: жодних імпортів `@web`, `@odoo`, `@td_constructor`, лише відносні (`./x.js`). Дані — через ОДИН впроваджений
адаптер; three.js, умовні моделі, тема й форми запису приходять від хоста. Перевіряє `node tools/test_core.mjs`.

## Розкладка

| Файл | Що |
|---|---|
| `index.js` | точка входу збірки: `mountEditor/unmountEditor`, реєстри, контракт, простори імен для тестів і мостів; **підключає слайси S1…S6** (файли слайсів реєструються у своїх модулях) |
| `app.js` | монтування, завантаження площадки, автозбереження, події шапки, `hotkeys`, життєвий цикл |
| `state.js` · `util.js` · `data.js` | `S`/`V`/`E` (стан, сцена, функції між модулями), утиліти, довідники й описи шаблонів |
| `cells.js` · `geometry.js` · `checks.js` · `live.js` | R-01…R-10: комірки, OBB/SAT, перевірки (дзеркала Python, золоті фікстури), «живі» перевірки |
| `scene.js` · `panels_left.js` · `panels_right.js` · `dialogs.js` · `fields.js` · `dxf.js` · `roles.js` · `body.js` | 3D-сцена, панелі, діалоги, підкладка DXF, права, розмітка |
| `adapter.js` | **контракт адаптера**, `BaseAdapter`, `assertAdapter`, `newUid`, `StoreError` |
| `adapter_odoo.js` | `OdooAdapter` (API `/f3d/constructor/*`; `rpc`, `orm`, `action`, `uploadModel` передає хост) + перетворення API↔стан |
| `artifact/` | лише прототип: `ArtifactAdapter` (`adapter_artifact.js`: db → localStorage → пам'ять, IndexedDB; `storage.js`), `odoo_sim.js` («Odoo» прототипа: план, журнал, відкат, категорії, оцінки), `sample.js` (+`seed/sample.json`, `fromProto`), `sample_locations.js`, `demo_stock.js`, `collab_artifact.js` (S6), діалоги каталогу й публікації, перевірки навантаження прототипу |
| `registry.js` | реєстри точок розширення |
| `host.js` · `three.js` | сервіси хоста й контейнер `THREE` |
| слайси S1…S6 | розділи «Слайс S1» … «Слайс S6» нижче: S1 `addr*.js`, `types_*.js`, `presets.js`, `library.js`, `shape_forms.js`; S2 `capacity*.js`, `plan_*.js`, `rules_dialog.js`; S3 `undo.js` … `s3_chrome.js`; S4 `parse_codes.js` … `autolayout.js`; S5 `building*.js`, `wizard.js`, `spec.js`, `plan_doc.js`, `docs_ui.js`; S6 `variants.js` … `i18n.js` |

## Слайс S1 «Структура місця» (F01, F08, F09-06/07)

| Файл | Що |
|---|---|
| `addr_core.js` · `addr.js` | адресація (F01): шаблон коду `{zone} {row} {bay} {level} {pos}` (+ UK/EN-синоніми), сегменти цифрами/літерами, напрями рядів і секцій, наслідування площадка → зона → місце, пресет `legacy` (коди як раніше). `addr_core.js` — чисте дзеркало `services/addr.py` (еталон — `static/tests/fixtures/addr_golden.json`); `addr.js` — панелі «Адресація» (площадка, зона, місце), попередній перегляд кодів (перші 10 й останній, скільки кодів зміниться, повтори), «Застосувати» й перенумерація, контекст адресації для `cellsOf`, закріплення номера ряду нових місць |
| `types_data.js` · `types_catalog.js` · `types_ui.js` | каталог 50 типів на семи генераторах (`pallet_rack`, `cantilever`, `shelf`, `floor_stack`, `floor_spot`, `machine_spot`, `zone`): група, форма 3D, «меблева» важливість ●/○/—, вид локації; діалог каталогу (пошук, фільтр «лише ті, що є на меблевій фабриці»), «Додати в проєкт» / «Додати на план», блок «Тип» («Конструкція ряду» / «Як у типу»), вкладка «Типи». `types_data.js` — єдине джерело: `data/td_slot_type_data.xml` модуля **генерується** з нього (`tools/test_core_s1.mjs`) |
| `shape_forms.js` | 9 форм типів у 3D і 2D (реєстр `shapes`): стійка, рулонний стелаж, штабель, зона, огорожа/камера, циліндр/бункер, шафа-машина, мобільний носій, ворота/док |
| `presets.js` · `library.js` | пресети «ряд», «секція», «виділене» (`data` R-22) і бібліотека типів і пресетів, спільна для проєктів (у Odoo — на компанію) |

**Адаптер** (`capabilities.library`): `library({op: "list"|"save"|"delete", kind: "type"|"preset", id?, vals?})` → API-11 `/library` → `{types, presets}` / `{record}`; бібліотека лежить у `S.site.library`. `saveAddr(vals, {renumber: "new"|"all"})` → `POST /f3d/constructor/site/addr`
(`addr`, `loc_tree`, `depth_mode`; сервер переносить правки комірок і розміщення на нові коди — `OdooAdapter.serverRenumber = true`). Прототип: бібліотека в `db` (`settings/library`), адресація й перенумерація — повністю в ядрі.

## Слайс S2 «Зв'язок з Odoo» (F02 без F02-09/12, F03, F04)

| Файл | Що |
|---|---|
| `capacity_core.js` | чиста логіка без DOM і без Odoo: ємність, зведення (місць, палетомісць, площа, об'єм, ємність у кг), «чи вміститься», перевірки `cell_load`, `putaway_fit`, `code_conflict`, оцінка «куди покладе» (дзеркало `services/capacity.py`, `putaway.py`; спільні випадки — `fixtures/s2_fit_cases.json`); синхронні перевірки читають лише кеш, який наповнюють панелі |
| `capacity_ui.js` | панелі ємності й зберігання: категорії зберігання, стратегія списання, функція й атрибути зони, габарити/вага комірки з джерелом, прапорці локації (`usage`, `replenish_location`), min/max, діалог «Категорії зберігання», налаштування перевірок ємності (рядок `td.check.config` створюється при першому вмиканні) |
| `plan_core.js` · `plan_dialog.js` | план змін: види рядків (`create`, `move`, `rename`, `attrs`, `update`, `archive`), область (зона/ряд), залежності (батьки додаються самі), таблиця для файла імпорту (F02-06), оцінка відкату; діалоги `plan` і `planLog` (журнал, відкат) |
| `rules_dialog.js` | правила розміщення й поповнення: список із позначками «нове / змінене / буде видалено», форма, підсвічування цілі (метрика `rule_target`), «Куди покладе Odoo», «Чи вміститься», блок «Правила розміщення сюди» у властивостях місця |
| `artifact/odoo_sim.js` · `artifact/checks_extra.js` | лише прототип: імітація «Odoo» і перевірки навантаження прототипа |

Нейтральні терміни (CD-30): «категорія зберігання», «стратегія списання», «правило розміщення», «правило поповнення»; рядок плану `{kind, res, code, name, changes, selected, blocked, blocked_reason, flags, depends_code, scope_uid, zone_uid, before, vals}`, `res` ∈ `location | equipment | workcenter | replenish | putaway` (`adapter_odoo.js` переводить `res_model`).

**Адаптер** (`capabilities.storage`, `putaway`, `rollback`): `categories({op})` → API-12 `/storage_categories` (+ `/removal_strategies`); `stockLoads(codes?)` → `/storage/loads` (`{loads, limits}`); `codesCheck(codes)` → API-17 `/codes/check`; `putawayWhere(q)` / `putawayFit()` / `lookup(kind, term, ids)` →
API-15 `/putaway/where`, `/putaway/fit`, `/putaway/lookup`; `planLog()` / `planOps(versionId)` / `rollback(versionId)` → API-18 `/publish/log`, `/publish/rollback` (`confirm: true`). У модулі «Опублікувати» відкриває майстер Odoo (API-06), журнал і відкат — діалог ядра. Прототип: `odoo_sim.js` вмикає `storage`, `putaway`, `rollback` на `ArtifactAdapter`, «Куди покладе» — «оцінка».

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

## Слайс S6 «Спільна робота й навчання» (F12, F13, F14, F19, N-01, N-03)

| Файл | Що |
|---|---|
| `collab_ui.js` | спільна основа S6: вбудовані стилі, шар накладок над 3D-сценою, проєкція точок сцени на екран, хук «після кожного кадру» (`V.renderer.render` обгортається один раз: значки й мініатюра оновлюються разом зі сценою, `scene.js` не змінюється) |
| `variants.js` | варіанти планування (F12): «Як є», «Проєкт A/B…» до 12 на площадку, «Створити з поточного», зробити активним (чернетка не втрачається), перейменувати, видалити, порівняння двох (цифри `cells`, `places`, `area`, `volume`, `max_weight` рахує ядро: `variantMetrics`; + `ops`), «Навчальна копія» (F12-05, F19-04); активний варіант один — у ньому йдуть застосування й публікація (F12-04) |
| `comments.js` | коментарі й задачі (F13): нотатка чи задача на складі, шарі, місці, комірці, розміщенні, об'єкті будівлі; значки з числом у 2D/3D (синій — нотатка, помаранчевий — відкрита задача, сірий — усе вирішено), блок у правій панелі (окрема панель під властивостями), вкладка зі списком і фільтрами (статус, вид, текст, «лише цей об'єкт»), опитування раз на 15 с без втрати набраного |
| `locks.js` | блокування зон (F14): вибір об'єкта в режимі правки орендує його зону на 5 хв (продовження раз на хвилину, зняття при виході чи закритті), значки з іменем (червоний — чужа, зелений — моя), список оренд раз на 15 с, банер оновлюється на місці; зона = найменша зона-контур, що містить центр, інакше сам об'єкт (дзеркало `td.zone.lock`) |
| `versions_ui.js` | історія версій (N-03): останні 50, нотатка до версії, «Переглянути» (схема й цифри поруч із поточним станом, лише читання), «Відновити» (спершу поточна чернетка зберігається контрольною точкою), «Зберегти точку»; замінює базовий діалог `history` записом у реєстрі з `force` |
| `levels.js` · `minimap.js` | рівні й навігація (N-01): WH › зона › ряд › стелаж › ярус (ховає решту, камера наїжджає, «↑» — U, «⟲»), «Клік виділяє: Місце / Стелаж / Ряд / Зона»; мініатюра плану з рамкою поточного виду (клік/перетягування переносить камеру) — обидва через хук кадру `collab_ui.js` |
| `tours.js` · `tour_defs.js` · `help_topics.js` | тури й інструкція (F19): тур новачка (13 кроків), 11 тематичних (`basic`, `rack`, `import`, `scratch`, `address`, `putaway`, `apply`, `find`, `labels`, `docs`, `team`), кроки «прочитати» й «дія» з «Показати мені», запуск зі списку чи `#tour-<id>`, ←/→/Esc; тур, що змінює дані, йде в навчальній копії («Залишити зміни» / «Скасувати», перерваний — пропозиція прибрати копію); «Інструкція» на 36 тем. Тексти двомовні `[UK, EN]`; на телефоні тури недоступні |
| `i18n.js` | мови UK/EN (F19-05, CD-31 Q7): `t()` для рядків ядра (українська — ключ), `addEn({...})`, `addPattern()`, DOM-перекладач; вибір мови в браузері (`f3d_constructor_lang`), без вибору — `host.lang`, інакше UK |
| `artifact/collab_artifact.js` | лише прототип: «сервер» варіантів, коментарів і версій у браузері (ті самі виклики, що API-21/22/24) |

**Адаптер** (`capabilities.variants`, `comments`, `locks`; історія — метод `versions`): `variants(req)` → API-21 `/variants` (`op`: `list|create|activate|rename|delete|end_training`); `comments(req)` → API-22 `/comments` (`list|create|update|resolve|delete|assignees`); `locks(req)` → API-23 `/locks` (`list|acquire|release`);
`versions({op})` → API-24 `/version/view` (`list|view`) і `/version/checkpoint` (`create|note`). Сторінка «Інструкція» в Odoo — `GET /f3d/constructor/help`: **ті самі 36 тем**, що `help_topics.js` (зіставлення перевіряє `tests/test_s6_help.py`); окремі тури `web_tour` (`td_constructor_guide_tour`, `_variants_tour`, `_collab_tour`) лежать у модулі (`static/src/tours/*`, bundle `web.assets_tests`) і ядру не належать.

**Обмеження прототипа (артефакта).** Користувач один, сервера немає: **блокування зон не емулюються** (`capabilities.locks = false`: кнопок і значків немає); коментарі й задачі **без виконавців і без завдань Odoo** (`mail.activity` — лише в модулі); варіанти й версії живуть у `db` цього браузера (колекція `variants` — документ площадки
`{items, active, seq}` + знімки `<id>.<n>`; `comments` — `{seq, items}`; один документ на варіант, бюджет `db` 256 КіБ ділить `storage.js`); PDF — «на сервері».
**Мови.** `t()` застосовано лише в 7 файлах S6 (`comments`, `levels`, `locks`, `minimap`, `tours`, `variants`, `versions_ui`); решту ядра (≈ 20 файлів: `app`, `panels_*`, `dialogs`, `fields`, `addr`, `types_ui`, `capacity_ui`, `rules_dialog`, `plan_dialog`, `files_ui`, `sync_ui`, `docs_ui`, `building_ui`, `wizard`, …) у режимі EN перекладає DOM-перекладач
(точні фрази й шаблони з `i18n.js`, атрибути `title`/`placeholder`/`aria-label`); те, чого в його словнику немає, лишається українською. Обгортання в `t()` — відкрите питання Q-15.

## Контракт адаптера (`adapter.js`)

`load(siteId)` → стан · `save(state, {now})` (порівняння зі станом адаптера, черга, автозбереження) · `flush()` · `check(layerId?)` ·
`publish({onClose, state})` · `uploadModel(variantId, payload)` · `restoreVersion(id)` · `listSites()` · `createSite(o)` · `saveSite(vals)` ·
`saveCheck(key, vals)` · `loadModel(variant, THREE)` · `attachUnderlay/detachUnderlay/loadUnderlay` · `ensureGroupIds(roles)` · `capabilities` ·
зворотні виклики `onStatus/onSaved/onConflict/onReject/onReload`. **Методи можливостей** (їх немає в `REQUIRED_METHODS`; ядро викликає, лише якщо `can(name)`): `library`, `saveAddr` (S1); `categories`, `stockLoads`, `codesCheck`, `putawayWhere`, `putawayFit`, `lookup`, `planLog`, `planOps`, `rollback` (S2); `stock`, `find`, `render` (S3); `locations`, `sync`, `saveParseRules`, `parseTable` (S4); `saveWizard`, `warehouses` (S5); `variants`, `comments`, `locks`, `versions` (S6). Стан (`site`, `layers`, `slots`, `placements`, `catalog`, `settings`,
`versions`, `rights`) описано в шапці `adapter.js`. У ядрі — нейтральні терміни («місце зберігання», «категорія», «правило»): імена
`stock.*` знає лише `adapter_odoo.js` (CD-30). Нова можливість адаптера: додати ім'я в `CAPABILITY_NAMES` (registry.js), виставити в
`capabilities`, ховати функцію через `can(name)`.

## Реєстри (`registry.js`)

`panels` (вкладки лівої панелі `area:"left"`; блоки правої `area:"right"|"site"|"slot"|"placement"`) · `dialogs` (`newSite`, `history`,
`serverIssues`, `conflict`, `confirm`, `help`, `hotkeys`; слайсів — `catalog`, `typeNew`, `typeResize`, `library`, `presetSave`, `presetInsert` (S1), `plan`, `planLog`, `categories`, `rules` (S2), `labels`, `array`, `bulk` (S3), `parseCodes`, `importLocations`, `exportLocations`, `syncOdoo` (S4), `wizardNew`, `spec`, `planDoc` (S5), `tours` (S6); від хоста — `variantForm`, `passportForm`, `record`) · `checks` (`{run, config?}`; `runChecks`
ітерує реєстр; слайси додають `cell_load`, `putaway_fit`, `code_conflict` (S2), `inside`, `aisle_width`, `height` (S5)) · `shapes` (каркаси шаблонів; нові форми типів) · `metrics` (колір комірки за `S.ui.metric`) · `menu` (`top`/`more`) ·
`hotkeys` (`{code|key|match, run, typing?}`) · `capabilities`. Запис: `registries.X.add(key, value, {sequence, force})`; повторний
ключ без `force` — помилка. Слайс реєструється **з свого файлу** (заглушка вже підключена в `index.js`).

## Збірка й тести

```
node tools/build_core.mjs module [--check]   # → odoo_addons/td_constructor/static/lib/f3d-core/constructor.esm.js (коміт; оновлює CORE_BUILD)
python3 build/constructor/proto/build.py     # → build/constructor/proto/index.html (esbuild IIFE + стилі модуля)
node tools/test_core.mjs                     # Node, без Odoo; з ESBUILD_DIR перевіряє свіжість збірки модуля; підключає test_core_s1…s6.mjs
node tools/test_core_s<N>.mjs                # окремо слайс (S1 адреси й каталог, S2 план і правила, S3 робота зі складом, S4 структура й файли, S5 будівля й документи, S6 спільна робота й навчання)
```

`ESBUILD_DIR` — каталог з `node_modules/esbuild` (без нього збірка робить `npm install esbuild` у тимчасовий каталог). Після правки `core/`
**перезберіть модуль** і закомітьте `constructor.esm.js` (при паралельних слайсах конфлікт у ньому розв'язується перезбіркою).

- Модуль: дія `static/src/action/constructor_action.js` → `static/src/editor/odoo_host.js` (хост, діалоги форм Odoo) → `core_loader.js`
  (динамічний import збірки). HOOT-тести редактора беруть ядро через `tests/editor/core.js` (`beforeEach(setupCore)`).
- Прототип: `build/constructor/proto/src/main.js` (хост артефакта) + `page.css`; стилі редактора — `constructor_action.scss` модуля.
  Playwright-тести — `build/constructor/proto/test_*.js` (`test_s1…s6.js`, `test_scene.js`, `smoke.js`, …; потрібні каталоги `vendor/` і `fixtures/` поза репозиторієм). Бюджет розміру прототипу — 900 КБ (`test_scene.js`; після S6 мінімізований — 833 КБ).
- Ядро в модулі — `static/lib/f3d-core/constructor.esm.js` (≈ 1 МБ, коміт), хеш `CORE_BUILD` — у `core_loader.js`. У Odoo-тестах Node-набір запускає `TestCoreNode`, HOOT — `static/tests/editor/s3…s6.test.js`.

## Що змінюється разом з ядром

Умовні 3D-моделі (`model/generic.js`) і завантажувачі моделей (`model/*`) лишаються в модулі (W3): хост передає `buildGenericModel` /
`loadLoaders`; прототип збирає `model/generic.js` тим самим esbuild. Імпорт моделей у прототипі (`artifact/adapter_artifact.js`
`parseModel`) — власний, на глобалах three r147; його об'єднання з `model/import.js` — окрема задача.
