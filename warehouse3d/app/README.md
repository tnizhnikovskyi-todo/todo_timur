# Конструктор склада — приложение (W-01 … W-03)

Раздел «3D-модель» прототипа (`../prototype/sklad.template.html`) как отдельное приложение: ядро без DOM,
экран отдельно, хост отдельно. Данные — снимок Odoo `../prototype/data.json` (склад WH) и синтетический второй склад WH2
(`src/core/demo.js`); Odoo приложение не меняет.

## Команды (из этого каталога, нужен `npm install`)

- `npm run dev` — vite, `http://localhost:5173`.
- `npm run build` — сборка в `dist/` (относительные пути, открывается с любого адреса).
- `npm test` — unit-тесты ядра и словарей (`node --test test/*.test.js`).
- `npm run e2e` — Playwright против `dist/` (нужны `npm run build` и глобальный `playwright`; браузер уже установлен).
- `npm run perf` — замер плавности (`e2e/perf.mjs`, после `npm run build`): WH и синтетический склад `?synthetic=10000`; печатает время построения 3D,
  draw calls, кадр при вращении (swiftshader медленнее видеокарты), время наведения и выбора в 2D. Критерий: draw calls ≤ 200, построение ≤ 3 с, перестройка без роста числа групп.

## Структура

- `src/core/` — без DOM и без модульных переменных. `model.js` — фабрика `createModel(project, storage, opts)`
  (`opts.bases` — снимки складов по `baseRef`); `project.js` (модель проекта v2, миграции, `openProject`, `nodesOf`),
  `demo.js` (демо-проект и склад WH2), `tree.js` (снимок + слой правок + настройки склада → дерево), `layout.js`
  (раскладка в метрах), `edit.js` (diff/apply, стек несохранённых, undo/redo, операции), `select.js` (чистая логика
  выделения), `storage.js` (интерфейс хранения + хранилище в памяти), `types.js` (константы).
  Подписи изменений и уведомлений — данные `{ k, p }`, текст собирает i18n.
- `src/view/` — `shell.js` (оболочка), `plan2d.js`, `plan3d.js` (three.js, грузится лениво), `panels.js`,
  `types.js` (окно типов мест), `help.js` (инструкция), `notify.js`, `keys.js`, `style.css`.
- `src/i18n/` — `uk.js`, `en.js`, `createI18n` → `t(key, params)`. Язык запоминается в `wh-app-lang`.
- `src/host/main.js` — загрузка данных, открытие проекта, монтирование view; `src/host/storage.js` — хранилище в `localStorage`
  (ключи `wh-app-*`, проект — `wh-app-project-<id>`).
- `src/core/synthetic.js` — генератор синтетического склада (n мест, 10 рядов × 20 стелажей × 5 ярусов на зону); хост подключает его по `?synthetic=N`
  (только для проверки: проект в памяти, `localStorage` не трогается).
- 3D (D-03): одинаковые элементы (геометрия + материал + тени) — один `InstancedMesh`; `paint` решает видимость и подсветку и собирает матрицы
  (`compose`), клик/наведение — raycast по инстансам → узел, перетаскивание сдвигает матрицы. Тени пересчитываются только при изменении сцены.
  2D: SVG создаётся один раз, перестройка меняет слой содержимого, подсветка — атрибутами только у изменившихся элементов.
  Отладочные данные для perf кладутся в `window.__WH_DEBUG`, если он задан до загрузки.
- `test/` — тесты ядра на `data.json` (`core`, `project`, `i18n`); `e2e/smoke.mjs` — сценарий в браузере (включая склады, ячейки и 390 px).

## Модель проекта v2 (`core/project.js`)

- `project { schema: 2, id, name, source { kind: odoo|file|scratch, name }, loaded_at, warehouses[] }`;
  `warehouse { id, code, name, company, baseRef | base, saved, pending, building: null }`.
  Склад владеет слоем правок: `saved` (SAVED) и `pending` (PENDING); типы мест склада — `saved.types` (`null` — общий
  справочник `BASE_TYPES`, иначе свой список поверх него). `building` — заготовка под W-04.
- Узлы склада производные: снимок Odoo + слой правок → дерево (`tree.js`) → `model.nodes()` / `nodesOf` даёт плоский
  список v2: `level` (zone, rack, bay, level, cell, floor), `tp`, `x y rot w d h`, `code`, `odoo_id` (null у новых и если
  в снимке нет id), `status` (existing, new, changed, archived), `is_location`. Корень любого склада — узел `WH` (id), подпись — код склада.
- Глубина локаций — часть слоя правок: `edit.depth` (`null` = `level` | `cell`) и `edit.depthZones [{ id зоны, d }]`; меняется
  операцией `ops.depth` через «Показати / Зберегти» с undo, как всё остальное. Ячейки яруса — `edit.cells [{ id яруса, n }]` (1–12, через «Показати / Зберегти»); при глубине `cell` и n > 1 ярус
  перестаёт быть местом, местами становятся ячейки `<код яруса>-1..n`.
- Хранилище (`core/storage.js`): `listProjects / loadProject / saveProject / deleteProject` — Promise, плюс синхронные
  настройки `read / write`. Формат версионирован (`migrateProject`). При первом запуске `openProject` создаёт демо-проект и
  переносит в склад WH правки прежних ключей (`wh-app-edit/pending`, прототип `wh-model-edit/pending`); старые ключи остаются.
  Нечитаемый проект не перезаписывается: сырая запись уходит в `wh-app-project-<id>.broken-<время>` (`backupBroken`), открывается
  демо-проект `demo-<время>`, `onNotice` → уведомление.

## Правила

- Любое изменение поведения обновляет инструкцию (`help.*` в `src/i18n/uk.js` и `en.js`) в том же коммите;
  шаг «инструкция» в `e2e/smoke.mjs` и тест словарей это проверяют по составу, но не по смыслу.
- Тексты интерфейса — только через словарь; `test/i18n.test.js` сверяет ключи uk/en и ключи из кода.
- В `src/core` нет `document` / `window`: `grep -rnE "document|window" src/core` должно быть пусто.
