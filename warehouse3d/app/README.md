# Конструктор склада — приложение (W-01)

Раздел «3D-модель» прототипа (`../prototype/sklad.template.html`) как отдельное приложение: ядро без DOM,
экран отдельно, хост отдельно. Данные — снимок Odoo `../prototype/data.json`; Odoo приложение не меняет.

## Команды (из этого каталога, нужен `npm install`)

- `npm run dev` — vite, `http://localhost:5173`.
- `npm run build` — сборка в `dist/` (относительные пути, открывается с любого адреса).
- `npm test` — unit-тесты ядра и словарей (`node --test test/*.test.js`).
- `npm run e2e` — Playwright против `dist/` (нужны `npm run build` и глобальный `playwright`; браузер уже установлен).

## Структура

- `src/core/` — без DOM и без модульных переменных. `model.js` — фабрика `createModel(data, storage, opts)`;
  `tree.js` (данные + слой правок → дерево), `layout.js` (раскладка в метрах), `edit.js` (diff/apply, стек
  несохранённых, undo/redo, операции), `select.js` (чистая логика выделения), `storage.js` (интерфейс хранения),
  `types.js` (константы). Подписи изменений и уведомлений — данные `{ k, p }`, текст собирает i18n.
- `src/view/` — `shell.js` (оболочка), `plan2d.js`, `plan3d.js` (three.js, грузится лениво), `panels.js`,
  `types.js` (окно типов мест), `help.js` (инструкция), `notify.js`, `keys.js`, `style.css`.
- `src/i18n/` — `uk.js`, `en.js`, `createI18n` → `t(key, params)`. Язык запоминается в `wh-app-lang`.
- `src/host/main.js` — загрузка данных, хранилище в `localStorage` (ключи `wh-app-*`), монтирование view.
- `test/` — тесты ядра на `data.json`; `e2e/smoke.mjs` — сценарий в браузере (включая 390 px).

## Правила

- Любое изменение поведения обновляет инструкцию (`help.*` в `src/i18n/uk.js` и `en.js`) в том же коммите;
  шаг «инструкция» в `e2e/smoke.mjs` и тест словарей это проверяют по составу, но не по смыслу.
- Тексты интерфейса — только через словарь; `test/i18n.test.js` сверяет ключи uk/en и ключи из кода.
- В `src/core` нет `document` / `window`: `grep -rnE "document|window" src/core` должно быть пусто.
