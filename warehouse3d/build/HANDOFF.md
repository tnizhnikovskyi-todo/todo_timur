# Передача контекста менеджера (после сжатия читать первым)

Обновлено: 2026-10-16. Роль: менеджер проекта (план, постановка задач агентам, приёмка, STATUS.md). Код сам не пишу.
Правила — `CLAUDE.md`; план — `PLAN.md` (v0.3, решения D-01…D-25); состояние — `STATUS.md`; туры — `TOURS.md`; типы мест — `TYPES.md`.

## Ссылки
- Приложение (артефакт, версия 14): https://claude.ai/artifact/9uobU9NBT4bwLssUkA2Bsj — видно организации.
- Вопросы заказчику (канал): https://claude.ai/artifact/B39oXG95VZckRsYRDg5vhe — открытых нет. Порядок — `CLAUDE.md`.
- Ветка (пушить только её): `claude/admiring-dirac-rsqz9c`. PR не создавать.
- Один HTML: `warehouse3d/konstruktor-skladu.html` (собирается `npm run build:single`, копия коммитится).

## Что сейчас идёт
- **W-24** — туры по типовым задачам (11 туров из `TOURS.md`, меню «Тури», `#tour-<id>`, учебная копия-вариант)
  + выход из инструкции («← До моделі», повторный клик «Інструкція», 2D/3D/Будівля/Редагувати, Esc).
  Агент `coder` в worktree, id агента для SendMessage: `adca547512b3e725c`.
- Заказчик просил: **после приёмки W-24 — опубликовать в артефакт** и прислать обновлённый HTML.

## Темп
D-25: по одному пакету одновременно. Агентов — `coder` (Sonnet), поиск — `scout` (Haiku), в отдельном worktree (`isolation: worktree`).

## Приёмка пакета (делаю сам, только после зелёного — слияние)
```
cd <worktree>/warehouse3d/app && (ls node_modules/jsqr >/dev/null 2>&1 || npm ci --silent)
npm test | grep -E "^# (pass|fail)"; grep -rnE "document|window" src/core | wc -l
npm run build | tail -1; npm run e2e (дважды) | grep -E "FAIL|шагов"; npm run perf | tail -1
# если менялся модуль Odoo: WH_ODOO=19 warehouse3d/tools/odoo/run_tests.sh <db> | grep tests.result
```
Долгие проверки — в фоне (`run_in_background`). Слияние: `git merge --no-ff <ветка worktree>` в основную копию,
`git worktree remove --force …`, `git branch -D …`, обновить STATUS.md, commit + push.
Конфликты при слиянии — не разрешаю сам: `git merge --abort` и SendMessage тому же агенту «влей основную ветку».
Пакет без обновления инструкции (`src/i18n/help.js`, uk/en) не принимается.

## Публикация в артефакт
```
cd warehouse3d/app && npm ci --silent && npm run build:artifact
# → dist/artifact.html (страница) и dist/artifact-files.json (published ./assets/… → dist/assets/…)
```
Artifact publish: `file_path=/home/user/todo_timur/warehouse3d/app/dist/artifact.html`,
`url=https://claude.ai/artifact/9uobU9NBT4bwLssUkA2Bsj`, `root=/home/user/todo_timur/warehouse3d/app`,
`files` = карта из artifact-files.json с ключами БЕЗ «./» (`assets/x.js` → `dist/assets/x.js`),
`capabilities={"db":{}, "user":{}, "downloads":true}`. Имена файлов меняются при каждой сборке — карту строить заново.
Отправить пользователю `warehouse3d/konstruktor-skladu.html` (SendUserFile, attach).

## Среда
- Odoo 18/19 — `warehouse3d/tools/odoo/` (ENV.md, setup.sh идемпотентный, run_tests.sh, serve.sh, prepare_module.sh).
- Модуль Odoo: `warehouse3d/odoo_addons/wh_constructor`. Приложение: `warehouse3d/app/`. Прототип: `warehouse3d/prototype/`.
- Время заказчика — Киев. Контейнер может перезапускаться: фоновые проверки тогда перезапустить.

## Открыто
- I-05 — проверить на первой реальной базе клиента ключ мест по штрихкоду.
- Не проверено вживую: 3D на реальной видеокарте, печать на Zebra, XLSX в Excel, ABC/возраст на живой базе.
