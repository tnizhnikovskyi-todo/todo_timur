# Контракт `ci.yml` для споживачів

Споживачі: `flow-package-build:gates-aggregator` (A-14, `references/c03-lookup.md`), B-11 (`package-upgrade-runner`), D-03, Тімлід.

## Перевірка
- Ім'я workflow `ci`, фінальний job `ci` — єдина required status check для `main` (вмикає Тімлід, не скіл).
- `ci` = агрегат: будь-який `failure`/`cancelled`, а також `skipped` там, де job мав іти, дає червоний статус.

## workflow_dispatch inputs
| Input | Умовчання | Зміст |
|---|---|---|
| `package_tag` | порожньо | тег пакета; порожньо — тег клієнта з `clients/REGISTRY.md` |
| `client` | порожньо | ідентифікатор клієнта за DATA_POLICY; порожньо — лише пакет |
| `odoo_version` | порожньо | порожньо — із суфікса `-odoo<N>` тега/гілки, інакше 19 |
| `sha` | порожньо | порожньо — HEAD гілки; інакше checkout саме цього SHA |
| `odoo_task` | порожньо | id задачі Odoo для звіту (розширення картки, відкрите В-2: звірити з B-11 і gates-aggregator) |

Усі inputs мають реально використовуватися в `resolve`/checkout, а не лише бути оголошеними.

## Статус на SHA
- push/PR — check-run на `head_sha`.
- dispatch — `head_sha` прогону = HEAD гілки, тому job `ci` додатково ставить commit status `context: ci` на input-SHA
  (`permissions: statuses: write`). A-14 шукає прогін через `actions_list` за SHA і читає `actions_get`.
- `run-name` містить SHA, ідентифікатор клієнта й тег; без назв юросіб.

## Тег пакета для клієнта
1. dispatch з `package_tag` -> він.
2. Інакше `clients/REGISTRY.md` на тому ж SHA: «тег-кандидат», якщо заповнений (B-11 фаза 1), інакше поточний тег.
3. Модулі клієнта тестуються проти пакета на цьому тезі (другий checkout `ref: <тег>`), не проти HEAD.
Формат `REGISTRY.md` у наряді не заданий: читай фактичний файл (автоекспорт `flow-state-keeper`); немає — відкрите питання в `memo`.

## Звіт у задачу Odoo
Job `report-odoo`: SHA, URL прогону, вердикти job'ів, лічильники; без логів. id задачі — input `odoo_task` або рядок `Odoo-Task: <id>`
в описі PR (`package/templates/pr-checklist.md`). Секрети `ODOO_FLOW_URL/DB/API_KEY` задає Тімлід; немає — notice без падіння
(відкрите В-5: права технічного користувача лише `message_post`). Джерело правди для гейтів — статус GitHub за SHA.
