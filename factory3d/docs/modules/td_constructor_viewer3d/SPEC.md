# td_constructor_viewer3d — специфікація

Міст «Конструктор» → «Переглядач» (етап 2, CD-25). Технічне рішення — [ARCHITECTURE.md](ARCHITECTURE.md). Суміжні
контракти: `td_viewer3d` R-01 п. 3 (провайдери), R-19 (злиття), R-25 (точка розширення ядра), Додаток A.15;
`td_constructor` (M-xx моделей `td.site`, `td.layout.version`, `td.placement`, `td.slot`, `td.equipment.variant`).

## 0. Дерево файлів

```
td_constructor_viewer3d/
  __manifest__.py            depends td_constructor, td_viewer3d; auto_install; assets
  models/viewer_provider.py  td.viewer.provider.layout (AbstractModel, sequence 180)
  models/layout_version.py   _inherit td.layout.version: create/unlink → подія шини
  tools/layout.py            diff(base, active) → {moved, added, hidden, replaced, frames}; load_inventory
  controllers/kiosk_model.py GET /f3d/kiosk/<token>/layout/model/<variant_id>
  static/src/layout/layout.js          applyLayout, moveNode; реєстрація розширення
  static/src/layout/slot_view.js       каркас і комірки нового місця
  static/src/layout/generic_models.js  умовні моделі за категорією, fitModel
  static/tests/hoot/layout.test.js     HOOT applyLayout
  tests/test_layout.py, test_hoot.py   Python і запуск HOOT
```

## 1. Маніфест

`name` «Завод 3D: розкладка конструктора у переглядачі», `version 19.0.1.0.0`, `depends = [td_constructor,
td_viewer3d]`, `auto_install = True`, `data = []`. Assets: `web.assets_backend` і `td_viewer3d.assets_kiosk` —
`static/src/layout/*.js`; `web.assets_unit_tests` — `static/tests/hoot/*`.

## 9. Алгоритми й правила

**R-01 Payload `layout`.** `build_layout(env)` (`tools/layout.py`). Версії: перша площадка з діючою (`active_version_id`) версією,
відмінною від бази (`is_seed`). Немає такої, немає права `read` на `td.site|layout.version|slot|placement|equipment.variant`
або знімка — `None`, ключ у payload не додається (кіоск — тихо, без `denied`/`error`). Формат (метри, градуси; координати
заводу: x уздовж, y впоперек; `rot` — проти годинникової):

| Ключ | Зміст |
|---|---|
| `site`, `version`, `base_version` | `{id, code, name}`; `{id, n, published_at}`; `{id, n}` |
| `moved` | `{код: {dx, dy, drot, delev}}`: розміщення за `td_code`, місця за префіксом, кожна комірка за кодом; зсув центра відносно бази |
| `added` | `[{code, kind: placement\|slot, name, category, front, dims {L,W,H}, x, y, rot, elev, model_url\|null, variant_id, template, params, cells [{code, lx, ly, lz, w, d, h, kind}]}]`; `lx, ly` — від центра місця, `lz` — від відмітки шару |
| `hidden` | `[код]`: прибрані розміщення й місця, а також старі комірки замінених місць |
| `replaced` | `[префікс місця]`: змінено параметри шаблону — старий каркас і комірки ховаються, нове місце в `added` |
| `frames` | `{префікс: {x, y, rot, L, W, template}}` — де шукати каркас місця в GLB серед вузлів `rack` (його код у GLB не збігається з префіксом) |

Положення бази розміщення — з `data/scene_inventory.json` (`{код: {x, y, z, L, W, H, yaw}}`, допускається обгортка
`{"objects": …}`), якщо код є в описі, інакше зі знімка бази; `moved` рахується як різниця центрів габаритного прямокутника
(`geometry.placement_obb`). Різниця менша за `1e-6` — не `moved`. `model_url` = `/f3d/constructor/model/<variant_id>/glb`
лише для варіанта з `model_glb`; зміна варіанта — заміна (`hidden` + `added`).

**R-02 Застосування (клієнт).** `applyLayout(api, layout)` викликає ядро (viewer R-25) після завантаження частини моделі, на
повній дельті, при зміні `layout` і при вигляді «Зараз» — **до** `stockLoad.sync`. Кожен виклик починає з бази: усе переставлене
повертається, приховане показується, додане знімається з `items` і відновлюється, тож застосування ідемпотентне й не накопичує
зсув. Початкова поза вузла зберігається в `userData.f3dBase` (`pos, quat, visible, centre`); `f3dRev` росте лише коли вузол
справді переставлено (stock_load розбирає комірку заново).

**R-03 `moved`.** Вузол `items.get(код)` (для місця без вузла за префіксом — найближчий вузол `rack` у межах 0,8 м від `frames[код]`)
зсувається на (dx, dy) і повертається на drot навколо центра свого bbox (мешів без службових `f3dStock`); `delev` — угору.
Blender (x, y, z) → three (x, z, −y). Підписи й підсвічування йдуть за вузлом, вибраний об'єкт — теж.

**R-04 `hidden`/`replaced`.** `visible = false`, вузол прибирається з `items` (не вибирається, не знаходиться за кодом, вантаж за
залишками з нього знімається), з сцени не видаляється; повернення — `layout = null` або новий `layout` без цього коду.

**R-05 `added`.** Місце: група з каркасом (`frameBoxes`: `pallet_rack`, `shelf`, `cantilever`; код каркаса = префікс) і комірками
(вузол на кожен `cells[].code`, невидимий об'єм-ціль, `kind` `stock` або `bin`, `f3dAlong` = вісь прольоту для розкладки палет).
Розміщення: група з умовною моделлю за `category` (`generic_models.buildGenericModel`, `fitModel` у габарит L×W×H) і невидимим
об'ємом для кліку; `model_url` — довантаження GLB варіанта (кеш за URL), помилка завантаження лишає умовну модель (warn). Об'єкт
реєструється в `items` (`userData.code, kind, label, f3dLayout`), має підпис (машини), вибір, картку й «Відкрити в Odoo».
Незмінний опис (`JSON.stringify`) не перебудовується; змінений — перебудова; зниклий — видалення з очищенням ресурсів.

**R-06 Кіоск.** `model_url` у кіоску клієнт замінює на `<client.base>/layout/model/<variant_id>`; контролер перевіряє токен
(`F3dKioskController._guard`) і віддає той самий GLB (`F3dModelController.download`, права читання варіанта). Інакше 404.

## 4. Права

Нових немає. Розділ `layout` — `_td_group = td_factory3d.group_td_user` (збирач закриває розділ для інших як `denied`);
додатково `has_access("read")` на моделі з R-01 — для кіоску й користувачів без прав «Конструктора» ключа немає.

## 7. API

Нових маршрутів, крім кіоскового GLB (R-06), немає: `layout` їде в `/f3d/viewer/data` (повний payload, схема 1.x, адитивно — viewer
Додаток A.15), у `/f3d/viewer/delta` (`patch.layout` — повна заміна, `null` — скинути) і в `/f3d/kiosk/<токен>/…`.
Шина: `_td_viewer_bus_models = [td.layout.version, td.site]`, подія `kind=state` з кодом площадки.

## 12. Acceptance Criteria

| AC | Given / When / Then | Перевірка |
|---|---|---|
| AC-01 | є діюча версія зі зсунутим CNC-2, новим розміщенням, прибраним UNLOAD-3 / збирається payload / `layout.moved["CNC-2"]`, `added`, `hidden` заповнені | `test_moved_added_hidden_replaced` |
| AC-02 | немає опублікованої версії / payload / ключа `layout` немає | `test_no_published_version_no_key` |
| AC-03 | користувач без `group_td_user` або кіоск без права читання версій / payload / ключа немає, без помилки | `test_rights`, `test_kiosk_silent_without_read_access` |
| AC-04 | публікація / шина й дельта / `patch.layout` повна, після видалення версії — `null` | `test_bus_event_and_delta`, `test_delta_after_version_removed_clears_layout` |
| AC-05 | змінені параметри шаблону місця / payload / `replaced`, старі комірки в `hidden`, нове місце в `added` | `test_cell_disabled_is_replacement`, `test_variant_change_is_replacement` |
| AC-06 | опис сцени містить положення коду / payload / `moved` від положення з опису | `test_inventory_pose_is_baseline` |
| AC-07 | `applyLayout` двічі з тим самим layout / HOOT / зсув не накопичується; `layout = null` повертає базу | `layout.test.js` «moved…» |
| AC-08 | додане розміщення й місце / HOOT / об'єкт у `items`, вибирається кліком, «Відкрити в Odoo» іде за кодом | `layout.test.js` «added…» |
| AC-09 | приховане / HOOT / `visible = false`, поза `items`, не вибирається, вантаж знято | `layout.test.js` «hidden…» |
| AC-10 | зсунута комірка з залишками / HOOT / палети в новому положенні, у старому порожньо | `layout.test.js` «порядок…» |
| AC-11 | кіоск / GLB варіанта за токеном | `TestKioskModel` |

## 13. План тестування

Python: `F3D_TEST_INSTALL=td_factory3d,td_viewer3d,td_constructor,td_constructor_viewer3d
factory3d/tools/odoo/run_tests.sh <db> /td_constructor_viewer3d`. HOOT (`tests/test_hoot.py`, фільтр
`@td_constructor_viewer3d`) і точка розширення (`td_viewer3d`, `extension.test.js`, R-25). Огляд на демо-шаблоні:
CNC-2 на 3 м, нова машина з каталогу, FG-R5 з 5 ярусами, UNLOAD-3 прибрано.

## 14. Definition of Done

Python- і HOOT-тести моста й `td_viewer3d` зелені; демо-набір (`/td_viewer3d,/test_td_viewer3d`) зелений з
встановленим мостом; без опублікованої версії «Переглядач» відтворює поведінку до моста.
